"""Private, immutable evidence publication; invoke sealing in a supervised helper.

The snapshot and persistence callbacks are trusted broker interfaces.  In particular,
quiescence is never decoded from a tool request.  Files are published before the
broker's durable registration; an unregistered publication is never readable here.
"""
from __future__ import annotations

import base64
import ctypes
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import uuid
import zipfile
from typing import Any, Callable, Iterator

from .contract import JobError

MAX_RESPONSE = 512 * 1024
DEFAULT_CHUNK = 64 * 1024
MAX_CHUNK = 256 * 1024
MANIFEST_NAME = "MANIFEST.json"
BROKER_EVENTS_NAME = "BROKER_EVENTS.json"
STOP_PROOF_NAME = "STOP_PROOF.json"
_ROLES = {"zip": "evidence.zip", "manifest": "manifest.json", "seal": "seal.json"}


class EvidenceError(JobError):
    """An intentionally path-free public error."""


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_name(name: str) -> str:
    if (not isinstance(name, str) or not name or len(name) > 240
            or not re.fullmatch(r"[A-Za-z0-9._/-]+", name)
            or name.startswith("/") or "//" in name
            or any(p in ("", ".", "..") for p in name.split("/"))
            or str(PurePosixPath(name)) != name):
        raise EvidenceError("CONFLICT", "unsafe evidence member")
    return name


def _integer(value: int, maximum: int) -> bool:
    return type(value) is int and 0 <= value <= maximum


def _same(st: os.stat_result) -> tuple[int, ...]:
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_uid,
            st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _directory(st: os.stat_result, owner: int) -> None:
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != owner or st.st_mode & 0o022:
        raise EvidenceError("CONFLICT", "evidence directory is not protected")


def _regular(st: os.stat_result, owner: int, maximum: int) -> None:
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
            or st.st_uid != owner or st.st_mode & 0o022 or st.st_size > maximum):
        raise EvidenceError("CONFLICT", "evidence member type, ownership or size changed")


def _root_descriptor(root: Path, owner: int) -> int:
    """Reject symlinks at every component, including ancestors of the admitted root."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise EvidenceError("UNSUPPORTED", "no-follow directory access unavailable")
    root = Path(root)
    if not root.is_absolute() or ".." in root.parts:
        raise EvidenceError("CONFLICT", "root must be an admitted absolute directory")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in root.parts[1:]:
            nxt = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=fd)
            os.close(fd)
            fd = nxt
        _directory(os.fstat(fd), owner)
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def _open_root(root: Path, owner: int) -> Iterator[int]:
    fd = _root_descriptor(root, owner)
    try:
        yield fd
        current = _root_descriptor(root, owner)
        try:
            original, entry = os.fstat(fd), os.fstat(current)
            if (original.st_dev, original.st_ino) != (entry.st_dev, entry.st_ino):
                raise EvidenceError("CONFLICT", "evidence root replaced during access")
        finally:
            os.close(current)
    finally:
        os.close(fd)


@contextmanager
def _open_member(root_fd: int, name: str, owner: int, maximum: int) -> Iterator[int]:
    components = _safe_name(name).split("/")
    directory = os.dup(root_fd)
    file_fd = None
    try:
        for component in components[:-1]:
            nxt = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=directory)
            try:
                _directory(os.fstat(nxt), owner)
            except Exception:
                os.close(nxt)
                raise
            os.close(directory)
            directory = nxt
        file_fd = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                          dir_fd=directory)
        _regular(os.fstat(file_fd), owner, maximum)
        yield file_fd
        _regular(os.fstat(file_fd), owner, maximum)
        # A descriptor remains valid after replacement: compare the directory entry too.
        entry = os.stat(components[-1], dir_fd=directory, follow_symlinks=False)
        if _same(entry) != _same(os.fstat(file_fd)):
            raise EvidenceError("CONFLICT", "evidence member replaced during read")
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(directory)


def _read(fd: int, maximum: int) -> bytes:
    original = os.fstat(fd)
    if original.st_size > maximum:
        raise EvidenceError("LIMIT_EXCEEDED", "evidence metadata too large")
    chunks = []
    left = maximum + 1
    while left:
        chunk = os.read(fd, min(DEFAULT_CHUNK, left))
        if not chunk:
            break
        chunks.append(chunk)
        left -= len(chunk)
    data = b"".join(chunks)
    if len(data) > maximum or len(data) != original.st_size or _same(original) != _same(os.fstat(fd)):
        raise EvidenceError("CONFLICT", "evidence changed during read")
    return data


def _file_digest(path: Path, *, expected_identity: tuple[int, ...] | None = None) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with _open_root(path.parent, os.geteuid()) as directory:
        with _open_member(directory, path.name, os.geteuid(), 2**53 - 1) as fd:
            before = os.fstat(fd)
            if expected_identity is not None and _same(before) != expected_identity:
                raise EvidenceError("CONFLICT", "generated evidence replaced before hashing")
            while block := os.read(fd, DEFAULT_CHUNK):
                size += len(block)
                if size > before.st_size:
                    raise EvidenceError("CONFLICT", "published evidence grew during hashing")
                digest.update(block)
            if size != before.st_size or _same(before) != _same(os.fstat(fd)):
                raise EvidenceError("CONFLICT", "published evidence changed during hashing")
    return size, digest.hexdigest()


def _publish_create_only(source: Path, destination: Path, *,
                         source_dir_fd: int = -100, destination_dir_fd: int = -100) -> None:
    """Linux atomic rename without replacement; no racy unlink of a staging entry."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise EvidenceError("UNSUPPORTED", "create-only atomic publication unavailable")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                       ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source_dir_fd, os.fsencode(source), destination_dir_fd, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, "create-only publication failed")


class _BoundedArchive:
    """Apply the archive limit to every write, including ZIP directory records."""

    def __init__(self, stream, maximum: int):
        self.stream, self.maximum = stream, maximum

    def write(self, data):
        if self.stream.tell() + len(data) > self.maximum:
            raise EvidenceError("LIMIT_EXCEEDED", "archive byte budget exceeded")
        return self.stream.write(data)

    def seek(self, *args):
        return self.stream.seek(*args)

    def tell(self):
        return self.stream.tell()

    def flush(self):
        return self.stream.flush()


@dataclass(frozen=True)
class QuiescenceProof:
    execution_id: str
    event_seq: int
    future_starts_blocked: bool
    tree_exited: bool
    collectors_stopped: bool
    writers_stopped: bool

    @property
    def complete(self) -> bool:
        return (bool(self.execution_id) and _integer(self.event_seq, 2**53 - 1)
                and all(v is True for v in (self.future_starts_blocked, self.tree_exited,
                                            self.collectors_stopped, self.writers_stopped)))


@dataclass(frozen=True)
class FrozenSnapshot:
    operation_id: str
    event_seq: int
    root: Path
    members: tuple[str, ...]
    quiescence: QuiescenceProof
    bindings: dict[str, Any] = field(default_factory=dict)
    previous_seal_id: str | None = None
    reconcile_id: str | None = None
    broker_events: tuple[dict, ...] = ()


class EvidenceStore:
    """An instance uses one broker-owned root and mandatory durable seal callbacks.

    The registration callback must durably persist the exact seal record or raise.
    ``is_registered`` must query that authoritative state, including after restart.
    The broker must authorize before calling if it doesn't supply ``authorize``.
    Neither IDs nor possession of files confer permission.  Sealing, full hashing,
    and source I/O run outside the broker control loop and its SQLite transactions.
    """

    def __init__(self, root: Path, *, snapshot_provider: Callable[[str], FrozenSnapshot],
                 register_seal: Callable[[dict], None],
                 is_registered: Callable[[str, str], bool],
                 list_seals: Callable[[str], list[dict]] | None = None,
                 authorize: Callable[[Any, str], None] | None = None,
                 max_members: int = 10000, max_source_bytes: int = 256 * 1024 * 1024,
                 max_artifact_bytes: int = 272 * 1024 * 1024,
                 max_seals: int = 1000, owner_uid: int | None = None):
        self.root = Path(root).absolute()
        if any(type(v) is not int or not 0 < v <= 2**53 - 1 for v in
               (max_members, max_source_bytes, max_artifact_bytes, max_seals)):
            raise EvidenceError("LIMIT_EXCEEDED", "invalid evidence store budget")
        self.owner = os.geteuid() if owner_uid is None else owner_uid
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with _open_root(self.root, self.owner):
            pass
        self.snapshot_provider = snapshot_provider
        self.register_seal = register_seal
        self.is_registered = is_registered
        self.list_seals = list_seals
        self.authorize = authorize
        self.max_members = max_members
        self.max_source_bytes = max_source_bytes
        self.max_artifact_bytes = max_artifact_bytes
        self.max_seals = max_seals
        self._cursor_key = secrets.token_bytes(32)

    def _auth(self, principal: Any, operation_id: str) -> None:
        if self.authorize is not None:
            self.authorize(principal, operation_id)

    def _snapshot(self, operation_id: str) -> FrozenSnapshot:
        snapshot = self.snapshot_provider(operation_id)
        if (not isinstance(snapshot, FrozenSnapshot) or snapshot.operation_id != operation_id
                or not isinstance(snapshot.quiescence, QuiescenceProof)
                or not snapshot.quiescence.complete
                or snapshot.event_seq != snapshot.quiescence.event_seq):
            raise EvidenceError("NOT_SEALED", "complete writer and execution stop proof required")
        if (len(snapshot.members) + 2 > self.max_members
                or len(set(snapshot.members)) != len(snapshot.members)):
            raise EvidenceError("LIMIT_EXCEEDED", "invalid evidence member count")
        for member in snapshot.members:
            _safe_name(member)
            if member in (MANIFEST_NAME, BROKER_EVENTS_NAME, STOP_PROOF_NAME):
                raise EvidenceError("CONFLICT", "reserved manifest name")
        if len(_json(snapshot.bindings)) > DEFAULT_CHUNK:
            raise EvidenceError("LIMIT_EXCEEDED", "evidence bindings too large")
        if not snapshot.broker_events:
            raise EvidenceError("NOT_SEALED", "frozen ledger event contents are required")
        if len(snapshot.broker_events) > 10000 or len(_json(snapshot.broker_events)) > 4 * 1024 * 1024:
            raise EvidenceError("LIMIT_EXCEEDED", "frozen ledger event budget exceeded")
        namespace = "reconcile" if snapshot.reconcile_id else "job"
        identity = snapshot.reconcile_id or snapshot.operation_id
        previous = -1
        for event in snapshot.broker_events:
            if (not isinstance(event, dict) or not _integer(event.get("seq"), snapshot.event_seq)
                    or event["seq"] <= previous or event.get("namespace") != namespace
                    or event.get("id") != identity):
                raise EvidenceError("CONFLICT", "frozen ledger event identity or ordering differs")
            previous = event["seq"]
        if previous != snapshot.event_seq:
            raise EvidenceError("CONFLICT", "frozen ledger events do not reach their cutoff")
        # Detach mutable caller containers before subsequent comparison.
        return FrozenSnapshot(snapshot.operation_id, snapshot.event_seq, Path(snapshot.root),
                              tuple(sorted(snapshot.members)), snapshot.quiescence,
                              json.loads(_json(snapshot.bindings)), snapshot.previous_seal_id,
                              snapshot.reconcile_id, tuple(json.loads(_json(snapshot.broker_events))))

    def _inventory(self, root_fd: int) -> dict[str, tuple[int, ...]]:
        result: dict[str, tuple[int, ...]] = {}
        visited = 0
        def walk(directory: int, prefix: str = "") -> None:
            nonlocal visited
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    visited += 1
                    if visited > self.max_members * 2:
                        raise EvidenceError("LIMIT_EXCEEDED", "too many evidence directory entries")
                    name = _safe_name(prefix + entry.name)
                    st = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(st.st_mode):
                        _directory(st, self.owner)
                        nxt = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                      dir_fd=directory)
                        try:
                            if _same(os.fstat(nxt)) != _same(st):
                                raise EvidenceError("CONFLICT", "evidence directory changed")
                            walk(nxt, name + "/")
                        finally:
                            os.close(nxt)
                    else:
                        _regular(st, self.owner, self.max_source_bytes)
                        result[name] = _same(st)
                        if len(result) > self.max_members:
                            raise EvidenceError("LIMIT_EXCEEDED", "too many evidence members")
        walk(root_fd)
        return result

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _sync_directory(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def seal(self, operation_id: str) -> dict:
        """Freeze and register one new version; errors preserve all original files.

        A failed/uncertain attempt is retained, never automatically retried here.
        A new reconciliation supplies a new snapshot and may publish a new seal.
        """
        return self._seal(operation_id, register=True)

    def publish_only(self, snapshot: FrozenSnapshot) -> dict:
        """Supervised helper publication without any ledger write or read access.

        The snapshot must be the helper's trusted, admitted snapshot.  The parent
        broker verifies helper exit and then durably registers the returned record.
        This method never calls registration and its files remain unreadable through
        the evidence API until that independent authoritative registration succeeds.
        """
        if self._snapshot(snapshot.operation_id) != snapshot:
            raise EvidenceError("CONFLICT", "helper snapshot differs from admitted snapshot")
        return self._seal(snapshot.operation_id, register=False)

    def _seal(self, operation_id: str, *, register: bool) -> dict:
        snapshot = self._snapshot(operation_id)
        virtual_members = {
            BROKER_EVENTS_NAME: _json({"schema_version": "lh-evidence-events-v1",
                "operation_id": operation_id, "reconcile_id": snapshot.reconcile_id,
                "event_seq": snapshot.event_seq, "events": snapshot.broker_events}),
            STOP_PROOF_NAME: _json({"schema_version": "lh-evidence-stop-proof-v1",
                "operation_id": operation_id, "reconcile_id": snapshot.reconcile_id,
                "proof": asdict(snapshot.quiescence)})}
        seal_id = str(uuid.uuid4())
        stage = self.root / ("staging-" + seal_id)
        destination = self.root / seal_id
        published = False
        try:
            if sum(1 for _ in self.root.iterdir()) >= self.max_seals * 2:
                raise EvidenceError("LIMIT_EXCEEDED", "evidence retention limit reached")
            stage.mkdir(mode=0o700)
            entries = []
            total = 0
            with _open_root(snapshot.root, self.owner) as root_fd:
                inventory = self._inventory(root_fd)
                if set(inventory) != set(snapshot.members):
                    raise EvidenceError("CONFLICT", "frozen evidence membership changed")
                total = sum(value[5] for value in inventory.values()) + sum(map(len, virtual_members.values()))
                if total > self.max_source_bytes:
                    raise EvidenceError("LIMIT_EXCEEDED", "evidence byte budget exceeded")
                archive_path = stage / _ROLES["zip"]
                archive_fd = os.open(archive_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(archive_fd, "w+b") as archive_stream:
                    with zipfile.ZipFile(_BoundedArchive(archive_stream, self.max_artifact_bytes),
                                         "w", compression=zipfile.ZIP_STORED,
                                         allowZip64=True) as archive:
                        for name in snapshot.members:
                            digest = hashlib.sha256()
                            copied = 0
                            info = zipfile.ZipInfo(name)
                            info.external_attr = (stat.S_IFREG | 0o600) << 16
                            with _open_member(root_fd, name, self.owner, self.max_source_bytes) as source:
                                original = os.fstat(source)
                                if _same(original) != inventory[name]:
                                    raise EvidenceError("CONFLICT", "frozen evidence member changed")
                                with archive.open(info, "w", force_zip64=True) as output:
                                    while block := os.read(source, DEFAULT_CHUNK):
                                        copied += len(block)
                                        if copied > original.st_size:
                                            raise EvidenceError("CONFLICT", "evidence member grew")
                                        digest.update(block)
                                        output.write(block)
                                if copied != original.st_size or _same(original) != _same(os.fstat(source)):
                                    raise EvidenceError("CONFLICT", "evidence member changed during seal")
                            entries.append({"name": name, "size": copied, "sha256": digest.hexdigest()})
                        for name, data in virtual_members.items():
                            info = zipfile.ZipInfo(name)
                            info.external_attr = (stat.S_IFREG | 0o600) << 16
                            archive.writestr(info, data)
                            entries.append({"name": name, "size": len(data), "sha256": _hash(data)})
                        manifest = {"schema_version": "lh-evidence-manifest-v1",
                                    "operation_id": operation_id, "seal_id": seal_id,
                                    "event_seq": snapshot.event_seq, "complete": True,
                                    "reconcile_id": snapshot.reconcile_id,
                                    "previous_seal_id": snapshot.previous_seal_id,
                                    "bindings": snapshot.bindings, "members": entries,
                                    "coverage": "members excludes MANIFEST.json; external seal binds archive and manifest"}
                        manifest_bytes = _json(manifest)
                        if len(manifest_bytes) > 4 * 1024 * 1024:
                            raise EvidenceError("LIMIT_EXCEEDED", "manifest byte budget exceeded")
                        info = zipfile.ZipInfo(MANIFEST_NAME)
                        info.external_attr = (stat.S_IFREG | 0o600) << 16
                        archive.writestr(info, manifest_bytes)
                    archive_stream.flush()
                    os.fsync(archive_stream.fileno())
                    generated_archive_identity = _same(os.fstat(archive_stream.fileno()))
                if inventory != self._inventory(root_fd) or snapshot != self._snapshot(operation_id):
                    raise EvidenceError("CONFLICT", "frozen evidence state changed during seal")
            self._write(stage / _ROLES["manifest"], manifest_bytes)
            zip_size, zip_digest = _file_digest(archive_path, expected_identity=generated_archive_identity)
            if zip_size > self.max_artifact_bytes:
                raise EvidenceError("LIMIT_EXCEEDED", "archive byte budget exceeded")
            artifacts = [{"artifact_id": seal_id + ".zip", "role": "zip", "size": zip_size,
                          "sha256": zip_digest},
                         {"artifact_id": seal_id + ".manifest", "role": "manifest",
                          "size": len(manifest_bytes), "sha256": _hash(manifest_bytes)}]
            seal = {"schema_version": "lh-evidence-seal-v1", "seal_id": seal_id,
                    "operation_id": operation_id, "event_seq": snapshot.event_seq,
                    "reconcile_id": snapshot.reconcile_id, "previous_seal_id": snapshot.previous_seal_id,
                    "bindings": snapshot.bindings, "complete": True,
                    "member_count": len(entries) + 1, "artifacts": artifacts}
            self._sync_directory(stage)
            # Both the directory and every published member are create-only.
            destination.mkdir(mode=0o700)
            published = True
            for role in ("zip", "manifest"):
                _publish_create_only(stage / _ROLES[role], destination / _ROLES[role])
            self._sync_directory(destination)
            self._sync_directory(stage)
            self._sync_directory(self.root)
            identities = {}
            with _open_root(destination, self.owner) as directory:
                for artifact in artifacts:
                    role = artifact["role"]
                    with _open_member(directory, _ROLES[role], self.owner, self.max_artifact_bytes) as fd:
                        identity = _same(os.fstat(fd))
                        if _file_digest(destination / _ROLES[role]) != (artifact["size"], artifact["sha256"]):
                            raise EvidenceError("CONFLICT", "published evidence differs from snapshot")
                        if identity != _same(os.fstat(fd)):
                            raise EvidenceError("CONFLICT", "published evidence changed while binding identity")
                        identities[role] = list(identity)
            # Persist the identity after atomic publication, which can change ctime.
            # The DB-authenticated external seal carries this binding across restart.
            seal["artifact_identities"] = identities
            seal_bytes = _json(seal)
            if len(seal_bytes) > DEFAULT_CHUNK:
                raise EvidenceError("LIMIT_EXCEEDED", "external seal byte budget exceeded")
            self._write(stage / _ROLES["seal"], seal_bytes)
            self._sync_directory(stage)
            _publish_create_only(stage / _ROLES["seal"], destination / _ROLES["seal"])
            self._sync_directory(destination)
            self._sync_directory(stage)
            self._sync_directory(self.root)
            if _file_digest(destination / _ROLES["seal"]) != (len(seal_bytes), _hash(seal_bytes)):
                raise EvidenceError("CONFLICT", "published seal differs from snapshot")
            with _open_root(destination, self.owner) as directory:
                for role, identity in identities.items():
                    with _open_member(directory, _ROLES[role], self.owner, self.max_artifact_bytes) as fd:
                        if list(_same(os.fstat(fd))) != identity:
                            raise EvidenceError("CONFLICT", "published identity changed before registration")
            record = dict(seal, seal_sha256=_hash(seal_bytes),
                          evidence_state="SEALED" if register else "STAGING")
            if not register:
                record["publication_state"] = "PUBLISHED_UNREGISTERED"
                record["artifacts"] = list(artifacts) + [{"artifact_id": seal_id + ".seal",
                    "role": "seal", "size": len(seal_bytes), "sha256": _hash(seal_bytes)}]
                return record
            self.register_seal(record)
            if not self.is_registered(seal_id, record["seal_sha256"]):
                raise EvidenceError("IO_UNCERTAIN", "seal registration not durable")
            return self._record(seal_id)
        except EvidenceError:
            if published:
                raise EvidenceError("IO_UNCERTAIN", "evidence publication durability unknown") from None
            raise
        except Exception:
            raise EvidenceError("IO_UNCERTAIN", "evidence publication durability unknown" if published
                                else "evidence snapshot unavailable") from None

    def _record(self, seal_id: str) -> dict:
        try:
            if str(uuid.UUID(seal_id)) != seal_id:
                raise ValueError
            with _open_root(self.root / seal_id, self.owner) as directory:
                with _open_member(directory, _ROLES["seal"], self.owner, DEFAULT_CHUNK) as fd:
                    data = _read(fd, DEFAULT_CHUNK)
            digest = _hash(data)
            if not self.is_registered(seal_id, digest):
                raise EvidenceError("NOT_SEALED", "evidence is not durably registered")
            record = json.loads(data)
            if (record.get("schema_version") != "lh-evidence-seal-v1"
                    or record.get("seal_id") != seal_id or record.get("complete") is not True):
                raise EvidenceError("CONFLICT", "invalid evidence seal")
            record["seal_sha256"] = digest
            record["evidence_state"] = "SEALED"
            record["artifacts"].append({"artifact_id": seal_id + ".seal", "role": "seal",
                                        "size": len(data), "sha256": digest})
            return record
        except EvidenceError:
            raise
        except FileNotFoundError:
            raise EvidenceError("NOT_FOUND", "evidence artifact not found") from None
        except (OSError, ValueError, KeyError, TypeError):
            raise EvidenceError("IO_UNCERTAIN", "evidence state unavailable") from None

    def owner_of(self, artifact_id: str) -> str:
        seal_id, _ = self._artifact(artifact_id)
        return self._record(seal_id)["operation_id"]

    @staticmethod
    def _artifact(artifact_id: str) -> tuple[str, str]:
        if not isinstance(artifact_id, str) or len(artifact_id) > 64:
            raise EvidenceError("NOT_FOUND", "evidence artifact not found")
        seal_id, separator, role = artifact_id.partition(".")
        if not separator or role not in _ROLES:
            raise EvidenceError("NOT_FOUND", "evidence artifact not found")
        return seal_id, role

    def manifest(self, operation_id: str, cursor: str | None = None, *,
                 principal: Any = None, page_size: int = 100) -> dict:
        self._auth(principal, operation_id)
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise EvidenceError("LIMIT_EXCEEDED", "invalid manifest page size")
        records = []
        try:
            if self.list_seals is not None:
                indexed = self.list_seals(operation_id)
                if not isinstance(indexed, list) or len(indexed) > self.max_seals:
                    raise EvidenceError("LIMIT_EXCEEDED", "registered evidence catalog exceeds budget")
                identities = set()
                for item in indexed:
                    if (not isinstance(item, dict) or not isinstance(item.get("seal_id"), str)
                            or item["seal_id"] in identities
                            or not isinstance(item.get("seal_sha256"), str)
                            or not re.fullmatch(r"[a-f0-9]{64}", item["seal_sha256"])):
                        raise EvidenceError("CONFLICT", "registered evidence catalog is invalid")
                    record = self._record(item["seal_id"])
                    if (record["operation_id"] != operation_id
                            or record["seal_sha256"] != item["seal_sha256"]):
                        raise EvidenceError("CONFLICT", "registered evidence binding differs")
                    identities.add(item["seal_id"])
                    records.append(record)
                paths = []
            else:
                # Synthetic standalone stores may lack the broker index.  Keep
                # their conservative scan bounded; production supplies list_seals.
                paths = []
                with os.scandir(self.root) as entries:
                    for entry in entries:
                        if len(paths) >= self.max_seals * 2:
                            raise EvidenceError("LIMIT_EXCEEDED", "evidence retention limit exceeded")
                        paths.append(Path(entry.name))
            for path in paths:
                if path.name.startswith("staging-"):
                    continue
                try:
                    record = self._record(path.name)
                except EvidenceError as exc:
                    if exc.code == "NOT_SEALED":
                        continue
                    raise
                if record["operation_id"] == operation_id:
                    records.append(record)
        except OSError:
            raise EvidenceError("IO_UNCERTAIN", "evidence catalog unavailable") from None
        if not records:
            raise EvidenceError("NOT_SEALED", "no complete evidence has been sealed")
        records.sort(key=lambda r: (r["event_seq"], r["seal_id"]))
        items = [dict(a, operation_id=operation_id, seal_id=r["seal_id"],
                      event_seq=r["event_seq"], reconcile_id=r["reconcile_id"],
                      seal_sha256=r["seal_sha256"])
                 for r in records for a in r["artifacts"]]
        version = _hash(_json(items))
        offset = 0
        binding = {"operation_id": operation_id, "principal": str(principal), "version": version}
        if cursor is not None:
            try:
                if not isinstance(cursor, str) or len(cursor) > 2048 or not re.fullmatch(r"[A-Za-z0-9_-]+", cursor):
                    raise ValueError
                decoded = base64.urlsafe_b64decode((cursor + "=" * (-len(cursor) % 4)).encode("ascii"))
                raw, signature = decoded[:-32], decoded[-32:]
                if not hmac.compare_digest(hmac.new(self._cursor_key, raw, "sha256").digest(), signature):
                    raise ValueError
                parsed = json.loads(raw)
                offset = parsed.pop("offset")
                if parsed != binding or not _integer(offset, len(items)):
                    raise ValueError
            except (ValueError, TypeError, KeyError, UnicodeError):
                raise EvidenceError("CONFLICT", "manifest cursor expired or changed") from None
        page = items[offset:offset + page_size]
        next_cursor = None
        if offset + len(page) < len(items):
            raw = _json(dict(binding, offset=offset + len(page)))
            next_cursor = base64.urlsafe_b64encode(raw + hmac.new(self._cursor_key, raw, "sha256").digest()).decode("ascii").rstrip("=")
        result = {"schema_version": "lh-evidence-page-v1", "operation_id": operation_id,
                  "catalog_digest": version, "artifacts": page, "next_cursor": next_cursor}
        if len(_json(result)) > MAX_RESPONSE:
            raise EvidenceError("LIMIT_EXCEEDED", "evidence response budget exceeded")
        self._auth(principal, operation_id)
        return result

    def read_chunk(self, artifact_id: str, offset: int = 0, length: int = DEFAULT_CHUNK,
                   expected_digest: str | None = None, *, expected_sha256: str | None = None,
                   principal: Any = None) -> dict:
        if expected_digest is None:
            expected_digest = expected_sha256
        elif expected_sha256 is not None and expected_sha256 != expected_digest:
            raise EvidenceError("CONFLICT", "conflicting expected digests")
        if (not _integer(offset, self.max_artifact_bytes) or type(length) is not int
                or not 1 <= length <= MAX_CHUNK):
            raise EvidenceError("LIMIT_EXCEEDED", "invalid evidence chunk range")
        seal_id, role = self._artifact(artifact_id)
        record = self._record(seal_id)
        self._auth(principal, record["operation_id"])
        artifact = next(a for a in record["artifacts"] if a["role"] == role)
        if expected_digest != artifact["sha256"]:
            raise EvidenceError("CONFLICT", "evidence digest does not match")
        if offset > artifact["size"]:
            raise EvidenceError("CONFLICT", "evidence offset exceeds size")
        try:
            with _open_root(self.root / seal_id, self.owner) as root_fd:
                with _open_member(root_fd, _ROLES[role], self.owner, self.max_artifact_bytes) as fd:
                    original = os.fstat(fd)
                    if original.st_size != artifact["size"]:
                        raise EvidenceError("CONFLICT", "sealed evidence size changed")
                    if role == "seal":
                        # Small external seal is authenticated against the DB on every read.
                        raw = _read(fd, DEFAULT_CHUNK)
                        if _hash(raw) != expected_digest:
                            raise EvidenceError("CONFLICT", "sealed evidence digest changed")
                        selected = raw[offset:offset + length]
                    else:
                        expected_identity = record.get("artifact_identities", {}).get(role)
                        if expected_identity != list(_same(original)):
                            raise EvidenceError("CONFLICT", "sealed evidence identity changed")
                        os.lseek(fd, offset, os.SEEK_SET)
                        selected = bytearray()
                        remaining = min(length, original.st_size - offset)
                        while remaining:
                            block = os.read(fd, min(DEFAULT_CHUNK, remaining))
                            if not block:
                                raise EvidenceError("CONFLICT", "sealed evidence was truncated")
                            selected.extend(block)
                            remaining -= len(block)
                    if _same(original) != _same(os.fstat(fd)):
                        raise EvidenceError("CONFLICT", "sealed evidence changed")
            self._auth(principal, record["operation_id"])
            result = {"artifact_id": artifact_id, "offset": offset, "length": len(selected),
                      "total_size": artifact["size"], "sha256": expected_digest,
                      "chunk_sha256": _hash(selected),
                      "data_base64": base64.b64encode(selected).decode("ascii"),
                      "eof": offset + len(selected) == artifact["size"]}
            if len(_json(result)) > MAX_RESPONSE:
                raise EvidenceError("LIMIT_EXCEEDED", "evidence response budget exceeded")
            return result
        except OSError:
            raise EvidenceError("IO_UNCERTAIN", "evidence bytes unavailable") from None
