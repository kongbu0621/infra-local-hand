"""Create/start ownership through real HTTP, supervisor and coordinator records."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.model import PLAN_SCHEMA, digest, seal_plan
from admin.local_hand_deploy.runtime import ConcreteEnvironment
from admin.local_hand_deploy.store import Store
from admin.local_hand_deploy.supervision import boot_id
from local_hand_jobs.maintenance import MaintenanceGate
from test_local_hand_deploy_coordinator import Effects
import test_local_hand_deploy_gateway_responses as fixtures


class StartHandler(fixtures.Handler):
    def do_POST(self):
        if self.path.endswith('/start') or '/stop?' in self.path:
            with self.server.requests.open('a') as stream:
                stream.write(self.path + '\n')
            self.server.container['State']['Running'] = self.path.endswith('/start')
            if self.server.mode.read_text() == 'start_disconnect':
                return
            self.reply(200, {})
        else:
            super().do_POST()

    def do_DELETE(self):
        with self.server.requests.open('a') as stream:
            stream.write(self.path + '\n')
        self.server.container = None
        self.reply(200, {})


class GatewayStartTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.GatewayResponseTests()
        with patch.object(fixtures, 'Handler', StartHandler):
            self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        f = self.f
        f.mode.write_text('success')
        f.adapter.guard_check = lambda _, target: {**target, 'descriptor_digest': 'd' * 64,
            'mode': 'candidate', 'target_running': True, 'boot': boot_id()}
        f.adapter.route_probe = lambda identity: {'container_id': identity,
            'config_digest': 'b' * 64, 'protocol_ready': True}
        actions = f.adapter.plan({'running': True, 'config_digest': 'b' * 64, 'deployment_digest': 'c' * 64})
        self.plan = seal_plan({'schema': PLAN_SCHEMA, 'request_id': 'start', 'node_id': 'node',
            'source': {'deployment_digest': digest('old')}, 'target': {'deployment_digest': 'c' * 64},
            'profile': {}, 'steps': [{'id': action['kind'], 'kind': 'gateway', 'action': action} for action in actions]})
        self.store = Store(f.root / 'start-records', 'node'); self.store.initialize()
        directory = f.root / 'start-gate'; directory.mkdir(mode=0o700)
        self.gate = MaintenanceGate(directory, 'node', owner_uid=fixtures.os.geteuid())
        self.gate.initialize(digest('old'), 'bootstrap', bootstrap=True)
        concrete = ConcreteEnvironment(self.plan, self.store, self.gate)
        concrete._gateway, concrete._runner = f.adapter, f.runner
        class Environment(Effects):
            after_create = None
            def effect_key(self, step): return concrete.effect_key(step)
            def prepare(self, *args, **kwargs): return concrete.prepare(*args, **kwargs)
            def observe(self, *args, **kwargs): return concrete.observe(*args, **kwargs)
            def execute(self, step, *args, **kwargs):
                result = concrete.execute(step, *args, **kwargs)
                if step['action']['kind'] == 'gateway_create' and self.after_create:
                    self.after_create(result)
                return result
            def prepare_compensation(self, op): return concrete.prepare_compensation(op)
            def effect_identity(self, *args, **kwargs): return concrete.effect_identity(*args, **kwargs)
        self.environment = Environment()
        self.coordinator = Coordinator(self.store, self.gate, self.environment)
        self.concrete = concrete

    def replace_after_create(self, *, running=False):
        def replace(result):
            original = result['observation']['id']
            labels = result['observation']['labels']
            desired = {'config_digest': labels['local-hand.deploy.config'],
                       'deployment_digest': labels['local-hand.deploy.deployment']}
            self.f.mode.write_text('success')
            replacement = self.f.adapter.engine.request('POST', '/containers/create?name=' + self.f.adapter.name,
                self.f.adapter._create_body(desired, result['attempt']['binding']['attempt_id']))['Id']
            self.assertNotEqual(original, replacement)
            if running:
                self.f.adapter.engine.request('POST', '/containers/' + replacement + '/start')
        self.environment.after_create = replace

    def test_new_start_does_not_dispatch_to_independent_created_replacement(self):
        self.replace_after_create()
        op = self.coordinator.apply(self.plan)
        self.assertIsNone(op['decision'])
        self.assertFalse(self.f.adapter.observe(require_route=False)['status'] == 'running')
        self.assertFalse(any(path.endswith('/start') for path in self.f.requests.read_text().splitlines()))

    def test_running_replacement_cannot_cover_its_original_create_step(self):
        self.replace_after_create(running=True)
        op = self.coordinator.apply(self.plan)
        self.assertIsNone(op['decision'])
        op = self.coordinator.resume(op['id'])
        self.assertIsNone(op['decision'])
        self.assertNotIn('covered_by', op['steps'][0])

    def test_http_error_creation_keeps_its_first_confirmed_identity(self):
        self.f.mode.write_text('effect_then_error')
        self.replace_after_create()
        op = self.coordinator.apply(self.plan)
        self.assertIsNone(op['decision'])
        first = copy.deepcopy(op['steps'][0]['attempts'][0].get('effect_identity'))
        self.assertIsNotNone(first)
        op = self.coordinator.resume(op['id'])
        self.assertIsNone(op['decision'])
        self.assertEqual(first, op['steps'][0]['attempts'][0]['effect_identity'])
        with self.store.locked(), self.assertRaisesRegex(Exception, 'RESTORE_GATEWAY_IDENTITY'):
            self.concrete.prepare_compensation(op)

    def test_original_creation_can_start_and_resume_without_replaying(self):
        op = self.coordinator.apply(self.plan)
        self.assertEqual('COMMITTED', op['decision'])
        requests = self.f.requests.read_bytes()
        self.coordinator.resume(op['id'])
        self.assertEqual(requests, self.f.requests.read_bytes())

    def test_old_target_snapshot_is_pinned_before_refresh_even_before_verified(self):
        self.f.mode.write_text('effect_then_error')
        self.environment.check_ok = False
        op = self.coordinator.apply(self.plan)
        identity = op['steps'][0]['attempts'][0].pop('effect_identity')
        op['steps'][0]['state'] = 'INTENT_RECORDED'
        with self.store.locked():
            self.store.save(op, 'LEGACY_TARGET_FIXTURE')
        self.f.independent_create(identity['attempt_id'])
        op = self.coordinator.resume(op['id'])
        self.assertEqual(identity, op['steps'][0]['attempts'][0]['effect_identity'])
        self.assertEqual('conflict', op['steps'][0]['observation']['state'])
        self.assertIsNone(op['decision'])

    def test_legacy_engine_returned_identity_recovers_without_saved_snapshot(self):
        self.environment.check_ok = False
        op = self.coordinator.apply(self.plan)
        identity = op['steps'][0]['attempts'][0].pop('effect_identity')
        op['steps'][0]['observation'] = None
        with self.store.locked():
            self.store.save(op, 'LEGACY_RECEIPT_FIXTURE')
        self.f.independent_create(identity['attempt_id'])
        op = self.coordinator.resume(op['id'])
        self.assertEqual(identity, op['steps'][0]['attempts'][0]['effect_identity'])
        self.assertIsNone(op['decision'])

    def test_weak_legacy_creation_does_not_reconstruct_identity_from_live_inspect(self):
        self.f.mode.write_text('effect_then_error')
        self.environment.check_ok = False
        op = self.coordinator.apply(self.plan)
        identity = op['steps'][0]['attempts'][0].pop('effect_identity')
        op['steps'][0]['observation'] = None
        with self.store.locked():
            self.store.save(op, 'MISSING_IDENTITY_FIXTURE')
        self.f.independent_create(identity['attempt_id'])
        op = self.coordinator.resume(op['id'])
        self.assertIsNone(op['decision'])
        self.assertNotIn('effect_identity', op['steps'][0]['attempts'][0])
        self.assertEqual('unknown', op['steps'][0]['observation']['state'])

    def test_inherited_legacy_forward_and_compensation_keep_saved_creation_identity(self):
        self.f.mode.write_text('effect_then_error')
        result = self.f.execute('legacy-adopted')
        saved = copy.deepcopy(ConcreteEnvironment._observation(result, self.f.action))
        saved.pop('effect_identity', None)
        saved['attempt'].pop('effect_identity', None)
        binding = result['attempt']['binding']
        step = {'id': 'create', 'kind': 'gateway', 'action': self.f.action}
        self.f.independent_create('legacy-adopted')
        for restore in (False, True):
            with self.subTest(restore=restore):
                origin = ({'id': 'old', 'plan': {'steps': []}, 'steps': [], 'compensation': [
                    {'step': step, 'record': {'restore': self.f.action, 'effective': False, 'state': 'RESTORED',
                        'restore_attempts': [{'binding': binding}], 'restore_observation': saved}}]} if restore else
                    {'id': 'old', 'plan': {'steps': [step]}, 'steps': [{'prepared': self.f.action,
                        'effective': True, 'state': 'VERIFIED', 'attempts': [{'binding': binding}], 'observation': saved}]})
                original = copy.deepcopy(origin)
                concrete = ConcreteEnvironment({'profile': {}}, SimpleNamespace(lock_fd=self.f.fd, get=lambda _: origin), None)
                concrete._gateway, concrete._runner = self.f.adapter, self.f.runner
                with self.assertRaisesRegex(Exception, 'RESTORE_GATEWAY_IDENTITY'):
                    concrete.prepare_compensation({'id': 'new', 'inherited': ['old'], 'plan': {'steps': []}, 'steps': []})
                self.assertEqual(original, origin)

    def test_unavailable_route_does_not_prevent_exact_closed_container_rollback(self):
        self.environment.check_ok = False
        op = self.coordinator.apply(self.plan)
        self.assertIsNone(op['decision'])
        self.environment.check_ok = True
        with patch.object(self.f.adapter, 'route_probe', side_effect=OSError('route unavailable')):
            final = self.coordinator.rollback(op['id'])
        self.assertEqual('ROLLED_BACK', final['decision'], final['waiting'])
        self.assertEqual({'error_type': 'OSError', 'error': 'route unavailable'},
                         final['steps'][1]['observation']['observation']['route_error'])
        self.assertEqual('absent', self.f.adapter.observe(require_route=False)['kind'])

    def test_unavailable_route_does_not_close_unknown_engine_start(self):
        self.environment.after_create = lambda _: self.f.mode.write_text('start_disconnect')
        with patch.object(self.f.adapter, 'route_probe', side_effect=OSError('route unavailable')):
            op = self.coordinator.apply(self.plan)
            self.assertFalse(op['steps'][1]['observation']['closed'])
            self.assertEqual({'error_type': 'OSError', 'error': 'route unavailable'},
                             op['steps'][1]['observation']['observation']['route_error'])
            before = self.f.requests.read_bytes()
            op = self.coordinator.rollback(op['id'])
        self.assertIsNone(op['decision'])
        self.assertEqual(before, self.f.requests.read_bytes())

    def running_replacement_plan(self):
        self.f.independent_create()
        original = self.f.adapter.observe(require_route=False)
        self.f.adapter.engine.request('POST', '/containers/' + original['id'] + '/start')
        actions = self.f.adapter.plan({'running': True, 'config_digest': 'b' * 64, 'deployment_digest': 'f' * 64})
        plan = {key: value for key, value in self.plan.items() if key != 'digest'}
        plan['target'] = {'deployment_digest': 'f' * 64}
        plan['steps'] = [{'id': action['kind'], 'kind': 'gateway', 'action': action} for action in actions]
        self.plan = self.concrete.plan = seal_plan(plan)
        return original['id']

    def test_compensation_creation_starts_exact_original_configuration_and_finishes(self):
        original_id = self.running_replacement_plan()
        self.environment.check_ok = False
        op = self.coordinator.apply(self.plan)
        candidate_id = self.f.adapter.observe(require_route=False)['id']
        self.assertIsNone(op['decision'])
        self.environment.check_ok = True
        restored = self.coordinator.rollback(op['id'])
        self.assertEqual('ROLLED_BACK', restored['decision'], restored['waiting'])
        self.assertTrue(restored['released'])
        actual = self.f.adapter.observe()
        self.assertNotIn(actual['id'], {original_id, candidate_id})
        self.assertEqual('running', actual['status'])
        self.assertEqual('c' * 64, actual['labels']['local-hand.deploy.deployment'])
        create = next(item for item in restored['compensation'] if item['step']['action']['kind'] == 'gateway_create')
        self.assertEqual(actual['id'], create['record']['restore_attempts'][0]['effect_identity']['container_id'])
        requests = self.f.requests.read_bytes()
        self.coordinator.resume(op['id'])
        self.assertEqual(requests, self.f.requests.read_bytes())

    def test_compensation_start_references_final_creation_step_and_rejects_replacement(self):
        self.running_replacement_plan()
        self.environment.check_ok = False
        op = self.coordinator.apply(self.plan)
        self.assertIsNone(op['decision'])
        self.replace_after_create()
        before_starts = sum(path.endswith('/start') for path in self.f.requests.read_text().splitlines())
        restored = self.coordinator.rollback(op['id'])
        self.assertIsNone(restored['decision'])
        creates = [item for item in restored['compensation'] if item['step']['action']['kind'] == 'gateway_create']
        starts = [item for item in restored['compensation'] if item['step']['action']['kind'] == 'gateway_start']
        self.assertEqual(creates[0]['step']['id'], starts[0]['record']['restore']['creation_ref']['step_id'])
        self.assertTrue(starts[0]['record']['restore']['creation_ref']['restore'])
        self.assertEqual(before_starts, sum(path.endswith('/start') for path in self.f.requests.read_text().splitlines()))


if __name__ == '__main__':
    unittest.main()
