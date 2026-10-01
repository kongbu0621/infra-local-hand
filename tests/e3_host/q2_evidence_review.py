"""Read-only, offline consistency review of retained Q2 controller evidence.

Both directories and the expected seal digest must come from the caller. Paths
inside artifacts are compared as data, never opened. This reviewer neither runs
artifact code nor establishes host provenance, live state, full phase evidence,
physical peak capacity or the supervisor's own independent exit. Byte/count
bounds do not guarantee that filesystem I/O will return on a faulty device.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from types import ModuleType

SCHEMA = "local-hand-q2-offline-evidence-review/v1"
SCOPE = "OFFLINE_TARGET_CONTROLLER_ARTIFACT_CONSISTENCY_ONLY"
OUTPUT = frozenset(("reservation.json", "delivery.json", "invocation.json", "controller.stdout",
                    "controller.stderr", "capture.json", "stop.json", "controls.json",
                    "controller-result.json", "result.json"))
DECLARATIONS = frozenset(("supervisor.json", "launcher.json", "controller-result.json"))
FILE_LIMIT = 2 * 1024 * 1024
TOTAL_LIMIT = 6 * 1024 * 1024
RECORD_LIMIT = 131072
SEAL_LIMIT = 65536
PIPE_LIMIT = 32768
COST_KEYS = frozenset(("storage_bytes", "storage_inodes", "cpu_ns", "memory_bytes", "pids", "output_bytes"))
DYNAMIC = frozenset(("invocation_id", "cgroup_device", "cgroup_inode"))
CANCEL_PURPOSE = "ISOLATED_Q4_CANCEL_HELPER"
CANCEL_LAUNCHER = "local-hand-q4-cancel-launcher/v1"
CANCEL_SUPERVISOR = "local-hand-q4-cancel-supervisor/v1"
SYSTEM_SUPERVISOR = "local-hand-q2-system-supervisor/v1"
SYSTEM_LAUNCHER = "local-hand-q2-system-launcher/v1"
SYSTEM_WIRE_LIMIT = 4 * 1024 * 1024


def require(ok, code):
    if not ok:
        raise ValueError(code)


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value < 2**63, "REVIEW_INTEGER")
    return value


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def token(value, pattern, code):
    require(type(value) is str and re.fullmatch(pattern, value) is not None, code)
    return value


def keys(value, expected, code="REVIEW_SCHEMA"):
    require(type(value) is dict and set(value) == set(expected), code)


def cancel_fixture(fixture):
    """Reject cross-scenario wrappers before interpreting any retained status."""
    pair = fixture.get("schema"), fixture.get("purpose")
    require(pair in (("local-hand-q2-supervisor/v1", "ISOLATED_Q2_SUPERVISION"),
                     (SYSTEM_SUPERVISOR, "ISOLATED_Q2_SUPERVISION"),
                     (CANCEL_SUPERVISOR, CANCEL_PURPOSE)), "REVIEW_FIXTURE_VERSION")
    nested = fixture["launcher"]
    cancel = pair == (CANCEL_SUPERVISOR, CANCEL_PURPOSE)
    require(cancel == (nested.get("schema") == CANCEL_LAUNCHER), "REVIEW_SCENARIO_BINDING")
    system = pair[0] == SYSTEM_SUPERVISOR
    require(system == (nested.get("schema") == SYSTEM_LAUNCHER), "REVIEW_MANAGER_BINDING")
    if system:
        require(nested.get("purpose") == "ISOLATED_Q2_CHAIN", "REVIEW_LAUNCHER_VERSION")
    if cancel:
        require(nested.get("purpose") == CANCEL_PURPOSE, "REVIEW_LAUNCHER_VERSION")
    return cancel


def system_fixture(fixture):
    cancel_fixture(fixture)
    return fixture["schema"] == SYSTEM_SUPERVISOR


def record_schema(cancel, suffix, *, system=False):
    require(type(cancel) is bool and type(system) is bool and not (cancel and system), "REVIEW_RECORD_KIND")
    return ("local-hand-q4-cancel-" if cancel else "local-hand-q2-system-" if system
            else "local-hand-q2-") + suffix + "/v1"


def case_contract():
    """Load this reviewer's fixed local decoder, never a path from evidence."""
    path = Path(__file__).with_name("q4_cancel_case.py")
    with path.open("rb") as source:
        raw = source.read(FILE_LIMIT + 1)
    require(len(raw) <= FILE_LIMIT, "REVIEW_DECODER_LIMIT")
    module = ModuleType("_q4_cancel_offline_contract")
    module.__file__ = str(path)
    # Compile retained local bytes explicitly; a read-only review must not
    # create a .pyc cache even when its caller omitted Python's -B option.
    exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def cancel_case_facts(result, fixture, completed_ns=None):
    """Bind a recorded case to its fixture; recording proves no task closure."""
    require(cancel_fixture(fixture), "REVIEW_CANCEL_FIXTURE")
    nested = fixture["launcher"]; resident = nested["resident"]; assembly = nested["assembly"]
    require(resident.get("schema") == "local-hand-q4-cancel-resident/v1"
            and resident.get("purpose") == CANCEL_PURPOSE and resident.get("phases") == ["preflight"],
            "REVIEW_CANCEL_RESIDENT")
    require(result.get("schema") == "local-hand-q4-cancel-launcher-result/v1"
            and result.get("status") == "CANCEL_CASE_RECORDED"
            and result.get("q3_accepted") is False and result.get("production_supported") is False
            and result.get("ordinary_phase_closed") is False
            and result.get("independent_ordinary_cleanup_required") is True,
            "REVIEW_CANCEL_SCOPE")
    entry = absolute(resident["entry"]["path"])
    suffix = "/tests/e3_host/q2_resident.py"
    require(entry.endswith(suffix), "REVIEW_SOURCE_ENTRY_LAYOUT")
    relative = "tests/e3_host/q4_cancel_case.py"
    pin = resident["cancel_case"]
    keys(pin, ("path", "sha256"), "REVIEW_CANCEL_SOURCE")
    require(pin["path"] == entry[:-len(suffix)] + "/" + relative
            and pin["sha256"] == nested["source"]["files"].get(relative), "REVIEW_CANCEL_SOURCE")
    token(pin["sha256"], r"[0-9a-f]{64}", "REVIEW_CANCEL_SOURCE")
    case = result.get("case")
    contract = case_contract()
    require(not contract.validate_report(case), "REVIEW_CANCEL_REPORT")
    require(case["ready_for_finish"] is True and case["chain_closed"] is False, "REVIEW_CANCEL_UNFINISHED")
    request = resident["request"]
    require(case["operation_id"] == request["operation_id"] and case["request_digest"] == request["request_digest"]
            and case["principal_id"] == resident["principal"]["principal_id"] and case["phase"] == "preflight"
            and case["target_execution_id"] == assembly["grant"]["allocation"]["execution_id"]
            and case["boot_id"] == assembly["installation"]["capacity"]["boot_id"], "REVIEW_CANCEL_BINDING")
    for observation in ([case["trigger"], case["helper"]] + case["stops"]):
        identity = observation.get("identity") if observation is not None else None
        if identity is not None:
            require(identity["cgroup"] == resident["ordinary"]["parent"]["path"] + "/" + identity["unit"],
                    "REVIEW_CANCEL_PARENT")
    envelope = nested["controller_envelope"]
    require(envelope["issued_ns"] <= case["observed_ns"] < envelope["deadline_ns"]
            and (completed_ns is None or case["observed_ns"] <= completed_ns), "REVIEW_CANCEL_TIME")
    return case


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "REVIEW_DUPLICATE_KEY")
            value[key] = item
        return value

    def forbidden(_):
        raise ValueError("REVIEW_NUMBER")

    value = json.loads(raw, object_pairs_hook=unique, parse_constant=forbidden, parse_float=forbidden)
    remaining = [60000]
    def finite(item, depth=0):
        remaining[0] -= 1
        require(depth <= 32 and remaining[0] >= 0, "REVIEW_STRUCTURE_LIMIT")
        if type(item) is dict:
            for key, child in item.items():
                require(len(key) <= 4096, "REVIEW_STRING_LIMIT")
                finite(child, depth + 1)
        elif type(item) is list:
            for child in item: finite(child, depth + 1)
        elif type(item) is int:
            require(-(2**63) <= item < 2**63, "REVIEW_INTEGER")
        else:
            require(item is None or type(item) in (bool, str), "REVIEW_VALUE")
            if type(item) is str: require(len(item) <= FILE_LIMIT, "REVIEW_STRING_LIMIT")
    finite(value)
    return value


def absolute(value):
    require(type(value) is str and 1 < len(value) <= 4096 and value.startswith("/")
            and not value.startswith("//") and str(PurePosixPath(value)) == value
            and ".." not in PurePosixPath(value).parts, "REVIEW_ABSOLUTE_PATH")
    return value


def fingerprint(info):
    return tuple(getattr(info, field) for field in
                 ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))


class Directory:
    """Open only caller-selected directories; all child names are constants."""
    def __init__(self, path, names):
        absolute(path)
        require(os.name == "posix" and hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd,
                "REVIEW_NOFOLLOW_UNSUPPORTED")
        self.fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        self.names = frozenset(names); self.members = {}; self.identity = None
        try:
            for component in PurePosixPath(path).parts[1:]:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=self.fd)
                os.close(self.fd); self.fd = child
            self.identity = fingerprint(os.fstat(self.fd))
            self.check_names()
        except Exception:
            os.close(self.fd); self.fd = None
            raise

    def check_names(self):
        found = set()
        with os.scandir(self.fd) as entries:
            for entry in entries:
                require(len(found) < len(self.names) and entry.name in self.names,
                        "REVIEW_DIRECTORY_MEMBERS")
                found.add(entry.name)
        require(found == self.names, "REVIEW_DIRECTORY_MEMBERS")

    def read(self, name, maximum):
        require(name in self.names and name not in self.members, "REVIEW_FIXED_MEMBER")
        before = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and not before.st_mode & 0o6000,
                "REVIEW_REGULAR_SINGLE_LINK_REQUIRED")
        require(before.st_size <= maximum, "REVIEW_FILE_LIMIT")
        child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=self.fd)
        try:
            require(fingerprint(os.fstat(child)) == fingerprint(before), "REVIEW_MEMBER_CHANGED")
            raw = bytearray()
            while len(raw) <= maximum:
                block = os.read(child, min(65536, maximum + 1 - len(raw)))
                if not block: break
                raw.extend(block)
            require(len(raw) <= maximum and len(raw) == before.st_size, "REVIEW_FILE_LIMIT")
            require(fingerprint(os.fstat(child)) == fingerprint(before), "REVIEW_MEMBER_CHANGED")
            self.members[name] = (child, fingerprint(before))
            return bytes(raw)
        except Exception:
            os.close(child)
            raise

    def stable(self):
        self.check_names()
        require(fingerprint(os.fstat(self.fd)) == self.identity, "REVIEW_DIRECTORY_CHANGED")
        for name, (fd, identity) in self.members.items():
            require(fingerprint(os.fstat(fd)) == identity
                    and fingerprint(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) == identity,
                    "REVIEW_MEMBER_CHANGED")

    def close(self):
        for fd, _ in self.members.values(): os.close(fd)
        if self.fd is not None: os.close(self.fd)


def limited_scope(value, *, stop):
    require(type(value) is dict and value.get("q3_accepted") is False
            and value.get("production_supported") is False and value.get(stop) is True, "REVIEW_SCOPE")


def identity(value):
    keys(value, ("invocation_id", "pid", "cgroup_device", "cgroup_inode"), "REVIEW_ORIGINAL_IDENTITY")
    token(value["invocation_id"], r"[0-9a-f]{32}", "REVIEW_INVOCATION")
    for name in ("pid", "cgroup_inode"): integer(value[name], 1)
    integer(value["cgroup_device"])
    return value


def timespan(value):
    require(type(value) is str and 0 < len(value) <= 64, "REVIEW_MANAGER_TIME")
    if value == "0": return 0
    total, previous = 0, 60_000_001
    for part in value.split(" "):
        match = re.fullmatch(r"(0|[1-9][0-9]{0,8})(?:\.([0-9]{1,6}))?(min|ms|us|s)", part)
        require(match is not None, "REVIEW_MANAGER_TIME")
        whole, fraction, suffix = match.groups(); scale = {"min": 60000000, "s": 1000000, "ms": 1000, "us": 1}[suffix]
        require(scale < previous, "REVIEW_MANAGER_TIME"); previous = scale
        total += int(whole) * scale
        if fraction is not None:
            numerator, denominator = int(fraction) * scale, 10**len(fraction)
            require(numerator % denominator == 0, "REVIEW_MANAGER_TIME")
            total += numerator // denominator
        require(total <= 120000000, "REVIEW_MANAGER_TIME")
    return total


def running(values, static, original):
    expected = dict(Id=static["unit"], LoadState="loaded", ActiveState="active", SubState="running",
        InvocationID=original["invocation_id"], ControlGroup=static["cgroup"], MainPID=str(original["pid"]),
        ControlPID="0", Slice=PurePosixPath(static["cgroup"]).parent.name, Type="exec", ExitType="cgroup",
        RemainAfterExit="no", Restart="no", RestartForceExitStatus="", KillMode="control-group", SendSIGKILL="yes",
        FinalKillSignal="9", NotifyAccess="none", ExecStartPre="", ExecStartPost="", ExecStop="", ExecStopPost="",
        ExecReload="", TriggeredBy="", OnFailure="", OnSuccess="", TimeoutStopFailureMode="kill", MemorySwapMax="0",
        User="root", Group="root", NoNewPrivileges="yes", AmbientCapabilities="")
    require(type(values) is dict and all(values.get(key) == item for key, item in expected.items())
            and values.get("Job") in ("", "0"), "REVIEW_RUNNING_PROPERTIES")
    require(type(values.get("CapabilityBoundingSet")) is str and set(values["CapabilityBoundingSet"].split()) ==
            {"cap_dac_read_search", "cap_setgid", "cap_setuid", "cap_setpcap", "cap_sys_admin"}, "REVIEW_RUNNING_CAPABILITIES")
    for name, wanted in (("RuntimeMaxUSec", static["runtime_max_usec"]), ("RuntimeRandomizedExtraUSec", 0),
                         ("TimeoutStopUSec", static["timeout_stop_usec"]), ("CPUQuotaPerSecUSec", static["cpu_quota_per_sec_usec"])):
        require(timespan(values.get(name)) == wanted, "REVIEW_RUNNING_LIMITS")
    for name, wanted in (("MemoryMax", static["memory_bytes"]), ("TasksMax", static["tasks_max"]),
                         ("LimitCPU", static["limit_cpu_seconds"]), ("LimitCPUSoft", static["limit_cpu_seconds"])):
        require(values.get(name) == str(wanted), "REVIEW_RUNNING_LIMITS")


def management_facts(records, stop, static):
    require(type(records) is list and 5 <= len(records) <= 16, "REVIEW_CONTROL_COUNT")
    decoded = []; total = 0
    for record in records:
        keys(record, ("arguments", "stdout_hex", "stderr_hex", "returncode", "eof", "error", "complete"))
        require(record["complete"] is True and type(record["returncode"]) is int and record["returncode"] == 0
                and record["eof"] == ["stderr", "stdout"] and record["error"] is None
                and record["stderr_hex"] == "", "REVIEW_CONTROL_CAPTURE")
        raw = bytes.fromhex(token(record["stdout_hex"], r"(?:[0-9a-f]{2}){0,32768}", "REVIEW_CONTROL_BYTES"))
        total += len(raw); require(total <= PIPE_LIMIT, "REVIEW_CONTROL_BYTES")
        args = record["arguments"]
        require(type(args) is list and all(type(arg) is str for arg in args), "REVIEW_CONTROL_ARGUMENTS")
        if args == ["stop", static["unit"]]:
            require(raw == b"", "REVIEW_STOP_OUTPUT"); decoded.append(None)
        else:
            require(len(args) == 4 and args[:3] == ["show", static["unit"], "--all"]
                    and args[3].startswith("--property="), "REVIEW_CONTROL_ARGUMENTS")
            rows = raw.decode("ascii").splitlines(); values = {}
            for row in rows:
                name, separator, val = row.partition("=")
                require(separator and name not in values, "REVIEW_MANAGER_FORMAT"); values[name] = val
            for name in ("ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost", "ExecReload"):
                values.setdefault(name, "")
            require(set(values) == set(args[3][11:].split(",")), "REVIEW_MANAGER_FIELDS")
            decoded.append(values)
    stops = [index for index, item in enumerate(decoded) if item is None]
    require(len(stops) == 1 and 2 <= stops[0] == len(decoded) - 2, "REVIEW_ORIGINAL_STOP_ORDER")
    require(decoded[stops[0] - 1] == stop["before"] and decoded[-1] == stop["after"], "REVIEW_STOP_RECORD_BINDING")
    initial = decoded[0]
    require(initial.get("Id") == static["unit"] and initial.get("LoadState") == "not-found"
            and initial.get("Job") in ("", "0"), "REVIEW_TARGET_ALREADY_EXISTED")
    return decoded


def system_geometry_facts(fixture):
    """Check recorded new geometry only; no claim about current host admission."""
    require(system_fixture(fixture), "REVIEW_SYSTEM_FIXTURE")
    nested = fixture["launcher"]; resident = nested["resident"]
    require((resident.get("schema"), resident.get("purpose"), resident.get("phases")) ==
            ("local-hand-q2-system-resident/v1", "ISOLATED_Q2_CHAIN", ["preflight", "business", "evidence"]),
            "REVIEW_SYSTEM_RESIDENT")
    ordinary = resident["ordinary"]; geometry = nested.get("system_geometry")
    keys(geometry, ("schema", "controller_parent", "ordinary_parent", "retained_ordinary_parent"),
         "REVIEW_SYSTEM_GEOMETRY")
    require(geometry["schema"] == "local-hand-q2-system-geometry/v1", "REVIEW_SYSTEM_GEOMETRY")
    for name, memory, tasks in (("controller_parent", 512 * 1024**2, 64),
                                ("ordinary_parent", 256 * 1024**2, 32),
                                ("retained_ordinary_parent", 256 * 1024**2, 64)):
        record = geometry[name]
        keys(record, ("parent", "memory_bytes", "tasks_max", "cpu_quota_per_sec_usec", "memory_swap_max"),
             "REVIEW_SYSTEM_PARENT_BUDGET")
        keys(record["parent"], ("path", "device", "inode"), "REVIEW_SYSTEM_PARENT")
        absolute(record["parent"]["path"])
        integer(record["parent"]["device"]); integer(record["parent"]["inode"], 1)
        require(all(type(record[key]) is int and record[key] == wanted for key, wanted in
                    (("memory_bytes", memory), ("tasks_max", tasks), ("cpu_quota_per_sec_usec", 1_000_000),
                     ("memory_swap_max", 0))), "REVIEW_SYSTEM_PARENT_BUDGET")
    outer = geometry["controller_parent"]["parent"]
    child = geometry["ordinary_parent"]["parent"]
    old = geometry["retained_ordinary_parent"]["parent"]
    require(outer == fixture["controller_parent"] and outer["path"] == "/lhqq2controller.slice"
            and child == ordinary["parent"] and str(PurePosixPath(child["path"]).parent) == outer["path"]
            and re.fullmatch(r"lhqq2controller-[a-z0-9_]+\.slice", PurePosixPath(child["path"]).name),
            "REVIEW_SYSTEM_PARENT_GEOMETRY")
    uid = integer(ordinary["uid"], 1)
    require(old["path"] == "/user.slice/user-" + str(uid) + ".slice/user@" + str(uid)
            + ".service/lhqq2ordinary.slice"
            and len({(pin["device"], pin["inode"]) for pin in (outer, child, old)}) == 3,
            "REVIEW_SYSTEM_RETAINED_PARENT")
    target = nested["controller_envelope"]["controller"]
    require(str(PurePosixPath(target["cgroup"]).parent) == outer["path"]
            and target["cgroup"] != child["path"] and target["cgroup"] == ordinary["broker_cgroup"],
            "REVIEW_SYSTEM_SIBLING_GEOMETRY")
    require(all(type(target[key]) is int and target[key] == wanted for key, wanted in
                (("memory_bytes", 256 * 1024**2), ("tasks_max", 32), ("cpu_quota_per_sec_usec", 1_000_000),
                 ("runtime_max_usec", 85_000_000), ("timeout_stop_usec", 1_000_000), ("limit_cpu_seconds", 85))),
            "REVIEW_SYSTEM_TARGET_BUDGET")
    binding = ordinary.get("manager_binding")
    keys(binding, ("schema", "manager_kind", "authority_id", "boot_id", "parent"), "REVIEW_SYSTEM_BINDING")
    require(binding["schema"] == "local-hand-manager-binding/v1" and binding["manager_kind"] == "system"
            and binding["parent"] == child
            and binding["boot_id"] == nested["assembly"]["installation"]["capacity"]["boot_id"],
            "REVIEW_SYSTEM_BINDING")
    token(binding["authority_id"], r"[a-z0-9][a-z0-9._-]{0,127}", "REVIEW_SYSTEM_BINDING")
    for phase in ("preflight", "business", "evidence"):
        require(nested["assembly"]["phases"][phase]["peer"]["parent"] == child, "REVIEW_SYSTEM_PHASE_PARENT")
    return geometry


def capacity_facts(fixture, reservation, member_bytes):
    nested = fixture["launcher"]; assembly = nested["assembly"]
    cancel = cancel_fixture(fixture)
    if cancel:
        require(assembly.get("schema") == "local-hand-q2-assembly/v1"
                and assembly.get("purpose") == "ISOLATED_Q2_PREFLIGHT", "REVIEW_CANCEL_ASSEMBLY")
        phase_grants = [assembly["grant"]]; status = "CANCEL_CASE_RECORDED"
    elif nested["schema"] == "local-hand-q2-launcher/v1":
        require(nested["purpose"] == "ISOLATED_Q2_PREFLIGHT", "REVIEW_LAUNCHER_VERSION")
        phase_grants = [assembly["grant"]]; status = "PREFLIGHT_CLOSED"
    else:
        require(nested["schema"] in ("local-hand-q2-launcher/v2", SYSTEM_LAUNCHER)
                and nested["purpose"] == "ISOLATED_Q2_CHAIN",
                "REVIEW_LAUNCHER_VERSION")
        keys(assembly["phases"], ("preflight", "business", "evidence"))
        phase_grants = [assembly["phases"][phase]["grant"] for phase in ("preflight", "business", "evidence")]
        status = "CHAIN_CLOSED"
    capacity = assembly["installation"]["capacity"]
    require(capacity["schema"] == "local-hand-quota-capacity/v1", "REVIEW_CAPACITY_SCHEMA")
    keys(capacity["management"], COST_KEYS); keys(reservation["capacity_costs"], COST_KEYS)
    costs = dict.fromkeys(COST_KEYS, 0)
    for grant in phase_grants:
        management = grant["management"]
        require(management["capacity_digest"] == digest(encoded(capacity).rstrip(b"\n")), "REVIEW_CAPACITY_BINDING")
        keys(management["stages"], ("admission", "query", "collector"))
        for name in COST_KEYS:
            costs[name] += integer(management[name], 1) if name.startswith("storage_") else sum(
                integer(item[name], 1) for item in management["stages"].values())
    for env, extra in ((nested["controller_envelope"], (len(phase_grants) - 1) * PIPE_LIMIT
                       + PIPE_LIMIT + (PIPE_LIMIT if cancel else 4096)),
                       (fixture["supervisor_envelope"], 2 * PIPE_LIMIT + 4096)):
        spec = env["controller"]
        for name in ("storage_bytes", "storage_inodes"): costs[name] += integer(env[name], 1)
        require(env["output_bytes"] == PIPE_LIMIT and type(env["output_bytes"]) is int, "REVIEW_OUTPUT_BUDGET")
        costs["cpu_ns"] += ((integer(spec["runtime_max_usec"], 1) + integer(spec["timeout_stop_usec"], 1) + 1000000)
                            * integer(spec["cpu_quota_per_sec_usec"], 1) + 999) // 1000
        costs["memory_bytes"] += integer(spec["memory_bytes"], 1)
        costs["pids"] += integer(spec["tasks_max"], 1)
        costs["output_bytes"] += PIPE_LIMIT + extra
    if system_fixture(fixture):
        system_geometry_facts(fixture)
        # The gateway is inside the existing target process/memory envelope;
        # its bounded control bytes are charged once, separately from captures.
        costs["output_bytes"] += SYSTEM_WIRE_LIMIT
    require(costs == reservation["capacity_costs"], "REVIEW_CAPACITY_COSTS")
    for key in COST_KEYS:
        integer(reservation["capacity_costs"][key])
        require(integer(costs[key]) <= integer(capacity["management"][key], 1), "REVIEW_CAPACITY_EXCEEDED")
    domains = capacity["domains"]
    require(type(domains) is list and 0 < len(domains) <= 128, "REVIEW_DOMAINS")
    seen = set()
    for domain in domains:
        pair = (domain["filesystem_uuid"], integer(domain["project_id"], 1))
        require(pair not in seen, "REVIEW_DUPLICATE_DOMAIN"); seen.add(pair)
    for kind, extra in (("bytes", 131072), ("inodes", 4)):
        used = integer(capacity["retained_" + kind]) + integer(capacity["management"]["storage_" + kind], 1) + extra
        used += sum(integer(domain["hard_" + kind], 1) for domain in domains)
        require(used <= integer(capacity["ceiling_" + kind], 1), "REVIEW_GLOBAL_CAPACITY")
    require(member_bytes <= fixture["supervisor_envelope"]["storage_bytes"], "REVIEW_SEALED_STORAGE")
    require(fixture["supervisor_envelope"]["storage_inodes"] >= len(OUTPUT) + len(DECLARATIONS) + 3,
            "REVIEW_SEALED_INODES")
    return status, capacity


def delivery_digest(fixture, fixture_sha, *, cpu_quota_format=None):
    """Reconstruct the recorded encoding; legacy bytes are never rewritten."""
    nested = fixture["launcher"]; spec = nested["controller_envelope"]["controller"]
    programs = nested["assembly"]["installation"]["programs"]
    entry = absolute(nested["resident"]["entry"]["path"])
    suffix = "/tests/e3_host/q2_resident.py"
    require(entry.endswith(suffix), "REVIEW_SOURCE_ENTRY_LAYOUT")
    repository = entry[:-len(suffix)]
    absolute(repository)
    rate = integer(spec["cpu_quota_per_sec_usec"], 1000)
    if cpu_quota_format is None:
        # Historical producer emitted four decimal places, including zeros.
        # Keep its digest reproducible even though systemd rejected that text.
        quota = str(rate // 10000) + "." + f"{rate % 10000:04d}" + "%"
    else:
        require(cpu_quota_format == "systemd-percent-hundredths/v1", "REVIEW_CPU_QUOTA_FORMAT")
        require(rate <= 1000000 and rate % 100 == 0, "REVIEW_CPU_QUOTA_PRECISION")
        quota = f"{rate // 10000}.{rate // 100 % 100:02d}".rstrip("0").rstrip(".") + "%"
    properties = dict(User="root", Group="root", Slice=PurePosixPath(spec["cgroup"]).parent.name,
        Type="exec", ExitType="cgroup", RemainAfterExit="no", Restart="no", RestartForceExitStatus="",
        KillMode="control-group", SendSIGKILL="yes", FinalKillSignal="SIGKILL", NotifyAccess="none",
        ExecStartPre="", ExecStartPost="", ExecStop="", ExecStopPost="", ExecReload="", OnFailure="", OnSuccess="",
        RuntimeMaxSec=str(spec["runtime_max_usec"]) + "us", RuntimeRandomizedExtraSec="0",
        TimeoutStopSec=str(spec["timeout_stop_usec"]) + "us", TimeoutStopFailureMode="kill",
        MemoryMax=str(spec["memory_bytes"]), MemorySwapMax="0", TasksMax=str(spec["tasks_max"]),
        CPUQuota=quota,
        CPUQuotaPeriodSec="100ms", LimitCPU=str(spec["limit_cpu_seconds"]), UMask="0077", WorkingDirectory="/",
        NoNewPrivileges="yes", CapabilityBoundingSet="CAP_DAC_READ_SEARCH CAP_SETGID CAP_SETUID CAP_SETPCAP CAP_SYS_ADMIN",
        AmbientCapabilities="", StandardInput="null")
    argv = [programs["systemd_run"]["path"], "--system", "--quiet", "--wait", "--pipe", "--no-ask-password",
        "--unit=" + spec["unit"], *("--property=" + key + "=" + val for key, val in properties.items()), "--",
        programs["python"]["path"], "-I", "-B", repository + "/tests/e3_host/q2_supervisor.py", "--controller",
        "--fixture", fixture["declarations"]["path"] + "/supervisor.json", "--sha256", fixture_sha]
    return digest(encoded(argv))


def facts(output, declarations, seal, member_bytes):
    fixture = decode(declarations["supervisor.json"])
    keys(fixture, ("schema", "purpose", "launcher", "controller_parent", "supervisor_envelope", "output", "declarations"))
    cancel = cancel_fixture(fixture)
    system = system_fixture(fixture)
    require(seal.get("schema") == record_schema(cancel, "controller-seal", system=system)
            and seal.get("scope") == "TARGET_CONTROLLER_CLOSURE_ONLY" and seal.get("status") == "CONTROLLER_CLOSED",
            "REVIEW_SEAL_SCOPE")
    keys(seal, ("schema", "scope", "files", "original", "fixture_sha256", "closed_ns", "status", "q3_accepted",
                "production_supported", "independent_supervisor_stop_required"))
    limited_scope(seal, stop="independent_supervisor_stop_required")
    original = identity(seal["original"])
    fixture_sha = digest(declarations["supervisor.json"])
    require(declarations["supervisor.json"] == encoded(fixture) and seal["fixture_sha256"] == fixture_sha,
            "REVIEW_FIXTURE_BINDING")
    reservation, delivery, capture, stop, result, marker = [decode(output[name + ".json"]) for name in
        ("reservation", "delivery", "capture", "stop", "result", "controller-result")]
    require(reservation["schema"] == fixture["schema"] and reservation["fixture_sha256"] == fixture_sha
            and reservation["target_static"] == fixture["launcher"]["controller_envelope"], "REVIEW_RESERVATION_BINDING")
    require(decode(output["invocation.json"]) == original == marker["controller"] == result["original"],
            "REVIEW_ORIGINAL_BINDING")
    require(marker["schema"] == record_schema(cancel, "controller-result", system=system) and marker["fixture_sha256"] == fixture_sha
            and decode(declarations["controller-result.json"]) == marker, "REVIEW_MARKER_BINDING")
    nested = copy.deepcopy(fixture["launcher"]); static = nested["controller_envelope"]["controller"]
    require(not set(static) & DYNAMIC, "REVIEW_STATIC_IDENTITY")
    nested["controller_envelope"]["controller"] = dict(static, **{name: original[name] for name in DYNAMIC})
    require(decode(declarations["launcher.json"]) == nested, "REVIEW_LAUNCHER_BINDING")
    launcher_status, capacity = capacity_facts(fixture, reservation, member_bytes)
    limited_scope(result, stop="independent_supervisor_stop_required")
    require(result["schema"] == record_schema(cancel, "supervisor-result", system=system) and result["status"] == "CLOSURE_OBSERVED_SEAL_PENDING"
            and result["scope"] == seal["scope"] and result["seal_required"] is True and result["sealed"] is False
            and result["cleanup_errors"] == [] and "reason" not in result and result["controller_stopped"] is True
            and result["closed_ns"] == seal["closed_ns"] and result["launcher_status"] == launcher_status,
            "REVIEW_PROVISIONAL_RESULT")
    limited_scope(marker["result"], stop="independent_controller_stop_required")
    expected_schema = ("local-hand-q4-cancel-launcher-result/v1" if cancel else
                       "local-hand-q2-system-launcher-result/v1" if system else
                       "local-hand-q2-launcher-result/" + fixture["launcher"]["schema"].rsplit("/", 1)[1])
    require(marker["result"]["schema"] == expected_schema and marker["result"]["status"] == launcher_status,
            "REVIEW_LAUNCHER_NOT_CLOSED")
    if cancel:
        cancel_case_facts(marker["result"], fixture, marker["completed_ns"])
    summary = {name: marker["result"][name] for name in ("schema", "status", "q3_accepted", "production_supported",
                                                       "independent_controller_stop_required")}
    require(decode(output["controller.stdout"]) == summary and output["controller.stderr"] == b"", "REVIEW_CLIENT_OUTPUT")
    limited_scope(capture, stop="independent_stop_required")
    require(capture["schema"] == "local-hand-q2-outer-capture/v1" and capture["complete"] is True
            and capture["error"] is None and capture["close_errors"] == [] and capture["eof"] == ["stderr", "stdout"]
            and type(capture["returncode"]) is int and capture["returncode"] == 0, "REVIEW_ORIGINAL_CAPTURE")
    integer(capture["client_pid"], 1)
    keys(capture["pipe_identities"], ("stdout", "stderr"))
    for name in ("stdout", "stderr"):
        pair = capture["pipe_identities"][name]
        require(type(pair) is list and len(pair) == 2, "REVIEW_PIPE_IDENTITY")
        integer(pair[0]); integer(pair[1], 1)
        require(capture[name + "_sha256"] == digest(output["controller." + name]), "REVIEW_PIPE_DIGEST")
    require(capture["pipe_identities"]["stdout"] != capture["pipe_identities"]["stderr"], "REVIEW_PIPE_ALIAS")
    target, outer = fixture["launcher"]["controller_envelope"], fixture["supervisor_envelope"]
    start, work_end, end = integer(target["issued_ns"], 1), integer(target["deadline_ns"], 1), integer(outer["deadline_ns"], 1)
    require(integer(outer["issued_ns"], 1) <= start < work_end < end
            and end <= outer["issued_ns"] + 120000000000
            and work_end + integer(static["timeout_stop_usec"], 1) * 1000 + 2000000000 <= end, "REVIEW_DEADLINES")
    require(start <= integer(delivery["started_ns"], 1) <= integer(marker["completed_ns"], 1) < work_end
            and marker["completed_ns"] <= integer(stop["closed_ns"], 1) <= integer(seal["closed_ns"], 1) < end
            and capture["started_ns"] == delivery["started_ns"] and capture["deadline_ns"] == end == delivery["deadline_ns"]
            and delivery["unit"] == static["unit"], "REVIEW_ORIGINAL_TIME_BINDING")
    token(delivery["argv_sha256"], r"[0-9a-f]{64}", "REVIEW_DELIVERY_DIGEST")
    if "cpu_quota_format" in delivery:
        require(delivery["cpu_quota_format"] == "systemd-percent-hundredths/v1", "REVIEW_CPU_QUOTA_FORMAT")
    require(delivery["argv_sha256"] == delivery_digest(fixture, fixture_sha,
        cpu_quota_format=delivery.get("cpu_quota_format")), "REVIEW_DELIVERY_BINDING")
    require(all(stop.get(name) is True for name in ("attempted", "acknowledged", "parent_empty", "complete")),
            "REVIEW_STOP_INCOMPLETE")
    running(stop["before"], static, original)
    after = stop["after"]
    require(after["Id"] == static["unit"] and after["Job"] in ("", "0") and after["MainPID"] == "0"
            and after["ControlPID"] == "0" and (after["LoadState"] == "not-found" or
            (after["LoadState"] == "loaded" and after["InvocationID"] == original["invocation_id"]
             and after["ActiveState"] in ("inactive", "failed") and after["ControlGroup"] in ("", static["cgroup"]))),
            "REVIEW_STOP_INSTANCE")
    controls = management_facts(decode(output["controls.json"]), stop, static)
    running(controls[-4], static, original)
    owner = reservation["owner"]
    require(owner["controller"] == outer["controller"] and owner["boot_id"] == capacity["boot_id"], "REVIEW_OWNER_BINDING")
    integer(owner["pid"], 1)
    require(owner["controller"]["invocation_id"] != original["invocation_id"]
            and owner["controller"]["unit"] != static["unit"], "REVIEW_OWNER_ALIAS")
    for name in ("stdout", "stderr"):
        pair = owner[name]; require(type(pair) is list and len(pair) == 2, "REVIEW_OWNER_PIPE")
        integer(pair[0]); integer(pair[1], 1)
    require(owner["stdout"] != owner["stderr"], "REVIEW_OWNER_PIPE")
    return fixture, launcher_status


def base_result():
    return dict(schema=SCHEMA, status="BLOCKED", scope=SCOPE, q3_accepted=False, production_supported=False,
                live_state_proven=False, host_provenance_proven=False, launcher_phase_evidence_reviewed=False,
                independent_supervisor_stop_required=True, full_capacity_acceptance_required=True,
                capacity_scope="RECORDED_DECLARATIONS_ONLY")


def review(evidence, declarations, expected_seal):
    token(expected_seal, r"[0-9a-f]{64}", "REVIEW_EXPECTED_SEAL_DIGEST_REQUIRED")
    directories = []
    try:
        out = Directory(evidence, OUTPUT | {"seal.json"}); directories.append(out)
        dec = Directory(declarations, DECLARATIONS); directories.append(dec)
        require(out.identity[:2] != dec.identity[:2], "REVIEW_DIRECTORY_ALIAS")
        raw_seal = out.read("seal.json", SEAL_LIMIT)
        require(digest(raw_seal) == expected_seal, "REVIEW_SEAL_DIGEST")
        seal = decode(raw_seal)
        require(type(seal) is dict and type(seal.get("files")) is dict and len(seal["files"]) == 13,
                "REVIEW_MANIFEST_COUNT")
        for pin in seal["files"].values():
            keys(pin, ("bytes", "sha256"), "REVIEW_MEMBER_PIN")
            integer(pin["bytes"])
            token(pin["sha256"], r"[0-9a-f]{64}", "REVIEW_MEMBER_PIN")
        blobs = []
        for directory, names in ((out, OUTPUT), (dec, DECLARATIONS)):
            blobs.append({name: directory.read(name, FILE_LIMIT if name in ("supervisor.json", "launcher.json")
                         else PIPE_LIMIT if name.startswith("controller.") else RECORD_LIMIT) for name in sorted(names)})
        total = sum(len(raw) for group in blobs for raw in group.values())
        require(total + len(raw_seal) <= TOTAL_LIMIT, "REVIEW_TOTAL_LIMIT")
        fixture = decode(blobs[1]["supervisor.json"])
        expected = {}
        for group, key in zip(blobs, ("output", "declarations")):
            prefix = absolute(fixture[key]["path"])
            for name, raw in group.items(): expected[prefix + "/" + name] = dict(bytes=len(raw), sha256=digest(raw))
        require(len(expected) == 13 and seal["files"] == expected, "REVIEW_MANIFEST_BINDING")
        fixture, launcher_status = facts(*blobs, seal, total + len(raw_seal))
        require(decode(blobs[0]["result.json"])["evidence"] == fixture["output"]["path"], "REVIEW_OUTPUT_BINDING")
        for directory in directories: directory.stable()
        result = base_result()
        result.update(status="OFFLINE_ARTIFACTS_CONSISTENT", seal_sha256=expected_seal, sealed_members=13,
                      sealed_bytes=total, recorded_launcher_status=launcher_status)
        if system_fixture(fixture):
            result.update(schema="local-hand-q2-system-offline-evidence-review/v1", manager_kind="system",
                          q2_accepted=False)
        if cancel_fixture(fixture):
            case = decode(blobs[0]["controller-result.json"])["result"]["case"]
            result.update(schema="local-hand-q4-cancel-offline-evidence-review/v1",
                          cancellation_case_record_reviewed=True, cancellation_case_status=case["status"],
                          helper_exit_proven=case["helper_exit_proven"], ordinary_phase_closed=False,
                          independent_ordinary_cleanup_required=True)
        return result
    finally:
        for directory in reversed(directories): directory.close()


def main(argv=None):
    class BoundedParser(argparse.ArgumentParser):
        def error(self, _message): raise ValueError("REVIEW_ARGUMENTS")
    parser = BoundedParser(description=__doc__)
    parser.add_argument("--evidence"); parser.add_argument("--declarations"); parser.add_argument("--seal-sha256")
    result = base_result()
    try:
        args = parser.parse_args(argv)
        require(args.evidence and args.declarations and args.seal_sha256, "EXPLICIT_REVIEW_INPUTS_REQUIRED")
        result["status"] = "INCOMPLETE"
        result = review(args.evidence, args.declarations, args.seal_sha256)
    except Exception as error:
        code = str(error) if isinstance(error, ValueError) else "REVIEW_INPUT_UNAVAILABLE"
        result["reason"] = code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "REVIEW_INVALID_ARTIFACT"
    raw = encoded(result)
    require(len(raw) <= 4096, "REVIEW_SUMMARY_LIMIT")
    print(raw.decode(), end="")
    return 0 if result["status"] == "OFFLINE_ARTIFACTS_CONSISTENT" else 3


if __name__ == "__main__":
    raise SystemExit(main())
