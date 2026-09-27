"""Actual child-process pipes and clock-boundary checks; no guest execution."""
from __future__ import annotations

import sys
import time
import unittest

from e3_host import q2_reconciliation_delivery as d


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux BOOTTIME/process groups")
class ReconciliationMemoryTransport(unittest.TestCase):
    def capture(self, source, data=b"", *, limit=None, prior=0, callback=None, duration=4):
        window = d.Window()
        return d.capture_memory([sys.executable, "-I", "-B", "-c", source], data,
            window=window, until_ns=window.issued_ns + int(duration * d.NS),
            prior_bytes=prior, output_limit=limit, on_stdout_line=callback)

    def test_full_duplex_large_input_does_not_deadlock(self):
        raw = b"x" * (1024 * 1024)
        source = "import sys;sys.stdout.buffer.write(b'hello\\n');sys.stdout.flush();x=sys.stdin.buffer.read();print(len(x));sys.stderr.write('done')"
        lines = []
        result = self.capture(source, raw, callback=lines.append)
        self.assertTrue(result["record"]["complete"])
        self.assertEqual(result["stdout"], b"hello\n1048576\n")
        self.assertEqual(result["stderr"], b"done")
        self.assertEqual(lines, [b"hello\n", b"1048576\n"])
        self.assertEqual(result["record"]["input_bytes_sent"], len(raw))
        self.assertFalse(result["record"]["remote_stop_proven"])

    def test_prior_phases_share_one_total_output_pool(self):
        result = self.capture("import sys;sys.stdout.buffer.write(b'x'*2000)", prior=d.OUTPUT_LIMIT - 1024)
        self.assertFalse(result["record"]["complete"])
        self.assertEqual(result["record"]["error"], "RECONCILIATION_CAPTURE_LIMIT")
        self.assertEqual(result["record"]["total_captured_bytes"], d.OUTPUT_LIMIT)
        self.assertEqual(len(result["stdout"]), 1024)

    def test_nonzero_exit_keeps_eof_without_claiming_success(self):
        result = self.capture("import sys;print('failed');sys.exit(3)")
        self.assertFalse(result["record"]["complete"])
        self.assertEqual(result["record"]["returncode"], 3)
        self.assertEqual(result["record"]["eof"], ["stderr", "stdout"])

    def test_exited_parent_with_open_descendant_pipe_is_incomplete(self):
        source = "import os,time;pid=os.fork();time.sleep(3) if pid==0 else None;os._exit(0)"
        started = time.monotonic()
        result = self.capture(source, duration=0.4)
        self.assertLess(time.monotonic() - started, 2)
        self.assertFalse(result["record"]["complete"])
        self.assertEqual(result["record"]["error"], "RECONCILIATION_CAPTURE_TIMEOUT")
        self.assertFalse(result["record"]["remote_stop_proven"])

    def test_observer_failure_cannot_be_accepted_as_transport_success(self):
        def fail(_):
            raise ValueError("SYNTHETIC_SIGNAL_REJECTED")
        result = self.capture("print('hello')", callback=fail)
        self.assertFalse(result["record"]["complete"])
        self.assertEqual(result["record"]["error"], "SYNTHETIC_SIGNAL_REJECTED")

    def test_new_phase_cannot_extend_original_deadline(self):
        window = d.Window()
        with self.assertRaises(ValueError):
            d.capture_memory([sys.executable, "-c", "pass"], b"", window=window,
                until_ns=window.deadline_ns + 1)

    def test_suspension_spends_window_even_if_monotonic_does_not(self):
        now = {"mono": 100 * d.NS, "boot": 100 * d.NS}
        window = d.Window(monotonic=lambda: now["mono"], boottime=lambda: now["boot"])
        now["boot"] += 5 * d.NS
        with self.assertRaisesRegex(ValueError, "HOST_CLOCK_DIVERGED"):
            window.guard()


class ReconciliationEnvelope(unittest.TestCase):
    def anchor(self):
        return d.legacy.make_clock_anchor(host_issued_ns=100 * d.NS,
            host_deadline_ns=400 * d.NS, host_probe_send_ns=110 * d.NS,
            host_probe_receive_ns=112 * d.NS, guest_sample_ns=1000 * d.NS,
            guest_boot_id="12345678-1234-1234-1234-123456789abc",
            expected_boot_id="12345678-1234-1234-1234-123456789abc")

    def test_first_probe_and_host_elapsed_are_inside_preparation(self):
        anchor = self.anchor()
        value = d.guest_envelope(anchor, attempt_id="reconcile01",
            guest_boot_id=anchor["guest_boot_id"], guest_now_ns=1010 * d.NS)
        # Conservative origin 986s: both caps spend the initial 24s.
        self.assertEqual(value["deadline_ns"], 1256 * d.NS)
        self.assertLessEqual(value["preparation_deadline_ns"], 1126 * d.NS)
        self.assertLess(value["preparation_deadline_ns"], value["issued_ns"] + 140 * d.NS)
        d.validate_envelope(anchor, value, attempt_id="reconcile01",
            boot_id=anchor["guest_boot_id"], now_ns=1011 * d.NS, preparation=True)
        changed = dict(value, preparation_deadline_ns=value["preparation_deadline_ns"] + d.NS)
        with self.assertRaises(ValueError):
            d.validate_envelope(anchor, changed, attempt_id="reconcile01",
                boot_id=anchor["guest_boot_id"], now_ns=1011 * d.NS, preparation=True)

    def test_late_driver_and_collector_do_not_obtain_another_window(self):
        anchor = self.anchor()
        value = d.guest_envelope(anchor, attempt_id="reconcile01",
            guest_boot_id=anchor["guest_boot_id"], guest_now_ns=1010 * d.NS)
        with self.assertRaises(ValueError):
            d.validate_envelope(anchor, value, attempt_id="reconcile01",
                boot_id=anchor["guest_boot_id"], now_ns=value["preparation_deadline_ns"], preparation=True)
        with self.assertRaises(ValueError):
            d.validate_envelope(anchor, value, attempt_id="reconcile01",
                boot_id=anchor["guest_boot_id"], now_ns=value["guest_outer_deadline_ns"])


if __name__ == "__main__":
    unittest.main()
