"""Fixed launch retention and real pipe exit; no production host claim."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

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

    def test_running_controller_is_reused_without_second_popen(self):
        self.launcher.process=Mock()
        self.launcher.started=True
        with patch.object(prepared.subprocess,'Popen') as popen:
            self.assertEqual('RUNNING',self.launcher.start())
        popen.assert_not_called()

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

