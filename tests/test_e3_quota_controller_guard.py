"""LOGIC_ONLY host/manager facts plus LOCAL_PIPE descriptor checks.

No systemd command, quota syscall, cgroup write, service, account, mount or
host preparation runs here. Successful admission is tested with explicit host
doubles, never classified as a real Q1 fixture or E3 acceptance.
"""
from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from admin.local_hand_quota_observer import admission as a, controller_guard as g
from test_e3_quota_monitor import decode, fixture, NOW
from test_e3_quota_worker import runtime


def controller_value():
    return {"schema": g.SCHEMA, "unit": "lhqcontrollerfixture.service", "invocation_id": "c" * 32,
            "cgroup": "/system.slice/lhqcontrollerfixture.service", "cgroup_device": 22, "cgroup_inode": 45,
            "runtime_max_usec": 90_000_000, "timeout_stop_usec": 1_000_000,
            "memory_bytes": 64 * 1024**2, "tasks_max": 16, "cpu_quota_per_sec_usec": 1_000_000,
            "limit_cpu_seconds": 30}


def manifest():
    value = fixture()
    value["cgroup_parent"] = "/" + runtime().query_slice
    return decode(value)


def properties(spec=None):
    spec = spec or g.decode_controller(controller_value())
    values = dict.fromkeys(g.SHOW_FIELDS, "")
    values.update(Id=spec.unit, LoadState="loaded", ActiveState="active", SubState="running",
                  InvocationID=spec.invocation_id, ControlGroup=spec.cgroup, MainPID="4242", ControlPID="0",
                  Slice="system.slice", Type="exec", ExitType="cgroup", RemainAfterExit="no", Restart="no",
                  KillMode="control-group", SendSIGKILL="yes", FinalKillSignal="9", NotifyAccess="none",
                  RuntimeMaxUSec="1min 30s", RuntimeRandomizedExtraUSec="0", TimeoutStopUSec="1s",
                  TimeoutStopFailureMode="kill", MemoryMax=str(spec.memory_bytes), MemorySwapMax="0",
                  TasksMax=str(spec.tasks_max), CPUQuotaPerSecUSec="1s", LimitCPU="30", LimitCPUSoft="30")
    return values


class DecodeTests(unittest.TestCase):
    def test_pure_spec_and_precise_microsecond_bounds(self):
        with patch.object(g, "_fixed_read", side_effect=AssertionError("host I/O")), \
                patch.object(g, "verify_file", side_effect=AssertionError("host I/O")):
            spec = g.decode_controller(controller_value())
        self.assertEqual(spec.runtime_max_usec, 90_000_000)
        self.assertEqual(spec.timeout_stop_usec, 1_000_000)
        self.assertEqual(spec.cpu_quota_per_sec_usec, 1_000_000)
        with self.assertRaises(AttributeError):
            spec.tasks_max = 128

    def test_missing_extra_and_prepared_booleans_rejected(self):
        for key in g.SPEC_FIELDS:
            value = controller_value()
            del value[key]
            with self.subTest(key=key), self.assertRaises(a.Rejected):
                g.decode_controller(value)
        for key in ("prepared", "supervised", "output_bounded"):
            with self.subTest(key=key), self.assertRaisesRegex(a.Rejected, "FIELDS"):
                g.decode_controller({**controller_value(), key: True})

    def test_invalid_or_unbounded_identity_and_limit_fields_rejected(self):
        changes = {"unit": ["--help", "bad@name.service", "x" * 129], "invocation_id": ["0" * 31, True],
                   "cgroup": ["/system.slice/other.service", "/", "/tree/../fixture.service"],
                   "cgroup_device": [-1, True], "cgroup_inode": [0, True],
                   "runtime_max_usec": [0, True, 120_000_001], "timeout_stop_usec": [0, 5_000_001],
                   "memory_bytes": [0, True, 1024**3 + 1], "tasks_max": [0, True, 65],
                   "cpu_quota_per_sec_usec": [0, True, 1_000_001], "limit_cpu_seconds": [0, True, 121]}
        for key, values in changes.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(a.Rejected):
                    g.decode_controller({**controller_value(), key: value})

    def test_systemctl_timespans_use_exact_integer_microseconds(self):
        for value, expected in (("0", 0), ("1s", 1_000_000), ("1min 30s", 90_000_000),
                                ("1.000001s", 1_000_001), ("1.001ms", 1001), ("999us", 999),
                                ("2min", 120_000_000), ("1min 1.000001s", 61_000_001)):
            with self.subTest(value=value):
                self.assertEqual(g._timespan_usec(value), expected)
        for value in ("", "infinity", "1000000", "1e6us", "1.0000001s", "0.1us", "1s 1s", "1s 1min",
                      "3min", "-1s", " 1s", "1s ", "nan", True):
            with self.subTest(value=value), self.assertRaises(a.Rejected):
                g._timespan_usec(value)

    def test_manager_exact_original_pid_invocation_and_constraints(self):
        spec = g.decode_controller(controller_value())
        g._check_manager(properties(), spec, 4242)
        changes = {"MainPID": "4243", "InvocationID": "d" * 32, "Id": "other.service", "Restart": "always",
                   "RestartForceExitStatus": "1", "Type": "oneshot", "ExitType": "main", "NotifyAccess": "all",
                   "RemainAfterExit": "yes", "ActiveState": "inactive", "SubState": "exited",
                   "Job": "1", "ControlPID": "1", "KillMode": "process", "SendSIGKILL": "no",
                   "FinalKillSignal": "15", "ExecStop": "a hook", "ExecStartPost": "a hook",
                   "OnFailure": "other.service", "OnSuccess": "other.service", "TriggeredBy": "test.timer",
                   "MemorySwapMax": "infinity", "RuntimeMaxUSec": "infinity", "RuntimeRandomizedExtraUSec": "1s",
                   "TimeoutStopFailureMode": "abort", "TimeoutStopUSec": "2s", "MemoryMax": "infinity",
                   "TasksMax": "infinity", "CPUQuotaPerSecUSec": "infinity", "LimitCPU": "infinity",
                   "LimitCPUSoft": "31"}
        for key, value in changes.items():
            with self.subTest(key=key), self.assertRaises(a.Rejected):
                g._check_manager({**properties(), key: value}, spec, 4242)


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux real pipe descriptor inspection")
class PipeTests(unittest.TestCase):
    def test_actual_anonymous_write_end_observed_and_read_end_rejected(self):
        reader, writer = os.pipe()
        try:
            info = os.fstat(writer)
            self.assertEqual(g._pipe_identity(writer), (info.st_dev, info.st_ino))
            with self.assertRaisesRegex(a.Rejected, "CONTROLLER_OUTPUT_PIPE_REQUIRED"):
                g._pipe_identity(reader)
        finally:
            os.close(reader)
            os.close(writer)

    def test_regular_file_descriptor_rejected(self):
        import tempfile
        with tempfile.TemporaryFile() as handle, self.assertRaisesRegex(a.Rejected, "CONTROLLER_OUTPUT_PIPE_REQUIRED"):
            g._pipe_identity(handle.fileno())


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux host and manager LOGIC_ONLY")
class HostTests(unittest.TestCase):
    def setUp(self):
        import resource

        self.config, self.manifest, self.spec = runtime(), manifest(), g.decode_controller(controller_value())
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(g.os, "getuid", return_value=0))
        self.stack.enter_context(patch.object(g.os, "geteuid", return_value=0))
        self.stack.enter_context(patch.object(g.os, "getpid", return_value=4242))
        self.cpu = self.stack.enter_context(patch.object(resource, "getrlimit", return_value=(30, 30)))
        ns = SimpleNamespace(st_dev=self.config.initial_userns_device, st_ino=self.config.initial_userns_inode)
        self.stat = self.stack.enter_context(patch.object(g.os, "stat", return_value=ns))
        self.read = self.stack.enter_context(patch.object(g, "_fixed_read", side_effect=lambda filename, maximum:
                b"systemd\n" if filename == "/proc/1/comm" else b"Name:\ttest\nPid:\t4242\nUid:\t0 0 0 0\n"))
        self.boot = self.stack.enter_context(patch.object(g, "_boot_id", return_value=self.manifest.boot_id))
        self.own = self.stack.enter_context(patch.object(g, "_own_cgroup", return_value=self.spec.cgroup))
        self.pipe = self.stack.enter_context(patch.object(g, "_pipe_identity", side_effect=lambda fd: (1, fd)))

    def test_actual_read_adapter_checks_bound_process_and_pipe_facts(self):
        import resource

        self.assertEqual(g._host_identity(self.config, self.manifest, self.spec), (4242, (1, 1), (1, 2)))
        self.cpu.assert_called_once_with(resource.RLIMIT_CPU)
        self.assertEqual({call.args[0] for call in self.read.call_args_list}, {"/proc/1/comm", "/proc/self/status"})
        self.assertEqual({call.args[0] for call in self.stat.call_args_list}, {"/proc/1/ns/user", "/proc/self/ns/user"})

    def test_wrong_boot_namespace_and_cgroup_rejected(self):
        for target, value in ((self.boot, "bad-boot"), (self.own, "/system.slice/other.service"),
                              (self.stat, SimpleNamespace(st_dev=99, st_ino=88))):
            original = target.return_value
            target.return_value = value
            with self.subTest(value=value), self.assertRaises(a.Rejected):
                g._host_identity(self.config, self.manifest, self.spec)
            target.return_value = original

    def test_query_tree_ancestor_and_descendant_rejected(self):
        for parent in ("/system.slice", self.spec.cgroup, self.spec.cgroup + "/child"):
            with self.subTest(parent=parent), self.assertRaisesRegex(a.Rejected, "CONTROLLER_IN_QUERY_TREE"):
                g._host_identity(self.config, replace(self.manifest, cgroup_parent=parent), self.spec)

    def test_all_proc_uid_values_and_main_pid_must_match(self):
        for raw in (b"Pid: 4242\nUid: 0 0 1 0\n", b"Pid: 4243\nUid: 0 0 0 0\n",
                    b"Pid: 4242\nUid: 0 0 0 0\nUid: 0 0 0 0\n"):
            self.read.side_effect = lambda filename, maximum: b"systemd\n" if filename == "/proc/1/comm" else raw
            with self.subTest(raw=raw), self.assertRaisesRegex(a.Rejected, "CONTROLLER_PROCESS_IDENTITY"):
                g._host_identity(self.config, self.manifest, self.spec)

    def test_merged_standard_stream_pipe_rejected(self):
        self.pipe.side_effect = None
        self.pipe.return_value = (1, 2)
        with self.assertRaisesRegex(a.Rejected, "CONTROLLER_OUTPUT_PIPE_ALIAS"):
            g._host_identity(self.config, self.manifest, self.spec)

    def test_current_cpu_rlimit_must_match_both_finite_manager_limits(self):
        for actual in ((-1, -1), (29, 30), (30, 31)):
            self.cpu.return_value = actual
            with self.subTest(actual=actual), self.assertRaisesRegex(a.Rejected, "CONTROLLER_CPU_LIMIT_CHANGED"):
                g._host_identity(self.config, self.manifest, self.spec)


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux cgroup observation LOGIC_ONLY")
class CgroupTests(unittest.TestCase):
    def scenario(self):
        self.spec = g.decode_controller(controller_value())
        self.data = {"memory.max": str(self.spec.memory_bytes), "memory.swap.max": "0", "pids.max": "16",
                     "cpu.max": "100000 100000"}
        self.opened = {}
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(g, "open_protected", side_effect=[42, 43]))
        self.stat = stack.enter_context(patch.object(g.os, "fstat", side_effect=lambda fd:
                SimpleNamespace(st_dev=22, st_ino=45, st_mode=stat.S_IFDIR | 0o755) if fd in (42, 43)
                else SimpleNamespace(st_mode=stat.S_IFREG | 0o644)))
        def open_file(name, flags, *, dir_fd):
            self.assertEqual(dir_fd, 42)
            fd = 50 + len(self.opened)
            self.opened[fd] = name
            return fd
        stack.enter_context(patch.object(g.os, "open", side_effect=open_file))
        stack.enter_context(patch.object(g.os, "close"))
        self.read = stack.enter_context(patch.object(g, "_fixed_read", side_effect=lambda name, maximum:
                b"mnt_id:\t18\n" if "fdinfo" in name else b"18 0 0:22 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n"))
        stack.enter_context(patch.object(g, "read_fd", side_effect=lambda fd, maximum:
                (self.data[self.opened[fd]] + "\n").encode()))

    def test_kernel_limit_files_match_exact_memory_tasks_and_cpu_ratio(self):
        self.scenario()
        g._cgroup_identity(self.spec)
        self.assertEqual(set(self.opened.values()), {"memory.max", "memory.swap.max", "pids.max", "cpu.max"})

    def test_kernel_unbounded_limits_and_different_ratio_rejected(self):
        for name, value in (("memory.max", "max"), ("memory.swap.max", "max"), ("pids.max", "max"),
                            ("cpu.max", "max 100000"), ("cpu.max", "100001 100000")):
            with self.subTest(name=name, value=value):
                self.scenario()
                self.data[name] = value
                with self.assertRaises(a.Rejected):
                    g._cgroup_identity(self.spec)

    def test_cgroup_mount_namespace_or_filesystem_substitution_rejected(self):
        self.scenario()
        self.read.side_effect = lambda name, maximum: (b"mnt_id:\t18\n" if "fdinfo" in name else
                b"18 0 0:22 /different /sys/fs/cgroup rw - cgroup2 cgroup rw\n")
        with self.assertRaisesRegex(a.Rejected, "CONTROLLER_CGROUP_MOUNT"):
            g._cgroup_identity(self.spec)


class FakeCapture:
    def __init__(self, output, *, done=True, error=None, returncode=0, stderr=b""):
        self.stdout, self.stderr = bytearray(output), bytearray(stderr)
        self.done, self.settled, self.error = done, done, error
        self.process = SimpleNamespace(returncode=returncode)
        self.calls, self.kills, self.closed = [], 0, 0

    def start(self, argv):
        self.calls.append(argv)

    def pump(self):
        pass

    def kill_client(self):
        self.kills += 1

    def close_pipes(self):
        self.closed += 1


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux controller admission LOGIC_ONLY")
class ManagerTests(unittest.TestCase):
    def scenario(self, *, output=None, **changes):
        raw = ("\n".join(key + "=" + value for key, value in properties().items()) + "\n").encode()
        capture = FakeCapture(raw if output is None else output, **changes)
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.verify = stack.enter_context(patch.object(g, "verify_file", return_value=77))
        self.make = stack.enter_context(patch.object(g, "Capture", return_value=capture))
        self.close = stack.enter_context(patch.object(g.os, "close"))
        self.clock = stack.enter_context(patch.object(g, "boottime_ns", side_effect=[NOW, NOW, NOW + 3_000_000_000]))
        stack.enter_context(patch.object(g.time, "sleep"))
        return capture

    def test_verified_executable_exact_fixed_show_and_one_shared_byte_limit(self):
        capture = self.scenario()
        spec, config = g.decode_controller(controller_value()), runtime()
        self.assertEqual(g._show_once(config, spec), properties())
        self.verify.assert_called_once_with(config.systemctl_path, config.systemctl_sha256, executable=True)
        self.make.assert_called_once_with(g.CONTROL_BYTES)
        self.assertEqual(capture.calls, [(config.systemctl_path, "--system", "--no-pager", "--no-ask-password",
                                         "show", spec.unit, "--all", "--property=" + ",".join(g.SHOW_FIELDS))])
        self.assertEqual(capture.kills, 0)
        self.close.assert_called_once_with(77)

    def test_manager_timeout_or_capture_failure_never_spawns_replacement(self):
        for changes in ({"done": False}, {"done": False, "error": "CAPTURE_BYTE_LIMIT"},
                        {"returncode": 1}, {"stderr": b"unexpected diagnostic"}):
            with self.subTest(changes=changes):
                capture = self.scenario(**changes)
                with self.assertRaises(a.Rejected):
                    g._show_once(runtime(), g.decode_controller(controller_value()))
                self.assertEqual(len(capture.calls), 1)
                self.make.assert_called_once()
                self.assertLessEqual(capture.kills, 1)

    def test_missing_duplicate_unknown_or_malformed_property_rejected(self):
        for output in (b"Id=one\nId=two\n", b"Id=one\n", b"bad\n", b"\xff\n"):
            with self.subTest(output=output):
                self.scenario(output=output)
                with self.assertRaises((a.Rejected, UnicodeError)):
                    g._show_once(runtime(), g.decode_controller(controller_value()))
                self.make.assert_called_once()

    def test_official_renderer_omits_only_empty_exec_arrays(self):
        raw = ("\n".join(key + "=" + value for key, value in properties().items()
                         if key not in g.EMPTY_EXEC_FIELDS) + "\n").encode()
        self.scenario(output=raw)
        self.assertEqual(g._show_once(runtime(), g.decode_controller(controller_value())), properties())

    def test_successful_show_still_rejects_capture_close_failure(self):
        capture = self.scenario()
        def bad_close():
            capture.error = "CAPTURE_CLOSE_UNCERTAIN"
        capture.close_pipes = bad_close
        with self.assertRaisesRegex(a.Rejected, "CONTROLLER_MANAGER_CAPTURE"):
            g._show_once(runtime(), g.decode_controller(controller_value()))

    def test_kill_or_cleanup_pump_error_still_attempts_pipe_close_and_preserves_timeout(self):
        for operation in ("kill_client", "pump"):
            with self.subTest(operation=operation):
                capture = self.scenario(done=False)
                # The first pump belongs to the observation loop; only fail
                # during timeout cleanup, without launching a real process.
                effect = OSError(5, "synthetic cleanup error")
                effects = [None, effect] if operation == "pump" else effect
                with patch.object(capture, operation, side_effect=effects), \
                        self.assertRaisesRegex(a.Rejected, "CONTROLLER_MANAGER_TIMEOUT"):
                    g._show_once(runtime(), g.decode_controller(controller_value()))
                self.assertEqual(capture.closed, 1)
                self.assertEqual(len(capture.calls), 1)
                self.close.assert_called_once_with(77)

    def test_digest_failure_stops_before_any_manager_start(self):
        self.scenario()
        self.verify.side_effect = a.Rejected("INSTALLATION_DIGEST")
        with self.assertRaisesRegex(a.Rejected, "INSTALLATION_DIGEST"):
            g._show_once(runtime(), g.decode_controller(controller_value()))
        self.make.assert_not_called()


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux admission sequencing LOGIC_ONLY")
class AdmissionTests(unittest.TestCase):
    def scenario(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.host = stack.enter_context(patch.object(g, "_host_identity", return_value=(4242, (1, 2), (1, 3))))
        self.cgroup = stack.enter_context(patch.object(g, "_cgroup_identity"))
        self.show = stack.enter_context(patch.object(g, "_show_once", return_value=properties()))
        stack.enter_context(patch.object(g, "boottime_ns", return_value=NOW))
        return runtime(), manifest(), g.decode_controller(controller_value())

    def test_only_reobserved_original_identities_become_finite_evidence(self):
        config, original_manifest, spec = self.scenario()
        observation = g.admit_controller(config, original_manifest, spec)
        self.assertEqual(observation.as_dict(), {
            "unit": spec.unit, "invocation_id": spec.invocation_id, "cgroup": spec.cgroup,
            "cgroup_device": 22, "cgroup_inode": 45, "boot_id": original_manifest.boot_id,
            "pid": 4242, "observed_ns": NOW, "stdout_pipe_device": 1, "stdout_pipe_inode": 2,
            "stderr_pipe_device": 1, "stderr_pipe_inode": 3})
        self.assertEqual(self.host.call_count, 2)
        self.assertEqual(self.cgroup.call_count, 2)
        self.show.assert_called_once()

    def test_invalid_dataclass_cannot_bypass_strict_decoding(self):
        config, original_manifest, spec = self.scenario()
        with self.assertRaises(a.Rejected):
            g.admit_controller(config, original_manifest, replace(spec, tasks_max=True))
        self.host.assert_not_called()
        self.show.assert_not_called()

    def test_bad_host_or_cgroup_precondition_stops_before_manager(self):
        for name in ("host", "cgroup"):
            with self.subTest(name=name):
                arguments = self.scenario()
                getattr(self, name).side_effect = OSError(5, "synthetic failure")
                with self.assertRaisesRegex(a.Rejected, "CONTROLLER_IO_UNCERTAIN"):
                    g.admit_controller(*arguments)
                self.show.assert_not_called()

    def test_identity_changes_after_show_rejected_without_second_manager(self):
        arguments = self.scenario()
        self.host.side_effect = [(4242, (1, 2), (1, 3)), (4242, (1, 2), (1, 4))]
        with self.assertRaisesRegex(a.Rejected, "CONTROLLER_IDENTITY_CHANGED"):
            g.admit_controller(*arguments)
        self.show.assert_called_once()


if __name__ == "__main__":
    unittest.main()
