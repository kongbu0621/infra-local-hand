"""Interrupted control-file publication must not manufacture remote evidence."""
from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import unittest
from unittest import mock

import test_local_hand_connect as connect_fixtures
from config_fixtures import profile_v2
from local_hand import mailbox_safety, worker
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError, result_success
from local_hand_connect import controller


@unittest.skipIf(os.name == 'nt', 'POSIX fault and local Git fixtures; Windows deferred')
class UntrackedMailboxChainTests(unittest.TestCase):
    def setUp(self):
        self.fixture = connect_fixtures.LocalHandConnectTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.f = self.fixture
        self.env = mock.patch.dict(os.environ,self.f.env,clear=False)
        self.env.start();self.addCleanup(self.env.stop)
        self.repo = self.f.root/'projects/demo';self.repo.mkdir(parents=True)
        self.f._git(self.repo,'init','-q')
        (self.repo/'sample.txt').write_bytes(b'before\n')
        value=profile_v2({'node_id':'fixture-windows-node','projects_root':str(self.repo.parent),
            'transport_policy':self.f.policy.as_dict(),
            'repositories':{'demo':{'path':'demo','single_writer':True,'validations':{}}}})
        value['transport_policy']=self.f.policy.as_dict()
        path=self.f.root/'profile.json';path.write_text(json.dumps(value))
        self.profile=load_profile(path);self.state=self.f.root/'state'

    def _remote_has(self, relative):
        return bool(self.f._git(self.f.root,'--git-dir',str(self.f.remote),'ls-tree','--name-only',self.f.branch,'--',relative).stdout.strip())

    def _assert_preserved(self, relative, data):
        records=list((self.f.mailbox/'.git/local-hand-untracked').glob('*/record.json'))
        matches=[]
        for path in records:
            record=json.loads(path.read_text())
            if record['relative_path']==relative:
                self.assertEqual(record['sha256'],hashlib.sha256(data).hexdigest())
                self.assertEqual(record['bytes'],len(data))
                self.assertEqual((path.parent/'payload').read_bytes(),data)
                matches.append(path)
        self.assertEqual(len(matches),1)

    def _cas(self, task_id):
        return self.f._task(task_id=task_id,action='fs.write_text_cas',params={
            'repository':'demo','relative_path':'sample.txt',
            'expected_sha256':hashlib.sha256(b'before\n').hexdigest(),'content':'after\n'})

    def test_submit_after_local_file_creation_must_really_publish(self):
        task=self.f._task(task_id='LH9300')
        rel='_executor_spike/tasks/LH9300.json';raw=(json.dumps(task)+'\n').encode()
        (self.f.mailbox/rel).write_bytes(raw)
        self.assertFalse(self._remote_has(rel))
        submitted=controller.submit_task(self.f.mailbox,self.f.branch,task)
        self.assertEqual(submitted['status'],'submitted')
        self.assertTrue(self._remote_has(rel),'local leftover was mistaken for remote delivery')
        self._assert_preserved(rel,raw)

    def test_wait_cannot_accept_an_uncommitted_local_result(self):
        task=self.f._task(task_id='LH9301')
        controller.submit_task(self.f.mailbox,self.f.branch,task)
        result=result_success(task,task['target_node'],{'local_only':True},self.f.expected_provenance)
        rel='_executor_spike/results/LH9301.json';raw=(json.dumps(result)+'\n').encode()
        (self.f.mailbox/rel).write_bytes(raw)
        with self.assertRaises(LocalHandError) as raised:
            controller.wait_for_result(self.f.mailbox,self.f.branch,task,timeout_seconds=0,
                expected_provenance=self.f.expected_provenance)
        self.assertEqual(raised.exception.code,'controller_wait_timeout')
        self.assertEqual(raised.exception.status,'indeterminate')
        self.assertFalse(self._remote_has(rel))
        self._assert_preserved(rel,raw)

    def test_worker_does_not_execute_an_uncommitted_local_task(self):
        task=self._cas('LH9302');rel='_executor_spike/tasks/LH9302.json'
        raw=(json.dumps(task)+'\n').encode();(self.f.mailbox/rel).write_bytes(raw)
        worker.process_once(self.f.mailbox,self.f.branch,self.profile,self.state)
        self.assertEqual((self.repo/'sample.txt').read_bytes(),b'before\n')
        self.assertFalse((self.state/'receipts/LH9302.json').exists())
        self.assertFalse(self._remote_has('_executor_spike/results/LH9302.json'))
        self._assert_preserved(rel,raw)

    def test_ignored_local_task_is_preserved_and_unrelated_file_is_untouched(self):
        task=self._cas('LH9306');rel='_executor_spike/tasks/LH9306.json'
        raw=(json.dumps(task)+'\n').encode();(self.f.mailbox/rel).write_bytes(raw)
        with (self.f.mailbox/'.git/info/exclude').open('a') as stream:
            stream.write('\n_executor_spike/tasks/LH9306.json\n')
        note=self.f.mailbox/'unrelated-note.txt';note.write_bytes(b'keep this local file\n')
        worker.process_once(self.f.mailbox,self.f.branch,self.profile,self.state)
        self.assertEqual((self.repo/'sample.txt').read_bytes(),b'before\n')
        self.assertFalse((self.state/'receipts/LH9306.json').exists())
        self.assertEqual(note.read_bytes(),b'keep this local file\n')
        self._assert_preserved(rel,raw)

    def test_archive_symlink_is_rejected_without_moving_original(self):
        task=self.f._task(task_id='LH9307');rel='_executor_spike/tasks/LH9307.json'
        raw=(json.dumps(task)+'\n').encode();(self.f.mailbox/rel).write_bytes(raw)
        outside=self.f.root/'outside';outside.mkdir()
        (self.f.mailbox/'.git/local-hand-untracked').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(LocalHandError) as raised:
            worker.sync_mailbox(self.f.mailbox,self.f.branch)
        self.assertEqual(raised.exception.code,'mailbox_untracked_preservation_failed')
        self.assertEqual((self.f.mailbox/rel).read_bytes(),raw)
        self.assertEqual(list(outside.iterdir()),[])

    def test_worker_retains_and_publishes_outbox_after_precommit_interruption(self):
        task=self._cas('LH9303');controller.submit_task(self.f.mailbox,self.f.branch,task)
        result=worker.execute_task(task,self.profile,self.state)
        worker._persist_result(outbox=self.state/'outbox',receipts=self.state/'receipts',task=task,result=result)
        receipt=(self.state/'receipts/LH9303.json').read_bytes()
        raw=(self.state/'outbox/LH9303.json').read_bytes();rel='_executor_spike/results/LH9303.json'
        (self.f.mailbox/rel).write_bytes(raw)
        (self.repo/'sample.txt').write_bytes(b'recovery-sentinel\n')
        worker.process_once(self.f.mailbox,self.f.branch,self.profile,self.state)
        self.assertTrue(self._remote_has(rel),'outbox was discarded without remote publication')
        remote=self.f._git(self.f.root,'--git-dir',str(self.f.remote),'show',self.f.branch+':'+rel).stdout
        self.assertEqual(json.loads(remote),result)
        self.assertEqual((self.state/'receipts/LH9303.json').read_bytes(),receipt)
        self.assertFalse(mailbox_safety.target_lexists(self.state/'outbox/LH9303.json'))
        self.assertEqual((self.repo/'sample.txt').read_bytes(),b'recovery-sentinel\n')
        self._assert_preserved(rel,raw)

    def _failed_temp_write(self, operation):
        target=self.f.mailbox/'_executor_spike/tasks/LH9304.json'
        with mock.patch.object(mailbox_safety.os,operation,side_effect=OSError(errno.EIO,'fixture local I/O failure')):
            with self.assertRaises((OSError,LocalHandError)) as raised:
                mailbox_safety.atomic_create_control_file(self.f.mailbox,target,b'payload')
        self.assertFalse(target.exists())
        self.assertFalse(list(target.parent.glob('.lh-*.tmp')),'owned temporary file blocks retry in the same process')
        self.assertIsInstance(raised.exception,LocalHandError)
        self.assertEqual(raised.exception.status,'indeterminate')
        mailbox_safety.atomic_create_control_file(self.f.mailbox,target,b'payload')
        self.assertEqual(target.read_bytes(),b'payload')

    def test_failed_write_cleans_only_owned_temp_and_allows_retry(self):
        self._failed_temp_write('write')

    def test_failed_file_sync_cleans_only_owned_temp_and_allows_retry(self):
        self._failed_temp_write('fsync')

    def test_directory_sync_failure_is_not_reported_as_durable_publication(self):
        target=self.f.mailbox/'_executor_spike/tasks/LH9305.json';original=os.fsync
        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError(errno.EIO,'fixture directory sync failure')
            return original(fd)
        with mock.patch.object(mailbox_safety.os,'fsync',side_effect=fail_directory):
            with self.assertRaises(LocalHandError) as raised:
                mailbox_safety.atomic_create_control_file(self.f.mailbox,target,b'payload')
        self.assertEqual(raised.exception.status,'indeterminate')
        self.assertEqual(target.read_bytes(),b'payload')
        self.assertFalse(list(target.parent.glob('.lh-*.tmp')))
