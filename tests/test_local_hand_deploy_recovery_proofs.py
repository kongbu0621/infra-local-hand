"""Read-only corrective planning reuses exact retained gateway observations."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from admin.local_hand_deploy import recovery
from admin.local_hand_deploy.binding import BINDING_SCHEMA, RELEASE_SCHEMA, repair_plan
from admin.local_hand_deploy.model import DeployError
import test_local_hand_deploy_gateway_completion as completion
import test_local_hand_deploy_gateway_removal as removal


class RecoveryProofTests(unittest.TestCase):
    def start_fixture(self):
        case = completion.GatewayCompletionTests('runTest')
        case.setUp(); self.addCleanup(case.doCleanups)
        return case

    def check_closed(self, case, op):
        original = copy.deepcopy(op)
        database = case.store.path.read_bytes()
        requests = case.f.requests.read_bytes()
        try:
            with case.store.locked(readonly=True), \
                    patch.object(recovery, 'ConcreteEnvironment', return_value=case.concrete), \
                    patch.object(case.f.adapter, 'route_probe', side_effect=OSError('route unavailable')):
                self.assertEqual([op], recovery.closed_effects(case.store, case.gate, op))
        finally:
            self.assertEqual(original, op)
            self.assertEqual(database, case.store.path.read_bytes())
            self.assertEqual(requests, case.f.requests.read_bytes())

    def test_readonly_recovery_reuses_legacy_start_completion_without_refresh(self):
        case = self.start_fixture()
        op, receipt, raw = case.lost_start()
        case.legacy(op, state='INTENT_RECORDED')
        self.check_closed(case, op)
        self.assertEqual(raw, receipt.read_bytes())
        self.assertNotIn('completion_identity', op['steps'][1]['attempts'][-1])

    def test_readonly_recovery_reuses_legacy_compensation_completion(self):
        case = self.start_fixture(); case.running_replacement_plan()
        case.environment.check_ok = False
        op = case.coordinator.apply(case.plan)
        case.f.mode.write_text('start_disconnect')
        op = case.coordinator.rollback(op['id'])
        self.assertIsNone(op['decision'])
        case.legacy(op, restore=True)
        case.f.mode.write_text('success')
        self.check_closed(case, op)

    def test_readonly_recovery_requires_the_original_target_observation(self):
        case = self.start_fixture()
        op, _, _ = case.lost_start(); case.legacy(op)
        op['steps'][1]['observation'] = None
        with self.assertRaises(DeployError) as refused:
            self.check_closed(case, op)
        self.assertEqual('CALLER_NOT_CLOSED', refused.exception.code)

    def test_old_target_cannot_close_a_later_unknown_attempt(self):
        case = self.start_fixture()
        op, _, _ = case.lost_start()
        old = copy.deepcopy(op['steps'][1]['observation'])
        identifier = case.f.adapter.observe(require_route=False)['id']
        case.f.adapter.engine.request('POST', '/containers/' + identifier + '/stop?t=10')
        case.f.mode.write_text('start_disconnect')
        with patch.object(case.f.adapter, 'route_probe', side_effect=OSError('new start not verified')):
            op = case.coordinator.resume(op['id'])
        self.assertEqual(2, len(op['steps'][1]['attempts']))
        # The attempt's intent can be saved before its first observation.
        op['steps'][1]['observation'] = old
        with self.assertRaises(DeployError) as refused:
            self.check_closed(case, op)
        self.assertEqual('CALLER_NOT_CLOSED', refused.exception.code)

    def test_real_repair_plan_reuses_legacy_creation_after_original_deletion(self):
        case = removal.AdoptedGatewayCreationTests('runTest')
        case.setUp(); self.addCleanup(case.doCleanups)
        op = case.applied
        record = case.original_creation()
        receipt = Path(record['attempts'][0]['binding']['result_directory']) / 'result.json'
        raw = receipt.read_bytes()
        record['attempts'][0].pop('effect_identity')
        record['observation'].pop('effect_identity', None)
        record['observation'].get('attempt', {}).pop('effect_identity', None)
        with case.store.locked():
            case.store.save(op, 'LEGACY_CREATION_OBSERVATION')
        identifier = case.identity['container_id']
        case.http.adapter.engine.request('DELETE', '/containers/' + identifier + '?force=false&v=false')
        configuration = case.f.configuration('d' * 64)
        candidate = case.f.root / 'corrected.json'; case.f.write(candidate, configuration)
        target = case.f.deployment('d' * 64, configuration)
        target['gateway'] = {**case.f.source['gateway'], 'deployment_digest': 'd' * 64,
            'config_digest': target['selection']['components']['manager']['configuration_digest']}
        binding = {'schema': BINDING_SCHEMA, 'node_id': 'node', 'state': str(case.store.root), 'profile': case.f.profile}
        release = {'schema': RELEASE_SCHEMA, 'node_id': 'node', 'request_id': 'legacy-correction',
            'target': target, 'files': [{'source': str(candidate), 'target': str(case.f.config)}]}
        database = case.store.path.read_bytes(); gate = case.f.gate.snapshot()
        requests = case.http.requests.read_bytes()
        plan = repair_plan(binding, release, op['id'])
        self.assertEqual(database, case.store.path.read_bytes())
        self.assertEqual(gate, case.f.gate.snapshot())
        self.assertEqual(requests, case.http.requests.read_bytes())
        self.assertEqual(raw, receipt.read_bytes())
        successor = case.coordinator.supersede(op['id'], plan)['successor']
        final = case.coordinator.resume(successor)
        self.assertEqual('COMMITTED', final['decision'], final['waiting'])
        self.assertTrue(final['released'])

    def test_fresh_readonly_environment_recovers_identity_without_saved_observation(self):
        case = removal.AdoptedGatewayCreationTests('runTest')
        case.setUp(); self.addCleanup(case.doCleanups)
        op = case.applied
        record = case.original_creation()
        record['observation'] = None
        original = copy.deepcopy(op)
        database = case.store.path.read_bytes(); requests = case.http.requests.read_bytes()
        with case.store.locked(readonly=True):
            self.assertEqual([op], recovery.closed_effects(case.store, case.f.gate, op))
        self.assertEqual(original, op)
        self.assertEqual(database, case.store.path.read_bytes())
        self.assertEqual(requests, case.http.requests.read_bytes())


if __name__ == '__main__':
    unittest.main()
