from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs.contract import JobError
from local_hand_jobs.resources import AuthorityLock, ResourceManager
from local_hand_jobs.state import StateStore


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = StateStore(self.root / "state.sqlite", "authority", "ledger", initialize=True)
        self.addCleanup(self.db.close)

    def test_aliases_and_new_epoch_cannot_steal_lease(self):
        manager = ResourceManager({"profile-a": "physical", "bind-b": "physical"})
        with self.db.transaction() as tx:
            manager.acquire(tx, "original", 1, ["profile-a"])
        with self.assertRaises(JobError) as raised, self.db.transaction() as tx:
            manager.acquire(tx, "new-id", 200, ["bind-b"])
        self.assertEqual("RESOURCE_BUSY", raised.exception.code)
        with self.assertRaises(JobError), self.db.transaction() as tx:
            manager.release(tx, "original", future_start_blocked=False, tree_exited=True, effects_checked=True)
        with self.db.transaction() as tx:
            manager.assert_owned(tx, "original", 1, ["physical"])

    def test_same_authority_rejects_second_broker_and_second_root(self):
        anchor = self.root / "authority.json"
        anchor.write_text(json.dumps({"authority_id": "authority", "ledger_id": "ledger", "state_root": str(self.root)}))
        anchor.chmod(0o600)
        kwargs = {"authority_id": "authority", "ledger_id": "ledger", "state_root": self.root}
        with AuthorityLock(anchor, **kwargs):
            with self.assertRaises(JobError) as raised:
                AuthorityLock(anchor, **kwargs)
            self.assertEqual("RESOURCE_BUSY", raised.exception.code)
        with self.assertRaises(JobError) as raised:
            AuthorityLock(anchor, **dict(kwargs, state_root=self.root / "second"))
        self.assertEqual("CONFLICT", raised.exception.code)

    def test_missing_state_is_not_silently_recreated(self):
        with self.assertRaises(JobError) as raised:
            StateStore(self.root / "missing.sqlite", "authority", "ledger")
        self.assertEqual("IO_UNCERTAIN", raised.exception.code)
        self.assertFalse((self.root / "missing.sqlite").exists())

    def test_ledger_removed_between_lookup_and_connect_is_not_recreated(self):
        path = self.root / "removed.sqlite"
        StateStore(path, "authority", "ledger", initialize=True).close()
        real_connect = sqlite3.connect
        def disappear(*args, **kwargs):
            path.rename(self.root / "original.sqlite")
            return real_connect(*args, **kwargs)
        with mock.patch("local_hand_jobs.state.sqlite3.connect", side_effect=disappear):
            with self.assertRaises(JobError) as raised:
                StateStore(path, "authority", "ledger")
        self.assertEqual("IO_UNCERTAIN", raised.exception.code)
        self.assertFalse(path.exists())
        self.assertTrue((self.root / "original.sqlite").is_file())

    def test_ledger_uri_escapes_query_and_fragment_characters(self):
        path = self.root / "ledger ?mode=memory#%25.sqlite"
        with self.subTest("initialize"):
            StateStore(path, "authority", "ledger", initialize=True).close()
        with self.subTest("reopen"):
            StateStore(path, "authority", "ledger").close()
        self.assertTrue(path.is_file())

    def test_failed_ledger_constructor_closes_connection_and_preserves_primary(self):
        path = self.root / "construction.sqlite"
        StateStore(path, "authority", "ledger", initialize=True).close()
        real_connect = sqlite3.connect
        cases = [(KeyboardInterrupt("interrupted integrity check"), False),
                 (JobError("IO_UNCERTAIN", "original identity failure"), True),
                 (sqlite3.DatabaseError("original database failure"), True)]
        for primary, close_failure in cases:
            with self.subTest(type(primary).__name__):
                connections = []
                class Connection:
                    def __init__(self, *args, **kwargs):
                        self.raw = real_connect(*args, **kwargs)
                        self.closed = False
                        connections.append(self)
                    def execute(self, sql):
                        if sql == "PRAGMA quick_check":
                            raise primary
                        return self.raw.execute(sql)
                    def close(self):
                        self.raw.close()
                        self.closed = True
                        if close_failure:
                            raise OSError(5, "secondary cleanup failure")
                try:
                    error_type = JobError if isinstance(primary, sqlite3.Error) else type(primary)
                    with mock.patch("local_hand_jobs.state.sqlite3.connect", Connection):
                        with self.assertRaises(error_type) as raised:
                            StateStore(path, "authority", "ledger")
                    if isinstance(primary, sqlite3.Error):
                        self.assertEqual("IO_UNCERTAIN", raised.exception.code)
                        self.assertIs(primary, raised.exception.__cause__)
                    else:
                        self.assertIs(primary, raised.exception)
                    self.assertTrue(connections[0].closed)
                finally:
                    for connection in connections:
                        connection.raw.close()

    def test_linked_or_public_ledger_is_not_admitted(self):
        linked = self.root / "linked.sqlite"
        os.link(self.db.path, linked)
        with self.assertRaises(JobError):
            StateStore(linked, "authority", "ledger")
        linked.unlink()
        self.db.path.chmod(0o644)
        with self.assertRaises(JobError):
            StateStore(self.db.path, "authority", "ledger")
        self.db.path.chmod(0o600)

    def test_ambiguous_or_nonfinite_ledger_json_closes_admission(self):
        payloads = ['{"outcome":"UNKNOWN","outcome":"SUCCEEDED"}',
                    '{"facts":{"stable":false,"stable":true}}']
        payloads.extend('{"observed_at":' + item + '}'
                        for item in ('NaN', 'Infinity', '-Infinity', '1e400', '-1e400'))
        for index, payload in enumerate(payloads):
            with self.subTest(payload=payload):
                state = StateStore(self.root / f"damaged-{index}.sqlite", "authority", "ledger", initialize=True)
                try:
                    with state.transaction() as tx:
                        state.insert(tx, "job", "id", "id", "owner", "a" * 64, {}, {}, 1000)
                        # The normal encoder rejects these values. Simulate
                        # damaged persisted TEXT, not an allowed state update.
                        tx.execute("UPDATE operations SET record_json=?", (payload,))
                    with self.assertRaises(JobError) as raised:
                        state.get("job", "id")
                    self.assertEqual("IO_UNCERTAIN", raised.exception.code)
                    self.assertFalse(state.healthy)
                    with self.assertRaises(JobError) as missing:
                        state.get("job", "missing")
                    self.assertEqual("IO_UNCERTAIN", missing.exception.code)
                finally:
                    state.close()

    def test_ledger_decoder_recursion_failure_is_storage_uncertainty(self):
        with self.db.transaction() as tx:
            self.db.insert(tx, "job", "id", "id", "owner", "a" * 64, {}, {}, 1000)
            self.db.update(tx, "job", "id", "OBSERVED", {"facts": {"duration": 1.125}})
        self.assertEqual(1.125, self.db.get("job", "id")["record"]["facts"]["duration"])
        failure = RecursionError("synthetic decoder budget exhaustion")
        with mock.patch("local_hand_jobs.state.json.loads", side_effect=failure):
            with self.assertRaises(JobError) as raised:
                self.db.get("job", "id")
        self.assertEqual("IO_UNCERTAIN", raised.exception.code)
        self.assertIs(failure, raised.exception.__cause__)
        self.assertFalse(self.db.healthy)

    def test_hardlinked_authority_anchor_is_not_an_independent_lock(self):
        anchor = self.root / "anchor"
        anchor.write_text(json.dumps({"authority_id": "authority", "ledger_id": "ledger", "state_root": str(self.root)}))
        anchor.chmod(0o600)
        os.link(anchor, self.root / "alias")
        with self.assertRaises(JobError) as raised:
            AuthorityLock(anchor, authority_id="authority", ledger_id="ledger", state_root=self.root)
        self.assertEqual("UNAUTHORIZED", raised.exception.code)

    def test_fifo_state_and_anchor_fail_without_waiting_for_a_writer(self):
        fifo = self.root / "fifo"
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(JobError):
            StateStore(fifo, "authority", "ledger")
        with self.assertRaises(JobError):
            AuthorityLock(fifo, authority_id="authority", ledger_id="ledger", state_root=self.root)

    def _authority(self):
        anchor = self.root / "authority.json"
        anchor.write_text(json.dumps({"authority_id": "authority", "ledger_id": "ledger", "state_root": str(self.root)}))
        anchor.chmod(0o600)
        return anchor, {"authority_id": "authority", "ledger_id": "ledger", "state_root": self.root}

    def test_authority_short_read_does_not_admit_a_valid_json_prefix(self):
        anchor, kwargs = self._authority()
        valid_prefix = anchor.read_bytes()
        anchor.write_bytes(valid_prefix + b" invalid registration suffix")
        real_read = os.read
        def short_read(descriptor, count):
            return real_read(descriptor, min(count, len(valid_prefix)))
        with mock.patch("local_hand_jobs.resources.os.read", side_effect=short_read):
            with self.assertRaises(JobError) as raised:
                AuthorityLock(anchor, **kwargs)
        self.assertEqual("IO_UNCERTAIN", raised.exception.code)

    def test_duplicate_authority_members_are_rejected_and_release_the_lock(self):
        anchor, kwargs = self._authority()
        original = anchor.read_bytes()
        for key in ("authority_id", "ledger_id", "state_root"):
            with self.subTest(key=key):
                duplicate = b'{' + json.dumps(key).encode() + b':"foreign",' + original[1:]
                anchor.write_bytes(duplicate)
                with self.assertRaises(JobError) as raised:
                    AuthorityLock(anchor, **kwargs)
                self.assertEqual("IO_UNCERTAIN", raised.exception.code)
                self.assertEqual(duplicate, anchor.read_bytes())
                # The failed parser must not retain the private authority lock.
                anchor.write_bytes(original)
                with AuthorityLock(anchor, **kwargs):
                    pass

    def test_authority_close_error_cannot_close_a_reused_descriptor(self):
        anchor, kwargs = self._authority()
        lock = AuthorityLock(anchor, **kwargs)
        descriptor, real_close = lock.fd, os.close
        def close_then_fail(fd):
            real_close(fd)
            raise OSError(5, "synthetic close error after release")
        with mock.patch("local_hand_jobs.resources.os.close", side_effect=close_then_fail):
            with self.assertRaises(OSError):
                lock.close()
        foreign = os.open(self.root / "foreign", os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            self.assertEqual(descriptor, foreign)
            lock.close()
            os.fstat(foreign)
            self.assertIsNone(lock.fd)
        finally:
            real_close(foreign)

    def test_authority_primary_error_survives_descriptor_cleanup_error(self):
        anchor, kwargs = self._authority()
        real_close = os.close
        def close_then_fail(fd):
            real_close(fd)
            raise OSError(5, "synthetic close error after release")
        with mock.patch("local_hand_jobs.resources.os.close", side_effect=close_then_fail):
            with self.assertRaises(JobError) as rejected:
                AuthorityLock(anchor, **dict(kwargs, ledger_id="other"))
            self.assertEqual("CONFLICT", rejected.exception.code)
            primary = KeyboardInterrupt("synthetic original interruption")
            with self.assertRaises(KeyboardInterrupt) as interrupted:
                with AuthorityLock(anchor, **kwargs):
                    raise primary
            self.assertIs(primary, interrupted.exception)
            try:
                raise ValueError("unrelated caller exception")
            except ValueError:
                with self.assertRaises(OSError):
                    with AuthorityLock(anchor, **kwargs):
                        pass


if __name__ == "__main__":
    unittest.main()
