"""Real SQLite/Broker coverage for the H11 observation-only recovery case.

The systemd boundary remains an explicit observer model.  The durable broker,
ledger transitions, leases, original handle and Q4 recovery implementation are
real; no result is synthesized in place of q4_h11_recovery.run().
"""
from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from unittest import mock

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("H11 recovery uses the Linux runner and original Q2 fixtures")

from e3_host import q2_resident as resident
from e3_host import q4_h11_recovery as recovery
from local_hand_jobs import budget, result_reader, runner as runner_module
from local_hand_jobs.broker import Broker
from test_local_hand_jobs_quota_binding import observed
import test_local_hand_jobs_quota_resident_chain as chain_fixtures


def _unit(execution_id, stage):
    identity = execution_id if stage == "helper" else execution_id + ":" + stage
    return "lhj-" + hashlib.sha256(identity.encode()).hexdigest() + ".service"


class RecoveryObserver:
    """One reattach and one observe/stop proof; never a delivery."""

    def __init__(self):
        self.reattaches = self.observations = self.stops = 0
        self.starts = []

    def set_start_guard(self, guard):
        self.guard = guard

    def start(self, *args, **kwargs):
        self.starts.append((args, kwargs))
        raise AssertionError("H11 recovery must not start an execution")

    def reattach(self, handle, plan):
        self.reattaches += 1
        self.handle = copy.deepcopy(handle)
        self.plan = copy.deepcopy(plan)
        return copy.deepcopy(handle)

    def inspect(self, handle):
        self.observations += 1
        # Models the recovery manager's identity-bound observe/StopUnit/recheck
        # transaction.  Anonymous collectors were owned by the dead resident.
        self.stops += 1
        return {"state": "EXITED", "future_start_blocked": True,
                "tree_exited": True, "writers_stopped": True,
                "collectors_stopped": False, "effects_checked": False,
                "exit_code": None, "facts": {},
                "result": {"outcome": "UNKNOWN", "helper_started": True},
                "missing": ["original anonymous collectors were lost"]}

    def stop(self, handle):
        raise AssertionError("broker cancellation is not part of H11 recovery")


class H11RecoveryBrokerTests(unittest.TestCase):
    def fixture(self):
        case = chain_fixtures.ResidentChainTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        prepared = case.prepare("preflight")
        grant = case.make_grant("preflight", prepared)
        case.grants["preflight"] = grant
        case.broker.bind_observation("job", case.identity, "preflight", grant.wire)
        case.broker._start("job", case.identity, "preflight")
        execution_id = grant.request.as_dict()["execution_id"]
        self.assertTrue(case.broker._guard_start(
            execution_id, lambda: True, stage="bootstrap"))
        case.now += budget.NANOSECONDS
        bootstrap_proof = {
            "execution_id": execution_id, "unit": _unit(execution_id, "bootstrap"),
            "state": "EXITED", "exit_code": 0,
            **dict.fromkeys(("future_start_blocked", "tree_exited", "collectors_stopped",
                             "writers_stopped", "effects_checked"), True),
            "result": {"bootstrap_prepared": True,
                       "quota_observation": observed(grant)},
        }
        self.assertTrue(case.broker._guard_start(
            execution_id, lambda: True, stage="helper",
            bootstrap_proof=bootstrap_proof))
        helper_proof = dict(bootstrap_proof, unit=_unit(execution_id, "helper"),
            identity={"cgroup": "/synthetic-job.slice/" + _unit(execution_id, "helper"),
                      "boot_id": grant.as_dict()["budget"]["boot_id"],
                      "invocation_id": "e" * 32})
        self.assertTrue(case.broker._guard_start(
            execution_id, lambda: True, stage="result_reader",
            helper_proof=helper_proof))

        row = case.row()
        grant = budget.stored_grant(row, "preflight")
        phase_deadline = budget.phase_deadline_ns(grant)
        runtime_deadline = (phase_deadline
                            - grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS)
        manager = {"version": 3, "stage": "result_reader",
                   "allocation_digest": row["record"]["bootstrap_grants"]["preflight"]["grant_digest"]}
        for index, stage in enumerate(("bootstrap", "helper", "result_reader"), 1):
            manager[stage] = {
                "unit": _unit(execution_id, stage), "boot_id": grant["boot_id"],
                "result_path": "/synthetic/result.json",
                "cgroup_parent": "/sys/fs/cgroup/fixture",
                "launch_acked": True, "stop_acked": False,
                "invocation_id": format(index, "x") * 32,
                "execution_id": execution_id,
                "phase_deadline_boottime_ns": runtime_deadline,
                "delivery_attempted": True,
            }
        manager["result_reader"].update(
            collector_started=False, h11_delivery_barrier=True)
        handle = {"execution_id": execution_id, "phase": "preflight",
                  "supervision_version": 3, "manager": manager}
        # Exercise Broker.tick's real proof path.  The dedicated H11 live hold
        # persists the exported receipt but must not append generic uncertainty
        # or move the row out of RUNNING.
        case.runner.proofs[execution_id] = {
            **runner_module._h11_held(), "recovery_handle": handle}
        case.broker.tick()
        held = case.row()["record"]
        self.assertEqual("RUNNING", held["lifecycle"])
        self.assertEqual("PENDING", held["outcome"])
        self.assertEqual(handle, held["handles"]["preflight"])
        self.assertNotIn("EXECUTION_UNCERTAIN",
                         [event["kind"] for event in case.f.db.events("job", case.identity)])
        plan = resident.h11_plan(case.broker, case.identity,
                                 grant["deadline_boottime_ns"])
        return case, plan

    @staticmethod
    def ledger(case):
        with case.f.db.transaction() as tx:
            row = case.f.db.get("job", case.identity, tx)
            leases = [tuple(item) for item in tx.execute(
                "SELECT resource,owner,epoch FROM leases ORDER BY resource").fetchall()]
            events = [tuple(item) for item in tx.execute(
                "SELECT seq,kind FROM events WHERE namespace='job' AND id=? ORDER BY seq",
                (case.identity,)).fetchall()]
        return copy.deepcopy(row), leases, events

    def test_origin_barrier_stays_running_and_recovery_uses_original_ledger_once(self):
        case, plan = self.fixture()
        before, leases_before, events_before = self.ledger(case)
        observer = RecoveryObserver()
        recovered = Broker(case.f.db, case.f.policy, chain_fixtures.ChainRegistry(),
                           observer, case.broker.evidence, quota_required=True)
        self.addCleanup(recovered.close)
        with mock.patch.object(recovered, "_release",
                               side_effect=AssertionError("H11 must retain every lease")), \
             mock.patch.object(result_reader, "_read_result",
                               side_effect=AssertionError("H11 must not reread a result")):
            summary = recovery.run(recovered, plan,
                current_clock=lambda: {"boot_id": plan.get("boot_id", "unused"),
                                       "boottime_ns": plan["phase_deadline_ns"] - 1})

        after, leases_after, events_after = self.ledger(case)
        self.assertEqual("RECOVERY_RECORDED", summary["status"])
        self.assertEqual((1, 1, 1, []),
                         (observer.reattaches, observer.observations, observer.stops,
                          observer.starts))
        for key in ("request", "plan", "digest"):
            self.assertEqual(before[key], after[key])
        self.assertEqual(before["record"]["delivery_intents"],
                         after["record"]["delivery_intents"])
        self.assertEqual(before["record"]["execution_budget"],
                         after["record"]["execution_budget"])
        self.assertEqual(leases_before, leases_after)
        appended = [kind for _, kind in events_after[len(events_before):]]
        self.assertEqual(["RECOVERY_BARRIER", "QUOTA_EXIT_PENDING"], appended)
        proof = after["record"]["exit_proof"]
        self.assertIs(proof["collectors_stopped"], False)
        self.assertIs(proof["effects_checked"], False)
        self.assertEqual("UNKNOWN", proof["result"]["outcome"])
        self.assertEqual("RECONCILE_REQUIRED", after["record"]["lifecycle"])

    def test_original_phase_deadline_blocks_recovery_before_ledger_mutation(self):
        case, plan = self.fixture()
        before = self.ledger(case)
        observer = RecoveryObserver()
        recovered = Broker(case.f.db, case.f.policy, chain_fixtures.ChainRegistry(),
                           observer, case.broker.evidence, quota_required=True)
        self.addCleanup(recovered.close)
        with self.assertRaisesRegex(ValueError, "H11_ORIGINAL_DEADLINE"):
            recovery.run(recovered, plan,
                current_clock=lambda: {"boot_id": "unused",
                                       "boottime_ns": plan["phase_deadline_ns"]})
        self.assertEqual(before, self.ledger(case))
        self.assertEqual((0, 0, 0, []),
                         (observer.reattaches, observer.observations, observer.stops,
                          observer.starts))

    def test_origin_plan_rejects_invocation_identity_reuse(self):
        case, _ = self.fixture()
        row = case.row()
        handle = copy.deepcopy(row["record"]["handles"]["preflight"])
        handle["manager"]["result_reader"]["invocation_id"] = \
            handle["manager"]["helper"]["invocation_id"]
        with case.f.db.transaction() as tx:
            case.f.db.update(tx, "job", case.identity,
                             "SYNTHETIC_INVOCATION_REUSE",
                             {"handles": {"preflight": handle}})
        with self.assertRaisesRegex(ValueError, "H11_MANAGER_IDENTITY_REUSE"):
            resident.h11_plan(case.broker, case.identity,
                              budget.stored_grant(case.row(), "preflight")["deadline_boottime_ns"])


if __name__ == "__main__":
    unittest.main()
