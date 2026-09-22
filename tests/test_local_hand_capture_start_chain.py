"""Real child lifetime checks when a bounded-capture reader cannot start."""
from __future__ import annotations

from contextlib import nullcontext
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from config_fixtures import profile_v2
from local_hand import bounded_io, validate
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError


@unittest.skipIf(os.name == "nt", "POSIX lifetime fixture; Windows deferred")
class CaptureStartChainTests(unittest.TestCase):
    def _check_start_failure(self, runner: str, fail_at: int, *, deny_termination: bool = False) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "projects/demo"
            repo.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            script = repo / "finite-child.py"
            script.write_text(
                "from pathlib import Path\nimport time\n"
                "end = time.monotonic() + 5\n"
                "with Path('heartbeat').open('ab', buffering=0) as out:\n"
                " while time.monotonic() < end:\n"
                "  out.write(b'x'); time.sleep(.02)\n"
            )
            data = profile_v2({"node_id": "capture-fixture", "projects_root": str(repo.parent),
                "repositories": {"demo": {"path": "demo", "single_writer": True,
                    "validations": {"probe": {"argv": [sys.executable, str(script)],
                        "timeout_seconds": 2, "replay_safe": True}}}}})
            profile_path = root / "profile.json"
            profile_path.write_text(json.dumps(data))
            profile = load_profile(profile_path)
            children = []
            real_popen = subprocess.Popen
            real_start = threading.Thread.start
            calls = 0

            def tracked_popen(*args, **kwargs):
                child = real_popen(*args, **kwargs)
                children.append(child)
                return child

            def start(thread):
                nonlocal calls
                calls += 1
                if calls == fail_at:
                    # Ensure the subprocess reached its side effect before
                    # injecting the OS-resource-like reader startup failure.
                    deadline = time.monotonic() + 1
                    while not (repo / "heartbeat").exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    raise RuntimeError("can't start new thread")
                return real_start(thread)

            error = None
            try:
                denied = (mock.patch.object(bounded_io, "_kill_tree", return_value=False)
                          if deny_termination else nullcontext())
                with denied, mock.patch.object(subprocess, "Popen", side_effect=tracked_popen), \
                     mock.patch.object(threading.Thread, "start", start):
                    try:
                        if runner == "generic":
                            bounded_io.run_process_bounded([sys.executable, str(script)], cwd=repo,
                                env=dict(os.environ), timeout=2, max_stdout=1024,
                                max_stderr=1024, code_prefix="capture_probe")
                        else:
                            validate.run_profile(profile, "demo", "probe")
                    except Exception as exc:
                        error = exc
                self.assertEqual(len(children), 1)
                self.assertTrue((repo / "heartbeat").exists())
                child = children[0]
                if deny_termination:
                    self.assertIsNone(child.poll(), "fixture must leave termination unconfirmed")
                    before = (repo / "heartbeat").read_bytes()
                    time.sleep(.08)
                    self.assertGreater(len((repo / "heartbeat").read_bytes()), len(before))
                    self.assertIsInstance(error, LocalHandError)
                    self.assertEqual(error.code, "capture_probe_termination_unconfirmed")
                    self.assertEqual(error.status, "indeterminate")
                    return
                self.assertIsNotNone(child.poll(), "reader start failure left the child running")
                before = (repo / "heartbeat").read_bytes()
                time.sleep(.08)
                self.assertEqual((repo / "heartbeat").read_bytes(), before)
                self.assertTrue(child.stdout.closed)
                self.assertTrue(child.stderr.closed)
                self.assertIsInstance(error, LocalHandError)
                prefix = "capture_probe" if runner == "generic" else "validation"
                self.assertEqual(error.code, prefix + "_capture_start_failed")
                self.assertEqual(error.status, "indeterminate")
            finally:
                # Baseline implementations leak the process: only terminate
                # this test's exact newly-created process group, then reap it.
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

    def test_generic_first_reader_start_failure_reaps_child(self):
        self._check_start_failure("generic", 1)

    def test_generic_second_reader_start_failure_reaps_child(self):
        self._check_start_failure("generic", 2)

    def test_validation_first_reader_start_failure_reaps_child(self):
        self._check_start_failure("validation", 1)

    def test_validation_second_reader_start_failure_reaps_child(self):
        self._check_start_failure("validation", 2)

    def test_reader_start_failure_cannot_claim_unconfirmed_termination(self):
        self._check_start_failure("generic", 2, deny_termination=True)
