"""Native ABI control-flow tests; wrapped syscalls are explicitly LOGIC_ONLY.

Real-binary negative cases use no inherited root FD and never query quotas.
No mount, quota change, privilege escalation, or host service is performed.
"""
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/admin/local_hand_quota_observer/quota_fd_query.c"
SHIM = ROOT / "tests/fixtures/quota_query_syscalls.c"
FLAGS = ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wconversion", "-Wformat=2",
         "-fstack-protector-strong", "-D_FORTIFY_SOURCE=2"]


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 ABI primitive is Linux-only")
class QuotaABITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which("cc")
        if not cc:
            raise unittest.SkipTest("C compiler unavailable; native ABI tests not covered")
        cls.temp = tempfile.TemporaryDirectory(prefix="lh-q1-abi-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.real = Path(cls.temp.name) / "query"
        cls.fake = Path(cls.temp.name) / "query-simulated"
        cls.build_commands = []
        for output, extra in [(cls.real, []), (cls.fake, [str(SHIM)] + [
                "-Wl,--wrap=" + name for name in ("fstat", "fcntl", "fstatfs", "ioctl", "syscall", "close")])]:
            command = [cc, *FLAGS, str(SOURCE), *extra, "-o", str(output)]
            cls.build_commands.append(command)
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise AssertionError("Native build failed:\n" + result.stdout + result.stderr)

    def invoke(self, case=None, args=()):
        env = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"}
        if case is not None:
            env["LH_Q1_TEST_CASE"] = case
        result = subprocess.run([str(self.fake if case is not None else self.real), *args],
                                env=env, capture_output=True, close_fds=True, timeout=5)
        self.assertEqual(result.stderr, b"")
        self.assertLess(len(result.stdout), 4096)
        self.assertTrue(result.stdout.endswith(b"\n"))
        body = json.loads(result.stdout)
        self.assertEqual(body["schema"], "local-hand-quota-abi/v1")
        for flag in ("admission_proven", "real_e3_accepted", "production_supported"):
            self.assertIs(body[flag], False)
        self.assertLessEqual(len(body["calls"]), 16)
        return result.returncode, body

    def test_real_binary_rejects_missing_fd_without_quota(self):
        code, body = self.invoke()
        self.assertEqual((code, body["code"]), (2, "ROOT_STAT_FAILED"))
        self.assertEqual(body["quota_syscall_attempts"], 0)
        self.assertEqual(body["calls"], [{"name": "fstat.before", "rc": -1, "errno": errno.EBADF}])

    def test_real_binary_has_no_free_argument_interface(self):
        for args in [("/",), ("--project-id", "73"), ("--set-quota", "0")]:
            with self.subTest(args=args):
                code, body = self.invoke(args=args)
                self.assertEqual((code, body["code"]), (2, "NO_ARGUMENTS_ALLOWED"))
                self.assertEqual(body["quota_syscall_attempts"], 0)
                self.assertEqual(body["calls"], [])

    def test_real_binary_output_failure_cannot_report_success(self):
        reader, writer = os.pipe()
        os.close(reader)
        try:
            result = subprocess.run([str(self.real)], stdout=writer, stderr=subprocess.PIPE,
                                    close_fds=True, timeout=5, env={"PATH": os.defpath})
        finally:
            os.close(writer)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")

    def test_logic_only_supported_fs_units_and_project_come_from_fd(self):
        for case in ("ext4", "xfs", "stale_errno"):
            with self.subTest(case=case):
                code, body = self.invoke(case)
                self.assertEqual((code, body["status"]), (0, "OBSERVED"))
                self.assertEqual(body["quota"]["hard_bytes"], 123 * 1024)
                self.assertEqual(body["root_after"], body["root"])
                self.assertEqual(body["project_after"], body["project"])
                self.assertEqual(body["enforcement_after"], body["enforcement"])
                self.assertEqual(body["project"]["id"], 73)
                self.assertEqual(body["quota_syscall_attempts"], 3)
                self.assertEqual(body["calls"][-1]["name"], "close.root")
                call = next(c for c in body["calls"] if c["name"] == "quotactl_fd.getquota")
                self.assertEqual(call["errno"], errno.EINTR if case == "stale_errno" else 0)
                self.assertEqual(call["rc"], 0)

    def test_logic_only_invalid_root_project_and_fs_do_not_query_quota(self):
        cases = {"stat_error": "ROOT_STAT_FAILED", "regular_file": "ROOT_NOT_DIRECTORY",
                 "flags_error": "ROOT_FLAGS_FAILED", "writable_fd": "ROOT_FD_MODE_UNSUPPORTED",
                 "opath_fd": "ROOT_FD_MODE_UNSUPPORTED", "fs_error": "FILESYSTEM_STAT_FAILED",
                 "unsupported_fs": "FILESYSTEM_UNSUPPORTED", "project_error": "PROJECT_QUERY_FAILED",
                 "zero_project": "INHERITED_PROJECT_REQUIRED", "no_inherit": "INHERITED_PROJECT_REQUIRED"}
        for case, reason in cases.items():
            with self.subTest(case=case):
                code, body = self.invoke(case)
                self.assertNotEqual(code, 0)
                self.assertEqual(body["code"], reason)
                self.assertEqual(body["quota_syscall_attempts"], 0)

    def test_logic_only_state_must_prove_accounting_and_enforcement(self):
        for case, reason in [("state_error", "ENFORCEMENT_QUERY_FAILED"),
                             ("no_enforcement", "PROJECT_ENFORCEMENT_UNPROVEN"),
                             ("wrong_state_version", "PROJECT_ENFORCEMENT_UNPROVEN")]:
            with self.subTest(case=case):
                code, body = self.invoke(case)
                self.assertEqual((code, body["code"]), (3, reason))
                self.assertEqual(body["quota_syscall_attempts"], 1)
                self.assertIsNone(body["quota"])

    def test_logic_only_errno_is_retained_and_query_is_not_retried(self):
        for case, expected in [("quota_eperm", errno.EPERM), ("quota_ero_fs", errno.EROFS),
                               ("quota_enosys", errno.ENOSYS), ("quota_eperm_close_error", errno.EPERM)]:
            with self.subTest(case=case):
                code, body = self.invoke(case)
                self.assertEqual((code, body["code"]), (3, "QUOTA_QUERY_FAILED"))
                calls = [c for c in body["calls"] if c["name"] == "quotactl_fd.getquota"]
                self.assertEqual(calls, [{"name": "quotactl_fd.getquota", "rc": -1, "errno": expected}])
                self.assertEqual(body["quota_syscall_attempts"], 2)
                self.assertIsNone(body["quota"])

    def test_logic_only_limit_validity_zero_and_overflow(self):
        for case, reason in [("invalid_limits", "HARD_LIMIT_FIELD_UNVERIFIED"),
                             ("unlimited", "FINITE_HARD_LIMIT_REQUIRED"),
                             ("overflow", "HARD_LIMIT_BYTE_OVERFLOW")]:
            with self.subTest(case=case):
                code, body = self.invoke(case)
                self.assertNotEqual(code, 0)
                self.assertEqual(body["code"], reason)
                self.assertIsNone(body["quota"]["hard_bytes"])
        code, body = self.invoke("boundary")
        self.assertEqual(code, 0)
        self.assertEqual(body["quota"]["hard_bytes"], ((2**64 - 1) // 1024) * 1024)

    def test_logic_only_drift_and_incomplete_rechecks_are_uncertain(self):
        cases = {"project_recheck_error": "PROJECT_RECHECK_FAILED", "project_changed": "PROJECT_CHANGED",
                 "inherit_changed": "PROJECT_CHANGED", "recheck_error": "ROOT_RECHECK_FAILED",
                 "root_changed": "ROOT_CHANGED", "uid_changed": "ROOT_CHANGED",
                 "state_recheck_error": "ENFORCEMENT_RECHECK_FAILED", "enforcement_changed": "ENFORCEMENT_CHANGED",
                 "close_error": "ROOT_CLOSE_FAILED"}
        for case, reason in cases.items():
            with self.subTest(case=case):
                code, body = self.invoke(case)
                self.assertEqual((code, body["status"], body["code"]), (4, "IO_UNCERTAIN", reason))
                self.assertEqual(sum(c["name"] == "close.root" for c in body["calls"]), 1)
                if case in ("project_changed", "inherit_changed"):
                    self.assertNotEqual(body["project"], body["project_after"])
                if case in ("root_changed", "uid_changed"):
                    self.assertNotEqual(body["root"], body["root_after"])
                if case == "enforcement_changed":
                    self.assertNotEqual(body["enforcement"], body["enforcement_after"])


if __name__ == "__main__":
    unittest.main()
