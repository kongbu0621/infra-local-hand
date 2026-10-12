"""Synthetic aggregate budgets; no real cgroup or hard CPU accounting claim."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

import test_local_hand_jobs_broker as broker_fixtures
from test_local_hand_jobs_broker import (DeferredDeliverySupervisor, RegistryFixture,
                                        SupervisorFixture, SYNTHETIC_BUDGET)
from local_hand_jobs import budget
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError
from local_hand_jobs.state import StateStore, encoded


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.f = broker_fixtures.BrokerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.clock = {"boot_id": "11111111-1111-4111-8111-111111111111", "boottime_ns": 100 * budget.NANOSECONDS}
        self.clock_patch = mock.patch.object(budget, "current_clock", side_effect=lambda: dict(self.clock))
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)

    def row(self, namespace="job", identity=None):
        return self.f.db.get(namespace, identity or self.f.request["operation_id"])

    def start_business(self):
        self.f.submit(); self.f.broker.tick()
        self.f.runner.finish(self.f.runner.starts[-1][1]); self.f.broker.tick(); self.f.broker.tick()

    def await_seal(self, *, effects_checked=True):
        self.f.broker.evidence = SimpleNamespace(root=Path(self.f.temp.name) / "sealed")
        self.start_business()
        self.f.runner.finish(self.f.runner.starts[-1][1], effects_checked=effects_checked,
            collectors_stopped=True, writers_stopped=True,
            result={"business_started": True, "evidence_snapshot": {"root": str(Path(self.f.temp.name) / "raw"), "members": []}})
        self.f.broker.tick()

    def assert_error(self, code, callback):
        with self.assertRaises(JobError) as caught:
            callback()
        self.assertEqual(code, caught.exception.code)

    def frozen_recovery_fixture(self, namespace="job", **proof_changes):
        fixture = broker_fixtures.BrokerTests(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        runner = DeferredDeliverySupervisor()
        evidence = SimpleNamespace(root=Path(fixture.temp.name) / "sealed")
        fixture.runner = runner
        fixture.broker = Broker(fixture.db, fixture.policy, RegistryFixture(), runner, evidence)
        fixture.submit()
        if namespace == "job":
            identity = fixture.request["operation_id"]
            fixture.broker.tick()
            self.assertIsNotNone(runner.deliver(runner.starts[-1][1]))
            runner.finish(runner.starts[-1][1]); fixture.broker.tick()
        else:
            fixture.cancel(); identity = str(uuid.uuid4()); fixture.reconcile(identity)
        fixture.broker.tick()
        self.assertIsNotNone(runner.deliver(runner.starts[-1][1]))
        proof = {"collectors_stopped": True, "writers_stopped": True,
                 "result": {"business_started": namespace == "job", "evidence_snapshot": {
                     "root": str(Path(fixture.temp.name) / "raw"), "members": []}}}
        proof.update(proof_changes)
        runner.finish(runner.starts[-1][1], **proof); fixture.broker.tick()
        self.assertEqual(fixture.db.get(namespace, identity)["record"]["phase"], "AWAITING_SEAL")
        return fixture, identity

    def recover_fixture(self, fixture):
        replacement = DeferredDeliverySupervisor()
        restored = Broker(fixture.db, fixture.policy, RegistryFixture(), replacement, fixture.broker.evidence)
        restored.recover()
        return restored, replacement

    def test_recovered_checked_work_delivers_only_its_first_evidence_intent(self):
        for namespace in ("job", "reconcile"):
            for exit_code in (0, 1):
                with self.subTest(namespace=namespace, exit_code=exit_code):
                    fixture, identity = self.frozen_recovery_fixture(namespace, exit_code=exit_code)
                    original = copy.deepcopy(fixture.db.get(namespace, identity)["record"])
                    restored, replacement = self.recover_fixture(fixture)
                    restored.tick()
                    self.assertEqual([item[2]["phase"] for item in replacement.starts], ["evidence"])
                    execution_id = replacement.starts[-1][1]
                    self.assertIsNotNone(replacement.deliver(execution_id))
                    self.assertIsNone(replacement.deliver(execution_id), "delivery cannot be replayed")
                    current = fixture.db.get(namespace, identity)["record"]
                    self.assertTrue(current["recovered"], "the generic recovery barrier must not be cleared")
                    self.assertEqual(current["business_outcome"], original["business_outcome"])
                    for key in ("started_boottime_ns", "deadline_boottime_ns", "boot_id"):
                        self.assertEqual(current["execution_budget"][key], original["execution_budget"][key])
                    for phase, grant in original["execution_budget"]["grants"].items():
                        self.assertEqual(current["execution_budget"]["grants"][phase], grant)
                    frozen = current["frozen_snapshot"]
                    publication = {"operation_id": fixture.request["operation_id"], "seal_id": str(uuid.uuid4()),
                        "seal_sha256": "a" * 64, "complete": True, "event_seq": frozen["event_seq"],
                        "bindings": frozen["bindings"]}
                    if namespace == "reconcile": publication["reconcile_id"] = identity
                    replacement.finish(execution_id, collectors_stopped=True, writers_stopped=True,
                                       result={"seal_record": publication})
                    restored.tick()
                    sealed = fixture.db.get(namespace, identity)["record"]
                    self.assertEqual(sealed["evidence"], "SEALED")
                    self.assertEqual(sealed["outcome"], original["business_outcome"])

    def recovered_publication(self):
        from local_hand_jobs.evidence import EvidenceStore, FrozenSnapshot, QuiescenceProof
        self.await_seal(); self.f.broker.tick()
        row = self.row(); record = row["record"]
        handle = dict(record["handles"]["evidence"], manager={
            "bootstrap": {"boot_id": self.clock["boot_id"]}, "helper": None, "result_reader": None})
        with self.f.db.transaction() as tx:
            self.f.db.update(tx, "job", row["id"], "SUPERVISOR_IDENTITY_OBSERVED", {
                "handles": dict(record["handles"], evidence=handle)})
        frozen = record["frozen_snapshot"]
        Path(frozen["root"]).mkdir(mode=0o700)
        snapshot = FrozenSnapshot(**dict(frozen, root=Path(frozen["root"]),
            members=tuple(frozen["members"]), broker_events=tuple(frozen["broker_events"]),
            quiescence=QuiescenceProof(**frozen["quiescence"])))
        store = EvidenceStore(Path(self.f.temp.name) / "sealed", snapshot_provider=lambda _: snapshot,
            register_seal=self.f.broker.register_seal, is_registered=self.f.broker.is_registered,
            list_seals=self.f.broker.list_seals)
        seal = store.publish_only(snapshot)
        self.f.broker.evidence = store
        previous_boot = self.clock["boot_id"]
        self.clock["boot_id"] = "22222222-2222-4222-8222-222222222222"
        self.f.broker._active.clear()  # Recovery uses a new process after the old boot ended.
        execution_id = "evidence-recovery-" + str(uuid.uuid4())
        proof = dict(kind="EVIDENCE_RECOVERY", operation_id=row["id"], request_digest=row["digest"],
            snapshot_sha256=hashlib.sha256(encoded(frozen).encode()).hexdigest(),
            prior_boot_id=previous_boot, boot_id=self.clock["boot_id"], prior_units_absent=True,
            execution_id=execution_id, unit="lhj-" + hashlib.sha256(execution_id.encode()).hexdigest() + ".service",
            invocation_id="a" * 32, state="EXITED", exit_code=0, future_start_blocked=True,
            tree_exited=True, collectors_stopped=True, writers_stopped=True, effects_checked=True,
            stdout_eof=True, stderr_eof=True, publication_sha256=hashlib.sha256(encoded(seal).encode()).hexdigest())
        return row["id"], row["digest"], seal, proof

    def test_recovered_publication_finishes_same_task_and_duplicate_callback_reuses_it(self):
        args = self.recovered_publication()
        before = copy.deepcopy(self.row())
        starts = list(self.f.runner.starts)
        result = self.f.broker.complete_recovered_evidence(*args)
        self.assertEqual((result["lifecycle"], result["outcome"], result["evidence"]),
                         ("TERMINAL", "SUCCEEDED", "SEALED"))
        after = self.row()
        for key in ("handles", "execution_budget", "frozen_snapshot", "business_exit_proof", "business_outcome"):
            self.assertEqual(before["record"][key], after["record"][key])
        for key in ("request", "plan", "digest", "id", "parent"):
            self.assertEqual(before[key], after[key])
        manifest = self.f.broker.evidence.manifest(args[0])
        self.assertTrue(manifest["artifacts"])
        self.assertEqual(self.f.broker.complete_recovered_evidence(*args), result)
        self.assertEqual(self.row()["record"]["event_seq"], after["record"]["event_seq"])
        self.assertEqual(self.f.runner.starts, starts)
        self.assertTrue(result["execution_resources_released"])

    def retained_publication(self):
        args = self.recovered_publication()
        with self.f.db.transaction() as tx:
            self.f.broker.resources.acquire(tx, "bootstrap:retained", 1, ["retained-work", "retained-evidence"])
        # The old callback recorded successful recovery but retained its execution lease.
        with mock.patch("local_hand_jobs.evidence_recovery.release_completed_evidence", return_value=False), \
             mock.patch.object(self.f.broker, "_release"):
            self.f.broker.complete_recovered_evidence(*args)
        return args

    def test_retained_completed_recovery_releases_only_execution_on_restart(self):
        args = self.retained_publication()
        before = copy.deepcopy(self.row())
        events = self.f.db.events("job", args[0])
        self.clock["boottime_ns"] += 10000 * budget.NANOSECONDS
        self.f.broker.recover()
        after = self.row()
        self.assertTrue(after["record"]["execution_resources_released"])
        for key in ("handles", "execution_budget", "exit_proof", "seals", "frozen_snapshot"):
            self.assertEqual(before["record"][key], after["record"][key])
        later = self.f.db.events("job", args[0])
        self.assertEqual(events, later[:-1])
        self.assertEqual("EXECUTION_RESOURCES_RELEASED", later[-1]["kind"])
        with self.f.db.transaction() as tx:
            self.assertEqual(["bootstrap:retained"] * 2,
                             [r[0] for r in tx.execute("SELECT owner FROM leases")])
            self.f.broker.resources.acquire(tx, "next-job", 1, after["plan"]["resource_ids"])
        self.f.broker.recover()
        self.f.broker.complete_recovered_evidence(*args)
        self.assertEqual(after, self.row())

    def test_retained_recovery_cannot_release_with_changed_proof(self):
        from local_hand_jobs.evidence_recovery import release_completed_evidence
        args = self.retained_publication()
        with self.f.db.transaction() as tx:
            row = self.f.db.get("job", args[0], tx)
            row["record"]["exit_proof"]["prior_units_absent"] = False
            leases = list(tx.execute("SELECT * FROM leases"))
            self.assert_error("IO_UNCERTAIN", lambda: release_completed_evidence(self.f.broker, tx, row))
            self.assertEqual(leases, list(tx.execute("SELECT * FROM leases")))

    def test_recovered_publication_rejects_live_or_unbound_proof_without_ledger_changes(self):
        args = self.recovered_publication()
        for key, value in (("prior_units_absent", False), ("boot_id", args[3]["prior_boot_id"]),
                           ("snapshot_sha256", "0" * 64), ("stdout_eof", False), ("exit_code", 1)):
            with self.subTest(key=key):
                before = copy.deepcopy(self.row())
                proof = dict(args[3], **{key: value})
                self.assert_error("IO_UNCERTAIN", lambda: self.f.broker.complete_recovered_evidence(*args[:3], proof))
                self.assertEqual(self.row(), before)

    def test_recovered_publication_keeps_unknown_prior_helper_delivery_blocked(self):
        args = self.recovered_publication()
        row = self.row()
        with self.f.db.transaction() as tx:
            self.f.db.update(tx, "job", args[0], "MANAGER_DELIVERY_INTENT", {
                "delivery_intents": [*row["record"].get("delivery_intents", []), "job-" + args[0] + "-evidence:helper"]})
        self.assert_error("IO_UNCERTAIN", lambda: self.f.broker.complete_recovered_evidence(*args))

    def test_recovered_seal_refuses_missing_proofs_and_any_prior_evidence_intent(self):
        for fault in ("effects", "collectors", "writers", "snapshot", "frozen_event", "old_intent"):
            with self.subTest(fault=fault):
                changes = {"effects_checked": False} if fault == "effects" else {
                    "collectors_stopped": False} if fault == "collectors" else {
                    "writers_stopped": False} if fault == "writers" else {}
                fixture, identity = self.frozen_recovery_fixture(**changes)
                if fault in ("snapshot", "frozen_event"):
                    with fixture.db.transaction() as tx:
                        frozen = copy.deepcopy(fixture.db.get("job", identity, tx)["record"]["frozen_snapshot"])
                        if fault == "snapshot": frozen.pop("quiescence")
                        else: frozen["members"].append("not-in-original-frozen-event")
                        fixture.db.update(tx, "job", identity, "SYNTHETIC_DAMAGED_SNAPSHOT", {"frozen_snapshot": frozen})
                if fault == "old_intent": fixture.broker.tick()
                old_budget = copy.deepcopy(fixture.db.get("job", identity)["record"]["execution_budget"])
                restored, replacement = self.recover_fixture(fixture)
                restored.tick()
                self.assertFalse(replacement.starts)
                self.assertEqual(fixture.db.get("job", identity)["record"]["execution_budget"], old_budget)
                if fault == "old_intent":
                    self.assertIsNone(fixture.runner.deliver(fixture.runner.starts[-1][1]))

    def test_recovered_first_seal_rechecks_current_fences_at_intent_and_delivery(self):
        for moment in ("before_intent", "before_delivery"):
            for fault in ("cancel", "revoke", "generation", "lease", "expired", "different_boot", "recover_again"):
                with self.subTest(moment=moment, fault=fault):
                    self.clock = {"boot_id": "11111111-1111-4111-8111-111111111111", "boottime_ns": 100 * budget.NANOSECONDS}
                    fixture, identity = self.frozen_recovery_fixture()
                    restored, replacement = self.recover_fixture(fixture)
                    if moment == "before_delivery": restored.tick()
                    baseline = copy.deepcopy(fixture.db.get("job", identity)["record"]["execution_budget"])
                    if fault == "cancel":
                        restored.cancel(identity, fixture.request["request_digest"], {"kind": "job"}, fixture.owner)
                    elif fault == "revoke": restored.revoke(fixture.owner.principal_id)
                    elif fault == "generation": fixture.policy.generation += 1
                    elif fault == "lease":
                        with fixture.db.transaction() as tx: tx.execute("DELETE FROM leases")
                    elif fault == "expired": self.clock["boottime_ns"] += 31 * budget.NANOSECONDS
                    elif fault == "different_boot": self.clock["boot_id"] = "22222222-2222-4222-8222-222222222222"
                    else: restored.recover()
                    if moment == "before_intent":
                        restored.tick()
                        if fault == "recover_again":
                            # Another recovery before the first evidence intent
                            # still has no old evidence execution to replay.
                            self.assertEqual(len(replacement.starts), 1)
                            self.assertIsNotNone(replacement.deliver(replacement.starts[-1][1]))
                            continue
                        self.assertFalse(replacement.starts)
                    else:
                        try:
                            self.assertIsNone(replacement.deliver(replacement.starts[-1][1]))
                        except JobError as error:
                            self.assertIn(error.code, ("LIMIT_EXCEEDED", "IO_UNCERTAIN", "RESOURCE_BUSY"))
                        self.assertFalse(replacement.delivered)
                    self.assertEqual(fixture.db.get("job", identity)["record"]["execution_budget"], baseline)

    def test_three_phase_allocations_are_durable_and_do_not_change_the_plan(self):
        self.await_seal()
        original = copy.deepcopy(self.row()["plan"])
        self.f.broker.tick()
        plans = [entry[2] for entry in self.f.runner.starts]
        self.assertEqual(["preflight", "business", "evidence"], [p["phase"] for p in plans])
        for key in ("wall_seconds", "cpu_seconds", "log_bytes"):
            self.assertLessEqual(sum(p["budgets"][key] for p in plans), SYNTHETIC_BUDGET[key])
        self.assertEqual(original, self.row()["plan"])
        self.assertEqual(3, len(self.row()["record"]["execution_budget"]["grants"]))
        for plan in plans:
            budget.validate_grant(plan["budget_grant"], budgets=plan["budgets"], original_budgets=SYNTHETIC_BUDGET)
        status = self.f.status()
        for key in ("execution_budget", "budget_grant", "boot_id", "deadline_boottime_ns"):
            self.assertNotIn(key, status)

    def test_reconciliation_and_its_seal_share_an_independent_two_phase_budget(self):
        self.f.broker.evidence = SimpleNamespace(root=Path(self.f.temp.name) / "sealed")
        self.f.submit(); self.f.cancel()
        identity = str(uuid.uuid4())
        self.f.reconcile(identity); self.f.broker.tick()
        self.f.runner.finish(self.f.runner.starts[-1][1], collectors_stopped=True, writers_stopped=True,
            result={"evidence_snapshot": {"root": str(Path(self.f.temp.name) / "raw"), "members": []}})
        self.f.broker.tick(); self.f.broker.tick()
        plans = [item[2] for item in self.f.runner.starts]
        self.assertEqual(["reconcile", "evidence"], [p["phase"] for p in plans])
        for key in ("wall_seconds", "cpu_seconds", "log_bytes"):
            self.assertLessEqual(sum(p["budgets"][key] for p in plans), SYNTHETIC_BUDGET[key])
        self.assertNotIn("execution_budget", self.row()["record"])
        self.assertEqual(identity, self.row("reconcile", identity)["record"]["execution_budget"]["record_id"])

    def test_phase_gap_deadline_exhaustion_blocks_business_without_refund(self):
        self.f.submit(); self.f.broker.tick()
        self.f.runner.finish(self.f.runner.starts[-1][1]); self.f.broker.tick()
        before = copy.deepcopy(self.row()["record"]["execution_budget"])
        self.clock["boottime_ns"] += 31 * budget.NANOSECONDS
        self.f.broker.tick(); self.f.broker.tick()
        self.assertEqual(1, len(self.f.runner.starts))
        self.assertEqual(before, self.row()["record"]["execution_budget"])
        self.assertEqual("FAILED", self.f.status()["outcome"])

    def test_final_delivery_fence_rejects_expired_or_changed_clock(self):
        for changed_boot in (False, True):
            with self.subTest(changed_boot=changed_boot):
                f = broker_fixtures.BrokerTests(); f.setUp()
                try:
                    runner = DeferredDeliverySupervisor()
                    f.broker = Broker(f.db, f.policy, RegistryFixture(), runner)
                    self.clock = {"boot_id": "11111111-1111-4111-8111-111111111111", "boottime_ns": 100 * budget.NANOSECONDS}
                    f.submit(); f.broker.tick()
                    original = copy.deepcopy(f.db.get("job", f.request["operation_id"])["record"]["execution_budget"])
                    if changed_boot:
                        self.clock["boot_id"] = "22222222-2222-4222-8222-222222222222"
                    else:
                        self.clock["boottime_ns"] += 31 * budget.NANOSECONDS
                    self.assert_error("IO_UNCERTAIN" if changed_boot else "LIMIT_EXCEEDED",
                                      lambda: runner.deliver(runner.starts[0][1]))
                    self.assertFalse(runner.delivered)
                    self.assertEqual(original, f.db.get("job", f.request["operation_id"])["record"]["execution_budget"])
                finally:
                    f.doCleanups()

    def test_restart_preserves_same_grants_and_does_not_reset_seal_deadline(self):
        self.await_seal()
        original = copy.deepcopy(self.row()["record"]["execution_budget"])
        reopened = StateStore(self.f.db.path, "authority", "ledger")
        self.addCleanup(reopened.close)
        replacement = SupervisorFixture()
        restored = Broker(reopened, self.f.policy, RegistryFixture(), replacement, self.f.broker.evidence)
        restored.recover()
        self.clock["boottime_ns"] += 31 * budget.NANOSECONDS
        restored.tick()
        self.assertFalse(replacement.starts)
        record = reopened.get("job", self.f.request["operation_id"])["record"]
        self.assertEqual(original, record["execution_budget"])
        self.assertEqual("SUCCEEDED", record["outcome"])
        self.assertNotEqual("SEALED", record["evidence"])

    def test_budget_exhaustion_does_not_release_unknown_business_effects(self):
        self.await_seal(effects_checked=False)
        self.clock["boottime_ns"] += 31 * budget.NANOSECONDS
        self.f.broker.tick()
        self.assertEqual("UNKNOWN", self.f.status()["outcome"])
        self.assert_error("RESOURCE_BUSY", lambda: self.f.broker.submit(self.f.make_request(), self.f.owner))

    def test_legacy_and_inconsistent_prior_state_never_acquire_a_fresh_budget(self):
        self.f.submit(); self.f.broker.tick()
        self.f.runner.finish(self.f.runner.starts[-1][1]); self.f.broker.tick()
        saved = self.row()
        for erase_handles in (False, True):
            row = copy.deepcopy(saved)
            row["record"].pop("execution_budget")
            if erase_handles:
                row["record"]["handles"] = {}
            self.assert_error("IO_UNCERTAIN", lambda: budget.reserve(row, "business"))
        # Even an inconsistent record which looks queued cannot erase the
        # immutable execution history and receive a newly started deadline.
        with self.f.db.transaction() as tx:
            record = copy.deepcopy(saved["record"])
            record.pop("execution_budget")
            record.update(phase="QUEUED", lifecycle="ACCEPTED", handles={}, business_started=False,
                          helper_started=False, exit_proof=None, facts={})
            tx.execute("UPDATE operations SET record_json=? WHERE namespace='job' AND id=?",
                       (json.dumps(record), self.f.request["operation_id"]))
        self.assert_error("IO_UNCERTAIN", lambda: self.f.broker._start("job", self.f.request["operation_id"], "preflight"))
        self.assertEqual(1, len(self.f.runner.starts))

    def test_malformed_internal_grants_and_reservation_bindings_are_rejected(self):
        self.f.submit(); self.f.broker.tick()
        row = self.row()
        grant = copy.deepcopy(row["record"]["execution_budget"]["grants"]["preflight"])
        changes = [{"version": True}, {"deadline_boottime_ns": 1.0}, {"reserved_boottime_ns": float("nan")},
                   {"extra": 1}, {"execution_id": "other"}, {"boot_id": True},
                   {"limits": dict(grant["limits"], log_bytes=True)}]
        for changed in changes:
            with self.subTest(changed=changed):
                self.assert_error("IO_UNCERTAIN", lambda: budget.validate_grant(dict(grant, **changed)))
        missing = dict(grant); missing.pop("boot_id")
        self.assert_error("IO_UNCERTAIN", lambda: budget.validate_grant(missing))
        for kind in ("clock", "identity", "aggregate"):
            damaged = copy.deepcopy(row)
            state = damaged["record"]["execution_budget"]
            if kind == "clock":
                state["grants"]["preflight"]["reserved_boottime_ns"] += 1
            elif kind == "identity":
                damaged["record"]["handles"]["preflight"]["execution_id"] = "other"
            else:
                state["grants"]["preflight"]["limits"]["cpu_seconds"] = SYNTHETIC_BUDGET["cpu_seconds"] + 1
            self.assert_error("IO_UNCERTAIN", lambda: budget.stored_grant(damaged, "preflight"))

    def test_tiny_envelopes_are_not_rounded_up(self):
        for field, value in (("log_bytes", 2), ("cpu_seconds", 2), ("wall_seconds", 3)):
            self.assert_error("LIMIT_EXCEEDED", lambda: budget.allocated_limits(dict(SYNTHETIC_BUDGET, **{field: value}), "job"))

    def test_failed_intent_commit_cannot_dispatch_or_recreate_its_budget(self):
        self.f.submit()
        update = self.f.db.update
        def fail(tx, namespace, identity, event, changes):
            if event == "EXECUTION_INTENT":
                raise sqlite3.OperationalError("synthetic intent commit failure")
            return update(tx, namespace, identity, event, changes)
        with mock.patch.object(self.f.db, "update", side_effect=fail):
            self.assert_error("IO_UNCERTAIN", lambda: self.f.broker._start("job", self.f.request["operation_id"], "preflight"))
        self.assertFalse(self.f.runner.starts)
        self.assertFalse(self.f.db.healthy)
        self.assert_error("IO_UNCERTAIN", lambda: self.f.broker._start("job", self.f.request["operation_id"], "preflight"))

    def test_unavailable_boot_clock_preserves_status_and_cancel_without_reopening_files(self):
        self.f.submit()
        self.clock_patch.stop()
        with mock.patch.multiple(budget, _boot_id=None, _clock_failed=False), \
                mock.patch("builtins.open", side_effect=PermissionError("synthetic boot identity denial")) as opened:
            restored = Broker(self.f.db, self.f.policy, RegistryFixture(), self.f.runner)
            self.f.broker = restored
            self.assertEqual("ACCEPTED", self.f.status()["lifecycle"])
            self.assert_error("IO_UNCERTAIN", lambda: restored._start("job", self.f.request["operation_id"], "preflight"))
            self.assert_error("IO_UNCERTAIN", budget.current_clock)
            self.assertEqual(1, opened.call_count)
            self.f.cancel()
            self.assertTrue(self.f.status()["cancel_requested"])
            self.assertFalse(self.f.runner.starts)


if __name__ == "__main__":
    unittest.main()
