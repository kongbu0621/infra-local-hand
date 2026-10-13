"""Retained results remain readable without creating an execution manager."""
import os
import sqlite3
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

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

    def test_resident_read_recovers_after_real_sqlite_lock_contention(self):
        from local_hand_mcp.resident import ResidentBroker
        # Rollback-journal ledgers are valid retained inputs. An exclusive
        # writer makes the actual SQLite read return BUSY, without any writes
        # by this adapter or a mocked database error.
        self.state.close();self.f.db.close()
        writer=sqlite3.connect(self.f.db.path,isolation_level=None)
        self.addCleanup(writer.close)
        writer.execute('PRAGMA journal_mode=DELETE')
        state=StateStore(self.f.db.path,'authority','ledger',read_only=True)
        self.addCleanup(state.close)
        retained=Broker(state,self.f.policy,fixtures.RegistryFixture(),None)
        retained.authority_lock=None
        self.addCleanup(retained.close)
        service=Mock();factory=Mock()
        adapter=ResidentBroker(retained,{'retained':[]},service,factory)
        args={'operation_id':self.f.request['operation_id']}
        before=writer.execute('SELECT * FROM events ORDER BY seq').fetchall()
        with patch.object(adapter,'_record',return_value=None):
            writer.execute('BEGIN EXCLUSIVE')
            with self.assertRaises(JobError) as caught:
                adapter.call('lh_job_status',args,self.f.owner)
            self.assertEqual('IO_UNCERTAIN',caught.exception.code)
            self.assertEqual(sqlite3.SQLITE_BUSY,caught.exception.__cause__.sqlite_errorcode)
            writer.execute('ROLLBACK')
            observed=adapter.call('lh_job_status',args,self.f.owner)
        self.assertEqual('ACCEPTED',observed['lifecycle'])
        self.assertEqual(before,writer.execute('SELECT * FROM events ORDER BY seq').fetchall())
        self.assertTrue(state.healthy)
        service.call.assert_not_called();factory.assert_not_called()
        self.assertEqual([],self.f.runner.starts)

    def test_io_error_failed_rollback_and_writable_contention_remain_unresolved(self):
        cases=((True,sqlite3.SQLITE_IOERR,False),(True,sqlite3.SQLITE_BUSY,True),
               (False,sqlite3.SQLITE_BUSY,False))
        for read_only,code,failed_rollback in cases:
            with self.subTest(read_only=read_only,code=code,failed_rollback=failed_rollback):
                state=StateStore(self.f.db.path,'authority','ledger',read_only=read_only)
                self.addCleanup(state.close)
                connection=state._db
                error=sqlite3.OperationalError('injected read failure');error.sqlite_errorcode=code
                class Connection:
                    def __init__(self,connection,failed):self.connection,self.failed=connection,failed
                    def __getattr__(self,name):return getattr(self.connection,name)
                    def execute(self,sql,*args):
                        if self.failed and sql=='ROLLBACK':
                            raise sqlite3.OperationalError('injected rollback failure')
                        return self.connection.execute(sql,*args)
                state._db=Connection(connection,failed_rollback)
                with self.assertRaises(JobError):
                    with state.transaction():raise error
                self.assertFalse(state.healthy)
                with self.assertRaises(JobError):state.get('job',self.f.request['operation_id'])
                state.close()


if __name__ == "__main__":
    unittest.main()
