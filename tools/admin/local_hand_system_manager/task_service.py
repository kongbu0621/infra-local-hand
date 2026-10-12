"""Launch a real Broker/MCP service using an existing bounded task installation.

This administrator entry reuses Gateway, quota assembly and Coordinator. It
does not provision accounts, mounts, quotas or ledgers, and never submits the
client's job. Its private declaration selects one already admitted request.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import stat
import subprocess
import threading

from local_hand_jobs import budget, quota_bridge, quota_closure, quota_contract as q, quota_payload, runner
from local_hand_jobs.broker import phase_plan
from local_hand_jobs.contract import Principal, validate_submit
from local_hand_jobs.deployment import verify_release
from local_hand_jobs.policy import Policy, thaw
from local_hand_jobs.registry import Registry
from local_hand_jobs.system_manager_protocol import Channel, start_ticks
from local_hand_jobs.task_session import SCHEMA
from admin.local_hand_quota_observer import q2_chain, q2_config, q2_management
from admin.local_hand_quota_observer.q2_coordinator import Coordinator
from admin.local_hand_quota_observer.protected_inputs import read_protected
from .server import Gateway

PHASES = quota_bridge.JOB_PHASES


def save(directory, name, value, mode=0o600):
    raw = q._canonical(value, 2 * 1024**2) + b"\n"
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 mode, dir_fd=directory)
    try:
        os.fchmod(fd, mode)
        pending = memoryview(raw)
        while pending:
            count = os.write(fd, pending)
            q.require(count > 0, "TASK_RECORD_WRITE")
            pending = pending[count:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(directory)


def service_command(value, descriptor):
    config = value["policy"]["process_manager"]
    q.require(value["transport"] in ("broker", "mcp"), "TASK_TRANSPORT")
    command = [value["setpriv"]["path"], "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all",
        "--no-new-privs", "--reuid=" + str(config["uid"]), "--regid=" + str(config["gid"]),
        "--clear-groups", "--", value["python"]["path"], "-I", "-B"]
    if value["transport"] == "broker":
        q.require(value["mcp"] is None, "TASK_TRANSPORT")
        command += ["-c", "import sys; sys.path.insert(0, sys.argv.pop(1)); "
                    "from local_hand_jobs.cli import broker_main; raise SystemExit(broker_main())",
                    str(Path(value["policy"]["execution_entrypoint"]).parent.parent),
                    "--policy", value["policy_path"]]
    else:
        q._keys(value["mcp"], {"auth_config", "port"})
        q.canonical_path(value["mcp"]["auth_config"])
        q.integer(value["mcp"]["port"], 1, 65535)
        command += ["-c", "import sys; sys.path.insert(0, sys.argv.pop(1)); "
                    "from local_hand_mcp.server import main; raise SystemExit(main())",
                    str(Path(value["policy"]["execution_entrypoint"]).parent.parent),
                    "--config", value["policy_path"],
                    "--auth-config", value["mcp"]["auth_config"], "--port", str(value["mcp"]["port"])]
    return command + ["--session", descriptor]


def checked_plan(base, prepared, grant, previous, binding):
    """Derive executable authority from the fixed plan, never incoming argv."""
    phase = prepared["phase"]
    q.require(phase in PHASES and list(previous) == list(PHASES[:PHASES.index(phase)]), "TASK_PHASE_ORDER")
    plan = quota_payload.decode_phase_plan(prepared["phase_plan"])
    prep = prepared["snapshot"]["preparation"]
    facts = plan.get("preflight_facts")
    q.require(type(facts) is dict and (phase != "preflight" or facts == {}), "TASK_PREFLIGHT_FACTS")
    row = dict(namespace="job", id=prepared["identity"], plan=base, record={"facts": facts})
    store = None
    if phase == "evidence":
        q.require(facts == previous["business"]["preflight_facts"], "TASK_PREFLIGHT_FACTS")
        frozen = plan.get("evidence_snapshot")
        q.require(type(frozen) is dict and frozen.get("operation_id") == row["id"]
                  and frozen.get("reconcile_id") is None and frozen.get("previous_seal_id") is None,
                  "TASK_EVIDENCE_IDENTITY")
        business = previous["business"]
        q.require(frozen.get("root") == business["bootstrap_allocation"]["roots"]["evidence"],
                  "TASK_EVIDENCE_ROOT")
        quiet = frozen.get("quiescence", {})
        q.require(quiet.get("execution_id") == business["execution_id"]
                  and quiet.get("event_seq") == frozen.get("event_seq") and all(quiet.get(key) is True for key in
                  ("future_starts_blocked", "tree_exited", "collectors_stopped", "writers_stopped")),
                  "TASK_EVIDENCE_QUIESCENCE")
        store = plan.get("evidence_store_root")
        q.require(prep["allocation"]["retained_paths"] == [store], "TASK_EVIDENCE_STORE")
        row["record"]["frozen_snapshot"] = frozen
    expected = phase_plan(row, phase, prep["budget"], allocation=prep["allocation"],
                          evidence_store_root=store, manager_binding=binding)
    q.require(plan == expected and grant.as_dict()["budget"] == prep["budget"]
              and grant.as_dict()["allocation"] == prep["allocation"], "TASK_PHASE_PLAN")
    return dict(expected, quota_observation_grant=grant.as_dict())


class TaskStopped(Exception):
    def __init__(self, snapshot):
        self.snapshot = snapshot


class PhaseClient(quota_bridge.Client):
    def call(self, action, value=None):
        result = super().call(action, value)
        q._keys(result, {"preparation", "observation", "pending", "closed", "task"})
        task = result.pop("task")
        q._keys(task, {"lifecycle", "phase", "outcome", "cancel_requested"})
        if task["lifecycle"] == "TERMINAL" and task["cancel_requested"] is True:
            raise TaskStopped(dict(result, task=task))
        return result


class TaskService:
    """One controller owns task channels while the public service owns its API."""
    def __init__(self, value):
        q.require(os.getuid() == os.geteuid() == 0, "TASK_ADMINISTRATOR")
        q._keys(value, {"schema", "policy", "policy_path", "request", "principal_id", "chain",
                       "controller_envelope", "setpriv", "python", "declarations", "intents",
                       "transport", "mcp"})
        q.require(value["schema"] == "local-hand-task-service/v1", "TASK_SERVICE_SCHEMA")
        self.value = value
        self.policy = Policy(value["policy"])
        q.canonical_path(value["policy_path"])
        self.request = validate_submit(value["request"])
        principal = Principal(value["principal_id"], frozenset(self.policy.principals[value["principal_id"]]["scopes"]))
        self.policy.authorize(principal, "lh:submit", request=self.request)
        self.plan = thaw(Registry().resolve(self.request, self.policy, principal=principal))
        raw = q._canonical(value["chain"], q2_config.LIMIT)
        self.chain = q2_chain.decode(raw, hashlib.sha256(raw).hexdigest())
        q2_chain.check_policy(self.chain, self.policy, self.request["profile_ref"])
        entry = Path(runner.__file__).with_name("cli.py") if value["transport"] == "broker" else Path(
            runner.__file__).parent.parent / "local_hand_mcp/server.py"
        verify_release(expected_source_commit=self.policy.source_commit,
            expected_payload_digest=self.policy.installed_payload_digest,
            expected_entrypoint=self.policy.execution_entrypoint, actual_entrypoint=entry)
        for pin in (value["setpriv"], value["python"]):
            os.close(q2_config.executable(pin))
        self.process = self.gateway = self.channel = self.manager_channel = self.worker = None
        self.declarations = self.intents = -1
        self.failures = []
        self.sockets = []
        self.capture_workers = []
        self.captures = []
        self.capture_stop = threading.Event()
        self.socket_pin = None
        self.closed = False

    def _spawn(self, command, fds):
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0, close_fds=True, pass_fds=fds,
            cwd="/", env={"PATH": "/usr/bin:/bin"})
        self.process = process
        captured = dict(pid=process.pid, returncode=None, eof=[], stdout=bytearray(), stderr=bytearray(),
                        total_bytes=0, truncated=False)
        self.captures.append(captured)
        def drain():
            streams = {name: getattr(process, name) for name in ("stdout", "stderr")}
            try:
                for stream in streams.values():
                    os.set_blocking(stream.fileno(), False)
                while not self.capture_stop.is_set():
                    ready = select.select([stream for name, stream in streams.items()
                        if name not in captured["eof"]], [], [], 0.05)[0]
                    for name, stream in streams.items():
                        if stream not in ready:
                            continue
                        raw = os.read(stream.fileno(), 4096)
                        if not raw:
                            captured["eof"].append(name)
                            continue
                        room = max(0, 32768 - sum(len(captured[key]) for key in streams))
                        captured[name].extend(raw[:room])
                        captured["total_bytes"] += len(raw)
                        captured["truncated"] |= len(raw) > room
                    captured["returncode"] = process.poll()
                    if len(captured["eof"]) == 2 and captured["returncode"] is not None:
                        break
            except OSError as error:
                captured["error"] = type(error).__name__
            finally:
                for stream in streams.values():
                    stream.close()
        thread = threading.Thread(target=drain, name="local-hand-service-output", daemon=True)
        self.capture_workers.append(thread)
        thread.start()
        return process

    def _serve_manager(self):
        def serve():
            try:
                self.gateway.serve()
            except Exception as error:
                self.failures.append(type(error).__name__)
        self.worker = threading.Thread(target=serve, name="local-hand-task-manager", daemon=True)
        self.worker.start()

    def _remember_socket(self):
        path = Path(self.policy.broker_root) / "maintenance.sock"
        try:
            info = path.lstat()
        except FileNotFoundError:
            return
        q.require(stat.S_ISSOCK(info.st_mode) and info.st_uid == self.policy.config["process_manager"]["uid"],
                  "TASK_SOCKET_IDENTITY")
        pin = (info.st_dev, info.st_ino, info.st_uid)
        q.require(self.socket_pin is None or self.socket_pin == pin, "TASK_SOCKET_CHANGED")
        self.socket_pin = pin

    def start(self):
        q.require(self.process is None, "TASK_SERVICE_STARTED")
        value, policy = self.value, self.policy
        manager = thaw(policy.config["process_manager"])
        binding = manager["manager_binding"]
        clock = budget.current_clock()
        envelope = value["controller_envelope"]
        end = envelope["deadline_ns"]
        q.require(binding["boot_id"] == clock["boot_id"] and
                  0 < end - clock["boottime_ns"] <= 600 * budget.NANOSECONDS, "TASK_SERVICE_DEADLINE")
        self.declarations = q2_config.pinned_directory(value["declarations"])
        self.intents = q2_config.pinned_directory(value["intents"])
        for fd, mode in ((self.declarations, 0o755), (self.intents, 0o700)):
            info = os.fstat(fd)
            q.require(info.st_uid == 0 and info.st_mode & 0o777 == mode, "TASK_DIRECTORY_MODE")
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        manager_left, manager_right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.sockets = [left, right, manager_left, manager_right]
        for sock in self.sockets:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        nonce = os.urandom(32).hex()
        manager_nonce = hashlib.sha256((nonce + ":manager").encode()).hexdigest()
        pin = dict(fd=right.fileno(), pid=os.getpid(), uid=0, gid=0, start_ticks=start_ticks(os.getpid()),
                   session=nonce, boot_id=clock["boot_id"], deadline_ns=end)
        namespace = os.stat("/proc/self/ns/user")
        declaration = dict(schema=SCHEMA, mode="execute", policy_digest=policy.policy_digest,
            operation_id=self.request["operation_id"], request_digest=self.request["request_digest"],
            principal_id=value["principal_id"], manager_binding=binding,
            initial_userns=dict(device=namespace.st_dev, inode=namespace.st_ino),
            broker_cgroup=envelope["controller"]["cgroup"], bridge=pin,
            manager_channel=dict(pin, fd=manager_right.fileno(), session=manager_nonce))
        filename = "session-" + nonce + ".json"
        save(self.declarations, filename, declaration, 0o644)
        command = service_command(value, value["declarations"]["path"] + "/" + filename)
        template = q2_chain.phase_template(self.chain, "preflight").data()
        q.require(template["peer"]["executable"]["path"] == value["python"]["path"]
                  and template["peer"]["runner"]["path"] == str(Path(runner.__file__).absolute()),
                  "TASK_INSTALLED_PROGRAM")
        self.declaration = declaration
        self.process = self._spawn(command, (right.fileno(), manager_right.fileno()))
        right.close(); manager_right.close()
        peer = (self.process.pid, manager["uid"], manager["gid"])
        self.manager_channel = Channel(manager_left, peer=peer, peer_start_ticks=start_ticks(self.process.pid),
            session_id=manager_nonce, boot_id=clock["boot_id"], deadline_ns=end)
        info = os.fstat(self.intents)
        self.gateway = Gateway(self.manager_channel, manager_binding=binding,
            ordinary_uid=manager["uid"], ordinary_gid=manager["gid"], python_path=value["python"]["path"],
            runner_path=template["peer"]["runner"]["path"],
            programs={name: template["installation"]["programs"][name] for name in ("systemctl", "systemd_run")},
            parent_mount_namespace=os.readlink("/proc/self/ns/mnt"), intent_directory=value["intents"]["path"],
            intent_pin=dict(device=info.st_dev, inode=info.st_ino), deadline_ns=end)
        self.channel = quota_bridge.Channel(left, peer=peer, session=nonce,
            boot_id=clock["boot_id"], deadline_ns=end, version=2)
        self._serve_manager()

    def run(self):
        """Wait for actual client admission; drive only the resulting task."""
        configs, previous = [], {}
        for index, phase in enumerate(PHASES):
            while not select.select([self.channel.sock], [], [], 0.05)[0]:
                self._remember_socket()
                self.channel._time()
            prepared = self.channel.receive()
            self._remember_socket()
            if prepared.get("event") == "terminal":
                q.require(prepared.get("identity") == self.request["operation_id"], "TASK_IDENTITY")
                self.channel.send(dict(action="finish", value=None))
                return dict(status="STOPPED", task=prepared["task"])
            q._keys(prepared, {"event", "namespace", "identity", "phase", "snapshot", "phase_plan"})
            q.require(prepared["event"] == "prepared" and prepared["namespace"] == "job"
                      and prepared["identity"] == self.request["operation_id"] and prepared["phase"] == phase,
                      "TASK_IDENTITY")
            session = prepared["snapshot"]["preparation"]["session"]
            grant = q2_chain.build_grant(self.chain, prepared["snapshot"], previousconfigs=configs,
                                        session=session, clock=budget.current_clock())
            plan = checked_plan(self.plan, prepared, grant, previous,
                                thaw(self.policy.config["process_manager"]["manager_binding"]))
            execution = runner._quota_prepared_execution(plan, parent_mount_namespace=os.readlink("/proc/self/ns/mnt"),
                                                         now_ns=budget.current_clock()["boottime_ns"])
            argv = runner.quota_bootstrap_argv(execution, grant, now_ns=budget.current_clock()["boottime_ns"])
            installed = q2_chain.install(self.chain, grant, bootstrap_argv=argv, previousconfigs=configs,
                                         session=session, clock=budget.current_clock())
            config = installed["config"]
            q2_management.controller(config, self.value["controller_envelope"])
            self.gateway.authorize_phase(plan, execution, grant, config)
            record = q2_management.RunRecord(installed["management_record"])
            coordinator = Coordinator(config, self.value["controller_envelope"], record, PhaseClient(self.channel))
            try:
                try:
                    result = coordinator.run()
                except TaskStopped as stopped:
                    # Ordinary cancellation closes no fabricated full-stage
                    # quota fence. Management still has its real exit duties.
                    management = None
                    if coordinator.management.used:
                        while coordinator.management.poll() is None:
                            coordinator._pump()
                            threading.Event().wait(0.05)
                        management = coordinator.management.finish()
                    result = dict(status="STOPPED", task=stopped.snapshot["task"], management=management)
                    save(self.intents, "stopped-" + phase + ".json", result)
                    self.channel.send(dict(action="finish", value=None))
                    return result
                save(self.intents, "phase-" + phase + ".json", result)
            finally:
                record.close()
            self.gateway.close_phase(result["fence"])
            configs.append(config)
            previous[phase] = plan
            if index + 1 < len(PHASES):
                following = PHASES[index + 1]
                self.channel.send(dict(action="advance", value={"from": phase, "to": following,
                    "closure_digest": quota_closure.digest(dict(phase=phase, fence=result["fence"]))}))
                self.channel.advance_phase(following)
        self.channel.send(dict(action="finish", value=None))
        return dict(status="CHAIN_CLOSED", operation_id=self.request["operation_id"])

    def recover(self):
        """Replace a proved-dead API process with the same task's read/stop session."""
        q.require(self.process.poll() is not None and self.gateway is not None,
                  "TASK_ORIGINAL_PROCESS_LIVE")
        self.worker.join(timeout=1)
        q.require(not self.worker.is_alive() and self.gateway.peer_pidfd >= 0 and
                  select.select([self.gateway.peer_pidfd], [], [], 0)[0], "TASK_ORIGINAL_EXIT_UNPROVEN")
        if self.socket_pin is not None:
            # Keep the old endpoint inode as crash evidence. Never unlink or
            # rename a replacement endpoint created by another service.
            root = os.open(self.policy.broker_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                info = os.stat("maintenance.sock", dir_fd=root, follow_symlinks=False)
                q.require(stat.S_ISSOCK(info.st_mode) and
                          (info.st_dev, info.st_ino, info.st_uid) == self.socket_pin, "TASK_SOCKET_CHANGED")
                os.rename("maintenance.sock", "maintenance-stopped-" + os.urandom(16).hex() + ".sock",
                          src_dir_fd=root, dst_dir_fd=root)
                os.fsync(root)
            finally:
                os.close(root)
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.sockets.extend((left, right))
        for sock in (left, right):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        nonce = os.urandom(32).hex()
        declaration = dict(self.declaration, mode="recover", bridge=None,
            manager_channel=dict(self.declaration["manager_channel"], fd=right.fileno(), session=nonce))
        filename = "recovery-" + nonce + ".json"
        save(self.declarations, filename, declaration, 0o644)
        command = service_command(self.value, self.value["declarations"]["path"] + "/" + filename)
        self.process = self._spawn(command, (right.fileno(),))
        right.close()
        manager = self.policy.config["process_manager"]
        self.manager_channel = Channel(left, peer=(self.process.pid, manager["uid"], manager["gid"]),
            peer_start_ticks=start_ticks(self.process.pid), session_id=nonce,
            boot_id=declaration["manager_channel"]["boot_id"], deadline_ns=declaration["manager_channel"]["deadline_ns"])
        self.gateway.rebind_service_recovery(self.manager_channel)
        self.socket_pin = None
        self._serve_manager()
        while not self.gateway.recovery_finished:
            q.require(self.process.poll() is None and self.worker.is_alive(), "TASK_RECOVERY_INCOMPLETE")
            self._remember_socket()
            self.manager_channel._time()
            threading.Event().wait(0.05)
        return dict(status="RECOVERY_RECORDED", operation_id=self.request["operation_id"], start_replayed=False)

    def retain_failure(self, error):
        """Keep the triggering error before a recovery attempt can replace it."""
        value = dict(error_type=type(error).__name__, reason=str(error)[:4096],
            returncode=self.process.poll(), manager_failures=list(self.failures),
            manager=None if self.gateway is None else self.gateway.snapshot())
        save(self.intents, "failure-" + os.urandom(16).hex() + ".json", value)

    def close(self):
        # No implicit replay, signal to a saved PID, or deletion of user files.
        if self.closed:
            return
        self.closed = True
        failure = None
        def attempt(action):
            nonlocal failure
            try:
                action()
            except BaseException as error:
                if failure is None:
                    failure = error
        self.capture_stop.set()
        for thread in self.capture_workers:
            attempt(lambda thread=thread: thread.join(timeout=1))
        if self.intents >= 0:
            if self.gateway is not None:
                attempt(lambda: save(self.intents, "manager-final.json", self.gateway.snapshot()))
            for index, captured in enumerate(self.captures):
                value = dict(captured)
                for name in ("stdout", "stderr"):
                    value[name + "_hex"] = bytes(value.pop(name)).hex()
                attempt(lambda index=index, value=value: save(self.intents,
                    "service-output-" + str(value["pid"]) + "-" + str(index) + ".json", value))
        for resource in (self.channel, self.gateway, self.manager_channel, *self.sockets):
            if resource is not None:
                attempt(resource.close)
        if self.worker is not None:
            attempt(lambda: self.worker.join(timeout=1))
        for name in ("declarations", "intents"):
            fd = getattr(self, name)
            if fd >= 0:
                attempt(lambda fd=fd: os.close(fd))
                setattr(self, name, -1)
        if failure is not None:
            raise failure


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start an admitted task's Broker/MCP service")
    parser.add_argument("--launch", required=True)
    args = parser.parse_args(argv)
    service = None
    failed = False
    try:
        value = q._load(read_protected(args.launch, 2 * 1024**2), 2 * 1024**2, 32)
        service = TaskService(value)
        service.start()
        try:
            result = service.run()
        except Exception as error:
            service.retain_failure(error)
            if service.process.poll() is None:
                raise
            result = service.recover()
        print(json.dumps(result, sort_keys=True), flush=True)
        # Keep the API available for result/evidence reads for the remainder
        # of this controller's original bounded window.
        end = value["controller_envelope"]["deadline_ns"]
        while service.process.poll() is None and budget.current_clock()["boottime_ns"] < end:
            threading.Event().wait(0.05)
        return 0
    except BaseException:
        failed = True
        raise
    finally:
        if service is not None:
            try:
                service.close()
            except BaseException:
                if not failed:
                    raise


if __name__ == "__main__":
    raise SystemExit(main())
