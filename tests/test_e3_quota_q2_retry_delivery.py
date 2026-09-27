"""New retry clock ancestry and real finite client streams, with no SSH."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from e3_host import q2_retry_delivery as d


class ImmutableWindows(unittest.TestCase):
    boot = "12345678-1234-1234-1234-123456789abc"
    attempt = "syntheticretry01"

    def anchor(self, **changes):
        values = dict(host_issued_ns=100*d.NS, host_deadline_ns=400*d.NS,
                      host_probe_send_ns=103*d.NS, host_probe_receive_ns=107*d.NS,
                      guest_boot_id=self.boot, expected_boot_id=self.boot, guest_sample_ns=900*d.NS)
        values.update(changes)
        return d.make_clock_anchor(**values)

    def envelope(self, now=901*d.NS):
        return d.guest_envelope(self.anchor(), attempt_id=self.attempt, guest_boot_id=self.boot, guest_now_ns=now)

    def test_distinct_clock_epochs_charge_every_probe_delay(self):
        anchor = self.anchor()
        self.assertEqual(anchor["guest_outer_deadline_ns"], 1191*d.NS)
        self.assertEqual(d.validate_clock_anchor(anchor), anchor)
        delayed = self.anchor(host_probe_receive_ns=117*d.NS)
        self.assertEqual(delayed["guest_outer_deadline_ns"], anchor["guest_outer_deadline_ns"]-10*d.NS)
        for field in ("host_issued_ns", "host_probe_send_ns", "guest_sample_ns"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.anchor(**{field:True})
        for change in ({"host_deadline_ns":401*d.NS}, {"host_probe_send_ns":99*d.NS},
                       {"host_probe_receive_ns":102*d.NS}, {"host_probe_receive_ns":395*d.NS},
                       {"guest_sample_ns":2**63-1}, {"expected_boot_id":"different"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.anchor(**change)

    def test_bootstrap_elapsed_is_not_refunded_at_driver_entry(self):
        envelope = self.envelope()
        self.assertEqual(envelope["preparation_deadline_ns"], 1041*d.NS)
        self.assertEqual(envelope["deadline_ns"], 1171*d.NS)
        entry = dict(monotonic_ns=51*d.NS, boottime_ns=931*d.NS)
        raw = d.encoded(envelope)
        self.assertEqual(d.validate_delivery(raw, d.sha(raw), self.attempt, entry, boot_id=self.boot), envelope)
        issued, deadline = d.preparation_window(envelope, entry)
        self.assertEqual((issued, deadline), (21*d.NS, 161*d.NS))
        self.assertEqual(deadline-entry["monotonic_ns"], 110*d.NS)
        self.assertEqual(d.owner_admission({"owner":{"runtime_ns":120*d.NS}}, envelope,
            dict(boot_id=self.boot,boottime_ns=1040*d.NS), entry), 120*d.NS)
        self.assertEqual(d.remaining(envelope,self.anchor(),guest_boot_id=self.boot,guest_now_ns=1040*d.NS),131*d.NS)

    def test_transport_delay_shortens_preparation_without_extending_guest_outer(self):
        envelope = self.envelope(now=1020*d.NS)
        self.assertEqual(envelope["guest_outer_deadline_ns"],1191*d.NS)
        self.assertEqual(envelope["deadline_ns"],1181*d.NS)
        self.assertEqual(envelope["preparation_deadline_ns"],1053*d.NS)
        self.assertEqual(envelope["preparation_deadline_ns"]-envelope["issued_ns"],33*d.NS)
        with self.assertRaisesRegex(ValueError,"GUEST_TIME_EXHAUSTED"):
            self.envelope(now=1053*d.NS)

    def test_pinned_envelope_identity_budget_and_schema_cannot_change(self):
        envelope = self.envelope(); entry=dict(monotonic_ns=100*d.NS,boottime_ns=902*d.NS)
        alterations=({"schema":"local-hand-q2-recovery-delivery/v1"}, {"attempt_id":"different01"},
            {"issued_ns":True}, {"preparation_deadline_ns":1042*d.NS}, {"deadline_ns":1172*d.NS},
            {"stop_ns":4*d.NS}, {"clock_anchor_sha256":"bad"}, {"guest_outer_deadline_ns":1172*d.NS},
            {"boot_id":"different"})
        for change in alterations:
            with self.subTest(change=change), self.assertRaises(ValueError):
                raw=d.encoded({**envelope,**change})
                d.validate_delivery(raw,d.sha(raw),self.attempt,entry,boot_id=self.boot)
        raw=d.encoded(envelope)
        with self.assertRaisesRegex(ValueError,"DIGEST"):
            d.validate_delivery(raw,"f"*64,self.attempt,entry,boot_id=self.boot)
        for key in ("deadline_ns","issued_ns","stop_ns","preparation_deadline_ns","guest_outer_deadline_ns"):
            with self.subTest(key=key),self.assertRaises(ValueError):
                changed={**envelope,key:envelope[key]+1}
                d.remaining(changed,self.anchor(),guest_boot_id=self.boot,guest_now_ns=902*d.NS)

    def test_guest_suspend_and_boot_change_fail_preparation_guard(self):
        envelope=self.envelope(); checks=[]
        valid=dict(boot_id=self.boot,boottime_ns=1000*d.NS)
        clock=lambda:valid
        guard=d.preparation_guard(lambda:checks.append(True),envelope,clock)
        guard();self.assertEqual(checks,[True])
        # A suspended guest can retain MONOTONIC time while BOOTTIME expires.
        valid["boottime_ns"]=1041*d.NS
        with self.assertRaisesRegex(ValueError,"PREPARATION_EXPIRED"):guard()
        valid.update(boottime_ns=1000*d.NS,boot_id="different")
        with self.assertRaisesRegex(ValueError,"BOOT"):guard()

    def test_owner_needs_full_original_duration_and_stop_finalization(self):
        envelope=self.envelope();entry=dict(monotonic_ns=100*d.NS,boottime_ns=902*d.NS)
        for duration,now in ((121*d.NS,1000*d.NS),(True,1000*d.NS),(120*d.NS,1041*d.NS),
                             (0,1000*d.NS),(120*d.NS,901*d.NS)):
            with self.subTest(duration=duration,now=now),self.assertRaises(ValueError):
                d.owner_admission({"owner":{"runtime_ns":duration}},envelope,
                    dict(boot_id=self.boot,boottime_ns=now),entry)
        short={**envelope,"deadline_ns":1128*d.NS}
        with self.assertRaisesRegex(ValueError,"OWNER_TIME_UNFUNDED"):
            d.owner_admission({"owner":{"runtime_ns":120*d.NS}},short,
                dict(boot_id=self.boot,boottime_ns=1000*d.NS),entry)

    def test_json_duplicates_floats_constants_and_oversize_rejected(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":1.0}',b'{"a":NaN}',b'{}'+b' '*d.DOCUMENT_LIMIT,b'[]'):
            with self.subTest(raw=raw[:30]),self.assertRaises(ValueError):d.document(raw)


@unittest.skipUnless(os.name=="posix","POSIX original-client finite pipe capture")
class RealClientCapture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.issued=time.monotonic_ns();self.deadline=self.issued+5*d.NS

    def capture(self,name,code,**kwargs):
        return d.capture_once([sys.executable,"-I","-B","-c",code],host_issued_ns=self.issued,
            host_deadline_ns=self.deadline,stdout_path=self.root/(name+".stdout"),
            stderr_path=self.root/(name+".stderr"),**kwargs)

    def test_nonzero_exit_is_complete_capture_but_failed_command(self):
        probe=self.capture("probe","print('clock')",output_limit=4096)
        guest=self.capture("guest","import os;os.write(1,b'failed record\\n');os.write(2,b'CPU rejection\\n');os._exit(3)",
                           prior_captured_bytes=probe["total_captured_bytes"])
        self.assertTrue(guest["complete"]);self.assertFalse(guest["legacy_capture_complete"])
        self.assertFalse(guest["command_succeeded"]);self.assertEqual(guest["returncode"],3)
        self.assertEqual(guest["eof"],["stderr","stdout"])
        self.assertEqual((self.root/"guest.stderr").read_bytes(),b"CPU rejection\n")
        report=d.final_report(attempt_id="syntheticretry01",host_issued_ns=self.issued,host_deadline_ns=self.deadline,
                              probe_capture=probe,guest_capture=guest)
        self.assertTrue(report["original_clients_capture_complete"])
        self.assertFalse(report["original_clients_succeeded"])
        self.assertEqual(report["status"],"INCOMPLETE")
        self.assertFalse(report["q2_accepted"]);self.assertFalse(report["remote_stop_proven"])
        self.assertTrue(report["evidence_retained"]);self.assertFalse(report["replay_allowed"])

    def test_zero_exit_full_eof_does_not_claim_q2_or_remote_stop(self):
        probe=self.capture("probe","print('clock')")
        guest=self.capture("guest","print('done')",prior_captured_bytes=probe["total_captured_bytes"])
        report=d.final_report(attempt_id="syntheticretry01",host_issued_ns=self.issued,host_deadline_ns=self.deadline,
                              probe_capture=probe,guest_capture=guest)
        self.assertEqual(report["status"],"CAPTURED")
        self.assertTrue(report["original_clients_capture_complete"])
        self.assertFalse(report["q2_accepted"]);self.assertFalse(report["remote_stop_proven"])
        late=d.final_report(attempt_id="syntheticretry01",host_issued_ns=self.issued,host_deadline_ns=self.deadline,
                            probe_capture=probe,guest_capture=guest,finished_ns=self.deadline+1)
        self.assertEqual(late["status"],"INCOMPLETE")
        self.assertFalse(late["within_management_deadline"])

    def test_combined_stdout_stderr_probe_guest_limit_is_not_per_call(self):
        prior=d.OUTPUT_LIMIT-1024
        guest=self.capture("guest","import os;os.write(1,b'a'*700);os.write(2,b'b'*700)",prior_captured_bytes=prior)
        self.assertFalse(guest["complete"])
        self.assertEqual(guest["error"],"DELIVERY_CAPTURE_LIMIT")
        self.assertEqual(guest["captured_bytes"],1024)
        self.assertEqual(guest["total_captured_bytes"],d.OUTPUT_LIMIT)
        with self.assertRaises(ValueError):
            self.capture("another","print('must not run')",prior_captured_bytes=d.OUTPUT_LIMIT)
        self.assertFalse((self.root/"another.stdout").exists())

    @unittest.skipUnless(hasattr(os,"fork"),"Pipe-holder requires fork")
    def test_original_client_exit_without_eof_is_incomplete(self):
        result=self.capture("guest","import os,time;child=os.fork();time.sleep(5) if child==0 else None;os._exit(0)",
                            deadline_ns=self.issued+400_000_000)
        self.assertEqual(result["returncode"],0)
        self.assertFalse(result["complete"])
        self.assertEqual(result["error"],"DELIVERY_CAPTURE_TIMEOUT")
        self.assertNotEqual(result["eof"],["stderr","stdout"])

    def test_phase_paths_are_create_only_and_deadline_cannot_extend(self):
        result=self.capture("probe","print('first')")
        before=(self.root/"probe.stdout").read_bytes()
        with self.assertRaises(ValueError):self.capture("probe","print('second')")
        self.assertEqual((self.root/"probe.stdout").read_bytes(),before)
        with self.assertRaises(ValueError):self.capture("guest","print('new clock')",deadline_ns=self.deadline+1)
        self.assertFalse((self.root/"guest.stdout").exists())
        changed=copy.deepcopy(result);changed["host_deadline_ns"]+=1
        with self.assertRaisesRegex(ValueError,"CAPTURE_BINDING"):
            d.final_report(attempt_id="syntheticretry01",host_issued_ns=self.issued,host_deadline_ns=self.deadline,
                           probe_capture=changed)

    def test_no_argument_entry_is_blocked_and_creates_nothing(self):
        result=subprocess.run([sys.executable,"-I","-B",d.__file__],cwd=self.root,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,3)
        self.assertEqual(json.loads(result.stdout)["status"],"BLOCKED")
        self.assertEqual(list(self.root.iterdir()),[])


if __name__=="__main__":unittest.main()
