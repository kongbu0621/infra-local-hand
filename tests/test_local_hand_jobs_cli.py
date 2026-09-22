from __future__ import annotations

import os
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs.cli import MaintenanceServer, request, _read_frame, create_broker
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
