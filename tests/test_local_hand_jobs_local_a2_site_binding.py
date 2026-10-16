"""Use a real isolated interpreter to bind the checked package to its import path."""
from pathlib import Path
import py_compile
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from local_hand_jobs import local_a2_jobs as a2, runner
from test_local_hand_jobs_local_a2_runtime import synthetic_runtime, execution_fixture


class LocalA2SiteBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.descriptor, blobs = synthetic_runtime(self.root)
        current = patch.object(a2, "SOURCE_BLOBS", blobs)
        current.start()
        self.addCleanup(current.stop)
        self.plan = execution_fixture(self.root / "execution", self.descriptor)
        for path in self.plan["roots"].values():
            Path(path).mkdir(parents=True)
        self.evidence = Path(self.plan["roots"]["evidence"])
        self.probe_count = 0

    def probe(self):
        self.probe_count += 1
        directory = self.evidence / ("probe-" + str(self.probe_count))
        directory.mkdir()
        observed = runner._capture_stage(a2.runtime_probe_stage(self.plan), directory, 65536, 10)
        return a2.finish_runtime_probe(self.plan, directory, observed)

    def select_decoy(self):
        actual = Path(self.descriptor["package_root"])
        decoy = Path(self.descriptor["runtime_root"]) / "lib/python9.9/site-packages/infra_artifact_ledger"
        shutil.copytree(actual, decoy)
        self.plan["local_a2_runtime"]["package_root"] = str(decoy)
        self.plan["bindings"]["runtime_descriptor_digest"] = a2.descriptor_digest(self.plan["local_a2_runtime"])
        return actual, decoy

    def distribution_probe(self):
        stage = a2.runtime_probe_stage(self.plan)
        stdlib = self.root / 'stdlib'
        stage['argv'][5] = ('import site, sys\nsite.__file__ = %r\n'
            'sys.path.insert(0, %r)\n' % (str(stdlib / 'site.py'), str(stdlib))) + stage['argv'][5]
        self.probe_count += 1
        directory = self.evidence / ('probe-' + str(self.probe_count))
        directory.mkdir()
        observed = runner._capture_stage(stage, directory, 65536, 10)
        return a2.finish_runtime_probe(self.plan, directory, observed)

    def apport_fixture(self):
        stdlib = self.root / 'stdlib'
        stdlib.mkdir()
        source = stdlib / 'sitecustomize.py'
        source.write_text('# install the apport exception handler if available\n'
            'try:\n    import apport_python_hook\nexcept ImportError:\n    pass\n'
            'else:\n    apport_python_hook.install()\n')
        return source

    def test_exact_stdlib_apport_hook_is_admitted_only_when_inert(self):
        source = self.apport_fixture()
        py_compile.compile(str(source), doraise=True)
        self.assertTrue(self.distribution_probe()['installed_import_path_verified'])
        marker = self.root / 'hook-executed'
        (source.parent / 'apport_python_hook.py').write_text(
            "import pathlib; pathlib.Path(%r).write_text('unexpected')\n" % str(marker))
        with self.assertRaises(ValueError):
            self.distribution_probe()
        self.assertFalse(marker.exists())

    def test_stdlib_apport_source_and_selected_cache_must_both_match(self):
        source = self.apport_fixture()
        original = source.read_bytes()
        source.write_bytes(original + b'\nUNREGISTERED = True\n')
        with self.assertRaises(ValueError):
            self.distribution_probe()
        py_compile.compile(str(source), doraise=True)
        source.write_bytes(original)
        with self.assertRaises(ValueError):
            self.distribution_probe()

    def test_normal_interpreter_site_directory_is_bound_without_importing_ledger(self):
        facts = a2.verify_inputs(self.plan)
        self.assertTrue(facts["local_a2_payload_verified"])
        self.assertTrue(self.probe()["local_a2_runtime_verified"])
        self.assertFalse((Path(self.descriptor["package_root"]) / "__pycache__").exists())

    def test_no_site_probe_handles_distribution_venv_sensitive_site_discovery(self):
        stage = a2.runtime_probe_stage(self.plan)
        # Debian only returns the venv site-packages candidate when prefixes
        # identify a venv. Model that distribution behavior on any test Python.
        stage["argv"][5] = '''import site, sys
original_getsitepackages = site.getsitepackages
def distribution_sites(prefixes):
    if sys.prefix == sys.base_prefix:
        return []
    return original_getsitepackages(prefixes)
site.getsitepackages = distribution_sites
''' + stage["argv"][5]
        observed = runner._capture_stage(stage, self.evidence, 65536, 10)
        facts = a2.finish_runtime_probe(self.plan, self.evidence, observed)
        self.assertTrue(facts["installed_import_path_verified"])
        self.assertFalse((Path(self.descriptor["package_root"]) / "__pycache__").exists())

    def test_checked_decoy_package_cannot_hide_the_actual_unverified_import(self):
        actual, decoy = self.select_decoy()
        with (actual / "__init__.py").open("ab") as stream:
            stream.write(b"\nUNREGISTERED_MARKER = 'unverified-import'\n")
        imported = subprocess.run([self.descriptor["runtime_python"], "-I", "-B", "-c",
            "import infra_artifact_ledger as p; print(p.__file__); print(p.UNREGISTERED_MARKER)"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(0, imported.returncode, imported.stderr)
        self.assertIn(str(actual / "__init__.py"), imported.stdout)
        self.assertIn("unverified-import", imported.stdout)
        self.assertNotIn(str(decoy), imported.stdout)
        # The copied source/wheel/package bytes are all valid. The interpreter
        # path probe must reject them because normal -I execution ignores them.
        self.assertTrue(a2.verify_inputs(self.plan)["local_a2_payload_verified"])
        with self.assertRaises(ValueError):
            self.probe()

    def test_actual_site_hooks_are_rejected_without_execution_even_with_a_clean_decoy(self):
        actual, _ = self.select_decoy()
        marker = self.root / "hook-executed"
        for name in ("extra.pth", "sitecustomize.py", "usercustomize.py"):
            path = actual.parent / name
            code = "import pathlib; pathlib.Path(%r).write_text('unexpected')\n" % str(marker)
            path.write_text(code)
            try:
                self.assertTrue(a2.verify_inputs(self.plan)["local_a2_payload_verified"])
                with self.subTest(hook=name), self.assertRaises(ValueError):
                    self.probe()
                self.assertFalse(marker.exists())
            finally:
                path.unlink()


if __name__ == "__main__":
    unittest.main()
