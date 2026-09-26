"""Explicit one-shot Q2 handoff from an existing root management endpoint.

The endpoint owns the original client and both pipes. Its child binds real
service identity in the same MainPID before checking and entering the existing
Q2 supervisor. No quota setup, replay, deadline renewal or production acceptance.
The endpoint's own actual exit/EOF must be retained by its original caller.
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
from types import ModuleType

SCHEMA = "local-hand-q2-original-handoff/v1"
ENVELOPE_SCHEMA = "local-hand-q2-issued-handoff/v1"
RESULT_SCHEMA = "local-hand-q2-handoff-result/v1"
LIMIT = 2 * 1024 * 1024
RECORD_LIMIT = 131072
PIPE_LIMIT = 32768
DYNAMIC = {"invocation_id", "cgroup_device", "cgroup_inode"}
OWNER_KEYS = {"issued_ns", "deadline_ns", "storage_bytes", "storage_inodes", "cpu_ns", "memory_bytes", "pids", "output_bytes"}
FILES = {"reservation.json": LIMIT, "delivery.json": 65536, "invocation.json": 65536,
         "supervisor.stdout": PIPE_LIMIT, "supervisor.stderr": PIPE_LIMIT,
         "capture.json": RECORD_LIMIT, "stop.json": RECORD_LIMIT, "controls.json": RECORD_LIMIT,
         "result.json": 65536, "child-result.json": RECORD_LIMIT, "seal.json": RECORD_LIMIT}
DECLARATIONS = {"envelope.json": LIMIT, "fixture-check.json": RECORD_LIMIT,
                "bound-supervisor.json": LIMIT, "supervisor-result.json": RECORD_LIMIT}


def require(ok, code):
    if not ok:
        raise ValueError(code)


def reason(error):
    value = getattr(error, "code", str(error) if isinstance(error, ValueError) else type(error).__name__)
    return value if type(value) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else type(error).__name__


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), "HANDOFF_FIELDS")


def integer(value, minimum=0, maximum=2**63-1):
    require(type(value) is int and minimum <= value <= maximum, "HANDOFF_INTEGER")
    return value


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value, limit=RECORD_LIMIT):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    require(len(raw) <= limit, "HANDOFF_RECORD_LIMIT")
    return raw


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "HANDOFF_DUPLICATE_KEY")
        value[key] = item
    return value


def document(raw, digest, limit=LIMIT):
    require(type(raw) is bytes and len(raw) <= limit and type(digest) is str
            and re.fullmatch(r"[0-9a-f]{64}", digest) and sha(raw) == digest, "HANDOFF_DIGEST")
    def forbidden(_):
        raise ValueError("HANDOFF_NUMBER")
    value = json.loads(raw, object_pairs_hook=unique, parse_float=forbidden, parse_constant=forbidden)
    remaining = [50000]
    def finite(item, depth=0):
        remaining[0] -= 1
        require(depth <= 30 and remaining[0] >= 0, "HANDOFF_STRUCTURE")
        if type(item) is dict:
            for child in item.values(): finite(child, depth + 1)
        elif type(item) is list:
            for child in item: finite(child, depth + 1)
        elif type(item) is int:
            integer(item)
        else:
            require(item is None or type(item) in (bool, str), "HANDOFF_NUMBER")
    finite(value)
    return value


def protected(path, limit=LIMIT):
    require(type(path) is str and path.startswith("/") and not path.startswith("//") and path != "/"
            and str(Path(path)) == path and ".." not in Path(path).parts, "HANDOFF_PATH")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        parts = Path(path).parts[1:]
        for index, name in enumerate(parts):
            directory = index + 1 < len(parts)
            child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
                            | (os.O_DIRECTORY if directory else 0), dir_fd=fd)
            os.close(fd); fd = child
            before = os.fstat(fd)
            require(before.st_uid == 0 and not before.st_mode & 0o022 and
                    (stat.S_ISDIR(before.st_mode) if directory else
                     stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and not before.st_mode & 0o6000), "HANDOFF_PROTECTION")
        require(before.st_size <= limit, "HANDOFF_FILE_LIMIT")
        raw = bytearray()
        while len(raw) <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - len(raw)))
            if not chunk: break
            raw.extend(chunk)
        after = os.fstat(fd)
        require(len(raw) <= limit and all(getattr(before, key) == getattr(after, key) for key in
                ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")), "HANDOFF_FILE_CHANGED")
        return bytes(raw)
    finally:
        os.close(fd)


def static_template(value):
    keys(value, {"schema", "purpose", "launcher", "controller_parent", "supervisor_envelope", "output", "declarations"})
    require(value["schema"] == "local-hand-q2-supervisor/v1" and value["purpose"] == "ISOLATED_Q2_SUPERVISION",
            "HANDOFF_TEMPLATE_SCHEMA")
    nested = value["launcher"]
    require(nested.get("schema") == "local-hand-q2-launcher/v2" and nested.get("purpose") == "ISOLATED_Q2_CHAIN",
            "HANDOFF_THREE_PHASE_REQUIRED")
    for env in (value["supervisor_envelope"], nested["controller_envelope"]):
        keys(env, {"controller", "output_bytes", "storage_bytes", "storage_inodes"})
        require(type(env["controller"]) is dict and not DYNAMIC.intersection(env["controller"]), "HANDOFF_FUTURE_IDENTITY")
    return value


def decode(raw, digest):
    value = document(raw, digest)
    keys(value, {"schema", "purpose", "preparation_id", "boot_id", "template", "supervisor_parent",
                 "output", "declarations", "owner_envelope"})
    require(value["schema"] == SCHEMA and value["purpose"] == "ONE_ORIGINAL_Q2_HANDOFF", "HANDOFF_SCHEMA")
    require(type(value["preparation_id"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["preparation_id"]), "HANDOFF_PREPARATION")
    require(type(value["boot_id"]) is str and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value["boot_id"]), "HANDOFF_BOOT")
    static_template(value["template"])
    keys(value["owner_envelope"], OWNER_KEYS)
    owner = value["owner_envelope"]
    for key, amount in owner.items(): integer(amount, 1)
    require(owner["issued_ns"] < owner["deadline_ns"] <= owner["issued_ns"] + 120_000_000_000,
            "HANDOFF_ORIGINAL_OWNER_DEADLINE")
    require(8 * 1024**2 <= owner["storage_bytes"] <= 64 * 1024**2 and 20 <= owner["storage_inodes"] <= 4096
            and owner["output_bytes"] == 2 * PIPE_LIMIT + 4096
            and owner["memory_bytes"] <= 1024**3 and owner["pids"] <= 64, "HANDOFF_OWNER_COSTS")
    return value


def modules(template, repository):
    """Install one verified source importer; never import via arbitrary sys.path."""
    retained = {}
    for name in ("q2_prepare_run", "q2_fixture_check", "q2_supervisor"):
        relative = "tests/e3_host/" + name + ".py"
        raw = protected(str(repository / relative))
        require(template["launcher"]["source"]["files"].get(relative) == sha(raw), "HANDOFF_SOURCE_DIGEST")
        retained[name] = raw
    result = []
    for name in ("q2_supervisor", "q2_fixture_check"):
        module = ModuleType("_handoff_" + name)
        module.__file__ = str(repository / "tests/e3_host" / (name + ".py"))
        exec(compile(retained[name], module.__file__, "exec", dont_inherit=True), module.__dict__)
        result.append(module)
    supervisor, checker = result
    launcher = supervisor.load_source(template, repository)
    return supervisor, checker, launcher


def clock(plan, end=None):
    from local_hand_jobs import budget
    now = budget.current_clock()
    owner = plan["owner_envelope"]
    require(now["boot_id"] == plan["boot_id"] and owner["issued_ns"] <= now["boottime_ns"]
            < (owner["deadline_ns"] if end is None else min(end, owner["deadline_ns"])), "HANDOFF_ORIGINAL_DEADLINE_OR_BOOT")
    return now


def issue(plan, supervisor, now):
    """Pure issuance of both original deadlines exactly once, before launch."""
    require(now["boot_id"] == plan["boot_id"], "HANDOFF_BOOT")
    value = copy.deepcopy(plan["template"])
    static_template(value)
    issued = integer(now["boottime_ns"], plan["owner_envelope"]["issued_ns"])
    for env in (value["supervisor_envelope"], value["launcher"]["controller_envelope"]):
        candidate = supervisor.candidate(env["controller"])
        env.update(issued_ns=issued, deadline_ns=issued + candidate.runtime_max_usec * 1000)
    target, own = value["launcher"]["controller_envelope"], value["supervisor_envelope"]
    require(target["deadline_ns"] + target["controller"]["timeout_stop_usec"] * 1000 + 2_000_000_000
            <= own["deadline_ns"] and own["deadline_ns"] + own["controller"]["timeout_stop_usec"] * 1000 + 2_000_000_000
            <= plan["owner_envelope"]["deadline_ns"], "HANDOFF_ORIGINAL_CLEANUP_BUDGET")
    return dict(schema=ENVELOPE_SCHEMA, plan=copy.deepcopy(plan), fixture=value)


def envelope(raw, digest, supervisor):
    value = document(raw, digest)
    keys(value, {"schema", "plan", "fixture"})
    require(value["schema"] == ENVELOPE_SCHEMA, "HANDOFF_ENVELOPE_SCHEMA")
    plan_raw = encoded(value["plan"], LIMIT)
    plan = decode(plan_raw, sha(plan_raw))
    issued = value["fixture"]["supervisor_envelope"]["issued_ns"]
    require(value == issue(plan, supervisor, dict(boot_id=plan["boot_id"], boottime_ns=issued)), "HANDOFF_ENVELOPE_CHANGED")
    return value


def binding(value, supervisor, launcher):
    """Pure validation with declared-only placeholders, never host admission."""
    from admin.local_hand_quota_observer import q2_config as c
    fixture = copy.deepcopy(value["fixture"])
    candidate = supervisor.candidate(fixture["supervisor_envelope"]["controller"])
    fixture["supervisor_envelope"]["controller"] = {"schema": "local-hand-q1-controller/v1", **asdict(candidate)}
    result = supervisor.validate(fixture, launcher, clock(value["plan"]))
    plan = value["plan"]; parent = c.identity(plan["supervisor_parent"])
    require(parent["path"] == str(Path(candidate.cgroup).parent), "HANDOFF_SUPERVISOR_PARENT")
    # Charge the management endpoint in addition to every child role. Its
    # declared reservation is original authority; it is not a measured peak.
    capacity = result["installation"]["capacity"]
    costs = {key: result["totals"][key] + plan["owner_envelope"][key] for key in result["totals"]}
    require(all(amount <= capacity["management"][key] for key, amount in costs.items()), "HANDOFF_COMBINED_CAPACITY")
    for kind in ("bytes", "inodes"):
        used = costs["storage_" + kind] + capacity["retained_" + kind]
        used += sum(domain["hard_" + kind] for domain in capacity["domains"])
        require(used <= capacity["ceiling_" + kind], "HANDOFF_GLOBAL_STORAGE")
    selected = [plan[key] for key in ("output", "declarations")]
    prior = []
    def paths(item):
        if type(item) is dict:
            if "path" in item and type(item["path"]) is str: prior.append(item)
            for child in item.values(): paths(child)
        elif type(item) is list:
            for child in item: paths(child)
    paths(fixture)
    for pin in selected:
        c.identity(pin)
        require(all(not c.overlap(pin["path"], old["path"]) for old in prior), "HANDOFF_OUTPUT_OVERLAP")
        require(all((pin["device"], pin["inode"]) != (old.get("device"), old.get("inode")) for old in prior), "HANDOFF_OUTPUT_ALIAS")
        prior.append(pin)
    result["costs_with_owner"] = costs
    return result


def owner_identity(plan, admitted):
    from admin.local_hand_quota_observer import controller_guard as guard, q2_config as c
    from admin.local_hand_quota_observer.systemd_runtime import _fixed_read, _own_cgroup
    require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0, "HANDOFF_ROOT_ENDPOINT_REQUIRED")
    require(_fixed_read("/proc/1/comm", 128).strip() == b"systemd", "HANDOFF_SYSTEMD_REQUIRED")
    expected = admitted["installation"]["initial_userns"]
    for path in ("/proc/self/ns/user", "/proc/1/ns/user"):
        info = os.stat(path)
        require((info.st_dev, info.st_ino) == (expected["device"], expected["inode"]), "HANDOFF_INITIAL_USERNS")
    own = _own_cgroup()
    require(not c.overlap(own, plan["supervisor_parent"]["path"]), "HANDOFF_ENDPOINT_IN_STOP_TREE")
    stdout, stderr = guard._pipe_identity(1), guard._pipe_identity(2)
    require(stdout != stderr, "HANDOFF_ENDPOINT_PIPE_ALIAS")
    for name in ("python", "systemctl", "systemd_run"):
        fd = c.executable(admitted["installation"]["programs"][name])
        try:
            if name == "python":
                executable, actual = os.fstat(fd), os.stat("/proc/self/exe")
                require((executable.st_dev, executable.st_ino) == (actual.st_dev, actual.st_ino), "HANDOFF_INTERPRETER")
        finally: os.close(fd)
    return dict(pid=os.getpid(), cgroup=own, stdout=list(stdout), stderr=list(stderr), boot_id=plan["boot_id"],
                self_exit_verified=False, original_management_session_exit_required=True)


def same_pid_bind(value, supervisor, launcher):
    """Bind only real current identity; original bytes/times are immutable."""
    from admin.local_hand_quota_observer import controller_guard as guard
    from admin.local_hand_quota_observer.protected_inputs import open_protected
    from admin.local_hand_quota_observer.systemd_runtime import _own_cgroup
    plan = value["plan"]; original = value["fixture"]
    clock(plan, original["launcher"]["controller_envelope"]["deadline_ns"])
    static = original["supervisor_envelope"]["controller"]
    require(_own_cgroup() == static["cgroup"], "HANDOFF_BIND_CGROUP")
    fd = open_protected("/sys/fs/cgroup" + static["cgroup"], directory=True)
    try: info = os.fstat(fd)
    finally: os.close(fd)
    observed = dict(invocation_id=os.environ.get("INVOCATION_ID"), pid=os.getpid(),
                    cgroup_device=info.st_dev, cgroup_inode=info.st_ino)
    actual = dict(static, **{key: observed[key] for key in DYNAMIC})
    guard.decode_controller(actual)
    bound = copy.deepcopy(original)
    bound["supervisor_envelope"]["controller"] = actual
    admitted = supervisor.validate(bound, launcher, clock(plan))
    host = supervisor.admit(bound, admitted)
    require(host["pid"] == observed["pid"] == os.getpid(), "HANDOFF_MAINPID_CHANGED")
    require(host["controller"] == actual and host["boot_id"] == plan["boot_id"], "HANDOFF_BIND_IDENTITY_CHANGED")
    require({key: bound["supervisor_envelope"][key] for key in bound["supervisor_envelope"] if key != "controller"}
            == {key: original["supervisor_envelope"][key] for key in original["supervisor_envelope"] if key != "controller"},
            "HANDOFF_ORIGINAL_ENVELOPE_CHANGED")
    return bound, observed


def publish(directory, name, raw, launcher):
    """Single atomic publication, preserving any interrupted pending member."""
    import ctypes
    pending = name + ".pending"
    launcher.save(directory, pending, raw)
    library = ctypes.CDLL(None, use_errno=True)
    rename = library.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(directory, os.fsencode(pending), directory, os.fsencode(name), 1) != 0:
        code = ctypes.get_errno(); raise OSError(code, os.strerror(code))
    os.fsync(directory)


def bound_role(value, supervisor, checker, launcher, repository):
    from admin.local_hand_quota_observer import q2_config as c
    plan = value["plan"]; output = c.pinned_directory(plan["declarations"])
    stopped = threading.Event(); previous = signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    try:
        bound, original = same_pid_bind(value, supervisor, launcher)
        raw = encoded(bound, LIMIT)
        launcher.save(output, "bound-supervisor.json", raw)
        report = checker.check(raw, sha(raw), repository, admitted=(bound, supervisor, launcher))
        launcher.save(output, "fixture-check.json", encoded(report))
        require(report["status"] == "CHECKED", "HANDOFF_FIXTURE_NOT_CHECKED")
        require(os.getpid() == original["pid"] and not stopped.is_set(), "HANDOFF_MAINPID_CHANGED_OR_STOPPED")
        clock(plan, bound["launcher"]["controller_envelope"]["deadline_ns"])
        # Direct function call in the exact checked MainPID. No exec or fork.
        result = supervisor.supervise(bound, launcher, repository)
        require(os.getpid() == original["pid"], "HANDOFF_MAINPID_CHANGED")
        marker = dict(schema="local-hand-q2-supervisor-handoff-result/v1", envelope_sha256=sha(encoded(value, LIMIT)),
                      original=original, result=result, completed_ns=clock(plan)["boottime_ns"],
                      bound_fixture_sha256=sha(raw))
        publish(output, "supervisor-result.json", encoded(marker), launcher)
        print(json.dumps(dict(schema=RESULT_SCHEMA, status=result["status"], q3_accepted=False,
                              production_supported=False), sort_keys=True), flush=True)
        # Independently stopped after durable result publication. The owner
        # must still prove this client's actual exit and both original EOFs.
        while not stopped.wait(0.025):
            clock(plan, bound["supervisor_envelope"]["deadline_ns"])
        return 0 if result["status"] == "CONTROLLER_CLOSED" and result.get("sealed") is True else 3
    finally:
        signal.signal(signal.SIGTERM, previous)
        os.close(output)


def command(value, supervisor, admitted, repository, path, digest):
    # Reuse the fixed service restriction contract, changing only the pinned
    # role entry. There is no user-supplied command or shell interpolation.
    spec = supervisor.candidate(value["fixture"]["supervisor_envelope"]["controller"])
    argv = supervisor.command(value["fixture"], dict(target=spec, installation=admitted["installation"]), repository, path, digest)
    index = argv.index(str(repository / "tests/e3_host/q2_supervisor.py"))
    return argv[:index] + [str(repository / "tests/e3_host/q2_prepare_run.py"), "--bind", "--envelope", path, "--sha256", digest]


def storage(plan, output, declarations):
    total = 0
    for directory, members in ((output, FILES), (declarations, DECLARATIONS)):
        block = integer(os.fstatvfs(directory).f_frsize, 1)
        total += max(block, os.fstat(directory).st_blocks * 512) + block
        total += sum((maximum + block - 1) // block * block for maximum in members.values())
    require(total <= plan["owner_envelope"]["storage_bytes"] and len(FILES) + len(DECLARATIONS) + 4
            <= plan["owner_envelope"]["storage_inodes"], "HANDOFF_STORAGE_RESERVATION")


def seal_members(plan, output, declarations, launcher):
    """Bound member enumeration and recheck held/path identities at sealing."""
    files = {}; allocated = 0
    for pin, descriptor, limits in ((plan["output"], output, FILES),
                                     (plan["declarations"], declarations, DECLARATIONS)):
        def same():
            linked, held = os.stat(pin["path"], follow_symlinks=False), os.fstat(descriptor)
            require(stat.S_ISDIR(linked.st_mode) and (linked.st_dev, linked.st_ino) ==
                    (held.st_dev, held.st_ino) == (pin["device"], pin["inode"]), "HANDOFF_SEAL_DIRECTORY_CHANGED")
        same(); names = set(); expected = set(limits) - {"seal.json"}
        with os.scandir(descriptor) as entries:
            for entry in entries:
                require(entry.name in expected and len(names) < len(expected), "HANDOFF_SEAL_MEMBERS")
                names.add(entry.name)
        require(names == expected, "HANDOFF_SEAL_MEMBERS")
        block = integer(os.fstatvfs(descriptor).f_frsize, 1)
        allocated += max(block, os.fstat(descriptor).st_blocks * 512)
        for name in sorted(names):
            path = pin["path"] + "/" + name
            before = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            raw = launcher.protected(path, limits[name])
            after = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            linked = os.stat(path, follow_symlinks=False)
            require(stat.S_ISREG(after.st_mode) and all(getattr(before, key) == getattr(after, key) ==
                    getattr(linked, key) for key in ("st_dev", "st_ino", "st_size", "st_blocks", "st_mtime_ns", "st_ctime_ns"))
                    and len(raw) == after.st_size, "HANDOFF_SEAL_MEMBER_CHANGED")
            allocated += max(after.st_blocks * 512, (len(raw) + block - 1) // block * block)
            files[path] = dict(sha256=sha(raw), bytes=len(raw))
        if "seal.json" in limits:
            allocated += (limits["seal.json"] + block - 1) // block * block + block
        same()
    require(allocated <= plan["owner_envelope"]["storage_bytes"] and len(files) + 3
            <= plan["owner_envelope"]["storage_inodes"], "HANDOFF_SEAL_STORAGE")
    return files


def marker(value, original, launcher):
    path = value["plan"]["declarations"]["path"] + "/supervisor-result.json"
    try: raw = launcher.protected(path, RECORD_LIMIT)
    except FileNotFoundError: return None
    item = document(raw, sha(raw), RECORD_LIMIT)
    keys(item, {"schema", "envelope_sha256", "original", "result", "completed_ns", "bound_fixture_sha256"})
    require(item["schema"] == "local-hand-q2-supervisor-handoff-result/v1" and item["original"] == original
            and item["envelope_sha256"] == sha(encoded(value, LIMIT)), "HANDOFF_CHILD_RESULT_BINDING")
    integer(item["completed_ns"], value["fixture"]["supervisor_envelope"]["issued_ns"],
            value["fixture"]["supervisor_envelope"]["deadline_ns"] - 1)
    require(type(item["result"]) is dict and item["result"].get("q3_accepted") is False
            and item["result"].get("production_supported") is False
            and item["result"].get("independent_supervisor_stop_required") is True, "HANDOFF_CHILD_SCOPE")
    bound = copy.deepcopy(value["fixture"])
    bound["supervisor_envelope"]["controller"].update({key: original[key] for key in DYNAMIC})
    require(sha(encoded(bound, LIMIT)) == item["bound_fixture_sha256"], "HANDOFF_CHILD_FIXTURE_CHANGED")
    return item


def run_original(plan, repository, *, loaded=None):
    """One explicit handoff. The caller supplies its original finite envelope."""
    plan_raw = encoded(plan, LIMIT); plan = decode(plan_raw, sha(plan_raw))
    result = dict(schema=RESULT_SCHEMA, status="BLOCKED", q2_accepted=False, q3_accepted=False,
                  production_supported=False, original_management_session_exit_required=True,
                  owner_self_exit_verified=False, scope="ONE_ORIGINAL_Q2_HANDOFF", sealed=False)
    output = declarations = None; process = worker = controls = None
    original = child = value = None; capture = {}; stop = {}; storage_admitted = False
    try:
        supervisor, checker, launcher = loaded or modules(plan["template"], repository)
        value = issue(plan, supervisor, clock(plan))
        admitted = binding(value, supervisor, launcher)
        owner = owner_identity(plan, admitted)
        control_value = dict(controller_parent=plan["supervisor_parent"],
                             supervisor_envelope=dict(output_bytes=PIPE_LIMIT))
        control_binding = dict(target=supervisor.candidate(value["fixture"]["supervisor_envelope"]["controller"]),
                               installation=admitted["installation"], boot_id=plan["boot_id"])
        controls = supervisor.Controls(control_value, control_binding)
        work_end = value["fixture"]["supervisor_envelope"]["deadline_ns"]
        end = plan["owner_envelope"]["deadline_ns"]
        require(controls.empty(), "HANDOFF_SUPERVISOR_PARENT_OCCUPIED")
        before = controls.show(work_end)
        require(before["Id"] == control_binding["target"].unit and before["LoadState"] == "not-found"
                and before["Job"] in ("", "0"), "HANDOFF_ALREADY_STARTED")
        output = launcher.directory(plan["output"], 0o700)
        declarations = launcher.directory(plan["declarations"], 0o700)
        storage(plan, output, declarations)
        result.update(status="INCOMPLETE", evidence=plan["output"]["path"])
        envelope_raw = encoded(value, LIMIT)
        launcher.save(output, "reservation.json", encoded(dict(schema=SCHEMA, plan_sha256=sha(plan_raw), owner=owner,
                      envelope_sha256=sha(envelope_raw), costs=admitted["costs_with_owner"]), LIMIT))
        # A concurrent loser at the create-only reservation must not add its
        # failure records to the successful original owner's directory.
        storage_admitted = True
        launcher.save(declarations, "envelope.json", envelope_raw)
        argv = command(value, supervisor, admitted, repository, plan["declarations"]["path"] + "/envelope.json", sha(envelope_raw))
        started = clock(plan, work_end)["boottime_ns"]
        launcher.save(output, "delivery.json", encoded(dict(unit=control_binding["target"].unit, started_ns=started,
                      deadline_ns=end, argv_sha256=sha(encoded(argv)))))
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            close_fds=True, bufsize=0, cwd="/", env=dict(PATH="/usr/bin:/bin", LANG="C", LC_ALL="C", SYSTEMD_COLORS="0"))
        from admin.local_hand_quota_observer.q2_capture import capture_existing
        def collect():
            try:
                capture.update(capture_existing(process, boot_id=plan["boot_id"], started_ns=started, deadline_ns=end, limit=PIPE_LIMIT))
            except Exception as error:
                capture.update(complete=False, returncode=process.poll(), error=reason(error), eof=[], stdout=b"", stderr=b"")
                for stream in (process.stdout, process.stderr):
                    try: stream.close()
                    except Exception: pass
        worker = threading.Thread(target=collect, daemon=True); worker.start()
        static = value["fixture"]["supervisor_envelope"]["controller"]
        original = supervisor.observe_start(controls, static, process, work_end)
        launcher.save(output, "invocation.json", encoded(original))
        for _ in range(4800):
            clock(plan, work_end)
            child = marker(value, original, launcher)
            if child is not None: break
            require(process.poll() is None and not capture, "HANDOFF_SUPERVISOR_EXITED_EARLY")
            time.sleep(0.025)
        require(child is not None, "HANDOFF_RESULT_MISSING")
        supervisor.stop_original(controls, static, original, end, stop)
        while worker.is_alive():
            clock(plan); worker.join(0.025)
        require(capture.get("complete") is True and capture.get("returncode") == 0 and capture.get("stderr") == b"",
                "HANDOFF_ORIGINAL_CAPTURE_INCOMPLETE")
        summary = document(capture["stdout"], sha(capture["stdout"]), PIPE_LIMIT)
        require(summary == dict(schema=RESULT_SCHEMA, status="CONTROLLER_CLOSED", q3_accepted=False, production_supported=False)
                and child["result"].get("status") == "CONTROLLER_CLOSED" and child["result"].get("sealed") is True,
                "HANDOFF_SUPERVISOR_NOT_CLOSED")
        require(controls.empty() and all(cap.done for _, cap in controls.calls), "HANDOFF_FINAL_EXIT_UNPROVEN")
        result.update(status="SUPERVISOR_CLOSED", original=original, stopped=True,
                      closed_ns=clock(plan)["boottime_ns"])
    except Exception as error:
        result["reason"] = reason(error)
    finally:
        failures = []
        def retain(action, code):
            try: action()
            except Exception:
                failures.append(code); result.update(status="INCOMPLETE", reason=code)
        if controls is not None and original is not None and not stop.get("attempted"):
            retain(lambda: supervisor.stop_original(controls, value["fixture"]["supervisor_envelope"]["controller"],
                    original, plan["owner_envelope"]["deadline_ns"], stop), "HANDOFF_CLEANUP_UNPROVEN")
        if worker is not None:
            def settle():
                while worker.is_alive():
                    clock(plan); worker.join(0.025)
            retain(settle, "HANDOFF_CAPTURE_UNFINISHED")
        if process is not None and process.poll() is None:
            # Terminating the local manager client is not target stop proof.
            retain(process.kill, "HANDOFF_CLIENT_KILL_UNCERTAIN")
            result.update(status="INCOMPLETE", reason="HANDOFF_CLIENT_EXIT_UNPROVEN")
        if output is not None and storage_admitted:
            captured = dict(capture)
            for name in ("stdout", "stderr"):
                raw = captured.pop(name, b"")
                retain(lambda name=name, raw=raw: launcher.save(output, "supervisor." + name, raw), "HANDOFF_CAPTURE_PERSIST")
            records = {"capture.json": captured, "stop.json": stop,
                       "controls.json": [] if controls is None else controls.evidence()}
            if child is not None: records["child-result.json"] = child
            for name, record in records.items():
                retain(lambda name=name, record=record: launcher.save(output, name, encoded(record)), "HANDOFF_RECORD_PERSIST")
            result["cleanup_errors"] = failures
            provisional = dict(result)
            if provisional["status"] == "SUPERVISOR_CLOSED": provisional["status"] = "CLOSURE_OBSERVED_SEAL_PENDING"
            retain(lambda: launcher.save(output, "result.json", encoded(provisional)), "HANDOFF_RESULT_PERSIST")
            if result["status"] == "SUPERVISOR_CLOSED" and not failures:
                def seal():
                    clock(plan)
                    require(controls.empty(), "HANDOFF_SEAL_PARENT_NOT_EMPTY")
                    files = seal_members(plan, output, declarations, launcher)
                    launcher.save(output, "seal.json", encoded(dict(schema="local-hand-q2-handoff-seal/v1",
                        status="SUPERVISOR_CLOSED", envelope_sha256=sha(encoded(value, LIMIT)), original=original,
                        files=files, owner_self_exit_verified=False, original_management_session_exit_required=True,
                        q2_accepted=False, q3_accepted=False, production_supported=False)))
                retain(seal, "HANDOFF_SEAL_UNPROVEN")
                if not failures: result["sealed"] = True
        for descriptor in (output, declarations):
            if descriptor is not None: retain(lambda descriptor=descriptor: os.close(descriptor), "HANDOFF_OUTPUT_CLOSE")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan"); parser.add_argument("--envelope"); parser.add_argument("--sha256")
    parser.add_argument("--bind", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    result = dict(schema=RESULT_SCHEMA, status="BLOCKED", q2_accepted=False, q3_accepted=False,
                  production_supported=False, owner_self_exit_verified=False, original_management_session_exit_required=True)
    try:
        require(bool(args.sha256 and (args.envelope if args.bind else args.plan))
                and not (args.plan and args.envelope), "EXPLICIT_PRIVATE_HANDOFF_REQUIRED")
        require(sys.platform.startswith("linux") and sys.flags.isolated and sys.dont_write_bytecode,
                "HANDOFF_ISOLATED_LINUX_PYTHON")
        repository = Path(__file__).resolve().parents[2]
        if args.bind:
            raw = protected(args.envelope); preliminary = document(raw, args.sha256)
            loaded = modules(preliminary["plan"]["template"], repository)
            return bound_role(envelope(raw, args.sha256, loaded[0]), *loaded, repository)
        plan = decode(protected(args.plan), args.sha256)
        result = run_original(plan, repository)
    except Exception as error:
        result["reason"] = reason(error)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "SUPERVISOR_CLOSED" and result.get("sealed") is True else 3


if __name__ == "__main__":
    raise SystemExit(main())
