"""Read-only E3 preparation contracts; no kernel, mount or service mutation.

Only collector tests launch actual children: fixed, harmless local Python code.
They do not establish real E3 supervision or authorize any workload.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import probe_e3_host as probe


@unittest.skipUnless(sys.platform == "linux", "E3 host observation is Linux-only")
class E3ProbeCollectorTests(unittest.TestCase):
    @staticmethod
    def stop_fixture_child(child):
        if child.poll() is None:
            child.kill()
        child.wait(timeout=2)
        for pipe in (child.stdout, child.stderr):
            if pipe is not None and not pipe.closed:
                pipe.close()

    def collect(self, code, *, timeout=.2, maximum=4096):
        actual = subprocess.Popen
        children = []
        def launch(*args, **kwargs):
            child = actual(*args, **kwargs)
            children.append(child)
            self.addCleanup(self.stop_fixture_child, child)
            return child
        with mock.patch.object(probe.subprocess, "Popen", side_effect=launch):
            result = probe._capture([sys.executable, "-I", "-c", code], {"LANG": "C", "LC_ALL": "C"},
                timeout_seconds=timeout, max_output_bytes=maximum)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll(), "collector returned while its actual child was still live")
        self.assertTrue(children[0].stdout.closed)
        self.assertEqual(result["cleanup"], "CONFIRMED")
        self.assertLessEqual(len(result["stdout"]), maximum)
        self.assertLessEqual(result["stdout_bytes_seen"] + result["stderr_bytes_seen"], maximum + 1)
        return result

    def test_real_fixed_child_has_no_inherited_environment_or_stdin(self):
        code = "import json,os,sys;print(json.dumps([os.environ.get('E3_PROBE_TEST_SECRET'),sys.stdin.read()]))"
        with mock.patch.dict(os.environ, {"E3_PROBE_TEST_SECRET": "must-not-inherit"}):
            result = self.collect(code, timeout=2)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(json.loads(result["stdout"]), [None, ""])

    def test_real_child_timeout_stops_and_reaps_with_a_wall_bound(self):
        before = time.monotonic()
        result = self.collect("import time;time.sleep(30)")
        self.assertLess(time.monotonic() - before, 3)
        self.assertEqual(result["status"], "TIMEOUT")
        self.assertIsNotNone(result["exit_code"])

    def test_real_child_stdout_and_stderr_overflow_are_bounded(self):
        for stream in (1, 2):
            with self.subTest(stream=stream):
                before = time.monotonic()
                result = self.collect(f"import os;os.write({stream},b'x'*(2*1024*1024))", timeout=2)
                self.assertLess(time.monotonic() - before, 3)
                self.assertEqual(result["status"], "OUTPUT_LIMIT")

    def test_denied_child_cleanup_stays_unresolved_and_does_not_claim_stopped(self):
        actual = subprocess.Popen
        children = []
        def launch(*args, **kwargs):
            child = actual(*args, **kwargs)
            children.append(child)
            self.addCleanup(self.stop_fixture_child, child)
            return child
        with mock.patch.object(probe.subprocess, "Popen", side_effect=launch), \
                mock.patch.object(probe, "_UNRESOLVED_CHILDREN", []), \
                mock.patch.object(probe.os, "killpg", side_effect=PermissionError("private cleanup detail")):
            before = time.monotonic()
            result = probe._capture([sys.executable, "-I", "-c", "import time;time.sleep(30)"], {},
                                    timeout_seconds=.02, max_output_bytes=1024)
        self.assertLess(time.monotonic() - before, 2)
        self.assertIsNone(children[0].poll())
        self.assertIsNone(result["exit_code"])
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(result["cleanup"], "UNRESOLVED")
        self.assertEqual(result["trigger"], "TIMEOUT")
        self.assertNotIn("private cleanup detail", repr(result))

    def test_selector_cleanup_failure_is_unresolved_after_actual_direct_child_exit(self):
        selector = probe.selectors.DefaultSelector()
        close = selector.close
        def fail_close():
            close()
            raise OSError("private selector cleanup detail")
        with mock.patch.object(probe.selectors, "DefaultSelector", return_value=selector), \
                mock.patch.object(selector, "close", side_effect=fail_close):
            result = probe._capture([sys.executable, "-I", "-c", "print('fixture')"], {},
                                    timeout_seconds=2, max_output_bytes=1024)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(result["cleanup"], "UNRESOLVED")
        self.assertEqual(result["trigger"], "COMPLETED")
        self.assertNotIn("private selector cleanup detail", repr(result))


@unittest.skipUnless(sys.platform == "linux", "E3 host observation is Linux-only")
class E3ProbeInputTests(unittest.TestCase):
    def test_cli_rejects_commands_remote_environment_and_noncanonical_inputs_before_probe(self):
        candidates = [
            ["--command", "touch /tmp/no"], ["--remote", "host.example.test"],
            ["--ssh", "host.example.test"], ["--env", "TOKEN=value"],
            ["--systemctl", "/foreign/systemctl"], ["--expected-uid", "-1"],
            ["--expected-uid", "1.2"], ["--cgroup", "/sys/fs/cgroup/fixture.slice"],
            ["--slice", "fixture.slice"], ["--mount-target", "relative"],
            ["--mount-target", "/mnt/../private"], ["--mount-target", "//host/share"],
            ["--mount-target", "/mnt//archive"], ["--mount-target", "/mnt/archive/"],
            ["--mount-target", "/mnt/archive\nsecret"],
            ["--cgroup", "/sys/fs/cgroup-other/fixture", "--slice", "fixture.slice"],
            ["--cgroup", "/sys/fs/cgroup/../fixture", "--slice", "fixture.slice"],
            ["--cgroup", "/sys/fs/cgroup/fixture", "--slice", "../fixture.slice"],
            ["--cgroup", "/sys/fs/cgroup/fixture", "--slice", "--user.slice"],
            ["--cgroup", "/sys/fs/cgroup/fixture", "--slice", "fixture.service"],
            ["--cgroup", "", "--slice", ""],
            sum((["--mount-target", f"/synthetic/{number}"] for number in range(9)), []),
        ]
        for argv in candidates:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), \
                    mock.patch.object(probe, "probe", side_effect=AssertionError("invalid input reached probe")):
                with self.assertRaises(SystemExit) as error:
                    probe.main(argv)
                self.assertEqual(error.exception.code, 2)

    def test_mount_input_validation_is_literal_and_does_not_touch_the_target(self):
        with mock.patch.object(Path, "stat", side_effect=AssertionError("target stat")), \
                mock.patch.object(Path, "resolve", side_effect=AssertionError("target resolution")), \
                mock.patch.object(os, "access", side_effect=AssertionError("target access")):
            args = probe.parse_args(["--expected-uid", "1001", "--cgroup", "/sys/fs/cgroup/fixture.slice",
                                     "--slice", "fixture.slice", "--mount-target", "/mnt/private-archive"])
        self.assertEqual(args.expected_uid, 1001)
        self.assertEqual(args.mount_target, ["/mnt/private-archive"])

    def test_cli_json_and_exit_zero_mean_observation_completed_never_acceptance(self):
        for readiness in ("BLOCKED", "INCOMPLETE", "OBSERVED_NOT_ACCEPTED"):
            report = {"schema_version": "infra-local-hand-e3-host-probe/v1", "readiness": readiness,
                      "real_e3_accepted": False, "production_supported": False, "business_authorized": False}
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(readiness=readiness), mock.patch.object(probe, "probe", return_value=report), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(probe.main(["--label", "scratch"]), 0)
            self.assertEqual(json.loads(stdout.getvalue()), report)
            self.assertEqual(stderr.getvalue(), "")

    def test_report_overflow_and_unhandled_error_return_small_unknown_json_without_details(self):
        for failure in (ValueError("credential-secret"), {"oversized": "x" * probe.MAX_REPORT_BYTES}):
            stdout = io.StringIO()
            options = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
            with self.subTest(failure=type(failure).__name__), mock.patch.object(probe, "probe", **options), \
                    contextlib.redirect_stdout(stdout):
                self.assertEqual(probe.main([]), 0)
            encoded = stdout.getvalue()
            result = json.loads(encoded)
            self.assertLess(len(encoded), probe.MAX_REPORT_BYTES)
            self.assertEqual(result["readiness"], "INCOMPLETE")
            self.assertFalse(result["real_e3_accepted"])
            self.assertFalse(result["production_supported"])
            self.assertFalse(result["business_authorized"])
            self.assertNotIn("credential-secret", encoded)


MOUNTINFO = (b"1 0 0:1 / / rw - ext4 /dev/private-source rw,password=mount-secret\n"
             b"2 1 0:2 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n"
             b"3 1 0:3 / /mnt/archive rw - cifs //private-server/private-share rw,username=private-user,password=mount-secret\n")


@contextlib.contextmanager
def observed_host(*, argv=None, uid=1001, pid1=b"systemd\n", mountinfo=MOUNTINFO, read_error=None,
                  command=None):
    """Synthetic local observations, never a real cgroup/NAS acceptance fixture."""
    args = probe.parse_args(argv if argv is not None else ["--expected-uid", "1001", "--cgroup",
        "/sys/fs/cgroup/fixture.slice", "--slice", "fixture.slice", "--mount-target", "/mnt/archive/job"])
    pid = os.getpid()
    calls = []
    source = Path(probe.__file__).read_bytes()
    def read(path, maximum):
        path = os.fspath(path)
        if path == str(Path(probe.__file__).resolve()):
            return source
        if read_error:
            raise read_error
        values = {"/proc/1/comm": pid1, f"/proc/{pid}/mountinfo": mountinfo,
                  "/proc/sys/kernel/random/boot_id": b"12345678-1234-4234-8234-123456789abc\n",
                  f"/proc/{pid}/cgroup": b"0::/fixture.slice\n"}
        if path not in values:
            raise AssertionError("probe attempted undeclared path " + path)
        return values[path]
    def capture(argv, environment, **bounds):
        calls.append((argv, environment, bounds))
        if command:
            return command(argv, environment, **bounds)
        if argv[-1] == "--version":
            raw = b"systemd 257 (private-version-detail)\nprivate-feature-detail\n"
        elif "fixture.slice" in argv:
            raw = (b"Id=fixture.slice\nLoadState=loaded\nActiveState=active\nSubState=active\n"
                   b"ControlGroup=/fixture.slice\nCPUAccounting=yes\nMemoryAccounting=yes\nTasksAccounting=yes\n")
        else:
            raw = b"Version=257\nControlGroup=/fixture.slice\nSystemState=running\n"
        return {"status": "COMPLETED", "trigger": "COMPLETED", "cleanup": "CONFIRMED", "exit_code": 0,
                "stdout": raw, "stdout_bytes_seen": len(raw), "stderr_bytes_seen": 0,
                "output_limit_bytes": probe.MAX_COMMAND_BYTES}
    with mock.patch.object(probe.sys, "platform", "linux"), \
            mock.patch.object(probe.sys, "version_info", (3, 12, 0)), \
            mock.patch.object(probe.os, "getuid", return_value=uid), \
            mock.patch.object(probe.os, "geteuid", return_value=uid), \
            mock.patch.object(probe.os, "readlink", side_effect=lambda path: path.rsplit("/", 1)[-1] + ":[1234]"), \
            mock.patch.object(probe, "read_bounded", side_effect=read), \
            mock.patch.object(probe, "_capture", side_effect=capture), \
            mock.patch.object(probe, "_observe_cgroup", side_effect=lambda path, mounts, gap: {
                "path": path, "filesystem_verified": True, "delegation_sufficient": False,
                "write_test_performed": False, "files": {"cgroup.controllers": ["cpu", "memory", "pids"],
                    "cgroup.subtree_control": ["cpu", "memory", "pids"]}}):
        yield args, calls


@unittest.skipUnless(sys.platform == "linux", "E3 host observation is Linux-only")
class E3ProbeObservationTests(unittest.TestCase):
    def assert_unaccepted(self, report):
        self.assertFalse(report["real_e3_accepted"])
        self.assertFalse(report["production_supported"])
        self.assertFalse(report["business_authorized"])
        self.assertEqual(report["unverified_blockers"], ["REAL_HARNESS_MISSING",
            "QUOTA_PERMISSION_MODEL_UNVERIFIED", "E3_SUPERVISION_UNVERIFIED"])

    def test_basic_observations_never_grant_e3_and_only_fixed_readonly_commands_have_clean_environment(self):
        with observed_host() as (args, calls), mock.patch.dict(os.environ, {
                "DBUS_SESSION_BUS_ADDRESS": "tcp:host=remote-secret", "SYSTEMD_PAGER": "arbitrary-command",
                "LD_PRELOAD": "/private/injection.so", "TOKEN": "credential-secret"}):
            report = probe.probe(args)
        self.assertEqual(report["readiness"], "OBSERVED_NOT_ACCEPTED")
        self.assertEqual(report["gaps"], [])
        self.assert_unaccepted(report)
        commands = [argv for argv, env, bounds in calls]
        self.assertEqual(commands[:2], [["/usr/bin/systemctl", "--version"], ["/usr/bin/systemd-run", "--version"]])
        self.assertEqual(len(commands), 4)
        for argv in commands[2:]:
            self.assertEqual(argv[:3], ["/usr/bin/systemctl", "--user", "show"])
            self.assertTrue(argv[-1].startswith("--property="))
        self.assertEqual(commands[3][3], "fixture.slice")
        self.assertNotIn("Delegate", commands[3][-1], "a slice cannot have service/scope delegation semantics")
        self.assertNotIn("Delegate", report["observations"]["systemd"]["slice"]["properties"])
        for argv, env, bounds in calls:
            self.assertEqual(env, {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C", "XDG_RUNTIME_DIR": "/run/user/1001"})
        serialized = json.dumps(report)
        for secret in ("credential-secret", "mount-secret", "private-source", "private-server", "private-user", "private-version-detail"):
            self.assertNotIn(secret, serialized)
        target = report["observations"]["mounts"][0]
        self.assertFalse(target["existence_verified"])
        self.assertFalse(target["writability_verified"])
        self.assertFalse(target["hard_quota_verified"])

    def test_root_identity_pid1_and_missing_private_inputs_have_explicit_nonpass_status(self):
        cases = [({"uid": 0}, "BLOCKED", "DEDICATED_NONROOT_ACCOUNT_REQUIRED"),
                 ({"uid": 1002}, "BLOCKED", "EXPECTED_UID_DIFFERS"),
                 ({"pid1": b"private-init-name\n"}, "BLOCKED", "PID1_NOT_SYSTEMD"),
                 ({"argv": []}, "INCOMPLETE", "EXPECTED_UID_REQUIRED")]
        for options, readiness, code in cases:
            with self.subTest(code=code), observed_host(**options) as (args, calls):
                report = probe.probe(args)
            self.assertEqual(report["readiness"], readiness)
            codes = {gap["code"] for gap in report["gaps"]}
            self.assertIn(code, codes)
            if options.get("argv") == []:
                self.assertIn("PRIVATE_CGROUP_AND_SLICE_REQUIRED", codes)
            self.assertNotIn("private-init-name", json.dumps(report))
            self.assert_unaccepted(report)

    def test_unknown_permission_truncated_and_unparseable_observations_are_incomplete_without_secrets(self):
        cases = ({"read_error": PermissionError(13, "private read denial")},
                 {"mountinfo": MOUNTINFO.rsplit(b" - ", 1)[0] + b" - cifs\n"}, {"mountinfo": b"\xff"},
                 {"mountinfo": b"x" * (probe.MAX_FILE_BYTES + 1)})
        for options in cases:
            with self.subTest(options=list(options)), observed_host(**options) as (args, calls):
                report = probe.probe(args)
            self.assertEqual(report["readiness"], "INCOMPLETE")
            self.assertTrue(report["gaps"])
            self.assertNotIn("private read denial", json.dumps(report))
            self.assert_unaccepted(report)

    def test_command_failures_and_cleanup_unknown_never_become_observed_ready(self):
        for status, cleanup, stdout in (("LAUNCH_FAILED", "CONFIRMED", b""),
                ("TIMEOUT", "CONFIRMED", b"systemd 257"), ("OUTPUT_LIMIT", "CONFIRMED", b"systemd 257"),
                ("COMPLETED", "CONFIRMED", b"unknown private-tool-detail"),
                ("UNRESOLVED", "UNRESOLVED", b"systemd 257")):
            def capture(argv, env, **bounds):
                return {"status": status, "cleanup": cleanup, "exit_code": 0, "stdout": stdout}
            with self.subTest(status=status, cleanup=cleanup), observed_host(command=capture) as (args, calls):
                report = probe.probe(args)
            self.assertEqual(report["readiness"], "INCOMPLETE")
            if cleanup == "UNRESOLVED":
                self.assertEqual(len(calls), 1, "unresolved collector must block further command launches")
                self.assertIn("COMMAND_CLEANUP_UNRESOLVED", [gap["code"] for gap in report["gaps"]])
            self.assertNotIn("private-tool-detail", json.dumps(report))
            self.assert_unaccepted(report)

    def test_mount_matching_is_lexical_longest_component_and_never_touches_targets(self):
        mounts = probe.parse_mountinfo(MOUNTINFO)
        with mock.patch.object(os, "stat", side_effect=AssertionError("target stat")), \
                mock.patch.object(os, "open", side_effect=AssertionError("target open")), \
                mock.patch.object(os, "access", side_effect=AssertionError("target access")), \
                mock.patch.object(Path, "resolve", side_effect=AssertionError("target resolve")):
            self.assertEqual(probe.match_mount("/mnt/archive/does-not-exist", mounts), mounts[2])
            self.assertEqual(probe.match_mount("/mnt/archive-other/file", mounts), mounts[0])
            self.assertEqual(probe.match_mount("/sys/fs/cgroup/fixture.slice", mounts), mounts[1])
        for key in ("source", "options", "super_options"):
            self.assertFalse(any(key in mount for mount in mounts))
        with self.assertRaisesRegex(probe.ProbeError, "AMBIGUOUS_OVERMOUNT"):
            probe.match_mount("/mnt/archive", mounts + [dict(mounts[2], mount_id=4)])

    def test_nsfs_namespace_roots_preserve_other_mounts_and_are_never_opened(self):
        namespace_types = ("net", "mnt", "uts", "ipc", "pid", "user", "cgroup", "time")
        rows = [f"{index + 10} 1 0:4 {name}:[{1000 + index}] /run/ns-fixture/{name} rw shared:4 - nsfs private-ns-source rw,password=ns-secret\n"
                for index, name in enumerate(namespace_types)]
        with mock.patch.object(os, "open", side_effect=AssertionError("namespace target open")), \
                mock.patch.object(os, "stat", side_effect=AssertionError("namespace target stat")), \
                mock.patch.object(Path, "resolve", side_effect=AssertionError("namespace target resolve")):
            mounts = probe.parse_mountinfo(MOUNTINFO + "".join(rows).encode())
            self.assertEqual(len(mounts), 3 + len(namespace_types))
            for index, name in enumerate(namespace_types):
                item = probe.match_mount("/run/ns-fixture/" + name, mounts)
                self.assertEqual(item["root"], f"{name}:[{1000 + index}]")
                self.assertEqual(item["type"], "nsfs")
            self.assertEqual(probe.match_mount("/mnt/archive/job", mounts)["type"], "cifs")
            self.assertEqual(probe.match_mount("/sys/fs/cgroup/fixture.slice", mounts)["type"], "cgroup2")
        self.assertEqual(mounts[:3], probe.parse_mountinfo(MOUNTINFO))
        for secret in ("private-ns-source", "ns-secret", "mount-secret"):
            self.assertNotIn(secret, json.dumps(mounts))

    def test_namespace_root_exception_keeps_filesystem_and_path_validation_strict(self):
        cases = [(kind, "net:[1000]", "/run/ns-fixture") for kind in ("ext4", "xfs", "cgroup2", "cifs", "nfs")]
        cases += [("nsfs", root, "/run/ns-fixture") for root in (
            "relative", "../net:[1000]", "net:[-1]", "net:[+1]", "net:[0]", "net:[01]",
            "net:[]", "net:[abc]", "net:[1000]suffix", "net:[1000]/child", "Net:[1000]",
            "net:[18446744073709551616]", "x" * 33 + ":[1000]", r"net:\134[1000]",
        )]
        cases += [("nsfs", "net:[1000]", point) for point in ("relative", "//run/ns-fixture", "/run/../ns-fixture")]
        for kind, root, point in cases:
            raw = f"10 1 0:4 {root} {point} rw - {kind} ignored rw\n".encode()
            with self.subTest(kind=kind, root=root, point=point), self.assertRaisesRegex(probe.ProbeError, "MOUNTINFO_FORMAT"):
                probe.parse_mountinfo(MOUNTINFO + raw)
        absolute = b"10 1 0:4 / /run/ns-fixture rw - nsfs ignored rw\n"
        self.assertEqual(probe.parse_mountinfo(absolute)[0]["root"], "/")
        escaped = b"10 1 0:4 net:[18446744073709551615] /run/ns\\040fixture rw - nsfs ignored rw\n"
        self.assertEqual(probe.parse_mountinfo(escaped)[0]["mount_point"], "/run/ns fixture")

    def test_nsfs_overmount_cannot_be_discarded_or_treated_as_delegated_cgroup(self):
        target = "/sys/fs/cgroup/fixture.slice"
        for point, expected in ((target, "CGROUP_NOT_CGROUP2"), ("/sys/fs/cgroup", "AMBIGUOUS_OVERMOUNT")):
            mounts = probe.parse_mountinfo(MOUNTINFO + f"10 2 0:4 cgroup:[1000] {point} rw - nsfs ignored rw\n".encode())
            gaps = []
            with self.subTest(point=point), mock.patch.object(os, "open", side_effect=AssertionError("namespace overmount opened")):
                result = probe._observe_cgroup(target, mounts, lambda code, *args, **kwargs: gaps.append(code))
            self.assertIn(expected, gaps)
            self.assertFalse(result["filesystem_verified"])
            self.assertFalse(result["delegation_sufficient"])
            self.assertEqual(result["files"], {})

    def test_valid_nsfs_records_do_not_erase_missing_private_inputs_or_grant_e3(self):
        namespaces = b"10 1 0:4 net:[1000] /run/ns-fixture rw - nsfs ignored rw\n"
        with observed_host(argv=["--label", "candidate", "--mount-target", "/mnt/archive/job"],
                           mountinfo=MOUNTINFO + namespaces) as (args, calls):
            report = probe.probe(args)
        self.assertEqual(report["readiness"], "INCOMPLETE")
        codes = {gap["code"] for gap in report["gaps"]}
        self.assertNotIn("MOUNTINFO_FORMAT", codes)
        self.assertIn("EXPECTED_UID_REQUIRED", codes)
        self.assertIn("PRIVATE_CGROUP_AND_SLICE_REQUIRED", codes)
        self.assertEqual(report["observations"]["mounts"][0]["match"]["type"], "cifs")
        self.assertTrue(report["observations"]["cgroups"]["root"]["filesystem_verified"])
        self.assert_unaccepted(report)

    def test_bounded_file_reads_reject_overflow_symlinks_and_special_files_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / "regular"
            regular.write_bytes(b"x" * 1025)
            with self.assertRaisesRegex(probe.ProbeError, "BYTE_LIMIT"):
                probe.read_bounded(regular, 1024)
            self.assertEqual(probe.read_bounded(regular, 1025), b"x" * 1025)
            (root / "alias").symlink_to(regular)
            (root / "parent-alias").symlink_to(root, target_is_directory=True)
            for target in (root / "alias", root / "parent-alias" / "regular"):
                with self.subTest(target=target), self.assertRaises(OSError):
                    probe.read_bounded(target, 2048)
            os.mkfifo(root / "fifo")
            before = time.monotonic()
            with self.assertRaisesRegex(probe.ProbeError, "NOT_REGULAR"):
                probe.read_bounded(root / "fifo", 1024)
            self.assertLess(time.monotonic() - before, .5)

    def test_cgroup_controller_mount_and_fd_binding_failures_remain_explicit(self):
        for case in ("missing", "disabled", "readonly", "wrong-filesystem", "changed-binding", "unknown-controller"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                values = {"cgroup.controllers": "cpu memory pids", "cgroup.subtree_control": "cpu memory pids",
                          "cgroup.type": "domain", "cgroup.events": "populated 0\nfrozen 0",
                          "cgroup.max.depth": "max", "cgroup.max.descendants": "max", "cpu.max": "max 100000",
                          "memory.max": "max", "pids.max": "max"}
                if case == "missing": values["cgroup.controllers"] = "cpu memory"
                if case == "disabled": values["cgroup.subtree_control"] = "cpu memory"
                if case == "unknown-controller": values["cgroup.controllers"] += " future-private-controller"
                for name, value in values.items(): (root / name).write_text(value + "\n")
                mount = {"mount_id": 42, "mount_point": directory, "type": "ext4" if case == "wrong-filesystem" else "cgroup2",
                         "read_only": case == "readonly"}
                gaps = []
                def gap(code, component, severity="INCOMPLETE", **details):
                    gaps.append((code, severity))
                with mock.patch.object(probe, "_fd_mount_id", return_value=43 if case == "changed-binding" else 42):
                    result = probe._observe_cgroup(directory, [mount], gap)
                expected = {"missing": ("REQUIRED_CONTROLLERS_UNAVAILABLE", "BLOCKED"),
                    "disabled": ("REQUIRED_CONTROLLERS_NOT_ENABLED", "BLOCKED"),
                    "readonly": ("CGROUP_MOUNT_READ_ONLY", "BLOCKED"),
                    "wrong-filesystem": ("CGROUP_NOT_CGROUP2", "BLOCKED"),
                    "changed-binding": ("CGROUP_MOUNT_BINDING_CHANGED", "INCOMPLETE"),
                    "unknown-controller": ("CONTROLLER_FORMAT_OR_VERSION", "INCOMPLETE")}[case]
                self.assertIn(expected, gaps)
                self.assertFalse(result["delegation_sufficient"])
                self.assertFalse(result["write_test_performed"])

    def test_root_cgroup_omits_nonroot_only_files_without_false_missing_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in {"cgroup.controllers": "cpu memory pids", "cgroup.subtree_control": "cpu memory pids",
                    "cgroup.max.depth": "max", "cgroup.max.descendants": "max"}.items():
                (root / name).write_text(value + "\n")
            actual_directory_fd = probe._directory_fd
            gaps = []
            mount = {"mount_id": 42, "mount_point": "/sys/fs/cgroup", "type": "cgroup2", "read_only": False}
            with mock.patch.object(probe, "_directory_fd", side_effect=lambda path: actual_directory_fd(directory)), \
                    mock.patch.object(probe, "_fd_mount_id", return_value=42):
                result = probe._observe_cgroup("/sys/fs/cgroup", [mount], lambda *args, **kwargs: gaps.append((args, kwargs)))
            self.assertEqual(gaps, [])
            self.assertEqual(set(result["files"]), {"cgroup.controllers", "cgroup.subtree_control",
                                                  "cgroup.max.depth", "cgroup.max.descendants"})
            self.assertFalse(result["delegation_sufficient"])
            self.assertFalse(result["write_test_performed"])

    def test_parent_close_failure_still_closes_new_directory_fd_without_double_close(self):
        closed = []
        def close(descriptor):
            closed.append(descriptor)
            if descriptor == 100:
                raise OSError("old parent close failed")
        with mock.patch.object(probe.os, "open", side_effect=[100, 101]), \
                mock.patch.object(probe.os, "close", side_effect=close):
            with self.assertRaisesRegex(OSError, "old parent close failed"):
                probe._directory_fd("/synthetic")
        self.assertEqual(closed, [100, 101])
