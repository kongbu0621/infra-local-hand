"""Q1 administrative, synchronous, create-only launch journal.

Use ONLY in the independently supervised administrative controller, never in a
listener/broker control thread: opening, reading, writing and fsync can block.
The provisioner must supply a distinct, capacity-limited local control filesystem
and pin this pre-created directory. This module bounds its own retained payload;
it does not establish filesystem capacity, locality, or service responsiveness.
The query worker must not have access to this directory or inherit its FDs.

An intent is the permanent consumption of a launch opportunity. Only the call
which durably creates it invokes the trusted delivery callback. Recovery never
replays that callback, including a crash BEFORE delivery. Every allocation stays
reserved forever in this Q1 implementation; there is deliberately no GC/release.
This is an internal management primitive, not public Q2 request admission.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat
import threading
import time

from .admission import Rejected, UUID, fields, integer, path, require, strict_json, token
from .supervision import Binding, bind_query


MAX_INTENTS = 32
MAX_FILE_BYTES = 4096
MAX_FILES = 1 + MAX_INTENTS * 3
_RECORD_NAME = re.compile(r"([0-9a-f]{32})\.(intent|invocation|unknown)\.json")


def _encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def _binding_value(binding):
    require(type(binding) is Binding, "BINDING_REQUIRED")
    checked = bind_query(binding.manifest, slot_ref=binding.slot.ref,
                         generation=binding.slot.generation, request_id=binding.request_id,
                         allocation_digest=binding.allocation_digest, execution_id=binding.execution_id,
                         phase=binding.phase, now_ns=binding.issued_ns,
                         phase_deadline_ns=binding.deadline_ns)
    require(checked == binding, "BINDING_CHANGED")
    manifest = binding.manifest
    value = {"schema": "local-hand-quota-q1-intent/v1", "manifest_digest": manifest.digest,
            "authority_digest": manifest.authority_digest,
            "installation_digest": manifest.installation_digest, "source_commit": manifest.source_commit,
            "epoch": manifest.epoch, "boot_id": manifest.boot_id,
            "request_id": binding.request_id, "allocation_digest": binding.allocation_digest,
            "execution_id": binding.execution_id, "phase": binding.phase, "slot_ref": binding.slot.ref,
            "generation": binding.slot.generation, "issued_ns": binding.issued_ns,
            "deadline_ns": binding.deadline_ns, "unit": binding.unit, "cgroup": binding.cgroup,
            "root_device": binding.slot.root.device, "root_inode": binding.slot.root.inode,
            "filesystem_uuid": binding.slot.filesystem_uuid, "filesystem": binding.slot.filesystem,
            "project_id": binding.slot.project_id, "xflags": binding.slot.xflags,
            "hard_bytes": binding.slot.hard_bytes}
    # Persist exactly the schema the recovery reader accepts, before any delivery.
    return _validate_intent(value)


def _validate_intent(value):
    fields(value, ("schema", "manifest_digest", "authority_digest", "installation_digest", "source_commit",
                   "epoch", "boot_id", "request_id", "allocation_digest", "execution_id", "phase",
                   "slot_ref", "generation", "issued_ns", "deadline_ns", "unit", "cgroup",
                   "root_device", "root_inode", "filesystem_uuid", "filesystem", "project_id", "xflags",
                   "hard_bytes"))
    require(value["schema"] == "local-hand-quota-q1-intent/v1", "INTENT_SCHEMA")
    for field in ("manifest_digest", "authority_digest", "installation_digest", "allocation_digest"):
        token(value[field], r"[0-9a-f]{64}")
    token(value["source_commit"], r"[0-9a-f]{40}")
    for field in ("epoch", "request_id", "execution_id", "generation"):
        token(value[field], r"[0-9a-f]{32}")
    token(value["boot_id"], UUID)
    token(value["filesystem_uuid"], UUID)
    token(value["filesystem"], r"ext4|xfs")
    integer(value["root_device"])
    integer(value["root_inode"], 1)
    integer(value["project_id"], 1, 2**32 - 1)
    require(integer(value["xflags"], 0, 2**32 - 1) & 0x200, "PROJECT_INHERIT")
    require(integer(value["hard_bytes"], 1024) % 1024 == 0, "PROJECT_LIMIT")
    token(value["slot_ref"], r"[a-z0-9][a-z0-9_.-]{0,63}")
    require(value["phase"] in ("preflight", "business", "reconcile", "evidence"), "PHASE")
    integer(value["issued_ns"])
    integer(value["deadline_ns"], value["issued_ns"] + 1)
    identity = [value[key] for key in ("manifest_digest", "slot_ref", "generation", "request_id",
                                      "allocation_digest", "execution_id", "phase")]
    unit = "lhq-" + hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest() + ".service"
    require(value["unit"] == unit and path(value["cgroup"]).endswith("/" + unit), "UNIT_BINDING")
    return value


def _boot_id():
    with open("/proc/sys/kernel/random/boot_id", "rb", buffering=0) as stream:
        raw = stream.read(38)
    require(len(raw) == 37 and raw.endswith(b"\n"), "BOOT_ID_UNCERTAIN")
    return token(raw[:-1].decode("ascii"), UUID)


def _now():
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME)


@dataclass(frozen=True)
class Record:
    request_id: str
    allocation_digest: str
    binding_digest: str
    unit: str
    cgroup: str
    boot_id: str
    invocation_id: str | None
    status: str
    unknown_reason: str | None
    intent_json: bytes


@dataclass(frozen=True)
class Delivery:
    record: Record
    delivered: bool


class StartJournal:
    """Bounded at 32 intents and three <=4KiB files per intent, plus lock.

    owner_uid and directory identity come from the private provisioner. They do
    not relax checks: owner_uid must be the current administrative euid; all path
    ancestors are root/admin-owned and non-writable by group/other. The final
    directory is exactly 0700. root is allowed as an ancestor owner only.
    """
    def __init__(self, control_dir, *, owner_uid, directory_device, directory_inode):
        integer(owner_uid, 0, 2**32 - 2)
        require(owner_uid == os.geteuid(), "CONTROL_OWNER")
        integer(directory_device)
        integer(directory_inode, 1)
        control_dir = path(os.fspath(control_dir))
        self._owner = owner_uid
        self._control_path = control_dir
        self._directory_identity = (directory_device, directory_inode)
        self._dir = -1
        self._guard = threading.Lock()
        self._poisoned = False
        try:
            self._dir = self._open_directory()
            observed = os.fstat(self._dir)
            require((observed.st_dev, observed.st_ino) == self._directory_identity, "CONTROL_IDENTITY")
            # Initialization also validates every retained record; it never repairs
            # an interrupted or corrupt write by deleting/replacing the evidence.
            with self._locked():
                self._scan()
        except BaseException:
            self.close()
            raise

    @property
    def control_dir(self):
        """Pinned canonical path to hide from the query unit, not a mutable setting."""
        return self._control_path

    def _open_directory(self):
        descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            parts = PurePosixPath(self._control_path).parts[1:]
            self._check_directory(descriptor, final=False)
            for index, part in enumerate(parts):
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=descriptor)
                parent, descriptor = descriptor, child
                os.close(parent)  # Never retry an uncertain close on a reused FD.
                self._check_directory(descriptor, final=index == len(parts) - 1)
            result, descriptor = descriptor, -1
            return result
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def verify_directory(self):
        """Recheck path-to-original-directory binding before runtime assembly.

        This is bounded in path depth, not wall time: path lookups can block.
        Trusted administration must still fence renames/mount changes throughout
        the query lifecycle. No filesystem check closes a concurrent-admin race.
        """
        require(self._dir >= 0 and not self._poisoned, "JOURNAL_UNAVAILABLE")
        descriptor = self._open_directory()
        try:
            current, original = os.fstat(descriptor), os.fstat(self._dir)
            require((current.st_dev, current.st_ino) == self._directory_identity
                    and (original.st_dev, original.st_ino) == self._directory_identity, "CONTROL_IDENTITY")
        finally:
            os.close(descriptor)

    def _check_directory(self, descriptor, *, final):
        info = os.fstat(descriptor)
        require(stat.S_ISDIR(info.st_mode), "CONTROL_DIRECTORY")
        require(info.st_uid in (0, self._owner) and not info.st_mode & 0o022, "CONTROL_ANCESTRY")
        if final:
            require(info.st_uid == self._owner and stat.S_IMODE(info.st_mode) == 0o700,
                    "CONTROL_DIRECTORY_PRIVATE")

    def close(self):
        if self._dir >= 0:
            descriptor, self._dir = self._dir, -1
            os.close(descriptor)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _file_info(self, descriptor, *, lock=False):
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == self._owner
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1, "CONTROL_FILE")
        require(info.st_size == 0 if lock else 0 < info.st_size <= MAX_FILE_BYTES, "CONTROL_FILE_SIZE")
        return info

    @contextmanager
    def _locked(self):
        require(self._dir >= 0 and not self._poisoned, "JOURNAL_UNAVAILABLE")
        require(self._guard.acquire(blocking=False), "JOURNAL_BUSY")
        descriptor = -1
        try:
            self._check_directory(self._dir, final=True)
            descriptor = os.open("lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                                 0o600, dir_fd=self._dir)
            self._file_info(descriptor, lock=True)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Rejected("JOURNAL_BUSY") from error
            yield
        finally:
            try:
                if descriptor >= 0:
                    os.close(descriptor)
            except OSError:
                self._poisoned = True
                raise
            finally:
                self._guard.release()

    def _read_file(self, name):
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                             dir_fd=self._dir)
        try:
            before = self._file_info(descriptor)
            raw = os.read(descriptor, MAX_FILE_BYTES + 1)
            after = self._file_info(descriptor)
            unchanged = ("st_dev", "st_ino", "st_uid", "st_gid", "st_mode", "st_nlink", "st_size",
                         "st_mtime_ns", "st_ctime_ns")
            require(all(getattr(before, key) == getattr(after, key) for key in unchanged)
                    and len(raw) == before.st_size and raw.endswith(b"\n"), "CONTROL_READ")
            value = strict_json(raw, MAX_FILE_BYTES, depth=2)
            require(_encode(value) == raw, "CONTROL_CANONICAL")
            return value
        finally:
            os.close(descriptor)

    def _create(self, name, value):
        raw = _encode(value)
        require(len(raw) <= MAX_FILE_BYTES, "CONTROL_BYTE_LIMIT")
        descriptor = -1
        try:
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                                 0o600, dir_fd=self._dir)
            require(os.write(descriptor, raw) == len(raw), "CONTROL_SHORT_WRITE")
            self._file_info(descriptor)
            os.fsync(descriptor)
            completed, descriptor = descriptor, -1
            os.close(completed)
            os.fsync(self._dir)
        except BaseException:
            self._poisoned = True
            raise
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _scan(self):
        grouped = {}
        with os.scandir(self._dir) as entries:
            for count, entry in enumerate(entries, 1):
                require(count <= MAX_FILES, "JOURNAL_CAPACITY")
                if entry.name == "lock":
                    continue
                match = _RECORD_NAME.fullmatch(entry.name)
                require(match is not None, "CONTROL_UNKNOWN_FILE")
                request_id, kind = match.groups()
                grouped.setdefault(request_id, {})[kind] = self._read_file(entry.name)
        require(len(grouped) <= MAX_INTENTS, "JOURNAL_CAPACITY")
        allocations, resources = set(), set()
        for request_id, files in grouped.items():
            require("intent" in files, "ORPHAN_RECORD")
            intent = _validate_intent(files["intent"])
            require(intent["request_id"] == request_id, "RECORD_IDENTITY")
            allocation = intent["allocation_digest"]
            require(allocation not in allocations, "ALLOCATION_ALIAS")
            allocations.add(allocation)
            claimed = self._resources(intent)
            require(not resources.intersection(claimed), "RESOURCE_ALIAS")
            resources.update(claimed)
            digest = hashlib.sha256(_encode(intent)).hexdigest()
            for kind, field, pattern in (("invocation", "invocation_id", r"[0-9a-f]{32}"),
                                          ("unknown", "reason", r"[A-Z][A-Z0-9_]{0,63}")):
                if kind in files:
                    value = fields(files[kind], ("schema", "binding_digest", field))
                    require(value["schema"] == "local-hand-quota-q1-" + kind + "/v1"
                            and value["binding_digest"] == digest, "RECORD_BINDING")
                    token(value[field], pattern)
        return grouped

    @staticmethod
    def _resources(intent):
        # Q1 has no generation-switch/stop-and-release protocol: changing the
        # generation must not renew the same logical slot's launch opportunity.
        return {("slot", intent["slot_ref"]),
                ("root", intent["root_device"], intent["root_inode"]),
                ("domain", intent["filesystem_uuid"], intent["project_id"])}

    def _record(self, files):
        intent = files["intent"]
        unknown = files.get("unknown", {}).get("reason")
        invocation = files.get("invocation", {}).get("invocation_id")
        status = "UNKNOWN" if unknown else "INVOCATION_RECORDED" if invocation else "INTENT"
        return Record(intent["request_id"], intent["allocation_digest"],
                      hashlib.sha256(_encode(intent)).hexdigest(), intent["unit"], intent["cgroup"],
                      intent["boot_id"], invocation, status, unknown, _encode(intent))

    def _existing(self, grouped, binding):
        value = _binding_value(binding)
        files = grouped.get(binding.request_id)
        if files is not None:
            require(files["intent"] == value, "REQUEST_CONFLICT")
        return files

    def read(self, binding):
        with self._locked():
            files = self._existing(self._scan(), binding)
            require(files is not None, "INTENT_REQUIRED")
            return self._record(files)

    def deliver_once(self, binding, callback):
        """Durably consume one opportunity BEFORE a trusted, fixed launch call.

        The callback must deliver only this binding, once, without retries. No
        callback result is interpreted as exit proof. Existing records are read
        even after a boot/deadline change; no callback is issued for them.
        """
        require(callable(callback), "CALLBACK_REQUIRED")
        value = _binding_value(binding)
        with self._locked():
            grouped = self._scan()
            existing = self._existing(grouped, binding)
            if existing is not None:
                return Delivery(self._record(existing), False)
            require(len(grouped) < MAX_INTENTS, "JOURNAL_CAPACITY")
            require(all(files["intent"]["allocation_digest"] != binding.allocation_digest
                        for files in grouped.values()), "ALLOCATION_RETAINED")
            require(all(not self._resources(files["intent"]).intersection(self._resources(value))
                        for files in grouped.values()), "RESOURCE_RETAINED")
            require(_boot_id() == binding.manifest.boot_id, "BOOT_CHANGED")
            require(binding.issued_ns <= _now() < binding.deadline_ns, "DEADLINE_EXPIRED")
            self._create(binding.request_id + ".intent.json", value)
        # This interval is deliberately not a recovery launch lease. A crash now
        # sacrifices liveness and retains the intent, instead of risking replay.
        try:
            require(_boot_id() == binding.manifest.boot_id, "BOOT_CHANGED")
            require(binding.issued_ns <= _now() < binding.deadline_ns, "DEADLINE_EXPIRED")
            callback(binding)
        except BaseException:
            try:
                self.mark_unknown(binding, "DELIVERY_UNCERTAIN")
            except (OSError, Rejected):
                pass  # Original durable intent still prohibits every re-delivery.
            raise
        return Delivery(self.read(binding), True)

    def _remember(self, binding, kind, field, value):
        with self._locked():
            grouped = self._scan()
            files = self._existing(grouped, binding)
            require(files is not None, "INTENT_REQUIRED")
            if kind in files:
                require(files[kind][field] == value, "ORIGINAL_RECORD_CONFLICT")
                return self._record(files)
            record = self._record(files)
            observation = {"schema": "local-hand-quota-q1-" + kind + "/v1",
                           "binding_digest": record.binding_digest, field: value}
            self._create(binding.request_id + "." + kind + ".json", observation)
            files[kind] = observation
            return self._record(files)

    def remember_invocation(self, binding, invocation_id):
        token(invocation_id, r"[0-9a-f]{32}")
        return self._remember(binding, "invocation", "invocation_id", invocation_id)

    def mark_unknown(self, binding, reason):
        token(reason, r"[A-Z][A-Z0-9_]{0,63}")
        return self._remember(binding, "unknown", "reason", reason)
