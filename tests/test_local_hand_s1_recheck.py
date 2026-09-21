"""Regression cases from GX10 fault injection and v1 contract comparison."""
from __future__ import annotations

import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from config_fixtures import profile_v2
from local_hand import act, worker
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError, task_digest
from local_hand_connect import controller


class S1RecheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'projects/demo'
        self.repo.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.target = self.repo / 'sample.txt'
        self.target.write_bytes(b'before\n')
        data = profile_v2({'node_id': 'recheck-fixture', 'projects_root': str(self.repo.parent),
                          'repositories': {'demo': {'path': 'demo', 'single_writer': True, 'validations': {}}}})
        path = self.root / 'profile.json'
        path.write_text(json.dumps(data))
        self.profile = load_profile(path)
        self.state = self.root / 'state'

    def task(self, action='fs.write_text_cas'):
        return {'schema_version': 'local-hand-task/v1', 'task_id': 'LH7711',
                'target_node': self.profile.node_id, 'action': action,
                'params': {'repository': 'demo', 'relative_path': 'sample.txt',
                           'expected_sha256': hashlib.sha256(b'before\n').hexdigest(),
                           'content': 'after\n'} if action == 'fs.write_text_cas' else {}}

    def mailbox(self, task):
        box = self.root / 'mailbox'
        for name in ('tasks', 'results', 'conflicts'):
            (box / '_executor_spike' / name).mkdir(parents=True)
        (box / '_executor_spike/tasks' / (task['task_id'] + '.json')).write_text(json.dumps(task))
        return box

    @unittest.skipIf(os.name == 'nt', 'POSIX directory fsync')
    def test_cas_directory_fsync_failure_is_indeterminate_after_replace(self):
        original = os.fsync
        injected = []
        def fail(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                injected.append(True)
                raise OSError(errno.EIO, 'injected directory fsync failure')
            return original(fd)
        with mock.patch.object(act.os, 'fsync', side_effect=fail):
            with self.assertRaises(LocalHandError) as ctx:
                worker.execute_task(self.task(), self.profile, self.state)
        self.assertTrue(injected)
        self.assertEqual(ctx.exception.status, 'indeterminate')
        self.assertEqual(ctx.exception.code, 'write_durability_unconfirmed')
        self.assertEqual(self.target.read_bytes(), b'after\n')

    def test_cas_readback_failures_are_indeterminate_after_replace(self):
        for failure in (OSError(errno.EIO, 'read-back failure'),
                        LocalHandError('write_source_too_large', 'over-limit read-back')):
            with self.subTest(failure=type(failure).__name__):
                self.target.write_bytes(b'before\n')
                with mock.patch.object(act, '_read_cas_target', side_effect=[b'before\n', b'before\n', failure]):
                    with self.assertRaises(LocalHandError) as ctx:
                        worker.execute_task(self.task(), self.profile, self.state)
                self.assertEqual(ctx.exception.status, 'indeterminate')
                self.assertEqual(ctx.exception.code, 'write_readback_unconfirmed')
                self.assertEqual(self.target.read_bytes(), b'after\n')

    def test_cas_readback_mismatch_remains_indeterminate(self):
        with mock.patch.object(act, '_read_cas_target', side_effect=[b'before\n', b'before\n', b'other\n']):
            with self.assertRaises(LocalHandError) as ctx:
                worker.execute_task(self.task(), self.profile, self.state)
        self.assertEqual(ctx.exception.status, 'indeterminate')
        self.assertEqual(ctx.exception.code, 'write_readback_mismatch')
        self.assertEqual(self.target.read_bytes(), b'after\n')

    def test_cas_temp_fsync_failure_has_no_replacement(self):
        with mock.patch.object(act.os, 'fsync', side_effect=OSError(errno.EIO, 'temp sync failure')):
            with self.assertRaises(OSError):
                worker.execute_task(self.task(), self.profile, self.state)
        self.assertEqual(self.target.read_bytes(), b'before\n')
        self.assertEqual(list(self.repo.glob('.sample.txt.local-hand-*')), [])

    @unittest.skipIf(os.name == 'nt', 'POSIX mode preservation semantics')
    def test_cas_mode_preservation_failure_has_no_replacement(self):
        before = self.target.read_bytes()
        self.target.chmod(0o755)
        with mock.patch.object(act.os, 'chmod', side_effect=OSError(errno.EPERM, 'injected chmod failure')):
            with self.assertRaises(LocalHandError) as ctx:
                worker.execute_task(self.task(), self.profile, self.state)
        self.assertEqual(ctx.exception.code, 'write_mode_preservation_failed')
        self.assertEqual(ctx.exception.status, 'failed')
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o755)
        self.assertEqual(list(self.repo.glob('.sample.txt.local-hand-*')), [])

    @unittest.skipIf(os.name == 'nt', 'POSIX directory fsync')
    def test_post_write_indeterminate_receipt_prevents_duplicate_replay(self):
        task = self.task()
        box = self.mailbox(task)
        original = os.fsync
        target_identity = (self.repo.stat().st_dev, self.repo.stat().st_ino)
        def fail_target_directory(fd):
            info = os.fstat(fd)
            if stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == target_identity:
                raise OSError(errno.EIO, 'target directory sync failure')
            return original(fd)
        with mock.patch.object(worker, 'validate_worker_mailbox'), mock.patch.object(worker, 'publish_outbox'), mock.patch.object(worker, 'sync_mailbox'):
            with mock.patch.object(act.os, 'fsync', side_effect=fail_target_directory):
                worker.process_once(box, self.profile.transport_policy.branch, self.profile, self.state)
            receipt = json.loads((self.state / 'receipts/LH7711.json').read_text())
            self.assertEqual(receipt['result']['status'], 'indeterminate')
            self.assertEqual(receipt['result']['error_code'], 'write_durability_unconfirmed')
            self.target.write_bytes(b'changed-after-first-run\n')
            with mock.patch.object(worker, 'execute_task') as execute:
                worker.process_once(box, self.profile.transport_policy.branch, self.profile, self.state)
                execute.assert_not_called()
        self.assertEqual(self.target.read_bytes(), b'changed-after-first-run\n')
        result = json.loads((self.state / 'outbox/LH7711.json').read_text())
        self.assertEqual(result, receipt['result'])

    def test_remote_result_repairs_pre_execution_intent_receipt(self):
        task = self.task('node.status')
        box = self.mailbox(task)
        result = worker.result_success(task, self.profile.node_id, {'fixture': True}, worker.build_provenance(self.profile))
        (box/'_executor_spike/results/LH7711.json').write_text(json.dumps(result))
        receipt_path = self.state/'receipts/LH7711.json'
        receipt_path.parent.mkdir(parents=True)
        receipt_path.write_text(json.dumps({'task_id':task['task_id'],'task_digest':task_digest(task),
                                            'source':'local_execution_started'}))
        with mock.patch.object(worker,'validate_worker_mailbox'), mock.patch.object(worker,'publish_outbox'), mock.patch.object(worker,'sync_mailbox'), mock.patch.object(worker,'execute_task') as execute:
            worker.process_once(box,self.profile.transport_policy.branch,self.profile,self.state)
            execute.assert_not_called()
        repaired=json.loads(receipt_path.read_text())
        self.assertEqual(repaired['source'],'remote_result_recovery')
        self.assertEqual(repaired['result'],result)

    def test_remote_result_content_conflict_preserves_receipt_and_isolates(self):
        task = self.task('node.status')
        box = self.mailbox(task)
        local = worker.result_success(task,self.profile.node_id,{'source':'local'},worker.build_provenance(self.profile))
        remote = worker.result_success(task,self.profile.node_id,{'source':'remote'},worker.build_provenance(self.profile))
        (box/'_executor_spike/results/LH7711.json').write_text(json.dumps(remote))
        receipt_path=self.state/'receipts/LH7711.json';receipt_path.parent.mkdir(parents=True)
        receipt_path.write_text(json.dumps({'task_id':task['task_id'],'task_digest':task_digest(task),'result':local}))
        with mock.patch.object(worker,'validate_worker_mailbox'), mock.patch.object(worker,'publish_outbox'), mock.patch.object(worker,'sync_mailbox'), mock.patch.object(worker,'execute_task') as execute:
            worker.process_once(box,self.profile.transport_policy.branch,self.profile,self.state)
            execute.assert_not_called()
        self.assertEqual(json.loads(receipt_path.read_text())['result'],local)
        conflicts=list((self.state/'conflicts').glob('CONFLICT-*.json'))
        self.assertEqual(len(conflicts),1)
        conflict=json.loads(conflicts[0].read_text())
        self.assertEqual(conflict['error_code'],'remote_result_content_conflict')
        self.assertNotEqual(conflict['details']['local_result_sha256'],conflict['details']['remote_result_sha256'])

    def test_unknown_task_fields_rejected_on_both_sides_before_write(self):
        for field in ('unknown', 'authorization', 'model', 'shell'):
            task = {**self.task(), field: 'unadmitted'}
            for validate in (worker.validate_task, controller._validate_controller_task):
                with self.subTest(field=field, validator=validate.__name__), self.assertRaises(LocalHandError):
                    validate(task)
            with self.assertRaises(LocalHandError):
                worker.execute_task(task, self.profile, self.state)
        self.assertEqual(self.target.read_bytes(), b'before\n')
        self.assertFalse(self.state.exists())

    def test_wrong_target_unknown_fields_still_ignored(self):
        task = {**self.task(), 'target_node': 'other-node', 'unknown': True, 'params': None}
        self.assertIsNone(worker.execute_task(task, self.profile, self.state))
        self.assertFalse(self.state.exists())

    def test_unknown_task_fields_get_digest_bound_durable_rejection(self):
        task = {**self.task(), 'unknown': True}
        box = self.mailbox(task)
        with mock.patch.object(worker, 'validate_worker_mailbox'), mock.patch.object(worker, 'publish_outbox'), mock.patch.object(worker, 'sync_mailbox'), mock.patch.object(worker, 'execute_task') as execute:
            worker.process_once(box, self.profile.transport_policy.branch, self.profile, self.state)
            execute.assert_not_called()
        result = json.loads((self.state / 'outbox/LH7711.json').read_text())
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(result['task_digest'], task_digest(task))
        self.assertEqual(self.target.read_bytes(), b'before\n')

    def test_result_shape_and_error_semantics_match_both_ingresses(self):
        task = self.task('node.status')
        result = worker.result_success(task, self.profile.node_id, {}, worker.build_provenance(self.profile))
        invalid = []
        for key in result:
            value = copy.deepcopy(result)
            value.pop(key)
            invalid.append(value)
        for key, value in (('extra', True), ('details', None), ('details', []), ('status', []),
                           ('error', 'unexpected'), ('error_code', 'unexpected'), ('status', 'failed')):
            invalid.append({**result, key: value})
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(LocalHandError):
                    worker.validate_remote_result(value, task['task_id'])
                with self.assertRaises(LocalHandError):
                    controller._validate_controller_result(value, task)
        for status in ('failed', 'rejected', 'stale', 'indeterminate'):
            value = worker.result_error(task, self.profile.node_id, LocalHandError('fixture_error', 'fixture message', status), worker.build_provenance(self.profile))
            self.assertEqual(worker.validate_remote_result(value, task['task_id']), value)
            self.assertEqual(controller._validate_controller_result(value, task), value)
