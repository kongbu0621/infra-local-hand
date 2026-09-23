"""Host-side evidence assembly: authenticated tool callback -> bounded file writer.

No token, URL, login flow or model-output callback is accepted.  The host gives this
component raw tool results directly.  E4 must independently prove that bridge in
the actual client; this module does not claim that ChatGPT automatically saves data.
"""
from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile
import zlib
from typing import Any, Callable, Protocol

from .evidence import (DEFAULT_CHUNK, MAX_CHUNK, MAX_RESPONSE, MANIFEST_NAME,
                       EvidenceError, _close_descriptors, _hash, _integer, _json, _open_member, _open_root,
                       _publish_create_only, _read, _regular, _safe_name, _same,
                       _sync_directory_ancestry)


def _decode_json(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise EvidenceError("CONFLICT", "duplicate evidence metadata key")
            result[key] = value
        return result
    def reject_constant(_value):
        raise ValueError("non-finite evidence metadata")
    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (UnicodeError, ValueError, RecursionError):
        raise EvidenceError("CONFLICT", "invalid evidence metadata") from None


def _descriptor(artifact: dict, maximum: int) -> dict:
    if (not isinstance(artifact, dict) or not isinstance(artifact.get("artifact_id"), str)
            or artifact.get("role") not in ("zip", "manifest", "seal")
            or not _integer(artifact.get("size"), maximum)
            or not isinstance(artifact.get("sha256"), str)
            or len(artifact["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in artifact["sha256"])):
        raise EvidenceError("CONFLICT", "invalid evidence descriptor")
    _safe_name(artifact["artifact_id"])
    if ("/" in artifact["artifact_id"]
            or artifact["artifact_id"].rpartition(".")[2] != artifact["role"]):
        raise EvidenceError("CONFLICT", "invalid artifact identifier")
    return {k: artifact[k] for k in ("artifact_id", "role", "size", "sha256")}


def _validate_compression(path: Path, info: zipfile.ZipInfo) -> None:
    """Verify the complete stored/deflated member without trusting declared EOF.

    ZipExtFile stops at the declared uncompressed size and can accept a truncated
    deflate stream if the available prefix has the expected CRC. Its other codecs
    also do not all offer a bounded decompression call. The producer uses stored
    members; retain deflate compatibility with explicit input and output bounds.
    """
    if info.compress_type == zipfile.ZIP_STORED:
        if info.compress_size != info.file_size:
            raise EvidenceError("CONFLICT", "stored member size mismatch")
        return
    if info.compress_type != zipfile.ZIP_DEFLATED:
        raise EvidenceError("CONFLICT", "unsupported evidence member compression")
    with path.open("rb") as raw:
        raw.seek(info.header_offset)
        header = raw.read(30)
        if len(header) != 30 or header[:4] != b"PK\x03\x04":
            raise EvidenceError("CONFLICT", "invalid archive member header")
        name_size = int.from_bytes(header[26:28], "little")
        extra_size = int.from_bytes(header[28:30], "little")
        raw.seek(name_size + extra_size, os.SEEK_CUR)
        decoder = zlib.decompressobj(-zlib.MAX_WBITS)
        remaining, produced = info.compress_size, 0
        while remaining:
            block = raw.read(min(DEFAULT_CHUNK, remaining))
            if not block:
                raise EvidenceError("CONFLICT", "compressed evidence member is truncated")
            remaining -= len(block)
            while block:
                output = decoder.decompress(block, min(DEFAULT_CHUNK, info.file_size - produced + 1))
                produced += len(output)
                if produced > info.file_size:
                    raise EvidenceError("CONFLICT", "compressed member exceeded declared size")
                if decoder.unused_data or decoder.eof and remaining:
                    raise EvidenceError("CONFLICT", "compressed member has trailing data")
                block = decoder.unconsumed_tail
        if not decoder.eof or produced != info.file_size:
            raise EvidenceError("CONFLICT", "compressed evidence member is incomplete")


class BoundedWriter(Protocol):
    """A host capability; private state and bytes never enter model context."""
    max_bytes: int
    def prepare(self, artifact: dict) -> int: ...
    def write(self, offset: int, data: bytes) -> None: ...
    def finish(self, validator: Callable[[Path], None]) -> Path: ...
    def close(self) -> None: ...


class BoundedFileWriter:
    """Exclusive private partial file and fsynced append-only checkpoint journal.

    A reopened writer verifies the saved prefix digest before resuming.  Bytes not
    covered by the last durable checkpoint are discarded only from its own locked
    partial file.  A final filename is published atomically without replacement.
    """

    def __init__(self, private_directory: Path, *, max_bytes: int = 272 * 1024 * 1024):
        if not _integer(max_bytes, 2**53 - 1) or max_bytes == 0:
            raise EvidenceError("LIMIT_EXCEEDED", "invalid writer byte budget")
        self.root = Path(private_directory).absolute()
        self.owner = os.geteuid()
        with _open_root(self.root, self.owner, create=True):
            pass
        self.max_bytes = max_bytes
        self._lock = None
        self._fd = None
        self._journal = None
        self._directory_fd = None
        self._completed = False
        self.offset = 0

    def prepare(self, artifact: dict) -> int:
        if self._lock is not None:
            raise EvidenceError("CONFLICT", "writer is already active")
        self.artifact = _descriptor(artifact, self.max_bytes)
        self._completed = False
        key = _hash(_json(self.artifact))
        self.directory = self.root / ("download-" + key)
        with _open_root(self.root, self.owner) as root:
            try:
                os.mkdir(self.directory.name, mode=0o700, dir_fd=root)
            except FileExistsError:
                pass
        self.partial = self.directory / "partial.bin"
        self.final = self.directory / ("evidence.zip" if self.artifact["role"] == "zip" else "evidence.json")
        try:
            with _open_root(self.directory, self.owner) as directory:
                self._directory_fd = os.dup(directory)
                self._lock = os.open("lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                                     0o600, dir_fd=directory)
                _regular(os.fstat(self._lock), self.owner, 0)
                try:
                    fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise EvidenceError("RESOURCE_BUSY", "evidence writer already active") from None
                try:
                    fd = os.open("binding.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory)
                except FileExistsError:
                    with _open_member(directory, "binding.json", self.owner, DEFAULT_CHUNK) as fd:
                        if _decode_json(_read(fd, DEFAULT_CHUNK)) != self.artifact:
                            raise EvidenceError("CONFLICT", "writer binding changed")
                else:
                    failure = None
                    try:
                        self._write_all(fd, _json(self.artifact))
                        os.fsync(fd)
                    except BaseException as error:
                        failure = error
                        raise
                    finally:
                        _close_descriptors(fd, failure=failure)
                try:
                    with _open_member(directory, self.final.name, self.owner, self.max_bytes) as final:
                        self._verify_descriptor(final)
                    self._completed = True
                    self.offset = self.artifact["size"]
                    return self.offset
                except FileNotFoundError:
                    pass
                self._fd = os.open("partial.bin", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                                   0o600, dir_fd=directory)
                _regular(os.fstat(self._fd), self.owner, self.max_bytes)
                self._journal = os.open("checkpoints.jsonl", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                                        0o600, dir_fd=directory)
                _regular(os.fstat(self._journal), self.owner, 4 * 1024 * 1024)
                journal = _read(self._journal, 4 * 1024 * 1024)
                complete = journal.rsplit(b"\n", 1)[0] + b"\n" if b"\n" in journal else b""
                checkpoint = {"offset": 0, "sha256": _hash(b"")}
                previous = 0
                for line in complete.splitlines():
                    item = _decode_json(line)
                    if (set(item) != {"offset", "sha256"}
                            or not _integer(item["offset"], self.artifact["size"])
                            or item["offset"] <= previous):
                        raise EvidenceError("CONFLICT", "invalid evidence checkpoint sequence")
                    checkpoint = item
                    previous = item["offset"]
                self.offset = checkpoint["offset"]
                if os.fstat(self._fd).st_size < self.offset:
                    raise EvidenceError("CONFLICT", "evidence partial file is truncated")
                self._digest = hashlib.sha256()
                remaining = self.offset
                while remaining:
                    block = os.read(self._fd, min(DEFAULT_CHUNK, remaining))
                    if not block:
                        raise EvidenceError("CONFLICT", "evidence partial file is truncated")
                    self._digest.update(block)
                    remaining -= len(block)
                if self._digest.hexdigest() != checkpoint["sha256"]:
                    raise EvidenceError("CONFLICT", "evidence checkpoint digest mismatch")
                os.ftruncate(self._fd, self.offset)
                os.ftruncate(self._journal, len(complete))
                os.lseek(self._journal, 0, os.SEEK_END)
                os.fsync(directory)
                self._assert_bound()
                return self.offset
        except BaseException as failure:
            self._close(failure)
            raise

    def _assert_bound(self) -> None:
        """The lock, writable descriptors and named private directory stay one object."""
        if self._directory_fd is None:
            raise EvidenceError("CONFLICT", "evidence writer directory is not active")
        try:
            with _open_root(self.directory, self.owner) as current:
                old, new = os.fstat(self._directory_fd), os.fstat(current)
                if (old.st_dev, old.st_ino) != (new.st_dev, new.st_ino):
                    raise EvidenceError("CONFLICT", "evidence writer directory replaced")
            for name, fd, maximum in (("lock", self._lock, 0),
                    ("partial.bin", self._fd, self.max_bytes),
                    ("checkpoints.jsonl", self._journal, 4 * 1024 * 1024)):
                if fd is not None:
                    original = os.fstat(fd)
                    _regular(original, self.owner, maximum)
                    entry = os.stat(name, dir_fd=self._directory_fd, follow_symlinks=False)
                    if _same(original) != _same(entry):
                        raise EvidenceError("CONFLICT", "evidence writer member replaced")
        except OSError:
            raise EvidenceError("CONFLICT", "evidence writer binding unavailable") from None

    @staticmethod
    def _write_all(fd: int, data: bytes) -> None:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise EvidenceError("IO_UNCERTAIN", "evidence writer made no progress")
            view = view[written:]

    def _verify_descriptor(self, fd: int) -> None:
        before = os.fstat(fd)
        _regular(before, self.owner, self.max_bytes)
        digest = hashlib.sha256()
        total = 0
        while block := os.read(fd, DEFAULT_CHUNK):
            total += len(block)
            if total > self.artifact["size"]:
                raise EvidenceError("CONFLICT", "download exceeded expected size")
            digest.update(block)
        if (total != self.artifact["size"] or digest.hexdigest() != self.artifact["sha256"]
                or _same(before) != _same(os.fstat(fd))):
            raise EvidenceError("CONFLICT", "download size or complete digest mismatch")

    def write(self, offset: int, data: bytes) -> None:
        if (self._fd is None or self._completed or offset != self.offset
                or not isinstance(data, bytes) or not 0 < len(data) <= MAX_CHUNK
                or offset + len(data) > self.artifact["size"]):
            raise EvidenceError("CONFLICT", "invalid bounded evidence write")
        self._assert_bound()
        _regular(os.fstat(self._fd), self.owner, self.max_bytes)
        if os.fstat(self._fd).st_size != offset:
            raise EvidenceError("CONFLICT", "partial evidence changed")
        self._write_all(self._fd, data)
        os.fsync(self._fd)
        self._digest.update(data)
        self.offset += len(data)
        checkpoint = _json({"offset": self.offset, "sha256": self._digest.hexdigest()}) + b"\n"
        if os.fstat(self._journal).st_size + len(checkpoint) > 4 * 1024 * 1024:
            raise EvidenceError("LIMIT_EXCEEDED", "checkpoint journal budget exceeded")
        self._write_all(self._journal, checkpoint)
        os.fsync(self._journal)
        self._assert_bound()

    def finish(self, validator: Callable[[Path], None]) -> Path:
        if self._lock is None or self.offset != self.artifact["size"]:
            raise EvidenceError("CONFLICT", "evidence download is incomplete")
        self._assert_bound()
        path = self.final if self._completed else self.partial
        directory = self._directory_fd
        with _open_member(directory, path.name, self.owner, self.max_bytes) as fd:
            self._verify_descriptor(fd)
            identity = _same(os.fstat(fd))
            # This host writer already requires Linux (flock and renameat2).  Give
            # the validator the pinned file, so a parent rename cannot redirect it.
            pinned_path = Path("/proc/self/fd") / str(fd)
            if not pinned_path.exists():
                raise EvidenceError("UNSUPPORTED", "descriptor-backed validation unavailable")
            validator(pinned_path)
            if _same(os.fstat(fd)) != identity:
                raise EvidenceError("CONFLICT", "evidence changed while validating")
            self._assert_bound()
        if not self._completed:
            _publish_create_only(Path(self.partial.name), Path(self.final.name),
                                 source_dir_fd=directory, destination_dir_fd=directory)
            # Renaming changes ctime.  Rehash the published descriptor and require
            # the same inode, then check the directory binding before returning it.
            self._completed = True
            fd, self._fd = self._fd, None
            try:
                os.close(fd)
            except OSError:
                # close may have released fd before reporting failure.  Keep the
                # published file and never retry a possibly reused descriptor.
                raise EvidenceError("IO_UNCERTAIN", "published evidence descriptor cleanup unresolved") from None
        with _open_member(directory, self.final.name, self.owner, self.max_bytes) as fd:
            final_stat = os.fstat(fd)
            if (final_stat.st_dev, final_stat.st_ino) != identity[:2]:
                raise EvidenceError("CONFLICT", "evidence replaced at publication")
            self._verify_descriptor(fd)
            os.fsync(fd)
            # A retained final file may be from a rename whose directory fsync
            # failed. Retry all durability barriers for completed downloads too,
            # while retaining the verified file and its full identity: fsync can
            # block long enough for a same-inode rewrite or entry replacement.
            os.fsync(directory)
            with _open_root(self.root, self.owner):
                _sync_directory_ancestry(self.root, self.owner)
            self._assert_bound()
            if _same(os.fstat(fd)) != _same(final_stat):
                raise EvidenceError("CONFLICT", "evidence changed during persistence")
        return self.final

    def close(self) -> None:
        self._close()

    def _close(self, failure: BaseException | None = None) -> None:
        close_failed = False
        for attribute in ("_fd", "_journal", "_lock", "_directory_fd"):
            fd = getattr(self, attribute, None)
            if fd is not None:
                setattr(self, attribute, None)
                try:
                    os.close(fd)
                except OSError:
                    # Attempt every held descriptor once, even after a failure.
                    # Retrying close is unsafe if its number has been reused.
                    close_failed = True
        if close_failed:
            if failure is not None:
                failure.add_note("Evidence writer descriptor cleanup also failed")
            else:
                raise EvidenceError("IO_UNCERTAIN", "evidence writer descriptor cleanup unresolved")

    def __enter__(self):
        return self

    def __exit__(self, _type, exception, _traceback):
        self._close(exception)


class EvidenceClient:
    """Callback signature: callback(tool_name, strict_arguments) -> raw result dict.

    Download receives a descriptor from ``lh_evidence_manifest`` and a host writer.
    Interruptions propagate; the caller resumes with the same descriptor and writer
    directory.  No operation submission, second authentication or automatic new ID
    is performed.  Only the final validated path is returned.
    """

    def __init__(self, authenticated_tool_callback: Callable[[str, dict], dict], *,
                 chunk_size: int = DEFAULT_CHUNK, max_members: int = 10000):
        if (type(chunk_size) is not int or not 1 <= chunk_size <= MAX_CHUNK
                or type(max_members) is not int or not 1 <= max_members <= 2**53 - 1):
            raise EvidenceError("LIMIT_EXCEEDED", "invalid download budget")
        self.callback = authenticated_tool_callback
        self.chunk_size = chunk_size
        self.max_members = max_members

    def _chunk(self, artifact_id: str, digest: str, offset: int, length: int,
               total: int | None = None) -> tuple[bytes, int]:
        result = self.callback("lh_evidence_read_chunk", {"artifact_id": artifact_id,
                               "offset": offset, "length": length, "expected_sha256": digest})
        if not isinstance(result, dict):
            raise EvidenceError("LIMIT_EXCEEDED", "invalid evidence response budget")
        try:
            response_size = len(_json(result))
        except (TypeError, ValueError, RecursionError):
            raise EvidenceError("CONFLICT", "invalid evidence response metadata") from None
        if response_size > MAX_RESPONSE:
            raise EvidenceError("LIMIT_EXCEEDED", "invalid evidence response budget")
        if (result.get("artifact_id") != artifact_id or result.get("sha256") != digest
                or type(result.get("offset")) is not int or result["offset"] != offset
                or not _integer(result.get("total_size"), 2**53 - 1)
                or total is not None and result["total_size"] != total
                or not _integer(result.get("length"), length)
                or type(result.get("eof")) is not bool
                or result["eof"] != (offset + result["length"] == result["total_size"])):
            raise EvidenceError("CONFLICT", "evidence chunk binding mismatch")
        try:
            encoded = result["data_base64"]
            if not isinstance(encoded, str) or len(encoded) > (MAX_CHUNK + 2) // 3 * 4:
                raise ValueError
            data = base64.b64decode(encoded, validate=True)
        except (KeyError, ValueError, binascii.Error):
            raise EvidenceError("CONFLICT", "invalid evidence chunk encoding") from None
        if (len(data) != result["length"] or _hash(data) != result.get("chunk_sha256")
                or offset + len(data) > result["total_size"]
                or not data and offset < result["total_size"]):
            raise EvidenceError("CONFLICT", "evidence chunk digest or size mismatch")
        return data, result["total_size"]

    def _seal(self, artifact: dict) -> dict:
        digest = artifact.get("seal_sha256")
        seal_id = artifact.get("seal_id")
        if (not isinstance(digest, str) or len(digest) != 64 or not isinstance(seal_id, str)
                or artifact.get("artifact_id") != seal_id + ".zip"):
            raise EvidenceError("CONFLICT", "external seal binding is missing")
        raw, total = self._chunk(seal_id + ".seal", digest, 0, DEFAULT_CHUNK)
        if total != len(raw) or total > DEFAULT_CHUNK or _hash(raw) != digest:
            raise EvidenceError("CONFLICT", "external seal digest or size mismatch")
        seal = _decode_json(raw)
        if (seal.get("schema_version") != "lh-evidence-seal-v1"
                or seal.get("seal_id") != seal_id or seal.get("complete") is not True
                or seal.get("operation_id") != artifact.get("operation_id")
                or seal.get("reconcile_id") != artifact.get("reconcile_id")
                or not _integer(seal.get("event_seq"), 2**53 - 1)
                or not _integer(artifact.get("event_seq"), 2**53 - 1)
                or seal.get("event_seq") != artifact.get("event_seq")):
            raise EvidenceError("CONFLICT", "external seal identity mismatch")
        try:
            entries = seal["artifacts"]
            if (not isinstance(entries, list) or len(entries) != 2
                    or {a["role"] for a in entries} != {"zip", "manifest"}):
                raise EvidenceError("CONFLICT", "external seal artifact list invalid")
            for entry in entries:
                descriptor = _descriptor(entry, 2**53 - 1)
                if descriptor["artifact_id"] != seal_id + "." + descriptor["role"]:
                    raise EvidenceError("CONFLICT", "external seal artifact identity mismatch")
            zip_entry = next(a for a in entries if a["role"] == "zip")
            if _descriptor(zip_entry, 2**53 - 1) != _descriptor(artifact, 2**53 - 1):
                raise EvidenceError("CONFLICT", "external seal archive mismatch")
        except (KeyError, TypeError, StopIteration):
            raise EvidenceError("CONFLICT", "external seal artifact list invalid") from None
        return seal

    def _validate_zip(self, path: Path, artifact: dict, seal: dict, maximum: int) -> None:
        try:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                if not _integer(seal["member_count"], 2**53 - 1):
                    raise EvidenceError("CONFLICT", "archive member count is not an integer")
                if len(infos) > self.max_members + 1 or len(infos) != seal["member_count"]:
                    raise EvidenceError("LIMIT_EXCEEDED", "archive member count mismatch")
                names = []
                for info in infos:
                    # ZipInfo truncates filename at NUL. Validate the decoded
                    # original too, so the manifest cannot hide an unsafe name.
                    if _safe_name(info.orig_filename) != info.filename:
                        raise EvidenceError("CONFLICT", "archive member name changed")
                    names.append(_safe_name(info.filename))
                    mode = info.external_attr >> 16
                    if (not stat.S_ISREG(mode) or info.is_dir() or info.flag_bits & 1
                            or info.file_size > maximum):
                        raise EvidenceError("CONFLICT", "archive has an unsafe member")
                if len(set(names)) != len(names) or names.count(MANIFEST_NAME) != 1:
                    raise EvidenceError("CONFLICT", "archive has duplicate or missing members")
                if sum(info.file_size for info in infos) > maximum:
                    raise EvidenceError("LIMIT_EXCEEDED", "archive expansion budget exceeded")
                if archive.getinfo(MANIFEST_NAME).file_size > 4 * 1024 * 1024:
                    raise EvidenceError("LIMIT_EXCEEDED", "archive manifest too large")
                for info in infos:
                    _validate_compression(path, info)
                raw = archive.read(MANIFEST_NAME)
                manifests = [a for a in seal["artifacts"] if a["role"] == "manifest"]
                if (len(manifests) != 1 or manifests[0]["sha256"] != _hash(raw)
                        or manifests[0]["size"] != len(raw)):
                    raise EvidenceError("CONFLICT", "archive manifest differs from external seal")
                manifest = _decode_json(raw)
                if (manifest.get("schema_version") != "lh-evidence-manifest-v1"
                        or manifest.get("operation_id") != seal["operation_id"]
                        or manifest.get("seal_id") != seal["seal_id"]
                        or not _integer(manifest.get("event_seq"), 2**53 - 1)
                        or manifest.get("event_seq") != seal["event_seq"]
                        or not isinstance(manifest.get("bindings"), dict)
                        # Python container equality equates true with 1 (and
                        # integer with float). Preserve the JSON value types.
                        or any(_json(manifest.get(field)) != _json(seal.get(field)) for field in
                               ("bindings", "reconcile_id", "previous_seal_id"))
                        or manifest.get("complete") is not True):
                    raise EvidenceError("CONFLICT", "archive manifest identity mismatch")
                members = manifest["members"]
                if (not isinstance(members, list) or len(members) != len(infos) - 1
                        or {m["name"] for m in members} != set(names) - {MANIFEST_NAME}):
                    raise EvidenceError("CONFLICT", "archive member manifest mismatch")
                for member in members:
                    if set(member) != {"name", "size", "sha256"}:
                        raise EvidenceError("CONFLICT", "invalid archive member record")
                    info = archive.getinfo(member["name"])
                    if (not _integer(member["size"], maximum)
                            or info.file_size != member["size"]):
                        raise EvidenceError("CONFLICT", "archive member size mismatch")
                    digest = hashlib.sha256()
                    read_size = 0
                    with archive.open(info) as stream:
                        while block := stream.read(DEFAULT_CHUNK):
                            read_size += len(block)
                            if read_size > info.file_size:
                                raise EvidenceError("CONFLICT", "archive member exceeded budget")
                            digest.update(block)
                    if read_size != member["size"] or digest.hexdigest() != member["sha256"]:
                        raise EvidenceError("CONFLICT", "archive member digest mismatch")
        except EvidenceError:
            raise
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError, zlib.error):
            raise EvidenceError("CONFLICT", "archive verification failed") from None

    def download(self, artifact: dict, writer: BoundedWriter) -> Path:
        descriptor = _descriptor(artifact, writer.max_bytes)
        try:
            seal = self._seal(artifact) if descriptor["role"] == "zip" else None
            offset = writer.prepare(descriptor)
            while offset < descriptor["size"]:
                data, _ = self._chunk(descriptor["artifact_id"], descriptor["sha256"],
                                      offset, min(self.chunk_size, descriptor["size"] - offset),
                                      descriptor["size"])
                writer.write(offset, data)
                offset += len(data)
            final = writer.finish(lambda path: self._validate_zip(path, artifact, seal, writer.max_bytes)
                                  if seal is not None else None)
        except BaseException as failure:
            try:
                writer.close()
            except Exception:
                failure.add_note("Evidence writer descriptor cleanup also failed")
            raise
        else:
            writer.close()
            return final
