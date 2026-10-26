"""Policy-link durability: real temporary links, supervisor and coordinator state."""
import copy
import fcntl
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.model import PLAN_SCHEMA, digest, seal_plan
from admin.local_hand_deploy.runtime import ConcreteEnvironment
from admin.local_hand_deploy.services import SystemdAdapter, _link_state
from admin.local_hand_deploy.store import Store
from admin.local_hand_deploy.supervision import SupervisedRunner
from local_hand_jobs.maintenance import MaintenanceGate
from test_local_hand_deploy_coordinator import Effects


class PolicyEnvironment(Effects):
    """Use real policy effects; no actual systemd service is selected or called."""
    def __init__(self, adapter, store):
        super().__init__()
        self.adapter, self.store = adapter, store

    def effect_key(self, step):
        return step['action']['path']

    def observe(self, step, prepared, attempt=None):
        previous = None if attempt is None else attempt.get('binding')
        return ConcreteEnvironment._observation(
            self.adapter.observe_action(prepared, previous, lock_fd=self.store.lock_fd), prepared)

    def execute(self, step, prepared, op, attempt_id, persist_intent, previous=None):
        binding = None if previous is None else previous.get('binding')
        return ConcreteEnvironment._observation(self.adapter.execute(
            prepared, attempt_id=attempt_id, lock_fd=self.store.lock_fd,
            persist_intent=persist_intent, previous=binding), prepared)

    def prepare_compensation(self, op):
        result = []
        for step, record in zip(op['plan']['steps'], op['steps']):
            if not record['effective']:
                continue
            action = {**step['action'], 'before': _link_state(step['action']['path']),
                      'after': copy.deepcopy(step['action']['before'])}
            result.append({'step': {**step, 'id': 'restore-policy', 'action': action}, 'prepared': action})
        return result


class PolicySyncTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.links = self.root / 'links'
        self.links.mkdir(mode=0o700)
        self.path = self.links / 'fixture.service'
        self.profile = {'units': {'fixture.service': {'policy_links': {
            str(self.path): {'policy': 'enabled-runtime', 'target': '/fixture/unit.service'}}}}}
        self.adapter = SystemdAdapter(self.profile, SupervisedRunner(self.root / 'calls'))
        self.fd = os.open(self.root / 'lock', os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, self.fd)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.real_sync = os.fsync
        info = self.links.stat()
        self.parent_identity = info.st_dev, info.st_ino

    def action(self, *, remove=False):
        if remove:
            os.symlink('/fixture/unit.service', self.path)
        return {'kind': 'service_policy_link', 'target': 'fixture.service', 'path': str(self.path),
                'before': _link_state(self.path), 'phase': 'files',
                'after': {'kind': 'absent'} if remove else {'kind': 'link', 'target': '/fixture/unit.service'}}

    def failing_sync(self, fd):
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) == self.parent_identity:
            raise OSError('injected policy-directory fsync failure')
        return self.real_sync(fd)

    def execute(self, action, attempt, *, previous=None):
        return self.adapter.execute(action, attempt_id=attempt, lock_fd=self.fd,
                                    persist_intent=lambda _: None, previous=previous)

    def test_successful_link_has_sync_proof_and_same_request_does_not_mutate(self):
        action = self.action()
        result = self.execute(action, 'original')
        self.assertTrue(result['postcondition'])
        self.assertTrue(result.get('synced'))
        original = _link_state(self.path)
        with patch('os.fsync', side_effect=AssertionError('already synchronized')), \
                patch('os.symlink', side_effect=AssertionError('must not relink')):
            again = self.execute(action, 'original', previous=result['attempt'])
        self.assertTrue(again['postcondition'])
        self.assertEqual(original, _link_state(self.path))

    def test_failed_link_sync_is_read_only_observed_then_synced_without_repeating_effect(self):
        self.check_failed_sync(remove=False)

    def test_failed_unlink_sync_is_read_only_observed_then_synced_without_repeating_effect(self):
        self.check_failed_sync(remove=True)

    def check_failed_sync(self, *, remove):
        action = self.action(remove=remove)
        with patch('os.fsync', side_effect=self.failing_sync):
            result = self.execute(action, 'first')
        self.assertEqual('unknown', result['supervision']['result']['status'])
        self.assertEqual('target', result['outcome'])
        self.assertFalse(result['postcondition'])
        self.assertFalse(result.get('synced'))
        original = _link_state(self.path)
        with patch('os.fsync', side_effect=AssertionError('observation must be read only')):
            observed = self.adapter.observe_action(action, result['attempt'], lock_fd=self.fd)
        self.assertFalse(observed['postcondition'])
        with patch('os.fsync', wraps=self.real_sync) as synced, \
                patch('os.symlink', side_effect=AssertionError('must not relink')), \
                patch('os.unlink', side_effect=AssertionError('must not unlink again')):
            resumed = self.execute(action, None, previous=result['attempt'])
        self.assertTrue(resumed['postcondition'])
        self.assertTrue(resumed.get('synced'))
        self.assertEqual(1, synced.call_count)
        self.assertEqual(original, _link_state(self.path))

    def coordinator(self, action):
        store = Store(self.root / 'records', 'test-node')
        store.initialize()
        gate_root = self.root / 'gate'
        gate_root.mkdir(mode=0o700)
        gate = MaintenanceGate(gate_root, 'test-node', owner_uid=os.geteuid())
        gate.initialize(digest('old'), 'bootstrap', bootstrap=True)
        environment = PolicyEnvironment(self.adapter, store)
        plan = seal_plan({'schema': PLAN_SCHEMA, 'request_id': 'policy', 'node_id': 'test-node',
            'source': {'deployment_digest': digest('old')}, 'target': {'deployment_digest': digest('new')},
            'steps': [{'id': 'policy', 'kind': 'service', 'action': action}], 'profile': {}})
        return Coordinator(store, gate, environment), store, environment, plan

    def test_coordinator_requires_durable_sync_intent_before_verifying_existing_link(self):
        coordinator, store, environment, plan = self.coordinator(self.action())
        with patch('os.fsync', side_effect=self.failing_sync):
            interrupted = coordinator.apply(plan)
        self.assertIsNone(interrupted['decision'])
        self.assertNotEqual('VERIFIED', interrupted['steps'][0]['state'])
        self.assertEqual(1, len(interrupted['steps'][0]['attempts']))
        original = _link_state(self.path)
        observed = []
        def verify_intent(fd):
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) == self.parent_identity:
                durable = store.get(interrupted['id'])
                event = store.connection.execute('SELECT kind FROM events ORDER BY sequence DESC LIMIT 1').fetchone()[0]
                self.assertEqual('SYNC_INTENT', event)
                self.assertNotEqual('VERIFIED', durable['steps'][0]['state'])
                observed.append(event)
            return self.real_sync(fd)
        with patch('os.fsync', side_effect=verify_intent), \
                patch('os.symlink', side_effect=AssertionError('must not relink')):
            final = coordinator.resume(interrupted['id'])
        self.assertEqual(['SYNC_INTENT'], observed)
        self.assertEqual('COMMITTED', final['decision'])
        self.assertTrue(final['released'])
        self.assertEqual('VERIFIED', final['steps'][0]['state'])
        self.assertTrue(final['steps'][0]['observation']['synced'])
        self.assertEqual(1, len(final['steps'][0]['attempts']))
        self.assertEqual(original, _link_state(self.path))

    def test_compensation_does_not_finish_until_removed_link_is_synced(self):
        coordinator, store, environment, plan = self.coordinator(self.action())
        environment.check_ok = False
        applied = coordinator.apply(plan)
        with patch('os.fsync', side_effect=self.failing_sync):
            interrupted = coordinator.rollback(applied['id'])
        self.assertIsNone(interrupted['decision'])
        self.assertNotEqual('RESTORED', interrupted['compensation'][0]['record']['state'])
        self.assertEqual({'kind': 'absent'}, _link_state(self.path))
        environment.check_ok = True
        with patch('os.unlink', side_effect=AssertionError('must not unlink again')):
            final = coordinator.resume(applied['id'])
        self.assertEqual('ROLLED_BACK', final['decision'])
        self.assertTrue(final['released'])
        self.assertTrue(final['compensation'][0]['record']['restore_observation']['synced'])
        self.assertEqual(1, len(final['compensation'][0]['record']['restore_attempts']))


if __name__ == '__main__':
    unittest.main()
