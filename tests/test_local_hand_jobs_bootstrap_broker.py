"""Synthetic two-unit intent/consumption tests; no kernel enforcement claims."""
import copy
import hashlib
import unittest
from types import SimpleNamespace
from unittest import mock

from local_hand_jobs import budget
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError
import test_local_hand_jobs_broker as broker_fixtures
from test_local_hand_jobs_broker import DeferredDeliverySupervisor, RegistryFixture


class BootstrapRegistry(RegistryFixture):
    def resolve(self, request, policy, *, principal=None):
        plan = super().resolve(request, policy, principal=principal)
        plan["execution"] = {"kind": "host.inspect", "operation_id": request["operation_id"],
            "roots": {name: "/synthetic/" + name + "/" + request["operation_id"]
                      for name in ("work", "evidence", "temporary")}}
        return plan


def slot(number):
    return {"slot_id": "slot-" + str(number), "roots": {
        name: {"path": "/synthetic/" + name + "/slot-" + str(number), "device": 1,
               "inode": number * 3 + index + 1, "uid": 1000}
        for index, name in enumerate(("work", "evidence", "temporary"))}}


def completion(execution_id):
    return {"state": "EXITED", "execution_id": execution_id,
        "unit": "lhj-" + hashlib.sha256((execution_id + ":bootstrap").encode()).hexdigest() + ".service",
        "exit_code": 0, "future_start_blocked": True, "tree_exited": True,
        "collectors_stopped": True, "writers_stopped": True, "effects_checked": True,
        "result": {"bootstrap_prepared": True, "helper_started": True, "business_started": False}}


class BootstrapBrokerTests(unittest.TestCase):
    def setUp(self):
        self.f = broker_fixtures.BrokerTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.policy.profiles = copy.deepcopy(self.f.policy.profiles)
        self.f.policy.profiles["fixture"].update(bootstrap_slots=[slot(1), slot(2), slot(3)],
            bootstrap_evidence_store={"path": "/synthetic/sealed", "device": 1, "inode": 100, "uid": 1000})
        self.runner = DeferredDeliverySupervisor()
        self.f.runner = self.runner
        self.broker = Broker(self.f.db, self.f.policy, BootstrapRegistry(), self.runner)
        self.f.broker = self.broker
        self.clock = {"boot_id": "11111111-1111-4111-8111-111111111111", "boottime_ns": 100 * budget.NANOSECONDS}
        patch = mock.patch.object(budget, "current_clock", side_effect=lambda: dict(self.clock))
        patch.start(); self.addCleanup(patch.stop)

    def start(self):
        self.f.submit(); self.broker.tick()
        return self.runner.starts[-1][1]

    def row(self):
        return self.f.db.get("job", self.f.request["operation_id"])

    def deliver(self, execution_id, stage, proof=None):
        def launch():
            self.runner.delivered.append((execution_id, stage))
            return object()
        return self.broker._guard_start(execution_id, launch, stage=stage, bootstrap_proof=proof)

    def test_two_deliveries_have_durable_separate_intents_and_one_budget(self):
        execution_id = self.start()
        original_plan = copy.deepcopy(self.row()["plan"])
        original_budget = copy.deepcopy(self.row()["record"]["execution_budget"])
        allocation = self.runner.starts[-1][2]["bootstrap_allocation"]
        self.assertEqual(allocation, self.row()["record"]["bootstrap_grants"]["preflight"])
        self.assertIsNotNone(self.deliver(execution_id, "bootstrap"))
        self.assertIsNotNone(self.deliver(execution_id, "helper", completion(execution_id)))
        self.assertIsNone(self.deliver(execution_id, "bootstrap"))
        self.assertIsNone(self.deliver(execution_id, "helper", completion(execution_id)))
        self.assertIsNone(self.runner.deliver(execution_id), "legacy call cannot replay staged delivery")
        record = self.row()["record"]
        self.assertEqual(record["delivery_intents"], [execution_id + ":bootstrap", execution_id + ":helper"])
        self.assertEqual(record["bootstrap_completed"]["preflight"], completion(execution_id))
        self.assertEqual(original_budget, record["execution_budget"])
        self.assertEqual(original_plan, self.row()["plan"])

    def test_phase_budget_is_fixed_and_cpu_shares_do_not_refund(self):
        execution_id = self.start()
        grant = self.runner.starts[-1][2]["budget_grant"]
        end = budget.phase_deadline_ns(grant)
        first, second = (budget.substage_limits(grant, stage) for stage in ("bootstrap", "helper"))
        self.assertEqual(first["cpu_seconds"] + second["cpu_seconds"], grant["limits"]["cpu_seconds"])
        self.assertEqual(second["log_bytes"], grant["limits"]["log_bytes"])
        self.deliver(execution_id, "bootstrap")
        self.clock["boottime_ns"] = end - grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS
        with self.assertRaisesRegex(JobError, "runtime"):
            self.deliver(execution_id, "helper", completion(execution_id))
        self.assertEqual(len(self.runner.delivered), 1)
        self.assertEqual(budget.phase_deadline_ns(grant), end)

    def test_helper_requires_exact_successful_preparation_and_consumption(self):
        execution_id = self.start()
        with self.assertRaises(JobError): self.deliver(execution_id, "helper", completion(execution_id))
        self.deliver(execution_id, "bootstrap")
        for key, bad in (("unit", "foreign.service"), ("tree_exited", False), ("effects_checked", 1),
                         ("exit_code", True), ("execution_id", "foreign"), ("result", {})):
            proof = completion(execution_id); proof[key] = bad
            with self.subTest(key=key), self.assertRaises(JobError):
                self.deliver(execution_id, "helper", proof)
        with self.f.db.transaction() as tx:
            tx.execute("DELETE FROM leases WHERE owner LIKE 'bootstrap:%'")
        with self.assertRaises(JobError): self.deliver(execution_id, "helper", completion(execution_id))
        self.assertEqual(len(self.runner.delivered), 1)

    def test_cancel_or_revoke_between_units_blocks_helper(self):
        for fault in ("cancel", "revoke", "generation"):
            with self.subTest(fault=fault):
                case = BootstrapBrokerTests(); case.setUp(); self.addCleanup(case.doCleanups)
                execution_id = case.start(); case.deliver(execution_id, "bootstrap")
                if fault == "cancel": case.f.cancel()
                elif fault == "revoke": case.broker.revoke(case.f.owner.principal_id)
                else: case.f.policy.generation += 1
                self.assertIsNone(case.deliver(execution_id, "helper", completion(execution_id)))
                self.assertEqual(len(case.runner.delivered), 1)

    def test_restart_never_replays_bootstrap_or_continues_helper(self):
        execution_id = self.start(); self.deliver(execution_id, "bootstrap")
        allocation = copy.deepcopy(self.row()["record"]["bootstrap_grants"])
        replacement = DeferredDeliverySupervisor()
        restored = Broker(self.f.db, self.f.policy, BootstrapRegistry(), replacement)
        restored.recover(); restored.tick()
        self.assertEqual(replacement.starts, [])
        self.assertIsNone(self.deliver(execution_id, "helper", completion(execution_id)))
        self.assertEqual(self.row()["record"]["bootstrap_grants"], allocation)
        self.assertEqual(self.row()["record"]["lifecycle"], "RECONCILE_REQUIRED")

    def test_legacy_delivery_cannot_be_reissued_as_bootstrap(self):
        execution_id = self.start()
        self.assertIsNotNone(self.runner.deliver(execution_id))
        self.assertIsNone(self.deliver(execution_id, "bootstrap"))

    def test_business_uses_same_consumed_roots_without_new_phase_allowance(self):
        execution_id = self.start()
        first = self.runner.starts[-1][2]["bootstrap_allocation"]
        self.deliver(execution_id, "bootstrap")
        self.deliver(execution_id, "helper", completion(execution_id))
        self.runner.finish(execution_id); self.broker.tick(); self.broker.tick()
        second = self.runner.starts[-1][2]["bootstrap_allocation"]
        self.assertEqual(second["roots"], first["roots"])
        self.assertEqual(second["allocation_id"], first["allocation_id"])
        self.assertTrue(first["fresh"]); self.assertFalse(second["fresh"])

    def test_recovered_first_seal_accepts_staged_history_without_replay(self):
        self.broker.evidence = SimpleNamespace(root="/synthetic/sealed")
        execution_id = self.start()
        for phase in ("preflight", "business"):
            execution_id = self.runner.starts[-1][1]
            self.deliver(execution_id, "bootstrap")
            self.deliver(execution_id, "helper", completion(execution_id))
            kwargs = {} if phase == "preflight" else {"collectors_stopped": True, "writers_stopped": True,
                "result": {"business_started": True, "evidence_snapshot": {"root": "/synthetic/raw", "members": []}}}
            self.runner.finish(execution_id, **kwargs); self.broker.tick()
            if phase == "preflight": self.broker.tick()
        self.assertEqual(self.row()["record"]["phase"], "AWAITING_SEAL")
        old_grants = copy.deepcopy(self.row()["record"]["execution_budget"]["grants"])
        replacement = DeferredDeliverySupervisor()
        self.broker = Broker(self.f.db, self.f.policy, BootstrapRegistry(), replacement, self.broker.evidence)
        self.broker.recover(); self.broker.tick()
        self.runner = replacement
        self.assertEqual([item[2]["phase"] for item in replacement.starts], ["evidence"])
        execution_id = replacement.starts[-1][1]
        self.assertIsNotNone(self.deliver(execution_id, "bootstrap"))
        self.assertIsNotNone(self.deliver(execution_id, "helper", completion(execution_id)))
        for phase, grant in old_grants.items():
            self.assertEqual(self.row()["record"]["execution_budget"]["grants"][phase], grant)
        self.assertIsNone(self.deliver(execution_id, "helper", completion(execution_id)))
        class RecoveringSupervisor(DeferredDeliverySupervisor):
            def reattach(self, handle, plan):
                self.recovery_plan = copy.deepcopy(plan)
                return handle
        observer = RecoveringSupervisor()
        recovered = Broker(self.f.db, self.f.policy, BootstrapRegistry(), observer, self.broker.evidence)
        recovered.recover(); recovered.tick()
        self.assertFalse(observer.starts)
        self.assertEqual(observer.recovery_plan["evidence_store_root"], "/synthetic/sealed")
        self.assertEqual(observer.recovery_plan["evidence_snapshot"], self.row()["record"]["frozen_snapshot"])
        self.assertEqual(observer.recovery_plan["bootstrap_allocation"],
                         self.row()["record"]["bootstrap_grants"]["evidence"])
