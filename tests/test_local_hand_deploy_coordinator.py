"""Control-protocol tests with real durable store/flock and admission marker.

Platform effect values below are a deterministic model, not systemd acceptance;
real filesystem and subprocess boundaries have their own adapter tests.
"""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.model import DeployError, Limits, PLAN_SCHEMA, digest, seal_plan
from admin.local_hand_deploy.report import report
from admin.local_hand_deploy.store import Store
from local_hand_jobs.maintenance import MaintenanceGate


def plan(request="one", *, before="old", after="new", steps=True):
    return seal_plan({"schema": PLAN_SCHEMA, "request_id": request, "node_id": "test-node",
        "source": {"deployment_digest": digest(before)}, "target": {"deployment_digest": digest(after)},
        "steps": [{"id": "configuration", "kind": "file", "action": {"key": "config", "before": before, "after": after}}] if steps else [],
        "profile": {}})


class Effects:
    def __init__(self):
        self.actual = {"config": "old"}
        self.changes = []
        self.closed = True
        self.drain_ready = True
        self.fail_after_effect = False
        self.check_ok = True
        self.selection = None

    def for_operation(self, op):
        return self

    def preflight(self, op):
        return {"observed": True}

    def prepare(self, step, op, record):
        return dict(step["action"])

    def effect_key(self, step):
        return step["action"]["key"]

    def observe(self, step, prepared, attempt=None):
        actual = self.actual[prepared["key"]]
        state = "target" if actual == prepared["after"] else "original" if actual == prepared["before"] else "conflict"
        return {"state": state if self.closed else "running", "closed": self.closed,
                "effective": state == "target" and prepared["before"] != prepared["after"]}

    def execute(self, step, prepared, op, attempt_id, persist_intent, previous=None):
        if attempt_id:
            persist_intent({"attempt_id": attempt_id})
        if self.actual[prepared["key"]] != prepared["after"]:
            self.actual[prepared["key"]] = prepared["after"]
            self.changes.append((prepared["key"], prepared["after"]))
        if self.fail_after_effect:
            self.fail_after_effect = False
            raise OSError("injected response loss")
        return {**self.observe(step, prepared), "synced": True}

    def drain(self, op):
        return {"quiescent": self.drain_ready}

    def block_startup(self, op):
        return {"blocked": True}

    def candidate_startup(self, op, step, attempt_id):
        return {}

    def check_local(self, op, rollback=False):
        return {"passed": self.check_ok}

    def release_valid(self, op):
        return {"passed": self.check_ok}

    def publish_stable(self, op):
        self.selection = self.selected_deployment(op)
        return self.selection

    def selected_deployment(self, op):
        return op["plan"]["target" if op["decision"] == "COMMITTED" else "source"]

    def prepare_compensation(self, op):
        result = []
        for step, record in reversed(list(zip(op["plan"]["steps"], op["steps"]))):
            if not record["effective"]:
                continue
            action = dict(record["prepared"])
            action["before"], action["after"] = action["after"], action["before"]
            result.append({"step": {"id": "restore-" + step["id"], "kind": step["kind"], "action": action}, "prepared": action})
        return result

    def restored_plan(self, op, request_id):
        return plan(request_id, before=op["plan"]["steps"][0]["action"]["after"],
                    after=op["plan"]["steps"][0]["action"]["before"])


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.store = Store(root / "records", "test-node")
        self.store.initialize()
        gate_root = root / "admission"; gate_root.mkdir(mode=0o700)
        self.gate = MaintenanceGate(gate_root, "test-node", owner_uid=os.geteuid())
        self.gate.initialize(digest("old"), "bootstrap", bootstrap=True)
        self.effects = Effects()
        self.coordinator = Coordinator(self.store, self.gate, self.effects)

    def test_completed_request_never_replays_or_recloses(self):
        original = self.coordinator.apply(plan())
        self.assertEqual("COMMITTED", original["decision"])
        self.assertTrue(original["released"])
        sequence = self.gate.snapshot()["sequence"]
        self.effects.actual["config"] = "independent-later-change"
        again = self.coordinator.apply(plan())
        self.assertEqual(original, again)
        self.assertEqual(sequence, self.gate.snapshot()["sequence"])
        self.assertEqual([("config", "new")], self.effects.changes)

    def test_same_request_different_digest_conflicts(self):
        self.coordinator.apply(plan())
        with self.assertRaisesRegex(DeployError, "different plan"):
            self.coordinator.apply(plan(after="different"))

    def test_foreign_node_handoff_is_rejected_before_observation_or_transfer(self):
        self.effects.check_ok = False
        original = self.coordinator.apply(plan())
        self.assertTrue(original['gate_owned'])
        before = self.store.path.read_bytes()
        gate = self.gate.snapshot()
        changes = list(self.effects.changes)
        foreign = seal_plan({**plan('foreign'), 'node_id': 'another-node'})
        with mock.patch.object(self.effects, 'for_operation', wraps=self.effects.for_operation) as observed:
            with self.assertRaises(DeployError) as failure:
                self.coordinator.supersede(original['id'], foreign)
            self.assertEqual('NODE_CONFLICT', failure.exception.code)
            observed.assert_not_called()
        self.assertEqual(before, self.store.path.read_bytes())
        self.assertEqual(gate, self.gate.snapshot())
        self.assertEqual(changes, self.effects.changes)
        self.assertEqual([original], self.store.list())

    def test_effect_done_response_lost_recovers_without_repeating(self):
        self.effects.fail_after_effect = True
        failed = self.coordinator.apply(plan())
        self.assertIsNone(failed["decision"])
        self.assertEqual("new", self.effects.actual["config"])
        # A new coordinator and reopened SQLite reuse the exact same intent.
        recovered = Coordinator(Store(self.store.root, "test-node"), self.gate, self.effects).resume(failed["id"])
        self.assertEqual("COMMITTED", recovered["decision"])
        self.assertEqual([("config", "new")], self.effects.changes)
        self.assertEqual(1, len(recovered["errors"]["primary"]))

    def test_no_effect_rollback_does_not_wait_for_long_task(self):
        self.effects.drain_ready = False
        paused = self.coordinator.apply(plan())
        self.assertEqual("DRAIN", paused["waiting"]["reason"])
        result = self.coordinator.rollback(paused["id"])
        self.assertEqual("ABORTED_NO_CHANGE", result["decision"])
        self.assertTrue(result["released"])
        self.assertEqual([], self.effects.changes)
        self.assertEqual("OPEN", self.gate.snapshot()["state"])

    def test_partial_effect_rollback_uses_same_saved_compensation(self):
        self.effects.fail_after_effect = True
        failed = self.coordinator.apply(plan())
        self.effects.fail_after_effect = True
        interrupted = self.coordinator.rollback(failed["id"])
        self.assertEqual("old", self.effects.actual["config"])
        saved = interrupted["compensation"]
        final = self.coordinator.resume(failed["id"])
        self.assertEqual("ROLLED_BACK", final["decision"])
        self.assertTrue(final["released"])
        self.assertEqual(saved[0]["step"], final["compensation"][0]["step"])
        self.assertEqual([("config", "new"), ("config", "old")], self.effects.changes)

    def test_resume_compensation_does_not_recheck_forward_reload_tree(self):
        class ReloadEffects(Effects):
            def __init__(self):
                super().__init__()
                self.actual["manager"] = "old"
                self.restore_plans = 0
                self.interrupt_restore = True

            def observe(self, step, prepared, attempt=None):
                if prepared["key"] == "manager" and self.actual["config"] != prepared["after"]:
                    raise RuntimeError("reload requires its own selected tree")
                return super().observe(step, prepared, attempt)

            def prepare_compensation(self, op):
                self.restore_plans += 1
                # Actual platform ordering: original files precede original reload.
                actions = []
                for step in op["plan"]["steps"]:
                    action = {**step["action"], "before": "new", "after": "old"}
                    actions.append({"step": {**step, "id": "restore-" + step["id"], "action": action}, "prepared": action})
                return actions

            def execute(self, step, prepared, op, attempt_id, persist_intent, previous=None):
                result = super().execute(step, prepared, op, attempt_id, persist_intent, previous)
                if op["direction"] == "ROLLBACK" and prepared["key"] == "config" and self.interrupt_restore:
                    self.interrupt_restore = False
                    raise OSError("interrupted after restoring file before manager reload")
                return result

        effects = ReloadEffects()
        effects.check_ok = False
        coordinator = Coordinator(self.store, self.gate, effects)
        requested = plan()
        requested["steps"].append({"id": "reload", "kind": "service", "action": {
            "key": "manager", "before": "old", "after": "new"}})
        requested = seal_plan(requested)
        original = coordinator.apply(requested)
        self.assertIsNone(original["decision"])
        self.assertEqual({"config": "new", "manager": "new"}, effects.actual)
        effects.check_ok = True
        stopped = coordinator.rollback(original["id"])
        self.assertIsNone(stopped["decision"])
        self.assertEqual({"config": "old", "manager": "new"}, effects.actual)
        result = Coordinator(Store(self.store.root, "test-node"), self.gate, effects).resume(original["id"])
        self.assertEqual("ROLLED_BACK", result["decision"])
        self.assertTrue(result["released"])
        self.assertEqual(1, effects.restore_plans)
        self.assertEqual({"config": "old", "manager": "old"}, effects.actual)
        self.assertEqual(1, effects.changes.count(("config", "old")))

    def test_handoff_waits_for_compensation_caller_not_forward_caller(self):
        self.effects.fail_after_effect = True
        original = self.coordinator.apply(plan())
        self.effects.fail_after_effect = True
        recovering = self.coordinator.rollback(original["id"])
        observe = self.effects.observe
        def pending_restore(step, prepared, attempt=None):
            value = observe(step, prepared, attempt)
            if prepared["after"] == "old":
                return {**value, "state": "running", "closed": False}
            return value
        with mock.patch.object(self.effects, "observe", side_effect=pending_restore):
            blocked = self.coordinator.supersede(recovering["id"], plan("repair", before="old", after="fixed"))
        self.assertEqual("CALLER_NOT_CLOSED", blocked["waiting"]["reason"])
        self.assertIsNone(blocked["successor"])
        self.assertEqual(1, len(self.store.list()))
        self.assertEqual(recovering["id"], self.gate.snapshot()["owner"])

    def test_handoff_limit_is_checked_before_link_is_persisted(self):
        self.effects.fail_after_effect = True
        original = self.coordinator.apply(plan())
        with self.store.locked():
            saved = self.store.get(original["id"])
            saved["inherited"] = ["previous-" + str(number) for number in range(16)]
            self.store.save(saved, "TEST_INHERITANCE_BOUND", recovery=True)
        with self.assertRaisesRegex(DeployError, "fixed limit"):
            self.coordinator.supersede(original["id"], plan("too-long", before="new", after="fixed"))
        self.assertIsNone(self.store.get(original["id"])["successor"])
        self.assertEqual(1, len(self.store.list()))
        self.assertEqual(original["id"], self.gate.snapshot()["owner"])

    def test_late_rollback_returns_same_successor_after_new_deployment(self):
        first = self.coordinator.apply(plan())
        rollback = self.coordinator.rollback(first["id"])
        self.assertEqual("COMMITTED", rollback["decision"])
        second = self.coordinator.apply(plan("second", before="old", after="third"))
        sequence = self.gate.snapshot()["sequence"]
        late = self.coordinator.rollback(first["id"])
        self.assertEqual(rollback["id"], late["id"])
        self.assertEqual("third", self.effects.actual["config"])
        self.assertEqual(sequence, self.gate.snapshot()["sequence"])
        self.assertEqual("COMMITTED", second["decision"])

    def test_release_loss_keeps_decision_and_only_completes_release(self):
        release = self.gate.release
        def lost(*args, **kwargs):
            release(*args, **kwargs)
            raise OSError("lost response")
        with mock.patch.object(self.gate, "release", side_effect=lost):
            interrupted = self.coordinator.apply(plan())
        self.assertEqual("COMMITTED", interrupted["decision"])
        self.assertFalse(interrupted["released"])
        sequence = self.gate.snapshot()["sequence"]
        final = self.coordinator.resume(interrupted["id"])
        self.assertTrue(final["released"])
        self.assertEqual(sequence, self.gate.snapshot()["sequence"])
        self.assertEqual(1, len(self.effects.changes))

    def test_decision_with_invalid_conditions_cannot_release(self):
        publish = self.effects.publish_stable
        def failure(op):
            self.effects.check_ok = False
            raise OSError("injected startup selection failure")
        with mock.patch.object(self.effects, "publish_stable", side_effect=failure):
            result = self.coordinator.apply(plan())
        result = self.coordinator.resume(result["id"])
        self.assertEqual("COMMITTED", result["decision"])
        self.assertEqual("DECISION_REQUIRES_LINKED_REPAIR", result["waiting"]["reason"])
        self.assertEqual("CLOSED", self.gate.snapshot()["state"])

    def test_handoff_fences_old_apply_resume_and_rollback(self):
        self.effects.drain_ready = False
        first = self.coordinator.apply(plan())
        target = plan("successor", before="old", after="fixed")
        handed = self.coordinator.supersede(first["id"], target)
        self.assertTrue(handed["handoff_complete"])
        self.assertIsNone(handed["waiting"])
        self.assertEqual("SUPERSEDED", report(handed)["deployment"]["disposition"])
        self.assertIsNone(handed["decision"])
        self.effects.drain_ready = True
        final = self.coordinator.apply(target)
        self.assertTrue(final["released"])
        sequence = self.gate.snapshot()["sequence"]
        for function in (self.coordinator.resume, self.coordinator.rollback):
            self.assertEqual(handed["id"], function(handed["id"])["id"])
        self.coordinator.apply(plan())
        self.assertEqual(sequence, self.gate.snapshot()["sequence"])
        self.assertEqual("fixed", self.effects.actual["config"])

    def test_unknown_running_attempt_never_dispatches_again(self):
        self.effects.fail_after_effect = True
        op = self.coordinator.apply(plan())
        self.effects.closed = False
        waiting = self.coordinator.resume(op["id"])
        self.assertEqual("CALLER_NOT_CLOSED", waiting["waiting"]["reason"])
        self.assertEqual(1, len(self.effects.changes))
        self.effects.closed = True
        self.assertTrue(self.coordinator.resume(op["id"])["released"])

    def test_local_startup_failure_does_not_consume_dispatch_budget(self):
        with mock.patch.object(self.effects, "candidate_startup", side_effect=RuntimeError("local guard invalid")):
            result = self.coordinator.apply(plan())
            for _ in range(self.store.limits.max_attempts + 1):
                result = self.coordinator.resume(result["id"])
        self.assertEqual([], self.effects.changes)
        self.assertTrue(all(attempt["binding"] is None for attempt in result["steps"][0]["attempts"]))
        fixed = self.coordinator.resume(result["id"])
        self.assertEqual("COMMITTED", fixed["decision"])
        self.assertEqual([("config", "new")], self.effects.changes)

    def test_closed_pre_dispatch_attempt_does_not_consume_dispatch_budget(self):
        def not_spawned(step, prepared, op, attempt_id, persist_intent, previous=None):
            persist_intent({"attempt_id": attempt_id})
            return {**self.effects.observe(step, prepared), "dispatched": False}
        with mock.patch.object(self.effects, "execute", side_effect=not_spawned):
            result = self.coordinator.apply(plan())
            for _ in range(self.store.limits.max_attempts + 1):
                result = self.coordinator.resume(result["id"])
        self.assertEqual([], self.effects.changes)
        self.assertTrue(all(attempt["dispatched"] is False for attempt in result["steps"][0]["attempts"]))
        self.assertEqual("COMMITTED", self.coordinator.resume(result["id"])["decision"])

    def test_implementation_identity_changes_without_rewriting_completed_history(self):
        first = {"source_commit": "1" * 40, "source_tree": "2" * 40, "adapter_digest": "3" * 64}
        second = {"source_commit": "4" * 40, "source_tree": "5" * 40, "adapter_digest": "6" * 64}
        self.effects.drain_ready = False
        result = Coordinator(self.store, self.gate, self.effects, implementation=first).apply(plan())
        self.assertEqual(first, result["implementation"])
        self.effects.drain_ready = True
        fixed = Coordinator(self.store, self.gate, self.effects, implementation=second).resume(result["id"])
        self.assertEqual(second, fixed["implementation"])
        again = Coordinator(self.store, self.gate, self.effects, implementation=first).resume(result["id"])
        self.assertEqual(fixed, again)
        with self.store.reading() as connection:
            events = connection.execute("SELECT document FROM events WHERE kind='IMPLEMENTATION_OBSERVED' ORDER BY sequence").fetchall()
        self.assertEqual(2, len(events))

    def test_no_change_plan_does_not_change_admission(self):
        before = self.gate.snapshot()
        op = self.coordinator.apply(plan(after="old", steps=False))
        self.assertEqual("COMMITTED", op["decision"])
        self.assertEqual(before, self.gate.snapshot())

    def test_linked_repair_after_release_does_not_reclaim_old_gate_or_effects(self):
        first = self.coordinator.apply(plan())
        state = self.gate.snapshot()
        repaired_plan = plan("security-repair", before="new", after="fixed")
        linked = self.coordinator.supersede(first["id"], repaired_plan)
        self.assertTrue(linked["released"])
        self.assertTrue(linked["handoff_complete"])
        self.assertEqual(state, self.gate.snapshot())
        successor = self.store.get(linked["successor"])
        self.assertFalse(successor.get("inherited"))
        result = self.coordinator.resume(successor["id"])
        self.assertTrue(result["released"])
        self.assertEqual("fixed", self.effects.actual["config"])
        state = self.gate.snapshot()
        self.coordinator.resume(first["id"])
        self.coordinator.rollback(first["id"])
        self.assertEqual(state, self.gate.snapshot())

    def test_report_reconstruction_does_not_infer_public_client_acceptance(self):
        op = self.coordinator.apply(plan())
        output = report(self.store.get(op["id"]))
        self.assertEqual("NOT_CHECKED", output["public_reachability"]["status"])
        self.assertEqual("NOT_CHECKED", output["client_acceptance"]["status"])
        self.assertEqual("UNKNOWN", output["admission"]["current"]["state"])

    def test_corrupt_database_not_replaced_by_initialization_or_status(self):
        self.store.path.write_bytes(b"broken")
        with self.assertRaises(DeployError):
            self.store.list()
        with self.assertRaises(DeployError):
            self.store.initialize()
        self.assertEqual(b"broken", self.store.path.read_bytes())

    def test_failed_intent_commit_never_executes_effect(self):
        save = self.store.save
        def full(op, kind, *args, **kwargs):
            if kind == "ACTION_INTENT":
                raise DeployError("STATE_LIMIT", "injected full disk")
            return save(op, kind, *args, **kwargs)
        with mock.patch.object(self.store, "save", side_effect=full):
            result = self.coordinator.apply(plan())
        self.assertEqual("old", self.effects.actual["config"])
        self.assertEqual([], self.effects.changes)
        self.assertFalse(result["released"])
        self.assertTrue(self.coordinator.resume(result["id"])["released"])


if __name__ == "__main__":
    unittest.main()
