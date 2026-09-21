"""Validation output -> bounded Result -> receipt -> recovery regressions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from config_fixtures import profile_v2
from local_hand import worker
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError, MAX_RESULT_JSON_BYTES, result_success, task_digest


class ResultBudgetChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'projects/demo'
        self.repo.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / 'sample.txt').write_bytes(b'before\n')
        self.mailbox = self.root / 'mailbox'
        for name in ('tasks', 'results', 'conflicts'):
            (self.mailbox / '_executor_spike' / name).mkdir(parents=True)
        self.state = self.root / 'state'

    def _task(self, task_id, action, params):
        return {'schema_version':'local-hand-task/v1', 'task_id':task_id,
                'target_node':'budget-fixture', 'action':action, 'params':params}

    def _profile(self, size, outcome):
        # Both streams fit their byte ceilings in the failed/timeout cases, but
        # JSON expands each NUL to six ASCII bytes. All child work is finite.
        code = ('import sys,time\n'
                f'sys.stdout.buffer.write(bytes({size}));sys.stdout.flush()\n'
                f'sys.stderr.buffer.write(bytes({size}));sys.stderr.flush()\n'
                + ('time.sleep(5)\n' if outcome == 'timeout' else
                   'raise SystemExit(0)\n' if outcome == 'succeeded' else 'raise SystemExit(7)\n'))
        value = profile_v2({'node_id':'budget-fixture', 'projects_root':str(self.repo.parent),
            'repositories':{'demo':{'path':'demo','single_writer':True,'validations':{
                'budget':{'argv':[sys.executable,'-I','-c',code],
                          'timeout_seconds':1 if outcome == 'timeout' else 5, 'replay_safe':True}}}}})
        path = self.root / 'profile.json'
        path.write_text(json.dumps(value))
        return load_profile(path)

    def _run_chain(self, size, outcome, expected_code):
        profile = self._profile(size, outcome)
        task = self._task('LH9100','validation.run_profile',{'repository':'demo','profile':'budget'})
        follow = self._task('LH9101','fs.write_text_cas',{'repository':'demo','relative_path':'sample.txt',
            'expected_sha256':hashlib.sha256(b'before\n').hexdigest(),'content':'after\n'})
        for value in (task, follow):
            (self.mailbox / '_executor_spike/tasks' / (value['task_id']+'.json')).write_text(json.dumps(value))
        with (mock.patch.object(worker,'validate_worker_mailbox'),
              mock.patch.object(worker,'sync_mailbox'), mock.patch.object(worker,'publish_outbox'),
              mock.patch.object(worker,'execute_task',wraps=worker.execute_task) as execute):
            worker.process_once(self.mailbox,profile.transport_policy.branch,profile,self.state)
            self.assertEqual((self.repo/'sample.txt').read_bytes(),b'after\n','oversized diagnostics blocked the next task')
            receipt_path = self.state / 'receipts/LH9100.json'
            receipt_bytes = receipt_path.read_bytes()
            receipt = json.loads(receipt_bytes)
            result_bytes = (self.state/'outbox/LH9100.json').read_bytes()
            result = json.loads(result_bytes)
            self.assertEqual(receipt['task_digest'],task_digest(task))
            self.assertEqual(receipt['result'],result)
            self.assertEqual(result['status'],'indeterminate' if outcome == 'succeeded' else 'failed')
            self.assertEqual(result['error_code'],expected_code)
            self.assertLessEqual(len(result_bytes),MAX_RESULT_JSON_BYTES)
            if expected_code == 'result_too_large':
                self.assertEqual(result['details']['original_status'],'succeeded' if outcome == 'succeeded' else 'failed')
                self.assertEqual(result['details']['original_error_code'],
                    None if outcome == 'succeeded' else 'validation_timeout' if outcome == 'timeout' else
                    'validation_output_too_large' if size > 2*1024*1024 else 'validation_failed')
                self.assertTrue(result['details']['original_details_omitted'])
            else:
                self.assertEqual(result['details']['exit_code'],7)
                self.assertEqual(result['details']['stdout'],'\0'*size)
                self.assertEqual(result['details']['stderr'],'\0'*size)
            # Restart with exactly the same Tasks and durable state.
            (self.repo/'sample.txt').write_bytes(b'recovery-sentinel\n')
            worker.process_once(self.mailbox,profile.transport_policy.branch,profile,self.state)
            self.assertEqual(execute.call_count,2,'recovery re-executed a completed task')
            self.assertEqual(receipt_path.read_bytes(),receipt_bytes)
            self.assertEqual((self.state/'outbox/LH9100.json').read_bytes(),result_bytes)
            self.assertEqual((self.repo/'sample.txt').read_bytes(),b'recovery-sentinel\n')

    def test_failed_validation_json_expansion_does_not_block_receipt_or_next_task(self):
        self._run_chain(1024*1024,'failed','result_too_large')

    def test_output_limit_failure_json_expansion_does_not_block_recovery(self):
        self._run_chain(2*1024*1024+1,'failed','result_too_large')

    def test_timeout_json_expansion_preserves_known_failure_and_prevents_replay(self):
        self._run_chain(1024*1024,'timeout','result_too_large')

    def test_small_failure_keeps_complete_diagnostics_and_recovery(self):
        self._run_chain(32,'failed','validation_failed')

    def test_successful_validation_with_unpublishable_output_is_indeterminate(self):
        self._run_chain(1024*1024,'succeeded','result_too_large')

    def test_oversized_success_payload_cannot_become_confirmed_execution_failure(self):
        profile = self._profile(32,'failed')
        task = self._task('LH9102','node.status',{})
        result = result_success(task,profile.node_id,{'large':'\0'*(2*1024*1024)},worker.build_provenance(profile))
        worker._persist_result(outbox=self.state/'outbox',receipts=self.state/'receipts',task=task,result=result)
        receipt = json.loads((self.state/'receipts/LH9102.json').read_text())
        pending = json.loads((self.state/'outbox/LH9102.json').read_text())
        self.assertEqual(receipt['result'],pending)
        self.assertEqual(pending['status'],'indeterminate')
        self.assertEqual(pending['error_code'],'result_too_large')
        self.assertEqual(pending['details']['original_status'],'succeeded')
        self.assertEqual(pending['task_digest'],task_digest(task))

    def test_remote_oversized_result_remains_rejected(self):
        profile = self._profile(32,'failed')
        task = self._task('LH9103','node.status',{})
        result = result_success(task,profile.node_id,{'large':'\0'*(2*1024*1024)},worker.build_provenance(profile))
        with self.assertRaises(LocalHandError) as raised:
            worker.validate_remote_result(result,task['task_id'],task['action'],profile.node_id,task_digest(task))
        self.assertEqual(raised.exception.code,'remote_result_invalid')
        self.assertEqual(raised.exception.status,'indeterminate')

    def test_invalid_local_identity_is_not_repaired_by_size_fallback(self):
        profile = self._profile(32,'failed')
        task = self._task('LH9104','node.status',{})
        result = result_success(task,profile.node_id,{'large':'\0'*(2*1024*1024)},worker.build_provenance(profile))
        result['task_digest'] = 'invalid'
        with self.assertRaises(LocalHandError) as raised:
            worker._persist_result(outbox=self.state/'outbox',receipts=self.state/'receipts',task=task,result=result)
        self.assertEqual(raised.exception.code,'result_invalid')
        self.assertFalse(self.state.exists())
