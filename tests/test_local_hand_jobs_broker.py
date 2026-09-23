"""Deterministic synthetic supervisor tests; no physical cgroup claims."""
from __future__ import annotations

import copy
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import time
import threading
import unittest
import uuid
import sqlite3
from unittest import mock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError, Principal, request_digest
from local_hand_jobs.state import StateStore


class PolicyFixture:
    generation = 1
    limits = {"max_queued": 20, "max_running": 2, "retained_bytes": 100000,
              "ledger_emergency_bytes": 1000, "requests_per_minute": 30}
    profiles = {"fixture": {"budgets": {"reconcile": {"reservation_bytes": 1000}}}}

    def authorize(self, principal, scope, request=None, owner=None):
        if scope not in principal.scopes or (owner is not None and owner != principal.principal_id):
            raise JobError("UNAUTHORIZED", "Fixture grant does not permit access")

    def expected(self, _):
        return {"node_id": "synthetic-node", "install_uuid": "11111111-1111-4111-8111-111111111111",
                "deployment_epoch": 1, "profile_digest": "1" * 64,
                "policy_digest": "2" * 64, "registry_digest": "3" * 64}

    def capabilities(self, principal, cursor=None, page_size=100):
        return {"authority_id": "fixture", "profiles": [{"profile_ref": "fixture", "expected": self.expected(None)}]}


class RegistryFixture:
    def resolve(self, request, policy, *, principal=None):
        return {"kind": request["kind"], "profile_ref": request["profile_ref"],
                "resource_ids": ["same-physical-root"], "reservation_bytes": 1000,
                "inputs": request["inputs"], "budgets": {"wall_seconds": 30}}


class SupervisorFixture:
    def __init__(self):
        self.starts, self.stops = [], []
        self.proofs = {}

    def start(self, parent, execution_id, plan):
        self.starts.append((parent, execution_id, copy.deepcopy(plan)))
        return {"execution_id": execution_id, "phase": plan["phase"]}

    def inspect(self, handle):
        return self.proofs.get(handle["execution_id"], {"state": "RUNNING"})

    def stop(self, handle):
        self.stops.append(handle["execution_id"])
        return self.proofs.get(handle["execution_id"], {"state": "UNKNOWN"})

    def finish(self, execution_id, **kwargs):
        self.proofs[execution_id] = {"state": "EXITED", "future_start_blocked": True,
            "tree_exited": True, "effects_checked": True, "exit_code": 0,
            "facts": {"inputs_stable": True}, **kwargs}


class DeferredDeliverySupervisor(SupervisorFixture):
    """The final manager delivery is deliberately delayed after queue acceptance."""
    def set_start_guard(self, guard):
        self.guard = guard
        self.delivered = []

    def deliver(self, execution_id):
        def launch():
            self.delivered.append(execution_id)
            return {"synthetic_manager_delivery": execution_id}
        return self.guard(execution_id, launch)


class CatalogFixture(RegistryFixture):
    def __init__(self):
        self.observations = {}
        self.prepared = {}

    def register_evidence(self, fact):
        self.observations[fact["operation_id"]] = copy.deepcopy(fact)

    def register_prepared(self, ref, fact):
        self.prepared[ref] = copy.deepcopy(fact)


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = StateStore(Path(self.temp.name) / "ledger.sqlite", "authority", "ledger", initialize=True)
        self.addCleanup(self.db.close)
        self.policy, self.runner = PolicyFixture(), SupervisorFixture()
        self.broker = Broker(self.db, self.policy, RegistryFixture(), self.runner)
        self.owner = Principal("owner", frozenset("lh:" + scope for scope in
            ("inspect", "submit", "read", "cancel", "reconcile", "evidence")))
        self.request = self.make_request()

    def make_request(self):
        req = {"schema_version": "lh-job-v1", "operation_id": str(uuid.uuid4()),
               "kind": "host.inspect", "profile_ref": "fixture", "expected": self.policy.expected(None),
               "inputs": {}, "expires_at": int(time.time()) + 120}
        req["request_digest"] = request_digest(req)
        return req

    def submit(self):
        return self.broker.call("lh_job_submit", self.request, self.owner)

    def status(self):
        return self.broker.call("lh_job_status", {"operation_id": self.request["operation_id"]}, self.owner)

    def cancel(self, target=None):
        return self.broker.call("lh_job_cancel", {"operation_id": self.request["operation_id"],
            "expected_request_digest": self.request["request_digest"], "target": target or {"kind": "job"}}, self.owner)

    def reconcile(self, identity):
        return self.broker.call("lh_job_reconcile", {"operation_id": self.request["operation_id"],
            "expected_request_digest": self.request["request_digest"], "reconcile_id": identity}, self.owner)

    def assertCode(self, code, function):
        with self.assertRaises(JobError) as raised:
            function()
        self.assertEqual(code, raised.exception.code)

    def test_ack_loss_dedup_and_cross_principal_conflict(self):
        first = self.submit()
        self.policy.generation += 1
        self.assertEqual(first, self.submit())
        changed = dict(self.request, expires_at=self.request["expires_at"] + 1)
        changed["request_digest"] = request_digest(changed)
        self.assertCode("CONFLICT", lambda: self.broker.call("lh_job_submit", changed, self.owner))
        outsider = Principal("outsider", self.owner.scopes)
        self.assertCode("UNAUTHORIZED", lambda: self.broker.call("lh_job_submit", self.request, outsider))
        self.assertFalse(self.runner.starts)

    def test_preflight_and_business_have_distinct_intents(self):
        self.submit(); self.broker.tick()
        self.assertEqual("preflight", self.runner.starts[0][2]["phase"])
        preflight = self.runner.starts[0][1]
        self.runner.finish(preflight)
        self.broker.tick()
        self.assertEqual("PREFLIGHT_COMPLETE", self.status()["phase"])
        self.assertEqual("PENDING", self.status()["outcome"])
        self.broker.tick()
        self.assertEqual("business", self.runner.starts[1][2]["phase"])
        self.runner.finish(self.runner.starts[1][1])
        self.broker.tick()
        self.assertEqual("SUCCEEDED", self.status()["outcome"])
        self.assertEqual("STAGING", self.status()["evidence"])
        self.assertEqual({}, self.status()["outputs"])

    def test_cancel_queued_prevents_start_and_releases_only_proven_resources(self):
        self.submit(); result = self.cancel(); self.broker.tick()
        self.assertEqual("CANCELLED", result["outcome"])
        self.assertFalse(self.runner.starts)
        self.request = self.make_request()
        self.submit()

    def test_delayed_launch_cancel_unknown_holds_barrier(self):
        self.submit(); self.broker.tick(); self.cancel(); self.broker.tick()
        self.assertEqual("UNKNOWN", self.status()["outcome"])
        self.assertTrue(self.runner.stops)
        next_request = self.make_request()
        self.assertCode("RESOURCE_BUSY", lambda: self.broker.call("lh_job_submit", next_request, self.owner))
        self.broker.tick()
        self.assertEqual(1, len(self.runner.starts))

    def test_incomplete_exited_observation_keeps_polling_original_execution(self):
        self.submit(); self.broker.tick()
        identity = self.runner.starts[0][1]
        self.runner.finish(identity, tree_exited=False)
        self.broker.tick()
        self.assertEqual("UNKNOWN", self.status()["outcome"])
        self.assertEqual(1, len(self.broker._active))
        self.runner.finish(identity)
        self.broker.tick()
        self.assertEqual("PREFLIGHT_COMPLETE", self.status()["phase"])
        self.assertFalse(self.broker._active)

    def test_unchanged_uncertainty_poll_does_not_exhaust_event_budget(self):
        self.submit(); self.broker.tick()
        self.runner.proofs[self.runner.starts[0][1]] = {"state": "UNKNOWN"}
        self.broker.tick()
        seq = self.status()["event_seq"]
        for _ in range(20):
            self.broker.tick()
        self.assertEqual(seq, self.status()["event_seq"])

    def test_revoke_and_generation_change_block_before_business(self):
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick()
        answer = self.broker.revoke("owner")
        self.assertTrue(answer["new_admission_closed"])
        self.broker.tick()
        self.assertEqual(1, len(self.runner.starts))
        self.assertCode("UNAUTHORIZED", self.status)

    def test_durable_cancel_fences_final_delayed_manager_delivery(self):
        runner = DeferredDeliverySupervisor()
        self.broker = Broker(self.db, self.policy, RegistryFixture(), runner)
        self.submit(); self.broker.tick()
        ready, release = threading.Event(), threading.Event()
        results = []
        def delayed():
            ready.set()
            if release.wait(2):
                results.append(runner.deliver(runner.starts[0][1]))
        thread = threading.Thread(target=delayed)
        thread.start()
        self.assertTrue(ready.wait(1))
        self.cancel()  # The database COMMIT precedes delivery, not merely Runner.stop.
        release.set(); thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual([None], results)
        self.assertEqual([], runner.delivered)

    def test_durable_revocation_fences_final_delivery(self):
        runner = DeferredDeliverySupervisor()
        broker = Broker(self.db, self.policy, RegistryFixture(), runner)
        broker.call("lh_job_submit", self.make_request(), self.owner); broker.tick()
        broker.revoke("owner")
        self.assertIsNone(runner.deliver(runner.starts[0][1]))
        self.assertFalse(runner.delivered)

    def test_changed_generation_fences_final_delivery(self):
        runner = DeferredDeliverySupervisor()
        broker = Broker(self.db, self.policy, RegistryFixture(), runner)
        broker.call("lh_job_submit", self.make_request(), self.owner); broker.tick()
        self.policy.generation += 1
        self.assertIsNone(runner.deliver(runner.starts[0][1]))
        self.assertFalse(runner.delivered)

    def test_final_delivery_requires_the_exact_persisted_intent(self):
        runner = DeferredDeliverySupervisor()
        self.broker = Broker(self.db, self.policy, RegistryFixture(), runner)
        self.submit(); self.broker.tick()
        self.assertIsNone(runner.deliver("invented-execution"))
        self.assertEqual([], runner.delivered)
        expected = runner.starts[0][1]
        self.assertEqual({"synthetic_manager_delivery": expected}, runner.deliver(expected))
        self.assertIsNone(runner.deliver(expected))
        self.assertEqual([expected], runner.delivered)

    def test_recovery_does_not_replay_intent(self):
        self.submit(); self.broker.tick()
        replacement = SupervisorFixture()
        second = Broker(self.db, self.policy, RegistryFixture(), replacement)
        second.recover(); second.tick()
        status = second.status(self.request["operation_id"], self.owner)
        self.assertEqual("UNKNOWN", status["outcome"])
        self.assertFalse(replacement.starts)

    def test_recovery_reattaches_original_acknowledged_manager_identity(self):
        class ReconnectingSupervisor(SupervisorFixture):
            def __init__(self):
                super().__init__()
                self.attached = []
            def reattach(self, handle, plan):
                self.attached.append((handle, plan))
                return handle
        self.submit(); self.broker.tick()
        execution = self.runner.starts[0][1]
        self.runner.proofs[execution] = {"state": "RUNNING", "recovery_handle": {
            "execution_id": execution, "manager": {"launch_acked": True, "boot_id": "synthetic-boot"}}}
        self.broker.tick()
        replacement = ReconnectingSupervisor()
        second = Broker(self.db, self.policy, RegistryFixture(), replacement)
        second.recover()
        self.assertFalse(replacement.starts)
        self.assertEqual(execution, replacement.attached[0][0]["execution_id"])
        self.assertEqual("synthetic-boot", replacement.attached[0][0]["manager"]["boot_id"])
        replacement.finish(execution)
        second.tick(); second.tick()
        self.assertFalse(replacement.starts)  # Recovered preflight never auto-runs business.
        self.assertEqual("UNKNOWN", second.status(self.request["operation_id"], self.owner)["outcome"])

    def test_cancel_before_seal_preserves_unknown_business_effects_and_lease(self):
        self.broker.evidence = SimpleNamespace(root=Path(self.temp.name) / "artifacts")
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick(); self.broker.tick()
        self.runner.finish(self.runner.starts[1][1], effects_checked=False,
            collectors_stopped=True, writers_stopped=True,
            result={"business_started": True, "side_effects": "POSSIBLY_PARTIAL",
                    "evidence_snapshot": {"root": str(Path(self.temp.name) / "raw"), "members": []}})
        self.broker.tick()
        self.assertEqual("AWAITING_SEAL", self.status()["phase"])
        self.cancel(); self.broker.tick()
        result = self.status()
        self.assertEqual("UNKNOWN", result["outcome"])
        self.assertEqual("POSSIBLY_PARTIAL", result["side_effects"])
        self.assertTrue(result["business_started"])
        self.assertEqual(2, len(self.runner.starts))
        self.assertCode("RESOURCE_BUSY", lambda: self.broker.call("lh_job_submit", self.make_request(), self.owner))

    def test_business_rechecks_frozen_registry_plan(self):
        class ChangingRegistry(RegistryFixture):
            digest = "a" * 64
            def resolve(self, *args, **kwargs):
                return dict(super().resolve(*args, **kwargs), plan_digest=self.digest)
        registry = ChangingRegistry()
        self.broker.registry = registry
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick()
        registry.digest = "b" * 64
        self.broker.tick()
        self.assertEqual("UNKNOWN", self.status()["outcome"])
        self.assertEqual(1, len(self.runner.starts))

    def test_restart_before_business_does_not_turn_old_preflight_into_new_start(self):
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick()
        replacement = SupervisorFixture()
        second = Broker(self.db, self.policy, RegistryFixture(), replacement)
        second.recover(); second.tick()
        self.assertFalse(replacement.starts)

    def test_no_reconcile_helper_over_unresolved_original_tree(self):
        self.submit(); self.broker.tick(); self.cancel(); self.broker.tick()
        identity = str(uuid.uuid4())
        self.reconcile(identity); self.broker.tick()
        self.assertEqual(1, len(self.runner.starts))
        round_status = self.broker.status(self.request["operation_id"], self.owner, identity)
        self.assertEqual("UNKNOWN", round_status["outcome"])

    def test_reconcile_stable_identity_and_targeted_cancel(self):
        self.submit(); self.cancel()
        identity = str(uuid.uuid4())
        first = self.reconcile(identity)
        self.assertEqual(first, self.reconcile(identity))
        self.cancel()  # Retrying business cancellation must not cancel the new round.
        status = self.broker.status(self.request["operation_id"], self.owner, identity)
        self.assertFalse(status["cancel_requested"])
        self.assertCode("RESOURCE_BUSY", lambda: self.reconcile(str(uuid.uuid4())))
        result = self.cancel({"kind": "reconcile", "reconcile_id": identity})
        self.assertEqual("CANCELLED", result["outcome"])
        self.broker.call("lh_job_submit", self.make_request(), self.owner)

    def test_readonly_reconcile_exit_does_not_release_unknown_business_effects(self):
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick(); self.broker.tick()
        self.runner.finish(self.runner.starts[1][1], effects_checked=False)
        self.broker.tick()
        identity = str(uuid.uuid4())
        self.reconcile(identity); self.broker.tick()
        self.runner.finish(self.runner.starts[-1][1], result={"original_outcome": "UNKNOWN"})
        self.broker.tick()
        self.assertEqual("UNKNOWN", self.status()["outcome"])
        self.assertCode("RESOURCE_BUSY", lambda: self.broker.call("lh_job_submit", self.make_request(), self.owner))

    def test_missing_cancel_is_not_a_tombstone_or_execution_proof(self):
        self.assertCode("NOT_FOUND", self.cancel)
        self.submit()
        self.assertFalse(self.status()["cancel_requested"])

    def test_retained_capacity_is_not_reclaimed_by_cancel(self):
        self.policy.limits = dict(self.policy.limits, retained_bytes=2000)
        self.submit(); self.cancel()
        self.request = self.make_request()
        self.assertCode("LIMIT_EXCEEDED", self.submit)

    def test_unacknowledged_launch_retains_global_execution_capacity(self):
        class IndependentRegistry(RegistryFixture):
            def resolve(self, request, policy, **kwargs):
                return dict(super().resolve(request, policy, **kwargs),
                            resource_ids=[request["operation_id"]])
        class LostAcknowledgement(SupervisorFixture):
            def start(self, *args):
                super().start(*args)
                raise OSError("synthetic receipt loss after launch delivery")
        self.policy.limits = dict(self.policy.limits, max_running=1)
        runner = LostAcknowledgement()
        self.broker = Broker(self.db, self.policy, IndependentRegistry(), runner)
        self.submit(); self.broker.tick()
        self.assertEqual("UNKNOWN", self.status()["outcome"])
        self.assertFalse(self.broker._active)
        following = self.make_request()
        self.broker.call("lh_job_submit", following, self.owner)
        self.broker.tick()
        self.assertEqual(1, len(runner.starts),
                         "an unresolved durable launch still consumes the global execution budget")
        self.assertEqual("QUEUED", self.broker.status(following["operation_id"], self.owner)["phase"])

    def test_failed_recovery_attachment_retains_global_execution_capacity(self):
        class IndependentRegistry(RegistryFixture):
            def resolve(self, request, policy, **kwargs):
                return dict(super().resolve(request, policy, **kwargs),
                            resource_ids=[request["operation_id"]])
        class FailedAttachment(SupervisorFixture):
            def reattach(self, handle, plan):
                raise OSError("synthetic temporary manager lookup failure")
        self.policy.limits = dict(self.policy.limits, max_running=1)
        registry = IndependentRegistry()
        self.broker = Broker(self.db, self.policy, registry, self.runner)
        self.submit(); self.broker.tick()
        replacement = FailedAttachment()
        recovered = Broker(self.db, self.policy, registry, replacement)
        recovered.recover()
        self.assertFalse(recovered._active)
        following = self.make_request()
        recovered.call("lh_job_submit", following, self.owner)
        recovered.tick()
        self.assertFalse(replacement.starts,
                         "an unobserved pre-crash process must not free its global execution slot")
        self.assertEqual("QUEUED", recovered.status(following["operation_id"], self.owner)["phase"])
        # Reattaching and independently proving the old tree's exit releases
        # the concurrency slot, without replaying the original business job.
        replacement.reattach = lambda handle, plan: handle
        replacement.finish(self.runner.starts[0][1])
        recovered.recover(); recovered.tick()
        self.assertEqual([following["operation_id"]], [item[0] for item in replacement.starts])
        self.assertEqual("UNKNOWN", recovered.status(self.request["operation_id"], self.owner)["outcome"])

    def test_unhealthy_db_cannot_report_missing(self):
        self.db.healthy = False
        self.assertCode("IO_UNCERTAIN", self.status)

    def test_immutable_identity_and_events(self):
        self.submit()
        self.assertCode("IO_UNCERTAIN", lambda: self._delete())

    def test_terminal_cancel_does_not_refresh_sealed_observation_after_restart(self):
        registry = CatalogFixture()
        self.broker.registry = registry
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick(); self.broker.tick()
        self.runner.finish(self.runner.starts[1][1]); self.broker.tick()
        self.broker.register_seal({"operation_id": self.request["operation_id"],
            "seal_id": "synthetic-seal", "seal_sha256": "a" * 64,
            "event_seq": self.status()["event_seq"], "complete": True})
        before = copy.deepcopy(registry.observations[self.request["operation_id"]])
        with mock.patch("local_hand_jobs.state.time.time", return_value=before["observed_at"] + 7200):
            self.cancel()
        restored = CatalogFixture()
        Broker(self.db, self.policy, restored, SupervisorFixture())
        after = restored.observations[self.request["operation_id"]]
        self.assertEqual(before["observed_at"], after["observed_at"], "cancel is not a fresh storage observation")
        self.assertEqual(before["event_seq"], after["event_seq"], "old PASS must not outrank a later failed run")
        self.assertEqual("SEALED", after["evidence_state"])

    def test_retired_profile_does_not_block_restore_of_historical_prepared_evidence(self):
        self.submit()
        with self.db.transaction() as tx:
            self.db.update(tx, "job", self.request["operation_id"], "EVIDENCE_SEALED", {
                "lifecycle": "TERMINAL", "phase": "EXITED", "outcome": "SUCCEEDED", "evidence": "SEALED",
                "prepared_facts": {"prepared_ref": "synthetic-prepared", "owner": "owner",
                    "profile_ref": "retired", "expected": self.request["expected"]}})
        class CurrentPolicy(PolicyFixture):
            def expected(self, profile):
                if profile == "retired":
                    raise JobError("UNAUTHORIZED", "Profile was removed")
                return super().expected(profile)
            def register_prepared_reference(self, *args, **kwargs):
                raise AssertionError("Retired prepared output must not enter current discovery")
        registry = CatalogFixture()
        restored = Broker(self.db, CurrentPolicy(), registry, SupervisorFixture())
        self.assertIn("synthetic-prepared", registry.prepared)
        self.assertEqual("SUCCEEDED", restored.status(self.request["operation_id"], self.owner)["outcome"])

    def test_launch_ack_storage_failure_keeps_accepted_handle_for_controlled_stop(self):
        self.submit()
        update = self.db.update
        def fail_ack(tx, namespace, identity, event, changes):
            if event == "LAUNCH_ENQUEUED":
                raise sqlite3.OperationalError("synthetic disk full while persisting launch acknowledgement")
            return update(tx, namespace, identity, event, changes)
        with mock.patch.object(self.db, "update", side_effect=fail_ack):
            self.assertCode("IO_UNCERTAIN", lambda: self.broker._start("job", self.request["operation_id"], "preflight"))
        self.assertFalse(self.db.healthy)
        self.assertEqual(1, len(self.runner.starts))
        self.assertIn(("job", self.request["operation_id"]), self.broker._active,
                      "DB failure must not lose the newly accepted supervisor handle")

    def test_new_reconcile_requires_current_request_grant_but_retry_preserves_identity(self):
        self.submit(); self.cancel()
        identity = str(uuid.uuid4())
        original = self.reconcile(identity)
        authorized = self.policy.authorize
        def grant_removed(principal, scope, request=None, owner=None):
            authorized(principal, scope, request=request, owner=owner)
            if request is not None:
                raise JobError("UNAUTHORIZED", "Synthetic profile grant was removed")
        self.policy.authorize = grant_removed
        self.assertEqual(original, self.reconcile(identity))
        self.cancel({"kind": "reconcile", "reconcile_id": identity})
        new_identity = str(uuid.uuid4())
        self.assertCode("UNAUTHORIZED", lambda: self.reconcile(new_identity))
        self.assertIsNone(self.db.get("reconcile", new_identity))
        with self.db.transaction() as tx:
            self.assertEqual(0, tx.execute("SELECT count(*) FROM leases").fetchone()[0])

    def test_committed_but_lost_admission_ack_preserves_id_capacity_and_barrier(self):
        connection = self.db._db
        class LostCommitReceipt:
            def __getattr__(self, name):
                return getattr(connection, name)
            def execute(self, sql, *args):
                result = connection.execute(sql, *args)
                if sql == "COMMIT" and connection.execute("SELECT count(*) FROM operations").fetchone()[0]:
                    raise sqlite3.OperationalError("synthetic lost receipt after durable commit")
                return result
        self.db._db = LostCommitReceipt()
        self.assertCode("IO_UNCERTAIN", self.submit)
        self.assertFalse(self.db.healthy)
        self.assertFalse(self.runner.starts)
        reopened = StateStore(self.db.path, "authority", "ledger")
        self.addCleanup(reopened.close)
        restored = Broker(reopened, self.policy, RegistryFixture(), SupervisorFixture())
        self.policy.generation += 1
        self.policy.limits = dict(self.policy.limits, retained_bytes=2000)
        with mock.patch("local_hand_jobs.broker.time.time", return_value=self.request["expires_at"] + 1):
            result = restored.call("lh_job_submit", self.request, self.owner)
        self.assertEqual(self.request["operation_id"], result["operation_id"])
        with reopened.transaction() as tx:
            self.assertEqual(1, tx.execute("SELECT count(*) FROM operations").fetchone()[0])
            self.assertEqual(1000, tx.execute("SELECT sum(reserved_bytes) FROM operations").fetchone()[0])
            self.assertEqual(1, tx.execute("SELECT count(*) FROM leases").fetchone()[0])

    def test_authoritative_seal_list_includes_rounds_and_keeps_missing_registration_distinct(self):
        self.submit(); self.cancel()
        identity = str(uuid.uuid4())
        self.reconcile(identity)
        job_seal = {"seal_id": str(uuid.uuid4()), "seal_sha256": "a" * 64}
        round_seal = {"seal_id": str(uuid.uuid4()), "seal_sha256": "b" * 64}
        with self.db.transaction() as tx:
            self.db.update(tx, "job", self.request["operation_id"], "SYNTHETIC_REGISTRATION", {"seals": [job_seal]})
            self.db.update(tx, "reconcile", identity, "SYNTHETIC_REGISTRATION", {"seals": [round_seal]})
        self.assertEqual([job_seal, round_seal], self.broker.list_seals(self.request["operation_id"]))
        self.assertCode("NOT_FOUND", lambda: self.broker.list_seals(str(uuid.uuid4())))
        self.db.healthy = False
        self.assertCode("IO_UNCERTAIN", lambda: self.broker.list_seals(self.request["operation_id"]))

    def test_evidence_completion_cannot_register_a_foreign_operation_publication(self):
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick(); self.broker.tick()
        self.runner.finish(self.runner.starts[1][1]); self.broker.tick()
        foreign_operation = self.request["operation_id"]
        foreign_event = self.status()["event_seq"]
        self.request = self.make_request()
        self.broker.evidence = SimpleNamespace(root=Path(self.temp.name) / "artifacts")
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[2][1]); self.broker.tick(); self.broker.tick()
        self.runner.finish(self.runner.starts[3][1], collectors_stopped=True, writers_stopped=True,
            result={"evidence_snapshot": {"root": str(Path(self.temp.name) / "raw"), "members": []}})
        self.broker.tick(); self.broker.tick()
        self.runner.finish(self.runner.starts[4][1], collectors_stopped=True, writers_stopped=True,
            result={"seal_record": {"operation_id": foreign_operation, "seal_id": str(uuid.uuid4()),
                                  "seal_sha256": "a" * 64, "event_seq": foreign_event, "complete": True}})
        self.broker.tick()
        self.assertEqual("STAGING", self.broker.status(foreign_operation, self.owner)["evidence"])
        self.assertEqual("DURABILITY_UNKNOWN", self.status()["evidence"])
        self.assertFalse(self.broker.list_seals(foreign_operation))
        self.assertEqual(True, self.status()["exit_proof"]["tree_exited"])

    def test_unknown_business_cannot_use_old_preflight_exit_to_start_reconcile(self):
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick(); self.broker.tick()
        execution = self.runner.starts[1][1]
        self.runner.proofs[execution] = {"state": "UNKNOWN"}
        self.broker.tick()
        identity = str(uuid.uuid4())
        self.reconcile(identity); self.broker.tick()
        self.assertEqual(2, len(self.runner.starts), "prior preflight exit cannot prove business exit")
        self.assertIsNone(self.status()["exit_proof"])
        self.assertEqual("UNKNOWN", self.broker.status(self.request["operation_id"], self.owner, identity)["outcome"])

    def test_unknown_evidence_helper_cannot_use_old_business_exit_to_start_reconcile(self):
        self.broker.evidence = SimpleNamespace(root=Path(self.temp.name) / "artifacts")
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick(); self.broker.tick()
        self.runner.finish(self.runner.starts[1][1], collectors_stopped=True, writers_stopped=True,
            result={"evidence_snapshot": {"root": str(Path(self.temp.name) / "raw"), "members": []}})
        self.broker.tick(); self.broker.tick()
        self.runner.proofs[self.runner.starts[2][1]] = {"state": "UNKNOWN"}
        self.broker.tick()
        identity = str(uuid.uuid4())
        self.reconcile(identity); self.broker.tick()
        self.assertEqual(3, len(self.runner.starts), "business exit cannot prove evidence helper exit")
        self.assertIsNone(self.status()["exit_proof"])
        self.assertEqual("UNKNOWN", self.broker.status(self.request["operation_id"], self.owner, identity)["outcome"])

    def test_recovery_invalidates_legacy_previous_phase_exit_proof(self):
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick(); self.broker.tick()
        # Existing d500384 ledgers retained the previous phase's proof here.
        with self.db.transaction() as tx:
            self.db.update(tx, "job", self.request["operation_id"], "SYNTHETIC_LEGACY_STATE", {
                "exit_proof": {"future_start_blocked": True, "tree_exited": True, "effects_checked": True}})
        replacement = SupervisorFixture()
        restored = Broker(self.db, self.policy, RegistryFixture(), replacement)
        restored.recover()
        identity = str(uuid.uuid4())
        restored.reconcile(self.request["operation_id"], self.request["request_digest"], identity, self.owner)
        restored.tick()
        self.assertFalse(replacement.starts)
        self.assertIsNone(restored.status(self.request["operation_id"], self.owner)["exit_proof"])

    def test_recovery_preserves_confirmed_business_outcome_across_seal_states(self):
        for phase in ("AWAITING_SEAL", "EVIDENCE", "EXITED"):
            for outcome, exit_code in (("SUCCEEDED", 0), ("FAILED", 1), ("UNKNOWN", 0)):
                with self.subTest(phase=phase, outcome=outcome), ExitStack() as cleanup:
                    folder = cleanup.enter_context(tempfile.TemporaryDirectory())
                    state = StateStore(Path(folder) / "ledger.sqlite", "authority", "ledger", initialize=True)
                    cleanup.callback(state.close)
                    runner = SupervisorFixture()
                    evidence = SimpleNamespace(root=Path(folder) / "artifacts")
                    broker = Broker(state, self.policy, RegistryFixture(), runner, evidence)
                    request = self.make_request()
                    broker.submit(request, self.owner); broker.tick()
                    runner.finish(runner.starts[0][1]); broker.tick(); broker.tick()
                    runner.finish(runner.starts[1][1], exit_code=exit_code,
                        effects_checked=outcome != "UNKNOWN",
                        collectors_stopped=True, writers_stopped=True,
                        result={"business_started": True,
                                "evidence_snapshot": {"root": str(Path(folder) / "raw"), "members": []}})
                    broker.tick()
                    if phase != "AWAITING_SEAL":
                        broker.tick()
                    if phase == "EXITED":
                        runner.finish(runner.starts[-1][1], exit_code=1,
                                      collectors_stopped=True, writers_stopped=True)
                        broker.tick()
                    before = broker.status(request["operation_id"], self.owner)
                    self.assertEqual(outcome, before["outcome"])
                    self.assertEqual(phase, before["phase"])
                    replacement = SupervisorFixture()  # No recovery attachment proof.
                    restored = Broker(state, self.policy, RegistryFixture(), replacement, evidence)
                    restored.recover()
                    after = restored.status(request["operation_id"], self.owner)
                    self.assertEqual(outcome, after["outcome"],
                                     "lost seal supervision must not erase a durable business result")
                    self.assertEqual(phase, after["phase"])
                    self.assertEqual("RECONCILE_REQUIRED", after["lifecycle"])
                    self.assertEqual({}, after["outputs"])
                    self.assertFalse(replacement.starts)
                    if phase in ("EVIDENCE", "EXITED"):
                        self.assertEqual("DURABILITY_UNKNOWN", after["evidence"])
                    self.assertEqual(2 if phase == "AWAITING_SEAL" else 3, len(runner.starts))
                    if phase == "EVIDENCE":
                        self.assertIsNone(after["exit_proof"], "a business proof cannot prove helper exit")
                    restored.recover()
                    self.assertEqual(outcome, restored.status(request["operation_id"], self.owner)["outcome"])
                    self.assertCode("RESOURCE_BUSY", lambda: restored.submit(self.make_request(), self.owner))
                    if phase == "AWAITING_SEAL":
                        self.policy.generation += 1
                        restored.tick()  # Current admission rejects the new evidence helper.
                        rejected = restored.status(request["operation_id"], self.owner)
                        self.assertEqual(outcome, rejected["outcome"])
                        self.assertEqual("STAGING", rejected["evidence"])
                        self.assertEqual("AWAITING_SEAL", rejected["phase"])
                        self.assertFalse(replacement.starts)

    def _queue_round_before_late_preflight_exit(self):
        self.submit(); self.broker.tick()
        execution = self.runner.starts[0][1]
        self.runner.proofs[execution] = {"state": "UNKNOWN"}
        self.broker.tick()
        self.assertEqual("RECONCILE_REQUIRED", self.status()["lifecycle"])
        identity = str(uuid.uuid4())
        self.reconcile(identity)
        self.runner.finish(execution)
        return identity

    def test_late_preflight_serializes_admitted_round_until_business_exit(self):
        identity = self._queue_round_before_late_preflight_exit()
        self.broker.tick()
        after_preflight = self.status()
        self.broker.tick()
        self.assertEqual(["preflight", "business"], [item[2]["phase"] for item in self.runner.starts],
                         "reconciliation must wait until the resumed business becomes quiescent")
        self.assertEqual("RUNNING", after_preflight["lifecycle"])
        self.assertEqual("QUEUED", self.broker.status(self.request["operation_id"], self.owner, identity)["phase"])
        self.runner.finish(self.runner.starts[-1][1]); self.broker.tick()
        self.assertEqual("SUCCEEDED", self.status()["outcome"])
        self.assertEqual("reconcile", self.runner.starts[-1][2]["phase"])

    def test_cancel_round_after_late_preflight_keeps_pending_business_lease(self):
        identity = self._queue_round_before_late_preflight_exit()
        complete = self.broker._complete
        def cancel_after_preflight(namespace, operation, proof):
            complete(namespace, operation, proof)
            if namespace == "job":
                # The API request arrives after late proof COMMIT and before
                # the coordinator next visits the queued reconciliation.
                self.cancel({"kind": "reconcile", "reconcile_id": identity})
        with mock.patch.object(self.broker, "_complete", side_effect=cancel_after_preflight):
            self.broker.tick()
        with self.db.transaction() as tx:
            self.assertEqual(1, tx.execute("SELECT count(*) FROM leases").fetchone()[0],
                             "a queued round cannot release the resumed parent's resource")
        self.assertCode("RESOURCE_BUSY", lambda: self.broker.submit(self.make_request(), self.owner))
        self.broker.tick()
        self.assertEqual(["preflight", "business"], [item[2]["phase"] for item in self.runner.starts])

    def _queue_round_before_late_business_exit(self, *, snapshot=False):
        if snapshot:
            self.broker.evidence = SimpleNamespace(root=Path(self.temp.name) / "artifacts")
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick(); self.broker.tick()
        execution = self.runner.starts[1][1]
        self.runner.proofs[execution] = {"state": "UNKNOWN"}
        self.broker.tick()
        identity = str(uuid.uuid4())
        self.reconcile(identity)
        result = {"evidence_snapshot": {"root": str(Path(self.temp.name) / "raw"), "members": []}} if snapshot else {}
        self.runner.finish(execution, collectors_stopped=True, writers_stopped=True, result=result)
        return identity

    def test_late_business_exit_keeps_already_admitted_round_lease(self):
        identity = self._queue_round_before_late_business_exit()
        self.broker.tick()
        self.assertEqual("SUCCEEDED", self.status()["outcome"])
        round_status = self.broker.status(self.request["operation_id"], self.owner, identity)
        self.assertEqual("RUNNING", round_status["lifecycle"],
                         "late parent completion must preserve the admitted round's reservation")
        self.assertEqual("reconcile", self.runner.starts[-1][2]["phase"])
        self.assertCode("RESOURCE_BUSY", lambda: self.broker.call("lh_job_submit", self.make_request(), self.owner))
        self.runner.finish(self.runner.starts[-1][1]); self.broker.tick()
        self.broker.call("lh_job_submit", self.make_request(), self.owner)

    def test_late_business_sealing_serializes_already_admitted_round(self):
        identity = self._queue_round_before_late_business_exit(snapshot=True)
        self.broker.tick()
        self.assertEqual("AWAITING_SEAL", self.status()["phase"])
        self.assertEqual("QUEUED", self.broker.status(self.request["operation_id"], self.owner, identity)["phase"],
                         "the late parent's evidence still owns the shared execution boundary")
        self.broker.tick()
        self.assertEqual(["preflight", "business", "evidence"], [start[2]["phase"] for start in self.runner.starts])
        frozen = self.runner.starts[-1][2]["evidence_snapshot"]
        self.runner.finish(self.runner.starts[-1][1], collectors_stopped=True, writers_stopped=True,
            result={"seal_record": {"operation_id": self.request["operation_id"], "seal_id": str(uuid.uuid4()),
                "seal_sha256": "a" * 64, "event_seq": frozen["event_seq"],
                "bindings": frozen["bindings"], "complete": True}})
        self.broker.tick()
        self.assertEqual("SEALED", self.status()["evidence"])
        self.assertEqual("reconcile", self.runner.starts[-1][2]["phase"])
        self.assertCode("RESOURCE_BUSY", lambda: self.broker.call("lh_job_submit", self.make_request(), self.owner))

    def test_cancel_admitted_round_during_late_parent_sealing_keeps_parent_lease(self):
        identity = self._queue_round_before_late_business_exit(snapshot=True)
        complete = self.broker._complete
        def cancel_after_parent_exit(namespace, operation, proof):
            complete(namespace, operation, proof)
            if namespace == "job":
                # Deterministic API interleaving after the parent's completion
                # transaction and before the coordinator reaches the queued round.
                self.cancel({"kind": "reconcile", "reconcile_id": identity})
        with mock.patch.object(self.broker, "_complete", side_effect=cancel_after_parent_exit):
            self.broker.tick()
        self.assertEqual("AWAITING_SEAL", self.status()["phase"])
        self.assertEqual("CANCELLED", self.broker.status(self.request["operation_id"], self.owner, identity)["outcome"])
        self.assertCode("RESOURCE_BUSY", lambda: self.broker.call("lh_job_submit", self.make_request(), self.owner))

    def test_verified_business_result_survives_helper_failure_and_late_cancel(self):
        for outcome, helper_exit, cancel in (("SUCCEEDED", 1, False), ("FAILED", 0, False),
                                              ("SUCCEEDED", 1, True), ("SUCCEEDED", 0, True)):
            with self.subTest(outcome=outcome, helper_exit=helper_exit, cancel=cancel), ExitStack() as cleanup:
                folder = cleanup.enter_context(tempfile.TemporaryDirectory())
                state = StateStore(Path(folder) / "ledger.sqlite", "authority", "ledger", initialize=True)
                cleanup.callback(state.close)
                runner = SupervisorFixture()
                broker = Broker(state, self.policy, RegistryFixture(), runner,
                                SimpleNamespace(root=Path(folder) / "artifacts"))
                request = self.make_request()
                broker.submit(request, self.owner); broker.tick()
                runner.finish(runner.starts[0][1]); broker.tick(); broker.tick()
                execution = runner.starts[1][1]
                runner.finish(execution, exit_code=helper_exit, helper_result_verified=True,
                    collectors_stopped=True, writers_stopped=True,
                    result={"execution_id": execution, "outcome": outcome, "business_started": True,
                            "evidence_snapshot": {"root": str(Path(folder) / "raw"), "members": []}})
                if cancel:
                    broker.cancel(request["operation_id"], request["request_digest"], {"kind": "job"}, self.owner)
                broker.tick()
                status = broker.status(request["operation_id"], self.owner)
                self.assertEqual(outcome, status["outcome"], "a helper exit or later stop request cannot rewrite a verified business result")
                self.assertEqual(helper_exit, status["exit_proof"]["exit_code"])
                self.assertEqual(cancel, status["cancel_requested"])
                self.assertEqual("EXITED" if cancel else "AWAITING_SEAL", status["phase"])
                if helper_exit != (0 if outcome == "SUCCEEDED" else 1):
                    self.assertEqual("DURABILITY_UNKNOWN", status["evidence"])
                    self.assertTrue(status["gaps"])
                self.assertEqual(2, len(runner.starts), "observation cannot replay the business")
                if not cancel:
                    broker.tick()
                    self.assertEqual("evidence", runner.starts[-1][2]["phase"])
                    frozen = runner.starts[-1][2]["evidence_snapshot"]
                    runner.finish(runner.starts[-1][1], collectors_stopped=True, writers_stopped=True,
                        result={"seal_record": {"operation_id": request["operation_id"], "seal_id": str(uuid.uuid4()),
                            "seal_sha256": "a" * 64, "event_seq": frozen["event_seq"],
                            "bindings": frozen["bindings"], "complete": True}})
                    broker.tick()
                    sealed = broker.status(request["operation_id"], self.owner)
                    self.assertEqual(outcome, sealed["outcome"])
                    self.assertEqual("SEALED", sealed["evidence"])
                    self.assertFalse(sealed["gaps"], "a confirmed seal resolves this publication gap")
                    self.assertEqual(helper_exit, state.get("job", request["operation_id"])["record"]["business_exit_proof"]["exit_code"])

    def test_verified_reconcile_result_is_separate_from_helper_and_parent(self):
        self.broker.evidence = SimpleNamespace(root=Path(self.temp.name) / "artifacts")
        self.submit(); self.cancel()
        identity = str(uuid.uuid4())
        self.reconcile(identity); self.broker.tick()
        execution = self.runner.starts[0][1]
        self.runner.finish(execution, exit_code=1, helper_result_verified=True,
            collectors_stopped=True, writers_stopped=True,
            result={"execution_id": execution, "outcome": "SUCCEEDED",
                    "evidence_snapshot": {"root": str(Path(self.temp.name) / "raw"), "members": []}})
        self.broker.tick()
        status = self.broker.status(self.request["operation_id"], self.owner, identity)
        self.assertEqual("SUCCEEDED", status["outcome"])
        self.assertEqual("DURABILITY_UNKNOWN", status["evidence"])
        self.assertEqual("CANCELLED", self.status()["outcome"])
        self.assertCode("RESOURCE_BUSY", lambda: self.broker.submit(self.make_request(), self.owner))

    def test_verified_result_needs_exact_binding_and_checked_effects(self):
        cases = (("foreign", "SUCCEEDED", True), (None, "SUCCEEDED", True),
                 ("same", "INVALID", True), ("same", "UNKNOWN", True),
                 ("same", "SUCCEEDED", False))
        for binding, outcome, checked in cases:
            with self.subTest(binding=binding, outcome=outcome, checked=checked), ExitStack() as cleanup:
                folder = cleanup.enter_context(tempfile.TemporaryDirectory())
                state = StateStore(Path(folder) / "ledger.sqlite", "authority", "ledger", initialize=True)
                cleanup.callback(state.close)
                runner = SupervisorFixture()
                broker = Broker(state, self.policy, RegistryFixture(), runner)
                request = self.make_request()
                broker.submit(request, self.owner); broker.tick()
                runner.finish(runner.starts[0][1]); broker.tick(); broker.tick()
                execution = runner.starts[1][1]
                result = {"outcome": outcome}
                if binding is not None:
                    result["execution_id"] = execution if binding == "same" else "another-execution"
                runner.finish(execution, helper_result_verified=True, effects_checked=checked, result=result)
                broker.tick()
                status = broker.status(request["operation_id"], self.owner)
                self.assertEqual("UNKNOWN", status["outcome"])
                self.assertEqual("RECONCILE_REQUIRED", status["lifecycle"])
                self.assertCode("RESOURCE_BUSY", lambda: broker.submit(self.make_request(), self.owner))
                self.assertEqual(2, len(runner.starts))

    def test_unverified_result_does_not_override_failed_helper_exit(self):
        self.submit(); self.broker.tick()
        self.runner.finish(self.runner.starts[0][1]); self.broker.tick(); self.broker.tick()
        execution = self.runner.starts[1][1]
        self.runner.finish(execution, exit_code=1,
                           result={"execution_id": execution, "outcome": "SUCCEEDED"})
        self.broker.tick()
        self.assertEqual("FAILED", self.status()["outcome"])

    def _delete(self):
        with self.db.transaction() as tx:
            tx.execute("DELETE FROM operations")


if __name__ == "__main__":
    unittest.main()
