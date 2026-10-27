"""Boot preparation never rewrites a running resource or launches business."""
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("Linux resident boot resources")

from admin.local_hand_system_manager import host_resources as boot


class HostResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {"schema": boot.SCHEMA, "uid": os.getuid(), "unit": "fixtureboot.slice",
                       "parent": f"/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/fixtureboot.slice",
                       "limits": dict(boot.LIMITS)}
        self.state = {"LoadState": "loaded", "ActiveState": "inactive", "Job": [0, "/"],
                      "FragmentPath": "", "ControlGroup": "", "InvocationID": "before"}
        self.bus = Mock()
        self.bus.__enter__ = Mock(return_value=self.bus)
        self.bus.__exit__ = Mock(return_value=False)
        self.bus.unit.side_effect = lambda name: dict(self.state)
        self.bus.call.side_effect = self.properties
        self.bus.run_job.side_effect = self.start

    def properties(self, method, arguments):
        self.assertEqual("SetUnitProperties", method)
        self.assertEqual(self.config["unit"], arguments[0][1])
        self.state.update(dict(arguments[2][1]))
        self.state["DropInPaths"] = [f"/run/user/{self.config['uid']}/systemd/user.control/fixtureboot.slice.d/50-TasksMax.conf"]

    def start(self, name, method, emit, mode):
        self.assertEqual((self.config["unit"], "StartUnit", "ignore-requirements"), (name, method, mode))
        self.assertEqual(64, self.state["TasksMax"])
        self.state.update(ActiveState="active", ControlGroup=self.config["parent"], InvocationID="new")
        return {"result": "done"}

    def prepare(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(boot.startup, "_protected_directory",
                                           side_effect=lambda *a, **k: os.open(self.root, os.O_DIRECTORY)))
            stack.enter_context(patch.object(boot, "SystemdBus", return_value=self.bus))
            check = stack.enter_context(patch.object(boot, "_kernel_check"))
            result = boot.prepare(self.config)
            check.assert_called_once_with(self.config)
            return result

    def test_prepare_limits_before_start_and_repeat_without_effects(self):
        self.assertTrue(self.prepare()["changed"])
        self.assertFalse(self.prepare()["changed"])
        self.assertEqual(1, self.bus.call.call_count)
        self.assertEqual(1, self.bus.run_job.call_count)

    def test_lost_properties_response_reuses_observed_effect_without_repeat(self):
        def lost(*args):
            self.properties(*args)
            raise TimeoutError("lost")
        self.bus.call.side_effect = lost
        with self.assertRaises(TimeoutError):
            self.prepare()
        self.assertFalse(self.bus.run_job.called)
        self.assertTrue(self.prepare()["changed"])
        self.assertEqual(1, self.bus.call.call_count)

    def test_lost_start_response_does_not_restart_or_update(self):
        def lost(*args, **kwargs):
            self.start(*args, **kwargs)
            raise TimeoutError("lost")
        self.bus.run_job.side_effect = lost
        with self.assertRaises(TimeoutError):
            self.prepare()
        self.assertFalse(self.prepare()["changed"])
        self.assertEqual(1, self.bus.call.call_count)
        self.assertEqual(1, self.bus.run_job.call_count)

    def test_active_drift_is_rejected_without_changes(self):
        self.state.update(boot.LIMITS)
        self.state.update(ActiveState="active", ControlGroup=self.config["parent"], TasksMax=65)
        with self.assertRaisesRegex(ValueError, "ACTIVE_DRIFT"):
            self.prepare()
        self.bus.call.assert_not_called(); self.bus.run_job.assert_not_called()

    def persistent_fragment(self):
        return (b"[Unit]\nDescription=Retained resource\n\n[Slice]\nMemoryMax=256M\n"
                b"MemorySwapMax=0\nTasksMax=64\nCPUQuota=100%\nCPUQuotaPeriodSec=100ms\n")

    def test_persistent_resource_readiness_keeps_active_instance_and_limits(self):
        self.state.update(boot.LIMITS)
        self.state.update(ActiveState="active", ControlGroup=self.config["parent"])
        for root in ("/etc/systemd/user", "/etc/xdg/systemd/user"):
            path = root + "/" + self.config["unit"]
            self.state["FragmentPath"] = path
            with patch.object(boot.Path, "is_symlink", return_value=False), \
                    patch.object(boot.startup, "protected_read", return_value=self.persistent_fragment()) as read:
                self.assertFalse(self.prepare()["changed"])
                read.assert_called_once_with(path, owner_uid=0, maximum=16384)
        self.assertEqual("before", self.state["InvocationID"])
        self.bus.call.assert_not_called(); self.bus.run_job.assert_not_called()

    def test_xdg_alias_only_accepts_protected_standard_target(self):
        self.state["FragmentPath"] = "/etc/xdg/systemd/user/fixtureboot.slice"
        import stat
        from types import SimpleNamespace
        with patch.object(boot.Path, "is_symlink", return_value=True), \
                patch.object(boot.startup, "_protected_directory", side_effect=lambda *a, **k: os.open(self.root, os.O_DIRECTORY)), \
                patch.object(boot.os, "stat", return_value=SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0)), \
                patch.object(boot.startup, "protected_read", return_value=self.persistent_fragment()) as read:
            with patch.object(boot.os, "readlink", return_value="../../systemd/user"):
                boot._state(self.bus, self.config)
                read.assert_called_once_with("/etc/systemd/user/fixtureboot.slice", owner_uid=0, maximum=16384)
            read.reset_mock()
            with patch.object(boot.os, "readlink", return_value="/unrelated"), self.assertRaises(ValueError):
                boot._state(self.bus, self.config)
            read.assert_not_called()

    def test_persistent_closed_resource_with_correct_limits_starts_without_rewrite(self):
        self.state.update(boot.LIMITS, FragmentPath="/etc/systemd/user/fixtureboot.slice")
        with patch.object(boot.startup, "protected_read", return_value=self.persistent_fragment()):
            self.assertTrue(self.prepare()["changed"])
        self.bus.call.assert_not_called(); self.bus.run_job.assert_called_once()

    def test_persistent_untrusted_or_different_definition_is_not_adopted(self):
        original = self.persistent_fragment()
        self.state["FragmentPath"] = "/etc/systemd/user/fixtureboot.slice"
        for raw in (original.replace(b"TasksMax=64", b"TasksMax=65"),
                    original.replace(b"[Unit]", b"[Unit]\nWants=other.service"),
                    original + b"[Service]\nExecStart=/unexpected\n",
                    original + b"[DEFAULT]\nUnexpected=yes\n",
                    original + b"TasksMax=64\n", original + b"\xff",
                    original.replace(b"CPUQuota=100%\n", b"")):
            with self.subTest(raw=raw), patch.object(boot.startup, "protected_read", return_value=raw):
                with self.assertRaisesRegex(ValueError, "HOST_RESOURCE_DEFINITION"):
                    self.prepare()
        with patch.object(boot.startup, "protected_read", side_effect=ValueError("untrusted")):
            with self.assertRaisesRegex(ValueError, "untrusted"): self.prepare()
        self.state["FragmentPath"] = "/home/user/.config/systemd/user/fixtureboot.slice"
        with patch.object(boot.startup, "protected_read") as read, self.assertRaises(ValueError):
            self.prepare()
        read.assert_not_called()
        self.bus.call.assert_not_called(); self.bus.run_job.assert_not_called()

    def test_busy_or_external_definition_rejected_before_changes(self):
        for change in ({"Job": [12, "/job/12"]}, {"ActiveState": "activating"},
                       {"Requires": ["other.service"]}, {"Wants": ["other.service"]},
                       {"Conflicts": ["other.slice"]}, {"FragmentPath": "/etc/unexpected"},
                       {"DropInPaths": ["/etc/unexpected.conf"]}, {"ControlGroup": "/wrong"}):
            previous = dict(self.state)
            self.state.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.prepare()
            self.state = previous
        self.bus.call.assert_not_called(); self.bus.run_job.assert_not_called()

    def test_old_cgroup_and_kernel_mismatch_are_not_repaired(self):
        with patch.object(boot.Path, "exists", return_value=True), self.assertRaisesRegex(ValueError, "NOT_CLOSED"):
            self.prepare()
        self.bus.call.assert_not_called()
        self.state.update(boot.LIMITS)
        self.state.update(ActiveState="active", ControlGroup=self.config["parent"])
        with patch.object(boot.Path, "read_text", return_value="max 100000"), self.assertRaises(ValueError):
            boot._kernel_check(self.config)

    def test_inputs_cannot_select_other_user_arbitrary_path_or_budget(self):
        for changes in ({"uid": 0}, {"unit": "app.slice"}, {"unit": "other-child.slice"},
                        {"unit": "../../other.slice"}, {"parent": "/elsewhere"},
                        {"limits": dict(boot.LIMITS, TasksMax=True)}, {"extra": "command"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                boot.validate(dict(self.config, **changes))

    def test_resident_input_extracts_only_nonsecret_fixed_resource(self):
        resident = {"uid": self.config["uid"], "password": "must-not-copy", "maintenance": {},
                    "template": {"observed": {"system_geometry": {"retained_ordinary_parent": {
                        "parent": {"path": self.config["parent"]}, "memory_bytes": 268435456,
                        "memory_swap_max": 0, "tasks_max": 64, "cpu_quota_per_sec_usec": 1000000}}}}}
        self.assertEqual(self.config, boot.from_resident(resident))

    def test_service_generation_rejects_argument_or_dependency_injection(self):
        resident = {"uid": self.config["uid"], "gid": 1234,
                    "template": {"observed": {"parents": {"controller": {"path": "/fixture.slice"}},
                        "system_geometry": {"retained_ordinary_parent": {
                            "parent": {"path": self.config["parent"]}, "memory_bytes": 268435456,
                            "memory_swap_max": 0, "tasks_max": 64, "cpu_quota_per_sec_usec": 1000000}}}}}
        args = dict(python="/usr/bin/python3", package_root="/opt/fixed/site", admin_tools="/opt/fixed/tools",
                    configuration="/etc/fixed/boot.json")
        for value in ("/x --command", "/x\nExecStart=/bad", "/x/%u", "/x/$COMMAND", "/x/../bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                boot.service_definition(resident, **dict(args, configuration=value))
        for path in ("/", "/other.service", "/x.slice\nWants=other.service"):
            resident["template"]["observed"]["parents"]["controller"]["path"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                boot.service_definition(resident, **args)
