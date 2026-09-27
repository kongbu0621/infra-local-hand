"""New scope clock ancestry, distinct schemas and real finite client pipes."""
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

from e3_host import q2_startup_retry_delivery as d


class StartupRetryClock(unittest.TestCase):
    boot = "12345678-1234-1234-1234-123456789abc"
    attempt = "startupretry01"

    def anchor(self, **changes):
        args = dict(host_issued_ns=100*d.NS, host_deadline_ns=400*d.NS, host_probe_send_ns=103*d.NS,
                    host_probe_receive_ns=107*d.NS, guest_boot_id=self.boot, expected_boot_id=self.boot,
                    guest_sample_ns=900*d.NS)
        args.update(changes)
        return d.make_clock_anchor(**args)

    def envelope(self, now=901*d.NS):
        return d.guest_envelope(self.anchor(), attempt_id=self.attempt, guest_boot_id=self.boot, guest_now_ns=now)

    def test_delay_and_different_clock_epochs_consume_one_original_window(self):
        anchor = self.anchor()
        self.assertEqual(anchor["guest_outer_deadline_ns"], 1191*d.NS)
        later = self.anchor(host_probe_receive_ns=117*d.NS)
        self.assertEqual(later["guest_outer_deadline_ns"], 1181*d.NS)
        envelope = self.envelope(now=1020*d.NS)
        self.assertEqual(envelope["preparation_deadline_ns"]-envelope["issued_ns"], 33*d.NS)
        self.assertEqual(envelope["deadline_ns"], 1181*d.NS)
        with self.assertRaisesRegex(ValueError, "GUEST_TIME_EXHAUSTED"):
            self.envelope(now=1053*d.NS)

    def test_host_suspend_before_probe_does_not_donate_time_to_remote_mapping(self):
        common=dict(issued_ns=100*d.NS,deadline_ns=400*d.NS,boottime_issued_ns=900*d.NS)
        # Host has 93 BOOTTIME seconds left, but MONOTONIC claims 293.
        # Neither clock is expired, yet mapping the larger value is forbidden.
        with self.assertRaisesRegex(ValueError,"HOST_CLOCK_DIVERGED"):
            d.validate_host_clock(**common,monotonic_now_ns=107*d.NS,boottime_now_ns=1107*d.NS)
        self.assertEqual(d.validate_host_clock(**common,monotonic_now_ns=107*d.NS,
            boottime_now_ns=908*d.NS)["sampling_margin_ns"],2*d.NS)
        with self.assertRaisesRegex(ValueError,"HOST_CLOCK_DIVERGED"):
            d.validate_host_clock(**common,monotonic_now_ns=107*d.NS,boottime_now_ns=909*d.NS+1)

    def test_old_schema_extra_fields_and_refreshed_clock_rejected(self):
        envelope = self.envelope(); entry = dict(monotonic_ns=51*d.NS, boottime_ns=931*d.NS)
        for changed in ({"schema":"local-hand-q2-cpuquota-retry-delivery/v1"}, {"old_attempt": True},
                        {"attempt_id":"otherattempt01"}, {"stop_ns":4*d.NS}, {"deadline_ns":1172*d.NS},
                        {"issued_ns": True}, {"preparation_deadline_ns":1042*d.NS}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                raw = d.encoded({**envelope, **changed})
                d.validate_delivery(raw, d.sha(raw), self.attempt, entry, boot_id=self.boot)
        anchor = self.anchor()
        for changed in ({"schema":"local-hand-q2-cpuquota-retry-clock-anchor/v1"}, {"sampling_margin_ns":0},
                        {"guest_outer_deadline_ns":anchor["guest_outer_deadline_ns"]+1}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                d.validate_clock_anchor({**anchor, **changed})

    def test_bootstrap_spent_time_suspend_and_stop_reserve_never_refunded(self):
        envelope = self.envelope(); entry = dict(monotonic_ns=51*d.NS, boottime_ns=931*d.NS)
        self.assertEqual(d.preparation_window(envelope, entry), (21*d.NS, 161*d.NS))
        now = dict(boot_id=self.boot, boottime_ns=1040*d.NS)
        self.assertEqual(d.owner_admission({"owner":{"runtime_ns":120*d.NS}}, envelope, now, entry), 120*d.NS)
        for altered in ({"boottime_ns":1041*d.NS}, {"boot_id":"other"}):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                d.preparation_guard(lambda:None, envelope, lambda:{**now, **altered})()
        with self.assertRaisesRegex(ValueError, "OWNER_TIME_UNFUNDED"):
            d.owner_admission({"owner":{"runtime_ns":120*d.NS}}, {**envelope,"deadline_ns":1168*d.NS}, now, entry)

    def test_strict_json_including_large_collection_has_explicit_limit(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":1.0}',b'{"a":NaN}',b'[]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                d.document(raw)
        raw=d.encoded({"payload":"x"*20000})
        with self.assertRaises(ValueError):d.document(raw)
        self.assertEqual(len(d.document(raw,maximum=d.OUTPUT_LIMIT)["payload"]),20000)
        with self.assertRaises(ValueError):d.document(raw,maximum=d.OUTPUT_LIMIT+1)


@unittest.skipUnless(sys.platform.startswith("linux"), "real finite Linux pipes and BOOTTIME")
class StartupRetryClientPipes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.boot=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        self.start=time.monotonic_ns();self.end=self.start+5*d.NS

    def capture(self,phase,source,**kwargs):
        kwargs.setdefault("host_boottime_issued_ns",self.boot)
        return d.capture_once([sys.executable,"-I","-B","-c",source],host_issued_ns=self.start,
            host_deadline_ns=self.end,stdout_path=self.root/(phase+".out"),stderr_path=self.root/(phase+".err"),**kwargs)

    def test_exit_three_and_complete_eof_preserves_captured_failure(self):
        probe=self.capture("probe","print('clock')")
        guest=self.capture("guest","import os;os.write(1,b'BLOCKED\\n');os.write(2,b'diagnostic\\n');os._exit(3)",
                           prior_captured_bytes=probe["total_captured_bytes"])
        self.assertTrue(guest["complete"]);self.assertFalse(guest["command_succeeded"])
        self.assertFalse(guest["primitive_capture_complete"]);self.assertEqual(guest["returncode"],3)
        self.assertEqual(guest["eof"],["stderr","stdout"])
        report=d.final_report(attempt_id="startupretry01",host_issued_ns=self.start,host_deadline_ns=self.end,host_boottime_issued_ns=self.boot,
                              probe_capture=probe,guest_capture=guest)
        self.assertTrue(report["original_clients_capture_complete"])
        self.assertEqual(report["status"],"INCOMPLETE")
        self.assertFalse(report["q2_accepted"]);self.assertFalse(report["remote_stop_proven"])

    def test_shared_output_pool_and_create_only_paths(self):
        result=self.capture("guest","import os;os.write(1,b'x'*800);os.write(2,b'y'*800)",
                            prior_captured_bytes=d.OUTPUT_LIMIT-1024)
        self.assertFalse(result["complete"]);self.assertEqual(result["captured_bytes"],1024)
        self.assertEqual(result["error"],"DELIVERY_CAPTURE_LIMIT")
        with self.assertRaises(ValueError):self.capture("collect","print('forbidden')",prior_captured_bytes=d.OUTPUT_LIMIT)
        self.assertFalse((self.root/"collect.out").exists())
        with self.assertRaises(ValueError):self.capture("guest","print('forbidden')")
        with self.assertRaises(ValueError):self.capture("new","print('forbidden')",deadline_ns=self.end+1)

    @unittest.skipUnless(hasattr(os,"fork"),"forked pipe-holder")
    def test_zero_client_exit_without_eof_is_not_capture_or_stop(self):
        result=self.capture("guest","import os,time;child=os.fork();time.sleep(3) if child==0 else None;os._exit(0)",
                            deadline_ns=self.start+400_000_000)
        self.assertEqual(result["returncode"],0);self.assertFalse(result["complete"])
        self.assertEqual(result["error"],"DELIVERY_CAPTURE_TIMEOUT")
        self.assertFalse(result["remote_stop_proven"])

    def test_host_suspend_spends_original_budget_and_stops_client_without_monotonic_wait(self):
        boot=time.clock_gettime_ns(time.CLOCK_BOOTTIME);original=time.clock_gettime_ns;calls=[]
        def clock(clock_id):
            calls.append(clock_id)
            return original(clock_id)+(10*d.NS if len(calls)>=3 else 0)
        started=time.monotonic()
        with patch.object(d.time,"clock_gettime_ns",side_effect=clock):
            result=self.capture("suspended","import time;time.sleep(3)",host_boottime_issued_ns=boot)
        self.assertLess(time.monotonic()-started,1)
        self.assertFalse(result["complete"]);self.assertFalse(result["within_original_deadline"])
        self.assertEqual(result["error"],"DELIVERY_CAPTURE_TIMEOUT")
        self.assertFalse(result["remote_stop_proven"])

    def test_suspend_after_clients_exit_cannot_make_transport_report_claim_inside_deadline(self):
        probe=self.capture("probe","print('clock')")
        guest=self.capture("guest","print('done')",prior_captured_bytes=probe["total_captured_bytes"])
        report=d.final_report(attempt_id="startupretry01",host_issued_ns=self.start,host_deadline_ns=self.end,
            host_boottime_issued_ns=self.boot,probe_capture=probe,guest_capture=guest,
            finished_ns=self.start+d.NS,finished_boottime_ns=self.boot+5*d.NS+1)
        self.assertTrue(probe["complete"]);self.assertTrue(guest["complete"])
        self.assertFalse(report["within_management_deadline"])
        self.assertFalse(report["original_clients_succeeded"])
        self.assertEqual(report["status"],"INCOMPLETE")
        self.assertEqual(report["finished_boottime_ns"],self.boot+5*d.NS+1)

    def test_cross_scope_receipt_and_cross_window_receipt_cannot_be_merged(self):
        capture=self.capture("probe","print('clock')")
        for fields in ({"schema":"local-hand-q2-cpuquota-retry-client-capture/v1"},
                       {"host_deadline_ns":self.end+1},{"prior_captured_bytes":1},{"boottime_issued_ns":self.boot+1}):
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                d.final_report(attempt_id="startupretry01",host_issued_ns=self.start,host_deadline_ns=self.end,host_boottime_issued_ns=self.boot,
                               probe_capture={**capture,**fields})


if __name__=="__main__":unittest.main()
