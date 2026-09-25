"""Actual subprocess output/EOF; no systemd/controller-stop inference."""
import os
import subprocess
import sys
import unittest

from local_hand_jobs import budget,quota_contract as q
if sys.platform.startswith('linux'):
    from admin.local_hand_quota_observer.q2_capture import capture_existing


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux outer anonymous capture')
class CaptureTests(unittest.TestCase):
    def start(self, code):
        p=subprocess.Popen([sys.executable,'-I','-B','-c',code],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
        def cleanup():
            if p.poll() is None:p.kill()
            p.wait(timeout=3)
            for f in (p.stdout,p.stderr):
                if not f.closed:f.close()
        self.addCleanup(cleanup)
        return p

    def capture(self,p,limit=32768,duration=2_000_000_000):
        clock=budget.current_clock()
        return capture_existing(p,boot_id=clock['boot_id'],started_ns=clock['boottime_ns'],
            deadline_ns=clock['boottime_ns']+duration,limit=limit)

    def test_actual_exit_both_eofs_and_replay_rejection(self):
        p=self.start("import os;os.write(1,b'out');os.write(2,b'err')")
        result=self.capture(p)
        self.assertTrue(result['complete']);self.assertEqual(0,result['returncode'])
        self.assertEqual(b'out',result['stdout']);self.assertEqual(b'err',result['stderr'])
        self.assertTrue(result['independent_stop_required']);self.assertFalse(result['q3_accepted'])
        with self.assertRaises(q.QuotaError):self.capture(p)

    def test_combined_overflow_preserves_bounded_prefix_and_failure(self):
        p=self.start("import os;os.write(1,b'x'*128);os.write(2,b'y'*128)")
        result=self.capture(p,limit=32)
        self.assertFalse(result['complete']);self.assertEqual('OUTER_BYTE_LIMIT',result['error'])
        self.assertEqual(32,len(result['stdout'])+len(result['stderr']))

    def test_deadline_does_not_kill_client_or_invent_eof(self):
        p=self.start("import time;time.sleep(2)")
        result=self.capture(p,duration=50_000_000)
        self.assertFalse(result['complete']);self.assertIsNone(result['returncode'])
        self.assertEqual([],result['eof']);self.assertIsNone(p.poll())

    def test_nonzero_exit_is_complete_capture_but_no_acceptance(self):
        p=self.start('raise SystemExit(7)');result=self.capture(p)
        self.assertTrue(result['complete']);self.assertEqual(7,result['returncode'])
        self.assertFalse(result['q3_accepted'])


if __name__=='__main__':unittest.main()
