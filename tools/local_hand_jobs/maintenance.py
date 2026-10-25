"""Protected node admission barrier, independent of the deployment process.

Only trusted local administrators change this record. Business credentials do
not grant access to it. A missing record is UNKNOWN, never an implicit OPEN.
The deployment coordinator holds its own deployment lock before calling this
module; execution never acquires that lock. Runtime lock order is its existing
service fence, this admission lock, then its task records. No observer waits
for a process while holding the admission lock.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import uuid

from .contract import JobError, canonical_bytes, strict_loads

SCHEMA = "local-hand-maintenance/v1"
CONFIG_SCHEMA = "local-hand-maintenance-config/v1"
MAX_STATE_BYTES = 8 * 1024 * 1024


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _identifier(value):
    if type(value) is not str or not value or len(value) > 4096 or "\0" in value:
        raise JobError("MAINTENANCE_UNKNOWN", "Maintenance identity is invalid")
    return value


def _digest(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise JobError("MAINTENANCE_UNKNOWN", "Maintenance deployment binding is invalid")
    return value


def from_config(config):
    """Absent means legacy, not a claim that an old service is protected."""
    value = config.get("maintenance")
    if value is None:
        return None
    if (type(value) is not dict or set(value) != {
            "schema", "directory", "node_id", "deployment_digest", "startup_descriptor"}
            or value["schema"] != CONFIG_SCHEMA):
        raise JobError("MAINTENANCE_UNKNOWN", "Maintenance configuration is invalid")
    _digest(value["deployment_digest"])
    path = Path(value["startup_descriptor"])
    if not path.is_absolute() or str(path) != value["startup_descriptor"] or ".." in path.parts:
        raise JobError("MAINTENANCE_UNKNOWN", "Startup descriptor path is invalid")
    return MaintenanceGate(value["directory"], value["node_id"])


def loaded_configuration(config, *, boot_id, component="manager"):
    """Proof of this process's loaded snapshot, not a later file re-read.

    The caller must also verify its installed payload before publishing this
    proof. Deployment configuration is excluded from the content digest to
    avoid a deployment-digest/configuration-digest circular dependency.
    """
    value = config["maintenance"]
    payload = config["installation"]["installed"]["payload_digest"]
    return dict(node_id=value["node_id"], deployment_digest=_digest(value["deployment_digest"]),
                configuration_digest=digest({k: v for k, v in config.items() if k != "maintenance"}),
                payload_digest=_digest(payload), boot_id=_identifier(boot_id), component=_identifier(component))


def prepared_binding(loaded, *, operation_id, attempt_id, request_digest, launch):
    return dict(operation_id=_identifier(operation_id), attempt_id=_identifier(attempt_id),
                request_digest=_digest(request_digest), resource_digest=digest(launch),
                deployment_digest=loaded["deployment_digest"],
                configuration_digest=loaded["configuration_digest"],
                payload_digest=loaded["payload_digest"], boot_id=loaded["boot_id"])


def process_proof(loaded, *, protocol_ready):
    """Actual instance identity accompanying, not replacing, loaded content."""
    from .system_manager_protocol import start_ticks
    invocation=os.environ.get('INVOCATION_ID')
    if invocation is not None and re.fullmatch(r'[0-9a-f]{32}',invocation) is None:
        invocation=None
    return dict(loaded,pid=os.getpid(),start_ticks=start_ticks(os.getpid()),
                invocation_id=invocation,protocol_ready=protocol_ready)


class MaintenanceGate:
    """One lock and one durable record for the marker and admission duties.

    ``owner_uid`` is an explicit local test/embedding parameter, never read
    from client requests or service configuration. Production defaults to root.
    A receipt is not a bearer credential: callers still need protected-file
    access and their original task authorization and input binding.
    """

    def __init__(self, directory, node_id, *, owner_uid=0):
        self.directory = Path(directory)
        if (not self.directory.is_absolute() or str(self.directory) != os.fspath(directory)
                or ".." in self.directory.parts or str(directory).startswith("//")):
            raise JobError("MAINTENANCE_UNKNOWN", "Maintenance directory is invalid")
        self.node_id = _identifier(node_id)
        self.owner_uid = owner_uid

    def _directory(self):
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            for part in self.directory.parts[1:]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=fd)
                os.close(fd)
                fd = child
                info = os.fstat(fd)
                if (info.st_uid not in {0, self.owner_uid}
                        or info.st_mode & 0o022 and not (info.st_uid == 0 and info.st_mode & stat.S_ISVTX)):
                    raise JobError("MAINTENANCE_UNKNOWN", "Maintenance directory is not protected")
            info = os.fstat(fd)
            if info.st_uid != self.owner_uid or stat.S_IMODE(info.st_mode) & 0o077:
                raise JobError("MAINTENANCE_UNKNOWN", "Maintenance directory is not private")
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _regular(self, fd):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != self.owner_uid
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise JobError("MAINTENANCE_UNKNOWN", "Maintenance record is not protected")
        return info

    @contextmanager
    def _locked(self, *, bootstrap=False):
        directory = lock = None
        try:
            directory = self._directory()
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            if bootstrap:
                try:
                    lock = os.open("admission.lock", flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
                    os.fchmod(lock, 0o600)
                    os.fsync(lock)
                    os.fsync(directory)
                except FileExistsError:
                    pass
            if lock is None:
                lock = os.open("admission.lock", flags, dir_fd=directory)
            before = self._regular(lock)
            fcntl.flock(lock, fcntl.LOCK_EX)
            named = os.stat("admission.lock", dir_fd=directory, follow_symlinks=False)
            if (before.st_dev, before.st_ino) != (named.st_dev, named.st_ino):
                raise JobError("MAINTENANCE_UNKNOWN", "Maintenance lock changed")
            yield directory
        except OSError as error:
            raise JobError("MAINTENANCE_UNKNOWN", "Maintenance state cannot be established") from error
        finally:
            if lock is not None:
                os.close(lock)
            if directory is not None:
                os.close(directory)

    @contextmanager
    def admission_lock(self):
        """Startup guards may serialize their final listener-open check here.

        The yielded view is read-only by convention; use the transition APIs
        to mutate it. Do not call another gate method while holding this lock.
        """
        with self._locked() as directory:
            yield self._read(directory)

    def _read(self, directory):
        fd = os.open("gate.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=directory)
        try:
            info = self._regular(fd)
            if info.st_size > MAX_STATE_BYTES:
                raise JobError("MAINTENANCE_UNKNOWN", "Maintenance record exceeds its bound")
            data = bytearray()
            while len(data) <= MAX_STATE_BYTES:
                chunk = os.read(fd, min(65536, MAX_STATE_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            value = strict_loads(bytes(data), maximum_bytes=MAX_STATE_BYTES)
            self._validate(value)
            return value
        except (ValueError, TypeError, KeyError, JobError) as error:
            raise JobError("MAINTENANCE_UNKNOWN", "Maintenance record is incomplete or invalid") from error
        finally:
            os.close(fd)

    def _validate(self, value):
        if (type(value) is not dict or set(value) != {"schema", "node_id", "state", "sequence", "owner",
                "decision_id", "deployment_digest", "responsibilities", "compatibility", "last_transition", "retired_owners"}
                or value["schema"] != SCHEMA or value["node_id"] != self.node_id
                or value["state"] not in {"OPEN", "CLOSED"}
                or type(value["sequence"]) is not int or value["sequence"] < 1
                or type(value["responsibilities"]) is not dict or type(value["compatibility"]) is not dict
                or type(value["retired_owners"]) is not list):
            raise ValueError("marker")
        for owner in value["retired_owners"]:
            _identifier(owner)
        if len(set(value["retired_owners"])) != len(value["retired_owners"]):
            raise ValueError("retired owners")
        _digest(value["deployment_digest"])
        if value["state"] == "CLOSED":
            _identifier(value["owner"])
            if value["owner"] in value["retired_owners"]:
                raise ValueError("retired current owner")
        elif value["owner"] is not None:
            raise ValueError("open owner")
        _identifier(value["decision_id"])
        for identity, item in value["responsibilities"].items():
            if (type(item) is not dict or set(item) != {"id", "kind", "operation_id", "attempt_id", "binding",
                    "binding_digest", "loaded", "state", "accepted_sequence", "proof"}
                    or item.get("id") != identity or re.fullmatch(r"[0-9a-f]{32}", identity) is None
                    or item.get("kind") not in {"prepare", "execute"}
                    or item.get("state") not in {"ACCEPTED", "DISPATCHING", "CLOSED"}
                    or type(item["accepted_sequence"]) is not int
                    or not 1 <= item["accepted_sequence"] <= value["sequence"]
                    or type(item.get("binding")) is not dict or type(item.get("loaded")) is not dict):
                raise ValueError("responsibility")
            if item["state"] == "CLOSED":
                self._validate_closure(item["proof"])
            elif item["proof"] is not None:
                raise ValueError("unclosed proof")
            for key in ("operation_id", "attempt_id"):
                _identifier(item[key])
            self._validate_loaded(item["loaded"])
            _digest(item["binding_digest"])
            if digest(item["binding"]) != item["binding_digest"]:
                raise ValueError("binding")
        for key, item in value["compatibility"].items():
            if (type(item) is not dict or set(item) != {"prepared", "target_deployment_digest", "owner"}
                    or key != digest(item["prepared"])
                    or type(item["prepared"]) is not dict):
                raise ValueError("compatibility")
            _digest(item["target_deployment_digest"])
            _identifier(item["owner"])
            self._validate_prepared(item["prepared"])
        transition=value["last_transition"]
        if transition is None:
            if value["sequence"] != 1 or value["state"] != "OPEN":raise ValueError("missing transition")
        elif type(transition) is not dict:
            raise ValueError("transition")
        elif transition.get("kind") == "close":
            if set(transition) != {"kind", "owner"} or value["state"] != "CLOSED" or transition["owner"] != value["owner"]:
                raise ValueError("close transition")
        elif transition.get("kind") == "handoff":
            if (set(transition) != {"kind", "owner", "successor"} or value["state"] != "CLOSED"
                    or transition["successor"] != value["owner"] or transition["owner"] not in value["retired_owners"]):
                raise ValueError("handoff transition")
        elif transition.get("kind") == "release":
            if (set(transition) != {"kind", "owner", "decision_id", "deployment_digest"} or value["state"] != "OPEN"
                    or transition["owner"] not in value["retired_owners"]
                    or any(transition[k] != value[k] for k in ("decision_id", "deployment_digest"))):
                raise ValueError("release transition")
        else:
            raise ValueError("unknown transition")

    def _write(self, directory, value):
        self._validate(value)
        raw = canonical_bytes(value) + b"\n"
        if len(raw) > MAX_STATE_BYTES:
            raise JobError("LIMIT_EXCEEDED", "Maintenance history needs explicit retention management")
        name = ".gate-" + uuid.uuid4().hex
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=directory)
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(raw)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise OSError("short write")
                view = view[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(name, "gate.json", src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)

    def _confirm(self, directory):
        """A lost directory-sync response needs re-sync, not just a read."""
        fd=os.open('gate.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=directory)
        try:
            self._regular(fd)
            os.fsync(fd)
            os.fsync(directory)
        finally:
            os.close(fd)

    @staticmethod
    def _expected(value, expected):
        if expected is None:
            return
        keys = ("sequence", "state", "owner", "decision_id", "deployment_digest", "node_id")
        matches = (value["sequence"] == expected if type(expected) is int else
                   type(expected) is dict and all(value[key] == expected.get(key) for key in keys))
        if not matches:
            raise JobError("CONFLICT", "Maintenance marker changed; observe the original operation")

    def initialize(self, deployment_digest, decision_id, *, bootstrap=False):
        if bootstrap is not True:
            raise JobError("UNAUTHORIZED", "Initialization requires explicit trusted bootstrap")
        _digest(deployment_digest); _identifier(decision_id)
        with self._locked(bootstrap=True) as directory:
            try:
                value = self._read(directory)
            except FileNotFoundError:
                value = dict(schema=SCHEMA, node_id=self.node_id, state="OPEN", sequence=1, owner=None,
                             decision_id=decision_id, deployment_digest=deployment_digest,
                             responsibilities={}, compatibility={}, last_transition=None, retired_owners=[])
                self._write(directory, value)
                return copy.deepcopy(value)
            if (value["sequence"] == 1 and value["state"] == "OPEN"
                    and value["deployment_digest"] == deployment_digest and value["decision_id"] == decision_id):
                self._confirm(directory)
                return value
            raise JobError("CONFLICT", "An existing maintenance record cannot be initialized again")

    def snapshot(self):
        with self._locked() as directory:
            return self._read(directory)

    def close(self, owner, expected=None):
        _identifier(owner)
        with self._locked() as directory:
            value = self._read(directory)
            if value["state"] == "CLOSED" and value["owner"] == owner:
                self._confirm(directory)
                return value
            self._expected(value, expected)
            if value["state"] != "OPEN" or owner in value["retired_owners"]:
                raise JobError("CONFLICT", "Another operation owns maintenance")
            value.update(state="CLOSED", owner=owner, sequence=value["sequence"] + 1,
                         last_transition=dict(kind="close", owner=owner))
            self._write(directory, value)
            return value

    def release(self, owner, decision_id, deployment_digest, expected=None):
        """Apply an already-persisted local decision; does not invent one.

        Coordinator must prove its release conditions immediately before this
        call. In particular ABORTED_NO_CHANGE may release with active original
        business; release itself must not demand that business finish.
        """
        _identifier(owner); _identifier(decision_id); _digest(deployment_digest)
        transition = dict(kind="release", owner=owner, decision_id=decision_id,
                          deployment_digest=deployment_digest)
        with self._locked() as directory:
            value = self._read(directory)
            if value["state"] == "OPEN" and value["last_transition"] == transition:
                self._confirm(directory)
                return value
            self._expected(value, expected)
            if value["state"] != "CLOSED" or value["owner"] != owner:
                raise JobError("CONFLICT", "Only the current maintenance owner may release")
            value.update(state="OPEN", owner=None, decision_id=decision_id,
                         deployment_digest=deployment_digest, sequence=value["sequence"] + 1,
                         last_transition=transition)
            value["retired_owners"].append(owner)
            self._write(directory, value)
            return value

    def handoff(self, owner, successor, expected=None):
        _identifier(owner); _identifier(successor)
        if owner == successor:
            raise JobError("CONFLICT", "Maintenance successor must be a distinct operation")
        transition = dict(kind="handoff", owner=owner, successor=successor)
        with self._locked() as directory:
            value = self._read(directory)
            if value["state"] == "CLOSED" and value["owner"] == successor and value["last_transition"] == transition:
                self._confirm(directory)
                return value
            self._expected(value, expected)
            if value["state"] != "CLOSED" or value["owner"] != owner or successor in value["retired_owners"]:
                raise JobError("CONFLICT", "Only the current maintenance owner may hand off")
            value.update(owner=successor, sequence=value["sequence"] + 1, last_transition=transition)
            value["retired_owners"].append(owner)
            self._write(directory, value)
            return value

    def _validate_loaded(self, loaded):
        if (type(loaded) is not dict or set(loaded) != {"node_id", "deployment_digest", "configuration_digest",
                "payload_digest", "boot_id", "component"} or loaded["node_id"] != self.node_id):
            raise JobError("STALE_DEPLOYMENT", "Loaded deployment proof is invalid")
        for key in ("deployment_digest", "configuration_digest", "payload_digest"):
            _digest(loaded[key])
        _identifier(loaded["boot_id"])
        _identifier(loaded["component"])

    def _prepared(self, value, prepared, loaded):
        self._validate_prepared(prepared)
        same = all(prepared.get(key) == loaded[key] for key in (
            "deployment_digest", "configuration_digest", "payload_digest", "boot_id"))
        decision = value["compatibility"].get(digest(prepared))
        if not same and not (decision and decision["prepared"] == prepared
                             and decision["target_deployment_digest"] == loaded["deployment_digest"]):
            raise JobError("STALE_DEPLOYMENT", "Prepared task requires exact deployment compatibility")

    @staticmethod
    def _validate_prepared(prepared):
        if type(prepared) is not dict or set(prepared) != {"operation_id", "attempt_id", "request_digest",
                "resource_digest", "deployment_digest", "configuration_digest", "payload_digest", "boot_id"}:
            raise JobError("STALE_DEPLOYMENT", "Prepared task has no complete deployment binding")
        for key in ("operation_id", "attempt_id", "boot_id"):
            _identifier(prepared[key])
        for key in ("request_digest", "resource_digest", "deployment_digest", "configuration_digest", "payload_digest"):
            _digest(prepared[key])

    def authorize_compatibility(self, owner, prepared, target_deployment_digest):
        _digest(target_deployment_digest)
        self._validate_prepared(prepared)
        with self._locked() as directory:
            value = self._read(directory)
            if value["state"] != "CLOSED" or value["owner"] != owner:
                raise JobError("CONFLICT", "Compatibility decision needs the current maintenance owner")
            value["compatibility"][digest(prepared)] = dict(owner=owner, prepared=copy.deepcopy(prepared),
                                                         target_deployment_digest=target_deployment_digest)
            self._write(directory, value)

    def accept(self, kind, operation_id, attempt_id, binding, loaded, *, authorization=None, prepared=None):
        """Persist responsibility before creating any thread/process.

        Repeating an unresolved attempt returns its original receipt. A closed
        attempt cannot be reopened; a safe local retry uses a new attempt ID.
        """
        if kind not in {"prepare", "execute"} or type(binding) is not dict:
            raise JobError("MAINTENANCE_UNKNOWN", "Admission responsibility is invalid")
        _identifier(operation_id); _identifier(attempt_id); self._validate_loaded(loaded)
        with self._locked() as directory:
            value = self._read(directory)
            if authorization is not None:
                authorization.require_current()
            matches = [item for item in value["responsibilities"].values() if
                       (item["kind"], item["operation_id"], item["attempt_id"]) == (kind, operation_id, attempt_id)]
            if matches:
                old = matches[0]
                if old["binding"] != binding or old["loaded"] != loaded or old["state"] == "CLOSED":
                    raise JobError("CONFLICT", "Admission attempt cannot be rebound or reopened")
                self._confirm(directory)
                return copy.deepcopy(old)
            if value["state"] != "OPEN":
                raise JobError("MAINTENANCE", "New preparation and execution are temporarily closed", {"retryable": True})
            if value["deployment_digest"] != loaded["deployment_digest"]:
                raise JobError("STALE_DEPLOYMENT", "Loaded deployment is no longer selected")
            if kind == "execute":
                self._prepared(value, prepared, loaded)
                if (prepared.get("operation_id") != operation_id
                        or binding.get("prepared") != prepared):
                    raise JobError("STALE_DEPLOYMENT", "Execution does not bind the original preparation")
            identity = uuid.uuid4().hex
            item = dict(id=identity, kind=kind, operation_id=operation_id, attempt_id=attempt_id,
                        binding=copy.deepcopy(binding), binding_digest=digest(binding), loaded=copy.deepcopy(loaded),
                        state="ACCEPTED", accepted_sequence=value["sequence"], proof=None)
            value["responsibilities"][identity] = item
            self._write(directory, value)
            return copy.deepcopy(item)

    @staticmethod
    def _receipt(value, receipt):
        item = value["responsibilities"].get(receipt.get("id")) if type(receipt) is dict else None
        keys = ("id", "kind", "operation_id", "attempt_id", "binding", "binding_digest", "loaded", "accepted_sequence")
        if item is None or any(item[key] != receipt.get(key) for key in keys):
            raise JobError("CONFLICT", "Admission responsibility does not match its original attempt")
        return item

    def dispatch(self, receipt, *, authorization=None):
        with self._locked() as directory:
            value = self._read(directory)
            item = self._receipt(value, receipt)
            if authorization is not None:
                authorization.require_current()
            if item["state"] != "ACCEPTED":
                raise JobError("IO_UNCERTAIN", "The original dispatch must be observed, not repeated")
            # CLOSED does not withdraw work accepted before the close. Persist
            # uncertainty before the syscall; a lost reply never permits replay.
            item["state"] = "DISPATCHING"
            self._write(directory, value)
            return copy.deepcopy(item)

    @staticmethod
    def _validate_closure(proof):
        if type(proof) is not dict or not (
                set(proof) == {"never_dispatched"} and proof["never_dispatched"] is True or
                set(proof) == {"process_exited", "writers_stopped"}
                and proof["process_exited"] is True and proof["writers_stopped"] is True):
            raise JobError("IO_UNCERTAIN", "Responsibility needs positive closure proof")

    def finish(self, receipt, proof):
        self._validate_closure(proof)
        with self._locked() as directory:
            value = self._read(directory)
            item = self._receipt(value, receipt)
            if item["state"] == "CLOSED":
                if item["proof"] != proof:
                    raise JobError("CONFLICT", "Original responsibility closure differs")
                self._confirm(directory)
                return copy.deepcopy(item)
            item.update(state="CLOSED", proof=copy.deepcopy(proof))
            self._write(directory, value)
            return copy.deepcopy(item)

    def active(self):
        value = self.snapshot()
        return [item for item in value["responsibilities"].values() if item["state"] != "CLOSED"]
