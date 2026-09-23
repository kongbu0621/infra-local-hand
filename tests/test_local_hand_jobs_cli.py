from __future__ import annotations

import os
import io
import json
from pathlib import Path
import socket
import stat
import struct
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs.cli import MaintenanceServer, request, _read_frame, create_broker, broker_main
from local_hand_jobs.contract import JobError, Principal


class SameBroker:
    def __init__(self):
        self.calls = []

    def call(self, tool, arguments, principal):
        self.calls.append((tool, arguments, principal))
        if "lh:read" not in principal.scopes:
            raise JobError("UNAUTHORIZED", "No read permission")
        return {"operation_id": "synthetic", "outcome": "UNKNOWN"}


class SyntheticPeerConnection:
    """Transport-level fixture, deliberately not claimed as a real Unix socket."""
    def __init__(self, raw):
        self.input = struct.pack("!I", len(raw)) + raw
        self.output = b""
    def settimeout(self, _): pass
    def getsockopt(self, *_): return struct.pack("3i", 123, os.geteuid(), os.getegid())
    def recv(self, length):
        value, self.input = self.input[:length], self.input[length:]
        return value
    def sendall(self, raw): self.output += raw
    def close(self): pass


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "broker.sock"
        self.broker = SameBroker()
        self.principal = Principal("synthetic", frozenset({"lh:read"}))

    def start(self, peers=None):
        server = MaintenanceServer(self.broker, self.path, peers if peers is not None else {os.geteuid(): self.principal})
        server.start(); self.addCleanup(server.close)
        return server

    def test_same_broker_and_os_peer_identity(self):
        raw = json.dumps({"tool": "lh_job_status", "arguments": {"operation_id": "synthetic"}}).encode()
        result = self.handle(raw)["result"]
        self.assertEqual("UNKNOWN", result["outcome"])
        self.assertIs(self.principal, self.broker.calls[0][2])

    def test_unmapped_peer_cannot_self_identify(self):
        raw = json.dumps({"tool": "lh_job_status", "arguments": {"principal": "synthetic"}}).encode()
        result = self.handle(raw, {})
        self.assertEqual("UNAUTHORIZED", result["error"]["code"])
        self.assertFalse(self.broker.calls)

    def test_raw_duplicate_keys_rejected_before_broker(self):
        raw = b'{"tool":"first","tool":"second","arguments":{}}'
        self.assertEqual("INVALID_REQUEST", self.handle(raw)["error"]["code"])
        self.assertFalse(self.broker.calls)

    def test_existing_socket_path_never_deleted(self):
        self.path.write_text("concurrent file")
        with self.assertRaises(JobError):
            MaintenanceServer(self.broker, self.path, {}).start()
        self.assertEqual("concurrent file", self.path.read_text())

    def test_unavailable_broker_does_not_execute_locally(self):
        with self.assertRaises(JobError) as raised:
            request(self.path, "lh_job_submit", {})
        self.assertEqual("IO_UNCERTAIN", raised.exception.code)
        self.assertFalse(self.broker.calls)

    def test_non_linux_factory_fails_before_runner_or_private_config_import(self):
        with patch("local_hand_jobs.cli.sys.platform", "win32"), self.assertRaises(JobError) as raised:
            create_broker("not-read", actual_entrypoint="not-read")
        self.assertEqual("UNSUPPORTED", raised.exception.code)

    def test_handler_thread_start_failure_releases_connection_and_slot(self):
        server = MaintenanceServer(self.broker, self.path, {}, max_clients=1)
        connection = Mock()
        server._listener = Mock()
        server._listener.accept.side_effect = [(connection, None), OSError("listener stopped")]
        with patch("local_hand_jobs.cli.threading.Thread.start", side_effect=RuntimeError("no thread capacity")):
            server._serve()
        connection.close.assert_called_once()
        self.assertTrue(server._slots.acquire(blocking=False))
        self.assertEqual(2, server._listener.accept.call_count)
        self.assertFalse(self.broker.calls)

    def test_close_after_listener_thread_failed_to_start(self):
        server = MaintenanceServer(self.broker, self.path, {})
        server._listener = Mock()
        server._thread = threading.Thread(target=lambda: None)
        server.close()
        server._listener.close.assert_called_once()

    @unittest.skipUnless(hasattr(os, "mknod"), "Socket inode fixture requires POSIX mknod")
    def test_startup_chmod_failure_removes_only_its_socket(self):
        # A real socket-type inode and injected listener failure test startup
        # ownership cleanup without claiming a real AF_UNIX transport roundtrip.
        listener = Mock()
        listener.bind.side_effect = lambda path: os.mknod(path, stat.S_IFSOCK | 0o600)
        server = MaintenanceServer(self.broker, self.path, {})
        with patch("local_hand_jobs.cli.socket.socket", return_value=listener), \
                patch.object(Path, "chmod", side_effect=OSError("synthetic chmod failure")):
            with self.assertRaises(JobError) as caught:
                server.start()
        self.assertEqual("IO_UNCERTAIN", caught.exception.code)
        self.assertFalse(self.path.exists(), "An owned failed-start socket blocks the next broker")
        listener.close.assert_called_once()

    @unittest.skipUnless(hasattr(os, "mknod"), "Socket inode fixture requires POSIX mknod")
    def test_startup_listen_failure_removes_only_its_socket(self):
        listener = Mock()
        listener.bind.side_effect = lambda path: os.mknod(path, stat.S_IFSOCK | 0o600)
        listener.listen.side_effect = OSError("synthetic listen failure")
        server = MaintenanceServer(self.broker, self.path, {})
        with patch("local_hand_jobs.cli.socket.socket", return_value=listener):
            with self.assertRaises(JobError) as caught:
                server.start()
        self.assertEqual("IO_UNCERTAIN", caught.exception.code)
        self.assertFalse(self.path.exists(), "An owned failed-start socket blocks the next broker")
        listener.close.assert_called_once()

    @unittest.skipUnless(hasattr(os, "mknod"), "Socket inode fixture requires POSIX mknod")
    def test_startup_failure_preserves_a_replacement_entry(self):
        listener = Mock()
        listener.bind.side_effect = lambda path: os.mknod(path, stat.S_IFSOCK | 0o600)
        def replace_then_fail(_):
            self.path.unlink()
            self.path.write_text("concurrent replacement")
            raise OSError("synthetic listen failure after replacement")
        listener.listen.side_effect = replace_then_fail
        server = MaintenanceServer(self.broker, self.path, {})
        with patch("local_hand_jobs.cli.socket.socket", return_value=listener):
            with self.assertRaises(JobError):
                server.start()
        self.assertEqual("concurrent replacement", self.path.read_text())
        listener.close.assert_called_once()

    @unittest.skipUnless(hasattr(os, "mknod"), "Socket inode fixture requires POSIX mknod")
    def test_second_start_preserves_the_running_listener(self):
        listener, replacement = Mock(), Mock()
        listener.bind.side_effect = lambda path: os.mknod(path, stat.S_IFSOCK | 0o600)
        replacement.bind.side_effect = OSError("already bound")
        server = MaintenanceServer(self.broker, self.path, {})
        with patch("local_hand_jobs.cli.socket.socket", side_effect=[listener, replacement]) as factory, \
                patch("local_hand_jobs.cli.threading.Thread", return_value=Mock(ident=1)):
            server.start()
            try:
                with self.assertRaises(JobError) as caught:
                    server.start()
                self.assertEqual("CONFLICT", caught.exception.code)
                self.assertEqual(1, factory.call_count)
                listener.close.assert_not_called()
                self.assertTrue(stat.S_ISSOCK(self.path.lstat().st_mode))
            finally:
                server.close()

    def test_closed_server_cannot_create_a_new_listener(self):
        server = MaintenanceServer(self.broker, self.path, {})
        server.close()
        with patch("local_hand_jobs.cli.socket.socket") as factory:
            with self.assertRaises(JobError) as caught:
                server.start()
        self.assertEqual("CONFLICT", caught.exception.code)
        factory.assert_not_called()

    def test_slow_frame_cannot_renew_the_server_deadline(self):
        elapsed = [0.0]
        raw = json.dumps({"tool": "lh_job_status", "arguments": {}}).encode()
        connection = SyntheticPeerConnection(raw)
        original = connection.recv
        def trickle(length):
            elapsed[0] += 0.4
            return original(min(length, 1))
        connection.recv = trickle
        server = MaintenanceServer(self.broker, self.path, {os.geteuid(): self.principal}, response_seconds=2)
        server._slots.acquire()
        with patch("local_hand_jobs.cli.time", SimpleNamespace(monotonic=lambda: elapsed[0]), create=True):
            server._handle(connection)
        self.assertEqual([], self.broker.calls)
        self.assertLessEqual(elapsed[0], 2.4)

    def test_private_control_budget_tightens_the_server_frame_deadline(self):
        self.broker.policy = SimpleNamespace(limits={"control_response_seconds": 1})
        elapsed = [0.0]
        raw = json.dumps({"tool": "lh_job_status", "arguments": {}}).encode()
        connection = SyntheticPeerConnection(raw)
        original = connection.recv
        def trickle(length):
            elapsed[0] += 0.4
            return original(min(length, 1))
        connection.recv = trickle
        server = MaintenanceServer(self.broker, self.path, {os.geteuid(): self.principal})
        server._slots.acquire()
        with patch("local_hand_jobs.cli.time", SimpleNamespace(monotonic=lambda: elapsed[0])):
            server._handle(connection)
        self.assertEqual([], self.broker.calls)
        self.assertLessEqual(elapsed[0], 1.21)

    def test_slow_response_cannot_renew_the_client_deadline(self):
        elapsed = [0.0]
        connection = SyntheticPeerConnection(b'{"result":{"outcome":"UNKNOWN"}}')
        connection.connect = lambda path: None
        original = connection.recv
        def trickle(length):
            elapsed[0] += 0.4
            return original(min(length, 1))
        connection.recv = trickle
        with patch("local_hand_jobs.cli.socket.socket", return_value=connection), \
                patch("local_hand_jobs.cli.time", SimpleNamespace(monotonic=lambda: elapsed[0]), create=True):
            with self.assertRaises(JobError) as caught:
                request(self.path, "lh_job_status", {}, timeout=2)
        self.assertEqual(caught.exception.code, "IO_UNCERTAIN")
        self.assertLessEqual(elapsed[0], 2.4)

    def test_response_json_is_unambiguous_and_envelope_is_exact(self):
        for raw in (b'{"result":{"outcome":"FAILED"},"result":{"outcome":"SUCCEEDED"}}',
                    b'{"result":{"observed_at":NaN}}', b'{"result":{"text":"\\ud800"}}',
                    b'{"result":{},"unexpected":true}', b'{"result":[],"error":{}}', b'[]'):
            connection = SyntheticPeerConnection(raw)
            connection.connect = lambda path: None
            with self.subTest(raw=raw), patch("local_hand_jobs.cli.socket.socket", return_value=connection):
                with self.assertRaises(JobError) as caught:
                    request(self.path, "lh_job_status", {})
                self.assertEqual(caught.exception.code, "IO_UNCERTAIN")

    def test_finite_status_timestamp_and_large_evidence_response_remain_valid(self):
        result = {"observed_at": 1234.125, "data_base64": "eA==" * 50000}
        connection = SyntheticPeerConnection(json.dumps({"result": result}).encode())
        connection.connect = lambda path: None
        with patch("local_hand_jobs.cli.socket.socket", return_value=connection):
            self.assertEqual(request(self.path, "lh_evidence_read_chunk", {}), result)

    def test_invalid_transport_budgets_fail_before_opening_a_connection(self):
        for budget in (True, 0, -1, float("inf"), float("nan")):
            with self.subTest(budget=budget), patch("local_hand_jobs.cli.socket.socket") as make_socket:
                with self.assertRaises(JobError):
                    request(self.path, "lh_job_status", {}, timeout=budget)
                make_socket.assert_not_called()
                with self.assertRaises(JobError):
                    MaintenanceServer(self.broker, self.path, {}, response_seconds=budget)

    def test_close_blocks_handlers_which_have_not_entered_the_broker(self):
        raw = json.dumps({"tool": "lh_job_status", "arguments": {}}).encode()
        server = MaintenanceServer(self.broker, self.path, {os.geteuid(): self.principal})
        server._slots.acquire()
        server.close()
        server._handle(SyntheticPeerConnection(raw))
        self.assertEqual([], self.broker.calls)
        self.assertTrue(server._slots.acquire(blocking=False))

    def test_close_does_not_forget_a_call_already_inside_the_broker(self):
        entered, release, completed = threading.Event(), threading.Event(), threading.Event()
        original = self.broker.call
        def blocked(*args):
            entered.set()
            release.wait(timeout=3)
            result = original(*args)
            completed.set()
            return result
        raw = json.dumps({"tool": "lh_job_status", "arguments": {}}).encode()
        connection = SyntheticPeerConnection(raw)
        connection.shutdown = Mock()
        server = MaintenanceServer(self.broker, self.path, {os.geteuid(): self.principal}, max_clients=1)
        server._slots.acquire()
        server._connections.add(connection)
        with patch.object(self.broker, "call", side_effect=blocked):
            handler = threading.Thread(target=server._handle, args=(connection,), daemon=True)
            handler.start()
            try:
                self.assertTrue(entered.wait(timeout=1))
                server.close()
                connection.shutdown.assert_called_once_with(socket.SHUT_RDWR)
                self.assertFalse(completed.is_set())
                self.assertFalse(server._slots.acquire(blocking=False))
            finally:
                release.set()
                handler.join(timeout=1)
        self.assertFalse(handler.is_alive())
        self.assertEqual(len(self.broker.calls), 1)
        self.assertTrue(server._slots.acquire(blocking=False))

    def test_failed_broker_composition_closes_the_opened_state(self):
        authority_root = Path(self.temp.name) / "authority"
        authority_root.mkdir(mode=0o700)
        (authority_root / "authority.json").write_text('{"ledger_id":"synthetic-ledger"}')
        policy = SimpleNamespace(config={}, source_commit="a" * 40, installed_payload_digest="b" * 64,
            execution_entrypoint="synthetic", broker_root=str(Path(self.temp.name) / "broker"),
            authority_root=str(authority_root), authority_id="synthetic-authority", limits={"retained_bytes":1024})
        state = unittest.mock.MagicMock()
        state.all.return_value = []
        authority = Mock()
        manager = Mock()
        manager.support.return_value = {"supported": True}
        manager.scan.return_value = {"status": "READY"}
        with patch("local_hand_jobs.policy.Policy.from_file", return_value=policy), \
                patch("local_hand_jobs.deployment.verify_release"), \
                patch("local_hand_jobs.resources.verify_local_filesystem"), \
                patch("local_hand_jobs.resources.AuthorityLock", return_value=authority), \
                patch("local_hand_jobs.runner.SystemdManager", return_value=manager), \
                patch("local_hand_jobs.state.StateStore", return_value=state), \
                patch("local_hand_jobs.broker.Broker"), \
                patch("local_hand_jobs.evidence.EvidenceStore", side_effect=JobError("IO_UNCERTAIN", "synthetic construction failure")):
            with self.assertRaises(JobError):
                create_broker("synthetic", actual_entrypoint="synthetic")
        state.close.assert_called_once()
        authority.close.assert_called_once()

    def test_service_teardown_attempts_every_resource_after_each_close_failure(self):
        for failed_resource in ("transport", "broker", "state", "authority"):
            with self.subTest(failed_resource=failed_resource):
                broker, server = Mock(), Mock()
                broker.policy = SimpleNamespace(local_peers={}, principals={}, broker_root=self.temp.name)
                attempted = []
                failure = OSError("synthetic service cleanup failure")
                def close(name):
                    attempted.append(name)
                    if name == failed_resource:
                        raise failure
                for name, resource in (("transport", server), ("broker", broker),
                                       ("state", broker.state), ("authority", broker.authority_lock)):
                    resource.close.side_effect = lambda name=name: close(name)
                with patch("local_hand_jobs.cli.create_broker", return_value=broker), \
                        patch("local_hand_jobs.cli.MaintenanceServer", return_value=server), \
                        patch("local_hand_jobs.cli.threading.Event") as event:
                    event.return_value.wait.side_effect = KeyboardInterrupt
                    # An already-handled caller exception must not suppress a
                    # cleanup failure in an otherwise successful service body.
                    try:
                        raise ValueError("unrelated caller error")
                    except ValueError:
                        with self.assertRaises(OSError) as caught:
                            broker_main(["--policy", "synthetic"])
                self.assertIs(failure, caught.exception)
                self.assertEqual(["transport", "broker", "state", "authority"], attempted)

    def test_startup_error_survives_all_service_teardown_failures(self):
        broker, server = Mock(), Mock()
        broker.policy = SimpleNamespace(local_peers={}, principals={}, broker_root=self.temp.name)
        broker.start.side_effect = JobError("IO_UNCERTAIN", "synthetic primary startup failure")
        resources = (server, broker, broker.state, broker.authority_lock)
        for resource in resources:
            resource.close.side_effect = OSError("synthetic cleanup failure")
        stderr = io.StringIO()
        with patch("local_hand_jobs.cli.create_broker", return_value=broker), \
                patch("local_hand_jobs.cli.MaintenanceServer", return_value=server), \
                patch("local_hand_jobs.cli.sys.stderr", stderr):
            result = broker_main(["--policy", "synthetic"])
        self.assertEqual(2, result)
        self.assertIn("synthetic primary startup failure", stderr.getvalue())
        self.assertNotIn("synthetic cleanup failure", stderr.getvalue())
        for resource in resources:
            resource.close.assert_called_once()

    def handle(self, raw, peers=None):
        server = MaintenanceServer(self.broker, self.path, peers if peers is not None else {os.geteuid(): self.principal})
        connection = SyntheticPeerConnection(raw)
        server._slots.acquire()
        server._handle(connection)
        return json.loads(connection.output[4:])

    def test_real_unix_socket_roundtrip_when_host_permits(self):
        try:
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        except PermissionError:
            self.skipTest("UNSUPPORTED: host policy prohibits AF_UNIX sockets; synthetic transport tests are separate")
        else:
            probe.close()
        self.start()
        self.assertEqual("UNKNOWN", request(self.path, "lh_job_status", {})["outcome"])


if __name__ == "__main__":
    unittest.main()
