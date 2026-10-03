"""Finite inherited controller channel, shared by the two original processes.

This module contains no listener, command execution, admission or reconnect.
Every packet carries kernel sender credentials; launch replies alone carry two
read-only anonymous pipes. Any uncertain exchange permanently consumes the FD.
"""
from __future__ import annotations

import array
import fcntl
import os
import select
import socket
import stat
import struct

from . import budget, quota_contract as q

SCHEMA = "local-hand-q2-system-manager/v1"
REQUEST_LIMIT = 65536
RESPONSE_LIMIT = 32768
WIRE_LIMIT = 4 * 1024 * 1024
CALL_LIMIT = 256
PHASES = ("preflight", "business", "evidence")
STAGES = ("bootstrap", "helper", "result_reader")
RECOVERY_PLAN_SCHEMA = "local-hand-q4-h11-recovery-plan/v1"
OPS = {"support", "inventory", "observe", "stop", "launch", "client_poll", "client_stop", "seal",
       "recovery_arm", "recovery_finish"}


def start_ticks(pid):
    q.integer(pid, 1)
    q.require(os.readlink("/proc/self") == str(os.getpid()), "SYSTEM_PROC_NAMESPACE")
    fd = os.open("/proc/" + str(pid) + "/stat", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        raw = os.read(fd, 4097)
        q.require(len(raw) <= 4096 and b")" in raw, "SYSTEM_PEER_STAT")
        return q.integer(int(raw.rsplit(b")", 1)[1].split()[19]), 1)
    finally:
        os.close(fd)


def reference(value):
    q._keys(value, {"execution_id", "phase", "stage"})
    q.match(value["execution_id"], r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
    q.require(value["phase"] in PHASES and value["stage"] in STAGES, "SYSTEM_STAGE")
    return value


def recovery_plan(value):
    """Finite test-only identity handoff; it contains no launch authority."""
    q._keys(value, {"schema", "namespace", "operation_id", "request_digest", "phase",
                    "execution_id", "event_seq", "handle_sha256", "budget_deadline_ns",
                    "phase_deadline_ns", "controller_deadline_ns", "units",
                    "collector_started"})
    q.require(value["schema"] == RECOVERY_PLAN_SCHEMA and value["namespace"] == "job",
              "SYSTEM_RECOVERY_PLAN")
    q.match(value["operation_id"], r"[0-9a-f-]{36}")
    q.match(value["request_digest"], r"[0-9a-f]{64}")
    q.require(value["phase"] in PHASES and
              value["execution_id"] == "job-" + value["operation_id"] + "-" + value["phase"],
              "SYSTEM_RECOVERY_PLAN")
    q.integer(value["event_seq"], 1)
    q.match(value["handle_sha256"], r"[0-9a-f]{64}")
    q.integer(value["budget_deadline_ns"], 1)
    q.integer(value["phase_deadline_ns"], 1)
    q.integer(value["controller_deadline_ns"], value["budget_deadline_ns"])
    q.require(value["phase_deadline_ns"] <= value["budget_deadline_ns"]
              and value["collector_started"] is False, "SYSTEM_RECOVERY_PLAN")
    q._keys(value["units"], set(STAGES))
    for unit in value["units"].values():
        q.match(unit, r"lhj-[0-9a-f]{64}\.service")
    q.require(len(set(value["units"].values())) == len(STAGES), "SYSTEM_RECOVERY_PLAN")
    return value


def request_body(op, body):
    q.require(op in OPS, "SYSTEM_OPERATION")
    fields = {"support": set(), "inventory": set(), "observe": {"ref", "view"},
              "stop": {"ref", "invocation_id"}, "launch": {"ref", "bindings"},
              "client_poll": {"ref", "token"}, "client_stop": {"ref", "token"},
              "seal": {"ref", "token"}, "recovery_arm": {"plan"}, "recovery_finish": set()}
    q._keys(body, fields[op])
    if "ref" in body:
        reference(body["ref"])
    if op == "observe":
        q.require(body["view"] in ("full", "invocation", "identity"), "SYSTEM_VIEW")
    if op == "stop":
        q.match(body["invocation_id"], r"[0-9a-f]{32}")
    if op == "launch":
        q._keys(body["bindings"], {"allocation_digest", "grant_digest"})
        for value in body["bindings"].values():
            q.match(value, r"[0-9a-f]{64}")
    if op == "recovery_arm":
        recovery_plan(body["plan"])
    if "token" in body:
        q.match(body["token"], r"[0-9a-f]{64}")
    return body


def readonly_pipe(fd):
    info = os.fstat(fd)
    q.require(stat.S_ISFIFO(info.st_mode) and
              fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY,
              "SYSTEM_READONLY_PIPE")
    q.match(os.readlink("/proc/self/fd/" + str(fd)), r"pipe:\[[0-9]+\]")
    os.set_inheritable(fd, False)
    return (info.st_dev, info.st_ino)


class Channel:
    """One outstanding call, original pidfd/start-time, no retransmission."""
    def __init__(self, sock, *, peer, peer_start_ticks, session_id, boot_id, deadline_ns):
        q.require(sock.family == socket.AF_UNIX and
                  sock.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) == socket.SOCK_SEQPACKET,
                  "SYSTEM_SOCKET")
        q.require(type(peer) is tuple and len(peer) == 3, "SYSTEM_PEER")
        for item in peer:
            q.integer(item)
        q.integer(peer[0], 1)
        q.match(session_id, r"[0-9a-f]{64}"); q.match(boot_id, q.UUID_PATTERN)
        self.sock, self.peer, self.session_id, self.boot_id = sock, peer, session_id, boot_id
        self.peer_start_ticks = q.integer(peer_start_ticks, 1)
        self.end = q.integer(deadline_ns, 1)
        self.owner = os.getpid()
        self.sequence = self.total = 0
        self.pending = None
        self.poisoned = False
        self.pidfd = os.pidfd_open(peer[0], 0)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            sock.setblocking(False)
            self._time()
        except BaseException:
            os.close(self.pidfd); self.pidfd = -1
            raise

    def _time(self):
        now = budget.current_clock()
        q.require(not self.poisoned and self.owner == os.getpid() and
                  now["boot_id"] == self.boot_id and now["boottime_ns"] < self.end,
                  "SYSTEM_CHANNEL_UNAVAILABLE")
        q.require(self.pidfd >= 0 and not select.select([self.pidfd], [], [], 0)[0]
                  and start_ticks(self.peer[0]) == self.peer_start_ticks, "SYSTEM_PEER_CHANGED")
        poller = select.poll()
        poller.register(self.sock, select.POLLERR | select.POLLHUP | select.POLLNVAL)
        q.require(not poller.poll(0), "SYSTEM_CHANNEL_DISCONNECTED")
        return now["boottime_ns"]

    def _charge(self, raw, fds):
        self.total += len(raw) + 12 + 4 * len(fds)
        q.require(self.total <= WIRE_LIMIT, "SYSTEM_WIRE_LIMIT")

    def _wait(self, writing, end):
        now = self._time()
        q.require(now < end, "SYSTEM_CHANNEL_TIMEOUT")
        ready = select.select([] if writing else [self.sock], [self.sock] if writing else [], [],
                              min(0.025, (end - now) / 1e9))
        return bool(ready[1 if writing else 0])

    def _send(self, op, body, fds, maximum):
        raw = q._canonical(dict(schema=SCHEMA, session_id=self.session_id,
                                sequence=self.sequence, op=op, body=body), maximum)
        # Validate the same finite JSON grammar before sending as on receive.
        q._load(raw, maximum, 12)
        q.require(not fds or op == "launch" and maximum == RESPONSE_LIMIT and len(fds) == 2,
                  "SYSTEM_FD_COUNT")
        pins = [readonly_pipe(fd) for fd in fds]
        q.require(len(set(pins)) == len(pins), "SYSTEM_PIPE_ALIAS")
        self._charge(raw, fds)
        end = min(self.end, self._time() + 3_000_000_000)
        rights = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", fds))] if fds else []
        while True:
            if not self._wait(True, end):
                continue
            try:
                sent = self.sock.sendmsg([raw], rights, socket.MSG_NOSIGNAL)
            except BlockingIOError:
                continue
            q.require(sent == len(raw), "SYSTEM_PARTIAL_SEND")
            return

    def _receive(self, maximum, op=None):
        end = min(self.end, self._time() + 3_000_000_000)
        fds = []
        try:
            while True:
                if not self._wait(False, end):
                    continue
                try:
                    raw, ancillary, flags, _ = self.sock.recvmsg(maximum,
                        socket.CMSG_SPACE(12) + socket.CMSG_SPACE(256), socket.MSG_CMSG_CLOEXEC)
                    break
                except BlockingIOError:
                    continue
            credentials = []; unexpected = False
            for level, kind, value in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    rights = array.array("i")
                    rights.frombytes(value[:len(value) // rights.itemsize * rights.itemsize])
                    fds.extend(rights)
                    unexpected |= len(value) % rights.itemsize != 0
                elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(value) == 12:
                    credentials.append(struct.unpack("3i", value))
                else:
                    unexpected = True
            q.require(raw and not flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) and
                      not unexpected and credentials == [self.peer], "SYSTEM_PACKET_IDENTITY")
            self._charge(raw, fds)
            value = q._load(raw, maximum, 12)
            q._keys(value, {"schema", "session_id", "sequence", "op", "body"})
            q.require(value["schema"] == SCHEMA and value["session_id"] == self.session_id
                      and type(value["sequence"]) is int and value["sequence"] == self.sequence
                      and value["op"] in OPS and (op is None or value["op"] == op), "SYSTEM_PACKET_ORDER")
            q.require(type(value["body"]) is dict, "SYSTEM_RESPONSE")
            expected = 2 if maximum == RESPONSE_LIMIT and op == "launch" and "error" not in value["body"] else 0
            q.require(len(fds) == expected, "SYSTEM_FD_COUNT")
            pins = [readonly_pipe(fd) for fd in fds]
            q.require(len(set(pins)) == len(pins), "SYSTEM_PIPE_ALIAS")
            self._time()
            result = (value, tuple(fds)); fds = []
            return result
        finally:
            for fd in fds:
                os.close(fd)

    def request(self, op, **body):
        received = ()
        try:
            self._time()
            q.require(self.pending is None and self.sequence < CALL_LIMIT, "SYSTEM_CALL_LIMIT")
            request_body(op, body)
            self.pending = op
            self._send(op, body, (), REQUEST_LIMIT)
            value, received = self._receive(RESPONSE_LIMIT, op)
            self.sequence += 1; self.pending = None
            if "error" in value["body"]:
                q._keys(value["body"], {"error"})
                raise q.QuotaError("SYSTEM_GATEWAY_REJECTED")
            return value["body"], received
        except BaseException:
            self.poisoned = True
            for fd in received:
                os.close(fd)
            raise

    def receive_request(self):
        try:
            self._time()
            q.require(self.pending is None and self.sequence < CALL_LIMIT, "SYSTEM_CALL_LIMIT")
            value, fds = self._receive(REQUEST_LIMIT)
            request_body(value["op"], value["body"])
            self.pending = value["op"]
            return value
        except BaseException:
            self.poisoned = True
            raise

    def respond(self, request, metadata, fds=()):
        try:
            q.require(self.pending == request["op"] and request["sequence"] == self.sequence,
                      "SYSTEM_RESPONSE_ORDER")
            self._send(self.pending, metadata, fds, RESPONSE_LIMIT)
            self.sequence += 1; self.pending = None
        except BaseException:
            self.poisoned = True
            raise

    def close(self):
        self.poisoned = True
        try:
            self.sock.close()
        finally:
            if self.pidfd >= 0:
                os.close(self.pidfd); self.pidfd = -1
