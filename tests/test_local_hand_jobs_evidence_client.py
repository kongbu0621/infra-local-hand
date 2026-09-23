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

    def test_writer_close_failure_releases_all_descriptors_and_resumes_same_prefix(self):
        payload = b"durable prefix and remaining evidence"
        artifact = {"artifact_id": "fixture.manifest", "role": "manifest",
                    "size": len(payload), "sha256": _hash(payload)}
        writer = BoundedFileWriter(self.root / "client")
        writer.prepare(artifact)
        writer.write(0, payload[:8])
        held = [writer._fd, writer._journal, writer._lock, writer._directory_fd]
        real_close, attempted = os.close, []
        def fail_after_close(fd):
            attempted.append(fd)
            real_close(fd)
            if fd == held[0]:
                raise OSError("fixture partial close failed after release")
        try:
            with mock.patch.object(evidence_client.os, "close", side_effect=fail_after_close):
                with self.assertRaises(Exception) as raised:
                    writer.close()
            self.assertEqual(attempted, held)
            self.assertIsInstance(raised.exception, EvidenceError)
            self.assertEqual(raised.exception.code, "IO_UNCERTAIN")
            writer.close()
            resumed = BoundedFileWriter(writer.root)
            self.addCleanup(resumed.close)
            self.assertEqual(resumed.prepare(artifact), 8)
            resumed.write(8, payload[8:])
            self.assertEqual(resumed.finish(lambda _: None).read_bytes(), payload)
        finally:
            # Retain the baseline failure while avoiding leaked fixture locks.
            for attribute in ("_fd", "_journal", "_lock", "_directory_fd"):
                fd = getattr(writer, attribute)
                setattr(writer, attribute, None)
                if fd is not None and fd not in attempted:
                    real_close(fd)

    def test_publication_close_failure_does_not_close_reused_descriptor(self):
        fixture, artifact = self.fixture()
        writer = BoundedFileWriter(self.root / "client")
        real_close, reused, zip_offsets, partial_fds = os.close, [], [], []
        def callback(tool, arguments):
            if arguments["artifact_id"].endswith(".zip"):
                zip_offsets.append(arguments["offset"])
                if not partial_fds:
                    partial_fds.append(writer._fd)
            return fixture.callback(tool, arguments)
        def fail_after_close(fd):
            real_close(fd)
            if partial_fds and fd == partial_fds[0] and writer.final.exists() and not reused:
                sentinel = os.open(os.devnull, os.O_RDONLY)
                if sentinel != fd:
                    os.dup2(sentinel, fd)
                    real_close(sentinel)
                reused.append(fd)
                raise OSError("fixture published partial close failed after release")
        try:
            with mock.patch.object(evidence_client.os, "close", side_effect=fail_after_close):
                with self.assertRaises(Exception) as raised:
                    EvidenceClient(callback).download(artifact, writer)
            self.assertEqual(len(reused), 1)
            os.fstat(reused[0])
            self.assertIsInstance(raised.exception, EvidenceError)
            self.assertEqual(raised.exception.code, "IO_UNCERTAIN")
            previous = list(zip_offsets)
            final = EvidenceClient(callback).download(artifact, BoundedFileWriter(writer.root))
            self.assertEqual(_hash(final.read_bytes()), artifact["sha256"])
            self.assertEqual(zip_offsets, previous)
        finally:
            for fd in reused:
                try:
                    real_close(fd)
                except OSError:
                    pass

    def test_download_cleanup_failure_preserves_original_interruption(self):
        fixture, artifact = self.fixture(os.urandom(200000))
        writer = BoundedFileWriter(self.root / "client")
        real_close, attempted, held = os.close, [], []
        def callback(tool, arguments):
            if arguments["artifact_id"].endswith(".zip") and arguments["offset"] > 0:
                held.extend([writer._fd, writer._journal, writer._lock, writer._directory_fd])
                raise ConnectionError("fixture original interruption")
            return fixture.callback(tool, arguments)
        def fail_after_close(fd):
            if fd in held:
                attempted.append(fd)
            real_close(fd)
            if held and fd == held[1]:
                raise OSError("fixture checkpoint close failed after release")
        try:
            with mock.patch.object(evidence_client.os, "close", side_effect=fail_after_close):
                with self.assertRaises(Exception) as raised:
                    EvidenceClient(callback).download(artifact, writer)
            self.assertIsInstance(raised.exception, ConnectionError)
            self.assertEqual(attempted, held)
            self.assertIn("Evidence writer descriptor cleanup also failed", raised.exception.__notes__)
            final = EvidenceClient(fixture.callback).download(artifact, BoundedFileWriter(writer.root))
            self.assertEqual(_hash(final.read_bytes()), artifact["sha256"])
        finally:
            for attribute in ("_fd", "_journal", "_lock", "_directory_fd"):
                fd = getattr(writer, attribute)
                setattr(writer, attribute, None)
                if fd is not None and fd not in attempted:
                    real_close(fd)

    def test_cleanup_does_not_suppress_failure_for_unrelated_ambient_exception(self):
        payload = b"fixture evidence"
        artifact = {"artifact_id": "fixture.manifest", "role": "manifest",
                    "size": len(payload), "sha256": _hash(payload)}
        for mode in ("close", "context", "download"):
            with self.subTest(mode=mode):
                writer = BoundedFileWriter(self.root / mode)
                lock_fd = []
                if mode != "download":
                    writer.prepare(artifact)
                    writer.write(0, payload)
                    lock_fd.append(writer._lock)
                def callback(tool, arguments):
                    lock_fd.append(writer._lock)
                    return {"artifact_id": artifact["artifact_id"], "sha256": artifact["sha256"],
                            "offset": 0, "length": len(payload), "total_size": len(payload),
                            "eof": True, "chunk_sha256": _hash(payload),
                            "data_base64": base64.b64encode(payload).decode()}
                real_close = os.close
                def fail_after_close(fd):
                    real_close(fd)
                    if fd in lock_fd:
                        raise OSError("fixture lock close failed after release")
                ambient = LookupError("already handled unrelated caller failure")
                try:
                    raise ambient
                except LookupError:
                    with mock.patch.object(evidence_client.os, "close", side_effect=fail_after_close):
                        with self.assertRaises(EvidenceError) as raised:
                            if mode == "download":
                                EvidenceClient(callback).download(artifact, writer)
                            elif mode == "context":
                                with writer:
                                    pass
                            else:
                                writer.close()
                    self.assertEqual(raised.exception.code, "IO_UNCERTAIN")
                    self.assertFalse(hasattr(ambient, "__notes__"))

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

    def test_binding_cleanup_preserves_primary_failure_and_reports_close_only_failure(self):
        payload = b"recoverable evidence bytes"
        artifact = {"artifact_id": "fixture.manifest", "role": "manifest",
                    "size": len(payload), "sha256": _hash(payload)}
        for phase in ("write", "sync", "close"):
            with self.subTest(phase=phase):
                writer = BoundedFileWriter(self.root / phase)
                self.addCleanup(writer.close)
                primary = OSError("fixture primary binding " + phase + " failure")
                binding_fds, attempted = [], []
                real_write, real_sync, real_close = os.write, os.fsync, os.close
                def fail_write(fd, data):
                    if Path(os.readlink(f"/proc/self/fd/{fd}")).name == "binding.json":
                        binding_fds.append(fd)
                        if phase == "write":
                            real_write(fd, data[:7])
                            raise primary
                    return real_write(fd, data)
                def fail_sync(fd):
                    if phase == "sync" and fd in binding_fds:
                        raise primary
                    return real_sync(fd)
                def fail_close(fd):
                    real_close(fd)
                    if fd in binding_fds:
                        attempted.append(fd)
                        raise OSError("fixture secondary binding close failure")
                ambient = LookupError("already handled unrelated caller failure")
                try:
                    raise ambient
                except LookupError:
                    with mock.patch.object(evidence_client.os, "write", side_effect=fail_write), \
                            mock.patch.object(evidence_client.os, "fsync", side_effect=fail_sync), \
                            mock.patch.object(evidence_client.os, "close", side_effect=fail_close):
                        with self.assertRaises(Exception) as raised:
                            writer.prepare(artifact)
                self.assertTrue(binding_fds)
                self.assertEqual(attempted, binding_fds)
                self.assertFalse(hasattr(ambient, "__notes__"))
                if phase == "close":
                    self.assertIsInstance(raised.exception, EvidenceError)
                    self.assertEqual(raised.exception.code, "IO_UNCERTAIN")
                else:
                    self.assertIs(raised.exception, primary)
                    self.assertIn("Evidence descriptor cleanup also failed", primary.__notes__)
                self.assertTrue(all(getattr(writer, name) is None for name in
                                    ("_fd", "_journal", "_lock", "_directory_fd")))
                self.assertFalse(writer.final.exists())
                if phase == "write":
                    self.assertEqual((writer.directory / "binding.json").read_bytes(), b'{"artif')
                    self.assertCode("CONFLICT", lambda: writer.prepare(artifact))
                else:
                    self.assertEqual(writer.prepare(artifact), 0)
                    writer.write(0, payload)
                    self.assertEqual(writer.finish(lambda _: None).read_bytes(), payload)

    def test_interrupted_checkpoint_restore_closes_owned_descriptors_and_can_resume(self):
        payload = b"recoverable evidence bytes"
        artifact = {"artifact_id": "fixture.manifest", "role": "manifest",
                    "size": len(payload), "sha256": _hash(payload)}
        writer = BoundedFileWriter(self.root / "client")
        self.addCleanup(writer.close)
        writer.prepare(artifact)
        writer.write(0, payload[:8])
        writer.close()
        primary = KeyboardInterrupt("fixture interruption during checkpoint restore")
        real_read, held = evidence_client._read, []
        def interrupt_journal(fd, maximum):
            if Path(os.readlink(f"/proc/self/fd/{fd}")).name == "checkpoints.jsonl":
                held.extend([writer._fd, writer._journal, writer._lock, writer._directory_fd])
                raise primary
            return real_read(fd, maximum)
        with mock.patch.object(evidence_client, "_read", side_effect=interrupt_journal):
            with self.assertRaises(KeyboardInterrupt) as raised:
                writer.prepare(artifact)
        self.assertIs(raised.exception, primary)
        self.assertEqual(len(held), 4)
        self.assertTrue(all(getattr(writer, name) is None for name in
                            ("_fd", "_journal", "_lock", "_directory_fd")))
        for fd in held:
            with self.assertRaises(OSError):
                os.fstat(fd)
        resumed = BoundedFileWriter(writer.root)
        self.addCleanup(resumed.close)
        self.assertEqual(resumed.prepare(artifact), 8)
        resumed.write(8, payload[8:])
        self.assertEqual(resumed.finish(lambda _: None).read_bytes(), payload)

    def _publication_sync_failure_requires_successful_recovery(self, target):
        fixture, artifact = self.fixture()
        directory = self.root / "client"
        directory.mkdir(mode=0o700)
        real_sync = os.fsync
        failures = []
        zip_offsets = []
        def callback(tool, arguments):
            if arguments["artifact_id"].endswith(".zip"):
                zip_offsets.append(arguments["offset"])
            return fixture.callback(tool, arguments)
        def fail_after_publication(fd):
            path = Path(os.readlink(Path("/proc/self/fd") / str(fd)))
            final = list(directory.glob("download-*/evidence.zip"))
            if final and path == (directory if target == "root" else final[0].parent):
                failures.append(path)
                raise OSError("fixture publication persistence failure")
            real_sync(fd)
        client = EvidenceClient(callback)
        with mock.patch.object(evidence_client.os, "fsync", side_effect=fail_after_publication):
            with self.assertRaisesRegex(OSError, "publication persistence failure"):
                client.download(artifact, BoundedFileWriter(directory))
            final = next(directory.glob("download-*/evidence.zip"))
            self.assertEqual(_hash(final.read_bytes()), artifact["sha256"])
            previous_chunks = list(zip_offsets)
            # Existing bytes alone do not prove the failed publication durable.
            with self.assertRaisesRegex(OSError, "publication persistence failure"):
                client.download(artifact, BoundedFileWriter(directory))
            self.assertEqual(zip_offsets, previous_chunks)
        self.assertEqual(len(failures), 2)
        self.assertEqual(client.download(artifact, BoundedFileWriter(directory)), final)
        self.assertEqual(zip_offsets, previous_chunks)

    def test_resumed_final_retries_failed_publication_directory_sync(self):
        self._publication_sync_failure_requires_successful_recovery("download")

    def test_final_publication_persists_download_entry_in_private_root(self):
        self._publication_sync_failure_requires_successful_recovery("root")

    def test_auto_created_private_root_ancestry_is_durable_before_completed_download(self):
        fixture, artifact = self.fixture()
        real_sync = os.fsync
        for ancestor in ("parent", "grandparent"):
            with self.subTest(ancestor=ancestor):
                directory = self.root / ancestor / "created-middle" / "private-root"
                target = directory.parent if ancestor == "parent" else directory.parent.parent
                attempts, zip_offsets = [], []
                def callback(tool, arguments):
                    if arguments["artifact_id"].endswith(".zip"):
                        zip_offsets.append(arguments["offset"])
                    return fixture.callback(tool, arguments)
                def fail_ancestor(fd):
                    if Path(os.readlink(Path("/proc/self/fd") / str(fd))) == target:
                        attempts.append(True)
                        raise OSError("fixture private root ancestry persistence failure")
                    real_sync(fd)
                client = EvidenceClient(callback)
                with mock.patch.object(evidence_client.os, "fsync", side_effect=fail_ancestor):
                    with self.assertRaisesRegex(OSError, "root ancestry persistence failure"):
                        client.download(artifact, BoundedFileWriter(directory))
                    previous = list(zip_offsets)
                    # mkdir(exist_ok=True) is not proof a prior failed chain is durable.
                    with self.assertRaisesRegex(OSError, "root ancestry persistence failure"):
                        client.download(artifact, BoundedFileWriter(directory))
                    self.assertEqual(previous, zip_offsets)
                self.assertEqual(len(attempts), 2)
                final = client.download(artifact, BoundedFileWriter(directory))
                self.assertEqual(_hash(final.read_bytes()), artifact["sha256"])
                self.assertEqual(previous, zip_offsets)

    def _final_mutation_during_sync_is_rejected(self, resumed):
        payload = b"expected verified evidence"
        artifact = {"artifact_id": "fixture.manifest", "role": "manifest",
                    "size": len(payload), "sha256": _hash(payload)}
        for target in ("file", "download", "root"):
            with self.subTest(target=target, resumed=resumed):
                directory = self.root / (target + ("-resumed" if resumed else "-new"))
                writer = BoundedFileWriter(directory)
                self.addCleanup(writer.close)
                writer.prepare(artifact)
                writer.write(0, payload)
                if resumed:
                    writer.finish(lambda _: None)
                    writer.close()
                    writer = BoundedFileWriter(directory)
                    self.addCleanup(writer.close)
                    self.assertEqual(writer.prepare(artifact), len(payload))
                original_sync = os.fsync
                changed = []
                target_path = {"file": writer.final, "download": writer.directory,
                               "root": writer.root}[target]
                def mutate_after_hash(fd):
                    path = Path(os.readlink(Path("/proc/self/fd") / str(fd)))
                    if not changed and path == target_path:
                        before = writer.final.stat()
                        writer.final.write_bytes(b"x" * len(payload))
                        os.utime(writer.final, ns=(before.st_atime_ns, before.st_mtime_ns))
                        changed.append(writer.final.stat().st_ino)
                        self.assertEqual(changed[-1], before.st_ino)
                    original_sync(fd)
                with mock.patch.object(evidence_client.os, "fsync", side_effect=mutate_after_hash):
                    self.assertCode("CONFLICT", lambda: writer.finish(lambda _: None))
                self.assertEqual(len(changed), 1)
                self.assertEqual(writer.final.read_bytes(), b"x" * len(payload))

    def test_new_final_keeps_verified_identity_through_all_durability_barriers(self):
        self._final_mutation_during_sync_is_rejected(False)

    def test_resumed_final_keeps_verified_identity_through_all_durability_barriers(self):
        self._final_mutation_during_sync_is_rejected(True)

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

    def test_writer_creation_rejects_symlink_ancestors_before_creating_directories(self):
        payload = b"fixture"
        artifact = {"artifact_id": "fixture.manifest", "role": "manifest",
                    "size": len(payload), "sha256": _hash(payload)}
        for phase in ("constructor", "prepare"):
            with self.subTest(phase=phase):
                parent = self.root / phase
                parent.mkdir(mode=0o700)
                foreign, alias = parent / "foreign", parent / "client"
                foreign.mkdir(mode=0o700)
                if phase == "constructor":
                    alias.symlink_to(foreign, target_is_directory=True)
                    create = lambda: BoundedFileWriter(alias / "missing" / "private")
                else:
                    writer = BoundedFileWriter(alias)
                    self.addCleanup(writer.close)
                    alias.rename(parent / "retained")
                    alias.symlink_to(foreign, target_is_directory=True)
                    create = lambda: writer.prepare(artifact)
                with self.assertRaises((OSError, EvidenceError)):
                    create()
                self.assertEqual(list(foreign.iterdir()), [])

    def test_client_member_budget_must_be_a_finite_positive_integer(self):
        for value in (True, 0, -1, float("inf"), 2**53):
            with self.subTest(value=value):
                self.assertCode("LIMIT_EXCEEDED", lambda: EvidenceClient(lambda *args: None, max_members=value))

    def test_external_seal_mismatch_rejected(self):
        fixture, artifact = self.fixture()
        changed = dict(artifact, seal_sha256="0" * 64)
        self.assertCode("CONFLICT", lambda: EvidenceClient(fixture.callback).download(
            changed, BoundedFileWriter(self.root / "client")))

    def test_archive_descriptor_cannot_skip_zip_checks_by_changing_its_role(self):
        artifact, callback = self.synthetic_archive(unsafe_name="../escape")
        artifact["role"] = "manifest"
        directory = self.root / "role-confusion"
        self.assertCode("CONFLICT", lambda: EvidenceClient(callback).download(
            artifact, BoundedFileWriter(directory)))
        self.assertFalse(list(directory.glob("download-*/evidence.json")))

    def test_download_descriptor_must_bind_the_reconciliation_in_the_external_seal(self):
        fixture, artifact = self.fixture()
        artifact = dict(artifact, reconcile_id="e013f084-1e57-4c43-8edc-361a363d658d")
        self.assertCode("CONFLICT", lambda: EvidenceClient(fixture.callback).download(
            artifact, BoundedFileWriter(self.root / "wrong-round")))

    def synthetic_archive(self, *, unsafe_name=None, symlink=False, duplicate=False,
                          extra=False, bad_member_digest=False, expand=False,
                          manifest_changes=None, seal_changes=None,
                          archive_transform=None, seal_transform=None):
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
        if archive_transform is not None:
            archive_raw = archive_transform(archive_raw)
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
        if seal_transform is not None:
            seal_transform(seal)
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

    def test_zip_original_member_name_cannot_hide_a_nul_suffix(self):
        def insert_nul(raw):
            self.assertEqual(raw.count(b"payload.binQ../hidden"), 2)
            changed = raw.replace(b"payload.binQ../hidden", b"payload.bin\0../hidden")
            with zipfile.ZipFile(io.BytesIO(changed)) as archive:
                info = archive.infolist()[0]
                self.assertEqual(info.filename, "payload.bin")
                self.assertEqual(info.orig_filename, "payload.bin\0../hidden")
            return changed
        artifact, callback = self.synthetic_archive(unsafe_name="payload.binQ../hidden",
            manifest_changes={"members": [{"name": "payload.bin", "size": 4,
                                            "sha256": _hash(b"data")}]},
            archive_transform=insert_nul)
        directory = self.root / "nul-name"
        self.assertCode("CONFLICT", lambda: EvidenceClient(callback).download(
            artifact, BoundedFileWriter(directory)))
        self.assertFalse(list(directory.glob("download-*/evidence.zip")))

    def test_external_seal_artifact_roles_and_ids_must_be_unambiguous(self):
        mutations = (
            lambda seal: seal["artifacts"].append(dict(seal["artifacts"][0], sha256="0" * 64)),
            lambda seal: seal["artifacts"][1].update(artifact_id="foreign.manifest"),
            lambda seal: seal["artifacts"][1].update(artifact_id=seal["seal_id"] + ".zip"),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                artifact, callback = self.synthetic_archive(seal_transform=mutate)
                directory = self.root / ("ambiguous-seal-" + str(index))
                self.assertCode("CONFLICT", lambda: EvidenceClient(callback).download(
                    artifact, BoundedFileWriter(directory)))
                # Metadata conflicts are rejected before any ZIP download state.
                self.assertEqual(list(directory.iterdir()), [])

    def test_manifest_binding_comparison_preserves_json_value_types(self):
        pairs = ((True, 1), (False, 0), (1.0, 1),
                 ({"nested": [True]}, {"nested": [1]}))
        for index, (manifest_value, seal_value) in enumerate(pairs):
            with self.subTest(index=index):
                artifact, callback = self.synthetic_archive(
                    manifest_changes={"bindings": {"value": manifest_value}},
                    seal_changes={"bindings": {"value": seal_value}})
                directory = self.root / ("binding-types-" + str(index))
                self.assertCode("CONFLICT", lambda: EvidenceClient(callback).download(
                    artifact, BoundedFileWriter(directory)))
                self.assertFalse(list(directory.glob("download-*/evidence.zip")))

    def test_evidence_cutoffs_counts_and_sizes_require_actual_integers(self):
        cases = ({"seal_changes": {"event_seq": 7.0}},
                 {"manifest_changes": {"event_seq": 7.0}},
                 {"seal_changes": {"member_count": 2.0}},
                 {"manifest_changes": {"members": [{"name": "payload.bin", "size": 4.0,
                                                     "sha256": _hash(b"data")}]}})
        for index, case in enumerate(cases):
            with self.subTest(index=index):
                artifact, callback = self.synthetic_archive(**case)
                directory = self.root / ("numeric-types-" + str(index))
                self.assertCode("CONFLICT", lambda: EvidenceClient(callback).download(
                    artifact, BoundedFileWriter(directory)))
                self.assertFalse(list(directory.glob("download-*/evidence.zip")))

    def test_invalid_raw_seal_json_is_a_structured_conflict(self):
        cases = [b'{"bad":' + value + b'}' for value in (b"NaN", b"Infinity", b"-Infinity")]
        cases.append(b'{"nested":' + b"[" * 10000 + b"0" + b"]" * 10000 + b"}")
        for index, raw in enumerate(cases):
            with self.subTest(index=index):
                artifact, _ = self.synthetic_archive()
                artifact["seal_sha256"] = _hash(raw)
                def callback(_tool, arguments):
                    return {"artifact_id": arguments["artifact_id"], "offset": 0,
                            "length": len(raw), "total_size": len(raw), "sha256": _hash(raw),
                            "chunk_sha256": _hash(raw), "data_base64": base64.b64encode(raw).decode(),
                            "eof": True}
                directory = self.root / ("invalid-json-" + str(index))
                self.assertCode("CONFLICT", lambda: EvidenceClient(callback).download(
                    artifact, BoundedFileWriter(directory)))
                self.assertEqual(list(directory.iterdir()), [])

    def test_invalid_raw_callback_result_is_a_structured_conflict(self):
        recursive = {}
        recursive["self"] = recursive
        cases = ({"bad": float("nan")}, {"bad": {1, 2}}, recursive)
        for index, result in enumerate(cases):
            with self.subTest(index=index):
                artifact, _ = self.synthetic_archive()
                directory = self.root / ("invalid-response-" + str(index))
                self.assertCode("CONFLICT", lambda: EvidenceClient(lambda *_: result).download(
                    artifact, BoundedFileWriter(directory)))
                self.assertEqual(list(directory.iterdir()), [])

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
