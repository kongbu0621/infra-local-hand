"""Explicit, test-only outer supervision of one existing Q2 fixture.

The supplied supervisor is itself an already running bounded root service. It
starts one fixed controller in an existing dedicated cgroup parent, retains its
original delivery client and pipes, and independently stops that exact service.
Only a complete target-controller proof receives a finite seal. The supervisor's
own external stop remains required; no result accepts Q3 or production use.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import threading
import time
from types import ModuleType, SimpleNamespace

SCHEMA = "local-hand-q2-supervisor/v1"
LIMIT = 2 * 1024 * 1024
RECORD_LIMIT = 65536
PIPE_LIMIT = 32768
CONTROL_CALLS = 16
START_OBSERVATIONS = 8
CAPABILITIES = "CAP_DAC_READ_SEARCH CAP_SETGID CAP_SETUID CAP_SETPCAP CAP_SYS_ADMIN"
CAP_MASK = sum(1 << bit for bit in (2, 6, 7, 8, 21))
DYNAMIC = {"invocation_id", "cgroup_device", "cgroup_inode"}
ENVELOPE = {"controller", "issued_ns", "deadline_ns", "output_bytes", "storage_bytes", "storage_inodes"}
STORAGE_FILES = ({"reservation.json": RECORD_LIMIT, "delivery.json": RECORD_LIMIT,
                  "invocation.json": RECORD_LIMIT, "controller.stdout": PIPE_LIMIT,
                  "controller.stderr": PIPE_LIMIT, "capture.json": 131072,
                  "stop.json": 131072, "controls.json": 131072,
                  "controller-result.json": 131072, "result.json": RECORD_LIMIT,
                  "seal.json": RECORD_LIMIT},
                 {"supervisor.json": LIMIT, "launcher.json": LIMIT,
                  "controller-result.json": RECORD_LIMIT})


def require(condition, code):
    if not condition:
        raise ValueError(code)


def reason(error):
    code = getattr(error, "code", str(error) if isinstance(error, ValueError) else type(error).__name__)
    return code if type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else type(error).__name__


def encoded(value, maximum=RECORD_LIMIT):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    require(len(raw) <= maximum, "SUPERVISOR_RECORD_LIMIT")
    return raw


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "SUPERVISOR_DUPLICATE_KEY")
        value[key] = item
    return value


def protected(path, maximum):
    """Bootstrap root-owned no-follow read; no application imports yet."""
    require(type(path) is str and path.startswith("/") and not path.startswith("//")
            and str(Path(path)) == path and ".." not in Path(path).parts, "SUPERVISOR_PATH")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        parts = Path(path).parts[1:]
        require(bool(parts), "SUPERVISOR_PATH")
        for index, name in enumerate(parts):
            directory = index + 1 < len(parts)
            child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
                            | (os.O_DIRECTORY if directory else 0), dir_fd=fd)
            os.close(fd); fd = child
            before = os.fstat(fd)
            require(before.st_uid == 0 and not before.st_mode & 0o022 and
                    (stat.S_ISDIR(before.st_mode) if directory else
                     stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and not before.st_mode & 0o6000),
                    "SUPERVISOR_PROTECTION")
        require(before.st_size <= maximum, "SUPERVISOR_FILE_LIMIT")
        raw = bytearray()
        while len(raw) <= maximum:
            part = os.read(fd, min(65536, maximum + 1 - len(raw)))
            if not part: break
            raw.extend(part)
        after = os.fstat(fd)
        require(len(raw) <= maximum and all(getattr(before, k) == getattr(after, k) for k in
                ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")), "SUPERVISOR_FILE_CHANGED")
        return bytes(raw)
    finally:
        os.close(fd)


def decode(raw, digest):
    require(len(raw) <= LIMIT and type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest)
            and sha(raw) == digest, "SUPERVISOR_DIGEST")
    value = json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("SUPERVISOR_NUMBER")))
    def finite(item, depth=0):
        require(depth <= 25, "SUPERVISOR_DEPTH")
        if type(item) is dict:
            for child in item.values(): finite(child, depth + 1)
        elif type(item) is list:
            for child in item: finite(child, depth + 1)
        else:
            require(item is None or type(item) in (str, int, bool), "SUPERVISOR_NUMBER")
            if type(item) is int: require(0 <= item < 2**63, "SUPERVISOR_NUMBER")
    finite(value)
    require(type(value) is dict and set(value) == {"schema", "purpose", "launcher", "controller_parent",
            "supervisor_envelope", "output", "declarations"} and value["schema"] == SCHEMA
            and value["purpose"] == "ISOLATED_Q2_SUPERVISION", "SUPERVISOR_SCHEMA")
    expected_status(value["launcher"])
    return value


def expected_status(launcher):
    require(type(launcher) is dict, "SUPERVISOR_LAUNCHER_SCHEMA")
    pair = (launcher.get("schema"), launcher.get("purpose"))
    statuses = {("local-hand-q2-launcher/v1", "ISOLATED_Q2_PREFLIGHT"): "PREFLIGHT_CLOSED",
                ("local-hand-q2-launcher/v2", "ISOLATED_Q2_CHAIN"): "CHAIN_CLOSED"}
    require(pair in statuses, "SUPERVISOR_LAUNCHER_SCHEMA")
    return statuses[pair]


def load_source(value, repository):
    """Execute the launcher and application modules from verified source bytes."""
    pins = value["launcher"]["source"]["files"]
    retained = {}
    for name in ("q2_supervisor", "q2_launcher"):
        relative = "tests/e3_host/" + name + ".py"
        raw = protected(str(repository / relative), LIMIT)
        require(pins.get(relative) == sha(raw), "SUPERVISOR_SOURCE_DIGEST")
        retained[name] = raw
    module = ModuleType("_q2_supervised_launcher")
    module.__file__ = str(repository / "tests/e3_host/q2_launcher.py")
    exec(compile(retained["q2_launcher"], module.__file__, "exec", dont_inherit=True), module.__dict__)
    module.source(value["launcher"], repository)
    return module


def templates(launcher):
    if expected_status(launcher) == "PREFLIGHT_CLOSED":
        from admin.local_hand_quota_observer import q2_assembly
        raw = encoded(launcher["assembly"], LIMIT)
        return [q2_assembly.decode(raw, sha(raw)).data()]
    from admin.local_hand_quota_observer import q2_chain
    raw = encoded(launcher["assembly"], LIMIT)
    chain = q2_chain.decode(raw, sha(raw))
    return [q2_chain.phase_template(chain, name).data() for name in ("preflight", "business", "evidence")]


def candidate(static):
    from admin.local_hand_quota_observer import controller_guard as guard
    require(type(static) is dict and set(static) == set(guard.SPEC_FIELDS) - DYNAMIC, "SUPERVISOR_STATIC_CONTROLLER")
    return guard.decode_controller(dict(static, invocation_id="0" * 32, cgroup_device=0, cgroup_inode=1))


def costs(envelope, spec, additional_output):
    return dict(storage_bytes=envelope["storage_bytes"], storage_inodes=envelope["storage_inodes"],
        cpu_ns=((spec.runtime_max_usec + spec.timeout_stop_usec + 1_000_000) * spec.cpu_quota_per_sec_usec + 999) // 1000,
        memory_bytes=spec.memory_bytes, pids=spec.tasks_max, output_bytes=envelope["output_bytes"] + additional_output)


def validate(value, launcher, clock):
    """Pure finite geometry/capacity checks before reservation or unit delivery."""
    from admin.local_hand_quota_observer import controller_guard as guard, q2_config as c
    from local_hand_jobs import quota_contract as q, quota_grant as g
    nested = value["launcher"]
    target_envelope = nested["controller_envelope"]
    own_envelope = value["supervisor_envelope"]
    for env in (target_envelope, own_envelope): q._keys(env, ENVELOPE)
    target = candidate(target_envelope["controller"])
    own = guard.decode_controller(own_envelope["controller"])
    phase_count = 1 if expected_status(nested) == "PREFLIGHT_CLOSED" else 3
    complete = copy.deepcopy(nested)
    complete["controller_envelope"]["controller"] = {"schema": guard.SCHEMA, **asdict(target)}
    raw = encoded(complete, LIMIT)
    launcher.decode(raw, sha(raw))
    for env, spec, minimum, inodes in ((target_envelope, target, 1024**2, max(8, 6 + phase_count)),
                                      (own_envelope, own, 8 * 1024**2, 16)):
        q.integer(env["issued_ns"], 1)
        q.integer(env["deadline_ns"], env["issued_ns"] + 1, env["issued_ns"] + spec.runtime_max_usec * 1000)
        q.integer(env["storage_bytes"], minimum); q.integer(env["storage_inodes"], inodes)
        q.integer(env["output_bytes"], PIPE_LIMIT, PIPE_LIMIT)
        require(env["issued_ns"] <= clock["boottime_ns"] < env["deadline_ns"], "SUPERVISOR_DEADLINE")
    require(own_envelope["issued_ns"] <= target_envelope["issued_ns"] and
            target_envelope["deadline_ns"] + target.timeout_stop_usec * 1000 + 2_000_000_000
            <= own_envelope["deadline_ns"] <= own_envelope["issued_ns"] + 120_000_000_000,
            "SUPERVISOR_ORIGINAL_CLEANUP_BUDGET")
    p = c.identity(value["controller_parent"])
    require(Path(p["path"]).parent == Path("/") and re.fullmatch(r"lhq[a-z0-9]+\.slice", Path(p["path"]).name)
            and str(Path(target.cgroup).parent) == p["path"], "SUPERVISOR_CONTROLLER_PARENT")
    supplied = templates(nested)
    installations = [item["installation"] for item in supplied]
    require(all(item == installations[0] for item in installations), "SUPERVISOR_INSTALLATION_BINDING")
    installation = installations[0]
    capacity = g.decode_capacity(q._canonical(installation["capacity"], g.GRANT_LIMIT))
    require(clock["boot_id"] == capacity["boot_id"], "SUPERVISOR_BOOT")
    totals = {key: 0 for key in capacity["management"]}
    parents = [p, c.identity(nested["resident"]["ordinary"]["parent"])]
    for item in supplied:
        data = item["grant"]; management = data["management"]
        q._keys(management, g._MANAGEMENT_KEYS - {"issued_ns"})
        q._keys(management["stages"], set(g.STAGES))
        for key in ("storage_bytes", "storage_inodes", "receive_ns", "stop_ns"): q.integer(management[key], 1)
        for stage in management["stages"].values():
            q._keys(stage, g._STAGE_KEYS)
            for amount in stage.values(): q.integer(amount, 1)
        require(management["capacity_digest"] == g.digest(capacity) and all(data["request"][key] == capacity[key]
                for key in ("boot_id", "epoch", "authority_digest")), "SUPERVISOR_CAPACITY_BINDING")
        for key, amount in g.totals(SimpleNamespace(as_dict=lambda data=data: data)).items(): totals[key] += amount
        parents.extend(c.identity(data[key]) for key in ("query_parent", "management_parent"))
    own_parent = str(Path(own.cgroup).parent)
    for parent in parents:
        require(not c.overlap(own_parent, parent["path"]), "SUPERVISOR_PARENT_OVERLAP")
    for parent in parents[1:]:
        require(not c.overlap(p["path"], parent["path"]), "SUPERVISOR_TARGET_OVERLAP")
    # Account resident pipes + launcher summary, then the additional original
    # controller pipes, supervisor admission captures and supervisor summary.
    for part in (costs(target_envelope, target, (phase_count - 1) * target_envelope["output_bytes"] + PIPE_LIMIT + 4096),
                 costs(own_envelope, own, 2 * PIPE_LIMIT + 4096)):
        for key, amount in part.items(): totals[key] += amount
    for key, amount in totals.items():
        require(q.integer(amount) <= capacity["management"][key], "SUPERVISOR_COMBINED_CAPACITY")
    for kind in ("bytes", "inodes"):
        used = totals["storage_" + kind] + capacity["retained_" + kind]
        used += sum(domain["hard_" + kind] for domain in capacity["domains"])
        require(q.integer(used) <= capacity["ceiling_" + kind], "SUPERVISOR_GLOBAL_STORAGE")
    destinations = [value[key] for key in ("output", "declarations")]
    protected_paths = [nested[key]["path"] for key in ("output", "declarations")]
    protected_paths += [item[key]["path"] for item in supplied for key in ("output", "journal")]
    protected_paths.extend((installation["tools_path"], installation["evidence"]["path"], installation["entry"]["path"],
                            nested["resident"]["installation"]["package_root"], nested["resident"]["entry"]["path"],
                            nested["setpriv"]["path"]))
    protected_paths.extend(pin["path"] for pin in installation["programs"].values())
    protected_paths.extend(pin["path"] for pin in nested["resident"]["installation"]["programs"].values())
    protected_pins = [nested[key] for key in ("output", "declarations")] + [installation["evidence"]]
    for item in supplied:
        protected_pins.extend(item[key] for key in ("output", "journal"))
        protected_paths.extend((item["grant"]["endpoint"]["path"], item["service"]["control_path"],
                                item["peer"]["executable"]["path"], item["peer"]["runner"]["path"]))
        protected_paths.extend(g.root_paths(item["grant"]["allocation"]).values())
        protected_pins.extend(item["grant"]["allocation"]["paths"].values())
    for pin in destinations:
        c.identity(pin)
        require(all(not c.overlap(pin["path"], path) for path in protected_paths), "SUPERVISOR_OUTPUT_OVERLAP")
        require(all((pin["device"], pin["inode"]) != (other["device"], other["inode"])
                    for other in protected_pins), "SUPERVISOR_OUTPUT_ALIAS")
        protected_paths.append(pin["path"])
        protected_pins.append(pin)
    return dict(target=target, own=own, installation=installation, totals=totals, boot_id=capacity["boot_id"])


def actual_controller(spec, installation, boot_id):
    from admin.local_hand_quota_observer import controller_guard as guard
    adapter = SimpleNamespace(initial_userns_device=installation["initial_userns"]["device"],
        initial_userns_inode=installation["initial_userns"]["inode"],
        systemctl_path=installation["programs"]["systemctl"]["path"],
        systemctl_sha256=installation["programs"]["systemctl"]["sha256"])
    manifest = SimpleNamespace(boot_id=boot_id, cgroup_parent="/unused-query.slice")
    before = guard._host_identity(adapter, manifest, spec)
    guard._cgroup_identity(spec)
    guard._check_manager(guard._show_once(adapter, spec), spec, before[0])
    guard._cgroup_identity(spec)
    require(before == guard._host_identity(adapter, manifest, spec), "SUPERVISOR_IDENTITY_CHANGED")
    return dict(controller={"schema": guard.SCHEMA, **asdict(spec)}, pid=before[0],
                stdout=list(before[1]), stderr=list(before[2]), boot_id=boot_id)


def admit(value, binding):
    from admin.local_hand_quota_observer import q2_config as c
    from admin.local_hand_quota_observer.systemd_runtime import _fixed_read
    installation = binding["installation"]
    for name in ("python", "systemctl", "systemd_run"):
        fd = c.executable(installation["programs"][name])
        try:
            if name == "python":
                actual, expected = os.stat("/proc/self/exe"), os.fstat(fd)
                require((actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino), "SUPERVISOR_INTERPRETER")
        finally: os.close(fd)
    rows = dict(line.split(":", 1) for line in _fixed_read("/proc/self/status", 16384).decode("ascii").splitlines())
    require(all(int(rows[key], 16) & CAP_MASK == CAP_MASK for key in ("CapPrm", "CapEff", "CapBnd")),
            "SUPERVISOR_EXISTING_CAPABILITIES_REQUIRED")
    return actual_controller(binding["own"], installation, binding["boot_id"])


def command(value, binding, repository, fixture_path, fixture_digest):
    spec = binding["target"]
    programs = binding["installation"]["programs"]
    properties = dict(User="root", Group="root", Slice=Path(spec.cgroup).parent.name,
        Type="exec", ExitType="cgroup", RemainAfterExit="no", Restart="no", RestartForceExitStatus="",
        KillMode="control-group", SendSIGKILL="yes", FinalKillSignal="SIGKILL", NotifyAccess="none",
        ExecStartPre="", ExecStartPost="", ExecStop="", ExecStopPost="", ExecReload="", OnFailure="", OnSuccess="",
        RuntimeMaxSec=str(spec.runtime_max_usec) + "us", RuntimeRandomizedExtraSec="0",
        TimeoutStopSec=str(spec.timeout_stop_usec) + "us", TimeoutStopFailureMode="kill",
        MemoryMax=str(spec.memory_bytes), MemorySwapMax="0", TasksMax=str(spec.tasks_max),
        CPUQuota=str(spec.cpu_quota_per_sec_usec // 10000) + "." + f"{spec.cpu_quota_per_sec_usec % 10000:04d}" + "%",
        CPUQuotaPeriodSec="100ms", LimitCPU=str(spec.limit_cpu_seconds), UMask="0077", WorkingDirectory="/",
        NoNewPrivileges="yes", CapabilityBoundingSet=CAPABILITIES, AmbientCapabilities="",
        StandardInput="null")
    return [programs["systemd_run"]["path"], "--system", "--quiet", "--wait", "--pipe", "--no-ask-password",
        "--unit=" + spec.unit, *("--property=" + key + "=" + val for key, val in properties.items()), "--",
        programs["python"]["path"], "-I", "-B", str(repository / "tests/e3_host/q2_supervisor.py"),
        "--controller", "--fixture", fixture_path, "--sha256", fixture_digest]


def storage_capacity(value, output, declarations):
    """Charge bounded files, the seal and directory growth before any write.

    These are retained control records, not a measurement of an earlier peak.
    The caller must already have opened the two pinned, empty directories.
    """
    total = 0
    for directory, members in zip((output, declarations), STORAGE_FILES):
        block = os.fstatvfs(directory).f_frsize
        require(type(block) is int and 0 < block < 2**63, "SUPERVISOR_STORAGE_GEOMETRY")
        # Existing directory blocks stay charged, including an extra block for
        # the finite names being added. Temporary marker rename uses one inode.
        total += max(block, os.fstat(directory).st_blocks * 512) + block
        total += sum(((maximum + block - 1) // block) * block for maximum in members.values())
    envelope = value["supervisor_envelope"]
    require(total <= envelope["storage_bytes"] and
            sum(map(len, STORAGE_FILES)) + 2 <= envelope["storage_inodes"], "SUPERVISOR_STORAGE_RESERVATION")
    return dict(storage_bytes=total, storage_inodes=sum(map(len, STORAGE_FILES)) + 2)


def seal_files(value, output, declarations, launcher):
    """Recheck the original directories and exact retained member allocation."""
    files = {}
    allocated = 0
    for pin, directory, limits in zip((value["output"], value["declarations"]),
                                      (output, declarations), STORAGE_FILES):
        def same_directory():
            actual = os.stat(pin["path"], follow_symlinks=False)
            held = os.fstat(directory)
            require(stat.S_ISDIR(actual.st_mode) and
                    (actual.st_dev, actual.st_ino) == (held.st_dev, held.st_ino) ==
                    (pin["device"], pin["inode"]), "SUPERVISOR_SEAL_DIRECTORY_CHANGED")
        same_directory()
        names = sorted(os.listdir(directory))
        expected = set(limits) - {"seal.json"}
        require(set(names) == expected, "SUPERVISOR_SEAL_MEMBERS")
        block = os.fstatvfs(directory).f_frsize
        require(type(block) is int and 0 < block < 2**63, "SUPERVISOR_STORAGE_GEOMETRY")
        allocated += max(block, os.fstat(directory).st_blocks * 512)
        for name in names:
            before = os.stat(name, dir_fd=directory, follow_symlinks=False)
            path = pin["path"] + "/" + name
            raw = launcher.protected(path, limits[name])
            after = os.stat(name, dir_fd=directory, follow_symlinks=False)
            linked = os.stat(path, follow_symlinks=False)
            require(stat.S_ISREG(after.st_mode) and all(getattr(before, key) == getattr(after, key) ==
                    getattr(linked, key) for key in ("st_dev", "st_ino", "st_size", "st_blocks", "st_mtime_ns", "st_ctime_ns"))
                    and after.st_size == len(raw), "SUPERVISOR_SEAL_MEMBER_CHANGED")
            allocated += max(after.st_blocks * 512, ((len(raw) + block - 1) // block) * block)
            files[path] = dict(bytes=len(raw), sha256=sha(raw))
        if "seal.json" in limits:
            allocated += ((limits["seal.json"] + block - 1) // block) * block + block
        same_directory()
    envelope = value["supervisor_envelope"]
    require(allocated <= envelope["storage_bytes"] and len(files) + 3 <= envelope["storage_inodes"],
            "SUPERVISOR_SEAL_STORAGE")
    return files


class Controls:
    """Bounded real system-manager calls, separately retained from target pipes."""
    def __init__(self, value, binding):
        self.value, self.binding, self.calls = value, binding, []
        self.limit = value["supervisor_envelope"]["output_bytes"]

    def clock(self, end):
        from local_hand_jobs import budget
        now = budget.current_clock()
        require(now["boot_id"] == self.binding["boot_id"] and now["boottime_ns"] < end, "SUPERVISOR_DEADLINE_OR_BOOT")
        return now["boottime_ns"]

    def call(self, arguments, end):
        from admin.local_hand_quota_observer.systemd_runtime import Capture
        require(len(self.calls) < CONTROL_CALLS and all(item[1].settled for item in self.calls), "SUPERVISOR_CONTROL_UNRESOLVED")
        room = self.limit - sum(len(c.stdout) + len(c.stderr) for _, c in self.calls)
        require(room > 0, "SUPERVISOR_CONTROL_OUTPUT")
        local_end = min(end, self.clock(end) + 2_000_000_000)
        cap = Capture(min(PIPE_LIMIT, room)); self.calls.append((list(arguments), cap))
        try:
            cap.start([self.binding["installation"]["programs"]["systemctl"]["path"],
                       "--system", "--no-pager", "--no-ask-password", *arguments])
            while True:
                self.clock(local_end); cap.pump()
                require(cap.error is None, "SUPERVISOR_CONTROL_CAPTURE")
                if cap.done:
                    require(cap.process.returncode == 0 and not cap.stderr, "SUPERVISOR_CONTROL_FAILED")
                    return bytes(cap.stdout)
                time.sleep(0.01)
        finally:
            if not cap.settled:
                cap.error = cap.error or "SUPERVISOR_CONTROL_INCOMPLETE"
                cap.kill_client()  # Never a target-service stop or exit proof.
                cap.pump()
            cap.close_pipes()

    def show(self, end):
        from admin.local_hand_quota_observer import controller_guard as guard
        names = (*guard.SHOW_FIELDS, "ExecStartPre", "ExecMainCode", "ExecMainStatus", "Result",
                 "User", "Group", "NoNewPrivileges", "CapabilityBoundingSet", "AmbientCapabilities")
        raw = self.call(("show", self.binding["target"].unit, "--all", "--property=" + ",".join(names)), end)
        pairs = [line.split("=", 1) for line in raw.decode("ascii").splitlines()]
        require(all(len(row) == 2 for row in pairs), "SUPERVISOR_MANAGER_FORMAT")
        values = unique(pairs)
        for name in (*guard.EMPTY_EXEC_FIELDS, "ExecStartPre"): values.setdefault(name, "")
        require(set(values) == set(names), "SUPERVISOR_MANAGER_FIELDS")
        return values

    def empty(self):
        from admin.local_hand_quota_observer.systemd_runtime import Q1Controller
        pin = self.value["controller_parent"]
        controller = SimpleNamespace(config=SimpleNamespace(cgroup_parent_device=pin["device"], cgroup_parent_inode=pin["inode"]))
        binding = SimpleNamespace(manifest=SimpleNamespace(cgroup_parent=pin["path"]))
        return Q1Controller._parent_empty(controller, binding)

    def evidence(self):
        return [dict(arguments=args, stdout_hex=bytes(cap.stdout).hex(), stderr_hex=bytes(cap.stderr).hex(),
                     returncode=None if cap.process is None else cap.process.poll(), eof=sorted(cap.eof), error=cap.error,
                     complete=cap.done) for args, cap in self.calls]


def bind_running(values, static, original=None):
    from admin.local_hand_quota_observer import controller_guard as guard
    require(values["ExecStartPre"] == "" and re.fullmatch(r"[1-9][0-9]{0,19}", values["MainPID"]),
            "SUPERVISOR_RUNNING_IDENTITY")
    candidate_data = dict(static, invocation_id=values["InvocationID"], cgroup_device=0, cgroup_inode=1)
    if original is not None:
        require(values["InvocationID"] == original["invocation_id"] and int(values["MainPID"]) == original["pid"],
                "SUPERVISOR_ORIGINAL_INSTANCE_CHANGED")
        candidate_data.update(cgroup_device=original["cgroup_device"], cgroup_inode=original["cgroup_inode"])
    spec = guard.decode_controller(candidate_data)
    guard._check_manager(values, spec, int(values["MainPID"]))
    require(values["User"] == "root" and values["Group"] == "root" and values["NoNewPrivileges"] == "yes"
            and values["AmbientCapabilities"] == "" and set(values["CapabilityBoundingSet"].split()) ==
            set(CAPABILITIES.lower().split()), "SUPERVISOR_CONTROLLER_PRIVILEGES")
    return spec


def observe_identity(values, static):
    from admin.local_hand_quota_observer import controller_guard as guard
    from admin.local_hand_quota_observer.protected_inputs import open_protected
    spec = bind_running(values, static)
    fd = open_protected("/sys/fs/cgroup" + spec.cgroup, directory=True)
    try: metadata = os.fstat(fd)
    finally: os.close(fd)
    identity = dict(invocation_id=spec.invocation_id, pid=int(values["MainPID"]),
                    cgroup_device=metadata.st_dev, cgroup_inode=metadata.st_ino)
    guard._cgroup_identity(guard.decode_controller(dict(static, **{key: identity[key] for key in DYNAMIC})))
    return identity


def observe_start(controls, static, process, end):
    """Observe the one submitted start through its finite pending states.

    Type=exec first exposes an activating unit and its start Job, often before
    MainPID exists. Neither is an accepted running identity. Observing them
    never resubmits a launch and leaves at least four control calls for stop.
    """
    invocation = pid = None
    for index in range(START_OBSERVATIONS):
        facts = controls.show(end)
        require(facts["Id"] == static["unit"] and process.poll() is None,
                "SUPERVISOR_DELIVERY_UNCERTAIN")
        if facts["LoadState"] == "loaded":
            current = facts["InvocationID"]
            require(current == "" or re.fullmatch(r"[0-9a-f]{32}", current), "SUPERVISOR_RUNNING_IDENTITY")
            if current:
                require(invocation in (None, current), "SUPERVISOR_ORIGINAL_INSTANCE_CHANGED")
                invocation = current
            require(re.fullmatch(r"0|[1-9][0-9]{0,19}", facts["MainPID"]), "SUPERVISOR_RUNNING_IDENTITY")
            current_pid = int(facts["MainPID"])
            if current_pid:
                require(pid in (None, current_pid), "SUPERVISOR_ORIGINAL_INSTANCE_CHANGED")
                pid = current_pid
            if (facts["ActiveState"], facts["SubState"]) == ("active", "running") and facts["Job"] in ("", "0"):
                return observe_identity(facts, static)
            require((facts["ActiveState"], facts["SubState"]) in
                    (("activating", "start-pre"), ("activating", "start"), ("active", "running")) and facts["ControlPID"] == "0"
                    and facts["ExecStartPre"] == "", "SUPERVISOR_DELIVERY_UNCERTAIN")
        else:
            require(facts["LoadState"] == "not-found" and facts["Job"] in ("", "0")
                    and facts["InvocationID"] == "" and facts["MainPID"] == "0"
                    and facts["ControlPID"] == "0" and invocation is None and pid is None,
                    "SUPERVISOR_DELIVERY_UNCERTAIN")
        controls.clock(end)
        if index + 1 < START_OBSERVATIONS: time.sleep(0.125)
    raise ValueError("SUPERVISOR_INSTANCE_NOT_OBSERVED")


def stop_original(controls, static, original, end, record):
    from admin.local_hand_quota_observer import controller_guard as guard
    require(original is not None and not record.get("attempted"), "SUPERVISOR_ORIGINAL_STOP_REQUIRED")
    record["before"] = controls.show(end)
    spec = bind_running(record["before"], static, original)
    guard._cgroup_identity(spec)
    controls.clock(end)
    record["attempted"] = True
    controls.call(("stop", spec.unit), end)
    record["acknowledged"] = True
    record["after"] = controls.show(end)
    after = record["after"]
    require(after["Id"] == spec.unit and after["Job"] in ("", "0") and after["MainPID"] == "0"
            and after["ControlPID"] == "0", "SUPERVISOR_STOP_PENDING")
    require(after["LoadState"] == "not-found" or
            (after["LoadState"] == "loaded" and after["InvocationID"] == spec.invocation_id
             and after["ActiveState"] in ("inactive", "failed") and after["ControlGroup"] in ("", spec.cgroup)),
            "SUPERVISOR_STOP_INSTANCE_CHANGED")
    record["parent_empty"] = controls.empty()
    require(record["parent_empty"], "SUPERVISOR_CONTROLLER_TREE_NOT_EMPTY")
    record["closed_ns"] = controls.clock(end)
    record["complete"] = True


def read_marker(value, original, launcher):
    path = value["declarations"]["path"] + "/controller-result.json"
    try: raw = launcher.protected(path, RECORD_LIMIT)
    except FileNotFoundError: return None
    marker = json.loads(raw, object_pairs_hook=unique)
    require(set(marker) == {"schema", "fixture_sha256", "controller", "result", "completed_ns"}
            and marker["schema"] == "local-hand-q2-controller-result/v1"
            and marker["fixture_sha256"] == sha(encoded(value, LIMIT))
            and marker["controller"] == original, "SUPERVISOR_RESULT_BINDING")
    require(type(marker["completed_ns"]) is int and value["launcher"]["controller_envelope"]["issued_ns"]
            <= marker["completed_ns"] < value["launcher"]["controller_envelope"]["deadline_ns"],
            "SUPERVISOR_RESULT_DEADLINE")
    result = marker["result"]
    require(type(result) is dict and result.get("q3_accepted") is False and result.get("production_supported") is False
            and result.get("independent_controller_stop_required") is True, "SUPERVISOR_RESULT_SCOPE")
    return marker


def publish_marker(directory, raw, launcher):
    """Publish complete fsynced bytes once; readers never see a partial marker."""
    import ctypes
    launcher.save(directory, "controller-result.pending", raw)
    library = ctypes.CDLL(None, use_errno=True)
    rename = library.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(directory, b"controller-result.pending", directory, b"controller-result.json", 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))
    os.fsync(directory)


def controller_role(value, launcher, repository):
    """One original controller PID; no fork between identity and launcher.run."""
    from admin.local_hand_quota_observer import controller_guard as guard, q2_config as c
    from admin.local_hand_quota_observer.systemd_runtime import _own_cgroup
    from local_hand_jobs import budget
    binding = validate(value, launcher, budget.current_clock())
    static = value["launcher"]["controller_envelope"]["controller"]
    require(_own_cgroup() == static["cgroup"], "SUPERVISOR_CHILD_CGROUP")
    fd = os.open("/sys/fs/cgroup" + static["cgroup"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try: metadata = os.fstat(fd)
    finally: os.close(fd)
    identity = dict(invocation_id=os.environ.get("INVOCATION_ID"), pid=os.getpid(),
                    cgroup_device=metadata.st_dev, cgroup_inode=metadata.st_ino)
    actual = dict(static, **{key: identity[key] for key in DYNAMIC})
    actual_controller(guard.decode_controller(actual), binding["installation"], binding["boot_id"])
    nested = copy.deepcopy(value["launcher"])
    nested["controller_envelope"]["controller"] = actual
    raw = encoded(nested, LIMIT); launcher.decode(raw, sha(raw))
    output = c.pinned_directory(value["declarations"])
    stopped = threading.Event()
    # The result is durable before StopUnit can end this holder. The holder
    # retains the original service for the parent's independent identity check.
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    try:
        launcher.save(output, "launcher.json", raw)
        result = launcher.run(nested, repository)
        now = budget.current_clock()
        require(now["boot_id"] == binding["boot_id"] and now["boottime_ns"] < nested["controller_envelope"]["deadline_ns"],
                "SUPERVISOR_CHILD_DEADLINE")
        marker = dict(schema="local-hand-q2-controller-result/v1", fixture_sha256=sha(encoded(value, LIMIT)),
                      controller=identity, result=result, completed_ns=now["boottime_ns"])
        publish_marker(output, encoded(marker), launcher)
        summary = {key: result[key] for key in ("schema", "status", "q3_accepted", "production_supported",
                   "independent_controller_stop_required")}
        print(encoded(summary, 4096).decode(), end="", flush=True)
        end = value["supervisor_envelope"]["deadline_ns"]
        while not stopped.wait(0.025):
            now = budget.current_clock()
            require(now["boot_id"] == binding["boot_id"] and now["boottime_ns"] < end, "SUPERVISOR_CHILD_HOLD_DEADLINE")
        return 0 if result["status"] == expected_status(nested) else 3
    finally:
        os.close(output)


def supervise(value, launcher, repository):
    from admin.local_hand_quota_observer import q2_capture
    from local_hand_jobs import budget
    result = dict(schema="local-hand-q2-supervisor-result/v1", status="BLOCKED", q3_accepted=False,
                  production_supported=False, independent_supervisor_stop_required=True,
                  scope="TARGET_CONTROLLER_CLOSURE_ONLY", seal_required=True, sealed=False)
    output = declarations = None
    storage_admitted = False
    process = worker = controls = None
    capture = {}; stop = {}; original = marker = None
    try:
        binding = validate(value, launcher, budget.current_clock())
        owner = admit(value, binding)
        controls = Controls(value, binding)
        work_end = value["launcher"]["controller_envelope"]["deadline_ns"]
        end = value["supervisor_envelope"]["deadline_ns"]
        require(controls.empty(), "SUPERVISOR_CONTROLLER_PARENT_OCCUPIED")
        before = controls.show(work_end)
        require(before["Id"] == binding["target"].unit and before["LoadState"] == "not-found"
                and before["Job"] in ("", "0"), "SUPERVISOR_TARGET_ALREADY_EXISTS")
        output = launcher.directory(value["output"], 0o700)
        declarations = launcher.directory(value["declarations"], 0o700)
        storage_capacity(value, output, declarations)
        storage_admitted = True
        result["status"] = "INCOMPLETE"
        result["evidence"] = value["output"]["path"]
        launcher.save(output, "reservation.json", encoded(dict(schema=SCHEMA, fixture_sha256=sha(encoded(value, LIMIT)),
            owner=owner, target_static=value["launcher"]["controller_envelope"], capacity_costs=binding["totals"])))
        fixture_raw = encoded(value, LIMIT)
        launcher.save(declarations, "supervisor.json", fixture_raw)
        argv = command(value, binding, repository, value["declarations"]["path"] + "/supervisor.json", sha(fixture_raw))
        started = controls.clock(work_end)
        launcher.save(output, "delivery.json", encoded(dict(argv_sha256=sha(encoded(argv)), started_ns=started,
                                                            deadline_ns=end, unit=binding["target"].unit)))
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   close_fds=True, bufsize=0, cwd="/", env=dict(PATH="/usr/bin:/bin", LANG="C", LC_ALL="C", SYSTEMD_COLORS="0"))
        def collect():
            try:
                capture.update(q2_capture.capture_existing(process, boot_id=binding["boot_id"], started_ns=started,
                    deadline_ns=end, limit=PIPE_LIMIT))
            except Exception as error:
                capture.update(complete=False, returncode=process.poll(), stdout=b"", stderr=b"", eof=[], error=reason(error))
                for stream in (process.stdout, process.stderr):
                    try: stream.close()
                    except Exception: pass
        worker = threading.Thread(target=collect, daemon=True); worker.start()
        static = value["launcher"]["controller_envelope"]["controller"]
        original = observe_start(controls, static, process, work_end)
        launcher.save(output, "invocation.json", encoded(original))
        for _ in range(4800):
            controls.clock(work_end)
            marker = read_marker(value, original, launcher)
            if marker is not None: break
            require(process.poll() is None and not capture, "SUPERVISOR_CONTROLLER_EXITED_EARLY")
            time.sleep(0.025)
        require(marker is not None, "SUPERVISOR_RESULT_MISSING")
        stop_original(controls, static, original, end, stop)
        while worker.is_alive():
            controls.clock(end); worker.join(0.025)
        require(capture.get("complete") is True and capture.get("returncode") == 0
                and capture.get("stderr") == b"", "SUPERVISOR_ORIGINAL_CAPTURE_INCOMPLETE")
        summary = json.loads(capture["stdout"], object_pairs_hook=unique)
        expected = {key: marker["result"][key] for key in ("schema", "status", "q3_accepted", "production_supported",
                    "independent_controller_stop_required")}
        require(summary == expected and expected["status"] == expected_status(value["launcher"]), "SUPERVISOR_LAUNCHER_NOT_CLOSED")
        require(controls.empty() and all(cap.done for _, cap in controls.calls), "SUPERVISOR_FINAL_EXIT_UNPROVEN")
        result.update(status="CONTROLLER_CLOSED", launcher_status=expected["status"], closed_ns=controls.clock(end),
                      original=original, controller_stopped=True)
    except Exception as error:
        result["reason"] = reason(error)
    finally:
        failures = []
        def retain(action, code):
            try: action()
            except Exception:
                failures.append(code); result.update(status="INCOMPLETE", reason=code)
        if controls is not None and original is not None and not stop.get("attempted"):
            retain(lambda: stop_original(controls, value["launcher"]["controller_envelope"]["controller"], original,
                   value["supervisor_envelope"]["deadline_ns"], stop), "SUPERVISOR_CLEANUP_STOP_UNPROVEN")
        if worker is not None:
            def await_capture():
                while worker.is_alive():
                    controls.clock(value["supervisor_envelope"]["deadline_ns"]); worker.join(0.025)
            retain(await_capture, "SUPERVISOR_CAPTURE_UNFINISHED")
        if output is not None and storage_admitted:
            captured = dict(capture)
            for name in ("stdout", "stderr"):
                raw = captured.pop(name, b"")
                retain(lambda name=name, raw=raw: launcher.save(output, "controller." + name, raw), "SUPERVISOR_CAPTURE_PERSIST")
            records = {"capture.json": captured, "stop.json": stop,
                       "controls.json": [] if controls is None else controls.evidence()}
            if marker is not None: records["controller-result.json"] = marker
            for name, item in records.items():
                retain(lambda name=name, item=item: launcher.save(output, name, encoded(item, 131072)), "SUPERVISOR_EVIDENCE_PERSIST")
            result["cleanup_errors"] = failures
            provisional = dict(result)
            if provisional["status"] == "CONTROLLER_CLOSED": provisional["status"] = "CLOSURE_OBSERVED_SEAL_PENDING"
            retain(lambda: launcher.save(output, "result.json", encoded(provisional)), "SUPERVISOR_RESULT_PERSIST")
            if result["status"] == "CONTROLLER_CLOSED" and not failures:
                def seal():
                    controls.clock(value["supervisor_envelope"]["deadline_ns"])
                    files = seal_files(value, output, declarations, launcher)
                    require(controls.empty(), "SUPERVISOR_SEAL_TREE_NOT_EMPTY")
                    payload = dict(schema="local-hand-q2-controller-seal/v1", scope=result["scope"], files=files,
                        original=original, fixture_sha256=sha(encoded(value, LIMIT)), closed_ns=result["closed_ns"],
                        status="CONTROLLER_CLOSED", q3_accepted=False, production_supported=False,
                        independent_supervisor_stop_required=True)
                    launcher.save(output, "seal.json", encoded(payload))
                retain(seal, "SUPERVISOR_SEAL_UNPROVEN")
                if not failures: result["sealed"] = True
        if output is not None: retain(lambda: os.close(output), "SUPERVISOR_OUTPUT_CLOSE")
        if declarations is not None: retain(lambda: os.close(declarations), "SUPERVISOR_DECLARATIONS_CLOSE")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture"); parser.add_argument("--sha256")
    parser.add_argument("--controller", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    result = dict(schema="local-hand-q2-supervisor-result/v1", status="BLOCKED", q3_accepted=False,
                  production_supported=False, independent_supervisor_stop_required=True)
    try:
        require(args.fixture and args.sha256, "EXPLICIT_PRIVATE_FIXTURE_REQUIRED")
        require(sys.flags.isolated and sys.dont_write_bytecode, "SUPERVISOR_ISOLATED_PYTHON")
        value = decode(protected(args.fixture, LIMIT), args.sha256)
        repository = Path(__file__).resolve().parents[2]
        launcher = load_source(value, repository)
        if args.controller: return controller_role(value, launcher, repository)
        result = supervise(value, launcher, repository)
    except Exception as error:
        result["reason"] = reason(error)
    print(json.dumps({key: result[key] for key in ("schema", "status", "q3_accepted", "production_supported",
          "independent_supervisor_stop_required", "reason", "evidence", "scope") if key in result}, sort_keys=True))
    return 0 if result["status"] == "CONTROLLER_CLOSED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
