"""Explicit finite fixture launcher inside an existing root controller.

Creates only finite evidence/configuration files in declared existing fixture
directories. The external supervisor must own this controller's original
deadline, output pipes and independent stop. No host provisioning or recovery.
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
import subprocess
import sys
import threading
from types import SimpleNamespace

SCHEMA = "local-hand-q2-launcher/v1"
CHAIN_SCHEMA = "local-hand-q2-launcher/v2"
PHASES = ("preflight", "business", "evidence")
LIMIT = 2 * 1024 * 1024
SOURCE_ROOTS = frozenset({"admin", "local_hand", "local_hand_jobs", "local_hand_connect", "local_hand_mcp"})


def require(condition, code):
    if not condition:
        raise ValueError(code)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "LAUNCHER_DUPLICATE_KEY")
        result[key] = value
    return result


def protected(path, maximum):
    """Root-owned no-follow source/fixture read, before application imports."""
    require(type(path) is str and path.startswith("/") and not path.startswith("//")
            and str(Path(path)) == path and ".." not in Path(path).parts, "LAUNCHER_PATH")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        parts = Path(path).parts[1:]
        require(bool(parts), "LAUNCHER_PATH")
        for index, name in enumerate(parts):
            directory = index < len(parts) - 1
            child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
                            | (os.O_DIRECTORY if directory else 0), dir_fd=fd)
            os.close(fd); fd = child
            info = os.fstat(fd)
            require(info.st_uid == 0 and not info.st_mode & 0o022
                    and (stat.S_ISDIR(info.st_mode) if directory else
                         stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not info.st_mode & 0o6000),
                    "LAUNCHER_PROTECTION")
        require(info.st_size <= maximum, "LAUNCHER_FILE_LIMIT")
        raw = bytearray()
        while len(raw) <= maximum:
            chunk = os.read(fd, min(65536, maximum + 1 - len(raw)))
            if not chunk: break
            raw.extend(chunk)
        after = os.fstat(fd)
        require(len(raw) <= maximum and all(getattr(info, key) == getattr(after, key) for key in
                ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")), "LAUNCHER_FILE_CHANGED")
        return bytes(raw)
    finally:
        os.close(fd)


def decode(raw, digest):
    require(len(raw) <= LIMIT and type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest)
            and hashlib.sha256(raw).hexdigest() == digest, "LAUNCHER_DIGEST")
    value = json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("LAUNCHER_NUMBER")))
    def finite(item, depth=0):
        require(depth <= 22, "LAUNCHER_DEPTH")
        if type(item) is dict:
            for child in item.values(): finite(child, depth + 1)
        elif type(item) is list:
            for child in item: finite(child, depth + 1)
        else:
            require(item is None or type(item) in (str, bool, int), "LAUNCHER_NUMBER")
            if type(item) is int: require(0 <= item <= 2**63-1, "LAUNCHER_NUMBER")
    finite(value)
    require(type(value) is dict and set(value) == {"schema", "purpose", "source", "resident", "assembly",
            "controller_envelope", "setpriv", "output", "declarations", "session"}
            and (value["schema"], value["purpose"]) in ((SCHEMA, "ISOLATED_Q2_PREFLIGHT"),
                (CHAIN_SCHEMA, "ISOLATED_Q2_CHAIN")), "LAUNCHER_SCHEMA")
    return value


class Pinned(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Import application code from retained verified bytes, never a cache."""
    def __init__(self, sources):
        self.sources = sources

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in SOURCE_ROOTS:
            return None
        require(fullname in self.sources, "LAUNCHER_UNPINNED_MODULE")
        return importlib.util.spec_from_loader(fullname, self, is_package=self.sources[fullname][2])

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        raw, filename, package = self.sources[module.__name__]
        module.__file__ = filename
        if package:
            module.__path__ = []
        exec(compile(raw, filename, "exec", dont_inherit=True), module.__dict__)


def source(value, repository):
    pin = value["source"]
    require(type(pin) is dict and set(pin) == {"commit", "files"}
            and re.fullmatch(r"[0-9a-f]{40}", pin["commit"]), "LAUNCHER_SOURCE")
    files = pin["files"]
    require(type(files) is dict and 1 <= len(files) <= 512, "LAUNCHER_SOURCE_FILES")
    require(not any(name.split(".")[0] in SOURCE_ROOTS for name in sys.modules), "LAUNCHER_PREIMPORTED")
    sources = {}
    for name, digest in files.items():
        require(type(name) is str and re.fullmatch(r"(?:tools|tests/e3_host)/(?:[a-z_][a-z0-9_]*/)*[a-z_][a-z0-9_]*\.py", name)
                and type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest), "LAUNCHER_SOURCE_PATH")
        filename = str(repository / name)
        raw = protected(filename, LIMIT)
        require(hashlib.sha256(raw).hexdigest() == digest, "LAUNCHER_SOURCE_CHANGED")
        if name.startswith("tools/"):
            relative = name[len("tools/"):]
            package = relative.endswith("/__init__.py")
            module = (relative[:-12] if package else relative[:-3]).replace("/", ".")
            if module.split(".")[0] in SOURCE_ROOTS:
                require(module not in sources, "LAUNCHER_SOURCE_ALIAS")
                sources[module] = raw, filename, package
    for folder in ("admin/local_hand_quota_observer", "local_hand_jobs", "local_hand"):
        for path in (repository / "tools" / folder).glob("**/*.py"):
            require(path.relative_to(repository).as_posix() in files, "LAUNCHER_SOURCE_MISSING")
    for name in ("q2_launcher", "q2_resident"):
        require("tests/e3_host/" + name + ".py" in files, "LAUNCHER_ENTRY_MISSING")
    # Only these existing administrative namespace packages are synthetic.
    # Every other application package and module must have explicit source.
    for name in ("admin", "admin.local_hand_quota_observer"):
        if any(module.startswith(name + ".") for module in sources):
            sources.setdefault(name, (b"", "<pinned-namespace>", True))
    for name in sources:
        parts = name.split(".")
        for count in range(1, len(parts)):
            parent = ".".join(parts[:count])
            require(parent in sources and sources[parent][2], "LAUNCHER_SOURCE_PARENT")
    require(all(name in sources and sources[name][2] for name in ("local_hand", "local_hand_jobs"))
            and "local_hand.provenance" in sources, "LAUNCHER_SOURCE_MISSING")
    sys.meta_path.insert(0, Pinned(sources))
    from local_hand import provenance
    require(provenance.source_commit(require_clean=True) == pin["commit"], "LAUNCHER_SOURCE_IDENTITY")


def controller(value, template, declared_totals=None):
    """Verify independent controller before the first file or process mutation."""
    from admin.local_hand_quota_observer import controller_guard as guard, q2_config as c
    from admin.local_hand_quota_observer.systemd_runtime import Capture
    from local_hand_jobs import budget, quota_contract as q, quota_grant as g
    prepared = template.data()
    data = prepared["installation"]
    envelope = value["controller_envelope"]
    q._keys(envelope, {"controller", "issued_ns", "deadline_ns", "output_bytes", "storage_bytes", "storage_inodes"})
    spec = guard.decode_controller(envelope["controller"])
    clock = budget.current_clock()
    q.integer(envelope["issued_ns"], 1)
    q.integer(envelope["deadline_ns"], envelope["issued_ns"] + 1)
    q.require(envelope["issued_ns"] <= clock["boottime_ns"] < envelope["deadline_ns"]
              <= envelope["issued_ns"] + spec.runtime_max_usec * 1000, "LAUNCHER_DEADLINE")
    q.integer(envelope["output_bytes"], 1, 32768)
    q.integer(envelope["storage_bytes"], 1024 * 1024)
    phase_count = 3 if value["schema"] == CHAIN_SCHEMA else 1
    q.integer(envelope["storage_inodes"], max(8, 6 + phase_count))
    # Capacity must fund the controller/resident before the resident reserves
    # anything. Static costs do not need, and must not invent, its future phase
    # clock or quota grant. Revalidate all finite template amounts before sums.
    management = prepared["grant"]["management"]
    q._keys(management, g._MANAGEMENT_KEYS - {"issued_ns"})
    for key in ("storage_bytes", "storage_inodes", "receive_ns", "stop_ns"):
        q.integer(management[key], 1)
    q._keys(management["stages"], set(g.STAGES))
    for stage in management["stages"].values():
        q._keys(stage, g._STAGE_KEYS)
        for amount in stage.values(): q.integer(amount, 1)
    capacity = g.decode_capacity(q._canonical(data["capacity"], g.GRANT_LIMIT))
    request = prepared["grant"]["request"]
    require(all(request[key] == capacity[key] for key in ("boot_id", "epoch", "authority_digest"))
            and management["capacity_digest"] == g.digest(capacity), "LAUNCHER_CAPACITY_BINDING")
    totals = g.totals(SimpleNamespace(as_dict=lambda: prepared["grant"])) if declared_totals is None else declared_totals
    costs = dict(storage_bytes=envelope["storage_bytes"], storage_inodes=envelope["storage_inodes"],
        cpu_ns=((spec.runtime_max_usec + spec.timeout_stop_usec + 1_000_000) * spec.cpu_quota_per_sec_usec + 999) // 1000,
        memory_bytes=spec.memory_bytes, pids=spec.tasks_max,
        # Resident pipes, manager-control captures and the outer summary have
        # independent finite buffers; none is charged as zero.
        output_bytes=phase_count * envelope["output_bytes"] + 32768 + 4096)
    for key, amount in costs.items():
        require(q.integer(amount + totals[key]) <= capacity["management"][key], "LAUNCHER_CONTROLLER_CAPACITY")
    for kind in ("bytes", "inodes"):
        used = costs["storage_" + kind] + totals["storage_" + kind] + capacity["retained_" + kind]
        used += sum(domain["hard_" + kind] for domain in capacity["domains"])
        require(q.integer(used) <= capacity["ceiling_" + kind], "LAUNCHER_CONTROLLER_STORAGE")
    ordinary = value["resident"]["ordinary"]
    q._keys(ordinary, {"uid", "gid", "parent", "broker_cgroup", "initial_userns"})
    q.integer(ordinary["uid"], 1); q.integer(ordinary["gid"], 1)
    q._keys(data["initial_userns"], {"device", "inode"})
    for number in data["initial_userns"].values(): q.integer(number, 1)
    require(ordinary["initial_userns"] == data["initial_userns"], "LAUNCHER_USER_NAMESPACE_BINDING")
    for path in ("/proc/self/ns/user", "/proc/1/ns/user"):
        info = os.stat(path)
        require({"device": info.st_dev, "inode": info.st_ino} == data["initial_userns"],
                "LAUNCHER_INITIAL_USER_NAMESPACE")
    require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0, "LAUNCHER_ADMINISTRATOR")
    for parent in (ordinary["parent"], template.data()["grant"]["query_parent"],
                   template.data()["grant"]["management_parent"]):
        c.identity(parent)
        require(not c.overlap(spec.cgroup, parent["path"]), "LAUNCHER_CONTROLLER_OVERLAP")
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    # Existing controller must be able to drop credentials; never add caps.
    require(all(int(status[key], 16) & 0x1c0 == 0x1c0 for key in ("CapPrm", "CapEff")), "LAUNCHER_DROP_PRIVILEGES_UNAVAILABLE")
    adapter = SimpleNamespace(initial_userns_device=data["initial_userns"]["device"],
        initial_userns_inode=data["initial_userns"]["inode"], systemctl_path=data["programs"]["systemctl"]["path"],
        systemctl_sha256=data["programs"]["systemctl"]["sha256"])
    manifest = SimpleNamespace(boot_id=template.data()["grant"]["request"]["boot_id"],
                               cgroup_parent=template.data()["grant"]["query_parent"]["path"])
    before = guard._host_identity(adapter, manifest, spec)
    guard._cgroup_identity(spec)
    guard._check_manager(guard._show_once(adapter, spec), spec, before[0])
    # Delegation belongs to the enclosing system user manager service, never
    # its -.slice. Observe the fixed UID's existing service without installing
    # or changing it. Its child ordinary slice must be in that exact subtree.
    fields = {"Id", "LoadState", "ActiveState", "SubState", "ControlGroup", "MainPID", "InvocationID", "User", "Delegate"}
    unit = "user@" + str(ordinary["uid"]) + ".service"
    capture = Capture(4096)
    current = budget.current_clock()
    end = min(envelope["deadline_ns"], current["boottime_ns"] + 2_000_000_000)
    try:
        require(current["boot_id"] == clock["boot_id"] and current["boottime_ns"] < end, "LAUNCHER_DEADLINE")
        capture.start((adapter.systemctl_path, "--system", "--no-pager", "--no-ask-password", "show", unit,
                       "--all", "--property=" + ",".join(sorted(fields))))
        while True:
            current = budget.current_clock()
            require(current["boot_id"] == clock["boot_id"] and current["boottime_ns"] < end,
                    "LAUNCHER_MANAGER_DEADLINE")
            capture.pump()
            require(capture.error is None, "LAUNCHER_MANAGER_CAPTURE")
            if capture.done:
                require(capture.process.returncode == 0 and not capture.stderr, "LAUNCHER_MANAGER_FAILED")
                break
            readers = [stream for name in ("stdout", "stderr") if name not in capture.eof
                       for stream in (getattr(capture.process, name),)]
            select.select(readers, [], [], min(0.01, (end - current["boottime_ns"]) / 1e9))
        pairs = [line.split("=", 1) for line in capture.stdout.decode("ascii").splitlines()]
        require(all(len(pair) == 2 for pair in pairs) and len(pairs) == len({pair[0] for pair in pairs}),
                "LAUNCHER_MANAGER_FORMAT")
        facts = dict(pairs)
        require(set(facts) == fields and all(facts[key] == expected for key, expected in {
            "Id": unit, "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
            "User": str(ordinary["uid"]), "Delegate": "yes"}.items()), "LAUNCHER_USER_MANAGER")
        q.match(facts["InvocationID"], r"[0-9a-f]{32}")
        require(re.fullmatch(r"[1-9][0-9]{0,19}", facts["MainPID"]) is not None, "LAUNCHER_USER_MANAGER_PID")
        manager_cgroup = q.canonical_path(facts["ControlGroup"])
        require(manager_cgroup != "/" and ordinary["parent"]["path"].startswith(manager_cgroup + "/")
                and not c.overlap(spec.cgroup, manager_cgroup), "LAUNCHER_USER_MANAGER_PARENT")
        capture.close_pipes()
        require(capture.done, "LAUNCHER_MANAGER_CAPTURE")
    finally:
        # Client cancellation is cleanup only, never service exit proof. The
        # original controller's independent outer supervision remains required.
        if not capture.settled:
            try: capture.kill_client()
            except (OSError, ValueError): pass
        capture.close_pipes()
    guard._cgroup_identity(spec)
    require(before == guard._host_identity(adapter, manifest, spec), "LAUNCHER_CONTROLLER_CHANGED")
    current = budget.current_clock()
    require(current["boot_id"] == clock["boot_id"] and current["boottime_ns"] < envelope["deadline_ns"],
            "LAUNCHER_DEADLINE")
    return clock


def directory(pin, mode):
    from admin.local_hand_quota_observer import q2_config as c
    fd = c.pinned_directory(pin)
    try:
        info = os.fstat(fd)
        require(info.st_uid == 0 and stat.S_IMODE(info.st_mode) == mode, "LAUNCHER_DIRECTORY_MODE")
        with os.scandir(fd) as entries:
            require(next(entries, None) is None, "LAUNCHER_ALREADY_CONSUMED")
        return fd
    except BaseException:
        os.close(fd); raise


def save(fd, name, raw, mode=0o600):
    """Create once and durably retain, including partial/failed attempts."""
    target = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode, dir_fd=fd)
    try:
        os.fchmod(target, mode)
        pending = memoryview(raw)
        while pending:
            count = os.write(target, pending)
            require(count > 0, "LAUNCHER_WRITE")
            pending = pending[count:]
        os.fsync(target)
    finally:
        os.close(target)
    os.fsync(fd)


def encoded(value, limit=65536):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    require(len(raw) <= limit, "LAUNCHER_RECORD_LIMIT")
    return raw


def start_ticks(pid):
    with open("/proc/" + str(pid) + "/stat", "rb") as stream: raw = stream.read(4097)
    require(len(raw) <= 4096, "LAUNCHER_PROC_LIMIT")
    return int(raw[raw.rfind(b")") + 2:].split()[19])


def command(value, fixture_path, fixture_digest):
    resident = value["resident"]; ordinary = resident["ordinary"]
    return [value["setpriv"]["path"], "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all",
            "--no-new-privs", "--reuid=" + str(ordinary["uid"]), "--regid=" + str(ordinary["gid"]),
            "--clear-groups", "--", resident["installation"]["programs"]["python"]["path"],
            "-I", "-B", resident["entry"]["path"], "--fixture", fixture_path, "--sha256", fixture_digest]


def reason(error):
    code = getattr(error, "code", None)
    if not isinstance(code, str) or not re.fullmatch(r"[A-Z_]{1,100}", code):
        code = str(error)
    return code if re.fullmatch(r"[A-Z_]{1,100}", code) else type(error).__name__[:100]


def validate_phase_plan(resident, prepared, grant, previous_plans):
    """Bind the pinned resident's durable facts to the immutable declaration.

    Dynamic facts arrive over the original authenticated process channel; the
    pinned resident checks their original SQLite events. No incoming argv,
    replacement base plan, new allocation, or future budget is authoritative.
    """
    from local_hand_jobs import quota_contract as q, quota_grant as g, quota_payload
    from local_hand_jobs.broker import phase_plan
    plan = quota_payload.decode_phase_plan(prepared["phase_plan"])
    phase = prepared["phase"]
    require(type(plan) is dict and list(previous_plans) == list(PHASES[:PHASES.index(phase)]),
            "LAUNCHER_PHASE_PLAN_ORDER")
    prep = prepared["snapshot"]["preparation"]
    require(type(plan.get("preflight_facts")) is dict, "LAUNCHER_PHASE_FACTS")
    facts = plan["preflight_facts"]
    if phase == "preflight":
        require(facts == {}, "LAUNCHER_PHASE_FACTS")
    if phase == "evidence":
        require(facts == previous_plans["business"]["preflight_facts"], "LAUNCHER_PHASE_FACTS_CHANGED")
    row = dict(namespace="job", id=prepared["identity"], plan=resident["plan"], record={"facts": facts})
    store = None
    if phase == "evidence":
        frozen = plan.get("evidence_snapshot")
        require(type(frozen) is dict, "LAUNCHER_SNAPSHOT")
        require(frozen.get("operation_id") == prepared["identity"] and frozen.get("reconcile_id") is None
                and frozen.get("previous_seal_id") is None, "LAUNCHER_SNAPSHOT_OPERATION")
        q.integer(frozen.get("event_seq"), 1)
        business = previous_plans["business"]
        require(frozen.get("root") == g.root_paths(business["bootstrap_allocation"])["evidence"],
                "LAUNCHER_SNAPSHOT_ROOT")
        quiet = frozen.get("quiescence")
        q._keys(quiet, {"execution_id", "event_seq", "future_starts_blocked", "tree_exited",
                        "collectors_stopped", "writers_stopped"})
        require(quiet["execution_id"] == business["execution_id"] and quiet["event_seq"] == frozen["event_seq"]
                and all(quiet[k] is True for k in ("future_starts_blocked", "tree_exited", "collectors_stopped", "writers_stopped")),
                "LAUNCHER_SNAPSHOT_QUIESCENCE")
        store = plan.get("evidence_store_root")
        require(prep["allocation"]["retained_paths"] == [store], "LAUNCHER_SNAPSHOT_STORE")
        row["record"]["frozen_snapshot"] = frozen
    expected = phase_plan(row, phase, prep["budget"], allocation=prep["allocation"], evidence_store_root=store)
    require(plan == expected, "LAUNCHER_PHASE_PLAN_CHANGED")
    require(grant.as_dict()["budget"] == prep["budget"] and grant.as_dict()["allocation"] == prep["allocation"],
            "LAUNCHER_PHASE_GRANT")
    return dict(expected, quota_observation_grant=grant.as_dict())


def run(value, repository):
    from local_hand_jobs import budget, quota_bridge as bridge, quota_contract as q, quota_closure, runner
    from admin.local_hand_quota_observer import q2_assembly as assembly, q2_chain as chains, q2_config as c, q2_management as m
    from admin.local_hand_quota_observer.q2_coordinator import Coordinator
    from admin.local_hand_quota_observer.q2_capture import capture_existing
    raw = encoded(value["assembly"], LIMIT)
    chained = value["schema"] == CHAIN_SCHEMA
    phases = PHASES if chained else ("preflight",)
    chain = chains.decode(raw, hashlib.sha256(raw).hexdigest()) if chained else None
    template = chains.phase_template(chain, "preflight") if chained else assembly.decode(raw, hashlib.sha256(raw).hexdigest())
    t = template.data(); resident = value["resident"]
    q.match(value["session"], r"[0-9a-f]{64}")
    q.integer(resident["ordinary"]["uid"], 1, 2**32-2)
    q.integer(resident["ordinary"]["gid"], 1, 2**32-2)
    work = next(root for root in t["grant"]["roots"] if root["role"] == "work")
    require((resident["ordinary"]["uid"], resident["ordinary"]["gid"]) == (work["uid"], work["gid"]),
            "LAUNCHER_ORDINARY_ACCOUNT")
    require("bridge" not in resident and resident["phases"] == list(phases)
            and resident["installation"]["source_commit"] == t["installation"]["source_commit"] == value["source"]["commit"],
            "LAUNCHER_RESIDENT_BINDING")
    if chained:
        require(resident["schema"] == "local-hand-q2-resident/v2" and resident["purpose"] == "ISOLATED_Q2_CHAIN",
                "LAUNCHER_RESIDENT_BINDING")
        for phase in phases:
            phase_work = next(root for root in chain.data()["phases"][phase]["grant"]["roots"] if root["role"] == "work")
            require((phase_work["uid"], phase_work["gid"]) == (resident["ordinary"]["uid"], resident["ordinary"]["gid"]),
                    "LAUNCHER_ORDINARY_ACCOUNT")
    require(resident["entry"]["path"] == str(repository / "tests/e3_host/q2_resident.py")
            and resident["entry"]["sha256"] == value["source"]["files"]["tests/e3_host/q2_resident.py"], "LAUNCHER_RESIDENT_ENTRY")
    require(resident["ordinary"]["parent"] == t["peer"]["parent"] and
            resident["ordinary"]["broker_cgroup"] == value["controller_envelope"]["controller"]["cgroup"], "LAUNCHER_RESIDENT_PARENT")
    work = [root for root in t["grant"]["roots"] if root["role"] == "work"]
    require(len(work) == 1 and (resident["ordinary"]["uid"], resident["ordinary"]["gid"])
            == (work[0]["uid"], work[0]["gid"]), "LAUNCHER_RESIDENT_ACCOUNT_BINDING")
    installed = resident["installation"]
    require(t["peer"]["executable"]["path"] == installed["programs"]["python"]["path"],
            "LAUNCHER_PEER_INTERPRETER")
    for name, digest in installed["files"].items():
        require(value["source"]["files"].get("tools/" + name) == digest, "LAUNCHER_INSTALLED_SOURCE")
    require(t["peer"]["runner"]["path"] == installed["package_root"] + "/local_hand_jobs/runner.py"
            and t["peer"]["runner"]["sha256"] == installed["files"]["local_hand_jobs/runner.py"], "LAUNCHER_RUNNER_BINDING")
    for pin in (value["setpriv"], installed["programs"]["python"], *t["installation"]["programs"].values()):
        q._keys(pin, {"path", "sha256"})
        require(hashlib.sha256(protected(pin["path"], 64 * 1024 * 1024)).hexdigest() == pin["sha256"], "LAUNCHER_PROGRAM_CHANGED")
    require(value["setpriv"]["path"] == "/usr/bin/setpriv", "LAUNCHER_PRIVILEGE_PROGRAM")
    for key in ("output", "declarations"): c.identity(value[key])
    protected_paths = [value["output"]["path"], value["declarations"]["path"], t["output"]["path"],
        t["journal"]["path"], t["installation"]["evidence"]["path"], t["installation"]["tools_path"], installed["package_root"],
        *t["grant"]["allocation"]["paths"]]
    require(all(not c.overlap(first, second) for i, first in enumerate(protected_paths) for second in protected_paths[i+1:]), "LAUNCHER_GEOMETRY")
    if chained:
        for phase in phases:
            declaration = chain.data()["phases"][phase]
            extras = [declaration["output"]["path"], *declaration["grant"]["allocation"]["paths"],
                      declaration["grant"]["endpoint"]["path"], declaration["service"]["control_path"]]
            require(all(not c.overlap(root, path) for root in (value["output"]["path"], value["declarations"]["path"], installed["package_root"])
                        for path in extras), "LAUNCHER_GEOMETRY")
    clock = controller(value, template, chains.declared_totals(chain)) if chained else controller(value, template)
    end = value["controller_envelope"]["deadline_ns"]
    output = declarations = None; channel = record = None; process = None; sockets = []; capture = {}; worker = None
    phase_result = None; configs = []; plans = {}; closures = {}; grants = {}; broker_session = None
    result = dict(schema="local-hand-q2-launcher-result/v2" if chained else "local-hand-q2-launcher-result/v1", status="INCOMPLETE", q3_accepted=False,
                  production_supported=False, independent_controller_stop_required=True)
    try:
        output = directory(value["output"], 0o700)
        declarations = directory(value["declarations"], 0o755)
        save(output, "reservation.json", encoded(dict(schema="local-hand-q2-launcher-reservation/v1",
            fixture_digest=hashlib.sha256(encoded(value, LIMIT)).hexdigest(), session=value["session"],
            controller=value["controller_envelope"], started_ns=clock["boottime_ns"])))
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET); sockets = [left, right]
        for sock in sockets: sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        declaration = dict(resident, bridge=dict(fd=right.fileno(), pid=os.getpid(), uid=0, gid=0,
            start_ticks=start_ticks(os.getpid()), session=value["session"], boot_id=clock["boot_id"], deadline_ns=end))
        raw = encoded(declaration, 262144)
        save(declarations, "resident.json", raw, 0o644)
        path = value["declarations"]["path"] + "/resident.json"
        argv = command(value, path, hashlib.sha256(raw).hexdigest())
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0, close_fds=True, pass_fds=(right.fileno(),), cwd="/", env={"PATH": "/usr/bin:/bin",
            "XDG_RUNTIME_DIR": "/run/user/" + str(resident["ordinary"]["uid"])})
        right.close(); sockets = [left]
        child_start = start_ticks(process.pid)
        channel = bridge.Channel(left, peer=(process.pid, resident["ordinary"]["uid"], resident["ordinary"]["gid"]),
            session=value["session"], boot_id=clock["boot_id"], deadline_ns=end, version=2 if chained else 1)
        require(start_ticks(process.pid) == child_start, "LAUNCHER_CHILD_REPLACED")
        def collect():
            try:
                captured = capture_existing(process, boot_id=clock["boot_id"], started_ns=clock["boottime_ns"],
                                            deadline_ns=end, limit=32768)
            except Exception as error:
                # A rejected capture setup has no verified pipe/exit evidence.
                # Keep it finite and incomplete, including direct JobError.
                closes = []
                for name in ("stdout", "stderr"):
                    try: getattr(process, name).close()
                    except Exception: closes.append(name)
                captured = dict(schema="local-hand-q2-outer-capture/v1", client_pid=process.pid,
                    returncode=None, stdout=b"", stderr=b"", eof=[], pipe_identities={},
                    error=reason(error), close_errors=closes, complete=False,
                    started_ns=clock["boottime_ns"], deadline_ns=end, independent_stop_required=True,
                    production_supported=False, q3_accepted=False)
            capture.update(captured)
        worker = threading.Thread(target=collect, name="q2-resident-capture", daemon=True); worker.start()
        for index, phase in enumerate(phases):
            while not select.select([left], [], [], 0.025)[0]: channel._time()
            prepared = channel.receive()
            keys = {"event", "namespace", "identity", "phase", "snapshot"}
            q._keys(prepared, keys | {"phase_plan"} if chained else keys)
            require(prepared["event"] == "prepared" and prepared["namespace"] == "job" and prepared["phase"] == phase
                    and prepared["identity"] == resident["request"]["operation_id"], "LAUNCHER_PREPARED")
            # The original broker session is distinct from the transport nonce.
            prep = prepared["snapshot"]["preparation"]
            session = prep["session"]
            if broker_session is None: broker_session = session
            require(session == broker_session, "LAUNCHER_BROKER_SESSION_CHANGED")
            if chained:
                template = chains.phase_template(chain, phase)
                grant = chains.build_grant(chain, prepared["snapshot"], previousconfigs=configs,
                                          session=session, clock=budget.current_clock())
                plan = validate_phase_plan(resident, prepared, grant, plans)
            else:
                grant = assembly.build_grant(template, prepared["snapshot"], session=session, clock=budget.current_clock())
                plan = dict(resident["plan"], phase=phase, execution_id=prep["budget"]["execution_id"],
                    budget_grant=prep["budget"], budgets=prep["budget"]["limits"], bootstrap_allocation=prep["allocation"],
                    supervision_version=3, quota_observation_grant=grant.as_dict())
            # Fixed setpriv delivery inherits this mount namespace. No extra
            # SYS_PTRACE authority is acquired merely to inspect another UID.
            namespace = os.readlink("/proc/self/ns/mnt")
            execution = runner._quota_prepared_execution(plan, parent_mount_namespace=namespace,
                                                         now_ns=budget.current_clock()["boottime_ns"])
            argv = runner.quota_bootstrap_argv(execution, grant, script=template.data()["peer"]["runner"]["path"],
                                               now_ns=budget.current_clock()["boottime_ns"])
            installed = chains.install(chain, grant, bootstrap_argv=argv, previousconfigs=configs,
                session=session, clock=budget.current_clock()) if chained else assembly.install(template, grant,
                bootstrap_argv=argv, session=session, clock=budget.current_clock())
            config = installed["config"]
            m.controller(config, value["controller_envelope"])
            record = m.RunRecord(installed["management_record"])
            phase_result = Coordinator(config, value["controller_envelope"], record, bridge.Client(channel)).run()
            save(output, "phase-" + phase + ".json" if chained else "phase.json", encoded(phase_result))
            require(phase_result["status"] == "PHASE_CLOSED" and phase_result["q3_accepted"] is False
                    and phase_result["production_supported"] is False, "LAUNCHER_PHASE_UNCLOSED")
            closures[phase] = quota_closure.digest({"phase": phase, "fence": phase_result["fence"]})
            grants[phase] = grant.digest; plans[phase] = plan; configs.append(config)
            if chained:
                record.close(); record = None
                result["closed_phases"] = list(closures)
                if index + 1 < len(phases):
                    following = phases[index + 1]
                    channel.send(dict(action="advance", value={"from": phase, "to": following,
                                                               "closure_digest": closures[phase]}))
                    channel.advance_phase(following)
        channel.send(dict(action="finish", value=None))
        channel.close(); channel = None
        while worker.is_alive() and budget.current_clock()["boottime_ns"] < end: worker.join(0.025)
        require(bool(capture) and capture["complete"] and capture["returncode"] == 0, "LAUNCHER_RESIDENT_CAPTURE")
        summary = q._load(capture["stdout"], 4096, 4)
        if chained:
            q._keys(summary, {"schema", "status", "operation_id", "phases", "closure_digests", "q3_accepted", "production_supported"})
            require(summary["schema"] == "local-hand-q2-resident-result/v2" and summary["status"] == "CHAIN_CLOSED"
                    and summary["phases"] == list(phases) and summary["closure_digests"] == closures, "LAUNCHER_RESIDENT_RESULT")
        else:
            q._keys(summary, {"schema", "status", "operation_id", "phase", "closure_digest", "q3_accepted", "production_supported"})
            require(summary["schema"] == "local-hand-q2-resident-result/v1" and summary["status"] == "PHASE_CLOSED"
                    and summary["phase"] == "preflight" and summary["closure_digest"] == closures["preflight"], "LAUNCHER_RESIDENT_RESULT")
        require(summary["operation_id"] == prepared["identity"]
                and summary["q3_accepted"] is False and summary["production_supported"] is False
                and capture["stderr"] == b"", "LAUNCHER_RESIDENT_RESULT")
        result.update(status="CHAIN_CLOSED" if chained else "PREFLIGHT_CLOSED")
        result.update(dict(grant_digests=grants, closure_digests=closures) if chained else dict(grant_digest=grant.digest))
    except Exception as error:
        result["reason"] = reason(error)
    finally:
        failures = []
        def cleanup(action, code):
            try: action()
            except Exception:
                failures.append(code)
                result.update(status="INCOMPLETE", reason=code)
        if channel is not None: cleanup(channel.close, "LAUNCHER_CHANNEL_CLOSE")
        for sock in sockets: cleanup(sock.close, "LAUNCHER_SOCKET_CLOSE")
        if record is not None: cleanup(record.close, "LAUNCHER_RECORD_CLOSE")
        # Never kill a client to invent complete EOF. The independent original
        # controller runtime bounds surviving work; retain the delivery PID.
        if worker is not None:
            def await_capture():
                while worker.is_alive() and budget.current_clock()["boottime_ns"] < end: worker.join(0.025)
            cleanup(await_capture, "LAUNCHER_CAPTURE_WAIT")
        elif process is not None:
            for stream in (process.stdout, process.stderr): cleanup(stream.close, "LAUNCHER_PIPE_CLOSE")
        if output is not None:
            if capture:
                capture = dict(capture)
                for name in ("stdout", "stderr"):
                    raw = capture.pop(name)
                    cleanup(lambda name=name, raw=raw: save(output, "resident." + name, raw), "LAUNCHER_OUTPUT_PERSIST")
                cleanup(lambda: save(output, "capture.json", encoded(capture)), "LAUNCHER_CAPTURE_PERSIST")
                result["resident_capture"] = capture
            result["resident_pid"] = None if process is None else process.pid
            result["evidence"] = value["output"]["path"]
            result["cleanup_errors"] = failures
            cleanup(lambda: save(output, "result.json", encoded(result)), "LAUNCHER_RESULT_PERSIST")
            cleanup(lambda: os.close(output), "LAUNCHER_OUTPUT_CLOSE")
        if declarations is not None: cleanup(lambda: os.close(declarations), "LAUNCHER_DECLARATIONS_CLOSE")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture"); parser.add_argument("--sha256")
    args = parser.parse_args(argv)
    result = dict(schema="local-hand-q2-launcher-result/v1", status="BLOCKED", q3_accepted=False,
                  production_supported=False, independent_controller_stop_required=True)
    try:
        require(args.fixture and args.sha256, "EXPLICIT_PRIVATE_FIXTURE_REQUIRED")
        require(sys.flags.isolated and sys.dont_write_bytecode, "LAUNCHER_ISOLATED_PYTHON")
        value = decode(protected(args.fixture, LIMIT), args.sha256)
        repository = Path(__file__).resolve().parents[2]
        source(value, repository)
        result = run(value, repository)
    except Exception as error:
        result["reason"] = reason(error)
    # Full records and host identities stay in the private fixture directory.
    print(json.dumps({key: result[key] for key in ("schema", "status", "q3_accepted", "production_supported",
          "independent_controller_stop_required", "reason", "evidence") if key in result}, sort_keys=True))
    return 0 if result["status"] in ("PREFLIGHT_CLOSED", "CHAIN_CLOSED") else 3


if __name__ == "__main__": raise SystemExit(main())
