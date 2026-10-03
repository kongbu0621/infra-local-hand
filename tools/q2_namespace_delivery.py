"""Offline contract for the approved Q2 namespace-fixture delivery.

This module is deliberately incapable of performing the delivery.  It has no
filesystem, process, SSH, socket, cgroup, or guest I/O.  It validates the
private F0 plan and sealed manifest supplied by a caller, constructs the one
reviewable remote command, validates only the exact unissued state, and checks
bounded canonical evidence envelopes.  It deliberately refuses to manufacture
durability acknowledgements or advance any field state.

Passing these functions proves only internal consistency of supplied bytes.
It does not prove that a target, watchdog, cgroup, budget, clock, durable
capture, or fsync exists.  Those facts remain F3 evidence.  In particular this
module never implements, builds, uploads, installs, or replaces watchdog W.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import PurePosixPath
import re
import shlex


RULE = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
BASELINE = "ad5abaee642cba02d997149badf75a08c219a35c"
CLOSURE = "f5d60351c95c0276a95c7843215e02b0a69fdc3f"
OWNER_DECISION = "LH-Q2-NAMESPACE-FIXTURE-DELIVERY-CLOSURE-20261003-01"
SCOPE = "LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1"
PHASES = ("F0", "F1", "F2", "F3", "F4")
CASE_IDS = tuple(f"N{number:02d}" for number in range(1, 13))

PLAN_SCHEMA = "local-hand-q2-namespace-fixture-delivery-plan/v1"
MANIFEST_SCHEMA = "local-hand-q2-namespace-fixture-delivery-manifest/v1"
WATCHDOG_SCHEMA = "local-hand-q2-namespace-fixture-watchdog/v1"
BRIDGE_SCHEMA = "local-hand-q2-namespace-fixture-bridge/v1"
STATE_SCHEMA = "local-hand-q2-namespace-fixture-delivery-state/v1"
FRAME_SCHEMA = "local-hand-q2-namespace-fixture-frame/v1"
CAPTURE_ACK_SCHEMA = "local-hand-q2-namespace-fixture-capture-ack/v1"
HANDOFF_SCHEMA = "local-hand-q2-namespace-fixture-cleanup-handoff/v1"
CLEANUP_FINAL_SCHEMA = "local-hand-q2-namespace-fixture-cleanup-final/v1"
SUCCESS_RECEIPT_SCHEMA = "local-hand-q2-namespace-fixture-success-receipt/v1"
REFERENCE_REPORT_SCHEMA = "local-hand-q2-namespace-reference-report/v1"
REFERENCE_CONTEXT_SCHEMA = "local-hand-q2-namespace-reference-context/v1"
REFERENCE_FRAME_SCHEMA = "local-hand-q2-namespace-reference-frame/v1"
REFERENCE_SYNTHETIC_SCHEMA = "local-hand-q2-namespace-synthetic-harness/v1"
REFERENCE_BOOTSTRAP_READY_SCHEMA = "local-hand-q2-namespace-bootstrap-ready/v1"
REFERENCE_G_GO_SCHEMA = "local-hand-q2-namespace-g-go/v1"
BRIDGE_BUILD_SCHEMA = "local-hand-q2-namespace-fixture-bridge-build/v1"
BRIDGE_RELATION_SCHEMA = "local-hand-q2-namespace-fixture-bridge-relation/v1"

ZERO_DIGEST = "0" * 64
MIB = 1024 * 1024
MAX_BOOTSTRAP_SOURCE = 32 * 1024
MAX_REMOTE_COMMAND = 48 * 1024
MAX_BUNDLE_BYTES = MIB
MAX_BUNDLE_FILES = 8
MAX_H_BYTES = 16 * 1024
MAX_CLEANUP_FINAL_BYTES = 32 * 1024
SUCCESS_RECEIPT_SIZE = 224
MAX_SUCCESS_RECEIPT_BYTES = SUCCESS_RECEIPT_SIZE
SUCCESS_RECEIPT_MAGIC = b"Q2NSR001"
SUCCESS_RECEIPT_VERSION = 1
SUCCESS_RECEIPT_HASH_OFFSET = 192
MAX_FRAME_PAYLOAD_BYTES = 1024 * 1024
MAX_CASES = 12
MAX_ACTIONS = 37
MAX_SUPPLEMENTARY_GROUPS = 32
MAX_CARRIER_REQUESTS = 1
MAX_BATCH_RELEASES = 1
MAX_NATIVE_BATCHES = 1
MAX_SELF_WRITES_OLD_CARRIER = 38
MAX_SELF_WRITES_GUARDIAN = 38
MAX_SELF_WRITES_TOTAL = 76
REQUIRED_BUNDLE_ROLES = (
    "collector", "supervisor", "bridge", "schema", "manifest", "launcher",
)
REQUIRED_BRIDGE_EXPORTS = (
    "fixture_clone_into_cgroup", "fixture_setup", "fixture_arm",
    "fixture_cleanup_tail",
)

SUCCESS_RECEIPT_LAYOUT = {
    "bytes": SUCCESS_RECEIPT_SIZE,
    "magic_ascii": SUCCESS_RECEIPT_MAGIC.decode("ascii"),
    "version": SUCCESS_RECEIPT_VERSION,
    "byte_order": "little",
    "version_offset": 8,
    "clock_offsets": {
        "process_cpu_ns": 16,
        "boottime_ns": 24,
        "monotonic_ns": 32,
        "realtime_ns": 40,
    },
    "counter_offset": 48,
    "digest_offsets": {
        "previous_digest": 56,
        "handoff_sha256": 88,
        "cleanup_final_sha256": 120,
        "capture_head_sha256": 152,
    },
    "reserved_offset": 184,
    "reserved_bytes": 8,
    "sha256_offset": SUCCESS_RECEIPT_HASH_OFFSET,
    "sha256_input_bytes": SUCCESS_RECEIPT_HASH_OFFSET,
    "sha256_bytes": 32,
    "single_raw_nonblocking_write": True,
}

REFERENCE_FRAME_PLAN = (
    {"counter": 1, "kind": "SETUP_R", "sender": "G", "receiver": "R", "rights": []},
    {"counter": 2, "kind": "SOURCE_R", "sender": "R", "receiver": "G",
        "rights": ["pid", "mnt"]},
    {"counter": 3, "kind": "SETUP_O", "sender": "G", "receiver": "O", "rights": []},
    {"counter": 4, "kind": "SOURCE_O", "sender": "O", "receiver": "G",
        "rights": ["pid", "mnt"]},
    {"counter": 5, "kind": "START_CHALLENGE", "sender": "G", "receiver": "R",
        "rights": []},
    {"counter": 6, "kind": "CHALLENGE_A", "sender": "R", "receiver": "O",
        "rights": ["pid", "mnt"]},
    {"counter": 7, "kind": "RESPONSE_A", "sender": "O", "receiver": "R",
        "rights": ["pid", "mnt"]},
    {"counter": 8, "kind": "CHALLENGE_B", "sender": "O", "receiver": "R",
        "rights": []},
    {"counter": 9, "kind": "RESPONSE_B", "sender": "R", "receiver": "O",
        "rights": []},
    {"counter": 10, "kind": "ROUND1_RESULT", "sender": "R", "receiver": "G",
        "rights": []},
    {"counter": 11, "kind": "ROUND1_RESULT", "sender": "O", "receiver": "G",
        "rights": []},
    {"counter": 12, "kind": "RECHECK", "sender": "G", "receiver": "R", "rights": []},
    {"counter": 13, "kind": "RECHECK", "sender": "G", "receiver": "O", "rights": []},
    {"counter": 14, "kind": "ROUND2_RESULT", "sender": "R", "receiver": "G",
        "rights": []},
    {"counter": 15, "kind": "ROUND2_RESULT", "sender": "O", "receiver": "G",
        "rights": []},
)

_LITERAL_SSH_SOURCE = re.compile(
    r"#!/usr/bin/env bash\n"
    r"set -euo pipefail\n"
    r"q1_vm=(?P<directory>/[A-Za-z0-9_./-]{1,4094})\n"
    r"exec ssh -F /dev/null \\\n"
    r"  -i \"\$q1_vm/id_ed25519\" -p (?P<port>[1-9][0-9]{0,4}) \\\n"
    r"  -o IdentitiesOnly=yes -o BatchMode=yes \\\n"
    r"  -o StrictHostKeyChecking=accept-new \\\n"
    r"  -o UserKnownHostsFile=\"\$q1_vm/known_hosts\" \\\n"
    r"  -o ConnectTimeout=10 \\\n"
    r"  (?P<destination>[A-Za-z_][A-Za-z0-9_.-]{0,63}@"
    r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?) \"\$@\"\n"
)

CONTROLLERS = ("cpu", "cpuset", "memory", "pids")
W_BLOCKED_SET = (
    "SIGCHLD", "SIGUSR1", "SIGHUP", "SIGTERM", "SIGINT", "SIGQUIT",
    "DEADLINE_SIGNAL",
)
FORBIDDEN_LAUNCH_ENV = ("SSH_AGENT_PID", "SSH_AUTH_SOCK")
QUALIFICATIONS = (
    "NOT_RUN", "BLOCKED_RETAINED", "UNKNOWN_RETAINED", "FAILED_RETAINED",
    "FIXTURE_LIVE_REFERENCE_MATCHED",
)
RELEASE_OUTCOMES = ("NOT_SENT", "CLEAN_REJECTED", "ACCEPTED", "UNKNOWN")

BUDGET_CEILINGS = {
    "action_journal_bytes": 64 * 1024,
    "result_journal_bytes": 752 * 1024,
    "case_slot_bytes": 16 * 1024,
    "case_slot_count": 12,
    "stage_logical_bytes": 2_080_768,
    "stage_regular_inodes": 22,
    "stage_total_inodes": 23,
    "stage_physical_bytes": 3 * MIB,
    "stage_physical_inodes": 48,
    "bundle_bytes": MAX_BUNDLE_BYTES,
    "bundle_files": MAX_BUNDLE_FILES,
    "bridge_logical_bytes": MIB,
    "bridge_logical_inodes": 1,
    "bridge_physical_bytes": 2 * MIB,
    "bridge_physical_inodes": 1,
    "private_capture_logical_bytes": 8 * MIB,
    "private_capture_logical_inodes": 256,
    "private_capture_physical_bytes": 12 * MIB,
    "private_capture_physical_inodes": 320,
    "public_record_logical_bytes": MIB,
    "public_record_logical_inodes": 64,
    "public_record_physical_bytes": 2 * MIB,
    "public_record_physical_inodes": 80,
    "existing_carrier_physical_bytes": 64 * MIB,
    "existing_carrier_physical_inodes": 1024,
    "watchdog_physical_bytes": 64 * MIB,
    "carrier_watchdog_base_bytes": 128 * MIB,
    "watchdog_full_failure_cpu_ns": 10_000_000_000,
    "watchdog_success_cpu_ns": 1_000_000_000,
    "loader_carrier_cpu_ns": 10_000_000_000,
    "carrier_audit_attributable_cpu_ns": 30_000_000_000,
    "batch_memory_bytes": 320 * MIB,
    "batch_pids": 5,
    "batch_cpu_ns": 170_000_000_000,
    "guardian_memory_bytes": 64 * MIB,
    "guardian_pids": 1,
    "guardian_cpu_ns": 10_000_000_000,
    "guardian_success_cpu_ns": 9_000_000_000,
    "supervisor_memory_bytes": 192 * MIB,
    "supervisor_pids": 1,
    "supervisor_cpu_ns": 100_000_000_000,
    "case_memory_max_bytes": 96 * MIB,
    "case_memory_peak_bytes": 128 * MIB,
    "case_pids": 3,
    "case_cpu_ns": 5_000_000_000,
    "shared_runtime_bytes": 64 * MIB,
    "handoff_bytes": MAX_H_BYTES,
    "cleanup_final_bytes": MAX_CLEANUP_FINAL_BYTES,
    "success_receipt_bytes": MAX_SUCCESS_RECEIPT_BYTES,
}

# Floors are deliberately physical and conservative.  They are applied to the
# per-device bill below rather than merely being descriptive manifest values.
# If roles share a physical device their bills are added before capacity is
# accepted.  Fixed kernel objects are additionally charged to the carrier/W
# device because A places them outside the 128 MiB carrier/W base.
DEVICE_ROLE_FLOORS = {
    "carrier": {
        "bytes": (128 * MIB) + (2 * MIB),
        "inodes": 1024 + 1,
    },
    "guest_tmpfs": {"bytes": 3 * MIB, "inodes": 48},
    "private_capture": {"bytes": 12 * MIB, "inodes": 320},
    "public_record": {"bytes": 2 * MIB, "inodes": 80},
}

DEADLINE_CEILINGS = {
    "owner_outer_ns": 840_000_000_000,
    "hello_exchange_ns": 10_000_000_000,
    "declare_release_ns": 48_000_000_000,
    "owner_prerelease_remaining_ns": 792_000_000_000,
    "guest_release_remaining_ns": 782_000_000_000,
    "owner_release_remaining_ns": 780_000_000_000,
    "guest_work_ns": 750_000_000_000,
    "guest_containment_ns": 760_000_000_000,
    "watchdog_remote_exit_ns": 830_000_000_000,
    "watchdog_margin_total_max_ns": 12_000_000_000,
    "offset_abs_max_ns": 2_000_000_000,
    "relative_drift_max_ns": 2_000_000_000,
    "final_success_reserve_ns": 110_000_000_000,
    "case_observe_ns": 20_000_000_000,
    "case_stop_ns": 25_000_000_000,
    "case_drain_ns": 30_000_000_000,
    "case_containment_ns": 40_000_000_000,
    "action_roundtrip_ns": 2_000_000_000,
    "cleanup_final_ack_ns": 5_000_000_000,
}

WATCHDOG_STATE_CONTRACT = {
    "entry_cpu_sample_first": True,
    "parent_before_pdeath_parent_after": True,
    "parent_non_one_and_identity_qualified": True,
    "signal_mask_normalized_empty_first": True,
    "catchable_dispositions_normalized_and_read_back": True,
    "sigxcpu_ignored_before_clone": True,
    "sigchld_no_nocldwait_or_nocldstop": True,
    "blocked_set": list(W_BLOCKED_SET),
    "signalfd_exact_blocked_set": True,
    "stdio_verified_then_close_range": True,
    "clone_args_bytes": 88,
    "clone_flags": ["CLONE_PIDFD"],
    "clone_exit_signal": "SIGCHLD",
    "clone_other_fields_zero": True,
    "single_child": True,
    "fork_fallback": False,
    "numeric_pid_migration_fallback": False,
    "child_pdeathsig_before_sigstop": True,
    "stopped_child_waitid_pidfd": True,
    "stopped_child_prlimit_readback": True,
    "single_pidfd_sigcont": True,
    "terminal_waitid_pidfd": True,
    "deadline_wins_simultaneous_ready": True,
    "timerfd_itself_kills": False,
    "status_zero_only_for_child_cld_exited_zero": True,
    "outer_read_calls": 0,
    "outer_write_calls": 0,
}


class NamespaceDeliveryContractError(ValueError):
    """Stable refusal from the public-safe offline contract."""


def _require(condition, reason):
    if not condition:
        raise NamespaceDeliveryContractError("Q2_NAMESPACE_DELIVERY_" + reason)


def _keys(value, names, reason="FIELDS"):
    _require(type(value) is dict and set(value) == set(names), reason)


def _same(value, expected):
    if type(value) is not type(expected):
        return False
    if type(expected) is dict:
        return (set(value) == set(expected)
            and all(_same(value[key], expected[key]) for key in expected))
    if type(expected) is list:
        return (len(value) == len(expected)
            and all(_same(left, right) for left, right in zip(value, expected)))
    return value == expected


def _integer(value, low=0, high=2**63 - 1, reason="INTEGER"):
    _require(type(value) is int and low <= value <= high, reason)
    return value


def _text(value, maximum=4096, reason="TEXT"):
    _require(type(value) is str, reason)
    try:
        raw = value.encode("utf-8", "strict")
    except UnicodeError:
        raise NamespaceDeliveryContractError("Q2_NAMESPACE_DELIVERY_" + reason) from None
    _require(0 < len(raw) <= maximum and "\x00" not in value
        and not any(ord(char) < 32 and char not in "\n\t" for char in value), reason)
    return value


def _token(value, pattern=r"[A-Za-z0-9][A-Za-z0-9_.:@+-]*", maximum=256,
           reason="TOKEN"):
    _text(value, maximum, reason)
    _require(re.fullmatch(pattern, value) is not None, reason)
    return value


def _digest(value, reason="DIGEST"):
    return _token(value, r"[0-9a-f]{64}", 64, reason)


def _commit(value, reason="COMMIT"):
    return _token(value, r"[0-9a-f]{40}", 40, reason)


def _boot(value):
    return _token(value,
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        36, "BOOT_ID")


def _path(value, *, allow_root=False):
    _text(value, 4096, "PATH")
    parsed = PurePosixPath(value)
    _require(value.startswith("/") and not value.startswith("//")
        and str(parsed) == value and ".." not in parsed.parts
        and not any(char.isspace() for char in value)
        and (allow_root or value != "/"), "PATH")
    return value


def sha256(raw):
    _require(type(raw) is bytes, "BYTES")
    return hashlib.sha256(raw).hexdigest()


def _json_value(value, depth=0):
    _require(depth <= 32, "JSON_DEPTH")
    if value is None or type(value) in (bool, int, str):
        if type(value) is int:
            _integer(value, -(2**63), 2**63 - 1, "JSON_INTEGER")
        elif type(value) is str:
            _text(value, MAX_FRAME_PAYLOAD_BYTES, "JSON_STRING")
        return
    if type(value) is list:
        _require(len(value) <= 4096, "JSON_LIST")
        for item in value:
            _json_value(item, depth + 1)
        return
    if type(value) is dict:
        _require(len(value) <= 4096, "JSON_OBJECT")
        for key, item in value.items():
            _text(key, 256, "JSON_KEY")
            _json_value(item, depth + 1)
        return
    raise NamespaceDeliveryContractError("Q2_NAMESPACE_DELIVERY_JSON_TYPE")


def canonical_bytes(value, *, maximum=None):
    """Return deterministic UTF-8 JSON after rejecting floats and odd types."""
    _json_value(value)
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")
    if maximum is not None:
        _require(len(raw) <= maximum, "CANONICAL_SIZE")
    return raw


def canonical_digest(value):
    return sha256(canonical_bytes(value))


def native_bridge_abi():
    """Return the exact JSON-like manifest exported by the built bridge."""
    return {
        "abi_version": 1,
        "clone_args_size": 88,
        "clone_flags": ["CLONE_INTO_CGROUP", "CLONE_PIDFD"],
        "clone_flags_value": (1 << 33) | 0x1000,
        "exit_signal": "SIGCHLD",
        "release_byte": 1,
        "max_gate_wait_ns": 840_000_000_000,
        "max_argv": 16,
        "max_env": 2,
        "max_groups": MAX_SUPPLEMENTARY_GROUPS,
        "exports": list(REQUIRED_BRIDGE_EXPORTS),
        "module_name": "_q2_namespace_clone_bridge",
        "init_symbol": "PyInit__q2_namespace_clone_bridge",
        "receipt_size": SUCCESS_RECEIPT_SIZE,
        "receipt_magic_ascii": SUCCESS_RECEIPT_MAGIC.decode("ascii"),
        "receipt_magic_offset": 0,
        "receipt_magic_bytes": len(SUCCESS_RECEIPT_MAGIC),
        "receipt_version": SUCCESS_RECEIPT_VERSION,
        "receipt_version_offset": 8,
        "receipt_byte_order": "little",
        "receipt_process_ns_offset": 16,
        "receipt_boottime_ns_offset": 24,
        "receipt_monotonic_ns_offset": 32,
        "receipt_realtime_ns_offset": 40,
        "receipt_counter_offset": 48,
        "receipt_previous_digest_offset": 56,
        "receipt_h_digest_offset": 88,
        "receipt_cleanup_final_digest_offset": 120,
        "receipt_ack_capture_head_offset": 152,
        "receipt_reserved_offset": 184,
        "receipt_reserved_bytes": 8,
        "receipt_hash_offset": SUCCESS_RECEIPT_HASH_OFFSET,
        "receipt_hash_input_bytes": SUCCESS_RECEIPT_HASH_OFFSET,
        "receipt_sha256_bytes": 32,
        "receipt_digest_size": 32,
        "receipt_single_raw_nonblocking_write": True,
        "fatal_timer_clock_identity": (
            "caller-sealed-not-kernel-readable:CLOCK_PROCESS_CPUTIME_ID"
        ),
        "atfork_registry_guard": "BLOCKED_EXTERNAL_F2_SOURCE_PROOF",
        "main_thread_guard": "BLOCKED_EXTERNAL_CALLER_PROOF",
    }


def reference_contract():
    """Return the sealed collector schemas, frame plan, and resource ceilings."""
    frame_plan = copy.deepcopy(list(REFERENCE_FRAME_PLAN))
    return {
        "context_schema": REFERENCE_CONTEXT_SCHEMA,
        "frame_schema": REFERENCE_FRAME_SCHEMA,
        "report_schema": REFERENCE_REPORT_SCHEMA,
        "synthetic_harness_schema": REFERENCE_SYNTHETIC_SCHEMA,
        "bootstrap_ready_schema": REFERENCE_BOOTSTRAP_READY_SCHEMA,
        "g_go_schema": REFERENCE_G_GO_SCHEMA,
        "purpose": "ISOLATED_NAMESPACE_FIXTURE",
        "frame_plan": frame_plan,
        "frame_plan_sha256": canonical_digest(frame_plan),
        "context_bytes_max": 16 * 1024,
        "frame_bytes_max": 4 * 1024,
        "frame_count": 15,
        "frame_payload_bytes_max": 60 * 1024,
        "status_bytes_max": 16 * 1024,
        "status_reads_max": 12,
        "status_bytes_total_max": 192 * 1024,
        "namespace_opens_max": 40,
        "random_bytes_exact": 64,
        "stdout_bytes_max": 32 * 1024,
        "stderr_bytes_max": 8 * 1024,
        "tasks_exact": 3,
        "installed_fd_max": {"G": 22, "R": 13, "O": 13},
        "installed_fd_total_max": 48,
        "queued_fd_max": 2,
        "fd_references_total_max": 50,
        "ordinary_groups_max": MAX_SUPPLEMENTARY_GROUPS,
        "synthetic_fixture_qualification": "NOT_RUN",
        "synthetic_field_ready": False,
        "synthetic_allow_run": False,
        "synthetic_native_fixture_executed": False,
        "synthetic_result_bytes_max": 4 * 1024,
        "synthetic_timeout_ns": 5_000_000_000,
        "synthetic_faults": ["EARLY_EXIT", "EXTRA_FRAME", "NONE", "STALE_SESSION"],
    }


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(type(key) is str and key not in result, "JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_number(_value):
    raise NamespaceDeliveryContractError("Q2_NAMESPACE_DELIVERY_JSON_NUMBER")


def decode_canonical(raw, *, maximum):
    _require(type(raw) is bytes and 0 < len(raw) <= maximum, "DOCUMENT_SIZE")
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_unique,
            parse_float=_reject_number, parse_constant=_reject_number)
    except NamespaceDeliveryContractError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise NamespaceDeliveryContractError("Q2_NAMESPACE_DELIVERY_JSON") from None
    _require(canonical_bytes(value) == raw, "JSON_NOT_CANONICAL")
    return value


def _identity(value, *, regular, sealed=False):
    common = ("path", "mount_id", "device", "inode", "uid", "gid", "mode",
        "parents_unwritable")
    names = common
    if regular:
        names = common + ("size", "sha256")
    _keys(value, names, "IDENTITY_FIELDS")
    _path(value["path"])
    for key in ("mount_id", "device", "inode"):
        _integer(value[key], 1, reason="IDENTITY_INTEGER")
    for key in ("uid", "gid"):
        _integer(value[key], 0, 2**32 - 2, "IDENTITY_INTEGER")
    _integer(value["mode"], 0, 0o7777, "IDENTITY_MODE")
    _require(value["parents_unwritable"] is True, "IDENTITY_PARENT_WRITABLE")
    if regular:
        if sealed:
            _require(value["mode"] & (0o222 | 0o6000) == 0,
                "IDENTITY_WRITABLE_OR_SETID")
        _integer(value["size"], 1, 2**63 - 1, "IDENTITY_SIZE")
        _digest(value["sha256"], "IDENTITY_DIGEST")
    return copy.deepcopy(value)


def _rlimit_pair(value, expected, reason):
    _require(type(value) is list and len(value) == 2
        and all(type(item) is int for item in value)
        and value == list(expected), reason)


def validate_watchdog(value):
    """Validate only W's sealed static contract; never execute or build W."""
    _keys(value, ("schema", "version", "identity", "source", "elf", "invocation",
        "security", "prefix", "state_machine", "resources", "status_map"),
        "WATCHDOG_FIELDS")
    _require(value["schema"] == WATCHDOG_SCHEMA, "WATCHDOG_SCHEMA")
    _token(value["version"], r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}", 128,
        "WATCHDOG_VERSION")
    identity = _identity(value["identity"], regular=True, sealed=True)

    source = value["source"]
    _keys(source, ("source_sha256", "binary_sha256", "relation_sha256",
        "build_manifest_sha256", "fault_trace_sha256"), "WATCHDOG_SOURCE_FIELDS")
    for item in source.values():
        _digest(item, "WATCHDOG_SOURCE_DIGEST")
    _require(source["binary_sha256"] == identity["sha256"], "WATCHDOG_BINARY_BINDING")

    elf = value["elf"]
    _keys(elf, ("class", "machine", "pt_interp", "loader", "dt_needed",
        "dt_needed_sha256", "complete"),
        "WATCHDOG_ELF_FIELDS")
    _require(elf["class"] == "ELF64" and elf["machine"] == "EM_X86_64",
        "WATCHDOG_ELF_PLATFORM")
    _path(elf["pt_interp"])
    loader_identity = _identity(elf["loader"], regular=True)
    _require(elf["pt_interp"] == loader_identity["path"],
        "WATCHDOG_PT_INTERP_BINDING")
    _require(type(elf["dt_needed"]) is list and 0 < len(elf["dt_needed"]) <= 32,
        "WATCHDOG_DT_NEEDED")
    seen = set()
    for dependency in elf["dt_needed"]:
        _keys(dependency, ("name", "identity"), "WATCHDOG_DEPENDENCY_FIELDS")
        name = _token(dependency["name"], r"[A-Za-z0-9_.+-]+", 256,
            "WATCHDOG_DEPENDENCY_NAME")
        _require(name not in seen, "WATCHDOG_DEPENDENCY_DUPLICATE")
        seen.add(name)
        _identity(dependency["identity"], regular=True)
    _require(elf["complete"] is True
        and elf["dt_needed_sha256"] == canonical_digest(elf["dt_needed"]),
        "WATCHDOG_DT_NEEDED_BINDING")

    invocation = value["invocation"]
    _keys(invocation, ("argv_sha256", "environment", "cwd", "umask"),
        "WATCHDOG_INVOCATION_FIELDS")
    _digest(invocation["argv_sha256"], "WATCHDOG_ARGV_DIGEST")
    _require(invocation["environment"] == {"LANG": "C", "LC_ALL": "C"},
        "WATCHDOG_ENVIRONMENT")
    _path(invocation["cwd"], allow_root=True)
    _require(type(invocation["umask"]) is int and invocation["umask"] == 0o077,
        "WATCHDOG_UMASK")

    security = value["security"]
    _keys(security, ("setid", "file_caps", "ambient_caps", "capabilities_sha256",
        "securebits_sha256", "seccomp_sha256", "lsm_sha256", "affinity_sha256",
        "scheduler_sha256"), "WATCHDOG_SECURITY_FIELDS")
    _require(security["setid"] is False and security["file_caps"] is False
        and security["ambient_caps"] == [], "WATCHDOG_PRIVILEGE")
    for key in security:
        if key.endswith("_sha256"):
            _digest(security[key], "WATCHDOG_SECURITY_DIGEST")

    prefix = value["prefix"]
    _keys(prefix, ("cpu_ns", "wall_ns", "tasks", "userspace_as_bytes",
        "userspace_rss_bytes", "physical_risk_bytes",
        "entry_installed_fds", "outer_read_calls", "outer_write_calls",
        "pipe_bytes", "kernel_object_bytes", "kernel_object_inodes", "audit_bytes",
        "audit_inodes", "fault_trace_qualified", "mutation_before_clone"),
        "WATCHDOG_PREFIX_FIELDS")
    _integer(prefix["cpu_ns"], 1, 1_000_000_000, "WATCHDOG_PREFIX_CPU")
    _integer(prefix["wall_ns"], 1, 2_000_000_000, "WATCHDOG_PREFIX_WALL")
    _require(prefix["tasks"] == 1 and type(prefix["tasks"]) is int,
        "WATCHDOG_PREFIX_TASKS")
    _integer(prefix["userspace_as_bytes"], 1, 64 * MIB,
        "WATCHDOG_PREFIX_AS")
    _integer(prefix["userspace_rss_bytes"], 1, 64 * MIB,
        "WATCHDOG_PREFIX_RSS")
    _integer(prefix["physical_risk_bytes"], 1, 64 * MIB,
        "WATCHDOG_PREFIX_PHYSICAL")
    _integer(prefix["entry_installed_fds"], 3, 8, "WATCHDOG_PREFIX_FDS")
    for key in ("outer_read_calls", "outer_write_calls"):
        _require(prefix[key] == 0 and type(prefix[key]) is int, "WATCHDOG_PREFIX_IO")
    for key in ("pipe_bytes", "kernel_object_bytes", "kernel_object_inodes",
                "audit_bytes", "audit_inodes"):
        _integer(prefix[key], 0, reason="WATCHDOG_PREFIX_ACCOUNTING")
    _require(prefix["fault_trace_qualified"] is True
        and prefix["mutation_before_clone"] is False, "WATCHDOG_PREFIX_QUALIFICATION")

    _require(_same(value["state_machine"], WATCHDOG_STATE_CONTRACT),
        "WATCHDOG_STATE_MACHINE")

    resources = value["resources"]
    _keys(resources, ("rlimits", "preclone_installed_fds", "postclone_base_fds",
        "peak_installed_fds", "steady_fds", "tasks", "physical_risk_bytes",
        "full_failure_cpu_ns", "success_cpu_ns", "remote_exit_ns",
        "wake_to_kill_ns", "kill_to_reap_ns", "reap_to_status_eof_ns"),
        "WATCHDOG_RESOURCE_FIELDS")
    limits = resources["rlimits"]
    _keys(limits, ("CPU", "AS", "DATA", "NOFILE", "CORE", "FSIZE", "STACK",
        "MEMLOCK", "MSGQUEUE", "NICE", "RTPRIO", "RTTIME"),
        "WATCHDOG_RLIMIT_FIELDS")
    for name, expected in {
        "CPU": (8, 9), "AS": (64 * MIB, 64 * MIB),
        "DATA": (64 * MIB, 64 * MIB), "NOFILE": (8, 8), "CORE": (0, 0),
        "FSIZE": (0, 0), "STACK": (8 * MIB, 8 * MIB), "MEMLOCK": (0, 0),
        "MSGQUEUE": (0, 0), "NICE": (0, 0), "RTPRIO": (0, 0),
        "RTTIME": (0, 0),
    }.items():
        _rlimit_pair(limits[name], expected, "WATCHDOG_RLIMIT")
    _integer(resources["peak_installed_fds"], 6, 7, "WATCHDOG_FD_TASK_TABLE")
    _require(type(resources["preclone_installed_fds"]) is int
        and type(resources["postclone_base_fds"]) is int
        and type(resources["steady_fds"]) is int
        and type(resources["tasks"]) is int
        and resources["preclone_installed_fds"] == 5
        and resources["postclone_base_fds"] == 6
        and resources["steady_fds"] == 3 and resources["tasks"] == 1,
        "WATCHDOG_FD_TASK_TABLE")
    _integer(resources["physical_risk_bytes"], 1, 64 * MIB,
        "WATCHDOG_PHYSICAL_RISK")
    _integer(resources["full_failure_cpu_ns"], 1, 10_000_000_000,
        "WATCHDOG_FAILURE_CPU")
    _integer(resources["success_cpu_ns"], 1, 1_000_000_000,
        "WATCHDOG_SUCCESS_CPU")
    _require(resources["remote_exit_ns"] == 830_000_000_000,
        "WATCHDOG_REMOTE_EXIT")
    margins = []
    for key in ("wake_to_kill_ns", "kill_to_reap_ns", "reap_to_status_eof_ns"):
        margins.append(_integer(resources[key], 1, 12_000_000_000,
            "WATCHDOG_MARGIN"))
    _require(sum(margins) <= 12_000_000_000, "WATCHDOG_MARGIN_TOTAL")

    _require(_same(value["status_map"], {
        "zero": "L_CLD_EXITED_0_ONLY",
        "nonzero": "COARSE_FAILURE_ONLY",
        "signal_or_unreaped": "UNKNOWN_RETAINED",
    }), "WATCHDOG_STATUS_MAP")
    return copy.deepcopy(value)


def _validate_member(value):
    _keys(value, ("basename", "role", "bytes", "sha256", "mode"),
        "BUNDLE_MEMBER_FIELDS")
    name = _token(value["basename"], r"[A-Za-z0-9][A-Za-z0-9_.-]{0,126}", 127,
        "BUNDLE_BASENAME")
    _require("/" not in name and name not in {"TASK.txt", "W", "watchdog"},
        "BUNDLE_FORBIDDEN_MEMBER")
    _require(value["role"] in {"collector", "supervisor", "bridge", "schema",
        "manifest", "launcher"}, "BUNDLE_ROLE")
    _integer(value["bytes"], 1, MAX_BUNDLE_BYTES, "BUNDLE_MEMBER_BYTES")
    _digest(value["sha256"], "BUNDLE_MEMBER_DIGEST")
    _require(type(value["mode"]) is int and value["mode"] in (0o400, 0o500),
        "BUNDLE_MEMBER_MODE")
    return copy.deepcopy(value)


def _validate_bridge(value, members):
    _keys(value, ("schema", "member_basename", "binary_bytes", "binary_sha256",
        "source_sha256", "relation", "relation_sha256", "build_manifest",
        "build_manifest_sha256",
        "compiler_sha256", "compiler_version_sha256", "flags", "flags_sha256",
        "deterministic_build_id_disabled", "python_abi", "soabi", "elf",
        "runtime_loader", "native_abi", "exports", "exports_sha256",
        "clean_build_one_sha256", "clean_build_two_sha256"), "BRIDGE_FIELDS")
    _require(value["schema"] == BRIDGE_SCHEMA, "BRIDGE_SCHEMA")
    basename = _token(value["member_basename"],
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,126}", 127, "BRIDGE_BASENAME")
    bridge_members = [member for member in members if member["role"] == "bridge"]
    _require(len(bridge_members) == 1 and bridge_members[0]["basename"] == basename,
        "BRIDGE_MEMBER_BINDING")
    member = bridge_members[0]
    _integer(value["binary_bytes"], 1, MAX_BUNDLE_BYTES, "BRIDGE_BINARY_BYTES")
    _require(value["binary_bytes"] == member["bytes"], "BRIDGE_MEMBER_BINDING")
    for name in ("binary_sha256", "source_sha256", "relation_sha256",
            "build_manifest_sha256", "compiler_sha256", "compiler_version_sha256",
            "flags_sha256", "exports_sha256", "clean_build_one_sha256",
            "clean_build_two_sha256"):
        _digest(value[name], "BRIDGE_DIGEST")
    _require(value["binary_sha256"] == member["sha256"]
        and value["clean_build_one_sha256"] == value["binary_sha256"]
        and value["clean_build_two_sha256"] == value["binary_sha256"],
        "BRIDGE_REPRODUCIBLE_BUILD")

    _require(type(value["flags"]) is list and 1 <= len(value["flags"]) <= 64,
        "BRIDGE_FLAGS")
    for flag in value["flags"]:
        _text(flag, 512, "BRIDGE_FLAG")
        _require("\x00" not in flag and "\n" not in flag and "\r" not in flag,
            "BRIDGE_FLAG")
    _require(value["flags_sha256"] == canonical_digest(value["flags"]),
        "BRIDGE_FLAGS_BINDING")
    _require(value["deterministic_build_id_disabled"] is True,
        "BRIDGE_BUILD_ID")
    _token(value["python_abi"], r"[A-Za-z0-9_.+-]+", 128, "BRIDGE_PYTHON_ABI")
    _token(value["soabi"], r"[A-Za-z0-9_.+-]+", 128, "BRIDGE_SOABI")

    elf = value["elf"]
    _keys(elf, ("class", "machine", "type", "pt_interp_absent", "dt_needed",
        "dt_needed_sha256", "complete"), "BRIDGE_ELF_FIELDS")
    _require(elf["class"] == "ELF64" and elf["machine"] == "EM_X86_64"
        and elf["type"] == "ET_DYN" and elf["pt_interp_absent"] is True,
        "BRIDGE_ELF_PLATFORM")
    _require(type(elf["dt_needed"]) is list and 0 < len(elf["dt_needed"]) <= 32,
        "BRIDGE_DT_NEEDED")
    names = set()
    for dependency in elf["dt_needed"]:
        _keys(dependency, ("name", "identity"), "BRIDGE_DEPENDENCY_FIELDS")
        name = _token(dependency["name"], r"[A-Za-z0-9_.+-]+", 256,
            "BRIDGE_DEPENDENCY_NAME")
        _require(name not in names, "BRIDGE_DEPENDENCY_DUPLICATE")
        names.add(name)
        _identity(dependency["identity"], regular=True)
    _require(elf["complete"] is True
        and elf["dt_needed_sha256"] == canonical_digest(elf["dt_needed"]),
        "BRIDGE_DT_NEEDED_BINDING")

    runtime_loader = value["runtime_loader"]
    _keys(runtime_loader, ("runtime_path", "runtime_sha256", "pt_interp", "loader"),
        "BRIDGE_RUNTIME_LOADER_FIELDS")
    _path(runtime_loader["runtime_path"])
    _digest(runtime_loader["runtime_sha256"], "BRIDGE_RUNTIME_DIGEST")
    _path(runtime_loader["pt_interp"])
    loader = _identity(runtime_loader["loader"], regular=True)
    _require(runtime_loader["pt_interp"] == loader["path"],
        "BRIDGE_RUNTIME_LOADER_BINDING")

    _require(_same(value["native_abi"], native_bridge_abi()),
        "BRIDGE_NATIVE_ABI")

    _require(type(value["exports"]) is list
        and value["exports"] == list(REQUIRED_BRIDGE_EXPORTS), "BRIDGE_EXPORTS")
    for export in value["exports"]:
        _token(export, r"[A-Za-z_][A-Za-z0-9_]*", 128, "BRIDGE_EXPORT")
    _require(value["exports_sha256"] == canonical_digest(value["exports"]),
        "BRIDGE_EXPORT_BINDING")

    expected_build = {
        "schema": BRIDGE_BUILD_SCHEMA,
        "source_sha256": value["source_sha256"],
        "compiler_sha256": value["compiler_sha256"],
        "compiler_version_sha256": value["compiler_version_sha256"],
        "flags": copy.deepcopy(value["flags"]),
        "flags_sha256": value["flags_sha256"],
        "deterministic_build_id_disabled": value["deterministic_build_id_disabled"],
        "python_abi": value["python_abi"],
        "soabi": value["soabi"],
        "elf_sha256": canonical_digest(elf),
        "runtime_loader_sha256": canonical_digest(runtime_loader),
        "native_abi_sha256": canonical_digest(value["native_abi"]),
    }
    _require(_same(value["build_manifest"], expected_build)
        and value["build_manifest_sha256"] == canonical_digest(expected_build),
        "BRIDGE_BUILD_MANIFEST_BINDING")
    expected_relation = {
        "schema": BRIDGE_RELATION_SCHEMA,
        "source_sha256": value["source_sha256"],
        "build_manifest_sha256": value["build_manifest_sha256"],
        "binary_bytes": value["binary_bytes"],
        "binary_sha256": value["binary_sha256"],
    }
    _require(_same(value["relation"], expected_relation)
        and value["relation_sha256"] == canonical_digest(expected_relation),
        "BRIDGE_RELATION_BINDING")
    return copy.deepcopy(value)


def validate_manifest(value):
    _keys(value, ("schema", "watchdog", "watchdog_args", "bootstrap", "bundle",
        "bridge", "stage", "protocol", "deadlines", "source_review"),
        "MANIFEST_FIELDS")
    _require(value["schema"] == MANIFEST_SCHEMA, "MANIFEST_SCHEMA")
    validate_watchdog(value["watchdog"])

    args = value["watchdog_args"]
    _require(type(args) is list and len(args) <= 32, "WATCHDOG_ARGS")
    for arg in args:
        _token(arg, r"[A-Za-z0-9_./:=+,-]+", 512, "WATCHDOG_ARG")
    _require("--" not in args, "WATCHDOG_ARG_SEPARATOR")

    bootstrap = value["bootstrap"]
    _keys(bootstrap, ("source", "source_bytes", "source_sha256", "token",
        "fixed_loader", "fixed_loader_sha256"), "BOOTSTRAP_FIELDS")
    source = _text(bootstrap["source"], MAX_BOOTSTRAP_SOURCE, "BOOTSTRAP_SOURCE")
    source_raw = source.encode("utf-8")
    _require(bootstrap["source_bytes"] == len(source_raw)
        and bootstrap["source_sha256"] == sha256(source_raw), "BOOTSTRAP_BINDING")
    expected_token = base64.urlsafe_b64encode(source_raw).rstrip(b"=").decode("ascii")
    _require(bootstrap["token"] == expected_token
        and re.fullmatch(r"[A-Za-z0-9_-]+", expected_token) is not None,
        "BOOTSTRAP_TOKEN")
    loader = _text(bootstrap["fixed_loader"], 4096, "FIXED_LOADER")
    _require(bootstrap["fixed_loader_sha256"] == sha256(loader.encode("utf-8")),
        "FIXED_LOADER_BINDING")

    bundle = value["bundle"]
    _keys(bundle, ("members", "total_bytes", "file_count", "aggregate_sha256"),
        "BUNDLE_FIELDS")
    _require(type(bundle["members"]) is list
        and 1 <= len(bundle["members"]) <= MAX_BUNDLE_FILES, "BUNDLE_MEMBERS")
    members = [_validate_member(member) for member in bundle["members"]]
    names = [member["basename"] for member in members]
    _require(len(set(names)) == len(names), "BUNDLE_MEMBER_DUPLICATE")
    roles = [member["role"] for member in members]
    _require(len(roles) == len(REQUIRED_BUNDLE_ROLES)
        and all(roles.count(role) == 1 for role in REQUIRED_BUNDLE_ROLES),
        "BUNDLE_REQUIRED_ROLES")
    total = sum(member["bytes"] for member in members)
    _require(bundle["file_count"] == len(members) and bundle["total_bytes"] == total
        and total <= MAX_BUNDLE_BYTES, "BUNDLE_TOTAL")
    aggregate = [{key: member[key] for key in ("basename", "bytes", "sha256")}
        for member in sorted(members, key=lambda item: item["basename"])]
    _require(bundle["aggregate_sha256"] == canonical_digest(aggregate),
        "BUNDLE_AGGREGATE")
    _validate_bridge(value["bridge"], members)

    stage = value["stage"]
    _keys(stage, ("action_journal_bytes", "result_journal_bytes", "case_slot_bytes",
        "case_slot_count", "result_offsets", "actual", "ceilings"), "STAGE_FIELDS")
    _require(_same({key: stage[key] for key in (
        "action_journal_bytes", "result_journal_bytes", "case_slot_bytes",
        "case_slot_count")}, {
            "action_journal_bytes": 64 * 1024,
            "result_journal_bytes": 752 * 1024,
            "case_slot_bytes": 16 * 1024,
            "case_slot_count": 12,
        }), "STAGE_LAYOUT")
    _require(_same(stage["result_offsets"], {
        "header": 0, "cases": 8192, "excursions": 598016,
        "terminal": 753664, "eof": 770048,
    }), "RESULT_OFFSETS")
    expected_actual = {
        "bundle_bytes": bundle["total_bytes"],
        "bundle_files": bundle["file_count"],
        "logical_bytes": (bundle["total_bytes"] + stage["action_journal_bytes"]
            + stage["result_journal_bytes"]
            + stage["case_slot_count"] * stage["case_slot_bytes"]),
        "regular_inodes": bundle["file_count"] + 2 + stage["case_slot_count"],
        "total_inodes": bundle["file_count"] + 3 + stage["case_slot_count"],
    }
    _require(_same(stage["actual"], expected_actual), "STAGE_ACTUAL_BINDING")
    expected_ceilings = {
        "bundle_bytes": MAX_BUNDLE_BYTES,
        "bundle_files": MAX_BUNDLE_FILES,
        "logical_bytes": 2_080_768,
        "regular_inodes": 22,
        "total_inodes": 23,
    }
    _require(_same(stage["ceilings"], expected_ceilings)
        and all(stage["actual"][name] <= stage["ceilings"][name]
            for name in expected_ceilings), "STAGE_CEILING")

    protocol = value["protocol"]
    _keys(protocol, ("case_ids", "reference_report_schema", "collector_frames",
        "reference_contract",
        "carrier_requests", "batch_releases", "native_batches", "action_commits",
        "old_carrier_self_writes", "guardian_self_writes", "total_self_writes",
        "guardian_outer_write_calls", "guardian_outer_write_bytes", "handoff_max_bytes",
        "cleanup_final_max_bytes", "success_receipt_bytes",
        "success_receipt_layout_sha256"), "PROTOCOL_FIELDS")
    _require(_same(protocol, {
        "case_ids": list(CASE_IDS), "reference_report_schema": REFERENCE_REPORT_SCHEMA,
        "collector_frames": 15, "reference_contract": reference_contract(),
        "carrier_requests": 1, "batch_releases": 1,
        "native_batches": 1, "action_commits": 37,
        "old_carrier_self_writes": 38, "guardian_self_writes": 38,
        "total_self_writes": 76, "guardian_outer_write_calls": 0,
        "guardian_outer_write_bytes": 0, "handoff_max_bytes": MAX_H_BYTES,
        "cleanup_final_max_bytes": MAX_CLEANUP_FINAL_BYTES,
        "success_receipt_bytes": SUCCESS_RECEIPT_SIZE,
        "success_receipt_layout_sha256": canonical_digest(SUCCESS_RECEIPT_LAYOUT),
    }), "PROTOCOL_CONTRACT")
    _require(_same(value["deadlines"], DEADLINE_CEILINGS), "DEADLINE_CONTRACT")

    review = value["source_review"]
    _keys(review, ("watchdog_source_reviewed", "watchdog_fault_trace_reviewed",
        "implementation_source_reviewed", "bridge_source_reviewed",
        "bridge_clean_builds_verified", "bridge_exports_verified",
        "strict_parser_tests_passed",
        "fault_tests_passed", "native_supported_results_retained",
        "unsupported_results_retained", "review_sha256"), "SOURCE_REVIEW_FIELDS")
    for key in review:
        if (key.endswith("_reviewed") or key.endswith("_verified")
                or key.endswith("_passed") or key.endswith("_retained")):
            _require(review[key] is True, "SOURCE_REVIEW_INCOMPLETE")
    _digest(review["review_sha256"], "SOURCE_REVIEW_DIGEST")
    return copy.deepcopy(value)


def _validate_manager(value):
    _keys(value, ("unit", "source_role", "api", "fields", "calls", "source_sha256",
        "writes_forbidden", "enumeration_forbidden"), "MANAGER_FIELDS")
    _token(value["unit"], r"user@[1-9][0-9]*\.service", 128, "MANAGER_UNIT")
    _token(value["source_role"], maximum=128, reason="MANAGER_SOURCE_ROLE")
    _token(value["api"], r"[A-Za-z0-9_.:-]+", 128, "MANAGER_API")
    _require(value["fields"] == ["MainPID", "InvocationID", "ControlGroup"],
        "MANAGER_FIELDS_LIST")
    _require(type(value["calls"]) is int and value["calls"] == 1, "MANAGER_CALLS")
    _digest(value["source_sha256"], "MANAGER_SOURCE_DIGEST")
    _require(value["writes_forbidden"] is True
        and value["enumeration_forbidden"] is True, "MANAGER_READ_ONLY")


def _validate_anchor(value):
    _keys(value, ("identity", "source_sha256", "fs_magic", "root_owned",
        "ordinary_delegation", "other_writer", "cgroup_type", "procs_empty",
        "subtree_control", "nr_dying_descendants", "live_descendants_d0",
        "depth_remaining", "descendants_remaining_after_d0", "cpuset_cpus",
        "cpuset_mems", "parent_controls_read_only"), "ANCHOR_FIELDS")
    _identity(value["identity"], regular=False)
    _digest(value["source_sha256"], "ANCHOR_SOURCE_DIGEST")
    _require(value["fs_magic"] == "CGROUP2_SUPER_MAGIC" and value["root_owned"] is True
        and value["ordinary_delegation"] is False and value["other_writer"] is False
        and value["cgroup_type"] == "domain" and value["procs_empty"] is True,
        "ANCHOR_QUALIFICATION")
    _require(value["subtree_control"] == list(CONTROLLERS), "ANCHOR_CONTROLLERS")
    _require(value["nr_dying_descendants"] == 0
        and type(value["nr_dying_descendants"]) is int, "ANCHOR_DYING")
    _integer(value["live_descendants_d0"], 0, reason="ANCHOR_D0")
    _integer(value["depth_remaining"], 2, reason="ANCHOR_DEPTH")
    _integer(value["descendants_remaining_after_d0"], 4,
        reason="ANCHOR_DESCENDANTS")
    _text(value["cpuset_cpus"], 256, "ANCHOR_CPUSET")
    _text(value["cpuset_mems"], 256, "ANCHOR_MEMS")
    _require(value["parent_controls_read_only"] is True, "ANCHOR_PARENT_WRITABLE")


def _validate_carrier_leaf(value):
    _keys(value, ("identity", "source_sha256", "cgroup_type", "subtree_control",
        "freeze", "populated", "frozen", "cpuset_cpus_effective",
        "cpuset_mems_effective", "parent_persistent", "held_fd_required",
        "cleanup_or_limit_race_absent", "numeric_pid_writes", "action_roundtrips",
        "final_entries", "old_carrier_self_writes", "guardian_self_writes",
        "total_self_writes"), "CARRIER_LEAF_FIELDS")
    _identity(value["identity"], regular=False)
    _digest(value["source_sha256"], "CARRIER_LEAF_SOURCE")
    _require(value["cgroup_type"] == "domain" and value["subtree_control"] == []
        and value["freeze"] == 0 and value["populated"] == 1 and value["frozen"] == 0,
        "CARRIER_LEAF_STATE")
    _text(value["cpuset_cpus_effective"], 256, "CARRIER_CPUSET")
    _text(value["cpuset_mems_effective"], 256, "CARRIER_MEMS")
    _require(value["parent_persistent"] is True and value["held_fd_required"] is True
        and value["cleanup_or_limit_race_absent"] is True
        and value["numeric_pid_writes"] is False, "CARRIER_LEAF_GUARDS")
    for name in ("action_roundtrips", "final_entries", "old_carrier_self_writes",
                 "guardian_self_writes", "total_self_writes"):
        _integer(value[name], 0, MAX_SELF_WRITES_TOTAL, "CARRIER_LEAF_WRITES")
    _require(value["action_roundtrips"] == MAX_ACTIONS
        and value["final_entries"] in (0, 1)
        and value["old_carrier_self_writes"]
            == value["action_roundtrips"] + value["final_entries"]
        and value["guardian_self_writes"] == 1 + value["action_roundtrips"]
        and value["total_self_writes"]
            == value["old_carrier_self_writes"] + value["guardian_self_writes"],
        "CARRIER_LEAF_WRITES")


def compute_device_bill(value):
    """Compute the A-defined conservative simultaneous bill for one device."""
    _keys(value, ("role", "device_ref", "available_bytes", "available_inodes",
        "obligations", "new_peak", "margin", "claimed_total", "policy"),
        "DEVICE_BILL_FIELDS")
    _token(value["role"], r"[a-z][a-z0-9_-]*", 64, "DEVICE_ROLE")
    _digest(value["device_ref"], "DEVICE_REF")
    _integer(value["available_bytes"], 0, reason="DEVICE_AVAILABLE")
    _integer(value["available_inodes"], 0, reason="DEVICE_AVAILABLE")
    _require(type(value["obligations"]) is list and len(value["obligations"]) <= 256,
        "DEVICE_OBLIGATIONS")
    ids = set()
    total_bytes = total_inodes = 0
    for obligation in value["obligations"]:
        _keys(obligation, ("id", "current_bytes", "current_inodes",
            "future_ceiling_bytes", "future_ceiling_inodes"), "OBLIGATION_FIELDS")
        name = _token(obligation["id"], maximum=128, reason="OBLIGATION_ID")
        _require(name not in ids, "OBLIGATION_DUPLICATE")
        ids.add(name)
        for key in ("current_bytes", "current_inodes", "future_ceiling_bytes",
                    "future_ceiling_inodes"):
            _integer(obligation[key], 0, reason="OBLIGATION_INTEGER")
        total_bytes += max(obligation["current_bytes"], obligation["future_ceiling_bytes"])
        total_inodes += max(obligation["current_inodes"], obligation["future_ceiling_inodes"])
    for group in ("new_peak", "margin"):
        _keys(value[group], ("bytes", "inodes"), "DEVICE_AMOUNT_FIELDS")
        _integer(value[group]["bytes"], 0, reason="DEVICE_AMOUNT")
        _integer(value[group]["inodes"], 0, reason="DEVICE_AMOUNT")
        total_bytes += value[group]["bytes"]
        total_inodes += value[group]["inodes"]
    expected = {"bytes": total_bytes, "inodes": total_inodes}
    _require(_same(value["claimed_total"], expected), "DEVICE_CLAIMED_TOTAL")
    _require(total_bytes <= value["available_bytes"]
        and total_inodes <= value["available_inodes"], "DEVICE_CAPACITY")
    _require(_same(value["policy"], {
        "same_obligation_uses_max": True,
        "hardlink_dedup_same_device_inode_only": True,
        "reflink_or_sparse_credit_requires_extent_proof": True,
        "partial_final_inode_uses_simultaneous_peak": True,
        "concurrent_writers_absent": True,
        "deletion_refunds_budget": False,
    }), "DEVICE_POLICY")
    return expected


def _validate_budgets(value):
    _keys(value, ("ceilings", "kernel_object_bytes", "kernel_object_inodes",
        "watchdog_prefix", "watchdog_and_carrier_shared_extent_proven", "devices",
        "source_sha256"), "BUDGET_FIELDS")
    _require(_same(value["ceilings"], BUDGET_CEILINGS), "BUDGET_CEILINGS")
    _integer(value["kernel_object_bytes"], 1, reason="KERNEL_OBJECT_BUDGET")
    _integer(value["kernel_object_inodes"], 1, reason="KERNEL_OBJECT_BUDGET")
    prefix = value["watchdog_prefix"]
    _keys(prefix, ("userspace_as_bytes", "userspace_rss_bytes",
        "physical_risk_bytes", "pipe_bytes", "kernel_object_bytes",
        "kernel_object_inodes", "audit_bytes", "audit_inodes"),
        "BUDGET_WATCHDOG_PREFIX_FIELDS")
    for name in ("userspace_as_bytes", "userspace_rss_bytes", "physical_risk_bytes"):
        _integer(prefix[name], 1, 64 * MIB, "BUDGET_WATCHDOG_PREFIX_MEMORY")
    for name in ("pipe_bytes", "kernel_object_bytes", "kernel_object_inodes",
                 "audit_bytes", "audit_inodes"):
        _integer(prefix[name], 0, reason="BUDGET_WATCHDOG_PREFIX_AMOUNT")
    _require(prefix["kernel_object_bytes"] == value["kernel_object_bytes"]
        and prefix["kernel_object_inodes"] == value["kernel_object_inodes"],
        "BUDGET_KERNEL_BINDING")
    _require(value["watchdog_and_carrier_shared_extent_proven"] is False,
        "UNPROVEN_BUDGET_DEDUP")
    _digest(value["source_sha256"], "BUDGET_SOURCE_DIGEST")
    _require(type(value["devices"]) is list and 1 <= len(value["devices"]) <= 16,
        "BUDGET_DEVICES")
    roles = set()
    by_device = {}
    carrier_device_ref = None
    for device in value["devices"]:
        bill = compute_device_bill(device)
        _require(device["role"] not in roles, "BUDGET_DEVICE_ROLE_DUPLICATE")
        roles.add(device["role"])
        _require(device["role"] in DEVICE_ROLE_FLOORS, "BUDGET_DEVICE_ROLE")
        floor = DEVICE_ROLE_FLOORS[device["role"]]
        _require(bill["bytes"] >= floor["bytes"]
            and bill["inodes"] >= floor["inodes"], "BUDGET_DEVICE_ROLE_FLOOR")
        device_ref = device["device_ref"]
        aggregate = by_device.setdefault(device_ref, {
            "available_bytes": device["available_bytes"],
            "available_inodes": device["available_inodes"],
            "bytes": 0,
            "inodes": 0,
        })
        _require(aggregate["available_bytes"] == device["available_bytes"]
            and aggregate["available_inodes"] == device["available_inodes"],
            "BUDGET_SHARED_DEVICE_CAPACITY")
        aggregate["bytes"] += bill["bytes"]
        aggregate["inodes"] += bill["inodes"]
        if device["role"] == "carrier":
            carrier_device_ref = device_ref
    _require(roles == set(DEVICE_ROLE_FLOORS), "BUDGET_DEVICE_ROLE_MISSING")
    _require(carrier_device_ref is not None, "BUDGET_DEVICE_ROLE_MISSING")
    by_device[carrier_device_ref]["bytes"] += value["kernel_object_bytes"]
    by_device[carrier_device_ref]["inodes"] += value["kernel_object_inodes"]
    by_device[carrier_device_ref]["bytes"] += prefix["pipe_bytes"] + prefix["audit_bytes"]
    by_device[carrier_device_ref]["inodes"] += prefix["audit_inodes"]
    for aggregate in by_device.values():
        _require(aggregate["bytes"] <= aggregate["available_bytes"]
            and aggregate["inodes"] <= aggregate["available_inodes"],
            "BUDGET_SHARED_DEVICE_CAPACITY")


def _validate_initial_state(value, plan_sha256=None, manifest_sha256=None):
    _require(type(value) is dict, "INITIAL_STATE_TYPE")
    expected = initial_state(plan_sha256 or value.get("plan_sha256", ZERO_DIGEST),
        manifest_sha256 or value.get("manifest_sha256", ZERO_DIGEST))
    _require(_same(value, expected), "INITIAL_STATE")


def validate_plan(value, *, manifest_sha256=None):
    _keys(value, ("schema", "authority", "implementation", "batch_id", "case_ids",
        "target", "manager_read", "carrier", "runtime", "anchor", "carrier_leaf",
        "stage_parent", "capture", "clocks", "budgets", "fixed_sources",
        "manifest_sha256", "initial_state"), "PLAN_FIELDS")
    _require(value["schema"] == PLAN_SCHEMA, "PLAN_SCHEMA")
    authority = value["authority"]
    _keys(authority, ("R", "A", "C", "owner_event", "scope", "phases",
        "endpoint_integrity_premise_accepted", "original_terminal_provenance_accepted"),
        "AUTHORITY_FIELDS")
    _require(_same(authority, {
        "R": RULE, "A": BASELINE, "C": CLOSURE, "owner_event": OWNER_DECISION,
        "scope": SCOPE, "phases": list(PHASES),
        "endpoint_integrity_premise_accepted": True,
        "original_terminal_provenance_accepted": False,
    }), "AUTHORITY")

    implementation = value["implementation"]
    _keys(implementation, ("commit", "tree", "source_files_sha256",
        "closure_ancestor_verified", "clean_tree", "targeted_tests_sha256",
        "full_suite_sha256", "native_ci_sha256", "independent_review_sha256"),
        "IMPLEMENTATION_FIELDS")
    _commit(implementation["commit"], "IMPLEMENTATION_COMMIT")
    _commit(implementation["tree"], "IMPLEMENTATION_TREE")
    _require(implementation["commit"] not in {RULE, BASELINE, CLOSURE},
        "IMPLEMENTATION_IDENTITY")
    for key in implementation:
        if key.endswith("sha256"):
            _digest(implementation[key], "IMPLEMENTATION_DIGEST")
    _require(implementation["closure_ancestor_verified"] is True
        and implementation["clean_tree"] is True, "IMPLEMENTATION_CHAIN")

    _token(value["batch_id"], r"[A-Za-z0-9][A-Za-z0-9_.-]{7,127}", 128,
        "BATCH_ID")
    _require(value["case_ids"] == list(CASE_IDS), "CASE_IDS")

    target = value["target"]
    _keys(target, ("guest_ref", "guest_source_sha256", "expected_boot_id", "uid",
        "gid", "groups", "groups_source_sha256", "same_uid_allowlist_sha256",
        "historical_fixture_only"), "TARGET_FIELDS")
    _digest(target["guest_ref"], "GUEST_REF")
    _digest(target["guest_source_sha256"], "GUEST_SOURCE")
    _boot(target["expected_boot_id"])
    _integer(target["uid"], 1, 2**32 - 2, "TARGET_UID")
    _integer(target["gid"], 1, 2**32 - 2, "TARGET_GID")
    _require(type(target["groups"]) is list
        and len(target["groups"]) <= MAX_SUPPLEMENTARY_GROUPS, "TARGET_GROUPS")
    for group in target["groups"]:
        _integer(group, 1, 2**32 - 2, "TARGET_GROUP")
    # The kernel setgroups/getgroups vector is exact: retain duplicates, but
    # require the caller to seal it in deterministic ascending order.
    _require(target["groups"] == sorted(target["groups"]), "TARGET_GROUPS")
    _digest(target["groups_source_sha256"], "TARGET_GROUP_SOURCE")
    _digest(target["same_uid_allowlist_sha256"], "TARGET_ALLOWLIST")
    _require(target["historical_fixture_only"] is True, "TARGET_SCOPE")
    _validate_manager(value["manager_read"])
    _require(value["manager_read"]["unit"] == f"user@{target['uid']}.service",
        "MANAGER_TARGET_BINDING")

    carrier = value["carrier"]
    _keys(carrier, ("profile", "profile_sha256", "host", "remote", "core_pattern",
        "remote_command", "remote_command_sha256"), "CARRIER_FIELDS")
    _require(carrier["profile"] == "env-bash-literal-ssh-v1", "CARRIER_PROFILE")
    _digest(carrier["profile_sha256"], "CARRIER_PROFILE_DIGEST")
    _text(carrier["remote_command"], MAX_REMOTE_COMMAND, "REMOTE_COMMAND")
    _digest(carrier["remote_command_sha256"], "REMOTE_COMMAND_DIGEST")
    host = carrier["host"]
    _keys(host, ("PATH", "cwd", "environment", "environment_sha256",
        "env_binary", "env_identity", "bash_binary", "bash_identity",
        "ssh_binary", "ssh_identity", "wrapper_source", "wrapper_source_bytes",
        "wrapper_source_sha256", "wrapper_identity", "identity_file",
        "identity_sha256", "identity_object", "known_hosts", "known_hosts_sha256",
        "known_hosts_object", "host_key_sha256", "local_argv",
        "local_argv_sha256", "ssh_argv", "ssh_argv_sha256",
        "excluded_environment", "fixed_identity_only", "known_host_preexisting",
        "new_host_key_adoption"), "HOST_FIELDS")
    _text(host["PATH"], 4096, "HOST_PATH_ENV")
    path_entries = host["PATH"].split(":")
    _require(path_entries and all(path_entries) and len(set(path_entries)) == len(path_entries),
        "HOST_PATH_ENV")
    for entry in path_entries:
        _path(entry, allow_root=True)
    for key in ("cwd", "env_binary", "bash_binary", "ssh_binary", "identity_file",
                "known_hosts"):
        _path(host[key], allow_root=(key == "cwd"))
    _require(PurePosixPath(host["bash_binary"]).name == "bash"
        and str(PurePosixPath(host["bash_binary"]).parent) in path_entries
        and PurePosixPath(host["ssh_binary"]).name == "ssh"
        and str(PurePosixPath(host["ssh_binary"]).parent) in path_entries,
        "HOST_PATH_RESOLUTION")
    for key in ("environment_sha256", "wrapper_source_sha256", "identity_sha256",
                "known_hosts_sha256", "host_key_sha256", "local_argv_sha256",
                "ssh_argv_sha256"):
        _digest(host[key], "HOST_DIGEST")
    environment = host["environment"]
    _require(type(environment) is dict and 1 <= len(environment) <= 32,
        "HOST_ENVIRONMENT")
    for name, item in environment.items():
        _token(name, r"[A-Z_][A-Z0-9_]*", 128, "HOST_ENVIRONMENT_NAME")
        _text(item, 4096, "HOST_ENVIRONMENT_VALUE")
    _require(environment.get("PATH") == host["PATH"]
        and environment.get("LANG") == "C" and environment.get("LC_ALL") == "C"
        and not ({*FORBIDDEN_LAUNCH_ENV, "BASH_ENV", "ENV"} & set(environment))
        and not any(name.startswith(("LD_", "PYTHON")) for name in environment)
        and host["environment_sha256"] == canonical_digest(environment),
        "HOST_ENVIRONMENT")
    for path_name, identity_name in (("env_binary", "env_identity"),
            ("bash_binary", "bash_identity"), ("ssh_binary", "ssh_identity")):
        identity = _identity(host[identity_name], regular=True)
        _require(identity["path"] == host[path_name], "HOST_EXECUTABLE_BINDING")
    identity_object = _identity(host["identity_object"], regular=True, sealed=True)
    known_hosts_object = _identity(host["known_hosts_object"], regular=True, sealed=True)
    _require(identity_object["path"] == host["identity_file"]
        and identity_object["sha256"] == host["identity_sha256"]
        and known_hosts_object["path"] == host["known_hosts"]
        and known_hosts_object["sha256"] == host["known_hosts_sha256"],
        "HOST_CREDENTIAL_BINDING")

    wrapper_source = _text(host["wrapper_source"], MAX_BOOTSTRAP_SOURCE,
        "HOST_WRAPPER_SOURCE")
    wrapper_raw = wrapper_source.encode("utf-8")
    wrapper_identity = _identity(host["wrapper_identity"], regular=True, sealed=True)
    _require(host["wrapper_source_bytes"] == len(wrapper_raw)
        and host["wrapper_source_sha256"] == sha256(wrapper_raw)
        and carrier["profile_sha256"] == host["wrapper_source_sha256"]
        and wrapper_identity["size"] == len(wrapper_raw)
        and wrapper_identity["sha256"] == host["wrapper_source_sha256"],
        "HOST_WRAPPER_BINDING")
    match = _LITERAL_SSH_SOURCE.fullmatch(wrapper_source)
    _require(match is not None, "HOST_WRAPPER_PROFILE")
    directory = match.group("directory")
    _require(host["identity_file"] == directory + "/id_ed25519"
        and host["known_hosts"] == directory + "/known_hosts",
        "HOST_WRAPPER_CREDENTIAL_PATH")
    expected_local_argv = [host["env_binary"], "bash", "-c", wrapper_source,
        wrapper_identity["path"], carrier["remote_command"]]
    expected_ssh_argv = ["ssh", "-F", "/dev/null", "-i", host["identity_file"],
        "-p", match.group("port"), "-o", "IdentitiesOnly=yes", "-o",
        "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o",
        "UserKnownHostsFile=" + host["known_hosts"], "-o", "ConnectTimeout=10",
        match.group("destination"), carrier["remote_command"]]
    _require(_same(host["local_argv"], expected_local_argv)
        and host["local_argv_sha256"] == canonical_digest(expected_local_argv),
        "HOST_LOCAL_ARGV_BINDING")
    _require(_same(host["ssh_argv"], expected_ssh_argv)
        and host["ssh_argv_sha256"] == canonical_digest(expected_ssh_argv),
        "HOST_SSH_ARGV_BINDING")
    _require(host["excluded_environment"] == list(FORBIDDEN_LAUNCH_ENV)
        and host["fixed_identity_only"] is True and host["known_host_preexisting"] is True
        and host["new_host_key_adoption"] is False, "HOST_AUTHENTICATION")
    remote = carrier["remote"]
    _keys(remote, ("login_shell", "login_shell_identity", "login_shell_version_sha256",
        "parser", "shell_argv_sha256", "sudo_path", "sudo_identity", "env_path",
        "env_identity", "sudo_policy_sha256", "no_pty",
        "stdin_binary", "stdout_stderr_separate", "wrapper_reads_stdin",
        "wrapper_redirects_stdio", "force_command_absent", "authorized_keys_command_absent",
        "ssh_rc_absent", "shell_startup_hooks_absent", "bash_env_absent", "env_hook_absent",
        "sudo_use_pty_absent", "sudo_io_plugin_absent", "sudo_prompt_absent"),
        "REMOTE_FIELDS")
    _path(remote["login_shell"])
    _require(remote["parser"] == "bash-posix-c-v1", "REMOTE_PARSER")
    login_shell = _identity(remote["login_shell_identity"], regular=True)
    sudo_identity = _identity(remote["sudo_identity"], regular=True)
    env_identity = _identity(remote["env_identity"], regular=True)
    _require(login_shell["path"] == remote["login_shell"]
        and sudo_identity["path"] == remote["sudo_path"]
        and env_identity["path"] == remote["env_path"], "REMOTE_IDENTITY_BINDING")
    for name in ("login_shell_version_sha256", "shell_argv_sha256",
                 "sudo_policy_sha256"):
        _digest(remote[name], "REMOTE_DIGEST")
    _require(remote["sudo_path"] == "/usr/bin/sudo"
        and remote["env_path"] == "/usr/bin/env", "REMOTE_FIXED_BINARIES")
    positive = ("no_pty", "stdin_binary", "stdout_stderr_separate",
        "force_command_absent", "authorized_keys_command_absent", "ssh_rc_absent",
        "shell_startup_hooks_absent", "bash_env_absent", "env_hook_absent",
        "sudo_use_pty_absent", "sudo_io_plugin_absent", "sudo_prompt_absent")
    _require(all(remote[key] is True for key in positive)
        and remote["wrapper_reads_stdin"] is False
        and remote["wrapper_redirects_stdio"] is False, "REMOTE_PROTOCOL")
    try:
        parsed_remote_command = shlex.split(carrier["remote_command"], posix=True)
    except ValueError:
        raise NamespaceDeliveryContractError(
            "Q2_NAMESPACE_DELIVERY_REMOTE_COMMAND_PARSE") from None
    _require(remote["shell_argv_sha256"] == canonical_digest(parsed_remote_command),
        "REMOTE_SHELL_ROUNDTRIP")
    core = carrier["core_pattern"]
    _keys(core, ("source_sha256", "value_sha256", "is_pipe"), "CORE_PATTERN_FIELDS")
    _digest(core["source_sha256"], "CORE_PATTERN_SOURCE")
    _digest(core["value_sha256"], "CORE_PATTERN_VALUE")
    _require(core["is_pipe"] is False, "CORE_PATTERN_PIPE")
    runtime = value["runtime"]
    _keys(runtime, ("identity", "abi", "soabi", "import_closure_sha256",
        "supports_isolated_mode", "guest_compilation"), "RUNTIME_FIELDS")
    _identity(runtime["identity"], regular=True)
    _require(runtime["abi"] == "linux-x86_64-lp64-cpython-3.12",
        "RUNTIME_ABI")
    _token(runtime["soabi"], r"[A-Za-z0-9_.+-]+", 128, "RUNTIME_SOABI")
    _digest(runtime["import_closure_sha256"], "RUNTIME_IMPORT_CLOSURE")
    _require(runtime["supports_isolated_mode"] is True
        and runtime["guest_compilation"] is False, "RUNTIME_MODE")
    _validate_anchor(value["anchor"])
    _validate_carrier_leaf(value["carrier_leaf"])
    _identity(value["stage_parent"], regular=False)

    capture = value["capture"]
    _keys(capture, ("private_parent_ref", "private_parent_source_sha256",
        "append_fsync_before_ack", "raw_publication", "public_summary_only",
        "max_logical_bytes", "max_logical_inodes", "max_physical_bytes",
        "max_physical_inodes"), "CAPTURE_FIELDS")
    _digest(capture["private_parent_ref"], "CAPTURE_PARENT")
    _digest(capture["private_parent_source_sha256"], "CAPTURE_SOURCE")
    _require(capture["append_fsync_before_ack"] is True
        and capture["raw_publication"] is False and capture["public_summary_only"] is True
        and capture["max_logical_bytes"] == 8 * MIB
        and capture["max_logical_inodes"] == 256
        and capture["max_physical_bytes"] == 12 * MIB
        and capture["max_physical_inodes"] == 320, "CAPTURE_CONTRACT")

    clocks = value["clocks"]
    _keys(clocks, ("ceilings", "owner_adjtimex_sha256", "guest_adjtimex_sha256",
        "owner_clocksource_sha256", "guest_clocksource_sha256",
        "relative_frequency_bound_sha256", "refresh_allowed"), "CLOCK_FIELDS")
    _require(_same(clocks["ceilings"], DEADLINE_CEILINGS)
        and clocks["refresh_allowed"] is False, "CLOCK_CONTRACT")
    for key in clocks:
        if key.endswith("sha256"):
            _digest(clocks[key], "CLOCK_SOURCE_DIGEST")
    _validate_budgets(value["budgets"])

    fixed = value["fixed_sources"]
    _keys(fixed, ("target", "ordinary_identity", "manager", "runtime", "carrier",
        "anchor", "carrier_leaf", "stage_parent", "watchdog", "budget", "clock",
        "audit", "capture"), "FIXED_SOURCE_FIELDS")
    _require(all(item is True for item in fixed.values()), "FIXED_SOURCE_MISSING")
    _digest(value["manifest_sha256"], "MANIFEST_DIGEST")
    if manifest_sha256 is not None:
        _require(value["manifest_sha256"] == manifest_sha256, "MANIFEST_BINDING")
    return copy.deepcopy(value)


def _command_inputs(plan, manifest):
    """Validate only inputs needed to compose the command, without a cycle.

    The complete plan binds this command into the host argv and initial state,
    so it cannot be validated until after the command has been composed.  This
    narrow pass still closes every free path used in the command itself.
    """
    checked_manifest = validate_manifest(manifest)
    _require(type(plan) is dict, "PLAN_TYPE")
    manifest_sha = canonical_digest(checked_manifest)
    _require(plan.get("manifest_sha256") == manifest_sha, "MANIFEST_BINDING")

    runtime = plan.get("runtime")
    _require(type(runtime) is dict, "RUNTIME_FIELDS")
    _keys(runtime, ("identity", "abi", "soabi", "import_closure_sha256",
        "supports_isolated_mode", "guest_compilation"), "RUNTIME_FIELDS")
    runtime_identity = _identity(runtime["identity"], regular=True)
    _require(runtime["abi"] == "linux-x86_64-lp64-cpython-3.12"
        and runtime["supports_isolated_mode"] is True
        and runtime["guest_compilation"] is False, "RUNTIME_MODE")

    carrier = plan.get("carrier")
    _require(type(carrier) is dict, "CARRIER_FIELDS")
    remote = carrier.get("remote")
    _require(type(remote) is dict, "REMOTE_FIELDS")
    for name in ("sudo_path", "env_path"):
        _path(remote.get(name))
    _require(remote["sudo_path"] == "/usr/bin/sudo"
        and remote["env_path"] == "/usr/bin/env", "REMOTE_FIXED_BINARIES")
    for path_name, identity_name in (("sudo_path", "sudo_identity"),
            ("env_path", "env_identity")):
        identity = _identity(remote.get(identity_name), regular=True)
        _require(identity["path"] == remote[path_name],
            "REMOTE_IDENTITY_BINDING")
    return checked_manifest, runtime_identity, remote


def expected_remote_command(plan, manifest):
    """Construct A's sole remote command using :func:`shlex.join`."""
    checked_manifest, runtime_identity, remote = _command_inputs(plan, manifest)
    watchdog = checked_manifest["watchdog"]
    bootstrap = checked_manifest["bootstrap"]
    argv = [
        "exec", remote["sudo_path"], "-n", "--", remote["env_path"], "-i",
        "LANG=C", "LC_ALL=C", watchdog["identity"]["path"],
        *checked_manifest["watchdog_args"], "--", runtime_identity["path"],
        "-I", "-B", "-c",
        bootstrap["fixed_loader"], bootstrap["token"],
    ]
    command = shlex.join(argv)
    _require(len(command.encode("utf-8")) <= MAX_REMOTE_COMMAND,
        "REMOTE_COMMAND_SIZE")
    return command


def validate_contract(plan, manifest):
    """Validate a complete offline F0/F2 pair and return only safe summaries."""
    checked_manifest = validate_manifest(manifest)
    manifest_sha = canonical_digest(checked_manifest)
    checked_plan = validate_plan(plan, manifest_sha256=manifest_sha)
    command = expected_remote_command(checked_plan, checked_manifest)
    _require(checked_plan["carrier"]["remote_command"] == command
        and checked_plan["carrier"]["remote_command_sha256"]
            == sha256(command.encode("utf-8")), "REMOTE_COMMAND_BINDING")
    expected_argv = [checked_manifest["watchdog"]["identity"]["path"],
        *checked_manifest["watchdog_args"], "--",
        checked_plan["runtime"]["identity"]["path"], "-I", "-B", "-c",
        checked_manifest["bootstrap"]["fixed_loader"],
        checked_manifest["bootstrap"]["token"]]
    expected_shell_argv = ["exec", checked_plan["carrier"]["remote"]["sudo_path"],
        "-n", "--", checked_plan["carrier"]["remote"]["env_path"], "-i",
        "LANG=C", "LC_ALL=C", *expected_argv]
    _require(shlex.split(command, posix=True) == expected_shell_argv
        and checked_plan["carrier"]["remote"]["shell_argv_sha256"]
            == canonical_digest(expected_shell_argv), "REMOTE_SHELL_ROUNDTRIP")
    _require(checked_manifest["watchdog"]["invocation"]["argv_sha256"]
        == canonical_digest(expected_argv), "WATCHDOG_ARGV_BINDING")
    bridge = checked_manifest["bridge"]
    _require(bridge["python_abi"] == checked_plan["runtime"]["abi"]
        and bridge["soabi"] == checked_plan["runtime"]["soabi"],
        "BRIDGE_RUNTIME_BINDING")
    runtime_identity = checked_plan["runtime"]["identity"]
    _require(bridge["runtime_loader"]["runtime_path"] == runtime_identity["path"]
        and bridge["runtime_loader"]["runtime_sha256"] == runtime_identity["sha256"],
        "BRIDGE_RUNTIME_LOADER_BINDING")
    prefix = checked_manifest["watchdog"]["prefix"]
    budget_prefix = checked_plan["budgets"]["watchdog_prefix"]
    _require(_same(budget_prefix, {name: prefix[name] for name in budget_prefix}),
        "WATCHDOG_PREFIX_BUDGET_BINDING")
    plan_without_state = copy.deepcopy(checked_plan)
    supplied_state = plan_without_state.pop("initial_state")
    plan_sha = canonical_digest(plan_without_state)
    _validate_initial_state(supplied_state, plan_sha, manifest_sha)
    return {
        "status": "OFFLINE_CONTRACT_SHAPE_VERIFIED",
        "plan_sha256": plan_sha,
        "manifest_sha256": manifest_sha,
        "remote_command_sha256": sha256(command.encode("utf-8")),
        "remote_command_bytes": len(command.encode("utf-8")),
        "carrier_request_limit": 1,
        "batch_release_limit": 1,
        "native_batch_limit": 1,
        "case_limit": 12,
        "field_facts_proven": False,
        "source_bytes_proven": False,
        "build_proven": False,
        "live_proven": False,
        "durability_proven": False,
        "guest_contacted": False,
    }


def evaluate_f0(plan=None, manifest=None):
    """Return ``NOT_ISSUED`` for absent private inputs, never fill blanks live."""
    blockers = []
    required_plan = ("target", "manager_read", "carrier", "runtime", "anchor",
        "carrier_leaf", "stage_parent", "capture", "clocks", "budgets",
        "fixed_sources", "initial_state")
    required_manifest = ("watchdog", "bootstrap", "bundle", "stage", "protocol",
        "deadlines", "source_review")
    if plan is None:
        blockers.append("F0_PRIVATE_PLAN_ABSENT")
    elif type(plan) is not dict:
        raise NamespaceDeliveryContractError("Q2_NAMESPACE_DELIVERY_PLAN_TYPE")
    else:
        blockers.extend("F0_PLAN_" + name.upper() + "_ABSENT"
            for name in required_plan if name not in plan or plan[name] in (None, ""))
    if manifest is None:
        blockers.append("F0_SEALED_MANIFEST_ABSENT")
    elif type(manifest) is not dict:
        raise NamespaceDeliveryContractError("Q2_NAMESPACE_DELIVERY_MANIFEST_TYPE")
    else:
        blockers.extend("F0_MANIFEST_" + name.upper() + "_ABSENT"
            for name in required_manifest if name not in manifest or manifest[name] in (None, ""))
    if blockers:
        return {
            "status": "NOT_ISSUED", "blockers": blockers,
            "fixture_delivery_issued": False,
            "fixture_batch_release_issued": False,
            "fixture_native_batch_issued": False,
            "batch_release_outcome": "NOT_SENT",
            "fixture_qualification": "NOT_RUN",
            "can_issue_carrier": False, "can_issue_release": False,
            "can_issue_native": False,
        }
    verified = validate_contract(plan, manifest)
    return {
        **verified, "blockers": [], "fixture_delivery_issued": False,
        "fixture_batch_release_issued": False,
        "fixture_native_batch_issued": False,
        "batch_release_outcome": "NOT_SENT", "fixture_qualification": "NOT_RUN",
        "contract_shape_only": True,
        "can_issue_carrier": False, "can_issue_release": False,
        "can_issue_native": False, "external_source_checks_required": True,
    }


def initial_state(plan_sha256, manifest_sha256):
    _digest(plan_sha256, "STATE_PLAN_DIGEST")
    _digest(manifest_sha256, "STATE_MANIFEST_DIGEST")
    _require(plan_sha256 != ZERO_DIGEST and manifest_sha256 != ZERO_DIGEST,
        "STATE_UNBOUND_DIGEST")
    return {
        "schema": STATE_SCHEMA,
        "plan_sha256": plan_sha256,
        "manifest_sha256": manifest_sha256,
        "sequence": 0,
        "phase": "DECLARED",
        "fixture_delivery_issued": False,
        "fixture_batch_release_issued": False,
        "fixture_batch_release_accepted": False,
        "batch_release_outcome": "NOT_SENT",
        "fixture_native_batch_issued": False,
        "fixture_qualification": "NOT_RUN",
        "carrier_requests": 0,
        "batch_releases": 0,
        "native_batches": 0,
        "action_commits": 0,
        "case_index": 0,
        "cases": {case: {
            "clone_issued": False, "exec_go_issued": False,
            "g_go_issued": False, "final": False,
        } for case in CASE_IDS},
        "capture_head": ZERO_DIGEST,
        "last_frame_digest": ZERO_DIGEST,
    }


def validate_state(value):
    _require(type(value) is dict, "STATE_FIELDS")
    _keys(value, initial_state("1" * 64, "2" * 64).keys(), "STATE_FIELDS")
    _digest(value["plan_sha256"], "STATE_PLAN_DIGEST")
    _digest(value["manifest_sha256"], "STATE_MANIFEST_DIGEST")
    expected = initial_state(value["plan_sha256"], value["manifest_sha256"])
    # This public-safe module has no capture writer or field authority.  Its
    # only valid state is therefore the exact unissued initial snapshot.
    _require(_same(value, expected), "OFFLINE_STATE_NOT_INITIAL")
    return copy.deepcopy(value)


def make_frame(kind, payload, *, counter, previous_digest):
    _token(kind, r"[A-Z][A-Z0-9_]*", 64, "FRAME_KIND")
    _require(kind.startswith("OFFLINE_TEST_"),
        "OFFLINE_FIELD_FRAME_MANUFACTURE_FORBIDDEN")
    _integer(counter, 1, 2**31 - 1, "FRAME_COUNTER")
    _digest(previous_digest, "FRAME_PREVIOUS")
    payload_raw = canonical_bytes(payload, maximum=MAX_FRAME_PAYLOAD_BYTES)
    value = {
        "schema": FRAME_SCHEMA,
        "kind": kind,
        "counter": counter,
        "previous_digest": previous_digest,
        "payload_bytes": len(payload_raw),
        "payload_sha256": sha256(payload_raw),
        "payload": payload,
    }
    return canonical_bytes(value, maximum=MAX_FRAME_PAYLOAD_BYTES + 4096)


def verify_frame(raw):
    value = decode_canonical(raw, maximum=MAX_FRAME_PAYLOAD_BYTES + 4096)
    _keys(value, ("schema", "kind", "counter", "previous_digest", "payload_bytes",
        "payload_sha256", "payload"), "FRAME_FIELDS")
    _require(value["schema"] == FRAME_SCHEMA, "FRAME_SCHEMA")
    _token(value["kind"], r"[A-Z][A-Z0-9_]*", 64, "FRAME_KIND")
    _integer(value["counter"], 1, 2**31 - 1, "FRAME_COUNTER")
    _digest(value["previous_digest"], "FRAME_PREVIOUS")
    payload = canonical_bytes(value["payload"], maximum=MAX_FRAME_PAYLOAD_BYTES)
    _require(value["payload_bytes"] == len(payload)
        and value["payload_sha256"] == sha256(payload), "FRAME_PAYLOAD_BINDING")
    return {
        **copy.deepcopy(value),
        "shape_verified": True,
        "fixture_qualification": "NOT_RUN",
        "durability_proven": False,
        "field_fact_proven": False,
        "live_proven": False,
    }


def next_capture_head(previous_head, frame_raw):
    _digest(previous_head, "CAPTURE_PREVIOUS")
    verify_frame(frame_raw)
    domain = b"local-hand-q2-namespace-capture/v1\x00"
    return sha256(domain + bytes.fromhex(previous_head)
        + len(frame_raw).to_bytes(8, "big") + frame_raw)


def make_capture_ack(previous_head, frame_raw, *, fsync_complete):
    """Refuse to manufacture a durability claim in the offline module."""
    del previous_head, frame_raw, fsync_complete
    raise NamespaceDeliveryContractError(
        "Q2_NAMESPACE_DELIVERY_OFFLINE_DURABLE_ACK_FORBIDDEN")


def verify_capture_ack(value, previous_head, frame_raw):
    """Check an external ACK envelope structurally; prove no fsync or field fact."""
    _keys(value, ("schema", "counter", "frame_digest", "capture_head",
        "append_complete", "fsync_complete"), "CAPTURE_ACK_FIELDS")
    frame = verify_frame(frame_raw)
    _digest(previous_head, "CAPTURE_PREVIOUS")
    expected = {
        "schema": CAPTURE_ACK_SCHEMA,
        "counter": frame["counter"],
        "frame_digest": sha256(frame_raw),
        "capture_head": next_capture_head(previous_head, frame_raw),
        "append_complete": True,
        "fsync_complete": True,
    }
    _require(_same(value, expected), "CAPTURE_ACK")
    return {
        **copy.deepcopy(value),
        "shape_verified": True,
        "durability_proven": False,
        "field_fact_proven": False,
        "live_proven": False,
    }


def advance_state(state, frame_raw, capture_ack):
    """Refuse all field-state mutation in this no-I/O offline verifier.

    A real delivery owner must append/fsync the action in its private capture
    before setting any issued bit.  A caller-supplied boolean or hash-chain is
    not evidence that this occurred, so this module cannot advance the state.
    """
    validate_state(state)
    del frame_raw, capture_ack
    raise NamespaceDeliveryContractError(
        "Q2_NAMESPACE_DELIVERY_OFFLINE_STATE_MUTATION_FORBIDDEN")


def _bounded_object(raw, schema, maximum):
    value = decode_canonical(raw, maximum=maximum)
    _keys(value, ("schema", "payload"), "BOUNDED_OBJECT_FIELDS")
    _require(value["schema"] == schema and type(value["payload"]) is dict,
        "BOUNDED_OBJECT_SCHEMA")
    return copy.deepcopy(value)


def _validate_handoff_payload(value):
    digest_fields = (
        "plan_sha256", "manifest_sha256", "bundle_sha256", "context_sha256",
        "runtime_sha256", "watchdog_sha256", "bridge_sha256",
        "cleanup_source_sha256", "source_catalog_sha256",
        "identity_catalog_sha256", "fd_table_sha256", "deadline_catalog_sha256",
        "cpu_ledger_sha256", "timer_catalog_sha256",
        "action_excursions_sha256", "stage_state_sha256",
        "owner_acks_sha256", "result_sha256", "action_head_sha256",
        "capture_head_sha256",
    )
    fields = (
        "batch_id", "session_id", "boot_id", "implementation_commit",
        "implementation_tree", *digest_fields, "case_ids", "case_bitmap",
        "action_counter", "stop_latch", "success_latch", "final_carrier_ready",
        "all_stage_slots_final_or_empty", "work_deadline_boottime_ns",
        "containment_deadline_boottime_ns", "utc_not_after_ns",
        "process_cpu_at_handoff_ns", "handoff_boottime_ns",
        "handoff_monotonic_ns", "handoff_realtime_ns",
    )
    _keys(value, fields, "HANDOFF_PAYLOAD_FIELDS")
    _token(value["batch_id"], r"[A-Za-z0-9][A-Za-z0-9_.-]{7,127}", 128,
        "HANDOFF_BATCH")
    _token(value["session_id"], r"[A-Za-z0-9][A-Za-z0-9_.-]{7,127}", 128,
        "HANDOFF_SESSION")
    _boot(value["boot_id"])
    _commit(value["implementation_commit"], "HANDOFF_IMPLEMENTATION")
    _commit(value["implementation_tree"], "HANDOFF_IMPLEMENTATION")
    for name in digest_fields:
        _digest(value[name], "HANDOFF_DIGEST")
    _require(value["case_ids"] == list(CASE_IDS), "HANDOFF_CASE_IDS")
    _token(value["case_bitmap"], r"[01]{12}", 12, "HANDOFF_CASE_BITMAP")
    _integer(value["action_counter"], 0, MAX_ACTIONS, "HANDOFF_ACTION_COUNTER")
    for name in ("stop_latch", "success_latch", "final_carrier_ready",
                 "all_stage_slots_final_or_empty"):
        _require(type(value[name]) is bool, "HANDOFF_BOOLEAN")
    _require(not (value["stop_latch"] and value["success_latch"]),
        "HANDOFF_LATCH")
    work = _integer(value["work_deadline_boottime_ns"], 1,
        reason="HANDOFF_DEADLINE")
    containment = _integer(value["containment_deadline_boottime_ns"], 1,
        reason="HANDOFF_DEADLINE")
    _require(work < containment and containment - work <= 10_000_000_000,
        "HANDOFF_DEADLINE_ORDER")
    _integer(value["utc_not_after_ns"], 1, reason="HANDOFF_DEADLINE")
    _integer(value["process_cpu_at_handoff_ns"], 0, 18_000_000_000,
        "HANDOFF_PROCESS_CPU")
    for name in ("handoff_boottime_ns", "handoff_monotonic_ns",
                 "handoff_realtime_ns"):
        _integer(value[name], 1, reason="HANDOFF_CLOCK")
    return copy.deepcopy(value)


def _validate_cleanup_final_payload(value):
    digest_fields = (
        "previous_digest", "handoff_sha256", "context_sha256", "runtime_sha256",
        "bridge_sha256", "bridge_copy_sha256", "bridge_seals_sha256",
        "cleanup_actuals_sha256", "stage_final_sha256", "cgroup_final_sha256",
        "anchor_final_sha256",
    )
    fields = (
        "batch_id", "session_id", "counter", *digest_fields, "case_bitmap",
        "action_counter", "tc_ns", "tw_ns", "all_cleanup_complete",
        "success_eligible",
    )
    _keys(value, fields, "CLEANUP_FINAL_PAYLOAD_FIELDS")
    _token(value["batch_id"], r"[A-Za-z0-9][A-Za-z0-9_.-]{7,127}", 128,
        "CLEANUP_FINAL_BATCH")
    _token(value["session_id"], r"[A-Za-z0-9][A-Za-z0-9_.-]{7,127}", 128,
        "CLEANUP_FINAL_SESSION")
    _integer(value["counter"], 1, 2**31 - 1, "CLEANUP_FINAL_COUNTER")
    for name in digest_fields:
        _digest(value[name], "CLEANUP_FINAL_DIGEST")
    _token(value["case_bitmap"], r"[01]{12}", 12, "CLEANUP_FINAL_CASE_BITMAP")
    _integer(value["action_counter"], 0, MAX_ACTIONS,
        "CLEANUP_FINAL_ACTION_COUNTER")
    _integer(value["tc_ns"], 1, 999_999_999, "CLEANUP_FINAL_TC")
    _integer(value["tw_ns"], 1, 1_000_000_000, "CLEANUP_FINAL_TW")
    _require(type(value["all_cleanup_complete"]) is bool
        and type(value["success_eligible"]) is bool, "CLEANUP_FINAL_BOOLEAN")
    _require(not value["success_eligible"] or (
        value["all_cleanup_complete"]
        and value["case_bitmap"] == "1" * len(CASE_IDS)
        and value["action_counter"] == MAX_ACTIONS), "CLEANUP_FINAL_SUCCESS")
    return copy.deepcopy(value)


def _validate_success_receipt_expected(value):
    fields = (
        "version", "process_cpu_ns", "boottime_ns", "monotonic_ns",
        "realtime_ns", "counter", "previous_digest", "handoff_sha256",
        "cleanup_final_sha256", "capture_head_sha256",
    )
    _keys(value, fields, "SUCCESS_RECEIPT_EXPECTED_FIELDS")
    _require(value["version"] == SUCCESS_RECEIPT_VERSION
        and type(value["version"]) is int, "SUCCESS_RECEIPT_VERSION")
    for name in ("process_cpu_ns", "boottime_ns", "monotonic_ns", "realtime_ns"):
        _integer(value[name], 1, 2**64 - 1, "SUCCESS_RECEIPT_CLOCK")
    _integer(value["counter"], 1, 2**64 - 1, "SUCCESS_RECEIPT_COUNTER")
    for name in ("previous_digest", "handoff_sha256", "cleanup_final_sha256",
                 "capture_head_sha256"):
        _digest(value[name], "SUCCESS_RECEIPT_DIGEST")
        _require(value[name] != ZERO_DIGEST, "SUCCESS_RECEIPT_DIGEST")
    return copy.deepcopy(value)


def make_handoff(payload):
    checked = _validate_handoff_payload(payload)
    _require(checked["success_latch"] is False
        and checked["final_carrier_ready"] is False
        and checked["all_stage_slots_final_or_empty"] is False,
        "OFFLINE_SUCCESS_HANDOFF_FORBIDDEN")
    return canonical_bytes({"schema": HANDOFF_SCHEMA, "payload": checked},
        maximum=MAX_H_BYTES)


def verify_handoff(raw, *, expected):
    """Bind one external handoff without treating it as field evidence."""
    value = _bounded_object(raw, HANDOFF_SCHEMA, MAX_H_BYTES)
    observed = _validate_handoff_payload(value["payload"])
    checked = _validate_handoff_payload(expected)
    _require(_same(observed, checked), "HANDOFF_EXPECTED_BINDING")
    return {
        **value,
        "shape_verified": True,
        "fixture_qualification": "NOT_RUN",
        "durability_proven": False,
        "field_fact_proven": False,
        "live_proven": False,
    }


def make_cleanup_final(payload):
    checked = _validate_cleanup_final_payload(payload)
    _require(checked["success_eligible"] is False,
        "OFFLINE_SUCCESS_CLEANUP_FORBIDDEN")
    return canonical_bytes({"schema": CLEANUP_FINAL_SCHEMA, "payload": checked},
        maximum=MAX_CLEANUP_FINAL_BYTES)


def verify_cleanup_final(raw, *, expected):
    """Bind one external cleanup frame without treating it as success proof."""
    value = _bounded_object(raw, CLEANUP_FINAL_SCHEMA, MAX_CLEANUP_FINAL_BYTES)
    observed = _validate_cleanup_final_payload(value["payload"])
    checked = _validate_cleanup_final_payload(expected)
    _require(_same(observed, checked), "CLEANUP_FINAL_EXPECTED_BINDING")
    return {
        **value,
        "shape_verified": True,
        "fixture_qualification": "NOT_RUN",
        "durability_proven": False,
        "native_execution_proven": False,
        "live_proven": False,
    }


def make_success_receipt(payload):
    """Refuse to manufacture the native process's terminal success evidence."""
    del payload
    raise NamespaceDeliveryContractError(
        "Q2_NAMESPACE_DELIVERY_OFFLINE_SUCCESS_RECEIPT_FORBIDDEN")


def verify_success_receipt(raw, *, expected):
    """Verify one external binary receipt without claiming native or live proof.

    Exact caller expectations bind every mutable field to the current external
    capture chain.  Matching bytes establish only binary structure and equality;
    this offline function cannot establish provenance, execution, durability,
    EOF/wait closure, or ``FIXTURE_LIVE_REFERENCE_MATCHED``.
    """
    checked = _validate_success_receipt_expected(expected)
    _require(type(raw) is bytes and len(raw) == SUCCESS_RECEIPT_SIZE,
        "SUCCESS_RECEIPT_SIZE")
    _require(raw[:8] == SUCCESS_RECEIPT_MAGIC, "SUCCESS_RECEIPT_MAGIC")
    _require(raw[184:192] == b"\x00" * 8, "SUCCESS_RECEIPT_RESERVED")
    _require(raw[SUCCESS_RECEIPT_HASH_OFFSET:] == hashlib.sha256(
        raw[:SUCCESS_RECEIPT_HASH_OFFSET]).digest(), "SUCCESS_RECEIPT_SHA256")

    observed = {
        "version": int.from_bytes(raw[8:16], "little"),
        "process_cpu_ns": int.from_bytes(raw[16:24], "little"),
        "boottime_ns": int.from_bytes(raw[24:32], "little"),
        "monotonic_ns": int.from_bytes(raw[32:40], "little"),
        "realtime_ns": int.from_bytes(raw[40:48], "little"),
        "counter": int.from_bytes(raw[48:56], "little"),
        "previous_digest": raw[56:88].hex(),
        "handoff_sha256": raw[88:120].hex(),
        "cleanup_final_sha256": raw[120:152].hex(),
        "capture_head_sha256": raw[152:184].hex(),
    }
    _require(observed["version"] == SUCCESS_RECEIPT_VERSION,
        "SUCCESS_RECEIPT_VERSION")
    _require(_same(observed, checked), "SUCCESS_RECEIPT_EXPECTED_BINDING")
    return {
        "schema": SUCCESS_RECEIPT_SCHEMA,
        "bytes": SUCCESS_RECEIPT_SIZE,
        "receipt_sha256": sha256(raw),
        "fields": observed,
        "binary_structure_verified": True,
        "fixture_qualification": "NOT_RUN",
        "source_bytes_proven": False,
        "build_proven": False,
        "native_execution_proven": False,
        "durability_proven": False,
        "live_proven": False,
    }
