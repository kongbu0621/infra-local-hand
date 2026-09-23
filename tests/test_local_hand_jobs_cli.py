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

    def test_handler_start_and_close_failure_does_not_stop_accepting(self):
        server = MaintenanceServer(self.broker, self.path, {}, max_clients=1)
        first, second = Mock(), Mock()
        first.close.side_effect = OSError("synthetic disconnected socket close failure")
        server._listener = Mock()
        server._listener.accept.side_effect = [(first, None), (second, None), OSError("stop")]
        with patch("local_hand_jobs.cli.threading.Thread") as thread:
            thread.return_value.start.side_effect = [RuntimeError("no thread capacity"), None]
            server._serve()
        self.assertEqual(3, server._listener.accept.call_count)
        self.assertNotIn(first, server._connections)
        self.assertIn(second, server._connections)
        self.assertEqual(2, thread.return_value.start.call_count)
        first.close.assert_called_once()
        self.assertFalse(server._slots.acquire(blocking=False))
        self.assertFalse(self.broker.calls)

    def test_rejected_connection_close_errors_preserve_listener_and_capacity(self):
        for reason in ("capacity", "closed"):
            with self.subTest(reason=reason):
                server = MaintenanceServer(self.broker, self.path, {}, max_clients=1)
                connection = Mock()
                connection.close.side_effect = OSError("synthetic rejected close failure")
                server._listener = Mock()
                if reason == "capacity":
                    self.assertTrue(server._slots.acquire(blocking=False))
                    server._listener.accept.side_effect = [(connection, None), OSError("stop")]
                else:
                    def accept_after_close():
                        server._closed.set()
                        return connection, None
                    server._listener.accept.side_effect = accept_after_close
                server._serve()
                connection.close.assert_called_once()
                self.assertFalse(server._connections)
                if reason == "capacity":
                    self.assertEqual(2, server._listener.accept.call_count)
                    self.assertFalse(server._slots.acquire(blocking=False))
                else:
                    self.assertTrue(server._slots.acquire(blocking=False))
                server._slots.release()
                self.assertFalse(self.broker.calls)

    def test_failed_bind_remains_primary_after_unbound_listener_close_failure(self):
        server = MaintenanceServer(self.broker, self.path, {})
        listener = Mock()
        primary = OSError("synthetic bind failure")
        listener.bind.side_effect = primary
        listener.close.side_effect = OSError("synthetic unbound cleanup failure")
        with patch("local_hand_jobs.cli.socket.socket", return_value=listener):
            with self.assertRaises(JobError) as caught:
                server.start()
        self.assertEqual("IO_UNCERTAIN", caught.exception.code)
        self.assertIs(primary, caught.exception.__cause__)
        self.assertTrue(server._closed.is_set())
        self.assertFalse(self.path.exists())

    @unittest.skipUnless(hasattr(os, "mknod"), "Socket inode fixture requires POSIX mknod")
    def test_close_failure_still_releases_connections_and_owned_socket(self):
        for failed_resource in ("listener", "connection", "thread"):
            with self.subTest(failed_resource=failed_resource):
                os.mknod(self.path, stat.S_IFSOCK | 0o600)
                info = self.path.lstat()
                server = MaintenanceServer(self.broker, self.path, {})
                server._identity = (info.st_dev, info.st_ino)
                server._listener = Mock()
                server._connections.update((Mock(), Mock()))
                connections = tuple(server._connections)
                server._thread = Mock(ident=1)
                primary = OSError("synthetic cleanup failure")
                target = {"listener": server._listener.close,
                          "connection": connections[0].close,
                          "thread": server._thread.join}[failed_resource]
                target.side_effect = primary
                # A handled caller error does not hide this method's failure.
                try:
                    raise ValueError("unrelated caller error")
                except ValueError:
                    with self.assertRaises(OSError) as caught:
                        server.close()
                self.assertIs(primary, caught.exception)
                self.assertTrue(server._closed.is_set())
                server._listener.close.assert_called_once()
                for connection in connections:
                    connection.shutdown.assert_called_once_with(socket.SHUT_RDWR)
                    connection.close.assert_called_once()
                server._thread.join.assert_called_once_with(timeout=1)
                self.assertFalse(self.path.exists())

    @unittest.skipUnless(hasattr(os, "mknod"), "Socket inode fixture requires POSIX mknod")
    def test_thread_start_failure_survives_listener_cleanup_failure(self):
        server = MaintenanceServer(self.broker, self.path, {})
        listener = Mock()
        listener.bind.side_effect = lambda path: os.mknod(path, stat.S_IFSOCK | 0o600)
        listener.close.side_effect = OSError("synthetic cleanup failure")
        primary = RuntimeError("synthetic thread-start failure")
        with patch("local_hand_jobs.cli.socket.socket", return_value=listener), \
                patch("local_hand_jobs.cli.threading.Thread.start", side_effect=primary):
            with self.assertRaises(JobError) as caught:
                server.start()
        self.assertEqual("IO_UNCERTAIN", caught.exception.code)
        self.assertIs(primary, caught.exception.__cause__)
        self.assertFalse(self.path.exists())

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

    @unittest.skipUnless(hasattr(os, "O_PATH"), "Socket inode protection requires Linux O_PATH")
    def test_startup_socket_permissions_are_bound_to_the_owned_inode(self):
        for moment in ("open", "chmod"):
            for replacement in ("symlink", "regular", "socket"):
                with self.subTest(moment=moment, replacement=replacement), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    path, saved, victim = root / "broker.sock", root / "saved.sock", root / "foreign"
                    victim.write_text("unrelated")
                    victim.chmod(0o644)
                    listener = Mock()
                    os.mknod(path, stat.S_IFSOCK | 0o644)
                    real_open, real_chmod, changed = os.open, Path.chmod, []

                    def replace():
                        path.rename(saved)  # Keep the original inode alive.
                        if replacement == "symlink":
                            path.symlink_to(victim)
                        elif replacement == "regular":
                            path.write_text("replacement")
                            real_chmod(path, 0o644)
                        else:
                            os.mknod(path, stat.S_IFSOCK | 0o644)
                        changed.append(True)

                    def open_after_change(value, *args, **kwargs):
                        if moment == "open" and Path(value) == path:
                            replace()
                        return real_open(value, *args, **kwargs)

                    def chmod_after_change(item, *args, **kwargs):
                        if moment == "chmod" and (item == path or item.parent == Path("/proc/self/fd")):
                            replace()
                        return real_chmod(item, *args, **kwargs)

                    server = MaintenanceServer(self.broker, path, {})
                    info = path.stat()
                    server._identity = (info.st_dev, info.st_ino)
                    server._listener = listener
                    with patch("local_hand_jobs.cli.socket.socket", return_value=listener), \
                            patch("os.open", side_effect=open_after_change), \
                            patch.object(Path, "chmod", chmod_after_change):
                        with self.assertRaises(OSError):
                            server._set_socket_permissions()
                    server.close()
                    self.assertEqual([True], changed)
                    self.assertEqual(0o644, stat.S_IMODE(victim.stat().st_mode))
                    self.assertEqual(0o644, stat.S_IMODE(path.stat().st_mode))
                    self.assertEqual(0o600 if moment == "chmod" else 0o644,
                                     stat.S_IMODE(saved.stat().st_mode))
                    listener.close.assert_called_once()

    def test_private_socket_parent_refusal_retains_its_original_code(self):
        root = Path(self.temp.name)
        root.chmod(0o755)
        try:
            with self.assertRaises(JobError) as caught:
                MaintenanceServer(self.broker, self.path, {}).start()
            self.assertEqual("UNAUTHORIZED", caught.exception.code)
            self.assertFalse(self.path.exists())
        finally:
            root.chmod(0o700)

    @unittest.skipUnless(hasattr(os, "mknod"), "Socket inode fixture requires POSIX mknod")
    def test_cleanup_captures_and_restores_a_postcheck_replacement(self):
        for replacement in ("regular", "symlink", "socket"):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                path, old, foreign = root / "broker.sock", root / "old.sock", root / "foreign"
                foreign.write_text("unrelated")
                os.mknod(path, stat.S_IFSOCK | 0o600)
                server = MaintenanceServer(self.broker, path, {})
                info = path.lstat()
                server._identity = (info.st_dev, info.st_ino)
                real_stat, changed = os.stat, []
                def stat_then_replace(value, *args, **kwargs):
                    info = real_stat(value, *args, **kwargs)
                    if value == path.name and kwargs.get("dir_fd") is not None and not changed:
                        path.rename(old)
                        if replacement == "regular":
                            path.write_text("replacement")
                        elif replacement == "symlink":
                            path.symlink_to(foreign)
                        else:
                            os.mknod(path, stat.S_IFSOCK | 0o644)
                        changed.append(True)
                    return info
                with patch("os.stat", side_effect=stat_then_replace):
                    with self.assertRaises(JobError) as caught:
                        server.close()
                self.assertEqual("IO_UNCERTAIN", caught.exception.code)
                self.assertEqual([True], changed)
                identity = path.lstat()
                server.close()
                self.assertEqual((identity.st_dev, identity.st_ino), (path.lstat().st_dev, path.lstat().st_ino))
                self.assertEqual("unrelated", foreign.read_text())
                self.assertTrue(stat.S_ISSOCK(old.lstat().st_mode))
                self.assertFalse(list(root.glob(".maintenance-cleanup-*")))

    @unittest.skipUnless(hasattr(os, "mknod"), "Socket inode fixture requires POSIX mknod")
    def test_cleanup_restore_conflict_retains_both_entries_and_private_record(self):
        from local_hand_jobs import evidence
        os.mknod(self.path, stat.S_IFSOCK | 0o600)
        server = MaintenanceServer(self.broker, self.path, {})
        info = self.path.lstat()
        server._identity = (info.st_dev, info.st_ino)
        old = self.path.with_name("old.sock")
        real_publish, calls = evidence._publish_create_only, []
        def publish(source, destination, **kwargs):
            calls.append(str(source))
            if len(calls) == 1:
                self.path.rename(old)
                self.path.write_text("first concurrent object")
            elif len(calls) == 2:
                self.path.write_text("second concurrent object")
            return real_publish(source, destination, **kwargs)
        with patch.object(evidence, "_publish_create_only", side_effect=publish):
            with self.assertRaises(JobError) as caught:
                server.close()
        self.assertEqual("IO_UNCERTAIN", caught.exception.code)
        self.assertNotIn(str(self.path), str(caught.exception))
        self.assertEqual("second concurrent object", self.path.read_text())
        recovery = server._cleanup_recovery
        self.assertEqual("first concurrent object", (recovery / "entry").read_text())
        record = json.loads((recovery / "recovery.json").read_text())
        self.assertEqual("TRUSTED_RECOVERY_REQUIRED", record["status"])
        self.assertEqual(str(self.path), record["socket_path"])
        server.close()
        self.assertEqual("first concurrent object", (recovery / "entry").read_text())
        self.assertEqual("second concurrent object", self.path.read_text())

    @unittest.skipUnless(hasattr(os, "O_PATH"), "Socket staging requires Linux O_PATH")
    def test_staged_bind_never_adopts_or_overwrites_a_concurrent_named_entry(self):
        for replacement in ("regular", "symlink", "socket"):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                path, target = root / "broker.sock", root / "foreign"
                target.write_text("unrelated")
                target.chmod(0o644)
                listener, bound = Mock(), []
                def bind(value):
                    self.assertTrue(str(value).startswith("/proc/self/fd/"))
                    os.mknod(value, stat.S_IFSOCK | 0o644)
                    bound.append(os.stat(value).st_ino)
                    if replacement == "regular":
                        path.write_text("concurrent")
                        path.chmod(0o644)
                    elif replacement == "symlink":
                        path.symlink_to(target)
                    else:
                        os.mknod(path, stat.S_IFSOCK | 0o644)
                listener.bind.side_effect = bind
                server = MaintenanceServer(self.broker, path, {})
                with patch("local_hand_jobs.cli.socket.socket", return_value=listener), \
                        patch("local_hand_jobs.cli.threading.Thread") as thread:
                    with self.assertRaises(JobError) as caught:
                        server.start()
                self.assertEqual("IO_UNCERTAIN", caught.exception.code)
                self.assertEqual(1, len(bound))
                self.assertIsNone(server._identity)
                self.assertEqual(0o644, stat.S_IMODE(path.stat().st_mode))
                self.assertEqual("unrelated", target.read_text())
                self.assertFalse(list(root.glob(".maintenance-start-*")))
                thread.assert_not_called()
                listener.close.assert_called_once()

    @unittest.skipUnless(hasattr(os, "O_PATH"), "Socket inode protection requires Linux O_PATH")
    def test_socket_permission_failure_has_no_path_fallback_and_releases_descriptor(self):
        for failure in ("proc", "close", "both"):
            with self.subTest(failure=failure):
                listener = Mock()
                listener.bind.side_effect = lambda value: os.mknod(value, stat.S_IFSOCK | 0o600)
                server = MaintenanceServer(self.broker, self.path, {})
                real_chmod, real_close, closed = Path.chmod, os.close, []
                primary = FileNotFoundError("synthetic missing proc FD link")

                def chmod(item, *args, **kwargs):
                    self.assertEqual(Path("/proc/self/fd"), item.parent)
                    if failure in {"proc", "both"}:
                        raise primary
                    return real_chmod(item, *args, **kwargs)

                def close(descriptor):
                    owned_socket = stat.S_ISSOCK(os.fstat(descriptor).st_mode)
                    real_close(descriptor)
                    if owned_socket:
                        closed.append(descriptor)
                    if owned_socket and failure in {"close", "both"}:
                        raise OSError("synthetic descriptor close failure")

                with patch("local_hand_jobs.cli.socket.socket", return_value=listener), \
                        patch.object(Path, "chmod", chmod), patch("os.close", side_effect=close):
                    with self.assertRaises(JobError) as caught:
                        server.start()
                self.assertEqual("IO_UNCERTAIN", caught.exception.code)
                if failure in {"proc", "both"}:
                    self.assertIs(primary, caught.exception.__cause__)
                self.assertEqual(1, len(closed))
                with self.assertRaises(OSError):
                    os.fstat(closed[0])
                self.assertFalse(self.path.exists())
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

    def test_client_cleanup_preserves_refusal_and_contains_close_failure(self):
        for raw, code in ((b'{"error":{"code":"UNAUTHORIZED","message":"revoked"}}', "UNAUTHORIZED"),
                          (b'{"result":{"outcome":"UNKNOWN"}}', "IO_UNCERTAIN"),
                          (b'{"result":{},"result":{}}', "IO_UNCERTAIN")):
            with self.subTest(raw=raw):
                connection = SyntheticPeerConnection(raw)
                connection.connect = Mock()
                connection.close = Mock(side_effect=OSError("synthetic close failure"))
                with patch("local_hand_jobs.cli.socket.socket", return_value=connection):
                    # A previously handled caller exception must not suppress
                    # a cleanup failure after a successful transport result.
                    try:
                        raise ValueError("unrelated caller failure")
                    except ValueError:
                        with self.assertRaises(JobError) as caught:
                            request(self.path, "lh_job_status", {})
                self.assertEqual(code, caught.exception.code)
                connection.close.assert_called_once()

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

    def test_extreme_integer_budgets_keep_the_admission_error_contract(self):
        for budget in (10 ** 1000, -(10 ** 1000)):
            for entry in ("client", "server"):
                with self.subTest(positive=budget > 0, entry=entry), \
                        patch("local_hand_jobs.cli.socket.socket") as make_socket:
                    with self.assertRaises(JobError) as caught:
                        if entry == "client":
                            request(self.path, "lh_job_status", {}, timeout=budget)
                        else:
                            MaintenanceServer(self.broker, self.path, {}, response_seconds=budget)
                    self.assertEqual(caught.exception.code, "INVALID_REQUEST")
                    make_socket.assert_not_called()

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

    def test_failed_composition_preserves_primary_after_all_cleanup_failures(self):
        root = Path(self.temp.name)
        (root / "authority.json").write_text('{"ledger_id":"synthetic-ledger"}')
        policy = SimpleNamespace(config={}, source_commit="a" * 40, installed_payload_digest="b" * 64,
            execution_entrypoint="synthetic", broker_root=str(root / "broker"),
            authority_root=str(root), authority_id="synthetic-authority", limits={"retained_bytes": 1024})
        state, authority, manager = unittest.mock.MagicMock(), Mock(), Mock()
        state.all.return_value = []
        manager.support.return_value = {"supported": True}
        manager.scan.return_value = {"status": "READY"}
        state.close.side_effect = OSError("synthetic state cleanup failure")
        authority.close.side_effect = OSError("synthetic authority cleanup failure")
        primary = JobError("IO_UNCERTAIN", "synthetic original construction failure")
        with patch("local_hand_jobs.policy.Policy.from_file", return_value=policy), \
                patch("local_hand_jobs.deployment.verify_release"), \
                patch("local_hand_jobs.resources.verify_local_filesystem"), \
                patch("local_hand_jobs.resources.AuthorityLock", return_value=authority), \
                patch("local_hand_jobs.runner.SystemdManager", return_value=manager), \
                patch("local_hand_jobs.state.StateStore", return_value=state), \
                patch("local_hand_jobs.broker.Broker"), \
                patch("local_hand_jobs.evidence.EvidenceStore", side_effect=primary):
            with self.assertRaises(JobError) as caught:
                create_broker("synthetic", actual_entrypoint="synthetic")
        self.assertIs(primary, caught.exception)
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
