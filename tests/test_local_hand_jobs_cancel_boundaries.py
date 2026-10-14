"""Cancellation timing boundaries with a real ledger and modeled OS proofs."""
import copy
import hashlib
import unittest

from unittest.mock import patch

from local_hand_jobs.contract import JobError
from test_local_hand_jobs_quota_binding import observed
import test_local_hand_jobs_quota_resident_chain as fixtures


class CancelBoundaryTests(unittest.TestCase):
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
