"""Failure evidence stays finite and cannot change the original Q2 checks."""
import errno
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
import time
from types import SimpleNamespace
import unittest
from unittest import mock

from local_hand_jobs import quota_contract as q
from admin.local_hand_quota_observer import q2_entry as entry
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import q2_coordinator as coordinator
    from admin.local_hand_quota_observer import q2_listener
    from admin.local_hand_quota_observer.systemd_runtime import Capture


class EntryDiagnosticsTests(unittest.TestCase):
    def test_original_argument_rejection_retains_exit_and_fixed_code(self):
        with mock.patch.object(entry.os, "write") as write:
            self.assertEqual(2, entry.main([]))
        descriptor, raw = write.call_args.args
        self.assertEqual(2, descriptor)
        marker, raw = raw.split(b"\n", 1)
        self.assertEqual(b"Q2_ENTRY_REJECTED", marker)
        value = json.loads(raw)
        self.assertEqual("ARGUMENTS", value["code"])
        self.assertEqual("entry", value["role"])
        self.assertLessEqual(len(raw), entry.DIAGNOSTIC_LIMIT)
        self.assertTrue(value["frames"])
        self.assertIsNotNone(entry.safe_diagnostic(value))

    def test_os_failure_retains_errno_without_text_paths_or_inputs(self):
        error = PermissionError(errno.EACCES, "SECRET MESSAGE", "/SECRET/PATH")
        with mock.patch.object(entry, "bootstrap", side_effect=error), mock.patch.object(entry.os, "write") as write:
            self.assertEqual(2, entry.main(["admission", "/SECRET/CONFIG", "SECRET_SESSION"]))
        raw = write.call_args.args[1]
        self.assertNotIn(b"SECRET", raw)
        value = json.loads(raw.split(b"\n", 1)[1])
        self.assertEqual(("admission", "PermissionError", errno.EACCES, None),
                         (value["role"], value["type"], value["errno"], value["code"]))

    def test_arbitrary_value_error_text_is_not_a_reason_code(self):
        value = entry.diagnostic(ValueError("PRIVATE_SESSION_VALUE"), "private-role")
        self.assertIsNone(value["code"])
        self.assertEqual("entry", value["role"])

    def test_arbitrary_exception_code_attribute_is_not_relayed(self):
        class PrivateError(ValueError):
            code = "PRIVATE_SESSION_VALUE"
        self.assertIsNone(entry.diagnostic(PrivateError("PRIVATE"), "listener")["code"])

    def test_source_mapping_uses_native_paths_but_keeps_posix_labels(self):
        for entry_path in (PureWindowsPath(r"C:\source\tools\admin\local_hand_quota_observer\q2_entry.py"),
                           PurePosixPath("/source/tools/admin/local_hand_quota_observer/q2_entry.py")):
            with self.subTest(entry_path=str(entry_path)):
                namespace = {}
                filename = str(entry_path.parent / "q2_listener.py")
                exec(compile("def fail():\n raise ValueError('PRIVATE')\n", filename, "exec"), namespace)
                try:
                    namespace["fail"]()
                except ValueError as error:
                    with mock.patch.object(entry, "Path", return_value=SimpleNamespace(absolute=lambda: entry_path)):
                        value = entry.diagnostic(error, "listener")
                self.assertEqual([dict(source="admin/local_hand_quota_observer/q2_listener.py", function="fail", line=2)],
                                 value["frames"])

    def test_broken_stderr_keeps_original_rejection(self):
        with mock.patch.object(entry.os, "write", side_effect=BrokenPipeError):
            self.assertEqual(2, entry.main([]))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux Q2 runtime")
    def test_success_is_silent_and_calls_the_original_role_once(self):
        config = object()
        with mock.patch.object(entry, "bootstrap", return_value=config), \
             mock.patch.object(q2_listener, "listener") as listener, mock.patch.object(entry.os, "write") as write:
            self.assertEqual(0, entry.main(["listener", "/synthetic/config", "a" * 64]))
        listener.assert_called_once_with(config)
        write.assert_not_called()

    def test_only_allowlisted_source_frames_survive_and_count_is_bounded(self):
        namespace = {}
        source = str(Path(entry.__file__).absolute().parent / "q2_listener.py")
        exec(compile("def repeated(n):\n if n: return repeated(n-1)\n raise ValueError('PRIVATE')\n", source, "exec"), namespace)
        try:
            namespace["repeated"](20)
        except ValueError as error:
            value = entry.diagnostic(error, "listener")
        self.assertEqual(8, len(value["frames"]))
        self.assertTrue(value["frames_truncated"])
        self.assertTrue(all(item["source"] == "admin/local_hand_quota_observer/q2_listener.py" for item in value["frames"]))
        self.assertNotIn("PRIVATE", json.dumps(value))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux Q2 coordinator")
class ManagementDiagnosticsTests(unittest.TestCase):
    def part(self, stderr=b"private stderr", *, error=None, returncode=2):
        process = SimpleNamespace(returncode=returncode, poll=mock.Mock(side_effect=AssertionError("extra poll")))
        capture = SimpleNamespace(process=process, error=error, stdout=bytearray(b"private stdout"),
            stderr=bytearray(stderr), eof={"stdout"}, pump=mock.Mock(side_effect=AssertionError("extra pump")))
        return dict(capture=capture, invocation="a" * 32, stop_attempted=False, stop_ok=False,
            terminal={"Result": "timeout", "ExecMainCode": "2", "ExecMainStatus": "15", "SECRET": "private"}, after=None)

    def emit(self, part, role="listener"):
        with mock.patch.object(coordinator.os, "write") as write:
            coordinator.management_failure(role, part)
        self.assertEqual(1, write.call_count)
        fd, raw = write.call_args.args
        self.assertEqual(2, fd)
        self.assertLessEqual(len(raw), coordinator.DIAGNOSTIC_LIMIT)
        return json.loads(raw), raw

    def test_retains_existing_facts_without_reads_or_raw_output(self):
        for role in ("listener", "admission"):
            with self.subTest(role=role):
                part = self.part()
                value, raw = self.emit(part, role)
                self.assertEqual((role, 2, "a" * 32), (value["role"], value["returncode"], value["invocation_id"]))
                self.assertEqual(["stdout"], value["eof"])
                self.assertEqual("timeout", value["terminal"]["Result"])
                self.assertEqual(hashlib.sha256(b"private stderr").hexdigest(), value["captured_stderr_sha256"])
                self.assertNotIn(b"private", raw)
                self.assertNotIn(b"SECRET", raw)
                self.assertIsNone(value["entry_diagnostic"])
                part["capture"].pump.assert_not_called()
                part["capture"].process.poll.assert_not_called()

    def test_safe_entry_metadata_is_relayed_but_bad_or_partial_json_is_not(self):
        value = entry.diagnostic(q.QuotaError("PEER_CGROUP"), "admission")
        raw = b"Q2_ENTRY_REJECTED\n" + json.dumps(value).encode() + b"\n"
        actual, _ = self.emit(self.part(raw), "admission")
        self.assertEqual(value, actual["entry_diagnostic"])
        for bad in (raw[:-1], raw[:-1] + b"PRIVATE\n", raw + raw, b"Q2_ENTRY_REJECTED\n{" + raw.split(b"{", 1)[1].replace(
                b'"schema":', b'"schema":"private","schema":', 1),
                b"Q2_ENTRY_REJECTED\n" + json.dumps(dict(value, PRIVATE="secret")).encode() + b"\n"):
            with self.subTest(bad=bad[:40]):
                actual, output = self.emit(self.part(bad))
                self.assertIsNone(actual["entry_diagnostic"])
                self.assertNotIn(b"secret", output)

    def test_manager_prefix_and_suffix_do_not_hide_safe_entry_metadata(self):
        value = entry.diagnostic(q.QuotaError("PEER_CGROUP"), "admission")
        raw = b"Q2_ENTRY_REJECTED\n" + json.dumps(value).encode() + b"\n"
        for wrapped in (b"PRIVATE manager prefix\n" + raw, raw + b"PRIVATE manager suffix\n",
                        b"PRIVATE before\n" + raw + b"PRIVATE after\n"):
            with self.subTest(prefix=wrapped[:20]):
                actual, output = self.emit(self.part(wrapped), "admission")
                self.assertEqual(value, actual["entry_diagnostic"])
                self.assertNotIn(b"PRIVATE", output)

    def test_unstarted_or_byte_limited_capture_is_not_complete_output(self):
        part = self.part(b"x" * 32754, error="CAPTURE_BYTE_LIMIT", returncode=None)
        part["capture"].process = None
        value, _ = self.emit(part)
        self.assertIsNone(value["returncode"])
        self.assertEqual("CAPTURE_BYTE_LIMIT", value["capture_error"])
        self.assertEqual(["stdout"], value["eof"])

    def test_broken_diagnostic_does_not_replace_original_management_failure(self):
        instance = coordinator.Coordinator.__new__(coordinator.Coordinator)
        part = self.part(error="CAPTURE_IO_UNCERTAIN")
        part["capture"].pump = mock.Mock()
        instance.management = SimpleNamespace(end=100, runs={"listener": part})
        instance.end = 100; instance.management_closed = False
        with mock.patch.object(coordinator, "boottime_ns", return_value=1), \
             mock.patch.object(coordinator.os, "write", side_effect=BrokenPipeError):
            with self.assertRaises(q.QuotaError) as caught:
                instance._pump()
        self.assertEqual("MANAGEMENT_CLIENT_FAILED", caught.exception.code)
        part["capture"].pump.assert_called_once_with()
        part["capture"].process.poll.assert_not_called()

    def test_real_original_capture_exit_is_reported_once_without_extra_poll(self):
        cap = Capture(32768)
        cap.start([sys.executable, "-I", "-B", "-c", "import sys;sys.stderr.write('private failure');sys.exit(7)"])
        try:
            end = time.monotonic() + 3
            while not cap.done and time.monotonic() < end:
                cap.pump(); time.sleep(.001)
            self.assertTrue(cap.done)
            part = dict(self.part(), capture=cap)
            with mock.patch.object(cap.process, "poll", side_effect=AssertionError("extra poll")):
                value, raw = self.emit(part)
            self.assertEqual(7, value["returncode"])
            self.assertEqual(["stdout", "stderr"], value["eof"])
            self.assertNotIn(b"private failure", raw)
        finally:
            if cap.process.poll() is None:
                cap.process.kill(); cap.process.wait()
            cap.close_pipes()


if __name__ == "__main__":
    unittest.main()
