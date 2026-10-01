"""Real private socket/credential/FD checks; no systemd qualification claim."""
import array
import json
import os
import socket
import sys
import threading
import unittest

if sys.platform.startswith("linux"):
    from local_hand_jobs import budget, quota_contract as q
    from local_hand_jobs import system_manager_protocol as wire


@unittest.skipUnless(sys.platform.startswith("linux") and hasattr(os, "pidfd_open"), "Linux inherited IPC")
class ProtocolTests(unittest.TestCase):
    def setUp(self):
        try:
            if os.readlink("/proc/self") != str(os.getpid()):
                self.skipTest("Current PID namespace has a different procfs namespace; real peer binding is unsupported")
            wire.start_ticks(os.getpid())
        except OSError:
            self.skipTest("Current PID namespace has no matching procfs; real peer start-time binding is unsupported")

    def pair(self, *, peer=None):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        now = budget.current_clock()
        options = dict(peer=peer or (os.getpid(), os.getuid(), os.getgid()),
            peer_start_ticks=wire.start_ticks(os.getpid()), session_id="a" * 64,
            boot_id=now["boot_id"], deadline_ns=now["boottime_ns"] + 5_000_000_000)
        first = wire.Channel(left, **options); second = wire.Channel(right, **options)
        self.addCleanup(first.close); self.addCleanup(second.close)
        return first, second

    def exchange(self, client, server, op, response, fds=(), **body):
        errors = []
        def serve():
            try:
                request = server.receive_request()
                self.assertEqual((op, body), (request["op"], request["body"]))
                server.respond(request, response, fds=fds)
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=serve); thread.start()
        try:
            return client.request(op, **body)
        finally:
            thread.join(4)
            self.assertFalse(thread.is_alive())
            if errors:
                raise errors[0]

    def pipe(self):
        read, write = os.pipe()
        self.addCleanup(os.close, read); self.addCleanup(os.close, write)
        return read, write

    def test_actual_credentials_and_two_distinct_readonly_pipes(self):
        a, b = self.pair(); left, writer = self.pipe(); right, _ = self.pipe()
        body = dict(ref=dict(execution_id="job-example-preflight", phase="preflight", stage="bootstrap"),
                    bindings=dict(allocation_digest="c" * 64, grant_digest="d" * 64))
        result, fds = self.exchange(a, b, "launch", {"client_state": {}}, (left, right), **body)
        try:
            self.assertEqual(2, len(fds))
            self.assertFalse(os.get_inheritable(fds[0]))
            self.assertEqual(wire.readonly_pipe(left), wire.readonly_pipe(fds[0]))
            os.write(writer, b"original-bytes")
            self.assertEqual(b"original-bytes", os.read(fds[0], 64))
            with self.assertRaises(OSError): os.write(fds[0], b"forbidden")
            self.assertEqual(a.total, b.total)
            self.assertEqual((1, 1), (a.sequence, b.sequence))
        finally:
            for fd in fds: os.close(fd)

    def test_foreign_credentials_poison_before_request_use(self):
        a, b = self.pair(peer=(os.getpid(), os.getuid() + 1, os.getgid()))
        a._send("support", {}, (), wire.REQUEST_LIMIT)
        with self.assertRaisesRegex(q.QuotaError, "SYSTEM_PACKET_IDENTITY"): b.receive_request()
        self.assertTrue(b.poisoned)

    def test_bad_start_time_cannot_open_channel(self):
        a, _ = self.pair()
        a.peer_start_ticks += 1
        with self.assertRaisesRegex(q.QuotaError, "SYSTEM_PEER_CHANGED"): a.request("support")
        self.assertTrue(a.poisoned)

    def test_original_peer_alive_but_closed_channel_cannot_deliver(self):
        a, b = self.pair()
        b.close()
        with self.assertRaisesRegex(q.QuotaError, "SYSTEM_CHANNEL_DISCONNECTED"): a.request("support")
        self.assertTrue(a.poisoned)

    def test_duplicate_extra_keys_replay_and_truncated_packets_rejected(self):
        for fault in ("duplicate", "extra", "replay", "oversize", "command"):
            with self.subTest(fault=fault):
                a, b = self.pair()
                value = dict(schema=wire.SCHEMA, session_id=a.session_id, sequence=0, op="support", body={})
                if fault == "extra": value["path"] = "/not-accepted"
                if fault == "replay": value["sequence"] = 1
                if fault == "command": value["body"] = dict(argv=["never-run"])
                raw = json.dumps(value).encode()
                if fault == "duplicate": raw = raw[:-1] + b',"sequence":0}'
                if fault == "oversize": raw = b"x" * (wire.REQUEST_LIMIT + 1)
                a.sock.send(raw)
                with self.assertRaises(q.QuotaError): b.receive_request()
                self.assertTrue(b.poisoned)

    def test_rejected_rights_are_closed_including_wrong_access_and_count(self):
        for kind in ("request", "write", "alias"):
            with self.subTest(kind=kind):
                a, b = self.pair(); read, write = self.pipe()
                value = dict(schema=wire.SCHEMA, session_id=a.session_id, sequence=0,
                             op="support" if kind == "request" else "launch", body={})
                rights = [read] if kind == "request" else [write, read] if kind == "write" else [read, read]
                before = len(os.listdir("/proc/self/fd"))
                a.sock.sendmsg([json.dumps(value).encode()], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", rights))])
                with self.assertRaises(q.QuotaError):
                    if kind == "request": b.receive_request()
                    else: b._receive(wire.RESPONSE_LIMIT, "launch")
                self.assertEqual(before, len(os.listdir("/proc/self/fd")))

    def test_call_and_wire_limits_are_cumulative_and_pending_call_cannot_reenter(self):
        for fault in ("calls", "wire", "pending"):
            with self.subTest(fault=fault):
                a, _ = self.pair()
                if fault == "calls": a.sequence = wire.CALL_LIMIT
                elif fault == "wire": a.total = wire.WIRE_LIMIT
                else: a.pending = "launch"
                with self.assertRaises(q.QuotaError): a.request("support")
                self.assertTrue(a.poisoned)

    def test_real_child_exit_cannot_be_replaced_by_same_pid_number(self):
        read, write = os.pipe(); child = os.fork()
        if child == 0:
            os.close(write); os.read(read, 1); os._exit(0)
        os.close(read)
        channel = left = right = None
        waited = False
        try:
            left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            now = budget.current_clock()
            channel = wire.Channel(left, peer=(child, os.getuid(), os.getgid()), peer_start_ticks=wire.start_ticks(child),
                session_id="a" * 64, boot_id=now["boot_id"], deadline_ns=now["boottime_ns"] + 5_000_000_000)
            os.close(write); write = -1
            os.waitpid(child, 0); waited = True
            with self.assertRaisesRegex(q.QuotaError, "SYSTEM_PEER_CHANGED"): channel.request("support")
        finally:
            if write >= 0: os.close(write)
            if not waited: os.waitpid(child, 0)
            if channel is not None: channel.close()
            elif left is not None: left.close()
            if right is not None: right.close()
