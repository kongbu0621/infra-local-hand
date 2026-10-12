"""Service session with real SQLite and Unix control transport.

Quota grants and process exit proofs are modeled here; this is not a host run.
"""
import copy
import os
from pathlib import Path
import socket
import sys
import time
import unittest
from unittest.mock import Mock, patch

from local_hand_jobs.contract import JobError, request_digest

if sys.platform.startswith("linux"):
    from local_hand_jobs.task_session import TaskSession
    from local_hand_jobs import quota_closure
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
