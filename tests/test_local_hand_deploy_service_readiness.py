"""Exercise delayed real Unix listeners without controlling host services."""
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from admin.local_hand_deploy.runtime import PlanningEnvironment
from admin.local_hand_deploy.model import DeployError
from admin.local_hand_deploy.services import SystemdAdapter, definition_digest
from admin.local_hand_deploy.supervision import SupervisedRunner
from local_hand_jobs import cli, startup


class ServiceReadinessTests(unittest.TestCase):
    environment_type = PlanningEnvironment

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'control.sock'
        self.profile = {'owner_uid': os.geteuid(), 'timeout_seconds': 1,
            'systemd': {'units': {'fixture.service': {'component': 'manager'}}},
            'probes': {'manager': {'kind': 'resident', 'socket': str(self.path),
                'peer_uid': os.geteuid(), 'principal_id': 'fixture'}}}
        self.env = self.environment_type(self.profile)

    def listener(self, *, refused=False, loaded=None, initializing=False):
        if refused:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.bind(str(self.path))
        pid = os.fork()
        if pid == 0:
            try:
                time.sleep(0.15)
                if refused:
                    self.path.unlink()
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                    server.bind(str(self.path)); server.listen(1); server.settimeout(3)
                    for index in range(2 if initializing else 1):
                        conn, _ = server.accept()
                        with conn:
                            deadline = time.monotonic() + 2
                            request = json.loads(cli._read_frame(conn, 4096, deadline=deadline))
                            (self.root / 'request.json').write_text(json.dumps(request))
                            raw = Path('/proc/self/stat').read_text()
                            proof = {'component': 'manager', 'protocol_ready': not initializing or index > 0,
                                'pid': os.getpid(), 'start_ticks': raw[raw.rindex(')') + 2:].split()[19],
                                'boot_id': startup.boot_id(), 'configuration_digest': 'a' * 64,
                                'deployment_digest': 'b' * 64, 'invocation_id': 'fixture', **(loaded or {})}
                            result = (proof if self.profile['probes']['manager']['kind'] == 'mcp'
                                      else {'maintenance_supported': True, 'loaded': proof})
                            cli._send_frame(conn, {'result': result}, deadline=deadline, limit=65536)
                # Keep /proc identity available until the parent finishes proof checks.
                time.sleep(3)
                os._exit(0)
            except BaseException:
                os._exit(1)
        def finish():
            try: os.kill(pid, signal.SIGTERM)
            except ProcessLookupError: pass
            os.waitpid(pid, 0)
        self.addCleanup(finish)
        return pid

    def test_absent_manager_socket_waits_for_real_guarded_response(self):
        pid = self.listener()
        result = self.env._loaded('fixture.service')
        self.assertEqual(pid, result['pid'])
        self.assertEqual('a' * 64, result['config_digest'])
        self.assertEqual('deployment_observe', json.loads((self.root / 'request.json').read_text())['action'])

    def test_refused_mcp_socket_waits_for_real_guarded_response(self):
        self.profile['probes']['manager']['kind'] = 'mcp'
        pid = self.listener(refused=True)
        self.assertEqual(pid, self.env._loaded('fixture.service')['pid'])

    def test_persistent_absence_is_bounded_and_preserves_error(self):
        self.profile['timeout_seconds'] = 0.12
        start = time.monotonic()
        with self.assertRaises(FileNotFoundError) as caught:
            self.env._loaded('fixture.service')
        self.assertEqual(str(self.path), caught.exception.filename)
        self.assertLess(time.monotonic() - start, 1)

    def test_mcp_http_initialization_waits_for_same_valid_peer(self):
        self.profile['probes']['manager']['kind'] = 'mcp'
        pid = self.listener(initializing=True)
        proof = self.env._loaded('fixture.service')
        self.assertEqual(pid, proof['pid'])
        self.assertIs(proof['protocol_ready'], True)

    def test_malformed_readiness_is_not_accepted_as_initializing(self):
        self.listener(loaded={'protocol_ready': 0})
        with self.assertRaises(DeployError) as caught:
            self.env._loaded('fixture.service')
        self.assertEqual('UNGUARDED_ENTRY', caught.exception.code)

    def test_expired_deadline_prevents_socket_connect(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(self.path)); server.listen(1)
            with patch('admin.local_hand_deploy.runtime.socket.socket') as connect:
                with self.assertRaises(TimeoutError):
                    self.env._probe('manager', deadline=time.monotonic() - 1)
            connect.assert_not_called()

    def test_invalid_proof_and_permission_errors_are_not_retried(self):
        for error in (DeployError('UNGUARDED_ENTRY', 'untrusted'), PermissionError('denied')):
            with self.subTest(error=error), patch.object(self.env, '_probe', side_effect=error) as probe:
                with self.assertRaises(type(error)):
                    self.env._loaded('fixture.service')
                self.assertEqual(1, probe.call_count)

    def test_socket_owner_checks_still_reject_regular_files(self):
        self.path.write_bytes(b'not a socket')
        with self.assertRaises(DeployError) as caught:
            self.env._loaded('fixture.service')
        self.assertEqual('UNTRUSTED_PROBE', caught.exception.code)

    def test_real_listener_cannot_claim_another_pid(self):
        self.listener(loaded={'pid': 0})
        with self.assertRaises(DeployError) as caught:
            self.env._loaded('fixture.service')
        self.assertEqual('UNGUARDED_ENTRY', caught.exception.code)

    def test_completed_start_resumes_after_probe_failure_without_redispatch(self):
        # Model only systemd. Use its real adapter, forked supervisor, retained
        # attempt, and a real peer-credential probe for the failed readback path.
        pid = self.listener()
        effect = self.root / 'started'
        value = {'LoadState': 'loaded', 'ActiveState': 'inactive', 'UnitFileState': 'disabled',
            'Type': 'exec', 'KillMode': 'control-group', 'Restart': 'no', 'Job': [0, '/'],
            'MainPID': 0, 'InvocationID': ''}
        class Bus:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def unit(self, name):
                return {**value, **({'ActiveState': 'active', 'MainPID': pid,
                    'InvocationID': 'fixture'} if effect.exists() else {})}
            def jobs(self): return []
            def fence_sender(self, sender): return {'closed': True}
            def run_job(self, unit, method, emit, mode=None):
                with effect.open('x') as out: out.write(method)
                emit({'kind': 'bus_binding', 'sender': ':fixture'})
                emit({'kind': 'dispatching'})
                emit({'kind': 'job_accepted', 'job_path': '/fixture/job'})
                emit({'kind': 'job_removed', 'job_path': '/fixture/job', 'result': 'done'})
                return {'done': True}
        fd = os.open(self.root / 'lock', os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, fd); fcntl.flock(fd, fcntl.LOCK_EX)
        runner = SupervisedRunner(self.root / 'calls', timeout=1)
        guard = lambda target, wanted: {**wanted, 'descriptor_digest': 'c' * 64,
            'mode': 'candidate', 'target_running': True, 'boot': startup.boot_id()}
        adapter = SystemdAdapter(self.profile['systemd'], runner, bus_factory=Bus,
            loaded_probe=self.env._loaded, guard_check=guard)
        action = {'kind': 'service_start', 'target': 'fixture.service',
            'before': adapter._snapshot(Bus(), 'fixture.service'),
            'after': {'definition_digest': definition_digest(value),
                      'config_digest': 'a' * 64, 'deployment_digest': 'b' * 64}}
        intents = []
        with patch.object(adapter, 'loaded_probe', side_effect=FileNotFoundError('old immediate probe')):
            with self.assertRaises(FileNotFoundError):
                adapter.execute(action, attempt_id='one', lock_fd=fd, persist_intent=intents.append)
        original = effect.stat()
        with patch.object(runner, 'run', side_effect=AssertionError('must not restart')):
            result = adapter.execute(action, attempt_id='one', previous=intents[0],
                                     lock_fd=fd, persist_intent=Mock())
        self.assertTrue(result['postcondition'], result)
        self.assertEqual(1, len(intents))
        self.assertEqual((original.st_ino, original.st_mtime_ns),
                         (effect.stat().st_ino, effect.stat().st_mtime_ns))


if __name__ == '__main__': unittest.main()
