"""Committed policy rollback keeps the original link and directory identities."""
import copy
import os
import unittest
from unittest.mock import patch

from admin.local_hand_deploy import services
from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.binding import BINDING_SCHEMA, RELEASE_SCHEMA, repair_plan
from admin.local_hand_deploy.planner import build_plan
from admin.local_hand_deploy.runtime import ConcreteEnvironment, PlanningEnvironment
import test_local_hand_deploy_runtime as runtime_fixtures


class CommittedPolicyRollbackTests(unittest.TestCase):
    def setUp(self):
        self.f = runtime_fixtures.RuntimeTests()
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        f = self.f
        self.links = f.root / 'links'; self.links.mkdir(mode=0o700)
        self.path = self.links / 'fixture.service'
        self.reloads = f.root / 'reloads'
        path, reloads = self.path, self.reloads
        class Bus:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def unit(self, name):
                return {'LoadState': 'loaded', 'ActiveState': 'inactive', 'Type': 'exec',
                    'KillMode': 'control-group', 'Restart': 'no', 'Job': [0, '/'],
                    'UnitFileState': 'enabled-runtime' if path.is_symlink() else 'disabled'}
            def jobs(self): return []
            def unique_name(self): return ':fixture.1'
            def fence_sender(self, sender): return {'closed': True}
            def properties(self, *args): return {}
            def call(self, method):
                if method != 'Reload': raise AssertionError(method)
                with reloads.open('a') as stream: stream.write('reload\n')
        mocked = patch.object(services, 'SystemdBus', side_effect=lambda **kwargs: Bus())
        mocked.start(); self.addCleanup(mocked.stop)
        scope = {'roots': [str(self.links)], 'unit_search_roots': [str(self.links)],
            'generator_program_roots': [], 'generator_inputs': [], 'generator_output_roots': [],
            'loaded_snapshot': services.tree_snapshot([str(self.links)])}
        f.profile['systemd'] = {'units': {'fixture.service': {'component': 'manager',
            'policy_links': {str(path): {'policy': 'enabled-runtime', 'target': '/fixture/unit.service'}}}},
            'reload_scope': scope}
        f.source['services'] = {'fixture.service': {'running': False, 'policy': 'disabled'}}
        f.target['services'] = {'fixture.service': {'running': False, 'policy': 'enabled-runtime'}}
        self.plan = build_plan(f.manifest)
        self.store = f.store()
        self.coordinator = Coordinator(self.store, f.gate, ConcreteEnvironment(self.plan, self.store, f.gate))

    def apply(self, *, partial=False):
        if partial:
            with patch.object(ConcreteEnvironment, 'check_local', return_value={'passed': False}):
                self.applied = self.coordinator.apply(self.plan)
            self.assertIsNone(self.applied['decision'])
            self.assertEqual('LOCAL_CHECK_FAILED', self.applied['waiting']['reason'])
        else:
            self.applied = self.coordinator.apply(self.plan)
            self.assertEqual('COMMITTED', self.applied['decision'], self.applied['waiting'])
            self.assertTrue(self.applied['released'])

    def test_committed_rollback_refuses_same_target_replacement(self):
        self.apply()
        original = services._link_state(self.path)
        independent = self.links / 'replacement'
        os.symlink('/fixture/unit.service', independent)
        os.replace(independent, self.path)
        replacement = services._link_state(self.path)
        self.assertNotEqual(original['binding'], replacement['binding'])
        before = self.store.list(), self.f.gate.snapshot(), self.reloads.read_bytes()
        with self.assertRaisesRegex(Exception, 'policy|Policy'):
            self.coordinator.rollback(self.applied['id'])
        self.assertEqual(before, (self.store.list(), self.f.gate.snapshot(), self.reloads.read_bytes()))
        self.assertEqual(replacement, services._link_state(self.path))

    def test_committed_rollback_refuses_replaced_parent(self):
        self.apply()
        original = self.links.with_name('original-links')
        self.links.rename(original); self.links.mkdir(mode=0o700)
        os.symlink('/fixture/unit.service', self.path)
        before = self.store.list(), self.f.gate.snapshot(), self.reloads.read_bytes()
        with self.assertRaisesRegex(Exception, 'policy|Policy'):
            self.coordinator.rollback(self.applied['id'])
        self.assertEqual(before, (self.store.list(), self.f.gate.snapshot(), self.reloads.read_bytes()))
        self.assertTrue(self.path.is_symlink())
        self.assertTrue((original / self.path.name).is_symlink())

    def test_planner_cannot_rebind_link_after_original_observation(self):
        self.apply()
        plan_services = PlanningEnvironment.plan_services
        def replace_then_plan(environment, *args):
            independent = self.links / 'replacement'
            os.symlink('/fixture/unit.service', independent)
            os.replace(independent, self.path)
            return plan_services(environment, *args)
        before = self.store.list(), self.f.gate.snapshot(), self.reloads.read_bytes()
        with patch.object(PlanningEnvironment, 'plan_services', replace_then_plan):
            with self.assertRaisesRegex(Exception, 'Policy link changed'):
                self.coordinator.rollback(self.applied['id'])
        self.assertEqual(before, (self.store.list(), self.f.gate.snapshot(), self.reloads.read_bytes()))
        self.assertTrue(self.path.is_symlink())

    def test_original_link_rollback_and_successor_reuse(self):
        self.apply()
        restored = self.coordinator.rollback(self.applied['id'])
        self.assertEqual('COMMITTED', restored['decision'], restored['waiting'])
        self.assertTrue(restored['released'])
        self.assertFalse(self.path.is_symlink())
        before = self.store.list(), self.reloads.read_bytes()
        self.assertEqual(restored['id'], self.coordinator.rollback(self.applied['id'])['id'])
        self.assertEqual(before, (self.store.list(), self.reloads.read_bytes()))
        enabled = self.coordinator.rollback(restored['id'])
        self.assertEqual('COMMITTED', enabled['decision'], enabled['waiting'])
        self.assertTrue(self.path.is_symlink())
        disabled = self.coordinator.rollback(enabled['id'])
        self.assertEqual('COMMITTED', disabled['decision'], disabled['waiting'])
        self.assertFalse(self.path.is_symlink())

    def test_committed_absence_cannot_claim_replaced_parent(self):
        self.apply()
        removed = self.coordinator.rollback(self.applied['id'])
        self.assertEqual('COMMITTED', removed['decision'], removed['waiting'])
        self.links.rename(self.links.with_name('original-empty-links'))
        self.links.mkdir(mode=0o700)
        before = self.store.list(), self.f.gate.snapshot(), self.reloads.read_bytes()
        with self.assertRaisesRegex(Exception, 'policy|Policy'):
            self.coordinator.rollback(removed['id'])
        self.assertEqual(before, (self.store.list(), self.f.gate.snapshot(), self.reloads.read_bytes()))
        self.assertEqual([], list(self.links.iterdir()))

    def correct_partial(self):
        f = self.f
        configuration = f.configuration('d' * 64)
        candidate = f.root / 'corrected.json'; f.write(candidate, configuration)
        target = f.deployment('d' * 64, configuration)
        target['services'] = copy.deepcopy(f.target['services'])
        binding = {'schema': BINDING_SCHEMA, 'node_id': 'node', 'state': str(self.store.root), 'profile': f.profile}
        release = {'schema': RELEASE_SCHEMA, 'node_id': 'node', 'request_id': 'correction',
            'target': target, 'files': [{'source': str(candidate), 'target': str(f.config)}]}
        plan = repair_plan(binding, release, self.applied['id'])
        successor = self.coordinator.supersede(self.applied['id'], plan)['successor']
        fixed = self.coordinator.resume(successor)
        self.assertEqual('COMMITTED', fixed['decision'], fixed['waiting'])
        return fixed

    def test_committed_correction_keeps_inherited_link_ownership(self):
        self.apply(partial=True)
        original = services._link_state(self.path)
        fixed = self.correct_partial()
        successor = fixed['id']
        self.assertEqual(original, services._link_state(self.path))
        retained = self.f.root / 'retained-original-link'
        self.path.rename(retained)
        os.symlink('/fixture/unit.service', self.path)
        before = self.store.list(), self.f.gate.snapshot(), self.reloads.read_bytes()
        with self.assertRaisesRegex(Exception, 'policy|Policy'):
            self.coordinator.rollback(successor)
        self.assertEqual(before, (self.store.list(), self.f.gate.snapshot(), self.reloads.read_bytes()))
        self.path.unlink(); retained.rename(self.path)
        restored = self.coordinator.rollback(successor)
        self.assertEqual('COMMITTED', restored['decision'], restored['waiting'])
        self.assertFalse(self.path.is_symlink())

    def test_failed_compensation_before_effect_does_not_hide_original_link(self):
        self.apply(partial=True)
        original = services._link_state(self.path)
        perform = services.SystemdAdapter._perform
        def fail_remove(adapter, action, emit):
            if action['kind'] == 'service_policy_link' and action['after']['kind'] == 'absent':
                raise OSError('local removal failed before effect')
            return perform(adapter, action, emit)
        with patch.object(services.SystemdAdapter, '_perform', fail_remove):
            interrupted = self.coordinator.rollback(self.applied['id'])
        self.assertIsNone(interrupted['decision'])
        self.assertEqual(original, services._link_state(self.path))
        fixed = self.correct_partial()
        self.assertEqual(original, services._link_state(self.path))
        restored = self.coordinator.rollback(fixed['id'])
        self.assertEqual('COMMITTED', restored['decision'], restored['waiting'])
        self.assertFalse(self.path.is_symlink())


if __name__ == '__main__': unittest.main()
