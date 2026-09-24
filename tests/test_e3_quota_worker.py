"""Q1 worker source checks; no privileged setup, systemd start or quota call.

Mock process/namespace/exec observations are explicitly LOGIC_ONLY. Temporary
file tests exercise actual no-follow/read behavior with fixture-only ownership
checks overridden; they do not qualify a protected installation or live root.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import base64
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from admin.local_hand_quota_observer import admission as a, protected_inputs as p
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import worker as w
else:
    w = None  # Windows must be able to collect the explicit Linux-only skips.
from test_e3_quota_monitor import binding, decode, encoded, fixture, INVOCATION, NOW


def runtime_value():
    return {
        "schema": "local-hand-quota-runtime/v1", "manifest_path": "/synthetic/admin/manifest.json",
        "manifest_digest": "0" * 64, "python_path": "/synthetic/bin/python3",
        "python_sha256": "1" * 64, "worker_path": "/synthetic/admin/worker.py", "worker_sha256": "2" * 64,
        "native_path": "/synthetic/bin/quota-query", "native_sha256": "3" * 64,
        "systemd_run_path": "/synthetic/bin/systemd-run", "systemd_run_sha256": "4" * 64,
        "systemctl_path": "/synthetic/bin/systemctl", "systemctl_sha256": "5" * 64,
        "package_files": {name: "6" * 64 for name in p.PACKAGE_FILES}, "query_slice": "lhqfixture.slice",
        "cgroup_parent_device": 25, "cgroup_parent_inode": 26,
        "initial_userns_device": 27, "initial_userns_inode": 28,
        "memory_bytes": 64 * 1024**2, "tasks_max": 4, "cpu_seconds": 2, "max_output_bytes": 8192}


def runtime(value=None):
    raw = encoded(runtime_value() if value is None else value)
    return p.decode_runtime(raw, hashlib.sha256(raw).hexdigest())


def status(**changes):
    values = dict(CapInh=0, CapPrm=w.CAPABILITIES, CapEff=w.CAPABILITIES,
                  CapBnd=w.CAPABILITIES, CapAmb=0, NoNewPrivs=1)
    values.update(changes)
    return ("\n".join(f"{key}:\t{value if key == 'NoNewPrivs' else format(value, '016x')}"
                     for key, value in values.items()) + "\n").encode()


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux process and FD worker")
class ProtectedInputsTests(unittest.TestCase):
    def test_runtime_schema_is_strict_immutable_and_independently_binds_installation(self):
        config = runtime()
        with self.assertRaises(FrozenInstanceError):
            config.tasks_max = 2
        digest = p.installation_digest(config)
        self.assertEqual(digest, p.installation_digest(replace(config, digest="a" * 64, manifest_digest="b" * 64)))
        self.assertNotEqual(digest, p.installation_digest(replace(config, native_sha256="c" * 64)))
        self.assertNotEqual(digest, p.installation_digest(replace(config, python_path="/other/python")))
        value = runtime_value()
        raw = encoded(value)
        with self.assertRaisesRegex(a.Rejected, "RUNTIME_DIGEST"):
            p.decode_runtime(raw + b" ", hashlib.sha256(raw).hexdigest())

    def test_runtime_rejects_command_paths_unknown_modules_and_unbounded_limits(self):
        cases = (("query_slice", "lhq-nested.slice"), ("query_slice", "app.slice"),
                 ("tasks_max", True), ("tasks_max", 9), ("memory_bytes", 0),
                 ("cpu_seconds", 31), ("max_output_bytes", 32769),
                 ("worker_path", "/synthetic/admin/other.py"), ("python_path", "/a/../python"),
                 ("initial_userns_inode", 0), ("package_files", {}))
        for key, value in cases:
            document = runtime_value()
            document[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(a.Rejected):
                runtime(document)
        value = runtime_value()
        value["command"] = "/bin/sh"
        with self.assertRaises(a.Rejected):
            runtime(value)

    def test_logical_ticket_roundtrip_rejects_injected_objects_and_extended_deadline(self):
        bound = binding()
        self.assertEqual(p.decode_ticket(p.encode_ticket(bound), bound.manifest), bound)
        value = json.loads(base64.b64decode(p.encode_ticket(bound)))
        for key, replacement in (("path", "/etc"), ("project_id", 73), ("deadline_ns", bound.deadline_ns + 1),
                                 ("issued_ns", True), ("schema", "unknown"), ("generation", "9" * 32)):
            changed = dict(value)
            changed[key] = replacement
            raw = base64.b64encode(encoded(changed)).decode()
            with self.subTest(key=key), self.assertRaises(a.Rejected):
                p.decode_ticket(raw, bound.manifest)
        with self.assertRaises(a.Rejected):
            p.decode_ticket(p.encode_ticket(bound) + "\n", bound.manifest)
        duplicate = b'{"schema":1,"schema":1}'
        with self.assertRaisesRegex(a.Rejected, "DUPLICATE_KEY"):
            p.decode_ticket(base64.b64encode(duplicate).decode(), bound.manifest)

    def test_protection_rejects_writable_ancestors_nonroot_files_and_setid(self):
        for mode, uid, nlink in ((stat.S_IFREG | 0o666, 0, 1), (stat.S_IFREG | 0o644, 1001, 1),
                                 (stat.S_IFREG | 0o4644, 0, 1), (stat.S_IFREG | 0o644, 0, 2),
                                 (stat.S_IFIFO | 0o600, 0, 1)):
            with self.subTest(mode=mode, uid=uid, nlink=nlink), self.assertRaises(a.Rejected):
                p._protected(SimpleNamespace(st_mode=mode, st_uid=uid, st_nlink=nlink), directory=False)
        with self.assertRaises(a.Rejected):
            p._protected(SimpleNamespace(st_mode=stat.S_IFDIR | 0o1777, st_uid=0), directory=True)

    def test_real_nofollow_and_bounded_reads_with_logic_only_ownership(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(p, "_protected"):
            base = Path(directory)
            target = base / "manifest.json"
            target.write_bytes(b"content")
            self.assertEqual(p.read_protected(str(target)), b"content")
            with self.assertRaisesRegex(a.Rejected, "INPUT_BYTE_LIMIT"):
                p.read_protected(str(target), 6)
            link = base / "linked.json"
            link.symlink_to(target)
            with self.assertRaises(OSError):
                p.read_protected(str(link))
            nested = base / "nested"
            nested.mkdir()
            (base / "alias").symlink_to(nested, target_is_directory=True)
            (nested / "file").write_bytes(b"x")
            with self.assertRaises(OSError):
                p.read_protected(str(base / "alias" / "file"))

    def test_real_verified_exec_fd_does_not_accept_scripts_or_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(p, "_protected"):
            target = Path(directory) / "file"
            for data in (b"#!/bin/sh\n", b"\x7fELFfixture-only"):
                target.write_bytes(data)
                target.chmod(0o755)
                digest = hashlib.sha256(data).hexdigest()
                with self.assertRaisesRegex(a.Rejected, "INSTALLATION_DIGEST"):
                    p.verify_file(str(target), "0" * 64, executable=True)
                if data.startswith(b"#!"):
                    with self.assertRaisesRegex(a.Rejected, "EXECUTABLE_FORMAT"):
                        p.verify_file(str(target), digest, executable=True)
                else:
                    fd = p.verify_file(str(target), digest, executable=True)
                    try:
                        self.assertFalse(os.get_inheritable(fd))
                        self.assertEqual(os.fstat(fd).st_ino, target.stat().st_ino)
                    finally:
                        os.close(fd)

    def test_close_failure_is_not_retried(self):
        metadata = SimpleNamespace(st_size=1, st_dev=1, st_ino=2, st_uid=0, st_gid=0, st_mode=0o100644,
                                   st_nlink=1, st_mtime_ns=1, st_ctime_ns=1)
        with patch.object(p, "open_protected", return_value=51), patch.object(os, "fstat", return_value=metadata), \
                patch.object(p, "read_fd", return_value=b"x"), patch.object(os, "close", side_effect=OSError(5, "IO")) as close:
            with self.assertRaises(OSError):
                p.verify_file("/synthetic/file", hashlib.sha256(b"x").hexdigest())
            self.assertEqual(close.call_args_list, [unittest.mock.call(51)])

    def test_executable_file_capability_presence_or_unreadability_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(p, "_protected"):
            target = Path(directory) / "native"
            data = b"\x7fELFfixture-only"
            target.write_bytes(data)
            target.chmod(0o755)
            digest = hashlib.sha256(data).hexdigest()
            for value in (b"", b"filecaps", OSError(errno.EPERM, "permission"), OSError(errno.EOPNOTSUPP, "unsupported")):
                with self.subTest(value=value), patch.object(os, "getxattr") as xattr:
                    if isinstance(value, OSError):
                        xattr.side_effect = value
                    else:
                        xattr.return_value = value
                    with self.assertRaisesRegex(a.Rejected, "FILE_CAPABILITY"):
                        p.verify_file(str(target), digest, executable=True)


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux process and FD worker")
class WorkerTests(unittest.TestCase):
    def test_logic_only_capabilities_require_exact_set_and_no_new_privileges(self):
        self.assertEqual(w.parse_status(status())["CapEff"], w.CAPABILITIES)
        for changes in ({"CapEff": 0}, {"CapPrm": w.CAPABILITIES | 1}, {"CapBnd": 2**40 - 1},
                        {"CapInh": 1}, {"CapInh": 0x200000}, {"CapAmb": 1}, {"NoNewPrivs": 0}):
            with self.subTest(changes=changes), self.assertRaises(a.Rejected):
                w.parse_status(status(**changes))
        with self.assertRaisesRegex(a.Rejected, "PROCESS_STATUS"):
            w.parse_status(status() + b"CapEff:\t0000000000200004\n")

    def test_logic_only_process_binding_rejects_wrong_namespace_cgroup_and_boot(self):
        config = runtime()
        manifest_value = fixture()
        manifest_value["cgroup_parent"] = "/" + config.query_slice
        bound = binding(decode(manifest_value))
        facts = {
            "/proc/self/status": status(), "/proc/self/cgroup": ("0::" + bound.cgroup + "\n").encode(),
            "/proc/sys/kernel/random/boot_id": (bound.manifest.boot_id + "\n").encode()}
        for mutation in (None, "namespace", "cgroup", "boot", "deadline", "invocation", "parent"):
            data = dict(facts)
            if mutation == "cgroup":
                data["/proc/self/cgroup"] = b"0::/other.service\n"
            if mutation == "boot":
                data["/proc/sys/kernel/random/boot_id"] = b"00000000-0000-0000-0000-000000000000\n"
            userns = SimpleNamespace(st_dev=27, st_ino=0 if mutation == "namespace" else 28)
            parent = SimpleNamespace(st_dev=25, st_ino=0 if mutation == "parent" else 26)
            with self.subTest(mutation=mutation), patch.object(os, "getuid", return_value=0), \
                    patch.object(os, "geteuid", return_value=0), patch.object(os, "stat", return_value=userns), \
                    patch.object(os, "fstat", return_value=parent), patch.object(os, "close"), \
                    patch.object(p, "open_protected", return_value=100), \
                    patch.object(w, "_proc_bytes", side_effect=lambda filename, *args: data[filename]), \
                    patch.dict(os.environ, {"INVOCATION_ID": "bad" if mutation == "invocation" else INVOCATION}), \
                    patch.object(w.time, "clock_gettime_ns", return_value=bound.deadline_ns if mutation == "deadline" else NOW):
                if mutation is None:
                    self.assertEqual(w.verify_process(config, bound), INVOCATION)
                else:
                    with self.assertRaises(a.Rejected):
                        w.verify_process(config, bound)

    def test_real_cli_rejects_missing_arguments_and_never_emits_ready(self):
        result = subprocess.run([sys.executable, "-I", "-B", w.__file__], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"QUOTA_WORKER_REJECTED\n")

    def test_same_namespace_mount_id_binds_type_device_and_rw(self):
        slot = decode().slots[0]
        raw = b"44 1 0:41 / /synthetic rw,nosuid - ext4 /dev/synthetic rw,prjquota\n"
        w.match_mount(b"pos:\t0\nmnt_id:\t44\n", raw, slot)
        for changed in (raw.replace(b"ext4", b"ext3"), raw.replace(b"0:41", b"0:42"),
                        raw.replace(b"rw,nosuid", b"ro,nosuid"), raw.replace(b"rw,prjquota", b"ro,prjquota"),
                        raw.replace(b"/synthetic", b"/other"), raw + raw, b"malformed\n"):
            with self.subTest(raw=changed), self.assertRaises(a.Rejected):
                w.match_mount(b"mnt_id:\t44\n", changed, slot)
        with self.assertRaises(a.Rejected):
            w.match_mount(b"mnt_id:\t44\nmnt_id:\t44\n", raw, slot)

    def test_real_root_descriptor_identity_failure_closes_before_mount_query(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "slot"
            root.mkdir(mode=0o700)
            slot = replace(decode().slots[0], path=str(root))
            with patch.object(p, "open_protected", side_effect=lambda *_args, **_kw: os.open(directory, os.O_RDONLY)), \
                    patch.object(w, "_proc_bytes") as proc:
                with self.assertRaisesRegex(a.Rejected, "ROOT_CHANGED"):
                    w.open_slot(slot)
                proc.assert_not_called()

    def test_bootstrap_rejects_unpinned_module_before_execution(self):
        value = runtime_value()
        value["worker_path"] = str(Path(w.__file__).absolute())
        value["worker_sha256"] = hashlib.sha256(b"worker bytes").hexdigest()
        raw = encoded(value)
        with patch.object(sys, "flags", SimpleNamespace(isolated=1)), patch.object(sys, "dont_write_bytecode", True), \
                patch.object(w, "_bootstrap_read", side_effect=[raw, b"worker bytes", b"raise AssertionError('executed')"]), \
                patch("builtins.exec") as execute:
            with self.assertRaisesRegex(ValueError, "BOOTSTRAP_MODULE_DIGEST"):
                w._bootstrap("/synthetic/config.json", hashlib.sha256(raw).hexdigest())
            execute.assert_not_called()

    def _run_context(self, *, expired=False, short_write=False):
        from contextlib import ExitStack
        stack = ExitStack()
        self.addCleanup(stack.close)
        config = runtime()
        value = fixture()
        value["installation_digest"] = p.installation_digest(config)
        manifest_raw = encoded(value)
        manifest = decode(value)
        config = replace(config, manifest_digest=manifest.digest)
        bound = binding(manifest)
        stack.enter_context(patch.object(p, "load_runtime", return_value=config))
        stack.enter_context(patch.object(p, "read_protected", return_value=manifest_raw))
        stack.enter_context(patch.object(p, "verify_installation", return_value=13))
        process = stack.enter_context(patch.object(w, "verify_process", side_effect=
                                      [INVOCATION, a.Rejected("QUERY_DEADLINE")] if expired else None,
                                      return_value=INVOCATION))
        stack.enter_context(patch.object(w.fcntl, "fcntl", return_value=10))
        root = stack.enter_context(patch.object(w, "open_slot", return_value=14))
        close = stack.enter_context(patch.object(os, "close"))
        stack.enter_context(patch.object(os, "listdir", return_value=[]))
        stack.enter_context(patch.object(w.time, "clock_gettime_ns", return_value=NOW))
        dup = stack.enter_context(patch.object(os, "dup2"))
        write = stack.enter_context(patch.object(os, "write", side_effect=lambda fd, data: 1 if short_write else len(data)))
        execute = stack.enter_context(patch.object(os, "execve", side_effect=RuntimeError("MOCK_EXEC_STOP")))
        stack.enter_context(patch.object(os, "supports_fd", {execute}))
        return config, bound, process, root, close, dup, write, execute

    def test_logic_only_exec_uses_fixed_native_fd_clean_env_and_ready_binding(self):
        config, bound, _process, _root, close, dup, write, execute = self._run_context()
        with self.assertRaisesRegex(RuntimeError, "MOCK_EXEC_STOP"):
            w.run("/synthetic/config.json", config.digest, p.encode_ticket(bound))
        dup.assert_called_once_with(14, 3, inheritable=True)
        execute.assert_called_once_with(10, [config.native_path], {"LANG": "C", "LC_ALL": "C"})
        ready = json.loads(write.call_args.args[1])
        self.assertEqual(ready["request_id"], bound.request_id)
        self.assertEqual(ready["runtime_digest"], config.digest)
        self.assertEqual(ready["unit"], bound.unit)
        self.assertLessEqual(len(write.call_args.args[1]), w.MAX_READY_BYTES)
        self.assertEqual([call.args[0] for call in close.call_args_list], [13, 14, 3, 10])

    def test_logic_only_expired_after_storage_io_never_writes_ready_or_executes(self):
        config, bound, _process, _root, _close, _dup, write, execute = self._run_context(expired=True)
        with self.assertRaisesRegex(a.Rejected, "QUERY_DEADLINE"):
            w.run("/synthetic/config.json", config.digest, p.encode_ticket(bound))
        write.assert_not_called()
        execute.assert_not_called()

    def test_logic_only_partial_ready_write_never_starts_native(self):
        config, bound, _process, _root, _close, dup, _write, execute = self._run_context(short_write=True)
        with self.assertRaisesRegex(a.Rejected, "READY_WRITE"):
            w.run("/synthetic/config.json", config.digest, p.encode_ticket(bound))
        execute.assert_not_called()
        dup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
