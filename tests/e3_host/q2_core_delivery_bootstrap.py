"""Self-contained RAM bootstrap for one approved core-delivery carrier.

Before the complete field package and stdin EOF are verified this module only
reads fixed kernel/process facts and stdin, and writes the bounded HELLO frame.
It does not create a path, import package code, or invoke the dispatcher.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import resource
import select
import stat
import struct
import subprocess
import sys
import time

SCOPE = "LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1"
SESSION_ID = "lhqcore-20261003a"
CARRIER_UNIT = "lhqcore20261003a-carrier.service"
LOADER_SHA256 = "6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61"
RULE = {"commit": "10d2a5c827964989f41ca6e8eeac3d44de6d0f04",
        "source_sha256": "c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5"}
BASELINE = {
    "commit": "74366b3fe41e675b1aa2d677228714a5606c275c", "tree": "7df4fd0c876df13af4ec73c6f910272a72d7ea4d",
    "documents_sha256": {
        "docs/a2-execution/Q2_CORE_LIVE_INPUT_REVIEW_20261003.md": "39853b72755e4737b5329856691e1f616cfd2ffdf403d1c06cbeccff89686f1c",
        "docs/a2-execution/q2-core-acceptance-delivery/ARCHITECTURE.md": "7599870a39f04a68a84992dbc2f3035ba202963fc1cc688914f9b5fa596b54ab",
        "docs/a2-execution/q2-core-acceptance-delivery/IMPLEMENTATION_PLAN.md": "dd128597f90cfdf38d4a9f716fa53fd12acbb12cbc86c261f3f9c760477938c1",
        "docs/a2-execution/q2-core-acceptance-delivery/REQUIREMENTS.md": "8ef192452302ae2c2c55c38dd6889a0a62265404f4baa823be097f0a2524ce76"}}
OWNER = {"event": "LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01",
         "record_path": "docs/governance/Q2_CORE_ACCEPTANCE_DELIVERY_OWNER_DECISION.md",
         "record_sha256": "e6a810ac5a76c903c687b6487ac2a4b08e02022fcf90927f7a34993dedb695cb"}
CLOSURE = {"commit": "a8dd077392ebb656770c8f94ca3b051e93fc296d",
           "tree": "b0d651ea5cbc2c408bb43ce6f3cdc5becd5170c6"}
CANDIDATE = {"commit": "4b6e4a7c403362358192086b88679e1326dcb2e1",
             "tree": "4d4349580c9f4b67cc26f601126849c2bc8d76a4"}
WHEEL = {"basename": "infra_local_hand-0.2.0a1-py3-none-any.whl", "bytes": 288375,
         "sha256": "ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9",
         "payload_digest": "b4d094a9f70c308c63870c9fbf273b6b0646ad211d6f61a79901f52e67cf2e23"}
PROJECTION = {"basename": ".local-hand-source-projection.json", "bytes": 11811,
              "sha256": "55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d",
              "file_count": 89}
PACKAGE_LIMITS = {"package_bytes": 33550320, "manifest_bytes": 1048576, "members": 4096,
                  "member_bytes": 16777216, "shared_allocated_bytes": 67108864,
                  "shared_entries": 4096, "carrier_audit_bytes": 8388608,
                  "carrier_audit_inodes": 512, "carrier_output_bytes": 62914560}
PACKAGE_MAGIC, HELLO_MAGIC, BIND_MAGIC, OUTPUT_MAGIC = b"LHCFP1\n", b"LHCHLO1\n", b"LHCBND1\n", b"LHCOUT1\n"
PACKAGE_SCHEMA = "local-hand-q2-core-field-package/v1"
HELLO_SCHEMA = "local-hand-q2-core-carrier-hello/v1"
BIND_SCHEMA = "local-hand-q2-core-carrier-bind/v1"
CONTEXT_SCHEMA = "local-hand-q2-core-bootstrap-context/v1"
FIELD_PATHS = {"loader": "field/loader.py", "bootstrap": "field/bootstrap.py",
               "dispatcher": "field/dispatcher.py"}
FIELD_LIMITS = {"loader": 8192, "bootstrap": 49152, "dispatcher": 262144}
HELLO_FIELDS = {"schema", "scope", "loader_sha256", "bootstrap_sha256", "guest_boot_id",
                "guest_boottime_origin_ns", "guest_monotonic_origin_ns", "pid", "uid", "gid",
                "euid", "egid", "python", "carrier_unit", "process_limits"}
BIND_FIELDS = {"schema", "scope", "session_id", "hello_sha256", "consumption_sha256",
               "package_basename", "package_bytes", "package_sha256", "host_boottime_origin_ns",
               "host_monotonic_origin_ns", "host_boottime_deadline_ns", "host_monotonic_deadline_ns",
               "host_boottime_bind_ns", "host_monotonic_bind_ns", "host_remaining_floor_ns",
               "clock_margin_ns", "local_final_reserve_ns", "mapped_duration_ns",
               "guest_duration_cap_ns", "guest_duration_ns"}
MANIFEST_FIELDS = {"schema", "scope", "rule", "baseline", "owner_decision", "closure",
                   "implementation", "candidate", "wheel", "projection", "entry", "locators",
                   "members", "limits"}
ENTRY_FIELDS = {"loader_path", "loader_bytes", "loader_sha256", "bootstrap_path", "bootstrap_bytes",
                "bootstrap_sha256", "dispatcher_path", "dispatcher_bytes", "dispatcher_sha256",
                "carrier_argv_sha256", "management_entry_binding_sha256"}
LOCATOR_FIELDS = {"schema", "observation_record_sha256", "source_relation_sha256", "state_parent",
                  "quota_parent", "install_parent", "journal_parent", "evidence_parent", "ordinary_user",
                  "ordinary_group", "user_manager_unit", "query_parent_unit", "controller_parent_unit",
                  "management_parent_unit", "supervisor_parent_unit", "ordinary_parent_unit",
                  "retained_ordinary_parent_path", "carrier_unit"}
MEMBER_FIELDS = {"path", "role", "mode", "bytes", "sha256", "origin"}
ROLES = {"candidate-worktree", "candidate-git-metadata", "wheel", "projection", "field-code"}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def sha(raw):
    require(isinstance(raw, (bytes, bytearray, memoryview)), "CORE_BOOTSTRAP_BYTES")
    return hashlib.sha256(raw).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        require(type(key) is str and key not in result, "CORE_BOOTSTRAP_DUPLICATE_KEY")
        result[key] = value
    return result


def _constant(_value):
    raise ValueError("CORE_BOOTSTRAP_NONFINITE")


def _shape(value, depth=0, count=None):
    count = [0] if count is None else count; count[0] += 1
    require(depth <= 32 and count[0] <= 262144, "CORE_BOOTSTRAP_COMPLEXITY")
    require(not isinstance(value, float), "CORE_BOOTSTRAP_FLOAT")
    if isinstance(value, dict):
        require(all(type(key) is str for key in value), "CORE_BOOTSTRAP_JSON_KEY")
        for item in value.values(): _shape(item, depth + 1, count)
    elif isinstance(value, list):
        for item in value: _shape(item, depth + 1, count)
    else:
        require(value is None or type(value) in (str, int, bool), "CORE_BOOTSTRAP_JSON_VALUE")


def encoded(value, newline=True):
    _shape(value)
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + ("\n" if newline else "")).encode("ascii")


def document(raw, limit, newline=True):
    require(type(raw) is bytes and 0 < len(raw) <= limit
            and raw.endswith(b"\n") == newline, "CORE_BOOTSTRAP_JSON_LIMIT")
    if newline: require(not raw.endswith(b"\n\n"), "CORE_BOOTSTRAP_JSON_NEWLINE")
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("CORE_BOOTSTRAP_JSON") from error
    _shape(value); require(encoded(value, newline) == raw, "CORE_BOOTSTRAP_JSON_CANONICAL")
    return value


def exact(value, fields, code):
    require(type(value) is dict and set(value) == set(fields), code)
    return value


def digest(value, code):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value or ""), code)


def commit(value, code):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value or ""), code)


def relative(value):
    require(type(value) is str and value.isascii() and 0 < len(value) <= 4096
            and re.fullmatch(r"[A-Za-z0-9._/-]+", value) and "//" not in value
            and "\\" not in value and "\0" not in value, "CORE_BOOTSTRAP_PATH")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value
            and all(part not in ("", ".", "..") for part in path.parts), "CORE_BOOTSTRAP_PATH")


def absolute(value):
    require(type(value) is str and value.isascii() and value.startswith("/")
            and not value.startswith("//") and "\\" not in value and "\0" not in value
            and len(value) <= 4096, "CORE_BOOTSTRAP_ABSOLUTE_PATH")
    path = PurePosixPath(value)
    require(path.as_posix() == value and ".." not in path.parts,
            "CORE_BOOTSTRAP_ABSOLUTE_PATH")


def _remaining_ns(deadlines):
    if deadlines is None:
        return None
    require(type(deadlines) is tuple and len(deadlines) == 2
            and all(type(value) is int and value > 0 for value in deadlines),
            "CORE_BOOTSTRAP_DEADLINE")
    remaining = min(deadlines[0] - time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                    deadlines[1] - time.clock_gettime_ns(time.CLOCK_MONOTONIC))
    require(remaining > 0, "CORE_BOOTSTRAP_DEADLINE")
    return remaining


def _stream_fd(stream):
    try:
        value = stream.fileno()
    except (AttributeError, OSError, ValueError):
        return None
    require(type(value) is int and value >= 0, "CORE_BOOTSTRAP_STREAM")
    return value


def _read_some(stream, maximum, deadlines):
    require(type(maximum) is int and maximum > 0, "CORE_BOOTSTRAP_LENGTH")
    remaining = _remaining_ns(deadlines)
    fd = _stream_fd(stream)
    if fd is None:
        block = stream.read(maximum)
        _remaining_ns(deadlines)
        require(type(block) is bytes, "CORE_BOOTSTRAP_STREAM")
        return block
    poller = select.poll()
    poller.register(fd, select.POLLIN | select.POLLHUP | select.POLLERR)
    timeout_ms = max(1, min(2_147_483_647, (remaining + 999_999) // 1_000_000))
    events = poller.poll(timeout_ms)
    _remaining_ns(deadlines)
    require(events and any(event_fd == fd and flags & (select.POLLIN | select.POLLHUP)
                           for event_fd, flags in events), "CORE_BOOTSTRAP_DEADLINE")
    try:
        block = os.read(fd, maximum)
    except OSError as error:
        raise ValueError("CORE_BOOTSTRAP_STREAM") from error
    require(type(block) is bytes, "CORE_BOOTSTRAP_STREAM")
    return block


def _read_exact(stream, length, deadlines=None):
    require(type(length) is int and length >= 0, "CORE_BOOTSTRAP_LENGTH")
    result = bytearray()
    while len(result) < length:
        block = _read_some(stream, min(65536, length - len(result)), deadlines)
        require(block, "CORE_BOOTSTRAP_TRUNCATED")
        result.extend(block)
    return result


def _frame(stream, magic, maximum, deadlines=None):
    require(_read_exact(stream, len(magic), deadlines) == magic, "CORE_BOOTSTRAP_FRAME_MAGIC")
    length = struct.unpack(">Q", _read_exact(stream, 8, deadlines))[0]
    require(0 < length <= maximum, "CORE_BOOTSTRAP_FRAME_LIMIT")
    return bytes(_read_exact(stream, length, deadlines))


def _expect_eof(stream, deadlines):
    require(_read_some(stream, 1, deadlines) == b"", "CORE_BOOTSTRAP_PACKAGE_EOF")


def _write_all(stream, raw, deadlines):
    require(type(raw) is bytes, "CORE_BOOTSTRAP_BYTES")
    fd = _stream_fd(stream)
    if fd is None:
        _remaining_ns(deadlines)
        written = stream.write(raw)
        require(written is None or written == len(raw), "CORE_BOOTSTRAP_STREAM")
        stream.flush()
        _remaining_ns(deadlines)
        return
    view = memoryview(raw)
    offset = 0
    poller = select.poll()
    poller.register(fd, select.POLLOUT | select.POLLHUP | select.POLLERR)
    while offset < len(view):
        remaining = _remaining_ns(deadlines)
        timeout_ms = max(1, min(2_147_483_647, (remaining + 999_999) // 1_000_000))
        events = poller.poll(timeout_ms)
        _remaining_ns(deadlines)
        require(events and any(event_fd == fd and flags & select.POLLOUT
                               for event_fd, flags in events), "CORE_BOOTSTRAP_DEADLINE")
        try:
            count = os.write(fd, view[offset:offset + 65536])
        except OSError as error:
            raise ValueError("CORE_BOOTSTRAP_STREAM") from error
        require(type(count) is int and count > 0, "CORE_BOOTSTRAP_STREAM")
        offset += count


def _program(path, maximum=16 * 1024 * 1024):
    path = os.path.realpath(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= maximum,
                "CORE_BOOTSTRAP_PROGRAM")
        raw = bytearray()
        while len(raw) <= maximum:
            block = os.read(fd, min(65536, maximum + 1 - len(raw)))
            if not block: break
            raw.extend(block)
        after = os.fstat(fd); current = os.stat(path, follow_symlinks=False)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_uid,
                                  value.st_gid, value.st_nlink, value.st_size)
        require(len(raw) == info.st_size <= maximum and identity(after) == identity(info)
                and identity(current) == identity(info), "CORE_BOOTSTRAP_PROGRAM")
    finally:
        os.close(fd)
    return {"path": path, "dev": info.st_dev, "ino": info.st_ino,
            "mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid,
            "nlink": info.st_nlink, "bytes": info.st_size, "sha256": sha(bytes(raw))}


def _properties():
    names = ("ControlGroup", "InvocationID", "ActiveState", "SubState", "RuntimeMaxUSec",
             "TimeoutStopUSec", "MemoryMax", "MemorySwapMax", "TasksMax", "CPUQuotaPerSecUSec",
             "Restart", "KillMode", "ExitType")
    argv = ["/usr/bin/systemctl", "--system", "--no-pager", "--no-ask-password", "show",
            CARRIER_UNIT, "--property=" + ",".join(names)]
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C",
                            "LC_ALL": "C", "SYSTEMD_COLORS": "0"}, check=False, timeout=5)
    require(result.returncode == 0 and len(result.stdout) <= 16384, "CORE_BOOTSTRAP_UNIT")
    rows = {}
    for line in result.stdout.decode("ascii").splitlines():
        key, separator, value = line.partition("=")
        require(separator and key in names and key not in rows, "CORE_BOOTSTRAP_UNIT")
        rows[key] = value
    require(set(rows) == set(names), "CORE_BOOTSTRAP_UNIT")
    def number(name):
        require(rows[name].isdigit(), "CORE_BOOTSTRAP_UNIT"); return int(rows[name])
    def usec(name):
        value = rows[name]
        require(0 < len(value) <= 64, "CORE_BOOTSTRAP_UNIT")
        if value == "0": return 0
        scales = {"min": 60_000_000, "s": 1_000_000, "ms": 1000, "us": 1}
        total, previous = 0, 60_000_001
        for component in value.split(" "):
            match = re.fullmatch(r"(0|[1-9][0-9]{0,8})(?:\.([0-9]{1,6}))?(min|ms|us|s)", component)
            require(match is not None, "CORE_BOOTSTRAP_UNIT")
            whole, fraction, suffix = match.groups(); scale = scales[suffix]
            require(scale < previous, "CORE_BOOTSTRAP_UNIT"); previous = scale
            amount = int(whole) * scale
            if fraction is not None:
                numerator, divisor = int(fraction) * scale, 10 ** len(fraction)
                require(numerator % divisor == 0, "CORE_BOOTSTRAP_UNIT")
                amount += numerator // divisor
            total += amount; require(total <= 900_000_000, "CORE_BOOTSTRAP_UNIT")
        return total
    value = {"name": CARRIER_UNIT, "control_group": rows["ControlGroup"],
             "invocation_id": rows["InvocationID"], "active_state": rows["ActiveState"],
             "sub_state": rows["SubState"], "runtime_max_usec": usec("RuntimeMaxUSec"),
             "timeout_stop_usec": usec("TimeoutStopUSec"), "memory_max": number("MemoryMax"),
             "memory_swap_max": number("MemorySwapMax"), "tasks_max": number("TasksMax"),
             "cpu_quota_per_sec_usec": usec("CPUQuotaPerSecUSec"), "restart": rows["Restart"],
             "kill_mode": rows["KillMode"], "exit_type": rows["ExitType"]}
    validate_carrier(value)
    return value


def validate_carrier(value):
    exact(value, {"name", "control_group", "invocation_id", "active_state", "sub_state",
                  "runtime_max_usec", "timeout_stop_usec", "memory_max", "memory_swap_max",
                  "tasks_max", "cpu_quota_per_sec_usec", "restart", "kill_mode", "exit_type"},
          "CORE_BOOTSTRAP_CARRIER_FIELDS")
    require(value["name"] == CARRIER_UNIT and value["control_group"].endswith("/" + CARRIER_UNIT)
            and re.fullmatch(r"[0-9a-f]{32}", value["invocation_id"] or "")
            and value["active_state"] == "active" and value["sub_state"] in ("running", "start")
            and value["runtime_max_usec"] == 800_000_000
            and value["timeout_stop_usec"] == 30_000_000
            and value["memory_max"] == 1_073_741_824 and value["memory_swap_max"] == 0
            and value["tasks_max"] == 128 and value["cpu_quota_per_sec_usec"] == 1_000_000
            and value["restart"] == "no" and value["kill_mode"] == "control-group"
            and value["exit_type"] == "cgroup", "CORE_BOOTSTRAP_CARRIER")


def make_hello(bootstrap_sha256):
    digest(bootstrap_sha256, "CORE_BOOTSTRAP_DIGEST")
    require(sys.platform.startswith("linux") and sys.flags.isolated and sys.dont_write_bytecode
            and os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0,
            "CORE_BOOTSTRAP_RUNTIME")
    boot_origin = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    mono_origin = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    with open("/proc/sys/kernel/random/boot_id", "r", encoding="ascii") as stream:
        boot_id = stream.read(64).strip()
    old_umask = os.umask(0o077); os.umask(old_umask)
    cpu = resource.getrlimit(resource.RLIMIT_CPU); nofile = resource.getrlimit(resource.RLIMIT_NOFILE)
    fsize = resource.getrlimit(resource.RLIMIT_FSIZE)
    value = {"schema": HELLO_SCHEMA, "scope": SCOPE, "loader_sha256": LOADER_SHA256,
             "bootstrap_sha256": bootstrap_sha256, "guest_boot_id": boot_id,
             "guest_boottime_origin_ns": boot_origin, "guest_monotonic_origin_ns": mono_origin,
             "pid": os.getpid(), "uid": os.getuid(), "gid": os.getgid(), "euid": os.geteuid(),
             "egid": os.getegid(), "python": _program("/usr/bin/python3"), "carrier_unit": _properties(),
             "process_limits": {"cpu_soft": cpu[0], "cpu_hard": cpu[1],
                                "nofile_soft": nofile[0], "nofile_hard": nofile[1],
                                "fsize_soft": fsize[0], "fsize_hard": fsize[1], "umask": old_umask}}
    return validate_hello(value, bootstrap_sha256)


def validate_hello(value, bootstrap_sha256):
    exact(value, HELLO_FIELDS, "CORE_BOOTSTRAP_HELLO_FIELDS")
    require(value["schema"] == HELLO_SCHEMA and value["scope"] == SCOPE
            and value["loader_sha256"] == LOADER_SHA256
            and value["bootstrap_sha256"] == bootstrap_sha256, "CORE_BOOTSTRAP_HELLO_AUTHORITY")
    digest(value["loader_sha256"], "CORE_BOOTSTRAP_HELLO_DIGEST")
    digest(value["bootstrap_sha256"], "CORE_BOOTSTRAP_HELLO_DIGEST")
    require(re.fullmatch(r"[0-9a-f-]{36}", value["guest_boot_id"] or "")
            and all(type(value[key]) is int and value[key] > 0 for key in
                    ("guest_boottime_origin_ns", "guest_monotonic_origin_ns", "pid"))
            and all(value[key] == 0 for key in ("uid", "gid", "euid", "egid")),
            "CORE_BOOTSTRAP_HELLO_IDENTITY")
    exact(value["python"], {"path", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes", "sha256"},
          "CORE_BOOTSTRAP_PYTHON")
    digest(value["python"]["sha256"], "CORE_BOOTSTRAP_PYTHON")
    validate_carrier(value["carrier_unit"])
    exact(value["process_limits"], {"cpu_soft", "cpu_hard", "nofile_soft", "nofile_hard",
                                    "fsize_soft", "fsize_hard", "umask"},
          "CORE_BOOTSTRAP_PROCESS_LIMITS")
    limits = value["process_limits"]
    require(limits == {"cpu_soft": 800, "cpu_hard": 800, "nofile_soft": 256,
                       "nofile_hard": 256, "fsize_soft": 67108864,
                       "fsize_hard": 67108864, "umask": 0o077},
            "CORE_BOOTSTRAP_PROCESS_LIMITS")
    require(len(encoded(value)) <= 4096, "CORE_BOOTSTRAP_HELLO_LIMIT")
    return value


def validate_bind(value, hello_raw):
    exact(value, BIND_FIELDS, "CORE_BOOTSTRAP_BIND_FIELDS")
    require(value["schema"] == BIND_SCHEMA and value["scope"] == SCOPE
            and value["session_id"] == SESSION_ID and value["hello_sha256"] == sha(hello_raw),
            "CORE_BOOTSTRAP_BIND_AUTHORITY")
    for key in ("hello_sha256", "consumption_sha256", "package_sha256"):
        digest(value[key], "CORE_BOOTSTRAP_BIND_DIGEST")
    require(type(value["package_basename"]) is str
            and re.fullmatch(r"[A-Za-z0-9._-]+\.lhfp", value["package_basename"])
            and type(value["package_bytes"]) is int
            and 0 < value["package_bytes"] <= PACKAGE_LIMITS["package_bytes"],
            "CORE_BOOTSTRAP_BIND_PACKAGE")
    numbers = BIND_FIELDS - {"schema", "scope", "session_id", "hello_sha256", "consumption_sha256",
                             "package_basename", "package_sha256"}
    require(all(type(value[key]) is int and value[key] >= 0 for key in numbers),
            "CORE_BOOTSTRAP_BIND_CLOCK")
    remaining = min(value["host_boottime_deadline_ns"] - value["host_boottime_bind_ns"],
                    value["host_monotonic_deadline_ns"] - value["host_monotonic_bind_ns"])
    floor = remaining // 1_000_000 * 1_000_000
    require(value["host_boottime_deadline_ns"]
                == value["host_boottime_origin_ns"] + 900_000_000_000
            and value["host_monotonic_deadline_ns"]
                == value["host_monotonic_origin_ns"] + 900_000_000_000
            and value["host_boottime_origin_ns"] <= value["host_boottime_bind_ns"]
            and value["host_monotonic_origin_ns"] <= value["host_monotonic_bind_ns"]
            and remaining > 0 and value["host_remaining_floor_ns"] == floor
            and value["clock_margin_ns"] == 2_000_000_000
            and value["local_final_reserve_ns"] == 15_000_000_000
            and value["mapped_duration_ns"] == floor - 17_000_000_000 > 0
            and value["guest_duration_cap_ns"] == 750_000_000_000
            and value["guest_duration_ns"] == min(value["mapped_duration_ns"], 750_000_000_000),
            "CORE_BOOTSTRAP_BIND_MAPPING")
    return value


def _validate_manifest(value, members, bootstrap_sha256):
    exact(value, MANIFEST_FIELDS, "CORE_BOOTSTRAP_MANIFEST_FIELDS")
    require(value["schema"] == PACKAGE_SCHEMA and value["scope"] == SCOPE and value["rule"] == RULE
            and value["baseline"] == BASELINE and value["owner_decision"] == OWNER
            and value["closure"] == CLOSURE and value["candidate"] == CANDIDATE
            and value["wheel"] == WHEEL and value["projection"] == PROJECTION
            and value["limits"] == PACKAGE_LIMITS, "CORE_BOOTSTRAP_MANIFEST_AUTHORITY")
    exact(value["implementation"], {"commit", "tree"}, "CORE_BOOTSTRAP_IMPLEMENTATION")
    commit(value["implementation"]["commit"], "CORE_BOOTSTRAP_IMPLEMENTATION")
    commit(value["implementation"]["tree"], "CORE_BOOTSTRAP_IMPLEMENTATION")
    entry = exact(value["entry"], ENTRY_FIELDS, "CORE_BOOTSTRAP_ENTRY_FIELDS")
    for name, path in FIELD_PATHS.items():
        require(entry[name + "_path"] == path and type(entry[name + "_bytes"]) is int
                and 0 < entry[name + "_bytes"] <= FIELD_LIMITS[name], "CORE_BOOTSTRAP_ENTRY")
        digest(entry[name + "_sha256"], "CORE_BOOTSTRAP_ENTRY")
    require(entry["loader_sha256"] == LOADER_SHA256
            and entry["bootstrap_sha256"] == bootstrap_sha256, "CORE_BOOTSTRAP_ENTRY_BINDING")
    digest(entry["carrier_argv_sha256"], "CORE_BOOTSTRAP_ENTRY")
    digest(entry["management_entry_binding_sha256"], "CORE_BOOTSTRAP_ENTRY")
    locators = exact(value["locators"], LOCATOR_FIELDS, "CORE_BOOTSTRAP_LOCATOR_FIELDS")
    require(locators["schema"] == "local-hand-q2-core-private-locators/v1"
            and locators["carrier_unit"] == CARRIER_UNIT, "CORE_BOOTSTRAP_LOCATORS")
    digest(locators["observation_record_sha256"], "CORE_BOOTSTRAP_LOCATORS")
    digest(locators["source_relation_sha256"], "CORE_BOOTSTRAP_LOCATORS")
    for key in ("state_parent", "quota_parent", "install_parent", "journal_parent",
                "evidence_parent", "retained_ordinary_parent_path"):
        absolute(locators[key])
    require(len({locators[key] for key in ("state_parent", "quota_parent", "install_parent",
                                           "journal_parent", "evidence_parent")}) == 5,
            "CORE_BOOTSTRAP_LOCATOR_ALIAS")
    for key in ("ordinary_user", "ordinary_group"):
        require(type(locators[key]) is str
                and re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", locators[key]),
                "CORE_BOOTSTRAP_LOCATOR_ACCOUNT")
    for key in ("user_manager_unit", "query_parent_unit", "controller_parent_unit",
                "management_parent_unit", "supervisor_parent_unit", "ordinary_parent_unit",
                "carrier_unit"):
        require(type(locators[key]) is str and locators[key].isascii()
                and re.fullmatch(r"[A-Za-z0-9_.@:-]{1,255}", locators[key]),
                "CORE_BOOTSTRAP_LOCATOR_UNIT")
    relation = {"schema": "local-hand-q2-core-locator-relation/v1",
                "management_entry_binding_sha256": entry["management_entry_binding_sha256"],
                "observation_record_sha256": locators["observation_record_sha256"],
                "locators": {key: item for key, item in locators.items() if key != "source_relation_sha256"}}
    require(sha(encoded(relation)) == locators["source_relation_sha256"], "CORE_BOOTSTRAP_LOCATOR_RELATION")
    rows = value["members"]
    require(type(rows) is list and 1 <= len(rows) <= PACKAGE_LIMITS["members"]
            and len(rows) == len(members), "CORE_BOOTSTRAP_MEMBER_COUNT")
    paths = []
    roles = {role: [] for role in ROLES}
    for row in rows:
        exact(row, MEMBER_FIELDS, "CORE_BOOTSTRAP_MEMBER_FIELDS"); relative(row["path"])
        require(row["role"] in ROLES and row["mode"] in (0o644, 0o755)
                and type(row["bytes"]) is int and 0 <= row["bytes"] <= PACKAGE_LIMITS["member_bytes"],
                "CORE_BOOTSTRAP_MEMBER")
        digest(row["sha256"], "CORE_BOOTSTRAP_MEMBER")
        require(row["path"] in members and len(members[row["path"]]) == row["bytes"]
                and sha(members[row["path"]]) == row["sha256"], "CORE_BOOTSTRAP_MEMBER_BYTES")
        origin = row["origin"]
        require(type(origin) is dict, "CORE_BOOTSTRAP_ORIGIN")
        if row["role"] in ("candidate-worktree", "field-code"):
            exact(origin, {"kind", "commit", "path", "blob"}, "CORE_BOOTSTRAP_ORIGIN")
            commit(origin["commit"], "CORE_BOOTSTRAP_ORIGIN"); relative(origin["path"])
            require(re.fullmatch(r"[0-9a-f]{40}", origin["blob"] or ""), "CORE_BOOTSTRAP_ORIGIN")
            raw = members[row["path"]]
            hasher = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0")
            hasher.update(raw); blob = hasher.hexdigest()
            require(origin["blob"] == blob, "CORE_BOOTSTRAP_ORIGIN")
            if row["role"] == "candidate-worktree":
                require(origin["kind"] == "candidate-blob" and origin["commit"] == CANDIDATE["commit"]
                        and row["path"] == "candidate/" + origin["path"]
                        and not row["path"].startswith("candidate/.git/"), "CORE_BOOTSTRAP_ORIGIN")
            else:
                require(origin["kind"] == "implementation-blob"
                        and origin["commit"] == value["implementation"]["commit"]
                        and row["path"] in FIELD_PATHS.values(), "CORE_BOOTSTRAP_ORIGIN")
        elif row["role"] == "candidate-git-metadata":
            exact(origin, {"kind", "commit", "git_path"}, "CORE_BOOTSTRAP_ORIGIN")
            relative(origin["git_path"])
            require(origin["kind"] == "candidate-git-metadata"
                    and origin["commit"] == CANDIDATE["commit"]
                    and origin["git_path"].startswith(".git/")
                    and row["path"] == "candidate/" + origin["git_path"],
                    "CORE_BOOTSTRAP_ORIGIN")
        else:
            exact(origin, {"kind", "basename", "sha256"}, "CORE_BOOTSTRAP_ORIGIN")
            expected = WHEEL if row["role"] == "wheel" else PROJECTION
            require(origin == {"kind": row["role"], "basename": expected["basename"],
                               "sha256": expected["sha256"]}, "CORE_BOOTSTRAP_ORIGIN")
            require(row["path"] == "artifacts/" + expected["basename"]
                    and row["bytes"] == expected["bytes"]
                    and row["sha256"] == expected["sha256"], "CORE_BOOTSTRAP_ARTIFACT")
        paths.append(row["path"]); roles[row["role"]].append(row)
    require(paths == sorted(paths, key=lambda item: item.encode("ascii")) and len(paths) == len(set(paths))
            and roles["candidate-worktree"] and roles["candidate-git-metadata"]
            and len(roles["wheel"]) == len(roles["projection"]) == 1
            and {row["path"] for row in roles["field-code"]} == set(FIELD_PATHS.values()),
            "CORE_BOOTSTRAP_INVENTORY")
    for name, path in FIELD_PATHS.items():
        row = next(item for item in roles["field-code"] if item["path"] == path)
        require((row["bytes"], row["sha256"]) == (entry[name + "_bytes"], entry[name + "_sha256"]),
                "CORE_BOOTSTRAP_ENTRY_BINDING")
    return value


def parse_package(raw, bootstrap_sha256):
    require(isinstance(raw, (bytes, bytearray, memoryview))
            and 16 < len(raw) <= PACKAGE_LIMITS["package_bytes"]
            and raw.startswith(PACKAGE_MAGIC), "CORE_BOOTSTRAP_PACKAGE")
    view = memoryview(raw); offset = len(PACKAGE_MAGIC)
    length = struct.unpack(">Q", view[offset:offset + 8])[0]; offset += 8
    require(0 < length <= PACKAGE_LIMITS["manifest_bytes"] and offset + length <= len(raw),
            "CORE_BOOTSTRAP_MANIFEST_LIMIT")
    # Keep one immutable package allocation. Member views below reference it;
    # they do not duplicate up to another 32 MiB before dispatcher admission.
    manifest = document(bytes(view[offset:offset + length]), PACKAGE_LIMITS["manifest_bytes"]); offset += length
    require(type(manifest) is dict and type(manifest.get("members")) is list,
            "CORE_BOOTSTRAP_MANIFEST")
    members = {}
    for row in manifest["members"]:
        require(type(row) is dict and type(row.get("bytes")) is int and 0 <= row["bytes"] <= 16777216,
                "CORE_BOOTSTRAP_MEMBER")
        end = offset + row["bytes"]; require(end <= len(raw), "CORE_BOOTSTRAP_TRUNCATED")
        require(type(row.get("path")) is str and row["path"] not in members, "CORE_BOOTSTRAP_MEMBER")
        members[row["path"]] = view[offset:end].toreadonly(); offset = end
    require(offset == len(raw), "CORE_BOOTSTRAP_TRAILING")
    _validate_manifest(manifest, members, bootstrap_sha256)
    return manifest, members


def _execute(context):
    raw = bytes(context["members"]["field/dispatcher.py"])
    namespace = {"__name__": "_lhqcore_dispatcher", "__file__": "field/dispatcher.py",
                 "__builtins__": __builtins__}
    exec(compile(raw, "field/dispatcher.py", "exec", flags=0, dont_inherit=True, optimize=0),
         namespace, namespace)
    factory, dispatch = namespace.get("FieldEffects"), namespace.get("dispatch")
    require(callable(factory) and callable(dispatch), "CORE_BOOTSTRAP_DISPATCHER_ABI")
    frame = dispatch(context, factory(context))
    require(type(frame) is bytes and frame.startswith(OUTPUT_MAGIC)
            and len(frame) <= 58_716_144, "CORE_BOOTSTRAP_OUTPUT_FRAME")
    return frame


def serve(*, stdin, stdout, bootstrap_sha256, hello_factory=None, dispatch=None):
    digest(bootstrap_sha256, "CORE_BOOTSTRAP_DIGEST")
    hello = (make_hello(bootstrap_sha256) if hello_factory is None
             else validate_hello(hello_factory(bootstrap_sha256), bootstrap_sha256))
    hello_raw = encoded(hello)
    initial_deadlines = (hello["guest_boottime_origin_ns"] + 750_000_000_000,
                         hello["guest_monotonic_origin_ns"] + 750_000_000_000)
    _write_all(stdout, HELLO_MAGIC + struct.pack(">Q", len(hello_raw)) + hello_raw,
               initial_deadlines)
    bind_raw = _frame(stdin, BIND_MAGIC, 4096, initial_deadlines)
    bind = validate_bind(document(bind_raw, 4096), hello_raw)
    require(bind["package_bytes"] + len(BIND_MAGIC) + 8 + len(bind_raw) <= 33_554_432,
            "CORE_BOOTSTRAP_INPUT_LIMIT")
    boot_deadline = hello["guest_boottime_origin_ns"] + bind["guest_duration_ns"]
    mono_deadline = hello["guest_monotonic_origin_ns"] + bind["guest_duration_ns"]
    guest_deadlines = (boot_deadline, mono_deadline)
    _remaining_ns(guest_deadlines)
    package_raw = _read_exact(stdin, bind["package_bytes"], guest_deadlines)
    _expect_eof(stdin, guest_deadlines)
    require(sha(package_raw) == bind["package_sha256"], "CORE_BOOTSTRAP_PACKAGE_EOF")
    manifest, members = parse_package(package_raw, bootstrap_sha256)
    _remaining_ns(guest_deadlines)
    context = {"schema": CONTEXT_SCHEMA, "hello": hello, "bind": bind, "manifest": manifest,
               "members": members, "guest_deadlines": {"boot_id": hello["guest_boot_id"],
                   "boottime_deadline_ns": boot_deadline, "monotonic_deadline_ns": mono_deadline},
               "stdin_bytes_received": len(BIND_MAGIC) + 8 + len(bind_raw) + len(package_raw)}
    frame = _execute(context) if dispatch is None else dispatch(context)
    require(type(frame) is bytes and frame.startswith(OUTPUT_MAGIC) and len(frame) <= 58_716_144,
            "CORE_BOOTSTRAP_OUTPUT_FRAME")
    _write_all(stdout, frame, guest_deadlines)
    return context


def main(stdin=None, stdout=None, stderr=None, *, bootstrap_sha256=None,
         hello_factory=None, dispatch=None):
    stdin = sys.stdin.buffer if stdin is None else stdin
    stdout = sys.stdout.buffer if stdout is None else stdout
    stderr = sys.stderr.buffer if stderr is None else stderr
    bootstrap_sha256 = (globals().get("BOOTSTRAP_SHA256") if bootstrap_sha256 is None
                        else bootstrap_sha256)
    try:
        serve(stdin=stdin, stdout=stdout, bootstrap_sha256=bootstrap_sha256,
              hello_factory=hello_factory, dispatch=dispatch)
        return 0
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r"CORE_[A-Z0-9_]+", code): code = "CORE_BOOTSTRAP_FAILURE"
        stderr.write((code + "\n").encode("ascii")); stderr.flush()
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
