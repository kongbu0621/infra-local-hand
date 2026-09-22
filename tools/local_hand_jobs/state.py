"""Durable local job ledger. Never infer absence after a storage error."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import stat
import threading
import time

from .contract import JobError


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class StateStore:
    """One SQLite ledger; callers hold a transaction through an admission decision.

    initialize is an administrative bootstrap action, never a recovery fallback.
    All externally visible identities and events are append-only.
    """

    def __init__(self, path, authority_id, ledger_id, *, initialize=False):
        self.path = Path(path).absolute()
        self.authority_id, self.ledger_id = authority_id, ledger_id
        self.lock = threading.RLock()
        self.healthy = True
        self._db = None
        try:
            parent = self.path.parent.lstat()
            if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
                    or parent.st_mode & 0o077 or self.path.parent.resolve() != self.path.parent):
                raise JobError("UNAUTHORIZED", "Ledger directory is not privately owned")
            if initialize:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                os.close(fd)
                directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                identity_before = os.fstat(descriptor)
                if (not stat.S_ISREG(identity_before.st_mode) or identity_before.st_nlink != 1
                        or identity_before.st_uid != os.geteuid() or identity_before.st_mode & 0o077):
                    raise JobError("IO_UNCERTAIN", "The registered ledger type or ownership is unproven")
            finally:
                os.close(descriptor)
            self._db = sqlite3.connect(str(self.path), timeout=0.5, isolation_level=None,
                                       check_same_thread=False)
            identity_after = self.path.lstat()
            if (identity_before.st_ino, identity_before.st_dev) != (identity_after.st_ino, identity_after.st_dev):
                raise JobError("IO_UNCERTAIN", "Ledger entry changed while opening")
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.execute("PRAGMA foreign_keys=ON")
            if initialize:
                self._create()
            result = self._db.execute("PRAGMA quick_check").fetchone()[0]
            identity = dict(self._db.execute("SELECT key,value FROM metadata"))
            if result != "ok" or identity != {
                "schema": "1", "authority_id": authority_id, "ledger_id": ledger_id,
            }:
                raise JobError("IO_UNCERTAIN", "Ledger identity or integrity is unproven")
        except JobError:
            if self._db is not None:
                self._db.close()
            self.healthy = False
            raise
        except (OSError, sqlite3.Error) as exc:
            if self._db is not None:
                self._db.close()
            self.healthy = False
            raise JobError("IO_UNCERTAIN", "Ledger initialization or lookup failed") from exc

    def _create(self):
        self._db.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE operations(
          namespace TEXT NOT NULL, id TEXT NOT NULL, parent TEXT NOT NULL,
          principal TEXT NOT NULL, digest TEXT NOT NULL,
          request_json TEXT NOT NULL, plan_json TEXT NOT NULL,
          reserved_bytes INTEGER NOT NULL CHECK(reserved_bytes>0),
          record_json TEXT NOT NULL, PRIMARY KEY(namespace,id));
        CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT,
          namespace TEXT NOT NULL,id TEXT NOT NULL,kind TEXT NOT NULL,
          observed_at REAL NOT NULL,data_json TEXT NOT NULL);
        CREATE TABLE leases(resource TEXT PRIMARY KEY,owner TEXT NOT NULL,epoch INTEGER NOT NULL);
        CREATE TABLE revocations(principal TEXT PRIMARY KEY,generation INTEGER NOT NULL);
        CREATE TABLE counters(key TEXT PRIMARY KEY,value INTEGER NOT NULL);
        INSERT INTO counters VALUES('generation',1);
        CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN
          SELECT RAISE(ABORT,'immutable events'); END;
        CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN
          SELECT RAISE(ABORT,'immutable events'); END;
        CREATE TRIGGER identities_no_update BEFORE UPDATE OF namespace,id,parent,principal,digest,
          request_json,plan_json,reserved_bytes ON operations BEGIN
          SELECT RAISE(ABORT,'immutable identity'); END;
        CREATE TRIGGER operations_no_delete BEFORE DELETE ON operations BEGIN
          SELECT RAISE(ABORT,'immutable identity'); END;
        COMMIT;
        """)
        with self.transaction() as tx:
            tx.executemany("INSERT INTO metadata VALUES(?,?)", [
                ("schema", "1"), ("authority_id", self.authority_id), ("ledger_id", self.ledger_id)])

    @contextmanager
    def transaction(self):
        with self.lock:
            if not self.healthy:
                raise JobError("IO_UNCERTAIN", "Ledger durability is unresolved")
            try:
                self._db.execute("BEGIN IMMEDIATE")
                yield self._db
                self._db.execute("COMMIT")
            except sqlite3.Error as exc:
                self.healthy = False
                try:
                    self._db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise JobError("IO_UNCERTAIN", "Ledger transaction outcome is unresolved") from exc
            except BaseException:
                try:
                    if self._db.in_transaction:
                        self._db.execute("ROLLBACK")
                except sqlite3.Error as exc:
                    self.healthy = False
                    raise JobError("IO_UNCERTAIN", "Ledger rollback durability is unresolved") from exc
                raise

    def get(self, namespace, identity, tx=None):
        if tx is None:
            with self.transaction() as connection:
                return self.get(namespace, identity, connection)
        row = tx.execute("SELECT * FROM operations WHERE namespace=? AND id=?",
                         (namespace, identity)).fetchone()
        if row is None:
            return None
        result = dict(row)
        try:
            for name in ("request", "plan", "record"):
                result[name] = json.loads(result.pop(name + "_json"))
                if not isinstance(result[name], dict):
                    raise ValueError
        except (ValueError, TypeError) as exc:
            self.healthy = False
            raise JobError("IO_UNCERTAIN", "Ledger record integrity is unresolved") from exc
        return result

    def all(self, tx):
        return [self.get(row[0], row[1], tx) for row in tx.execute(
            "SELECT namespace,id FROM operations ORDER BY rowid").fetchall()]

    def insert(self, tx, namespace, identity, parent, principal, digest, request, plan, reserved_bytes):
        record = {"lifecycle": "ACCEPTED", "outcome": "PENDING", "evidence": "STAGING",
                  "phase": "QUEUED", "cancel_requested": False, "business_started": False,
                  "helper_started": False, "side_effects": "UNOBSERVED", "exit_proof": None,
                  "gaps": [], "outputs": {}, "observed_at": time.time(), "event_seq": 0}
        tx.execute("INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)", (
            namespace, identity, parent, principal, digest, encoded(request), encoded(plan),
            reserved_bytes, encoded(record)))
        self.update(tx, namespace, identity, "ACCEPTED", {})
        return self.get(namespace, identity, tx)

    def update(self, tx, namespace, identity, event, changes):
        row = self.get(namespace, identity, tx)
        if row is None:
            raise JobError("NOT_FOUND", "No record in the healthy ledger")
        record = row["record"]
        record.update(changes)
        now = time.time()
        cursor = tx.execute("INSERT INTO events(namespace,id,kind,observed_at,data_json) VALUES(?,?,?,?,?)",
                            (namespace, identity, event, now, encoded(changes)))
        record.update(event_seq=cursor.lastrowid, observed_at=now)
        tx.execute("UPDATE operations SET record_json=? WHERE namespace=? AND id=?",
                   (encoded(record), namespace, identity))
        return record

    def events(self, namespace, identity):
        with self.transaction() as tx:
            return [dict(row) for row in tx.execute(
                "SELECT * FROM events WHERE namespace=? AND id=? ORDER BY seq", (namespace, identity))]

    def close(self):
        with self.lock:
            self._db.close()
