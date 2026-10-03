"""Root controller's original, finite system-manager delivery authority.

Only root in-process configuration can register a phase. The inherited channel
accepts references, never commands, paths, properties, process IDs or grants.
All intents remain after failure.  The test-only H11 launcher may replace a
definitively exited ordinary peer with one observation-only recovery session;
that session can only inspect/stop retained identities and cannot reacquire the
old anonymous pipes, launch, seal or target a saved client PID.
"""
from __future__ import annotations

import array
import copy
import fcntl
import hashlib
import os
from pathlib import PurePosixPath
import re
import select
import shlex
import signal
import stat
import subprocess
import termios
import threading
import time

from local_hand_jobs import (bootstrap, budget, manager_binding as mb, quota_contract as q,
                             quota_grant as g, quota_lifecycle as life, result_reader, runner)
from local_hand_jobs import system_manager_protocol as wire
from admin.local_hand_quota_observer import q2_config, q2_runtime
from admin.local_hand_quota_observer.q2_journal import Journal
from admin.local_hand_quota_observer.protected_inputs import open_protected
from admin.local_hand_quota_observer.systemd_runtime import Capture, ENVIRONMENT
from admin.local_hand_quota_observer.controller_guard import _timespan_usec

_EXTRA_FIELDS = ("Slice", "User", "Group", "NoNewPrivileges", "CapabilityBoundingSet",
    "AmbientCapabilities", "PrivateUsers", "PrivateNetwork", "PrivateMounts", "PrivateDevices",
    "ProtectSystem", "ProtectHome", "ProtectControlGroups", "ProtectKernelTunables", "ProtectKernelModules",
    "RestrictSUIDSGID", "RestrictNamespaces", "LockPersonality", "MemoryMax", "MemorySwapMax", "TasksMax",
    "LimitCPU", "LimitFSIZE", "CPUQuotaPerSecUSec", "CPUQuotaPeriodUSec", "RuntimeMaxUSec", "TimeoutStopUSec",
    "InaccessiblePaths", "ReadOnlyPaths", "ReadWritePaths", "SendSIGKILL")
_ALL_FIELDS = (*life.FIELDS, *_EXTRA_FIELDS)


def _unit(execution_id, stage):
    suffix = "" if stage == "helper" else ":" + stage
    return "lhj-" + hashlib.sha256((execution_id + suffix).encode()).hexdigest() + ".service"


def _properties(raw):
    rows = [line.split("=", 1) for line in raw.decode("utf-8", "strict").splitlines()]
    q.require(all(len(row) == 2 for row in rows) and len({r[0] for r in rows}) == len(rows), "SYSTEM_PROPERTIES")
    return dict(rows)


def _usec(text):
    return _timespan_usec(text)


def _quota_usec(text):
    match = re.fullmatch(r"([0-9]{1,3})(?:\.([0-9]{1,2}))?%", text)
    q.require(match is not None, "SYSTEM_CPU_QUOTA")
    value = int(match[1]) * 10000 + int((match[2] or "").ljust(2, "0")) * 100
    q.require(0 < value <= 1000000, "SYSTEM_CPU_QUOTA")
    return value


class _ControlCapture(Capture):
    """Count every received byte, including the first overflow byte."""
    def __init__(self, limit):
        super().__init__(limit)
        self.received = 0

    def pump(self):
        if self.error is not None:
            return
        q.require(self.process is not None and self.configured, "SYSTEM_CONTROL_PIPE_SETUP")
        for name in ("stdout", "stderr"):
            if name in self.eof:
                continue
            try:
                raw = os.read(getattr(self.process, name).fileno(), min(4096, self.limit - self.received + 1))
            except BlockingIOError:
                continue
            except OSError:
                self.error = "SYSTEM_CONTROL_PIPE_READ"
                return
            self.received += len(raw)
            if not raw:
                self.eof.add(name)
            else:
                room = self.limit - len(self.stdout) - len(self.stderr)
                getattr(self, name).extend(raw[:room])
                if self.received > self.limit:
                    self.error = "SYSTEM_CONTROL_BYTE_LIMIT"
                    return


def _drained(fd):
    """Observe EOF without reading a byte also destined for the resident."""
    wire.readonly_pipe(fd)
    poller = select.poll(); poller.register(fd, select.POLLIN | select.POLLHUP | select.POLLERR)
    events = poller.poll(0)
    pending = array.array("i", [0])
    fcntl.ioctl(fd, termios.FIONREAD, pending, True)
    return bool(events and events[0][1] & select.POLLHUP and not events[0][1] & select.POLLERR
                and pending[0] == 0)


class Gateway:
    def __init__(self, channel, *, manager_binding, ordinary_uid, ordinary_gid, python_path,
                 runner_path, programs, parent_mount_namespace, intent_directory, intent_pin, deadline_ns):
        q.require(os.getuid() == os.geteuid() == 0, "SYSTEM_GATEWAY_ROOT")
        self.binding = mb.validate(manager_binding)
        self.uid = q.integer(ordinary_uid, 1, 2**32 - 2)
        self.gid = q.integer(ordinary_gid, 1, 2**32 - 2)
        q.require(channel.peer[1:] == (self.uid, self.gid) and channel.boot_id == self.binding["boot_id"],
                  "SYSTEM_GATEWAY_PEER")
        self.channel = channel
        self.peer_pidfd = -1
        self.end = q.integer(deadline_ns, 1)
        q.require(self.end <= channel.end, "SYSTEM_GATEWAY_DEADLINE")
        self.python_path = q.canonical_path(python_path)
        self.runner_path = q.canonical_path(runner_path)
        self.namespace = q.match(parent_mount_namespace, r"mnt:\[[0-9]+\]")
        q._keys(programs, {"systemctl", "systemd_run"})
        self.programs = copy.deepcopy(programs)
        for item in self.programs.values():
            q._keys(item, {"path", "sha256"})
            os.close(q2_config.executable(item))
        self.configuration = dict(uid=self.uid, gid=self.gid, manager_binding=self.binding,
            slice=PurePosixPath(self.binding["parent"]["path"]).name,
            cgroup="/sys/fs/cgroup" + self.binding["parent"]["path"])
        self.core = runner._SystemdExecutionCore(self.configuration)
        self.phases = {}; self.parts = {}; self.closed_phases = []
        self.lock = threading.RLock()
        self.failure = None; self.closed = False; self.controls = 0; self.control_bytes = 0
        self.retired_wire_bytes = 0; self.retired_calls = 0
        self.session_failures = []
        self.recovery_only = False; self.recovery_finished = False
        self.recovery_rebinds = 0; self.recovery_armed = False; self.recovery_arm_ack = False
        self.recovery_plan = None
        self._serving = False
        self.pending_control = None
        self.directory = -1
        q._keys(intent_pin, {"device", "inode"})
        self.directory = open_protected(intent_directory, directory=True)
        try:
            info = os.fstat(self.directory)
            q.require((info.st_dev, info.st_ino) == (intent_pin["device"], intent_pin["inode"])
                      and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o700, "SYSTEM_INTENT_DIRECTORY")
            with os.scandir(self.directory) as entries:
                for count, entry in enumerate(entries, 1):
                    q.require(count <= 64 and not entry.name.startswith("gateway-"), "SYSTEM_INTENT_REPLAY")
            self._time(); self._parent()
            self.peer_pidfd = os.dup(channel.pidfd)
        except BaseException:
            if self.peer_pidfd >= 0:
                os.close(self.peer_pidfd); self.peer_pidfd = -1
            os.close(self.directory); self.directory = -1
            raise

    def _time(self):
        now = budget.current_clock()
        q.require(not self.closed and self.failure is None and now["boot_id"] == self.binding["boot_id"]
                  and now["boottime_ns"] < self.end, "SYSTEM_GATEWAY_UNAVAILABLE")
        q.require(self.control_bytes + self.retired_wire_bytes + self.channel.total <= wire.WIRE_LIMIT,
                  "SYSTEM_AGGREGATE_OUTPUT_LIMIT")
        # Channel.receive_request() enforces the strict pre-request bound.  Once
        # the final permitted response commits, bookkeeping/phase closure must
        # still be able to observe the exact cumulative limit without admitting
        # a 257th call.
        q.require(self.retired_calls + self.channel.sequence <= wire.CALL_LIMIT,
                  "SYSTEM_CALL_LIMIT")
        self.channel._time()
        return now["boottime_ns"]

    def _recovery_time(self):
        """Recovery never receives a fresh observation/stop window."""
        now = self._time()
        q.require(type(self.recovery_plan) is dict
                  and now < min(self.recovery_plan["phase_deadline_ns"],
                                self.recovery_plan["budget_deadline_ns"], self.end),
                  "SYSTEM_RECOVERY_DEADLINE")
        return now

    def _discard_original_clients(self):
        """Permanently abandon local pipe/PID ownership before H11 reattach."""
        for part in self.parts.values():
            pipes = part.get("pipe_identities")
            q.require(type(pipes) is dict and set(pipes) == {"stdout", "stderr"}
                      and all(type(pipes[name]) is dict
                              and set(pipes[name]) == {"device", "inode"}
                              and type(pipes[name]["device"]) is int
                              and type(pipes[name]["inode"]) is int
                              and pipes[name]["device"] >= 0
                              and pipes[name]["inode"] > 0
                              for name in pipes)
                      and (pipes["stdout"]["device"], pipes["stdout"]["inode"])
                          != (pipes["stderr"]["device"], pipes["stderr"]["inode"]),
                      "SYSTEM_RECOVERY_PIPE_IDENTITY")
            process = part.get("process")
            if process is not None:
                for name in ("stdout", "stderr"):
                    stream = getattr(process, name, None)
                    if stream is not None:
                        try:
                            stream.close()
                        except OSError:
                            pass
                # poll() is evidence only.  Recovery never signals or waits on
                # this PID and never treats its exit as unit/tree proof.
                part["abandoned_client"] = dict(pid=process.pid,
                    start_ticks=part.get("start_ticks"), returncode=process.poll(),
                    pipe_identities=copy.deepcopy(pipes))
                part["process"] = None
            else:
                # Component tests may model an already-reaped local client;
                # the immutable pipe identities remain mandatory evidence.
                part.setdefault("abandoned_client", dict(pid=None,
                    start_ticks=part.get("start_ticks"), returncode=None,
                    pipe_identities=copy.deepcopy(pipes)))
            if part.get("pidfd", -1) >= 0:
                os.close(part["pidfd"]); part["pidfd"] = -1
            part["collectors_lost"] = True

    def rebind_recovery(self, channel):
        """Bind one new ordinary peer without refreshing identity or budget.

        The original server loop must already have ended and its exact peer
        must be dead.  A pending request cannot be carried across sessions.
        Calls and bytes remain cumulative across both channels.
        """
        with self.lock:
            old = self.channel
            now = budget.current_clock()
            q.require(not self.closed and not self._serving and not self.recovery_only
                      and self.recovery_rebinds == 0 and self.pending_control is None
                      and self.recovery_armed is True and self.recovery_arm_ack is True
                      and self.recovery_plan is not None,
                      "SYSTEM_RECOVERY_STATE")
            q.require(old.pending is None and self.peer_pidfd >= 0
                      and bool(select.select([self.peer_pidfd], [], [], 0)[0]),
                      "SYSTEM_RECOVERY_OLD_PEER")
            q.require(channel.peer[0] != old.peer[0]
                      and channel.peer[1:] == (self.uid, self.gid)
                      and channel.boot_id == self.binding["boot_id"] == now["boot_id"]
                      and channel.end == self.end and now["boottime_ns"] < self.end
                      and channel.sequence == channel.total == 0 and channel.pending is None
                      and channel.session_id == hashlib.sha256(
                          (old.session_id + ":h11-recovery").encode("ascii")).hexdigest(),
                      "SYSTEM_RECOVERY_PEER")
            q.require(now["boottime_ns"] < min(self.recovery_plan["phase_deadline_ns"],
                                               self.recovery_plan["budget_deadline_ns"]),
                      "SYSTEM_RECOVERY_DEADLINE")
            q.require(self.failure in (None, "SYSTEM_PEER_CHANGED", "SYSTEM_CHANNEL_DISCONNECTED")
                      and self.parts and len(self.parts) == 3
                      and {stage for _, stage in self.parts} == set(wire.STAGES)
                      and len({phase for phase, _ in self.parts}) == 1,
                      "SYSTEM_RECOVERY_SCOPE")
            self.retired_wire_bytes += old.total
            self.retired_calls += old.sequence
            q.require(self.control_bytes + self.retired_wire_bytes <= wire.WIRE_LIMIT
                      and self.retired_calls < wire.CALL_LIMIT,
                      "SYSTEM_RECOVERY_BUDGET")
            if self.failure is not None:
                self.session_failures.append(self.failure)
            old.close()
            os.close(self.peer_pidfd)
            self.peer_pidfd = os.dup(channel.pidfd)
            self._discard_original_clients()
            self.channel = channel
            self.failure = None
            self.recovery_only = True
            self.recovery_rebinds = 1
            self.recovery_finished = False

    def _parent(self, *, empty=False):
        pin, is_empty = life.parent(self.configuration["cgroup"], self.binding["parent"])
        q.require(not empty or is_empty, "SYSTEM_PARENT_OCCUPIED")
        return pin

    def authorize_phase(self, plan, execution, grant, config):
        """Trusted launcher call after independent plan/grant/config validation."""
        with self.lock:
            now = self._time()
            phase = grant.request.as_dict()["phase"]
            q.require(len(self.phases) < 3 and phase == wire.PHASES[len(self.phases)]
                      and self.closed_phases == list(self.phases), "SYSTEM_PHASE_ORDER")
            mb.check(self.binding, plan.get("manager_binding"))
            original = runner._quota_prepared_execution(plan,
                parent_mount_namespace=self.namespace, now_ns=now)
            q.require(original == execution and original["python"] == self.python_path,
                      "SYSTEM_EXECUTION_BINDING")
            q.require(config.active().wire == grant.wire and
                      config.data()["programs"]["python"]["path"] == self.python_path,
                      "SYSTEM_GRANT_BINDING")
            peer = config.data()["peers"][grant.request.as_dict()["request_id"]]
            argv = runner.quota_bootstrap_argv(original, grant, script=self.runner_path, now_ns=now)
            command_digest = hashlib.sha256(b"\0".join(os.fsencode(arg) for arg in argv) + b"\0").hexdigest()
            q.require(peer["executable"]["path"] == self.python_path and
                      peer["command_sha256"] == command_digest and peer["parent"] == self.binding["parent"],
                      "SYSTEM_PHASE_PARENT")
            for item in grant.as_dict()["roots"]:
                q.require((item["uid"], item["gid"]) == (self.uid, self.gid), "SYSTEM_ORDINARY_IDENTITY")
            self._parent(empty=True)
            self.phases[phase] = dict(execution=copy.deepcopy(original), grant=g.decode_grant(grant.wire),
                                      config=config, plan=copy.deepcopy(plan))

    def _journal(self, phase):
        item = self.phases[phase]; config = item["config"]; raw = config.data()
        journal = Journal(raw["journal"]["path"], raw["journal"]["pin"], raw["capacity"],
                          list(config.grants().values()))
        try:
            with journal.locked():
                return journal.scan()[item["grant"].request.as_dict()["request_id"]]
        finally:
            journal.close()

    def close_phase(self, fence):
        with self.lock:
            self._time()
            q.require(len(self.closed_phases) < len(self.phases), "SYSTEM_PHASE_ORDER")
            phase = wire.PHASES[len(self.closed_phases)]
            q.require(self.pending_control is None and all((phase, stage) in self.parts and self.parts[phase, stage]["sealed"]
                          for stage in wire.STAGES), "SYSTEM_PHASE_UNSEALED")
            state = self._journal(phase)
            q.require(state["status"] == "CLOSED" and state["closed"] == fence, "SYSTEM_PHASE_FENCE")
            self._parent(empty=True)
            self.closed_phases.append(phase)

    def _command(self, *arguments):
        """Fixed callers only; 32KiB dual streams, original root deadline."""
        self._time(); self.controls += 1
        q.require(self.pending_control is None, "SYSTEM_CONTROL_PENDING")
        q.require(self.controls <= 256, "SYSTEM_CONTROL_LIMIT")
        cap = _ControlCapture(16384)
        self.pending_control = cap
        cap.start((self.programs["systemctl"]["path"], "--system", "--no-ask-password", *arguments))
        cap.original_start_ticks = wire.start_ticks(cap.process.pid)
        end = min(self.end, self._time() + 2_000_000_000)
        try:
            while not cap.settled:
                cap.pump()
                q.require(self.control_bytes + cap.received + self.channel.total <= wire.WIRE_LIMIT,
                          "SYSTEM_AGGREGATE_OUTPUT_LIMIT")
                q.require(cap.error is None and self._time() < end, "SYSTEM_CONTROL_INCOMPLETE")
                time.sleep(0.002)
            q.require(cap.done, "SYSTEM_CONTROL_INCOMPLETE")
            result = dict(returncode=cap.process.returncode, stdout=bytes(cap.stdout).decode("utf-8", "strict"),
                          stderr=bytes(cap.stderr).decode("utf-8", "strict"))
            self.pending_control = None
            return result
        finally:
            self.control_bytes += cap.received
            # Do not kill a client to manufacture a successful observation.
            # An uncertain client remains inside the original target envelope.
            cap.close_pipes()

    def _get(self, ref, *, delivered=True):
        wire.reference(ref)
        q.require(ref["phase"] in self.phases, "SYSTEM_PHASE_UNREGISTERED")
        item = self.phases[ref["phase"]]
        q.require(item["execution"]["execution_id"] == ref["execution_id"], "SYSTEM_EXECUTION_REFERENCE")
        part = self.parts.get((ref["phase"], ref["stage"]))
        q.require(not delivered or part is not None, "SYSTEM_STAGE_UNDELIVERED")
        return item, part

    def _state(self, part):
        process = part["process"]
        code = process.poll()
        if code is None:
            q.require(wire.start_ticks(process.pid) == part["start_ticks"], "SYSTEM_CLIENT_CHANGED")
        return dict(token=part["token"], pid=process.pid, start_ticks=part["start_ticks"], returncode=code)

    def _show(self, part):
        result = self._command("show", part["unit"], "--all", "--property=" + ",".join(_ALL_FIELDS))
        q.require(result["returncode"] == 0, "SYSTEM_SHOW_FAILED")
        values = _properties(result["stdout"].encode())
        for key in ("ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost", "ExecReload"):
            values.setdefault(key, "")
        q._keys(values, set(_ALL_FIELDS))
        q.require(values["Id"] == part["unit"], "SYSTEM_UNIT_CHANGED")
        if values["LoadState"] == "loaded":
            identity = life._loaded_identity(part, {key: values[key] for key in life.FIELDS})
            part["invocation_id"] = identity["invocation_id"]
            part.setdefault("identity_observation", values)
            q.require(values["ControlGroup"] == identity["cgroup"] or life._terminal(values),
                      "SYSTEM_ACTIVE_PARENT_MISSING")
            properties = part["properties"]
            exact = {key: properties[key] for key in ("Slice", "User", "Group", "NoNewPrivileges",
                "CapabilityBoundingSet", "AmbientCapabilities", "PrivateUsers", "PrivateNetwork", "PrivateMounts",
                "PrivateDevices", "ProtectSystem", "ProtectHome", "ProtectControlGroups", "ProtectKernelTunables",
                "ProtectKernelModules", "RestrictSUIDSGID", "LockPersonality", "MemoryMax", "MemorySwapMax", "TasksMax",
                "LimitCPU", "LimitFSIZE", "SendSIGKILL")}
            q.require(all(values[key] == value for key, value in exact.items()) and
                      values["RestrictNamespaces"] == "yes",
                      "SYSTEM_UNIT_PROPERTIES")
            # Our admitted paths contain no whitespace, backslash or systemd
            # specifier. Compare the complete native lists; reordering does
            # not change their meaning, extra/missing/optional paths do.
            q.require(all(sorted(shlex.split(values[key], posix=True)) == sorted(properties[key].split())
                          for key in ("InaccessiblePaths", "ReadOnlyPaths", "ReadWritePaths")),
                      "SYSTEM_UNIT_PATHS")
            expected_rate = _quota_usec(properties["CPUQuota"])
            q.require(_usec(values["CPUQuotaPerSecUSec"]) == expected_rate
                      and _usec(values["CPUQuotaPeriodUSec"]) == 1000
                      and _usec(values["RuntimeMaxUSec"]) == int(properties["RuntimeMaxSec"][:-2])
                      and _usec(values["TimeoutStopUSec"]) == int(properties["TimeoutStopSec"]) * 1000000,
                      "SYSTEM_UNIT_LIMITS")
            if life._terminal(values):
                part.setdefault("terminal", values)
        else:
            q.require(values["LoadState"] == "not-found" and values["InvocationID"] == ""
                      and values["ControlGroup"] == "" and values["ActiveState"] == "inactive"
                      and values["SubState"] == "dead" and values["Job"] in ("", "0"), "SYSTEM_UNIT_MISSING")
            # Before a delayed first delivery, absence remains pending only.
            q.require(part["invocation_id"] is None or part["stop_ok"] and
                      ("terminal" in part or self.recovery_only and
                       type(part.get("identity_observation")) is dict),
                      "SYSTEM_ORIGINAL_UNIT_MISSING")
        part["after"] = values
        return result, values

    def _intent(self, phase, stage, value):
        name = "gateway-" + phase + "-" + stage + ".intent.json"
        raw = q._canonical(value, 8191) + b"\n"
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=self.directory)
        try:
            pending = memoryview(raw)
            while pending:
                written = os.write(fd, pending)
                q.require(written > 0, "SYSTEM_INTENT_WRITE")
                pending = pending[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(self.directory)

    def _predecessor(self, phase, stage):
        state = self._journal(phase)
        if stage == "bootstrap":
            q.require(state["status"] == "READY", "SYSTEM_QUOTA_ALREADY_CONSUMED")
            config = self.phases[phase]["config"]
            for role in ("listener", "admission"):
                result = self._command("show", q2_runtime.name(config, role), "--all",
                    "--property=Id,LoadState,ActiveState,SubState,InvocationID,ControlGroup,Job")
                values = _properties(result["stdout"].encode())
                expected_unit = q2_runtime.name(config, role)
                q.require(result["returncode"] == 0 and values.get("Id") == expected_unit
                          and values.get("LoadState") == "loaded" and values.get("ActiveState") == "active"
                          and values.get("SubState") == "running" and values.get("Job") in ("", "0")
                          and values.get("ControlGroup") == q2_runtime.parent(config, role)["path"] + "/" + expected_unit,
                          "SYSTEM_MANAGEMENT_NOT_READY")
                q.match(values.get("InvocationID"), r"[0-9a-f]{32}")
            return
        previous = self.parts.get((phase, wire.STAGES[wire.STAGES.index(stage) - 1]))
        q.require(previous is not None and previous["sealed"], "SYSTEM_PREDECESSOR_UNSEALED")
        q.require(state["status"] == "RESULT" and state["result"]["receipt"]["status"] == "OBSERVED",
                  "SYSTEM_QUOTA_RESULT_UNPROVEN")
        bootstrap_part = self.parts[phase, "bootstrap"]
        peer = state["intent"]["peer"]
        q.require(peer["unit"] == bootstrap_part["unit"] and
                  peer["invocation_id"] == bootstrap_part["invocation_id"] and
                  peer["parent"] == self.binding["parent"] and
                  peer["cgroup"] == self.binding["parent"]["path"] + "/" + bootstrap_part["unit"],
                  "SYSTEM_BOOTSTRAP_RECEIPT_BINDING")
        q.require(bootstrap_part["terminal"]["ExecMainStatus"] == "0", "SYSTEM_BOOTSTRAP_FAILED")

    def _build(self, item, stage):
        execution = item["execution"]
        properties = self.core._properties(execution, stage)
        remaining = min(runner._runtime_microseconds(execution["budget_grant"]),
            runner._deadline_remaining((execution["budget_grant"], execution["phase_deadline_boottime_ns"])) // 1000)
        q.require(remaining > 0, "SYSTEM_PHASE_DEADLINE")
        properties.update(User=str(self.uid), Group=str(self.gid), AmbientCapabilities="", MemorySwapMax="0",
                          RuntimeMaxSec=str(remaining) + "us")
        unit = _unit(execution["execution_id"], stage)
        if stage == "bootstrap":
            payload = runner.quota_bootstrap_argv(execution, item["grant"], script=self.runner_path,
                                                  now_ns=self._time())
        elif stage == "helper":
            plan_path = str(PurePosixPath(execution["roots"]["evidence"]) / bootstrap.plan_name(execution["execution_id"]))
            payload = [self.python_path, "-I", self.runner_path, "--helper", plan_path]
        else:
            helper = self.parts[execution["phase"], "helper"]
            helper_identity = dict(unit=helper["unit"], boot_id=self.binding["boot_id"],
                invocation_id=helper["invocation_id"], cgroup=self.binding["parent"]["path"] + "/" + helper["unit"],
                exit_code=int(helper["terminal"]["ExecMainStatus"]))
            payload = {key: execution[key] for key in ("execution_id", "phase", "operation_id", "budget_grant", "budgets",
                "supervision_version", "bootstrap_allocation", "parent_mount_namespace", "phase_deadline_boottime_ns", "runtime_cap_us")}
            payload.update(reader_unit=unit, unit=unit, helper_identity=helper_identity,
                           result_name=result_reader.result_name(execution["execution_id"]))
            payload = [self.python_path, "-I", "-B", self.runner_path, "--result-reader", result_reader.encode_payload(payload)]
        argv = [self.programs["systemd_run"]["path"], "--system", "--quiet", "--pipe", "--no-ask-password",
                "--unit=" + unit, "--description=Local-Hand-supervised-" + stage]
        argv.extend("--property=" + key + "=" + value for key, value in properties.items()
                    if value or key in ("CapabilityBoundingSet", "AmbientCapabilities"))
        argv.extend(["--", *payload])
        bootstrap.check_argv(argv, ENVIRONMENT)
        return unit, properties, argv

    def _launch(self, body):
        ref = body["ref"]; phase, stage = ref["phase"], ref["stage"]
        item, previous = self._get(ref, delivered=False)
        q.require(previous is None and len(self.parts) < 9 and phase not in self.closed_phases,
                  "SYSTEM_DELIVERY_REPLAY")
        q.require(body["bindings"] == dict(allocation_digest=item["execution"]["bootstrap_allocation"]["grant_digest"],
                                           grant_digest=item["grant"].digest), "SYSTEM_LAUNCH_BINDING")
        self._predecessor(phase, stage); self._parent(empty=True)
        unit, properties, argv = self._build(item, stage)
        before = self._command("show", unit, "--property=Id,LoadState,Job")
        values = _properties(before["stdout"].encode())
        q.require(before["returncode"] == 0 and set(values) == {"Id", "LoadState", "Job"}
                  and values["Id"] == unit and values["LoadState"] == "not-found" and values["Job"] in ("", "0"),
                  "SYSTEM_UNIT_ALREADY_EXISTS")
        token = hashlib.sha256((self.channel.session_id + ":" + phase + ":" + stage).encode()).hexdigest()
        template = ["--property=RuntimeMaxSec=1us" if arg.startswith("--property=RuntimeMaxSec=") else arg
                    for arg in argv]
        intent = dict(schema=wire.SCHEMA, ref=ref, token=token, manager_binding=self.binding,
            grant_digest=item["grant"].digest, allocation_digest=body["bindings"]["allocation_digest"],
            command_template_digest=hashlib.sha256(b"\0".join(os.fsencode(arg) for arg in template) + b"\0").hexdigest(),
            issued_ns=self._time(), deadline_ns=item["execution"]["phase_deadline_boottime_ns"])
        self._intent(phase, stage, intent)
        # Mark delivery consumed BEFORE Popen. A missing reply is never evidence
        # that the manager failed to accept the original command.
        part = self.parts[phase, stage] = dict(unit=unit, token=token, properties=properties,
            boot_id=self.binding["boot_id"], quota_parent=self.binding["parent"], invocation_id=None,
            sealed=False, stop_ok=False, process=None)
        # fsync and manager observation can consume time. Only the runtime
        # property is recomputed, from the SAME original absolute grant, after
        # the durable intent and immediately before the unique delivery.
        self._time()
        _, final_properties, final_argv = self._build(item, stage)
        final_template = ["--property=RuntimeMaxSec=1us" if arg.startswith("--property=RuntimeMaxSec=") else arg
                          for arg in final_argv]
        q.require(final_template == template, "SYSTEM_DELIVERY_PLAN_CHANGED")
        part["properties"] = final_properties
        part["command_digest"] = hashlib.sha256(b"\0".join(os.fsencode(arg) for arg in final_argv) + b"\0").hexdigest()
        part["process"] = subprocess.Popen(final_argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, env=ENVIRONMENT)
        part["start_ticks"] = wire.start_ticks(part["process"].pid)
        part["pidfd"] = os.pidfd_open(part["process"].pid, 0)
        streams = {name: getattr(part["process"], name).fileno()
                   for name in ("stdout", "stderr")}
        identities = {name: wire.readonly_pipe(fd) for name, fd in streams.items()}
        q.require(len(set(identities.values())) == 2, "SYSTEM_PIPE_ALIAS")
        part["pipe_identities"] = {name: {"device": identity[0], "inode": identity[1]}
                                   for name, identity in identities.items()}
        fds = tuple(streams[name] for name in ("stdout", "stderr"))
        for fd in fds:
            os.set_blocking(fd, False)
        return dict(client_state=self._state(part)), fds

    def _seal(self, part):
        q.require(not part["sealed"], "SYSTEM_SEAL_REPLAY")
        _, after = self._show(part)
        terminal = part.get("terminal")
        q.require(part["stop_ok"] and terminal is not None and part["invocation_id"] is not None
                  and after["ActiveState"] in ("inactive", "failed") and after["Job"] in ("", "0")
                  and terminal["ExecMainCode"] == "1" and terminal["ExecMainStatus"].isdigit(),
                  "SYSTEM_STAGE_EXIT_UNPROVEN")
        self._parent(empty=True)
        q.require(part["process"].poll() == int(terminal["ExecMainStatus"])
                  and all(_drained(getattr(part["process"], name).fileno()) for name in ("stdout", "stderr")),
                  "SYSTEM_CLIENT_EOF_UNPROVEN")
        for name in ("stdout", "stderr"):
            getattr(part["process"], name).close()
        os.close(part["pidfd"]); part["pidfd"] = -1
        part["sealed"] = True

    def dispatch(self, op, body):
        with self.lock:
            self._time(); wire.request_body(op, body)
            q.require(not (self.recovery_armed and not self.recovery_only),
                      "SYSTEM_RECOVERY_ARMED")
            if self.recovery_only:
                q.require(op in ("support", "inventory", "observe", "stop", "recovery_finish"),
                          "SYSTEM_RECOVERY_OPERATION")
                self._recovery_time()
            if op == "support":
                self._parent()
                return dict(supported=True, status="CANDIDATE", reasons=[], manager_binding=self.binding), ()
            if op == "inventory":
                self._parent()
                result = self._command("list-units", "lhj-*.service", "--all", "--plain", "--no-legend")
                names = [line.split()[0] for line in result["stdout"].splitlines() if line.strip()]
                q.require(len(names) <= 9 and len(names) == len(set(names)), "SYSTEM_INVENTORY_LIMIT")
                known = {part["unit"]: part for part in self.parts.values()}
                q.require(set(names) <= known.keys(), "SYSTEM_INVENTORY_UNKNOWN")
                for unit in names:
                    self._show(known[unit])
                return result, ()
            if op == "launch":
                return self._launch(body)
            if op == "recovery_arm":
                plan = wire.recovery_plan(body["plan"])
                phase = plan["phase"]
                item = self.phases.get(phase)
                expected_parts = {(phase, stage) for stage in wire.STAGES}
                expected_units = {stage: self.parts[phase, stage]["unit"] for stage in wire.STAGES}
                q.require(not self.recovery_only and not self.recovery_armed
                          and self.pending_control is None and len(self.parts) == 3
                          and set(self.parts) == expected_parts and item is not None
                          and plan["units"] == expected_units
                          and item["execution"]["execution_id"] == plan["execution_id"]
                          and item["execution"]["operation_id"] == plan["operation_id"]
                          and item["plan"].get("request_digest") == plan["request_digest"]
                          and item["execution"]["budget_grant"]["deadline_boottime_ns"]
                              == plan["budget_deadline_ns"]
                          and budget.phase_deadline_ns(item["execution"]["budget_grant"])
                              == plan["phase_deadline_ns"]
                          and plan["controller_deadline_ns"] == self.end
                          and plan["collector_started"] is False
                          and self._time() < plan["phase_deadline_ns"]
                          and all(re.fullmatch(r"[0-9a-f]{32}", part.get("invocation_id") or "")
                              for part in self.parts.values())
                          and len({part["invocation_id"] for part in self.parts.values()}) == 3,
                          "SYSTEM_RECOVERY_ARM")
                self.recovery_plan = copy.deepcopy(plan)
                self.recovery_armed = True
                return dict(armed=True), ()
            if op == "recovery_finish":
                q.require(self.recovery_only and not self.recovery_finished and self.pending_control is None
                          and all(part.get("recovery_observed") is True
                              and part.get("collectors_lost") is True
                              and part.get("process") is None and part.get("pidfd") == -1
                              and part.get("stop_ok") is True
                              and type(part.get("identity_observation")) is dict
                              and part["identity_observation"].get("InvocationID") == part.get("invocation_id")
                              and part.get("after", {}).get("ActiveState") in ("inactive", "failed")
                              and part.get("after", {}).get("Job") in ("", "0")
                              for part in self.parts.values()),
                          "SYSTEM_RECOVERY_INCOMPLETE")
                self._parent(empty=True)
                self.recovery_finished = True
                return dict(closed=True), ()
            item, part = self._get(body["ref"])
            if "token" in body:
                q.require(body["token"] == part["token"], "SYSTEM_CLIENT_TOKEN")
            if op == "observe":
                result, values = self._show(part)
                if self.recovery_only:
                    part["recovery_observed"] = True
                    terminal = part.get("terminal")
                    result["recovery_history"] = dict(
                        invocation_id=part.get("invocation_id"),
                        stop_ok=part.get("stop_ok") is True,
                        sealed=part.get("sealed") is True,
                        identity=(None if part.get("identity_observation") is None else
                                  {key: part["identity_observation"][key] for key in life.FIELDS}),
                        terminal=(None if terminal is None else
                                  {key: terminal[key] for key in life.FIELDS}))
                if body["view"] == "invocation":
                    result["stdout"] = values["InvocationID"] + "\n"
                elif body["view"] == "identity":
                    result["stdout"] = "\n".join(k + "=" + values[k] for k in
                        ("Id", "LoadState", "ActiveState", "SubState", "InvocationID", "ControlGroup", "Job")) + "\n"
                else:
                    result["stdout"] = "\n".join(k + "=" + values[k] for k in life.FIELDS) + "\n"
                if not self.recovery_only:
                    result["client_state"] = self._state(part)
                return result, ()
            if op == "stop":
                _, values = self._show(part)
                q.require(values["LoadState"] == "loaded" and
                          values["InvocationID"] == body["invocation_id"] == part["invocation_id"],
                          "SYSTEM_STOP_IDENTITY")
                result = self._command("stop", part["unit"])
                part["stop_ok"] = result["returncode"] == 0
                if not self.recovery_only:
                    result["client_state"] = self._state(part)
                return result, ()
            if op == "client_stop":
                if self._state(part)["returncode"] is None:
                    signal.pidfd_send_signal(part["pidfd"], signal.SIGKILL)
                # Killing this registered command cannot manufacture unit exit.
                return dict(client_state=self._state(part)), ()
            if op == "seal":
                q.require(self._time() < item["execution"]["phase_deadline_boottime_ns"], "SYSTEM_PHASE_DEADLINE")
                self._seal(part)
                return dict(closed=True, client_state=self._state(part)), ()
            return dict(client_state=self._state(part)), ()

    def serve(self):
        with self.lock:
            q.require(not self._serving and not self.closed, "SYSTEM_GATEWAY_SERVE")
            self._serving = True
        try:
            # A successful arm ACK is the exact crash injection barrier.  Stop
            # consuming the old peer before any later observer RPC can move the
            # retained identity; the launcher will next kill that exact peer.
            while (not self.closed and not self.recovery_finished
                   and not (self.recovery_armed and not self.recovery_only)):
                if not select.select([self.channel.sock], [], [], 0.025)[0]:
                    self._time(); continue
                request = self.channel.receive_request()
                try:
                    result, fds = self.dispatch(request["op"], request["body"])
                except Exception:
                    self._respond(request, dict(error="SYSTEM_GATEWAY_REJECTED"))
                    raise
                if self.recovery_only:
                    self._recovery_time()
                self._respond(request, result, fds=fds)
        except Exception as error:
            if not self.closed:
                code = str(error)
                self.failure = code if len(code) <= 96 and code.replace("_", "").isalnum() else type(error).__name__
            self.channel.close()
        finally:
            with self.lock:
                self._serving = False

    def _respond(self, request, result, fds=()):
        raw = q._canonical(dict(schema=wire.SCHEMA, session_id=self.channel.session_id,
            sequence=self.channel.sequence, op=request["op"], body=result), wire.RESPONSE_LIMIT)
        q.require(self.control_bytes + self.retired_wire_bytes + self.channel.total
                  + len(raw) + 12 + 4 * len(fds) <= wire.WIRE_LIMIT,
                  "SYSTEM_AGGREGATE_OUTPUT_LIMIT")
        self.channel.respond(request, result, fds=fds)
        if request["op"] == "recovery_arm":
            q.require(self.recovery_armed and self.channel.pending is None,
                      "SYSTEM_RECOVERY_ARM_ACK")
            self.recovery_arm_ack = True

    def snapshot(self):
        """Finite original identities only; never raw request/argv/environment."""
        with self.lock:
            parts = []
            for (phase, stage), part in self.parts.items():
                process = part.get("process")
                parts.append(dict(phase=phase, stage=stage, unit=part["unit"], token=part["token"],
                    pid=None if process is None else process.pid, start_ticks=part.get("start_ticks"),
                    returncode=None if process is None else process.poll(), invocation_id=part["invocation_id"],
                    stop_ack=part["stop_ok"], sealed=part["sealed"], command_digest=part.get("command_digest"),
                    runtime_max=part["properties"]["RuntimeMaxSec"],
                    pipe_identities=copy.deepcopy(part.get("pipe_identities")),
                    abandoned_client=copy.deepcopy(part.get("abandoned_client")),
                    collectors_lost=part.get("collectors_lost") is True,
                    recovery_observed=part.get("recovery_observed") is True,
                    identity_observation=(None if part.get("identity_observation") is None else
                        {key: part["identity_observation"][key] for key in life.FIELDS}),
                    terminal=(None if part.get("terminal") is None else
                        {key: part["terminal"][key] for key in life.FIELDS}),
                    after=(None if part.get("after") is None else
                        {key: part["after"][key] for key in life.FIELDS})))
            value = dict(schema=wire.SCHEMA, manager_binding=self.binding, failure=self.failure,
                closed_phases=list(self.closed_phases), stages=parts, wire_bytes=self.channel.total,
                calls=self.retired_calls + self.channel.sequence,
                aggregate_wire_bytes=self.retired_wire_bytes + self.channel.total,
                recovery_only=self.recovery_only, recovery_finished=self.recovery_finished,
                recovery_rebinds=self.recovery_rebinds, recovery_armed=self.recovery_armed,
                recovery_arm_ack=self.recovery_arm_ack,
                recovery_plan_sha256=(None if self.recovery_plan is None else
                    hashlib.sha256(q._canonical(self.recovery_plan, wire.REQUEST_LIMIT)).hexdigest()),
                session_failures=list(self.session_failures),
                control_calls=self.controls, control_output_bytes=self.control_bytes)
            cap = self.pending_control
            value["pending_control"] = None if cap is None else dict(
                pid=None if cap.process is None else cap.process.pid,
                start_ticks=getattr(cap, "original_start_ticks", None),
                returncode=None if cap.process is None else cap.process.poll(), eof=sorted(cap.eof), error=cap.error)
            q._canonical(value, 32768)
            return value

    def close(self):
        """Close owned descriptors only; never stop/delete/relaunch a unit."""
        with self.lock:
            self.closed = True
            self.channel.close()
            if getattr(self, "peer_pidfd", -1) >= 0:
                os.close(self.peer_pidfd); self.peer_pidfd = -1
            if self.pending_control is not None:
                self.pending_control.close_pipes()
            for part in self.parts.values():
                process = part.get("process")
                if process is not None:
                    for name in ("stdout", "stderr"):
                        getattr(process, name).close()
                if part.get("pidfd", -1) >= 0:
                    os.close(part["pidfd"]); part["pidfd"] = -1
            if self.directory >= 0:
                os.close(self.directory); self.directory = -1
