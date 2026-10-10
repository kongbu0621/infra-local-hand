"""One-shot local carrier and capture primitives for the closed core scope.

The functions in this module deliberately separate static qualification from
the irreversible marker write.  Nothing here searches for a guest, chooses an
alternate locator, removes an existing object, or retries a transport.  The
caller must supply the already-qualified management anchor and frozen package.
"""
from __future__ import annotations

import base64
import errno
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import selectors
import shlex
import stat
import struct
import subprocess
import sys
import time
import types


def _helper(name):
    spec = importlib.util.spec_from_file_location(
        "_q2_core_delivery_entry_" + name, Path(__file__).with_name(name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract = _helper("q2_core_delivery_contract")
require = contract.require

# The remote dispatcher is also the normative constructor for the exact case
# member closures and PASS verdicts.  The local side loads the independently
# frozen D source only to *validate* returned bytes; it never calls dispatch or
# any field effect.
dispatcher_contract = _helper("q2_core_delivery_dispatcher")
capture_contract = _helper("q2_core_capture")

HOST_WINDOW_NS = 1800000000000
CLOCK_MARGIN_NS = 2_000_000_000
LOCAL_FINAL_RESERVE_NS = 30000000000
GUEST_CAP_NS = 1500000000000
MARKER_LIMIT = 32768
REMOTE_COMMAND_LIMIT = 131_071
LOCAL_ARG_ENV_LIMIT = 1048576
LINUX_SINGLE_ARGUMENT_LIMIT = 131_072
REMOTE_RESULT_LIMIT = 524288
CAPTURE_LIMIT = 134217728
CAPTURE_INODE_LIMIT = 32
STDERR_LIMIT = 8388608
OUTPUT_FRAME_LIMIT = 117432304
CARRIER_OUTPUT_LIMIT = 125829120
STREAM_CAPTURE_LIMIT = 109051904
HELLO_JSON_LIMIT = 8192
HELLO_FRAME_LIMIT = 8208
BIND_JSON_LIMIT = 8192
BIND_FRAME_LIMIT = 8208

# PP1 binds the exact reviewed dispatcher. Exact D first CI, full PP2 originals
# and actual coordinator completion remain required before original 07a.
# Historical dispatcher pins remain in their consumed source profiles.
RELEASABLE_DISPATCHER_SHA256 = frozenset({"645de8571fb812c7b713af2eff53ab0255814ed7ce1edf57f139bcbc69000152"})

OUTPUT_LIMITS = {
    "frame_bytes": OUTPUT_FRAME_LIMIT,
    "manifest_bytes": 2_097_152,
    "members": 8192,
    "member_bytes": 33_554_432,
    "stderr_bytes": STDERR_LIMIT,
}

CASE_INDEX_FIELDS = {
    "index", "case_id", "status", "semantic_pass", "verdict_path", "verdict_sha256",
}
MISSING_FIELDS = {"code", "role", "detail_sha256"}
USAGE_FIELDS = {
    "guest_elapsed_ns", "carrier_cpu_ns", "carrier_memory_peak_bytes", "carrier_pids_peak",
    "stdin_bytes_received", "output_frame_bytes", "guest_allocated_bytes",
    "guest_allocated_inodes", "job_units_started", "controller_units_started",
    "quota_query_units_started", "dynamic_quota_units_started", "native_children_started",
}
H01_EXECUTION_FIELDS = {
    "status", "operation_id", "execution_id", "unit", "invocation_id", "wait_status",
    "business_started", "outcome", "evidence_sha256",
}
H01_PACKAGE_FIELDS = {
    "status", "result_member", "result_sha256", "required_members_sha256",
}
MEMBER_ROLES = {
    "session", "admission", "installation", "intent", "plan", "preparation-plan",
    "preparation-result", "phase-receipt", "empty-ledger-gate", "authority", "ledger",
    "fixture-check", "observer-config", "phase-result", "gateway", "origin-capture",
    "launcher-reservation", "launcher-result", "stdout", "stderr", "wait", "result",
    "recovery-plan", "recovery-summary", "recovery-proof", "stop", "verdict",
    "business-evidence-archive", "business-evidence-manifest", "business-evidence-seal",
    "control-seal",
}

WRAPPER_SHA256 = "aed91e80483d4df103f95c1d4cd5bf9bd18720f4dc51720702c329c937f93c63"
START_SHA256 = "1acc8c4cb09bc5b14c32adc35e87d8500098cbf3968d53f406269e96df30f96a"
CLOUD_CONFIG_SHA256 = "5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523"
PUBLIC_KEY_SHA256 = "e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c"
KNOWN_HOSTS_SHA256 = "d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd"

MANAGEMENT_FIELDS = {
    "schema", "anchor", "writer", "wrapper", "fixture_start", "fixture_cloud_config", "profile",
    "environment", "dependencies", "identity", "identity_public", "known_hosts",
    "cwd", "remote_expectation", "transport",
}
FILE_IDENTITY_FIELDS = {
    "path", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes", "sha256",
}
REMOTE_IDENTITY_FIELDS = FILE_IDENTITY_FIELDS

_WRAPPER = re.compile(
    r"#!/usr/bin/env bash\n"
    r"set -euo pipefail\n"
    r"q1_vm=(?P<directory>/[A-Za-z0-9_./-]{1,4094})\n"
    r"exec ssh -F /dev/null \\\n"
    r"  -i \"\$q1_vm/id_ed25519\" -p (?P<port>[1-9][0-9]{0,4}) \\\n"
    r"  -o IdentitiesOnly=yes -o BatchMode=yes \\\n"
    r"  -o StrictHostKeyChecking=accept-new \\\n"
    r"  -o UserKnownHostsFile=\"\$q1_vm/known_hosts\" \\\n"
    r"  -o ConnectTimeout=10 \\\n"
    r"  q1admin@127\.0\.0\.1 \"\$@\"\n"
)


class ConsumedError(RuntimeError):
    """The create-only marker exists or may exist; another request is forbidden."""


def _write_all(fd, raw):
    offset = 0
    while offset < len(raw):
        written = os.write(fd, raw[offset:])
        require(written > 0, "CORE_LOCAL_WRITE")
        offset += written


def _read_all(fd, limit):
    value = bytearray()
    while True:
        raw = os.read(fd, min(65_536, limit + 1 - len(value)))
        if not raw:
            return bytes(value)
        value.extend(raw)
        require(len(value) <= limit, "CORE_LOCAL_READ_LIMIT")


def _identity(st):
    return {
        "dev": st.st_dev,
        "ino": st.st_ino,
        "mode": stat.S_IMODE(st.st_mode),
        "uid": st.st_uid,
        "gid": st.st_gid,
        "nlink": st.st_nlink,
        "bytes": st.st_size,
        "allocated_bytes": st.st_blocks * 512,
    }


def read_regular_at(directory_fd, basename, *, limit, expected_mode=None,
                    expected_sha256=None):
    """Read one stable, single-link regular file relative to a held directory."""
    require(type(basename) is str and "/" not in basename and basename not in ("", ".", ".."),
            "CORE_LOCAL_BASENAME")
    flags = os.O_RDONLY | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(basename, flags, dir_fd=directory_fd)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 <= before.st_size <= limit, "CORE_LOCAL_FILE")
        if expected_mode is not None:
            require(stat.S_IMODE(before.st_mode) == expected_mode, "CORE_LOCAL_MODE")
        raw = _read_all(fd, limit)
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_mode, before.st_nlink, before.st_size,
                 before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_mode, after.st_nlink, after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns)
                and len(raw) == before.st_size, "CORE_LOCAL_FILE_CHANGED")
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 is not None:
            require(digest == expected_sha256, "CORE_LOCAL_DIGEST")
        return raw, dict(_identity(after), sha256=digest)
    finally:
        os.close(fd)


def controlled_environment(source=None):
    """Return A's exact local environment and drop shell/agent injection."""
    source = os.environ if source is None else source
    require(hasattr(source, "get"), "CORE_LOCAL_ENVIRONMENT")
    values = {}
    for key in ("HOME", "USER", "LOGNAME"):
        value = source.get(key)
        require(type(value) is str and value and "\0" not in value,
                "CORE_LOCAL_ENVIRONMENT")
        values[key] = value
    values.update(PATH="/usr/bin:/bin", LANG="C", LC_ALL="C", SYSTEMD_COLORS="0")
    return values


def remote_tokens(loader_raw, bootstrap_raw):
    """Construct the only remote token vector approved by exact A."""
    require(type(loader_raw) is bytes and 0 < len(loader_raw) <= 16384,
            "CORE_LOADER_LIMIT")
    require(type(bootstrap_raw) is bytes and 0 < len(bootstrap_raw) <= 98_304,
            "CORE_BOOTSTRAP_LIMIT")
    try:
        loader = loader_raw.decode("utf-8", "strict")
    except UnicodeError as error:
        raise contract.ContractError("CORE_LOADER_ENCODING") from error
    encoded = base64.b64encode(bootstrap_raw).decode("ascii")
    require(len(encoded.encode("ascii")) <= 131_071, "CORE_BOOTSTRAP_ARGUMENT")
    tokens = [
        "exec", "/usr/bin/sudo", "-n", "--", "/usr/bin/env", "-i",
        "HOME=/root", "PATH=/usr/bin:/bin", "LANG=C", "LC_ALL=C",
        "SYSTEMD_COLORS=0", "/usr/bin/systemd-run", "--system",
        "--no-ask-password", "--quiet", "--wait", "--pipe", "--collect",
        "--service-type=exec", "--unit=lhqcore20261007a-carrier.service",
        "--property=Restart=no", "--property=RuntimeMaxSec=1600s",
        "--property=TimeoutStopSec=60s", "--property=KillMode=control-group",
        "--property=ExitType=cgroup", "--property=CPUQuota=200%",
        "--property=LimitCPU=1600", "--property=MemoryMax=2147483648",
        "--property=MemorySwapMax=0", "--property=TasksMax=256",
        "--property=LimitNOFILE=512", "--property=LimitFSIZE=134217728",
        "--property=UMask=0077", "--", "/usr/bin/python3", "-I", "-B", "-c",
        loader, encoded, hashlib.sha256(bootstrap_raw).hexdigest(),
    ]
    require(all(type(item) is str and item and "\0" not in item for item in tokens),
            "CORE_REMOTE_TOKENS")
    command = shlex.join(tokens)
    require(len(command.encode("utf-8")) <= REMOTE_COMMAND_LIMIT,
            "CORE_REMOTE_COMMAND_LIMIT")
    require(max(len(item.encode("utf-8")) for item in tokens) < LINUX_SINGLE_ARGUMENT_LIMIT,
            "CORE_REMOTE_ARGUMENT_LIMIT")
    return tokens


def wrapper_argv(wrapper_path, wrapper_raw, tokens):
    """Execute the held, exact wrapper bytes without reopening its pathname."""
    require(type(wrapper_path) is str and wrapper_path.startswith("/") and "\0" not in wrapper_path,
            "CORE_WRAPPER_PATH")
    require(type(wrapper_raw) is bytes and hashlib.sha256(wrapper_raw).hexdigest() == WRAPPER_SHA256,
            "CORE_WRAPPER_DIGEST")
    try:
        source = wrapper_raw.decode("utf-8", "strict")
    except UnicodeError as error:
        raise contract.ContractError("CORE_WRAPPER_ENCODING") from error
    match = _WRAPPER.fullmatch(source)
    require(match is not None and int(match["port"]) == 22221,
            "CORE_WRAPPER_PROFILE")
    require(type(tokens) is list and tokens == remote_tokens(
        tokens[-3].encode("utf-8"), base64.b64decode(tokens[-2], validate=True)
    ), "CORE_REMOTE_TOKEN_BINDING")
    argv = ["/usr/bin/env", "bash", "-c", source, wrapper_path, shlex.join(tokens)]
    require(all(type(item) is str and item and "\0" not in item for item in argv),
            "CORE_LOCAL_ARGV")
    return argv


def argv_digest(argv):
    require(type(argv) is list and argv and all(type(item) is str and item and "\0" not in item
                                                for item in argv), "CORE_LOCAL_ARGV")
    return hashlib.sha256(contract.canonical({"schema": contract.CARRIER_ARGV_SCHEMA,
                                               "argv": argv}, newline=True)).hexdigest()


def encoded_argv_environment_size(argv, environment):
    require(type(environment) is dict, "CORE_LOCAL_ENVIRONMENT")
    raw = sum(len(item.encode("utf-8")) + 1 for item in argv)
    raw += sum(len((key + "=" + value).encode("utf-8")) + 1
               for key, value in environment.items())
    try:
        arg_max = os.sysconf("SC_ARG_MAX")
    except (OSError, ValueError) as error:
        raise contract.ContractError("CORE_LOCAL_ARG_MAX") from error
    require(type(arg_max) is int and arg_max > 0 and raw <= LOCAL_ARG_ENV_LIMIT
            and raw <= arg_max, "CORE_LOCAL_ARG_ENV_LIMIT")
    return raw


def field_release_gate(manifest, members):
    """Prove the exact packaged dispatcher is explicitly field-releasable.

    Package syntax and a management preimage are necessary but not sufficient
    to consume the one-shot marker.  This independent digest allowlist stays
    closed to every digest not verified by the private release review.
    Source readiness alone cannot issue a carrier even if a caller supplies
    otherwise well-formed bytes.
    """
    require(type(manifest) is dict and type(members) is dict,
            "CORE_DELIVERY_RELEASE_GATE")
    entry = manifest.get("entry")
    require(type(entry) is dict and type(entry.get("dispatcher_path")) is str
            and type(entry.get("dispatcher_sha256")) is str,
            "CORE_DELIVERY_RELEASE_GATE")
    raw = members.get(entry["dispatcher_path"])
    require(type(raw) is bytes
            and hashlib.sha256(raw).hexdigest() == entry["dispatcher_sha256"],
            "CORE_DELIVERY_RELEASE_GATE")
    readiness = dispatcher_contract.field_readiness()
    contract.exact(readiness, {
        "schema", "scope", "releasable", "unbound_approved_inputs",
        "unimplemented_effects", "protocol_blockers",
    }, "CORE_DELIVERY_RELEASE_GATE")
    require(readiness["schema"] == "local-hand-q2-core-field-readiness/v1"
            and readiness["scope"] == contract.SCOPE
            and readiness["releasable"] is True
            and readiness["unbound_approved_inputs"] == []
            and readiness["unimplemented_effects"] == []
            and readiness["protocol_blockers"] == []
            and entry["dispatcher_sha256"] in RELEASABLE_DISPATCHER_SHA256,
            "CORE_DELIVERY_RELEASE_GATE")
    return {"dispatcher_sha256": entry["dispatcher_sha256"],
            "releasable": True}


def _validate_file_identity(value, *, expected_path=None, expected_sha256=None,
                            private_key=False):
    fields = set(FILE_IDENTITY_FIELDS)
    if private_key:
        fields.remove("sha256")
        fields.add("derived_public_key_sha256")
    contract.exact(value, fields, "CORE_MANAGEMENT_FILE_FIELDS")
    contract.absolute_path(value["path"], "CORE_MANAGEMENT_FILE_PATH")
    if expected_path is not None:
        require(value["path"] == expected_path, "CORE_MANAGEMENT_FILE_PATH")
    for key in ("dev", "ino", "mode", "uid", "gid", "nlink", "bytes"):
        contract.integer(value[key], 0, code="CORE_MANAGEMENT_FILE_IDENTITY")
    require(value["nlink"] == 1 and value["mode"] <= 0o7777,
            "CORE_MANAGEMENT_FILE_IDENTITY")
    digest_key = "derived_public_key_sha256" if private_key else "sha256"
    contract.digest(value[digest_key], "CORE_MANAGEMENT_FILE_DIGEST")
    if expected_sha256 is not None:
        require(value[digest_key] == expected_sha256, "CORE_MANAGEMENT_FILE_DIGEST")
    return value


def static_remote_expectation(tokens):
    """Use the same source-bound expectation constructor as approved inputs."""
    name = "_core_entry_policy_helpers"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(Path(__file__).parent)]
        sys.modules[name] = package
    policy = importlib.import_module(name + ".q2_core_policy_basis")
    return policy.remote_expectation(tokens)


def static_policy_basis(*, source_raw, tokens):
    static_remote_expectation(tokens)
    policy = importlib.import_module("_core_entry_policy_helpers.q2_core_policy_basis")
    return policy.build_policy_basis(source_raw=source_raw, tokens=tokens)


def local_management_binding_digest(value, *, tokens, argv, wrapper_raw):
    """Bind local held identities and static expectations; never guest preimages."""
    contract.exact(value, MANAGEMENT_FIELDS, "CORE_MANAGEMENT_FIELDS")
    require(value["schema"] == contract.MANAGEMENT_BINDING_SCHEMA
            and value["profile"] == "env-bash-literal-ssh-v1",
            "CORE_MANAGEMENT_AUTHORITY")
    anchor, writer = value["anchor"], value["writer"]
    contract.exact(anchor, {"path", "dev", "ino", "mode", "uid", "gid", "nlink"},
                   "CORE_MANAGEMENT_ANCHOR_FIELDS")
    contract.absolute_path(anchor["path"], "CORE_MANAGEMENT_ANCHOR_PATH")
    for key in ("dev", "ino", "mode", "uid", "gid", "nlink"):
        contract.integer(anchor[key], 0, code="CORE_MANAGEMENT_ANCHOR_IDENTITY")
    require(anchor["mode"] == 0o700 and anchor["ino"] > 0 and anchor["nlink"] > 0,
            "CORE_MANAGEMENT_ANCHOR_IDENTITY")
    contract.exact(writer, {"schema", "user_namespace", "pid_namespace", "process",
                            "uid", "gid", "supplementary_gids"}, "CORE_MANAGEMENT_WRITER_FIELDS")
    require(writer["schema"] == "local-hand-q2-core-local-writer/v1", "CORE_MANAGEMENT_WRITER")
    for name in ("user_namespace", "pid_namespace"):
        contract.exact(writer[name], {"dev", "ino"}, "CORE_MANAGEMENT_WRITER_NAMESPACE")
        contract.integer(writer[name]["dev"], 0, code="CORE_MANAGEMENT_WRITER_NAMESPACE")
        contract.integer(writer[name]["ino"], 1, code="CORE_MANAGEMENT_WRITER_NAMESPACE")
    contract.exact(writer["process"], {"pid", "starttime_ticks"}, "CORE_MANAGEMENT_WRITER_PROCESS")
    contract.integer(writer["process"]["pid"], 1, code="CORE_MANAGEMENT_WRITER_PROCESS")
    contract.integer(writer["process"]["starttime_ticks"], 0, code="CORE_MANAGEMENT_WRITER_PROCESS")
    for key in ("uid", "gid"):
        contract.exact(writer[key], {"real", "effective", "saved", "filesystem"},
                       "CORE_MANAGEMENT_WRITER_IDS")
        require(all(type(v) is int and v == anchor[key] for v in writer[key].values()),
                "CORE_MANAGEMENT_WRITER_IDS")
    groups = writer["supplementary_gids"]
    require(type(groups) is list and all(type(v) is int and 0 <= v < 2**63 for v in groups)
            and groups == sorted(set(groups)), "CORE_MANAGEMENT_WRITER_GROUPS")
    _validate_file_identity(value["wrapper"], expected_sha256=WRAPPER_SHA256)
    _validate_file_identity(value["fixture_start"], expected_sha256=START_SHA256)
    _validate_file_identity(value["fixture_cloud_config"], expected_sha256=CLOUD_CONFIG_SHA256)
    _validate_file_identity(value["identity_public"], expected_sha256=PUBLIC_KEY_SHA256)
    _validate_file_identity(value["known_hosts"], expected_sha256=KNOWN_HOSTS_SHA256)
    _validate_file_identity(value["identity"], expected_sha256=PUBLIC_KEY_SHA256,
                            private_key=True)
    require(value["wrapper"]["path"] == argv[4]
            and hashlib.sha256(wrapper_raw).hexdigest() == value["wrapper"]["sha256"],
            "CORE_MANAGEMENT_WRAPPER_BINDING")

    dependencies = value["dependencies"]
    expected_dependencies = (
        ("env", "/usr/bin/env"), ("bash", "/usr/bin/bash"),
        ("ssh", "/usr/bin/ssh"), ("ssh-keygen", "/usr/bin/ssh-keygen"),
    )
    require(type(dependencies) is list and len(dependencies) == 4,
            "CORE_MANAGEMENT_DEPENDENCIES")
    for item, (role, path) in zip(dependencies, expected_dependencies, strict=True):
        contract.exact(item, FILE_IDENTITY_FIELDS | {"role"},
                       "CORE_MANAGEMENT_DEPENDENCY_FIELDS")
        require(item["role"] == role, "CORE_MANAGEMENT_DEPENDENCIES")
        _validate_file_identity({key: child for key, child in item.items() if key != "role"},
                                expected_path=path)

    environment = value["environment"]
    contract.exact(environment, {"HOME", "USER", "LOGNAME", "PATH", "LANG", "LC_ALL",
                                 "SYSTEMD_COLORS"}, "CORE_MANAGEMENT_ENVIRONMENT")
    require(environment == controlled_environment(environment), "CORE_MANAGEMENT_ENVIRONMENT")
    cwd = value["cwd"]
    contract.exact(cwd, {"path", "dev", "ino", "mode", "uid", "gid"},
                   "CORE_MANAGEMENT_CWD_FIELDS")
    contract.absolute_path(cwd["path"], "CORE_MANAGEMENT_CWD_PATH")
    for key in ("dev", "ino", "mode", "uid", "gid"):
        contract.integer(cwd[key], 0, code="CORE_MANAGEMENT_CWD_IDENTITY")

    require(value["remote_expectation"] == static_remote_expectation(tokens),
            "CORE_MANAGEMENT_REMOTE_COMMAND")

    transport = value["transport"]
    transport_fields = {
        "no_pty", "stdin_binary", "stdout_stderr_separate", "known_host_preexisting",
        "batch_mode", "invocation_matches_frozen_command", "sudo_noninteractive",
        "sudo_no_password", "sudo_policy_is_exact", "fixture_policy_broader_than_command",
    }
    contract.exact(transport, transport_fields, "CORE_MANAGEMENT_TRANSPORT_FIELDS")
    require(all(type(transport[key]) is bool for key in transport_fields),
            "CORE_MANAGEMENT_TRANSPORT")
    require(transport["sudo_policy_is_exact"] is False
            and all(transport[key] is True for key in transport_fields
                    if key != "sudo_policy_is_exact"), "CORE_MANAGEMENT_TRANSPORT")
    expected_argv = wrapper_argv(value["wrapper"]["path"], wrapper_raw, tokens)
    require(argv == expected_argv, "CORE_MANAGEMENT_ARGV")
    return hashlib.sha256(contract.canonical(value, newline=True)).hexdigest()


def _stable_fd_bytes(fd, *, expected, call, read_content=True):
    """Requalify one already-open local object without following another name."""
    require(type(fd) is int and fd >= 0 and type(expected) is dict,
            "CORE_MANAGEMENT_HELD_FD")
    before = call(os.fstat, fd)
    actual = {
        "dev": before.st_dev, "ino": before.st_ino,
        "mode": stat.S_IMODE(before.st_mode), "uid": before.st_uid,
        "gid": before.st_gid, "nlink": before.st_nlink, "bytes": before.st_size,
    }
    for key, observed in actual.items():
        require(expected[key] == observed, "CORE_MANAGEMENT_HELD_IDENTITY")
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
            "CORE_MANAGEMENT_HELD_IDENTITY")
    raw = None
    if read_content:
        chunks = bytearray()
        offset = 0
        while offset < before.st_size:
            chunk = call(os.pread, fd, min(65_536, before.st_size - offset), offset)
            require(chunk, "CORE_MANAGEMENT_HELD_SHORT_READ")
            chunks.extend(chunk); offset += len(chunk)
        raw = bytes(chunks)
        require(len(raw) == before.st_size
                and hashlib.sha256(raw).hexdigest() == expected["sha256"],
                "CORE_MANAGEMENT_HELD_DIGEST")
    after = call(os.fstat, fd)
    require((before.st_dev, before.st_ino, before.st_mode, before.st_uid, before.st_gid,
             before.st_nlink, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_gid,
                after.st_nlink, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            "CORE_MANAGEMENT_HELD_CHANGED")
    return raw


def _open_held_regular(path=None, *, directory_fd=None, basename=None, call, noatime=True):
    require(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_NOATIME"), "CORE_MANAGEMENT_READ_FLAGS")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    if noatime:
        flags |= os.O_NOATIME
    if directory_fd is None:
        return call(os.open, path, flags)
    return call(os.open, basename, flags, dir_fd=directory_fd)


def requalify_management_anchor(directory_fd, binding, *, tokens, argv, deadline, environment=None):
    """Hold and requalify every local management object used by the one request.

    Remote program identities are intentionally not read here: current guest
    policy/program attestation belongs to the already-consumed remote admission
    step.  The returned CLOEXEC descriptors remain held by the caller through
    marker creation and ``Popen`` return, closing the local name-replacement
    interval without leaking descriptors into the carrier.
    """
    require(type(directory_fd) is int and directory_fd >= 0, "CORE_MANAGEMENT_ANCHOR")
    call = deadline.call
    anchor = call(os.fstat, directory_fd)
    require(stat.S_ISDIR(anchor.st_mode), "CORE_MANAGEMENT_ANCHOR")
    anchor_paths = [binding[key]["path"] for key in (
        "wrapper", "fixture_start", "fixture_cloud_config", "identity",
        "identity_public", "known_hosts",
    )]
    anchor_parent = str(Path(anchor_paths[0]).parent)
    require(all(str(Path(path).parent) == anchor_parent for path in anchor_paths),
            "CORE_MANAGEMENT_ANCHOR_PATH")
    current_anchor = call(os.stat, anchor_parent, follow_symlinks=False)
    require(stat.S_ISDIR(current_anchor.st_mode)
            and (current_anchor.st_dev, current_anchor.st_ino)
            == (anchor.st_dev, anchor.st_ino), "CORE_MANAGEMENT_ANCHOR_CHANGED")
    expected_anchor = binding["anchor"]
    require(anchor_parent == expected_anchor["path"] and
            (anchor.st_dev, anchor.st_ino, stat.S_IMODE(anchor.st_mode), anchor.st_uid,
             anchor.st_gid, anchor.st_nlink) == tuple(expected_anchor[key] for key in
                ("dev", "ino", "mode", "uid", "gid", "nlink")), "CORE_MANAGEMENT_ANCHOR_CHANGED")
    require(capture_contract.observe_writer(call) == binding["writer"], "CORE_MANAGEMENT_WRITER_CHANGED")

    held = []
    raw = {}
    try:
        for role in ("wrapper", "fixture_start", "fixture_cloud_config",
                     "identity_public", "known_hosts"):
            record = binding[role]
            basename = Path(record["path"]).name
            fd = _open_held_regular(directory_fd=directory_fd, basename=basename, call=call)
            held.append(fd)
            raw[role] = _stable_fd_bytes(fd, expected=record, call=call)
        private = binding["identity"]
        private_fd = _open_held_regular(
            directory_fd=directory_fd, basename=Path(private["path"]).name, call=call)
        held.append(private_fd)
        _stable_fd_bytes(private_fd, expected=private, call=call, read_content=False)
        require(private["derived_public_key_sha256"] == PUBLIC_KEY_SHA256
                and hashlib.sha256(raw["identity_public"]).hexdigest()
                == private["derived_public_key_sha256"],
                "CORE_MANAGEMENT_PRIVATE_PUBLIC_BINDING")

        for record in binding["dependencies"]:
            # Preserve the admitted dependency read profile. This is not a
            # retry/fallback from an EPERM on a private/capture object.
            fd = _open_held_regular(record["path"], call=call, noatime=False)
            held.append(fd)
            _stable_fd_bytes(fd, expected=record, call=call)

        cwd_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NOATIME
        cwd_fd = call(os.open, binding["cwd"]["path"], cwd_flags)
        held.append(cwd_fd)
        cwd = call(os.fstat, cwd_fd)
        expected_cwd = binding["cwd"]
        require(stat.S_ISDIR(cwd.st_mode)
                and (cwd.st_dev, cwd.st_ino, stat.S_IMODE(cwd.st_mode), cwd.st_uid, cwd.st_gid)
                == tuple(expected_cwd[key] for key in ("dev", "ino", "mode", "uid", "gid")),
                "CORE_MANAGEMENT_CWD_CHANGED")

        selected_environment = controlled_environment() if environment is None else environment
        require(selected_environment == binding["environment"],
                "CORE_MANAGEMENT_ENVIRONMENT_CHANGED")
        digest = local_management_binding_digest(binding, tokens=tokens, argv=argv,
                                           wrapper_raw=raw["wrapper"])
        require(capture_contract.observe_writer(call) == binding["writer"], "CORE_MANAGEMENT_WRITER_CHANGED")
        return {"fds": held, "wrapper_raw": raw["wrapper"],
                "environment": dict(selected_environment), "binding_sha256": digest,
                "anchor_dev": anchor.st_dev, "anchor_ino": anchor.st_ino, "deadline": deadline}
    except BaseException:
        for fd in held:
            try:
                call(os.close, fd)
            except (OSError, capture_contract.CaptureError):
                pass
        raise


def close_held_management(value):
    fds = value.get("fds", []) if type(value) is dict else []
    for fd in fds:
        try:
            value["deadline"].call(os.close, fd)
        except (OSError, capture_contract.CaptureError):
            pass
    if type(value) is dict:
        value["fds"] = []


def freeze_host_window(clock_gettime_ns=time.clock_gettime_ns):
    boot = clock_gettime_ns(time.CLOCK_BOOTTIME)
    mono = clock_gettime_ns(time.CLOCK_MONOTONIC)
    require(type(boot) is int and type(mono) is int and boot > 0 and mono > 0,
            "CORE_HOST_CLOCK")
    return {
        "host_boottime_origin_ns": boot,
        "host_monotonic_origin_ns": mono,
        "host_boottime_deadline_ns": boot + HOST_WINDOW_NS,
        "host_monotonic_deadline_ns": mono + HOST_WINDOW_NS,
    }


def build_bind(hello, consumption_sha256, package_basename, package_raw, origins,
               *, package_entry, remote_expectation, boot_bind_ns, mono_bind_ns):
    contract.exact(package_entry, {
        "loader_path", "loader_bytes", "loader_sha256", "bootstrap_path",
        "bootstrap_bytes", "bootstrap_sha256", "dispatcher_path",
        "dispatcher_bytes", "dispatcher_sha256", "carrier_argv_sha256",
        "local_management_binding_sha256", "writer",
    }, "CORE_BIND_PACKAGE_ENTRY")
    contract.validate_local_writer(package_entry["writer"])
    contract.validate_hello(
        hello,
        loader_sha256=package_entry["loader_sha256"],
        bootstrap_sha256=package_entry["bootstrap_sha256"],
        remote_expectation=remote_expectation,
    )
    contract.digest(consumption_sha256, "CORE_BIND_CONSUMPTION")
    require(type(package_raw) is bytes and 0 < len(package_raw) <= contract.PACKAGE_LIMITS["package_bytes"],
            "CORE_BIND_PACKAGE")
    require(set(origins) == {
        "host_boottime_origin_ns", "host_monotonic_origin_ns",
        "host_boottime_deadline_ns", "host_monotonic_deadline_ns",
    }, "CORE_BIND_HOST_WINDOW")
    require(origins["host_boottime_deadline_ns"]
            == origins["host_boottime_origin_ns"] + HOST_WINDOW_NS
            and origins["host_monotonic_deadline_ns"]
            == origins["host_monotonic_origin_ns"] + HOST_WINDOW_NS
            and boot_bind_ns >= origins["host_boottime_origin_ns"]
            and mono_bind_ns >= origins["host_monotonic_origin_ns"],
            "CORE_BIND_HOST_WINDOW")
    remaining = min(origins["host_boottime_deadline_ns"] - boot_bind_ns,
                    origins["host_monotonic_deadline_ns"] - mono_bind_ns)
    floor = remaining // 1_000_000 * 1_000_000
    mapped = floor - CLOCK_MARGIN_NS - LOCAL_FINAL_RESERVE_NS
    require(mapped > 0, "CORE_BIND_EXPIRED")
    value = {
        "schema": "local-hand-q2-core-carrier-bind/v1",
        "scope": contract.SCOPE,
        "session_id": contract.SESSION_ID,
        "hello_sha256": hashlib.sha256(contract.canonical(hello, newline=True)).hexdigest(),
        "consumption_sha256": consumption_sha256,
        "package_basename": package_basename,
        "package_bytes": len(package_raw),
        "package_sha256": hashlib.sha256(package_raw).hexdigest(),
        **origins,
        "host_boottime_bind_ns": boot_bind_ns,
        "host_monotonic_bind_ns": mono_bind_ns,
        "host_remaining_floor_ns": floor,
        "clock_margin_ns": CLOCK_MARGIN_NS,
        "local_final_reserve_ns": LOCAL_FINAL_RESERVE_NS,
        "mapped_duration_ns": mapped,
        "guest_duration_cap_ns": GUEST_CAP_NS,
        "guest_duration_ns": min(mapped, GUEST_CAP_NS),
    }
    contract.validate_bind(value)
    package_api = _helper("q2_core_delivery_package")
    frozen_manifest, frozen_members = package_api.parse_package(package_raw)
    approved = contract.document(frozen_members[frozen_manifest['approved_inputs']['path']],
                                 limit=contract.APPROVED_INPUTS_LIMIT,newline=True)
    package_api._approved_module().prior_attempt.validate_journal_transition(
        approved['reconciliation']['journal_transition'],
        priors=approved['reconciliation']['prior_core_attempts'],
        implementation=frozen_manifest['implementation'],current_boot=hello['guest_boot_id'])
    return value


def frame(magic, value, *, json_limit):
    raw = contract.canonical(value, newline=True, limit=json_limit)
    return magic + struct.pack(">Q", len(raw)) + raw


def parse_frame(raw, magic, *, json_limit, total_limit, trailing=False):
    require(type(raw) is bytes and len(raw) <= total_limit and raw.startswith(magic)
            and len(raw) >= len(magic) + 8, "CORE_FRAME")
    length = struct.unpack(">Q", raw[len(magic):len(magic) + 8])[0]
    require(0 < length <= json_limit, "CORE_FRAME_LENGTH")
    end = len(magic) + 8 + length
    require(end <= len(raw) and (trailing or end == len(raw)), "CORE_FRAME_BOUNDARY")
    value = contract.document(raw[len(magic) + 8:end], limit=json_limit, newline=True)
    return value, raw[end:]


def consumption_record(*, implementation, amendment, package, approved_inputs_sha256,
                       local_management_binding_sha256, writer, carrier_argv_sha256, origins):
    contract.validate_amendment(amendment, implementation=implementation)
    contract.validate_local_writer(writer)
    for item in (local_management_binding_sha256, carrier_argv_sha256, approved_inputs_sha256):
        contract.digest(item, "CORE_MARKER_DIGEST")
    require(set(origins) == {
        "host_boottime_origin_ns", "host_monotonic_origin_ns",
        "host_boottime_deadline_ns", "host_monotonic_deadline_ns",
    } and origins["host_boottime_deadline_ns"]
        == origins["host_boottime_origin_ns"] + HOST_WINDOW_NS
        and origins["host_monotonic_deadline_ns"]
        == origins["host_monotonic_origin_ns"] + HOST_WINDOW_NS,
        "CORE_MARKER_HOST_WINDOW")
    value = {
        "schema": contract.CONSUMPTION_SCHEMA,
        "scope": contract.SCOPE,
        "session_id": contract.SESSION_ID,
        "baseline": contract.BASELINE,
        "owner_decision": contract.OWNER_DECISION,
        "closure": contract.CLOSURE,
        "implementation": implementation,
        "amendment": amendment,
        "candidate": contract.CANDIDATE,
        "package": package,
        "approved_inputs_sha256": approved_inputs_sha256,
        "local_management_binding_sha256": local_management_binding_sha256,
        "writer": writer,
        "carrier_argv_sha256": carrier_argv_sha256,
        **origins,
        "state": "CONSUMPTION_RECORD_COMPLETE",
    }
    contract.exact(value, (
        "schema", "scope", "session_id", "baseline", "owner_decision", "closure",
        "implementation", "amendment", "candidate", "package", "approved_inputs_sha256",
        "local_management_binding_sha256", "writer",
        "carrier_argv_sha256", "host_boottime_origin_ns", "host_monotonic_origin_ns",
        "host_boottime_deadline_ns", "host_monotonic_deadline_ns", "state",
    ), "CORE_MARKER_FIELDS")
    return value


def create_consumption_marker(directory_fd, value, *, capture):
    """Irreversibly consume the one delivery with a final-name O_EXCL write."""
    raw = contract.canonical(value, newline=True, limit=MARKER_LIMIT)
    require(capture.directory_fd == directory_fd, "CORE_CAPTURE_HELD_PARENT")
    require(value.get("writer") == capture.writer, "CORE_MARKER_CAPTURE_WRITER")
    require(all(value.get(key) == expected for key, expected in capture.deadline.origins.items()),
            "CORE_MARKER_CAPTURE_WINDOW")
    if "marker" in capture.attempted:
        raise ConsumedError("CORE_MARKER_ALREADY_CONSUMED")
    try:
        item = capture.create("marker", raw)
    except FileExistsError as error:
        raise ConsumedError("CORE_MARKER_ALREADY_CONSUMED") from error
    except BaseException as error:
        if "marker" not in capture.objects:
            raise
        raise ConsumedError("CORE_MARKER_PARTIAL_CONSUMED") from error
    return {
        "object_created": True,
        "record_complete": True,
        **item,
    }


def create_capture_file(directory_fd, basename, raw, *, limit, capture):
    """Create, fsync and stable-reread one final capture object; never replace."""
    require(type(raw) is bytes and len(raw) <= limit, "CORE_CAPTURE_LIMIT")
    require(basename in set(contract.OUTPUT_BASENAMES.values()), "CORE_CAPTURE_BASENAME")
    require(capture.directory_fd == directory_fd, "CORE_CAPTURE_HELD_PARENT")
    role = next(key for key, name in capture_contract.BASENAMES.items() if name == basename)
    return capture.create(role, raw)


def parse_output(raw):
    """Parse an exact LHCOUT1 frame and verify every raw member and EOF."""
    manifest, payload = parse_frame(raw, contract.OUTPUT_MAGIC,
                                    json_limit=1_048_576,
                                    total_limit=contract.LIMITS["output_package_bytes"],
                                    trailing=True)
    contract.validate_record(manifest, "local-hand-q2-core-output-package/v1")
    require(manifest["schema"] == "local-hand-q2-core-output-package/v1"
            and manifest["session_id"] == contract.SESSION_ID,
            "CORE_OUTPUT_AUTHORITY")
    members = manifest["members"]
    require(type(members) is list and len(members) <= 4096, "CORE_OUTPUT_MEMBERS")
    previous = None
    values = {}
    offset = 0
    for item in members:
        contract.exact(item, ("path", "case_id", "role", "mode", "bytes", "sha256"),
                       "CORE_OUTPUT_MEMBER_FIELDS")
        path = contract.relative_path(item["path"], "CORE_OUTPUT_PATH")
        require(previous is None or previous.encode("ascii") < path.encode("ascii"),
                "CORE_OUTPUT_ORDER")
        previous = path
        size = contract.integer(item["bytes"], 0, 16_777_216, "CORE_OUTPUT_MEMBER_BYTES")
        contract.digest(item["sha256"], "CORE_OUTPUT_MEMBER_DIGEST")
        require(item["mode"] in (384, 420), "CORE_OUTPUT_MEMBER_MODE")
        end = offset + size
        require(end <= len(payload), "CORE_OUTPUT_SHORT")
        member = payload[offset:end]
        require(hashlib.sha256(member).hexdigest() == item["sha256"],
                "CORE_OUTPUT_MEMBER_CONTENT")
        values[path] = member
        offset = end
    require(offset == len(payload), "CORE_OUTPUT_TRAILING")
    require(manifest["cases"] == manifest["remote_result"]["cases"],
            "CORE_OUTPUT_CASES")
    contract.validate_record(manifest["remote_result"], contract.REMOTE_RESULT_SCHEMA)
    return manifest, values


def marker_absent(directory_fd):
    """A non-mutating gate; any object or lookup ambiguity is already consumed."""
    try:
        os.stat(contract.MARKER_BASENAME, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return True
    raise ConsumedError("CORE_MARKER_ALREADY_CONSUMED")


def output_names_absent(directory_fd):
    for basename in sorted(contract.OUTPUT_BASENAMES.values()):
        try:
            os.stat(basename, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        raise ConsumedError("CORE_OUTPUT_NAME_EXISTS:" + basename)
    return True


def _missing(code, role, detail):
    require(type(code) is str and code.isascii() and code
            and type(role) is str and role.isascii() and role,
            "CORE_LOCAL_MISSING")
    return {"code": code, "role": role,
            "detail_sha256": hashlib.sha256(contract.canonical(detail)).hexdigest()}


def _validate_missing(value, code="CORE_REMOTE_MISSING"):
    require(type(value) is list, code)
    previous = None
    for item in value:
        contract.exact(item, MISSING_FIELDS, code)
        require(type(item["code"]) is str and item["code"].isascii() and item["code"]
                and type(item["role"]) is str and item["role"].isascii() and item["role"], code)
        contract.digest(item["detail_sha256"], code)
        ordering = (item["code"].encode("ascii"), item["role"].encode("ascii"),
                    item["detail_sha256"].encode("ascii"))
        require(previous is None or previous < ordering, code)
        previous = ordering
    return value


def _plain_member(item):
    return {key: item[key] for key in ("role", "path", "bytes", "sha256")}


def _document_member(values, path, *, limit=16_777_216):
    require(path in values, "CORE_OUTPUT_MEMBER_MISSING")
    return contract.document(values[path], limit=limit, newline=True)


def _validate_case_index(cases, members):
    require(type(cases) is list and len(cases) == 3, "CORE_REMOTE_CASES")
    statuses = []
    by_path = {item["path"]: item for item in members}
    for case, fixed in zip(cases, contract.CASES, strict=True):
        contract.exact(case, CASE_INDEX_FIELDS, "CORE_REMOTE_CASE_FIELDS")
        require(case["index"] == fixed["index"] and case["case_id"] == fixed["case_id"]
                and case["status"] in ("NOT_RUN", "PASS", "INCOMPLETE")
                and type(case["semantic_pass"]) is bool,
                "CORE_REMOTE_CASE")
        status = case["status"]; statuses.append(status)
        if status == "NOT_RUN":
            require(case["semantic_pass"] is False and case["verdict_path"] is None
                    and case["verdict_sha256"] is None, "CORE_REMOTE_CASE_NOT_RUN")
        else:
            require(case["semantic_pass"] is (status == "PASS"), "CORE_REMOTE_CASE_STATUS")
            both_null = case["verdict_path"] is None and case["verdict_sha256"] is None
            if status == "PASS":
                require(not both_null, "CORE_REMOTE_CASE_VERDICT")
            if not both_null:
                expected_path = "cases/" + fixed["case_id"] + "/reservation/case-verdict.json"
                require(case["verdict_path"] == expected_path
                        and expected_path in by_path
                        and by_path[expected_path]["role"] == "verdict"
                        and case["verdict_sha256"] == by_path[expected_path]["sha256"],
                        "CORE_REMOTE_CASE_VERDICT")
            else:
                require(status == "INCOMPLETE", "CORE_REMOTE_CASE_VERDICT")
    allowed = {
        ("PASS", "PASS", "PASS"), ("NOT_RUN", "NOT_RUN", "NOT_RUN"),
        ("INCOMPLETE", "NOT_RUN", "NOT_RUN"), ("PASS", "NOT_RUN", "NOT_RUN"),
        ("PASS", "INCOMPLETE", "NOT_RUN"), ("PASS", "PASS", "NOT_RUN"),
        ("PASS", "PASS", "INCOMPLETE"),
    }
    require(tuple(statuses) in allowed, "CORE_REMOTE_CASE_PREFIX")
    return statuses


def _validate_h01_summaries(remote, members):
    execution = remote["h01_business_execution"]
    package = remote["h01_result_package"]
    contract.exact(execution, H01_EXECUTION_FIELDS, "CORE_REMOTE_H01_EXECUTION_FIELDS")
    contract.exact(package, H01_PACKAGE_FIELDS, "CORE_REMOTE_H01_PACKAGE_FIELDS")
    require(execution["status"] in ("NOT_RUN", "INCOMPLETE", "VERIFIED")
            and package["status"] in ("NOT_RUN", "INCOMPLETE", "VERIFIED")
            and type(execution["business_started"]) is bool
            and execution["outcome"] in ("NOT_RUN", "SUCCEEDED", "FAILED", "UNKNOWN"),
            "CORE_REMOTE_H01_SUMMARY")
    for key in ("operation_id", "execution_id", "unit", "invocation_id", "evidence_sha256"):
        require(execution[key] is None or type(execution[key]) is str,
                "CORE_REMOTE_H01_SUMMARY")
    require(execution["wait_status"] is None or type(execution["wait_status"]) is int,
            "CORE_REMOTE_H01_SUMMARY")
    if execution["evidence_sha256"] is not None:
        contract.digest(execution["evidence_sha256"], "CORE_REMOTE_H01_SUMMARY")
    for key in ("result_sha256", "required_members_sha256"):
        if package[key] is not None:
            contract.digest(package[key], "CORE_REMOTE_H01_SUMMARY")
    by_path = {item["path"]: item for item in members}
    result_member = package["result_member"]
    if result_member is None:
        require(package["result_sha256"] is None, "CORE_REMOTE_H01_RESULT")
    else:
        contract.exact(result_member, ("role", "path", "bytes", "sha256"),
                       "CORE_REMOTE_H01_RESULT_FIELDS")
        require(result_member["path"] in by_path
                and _plain_member(by_path[result_member["path"]]) == result_member
                and result_member["role"] == "result"
                and package["result_sha256"] == result_member["sha256"],
                "CORE_REMOTE_H01_RESULT")
    h01_status = remote["cases"][0]["status"]
    if h01_status == "NOT_RUN":
        require(execution == {
            "status": "NOT_RUN", "operation_id": None, "execution_id": None,
            "unit": None, "invocation_id": None, "wait_status": None,
            "business_started": False, "outcome": "NOT_RUN", "evidence_sha256": None,
        } and package == {
            "status": "NOT_RUN", "result_member": None, "result_sha256": None,
            "required_members_sha256": None,
        }, "CORE_REMOTE_H01_NOT_RUN")
    elif h01_status == "PASS":
        require(execution["status"] == package["status"] == "VERIFIED"
                and execution["operation_id"] == contract.CASES[0]["operation_id"]
                and execution["business_started"] is True
                and execution["outcome"] == "SUCCEEDED"
                and all(execution[key] is not None for key in
                        ("execution_id", "unit", "invocation_id", "wait_status", "evidence_sha256"))
                and result_member is not None and package["required_members_sha256"] is not None,
                "CORE_REMOTE_H01_PASS")
    else:
        require(execution["status"] != "VERIFIED" and package["status"] != "VERIFIED",
                "CORE_REMOTE_H01_INCOMPLETE")
    return execution, package


def _seal_id(members):
    pattern = re.compile(
        r"cases/c01-h01-normal/business-evidence/"
        r"([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/"
        r"seal\.json")
    found = [pattern.fullmatch(item["path"]) for item in members]
    values = {item.group(1) for item in found if item is not None}
    require(len(values) == 1, "CORE_OUTPUT_H01_SEAL")
    return next(iter(values))


def _deep_validate_pass_case(fixed, case_index, members, values, remote):
    selected = [item for item in members if item["case_id"] == fixed["case_id"]]
    sources = [{"path": item["path"], "role": item["role"], "mode": item["mode"],
                "raw": values[item["path"]]} for item in selected]
    seal_id = _seal_id(selected) if fixed["index"] == 1 else None
    dispatcher_contract._validate_source_set(fixed, sources, seal_id=seal_id)
    prefix = "cases/" + fixed["case_id"] + "/"
    verdict_path = prefix + "reservation/case-verdict.json"
    plan_path = prefix + "reservation/case-plan.json"
    verdict = _document_member(values, verdict_path)
    contract.validate_record(verdict, "local-hand-q2-core-case-verdict/v1")
    plan = _document_member(values, plan_path)
    intent = _document_member(values, prefix + "intent.json")
    require(intent == dispatcher_contract.build_intent(fixed), "CORE_OUTPUT_INTENT_BINDING")
    dispatcher_contract.validate_plan(fixed, intent, plan, plan["deadlines"])
    proof = None
    if fixed["index"] == 3:
        proof = _document_member(values, prefix + "reservation/h11-recovery-proof.json")
    expected = dispatcher_contract._validate_verdict(
        fixed, verdict["observations"], verdict["stop"], sources, proof,
        plan["deadlines"]["owner_deadline_ns"])
    require(verdict == expected and case_index["verdict_sha256"]
            == hashlib.sha256(values[verdict_path]).hexdigest(),
            "CORE_OUTPUT_VERDICT_BINDING")
    if fixed["index"] == 1:
        execution = remote["h01_business_execution"]
        expected_summary = dispatcher_contract._h01_summary(
            fixed, sources, {"business_invocation_id": execution["invocation_id"],
                             "business_wait_status": execution["wait_status"]}, seal_id)
        require(remote["h01_business_execution"] == expected_summary["h01_business_execution"]
                and remote["h01_result_package"] == expected_summary["h01_result_package"],
                "CORE_OUTPUT_H01_SUMMARY_BINDING")
    return sources


def _contains_unit_identity(value, unit, invocation_id):
    if type(value) is dict:
        if value.get("unit") == unit and value.get("invocation_id") == invocation_id:
            return True
        return any(_contains_unit_identity(item, unit, invocation_id)
                   for item in value.values())
    if type(value) is list:
        return any(_contains_unit_identity(item, unit, invocation_id) for item in value)
    return False


def _h01_truth_binding(remote, values):
    """Require raw H01 producer bytes, not only the remote summary."""
    execution = remote["h01_business_execution"]
    prefix = "cases/c01-h01-normal/"
    verdict = _document_member(values, prefix + "reservation/case-verdict.json")
    unit_rows = verdict["observations"]["unit_identities"]
    require(any(row == {"phase": "business", "stage": "helper",
                        "unit": execution["unit"], "invocation_id": execution["invocation_id"]}
                for row in unit_rows), "CORE_LOCAL_H01_UNIT_BINDING")
    gateway = _document_member(values, prefix + "launcher_output/gateway.json")
    launcher = _document_member(values, prefix + "launcher_output/result.json")
    require(_contains_unit_identity(gateway, execution["unit"], execution["invocation_id"])
            and _contains_unit_identity(launcher, execution["unit"], execution["invocation_id"]),
            "CORE_LOCAL_H01_RAW_UNIT_BINDING")
    wait = _document_member(values, prefix + "launcher_output/capture.json")
    require(wait.get("returncode") == execution["wait_status"]
            and wait.get("complete") is True
            and set(wait.get("eof", [])) == {"stdout", "stderr"},
            "CORE_LOCAL_H01_WAIT_BINDING")
    receipt = _document_member(values, prefix + "reservation/phase-business-receipt.json")
    contract.validate_record(receipt, "local-hand-q2-core-phase-receipt/v1")
    require(receipt["phase"] == "business" and receipt["case_id"] == contract.CASES[0]["case_id"],
            "CORE_LOCAL_H01_RECEIPT_BINDING")
    return True


def _validate_carrier_bindings(values, expected):
    """Recompute the guest's v2 input links from this live host's frozen bytes."""
    require(type(expected) is dict, "CORE_OUTPUT_FROZEN_CONTEXT_REQUIRED")
    frozen = expected["manifest"]
    session = _document_member(values, "carrier/session.json")
    admission = _document_member(values, "carrier/admission.json")
    installation = _document_member(values, "carrier/installation.json")
    contract.validate_record(session, "local-hand-q2-core-dispatch-session/v2")
    for key in ("scope", "rule", "baseline", "owner_decision", "closure", "implementation",
                "amendment", "entry", "locators"):
        require(contract.canonical(session[key]) == contract.canonical(frozen[key]),
                "CORE_OUTPUT_SESSION_BINDING")
    require(session["session_id"] == contract.SESSION_ID
            and session["admission"] == admission
            and session["installation"] == installation, "CORE_OUTPUT_CARRIER_SIBLING_BINDING")
    contract.validate_admission_binding(admission["binding"],
        approved_inputs_raw=expected["approved_inputs_raw"],
        local_management_binding=expected["binding"], hello=expected["hello"],
        amendment=frozen["amendment"])
    dispatcher_contract._validate_installation(installation, frozen)
    marker, bind = expected["marker"], expected["bind"]
    writer = contract.validate_local_writer(expected["binding"]["writer"])
    require(contract.canonical(frozen["entry"]["writer"]) == contract.canonical(writer),
            "CORE_OUTPUT_WRITER_BINDING")
    marker_record = consumption_record(
        implementation=frozen["implementation"], amendment=frozen["amendment"],
        package={"basename": bind["package_basename"], "bytes": bind["package_bytes"],
                 "sha256": bind["package_sha256"],
                 "manifest_sha256": contract.sha256(contract.canonical(frozen, newline=True))},
        approved_inputs_sha256=frozen["approved_inputs"]["sha256"],
        local_management_binding_sha256=frozen["entry"]["local_management_binding_sha256"],
        writer=writer, carrier_argv_sha256=frozen["entry"]["carrier_argv_sha256"],
        origins={key: bind[key] for key in ("host_boottime_origin_ns", "host_monotonic_origin_ns",
                                          "host_boottime_deadline_ns", "host_monotonic_deadline_ns")})
    marker_raw = contract.canonical(marker_record, newline=True, limit=MARKER_LIMIT)
    require(marker["basename"] == contract.MARKER_BASENAME
            and marker["bytes"] == len(marker_raw)
            and marker["sha256"] == bind["consumption_sha256"] == contract.sha256(marker_raw),
            "CORE_OUTPUT_HOST_MARKER_BINDING")
    require(session["consumption"] == {"basename": marker["basename"], "bytes": marker["bytes"],
                "sha256": marker["sha256"], "state": "CONSUMPTION_RECORD_COMPLETE"},
            "CORE_OUTPUT_CONSUMPTION_BINDING")
    require(session["package"] == {"basename": bind["package_basename"],
                "bytes": bind["package_bytes"], "sha256": bind["package_sha256"],
                "manifest_sha256": hashlib.sha256(contract.canonical(frozen, newline=True)).hexdigest()},
            "CORE_OUTPUT_PACKAGE_BINDING")
    hello = expected["hello"]
    bind_keys = ("host_boottime_origin_ns", "host_monotonic_origin_ns", "host_boottime_deadline_ns",
        "host_monotonic_deadline_ns", "clock_margin_ns", "host_boottime_bind_ns", "host_monotonic_bind_ns",
        "hello_sha256", "mapped_duration_ns", "host_remaining_floor_ns", "guest_duration_cap_ns",
        "guest_duration_ns", "local_final_reserve_ns")
    outer = {key: bind[key] for key in bind_keys}
    outer.update(guest_boot_id=hello["guest_boot_id"],
        guest_boottime_origin_ns=hello["guest_boottime_origin_ns"],
        guest_monotonic_origin_ns=hello["guest_monotonic_origin_ns"],
        guest_boottime_deadline_ns=hello["guest_boottime_origin_ns"] + bind["guest_duration_ns"],
        guest_monotonic_deadline_ns=hello["guest_monotonic_origin_ns"] + bind["guest_duration_ns"],
        remote_final_reserve_ns=dispatcher_contract.REMOTE_FINAL_RESERVE_NS)
    require(session["outer"] == outer, "CORE_OUTPUT_OUTER_BINDING")
    dispatcher_contract._validate_admission(admission, {
        "manifest": frozen,
        "members": {dispatcher_contract.APPROVED_INPUTS_PATH: expected["approved_inputs_raw"]},
        "hello": hello,
        "guest_deadlines": {clock + "_deadline_ns": outer["guest_" + clock + "_deadline_ns"]
                            for clock in ("boottime", "monotonic")},
    })


def validate_output_semantics(manifest, values, *, consumption_sha256,
                              stdin_bytes_received, frame_bytes, expected_context=None):
    """Independently validate the final output graph and returned truth."""
    contract.validate_record(manifest, "local-hand-q2-core-output-package/v1")
    require(manifest["session_id"] == contract.SESSION_ID
            and manifest["limits"] == OUTPUT_LIMITS, "CORE_OUTPUT_AUTHORITY")
    members = manifest["members"]
    require(type(members) is list and len(members) <= OUTPUT_LIMITS["members"]
            and set(values) == {item["path"] for item in members},
            "CORE_OUTPUT_MEMBER_SET")
    totals = {case["case_id"]: 0 for case in contract.CASES}
    totals["carrier"] = 0
    seen = set()
    for item in members:
        require(item["path"] not in seen and item["role"] in MEMBER_ROLES
                and item["case_id"] in totals, "CORE_OUTPUT_MEMBER_AUTHORITY")
        seen.add(item["path"]); totals[item["case_id"]] += item["bytes"]
        expected_prefix = "carrier/" if item["case_id"] == "carrier" else (
            "cases/" + item["case_id"] + "/")
        require(item["path"].startswith(expected_prefix), "CORE_OUTPUT_MEMBER_CASE")
    require(all(totals[case["case_id"]] <= 16_777_216 for case in contract.CASES),
            "CORE_OUTPUT_CASE_BYTES")

    remote = manifest["remote_result"]
    contract.validate_record(remote, contract.REMOTE_RESULT_SCHEMA)
    require(remote["session_id"] == contract.SESSION_ID
            and remote["consumption_sha256"] == consumption_sha256
            and manifest["cases"] == remote["cases"], "CORE_REMOTE_AUTHORITY")
    statuses = _validate_case_index(remote["cases"], members)
    require((remote["state"] == "REMOTE_FINALIZED" and statuses == ["PASS"] * 3)
            or remote["state"] == "REMOTE_STOP_AND_RETAIN",
            "CORE_REMOTE_STATE")
    _validate_missing(remote["missing"])
    require(remote["state"] != "REMOTE_FINALIZED" or remote["missing"] == [],
            "CORE_REMOTE_FINAL_MISSING")
    usage = remote["usage"]
    contract.exact(usage, USAGE_FIELDS, "CORE_REMOTE_USAGE_FIELDS")
    complete = remote["state"] == "REMOTE_FINALIZED"
    for key in USAGE_FIELDS:
        if usage[key] is None:
            require(not complete and any(row["role"] == "usage/" + key for row in remote["missing"]),
                    "CORE_REMOTE_USAGE_MISSING")
        else:
            contract.integer(usage[key], 0, code="CORE_REMOTE_USAGE")
    ceilings = {"guest_elapsed_ns": GUEST_CAP_NS, "carrier_cpu_ns": 1_600_000_000_000,
        "carrier_memory_peak_bytes": 2_147_483_648, "carrier_pids_peak": 256,
        "guest_allocated_bytes": contract.LIMITS["total_guest_physical_bytes"],
        "guest_allocated_inodes": contract.LIMITS["total_guest_physical_inodes"],
        "job_units_started": 15, "controller_units_started": 6, "quota_query_units_started": 5,
        "dynamic_quota_units_started": 15, "native_children_started": 16}
    require(all(usage[key] is None or usage[key] <= limit or not complete for key, limit in ceilings.items())
            and usage["stdin_bytes_received"] in (None, stdin_bytes_received)
            and usage["output_frame_bytes"] in (None, frame_bytes), "CORE_REMOTE_USAGE_LIMIT")
    execution, package = _validate_h01_summaries(remote, members)
    if any(row["case_id"] == "carrier" for row in members) or statuses[0] == "PASS":
        _validate_carrier_bindings(values, expected_context)

    require(type(expected_context) is dict, "CORE_OUTPUT_FROZEN_CONTEXT_REQUIRED")
    frozen = expected_context["manifest"]
    hello, bind = expected_context["hello"], expected_context["bind"]
    deadlines = {clock + "_" + kind + "_ns": hello["guest_" + clock + "_origin_ns"]
                 + (bind["guest_duration_ns"] if kind == "deadline" else 0)
                 for clock in ("boottime", "monotonic") for kind in ("origin", "deadline")}
    admission = (_document_member(values, "carrier/admission.json")
                 if "carrier/admission.json" in values else None)
    installation = (_document_member(values, "carrier/installation.json")
                    if "carrier/installation.json" in values else None)
    plans = [_document_member(values, path) for fixed in contract.CASES
             if (path := "cases/" + fixed["case_id"] + "/reservation/case-plan.json") in values]
    preparations = [_document_member(values, path) for fixed in contract.CASES
                    if (path := "cases/" + fixed["case_id"] + "/reservation/preparation-result.json") in values]
    accounting = contract.validate_resource_accounting(remote["resource_accounting"],
        implementation=frozen["implementation"], locators=frozen["locators"], guest_deadlines=deadlines,
        admission=admission, plans=plans, installation=installation, preparations=preparations, complete=complete)
    require(all(row in remote["missing"] for row in accounting["missing"]), "CORE_REMOTE_RESOURCE_MISSING")
    require(usage["guest_allocated_bytes"] == accounting["observed_maxima_sum"]["bytes"]
            and usage["guest_allocated_inodes"] == accounting["observed_maxima_sum"]["inodes"],
            "CORE_REMOTE_RESOURCE_USAGE")
    require(complete or statuses != ["PASS"] * 3 or bool(remote["missing"]), "CORE_REMOTE_STOP_MISSING")

    for fixed, case_index in zip(dispatcher_contract.CASES, remote["cases"], strict=True):
        if case_index["status"] == "PASS":
            _deep_validate_pass_case(fixed, case_index, members, values, remote)
    if statuses == ["PASS"] * 3:
        require(len(members) == 82, "CORE_OUTPUT_COMPLETE_MEMBER_COUNT")
        carrier = {(item["path"], item["role"], item["mode"])
                   for item in members if item["case_id"] == "carrier"}
        require(carrier == {
            ("carrier/session.json", "session", 384),
            ("carrier/admission.json", "admission", 384),
            ("carrier/installation.json", "installation", 384),
        }, "CORE_OUTPUT_CARRIER_SET")
        for path, schema in (
            ("carrier/session.json", "local-hand-q2-core-dispatch-session/v2"),
        ):
            contract.validate_record(_document_member(values, path), schema)
        raw_truth_bound = _h01_truth_binding(remote, values)
    else:
        raw_truth_bound = (_h01_truth_binding(remote, values)
                           if statuses[0] == "PASS" else False)
        require(execution["status"] != "VERIFIED" or statuses[0] == "PASS",
                "CORE_REMOTE_H01_STOP_SUMMARY")
    return {"remote": remote, "statuses": statuses,
            "h01_raw_truth_bound": raw_truth_bound,
            "remote_result_sha256": hashlib.sha256(contract.canonical(remote)).hexdigest(),
            "members_sha256": hashlib.sha256(contract.canonical(members)).hexdigest()}


def _hello_prefix(raw, package_entry, remote_expectation):
    require(type(raw) is bytearray, "CORE_HELLO_BUFFER")
    if len(raw) < len(contract.HELLO_MAGIC) + 8:
        return None
    require(raw.startswith(contract.HELLO_MAGIC), "CORE_HELLO_MAGIC")
    size = struct.unpack(">Q", raw[len(contract.HELLO_MAGIC):len(contract.HELLO_MAGIC) + 8])[0]
    require(0 < size <= HELLO_JSON_LIMIT, "CORE_HELLO_LENGTH")
    end = len(contract.HELLO_MAGIC) + 8 + size
    require(end <= HELLO_FRAME_LIMIT, "CORE_HELLO_LIMIT")
    if len(raw) < end:
        return None
    value = contract.document(bytes(raw[len(contract.HELLO_MAGIC) + 8:end]),
                              limit=HELLO_JSON_LIMIT, newline=True)
    contract.validate_hello(value, loader_sha256=package_entry["loader_sha256"],
                            bootstrap_sha256=package_entry["bootstrap_sha256"],
                            remote_expectation=remote_expectation)
    return value, end


def _close_pipe(stream, call):
    if stream is not None:
        try:
            call(stream.close)
        except OSError:
            pass


def _stop_process(process, call, *, kill=False):
    if process is None or call(process.poll) is not None:
        return
    try:
        call(process.kill if kill else process.terminate)
    except (OSError, ProcessLookupError):
        pass


def execute_carrier_once(*, argv, environment, cwd, origins, marker,
                         package_basename, package_raw, package_entry, remote_expectation,
                         popen_factory=subprocess.Popen,
                         selector_factory=selectors.DefaultSelector,
                         clock_gettime_ns=time.clock_gettime_ns):
    """Issue exactly one fixed execve and exchange one HELLO/BIND/package stream.

    All child descriptors are nonblocking and every select/write/read is bounded
    by the original dual host window.  The function never reconnects or invokes
    the factory a second time.
    """
    require(marker.get("object_created") is True and marker.get("record_complete") is True,
            "CORE_TRANSPORT_MARKER")
    require(type(package_raw) is bytes and 0 < len(package_raw) <= contract.LIMITS["package_bytes"],
            "CORE_TRANSPORT_PACKAGE")
    require(type(argv) is list and argv_digest(argv) == package_entry["carrier_argv_sha256"],
            "CORE_TRANSPORT_ARGV")
    encoded_argv_environment_size(argv, environment)
    require(origins["host_boottime_deadline_ns"]
            == origins["host_boottime_origin_ns"] + HOST_WINDOW_NS
            and origins["host_monotonic_deadline_ns"]
            == origins["host_monotonic_origin_ns"] + HOST_WINDOW_NS,
            "CORE_TRANSPORT_HOST_WINDOW")
    consumption_sha256 = marker["sha256"]
    deadline = capture_contract.Deadline(origins, clock_gettime_ns)
    call = deadline.call
    result = {
        "transport": {"execve_succeeded": False, "hello_valid": False,
                      "bind_written": False, "package_written": False,
                      "stdin_bytes_written": 0, "stdin_eof": False},
        "wait": {"status": None, "stdout_eof": False, "stderr_eof": False,
                 "host_deadline_met": False},
        "stdout": b"", "stderr": b"", "hello": None, "hello_frame_bytes": 0,
        "bind": None, "bind_frame_bytes": 0, "errors": [],
    }
    process = None
    def started(value):
        nonlocal process
        process = value
        result["transport"]["execve_succeeded"] = True
    try:
        process = call(popen_factory,
            argv, executable=argv[0], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=cwd, env=environment, shell=False,
            close_fds=True, bufsize=0, returned=started,
        )
        result["transport"]["execve_succeeded"] = True
    except (OSError, ValueError, capture_contract.CaptureError) as error:
        result["errors"].append(_missing(
            "CORE_EXECVE_LATE" if process is not None else "CORE_EXECVE_FAILED", "transport",
                                                 {"errno": getattr(error, "errno", None),
                                                  "type": type(error).__name__}))
        return result

    selector = None
    stdout = bytearray(); stderr = bytearray()
    hello_end = None; bind_frame = b""; input_raw = None; input_offset = 0
    stdin_open = True; terminated = False
    streams = (("stdout", process.stdout), ("stderr", process.stderr))
    try:
        selector = call(selector_factory)
        require(process.stdin is not None and all(stream is not None for _, stream in streams),
                "CORE_TRANSPORT_PIPES")
        for role, stream in streams:
            call(os.set_blocking, stream.fileno(), False)
            call(selector.register, stream.fileno(), selectors.EVENT_READ, role)
        call(os.set_blocking, process.stdin.fileno(), False)

        while True:
            boot_now, mono_now = deadline.check()
            stop_remaining = min(
                origins["host_boottime_deadline_ns"] - LOCAL_FINAL_RESERVE_NS - boot_now,
                origins["host_monotonic_deadline_ns"] - LOCAL_FINAL_RESERVE_NS - mono_now,
            )
            if stop_remaining <= 0:
                result["errors"].append(_missing(
                    "CORE_HOST_TRANSPORT_DEADLINE", "transport",
                    {"boot_now": boot_now, "mono_now": mono_now}))
                if stdin_open:
                    _close_pipe(process.stdin, call); stdin_open = False
                _stop_process(process, call); terminated = True
                break

            if (result["wait"]["stdout_eof"] and result["wait"]["stderr_eof"]
                    and call(process.poll) is not None):
                break
            timeout = min(0.1, stop_remaining / 1_000_000_000)
            events = call(selector.select, timeout)
            if not events and call(process.poll) is not None:
                # A final nonblocking selector turn observes pipe EOF.
                events = call(selector.select, 0)
            for key, mask in events:
                role = key.data
                if role == "stdin":
                    if input_raw is None:
                        continue
                    def input_written(written):
                        nonlocal input_offset
                        if written > 0:
                            input_offset += written
                            result["transport"]["stdin_bytes_written"] = input_offset
                            result["transport"]["bind_written"] = input_offset >= len(bind_frame)
                            result["transport"]["package_written"] = input_offset == len(input_raw)
                    try:
                        written = call(os.write, key.fd, input_raw[input_offset:input_offset + 65_536],
                                       returned=input_written)
                    except BlockingIOError:
                        continue
                    except BrokenPipeError:
                        written = 0
                        result["errors"].append(_missing(
                            "CORE_STDIN_BROKEN_PIPE", "transport", {"offset": input_offset}))
                    if written <= 0:
                        try:
                            call(selector.unregister, key.fd)
                        except (KeyError, ValueError):
                            pass
                        _close_pipe(process.stdin, call); stdin_open = False
                        continue
                    if input_offset == len(input_raw):
                        call(selector.unregister, key.fd)
                        _close_pipe(process.stdin, call); stdin_open = False
                        result["transport"]["stdin_eof"] = True
                    continue

                target = stdout if role == "stdout" else stderr
                role_limit = ((HELLO_FRAME_LIMIT + OUTPUT_FRAME_LIMIT)
                              if role == "stdout" else STDERR_LIMIT)
                available = min(role_limit - len(target),
                                CARRIER_OUTPUT_LIMIT - len(stdout) - len(stderr),
                                STREAM_CAPTURE_LIMIT - len(stdout) - len(stderr))
                try:
                    chunk = call(os.read, key.fd, min(65_536, max(1, available + 1)))
                except BlockingIOError:
                    continue
                if not chunk:
                    call(selector.unregister, key.fd)
                    _close_pipe(process.stdout if role == "stdout" else process.stderr, call)
                    result["wait"][role + "_eof"] = True
                    continue
                if available < 0 or len(chunk) > available:
                    result["errors"].append(_missing(
                        "CORE_CARRIER_OUTPUT_LIMIT", role,
                        {"stdout": len(stdout), "stderr": len(stderr),
                         "additional": len(chunk)}))
                    if stdin_open:
                        try:
                            call(selector.unregister, process.stdin.fileno())
                        except (KeyError, ValueError):
                            pass
                        _close_pipe(process.stdin, call); stdin_open = False
                    _stop_process(process, call); terminated = True
                    break
                target.extend(chunk)

                if role == "stdout" and hello_end is None:
                    try:
                        parsed = _hello_prefix(stdout, package_entry, remote_expectation)
                    except (contract.ContractError, ValueError) as error:
                        result["errors"].append(_missing(
                            "CORE_HELLO_INVALID", "transport", {"reason": str(error)[:96]}))
                        if stdin_open:
                            _close_pipe(process.stdin, call); stdin_open = False
                        if not terminated:
                            _stop_process(process, call); terminated = True
                        continue
                    if parsed is not None:
                        hello, hello_end = parsed
                        require(len(stdout) == hello_end, "CORE_HELLO_EARLY_OUTPUT")
                        result["hello"] = hello
                        result["hello_frame_bytes"] = hello_end
                        result["transport"]["hello_valid"] = True
                        boot_bind, mono_bind = deadline.check()
                        bind = build_bind(
                            hello, consumption_sha256, package_basename, package_raw, origins,
                            package_entry=package_entry, boot_bind_ns=boot_bind,
                            mono_bind_ns=mono_bind, remote_expectation=remote_expectation)
                        bind_frame = frame(contract.BIND_MAGIC, bind,
                                           json_limit=BIND_JSON_LIMIT)
                        require(len(bind_frame) <= BIND_FRAME_LIMIT, "CORE_BIND_FRAME_LIMIT")
                        input_raw = bind_frame + package_raw
                        require(len(input_raw) <= contract.LIMITS["carrier_input_bytes"],
                                "CORE_CARRIER_INPUT_LIMIT")
                        result["bind"] = bind; result["bind_frame_bytes"] = len(bind_frame)
                        call(selector.register, process.stdin.fileno(), selectors.EVENT_WRITE, "stdin")
                elif role == "stdout" and not result["transport"]["stdin_eof"]:
                    # Output before the sole input stream reaches real EOF is
                    # outside the approved protocol and cannot be accepted.
                    require(len(stdout) == hello_end, "CORE_OUTPUT_BEFORE_STDIN_EOF")
            if terminated:
                break

        if stdin_open:
            try:
                call(selector.unregister, process.stdin.fileno())
            except (KeyError, ValueError):
                pass
            _close_pipe(process.stdin, call); stdin_open = False
        if terminated and call(process.poll) is None:
            try:
                call(process.wait, timeout=0.25)
            except (subprocess.TimeoutExpired, TimeoutError):
                _stop_process(process, call, kill=True)
                try:
                    call(process.wait, timeout=0.25)
                except (subprocess.TimeoutExpired, TimeoutError):
                    pass
        status = call(process.poll)
        result["wait"]["status"] = status
        final_boot, final_mono = deadline.check()
        result["wait"]["host_deadline_met"] = (
            status is not None and final_boot < origins["host_boottime_deadline_ns"]
            and final_mono < origins["host_monotonic_deadline_ns"])
    except (contract.ContractError, OSError, ValueError, capture_contract.CaptureError) as error:
        result["errors"].append(_missing(
            "CORE_TRANSPORT_FAILED", "transport", {"reason": str(error)[:96]}))
        if not deadline.failed:
            try:
                if stdin_open:
                    _close_pipe(process.stdin, call); stdin_open = False
                _stop_process(process, call)
                try:
                    call(process.wait, timeout=0.25)
                except (subprocess.TimeoutExpired, TimeoutError):
                    _stop_process(process, call, kill=True)
                    try:
                        call(process.wait, timeout=0.25)
                    except (subprocess.TimeoutExpired, TimeoutError):
                        pass
                result["wait"]["status"] = call(process.poll)
            except capture_contract.CaptureError:
                # A late syscall does not create a 905-second cleanup window.
                result["wait"]["host_deadline_met"] = False
    finally:
        if not deadline.failed:
            try:
                if selector is not None:
                    call(selector.close)
                for _, stream in streams:
                    _close_pipe(stream, call)
            except (OSError, ValueError, capture_contract.CaptureError):
                result["wait"]["host_deadline_met"] = False
        result["stdout"] = bytes(stdout)
        result["stderr"] = bytes(stderr)
        result["errors"] = sorted(
            {tuple(sorted(item.items())): item for item in result["errors"]}.values(),
            key=lambda item: (item["code"].encode("ascii"), item["role"].encode("ascii"),
                              item["detail_sha256"].encode("ascii")))
    return result


def _capture_item_from_marker(marker):
    return {key: marker[key] for key in (
        "basename", "bytes", "allocated_bytes", "sha256", "dev", "ino", "mode", "nlink",
    )}


def _truth_reference(members, role, path):
    item = next((item for item in members
                 if item["role"] == role and item["path"] == path), None)
    require(item is not None, "CORE_LOCAL_TRUTH_MEMBER")
    return _plain_member(item)


def _truth_summaries(semantic, manifest, *, frame_sha256,
                     capture_manifest_sha256):
    if semantic is None:
        return ({"status": "UNKNOWN", "evidence_sha256": None},
                {"status": "UNKNOWN", "evidence_sha256": None})
    remote = semantic["remote"]
    h01_case = remote["cases"][0]
    members = manifest["members"]
    if h01_case["status"] == "PASS" and semantic["h01_raw_truth_bound"]:
        execution_members = [
            _truth_reference(members, "preparation-result",
                "cases/c01-h01-normal/reservation/preparation-result.json"),
            _truth_reference(members, "observer-config",
                "cases/c01-h01-normal/business/observer.json"),
            _truth_reference(members, "phase-receipt",
                "cases/c01-h01-normal/reservation/phase-business-receipt.json"),
            _truth_reference(members, "phase-result",
                "cases/c01-h01-normal/launcher_output/phase-business.json"),
            _truth_reference(members, "launcher-reservation",
                "cases/c01-h01-normal/launcher_output/reservation.json"),
            _truth_reference(members, "gateway",
                "cases/c01-h01-normal/launcher_output/gateway.json"),
            _truth_reference(members, "launcher-result",
                "cases/c01-h01-normal/launcher_output/result.json"),
            _truth_reference(members, "wait",
                "cases/c01-h01-normal/launcher_output/capture.json"),
            _truth_reference(members, "verdict",
                "cases/c01-h01-normal/reservation/case-verdict.json"),
        ]
        result_ref = remote["h01_result_package"]["result_member"]
        seal = remote["h01_business_execution"]["evidence_sha256"]
        evidence_rows = [item for item in members
                         if item["case_id"] == "c01-h01-normal"
                         and item["role"] in {
                             "business-evidence-archive", "business-evidence-manifest",
                             "business-evidence-seal",
                         }]
        require(len(evidence_rows) == 3
                and any(item["role"] == "business-evidence-seal"
                        and item["sha256"] == seal for item in evidence_rows),
                "CORE_LOCAL_TRUTH_EVIDENCE")
        collection_members = [result_ref] + [_plain_member(item) for item in evidence_rows] + [
            _truth_reference(members, "gateway",
                "cases/c01-h01-normal/launcher_output/gateway.json"),
            _truth_reference(members, "wait",
                "cases/c01-h01-normal/launcher_output/capture.json"),
            _truth_reference(members, "verdict",
                "cases/c01-h01-normal/reservation/case-verdict.json"),
        ]
        statuses = (("real_task_execution", "YES", execution_members),
                    ("result_evidence_collection", "YES", collection_members))
    elif (semantic["statuses"] == ["NOT_RUN", "NOT_RUN", "NOT_RUN"]
          and remote["h01_business_execution"]["status"] == "NOT_RUN"
          and remote["h01_result_package"]["status"] == "NOT_RUN"):
        statuses = (("real_task_execution", "NO", []),
                    ("result_evidence_collection", "NO", []))
    else:
        return ({"status": "UNKNOWN", "evidence_sha256": None},
                {"status": "UNKNOWN", "evidence_sha256": None})
    results = []
    for kind, status, rows in statuses:
        rows = sorted(rows, key=lambda item: (item["role"].encode("ascii"),
                                              item["path"].encode("ascii")))
        evidence = {
            "schema": contract.TRUTH_EVIDENCE_SCHEMA, "kind": kind, "status": status,
            "frame_sha256": frame_sha256,
            "remote_result_sha256": semantic["remote_result_sha256"],
            "capture_manifest_sha256": capture_manifest_sha256,
            "h01_case": h01_case,
            "h01_business_execution": remote["h01_business_execution"],
            "h01_result_package": remote["h01_result_package"], "members": rows,
        }
        results.append({"status": status,
                        "evidence_sha256": hashlib.sha256(
                            contract.canonical(evidence)).hexdigest()})
    return tuple(results)


def _validate_live_capacity(value, expected_context, capture):
    prior_api = _helper("q2_core_delivery_package")._approved_module().prior_attempt
    approved = contract.document(expected_context['approved_inputs_raw'], limit=1_048_576, newline=True)
    manifest, binding = expected_context['manifest'], expected_context['binding']
    require(value['local_management_binding_sha256']
            == manifest['entry']['local_management_binding_sha256']
            and contract.canonical(binding['anchor']) == contract.canonical(capture.anchor)
            and contract.canonical(binding['writer']) == contract.canonical(capture.writer),
            'CORE_FINAL_CAPACITY_BINDING')
    return prior_api.validate_capacity_condition(value, binding=binding,
        prior=approved['reconciliation']['prior_core_attempts'],
        diagnostic=approved['reconciliation']['prior_diagnostic_capture'],
        journal=approved['reconciliation']['journal_transition'],
        implementation=manifest['implementation'], origins=capture.deadline.origins)


def finalize_carrier(directory_fd, *, marker, exchange, capture, expected_context,
                     host_capacity_condition):
    """Create the bounded local capture graph and the sole terminal receipt."""
    require(marker.get("record_complete") is True, "CORE_FINAL_MARKER")
    require(capture.directory_fd == directory_fd and not capture.failed
            and capture.objects.get("marker", {}).get("complete") is True
            and capture.objects["marker"].get("sha256") == marker["sha256"],
            "CORE_FINAL_LIVE_CAPTURE")
    require(type(exchange) is dict and type(exchange.get("stdout")) is bytes
            and type(exchange.get("stderr")) is bytes, "CORE_FINAL_EXCHANGE")
    _validate_live_capacity(host_capacity_condition, expected_context, capture)
    capacity_raw = contract.canonical(host_capacity_condition)
    capture.deadline.call(output_names_absent, directory_fd)
    stdout_raw = exchange["stdout"]; stderr_raw = exchange["stderr"]
    require(len(stderr_raw) <= STDERR_LIMIT
            and len(stdout_raw) + len(stderr_raw) <= STREAM_CAPTURE_LIMIT,
            "CORE_FINAL_STREAM_LIMIT")
    files = [_capture_item_from_marker(marker)]
    stdout_item = create_capture_file(
        directory_fd, contract.OUTPUT_BASENAMES["stdout_basename"], stdout_raw,
        limit=STREAM_CAPTURE_LIMIT, capture=capture)
    stderr_item = create_capture_file(
        directory_fd, contract.OUTPUT_BASENAMES["stderr_basename"], stderr_raw,
        limit=STDERR_LIMIT, capture=capture)
    files.extend((stdout_item, stderr_item))

    errors = list(exchange.get("errors", []))
    output_tail = b""
    if (exchange["transport"]["hello_valid"]
            and 0 < exchange["hello_frame_bytes"] <= len(stdout_raw)):
        output_tail = stdout_raw[exchange["hello_frame_bytes"]:]
    manifest = None; values = None; semantic = None; remote_item = None
    manifest_sha256 = members_sha256 = None
    output_present = bool(output_tail)
    if output_present and exchange["wait"]["stdout_eof"]:
        try:
            manifest, values = parse_output(output_tail)
            semantic = validate_output_semantics(
                manifest, values, consumption_sha256=marker["sha256"],
                stdin_bytes_received=exchange["transport"]["stdin_bytes_written"],
                frame_bytes=len(output_tail), expected_context=expected_context)
            errors.extend(semantic["remote"]["missing"])
            manifest_sha256 = hashlib.sha256(
                contract.canonical(manifest, newline=True)).hexdigest()
            members_sha256 = semantic["members_sha256"]
            remote_raw = contract.canonical(semantic["remote"])
            require(len(remote_raw) <= REMOTE_RESULT_LIMIT, "CORE_REMOTE_RESULT_LIMIT")
            remote_item = create_capture_file(
                directory_fd, contract.OUTPUT_BASENAMES["remote_result_basename"],
                remote_raw, limit=REMOTE_RESULT_LIMIT, capture=capture)
            files.append(remote_item)
        except (contract.ContractError, dispatcher_contract.DispatchError,
                KeyError, TypeError, ValueError) as error:
            manifest = values = semantic = None
            errors.append(_missing("CORE_OUTPUT_INVALID", "output-package",
                                   {"reason": str(error)[:96]}))
    elif output_present:
        errors.append(_missing("CORE_OUTPUT_WITHOUT_EOF", "output-package",
                               {"bytes": len(output_tail)}))
    else:
        errors.append(_missing("CORE_OUTPUT_MISSING", "output-package", {"bytes": 0}))

    files.sort(key=lambda item: item["basename"].encode("ascii"))
    capture.sample()
    current_allocation = {capture_contract.BASENAMES[role]: record["allocated_bytes"]
                          for role, record in capture.objects.items()}
    for item in files:
        item["allocated_bytes"] = current_allocation[item["basename"]]
    logical_bytes = sum(item["bytes"] for item in files)
    allocated_bytes = sum(item["allocated_bytes"] for item in files)
    require(allocated_bytes <= CAPTURE_LIMIT and len(files) <= CAPTURE_INODE_LIMIT,
            "CORE_CAPTURE_BUDGET")
    errors = sorted(
        {tuple(sorted(item.items())): item for item in errors}.values(),
        key=lambda item: (item["code"].encode("ascii"), item["role"].encode("ascii"),
                          item["detail_sha256"].encode("ascii")))
    capture_document = {
        "schema": "local-hand-q2-core-capture-manifest/v1",
        "session_id": contract.SESSION_ID, "consumption_sha256": marker["sha256"],
        "stdout": {"basename": stdout_item["basename"], "bytes": stdout_item["bytes"],
                   "sha256": stdout_item["sha256"],
                   "eof": exchange["wait"]["stdout_eof"]},
        "stderr": {"basename": stderr_item["basename"], "bytes": stderr_item["bytes"],
                   "sha256": stderr_item["sha256"],
                   "eof": exchange["wait"]["stderr_eof"]},
        "output_package": {
            "present": output_present, "frame_bytes": len(output_tail) if output_present else 0,
            "manifest_sha256": manifest_sha256, "members_sha256": members_sha256,
            "valid": semantic is not None,
        },
        "wait": {"status": exchange["wait"]["status"],
                 "host_deadline_met": exchange["wait"]["host_deadline_met"]},
        "files": files, "logical_bytes": logical_bytes,
        "allocated_bytes": allocated_bytes, "inodes": len(files),
        "fsync_complete": True, "reread_equal": True, "missing": errors,
    }
    contract.validate_record(capture_document, "local-hand-q2-core-capture-manifest/v1")
    _validate_missing(capture_document["missing"], "CORE_CAPTURE_MISSING")
    capture_raw = contract.canonical(capture_document, newline=True, limit=262_144)
    capture_item = create_capture_file(
        directory_fd, contract.OUTPUT_BASENAMES["capture_manifest_basename"],
        capture_raw, limit=262_144, capture=capture)
    capture_sha256 = capture_item["sha256"]

    frame_sha256 = hashlib.sha256(output_tail).hexdigest() if semantic is not None else None
    execution_truth, collection_truth = _truth_summaries(
        semantic, manifest, frame_sha256=frame_sha256,
        capture_manifest_sha256=capture_sha256)
    transport = dict(exchange["transport"])
    wait = dict(exchange["wait"])
    complete = (
        semantic is not None and semantic["remote"]["state"] == "REMOTE_FINALIZED"
        and semantic["statuses"] == ["PASS"] * 3
        and all(transport[key] is True for key in (
            "execve_succeeded", "hello_valid", "bind_written", "package_written", "stdin_eof"))
        and transport["stdin_bytes_written"] > 0 and wait["status"] == 0
        and wait["stdout_eof"] is True and wait["stderr_eof"] is True
        and wait["host_deadline_met"] is True and not errors
        and execution_truth["status"] == collection_truth["status"] == "YES")
    receipt = {
        "schema": "local-hand-q2-core-local-acceptance-receipt/v1",
        "scope": contract.SCOPE, "session_id": contract.SESSION_ID,
        "consumption": {key: marker[key] for key in (
            "object_created", "record_complete", "basename", "bytes", "sha256")},
        "transport": transport,
        "remote_result": {
            "present": remote_item is not None,
            "sha256": None if semantic is None else semantic["remote_result_sha256"],
            "frame_sha256": frame_sha256,
        },
        "wait": wait,
        "capture": {"bytes": allocated_bytes, "inodes": len(files),
                    "manifest_sha256": capture_sha256,
                    "fsync_complete": True, "reread_equal": True},
        "real_task_execution": execution_truth,
        "result_evidence_collection": collection_truth,
        "state": "COMPLETE" if complete else "STOP_AND_RETAIN",
        "missing": errors,
    }
    contract.validate_record(receipt, "local-hand-q2-core-local-acceptance-receipt/v1")
    _validate_missing(receipt["missing"], "CORE_RECEIPT_MISSING")
    receipt_raw = contract.canonical(receipt, newline=True, limit=65_536)
    receipt_item = create_capture_file(
        directory_fd, contract.OUTPUT_BASENAMES["local_receipt_basename"],
        receipt_raw, limit=65_536, capture=capture)
    accounting = capture.finish()
    _validate_live_capacity(host_capacity_condition, expected_context, capture)
    require(contract.canonical(host_capacity_condition) == capacity_raw, 'CORE_FINAL_CAPACITY_CHANGED')
    capture.deadline.check()
    return {"receipt": receipt, "receipt_item": receipt_item,
            "capture_manifest": capture_document, "capture_item": capture_item,
            "semantic": semantic, "files": files,
            "total_allocated_bytes": capture.allocated,
            "total_inodes": len(capture.objects), "capture_accounting": accounting,
            "host_capacity_condition": host_capacity_condition}


def read_prior_originals(directory_fd, anchor, approved, deadline):
    """Rebind embedded prior bytes to this window's same held private anchor."""
    package_format = _helper("q2_core_delivery_package")
    prior_api = package_format._approved_module().prior_attempt
    seen = set()
    files = prior_api.read_all_files(directory_fd, anchor, deadline.call, _seen=seen)
    diagnostic_files = prior_api.read_diagnostic_files(directory_fd, anchor, deadline.call, _seen=seen)
    prior = prior_api.build_all(files)
    require(contract.canonical(prior) == contract.canonical(
        approved['reconciliation']['prior_core_attempts']), "CORE_DELIVERY_PRIOR_SOURCE_BINDING")
    require(contract.canonical(prior_api.build_diagnostic(diagnostic_files)) == contract.canonical(
        approved['reconciliation']['prior_diagnostic_capture']), 'CORE_DELIVERY_DIAGNOSTIC_SOURCE_BINDING')
    deadline.check()
    journal_files = prior_api.read_journal_files(directory_fd,anchor,deadline.call,_seen=seen)
    previous = prior_api.read_previous_journal_files(directory_fd,anchor,deadline.call,_seen=seen)
    transition = approved['reconciliation']['journal_transition']
    require(contract.canonical(prior_api.build_previous_maintenance(previous)) ==
        contract.canonical(transition['previous_maintenance']), 'CORE_DELIVERY_PREVIOUS_MAINTENANCE')
    require(transition['originals'] == [dict(basename=name,bytes=len(raw),sha256=contract.sha256(raw))
        for name,raw in sorted(journal_files.items())], 'CORE_DELIVERY_JOURNAL_SOURCE_BINDING')
    prior_api.read_capacity_diagnostic(directory_fd,anchor,deadline.call,_seen=seen)
    return files, diagnostic_files, journal_files


def verify_prior_originals(directory_fd, binding, approved, deadline, *, implementation):
    """Same pre-marker source binding followed by the sole capacity observation."""
    _,_,journal_files=read_prior_originals(directory_fd, binding['anchor'], approved, deadline)
    prior_api = _helper("q2_core_delivery_package")._approved_module().prior_attempt
    return prior_api.observe_capture_condition(directory_fd, binding=binding,
        prior=approved['reconciliation']['prior_core_attempts'], implementation=implementation,
        diagnostic=approved['reconciliation']['prior_diagnostic_capture'],
        journal=approved['reconciliation']['journal_transition'],
        deadline=deadline, journal_files=journal_files, writer_observer=capture_contract.observe_writer)


def deliver_once(directory_fd, *, binding, package_basename, package_raw,
                 loader_raw, bootstrap_raw, wrapper_raw,
                 origins=None,
                 popen_factory=subprocess.Popen,
                 selector_factory=selectors.DefaultSelector,
                 clock_gettime_ns=time.clock_gettime_ns):
    """Static gate, consume, issue once, then finalize on the same held anchor."""
    package_format = _helper("q2_core_delivery_package")
    manifest, members = package_format.parse_package(package_raw)
    entry = manifest["entry"]
    require(members[entry["loader_path"]] == loader_raw
            and members[entry["bootstrap_path"]] == bootstrap_raw,
            "CORE_DELIVERY_ENTRY_BYTES")
    field_release_gate(manifest, members)
    contract.validate_package_basename(package_basename, "CORE_DELIVERY_PACKAGE_BASENAME")
    require(package_basename == contract.SESSION_ID + '.lhfp', 'CORE_DELIVERY_PACKAGE_BASENAME')
    tokens = remote_tokens(loader_raw, bootstrap_raw)
    argv = wrapper_argv(binding["wrapper"]["path"], wrapper_raw, tokens)
    environment = controlled_environment()
    encoded_argv_environment_size(argv, environment)
    require("anchor" in binding and "writer" in binding, "CORE_LOCAL_WRITER_BINDING_UNBOUND")
    contract.validate_local_writer(binding["writer"])
    require(contract.canonical(entry["writer"]) == contract.canonical(binding["writer"]),
            "CORE_DELIVERY_WRITER_BINDING")
    # The window starts before current local inspection/package freeze. Never
    # refresh it on entry; caller must pass that same original window.
    require(origins is not None, "CORE_DELIVERY_ORIGIN_REQUIRED")
    deadline = capture_contract.Deadline(origins, clock_gettime_ns)
    deadline.check()
    approved = contract.document(members[contract.APPROVED_INPUTS_PATH], limit=1_048_576, newline=True)
    require(approved["policy_basis"]["remote_expectation"] == binding["remote_expectation"],
            "CORE_DELIVERY_POLICY_LOCAL_BINDING")
    qualification = requalify_management_anchor(
        directory_fd, binding, tokens=tokens, argv=argv, environment=environment, deadline=deadline)
    try:
        require(qualification["wrapper_raw"] == wrapper_raw
                and qualification["binding_sha256"]
                == entry["local_management_binding_sha256"]
                and argv_digest(argv) == entry["carrier_argv_sha256"],
                "CORE_DELIVERY_STATIC_BINDING")
        capacity = verify_prior_originals(directory_fd, binding, approved, deadline,
                                         implementation=manifest['implementation'])
        capacity_raw = contract.canonical(capacity)
        deadline.call(marker_absent, directory_fd)
        deadline.call(output_names_absent, directory_fd)
        capture = capture_contract.LiveCapture(
            directory_fd, anchor=binding["anchor"], writer=binding["writer"], origins=origins,
            clock_gettime_ns=clock_gettime_ns)
        raw_manifest = contract.canonical(manifest, newline=True)
        package_record = {
            "basename": package_basename, "bytes": len(package_raw),
            "sha256": hashlib.sha256(package_raw).hexdigest(),
            "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        }
        marker_record = consumption_record(
            implementation=manifest["implementation"], amendment=manifest["amendment"],
            package=package_record, approved_inputs_sha256=manifest["approved_inputs"]["sha256"],
            local_management_binding_sha256=entry["local_management_binding_sha256"],
            writer=binding["writer"],
            carrier_argv_sha256=entry["carrier_argv_sha256"], origins=origins)
        marker = create_consumption_marker(directory_fd, marker_record, capture=capture)
        # qualification.fds and directory_fd are still held here.  Popen is the
        # sole carrier request and returns only after execve success/failure is
        # known; no pathname-selected replacement anchor can be substituted.
        exchange = execute_carrier_once(
            argv=argv, environment=environment, cwd=binding["cwd"]["path"],
            origins=origins, marker=marker, package_basename=package_basename,
            package_raw=package_raw, package_entry=entry,
            remote_expectation=binding["remote_expectation"],
            popen_factory=popen_factory, selector_factory=selector_factory,
            clock_gettime_ns=clock_gettime_ns)
    finally:
        close_held_management(qualification)
    expected_context = {"manifest": manifest, "approved_inputs_raw": members[contract.APPROVED_INPUTS_PATH],
                        "binding": binding, "hello": exchange.get("hello"), "bind": exchange.get("bind"),
                        "marker": marker}
    finalized = finalize_carrier(directory_fd, marker=marker, exchange=exchange, capture=capture,
                                 expected_context=expected_context, host_capacity_condition=capacity)
    _validate_live_capacity(finalized['host_capacity_condition'], expected_context, capture)
    require(contract.canonical(finalized['host_capacity_condition']) == capacity_raw,
            'CORE_DELIVERY_CAPACITY_CHANGED')
    capture.close_handles()
    capture.deadline.check()
    return {"marker": marker, "exchange": exchange, **finalized}
