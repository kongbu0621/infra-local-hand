"""Q1 experiment wiring with explicit fake supervision/controller, no host calls."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import base64
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from admin.local_hand_quota_observer import admission as a, experiment as e, protected_inputs as p
from admin.local_hand_quota_observer.controller_guard import ControllerObservation
from admin.local_hand_quota_observer.supervision import Decision
from admin.local_hand_quota_observer.systemd_runtime import Outcome
from test_e3_quota_fixture import make_inputs
from test_e3_quota_monitor import binding, encoded


INPUT_PATH = '/synthetic/experiment/input.json'


def experiment_fixture(operation='run'):
    inputs = make_inputs()
    manifest = a.decode_manifest(inputs['manifest_bytes'], inputs['manifest_digest'])
    config = p.decode_runtime(inputs['runtime_bytes'], inputs['runtime_digest'])
    bound = binding(manifest)
    controller = {
        'schema': 'local-hand-q1-controller/v1', 'unit': 'lhqc-fixture.service',
        'invocation_id': 'd' * 32, 'cgroup': '/lhqcfixture.slice/lhqc-fixture.service',
        'cgroup_device': 71, 'cgroup_inode': 72, 'runtime_max_usec': 60_000_000,
        'timeout_stop_usec': 1_000_000, 'memory_bytes': 128 * 1024**2,
        'tasks_max': 16, 'cpu_quota_per_sec_usec': 1_000_000, 'limit_cpu_seconds': 30,
    }
    value = {
        'schema': 'local-hand-quota-q1-experiment-input/v1', 'operation': operation,
        'source_commit': manifest.source_commit, 'runtime_path': inputs['runtime_path'],
        'runtime_digest': inputs['runtime_digest'],
        'journal': {'path': inputs['journal_path'], 'owner_uid': 0, 'device': 61, 'inode': 62},
        'ticket': p.encode_ticket(bound), 'controller': controller,
    }
    observation = ControllerObservation(controller['unit'], controller['invocation_id'], controller['cgroup'],
                                        71, 72, manifest.boot_id, 500, bound.issued_ns, 9, 20, 9, 21)
    return inputs, manifest, config, bound, value, observation


def decode(value):
    raw = encoded(value)
    return e.decode_experiment(raw, hashlib.sha256(raw).hexdigest(), 'c' * 40)


class ExperimentInputTests(unittest.TestCase):
    def test_pins_original_ticket_and_explicit_operation_without_new_time_or_id(self):
        _, _, _, bound, value, _ = experiment_fixture()
        with patch('builtins.open', side_effect=AssertionError('pure decode opened a file')):
            spec = decode(value)
        self.assertEqual(spec.ticket, p.encode_ticket(bound))
        self.assertEqual(spec.operation, 'run')
        with self.assertRaises(FrozenInstanceError):
            spec.operation = 'recover_original'
        value['operation'] = 'recover_original'
        recovery = decode(value)
        self.assertEqual(recovery.ticket, spec.ticket)
        self.assertNotEqual(recovery.digest, spec.digest)

    def test_external_pins_fix_original_bytes_and_full_source_commit(self):
        value = experiment_fixture()[4]
        raw = encoded(value)
        for document, digest, source, reason in (
            (raw + b' ', hashlib.sha256(raw).hexdigest(), 'c' * 40, 'EXPERIMENT_DIGEST'),
            (raw, hashlib.sha256(raw).hexdigest(), 'd' * 40, 'SOURCE_COMMIT_CHANGED'),
            (raw, hashlib.sha256(raw).hexdigest(), 'c' * 7, 'TOKEN'),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(a.Rejected, reason):
                e.decode_experiment(document, digest, source)

    def test_no_default_operation_new_deadline_or_quota_override(self):
        original = experiment_fixture()[4]
        cases = []
        for operation in (None, True, 'retry', 'prepare', 'install', 'observe', 'release'):
            value = deepcopy(original); value['operation'] = operation; cases.append(value)
        value = deepcopy(original); del value['operation']; cases.append(value)
        for key in ('duration', 'deadline', 'force', 'prepared', 'command', 'quota_limit'):
            value = deepcopy(original); value[key] = 1; cases.append(value)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(a.Rejected):
                decode(value)

    def test_control_identity_is_exact_and_cannot_be_a_boolean_or_nonroot(self):
        original = experiment_fixture()[4]
        for field, value in (('owner_uid', True), ('owner_uid', 1000), ('device', -1),
                             ('inode', 0), ('path', '/'), ('path', '/synthetic/../journal')):
            changed = deepcopy(original); changed['journal'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(a.Rejected):
                decode(changed)
        original['controller'] = {'supervised': True}
        with self.assertRaises(a.Rejected):
            decode(original)

    def test_duplicate_keys_unknown_versions_and_oversized_inputs_are_rejected(self):
        original = experiment_fixture()[4]
        raw = encoded(original)
        duplicate = b'{"operation":"run",' + raw[1:]
        too_large = raw + b' ' * e.MAX_EXPERIMENT_BYTES
        for document in (duplicate, too_large):
            with self.assertRaises(a.Rejected):
                e.decode_experiment(document, hashlib.sha256(document).hexdigest(), 'c' * 40)
        original['schema'] = 'other/v1'
        with self.assertRaisesRegex(a.Rejected, 'EXPERIMENT_VERSION'):
            decode(original)


class ExperimentWiringTests(unittest.TestCase):
    def setUp(self):
        self.inputs, self.manifest, self.config, self.bound, self.value, self.observation = experiment_fixture()
        self.calls = []
        self.close_error = self.run_error = self.guard_error = self.journal_error = None
        self.controller_config = self.config
        self.launcher = None
        self.journal = SimpleNamespace(close=self.close_journal)
        self.outcome = Outcome(Decision('UNKNOWN', 'ORIGINAL_INTENT_RETAINED'), self.bound,
                               b'partial\x00', b'errno=5\n', None, self.manifest.cgroup_parent, 0)
        for name, replacement in (
            ('read_protected', self.read), ('load_runtime', self.load),
            ('admit_controller', self.guard), ('_open_journal', self.open_journal),
            ('Q1Controller', self.controller),
        ):
            patcher = patch.object(e, name, side_effect=replacement)
            patcher.start(); self.addCleanup(patcher.stop)

    def read(self, filename, maximum):
        self.calls.append(('read', filename))
        if filename == INPUT_PATH:
            return encoded(self.value)
        self.assertEqual(filename, self.config.manifest_path)
        return self.inputs['manifest_bytes']

    def load(self, filename, digest):
        self.assertEqual((filename, digest), (self.inputs['runtime_path'], self.config.digest))
        return self.config

    def guard(self, config, manifest, spec):
        self.calls.append(('guard', spec.unit))
        self.assertEqual((config, manifest), (self.config, self.manifest))
        if self.guard_error:
            raise self.guard_error
        return self.observation

    def open_journal(self, identity):
        self.calls.append(('journal', identity.path))
        if self.journal_error:
            raise self.journal_error
        return self.journal

    def close_journal(self):
        self.calls.append(('close', None))
        if self.close_error:
            raise self.close_error

    def deliver_query(self, ticket):
        self.calls.append(('run', ticket))
        if self.run_error:
            raise self.run_error
        return self.outcome

    def recover(self, ticket):
        self.calls.append(('recover_original', ticket))
        return self.outcome

    def controller(self, path, digest, journal):
        self.calls.append(('controller', path))
        self.assertIs(journal, self.journal)
        return SimpleNamespace(config=self.controller_config, manifest=self.manifest,
                               run=self.deliver_query, recover_original=self.recover,
                               controls=[], launcher=self.launcher)

    def invoke(self):
        raw = encoded(self.value)
        result = json.loads(e.execute_experiment(INPUT_PATH, hashlib.sha256(raw).hexdigest(), 'c' * 40))
        for key in ('admission_proven', 'real_e3_accepted', 'production_supported'):
            self.assertIs(result[key], False)
        return result

    def test_supervision_precedes_every_journal_touch_and_only_original_ticket_is_called(self):
        result = self.invoke()
        self.assertEqual(result['status'], 'UNKNOWN')
        kinds = [kind for kind, _ in self.calls]
        self.assertLess(kinds.index('guard'), kinds.index('journal'))
        self.assertEqual([item for item in self.calls if item[0] == 'run'], [('run', self.value['ticket'])])
        self.assertEqual(kinds[-1], 'close')
        self.assertEqual(result['binding']['issued_ns'], self.bound.issued_ns)
        self.assertEqual(result['binding']['deadline_ns'], self.bound.deadline_ns)
        self.assertEqual(base64.b64decode(result['capture']['stdout']['data']), self.outcome.stdout)

    def test_recovery_never_calls_run_or_rebinds_original_ticket(self):
        self.value['operation'] = 'recover_original'
        result = self.invoke()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual([item for item in self.calls if item[0] == 'recover_original'],
                         [('recover_original', self.value['ticket'])])
        self.assertNotIn('run', [kind for kind, _ in self.calls])

    def test_guard_rejection_never_constructs_journal_or_controller(self):
        self.guard_error = a.Rejected('CONTROLLER_NOT_SUPERVISED')
        result = self.invoke()
        self.assertEqual(result['status'], 'REJECTED')
        self.assertFalse(result['controller_entered'])
        self.assertNotIn('journal', [kind for kind, _ in self.calls])

    def test_bad_ticket_is_rejected_before_host_admission_and_omitted_from_failure_context(self):
        self.value['ticket'] = base64.b64encode(b'{"unexpected":"private"}').decode()
        result = self.invoke()
        self.assertEqual(result['status'], 'REJECTED')
        self.assertIsNone(result['original_ticket'])
        self.assertNotIn('guard', [kind for kind, _ in self.calls])

    def test_input_file_cannot_be_inside_journal_or_overlap_an_installation(self):
        for filename in (self.value['journal']['path'] + '/input.json', self.config.worker_path):
            raw = encoded(self.value)
            with patch.object(e, 'read_protected', side_effect=[raw, self.inputs['manifest_bytes']]):
                result = json.loads(e.execute_experiment(filename, hashlib.sha256(raw).hexdigest(), 'c' * 40))
            self.assertEqual(result['status'], 'REJECTED')
        self.assertNotIn('guard', [kind for kind, _ in self.calls])

    def test_journal_initialization_failure_is_unknown_without_freeing_old_resources(self):
        self.journal_error = OSError('PRIVATE_PATH_MUST_NOT_ESCAPE')
        result = self.invoke()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertTrue(result['controller_entered'])
        self.assertNotIn('controller', [kind for kind, _ in self.calls])
        self.assertNotIn('PRIVATE_PATH_MUST_NOT_ESCAPE', json.dumps(result))

    def test_changed_second_runtime_read_does_not_deliver_a_query(self):
        self.controller_config = replace(self.config, digest='e' * 64)
        result = self.invoke()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertNotIn('run', [kind for kind, _ in self.calls])
        self.assertEqual(result['decision']['reason'], 'EXPERIMENT_INPUT_CHANGED')

    def test_interruption_preserves_partial_bytes_and_known_child_without_poll_or_retry(self):
        self.launcher = SimpleNamespace(stdout=bytearray(b'partial\xff'), stderr=bytearray(b'failure'),
                                        process=SimpleNamespace(pid=601))
        self.run_error = KeyboardInterrupt()
        result = self.invoke()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['decision']['reason'], 'EXPERIMENT_INTERRUPTED')
        self.assertEqual(result['pending_clients'], [601])
        self.assertFalse(result['decision']['query_stopped'])
        self.assertEqual(base64.b64decode(result['capture']['stdout']['data']), b'partial\xff')
        self.assertEqual(sum(kind == 'run' for kind, _ in self.calls), 1)

    def test_close_failure_is_separate_and_does_not_erase_raw_outcome(self):
        self.close_error = OSError('private detail')
        result = self.invoke()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['entry_error'], 'JOURNAL_CLOSE_UNCERTAIN')
        self.assertEqual(result['decision']['reason'], 'ORIGINAL_INTENT_RETAINED')
        self.assertEqual(base64.b64decode(result['capture']['stderr']['data']), b'errno=5\n')

    def test_encoder_failure_never_reexecutes_query(self):
        with patch.object(e, 'encode_outcome', side_effect=a.Rejected('EVIDENCE_BYTE_LIMIT')):
            result = self.invoke()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['failure_code'], 'EVIDENCE_BYTE_LIMIT')
        self.assertEqual(sum(kind == 'run' for kind, _ in self.calls), 1)


if __name__ == '__main__':
    unittest.main()
