"""Boot-bound Q2 namespace checks, modeled roles and local child permissions.

No service, account, mount or quota is created. The capability test only drops
its child process's permissions; it is not systemd or guest acceptance.
"""
from contextlib import ExitStack
import copy
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

if sys.platform.startswith("linux"):
    import resource
    from admin.local_hand_quota_observer import q2_config as c, q2_management as m
    from admin.local_hand_quota_observer import q2_runtime as r, systemd_runtime as runtime
    from local_hand_jobs import quota_contract as q
    from q2_fixtures import BOOT, SECOND
    from test_e3_quota_q2_runtime import declaration, config


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux namespace identity")
class NamespaceTests(unittest.TestCase):
    def setUp(self):
        self.pin = dict(device=4, inode=123)
        self.observed = SimpleNamespace(st_dev=4, st_ino=123)

    def test_matching_pin_reads_self_only_and_preserves_protected_input(self):
        before = copy.deepcopy(self.pin)
        with mock.patch.object(runtime, "_boot_id", return_value=BOOT) as boot, \
             mock.patch.object(c.os, "stat", return_value=self.observed) as observed:
            self.assertEqual(before, c.initial_namespace(self.pin, BOOT))
        observed.assert_called_once_with("/proc/self/ns/user")
        self.assertEqual(2, boot.call_count)
        self.assertEqual(before, self.pin)

    def test_missing_malformed_or_forged_pin_rejects_without_namespace_read(self):
        bad = (None, {}, dict(device=True, inode=123), dict(device=4, inode=0),
               dict(self.pin, trusted=True), dict(self.pin, path="/proc/self/ns/user"))
        for pin in bad:
            with self.subTest(pin=pin), mock.patch.object(c.os, "stat") as observed:
                with self.assertRaises(q.QuotaError): c.initial_namespace(pin, BOOT)
                observed.assert_not_called()

    def test_changed_namespace_never_replaces_the_initial_pin(self):
        for info in (SimpleNamespace(st_dev=5, st_ino=123), SimpleNamespace(st_dev=4, st_ino=124)):
            before = copy.deepcopy(self.pin)
            with mock.patch.object(runtime, "_boot_id", return_value=BOOT), \
                 mock.patch.object(c.os, "stat", return_value=info) as observed:
                with self.assertRaisesRegex(q.QuotaError, "INITIAL_USER_NAMESPACE_REQUIRED"):
                    c.initial_namespace(self.pin, BOOT)
            observed.assert_called_once_with("/proc/self/ns/user")
            self.assertEqual(before, self.pin)

    def test_boot_must_match_before_and_after_namespace_observation(self):
        for values, calls in ((["f"*36], 0), ([BOOT, "f"*36], 1)):
            with mock.patch.object(runtime, "_boot_id", side_effect=values), \
                 mock.patch.object(c.os, "stat", return_value=self.observed) as observed:
                with self.assertRaisesRegex(q.QuotaError, "INITIAL_NAMESPACE_BOOT_CHANGED"):
                    c.initial_namespace(self.pin, BOOT)
                self.assertEqual(calls, observed.call_count)

    def test_unreadable_self_namespace_is_not_a_success_or_pid1_fallback(self):
        for failure in (PermissionError(errno.EACCES, "denied"), FileNotFoundError(errno.ENOENT, "gone")):
            with mock.patch.object(runtime, "_boot_id", return_value=BOOT), \
                 mock.patch.object(c.os, "stat", side_effect=failure) as observed:
                with self.assertRaises(type(failure)): c.initial_namespace(self.pin, BOOT)
            observed.assert_called_once_with("/proc/self/ns/user")

    def test_protected_configuration_digest_rejects_replaced_namespace_pin(self):
        original = declaration(); raw = q._canonical(original, c.LIMIT)
        modified = copy.deepcopy(original); modified["initial_userns"]["inode"] += 1
        with mock.patch.object(c, "read_protected", return_value=q._canonical(modified, c.LIMIT)), \
             mock.patch.object(c, "executable") as executable:
            with self.assertRaises(q.QuotaError): c.load("/synthetic/config.json", c.hashlib.sha256(raw).hexdigest())
            executable.assert_not_called()

    def controller_context(self, stack):
        adapter = SimpleNamespace(initial_userns_device=4, initial_userns_inode=123)
        manifest = SimpleNamespace(boot_id=BOOT, cgroup_parent="/query.slice")
        spec = SimpleNamespace(limit_cpu_seconds=10, cgroup="/controller.slice/once.service")
        actual_read = m.guard._fixed_read
        def read(path, maximum):
            if path == "/proc/1/comm": return b"systemd\n"
            if path == "/proc/self/status": return b"Pid:\t99\nUid:\t0 0 0 0\n"
            return actual_read(path, maximum)
        for patcher in (mock.patch.object(m.os, "getuid", return_value=0),
                        mock.patch.object(m.os, "geteuid", return_value=0),
                        mock.patch.object(m.os, "getpid", return_value=99),
                        mock.patch.object(resource, "getrlimit", return_value=(10, 10)),
                        mock.patch.object(m, "_boot_id", return_value=BOOT),
                        mock.patch.object(runtime, "_boot_id", return_value=BOOT),
                        mock.patch.object(m.guard, "_fixed_read", side_effect=read),
                        mock.patch.object(m.guard, "_own_cgroup", return_value=spec.cgroup),
                        mock.patch.object(m.guard, "_pipe_identity", side_effect=lambda fd: (7, fd)),
                        mock.patch.object(c.os, "stat", return_value=self.observed)):
            stack.enter_context(patcher)
        return adapter, manifest, spec

    def test_controller_keeps_cpu_uid_process_group_and_pipe_checks(self):
        with ExitStack() as stack:
            args = self.controller_context(stack)
            self.assertEqual((99, (7, 1), (7, 2)), m.host_identity(*args))
            for fault in (mock.patch.object(m.os, "geteuid", return_value=1),
                          mock.patch.object(resource, "getrlimit", return_value=(10, 11)),
                          mock.patch.object(m.guard, "_own_cgroup", return_value="/other.service"),
                          mock.patch.object(m.guard, "_pipe_identity", return_value=(7, 1)),
                          mock.patch.object(c.os, "stat", return_value=SimpleNamespace(st_dev=4, st_ino=124))):
                with fault, self.assertRaises(q.QuotaError): m.host_identity(*args)

    def test_all_runtime_roles_reject_wrong_namespace_before_cgroup_access(self):
        cfg = config()
        for role in ("listener", "admission", "query", "native"):
            with self.subTest(role=role), mock.patch.object(r.os, "getuid", return_value=0), \
                 mock.patch.object(r.os, "geteuid", return_value=0), \
                 mock.patch.object(r, "_boot_id", return_value=BOOT), \
                 mock.patch.object(runtime, "_boot_id", return_value=BOOT), \
                 mock.patch.object(c.os, "stat", return_value=SimpleNamespace(st_dev=4, st_ino=124)), \
                 mock.patch.object(c, "pinned_directory") as directory:
                with self.assertRaisesRegex(q.QuotaError, "INITIAL_USER_NAMESPACE_REQUIRED"): r.host(cfg, role)
                directory.assert_not_called()

    @unittest.skipUnless(getattr(os, "geteuid", lambda: -1)() == 0, "Requires isolated root child to drop capabilities")
    def test_real_child_drops_capabilities_and_uses_original_namespace_pin(self):
        # The test supplies a modeled trusted pin. Only the permission failure,
        # unchanged self namespace and capability reduction are real OS facts;
        # this does not establish a production initial-namespace attestation.
        script = r'''
import ctypes, errno, json, os, sys
sys.path.insert(0, sys.argv[1])
from admin.local_hand_quota_observer import q2_config as c, systemd_runtime as r
from local_hand_jobs import quota_contract as q
class Header(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]
class Data(ctypes.Structure):
    _fields_ = [("effective", ctypes.c_uint32), ("permitted", ctypes.c_uint32), ("inheritable", ctypes.c_uint32)]
before = os.stat("/proc/self/ns/user")
try: pid1 = os.stat("/proc/1/ns/user")
except PermissionError: pass  # The executor can already have restricted capabilities.
else: assert (before.st_dev, before.st_ino) == (pid1.st_dev, pid1.st_ino)
pin = dict(device=before.st_dev, inode=before.st_ino); boot = r._boot_id()
libc = ctypes.CDLL(None, use_errno=True); header = Header(0x20080522, 0); empty = (Data * 2)()
assert libc.capset(ctypes.byref(header), empty) == 0, ctypes.get_errno()
denied = False
try: os.stat("/proc/1/ns/user")
except PermissionError as error:
    assert error.errno in (errno.EACCES, errno.EPERM); denied = True
assert c.initial_namespace(pin, boot) == pin
try: c.initial_namespace(dict(pin, inode=pin["inode"]+1), boot)
except q.QuotaError: rejected = True
else: rejected = False
print(json.dumps(dict(pid1_denied=denied, self_pin_matched=True, changed_pin_rejected=rejected)))
'''
        run = subprocess.run([sys.executable, "-I", "-B", "-c", script,
                              str(Path(__file__).resolve().parents[1] / "tools")], capture_output=True, timeout=10)
        self.assertEqual(0, run.returncode, run.stderr.decode())
        result = json.loads(run.stdout)
        self.assertTrue(result["self_pin_matched"] and result["changed_pin_rejected"])
        if not result["pid1_denied"]: self.skipTest("PID 1 permissions do not reproduce the restricted-root denial here")


if __name__ == "__main__": unittest.main()
