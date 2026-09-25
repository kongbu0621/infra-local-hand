"""Finite Q2 append-only cells; call only in a supervised management worker.

Provisioning is explicit and separate. Opening/recovery NEVER creates a file.
The external protected pin and immutable grant table must survive a restart.
No FS call here is assumed nonblocking; the listener must not call this class.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import PurePosixPath
import stat
import threading

from local_hand_jobs import quota_contract as q, quota_grant as g


def peer_binding(value, grant):
    """Validate an OS/manager attestation, not peer-supplied JSON credentials."""
    q._keys(value, {"uid", "gid", "pid", "start_ticks", "boot_id", "unit", "invocation_id", "cgroup", "parent"})
    data = grant.as_dict()
    root = next(root for root in data["roots"] if root["role"] == "work")
    q.require((value["uid"], value["gid"]) == (root["uid"], root["gid"]), "BOOTSTRAP_PEER")
    for key in ("uid", "gid", "pid", "start_ticks"):
        q.integer(value[key], 1 if key in ("pid", "start_ticks") else 0)
    unit = "lhj-" + hashlib.sha256((data["request"]["execution_id"] + ":bootstrap").encode()).hexdigest() + ".service"
    q.require(value["unit"] == unit and value["boot_id"] == data["request"]["boot_id"], "BOOTSTRAP_PEER")
    q.match(value["invocation_id"], r"[0-9a-f]{32}")
    q._keys(value["parent"], {"path", "device", "inode"})
    q.canonical_path(value["parent"]["path"])
    q.integer(value["parent"]["device"])
    q.integer(value["parent"]["inode"], 1)
    q.require(q.canonical_path(value["cgroup"]) == value["parent"]["path"] + "/" + unit, "BOOTSTRAP_PEER")
    return value


def invocation(value, grant):
    q._keys(value, {"unit", "invocation_id", "cgroup", "parent"})
    parent = grant.as_dict()["query_parent"]
    q.match(value["invocation_id"], r"[0-9a-f]{32}")
    q.require(value["unit"] == grant.request.query_unit and value["parent"] == parent
              and value["cgroup"] == parent["path"] + "/" + value["unit"], "QUERY_BINDING")
    return value


def closed_fence(value, grant, receipt, peer):
    q._keys(value, {"schema", "request_digest", "receipt_digest", "boot_id", "execution_id",
                    "proof_digest", "closed_ns", "stages"})
    data = grant.as_dict()
    q.require(value["schema"] == "local-hand-quota-phase-closed/v1"
              and value["request_digest"] == grant.request.digest
              and value["receipt_digest"] == hashlib.sha256(receipt.wire).hexdigest()
              and value["boot_id"] == data["request"]["boot_id"]
              and value["execution_id"] == data["request"]["execution_id"], "PHASE_FENCE")
    q.match(value["proof_digest"], r"[0-9a-f]{64}")
    q.integer(value["closed_ns"], receipt.as_dict()["finished_ns"])
    q._keys(value["stages"], {"bootstrap", "helper", "reader", "query", "collector"})
    for stage, proof in value["stages"].items():
        q._keys(proof, {*q.EXIT_FLAGS, "proof_digest", "identity"})
        q.match(proof["proof_digest"], r"[0-9a-f]{64}")
        q.require(all(proof[key] is True for key in q.EXIT_FLAGS), "PHASE_EXIT_UNPROVEN")
        identity = proof["identity"]
        q._keys(identity, {"boot_id", "unit", "invocation_id", "cgroup", "parent"})
        q.match(identity["invocation_id"], r"[0-9a-f]{32}")
        if stage == "query":
            expected = dict(receipt.as_dict()["query"], parent=data["query_parent"])
        elif stage == "bootstrap":
            expected = {key: peer[key] for key in ("unit", "invocation_id", "cgroup", "parent")}
        else:
            parent = data["management_parent"] if stage == "collector" else peer["parent"]
            suffix = ":result_reader" if stage == "reader" else ""
            unit = ("lhqoc-" + grant.request.digest if stage == "collector" else
                    "lhj-" + hashlib.sha256((data["request"]["execution_id"] + suffix).encode()).hexdigest()) + ".service"
            expected = {"unit": unit, "invocation_id": identity["invocation_id"],
                        "parent": parent, "cgroup": parent["path"] + "/" + unit}
        q.require(identity == dict(expected, boot_id=data["request"]["boot_id"]), "PHASE_STAGE_IDENTITY")
    return value


def _directory(path, owner):
    path = q.canonical_path(os.fspath(path))
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in (None, *PurePosixPath(path).parts[1:]):
            if part is not None:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor)
                old, descriptor = descriptor, child
                os.close(old)
            info = os.fstat(descriptor)
            q.require(info.st_uid in (0, owner) and not info.st_mode & 0o022, "JOURNAL_ANCESTRY")
        q.require(info.st_uid == owner and stat.S_IMODE(info.st_mode) == 0o700, "JOURNAL_PRIVATE")
        result, descriptor = descriptor, -1
        return result
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _names(descriptor):
    names = set()
    with os.scandir(descriptor) as entries:
        for entry in entries:
            names.add(entry.name)
            q.require(len(names) <= g.MAX_GRANTS + 2, "JOURNAL_FILE_COUNT")
    return names


def _write(descriptor, raw):
    pending = memoryview(raw)
    while pending:
        written = os.write(descriptor, pending)
        q.require(written > 0, "JOURNAL_WRITE")
        pending = pending[written:]
    os.fsync(descriptor)


def _line(value):
    return q._canonical(value, 65536) + b"\n"


class Journal:
    def __init__(self, path, pin, capacity, grants):
        self.path = q.canonical_path(os.fspath(path))
        self.owner = os.geteuid()
        self.grants = {}
        q.require(0 < len(grants) <= g.MAX_GRANTS, "GRANT_COUNT")
        for original in grants:
            grant = g.decode_grant(original.wire)
            key = grant.request.as_dict()["request_id"]
            q.require(key not in self.grants, "DUPLICATE_GRANT")
            self.grants[key] = grant
        self.capacity = g.decode_capacity(q._canonical(capacity, g.GRANT_LIMIT))
        for grant in self.grants.values():
            g.check_capacity(self.capacity, [grant])
        self.policy = _line({"schema": "local-hand-quota-journal/v2", "capacity_digest": g.digest(self.capacity),
                             "grants": {key: item.digest for key, item in self.grants.items()}})
        self.pin = q._load(q._canonical(pin, g.GRANT_LIMIT), g.GRANT_LIMIT, 5)
        q._keys(self.pin, {"directory", "files"})
        q._keys(self.pin["directory"], {"device", "inode"})
        q._keys(self.pin["files"], {"lock", "policy", *(key + ".cell" for key in self.grants)})
        for item in (self.pin["directory"], *self.pin["files"].values()):
            q._keys(item, {"device", "inode"})
            q.integer(item["device"])
            q.integer(item["inode"], 1)
        self._dir = self._lock = -1
        self._guard = threading.Lock()
        self._poisoned = False
        try:
            self._dir = _directory(self.path, self.owner)
            self._lock = self._open("lock")
            with self.locked():
                self.scan()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def provision(path, capacity, grants):
        """Offline, create-only initialization; caller protects the returned pin.

        Failure leaves all partial files. It never finishes/replaces an existing
        directory. Administrative provisioning is not a wire service operation.
        """
        grants = [g.decode_grant(item.wire) for item in grants]
        q.require(0 < len(grants) <= g.MAX_GRANTS, "GRANT_COUNT")
        capacity = g.decode_capacity(q._canonical(capacity, g.GRANT_LIMIT))
        ids = [item.request.as_dict()["request_id"] for item in grants]
        q.require(len(set(ids)) == len(ids), "DUPLICATE_GRANT")
        for grant in grants:
            g.check_capacity(capacity, [grant])
        descriptor = _directory(path, os.geteuid())
        try:
            q.require(not _names(descriptor), "JOURNAL_EXISTS")
            files = {"lock": b"", "policy": _line({"schema": "local-hand-quota-journal/v2",
                "capacity_digest": g.digest(capacity), "grants": {key: item.digest for key, item in zip(ids, grants)}})}
            files.update({key + ".cell": _line({"kind": "READY", "grant_digest": item.digest}) for key, item in zip(ids, grants)})
            pin = {"directory": {}, "files": {}}
            info = os.fstat(descriptor)
            pin["directory"] = {"device": info.st_dev, "inode": info.st_ino}
            for name, raw in files.items():
                child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=descriptor)
                try:
                    _write(child, raw)
                    info = os.fstat(child)
                    pin["files"][name] = {"device": info.st_dev, "inode": info.st_ino}
                finally:
                    os.close(child)
            os.fsync(descriptor)
            return pin
        finally:
            os.close(descriptor)

    def _open(self, name, *, append=False):
        descriptor = os.open(name, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | (os.O_APPEND if append else 0), dir_fd=self._dir)
        try:
            info = os.fstat(descriptor)
            q.require(stat.S_ISREG(info.st_mode) and info.st_uid == self.owner
                      and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
                      and {"device": info.st_dev, "inode": info.st_ino} == self.pin["files"][name], "JOURNAL_FILE")
            q.require(info.st_size <= g.CELL_BYTES and (name != "lock" or info.st_size == 0), "JOURNAL_SIZE")
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def close(self):
        for key in ("_lock", "_dir"):
            descriptor = getattr(self, key)
            setattr(self, key, -1)
            if descriptor >= 0:
                os.close(descriptor)

    @contextmanager
    def locked(self):
        q.require(self._dir >= 0 and not self._poisoned, "JOURNAL_UNAVAILABLE")
        q.require(self._guard.acquire(blocking=False), "JOURNAL_BUSY")
        acquired = False
        try:
            try:
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                raise q.QuotaError("JOURNAL_BUSY") from None
            current = _directory(self.path, self.owner)
            try:
                info = os.fstat(current)
                q.require({"device": info.st_dev, "inode": info.st_ino} == self.pin["directory"], "JOURNAL_IDENTITY")
            finally:
                os.close(current)
            q.require(_names(self._dir) == self.pin["files"].keys(), "JOURNAL_FILES")
            # A renamed/replaced lock must not create a second lock domain.
            child = self._open("lock")
            os.close(child)
            yield
        finally:
            if acquired:
                fcntl.flock(self._lock, fcntl.LOCK_UN)
            self._guard.release()

    def _read(self, name):
        descriptor = self._open(name)
        try:
            data = bytearray()
            while len(data) <= g.CELL_BYTES:
                chunk = os.read(descriptor, min(8192, g.CELL_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            q.require(0 < len(data) <= g.CELL_BYTES, "JOURNAL_SIZE")
            return bytes(data)
        finally:
            os.close(descriptor)

    def scan(self):
        """Caller holds locked(); every declaration/cell remains mandatory."""
        q.require(self._read("policy") == self.policy, "JOURNAL_POLICY")
        result = {}
        for key, grant in self.grants.items():
            raw = self._read(key + ".cell")
            lines = raw.splitlines(keepends=True)
            q.require(1 <= len(lines) <= 5 and all(line.endswith(b"\n") for line in lines), "JOURNAL_PARTIAL")
            values = [q._load(line[:-1], 65536, 12) for line in lines]
            q.require(all(_line(value) == line for value, line in zip(values, lines)), "JOURNAL_CANONICAL")
            q.require(values[0] == {"kind": "READY", "grant_digest": grant.digest}, "JOURNAL_BINDING")
            state = {"status": "READY"}
            prefix = lines[0]
            for value, line in zip(values[1:], lines[1:]):
                q._keys(value, {"kind", "value", "previous_digest", "digest"})
                unsigned = {key: child for key, child in value.items() if key != "digest"}
                q.require(value["previous_digest"] == hashlib.sha256(prefix).hexdigest()
                          and value["digest"] == hashlib.sha256(q._canonical(unsigned, 65536)).hexdigest(),
                          "JOURNAL_CHECKSUM")
                prefix += line
                kind, item = value["kind"], value["value"]
                if kind == "INTENT":
                    q.require(state["status"] == "READY", "JOURNAL_ORDER")
                    q._keys(item, {"request_digest", "peer", "reserved_ns"})
                    q.require(item["request_digest"] == grant.request.digest, "JOURNAL_BINDING")
                    q.integer(item["reserved_ns"], grant.as_dict()["management"]["issued_ns"], grant.request.as_dict()["deadline_ns"] - 1)
                    peer_binding(item["peer"], grant)
                elif kind == "INVOCATION":
                    q.require(state["status"] == "INTENT", "JOURNAL_ORDER")
                    invocation(item, grant)
                elif kind == "RESULT":
                    q.require(state["status"] in ("INTENT", "INVOCATION"), "JOURNAL_ORDER")
                    q._keys(item, {"receipt", "received_ns"})
                    q.integer(item["received_ns"], state["intent"]["reserved_ns"])
                    receipt = q.decode_receipt(q._canonical(item["receipt"], q.RESPONSE_LIMIT), grant.request,
                        grant.as_dict()["roots"], now_ns=item["received_ns"])
                    query = receipt.as_dict()["query"]
                    if query is not None:
                        prior = state.get("invocation")
                        q.require(prior is not None and query == {k: prior[k] for k in query}, "QUERY_BINDING")
                    q.require(receipt.as_dict()["status"] != "OBSERVED" or query is not None, "QUERY_BINDING")
                elif kind == "CLOSED":
                    q.require(state["status"] == "RESULT" and state["result"]["receipt"]["status"] == "OBSERVED", "JOURNAL_ORDER")
                    stored = state["result"]
                    receipt = q.decode_receipt(q._canonical(stored["receipt"], q.RESPONSE_LIMIT), grant.request,
                        grant.as_dict()["roots"], now_ns=stored["received_ns"])
                    closed_fence(item, grant, receipt, state["intent"]["peer"])
                else:
                    raise q.QuotaError("JOURNAL_KIND")
                state[kind.lower()] = item
                state["status"] = kind
            result[key] = state
        g.check_capacity(self.capacity, [self.grants[key] for key, state in result.items() if state["status"] != "READY"])
        return result

    def append(self, key, kind, value):
        """Caller validates transition under locked(); uncertain writes poison."""
        q.require(key in self.grants and not self._poisoned, "JOURNAL_UNAVAILABLE")
        try:
            previous = self._read(key + ".cell")
            record = {"kind": kind, "value": value, "previous_digest": hashlib.sha256(previous).hexdigest()}
            record["digest"] = hashlib.sha256(q._canonical(record, 65536)).hexdigest()
            raw = _line(record)
            descriptor = self._open(key + ".cell", append=True)
            try:
                q.require(os.fstat(descriptor).st_size + len(raw) <= g.CELL_BYTES, "JOURNAL_SIZE")
                _write(descriptor, raw)
            finally:
                os.close(descriptor)
        except BaseException:
            self._poisoned = True
            raise
