"""Retained results remain readable without creating an execution manager."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from local_hand_jobs.broker import Broker
from local_hand_jobs.cli import MaintenanceServer, request
from local_hand_jobs.contract import JobError
from local_hand_jobs.state import StateStore
import test_local_hand_jobs_broker as fixtures


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux retained-result service")
class ReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.BrokerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.submit()
        self.state = StateStore(self.f.db.path, "authority", "ledger", read_only=True)
        self.addCleanup(self.state.close)
        self.broker = Broker(self.state, self.f.policy, fixtures.RegistryFixture(), None)
        self.addCleanup(self.broker.close)

    def test_real_client_reads_original_status_without_recovery_or_writes(self):
        before = self.f.db.events("job", self.f.request["operation_id"])
        with patch.object(self.broker, "recover") as recover:
            self.broker.start()
            recover.assert_not_called()
        self.assertIsNone(self.broker._thread)
        path = Path(self.f.temp.name) / "readonly.sock"
        server = MaintenanceServer(self.broker, path, {os.getuid(): self.f.owner})
        self.addCleanup(server.close)
        server.start()
        observed = request(path, "lh_job_status", {"operation_id": self.f.request["operation_id"]})
        self.assertEqual("ACCEPTED", observed["lifecycle"])
        for tool in ("lh_job_submit", "lh_job_cancel", "lh_job_reconcile"):
            with self.subTest(tool=tool), self.assertRaises(JobError) as caught:
                request(path, tool, self.f.request if tool == "lh_job_submit" else {})
            self.assertEqual("UNSUPPORTED", caught.exception.code)
        self.assertEqual(before, self.f.db.events("job", self.f.request["operation_id"]))
        self.assertTrue(self.state.healthy)
        self.assertEqual([], self.f.runner.starts)

    def test_sqlite_itself_refuses_a_write(self):
        with self.assertRaises(JobError):
            with self.state.transaction() as tx:
                tx.execute("UPDATE counters SET value=value+1 WHERE key='generation'")
        with self.f.db.transaction() as tx:
            self.assertEqual(1, tx.execute("SELECT value FROM counters WHERE key='generation'").fetchone()[0])

    def test_read_only_cannot_create_a_ledger(self):
        path = Path(self.f.temp.name) / "missing.sqlite"
        with self.assertRaises(ValueError):
            StateStore(path, "authority", "ledger", initialize=True, read_only=True)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
