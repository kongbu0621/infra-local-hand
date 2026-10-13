"""Service-side lifetime of one administrator-created execution session.

The public transports submit/read/cancel through Broker. Only the inherited
administrator channels can bind quota observations or authorize phase changes.
The session never submits a request on behalf of a client.
"""
from __future__ import annotations

import os
from pathlib import Path
import select
import socket
import stat

from . import budget, manager_binding, quota_binding, quota_bridge, quota_closure, quota_payload
from . import quota_contract as q
from .broker import phase_plan, thaw
from .contract import JobError

SCHEMA = "local-hand-task-session/v1"
PHASES = quota_bridge.JOB_PHASES
LIMIT = 65536


def read_descriptor(path):
    """Read a root-owned declaration through retained, non-symlink ancestors."""
    path = q.canonical_path(str(path))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        parts = Path(path).parts[1:]
        for index, part in enumerate(parts):
            directory = index < len(parts) - 1
            child = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
                            | (os.O_DIRECTORY if directory else 0), dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            q.require(info.st_uid == 0 and not info.st_mode & 0o022
                      and (stat.S_ISDIR(info.st_mode) if directory else
                           stat.S_ISREG(info.st_mode) and info.st_nlink == 1), "SESSION_PROTECTION")
        q.require(info.st_size <= LIMIT, "SESSION_SIZE")
        raw = bytearray()
        while len(raw) <= LIMIT:
            chunk = os.read(fd, min(8192, LIMIT + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        after = os.fstat(fd)
        q.require(len(raw) == info.st_size and all(getattr(info, key) == getattr(after, key)
                  for key in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink",
                              "st_size", "st_mtime_ns", "st_ctime_ns")), "SESSION_CHANGED")
        return q._load(bytes(raw), LIMIT, 12)
    finally:
        os.close(fd)


def bridge_from_pin(pin):
    from .system_manager_protocol import start_ticks
    q._keys(pin, {"fd", "pid", "uid", "gid", "start_ticks", "session", "boot_id", "deadline_ns"})
    q.integer(pin["fd"], 3)
    q.integer(pin["pid"], 1)
    q.integer(pin["start_ticks"], 1)
    q.require(type(pin["uid"]) is int and type(pin["gid"]) is int
              and (pin["uid"], pin["gid"]) == (0, 0) and pin["pid"] != os.getpid()
              and start_ticks(pin["pid"]) == pin["start_ticks"], "SESSION_ADMINISTRATOR")
    sock = socket.socket(fileno=pin["fd"])
    channel = None
    try:
        q.require(sock.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) == 1,
                  "SESSION_CREDENTIALS")
        channel = quota_bridge.Channel(sock, peer=(pin["pid"], 0, 0), session=pin["session"],
            boot_id=pin["boot_id"], deadline_ns=pin["deadline_ns"], version=2)
        q.require(start_ticks(pin["pid"]) == pin["start_ticks"], "SESSION_ADMINISTRATOR")
        return channel
    except BaseException:
        (channel if channel is not None else sock).close()
        raise


def admit_host(value, policy):
    """Check the same unprivileged account/namespace separation as execution."""
    configuration = thaw(policy.config["process_manager"])
    binding = manager_binding.from_configuration(configuration, authority_id=policy.authority_id)
    q.require(binding is not None, "SESSION_SYSTEM_MANAGER_REQUIRED")
    manager_binding.check(binding, value["manager_binding"])
    q.require(os.getuid() == os.geteuid() == configuration["uid"]
              and os.getgid() == os.getegid() == configuration["gid"]
              and set(os.getgroups()) <= {configuration["gid"]}, "SESSION_ACCOUNT")
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    q.require(status.get("NoNewPrivs", "").strip() == "1"
              and all(int(status[name].strip(), 16) == 0
                      for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")),
              "SESSION_CAPABILITIES")
    q._keys(value["initial_userns"], {"device", "inode"})
    namespace = os.stat("/proc/self/ns/user")
    q.require(value["initial_userns"] == {"device": namespace.st_dev, "inode": namespace.st_ino},
              "SESSION_USER_NAMESPACE")
    own = Path("/proc/self/cgroup").read_text()
    parent = binding["parent"]["path"]
    control = value["broker_cgroup"]
    q.canonical_path(control)
    q.require(own == "0::" + control + "\n" and control != parent
              and Path(control).parent == Path(parent).parent, "SESSION_CONTROL_SEPARATION")
    parent_info = os.stat(configuration["cgroup"], follow_symlinks=False)
    q.require(parent_info.st_uid == 0 and not parent_info.st_mode & 0o022, "SESSION_SYSTEM_PARENT")
    for name in ("cgroup.controllers", "cgroup.subtree_control"):
        q.require({"cpu", "memory", "pids"} <= set(Path(configuration["cgroup"]).parent.joinpath(name)
                  .read_text().split()), "SESSION_CONTROLLERS")
    now = budget.current_clock()
    pin = value["manager_channel"]
    q.require(binding["boot_id"] == pin["boot_id"] == now["boot_id"]
              and 0 < pin["deadline_ns"] - now["boottime_ns"] <= 600 * budget.NANOSECONDS,
              "SESSION_DEADLINE")


class TaskSession:
    def __init__(self, value, manager, channel):
        self.value, self.manager, self.channel = value, manager, channel
        self.broker = None
        self.phase = None
        self.handler = None
        self.started = False
        self.closed = False
        self.finished = False
        self.failure = None
        self.preparations = {}
        self.closures = {}
        self.terminal_sent = False

    @classmethod
    def open(cls, path, policy):
        from .system_manager import SystemManager, channel_from_pin
        value = read_descriptor(path)
        q._keys(value, {"schema", "mode", "policy_digest", "operation_id", "request_digest",
                       "principal_id", "manager_binding", "initial_userns", "broker_cgroup",
                       "manager_channel", "bridge"})
        q.require(value["schema"] == SCHEMA and value["mode"] in ("execute", "recover"), "SESSION_SCHEMA")
        q.match(value["operation_id"], q.UUID_PATTERN)
        q.match(value["request_digest"], r"[0-9a-f]{64}")
        q.require(value["policy_digest"] == policy.policy_digest
                  and value["principal_id"] in policy.principals, "SESSION_POLICY")
        if value["mode"] == "recover":
            q.require(value["bridge"] is None, "SESSION_RECOVERY_CHANNEL")
        else:
            q.require(type(value["bridge"]) is dict and
                      value["bridge"].get("fd") != value["manager_channel"].get("fd") and
                      all(value["bridge"].get(key) == value["manager_channel"].get(key)
                          for key in ("pid", "uid", "gid", "start_ticks", "boot_id", "deadline_ns")),
                      "SESSION_CHANNEL_BINDING")
        admit_host(value, policy)
        channel = manager_channel = manager = None
        try:
            manager_channel = channel_from_pin(value["manager_channel"])
            manager = SystemManager(policy.config["process_manager"], channel=manager_channel,
                                    recovery=value["mode"] == "recover")
            if value["mode"] == "execute":
                channel = bridge_from_pin(value["bridge"])
            return cls(value, manager, channel)
        except BaseException:
            for resource in (channel, manager if manager is not None else manager_channel):
                if resource is not None:
                    resource.close()
            raise

    def attach(self, broker):
        """Bind before exposing either public transport or starting a thread."""
        q.require(self.broker is None and broker.quota_required, "SESSION_ATTACHMENT")
        with broker.state.transaction() as tx:
            rows = broker.state.all(tx)
        for row in rows:
            if row["record"]["lifecycle"] != "TERMINAL":
                q.require(row["namespace"] == "job" and row["id"] == self.value["operation_id"],
                          "SESSION_OTHER_ACTIVE_OPERATION")
        row = broker.state.get("job", self.value["operation_id"])
        if row is not None:
            q.require(row["digest"] == self.value["request_digest"]
                      and row["principal"] == self.value["principal_id"], "SESSION_OPERATION_CHANGED")
            q.require(self.value["mode"] == "recover" or
                      row["record"]["phase"] == "QUEUED"
                      and not row["record"].get("execution_budget"), "SESSION_RECOVERY_REQUIRED")
        else:
            q.require(self.value["mode"] == "execute", "SESSION_RECOVERY_MISSING")
        self.broker = broker
        broker.task_session = self

    def admit(self, request, principal):
        if self.closed or self.failure is not None or self.value["mode"] != "execute":
            raise JobError("UNSUPPORTED", "This session permits observation of its original task only")
        if (request["operation_id"] != self.value["operation_id"]
                or request["request_digest"] != self.value["request_digest"]
                or principal.principal_id != self.value["principal_id"]):
            raise JobError("UNAUTHORIZED", "Request does not match this task session")

    def recover(self):
        if self.value["mode"] == "recover":
            self.broker.recover()

    def _prepare(self, phase):
        b, identity = self.broker, self.value["operation_id"]
        with b.fence:
            # Cancellation may commit after the coordinator's first snapshot
            # or while the administrator's advance packet is in flight.
            if b.state.get("job", identity)["record"]["cancel_requested"]:
                return  # The next tick publishes the original stopped state.
            b._start("job", identity, phase)
            handler = quota_bridge.Phase(b, "job", identity, phase, version=2)
            snapshot = handler.snapshot()
            with b.state.transaction() as tx:
                row = b.state.get("job", identity, tx)
                prepared = quota_binding.original(tx, row, phase, "QUOTA_PREPARATION", "quota_preparations")
                q.require(prepared["session"] == b._quota_session and
                          prepared == snapshot["preparation"] and not row["record"].get("recovered"),
                          "SESSION_PREPARATION_CHANGED")
                for earlier, closed in self.closures.items():
                    q.require(quota_binding.original(tx, row, earlier, "QUOTA_PHASE_CLOSED", "quota_closed")
                              == closed, "SESSION_CLOSURE_CHANGED")
                plan = phase_plan(row, phase, prepared["budget"], allocation=prepared["allocation"],
                    evidence_store_root=str(b.evidence.root) if phase == "evidence" else None,
                    manager_binding=b.manager_binding)
            self.phase, self.handler, self.started = phase, handler, False
            self.preparations[phase] = prepared
        self.channel.send(dict(event="prepared", namespace="job", identity=identity, phase=phase,
                               snapshot=snapshot, phase_plan=quota_payload.encode_phase_plan(plan)))

    def _advance(self, command):
        index = len(self.closures)
        q.require(0 < index < len(PHASES), "SESSION_ADVANCE")
        previous, following = PHASES[index - 1], PHASES[index]
        q.require(command == dict(action="advance", value={"from": previous, "to": following,
                  "closure_digest": quota_closure.digest(self.closures[previous])}), "SESSION_ADVANCE")
        # This advances transport accounting, not permission to run a phase.
        self.channel.advance_phase(following)
        self.phase = following
        return following

    def tick(self):
        if self.closed or self.finished:
            return
        if self.failure is not None:
            if ("job", self.value["operation_id"]) in self.broker._active:
                self.broker.tick()
            return
        try:
            self._tick()
        except Exception as error:
            # A failed control exchange never becomes an automatic resubmit.
            # Keep the public read/cancel transports and the original ledger.
            self.failure = type(error).__name__
            row = self.broker.state.get("job", self.value["operation_id"])
            if row is not None and row["record"]["lifecycle"] != "TERMINAL":
                self.broker._unknown("job", row["id"], "Task session requires recovery; original execution retained")
            raise JobError("IO_UNCERTAIN", "Original task session requires recovery") from error

    def _tick(self):
        b, identity = self.broker, self.value["operation_id"]
        row = b.state.get("job", identity)
        if row is None:
            self.channel._time()
            return  # Only a real client submission may create this task.
        if self.value["mode"] == "recover":
            if ("job", identity) in b._active or ("job", identity) in b._recovering:
                b.tick()
            if ("job", identity) not in b._active and ("job", identity) not in b._recovering:
                self.manager.finish_recovery()
                self.finished = True
            return
        record = row["record"]
        if record["cancel_requested"] or self.started:
            b.tick()
            record = b.state.get("job", identity)["record"]
        stopped = record["lifecycle"] == "TERMINAL" and record["cancel_requested"]
        self.channel._time()
        if stopped:
            index = len(self.closures)
            awaiting_advance = (self.handler is None and 0 < index < len(PHASES)
                                and self.phase == PHASES[index - 1])
            if self.handler is None and not self.terminal_sent and not awaiting_advance:
                self.channel.send(dict(event="terminal", namespace="job", identity=identity,
                                       task=self._status(record)))
                self.terminal_sent = True
            if select.select([self.channel.sock], [], [], 0)[0]:
                command = self.channel.receive()
                if command == {"action": "finish", "value": None}:
                    self.finished = True
                elif awaiting_advance:
                    # The peer advances immediately after sending this packet.
                    # Reply only after matching that transport phase, without
                    # preparing or delivering the now-cancelled next phase.
                    self._advance(command)
                    self.channel.send(dict(event="terminal", namespace="job", identity=identity,
                                           task=self._status(record)))
                    self.terminal_sent = True
                else:
                    # Cancellation can commit while the administrator's bind
                    # or start packet is in flight. Reply with the real stopped
                    # state without applying that packet or launching a stage.
                    q.require(type(command) is dict and set(command) == {"action", "value"}
                              and command["action"] in ("snapshot", "bind", "start")
                              and self.handler is not None, "SESSION_STOPPED")
                    self.channel.send(dict(self.handler.snapshot(), task=self._status(record)))
            return
        if self.handler is None:
            if not self.closures:
                self._prepare("preflight")
                return
            if not select.select([self.channel.sock], [], [], 0)[0]:
                return
            command = self.channel.receive()
            index = len(self.closures)
            if index == len(PHASES):
                q.require(command == {"action": "finish", "value": None}, "SESSION_FINISH")
                self.finished = True
                return
            self._prepare(self._advance(command))
            return
        if select.select([self.channel.sock], [], [], 0)[0]:
            command = self.channel.receive()
            q.require(type(command) is dict and (command.get("action") != "start" or not self.started),
                      "SESSION_START_REPLAY")
            reply = self.handler.handle(command)
            self.channel.send(dict(reply, task=self._status(b.state.get("job", identity)["record"])))
            if command["action"] == "start":
                self.started = True
            if reply["closed"] is not None:
                self.closures[self.phase] = reply["closed"]
                self.handler = None
                self.started = False

    @staticmethod
    def _status(record):
        return {key: record[key] for key in ("lifecycle", "phase", "outcome", "cancel_requested")}

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.channel is not None:
                self.channel.close()
        finally:
            self.manager.close()
