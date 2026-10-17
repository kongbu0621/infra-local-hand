"""Prepared adapter admission and retries; execution is covered by TaskService."""
import copy
import sqlite3
import time
import unittest
import uuid
from unittest.mock import Mock, patch

from local_hand_jobs.contract import JobError, Principal, TOOL_SCOPES, request_digest
from local_hand_jobs.policy import Policy
from local_hand_mcp.prepared import PreparedBroker
from test_local_hand_jobs_policy import policy_fixture


class PreparedTests(unittest.TestCase):
    def setUp(self):
        self.policy = Policy(policy_fixture('/synthetic-prepared'))
        self.owner = Principal('owner', frozenset(TOOL_SCOPES.values()))
        self.request = dict(schema_version='lh-job-v1', operation_id=str(uuid.uuid4()), kind='host.inspect',
            profile_ref='fixture', expected=self.policy.expected('fixture'), inputs={}, expires_at=int(time.time())+120)
        self.request['request_digest'] = request_digest(self.request)
        self.retained = Mock()
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE revocations(principal TEXT)')
        self.addCleanup(db.close)
        self.retained.state.transaction.return_value = db
        self.retained.state.get.return_value = None
        self.launcher = Mock()
        self.reader = Mock()
        self.factory = Mock(return_value=self.reader)
        self.router = PreparedBroker(self.retained, self.policy, self.request, 'owner', self.launcher, self.factory)
        self.local = patch('local_hand_mcp.prepared.cli.request').start()
        self.addCleanup(patch.stopall)

    def call(self, name='lh_job_submit', args=None, principal=None):
        return self.router.call(name, self.request if args is None else args, principal or self.owner)

    def test_capabilities_and_unsubmitted_status_never_start_execution(self):
        self.call('lh_capabilities', {})
        self.launcher.call.assert_not_called()
        self.launcher.call.return_value = 'IDLE'
        with self.assertRaises(JobError) as caught:
            self.call('lh_job_status', {'operation_id': self.request['operation_id']})
        self.assertEqual('NOT_FOUND', caught.exception.code)
        self.assertEqual(['status'], [x.args[0] for x in self.launcher.call.call_args_list])
        self.local.assert_not_called()

    def test_missing_scope_foreign_principal_and_changed_request_do_not_start(self):
        cases = [(self.request, Principal('owner', frozenset({'lh:read'}))),
                 (self.request, Principal('other', self.owner.scopes))]
        changed = dict(self.request, operation_id=str(uuid.uuid4()))
        changed['request_digest'] = request_digest(changed)
        cases.append((changed, self.owner))
        changed = dict(self.request, expires_at=self.request['expires_at'] + 1)
        changed['request_digest'] = request_digest(changed)
        cases.append((changed, self.owner))
        for args, principal in cases:
            with self.subTest(principal=principal, args=args), self.assertRaises(JobError):
                self.call(args=args, principal=principal)
        self.launcher.call.assert_not_called()
        self.local.assert_not_called()

    def test_expired_unsubmitted_request_does_not_start(self):
        with patch('local_hand_mcp.prepared.time.time', return_value=self.request['expires_at']+1):
            self.launcher.call.return_value = 'IDLE'
            with self.assertRaises(JobError) as caught:
                self.call()
        self.assertEqual('STALE_DEPLOYMENT', caught.exception.code)
        self.assertEqual(['status'], [x.args[0] for x in self.launcher.call.call_args_list])

    def test_only_submission_starts_then_uses_real_broker_protocol(self):
        self.launcher.call.side_effect = ['IDLE', 'RUNNING', 'RUNNING']
        self.local.return_value = {'lifecycle': 'ACCEPTED'}
        self.assertEqual({'lifecycle': 'ACCEPTED'}, self.call())
        self.call()
        self.assertEqual(['status', 'start', 'status'], [x.args[0] for x in self.launcher.call.call_args_list])
        self.assertEqual(2, self.local.call_count)
        self.assertEqual(self.request, self.local.call_args.args[2])

    def test_lost_submit_reply_is_queried_without_restarting_controller(self):
        self.launcher.call.side_effect = ['IDLE', 'RUNNING', 'RUNNING']
        self.local.side_effect = [JobError('IO_UNCERTAIN', 'lost receipt'), {'outcome': 'SUCCEEDED'}]
        with self.assertRaises(JobError):
            self.call()
        self.assertEqual({'outcome': 'SUCCEEDED'}, self.call('lh_job_status', {'operation_id': self.request['operation_id']}))
        self.assertEqual(1, sum(x.args[0] == 'start' for x in self.launcher.call.call_args_list))
        self.assertEqual('lh_job_status', self.local.call_args.args[1])

    def test_temporary_launcher_read_failure_can_be_retried(self):
        self.launcher.call.side_effect = [JobError('IO_UNCERTAIN', 'read failure'), 'IDLE', 'RUNNING']
        with self.assertRaises(JobError):
            self.call()
        self.call()
        self.local.assert_called_once()

    def test_original_task_and_evidence_keep_their_reader(self):
        self.call('lh_job_status', {'operation_id': str(uuid.uuid4())})
        self.call('lh_evidence_read_chunk', {'artifact_id': str(uuid.uuid4())+'.zip',
                  'expected_sha256': 'a'*64, 'offset': 0})
        self.assertEqual(2, self.retained.call.call_count)
        self.launcher.call.assert_not_called()

    def test_completed_controller_only_opens_read_only_result_service(self):
        self.launcher.call.return_value = 'EXITED'
        self.reader.state.get.return_value = {'digest': self.request['request_digest'], 'principal': 'owner'}
        self.reader._view.return_value = {'outcome': 'SUCCEEDED'}
        self.assertEqual({'outcome': 'SUCCEEDED'}, self.call())
        self.call('lh_job_status', {'operation_id': self.request['operation_id']})
        self.factory.assert_called_once()
        self.local.assert_not_called()
        self.assertEqual(['status', 'status'], [x.args[0] for x in self.launcher.call.call_args_list])

    def test_exit_without_committed_job_is_unknown_and_never_resubmitted(self):
        self.launcher.call.return_value = 'EXITED'
        self.reader.state.get.return_value = None
        with self.assertRaises(JobError) as caught:
            self.call()
        self.assertEqual('IO_UNCERTAIN', caught.exception.code)
        self.local.assert_not_called()

    def test_completed_submit_keeps_read_permissions_and_revocation_effective(self):
        from types import MethodType
        from local_hand_jobs.broker import Broker
        from local_hand_jobs.policy import thaw

        limited = thaw(self.policy.config)
        limited['principals']['owner']['scopes'].remove('lh:read')
        limited = Policy(limited)
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE revocations(principal TEXT)')
        self.addCleanup(db.close)
        self.reader.state.transaction.return_value = db
        self.reader._authorize = MethodType(Broker._authorize, self.reader)
        self.reader.state.get.return_value = dict(digest=self.request['request_digest'], principal='owner')
        self.launcher.call.return_value = 'EXITED'
        for denied in ('token', 'entry_grant', 'reader_grant', 'reader_revoked'):
            self.reader.policy = limited if denied == 'reader_grant' else self.policy
            if denied == 'reader_revoked':
                db.execute('INSERT INTO revocations VALUES (?)', ('owner',))
            principal = (Principal('owner', self.owner.scopes - {'lh:read'})
                         if denied == 'token' else self.owner)
            with self.subTest(denied=denied), \
                 patch.object(self.router, 'policy', limited if denied == 'entry_grant' else self.policy):
                with self.assertRaises(JobError) as caught:
                    self.call(principal=principal)
                self.assertEqual('UNAUTHORIZED', caught.exception.code)
                self.reader._view.assert_not_called()
        db.execute('DELETE FROM revocations')
        self.reader.policy = self.policy
        self.reader._view.return_value = {'outcome': 'UNKNOWN'}
        self.assertEqual({'outcome': 'UNKNOWN'}, self.call())
        self.local.assert_not_called()
        self.assertTrue(all(c.args[0] == 'status' for c in self.launcher.call.call_args_list))

    def test_close_preserves_retained_cleanup_when_new_reader_fails(self):
        self.router.reader = self.reader
        self.reader.close.side_effect = OSError('modeled close failure')
        with self.assertRaises(OSError):
            self.router.close()
        self.retained.close.assert_called_once()
        self.reader.state.close.assert_called_once()
        self.reader.authority_lock.close.assert_called_once()
