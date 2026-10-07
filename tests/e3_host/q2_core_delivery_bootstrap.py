"""Standalone RAM bootstrap: bounded JIT HELLO, then complete v3 package/EOF
validation before importing any delivered code or creating persistent objects.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from pathlib import PurePosixPath
import pwd
import re
import resource
import select
import shlex
import stat
import struct
import subprocess
import sys
import time

SCOPE = "LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1"
SESSION_ID = "lhqcore-20261007a"
CARRIER_UNIT = "lhqcore20261007a-carrier.service"
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
AMENDMENT_BASELINE = {
    "commit": "0bdb49cae5586be60a7ba31d4a8e8367854d1e8c",
    "tree": "ee15aa4fa26fd2e87b40f6fad72828265e5cf9bc",
    "documents_sha256": {
    "docs/a2-execution/q2-core-binding-finalization-amendment/REQUIREMENTS.md":
    "e6b29c45c550f2ae8b3eaa91baad8d1382851dec6a69e2f807cce9233b14cdb1",
    "docs/a2-execution/q2-core-binding-finalization-amendment/ARCHITECTURE.md":
    "7782e2fb89a28052978d3ce205278906b92752e3ba1add9cd634c0e7c0f92c96",
    "docs/a2-execution/q2-core-binding-finalization-amendment/IMPLEMENTATION_PLAN.md":
    "52faaf002d9b5b9d88aef0b6f568e8ed56d2aa49eb0ea41e7eeb85d2d0b64cce",
    },
}
AMENDMENT_OWNER_DECISION = {
    "event": "LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-CLOSURE-20261004-01",
    "record_path": "docs/governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_OWNER_DECISION.md",
    "record_sha256": "800f01b3e7d4aeec77095bbc67196837427a7dbece7f1212bca266adb3d9ddbd",
}
AMENDMENT_CLOSURE = {
    "commit": "7598886e15ed6911fe0e09e2f8d66203455f9057",
    "tree": "7f2178942c126f883829a139b842cfc2c2e12159",
}
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
PACKAGE_SCHEMA = "local-hand-q2-core-field-package/v3"
HELLO_SCHEMA = "local-hand-q2-core-carrier-hello/v2"
BIND_SCHEMA = "local-hand-q2-core-carrier-bind/v1"
CONTEXT_SCHEMA = "local-hand-q2-core-bootstrap-context/v1"
FIELD_PATHS = {"loader": "field/loader.py", "bootstrap": "field/bootstrap.py",
    "dispatcher": "field/dispatcher.py"}
FIELD_LIMITS = {"loader": 8192, "bootstrap": 49152, "dispatcher": 524288}
HELLO_FIELDS = {"schema", "scope", "loader_sha256", "bootstrap_sha256", "guest_boot_id",
    "guest_boottime_origin_ns", "guest_monotonic_origin_ns", "pid", "uid", "gid",
    "euid", "egid", "python", "carrier_unit", "process_limits", "remote_management"}
BIND_FIELDS = {"schema", "scope", "session_id", "hello_sha256", "consumption_sha256",
    "package_basename", "package_bytes", "package_sha256", "host_boottime_origin_ns",
    "host_monotonic_origin_ns", "host_boottime_deadline_ns", "host_monotonic_deadline_ns",
    "host_boottime_bind_ns", "host_monotonic_bind_ns", "host_remaining_floor_ns",
    "clock_margin_ns", "local_final_reserve_ns", "mapped_duration_ns",
    "guest_duration_cap_ns", "guest_duration_ns"}
MANIFEST_FIELDS = {"schema", "scope", "rule", "baseline", "owner_decision", "closure",
    "implementation", "candidate", "wheel", "projection", "entry", "locators",
    "members", "limits", "amendment", "approved_inputs"}
ENTRY_FIELDS = {"loader_path", "loader_bytes", "loader_sha256", "bootstrap_path", "bootstrap_bytes",
    "bootstrap_sha256", "dispatcher_path", "dispatcher_bytes", "dispatcher_sha256",
    "carrier_argv_sha256", "local_management_binding_sha256", "writer"}
LOCATOR_FIELDS = {"schema", "observation_record_sha256", "source_relation_sha256", "state_parent",
    "quota_parent", "install_parent", "journal_parent", "evidence_parent", "ordinary_user",
    "ordinary_group", "user_manager_unit", "query_parent_unit", "controller_parent_unit",
    "management_parent_unit", "supervisor_parent_unit", "ordinary_parent_unit",
    "retained_ordinary_parent_path", "carrier_unit"}
MEMBER_FIELDS = {"path", "role", "mode", "bytes", "sha256", "origin"}
ROLES = {"candidate-worktree", "candidate-git-metadata", "wheel", "projection", "field-code", "approved-inputs"}
REMOTE_ALIASES = {"shell": "/bin/bash", "sudo": "/usr/bin/sudo", "env": "/usr/bin/env",
    "systemd_run": "/usr/bin/systemd-run", "python": "/usr/bin/python3"}
PROGRAM_FIELDS = {"path", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes", "sha256"}
ENTITY_FIELDS = PROGRAM_FIELDS | {"resolved_path", "symlink_chain"}
REMOTE_FIELDS = {"account", "uid", "gid", "home", "login_shell", "parser_profile",
    "remote_tokens_sha256", "remote_command_sha256"} | set(REMOTE_ALIASES)


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
        if type(value) is int:
            require(-(2**63) <= value < 2**63, "CORE_BOOTSTRAP_INTEGER")


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


def validate_writer(value):
    code = "CORE_BOOTSTRAP_WRITER"
    exact(value, {"schema", "user_namespace", "pid_namespace", "process", "uid", "gid",
        "supplementary_gids"}, code)
    require(value["schema"] == "local-hand-q2-core-local-writer/v1", code)
    for name in ("user_namespace", "pid_namespace", "process", "uid", "gid"):
        fields = ({"dev": 0, "ino": 1} if name.endswith("namespace") else
                  {"pid": 1, "starttime_ticks": 0} if name == "process" else
                  dict.fromkeys(("real", "effective", "saved", "filesystem"), 0))
        exact(value[name], fields, code)
        require(all(type(value[name][k]) is int and low <= value[name][k] < 2**63
                    for k, low in fields.items()), code)
        if name in ("uid", "gid"):
            require(len(set(value[name].values())) == 1, code)
    groups = value["supplementary_gids"]
    require(type(groups) is list and all(type(n) is int and 0 <= n < 2**63 for n in groups), code)
    require(groups == sorted(set(groups)) and len(encoded(value, newline=False)) <= 4096, code)
    return value


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


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _components(path):
    require(type(path) is str and 0 < len(path.encode("utf-8")) <= 4096
            and "\0" not in path and ".." not in path.split("/")
            and all(item not in ("", ".") for item in path.strip("/").split("/")),
            "CORE_BOOTSTRAP_ALIAS")
    return path.strip("/").split("/")


def _resolve_program(path, root_fd):
    """Resolve from one held root; keep every traversed parent until verification."""
    require(path.startswith("/") and not path.startswith("//"), "CORE_BOOTSTRAP_ALIAS")
    pending, resolved, chain, checks, held = _components(path), [], [], [], []
    parent = root_fd; seen = set(); components = 0
    try:
        while pending:
            name = pending.pop(0); components += 1
            require(components <= 64, "CORE_BOOTSTRAP_ALIAS_LIMIT")
            current = "/" + "/".join(resolved + [name])
            require(len(current.encode("utf-8")) <= 4096, "CORE_BOOTSTRAP_ALIAS_LIMIT")
            require(current != "/proc" and current != "/dev/fd",
        "CORE_BOOTSTRAP_MAGIC_LINK")
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                identity = _identity(info)
                target = os.readlink(name, dir_fd=parent)
                require(_identity(os.stat(name, dir_fd=parent, follow_symlinks=False))
                        == identity, "CORE_BOOTSTRAP_ALIAS_DRIFT")
                require(len(chain) < 8 and current not in seen
                        and not target.startswith("//"), "CORE_BOOTSTRAP_ALIAS_LIMIT")
                seen.add(current); parts = _components(target)
                chain.append({"path": current, "target": target})
                checks.append((parent, name, identity, target))
                if target.startswith("/"):
                    # Absolute targets stay rooted in the original held namespace root.
                    parent, resolved = root_fd, []
                pending = parts + pending
                continue
            checks.append((parent, name, _identity(info), None))
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC
            if pending:
                require(stat.S_ISDIR(info.st_mode), "CORE_BOOTSTRAP_ALIAS_DIRECTORY")
                flags |= os.O_DIRECTORY
            else:
                require(stat.S_ISREG(info.st_mode), "CORE_BOOTSTRAP_PROGRAM")
            fd = os.open(name, flags, dir_fd=parent); held.append(fd)
            require(_identity(os.fstat(fd)) == _identity(info), "CORE_BOOTSTRAP_ALIAS_DRIFT")
            resolved.append(name); parent = fd
        require(held and stat.S_ISREG(os.fstat(held[-1]).st_mode), "CORE_BOOTSTRAP_PROGRAM")
        return held[-1], "/" + "/".join(resolved), chain, checks, held
    except BaseException:
        for fd in reversed(held): os.close(fd)
        raise


def _check_resolution(checks):
    for parent, name, expected, target in checks:
        require(_identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) == expected,
        "CORE_BOOTSTRAP_ALIAS_DRIFT")
        if target is not None:
            require(os.readlink(name, dir_fd=parent) == target, "CORE_BOOTSTRAP_ALIAS_DRIFT")


def _program(path, maximum=16 * 1024 * 1024):
    root = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                   | os.O_NOATIME | os.O_CLOEXEC)
    held = []; second = []
    try:
        root_identity = _identity(os.fstat(root))
        fd, resolved, chain, checks, held = _resolve_program(path, root)
        info = os.fstat(fd)
        require(info.st_uid == info.st_gid == 0 and info.st_nlink == 1
                and info.st_mode & 0o111 and not info.st_mode & 0o022
                and 0 < info.st_size <= maximum, "CORE_BOOTSTRAP_PROGRAM")
        _check_resolution(checks)
        raw = bytearray()
        while len(raw) < info.st_size:
            block = os.read(fd, min(65536, info.st_size - len(raw)))
            if not block: break
            raw.extend(block)
        require(len(raw) == info.st_size and _identity(os.fstat(fd)) == _identity(info),
        "CORE_BOOTSTRAP_PROGRAM_DRIFT")
        _check_resolution(checks)
        other, other_path, other_chain, other_checks, second = _resolve_program(path, root)
        require(other_path == resolved and other_chain == chain
                and _identity(os.fstat(other)) == _identity(info), "CORE_BOOTSTRAP_ALIAS_DRIFT")
        _check_resolution(other_checks)
        require(_identity(os.fstat(root)) == root_identity
                and _identity(os.stat("/", follow_symlinks=False)) == root_identity,
        "CORE_BOOTSTRAP_ROOT_DRIFT")
        return {"path": path, "resolved_path": resolved, "symlink_chain": chain,
        "dev": info.st_dev, "ino": info.st_ino, "mode": stat.S_IMODE(info.st_mode),
        "uid": info.st_uid, "gid": info.st_gid, "nlink": info.st_nlink,
        "bytes": info.st_size, "sha256": sha(bytes(raw))}
    finally:
        for fd in reversed(second + held): os.close(fd)
        os.close(root)


def _remote_command_digests(bootstrap_sha256):
    """Reconstruct the fixed vector from verified Python invocation inputs."""
    original = getattr(sys, "orig_argv", None)
    require(type(original) is list and len(original) == 7
            and original[:4] == ["/usr/bin/python3", "-I", "-B", "-c"]
            and sys.argv == ["-c", original[5], original[6]]
            and original[6] == bootstrap_sha256, "CORE_BOOTSTRAP_INVOKED_ARGV")
    require(all(type(item) is str and item and "\0" not in item for item in original),
            "CORE_BOOTSTRAP_INVOKED_ARGV")
    loader = original[4].encode("utf-8")
    require(0 < len(loader) <= 8192 and sha(loader) == LOADER_SHA256
            and original[5].isascii() and 0 < len(original[5]) <= 65536,
            "CORE_BOOTSTRAP_INVOKED_LOADER")
    try:
        raw = base64.b64decode(original[5], validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("CORE_BOOTSTRAP_INVOKED_BASE64") from error
    require(0 < len(raw) <= 49152 and base64.b64encode(raw).decode("ascii") == original[5]
            and sha(raw) == bootstrap_sha256, "CORE_BOOTSTRAP_INVOKED_BASE64")
    tokens = [
        "exec", "/usr/bin/sudo", "-n", "--", "/usr/bin/env", "-i",
        "HOME=/root", "PATH=/usr/bin:/bin", "LANG=C", "LC_ALL=C", "SYSTEMD_COLORS=0",
        "/usr/bin/systemd-run", "--system", "--no-ask-password", "--quiet", "--wait", "--pipe",
        "--collect", "--service-type=exec", "--unit=lhqcore20261007a-carrier.service",
        "--property=Restart=no", "--property=RuntimeMaxSec=800s", "--property=TimeoutStopSec=30s",
        "--property=KillMode=control-group", "--property=ExitType=cgroup", "--property=CPUQuota=100%",
        "--property=LimitCPU=800", "--property=MemoryMax=1073741824", "--property=MemorySwapMax=0",
        "--property=TasksMax=128", "--property=LimitNOFILE=256", "--property=LimitFSIZE=67108864",
        "--property=UMask=0077", "--", *original]
    command = shlex.join(tokens).encode("utf-8")
    require(len(command) <= 98304, "CORE_BOOTSTRAP_COMMAND_LIMIT")
    return sha(encoded(tokens, newline=False)), sha(command)


def collect_remote_management(bootstrap_sha256):
    account = pwd.getpwnam("q1admin")
    require(account.pw_name == "q1admin" and account.pw_dir == "/home/q1admin"
            and account.pw_shell == "/bin/bash" and account.pw_uid > 0 and account.pw_gid > 0,
            "CORE_BOOTSTRAP_ACCOUNT")
    token_sha, command_sha = _remote_command_digests(bootstrap_sha256)
    entities = {name: _program(path) for name, path in REMOTE_ALIASES.items()}
    require(sum(item["bytes"] for item in entities.values()) <= 83886080,
            "CORE_BOOTSTRAP_PROGRAM_LIMIT")
    return {"account": account.pw_name, "uid": account.pw_uid, "gid": account.pw_gid,
            "home": account.pw_dir, "login_shell": account.pw_shell,
            "parser_profile": "bash-noninteractive-c-v1", **entities,
            "remote_tokens_sha256": token_sha, "remote_command_sha256": command_sha}


def validate_remote_management(value):
    exact(value, REMOTE_FIELDS, "CORE_BOOTSTRAP_REMOTE_FIELDS")
    require(value["account"] == "q1admin" and value["home"] == "/home/q1admin"
            and value["login_shell"] == "/bin/bash"
            and value["parser_profile"] == "bash-noninteractive-c-v1"
            and all(type(value[key]) is int and value[key] > 0 for key in ("uid", "gid")),
            "CORE_BOOTSTRAP_ACCOUNT")
    for key in ("remote_tokens_sha256", "remote_command_sha256"):
        digest(value[key], "CORE_BOOTSTRAP_REMOTE_DIGEST")
    total = 0
    for name, alias in REMOTE_ALIASES.items():
        entity = exact(value[name], ENTITY_FIELDS, "CORE_BOOTSTRAP_ENTITY_FIELDS")
        require(entity["path"] == alias, "CORE_BOOTSTRAP_ENTITY_ALIAS")
        absolute(entity["resolved_path"])
        require(all(type(entity[key]) is int and entity[key] >= 0
                    for key in ("dev", "ino", "mode", "uid", "gid", "nlink", "bytes"))
                and entity["uid"] == entity["gid"] == 0 and entity["nlink"] == 1
                and 0 < entity["bytes"] <= 16777216 and 0 < entity["ino"]
                and 0 <= entity["mode"] <= 0o7777 and entity["mode"] & 0o111
                and not entity["mode"] & 0o022, "CORE_BOOTSTRAP_ENTITY")
        digest(entity["sha256"], "CORE_BOOTSTRAP_ENTITY")
        require(type(entity["symlink_chain"]) is list and len(entity["symlink_chain"]) <= 8,
        "CORE_BOOTSTRAP_ALIAS_LIMIT")
        seen = set()
        for link in entity["symlink_chain"]:
            exact(link, {"path", "target"}, "CORE_BOOTSTRAP_ALIAS_FIELDS")
            absolute(link["path"]); _components(link["target"])
            require(link["path"] not in seen and not link["target"].startswith("//"),
        "CORE_BOOTSTRAP_ALIAS_LIMIT")
            seen.add(link["path"])
        total += entity["bytes"]
    require(total <= 83886080, "CORE_BOOTSTRAP_PROGRAM_LIMIT")
    return value


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
    remote = collect_remote_management(bootstrap_sha256)
    value = {"schema": HELLO_SCHEMA, "scope": SCOPE, "loader_sha256": LOADER_SHA256,
             "bootstrap_sha256": bootstrap_sha256, "guest_boot_id": boot_id,
             "guest_boottime_origin_ns": boot_origin, "guest_monotonic_origin_ns": mono_origin,
             "pid": os.getpid(), "uid": os.getuid(), "gid": os.getgid(), "euid": os.geteuid(),
             "egid": os.getegid(), "remote_management": remote,
             "python": {key: (remote["python"]["resolved_path"] if key == "path"
                              else remote["python"][key]) for key in PROGRAM_FIELDS},
             "carrier_unit": _properties(),
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
            and all(type(value[key]) is int and value[key] == 0 for key in ("uid", "gid", "euid", "egid")),
            "CORE_BOOTSTRAP_HELLO_IDENTITY")
    exact(value["python"], {"path", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes", "sha256"},
          "CORE_BOOTSTRAP_PYTHON")
    remote = validate_remote_management(value["remote_management"])
    require(value["python"] == {key: (remote["python"]["resolved_path"] if key == "path"
                                      else remote["python"][key]) for key in PROGRAM_FIELDS},
            "CORE_BOOTSTRAP_PYTHON_PROJECTION")
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
    require(value["package_basename"] == SESSION_ID + '.lhfp'
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
    amendment = exact(value["amendment"], {"baseline", "owner_decision", "closure", "implementation"},
        "CORE_BOOTSTRAP_AMENDMENT")
    require(amendment == {"baseline": AMENDMENT_BASELINE, "owner_decision": AMENDMENT_OWNER_DECISION,
        "closure": AMENDMENT_CLOSURE, "implementation": value["implementation"]}
            and value["implementation"]["tree"] != "0" * 40
            and value["implementation"]["commit"] not in {"0" * 40, BASELINE["commit"], CLOSURE["commit"],
                AMENDMENT_BASELINE["commit"], AMENDMENT_CLOSURE["commit"],
        "520f77f578b90d31870517e33e29bee42918f3c0"}, "CORE_BOOTSTRAP_AMENDMENT")
    approved = exact(value["approved_inputs"], {"path", "bytes", "sha256", "approved_source_relation_sha256"},
        "CORE_BOOTSTRAP_APPROVED_INPUTS")
    require(approved["path"] == "private/approved-inputs.json" and type(approved["bytes"]) is int
            and 0 < approved["bytes"] <= 1048576 and approved["path"] in members,
            "CORE_BOOTSTRAP_APPROVED_INPUTS")
    approved_raw = bytes(members[approved["path"]])
    require(len(approved_raw) == approved["bytes"] and sha(approved_raw) == approved["sha256"],
            "CORE_BOOTSTRAP_APPROVED_INPUTS")
    artifact = document(approved_raw, 1048576)
    components = {"source_relation", "policy_basis", "historical_capacity_obligations",
        "retained_preparation", "reconciliation"}
    exact(artifact, {"schema", "scope", "amendment"} | components, "CORE_BOOTSTRAP_APPROVED_FIELDS")
    require(artifact["schema"] == "local-hand-q2-core-approved-inputs/v1" and artifact["scope"] == SCOPE
            and artifact["amendment"] == amendment
            and all(type(artifact[key]) is dict and artifact[key] for key in components)
            and sha(encoded(artifact["source_relation"], newline=False))
                == approved["approved_source_relation_sha256"], "CORE_BOOTSTRAP_APPROVED_INPUTS")
    entry = exact(value["entry"], ENTRY_FIELDS, "CORE_BOOTSTRAP_ENTRY_FIELDS")
    validate_writer(entry["writer"])
    for name, path in FIELD_PATHS.items():
        require(entry[name + "_path"] == path and type(entry[name + "_bytes"]) is int
                and 0 < entry[name + "_bytes"] <= FIELD_LIMITS[name], "CORE_BOOTSTRAP_ENTRY")
        digest(entry[name + "_sha256"], "CORE_BOOTSTRAP_ENTRY")
    require(entry["loader_sha256"] == LOADER_SHA256
            and entry["bootstrap_sha256"] == bootstrap_sha256, "CORE_BOOTSTRAP_ENTRY_BINDING")
    digest(entry["carrier_argv_sha256"], "CORE_BOOTSTRAP_ENTRY")
    digest(entry["local_management_binding_sha256"], "CORE_BOOTSTRAP_ENTRY")
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
    relation = {"schema": "local-hand-q2-core-locator-relation/v2",
        "local_management_binding_sha256": entry["local_management_binding_sha256"],
        "observation_record_sha256": locators["observation_record_sha256"],
        "locators": {key: item for key, item in locators.items() if key != "source_relation_sha256"}}
    require(sha(encoded(relation, newline=False)) == locators["source_relation_sha256"], "CORE_BOOTSTRAP_LOCATOR_RELATION")
    rows = value["members"]
    require(type(rows) is list and 1 <= len(rows) <= PACKAGE_LIMITS["members"]
            and len(rows) == len(members), "CORE_BOOTSTRAP_MEMBER_COUNT")
    paths = []
    roles = {role: [] for role in ROLES}
    for row in rows:
        exact(row, MEMBER_FIELDS, "CORE_BOOTSTRAP_MEMBER_FIELDS"); relative(row["path"])
        require(row["role"] in ROLES and row["mode"] in ((0o600,) if row["role"] == "approved-inputs" else (0o644, 0o755))
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
        elif row["role"] == "approved-inputs":
            require(row["path"] == approved["path"] and row["bytes"] == approved["bytes"]
                    and row["sha256"] == approved["sha256"]
                    and origin == {"kind": "approved-inputs", **{key: approved[key] for key in
                        ("bytes", "sha256", "approved_source_relation_sha256")}},
        "CORE_BOOTSTRAP_APPROVED_ORIGIN")
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
            and len(roles["wheel"]) == len(roles["projection"]) == len(roles["approved-inputs"]) == 1
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
    # Member views retain one package allocation until dispatcher admission.
    manifest = document(bytes(view[offset:offset + length]), PACKAGE_LIMITS["manifest_bytes"]); offset += length
    require(type(manifest) is dict and type(manifest.get("members")) is list
            and 1 <= len(manifest["members"]) <= PACKAGE_LIMITS["members"],
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
