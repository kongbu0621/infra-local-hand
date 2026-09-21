"""Mailbox decisions must use the exact fetched, admitted branch commit."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest import mock

import test_local_hand_connect as connect_fixtures
from config_fixtures import profile_v2
from local_hand import worker
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError
from local_hand_connect import controller


@unittest.skipIf(os.name == 'nt', 'POSIX local Git fixtures; Windows deferred')
class FetchSnapshotChainTests(unittest.TestCase):
    def setUp(self):
        self.f = connect_fixtures.LocalHandConnectTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        environment = mock.patch.dict(os.environ, self.f.env, clear=False)
        environment.start()
        self.addCleanup(environment.stop)
        self.repo = self.f.root / 'projects/demo'
        self.repo.mkdir(parents=True)
        self.f._git(self.repo, 'init', '-q')
        (self.repo / 'sample.txt').write_bytes(b'before\n')
        value = profile_v2({'node_id': 'fixture-windows-node', 'projects_root': str(self.repo.parent),
            'repositories': {'demo': {'path': 'demo', 'single_writer': True, 'validations': {}}}})
        value['transport_policy'] = self.f.policy.as_dict()
        path = self.f.root / 'profile.json'
        path.write_text(json.dumps(value))
        self.profile = load_profile(path)
        self.state = self.f.root / 'state'

    def _disable_tracking(self, *, remove_ref=False):
        self.f._git(self.f.mailbox, 'config', '--unset-all', 'remote.origin.fetch')
        if remove_ref:
            self.f._git(self.f.mailbox, 'update-ref', '-d', 'refs/remotes/origin/' + self.f.branch)

    def _publish_task(self, task_id):
        task = self.f._task(task_id=task_id, action='fs.write_text_cas', params={
            'repository': 'demo', 'relative_path': 'sample.txt',
            'expected_sha256': hashlib.sha256(b'before\n').hexdigest(), 'content': 'after\n'})
        relative = '_executor_spike/tasks/' + task_id + '.json'
        (self.f.seed / relative).write_text(json.dumps(task) + '\n')
        self.f._git(self.f.seed, 'add', '--', relative)
        self.f._git(self.f.seed, 'commit', '-qm', 'committed fixture task')
        self.f._git(self.f.seed, 'push', 'origin', 'HEAD:refs/heads/' + self.f.branch)
        return task

    def test_controller_reads_fetched_result_when_tracking_ref_is_stale(self):
        task = self.f._task(task_id='LH9400')
        controller.submit_task(self.f.mailbox, self.f.branch, task)
        self._disable_tracking()
        self.f._publish_result(task)
        result = controller.wait_for_result(self.f.mailbox, self.f.branch, task,
            timeout_seconds=0, expected_provenance=self.f.expected_provenance)
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['details'], {'connected': True})

    def test_controller_submit_reconciles_without_tracking_ref(self):
        self._disable_tracking(remove_ref=True)
        task = self.f._task(task_id='LH9401')
        first = controller.submit_task(self.f.mailbox, self.f.branch, task)
        second = controller.submit_task(self.f.mailbox, self.f.branch, task)
        self.assertEqual(first['status'], 'submitted')
        self.assertEqual(second['status'], 'already_present')
        self.assertEqual(first['task_digest'], second['task_digest'])
        committed = self.f._git(self.f.root, '--git-dir', str(self.f.remote), 'show',
            'refs/heads/' + self.f.branch + ':_executor_spike/tasks/LH9401.json').stdout
        self.assertEqual(json.loads(committed), task)

    def test_worker_executes_fetched_task_without_tracking_mapping(self):
        self._disable_tracking()
        task = self._publish_task('LH9402')
        worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
        self.assertEqual((self.repo / 'sample.txt').read_bytes(), b'after\n')
        receipt = json.loads((self.state / 'receipts/LH9402.json').read_text())
        remote = json.loads(self.f._git(self.f.root, '--git-dir', str(self.f.remote), 'show',
            'refs/heads/' + self.f.branch + ':_executor_spike/results/LH9402.json').stdout)
        self.assertEqual(remote, receipt['result'])
        self.assertEqual(remote['task_id'], task['task_id'])
        self.assertEqual(remote['status'], 'succeeded')

    def test_missing_branch_cannot_be_replaced_by_same_named_tag(self):
        worker.sync_mailbox(self.f.mailbox, self.f.branch)
        initial = self.f._git(self.f.seed, 'rev-parse', 'HEAD').stdout.strip()
        self.f._git(self.f.root, '--git-dir', str(self.f.remote), 'update-ref', 'refs/tags/' + self.f.branch, initial)
        self.f._git(self.f.root, '--git-dir', str(self.f.remote), 'update-ref', '-d', 'refs/heads/' + self.f.branch)
        with self.assertRaises(LocalHandError):
            worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
        self.assertEqual((self.repo / 'sample.txt').read_bytes(), b'before\n')
        self.assertFalse(list((self.state / 'receipts').glob('*.json')))

    def test_branch_wins_over_same_named_tag_without_tracking_mapping(self):
        initial = self.f._git(self.f.seed, 'rev-parse', 'HEAD').stdout.strip()
        self.f._git(self.f.root, '--git-dir', str(self.f.remote), 'update-ref', 'refs/tags/' + self.f.branch, initial)
        self._disable_tracking()
        self._publish_task('LH9403')
        worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
        self.assertEqual((self.repo / 'sample.txt').read_bytes(), b'after\n')
        self.assertEqual(json.loads((self.state / 'receipts/LH9403.json').read_text())['status'], 'succeeded')

    def test_fetched_tree_is_admitted_even_when_tracking_ref_is_old(self):
        self._disable_tracking()
        relative = '_executor_spike/tasks/LH9404.json'
        (self.f.seed / relative).symlink_to('../../../outside.json')
        self.f._git(self.f.seed, 'add', '--', relative)
        self.f._git(self.f.seed, 'commit', '-qm', 'invalid remote control tree fixture')
        self.f._git(self.f.seed, 'push', 'origin', 'HEAD:refs/heads/' + self.f.branch)
        with self.assertRaises(LocalHandError) as raised:
            worker.sync_mailbox(self.f.mailbox, self.f.branch)
        self.assertEqual(raised.exception.code, 'mailbox_symlink_rejected')
        self.assertFalse((self.f.mailbox / relative).is_symlink())

    def _outbox_scan_failure(self, failure):
        outbox = self.state / 'outbox'
        original_scandir, original_listdir = os.scandir, os.listdir
        def wrap(original):
            def scan(path):
                if not isinstance(path, int) and Path(path) == outbox:
                    raise failure
                return original(path)
            return scan
        first = mock.patch.object(os, 'scandir', side_effect=wrap(original_scandir))
        second = mock.patch.object(os, 'listdir', side_effect=wrap(original_listdir))
        return first, second

    def test_unreadable_outbox_stops_before_new_task_execution(self):
        self._publish_task('LH9405')
        first, second = self._outbox_scan_failure(PermissionError('fixture outbox unreadable'))
        with first, second:
            with self.assertRaises(LocalHandError) as raised:
                worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
        self.assertEqual(raised.exception.code, 'local_outbox_unreadable')
        self.assertEqual(raised.exception.status, 'indeterminate')
        self.assertEqual((self.repo / 'sample.txt').read_bytes(), b'before\n')
        self.assertFalse((self.state / 'receipts/LH9405.json').exists())

    def test_failed_outbox_scan_preserves_pending_result_and_retries_without_replay(self):
        task = self._publish_task('LH9406')
        result = worker.execute_task(task, self.profile, self.state)
        worker._persist_result(outbox=self.state/'outbox', receipts=self.state/'receipts', task=task, result=result)
        pending = self.state / 'outbox/LH9406.json'
        receipt = self.state / 'receipts/LH9406.json'
        pending_bytes, receipt_bytes = pending.read_bytes(), receipt.read_bytes()
        (self.repo / 'sample.txt').write_bytes(b'recovery-sentinel\n')
        first, second = self._outbox_scan_failure(OSError('fixture outbox I/O failure'))
        with first, second:
            with self.assertRaises(LocalHandError) as raised:
                worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
        self.assertEqual(raised.exception.code, 'local_outbox_unreadable')
        self.assertEqual(raised.exception.status, 'indeterminate')
        self.assertEqual(pending.read_bytes(), pending_bytes)
        self.assertEqual(receipt.read_bytes(), receipt_bytes)
        worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
        self.assertFalse(pending.exists())
        self.assertEqual(receipt.read_bytes(), receipt_bytes)
        self.assertEqual((self.repo / 'sample.txt').read_bytes(), b'recovery-sentinel\n')
