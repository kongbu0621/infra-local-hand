"""Container deletion proves original ID absence, independently of its name."""
import copy
from contextlib import nullcontext
from pathlib import Path
import unittest
from urllib.parse import unquote
from unittest.mock import patch

import test_local_hand_deploy_gateway_responses as fixtures
import test_local_hand_deploy_runtime as runtime_fixtures
from test_local_hand_deploy_gateway_start import StartHandler
from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.binding import BINDING_SCHEMA, RELEASE_SCHEMA, repair_plan
from admin.local_hand_deploy.planner import build_plan
from admin.local_hand_deploy.runtime import ConcreteEnvironment, PlanningEnvironment
from admin.local_hand_deploy.gateway import GatewayAdapter


class NamedHandler(StartHandler):
    def do_GET(self):
        if '/containers/' in self.path and '/containers/json?' not in self.path:
            selected = unquote(self.path.split('/containers/', 1)[1].removesuffix('/json'))
            retained = getattr(self.server, 'retained', {})
            if selected in retained:
                self.reply(200, retained[selected])
                return
            current = self.server.container
            if current is None or selected not in {current['Id'], getattr(self.server, 'current_name', 'response-gateway')}:
                self.reply(404, {'message': 'No such container'})
                return
        super().do_GET()

    def do_POST(self):
        if '/rename?name=' in self.path:
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            self.server.retained = {**getattr(self.server, 'retained', {}),
                                    self.server.container['Id']: copy.deepcopy(self.server.container)}
            self.server.current_name = unquote(self.path.split('/rename?name=', 1)[1])
            self.reply(200, {})
            return
        old = self.server.container and self.server.container['Id']
        old_name = getattr(self.server, 'current_name', 'response-gateway')
        super().do_POST()
        if ('/create?name=' in self.path and self.server.container and self.server.container['Id'] != old
                and getattr(self.server, 'current_name', 'response-gateway') == old_name):
            self.server.current_name = unquote(self.path.split('/create?name=', 1)[1])

    def do_DELETE(self):
        identifier = unquote(self.path.split('/containers/', 1)[1].split('?', 1)[0])
        if identifier in getattr(self.server, 'retained', {}):
            self.server.retained.pop(identifier)
            if self.server.container and self.server.container['Id'] == identifier:
                self.server.container = None
            with self.server.requests.open('a') as stream:
                stream.write(self.path + '\n')
            self.reply(200, {})
            return
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


class _GatewayRollbackFixture(unittest.TestCase):
    """Full production planner/coordinator, with temporary config and Engine."""
    pause_before_commit = False
    handler = NamedHandler
    mode = 'success'
    def setUp(self):
        self.f = runtime_fixtures.RuntimeTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.http = fixtures.GatewayResponseTests()
        with patch.object(fixtures, 'Handler', self.handler):
            self.http.setUp()
        self.addCleanup(self.http.doCleanups)
        f, http = self.f, self.http
        http.mode.write_text(self.mode)
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
        with (patch.object(ConcreteEnvironment, 'check_local', return_value={'passed': False})
              if self.pause_before_commit else nullcontext()):
            self.applied = self.coordinator.apply(self.plan)
        self.assertEqual(None if self.pause_before_commit else 'COMMITTED',
                         self.applied['decision'], self.applied['waiting'])
        creation = next(record for step, record in zip(self.plan['steps'], self.applied['steps'])
                        if step['action'].get('kind') == 'gateway_create')
        self.identity = creation['attempts'][0].get('effect_identity')


class CommittedGatewayRollbackTests(_GatewayRollbackFixture):
    def assert_refused_without_effects(self):
        gate = self.f.gate.snapshot()
        records = self.store.list()
        requests = self.http.requests.read_bytes()
        with self.assertRaisesRegex(Exception, 'gateway|Gateway|GATEWAY'):
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


class PendingGatewayRollbackTests(_GatewayRollbackFixture):
    pause_before_commit = True

    def test_forward_resume_does_not_recreate_while_fixed_original_id_is_renamed(self):
        identifier = self.identity['container_id']
        self.http.adapter.engine.request('POST', '/containers/' + identifier + '/rename?name=renamed-owned', {})
        requests = self.http.requests.read_bytes()
        final = self.coordinator.resume(self.applied['id'])
        self.assertIsNone(final['decision'])
        self.assertEqual(requests, self.http.requests.read_bytes())
        self.assertEqual(identifier, self.http.adapter.engine.request('GET', '/containers/' + identifier + '/json')['Id'])

    def test_forward_resume_recreates_only_after_fixed_original_id_is_truly_absent(self):
        identifier = self.identity['container_id']
        self.http.adapter.engine.request('DELETE', '/containers/' + identifier + '?force=false&v=false')
        final = self.coordinator.resume(self.applied['id'])
        self.assertEqual('COMMITTED', final['decision'], final['waiting'])
        self.assertTrue(final['released'])
        self.assertNotEqual(identifier, self.http.adapter.observe(require_route=False)['id'])

    def test_historical_multiple_creations_keep_earlier_id_before_committed_rollback(self):
        identifier = self.identity['container_id']
        self.http.adapter.engine.request('POST', '/containers/' + identifier + '/rename?name=renamed-owned', {})
        observe = GatewayAdapter.observe_action
        def legacy_observe(adapter, action, *args, **kwargs):
            value = observe(adapter, action, *args, **kwargs)
            if (action['kind'] == 'gateway_create' and value.get('effect_identity')
                    and value.get('observation', {}).get('kind') == 'absent'):
                value['outcome'] = 'original'
            return value
        # Model the historical implementation that recreated after a rename.
        # Both original Engine receipts are produced by the real HTTP runner.
        with patch.object(GatewayAdapter, 'observe_action', legacy_observe), \
                patch.object(ConcreteEnvironment, 'check_local', return_value={'passed': True}):
            committed = self.coordinator.resume(self.applied['id'])
        self.assertEqual('COMMITTED', committed['decision'])
        creation = next(record for step, record in zip(committed['plan']['steps'], committed['steps'])
                        if step['action'].get('kind') == 'gateway_create')
        self.assertEqual(2, len(creation['attempts']))
        creation['attempts'][0].pop('effect_identity')  # Earlier receipt alone must still retain its own ID.
        with self.store.locked():
            self.store.save(committed, 'LEGACY_CREATION_RECEIPTS')
            environment = ConcreteEnvironment(committed['plan'], self.store, self.f.gate)
            _, observations = environment._gateway_history(committed)
        self.assertEqual({identifier, self.http.adapter.observe(require_route=False)['id']},
                         {value['effect_identity']['container_id'] for value in observations})
        requests, gate, operations = self.http.requests.read_bytes(), self.f.gate.snapshot(), self.store.list()
        with self.assertRaisesRegex(Exception, 'RESTORE_GATEWAY_IDENTITY'):
            self.coordinator.rollback(committed['id'])
        self.assertEqual(requests, self.http.requests.read_bytes())
        self.assertEqual(gate, self.f.gate.snapshot())
        self.assertEqual(operations, self.store.list())

    def test_uncommitted_rollback_cannot_leave_renamed_creation_and_report_restored(self):
        identifier = self.identity['container_id']
        self.http.adapter.engine.request('POST', '/containers/' + identifier + '/rename?name=renamed-owned', {})
        requests = self.http.requests.read_bytes()
        final = self.coordinator.rollback(self.applied['id'])
        self.assertIsNone(final['decision'])
        self.assertFalse(final['released'])
        self.assertEqual('CLOSED', self.f.gate.snapshot()['state'])
        self.assertEqual(requests, self.http.requests.read_bytes())
        self.assertEqual(identifier, self.http.adapter.engine.request('GET', '/containers/' + identifier + '/json')['Id'])

    def test_uncommitted_rollback_can_finish_after_creation_was_truly_removed(self):
        identifier = self.identity['container_id']
        self.http.adapter.engine.request('DELETE', '/containers/' + identifier + '?force=false&v=false')
        requests = self.http.requests.read_bytes()
        final = self.coordinator.rollback(self.applied['id'])
        self.assertEqual('ROLLED_BACK', final['decision'], final['waiting'])
        self.assertTrue(final['released'])
        self.assertEqual('OPEN', self.f.gate.snapshot()['state'])
        self.assertEqual(requests, self.http.requests.read_bytes())

    def correction(self, *, predecessor=None, marker='d', present=False, pause=False):
        predecessor = predecessor or self.applied
        configuration = self.f.configuration(marker * 64)
        candidate = self.f.root / ('correction-' + marker + '.json')
        self.f.write(candidate, configuration)
        target = self.f.deployment(marker * 64, configuration)
        target['gateway'] = {**self.f.source['gateway'], 'deployment_digest': marker * 64, 'present': present,
            'config_digest': target['selection']['components']['manager']['configuration_digest']}
        binding = {'schema': BINDING_SCHEMA, 'node_id': 'node', 'state': str(self.store.root), 'profile': self.f.profile}
        release = {'schema': RELEASE_SCHEMA, 'node_id': 'node', 'request_id': 'correct-' + marker,
            'target': target, 'files': [{'source': str(candidate), 'target': str(self.f.config)}]}
        plan = repair_plan(binding, release, predecessor['id'])
        successor = self.coordinator.supersede(predecessor['id'], plan)['successor']
        with patch.object(ConcreteEnvironment, 'check_local', return_value={'passed': False}) if pause else nullcontext():
            return self.coordinator.resume(successor)

    def test_corrective_commit_cannot_forget_inherited_renamed_creation(self):
        identifier = self.identity['container_id']
        self.http.adapter.engine.request('POST', '/containers/' + identifier + '/rename?name=renamed-owned', {})
        requests = self.http.requests.read_bytes()
        final = self.correction()
        self.assertIsNone(final['decision'])
        self.assertFalse(final['released'])
        self.assertEqual('CLOSED', self.f.gate.snapshot()['state'])
        self.assertEqual([self.applied['id']], final['inherited'])
        self.assertEqual(requests, self.http.requests.read_bytes())
        self.assertEqual(identifier, self.http.adapter.engine.request('GET', '/containers/' + identifier + '/json')['Id'])

    def test_corrective_commit_accepts_actual_absence_of_inherited_creation(self):
        identifier = self.identity['container_id']
        self.http.adapter.engine.request('DELETE', '/containers/' + identifier + '?force=false&v=false')
        requests = self.http.requests.read_bytes()
        final = self.correction()
        self.assertEqual('COMMITTED', final['decision'], final['waiting'])
        self.assertTrue(final['released'])
        self.assertEqual(requests, self.http.requests.read_bytes())

    def test_multigeneration_correction_accepts_removed_original_ids(self):
        first = self.identity['container_id']
        intermediate = self.correction(present=True, pause=True)
        self.assertIsNone(intermediate['decision'])
        second = self.http.adapter.observe(require_route=False)['id']
        self.assertNotEqual(first, second)
        final = self.correction(predecessor=intermediate, marker='e')
        self.assertEqual('COMMITTED', final['decision'], final['waiting'])
        self.assertTrue(final['released'])
        self.assertEqual([self.applied['id'], intermediate['id']], final['inherited'])
        for identifier in (first, second):
            self.assertIsNone(self.http.adapter.engine.request('GET', '/containers/' + identifier + '/json', missing=True))


class RenameBeforeErrorHandler(NamedHandler):
    def reply(self, status, value, **kwargs):
        if status == 500 and self.server.container is not None:
            self.server.current_name = 'renamed-before-first-observation'
        super().reply(status, value, **kwargs)


class UncertainGatewayCreationTests(_GatewayRollbackFixture):
    pause_before_commit = True
    handler = RenameBeforeErrorHandler
    mode = 'effect_then_error'

    def test_direct_adapter_retries_retain_the_original_unknown_attempt(self):
        record = next(record for step, record in zip(self.applied['plan']['steps'], self.applied['steps'])
                      if step['action'].get('kind') == 'gateway_create')
        requests = self.http.requests.read_bytes()
        root = self.store.root / 'supervision'
        retained = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
        with self.store.locked():
            environment = ConcreteEnvironment(self.applied['plan'], self.store, self.f.gate)
            environment._mutating_adapters()
            environment.gateway.guard_check = self.http.adapter.guard_check
            previous = record['attempts'][0]
            for index in range(3):
                observed = environment.gateway.execute(record['prepared'], attempt_id='direct-retry-' + str(index),
                    lock_fd=self.store.lock_fd, previous=previous,
                    persist_intent=lambda _: self.fail('unknown creation cannot acquire a new attempt'))
                self.assertEqual('unknown', observed['outcome'])
                self.assertEqual(['created-1'], observed['unresolved_creation_candidates'])
                self.assertEqual(previous['binding'], observed['supervision']['binding'])
                self.assertNotIn('attempt', observed)
        self.assertEqual(retained, {path: path.read_bytes() for path in root.rglob('*') if path.is_file()})
        self.assertEqual(requests, self.http.requests.read_bytes())

    def test_error_before_first_id_capture_cannot_be_aborted_as_no_change(self):
        self.assertIsNone(self.identity)
        record = next(record for step, record in zip(self.applied['plan']['steps'], self.applied['steps'])
                      if step['action'].get('kind') == 'gateway_create')
        observed = record['observation']
        self.assertTrue(observed['closed'], 'the complete HTTP failure remains closed')
        self.assertEqual('unknown', observed['state'])
        self.assertEqual(['created-1'], observed['unresolved_creation_candidates'])
        self.assertFalse(record['effective'], 'copyable labels cannot establish exact ownership')
        self.assertNotIn('effect_identity', record['attempts'][0])
        requests = self.http.requests.read_bytes()
        for method in (self.coordinator.resume, self.coordinator.rollback):
            final = method(self.applied['id'])
            self.assertIsNone(final['decision'])
            self.assertFalse(final['released'])
        self.assertEqual('CLOSED', self.f.gate.snapshot()['state'])
        self.assertEqual(requests, self.http.requests.read_bytes())
        self.assertEqual('created-1', self.http.adapter.engine.request('GET', '/containers/created-1/json')['Id'])


class DroppedCreationReplyHandler(NamedHandler):
    def reply(self, status, value, **kwargs):
        if status == 201:
            return
        super().reply(status, value, **kwargs)


class AdoptedGatewayCreationTests(_GatewayRollbackFixture):
    pause_before_commit = True
    handler = DroppedCreationReplyHandler

    def original_creation(self):
        record = next(record for step, record in zip(self.applied['plan']['steps'], self.applied['steps'])
                      if step['action'].get('kind') == 'gateway_create')
        self.assertEqual('target', record['observation']['state'])
        self.assertTrue(record['observation']['closed'])
        self.assertEqual('unknown', record['observation']['supervision']['result']['status'])
        self.assertEqual(self.identity, record['attempts'][0]['effect_identity'])
        return record

    def test_verified_creation_with_lost_reply_can_finish_normal_rollback(self):
        record = self.original_creation()
        receipt = Path(record['attempts'][0]['binding']['result_directory']) / 'result.json'
        original = receipt.read_bytes()
        final = self.coordinator.rollback(self.applied['id'])
        self.assertEqual('ROLLED_BACK', final['decision'], final['waiting'])
        self.assertTrue(final['released'])
        self.assertIsNone(self.http.adapter.engine.request('GET', '/containers/' + self.identity['container_id'] + '/json', missing=True))
        self.assertEqual(original, receipt.read_bytes())

    def test_verified_creation_with_lost_reply_survives_legitimate_corrective_replacement(self):
        self.original_creation()
        final = PendingGatewayRollbackTests.correction(self, present=True)
        self.assertEqual('COMMITTED', final['decision'], final['waiting'])
        self.assertTrue(final['released'])
        self.assertNotEqual(self.identity['container_id'], self.http.adapter.observe(require_route=False)['id'])
        self.assertIsNone(self.http.adapter.engine.request('GET', '/containers/' + self.identity['container_id'] + '/json', missing=True))

    def test_fixed_completion_does_not_authorize_renamed_creation_replay(self):
        self.original_creation()
        identifier = self.identity['container_id']
        self.http.adapter.engine.request('POST', '/containers/' + identifier + '/rename?name=renamed-owned', {})
        requests = self.http.requests.read_bytes()
        final = self.coordinator.resume(self.applied['id'])
        self.assertIsNone(final['decision'])
        self.assertFalse(final['released'])
        self.assertEqual(requests, self.http.requests.read_bytes())
        self.assertEqual(identifier, self.http.adapter.engine.request('GET', '/containers/' + identifier + '/json')['Id'])
