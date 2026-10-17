"""Temporary A2 retirement blocks new work without losing retained identities."""
import copy
import sys
import unittest
from unittest.mock import Mock, patch

from local_hand_jobs.contract import JobError, Principal, request_digest
import test_local_hand_jobs_broker as broker_fixtures


class RetiredBrokerTests(unittest.TestCase):
    setUp = broker_fixtures.BrokerTests.setUp
    submit = broker_fixtures.BrokerTests.submit
    status = broker_fixtures.BrokerTests.status
    cancel = broker_fixtures.BrokerTests.cancel
    make_request = broker_fixtures.BrokerTests.make_request

    def test_new_job_cannot_reach_task_session_plan_or_resource_reservation(self):
        retired = dict(self.request, kind='ledger.test.local_a2', inputs={'runtime_ref': 'installed-a2'})
        retired['request_digest'] = request_digest(retired)
        session = Mock()
        with patch.object(self.broker, 'task_session', session), \
             patch.object(self.broker.registry, 'resolve') as resolve:
            with self.assertRaises(JobError) as caught:
                self.broker.call('lh_job_submit', retired, self.owner)
            self.assertEqual('UNSUPPORTED', caught.exception.code)
            session.admit.assert_not_called(); resolve.assert_not_called()
        self.assertIsNone(self.db.get('job', retired['operation_id']))
        self.assertFalse(self.runner.starts)
        # No ID or capacity was consumed: an ordinary job still works.
        self.submit(); self.broker.tick()
        self.assertEqual(1, len(self.runner.starts))

    def test_original_admission_remains_queryable_idempotent_and_cancellable(self):
        self.request.update(kind='ledger.test.local_a2', inputs={'runtime_ref': 'installed-a2'})
        self.request['request_digest'] = request_digest(self.request)
        plan = self.broker.registry.resolve(self.request, self.policy, principal=self.owner)
        operation = self.request['operation_id']
        with self.db.transaction() as tx:
            self.db.insert(tx, 'job', operation, operation, self.owner.principal_id,
                           self.request['request_digest'], self.request, plan, plan['reservation_bytes'])
        original = copy.deepcopy(self.db.get('job', operation))
        with patch.object(self.broker.registry, 'resolve') as resolve:
            self.assertEqual(dict(self.submit(), reconciliations=[]), self.status())
            self.assertEqual(original, self.db.get('job', operation))
            resolve.assert_not_called()
        self.assertEqual('CANCELLED', self.cancel()['outcome'])
        self.assertFalse(self.runner.starts)


if sys.platform.startswith('linux'):
    from local_hand_jobs.policy import Policy
    from test_local_hand_jobs_local_a2_admission import local_a2_policy_fixture
    import test_local_hand_resident as resident_fixtures
    import test_local_hand_local_a2_registration_recovery as recovery_fixtures

    class RetiredResidentTests(unittest.TestCase):
        call = resident_fixtures.ResidentTests.call

        def setUp(self):
            resident_fixtures.ResidentTests.setUp(self)
            self.policy = Policy(local_a2_policy_fixture('/synthetic-resident'))
            self.broker.policy = self.policy
            self.request.update(kind='ledger.test.local_a2', inputs={'runtime_ref': 'installed-a2'},
                                expected=self.policy.expected('fixture'))
            self.request['request_digest'] = request_digest(self.request)
            self.broker.config['local_a2'] = dict(runtime_refs=['installed-a2'], budgets={})
            current = patch('local_hand_mcp.resident.Policy.from_file', return_value=self.policy)
            current.start(); self.addCleanup(current.stop)

        def test_ready_but_unsubmitted_job_cannot_start_controller(self):
            self.service.call.return_value = {'state': 'IDLE'}
            with self.assertRaises(JobError) as caught:
                self.call('lh_job_submit', self.request)
            self.assertEqual('UNSUPPORTED', caught.exception.code)
            self.service.call.assert_called_once_with('status', operation_id=self.request['operation_id'],
                                                      principal_id='owner')
            self.local.assert_not_called()

        def test_exited_original_submit_returns_record_without_start_or_replay(self):
            self.service.call.return_value = {'state': 'EXITED'}
            self.reader.state.get.return_value = dict(digest=self.request['request_digest'], principal='owner')
            self.reader._view.return_value = {'outcome': 'SUCCEEDED'}
            self.assertEqual({'outcome': 'SUCCEEDED'}, self.call('lh_job_submit', self.request))
            self.service.call.assert_called_once_with('status', operation_id=self.request['operation_id'],
                                                      principal_id='owner')
            self.local.assert_not_called()

        def test_retained_submit_requires_read_at_every_authority(self):
            import sqlite3
            from types import MethodType
            from local_hand_jobs.broker import Broker
            from local_hand_jobs.policy import thaw

            limited = thaw(self.policy.config)
            limited['principals']['owner']['scopes'].remove('lh:read')
            limited = Policy(limited)
            # Use the real reader authorization and durable revocation check;
            # only the stored row and execution-state observation are modeled.
            db = sqlite3.connect(':memory:')
            db.execute('CREATE TABLE revocations(principal TEXT)')
            self.addCleanup(db.close)
            self.reader.state.transaction.return_value = db
            self.reader._authorize = MethodType(Broker._authorize, self.reader)
            self.reader.state.get.return_value = dict(digest=self.request['request_digest'], principal='owner')
            for state in ('EXITED', 'UNRESOLVED'):
                for denied in ('token', 'entry_grant', 'task_grant', 'reader_grant', 'reader_revoked'):
                    self.service.call.return_value = {'state': state}
                    self.reader._view.reset_mock()
                    self.reader.policy = limited if denied == 'reader_grant' else self.policy
                    db.execute('DELETE FROM revocations')
                    if denied == 'reader_revoked':
                        db.execute('INSERT INTO revocations VALUES (?)', ('owner',))
                    principal = (Principal('owner', self.owner.scopes - {'lh:read'})
                                 if denied == 'token' else self.owner)
                    with self.subTest(state=state, denied=denied), \
                         patch.object(self.broker, 'policy', limited if denied == 'entry_grant' else self.policy), \
                         patch('local_hand_mcp.resident.Policy.from_file',
                               return_value=limited if denied == 'task_grant' else self.policy):
                        with self.assertRaises(JobError) as caught:
                            self.call('lh_job_submit', self.request, principal)
                        self.assertEqual('UNAUTHORIZED', caught.exception.code)
                        self.reader._view.assert_not_called()
                db.execute('DELETE FROM revocations')
                self.reader.policy = self.policy
                original = dict(operation_id=self.request['operation_id'], outcome='UNKNOWN')
                self.reader._view.return_value = original
                self.assertEqual(original, self.call('lh_job_submit', self.request))
            self.local.assert_not_called()
            self.assertTrue(all(c.args[0] == 'status' for c in self.service.call.call_args_list))

        def test_running_old_controller_never_receives_first_submit(self):
            self.service.call.return_value = {'state': 'RUNNING'}
            def old_controller(path, name, args, **kwargs):
                if name == 'lh_job_submit':
                    return dict(operation_id=self.request['operation_id'],
                                request_digest=self.request['request_digest'], lifecycle='ACCEPTED')
                raise JobError('NOT_FOUND', 'Controller started but no request was committed')
            self.local.side_effect = old_controller
            with self.assertRaises(JobError) as caught:
                self.call('lh_job_submit', self.request)
            self.assertEqual('NOT_FOUND', caught.exception.code)
            self.assertEqual(['lh_job_status'], [c.args[1] for c in self.local.call_args_list])
            self.assertEqual(['status'], [c.args[0] for c in self.service.call.call_args_list])

        def test_running_original_submit_becomes_bound_status_query(self):
            self.service.call.return_value = {'state': 'RUNNING'}
            result = dict(operation_id=self.request['operation_id'],
                          request_digest=self.request['request_digest'], outcome='UNKNOWN')
            self.local.return_value = result
            self.assertEqual(result, self.call('lh_job_submit', self.request))
            self.assertEqual('lh_job_status', self.local.call_args.args[1])
            self.assertEqual({'operation_id': self.request['operation_id']}, self.local.call_args.args[2])

        def test_running_retired_query_requires_read_scope_and_original_binding(self):
            self.service.call.return_value = {'state': 'RUNNING'}
            submit_only = Principal('owner', frozenset({'lh:submit'}))
            with self.assertRaises(JobError) as caught:
                self.call('lh_job_submit', self.request, submit_only)
            self.assertEqual('UNAUTHORIZED', caught.exception.code)
            self.local.assert_not_called()
            for key in ('operation_id', 'request_digest'):
                result = {field: self.request[field] for field in ('operation_id', 'request_digest')}
                result[key] = 'foreign'
                self.local.return_value = result
                with self.subTest(key=key), self.assertRaises(JobError) as caught:
                    self.call('lh_job_submit', self.request)
                self.assertEqual('CONFLICT', caught.exception.code)

        def test_retired_query_crossing_exit_keeps_original_task(self):
            self.service.call.side_effect = [{'state': 'RUNNING'}, {'state': 'EXITED'}]
            self.local.side_effect = JobError('IO_UNCERTAIN', 'Controller exited during query')
            original = dict(operation_id=self.request['operation_id'],
                            request_digest=self.request['request_digest'], outcome='UNKNOWN')
            self.reader.call.return_value = original
            self.assertEqual(original, self.call('lh_job_submit', self.request))
            self.reader.call.assert_called_once_with('lh_job_status',
                {'operation_id': self.request['operation_id']}, self.owner)
            self.assertEqual(['lh_job_status'], [c.args[1] for c in self.local.call_args_list])

        def test_retained_status_and_evidence_still_route_to_original_reader(self):
            self.service.call.return_value = {'state': 'EXITED'}
            args = {'operation_id': self.request['operation_id']}
            self.reader.call.return_value = {'outcome': 'UNKNOWN'}
            self.assertEqual({'outcome': 'UNKNOWN'}, self.call('lh_job_status', args))
            self.reader.call.assert_called_with('lh_job_status', args, self.owner)
            manifest = dict(artifacts=[], catalog_digest='a'*64)
            self.reader.call.return_value = manifest
            self.assertEqual(manifest, self.call('lh_evidence_manifest', args))
            self.reader.call.assert_called_with('lh_evidence_manifest', args, self.owner)
            self.local.assert_not_called()
            self.assertTrue(all(c.args[0] == 'status' for c in self.service.call.call_args_list))

        def test_mcp_discovery_new_admission_and_original_ready_response(self):
            from dataclasses import replace
            import sqlite3
            from test_local_hand_mcp_auth import HAS_EXTRA, SyntheticIssuer
            from test_local_hand_mcp_server import ASGIClient
            from local_hand_mcp.server import create_app
            if not HAS_EXTRA:
                self.skipTest('Optional pinned MCP extra is not installed')
            issuer = SyntheticIssuer()
            issuer.verifier.config = replace(issuer.config, subject_map={'issuer-user-a': 'owner'})
            # Dispatch runs in the real SDK worker thread. Only the manager is
            # modeled; authentication, broker policy and MCP serialization run.
            db = sqlite3.connect(':memory:', check_same_thread=False)
            db.execute('CREATE TABLE revocations(principal TEXT)')
            self.addCleanup(db.close)
            self.retained.state.transaction.return_value = db
            headers = {'Authorization': 'Bearer ' + issuer.token(),
                       'Accept': 'application/json, text/event-stream'}
            with ASGIClient(create_app(self.broker, issuer.verifier), 'http://127.0.0.1:8765') as client:
                def rpc(method, params=None):
                    response = client.post('/mcp', json=dict(jsonrpc='2.0', id=1, method=method,
                                                           params=params or {}), headers=headers)
                    self.assertEqual(200, response.status_code, response.text)
                    return response.json()['result']
                tools = {tool['name']: tool for tool in rpc('tools/list')['tools']}
                for name in ('lh_job_prepare', 'lh_job_submit'):
                    kinds = {v['properties']['kind']['const'] for v in tools[name]['inputSchema']['oneOf']}
                    self.assertNotIn('ledger.test.local_a2', kinds)
                args = dict(operation_id=self.request['operation_id'], kind=self.request['kind'],
                            profile_ref='fixture', inputs=self.request['inputs'])
                self.broker._record.return_value = None
                refused = rpc('tools/call', dict(name='lh_job_prepare', arguments=args))
                self.assertTrue(refused['isError'])
                self.assertEqual('UNSUPPORTED', refused['structuredContent']['error']['code'])
                self.service.call.assert_not_called()
                self.broker._record.return_value = self.record
                original = dict(state='READY', operation_id=args['operation_id'], request=self.request)
                self.service.call.return_value = original
                polled = rpc('tools/call', dict(name='lh_job_prepare', arguments=args))
                self.assertFalse(polled.get('isError', False), polled)
                self.assertEqual(original, polled['structuredContent'])
                self.service.call.assert_called_once_with('prepare', principal_id='owner',
                                                          **args, allow_new=False)
                self.service.call.reset_mock()
                self.service.call.return_value = {'state': 'RUNNING'}
                status = dict(operation_id=self.request['operation_id'],
                    request_digest=self.request['request_digest'], lifecycle='RUNNING',
                    outcome='UNKNOWN', evidence='STAGING', phase='PREFLIGHT')
                self.local.return_value = status
                observed = rpc('tools/call', dict(name='lh_job_submit', arguments=self.request))
                self.assertFalse(observed.get('isError', False), observed)
                self.assertEqual(status, observed['structuredContent'])
                self.assertEqual('lh_job_status', self.local.call_args.args[1])
                self.assertEqual(['status'], [c.args[0] for c in self.service.call.call_args_list])
                self.service.call.reset_mock()
                self.local.reset_mock()
                self.service.call.return_value = {'state': 'EXITED'}
                self.reader.state.get.return_value = dict(digest=self.request['request_digest'], principal='owner')
                self.reader._view.return_value = status
                headers['Authorization'] = 'Bearer ' + issuer.token(claims={'scope': 'lh:submit'})
                refused = rpc('tools/call', dict(name='lh_job_submit', arguments=self.request))
                self.assertTrue(refused['isError'])
                self.assertEqual('UNAUTHORIZED', refused['structuredContent']['error']['code'])
                self.reader._view.assert_not_called()
                headers['Authorization'] = 'Bearer ' + issuer.token()
                observed = rpc('tools/call', dict(name='lh_job_submit', arguments=self.request))
                self.assertFalse(observed.get('isError', False), observed)
                self.assertEqual(status, observed['structuredContent'])
                self.assertEqual(['status', 'status'], [c.args[0] for c in self.service.call.call_args_list])
                self.local.assert_not_called()

    class RetiredManagerTests(unittest.TestCase):
        setUp = recovery_fixtures.RuntimePreparationRecoveryTests.setUp
        ready = recovery_fixtures.RuntimePreparationRecoveryTests.ready

        def test_direct_manager_start_cannot_bypass_retirement(self):
            record = self.ready()
            args = dict(action='start', operation_id=record['operation_id'], principal_id='owner',
                        request_digest=record['request']['request_digest'])
            with patch.object(self.service, 'execution_state', return_value='IDLE'), \
                 patch.object(self.service, '_launcher') as launch:
                with self.assertRaises(JobError) as caught:
                    self.service.call(args)
                self.assertEqual('UNSUPPORTED', caught.exception.code)
                launch.assert_not_called()
            self.assertEqual(record, self.service.records[record['operation_id']])

        def test_existing_controller_is_observed_without_relaunch(self):
            record = self.ready()
            args = dict(action='start', operation_id=record['operation_id'], principal_id='owner',
                        request_digest=record['request']['request_digest'])
            for state in ('RUNNING', 'EXITED', 'UNRESOLVED'):
                with self.subTest(state=state), \
                     patch.object(self.service, 'execution_state', return_value=state), \
                     patch.object(self.service, '_launcher') as launch:
                    self.assertEqual(dict(state=state), self.service.call(args))
                    launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
