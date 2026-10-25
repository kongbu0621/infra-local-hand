"""Corrective deployment through real guarded files, SQLite and handoff."""
import copy
import json
import unittest
from unittest.mock import patch

import test_local_hand_deploy_runtime as fixture
from admin.local_hand_deploy.binding import BINDING_SCHEMA, RELEASE_SCHEMA, repair_plan
from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.model import DeployError
from admin.local_hand_deploy.planner import build_plan
from admin.local_hand_deploy.runtime import ConcreteEnvironment
from admin.local_hand_deploy import recovery
from admin.local_hand_deploy.services import tree_snapshot


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.RuntimeTests(methodName="runTest")
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        f = self.f
        self.store = f.store()
        self.plan = build_plan(f.manifest)
        self.coordinator = Coordinator(self.store, f.gate, ConcreteEnvironment(self.plan, self.store, f.gate))
        self.binding = {"schema": BINDING_SCHEMA, "node_id": "node", "state": str(self.store.root), "profile": f.profile}
        self.fixed = f.configuration("d" * 64)
        self.fixed_path = f.root / "fixed.json"
        f.write(self.fixed_path, self.fixed)
        self.release = {"schema": RELEASE_SCHEMA, "node_id": "node", "request_id": "correction",
            "target": f.deployment("d" * 64, self.fixed), "files": [{"source": str(self.fixed_path), "target": str(f.config)}]}

    def partial(self):
        with patch.object(ConcreteEnvironment, "check_local", return_value={"passed": False}):
            op = self.coordinator.apply(self.plan)
        self.assertEqual("LOCAL_CHECK_FAILED", op["waiting"]["reason"])
        self.assertEqual(self.f.new_config, json.loads(self.f.config.read_bytes()))
        self.assertEqual("CLOSED", self.f.gate.snapshot()["state"])
        return op

    def test_partial_corrective_plan_is_read_only_then_commits_same_chain(self):
        old = self.partial()
        before = {p: (p.stat().st_ino, p.stat().st_mtime_ns) for p in self.f.root.rglob("*")}
        plan = repair_plan(self.binding, self.release, old["id"])
        self.assertEqual(before, {p: (p.stat().st_ino, p.stat().st_mtime_ns) for p in self.f.root.rglob("*")})
        self.assertEqual(self.f.source["selection"], plan["source"]["selection"])
        handed = self.coordinator.supersede(old["id"], plan)
        new = self.coordinator.resume(handed["successor"])
        self.assertTrue(new["released"], new.get("waiting"))
        self.assertEqual("COMMITTED", new["decision"])
        self.assertEqual(self.fixed, json.loads(self.f.config.read_bytes()))
        inode = self.f.config.stat().st_ino
        gate = self.f.gate.snapshot()
        for method in (self.coordinator.resume, self.coordinator.rollback):
            self.assertTrue(method(old["id"])["handoff_complete"])
        self.assertEqual(inode, self.f.config.stat().st_ino)
        self.assertEqual(gate, self.f.gate.snapshot())

    def test_failed_correction_restores_original_not_intermediate_configuration(self):
        old = self.partial()
        plan = repair_plan(self.binding, self.release, old["id"])
        new_id = self.coordinator.supersede(old["id"], plan)["successor"]
        with patch.object(ConcreteEnvironment, "check_local", return_value={"passed": False}):
            new = self.coordinator.resume(new_id)
        self.assertIsNone(new["decision"])
        self.assertEqual(self.fixed, json.loads(self.f.config.read_bytes()))
        restored = self.coordinator.rollback(new_id)
        self.assertTrue(restored["released"], restored.get("waiting"))
        self.assertEqual("ROLLED_BACK", restored["decision"])
        self.assertEqual(self.f.old_config, json.loads(self.f.config.read_bytes()))

    def test_committed_correction_rollback_uses_earliest_original(self):
        old = self.partial()
        plan = repair_plan(self.binding, self.release, old["id"])
        new_id = self.coordinator.supersede(old["id"], plan)["successor"]
        new = self.coordinator.resume(new_id)
        self.assertTrue(new["released"], new.get("waiting"))
        restored = self.coordinator.rollback(new_id)
        self.assertTrue(restored["released"], restored.get("waiting"))
        self.assertEqual(self.f.old_config, json.loads(self.f.config.read_bytes()))

    def test_committed_rollback_refuses_same_byte_independent_replacement(self):
        old = self.coordinator.apply(self.plan)
        external = self.f.root / "external"
        self.f.write(external, self.f.new_config)
        external.replace(self.f.config)
        inode = self.f.config.stat().st_ino
        with self.assertRaises(DeployError): self.coordinator.rollback(old["id"])
        self.assertEqual(inode, self.f.config.stat().st_ino)
        self.assertEqual("OPEN", self.f.gate.snapshot()["state"])

    def test_corrective_apply_without_handoff_does_not_create_an_orphan(self):
        old = self.partial()
        plan = repair_plan(self.binding, self.release, old["id"])
        before = self.store.path.read_bytes()
        with self.assertRaises(DeployError): self.coordinator.apply(plan)
        self.assertEqual(before, self.store.path.read_bytes())
        self.assertEqual(1, len(self.store.list()))

    def test_other_fixed_target_rejected_without_changing_original(self):
        old = self.partial()
        changed = copy.deepcopy(self.binding)
        changed["profile"]["probes"]["manager"]["socket"] += "-other"
        before = self.store.path.read_bytes()
        with self.assertRaises(DeployError): repair_plan(changed, self.release, old["id"])
        self.assertEqual(before, self.store.path.read_bytes())

    def test_preparation_failure_resumes_without_reclassifying_staging_as_drift(self):
        old = self.partial()
        plan = repair_plan(self.binding, self.release, old["id"])
        new_id = self.coordinator.supersede(old["id"], plan)["successor"]
        prepare = ConcreteEnvironment.prepare
        def fail_after_staging(env, *args):
            prepare(env, *args)
            raise OSError("lost preparation response")
        with patch.object(ConcreteEnvironment, "prepare", fail_after_staging):
            result = self.coordinator.resume(new_id)
        self.assertEqual("PREPARING", result["phase"])
        result = self.coordinator.resume(new_id)
        self.assertTrue(result["released"], result.get("waiting"))
        self.assertEqual(self.fixed, json.loads(self.f.config.read_bytes()))

    def test_recovery_reload_tree_accepts_owned_partial_files_not_unrelated_drift(self):
        plan, unit = self.f.unit_plan()
        env = ConcreteEnvironment(plan, self.store, self.f.gate)
        with self.store.locked():
            op = self.store.create(plan)
            for step, record in zip(plan["steps"], op["steps"]):
                record["prepared"] = env.prepare(step, op, record)
            step, record = plan["steps"][0], op["steps"][0]
            env.execute(step, record["prepared"], op, "publish", lambda _: None)
            record["effective"] = True
            self.store.save(op, "PUBLISHED")
            before = copy.deepcopy(plan["profile"]["systemd"]["reload_scope"]["loaded_snapshot"])
            actual = recovery.reload_tree(plan["profile"], [op])
            self.assertEqual(tree_snapshot([str(unit.parent)]), actual)
            self.assertNotEqual(before, actual)
            self.assertEqual(before, plan["profile"]["systemd"]["reload_scope"]["loaded_snapshot"])
            (unit.parent / "unrelated.service").write_text("independent")
            with self.assertRaises(DeployError): recovery.reload_tree(plan["profile"], [op])

    def test_plan_observation_drift_rejected_before_handoff(self):
        old = self.partial()
        plan = repair_plan(self.binding, self.release, old["id"])
        selection = json.loads(self.f.selection.read_bytes())
        selection["owner"] = "unrelated"
        self.f.write(self.f.selection, selection)
        before = self.store.path.read_bytes()
        with self.assertRaises(DeployError): self.coordinator.supersede(old["id"], plan)
        self.assertEqual(before, self.store.path.read_bytes())
        self.assertEqual(old["id"], self.f.gate.snapshot()["owner"])

    def test_known_independent_file_change_is_not_reclaimed_by_rollback(self):
        old = self.partial()
        external = self.f.root / "external"
        self.f.write(external, self.f.new_config)
        external.replace(self.f.config)
        independent_inode = self.f.config.stat().st_ino
        plan = repair_plan(self.binding, self.release, old["id"])
        new_id = self.coordinator.supersede(old["id"], plan)["successor"]
        # A successor that has not overwritten this separately owned object
        # cannot use the old deployment backup to reclaim it.
        result = self.coordinator.rollback(new_id)
        self.assertFalse(result["released"])
        self.assertEqual(independent_inode, self.f.config.stat().st_ino)
        self.assertEqual("CLOSED", self.f.gate.snapshot()["state"])


if __name__ == "__main__": unittest.main()
