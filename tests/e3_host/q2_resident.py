"""Explicit, finite test-only composition of the real resident broker.

An administrator supplies an existing isolated ledger, installed wheel and
credentialed inherited channel. No listener, account, ledger or quota is
provisioned here. Production entrypoints never import this module.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import socket
import stat
import sys

SCHEMA = "local-hand-q2-resident/v1"
CHAIN_SCHEMA = "local-hand-q2-resident/v2"
LIMIT = 262144
PHASES = ("preflight",)
CHAIN_PHASES = ("preflight", "business", "evidence")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def unique(items):
    value = {}
    for key, item in items:
        require(key not in value, "RESIDENT_DUPLICATE_KEY")
        value[key] = item
    return value


def fixture_phases(value):
    phases = PHASES if value.get("schema") == SCHEMA else CHAIN_PHASES if value.get("schema") == CHAIN_SCHEMA else ()
    require(bool(phases) and value.get("phases") == list(phases)
            and value.get("purpose") == ("ISOLATED_Q2_RESIDENT" if phases == PHASES else "ISOLATED_Q2_CHAIN"),
            "RESIDENT_SCHEMA")
    return phases


def protected(filename, maximum):
    """Read trusted bytes before importing any installed application module."""
    require(type(filename) is str and filename.startswith("/")
            and not filename.startswith("//") and str(Path(filename)) == filename
            and ".." not in Path(filename).parts, "RESIDENT_PATH")
    current = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        parts = Path(filename).parts[1:]
        require(bool(parts), "RESIDENT_PATH")
        for index, part in enumerate(parts):
            directory = index < len(parts) - 1
            child = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
                            | os.O_NONBLOCK | (os.O_DIRECTORY if directory else 0), dir_fd=current)
            previous, current = current, child
            os.close(previous)
            info = os.fstat(current)
            require((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
                    and info.st_uid == 0 and not info.st_mode & 0o022
                    and (directory or info.st_nlink == 1 and not info.st_mode & 0o6000),
                    "RESIDENT_PROTECTION")
        require(info.st_size <= maximum, "RESIDENT_FILE_LIMIT")
        raw = bytearray()
        while len(raw) <= maximum:
            chunk = os.read(current, min(65536, maximum + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        after = os.fstat(current)
        require(len(raw) <= maximum and all(getattr(info, name) == getattr(after, name) for name in
                ("st_dev", "st_ino", "st_uid", "st_gid", "st_mode", "st_nlink", "st_size",
                 "st_mtime_ns", "st_ctime_ns")), "RESIDENT_FILE_CHANGED")
        return bytes(raw)
    finally:
        os.close(current)


class Pinned(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Execute only the already verified source bytes, including package init."""
    def __init__(self, sources):
        self.sources = sources
        self.roots = {name.split(".")[0] for name in sources}

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in self.roots:
            return None
        require(fullname in self.sources, "RESIDENT_UNPINNED_MODULE")
        return importlib.util.spec_from_loader(fullname, self, is_package=self.sources[fullname][2])

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        raw, filename, package = self.sources[module.__name__]
        module.__file__ = filename
        if package:
            module.__path__ = []
        exec(compile(raw, filename, "exec", dont_inherit=True), module.__dict__)


def bootstrap(path, digest):
    require(sys.flags.isolated and sys.dont_write_bytecode, "RESIDENT_ISOLATED_PYTHON")
    raw = protected(path, LIMIT)
    require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest)
            and hashlib.sha256(raw).hexdigest() == digest, "RESIDENT_FIXTURE_DIGEST")
    value = json.loads(raw, object_pairs_hook=unique)
    require(type(value) is dict and set(value) == {
        "schema", "purpose", "entry", "installation", "policy", "ordinary", "principal",
        "request", "plan", "phases", "bridge"}, "RESIDENT_SCHEMA")
    fixture_phases(value)
    entry = value["entry"]
    require(type(entry) is dict and set(entry) == {"path", "sha256"}
            and entry["path"] == os.path.abspath(__file__)
            and hashlib.sha256(protected(entry["path"], 512 * 1024)).hexdigest() == entry["sha256"],
            "RESIDENT_ENTRY")
    installation = value["installation"]
    require(type(installation) is dict and set(installation) == {
        "package_root", "source_commit", "payload_digest", "files", "programs"}, "RESIDENT_INSTALLATION")
    sources = {}
    files = installation["files"]
    require(type(files) is dict and 1 <= len(files) <= 512, "RESIDENT_MODULE_COUNT")
    allowed = {"local_hand", "local_hand_jobs", "local_hand_mcp", "local_hand_connect"}
    for relative, checksum in files.items():
        require(type(relative) is str and re.fullmatch(r"[a-z_]+/[a-z_][a-z0-9_]*\.py", relative)
                and relative.split("/")[0] in allowed and type(checksum) is str
                and re.fullmatch(r"[0-9a-f]{64}", checksum), "RESIDENT_MODULE_PATH")
        filename = installation["package_root"] + "/" + relative
        source = protected(filename, 512 * 1024)
        require(hashlib.sha256(source).hexdigest() == checksum, "RESIDENT_MODULE_DIGEST")
        package = relative.endswith("/__init__.py")
        name = (relative[:-12] if package else relative[:-3]).replace("/", ".")
        sources[name] = source, filename, package
    require(all(name in sources for name in allowed), "RESIDENT_PACKAGE_MISSING")
    require(not any(name.split(".")[0] in allowed for name in sys.modules), "RESIDENT_PREIMPORTED")
    sys.meta_path.insert(0, Pinned(sources))
    return value


def process_start(pid):
    with open("/proc/" + str(pid) + "/stat", "rb") as stream:
        raw = stream.read(4097)
    require(len(raw) <= 4096, "RESIDENT_PROC_LIMIT")
    return int(raw[raw.rfind(b")") + 2:].split()[19])


def channel_from_pin(pin, *, version=1):
    from local_hand_jobs import quota_contract as q, quota_bridge
    q._keys(pin, {"fd", "pid", "uid", "gid", "start_ticks", "session", "boot_id", "deadline_ns"})
    q.integer(pin["fd"], 3)
    q.integer(pin["pid"], 1)
    q.integer(pin["start_ticks"], 1)
    require((pin["uid"], pin["gid"]) == (0, 0) and pin["pid"] != os.getpid(), "RESIDENT_ADMINISTRATOR")
    require(process_start(pin["pid"]) == pin["start_ticks"], "RESIDENT_ADMIN_REPLACED")
    sock = socket.socket(fileno=pin["fd"])
    channel = None
    try:
        channel = quota_bridge.Channel(sock, peer=(pin["pid"], 0, 0), session=pin["session"],
                                      boot_id=pin["boot_id"], deadline_ns=pin["deadline_ns"], version=version)
        require(process_start(pin["pid"]) == pin["start_ticks"], "RESIDENT_ADMIN_REPLACED")
        return channel
    except BaseException:
        if channel is not None:
            channel.close()
        else:
            sock.close()
        raise


def host_admission(value, policy, manager):
    """Actual existing account, initial namespace, delegation and parent pins."""
    from local_hand_jobs import budget, quota_contract as q, quota_lifecycle
    pin = value["ordinary"]
    q._keys(pin, {"uid", "gid", "parent", "broker_cgroup", "initial_userns"})
    q.integer(pin["uid"], 1)
    q.integer(pin["gid"], 1)
    require(os.getuid() == os.geteuid() == pin["uid"] and os.getgid() == os.getegid() == pin["gid"]
            and set(os.getgroups()) <= {pin["gid"]}, "RESIDENT_ACCOUNT")
    status = {}
    with open("/proc/self/status", "r") as stream:
        for line in stream:
            name, _, text = line.partition(":")
            if name in {"CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb", "NoNewPrivs"}:
                status[name] = text.strip()
    require(set(status) == {"CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb", "NoNewPrivs"}
            and status["NoNewPrivs"] == "1" and all(int(item, 16) == 0 for name, item in status.items()
                if name != "NoNewPrivs"), "RESIDENT_CAPABILITIES")
    q._keys(pin["initial_userns"], {"device", "inode"})
    namespace = os.stat("/proc/self/ns/user")
    require({"device": namespace.st_dev, "inode": namespace.st_ino} == pin["initial_userns"],
            "RESIDENT_USER_NAMESPACE")
    clock = budget.current_clock()
    require(clock["boot_id"] == value["bridge"]["boot_id"]
            and 0 < value["bridge"]["deadline_ns"] - clock["boottime_ns"] <= 600 * budget.NANOSECONDS,
            "RESIDENT_ORIGINAL_DEADLINE")
    support = manager.support()
    require(support["supported"] is True, "RESIDENT_HOST_UNSUPPORTED")
    parent = pin["parent"]
    q._keys(parent, {"path", "device", "inode"})
    q.integer(parent["device"], 1)
    q.integer(parent["inode"], 1)
    require(policy.config["process_manager"]["cgroup"] == "/sys/fs/cgroup" + parent["path"],
            "RESIDENT_MANAGER_PARENT")
    require(quota_lifecycle.parent(policy.config["process_manager"]["cgroup"], parent)[1], "RESIDENT_PARENT_OCCUPIED")
    own = Path("/proc/self/cgroup").read_text()
    require(own == "0::" + pin["broker_cgroup"] + "\n" and pin["broker_cgroup"] != parent["path"]
            and not pin["broker_cgroup"].startswith(parent["path"] + "/"), "RESIDENT_CONTROL_SEPARATION")
    delegation = manager._command("show", "--property=ControlGroup", "--", "-.slice")
    require(delegation.returncode == 0, "RESIDENT_MANAGER_OBSERVATION")
    facts = dict(line.split("=", 1) for line in delegation.stdout.decode("ascii").splitlines())
    require(set(facts) == {"ControlGroup"} and facts["ControlGroup"] != "/"
            and parent["path"].startswith(facts["ControlGroup"] + "/"), "RESIDENT_DELEGATION")
    for name in ("cgroup.controllers", "cgroup.subtree_control"):
        require({"cpu", "memory", "pids"} <= set(Path("/sys/fs/cgroup" + facts["ControlGroup"], name).read_text().split()),
                "RESIDENT_CONTROLLERS")


def compose(value):
    from local_hand_jobs import cli, deployment, policy as policy_module
    from local_hand_jobs.runner import _SystemdExecutionCore
    from local_hand_jobs import quota_contract as q
    from local_hand import provenance
    install = value["installation"]
    q.match(install["source_commit"], r"[0-9a-f]{40}")
    q.match(install["payload_digest"], r"[0-9a-f]{64}")
    q._keys(value["policy"], {"path", "digest"})
    # Policy.from_file independently requires the dedicated account's private
    # single-link configuration and stable protected ancestry.
    policy = policy_module.Policy.from_file(value["policy"]["path"])
    require(policy.policy_digest == value["policy"]["digest"], "RESIDENT_POLICY_DIGEST")
    require(policy.source_commit == install["source_commit"]
            and policy.installed_payload_digest == install["payload_digest"]
            and Path(cli.__file__).parent.parent == Path(install["package_root"]), "RESIDENT_RELEASE_BINDING")
    metadata = provenance.build_metadata()
    require(metadata is not None and metadata["artifact_kind"] == "wheel", "RESIDENT_INSTALLED_WHEEL_REQUIRED")
    deployment.verify_release(expected_source_commit=policy.source_commit,
        expected_payload_digest=policy.installed_payload_digest,
        expected_entrypoint=policy.execution_entrypoint, actual_entrypoint=cli.__file__)
    programs = install["programs"]
    q._keys(programs, {"python", "systemctl", "systemd_run"})
    for name, expected in (("python", os.path.realpath(sys.executable)),
                           ("systemctl", "/usr/bin/systemctl"), ("systemd_run", "/usr/bin/systemd-run")):
        pin = programs[name]
        q._keys(pin, {"path", "sha256"})
        require(pin["path"] == expected and hashlib.sha256(protected(expected, 64 * 1024 * 1024)).hexdigest()
                == pin["sha256"], "RESIDENT_PROGRAM_BINDING")
    require(all(os.path.realpath(profile["python"]) == programs["python"]["path"]
                for profile in policy.profiles.values()), "RESIDENT_INTERPRETER_BINDING")
    manager = _SystemdExecutionCore(policy.config.get("process_manager"))
    host_admission(value, policy, manager)
    broker = cli._compose_broker(policy, manager, quota_required=True)
    try:
        # Explicitly supplied existing empty ledger only. A former request or
        # retained reservation is evidence to stop, never a resume invitation.
        with broker.state.transaction() as tx:
            require(not broker.state.all(tx) and tx.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
                    and tx.execute("SELECT COUNT(*) FROM leases").fetchone()[0] == 0, "RESIDENT_LEDGER_ALREADY_USED")
        return broker
    except BaseException:
        cli.close_service(broker, None, failed=True)
        raise


def prepare_request(value, broker):
    from local_hand_jobs import contract, quota_contract as q
    q._keys(value["principal"], {"principal_id", "scopes"})
    pin = value["principal"]
    require(type(pin["principal_id"]) is str and re.fullmatch(r"q2-synthetic-[a-z0-9-]{1,64}", pin["principal_id"]),
            "RESIDENT_SYNTHETIC_PRINCIPAL")
    require(type(pin["scopes"]) is list and len(set(pin["scopes"])) == len(pin["scopes"])
            and set(pin["scopes"]) == {"lh:submit", "lh:read", "lh:evidence"}, "RESIDENT_SCOPES")
    request = contract.validate_submit(value["request"])
    require(request["kind"] == "host.inspect" and request["inputs"] == {}
            and fixture_phases(value), "RESIDENT_SYNTHETIC_REQUEST")
    principal = contract.Principal(pin["principal_id"], frozenset(pin["scopes"]))
    broker.submit(request, principal)
    require(broker.state.get("job", request["operation_id"])["plan"] == value["plan"], "RESIDENT_PLAN_BINDING")
    return request["operation_id"], principal


class Chain:
    """One original operation/session; phase advancement is never recovery."""
    def __init__(self, broker, identity, plan):
        self.broker, self.identity, self.plan = broker, identity, plan
        self.session = broker._quota_session
        self.preparations, self.closed = {}, {}

    def _row(self, tx):
        from local_hand_jobs import budget, quota_binding as binding
        b = self.broker
        row = b.state.get("job", self.identity, tx)
        require(row is not None and row["plan"] == self.plan and not row["record"].get("recovered")
                and not row["record"]["cancel_requested"] and b._quota_session == self.session
                and binding.admission_version(tx, row) == 1, "RESIDENT_ORIGINAL_CHAIN")
        for phase, prepared in self.preparations.items():
            require(binding.original(tx, row, phase, "QUOTA_PREPARATION", "quota_preparations") == prepared
                    and budget.stored_grant(row, phase) == prepared["budget"], "RESIDENT_PREPARATION_CHANGED")
        for phase, closed in self.closed.items():
            require(binding.original(tx, row, phase, "QUOTA_PHASE_CLOSED", "quota_closed") == closed,
                    "RESIDENT_CLOSURE_CHANGED")
        if "preflight" in self.closed:
            pending = binding.original(tx, row, "preflight", "QUOTA_EXIT_PENDING", "quota_pending")
            require(row["record"]["facts"] == pending["proof"].get("facts", {}), "RESIDENT_PREFLIGHT_FACTS_CHANGED")
        if self.preparations:
            budget.remaining_ns(self.preparations["preflight"]["budget"])
        return row

    def declaration(self, phase, snapshot):
        from local_hand_jobs import budget, quota_payload
        from local_hand_jobs.broker import phase_plan
        index = len(self.preparations)
        require(index < len(CHAIN_PHASES) and phase == CHAIN_PHASES[index]
                and list(self.closed) == list(CHAIN_PHASES[:index]), "RESIDENT_PHASE_ORDER")
        prepared = snapshot["preparation"]
        require(all(snapshot[name] is None for name in ("observation", "pending", "closed"))
                and prepared["session"] == self.session and prepared["phase"] == phase, "RESIDENT_PREPARATION")
        with self.broker.fence, self.broker.state.transaction() as tx:
            row = self._row(tx)
            require(set(row["record"].get("quota_preparations", {})) == set(CHAIN_PHASES[:index + 1])
                    and set(row["record"].get("quota_closed", {})) == set(CHAIN_PHASES[:index])
                    and phase not in row["record"]["handles"]
                    and budget.stored_grant(row, phase) == prepared["budget"], "RESIDENT_PHASE_HISTORY")
            if self.preparations:
                original = self.preparations["preflight"]
                require(prepared["generation"] == original["generation"] and all(prepared["budget"][key]
                        == original["budget"][key] for key in ("namespace", "record_id", "operation_id",
                        "budget_digest", "boot_id", "started_boottime_ns", "deadline_boottime_ns")),
                        "RESIDENT_OPERATION_BUDGET_CHANGED")
            if phase == "evidence":
                frozen = tx.execute("SELECT data_json FROM events WHERE namespace='job' AND id=? "
                                    "AND kind='SEAL_SNAPSHOT_FROZEN'", (self.identity,)).fetchall()
                require(len(frozen) == 1 and json.loads(frozen[0]["data_json"]).get("frozen_snapshot")
                        == row["record"].get("frozen_snapshot"), "RESIDENT_FROZEN_SNAPSHOT_CHANGED")
            plan = phase_plan(row, phase, prepared["budget"], allocation=prepared["allocation"],
                evidence_store_root=str(self.broker.evidence.root) if phase == "evidence" else None)
            # No argv or grant authority is accepted from the administrator's
            # advance packet. This declaration comes only from the original row.
            result = quota_payload.encode_phase_plan(plan)
        self.preparations[phase] = prepared
        return result

    def retain_closure(self, phase, closed):
        from local_hand_jobs import quota_binding as binding
        require(phase == CHAIN_PHASES[len(self.closed)] and phase in self.preparations,
                "RESIDENT_PHASE_ORDER")
        with self.broker.fence, self.broker.state.transaction() as tx:
            row = self._row(tx)
            require(binding.original(tx, row, phase, "QUOTA_PHASE_CLOSED", "quota_closed") == closed
                    and ("job", self.identity) not in self.broker._active, "RESIDENT_CLOSURE_UNPROVEN")
        self.closed[phase] = closed

    def advance(self, channel, previous, following):
        from local_hand_jobs import quota_closure
        require(previous in self.closed and len(self.closed) < len(CHAIN_PHASES)
                and following == CHAIN_PHASES[len(self.closed)], "RESIDENT_PHASE_ORDER")
        command = channel.receive()
        require(command == dict(action="advance", value={"from": previous, "to": following,
                "closure_digest": quota_closure.digest(self.closed[previous])}), "RESIDENT_ADVANCE")
        with self.broker.fence, self.broker.state.transaction() as tx:
            row = self._row(tx)
            require(row["record"]["phase"] == ("PREFLIGHT_COMPLETE" if following == "business" else "AWAITING_SEAL")
                    and set(row["record"].get("quota_preparations", {})) == set(self.closed)
                    and set(row["record"].get("quota_closed", {})) == set(self.closed)
                    and ("job", self.identity) not in self.broker._active, "RESIDENT_ADVANCE_UNPROVEN")
        channel.advance_phase(following)

    def complete(self):
        require(list(self.closed) == list(CHAIN_PHASES), "RESIDENT_CHAIN_INCOMPLETE")
        with self.broker.fence, self.broker.state.transaction() as tx:
            row = self._row(tx)
            require(row["record"]["phase"] == "EXITED" and row["record"]["evidence"] == "SEALED"
                    and bool(row["record"].get("seals")) and ("job", self.identity) not in self.broker._active,
                    "RESIDENT_SEAL_UNPROVEN")


def run_phase(broker, identity, phase, channel, *, chain=None):
    """Autonomous observation, same persistent startup fence and broker session."""
    from local_hand_jobs import quota_bridge
    handler = quota_bridge.Phase(broker, "job", identity, phase, version=2 if chain is not None else 1)
    # _start reserves the original budget and root allocation exactly once; it
    # cannot launch a manager before the authenticated root binds observation.
    broker._start("job", identity, phase)
    snapshot = handler.snapshot()
    prepared = dict(event="prepared", namespace="job", identity=identity, phase=phase, snapshot=snapshot)
    if chain is not None:
        prepared["phase_plan"] = chain.declaration(phase, snapshot)
    channel.send(prepared)
    started = False
    while True:
        channel._time()
        # Bind alone may never race the explicit original start command.
        if started:
            broker.tick()
        require(broker.state.healthy, "RESIDENT_LEDGER_UNHEALTHY")
        if select.select([channel.sock], [], [], 0.05)[0]:
            command = channel.receive()
            require(type(command) is dict, "RESIDENT_COMMAND")
            require(command.get("action") != "start" or not started, "RESIDENT_START_REPLAY")
            reply = handler.handle(command)
            channel.send(reply)
            if command["action"] == "start":
                started = True
            if reply["closed"] is not None:
                if chain is not None:
                    chain.retain_closure(phase, reply["closed"])
                    return reply["closed"]
                # The administrator must consume the final closure ACK while
                # this exact peer remains alive. It then sends finish and owns
                # the real process-exit and pipe-EOF capture, without a reply.
                finish = channel.receive()
                require(finish == {"action": "finish", "value": None}, "RESIDENT_FINISH")
                return reply["closed"]


def run(value, channel, broker):
    identity, principal = prepare_request(value, broker)
    from local_hand_jobs import quota_closure
    if fixture_phases(value) == CHAIN_PHASES:
        chain = Chain(broker, identity, value["plan"])
        for index, phase in enumerate(CHAIN_PHASES):
            if index:
                chain.advance(channel, CHAIN_PHASES[index - 1], phase)
            run_phase(broker, identity, phase, channel, chain=chain)
        chain.complete()
        require(channel.receive() == {"action": "finish", "value": None}, "RESIDENT_FINISH")
        return dict(schema="local-hand-q2-resident-result/v2", status="CHAIN_CLOSED", operation_id=identity,
            phases=list(CHAIN_PHASES), closure_digests={phase: quota_closure.digest(closed) for phase, closed in chain.closed.items()},
            q3_accepted=False, production_supported=False)
    closure = run_phase(broker, identity, "preflight", channel)
    return dict(schema="local-hand-q2-resident-result/v1", status="PHASE_CLOSED", operation_id=identity,
                phase="preflight", closure_digest=quota_closure.digest(closure),
                q3_accepted=False, production_supported=False)


def failure_reason(error):
    code = getattr(error, "code", str(error))
    return code if type(code) is str and re.fullmatch(r"[A-Z_]{1,100}", code) else type(error).__name__


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture")
    parser.add_argument("--sha256")
    args = parser.parse_args(argv)
    result = dict(schema="local-hand-q2-resident-result/v1", status="BLOCKED", q3_accepted=False,
                  production_supported=False)
    broker = channel = None
    try:
        require(args.fixture and args.sha256, "EXPLICIT_PRIVATE_FIXTURE_REQUIRED")
        value = bootstrap(args.fixture, args.sha256)
        channel = channel_from_pin(value["bridge"], version=2 if value["schema"] == CHAIN_SCHEMA else 1)
        broker = compose(value)
        result = run(value, channel, broker)
    except Exception as error:
        result.update(status="INCOMPLETE" if broker is not None else "BLOCKED",
                      reason=failure_reason(error))
    finally:
        if channel is not None:
            try:
                channel.close()
            except Exception as error:
                result.update(status="INCOMPLETE", reason=failure_reason(error))
        if broker is not None:
            try:
                from local_hand_jobs.cli import close_service
                close_service(broker, None, failed=result["status"] not in ("PHASE_CLOSED", "CHAIN_CLOSED"))
            except Exception as error:
                result.update(status="INCOMPLETE", reason=failure_reason(error))
    output = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    require(len(output) <= 4096, "RESIDENT_SUMMARY_LIMIT")
    os.write(1, output + b"\n")
    return 0 if result["status"] in ("PHASE_CLOSED", "CHAIN_CLOSED") else 3


if __name__ == "__main__":
    raise SystemExit(main())
