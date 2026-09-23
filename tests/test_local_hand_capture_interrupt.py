"""Catchable interruptions must not abandon a child already owned by S1."""
from __future__ import annotations

import os
from contextlib import nullcontext
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

from local_hand import bounded_io, validate
from local_hand.protocol import LocalHandError


@unittest.skipIf(os.name == "nt", "POSIX signal/process-group fixture; Windows deferred")
class CaptureInterruptTests(unittest.TestCase):
    def _check(self, runner, stage, interrupt, deny_termination=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            heartbeat = root / "heartbeat"
            argv = [sys.executable, "-c",
                    "import time;from pathlib import Path;"
                    "p=Path('heartbeat');end=time.monotonic()+10\n"
                    "while time.monotonic()<end:p.write_bytes(b'alive');time.sleep(.02)"]
            children = []
            popen, sleep, thread_start = subprocess.Popen, time.sleep, threading.Thread.start
            calls = 0

            def track(*args, **kwargs):
                child = popen(*args, **kwargs)
                children.append(child)
                return child

            def trigger():
                deadline = time.monotonic() + 3
                while not heartbeat.exists() and time.monotonic() < deadline:
                    sleep(.01)
                self.assertTrue(heartbeat.exists(), "finite child must have started")
                if interrupt == "sigint":
                    signal.raise_signal(signal.SIGINT)
                raise interrupt

            def monitor_sleep(seconds):
                nonlocal calls
                calls += 1
                if calls == 1:
                    trigger()
                return sleep(seconds)

            def start(reader):
                nonlocal calls
                calls += 1
                if calls == stage:
                    trigger()
                return thread_start(reader)

            spec = SimpleNamespace(argv=argv, timeout_seconds=5, replay_safe=True)
            profile = SimpleNamespace(repositories={"demo": SimpleNamespace(validations={"probe": spec})})
            fault = (mock.patch.object(time, "sleep", monitor_sleep) if stage == "monitor"
                     else mock.patch.object(threading.Thread, "start", start))
            expected = KeyboardInterrupt if interrupt == "sigint" else type(interrupt)
            if deny_termination and interrupt != "sigint":
                expected = LocalHandError
            denied = nullcontext()
            if deny_termination:
                denied = (mock.patch.object(bounded_io, "_kill_tree", return_value=False)
                          if runner == "generic" else mock.patch.object(validate, "_terminate_tree",
                              return_value=(None, False, "synthetic-unconfirmed")))
            try:
                with mock.patch.object(subprocess, "Popen", side_effect=track), fault, denied, \
                     mock.patch.object(validate, "repository_root", return_value=root):
                    with self.assertRaises(expected) as raised:
                        if runner == "generic":
                            bounded_io.run_process_bounded(argv, cwd=root, env=dict(os.environ),
                                timeout=5, max_stdout=1024, max_stderr=1024, code_prefix="interrupt")
                        else:
                            validate.run_profile(profile, "demo", "probe")
                if interrupt != "sigint" and not deny_termination:
                    self.assertIs(raised.exception, interrupt)
                self.assertEqual(len(children), 1)
                child = children[0]
                if deny_termination:
                    self.assertIsNone(child.poll(), "synthetic termination denial must leave the child alive")
                    if interrupt == "sigint":
                        self.assertIn("unconfirmed", " ".join(raised.exception.__notes__))
                    else:
                        self.assertEqual(raised.exception.status, "indeterminate")
                        self.assertIs(raised.exception.__cause__, interrupt)
                else:
                    self.assertIsNotNone(child.poll(), "catchable interruption abandoned its owned child")
                self.assertTrue(child.stdout.closed)
                self.assertTrue(child.stderr.closed)
            finally:
                # The red baseline leaks only our finite child's exact group.
                for child in children:
                    if child.poll() is None:
                        try:
                            os.killpg(child.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    child.wait(timeout=3)
                    for stream in (child.stdout, child.stderr):
                        if not stream.closed:
                            stream.close()

    def test_sigint_during_monitor_reaps_child_and_propagates(self):
        for runner in ("generic", "validation"):
            with self.subTest(runner=runner):
                self._check(runner, "monitor", "sigint")

    def test_monitor_failure_reaps_child_and_preserves_primary_exception(self):
        for runner in ("generic", "validation"):
            with self.subTest(runner=runner):
                self._check(runner, "monitor", RuntimeError("synthetic monitor failure"))

    def test_sigint_during_either_reader_start_reaps_child_and_propagates(self):
        for runner in ("generic", "validation"):
            for stage in (1, 2):
                with self.subTest(runner=runner, reader=stage):
                    self._check(runner, stage, "sigint")

    def test_unconfirmed_cleanup_preserves_shutdown_or_reports_uncertainty(self):
        for runner in ("generic", "validation"):
            for interrupt in ("sigint", RuntimeError("synthetic monitor failure")):
                with self.subTest(runner=runner, interrupt=interrupt):
                    self._check(runner, "monitor", interrupt, deny_termination=True)
