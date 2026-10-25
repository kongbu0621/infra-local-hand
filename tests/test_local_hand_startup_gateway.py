"""The fixed gateway uses host credentials without weakening MCP startup."""
from contextlib import contextmanager
import copy
import hashlib
import os
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from local_hand_jobs import maintenance, startup
from local_hand_jobs.contract import JobError


class GatewayStartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.gate = maintenance.MaintenanceGate(self.root, 'test-node', owner_uid=os.getuid())
        self.gate.initialize('a' * 64, 'bootstrap', bootstrap=True)
        self.path = self.root / 'selection.json'
        member = self.root / 'member.json'; member.write_bytes(b'{}'); member.chmod(0o600)
        self.config = {'maintenance': {'startup_descriptor': str(self.path)}}
        self.selection = dict(schema=startup.SCHEMA, node_id='test-node', deployment_digest='a' * 64,
            decision_id='bootstrap', owner=None, mode='stable', permit=None,
            members=[dict(path=str(member), sha256=hashlib.sha256(b'{}').hexdigest())],
            components={name: dict(configuration_digest='b' * 64, payload_digest='c' * 64,
                                   entry=entry, running=True) for name, entry in (('gateway', 'public'), ('mcp', 'local'))})
        startup.publish(self.path, self.selection, self.gate, expected_digest=None, owner_uid=os.getuid())

    def candidate(self):
        self.gate.close('deploy')
        value = copy.deepcopy(self.selection)
        value.update(mode='candidate', owner='deploy', decision_id=None,
            permit=dict(boot_id=startup.boot_id(), attempt_id='attempt', claims={}))
        startup.publish(self.path, value, self.gate, expected_digest=startup.digest(self.selection), owner_uid=os.getuid())

    @contextmanager
    def manager(self, mode='candidate', *, peer_uid=0, mcp=False):
        left, right = socket.socketpair(); errors = []
        def serve():
            with left:
                try:
                    if mcp:
                        startup.serve_authorization(left, self.config, self.gate, peer_pid=os.getpid())
                    else:
                        startup.serve_gateway_authorization(left, self.config, self.gate,
                            peer_pid=os.getpid(), peer_uid=peer_uid, mode=mode)
                except BaseException as error: errors.append(error)
        worker = threading.Thread(target=serve, daemon=True); worker.start()
        try:
            yield right, errors
        finally:
            right.close(); worker.join(3)
            self.assertFalse(worker.is_alive(), 'startup manager did not release its connection and gate')

    def proof(self, response, *, entry='local'):
        selected = response['selection']
        return {**response.get('host_instance', startup.instance(os.getpid())), 'component': 'gateway',
                'entry': entry, 'node_id': selected['node_id'], 'deployment_digest': selected['deployment_digest'],
                **{key: selected['components']['gateway'][key] for key in ('configuration_digest', 'payload_digest')}}

    def exchange(self, mode='candidate', transform=None):
        with self.manager(mode) as (connection, errors):
            end = time.monotonic() + 3
            response = startup._frame_read(connection, end)
            proof = self.proof(response, entry='public' if mode == 'public' else 'local')
            if transform is not None: proof = transform(proof)
            startup._frame_send(connection, dict(action='startup_bound', proof=proof), end)
            acknowledged = startup._frame_read(connection, end)
        self.assertEqual([], errors)
        self.assertEqual({'bound': True, 'descriptor_digest': startup.digest(response['selection'])}, acknowledged)
        return response

    def test_candidate_claim_is_actual_host_instance_and_has_separate_component(self):
        self.candidate()
        response = self.exchange()
        self.assertEqual(startup.instance(os.getpid()), response['host_instance'])
        claims = startup.read_selection(self.path, owner_uid=os.getuid())['permit']['claims']
        self.assertEqual({'gateway': startup.instance(os.getpid())}, claims)

    def test_public_cannot_consume_candidate_permit_or_open_before_release(self):
        self.candidate()
        with self.manager('public') as (connection, errors):
            with self.assertRaises(JobError): startup._frame_read(connection, time.monotonic() + 3)
        self.assertEqual(1, len(errors))
        self.assertEqual({}, startup.read_selection(self.path, owner_uid=os.getuid())['permit']['claims'])
        current = startup.read_selection(self.path, owner_uid=os.getuid())
        stable = dict(self.selection, deployment_digest='d' * 64, decision_id='committed')
        startup.publish(self.path, stable, self.gate, expected_digest=startup.digest(current),
                        owner_uid=os.getuid(), maintenance_owner='deploy')
        # Local/status initialization remains live while the durable commit is
        # published but admission has not yet been released.
        self.exchange('candidate')
        with self.manager('public') as (connection, errors):
            with self.assertRaises(JobError): startup._frame_read(connection, time.monotonic() + 3)
        self.assertEqual(1, len(errors))
        self.gate.release('deploy', 'committed', 'd' * 64)
        self.exchange('public')

    def test_original_stable_public_restart_can_serve_reads_while_gate_closed(self):
        self.gate.close('deploy')
        self.exchange('public')
        self.assertEqual('CLOSED', self.gate.snapshot()['state'])

    def test_nonroot_gateway_peer_and_mismatched_host_instance_are_rejected(self):
        with self.manager(peer_uid=12345) as (connection, errors):
            with self.assertRaises(JobError): startup._frame_read(connection, time.monotonic() + 3)
        self.assertEqual('UNAUTHORIZED', errors[0].code)
        for changed in ({'pid': os.getpid() + 1}, {'start_ticks': 1}, {'entry': 'public'},
                        {'configuration_digest': '0' * 64}):
            with self.subTest(changed=changed), self.manager() as (connection, errors):
                end = time.monotonic() + 3
                response = startup._frame_read(connection, end)
                startup._frame_send(connection, dict(action='startup_bound', proof={**self.proof(response), **changed}), end)
                with self.assertRaises(JobError): startup._frame_read(connection, end)
            self.assertEqual('STARTUP_MISMATCH', errors[0].code)

    def test_gateway_claim_and_public_entry_cannot_use_existing_mcp_handshake(self):
        with self.manager(mcp=True) as (connection, errors):
            end = time.monotonic() + 3
            response = startup._frame_read(connection, end)
            startup._frame_send(connection, dict(action='startup_bound', proof=self.proof(response, entry='public')), end)
            with self.assertRaises(JobError): startup._frame_read(connection, end)
        self.assertEqual('STARTUP_MISMATCH', errors[0].code)

    def test_gate_is_held_until_actual_bind_ack_then_released(self):
        closer = None; done = threading.Event(); close_errors = []
        def close():
            try: self.gate.close('deploy')
            except BaseException as error: close_errors.append(error)
            finally: done.set()
        try:
            with self.manager() as (connection, errors):
                end = time.monotonic() + 3
                response = startup._frame_read(connection, end)
                closer = threading.Thread(target=close, daemon=True); closer.start()
                self.assertFalse(done.wait(.1))
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0)); listener.listen()
                    startup._frame_send(connection, dict(action='startup_bound', proof=self.proof(response)), end)
                    self.assertTrue(startup._frame_read(connection, end)['bound'])
            self.assertEqual([], errors)
        finally:
            if closer is not None: closer.join(3)
        self.assertTrue(done.is_set()); self.assertEqual([], close_errors)

    def test_disconnect_does_not_leave_gate_locked(self):
        with self.manager() as (connection, errors):
            startup._frame_read(connection, time.monotonic() + 3)
        self.assertEqual(1, len(errors))
        self.assertEqual('CLOSED', self.gate.close('deploy')['state'])

    def test_public_manager_releases_gate_when_bind_ack_stalls(self):
        started = time.monotonic()
        with self.manager('public') as (connection, errors):
            startup._frame_read(connection, started + 3)
            with self.assertRaises(JobError):
                startup._frame_read(connection, started + 3)
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertEqual(1, len(errors))
        self.assertIsInstance(errors[0].__cause__, TimeoutError)
        self.assertEqual('CLOSED', self.gate.close('deploy')['state'])

    def test_public_client_closes_unresponsive_manager_within_one_second_window(self):
        class Peer:
            def __init__(self, connection): self.connection = connection
            def connect(self, path): pass
            def getsockopt(self, *args): return struct.pack('3i', os.getpid(), 0, 0)
            def __getattr__(self, name): return getattr(self.connection, name)
        left, right = socket.socketpair(); errors = []; requests = []; eof = []
        def stalled_manager():
            with left:
                try:
                    requests.append(startup._frame_read(left, time.monotonic() + 3))
                    left.settimeout(3)
                    eof.append(left.recv(1))
                except BaseException as error: errors.append(error)
        worker = threading.Thread(target=stalled_manager, daemon=True); worker.start()
        started = time.monotonic()
        try:
            with patch.object(startup.socket, 'socket', return_value=Peer(right)):
                with self.assertRaises(TimeoutError):
                    with startup.remote_gateway_authorization('/fixed/manager.sock', mode='public'):
                        self.fail('Unresponsive manager cannot admit a gateway')
            self.assertLess(time.monotonic() - started, 2.5)
        finally:
            right.close(); worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual([], errors)
        self.assertEqual([b''], eof)
        self.assertEqual([{'action': 'startup_authorize', 'component': 'gateway', 'mode': 'public'}], requests)

    def test_client_uses_fixed_gateway_request_and_requires_actual_ack(self):
        # Real framed I/O; only the root manager peer credential is synthesized
        # so this test also runs in ordinary Linux CI.
        class Peer:
            def __init__(self, connection): self.connection = connection
            def connect(self, path): pass
            def getsockopt(self, *args): return struct.pack('3i', os.getpid(), 0, 0)
            def __getattr__(self, name): return getattr(self.connection, name)
        for omit_ack in (False, True):
            left, right = socket.socketpair(); errors = []; requests = []
            def server():
                with left:
                    try:
                        requests.append(startup._frame_read(left, time.monotonic() + 3))
                        startup.serve_gateway_authorization(left, self.config, self.gate,
                            peer_pid=os.getpid(), peer_uid=0, mode='candidate')
                    except BaseException as error: errors.append(error)
            worker = threading.Thread(target=server, daemon=True); worker.start()
            try:
                with patch.object(startup.socket, 'socket', return_value=Peer(right)):
                    if omit_ack:
                        with self.assertRaises(JobError):
                            with startup.remote_gateway_authorization('/fixed/manager.sock'): pass
                    else:
                        with startup.remote_gateway_authorization('/fixed/manager.sock') as (selection, host, acknowledge):
                            acknowledge(self.proof({'selection': selection, 'host_instance': host}))
            finally:
                right.close(); worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual([{'action': 'startup_authorize', 'component': 'gateway', 'mode': 'candidate'}], requests)
            self.assertEqual(1 if omit_ack else 0, len(errors))


if __name__ == '__main__': unittest.main()
