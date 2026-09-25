"""Finite single-request listener and separate admission entry.

All disk/proc reads and fsyncs happen before accept or in the separately bounded
admission unit. External descriptors are rejected. An accepted client FD may
cross only the private, authenticated root control connection. No worker restart,
endpoint replacement, replay, or allocation cleanup is performed here.
"""
from __future__ import annotations

import array
import fcntl
import os
from pathlib import PurePosixPath
import select
import socket
import stat
import struct

from local_hand_jobs import quota_contract as q
from . import q2_config as c, q2_peer as peer, q2_runtime as runtime
from .q2_journal import Journal
from .q2_service import Service
from .systemd_runtime import boottime_ns


class Frame:
    def __init__(self, end):
        self.end = end
        self.buffer = bytearray()
        self.expected = None
        self.eof = False

    def feed(self, chunk, *, now):
        q.require(now < self.end and not self.eof, "FRAME_DEADLINE")
        if not chunk:
            self.eof = True
        self.buffer.extend(chunk)
        q.require(len(self.buffer) <= q.REQUEST_LIMIT + 4, "FRAME_LIMIT")
        if len(self.buffer) >= 4 and self.expected is None:
            self.expected = struct.unpack("!I", self.buffer[:4])[0]
            q.require(0 < self.expected <= q.REQUEST_LIMIT, "FRAME_LIMIT")
        q.require(self.expected is None or len(self.buffer) <= 4 + self.expected, "FRAME_TRAILING")
        if self.eof:
            q.require(self.expected is not None and len(self.buffer) == self.expected + 4, "FRAME_TRUNCATED")
            return bytes(self.buffer[4:])
        return None


def ancillary(items):
    descriptors = []
    for level, kind, raw in items:
        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
            values = array.array("i")
            values.frombytes(raw[:len(raw) - len(raw) % values.itemsize])
            descriptors.extend(values)
    return descriptors


def bind(path, *, seqpacket=False, gid=0):
    parent = c.open_protected(str(PurePosixPath(path).parent), directory=True)
    os.close(parent)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET if seqpacket else socket.SOCK_STREAM)
    try:
        # bind fails on an existing filesystem entry; never unlink a reservation.
        sock.bind(path)
        os.chown(path, 0, gid, follow_symlinks=False)
        os.chmod(path, 0o600 if seqpacket else 0o660, follow_symlinks=False)
        sock.listen(1)
        sock.setblocking(False)
        return sock
    except BaseException:
        sock.close()
        raise


def listener(config):
    runtime.host(config, "listener")
    v = config.data(); grant = config.active(); data = grant.as_dict()
    private = bind(v["service"]["control_path"], seqpacket=True)
    endpoint = None; control = None; clients = {}; dispatched = False
    end = min(runtime.deadline(config, "listener"), boottime_ns() + runtime.limits(config, "listener")["runtime_ns"])
    try:
        # Authentication reads occur BEFORE accepting unprivileged connections.
        while boottime_ns() < end:
            if select.select([private], [], [], min(0.05, max(0, end - boottime_ns()) / 1e9))[0]:
                control, _ = private.accept()
                peer.control(config, control, "admission")
                control.setblocking(False)
                break
        q.require(control is not None, "WORKER_UNAVAILABLE")
        endpoint = bind(data["endpoint"]["path"], gid=data["endpoint"]["gid"])
        # Hot path below contains no filesystem/proc/manager operations.
        while boottime_ns() < end:
            now = boottime_ns()
            for conn, frame in list(clients.items()):
                if now >= frame.end:
                    conn.close(); del clients[conn]
            ready = select.select([endpoint, control, *clients], [], [], min(0.02, max(0, end - now) / 1e9))[0]
            if control in ready:
                ack, items, flags, _ = control.recvmsg(1, socket.CMSG_SPACE(16))
                received = ancillary(items)
                for fd in received:
                    os.close(fd)
                q.require(not items and not flags and ack == b"1" and dispatched, "WORKER_UNCERTAIN")
                return  # One completed original attempt. Endpoints remain reserved.
            if endpoint in ready:
                conn, _ = endpoint.accept(); conn.setblocking(False)
                if dispatched or len(clients) >= v["service"]["max_connections"]:
                    conn.close()
                else:
                    clients[conn] = Frame(min(end, now + v["service"]["accept_ns"]))
            for conn in list(clients):
                if conn not in ready:
                    continue
                try:
                    chunk, items, flags, _ = conn.recvmsg(4096, socket.CMSG_SPACE(16), socket.MSG_CMSG_CLOEXEC)
                    received = ancillary(items)
                    for fd in received:
                        os.close(fd)
                    q.require(not items and not (flags & ~socket.MSG_CMSG_CLOEXEC), "WIRE_DESCRIPTORS")
                    raw = clients[conn].feed(chunk, now=boottime_ns())
                    if raw is None:
                        continue
                    q.require(q.decode_request(raw) == grant.request and not dispatched, "REQUEST_NOT_ADMITTED")
                    # Only the original accepted socket goes to the root worker.
                    dispatched = True  # Delivery uncertainty permanently consumes this listener.
                    count = control.sendmsg([raw], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [conn.fileno()]))])
                    q.require(count == len(raw), "WORKER_DELIVERY_UNCERTAIN")
                    dispatched = True
                    for other in clients:
                        other.close()
                    clients.clear()
                    break
                except (OSError, ValueError):
                    conn.close(); clients.pop(conn, None)
                    if dispatched:
                        raise
        raise q.QuotaError("LISTENER_DEADLINE")
    finally:
        for conn in clients:
            conn.close()
        for conn in (control, endpoint, private):
            if conn is not None:
                conn.close()


def reserve_session(config):
    value = config.data()["session"]
    fd = c.open_protected(value["path"])
    try:
        info = os.fstat(fd)
        q.require((info.st_dev, info.st_ino) == (value["device"], value["inode"])
                  and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size == 0, "SESSION_CONSUMED")
        # open_protected is read-only; reopen through the verified descriptor.
        writer = os.open("/proc/self/fd/" + str(fd), os.O_WRONLY | os.O_CLOEXEC)
        try:
            fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
            q.require(os.fstat(writer).st_size == 0, "SESSION_CONSUMED")
            raw = q._canonical({"config_digest": config.digest, "identity": runtime.host(config, "admission")}, 4096)
            q.require(os.write(writer, raw) == len(raw), "SESSION_WRITE")
            os.fsync(writer)
        finally:
            os.close(writer)
    finally:
        os.close(fd)


def admission(config):
    runtime.host(config, "admission")
    reserve_session(config)
    v = config.data(); grant = config.active()
    journal = Journal(v["journal"]["path"], v["journal"]["pin"], v["capacity"], list(config.grants().values()))
    control = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    connection = None
    try:
        # Startup ordering is explicit: listener first. There is no connect retry.
        control.settimeout(max(0.001, (runtime.deadline(config, "admission") - boottime_ns()) / 1e9))
        control.connect(v["service"]["control_path"])
        peer.control(config, control, "listener")
        raw, items, flags, _ = control.recvmsg(q.REQUEST_LIMIT + 1, socket.CMSG_SPACE(16), socket.MSG_CMSG_CLOEXEC)
        descriptors = ancillary(items)
        if (flags & ~socket.MSG_CMSG_CLOEXEC) or len(descriptors) != 1 or len(items) != 1:
            for fd in descriptors:
                os.close(fd)
            raise q.QuotaError("CONTROL_FRAME")
        connection = socket.socket(fileno=descriptors[0])
        q.require(connection.type == socket.SOCK_STREAM and q.decode_request(raw) == grant.request, "CONTROL_REQUEST")
        attested = peer.inspect(config, connection)
        # The expected command/parent/uid came from protected config; process
        # start ticks/invocation were read independently, not from request JSON.
        result = Service(journal).handle(raw, peer=attested, expected_peer=attested,
                                        dispatch=runtime.Dispatcher(config))
        q.require(result.receipt is not None, "ORIGINAL_QUERY_UNRESOLVED")
        runtime.host(config, "admission")
        connection.settimeout(max(0.001, (runtime.deadline(config, "admission") - boottime_ns()) / 1e9))
        connection.sendall(struct.pack("!I", len(result.receipt)) + result.receipt)
        connection.shutdown(socket.SHUT_WR)
        connection.close(); connection = None
        control.sendall(b"1")
    finally:
        if connection is not None:
            connection.close()
        control.close()
        journal.close()
