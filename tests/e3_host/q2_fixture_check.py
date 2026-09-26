"""Read-only batch admission of the exact supervisor/v1 + launcher/v2 fixture.

Run with the same already supervised root service and original envelope as the
supervisor. No reservation, grant, database, socket, target service or quota is
created. CHECKED is a point-in-time prerequisite report, never launch authority
or a quota/exit/qualification result. Kernel filesystem waits still require the
existing independent supervisor; O_NONBLOCK is not a disk-I/O timeout.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import importlib.util
import json
import marshal
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time
from types import ModuleType

SCHEMA = "local-hand-q2-fixture-check/v1"
LIMIT = 2 * 1024 * 1024
PHASES = ("preflight", "business", "evidence")
PACKAGES = ("local_hand", "local_hand_connect", "local_hand_jobs", "local_hand_mcp")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def reason(error):
    text = getattr(error, "code", str(error) if isinstance(error, ValueError) else type(error).__name__)
    return text if type(text) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", text) else type(error).__name__


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "FIXTURE_DUPLICATE_KEY")
        value[key] = item
    return value


def document(raw, maximum=LIMIT):
    require(type(raw) is bytes and len(raw) <= maximum, "FIXTURE_FILE_LIMIT")
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("FIXTURE_NUMBER")))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(info):
    return tuple(getattr(info, name) for name in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid",
                                                "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))


def ordinary_access(fd, reader, bits, *, default_acl=False):
    """Conservative DAC check for the resident's cleared supplementary groups.

    It is a read-only prerequisite, not an impersonation or kernel access test.
    ACL-dependent access is unproven rather than guessed from the mode mask.
    """
    uid, gid = reader
    require(type(uid) is int and uid > 0 and type(gid) is int and gid > 0, "FIXTURE_ORDINARY_IDENTITY")
    info = os.fstat(fd)
    shift = 6 if info.st_uid == uid else 3 if info.st_gid == gid else 0
    require((info.st_mode >> shift) & bits == bits, "FIXTURE_ORDINARY_PATH_ACCESS")
    for name in ("system.posix_acl_access", "system.posix_acl_default") if default_acl else ("system.posix_acl_access",):
        try:
            os.getxattr(fd, name)
        except OSError as error:
            if error.errno in (errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP):
                continue
            raise
        raise ValueError("FIXTURE_ORDINARY_ACL_UNPROVEN")


def opened(path, *, owner=0, directory=False, reader=None, required_bits=4, ancestor_bits=5):
    """No symlink components; ordinary-owned ancestry is allowed only explicitly."""
    require(type(path) is str and path.startswith("/") and not path.startswith("//")
            and str(Path(path)) == path and ".." not in Path(path).parts and path != "/", "FIXTURE_PATH")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        if reader is not None:
            ordinary_access(fd, reader, ancestor_bits)
        parts = Path(path).parts[1:]
        for index, name in enumerate(parts):
            isdir = index + 1 < len(parts) or directory
            child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
                            | (os.O_DIRECTORY if isdir else 0), dir_fd=fd)
            os.close(fd); fd = child
            info = os.fstat(fd)
            require(info.st_uid in (0, owner) and not info.st_mode & 0o022
                    and (stat.S_ISDIR(info.st_mode) if isdir else
                         stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not info.st_mode & 0o6000),
                    "FIXTURE_PROTECTION")
            if reader is not None:
                ordinary_access(fd, reader, (5 if directory and index + 1 == len(parts) else ancestor_bits)
                                if isdir else required_bits)
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_fd(fd, maximum):
    before = os.fstat(fd)
    require(stat.S_ISREG(before.st_mode) and before.st_size <= maximum, "FIXTURE_FILE_LIMIT")
    raw = bytearray()
    while len(raw) <= maximum:
        block = os.read(fd, min(65536, maximum + 1 - len(raw)))
        if not block:
            break
        raw.extend(block)
    require(len(raw) <= maximum and identity(before) == identity(os.fstat(fd)), "FIXTURE_FILE_CHANGED")
    return bytes(raw)


def protected(path, maximum, *, owner=0):
    fd = opened(path, owner=owner)
    try:
        return read_fd(fd, maximum)
    finally:
        os.close(fd)


def fixed(path, maximum):
    """Only caller-fixed proc paths; no fixture path may use this weaker reader."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        return read_fd(fd, maximum)
    finally:
        os.close(fd)


def bootstrap(raw, digest, repository):
    require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest)
            and len(raw) <= LIMIT and sha(raw) == digest, "FIXTURE_DIGEST")
    preliminary = document(raw)
    files = preliminary["launcher"]["source"]["files"]
    retained = {}
    for name in ("q2_fixture_check", "q2_supervisor"):
        relative = "tests/e3_host/" + name + ".py"
        retained[name] = protected(str(repository / relative), LIMIT)
        require(files.get(relative) == sha(retained[name]), "FIXTURE_BOOTSTRAP_SOURCE")
    supervisor = ModuleType("_q2_checked_supervisor")
    supervisor.__file__ = str(repository / "tests/e3_host/q2_supervisor.py")
    exec(compile(retained["q2_supervisor"], supervisor.__file__, "exec", dont_inherit=True), supervisor.__dict__)
    value = supervisor.decode(raw, digest)
    require(supervisor.expected_status(value["launcher"]) == "CHAIN_CLOSED", "FIXTURE_THREE_PHASE_REQUIRED")
    launcher = supervisor.load_source(value, repository)
    return value, supervisor, launcher


class Report:
    def __init__(self):
        self.rows = []
        self.values = {}
        self.guard = None

    def probe(self, name, action, *, needs=()):
        if any(key not in self.values for key in needs):
            self.rows.append(dict(check=name, status="BLOCKED", reason="PREREQUISITE_UNPROVEN"))
            return None
        try:
            if self.guard is not None:
                self.guard()
            value = action()
            if self.guard is not None:
                self.guard()
            self.values[name] = value
            self.rows.append(dict(check=name, status="PASS"))
            return value
        except Exception as error:
            self.rows.append(dict(check=name, status="BLOCKED", reason=reason(error)))
            return None

    def result(self):
        return dict(schema=SCHEMA, status="CHECKED" if self.rows and all(row["status"] == "PASS" for row in self.rows)
                    else "BLOCKED", scope="READ_ONLY_EXISTING_PREREQUISITES", checks=self.rows,
                    q2_accepted=False, q3_accepted=False, production_supported=False,
                    quota_state="NOT_OBSERVED", execution_state="NOT_RUN", capacity_peak="NOT_MEASURED",
                    independent_supervisor_stop_required=True,
                    future_admission_required=["original_grant_reservation", "ordinary_identity_and_namespace",
                        "quota_and_enforcement", "three_phase_execution", "original_exit_and_eof", "supervisor_external_stop"])


def directory(pin, mode=0o700, owner=0, *, empty=True, gid=None):
    fd = opened(pin["path"], owner=owner, directory=True)
    try:
        info = os.fstat(fd)
        require((info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode)) ==
                (pin["device"], pin["inode"], owner, mode), "FIXTURE_DIRECTORY_IDENTITY")
        require(gid is None or info.st_gid == gid, "FIXTURE_DIRECTORY_GROUP")
        if empty:
            with os.scandir(fd) as entries:
                require(next(entries, None) is None, "FIXTURE_DIRECTORY_CONSUMED")
        require(identity(info) == identity(os.fstat(fd)), "FIXTURE_DIRECTORY_CHANGED")
    finally:
        os.close(fd)


def absent_endpoint(path):
    require(type(path) is str and str(Path(path)) == path and len(path.encode()) <= 107, "FIXTURE_ENDPOINT")
    fd = opened(str(Path(path).parent), directory=True)
    try:
        try:
            os.stat(Path(path).name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise ValueError("FIXTURE_ENDPOINT_CONSUMED")
    finally:
        os.close(fd)


def executable(pin):
    fd = opened(pin["path"])
    try:
        info = os.fstat(fd)
        require(info.st_mode & 0o111, "FIXTURE_EXECUTABLE_MODE")
        raw = read_fd(fd, 64 * 1024 * 1024)
        require(raw.startswith(b"\x7fELF") and sha(raw) == pin["sha256"], "FIXTURE_EXECUTABLE_DIGEST")
    finally:
        os.close(fd)


def static_binding(value, supervisor, repository):
    """Resident/installation binding checked without composing a mutable broker."""
    from local_hand_jobs import quota_contract as q
    nested = value["launcher"]; resident = nested["resident"]; install = resident["installation"]
    q._keys(resident, {"schema", "purpose", "entry", "installation", "policy", "ordinary", "principal",
                       "request", "plan", "phases"})
    require(resident["schema"] == "local-hand-q2-resident/v2" and resident["purpose"] == "ISOLATED_Q2_CHAIN"
            and resident["phases"] == list(PHASES), "FIXTURE_RESIDENT_VERSION")
    q.match(nested["session"], r"[0-9a-f]{64}")
    q._keys(install, {"package_root", "source_commit", "payload_digest", "files", "programs"})
    q._keys(install["programs"], {"python", "systemctl", "systemd_run"})
    q._keys(resident["ordinary"], {"uid", "gid", "parent", "broker_cgroup", "initial_userns"})
    q.integer(resident["ordinary"]["uid"], 1, 2**32-2); q.integer(resident["ordinary"]["gid"], 1, 2**32-2)
    require(1 <= len(install["files"]) <= 512, "FIXTURE_INSTALLED_FILE_COUNT")
    require(resident["entry"] == dict(path=str(repository / "tests/e3_host/q2_resident.py"),
            sha256=nested["source"]["files"]["tests/e3_host/q2_resident.py"]), "FIXTURE_RESIDENT_ENTRY")
    require(nested["setpriv"]["path"] == "/usr/bin/setpriv", "FIXTURE_SETPRIV")
    for name, digest in install["files"].items():
        q.match(name, r"(?:local_hand|local_hand_jobs|local_hand_mcp|local_hand_connect)/[a-z_][a-z0-9_]*\.py")
        require(nested["source"]["files"].get("tools/" + name) == digest, "FIXTURE_INSTALLED_SOURCE")
    templates = supervisor.templates(nested)
    for template in templates:
        ordinary = resident["ordinary"]; peer = template["peer"]
        require(install["source_commit"] == template["installation"]["source_commit"] == nested["source"]["commit"],
                "FIXTURE_SOURCE_BINDING")
        require(template["installation"]["tools_path"] == str(repository / "tools")
                and all(nested["source"]["files"].get("tools/" + name) == digest
                        for name, digest in template["installation"]["package_files"].items()), "FIXTURE_ADMIN_SOURCE_BINDING")
        require(ordinary["parent"] == peer["parent"] and ordinary["initial_userns"] == template["installation"]["initial_userns"]
                and ordinary["broker_cgroup"] == nested["controller_envelope"]["controller"]["cgroup"], "FIXTURE_RESIDENT_PARENT")
        work = [root for root in template["grant"]["roots"] if root["role"] == "work"]
        require(len(work) == 1 and (work[0]["uid"], work[0]["gid"]) == (ordinary["uid"], ordinary["gid"]), "FIXTURE_ACCOUNT_BINDING")
        require(peer["executable"]["path"] == install["programs"]["python"]["path"] and peer["runner"] ==
                dict(path=install["package_root"] + "/local_hand_jobs/runner.py", sha256=install["files"]["local_hand_jobs/runner.py"]),
                "FIXTURE_RUNNER_BINDING")
    return templates


def installed_release(nested):
    """Bounded flat-package inventory, including non-Python payload and metadata."""
    from local_hand import provenance
    install = nested["resident"]["installation"]; root = install["package_root"]
    metadata = document(protected(root + "/local_hand/" + provenance.METADATA_NAME, 65536), 65536)
    require(set(metadata) == {"schema_version", "product_version", "source_commit", "artifact_kind", "files"}
            and metadata["schema_version"] == provenance.BUILD_SCHEMA and metadata["product_version"] == provenance.VERSION
            and metadata["artifact_kind"] == "wheel" and metadata["source_commit"] == install["source_commit"], "FIXTURE_WHEEL_METADATA")
    actual = {}; caches = []
    for package in PACKAGES:
        fd = opened(root + "/" + package, directory=True)
        try:
            with os.scandir(fd) as entries:
                for entry in entries:
                    require(len(actual) < 512, "FIXTURE_INSTALLED_FILE_COUNT")
                    if package == "local_hand" and entry.name == provenance.METADATA_NAME:
                        continue
                    if entry.name == "__pycache__":
                        caches.append(package)
                        continue
                    require(re.fullmatch(r"[a-z_][a-z0-9_]*\.(?:py|sh|ps1)", entry.name), "FIXTURE_INSTALLED_EXTRA_FILE")
                    relative = package + "/" + entry.name
                    actual[relative] = sha(protected(root + "/" + relative, LIMIT))
        finally:
            os.close(fd)
        require(package + "/__init__.py" in actual, "FIXTURE_INSTALLED_PACKAGE")
    require(actual == metadata["files"] and {key: val for key, val in actual.items() if key.endswith(".py")} == install["files"],
            "FIXTURE_WHEEL_FILES")
    # Match the installed resident's source-bound cache contract. Keep the
    # reads bounded/no-follow instead of calling its pathname-based helper.
    require(sys.pycache_prefix is None, "FIXTURE_WHEEL_EXTERNAL_CACHE")
    pattern = re.compile(r"([a-z_][a-z0-9_]*)\." + re.escape(sys.implementation.cache_tag) + r"(?:\.opt-([12]))?\.pyc")
    for package in caches:
        cache = root + "/" + package + "/__pycache__"
        fd = opened(cache, directory=True)
        try:
            count = 0
            with os.scandir(fd) as entries:
                for entry in entries:
                    count += 1
                    require(count <= 3 * len(install["files"]), "FIXTURE_WHEEL_CACHE_COUNT")
                    match = pattern.fullmatch(entry.name)
                    require(match is not None, "FIXTURE_WHEEL_CACHE_NAME")
                    relative = package + "/" + match[1] + ".py"
                    require(relative in install["files"], "FIXTURE_WHEEL_CACHE_SOURCE")
                    raw = protected(root + "/" + relative, LIMIT)
                    require(sha(raw) == install["files"][relative], "FIXTURE_WHEEL_CACHE_SOURCE")
                    variants = []
                    for name in (root + "/" + relative, "tools/" + relative, relative):
                        compiled = compile(raw, name, "exec", dont_inherit=True, optimize=int(match[2] or "0"))
                        variants.append(marshal.dumps(compiled))
                    cached = protected(cache + "/" + entry.name, max(map(len, variants)) + 16)
                    require(cached[:4] == importlib.util.MAGIC_NUMBER and cached[16:] in variants, "FIXTURE_WHEEL_CACHE_BYTES")
        finally:
            os.close(fd)
    digest = sha(json.dumps(dict(schema_version="infra-local-hand-full-payload/v1", files=actual),
                            sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii"))
    require(digest == install["payload_digest"], "FIXTURE_WHEEL_PAYLOAD")
    return digest


def resident_paths(nested):
    """The root checker must not confuse its own access with resident access."""
    resident = nested["resident"]; installation = resident["installation"]
    uid, gid = resident["ordinary"]["uid"], resident["ordinary"]["gid"]
    from local_hand import provenance
    # q2_resident.protected opens EVERY directory with O_RDONLY|O_DIRECTORY;
    # its ancestors therefore need read+search, not only pathname traversal.
    paths = [(resident["entry"]["path"], 0, 4)]
    paths += [(installation["package_root"] + "/" + name, 0, 4) for name in
              (*installation["files"], "local_hand/" + provenance.METADATA_NAME)]
    paths += [(pin["path"], 0, 5) for pin in installation["programs"].values()]
    for path, owner, bits in paths:
        fd = opened(path, owner=owner, reader=(uid, gid), required_bits=bits)
        os.close(fd)
    # Policy.from_file uses lstat + one leaf open. A protected 0711 ancestor
    # can legitimately work there, so do not require directory read access.
    fd = opened(resident["policy"]["path"], owner=uid, reader=(uid, gid), ancestor_bits=1)
    os.close(fd)
    for package in PACKAGES:
        cache = installation["package_root"] + "/" + package + "/__pycache__"
        try:
            fd = opened(cache, directory=True, reader=(uid, gid))
        except FileNotFoundError:
            continue
        try:
            with os.scandir(fd) as entries:
                for count, entry in enumerate(entries, 1):
                    require(count <= 3 * len(installation["files"]), "FIXTURE_WHEEL_CACHE_COUNT")
                    child = opened(cache + "/" + entry.name, reader=(uid, gid))
                    os.close(child)
        finally:
            os.close(fd)
    # resident.json is created here later with 0644. A default ACL could make
    # that future read differ from the current directory's ordinary mode bits.
    fd = opened(nested["declarations"]["path"], directory=True, reader=(uid, gid))
    try:
        ordinary_access(fd, (uid, gid), 5, default_acl=True)
    finally:
        os.close(fd)


def policy_snapshot(nested):
    from local_hand_jobs import policy as p, contract
    resident = nested["resident"]; pin = resident["policy"]; ordinary = resident["ordinary"]
    require(set(pin) == {"path", "digest"}, "FIXTURE_POLICY_PIN")
    fd = opened(pin["path"], owner=ordinary["uid"])
    try:
        info = os.fstat(fd)
        require(info.st_uid == ordinary["uid"] and stat.S_IMODE(info.st_mode) == 0o600, "FIXTURE_POLICY_OWNER")
        raw = read_fd(fd, 65536)
    finally:
        os.close(fd)
    policy = p.Policy(contract.strict_loads(raw))
    require(policy.policy_digest == pin["digest"] and policy.source_commit == resident["installation"]["source_commit"]
            and policy.installed_payload_digest == resident["installation"]["payload_digest"]
            and policy.execution_entrypoint == resident["installation"]["package_root"] + "/local_hand_jobs/cli.py",
            "FIXTURE_POLICY_BINDING")
    require(policy.config["process_manager"]["cgroup"] == "/sys/fs/cgroup" + ordinary["parent"]["path"], "FIXTURE_POLICY_PARENT")
    return policy


def empty_ledger(policy, uid, generation):
    """Inspect an existing quiescent DB in RAM; never open SQLite on host paths."""
    root = opened(policy.broker_root, owner=uid, directory=True)
    try:
        parent = os.fstat(root)
        require(parent.st_uid == uid and stat.S_IMODE(parent.st_mode) == 0o700, "FIXTURE_LEDGER_PARENT")
        def sidecars():
            for name in ("jobs.sqlite-wal", "jobs.sqlite-shm", "jobs.sqlite-journal"):
                try: os.stat(name, dir_fd=root, follow_symlinks=False)
                except FileNotFoundError: continue
                raise ValueError("FIXTURE_LEDGER_SIDECAR_REQUIRES_ORDINARY_ADMISSION")
        sidecars()
        fd = os.open("jobs.sqlite", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=root)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_uid == uid and before.st_nlink == 1
                    and stat.S_IMODE(before.st_mode) == 0o600, "FIXTURE_LEDGER_FILE")
            raw = read_fd(fd, 32 * 1024 * 1024)
            # A closed WAL-mode database still has header 2/2. Only the in-memory
            # snapshot changes journal mode; the host bytes are never modified.
            require(raw.startswith(b"SQLite format 3\0") and len(raw) >= 100, "FIXTURE_LEDGER_FORMAT")
            snapshot = bytearray(raw); snapshot[18:20] = b"\1\1"
            db = sqlite3.connect(":memory:")
            try:
                db.deserialize(bytes(snapshot)); db.execute("PRAGMA query_only=ON")
                end = time.monotonic() + 1
                db.set_progress_handler(lambda: int(time.monotonic() >= end), 100)
                tables = dict(db.execute("SELECT name,type FROM sqlite_schema WHERE name IN ('metadata','operations','events','leases','counters')"))
                require(tables == dict.fromkeys(("metadata", "operations", "events", "leases", "counters"), "table"), "FIXTURE_LEDGER_SCHEMA")
                require(db.execute("PRAGMA quick_check").fetchall() == [("ok",)], "FIXTURE_LEDGER_INTEGRITY")
                metadata = dict(db.execute("SELECT key,value FROM metadata"))
                require(set(metadata) == {"schema", "authority_id", "ledger_id"} and metadata["schema"] == "1"
                        and metadata["authority_id"] == policy.authority_id and bool(metadata["ledger_id"]), "FIXTURE_LEDGER_IDENTITY")
                require(all(db.execute("SELECT COUNT(*) FROM " + name).fetchone()[0] == 0
                            for name in ("operations", "events", "leases")), "FIXTURE_LEDGER_CONSUMED")
                count = db.execute("SELECT value FROM counters WHERE key='generation'").fetchone()
                require(count is not None and generation == [policy.generation, count[0]], "FIXTURE_LEDGER_GENERATION")
            finally:
                db.close()
            sidecars()
            require(identity(before) == identity(os.fstat(fd)) == identity(os.stat("jobs.sqlite", dir_fd=root, follow_symlinks=False))
                    and identity(parent) == identity(os.fstat(root)), "FIXTURE_LEDGER_CHANGED")
        finally:
            os.close(fd)
    finally:
        os.close(root)


def namespace(pin):
    for path in ("/proc/self/ns/user", "/proc/1/ns/user"):
        info = os.stat(path)
        require(pin == dict(device=info.st_dev, inode=info.st_ino), "FIXTURE_INITIAL_NAMESPACE")


def manager_delegation(controls, ordinary, end):
    fields = {"Id", "LoadState", "ActiveState", "SubState", "ControlGroup", "MainPID", "InvocationID", "User", "Delegate"}
    unit = "user@" + str(ordinary["uid"]) + ".service"
    raw = controls.call(("show", unit, "--all", "--property=" + ",".join(sorted(fields))), end)
    facts = unique(line.split("=", 1) for line in raw.decode("ascii").splitlines())
    require(set(facts) == fields and all(facts.get(key) == val for key, val in dict(Id=unit, LoadState="loaded",
            ActiveState="active", SubState="running", User=str(ordinary["uid"]), Delegate="yes").items()), "FIXTURE_USER_MANAGER")
    require(re.fullmatch(r"[0-9a-f]{32}", facts["InvocationID"]) and re.fullmatch(r"[1-9][0-9]{0,19}", facts["MainPID"])
            and facts["ControlGroup"] != "/" and ordinary["parent"]["path"].startswith(facts["ControlGroup"] + "/"), "FIXTURE_DELEGATION")
    for name in ("cgroup.controllers", "cgroup.subtree_control"):
        data = protected("/sys/fs/cgroup" + facts["ControlGroup"] + "/" + name, 4096, owner=ordinary["uid"])
        require({b"cpu", b"memory", b"pids"} <= set(data.split()), "FIXTURE_CONTROLLERS")


def storage_geometry(value, supervisor):
    descriptors = []
    try:
        for key in ("output", "declarations"):
            pin = value[key]
            fd = opened(pin["path"], directory=True); descriptors.append(fd)
            info = os.fstat(fd)
            require((info.st_dev, info.st_ino) == (pin["device"], pin["inode"]), "FIXTURE_DIRECTORY_IDENTITY")
        return supervisor.storage_capacity(value, *descriptors)
    finally:
        for fd in descriptors:
            os.close(fd)


def check(raw, digest, repository):
    report = Report()
    report.probe("linux", lambda: require(sys.platform.startswith("linux"), "LINUX_REQUIRED"))
    if "linux" not in report.values:
        return report.result()
    report.probe("systemd_pid1", lambda: require(fixed("/proc/1/comm", 4096).strip() == b"systemd", "SYSTEMD_REQUIRED"))
    report.probe("administrator", lambda: require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0,
                                                "ADMINISTRATOR_REQUIRED"))
    loaded = report.probe("protected_source", lambda: bootstrap(raw, digest, repository))
    if loaded is None:
        report.probe("fixture_checks", lambda: None, needs=("protected_source",))
        return report.result()
    value, supervisor, launcher = loaded
    from local_hand_jobs import budget, quota_lifecycle
    clock = report.probe("clock", budget.current_clock)
    binding = report.probe("declaration_capacity_geometry", lambda: supervisor.validate(value, launcher, clock), needs=("clock",))
    if binding is not None:
        def original_time():
            now = budget.current_clock()
            require(now["boot_id"] == binding["boot_id"] and value["supervisor_envelope"]["issued_ns"]
                    <= now["boottime_ns"] < value["launcher"]["controller_envelope"]["deadline_ns"], "FIXTURE_ORIGINAL_DEADLINE")
        report.guard = original_time
    templates = report.probe("resident_static_binding", lambda: static_binding(value, supervisor, repository))
    nested = value["launcher"]; resident = nested["resident"]
    report.probe("initial_namespace", lambda: namespace(resident["ordinary"]["initial_userns"]))
    report.probe("installed_wheel", lambda: installed_release(nested), needs=("resident_static_binding",))
    policy = report.probe("ordinary_policy", lambda: policy_snapshot(nested), needs=("resident_static_binding",))
    report.probe("ordinary_resident_path_access", lambda: resident_paths(nested), needs=("resident_static_binding",))
    report.probe("original_empty_ledger", lambda: empty_ledger(policy, resident["ordinary"]["uid"], nested["assembly"]["broker_generation"]),
                 needs=("ordinary_policy",))
    pins = [("setpriv", nested["setpriv"])]
    if templates:
        pins += [("observer_" + name, pin) for name, pin in templates[0]["installation"]["programs"].items()]
    pins += [("resident_" + name, pin) for name, pin in resident["installation"]["programs"].items()]
    for name, pin in pins:
        report.probe("program_" + name, lambda pin=pin: executable(pin))
    destinations = [("supervisor_output", value["output"], 0o700), ("supervisor_declarations", value["declarations"], 0o700),
                    ("launcher_output", nested["output"], 0o700), ("launcher_declarations", nested["declarations"], 0o755)]
    parents = [("controller", value["controller_parent"]), ("ordinary", resident["ordinary"]["parent"])]
    if templates:
        destinations += [("journal", templates[0]["journal"], 0o700), ("management_evidence", templates[0]["installation"]["evidence"], 0o700)]
        parents += [(key, templates[0]["grant"][key + "_parent"]) for key in ("query", "management")]
        for phase, template in zip(PHASES, templates):
            destinations.append((phase + "_output", template["output"], 0o700))
            for label, path in (("endpoint", template["grant"]["endpoint"]["path"]), ("control", template["service"]["control_path"])):
                report.probe(phase + "_" + label, lambda path=path: absent_endpoint(path))
            from local_hand_jobs import quota_grant as g
            roots = g.root_paths(template["grant"]["allocation"])
            for root in template["grant"]["roots"]:
                pin = dict(path=roots[root["role"]], device=root["device"], inode=root["inode"])
                report.probe(phase + "_root_" + root["role"], lambda pin=pin, root=root:
                             directory(pin, stat.S_IMODE(root["mode"]), root["uid"], empty=False, gid=root["gid"]))
    for name, pin, mode in destinations:
        report.probe(name, lambda pin=pin, mode=mode: directory(pin, mode))
    report.probe("supervisor_storage_geometry", lambda: storage_geometry(value, supervisor),
                 needs=("declaration_capacity_geometry", "supervisor_output", "supervisor_declarations"))
    for name, pin in parents:
        report.probe(name + "_parent_empty", lambda pin=pin: require(quota_lifecycle.parent("/sys/fs/cgroup" + pin["path"], pin)[1],
                                                                       "FIXTURE_PARENT_OCCUPIED"))
    own = report.probe("original_supervisor", lambda: supervisor.admit(value, binding),
        needs=("systemd_pid1", "administrator", "initial_namespace", "declaration_capacity_geometry"))
    if own is not None:
        controls = supervisor.Controls(value, binding); end = nested["controller_envelope"]["deadline_ns"]
        def target_absent():
            facts = controls.show(end)
            require(facts["Id"] == binding["target"].unit and facts["LoadState"] == "not-found" and facts["Job"] in ("", "0"),
                    "FIXTURE_TARGET_CONSUMED")
        report.probe("target_not_started", target_absent)
        report.probe("ordinary_manager_delegation", lambda: manager_delegation(controls, resident["ordinary"], end))
        report.probe("original_deadline_after_checks", lambda: controls.clock(end))
    else:
        for name in ("target_not_started", "ordinary_manager_delegation", "original_deadline_after_checks"):
            report.probe(name, lambda: None, needs=("original_supervisor",))
    return report.result()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture"); parser.add_argument("--sha256")
    args = parser.parse_args(argv)
    result = Report().result()
    try:
        require(bool(args.fixture and args.sha256), "EXPLICIT_PRIVATE_FIXTURE_REQUIRED")
        require(sys.platform.startswith("linux"), "LINUX_REQUIRED")
        require(sys.flags.isolated and sys.dont_write_bytecode, "FIXTURE_ISOLATED_PYTHON")
        result = check(protected(args.fixture, LIMIT), args.sha256, Path(__file__).resolve().parents[2])
    except Exception as error:
        result["reason"] = reason(error)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "CHECKED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
