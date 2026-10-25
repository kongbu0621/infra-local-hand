"""Guarded startup observes host resources; it cannot initialize them implicitly."""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("Linux resident host resources")

from admin.local_hand_system_manager import host_readiness as readiness
from admin.local_hand_system_manager import resident_service


class HostReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parent = self.root / "execution.slice"
        self.parent.mkdir()
        self.retained = self.root / "retained.slice"
        self.retained.mkdir()
        for name, value in {"cpu.max": "100000 100000", "memory.max": "268435456",
                            "memory.swap.max": "0", "pids.max": "64"}.items():
            (self.retained / name).write_text(value)
        self.config = {"uid": 1234, "template": {"observed": {
            "parents": {"execution": {"path": "/execution.slice"}},
            "system_geometry": {"schema": "fixture", "retained_ordinary_parent": {
                "parent": {"path": "/retained.slice"}, "memory_bytes": 268435456,
                "memory_swap_max": 0, "tasks_max": 64, "cpu_quota_per_sec_usec": 1000000}}}}}
        self.bus = Mock()
        self.bus.__enter__ = Mock(return_value=self.bus)
        self.bus.__exit__ = Mock(return_value=False)
        self.bus.unit.side_effect = lambda name: {"LoadState": "loaded", "ActiveState": "active", "Job": [0, "/"],
                                                 "ControlGroup": "/" + name}

    def check(self, config=None):
        with patch.object(readiness, "SystemdBus", return_value=self.bus), \
             patch.object(readiness, "_cgroup", side_effect=lambda path: self.root / path.removeprefix("/")):
            return readiness.check_host(self.config if config is None else config)

    def test_ready_resources_only_read_and_preserve_bytes(self):
        before = {p.name: p.read_bytes() for p in self.retained.iterdir()}
        self.assertTrue(self.check()["ready"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.retained.iterdir()})
        self.assertEqual({"unit", "__enter__", "__exit__"}, {call[0] for call in self.bus.mock_calls})

    def test_inactive_pending_or_changed_parent_is_not_repaired(self):
        for change in ({"ActiveState": "inactive"}, {"Job": [1, "/job/1"]}, {"ControlGroup": "/other.slice"}):
            self.bus.unit.side_effect = lambda name: {"LoadState": "loaded", "ActiveState": "active", "Job": [0, "/"],
                                                     "ControlGroup": "/" + name, **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check()
        self.assertFalse(self.bus.run_job.called)

    def test_limit_drift_missing_or_unbounded_resource_is_rejected_without_writes(self):
        for name, value in (("pids.max", "65"), ("cpu.max", "max 100000"), ("cpu.max", "1 0"),
                            ("memory.max", "max")):
            path = self.retained / name
            old = path.read_bytes()
            path.write_text(value)
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                self.check()
            self.assertEqual(value, path.read_text())
            path.write_bytes(old)
        (self.retained / "memory.swap.max").unlink()
        with self.assertRaises(FileNotFoundError):
            self.check()

    def test_guarded_configuration_cannot_initialize_host(self):
        with patch.object(resident_service.os, "getuid", return_value=0), \
             patch.object(resident_service.os, "geteuid", return_value=0), \
             patch.object(resident_service.subprocess, "run") as execute:
            with self.assertRaisesRegex(ValueError, "GUARDED_INITIALIZATION_FORBIDDEN"):
                resident_service.initialize_host({"maintenance": {}})
            execute.assert_not_called()

    def test_cli_readiness_never_enters_initialization_or_listener(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(resident_service, "load", return_value=self.config))
            init = stack.enter_context(patch.object(resident_service, "initialize_host"))
            serve = stack.enter_context(patch.object(resident_service, "serve"))
            check = stack.enter_context(patch.object(readiness, "check_host", return_value={"ready": True}))
            output = stack.enter_context(patch("builtins.print"))
            resident_service.main(["--config", "/fixture", "--check-host"])
            check.assert_called_once_with(self.config)
            init.assert_not_called(); serve.assert_not_called()
            self.assertTrue(json.loads(output.call_args.args[0])["ready"])

    def test_path_escape_and_missing_retained_budget_are_rejected(self):
        for path in ("/", "relative", "/a/../b", "/a//b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                readiness._cgroup(path)
        config = copy.deepcopy(self.config)
        del config["template"]["observed"]["system_geometry"]["retained_ordinary_parent"]
        with self.assertRaisesRegex(ValueError, "RETAINED_PARENT_MISSING"):
            self.check(config)
