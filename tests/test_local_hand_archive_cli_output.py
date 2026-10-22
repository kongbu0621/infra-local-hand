"""Archive CLI response delivery, independent of the optional Ledger package."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from local_hand_jobs import artifact_archive as consumer


ARGUMENTS = ["read-snapshot", "--snapshot", "snapshot", "--expected-manifest-sha256", "a" * 64,
             "--artifact-id", "artifact:test", "--version-id", "version:test",
             "--scratch-parent", "scratch", "--output", "output"]
RESULT = {"status": "READ", "evidence_directory": "output/成果", "content_verified": True}


class FlushFailure(io.StringIO):
    def flush(self):
        raise OSError("channel flush failed")


class CLIOutputTests(unittest.TestCase):
    def run_main(self, output, errors, failure=None):
        with mock.patch.object(consumer, "read_snapshot_version", return_value=RESULT,
                               side_effect=failure) as operation, \
                redirect_stdout(output), redirect_stderr(errors):
            code = consumer.main(ARGUMENTS)
        operation.assert_called_once()
        return code

    def test_text_only_stream_supports_success_and_error_responses(self):
        for failure, expected in ((None, 0), (consumer.ArchiveError("CONFLICT", "Read refused"), 1)):
            with self.subTest(failure=failure):
                output, errors = io.StringIO(), io.StringIO()
                with mock.patch.object(output, "flush", wraps=output.flush) as flush:
                    self.assertEqual(self.run_main(output, errors, failure), expected)
                flush.assert_called_once()
                self.assertEqual(output.getvalue().count("\n"), 1)
                response = json.loads(output.getvalue())
                self.assertEqual(response["status"], "READ" if failure is None else "ERROR")
                self.assertEqual(errors.getvalue(), "")

    def test_flush_failure_returns_error_without_a_second_response(self):
        for failure in (None, consumer.ArchiveError("CONFLICT", "Read refused")):
            with self.subTest(failure=failure):
                output, errors = FlushFailure(), io.StringIO()
                self.assertEqual(self.run_main(output, errors, failure), 1)
                self.assertEqual(output.getvalue().count("\n"), 1)
                self.assertIn("response channel failed", errors.getvalue())
                self.assertIn("retain", errors.getvalue())

    def test_unavailable_closed_and_failing_error_channels_are_bounded(self):
        closed = io.StringIO()
        closed.close()
        for output, errors in ((None, None), (closed, closed), (FlushFailure(), FlushFailure())):
            with self.subTest(output=type(output).__name__):
                self.assertEqual(self.run_main(output, errors), 1)

    def test_real_file_short_writes_deliver_one_complete_utf8_response(self):
        write = os.write
        # TemporaryFile is a NamedTemporaryFile wrapper on Windows. Use a
        # regular file so these faults reach the real descriptor on both OSes.
        with tempfile.TemporaryDirectory() as directory, \
                open(Path(directory) / "response", "w+b") as raw, \
                io.TextIOWrapper(raw, encoding="ascii") as output:
            errors = io.StringIO()
            with mock.patch.object(consumer.os, "write",
                                   side_effect=lambda fd, data: write(fd, data[:3])) as writes:
                self.assertEqual(self.run_main(output, errors), 0)
            self.assertGreater(writes.call_count, 1)
            raw.seek(0)
            self.assertEqual(raw.read(), consumer._json(RESULT) + b"\n")
            self.assertEqual(errors.getvalue(), "")

    def test_partial_file_write_failure_does_not_append_an_error_json(self):
        write = os.write
        attempts = []
        def fail_after_prefix(fd, data):
            attempts.append(bytes(data))
            if len(attempts) == 1:
                return write(fd, data[:7])
            raise BrokenPipeError("receiver disappeared")
        with tempfile.TemporaryDirectory() as directory, \
                open(Path(directory) / "response", "w+b") as raw, \
                io.TextIOWrapper(raw, encoding="utf-8") as output:
            errors = io.StringIO()
            with mock.patch.object(consumer.os, "write", side_effect=fail_after_prefix):
                self.assertEqual(self.run_main(output, errors), 1)
            raw.seek(0)
            self.assertEqual(raw.read(), consumer._json(RESULT)[:7])
            self.assertEqual(len(attempts), 2)
            self.assertIn("response channel failed", errors.getvalue())

    def test_zero_write_stops_without_retrying_or_reporting_success(self):
        with tempfile.TemporaryDirectory() as directory, \
                open(Path(directory) / "response", "w+b") as raw, \
                io.TextIOWrapper(raw, encoding="utf-8") as output:
            errors = io.StringIO()
            with mock.patch.object(consumer.os, "write", return_value=0) as write:
                self.assertEqual(self.run_main(output, errors), 1)
            write.assert_called_once()
            raw.seek(0)
            self.assertEqual(raw.read(), b"")
            self.assertIn("response channel failed", errors.getvalue())


# The operation stub records a completed result before main attempts delivery.
# These subprocess tests cover real OS channels and interpreter shutdown, not
# Ledger recovery or NAS qualification; those have separate integration tests.
SCRIPT = r"""
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from local_hand_jobs import artifact_archive as consumer
receipt, outcome = Path(sys.argv[2]), sys.argv[3]
result = {"status": "READ", "evidence_directory": "output/成果", "content_verified": True}
def completed_operation(**kwargs):
    with receipt.open("xb") as stream:
        stream.write(consumer._json(result))
    if outcome == "error":
        raise consumer.ArchiveError("CONFLICT", "Read refused after retained output")
    return result
consumer.read_snapshot_version = completed_operation
sys.stdin.buffer.read(1)
raise SystemExit(consumer.main(["read-snapshot", "--snapshot", "snapshot",
    "--expected-manifest-sha256", "a" * 64, "--artifact-id", "artifact:test",
    "--version-id", "version:test", "--scratch-parent", "scratch", "--output", "output"]))
"""


class CLIOutputProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONIOENCODING": "ascii"}

    def arguments(self, name, outcome):
        # Console entry points do not use -I: exercise a real non-UTF-8 stdout
        # encoding while selecting current source explicitly, with no PYTHONPATH.
        return [sys.executable, "-B", "-c", SCRIPT, str(Path(consumer.__file__).parents[1]),
                str(self.root / name), outcome]

    def assert_retained(self, name):
        self.assertEqual((self.root / name).read_bytes(), consumer._json(RESULT))

    def test_ascii_console_still_delivers_utf8_machine_json(self):
        result = subprocess.run(self.arguments("unicode.json", "success"), input=b"x",
            cwd=self.root, env=self.environment, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, consumer._json(RESULT) + b"\n")
        self.assertEqual(result.stderr, b"")
        self.assert_retained("unicode.json")

    @unittest.skipUnless(sys.platform == "linux", "Linux pipe and /dev/full output semantics")
    def test_closed_pipe_never_becomes_shutdown_exit_120(self):
        for outcome in ("success", "error"):
            name = "pipe-" + outcome + ".json"
            with self.subTest(outcome=outcome), subprocess.Popen(self.arguments(name, outcome),
                    cwd=self.root, env=self.environment, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                process.stdout.close()
                process.stdout = None
                _, errors = process.communicate(input=b"x", timeout=10)
                self.assertEqual(process.returncode, 1, errors)
                self.assertIn(b"response channel failed", errors)
                self.assertNotIn(b"Traceback", errors)
                self.assertNotIn(b"Exception ignored", errors)
                self.assert_retained(name)

    @unittest.skipUnless(sys.platform == "linux", "Linux /dev/full output semantics")
    def test_full_stdout_and_stderr_never_leave_pending_response_bytes(self):
        for outcome in ("success", "error"):
            for stderr_fails in (False, True):
                name = "full-" + outcome + "-" + str(stderr_fails) + ".json"
                with self.subTest(outcome=outcome, stderr_fails=stderr_fails), open("/dev/full", "wb", buffering=0) as full:
                    result = subprocess.run(self.arguments(name, outcome), input=b"x", cwd=self.root,
                        env=self.environment, stdout=full, stderr=full if stderr_fails else subprocess.PIPE,
                        timeout=10)
                self.assertEqual(result.returncode, 1, result.stderr)
                if not stderr_fails:
                    self.assertIn(b"response channel failed", result.stderr)
                    self.assertNotIn(b"Traceback", result.stderr)
                    self.assertNotIn(b"Exception ignored", result.stderr)
                self.assert_retained(name)


if __name__ == "__main__":
    unittest.main()
