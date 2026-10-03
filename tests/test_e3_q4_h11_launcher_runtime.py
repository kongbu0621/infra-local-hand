"""H11 launcher process handoff with real sockets, PIDs, pidfds and EOF.

Host systemd/quota commands stay explicit models, so this is not fixture
acceptance.  Unlike the protocol-unit tests, however, the launcher runs its
complete H11 branch: it kills one real origin process through the retained
pidfd, observes coordinator EOF, creates a different recovery process/channel,
and consumes that process's bounded result/EOF.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import stat
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

import test_e3_quota_q2_launcher as base

launcher = base.launcher

if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import q2_assembly, q2_capture, q2_coordinator, q2_management
    from admin.local_hand_system_manager import server
    from local_hand_jobs import budget, quota_bridge, runner, system_manager_protocol
    from q2_fixtures import BOOT, SECOND


CHILD = r"""
import json, signal, socket, sys
value = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
if value['schema'] == 'local-hand-q4-h11-origin-resident/v1':
    bridge = socket.socket(fileno=value['bridge']['fd'])
    bridge.send(b'prepared')
    while True:
        signal.pause()
else:
    plan = value['recovery']
    result = dict(schema='local-hand-q4-h11-recovery-result/v1', status='RECOVERY_RECORDED',
        operation_id=plan['operation_id'], execution_id=plan['execution_id'], phase=plan['phase'],
        original_event_seq=plan['event_seq'], recovery_event_seq=plan['event_seq'] + 3,
        event_kinds=['RECOVERY_BARRIER', 'QUOTA_EXIT_PENDING'], ticks=2, units=plan['units'],
        original_deadline_ns=plan['budget_deadline_ns'], phase_deadline_ns=plan['phase_deadline_ns'],
        controller_deadline_ns=plan['controller_deadline_ns'], future_start_blocked=True,
        tree_exited=True, writers_stopped=True, collectors_stopped=False, effects_checked=False,
        outcome='UNKNOWN', leases_retained=True, result_reread=False, start_replayed=False,
        q3_accepted=False, production_supported=False)
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
"""


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux pidfd H11 launcher handoff")
class H11LauncherProcessTests(unittest.TestCase):
    def setUp(self):
        fixture = base.LauncherOrderingTests()
        with mock.patch.object(base.Path, "home", return_value=Path("/tmp")):
            fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.repository = fixture.repository
        self.value = fixture.value
        self.prepared = fixture.prepared
        self.value.update(schema=launcher.H11_SCHEMA, purpose=launcher.H11_PURPOSE)
        ordinary = self.value["resident"]["ordinary"]
        ordinary["manager_binding"] = dict(schema="local-hand-manager-binding/v1", manager_kind="system",
            authority_id="h11-fixture-authority", boot_id=BOOT, parent=copy.deepcopy(ordinary["parent"]))
        self.value["resident"].update(schema="local-hand-q4-h11-origin-resident/v1",
            purpose="ISOLATED_Q4_H11_ORIGIN", phases=["preflight"])
        self.value["resident"]["policy"] = {
            "path": "/modeled/h11-policy.json", "digest": "d" * 64}
        self.value["resident"]["request"]["request_digest"] = "f" * 64
        recovery = self.repository / "tests/e3_host/q4_h11_recovery.py"
        self.value["recovery_case"] = dict(path=str(recovery), sha256=hashlib.sha256(recovery.read_bytes()).hexdigest())
        self.value["source"]["files"]["tests/e3_host/q4_h11_recovery.py"] = self.value["recovery_case"]["sha256"]
        self.clock = dict(boot_id=BOOT, boottime_ns=2 * SECOND)
        self.authorized = threading.Event()
        self.gateways = []

    def test_complete_origin_kill_and_recovery_peer_replacement(self):
        test = self
        spawned = []
        real_popen = launcher.subprocess.Popen

        def spawn(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            spawned.append(process)
            return process

        def directory(pin, mode):
            fd = os.open(pin["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode)) != (pin["device"], pin["inode"], mode):
                os.close(fd)
                raise ValueError("MODELED_DIRECTORY")
            with os.scandir(fd) as entries:
                if next(entries, None) is not None:
                    os.close(fd)
                    raise ValueError("LAUNCHER_ALREADY_CONSUMED")
            return fd

        class BridgeChannel:
            def __init__(self, sock, **unused):
                self.sock = sock
            def _time(self):
                return test.clock["boottime_ns"]
            def receive(self):
                if self.sock.recv(32) != b"prepared":
                    raise ValueError("MODELED_PREPARED")
                return copy.deepcopy(test.prepared)
            def close(self):
                self.sock.close()

        class Coordinator:
            def __init__(self, config, envelope, record, channel):
                self.channel = channel
            def run(self):
                # The prepared datagram was consumed above. Only death of the
                # actual origin peer can produce EOF on this inherited socket.
                try:
                    while self.channel.sock.recv(1):
                        pass
                except OSError:
                    pass
                error = RuntimeError("origin bridge peer exited")
                error.code = "BRIDGE_PEER_EXITED"
                raise error

        class ManagerChannel:
            def __init__(self, sock, **kwargs):
                self.sock = sock
                self.peer = kwargs["peer"]
                self.session_id = kwargs["session_id"]
            def close(self):
                self.sock.close()

        class Gateway:
            def __init__(self, channel, **kwargs):
                self.channel = channel
                self.old_peer = channel.peer[0]
                self.new_peer = None
                self.failure = None
                self.recovery_only = False
                self.recovery_finished = False
                self.recovery_armed = False
                self.recovery_arm_ack = False
                self.recovery_plan = None
                self.closed = False
                test.gateways.append(self)
            def authorize_phase(self, plan, execution, grant, config):
                operation = test.value["resident"]["request"]["operation_id"]
                execution_id = plan["execution_id"]
                units = {stage: "lhj-" + hashlib.sha256(
                    (execution_id + ("" if stage == "helper" else ":" + stage)).encode()).hexdigest() + ".service"
                    for stage in ("bootstrap", "helper", "result_reader")}
                data = grant.as_dict()["budget"]
                self.recovery_plan = dict(schema="local-hand-q4-h11-recovery-plan/v1", namespace="job",
                    operation_id=operation, request_digest=test.value["resident"]["request"]["request_digest"],
                    phase="preflight", execution_id=execution_id, event_seq=17, handle_sha256="e" * 64,
                    budget_deadline_ns=data["deadline_boottime_ns"],
                    phase_deadline_ns=budget.phase_deadline_ns(data),
                    controller_deadline_ns=test.value["controller_envelope"]["deadline_ns"],
                    collector_started=False, units=units)
                test.authorized.set()
            def serve(self):
                if not self.recovery_only:
                    if not test.authorized.wait(3):
                        raise ValueError("MODELED_ARM_TIMEOUT")
                    self.recovery_armed = True
                    self.recovery_arm_ack = True
                    return
                self.recovery_finished = True
            def rebind_recovery(self, channel):
                old = self.channel
                self.new_peer = channel.peer[0]
                if self.new_peer == self.old_peer:
                    raise ValueError("MODELED_PEER_REUSE")
                try:
                    os.kill(self.old_peer, 0)
                except ProcessLookupError:
                    pass
                else:
                    raise ValueError("MODELED_OLD_PEER_ALIVE")
                old.close()
                self.channel = channel
                self.recovery_only = True
            def close(self):
                self.closed = True
            def snapshot(self):
                return dict(schema="modeled-h11-gateway/v1", old_peer=self.old_peer,
                    new_peer=self.new_peer, recovery_armed=self.recovery_armed,
                    recovery_finished=self.recovery_finished)

        def capture(process, **kwargs):
            stdout, stderr = process.communicate(timeout=5)
            return dict(schema="local-hand-q2-outer-capture/v1", client_pid=process.pid,
                returncode=process.returncode, stdout=stdout, stderr=stderr, eof=["stdout", "stderr"],
                pipe_identities={}, error=None, complete=True, started_ns=kwargs["started_ns"],
                deadline_ns=kwargs["deadline_ns"], independent_stop_required=True,
                production_supported=False, q3_accepted=False)

        def install(template, grant, **unused):
            return dict(config=SimpleNamespace(), management_record={"fixed": True})

        class Record:
            def __init__(self, pin):
                self.pin = pin
            def close(self):
                pass

        patches = [
            mock.patch.object(launcher, "protected", return_value=b"modeled protected executable"),
            mock.patch.object(launcher, "controller", return_value=dict(self.clock)),
            mock.patch.object(launcher, "directory", side_effect=directory),
            mock.patch.object(launcher, "command", side_effect=lambda value, path, digest:
                              [sys.executable, "-B", "-c", CHILD, path]),
            mock.patch.object(launcher.subprocess, "Popen", side_effect=spawn),
            mock.patch.object(budget, "current_clock", return_value=dict(self.clock)),
            mock.patch.object(quota_bridge, "Channel", BridgeChannel),
            mock.patch.object(quota_bridge, "Client", side_effect=lambda channel: channel),
            mock.patch.object(system_manager_protocol, "Channel", ManagerChannel),
            mock.patch.object(server, "Gateway", Gateway),
            mock.patch.object(runner, "_quota_prepared_execution", return_value={}),
            mock.patch.object(runner, "quota_bootstrap_argv", return_value=["modeled-bootstrap"]),
            mock.patch.object(q2_assembly, "install", side_effect=install),
            mock.patch.object(q2_management, "controller"),
            mock.patch.object(q2_management, "RunRecord", Record),
            mock.patch.object(q2_coordinator, "Coordinator", Coordinator),
            mock.patch.object(q2_capture, "capture_existing", side_effect=capture),
        ]
        for item in patches:
            item.start()
        try:
            result = launcher.run(self.value, self.repository)
        finally:
            for item in reversed(patches):
                item.stop()
            for process in spawned:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=3)

        self.assertEqual("RECOVERY_RECORDED", result["status"], result)
        self.assertNotEqual(result["original_resident_pid"], result["recovery_resident_pid"])
        self.assertEqual(-signal.SIGKILL, result["origin_capture"]["returncode"])
        self.assertEqual({"status": "ORIGIN_PEER_EXITED", "reason": "BRIDGE_PEER_EXITED"},
                         result["origin_coordinator"])
        gateway = self.gateways[0]
        self.assertEqual(result["original_resident_pid"], gateway.old_peer)
        self.assertEqual(result["recovery_resident_pid"], gateway.new_peer)
        self.assertTrue(gateway.recovery_armed)
        self.assertTrue(gateway.recovery_finished)
        self.assertTrue((self.root / "output/origin-capture.json").is_file())
        self.assertTrue((self.root / "output/recovery.json").is_file())


if __name__ == "__main__":
    unittest.main()
