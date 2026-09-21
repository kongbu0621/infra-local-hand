"""A reset return code alone does not establish committed mailbox evidence."""
from __future__ import annotations
import hashlib
import json
import os
import unittest
from unittest import mock
from local_hand import worker
from local_hand.protocol import conflict_filename, task_digest
from local_hand_connect import controller
from test_local_hand_state_lookup_chain import StateLookupChainTests

@unittest.skipIf(os.name == 'nt', 'POSIX local Git fixtures; Windows deferred')
class ResetResidueChainTests(unittest.TestCase):
    def setUp(self):
        self.chain = StateLookupChainTests()
        self.chain.setUp()
        self.addCleanup(self.chain.doCleanups)

    def _leave_residue_after_reset(self, relative, payload):
        original = worker.run_git
        self.injected = 0
        def run(args, cwd, **kwargs):
            result = original(args, cwd, **kwargs)
            if args[:2] == ['reset', '--hard'] and args[2] != 'HEAD' and not self.injected:
                target = cwd / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                self.injected += 1
            return result
        return mock.patch.object(worker, 'run_git', side_effect=run)

    def _assert_archived(self, relative, payload):
        self.assertEqual(self.injected, 1)
        records = list((self.chain.f.mailbox / '.git/local-hand-untracked').glob('*/record.json'))
        matched = [path for path in records if json.loads(path.read_text())['relative_path'] == relative]
        self.assertEqual(len(matched), 1)
        self.assertEqual((matched[0].parent/'payload').read_bytes(), payload)

    def test_uncommitted_task_left_after_reset_is_preserved_without_execution(self):
        c = self.chain
        task = c.f._task(task_id='LH9700', action='fs.write_text_cas', params={
            'repository':'demo', 'relative_path':'sample.txt',
            'expected_sha256':hashlib.sha256(b'before\n').hexdigest(), 'content':'after\n'})
        relative = '_executor_spike/tasks/LH9700.json'
        payload = (json.dumps(task)+'\n').encode()
        with self._leave_residue_after_reset(relative, payload), mock.patch.object(worker, 'execute_task', wraps=worker.execute_task) as execute:
            worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
        self.assertEqual(execute.call_count, 0, 'uncommitted reset residue was executed')
        self.assertEqual((c.repo/'sample.txt').read_bytes(), b'before\n')
        self.assertFalse((c.state/'receipts/LH9700.json').exists())
        self._assert_archived(relative, payload)

    def test_conflict_reset_residue_cannot_substitute_for_remote_publication(self):
        c = self.chain
        task = c._submit('LH9701')
        worker._quarantine_task_conflict(state_root=c.state, outbox=c.state/'outbox',
            task=task, profile=c.profile, code='outcome_unknown', message='fixture replay barrier',
            observed_digest=None, status='indeterminate')
        name = conflict_filename(task_digest(task));relative = '_executor_spike/conflicts/'+name
        saved = (c.state/'conflicts'/name).read_bytes()
        worker.publish_outbox(c.f.mailbox, c.f.branch, c.state/'outbox')
        c._remove_remote(relative)
        with self._leave_residue_after_reset(relative, saved), mock.patch.object(worker, 'execute_task', side_effect=AssertionError('blocked task replayed')):
            worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
        committed = c.f._git(c.f.root, '--git-dir', str(c.f.remote), 'show', 'refs/heads/'+c.f.branch+':'+relative)
        self.assertEqual(json.loads(committed.stdout), json.loads(saved))
        actual = controller.wait_for_result(c.f.mailbox, c.f.branch, task, timeout_seconds=0,
            expected_provenance=worker.build_provenance(c.profile))
        self.assertEqual(actual, json.loads(saved))
        self.assertFalse((c.state/'receipts/LH9701.json').exists())
        self.assertEqual((c.repo/'sample.txt').read_bytes(), b'before\n')
        self._assert_archived(relative, saved)
