"""Real subprocess checks of offline Q1 snapshot handling, never host admission."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
CLI = TOOLS / "validate_q1_fixture.py"
sys.path.insert(0, str(TOOLS))
from admin.local_hand_quota_observer import protected_inputs as p
from test_e3_quota_monitor import encoded, fixture
from test_e3_quota_worker import runtime_value


def snapshots():
    config = runtime_value()
    manifest = fixture()
    temporary = encoded(config)
    decoded = p.decode_runtime(temporary, hashlib.sha256(temporary).hexdigest())
    manifest["installation_digest"] = p.installation_digest(decoded)
    manifest["cgroup_parent"] = "/" + config["query_slice"]
    manifest_raw = encoded(manifest)
    config["manifest_digest"] = hashlib.sha256(manifest_raw).hexdigest()
    return manifest_raw, encoded(config)


@unittest.skipUnless(sys.platform.startswith("linux"), "Offline Q1 snapshot CLI is Linux-only")
class OfflineFixtureCLITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.manifest = self.base / "manifest.json"
        self.runtime = self.base / "runtime.json"
        self.manifest_raw, self.runtime_raw = snapshots()
        self.manifest.write_bytes(self.manifest_raw)
        self.runtime.write_bytes(self.runtime_raw)

    def arguments(self, **changes):
        values = {
            "manifest-snapshot": str(self.manifest),
            "manifest-sha256": hashlib.sha256(self.manifest_raw).hexdigest(),
            "runtime-snapshot": str(self.runtime),
            "runtime-sha256": hashlib.sha256(self.runtime_raw).hexdigest(),
            "source-commit": "c" * 40,
            "runtime-path": "/synthetic/admin/runtime.json",
            "journal-path": "/synthetic/control",
        }
        values.update(changes)
        return [item for key, value in values.items() for item in ("--" + key, value)]

    def invoke(self, arguments=None, *, prefix=None):
        return subprocess.run(
            [sys.executable, "-I", "-B", *(prefix or [str(CLI)]),
             *(self.arguments() if arguments is None else arguments)],
            cwd=self.base, capture_output=True, text=True, timeout=10, check=False)

    def report(self, completed, status, returncode, code=None):
        self.assertEqual(completed.returncode, returncode, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertLess(len(completed.stdout), 8192)
        value = json.loads(completed.stdout)
        self.assertEqual(value["schema"], "local-hand-quota-q1-offline-validation/v1")
        self.assertEqual(value["status"], status)
        self.assertEqual(value["evidence_class"], "OFFLINE_ONLY")
        self.assertEqual(value["host_readiness"], "NOT_VERIFIED")
        for flag in ("admission_proven", "real_e3_accepted", "production_supported"):
            self.assertIs(value[flag], False)
        if code is not None:
            self.assertEqual(value["code"], code)
        self.assertNotIn(str(self.base), completed.stdout)
        self.assertNotIn("/synthetic/", completed.stdout)
        return value

    def test_real_subprocess_reports_consistency_only_and_writes_nothing(self):
        before = sorted(str(path.relative_to(self.base)) for path in self.base.rglob("*"))
        value = self.report(self.invoke(), "CONFIG_CONSISTENT", 0)
        self.assertEqual(value["source_commit"], "c" * 40)
        self.assertEqual(value["slot_count"], 1)
        self.assertEqual(value["billing_domain_count"], 1)
        self.assertTrue(value["unverified"])
        self.assertEqual(self.manifest.read_bytes(), self.manifest_raw)
        self.assertEqual(self.runtime.read_bytes(), self.runtime_raw)
        self.assertEqual(before, sorted(str(path.relative_to(self.base)) for path in self.base.rglob("*")))

    def test_snapshot_digests_and_source_commit_are_independently_checked(self):
        for key, code, replacement in (
            ("manifest-sha256", "MANIFEST_DIGEST", "0" * 64),
            ("runtime-sha256", "RUNTIME_DIGEST", "0" * 64),
            ("source-commit", "SOURCE_COMMIT_CHANGED", "0" * 40),
        ):
            with self.subTest(key=key):
                self.report(self.invoke(self.arguments(**{key: replacement})), "REJECTED", 2, code)

    def test_invalid_value_and_missing_file_do_not_echo_supplied_input(self):
        secret = "DO_NOT_ECHO_PRIVATE_INPUT"
        completed = self.invoke(self.arguments(**{"manifest-sha256": secret}))
        self.report(completed, "REJECTED", 2, "TOKEN")
        self.assertNotIn(secret, completed.stdout + completed.stderr)
        completed = self.invoke(self.arguments(**{"runtime-snapshot": str(self.base / secret)}))
        self.report(completed, "REJECTED", 2, "SNAPSHOT_IO")
        self.assertNotIn(secret, completed.stdout + completed.stderr)

    def test_missing_required_input_has_standard_argparse_usage_error(self):
        completed = self.invoke([])
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("usage:", completed.stderr)
        self.assertIn("required", completed.stderr)

    def test_unknown_and_abbreviated_flags_are_rejected(self):
        for flag in ("--unexpected", "--manifest-snap"):
            with self.subTest(flag=flag):
                completed = self.invoke(self.arguments() + [flag, "ignored"])
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertIn("unrecognized arguments", completed.stderr)

    def test_fifo_is_rejected_without_waiting_for_a_writer(self):
        fifo = self.base / "snapshot.fifo"
        os.mkfifo(fifo)
        for key in ("manifest-snapshot", "runtime-snapshot"):
            with self.subTest(key=key):
                self.report(self.invoke(self.arguments(**{key: str(fifo)})),
                            "REJECTED", 2, "SNAPSHOT_NOT_REGULAR")

    def test_leaf_and_parent_symlinks_are_rejected(self):
        leaf = self.base / "linked.json"
        leaf.symlink_to(self.manifest)
        parent = self.base / "alias"
        parent.symlink_to(self.base, target_is_directory=True)
        for filename in (leaf, parent / "manifest.json"):
            with self.subTest(filename=filename):
                self.report(self.invoke(self.arguments(**{"manifest-snapshot": str(filename)})),
                            "REJECTED", 2, "SNAPSHOT_IO")

    def test_directory_is_rejected_before_read(self):
        self.report(self.invoke(self.arguments(**{"manifest-snapshot": str(self.base)})),
                    "REJECTED", 2, "SNAPSHOT_NOT_REGULAR")

    def test_both_snapshot_size_limits_are_enforced(self):
        for key, maximum in (("manifest-snapshot", 32768), ("runtime-snapshot", 16384)):
            with self.subTest(key=key):
                oversized = self.base / "oversized.json"
                oversized.write_bytes(b" " * (maximum + 1))
                self.report(self.invoke(self.arguments(**{key: str(oversized)})),
                            "REJECTED", 2, "SNAPSHOT_BYTE_LIMIT")

    def test_actual_snapshot_metadata_change_during_read_is_rejected(self):
        # Fault injection schedules an actual metadata change between the CLI's
        # first read and completion check; this is not evidence of host admission.
        script = """
import os, runpy, sys
sys.argv = sys.argv[1:]
target = sys.argv[sys.argv.index('--manifest-snapshot') + 1]
initial = os.stat(target)
original_read = os.read
changed = False
def read_and_change(descriptor, maximum):
    global changed
    data = original_read(descriptor, maximum)
    current = os.fstat(descriptor)
    if not changed and (current.st_dev, current.st_ino) == (initial.st_dev, initial.st_ino):
        os.utime(target, ns=(initial.st_atime_ns, initial.st_mtime_ns + 1000000000))
        changed = True
    return data
os.read = read_and_change
runpy.run_path(sys.argv[0], run_name='__main__')
"""
        self.report(self.invoke(prefix=["-c", script, str(CLI)]),
                    "REJECTED", 2, "SNAPSHOT_CHANGED")

    def test_isolated_and_no_bytecode_flags_are_required_before_repo_import(self):
        for flags in (("-I",), ("-B",)):
            with self.subTest(flags=flags):
                completed = subprocess.run(
                    [sys.executable, *flags, str(CLI), *self.arguments()], cwd=self.base,
                    capture_output=True, text=True, timeout=10, check=False)
                self.report(completed, "REJECTED", 2, "ISOLATED_PYTHON_REQUIRED")

    def test_nonlinux_is_explicitly_unsupported_before_snapshot_or_repo_access(self):
        script = """
import runpy, sys
sys.platform = 'darwin'
sys.argv = sys.argv[1:]
def audit(event, args):
    if event == 'import' and args[0].startswith('admin.'):
        raise AssertionError('unsupported platform imported repository modules')
sys.addaudithook(audit)
runpy.run_path(sys.argv[0], run_name='__main__')
"""
        self.report(self.invoke(prefix=["-c", script, str(CLI)]), "UNSUPPORTED", 3, "LINUX_REQUIRED")

    def test_declared_host_paths_processes_writes_and_runtime_imports_are_never_used(self):
        script = """
import os, runpy, sys
sys.argv = sys.argv[1:]
def audit(event, args):
    if event == 'open':
        filename, mode, flags = args
        if isinstance(filename, (str, bytes)):
            value = os.fsdecode(filename)
            if value == '/synthetic' or value.startswith('/synthetic/'):
                raise AssertionError('declared host path was opened')
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise AssertionError('offline validator attempted a write')
    if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.fork', 'ctypes.dlopen'):
        raise AssertionError('offline validator attempted host execution')
    if event == 'import' and args[0].rsplit('.', 1)[-1] in ('systemd_runtime', 'journal', 'worker'):
        raise AssertionError('offline validator imported host runtime')
def guard(function):
    def checked(filename, *args, **kwargs):
        if isinstance(filename, (str, bytes, os.PathLike)):
            value = os.fsdecode(filename)
            if value == '/synthetic' or value.startswith('/synthetic/'):
                raise AssertionError('declared host path metadata was read')
        return function(filename, *args, **kwargs)
    return checked
os.stat, os.lstat = guard(os.stat), guard(os.lstat)
sys.addaudithook(audit)
runpy.run_path(sys.argv[0], run_name='__main__')
"""
        self.report(self.invoke(prefix=["-c", script, str(CLI)]), "CONFIG_CONSISTENT", 0)


if __name__ == "__main__":
    unittest.main()
