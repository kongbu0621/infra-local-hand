"""H11 at the durable-intent/manager-delivery boundary (modeled OS, real ledger)."""
import copy
import hashlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from local_hand_jobs import runner
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError
from local_hand_jobs.task_session import TaskSession
from test_local_hand_jobs_quota_binding import observed
import test_local_hand_jobs_quota_resident_chain as fixtures


class RecoveryDeliveryTests(unittest.TestCase):
    def interrupted(self, phase, stage, *, amend=None):
        f = fixtures.ResidentChainTests()
        f.setUp(); self.addCleanup(f.doCleanups)
        phases = ("preflight", "business", "evidence")
        stages = ("bootstrap", "helper", "result_reader")
        for earlier in phases[:phases.index(phase)]:
            f.close(earlier)
        prepared = f.prepare(phase)
        grant = f.make_grant(phase, prepared)
        f.broker.bind_observation("job", f.identity, phase, grant.wire)
        f.broker._start("job", f.identity, phase)
        f.now += fixtures.SECOND
        execution = "job-" + f.identity + "-" + phase
        proofs = {}
        for index, current in enumerate(stages):
            suffix = "" if current == "helper" else ":" + current
            unit = "lhj-" + hashlib.sha256((execution + suffix).encode()).hexdigest() + ".service"
            absent = index >= stages.index(stage)
            proof = dict(execution_id=execution, unit=unit, state="EXITED",
                future_start_blocked=True, tree_exited=True, writers_stopped=True,
                collectors_stopped=False, effects_checked=False, exit_code=None,
                observed_ns=f.now, proof_digest="a"*64,
                identity=None if absent else dict(boot_id=fixtures.BOOT,
                    invocation_id="e"*32, cgroup="/synthetic-job.slice/" + unit),
                result=dict(outcome="UNKNOWN", helper_started=not absent))
            if absent:
                proof.update(launch_prevented=True)
                proof["result"]["business_started"] = False
            proofs[current] = proof
            if index <= stages.index(stage):
                options = {}
                if current == "helper":
                    bootstrap = dict(proofs["bootstrap"], exit_code=0, collectors_stopped=True,
                        effects_checked=True, result=dict(bootstrap_prepared=True, quota_observation=observed(grant)))
                    options["bootstrap_proof"] = bootstrap
                elif current == "result_reader":
                    options["helper_proof"] = dict(proofs["helper"], collectors_stopped=True)
                # Commit the actual delivery fence, then lose the API before
                # the last callback can reach the manager. Earlier callbacks
                # model delivered units, whose exit is independently proved.
                if current == stage:
                    def interrupted_launch():
                        raise InterruptedError("API lost before manager delivery")
                    with self.assertRaises(InterruptedError):
                        f.broker._guard_start(execution, interrupted_launch, stage=current, **options)
                else:
                    self.assertTrue(f.broker._guard_start(execution, lambda: True, stage=current, **options))
        manager = object.__new__(runner._SystemdExecutionCore)
        handle = dict(version=3, recovered=True, **{s:dict(stage=s, recovered=True) for s in stages})
        with patch.object(manager, "_check_manager_binding"), \
                patch.object(manager, "_inspect_unit", side_effect=lambda part: proofs[part["stage"]]):
            proof = manager.inspect(handle)
        if amend:
            amend(proof)
        replacement = SimpleNamespace(reattach=Mock(side_effect=lambda h,p:h), inspect=Mock(return_value=proof))
        b = Broker(f.broker.state, f.broker.policy, f.broker.registry, replacement,
                   evidence=f.broker.evidence, quota_required=True)
        session = TaskSession(dict(mode="recover", operation_id=f.identity,
            request_digest=f.row()["digest"], principal_id=f.f.owner.principal_id), Mock(), None)
        self.addCleanup(session.close); session.attach(b)
        return f, b, session, proof

    def test_recovery_after_intent_before_delivery_finishes_without_replay(self):
        for phase in ("preflight", "business", "evidence"):
            for stage in ("bootstrap", "helper", "result_reader"):
                with self.subTest(phase=phase, stage=stage):
                    f, b, session, proof = self.interrupted(phase, stage)
                    before = copy.deepcopy(f.row())
                    events = b.state.events("job", f.identity)
                    with b.state.transaction() as tx:
                        leases = [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")]
                    with patch.object(b, "_start", side_effect=AssertionError("H11 replayed execution")):
                        session.recover(); session.tick()
                    record = f.row()["record"]
                    self.assertEqual(("TERMINAL", "EXITED", "SUCCEEDED" if phase == "evidence" else "UNKNOWN"),
                        (record["lifecycle"], record["phase"], record["outcome"]))
                    self.assertFalse(record["cancel_requested"])
                    self.assertEqual(proof, record["exit_proof"])
                    self.assertFalse(proof["collectors_stopped"])
                    self.assertFalse(proof["effects_checked"])
                    for key in ("request", "digest", "plan", "reserved_bytes"):
                        self.assertEqual(before[key], f.row()[key])
                    for key in ("delivery_intents", "execution_budget", "quota_preparations", "quota_closed",
                                "business_outcome", "business_exit_proof", "frozen_snapshot"):
                        self.assertEqual(before["record"].get(key), record.get(key), key)
                    if phase == "business" and stage != "result_reader":
                        self.assertFalse(record["business_started"])
                        self.assertEqual("NONE", record["side_effects"])
                    if phase == "evidence":
                        self.assertEqual("STAGING" if stage != "result_reader" else "DURABILITY_UNKNOWN", record["evidence"])
                    self.assertEqual(events, b.state.events("job", f.identity)[:len(events)])
                    with b.state.transaction() as tx:
                        self.assertEqual([x for x in leases if x[1] != f.identity],
                            [tuple(x) for x in tx.execute("SELECT * FROM leases ORDER BY resource")])
                    final = copy.deepcopy(f.row())
                    events = b.state.events("job", f.identity)
                    session.recover(); session.tick()
                    self.assertEqual(final, f.row())
                    self.assertEqual(events, b.state.events("job", f.identity))
                    session.manager.finish_recovery.assert_called_once()

    def test_missing_absence_proof_or_contradictory_receipt_cannot_release_resources(self):
        cases = ("identity", "unit", "exit_code", "digest", "observation", "writer", "collector",
                 "result", "marker", "reader_missing", "saved_invocation", "saved_ack", "manager")
        for stage in ("helper", "result_reader"):
            for damage in cases:
                with self.subTest(stage=stage, damage=damage):
                    def amend(proof):
                        target = proof if stage == "helper" else proof["result_reader_exit_proof"]
                        if damage == "identity": target["identity"] = {"invocation_id":"f"*32}
                        elif damage == "unit": target["unit"] = "foreign.service"
                        elif damage == "exit_code": target["exit_code"] = 0
                        elif damage == "digest": target.pop("proof_digest")
                        elif damage == "observation": target.pop("observed_ns")
                        elif damage == "writer": target["writers_stopped"] = False
                        elif damage == "collector": target["collectors_stopped"] = True
                        elif damage == "result": target["result"]["outcome"] = "SUCCEEDED"
                        elif damage == "marker": target.pop("launch_prevented")
                        elif damage == "reader_missing": proof.pop("result_reader_exit_proof")
                    f, b, session, proof = self.interrupted("business", stage, amend=amend)
                    if damage in ("saved_invocation", "saved_ack"):
                        handles = copy.deepcopy(f.row()["record"]["handles"])
                        handles["business"]["manager"] = {stage: {
                            "invocation_id":"f"*32} if damage == "saved_invocation" else {"launch_acked":True}}
                        with b.state.transaction() as tx:
                            b.state.update(tx, "job", f.identity, "TEST_RECEIPT", {"handles":handles})
                    with b.state.transaction() as tx:
                        leases = [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")]
                    if damage == "manager":
                        session.manager.finish_recovery.side_effect = JobError("IO_UNCERTAIN", "Parent occupied")
                    with patch.object(b, "_start", side_effect=AssertionError("H11 replayed execution")):
                        session.recover()
                        if damage == "manager":
                            with self.assertRaises(JobError): session.tick()
                        else:
                            session.tick()
                    self.assertNotEqual("TERMINAL", f.row()["record"]["lifecycle"])
                    self.assertFalse(f.row()["record"]["cancel_requested"])
                    with b.state.transaction() as tx:
                        self.assertEqual(leases, [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")])


if __name__ == "__main__":
    unittest.main()
