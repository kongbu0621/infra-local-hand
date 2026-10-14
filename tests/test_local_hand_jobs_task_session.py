"""Service session with real SQLite and Unix control transport.

Quota grants and process exit proofs are modeled here; this is not a host run.
"""
import copy
import json
import os
from pathlib import Path
import select
import socket
import sqlite3
import sys
import time
import unittest
from unittest.mock import Mock, patch

from local_hand_jobs.contract import JobError, request_digest

if sys.platform.startswith("linux"):
    from local_hand_jobs.task_session import TaskSession
    from local_hand_jobs import budget, quota_bridge, quota_closure
    from local_hand_jobs.broker import Broker
    from local_hand_jobs.cli import MaintenanceServer, request as local_request
    from local_hand_jobs.state import StateStore
    import test_local_hand_jobs_quota_resident_chain as chain_fixtures


class Bridge:
    def __init__(self):
        self.sock, self.writer = socket.socketpair()
        self.incoming, self.outgoing, self.phases = [], [], []

    def _time(self):
        pass

    def send(self, value):
        self.outgoing.append(copy.deepcopy(value))

    def enqueue(self, command):
        self.incoming.append(command)
        self.writer.send(b"!")

    def receive(self):
        self.sock.recv(1)
        return self.incoming.pop(0)

    def advance_phase(self, phase):
        self.phases.append(phase)

    def close(self):
        self.sock.close()
        self.writer.close()


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux task session")
class TaskSessionTests(unittest.TestCase):
    def setUp(self):
        self.f = chain_fixtures.ResidentChainTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.broker = self.f.broker
        self.channel = Bridge()
        self.manager = Mock()
        self.session = TaskSession(dict(mode="execute", operation_id=self.f.identity,
            request_digest=self.f.f.request["request_digest"], principal_id=self.f.f.owner.principal_id),
            self.manager, self.channel)
        self.addCleanup(self.session.close)
        self.session.attach(self.broker)

    def command(self, action, value=None):
        self.channel.enqueue(dict(action=action, value=value))
        self.session.tick()
        return self.channel.outgoing[-1]

    def test_initial_read_contention_preserves_session_and_queued_command(self):
        self.session.tick()
        prepared = self.channel.outgoing[-1]
        grant = self.f.make_grant("preflight", prepared["snapshot"]["preparation"])
        self.channel.enqueue(dict(action="bind", value=grant.as_dict()))
        before = self.broker.state.events("job", self.f.identity)
        writer = sqlite3.connect(self.broker.state.path, isolation_level=None)
        self.addCleanup(writer.close)
        writer.execute("BEGIN IMMEDIATE")
        try:
            for _ in range(2):
                with self.assertRaises(JobError) as caught:
                    self.session.tick()
                self.assertEqual(sqlite3.SQLITE_BUSY, caught.exception.__cause__.sqlite_errorcode)
                self.assertIsNone(self.session.failure)
                self.assertEqual(1, len(self.channel.incoming))
        finally:
            writer.execute("ROLLBACK")
        self.assertEqual(before, self.broker.state.events("job", self.f.identity))
        self.assertEqual([], self.f.runner.starts)
        self.session.tick()
        self.assertEqual([], self.channel.incoming)
        self.assertIsNone(self.session.failure)
        self.command("start")
        self.assertEqual(1, len(self.f.runner.starts))

    def test_contention_after_consuming_command_keeps_recovery_barrier(self):
        self.session.tick()
        prepared = self.channel.outgoing[-1]
        grant = self.f.make_grant("preflight", prepared["snapshot"]["preparation"])
        self.command("bind", grant.as_dict())
        self.channel.enqueue(dict(action="start", value=None))
        writer = sqlite3.connect(self.broker.state.path, isolation_level=None)
        self.addCleanup(writer.close)
        receive = self.channel.receive
        def receive_then_lock():
            command = receive()
            writer.execute("BEGIN IMMEDIATE")
            return command
        try:
            with patch.object(self.channel, "receive", side_effect=receive_then_lock):
                with self.assertRaises(JobError):self.session.tick()
        finally:
            if writer.in_transaction:writer.execute("ROLLBACK")
        self.assertEqual([], self.channel.incoming)
        self.assertIsNotNone(self.session.failure)
        before = copy.deepcopy(self.channel.outgoing)
        self.session.tick()
        self.assertEqual(before, self.channel.outgoing)
        self.assertEqual([], self.f.runner.starts)

    def test_exit_record_contention_before_command_keeps_session_retryable(self):
        self.session.tick()
        prepared = self.channel.outgoing[-1]
        grant = self.f.make_grant("preflight", prepared["snapshot"]["preparation"])
        self.command("bind", grant.as_dict())
        self.command("start")
        execution = self.f.runner.starts[0][1]
        self.f.runner.finish(execution)
        self.f.runner.proofs[execution]["execution_id"] = execution
        self.channel.enqueue(dict(action="snapshot", value=None))
        writer = sqlite3.connect(self.broker.state.path, isolation_level=None)
        self.addCleanup(writer.close)
        inspect = self.f.runner.inspect
        def observe_then_lock(handle):
            proof = inspect(handle)
            writer.execute("BEGIN IMMEDIATE")
            return proof
        try:
            with patch.object(self.f.runner, "inspect", side_effect=observe_then_lock):
                with self.assertRaises(JobError):self.session.tick()
            self.assertIsNone(self.session.failure)
            self.assertEqual(1, len(self.channel.incoming))
        finally:
            if writer.in_transaction:writer.execute("ROLLBACK")
        self.session.tick()
        self.assertIsNone(self.session.failure)
        self.assertEqual([], self.channel.incoming)
        self.assertEqual(1, len(self.f.runner.starts))
        self.assertEqual(execution, self.channel.outgoing[-1]["pending"]["proof"]["execution_id"])

    def test_initial_preparation_contention_before_reservation_can_continue(self):
        self._check_initial_preparation_contention(after_reservation=False)

    def test_initial_preparation_contention_reuses_committed_reservation(self):
        self._check_initial_preparation_contention(after_reservation=True)

    def _check_initial_preparation_contention(self, *, after_reservation):
        writer = sqlite3.connect(self.broker.state.path, isolation_level=None)
        self.addCleanup(writer.close)
        start = self.broker._start
        def contend(*args):
            if after_reservation:start(*args)
            writer.execute("BEGIN IMMEDIATE")
            if not after_reservation:start(*args)
        try:
            with patch.object(self.broker, "_start", side_effect=contend):
                with self.assertRaises(JobError):self.session.tick()
            self.assertIsNone(self.session.failure)
            self.assertEqual([], self.channel.outgoing)
        finally:
            if writer.in_transaction:writer.execute("ROLLBACK")
        reserved = copy.deepcopy(self.f.row()["record"].get("execution_budget"))
        self.session.tick()
        self.assertIsNone(self.session.failure)
        if after_reservation:self.assertEqual(reserved, self.f.row()["record"]["execution_budget"])
        self.assertEqual(1, sum(event['kind']=='QUOTA_PREPARATION' for event in
                               self.broker.state.events('job', self.f.identity)))
        self.assertEqual([], self.f.runner.starts)
        prepared = self.channel.outgoing[-1]
        grant = self.f.make_grant("preflight", prepared["snapshot"]["preparation"])
        self.command("bind", grant.as_dict())
        self.command("start")
        self.assertEqual(1, len(self.f.runner.starts))

    def test_preparation_is_not_launch_and_bind_waits_for_controller_start(self):
        self.session.tick()
        prepared = self.channel.outgoing[-1]
        self.assertEqual("prepared", prepared["event"])
        self.assertFalse(self.f.row()["record"]["handles"])
        grant = self.f.make_grant("preflight", prepared["snapshot"]["preparation"])
        self.command("bind", grant.as_dict())
        for _ in range(3):
            self.session.tick()
        self.assertFalse(self.f.row()["record"]["handles"])
        self.command("start")
        self.assertEqual({"preflight"}, set(self.f.row()["record"]["handles"]))
        with self.assertRaises(JobError):
            self.command("start")
        self.assertEqual(1, len(self.f.runner.starts))

    def test_cancel_before_delivery_finishes_without_manager_start(self):
        request = self.f.f.request
        self.broker.cancel(self.f.identity, request["request_digest"], {"kind": "job"}, self.f.f.owner)
        self.session.tick()
        self.assertEqual("CANCELLED", self.f.row()["record"]["outcome"])
        self.assertFalse(self.f.row()["record"]["handles"])
        self.assertEqual("terminal", self.channel.outgoing[-1]["event"])
        self.command("finish")
        self.assertTrue(self.session.finished)

    def test_cancel_after_preparation_answers_inflight_start_without_launch(self):
        self.session.tick()
        self.broker.cancel(self.f.identity, self.f.f.request["request_digest"],
                           {"kind": "job"}, self.f.f.owner)
        for action in ("bind", "start"):
            result = self.command(action)
            self.assertEqual("CANCELLED", result["task"]["outcome"])
        self.assertFalse(self.f.row()["record"]["handles"])
        self.assertEqual([], self.f.runner.starts)
        self.assertIsNone(self.session.failure)
        self.command("finish")
        self.assertTrue(self.session.finished)

    def test_cancel_between_closed_phase_and_advance_keeps_real_channel_in_order(self):
        self._cancel_at_closed_phase(queued=False)

    def test_cancel_with_advance_already_in_flight_keeps_real_channel_in_order(self):
        self._cancel_at_closed_phase(queued=True)

    def test_cancel_after_business_closure_preserves_success_without_starting_evidence(self):
        self._cancel_at_closed_phase(queued=True, phase="business")

    def test_cancel_after_advance_before_preparation_keeps_real_channel_in_order(self):
        self._cancel_at_closed_phase(queued=True, during_prepare=True)

    def test_cancel_before_initial_preparation_does_not_freeze_session(self):
        prepare = self.session._prepare
        def cancel_before_prepare(phase):
            self.broker.cancel(self.f.identity, self.f.f.request["request_digest"],
                               {"kind": "job"}, self.f.f.owner)
            prepare(phase)
        with patch.object(self.session, "_prepare", side_effect=cancel_before_prepare):
            self.session.tick()
        self.session.tick()
        self.assertEqual("terminal", self.channel.outgoing[-1]["event"])
        self.assertEqual("CANCELLED", self.channel.outgoing[-1]["task"]["outcome"])
        self.assertIsNone(self.session.failure)
        self.assertFalse(self.f.row()["record"].get("quota_preparations"))
        self.assertEqual([], self.f.runner.starts)
        self.command("finish")
        self.assertTrue(self.session.finished)

    def test_cancelled_transition_still_rejects_changed_closure_digest(self):
        self.session.tick()
        fence, _ = self.f.pending("preflight")
        self.command("close", fence)
        starts = len(self.f.runner.starts)
        self.broker.cancel(self.f.identity, self.f.f.request["request_digest"],
                           {"kind": "job"}, self.f.f.owner)
        with self.assertRaises(JobError) as caught:
            self.command("advance", {"from": "preflight", "to": "business",
                                    "closure_digest": "0" * 64})
        self.assertIn("SESSION_ADVANCE", str(caught.exception.__cause__))
        self.assertEqual([], self.channel.phases)
        self.assertEqual(starts, len(self.f.runner.starts))
        self.assertEqual({"preflight"}, set(self.f.row()["record"]["quota_preparations"]))
        self.assertEqual("CANCELLED", self.f.row()["record"]["outcome"])

    def _cancel_at_closed_phase(self, *, queued, phase="preflight", during_prepare=False):
        self.session.tick()
        phases = ("preflight", "business", "evidence")
        index = phases.index(phase)
        for current in phases[:index+1]:
            fence, _ = self.f.pending(current)
            self.command("close", fence)
            closed = self.f.row()["record"]["quota_closed"][current]
            self.f.chain.retain_closure(current, closed)
            if current != phase:
                self.command("advance", {"from": current, "to": phase,
                             "closure_digest": quota_closure.digest(closed)})
        starts = len(self.f.runner.starts)
        self.channel.close()
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        clock = budget.current_clock()
        options = dict(peer=(os.getpid(), os.getuid(), os.getgid()), session="a"*64,
                       boot_id=clock["boot_id"], deadline_ns=clock["boottime_ns"]+60_000_000_000, version=2)
        self.channel = quota_bridge.Channel(left, **options)
        controller = quota_bridge.Channel(right, **options)
        self.addCleanup(controller.close)
        self.session.channel = self.channel
        for current in phases[1:index+1]:
            self.channel.advance_phase(current)
            controller.advance_phase(current)
        following = phases[index+1]
        advance = dict(action="advance", value={"from": phase, "to": following,
                       "closure_digest": quota_closure.digest(closed)})
        def cancel():
            self.broker.cancel(self.f.identity, self.f.f.request["request_digest"], {"kind": "job"}, self.f.f.owner)
        if not during_prepare:
            cancel()
        if queued:
            controller.send(advance)
            controller.advance_phase(following)
        else:
            self.session.tick()
            self.assertEqual([], select.select([controller.sock], [], [], 0)[0],
                             "No old-phase reply may race the controller's phase advance")
            controller.send(advance)
            controller.advance_phase(following)
        if during_prepare:
            prepare = self.session._prepare
            def cancel_before_prepare(current):
                cancel()
                prepare(current)
            with patch.object(self.session, "_prepare", side_effect=cancel_before_prepare):
                self.session.tick()
            self.session.tick()
        else:
            self.session.tick()
        terminal = controller.receive()
        self.assertEqual("terminal", terminal["event"])
        self.assertEqual("CANCELLED" if phase == "preflight" else "SUCCEEDED", terminal["task"]["outcome"])
        self.assertTrue(terminal["task"]["cancel_requested"])
        self.assertIsNone(self.session.failure)
        self.assertEqual(starts, len(self.f.runner.starts))
        self.assertEqual(set(phases[:index+1]), set(self.f.row()["record"]["handles"]))
        self.assertEqual(set(phases[:index+1]), set(self.f.row()["record"]["quota_preparations"]))
        controller.send(dict(action="finish", value=None))
        self.session.tick()
        self.assertTrue(self.session.finished)

    def test_wrong_task_rejected_before_creating_a_second_row_or_leases(self):
        request = copy.deepcopy(self.f.f.request)
        request["operation_id"] = "11111111-2222-4333-8444-666666666666"
        request["request_digest"] = request_digest(request)
        with self.assertRaises(JobError) as caught:
            self.broker.submit(request, self.f.f.owner)
        self.assertEqual("UNAUTHORIZED", caught.exception.code)
        self.assertIsNone(self.broker.state.get("job", request["operation_id"]))
        original = self.broker.submit(self.f.f.request, self.f.f.owner)
        self.assertEqual(self.f.identity, original["operation_id"])

    def test_execute_session_cannot_adopt_an_existing_preparation(self):
        self.session.tick()
        second = TaskSession(self.session.value, Mock(), Mock())
        with self.assertRaisesRegex(ValueError, "SESSION_RECOVERY_REQUIRED"):
            second.attach(self.broker)

    def test_recovery_runs_original_broker_attachment_and_never_prepares(self):
        self.session.value = dict(self.session.value, mode="recover")
        with patch.object(self.broker, "recover") as recover, \
                patch.object(self.broker, "tick") as tick, \
                patch.object(self.broker, "_start") as start:
            self.session.recover()
            self.session.tick()
            recover.assert_called_once()
            tick.assert_not_called()
            start.assert_not_called()
        self.manager.finish_recovery.assert_called_once()
        self.assertFalse(self.channel.outgoing)

    def test_recovery_cannot_create_a_fresh_phase_even_when_prior_result_allows_it(self):
        self.session.value = dict(self.session.value, mode="recover")
        with self.assertRaises(JobError) as caught:
            self.broker._start("job", self.f.identity, "preflight")
        self.assertEqual("UNSUPPORTED", caught.exception.code)
        self.assertFalse(self.f.row()["record"]["handles"])
        self.assertNotIn("quota_preparations", self.f.row()["record"])

    def test_failed_control_exchange_retains_cancel_observation(self):
        self.session.tick()
        self.channel.enqueue({"action": "unrecognized", "value": None})
        with self.assertRaises(JobError):
            self.session.tick()
        self.assertEqual("RECONCILE_REQUIRED", self.f.row()["record"]["lifecycle"])
        self.broker._active["job", self.f.identity] = {"execution_id": "retained"}
        with patch.object(self.broker, "tick") as tick:
            self.session.tick()
            tick.assert_called_once()

    def test_control_failure_logs_original_location_without_payload_or_token(self):
        self.session.tick()
        secret = "Bearer private-token /private/host/path"
        self.channel.enqueue({"action": secret, "value": {"token": secret}})
        with self.assertLogs("local_hand_jobs.task_session", level="ERROR") as logs:
            with self.assertRaises(JobError):
                self.session.tick()
        self.assertNotIn(secret, str(logs.output))
        value = json.loads(logs.records[0].getMessage().split(" ", 1)[1])
        self.assertEqual(self.f.identity, value["operation_id"])
        self.assertEqual("preflight", value["phase"])
        self.assertEqual("invalid_command", value["action"])
        self.assertTrue(value["control_started"])
        cause = value["causes"][0]
        self.assertEqual("QuotaError", cause["type"])
        self.assertIn("code", cause)
        self.assertTrue(any(frame["file"] == "quota_bridge.py" and frame["line"] > 0 for frame in cause["frames"]))

    def test_business_bootstrap_cancel_answers_pending_snapshot_and_finishes(self):
        self.session.tick()
        fence, _ = self.f.pending("preflight")
        self.command("close", fence)
        closed = self.f.row()["record"]["quota_closed"]["preflight"]
        self.f.chain.retain_closure("preflight", closed)
        self.command("advance", {"from": "preflight", "to": "business",
                                 "closure_digest": quota_closure.digest(closed)})
        prepared = self.channel.outgoing[-1]["snapshot"]["preparation"]
        grant = self.f.make_grant("business", prepared)
        self.command("bind", grant.as_dict())
        self.command("start")
        execution = "job-" + self.f.identity + "-business"
        self.assertTrue(self.broker._guard_start(execution, lambda: True, stage="bootstrap"))
        self.broker.cancel(self.f.identity, self.f.f.request["request_digest"], {"kind": "job"}, self.f.f.owner)
        self.f.runner.finish(execution, exit_code=1,
            writers_stopped=True, collectors_stopped=True,
            result=dict(outcome="CANCELLED", business_started=False, helper_started=True))
        self.f.runner.proofs[execution]["execution_id"] = execution
        reply = self.command("snapshot")
        self.assertEqual("TERMINAL", reply["task"]["lifecycle"])
        self.assertEqual("CANCELLED", reply["task"]["outcome"])
        self.assertIsNone(reply["observation"])
        self.assertIsNone(reply["closed"])
        self.assertIsNotNone(reply["pending"])
        self.command("finish")
        self.assertTrue(self.session.finished)
        self.assertIsNone(self.session.failure)
        self.assertEqual(2, len(self.f.runner.starts))
        self.assertNotIn(execution + ":helper", self.f.row()["record"]["delivery_intents"])

    def test_control_failure_logs_os_cause_without_exception_text(self):
        self.session.tick()
        self.channel.enqueue({"action": "snapshot", "value": None})
        def broken_snapshot():
            try:
                raise OSError(5, "private-token", "/private/host/path")
            except OSError as cause:
                raise JobError("IO_UNCERTAIN", "Bearer private-token") from cause
        with patch.object(self.session.handler, "snapshot", side_effect=broken_snapshot):
            with self.assertLogs("local_hand_jobs.task_session", level="ERROR") as logs:
                with self.assertRaises(JobError):
                    self.session.tick()
        self.assertNotIn("private-token", str(logs.output))
        self.assertNotIn("/private/host/path", str(logs.output))
        value = json.loads(logs.records[0].getMessage().split(" ", 1)[1])
        self.assertEqual("snapshot", value["action"])
        self.assertEqual("IO_UNCERTAIN", value["causes"][0]["code"])
        self.assertEqual(5, value["causes"][1]["errno"])

    def test_start_uses_session_coordinator_and_close_releases_channels(self):
        with patch.object(self.session, "recover") as recover, \
                patch.object(self.session, "tick", side_effect=lambda: self.broker._shutdown.set()) as tick:
            self.broker.start()
            self.broker._thread.join(timeout=1)
            self.assertFalse(self.broker._thread.is_alive())
            recover.assert_called_once()
            tick.assert_called_once()
        self.broker.close()
        self.manager.close.assert_called_once()

    def test_three_phase_closure_advances_only_on_original_controller_ack(self):
        self.session.tick()
        for index, phase in enumerate(("preflight", "business", "evidence")):
            fence, _ = self.f.pending(phase)
            self.command("close", fence)
            closed = self.f.row()["record"]["quota_closed"][phase]
            self.f.chain.retain_closure(phase, closed)
            starts = len(self.f.runner.starts)
            for _ in range(3):
                self.session.tick()
            self.assertEqual(starts, len(self.f.runner.starts))
            if index < 2:
                following = ("business", "evidence")[index]
                self.command("advance", {"from": phase, "to": following,
                    "closure_digest": quota_closure.digest(closed)})
                self.assertEqual(following, self.channel.outgoing[-1]["phase"])
        self.command("finish")
        record = self.f.row()["record"]
        self.assertEqual(("TERMINAL", "SUCCEEDED", "SEALED"),
                         (record["lifecycle"], record["outcome"], record["evidence"]))
        self.assertEqual(3, len(self.f.runner.starts))
        self.assertNotIn("Original management and ordinary phase closure is pending", record["gaps"])
        self.assertTrue(self.session.finished)

    def test_real_unix_client_submits_queries_and_cancels_the_session_task(self):
        # New empty database: the service/session must not auto-submit a job.
        root = Path(self.f.f.temp.name)
        state = StateStore(root / "service.sqlite", "authority", "service-ledger", initialize=True)
        self.addCleanup(state.close)
        broker = Broker(state, self.f.f.policy, self.broker.registry, self.f.runner,
                        evidence=self.broker.evidence, quota_required=True)
        session = TaskSession(self.session.value, self.manager, self.channel)
        session.attach(broker)
        broker.start()
        self.addCleanup(broker.close)
        path = root / "maintenance.sock"
        server = MaintenanceServer(broker, path, {os.geteuid(): self.f.f.owner})
        server.start()
        self.addCleanup(server.close)
        self.assertIsNone(state.get("job", self.f.identity))
        accepted = local_request(path, "lh_job_submit", self.f.f.request)
        self.assertEqual(self.f.identity, accepted["operation_id"])
        duplicate = local_request(path, "lh_job_submit", self.f.f.request)
        self.assertEqual(accepted["request_digest"], duplicate["request_digest"])
        local_request(path, "lh_job_cancel", dict(operation_id=self.f.identity,
            expected_request_digest=accepted["request_digest"], target={"kind": "job"}))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            status = local_request(path, "lh_job_status", {"operation_id": self.f.identity})
            if status["lifecycle"] == "TERMINAL":
                break
            time.sleep(0.01)
        self.assertEqual("CANCELLED", status["outcome"])
        self.assertFalse(state.get("job", self.f.identity)["record"]["handles"])
        with state.transaction() as tx:
            self.assertEqual(1, len(state.all(tx)))


if __name__ == "__main__":
    unittest.main()
