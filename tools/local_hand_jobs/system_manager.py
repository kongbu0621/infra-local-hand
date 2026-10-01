"""Ordinary-side transport for the explicitly admitted Q2 system manager.

Stage admission, durable intents, pipes and transitions remain in Runner. This
adapter sends only finite logical references to the original administrator;
it cannot send argv, unit properties, paths, credentials or bus requests.
"""
from __future__ import annotations

import os
import socket
import subprocess
import threading

from . import budget, manager_binding, quota_contract as q, quota_lifecycle
from . import system_manager_protocol as wire
from .contract import JobError
from .runner import _SystemdExecutionCore, RunnerError, _unknown


def channel_from_pin(pin):
    """Consume the one inherited FD and its protected original-controller pin."""
    q._keys(pin, {"fd", "pid", "uid", "gid", "start_ticks", "session", "boot_id", "deadline_ns"})
    q.integer(pin["fd"], 3)
    q.integer(pin["pid"], 1)
    q.integer(pin["start_ticks"], 1)
    q.require(type(pin["uid"]) is int and type(pin["gid"]) is int and
              (pin["uid"], pin["gid"]) == (0, 0) and pin["pid"] != os.getpid(),
              "SYSTEM_ADMINISTRATOR")
    q.require(wire.start_ticks(pin["pid"]) == pin["start_ticks"], "SYSTEM_PEER_CHANGED")
    sock = socket.socket(fileno=pin["fd"])
    channel = None
    try:
        # PASSCRED must already be active before the peer can enqueue a packet.
        q.require(sock.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) == 1,
                  "SYSTEM_CREDENTIALS_NOT_ENABLED")
        channel = wire.Channel(sock, peer=(pin["pid"], 0, 0), peer_start_ticks=pin["start_ticks"],
            session_id=pin["session"], boot_id=pin["boot_id"], deadline_ns=pin["deadline_ns"])
        q.require(wire.start_ticks(pin["pid"]) == pin["start_ticks"], "SYSTEM_PEER_CHANGED")
        return channel
    except BaseException:
        if channel is not None:
            channel.close()
        else:
            sock.close()
        raise


class _RemoteClient:
    """Original root waiting client with actual, separate read-only pipe FDs.

poll() consumes no RPC: each bounded unit observation refreshes this state.
No ordinary signal targets a root PID. kill() requests only this pinned token.
"""
    def __init__(self, manager, part, state, fds):
        self.manager, self.part = manager, part
        self.state = None
        self.stdout = self.stderr = None
        remaining = list(fds)
        try:
            self.update(state)
            q.require(len(fds) == 2 and wire.readonly_pipe(fds[0]) != wire.readonly_pipe(fds[1]),
                      "SYSTEM_PIPE_ALIAS")
            self.stdout = os.fdopen(fds[0], "rb", buffering=0)
            remaining.remove(fds[0])
            self.stderr = os.fdopen(fds[1], "rb", buffering=0)
            remaining.remove(fds[1])
        except BaseException:
            for stream in (self.stdout, self.stderr):
                if stream is not None:
                    stream.close()
            for fd in remaining:
                try: os.close(fd)
                except OSError: pass
            raise

    def update(self, value):
        q._keys(value, {"token", "pid", "start_ticks", "returncode"})
        q.match(value["token"], r"[0-9a-f]{64}")
        q.integer(value["pid"], 1); q.integer(value["start_ticks"], 1)
        code = value["returncode"]
        q.require(code is None or type(code) is int and -255 <= code <= 255, "SYSTEM_CLIENT_STATUS")
        if self.state is not None:
            q.require(all(value[key] == self.state[key] for key in ("token", "pid", "start_ticks")) and
                      (self.state["returncode"] is None or code == self.state["returncode"]),
                      "SYSTEM_CLIENT_CHANGED")
        self.state = dict(value)
        self.returncode = code
        self.pid = value["pid"]  # Evidence only; never passed to an ordinary signal call.

    def poll(self):
        return self.returncode

    def kill(self):
        self.manager._client_operation("client_stop", self.part, self)


class SystemManager(_SystemdExecutionCore):
    """Private system transport, selectable only by protected Q2 composition."""
    def __init__(self, configuration, *, channel):
        super().__init__(configuration)
        q.require(self.execution_binding() is not None, "SYSTEM_BINDING_REQUIRED")
        self.channel = channel
        self._channel_lock = threading.Lock()
        self._failed = False

    def observation_interval(self):
        # Three original 24-second phases must share 256 finite RPCs. Half a
        # second leaves room for all nine launches, original stop checks and
        # seals. This changes polling only, never the original OS deadlines.
        return 0.5

    def close(self):
        # Closing this channel grants no stop, release, cleanup or restart.
        with self._channel_lock:
            self._failed = True
            self.channel.close()

    def _request(self, op, **body):
        with self._channel_lock:
            if self._failed:
                raise RunnerError("IO_UNCERTAIN", "Original system manager channel is unavailable")
            fds = ()
            try:
                metadata, fds = self.channel.request(op, **body)
                q.require(type(metadata) is dict, "SYSTEM_RESPONSE")
                if op == "support":
                    q._keys(metadata, {"supported", "status", "reasons", "manager_binding"})
                    q.require(type(metadata["supported"]) is bool and type(metadata["status"]) is str and
                              type(metadata["reasons"]) is list and
                              all(type(item) is str for item in metadata["reasons"]), "SYSTEM_SUPPORT")
                    manager_binding.check(self.execution_binding(), metadata["manager_binding"])
                elif op in ("inventory", "observe", "stop"):
                    q._keys(metadata, {"returncode", "stdout", "stderr"} |
                            ({"client_state"} if op != "inventory" else set()))
                    q.require(type(metadata["returncode"]) is int and
                              type(metadata["stdout"]) is str and type(metadata["stderr"]) is str,
                              "SYSTEM_COMMAND_STATUS")
                else:
                    q._keys(metadata, {"client_state"} | ({"closed"} if op == "seal" else set()))
                    if op == "seal":
                        q.require(metadata["closed"] is True, "SYSTEM_SEAL_UNPROVEN")
                q.require(len(fds) == (2 if op == "launch" else 0), "SYSTEM_FD_COUNT")
                return metadata, fds
            except BaseException as error:
                self._failed = True
                for fd in fds:
                    try: os.close(fd)
                    except OSError: pass
                self.channel.close()
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise
                raise RunnerError("IO_UNCERTAIN", "Original system manager response is unresolved") from error

    def support(self):
        binding = self.execution_binding()
        clock = budget.current_clock()
        reasons = []
        if ((os.geteuid(), os.getegid()) != (self.configuration["uid"], self.configuration["gid"])
                or os.geteuid() == 0):
            reasons.append("dedicated ordinary account is required")
        try:
            manager_binding.validate(binding, boot_id=clock["boot_id"])
            quota_lifecycle.parent(self.configuration["cgroup"], binding["parent"])
        except (OSError, ValueError, JobError):
            reasons.append("original ordinary parent identity is unresolved")
        if reasons:
            return dict(supported=False, status="UNSUPPORTED", reasons=reasons)
        value, _ = self._request("support")
        return {key: value[key] for key in ("supported", "status", "reasons")}

    def _admit(self, plan):
        self._check_manager_binding(plan)
        if plan.get("supervision_version") != 3 or plan.get("quota_observation_grant") is None:
            raise RunnerError("UNSUPPORTED", "System manager requires original quota supervision version 3")
        return super()._admit(plan)

    @staticmethod
    def _ref(part):
        return wire.reference(dict(execution_id=part["execution_id"],
            phase=part["identity"]["phase"], stage=part["stage"]))

    def _check_stage_binding(self, part):
        self._check_manager_binding(part, part["identity"])
        try:
            binding = manager_binding.validate(self.execution_binding(), boot_id=part["boot_id"],
                parent=part.get("quota_parent", self.execution_binding()["parent"]))
            q.require(part["cgroup_parent"] == "/sys/fs/cgroup" + binding["parent"]["path"],
                      "SYSTEM_STAGE_PARENT_CHANGED")
        except (ValueError, JobError) as error:
            raise RunnerError("IO_UNCERTAIN", "Original system stage binding is unresolved") from error

    def _part(self, unit):
        parts = [handle.get(stage) for handle in self._runs.values() for stage in wire.STAGES]
        parts = [part for part in parts if part is not None and part["unit"] == unit]
        if len(parts) != 1:
            raise RunnerError("IO_UNCERTAIN", "Original system stage identity is unresolved")
        part = parts[0]
        self._check_stage_binding(part)
        return part

    def _refresh(self, part, state):
        client = part.get("launch")
        if client is None:
            q.require(state is None, "SYSTEM_CLIENT_UNREGISTERED")
        else:
            client.update(state)

    def _command(self, *arguments, timeout=3):
        """Translate only the shared core's fixed queries, never arbitrary argv."""
        if arguments == ("list-units", "lhj-*.service", "--all", "--plain", "--no-legend"):
            value, _ = self._request("inventory")
        else:
            q.require(len(arguments) >= 2, "SYSTEM_FIXED_COMMAND")
            unit = arguments[-1] if arguments[:2] == ("stop", "--no-block") else arguments[1]
            part = self._part(unit)
            ref = self._ref(part)
            if arguments in (("stop", unit), ("stop", "--no-block", unit)):
                q.match(part.get("invocation_id"), r"[0-9a-f]{32}")
                value, _ = self._request("stop", ref=ref, invocation_id=part["invocation_id"])
            else:
                views = {( "show", unit, "--property=InvocationID", "--value"): "invocation",
                    ("show", unit, "--property=InvocationID,ControlGroup"): "identity",
                    ("show", unit, "--all", "--property=" + ",".join(quota_lifecycle.FIELDS)): "full"}
                q.require(arguments in views, "SYSTEM_FIXED_COMMAND")
                value, _ = self._request("observe", ref=ref, view=views[arguments])
            try:
                self._refresh(part, value["client_state"])
            except (ValueError, JobError) as error:
                self.close()
                raise RunnerError("IO_UNCERTAIN", "Original system client identity is unresolved") from error
        return subprocess.CompletedProcess(arguments, value["returncode"],
            value["stdout"].encode("utf-8"), value["stderr"].encode("utf-8"))

    def _launch_stage(self, handle, part, command, environment):
        self._check_manager_binding(handle, part)
        self._check_stage_binding(part)
        execution = handle["execution"]
        if handle["version"] != 3 or "quota_grant_digest" not in execution:
            raise RunnerError("UNSUPPORTED", "System manager requires the original quota grant")
        value, fds = self._request("launch", ref=self._ref(part), bindings={
            "allocation_digest": execution["bootstrap_allocation"]["grant_digest"],
            "grant_digest": execution["quota_grant_digest"]})
        try:
            return _RemoteClient(self, part, value["client_state"], fds)
        except (OSError, ValueError, JobError) as error:
            self.close()
            raise RunnerError("IO_UNCERTAIN", "Original system launch pipes are unresolved") from error

    def _client_operation(self, operation, part, client):
        self._check_stage_binding(part)
        value, _ = self._request(operation, ref=self._ref(part), token=client.state["token"])
        try:
            client.update(value["client_state"])
        except (ValueError, JobError) as error:
            self.close()
            raise RunnerError("IO_UNCERTAIN", "Original system client identity is unresolved") from error

    def _inspect_unit(self, part):
        self._check_stage_binding(part)
        if part.get("recovered"):
            return _unknown("original system pipes were lost; no stage replay is authorized")
        proof = super()._inspect_unit(part)
        if proof.get("state") != "EXITED" or part.get("cancel_before_launch"):
            return proof
        if not part.get("system_sealed"):
            client = part.get("launch")
            if (client is None or not part.get("pipe_closed") or
                    not client.stdout.closed or not client.stderr.closed or
                    part.get("system_seal_attempted")):
                return _unknown("original system client closure is unresolved")
            # A missing seal acknowledgement never authorizes the next stage,
            # even when the shared observer has already cached its local proof.
            part["system_seal_attempted"] = True
            self._client_operation("seal", part, client)
            part["system_sealed"] = True
        return proof
