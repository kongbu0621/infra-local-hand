"""Release admission includes every service package and its actual entry file."""
from __future__ import annotations

import json
import marshal
import py_compile
from pathlib import Path
import shutil
import unittest
from unittest import mock
from tempfile import TemporaryDirectory

from local_hand import provenance
from local_hand.protocol import LocalHandError
from local_hand_jobs import deployment
from local_hand_jobs.contract import JobError


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in provenance.PAYLOAD_PACKAGES:
            (self.root / name).mkdir()
            (self.root / name / "__init__.py").write_text("# synthetic fixture\n")
        for rel in ("local_hand/worker.py", "local_hand/provenance.py", "local_hand_jobs/cli.py", "local_hand_mcp/server.py"):
            (self.root / rel).write_text("# synthetic fixture\n")
        patch = mock.patch.object(provenance, "__file__", str(self.root / "local_hand/provenance.py"))
        patch.start()
        self.addCleanup(patch.stop)
        self.entry = str(self.root / "local_hand_jobs/cli.py")
        self.digest = provenance.full_payload_digest(self.root)
        self.stamp()

    def stamp(self, artifact_kind="wheel"):
        metadata = {"schema_version": provenance.BUILD_SCHEMA, "product_version": provenance.VERSION,
                    "source_commit": "a" * 40, "artifact_kind": artifact_kind,
                    "files": provenance.payload_hashes(self.root)}
        (self.root / "local_hand" / provenance.METADATA_NAME).write_text(json.dumps(metadata))

    def verify(self, **updates):
        args = dict(expected_source_commit="a" * 40, expected_payload_digest=self.digest,
                    expected_entrypoint=self.entry, actual_entrypoint=self.entry)
        args.update(updates)
        return deployment.verify_release(**args)

    def test_complete_release_admitted_with_exact_identity(self):
        self.assertEqual(self.verify(), {"source_commit": "a" * 40,
                         "installed_payload_digest": self.digest, "execution_entrypoint": self.entry})

    def test_jobs_and_mcp_bytes_are_bound_independently_of_rewritten_metadata(self):
        for rel in ("local_hand_jobs/cli.py", "local_hand_mcp/server.py"):
            with self.subTest(rel=rel):
                path = self.root / rel
                path.write_text("# altered fixture\n")
                with self.assertRaises(JobError):
                    self.verify()
                self.stamp()  # Forging self-described metadata cannot override private digest.
                with self.assertRaises(JobError):
                    self.verify()
                path.write_text("# synthetic fixture\n")
                self.stamp()
        self.assertEqual(self.verify()["installed_payload_digest"], self.digest)

    def test_source_and_entrypoint_are_not_interchangeable(self):
        with self.assertRaises(JobError):
            self.verify(expected_source_commit="b" * 40)
        with self.assertRaises(JobError):
            self.verify(expected_entrypoint=str(self.root / "local_hand_mcp/server.py"))
        with self.assertRaises(JobError):
            self.verify(actual_entrypoint=str(self.root / "local_hand/worker.py"))

    def test_symlink_entrypoint_and_symlink_parent_rejected(self):
        alias = self.root / "alias.py"
        alias.symlink_to(self.entry)
        with self.assertRaises(JobError):
            self.verify(expected_entrypoint=str(alias), actual_entrypoint=str(alias))
        folder = self.root / "alias"
        folder.symlink_to(self.root / "local_hand_jobs", target_is_directory=True)
        with self.assertRaises(JobError):
            self.verify(expected_entrypoint=str(folder / "cli.py"), actual_entrypoint=str(folder / "cli.py"))

    def test_double_slash_release_identity_cannot_be_admitted(self):
        # Python can preserve // in both the imported module's __file__ and
        # the service entry file, while POSIX resolves the same file bytes.
        alias = "/" + self.entry
        with mock.patch.object(provenance, "__file__", "/" + provenance.__file__):
            with self.assertRaises(JobError) as raised:
                self.verify(expected_entrypoint=alias, actual_entrypoint=alias)
        self.assertEqual(raised.exception.code, "PROVENANCE_MISMATCH")
        self.assertEqual(self.verify()["execution_entrypoint"], self.entry)

    def test_missing_package_cannot_be_hidden_in_metadata(self):
        shutil.rmtree(self.root / "local_hand_mcp")
        self.stamp()
        with self.assertRaises(JobError):
            self.verify()

    def test_unbound_extension_rejected(self):
        (self.root / "local_hand_jobs/shadow.so").write_bytes(b"synthetic extension")
        with self.assertRaises(LocalHandError):
            provenance.full_payload_digest(self.root)

    def test_legacy_source_staging_cannot_admit_job_service(self):
        self.stamp(artifact_kind="source-staging")
        with self.assertRaises(JobError):
            self.verify()

    def test_source_checkout_identity_requires_clean_bytes(self):
        (self.root / "local_hand" / provenance.METADATA_NAME).unlink()
        with mock.patch.object(provenance, "source_commit", return_value="a" * 40) as source:
            self.verify()
            source.assert_called_once_with(require_clean=True)

    def test_legitimate_cache_does_not_change_digest_but_replaced_code_is_rejected(self):
        source = self.root / "local_hand_jobs/cli.py"
        cache = Path(py_compile.compile(str(source), doraise=True))
        self.assertEqual(provenance.full_payload_digest(self.root), self.digest)
        header = cache.read_bytes()[:16]
        source.write_text("raise RuntimeError('synthetic malicious cache')\n")
        py_compile.compile(str(source), cfile=str(cache), doraise=True)
        changed = cache.read_bytes()[16:]
        source.write_text("# synthetic fixture\n")
        cache.write_bytes(header + changed)
        with self.assertRaises(LocalHandError):
            provenance.full_payload_digest(self.root)

    def test_cache_sharing_and_import_history_do_not_change_release_identity(self):
        source = self.root / "local_hand_jobs/cli.py"
        source.write_text("value = 'a synthetic non identifier'\n")
        self.digest = provenance.full_payload_digest(self.root)
        self.stamp()
        for optimize in (0, 1, 2):
            cache = Path(py_compile.compile(str(source), doraise=True, optimize=optimize))
            header = cache.read_bytes()[:16]
            for filename in (str(source), "tools/local_hand_jobs/cli.py", "local_hand_jobs/cli.py"):
                code = compile(source.read_bytes(), filename, "exec", dont_inherit=True, optimize=optimize)
                # Both are valid caches; v2 does not share objects, v4 does.
                # Retaining a constant also changes v4 flags on Python 3.12.
                for version in (2, 4):
                    cache.write_bytes(header + marshal.dumps(code, version))
                    retained = code.co_consts[0]
                    with mock.patch.object(marshal, "loads", side_effect=AssertionError("untrusted load")):
                        self.assertEqual(self.verify()["installed_payload_digest"], self.digest)
                    self.assertIsInstance(retained, str)
                cache.write_bytes(header + marshal.dumps(code.replace(co_consts=("replaced", None))))
                with self.assertRaises(JobError):
                    self.verify()
                cache.write_bytes(header + marshal.dumps(code))

    def test_bad_cache_size_magic_and_trailing_bytes_rejected(self):
        source = self.root / "local_hand_jobs/cli.py"
        cache = Path(py_compile.compile(str(source), doraise=True))
        original = cache.read_bytes()
        for changed in (original[:10], b"xxxx" + original[4:], original + b"N"):
            cache.write_bytes(changed)
            with self.assertRaises(LocalHandError):
                provenance.full_payload_digest(self.root)
        cache.write_bytes(original)
        with mock.patch.object(provenance, "MAX_CACHE_BYTES", 1):
            with self.assertRaises(LocalHandError):
                provenance.full_payload_digest(self.root)


if __name__ == "__main__":
    unittest.main()
