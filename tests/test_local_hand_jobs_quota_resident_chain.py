"""Real SQLite three-phase chain; all systemd, quota and seal facts are modeled.

These tests exercise persisted original authority and bounded payloads. They do
not execute a host fixture or establish Q3/production support.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

from local_hand_jobs import budget, quota_bridge, quota_closure, quota_contract, quota_grant
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError
from q2_fixtures import BOOT, SECOND, capacity, encoded, grant_data
from test_e3_quota_q2_closure import complete
from test_local_hand_jobs_quota_binding import Registry, observed
import test_local_hand_jobs_broker as fixtures

PATH = Path(__file__).parent / "e3_host" / "q2_resident.py"
SPEC = importlib.util.spec_from_file_location("resident_chain_fixture_entry", PATH)
resident = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resident)


class ChainRegistry(Registry):
    def resolve(self, request, policy, *, principal=None):
        plan = super().resolve(request, policy, principal=principal)
        plan["budgets"].update(memory_bytes=32*1024**2, processes=16, log_bytes=96*1024)
        plan["execution"].update(python="/usr/bin/python3", kind="host.inspect",
            operation_id=request["operation_id"], readonly=[], storage={}, stages=[])
        return plan


class ResidentChainTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.BrokerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.now = 100 * SECOND
        patch = self.clock_patch = mock.patch.object(budget, "current_clock", side_effect=lambda: {
            "boot_id": BOOT, "boottime_ns": self.now})
        patch.start()
        self.addCleanup(patch.stop)
        self.runner = fixtures.DeferredDeliverySupervisor()
        self.f.policy.limits = dict(self.f.policy.limits, retained_bytes=1024**3)
        profile = copy.deepcopy(self.f.policy.profiles["fixture"])
        profile["bootstrap_slots"] = [{"slot_id": "quota-slot-" + str(n), "roots": {
            role: {"path": f"/synthetic/slot-{n}/{role}", "device": 7,
                   "inode": 101 + n*10 + i, "uid": 1234}
            for i, role in enumerate(("work", "evidence", "temporary"))}} for n in range(2)]
        profile["bootstrap_evidence_store"] = dict(path="/synthetic/retained", device=7, inode=141, uid=1234)
        self.f.policy.profiles = {"fixture": profile}
        self.f.policy.config = {"process_manager": {"cgroup": "/sys/fs/cgroup/synthetic-job.slice"}}
        self.broker = Broker(self.f.db, self.f.policy, ChainRegistry(), self.runner,
            evidence=SimpleNamespace(root=Path("/synthetic/retained")), quota_required=True)
        self.broker.submit(self.f.request, self.f.owner)
        self.identity = self.f.request["operation_id"]
        self.chain = resident.Chain(self.broker, self.identity, self.row()["plan"])
        self.grants = {}
        self.declarations = {}
        self.capacity = capacity()
        for domain in self.capacity["domains"]:
            if domain["project_id"] in (1002, 1012):
                domain["hard_bytes"] = 1024**2

    def row(self):
        return self.f.db.get("job", self.identity)

    def prepare(self, phase):
        self.broker._start("job", self.identity, phase)
        snapshot = quota_bridge.Phase(self.broker, "job", self.identity, phase).snapshot()
        declaration = self.chain.declaration(phase, snapshot)
        self.declarations[phase] = declaration
        return snapshot["preparation"]

    def pending(self, phase, *, stages=None):
        prepared = self.prepare(phase)
        grant = self.make_grant(phase, prepared)
        self.grants[phase] = grant
        self.broker.bind_observation("job", self.identity, phase, grant.wire)
        self.broker._start("job", self.identity, phase)
        execution = grant.request.as_dict()["execution_id"]
        self.assertTrue(self.broker._guard_start(execution, lambda: True, stage="bootstrap"))
        self.now += SECOND
        bootstrap_proof = dict(execution_id=execution,
            unit="lhj-" + hashlib.sha256((execution + ":bootstrap").encode()).hexdigest() + ".service",
            state="EXITED", exit_code=0,
            **dict.fromkeys(("future_start_blocked", "tree_exited", "collectors_stopped", "writers_stopped", "effects_checked"), True),
            result=dict(bootstrap_prepared=True, quota_observation=observed(grant)))
        self.assertTrue(self.broker._guard_start(execution, lambda: True, stage="helper", bootstrap_proof=bootstrap_proof))
        unit = "lhj-" + hashlib.sha256(execution.encode()).hexdigest() + ".service"
        helper_proof = dict(bootstrap_proof, unit=unit, identity=dict(
            cgroup="/synthetic-job.slice/" + unit, boot_id=BOOT, invocation_id="e"*32))
        self.assertTrue(self.broker._guard_start(execution, lambda: True, stage="result_reader", helper_proof=helper_proof))
        self.now += SECOND
        fence, proof, _, _ = complete(grant, observation=observed(grant)["receipt"])
        if phase == "business":
            proof["result"]["evidence_snapshot"] = {"root": prepared["allocation"]["roots"]["evidence"]}
        elif phase == "evidence":
            frozen = self.row()["record"]["frozen_snapshot"]
            proof["result"]["seal_record"] = dict(complete=True, operation_id=self.identity,
                reconcile_id=None, event_seq=frozen["event_seq"], bindings=frozen["bindings"], seal_id="modeled-seal")
        if stages is not None:
            proof["result"]["stages"] = stages
        fence["ordinary_digest"] = quota_closure.digest(proof)
        fence["proof_digest"] = quota_closure.digest({key: value for key, value in fence.items() if key != "proof_digest"})
        self.runner.proofs[execution] = proof
        self.broker.tick()  # Actual coordinator consumes the modeled OS exit proof.
        self.assertNotIn(("job", self.identity), self.broker._active)
        return fence, proof

    def close(self, phase):
        fence, proof = self.pending(phase)
        self.broker.close_observation("job", self.identity, phase, fence)
        closed = self.row()["record"]["quota_closed"][phase]
        self.chain.retain_closure(phase, closed)
        return closed

    def make_grant(self, phase, prepared):
        data = grant_data(number=len(self.grants) + 1, phase=phase, declared_capacity=self.capacity,
            allocation=prepared["allocation"], phase_budget=prepared["budget"], issued=self.now,
            predecessors=[item.request.as_dict()["request_id"] for item in self.grants.values()], offset=10 if phase == "evidence" else 0)
        for root in data["roots"]:
            if root["role"] == "evidence":
                root["hard_bytes"] = 1024**2
        return quota_grant.decode_grant(encoded(data))

    def advance(self, previous, following, *, command=None):
        if command is None:
            command = dict(action="advance", value={"from": previous, "to": following,
                "closure_digest": quota_closure.digest(self.chain.closed[previous])})
        channel = mock.Mock(receive=lambda: command)
        self.chain.advance(channel, previous, following)
        channel.advance_phase.assert_called_once_with(following)
        return channel

    def test_three_phases_keep_original_operation_budget_session_and_deliver_once(self):
        for index, phase in enumerate(resident.CHAIN_PHASES):
            self.close(phase)
            if index < 2:
                self.advance(phase, resident.CHAIN_PHASES[index+1])
        self.chain.complete()
        self.assertEqual("SEALED", self.row()["record"]["evidence"])
        self.assertEqual(3, len(self.runner.starts))
        original = self.chain.preparations["preflight"]
        for phase, prepared in self.chain.preparations.items():
            self.assertEqual(self.broker._quota_session, prepared["session"])
            for key in ("operation_id", "budget_digest", "started_boottime_ns", "deadline_boottime_ns"):
                self.assertEqual(original["budget"][key], prepared["budget"][key])
            self.assertEqual(f"job-{self.identity}-{phase}", prepared["budget"]["execution_id"])
        for key in ("wall_seconds", "cpu_seconds", "log_bytes"):
            self.assertLessEqual(sum(prepared["budget"]["limits"][key] for prepared in self.chain.preparations.values()),
                                 self.row()["plan"]["budgets"][key])
        self.assertEqual(original["allocation"]["allocation_id"], self.chain.preparations["business"]["allocation"]["allocation_id"])
        self.assertNotEqual(original["allocation"]["allocation_id"], self.chain.preparations["evidence"]["allocation"]["allocation_id"])
        self.assertEqual({f"job-{self.identity}-{phase}:{stage}" for phase in resident.CHAIN_PHASES
                         for stage in ("bootstrap", "helper", "result_reader")},
                         set(self.row()["record"]["delivery_intents"]))
        events = self.f.db.events("job", self.identity)
        for kind, expected in (("QUOTA_PREPARATION", 3), ("EXECUTION_INTENT", 3),
                               ("MANAGER_DELIVERY_INTENT", 9), ("QUOTA_PHASE_CLOSED", 3)):
            self.assertEqual(expected, sum(event["kind"] == kind for event in events))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux fixed runner argv")
    def test_evidence_payload_measurement_uses_actual_frozen_sqlite_history(self):
        from local_hand_jobs import bootstrap, quota_payload, runner
        self.close("preflight")
        self.advance("preflight", "business")
        self.close("business")
        self.advance("business", "evidence")
        prepared = self.prepare("evidence")
        frozen = self.row()["record"]["frozen_snapshot"]
        self.assertGreater(len(encoded(frozen)), 65536)
        plan = quota_payload.decode_phase_plan(self.declarations["evidence"])
        self.assertEqual(frozen, plan["evidence_snapshot"])
        self.assertTrue(any(type(event["observed_at"]) is float for event in frozen["broker_events"]))
        grant = self.make_grant("evidence", prepared)
        plan["quota_observation_grant"] = grant.as_dict()
        execution = runner._quota_prepared_execution(plan, parent_mount_namespace="mnt:[123]", now_ns=self.now)
        argv = runner.quota_bootstrap_argv(execution, grant, now_ns=self.now)
        payload = bootstrap.decode_payload(argv[-1])
        self.assertEqual(execution, payload["execution"])
        self.assertEqual(frozen, payload["execution"]["evidence_snapshot"])
        self.assertGreater(len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()), 128*1024)
        self.assertLess(len(argv[-1]), bootstrap.MAX_ENCODED_BYTES)
        bootstrap.check_argv(argv, {})
        self.assertEqual(2, len(self.runner.starts))

    @unittest.skipUnless(sys.platform.startswith("linux") and hasattr(os, "pidfd_open"),
                         "Linux actual capture and credentialed bridge")
    def test_actual_capture_elapsed_time_survives_sqlite_and_authenticated_v2_bridge(self):
        from local_hand_jobs import runner
        directory = Path(self.f.temp.name)
        stage = dict(name="actual-bounded-stage", argv=[sys.executable, "-I", "-B", "-c",
            "import sys; print('q2 actual stage'); print('q2 stderr', file=sys.stderr)"],
            cwd=str(directory), env={"LANG": "C", "LC_ALL": "C"})
        measurement = runner._capture_stage(stage, directory, 1024, 5)
        self.assertEqual("SUCCEEDED", measurement["outcome"])
        self.assertEqual(0, measurement["exit_code"])
        self.assertIs(type(measurement["elapsed_seconds"]), float)
        self.assertGreaterEqual(measurement["elapsed_seconds"], 0)
        self.assertEqual(b"q2 actual stage\n", (directory / "actual-bounded-stage.stdout").read_bytes())
        self.assertEqual(b"q2 stderr\n", (directory / "actual-bounded-stage.stderr").read_bytes())
        _, proof = self.pending("preflight", stages=[measurement])
        original_digest = quota_closure.digest(proof)
        snapshot = quota_bridge.Phase(self.broker, "job", self.identity, "preflight", version=2).snapshot()
        self.assertEqual(proof, snapshot["pending"]["proof"])
        with self.assertRaisesRegex(quota_contract.QuotaError, "NON_INTEGER_NUMBER"):
            quota_bridge.Phase(self.broker, "job", self.identity, "preflight", version=1).snapshot()

        # Ledger stage identities above remain modeled. The inherited socket,
        # credentials, pidfd and deadline below use the real current process/OS.
        self.clock_patch.stop()
        clock = budget.current_clock()
        options = dict(peer=(os.getpid(), os.getuid(), os.getgid()), session="c"*64,
            boot_id=clock["boot_id"], deadline_ns=clock["boottime_ns"] + 5*SECOND, version=2)
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        sender, receiver = quota_bridge.Channel(left, **options), quota_bridge.Channel(right, **options)
        self.addCleanup(sender.close)
        self.addCleanup(receiver.close)
        errors = []
        def send():
            try:
                sender.send(snapshot)
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=send)
        thread.start()
        try:
            received = receiver.receive()
        finally:
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual([], errors)
        self.assertEqual(snapshot, received)
        self.assertEqual(proof, received["pending"]["proof"])
        self.assertEqual(original_digest, quota_closure.digest(received["pending"]["proof"]))
        self.assertEqual(measurement, received["pending"]["proof"]["result"]["stages"][0])
        self.assertEqual((1, 1), (sender.tx, receiver.rx))
        changed_authority = copy.deepcopy(snapshot)
        limits = changed_authority["preparation"]["budget"]["limits"]
        limits["cpu_seconds"] = float(limits["cpu_seconds"])
        sender.send(changed_authority)
        with self.assertRaisesRegex(quota_contract.QuotaError, "NON_INTEGER_NUMBER"):
            receiver.receive()
        self.assertTrue(receiver.poisoned)
        self.assertEqual(proof, self.row()["record"]["quota_pending"]["preflight"]["proof"])
        self.assertNotIn("preflight", self.row()["record"].get("quota_closed", {}))

    def test_unclosed_phase_cannot_advance_or_prepare_business(self):
        self.prepare("preflight")
        channel = mock.Mock()
        with self.assertRaisesRegex(ValueError, "RESIDENT_PHASE_ORDER"):
            self.chain.advance(channel, "preflight", "business")
        channel.receive.assert_not_called()
        channel.advance_phase.assert_not_called()
        with self.assertRaises(JobError):
            self.broker._start("job", self.identity, "business")
        self.assertEqual([], self.runner.starts)
        self.assertEqual({"preflight"}, set(self.row()["record"]["quota_preparations"]))

    def test_advance_requires_exact_original_closure_and_no_extra_authority(self):
        self.close("preflight")
        original = {"action": "advance", "value": {"from": "preflight", "to": "business",
            "closure_digest": quota_closure.digest(self.chain.closed["preflight"])}}
        for fault in ("digest", "skip", "argv", "budget"):
            command = copy.deepcopy(original)
            if fault == "digest":
                command["value"]["closure_digest"] = "0"*64
            elif fault == "skip":
                command["value"]["to"] = "evidence"
            else:
                command["value"][fault] = [] if fault == "argv" else {}
            channel = mock.Mock(receive=lambda: command)
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, "RESIDENT_ADVANCE"):
                self.chain.advance(channel, "preflight", "business")
            channel.advance_phase.assert_not_called()
        self.assertEqual({"preflight"}, set(self.row()["record"]["quota_preparations"]))

    def test_changed_session_or_expired_original_deadline_never_advances(self):
        self.close("preflight")
        original_session = self.broker._quota_session
        self.broker._quota_session = "f"*32
        with self.assertRaisesRegex(ValueError, "RESIDENT_ORIGINAL_CHAIN"):
            self.advance("preflight", "business")
        self.broker._quota_session = original_session
        self.now = self.chain.preparations["preflight"]["budget"]["deadline_boottime_ns"]
        with self.assertRaises(JobError):
            self.advance("preflight", "business")
        self.assertEqual(1, len(self.runner.starts))

    def test_changed_stored_budget_or_preparation_is_not_reconstructed(self):
        self.close("preflight")
        row = self.row()
        original = copy.deepcopy(row["record"]["quota_preparations"])
        changed = copy.deepcopy(original)
        changed["preflight"]["budget"]["deadline_boottime_ns"] += SECOND
        with self.f.db.transaction() as tx:
            self.f.db.update(tx, "job", self.identity, "FAULT", {"quota_preparations": changed})
        with self.assertRaises(JobError):
            self.advance("preflight", "business")
        self.assertEqual(1, len(self.runner.starts))

    def test_replayed_preparation_start_and_advance_never_deliver_again(self):
        self.close("preflight")
        snapshot = quota_bridge.Phase(self.broker, "job", self.identity, "preflight").snapshot()
        with self.assertRaisesRegex(ValueError, "RESIDENT_PHASE_ORDER"):
            self.chain.declaration("preflight", snapshot)
        with self.assertRaises(JobError):
            self.broker._start("job", self.identity, "preflight")
        self.advance("preflight", "business")
        self.prepare("business")
        with self.assertRaisesRegex(ValueError, "RESIDENT_ADVANCE_UNPROVEN"):
            self.advance("preflight", "business")
        self.assertEqual(1, len(self.runner.starts))

    def test_mutable_facts_cannot_replace_original_events(self):
        self.close("preflight")
        with self.f.db.transaction() as tx:
            self.f.db.update(tx, "job", self.identity, "FAULT", {"facts": {"inputs_stable": True, "foreign": True}})
        with self.assertRaisesRegex(ValueError, "RESIDENT_PREFLIGHT_FACTS_CHANGED"):
            self.advance("preflight", "business")
        self.assertEqual(1, len(self.runner.starts))

    def test_frozen_snapshot_change_is_rejected_before_evidence_delivery(self):
        self.close("preflight")
        self.advance("preflight", "business")
        self.close("business")
        self.advance("business", "evidence")
        changed = copy.deepcopy(self.row()["record"]["frozen_snapshot"])
        changed["root"] = "/synthetic/foreign"
        with self.f.db.transaction() as tx:
            self.f.db.update(tx, "job", self.identity, "FAULT", {"frozen_snapshot": changed})
        with self.assertRaisesRegex(ValueError, "RESIDENT_FROZEN_SNAPSHOT_CHANGED"):
            self.prepare("evidence")
        self.assertEqual(2, len(self.runner.starts))

    def test_completed_preflight_does_not_prove_final_seal(self):
        self.close("preflight")
        with self.assertRaisesRegex(ValueError, "RESIDENT_CHAIN_INCOMPLETE"):
            self.chain.complete()
        self.assertNotEqual("SEALED", self.row()["record"]["evidence"])


if __name__ == "__main__":
    unittest.main()
