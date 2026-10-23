"""Check probe safety/evidence logic without starting any system service."""
import copy
import errno
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

if sys.platform != "linux":
    raise unittest.SkipTest("Linux-only explicit host fixture")

import first_node_probe as probe


class FirstNodeProbeTests(unittest.TestCase):
    def test_no_arguments_never_starts_a_fixture(self):
        with patch.object(probe, "probe") as run, patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit):
            probe.main([])
        run.assert_not_called()

    def test_inspection_requires_a_concrete_manager_config(self):
        with patch.object(probe, "probe") as run, patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit):
            probe.main(["--inspect"])
        run.assert_not_called()

    def test_failed_inspection_never_starts_fixture_or_reports_success(self):
        with patch.object(probe, "inspect_manager", side_effect=PermissionError("denied")), \
             patch.object(probe, "probe") as run, patch.object(sys, "stdout", io.StringIO()) as output:
            self.assertEqual(1, probe.main(["--probe", "--manager-config", "/unreadable/config.json"]))
        run.assert_not_called()
        self.assertEqual("PermissionError", json.loads(output.getvalue())["error"]["type"])

    def test_probe_refuses_unprivileged_execution_before_mkdir(self):
        with patch.object(probe.os, "getuid", return_value=1000), patch.object(Path, "mkdir") as mkdir:
            with self.assertRaises(PermissionError):
                probe.probe()
        mkdir.assert_not_called()

    def test_worker_refuses_root_or_nonfixture_target(self):
        for identity, root, slot in ((0, "/run/lhp1" + "a" * 12, 0),
                                     (5000, "/etc", 0), (5000, "/run/lhp1" + "a" * 12, 5)):
            with self.subTest(identity=identity, root=root, slot=slot), patch.object(probe.os, "geteuid", return_value=identity):
                with self.assertRaises(ValueError):
                    probe.worker(root, slot)

    def test_command_is_bounded_and_has_no_production_unit_target(self):
        command = probe.service_command("lhp1aaaaaaaaaaaas0.service", "lhp1aaaaaaaaaaaa.slice",
                                        Path("/run/lhp1aaaaaaaaaaaa"), 0, 700000)
        for option in ("--reuid=700000", "--regid=700000", "--property=MemoryMax=64M",
                       "--property=TasksMax=4", "--property=RuntimeMaxSec=150s",
                       "--property=KillMode=control-group", "--property=NoNewPrivileges=yes",
                       "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all",
                       "--clear-groups", "--property=SupplementaryGroups="):
            self.assertIn(option, command)
        self.assertLess(command.index("/usr/bin/setpriv"), command.index("/usr/bin/python3"))
        self.assertNotIn("--user", command)
        self.assertFalse(any(arg.startswith("--property=User=") for arg in command))
        self.assertIn("--property=StandardError=append:/run/lhp1aaaaaaaaaaaa/diagnostics/"
                      "lhp1aaaaaaaaaaaas0.service.stderr", command)
        with self.assertRaises(ValueError):
            probe.service_command("gx10-lh-manager.service", "system.slice", Path("/run"), 0, 1)

    def test_exited_launcher_fails_without_waiting_for_response_timeout(self):
        with patch.object(probe, "read_json", side_effect=FileNotFoundError), \
             patch.object(probe, "show", return_value=dict(ActiveState="failed", ExecMainStatus="127")), \
             patch.object(probe.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, '127'):
                probe.await_file(Path("/unused/ready.json"), unit="lhp1aaaaaaaaaaaas0.service")
        sleep.assert_not_called()

    def test_collected_unit_default_success_is_not_reported_as_real_exit(self):
        with patch.object(probe, "read_json", side_effect=FileNotFoundError), \
             patch.object(probe, "show", return_value=dict(LoadState="not-found", ActiveState="inactive",
                                                          Result="success", ExecMainStatus="0")):
            with self.assertRaises(RuntimeError) as raised:
                probe.await_file(Path("/unused/ready.json"), unit="lhp1aaaaaaaaaaaas0.service")
        self.assertIn("unavailable_after_collection", str(raised.exception))
        self.assertNotIn("success", str(raised.exception))

    def test_ready_requires_all_credentials_and_caps_to_be_dropped(self):
        ready = dict(uid=700000, gid=700000, uids=[700000] * 4, gids=[700000] * 4,
                     groups=[], no_new_privs="1", pid=123,
                     capabilities={key: "0" for key in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")})
        changed = []
        for key in ready["capabilities"]:
            bad = copy.deepcopy(ready)
            bad["capabilities"][key] = "100"
            changed.append(bad)
        for key in ("uids", "gids"):
            bad = copy.deepcopy(ready)
            bad[key][2] = 0
            changed.append(bad)
        changed.append(dict(ready, groups=[700000]))
        for bad in changed:
            with self.subTest(value=bad), patch.object(probe, "await_file", return_value=bad), \
                 patch.object(probe, "show") as show:
                with self.assertRaises(ValueError):
                    probe.verify_ready("lhp1aaaaaaaaaaaar0.service", Path("/unused"), 700000)
                show.assert_not_called()
        with patch.object(probe, "await_file", return_value=ready), \
             patch.object(probe, "show", return_value=dict(ActiveState="active", MainPID="123", ControlGroup="/fixture")), \
             patch.object(probe, "cgroup_limits", return_value={"memory.max": str(64 * 1024**2),
                          "memory.swap.max": "0", "pids.max": "4", "cpu.max": "10000 100000"}):
            self.assertEqual(123, probe.verify_ready("lhp1aaaaaaaaaaaar0.service", Path("/unused"), 700000)["pid"])

    def test_missing_or_stopped_peer_is_not_reported_as_access_denial(self):
        result = dict(own_file=0, own_socket=0, peer_files=[errno.EACCES] * 4,
                      peer_sockets=[errno.EPERM] * 4, manager_socket=errno.EACCES)
        probe.assert_access(result)
        for value in (0, errno.ENOENT, errno.ECONNREFUSED):
            changed = copy.deepcopy(result)
            changed["peer_sockets"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                probe.assert_access(changed)
        with self.assertRaises(ValueError):
            probe.assert_access(dict(result, own_file=errno.EACCES))

    def test_reused_identity_requires_both_retained_refusals(self):
        result = dict(own_file=0, own_socket=0, peer_files=[errno.EACCES] * 4,
                      peer_sockets=[errno.EACCES] * 4, manager_socket=errno.EACCES,
                      retained_file=errno.EACCES, retained_socket=0)
        with self.assertRaises(ValueError):
            probe.assert_access(result, retained=True)

    def test_collected_unit_still_checks_original_cgroup(self):
        unit = "lhp1aaaaaaaaaaaas0.service"
        with patch.object(probe, "show", return_value=dict(ActiveState="inactive", MainPID="0", ControlGroup="")), \
             patch.object(probe, "cgroup_limits", return_value={"cgroup.events": "populated 1"}) as limits:
            self.assertFalse(probe.stopped(unit))
            limits.assert_called_once_with("/lhp1aaaaaaaaaaaa.slice/" + unit)
            limits.return_value = {"cgroup.events": "populated 0"}
            self.assertTrue(probe.stopped(unit))

    def test_unit_observation_failure_remains_uncertain(self):
        with patch.object(probe, "run", return_value=subprocess.CompletedProcess([], 1, "", "unavailable")):
            with self.assertRaises(RuntimeError):
                probe.stopped("lhp1aaaaaaaaaaaas0.service")

    def test_json_read_limit_and_command_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "command.json"
            old = os.umask(0o077)
            try:
                probe.write_json(path, {"sequence": 1}, mode=0o644)
            finally:
                os.umask(old)
            self.assertEqual(0o644, stat.S_IMODE(path.stat().st_mode))
            self.assertEqual({"sequence": 1}, probe.read_json(path))
            with self.assertRaises(ValueError):
                probe.read_json(path, 4)

    def test_inspection_does_not_emit_auth_or_session_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(dict(auth={"password": "secret-one"},
                 template={"plan": {"settings": {"identity": {"session": "secret-two"}}}},
                 private_root="secret-three")))
            os.chmod(path, 0o600)
            real = os.fstat
            def owner(fd):
                values = list(real(fd)); values[4] = 0
                return os.stat_result(values)
            with patch.object(probe.os, "fstat", side_effect=owner):
                result = json.dumps(probe.inspect_manager(path))
            for secret in ("secret-one", "secret-two", "secret-three"):
                self.assertNotIn(secret, result)


if __name__ == "__main__":
    unittest.main()
