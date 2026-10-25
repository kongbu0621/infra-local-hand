"""Deployment adapters: real fork/flock and filesystem effects, finite fake managers.

The fake manager tests exercise decision boundaries, not systemd/Docker acceptance.
Live, isolated transport checks are reported separately from these unit checks.
"""
import copy
import fcntl
import json
import os
from pathlib import Path
import signal
import tempfile
import time
import unittest

from admin.local_hand_deploy.supervision import AdapterError, SupervisedRunner, boot_id, verify_lock
from admin.local_hand_deploy.services import SystemdAdapter, tree_snapshot, validate_guard
from admin.local_hand_deploy.gateway import GatewayAdapter
from admin.local_hand_deploy.systemd_bus import SystemdBus


class UnitObservationTests(unittest.TestCase):
    class Bus(SystemdBus):
        def __init__(self, properties, file_state_error=None):
            self.observed = properties
            self.file_state_error = file_state_error
            self.methods = []

        def call(self, method, arguments=(), **kwargs):
            self.methods.append(method)
            if method == "LoadUnit":
                return ["/org/freedesktop/systemd1/unit/fixture"]
            if method == "GetUnitFileState":
                if self.file_state_error:
                    raise self.file_state_error
                return ["disabled"]
            raise AssertionError(method)

        def properties(self, path, interface):
            return dict(self.observed) if interface.endswith(".Unit") else {}

    def test_loaded_dependency_without_unit_file_keeps_actual_runtime_state(self):
        for name in ("system.slice", "fixture.mount", "fixture.target"):
            with self.subTest(name=name):
                bus = self.Bus({"LoadState": "loaded", "ActiveState": "active",
                                "Job": [0, "/"], "UnitFileState": "", "FragmentPath": ""},
                               AdapterError("SYSTEMD_BUS_ERRNO_2"))
                observed = bus.unit(name)
                self.assertEqual("active", observed["ActiveState"])
                self.assertEqual("", observed["UnitFileState"])
                self.assertNotIn("GetUnitFileState", bus.methods)

    def test_inactive_dependency_still_blocks_starting_service(self):
        class Bus(self.Bus):
            def unit(self, name):
                if name == "fixture.service":
                    return {"LoadState": "loaded", "ActiveState": "inactive", "UnitFileState": "disabled",
                            "Type": "exec", "KillMode": "control-group", "Restart": "no",
                            "Requires": ["system.slice"]}
                return super().unit(name)
        profile = {"units": {"fixture.service": {"read_only_dependencies": ["system.slice"]}}}
        adapter = SystemdAdapter(profile, None, bus_factory=lambda: None)
        bus = Bus({"LoadState": "loaded", "ActiveState": "inactive", "Job": [0, "/"], "UnitFileState": ""})
        with self.assertRaisesRegex(AdapterError, "SHARED_DEPENDENCY_NOT_READY"):
            adapter._snapshot(bus, "fixture.service", starting=True)

    def test_service_file_state_errors_are_not_suppressed(self):
        for errno in (2, 13):
            with self.subTest(errno=errno):
                bus = self.Bus({"LoadState": "loaded", "ActiveState": "active"},
                               AdapterError("SYSTEMD_BUS_ERRNO_" + str(errno)))
                with self.assertRaisesRegex(AdapterError, "SYSTEMD_BUS_ERRNO_" + str(errno)):
                    bus.unit("fixture.service")
        missing = self.Bus({"LoadState": "not-found", "ActiveState": "inactive"},
                           AdapterError("SYSTEMD_BUS_ERRNO_2"))
        self.assertEqual("absent", missing.unit("fixture.service")["UnitFileState"])
        loaded = self.Bus({"LoadState": "loaded", "ActiveState": "active", "UnitFileState": "enabled"})
        self.assertEqual("disabled", loaded.unit("fixture.service")["UnitFileState"])


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fd = os.open(self.root / "node.lock", os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.runner = SupervisedRunner(self.root / "calls", timeout=0.3)

    def tearDown(self):
        os.close(self.fd)
        self.temp.cleanup()

    def test_real_child_inherits_exact_lock_and_records_before_effect(self):
        intent = self.root / "intent"
        effect = self.root / "effect"
        def persist(binding):
            intent.write_text(json.dumps(binding))
        def perform(action, emit):
            verify_lock(self.fd)
            self.assertTrue(intent.exists())
            emit({"kind": "before_effect"})
            effect.write_text("one")
            return {"done": True}
        result = self.runner.run({"kind": "fixture"}, perform, attempt_id="a", lock_fd=self.fd, persist_intent=persist)
        self.assertTrue(result["closed"])
        self.assertEqual("returned", result["result"]["status"])
        self.assertEqual("one", effect.read_text())
        replay = self.runner.run({"kind": "fixture"}, lambda *_: effect.write_text("two"), attempt_id="a", lock_fd=self.fd, persist_intent=persist)
        self.assertEqual(result["binding"], replay["binding"])
        self.assertEqual("one", effect.read_text())

    def test_other_open_description_does_not_claim_the_lock(self):
        other = os.open(self.root / "node.lock", os.O_RDWR)
        try:
            with self.assertRaisesRegex(AdapterError, "DESCRIPTION_NOT_HELD"):
                verify_lock(other)
        finally:
            os.close(other)

    def test_failed_intent_never_dispatches(self):
        def persist(_):
            raise OSError("disk full")
        with self.assertRaises(OSError):
            self.runner.run({}, lambda *_: (self.root / "bad").touch(), attempt_id="b", lock_fd=self.fd, persist_intent=persist)
        self.assertFalse((self.root / "bad").exists())

    def test_read_only_supervisor_does_not_create_directory(self):
        path = self.root / "not-created"
        runner = SupervisedRunner(path, create=False)
        self.assertFalse(path.exists())
        with self.assertRaisesRegex(AdapterError, "READ_ONLY"):
            runner.run({}, lambda *_: None, attempt_id="none", lock_fd=self.fd, persist_intent=lambda _: None)
        self.assertFalse(path.exists())
        runner.ensure_directory()
        self.assertTrue(path.is_dir())

    def test_timeout_retains_unknown_and_does_not_repeat(self):
        def perform(action, emit):
            (self.root / "count").write_text("1")
            time.sleep(2)
        result = self.runner.run({}, perform, attempt_id="c", lock_fd=self.fd, persist_intent=lambda _: None)
        self.assertTrue(result["closed"])
        self.assertEqual("unknown", result["result"]["status"])
        self.assertEqual("TimeoutError", result["result"]["error_type"])
        self.runner.run({}, perform, attempt_id="c", lock_fd=self.fd, persist_intent=lambda _: None)
        self.assertEqual("1", (self.root / "count").read_text())

    def test_reporting_failure_keeps_original_intent_and_effect(self):
        def perform(action, emit):
            (self.root / "done").write_text("yes")
            return "x" * 70000
        result = self.runner.run({}, perform, attempt_id="d", lock_fd=self.fd, persist_intent=lambda _: None)
        self.assertTrue(result["closed"])
        self.assertIsNone(result["result"])
        self.assertEqual("yes", (self.root / "done").read_text())

    def test_real_lock_survives_coordinator_exit_while_child_is_running(self):
        # The intermediate coordinator creates a supervised child, then is killed.
        # The grandchild keeps the inherited open-file-description lock until exit.
        ready, release = self.root / "ready", self.root / "release"
        coordinator = os.fork()
        if coordinator == 0:
            def perform(action, emit):
                ready.write_text(str(os.getpid()))
                while not release.exists():
                    time.sleep(0.01)
            runner = SupervisedRunner(self.root / "survivor", timeout=2)
            runner.run({}, perform, attempt_id="survivor", lock_fd=self.fd, persist_intent=lambda _: None)
            os._exit(0)
        for _ in range(100):
            if ready.exists():
                break
            time.sleep(0.01)
        self.assertTrue(ready.exists())
        os.kill(coordinator, signal.SIGKILL)
        os.waitpid(coordinator, 0)
        os.close(self.fd)
        self.fd = os.open(self.root / "node.lock", os.O_RDWR)
        with self.assertRaises(BlockingIOError):
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        release.touch()
        for _ in range(200):
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(0.01)
        else:
            self.fail("supervised child did not release its inherited lock")


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runner = SupervisedRunner(self.root / "calls")
        self.fd = os.open(self.root / "lock", os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.links = self.root / "links"
        self.links.mkdir(mode=0o700)
        self.path = str(self.links / "fixture.service")
        self.profile = {"units": {"fixture.service": {"policy_links": {
            self.path: {"policy": "enabled-runtime", "target": "/fixture/unit.service"}}}}}
        self.adapter = SystemdAdapter(self.profile, self.runner)

    def tearDown(self):
        os.close(self.fd)
        self.temp.cleanup()

    def test_exact_link_policy_effect_replays_without_replacing_link(self):
        action = {"kind": "service_policy_link", "target": "fixture.service", "path": self.path,
                  "before": {"kind": "absent"}, "after": {"kind": "link", "target": "/fixture/unit.service"}}
        result = self.adapter.execute(action, attempt_id="link", lock_fd=self.fd, persist_intent=lambda _: None)
        self.assertTrue(result["postcondition"])
        inode = Path(self.path).lstat().st_ino
        result2 = self.adapter.execute(action, attempt_id="link2", lock_fd=self.fd, persist_intent=lambda _: self.fail("reissued"), previous=result["attempt"])
        self.assertTrue(result2["postcondition"])
        self.assertEqual(inode, Path(self.path).lstat().st_ino)

    def test_policy_cannot_follow_or_replace_independent_link(self):
        os.symlink("/unrelated", self.path)
        action = {"kind": "service_policy_link", "target": "fixture.service", "path": self.path,
                  "before": {"kind": "absent"}, "after": {"kind": "link", "target": "/fixture/unit.service"}}
        with self.assertRaisesRegex(AdapterError, "CONFLICT"):
            self.adapter.execute(action, attempt_id="bad", lock_fd=self.fd, persist_intent=lambda _: None)
        self.assertEqual("/unrelated", os.readlink(self.path))

    def test_shared_reload_requires_full_loaded_baseline_and_detects_unrelated_change(self):
        with self.assertRaisesRegex(AdapterError, "LOADED_BASELINE"):
            self.adapter.check_reload_scope()
        scope = self.root / "units"
        scope.mkdir()
        config = scope / "other.service"
        config.write_text("original")
        baseline = tree_snapshot([str(scope)])
        self.profile["reload_scope"] = {"roots": [str(scope)], "unit_search_roots": [str(scope)],
            "generator_program_roots": [], "generator_inputs": [], "generator_output_roots": [], "loaded_snapshot": baseline}
        self.assertEqual(baseline, self.adapter.check_reload_scope())
        config.write_text("independent edit")
        with self.assertRaisesRegex(AdapterError, "UNACCOUNTED_CHANGES"):
            self.adapter.check_reload_scope()

    def test_candidate_guard_rejects_previous_boot_or_attempt(self):
        target = {"config_digest": "a" * 64, "deployment_digest": "b" * 64}
        proof = {**target, "descriptor_digest": "c" * 64, "mode": "candidate", "target_running": True,
                 "boot": boot_id(), "attempt_id": "current"}
        self.assertEqual(proof, validate_guard(proof, target, attempt_id="current"))
        for change in ({"boot": "old"}, {"attempt_id": "old"}, {"mode": "blocked"}, {"target_running": False}):
            with self.subTest(change=change), self.assertRaises(AdapterError):
                validate_guard({**proof, **change}, target, attempt_id="current")
        with self.assertRaises(AdapterError):
            validate_guard(True, target, attempt_id="current")

    def test_dependency_failure_does_not_prevent_stopping_or_observing(self):
        class Bus:
            def unit(self, name):
                if name == "shared.target":
                    return {"ActiveState": "inactive", "Job": [0, "/"]}
                return {"LoadState": "loaded", "ActiveState": "active", "UnitFileState": "disabled",
                        "Type": "exec", "KillMode": "control-group", "Restart": "no",
                        "Requires": ["shared.target"], "MainPID": 123, "Job": [0, "/"]}
        self.profile["units"]["fixture.service"]["read_only_dependencies"] = ["shared.target"]
        observed = self.adapter._snapshot(Bus(), "fixture.service")
        self.assertEqual("active", observed["active"])
        with self.assertRaisesRegex(AdapterError, "DEPENDENCY_NOT_READY"):
            self.adapter._snapshot(Bus(), "fixture.service", starting=True)
        actions = self.adapter.plan({"fixture.service": {"running": False, "policy": "disabled"}},
                                    {"units": {"fixture.service": observed}, "jobs": []}, _check_global=False)
        self.assertEqual(["service_stop"], [a["kind"] for a in actions])

    def test_definition_change_restarts_and_restore_keeps_original_loaded_config(self):
        old = {"active": "active", "policy": "disabled", "definition_digest": "1" * 64,
               "loaded": {"config_digest": "2" * 64, "deployment_digest": "3" * 64},
               "links": {self.path: {"kind": "absent"}}}
        target = {"running": True, "policy": "disabled", "definition_digest": "4" * 64,
                  "config_digest": "2" * 64, "deployment_digest": "3" * 64}
        actions = self.adapter.plan({"fixture.service": target},
            {"units": {"fixture.service": old}, "jobs": []}, _check_global=False)
        self.assertEqual(["service_stop", "service_start"], [a["kind"] for a in actions])
        # Candidate start failed after reload. Restore starts with original
        # loaded configuration, not with the candidate or a reversed stop argv.
        current = {**old, "active": "failed", "definition_digest": "4" * 64, "loaded": None}
        restore = self.adapter.plan_restore(actions, {"units": {"fixture.service": current}, "jobs": []})
        self.assertEqual(["service_start"], [a["kind"] for a in restore])
        self.assertEqual("1" * 64, restore[0]["after"]["definition_digest"])
        self.assertEqual("2" * 64, restore[0]["after"]["config_digest"])

    def test_reload_before_first_dispatch_is_closed_and_executable(self):
        class Bus:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def jobs(self): return []
            def properties(self, *args): return {}
            def unit(self, name):
                return {"LoadState": "loaded", "ActiveState": "inactive", "UnitFileState": "disabled",
                        "Type": "exec", "KillMode": "control-group", "Restart": "no", "NeedDaemonReload": True}
        scope = self.root / "unit-tree"
        scope.mkdir()
        (scope / "fixture.service").write_text("unit")
        baseline = tree_snapshot([str(scope)])
        self.profile["reload_scope"] = {"roots": [str(scope)], "unit_search_roots": [str(scope)],
            "generator_program_roots": [], "generator_inputs": [], "generator_output_roots": [], "loaded_snapshot": baseline}
        adapter = SystemdAdapter(self.profile, self.runner, bus_factory=Bus)
        action = adapter.plan_reload(baseline)
        observed = adapter.observe_action(action)
        self.assertTrue(observed["closed"])
        self.assertFalse(observed["postcondition"])
        self.assertEqual("original", observed["outcome"])

    def test_compensation_reload_accepts_only_finite_retained_history(self):
        scope = self.root / "history-tree"
        scope.mkdir()
        unit = scope / "fixture.service"
        unit.write_text("original")
        original = tree_snapshot([str(scope)])
        unit.write_text("candidate-one")
        intermediate = tree_snapshot([str(scope)])
        unit.write_text("candidate-two")
        candidate = tree_snapshot([str(scope)])
        self.profile["reload_scope"] = {"roots": [str(scope)]}
        actions = [{"kind": "service_daemon_reload", "before": original, "after": intermediate},
                   {"kind": "service_daemon_reload", "before": intermediate, "after": candidate},
                   {"kind": "service_daemon_reload", "before": candidate, "after": original}]
        unit.write_text("candidate-one")
        restore = self.adapter.plan_restore(actions, {"units": {}, "jobs": []})
        self.assertEqual(original, restore[-1]["after"])
        unit.write_text("independent value")
        with self.assertRaisesRegex(AdapterError, "UNACCOUNTED"):
            self.adapter.plan_restore(actions, {"units": {}, "jobs": []})

    def test_reload_retained_staging_is_exact_and_not_part_of_restored_target(self):
        scope = self.root / "retained-tree"
        scope.mkdir()
        unit = scope / "fixture.service"
        unit.write_text("original")
        original = tree_snapshot([str(scope)])
        unit.write_text("candidate")
        candidate = tree_snapshot([str(scope)])
        staged = scope / ".retained-exact"
        staged.write_text("original")
        retained = {str(staged): tree_snapshot([str(staged)])[str(staged)]}
        self.profile["reload_scope"] = {"roots": [str(scope)]}
        actions = [{"kind": "service_daemon_reload", "before": original, "after": candidate}]
        result = self.adapter.plan_restore(actions, {"units": {}, "jobs": []},
                                           retained_tree=retained, retained_target={})
        self.assertEqual(original, result[-1]["after"])
        self.assertIn(str(staged), result[-1]["before"])
        staged.write_text("independent value")
        with self.assertRaisesRegex(AdapterError, "UNACCOUNTED"):
            self.adapter.plan_restore(actions, {"units": {}, "jobs": []},
                                      retained_tree=retained, retained_target={})
        staged.unlink()
        unit.unlink()
        # An empty retained inventory must not add absence as an accepted value
        # for every original configuration member.
        with self.assertRaisesRegex(AdapterError, "UNACCOUNTED"):
            self.adapter.plan_restore(actions, {"units": {}, "jobs": []})

    def test_new_process_recovers_durable_intent_before_child_registration(self):
        action = {"kind": "service_policy_link", "target": "fixture.service", "path": self.path,
                  "before": {"kind": "absent"}, "after": {"kind": "link", "target": "/fixture/unit.service"}}
        intent = self.root / "saved-intent.json"
        coordinator = os.fork()
        if coordinator == 0:
            def persist(binding):
                intent.write_text(json.dumps(binding))
                os._exit(17)
            self.adapter.execute(action, attempt_id="old", lock_fd=self.fd, persist_intent=persist)
            os._exit(99)
        _, status = os.waitpid(coordinator, 0)
        self.assertEqual(17, os.waitstatus_to_exitcode(status))
        os.close(self.fd)
        self.fd = os.open(self.root / "lock", os.O_RDWR)
        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = json.loads(intent.read_text())
        fresh = SystemdAdapter(self.profile, SupervisedRunner(self.root / "calls"))
        observed = fresh.observe_action(action, previous, lock_fd=self.fd)
        self.assertEqual("original", observed["outcome"])
        self.assertTrue(observed["closed"])
        resumed = fresh.execute(action, attempt_id="new", lock_fd=self.fd, persist_intent=lambda _: None, previous=previous)
        self.assertTrue(resumed["postcondition"])
        self.assertEqual("/fixture/unit.service", os.readlink(self.path))


class EngineFixture:
    def __init__(self):
        self.container = None
        self.calls = []

    def request(self, method, path, body=None, **kwargs):
        self.calls.append((method, path, body))
        if path == "/info":
            return {"ID": "daemon-fixture"}
        if path.startswith("/images/"):
            return {"Id": "sha256:" + "a" * 64, "Config": {}}
        if method == "GET" and path.startswith("/containers/"):
            return self.container
        raise AssertionError((method, path))


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runner = SupervisedRunner(Path(self.temp.name) / "calls")
        self.engine = EngineFixture()
        self.profile = {"project": "fixture", "service": "gateway", "container_name": "fixture-gateway", "daemon_id": "daemon-fixture",
            "compose": {"services": {"gateway": {"image": "sha256:" + "a" * 64, "networks": {}, "restart": "no"}}}}

    def tearDown(self):
        self.temp.cleanup()

    def adapter(self):
        return GatewayAdapter(self.profile, self.runner, engine=self.engine)

    def container(self, compose, *, name="original", running=True, labels=None):
        source = compose["services"]["gateway"]
        return {"Id": name, "Image": "sha256:" + "a" * 64,
                "Config": {"Labels": {"com.docker.compose.project": "fixture", "com.docker.compose.service": "gateway", **(labels or {})},
                           "Cmd": source.get("command"), "Entrypoint": source.get("entrypoint"), "User": source.get("user"),
                           "Env": [k + "=" + str(v) for k, v in source.get("environment", {}).items()]},
                "HostConfig": {"RestartPolicy": {"Name": source.get("restart", "no")}},
                "State": {"Running": running}, "NetworkSettings": {"Networks": {"none": {}}}}

    def test_no_implicit_dependency_network_volume_or_pull(self):
        adapter = self.adapter()
        target = {"running": True, "config_digest": "b" * 64, "deployment_digest": "c" * 64}
        actions = adapter.plan(target)
        self.assertEqual(["gateway_create", "gateway_start"], [a["kind"] for a in actions])
        self.assertTrue(all(method == "GET" for method, _, _ in self.engine.calls))
        body = adapter._create_body(target, "one")
        self.assertEqual("none", body["HostConfig"]["NetworkMode"])
        self.assertFalse(body["HostConfig"]["AutoRemove"])
        self.assertEqual([], body["HostConfig"]["Mounts"])
        self.assertNotIn("Volumes", body)

    def test_missing_external_dependency_is_not_created(self):
        self.profile["compose"]["services"]["gateway"]["depends_on"] = {"identity": {"condition": "service_healthy"}}
        with self.assertRaisesRegex(AdapterError, "DEPENDENCY_BINDING"):
            self.adapter().plan({"running": True})
        self.assertTrue(all(method == "GET" for method, _, _ in self.engine.calls))

    def test_implicit_network_or_build_is_rejected(self):
        for extra in ({"build": "."}, {"networks": {"default": {}}}, {"command": "sh -c echo bad"}):
            with self.subTest(extra=extra):
                profile = copy.deepcopy(self.profile)
                profile["compose"]["services"]["gateway"].update(extra)
                with self.assertRaises(AdapterError):
                    GatewayAdapter(profile, self.runner, engine=self.engine)

    def test_original_absence_restore_does_not_start_gateway(self):
        adapter = self.adapter()
        target = {"running": True, "config_digest": "b" * 64, "deployment_digest": "c" * 64}
        actions = adapter.plan(target)
        self.assertEqual([], adapter.plan_restore(actions))

    def test_stopped_container_creation_does_not_require_permission_to_run(self):
        target = {"running": False, "config_digest": "b" * 64, "deployment_digest": "c" * 64}
        actions = self.adapter().plan(target)
        self.assertEqual(["gateway_create"], [a["kind"] for a in actions])
        proof = {**target, "descriptor_digest": "d" * 64, "mode": "candidate", "target_running": False,
                 "boot": boot_id(), "attempt_id": "create-stopped"}
        self.assertEqual(proof, validate_guard(proof, target, attempt_id="create-stopped", allow_stopped=True))
        with self.assertRaisesRegex(AdapterError, "BLOCKED"):
            validate_guard(proof, {**target, "running": True}, attempt_id="create-stopped", allow_stopped=True)

    def test_stopped_container_observation_does_not_require_live_route_listener(self):
        self.engine.container = self.container(self.profile["compose"], running=False)
        def unavailable(_):
            raise AssertionError("stopped container cannot run its readiness listener")
        adapter = GatewayAdapter(self.profile, self.runner, engine=self.engine, route_probe=unavailable)
        observed = adapter.observe()
        self.assertEqual("stopped", observed["status"])
        self.assertIsNone(observed["route"])
        action = {"kind": "gateway_stop", "target": "gateway", "before": observed, "after": {"running": False}}
        self.assertTrue(adapter.observe_action(action)["postcondition"])

    def test_running_unhealthy_container_can_be_stopped_and_removed_by_exact_engine_identity(self):
        self.engine.container = self.container(self.profile["compose"], labels={
            "local-hand.deploy.config": "b" * 64, "local-hand.deploy.deployment": "c" * 64})
        before = {**self.adapter().observe(), "route": {"protocol_ready": True}}
        def unavailable(_): raise RuntimeError("actual status endpoint is unavailable")
        adapter = GatewayAdapter(self.profile, self.runner, engine=self.engine, route_probe=unavailable)
        action = {"kind": "gateway_stop", "target": "gateway", "before": before, "after": {"running": False}}
        self.assertEqual("original", adapter.observe_action(action)["outcome"])
        planned = adapter.plan({"present": False, "running": False})
        self.assertEqual(["gateway_stop", "gateway_remove"], [step["kind"] for step in planned])
        original_request = self.engine.request
        def mutate(method, path, body=None, **kwargs):
            if method == "POST" and path == "/containers/original/stop?t=10":
                self.engine.container["State"]["Running"] = False
                return None
            if method == "DELETE" and path == "/containers/original?force=false&v=false":
                self.engine.container = None
                return None
            return original_request(method, path, body, **kwargs)
        self.engine.request = mutate
        adapter._perform(action, lambda _: None)
        self.assertTrue(adapter.observe_action(action)["postcondition"])
        adapter._perform(planned[1], lambda _: None)
        self.assertTrue(adapter.observe_action(planned[1])["postcondition"])

    def test_unhealthy_stop_still_rejects_changed_container_or_configuration(self):
        self.engine.container = self.container(self.profile["compose"])
        before = self.adapter().observe()
        def unavailable(_): raise RuntimeError("status unavailable")
        adapter = GatewayAdapter(self.profile, self.runner, engine=self.engine, route_probe=unavailable)
        action = {"kind": "gateway_stop", "target": "gateway", "before": before, "after": {"running": False}}
        self.engine.container["Id"] = "independent"
        self.assertEqual("conflict", adapter.observe_action(action)["outcome"])
        with self.assertRaisesRegex(AdapterError, "ID_CHANGED"):
            adapter._perform(action, lambda _: None)
        self.engine.container["Id"] = "original"
        self.engine.container["Config"]["Cmd"] = ["changed-command"]
        with self.assertRaisesRegex(AdapterError, "OUTSIDE_RETAINED"):
            adapter.observe_action(action)
        self.assertTrue(all(method == "GET" for method, _, _ in self.engine.calls))

    def test_unhealthy_candidate_compensation_is_planned_but_start_still_requires_route(self):
        original = copy.deepcopy(self.profile["compose"])
        original["services"]["gateway"]["command"] = ["serve", "original"]
        self.profile["original_compose"] = original
        self.profile["compose"]["services"]["gateway"]["command"] = ["serve", "candidate"]
        self.engine.container = self.container(original)
        before = {**self.adapter().observe(), "config_digest": "1" * 64, "deployment_digest": "2" * 64}
        forward = self.adapter().plan({"running": True, "config_digest": "3" * 64, "deployment_digest": "4" * 64}, before)
        self.engine.container = self.container(self.profile["compose"], name="candidate", labels={
            "local-hand.deploy.config": "3" * 64, "local-hand.deploy.deployment": "4" * 64})
        def unavailable(_): raise RuntimeError("status unavailable")
        adapter = GatewayAdapter(self.profile, self.runner, engine=self.engine, route_probe=unavailable)
        restore = adapter.plan_restore(forward)
        self.assertEqual(["gateway_stop", "gateway_remove", "gateway_create", "gateway_start"], [step["kind"] for step in restore])
        self.assertEqual("original", adapter.observe_action(restore[0])["outcome"])
        with self.assertRaisesRegex(RuntimeError, "status unavailable"):
            adapter.observe_action(forward[-1])
        with self.assertRaisesRegex(RuntimeError, "status unavailable"):
            adapter.observe()

    def test_restore_retains_original_compose_and_verified_legacy_identity(self):
        original = copy.deepcopy(self.profile["compose"])
        original["services"]["gateway"]["command"] = ["serve", "original"]
        self.profile["original_compose"] = original
        self.profile["compose"]["services"]["gateway"]["command"] = ["serve", "candidate"]
        self.engine.container = self.container(original)
        adapter = self.adapter()
        before = {**adapter.observe(), "config_digest": "1" * 64, "deployment_digest": "2" * 64}
        actions = adapter.plan({"running": True, "config_digest": "3" * 64, "deployment_digest": "4" * 64}, before)
        self.assertEqual(["gateway_stop", "gateway_remove", "gateway_create", "gateway_start"], [a["kind"] for a in actions])
        # Candidate has not replaced the original yet; rollback only restarts the
        # exact original object, even though it predates deployment labels.
        self.engine.container["State"]["Running"] = False
        restore = adapter.plan_restore(actions)
        self.assertEqual(["gateway_start"], [a["kind"] for a in restore])
        self.assertEqual(original, restore[0]["compose"])
        self.assertEqual("1" * 64, restore[0]["after"]["config_digest"])
        # Once replaced, the original proof is not transferred to the new object;
        # restoration recreates its original argv and configuration identity.
        self.engine.container = self.container(self.profile["compose"], name="candidate", labels={
            "local-hand.deploy.config": "3" * 64, "local-hand.deploy.deployment": "4" * 64})
        restore = adapter.plan_restore(actions)
        self.assertEqual(["gateway_stop", "gateway_remove", "gateway_create", "gateway_start"], [a["kind"] for a in restore])
        self.assertTrue(all(a["compose"] == original for a in restore))
        self.assertEqual(["serve", "original"], adapter._using(original)._create_body(restore[2]["after"], "restore")["Cmd"])

    def test_legacy_gateway_missing_original_binding_is_not_guessed(self):
        self.engine.container = self.container(self.profile["compose"])
        adapter = self.adapter()
        actions = adapter.plan({"running": True, "config_digest": "3" * 64, "deployment_digest": "4" * 64})
        with self.assertRaisesRegex(AdapterError, "ORIGINAL_GATEWAY_CONFIGURATION_BINDING"):
            adapter.plan_restore(actions)

    def test_corrective_chain_retains_intermediate_gateway_spec_for_restore(self):
        original = copy.deepcopy(self.profile["compose"])
        original["services"]["gateway"]["command"] = ["serve", "original"]
        intermediate = copy.deepcopy(original)
        intermediate["services"]["gateway"]["command"] = ["serve", "intermediate"]
        self.profile["compose"]["services"]["gateway"]["command"] = ["serve", "corrected"]
        self.profile.update(original_compose=original, retained_composes=[intermediate])
        self.engine.container = self.container(intermediate, name="intermediate", labels={
            "local-hand.deploy.config": "3" * 64, "local-hand.deploy.deployment": "4" * 64})
        adapter = self.adapter()
        self.assertEqual(intermediate, adapter.observe()["compose"])
        restored = adapter._using(original)
        self.assertEqual(intermediate, restored.observe()["compose"])
        self.assertTrue(all(method == "GET" for method, _, _ in self.engine.calls))

    def test_foreign_container_and_daemon_rejected(self):
        self.engine.container = {"Id": "foreign", "Config": {"Labels": {}}, "State": {"Running": True}}
        with self.assertRaisesRegex(AdapterError, "FOREIGN"):
            self.adapter().observe()
        self.profile["daemon_id"] = "different"
        with self.assertRaisesRegex(AdapterError, "DAEMON_ID"):
            self.adapter().observe()


if __name__ == "__main__":
    unittest.main()
