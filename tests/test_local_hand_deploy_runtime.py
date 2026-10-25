"""Concrete configuration planning, guarded publication and compensation tests."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from admin.local_hand_deploy import files
from admin.local_hand_deploy.model import DeployError, new_operation, seal_plan
from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.planner import MANIFEST_SCHEMA, PROFILE_SCHEMA, build_plan
from admin.local_hand_deploy.runtime import ConcreteEnvironment, PlanningEnvironment
from admin.local_hand_deploy.services import tree_snapshot
from admin.local_hand_deploy.store import Store
from local_hand_jobs import maintenance, startup


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.owner = os.geteuid()
        self.config = self.root / "manager.json"
        self.candidate = self.root / "candidate.json"
        self.selection = self.root / "selection.json"
        self.gate_dir = self.root / "gate"
        self.gate_dir.mkdir(mode=0o700)
        self.a, self.b = "a" * 64, "b" * 64
        self.profile = {"schema": PROFILE_SCHEMA, "owner_uid": self.owner,
            "startup_descriptor": str(self.selection), "maintenance_directory": str(self.gate_dir),
            "filesystem_support": {"ordinary_handles": True, "fsid": True, "reboot_verified": True},
            "guarded_components": {"manager": {"configuration": str(self.config), "entrypoints": ["listener"]}},
            "probes": {"manager": {"kind": "resident", "socket": str(self.root / "manager.sock"), "peer_uid": self.owner}}}
        self.old_config, self.new_config = self.configuration(self.a), self.configuration(self.b)
        self.write(self.config, self.old_config); self.write(self.candidate, self.new_config)
        self.source = self.deployment(self.a, self.old_config)
        self.target = self.deployment(self.b, self.new_config)
        self.write(self.selection, self.source["selection"])
        self.gate = maintenance.MaintenanceGate(self.gate_dir, "node", owner_uid=self.owner)
        self.gate.initialize(self.a, "original-decision", bootstrap=True)
        self.manifest = {"schema": MANIFEST_SCHEMA, "request_id": "request", "node_id": "node",
                         "source": self.source, "target": self.target, "profile": self.profile,
                         "files": [{"source": str(self.candidate), "target": str(self.config)}]}
        try:
            fd = os.open(self.config, os.O_RDONLY)
            try:
                files._binding(fd)
            finally:
                os.close(fd)
        except files.FileError as error:
            if error.code == "UNSUPPORTED":
                self.skipTest(str(error))
            raise

    def write(self, path, value):
        path.write_bytes(startup.canonical(value))
        path.chmod(0o600)

    def configuration(self, deployment):
        return {"installation": {"installed": {"payload_digest": "c" * 64}},
                "maintenance": {"schema": maintenance.CONFIG_SCHEMA, "node_id": "node",
                    "deployment_digest": deployment, "directory": str(self.gate_dir), "startup_descriptor": str(self.selection)}}

    def deployment(self, deployment, config):
        return {"deployment_digest": deployment, "selection": {"schema": startup.SCHEMA,
            "node_id": "node", "deployment_digest": deployment, "decision_id": "original-decision", "owner": None,
            "mode": "stable", "permit": None, "members": [{"path": str(self.config),
                "sha256": hashlib.sha256(startup.canonical(config)).hexdigest()}],
            "components": {"manager": {"configuration_digest": maintenance.digest({k: v for k, v in config.items() if k != "maintenance"}),
                "payload_digest": "c" * 64, "entry": "local", "running": False}}}}

    def store(self):
        store = Store(self.root / "state", "node", owner_uid=self.owner)
        store.initialize()
        return store

    def test_plan_is_read_only_and_fixed_actions(self):
        before = {str(path): (path.stat().st_ino, path.stat().st_mtime_ns) for path in self.root.rglob("*")}
        plan = build_plan(self.manifest)
        after = {str(path): (path.stat().st_ino, path.stat().st_mtime_ns) for path in self.root.rglob("*")}
        self.assertEqual(before, after)
        self.assertEqual(["file"], [step["kind"] for step in plan["steps"]])
        self.assertFalse((self.root / "state").exists())

    def test_unsupported_profile_does_not_prepare(self):
        self.manifest["profile"]["shell"] = "anything"
        with self.assertRaises(DeployError):
            build_plan(self.manifest)
        self.assertEqual(startup.canonical(self.old_config), self.config.read_bytes())

    def test_target_digest_and_actual_candidate_must_match(self):
        self.write(self.candidate, self.old_config)
        with self.assertRaises(DeployError):
            build_plan(self.manifest)

    def test_unknown_filesystem_profile_is_not_assumed_migrated(self):
        self.manifest["profile"]["filesystem_support"]["reboot_verified"] = False
        with self.assertRaisesRegex(DeployError, "filesystem"):
            build_plan(self.manifest)

    def test_unguarded_running_component_cannot_be_switched(self):
        self.manifest["source"]["selection"]["components"]["manager"]["running"] = True
        with self.assertRaisesRegex(DeployError, "uncontrolled"):
            build_plan(self.manifest)

    def test_identical_configuration_has_no_steps(self):
        self.manifest["target"] = copy.deepcopy(self.source)
        self.manifest["files"][0]["source"] = str(self.config)
        self.assertEqual([], build_plan(self.manifest)["steps"])

    def test_concrete_file_publication_and_stable_release_precheck(self):
        plan = build_plan(self.manifest)
        store = self.store()
        env = ConcreteEnvironment(plan, store, self.gate)
        with store.locked():
            op = store.create(plan)
            env.preflight(op)
            step, record = plan["steps"][0], op["steps"][0]
            record["prepared"] = env.prepare(step, op, record)
            self.gate.close(op["id"])
            op["startup"]["current"] = env.block_startup(op)
            observed = env.execute(step, record["prepared"], op, "attempt", lambda _: None)
            record["effective"] = observed["effective"]
            self.assertEqual("target", observed["state"])
            self.assertTrue(env.check_local(op)["passed"])
            op["decision"] = "COMMITTED"; op["decision_id"] = "decision"
            self.assertTrue(env.release_valid(op)["passed"])
            with self.assertRaisesRegex(DeployError, "saved matching decision"):
                env.publish_stable(op)
            store.save(op, "DECISION")
            # No services are running: publish the verified selection directly.
            env.publish_stable(op)
            self.assertTrue(env.release_valid(op)["passed"])
        self.assertEqual(self.new_config, json.loads(self.config.read_bytes()))

    def test_real_store_coordinator_apply_and_committed_rollback(self):
        plan = build_plan(self.manifest)
        store = self.store()
        coordinator = Coordinator(store, self.gate, ConcreteEnvironment(plan, store, self.gate))
        result = coordinator.apply(plan)
        self.assertEqual("COMMITTED", result["decision"])
        self.assertTrue(result["released"], result.get("waiting"))
        self.assertEqual(self.b, self.gate.snapshot()["deployment_digest"])
        restored = coordinator.rollback(result["id"])
        self.assertEqual("COMMITTED", restored["decision"], restored.get("waiting"))
        self.assertTrue(restored["released"], restored.get("waiting"))
        self.assertEqual(self.old_config, json.loads(self.config.read_bytes()))
        self.assertEqual(self.a, self.gate.snapshot()["deployment_digest"])
        repeated = coordinator.rollback(result["id"])
        self.assertEqual(restored["id"], repeated["id"])

    def test_compensation_restores_original_attributes_and_selection(self):
        plan = build_plan(self.manifest)
        store = self.store()
        env = ConcreteEnvironment(plan, store, self.gate)
        with store.locked():
            op = new_operation(plan)
            step, record = plan["steps"][0], op["steps"][0]
            record["prepared"] = env.prepare(step, op, record)
            self.gate.close(op["id"])
            op["startup"]["current"] = env.block_startup(op)
            env.execute(step, record["prepared"], op, "attempt", lambda _: None)
            record["effective"] = True
            op["direction"] = "ROLLBACK"
            compensation = env.prepare_compensation(op)
            self.assertEqual(1, len(compensation))
            item = compensation[0]
            observed = env.execute(item["step"], item["prepared"], op, "restore", lambda _: None)
            self.assertEqual("target", observed["state"])
            self.assertTrue(env.check_local(op, rollback=True)["passed"])
        self.assertEqual(self.old_config, json.loads(self.config.read_bytes()))

    def test_compensation_refuses_independent_same_content_replacement(self):
        plan = build_plan(self.manifest)
        store = self.store()
        env = ConcreteEnvironment(plan, store, self.gate)
        with store.locked():
            op = new_operation(plan)
            step, record = plan["steps"][0], op["steps"][0]
            record["prepared"] = env.prepare(step, op, record)
            env.execute(step, record["prepared"], op, "attempt", lambda _: None)
            record["effective"] = True
            replacement = self.root / "independent"
            self.write(replacement, self.new_config)
            replacement.replace(self.config)
            with self.assertRaisesRegex(DeployError, "compensated"):
                env.prepare_compensation(op)

    def test_inherited_partial_compensation_uses_restored_object_identity(self):
        plan = build_plan(self.manifest)
        store = self.store()
        env = ConcreteEnvironment(plan, store, self.gate)
        with store.locked():
            original = store.create(plan)
            step, record = plan["steps"][0], original["steps"][0]
            record["prepared"] = env.prepare(step, original, record)
            env.execute(step, record["prepared"], original, "publish", lambda _: None)
            record["effective"] = True
            original["direction"] = "ROLLBACK"
            item = env.prepare_compensation(original)[0]
            env.execute(item["step"], item["prepared"], original, "restore", lambda _: None)
            restored_inode = self.config.stat().st_ino
            original["compensation"] = [{"step": item["step"], "record": {
                "restore": item["prepared"], "restore_attempts": [], "state": "RESTORED", "effective": True}}]
            store.save(original, "RESTORE_STEP_COMPLETED", recovery=True)
            successor_plan = seal_plan({**plan, "request_id": "successor"})
            successor = store.create(successor_plan, predecessor=original["id"])
            successor["inherited"] = [original["id"]]
            successor["direction"] = "ROLLBACK"
            compensation = env.for_operation(successor).prepare_compensation(successor)
            self.assertEqual("noop", compensation[0]["prepared"]["action"])
            self.assertEqual(record["prepared"]["preparation_budget_bytes"],
                             compensation[0]["prepared"]["preparation_budget_bytes"])
            env.execute(compensation[0]["step"], compensation[0]["prepared"], successor, "restore-again", lambda _: None)
            self.assertEqual(restored_inode, self.config.stat().st_ino)
            self.assertEqual(self.old_config, json.loads(self.config.read_bytes()))

    def test_mcp_session_mode_cannot_claim_final_admission_guard(self):
        config = {"schema": "local-hand-mcp-startup/v1", "mode": "session", "port": 3000,
                  "inputs": {"config": str(self.config), "auth_config": str(self.config), "session": str(self.config)}}
        self.write(self.config, config)
        selection = copy.deepcopy(self.source["selection"])
        selection["members"][0]["sha256"] = hashlib.sha256(self.config.read_bytes()).hexdigest()
        with self.assertRaisesRegex(DeployError, "MCP startup configuration"):
            PlanningEnvironment(self.profile)._verify_components(selection)

    def test_manager_starts_before_network_listener_in_forward_and_compensation(self):
        # Deliberately list the dependent first. A failed first MCP start must
        # not prevent every resume from ever reaching its management listener.
        self.profile["probes"]["mcp"] = {"kind": "mcp", "socket": str(self.root / "mcp.sock")}
        self.profile["guarded_components"]["mcp"] = {"configuration": str(self.config), "entrypoints": ["listener"]}
        self.profile["systemd"] = {"reload_scope": {"roots": []}, "units": {"mcp.service": {"component": "mcp"},
                                             "manager.service": {"component": "manager"}}}
        for deployment in (self.source, self.target):
            deployment["selection"]["components"]["mcp"] = copy.deepcopy(deployment["selection"]["components"]["manager"])
            deployment["services"] = {"mcp.service": {}, "manager.service": {}}
        starts = [{"kind": "service_start", "target": unit, "phase": "after_reload"}
                  for unit in ("mcp.service", "manager.service")]
        observer = SimpleNamespace(validate_baseline=lambda *_: None, plan_services=lambda *_: copy.deepcopy(starts))
        plan = build_plan(self.manifest, environment=observer)
        self.assertEqual(["manager.service", "mcp.service"],
                         [item["action"]["target"] for item in plan["steps"] if item["kind"] == "service"])
        store = self.store()
        environment = ConcreteEnvironment(plan, store, self.gate)
        environment._services = SimpleNamespace(plan_restore=lambda *_args, **_kwargs: copy.deepcopy(starts))
        with store.locked():
            operation = store.create(plan)
            for step, record in zip(plan["steps"], operation["steps"]):
                if step["kind"] == "service":
                    record["prepared"] = copy.deepcopy(step["action"])
                    record["effective"] = True
            restored = environment.prepare_compensation(operation)
        self.assertEqual(["manager.service", "mcp.service"], [item["step"]["action"]["target"] for item in restored])

    def unit_plan(self):
        units = self.root / "units"
        units.mkdir(mode=0o700)
        unit, candidate = units / "fixture.service", self.root / "candidate.service"
        unit.write_bytes(b"original definition\n"); unit.chmod(0o600)
        candidate.write_bytes(b"candidate definition\n"); candidate.chmod(0o600)
        before = tree_snapshot([str(units)])
        file_action = files.plan_files([{"source": str(candidate), "target": str(unit)}], owner_uid=self.owner)["files"][0]
        after = copy.deepcopy(before)
        after[str(unit)] = {"kind": "file", "digest": file_action["source"]["snapshot"]["sha256"], **file_action["attributes"]}
        plan = build_plan(self.manifest)
        plan["profile"]["systemd"] = {"units": {"fixture.service": {}}, "reload_scope": {
            "roots": [str(units)], "loaded_snapshot": before, "unit_search_roots": [str(units)],
            "generator_program_roots": [], "generator_inputs": [], "generator_output_roots": []}}
        plan["steps"] = [{"id": "unit-file", "kind": "file", "action": file_action},
            {"id": "manager-reload", "kind": "service", "action": {"kind": "service_daemon_reload",
            "target": "manager", "before": before, "after": after, "phase": "after_files", "subeffects": ["manager_reload"]}}]
        return seal_plan(plan), unit

    def test_committed_rollback_reverses_exact_gateway_profiles(self):
        plan = build_plan(self.manifest)
        old = {"services": {"gateway": {"image": "retained-original"}}}
        new = {"services": {"gateway": {"image": "committed-target"}}}
        plan["profile"]["gateway"] = {"compose": new, "original_compose": old}
        environment = ConcreteEnvironment(plan, self.store(), self.gate)
        operation = {"plan": plan, "steps": [], "inherited": []}
        with patch("admin.local_hand_deploy.planner.build_plan", side_effect=lambda manifest, observer: (manifest, observer)):
            manifest, observer = environment.restored_plan(operation, "restore-original")
        self.assertEqual(old, manifest["profile"]["gateway"]["compose"])
        self.assertEqual(new, manifest["profile"]["gateway"]["original_compose"])
        self.assertIs(manifest["profile"], observer.profile)
        self.assertEqual(new, environment.profile["gateway"]["compose"])

    def test_reload_retains_exact_failed_preparation_objects(self):
        plan, unit = self.unit_plan()
        store = self.store()
        env = ConcreteEnvironment(plan, store, self.gate)
        with store.locked():
            op = store.create(plan)
            step, record = plan["steps"][0], op["steps"][0]
            abandoned = env.prepare(step, op, record)
            record["prepared"] = env.prepare(step, op, record)
            reload = env.prepare(plan["steps"][1], op, op["steps"][1])
            self.assertEqual([abandoned["staged"]["path"]], [item["path"] for item in reload["retained_files"]])
            env.execute(step, record["prepared"], op, "publish", lambda _: None)
            env._verify_retention(reload)
            self.assertEqual(reload["after"], env.services.check_reload_scope(reload["after"]))
            replacement = self.root / "independent-stage"
            replacement.write_bytes(Path(abandoned["staged"]["path"]).read_bytes()); replacement.chmod(0o600)
            replacement.replace(abandoned["staged"]["path"])
            with self.assertRaises(files.FileError):
                env._verify_retention(reload)

    def test_restoration_reloads_original_even_when_forward_reload_was_not_dispatched(self):
        plan, unit = self.unit_plan()
        store = self.store()
        env = ConcreteEnvironment(plan, store, self.gate)
        with store.locked():
            op = store.create(plan)
            step, record = plan["steps"][0], op["steps"][0]
            record["prepared"] = env.prepare(step, op, record)
            op["steps"][1]["prepared"] = env.prepare(plan["steps"][1], op, op["steps"][1])
            env.execute(step, record["prepared"], op, "publish", lambda _: None)
            record["effective"] = True
            # A boot may have loaded the new bytes without our explicit Reload.
            # Empty service observations isolate the real file/reload-tree seam.
            env.services.observe = lambda: {"units": {}, "jobs": []}
            op["direction"] = "ROLLBACK"
            compensation = env.prepare_compensation(op)
            self.assertEqual(["file", "service"], [item["step"]["kind"] for item in compensation])
            self.assertFalse(op["steps"][1]["effective"])
            restored, reload = compensation
            env.execute(restored["step"], restored["prepared"], op, "restore", lambda _: None)
            self.assertEqual(b"original definition\n", unit.read_bytes())
            self.assertEqual(reload["prepared"]["after"], env.services.check_reload_scope(reload["prepared"]["after"]))


if __name__ == "__main__":
    unittest.main()
