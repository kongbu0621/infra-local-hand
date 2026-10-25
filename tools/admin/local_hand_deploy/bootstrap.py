"""Finite, offline import of a stopped guarded compatibility baseline.

This is not a hot barrier for an old manager.  The operator first persistently
masks the old entry units and installs the separately named guarded definitions,
without starting them.  This module verifies those facts, owns the old dispatch
locks, and publishes only configuration files.  It never stops a business unit,
replays a task, starts a service, or treats a caller's ``offline`` flag as proof.

Old ``--session`` clients need inherited authenticated channels to the original
root controller (TaskSession.open), not merely a retained descriptor.  Closing
that exact controller and its cgroup closes this path; ordinary interactive OS
accounts do not have to be disabled.  Administrator launches outside the declared
installation remain subject to the deployment's cooperative single-writer rule.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import copy
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import time

from local_hand_jobs import startup
from local_hand_jobs.contract import JobError
from local_hand_jobs.maintenance import MaintenanceGate
from local_hand import provenance

from . import files
from .model import DeployError, PLAN_SCHEMA, canonical, decode, digest, identity, operation_id, seal_plan, validate_plan
from .planner import _path, _selection, validate_profile
from .runtime import PlanningEnvironment
from .services import UNIT, HOOKS, definition_digest
from .systemd_bus import SystemdBus


MANIFEST_SCHEMA = "local-hand-offline-bootstrap/v1"
MAX_ENTRIES = 8
MAX_RECORDS = 64
MAX_ATTEMPTS = 256
MAX_RECORD_BYTES = 128 * 1024
MAX_SCAN = 2048


def _fail(code, message):
    raise DeployError(code, message)


def is_bootstrap(plan):
    value = plan.get("source", {}).get("bootstrap")
    return isinstance(value, dict) and value.get("schema") == MANIFEST_SCHEMA


def _read(path, owner, maximum=MAX_RECORD_BYTES):
    try:
        return decode(startup.protected_read(path, owner_uid=owner, maximum=maximum))
    except JobError as error:
        raise DeployError("BOOTSTRAP_UNKNOWN", "A protected original record cannot be observed") from error


def _exists(path):
    try:
        Path(path).lstat()
        return True
    except FileNotFoundError:
        return False


def _children(path, limit):
    # Bound enumeration itself, not merely the final selected matches.
    result = []
    with os.scandir(path) as stream:
        for item in stream:
            if len(result) >= limit:
                _fail("BOOTSTRAP_SCAN_LIMIT", "Legacy inventory exceeds its fixed scan budget")
            result.append(Path(item.path))
    return sorted(result)


def _directory(path, owner):
    fd = startup._protected_directory(path, owner_uid=owner)
    os.close(fd)


def _legacy(specifications, owner):
    if not isinstance(specifications, list) or not 1 <= len(specifications) <= MAX_ENTRIES:
        _fail("BOOTSTRAP_SCOPE", "A finite explicit old entry set is required")
    entries, units, dispatch = [], set(), False
    for spec in specifications:
        kind = spec.get("kind") if isinstance(spec, dict) else None
        keys = {"kind", "unit", "configuration"} if kind in {"resident", "prepared"} else {"kind", "unit"}
        if (kind not in {"resident", "prepared", "mcp", "gateway"} or set(spec) != keys
                or not UNIT.fullmatch(str(spec.get("unit", ""))) or spec["unit"] in units):
            _fail("BOOTSTRAP_SCOPE", "Only fixed old manager, MCP and gateway services are admitted")
        units.add(spec["unit"])
        entry = dict(spec)
        if kind in {"resident", "prepared"}:
            dispatch = True
            path = _path(spec["configuration"])
            config = _read(path, owner, 2 * 1024 * 1024)
            if config.get("maintenance") is not None:
                _fail("BOOTSTRAP_SCOPE", "Already guarded managers use the ordinary deployment protocol")
            if kind == "resident":
                if not isinstance(config.get("private_root"), str) or not isinstance(config.get("socket"), str):
                    _fail("BOOTSTRAP_SCOPE", "Old resident configuration lacks its actual dispatch roots")
                entry["records_root"] = _path(config["private_root"])
                entry["lock"] = str(Path(entry["records_root"]) / "service.lock")
            else:
                if config.get("schema") != "local-hand-prepared-service/v1":
                    _fail("BOOTSTRAP_SCOPE", "Old prepared configuration has an unsupported schema")
                entry["output"] = _path(config["output"])
                entry["lock"] = str(Path(entry["output"]) / "service.lock")
                raw = startup.protected_read(_path(config["launch_path"]), owner_uid=owner, maximum=2 * 1024 * 1024)
                if hashlib.sha256(raw).hexdigest() != config.get("launch_sha256"):
                    _fail("BOOTSTRAP_SCOPE", "Original prepared launch binding differs")
                launch = decode(raw)
                entry["controller_unit"] = launch["controller_envelope"]["controller"]["unit"]
                entry["launch_path"] = config["launch_path"]
                entry["launch_digest"] = config["launch_sha256"]
            entry["socket"] = _path(config["socket"])
            entry["configuration_digest"] = digest(config)
        entries.append(entry)
    if not dispatch:
        _fail("BOOTSTRAP_SCOPE", "Import requires the original dispatch owner, not just a network listener")
    if len({entry["lock"] for entry in entries if "lock" in entry}) != sum("lock" in entry for entry in entries):
        _fail("BOOTSTRAP_SCOPE", "Duplicate old dispatch lock")
    return entries


@contextmanager
def legacy_locks(entries, owner, expected=None):
    """Own existing dispatch locks; never manufacture evidence with O_CREAT."""
    bindings = {}
    with ExitStack() as stack:
        for entry in sorted((item for item in entries if "lock" in item), key=lambda item: item["lock"]):
            path = Path(entry["lock"])
            directory = startup._protected_directory(path.parent, owner_uid=owner)
            stack.callback(os.close, directory)
            fd = os.open(path.name, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_nlink != 1):
                _fail("BOOTSTRAP_LOCK", "Original dispatch lock is not protected")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                _fail("BOOTSTRAP_BUSY", "An old dispatch owner is still alive")
            named = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            if (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
                _fail("BOOTSTRAP_LOCK", "Original dispatch lock was replaced")
            bindings[str(path)] = files._binding(fd)
        if expected is not None and bindings != expected:
            _fail("BOOTSTRAP_LOCK", "Original dispatch lock identity changed")
        yield bindings


class OfflineObserver:
    """Fixed read-only platform observations. Injection is only for trusted tests."""
    def __init__(self, profile, *, bus_factory=None):
        self.profile, self.owner = profile, profile.get("owner_uid", 0)
        self.environment = PlanningEnvironment(profile)
        self.bus_factory = bus_factory or (lambda: SystemdBus(timeout=min(profile.get("timeout_seconds", 30), 30)))
        self.deadline = None

    def _budget(self):
        if self.deadline is not None and time.monotonic() > self.deadline:
            _fail("BOOTSTRAP_OBSERVATION_TIMEOUT", "Offline observation exceeded its finite time budget")

    def cgroup_empty(self, value):
        name = value.get("ControlGroup", "")
        if not name:
            return
        path = Path("/sys/fs/cgroup") / name.lstrip("/")
        if not name.startswith("/") or ".." in path.parts:
            _fail("BOOTSTRAP_UNKNOWN", "Invalid original process group")
        pending, count = [path], 0
        while pending:
            self._budget()
            current = pending.pop()
            if not current.exists():
                continue
            for child in _children(current, MAX_SCAN):
                count += 1
                if count > MAX_SCAN:
                    _fail("BOOTSTRAP_SCAN_LIMIT", "Original cgroup exceeds its observation budget")
                if child.name == "cgroup.procs" and child.read_bytes().strip():
                    _fail("BOOTSTRAP_BUSY", "An old process or inherited session channel remains alive")
                if stat.S_ISDIR(child.lstat().st_mode):
                    pending.append(child)

    def stopped(self, bus, name, *, masked=False):
        self._budget()
        if not UNIT.fullmatch(str(name)):
            _fail("BOOTSTRAP_SCOPE", "Legacy record contains an unsupported controller unit")
        value = bus.unit(name)
        if (value.get("ActiveState") not in {"inactive", "failed"} or value.get("MainPID", 0)
                or value.get("ControlPID", 0) or value.get("Job", [0])[0]
                or any(job[1] == name for job in bus.jobs())):
            _fail("BOOTSTRAP_BUSY", "An old service, controller or queued systemd job is not closed")
        self.cgroup_empty(value)
        if masked:
            # masked-runtime is deliberately insufficient after an ordinary reboot.
            if value.get("UnitFileState") != "masked" or value.get("LoadState") != "masked":
                _fail("BOOTSTRAP_SOURCE_OPEN", "Every old automatic entry requires a loaded persistent mask")
        elif value.get("LoadState") not in {"loaded", "not-found"}:
            _fail("BOOTSTRAP_UNKNOWN", "Controller definition cannot be observed")
        return value

    def _execution(self, bus, output, unit, old_boot=None):
        self.stopped(bus, unit)
        if _exists(Path(output) / "launch-intent.json") or _exists(Path(output) / "started.json"):
            if isinstance(old_boot, str) and re.fullmatch(r"[0-9a-f-]{36}", old_boot) and old_boot != startup.boot_id():
                # A new host boot closes old inherited channels and queued calls.
                # This is process closure, not a fabricated old task outcome.
                return
            # No task result/ledger revalidation: only closure of a possible
            # surviving call. Missing closure cannot be guessed from inactivity.
            proof = _read(Path(output) / "finished.json", self.owner)
            if type(proof.get("returncode")) is not int or proof.get("streams_eof") is not True:
                _fail("BOOTSTRAP_UNRESOLVED", "Original launcher has no closed delivery/collector record")

    def task_parents(self, bus, launch):
        """Controller exit alone does not prove its separately launched stages exited."""
        self.stopped(bus, launch["controller_envelope"]["controller"]["unit"])
        groups = {launch["policy"]["process_manager"]["cgroup"]}
        phases = launch["chain"]["phases"]
        if set(phases) != {"preflight", "business", "evidence"}:
            _fail("BOOTSTRAP_SCOPE", "Original phase declaration is incomplete")
        for phase in phases.values():
            for pin in (phase["grant"]["query_parent"], phase["grant"]["management_parent"],
                        phase["service"]["parent"], phase["peer"]["parent"]):
                groups.add(pin["path"])
        names = set()
        for name in groups:
            _path(name)
            path = name[len("/sys/fs/cgroup"):] if name.startswith("/sys/fs/cgroup/") else name
            if path == "/" or not path.endswith(".slice"):
                _fail("BOOTSTRAP_SCOPE", "Original task has an unsupported process parent")
            self.cgroup_empty({"ControlGroup": path})
            names.add(Path(path).name)
        jobs = bus.jobs()
        if len(jobs) > MAX_SCAN:
            _fail("BOOTSTRAP_SCAN_LIMIT", "System job inventory exceeds the observation bound")
        for job in jobs:
            self._budget()
            value = bus.unit(job[1])
            if value.get("Slice") in names or value.get("Id") in names:
                _fail("BOOTSTRAP_BUSY", "An original task stage still has a queued system job")

    def duties(self, bus, entry):
        if entry["kind"] == "prepared":
            raw = startup.protected_read(entry["launch_path"], owner_uid=self.owner, maximum=2 * 1024 * 1024)
            if hashlib.sha256(raw).hexdigest() != entry["launch_digest"]:
                _fail("BOOTSTRAP_CHANGED", "Original prepared declaration changed")
            launch = decode(raw)
            self.task_parents(bus, launch)
            self._execution(bus, entry["output"], entry["controller_unit"],
                            launch["controller_envelope"]["controller"].get("boot_id"))
            return {"kind": "prepared", "output": entry["output"]}
        root = Path(entry["records_root"])
        _directory(root, self.owner)
        records, attempts, fingerprints = 0, 0, []
        for directory in _children(root, MAX_SCAN):
            mode = directory.lstat().st_mode
            if stat.S_ISLNK(mode):
                _fail("BOOTSTRAP_SCOPE", "Legacy task inventory contains an aliased entry")
            if not stat.S_ISDIR(mode):
                continue
            if not _exists(directory / "current.json"):
                continue
            records += 1
            if records > MAX_RECORDS:
                _fail("BOOTSTRAP_SCAN_LIMIT", "Legacy task count exceeds its bound")
            record = _read(directory / "current.json", self.owner)
            if record.get("operation_id") != directory.name:
                _fail("BOOTSTRAP_SCOPE", "Original task identity differs from its retained directory")
            fingerprints.append(digest(record))
            current_attempt = Path(_path(record["attempt"]))
            if current_attempt.parent != directory:
                _fail("BOOTSTRAP_SCOPE", "Preparation attempt is outside its task directory")
            self.stopped(bus, record["prepare_unit"])
            if record.get("controller_unit"):
                self._execution(bus, _path(record["output"]), record["controller_unit"], record.get("boot_id"))
                self.task_parents(bus, _read(_path(record["launch_path"]), self.owner, 2 * 1024 * 1024))
            for attempt in _children(directory, MAX_SCAN):
                if not stat.S_ISDIR(attempt.lstat().st_mode):
                    continue
                attempts += 1
                if attempts > MAX_ATTEMPTS:
                    _fail("BOOTSTRAP_SCAN_LIMIT", "Legacy attempts exceed their bound")
                delivery = attempt / "preparation-delivery.json"
                if _exists(delivery):
                    proof_path = attempt / "preparation-exit.json"
                    proof = _read(proof_path, self.owner) if _exists(proof_path) else None
                    # A nonzero waiter can have left its unit behind. The exact
                    # unit is derived by the old fixed dispatcher from the serial.
                    data = _read(delivery, self.owner)
                    command = data.get("command", [])
                    names = [arg[len("--unit="):] for arg in command if isinstance(arg, str) and arg.startswith("--unit=")]
                    unit = names[0] if len(names) == 1 else None
                    if unit is None or (attempt == current_attempt and unit != record["prepare_unit"]):
                        _fail("BOOTSTRAP_UNRESOLVED", "Retained preparation lacks its exact unit binding")
                    self.stopped(bus, unit)
                    if (not isinstance(proof, dict) or type(proof.get("returncode")) is not int):
                        if record.get("boot_id") in (None, startup.boot_id()):
                            _fail("BOOTSTRAP_UNRESOLVED", "Preparation delivery is not closed")
                    fingerprints.append(digest({"delivery": data, "exit": proof}))
                output = attempt / "execution"
                if attempt != current_attempt and (_exists(output / "launch-intent.json") or _exists(output / "started.json")):
                    result = _read(attempt / "result.json", self.owner, 2 * 1024 * 1024)
                    launch = result["launch"]
                    self.task_parents(bus, launch)
                    self._execution(bus, output, launch["controller_envelope"]["controller"]["unit"],
                                    launch["controller_envelope"]["controller"].get("boot_id"))
        return {"records": records, "attempts": attempts, "digest": digest(fingerprints)}

    def verify_target(self, target, candidates=None):
        self.environment._verify_components(target["selection"], candidates)
        # Bootstrap imports the selected administrator/runtime projection. A
        # unit pointing to an older unguarded Python import tree is not adopted.
        actual = provenance.full_payload_digest(Path(__file__).parents[2])
        if any(component["payload_digest"] != actual for name, component in target["selection"]["components"].items()
               if self.profile["probes"][name]["kind"] != "gateway"):
            _fail("BOOTSTRAP_GUARD", "Compatibility payload is not this selected guarded implementation")

    def observe(self, entries, target):
        self.deadline = time.monotonic() + self.profile.get("timeout_seconds", 30)
        for entry in entries:
            if "configuration" in entry and digest(_read(entry["configuration"], self.owner, 2 * 1024 * 1024)) != entry["configuration_digest"]:
                _fail("BOOTSTRAP_CHANGED", "Original dispatch configuration changed")
        with self.bus_factory() as bus:
            old = {entry["unit"]: self.stopped(bus, entry["unit"], masked=True) for entry in entries}
            duties = [self.duties(bus, entry) for entry in entries if "lock" in entry]
            services = target.get("services", {})
            if set(services) != set(self.profile.get("systemd", {}).get("units", {})):
                _fail("BOOTSTRAP_SCOPE", "Every guarded service needs its exact stopped baseline")
            observed = {}
            for unit, desired in services.items():
                if unit in old or desired.get("running") is not False:
                    _fail("BOOTSTRAP_SCOPE", "Guarded compatibility services must use separate stopped names")
                value = self.stopped(bus, unit)
                if (value.get("LoadState") != "loaded" or value.get("NeedDaemonReload")
                        or value.get("UnitFileState") not in {"disabled", "static"}
                        or value["UnitFileState"] != desired.get("policy")):
                    _fail("BOOTSTRAP_PREPARATION_REQUIRED", "Install and load the separate stopped guarded definitions first")
                component = self.profile["systemd"]["units"][unit]["component"]
                guard = self.profile["guarded_components"][component]["configuration"]
                commands = value.get("ExecStart", [])
                args = commands[0][1] if len(commands) == 1 else []
                kind = self.profile["probes"][component]["kind"]
                flag = "--startup-config" if kind == "mcp" else "--config"
                module = {"resident": "admin.local_hand_system_manager.resident_service",
                          "prepared": "admin.local_hand_system_manager.prepared_service", "mcp": "local_hand_mcp.server"}.get(kind)
                if (module is None or "-m" not in args or args[args.index("-m") + 1:args.index("-m") + 2] != [module]
                        or flag not in args or args[args.index(flag) + 1:args.index(flag) + 2] != [guard]
                        or Path(commands[0][0]).resolve() != Path(sys.executable).resolve()
                        or "PYTHONPATH=" + str(Path(__file__).parents[2]) not in value.get("Environment", [])
                        or not ("-B" in args or "PYTHONDONTWRITEBYTECODE=1" in value.get("Environment", []))
                        or any(flag in args[:args.index("-m")] for flag in ("-I", "-E", "-c"))
                        or any(value.get(hook) for hook in HOOKS)
                        or value.get("WorkingDirectory", "") not in {"", "/"}
                        or any(item.startswith("PYTHONHOME=") for item in value.get("Environment", []))):
                    _fail("BOOTSTRAP_GUARD", "Actual guarded entry must load its exact selected configuration")
                observed[unit] = {"definition_digest": definition_digest(value), "policy": value["UnitFileState"]}
            managed = {item["component"] for item in self.profile.get("systemd", {}).get("units", {}).values()}
            if self.profile.get("gateway"):
                gateway = self.environment.gateway.observe()
                if gateway["kind"] != "absent" or target.get("gateway", {}).get("present") is not False:
                    _fail("BOOTSTRAP_PREPARATION_REQUIRED", "Import requires an absent old gateway; ordinary deployment creates its guarded replacement")
                managed.add(self.profile["gateway"]["component"])
            if managed != set(target["selection"]["components"]):
                _fail("BOOTSTRAP_SCOPE", "Every compatibility component requires an actual stopped entry binding")
            return {"legacy_units": sorted(old), "duties": duties, "guarded_units": observed}


def build_bootstrap_plan(manifest, observer=None):
    keys = {"schema", "request_id", "node_id", "legacy", "target", "files", "profile"}
    if (not isinstance(manifest, dict) or set(manifest) != keys or manifest["schema"] != MANIFEST_SCHEMA
            or len(canonical(manifest)) > 1024 * 1024):
        _fail("BOOTSTRAP_SCOPE", "Unknown offline import manifest")
    identity(manifest["request_id"]); identity(manifest["node_id"])
    target, profile = copy.deepcopy(manifest["target"]), copy.deepcopy(manifest["profile"])
    _selection(target, manifest["node_id"])
    validate_profile(profile, target, target)
    if any(component["running"] for component in target["selection"]["components"].values()):
        _fail("BOOTSTRAP_SCOPE", "The imported compatibility baseline must be completely stopped")
    owner = profile.get("owner_uid", 0)
    entries = _legacy(manifest["legacy"], owner)
    required = {probe["kind"] for probe in profile["probes"].values()} - {"gateway"}
    if not required.issubset({entry["kind"] for entry in entries}):
        _fail("BOOTSTRAP_SCOPE", "Every selected entry needs its explicit old admission source")
    if _exists(profile["startup_descriptor"]) or _exists(Path(profile["maintenance_directory"]) / "gate.json"):
        _fail("BOOTSTRAP_EXISTS", "An existing guarded selection must use ordinary deployment recovery")
    file_plan = files.plan_files(manifest["files"], limits=files.FileLimits(**profile.get("file_limits", {})), owner_uid=owner)
    members = {member["path"] for member in target["selection"]["members"]}
    if any(entry["target"] not in members or entry["source"] is None for entry in file_plan["files"]):
        _fail("BOOTSTRAP_SCOPE", "Offline import publishes only the complete selected configuration set")
    retained = {Path(entry[key]) for entry in entries for key in ("configuration", "launch_path", "lock", "socket", "records_root", "output") if key in entry}
    retained.update((Path(profile["startup_descriptor"]), Path(profile["maintenance_directory"])))
    if any(Path(entry["target"]) == path or path in Path(entry["target"]).parents
           for entry in file_plan["files"] for path in retained):
        _fail("BOOTSTRAP_SCOPE", "Import cannot overwrite old entry configuration, task records or coordination state")
    planned = {entry["target"]: entry for entry in file_plan["files"]}
    for guard in profile["guarded_components"].values():
        entry = planned.get(guard["configuration"])
        if entry is None or entry["original"]["exists"]:
            _fail("BOOTSTRAP_SCOPE", "Each new guarded entry needs a separately named, initially absent configuration")
    roots = [Path(path) for path in profile.get("systemd", {}).get("reload_scope", {}).get("roots", [])]
    if any(Path(entry["target"]) == root or root in Path(entry["target"]).parents
           for entry in file_plan["files"] for root in roots):
        _fail("BOOTSTRAP_SCOPE", "Guarded unit definitions are prepared offline, outside configuration import")
    observer = observer or OfflineObserver(profile)
    candidates = {entry["target"]: entry["source"]["path"] for entry in file_plan["files"]}
    observer.verify_target(target, candidates)
    with legacy_locks(entries, owner) as bindings:
        observation = observer.observe(entries, target)
    bootstrap = {"schema": MANIFEST_SCHEMA, "entries": entries, "locks": bindings, "observation": observation}
    source = {"deployment_digest": digest(bootstrap), "bootstrap": bootstrap}
    return seal_plan({"schema": PLAN_SCHEMA, "request_id": manifest["request_id"], "node_id": manifest["node_id"],
        "source": source, "target": target, "profile": profile,
        "steps": [{"id": f"step-{index:03d}", "kind": "file", "action": entry} for index, entry in enumerate(file_plan["files"])]})


def _stage(store, operation, step):
    path = store.root
    for part in ("operations", operation["id"], step["id"], "bootstrap"):
        path /= part
        path.mkdir(mode=0o700, exist_ok=True)
        _directory(path, store.owner_uid)
        info = path.lstat()
        if info.st_uid != store.owner_uid or stat.S_IMODE(info.st_mode) != 0o700:
            _fail("BOOTSTRAP_STATE", "Preparation directory is not private")
        startup._confirm_selection(path, owner_uid=store.owner_uid)
    return path


def _adopt_bootstrap(store, plan, *, observer=None, implementation=None):
    """Resume the same finite import. No new plan may erase a partial import."""
    validate_plan(plan)
    if not is_bootstrap(plan) or plan["node_id"] != store.node_id:
        _fail("BOOTSTRAP_SCOPE", "Expected this node's original offline import plan")
    profile, target = plan["profile"], plan["target"]
    owner = profile.get("owner_uid", 0)
    observer = observer or OfflineObserver(profile)
    binding = plan["source"]["bootstrap"]
    gate = MaintenanceGate(profile["maintenance_directory"], plan["node_id"], owner_uid=owner)
    with store.locked():
        if any(op["plan"]["request_id"] != plan["request_id"] for op in store.list(unfinished=True)):
            _fail("DEPLOYMENT_BUSY", "An unfinished operation must be resumed before importing a new baseline")
        operation = store.create(plan)
        if operation["released"]:
            return operation
        if operation["direction"] != "APPLY":
            return _rollback_locked(store, operation, observer)
        with legacy_locks(binding["entries"], owner, binding["locks"]):
            observation = observer.observe(binding["entries"], target)
            if observation != binding["observation"]:
                _fail("BOOTSTRAP_CHANGED", "Old duties or guarded definitions changed since the offline plan")
            operation["implementation"] = implementation
            operation["phase"] = "BOOTSTRAP_OFFLINE"
            store.save(operation, "BOOTSTRAP_OFFLINE_INTENT", {"legacy_sources_closed": True})
            # Prepare all backups before the first publication. A failed prepare
            # retains bounded partial objects; the file adapter never adopts them
            # as an unrecorded publication.
            for step, record in zip(plan["steps"], operation["steps"]):
                if record["prepared"] is None:
                    record["prepared"] = files.prepare_file(step["action"], _stage(store, operation, step),
                        operation_id=operation["id"], attempt_id=step["id"], lock_fd=store.lock_fd)
                    record["state"] = "PREPARED"
                    store.save(operation, "BOOTSTRAP_FILE_INTENT", {"step": step["id"]})
            # Preflight every retained identity before any further mutation.
            for record in operation["steps"]:
                if files.observe_file(record["prepared"])["state"] not in {"original", "target"}:
                    _fail("BOOTSTRAP_CHANGED", "A partially published compatibility file changed independently")
            for step, record in zip(plan["steps"], operation["steps"]):
                result = files.execute_file(record["prepared"], lock_fd=store.lock_fd)
                record.update(state="VERIFIED", observation=result,
                              effective=record["prepared"]["expected"] != record["prepared"]["desired"])
                store.save(operation, "BOOTSTRAP_FILE_VERIFIED", {"step": step["id"]})
            observer.verify_target(target)
            if observer.observe(binding["entries"], target) != binding["observation"]:
                _fail("BOOTSTRAP_CHANGED", "Old sources reopened before compatibility publication")
            if operation["decision"] is None:
                operation.update(decision="COMMITTED", decision_id="bootstrap-" + digest({"operation": operation["id"], "target": target})[:32],
                                 phase="BOOTSTRAP_DECIDED")
                operation["checks"]["local"] = {"passed": True, "kind": "OFFLINE_COMPATIBILITY_IMPORT",
                    "services_started": False, "business_replayed": False}
                store.save(operation, "BOOTSTRAP_DECISION")
            selection = copy.deepcopy(target["selection"])
            selection.update(decision_id=operation["decision_id"], owner=None, mode="stable", permit=None)
            # The decision and all closed-source evidence precede OPEN. OPEN
            # admits no old process, and every selected guarded component is
            # explicitly stopped. The next ordinary operation starts services.
            gate.initialize(selection["deployment_digest"], selection["decision_id"], bootstrap=True)
            if _exists(profile["startup_descriptor"]):
                # Lost response after initial publication: exact same stopped
                # decision only; do not relax ordinary stable publication's CAS.
                with gate.admission_lock() as state:
                    if (state["state"] != "OPEN" or state["sequence"] != 1
                            or state["decision_id"] != selection["decision_id"]
                            or startup.read_selection(profile["startup_descriptor"], owner_uid=owner) != selection):
                        _fail("BOOTSTRAP_CHANGED", "The imported startup decision was independently changed")
                    startup.verify_members(selection, owner_uid=owner)
                    startup._confirm_selection(profile["startup_descriptor"], owner_uid=owner)
            else:
                startup.publish(profile["startup_descriptor"], selection, gate, expected_digest=None, owner_uid=owner)
            operation["startup"]["current"] = selection
            operation.update(released=True, phase="COMPLETE", waiting=None)
            store.save(operation, "BOOTSTRAP_RELEASED")
            return operation


def _rollback_locked(store, operation, observer):
    plan = operation["plan"]
    binding, profile = plan["source"]["bootstrap"], plan["profile"]
    if operation["decision"] == "COMMITTED":
        _fail("BOOTSTRAP_COMPATIBILITY_BASELINE", "A committed guarded import cannot roll back to an unguarded release")
    with legacy_locks(binding["entries"], profile.get("owner_uid", 0), binding["locks"]):
        if observer.observe(binding["entries"], plan["target"]) != binding["observation"]:
            _fail("BOOTSTRAP_CHANGED", "Original closed sources changed before isolated compensation")
        operation.update(direction="ROLLBACK", phase="BOOTSTRAP_RESTORING")
        store.save(operation, "BOOTSTRAP_ROLLBACK_INTENT", recovery=True)
        # Once a separate restore action exists, its new object identity is the
        # current chain. Never re-observe an already restored publication object.
        for step, record in reversed(list(zip(plan["steps"], operation["steps"]))):
            current = record["restore"] or record["prepared"]
            if current and files.observe_file(current)["state"] not in {"original", "target"}:
                _fail("BOOTSTRAP_CHANGED", "A compatibility object changed before compensation")
        for step, record in reversed(list(zip(plan["steps"], operation["steps"]))):
            if not record["prepared"]:
                continue
            if record["restore"] is None:
                directory = _stage(store, operation, {"id": step["id"] + "-restore"})
                record["restore"] = files.prepare_restore(record["prepared"], directory,
                    operation_id=operation["id"], attempt_id=step["id"] + "-restore", lock_fd=store.lock_fd)
                store.save(operation, "BOOTSTRAP_RESTORE_INTENT", {"step": step["id"]}, recovery=True)
            record["restore_observation"] = files.execute_file(record["restore"], lock_fd=store.lock_fd)
            record["state"] = "RESTORED"
            store.save(operation, "BOOTSTRAP_RESTORED", {"step": step["id"]}, recovery=True)
        operation.update(decision="ROLLED_BACK", decision_id="isolated-" + operation["id"], phase="COMPLETE", released=True, waiting=None)
        operation["checks"]["restored"] = {"passed": True, "kind": "ISOLATED_LEGACY_FILES",
            "admission_opened": False, "legacy_masks_retained": True, "services_started": False}
        store.save(operation, "BOOTSTRAP_ISOLATED", recovery=True)
        return operation


def _failed(store, plan, error):
    """Retain a bounded error without masking the original persistence failure."""
    try:
        with store.locked():
            operation = store.get(operation_id(plan["request_id"]))
            if operation["plan"]["digest"] != plan["digest"] or operation["released"]:
                raise error
            category = "recovery" if operation["direction"] == "ROLLBACK" else "primary"
            detail = {"code": str(getattr(error, "code", type(error).__name__))[:128], "phase": operation["phase"]}
            if len(operation["errors"][category]) < 64:
                operation["errors"][category].append(detail)
            operation["waiting"] = {"reason": "BOOTSTRAP_NOT_COMPLETED", "resume": operation["id"]}
            store.save(operation, "BOOTSTRAP_WAITING", detail, recovery=True)
            return operation
    except (OSError, RuntimeError, ValueError, JobError):
        raise error


def adopt_bootstrap(store, plan, *, observer=None, implementation=None):
    validate_plan(plan)
    if not is_bootstrap(plan):
        _fail("BOOTSTRAP_SCOPE", "Expected an offline import plan")
    try:
        return _adopt_bootstrap(store, plan, observer=observer, implementation=implementation)
    except (OSError, RuntimeError, ValueError, JobError) as error:
        return _failed(store, plan, error)


def rollback_bootstrap(store, operation_id, *, observer=None):
    operation = store.get(operation_id)
    if not is_bootstrap(operation["plan"]):
        _fail("BOOTSTRAP_SCOPE", "Expected an offline import operation")
    if operation["decision"] == "COMMITTED":
        _fail("BOOTSTRAP_COMPATIBILITY_BASELINE", "Use ordinary deployment from the imported guarded baseline")
    observer = observer or OfflineObserver(operation["plan"]["profile"])
    try:
        with store.locked():
            operation = store.get(operation_id)
            if operation["released"]:
                return operation
            return _rollback_locked(store, operation, observer)
    except (OSError, RuntimeError, ValueError, JobError) as error:
        return _failed(store, operation["plan"], error)
