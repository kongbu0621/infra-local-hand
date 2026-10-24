"""Fixed launch retention and real pipe exit; no production host claim."""
import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux administrator task launcher')

from admin.local_hand_system_manager import prepared_service as prepared
from admin.local_hand_system_manager.resident_service import ResidentService
from local_hand_jobs.contract import JobError, Principal


class FixedLaunchTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.launcher=prepared.FixedLauncher.__new__(prepared.FixedLauncher)
        item=self.launcher
        item.output=Path(root.name)
        item.directory=os.open(root.name,os.O_RDONLY|os.O_DIRECTORY)
        self.addCleanup(os.close,item.directory)
        item.process=None;item.complete=threading.Event();item.result=None;item.failure=None
        item.record_lock=threading.Lock()
        item.started=False;item.finished=False
        item.static='/synthetic/static.json'
        item.installation={'installed':{'programs':{'python':{},'systemd_run':{}}}}
        item.launch={'request':{'operation_id':'prepared-operation'},'policy':{
            'broker_root':root.name,'process_manager':{'uid':os.getuid(),'manager_binding':{'boot_id':'test-boot'}}}}

    def test_expiry_during_executable_check_precedes_intent_and_delivery(self):
        cutoff = int(time.time()) + 100
        principal = Principal('owner', frozenset({'lh:submit'}), expires_at=cutoff)
        with patch('time.time', return_value=cutoff - 1) as clock:
            def executable(_):
                clock.return_value = cutoff
                return os.open('/dev/null', os.O_RDONLY)
            with patch.object(prepared, 'controller_command', return_value=['/synthetic/not-started']), \
                 patch.object(prepared.budget, 'current_clock', return_value={'boot_id':'test-boot'}), \
                 patch.object(prepared.q2_config, 'executable', side_effect=executable), \
                 patch.object(prepared.subprocess, 'Popen') as popen:
                with self.assertRaises(JobError) as caught:
                    self.launcher.start(authorization=principal)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        popen.assert_not_called()
        self.assertEqual([], list(self.launcher.output.iterdir()))

    def test_expiry_after_intent_or_thread_creation_retains_failure_and_allows_one_retry(self):
        for stage in ('intent', 'thread'):
            with self.subTest(stage=stage):
                fixture = FixedLaunchTests('runTest')
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                item = fixture.launcher
                cutoff = int(time.time()) + 100
                principal = Principal('owner', frozenset({'lh:submit'}), expires_at=cutoff)
                create, start_thread, commit = subprocess.Popen, threading.Thread.start, item._commit_intent
                workers = []
                command = [sys.executable, '-c', "print('one refreshed attempt')"]
                with patch('time.time', return_value=cutoff - 1) as clock:
                    def publish(argv):
                        commit(argv)
                        if stage == 'intent': clock.return_value = cutoff
                    def start(worker):
                        workers.append(worker)
                        start_thread(worker)
                        if stage == 'thread': clock.return_value = cutoff
                    with patch.object(prepared, 'controller_command', return_value=command), \
                         patch.object(prepared.budget, 'current_clock', return_value={'boot_id':'test-boot'}), \
                         patch.object(prepared.q2_config, 'executable', side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
                         patch.object(item, '_commit_intent', side_effect=publish), \
                         patch.object(prepared.threading.Thread, 'start', new=start), \
                         patch.object(prepared.subprocess, 'Popen', side_effect=create) as popen:
                        with self.assertRaises(JobError) as caught:
                            item.start(authorization=principal)
                        self.assertEqual('UNAUTHORIZED', caught.exception.code)
                        popen.assert_not_called()
                        self.assertEqual('IDLE', item.state())
                        self.assertFalse((item.output/'launch-intent.json').exists())
                        retained = list(item.output.glob('local-authorization-expired-*.json'))
                        self.assertEqual(1, len(retained))
                        original = retained[0].read_bytes()
                        for worker in workers:
                            worker.join(1)
                            self.assertFalse(worker.is_alive())
                        refreshed = Principal('owner', principal.scopes, expires_at=cutoff + 100)
                        item.start(authorization=refreshed)
                        self.assertTrue(item.complete.wait(3))
                        # Expiry cannot cancel or replay an already delivered process.
                        clock.return_value = refreshed.expires_at
                        self.assertEqual('EXITED', item.state())
                        self.assertEqual('EXITED', item.start())
                        popen.assert_called_once()
                        self.assertEqual(original, retained[0].read_bytes())
                        self.assertEqual(0, item.result['returncode'])

    def test_fixed_receiver_retains_authority_until_process_delivery(self):
        from local_hand_jobs.forwarded_bounds import attach
        launch = dict(self.launcher.launch, principal_id='owner')
        launch['request'] = dict(launch['request'], request_digest='a'*64)
        launch['policy']['principals'] = {'owner': {'scopes': ['lh:submit', 'lh:read']}}
        body = dict(action='start', **launch['request'])
        cutoff = int(time.time()) + 100
        principal = Principal('owner', frozenset({'lh:submit'}), expires_at=cutoff)
        request, authorization = prepared.bounded_request(attach(body, principal), launch)
        self.assertEqual(body, request)
        self.assertEqual(cutoff, authorization.expires_at)
        with patch('time.time', return_value=cutoff), patch.object(prepared.subprocess, 'Popen') as popen:
            with self.assertRaises(JobError) as caught:
                self.launcher.start(authorization=authorization)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        popen.assert_not_called()
        self.assertEqual((body, None), prepared.bounded_request(body, launch))

    def test_local_popen_failure_retains_record_and_can_retry_without_remote_execution(self):
        with patch.object(prepared,'controller_command',return_value=['/synthetic/absent']), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=OSError('not started')) as popen:
            for _ in range(2):
                with self.assertRaises(JobError):self.launcher.start()
                self.assertEqual('IDLE',self.launcher.state())
            self.assertEqual(2,popen.call_count)
        self.assertEqual(2,len(list(self.launcher.output.glob('local-start-failed-*.json'))))
        self.assertFalse((self.launcher.output/'launch-intent.json').exists())

    def test_uncertain_previous_start_is_not_replayed(self):
        self.launcher.started=True
        with patch.object(prepared.subprocess,'Popen') as popen:
            with self.assertRaises(JobError):self.launcher.start()
        popen.assert_not_called()

    def test_capture_thread_start_failure_precedes_process_delivery_and_allows_retry(self):
        create=subprocess.Popen
        command=[sys.executable,'-c',"print('completed once after local failures')"]
        with patch.object(prepared,'controller_command',return_value=command), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=create) as popen:
            with patch.object(prepared.threading.Thread,'start',side_effect=RuntimeError('no thread resources')):
                for _ in range(2):
                    with self.assertRaises(JobError):self.launcher.start()
                    self.assertEqual('IDLE',self.launcher.state())
                popen.assert_not_called()
            self.assertFalse((self.launcher.output/'launch-intent.json').exists())
            self.launcher.start()
            self.assertTrue(self.launcher.complete.wait(3))
            self.assertEqual('EXITED',self.launcher.start())
            popen.assert_called_once()
        self.assertEqual(2,len(list(self.launcher.output.glob('local-start-failed-*.json'))))
        self.assertEqual(0,self.launcher.result['returncode'])
        self.assertEqual(b'completed once after local failures\n',
                         bytes.fromhex(self.launcher.result['streams']['stdout']['hex']))

    def test_started_capture_worker_cannot_adopt_a_later_attempt_after_start_raises(self):
        original_start=threading.Thread.start
        workers=[]
        def interrupted_start(worker):
            workers.append(worker)
            original_start(worker)
            raise RuntimeError('interrupted after native thread start')
        with patch.object(prepared,'controller_command',return_value=['/synthetic/absent']), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.threading.Thread,'start',new=interrupted_start), \
             patch.object(self.launcher,'_capture') as capture, \
             patch.object(prepared.subprocess,'Popen') as popen:
            try:
                with self.assertRaises(JobError):self.launcher.start()
            finally:
                for worker in workers:worker.join(timeout=1)
            self.assertTrue(all(not worker.is_alive() for worker in workers))
            popen.assert_not_called()
            capture.assert_not_called()
        self.assertEqual('IDLE',self.launcher.state())

    def test_capture_drains_large_real_dual_streams_without_additional_threads(self):
        process=subprocess.Popen([sys.executable,'-c',
            "import os;os.write(1,b'x'*100000);os.write(2,b'y'*100000)"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None:process.kill()
            process.wait(timeout=3)
            for stream in (process.stdout,process.stderr):
                if not stream.closed:stream.close()
        self.addCleanup(cleanup)
        self.launcher.process=process
        self.launcher.started=True
        with patch.object(prepared.threading.Thread,'start',side_effect=RuntimeError('no thread resources')):
            self.launcher._capture()
        self.assertEqual('EXITED',self.launcher.state())
        self.assertTrue(self.launcher.result['streams_eof'])
        for name,byte in [('stdout',b'x'),('stderr',b'y')]:
            stream=self.launcher.result['streams'][name]
            self.assertEqual(100000,stream['total_bytes'])
            self.assertEqual(byte*32768,bytes.fromhex(stream['hex']))
            self.assertTrue(stream['truncated'])

    def test_waiter_exit_does_not_finish_capture_while_descendant_holds_pipes(self):
        process=subprocess.Popen([sys.executable,'-c',
            "import os\nif os.fork()==0:\n os.read(0,1)\n os._exit(0)\nos._exit(0)"],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.launcher.process=process
        self.launcher.started=True
        worker=threading.Thread(target=self.launcher._capture,daemon=True)
        try:
            self.assertEqual(0,process.wait(timeout=3))
            worker.start()
            self.assertFalse(self.launcher.complete.wait(.05))
            self.assertEqual('RUNNING',self.launcher.state())
            self.assertFalse((self.launcher.output/'finished.json').exists())
        finally:
            process.stdin.close()
            if worker.ident is not None:worker.join(timeout=3)
            if process.poll() is None:process.kill()
            process.wait(timeout=3)
            for stream in (process.stdout,process.stderr):
                if not stream.closed:stream.close()
        self.assertFalse(worker.is_alive())
        self.assertEqual('EXITED',self.launcher.state())
        self.assertTrue(self.launcher.result['streams_eof'])

    def test_capture_read_failure_is_unknown_and_never_an_exit_or_second_launch(self):
        process=subprocess.Popen([sys.executable,'-c',"print('retained')"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        process.wait(timeout=3)
        self.launcher.process=process
        self.launcher.started=True
        with patch.object(prepared.os,'read',side_effect=OSError('pipe failure')):
            self.launcher._capture()
        self.assertFalse(self.launcher.complete.is_set())
        self.assertFalse((self.launcher.output/'finished.json').exists())
        with patch.object(prepared.subprocess,'Popen') as popen:
            with self.assertRaises(JobError):self.launcher.state()
            with self.assertRaises(JobError):self.launcher.start()
            popen.assert_not_called()

    def completed_child(self):
        process=subprocess.Popen([sys.executable,'-c',"print('original exit proof')"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None:process.kill()
            process.wait(timeout=3)
            for stream in (process.stdout,process.stderr):
                if not stream.closed:stream.close()
        self.addCleanup(cleanup)
        self.launcher.process=process
        self.launcher.started=True
        return process

    def test_exit_record_open_failure_retries_publication_without_recapturing_or_launching(self):
        process=self.completed_child()
        with patch.object(prepared.task_service,'save',side_effect=OSError('record open unavailable')):
            self.launcher._capture()
        self.assertEqual(0,process.returncode)
        self.assertTrue(self.launcher.complete.is_set())
        original=self.launcher.result
        with patch.object(prepared.subprocess,'Popen') as spawn, \
             patch.object(self.launcher,'_capture') as capture:
            self.assertEqual('EXITED',self.launcher.state())
            self.assertEqual('EXITED',self.launcher.start())
            spawn.assert_not_called()
            capture.assert_not_called()
        self.assertIs(original,self.launcher.result)
        self.assertEqual(original,json.loads((self.launcher.output/'finished.json').read_bytes()))

    def test_partial_exit_record_is_retained_without_publishing_a_truncated_completion(self):
        self.completed_child()
        write=os.write
        calls=0
        def interrupted(fd,raw):
            nonlocal calls
            calls+=1
            if calls==1:return write(fd,raw[:19])
            raise OSError('storage interrupted after partial write')
        with patch.object(prepared.os,'write',side_effect=interrupted):
            self.launcher._capture()
        partials={p:p.read_bytes() for p in self.launcher.output.iterdir()}
        self.assertEqual(1,len(partials))
        self.assertEqual([19],[len(raw) for raw in partials.values()])
        self.assertFalse((self.launcher.output/'finished.json').exists())
        self.assertEqual('EXITED',self.launcher.state())
        self.assertEqual(partials,{p:p.read_bytes() for p in partials})
        self.assertEqual(self.launcher.result,json.loads((self.launcher.output/'finished.json').read_bytes()))

    def test_published_exit_record_sync_failure_reuses_same_inode_and_result(self):
        self.completed_child()
        resident=ResidentService.__new__(ResidentService)
        resident.boot='test-boot'
        resident.launchers={'original-attempt':self.launcher}
        record=dict(output=str(self.launcher.output),attempt='original-attempt',boot_id=resident.boot)
        self.enterContext(patch('admin.local_hand_system_manager.resident_service.load',
                               side_effect=lambda path:json.loads(Path(path).read_bytes())))
        fsync=os.fsync
        def interrupted(fd):
            if fd==self.launcher.directory and (self.launcher.output/'finished.json').exists():
                raise OSError('completion directory sync failed')
            fsync(fd)
        with patch.object(prepared.os,'fsync',side_effect=interrupted):
            self.launcher._capture()
            with self.assertRaises(JobError):self.launcher.state()
            with self.assertRaises(JobError):resident.execution_state(record)
        path=self.launcher.output/'finished.json'
        identity=path.stat().st_ino
        original=path.read_bytes()
        with patch.object(prepared.task_service,'save') as save:
            self.assertEqual('EXITED',resident.execution_state(record))
            save.assert_not_called()
        self.assertEqual(identity,path.stat().st_ino)
        self.assertEqual(original,path.read_bytes())

    def test_conflicting_exit_record_is_never_replaced_or_treated_as_this_result(self):
        self.completed_child()
        path=self.launcher.output/'finished.json'
        original=b'{"returncode":7,"streams_eof":true}\n'
        path.write_bytes(original)
        path.chmod(0o600)
        self.launcher._capture()
        with patch.object(prepared.subprocess,'Popen') as spawn:
            for _ in range(2):
                with self.assertRaises(JobError):self.launcher.start()
            spawn.assert_not_called()
        self.assertEqual(original,path.read_bytes())

    def test_completion_cannot_follow_aliases_or_accept_shared_or_public_records(self):
        self.completed_child()
        with patch.object(prepared.task_service,'save',side_effect=OSError('not published yet')):
            self.launcher._capture()
        raw=prepared.q._canonical(self.launcher.result,2*1024**2)+b'\n'
        path=self.launcher.output/'finished.json'
        retained=self.launcher.output/'retained.json'
        retained.write_bytes(raw)
        retained.chmod(0o600)
        for kind in ('symlink','hardlink','fifo','public'):
            with self.subTest(kind=kind):
                if kind=='symlink':path.symlink_to(retained)
                elif kind=='hardlink':os.link(retained,path)
                elif kind=='fifo':os.mkfifo(path,0o600)
                else:
                    path.write_bytes(raw)
                    path.chmod(0o644)
                try:
                    with self.assertRaises(JobError):self.launcher.state()
                    self.assertEqual(raw,retained.read_bytes())
                finally:path.unlink()
        self.assertEqual('EXITED',self.launcher.state())

    def test_completion_replacement_during_sync_keeps_original_proof_and_rejects_entry(self):
        self.completed_child()
        fsync=os.fsync
        path=self.launcher.output/'finished.json'
        archived=self.launcher.output/'original-finished.json'
        foreign=b'{"foreign":true}\n'
        def replace(fd):
            fsync(fd)
            if fd==self.launcher.directory and path.exists() and not archived.exists():
                path.rename(archived)
                path.write_bytes(foreign)
                path.chmod(0o600)
        with patch.object(prepared.os,'fsync',side_effect=replace):
            self.launcher._capture()
        self.assertTrue(self.launcher.complete.is_set())
        self.assertEqual(self.launcher.result,json.loads(archived.read_bytes()))
        with self.assertRaises(JobError):self.launcher.state()
        self.assertEqual(foreign,path.read_bytes())

    def test_intent_commit_failure_before_popen_does_not_block_local_retry(self):
        fsync=os.fsync
        interrupted_once=False
        def interrupted(fd):
            nonlocal interrupted_once
            if fd==self.launcher.directory and not interrupted_once:
                interrupted_once=True
                raise OSError('directory sync failed before process creation')
            fsync(fd)
        with patch.object(prepared,'controller_command',return_value=['/synthetic/absent']), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=OSError('not started')) as popen:
            with patch.object(prepared.os,'fsync',side_effect=interrupted):
                with self.assertRaises(JobError):self.launcher.start()
            popen.assert_not_called()
            with self.assertRaises(JobError):self.launcher.start()
            popen.assert_called_once()
        self.assertEqual('IDLE',self.launcher.state())
        self.assertEqual(1,len(list(self.launcher.output.glob('local-intent-failed-*.json'))))

    def test_intent_open_error_does_not_claim_ownership_of_an_existing_record(self):
        original=b'{"prior":"unknown effects"}'
        (self.launcher.output/'launch-intent.json').write_bytes(original)
        with patch.object(prepared.os,'open',side_effect=OSError('cannot inspect storage')):
            with self.assertRaises(JobError):self.launcher._commit_intent(['/synthetic'])
        self.assertEqual(original,(self.launcher.output/'launch-intent.json').read_bytes())
        self.assertEqual([],list(self.launcher.output.glob('local-intent-failed-*.json')))

    def test_running_controller_is_reused_without_second_popen(self):
        self.launcher.process=Mock()
        self.launcher.started=True
        with patch.object(prepared.subprocess,'Popen') as popen:
            self.assertEqual('RUNNING',self.launcher.start())
        popen.assert_not_called()

    def test_real_child_starts_only_after_intent_commit_and_is_not_restarted(self):
        popen=subprocess.Popen
        command=[sys.executable,'-c',"print('completed once')"]
        def create(argv,**kwargs):
            import json
            intent=json.loads((self.launcher.output/'launch-intent.json').read_text())
            self.assertEqual(command,intent['command'])
            self.assertEqual(self.launcher.launch['request']['operation_id'],intent['operation_id'])
            return popen(argv,**kwargs)
        with patch.object(prepared,'controller_command',return_value=command), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=create) as spawn:
            self.launcher.start()
            self.assertTrue(self.launcher.complete.wait(3))
            self.assertEqual('EXITED',self.launcher.start())
            spawn.assert_called_once()
        self.assertEqual(0,self.launcher.result['returncode'])
        self.assertTrue(self.launcher.result['streams_eof'])

    def test_intent_appearing_after_launcher_open_is_preserved_and_not_replayed(self):
        original=b'{"prior":"unknown effects"}'
        (self.launcher.output/'launch-intent.json').write_bytes(original)
        with patch.object(prepared,'controller_command',return_value=['/synthetic/absent']), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen') as popen:
            for _ in range(2):
                with self.assertRaises(JobError):self.launcher.start()
        popen.assert_not_called()
        self.assertEqual(original,(self.launcher.output/'launch-intent.json').read_bytes())
        self.assertEqual([],list(self.launcher.output.glob('local-*-failed-*.json')))

    def test_exit_requires_reaped_child_and_real_stdout_stderr_eof(self):
        process=subprocess.Popen([sys.executable,'-c',"import sys;print('retained');print('error record',file=sys.stderr)"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(lambda:process.poll() is None and process.kill())
        self.launcher.process=process
        self.launcher.started=True
        self.launcher._capture()
        self.assertTrue(self.launcher.complete.is_set())
        self.assertEqual(0,self.launcher.result['returncode'])
        self.assertTrue(self.launcher.result['streams_eof'])
        self.assertEqual(b'retained\n',bytes.fromhex(self.launcher.result['streams']['stdout']['hex']))
        self.assertEqual('EXITED',self.launcher.state())
        self.assertTrue((self.launcher.output/'finished.json').exists())
        self.assertEqual('EXITED',self.launcher.start())
