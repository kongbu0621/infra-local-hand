from __future__ import annotations

import json
import os
from pathlib import Path
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
