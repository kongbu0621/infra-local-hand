"""Isolated imports with real timestamp-valid poisoned bytecode caches.

Protected ownership reads are explicitly modeled for unprivileged CI. Actual
Python import/cache selection, pinned bytes and fail-closed imports are tested;
no systemd, quota fixture or host acceptance is claimed.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import subprocess
import stat
import sys
import tempfile
import unittest


ENTRY = Path(__file__).parent / "e3_host" / "q2_batch_check.py"
COMMIT = "a" * 40


class SourceLoadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = {}
        self.add("tools/local_hand/__init__.py", b"")
        self.provenance = self.add("tools/local_hand/provenance.py",
            ("def source_commit(*, require_clean=False):\n"
             "    assert require_clean is True\n"
             "    return " + repr(COMMIT) + "\n").encode())
        self.add("tools/local_hand_jobs/__init__.py", b"")
        self.add("tools/local_hand_jobs/fixed.py", b"answer = 41\n")
        self.add("tools/admin/local_hand_quota_observer/fixed.py", b"answer = 42\n")
        self.add("tests/e3_host/q2_batch_check.py", b"# synthetic pinned entry\n")

    def add(self, relative, raw):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        self.files[relative] = hashlib.sha256(raw).hexdigest()
        return path

    def child(self, body, *, before=""):
        fixture = self.root / "fixture.json"
        fixture.write_text(json.dumps({"source_commit": COMMIT, "files": self.files}))
        script = """
import importlib, importlib.util, json, sys, types
from pathlib import Path
spec = importlib.util.spec_from_file_location('isolated_batch', sys.argv[1])
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)
root = Path(sys.argv[2])
value = json.loads((root / 'fixture.json').read_bytes())
# Model protected ownership only. Do not model module loading or cache reads.
batch.protected = lambda name, maximum: Path(name).read_bytes()
""" + before + "\nbatch.source(value, root)\n" + body
        return subprocess.run([sys.executable, "-I", "-B", "-c", script, str(ENTRY), str(self.root)],
                              capture_output=True, text=True, timeout=10)

    def test_valid_poisoned_cache_executes_normally_but_never_through_batch(self):
        real = self.provenance.read_bytes().ljust(512, b" ")
        poison = b"raise RuntimeError('SYNTHETIC_CACHE_EXECUTED')\n".ljust(512, b" ")
        timestamp = 1_700_000_000
        self.provenance.write_bytes(poison)
        os.utime(self.provenance, (timestamp, timestamp))
        cached = Path(importlib.util.cache_from_source(str(self.provenance)))
        py_compile.compile(str(self.provenance), cfile=str(cached), doraise=True,
                           invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
        self.provenance.write_bytes(real)
        os.utime(self.provenance, (timestamp, timestamp))
        self.files["tools/local_hand/provenance.py"] = hashlib.sha256(real).hexdigest()
        cache_before = cached.read_bytes()
        control = subprocess.run([sys.executable, "-I", "-B", "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); import local_hand.provenance", str(self.root / "tools")],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(0, control.returncode)
        self.assertIn("SYNTHETIC_CACHE_EXECUTED", control.stderr)
        result = self.child("""
from local_hand import provenance
assert provenance.source_commit(require_clean=True) == 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
assert isinstance(provenance.__loader__, batch.Pinned)
print('PINNED_SOURCE_USED')
""")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("PINNED_SOURCE_USED\n", result.stdout)
        self.assertEqual(cache_before, cached.read_bytes())

    def test_verified_bytes_retained_and_admin_namespace_has_no_search_path(self):
        result = self.child("""
(root / 'tools/local_hand_jobs/fixed.py').write_text("raise RuntimeError('CHANGED_AFTER_VERIFICATION')\\n")
from local_hand_jobs import fixed
from admin.local_hand_quota_observer import fixed as admin_fixed
import admin
assert fixed.answer == 41 and admin_fixed.answer == 42
assert admin.__path__ == [] and admin.__file__ == '<pinned-namespace>'
assert str(root / 'tools') not in sys.path
print('RETAINED_SOURCE_USED')
""")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("RETAINED_SOURCE_USED\n", result.stdout)

    def test_preimported_owned_roots_rejected_before_any_source_execution(self):
        for package in ("admin", "local_hand", "local_hand_jobs", "local_hand_connect", "local_hand_mcp"):
            with self.subTest(package=package):
                result = self.child("raise AssertionError('source accepted preimports')",
                    before="sys.modules[" + repr(package) + "] = types.ModuleType(" + repr(package) + ")")
                self.assertNotEqual(0, result.returncode)
                self.assertIn("FIXTURE_PREIMPORTED", result.stderr)

    def test_unlisted_modules_cannot_fall_back_to_python_search_path(self):
        for package in ("local_hand_connect", "local_hand_mcp"):
            path = self.root / "shadow" / package
            path.mkdir(parents=True)
            (path / "__init__.py").write_text("raise RuntimeError('UNBOUND_PACKAGE_EXECUTED')\n")
        result = self.child("""
sys.path.insert(0, str(root / 'shadow'))
for name in ('local_hand_connect', 'local_hand_mcp', 'local_hand.unlisted', 'admin.unlisted'):
    try:
        importlib.import_module(name)
    except ValueError as error:
        assert str(error) == 'FIXTURE_UNPINNED_MODULE'
    else:
        raise AssertionError('unlisted import accepted: ' + name)
print('UNLISTED_REJECTED')
""")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("UNLISTED_REJECTED\n", result.stdout)

    def test_optional_package_imports_require_explicit_verified_sources(self):
        for package in ("local_hand_connect", "local_hand_mcp"):
            self.add("tools/" + package + "/__init__.py", b"from .fixed import answer\n")
            self.add("tools/" + package + "/fixed.py", b"answer = 73\n")
        result = self.child("""
import local_hand_connect, local_hand_mcp
assert local_hand_connect.answer == local_hand_mcp.answer == 73
print('OPTIONAL_PINNED')
""")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("OPTIONAL_PINNED\n", result.stdout)

    def test_missing_package_or_source_digest_rejected_before_import(self):
        self.add("tools/local_hand_connect/fixed.py", b"answer = 73\n")
        result = self.child("raise AssertionError('missing package accepted')")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("FIXTURE_SOURCE_PARENT", result.stderr)
        self.files.pop("tools/local_hand_connect/fixed.py")
        self.files["tools/local_hand/provenance.py"] = "f" * 64
        result = self.child("raise AssertionError('wrong bytes accepted')")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("SOURCE_BYTES_CHANGED", result.stderr)


@unittest.skipUnless(os.name == "posix" and hasattr(os, "mkfifo"), "POSIX protected descriptor reads required")
class ProtectedReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def child(self, target, reason=None):
        # Only root ownership and ancestor directory permissions are modeled
        # for CI. Actual opens, no-follow flags, file kinds and reads remain real.
        script = """
import importlib.util, os, stat, sys, types
from pathlib import Path
spec = importlib.util.spec_from_file_location('isolated_batch', sys.argv[1])
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)
original = os.fstat
def ownership(fd):
    info = original(fd)
    values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
    values['st_uid'] = 0
    if stat.S_ISDIR(info.st_mode): values['st_mode'] &= ~0o022
    return types.SimpleNamespace(**values)
batch.os.fstat = ownership
try:
    value = batch.protected(sys.argv[2], 16)
except (OSError, ValueError) as error:
    if len(sys.argv) < 4 or str(error) != sys.argv[3]: raise
    print('REJECTED')
else:
    if len(sys.argv) > 3: raise AssertionError('unsafe input accepted')
    assert value == b'fixed-source'
    print('READ_ONLY')
"""
        argv = [sys.executable, "-I", "-B", "-c", script, str(ENTRY), str(target)]
        if reason is not None: argv.append(reason)
        return subprocess.run(argv, capture_output=True, text=True, timeout=5)

    def test_actual_fifo_is_rejected_without_a_writer_or_read(self):
        fifo = self.root / "fixture.fifo"
        os.mkfifo(fifo, 0o600)
        result = self.child(fifo, "FIXTURE_FILE")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("REJECTED\n", result.stdout)
        self.assertTrue(stat.S_ISFIFO(fifo.lstat().st_mode))

    def test_regular_file_read_does_not_change_bytes_or_permissions(self):
        path = self.root / "source.py"
        path.write_bytes(b"fixed-source")
        path.chmod(0o600)
        result = self.child(path)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("READ_ONLY\n", result.stdout)
        self.assertEqual(b"fixed-source", path.read_bytes())
        self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))

    def test_hardlink_setid_and_oversize_files_are_rejected(self):
        for case in ("hardlink", "setid", "oversize"):
            with self.subTest(case=case):
                path = self.root / case
                path.write_bytes(b"fixed-source")
                path.chmod(0o600)
                if case == "hardlink": os.link(path, self.root / "alias")
                if case == "setid": path.chmod(0o4600)
                if case == "oversize": path.write_bytes(b"x" * 17)
                result = self.child(path, "FIXTURE_FILE")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("REJECTED\n", result.stdout)


if __name__ == "__main__":
    unittest.main()
