"""Real files and crash-boundary checks for private evidence publication."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from local_hand_jobs import evidence
from local_hand_jobs.evidence import EvidenceError, EvidenceStore, FrozenSnapshot, QuiescenceProof

OP = "2b909984-2ac7-41ab-8d96-9febc473284d"


class EvidenceFixture:
    def __init__(self, root: Path, payload: bytes = b"retained command output\n"):
        self.source = root / "source"
        self.source.mkdir(mode=0o700)
        (self.source / "stdout.log").write_bytes(payload)
        self.snapshot = FrozenSnapshot(OP, 7, self.source, ("stdout.log",),
            QuiescenceProof("owned-execution", 7, True, True, True, True),
            {"source_sha256": "a" * 64, "retention": "COMPLETE"}, broker_events=(
                {"seq": 7, "namespace": "job", "id": OP, "kind": "EXECUTION_EXIT",
                 "observed_at": 1, "data_json": '{"outcome":"SUCCEEDED"}'},))
        self.registered = {}
        self.authorized = True
        self.authorizations = []
        self.store = EvidenceStore(root / "store", snapshot_provider=lambda _: self.snapshot,
            register_seal=self.register,
            is_registered=lambda seal_id, digest: self.registered.get(seal_id) == digest,
            authorize=self.authorize)

    def register(self, record):
        self.registered[record["seal_id"]] = record["seal_sha256"]

    def authorize(self, principal, operation_id):
        self.authorizations.append((principal, operation_id))
        if not self.authorized or principal != "reader" or operation_id != OP:
            raise EvidenceError("UNAUTHORIZED", "fixture access denied")

    def sealed(self):
        self.store.seal(OP)
        return self.store.manifest(OP, principal="reader")["artifacts"][0]

    def callback(self, tool, arguments):
        if tool != "lh_evidence_read_chunk":
            raise AssertionError("download must only read existing evidence")
        return self.store.read_chunk(principal="reader", **arguments)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = EvidenceFixture(self.root)

    def assertCode(self, code, call):
        with self.assertRaises(EvidenceError) as raised:
            call()
        self.assertEqual(raised.exception.code, code)
        self.assertNotIn(str(self.root), str(raised.exception))

    def test_seal_binds_exact_members_events_and_external_manifest(self):
        record = self.fixture.store.seal(OP)
        directory = self.fixture.store.root / record["seal_id"]
        raw = (directory / "seal.json").read_bytes()
        seal = json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), record["seal_sha256"])
        self.assertNotIn("seal_sha256", seal)
        self.assertEqual(seal["member_count"], 4)
        self.assertEqual(seal["event_seq"], 7)
        with zipfile.ZipFile(directory / "evidence.zip") as archive:
            self.assertEqual(archive.namelist(), ["stdout.log", "BROKER_EVENTS.json", "STOP_PROOF.json", "MANIFEST.json"])
            manifest = json.loads(archive.read("MANIFEST.json"))
            self.assertEqual(manifest["members"][0]["sha256"],
                             hashlib.sha256(archive.read("stdout.log")).hexdigest())
            self.assertEqual(archive.read("MANIFEST.json"), (directory / "manifest.json").read_bytes())
            self.assertEqual(json.loads(archive.read("BROKER_EVENTS.json"))["events"], list(self.fixture.snapshot.broker_events))
            self.assertTrue(json.loads(archive.read("STOP_PROOF.json"))["proof"]["tree_exited"])
        self.assertEqual((self.fixture.source / "stdout.log").read_bytes(), b"retained command output\n")
        self.assertTrue(all(path.stat().st_nlink == 1 for path in directory.iterdir()))

    def test_each_stop_fact_is_required_and_not_truthy(self):
        original = self.fixture.snapshot
        for field in ("future_starts_blocked", "tree_exited", "collectors_stopped", "writers_stopped"):
            for value in (False, 1, "yes"):
                with self.subTest(field=field, value=value):
                    self.fixture.snapshot = replace(original, quiescence=replace(original.quiescence, **{field: value}))
                    self.assertCode("NOT_SEALED", lambda: self.fixture.store.seal(OP))

    def test_stale_stop_proof_rejected(self):
        self.fixture.snapshot = replace(self.fixture.snapshot, event_seq=8)
        self.assertCode("NOT_SEALED", lambda: self.fixture.store.seal(OP))

    def test_complete_seal_requires_actual_cutoff_events_and_correct_identity(self):
        original = self.fixture.snapshot
        self.fixture.snapshot = replace(original, broker_events=())
        self.assertCode("NOT_SEALED", lambda: self.fixture.store.seal(OP))
        for change in ({"seq": 6}, {"seq": 8}, {"namespace": "reconcile"}, {"id": "another-job"}):
            self.fixture.snapshot = replace(original, broker_events=(dict(original.broker_events[0], **change),))
            self.assertCode("CONFLICT", lambda: self.fixture.store.seal(OP))

    def test_unexpected_members_and_reserved_manifest_rejected(self):
        (self.fixture.source / "concurrent.log").write_bytes(b"not owned by this snapshot")
        self.assertCode("CONFLICT", lambda: self.fixture.store.seal(OP))
        self.assertEqual((self.fixture.source / "concurrent.log").read_bytes(), b"not owned by this snapshot")
        self.fixture.snapshot = replace(self.fixture.snapshot, members=("MANIFEST.json",))
        self.assertCode("CONFLICT", lambda: self.fixture.store.seal(OP))

    def test_event_change_after_hashing_cannot_publish(self):
        old = self.fixture.store.snapshot_provider
        calls = 0
        def provider(operation):
            nonlocal calls
            calls += 1
            result = old(operation)
            return result if calls == 1 else replace(result, event_seq=8,
                    quiescence=replace(result.quiescence, event_seq=8))
        self.fixture.store.snapshot_provider = provider
        self.assertCode("CONFLICT", lambda: self.fixture.store.seal(OP))
        self.assertFalse(self.fixture.registered)

    def test_source_directory_replacement_cannot_register_a_stale_snapshot(self):
        original = self.fixture.store._inventory
        calls = 0
        def replace_after_final_inventory(fd):
            nonlocal calls
            calls += 1
            result = original(fd)
            if calls == 2:
                self.fixture.source.rename(self.root / "retained-original")
                self.fixture.source.mkdir(mode=0o700)
                (self.fixture.source / "stdout.log").write_bytes(b"changed source directory")
            return result
        with mock.patch.object(self.fixture.store, "_inventory", side_effect=replace_after_final_inventory):
            self.assertCode("CONFLICT", lambda: self.fixture.store.seal(OP))
        self.assertFalse(self.fixture.registered)
        self.assertEqual((self.fixture.source / "stdout.log").read_bytes(), b"changed source directory")

    def test_symlink_hardlink_fifo_and_directory_alias_rejected(self):
        source = self.fixture.source / "stdout.log"
        source.unlink()
        target = self.root / "unrelated"
        target.write_bytes(b"retain")
        factories = (lambda: source.symlink_to(target), lambda: os.link(target, source),
                     lambda: os.mkfifo(source), lambda: source.symlink_to(self.root, target_is_directory=True))
        for factory in factories:
            factory()
            self.assertCode("CONFLICT", lambda: self.fixture.store.seal(OP))
            source.unlink()
        self.assertEqual(target.read_bytes(), b"retain")

    def test_source_budget_rejection_preserves_inputs(self):
        self.fixture.store.max_source_bytes = 4
        self.assertCode("CONFLICT", lambda: self.fixture.store.seal(OP))
        self.assertTrue((self.fixture.source / "stdout.log").is_file())

    def test_registration_failure_never_opens_published_bytes_even_after_restart(self):
        def fail(_):
            raise OSError("fixture persistence failure")
        self.fixture.store.register_seal = fail
        self.assertCode("IO_UNCERTAIN", lambda: self.fixture.store.seal(OP))
        paths = [p for p in self.fixture.store.root.iterdir() if not p.name.startswith("staging-")]
        self.assertEqual(len(paths), 1)
        self.assertTrue((paths[0] / "evidence.zip").is_file())
        self.assertCode("NOT_SEALED", lambda: self.fixture.store.manifest(OP, principal="reader"))
        reopened = EvidenceStore(self.fixture.store.root, snapshot_provider=lambda _: self.fixture.snapshot,
                                 register_seal=fail, is_registered=lambda *_: False)
        self.assertCode("NOT_SEALED", lambda: reopened.owner_of(paths[0].name + ".zip"))

    def test_supervised_publish_is_closed_until_parent_registers(self):
        with mock.patch.object(self.fixture.store, "register_seal", side_effect=AssertionError("helper cannot register")):
            record = self.fixture.store.publish_only(self.fixture.snapshot)
        self.assertEqual(record["publication_state"], "PUBLISHED_UNREGISTERED")
        self.assertEqual(record["evidence_state"], "STAGING")
        self.assertFalse(self.fixture.registered)
        self.assertCode("NOT_SEALED", lambda: self.fixture.store.owner_of(record["seal_id"] + ".zip"))
        self.fixture.register(record)
        self.assertEqual(self.fixture.store.owner_of(record["seal_id"] + ".zip"), OP)

    def test_published_replacement_before_registration_remains_closed(self):
        real = evidence._publish_create_only
        def replacement(source, destination):
            real(source, destination)
            if destination.name == "evidence.zip":
                destination.write_bytes(b"replacement")
        with mock.patch.object(evidence, "_publish_create_only", side_effect=replacement):
            self.assertCode("IO_UNCERTAIN", lambda: self.fixture.store.seal(OP))
        self.assertFalse(self.fixture.registered)

    def test_staging_archive_replacement_cannot_become_the_authenticated_archive(self):
        original = self.fixture.store._write
        def replace_completed_archive(path, data):
            original(path, data)
            if path.name == "manifest.json":
                (path.parent / "evidence.zip").write_bytes(b"not the generated archive")
        with mock.patch.object(self.fixture.store, "_write", side_effect=replace_completed_archive):
            self.assertCode("CONFLICT", lambda: self.fixture.store.seal(OP))
        self.assertFalse(self.fixture.registered)

    def test_directory_fsync_failure_has_no_registration(self):
        original = self.fixture.store._sync_directory
        def fail_destination(path):
            if not path.name.startswith("staging-"):
                raise OSError("fixture directory persistence failure")
            original(path)
        with mock.patch.object(self.fixture.store, "_sync_directory", side_effect=fail_destination):
            self.assertCode("IO_UNCERTAIN", lambda: self.fixture.store.seal(OP))
        self.assertFalse(self.fixture.registered)

    def test_create_only_collision_retains_concurrent_file(self):
        real = evidence._publish_create_only
        collided = []
        def concurrent(source, destination):
            if not collided:
                destination.write_bytes(b"concurrent owner bytes")
                collided.append(destination)
            return real(source, destination)
        with mock.patch.object(evidence, "_publish_create_only", side_effect=concurrent):
            self.assertCode("IO_UNCERTAIN", lambda: self.fixture.store.seal(OP))
        self.assertEqual(collided[0].read_bytes(), b"concurrent owner bytes")
        self.assertFalse(self.fixture.registered)

    def test_appended_seal_never_modifies_original(self):
        first = self.fixture.store.seal(OP)
        original = (self.fixture.store.root / first["seal_id"] / "evidence.zip").read_bytes()
        self.fixture.snapshot = replace(self.fixture.snapshot, event_seq=9,
            quiescence=replace(self.fixture.snapshot.quiescence, event_seq=9),
            previous_seal_id=first["seal_id"], reconcile_id="e013f084-1e57-4c43-8edc-361a363d658d",
            broker_events=({"seq": 9, "namespace": "reconcile", "id": "e013f084-1e57-4c43-8edc-361a363d658d",
                            "kind": "OBSERVATION_EXIT", "observed_at": 2, "data_json": "{}"},))
        second = self.fixture.store.seal(OP)
        self.assertNotEqual(first["seal_id"], second["seal_id"])
        self.assertEqual(second["previous_seal_id"], first["seal_id"])
        self.assertEqual((self.fixture.store.root / first["seal_id"] / "evidence.zip").read_bytes(), original)

    def test_chunk_full_digest_range_and_response_budget(self):
        artifact = self.fixture.sealed()
        result = self.fixture.store.read_chunk(artifact["artifact_id"], 0, 256 * 1024,
                                             artifact["sha256"], principal="reader")
        self.assertEqual(result["sha256"], artifact["sha256"])
        self.assertLess(len(json.dumps(result)), evidence.MAX_RESPONSE)
        self.assertTrue(result["eof"])
        for offset, length in ((True, 1), (-1, 1), (0, True), (0, 0), (0, 262145)):
            self.assertCode("LIMIT_EXCEEDED", lambda: self.fixture.store.read_chunk(
                artifact["artifact_id"], offset, length, artifact["sha256"], principal="reader"))
        self.assertCode("CONFLICT", lambda: self.fixture.store.read_chunk(
            artifact["artifact_id"], artifact["size"] + 1, 1, artifact["sha256"], principal="reader"))

    def test_every_chunk_rechecks_authorization_and_artifact_bytes(self):
        artifact = self.fixture.sealed()
        self.fixture.callback("lh_evidence_read_chunk", {"artifact_id": artifact["artifact_id"],
                              "expected_sha256": artifact["sha256"], "offset": 0, "length": 1})
        self.fixture.authorized = False
        self.assertCode("UNAUTHORIZED", lambda: self.fixture.callback("lh_evidence_read_chunk",
            {"artifact_id": artifact["artifact_id"], "expected_sha256": artifact["sha256"]}))
        self.fixture.authorized = True
        path = self.fixture.store.root / artifact["seal_id"] / "evidence.zip"
        raw = bytearray(path.read_bytes())
        raw[10] ^= 1
        path.write_bytes(raw)
        self.assertCode("CONFLICT", lambda: self.fixture.callback("lh_evidence_read_chunk",
            {"artifact_id": artifact["artifact_id"], "expected_sha256": artifact["sha256"]}))

    def test_persisted_identity_survives_restart_and_detects_restored_mtime(self):
        artifact = self.fixture.sealed()
        reopened = EvidenceStore(self.fixture.store.root, snapshot_provider=lambda _: self.fixture.snapshot,
            register_seal=self.fixture.register,
            is_registered=lambda seal_id, digest: self.fixture.registered.get(seal_id) == digest)
        self.assertGreater(reopened.read_chunk(artifact["artifact_id"], 0, 16, artifact["sha256"])["length"], 0)
        path = self.fixture.store.root / artifact["seal_id"] / "evidence.zip"
        before = path.stat()
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertCode("CONFLICT", lambda: reopened.read_chunk(artifact["artifact_id"], 0, 16, artifact["sha256"]))

    def test_chunk_does_not_rehash_the_full_archive(self):
        (self.fixture.source / "stdout.log").write_bytes(os.urandom(1024 * 1024))
        artifact = self.fixture.sealed()
        real_read = os.read
        byte_count = 0
        def counted(fd, size):
            nonlocal byte_count
            data = real_read(fd, size)
            byte_count += len(data)
            return data
        with mock.patch.object(evidence.os, "read", side_effect=counted):
            result = self.fixture.store.read_chunk(artifact["artifact_id"], 0, 65536,
                                                  artifact["sha256"], principal="reader")
        self.assertEqual(result["length"], 65536)
        self.assertLess(byte_count, 128 * 1024)

    def test_manifest_cursor_binds_subject_and_exact_catalog(self):
        self.fixture.sealed()
        first = self.fixture.store.manifest(OP, principal="reader", page_size=1)
        second = self.fixture.store.manifest(OP, principal="reader", page_size=1, cursor=first["next_cursor"])
        self.assertNotEqual(first["artifacts"], second["artifacts"])
        self.assertCode("CONFLICT", lambda: self.fixture.store.manifest(OP, principal="reader",
                       cursor=first["next_cursor"] + "x"))
        self.fixture.store.seal(OP)
        self.assertCode("CONFLICT", lambda: self.fixture.store.manifest(OP, principal="reader",
                       cursor=first["next_cursor"]))

    def test_registered_index_isolated_from_incomplete_or_unrelated_publications(self):
        artifact = self.fixture.sealed()
        self.fixture.store.list_seals = lambda _: [{"seal_id": identity, "seal_sha256": digest}
                for identity, digest in self.fixture.registered.items()]
        pending = self.fixture.store.root / "cc61bb0c-ea6b-4058-a2a1-ab5e92ed134c"
        pending.mkdir(mode=0o700)
        unrelated = self.fixture.store.root / "b065541e-2a1b-416a-86b1-80f5e740f8dc"
        unrelated.mkdir(mode=0o700)
        (unrelated / "seal.json").write_bytes(b"corrupt unrelated publication")
        page = self.fixture.store.manifest(OP, principal="reader")
        self.assertEqual(page["artifacts"][0], artifact)
        self.assertCode("NOT_FOUND", lambda: self.fixture.store.owner_of(pending.name + ".zip"))

    def test_registered_index_never_hides_missing_or_changed_registered_seal(self):
        artifact = self.fixture.sealed()
        self.fixture.store.list_seals = lambda _: [{"seal_id": artifact["seal_id"],
                                                    "seal_sha256": artifact["seal_sha256"]}]
        path = self.fixture.store.root / artifact["seal_id"] / "seal.json"
        path.unlink()
        self.assertCode("NOT_FOUND", lambda: self.fixture.store.manifest(OP, principal="reader"))

    def test_default_manifest_page_at_most_100(self):
        for _ in range(34):
            self.fixture.store.seal(OP)
        first = self.fixture.store.manifest(OP, principal="reader")
        self.assertEqual(len(first["artifacts"]), 100)
        second = self.fixture.store.manifest(OP, principal="reader", cursor=first["next_cursor"])
        self.assertEqual(len(second["artifacts"]), 2)
        self.assertIsNone(second["next_cursor"])

    def test_unknown_or_path_artifact_never_resolves_user_path(self):
        self.assertCode("NOT_FOUND", lambda: self.fixture.store.owner_of("../../secret.zip"))
        self.assertCode("NOT_FOUND", lambda: self.fixture.store.owner_of("260117ce-c01e-4697-b0f9-2820e3ce47ea.zip"))


if __name__ == "__main__":
    unittest.main()
