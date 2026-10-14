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
        with self.broker.state.transaction() as tx:
            self.assertEqual(0, tx.execute("SELECT count(*) FROM leases WHERE owner=?", (self.f.identity,)).fetchone()[0])
            self.assertEqual(6, tx.execute("SELECT count(*) FROM leases").fetchone()[0])
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

    def test_cancel_with_original_close_inflight_returns_stopped_snapshot(self):
        self.session.tick()
        complete = chain_fixtures.complete
        def identified(grant, **options):
            value = complete(grant, **options)
            value[1]["execution_id"] = "job-" + self.f.identity + "-preflight"
            return value
        with patch.object(chain_fixtures, "complete", side_effect=identified):
            fence, _ = self.f.pending("preflight")
        self.broker.cancel(self.f.identity, self.f.f.request["request_digest"], {"kind": "job"}, self.f.f.owner)
        reply = self.command("close", fence)
        self.assertEqual("TERMINAL", reply["task"]["lifecycle"])
        self.assertTrue(reply["task"]["cancel_requested"])
        self.assertIsNone(reply["closed"])
        self.assertIsNotNone(reply["pending"])
        self.assertIsNone(self.session.failure)
        self.command("finish")
        self.assertTrue(self.session.finished)

    def test_close_publication_contention_replies_once_and_cancellation_finishes(self):
        self.session.tick()
        fence, _ = self.f.pending("preflight")
        self.command("close", fence)
        closed = self.f.row()["record"]["quota_closed"]["preflight"]
        self.f.chain.retain_closure("preflight", closed)
        self.command("advance", {"from":"preflight", "to":"business",
                                "closure_digest":quota_closure.digest(closed)})
        fence, _ = self.f.pending("business")
        starts = copy.deepcopy(self.f.runner.starts)
        replies = copy.deepcopy(self.channel.outgoing)
        writer = sqlite3.connect(self.broker.state.path, isolation_level=None)
        self.addCleanup(writer.close)
        complete = self.broker._complete
        def locked(*args):
            writer.execute("BEGIN IMMEDIATE")
            try:return complete(*args)
            finally:writer.execute("ROLLBACK")
        with patch.object(self.broker, "_complete", side_effect=locked):
            with self.assertRaises(JobError):
                self.command("close", fence)
        self.assertIn("business", self.f.row()["record"]["quota_closed"])
        self.assertEqual([], self.channel.incoming)
        self.assertEqual(replies, self.channel.outgoing)
        self.assertIsNone(self.session.failure)
        self.assertFalse(self.session.handler.failed)
        self.broker.cancel(self.f.identity, self.f.row()["digest"], {"kind":"job"}, self.f.f.owner)
        self.session.tick()
        reply = self.channel.outgoing[-1]
        self.assertEqual(len(replies)+1, len(self.channel.outgoing))
        self.assertEqual(fence, reply["closed"]["fence"])
        self.assertEqual("TERMINAL", reply["task"]["lifecycle"])
        self.assertIsNone(self.session.failure)
        self.command("advance", {"from":"business", "to":"evidence",
                                "closure_digest":quota_closure.digest(reply["closed"])})
        self.assertEqual("terminal", self.channel.outgoing[-1]["event"])
        self.command("finish")
        self.assertTrue(self.session.finished)
        self.assertEqual(starts, self.f.runner.starts)
        self.assertNotIn("evidence", self.f.row()["record"]["handles"])
        self.assertEqual(2, sum(e["kind"] == "QUOTA_PHASE_CLOSED"
                               for e in self.broker.state.events("job", self.f.identity)))

    def test_close_reply_contention_waits_for_original_advance_before_next_preparation(self):
        self.session.tick()
        fence, _ = self.f.pending("preflight")
        self.session.started = True
        writer = sqlite3.connect(self.broker.state.path, isolation_level=None)
        self.addCleanup(writer.close)
        snapshot = self.session.handler.snapshot
        def locked():
            writer.execute("BEGIN IMMEDIATE")
            try:return snapshot()
            finally:writer.execute("ROLLBACK")
        with patch.object(self.session.handler, "snapshot", side_effect=locked):
            with self.assertRaises(JobError):
                self.command("close", fence)
        self.assertEqual("PREFLIGHT_COMPLETE", self.f.row()["record"]["phase"])
        starts = copy.deepcopy(self.f.runner.starts)
        self.session.tick()
        reply = self.channel.outgoing[-1]
        self.assertEqual(fence, reply["closed"]["fence"])
        self.assertIsNone(self.session.failure)
        self.assertEqual({"preflight"}, set(self.f.row()["record"]["quota_preparations"]))
        self.assertEqual(starts, self.f.runner.starts)
        self.f.chain.retain_closure("preflight", reply["closed"])
        self.command("advance", {"from":"preflight", "to":"business",
                                "closure_digest":quota_closure.digest(reply["closed"])})
        self.assertEqual("business", self.channel.outgoing[-1]["phase"])
        self.assertEqual(starts, self.f.runner.starts)

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

    def test_cancel_after_recovery_handshake_finishes_same_task_without_new_control(self):
        for phase in ("preflight", "business"):
            with self.subTest(phase=phase):
                case = TaskSessionTests()
                case.setUp(); self.addCleanup(case.doCleanups)
                for current in ("preflight", "business")[:1 if phase == "preflight" else 2]:
                    case.f.close(current)
                old = case.f.row()
                recovered = Broker(case.broker.state, case.broker.policy, case.broker.registry,
                                   case.f.runner, evidence=case.broker.evidence, quota_required=True)
                manager = Mock()
                session = TaskSession(dict(case.session.value, mode="recover"), manager, None)
                case.addCleanup(session.close)
                session.attach(recovered)
                session.recover()
                session.tick()
                self.assertTrue(session.finished)
                manager.finish_recovery.assert_called_once()
                before = copy.deepcopy(case.f.row())
                starts = copy.deepcopy(case.f.runner.starts)
                events = recovered.state.events("job", case.f.identity)
                self.assertEqual("RECONCILE_REQUIRED", before["record"]["lifecycle"])
                session.tick()
                self.assertEqual(events, recovered.state.events("job", case.f.identity))
                endpoint = Path(case.f.f.temp.name) / "cancel-after-recovery.sock"
                server = MaintenanceServer(recovered, endpoint, {os.geteuid():case.f.f.owner})
                server.start(); case.addCleanup(server.close)
                cancel = dict(operation_id=case.f.identity, expected_request_digest=old["digest"], target={"kind":"job"})
                local_request(endpoint, "lh_job_cancel", cancel)
                with patch.object(recovered, "_start", side_effect=AssertionError("Recovery launched work")):
                    session.tick(); session.tick()
                status = local_request(endpoint, "lh_job_status", {"operation_id":case.f.identity})
                self.assertEqual("TERMINAL", status["lifecycle"])
                self.assertEqual("CANCELLED" if phase == "preflight" else "SUCCEEDED", status["outcome"])
                self.assertEqual(starts, case.f.runner.starts)
                self.assertEqual(before["record"]["exit_proof"], case.f.row()["record"]["exit_proof"])
                self.assertEqual(old["record"]["delivery_intents"], case.f.row()["record"]["delivery_intents"])
                self.assertEqual(old["record"]["quota_closed"], case.f.row()["record"]["quota_closed"])
                with recovered.state.transaction() as tx:
                    self.assertEqual(0, tx.execute("SELECT count(*) FROM leases WHERE owner=?", (case.f.identity,)).fetchone()[0])
                    self.assertEqual(6, tx.execute("SELECT count(*) FROM leases").fetchone()[0])
                events = recovered.state.events("job", case.f.identity)
                repeated = local_request(endpoint, "lh_job_cancel", cancel)
                session.tick()
                self.assertEqual(status["event_seq"], repeated["event_seq"])
                self.assertEqual(events, recovered.state.events("job", case.f.identity))
                manager.finish_recovery.assert_called_once()

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

    def test_cancel_after_recovery_with_pending_exit_through_live_coordinator(self):
        from test_local_hand_jobs_cancel_boundaries import CancelBoundaryTests
        fixture = CancelBoundaryTests()
        self.addCleanup(fixture.doCleanups)
        f, _, proof = fixture.pending_result("business", failed=True)
        replacement = Mock()
        replacement.reattach.side_effect = AssertionError("Durable exit must not be reattached")
        b = Broker(f.broker.state, f.broker.policy, f.broker.registry, replacement,
                   evidence=f.broker.evidence, quota_required=True)
        self.addCleanup(b.close)
        manager = Mock()
        session = TaskSession(dict(mode="recover", operation_id=f.identity,
            request_digest=f.row()["digest"], principal_id=f.f.owner.principal_id), manager, None)
        session.attach(b)
        b.start()
        deadline = time.monotonic() + 3
        while not session.finished and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(session.finished)
        manager.finish_recovery.assert_called_once()
        endpoint = Path(f.f.temp.name) / "recovered-pending-exit.sock"
        server = MaintenanceServer(b, endpoint, {os.geteuid():f.f.owner})
        server.start(); self.addCleanup(server.close)
        cancel = dict(operation_id=f.identity, expected_request_digest=f.row()["digest"], target={"kind":"job"})
        local_request(endpoint, "lh_job_cancel", cancel)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status = local_request(endpoint, "lh_job_status", {"operation_id":f.identity})
            if status["lifecycle"] == "TERMINAL":break
            time.sleep(.01)
        self.assertEqual(("TERMINAL", "EXITED", "UNKNOWN"),
            (status["lifecycle"], status["phase"], status["outcome"]))
        self.assertEqual(proof, f.row()["record"]["exit_proof"])
        self.assertTrue(f.row()["record"]["execution_resources_released"])
        self.assertEqual(status["event_seq"], local_request(endpoint, "lh_job_cancel", cancel)["event_seq"])
        replacement.reattach.assert_not_called()
        replacement.start.assert_not_called()
        replacement.stop.assert_not_called()
        manager.finish_recovery.assert_called_once()

    def test_cancel_after_failed_control_exchange_finishes_retained_exit(self):
        for phase in ("preflight", "business", "evidence"):
            with self.subTest(phase=phase):
                case = TaskSessionTests()
                case.setUp(); self.addCleanup(case.doCleanups)
                case._cancel_retained_exit_after_control_failure(phase)

    def test_concurrent_cancel_cannot_be_reopened_by_control_failure(self):
        unknown = self.broker._unknown
        retained = {}
        def cancel_then_record_error(*args):
            self.broker.cancel(self.f.identity, self.f.row()["digest"], {"kind":"job"}, self.f.f.owner)
            retained["row"] = copy.deepcopy(self.f.row())
            retained["events"] = self.broker.state.events("job", self.f.identity)
            return unknown(*args)
        with patch.object(self.session, "_prepare", side_effect=OSError("local preparation failed")), \
                patch.object(self.broker, "_unknown", side_effect=cancel_then_record_error), \
                self.assertLogs("local_hand_jobs.task_session", level="ERROR"):
            with self.assertRaises(JobError):
                self.session.tick()
        self.assertEqual("TERMINAL", retained["row"]["record"]["lifecycle"])
        self.assertEqual(retained["row"], self.f.row())
        self.assertEqual(retained["events"], self.broker.state.events("job", self.f.identity))
        self.assertEqual([], self.f.runner.starts)

    def test_failed_advance_never_launches_but_still_accepts_later_cancel(self):
        self.session.tick()
        fence, _ = self.f.pending("preflight")
        self.command("close", fence)
        with self.assertLogs("local_hand_jobs.task_session", level="ERROR"):
            with self.assertRaises(JobError):
                self.command("advance", {"from":"preflight", "to":"business", "closure_digest":"0"*64})
        before = copy.deepcopy(self.f.row())
        with patch.object(self.broker, "_start", side_effect=AssertionError("Failed session launched")):
            self.session.tick()
            self.assertEqual(before, self.f.row())
            self.broker.cancel(self.f.identity, before["digest"], {"kind":"job"}, self.f.f.owner)
            self.session.tick()
        self.assertEqual("TERMINAL", self.f.row()["record"]["lifecycle"])
        self.assertEqual("CANCELLED", self.f.row()["record"]["outcome"])
        self.assertEqual({"preflight"}, set(self.f.row()["record"]["handles"]))

    def _cancel_retained_exit_after_control_failure(self, phase):
        self.session.tick()
        phases = ("preflight", "business", "evidence")
        for current in phases[:phases.index(phase)]:
            fence, _ = self.f.pending(current)
            self.command("close", fence)
            closed = self.f.row()["record"]["quota_closed"][current]
            self.f.chain.retain_closure(current, closed)
            self.command("advance", {"from":current, "to":phases[phases.index(current)+1],
                                    "closure_digest":quota_closure.digest(closed)})
        complete = chain_fixtures.complete
        def uncollected(grant, **options):
            value = complete(grant, **options)
            proof = value[1]
            execution = "job-" + self.f.identity + "-" + phase
            proof.update(execution_id=execution, effects_checked=False, helper_result_verified=False,
                         result=dict(outcome="UNKNOWN", helper_started=True))
            identity = proof["quota_stage_exits"]["reader"]["identity"]
            proof["result_reader_exit_proof"] = dict(execution_id=execution, state="EXITED",
                unit=identity["unit"], identity={k:identity[k] for k in ("boot_id", "invocation_id", "cgroup")},
                **dict.fromkeys(("future_start_blocked", "tree_exited", "writers_stopped", "collectors_stopped"), True))
            return value
        with patch.object(chain_fixtures, "complete", side_effect=uncollected):
            _, proof = self.f.pending(phase)
        self.assertNotIn(("job", self.f.identity), self.broker._active)
        self.channel.enqueue({"action":"unrecognized", "value":None})
        with self.assertLogs("local_hand_jobs.task_session", level="ERROR"):
            with self.assertRaises(JobError):
                self.session.tick()
        self.assertIsNotNone(self.session.failure)
        before = copy.deepcopy(self.f.row())
        starts = copy.deepcopy(self.f.runner.starts)
        replies = copy.deepcopy(self.channel.outgoing)
        with self.broker.state.transaction() as tx:
            leases = [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")]
        endpoint = Path(self.f.f.temp.name) / "cancel-after-failure.sock"
        server = MaintenanceServer(self.broker, endpoint, {os.geteuid():self.f.f.owner})
        server.start(); self.addCleanup(server.close)
        cancel = dict(operation_id=self.f.identity, expected_request_digest=before["digest"], target={"kind":"job"})
        local_request(endpoint, "lh_job_cancel", cancel)
        self.session.tick(); self.session.tick()
        record = self.f.row()["record"]
        self.assertEqual(("TERMINAL", "EXITED"), (record["lifecycle"], record["phase"]))
        self.assertEqual({"preflight":"CANCELLED", "business":"UNKNOWN", "evidence":"SUCCEEDED"}[phase], record["outcome"])
        self.assertEqual(proof, record["exit_proof"])
        self.assertEqual(starts, self.f.runner.starts)
        self.assertEqual(replies, self.channel.outgoing)
        self.assertEqual(before["record"]["delivery_intents"], record["delivery_intents"])
        with self.broker.state.transaction() as tx:
            self.assertEqual([r for r in leases if r[1] != self.f.identity],
                             [tuple(r) for r in tx.execute("SELECT * FROM leases ORDER BY resource")])
        events = self.broker.state.events("job", self.f.identity)
        status = local_request(endpoint, "lh_job_status", {"operation_id":self.f.identity})
        repeated = local_request(endpoint, "lh_job_cancel", cancel)
        self.assertEqual("TERMINAL", status["lifecycle"])
        self.assertEqual(status["event_seq"], repeated["event_seq"])
        self.session.tick()
        self.assertEqual(events, self.broker.state.events("job", self.f.identity))

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
        self.check_business_cancel(helper=False)

    def test_business_helper_cancel_stops_controller_without_ordinary_three_stage_closure(self):
        self.check_business_cancel(helper=True)

    def test_business_reader_cancel_answers_controller_and_finishes(self):
        self.check_business_cancel(helper=True, reader=True)

    def test_evidence_cancel_at_each_stage_answers_controller_and_preserves_business(self):
        for helper, reader in ((False, False), (True, False), (True, True)):
            with self.subTest(helper=helper, reader=reader):
                case = TaskSessionTests()
                case.setUp(); self.addCleanup(case.doCleanups)
                case.check_business_cancel(helper=helper, reader=reader, phase="evidence")

    def check_business_cancel(self, *, helper, reader=False, phase="business"):
        self.session.tick()
        previous = ("preflight",) if phase == "business" else ("preflight", "business")
        for index, current in enumerate(previous):
            fence, _ = self.f.pending(current)
            self.command("close", fence)
            closed = self.f.row()["record"]["quota_closed"][current]
            self.f.chain.retain_closure(current, closed)
            following = previous[index+1] if index+1 < len(previous) else phase
            self.command("advance", {"from": current, "to": following,
                                     "closure_digest": quota_closure.digest(closed)})
        prepared = self.channel.outgoing[-1]["snapshot"]["preparation"]
        grant = self.f.make_grant(phase, prepared)
        self.command("bind", grant.as_dict())
        self.command("start")
        execution = "job-" + self.f.identity + "-" + phase
        self.assertTrue(self.broker._guard_start(execution, lambda: True, stage="bootstrap"))
        if helper:
            import hashlib
            from test_local_hand_jobs_quota_binding import observed
            self.f.now += chain_fixtures.SECOND
            bootstrap = dict(execution_id=execution, state="EXITED", exit_code=0,
                unit="lhj-" + hashlib.sha256((execution + ":bootstrap").encode()).hexdigest() + ".service",
                **dict.fromkeys(("future_start_blocked", "tree_exited", "collectors_stopped",
                                 "writers_stopped", "effects_checked"), True),
                result=dict(bootstrap_prepared=True, quota_observation=observed(grant)))
            self.assertTrue(self.broker._guard_start(execution, lambda: True, stage="helper", bootstrap_proof=bootstrap))
        if reader:
            unit = "lhj-" + hashlib.sha256(execution.encode()).hexdigest() + ".service"
            proof = dict(bootstrap, unit=unit, identity=dict(boot_id=chain_fixtures.BOOT,
                invocation_id="e"*32, cgroup="/synthetic-job.slice/" + unit))
            self.assertTrue(self.broker._guard_start(execution, lambda: True, stage="result_reader", helper_proof=proof))
        self.broker.cancel(self.f.identity, self.f.f.request["request_digest"], {"kind": "job"}, self.f.f.owner)
        self.f.runner.finish(execution, exit_code=1,
            writers_stopped=True, collectors_stopped=True,
            result=dict(outcome="CANCELLED", business_started=False, helper_started=True))
        self.f.runner.proofs[execution]["execution_id"] = execution
        if helper:
            self.f.runner.proofs[execution].update(exit_code=0, effects_checked=False,
                helper_result_verified=False, result=dict(outcome="UNKNOWN", helper_started=True))
        if reader:
            unit = "lhj-" + hashlib.sha256((execution + ":result_reader").encode()).hexdigest() + ".service"
            self.f.runner.proofs[execution]["result_reader_exit_proof"] = dict(bootstrap, unit=unit, exit_code=1,
                identity=dict(boot_id=chain_fixtures.BOOT, invocation_id="f"*32, cgroup="/synthetic-job.slice/" + unit))
        reply = self.command("snapshot")
        self.assertEqual("TERMINAL", reply["task"]["lifecycle"])
        self.assertEqual("SUCCEEDED" if phase == "evidence" else "UNKNOWN" if helper else "CANCELLED", reply["task"]["outcome"])
        self.assertEqual(not helper, reply["observation"] is None)
        self.assertIsNone(reply["closed"])
        self.assertIsNotNone(reply["pending"])
        from admin.local_hand_system_manager.task_service import PhaseClient, TaskStopped
        client = object.__new__(PhaseClient)
        with patch.object(quota_bridge.Client, "call", return_value=copy.deepcopy(reply)):
            with self.assertRaises(TaskStopped) as stopped:
                client.call("snapshot")
        self.assertEqual(reply, stopped.exception.snapshot)
        self.command("finish")
        self.assertTrue(self.session.finished)
        self.assertIsNone(self.session.failure)
        self.assertEqual(len(previous)+1, len(self.f.runner.starts))
        deliveries = self.f.row()["record"]["delivery_intents"]
        self.assertEqual(helper, execution + ":helper" in deliveries)
        self.assertEqual(reader, execution + ":result_reader" in deliveries)

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
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            record = state.get("job", self.f.identity)["record"]
            if "preflight" in record.get("quota_preparations", {}):
                break
            time.sleep(0.01)
        self.assertIn("preflight", record.get("quota_preparations", {}))
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
            self.assertEqual(0, tx.execute("SELECT count(*) FROM leases WHERE owner=?", (self.f.identity,)).fetchone()[0])
            self.assertEqual(6, tx.execute("SELECT count(*) FROM leases").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
