"""Optional consumer integration against the installed public Ledger library."""
import hashlib
from contextlib import redirect_stdout
from dataclasses import replace
import importlib.util
import io
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

    def test_initialization_guard_failure_can_resume_an_empty_database(self):
        publish = consumer._publish_files
        def interrupted(parent, name, files):
            if name == "database-initialized":
                raise OSError("interrupted before initialization guard publication")
            return publish(parent, name, files)
        with mock.patch.object(consumer, "_publish_files", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.archive()
        self.assertFalse((self.store / "database-initialized").exists())
        self.assertTrue((self.store / "ledger.sqlite").is_file())
        self.assertEqual(self.verification()["counts"]["idempotency_records"], 0)
        result = self.resume()
        self.assertEqual(result["status"], "ARCHIVED")
        self.assertEqual(self.verification()["counts"]["idempotency_records"], 2)
        self.assertEqual(consumer.recovery_checkpoint(self.store)["status"], "RECOVERY_CHECKPOINT")

    def legacy_device_number(self, *, version=2):
        """Model a prior boot's device number; keep the actual DB inode/bytes."""
        marker = self.store / "database-initialized"
        identity = consumer._database_identity(self.store / "ledger.sqlite")
        identity = dict(identity, device=identity["device"] + 1)
        if version == 1:
            (marker / "format.json").write_bytes(consumer._json(dict(schema_version="lh-artifact-store-v1")))
            (marker / "database-identity").mkdir(mode=0o700)
            (marker / "database-identity/identity.json").write_bytes(consumer._json(identity))
        else:
            (marker / "format.json").write_bytes(consumer._json(dict(
                schema_version="lh-artifact-store-v2", database_identity=identity)))
        for reservation in self.store.glob("request-task-*"):
            saved = json.loads((reservation / "identity.json").read_bytes())
            saved["database_identity"] = identity
            (reservation / "identity.json").write_bytes(consumer._json(saved))
        return hashlib.sha256((self.store / "ledger.sqlite").read_bytes()).hexdigest()

    def test_new_store_survives_device_renumbering_but_rejects_other_filesystem(self):
        first = self.archive()
        physical = consumer._physical_database_identity(self.store / "ledger.sqlite")
        with mock.patch.object(consumer, "_physical_database_identity",
                               return_value=dict(physical, device=physical["device"] + 1)):
            self.assertTrue(self.read(first)["content_verified"])
            self.assertTrue(self.resume()["reused"])
        with mock.patch.object(consumer, "_physical_database_identity",
                               return_value=dict(physical, filesystem_id=physical["filesystem_id"] + 1)):
            with self.assertRaises(consumer.ArchiveError):
                self.read(first, "wrong-fs")

    def test_new_store_missing_filesystem_binding_cannot_silently_rebind(self):
        first = self.archive()
        path = self.store / "database-initialized/format.json"
        value = json.loads(path.read_bytes()); value.pop("filesystem_binding")
        path.write_bytes(consumer._json(value))
        with self.assertRaises(consumer.ArchiveError):
            self.read(first)

    def test_legacy_trusted_binding_preserves_records_and_restores_exact_read_resume(self):
        for version in (1, 2):
            with self.subTest(version=version):
                self.store = self.root / ("legacy-" + str(version))
                first = self.archive()
                checkpoint = self.legacy_device_number(version=version)
                before = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
                with self.assertRaises(consumer.ArchiveError):
                    self.read(first, "not-bound-" + str(version))
                with mock.patch.object(self.api, "initialize", side_effect=AssertionError("must not initialize")):
                    result = consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
                self.assertFalse(result["reused"])
                self.assertEqual(result["ledger_writes"], 0)
                self.assertTrue(consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)["reused"])
                self.assertTrue(self.read(first, "bound-" + str(version))["content_verified"])
                resumed = self.resume()
                self.assertEqual(resumed["version_id"], first["version_id"])
                self.assertEqual(resumed["recorded_at"], first["recorded_at"])
                self.assertTrue(resumed["reused"])
                for path, raw in before.items():
                    self.assertEqual(path.read_bytes(), raw, str(path))

    def test_legacy_binding_rejects_wrong_checkpoint_replacement_and_sidecars(self):
        self.archive()
        checkpoint = self.legacy_device_number()
        before = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
        with self.assertRaises(consumer.ArchiveError):
            consumer.bind_filesystem(self.store, expected_database_sha256="0" * 64)
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(self.store / "ledger.sqlite") + suffix)
            sidecar.symlink_to(self.root / "missing")
            with self.assertRaises(consumer.ArchiveError):
                consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
            sidecar.unlink()
        path = self.store / "ledger.sqlite"
        path.rename(self.root / "original-database")
        shutil.copy2(self.root / "original-database", path)
        with self.assertRaises(consumer.ArchiveError):
            consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
        self.assertFalse((self.store / "database-initialized/filesystem-binding").exists())
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw)

    def test_legacy_binding_rejects_missing_confirmed_operation_without_replay(self):
        original = self.store / "ledger.sqlite"
        # Keep a valid empty DB checkpoint, then roll back only its bytes after
        # archiving. A matching caller hash must not overrule an external receipt.
        self.store.mkdir(mode=0o700)
        with self.api.initialize(original):
            pass
        empty = original.read_bytes()
        self.archive()
        self.legacy_device_number()
        original.write_bytes(empty)
        checkpoint = hashlib.sha256(empty).hexdigest()
        with self.assertRaises(consumer.ArchiveError):
            consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
        self.assertEqual(original.read_bytes(), empty)
        self.assertFalse((self.store / "database-initialized/filesystem-binding").exists())

    def test_filesystem_binding_cli_in_a_separate_process(self):
        first = self.archive()
        checkpoint = self.legacy_device_number()
        script = "import sys;sys.path.insert(0,sys.argv.pop(1));from local_hand_jobs.artifact_archive import main;raise SystemExit(main())"
        result = subprocess.run([sys.executable, "-I", "-B", "-c", script,
            str(Path(consumer.__file__).parents[1]), "bind-filesystem", "--store", str(self.store),
            "--expected-database-sha256", checkpoint], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "FILESYSTEM_BOUND")
        self.assertTrue(self.read(first)["content_verified"])

    def test_filesystem_binding_rejects_crosswired_requests_without_receipt_writes(self):
        for missing_append_receipt in (False, True):
            with self.subTest(missing_append_receipt=missing_append_receipt):
                self.store = self.root / ("crosswired-" + str(missing_append_receipt))
                self.archive()
                checkpoint = self.legacy_device_number()
                task = next(self.store.glob("task-*"))
                reservation = next(self.store.glob("request-task-*"))
                # The DB is intact, but a copied append request occupies the
                # create slot. Its claimed kind must not select another receipt.
                (task / "create.json").write_bytes((task / "append.json").read_bytes())
                if missing_append_receipt:
                    (reservation / "append_version").rename(self.root / "saved-append-receipt")
                before = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
                with self.assertRaises(consumer.ArchiveError):
                    consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
                self.assertEqual(before, {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()})

    def test_filesystem_binding_checks_create_implied_by_append_receipt(self):
        self.archive()
        self.legacy_device_number()
        reservation = next(self.store.glob("request-task-*"))
        (reservation / "create_artifact").rename(self.root / "saved-create-receipt")
        database = self.store / "ledger.sqlite"
        with sqlite3.connect(database) as connection:
            connection.execute("DELETE FROM operations WHERE kind='create_artifact'")
        # Valid Ledger structure alone does not prove the consumer's original
        # create exists: imported records need not have a local create operation.
        self.verification()
        before = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
        with self.assertRaises(consumer.ArchiveError):
            consumer.bind_filesystem(self.store,
                expected_database_sha256=hashlib.sha256(database.read_bytes()).hexdigest())
        self.assertEqual(before, {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()})

    def test_filesystem_binding_rejects_requests_from_another_task(self):
        for case in ("create_artifact", "append_version", "implied-create"):
            with self.subTest(case=case):
                self.store = self.root / ("foreign-request-" + case)
                self.archive()
                consumer.archive_result(self.store, producer="test:another-hand", status_path=self.status_path,
                    status_sha256=self.digest, evidence_dir=self.evidence)
                self.legacy_device_number()
                task = self.store / consumer._task_name("test:local-hand", OP)
                other = self.store / consumer._task_name("test:another-hand", OP)
                reservation = self.store / ("request-" + task.name)
                other_reservation = self.store / ("request-" + other.name)
                kind = "create_artifact" if case == "implied-create" else case
                filename = "create.json" if kind == "create_artifact" else "append.json"
                original = json.loads((task / filename).read_bytes())
                (task / filename).write_bytes((other / filename).read_bytes())
                if case == "implied-create":
                    (reservation / kind).rename(self.root / "saved-implied-create-receipt")
                    with sqlite3.connect(self.store / "ledger.sqlite") as connection:
                        connection.execute("DELETE FROM operations WHERE scope=? AND kind=? AND key=?",
                            (original["idempotency_scope_ref"], kind, original["idempotency_key"]))
                else:
                    (reservation / kind / "commit.json").write_bytes(
                        (other_reservation / kind / "commit.json").read_bytes())
                # Each substituted request/receipt pair is valid for the other
                # task; neither may establish this task's original history.
                self.verification()
                before = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
                with self.assertRaises(consumer.ArchiveError):
                    consumer.bind_filesystem(self.store,
                        expected_database_sha256=hashlib.sha256((self.store / "ledger.sqlite").read_bytes()).hexdigest())
                self.assertEqual(before, {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()})

    def test_filesystem_binding_rejects_changed_mapping_and_allows_repaired_retry(self):
        self.archive()
        checkpoint = self.legacy_device_number()
        task = next(self.store.glob("task-*"))
        reservation = next(self.store.glob("request-task-*"))
        mapping = task / "binding.json"
        guard = reservation / "identity.json"
        original_mapping, original_guard = mapping.read_bytes(), guard.read_bytes()
        for field, value in (("token", "f" * 32), ("schema_version", "unknown"),
                             ("status_sha256", "not-a-digest"), ("token", None)):
            with self.subTest(field=field, value=value):
                changed = dict(json.loads(original_mapping), **{field: value})
                mapping.write_bytes(consumer._json(changed))
                guard.write_bytes(consumer._json(dict(json.loads(original_guard), binding=changed)))
                before = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
                with self.assertRaises(consumer.ArchiveError):
                    consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
                self.assertEqual(before, {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()})
        mapping.write_bytes(original_mapping)
        guard.write_bytes(original_guard)
        self.assertFalse(consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)["reused"])
        self.assertTrue(self.resume()["reused"])

    def test_filesystem_binding_requires_original_reservation_bytes(self):
        for version in (1, 2):
            for mutation in ("whitespace", "extra-field", "device-type", "inode-type"):
                with self.subTest(version=version, mutation=mutation):
                    self.store = self.root / ("reservation-" + str(version) + "-" + mutation)
                    first = self.archive()
                    checkpoint = self.legacy_device_number(version=version)
                    guard = next(self.store.glob("request-task-*")) / "identity.json"
                    original = guard.read_bytes()
                    changed = json.loads(original)
                    if mutation == "whitespace":
                        raw = original + b"\n"
                    elif mutation == "extra-field":
                        raw = consumer._json(dict(changed, extra=True))
                    else:
                        field = mutation.removesuffix("-type")
                        changed["database_identity"][field] = float(changed["database_identity"][field])
                        raw = consumer._json(changed)
                    guard.write_bytes(raw)
                    before = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
                    with self.api.open(self.store / "ledger.sqlite") as ledger:
                        ledger_type = type(ledger)
                    with mock.patch.object(ledger_type, "execute", side_effect=AssertionError("binding cannot replay")):
                        with self.assertRaises(consumer.ArchiveError) as denied:
                            consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
                        self.assertEqual(denied.exception.code, "INTEGRITY_FAILURE")
                        self.assertEqual(before, {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()})
                        guard.write_bytes(original)
                        self.assertFalse(consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)["reused"])
                        self.assertTrue(consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)["reused"])
                        resumed = self.resume()
                    self.assertTrue(resumed["reused"])
                    self.assertEqual((first["artifact_id"], first["version_id"], first["recorded_at"]),
                                     (resumed["artifact_id"], resumed["version_id"], resumed["recorded_at"]))
                    self.assertEqual(original, guard.read_bytes())
                    self.assertEqual(checkpoint, hashlib.sha256((self.store / "ledger.sqlite").read_bytes()).hexdigest())

    def test_existing_filesystem_binding_still_checks_original_reservation_bytes(self):
        self.archive()
        checkpoint = self.legacy_device_number()
        consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
        guard = next(self.store.glob("request-task-*")) / "identity.json"
        original = guard.read_bytes()
        guard.write_bytes(original + b"\n")
        before = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
        with self.assertRaises(consumer.ArchiveError) as denied:
            consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
        self.assertEqual(denied.exception.code, "INTEGRITY_FAILURE")
        self.assertEqual(before, {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()})
        guard.write_bytes(original)
        self.assertTrue(consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)["reused"])
        self.assertTrue(self.resume()["reused"])

    def test_filesystem_binding_preserves_partial_archives_and_missing_receipts(self):
        for state in ("create-only", "missing-create-receipt", "missing-append-receipt"):
            with self.subTest(state=state):
                self.store = self.root / state
                if state == "create-only":
                    ensure = consumer._ensure_operation
                    def stop_after_create(ledger, raw, **kwargs):
                        result = ensure(ledger, raw, **kwargs)
                        if json.loads(raw)["operation_kind"] == "create_artifact":
                            raise OSError("interrupted before append")
                        return result
                    with mock.patch.object(consumer, "_ensure_operation", side_effect=stop_after_create):
                        with self.assertRaises(OSError):
                            self.archive()
                else:
                    self.archive()
                    reservation = next(self.store.glob("request-task-*"))
                    kind = "create_artifact" if state == "missing-create-receipt" else "append_version"
                    (reservation / kind).rename(self.root / ("saved-" + state))
                checkpoint = self.legacy_device_number()
                before = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
                with self.api.open(self.store / "ledger.sqlite") as ledger:
                    ledger_type = type(ledger)
                with mock.patch.object(ledger_type, "execute", side_effect=AssertionError("verification cannot execute")):
                    result = consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
                self.assertEqual(result["ledger_writes"], 0)
                after = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
                binding_file = self.store / "database-initialized/filesystem-binding/identity.json"
                self.assertEqual(set(after) - set(before), {binding_file})
                self.assertEqual(before, {p: raw for p, raw in after.items() if p != binding_file})

    def test_filesystem_binding_publication_failure_retries_without_replay(self):
        from local_hand_jobs import evidence
        for after_rename in (False, True):
            with self.subTest(after_rename=after_rename):
                self.store = self.root / ("publish-" + str(after_rename))
                first = self.archive()
                checkpoint = self.legacy_device_number()
                before = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
                publish = evidence._publish_create_only
                def interrupted(source, target):
                    if after_rename:
                        publish(source, target)
                    raise OSError("filesystem binding publication interrupted")
                with mock.patch.object(evidence, "_publish_create_only", side_effect=interrupted):
                    with self.assertRaises(OSError):
                        consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
                failed = {p: p.read_bytes() for p in self.store.rglob("*") if p.is_file()}
                with self.api.open(self.store / "ledger.sqlite") as ledger:
                    ledger_type = type(ledger)
                with mock.patch.object(ledger_type, "execute", side_effect=AssertionError("retry cannot execute")):
                    result = consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)
                self.assertEqual(result["reused"], after_rename)
                for path, raw in before.items():
                    self.assertEqual(path.read_bytes(), raw)
                for path, raw in failed.items():
                    self.assertEqual(path.read_bytes(), raw)
                self.assertTrue(self.read(first, "publication-read-" + str(after_rename))["content_verified"])

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

    def test_cli_reports_safe_directory_error_and_allows_corrected_read(self):
        result = self.archive()
        counts = self.verification()
        parent = self.root / "read-output"
        parent.mkdir()
        parent.chmod(0o775)
        args = ["read", "--store", str(self.store), "--artifact-id", result["artifact_id"],
                "--version-id", result["version_id"], "--output", str(parent / "readback")]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(consumer.main(args), 1)
        error = json.loads(output.getvalue())
        self.assertEqual(error["code"], "CONFLICT")
        self.assertIn("directory is not protected", error["message"])
        self.assertNotIn(str(self.root), output.getvalue())
        self.assertFalse((parent / "readback").exists())
        parent.chmod(0o700)
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(consumer.main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "READ")
        self.assertEqual(self.verification(), counts)

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

    def test_reservation_checks_missing_global_marker_before_database_mutation(self):
        for replacement in (False, True):
            with self.subTest(replacement=replacement):
                self.store = self.root / ("missing" if not replacement else "replaced")
                first = self.archive()
                database = self.store / "ledger.sqlite"
                marker = self.store / "database-initialized"
                saved_database = self.root / (self.store.name + ".sqlite")
                saved_marker = self.root / (self.store.name + "-marker")
                database.rename(saved_database)
                marker.rename(saved_marker)
                if replacement:
                    self.api.initialize(database).close()
                before = {path: path.read_bytes() for path in self.store.rglob("*") if path.is_file()}
                with self.assertRaises(consumer.ArchiveError):
                    self.resume()
                self.assertEqual(database.exists(), replacement)
                self.assertFalse(marker.exists())
                self.assertEqual(before, {path: path.read_bytes() for path in self.store.rglob("*") if path.is_file()})
                if replacement:
                    database.rename(self.root / "retained-replacement.sqlite")
                saved_database.rename(database)
                saved_marker.rename(marker)
                self.assertEqual(self.resume()["recorded_at"], first["recorded_at"])

    def test_in_place_database_rollback_cannot_replay_confirmed_operations(self):
        empty = self.root / "empty.sqlite"
        self.api.initialize(empty).close()
        snapshots = [empty.read_bytes()]
        original = consumer._ensure_operation
        def capture_create(ledger, raw, **kwargs):
            result = original(ledger, raw, **kwargs)
            if json.loads(raw)["operation_kind"] == "create_artifact":
                snapshots.append((self.store / "ledger.sqlite").read_bytes())
            return result
        with mock.patch.object(consumer, "_ensure_operation", side_effect=capture_create):
            first = self.archive()
        database = self.store / "ledger.sqlite"
        complete = database.read_bytes()
        inode = database.stat().st_ino
        for snapshot in snapshots:
            database.write_bytes(snapshot)
            self.assertEqual(database.stat().st_ino, inode)
            with self.api.open(database) as ledger:
                ledger_type = type(ledger)
            with mock.patch.object(ledger_type, "execute", side_effect=AssertionError("confirmed operations must not execute")):
                for call in (self.resume, self.archive):
                    with self.assertRaises(consumer.ArchiveError) as raised:
                        call()
                    self.assertEqual(raised.exception.code, "INTEGRITY_FAILURE")
                    self.assertEqual(database.read_bytes(), snapshot)
        database.write_bytes(complete)
        recovered = self.resume()
        self.assertTrue(recovered["reused"])
        self.assertEqual(recovered["recorded_at"], first["recorded_at"])

    def test_commit_receipt_publication_failure_reconciles_without_repeating_commit(self):
        for kind in ("create_artifact", "append_version"):
            for after_publication in (False, True):
                with self.subTest(kind=kind, after_publication=after_publication):
                    self.store = self.root / (kind + str(after_publication))
                    publish = consumer._publish_files
                    def interrupted(parent, name, files):
                        if name != kind or after_publication:
                            publish(parent, name, files)
                        if name == kind:
                            raise OSError("commit receipt publication interrupted")
                    with mock.patch.object(consumer, "_publish_files", side_effect=interrupted):
                        with self.assertRaises(OSError):
                            self.archive()
                    with self.api.open(self.store / "ledger.sqlite") as ledger:
                        ledger_type = type(ledger)
                    execute = ledger_type.execute
                    calls = []
                    def observed_execute(handle, raw, **kwargs):
                        calls.append(json.loads(raw)["operation_kind"])
                        return execute(handle, raw, **kwargs)
                    with mock.patch.object(ledger_type, "execute", new=observed_execute):
                        recovered = self.resume()
                    self.assertEqual(calls, ["append_version"] if kind == "create_artifact" else [])
                    self.assertEqual(self.verification()["counts"]["versions"], 1)
                    self.assertEqual(self.verification()["counts"]["idempotency_records"], 2)
                    self.read(recovered, name=kind + str(after_publication) + "-read")

    def test_append_receipt_protects_missing_create_receipt_from_reexecution(self):
        first = self.archive()
        database = self.store / "ledger.sqlite"
        complete = database.read_bytes()
        reservation = next(self.store.glob("request-task-*"))
        (reservation / "create_artifact").rename(self.root / "saved-create-receipt")
        empty = self.root / "empty.sqlite"
        self.api.initialize(empty).close()
        database.write_bytes(empty.read_bytes())
        with self.api.open(database) as ledger:
            ledger_type = type(ledger)
        with mock.patch.object(ledger_type, "execute", side_effect=AssertionError("known create must not execute")):
            with self.assertRaises(consumer.ArchiveError) as raised:
                self.resume()
            self.assertEqual(raised.exception.code, "INTEGRITY_FAILURE")
            self.assertEqual(database.read_bytes(), empty.read_bytes())
            database.write_bytes(complete)
            recovered = self.resume()
        self.assertEqual(recovered["recorded_at"], first["recorded_at"])
        self.assertEqual((reservation / "create_artifact/commit.json").read_bytes(),
                         (self.root / "saved-create-receipt/commit.json").read_bytes())

    def test_changed_commit_timestamp_is_not_accepted_as_original_history(self):
        first = self.archive()
        database = self.store / "ledger.sqlite"
        complete = database.read_bytes()
        # Coherent, same-inode rollback/rewrite of this fixture's history.
        with sqlite3.connect(database) as connection:
            raw = connection.execute("SELECT data FROM operations WHERE kind='append_version'").fetchone()[0]
            record = json.loads(raw)
            record["recorded_at"] = "2020-01-01T00:00:00.000000Z"
            connection.execute("UPDATE operations SET data=? WHERE kind='append_version'",
                               (json.dumps(record),))
        changed = database.read_bytes()
        with self.assertRaises(consumer.ArchiveError) as raised:
            self.resume()
        self.assertEqual(raised.exception.code, "INTEGRITY_FAILURE")
        self.assertEqual(database.read_bytes(), changed)
        database.write_bytes(complete)
        self.assertEqual(self.resume()["recorded_at"], first["recorded_at"])

    def test_changed_result_timestamp_is_rejected_before_continuing_archive(self):
        for kind, create_only in (("artifact", False), ("version", False), ("artifact", True)):
            with self.subTest(kind=kind, create_only=create_only):
                self.store = self.root / (kind + str(create_only))
                ensure = consumer._ensure_operation
                def stop_after_create(ledger, raw, **kwargs):
                    result = ensure(ledger, raw, **kwargs)
                    if json.loads(raw)["operation_kind"] == "create_artifact":
                        raise OSError("interrupted before append")
                    return result
                if create_only:
                    with mock.patch.object(consumer, "_ensure_operation", side_effect=stop_after_create):
                        with self.assertRaises(OSError):
                            self.archive()
                else:
                    self.archive()
                database = self.store / "ledger.sqlite"
                original = database.read_bytes()
                # Change only the primary record; its operation and external
                # receipt still retain the original successful timestamp.
                with sqlite3.connect(database) as connection:
                    identity, raw = connection.execute(
                        "SELECT id, data FROM records WHERE kind=?", (kind,)).fetchone()
                    record = json.loads(raw)
                    record["recorded_at"] = "2020-01-01T00:00:00.000000Z"
                    connection.execute("UPDATE records SET data=? WHERE id=?", (json.dumps(record), identity))
                changed = {path: path.read_bytes() for path in self.store.rglob("*") if path.is_file()}
                with self.api.open(database) as ledger:
                    ledger_type = type(ledger)
                with mock.patch.object(ledger_type, "execute", side_effect=AssertionError("inconsistent history must not write")):
                    for call in (self.resume, self.archive):
                        with self.assertRaises(consumer.ArchiveError) as raised:
                            call()
                        self.assertEqual(raised.exception.code, "INTEGRITY_FAILURE")
                        self.assertEqual(changed, {path: path.read_bytes() for path in self.store.rglob("*") if path.is_file()})
                database.write_bytes(original)
                self.assertEqual(self.resume()["status"], "ARCHIVED")
                self.assertEqual(self.verification()["counts"]["versions"], 1)
                self.assertEqual(self.verification()["counts"]["idempotency_records"], 2)

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
        # Filesystem maintenance must accept this unchanged v1 token-scoped
        # request, rather than reinterpret it with the newer task-scoped key.
        before_binding = {path: path.read_bytes() for path in self.store.rglob("*") if path.is_file()}
        checkpoint = hashlib.sha256((self.store / "ledger.sqlite").read_bytes()).hexdigest()
        with mock.patch.object(ledger_type, "execute", side_effect=AssertionError("binding must not replay")):
            self.assertFalse(consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)["reused"])
            self.assertTrue(consumer.bind_filesystem(self.store, expected_database_sha256=checkpoint)["reused"])
        self.assertEqual(before_binding, {path: path.read_bytes() for path in before_binding})
        self.assertEqual(self.verification(), counts)
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
