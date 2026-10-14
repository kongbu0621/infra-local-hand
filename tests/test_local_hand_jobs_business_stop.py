"""Original SQLite business cancellation; OS proofs are modeled."""
import copy
import hashlib
import unittest
from unittest.mock import patch

from local_hand_jobs.contract import JobError
import test_local_hand_jobs_quota_resident_chain as fixtures


class BusinessStopTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ResidentChainTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.broker = self.f.broker
        self.f.close("preflight")

    def stopped(self, *, helper=False, **flags):
        prepared = self.f.prepare("business")
        grant = self.f.make_grant("business", prepared)
        self.f.grants["business"] = grant
        self.broker.bind_observation("job", self.f.identity, "business", grant.wire)
        self.broker._start("job", self.f.identity, "business")
        execution = "job-" + self.f.identity + "-business"
        self.assertTrue(self.broker._guard_start(execution, lambda: True, stage="bootstrap"))
        self.f.now += fixtures.SECOND
        if helper:
            from test_local_hand_jobs_quota_binding import observed
            bootstrap = dict(execution_id=execution, state="EXITED", exit_code=0,
                unit="lhj-" + hashlib.sha256((execution + ":bootstrap").encode()).hexdigest() + ".service",
                **dict.fromkeys(("future_start_blocked", "tree_exited", "collectors_stopped",
                                 "writers_stopped", "effects_checked"), True),
                result=dict(bootstrap_prepared=True, quota_observation=observed(grant)))
            self.assertTrue(self.broker._guard_start(execution, lambda: True, stage="helper", bootstrap_proof=bootstrap))
        self.broker.cancel(self.f.identity, self.f.f.request["request_digest"], {"kind": "job"}, self.f.f.owner)
        proof = dict(execution_id=execution, state="EXITED", exit_code=1,
            **dict.fromkeys(("future_start_blocked", "tree_exited", "collectors_stopped",
                             "writers_stopped", "effects_checked"), True),
            result=dict(outcome="CANCELLED", bootstrap_prepared=True, business_started=False, helper_started=True))
        proof.update(flags)
        self.f.runner.proofs[execution] = proof
        return proof

    def leases(self):
        with self.broker.state.transaction() as tx:
            return [tuple(row) for row in tx.execute("SELECT * FROM leases ORDER BY resource")]

    def test_business_bootstrap_cancellation_finishes_without_ordinary_closure(self):
        proof = self.stopped()
        before = copy.deepcopy(self.f.row())
        leases = self.leases()
        self.broker.tick()
        row = self.f.row()
        record = row["record"]
        self.assertEqual(("TERMINAL", "EXITED", "CANCELLED", "NONE"),
                         tuple(record[k] for k in ("lifecycle", "phase", "outcome", "side_effects")))
        self.assertEqual(proof, record["exit_proof"])
        self.assertIs(record["business_started"], False)
        self.assertEqual({"preflight"}, set(record["quota_closed"]))
        self.assertNotIn("business", record["quota_observed"])
        self.assertEqual([x for x in leases if x[1] != self.f.identity], self.leases())
        self.assertEqual(6, len(self.leases()))
        for key in ("handles", "execution_budget", "delivery_intents", "quota_preparations"):
            self.assertEqual(before["record"][key], record[key])
        for key in ("request", "digest", "plan"):
            self.assertEqual(before[key], row[key])
        events = self.broker.state.events("job", self.f.identity)
        self.broker.tick()
        self.broker.recover()
        self.broker.cancel(self.f.identity, row["digest"], {"kind": "job"}, self.f.f.owner)
        self.assertEqual(events, self.broker.state.events("job", self.f.identity))
        self.assertEqual(2, len(self.f.runner.starts))

    def test_existing_pending_proof_can_finish_after_deadline_without_supervisor(self):
        from local_hand_jobs.stopped_completion import complete_stopped_business_start
        proof = self.stopped(exit_code=None, effects_checked=False)
        with patch("local_hand_jobs.stopped_completion.complete_stopped_business_start", return_value=False):
            self.broker.tick()
        self.broker._unknown("job", self.f.identity, "Original controller failure")
        self.f.now += 10000 * fixtures.SECOND
        self.broker.runner = None
        with self.broker.state.transaction() as tx:
            self.assertTrue(complete_stopped_business_start(self.broker, tx, self.broker.state.get("job", self.f.identity, tx)))
        self.assertEqual(proof, self.f.row()["record"]["exit_proof"])
        self.assertEqual(6, len(self.leases()))

    def test_helper_delivery_cannot_be_erased_by_no_business_label(self):
        self.stopped(helper=True)
        leases = self.leases()
        self.broker.tick()
        self.assertNotEqual("TERMINAL", self.f.row()["record"]["lifecycle"])
        self.assertEqual(leases, self.leases())

    def cancelled_helper(self, **flags):
        values = dict(exit_code=0, effects_checked=False, helper_result_verified=False,
                      result=dict(outcome="UNKNOWN", helper_started=True),
                      missing=["cancelled before result observation; no new reader is authorized"])
        values.update(flags)
        return self.stopped(helper=True, **values)

    def test_cancelled_inspection_preserves_unknown_result_and_original_start_facts(self):
        for started in (None, True, False):
            with self.subTest(business_started=started):
                case = BusinessStopTests()
                case.setUp()
                self.addCleanup(case.doCleanups)
                proof = case.cancelled_helper()
                with case.broker.state.transaction() as tx:
                    case.broker.state.update(tx, "job", case.f.identity, "START_FACT",
                                             {"business_started": started})
                before, leases = copy.deepcopy(case.f.row()), case.leases()
                case.broker.tick()
                row, record = case.f.row(), case.f.row()["record"]
                self.assertEqual(("TERMINAL", "EXITED", "UNKNOWN", "RETAINED_LOCAL_FILES"),
                    tuple(record[k] for k in ("lifecycle", "phase", "outcome", "side_effects")))
                self.assertEqual(proof, record["exit_proof"])
                self.assertIs(record["business_started"], started)
                self.assertEqual({"preflight"}, set(record["quota_closed"]))
                self.assertEqual([x for x in leases if x[1] != case.f.identity], case.leases())
                self.assertEqual(6, len(case.leases()))
                for key in ("handles", "execution_budget", "delivery_intents", "quota_preparations", "quota_observed"):
                    self.assertEqual(before["record"][key], record[key])
                for key in ("request", "digest", "plan"):
                    self.assertEqual(before[key], row[key])
                events = case.broker.state.events("job", case.f.identity)
                self.assertEqual("INSPECTION_CANCELLED", events[-1]["kind"])
                case.broker.tick()
                case.broker.recover()
                case.broker.cancel(case.f.identity, row["digest"], {"kind": "job"}, case.f.f.owner)
                self.assertEqual(events, case.broker.state.events("job", case.f.identity))
                self.assertEqual(2, len(case.f.runner.starts))

    def test_cancelled_helper_requires_complete_exit_and_unobserved_result(self):
        flags = [{key: False} for key in ("future_start_blocked", "tree_exited", "writers_stopped", "collectors_stopped")]
        flags += [{"helper_result_verified": True}, {"effects_checked": True},
                  {"result": dict(outcome="SUCCEEDED", helper_started=True)}]
        for change in flags:
            with self.subTest(change=change):
                case = BusinessStopTests()
                case.setUp()
                self.addCleanup(case.doCleanups)
                case.cancelled_helper(**change)
                leases = case.leases()
                case.broker.tick()
                self.assertNotEqual("TERMINAL", case.f.row()["record"]["lifecycle"])
                self.assertEqual(leases, case.leases())

    def test_retained_helper_proof_recovers_without_supervisor_and_rejects_other_effects(self):
        from local_hand_jobs.stopped_completion import complete_cancelled_inspection
        proof = self.cancelled_helper()
        with patch("local_hand_jobs.stopped_completion.complete_cancelled_inspection", return_value=False):
            self.broker.tick()
        self.broker._unknown("job", self.f.identity, "Original controller failure")
        self.broker.runner = None
        self.f.now += 10000 * fixtures.SECOND
        leases = self.leases()
        for key, value in (("kind", "storage.write"), ("stages", ["write"]),
                           ("storage", {"destination": "external"}), ("writable", ["/external"])):
            with self.subTest(key=key), self.broker.state.transaction() as tx:
                row = self.broker.state.get("job", self.f.identity, tx)
                row["plan"]["execution"][key] = value
                self.assertFalse(complete_cancelled_inspection(self.broker, tx, row))
        self.assertEqual(leases, self.leases())
        with self.broker.state.transaction() as tx:
            self.assertTrue(complete_cancelled_inspection(self.broker, tx, self.broker.state.get("job", self.f.identity, tx)))
        self.assertEqual(proof, self.f.row()["record"]["exit_proof"])

    def test_cancelled_helper_rejects_changed_proof_and_rolls_back_failed_event(self):
        from local_hand_jobs.stopped_completion import complete_cancelled_inspection
        self.cancelled_helper()
        with patch("local_hand_jobs.stopped_completion.complete_cancelled_inspection", return_value=False):
            self.broker.tick()
        before, leases = copy.deepcopy(self.f.row()), self.leases()
        with self.assertRaisesRegex(RuntimeError, "disk fault"):
            with self.broker.state.transaction() as tx, patch.object(self.broker.state, "update", side_effect=RuntimeError("disk fault")):
                complete_cancelled_inspection(self.broker, tx, self.broker.state.get("job", self.f.identity, tx))
        self.assertEqual(before, self.f.row())
        self.assertEqual(leases, self.leases())
        pending = copy.deepcopy(before["record"]["quota_pending"])
        pending["business"]["proof"]["exit_code"] = 1
        with self.broker.state.transaction() as tx:
            self.broker.state.update(tx, "job", self.f.identity, "FAULT", {"quota_pending": pending})
        with self.assertRaises(JobError), self.broker.state.transaction() as tx:
            complete_cancelled_inspection(self.broker, tx, self.broker.state.get("job", self.f.identity, tx))
        self.assertEqual(leases, self.leases())

    def test_inspection_with_result_reader_delivery_requires_original_result_path(self):
        from local_hand_jobs.stopped_completion import complete_cancelled_inspection
        self.cancelled_helper()
        with patch("local_hand_jobs.stopped_completion.complete_cancelled_inspection", return_value=False):
            self.broker.tick()
        row, leases = self.f.row(), self.leases()
        deliveries = row["record"]["delivery_intents"] + ["job-" + self.f.identity + "-business:result_reader"]
        with self.broker.state.transaction() as tx:
            self.broker.state.update(tx, "job", self.f.identity, "MANAGER_DELIVERY_INTENT", {"delivery_intents": deliveries})
            self.assertFalse(complete_cancelled_inspection(self.broker, tx, self.broker.state.get("job", self.f.identity, tx)))
        self.assertEqual(leases, self.leases())

    def test_missing_exit_or_writer_proof_retains_execution_lease(self):
        for key in ("future_start_blocked", "tree_exited", "writers_stopped", "collectors_stopped"):
            with self.subTest(key=key):
                case = BusinessStopTests()
                case.setUp()
                self.addCleanup(case.doCleanups)
                case.stopped(**{key: False})
                leases = case.leases()
                case.broker.tick()
                self.assertNotEqual("TERMINAL", case.f.row()["record"]["lifecycle"])
                self.assertEqual(leases, case.leases())

    def test_completion_event_failure_rolls_back_lease_release(self):
        from local_hand_jobs.stopped_completion import complete_stopped_business_start
        self.stopped()
        with patch("local_hand_jobs.stopped_completion.complete_stopped_business_start", return_value=False):
            self.broker.tick()
        before, leases = copy.deepcopy(self.f.row()), self.leases()
        with self.assertRaisesRegex(RuntimeError, "disk fault"):
            with self.broker.state.transaction() as tx, patch.object(self.broker.state, "update", side_effect=RuntimeError("disk fault")):
                complete_stopped_business_start(self.broker, tx, self.broker.state.get("job", self.f.identity, tx))
        self.assertEqual(before, self.f.row())
        self.assertEqual(leases, self.leases())

    def test_changed_pending_snapshot_is_rejected(self):
        from local_hand_jobs.stopped_completion import complete_stopped_business_start
        self.stopped()
        with patch("local_hand_jobs.stopped_completion.complete_stopped_business_start", return_value=False):
            self.broker.tick()
        pending = copy.deepcopy(self.f.row()["record"]["quota_pending"])
        pending["business"]["proof"]["exit_code"] = 0
        with self.broker.state.transaction() as tx:
            self.broker.state.update(tx, "job", self.f.identity, "FAULT", {"quota_pending": pending})
        leases = self.leases()
        with self.assertRaises(JobError), self.broker.state.transaction() as tx:
            complete_stopped_business_start(self.broker, tx, self.broker.state.get("job", self.f.identity, tx))
        self.assertEqual(leases, self.leases())
