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
import sys
import tempfile
import unittest


ENTRY = Path(__file__).parent / "e3_host" / "q2_launcher.py"
COMMIT = "a" * 40
TREE = "b" * 40
HARNESS = (
    "q2_fixture_check", "q2_launcher", "q2_prepare_assembly", "q2_prepare_driver",
    "q2_prepare_run", "q2_resident", "q2_supervisor", "q4_cancel_case",
    "q4_cancel_runtime", "q4_h11_recovery",
)


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
        for name in HARNESS:
            self.add("tests/e3_host/" + name + ".py", b"# synthetic pinned entry\n")

    def add(self, relative, raw):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        self.files[relative] = hashlib.sha256(raw).hexdigest()
        return path

    def child(self, body, *, before=""):
        fixture = self.root / "fixture.json"
        manifest = {"schema": "local-hand-q2-source-projection/v1", "source_commit": COMMIT,
                    "source_tree": TREE,
                    "files": {name: {"mode": 0o644, "sha256": digest}
                              for name, digest in sorted(self.files.items())}}
        manifest_raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
        (self.root / ".local-hand-source-projection.json").write_bytes(manifest_raw)
        fixture.write_text(json.dumps({"source": {"commit": COMMIT,
            "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(), "files": self.files}}))
        script = """
import importlib, importlib.util, json, sys, types
from pathlib import Path
spec = importlib.util.spec_from_file_location('isolated_launcher', sys.argv[1])
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
root = Path(sys.argv[2])
value = json.loads((root / 'fixture.json').read_bytes())
# Model protected ownership only. Do not model module loading or cache reads.
launcher.protected = lambda name, maximum: Path(name).read_bytes()
""" + before + "\nlauncher.source(value, root)\n" + body
        return subprocess.run([sys.executable, "-I", "-B", "-c", script, str(ENTRY), str(self.root)],
                              capture_output=True, text=True, timeout=10)

    def test_valid_poisoned_cache_executes_normally_but_never_through_launcher(self):
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
assert isinstance(provenance.__loader__, launcher.Pinned)
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
                self.assertIn("LAUNCHER_PREIMPORTED", result.stderr)

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
        assert str(error) == 'LAUNCHER_UNPINNED_MODULE'
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
        self.assertIn("LAUNCHER_SOURCE_PARENT", result.stderr)
        self.files.pop("tools/local_hand_connect/fixed.py")
        self.files["tools/local_hand/provenance.py"] = "f" * 64
        result = self.child("raise AssertionError('wrong bytes accepted')")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("LAUNCHER_SOURCE_CHANGED", result.stderr)

    def test_projection_manifest_is_required_and_exact(self):
        manifest = self.root / ".local-hand-source-projection.json"
        result = self.child("print('accepted')", before="")
        self.assertEqual(0, result.returncode, result.stderr)
        manifest.unlink()
        # child() recreates the manifest, so poison it after fixture setup in
        # the isolated process and before source admission.
        result = self.child("raise AssertionError('projection accepted')", before="""
value_manifest = root / '.local-hand-source-projection.json'
projection = json.loads(value_manifest.read_text())
projection['source_tree'] = 'c' * 40
value_manifest.write_text(json.dumps(projection, sort_keys=True, separators=(',', ':')) + '\\n')
""")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("LAUNCHER_PROJECTION_DIGEST", result.stderr)

    def test_namespace_and_watchdog_entries_are_rejected(self):
        for relative in ("tests/e3_host/q2_namespace_fixture.py", "tools/q2_watchdog.py",
                         "/tools/local_hand/escape.py", "tools/local_hand/../escape.py",
                         "tools//local_hand/escape.py", ".local-hand-source-projection.json"):
            with self.subTest(relative=relative):
                self.files[relative] = hashlib.sha256(b"OUT_OF_SCOPE").hexdigest()
                result = self.child("raise AssertionError('out-of-scope source accepted')")
                self.assertNotEqual(0, result.returncode)
                self.assertIn("LAUNCHER_PROJECTION_MANIFEST", result.stderr)
                self.files.pop(relative)


if __name__ == "__main__":
    unittest.main()
