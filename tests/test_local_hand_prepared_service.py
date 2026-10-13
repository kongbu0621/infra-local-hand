"""Fixed launch retention and real pipe exit; no production host claim."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux administrator task launcher')

from admin.local_hand_system_manager import prepared_service as prepared
from local_hand_jobs.contract import JobError


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
