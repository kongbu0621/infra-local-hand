"""Real local IPC with synthetic peers/facts; no privileged observer or quota."""
from __future__ import annotations

import array
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs import quota_client as client
from local_hand_jobs import quota_contract as q
from test_local_hand_jobs_quota_contract import encoded, receipt_data, request_data, root_facts


def framed(raw):
    return struct.pack("!I", len(raw)) + raw


@unittest.skipUnless(sys.platform == "linux", "Q2 Linux BOOTTIME/poll contract")
class DeadlineTests(unittest.TestCase):
    def test_original_deadline_and_clock_regression(self):
        with mock.patch.object(client, "_boottime_ns", side_effect=[10, 11, 9]):
            deadline = client._Deadline(20)
            self.assertEqual(11, deadline.now())
            with self.assertRaisesRegex(q.QuotaError, "CLOCK_REGRESSION"):
                deadline.now()
        with mock.patch.object(client, "_boottime_ns", side_effect=[10, 20]):
            deadline = client._Deadline(20)
            with self.assertRaisesRegex(q.QuotaError, "DEADLINE"):
                deadline.now()

    def test_wait_budget_is_remaining_original_time(self):
        with mock.patch.object(client, "_boottime_ns", side_effect=[n * 1_000_000 for n in (10, 12, 13, 17, 18)]), \
             mock.patch.object(client.select, "poll") as create:
            deadline = client._Deadline(20_000_000)
            deadline.wait("synthetic")
            deadline.wait("synthetic", write=True)
        self.assertEqual([8, 3], [call.args[0] for call in create.return_value.poll.call_args_list])

    def test_high_fd_and_submillisecond_deadline_use_poll(self):
        with mock.patch.object(client, "_boottime_ns", return_value=10), \
             mock.patch.object(client.select, "poll") as create:
            client._Deadline(11).wait(5000)
        create.return_value.register.assert_called_once_with(5000, client.select.POLLIN)
        create.return_value.poll.assert_called_once_with(1)


class EndpointMetadataTests(unittest.TestCase):
    """Declared metadata faults only; actual endpoint checks remain in IPC tests."""

    def test_every_ancestor_and_socket_metadata_is_checked(self):
        endpoint = client.Endpoint("/synthetic/q.sock", 0, 22,
                                   "11111111-2222-3333-4444-555555555555")
        paths = {
            "/": SimpleNamespace(st_dev=1, st_ino=2, st_mode=0o40755, st_uid=0, st_gid=0),
            "/synthetic": SimpleNamespace(st_dev=1, st_ino=3, st_mode=0o40755, st_uid=0, st_gid=0),
            endpoint.path: SimpleNamespace(st_dev=1, st_ino=4, st_mode=0o140660, st_uid=0, st_gid=22)}
        with mock.patch.object(client.os, "lstat", side_effect=lambda path: paths[str(path)]):
            self.assertEqual(3, len(client._endpoint_identity(endpoint)))
            for path, field, value in (("/", "st_mode", 0o40777),
                    ("/synthetic", "st_uid", 1234), ("/synthetic", "st_mode", 0o120777),
                    (endpoint.path, "st_mode", 0o100660), (endpoint.path, "st_mode", 0o140666),
                    (endpoint.path, "st_uid", 1234), (endpoint.path, "st_gid", 23)):
                before = getattr(paths[path], field)
                setattr(paths[path], field, value)
                with self.subTest(path=path, field=field), self.assertRaises(q.QuotaError):
                    client._endpoint_identity(endpoint)
                setattr(paths[path], field, before)

    def test_endpoint_must_be_bounded_canonical_and_never_abstract(self):
        for path in ("relative", "/a/../q", "/a//q", "/a/./q", "/a/q/", "\0abstract",
                     "/a/space q", "/" + "q" * 107):
            endpoint = client.Endpoint(path, 0, 0, "11111111-2222-3333-4444-555555555555")
            with self.subTest(path=path), mock.patch.object(client.os, "lstat") as read:
                with self.assertRaises(q.QuotaError):
                    client._endpoint_identity(endpoint)
                read.assert_not_called()


@unittest.skipUnless(sys.platform == "linux", "Q2 Linux Unix-socket logic contract")
class ScriptedTransportTests(unittest.TestCase):
    """LOGIC_ONLY fault injection; does not replace the real IPC tests below."""

    def setUp(self):
        self.request = q.decode_request(encoded(request_data()))
        self.roots = root_facts()
        self.response = encoded(receipt_data(self.request, self.roots))
        self.sock = mock.MagicMock()
        self.sock.__enter__.return_value = self.sock
        self.sock.connect_ex.return_value = 0
        self.sock.getsockopt.return_value = struct.pack("=iII", 123, 0, 0)
        self.sock.send.side_effect = lambda data: min(len(data), 17)
        self.endpoint = client.Endpoint("/synthetic/q.sock", 0, 0, self.request.as_dict()["boot_id"])
        self.clock = mock.patch.object(client, "_boottime_ns", return_value=300).start()
        self.addCleanup(mock.patch.stopall)

    def incoming(self, wire, *, ancillary=(), flags=0):
        pending = bytearray(wire)

        def receive(count, _ancillary_size, _flags):
            chunk = bytes(pending[:min(count, 11)])
            del pending[:len(chunk)]
            return chunk, ancillary, flags, None

        self.sock.recvmsg.side_effect = receive

    def observe(self, *, identities=("stable", "stable", "stable"), boots=None):
        with mock.patch.object(client.socket, "socket", return_value=self.sock) as create, \
             mock.patch.object(client, "_endpoint_identity", side_effect=identities), \
             mock.patch.object(client, "_boot_id", side_effect=boots or [self.endpoint.boot_id] * 2):
            try:
                return client.observe(self.endpoint, self.request, self.roots)
            finally:
                self.assertLessEqual(create.call_count, 1, "must not reconnect")

    def test_fragmentation_binds_receipt_and_half_closes_request(self):
        self.incoming(framed(self.response))
        result = self.observe()
        self.assertEqual("OBSERVED", result.as_dict()["status"])
        self.sock.shutdown.assert_called_once_with(socket.SHUT_WR)
        sent = b"".join(bytes(call.args[0][:17]) for call in self.sock.send.call_args_list)
        self.assertEqual(framed(self.request.wire), sent)
        self.sock.__exit__.assert_called_once()

    def test_bad_frames_fail_without_retry(self):
        for wire, code in ((b"", "PARTIAL_FRAME"), (b"\0\0", "PARTIAL_FRAME"),
                (framed(self.response)[:-1], "PARTIAL_FRAME"),
                (struct.pack("!I", q.RESPONSE_LIMIT + 1), "RESPONSE_LENGTH"),
                (struct.pack("!I", 0), "RESPONSE_LENGTH"),
                (framed(self.response) + b"!", "TRAILING_BYTES")):
            self.incoming(wire)
            self.sock.reset_mock()
            with self.subTest(code=code), self.assertRaisesRegex(q.QuotaError, code):
                self.observe()
            self.sock.connect_ex.assert_called_once()
            self.sock.__exit__.assert_called_once()

    def test_missing_eof_spends_remaining_deadline_not_another_window(self):
        self.incoming(framed(self.response))
        receive = self.sock.recvmsg.side_effect

        def no_eof(*args):
            result = receive(*args)
            if not result[0]:
                raise BlockingIOError()
            return result

        self.sock.recvmsg.side_effect = no_eof

        def expire(*_args):
            self.clock.return_value = 10_000

        with mock.patch.object(client.select, "poll") as create:
            create.return_value.poll.side_effect = expire
            with self.assertRaisesRegex(q.QuotaError, "DEADLINE"):
                self.observe()
        create.return_value.poll.assert_called_once_with(1)
        self.sock.connect_ex.assert_called_once()

    def test_injected_rights_are_closed_even_with_truncation(self):
        for flags in (0, socket.MSG_CTRUNC):
            read_fd, write_fd = os.pipe()
            received_fd = os.dup(read_fd)
            try:
                self.sock.recvmsg.side_effect = None
                self.sock.recvmsg.return_value = (b"x", [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                    array.array("i", [received_fd]).tobytes())], flags, None)
                with self.subTest(flags=flags), self.assertRaisesRegex(q.QuotaError, "ANCILLARY"):
                    client._recv(self.sock, 1, client._Deadline(10_000))
                with self.assertRaises(OSError) as error:
                    os.fstat(received_fd)
                self.assertEqual(errno.EBADF, error.exception.errno)
                received_fd = None  # Never close the same numeric descriptor twice.
                os.fstat(read_fd)
            finally:
                for fd in (received_fd, read_fd, write_fd):
                    if fd is None:
                        continue
                    try:
                        os.close(fd)
                    except OSError:
                        pass

    def test_unknown_ancillary_and_data_truncation_are_rejected(self):
        for ancillary, flags in (([(socket.SOL_SOCKET, socket.SCM_CREDENTIALS, b"x")], 0),
                                  ([], socket.MSG_TRUNC), ([], socket.MSG_CTRUNC)):
            self.sock.recvmsg.return_value = (b"x", ancillary, flags, None)
            with self.subTest(flags=flags), self.assertRaisesRegex(q.QuotaError, "ANCILLARY"):
                client._recv(self.sock, 1, client._Deadline(10_000))

    def test_queue_full_and_peer_mismatch_send_no_bytes(self):
        self.sock.connect_ex.return_value = errno.EAGAIN
        with self.assertRaisesRegex(q.QuotaError, "CONNECT"):
            self.observe()
        self.sock.send.assert_not_called()
        self.sock.connect_ex.return_value = 0
        self.sock.getsockopt.return_value = struct.pack("=iII", 123, 1001, 1001)
        with self.assertRaisesRegex(q.QuotaError, "SERVER_PEER"):
            self.observe()
        self.sock.send.assert_not_called()

    def test_send_backpressure_expires_without_a_second_delivery(self):
        self.sock.send.side_effect = BlockingIOError()

        def expire(*_args):
            self.clock.return_value = 10_000

        with mock.patch.object(client.select, "poll") as create:
            create.return_value.poll.side_effect = expire
            with self.assertRaisesRegex(q.QuotaError, "DEADLINE"):
                self.observe()
        self.sock.connect_ex.assert_called_once()
        self.sock.send.assert_called_once()
        self.sock.shutdown.assert_not_called()
        self.sock.recvmsg.assert_not_called()

    def test_pending_connect_must_finish_before_peer_check_and_send(self):
        self.sock.connect_ex.return_value = errno.EINPROGRESS
        self.sock.getsockopt.side_effect = [errno.ECONNREFUSED]
        with mock.patch.object(client.select, "poll"):
            with self.assertRaisesRegex(q.QuotaError, "CONNECT"):
                self.observe()
        self.sock.send.assert_not_called()
        self.sock.getsockopt.assert_called_once_with(socket.SOL_SOCKET, socket.SO_ERROR)
        self.sock.reset_mock()
        self.sock.getsockopt.side_effect = [0, struct.pack("=iII", 123, 0, 0)]
        self.incoming(framed(self.response))
        with mock.patch.object(client.select, "poll"):
            self.assertEqual("OBSERVED", self.observe().as_dict()["status"])
        self.assertEqual(2, self.sock.getsockopt.call_count)

    def test_endpoint_change_before_send_and_after_response_fail(self):
        self.incoming(framed(self.response))
        with self.assertRaisesRegex(q.QuotaError, "ENDPOINT_CHANGED"):
            self.observe(identities=("stable", "changed"))
        self.sock.send.assert_not_called()
        with self.assertRaisesRegex(q.QuotaError, "ENDPOINT_CHANGED"):
            self.observe(identities=("stable", "stable", "changed"))

    def test_late_decode_cannot_consume_a_shorter_receipt_deadline(self):
        receipt = receipt_data(self.request, self.roots)
        receipt["deadline_ns"] = 400
        self.incoming(framed(encoded(receipt)))
        decode = client.decode_receipt

        def slow_decode(*args, **kwargs):
            result = decode(*args, **kwargs)
            self.clock.return_value = 400
            return result

        with mock.patch.object(client, "decode_receipt", side_effect=slow_decode):
            with self.assertRaisesRegex(q.QuotaError, "DEADLINE"):
                self.observe()

    def test_boot_change_and_transport_errors_do_not_reach_consumption(self):
        self.incoming(framed(self.response))
        with self.assertRaisesRegex(q.QuotaError, "BOOT_BINDING"):
            self.observe(boots=[self.endpoint.boot_id, "22222222-2222-3333-4444-555555555555"])
        self.sock.send.side_effect = PermissionError("private installation path")
        with self.assertRaisesRegex(q.QuotaError, "^TRANSPORT_IO$"):
            self.observe()


@unittest.skipUnless(sys.platform == "linux" and os.geteuid() == 0,
                     "protected root-owned endpoint fixture requires isolated Linux root executor")
class QuotaClientSocketTests(unittest.TestCase):
    """Root only creates protected test socket paths; client gains no authority."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="q2-", dir="/root")
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "q.sock")
        try:
            self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        except PermissionError as exc:
            self.skipTest(f"executor denied AF_UNIX socket creation: errno={exc.errno}; IPC UNVERIFIED")
        self.addCleanup(self.listener.close)
        self.listener.bind(self.path)
        os.chmod(self.path, 0o660)
        self.listener.listen(1)
        self.listener.settimeout(2)
        self.endpoint = client.Endpoint(self.path, os.geteuid(), os.getegid(), client._boot_id())
        self.roots = root_facts()
        self.set_request()

    def set_request(self, seconds=3):
        now = client._boottime_ns()
        value = request_data(deadline=now + int(seconds * 1e9))
        value["boot_id"] = self.endpoint.boot_id
        self.request = q.decode_request(encoded(value))
        self.response = receipt_data(self.request, self.roots, start=now, finish=now)

    @contextmanager
    def peer(self, action):
        state = {"accepted": 0, "requests": [], "errors": [], "stop": threading.Event()}

        def run():
            try:
                connection, _ = self.listener.accept()
                state["accepted"] += 1
                with connection:
                    connection.settimeout(2)
                    header = b""
                    while len(header) < 4:
                        chunk = connection.recv(4 - len(header))
                        if not chunk:  # Peer identity rejection sends no request.
                            return
                        header += chunk
                    size = struct.unpack("!I", header)[0]
                    self.assertLessEqual(size, q.REQUEST_LIMIT)
                    data = bytearray()
                    while len(data) < size:
                        chunk = connection.recv(size - len(data))
                        self.assertTrue(chunk)
                        data.extend(chunk)
                    self.assertEqual(b"", connection.recv(1))  # Actual request half-close.
                    state["requests"].append(bytes(data))
                    action(connection, state["stop"])
            except (BrokenPipeError, ConnectionResetError):
                pass  # Expected when a bounded client rejects a prefix.
            except Exception as exc:
                state["errors"].append(repr(exc))

        thread = threading.Thread(target=run, name="q2-test-peer", daemon=True)
        thread.start()
        try:
            yield state
        finally:
            state["stop"].set()
            thread.join(3)
            self.assertFalse(thread.is_alive(), "test peer did not stop")
            self.assertEqual([], state["errors"])

    def observe(self, endpoint=None):
        return client.observe(self.endpoint if endpoint is None else endpoint, self.request, self.roots)

    def test_fragmented_response_and_eof_return_immutable_bound_facts(self):
        response = framed(encoded(self.response))

        def action(connection, _stop):
            for offset in range(0, len(response), 7):
                connection.sendall(response[offset:offset + 7])

        with self.peer(action) as state:
            result = self.observe()
        self.assertEqual([self.request.wire], state["requests"])
        self.assertEqual(1, state["accepted"])
        self.assertEqual("OBSERVED", result.as_dict()["status"])
        self.assertEqual(3 * 65536, result.domain_hard_bytes)

    def test_partial_header_body_zero_oversize_and_trailing_data_are_rejected_once(self):
        whole = framed(encoded(self.response))
        for raw, code in ((b"", "PARTIAL_FRAME"), (b"\x00\x00", "PARTIAL_FRAME"),
                (whole[:-1], "PARTIAL_FRAME"), (struct.pack("!I", 0), "RESPONSE_LENGTH"),
                (struct.pack("!I", q.RESPONSE_LIMIT + 1), "RESPONSE_LENGTH"),
                (whole + b"!", "TRAILING_BYTES")):
            with self.subTest(code=code, size=len(raw)), \
                 self.peer(lambda connection, stop: connection.sendall(raw)) as state, \
                 mock.patch.object(client, "_connect", wraps=client._connect) as connect:
                with self.assertRaisesRegex(q.QuotaError, code):
                    self.observe()
                self.assertEqual(1, connect.call_count)
            self.assertEqual(1, state["accepted"])

    def test_complete_json_without_transport_eof_is_not_complete(self):
        self.set_request(0.15)

        def action(connection, stop):
            connection.sendall(framed(encoded(self.response)))
            stop.wait(2)

        start = time.monotonic()
        with self.peer(action), mock.patch.object(client, "_connect", wraps=client._connect) as connect:
            with self.assertRaisesRegex(q.QuotaError, "DEADLINE"):
                self.observe()
            self.assertEqual(1, connect.call_count)
        self.assertLess(time.monotonic() - start, 1.5)

    def test_slow_fragments_do_not_refresh_deadline(self):
        self.set_request(0.15)

        def action(connection, stop):
            for byte in framed(encoded(self.response)):
                connection.sendall(bytes((byte,)))
                if stop.wait(0.025):
                    break

        start = time.monotonic()
        with self.peer(action):
            with self.assertRaisesRegex(q.QuotaError, "DEADLINE"):
                self.observe()
        self.assertLess(time.monotonic() - start, 1.5)

    def test_rights_in_header_body_or_after_frame_are_closed_before_rejection(self):
        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, read_fd)
        self.addCleanup(os.close, write_fd)
        response = framed(encoded(self.response))
        for offset in (0, 8, len(response)):
            baseline = len(os.listdir("/proc/self/fd"))

            def action(connection, _stop):
                if offset:
                    connection.sendall(response[:offset])
                data = response[offset:offset + 1] or b"!"
                connection.sendmsg([data], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                             array.array("i", [read_fd, write_fd]))])

            with self.subTest(offset=offset), self.peer(action):
                with self.assertRaisesRegex(q.QuotaError, "ANCILLARY"):
                    self.observe()
            self.assertEqual(baseline, len(os.listdir("/proc/self/fd")), "received FD leak")
            os.fstat(read_fd)
            os.fstat(write_fd)

    def test_os_peer_must_match_installed_socket_owner(self):
        os.chown(self.path, 1, os.getegid())
        endpoint = client.Endpoint(self.path, 1, os.getegid(), self.endpoint.boot_id)
        with self.peer(lambda connection, stop: self.fail("request sent to wrong peer")) as state:
            with self.assertRaisesRegex(q.QuotaError, "SERVER_PEER"):
                self.observe(endpoint)
        self.assertEqual([], state["requests"])

    def test_endpoint_replacement_after_connection_is_rejected(self):
        replacement = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(replacement.close)

        def action(connection, _stop):
            os.unlink(self.path)
            replacement.bind(self.path)
            os.chmod(self.path, 0o660)
            connection.sendall(framed(encoded(self.response)))

        with self.peer(action):
            with self.assertRaisesRegex(q.QuotaError, "ENDPOINT_CHANGED"):
                self.observe()

    def test_unprotected_parent_world_socket_and_symlink_fail_before_connect(self):
        with mock.patch.object(client, "_connect", side_effect=AssertionError("must reject before connect")):
            os.chmod(self.temp.name, 0o777)
            with self.assertRaisesRegex(q.QuotaError, "ENDPOINT_PARENT"):
                self.observe()
            os.chmod(self.temp.name, 0o700)
            os.chmod(self.path, 0o666)
            with self.assertRaisesRegex(q.QuotaError, "ENDPOINT_SOCKET"):
                self.observe()
            os.chmod(self.path, 0o660)
            link = str(Path(self.temp.name) / "link.sock")
            os.symlink(self.path, link)
            with self.assertRaisesRegex(q.QuotaError, "ENDPOINT_SOCKET"):
                self.observe(client.Endpoint(link, 0, os.getegid(), self.endpoint.boot_id))
            directory_link = str(Path(self.temp.name) / "link")
            os.symlink(self.temp.name, directory_link)
            with self.assertRaisesRegex(q.QuotaError, "ENDPOINT_PARENT"):
                self.observe(client.Endpoint(directory_link + "/q.sock", 0, os.getegid(), self.endpoint.boot_id))

    def test_expired_boot_mismatch_invalid_request_and_roots_send_nothing(self):
        with mock.patch.object(client, "_connect", side_effect=AssertionError("must reject before connect")):
            with self.assertRaisesRegex(q.QuotaError, "BOOT_BINDING"):
                self.observe(client.Endpoint(self.path, 0, os.getegid(), "22222222-2222-3333-4444-555555555555"))
            self.roots[2]["uid"] = 0
            with self.assertRaises(q.QuotaError):
                self.observe()
            self.roots = root_facts()
            self.request = q.Request(b"{}")
            with self.assertRaises(q.QuotaError):
                self.observe()
            self.set_request(-1)
            with self.assertRaisesRegex(q.QuotaError, "DEADLINE"):
                self.observe()

    def test_bound_receipt_from_another_request_is_rejected_after_complete_ipc(self):
        wrong = q.decode_request(encoded({**self.request.as_dict(), "generation": "c" * 32}))
        now = client._boottime_ns()
        response = receipt_data(wrong, self.roots, start=now, finish=now)
        with self.peer(lambda connection, stop: connection.sendall(framed(encoded(response)))):
            with self.assertRaisesRegex(q.QuotaError, "REQUEST_BINDING"):
                self.observe()

    def test_connection_error_is_sanitized_and_not_retried(self):
        self.listener.close()
        with mock.patch.object(client, "_connect", wraps=client._connect) as connect:
            with self.assertRaises(q.QuotaError) as error:
                self.observe()
        self.assertEqual(1, connect.call_count)
        self.assertNotIn(self.path, str(error.exception))


if __name__ == "__main__":
    unittest.main()
