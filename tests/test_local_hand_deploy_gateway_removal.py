"""Container deletion proves original ID absence, independently of its name."""
import copy
import unittest
from urllib.parse import unquote
from unittest.mock import patch

import test_local_hand_deploy_gateway_responses as fixtures
import test_local_hand_deploy_runtime as runtime_fixtures
from test_local_hand_deploy_gateway_start import StartHandler
from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.planner import build_plan
from admin.local_hand_deploy.runtime import ConcreteEnvironment, PlanningEnvironment


class NamedHandler(StartHandler):
    def do_GET(self):
        if '/containers/' in self.path:
            selected = unquote(self.path.split('/containers/', 1)[1].removesuffix('/json'))
            current = self.server.container
            if current is None or selected not in {current['Id'], getattr(self.server, 'current_name', 'response-gateway')}:
                self.reply(404, {'message': 'No such container'})
                return
        super().do_GET()

    def do_POST(self):
        if '/rename?name=' in self.path:
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            self.server.current_name = unquote(self.path.split('/rename?name=', 1)[1])
            self.reply(200, {})
            return
        super().do_POST()

    def do_DELETE(self):
        if self.server.mode.read_text() == 'delete-replace-disconnect':
            with self.server.requests.open('a') as stream:
                stream.write(self.path + '\n')
            self.server.container = copy.deepcopy(self.server.container)
            self.server.container['Id'] = 'independent-after-delete'
            return
        super().do_DELETE()


class GatewayRemovalTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.GatewayResponseTests()
        with patch.object(fixtures, 'Handler', NamedHandler):
            self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.mode.write_text('success')
        self.created = self.f.execute('original-create')
        self.action = self.f.adapter.plan({'present': False, 'running': False})[0]

    def execute(self, previous=None):
        return self.f.adapter.execute(self.action, attempt_id='remove-original', lock_fd=self.f.fd,
            persist_intent=lambda _: None, previous=previous)

    def test_renamed_original_is_not_reported_deleted_or_automatically_removed(self):
        original = self.created['observation']['id']
        self.f.adapter.engine.request('POST', '/containers/' + original + '/rename?name=independent-name', {})
        observed = self.f.adapter.observe_action(self.action, lock_fd=self.f.fd)
        self.assertTrue(observed['closed'])
        self.assertEqual('conflict', observed['outcome'])
        self.assertFalse(observed['postcondition'])
        with self.assertRaisesRegex(Exception, 'CONFLICT'):
            self.execute()
        self.assertEqual(original, self.f.adapter.engine.request('GET', '/containers/' + original + '/json')['Id'])
        self.assertEqual(1, self.f.count())

    def test_actual_original_deletion_completes_without_replaying(self):
        removed = self.execute()
        self.assertTrue(removed['postcondition'])
        self.assertIsNone(self.f.adapter.engine.request('GET', '/containers/' + self.action['before']['id'] + '/json', missing=True))
        requests = self.f.requests.read_bytes()
        self.assertTrue(self.execute(removed['attempt'])['postcondition'])
        self.assertEqual(requests, self.f.requests.read_bytes())

    def test_completed_removal_does_not_adopt_later_name_occupant(self):
        removed = self.execute()
        replacement = self.f.independent_create()['Id']
        observed = self.f.adapter.observe_action(self.action, removed['attempt'], lock_fd=self.f.fd)
        self.assertTrue(observed['closed'])
        self.assertEqual('conflict', observed['outcome'])
        self.assertFalse(observed['postcondition'])
        self.assertTrue(observed['effective'])
        requests = self.f.requests.read_bytes()
        with self.assertRaisesRegex(Exception, 'CONFLICT'):
            self.execute(removed['attempt'])
        self.assertEqual(requests, self.f.requests.read_bytes())
        self.assertEqual(replacement, self.f.adapter.observe(require_route=False)['id'])

    def test_unknown_delete_response_can_close_original_without_adopting_replacement(self):
        self.f.mode.write_text('delete-replace-disconnect')
        removed = self.execute()
        self.assertTrue(removed['closed'])
        self.assertEqual('conflict', removed['outcome'])
        self.assertFalse(removed['postcondition'])
        self.assertTrue(removed['effective'])
        self.assertEqual('unknown', removed['supervision']['result']['status'])
        self.assertEqual('independent-after-delete', self.f.adapter.observe(require_route=False)['id'])


class CommittedGatewayRollbackTests(unittest.TestCase):
    """Full production planner/coordinator, with temporary config and Engine."""
    def setUp(self):
        self.f = runtime_fixtures.RuntimeTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.http = fixtures.GatewayResponseTests()
        with patch.object(fixtures, 'Handler', NamedHandler):
            self.http.setUp()
        self.addCleanup(self.http.doCleanups)
        f, http = self.f, self.http
        http.mode.write_text('success')
        f.profile['gateway'] = {**copy.deepcopy(http.adapter.profile), 'socket': str(http.root / 'engine.sock'),
                                'component': 'manager'}
        f.source['gateway'] = {'present': False, 'running': False,
            'config_digest': f.source['selection']['components']['manager']['configuration_digest'],
            'deployment_digest': f.a}
        f.target['gateway'] = {'present': True, 'running': False,
            'config_digest': f.target['selection']['components']['manager']['configuration_digest'],
            'deployment_digest': f.b}
        self.plan = build_plan(f.manifest)
        self.store = f.store()
        self.coordinator = Coordinator(self.store, f.gate, ConcreteEnvironment(self.plan, self.store, f.gate))
        self.applied = self.coordinator.apply(self.plan)
        self.assertEqual('COMMITTED', self.applied['decision'], self.applied['waiting'])
        creation = next(record for step, record in zip(self.plan['steps'], self.applied['steps'])
                        if step['action'].get('kind') == 'gateway_create')
        self.identity = creation['attempts'][0]['effect_identity']

    def assert_refused_without_effects(self):
        gate = self.f.gate.snapshot()
        records = self.store.list()
        requests = self.http.requests.read_bytes()
        with self.assertRaisesRegex(Exception, 'gateway|Gateway'):
            self.coordinator.rollback(self.applied['id'])
        self.assertEqual(gate, self.f.gate.snapshot())
        self.assertEqual(records, self.store.list())
        self.assertEqual(requests, self.http.requests.read_bytes())
        self.assertIsNone(self.store.get(self.applied['id'])['rollback_successor'])

    def test_committed_rollback_rejects_replacement_before_link_or_gate_close(self):
        replacement = self.http.adapter.engine.request('POST', '/containers/create?name=' + self.http.adapter.name,
            self.http.adapter._create_body(self.f.target['gateway'], self.identity['attempt_id']))['Id']
        self.assertNotEqual(self.identity['container_id'], replacement)
        self.assert_refused_without_effects()
        self.assertEqual(replacement, self.http.adapter.observe(require_route=False)['id'])

    def test_committed_rollback_preserves_renamed_original(self):
        self.http.adapter.engine.request('POST', '/containers/' + self.identity['container_id'] + '/rename?name=elsewhere', {})
        self.assert_refused_without_effects()
        self.assertEqual(self.identity['container_id'], self.http.adapter.engine.request(
            'GET', '/containers/' + self.identity['container_id'] + '/json')['Id'])

    def test_rollback_planner_cannot_replace_its_verified_original_with_a_later_probe(self):
        gate, records = self.f.gate.snapshot(), self.store.list()
        planner = PlanningEnvironment.plan_gateway
        def replace_then_plan(environment, source, target):
            self.http.adapter.engine.request('POST', '/containers/create?name=' + self.http.adapter.name,
                self.http.adapter._create_body(self.f.target['gateway'], self.identity['attempt_id']))
            return planner(environment, source, target)
        with patch.object(PlanningEnvironment, 'plan_gateway', replace_then_plan):
            with self.assertRaisesRegex(Exception, 'Gateway changed while constructing rollback'):
                self.coordinator.rollback(self.applied['id'])
        self.assertEqual(gate, self.f.gate.snapshot())
        self.assertEqual(records, self.store.list())
        self.assertFalse(any('force=false' in path for path in self.http.requests.read_text().splitlines()))
        self.assertNotEqual(self.identity['container_id'], self.http.adapter.observe(require_route=False)['id'])

    def test_committed_rollback_removes_exact_original_and_reuses_successor(self):
        restored = self.coordinator.rollback(self.applied['id'])
        self.assertEqual('COMMITTED', restored['decision'], restored['waiting'])
        self.assertTrue(restored['released'])
        removal = next(step for step in restored['plan']['steps'] if step['action'].get('kind') == 'gateway_remove')
        self.assertEqual(self.identity['container_id'], removal['action']['before']['id'])
        requests = self.http.requests.read_bytes()
        self.assertEqual(restored['id'], self.coordinator.rollback(self.applied['id'])['id'])
        self.assertEqual(requests, self.http.requests.read_bytes())

    def test_committed_rollback_can_finish_after_original_was_truly_deleted(self):
        self.http.adapter.engine.request('DELETE', '/containers/' + self.identity['container_id'] + '?force=false&v=false')
        requests = self.http.requests.read_bytes()
        restored = self.coordinator.rollback(self.applied['id'])
        self.assertEqual('COMMITTED', restored['decision'], restored['waiting'])
        self.assertTrue(restored['released'])
        self.assertEqual(requests, self.http.requests.read_bytes())
        self.assertFalse(any(step['kind'] == 'gateway' for step in restored['plan']['steps']))
