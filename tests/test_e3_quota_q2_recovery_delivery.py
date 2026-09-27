"""Retained failure binding and cross-host clocks; no SSH or fixture mutation."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from e3_host import q2_prepare_delivery as base
from e3_host import q2_recovery_delivery as d


@unittest.skipUnless(os.name == "posix", "Linux capture and no-follow reads")
class OriginalCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.expected = dict(source_commit="a"*40, source_tree="b"*40,
                             archive_sha256="c"*64, wheel_sha256="d"*64,
                             remote_unit="synthetic-prepare.service", guest_input_sha256=d.sha(b"synthetic input\n"),
                             plan_sha256="e"*64, receipt_sha256="", preparation_id="synthetic001")
        self.receipt = dict(schema="local-hand-q2-fixture-preparation/v1", preparation_id="synthetic001",
                            plan_sha256="e"*64, status="INCOMPLETE", reason="PREPARE_COMMAND_FAILED",
                            fixture_generated=False, q2_accepted=False, q3_accepted=False, production_supported=False,
                            facts=dict(capacity_observed={}, host={}, mounts={}, retained_before=[]))
        self.receipt_raw = d.encoded(self.receipt)
        self.expected["receipt_sha256"] = d.sha(self.receipt_raw)
        self.stdout = ("Q2_DELIVERY_READY source="+self.expected["source_commit"]+" plan_sha256="+
                       self.expected["plan_sha256"]+"\n").encode()+self.receipt_raw

    def capture(self, *, pipe_holder=False):
        issued = time.monotonic_ns()
        deadline = issued+int((0.5 if pipe_holder else 3)*d.NS)
        base.write(self.root/"guest-input.py", b"synthetic input\n")
        self.intent = dict(schema="local-hand-q2-private-handoff/v1",
                           **{k:self.expected[k] for k in ("source_commit", "source_tree", "archive_sha256", "wheel_sha256")},
                           issued_ns=issued, deadline_ns=deadline, q2_accepted=False)
        base.write(self.root/"intent.json", d.encoded(self.intent))
        code = "import os,time; os.write(1,"+repr(self.stdout)+"); os.write(2,b'synthetic original failure\\n'); "
        if pipe_holder:
            code += "child=os.fork(); time.sleep(5) if child==0 else None; os._exit(3)"
        else:
            code += "os._exit(3)"
        self.report = base.capture([sys.executable, "-I", "-B", "-c", code], issued_ns=issued,
                                   deadline_ns=deadline, output_limit=65536, stdout_path=self.root/"guest.stdout",
                                   stderr_path=self.root/"guest.stderr", stdin_path=self.root/"guest-input.py")
        self.report.update({name+"_sha256": d.sha((self.root/name).read_bytes())
                            for name in ("guest.stdout", "guest.stderr", "guest-input.py")})
        self.report.update({k:self.expected[k] for k in ("source_commit", "source_tree", "remote_unit")})
        self.report.update(q3_accepted=False, production_supported=False)
        base.write(self.root/"report.json", d.encoded(self.report))

    def test_actual_nonzero_client_complete_streams_preserve_original_bytes(self):
        self.capture()
        before = {p.name:p.read_bytes() for p in self.root.iterdir()}
        proof = d.validate_original_capture(self.root, self.expected)
        self.assertTrue(proof["original_failure_fully_captured"])
        self.assertFalse(proof["remote_stop_proven"])
        self.assertEqual(proof["capture"], dict(report_sha256=d.sha(before["report.json"]),
                         stdout_sha256=d.sha(before["guest.stdout"]), stderr_sha256=d.sha(before["guest.stderr"]),
                         receipt_sha256=self.expected["receipt_sha256"], returncode=3,
                         eof=["stderr", "stdout"], failure=None))
        for name in ("intent.json", "report.json", "guest.stdout", "guest.stderr"):
            self.assertEqual(bytes.fromhex(proof["files"][name]["hex"]), before[name])
        self.assertNotIn("hex", proof["files"]["guest-input.py"])
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.root.iterdir()})

    @unittest.skipUnless(hasattr(os, "fork"), "pipe holder test requires fork")
    def test_actual_exit_three_without_eof_is_not_recoverable_capture(self):
        self.capture(pipe_holder=True)
        self.assertEqual(self.report["returncode"], 3)
        self.assertEqual(self.report["error"], "DELIVERY_CAPTURE_TIMEOUT")
        with self.assertRaisesRegex(ValueError, "RECOVERY_DELIVERY_ORIGINAL_CAPTURE"):
            d.validate_original_capture(self.root, self.expected)

    def test_capture_claims_and_deadline_must_match_original_intent(self):
        self.capture()
        alterations = ({"returncode":0}, {"returncode":True}, {"error":"DELIVERY_CLIENT_EXIT_UNPROVEN"},
                       {"eof":["stdout"]}, {"complete":True}, {"q2_accepted":True},
                       {"remote_stop_proven":True}, {"within_original_deadline":False},
                       {"issued_ns":self.report["issued_ns"]+1},
                       {"finished_ns":self.report["deadline_ns"]+1},
                       {"captured_bytes":self.report["captured_bytes"]-1})
        for change in alterations:
            with self.subTest(change=change):
                (self.root/"report.json").write_bytes(d.encoded({**self.report, **change}))
                with self.assertRaises(ValueError):
                    d.validate_original_capture(self.root, self.expected)
        (self.root/"report.json").write_bytes(d.encoded(self.report))
        (self.root/"intent.json").write_bytes(d.encoded({**self.intent,"archive_sha256":"f"*64}))
        with self.assertRaisesRegex(ValueError, "RECOVERY_DELIVERY_OLD_BINDING"):
            d.validate_original_capture(self.root, self.expected)

    def test_pinned_input_replacement_not_accepted_by_rehashing_report(self):
        self.capture()
        (self.root/"guest-input.py").write_bytes(b"replacement\n")
        self.report["guest-input.py_sha256"] = d.sha(b"replacement\n")
        (self.root/"report.json").write_bytes(d.encoded(self.report))
        with self.assertRaisesRegex(ValueError, "RECOVERY_DELIVERY_INPUT_CHANGED"):
            d.validate_original_capture(self.root, self.expected)

    def test_receipt_must_be_pinned_unique_canonical_tail(self):
        self.capture()
        for replacement in (self.stdout+b"{}\n", b"noise\n"+self.stdout,
                            self.stdout.replace(b'"INCOMPLETE"', b'"COMPLETE"')):
            with self.subTest(replacement=replacement[-30:]):
                (self.root/"guest.stdout").write_bytes(replacement)
                self.report["guest.stdout_sha256"] = d.sha(replacement)
                self.report["captured_bytes"] = len(replacement)+len((self.root/"guest.stderr").read_bytes())
                (self.root/"report.json").write_bytes(d.encoded(self.report))
                with self.assertRaises(ValueError):
                    d.validate_original_capture(self.root, self.expected)

    def test_no_follow_and_regular_owned_single_link_files(self):
        self.capture()
        target = self.root/"intent.json"; raw = target.read_bytes()
        outside = self.root/"retained"; outside.write_bytes(raw)
        for kind in ("symlink", "hardlink", "fifo", "writable", "oversize"):
            with self.subTest(kind=kind):
                target.unlink()
                if kind == "symlink": target.symlink_to(outside)
                elif kind == "hardlink": os.link(outside, target)
                elif kind == "fifo": os.mkfifo(target)
                else:
                    target.write_bytes(b"x"*(d.FILE_LIMITS["intent.json"]+1) if kind == "oversize" else raw)
                    if kind == "writable": target.chmod(0o666)
                with self.assertRaises((ValueError, OSError)):
                    d.validate_original_capture(self.root, self.expected)
        target.unlink(); target.write_bytes(raw); target.chmod(0o600)
        linked_root = self.root/"alias"; linked_root.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises((ValueError, OSError)):
            d.validate_original_capture(linked_root, self.expected)

    def test_changed_file_entry_during_read_set_rejected(self):
        self.capture()
        actual = d._read
        def swap(fd, name, limit):
            result = actual(fd, name, limit)
            if name == "guest-input.py":
                original = self.root/"intent.json"
                original.rename(self.root/"old-intent")
                original.write_bytes(d.encoded(self.intent))
            return result
        with patch.object(d, "_read", side_effect=swap), self.assertRaisesRegex(ValueError, "CHANGED"):
            d.validate_original_capture(self.root, self.expected)

    def test_duplicate_keys_rejected(self):
        self.capture()
        original = (self.root/"intent.json").read_bytes()
        (self.root/"intent.json").write_bytes(b'{"q2_accepted":false,'+original[1:])
        with self.assertRaisesRegex(ValueError, "RECOVERY_DELIVERY_DUPLICATE_KEY"):
            d.validate_original_capture(self.root, self.expected)


class CrossHostClock(unittest.TestCase):
    boot = "12345678-1234-1234-1234-123456789abc"

    def anchor(self, **changes):
        values = dict(host_issued_ns=100*d.NS, host_deadline_ns=400*d.NS,
                      host_probe_send_ns=103*d.NS, host_probe_receive_ns=107*d.NS,
                      guest_boot_id=self.boot, expected_boot_id=self.boot, guest_sample_ns=900*d.NS)
        values.update(changes)
        return d.make_clock_anchor(**values)

    def test_different_clock_epochs_charge_probe_elapsed_and_margin(self):
        anchor = self.anchor()
        self.assertEqual(anchor["guest_outer_deadline_ns"], 1191*d.NS)
        self.assertEqual(d.validate_clock_anchor(anchor), anchor)
        delayed = self.anchor(host_probe_receive_ns=117*d.NS)
        self.assertEqual(delayed["guest_outer_deadline_ns"], anchor["guest_outer_deadline_ns"]-10*d.NS)

    def test_invalid_window_changed_boot_expired_and_boolean_stamps_rejected(self):
        for changes in ({"expected_boot_id":"0"*36}, {"host_issued_ns":True},
                        {"host_deadline_ns":401*d.NS}, {"host_probe_send_ns":99*d.NS},
                        {"host_probe_receive_ns":102*d.NS}, {"host_probe_receive_ns":395*d.NS},
                        {"guest_sample_ns":2**63-1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.anchor(**changes)
        forged = self.anchor(); forged["guest_outer_deadline_ns"] += 1
        with self.assertRaisesRegex(ValueError, "RECOVERY_DELIVERY_ANCHOR_CHANGED"):
            d.validate_clock_anchor(forged)

    def test_guest_entry_caps_service_and_pins_preparation_before_reads(self):
        anchor = self.anchor()
        envelope = d.guest_envelope(anchor, recovery_id="syntheticrecovery", guest_boot_id=self.boot,
                                    guest_now_ns=901*d.NS)
        self.assertEqual(envelope["deadline_ns"], 1171*d.NS)
        self.assertEqual(envelope["preparation_deadline_ns"], 1041*d.NS)
        self.assertEqual(envelope["clock_anchor_sha256"], d.sha(d.encoded(anchor)))
        self.assertEqual(envelope["stop_ns"], 3*d.NS)
        self.assertEqual(d.remaining(envelope, anchor, guest_boot_id=self.boot, guest_now_ns=1040*d.NS), 131*d.NS)
        # A second entry does not let an already-issued envelope acquire extra time.
        changed = {**envelope, "preparation_deadline_ns":1042*d.NS}
        with self.assertRaisesRegex(ValueError, "RECOVERY_DELIVERY_ENVELOPE_CHANGED"):
            d.remaining(changed, anchor, guest_boot_id=self.boot, guest_now_ns=1040*d.NS)
        with self.assertRaisesRegex(ValueError, "RECOVERY_DELIVERY_ISSUANCE_TIME_EXHAUSTED"):
            d.remaining(envelope, anchor, guest_boot_id=self.boot, guest_now_ns=1041*d.NS)

    def test_transport_delay_shortens_preparation_and_never_moves_outer_deadline(self):
        anchor = self.anchor()
        envelope = d.guest_envelope(anchor, recovery_id="syntheticrecovery", guest_boot_id=self.boot,
                                    guest_now_ns=1020*d.NS)
        self.assertEqual(envelope["guest_outer_deadline_ns"], 1191*d.NS)
        self.assertEqual(envelope["deadline_ns"], 1181*d.NS)
        self.assertEqual(envelope["preparation_deadline_ns"], 1053*d.NS)
        self.assertEqual(envelope["preparation_deadline_ns"]-envelope["issued_ns"], 33*d.NS)
        with self.assertRaisesRegex(ValueError, "RECOVERY_DELIVERY_GUEST_TIME_EXHAUSTED"):
            d.guest_envelope(anchor, recovery_id="syntheticrecovery", guest_boot_id=self.boot, guest_now_ns=1053*d.NS)
        with self.assertRaisesRegex(ValueError, "RECOVERY_DELIVERY_BOOT"):
            d.remaining(envelope, anchor, guest_boot_id="different", guest_now_ns=1020*d.NS)

    def test_changed_anchor_or_envelope_cannot_extend_remaining(self):
        anchor = self.anchor()
        envelope = d.guest_envelope(anchor, recovery_id="syntheticrecovery", guest_boot_id=self.boot,
                                    guest_now_ns=901*d.NS)
        for field in ("deadline_ns", "guest_outer_deadline_ns", "issued_ns", "stop_ns"):
            with self.subTest(field=field):
                altered = {**envelope, field:envelope[field]+1}
                with self.assertRaises(ValueError):
                    d.remaining(altered, anchor, guest_boot_id=self.boot, guest_now_ns=902*d.NS)
        with self.assertRaisesRegex(ValueError, "RECOVERY_DELIVERY_INTEGER"):
            d.remaining(envelope, anchor, guest_boot_id=self.boot, guest_now_ns=902*d.NS, owner_runtime_ns=121*d.NS)


if __name__ == "__main__":
    unittest.main()
