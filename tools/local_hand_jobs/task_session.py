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

from . import budget, diagnostics, manager_binding, quota_binding, quota_bridge, quota_closure, quota_payload
from . import quota_contract as q
from .broker import phase_plan, thaw
from .contract import JobError
from .state import LedgerBusy

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
        self._control_started = False
        self._action = "idle"
        self._pending_close = None
        self._close_retry_logged = False
        self._recovery_acknowledged = False

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

    def _finish_unstarted_recovery(self):
        """Close this session's admitted but never dispatched task, without replay."""
        b, identity = self.broker, self.value["operation_id"]
        with b.fence, b.state.transaction() as tx:
            row = b.state.get("job", identity, tx)
            record = row["record"]
            if record["lifecycle"] == "TERMINAL" or record["phase"] != "QUEUED":
                return
            issued = tx.execute("SELECT 1 FROM events WHERE namespace='job' AND id=? AND kind IN "
                "('EXECUTION_INTENT','LAUNCH_ENQUEUED','MANAGER_DELIVERY_INTENT') LIMIT 1", (identity,)).fetchone()
            key = ("job", identity)
            if (issued is not None or record.get("handles") or record.get("delivery_intents")
                    or record.get("business_started") is not False or record.get("helper_started") is not False
                    or key in b._active or key in b._recovering):
                raise JobError("IO_UNCERTAIN", "Unstarted recovery conflicts with original execution history")
            # The recovery-only session cannot launch. The original immutable
            # ledger has no delivery intent; retained preparation is not execution.
            proof = dict(future_start_blocked=True, tree_exited=True, effects_checked=True)
            b._release(tx, row, proof)
            if tx.execute("SELECT 1 FROM leases WHERE owner=? LIMIT 1", (identity,)).fetchone() is not None:
                raise JobError("IO_UNCERTAIN", "Unstarted recovery still owns execution resources")
            b.state.update(tx, "job", identity, "RECOVERED_BEFORE_START", {
                "lifecycle": "TERMINAL", "phase": "EXITED", "outcome": "UNKNOWN", "recovered": True,
                "exit_proof": proof, "side_effects": "NONE", "execution_resources_released": True,
                "artifacts_retained": True,
                "gaps": ["Task API stopped before execution; no business result was produced"],
            })

    def _prepare(self, phase):
        self._action = "prepare_" + phase
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
        self._control_started = True
        self.channel.send(dict(event="prepared", namespace="job", identity=identity, phase=phase,
                               snapshot=snapshot, phase_plan=quota_payload.encode_phase_plan(plan)))

    def _advance(self, command):
        self._action = "advance"
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
        if self.closed:
            return
        if self.finished or self.failure is not None:
            key = ("job", self.value["operation_id"])
            row = self.broker.state.get(*key)
            # Ending the control exchange does not end the task's API window.
            # A later durable cancellation must still consume retained exits,
            # without replaying commands or repeating the recovery handshake.
            # The broker's cancel fence forbids new starts.
            if (key in self.broker._active or key in self.broker._recovering
                    or row is not None and row["record"]["cancel_requested"]
                    and row["record"]["lifecycle"] != "TERMINAL"):
                self.broker.tick()
            return
        self._control_started = False
        self._action = "observe"
        # Reads and observation of the original execution precede the control
        # exchange. Failure here has not consumed the next queued command.
        # StateStore still blocks an actually damaged or uncertain ledger.
        row = self.broker.state.get("job", self.value["operation_id"])
        if row is not None:
            key = ("job", self.value["operation_id"])
            if self.value["mode"] == "recover":
                if key in self.broker._active or key in self.broker._recovering:
                    self.broker.tick()
            elif self._pending_close is None and (row["record"]["cancel_requested"] or self.started):
                self.broker.tick()
                row = self.broker.state.get(*key)
        try:
            self._action = "exchange"
            self._tick(row)
        except Exception as error:
            if isinstance(error, LedgerBusy) and not self._control_started:
                raise  # Local preparation can reuse its original reservation.
            if isinstance(error, LedgerBusy) and self._action == "close" and self._pending_close is not None:
                # Keep the exact consumed close until its durable publication
                # can reply. No control packet has been sent and no stage is
                # launched. The original channel deadline still bounds retry.
                if not self._close_retry_logged:
                    diagnostics.failure("task_session", error, operation_id=self.value["operation_id"],
                                        phase=self.phase, action="close_retry", control_started=True)
                    self._close_retry_logged = True
                raise
            # A failed control exchange never becomes an automatic resubmit.
            # Keep the public read/cancel transports and the original ledger.
            diagnostics.failure("task_session", error, operation_id=self.value["operation_id"],
                phase=self.phase, action=self._action, control_started=self._control_started)
            self.failure = type(error).__name__
            row = self.broker.state.get("job", self.value["operation_id"])
            if row is not None and row["record"]["lifecycle"] != "TERMINAL":
                self.broker._unknown("job", row["id"], "Task session requires recovery; original execution retained")
            raise JobError("IO_UNCERTAIN", "Original task session requires recovery") from error

    def _receive(self):
        self._action = "receive"
        command = self.channel.receive()
        action = command.get("action") if type(command) is dict else None
        self._action = (action if type(action) is str and action in
                        ("snapshot", "bind", "start", "close", "advance", "finish") else "invalid_command")
        return command

    def _tick(self, row):
        b, identity = self.broker, self.value["operation_id"]
        if row is None:
            self.channel._time()
            return  # Only a real client submission may create this task.
        if self.value["mode"] == "recover":
            if ("job", identity) not in b._active and ("job", identity) not in b._recovering:
                if not self._recovery_acknowledged:
                    self._control_started = True
                    self.manager.finish_recovery()
                    self._recovery_acknowledged = True
                # The surviving manager has proved its execution parent empty.
                # Retry local ledger contention without resending its handshake.
                self._control_started = False
                self._finish_unstarted_recovery()
                self.finished = True
            return
        record = row["record"]
        stopped = record["lifecycle"] == "TERMINAL" and record["cancel_requested"]
        self.channel._time()
        if stopped and self._pending_close is None:
            index = len(self.closures)
            awaiting_advance = (self.handler is None and 0 < index < len(PHASES)
                                and self.phase == PHASES[index - 1])
            if self.handler is None and not self.terminal_sent and not awaiting_advance:
                self._control_started = True
                self.channel.send(dict(event="terminal", namespace="job", identity=identity,
                                       task=self._status(record)))
                self.terminal_sent = True
            if select.select([self.channel.sock], [], [], 0)[0]:
                self._control_started = True
                command = self._receive()
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
                    # Cancellation can commit while the administrator's bind,
                    # start or close packet is in flight. Reply with the real stopped
                    # state without applying that packet or launching a stage.
                    q.require(type(command) is dict and set(command) == {"action", "value"}
                              and command["action"] in ("snapshot", "bind", "start", "close")
                              and self.handler is not None, "SESSION_STOPPED")
                    self.channel.send(dict(self.handler.snapshot(), task=self._status(record)))
            return
        if self.handler is None:
            if not self.closures:
                self._prepare("preflight")
                return
            if not select.select([self.channel.sock], [], [], 0)[0]:
                return
            self._control_started = True
            command = self._receive()
            index = len(self.closures)
            if index == len(PHASES):
                q.require(command == {"action": "finish", "value": None}, "SESSION_FINISH")
                self.finished = True
                return
            self._prepare(self._advance(command))
            return
        if self._pending_close is not None or select.select([self.channel.sock], [], [], 0)[0]:
            self._control_started = True
            if self._pending_close is not None:
                command = self._pending_close
                self._action = "close"
            else:
                command = self._receive()
                self._close_retry_logged = False
            q.require(type(command) is dict and (command.get("action") != "start" or not self.started),
                      "SESSION_START_REPLAY")
            if command.get("action") == "close":
                self._pending_close = command
            reply = self.handler.handle(command)
            self.channel.send(dict(reply, task=self._status(b.state.get("job", identity)["record"])))
            self._pending_close = None
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
