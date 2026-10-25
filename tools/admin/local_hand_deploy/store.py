"""Independent SQLite state with one durable mutation protocol and bounded logs.

The stable node flock is inherited by supervised callers; closing this process's
copy never explicitly unlocks a lock that an unfinished child still holds.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import sqlite3
import stat
import time

from local_hand_jobs.startup import _protected_directory

from .files import _binding
from .model import DeployError, Limits, SCHEMA, canonical, decode, identity, new_operation, validate_plan


def _protected(path, *, directory=False, owner_uid=None):
    owner_uid = os.geteuid() if owner_uid is None else owner_uid
    try:
        parent_fd = _protected_directory(path.parent, owner_uid=owner_uid)
        try:
            info = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        finally:
            os.close(parent_fd)
        if (not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
                or info.st_uid != owner_uid or info.st_mode & 0o077
                or (not directory and info.st_nlink != 1)):
            raise ValueError("unprotected state")
        return info
    except (OSError, ValueError) as exc:
        raise DeployError("STATE_UNAVAILABLE", "Deployment state must be private, owned, and unsymlinked") from exc


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Store:
    def __init__(self, root, node_id, *, limits=Limits(), owner_uid=None):
        self.root = Path(root)
        if not self.root.is_absolute() or ".." in self.root.parts:
            raise DeployError("STATE_UNAVAILABLE", "State directory must be absolute")
        self.node_id = identity(node_id, "node ID")
        self.limits = limits
        self.owner_uid = os.geteuid() if owner_uid is None else owner_uid
        self.path = self.root / "operations.sqlite3"
        self.lock_path = self.root / "deployment.lock"
        self.lock_fd = None
        self.connection = None

    def initialize(self):
        """Explicit create-only bootstrap; never repair an existing broken store."""
        self.root.mkdir(mode=0o700, parents=False, exist_ok=True)
        _protected(self.root, directory=True, owner_uid=self.owner_uid)
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            _protected(self.lock_path, owner_uid=self.owner_uid)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.path.exists() or self.path.is_symlink():
                raise DeployError("STATE_EXISTS", "Existing deployment state must be opened, not initialized")
            created = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                binding = _binding(created)
                os.fsync(created)
            finally:
                os.close(created)
            connection = sqlite3.connect(self.path)
            try:
                self._settings(connection, initialize=True)
                connection.executescript("""
                    CREATE TABLE metadata (singleton INTEGER PRIMARY KEY CHECK(singleton=1), value BLOB NOT NULL);
                    CREATE TABLE operations (id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
                        plan_digest TEXT NOT NULL, document BLOB NOT NULL);
                    CREATE TABLE events (sequence INTEGER PRIMARY KEY, operation TEXT NOT NULL REFERENCES operations(id),
                        kind TEXT NOT NULL, recorded_ns INTEGER NOT NULL, document BLOB NOT NULL);
                """)
                metadata = {"schema": SCHEMA, "node_id": self.node_id, "storage_binding": binding,
                            "limits": asdict(self.limits)}
                connection.execute("INSERT INTO metadata VALUES (1, ?)", (canonical(metadata),))
                connection.commit()
            finally:
                connection.close()
            _sync_directory(self.root)
        except BlockingIOError as exc:
            raise DeployError("DEPLOYMENT_BUSY", "Another deployment still owns the node") from exc
        finally:
            os.close(fd)

    def _settings(self, connection, *, initialize=False, readonly=False):
        if initialize:
            connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=EXTRA")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=0")
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        # max_page_count is connection-local. Reapply on every writer, not
        # merely when the database is first created.
        if not readonly:
            connection.execute(f"PRAGMA max_page_count={self.limits.max_database_bytes // page_size}")
        actual = (connection.execute("PRAGMA journal_mode").fetchone()[0].lower(),
                  connection.execute("PRAGMA synchronous").fetchone()[0],
                  connection.execute("PRAGMA foreign_keys").fetchone()[0])
        if actual != ("delete", 3, 1):
            raise DeployError("STATE_UNSUPPORTED", "Required SQLite durability settings are unavailable")

    def _open(self, *, readonly=False):
        _protected(self.root, directory=True, owner_uid=self.owner_uid)
        info = _protected(self.path, owner_uid=self.owner_uid)
        if info.st_size > self.limits.max_database_bytes:
            raise DeployError("STATE_LIMIT", "Deployment database exceeds its byte budget")
        # SQLite may recover its own rollback journal on writable resume. A
        # read-only status cannot create a database or silently recover it.
        for suffix in ("-journal", "-wal", "-shm"):
            sidecar = Path(str(self.path) + suffix)
            if sidecar.exists() or sidecar.is_symlink():
                _protected(sidecar, owner_uid=self.owner_uid)
                if suffix != "-journal":
                    raise DeployError("STATE_UNSUPPORTED", "Unexpected SQLite journal mode")
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            binding = _binding(fd)
        finally:
            os.close(fd)
        try:
            connection = sqlite3.connect(self.path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True)
            self._settings(connection, readonly=readonly)
            metadata = decode(connection.execute("SELECT value FROM metadata WHERE singleton=1").fetchone()[0])
            expected = {"schema": SCHEMA, "node_id": self.node_id, "storage_binding": binding,
                        "limits": asdict(self.limits)}
            if metadata != expected:
                raise DeployError("STATE_CONFLICT", "Node, storage identity, record format or limits differ")
            if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise DeployError("STATE_CORRUPT", "Deployment database integrity check failed")
            return connection
        except (sqlite3.Error, TypeError, IndexError) as exc:
            if "connection" in locals():
                connection.close()
            raise DeployError("STATE_UNAVAILABLE", "Deployment records cannot be verified") from exc
        except Exception:
            if "connection" in locals():
                connection.close()
            raise

    @contextmanager
    def locked(self, *, readonly=False):
        if self.connection is not None:
            raise DeployError("LOCK_ORDER", "Deployment lock is not reentrant")
        _protected(self.lock_path, owner_uid=self.owner_uid)
        fd = os.open(self.lock_path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd = fd
            self.connection = self._open(readonly=readonly)
            yield self
        except BlockingIOError as exc:
            raise DeployError("DEPLOYMENT_BUSY", "Another deployment or supervised caller owns the node") from exc
        finally:
            if self.connection is not None:
                self.connection.close(); self.connection = None
            self.lock_fd = None
            # No LOCK_UN: a child may still share this open file description.
            os.close(fd)

    @contextmanager
    def reading(self):
        connection = self._open(readonly=True)
        try:
            yield connection
        finally:
            connection.close()

    def _required(self):
        if self.connection is None or self.lock_fd is None:
            raise DeployError("LOCK_REQUIRED", "Mutation requires the node deployment lock")
        return self.connection

    def get(self, operation_id):
        identity(operation_id)
        if self.connection is not None:
            row = self.connection.execute("SELECT document FROM operations WHERE id=?", (operation_id,)).fetchone()
        else:
            with self.reading() as connection:
                row = connection.execute("SELECT document FROM operations WHERE id=?", (operation_id,)).fetchone()
        if row is None:
            raise DeployError("NOT_FOUND", "Deployment operation is not recorded")
        return decode(row[0])

    def list(self, *, unfinished=False):
        def read(connection):
            return [decode(row[0]) for row in connection.execute(
                "SELECT document FROM operations ORDER BY rowid LIMIT ?", (self.limits.max_operations + 1,))]
        if self.connection is not None:
            result = read(self.connection)
        else:
            with self.reading() as connection:
                result = read(connection)
        if len(result) > self.limits.max_operations:
            raise DeployError("STATE_LIMIT", "Operation count exceeds its limit")
        return [op for op in result if not unfinished or
                (not op["released"] and not op["handoff_complete"])]

    def validate_plan(self, plan):
        """Bind every incoming plan before observation, persistence or handoff."""
        validate_plan(plan, self.limits)
        if plan["node_id"] != self.node_id:
            raise DeployError("NODE_CONFLICT", "Plan belongs to a different node")
        return plan

    def create(self, plan, *, predecessor=None):
        self.validate_plan(plan)
        connection = self._required()
        row = connection.execute("SELECT plan_digest,document FROM operations WHERE request_id=?",
                                 (plan["request_id"],)).fetchone()
        if row:
            if row[0] != plan["digest"]:
                raise DeployError("REQUEST_CONFLICT", "Request ID already identifies a different plan")
            return decode(row[1])
        if connection.execute("SELECT count(*) FROM operations").fetchone()[0] >= self.limits.max_operations:
            raise DeployError("STATE_LIMIT", "Operation count budget is exhausted")
        operation = new_operation(plan, predecessor=predecessor)
        raw = canonical(operation)
        if len(raw) > self.limits.max_record_bytes:
            raise DeployError("STATE_LIMIT", "Initial operation exceeds its byte budget")
        try:
            with connection:
                connection.execute("INSERT INTO operations VALUES (?,?,?,?)", (
                    operation["id"], plan["request_id"], plan["digest"], raw))
                self._event(operation, "CREATED", {})
        except sqlite3.Error as exc:
            raise DeployError("STATE_UNAVAILABLE", "Cannot persist deployment request") from exc
        return operation

    def _event(self, operation, kind, detail, *, recovery=False):
        connection = self._required()
        count = connection.execute("SELECT count(*) FROM events").fetchone()[0]
        allowed = self.limits.max_events if recovery else self.limits.max_events - self.limits.recovery_events
        if count >= allowed:
            raise DeployError("STATE_LIMIT", "Event budget exhausted; recovery reserve is retained")
        body = canonical(detail)
        if len(body) > self.limits.max_record_bytes:
            raise DeployError("STATE_LIMIT", "Event exceeds its byte budget")
        connection.execute("INSERT INTO events(operation,kind,recorded_ns,document) VALUES (?,?,?,?)",
                           (operation["id"], kind, time.time_ns(), body))

    def check_attempt_budget(self, operation, *, restore=False):
        """Retain bounded completion/compensation room before another effect.

        This is a logical record budget, not a promise that the disk cannot
        fail. The node lock excludes another deployment consuming it between
        this check and the following durable intent.
        """
        connection = self._required()
        if restore:
            remaining = sum(entry["record"]["state"] != "RESTORED"
                            for entry in operation.get("compensation", []))
        else:
            # Compensation may add stop/reload/start around original files.
            remaining = min(self.limits.max_steps, len(operation["steps"]) * 3 + 4)
        events = 12 * remaining + 64
        count = connection.execute("SELECT count(*) FROM events").fetchone()[0]
        if count + events > self.limits.max_events:
            raise DeployError("STATE_LIMIT", "No event budget for completion, compensation and release")
        raw = len(canonical(operation))
        # Reserve attempt identities, observations and final readback in the
        # operation document, separately from append-only event capacity.
        growth = max(262144, raw) + 8192 * (remaining + 2)
        if raw + growth > self.limits.max_record_bytes:
            raise DeployError("STATE_LIMIT", "No operation byte budget for the bounded recovery path")
        page = connection.execute("PRAGMA page_size").fetchone()[0]
        pages = connection.execute("PRAGMA page_count").fetchone()[0]
        free = connection.execute("PRAGMA freelist_count").fetchone()[0]
        # Leave another complete operation slot for an explicit successor,
        # plus an overflow-page envelope for all reserved event records.
        required = 2 * self.limits.max_record_bytes + events * (page * 2)
        if (pages - free) * page + required > self.limits.max_database_bytes:
            raise DeployError("STATE_LIMIT", "No database byte budget for linked recovery and release")
        return {"events": events, "operation_bytes": growth, "database_bytes": required}

    def save(self, operation, kind, detail=None, *, recovery=False):
        connection = self._required()
        operation["updated_ns"] = time.time_ns()
        raw = canonical(operation)
        if len(raw) > self.limits.max_record_bytes:
            raise DeployError("STATE_LIMIT", "Operation record exceeds its byte budget")
        try:
            with connection:
                if connection.execute("UPDATE operations SET document=? WHERE id=?", (raw, operation["id"])).rowcount != 1:
                    raise DeployError("NOT_FOUND", "Cannot rewrite an unrecorded operation")
                self._event(operation, kind, detail or {}, recovery=recovery)
        except sqlite3.Error as exc:
            raise DeployError("STATE_UNAVAILABLE", "Cannot persist operation and event atomically") from exc

    def link(self, operation, successor_plan, *, rollback=False):
        """Create successor and immutable link in one transaction, including retries."""
        connection = self._required()
        self.validate_plan(successor_plan)
        key = "rollback_successor" if rollback else "successor"
        original = self.get(operation["id"])
        if original[key]:
            return self.get(original[key])
        successor = new_operation(successor_plan, predecessor=original["id"])
        if connection.execute("SELECT count(*) FROM operations").fetchone()[0] >= self.limits.max_operations:
            raise DeployError("STATE_LIMIT", "No space for linked recovery operation")
        original[key] = successor["id"]
        original_raw, successor_raw = canonical(original), canonical(successor)
        if max(len(original_raw), len(successor_raw)) > self.limits.max_record_bytes:
            raise DeployError("STATE_LIMIT", "Recovery link exceeds its record byte budget")
        try:
            with connection:
                connection.execute("INSERT INTO operations VALUES (?,?,?,?)", (
                    successor["id"], successor_plan["request_id"], successor_plan["digest"], successor_raw))
                connection.execute("UPDATE operations SET document=? WHERE id=?", (original_raw, original["id"]))
                self._event(original, "ROLLBACK_LINK" if rollback else "HANDOFF_LINK", {"successor": successor["id"]}, recovery=True)
                self._event(successor, "CREATED", {"predecessor": original["id"]}, recovery=True)
        except sqlite3.Error as exc:
            raise DeployError("STATE_UNAVAILABLE", "Cannot persist recovery successor atomically") from exc
        operation.update(original)
        return successor
