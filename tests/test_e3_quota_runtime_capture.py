"""Actual finite local subprocess pipes and LOGIC_ONLY systemd argv checks.

Only the current Python executable is launched. No systemd command, quota call,
privileged service, account, mount or real fixture is started by these tests.
Capture completion concerns the command client, never a query unit's stop proof.
"""
from dataclasses import replace
import os
from pathlib import Path
import signal
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from test_e3_quota_monitor import binding, decode, fixture, NOW

if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import admission as a, protected_inputs as p, systemd_runtime as r
    from test_e3_quota_worker import runtime


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux anonymous pipe capture")
class CaptureTests(unittest.TestCase):
    def capture(self, source, limit=128):
        capture = r.Capture(limit)
        self.addCleanup(self.cleanup_capture, capture)
        capture.start((sys.executable, "-I", "-B", "-c", source))
        return capture

    @staticmethod
    def cleanup_capture(capture):
        capture.kill_client()
        if capture.process is not None:
            capture.process.wait(timeout=3)
        capture.close_pipes()

    def until(self, capture, predicate, *, timeout=3):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            capture.pump()
            if predicate():
                return
            time.sleep(0.001)
        self.fail(f"capture failed to settle in {timeout}s; error={capture.error!r}, eof={capture.eof!r}")

    def test_actual_anonymous_pipes_are_nonblocking_and_preserve_exact_streams(self):
        capture = self.capture("import os; os.write(1,b'out\\x00\\xff'); os.write(2,b'err\\n')")
        self.assertFalse(os.get_blocking(capture.process.stdout.fileno()))
        self.assertFalse(os.get_blocking(capture.process.stderr.fileno()))
        self.until(capture, lambda: capture.settled)
        self.assertEqual(bytes(capture.stdout), b"out\x00\xff")
        self.assertEqual(bytes(capture.stderr), b"err\n")
        self.assertEqual(capture.process.returncode, 0)
        self.assertTrue(capture.done)
        capture.close_pipes()
        self.assertTrue(capture.process.stdout.closed and capture.process.stderr.closed)

    def test_exit_alone_does_not_complete_capture_before_both_eofs(self):
        capture = self.capture("import os; os.write(1,b'pending'); os.write(2,b'stderr')")
        capture.process.wait(timeout=3)
        self.assertTrue(capture.exited)
        self.assertEqual(capture.eof, set())
        self.assertFalse(capture.settled)
        self.assertFalse(capture.done)
        self.until(capture, lambda: capture.done)
        self.assertEqual(bytes(capture.stdout), b"pending")
        self.assertEqual(bytes(capture.stderr), b"stderr")

    def test_both_eofs_do_not_complete_a_still_running_process(self):
        capture = self.capture("import os,time; os.close(1); os.close(2); time.sleep(1)")
        self.until(capture, lambda: len(capture.eof) == 2)
        self.assertFalse(capture.exited)
        self.assertFalse(capture.settled)
        self.assertFalse(capture.done)
        capture.kill_client()
        self.until(capture, lambda: capture.settled)
        self.assertEqual(capture.process.returncode, -signal.SIGKILL)

    def test_stdout_and_stderr_share_one_limit_and_overflow_can_still_settle(self):
        capture = self.capture("import os; os.write(1,b'a'*4096); os.write(2,b'b'*4096)", limit=67)
        maximum = 0
        end = time.monotonic() + 3
        while time.monotonic() < end:
            capture.pump()
            maximum = max(maximum, len(capture.stdout) + len(capture.stderr))
            self.assertLessEqual(maximum, 67)
            if capture.settled:
                break
            time.sleep(0.001)
        self.assertTrue(capture.settled)
        self.assertEqual(maximum, 67)
        self.assertEqual(capture.error, "CAPTURE_BYTE_LIMIT")
        self.assertFalse(capture.done)
        self.assertEqual(capture.process.returncode, 0)

    def test_exact_shared_byte_limit_is_not_overflow(self):
        capture = self.capture("import os; os.write(1,b'a'*32); os.write(2,b'b'*32)", limit=64)
        self.until(capture, lambda: capture.settled)
        self.assertEqual((bytes(capture.stdout), bytes(capture.stderr)), (b"a" * 32, b"b" * 32))
        self.assertIsNone(capture.error)
        self.assertTrue(capture.done)

    def test_nonzero_return_code_is_retained_separately_from_capture_completion(self):
        capture = self.capture("import os; os.write(2,b'failed'); raise SystemExit(7)")
        self.until(capture, lambda: capture.settled)
        self.assertTrue(capture.done)  # Fully collected does not mean command success.
        self.assertEqual(capture.process.returncode, 7)
        self.assertEqual(bytes(capture.stderr), b"failed")

    def test_kill_client_does_not_synthesize_pipe_eof_or_replacement_process(self):
        capture = self.capture("import os,time; os.write(1,b'started'); time.sleep(5)")
        self.until(capture, lambda: bool(capture.stdout))
        process = capture.process
        before_eof = set(capture.eof)
        capture.kill_client()
        self.assertEqual(capture.eof, before_eof)
        self.assertIs(capture.process, process)
        self.until(capture, lambda: capture.settled)
        self.assertEqual(capture.process.returncode, -signal.SIGKILL)
        self.assertEqual(bytes(capture.stdout), b"started")
        capture.kill_client()  # Already reaped command, no additional process.
        self.assertIs(capture.process, process)

    def test_io_error_is_sticky_even_when_later_reads_and_exit_settle(self):
        capture = self.capture("import os; os.write(1,b'facts')")
        with patch.object(r.os, "read", side_effect=OSError(5, "synthetic pipe read error")):
            capture.pump()
        self.assertEqual(capture.error, "CAPTURE_IO_UNCERTAIN")
        self.until(capture, lambda: capture.settled)
        self.assertEqual(bytes(capture.stdout), b"facts")
        self.assertFalse(capture.done)
        self.assertEqual(capture.error, "CAPTURE_IO_UNCERTAIN")

    def test_unstarted_capture_invalid_limit_and_second_start_do_not_launch(self):
        for limit in (0, True, 32769):
            with self.subTest(limit=limit), self.assertRaises(a.Rejected):
                r.Capture(limit)
        empty = r.Capture(32)
        empty.pump()
        self.assertEqual(empty.error, "CAPTURE_SETUP_UNCERTAIN")
        self.assertFalse(empty.exited or empty.done or empty.settled)
        capture = self.capture("pass")
        original = capture.process
        with self.assertRaisesRegex(a.Rejected, "CAPTURE_ALREADY_STARTED"):
            capture.start((sys.executable, "-I", "-B", "-c", "raise SystemExit(99)"))
        self.assertIs(capture.process, original)
        self.until(capture, lambda: capture.settled)
        self.assertEqual(capture.process.returncode, 0)

    def test_environment_is_fixed_and_inheritable_control_fd_is_not_passed(self):
        reader, writer = os.pipe()
        try:
            os.set_inheritable(writer, True)
            program = (
                "import os; "
                f"fd={writer}; "
                "print(os.environ.get('LH_TEST_PRIVATE_TOKEN', 'missing')); "
                "\ntry: os.fstat(fd)\nexcept OSError: print('fd-closed')\nelse: raise SystemExit(9)"
            )
            with patch.dict(os.environ, {"LH_TEST_PRIVATE_TOKEN": "synthetic-sensitive-value"}):
                capture = self.capture(program)
            self.until(capture, lambda: capture.settled)
            self.assertEqual(capture.process.returncode, 0)
            self.assertEqual(bytes(capture.stdout), b"missing\nfd-closed\n")
        finally:
            os.close(reader)
            os.close(writer)


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux fixed systemd assembly")
class UnitCommandTests(unittest.TestCase):
    def fixture(self):
        config = runtime()
        value = fixture()
        value["cgroup_parent"] = "/" + config.query_slice
        return config, binding(decode(value))

    def command(self, config=None, bound=None, *, config_path="/synthetic/admin/runtime.json",
                control_dir="/synthetic/control", now_ns=NOW):
        original_config, original_binding = self.fixture()
        return r.unit_command(config or original_config, bound or original_binding,
                              config_path, control_dir, now_ns=now_ns)

    def test_fixed_argv_binds_unit_worker_ticket_and_constrained_properties(self):
        config, bound = self.fixture()
        command = self.command(config, bound)
        self.assertIsInstance(command, tuple)
        self.assertEqual(command[:5], (config.systemd_run_path, "--system", "--quiet", "--pipe",
                                      "--unit=" + bound.unit))
        separator = command.index("--")
        self.assertEqual(command[separator + 1:], (config.python_path, "-I", "-B", config.worker_path,
                                                  "/synthetic/admin/runtime.json", config.digest,
                                                  p.encode_ticket(bound)))
        self.assertEqual(command[5], "--no-ask-password")
        props = dict(argument.removeprefix("--property=").split("=", 1) for argument in command[6:separator])
        self.assertEqual(len(props), separator - 6)
        self.assertEqual({key: props[key] for key in ("Slice", "Type", "ExitType", "RemainAfterExit",
                                                     "Restart", "KillMode")},
                         {"Slice": config.query_slice, "Type": "exec", "ExitType": "cgroup",
                          "RemainAfterExit": "yes", "Restart": "no", "KillMode": "control-group"})
        self.assertEqual(props["InaccessiblePaths"], "/synthetic/control")
        self.assertEqual(props["ReadWritePaths"], bound.slot.path)
        self.assertEqual(props["CapabilityBoundingSet"], "CAP_SYS_ADMIN CAP_DAC_READ_SEARCH")
        self.assertEqual(props["PrivateUsers"], "no")
        for key in ("NoNewPrivileges", "PrivateNetwork", "PrivateDevices", "PrivateMounts"):
            self.assertEqual(props[key], "yes")
        self.assertEqual(props["MemoryMax"], str(config.memory_bytes))
        self.assertEqual(props["TasksMax"], str(config.tasks_max))
        self.assertNotIn("--user", command)
        self.assertFalse(any(argument.startswith("--setenv=") for argument in command))

    def test_only_remaining_original_time_is_available_and_short_deadline_rejected(self):
        config, bound = self.fixture()
        command = self.command(config, bound, now_ns=bound.deadline_ns - 1234567)
        self.assertIn("--property=RuntimeMaxSec=1234us", command)
        self.assertIn("--property=TimeoutStartSec=1234us", command)
        for now in (bound.issued_ns - 1, bound.deadline_ns - 999, bound.deadline_ns, bound.deadline_ns + 1):
            with self.subTest(now=now), self.assertRaises(a.Rejected):
                self.command(config, bound, now_ns=now)

    def test_wrong_slice_and_nonadministrative_query_identity_are_rejected(self):
        config, bound = self.fixture()
        with self.assertRaisesRegex(a.Rejected, "DEDICATED_SLICE_REQUIRED"):
            self.command(replace(config, query_slice="other.slice"), bound)
        for uid, euid in ((1000, 0), (0, 1000), (1000, 1000)):
            manifest = replace(bound.manifest, query_uid=uid, query_euid=euid)
            with self.subTest(uid=uid, euid=euid), self.assertRaisesRegex(a.Rejected, "ADMIN_QUERY_UID_REQUIRED"):
                self.command(config, replace(bound, manifest=manifest))

    def test_control_installation_and_target_root_cannot_overlap(self):
        config, bound = self.fixture()
        cases = (
            {"control_dir": "/synthetic/admin"},
            {"control_dir": config.worker_path + "/child"},
            {"control_dir": bound.slot.path},
            {"control_dir": bound.slot.path + "/child"},
            {"control_dir": str(Path(bound.slot.path).parent)},
            {"config_path": bound.slot.path + "/runtime.json"},
            {"config_path": "/synthetic/control/config.json"},
            {"config_path": "/synthetic/../runtime.json"},
            {"control_dir": "/synthetic/control;arbitrary"},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaises(a.Rejected):
                self.command(config, bound, **arguments)


if __name__ == "__main__":
    unittest.main()
