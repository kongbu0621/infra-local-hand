"""Retained results remain readable without creating an execution manager."""
import os
import sqlite3
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from local_hand_jobs.broker import Broker
from local_hand_jobs.cli import MaintenanceServer, request
from local_hand_jobs.contract import JobError, Principal
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

    def test_retained_cancellation_acknowledges_only_a_valid_terminal_target_without_writes(self):
        args=dict(operation_id=self.f.request['operation_id'],
                  expected_request_digest=self.f.request['request_digest'],target={'kind':'job'})
        with self.assertRaises(JobError) as caught:self.broker.cancel(principal=self.f.owner,**args)
        self.assertEqual('IO_UNCERTAIN',caught.exception.code)
        self.assertFalse(self.f.status()['cancel_requested'])
        original=self.f.cancel()
        before=self.f.db.events('job',args['operation_id'])
        for _ in range(2):self.assertEqual(original,self.broker.cancel(principal=self.f.owner,**args))
        for changed,principal,code in (
                (dict(args,expected_request_digest='f'*64),self.f.owner,'CONFLICT'),
                (dict(args,target={'kind':'reconcile','reconcile_id':'12345678-1234-4234-8234-123456789abc'}),self.f.owner,'NOT_FOUND'),
                (args,Principal('other',self.f.owner.scopes),'UNAUTHORIZED'),
                (args,Principal('owner',frozenset({'lh:read'})),'UNAUTHORIZED')):
            with self.assertRaises(JobError) as caught:self.broker.cancel(principal=principal,**changed)
            self.assertEqual(code,caught.exception.code)
        self.assertEqual(before,self.f.db.events('job',args['operation_id']))
        self.assertEqual([],self.f.runner.starts)

    def test_resident_cancel_reaches_real_socket_and_durable_broker_then_retained_reader(self):
        from local_hand_mcp.resident import ResidentBroker
        self.f.broker.tick()
        self.f.policy.broker_root=Path(self.f.temp.name)
        self.broker.authority_lock=None
        server=MaintenanceServer(self.f.broker,Path(self.f.temp.name)/'maintenance.sock',{os.getuid():self.f.owner})
        self.addCleanup(server.close);server.start()
        service=Mock();service.call.return_value={'state':'RUNNING'}
        adapter=ResidentBroker(self.broker,{'retained':[]},service,Mock(return_value=self.broker))
        record=dict(operation_id=self.f.request['operation_id'],principal_id='owner',state='READY',
                    request=self.f.request,policy_path='/synthetic-policy')
        args=dict(operation_id=self.f.request['operation_id'],
                  expected_request_digest=self.f.request['request_digest'],target={'kind':'job'})
        with patch.object(adapter,'_record',return_value=record), \
             patch('local_hand_mcp.resident.Policy.from_file',return_value=self.f.policy):
            with self.assertRaises(JobError) as caught:
                adapter.call('lh_job_cancel',dict(args,expected_request_digest='f'*64),self.f.owner)
            self.assertEqual('CONFLICT',caught.exception.code)
            self.assertFalse(self.f.status()['cancel_requested'])
            result=adapter.call('lh_job_cancel',args,self.f.owner)
            self.assertTrue(result['cancel_requested'])
            self.assertNotEqual('TERMINAL',result['lifecycle'])
            events=self.f.db.events('job',args['operation_id'])
            self.assertEqual(result,adapter.call('lh_job_cancel',args,self.f.owner))
            self.assertEqual(events,self.f.db.events('job',args['operation_id']))
            self.f.broker.tick()
            self.assertTrue(self.f.runner.stops)
            self.f.runner.finish(self.f.runner.starts[0][1])
            self.f.broker.tick();self.f.broker.tick()
            self.assertEqual(1,len(self.f.runner.starts))
            self.assertEqual('TERMINAL',self.f.status()['lifecycle'])
            self.assertEqual('CANCELLED',self.f.status()['outcome'])
            service.call.return_value={'state':'EXITED'}
            events=self.f.db.events('job',args['operation_id'])
            self.assertEqual('CANCELLED',adapter.call('lh_job_cancel',args,self.f.owner)['outcome'])
            self.assertEqual(events,self.f.db.events('job',args['operation_id']))
        self.assertTrue(all(item.args[0]=='status' for item in service.call.call_args_list))

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
