"""Synthetic third-stage admission/recovery; no real cgroup acceptance claim."""
import copy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest import mock

from local_hand_jobs import budget
from local_hand_jobs.broker import Broker
from local_hand_jobs.cli import _known_manager_units
from local_hand_jobs.contract import JobError
from local_hand_jobs.runner import SystemdManager
import test_local_hand_jobs_bootstrap_broker as bootstrap_fixtures
from test_local_hand_jobs_broker import DeferredDeliverySupervisor


def unit(execution_id, stage=None):
    identity = execution_id if stage is None else execution_id + ":" + stage
    return "lhj-" + hashlib.sha256(identity.encode()).hexdigest() + ".service"


def helper_completion(case, execution_id):
    phase = case.row()["record"]["phase"].lower()
    grant = budget.stored_grant(case.row(), phase)
    return {"execution_id": execution_id, "unit": unit(execution_id), "state": "EXITED",
        "exit_code": 7, "future_start_blocked": True, "tree_exited": True,
        "collectors_stopped": True, "writers_stopped": True,
        "identity": {"boot_id": grant["boot_id"], "invocation_id": "a" * 32,
                     "cgroup": "/fixture/" + unit(execution_id)}}


def deliver_reader(case, execution_id, proof=None):
    def launch():
        case.runner.delivered.append((execution_id, "result_reader"))
        return {"delivered": execution_id + ":result_reader"}
    return case.broker._guard_start(execution_id, launch, stage="result_reader",
        helper_proof=helper_completion(case, execution_id) if proof is None else proof)


class ResultReaderBrokerTests(unittest.TestCase):
    def fixture(self):
        # Composition avoids collecting all existing bootstrap tests a second time.
        case = bootstrap_fixtures.BootstrapBrokerTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.f.policy.config = {"process_manager": {"cgroup": "/sys/fs/cgroup/fixture"}}
        return case

    def ready_reader(self, case):
        execution_id = case.start()
        self.assertIsNotNone(case.deliver(execution_id, "bootstrap"))
        self.assertIsNotNone(case.deliver(execution_id, "helper", bootstrap_fixtures.completion(execution_id)))
        return execution_id

    def assert_code(self, expected, callback):
        with self.assertRaises(JobError) as caught:
            callback()
        self.assertEqual(caught.exception.code, expected)

    def await_seal(self, case):
        case.broker.evidence = SimpleNamespace(root="/synthetic/sealed")
        case.start()
        for phase in ("preflight", "business"):
            execution_id = case.runner.starts[-1][1]
            case.deliver(execution_id, "bootstrap")
            case.deliver(execution_id, "helper", bootstrap_fixtures.completion(execution_id))
            self.assertIsNotNone(deliver_reader(case, execution_id))
            details = {} if phase == "preflight" else {
                "collectors_stopped": True, "writers_stopped": True,
                "result": {"business_started": True,
                    "evidence_snapshot": {"root": "/synthetic/raw", "members": []}}}
            case.runner.finish(execution_id, **details)
            case.broker.tick()
            if phase == "preflight":
                case.broker.tick()
        self.assertEqual(case.row()["record"]["phase"], "AWAITING_SEAL")

    def recover(self, case, runner=None):
        runner = runner or DeferredDeliverySupervisor()
        case.broker = Broker(case.f.db, case.f.policy, bootstrap_fixtures.BootstrapRegistry(),
                             runner, case.broker.evidence)
        case.f.broker = case.broker
        case.runner = runner
        case.f.runner = runner
        case.broker.recover()
        case.broker.tick()
        return runner

    def test_original_three_stage_intent_fixed_shares_and_reader_delivery_do_not_refund(self):
        case = self.fixture()
        execution_id = self.ready_reader(case)
        row = case.row()
        original_plan = copy.deepcopy(row["plan"])
        original_budget = copy.deepcopy(row["record"]["execution_budget"])
        original_roots = copy.deepcopy(row["record"]["bootstrap_grants"])
        plan = case.runner.starts[-1][2]
        self.assertEqual(plan["supervision_version"], 3)
        self.assertEqual(row["record"]["handles"]["preflight"]["supervision_version"], 3)
        with case.f.db.transaction() as tx:
            event = tx.execute("SELECT data_json FROM events WHERE kind='EXECUTION_INTENT'").fetchone()
        intent = json.loads(event[0])
        self.assertEqual(intent["handles"]["preflight"], {
            "execution_id": execution_id, "intent_only": True, "supervision_version": 3})
        grant = plan["budget_grant"]
        shares = [budget.substage_limits(grant, stage, supervision_version=3)
                  for stage in ("bootstrap", "helper", "result_reader")]
        total_cpu = grant["limits"]["cpu_seconds"]
        self.assertEqual([share["cpu_seconds"] for share in shares],
                         [total_cpu // 3, total_cpu - 2 * (total_cpu // 3), total_cpu // 3])
        self.assertEqual(sum(share["cpu_seconds"] for share in shares), total_cpu)
        deadline = budget.phase_deadline_ns(grant)
        proof = helper_completion(case, execution_id)
        self.assertNotIn("effects_checked", proof)
        self.assertIsNotNone(deliver_reader(case, execution_id, proof))
        for stage in ("bootstrap", "helper", "result_reader"):
            delivered = (deliver_reader(case, execution_id) if stage == "result_reader" else
                case.deliver(execution_id, stage,
                    bootstrap_fixtures.completion(execution_id) if stage == "helper" else None))
            self.assertIsNone(delivered)
        self.assertIsNone(case.runner.deliver(execution_id))
        record = case.row()["record"]
        self.assertEqual(record["delivery_intents"],
                         [execution_id + ":" + stage for stage in ("bootstrap", "helper", "result_reader")])
        self.assertEqual(record["helper_completed"]["preflight"], proof)
        self.assertEqual(len(case.runner.delivered), 3)
        self.assertEqual(record["execution_budget"], original_budget)
        self.assertEqual(record["bootstrap_grants"], original_roots)
        self.assertEqual(case.row()["plan"], original_plan)
        self.assertEqual(budget.phase_deadline_ns(grant), deadline)

    def test_reader_requires_both_prior_durable_deliveries(self):
        for prior in ([], ["bootstrap"], ["helper"]):
            with self.subTest(prior=prior):
                case = self.fixture()
                execution_id = case.start()
                with case.f.db.transaction() as tx:
                    case.f.db.update(tx, "job", case.f.request["operation_id"], "SYNTHETIC_PRIOR_DELIVERY", {
                        "delivery_intents": [execution_id + ":" + stage for stage in prior]})
                original = copy.deepcopy(case.row()["record"]["execution_budget"])
                self.assert_code("IO_UNCERTAIN", lambda: deliver_reader(case, execution_id))
                self.assertEqual(case.runner.delivered, [])
                self.assertEqual(case.row()["record"]["execution_budget"], original)

    def test_cancel_revocation_and_generation_changes_block_reader_before_launch(self):
        for fault in ("cancel", "revoke", "generation"):
            with self.subTest(fault=fault):
                case = self.fixture()
                execution_id = self.ready_reader(case)
                original = copy.deepcopy(case.row()["record"]["execution_budget"])
                if fault == "cancel":
                    case.f.cancel()
                elif fault == "revoke":
                    case.broker.revoke(case.f.owner.principal_id)
                else:
                    case.f.policy.generation += 1
                self.assertIsNone(deliver_reader(case, execution_id))
                self.assertEqual(len(case.runner.delivered), 2)
                self.assertEqual(case.row()["record"]["execution_budget"], original)
                self.assertNotIn("helper_completed", case.row()["record"])

    def test_reader_requires_original_consumed_roots_and_resource_lease(self):
        for fault in ("bootstrap_lease", "resource_lease"):
            with self.subTest(fault=fault):
                case = self.fixture()
                execution_id = self.ready_reader(case)
                with case.f.db.transaction() as tx:
                    if fault == "bootstrap_lease":
                        tx.execute("DELETE FROM leases WHERE owner LIKE 'bootstrap:%'")
                    else:
                        tx.execute("DELETE FROM leases WHERE owner NOT LIKE 'bootstrap:%'")
                with self.assertRaises(JobError):
                    deliver_reader(case, execution_id)
                self.assertEqual(len(case.runner.delivered), 2)
                self.assertNotIn("helper_completed", case.row()["record"])

    def test_old_immutable_intent_cannot_be_upgraded_by_a_current_handle_marker(self):
        for old_version in (None, 2):
            with self.subTest(old_version=old_version):
                case = self.fixture()
                update = case.f.db.update
                def old_intent(tx, namespace, identity, kind, changes):
                    if kind == "EXECUTION_INTENT":
                        changes = copy.deepcopy(changes)
                        handle = changes["handles"]["preflight"]
                        if old_version is None:
                            handle.pop("supervision_version")
                        else:
                            handle["supervision_version"] = old_version
                    return update(tx, namespace, identity, kind, changes)
                with mock.patch.object(case.f.db, "update", side_effect=old_intent):
                    execution_id = self.ready_reader(case)
                self.assertEqual(case.row()["record"]["handles"]["preflight"]["supervision_version"], 3)
                original = copy.deepcopy(case.row()["record"]["execution_budget"])
                self.assert_code("IO_UNCERTAIN", lambda: deliver_reader(case, execution_id))
                self.assertEqual(len(case.runner.delivered), 2)
                self.assertEqual(case.row()["record"]["execution_budget"], original)

    def test_reader_rejects_missing_or_noninteger_current_supervision_marker(self):
        for marker in (None, 2, True, "3"):
            with self.subTest(marker=marker):
                case = self.fixture()
                execution_id = self.ready_reader(case)
                handles = copy.deepcopy(case.row()["record"]["handles"])
                if marker is None:
                    handles["preflight"].pop("supervision_version")
                else:
                    handles["preflight"]["supervision_version"] = marker
                with case.f.db.transaction() as tx:
                    case.f.db.update(tx, "job", case.f.request["operation_id"], "SYNTHETIC_HANDLE", {"handles": handles})
                self.assert_code("IO_UNCERTAIN", lambda: deliver_reader(case, execution_id))
                self.assertEqual(len(case.runner.delivered), 2)

    def test_reader_rejects_incomplete_or_foreign_helper_exit_identity(self):
        case = self.fixture()
        execution_id = self.ready_reader(case)
        original = copy.deepcopy(case.row()["record"]["execution_budget"])
        corruptions = [("execution_id", "foreign"), ("unit", "foreign.service"),
            ("state", "RUNNING"), ("future_start_blocked", False), ("tree_exited", False),
            ("collectors_stopped", 1), ("writers_stopped", False), ("identity", {}),
            ("identity.boot_id", "22222222-2222-4222-8222-222222222222"),
            ("identity.invocation_id", "A" * 32), ("identity.invocation_id", "a" * 31),
            ("identity.invocation_id", 1), ("identity.cgroup", "/foreign/" + unit(execution_id))]
        for key, value in corruptions:
            proof = helper_completion(case, execution_id)
            if key.startswith("identity."):
                proof["identity"][key.split(".")[1]] = value
            else:
                proof[key] = value
            with self.subTest(key=key, value=value):
                self.assert_code("IO_UNCERTAIN", lambda: deliver_reader(case, execution_id, proof))
                self.assertEqual(len(case.runner.delivered), 2)
                self.assertEqual(case.row()["record"]["execution_budget"], original)
        self.assertNotIn("helper_completed", case.row()["record"])

    def test_reader_has_no_fresh_deadline_after_helper_or_host_restart(self):
        for fault in ("stop_grace_boundary", "phase_deadline", "operation_deadline", "different_boot"):
            with self.subTest(fault=fault):
                case = self.fixture()
                execution_id = self.ready_reader(case)
                original = copy.deepcopy(case.row()["record"]["execution_budget"])
                grant = case.runner.starts[-1][2]["budget_grant"]
                proof = helper_completion(case, execution_id)
                if fault == "different_boot":
                    case.clock["boot_id"] = "22222222-2222-4222-8222-222222222222"
                elif fault == "operation_deadline":
                    case.clock["boottime_ns"] = grant["deadline_boottime_ns"]
                else:
                    case.clock["boottime_ns"] = budget.phase_deadline_ns(grant)
                    if fault == "stop_grace_boundary":
                        case.clock["boottime_ns"] -= grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS
                self.assert_code("IO_UNCERTAIN" if fault == "different_boot" else "LIMIT_EXCEEDED",
                                 lambda: deliver_reader(case, execution_id, proof))
                self.assertEqual(len(case.runner.delivered), 2)
                self.assertEqual(len(case.runner.starts), 1)
                self.assertEqual(case.row()["record"]["execution_budget"], original)

    def test_private_preparation_and_helper_identity_metadata_never_leave_status(self):
        case = self.fixture()
        execution_id = self.ready_reader(case)
        deliver_reader(case, execution_id)
        record = case.row()["record"]
        self.assertIn("bootstrap_completed", record)
        self.assertIn("helper_completed", record)
        status = case.f.status()
        for name in ("handles", "delivery_intents", "bootstrap_grants", "bootstrap_completed",
                     "helper_completed", "execution_budget", "budget_grant"):
            self.assertNotIn(name, status)
        encoded = json.dumps(status, sort_keys=True)
        for private in ("/synthetic/", "/fixture/", "invocation_id", "boottime_ns", "supervision_version"):
            self.assertNotIn(private, encoded)

    def assert_unchecked_preflight_retains_barrier(self, case, execution_id, proof):
        before = copy.deepcopy(case.row()["record"])
        case.runner.proofs[execution_id] = proof
        case.broker.tick()
        case.broker.tick()
        record = case.row()["record"]
        self.assertEqual(record["phase"], "EXITED")
        self.assertEqual(record["lifecycle"], "RECONCILE_REQUIRED")
        self.assertEqual(record["outcome"], "UNKNOWN")
        self.assertIs(record["exit_proof"]["effects_checked"], False)
        self.assertEqual(record["exit_proof"]["exit_code"], 0)
        self.assertEqual(record["execution_budget"], before["execution_budget"])
        self.assertEqual(record["bootstrap_grants"], before["bootstrap_grants"])
        self.assertNotIn("business", record["handles"])
        self.assertEqual([item[2]["phase"] for item in case.runner.starts], ["preflight"])
        self.assertEqual(case.runner.delivered,
                         [(execution_id, "bootstrap"), (execution_id, "helper")])
        with case.f.db.transaction() as tx:
            promoted = tx.execute("SELECT COUNT(*) FROM events WHERE kind='PREFLIGHT_COMPLETE'").fetchone()[0]
        self.assertEqual(promoted, 0)
        self.assert_code("RESOURCE_BUSY", lambda: case.broker.call(
            "lh_job_submit", case.f.make_request(), case.f.owner))

    def test_refused_reader_with_zero_helper_exit_and_no_facts_remains_unknown(self):
        case = self.fixture()
        execution_id = self.ready_reader(case)
        helper = helper_completion(case, execution_id)
        helper["exit_code"] = 0
        proof = SystemdManager._unavailable_result(helper, "result reader startup guard refused delivery")
        self.assertEqual(proof["facts"], {})
        self.assertEqual(proof["result"]["outcome"], "UNKNOWN")
        self.assert_unchecked_preflight_retains_barrier(case, execution_id, proof)

    def test_stable_input_facts_cannot_promote_unchecked_zero_exit_preflight(self):
        case = self.fixture()
        execution_id = self.ready_reader(case)
        proof = dict(helper_completion(case, execution_id), exit_code=0,
            effects_checked=False, facts={"inputs_stable": True}, result={"outcome": "UNKNOWN"})
        self.assert_unchecked_preflight_retains_barrier(case, execution_id, proof)

    def test_first_evidence_after_recovery_can_finish_all_three_original_stages_once(self):
        case = self.fixture()
        self.await_seal(case)
        original = copy.deepcopy(case.row()["record"])
        runner = self.recover(case)
        self.assertEqual([item[2]["phase"] for item in runner.starts], ["evidence"])
        execution_id = runner.starts[-1][1]
        self.assertIsNotNone(case.deliver(execution_id, "bootstrap"))
        self.assertIsNotNone(case.deliver(execution_id, "helper", bootstrap_fixtures.completion(execution_id)))
        self.assertIsNotNone(deliver_reader(case, execution_id))
        self.assertIsNone(deliver_reader(case, execution_id))
        current = case.row()["record"]
        self.assertTrue(current["recovered"])
        self.assertEqual(current["business_outcome"], original["business_outcome"])
        for key in ("started_boottime_ns", "deadline_boottime_ns", "boot_id"):
            self.assertEqual(current["execution_budget"][key], original["execution_budget"][key])
        for phase, grant in original["execution_budget"]["grants"].items():
            self.assertEqual(current["execution_budget"]["grants"][phase], grant)
        self.assertEqual(current["handles"]["evidence"]["supervision_version"], 3)
        self.assertEqual(len(current["delivery_intents"]), 9)

    def test_another_recovery_at_each_evidence_stage_never_replays_or_advances(self):
        for delivered_stages in range(4):
            with self.subTest(delivered_stages=delivered_stages):
                case = self.fixture()
                self.await_seal(case)
                self.recover(case)
                execution_id = case.runner.starts[-1][1]
                if delivered_stages >= 1:
                    case.deliver(execution_id, "bootstrap")
                if delivered_stages >= 2:
                    case.deliver(execution_id, "helper", bootstrap_fixtures.completion(execution_id))
                if delivered_stages >= 3:
                    deliver_reader(case, execution_id)
                before = copy.deepcopy(case.row()["record"])
                prior_broker = case.broker
                proof = helper_completion(case, execution_id)
                runner = self.recover(case)
                self.assertEqual(runner.starts, [])
                for stage, details in (("bootstrap", {}),
                        ("helper", {"bootstrap_proof": bootstrap_fixtures.completion(execution_id)}),
                        ("result_reader", {"helper_proof": proof})):
                    launch = mock.Mock()
                    self.assertIsNone(prior_broker._guard_start(execution_id, launch, stage=stage, **details))
                    launch.assert_not_called()
                after = case.row()["record"]
                for key in ("execution_budget", "bootstrap_grants", "delivery_intents"):
                    self.assertEqual(after.get(key), before.get(key))
                self.assertEqual(after["evidence"], "DURABILITY_UNKNOWN")

    def test_prior_evidence_reader_intent_blocks_claim_of_first_recovered_evidence(self):
        case = self.fixture()
        self.await_seal(case)
        evidence_id = "job-" + case.f.request["operation_id"] + "-evidence"
        delivered = case.row()["record"]["delivery_intents"]
        with case.f.db.transaction() as tx:
            case.f.db.update(tx, "job", case.f.request["operation_id"], "MANAGER_DELIVERY_INTENT", {
                "delivery_intents": [*delivered, evidence_id + ":result_reader"]})
        original = copy.deepcopy(case.row()["record"]["execution_budget"])
        runner = self.recover(case)
        self.assertEqual(runner.starts, [])
        self.assertEqual(case.row()["record"]["execution_budget"], original)


class ResultReaderInventoryTests(unittest.TestCase):
    def setUp(self):
        self.case = bootstrap_fixtures.BootstrapBrokerTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_missing_first_receipt_still_derives_all_three_units_from_original_intent(self):
        start = self.case.runner.start
        def lose_acknowledgement(parent, execution_id, plan):
            start(parent, execution_id, plan)
            raise JobError("IO_UNCERTAIN", "Synthetic loss of first manager acknowledgement")
        with mock.patch.object(self.case.runner, "start", side_effect=lose_acknowledgement):
            self.case.f.submit()
            self.case.broker.tick()
        self.execution_id = self.case.runner.starts[-1][1]
        row = self.case.row()
        self.assertEqual(row["record"]["handles"]["preflight"], {"execution_id": self.execution_id,
            "intent_only": True, "supervision_version": 3})
        self.assertEqual(set(_known_manager_units([row])),
            {unit(self.execution_id), unit(self.execution_id, "bootstrap"), unit(self.execution_id, "result_reader")})
        row["record"]["handles"]["preflight"]["manager"] = {
            "version": 3, "bootstrap": {"unit": "foreign-bootstrap.service"},
            "helper": {"unit": "foreign-helper.service"}, "result_reader": {"unit": "foreign-reader.service"}}
        self.assertEqual(set(_known_manager_units([row])),
            {unit(self.execution_id), unit(self.execution_id, "bootstrap"), unit(self.execution_id, "result_reader")})

    def test_reader_inventory_rejects_unbound_layouts_instead_of_ignoring_reader(self):
        self.execution_id = self.case.start()
        for fault in ("missing_allocation", "missing_allocation_v2", "missing_original_version",
                      "bad_version", "bool_version", "foreign_execution"):
            with self.subTest(fault=fault):
                row = self.case.row()
                handle = row["record"]["handles"]["preflight"]
                handle["manager"] = {"version": 3}
                if fault == "missing_allocation":
                    row["record"]["bootstrap_grants"] = {}
                elif fault == "missing_allocation_v2":
                    row["record"]["bootstrap_grants"] = {}
                    handle["supervision_version"] = 2
                    handle.pop("manager")
                elif fault == "missing_original_version":
                    handle.pop("supervision_version")
                elif fault == "bad_version":
                    handle["supervision_version"] = 2
                elif fault == "bool_version":
                    handle["supervision_version"] = True
                else:
                    handle["execution_id"] = "foreign"
                with self.assertRaises(JobError):
                    _known_manager_units([row])

    def test_legacy_layouts_keep_their_original_one_or_two_unit_inventory(self):
        self.execution_id = self.case.start()
        row = self.case.row()
        handle = row["record"]["handles"]["preflight"]
        handle.pop("supervision_version")
        handle["manager"] = {"version": 2}
        self.assertEqual(set(_known_manager_units([row])),
                         {unit(self.execution_id), unit(self.execution_id, "bootstrap")})
        handle["manager"] = {"version": 1}
        row["record"]["bootstrap_grants"] = {}
        self.assertEqual(_known_manager_units([row]), [unit(self.execution_id)])


if __name__ == "__main__":
    unittest.main()
