"""Exact evidence reads through the public Ledger snapshot storage adapter."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid
from unittest import mock

import test_local_hand_artifact_archive as fixtures
from local_hand_jobs import artifact_archive as consumer


@unittest.skipUnless(sys.platform == "linux" and fixtures.HAS_LEDGER,
                     "Linux and installed Ledger required")
class SnapshotReadTests(fixtures.BundleFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        from infra_artifact_ledger import recovery
        self.recovery = recovery
        self.store = self.root / "archive"
        status = dict(operation_id=fixtures.OP, request_digest="a" * 64,
            lifecycle="TERMINAL", phase="EXITED", outcome="SUCCEEDED", evidence="SEALED",
            observed_at=1.5, seal_refs=[{k: self.descriptor[k] for k in ("seal_id", "seal_sha256")}])
        self.status_path = self.root / "status.json"
        raw = consumer._json(status)
        self.status_path.write_bytes(raw)
        self.archived = consumer.archive_result(self.store, producer="test:snapshot-reader",
            status_path=self.status_path, status_sha256=consumer._sha(raw), evidence_dir=self.evidence)
        snapshots = self.root / "snapshots"
        snapshots.mkdir(mode=0o700)
        self.scratch = self.root / "scratch"
        self.scratch.mkdir(mode=0o700)
        self.snapshot = recovery.create(db=self.store / "ledger.sqlite", output_root=snapshots,
            snapshot_id=uuid.uuid4().hex, source_commit="1" * 40)["data"]
        self.output = self.root / "readback"
        self.arguments = dict(snapshot=self.snapshot["snapshot_path"],
            expected_manifest_sha256=self.snapshot["manifest_sha256"],
            artifact_id=self.archived["artifact_id"], version_id=self.archived["version_id"],
            output=self.output, scratch_parent=self.scratch)

    def tree(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def read(self, **overrides):
        return consumer.read_snapshot_version(**dict(self.arguments, **overrides))

    def test_exact_read_without_original_archive_or_execution_and_no_ledger_writes(self):
        expected = self.tree(next(self.store.glob("task-*")))
        snapshot_path = Path(self.snapshot["snapshot_path"])
        original_snapshot = self.tree(snapshot_path)
        api = consumer._ledger_api()
        with api.open(self.store / "ledger.sqlite") as ledger:
            ledger_type = type(ledger)
        shutil.rmtree(self.store)
        shutil.rmtree(self.evidence)
        shutil.rmtree(self.fixture.store.root)
        self.status_path.unlink()
        with mock.patch.object(api, "initialize", side_effect=AssertionError("no initialization")), \
                mock.patch.object(ledger_type, "execute", side_effect=AssertionError("no execution")):
            result = self.read()
        self.assertTrue(result["content_verified"])
        self.assertEqual(result["database_sha256"], self.snapshot["database_sha256"])
        self.assertEqual(result["source"]["operation_id"], fixtures.OP)
        self.assertEqual(set(result["files"]), set(consumer.LIMITS))
        self.assertEqual(self.tree(self.output / "evidence"),
                         {name: expected[name] for name in consumer.LIMITS})
        self.assertEqual(json.loads((self.output / "read-receipt/result.json").read_bytes()), result)
        self.assertEqual(self.tree(snapshot_path), original_snapshot)

    def test_cli_in_independent_interpreter(self):
        script = ("import sys; sys.path.insert(0, sys.argv.pop(1)); "
                  "from local_hand_jobs.artifact_archive import main; raise SystemExit(main())")
        args = [value for key, value in self.arguments.items()
                for value in ("--" + key.replace("_", "-"), str(value))]
        completed = subprocess.run([sys.executable, "-I", "-B", "-c", script,
            str(Path(consumer.__file__).parents[1]), "read-snapshot", *args],
            capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["version_id"], self.archived["version_id"])

    def test_wrong_digest_and_corrupt_snapshot_never_publish_evidence(self):
        with self.assertRaises(self.recovery.RecoveryError):
            self.read(expected_manifest_sha256="0" * 64)
        self.assertFalse(self.output.exists())
        database = Path(self.snapshot["snapshot_path"]) / "ledger.sqlite"
        raw = database.read_bytes()
        database.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        with self.assertRaises(self.recovery.RecoveryError):
            self.read()
        self.assertFalse((self.output / "evidence").exists())

    def test_wrong_artifact_or_version_keeps_restore_but_never_reports_success(self):
        original = self.tree(self.store)
        for field in ("artifact_id", "version_id"):
            target = self.root / field
            with self.subTest(field=field), self.assertRaises(consumer._ledger_api().LedgerError):
                self.read(**{field: field.split("_")[0] + ":not-present", "output": target})
            self.assertTrue((target / "snapshot-receipt/restore.json").is_file())
            self.assertFalse((target / "evidence").exists())
            self.assertFalse((target / "read-receipt").exists())
        self.assertEqual(self.tree(self.store), original)

    def test_existing_output_is_preserved_and_new_read_is_allowed(self):
        self.read()
        original = self.tree(self.output)
        with self.assertRaises(self.recovery.RecoveryError) as caught:
            self.read()
        self.assertEqual(caught.exception.code, "TARGET_EXISTS")
        self.assertEqual(self.tree(self.output), original)
        self.assertTrue(self.read(output=self.root / "second-read")["content_verified"])

    def test_parent_traversal_output_is_rejected_before_restore(self):
        parent = self.root / "parent"
        parent.mkdir(mode=0o700)
        output = parent / ".." / "readback"
        original = self.tree(Path(self.snapshot["snapshot_path"]))
        with mock.patch.object(self.recovery, "restore", wraps=self.recovery.restore) as restore:
            with self.assertRaises(consumer.ArchiveError) as caught:
                self.read(output=output)
            self.assertEqual(caught.exception.code, "INVALID_INPUT")
            restore.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.tree(Path(self.snapshot["snapshot_path"])), original)

    def test_error_after_restore_retains_copy_and_allows_fresh_read(self):
        with mock.patch.object(consumer, "_load_version", side_effect=OSError("interrupted read")):
            with self.assertRaises(OSError):
                self.read()
        self.assertTrue((self.output / "snapshot-receipt/restore.json").is_file())
        self.assertEqual(consumer._file_digest(self.output / "ledger.sqlite")["sha256"],
                         self.snapshot["database_sha256"])
        self.assertFalse((self.output / "evidence").exists())
        self.assertTrue(self.read(output=self.root / "retry-read")["content_verified"])

    def test_cli_restore_rejection_is_not_an_archive_commit(self):
        original = self.tree(self.store)
        arguments = dict(self.arguments, expected_manifest_sha256="0" * 64)
        args = [value for key, value in arguments.items()
                for value in ("--" + key.replace("_", "-"), str(value))]
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(consumer.main(["read-snapshot", *args]), 1)
        response = json.loads(stream.getvalue())
        self.assertEqual(response["code"], "INTEGRITY_FAILURE")
        self.assertEqual(response["commit_state"], "not_applicable")
        self.assertEqual(response["publication_state"], "not_published")
        self.assertFalse(self.output.exists())
        self.assertEqual(self.tree(self.store), original)

    def test_cli_read_failure_keeps_restore_without_suggesting_archive_resume(self):
        original = self.tree(self.store)
        args = [value for key, value in self.arguments.items()
                for value in ("--" + key.replace("_", "-"), str(value))]
        stream = io.StringIO()
        with mock.patch.object(consumer, "_load_version", side_effect=OSError("read failed")), \
                redirect_stdout(stream):
            self.assertEqual(consumer.main(["read-snapshot", *args]), 1)
        response = json.loads(stream.getvalue())
        self.assertEqual(response["commit_state"], "not_applicable")
        self.assertIn("Snapshot read failed", response["message"])
        self.assertNotIn("reconcile the original request", response["message"])
        self.assertTrue((self.output / "snapshot-receipt/restore.json").is_file())
        self.assertFalse((self.output / "read-receipt").exists())
        self.assertEqual(self.tree(self.store), original)
        self.assertTrue(self.read(output=self.root / "retry-cli-read")["content_verified"])

    def test_storage_error_fields_survive_cli_and_binding_reaches_adapter(self):
        # Adapter boundary only; this mock is not NAS qualification.
        config = {"storage_ref": "test:private-binding"}
        config_path = self.root / "storage.json"
        config_path.write_bytes(consumer._json(config))
        error = self.recovery.RecoveryError("UNSUPPORTED_STORAGE", "Storage binding differs.",
                                            "validate", "not_published")
        args = [value for key, value in self.arguments.items()
                for value in ("--" + key.replace("_", "-"), str(value))]
        stream = io.StringIO()
        with mock.patch.object(self.recovery, "restore", side_effect=error) as restore, redirect_stdout(stream):
            self.assertEqual(consumer.main(["read-snapshot", *args, "--storage-config", str(config_path)]), 1)
        self.assertEqual(restore.call_args.kwargs["storage_config"], config)
        response = json.loads(stream.getvalue())
        self.assertEqual(response["code"], "UNSUPPORTED_STORAGE")
        self.assertEqual(response["commit_state"], "not_applicable")
        self.assertEqual(response["publication_state"], "not_published")
        self.assertEqual(response["stage"], "validate")
        self.assertEqual(response["message"], "Storage binding differs.")
        self.assertFalse(self.output.exists())

    def test_changed_restored_database_is_rejected_before_evidence_publication(self):
        load_version = consumer._load_version
        def changed(*args):
            files = load_version(*args)
            with (self.output / "ledger.sqlite").open("ab") as stream:
                stream.write(b"changed")
            return files
        with mock.patch.object(consumer, "_load_version", side_effect=changed):
            with self.assertRaises(consumer.ArchiveError) as caught:
                self.read()
        self.assertEqual(caught.exception.code, "INTEGRITY_FAILURE")
        self.assertFalse((self.output / "evidence").exists())
