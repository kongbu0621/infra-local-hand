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
from types import SimpleNamespace

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

    def test_existing_response_does_not_prove_the_worker_is_still_active(self):
        response = dict(sequence=1, pid=123)
        for state in (dict(ActiveState="failed", MainPID="0"),
                      dict(ActiveState="inactive", MainPID="0"),
                      dict(ActiveState="deactivating", MainPID="123"),
                      dict(LoadState="not-found", ActiveState="inactive", MainPID="0"),
                      dict(ActiveState="active", MainPID="456")):
            with self.subTest(state=state), patch.object(probe, "read_json", return_value=response), \
                 patch.object(probe, "show", return_value=state), self.assertRaises(RuntimeError):
                probe.await_file(Path("/unused/response.json"), unit="lhp1aaaaaaaaaaaas0.service")

    def test_response_waits_for_active_unit_and_records_the_observation(self):
        active = dict(ActiveState="active", MainPID="123", InvocationID="a" * 32, ControlGroup="/fixture")
        with patch.object(probe, "read_json", return_value=dict(sequence=1, pid=123)), \
             patch.object(probe, "show", side_effect=[dict(ActiveState="activating", MainPID="123"), active]), \
             patch.object(probe.time, "sleep"):
            result = probe.await_file(Path("/unused/response.json"), unit="lhp1aaaaaaaaaaaas0.service")
        self.assertEqual(dict(unit="lhp1aaaaaaaaaaaas0.service", **active), result["unit_observation"])

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

    def test_incomplete_or_noninteger_access_results_cannot_pass(self):
        good = dict(own_file=0, own_socket=0, peer_files=[errno.EACCES] * 4,
                    peer_sockets=[errno.EACCES] * 4, manager_socket=errno.EACCES)
        bad = [dict(good, peer_files=[]), dict(good, peer_sockets=[errno.EACCES] * 3),
               dict(good, peer_files=[errno.EACCES] * 5), dict(good, own_file=False)]
        for result in bad:
            with self.subTest(result=result), self.assertRaises(ValueError):
                probe.assert_access(result)

    def test_response_is_bound_to_expected_process_and_command(self):
        good = dict(sequence=1, pid=123, uid=700000, own_file=0, own_socket=0,
                    peer_files=[errno.EACCES] * 4, peer_sockets=[errno.EACCES] * 4,
                    manager_socket=errno.EACCES)
        identity = dict(pid=123, uid=700000)
        probe.verify_observation(good, identity, 1)
        for key, value in (("sequence", 2), ("sequence", True), ("pid", 456), ("uid", 700001)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                probe.verify_observation(dict(good, **{key: value}), identity, 1)

    def test_missing_controller_files_do_not_prove_cgroup_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            group = Path(directory) / "lhp1aaaaaaaaaaaa.slice" / "lhp1aaaaaaaaaaaas0.service"
            group.mkdir(parents=True)
            events = group / "cgroup.events"
            def mapped_path(value):
                return Path(directory + value.removeprefix("/sys/fs/cgroup")) if str(value).startswith("/sys/fs/cgroup") else Path(value)
            with patch.object(probe, "Path", side_effect=mapped_path), \
                 patch.object(probe, "show", return_value=dict(LoadState="loaded", ActiveState="inactive",
                      MainPID="0", ControlPID="0", Job="", ControlGroup="")):
                events.write_text("populated 1\n")
                self.assertFalse(probe.stopped("lhp1aaaaaaaaaaaas0.service"))
                events.unlink()
                self.assertFalse(probe.stopped("lhp1aaaaaaaaaaaas0.service"))
                events.write_text("populated 0\n")
                self.assertTrue(probe.stopped("lhp1aaaaaaaaaaaas0.service"))
                events.unlink()
                group.rmdir()
                self.assertTrue(probe.stopped("lhp1aaaaaaaaaaaas0.service"))

    def test_populated_parent_preserves_fixture_even_after_leaf_cleanup(self):
        # Exercise the real probe finally path, with no root privilege or services.
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "run").mkdir()
            group = base / "cgroup" / "lhp1aaaaaaaaaaaa.slice"
            group.mkdir(parents=True)
            (group / "cgroup.events").write_text("populated 1\n")
            def mapped_path(value):
                if str(value) == "/run":
                    return base / "run"
                if str(value).startswith("/sys/fs/cgroup"):
                    return Path(str(base / "cgroup") + str(value).removeprefix("/sys/fs/cgroup"))
                return Path(value)
            with patch.object(probe, "Path", side_effect=mapped_path), \
                 patch.object(probe.os, "getuid", return_value=0), \
                 patch.object(probe.os, "geteuid", return_value=0), \
                 patch.object(probe.uuid, "uuid4", return_value=SimpleNamespace(hex="a" * 32)), \
                 patch.object(probe.socket, "socket"), patch.object(probe, "choose_uids", return_value=[]), \
                 patch.object(probe, "show", return_value=dict(LoadState="loaded", ActiveState="inactive",
                                                               Job="", ControlGroup="")), \
                 patch.object(probe, "run", return_value=subprocess.CompletedProcess([], 1, "", "stop failed")):
                result = probe.probe()
            self.assertEqual("CLEANUP_UNCERTAIN", result["status"])
            self.assertTrue((base / "run" / "lhp1aaaaaaaaaaaa").is_dir())

    def test_pending_parent_job_preserves_empty_fixture(self):
        # A currently empty slice may still have a queued start; do not remove
        # its limits or files merely because it has no processes at this instant.
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            def mapped_path(value):
                return base if str(value) == "/run" else Path(value)
            with patch.object(probe, "Path", side_effect=mapped_path), \
                 patch.object(probe.os, "getuid", return_value=0), \
                 patch.object(probe.os, "geteuid", return_value=0), \
                 patch.object(probe.uuid, "uuid4", return_value=SimpleNamespace(hex="a" * 32)), \
                 patch.object(probe.socket, "socket"), patch.object(probe, "choose_uids", return_value=[]), \
                 patch.object(probe, "run", return_value=subprocess.CompletedProcess([], 1, "", "stop failed")), \
                 patch.object(probe, "cgroup_empty", return_value=True), \
                 patch.object(probe, "show", return_value=dict(LoadState="loaded", ActiveState="inactive",
                                                               Job="47", ControlGroup="")):
                result = probe.probe()
            self.assertEqual("CLEANUP_UNCERTAIN", result["status"])
            self.assertTrue((base / "lhp1aaaaaaaaaaaa").is_dir())

    def test_stopped_requires_complete_idle_unit_and_original_cgroup(self):
        unit = "lhp1aaaaaaaaaaaas0.service"
        group = "/lhp1aaaaaaaaaaaa.slice/" + unit
        good = dict(LoadState="loaded", ActiveState="inactive", MainPID="0",
                    ControlPID="0", Job="", ControlGroup=group)
        invalid = [dict(good, Job="47"), dict(good, ControlPID="101"),
                   dict(good, ControlGroup="/another-empty-group"), dict(good, LoadState="error")]
        invalid += [{key: value for key, value in good.items() if key != missing}
                    for missing in ("MainPID", "ControlPID", "Job", "LoadState", "ControlGroup")]
        for state in invalid:
            with self.subTest(state=state), patch.object(probe, "show", return_value=state), \
                 patch.object(probe, "cgroup_empty", return_value=True):
                self.assertFalse(probe.stopped(unit))
        for state in (good, dict(good, LoadState="not-found", ControlGroup=""), dict(good, Job="0")):
            with self.subTest(state=state), patch.object(probe, "show", return_value=state), \
                 patch.object(probe, "cgroup_empty", return_value=True) as empty:
                self.assertTrue(probe.stopped(unit))
                empty.assert_called_once_with(group)

    def test_stop_observation_requests_job_and_control_process(self):
        unit = "lhp1aaaaaaaaaaaas0.service"
        def reply(argv, **kwargs):
            values = dict(LoadState="loaded", ActiveState="inactive", MainPID="0", ControlPID="101",
                          Job="47", ControlGroup="", InvocationID="a" * 32, Result="success",
                          ExecMainCode="0", ExecMainStatus="0")
            requested = [argv[i + 1] for i, item in enumerate(argv) if item == "-p"]
            return subprocess.CompletedProcess(argv, 0, "".join(key + "=" + values[key] + "\n" for key in requested), "")
        with patch.object(probe, "run", side_effect=reply), patch.object(probe, "cgroup_empty", return_value=True):
            self.assertFalse(probe.stopped(unit))

    def test_probe_pipeline_binds_every_response_and_cleans_up(self):
        # Run the real coordinator, replacing only privileged/worker interfaces.
        # Late responses must not satisfy a different worker or command.
        for corruption in (None, (1, "pid"), (2, "uid"), (3, "pid"),
                           (0, "readiness"), (0, "stop"), (0, "parent")):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                token = "lhp1aaaaaaaaaaaa"
                def mapped_path(value):
                    return base if str(value) == "/run" else Path(value)
                def ready(unit, own, uid):
                    if corruption == (0, "readiness") and own.name == "2":
                        raise RuntimeError("third worker failed during readiness")
                    return dict(pid=200 if "r0" in unit else 100 + int(own.name), uid=uid,
                                cgroup="/" + token + ".slice/" + unit)
                def show(unit):
                    if unit.endswith(".slice"):
                        return dict(LoadState="loaded", ActiveState="inactive", Job="47" if corruption == (0, "parent") else "",
                                    ControlGroup="/" + token + ".slice")
                    return dict(ActiveState="inactive" if corruption == (0, "stop") else "active",
                                MainPID="0" if corruption == (0, "stop") else "100",
                                ControlGroup="/" + token + ".slice/" + unit)
                def response(path, predicate=lambda value: True, **kwargs):
                    number = int(path.parent.name)
                    command = probe.read_json(base / token / (str(number) + ".command.json"))
                    sequence = command["sequence"]
                    result = dict(pid=200 if sequence == 3 else 100 + number, uid=700000 + number,
                                  sequence=sequence, own_file=0, own_socket=0,
                                  peer_files=[errno.EACCES] * 4, peer_sockets=[errno.EACCES] * 4,
                                  manager_socket=errno.EACCES)
                    if sequence == 3:
                        result.update(retained_file=errno.EACCES, retained_socket=errno.EACCES)
                    if corruption and sequence == corruption[0]:
                        result[corruption[1]] += 1
                    return result
                with patch.object(probe, "Path", side_effect=mapped_path), \
                     patch.object(probe.os, "getuid", return_value=0), \
                     patch.object(probe.os, "geteuid", return_value=0), \
                     patch.object(probe.os, "chown"), patch.object(probe.socket, "socket"), \
                     patch.object(probe.uuid, "uuid4", return_value=SimpleNamespace(hex="a" * 32)), \
                     patch.object(probe, "choose_uids", return_value=list(range(700000, 700005))), \
                     patch.object(probe, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as commands, \
                     patch.object(probe, "verify_ready", side_effect=ready), \
                     patch.object(probe, "show", side_effect=show), \
                     patch.object(probe, "cgroup_limits", return_value={"memory.max": str(512 * 1024**2),
                                  "memory.swap.max": "0", "pids.max": "24", "cpu.max": "50000 100000"}), \
                     patch.object(probe, "stopped", return_value=True), \
                     patch.object(probe, "cgroup_empty", return_value=True), \
                     patch.object(probe, "await_file", side_effect=response):
                    result = probe.probe()
                if corruption == (0, "parent"):
                    self.assertEqual("CLEANUP_UNCERTAIN", result["status"])
                    self.assertFalse(result["cleanup"]["parent_quiescent"])
                    self.assertTrue(result["cleanup"]["parent_empty"])
                    self.assertTrue((base / token).is_dir())
                    self.assertFalse(any("revert" in call.args[0] for call in commands.call_args_list))
                    continue
                self.assertEqual("FAILED" if corruption else "PASS", result["status"])
                self.assertTrue(result["cleanup"]["parent_empty"])
                self.assertTrue(result["cleanup"]["fixture_removed"])
                self.assertFalse((base / token).exists())
                if not corruption:
                    self.assertEqual(10, len(result["observations"]))
                if corruption == (0, "readiness"):
                    self.assertEqual([100, 101], [item["pid"] for item in result["identities"]])

    def test_collected_unit_still_checks_original_cgroup(self):
        unit = "lhp1aaaaaaaaaaaas0.service"
        with patch.object(probe, "show", return_value=dict(LoadState="not-found", ActiveState="inactive",
                     MainPID="0", ControlPID="0", Job="", ControlGroup="")), \
             patch.object(probe, "cgroup_empty", return_value=False) as empty:
            self.assertFalse(probe.stopped(unit))
            empty.assert_called_once_with("/lhp1aaaaaaaaaaaa.slice/" + unit)
            empty.return_value = True
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
