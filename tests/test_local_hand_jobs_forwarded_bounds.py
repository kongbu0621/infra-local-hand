"""Network authority must survive authenticated local transport boundaries."""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from local_hand_jobs import cli, forwarded_bounds
from local_hand_jobs.contract import JobError, Principal, TOOL_SCOPES
from local_hand_mcp.resident import ResidentBroker
import test_local_hand_resident as fixtures
import test_local_hand_mcp_prepared as prepared_fixtures
import test_local_hand_prepared_service as launch_fixtures


class BoundsTests(unittest.TestCase):
    def setUp(self):
        self.cutoff = int(time.time()) + 300
        self.peer = Principal('owner', frozenset({'lh:read', 'lh:submit'}))
        self.network = Principal('owner', frozenset({'lh:read'}), expires_at=self.cutoff)
        self.body = {'tool': 'lh_job_status', 'arguments': {'operation_id': 'fixture'}}

    def test_bounds_preserve_original_scope_deadline_and_request(self):
        sent = forwarded_bounds.attach(self.body, self.network)
        body, admitted = forwarded_bounds.restrict(sent, self.peer)
        self.assertEqual(self.body, body)
        self.assertEqual(self.network.scopes, admitted.scopes)
        self.assertEqual(self.cutoff, admitted.expires_at)
        self.assertNotIn('token', json.dumps(sent))

    def test_peer_grant_is_an_independent_upper_bound(self):
        other = Principal('owner', frozenset({'lh:read', 'lh:cancel'}), expires_at=self.cutoff + 1)
        _, admitted = forwarded_bounds.restrict(forwarded_bounds.attach(self.body, other),
            Principal('owner', frozenset({'lh:read'}), expires_at=self.cutoff))
        self.assertEqual(frozenset({'lh:read'}), admitted.scopes)
        self.assertEqual(self.cutoff, admitted.expires_at)

    def test_changed_request_identity_and_malformed_bounds_are_refused(self):
        original = forwarded_bounds.attach(self.body, self.network)
        changes = [lambda d: d['arguments'].update(operation_id='another-task'),
                   lambda d: d.update(tool='lh_job_submit'),
                   lambda d: d['authorization_bounds'].update(principal_id='another-owner'),
                   lambda d: d['authorization_bounds'].update(expires_at=True),
                   lambda d: d['authorization_bounds'].update(expires_at=None),
                   lambda d: d['authorization_bounds'].update(scopes=['lh:read', 'lh:read']),
                   lambda d: d['authorization_bounds'].update(scopes=['admin']),
                   lambda d: d['authorization_bounds'].update(scopes=['lh:read', {}]),
                   lambda d: d.update(authorization_bounds=None)]
        for change in changes:
            candidate = copy.deepcopy(original)
            change(candidate)
            with self.subTest(candidate=candidate), self.assertRaises(JobError) as caught:
                forwarded_bounds.restrict(candidate, self.peer)
            self.assertEqual('UNAUTHORIZED', caught.exception.code)

    def test_expired_bounds_cannot_be_sent_or_received(self):
        sent = forwarded_bounds.attach(self.body, self.network)
        with patch('time.time', return_value=self.cutoff):
            for action in (lambda: forwarded_bounds.attach(self.body, self.network),
                           lambda: forwarded_bounds.restrict(sent, self.peer)):
                with self.assertRaises(JobError) as caught:
                    action()
                self.assertEqual('UNAUTHORIZED', caught.exception.code)

    def test_legacy_local_identity_has_no_new_network_deadline(self):
        sent = forwarded_bounds.attach(self.body, self.peer)
        self.assertIs(sent, self.body)
        self.assertIs(forwarded_bounds.restrict(sent, self.peer)[1], self.peer)


class SocketBoundsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.socket = Path(self.temp.name) / 'control.sock'
        self.received = []
        self.cutoff = int(time.time()) + 300
        class Broker:
            def call(inner, tool, arguments, principal):
                principal.require_current()
                self.received.append(principal)
                if 'lh:read' not in principal.scopes:
                    raise JobError('UNAUTHORIZED', 'Read scope required')
                return {'result': 'owned-task'}
        self.peer = Principal('owner', frozenset({'lh:read', 'lh:submit'}))
        self.server = cli.MaintenanceServer(Broker(), self.socket, {os.geteuid(): self.peer})
        self.server.start()
        self.addCleanup(self.server.close)

    def test_real_socket_forwards_narrow_scope_and_original_expiration(self):
        principal = Principal('owner', frozenset({'lh:read'}), expires_at=self.cutoff)
        self.assertEqual({'result': 'owned-task'}, cli.request(self.socket, 'lh_job_status', {}, principal=principal))
        self.assertEqual(principal.scopes, self.received[0].scopes)
        self.assertEqual(self.cutoff, self.received[0].expires_at)

    def test_real_socket_cannot_replace_token_scope_with_os_peer_scope(self):
        principal = Principal('owner', frozenset({'lh:submit'}), expires_at=self.cutoff)
        with self.assertRaises(JobError) as caught:
            cli.request(self.socket, 'lh_job_status', {}, principal=principal)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        self.assertEqual(principal.scopes, self.received[0].scopes)

    def test_real_socket_cannot_self_identify_as_another_principal(self):
        principal = Principal('other', frozenset({'lh:read'}), expires_at=self.cutoff)
        with self.assertRaises(JobError) as caught:
            cli.request(self.socket, 'lh_job_status', {}, principal=principal)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        self.assertEqual([], self.received)

    def test_original_local_socket_request_remains_supported(self):
        self.assertEqual({'result': 'owned-task'}, cli.request(self.socket, 'lh_job_status', {}))
        self.assertIs(self.peer, self.received[0])


class ResidentBoundsTests(unittest.TestCase):
    setUp = fixtures.ResidentTests.setUp

    def test_prepare_and_controller_calls_keep_network_bounds(self):
        cutoff = int(time.time()) + 300
        network = Principal('owner', frozenset({'lh:submit'}), expires_at=cutoff)
        args = dict(operation_id=self.request['operation_id'], kind='host.inspect', profile_ref='fixture')
        self.broker.call('lh_job_prepare', args, network)
        call = self.service.call.call_args
        body = dict(action=call.args[0], **call.kwargs)
        original, admitted = forwarded_bounds.restrict(body, self.owner)
        self.assertEqual(dict(action='prepare', principal_id='owner', **args), original)
        self.assertEqual(network.scopes, admitted.scopes)
        self.assertEqual(cutoff, admitted.expires_at)
        self.broker._running_request(self.record, self.policy, 'lh_job_submit', self.request, network)
        self.assertIs(network, self.local.call_args.kwargs['principal'])

    def test_expiry_during_service_lookup_prevents_controller_delivery(self):
        cutoff = int(time.time()) + 300
        network = Principal('owner', frozenset({'lh:read'}), expires_at=cutoff)
        with patch('time.time', return_value=cutoff - 1) as clock:
            def route(*args, **kwargs):
                clock.return_value = cutoff
                return {'state': 'RUNNING'}
            self.service.call.side_effect = route
            with self.assertRaises(JobError) as caught:
                self.broker.call('lh_job_status', {'operation_id': self.request['operation_id']}, network)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        self.local.assert_not_called()

    def test_controller_refusal_never_retries_without_bounds(self):
        network = Principal('owner', frozenset({'lh:read'}), expires_at=int(time.time()) + 300)
        self.local.side_effect = JobError('INVALID_REQUEST', 'Legacy controller refuses bounds')
        with self.assertRaises(JobError):
            self.broker._running_request(self.record, self.policy, 'lh_job_status', {}, network)
        self.assertEqual(1, self.local.call_count)
        self.service.call.assert_not_called()
        self.factory.assert_not_called()


class ManagerBoundsTests(unittest.TestCase):
    setUp = fixtures.PreparationTests.setUp

    def network_request(self, scope='lh:submit'):
        self.config['template'] = {'scopes': list(set(TOOL_SCOPES.values()))}
        return forwarded_bounds.attach(self.args, Principal('owner', frozenset({scope}), expires_at=int(time.time()) + 300))

    def test_manager_refuses_wrong_scope_before_creating_attempt(self):
        with patch.object(self.service, '_prepare_worker') as worker:
            with self.assertRaises(JobError) as caught:
                self.service.call(self.network_request('lh:read'))
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        self.assertEqual([], list(Path(self.config['private_root']).iterdir()))
        worker.assert_not_called()

    def test_manager_refuses_expired_request_after_lock_wait(self):
        body = self.network_request()
        with patch('time.time', return_value=body['authorization_bounds']['expires_at']):
            with self.assertRaises(JobError) as caught:
                self.service.call(body)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        self.assertEqual({}, self.service.records)

    def test_manager_rechecks_expiry_after_busy_observation(self):
        body = self.network_request()
        with patch('time.time', return_value=body['authorization_bounds']['expires_at'] - 1) as clock:
            def idle():
                clock.return_value = body['authorization_bounds']['expires_at']
                return False
            with patch.object(self.service, '_busy', side_effect=idle), self.assertRaises(JobError) as caught:
                self.service.call(body)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        self.assertEqual([], list(Path(self.config['private_root']).iterdir()))

    def test_manager_accepts_bounded_preparation_and_cannot_enlarge_installed_grant(self):
        body = self.network_request()
        self.config['template']['scopes'] = ['lh:read']
        with self.assertRaises(JobError):
            self.service.call(body)
        self.config['template']['scopes'] = ['lh:submit']
        with patch.object(self.service, '_prepare_worker') as worker:
            self.assertEqual('PREPARING', self.service.call(body)['state'])
            self.service.worker.join(2)
        worker.assert_called_once()

    def test_start_rechecks_deadline_before_launch(self):
        self.network_request()
        record = fixtures.PreparationTests.ready_record(self)
        self.service._save(record)
        # The network deadline must precede the prepared request's expiry.
        # Separate wall-clock reads can otherwise cross a second and test the
        # stale preparation refusal instead of the delivery authorization gate.
        principal = Principal('owner', frozenset({'lh:submit'}),
                              expires_at=record['request']['expires_at'] - 30)
        body = forwarded_bounds.attach(dict(action='start', principal_id='owner',
            operation_id=record['operation_id'], request_digest=record['request']['request_digest']), principal)
        with patch('time.time', return_value=principal.expires_at - 1) as clock:
            def idle(**kwargs):
                clock.return_value = principal.expires_at
                return False
            with patch.object(self.service, 'execution_state', return_value='IDLE'), \
                 patch.object(self.service, '_busy', side_effect=idle), \
                 patch.object(self.service, '_launcher') as launcher:
                with self.assertRaises(JobError) as caught:
                    self.service.call(body)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        launcher.assert_not_called()

    def test_expiry_inside_fixed_launcher_never_delivers_a_process(self):
        from admin.local_hand_system_manager import prepared_service as prepared
        self.network_request()
        record = fixtures.PreparationTests.ready_record(self)
        self.service._save(record)
        launch_fixtures.FixedLaunchTests.setUp(self)
        self.launcher.launch['request'] = record['request']
        self.launcher.launch['policy']['process_manager']['manager_binding']['boot_id'] = 'boot-one'
        cutoff = int(time.time()) + 100
        principal = Principal('owner', frozenset({'lh:submit'}), expires_at=cutoff)
        body = forwarded_bounds.attach(dict(action='start', principal_id='owner',
            operation_id=record['operation_id'], request_digest=record['request']['request_digest']), principal)
        with patch('time.time', return_value=cutoff - 1) as clock:
            def command(*args):
                clock.return_value = cutoff
                return ['/synthetic/not-started']
            with patch.object(self.service, 'execution_state', return_value='IDLE'), \
                 patch.object(self.service, '_busy', return_value=False), \
                 patch.object(self.service, '_launcher', return_value=self.launcher), \
                 patch.object(prepared, 'controller_command', side_effect=command), \
                 patch.object(prepared.q2_config, 'executable', side_effect=lambda _: os.open('/dev/null', os.O_RDONLY)), \
                 patch.object(prepared.subprocess, 'Popen', side_effect=OSError('must not deliver')) as popen:
                with self.assertRaises(JobError) as caught:
                    self.service.call(body)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        popen.assert_not_called()
        self.assertFalse((self.launcher.output / 'launch-intent.json').exists())
        self.assertEqual('IDLE', self.launcher.state())


class PreparedBoundsTests(unittest.TestCase):
    setUp = prepared_fixtures.PreparedTests.setUp

    def test_prepared_launcher_and_controller_both_keep_original_bounds(self):
        principal = Principal('owner', frozenset({'lh:submit'}), expires_at=int(time.time()) + 300)
        self.launcher.call.side_effect = ['IDLE', 'RUNNING']
        self.router.call('lh_job_submit', self.request, principal)
        self.assertEqual(['status', 'start'], [call.args[0] for call in self.launcher.call.call_args_list])
        for call in self.launcher.call.call_args_list:
            self.assertIs(principal, call.kwargs['principal'])
        self.assertIs(principal, self.local.call_args.kwargs['principal'])

    def test_fixed_launcher_cannot_widen_scope_or_accept_expired_bounds(self):
        from admin.local_hand_system_manager.prepared_service import bounded_request
        launch = {'principal_id': 'owner', 'policy': {'principals': {'owner': {'scopes': ['lh:read','lh:submit']}}},
                  'request': self.request}
        body = {'action': 'start', 'operation_id': self.request['operation_id'], 'request_digest': self.request['request_digest']}
        cutoff = int(time.time()) + 300
        read = forwarded_bounds.attach(body, Principal('owner', frozenset({'lh:read'}), expires_at=cutoff))
        with self.assertRaises(JobError):
            bounded_request(read, launch)
        submit = forwarded_bounds.attach(body, Principal('owner', frozenset({'lh:submit'}), expires_at=cutoff))
        received, authorization = bounded_request(submit, launch)
        self.assertEqual(body, received)
        self.assertEqual(frozenset({'lh:submit'}), authorization.scopes)
        self.assertEqual(cutoff, authorization.expires_at)
        with patch('time.time', return_value=cutoff), self.assertRaises(JobError):
            bounded_request(submit, launch)
