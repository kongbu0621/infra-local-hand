"""Cancellation timing boundaries with a real ledger and modeled OS proofs."""
import copy
import hashlib
import sqlite3
import unittest

from types import SimpleNamespace
from unittest.mock import Mock, patch

from local_hand_jobs import runner
from local_hand_jobs.broker import Broker
from local_hand_jobs.state import LedgerBusy
from local_hand_jobs.contract import JobError
from test_local_hand_jobs_quota_binding import observed
import test_local_hand_jobs_quota_resident_chain as fixtures


class CancelBoundaryTests(unittest.TestCase):
    def pending_result(self, phase, *, failed=False, amend=None):
        f = fixtures.ResidentChainTests()
        f.setUp(); self.addCleanup(f.doCleanups)
        for earlier in ("preflight", "business")[:("preflight", "business", "evidence").index(phase)]:
            f.close(earlier)
        complete = fixtures.complete
        def verified(grant, **options):
            value = complete(grant, **options)
            execution = "job-" + f.identity + "-" + phase
            value[1].update(execution_id=execution, helper_result_verified=True,
                effects_checked=not failed, exit_code=1 if failed else 0,
                result=dict(execution_id=execution, phase=phase, outcome="FAILED" if failed else "SUCCEEDED",
                            effects_checked=not failed, business_started=phase == "business", helper_started=True,
                            facts={}, **({"error": "LedgerPlanError"} if failed else {})))
            # The real runner carries the reader's independent exit identity.
            reader = value[1]["quota_stage_exits"]["reader"]
            identity = reader["identity"]
            value[1]["result_reader_exit_proof"] = dict(execution_id=execution, unit=identity["unit"],
                identity={k:identity[k] for k in ("boot_id", "invocation_id", "cgroup")},
                state="EXITED", exit_code=0, **dict.fromkeys(("future_start_blocked", "tree_exited",
                    "writers_stopped", "collectors_stopped"), True))
            if amend is not None:
                amend(value[1])
            return value
        with patch.object(fixtures, "complete", side_effect=verified):
            fence, proof = f.pending(phase)
        return f, fence, proof

    def test_cancellation_after_verified_failure_releases_only_execution_resources(self):
        for phase, closed in [(p, c) for p in ("preflight", "business", "evidence") for c in (False, True)]:
            with self.subTest(phase=phase, closed=closed):
                f, fence, proof = self.pending_result(phase, failed=True)
                b = f.broker
                if closed:
                    b.close_observation("job", f.identity, phase, fence)
                before = copy.deepcopy(f.row())
                with b.state.transaction() as tx:
                    leases = [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")]
                b.cancel(f.identity, before["digest"], {"kind":"job"}, f.f.owner)
                b.tick(); b.tick()  # AWAITING_SEAL first records the blocked evidence start.
                record = f.row()["record"]
                self.assertEqual(("TERMINAL", "EXITED"), (record["lifecycle"], record["phase"]))
                self.assertEqual({"preflight":"CANCELLED", "business":"UNKNOWN", "evidence":"SUCCEEDED"}[phase], record["outcome"])
                self.assertEqual(proof, record["exit_proof"])
                self.assertEqual("FAILED", record["exit_proof"]["result"]["outcome"])
                self.assertEqual(before["record"].get("quota_closed", {}), record.get("quota_closed", {}))
                self.assertEqual(before["record"]["delivery_intents"], record["delivery_intents"])
                with b.state.transaction() as tx:
                    self.assertEqual([r for r in leases if r[1] != f.identity],
                        [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")])
                events = b.state.events("job", f.identity)
                b.tick(); b.cancel(f.identity, before["digest"], {"kind":"job"}, f.f.owner)
                self.assertEqual(events, b.state.events("job", f.identity))

    def test_cancelled_closure_retries_publication_after_real_ledger_contention(self):
        for phase in ("business", "evidence"):
            for resume in ("tick", "same_close", "recover", "new_broker"):
                with self.subTest(phase=phase, resume=resume):
                    f, fence, proof = self.pending_result(phase)
                    b = f.broker
                    b.cancel(f.identity, f.row()["digest"], {"kind":"job"}, f.f.owner)
                    writer = sqlite3.connect(b.state.path, isolation_level=None)
                    self.addCleanup(writer.close)
                    complete = b._complete
                    def locked(*args):
                        writer.execute("BEGIN IMMEDIATE")
                        try:return complete(*args)
                        finally:writer.execute("ROLLBACK")
                    with patch.object(b, "_complete", side_effect=locked), self.assertRaises(LedgerBusy):
                        b.close_observation("job", f.identity, phase, fence)
                    before = copy.deepcopy(f.row())
                    self.assertIn(phase, before["record"]["quota_closed"])
                    self.assertNotEqual("TERMINAL", before["record"]["lifecycle"])
                    starts = copy.deepcopy(f.runner.starts)
                    if resume == "same_close":
                        b.close_observation("job", f.identity, phase, fence)
                    elif resume == "new_broker":
                        other = Broker(b.state, b.policy, b.registry, f.runner, evidence=b.evidence, quota_required=True)
                        self.assertNotEqual(b._quota_session, other._quota_session)
                        with patch.object(f.runner, "reattach", create=True,
                                          side_effect=AssertionError("Closed execution reattached")) as reattach:
                            other.recover()
                            reattach.assert_not_called()
                    else:
                        getattr(b, resume)()
                    record = f.row()["record"]
                    self.assertEqual(("TERMINAL", "EXITED", "SUCCEEDED"),
                        (record["lifecycle"], record["phase"], record["outcome"]))
                    self.assertEqual("SEALED" if phase == "evidence" else "STAGING", record["evidence"])
                    self.assertEqual(starts, f.runner.starts)
                    self.assertEqual(before["record"]["quota_closed"], record["quota_closed"])
                    events = b.state.events("job", f.identity)
                    self.assertEqual(("preflight", "business", "evidence").index(phase)+1,
                        sum(e["kind"] == "QUOTA_PHASE_CLOSED" for e in events))
                    b.tick(); b.recover()
                    b.close_observation("job", f.identity, phase, fence)
                    self.assertEqual(events, b.state.events("job", f.identity))

    def test_verified_failure_requires_exact_result_identity_and_reader_exit(self):
        mutations = {
            "foreign_execution": lambda p: p["result"].update(execution_id="foreign"),
            "foreign_phase": lambda p: p["result"].update(phase="preflight"),
            "unchecked_reader": lambda p: p["result_reader_exit_proof"].update(collectors_stopped=False),
            "foreign_reader_boot": lambda p: p["result_reader_exit_proof"]["identity"].update(boot_id="other"),
            "live_writer": lambda p: p.update(writers_stopped=False),
            "contradictory_effects": lambda p: p["result"].update(effects_checked=True),
        }
        for name, amend in mutations.items():
            with self.subTest(mutation=name):
                f, _, _ = self.pending_result("business", failed=True, amend=amend)
                b = f.broker
                b.cancel(f.identity, f.row()["digest"], {"kind":"job"}, f.f.owner)
                before = copy.deepcopy(f.row())
                with b.state.transaction() as tx:
                    leases = [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")]
                b.tick()
                self.assertEqual(before, f.row())
                self.assertNotEqual("TERMINAL", f.row()["record"]["lifecycle"])
                with b.state.transaction() as tx:
                    self.assertEqual(leases, [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")])

    def test_closed_publication_rejects_changed_retained_evidence(self):
        for field in ("quota_closed", "quota_pending", "handles"):
            with self.subTest(field=field):
                f, fence, _ = self.pending_result("business")
                b = f.broker
                b.cancel(f.identity, f.row()["digest"], {"kind":"job"}, f.f.owner)
                with patch.object(b, "_complete", side_effect=RuntimeError("publication interrupted")):
                    with self.assertRaises(RuntimeError):
                        b.close_observation("job", f.identity, "business", fence)
                changed = copy.deepcopy(f.row()["record"][field])
                if field == "handles":
                    changed["business"]["execution_id"] = "foreign"
                else:
                    changed.pop("business")
                with b.state.transaction() as tx:
                    b.state.update(tx, "job", f.identity, "TEST_CORRUPTION", {field:changed})
                before = copy.deepcopy(f.row())
                starts = copy.deepcopy(f.runner.starts)
                events = b.state.events("job", f.identity)
                with self.assertRaises(JobError):
                    b.tick()
                self.assertEqual(before, f.row())
                self.assertEqual(starts, f.runner.starts)
                self.assertEqual(events, b.state.events("job", f.identity))

    def test_cancel_after_closure_rejects_changed_original_exit(self):
        for phase in ("preflight", "business", "evidence"):
            with self.subTest(phase=phase):
                f, fence, _ = self.pending_result(phase, failed=True)
                b = f.broker
                b.close_observation("job", f.identity, phase, fence)
                b.cancel(f.identity, f.row()["digest"], {"kind":"job"}, f.f.owner)
                if phase == "business":
                    b.tick()  # Record blocked evidence start before testing the EXITED snapshot.
                self.assertEqual("EXITED", f.row()["record"]["phase"])
                changed = copy.deepcopy(f.row()["record"]["exit_proof"])
                changed["exit_code"] = 77
                with b.state.transaction() as tx:
                    b.state.update(tx, "job", f.identity, "TEST_CORRUPTION", {"exit_proof":changed})
                before = copy.deepcopy(f.row())
                with self.assertRaises(JobError):
                    b.tick()
                self.assertEqual(before, f.row())

    def test_cancel_before_observer_enters_manager_finishes_original_task(self):
        for phase in ("preflight", "business", "evidence"):
            for failure in ("cancel", "observer_start", "manager_no_start"):
                with self.subTest(phase=phase, failure=failure):
                    f = fixtures.ResidentChainTests()
                    f.setUp(); self.addCleanup(f.doCleanups)
                    for earlier in ("preflight", "business")[:("preflight", "business", "evidence").index(phase)]:
                        f.close(earlier)
                    prepared = f.prepare(phase)
                    grant = f.make_grant(phase, prepared)
                    f.broker.bind_observation("job", f.identity, phase, grant.wire)
                    manager = SimpleNamespace(start=Mock(side_effect=runner._NoStartError("UNSUPPORTED", "not delivered")))
                    actual = runner.Runner(manager)
                    self.addCleanup(actual.close)
                    f.broker.runner = actual
                    held = []
                    with patch.object(actual, "_launch_supervisor", side_effect=lambda item, name: held.append(item)):
                        f.broker._start("job", f.identity, phase)
                    item, = held
                    f.broker.cancel(f.identity, f.f.request["request_digest"], {"kind": "job"}, f.f.owner)
                    if failure == "cancel":
                        actual.stop(item.handle)
                        actual._supervise(item)
                    elif failure == "observer_start":
                        with patch.object(runner.threading.Thread, "start", side_effect=RuntimeError("thread unavailable")):
                            actual._launch_supervisor(item, "test-observer")
                    else:
                        actual._supervise(item)
                    before = copy.deepcopy(f.row()["record"].get("delivery_intents", []))
                    f.broker.tick()
                    record = f.row()["record"]
                    self.assertEqual(("TERMINAL", "EXITED"), (record["lifecycle"], record["phase"]))
                    self.assertEqual("SUCCEEDED" if phase == "evidence" else "CANCELLED", record["outcome"])
                    self.assertTrue(record["execution_resources_released"])
                    self.assertTrue(record["exit_proof"]["launch_prevented"])
                    self.assertEqual(item.handle["execution_id"], record["exit_proof"]["execution_id"])
                    self.assertEqual(before, record.get("delivery_intents", []))
                    self.assertEqual(1 if failure == "manager_no_start" else 0, manager.start.call_count)
                    events = f.broker.state.events("job", f.identity)
                    f.broker.tick()
                    self.assertEqual(events, f.broker.state.events("job", f.identity))

    def stopped(self, phase, stage):
        f = fixtures.ResidentChainTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        for previous in ("preflight", "business", "evidence")[:("preflight", "business", "evidence").index(phase)]:
            f.close(previous)
        prepared = f.prepare(phase)
        grant = f.make_grant(phase, prepared)
        f.grants[phase] = grant
        b = f.broker
        b.bind_observation("job", f.identity, phase, grant.wire)
        b._start("job", f.identity, phase)
        execution = "job-" + f.identity + "-" + phase
        if stage != "none":
            self.assertTrue(b._guard_start(execution, lambda: True, stage="bootstrap"))
        f.now += fixtures.SECOND
        flags = dict.fromkeys(("future_start_blocked", "tree_exited", "collectors_stopped", "writers_stopped"), True)
        bootstrap = dict(execution_id=execution, state="EXITED", exit_code=0, **flags,
            effects_checked=True, unit="lhj-" + hashlib.sha256((execution + ":bootstrap").encode()).hexdigest() + ".service",
            result=dict(bootstrap_prepared=True, quota_observation=observed(grant)))
        proof = dict(bootstrap, exit_code=1, result=dict(outcome="CANCELLED", business_started=False, helper_started=True))
        if stage == "none":
            proof.update(launch_prevented=True, result=dict(outcome="CANCELLED", business_started=False, helper_started=False))
        if stage not in ("none", "bootstrap"):
            self.assertTrue(b._guard_start(execution, lambda: True, stage="helper", bootstrap_proof=bootstrap))
            unit = "lhj-" + hashlib.sha256(execution.encode()).hexdigest() + ".service"
            proof = dict(execution_id=execution, state="EXITED", exit_code=None, **flags,
                effects_checked=False, helper_result_verified=False, unit=unit,
                identity=dict(cgroup="/synthetic-job.slice/" + unit, boot_id=fixtures.BOOT, invocation_id="e"*32),
                result=dict(outcome="UNKNOWN", helper_started=True), missing=["No verified result"])
        if stage == "result_reader":
            self.assertTrue(b._guard_start(execution, lambda: True, stage="result_reader", helper_proof=proof))
            unit = "lhj-" + hashlib.sha256((execution + ":result_reader").encode()).hexdigest() + ".service"
            proof["result_reader_exit_proof"] = dict(execution_id=execution, state="EXITED", exit_code=1, **flags,
                unit=unit, identity=dict(cgroup="/synthetic-job.slice/" + unit, boot_id=fixtures.BOOT, invocation_id="f"*32))
        b.cancel(f.identity, f.f.request["request_digest"], {"kind": "job"}, f.f.owner)
        f.runner.proofs[execution] = proof
        return f, proof

    def check_completion(self, phase, stage):
        f, proof = self.stopped(phase, stage)
        b = f.broker
        before = copy.deepcopy(f.row())
        with b.state.transaction() as tx:
            leases = [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")]
        b.tick()
        row, record = f.row(), f.row()["record"]
        self.assertEqual(("TERMINAL", "EXITED"), (record["lifecycle"], record["phase"]))
        self.assertEqual("UNKNOWN" if phase == "business" else before["record"]["business_outcome"], record["outcome"])
        self.assertEqual(proof, record["exit_proof"])
        self.assertEqual(before["record"]["business_started"], record["business_started"])
        for key in ("handles", "delivery_intents", "execution_budget", "quota_preparations", "quota_closed"):
            self.assertEqual(before["record"][key], record[key])
        for key in ("request", "digest", "plan"):
            self.assertEqual(before[key], row[key])
        with b.state.transaction() as tx:
            self.assertEqual([r for r in leases if r[1] != f.identity],
                             [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")])
        events = b.state.events("job", f.identity)
        b.tick(); b.recover()
        b.cancel(f.identity, row["digest"], {"kind": "job"}, f.f.owner)
        self.assertEqual(events, b.state.events("job", f.identity))
        self.assertEqual(2 if phase == "business" else 3, len(f.runner.starts))
        if phase == "evidence":
            self.assertEqual("STAGING" if stage == "bootstrap" else "DURABILITY_UNKNOWN", record["evidence"])
            self.assertEqual(before["record"]["business_exit_proof"], record["business_exit_proof"])
            self.assertFalse(record.get("seals"))

    def test_business_reader_cancellation_finishes_without_claiming_a_result(self):
        self.check_completion("business", "result_reader")

    def test_cancel_between_execution_intent_and_first_delivery_finishes_each_phase(self):
        for phase in ("preflight", "business", "evidence"):
            with self.subTest(phase=phase):
                f, proof = self.stopped(phase, "none")
                before = copy.deepcopy(f.row()["record"].get("delivery_intents", []))
                f.broker.tick()
                record = f.row()["record"]
                self.assertEqual("TERMINAL", record["lifecycle"])
                self.assertEqual("SUCCEEDED" if phase == "evidence" else "CANCELLED", record["outcome"])
                self.assertEqual(proof, record["exit_proof"])
                self.assertEqual(before, record.get("delivery_intents", []))

    def test_evidence_cancellation_preserves_original_business_outcome(self):
        for stage in ("bootstrap", "helper", "result_reader"):
            with self.subTest(stage=stage):
                self.check_completion("evidence", stage)

    def test_reader_exit_requires_every_stop_flag_and_original_identity(self):
        changes = [{key: False} for key in ("future_start_blocked", "tree_exited", "collectors_stopped", "writers_stopped")]
        changes += [{"execution_id": "foreign"}, {"unit": "foreign"},
                    {"identity": dict(boot_id=fixtures.BOOT, invocation_id="f"*32, cgroup="/foreign")}]
        for change in changes:
            with self.subTest(change=change):
                f, proof = self.stopped("business", "result_reader")
                proof["result_reader_exit_proof"].update(change)
                with f.broker.state.transaction() as tx:
                    leases = list(tx.execute("SELECT * FROM leases ORDER BY resource"))
                f.broker.tick()
                self.assertNotEqual("TERMINAL", f.row()["record"]["lifecycle"])
                with f.broker.state.transaction() as tx:
                    self.assertEqual(leases, list(tx.execute("SELECT * FROM leases ORDER BY resource")))

    def test_evidence_stop_rejects_changed_business_result(self):
        from local_hand_jobs.stopped_completion import complete_cancelled_evidence
        f, _ = self.stopped("evidence", "helper")
        with patch("local_hand_jobs.stopped_completion.complete_cancelled_evidence", return_value=False):
            f.broker.tick()
        with f.broker.state.transaction() as tx:
            f.broker.state.update(tx, "job", f.identity, "FAULT", {"business_outcome": "FAILED"})
        with self.assertRaises(JobError), f.broker.state.transaction() as tx:
            complete_cancelled_evidence(f.broker, tx, f.broker.state.get("job", f.identity, tx))

    def test_verified_result_and_seal_follow_original_closure_despite_late_cancel(self):
        for phase in ("business", "evidence"):
            with self.subTest(phase=phase):
                f = fixtures.ResidentChainTests()
                f.setUp(); self.addCleanup(f.doCleanups)
                for previous in ("preflight", "business")[:1 if phase == "business" else 2]:
                    f.close(previous)
                complete = fixtures.complete
                def verified(grant, **options):
                    value = complete(grant, **options)
                    execution = "job-" + f.identity + "-" + phase
                    value[1].update(execution_id=execution, helper_result_verified=True,
                        result=dict(execution_id=execution, outcome="SUCCEEDED", business_started=True))
                    return value
                with patch.object(fixtures, "complete", side_effect=verified):
                    fence, _ = f.pending(phase)
                f.broker.cancel(f.identity, f.f.request["request_digest"], {"kind": "job"}, f.f.owner)
                f.broker.tick()
                self.assertNotEqual("TERMINAL", f.row()["record"]["lifecycle"])
                f.broker.close_observation("job", f.identity, phase, fence)
                record = f.row()["record"]
                self.assertEqual("TERMINAL", record["lifecycle"])
                self.assertEqual("SUCCEEDED", record["outcome"])
                self.assertEqual("SEALED" if phase == "evidence" else "STAGING", record["evidence"])
