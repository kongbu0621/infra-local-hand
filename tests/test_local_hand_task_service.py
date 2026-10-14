"""Administrator adapter checks; host supervision/quota remain modeled."""
import copy
import os
import select
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

if sys.platform.startswith("linux"):
    from admin.local_hand_system_manager import task_service
    from local_hand_jobs import quota_payload, quota_contract as q, system_manager_protocol as wire
    import test_local_hand_jobs_task_session as session_fixtures
    import test_e3_system_manager_gateway as gateway_fixtures


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux administrator task service")
class TaskServiceTests(unittest.TestCase):
    def test_cancel_uses_bounded_stop_path_and_hides_snapshot_in_exception_text(self):
        coordinator = Mock(management_closed=False)
        coordinator.management.used = True
        result = task_service.finish_stopped_management(coordinator)
        self.assertIs(result, coordinator.management.finish_stopped.return_value)
        coordinator.management.poll.assert_not_called()
        coordinator.management.finish.assert_not_called()
        snapshot = {"token": "private-secret", "path": "/private/host"}
        error = task_service.TaskStopped(snapshot)
        self.assertIs(snapshot, error.snapshot)
        self.assertNotIn("private-secret", str(error))
        self.assertNotIn("/private/host", str(error))

    def test_cancel_after_management_closure_reuses_proof_without_second_finish(self):
        coordinator = Mock(management_closed=True, management_result={"original": "closure"})
        coordinator.management.finish.side_effect = ValueError("MANAGEMENT_RECORD_CLOSED")
        self.assertIs(coordinator.management_result, task_service.finish_stopped_management(coordinator))
        coordinator.management.poll.assert_not_called()
        coordinator.management.finish.assert_not_called()

    def test_api_window_stops_actual_child_by_pidfd_and_waits_for_exit(self):
        code = "import signal,time;signal.signal(signal.SIGINT,lambda *_:exit(0));print('ready',flush=True);time.sleep(10)"
        process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE)
        self.addCleanup(process.stdout.close)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        self.assertEqual(b"ready\n", process.stdout.readline())
        service = task_service.TaskService.__new__(task_service.TaskService)
        service.process, service.value = process, {}
        with tempfile.TemporaryDirectory() as root:
            service.intents = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with patch.object(task_service, "service_command", return_value=[sys.executable, "-c", "unused"]):
                    service.stop_api()
                self.assertEqual(0, process.returncode)
            finally:
                os.close(service.intents)

    def test_original_failure_is_retained_before_recovery_changes_gateway(self):
        service = task_service.TaskService.__new__(task_service.TaskService)
        service.process = Mock()
        service.process.poll.return_value = -9
        service.gateway = Mock()
        service.gateway.snapshot.return_value = {"failure": "SYSTEM_PEER_CHANGED"}
        service.failures = ["QuotaError"]
        with tempfile.TemporaryDirectory() as root:
            service.intents = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                service.retain_failure(ValueError("BRIDGE_PEER_EXITED"))
                from pathlib import Path
                import json
                retained = json.loads(next(Path(root).glob("failure-*.json")).read_text())
                self.assertEqual("BRIDGE_PEER_EXITED", retained["reason"])
                self.assertEqual(-9, retained["returncode"])
                self.assertEqual("SYSTEM_PEER_CHANGED", retained["manager"]["failure"])
            finally:
                os.close(service.intents)

    def test_root_reconstructs_phase_plan_and_rejects_client_command_substitution(self):
        fixture = session_fixtures.TaskSessionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.session.tick()
        prepared = fixture.channel.outgoing[-1]
        grant = fixture.f.make_grant("preflight", prepared["snapshot"]["preparation"])
        expected = task_service.checked_plan(fixture.f.row()["plan"], prepared, grant, {}, None)
        self.assertEqual(grant.as_dict(), expected["quota_observation_grant"])
        tampered = copy.deepcopy(prepared)
        plan = quota_payload.decode_phase_plan(tampered["phase_plan"])
        plan["execution"]["python"] = "/unadmitted/program"
        tampered["phase_plan"] = quota_payload.encode_phase_plan(plan)
        with self.assertRaisesRegex(ValueError, "TASK_PHASE_PLAN"):
            task_service.checked_plan(fixture.f.row()["plan"], tampered, grant, {}, None)

    def test_launcher_uses_real_service_entry_and_fixed_unprivileged_account(self):
        value = dict(transport="broker", mcp=None, setpriv={"path": "/usr/bin/setpriv"},
            python={"path": "/usr/bin/python3"}, policy_path="/private/policy.json",
            policy=dict(process_manager=dict(uid=1234, gid=5678),
                        execution_entrypoint="/installed/local_hand_jobs/cli.py"))
        argv = task_service.service_command(value, "/private/session.json")
        self.assertIn("--reuid=1234", argv)
        self.assertIn("--regid=5678", argv)
        self.assertIn("--bounding-set=-all", argv)
        self.assertIn("broker_main()", argv[argv.index("-c") + 1])
        self.assertEqual("/installed", argv[argv.index("-c") + 2])
        self.assertEqual(["--session", "/private/session.json"], argv[-2:])
        self.assertFalse(any("tests/" in item for item in argv))
        value.update(transport="mcp", mcp=dict(auth_config="/private/auth.json", port=8765))
        argv = task_service.service_command(value, "/private/session.json")
        self.assertIn("local_hand_mcp.server", argv[argv.index("-c") + 1])
        self.assertIn("--auth-config", argv)

    def test_natural_service_crash_recovery_requires_real_peer_exit_without_test_arm(self):
        fixture = gateway_fixtures.GatewayTests()
        gateway, item = fixture.gateway()
        self.addCleanup(fixture.doCleanups)
        fixture.arm(gateway, item)
        gateway.recovery_armed = gateway.recovery_arm_ack = False
        gateway.recovery_plan = None
        gateway.uid, gateway.gid = os.getuid(), os.getgid()
        processes, channels = [], []
        def peer(nonce):
            left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"],
                                       pass_fds=(right.fileno(),), close_fds=True)
            right.close()
            processes.append(process)
            channel = wire.Channel(left, peer=(process.pid, os.getuid(), os.getgid()),
                peer_start_ticks=wire.start_ticks(process.pid), session_id=nonce,
                boot_id=gateway.binding["boot_id"], deadline_ns=gateway.end)
            channels.append(channel)
            return process, channel
        try:
            old_process, old = peer("a" * 64)
            _, new = peer("b" * 64)
            gateway.channel = old
            gateway.peer_pidfd = os.dup(old.pidfd)
            old.total, old.sequence, old.pending = 123, 4, "observe"
            with self.assertRaisesRegex(ValueError, "SYSTEM_RECOVERY_STATE"):
                gateway.rebind_service_recovery(new)
            old_process.terminate()
            old_process.wait(timeout=2)
            self.assertTrue(select.select([gateway.peer_pidfd], [], [], 1)[0])
            gateway.rebind_service_recovery(new)
            self.assertTrue(gateway.recovery_only)
            self.assertTrue(gateway.service_recovery)
            self.assertEqual((123, 4), (gateway.retired_wire_bytes, gateway.retired_calls))
            self.assertTrue(all(part["collectors_lost"] for part in gateway.parts.values()))
            reference = dict(execution_id=item["execution"]["execution_id"], phase="preflight", stage="helper")
            with self.assertRaisesRegex(ValueError, "SYSTEM_RECOVERY_OPERATION"):
                gateway.dispatch("launch", dict(ref=reference,
                    bindings=dict(allocation_digest="a" * 64, grant_digest="b" * 64)))
        finally:
            if getattr(gateway, "peer_pidfd", -1) >= 0:
                os.close(gateway.peer_pidfd)
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=2)
            for channel in channels:
                channel.close()


if __name__ == "__main__":
    unittest.main()
