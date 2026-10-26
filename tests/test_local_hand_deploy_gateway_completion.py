"""Retain adopted start/stop completion across later readiness or state changes."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from admin.local_hand_deploy.model import digest, seal_plan
import test_local_hand_deploy_gateway_start as fixtures


class GatewayCompletionTests(unittest.TestCase):
    def setUp(self):
        fixtures.GatewayStartTests.setUp(self)
        self.environment.completion_identity = self.concrete.completion_identity

    running_replacement_plan = fixtures.GatewayStartTests.running_replacement_plan

    def lost_start(self, *, commit=False):
        self.environment.check_ok = commit
        self.environment.after_create = lambda _: self.f.mode.write_text('start_disconnect')
        op = self.coordinator.apply(self.plan)
        record = op['steps'][1]
        self.assertEqual('VERIFIED', record['state'])
        self.assertEqual('target', record['observation']['state'])
        self.assertTrue(record['observation']['closed'])
        self.assertEqual('unknown', record['observation']['supervision']['result']['status'])
        receipt = Path(record['attempts'][0]['binding']['result_directory']) / 'result.json'
        self.f.mode.write_text('success')
        self.environment.after_create = None
        return op, receipt, receipt.read_bytes()

    def legacy(self, op, *, restore=False, state=None):
        record = op['compensation'][-1]['record'] if restore else op['steps'][1]
        attempts = record['restore_attempts' if restore else 'attempts']
        attempts[-1].pop('completion_identity', None)
        saved = record['restore_observation' if restore else 'observation']
        saved.pop('completion_identity', None)
        saved.get('attempt', {}).pop('completion_identity', None)
        if state is not None:
            record['state'] = state
        with self.store.locked():
            self.store.save(op, 'LEGACY_ADOPTED_COMPLETION')

    def test_lost_start_reply_keeps_completion_when_route_later_fails(self):
        op, receipt, raw = self.lost_start()
        self.environment.check_ok = True
        with patch.object(self.f.adapter, 'route_probe', side_effect=OSError('route failed after adopted start')):
            final = self.coordinator.rollback(op['id'])
        self.assertEqual('ROLLED_BACK', final['decision'], final['waiting'])
        self.assertTrue(final['released'])
        self.assertEqual(raw, receipt.read_bytes())
        self.assertEqual(1, sum(path.endswith('/start') for path in self.f.requests.read_text().splitlines()))

    def test_saved_target_before_verified_migrates_before_refresh_overwrites_it(self):
        op, receipt, raw = self.lost_start()
        self.legacy(op, state='INTENT_RECORDED')
        self.environment.check_ok = True
        with patch.object(self.f.adapter, 'route_probe', side_effect=OSError('route unavailable')):
            final = self.coordinator.rollback(op['id'])
        self.assertEqual('ROLLED_BACK', final['decision'], final['waiting'])
        proof = final['steps'][1]['attempts'][0]['completion_identity']
        self.assertEqual(final['steps'][0]['attempts'][0]['effect_identity']['container_id'], proof['container_id'])
        self.assertEqual(raw, receipt.read_bytes())

    def test_missing_old_target_cannot_invent_completion_from_failed_route(self):
        op, _, _ = self.lost_start()
        self.legacy(op)
        op['steps'][1]['observation'] = None
        with self.store.locked():
            self.store.save(op, 'MISSING_ADOPTED_COMPLETION')
        requests = self.f.requests.read_bytes()
        with patch.object(self.f.adapter, 'route_probe', side_effect=OSError('route unavailable')):
            final = self.coordinator.rollback(op['id'])
        self.assertIsNone(final['decision'])
        self.assertEqual('CALLER_NOT_CLOSED', final['waiting']['reason'])
        self.assertNotIn('completion_identity', final['steps'][1]['attempts'][0])
        self.assertEqual(requests, self.f.requests.read_bytes())

    def test_later_unknown_start_does_not_borrow_previous_attempt_completion(self):
        op, _, _ = self.lost_start()
        original = copy.deepcopy(op['steps'][1]['attempts'][0].get('completion_identity'))
        identity = self.f.adapter.observe(require_route=False)['id']
        self.f.adapter.engine.request('POST', '/containers/' + identity + '/stop?t=10')
        self.f.mode.write_text('start_disconnect')
        with patch.object(self.f.adapter, 'route_probe', side_effect=OSError('second start has no readiness proof')):
            final = self.coordinator.resume(op['id'])
        attempts = final['steps'][1]['attempts']
        self.assertEqual(2, len(attempts))
        self.assertIsNotNone(original)
        self.assertEqual(original, attempts[0]['completion_identity'])
        self.assertNotIn('completion_identity', attempts[1])
        self.assertFalse(final['steps'][1]['observation']['closed'])

    def test_adopted_stop_can_retry_after_same_container_is_restarted(self):
        self.f.independent_create()
        identity = self.f.adapter.observe(require_route=False)['id']
        self.f.adapter.engine.request('POST', '/containers/' + identity + '/start')
        action = self.f.adapter.plan({'running': False, 'config_digest': 'b' * 64, 'deployment_digest': 'c' * 64})[0]
        self.f.mode.write_text('start_disconnect')
        first = self.f.adapter.execute(action, attempt_id='lost-stop', lock_fd=self.f.fd, persist_intent=lambda _: None)
        self.assertTrue(first['postcondition'])
        self.assertEqual('unknown', first['supervision']['result']['status'])
        receipt = Path(first['attempt']['binding']['result_directory']) / 'result.json';raw = receipt.read_bytes()
        self.f.mode.write_text('success')
        self.f.adapter.engine.request('POST', '/containers/' + identity + '/start')
        final = self.f.adapter.execute(action, attempt_id='stop-again', lock_fd=self.f.fd,
            persist_intent=lambda _: None, previous=first['attempt'])
        self.assertTrue(final['postcondition'], final)
        self.assertEqual('stopped', self.f.adapter.observe(require_route=False)['status'])
        self.assertEqual(raw, receipt.read_bytes())

    def test_committed_legacy_start_completion_allows_identity_only_rollback_check(self):
        op, receipt, raw = self.lost_start(commit=True)
        self.legacy(op)
        original = copy.deepcopy(op)
        self.concrete.profile = {**self.concrete.profile, 'gateway': self.f.adapter.profile}
        with self.store.locked(), patch.object(self.f.adapter, 'route_probe', side_effect=OSError('route unavailable')):
            current = self.concrete._committed_gateway([op])
        self.assertEqual(op['steps'][0]['attempts'][0]['effect_identity']['container_id'], current['id'])
        self.assertEqual(original, op)
        self.assertEqual(raw, receipt.read_bytes())

    def test_adopted_start_can_handoff_and_compensate_inherited_effects(self):
        op, receipt, raw = self.lost_start()
        self.legacy(op)
        successor = seal_plan({**{key: value for key, value in self.plan.items() if key != 'digest'},
            'request_id': 'correct-after-adopted-start', 'target': {'deployment_digest': digest('corrected')}, 'steps': []})
        self.environment.check_ok = True
        with patch.object(self.f.adapter, 'route_probe', side_effect=OSError('route unavailable')):
            linked = self.coordinator.supersede(op['id'], successor)
            self.assertIsNotNone(linked['successor'], linked['waiting'])
            final = self.coordinator.rollback(linked['successor'])
        self.assertEqual('ROLLED_BACK', final['decision'], final['waiting'])
        self.assertEqual([op['id']], final['inherited'])
        self.assertEqual(raw, receipt.read_bytes())

    def test_compensation_preserves_adopted_start_completion_without_faking_readiness(self):
        self.running_replacement_plan()
        self.environment.check_ok = False
        op = self.coordinator.apply(self.plan)
        self.f.mode.write_text('start_disconnect')
        restored = self.coordinator.rollback(op['id'])
        self.assertIsNone(restored['decision'])
        record = restored['compensation'][-1]['record']
        self.assertEqual('gateway_start', record['restore']['kind'])
        self.assertEqual('RESTORED', record['state'])
        self.legacy(restored, restore=True)
        self.f.mode.write_text('success');self.environment.check_ok = True
        requests = self.f.requests.read_bytes()
        with patch.object(self.f.adapter, 'route_probe', side_effect=OSError('restored route unavailable')):
            waiting = self.coordinator.resume(op['id'])
        self.assertIsNone(waiting['decision'])
        self.assertNotEqual('CALLER_NOT_CLOSED', waiting['waiting']['reason'])
        self.assertTrue(waiting['compensation'][-1]['record']['restore_observation']['closed'])
        self.assertFalse(waiting['compensation'][-1]['record']['restore_observation']['postcondition'])
        self.assertEqual(requests, self.f.requests.read_bytes())
        final = self.coordinator.resume(op['id'])
        self.assertEqual('ROLLED_BACK', final['decision'], final['waiting'])
        self.assertEqual(requests, self.f.requests.read_bytes())


if __name__ == '__main__':
    unittest.main()
