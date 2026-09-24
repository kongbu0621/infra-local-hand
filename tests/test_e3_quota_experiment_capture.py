"""LOCAL_PIPE collection; controller identities are LOGIC_ONLY fixtures.

Only Python test children are started. No systemd/quota, service, host setup or
real-unit stop runs. All test descendants are independently cleaned up here.
"""
from dataclasses import replace
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from admin.local_hand_quota_observer import experiment_capture as c
from admin.local_hand_quota_observer.admission import Rejected
from admin.local_hand_quota_observer.controller_guard import ControllerObservation
from test_e3_quota_monitor import binding


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux anonymous diagnostic pipes")
class ExperimentCaptureTests(unittest.TestCase):
    def child(self, source, *, bufsize=0, stdout=subprocess.PIPE):
        process = subprocess.Popen((sys.executable, "-I", "-B", "-c", source),
                                   stdin=subprocess.DEVNULL, stdout=stdout,
                                   stderr=subprocess.PIPE, bufsize=bufsize, start_new_session=True)
        self.addCleanup(self.cleanup, process)
        return process

    @staticmethod
    def cleanup(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def inputs(self, process, *, duration_ns=1_500_000_000):
        now = c.boottime_ns()
        bound = binding(now_ns=now, phase_deadline_ns=now + 2_000_000_000)
        return bound, dict(operation="run", collection_started_ns=now,
                           collection_deadline_ns=now + duration_ns)

    def observation(self, process, bound):
        out, err = (os.fstat(stream.fileno()) for stream in (process.stdout, process.stderr))
        return ControllerObservation("lhqcontroller-test.service", "d" * 32,
                                     "/controller-test.slice/lhqcontroller-test.service", 71, 72,
                                     bound.manifest.boot_id, process.pid, bound.issued_ns,
                                     out.st_dev, out.st_ino, err.st_dev, err.st_ino)

    def test_raw_bytes_complete_with_unknown_controller_never_implies_stop_or_success(self):
        process = self.child("import os; os.write(1,b'out\\x00\\xff'); os.write(2,b'err'); raise SystemExit(7)")
        bound, args = self.inputs(process)
        with patch.object(subprocess.Popen, "__init__", side_effect=AssertionError("must not spawn")), \
                patch.object(process, "kill", side_effect=AssertionError("must not signal")), \
                patch.object(process, "wait", side_effect=AssertionError("must not wait")):
            result = c.capture_existing(process, bound, **args)
        self.assertTrue(result.capture_complete)
        self.assertEqual((result.stdout, result.stderr), (b"out\x00\xff", b"err"))
        self.assertEqual(result.client_returncode, 7)
        self.assertIsNone(result.original_controller)
        self.assertIsNone(result.original_query_invocation_id)
        self.assertTrue(result.independent_stop_required)
        self.assertTrue(result.stdout_closed and result.stderr_closed)
        self.assertNotEqual(result.stdout_pipe_identity, result.stderr_pipe_identity)
        self.assertIs(result.original_binding, bound)

    def test_independent_controller_and_original_query_identity_are_retained(self):
        process = self.child("print('diagnostic only')")
        bound, args = self.inputs(process)
        controller = self.observation(process, bound)
        result = c.capture_existing(process, bound, controller=controller,
                                    original_query_invocation_id="a" * 32, **args)
        self.assertTrue(result.capture_complete)
        self.assertIs(result.original_controller, controller)
        self.assertEqual(result.original_query_invocation_id, "a" * 32)
        self.assertTrue(result.independent_stop_required)

    def test_stdout_overflow_retains_bounded_prefix_without_claiming_eof(self):
        process = self.child("import os; os.write(1,b'x'*200000)")
        bound, args = self.inputs(process)
        result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.error, "CAPTURE_BYTE_LIMIT")
        self.assertEqual(result.stdout, b"x" * c.MAX_CAPTURE_BYTES)
        self.assertFalse(result.stdout_eof or result.capture_complete)
        self.assertTrue(result.stdout_closed)

    def test_stderr_has_its_own_limit(self):
        process = self.child("import os; os.write(2,b'e'*20000)")
        bound, args = self.inputs(process)
        result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.error, "CAPTURE_BYTE_LIMIT")
        self.assertEqual(result.stderr, b"e" * c.MAX_STDERR_BYTES)

    def test_stderr_consumes_shared_total_budget(self):
        process = self.child("import os; os.write(2,b'e'*16384); os.write(1,b'x'*131072)")
        bound, args = self.inputs(process)
        result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.error, "CAPTURE_BYTE_LIMIT")
        self.assertEqual(len(result.stdout) + len(result.stderr), c.MAX_CAPTURE_BYTES)
        self.assertGreater(len(result.stderr), 0)
        self.assertLessEqual(len(result.stderr), c.MAX_STDERR_BYTES)

    def test_exact_shared_limit_and_both_eofs_are_complete(self):
        process = self.child("import os; os.write(2,b'e'*16384); os.write(1,b'x'*114688)")
        bound, args = self.inputs(process)
        result = c.capture_existing(process, bound, **args)
        self.assertTrue(result.capture_complete)
        self.assertEqual(len(result.stdout) + len(result.stderr), c.MAX_CAPTURE_BYTES)

    def test_client_exit_with_descendant_holding_pipes_is_not_eof_or_unit_stop(self):
        process = self.child("import os,time; child=os.fork(); "
                             "time.sleep(10) if child==0 else os.write(1,b'parent-exit')")
        bound, args = self.inputs(process, duration_ns=150_000_000)
        result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.stdout, b"parent-exit")
        self.assertEqual(result.client_returncode, 0)
        self.assertEqual(result.error, "CAPTURE_DEADLINE_EXPIRED")
        self.assertFalse(result.stdout_eof or result.stderr_eof or result.capture_complete)
        self.assertTrue(result.independent_stop_required)

    def test_eof_with_running_client_does_not_claim_client_exit(self):
        process = self.child("import os,time; os.close(1); os.close(2); time.sleep(10)")
        bound, args = self.inputs(process, duration_ns=150_000_000)
        result = c.capture_existing(process, bound, **args)
        self.assertTrue(result.stdout_eof and result.stderr_eof)
        self.assertIsNone(result.client_returncode)
        self.assertEqual(result.error, "CAPTURE_DEADLINE_EXPIRED")
        self.assertFalse(result.capture_complete)

    def test_timeout_preserves_partial_prefix_and_does_not_kill_or_refresh(self):
        process = self.child("import os,time; os.write(1,b'partial'); time.sleep(10)")
        bound, args = self.inputs(process, duration_ns=150_000_000)
        result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.stdout, b"partial")
        self.assertEqual(result.collection_deadline_ns, args["collection_deadline_ns"])
        self.assertIsNone(process.poll())
        self.assertFalse(result.stdout_eof)
        self.assertEqual(result.error, "CAPTURE_DEADLINE_EXPIRED")

    def test_recovery_collects_expired_original_ticket_without_renewal(self):
        process = self.child("print('retained original state')")
        bound, args = self.inputs(process)
        bound = replace(bound, issued_ns=bound.issued_ns - 4_000_000_000,
                        deadline_ns=bound.issued_ns - 2_000_000_000)
        args["operation"] = "recover_original"
        result = c.capture_existing(process, bound, **args)
        self.assertTrue(result.capture_complete)
        self.assertIs(result.original_binding, bound)
        self.assertLess(result.original_binding.deadline_ns, result.collection_started_ns)
        self.assertTrue(result.independent_stop_required)

    def test_run_keeps_late_cleanup_diagnostic_without_changing_original_deadline(self):
        process = self.child("import time,os; time.sleep(0.075); "
                             "os.write(1,b'{\"status\":\"UNKNOWN\",\"cleanup_reason\":\"TIMEOUT\"}\\n')")
        bound, args = self.inputs(process)
        bound = replace(bound, deadline_ns=bound.issued_ns + 30_000_000)
        result = c.capture_existing(process, bound, **args)
        self.assertTrue(result.capture_complete)
        self.assertEqual(result.stdout, b'{"status":"UNKNOWN","cleanup_reason":"TIMEOUT"}\n')
        self.assertIs(result.original_binding, bound)
        self.assertGreater(c.boottime_ns(), bound.deadline_ns)
        self.assertTrue(result.independent_stop_required)

    def test_expired_collection_window_reads_nothing_and_does_not_extend(self):
        process = self.child("print('already buffered')")
        bound, args = self.inputs(process)
        process.wait(timeout=3)
        args["collection_deadline_ns"] = args["collection_started_ns"] + 1
        result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.error, "CAPTURE_DEADLINE_EXPIRED")
        self.assertEqual(result.stdout, b"")
        self.assertFalse(result.stdout_eof or result.stderr_eof)

    def test_partial_read_error_is_preserved_and_does_not_retry(self):
        process = self.child("import os; os.write(1,b'x'*8192)")
        bound, args = self.inputs(process)
        original_read, calls = os.read, []

        def read(fd, size):
            calls.append(fd)
            if len(calls) == 2:
                raise OSError("synthetic failure")
            return original_read(fd, size)

        with patch.object(c.os, "read", side_effect=read):
            result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.stdout, b"x" * 4096)
        self.assertEqual(result.error, "CAPTURE_IO_UNCERTAIN")
        self.assertEqual(len(calls), 2)
        self.assertTrue(result.stdout_closed and result.stderr_closed)

    def test_interrupt_preserves_prefix(self):
        process = self.child("import os; os.write(1,b'x'*8192)")
        bound, args = self.inputs(process)
        original_read, calls = os.read, []

        def read(fd, size):
            calls.append(fd)
            if len(calls) == 2:
                raise KeyboardInterrupt
            return original_read(fd, size)

        with patch.object(c.os, "read", side_effect=read):
            result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.stdout, b"x" * 4096)
        self.assertEqual(result.error, "CAPTURE_INTERRUPTED")
        self.assertFalse(result.capture_complete)

    def test_close_error_does_not_overwrite_first_failure_or_invent_eof(self):
        process = self.child("import os; os.write(1,b'x'*200000)")
        bound, args = self.inputs(process)
        actual_close = process.stdout.close

        def failing_close():
            actual_close()
            raise OSError("synthetic close failure")

        process.stdout.close = failing_close
        try:
            result = c.capture_existing(process, bound, **args)
        finally:
            process.stdout.close = actual_close
        self.assertEqual(result.error, "CAPTURE_BYTE_LIMIT")
        self.assertEqual(result.close_errors, ("STDOUT_CLOSE_UNCERTAIN",))
        self.assertFalse(result.stdout_eof)
        self.assertTrue(result.stdout_closed)

    def test_wrong_known_pipe_binding_rejects_and_closes_without_reading(self):
        process = self.child("print('unbound')")
        bound, args = self.inputs(process)
        controller = replace(self.observation(process, bound), stdout_pipe_inode=1)
        result = c.capture_existing(process, bound, controller=controller, **args)
        self.assertEqual(result.error, "CAPTURE_PIPE_CHANGED")
        self.assertEqual(result.stdout, b"")
        self.assertTrue(result.stdout_closed)

    def test_repeated_collection_rejects_closed_original_pipes(self):
        process = self.child("print('once')")
        bound, args = self.inputs(process)
        result = c.capture_existing(process, bound, **args)
        with self.assertRaisesRegex(Rejected, "CAPTURE_UNBUFFERED_PIPES_REQUIRED"):
            c.capture_existing(process, bound, **args)
        self.assertEqual(result.stdout, b"once\n")

    def test_bad_client_buffering_deadline_or_identity_is_rejected_before_transfer(self):
        process = self.child("pass")
        bound, args = self.inputs(process)
        with self.assertRaisesRegex(Rejected, "CAPTURE_ORIGINAL_IDENTITY_REQUIRED"):
            c.capture_existing(object(), bound, **args)
        for changes, reason in (({"operation": "retry"}, "CAPTURE_OPERATION"),
                                ({"collection_deadline_ns": bound.issued_ns + 121_000_000_000}, "CAPTURE_SUPERVISION_DEADLINE"),
                                ({"collection_started_ns": True}, "INTEGER"),
                                ({"original_query_invocation_id": "guess"}, "TOKEN")):
            with self.subTest(changes=changes), self.assertRaisesRegex(Rejected, reason):
                c.capture_existing(process, bound, **(args | changes))
        self.assertFalse(process.stdout.closed)
        buffered = self.child("pass", bufsize=-1)
        with self.assertRaisesRegex(Rejected, "CAPTURE_UNBUFFERED_PIPES_REQUIRED"):
            c.capture_existing(buffered, bound, **args)

    def test_regular_file_reader_is_rejected_without_creating_eof(self):
        process = self.child("pass")
        bound, args = self.inputs(process)
        process.stdout.close()
        with tempfile.TemporaryFile("w+b", buffering=0) as stream:
            process.stdout = stream
            result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.error, "CAPTURE_ANONYMOUS_READER_REQUIRED")
        self.assertFalse(result.stdout_eof)

    def test_aliased_pipe_streams_are_rejected(self):
        process = self.child("pass")
        bound, args = self.inputs(process)
        process.stdout.close()
        process.stdout = os.fdopen(os.dup(process.stderr.fileno()), "rb", buffering=0)
        result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.error, "CAPTURE_PIPE_ALIAS")
        self.assertFalse(result.stdout_eof or result.stderr_eof)

    def test_named_fifo_is_not_accepted_as_original_anonymous_output(self):
        process = self.child("pass")
        bound, args = self.inputs(process)
        process.stdout.close()
        with tempfile.TemporaryDirectory() as directory:
            fifo = os.path.join(directory, "named-fifo")
            os.mkfifo(fifo)
            process.stdout = os.fdopen(os.open(fifo, os.O_RDONLY | os.O_NONBLOCK), "rb", buffering=0)
            result = c.capture_existing(process, bound, **args)
        self.assertEqual(result.error, "CAPTURE_ANONYMOUS_READER_REQUIRED")
        self.assertFalse(result.stdout_eof)


if __name__ == "__main__":
    unittest.main()
