"""One-shot, unprivileged Q2 Unix client for an already supervised bootstrap.

No retry, process, thread, quota syscall, ledger update, or business launch. The
caller must retain allocation on error. Filesystem operations belong inside the
supervised bootstrap; this API must not run on the broker's control thread.
"""
from __future__ import annotations

import array
from dataclasses import dataclass
import errno
import os
from pathlib import PurePosixPath
import select
import socket
import stat
import struct
import time

from .quota_contract import (QuotaError, RESPONSE_LIMIT, UUID_PATTERN, canonical_path,
                             decode_receipt, decode_request, integer, match, require,
                             validate_expected_roots)


@dataclass(frozen=True, slots=True)
class Endpoint:
    """Protected installation input, never derived from the wire request."""

    path: str
    uid: int
    gid: int
    boot_id: str


def _boottime_ns():
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME)


class _Deadline:
    def __init__(self, end_ns):
        self.end_ns = integer(end_ns, 1)
        self.last_ns = 0
        self.now()

    def now(self):
        tick = integer(_boottime_ns())
        require(tick >= self.last_ns, "CLOCK_REGRESSION")
        self.last_ns = tick
        require(tick < self.end_ns, "DEADLINE")
        return tick

    def wait(self, sock, *, write=False):
        remaining = self.end_ns - self.now()
        poller = select.poll()  # No select(2) FD_SETSIZE limit for an inherited high FD.
        poller.register(sock, select.POLLOUT if write else select.POLLIN)
        try:
            poller.poll(min(2**31 - 1, (remaining + 999_999) // 1_000_000))
        except InterruptedError:
            pass
        self.now()


def _boot_id():
    with open("/proc/sys/kernel/random/boot_id", "rb") as handle:
        value = handle.read(38)
    require(len(value) == 37 and value.endswith(b"\n"), "BOOT_ID")
    try:
        return match(value[:-1].decode("ascii"), UUID_PATTERN)
    except UnicodeError:
        raise QuotaError("BOOT_ID") from None


def _endpoint_identity(endpoint):
    path = PurePosixPath(canonical_path(endpoint.path))
    require(len(endpoint.path.encode("ascii")) <= 107, "ENDPOINT_LENGTH")
    integer(endpoint.uid, 0, 2**32 - 2)
    integer(endpoint.gid, 0, 2**32 - 2)
    match(endpoint.boot_id, UUID_PATTERN)
    identities = []
    for parent in reversed(path.parents):
        info = os.lstat(parent)
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
                and info.st_mode & 0o022 == 0, "ENDPOINT_PARENT")
        identities.append((info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid))
    info = os.lstat(path)
    require(stat.S_ISSOCK(info.st_mode) and info.st_uid == endpoint.uid
            and info.st_gid == endpoint.gid and info.st_mode & 0o007 == 0
            and info.st_mode & 0o7000 == 0, "ENDPOINT_SOCKET")
    identities.append((info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid))
    return tuple(identities)


def _connect(sock, endpoint, deadline):
    deadline.now()
    result = sock.connect_ex(endpoint.path)
    if result in (errno.EINPROGRESS, errno.EALREADY):
        deadline.wait(sock, write=True)
        result = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
    # AF_UNIX EAGAIN can mean a full listen queue without a pending connection.
    # Do not turn it into another attempt or an assumed successful connection.
    require(result == 0, "CONNECT")
    deadline.now()
    peer = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("=iII"))
    pid, uid, gid = struct.unpack("=iII", peer)
    require(pid > 0 and (uid, gid) == (endpoint.uid, endpoint.gid), "SERVER_PEER")


def _send(sock, data, deadline):
    remaining = memoryview(data)
    while remaining:
        deadline.now()
        try:
            sent = sock.send(remaining)
        except (BlockingIOError, InterruptedError):
            deadline.wait(sock, write=True)
            continue
        require(sent > 0, "SEND_CLOSED")
        remaining = remaining[sent:]
    deadline.now()
    sock.shutdown(socket.SHUT_WR)


def _recv(sock, count, deadline):
    while True:
        deadline.now()
        try:
            chunk, ancillary, flags, _address = sock.recvmsg(
                count, socket.CMSG_SPACE(256 * array.array("i").itemsize), socket.MSG_CMSG_CLOEXEC)
        except (BlockingIOError, InterruptedError):
            deadline.wait(sock)
            continue
        # Close every delivered right before any error, including CTRUNC. The
        # kernel can have installed FDs even when the payload will be rejected.
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                rights = array.array("i")
                rights.frombytes(data[:len(data) - len(data) % rights.itemsize])
                for fd in rights:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
        require(not ancillary and not flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC), "ANCILLARY")
        deadline.now()
        return chunk


def _exact(sock, count, deadline):
    result = bytearray()
    while len(result) < count:
        chunk = _recv(sock, count - len(result), deadline)
        require(bool(chunk), "PARTIAL_FRAME")
        result.extend(chunk)
    return bytes(result)


def _exchange(sock, wire, deadline):
    _send(sock, struct.pack("!I", len(wire)) + wire, deadline)
    size = struct.unpack("!I", _exact(sock, 4, deadline))[0]
    require(0 < size <= RESPONSE_LIMIT, "RESPONSE_LENGTH")
    response = _exact(sock, size, deadline)
    require(_recv(sock, 1, deadline) == b"", "TRAILING_BYTES")
    return response


def observe(endpoint, request, expected_roots):
    """Return bound immutable facts, or raise without retrying or releasing.

    Endpoint/request/expected roots are trusted bootstrap inputs. This client
    does not authenticate their origin or consume a grant. Service-side durable
    admission and bootstrap integration remain separate prerequisites.
    """
    try:
        request = decode_request(request.wire)
        original = request.as_dict()
        roots = validate_expected_roots(expected_roots, original["phase"])
        deadline = _Deadline(original["deadline_ns"])
        require(_boot_id() == endpoint.boot_id == original["boot_id"], "BOOT_BINDING")
        before = _endpoint_identity(endpoint)
        deadline.now()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.setblocking(False)
            _connect(sock, endpoint, deadline)
            require(_endpoint_identity(endpoint) == before, "ENDPOINT_CHANGED")
            response = _exchange(sock, request.wire, deadline)
            require(_endpoint_identity(endpoint) == before, "ENDPOINT_CHANGED")
            require(_boot_id() == endpoint.boot_id, "BOOT_BINDING")
            result = decode_receipt(response, request, roots, now_ns=deadline.now())
            require(deadline.now() < result.as_dict()["deadline_ns"], "DEADLINE")
            return result
    except OSError:
        raise QuotaError("TRANSPORT_IO") from None
