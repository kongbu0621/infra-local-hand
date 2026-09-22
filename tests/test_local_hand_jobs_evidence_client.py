"""Callback-to-file verification, including a real 16 MiB resumable archive."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
import zipfile

from local_hand_jobs import evidence_client
from local_hand_jobs.evidence import EvidenceError, _json, _hash
from local_hand_jobs.evidence_client import BoundedFileWriter, EvidenceClient
from test_local_hand_jobs_evidence import EvidenceFixture, OP


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def assertCode(self, code, call):
        with self.assertRaises(EvidenceError) as raised:
            call()
        self.assertEqual(raised.exception.code, code)

    def fixture(self, payload=b"fixture output\n"):
        fixture = EvidenceFixture(self.root, payload)
        return fixture, fixture.sealed()

    def test_16_mib_low_compression_archive_interrupt_resume_actual_file(self):
        payload = os.urandom(16 * 1024 * 1024)
        fixture, artifact = self.fixture(payload)
        self.assertGreater(artifact["size"], 16 * 1024 * 1024)
        offsets = []
        interrupted = False
        def callback(tool, arguments):
            nonlocal interrupted
            if arguments["artifact_id"].endswith(".zip"):
                offsets.append(arguments["offset"])
                if len(offsets) == 5 and not interrupted:
                    interrupted = True
                    raise ConnectionError("fixture disconnected after durable chunks")
            return fixture.callback(tool, arguments)
        directory = self.root / "client"
        client = EvidenceClient(callback)
        with self.assertRaises(ConnectionError):
            client.download(artifact, BoundedFileWriter(directory))
        self.assertFalse(list(directory.glob("download-*/evidence.zip")))
        resumed_at = offsets[-1]
        final = client.download(artifact, BoundedFileWriter(directory))
        self.assertEqual(offsets[5], resumed_at)
        self.assertEqual(offsets.count(resumed_at), 2)
        self.assertEqual(final.stat().st_size, artifact["size"])
        self.assertEqual(hashlib.sha256(final.read_bytes()).hexdigest(), artifact["sha256"])
        with zipfile.ZipFile(final) as archive:
            self.assertEqual(archive.read("stdout.log"), payload)
            self.assertGreater(archive.getinfo("stdout.log").compress_size / len(payload), 0.99)
        # Completed retry validates the actual final file and fetches no ZIP chunks.
        previous = len(offsets)
        self.assertEqual(client.download(artifact, BoundedFileWriter(directory)), final)
        self.assertEqual(len(offsets), previous)

    def test_wrong_chunk_fields_rejected_before_final_publication(self):
        fixture, artifact = self.fixture()
        mutations = (
            lambda r: r.update(offset=True),
            lambda r: r.update(sha256="0" * 64),
            lambda r: r.update(total_size=r["total_size"] + 1),
            lambda r: r.update(chunk_sha256="0" * 64),
            lambda r: r.update(data_base64="!!!"),
            lambda r: r.update(eof=not r["eof"]),
            lambda r: r.update(length=0, data_base64="", chunk_sha256=_hash(b""), eof=False),
        )
        for index, mutate in enumerate(mutations):
            def callback(tool, arguments):
                result = fixture.callback(tool, arguments)
                if arguments["artifact_id"].endswith(".zip"):
                    mutate(result)
                return result
            directory = self.root / ("client-" + str(index))
            with self.subTest(index=index):
                self.assertCode("CONFLICT", lambda: EvidenceClient(callback).download(
                    artifact, BoundedFileWriter(directory)))
                self.assertFalse(list(directory.glob("download-*/evidence.zip")))

    def test_revocation_during_download_preserves_partial_only(self):
        fixture, artifact = self.fixture(os.urandom(200000))
        def callback(tool, arguments):
            if arguments["artifact_id"].endswith(".zip") and arguments["offset"] > 0:
                fixture.authorized = False
            return fixture.callback(tool, arguments)
        directory = self.root / "client"
        self.assertCode("UNAUTHORIZED", lambda: EvidenceClient(callback).download(
            artifact, BoundedFileWriter(directory)))
        self.assertTrue(list(directory.glob("download-*/partial.bin")))
        self.assertFalse(list(directory.glob("download-*/evidence.zip")))

    def test_partial_mutation_rejected_on_resume(self):
        fixture, artifact = self.fixture(os.urandom(200000))
        def callback(tool, arguments):
            if arguments["artifact_id"].endswith(".zip") and arguments["offset"] > 0:
                raise ConnectionError("fixture interruption")
            return fixture.callback(tool, arguments)
        directory = self.root / "client"
        with self.assertRaises(ConnectionError):
            EvidenceClient(callback).download(artifact, BoundedFileWriter(directory))
        partial = next(directory.glob("download-*/partial.bin"))
        raw = bytearray(partial.read_bytes())
        raw[0] ^= 1
        partial.write_bytes(raw)
        self.assertCode("CONFLICT", lambda: EvidenceClient(fixture.callback).download(
            artifact, BoundedFileWriter(directory)))

    def test_torn_checkpoint_discards_only_uncommitted_tail(self):
        fixture, artifact = self.fixture(os.urandom(200000))
        directory = self.root / "client"
        writer = BoundedFileWriter(directory)
        self.assertEqual(writer.prepare(artifact), 0)
        raw = (fixture.store.root / artifact["seal_id"] / "evidence.zip").read_bytes()
        writer.write(0, raw[:65536])
        partial, journal = writer.partial, writer.directory / "checkpoints.jsonl"
        writer.close()
        with partial.open("ab") as stream:
            stream.write(b"uncommitted-tail")
        with journal.open("ab") as stream:
            stream.write(b'{"offset":')
        self.assertEqual(EvidenceClient(fixture.callback).download(artifact, BoundedFileWriter(directory)).read_bytes(), raw)

    def test_parallel_writer_denied_by_same_binding_lock(self):
        _, artifact = self.fixture()
        first = BoundedFileWriter(self.root / "client")
        first.prepare(artifact)
        self.addCleanup(first.close)
        second = BoundedFileWriter(self.root / "client")
        self.assertCode("RESOURCE_BUSY", lambda: second.prepare(artifact))

    def test_writer_refuses_foreign_existing_final(self):
        fixture, artifact = self.fixture()
        real = evidence_client._publish_create_only
        collided = []
        def collide(source, destination, **kwargs):
            directory = Path("/proc/self/fd") / str(kwargs["destination_dir_fd"])
            foreign = directory / destination
            foreign.write_bytes(b"another writer owns this")
            collided.append(foreign.resolve())
            return real(source, destination, **kwargs)
        with mock.patch.object(evidence_client, "_publish_create_only", side_effect=collide):
            with self.assertRaises(FileExistsError):
                EvidenceClient(fixture.callback).download(artifact, BoundedFileWriter(self.root / "client"))
        self.assertEqual(collided[0].read_bytes(), b"another writer owns this")

    def test_parent_replacement_during_validation_never_returns_foreign_bytes(self):
        payload = b"expected validated bytes"
        artifact = {"artifact_id": "fixture.manifest", "role": "manifest",
                    "size": len(payload), "sha256": _hash(payload)}
        writer = BoundedFileWriter(self.root / "client")
        self.addCleanup(writer.close)
        writer.prepare(artifact)
        writer.write(0, payload)
        def replace_parent(path):
            self.assertEqual(path.read_bytes(), payload)
            writer.directory.rename(self.root / "retained-original")
            writer.directory.mkdir(mode=0o700)
            writer.partial.write_bytes(b"UNVERIFIED-REPLACEMENT")
        self.assertCode("CONFLICT", lambda: writer.finish(replace_parent))
        self.assertFalse(writer.final.exists())
        self.assertEqual(writer.partial.read_bytes(), b"UNVERIFIED-REPLACEMENT")
        self.assertEqual((self.root / "retained-original" / "partial.bin").read_bytes(), payload)

    def test_parent_replacement_between_chunks_stops_original_writer(self):
        payload = b"expected validated bytes"
        artifact = {"artifact_id": "fixture.manifest", "role": "manifest",
                    "size": len(payload), "sha256": _hash(payload)}
        writer = BoundedFileWriter(self.root / "client")
        self.addCleanup(writer.close)
        writer.prepare(artifact)
        writer.write(0, payload[:8])
        writer.directory.rename(self.root / "retained-original")
        writer.directory.mkdir(mode=0o700)
        writer.partial.write_bytes(b"foreign")
        self.assertCode("CONFLICT", lambda: writer.write(8, payload[8:]))
        self.assertEqual((self.root / "retained-original" / "partial.bin").read_bytes(), payload[:8])
        self.assertEqual(writer.partial.read_bytes(), b"foreign")

    def test_writer_budget_does_not_create_download(self):
        fixture, artifact = self.fixture()
        directory = self.root / "client"
        self.assertCode("CONFLICT", lambda: EvidenceClient(fixture.callback).download(
            artifact, BoundedFileWriter(directory, max_bytes=4)))
        self.assertEqual(list(directory.iterdir()), [])

    def test_external_seal_mismatch_rejected(self):
        fixture, artifact = self.fixture()
        changed = dict(artifact, seal_sha256="0" * 64)
        self.assertCode("CONFLICT", lambda: EvidenceClient(fixture.callback).download(
            changed, BoundedFileWriter(self.root / "client")))

    def synthetic_archive(self, *, unsafe_name=None, symlink=False, duplicate=False,
                          extra=False, bad_member_digest=False, expand=False,
                          manifest_changes=None, seal_changes=None):
        seal_id = "2f6f5c74-20eb-4c59-b692-e690e8449e5b"
        name = unsafe_name or "payload.bin"
        payload = b"data" * (10000 if expand else 1)
        manifest = {"schema_version": "lh-evidence-manifest-v1", "operation_id": OP,
                    "seal_id": seal_id, "event_seq": 7, "complete": True,
                    "bindings": {}, "reconcile_id": None, "previous_seal_id": None,
                    "members": [{"name": name, "size": len(payload),
                                 "sha256": "0" * 64 if bad_member_digest else _hash(payload)}]}
        manifest.update(manifest_changes or {})
        manifest_raw = _json(manifest)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo(name)
            info.external_attr = ((stat.S_IFLNK if symlink else stat.S_IFREG) | 0o600) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
            info = zipfile.ZipInfo("MANIFEST.json")
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            archive.writestr(info, manifest_raw)
            if duplicate or extra:
                info = zipfile.ZipInfo(name if duplicate else "unexpected.bin")
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                if duplicate:
                    with self.assertWarnsRegex(UserWarning, "Duplicate name"):
                        archive.writestr(info, b"foreign")
                else:
                    archive.writestr(info, b"foreign")
        archive_raw = output.getvalue()
        artifact = {"artifact_id": seal_id + ".zip", "role": "zip", "size": len(archive_raw),
                    "sha256": _hash(archive_raw), "seal_id": seal_id,
                    "operation_id": OP, "event_seq": 7}
        seal = {"schema_version": "lh-evidence-seal-v1", "operation_id": OP,
                "seal_id": seal_id, "event_seq": 7, "complete": True,
                "bindings": {}, "reconcile_id": None, "previous_seal_id": None,
                "member_count": 3 if duplicate or extra else 2,
                "artifacts": [{k: artifact[k] for k in ("artifact_id", "role", "size", "sha256")},
                              {"artifact_id": seal_id + ".manifest", "role": "manifest",
                               "size": len(manifest_raw), "sha256": _hash(manifest_raw)}]}
        seal.update(seal_changes or {})
        seal_raw = _json(seal)
        artifact["seal_sha256"] = _hash(seal_raw)
        def callback(tool, arguments):
            raw = seal_raw if arguments["artifact_id"].endswith(".seal") else archive_raw
            offset = arguments["offset"]
            chunk = raw[offset:offset + arguments["length"]]
            return {"artifact_id": arguments["artifact_id"], "offset": offset,
                    "length": len(chunk), "total_size": len(raw), "sha256": _hash(raw),
                    "chunk_sha256": _hash(chunk), "data_base64": base64.b64encode(chunk).decode(),
                    "eof": offset + len(chunk) == len(raw)}
        return artifact, callback

    def test_external_seal_and_manifest_must_agree_on_candidate_and_reconciliation(self):
        for field, first, second in (("bindings", {"source_digest": "a" * 64}, {"source_digest": "b" * 64}),
                ("reconcile_id", "fixture-first", "fixture-second"),
                ("previous_seal_id", "fixture-first", "fixture-second")):
            with self.subTest(field=field):
                artifact, callback = self.synthetic_archive(manifest_changes={field: first},
                                                              seal_changes={field: second})
                self.assertCode("CONFLICT", lambda: EvidenceClient(callback).download(
                    artifact, BoundedFileWriter(self.root / field)))

    def test_correct_full_sha_does_not_bypass_zip_member_validation(self):
        cases = ({"unsafe_name": "../escape"}, {"unsafe_name": "/absolute"},
                 {"symlink": True}, {"duplicate": True}, {"extra": True},
                 {"bad_member_digest": True})
        for index, case in enumerate(cases):
            with self.subTest(case=case):
                artifact, callback = self.synthetic_archive(**case)
                directory = self.root / ("client-" + str(index))
                self.assertCode("CONFLICT", lambda: EvidenceClient(callback).download(
                    artifact, BoundedFileWriter(directory)))
                self.assertFalse(list(directory.glob("download-*/evidence.zip")))
        self.assertFalse((self.root / "escape").exists())

    def test_compressed_expansion_is_bounded_before_read(self):
        artifact, callback = self.synthetic_archive(expand=True)
        self.assertLess(artifact["size"], 8192)
        self.assertCode("CONFLICT", lambda: EvidenceClient(callback).download(
            artifact, BoundedFileWriter(self.root / "client", max_bytes=8192)))


if __name__ == "__main__":
    unittest.main()
