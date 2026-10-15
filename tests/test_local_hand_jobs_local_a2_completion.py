"""A2 cancellation/recovery with real SQLite and modeled runtime/OS proofs.

The registered plan is real; these tests neither execute A2 nor attest a host.
They reuse the existing phase fixtures without replaying their whole suites.
"""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from local_hand_jobs import local_a2_jobs
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import request_digest
from local_hand_jobs.preflight_completion import supports_local_completion
from local_hand_jobs.policy import Policy, thaw
from local_hand_jobs.registry import Registry
from local_hand_jobs.task_session import TaskSession
import test_local_hand_jobs_broker as broker_fixtures
import test_local_hand_jobs_budget as budget_fixtures
import test_local_hand_jobs_cancel_boundaries as cancel_fixtures
import test_local_hand_jobs_quota_resident_chain as chain_fixtures
import test_local_hand_jobs_recovery_delivery as recovery_fixtures
from test_local_hand_local_a2_preparation import runtime_fixture
from test_local_hand_jobs_local_a2_admission import local_a2_policy_fixture


class LocalA2CompletionTests(unittest.TestCase):
    def setUp(self):
        self.runtime = runtime_fixture()
        self.facts = dict(inputs_stable=True, local_a2_runtime_verified=True, installed_bytecode_verified=True,
            runtime_descriptor_digest=local_a2_jobs.descriptor_digest(self.runtime))
        self.plan_damage = None
        original_request = broker_fixtures.BrokerTests.make_request
        original_complete = chain_fixtures.complete
        original_finish = broker_fixtures.SupervisorFixture.finish
        config = local_a2_policy_fixture("/synthetic-completion")
        config["limits"]["retained_bytes"] = 1024**3
        profile = config["profiles"]["fixture"]
        profile["local_a2_runtimes"] = {"ledger-a2": self.runtime}
        profile["budgets"][local_a2_jobs.KIND] = dict(broker_fixtures.SYNTHETIC_BUDGET,
            wall_seconds=90, cpu_seconds=30, temporary_bytes=1024**2, memory_bytes=32*1024**2,
            processes=16, log_bytes=96*1024, reservation_bytes=4*1024**2)
        config["principals"]["owner"]["profiles"]["fixture"]["runtime_refs"] = ["ledger-a2"]
        real_policy, real_registry = Policy(config), Registry()

        def make_request(fixture):
            fixture.policy.expected = lambda _: real_policy.expected("fixture")
            value = original_request(fixture)
            fixture.policy.limits = dict(fixture.policy.limits, retained_bytes=1024**3)
            value.update(kind=local_a2_jobs.KIND, inputs={"runtime_ref": "ledger-a2"},
                         expected=real_policy.expected("fixture"))
            value["request_digest"] = request_digest(value)
            return value

        def resolve(registry, request, policy, **kwargs):
            # Preserve the real Registry's expected/deployment bindings and
            # canonical plan shape through the SQLite round trip.
            value = thaw(real_registry.resolve(request, real_policy, **kwargs))
            if self.plan_damage is not None:
                self.plan_damage(value["execution"])
            return value

        def complete(*args, **kwargs):
            value = original_complete(*args, **kwargs)
            value[1]["facts"] = copy.deepcopy(self.facts)
            # ResidentChain.pending binds the final modeled proof digest.
            return value

        def finish(supervisor, execution_id, **kwargs):
            kwargs.setdefault("facts", copy.deepcopy(self.facts))
            return original_finish(supervisor, execution_id, **kwargs)

        for target, name, replacement in (
            (broker_fixtures.BrokerTests, "make_request", make_request),
            (broker_fixtures.RegistryFixture, "resolve", resolve),
            (chain_fixtures.ChainRegistry, "resolve", resolve),
            (chain_fixtures, "complete", complete),
            (broker_fixtures.SupervisorFixture, "finish", finish),
        ):
            current = patch.object(target, name, replacement)
            current.start()
            self.addCleanup(current.stop)

    def fixture(self, cls, *, setup=False):
        case = cls()
        if setup:
            case.setUp()
        self.addCleanup(case.doCleanups)
        return case

    def test_cancelled_preflight_needs_no_business_runtime_result(self):
        case = self.fixture(cancel_fixtures.CancelBoundaryTests)
        for stage in ("none", "helper", "result_reader"):
            with self.subTest(stage=stage):
                f, proof = case.stopped("preflight", stage, kind=local_a2_jobs.KIND)
                before = copy.deepcopy(f.row())
                self.assertNotIn("facts", before["record"])
                f.broker.tick()
                record = f.row()["record"]
                self.assertEqual(("TERMINAL", "CANCELLED", "NONE"),
                    (record["lifecycle"], record["outcome"], record["side_effects"]))
                self.assertEqual(proof, record["exit_proof"])
                self.assertEqual(1, len(f.runner.starts))
                self.assertEqual(before["request"], f.row()["request"])

    def test_business_cancel_retains_unknown_and_only_releases_execution(self):
        case = self.fixture(cancel_fixtures.CancelBoundaryTests)
        for stage in ("helper", "result_reader"):
            with self.subTest(stage=stage):
                case.check_completion("business", stage, kind=local_a2_jobs.KIND)

    def test_evidence_cancel_preserves_original_business_result(self):
        case = self.fixture(cancel_fixtures.CancelBoundaryTests)
        case.check_completion("evidence", "result_reader", kind=local_a2_jobs.KIND)

    def test_runtime_facts_and_static_scope_fail_closed_without_releasing_capacity(self):
        case = self.fixture(cancel_fixtures.CancelBoundaryTests)
        valid = copy.deepcopy(self.facts)
        for label, facts, damage in (
            ("null", None, None), ("empty", {}, None), ("missing", {"inputs_stable": True}, None),
            ("digest", dict(valid, runtime_descriptor_digest="0" * 64), None),
            ("external-write", valid, lambda p: p["writable"].append("/external")),
            ("different-program", valid, lambda p: p["stages"][0]["argv"].append("--storage-config")),
        ):
            with self.subTest(fault=label):
                self.facts = facts if facts else valid
                self.plan_damage = damage
                f, proof = case.stopped("business", "result_reader", kind=local_a2_jobs.KIND)
                if not facts:
                    with f.broker.state.transaction() as tx:
                        f.broker.state.update(tx, "job", f.identity, "MODELED_SNAPSHOT_DAMAGE", {"facts": facts})
                with f.broker.state.transaction() as tx:
                    leases = [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")]
                starts = copy.deepcopy(f.runner.starts)
                f.broker.tick()
                self.assertNotEqual("TERMINAL", f.row()["record"]["lifecycle"])
                self.assertNotEqual("SUCCEEDED", f.row()["record"]["outcome"])
                self.assertEqual(starts, f.runner.starts)
                with f.broker.state.transaction() as tx:
                    self.assertEqual(leases, [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")])

    def test_mutable_facts_cannot_replace_missing_original_runtime_verification(self):
        valid = copy.deepcopy(self.facts)
        self.facts = {"inputs_stable": True}
        case = self.fixture(cancel_fixtures.CancelBoundaryTests)
        f, _ = case.stopped("business", "result_reader", kind=local_a2_jobs.KIND)
        with f.broker.state.transaction() as tx:
            f.broker.state.update(tx, "job", f.identity, "MODELED_SNAPSHOT_DAMAGE", {"facts": valid})
            self.assertFalse(supports_local_completion(f.broker.state.get("job", f.identity, tx), tx=tx))
        f.broker.tick()
        self.assertNotEqual("TERMINAL", f.row()["record"]["lifecycle"])
        with f.broker.state.transaction() as tx:
            self.assertEqual(1, tx.execute("SELECT count(*) FROM leases WHERE owner=?", (f.identity,)).fetchone()[0])

    def test_second_recovery_retains_original_exit_and_never_replays_a2(self):
        case = self.fixture(recovery_fixtures.RecoveryDeliveryTests)
        f, first, session, proof = case.interrupted("business", "result_reader", kind=local_a2_jobs.KIND)
        session.recover()
        first.tick()  # Lose the API after retaining exit, before manager acknowledgement.
        before = copy.deepcopy(f.row())
        replacement = SimpleNamespace(reattach=Mock(side_effect=AssertionError("Repeated observation")))
        second = Broker(first.state, first.policy, first.registry, replacement, evidence=first.evidence, quota_required=True)
        recovered = TaskSession(dict(session.value), Mock(), None)
        self.addCleanup(recovered.close)
        recovered.attach(second)
        with patch.object(second, "_start", side_effect=AssertionError("A2 business replay")):
            recovered.recover()
            recovered.tick()
        row = f.row()
        self.assertEqual(("TERMINAL", "EXITED", "UNKNOWN"),
            tuple(row["record"][key] for key in ("lifecycle", "phase", "outcome")))
        self.assertEqual(proof, row["record"]["exit_proof"])
        self.assertFalse(proof["effects_checked"])
        self.assertFalse(proof["collectors_stopped"])
        for key in ("request", "digest", "plan"):
            self.assertEqual(before[key], row[key])
        events = second.state.events("job", f.identity)
        recovered.recover()
        recovered.tick()
        self.assertEqual(events, second.state.events("job", f.identity))
        replacement.reattach.assert_not_called()

    def test_between_phase_recovery_never_starts_the_following_phase(self):
        for previous in ("preflight", "business"):
            with self.subTest(previous=previous):
                f = self.fixture(chain_fixtures.ResidentChainTests, setup=True)
                f.close("preflight")
                if previous == "business":
                    f.close("business")
                before = copy.deepcopy(f.row())
                session = TaskSession(dict(mode="recover", operation_id=f.identity,
                    request_digest=before["digest"], principal_id=f.f.owner.principal_id), Mock(), None)
                self.addCleanup(session.close)
                session.attach(f.broker)
                with patch.object(f.broker, "_start", side_effect=AssertionError("Recovery started another phase")):
                    session.recover()
                    session.tick()
                record = f.row()["record"]
                self.assertEqual("TERMINAL", record["lifecycle"])
                self.assertEqual("UNKNOWN" if previous == "preflight" else before["record"]["business_outcome"], record["outcome"])
                self.assertEqual(before["record"]["exit_proof"], record["exit_proof"])
                self.assertFalse(record.get("seals"))

    def test_completed_evidence_recovery_releases_only_execution_and_reuses_result(self):
        case = self.fixture(budget_fixtures.BudgetTests, setup=True)
        case.test_retained_completed_recovery_releases_only_execution_on_restart()


if __name__ == "__main__":
    unittest.main()
