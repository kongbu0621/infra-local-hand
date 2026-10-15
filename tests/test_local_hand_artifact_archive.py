"""Optional consumer integration against the installed public Ledger library."""
import hashlib
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from local_hand_jobs import artifact_archive as consumer

HAS_LEDGER = importlib.util.find_spec("infra_artifact_ledger") is not None
if sys.platform == "linux":
    from local_hand_jobs.evidence import EvidenceError
    from local_hand_jobs.evidence_client import verify_local_bundle
    from test_local_hand_jobs_evidence import EvidenceFixture, OP


class BundleFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = EvidenceFixture(self.root)
        self.descriptor = self.fixture.sealed()
        sealed = self.fixture.store.root / self.descriptor["seal_id"]
        self.evidence = self.root / "downloaded"
        self.evidence.mkdir()
        self.raw = {name: (sealed / stored).read_bytes() for name, stored in
                    (("evidence.zip", "evidence.zip"), ("evidence.manifest", "manifest.json"),
                     ("evidence.seal", "seal.json"))}
        for name, raw in self.raw.items():
            (self.evidence / name).write_bytes(raw)

    def verify(self, files):
        return verify_local_bundle(files["evidence.zip"], files["evidence.manifest"], files["evidence.seal"],
            operation_id=OP, seal_id=self.descriptor["seal_id"], seal_sha256=self.descriptor["seal_sha256"])


@unittest.skipUnless(sys.platform == "linux", "Linux local evidence consumer")
class LocalBundleTests(BundleFixture, unittest.TestCase):
    def test_retained_bundle_and_each_changed_artifact(self):
        self.assertEqual(self.verify(self.raw)["operation_id"], OP)
        for name in self.raw:
            with self.subTest(name=name):
                changed = dict(self.raw)
                changed[name] += b"x"
                with self.assertRaises(EvidenceError):
                    self.verify(changed)

    def test_wrong_operation_and_expansion_budget_rejected(self):
        with self.assertRaises(EvidenceError):
            verify_local_bundle(*[self.raw[n] for n in ("evidence.zip", "evidence.manifest", "evidence.seal")],
                operation_id="another-task", seal_id=self.descriptor["seal_id"],
                seal_sha256=self.descriptor["seal_sha256"])
        with self.assertRaises(EvidenceError):
            verify_local_bundle(*[self.raw[n] for n in ("evidence.zip", "evidence.manifest", "evidence.seal")],
                operation_id=OP, seal_id=self.descriptor["seal_id"],
                seal_sha256=self.descriptor["seal_sha256"], maximum=1)


@unittest.skipUnless(sys.platform == "linux" and HAS_LEDGER, "Install verified optional Ledger wheel for integration")
class ArchiveTests(BundleFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        import infra_artifact_ledger
        self.api = infra_artifact_ledger
        self.store = self.root / "archive"
        self.status = dict(operation_id=OP, request_digest="a" * 64,
            lifecycle="TERMINAL", phase="EXITED", outcome="SUCCEEDED", evidence="SEALED",
            observed_at=1.5, seal_refs=[{key: self.descriptor[key] for key in ("seal_id", "seal_sha256")}])
        self.status_path = self.root / "status.json"
        self.save_status()

    def save_status(self):
        self.status_path.write_bytes(consumer._json(self.status))
        self.digest = hashlib.sha256(self.status_path.read_bytes()).hexdigest()

    def archive(self):
        return consumer.archive_result(self.store, producer="test:local-hand", status_path=self.status_path,
                                       status_sha256=self.digest, evidence_dir=self.evidence)

    def resume(self):
        return consumer.resume_archive(self.store, producer="test:local-hand", operation_id=OP)

    def read(self, result, name="restored"):
        return consumer.read_version(self.store, artifact_id=result["artifact_id"],
                                     version_id=result["version_id"], output=self.root / name)

    def verification(self):
        with self.api.open(self.store / "ledger.sqlite") as ledger:
            return ledger.verify()

    def test_archive_restart_precise_read_and_retry_without_original_inputs(self):
        result = self.archive()
        self.assertFalse(result["reused"])
        counts = self.verification()
        self.assertEqual(counts["counts"]["versions"], 1)
        self.assertEqual(counts["counts"]["idempotency_records"], 2)
        shutil.rmtree(self.fixture.store.root)
        shutil.rmtree(self.evidence)
        self.status_path.unlink()
        arguments = ["read", "--store", str(self.store), "--artifact-id", result["artifact_id"],
                     "--version-id", result["version_id"], "--output", str(self.root / "reopened")]
        # A genuinely new interpreter uses the same public command. It receives
        # no callback and has neither original inputs nor an executing service.
        script = "import sys; sys.path.insert(0, sys.argv.pop(1)); from local_hand_jobs.artifact_archive import main; raise SystemExit(main())"
        output = subprocess.run([sys.executable, "-I", "-B", "-c", script,
            str(Path(consumer.__file__).parents[1]), *arguments], capture_output=True, timeout=30)
        self.assertEqual(output.returncode, 0, output.stdout + output.stderr)
        self.assertTrue(json.loads(output.stdout)["content_verified"])
        for name, raw in self.raw.items():
            self.assertEqual((self.root / "reopened" / name).read_bytes(), raw)
        recovered = self.resume()
        self.assertTrue(recovered["reused"])
        self.assertEqual((recovered["artifact_id"], recovered["version_id"], recovered["recorded_at"]),
                         (result["artifact_id"], result["version_id"], result["recorded_at"]))
        self.assertEqual(self.verification(), counts)

    def test_lost_response_after_either_commit_reconciles_original_requests(self):
        original = consumer._ensure_operation
        for kind in ("create_artifact", "append_version"):
            self.store = self.root / kind
            def lose_response(ledger, raw, **kwargs):
                result = original(ledger, raw, **kwargs)
                if json.loads(raw)["operation_kind"] == kind:
                    raise OSError("response lost after commit")
                return result
            with mock.patch.object(consumer, "_ensure_operation", side_effect=lose_response):
                with self.assertRaises(OSError):
                    self.archive()
            staged = next(self.store.glob("task-*"))
            requests = {name: (staged / name).read_bytes() for name in ("create.json", "append.json")}
            result = self.resume()
            self.read(result, name=kind + "-read")
            self.assertEqual(self.verification()["counts"]["versions"], 1)
            self.assertEqual(self.verification()["counts"]["idempotency_records"], 2)
            self.assertEqual(requests, {name: (staged / name).read_bytes() for name in requests})

    def test_read_failure_after_append_can_retry_without_another_write(self):
        with mock.patch.object(consumer, "_load_version", side_effect=OSError("temporary read failure")):
            with self.assertRaises(OSError):
                self.archive()
        counts = self.verification()
        with self.api.open(self.store / "ledger.sqlite") as handle:
            ledger_type = type(handle)
        with mock.patch.object(ledger_type, "execute", side_effect=AssertionError("must reuse commits")):
            self.assertTrue(self.resume()["content_verified"])
        self.assertEqual(self.verification(), counts)

    def test_known_commit_with_damaged_payload_never_returns_success_or_repairs(self):
        result = self.archive()
        # Deliberate offline corruption of this test's private database.
        with sqlite3.connect(self.store / "ledger.sqlite") as connection:
            columns = connection.execute("PRAGMA table_info(payloads)").fetchall()
            data_column = next(row[1] for row in columns if row[1] != "blob_ref")
            connection.execute('UPDATE payloads SET "' + data_column + '" = ?', (b"damaged",))
        for call in (self.resume, lambda: self.read(result)):
            with self.assertRaises(self.api.LedgerError) as error:
                call()
            self.assertEqual(error.exception.code, "INTEGRITY_FAILURE")
        self.assertFalse((self.root / "restored").exists())
        with self.api.open(self.store / "ledger.sqlite") as ledger:
            request = json.loads(next(self.store.glob("task-*/append.json")).read_bytes())
            record = ledger.get_operation(request["idempotency_scope_ref"], "append_version", "append")
            self.assertEqual(record["idempotency_record"]["result_ref"], result["version_id"])

    def test_changed_status_observation_reuses_original_snapshot(self):
        first = self.archive()
        self.status["observed_at"] = 2.5
        self.save_status()
        second = self.archive()
        self.assertEqual(first["version_id"], second["version_id"])
        self.assertTrue(second["reused"])
        self.assertEqual(second["files"]["status.json"], first["files"]["status.json"])

    def test_changed_request_binding_rejected_without_changing_history(self):
        self.archive()
        counts = self.verification()
        self.status["request_digest"] = "b" * 64
        self.save_status()
        with self.assertRaises(consumer.ArchiveError):
            self.archive()
        self.assertEqual(self.verification(), counts)

    def test_unknown_running_unsealed_or_wrong_trusted_digest_rejected_before_staging(self):
        original = dict(self.status)
        for key, value in (("outcome", "UNKNOWN"), ("lifecycle", "RUNNING"),
                           ("phase", "BUSINESS"), ("evidence", "STAGING")):
            self.status = dict(original, **{key: value})
            self.save_status()
            with self.assertRaises(consumer.ArchiveError):
                self.archive()
            self.assertFalse(self.store.exists())
        self.status = original
        self.save_status()
        self.digest = "0" * 64
        with self.assertRaises(consumer.ArchiveError):
            self.archive()
        self.assertFalse(self.store.exists())

    def test_wrong_task_seal_or_tool_error_cannot_be_archived(self):
        self.status["operation_id"] = "another-task"
        self.save_status()
        with self.assertRaises(EvidenceError):
            self.archive()
        self.status = dict(structuredContent=self.status, isError=True)
        self.save_status()
        with self.assertRaises(consumer.ArchiveError):
            self.archive()
        self.assertFalse(self.store.exists())

    def test_output_conflict_or_wrong_artifact_preserves_existing_files(self):
        result = self.archive()
        self.read(result)
        original = (self.root / "restored" / "evidence.zip").read_bytes()
        with self.assertRaises(OSError):
            self.read(result)
        self.assertEqual((self.root / "restored" / "evidence.zip").read_bytes(), original)
        with self.assertRaises(self.api.LedgerError):
            self.read(dict(result, artifact_id="artifact:wrong"), "wrong")
        self.assertFalse((self.root / "wrong").exists())

    def test_changed_journal_cannot_replace_original_request(self):
        self.archive()
        counts = self.verification()
        next(self.store.glob("task-*/append.json")).write_bytes(b"{}")
        with self.assertRaises(consumer.ArchiveError):
            self.resume()
        self.assertEqual(self.verification(), counts)

    def test_missing_database_is_not_recreated(self):
        self.archive()
        (self.store / "ledger.sqlite").rename(self.root / "retained.sqlite")
        with self.assertRaises(consumer.ArchiveError):
            self.resume()
        self.assertFalse((self.store / "ledger.sqlite").exists())

    def test_missing_recovery_directory_cannot_create_a_second_version(self):
        first = self.archive()
        counts = self.verification()
        journal = next(self.store.glob("task-*"))
        retained = self.root / "retained-request"
        journal.rename(retained)
        reservation = next(self.store.glob("request-task-*"))
        for lose_reservation in (False, True):
            if lose_reservation:
                reservation.rename(self.root / "retained-reservation")
            with self.assertRaises(consumer.ArchiveError):
                self.archive()
            self.assertFalse(journal.exists())
            self.assertEqual(self.verification(), counts)
        retained.rename(journal)
        recovered = self.resume()
        self.assertTrue(recovered["reused"])
        self.assertEqual(recovered["recorded_at"], first["recorded_at"])

    def test_missing_recovery_directory_after_create_commit_cannot_allocate_new_identity(self):
        original = consumer._ensure_operation
        def lose_create(ledger, raw, **kwargs):
            original(ledger, raw, **kwargs)
            raise OSError("lost create response")
        with mock.patch.object(consumer, "_ensure_operation", side_effect=lose_create):
            with self.assertRaises(OSError):
                self.archive()
        counts = self.verification()
        self.assertEqual(counts["counts"]["artifacts"], 1)
        self.assertEqual(counts["counts"]["versions"], 0)
        for pattern in ("task-*", "request-task-*"):
            path = next(self.store.glob(pattern))
            path.rename(self.root / path.name)
        with self.assertRaises(consumer.ArchiveError):
            self.archive()
        self.assertEqual(self.verification(), counts)
        for path in self.root.glob("task-*"):
            path.rename(self.store / path.name)
        self.assertEqual(self.resume()["status"], "ARCHIVED")
        self.assertEqual(self.verification()["counts"]["artifacts"], 1)

    def test_replaced_database_is_not_replayed_and_original_can_resume(self):
        first = self.archive()
        original = self.root / "original.sqlite"
        database = self.store / "ledger.sqlite"
        database.rename(original)
        self.api.initialize(database).close()
        empty = self.verification()
        for call in (self.resume, self.archive, lambda: self.read(first)):
            with self.assertRaises(consumer.ArchiveError):
                call()
            self.assertEqual(self.verification(), empty)
        database.rename(self.root / "replacement.sqlite")
        original.rename(database)
        recovered = self.resume()
        self.assertTrue(recovered["reused"])
        self.assertEqual(recovered["recorded_at"], first["recorded_at"])
        self.read(first)

    def test_reservation_publication_failure_can_resume_without_a_prior_write(self):
        original = consumer._publish_files
        def interrupted(parent, name, files):
            original(parent, name, files)
            if name.startswith("request-task-"):
                raise OSError("reservation visible but sync/return failed")
        with mock.patch.object(consumer, "_publish_files", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.archive()
        self.assertEqual(self.verification()["counts"]["artifacts"], 0)
        self.assertEqual(self.resume()["status"], "ARCHIVED")
        self.assertEqual(self.verification()["counts"]["versions"], 1)

    def test_same_operation_from_distinct_producers_has_separate_identity(self):
        first = self.archive()
        second = consumer.archive_result(self.store, producer="test:other-instance",
            status_path=self.status_path, status_sha256=self.digest, evidence_dir=self.evidence)
        self.assertNotEqual(first["artifact_id"], second["artifact_id"])
        self.assertNotEqual(first["version_id"], second["version_id"])
        self.assertEqual(self.verification()["counts"]["versions"], 2)
        self.assertTrue(self.resume()["reused"])
        self.read(second)

    def test_legacy_requests_and_database_remain_readable_without_rewriting_history(self):
        files = dict(self.raw, **{"status.json": self.status_path.read_bytes()})
        files["source.json"] = consumer._json(consumer._source(files, "test:local-hand", self.digest))
        binding = dict(schema_version="lh-artifact-request-v1", producer="test:local-hand",
                       operation_id=OP, status_sha256=self.digest, token="c" * 32)
        create, append, payloads = consumer._requests(binding, files)
        with consumer._locked_store(self.store, create=True):
            consumer._publish_files(self.store, consumer._task_name("test:local-hand", OP),
                dict(files, **{"binding.json": consumer._json(binding), "create.json": create, "append.json": append}))
            consumer._publish_files(self.store, "database-initialized", {
                "format.json": consumer._json(dict(schema_version="lh-artifact-store-v1"))})
            with self.api.initialize(self.store / "ledger.sqlite") as ledger:
                consumer._ensure_operation(ledger, create)
                appended = consumer._ensure_operation(ledger, append, payloads=payloads)
                ledger_type = type(ledger)
        original_files = {path: path.read_bytes() for path in self.store.rglob("*") if path.is_file()}
        counts = self.verification()
        with mock.patch.object(ledger_type, "execute", side_effect=AssertionError("must not rewrite history")):
            recovered = self.resume()
            self.read(recovered)
        self.assertEqual(recovered["recorded_at"], appended["recorded_at"])
        self.assertEqual(self.verification(), counts)
        self.assertEqual(original_files, {path: path.read_bytes() for path in original_files})
        self.assertTrue((self.store / "database-initialized/database-identity/identity.json").is_file())
        # The independent reservation also protects older token-scoped requests.
        next(self.store.glob("task-*")).rename(self.root / "legacy-request")
        with self.assertRaises(consumer.ArchiveError):
            self.archive()
        self.assertEqual(self.verification(), counts)

    def test_interruption_after_request_publication_preserves_ids_before_any_ledger_write(self):
        original = consumer._publish_files
        def interrupted(parent, name, files):
            original(parent, name, files)
            if name.startswith("task-"):
                raise OSError("request directory visible, response lost")
        with mock.patch.object(consumer, "_publish_files", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.archive()
        self.assertFalse((self.store / "ledger.sqlite").exists())
        request = json.loads(next(self.store.glob("task-*/append.json")).read_bytes())
        result = self.resume()
        self.assertEqual(result["version_id"], request["body"]["version"]["version_id"])
        self.assertEqual(self.verification()["counts"]["versions"], 1)

    def test_conflicting_committed_request_is_not_accepted_by_metadata_query(self):
        self.archive()
        request = json.loads(next(self.store.glob("task-*/create.json")).read_bytes())
        request["body"]["artifact"]["type_ref"]["type_version"] = "2"
        counts = self.verification()
        with self.api.open(self.store / "ledger.sqlite") as ledger:
            with self.assertRaises(consumer.ArchiveError) as error:
                consumer._ensure_operation(ledger, consumer._json(request))
            self.assertEqual(error.exception.code, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.verification(), counts)

    def test_oversize_input_rejected_before_creating_store(self):
        with mock.patch.dict(consumer.LIMITS, {"evidence.zip": 1}):
            with self.assertRaises(consumer.LocalHandError):
                self.archive()
        self.assertFalse(self.store.exists())

    def test_workspace_source_and_before_after_are_bound_to_sealed_members(self):
        for valid in (True, False):
            case = self.root / ("valid" if valid else "invalid")
            case.mkdir()
            fixture = EvidenceFixture(case)
            business = fixture.source / "business"
            business.mkdir(mode=0o700)
            before, after = b"old\n", b"new\n"
            result = dict(schema_version="lh-workspace-edit-v1", scope="TASK_OWNED_COPY",
                source_ref="project:test", source_commit="a" * 40, relative_path="hello.txt",
                validation_ref="core", original_modified=False, read_back_verified=True,
                validation_succeeded=True, edited_file_unchanged_by_validation=True,
                before_sha256=consumer._sha(before) if valid else "0" * 64,
                after_sha256=consumer._sha(after))
            members = {"workspace-result.json": consumer._json(result),
                       "workspace-before.txt": before, "workspace-after.txt": after}
            for name, raw in members.items():
                (business / name).write_bytes(raw)
                (business / name).chmod(0o600)
            fixture.snapshot = replace(fixture.snapshot,
                members=("stdout.log", *("business/" + n for n in members)))
            descriptor = fixture.sealed()
            sealed = fixture.store.root / descriptor["seal_id"]
            status = dict(self.status, seal_refs=[{k: descriptor[k] for k in ("seal_id", "seal_sha256")}])
            files = {"status.json": consumer._json(status), "evidence.zip": (sealed / "evidence.zip").read_bytes(),
                     "evidence.manifest": (sealed / "manifest.json").read_bytes(),
                     "evidence.seal": (sealed / "seal.json").read_bytes()}
            if valid:
                source = consumer._source(files, "test:instance", consumer._sha(files["status.json"]))
                self.assertEqual(source["workspace"]["source_commit"], "a" * 40)
            else:
                with self.assertRaises(consumer.ArchiveError):
                    consumer._source(files, "test:instance", consumer._sha(files["status.json"]))

    def test_concurrent_consumer_is_bounded_and_lock_released_after_failure(self):
        with consumer._locked_store(self.store, create=True):
            with self.assertRaises(consumer.ArchiveError) as raised:
                self.archive()
            self.assertEqual(raised.exception.code, "BUSY")
        self.assertEqual(self.archive()["status"], "ARCHIVED")

    def test_store_symlink_and_symlinked_input_rejected(self):
        destination = self.root / "destination"
        destination.mkdir()
        self.store.symlink_to(destination, target_is_directory=True)
        with self.assertRaises(OSError):
            self.archive()
        self.assertEqual(list(destination.iterdir()), [])
        self.store.unlink()
        self.status_path.rename(self.root / "original-status.json")
        self.status_path.symlink_to(self.root / "original-status.json")
        with self.assertRaises(consumer.LocalHandError):
            self.archive()
        self.assertFalse(self.store.exists())


if __name__ == "__main__":
    unittest.main()
