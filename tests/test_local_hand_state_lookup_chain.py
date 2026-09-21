"""A failed metadata lookup must not erase an existing replay barrier."""
from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest import mock

import test_local_hand_connect as connect_fixtures
from config_fixtures import profile_v2
from local_hand import mailbox_safety, worker
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError, conflict_filename, task_digest
from local_hand_connect import controller


@unittest.skipIf(os.name == 'nt', 'POSIX local Git fixtures; Windows deferred')
class StateLookupChainTests(unittest.TestCase):
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

    def _submit(self, task_id):
        task = self.f._task(task_id=task_id, action='fs.write_text_cas', params={
            'repository': 'demo', 'relative_path': 'sample.txt',
            'expected_sha256': hashlib.sha256(b'before\n').hexdigest(), 'content': 'after\n'})
        controller.submit_task(self.f.mailbox, self.f.branch, task)
        return task

    def _lookup_failure(self, target, number=errno.EIO):
        original = os.lstat
        def lookup(path, *args, **kwargs):
            if not isinstance(path, int) and Path(path) == target:
                raise OSError(number, 'fixture metadata lookup failure', os.fspath(path))
            return original(path, *args, **kwargs)
        return mock.patch.object(os, 'lstat', side_effect=lookup)

    def _assert_unavailable(self, exc):
        self.assertIsInstance(exc, LocalHandError)
        self.assertEqual(exc.code, 'path_state_unavailable')
        self.assertEqual(exc.status, 'indeterminate')

    def _remove_remote(self, relative):
        self.f._git(self.f.seed, 'fetch', 'origin', self.f.branch)
        self.f._git(self.f.seed, 'reset', '--hard', 'FETCH_HEAD')
        self.f._git(self.f.seed, 'rm', '--', relative)
        self.f._git(self.f.seed, 'commit', '-qm', 'remove fixture evidence to test local recovery')
        self.f._git(self.f.seed, 'push', 'origin', 'HEAD:refs/heads/' + self.f.branch)

    def test_receipt_lookup_error_never_reexecutes_completed_task(self):
        self._submit('LH9500')
        worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
        receipt = self.state / 'receipts/LH9500.json'
        saved = receipt.read_bytes()
        self._remove_remote('_executor_spike/results/LH9500.json')
        # Restoring the original input makes an illicit second CAS observable.
        (self.repo / 'sample.txt').write_bytes(b'before\n')
        failure = None
        with self._lookup_failure(receipt), mock.patch.object(worker, 'execute_task', wraps=worker.execute_task) as execute:
            try:
                worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
            except LocalHandError as exc:
                failure = exc
        self.assertEqual(execute.call_count, 0, 'a completed task was executed again')
        self._assert_unavailable(failure)
        self.assertEqual(receipt.read_bytes(), saved)
        self.assertEqual((self.repo / 'sample.txt').read_bytes(), b'before\n')
        worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
        self.assertEqual(receipt.read_bytes(), saved)
        self.assertEqual((self.repo / 'sample.txt').read_bytes(), b'before\n')
        self.assertEqual(json.loads((self.f.mailbox / '_executor_spike/results/LH9500.json').read_text()), json.loads(saved)['result'])

    def test_conflict_lookup_error_never_executes_blocked_task(self):
        task = self._submit('LH9501')
        worker._quarantine_task_conflict(state_root=self.state, outbox=self.state/'outbox',
            task=task, profile=self.profile, code='outcome_unknown', message='fixture replay barrier',
            observed_digest=None, status='indeterminate')
        marker = self.state / 'conflicts' / conflict_filename(task_digest(task))
        saved = marker.read_bytes()
        worker.publish_outbox(self.f.mailbox, self.f.branch, self.state/'outbox')
        self._remove_remote('_executor_spike/conflicts/' + marker.name)
        failure = None
        with self._lookup_failure(marker, errno.EACCES), mock.patch.object(worker, 'execute_task', wraps=worker.execute_task) as execute:
            try:
                worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
            except LocalHandError as exc:
                failure = exc
        self.assertEqual(execute.call_count, 0, 'a conflict-blocked task was executed')
        self._assert_unavailable(failure)
        self.assertEqual(marker.read_bytes(), saved)
        self.assertFalse((self.state/'receipts/LH9501.json').exists())
        worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
        self.assertEqual((self.repo/'sample.txt').read_bytes(), b'before\n')
        self.assertEqual((self.f.mailbox/'_executor_spike/conflicts'/marker.name).read_bytes(), saved)

    def test_remote_result_lookup_error_preserves_pending_result(self):
        self._submit('LH9502')
        worker.process_once(self.f.mailbox, self.f.branch, self.profile, self.state)
        target = self.f.mailbox / '_executor_spike/results/LH9502.json'
        pending = self.state / 'outbox/LH9502.json'
        pending.write_bytes(target.read_bytes())
        saved = pending.read_bytes()
        with self._lookup_failure(target), self.assertRaises(LocalHandError) as raised:
            worker.publish_outbox(self.f.mailbox, self.f.branch, self.state/'outbox')
        self._assert_unavailable(raised.exception)
        self.assertEqual(pending.read_bytes(), saved)
        worker.publish_outbox(self.f.mailbox, self.f.branch, self.state/'outbox')
        self.assertFalse(pending.exists())
        self.assertEqual(target.read_bytes(), saved)

    def test_quarantine_lookup_error_does_not_overwrite_prior_evidence(self):
        outbox = self.state / 'outbox'
        outbox.mkdir(parents=True)
        quarantine = self.state / 'quarantine'
        quarantine.mkdir()
        pending = outbox / 'LH9503.json'
        pending.write_bytes(b'new invalid evidence')
        reason = 'fixture invalid record'
        prior = quarantine / (pending.name + '.' + hashlib.sha256(reason.encode()).hexdigest()[:12] + '.invalid')
        prior.write_bytes(b'prior invalid evidence')
        failure = None
        with self._lookup_failure(prior):
            try:
                worker._quarantine_local_outbox_file(outbox, pending, reason)
            except LocalHandError as exc:
                failure = exc
        self.assertEqual(prior.read_bytes(), b'prior invalid evidence')
        self.assertEqual(pending.read_bytes(), b'new invalid evidence')
        self._assert_unavailable(failure)
        worker._quarantine_local_outbox_file(outbox, pending, reason)
        self.assertEqual(prior.read_bytes(), b'prior invalid evidence')
        self.assertEqual(prior.with_name(prior.stem + '.1.invalid').read_bytes(), b'new invalid evidence')

    def test_controller_does_not_skip_unreadable_conflict(self):
        task = self._submit('LH9504')
        worker._quarantine_task_conflict(state_root=self.state, outbox=self.state/'outbox',
            task=task, profile=self.profile, code='outcome_unknown', message='fixture conflict',
            observed_digest=None, status='indeterminate')
        worker.publish_outbox(self.f.mailbox, self.f.branch, self.state/'outbox')
        marker = self.f.mailbox/'_executor_spike/conflicts'/conflict_filename(task_digest(task))
        with self._lookup_failure(marker), self.assertRaises(LocalHandError) as raised:
            controller.wait_for_result(self.f.mailbox, self.f.branch, task,
                timeout_seconds=0, expected_provenance=worker.build_provenance(self.profile))
        self._assert_unavailable(raised.exception)

    def test_absence_dangling_link_and_lookup_failures_are_distinct(self):
        target = self.f.root/'lookup-target'
        self.assertFalse(mailbox_safety.target_lexists(target))
        target.symlink_to(self.f.root/'missing-destination')
        self.assertTrue(mailbox_safety.target_lexists(target))
        for number in (errno.EIO, errno.EACCES, errno.ENOTDIR):
            with self.subTest(errno=number), self._lookup_failure(target, number):
                with self.assertRaises(LocalHandError) as raised:
                    mailbox_safety.target_lexists(target)
                self._assert_unavailable(raised.exception)
                self.assertEqual(raised.exception.__cause__.errno, number)
