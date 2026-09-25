"""Private, inherited administrator channel for one resident broker phase.

Not a listening socket, MCP method, CLI route, grant issuer or restart API.
The trusted fixture creates/pins both processes and their inherited socketpair.
SCM_CREDENTIALS authenticates the sender of EVERY packet: SO_PEERCRED on an
inherited socketpair would identify its creator, not its eventual sender.
"""
from __future__ import annotations

import array
import os
import select
import socket
import struct

from . import budget, quota_binding as binding, quota_contract as q, quota_grant as g

LIMIT = 2 * 1024 * 1024
CHUNK = 16384
HEADER = struct.Struct("!III")
SCHEMA = "local-hand-quota-bridge/v1"
CHAIN_SCHEMA = "local-hand-quota-bridge/v2"
JOB_PHASES = ("preflight", "business", "evidence")


class Channel:
    """Bounded, ordered, credentialed records; any uncertainty poisons the FD.

    The socket and expected pid/uid/gid come from trusted process creation,
    NEVER from an incoming record. There is no reconnect or retransmission.
    A retained pidfd prevents a replacement process satisfying the PID pin.
    """
    def __init__(self, sock, *, peer, session, boot_id, deadline_ns, version=1):
        q.require(type(version) is int and version in (1, 2), "BRIDGE_VERSION")
        q.require(sock.family == socket.AF_UNIX and sock.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
                  == socket.SOCK_SEQPACKET, "BRIDGE_SOCKET")
        q.require(type(peer) is tuple and len(peer) == 3, "BRIDGE_PEER")
        for value in peer:q.integer(value)
        q.integer(peer[0], 1)
        q.match(session, r"[0-9a-f]{64}");q.match(boot_id, q.UUID_PATTERN)
        self.sock, self.peer, self.session, self.boot_id = sock, peer, session, boot_id
        self.end = q.integer(deadline_ns, 1)
        self.owner = os.getpid()
        self.tx = self.rx = self.total = self.packets = 0
        self.version, self.phase_index = version, 0
        self.phase_tx = self.phase_rx = self.phase_total = self.phase_packets = 0
        self.poisoned = False
        self.pidfd = os.pidfd_open(peer[0], 0)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            sock.setblocking(False)
            self._time()
        except BaseException:
            os.close(self.pidfd);self.pidfd = -1
            raise

    def _time(self):
        clock = budget.current_clock()
        q.require(not self.poisoned and self.owner == os.getpid() and clock["boot_id"] == self.boot_id
                  and clock["boottime_ns"] < self.end, "BRIDGE_UNAVAILABLE")
        q.require(self.pidfd >= 0 and not select.select([self.pidfd], [], [], 0)[0], "BRIDGE_PEER_EXITED")
        return clock["boottime_ns"]

    def _wait(self, writing, end):
        now = self._time()
        q.require(now < end, "BRIDGE_TIMEOUT")
        ready = select.select([] if writing else [self.sock], [self.sock] if writing else [],
                              [], min(0.05, (end-now)/1e9))
        return bool(ready[1 if writing else 0])

    def _charge(self, count):
        self.total += count;self.packets += 1
        self.phase_total += count;self.phase_packets += 1
        phases = len(JOB_PHASES) if self.version == 2 else 1
        q.require(self.total <= phases * 8 * LIMIT and self.packets <= phases * 2048
                  and self.phase_total <= 8 * LIMIT and self.phase_packets <= 2048, "BRIDGE_TOTAL_LIMIT")

    def advance_phase(self, phase):
        """Advance fixed transport accounting only; never an execution grant.

        Both original peers call after sending/validating the authenticated
        advance command. Global order, byte totals and deadline remain intact.
        The resident separately proves the prior durable phase closure.
        """
        try:
            self._time()
            q.require(self.version == 2 and self.phase_index + 1 < len(JOB_PHASES)
                      and phase == JOB_PHASES[self.phase_index + 1], "BRIDGE_PHASE_ORDER")
            self.phase_index += 1
            self.phase_tx = self.phase_rx = self.phase_total = self.phase_packets = 0
        except BaseException:
            self.poisoned = True
            raise

    def send(self, value):
        try:
            self._time()
            q.require(self.phase_tx < 64 and self.tx < (192 if self.version == 2 else 64), "BRIDGE_EXCHANGE_LIMIT")
            envelope = dict(schema=SCHEMA, session=self.session, value=value)
            if self.version == 2:
                from . import quota_payload
                envelope.update(schema=CHAIN_SCHEMA, phase=JOB_PHASES[self.phase_index])
                envelope["value"] = quota_payload.encode_bridge_value(value)
            raw = q._canonical(envelope, LIMIT)
            end = min(self.end, self._time()+2_000_000_000)
            for offset in range(0,len(raw),CHUNK):
                packet = HEADER.pack(self.tx, offset, len(raw)) + raw[offset:offset+CHUNK]
                while True:
                    if not self._wait(True,end):continue
                    try:written = self.sock.send(packet, socket.MSG_NOSIGNAL)
                    except BlockingIOError:continue
                    q.require(written == len(packet), "BRIDGE_PARTIAL_SEND")
                    self._charge(written);break
            self._time();self.tx += 1;self.phase_tx += 1
        except BaseException:
            self.poisoned = True
            raise

    def receive(self):
        try:
            q.require(self.phase_rx < 64 and self.rx < (192 if self.version == 2 else 64), "BRIDGE_EXCHANGE_LIMIT")
            end = min(self.end, self._time()+2_000_000_000)
            raw = bytearray();expected = None
            while expected is None or len(raw) < expected:
                if not self._wait(False,end):continue
                try:
                    packet, ancillary, flags, _ = self.sock.recvmsg(HEADER.size+CHUNK,
                        socket.CMSG_SPACE(12)+socket.CMSG_SPACE(256), socket.MSG_CMSG_CLOEXEC)
                except BlockingIOError:continue
                descriptors=[];credentials=[];unexpected=False
                for level, kind, data in ancillary:
                    if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                        values=array.array('i');values.frombytes(data[:len(data)//values.itemsize*values.itemsize])
                        descriptors.extend(values)
                    elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data)==12:
                        credentials.append(struct.unpack('3i',data))
                    else:unexpected=True
                # Close even rejected descriptors, including those returned on
                # ancillary truncation. The kernel closes omitted rights.
                try:
                    q.require(not descriptors and not unexpected and credentials == [self.peer]
                        and not flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC), "BRIDGE_CREDENTIALS")
                finally:
                    for fd in descriptors:os.close(fd)
                self._charge(len(packet))
                q.require(len(packet) > HEADER.size, "BRIDGE_EOF")
                seq, offset, size = HEADER.unpack(packet[:HEADER.size])
                q.require(seq == self.rx and offset == len(raw) and 0 < size <= LIMIT
                    and (expected is None or expected == size), "BRIDGE_ORDER")
                expected = size;raw.extend(packet[HEADER.size:])
                q.require(len(raw) <= expected and len(packet)-HEADER.size == min(CHUNK,size-offset), "BRIDGE_FRAME")
            value = q._load(bytes(raw), LIMIT, 20)
            q._keys(value, {"schema","session","value"} | ({"phase"} if self.version == 2 else set()))
            q.require(value["schema"] == (CHAIN_SCHEMA if self.version == 2 else SCHEMA)
                      and value["session"] == self.session, "BRIDGE_SESSION")
            if self.version == 2:
                from . import quota_payload
                q.require(value["phase"] == JOB_PHASES[self.phase_index], "BRIDGE_PHASE_ORDER")
                value["value"] = quota_payload.decode_bridge_value(value["value"])
            self._time();self.rx += 1;self.phase_rx += 1
            return value["value"]
        except BaseException:
            self.poisoned = True
            raise

    def close(self):
        self.poisoned = True
        try:self.sock.close()
        finally:
            if self.pidfd >= 0:
                os.close(self.pidfd);self.pidfd = -1


class Phase:
    """Only the originally selected operation/phase is reachable on this FD.

    Call from a separate finite bridge worker in the resident broker process.
    Immutable event verification and mutations use the existing broker fence.
    The ordinary maintenance transport does not construct or expose this class.
    """
    def __init__(self, broker, namespace, identity, phase, *, version=1):
        q.require(type(version) is int and version in (1, 2), "BRIDGE_VERSION")
        q.require(namespace in q._PHASES and phase in q._PHASES[namespace], "BRIDGE_PHASE")
        self.broker, self.namespace, self.identity, self.phase = broker, namespace, identity, phase
        self.version = version
        self.session = broker._quota_session
        self.failed = False

    def snapshot(self):
        b = self.broker
        with b.fence, b.state.transaction() as tx:
            row = b.state.get(self.namespace,self.identity,tx)
            q.require(row is not None and not row['record'].get('recovered')
                and binding.admission_version(tx,row) == 1, "BRIDGE_ORIGINAL_ADMISSION")
            prep = binding.original(tx,row,self.phase,'QUOTA_PREPARATION','quota_preparations')
            q.require(prep['session'] == self.session == b._quota_session, "QUOTA_RECOVERY_BARRIER")
            result = dict(preparation=prep, observation=None, pending=None, closed=None)
            for name, kind, field in (('observation','QUOTA_OBSERVED','quota_observed'),
                    ('pending','QUOTA_EXIT_PENDING','quota_pending'),('closed','QUOTA_PHASE_CLOSED','quota_closed')):
                if self.phase in row['record'].get(field,{}) or binding.recorded(tx,row,self.phase,kind):
                    result[name] = binding.original(tx,row,self.phase,kind,field)
            # Canonical copy prevents sharing mutable state beyond the fence.
            if self.version == 2:
                from . import quota_payload
                return quota_payload.decode_bridge_value(q._load(q._canonical(
                    quota_payload.encode_bridge_value(result), LIMIT), LIMIT, 20))
            return q._load(q._canonical(result,LIMIT),LIMIT,20)

    def handle(self, command):
        q.require(not self.failed, "BRIDGE_POISONED")
        try:
            q._keys(command, {'action','value'})
            b=self.broker;action=command['action'];value=command['value']
            q.require(self.session == b._quota_session, "QUOTA_RECOVERY_BARRIER")
            if action == 'snapshot':
                q.require(value is None, "BRIDGE_ARGUMENT")
                return self.snapshot()
            if action == 'bind':
                grant=g.decode_grant(q._canonical(value,g.GRANT_LIMIT))
                b.bind_observation(self.namespace,self.identity,self.phase,grant.wire)
            elif action == 'start':
                q.require(value is None, "BRIDGE_ARGUMENT")
                # Refuse an unbound phase instead of creating a new preparation.
                with b.fence,b.state.transaction() as tx:
                    row=b.state.get(self.namespace,self.identity,tx)
                    binding.selected(tx,row,self.phase,session=self.session,
                        now_ns=budget.current_clock()['boottime_ns'])
                b._start(self.namespace,self.identity,self.phase)
            elif action == 'close':
                b.close_observation(self.namespace,self.identity,self.phase,value)
            else:raise q.QuotaError('BRIDGE_ACTION')
            return self.snapshot()
        except BaseException:
            self.failed = True
            raise

    def serve_once(self, channel):
        # Root credentials are required on every request, not just constructor.
        q.require(channel.peer[1:] == (0,0), "BRIDGE_ADMINISTRATOR")
        try:channel.send(self.handle(channel.receive()))
        except BaseException:
            self.failed=True;channel.poisoned=True
            raise


class Client:
    def __init__(self, channel):
        q.require(channel.peer[1] > 0 and channel.peer[2] > 0, "BRIDGE_ORDINARY_PEER")
        self.channel = channel

    def call(self, action, value=None):
        self.channel.send(dict(action=action,value=value))
        return self.channel.receive()


def serve_phase(phase, channel):
    """Finite worker in the original resident process; no broker restart/start.

    A closed phase returns after its acknowledgment. Closing this private FD
    cannot prove the independently managed ordinary units or collectors exited.
    """
    try:
        while True:
            channel._time()
            if not select.select([channel.sock],[],[],0.05)[0]:continue
            phase.serve_once(channel)
            if phase.snapshot()['closed'] is not None:return
    finally:channel.close()
