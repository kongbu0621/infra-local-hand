"""Pre-fork failures never consume a daemon dispatch or poison same-process recovery."""
import copy
import fcntl
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from admin.local_hand_deploy import supervision
from admin.local_hand_deploy.supervision import AdapterError, SupervisedRunner
from admin.local_hand_deploy.services import SystemdAdapter, _link_state
from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.model import PLAN_SCHEMA, digest, seal_plan
from admin.local_hand_deploy.runtime import ConcreteEnvironment
from admin.local_hand_deploy.store import Store, Limits
from local_hand_jobs.maintenance import MaintenanceGate
from test_local_hand_deploy_coordinator import Effects


class SupervisionRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.fd = os.open(self.root / 'lock', os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, self.fd)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.runner = SupervisedRunner(self.root / 'calls', timeout=0.3)
        self.bound = []

    def start(self, runner=None, attempt='original', persist=None):
        return (runner or self.runner).run({'kind': 'fixture'},
            lambda *_: (self.root / 'effect').write_text('one'), attempt_id=attempt,
            lock_fd=self.fd, persist_intent=persist or self.bound.append)

    def test_fork_failure_closes_in_original_and_new_runner_without_replaying(self):
        with patch.object(supervision.os, 'fork', side_effect=OSError('fork unavailable')):
            with self.assertRaisesRegex(OSError, 'fork unavailable'):self.start()
        self.assertFalse((self.root / 'effect').exists())
        for runner in (self.runner, SupervisedRunner(self.root / 'calls')):
            observed = runner.observe(self.bound[0], lock_fd=self.fd)
            self.assertTrue(observed['closed'])
            self.assertEqual('OSError', observed['not_started']['error_type'])
            self.assertEqual([], observed['events'])
            self.assertFalse(runner.observe(self.bound[0])['closed'])
            self.start(runner)
            self.assertFalse((self.root / 'effect').exists())
        self.assertTrue(self.start(attempt='retry')['closed'])
        self.assertEqual('one', (self.root / 'effect').read_text())

    def test_intent_ack_failure_retains_no_child_and_original_error(self):
        def fail(binding):
            self.bound.append(binding)
            raise OSError('intent ack lost')
        with patch.object(supervision.os, 'fork') as fork:
            with self.assertRaisesRegex(OSError, 'intent ack lost'):self.start(persist=fail)
        fork.assert_not_called()
        observed = self.runner.observe(self.bound[0], lock_fd=self.fd)
        self.assertTrue(observed['closed'])
        self.assertEqual('intent ack lost', observed['not_started']['error'])

    def test_thread_precondition_can_recover_after_thread_exits(self):
        done = threading.Event(); thread = threading.Thread(target=done.wait); thread.start()
        try:
            with self.assertRaisesRegex(AdapterError, 'SINGLE_THREAD'):self.start()
        finally:done.set(); thread.join(3)
        self.assertTrue(self.runner.observe(self.bound[0], lock_fd=self.fd)['closed'])
        self.assertTrue(self.start(attempt='retry')['closed'])

    def test_receipt_staging_failure_keeps_original_caller_proof_and_partial_bytes(self):
        write = supervision._write_once
        def fail(path, value, maximum):
            if path.name == 'not-started.pending':
                path.write_bytes(b'{partial')
                raise OSError('receipt unavailable')
            return write(path, value, maximum)
        with patch.object(supervision, '_write_once', side_effect=fail), \
                patch.object(supervision.os, 'fork', side_effect=OSError('fork unavailable')):
            with self.assertRaisesRegex(OSError, 'fork unavailable') as error:self.start()
        self.assertIn('receipt unavailable', ' '.join(error.exception.__notes__))
        self.assertEqual(b'{partial', (self.root / 'calls/original/not-started.pending').read_bytes())
        self.assertFalse((self.root / 'calls/original/not-started.json').exists())
        self.assertTrue(self.runner.observe(self.bound[0], lock_fd=self.fd)['closed'])
        self.assertTrue(self.start(attempt='retry')['closed'])

    def test_receipt_cannot_override_conflicting_binding_process_result_or_event(self):
        with patch.object(supervision.os, 'fork', side_effect=OSError('fork unavailable')):
            with self.assertRaises(OSError):self.start()
        directory = self.root / 'calls/original'
        receipt = directory / 'not-started.json'; original = receipt.read_bytes()
        wrong = json.loads(original); wrong['binding_digest'] = '0' * 64
        receipt.write_text(json.dumps(wrong))
        with self.assertRaisesRegex(AdapterError, 'NO_START_CONFLICT'):
            self.runner.observe(self.bound[0], lock_fd=self.fd)
        receipt.write_bytes(original)
        for name in ('process.json', 'result.json', 'event-00.json', 'event-01.json', 'event-31.json'):
            with self.subTest(name=name):
                path = directory / name; path.write_text('null')
                try:
                    with self.assertRaisesRegex(AdapterError, 'NO_START_CONFLICT'):
                        self.runner.observe(self.bound[0], lock_fd=self.fd)
                finally:path.unlink()

    def test_asynchronous_fork_interruption_is_not_a_no_start_receipt(self):
        def interrupted():raise KeyboardInterrupt('unknown fork boundary')
        with patch.object(supervision.os, 'fork', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):self.start()
        self.assertFalse((self.root / 'calls/original/not-started.json').exists())
        self.assertFalse(self.runner.observe(self.bound[0], lock_fd=self.fd)['closed'])

    def test_real_coordinator_retries_fork_failure_with_one_dispatch_budget(self):
        target = str(self.root / 'enabled.service')
        action = {'kind': 'service_policy_link', 'target': 'fixture.service', 'path': target,
                  'before': _link_state(target), 'after': {'kind': 'link', 'target': '/fixture/unit.service'}}
        plan = seal_plan({'schema': PLAN_SCHEMA, 'request_id': 'prepare-retry', 'node_id': 'node',
            'source': {'deployment_digest': digest('old')}, 'target': {'deployment_digest': digest('new')},
            'profile': {}, 'steps': [{'id': 'link', 'kind': 'service', 'action': action}]})
        store = Store(self.root / 'records', 'node', limits=Limits(max_attempts=1)); store.initialize()
        gate_dir = self.root / 'gate'; gate_dir.mkdir(mode=0o700)
        gate = MaintenanceGate(gate_dir, 'node', owner_uid=os.geteuid()); gate.initialize(digest('old'), 'fixture', bootstrap=True)
        env = ConcreteEnvironment(plan, store, gate)
        env._runner = self.runner
        env._services = SystemdAdapter({'units': {'fixture.service': {
            'policy_links': {target: {'target': '/fixture/unit.service'}}}}}, self.runner)
        class Environment(Effects):
            def effect_key(self, step):return env.effect_key(step)
            def prepare(self, step, op, record):return copy.deepcopy(step['action'])
            def observe(self, *args, **kwargs):return env.observe(*args, **kwargs)
            def execute(self, *args, **kwargs):return env.execute(*args, **kwargs)
        coordinator = Coordinator(store, gate, Environment())
        with patch.object(supervision.os, 'fork', side_effect=OSError('fork unavailable')):
            op = coordinator.apply(plan)
        self.assertIsNone(op['decision']); self.assertFalse(Path(target).is_symlink())
        op = coordinator.resume(op['id'])
        self.assertEqual('COMMITTED', op['decision'], op['waiting'])
        self.assertEqual([False, True], [attempt['dispatched'] for attempt in op['steps'][0]['attempts']])
        self.assertEqual('/fixture/unit.service', os.readlink(target))
        self.assertEqual(op, coordinator.resume(op['id']))


if __name__ == '__main__':unittest.main()
