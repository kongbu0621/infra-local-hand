"""Policy-link durability: real temporary links, supervisor and coordinator state."""
import copy
import fcntl
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.model import PLAN_SCHEMA, digest, seal_plan
from admin.local_hand_deploy.runtime import ConcreteEnvironment
from admin.local_hand_deploy.services import SystemdAdapter, _link_state
from admin.local_hand_deploy.store import Store
from admin.local_hand_deploy.supervision import AdapterError, SupervisedRunner
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
        environment = ConcreteEnvironment({'profile': {}}, self.store, None)
        environment._services, environment._runner = self.adapter, self.adapter.runner
        with patch.object(self.adapter, 'observe', return_value={'units': {}, 'jobs': []}):
            return environment.prepare_compensation(op)


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

    def test_replaced_parent_cannot_supply_unlink_sync_or_compensation(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                info = self.links.stat(); self.parent_identity = info.st_dev, info.st_ino
                action = self.action(remove=True)
                with patch('os.fsync', side_effect=self.failing_sync if failed else self.real_sync):
                    result = self.execute(action, 'old-parent-unlink-' + str(failed))
                self.assertEqual(not failed, result['synced'])
                receipt = Path(result['attempt']['binding']['result_directory']) / 'result.json'
                original_receipt = receipt.read_bytes()
                original_parent = self.links.with_name('original-links-' + str(failed))
                self.links.rename(original_parent)
                self.links.mkdir(mode=0o700)
                independent = self.links.stat()
                with patch('os.fsync', side_effect=AssertionError('must not sync replacement parent')):
                    observed = self.adapter.observe_action(action, result['attempt'], lock_fd=self.fd)
                    self.assertEqual('conflict', observed['outcome'])
                    self.assertFalse(observed['postcondition'])
                    with self.assertRaisesRegex(AdapterError, 'CONFLICT'):
                        self.execute(action, None, previous=result['attempt'])
                with self.assertRaisesRegex(AdapterError, 'RESTORE_POLICY_LINK'):
                    self.concrete().prepare_compensation(self.operation(action, result))
                self.assertEqual([], list(self.links.iterdir()))
                self.assertEqual([], list(original_parent.iterdir()))
                self.assertEqual(independent.st_ino, self.links.stat().st_ino)
                self.assertEqual(original_receipt, receipt.read_bytes())

    def test_empty_parent_replacement_before_dispatch_is_not_adopted(self):
        action = self.action()
        original_parent = self.links.with_name('original-empty-links')
        self.links.rename(original_parent)
        self.links.mkdir(mode=0o700)
        with patch('os.symlink', side_effect=AssertionError('must not write replacement parent')), \
                self.assertRaisesRegex(AdapterError, 'CONFLICT'):
            self.execute(action, 'replaced-parent-before-start')
        self.assertEqual([], list(self.links.iterdir()))
        self.assertEqual([], list(original_parent.iterdir()))

    def test_same_link_object_moved_to_replacement_parent_is_not_adopted(self):
        action = self.action()
        result = self.execute(action, 'original-link-parent')
        original = _link_state(self.path)
        original_parent = self.links.with_name('original-linked-directory')
        self.links.rename(original_parent)
        self.links.mkdir(mode=0o700)
        (original_parent / self.path.name).rename(self.path)
        relocated = _link_state(self.path)
        self.assertEqual(original['binding'], relocated['binding'])
        self.assertNotEqual(original['parent'], relocated['parent'])
        with patch('os.fsync', side_effect=AssertionError('must not sync replacement parent')):
            observed = self.adapter.observe_action(action, result['attempt'], lock_fd=self.fd)
            self.assertEqual('conflict', observed['outcome'])
            with self.assertRaisesRegex(AdapterError, 'CONFLICT'):
                self.execute(action, None, previous=result['attempt'])
        with self.assertRaisesRegex(AdapterError, 'RESTORE_POLICY_LINK'):
            self.concrete().prepare_compensation(self.operation(action, result))
        self.assertEqual(relocated, _link_state(self.path))

    def test_parent_changed_between_unlink_and_receipt_is_not_rebound(self):
        action = self.action(remove=True)
        original_parent = self.links.with_name('original-inflight-directory')
        unlink = os.unlink
        events = []
        def replace_parent(name, **kwargs):
            unlink(name, **kwargs)
            self.links.rename(original_parent)
            self.links.mkdir(mode=0o700)
        with patch('os.unlink', side_effect=replace_parent), \
                patch('os.fsync', side_effect=AssertionError('must not sync replacement parent')), \
                self.assertRaisesRegex(AdapterError, 'ENABLE_LINK_CHANGED'):
            self.adapter._perform(action, events.append)
        self.assertEqual([{'kind': 'policy_link_effect', 'link': {
            'kind': 'absent', 'parent': action['before']['parent']}}], events)
        self.assertNotEqual(events[0]['link']['parent'], _link_state(self.path)['parent'])
        self.assertEqual([], list(self.links.iterdir()))
        self.assertEqual([], list(original_parent.iterdir()))

    def replace_independently(self):
        original = _link_state(self.path)
        other = self.links / 'independent'
        os.symlink('/fixture/unit.service', other)
        os.replace(other, self.path)
        current = _link_state(self.path)
        self.assertNotEqual(original['ino'], current['ino'])
        return current

    def replace_reusing_inode(self):
        original = self.path.lstat()
        for _ in range(10000):
            self.path.unlink()
            os.symlink('/fixture/unit.service', self.path)
            current = self.path.lstat()
            if current.st_ino == original.st_ino:
                self.assertNotEqual(original.st_ctime_ns, current.st_ctime_ns)
                return _link_state(self.path)
        self.skipTest('filesystem did not reuse the original inode within the bounded probe')

    def test_reused_inode_is_not_a_success_receipt_or_restoration_identity(self):
        action = self.action()
        result = self.execute(action, 'reuse-original')
        independent = self.replace_reusing_inode()
        observed = self.adapter.observe_action(action, result['attempt'], lock_fd=self.fd)
        self.assertEqual('conflict', observed['outcome'])
        self.assertFalse(observed['postcondition'])
        with self.assertRaisesRegex(AdapterError, 'RESTORE_POLICY_LINK'):
            self.concrete().prepare_compensation(self.operation(action, result))
        self.assertEqual(independent, _link_state(self.path))

    def test_remove_precondition_does_not_accept_a_reused_inode(self):
        action = self.action(remove=True)
        independent = self.replace_reusing_inode()
        with self.assertRaisesRegex(AdapterError, 'CONFLICT'):
            self.execute(action, 'remove-reused-precondition')
        self.assertEqual(independent, _link_state(self.path))

    def test_weak_historical_receipt_cannot_supply_current_object_identity(self):
        action = self.action()
        result = self.execute(action, 'weak-receipt')
        receipt_path = Path(result['attempt']['binding']['result_directory']) / 'result.json'
        original_receipt = receipt_path.read_bytes()
        real_observe = self.adapter.runner.observe
        def old_receipt(binding, **kwargs):
            value = copy.deepcopy(real_observe(binding, **kwargs))
            value['events'] = []
            value['result']['value']['link'].pop('binding', None)
            return value
        with patch.object(self.adapter.runner, 'observe', side_effect=old_receipt):
            observed = self.adapter.observe_action(action, result['attempt'], lock_fd=self.fd)
            self.assertTrue(observed['closed'])
            self.assertEqual('conflict', observed['outcome'])
            self.assertFalse(observed['postcondition'])
            self.assertTrue(observed['effective'], 'a weak object identity does not erase the original effect')
            with self.assertRaisesRegex(AdapterError, 'CONFLICT'):
                self.execute(action, None, previous=result['attempt'])
            with self.assertRaisesRegex(AdapterError, 'RESTORE_POLICY_LINK'):
                self.concrete().prepare_compensation(self.operation(action, result))
        # A newly authorized correction binds today's exact object and can
        # proceed without upgrading or rewriting the old weak receipt.
        correction = {**action, 'before': _link_state(self.path), 'after': {'kind': 'absent'}}
        self.assertTrue(self.execute(correction, 'explicit-correction')['postcondition'])
        self.assertEqual(original_receipt, receipt_path.read_bytes())

    def test_historical_removal_without_original_parent_cannot_claim_absence(self):
        action = self.action(remove=True)
        action['before'].pop('binding')
        action['before'].pop('parent')
        def old_remove(action, emit):
            os.unlink(action['path'])
            directory = os.open(self.links, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return {'link': {'kind': 'absent'}}
        result = self.adapter.runner.run(action, old_remove, attempt_id='historical-remove',
            lock_fd=self.fd, persist_intent=lambda _: None)
        original_receipt = (Path(result['binding']['result_directory']) / 'result.json').read_bytes()
        with patch('os.fsync', side_effect=AssertionError('old parent is unproven')):
            observed = self.adapter.observe_action(action, result, lock_fd=self.fd)
            self.assertTrue(observed['closed'])
            self.assertTrue(observed['effective'])
            self.assertEqual('conflict', observed['outcome'])
            self.assertFalse(observed['synced'])
            with self.assertRaisesRegex(AdapterError, 'CONFLICT'):
                self.execute(action, None, previous=result)
        self.assertEqual(original_receipt, (Path(result['binding']['result_directory']) / 'result.json').read_bytes())

    def test_recorded_effect_with_wrong_after_value_is_not_replayed_as_original(self):
        action = self.action()
        symlink = os.symlink
        def independently_remove(target, path, **kwargs):
            symlink(target, path, **kwargs)
            os.unlink(path, dir_fd=kwargs.get('dir_fd'))
        with patch('os.symlink', side_effect=independently_remove):
            result = self.execute(action, 'after-value-conflict')
        self.assertEqual(action['before'], _link_state(self.path))
        self.assertEqual('conflict', result['outcome'])
        self.assertTrue(result['effective'])
        self.assertFalse(result['postcondition'])
        with patch('os.symlink', side_effect=AssertionError('must not replay inconsistent effect')), \
                self.assertRaisesRegex(AdapterError, 'CONFLICT'):
            self.execute(action, 'retry-inconsistent-effect', previous=result['attempt'])

    def test_another_action_cannot_reuse_a_successful_link_receipt(self):
        action = self.action()
        result = self.execute(action, 'bound-original')
        different = {**action, 'before': _link_state(self.path)}
        with self.assertRaisesRegex(AdapterError, 'ATTEMPT_BINDING_CONFLICT'):
            self.adapter.observe_action(different, result['attempt'], lock_fd=self.fd)

    def test_same_target_replacement_is_not_adopted_after_success_or_sync_failure(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                self.path.unlink(missing_ok=True)
                action = self.action()
                with patch('os.fsync', side_effect=self.failing_sync if failed else self.real_sync):
                    result = self.execute(action, 'drift-' + str(failed))
                independent = self.replace_independently()
                with patch('os.fsync', side_effect=AssertionError('must not sync independent object')):
                    observed = self.adapter.observe_action(action, result['attempt'], lock_fd=self.fd)
                    self.assertEqual('conflict', observed['outcome'])
                    self.assertFalse(observed['postcondition'])
                    with self.assertRaisesRegex(AdapterError, 'CONFLICT'):
                        self.execute(action, None, previous=result['attempt'])
                self.assertEqual(independent, _link_state(self.path))
                self.path.unlink()

    def test_lost_effect_event_without_success_receipt_does_not_claim_visible_link(self):
        action = self.action()
        perform = self.adapter._perform
        def lose_event(action, emit):
            return perform(action, lambda event: None if event['kind'] == 'policy_link_effect' else emit(event))
        with patch.object(self.adapter, '_perform', side_effect=lose_event), \
                patch('os.fsync', side_effect=self.failing_sync):
            result = self.execute(action, 'lost-effect')
        self.assertEqual('unknown', result['outcome'])
        original = _link_state(self.path)
        with patch('os.fsync', side_effect=AssertionError('missing ownership')), \
                patch('os.symlink', side_effect=AssertionError('must not relink')):
            resumed = self.execute(action, None, previous=result['attempt'])
        self.assertEqual('unknown', resumed['outcome'])
        self.assertFalse(resumed['postcondition'])
        self.assertEqual(original, _link_state(self.path))
        with patch.object(self.adapter, 'observe', return_value={'units': {}, 'jobs': []}), \
                self.assertRaisesRegex(AdapterError, 'RESTORE_POLICY_LINK'):
            self.concrete().prepare_compensation(self.operation(action, result))

    def test_legacy_success_receipt_without_effect_event_still_binds_exact_link(self):
        action = self.action()
        result = self.execute(action, 'legacy-success')
        observe = self.adapter.runner.observe
        def legacy(binding, **kwargs):
            return {**observe(binding, **kwargs), 'events': []}
        with patch.object(self.adapter.runner, 'observe', side_effect=legacy), \
                patch('os.fsync', side_effect=AssertionError('receipt already proves sync')):
            self.assertTrue(self.execute(action, None, previous=result['attempt'])['postcondition'])
            self.replace_independently()
            self.assertEqual('conflict', self.adapter.observe_action(action, result['attempt'], lock_fd=self.fd)['outcome'])

    def operation(self, action, result, *, inherited=None):
        return {'id': 'fixture', 'inherited': inherited or [],
            'plan': {'steps': [{'id': 'policy', 'kind': 'service', 'action': action}]},
            'steps': [{'prepared': action, 'effective': True, 'state': 'INTENT_RECORDED',
                       'attempts': [{'binding': result['attempt']['binding']}]}]}

    def concrete(self, origins=None):
        store = SimpleNamespace(lock_fd=self.fd, get=(origins or {}).__getitem__)
        environment = ConcreteEnvironment({'profile': {}}, store, None)
        environment._services = self.adapter
        environment._runner = self.adapter.runner
        return environment

    def test_production_compensation_rejects_replaced_link_after_success_or_sync_failure(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                self.path.unlink(missing_ok=True)
                action = self.action()
                with patch('os.fsync', side_effect=self.failing_sync if failed else self.real_sync):
                    result = self.execute(action, 'compensate-drift-' + str(failed))
                independent = self.replace_independently()
                environment = self.concrete()
                with patch.object(self.adapter, 'observe', return_value={'units': {}, 'jobs': []}), \
                        self.assertRaisesRegex(AdapterError, 'RESTORE_POLICY_LINK'):
                    environment.prepare_compensation(self.operation(action, result))
                self.assertEqual(independent, _link_state(self.path))
                self.path.unlink()

    def test_production_compensation_carries_exact_owned_link(self):
        action = self.action()
        with patch('os.fsync', side_effect=self.failing_sync):
            result = self.execute(action, 'owned-effect')
        owned = _link_state(self.path)
        with patch.object(self.adapter, 'observe', return_value={'units': {}, 'jobs': []}):
            actions = self.concrete().prepare_compensation(self.operation(action, result))
        self.assertEqual(1, len(actions))
        self.assertEqual(owned, actions[0]['prepared']['before'])
        restored = self.execute(actions[0]['prepared'], 'owned-restoration')
        self.assertTrue(restored['postcondition'])
        self.assertEqual(action['before'], _link_state(self.path))

    def test_inherited_compensation_preserves_latest_identity_and_pending_sync(self):
        original = self.action(remove=True)
        removed = self.execute(original, 'forward-remove')
        restore = {**original, 'before': _link_state(self.path),
                   'after': {'kind': 'link', 'target': '/fixture/unit.service'}}
        with patch('os.fsync', side_effect=self.failing_sync):
            restored = self.execute(restore, 'restore-create')
        owned = _link_state(self.path)
        origin = self.operation(original, removed)
        origin['compensation'] = [{'step': {'id': 'restore', 'kind': 'service', 'action': restore},
            'record': {'effective': False, 'state': 'INTENT_RECORDED', 'restore': restore,
                       'restore_attempts': [{'binding': restored['attempt']['binding']}]}}]
        successor = {'id': 'successor', 'inherited': ['original'], 'plan': {'steps': []}, 'steps': []}
        environment = self.concrete({'original': origin})
        with patch.object(self.adapter, 'observe', return_value={'units': {}, 'jobs': []}):
            actions = environment.prepare_compensation(successor)
            self.assertEqual(1, len(actions), 'inherited pending sync must survive restoration planning')
            self.assertEqual(owned, actions[0]['prepared']['before'])
            with patch('os.symlink', side_effect=AssertionError('must only sync')), \
                    patch('os.unlink', side_effect=AssertionError('must only sync')):
                final = self.execute(actions[0]['prepared'], None)
            self.assertTrue(final['postcondition'])
            independent = self.replace_independently()
            with self.assertRaisesRegex(AdapterError, 'RESTORE_POLICY_LINK'):
                environment.prepare_compensation(successor)
        self.assertEqual(independent, _link_state(self.path))

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

    def test_covered_earlier_link_step_cannot_bypass_later_pending_sync(self):
        remove = self.action(remove=True)
        coordinator, store, environment, plan = self.coordinator(remove)
        create = {**remove, 'before': {'kind': 'absent', 'parent': remove['before']['parent']},
                  'after': {'kind': 'link', 'target': '/fixture/unit.service'}}
        plan.pop('digest')
        plan['steps'].append({'id': 'create', 'kind': 'service', 'action': create})
        plan = seal_plan(plan)
        def fail_after_create(fd):
            return self.failing_sync(fd) if self.path.is_symlink() else self.real_sync(fd)
        with patch('os.fsync', side_effect=fail_after_create):
            interrupted = coordinator.apply(plan)
        self.assertIsNone(interrupted['decision'])
        self.assertEqual('VERIFIED', interrupted['steps'][0]['state'])
        self.assertFalse(interrupted['steps'][1]['observation']['synced'])
        original = _link_state(self.path)
        with patch('os.fsync', side_effect=self.failing_sync), \
                patch('os.symlink', side_effect=AssertionError('must not relink')), \
                patch('os.unlink', side_effect=AssertionError('must not unlink')):
            waiting = coordinator.resume(interrupted['id'])
        self.assertEqual('create', waiting['steps'][0]['covered_by'])
        self.assertIsNone(waiting['decision'])
        self.assertNotEqual('VERIFIED', waiting['steps'][1]['state'])
        with patch('os.symlink', side_effect=AssertionError('must not relink')), \
                patch('os.unlink', side_effect=AssertionError('must not unlink')):
            final = coordinator.resume(interrupted['id'])
        self.assertEqual('COMMITTED', final['decision'])
        self.assertTrue(final['steps'][1]['observation']['synced'])
        self.assertEqual([1, 1], [len(record['attempts']) for record in final['steps']])
        self.assertEqual(original, _link_state(self.path))

    def test_lost_acknowledgment_and_later_drift_do_not_erase_a_recorded_effect(self):
        coordinator, store, environment, plan = self.coordinator(self.action())
        execute = environment.execute
        def lose_return(*args, **kwargs):
            execute(*args, **kwargs)
            self.replace_independently()
            raise OSError('lost return after a recorded effect and independent replacement')
        with patch.object(environment, 'execute', side_effect=lose_return):
            interrupted = coordinator.apply(plan)
        self.assertFalse(interrupted['steps'][0]['effective'])
        independent = _link_state(self.path)
        restored = coordinator.rollback(interrupted['id'])
        self.assertTrue(restored['steps'][0]['effective'])
        self.assertEqual('conflict', restored['steps'][0]['observation']['state'])
        self.assertIsNone(restored['decision'])
        self.assertFalse(restored['released'])
        self.assertEqual('CLOSED', coordinator.gate.snapshot()['state'])
        self.assertEqual(independent, _link_state(self.path))

    def test_compensation_does_not_finish_until_removed_link_is_synced(self):
        coordinator, store, environment, plan = self.coordinator(self.action())
        environment.check_ok = False
        applied = coordinator.apply(plan)
        with patch('os.fsync', side_effect=self.failing_sync):
            interrupted = coordinator.rollback(applied['id'])
        self.assertIsNone(interrupted['decision'])
        self.assertNotEqual('RESTORED', interrupted['compensation'][0]['record']['state'])
        self.assertEqual(plan['steps'][0]['action']['before'], _link_state(self.path))
        environment.check_ok = True
        with patch('os.unlink', side_effect=AssertionError('must not unlink again')):
            final = coordinator.resume(applied['id'])
        self.assertEqual('ROLLED_BACK', final['decision'])
        self.assertTrue(final['released'])
        self.assertTrue(final['compensation'][0]['record']['restore_observation']['synced'])
        self.assertEqual(1, len(final['compensation'][0]['record']['restore_attempts']))


if __name__ == '__main__':
    unittest.main()
