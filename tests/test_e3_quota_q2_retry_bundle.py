"""Actual nested helper imports before the future staging directory exists."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from e3_host import q2_retry_bundle as b


def hashes(files):
    return {path: hashlib.sha256(raw.encode() if type(raw) is str else raw).hexdigest()
            for path, raw in files.items()}


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux guest paths and nested orchestration helpers")
class VirtualBundle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "future" / "tools"
        self.original = importlib.util.spec_from_file_location
        self.source = Path(b.__file__).parent

    def files(self, *names):
        return {str(self.directory / (name + ".py")): (self.source / (name + ".py")).read_bytes()
                for name in names}

    def test_actual_prepare_and_its_nested_contract_import_with_no_staging(self):
        files = self.files("q2_prepare", "q2_prepare_contract", "q2_prepare_driver")
        with b.virtual_tools(files, hashes(files)) as virtual:
            prepare = virtual.load(self.directory / "q2_prepare.py", "_bootstrap_prepare")
            driver = virtual.load(self.directory / "q2_prepare_driver.py", "_bootstrap_driver")
            contract = driver.helper("q2_prepare_contract")
            self.assertEqual(prepare.c.__file__, str(self.directory / "q2_prepare_contract.py"))
            self.assertEqual(contract.__file__, prepare.c.__file__)
            self.assertEqual(contract.encoded({"ready": True}), b'{"ready":true}\n')
            self.assertEqual(prepare.reason(ValueError("SYNTHETIC_FAILURE")), "SYNTHETIC_FAILURE")
            self.assertFalse(self.directory.exists())
        self.assertIs(importlib.util.spec_from_file_location, self.original)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_actual_delivery_transport_helper_import(self):
        files = self.files("q2_retry_delivery", "q2_prepare_delivery")
        with b.virtual_tools(files, hashes(files)) as virtual:
            delivery = virtual.load(self.directory / "q2_retry_delivery.py", "_bootstrap_delivery")
            transport = delivery.transport()
            self.assertEqual(transport.__file__, str(self.directory / "q2_prepare_delivery.py"))
            self.assertEqual(transport.raw_json({"ok": True}), b'{"ok":true}\n')
        self.assertFalse(self.directory.exists())

    def test_all_members_are_verified_before_any_execution(self):
        one = str(self.directory / "q2_first.py")
        two = str(self.directory / "q2_second.py")
        files = {one: b"raise RuntimeError('executed')\n", two: b"pass\n"}
        expected = hashes(files); expected[two] = "0" * 64
        with self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_DIGEST"):
            b.virtual_tools(files, expected)
        self.assertIs(importlib.util.spec_from_file_location, self.original)

    def test_caller_mapping_mutation_cannot_change_verified_bytes(self):
        path = str(self.directory / "q2_sample.py")
        files = {path: "value = 'verified Unicode: 北京'\n"}
        expected = hashes(files)
        with b.virtual_tools(files, expected) as virtual:
            files[path] = "value = 'changed'\n"; expected[path] = "0" * 64
            self.assertEqual(virtual.load(path, "_sample").value, "verified Unicode: 北京")

    def test_exception_restores_hook_and_later_load_is_inactive(self):
        path = str(self.directory / "q2_failure.py")
        files = {path: b"raise RuntimeError('expected source failure')\n"}
        with self.assertRaisesRegex(RuntimeError, "expected source failure"):
            with b.virtual_tools(files, hashes(files)) as virtual:
                virtual.load(path, "_failure")
        self.assertIs(importlib.util.spec_from_file_location, self.original)
        with self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_INACTIVE"):
            virtual.load(path, "_failure")

    def test_overlapping_contexts_and_context_reentry_are_rejected(self):
        path = str(self.directory / "q2_sample.py")
        files = {path: b"value = 1\n"}
        manager = b.virtual_tools(files, hashes(files))
        with manager:
            with self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_OVERLAP"):
                with b.virtual_tools(files, hashes(files)):
                    self.fail("overlap entered")
            self.assertEqual(manager.load(path, "_sample").value, 1)
        with self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_REENTRY"):
            with manager:
                self.fail("reentered")
        self.assertIs(importlib.util.spec_from_file_location, self.original)

    def test_recursive_import_rejected_and_hook_restored(self):
        path = str(self.directory / "q2_cycle.py")
        files = {path: b"import importlib.util\nspec=importlib.util.spec_from_file_location('_cycle',__file__)\n"
                      b"module=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\n"}
        with self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_RECURSIVE_IMPORT"):
            with b.virtual_tools(files, hashes(files)) as virtual:
                virtual.load(path, "_cycle")
        self.assertIs(importlib.util.spec_from_file_location, self.original)

    def test_missing_same_directory_sibling_cannot_fall_back_to_disk(self):
        self.directory.mkdir(parents=True)
        missing = self.directory / "q2_unpinned.py"
        missing.write_text("raise RuntimeError('disk fallback')\n")
        path = str(self.directory / "q2_sample.py")
        files = {path: b"pass\n"}
        with b.virtual_tools(files, hashes(files)) as virtual:
            with self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_UNPINNED_SIBLING"):
                importlib.util.spec_from_file_location("_unpinned", missing)
            with self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_UNPINNED_MODULE"):
                virtual.load(missing, "_unpinned")

    def test_unrelated_specs_use_normal_imports_without_interception(self):
        path = str(self.directory / "q2_sample.py")
        files = {path: b"pass\n"}
        unrelated = Path(self.tmp.name) / "runtime.py"
        unrelated.write_text("value = 9\n")
        with b.virtual_tools(files, hashes(files)):
            spec = importlib.util.spec_from_file_location("unrelated_runtime", unrelated)
            self.assertIsInstance(spec.loader, importlib.machinery.SourceFileLoader)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            self.assertEqual(module.value, 9)

    def test_alias_or_bytes_spec_cannot_bypass_exact_member_interception(self):
        path = str(self.directory / "q2_sample.py")
        files = {path: b"pass\n"}
        aliases = (path.encode(), str(self.directory) + "/./q2_sample.py",
                   str(self.directory) + "/../tools/q2_sample.py")
        with b.virtual_tools(files, hashes(files)):
            for alias in aliases:
                with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_UNPINNED_SIBLING"):
                    importlib.util.spec_from_file_location("_sample", alias)

    def test_aliases_runtime_names_mixed_directories_and_limits_rejected(self):
        for path in ("relative/q2_one.py", "//tools/q2_one.py", "/tools/../q2_one.py", "/tools/./q2_one.py",
                     "/tools/runtime.py", "/tools/q2_one.py/", "/tools\\q2_one.py"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_PATH"):
                files = {path: b"pass\n"}; b.virtual_tools(files, hashes(files))
        files = {"/one/q2_one.py": b"pass\n", "/two/q2_two.py": b"pass\n"}
        with self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_DIRECTORY"):
            b.virtual_tools(files, hashes(files))
        files = {f"/tools/q2_{number}.py": b"pass\n" for number in range(65)}
        with self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_FILES"):
            b.virtual_tools(files, hashes(files))
        files = {"/tools/q2_one.py": b"#" * (b.MAX_BYTES + 1)}
        with self.assertRaisesRegex(ValueError, "RETRY_BUNDLE_SIZE"):
            b.virtual_tools(files, hashes(files))

    def test_no_argument_entry_is_blocked(self):
        result = subprocess.run([sys.executable, "-I", "-B", b.__file__], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'"status": "BLOCKED"', result.stdout)
        self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
