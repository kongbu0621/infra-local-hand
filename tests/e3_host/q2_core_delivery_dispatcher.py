"""Strict field dispatcher for the closed Q2 core acceptance delivery.

The module is a field blob: it is deliberately self-contained and must not
import another D helper.  ``dispatch`` owns all ordering and validation.  The
``FieldEffects`` object owns operating-system effects and is injected into the
dispatcher so the contract can be tested without substituting modeled case
results for field evidence.

Current-guest admission, preparation capacity collectors and complete shared-pool
accounting remain fail-closed. Component tests are not original field evidence.
"""
from __future__ import annotations

import base64
import csv
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import resource
import selectors
import signal
import stat
import struct
import subprocess
import time
import zipfile


class DispatchError(RuntimeError):
    """A stable fail-closed dispatcher rejection."""


def _require(condition, code):
    if not condition:
        raise DispatchError(code)


def _pairs(items):
    result = {}
    for key, value in items:
        _require(type(key) is str and key not in result, "CORE_DISPATCH_JSON_DUPLICATE")
        result[key] = value
    return result


def _nonfinite(_value):
    raise DispatchError("CORE_DISPATCH_JSON_NONFINITE")


def _shape(value, depth=0, count=None):
    count = [0] if count is None else count
    count[0] += 1
    _require(depth <= 32 and count[0] <= 262144, "CORE_DISPATCH_JSON_COMPLEXITY")
    _require(not isinstance(value, float), "CORE_DISPATCH_JSON_FLOAT")
    if isinstance(value, dict):
        _require(all(type(key) is str for key in value), "CORE_DISPATCH_JSON_KEY")
        for item in value.values():
            _shape(item, depth + 1, count)
    elif isinstance(value, list):
        for item in value:
            _shape(item, depth + 1, count)
    else:
        _require(value is None or type(value) in (str, int, bool),
                 "CORE_DISPATCH_JSON_VALUE")
        if type(value) is int:
            _require(-(2**63) <= value < 2**63, "CORE_DISPATCH_JSON_INTEGER")
    return value


def canonical(value, *, newline=False, limit=None):
    _shape(value)
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as error:
        raise DispatchError("CORE_DISPATCH_JSON_ENCODE") from error
    if newline:
        raw += b"\n"
    if limit is not None:
        _require(0 < len(raw) <= limit, "CORE_DISPATCH_JSON_LIMIT")
    return raw


def document(raw, *, limit, newline=True):
    _require(type(raw) is bytes and 0 < len(raw) <= limit,
             "CORE_DISPATCH_JSON_LIMIT")
    _require(raw.endswith(b"\n") == newline and
             (not newline or not raw.endswith(b"\n\n")),
             "CORE_DISPATCH_JSON_NEWLINE")
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                           parse_constant=_nonfinite)
    except DispatchError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DispatchError("CORE_DISPATCH_JSON_DECODE") from error
    _shape(value)
    _require(canonical(value, newline=newline) == raw,
             "CORE_DISPATCH_JSON_CANONICAL")
    return value


def _exact(value, fields, code):
    _require(type(value) is dict and set(value) == set(fields), code)
    return value


def _integer(value, low=0, high=2**63 - 1, code="CORE_DISPATCH_INTEGER"):
    _require(type(value) is int and low <= value <= high, code)
    return value


def _digest(value, code="CORE_DISPATCH_DIGEST"):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             code)
    return value


def _commit(value, code="CORE_DISPATCH_COMMIT"):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None,
             code)
    return value


def _path(value, code="CORE_DISPATCH_PATH"):
    _require(type(value) is str and value.isascii() and 0 < len(value) <= 4096
             and re.fullmatch(r"[A-Za-z0-9._/-]+", value) is not None
             and "//" not in value and "\\" not in value and "\0" not in value,
             code)
    parsed = PurePosixPath(value)
    _require(not parsed.is_absolute() and parsed.as_posix() == value
             and all(part not in ("", ".", "..") for part in parsed.parts), code)
    return value


def _sha(raw):
    _require(type(raw) is bytes or (isinstance(raw, memoryview) and raw.readonly),
             "CORE_DISPATCH_BYTES")
    return hashlib.sha256(raw).hexdigest()


SCOPE = "LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1"
SESSION = "lhqcore-20261003a"
RULE = {
    "commit": "10d2a5c827964989f41ca6e8eeac3d44de6d0f04",
    "source_sha256": "c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5",
}
BASELINE = {
    "commit": "74366b3fe41e675b1aa2d677228714a5606c275c",
    "tree": "7df4fd0c876df13af4ec73c6f910272a72d7ea4d",
    "documents_sha256": {
        "docs/a2-execution/Q2_CORE_LIVE_INPUT_REVIEW_20261003.md":
            "39853b72755e4737b5329856691e1f616cfd2ffdf403d1c06cbeccff89686f1c",
        "docs/a2-execution/q2-core-acceptance-delivery/ARCHITECTURE.md":
            "7599870a39f04a68a84992dbc2f3035ba202963fc1cc688914f9b5fa596b54ab",
        "docs/a2-execution/q2-core-acceptance-delivery/IMPLEMENTATION_PLAN.md":
            "dd128597f90cfdf38d4a9f716fa53fd12acbb12cbc86c261f3f9c760477938c1",
        "docs/a2-execution/q2-core-acceptance-delivery/REQUIREMENTS.md":
            "8ef192452302ae2c2c55c38dd6889a0a62265404f4baa823be097f0a2524ce76",
    },
}
OWNER_DECISION = {
    "event": "LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01",
    "record_path": "docs/governance/Q2_CORE_ACCEPTANCE_DELIVERY_OWNER_DECISION.md",
    "record_sha256": "e6a810ac5a76c903c687b6487ac2a4b08e02022fcf90927f7a34993dedb695cb",
}
CLOSURE = {
    "commit": "a8dd077392ebb656770c8f94ca3b051e93fc296d",
    "tree": "b0d651ea5cbc2c408bb43ce6f3cdc5becd5170c6",
}
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
CANDIDATE = {
    "commit": "4b6e4a7c403362358192086b88679e1326dcb2e1",
    "tree": "4d4349580c9f4b67cc26f601126849c2bc8d76a4",
}
WHEEL = {
    "basename": "infra_local_hand-0.2.0a1-py3-none-any.whl",
    "bytes": 288375,
    "sha256": "ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9",
    "payload_digest": "b4d094a9f70c308c63870c9fbf273b6b0646ad211d6f61a79901f52e67cf2e23",
}
PROJECTION = {
    "basename": ".local-hand-source-projection.json",
    "bytes": 11811,
    "sha256": "55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d",
    "file_count": 89,
}

INSTALL_BASENAME = "local-hand-core-acceptance-20261003a"
STAGING_BASENAME = ".local-hand-core-acceptance-20261003a.staging"
PREPARATION_HELPERS = (
    "q2_prepare_contract", "q2_prepare_driver", "q2_prepare_assembly",
)
WHEEL_PACKAGES = ("local_hand", "local_hand_connect", "local_hand_jobs", "local_hand_mcp")
WHEEL_METADATA = "local_hand/_build_metadata.json"
PROJECTION_HARNESS = frozenset({
    "tests/e3_host/q2_fixture_check.py",
    "tests/e3_host/q2_launcher.py",
    "tests/e3_host/q2_prepare_assembly.py",
    "tests/e3_host/q2_prepare_driver.py",
    "tests/e3_host/q2_prepare_run.py",
    "tests/e3_host/q2_resident.py",
    "tests/e3_host/q2_supervisor.py",
    "tests/e3_host/q4_cancel_case.py",
    "tests/e3_host/q4_cancel_runtime.py",
    "tests/e3_host/q4_h11_recovery.py",
})
PROJECTION_REQUIRED = PROJECTION_HARNESS | frozenset({
    "tools/admin/local_hand_quota_observer/q2_entry.py",
    "tools/admin/local_hand_system_manager/__init__.py",
    "tools/admin/local_hand_system_manager/server.py",
    "tools/local_hand/__init__.py",
    "tools/local_hand/provenance.py",
    "tools/local_hand_connect/__init__.py",
    "tools/local_hand_jobs/__init__.py",
    "tools/local_hand_mcp/__init__.py",
})

# The v2 package now carries these private approved components. They remain
# unbound to field admission until current-guest cross-checks are implemented.
# The self-contained component parser below validates static relations; that
# must not promote historical inputs into current observed facts.
UNBOUND_APPROVED_INPUTS = (
    "admission.policy_expected_entities",
    "admission.historical_capacity_obligations",
    "preparation.retained_paths_and_domains",
)
UNIMPLEMENTED_FIELD_EFFECTS = (
    "admission.current_guest_collector",
    "installation.shared_pool_peak_accounting",
    "installation.deadline_guarding",
    "installation.program_execution_binding",
    "preparation.current_capacity_collectors",
    "evidence.usage_and_peak_accounting",
)

OUTPUT_MAGIC = b"LHCOUT1\n"
PACKAGE_MAGIC = b"LHCFP1\n"
CONTEXT_SCHEMA = "local-hand-q2-core-bootstrap-context/v1"
OUTPUT_SCHEMA = "local-hand-q2-core-output-package/v1"
REMOTE_SCHEMA = "local-hand-q2-core-remote-result/v1"
INTENT_SCHEMA = "local-hand-q2-core-case-intent/v1"
PLAN_SCHEMA = "local-hand-q2-core-case-plan/v1"
RECEIPT_SCHEMA = "local-hand-q2-core-phase-receipt/v1"
VERDICT_SCHEMA = "local-hand-q2-core-case-verdict/v1"
PROOF_SCHEMA = "local-hand-q2-core-h11-recovery-proof/v1"
CONSUMPTION_SCHEMA = "local-hand-q2-core-carrier-consumption/v2"
PACKAGE_SCHEMA = "local-hand-q2-core-field-package/v3"
HELLO_SCHEMA = "local-hand-q2-core-carrier-hello/v2"
SESSION_SCHEMA = "local-hand-q2-core-dispatch-session/v2"
APPROVED_INPUTS_PATH = "private/approved-inputs.json"
APPROVED_INPUTS_LIMIT = 1048576
REMOTE_ALIASES = {"shell": "/bin/bash", "sudo": "/usr/bin/sudo", "env": "/usr/bin/env",
                  "systemd_run": "/usr/bin/systemd-run", "python": "/usr/bin/python3"}
PROGRAM_FIELDS = {"path", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes", "sha256"}
ADMISSION_COMPONENTS = (
    "source_relation", "policy_basis", "historical_capacity_obligations",
    "retained_preparation", "reconciliation",
)

NS = 1_000_000_000
REMOTE_FINAL_RESERVE_NS = 45 * NS
CASE_GATE_NS = 315 * NS
PREPARATION_NS = 150 * NS
OWNER_NS = 120 * NS
MANIFEST_LIMIT = 1_048_576
MEMBER_LIMIT = 16_777_216
MEMBER_COUNT_LIMIT = 4096
FRAME_LIMIT = 58_716_144
STDERR_LIMIT = 4_194_304
CASE_BYTES_LIMIT = 16_777_216

LIMITS = {
    "carrier_seconds": 900, "remote_unit_seconds": 800,
    "guest_duration_cap_seconds": 750, "preparation_seconds": 150,
    "owner_seconds": 120, "case_gate_seconds": 315,
    "hello_frame_bytes": 4112, "bind_frame_bytes": 4112,
    "package_bytes": 33550320, "carrier_input_bytes": 33554432,
    "output_package_bytes": FRAME_LIMIT, "carrier_stderr_bytes": STDERR_LIMIT,
    "carrier_output_bytes": 62914560, "host_capture_bytes": 67108864,
    "host_capture_inodes": 16, "carrier_cpu_seconds": 800,
    "carrier_memory_bytes": 1073741824, "carrier_pids": 128,
    "carrier_audit_bytes": 8388608, "carrier_audit_inodes": 512,
    "shared_bytes": 67108864, "shared_inodes": 4096,
    "case_physical_bytes": 37748736, "case_physical_inodes": 2944,
    "all_case_physical_bytes": 113246208, "all_case_physical_inodes": 8832,
    "case_admission_bytes": 71303168, "case_admission_inodes": 3968,
    "all_case_admission_bytes": 213909504, "all_case_admission_inodes": 11904,
    "all_case_cpu_seconds": 1290, "total_cpu_seconds": 2090,
    "all_case_output_bytes": 50331648, "peak_memory_bytes": 2751463424,
    "peak_pids": 1160, "job_units": 15, "controller_units": 6,
    "quota_query_units": 5, "dynamic_quota_units": 15, "native_children": 16,
    "total_guest_physical_bytes": 188743680,
    "total_guest_physical_inodes": 13440,
    "total_guest_admission_bytes": 289406976,
    "total_guest_admission_inodes": 16512,
}
OUTPUT_LIMITS = {
    "frame_bytes": FRAME_LIMIT, "manifest_bytes": MANIFEST_LIMIT,
    "members": MEMBER_COUNT_LIMIT, "member_bytes": MEMBER_LIMIT,
    "stderr_bytes": STDERR_LIMIT,
}
PACKAGE_LIMITS = {
    "package_bytes": 33550320, "manifest_bytes": 1048576, "members": 4096,
    "member_bytes": 16777216, "shared_allocated_bytes": 67108864,
    "shared_entries": 4096, "carrier_audit_bytes": 8388608,
    "carrier_audit_inodes": 512, "carrier_output_bytes": 62914560,
}

DIRECTORY_ROLES = (
    "reservation", "state", "authority", "journal", "capture", "declarations",
    "session", "control", "profile_work", "profile_evidence", "profile_temporary",
    "store_parent",
)
ROOT_REFS = (
    ("work-a", "a", "work"), ("evidence-a", "a", "evidence"),
    ("temporary-a", "a", "temporary"), ("work-b", "b", "work"),
    ("evidence-b", "b", "evidence"), ("temporary-b", "b", "temporary"),
    ("retained_store", "store", "retained_store"),
)


def _unit(execution_id, suffix=""):
    return "lhj-" + hashlib.sha256((execution_id + suffix).encode("utf-8")).hexdigest() + ".service"


def _phase_units(operation_id, phases):
    result = []
    for phase in phases:
        execution = "job-" + operation_id + "-" + phase
        result.append({
            "phase": phase,
            "bootstrap_unit": _unit(execution, ":bootstrap"),
            "helper_unit": _unit(execution),
            "result_reader_unit": _unit(execution, ":result_reader"),
        })
    return result


CASES = (
    {"index": 1, "case_id": "c01-h01-normal", "kind": "H01_NORMAL",
     "predecessor": None, "preparation_id": "lhqc01h01normal",
     "operation_id": "b6638120-ed28-4ed1-b603-a153fab1c93d",
     "controller_prefix": "lhqcore20261003a-c01", "project_ids": list(range(12101, 12108)),
     "phases": ["preflight", "business", "evidence"]},
    {"index": 2, "case_id": "c02-q4-cancel", "kind": "Q4_HELPER_RUNNING_CANCEL_SUBSET",
     "predecessor": "c01-h01-normal", "preparation_id": "lhqc02q4cancel",
     "operation_id": "ade1b42f-f03d-48dc-b690-e588b44289f6",
     "controller_prefix": "lhqcore20261003a-c02", "project_ids": list(range(12108, 12115)),
     "phases": ["preflight"]},
    {"index": 3, "case_id": "c03-h11-recovery", "kind": "H11_SAME_LEDGER_RECOVERY",
     "predecessor": "c02-q4-cancel", "preparation_id": "lhqc03h11recovery",
     "operation_id": "4b035797-229a-4cdc-8eca-8195869b7ac9",
     "controller_prefix": "lhqcore20261003a-c03", "project_ids": list(range(12115, 12122)),
     "phases": ["preflight"]},
)


def _budget(phases):
    return {
        "operation": {"wall_seconds": 72, "terminate_grace_seconds": 1,
                      "cpu_seconds": 30, "memory_bytes": 67108864, "processes": 8,
                      "temporary_bytes": 1048576, "nas_bytes": 0, "log_bytes": 98304,
                      "reservation_bytes": 8388608},
        "phases": [{"phase": phase, "wall_seconds": 24, "cpu_seconds": 10,
                    "bootstrap_cpu_seconds": 3, "helper_cpu_seconds": 4,
                    "result_reader_cpu_seconds": 3} for phase in phases],
        "controller": {"memory_bytes": 536870912, "tasks_max": 64,
                       "cpu_quota_per_sec_usec": 1000000, "memory_swap_max": 0},
        "ordinary": {"memory_bytes": 268435456, "tasks_max": 32,
                     "cpu_quota_per_sec_usec": 1000000, "memory_swap_max": 0},
        "retained_ordinary": {"memory_bytes": 268435456, "tasks_max": 64,
                              "cpu_quota_per_sec_usec": 1000000, "memory_swap_max": 0},
        "target": {"memory_bytes": 268435456, "tasks_max": 32,
                   "cpu_quota_per_sec_usec": 1000000, "runtime_seconds": 85,
                   "stop_seconds": 1, "storage_bytes": 1048576, "storage_inodes": 64},
        "supervisor": {"memory_bytes": 67108864, "tasks_max": 32,
                       "cpu_quota_per_sec_usec": 1000000, "runtime_seconds": 100,
                       "stop_seconds": 1, "storage_bytes": 8388608, "storage_inodes": 64},
        "owner": {"wall_seconds": 120, "cpu_seconds": 120, "memory_bytes": 536870912,
                  "tasks_max": 64, "storage_bytes": 8388608, "storage_inodes": 64,
                  "output_bytes": 69632},
        "management": {
            "cpu_seconds": 400, "memory_bytes": 1610612736, "pids": 1024,
            "output_bytes": 16777216, "storage_bytes": 33554432,
            "storage_inodes": 1024, "manager_wire_bytes": 4194304,
            "receive_seconds": 1, "stop_seconds": 1,
            "stages": [
                {"stage": "collector", "memory_bytes": 67108864, "tasks_max": 8,
                 "cpu_seconds": 2, "output_bytes": 32768, "runtime_seconds": 8},
                {"stage": "admission", "memory_bytes": 67108864, "tasks_max": 8,
                 "cpu_seconds": 2, "output_bytes": 32768, "runtime_seconds": 7},
                {"stage": "query", "memory_bytes": 67108864, "tasks_max": 8,
                 "cpu_seconds": 2, "output_bytes": 32768, "runtime_seconds": 5},
            ],
        },
        "durable": {"state_bytes": 8388608, "state_inodes": 1536,
                    "journal_bytes": 1048576, "journal_inodes": 128,
                    "capture_declarations_bytes": 20971520,
                    "capture_declarations_inodes": 384},
        "roots": {"count": 7, "hard_bytes_each": 1048576,
                  "hard_inodes_each": 128},
    }


def _identity(case, *, full=False):
    seed = (SESSION + ":" + case["case_id"]).encode("ascii")
    result = {
        "id": hashlib.sha256(seed + b":identity").hexdigest()[:32],
        "authority_id": SESSION + "-" + case["case_id"] + "-authority",
        "node_id": SESSION + "-guest",
        "install_uuid": "2ba06c6f-d3e5-4e36-a41f-d5991cdd7232",
        "deployment_epoch": 1, "generation": 1,
        "operation_id": case["operation_id"],
        "profile_ref": SESSION + "-" + case["case_id"] + "-profile",
        "principal_id": "q2-synthetic-" + SESSION + "-" + case["case_id"],
        "epoch": hashlib.sha256(seed + b":epoch").hexdigest()[:32],
        "slot_generation": hashlib.sha256(seed + b":slot-generation").hexdigest()[:32],
        "session": hashlib.sha256(seed + b":session").hexdigest(),
        "ledger_id": SESSION + "-" + case["case_id"] + "-ledger",
    }
    if full:
        result.update(authority_digest=None, manifest_digest=None, expires_at=None)
    return result


def _planned_directories(case):
    ordinary = {"state", "authority", "profile_work", "profile_evidence",
                "profile_temporary", "store_parent"}
    root_755 = {"control", "session", "declarations"}
    parent_for = {
        "reservation": "state", "state": "state", "authority": "state",
        "journal": "journal", "capture": "evidence", "declarations": "evidence",
        "session": "state", "control": "state", "profile_work": "quota",
        "profile_evidence": "quota", "profile_temporary": "quota", "store_parent": "quota",
    }
    return [{"role": role, "parent_role": parent_for[role],
             "relative_path": SESSION + "/" + case["case_id"] + "/" + role.replace("_", "-"),
             "owner": "ordinary" if role in ordinary else "root",
             "mode": 448 if role in ordinary or role not in root_755 else 493}
            for role in DIRECTORY_ROLES]


def _planned_roots(case):
    base = SESSION + "/" + case["case_id"] + "/"
    paths = ("profile-work/work-a", "profile-evidence/evidence-a",
             "profile-temporary/temporary-a", "profile-work/work-b",
             "profile-evidence/evidence-b", "profile-temporary/temporary-b",
             "store-parent/retained_store")
    return [{"ref": ref, "slot": slot, "role": role, "path": base + path,
             "project_id": case["project_ids"][index], "hard_bytes": 1048576,
             "inode_hard_limit": 128}
            for index, ((ref, slot, role), path) in enumerate(zip(ROOT_REFS, paths, strict=True))]


def build_intent(case):
    """Build A's deterministic pre-mutation intent."""
    _require(case in CASES, "CORE_DISPATCH_CASE")
    identity = _identity(case)
    directories = _planned_directories(case)
    roots = _planned_roots(case)
    budgets = _budget(case["phases"])
    preimage = {
        "schema": "local-hand-q2-core-preparation-input/v1", "session_id": SESSION,
        "index": case["index"], "case_id": case["case_id"],
        "preparation_id": case["preparation_id"], "identity": identity,
        "planned_directories": directories, "planned_roots": roots, "budgets": budgets,
    }
    return {
        "schema": INTENT_SCHEMA, "session_id": SESSION, "index": case["index"],
        "case_id": case["case_id"], "kind": case["kind"],
        "predecessor": case["predecessor"], "preparation_id": case["preparation_id"],
        "identity": identity, "operation_id": case["operation_id"],
        "controller_prefix": case["controller_prefix"],
        "project_ids": list(case["project_ids"]), "directory_roles": list(DIRECTORY_ROLES),
        "planned_directories": directories, "planned_roots": roots,
        "preparation_input_sha256": _sha(canonical(preimage)),
        "phases": list(case["phases"]), "budgets": budgets, "state": "INTENT_RECORDED",
    }


INTENT_FIELDS = (
    "schema", "session_id", "index", "case_id", "kind", "predecessor",
    "preparation_id", "identity", "operation_id", "controller_prefix", "project_ids",
    "directory_roles", "planned_directories", "planned_roots",
    "preparation_input_sha256", "phases", "budgets", "state",
)
PLAN_FIELDS = (
    "schema", "session_id", "index", "case_id", "kind", "predecessor",
    "preparation_id", "identity", "principal", "authority_path", "ledger_path",
    "request", "operation_id", "roots", "controllers", "system_geometry", "phases",
    "empty_ledger_expectation", "deadlines", "budgets",
)


def validate_plan(case, intent, plan, deadlines):
    """Validate all D-owned/static plan bindings before owner or submit."""
    _exact(plan, PLAN_FIELDS, "CORE_DISPATCH_PLAN_FIELDS")
    expected = {key: intent[key] for key in
                ("session_id", "index", "case_id", "kind", "predecessor",
                 "preparation_id", "operation_id", "budgets")}
    _require(plan["schema"] == PLAN_SCHEMA and all(plan[key] == value for key, value in expected.items()),
             "CORE_DISPATCH_PLAN_BINDING")
    identity = _exact(plan["identity"], (
        "id", "authority_id", "node_id", "install_uuid", "deployment_epoch", "generation",
        "operation_id", "profile_ref", "principal_id", "epoch", "authority_digest",
        "manifest_digest", "slot_generation", "expires_at", "session", "ledger_id",
    ), "CORE_DISPATCH_PLAN_IDENTITY_FIELDS")
    logical = intent["identity"]
    _require(all(identity[key] == value for key, value in logical.items()),
             "CORE_DISPATCH_PLAN_IDENTITY")
    _digest(identity["authority_digest"], "CORE_DISPATCH_PLAN_AUTHORITY")
    _digest(identity["manifest_digest"], "CORE_DISPATCH_PLAN_MANIFEST")
    _integer(identity["expires_at"], 1, code="CORE_DISPATCH_PLAN_EXPIRY")
    scopes = ["lh:submit", "lh:read", "lh:evidence"] + (["lh:cancel"] if case["index"] == 2 else [])
    _require(plan["principal"] == {"principal_id": identity["principal_id"], "scopes": scopes},
             "CORE_DISPATCH_PLAN_PRINCIPAL")
    _require(plan["authority_path"].endswith("/authority/authority.json")
             and plan["ledger_path"].endswith("/state/jobs.sqlite"),
             "CORE_DISPATCH_PLAN_PATH")
    request = _exact(plan["request"], (
        "schema_version", "operation_id", "kind", "profile_ref", "expected", "inputs",
        "expires_at", "request_digest",
    ), "CORE_DISPATCH_PLAN_REQUEST_FIELDS")
    _require(request["schema_version"] == "lh-job-v1"
             and request["operation_id"] == case["operation_id"]
             and request["kind"] == "host.inspect"
             and request["profile_ref"] == identity["profile_ref"]
             and request["inputs"] == {}
             and request["expires_at"] == identity["expires_at"],
             "CORE_DISPATCH_PLAN_REQUEST")
    _digest(request["request_digest"], "CORE_DISPATCH_PLAN_REQUEST")
    _exact(request["expected"], (
        "node_id", "install_uuid", "deployment_epoch", "profile_digest", "policy_digest",
        "registry_digest",
    ), "CORE_DISPATCH_PLAN_EXPECTED")
    for key in ("profile_digest", "policy_digest", "registry_digest"):
        _digest(request["expected"][key], "CORE_DISPATCH_PLAN_EXPECTED")
    _require(request["expected"]["node_id"] == identity["node_id"]
             and request["expected"]["install_uuid"] == identity["install_uuid"]
             and request["expected"]["deployment_epoch"] == 1,
             "CORE_DISPATCH_PLAN_EXPECTED")
    _require(type(plan["roots"]) is list and len(plan["roots"]) == 7,
             "CORE_DISPATCH_PLAN_ROOTS")
    for wrapper, planned in zip(plan["roots"], intent["planned_roots"], strict=True):
        _exact(wrapper, ("ref", "slot", "planned", "observed"),
               "CORE_DISPATCH_PLAN_ROOT_FIELDS")
        _require(wrapper["ref"] == planned["ref"] and wrapper["slot"] == planned["slot"]
                 and wrapper["planned"] == planned, "CORE_DISPATCH_PLAN_ROOT")
        observed = _exact(wrapper["observed"], (
            "path", "role", "device", "inode", "uid", "gid", "mode", "filesystem",
            "filesystem_uuid", "project_id", "xflags", "hard_bytes", "accounting",
            "enforcement", "identity_unchanged", "hard_inodes",
        ), "CORE_DISPATCH_PLAN_OBSERVED_FIELDS")
        _require(observed["path"] == planned["path"] and observed["role"] == planned["role"]
                 and observed["project_id"] == planned["project_id"]
                 and observed["hard_bytes"] == planned["hard_bytes"]
                 and observed["hard_inodes"] == planned["inode_hard_limit"]
                 and observed["mode"] == 16832 and observed["accounting"] is True
                 and observed["enforcement"] is True and observed["identity_unchanged"] is True,
                 "CORE_DISPATCH_PLAN_OBSERVED")
        for key in ("device", "inode", "uid", "gid", "project_id", "xflags"):
            _integer(observed[key], 1 if key in ("inode", "project_id") else 0,
                     code="CORE_DISPATCH_PLAN_OBSERVED")
    _exact(plan["controllers"], (
        "target", "supervisor", "controller_parent", "query_parent", "management_parent",
        "supervisor_parent", "target_storage_bytes", "target_storage_inodes",
        "supervisor_storage_bytes", "supervisor_storage_inodes",
    ), "CORE_DISPATCH_PLAN_CONTROLLERS")
    _require(plan["controllers"]["target_storage_bytes"] == 1048576
             and plan["controllers"]["target_storage_inodes"] == 64
             and plan["controllers"]["supervisor_storage_bytes"] == 8388608
             and plan["controllers"]["supervisor_storage_inodes"] == 64,
             "CORE_DISPATCH_PLAN_CONTROLLER_BUDGET")
    expected_units = _phase_units(case["operation_id"], case["phases"])
    _require(plan["phases"] == expected_units, "CORE_DISPATCH_PLAN_PHASES")
    if case["index"] == 2:
        _require(plan["system_geometry"] is None, "CORE_DISPATCH_PLAN_GEOMETRY")
    else:
        geometry = _exact(plan["system_geometry"], (
            "schema", "controller_parent", "ordinary_parent", "retained_ordinary_parent",
        ), "CORE_DISPATCH_PLAN_GEOMETRY")
        _require(geometry["schema"] == "local-hand-q2-system-geometry/v1",
                 "CORE_DISPATCH_PLAN_GEOMETRY")
    expectation = _exact(plan["empty_ledger_expectation"], (
        "ledger_path", "authority_id", "ledger_id", "expected_operations",
        "expected_events", "expected_leases", "expected_sidecars",
    ), "CORE_DISPATCH_PLAN_EMPTY")
    _require(expectation == {"ledger_path": plan["ledger_path"],
                             "authority_id": identity["authority_id"],
                             "ledger_id": identity["ledger_id"],
                             "expected_operations": 0, "expected_events": 0,
                             "expected_leases": 0, "expected_sidecars": []},
             "CORE_DISPATCH_PLAN_EMPTY")
    _require(plan["deadlines"] == deadlines, "CORE_DISPATCH_PLAN_DEADLINE")
    return plan


COMMON = (
    ("intent.json", "intent", 384),
    ("reservation/case-plan.json", "plan", 384),
    ("reservation/preparation-plan.json", "preparation-plan", 384),
    ("reservation/preparation-result.json", "preparation-result", 384),
    ("reservation/empty-ledger-gate.json", "empty-ledger-gate", 384),
    ("owner_declarations/fixture-check.json", "fixture-check", 384),
    ("authority/authority.json", "authority", 384),
    ("reservation/case-verdict.json", "verdict", 384),
)


def _h01_special(seal_id):
    _require(type(seal_id) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        seal_id) is not None, "CORE_DISPATCH_H01_SEAL_ID")
    rows = []
    for phase in ("preflight", "business", "evidence"):
        rows.extend(((phase + "/observer.json", "observer-config", 384),
                     ("reservation/phase-" + phase + "-receipt.json", "phase-receipt", 384),
                     ("launcher_output/phase-" + phase + ".json", "phase-result", 384)))
    rows.extend((
        ("launcher_output/reservation.json", "launcher-reservation", 384),
        ("launcher_output/gateway.json", "gateway", 384),
        ("launcher_output/result.json", "launcher-result", 384),
        ("launcher_output/resident.stdout", "stdout", 384),
        ("launcher_output/resident.stderr", "stderr", 384),
        ("launcher_output/capture.json", "wait", 384),
        ("records/ledger-export.json", "ledger", 384),
        ("business/result-03c94c57c840717302854a3f.json", "result", 384),
        ("business-evidence/" + seal_id + "/evidence.zip", "business-evidence-archive", 384),
        ("business-evidence/" + seal_id + "/manifest.json", "business-evidence-manifest", 384),
        ("business-evidence/" + seal_id + "/seal.json", "business-evidence-seal", 384),
        ("supervisor_output/stop.json", "stop", 384),
        ("owner_output/stop.json", "stop", 384),
        ("supervisor_output/seal.json", "control-seal", 384),
        ("owner_output/seal.json", "control-seal", 384),
    ))
    return tuple(rows)


Q4_SPECIAL = (
    ("preflight/observer.json", "observer-config", 384),
    ("reservation/phase-preflight-receipt.json", "phase-receipt", 384),
    ("launcher_output/reservation.json", "launcher-reservation", 384),
    ("launcher_output/phase.json", "phase-result", 384),
    ("launcher_output/result.json", "launcher-result", 384),
    ("launcher_output/resident.stdout", "stdout", 384),
    ("launcher_output/resident.stderr", "stderr", 384),
    ("launcher_output/capture.json", "wait", 384),
    ("records/ledger-export.json", "ledger", 384),
    ("supervisor_output/stop.json", "stop", 384),
    ("owner_output/stop.json", "stop", 384),
    ("supervisor_output/seal.json", "control-seal", 384),
    ("owner_output/seal.json", "control-seal", 384),
)
H11_SPECIAL = (
    ("preflight/observer.json", "observer-config", 384),
    ("reservation/phase-preflight-receipt.json", "phase-receipt", 384),
    ("launcher_output/reservation.json", "launcher-reservation", 384),
    ("launcher_declarations/recovery-resident.json", "recovery-plan", 420),
    ("launcher_output/recovery.json", "recovery-summary", 384),
    ("launcher_output/origin-resident.stdout", "stdout", 384),
    ("launcher_output/origin-resident.stderr", "stderr", 384),
    ("launcher_output/origin-capture.json", "origin-capture", 384),
    ("launcher_output/gateway.json", "gateway", 384),
    ("launcher_output/result.json", "launcher-result", 384),
    ("launcher_output/resident.stdout", "stdout", 384),
    ("launcher_output/resident.stderr", "stderr", 384),
    ("launcher_output/capture.json", "wait", 384),
    ("reservation/h11-recovery-proof.json", "recovery-proof", 384),
    ("supervisor_output/stop.json", "stop", 384),
    ("owner_output/stop.json", "stop", 384),
    ("supervisor_output/seal.json", "control-seal", 384),
    ("owner_output/seal.json", "control-seal", 384),
)


def required_paths(case, *, seal_id=None):
    special = _h01_special(seal_id) if case["index"] == 1 else (
        Q4_SPECIAL if case["index"] == 2 else H11_SPECIAL)
    prefix = "cases/" + case["case_id"] + "/"
    return tuple((prefix + path, role, mode) for path, role, mode in COMMON + special)


def phase_source_specs(case, phase):
    prefix = "cases/" + case["case_id"] + "/"
    preparation = (prefix + "reservation/preparation-result.json", "preparation-result")
    observer = (prefix + phase + "/observer.json", "observer-config")
    reservation = (prefix + "launcher_output/reservation.json", "launcher-reservation")
    launcher = (prefix + "launcher_output/result.json", "launcher-result")
    if case["index"] == 1:
        rows = (preparation, observer,
                (prefix + "launcher_output/phase-" + phase + ".json", "phase-result"),
                launcher, reservation)
    elif case["index"] == 2:
        rows = (preparation, observer,
                (prefix + "launcher_output/phase.json", "phase-result"), launcher, reservation)
    else:
        rows = (preparation, observer,
                (prefix + "launcher_declarations/recovery-resident.json", "recovery-plan"),
                (prefix + "launcher_output/recovery.json", "recovery-summary"),
                (prefix + "launcher_output/gateway.json", "gateway"),
                (prefix + "launcher_output/origin-capture.json", "origin-capture"),
                launcher, reservation)
    return tuple(sorted(rows, key=lambda row: (row[1].encode("ascii"), row[0].encode("ascii"))))


SOURCE_FIELDS = ("path", "role", "mode", "raw")


def _source(value, *, case_id=None):
    _exact(value, SOURCE_FIELDS, "CORE_DISPATCH_SOURCE_FIELDS")
    _path(value["path"], "CORE_DISPATCH_SOURCE_PATH")
    _require(type(value["role"]) is str and value["role"].isascii()
             and value["mode"] in (384, 420) and type(value["raw"]) is bytes
             and len(value["raw"]) <= MEMBER_LIMIT, "CORE_DISPATCH_SOURCE")
    if case_id is not None:
        _require(value["path"].startswith("cases/" + case_id + "/"),
                 "CORE_DISPATCH_SOURCE_CASE")
    return value


def _reference(source, *, sealed=False):
    return {"role": source["role"], "path": source["path"], "bytes": len(source["raw"]),
            "sha256": _sha(source["raw"]), **({"sealed": sealed} if sealed is not None else {})}


def _plain_reference(source):
    return {"path": source["path"], "bytes": len(source["raw"]),
            "sha256": _sha(source["raw"])}


def _member(source, case_id):
    ref = _reference(source, sealed=None)
    return {"path": ref["path"], "case_id": case_id, "role": ref["role"],
            "mode": source["mode"], "bytes": ref["bytes"], "sha256": ref["sha256"]}


def _validate_source_set(case, sources, *, seal_id):
    expected = required_paths(case, seal_id=seal_id)
    _require(len(expected) == (32 if case["index"] == 1 else 21 if case["index"] == 2 else 26),
             "CORE_DISPATCH_INTERNAL_COUNT")
    actual = []
    seen = set()
    total = 0
    for source in sources:
        _source(source, case_id=case["case_id"])
        key = source["path"]
        _require(key not in seen, "CORE_DISPATCH_SOURCE_DUPLICATE")
        seen.add(key); total += len(source["raw"])
        actual.append((key, source["role"], source["mode"]))
    _require(set(actual) == set(expected) and len(actual) == len(expected),
             "CORE_DISPATCH_REQUIRED_SET")
    _require(total <= CASE_BYTES_LIMIT, "CORE_DISPATCH_CASE_BYTES")
    if case["index"] == 3:
        forbidden = ("business/result-", "business-evidence/", "ledger-export",
                     "/ledger", "result-receipt", "ledger-identity", "result-identity")
        for source in sources:
            suffix = source["path"].split("/", 2)[-1]
            _require(not any(token in suffix for token in forbidden),
                     "CORE_DISPATCH_H11_FORBIDDEN_SOURCE")
    return sources


def _parse_source(sources, path, *, maximum=MEMBER_LIMIT, newline=True):
    source = next((item for item in sources if item["path"] == path), None)
    _require(source is not None, "CORE_DISPATCH_SOURCE_MISSING")
    return document(source["raw"], limit=maximum, newline=newline)


def _phase_receipt(case, phase, facts, sources):
    _exact(facts, ("quota_request_id", "quota_request_sha256", "query_unit", "listener_unit",
                   "admission_unit", "budget_deadline_ns", "phase_deadline_ns",
                   "stage_deadline_ns", "controller_deadline_ns"),
           "CORE_DISPATCH_PHASE_FACT_FIELDS")
    digest = _digest(facts["quota_request_sha256"], "CORE_DISPATCH_PHASE_DIGEST")
    _require(facts["listener_unit"] == "lhqoc-" + digest + ".service"
             and facts["admission_unit"] == "lhqoa-" + digest + ".service"
             and facts["query_unit"] == "lhqo-" + digest + ".service",
             "CORE_DISPATCH_PHASE_UNITS")
    for key in ("budget_deadline_ns", "phase_deadline_ns", "stage_deadline_ns",
                "controller_deadline_ns"):
        _integer(facts[key], 1, code="CORE_DISPATCH_PHASE_DEADLINE")
    _require(facts["stage_deadline_ns"] < facts["phase_deadline_ns"]
             <= facts["budget_deadline_ns"], "CORE_DISPATCH_PHASE_DEADLINE")
    expected = phase_source_specs(case, phase)
    refs = []
    for path, role in expected:
        source = next((item for item in sources if item["path"] == path), None)
        _require(source is not None and source["role"] == role, "CORE_DISPATCH_PHASE_SOURCES")
        refs.append(_reference(source, sealed=None))
    refs.sort(key=lambda row: (row["role"].encode("ascii"), row["path"].encode("ascii")))
    return {
        "schema": RECEIPT_SCHEMA, "session_id": SESSION, "index": case["index"],
        "case_id": case["case_id"], "phase": phase,
        **facts, "source_artifacts": refs,
        "source_artifacts_sha256": _sha(canonical(refs)),
    }


H01_OBSERVATIONS = (
    "empty_ledger_gate", "resident_empty_gate", "request_accepted", "grant_issued",
    "manager_delivered", "unit_identities", "bootstrap_exited", "helper_started",
    "helper_exited", "result_reader_exited", "result_verified", "client_waited",
    "stdout_eof", "stderr_eof", "future_start_blocked", "tree_exited",
    "writers_stopped", "collectors_stopped", "ledger_terminal", "evidence_sealed",
)
Q4_OBSERVATIONS = (
    "empty_ledger_gate", "resident_empty_gate", "request_accepted", "helper_running_seen",
    "cancel_called", "cancel_durable", "cancel_returned", "no_late_delivery",
    "unit_identities", "stop_ack", "helper_exited", "exit_flags_complete",
    "client_returned", "stdout_eof", "stderr_eof", "chain_closed",
    "ordinary_phase_closed", "independent_ordinary_cleanup_required", "full_h07",
)
H11_OBSERVATIONS = (
    "empty_ledger_gate", "resident_empty_gate", "original_request_accepted", "recovery_plan",
    "recovery_summary", "launcher_result", "gateway_snapshot", "origin_capture",
    "ledger_identity", "recovery_proof", "result_identity", "future_start_blocked",
    "tree_exited", "writers_stopped", "collectors_stopped", "effects_checked", "outcome",
    "leases_retained", "result_reread", "start_replayed", "business_evidence_sealed",
    "control_closure_sealed",
)


def _validate_gate(value, source):
    _exact(value, ("path", "bytes", "sha256"), "CORE_DISPATCH_GATE_REF")
    _require(value == _plain_reference(source), "CORE_DISPATCH_GATE_REF")


def _validate_resident_gate(value, case):
    _exact(value, ("passed", "candidate_commit", "resident_source_sha256",
                   "accepted_operation_id", "accepted_event_seq"),
           "CORE_DISPATCH_RESIDENT_GATE")
    _require(value["passed"] is True and value["candidate_commit"] == CANDIDATE["commit"]
             and value["accepted_operation_id"] == case["operation_id"],
             "CORE_DISPATCH_RESIDENT_GATE")
    _digest(value["resident_source_sha256"], "CORE_DISPATCH_RESIDENT_GATE")
    _integer(value["accepted_event_seq"], 1, code="CORE_DISPATCH_RESIDENT_GATE")


def _validate_units(value, case):
    phases = case["phases"]
    _require(type(value) is list and value, "CORE_DISPATCH_UNIT_IDENTITIES")
    expected_stages = {(phase, stage) for phase in phases
                       for stage in ("bootstrap", "helper", "result_reader")}
    actual = set()
    last = None
    for row in value:
        _exact(row, ("phase", "stage", "unit", "invocation_id"),
               "CORE_DISPATCH_UNIT_IDENTITY")
        key = (row["phase"], row["stage"])
        _require(key not in actual and key in expected_stages, "CORE_DISPATCH_UNIT_IDENTITY")
        actual.add(key)
        expected = next(item for item in _phase_units(case["operation_id"], phases)
                        if item["phase"] == row["phase"])
        unit_key = row["stage"] + "_unit" if row["stage"] != "result_reader" else "result_reader_unit"
        _require(row["unit"] == expected[unit_key]
                 and re.fullmatch(r"[0-9a-f]{32}", row["invocation_id"] or "") is not None,
                 "CORE_DISPATCH_UNIT_IDENTITY")
        ordering = (row["phase"], row["stage"], row["unit"])
        _require(last is None or last < ordering, "CORE_DISPATCH_UNIT_ORDER")
        last = ordering
    _require(actual == expected_stages, "CORE_DISPATCH_UNIT_IDENTITIES")


def _validate_stop(stop, owner_deadline):
    _exact(stop, ("requested", "acknowledged", "tree_exited", "writers_stopped", "deadline_ns"),
           "CORE_DISPATCH_STOP_FIELDS")
    _require(stop == {"requested": True, "acknowledged": True, "tree_exited": True,
                      "writers_stopped": True, "deadline_ns": owner_deadline},
             "CORE_DISPATCH_STOP")


def _validate_verdict(case, observations, stop, sources, proof, owner_deadline):
    expected_fields = H01_OBSERVATIONS if case["index"] == 1 else (
        Q4_OBSERVATIONS if case["index"] == 2 else H11_OBSERVATIONS)
    _exact(observations, expected_fields, "CORE_DISPATCH_OBSERVATION_FIELDS")
    gate_path = "cases/" + case["case_id"] + "/reservation/empty-ledger-gate.json"
    gate_source = next(item for item in sources if item["path"] == gate_path)
    _validate_gate(observations["empty_ledger_gate"], gate_source)
    _validate_resident_gate(observations["resident_empty_gate"], case)
    if case["index"] != 3:
        _validate_units(observations.get("unit_identities"), case)
    _validate_stop(stop, owner_deadline)
    if case["index"] == 1:
        for key in expected_fields:
            if key not in ("empty_ledger_gate", "resident_empty_gate", "unit_identities"):
                _require(observations[key] is True, "CORE_DISPATCH_H01_TRUTH")
    elif case["index"] == 2:
        false = {"chain_closed", "ordinary_phase_closed", "full_h07"}
        for key in expected_fields:
            if key in ("empty_ledger_gate", "resident_empty_gate", "unit_identities"):
                continue
            _require(observations[key] is (False if key in false else True),
                     "CORE_DISPATCH_Q4_TRUTH")
    else:
        _validate_h11_proof(proof, case, sources, owner_deadline)
        for key in ("recovery_plan", "recovery_summary", "launcher_result", "gateway_snapshot",
                    "origin_capture", "ledger_identity", "result_identity"):
            _require(observations[key] == proof[key], "CORE_DISPATCH_H11_PROJECTION")
        proof_source = next(item for item in sources if item["role"] == "recovery-proof")
        _require(observations["recovery_proof"] == _plain_reference(proof_source),
                 "CORE_DISPATCH_H11_PROJECTION")
        _require(observations["outcome"] == "UNKNOWN", "CORE_DISPATCH_H11_TRUTH")
        false = {"collectors_stopped", "effects_checked", "result_reread", "start_replayed",
                 "business_evidence_sealed"}
        objects = {"empty_ledger_gate", "resident_empty_gate", "unit_identities", "recovery_plan",
                   "recovery_summary", "launcher_result", "gateway_snapshot", "origin_capture",
                   "ledger_identity", "recovery_proof", "result_identity", "outcome"}
        for key in expected_fields:
            if key not in objects:
                _require(observations[key] is (False if key in false else True),
                         "CORE_DISPATCH_H11_TRUTH")
    artifacts = [_reference(source, sealed=True) for source in sources
                 if source["role"] != "verdict"]
    artifacts.sort(key=lambda row: row["path"].encode("ascii"))
    return {"schema": VERDICT_SCHEMA, "session_id": SESSION, "index": case["index"],
            "case_id": case["case_id"], "status": "PASS", "semantic_pass": True,
            "observations": observations, "artifacts": artifacts, "missing": [], "stop": stop}


def _validate_h11_proof(proof, case, sources, owner_deadline):
    _exact(proof, ("schema", "session_id", "index", "case_id", "candidate",
                   "ledger_identity", "recovery_plan", "recovery_summary", "launcher_result",
                   "gateway_snapshot", "origin_capture", "control_seal", "result_identity",
                   "assertions"), "CORE_DISPATCH_H11_PROOF_FIELDS")
    _require(proof["schema"] == PROOF_SCHEMA and proof["session_id"] == SESSION
             and proof["index"] == 3 and proof["case_id"] == case["case_id"],
             "CORE_DISPATCH_H11_PROOF_BINDING")
    candidate = _exact(proof["candidate"], (
        "commit", "tree", "h11_source_path", "h11_source_sha256", "resident_source_path",
        "resident_source_sha256", "launcher_source_path", "launcher_source_sha256",
    ), "CORE_DISPATCH_H11_CANDIDATE")
    _require(candidate["commit"] == CANDIDATE["commit"] and candidate["tree"] == CANDIDATE["tree"],
             "CORE_DISPATCH_H11_CANDIDATE")
    for key in ("h11_source_sha256", "resident_source_sha256", "launcher_source_sha256"):
        _digest(candidate[key], "CORE_DISPATCH_H11_CANDIDATE")
    ledger = _exact(proof["ledger_identity"], ("path", "dev", "ino", "unchanged"),
                    "CORE_DISPATCH_H11_LEDGER")
    _require(ledger["path"].endswith("/state/jobs.sqlite") and ledger["unchanged"] is True,
             "CORE_DISPATCH_H11_LEDGER")
    _integer(ledger["dev"], 0, code="CORE_DISPATCH_H11_LEDGER")
    _integer(ledger["ino"], 1, code="CORE_DISPATCH_H11_LEDGER")
    result = _exact(proof["result_identity"], (
        "expected_path", "expected_basename", "stat_performed", "opened", "hashed",
    ), "CORE_DISPATCH_H11_RESULT_IDENTITY")
    _require(result["expected_basename"] == "result-f7b176ecb6b8081fac3a7a47.json"
             and result["expected_path"].endswith("/" + result["expected_basename"])
             and result["stat_performed"] is False and result["opened"] is False
             and result["hashed"] is False, "CORE_DISPATCH_H11_RESULT_IDENTITY")
    refs = {
        "recovery_plan": ("launcher_declarations/recovery-resident.json", "recovery-plan"),
        "recovery_summary": ("launcher_output/recovery.json", "recovery-summary"),
        "launcher_result": ("launcher_output/result.json", "launcher-result"),
        "gateway_snapshot": ("launcher_output/gateway.json", "gateway"),
        "origin_capture": ("launcher_output/origin-capture.json", "origin-capture"),
        "control_seal": ("owner_output/seal.json", "control-seal"),
    }
    prefix = "cases/" + case["case_id"] + "/"
    for key, (suffix, role) in refs.items():
        source = next((item for item in sources if item["path"] == prefix + suffix), None)
        _require(source is not None and source["role"] == role, "CORE_DISPATCH_H11_REFERENCE")
        fields = ("path", "bytes", "sha256", "embedded_plan_sha256") if key == "recovery_plan" \
            else ("path", "bytes", "sha256")
        _exact(proof[key], fields, "CORE_DISPATCH_H11_REFERENCE")
        basic = _plain_reference(source)
        _require(all(proof[key][name] == value for name, value in basic.items()),
                 "CORE_DISPATCH_H11_REFERENCE")
        if key == "recovery_plan":
            _digest(proof[key]["embedded_plan_sha256"], "CORE_DISPATCH_H11_REFERENCE")
    assertions = _exact(proof["assertions"], (
        "same_operation", "same_request_digest", "original_handle_admitted",
        "same_original_stage_units", "same_grant_and_deadlines", "leases_retained",
        "delivery_intents_unchanged", "recovery_launch_forbidden", "gateway_parts_unchanged",
        "recovery_barrier_count", "quota_exit_pending_count", "start_replayed", "result_reread",
        "deadline_extended", "future_start_blocked", "tree_exited", "writers_stopped",
        "collectors_stopped", "effects_checked", "outcome", "business_evidence_sealed",
    ), "CORE_DISPATCH_H11_ASSERTIONS")
    for key in ("same_operation", "same_request_digest", "original_handle_admitted",
                "same_original_stage_units", "same_grant_and_deadlines", "leases_retained",
                "delivery_intents_unchanged", "recovery_launch_forbidden",
                "gateway_parts_unchanged", "future_start_blocked", "tree_exited", "writers_stopped"):
        _require(assertions[key] is True, "CORE_DISPATCH_H11_ASSERTIONS")
    for key in ("start_replayed", "result_reread", "deadline_extended", "collectors_stopped",
                "effects_checked", "business_evidence_sealed"):
        _require(assertions[key] is False, "CORE_DISPATCH_H11_ASSERTIONS")
    _require(assertions["recovery_barrier_count"] == assertions["quota_exit_pending_count"] == 1
             and assertions["outcome"] == "UNKNOWN", "CORE_DISPATCH_H11_ASSERTIONS")
    reservation = _parse_source(sources, prefix + "launcher_output/reservation.json")
    _require(type(reservation.get("controller")) is dict
             and reservation["controller"].get("deadline_ns") == owner_deadline,
             "CORE_DISPATCH_H11_DEADLINE")
    return proof


# Self-contained source-less approved-input parser for amendment A §3.
# Fixed public source descriptors are ordinary Python literals. No module from
# the host, package candidate or retained evidence is imported or executed.
# Private raw verification remains the host builder's duty before issuance.
APPROVED_FIXED_PINS = {'horizon': (7402, '7e149980e1fbb5f4494dcba06a11e0da451268a19d0cc30354ed375db2750b9d'), 'later': (795, 'c4ca5a1a83cb0247975c2178f2b8c43831503c771e714ac04147201ca7758481'), 'legacy': (885, '1e022bb0e7f3fb7ed09f5dd00ed61debda9992c7aa17324b8d36bb5cd2aaa585'), 'locator': (2893, '7d8364c8a417ee4879d4598e2ae6a9bb8cc14d14b79dc90d906bbad406bd5531'), 'placement': (790, '3bfbf6dd7417a1605286d3295b42df9b4e9b07202252b30eb46ed51a30f5c7a4'), 'producer': (1778, '851583a3a5268cb43fcd50990b2ef297f45fa7fe6e3ad679e9ea5af8ed978ab1'), 'quota': (847, '53fefd38c4b1795feb316ef9cc22d0d1aca99f1787af521b11af77d8e1ef82c6')}
APPROVED_LEGACY_FIELDS = ('archive', 'chain', 'inventory', 'manifest', 'producer_blobs')

APPROVED_ADOPTED_RAW = (('second-bootstrap-intent', 556, '58992ee2ff0d66fec5e10c7e138e8de4529089ca35d76f71200db1a05ac160b6'),
 ('second-bootstrap-attestation', 7766, 'cfc6c07265b4edc6d0b26e67a6ca9cfc19c652b4d011a2386b9bd95e945a34cb'))

APPROVED_RETAINED_PINS = {'domains': (267, '45c231e6f4dd1360888b9e4e3f790ce175440b8af89231801feeede2b21a2c4c'),
 'object': (1484, '24772cefec5e2c51364a1f4d1dadf692a2a666999077772138201004f811a808'),
 'paths': (1196, '1ea38f024d0ed06ec5d801ac9fc1b99f4938366d3cc979d8f5ba3b9eddd013c6')}

APPROVED_RECONCILIATION = {'applied': [],
 'record_basenames': ['evidence-adoption.json',
                      'reconciliation-intent.json',
                      'live-attestation.json',
                      'reconciliation-record.json',
                      'reconciliation-seal.json'],
 'released_bytes': 0,
 'released_inodes': 0,
 'state': 'NO_ELIGIBLE_RETAINED_SEALED_RECORD_SOURCE'}

APPROVED_VECTOR_PINS = {'delta': (6678, 'b8af1d3264b77b9142a48288482c26d2eafa894523f85baa0fc71d595da90352'),
 'effective': (18110, '7c2786f240144e7a2de90bc9a70561089a7334559bd8e962371132cf1db806e9'),
 'placement_normalized': (4549, 'b6153d8c45e5b009bcc1f878406565e08bcf7c7d07c17f18361b562bf1096703'),
 'placement_source': (4327, 'edcb0bb95508c15e5b3fb60d679c46c93961e95d8e802a338fc1f4397c18ee0d'),
 'quota': (2997, '95b59d878d643bfbce2eef6ce88145bf1086058694dee127b3de49d13319bde0'),
 'row_relation': (462, '89dea12770f6c6ab19b901adcf4c4d42e6b8b42300c1ca470b1ec7ac03ec47e6'),
 'snapshot': (11433, '82bdb7a94c85a7450a45d9ee7dff2baa4e5fef7b8a7a7d8f7787a0cb7bea358e')}

APPROVED_PREFIX_SHA256 = '09f107f265986afd0dcc0535de84d2df37ac47ddeff78d20569c2bb8a5513e88'

APPROVED_TAIL_SHA256 = '60885e762f1dfe007f43b6ae1e056dabdce9b1e142688741d333f806f6952a68'

APPROVED_TOTALS = {'configured_quota_bytes': 249561088,
 'configured_quota_inodes': 17792,
 'delta_bytes': 138412032,
 'delta_inodes': 8064,
 'effective_bytes': 765202432,
 'effective_inodes': 40177,
 'snapshot_bytes': 626790400,
 'snapshot_inodes': 32113}

APPROVED_POLICY_SOURCE_PINS = {'fixture_cloud_config': '5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523',
 'identity_public': 'e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c',
 'known_hosts': 'd1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd'}

def _approved_require(ok, code):
    _require(ok, "CORE_DISPATCH_APPROVED_" + code)


def _approved_exact(value, fields):
    return _exact(value, fields, "CORE_DISPATCH_APPROVED_FIELDS")


def _approved_absolute(value):
    return _absolute_text(value, "CORE_DISPATCH_APPROVED_PATH")


def _approved_hash(value):
    return _sha(canonical(value))


def _approved_equal(value, expected, code):
    _approved_require(canonical(value) == canonical(expected), code)


def _approved_vector(value, pin, code):
    raw = canonical(value)
    _approved_require((len(raw), _sha(raw)) == pin, code)


def _approved_union(relation):
    obligations = relation["obligations"]
    return dict(schema="local-hand-q2-core-source-union/v1", locator=relation["locator"],
        **{key: obligations[key] for key in ("legacy_20260927", "horizon_20261001e", "producer",
                                            "configured_quota_liability", "placement")},
        later_nonissuance=relation["later_nonissuance"])


def _approved_adoption(value):
    _approved_exact(value, {"current_owner_supplied_raw", "forward_baseline_entries", "disclosed_atime_changes",
                    "run_permission_adopted", "released_bytes", "released_inodes"})
    _approved_require(value["run_permission_adopted"] is False and type(value["released_bytes"]) is int
             and type(value["released_inodes"]) is int and value["released_bytes"] == value["released_inodes"] == 0,
             "LEGACY_PERMISSION")
    rows = value["current_owner_supplied_raw"]
    _approved_require(type(rows) is list and len(rows) == 2, "LEGACY_ADOPTION_COUNT")
    for row, (identifier, size, digest) in zip(rows, APPROVED_ADOPTED_RAW, strict=True):
        _approved_absolute(row.get("path"))
        _approved_equal(row, dict(id=identifier, path=row["path"], bytes=size, sha256=digest,
                         source_class="CURRENT_OWNER_SUPPLIED_RAW", proof_id="owner-adoption"), "LEGACY_ADOPTION")
    _approved_require(rows[0]["path"].endswith(".intent.json")
             and rows[1]["path"] == rows[0]["path"][:-len(".intent.json")] + "/bootstrap-attestation.json",
             "LEGACY_ADOPTION_PATH_RELATION")
    forward = value["forward_baseline_entries"]
    _approved_require(type(forward) is list and len(forward) == 610, "LEGACY_FORWARD_COUNT")
    seen, by_path = set(), {}
    for row in forward:
        _approved_require(type(row) is dict and set(row) in ({"source_metadata", "sha256"},
                     {"source_metadata", "sha256", "link_target"}), "LEGACY_FORWARD_FIELDS")
        meta = row["source_metadata"]
        fields = {"device", "inode", "st_mode", "uid", "gid", "nlink", "size", "blocks",
                  "atime_ns", "mtime_ns", "ctime_ns", "path", "type"}
        _approved_exact(meta, fields)
        _approved_absolute(meta["path"])
        for key in fields - {"path", "type"}:
            _integer(meta[key], 1 if key in ("device", "inode", "nlink") else 0)
        identity = meta["device"], meta["inode"]
        _approved_require(identity not in seen and meta["path"] not in by_path, "LEGACY_FORWARD_ALIAS")
        seen.add(identity); by_path[meta["path"]] = row
        _approved_require(meta["type"] in ("regular", "directory", "symlink"), "LEGACY_FORWARD_TYPE")
        _approved_require(stat.S_IFMT(meta["st_mode"]) == {
            "regular": stat.S_IFREG, "directory": stat.S_IFDIR, "symlink": stat.S_IFLNK}[meta["type"]],
            "LEGACY_FORWARD_MODE")
        if meta["type"] == "regular":
            _digest(row["sha256"])
            _approved_require(meta["nlink"] == 1 and "link_target" not in row, "LEGACY_FORWARD_REGULAR")
        elif meta["type"] == "directory":
            _approved_require(row["sha256"] is None and "link_target" not in row, "LEGACY_FORWARD_DIRECTORY")
        else:
            _approved_require(row["sha256"] is None and type(row.get("link_target")) is str, "LEGACY_FORWARD_SYMLINK")
    _approved_require(list(by_path) == sorted(by_path), "LEGACY_FORWARD_ORDER")
    parent = rows[0]["path"][:-len(".intent.json")]
    _approved_require(parent in by_path and by_path[parent]["source_metadata"]["type"] == "directory"
             and all(path == rows[0]["path"] or path == parent or path.startswith(parent + "/")
                     for path in by_path), "LEGACY_FORWARD_ROOT")
    for row in rows:
        _approved_require(row["path"] in by_path and by_path[row["path"]]["sha256"] == row["sha256"]
                 and by_path[row["path"]]["source_metadata"]["size"] == row["bytes"], "LEGACY_FORWARD_ADOPTED")
    changed = value["disclosed_atime_changes"]
    _approved_require(type(changed) is dict and len(changed) == 5, "LEGACY_ATIME_COUNT")
    for path, row in changed.items():
        _approved_absolute(path)
        _approved_exact(row, {"source_class", "sha256", "source_metadata", "historical_atime_preservation_proven"})
        _approved_require(row["source_class"] == "POST_READ_METADATA_BASELINE"
                 and row["historical_atime_preservation_proven"] is False, "LEGACY_ATIME_CLASS")
        _digest(row["sha256"])
        _approved_exact(row["source_metadata"], fields - {"path", "type"})
        for field, number in row["source_metadata"].items():
            _integer(number, 1 if field in ("device", "inode", "nlink") else 0)
        if path in by_path:
            _approved_equal(row["source_metadata"], {key: item for key, item in by_path[path]["source_metadata"].items()
                                          if key not in ("path", "type")}, "LEGACY_ATIME_METADATA")
            _approved_require(row["sha256"] == by_path[path]["sha256"], "LEGACY_ATIME_DIGEST")


def _approved_validate_relations(value):
    relation = value["source_relation"]
    _approved_exact(relation, {"schema", "locator", "obligations", "later_nonissuance", "zero_mismatch"})
    _approved_require(relation["schema"] == "local-hand-q2-core-approved-source-relation/v1"
             and relation["zero_mismatch"] is True, "SOURCE_RELATION")
    _approved_vector(relation["locator"], APPROVED_FIXED_PINS['locator'], "LOCATOR_RELATION")
    _approved_vector(relation["later_nonissuance"], APPROVED_FIXED_PINS['later'], "LATER_RELATION")
    obligations = relation["obligations"]
    fields = {"schema", "legacy_20260927", "horizon_20261001e", "producer", "configured_quota_liability",
              "placement", "row_relation", "source_horizon", "snapshot_rows_sha256", "delta_rows_sha256",
              "effective_rows_sha256", "source_union_sha256", "run_permission_adopted", "zero_mismatch"}
    _approved_exact(obligations, fields)
    _approved_require(obligations["schema"] == "local-hand-q2-core-approved-obligation-sources/v1"
             and obligations["source_horizon"] == "20261001e" and obligations["zero_mismatch"] is True
             and obligations["run_permission_adopted"] is False, "OBLIGATION_RELATION")
    old = obligations["legacy_20260927"]
    _approved_exact(old, {*APPROVED_LEGACY_FIELDS, "adoption"})
    _approved_vector({key: item for key, item in old.items() if key != "adoption"}, APPROVED_FIXED_PINS['legacy'], "LEGACY_FIXED")
    _approved_adoption(old["adoption"])
    for key, expected in (("horizon_20261001e", APPROVED_FIXED_PINS['horizon']), ("producer", APPROVED_FIXED_PINS['producer']),
                          ("configured_quota_liability", APPROVED_FIXED_PINS['quota']), ("placement", APPROVED_FIXED_PINS['placement'])):
        _approved_vector(obligations[key], expected, "RELATION_" + key.upper())
    _approved_vector(obligations["row_relation"], APPROVED_VECTOR_PINS["row_relation"], "ROW_RELATION")
    for field, name in (("snapshot_rows_sha256", "snapshot"), ("delta_rows_sha256", "delta"),
                        ("effective_rows_sha256", "effective")):
        _approved_require(obligations[field] == APPROVED_VECTOR_PINS[name][1], "ROW_DIGEST")
    _approved_require(obligations["source_union_sha256"] == _approved_hash(_approved_union(relation)), "SOURCE_UNION")
    return obligations


def _approved_validate_capacity(value, obligations):
    _approved_exact(value, {"schema", "source_horizon", "source_union_sha256", "snapshot_rows", "delta_rows",
                    "effective_rows", "row_relation", "placement", "configured_quota_rows", "totals",
                    "released_or_refunded"})
    _approved_require(value["schema"] == "local-hand-q2-core-historical-capacity-obligations/v1"
             and value["source_horizon"] == "20261001e" and value["released_or_refunded"] is False,
             "CAPACITY_SCHEMA")
    for key in ("source_union_sha256", "row_relation", "placement"):
        _approved_equal(value[key], obligations[key], "CAPACITY_RELATION")
    for key, name in (("snapshot_rows", "snapshot"), ("delta_rows", "delta"),
                      ("effective_rows", "effective"), ("configured_quota_rows", "quota")):
        _approved_vector(value[key], APPROVED_VECTOR_PINS[name], "CAPACITY_" + name.upper())
    _approved_equal(value["effective_rows"], value["snapshot_rows"] + value["delta_rows"], "CAPACITY_CONSTRUCTION")
    _approved_require(_approved_hash(value["snapshot_rows"][:7]) == APPROVED_PREFIX_SHA256
             and _approved_hash(value["snapshot_rows"][7:]) == APPROVED_TAIL_SHA256, "CAPACITY_PREFIX")
    _approved_equal(value["totals"], APPROVED_TOTALS, "CAPACITY_TOTALS")
    for key, count in (("snapshot_rows", 24), ("delta_rows", 12), ("effective_rows", 36)):
        rows = value[key]
        _approved_require(type(rows) is list and len(rows) == count, "CAPACITY_COUNT")
        prefix = key.removesuffix("_rows")
        for field in ("bytes", "inodes"):
            _approved_require(sum(_integer(row["commitment"][field]) for row in rows)
                     == value["totals"][prefix + "_" + field], "CAPACITY_SUM")
    _approved_require([row["project_id"] for row in value["configured_quota_rows"]]
             == obligations["configured_quota_liability"]["project_ids"], "CAPACITY_PROJECTS")


def _approved_validate_retained(value):
    _approved_exact(value, {"paths", "domains"})
    for key in ("paths", "domains"):
        _approved_vector(value[key], APPROVED_RETAINED_PINS[key], "RETAINED_" + key.upper())
    _approved_vector(value, APPROVED_RETAINED_PINS["object"], "RETAINED_OBJECT")
    _approved_require(len(value["paths"]) == 16 and len(value["domains"]) == 4, "RETAINED_COUNT")
    for row in value["paths"]:
        _approved_exact(row, {"path", "device", "inode"})
        _approved_absolute(row["path"]); _integer(row["device"], 1); _integer(row["inode"], 1)
    for row in value["domains"]:
        _approved_exact(row, {"project_id", "hard_bytes", "inode_hard_limit"})
        for number in row.values():
            _integer(number, 1)


def _approved_validate_policy(value):
    _approved_exact(value, {"schema", "fixture_cloud_config", "identity_public", "known_hosts",
                    "remote_expectation", "policies", "policy_predicates_sha256"})
    _approved_require(value["schema"] == "local-hand-q2-core-policy-basis/v1", "POLICY_SCHEMA")
    for name, digest in APPROVED_POLICY_SOURCE_PINS.items():
        _approved_equal(value[name], dict(binding_pointer="/" + name, sha256=digest), "POLICY_SOURCE")
    expected = copy.deepcopy(value["remote_expectation"])
    _approved_require(type(expected) is dict, "POLICY_EXPECTATION")
    for key in ("remote_tokens_sha256", "remote_command_sha256"):
        _digest(expected.get(key))
        expected[key] = ""
    # These template pins cover every fixed key and scalar in A §3.2. Only the
    # two D-dependent command digests and source-derived key are normalized.
    # The parser does not call the policy builder, so rehashing a weakened
    # predicate cannot turn it into a valid predicate.
    _approved_vector(expected, (410, "307997766eca2a5bef0411b6a41e72c1e904fa74831a03659e26a61b5c1d80cd"),
            "POLICY_EXPECTATION_TEMPLATE")
    policies = value["policies"]
    _approved_exact(policies, {"sudo", "sshd", "authorized_keys", "rc"})
    _approved_require(value["policy_predicates_sha256"] == _approved_hash(policies), "POLICY_DIGEST")
    normalized = copy.deepcopy(policies)
    for name, item in policies.items():
        _approved_exact(item, {"schema", "mode", "sources", "paths", "argv", "environment", "execution",
                       "predicate", "limits", "predicate_sha256"})
        _approved_require(item["predicate_sha256"] == _approved_hash(item["predicate"]), "POLICY_PREDICATE_DIGEST")
        normalized[name]["predicate_sha256"] = ""
    try:
        key = policies["authorized_keys"]["predicate"]["parameters"]["approved_key"]
        _approved_exact(key, {"type", "key_base64", "source_sha256"})
        _approved_require(type(key["key_base64"]) is str and key["key_base64"].isascii(), "POLICY_KEY")
        _approved_equal(key, _approved_key(("ssh-ed25519 " + key["key_base64"] + "\n").encode("ascii")), "POLICY_KEY")
        target = normalized["authorized_keys"]["predicate"]["parameters"]["approved_key"]
        target["key_base64"] = target["source_sha256"] = ""
    except (KeyError, TypeError) as error:
        raise DispatchError("CORE_DISPATCH_APPROVED_POLICY_KEY") from error
    _approved_vector(normalized, (6574, "b70e64bb418db787b2e7756f70d5e605329a00008a970aaf9939a32104e8506a"),
            "POLICY_PREDICATE_TEMPLATE")


def _approved_key(raw):
    try:
        lines = [line.strip() for line in raw.decode("ascii").splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        _approved_require(len(lines) == 1, "KEY_COUNT")
        fields = lines[0].split()
        _approved_require(len(fields) >= 2 and fields[0] == "ssh-ed25519", "KEY_TYPE")
        decoded = base64.b64decode(fields[1], validate=True)
        _approved_require(base64.b64encode(decoded).decode("ascii") == fields[1]
                 and decoded == struct.pack(">I", 11) + b"ssh-ed25519"
                 + struct.pack(">I", 32) + decoded[-32:] and len(decoded) == 51,
                 "KEY_ENCODING")
    except (UnicodeError, ValueError, IndexError) as error:
        raise DispatchError("CORE_DISPATCH_APPROVED_POLICY_KEY") from error
    return dict(type="ssh-ed25519", key_base64=fields[1], source_sha256=APPROVED_POLICY_SOURCE_PINS["identity_public"])


def _validate_approved_components(value):
    """Validate all fixed component relations; this is not a live admission."""
    try:
        _approved_exact(value, ("schema", "scope", "amendment", *ADMISSION_COMPONENTS))
        _approved_require(value["schema"] == "local-hand-q2-core-approved-inputs/v1"
                          and value["scope"] == SCOPE, "SCHEMA")
        _amendment(value["amendment"], value["amendment"]["implementation"])
        obligations = _approved_validate_relations(value)
        _approved_validate_capacity(value["historical_capacity_obligations"], obligations)
        _approved_validate_retained(value["retained_preparation"])
        _approved_equal(value["reconciliation"], APPROVED_RECONCILIATION, "RECONCILIATION")
        _approved_validate_policy(value["policy_basis"])
        return value
    except DispatchError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError, ValueError) as error:
        raise DispatchError("CORE_DISPATCH_APPROVED_INVALID_SHAPE") from error


def _amendment(value, implementation):
    _exact(value, ("baseline", "owner_decision", "closure", "implementation"),
           "CORE_DISPATCH_AMENDMENT_FIELDS")
    _require(value["baseline"] == AMENDMENT_BASELINE
             and value["owner_decision"] == AMENDMENT_OWNER_DECISION
             and value["closure"] == AMENDMENT_CLOSURE
             and value["implementation"] == implementation,
             "CORE_DISPATCH_AMENDMENT_AUTHORITY")
    _exact(implementation, ("commit", "tree"), "CORE_DISPATCH_IMPLEMENTATION")
    for item in implementation.values():
        _commit(item, "CORE_DISPATCH_IMPLEMENTATION")
    _require(implementation["commit"] not in (
        CLOSURE["commit"], AMENDMENT_BASELINE["commit"], AMENDMENT_CLOSURE["commit"],
        "520f77f578b90d31870517e33e29bee42918f3c0"), "CORE_DISPATCH_IMPLEMENTATION")
    return value


def _remote_management(value):
    _exact(value, set(REMOTE_ALIASES) | {
        "account", "uid", "gid", "home", "login_shell", "parser_profile",
        "remote_tokens_sha256", "remote_command_sha256"}, "CORE_DISPATCH_REMOTE_FIELDS")
    _require(value["account"] == "q1admin" and value["home"] == "/home/q1admin"
             and value["login_shell"] == "/bin/bash"
             and value["parser_profile"] == "bash-noninteractive-c-v1",
             "CORE_DISPATCH_REMOTE_ACCOUNT")
    for key in ("uid", "gid"):
        _integer(value[key], 1, 2**32 - 2, "CORE_DISPATCH_REMOTE_ACCOUNT")
    for key in ("remote_tokens_sha256", "remote_command_sha256"):
        _digest(value[key], "CORE_DISPATCH_REMOTE_COMMAND")
    total = 0
    for name, alias in REMOTE_ALIASES.items():
        item = _exact(value[name], PROGRAM_FIELDS | {"resolved_path", "symlink_chain"},
                      "CORE_DISPATCH_REMOTE_ENTITY_FIELDS")
        _require(item["path"] == alias, "CORE_DISPATCH_REMOTE_ALIAS")
        _absolute_text(item["resolved_path"], "CORE_DISPATCH_REMOTE_ENTITY")
        for key in ("dev", "uid", "gid"):
            _integer(item[key], 0, code="CORE_DISPATCH_REMOTE_ENTITY")
        _integer(item["ino"], 1, code="CORE_DISPATCH_REMOTE_ENTITY")
        _integer(item["nlink"], 1, 1, "CORE_DISPATCH_REMOTE_ENTITY")
        _integer(item["mode"], 0, 0o7777, "CORE_DISPATCH_REMOTE_ENTITY")
        _integer(item["bytes"], 1, 16777216, "CORE_DISPATCH_REMOTE_ENTITY")
        _require(item["uid"] == item["gid"] == 0 and item["mode"] & 0o111
                 and not item["mode"] & 0o022, "CORE_DISPATCH_REMOTE_ENTITY")
        _digest(item["sha256"], "CORE_DISPATCH_REMOTE_ENTITY")
        chain = item["symlink_chain"]
        _require(type(chain) is list and len(chain) <= 8, "CORE_DISPATCH_REMOTE_ALIAS")
        seen = set()
        for link in chain:
            _exact(link, ("path", "target"), "CORE_DISPATCH_REMOTE_ALIAS")
            _absolute_text(link["path"], "CORE_DISPATCH_REMOTE_ALIAS")
            target = link["target"]
            _require(type(target) is str and target.isascii() and 0 < len(target) <= 4096
                     and re.fullmatch(r"[A-Za-z0-9._/-]+", target) is not None
                     and "//" not in target and ".." not in target.split("/")
                     and len(target.split("/")) <= 64 and link["path"] not in seen,
                     "CORE_DISPATCH_REMOTE_ALIAS")
            seen.add(link["path"])
        total += item["bytes"]
    _require(total <= 83886080, "CORE_DISPATCH_REMOTE_ENTITY_LIMIT")
    return value


def _approved_inputs_envelope(context):
    """Bind preimages, not live facts; raw verification/admission remain required."""
    manifest, members = context["manifest"], context["members"]
    descriptor = _exact(manifest["approved_inputs"], (
        "path", "bytes", "sha256", "approved_source_relation_sha256"),
        "CORE_DISPATCH_APPROVED_DESCRIPTOR")
    _require(descriptor["path"] == APPROVED_INPUTS_PATH,
             "CORE_DISPATCH_APPROVED_DESCRIPTOR")
    _integer(descriptor["bytes"], 1, APPROVED_INPUTS_LIMIT,
             "CORE_DISPATCH_APPROVED_DESCRIPTOR")
    for key in ("sha256", "approved_source_relation_sha256"):
        _digest(descriptor[key], "CORE_DISPATCH_APPROVED_DESCRIPTOR")
    view = members.get(APPROVED_INPUTS_PATH)
    _require(type(view) is bytes or (isinstance(view, memoryview) and view.readonly),
             "CORE_DISPATCH_APPROVED_MEMBER")
    raw = bytes(view)
    _require(len(raw) == descriptor["bytes"] and _sha(raw) == descriptor["sha256"],
             "CORE_DISPATCH_APPROVED_MEMBER")
    rows = [row for row in manifest["members"] if row.get("role") == "approved-inputs"]
    expected = {"path": APPROVED_INPUTS_PATH, "role": "approved-inputs", "mode": 384,
                "bytes": len(raw), "sha256": _sha(raw), "origin": {
                    "kind": "approved-inputs", "bytes": len(raw), "sha256": _sha(raw),
                    "approved_source_relation_sha256": descriptor["approved_source_relation_sha256"]}}
    _require(rows == [expected], "CORE_DISPATCH_APPROVED_ROW")
    value = document(raw, limit=APPROVED_INPUTS_LIMIT)
    _exact(value, ("schema", "scope", "amendment", *ADMISSION_COMPONENTS),
           "CORE_DISPATCH_APPROVED_FIELDS")
    _require(value["schema"] == "local-hand-q2-core-approved-inputs/v1"
             and value["scope"] == SCOPE, "CORE_DISPATCH_APPROVED_SCHEMA")
    _amendment(value["amendment"], manifest["implementation"])
    _require(value["amendment"] == manifest["amendment"],
             "CORE_DISPATCH_APPROVED_AMENDMENT")
    for key in ADMISSION_COMPONENTS:
        _require(type(value[key]) is dict, "CORE_DISPATCH_APPROVED_COMPONENT")
    _require(_sha(canonical(value["source_relation"]))
             == descriptor["approved_source_relation_sha256"],
             "CORE_DISPATCH_APPROVED_SOURCE_RELATION")
    return value


def _admission_binding(context):
    """Return the nine exact, distinct digests specified by amendment A §4."""
    approved = _approved_inputs_envelope(context)
    binding = {"approved_inputs_sha256": context["manifest"]["approved_inputs"]["sha256"]}
    for key in ADMISSION_COMPONENTS:
        name = "approved_source_relation" if key == "source_relation" else key
        binding[name + "_sha256"] = _sha(canonical(approved[key]))
    binding.update({
        "local_management_binding_sha256": context["manifest"]["entry"]["local_management_binding_sha256"],
        "hello_sha256": _sha(canonical(context["hello"], newline=True)),
        "remote_management_sha256": _sha(canonical(context["hello"]["remote_management"])),
    })
    for digest in binding.values():
        _digest(digest, "CORE_DISPATCH_ADMISSION_BINDING")
    return binding


def _validate_admission_binding(value, context):
    expected = _admission_binding(context)
    _exact(value, expected, "CORE_DISPATCH_ADMISSION_BINDING_FIELDS")
    _require(value == expected, "CORE_DISPATCH_ADMISSION_BINDING")
    return value


def _validate_context_envelope(context):
    """Validate the v2 transport envelope without claiming admission/consumption."""
    _exact(context, ("schema", "hello", "bind", "manifest", "members", "guest_deadlines",
                     "stdin_bytes_received"), "CORE_DISPATCH_CONTEXT_FIELDS")
    _require(context["schema"] == CONTEXT_SCHEMA, "CORE_DISPATCH_CONTEXT_SCHEMA")
    hello, bind, manifest = context["hello"], context["bind"], context["manifest"]
    _exact(hello, ("schema", "scope", "loader_sha256", "bootstrap_sha256", "guest_boot_id",
                   "guest_boottime_origin_ns", "guest_monotonic_origin_ns", "pid", "uid", "gid",
                   "euid", "egid", "python", "carrier_unit", "process_limits", "remote_management"),
           "CORE_DISPATCH_HELLO_FIELDS")
    _require(hello["schema"] == HELLO_SCHEMA
             and hello["scope"] == SCOPE and hello["uid"] == hello["gid"] == 0
             and hello["euid"] == hello["egid"] == 0, "CORE_DISPATCH_HELLO")
    for key in ("loader_sha256", "bootstrap_sha256"):
        _digest(hello[key], "CORE_DISPATCH_HELLO")
    for key in ("uid", "gid", "euid", "egid"):
        _integer(hello[key], 0, 0, "CORE_DISPATCH_HELLO")
    for key in ("pid", "guest_boottime_origin_ns", "guest_monotonic_origin_ns"):
        _integer(hello[key], 1, code="CORE_DISPATCH_HELLO")
    _require(type(hello["guest_boot_id"]) is str and re.fullmatch(
        r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", hello["guest_boot_id"]),
        "CORE_DISPATCH_HELLO")
    remote = _remote_management(hello["remote_management"])
    _require(hello["python"] == {
        key: remote["python"]["resolved_path"] if key == "path" else remote["python"][key]
        for key in PROGRAM_FIELDS}, "CORE_DISPATCH_PYTHON_PROJECTION")
    unit = _exact(hello["carrier_unit"], (
        "name", "control_group", "invocation_id", "active_state", "sub_state",
        "runtime_max_usec", "timeout_stop_usec", "memory_max", "memory_swap_max",
        "tasks_max", "cpu_quota_per_sec_usec", "restart", "kill_mode", "exit_type"),
        "CORE_DISPATCH_CARRIER_FIELDS")
    carrier_name = "lhqcore20261003a-carrier.service"
    _absolute_text(unit["control_group"], "CORE_DISPATCH_CARRIER")
    _require(unit["name"] == carrier_name and unit["control_group"].endswith("/" + carrier_name)
             and type(unit["invocation_id"]) is str
             and re.fullmatch(r"[0-9a-f]{32}", unit["invocation_id"])
             and unit["active_state"] == "active" and unit["sub_state"] in ("running", "start")
             and unit["restart"] == "no" and unit["kill_mode"] == "control-group"
             and unit["exit_type"] == "cgroup", "CORE_DISPATCH_CARRIER")
    for key, expected in {"runtime_max_usec": 800000000, "timeout_stop_usec": 30000000,
                          "memory_max": 1073741824, "memory_swap_max": 0, "tasks_max": 128,
                          "cpu_quota_per_sec_usec": 1000000}.items():
        _integer(unit[key], expected, expected, "CORE_DISPATCH_CARRIER")
    limits = {"cpu_soft": 800, "cpu_hard": 800, "nofile_soft": 256, "nofile_hard": 256,
              "fsize_soft": 67108864, "fsize_hard": 67108864, "umask": 0o077}
    _exact(hello["process_limits"], limits, "CORE_DISPATCH_PROCESS_LIMITS")
    for key, expected in limits.items():
        _integer(hello["process_limits"][key], expected, expected, "CORE_DISPATCH_PROCESS_LIMITS")
    canonical(hello, newline=True, limit=4096)
    _exact(bind, ("schema", "scope", "session_id", "hello_sha256", "consumption_sha256",
                  "package_basename", "package_bytes", "package_sha256",
                  "host_boottime_origin_ns", "host_monotonic_origin_ns",
                  "host_boottime_deadline_ns", "host_monotonic_deadline_ns",
                  "host_boottime_bind_ns", "host_monotonic_bind_ns", "host_remaining_floor_ns",
                  "clock_margin_ns", "local_final_reserve_ns", "mapped_duration_ns",
                  "guest_duration_cap_ns", "guest_duration_ns"), "CORE_DISPATCH_BIND_FIELDS")
    _require(bind["schema"] == "local-hand-q2-core-carrier-bind/v1" and bind["scope"] == SCOPE
             and bind["session_id"] == SESSION and bind["hello_sha256"] == _sha(canonical(hello, newline=True)),
             "CORE_DISPATCH_BIND")
    for key in ("hello_sha256", "consumption_sha256", "package_sha256"):
        _digest(bind[key], "CORE_DISPATCH_BIND")
    for key in ("host_boottime_origin_ns", "host_monotonic_origin_ns",
                "host_boottime_deadline_ns", "host_monotonic_deadline_ns",
                "host_boottime_bind_ns", "host_monotonic_bind_ns"):
        _integer(bind[key], 1, code="CORE_DISPATCH_BIND_CLOCK")
    _require(bind["host_boottime_deadline_ns"]
             == bind["host_boottime_origin_ns"] + LIMITS["carrier_seconds"] * NS
             and bind["host_monotonic_deadline_ns"]
             == bind["host_monotonic_origin_ns"] + LIMITS["carrier_seconds"] * NS
             and bind["host_boottime_origin_ns"] <= bind["host_boottime_bind_ns"]
             < bind["host_boottime_deadline_ns"]
             and bind["host_monotonic_origin_ns"] <= bind["host_monotonic_bind_ns"]
             < bind["host_monotonic_deadline_ns"],
             "CORE_DISPATCH_OUTER_DEADLINE")
    remaining = min(bind["host_boottime_deadline_ns"] - bind["host_boottime_bind_ns"],
                    bind["host_monotonic_deadline_ns"] - bind["host_monotonic_bind_ns"])
    floor = remaining // 1_000_000 * 1_000_000
    _require(remaining > 0 and bind["host_remaining_floor_ns"] == floor
             and bind["clock_margin_ns"] == 2_000_000_000
             and bind["local_final_reserve_ns"] == 15_000_000_000
             and bind["mapped_duration_ns"] == floor - 17_000_000_000 > 0
             and bind["guest_duration_cap_ns"] == 750_000_000_000
             and bind["guest_duration_ns"] == min(bind["mapped_duration_ns"], 750_000_000_000),
             "CORE_DISPATCH_BIND_MAPPING")
    _exact(manifest, ("schema", "scope", "rule", "baseline", "owner_decision", "closure",
                      "implementation", "candidate", "wheel", "projection", "entry", "locators",
                      "members", "limits", "amendment", "approved_inputs"), "CORE_DISPATCH_MANIFEST_FIELDS")
    _require(manifest["schema"] == PACKAGE_SCHEMA
             and manifest["scope"] == SCOPE and manifest["rule"] == RULE
             and manifest["baseline"] == BASELINE and manifest["owner_decision"] == OWNER_DECISION
             and manifest["closure"] == CLOSURE and manifest["candidate"] == CANDIDATE
             and manifest["wheel"] == WHEEL and manifest["projection"] == PROJECTION
             and manifest["limits"] == PACKAGE_LIMITS, "CORE_DISPATCH_MANIFEST_AUTHORITY")
    _exact(manifest["implementation"], ("commit", "tree"), "CORE_DISPATCH_IMPLEMENTATION")
    _commit(manifest["implementation"]["commit"], "CORE_DISPATCH_IMPLEMENTATION")
    _commit(manifest["implementation"]["tree"], "CORE_DISPATCH_IMPLEMENTATION")
    _require(manifest["implementation"] != CLOSURE, "CORE_DISPATCH_IMPLEMENTATION")
    _amendment(manifest["amendment"], manifest["implementation"])
    entry = manifest["entry"]
    _exact(entry, ("loader_path", "loader_bytes", "loader_sha256", "bootstrap_path",
                   "bootstrap_bytes", "bootstrap_sha256", "dispatcher_path", "dispatcher_bytes",
                   "dispatcher_sha256", "carrier_argv_sha256", "local_management_binding_sha256", "writer"),
           "CORE_DISPATCH_ENTRY_FIELDS")
    _validate_local_writer(entry["writer"])
    for key in ("carrier_argv_sha256", "local_management_binding_sha256"):
        _digest(entry[key], "CORE_DISPATCH_ENTRY")
    _require(type(entry) is dict and entry.get("loader_path") == "field/loader.py"
             and entry.get("bootstrap_path") == "field/bootstrap.py"
             and entry.get("dispatcher_path") == "field/dispatcher.py"
             and hello["loader_sha256"] == entry.get("loader_sha256")
             and hello["bootstrap_sha256"] == entry.get("bootstrap_sha256"),
             "CORE_DISPATCH_ENTRY")
    locators = _exact(manifest["locators"], (
        "schema", "observation_record_sha256", "source_relation_sha256", "state_parent",
        "quota_parent", "install_parent", "journal_parent", "evidence_parent", "ordinary_user",
        "ordinary_group", "user_manager_unit", "query_parent_unit", "controller_parent_unit",
        "management_parent_unit", "supervisor_parent_unit", "ordinary_parent_unit",
        "retained_ordinary_parent_path", "carrier_unit"), "CORE_DISPATCH_LOCATOR_FIELDS")
    _require(locators["schema"] == "local-hand-q2-core-private-locators/v1"
             and locators["carrier_unit"] == carrier_name, "CORE_DISPATCH_LOCATOR")
    _digest(locators["observation_record_sha256"], "CORE_DISPATCH_LOCATOR")
    relation = {"schema": "local-hand-q2-core-locator-relation/v2",
                "local_management_binding_sha256": entry["local_management_binding_sha256"],
                "observation_record_sha256": locators["observation_record_sha256"],
                "locators": {key: item for key, item in locators.items()
                             if key != "source_relation_sha256"}}
    _require(locators["source_relation_sha256"] == _sha(canonical(relation)),
             "CORE_DISPATCH_LOCATOR_RELATION")
    members = context["members"]
    _require(type(manifest["members"]) is list and manifest["members"],
             "CORE_DISPATCH_PACKAGE_MEMBERS")
    paths = []
    for row in manifest["members"]:
        _exact(row, ("path", "role", "mode", "bytes", "sha256", "origin"),
               "CORE_DISPATCH_PACKAGE_ROW")
        paths.append(_path(row["path"], "CORE_DISPATCH_PACKAGE_ROW"))
        _integer(row["bytes"], 0, MEMBER_LIMIT, "CORE_DISPATCH_PACKAGE_ROW")
        _digest(row["sha256"], "CORE_DISPATCH_PACKAGE_ROW")
        _require(type(row["mode"]) is int
                 and ((row["role"] == "approved-inputs" and row["mode"] == 384)
                      or (row["role"] in ("candidate-worktree", "candidate-git-metadata",
                                           "wheel", "projection", "field-code")
                          and row["mode"] in (420, 493))), "CORE_DISPATCH_PACKAGE_ROW")
    _require(len(paths) <= MEMBER_COUNT_LIMIT and len(set(paths)) == len(paths)
             and paths == sorted(paths, key=lambda item: item.encode("ascii")),
             "CORE_DISPATCH_PACKAGE_MEMBERS")
    _require(type(members) is dict and set(members) == {row["path"] for row in manifest["members"]},
             "CORE_DISPATCH_PACKAGE_MEMBERS")
    manifest_raw = canonical(manifest, newline=True)
    package_hash = hashlib.sha256()
    package_hash.update(PACKAGE_MAGIC)
    package_hash.update(struct.pack(">Q", len(manifest_raw)))
    package_hash.update(manifest_raw)
    package_bytes = len(PACKAGE_MAGIC) + 8 + len(manifest_raw)
    for row in manifest["members"]:
        raw = members[row["path"]]
        _require((type(raw) is bytes or (isinstance(raw, memoryview) and raw.readonly))
                 and len(raw) == row["bytes"] and _sha(raw) == row["sha256"],
                 "CORE_DISPATCH_PACKAGE_MEMBER")
        package_hash.update(raw)
        package_bytes += len(raw)
    _require(package_bytes == bind["package_bytes"]
             and package_hash.hexdigest() == bind["package_sha256"],
             "CORE_DISPATCH_PACKAGE_BINDING")
    _require(entry.get("dispatcher_bytes") == len(members["field/dispatcher.py"])
             and entry.get("dispatcher_sha256") == _sha(members["field/dispatcher.py"]),
             "CORE_DISPATCH_ENTRY")
    for role in ("loader", "bootstrap", "dispatcher"):
        raw = members.get("field/" + role + ".py")
        _require(raw is not None and type(entry[role + "_bytes"]) is int
                 and entry[role + "_bytes"] == len(raw)
                 and entry[role + "_sha256"] == _sha(raw), "CORE_DISPATCH_ENTRY")
    deadlines = _exact(context["guest_deadlines"],
                       ("boot_id", "boottime_deadline_ns", "monotonic_deadline_ns"),
                       "CORE_DISPATCH_GUEST_DEADLINES")
    _require(deadlines["boot_id"] == hello["guest_boot_id"]
             and deadlines["boottime_deadline_ns"] == hello["guest_boottime_origin_ns"] + bind["guest_duration_ns"]
             and deadlines["monotonic_deadline_ns"] == hello["guest_monotonic_origin_ns"] + bind["guest_duration_ns"],
             "CORE_DISPATCH_GUEST_DEADLINES")
    _integer(context["stdin_bytes_received"], 1, LIMITS["carrier_input_bytes"],
             "CORE_DISPATCH_STDIN")
    expected_stdin = 8 + 8 + len(canonical(bind, newline=True)) + bind["package_bytes"]
    _require(context["stdin_bytes_received"] == expected_stdin, "CORE_DISPATCH_STDIN")
    approved = _approved_inputs_envelope(context)
    policy = approved["policy_basis"]
    _require(type(policy.get("remote_expectation")) is dict,
             "CORE_DISPATCH_REMOTE_EXPECTATION")
    expected = policy["remote_expectation"]
    _exact(expected, ("account", "home_path", "login_shell", "hello_schema", "parser_profile",
                      "aliases", "remote_tokens_sha256", "remote_command_sha256",
                      "remote_entity_preimages_stage"), "CORE_DISPATCH_REMOTE_EXPECTATION")
    _require(expected == {
        "account": "q1admin", "home_path": "/home/q1admin", "login_shell": "/bin/bash",
        "hello_schema": HELLO_SCHEMA, "parser_profile": "bash-noninteractive-c-v1",
        "aliases": REMOTE_ALIASES, "remote_tokens_sha256": remote["remote_tokens_sha256"],
        "remote_command_sha256": remote["remote_command_sha256"],
        "remote_entity_preimages_stage": "HELLO_JIT"}, "CORE_DISPATCH_REMOTE_EXPECTATION")
    return context


def _validate_context(context):
    _validate_context_envelope(context)
    _validate_approved_components(_approved_inputs_envelope(context))
    _consumption_info(context)
    return context


def _validate_local_writer(value):
    """Validate transported host bytes, never sample a guest substitute."""
    code = "CORE_DISPATCH_HOST_WRITER"
    _exact(value, ("schema", "user_namespace", "pid_namespace", "process", "uid", "gid",
                   "supplementary_gids"), code)
    _require(value["schema"] == "local-hand-q2-core-local-writer/v1", code)
    for name in ("user_namespace", "pid_namespace", "process", "uid", "gid"):
        fields = ({"dev": 0, "ino": 1} if name.endswith("namespace") else
                  {"pid": 1, "starttime_ticks": 0} if name == "process" else
                  dict.fromkeys(("real", "effective", "saved", "filesystem"), 0))
        _exact(value[name], fields, code)
        for key, minimum in fields.items():
            _integer(value[name][key], minimum, code=code)
        if name in ("uid", "gid"):
            _require(len(set(value[name].values())) == 1, code)
    groups = value["supplementary_gids"]
    _require(type(groups) is list, code)
    for item in groups:
        _integer(item, code=code)
    _require(groups == sorted(set(groups)), code)
    canonical(value, limit=4096)
    return value


def _consumption_info(context):
    """Rebuild marker v2 from v3 inputs; this is not host persistence proof."""
    manifest, bind = context["manifest"], context["bind"]
    _require(manifest["schema"] == PACKAGE_SCHEMA,
             "CORE_DISPATCH_MANIFEST_AUTHORITY")
    entry = manifest["entry"]
    writer = _validate_local_writer(entry["writer"])
    marker = {"schema": "local-hand-q2-core-carrier-consumption/v2",
        "scope": SCOPE, "session_id": SESSION,
        **{key: manifest[key] for key in ("baseline", "owner_decision", "closure",
                                          "implementation", "amendment", "candidate")},
        "package": {"basename": bind["package_basename"], "bytes": bind["package_bytes"],
                    "sha256": bind["package_sha256"],
                    "manifest_sha256": _sha(canonical(manifest, newline=True))},
        "approved_inputs_sha256": manifest["approved_inputs"]["sha256"],
        "local_management_binding_sha256": entry["local_management_binding_sha256"],
        "writer": writer, "carrier_argv_sha256": entry["carrier_argv_sha256"],
        **{key: bind[key] for key in ("host_boottime_origin_ns", "host_monotonic_origin_ns",
                                      "host_boottime_deadline_ns", "host_monotonic_deadline_ns")},
        "state": "CONSUMPTION_RECORD_COMPLETE"}
    raw = canonical(marker, newline=True, limit=16384)
    _require(_sha(raw) == bind["consumption_sha256"], "CORE_DISPATCH_CONSUMPTION_BINDING")
    return {"basename": ".lhqcore-20261003a.carrier-consumed.json", "bytes": len(raw),
            "sha256": _sha(raw), "state": marker["state"]}


def field_readiness():
    """Inert readiness report: distinguish missing input bindings from D code gaps."""
    return {
        "schema": "local-hand-q2-core-field-readiness/v1",
        "scope": SCOPE,
        "releasable": False,
        "unbound_approved_inputs": list(UNBOUND_APPROVED_INPUTS),
        "protocol_blockers": [],
        "unimplemented_effects": list(UNIMPLEMENTED_FIELD_EFFECTS),
    }


def _git_blob(raw):
    _require(type(raw) is bytes, "CORE_EFFECT_PACKAGE_BYTES")
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _projection_path(name):
    if type(name) is not str:
        return False
    path = PurePosixPath(name)
    module = re.fullmatch(
        r"tools/(?:admin/(?:local_hand_quota_observer|local_hand_system_manager)|"
        r"local_hand|local_hand_connect|local_hand_jobs|local_hand_mcp)/"
        r"[a-z_][a-z0-9_]*\.py", name)
    return (not path.is_absolute() and path.as_posix() == name
            and all(part not in ("", ".", "..") for part in path.parts)
            and (name in PROJECTION_HARNESS or module is not None)) \
        and "namespace" not in name.lower() and "watchdog" not in name.lower()


def _json_object(raw, code):
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_pairs,
                           parse_constant=_nonfinite)
    except DispatchError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DispatchError(code) from error
    _shape(value)
    return value


def _wheel_payload(raw, source_files):
    """Verify the exact wheel and its source/payload binding in memory."""
    _require(type(raw) is bytes and len(raw) == WHEEL["bytes"]
             and _sha(raw) == WHEEL["sha256"], "CORE_EFFECT_WHEEL_PIN")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            _require(1 <= len(names) <= 1024 and len(names) == len(set(names))
                     and sum(item.file_size for item in infos) <= 32 * 1024 * 1024,
                     "CORE_EFFECT_WHEEL_INVENTORY")
            for item in infos:
                path = PurePosixPath(item.filename)
                file_type = stat.S_IFMT(item.external_attr >> 16)
                _require(not item.is_dir() and not path.is_absolute()
                         and path.as_posix() == item.filename
                         and all(part not in ("", ".", "..") for part in path.parts)
                         and item.file_size <= MEMBER_LIMIT
                         and file_type in (0, stat.S_IFREG),
                         "CORE_EFFECT_WHEEL_ENTRY")
            content = {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise DispatchError("CORE_EFFECT_WHEEL_ARCHIVE") from error
    metadata = _json_object(content.get(WHEEL_METADATA, b""),
                            "CORE_EFFECT_WHEEL_METADATA")
    _exact(metadata, ("schema_version", "product_version", "source_commit",
                      "artifact_kind", "files"), "CORE_EFFECT_WHEEL_METADATA")
    _require(metadata["schema_version"] == "infra-local-hand-build/v1"
             and metadata["product_version"] == "0.2.0a1"
             and metadata["source_commit"] == CANDIDATE["commit"]
             and metadata["artifact_kind"] == "wheel", "CORE_EFFECT_WHEEL_METADATA")
    package_pattern = r"tools/(?:(?:" + "|".join(WHEEL_PACKAGES) + \
        r"))/[a-z_][a-z0-9_]*\.(?:py|sh|ps1)"
    expected = {name[6:]: digest for name, digest in source_files.items()
                if re.fullmatch(package_pattern, name)}
    _require(metadata["files"] == expected
             and all(package + "/__init__.py" in expected for package in WHEEL_PACKAGES),
             "CORE_EFFECT_WHEEL_SOURCE")
    for name, digest in expected.items():
        _require(name in content and _sha(content[name]) == digest,
                 "CORE_EFFECT_WHEEL_PAYLOAD")
    dist = "infra_local_hand-0.2.0a1.dist-info/"
    extras = set(content) - set(expected) - {WHEEL_METADATA}
    _require(extras and all(name.startswith(dist)
                            and len(PurePosixPath(name).parts) == 2 for name in extras)
             and {dist + name for name in ("METADATA", "WHEEL", "RECORD")} <= extras,
             "CORE_EFFECT_WHEEL_EXTRAS")
    _require(b"Name: infra-local-hand\n" in content[dist + "METADATA"]
             and b"Version: 0.2.0a1\n" in content[dist + "METADATA"]
             and b"Root-Is-Purelib: true\n" in content[dist + "WHEEL"],
             "CORE_EFFECT_WHEEL_DISTRIBUTION")
    try:
        rows = list(csv.reader(io.StringIO(content[dist + "RECORD"].decode("utf-8", "strict"))))
    except (UnicodeError, csv.Error) as error:
        raise DispatchError("CORE_EFFECT_WHEEL_RECORD") from error
    _require(len(rows) == len(content) and all(len(row) == 3 for row in rows)
             and len({row[0] for row in rows}) == len(rows)
             and {row[0] for row in rows} == set(content), "CORE_EFFECT_WHEEL_RECORD")
    for name, digest, size in rows:
        if name == dist + "RECORD":
            _require(digest == size == "", "CORE_EFFECT_WHEEL_RECORD")
        else:
            actual = base64.urlsafe_b64encode(hashlib.sha256(content[name]).digest()) \
                .rstrip(b"=").decode("ascii")
            _require(digest == "sha256=" + actual and size == str(len(content[name])),
                     "CORE_EFFECT_WHEEL_RECORD")
    payload = _sha(json.dumps({"schema_version": "infra-local-hand-full-payload/v1",
                               "files": expected}, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True).encode("ascii"))
    _require(payload == WHEEL["payload_digest"], "CORE_EFFECT_WHEEL_PAYLOAD_DIGEST")
    return {"files": expected, "payload_digest": payload, "content": content}


def verify_install_inputs(context):
    """RAM-only P5 input verification; no effects or live-readiness claim."""
    manifest, members = context["manifest"], context["members"]
    if manifest.get("schema") == PACKAGE_SCHEMA:
        _approved_inputs_envelope(context)
    rows = manifest["members"]
    _require(type(rows) is list and rows
             and [row.get("path") for row in rows]
             == sorted((row.get("path") for row in rows), key=lambda item: item.encode("ascii")),
             "CORE_EFFECT_PACKAGE_ORDER")
    source_files = {}
    helper_digests = {}
    wheel_raw = projection_raw = None
    for row in rows:
        _exact(row, ("path", "role", "mode", "bytes", "sha256", "origin"),
               "CORE_EFFECT_PACKAGE_ROW")
        path = _path(row["path"], "CORE_EFFECT_PACKAGE_PATH")
        _require((row["role"] == "approved-inputs" and row["mode"] == 384
                  and path == APPROVED_INPUTS_PATH and manifest.get("schema") == PACKAGE_SCHEMA)
                 or (row["mode"] in (420, 493) and row["role"] in (
                     "candidate-worktree", "candidate-git-metadata", "wheel", "projection", "field-code")),
            "CORE_EFFECT_PACKAGE_ROW")
        view = members.get(path)
        _require(type(view) is bytes or (isinstance(view, memoryview) and view.readonly),
                 "CORE_EFFECT_PACKAGE_MEMBER")
        raw = bytes(view)
        _require(len(raw) == row["bytes"] and _sha(raw) == row["sha256"],
                 "CORE_EFFECT_PACKAGE_MEMBER")
        origin = row["origin"]
        if row["role"] == "approved-inputs":
            # The envelope check above validates its exact descriptor/origin.
            # Private approved facts never become installation/projection input.
            continue
        if row["role"] == "candidate-worktree":
            _exact(origin, ("kind", "commit", "path", "blob"),
                   "CORE_EFFECT_PACKAGE_ORIGIN")
            name = _path(origin["path"], "CORE_EFFECT_PACKAGE_ORIGIN")
            _require(origin["kind"] == "candidate-blob"
                     and origin["commit"] == CANDIDATE["commit"]
                     and path == "candidate/" + name
                     and origin["blob"] == _git_blob(raw)
                     and name not in source_files, "CORE_EFFECT_PACKAGE_ORIGIN")
            source_files[name] = row["sha256"]
            if name in {"tests/e3_host/" + item + ".py" for item in PREPARATION_HELPERS}:
                helper_digests[name.rsplit("/", 1)[-1][:-3]] = row["sha256"]
        elif row["role"] == "candidate-git-metadata":
            _exact(origin, ("kind", "commit", "git_path"),
                   "CORE_EFFECT_PACKAGE_ORIGIN")
            name = _path(origin["git_path"], "CORE_EFFECT_PACKAGE_ORIGIN")
            _require(origin["kind"] == "candidate-git-metadata"
                     and origin["commit"] == CANDIDATE["commit"]
                     and name.startswith(".git/") and path == "candidate/" + name,
                     "CORE_EFFECT_PACKAGE_ORIGIN")
        elif row["role"] in ("wheel", "projection"):
            _exact(origin, ("kind", "basename", "sha256"),
                   "CORE_EFFECT_PACKAGE_ORIGIN")
            expected = WHEEL if row["role"] == "wheel" else PROJECTION
            _require(origin == {"kind": row["role"], "basename": expected["basename"],
                                "sha256": expected["sha256"]},
                     "CORE_EFFECT_PACKAGE_ORIGIN")
            if row["role"] == "wheel":
                _require(wheel_raw is None, "CORE_EFFECT_PACKAGE_ARTIFACT")
                wheel_raw = raw
            else:
                _require(projection_raw is None, "CORE_EFFECT_PACKAGE_ARTIFACT")
                projection_raw = raw
        else:
            _exact(origin, ("kind", "commit", "path", "blob"),
                   "CORE_EFFECT_PACKAGE_ORIGIN")
            _require(origin["kind"] == "implementation-blob"
                     and origin["commit"] == manifest["implementation"]["commit"]
                     and origin["blob"] == _git_blob(raw), "CORE_EFFECT_PACKAGE_ORIGIN")
    _require(set(helper_digests) == set(PREPARATION_HELPERS)
             and wheel_raw is not None and projection_raw is not None,
             "CORE_EFFECT_PACKAGE_REQUIRED")
    projection = document(projection_raw, limit=MEMBER_LIMIT, newline=True)
    _exact(projection, ("schema", "source_commit", "source_tree", "files"),
           "CORE_EFFECT_PROJECTION")
    _require(projection["schema"] == "local-hand-q2-source-projection/v1"
             and projection["source_commit"] == CANDIDATE["commit"]
             and projection["source_tree"] == CANDIDATE["tree"]
             and type(projection["files"]) is dict
             and len(projection["files"]) == PROJECTION["file_count"],
             "CORE_EFFECT_PROJECTION")
    for name, item in projection["files"].items():
        _require(_projection_path(name), "CORE_EFFECT_PROJECTION_PATH")
        _exact(item, ("mode", "sha256"), "CORE_EFFECT_PROJECTION_ENTRY")
        _require(item["mode"] in (420, 493) and source_files.get(name) == item["sha256"],
                 "CORE_EFFECT_PROJECTION_ENTRY")
    _require(PROJECTION_REQUIRED <= set(projection["files"]),
             "CORE_EFFECT_PROJECTION_REQUIRED")
    wheel = _wheel_payload(wheel_raw, source_files)
    return {"source_files": source_files, "projection": projection,
            "wheel_files": wheel["files"], "payload_digest": wheel["payload_digest"],
            "helper_digests": helper_digests,
            "members_sha256": _sha(canonical(rows))}


def _prep_require(condition, code):
    _require(condition, "CORE_EFFECT_PREPARATION_" + code)


def _prep_guard(effects, deadline):
    outer = effects.context["guest_deadlines"]
    active = getattr(effects, "_active_case_deadlines", {})
    pairs = {active.get("preparation_deadline_ns"): active.get("preparation_monotonic_deadline_ns"),
             active.get("owner_deadline_ns"): active.get("owner_monotonic_deadline_ns"),
             active.get("remote_final_deadline_ns"): active.get("remote_final_monotonic_deadline_ns"),
             outer["boottime_deadline_ns"]: outer["monotonic_deadline_ns"]}
    mono = pairs.get(deadline)
    _prep_require(type(mono) is int and deadline <= outer["boottime_deadline_ns"]
             and mono <= outer["monotonic_deadline_ns"], 'CLOCK_BINDING')
    # Original per-case clocks survive suspend; an outer-offset recalculation
    # could incorrectly extend the case's monotonic deadline.
    return _clock(effects, {"boot_id": outer["boot_id"],
        "boottime_deadline_ns": deadline, "monotonic_deadline_ns": mono})


def _prep_settings(case, expires_at):
    b = _budget(case["phases"])
    identity = dict(_identity(case), expires_at=expires_at)
    controllers = {}
    for role in ("target", "supervisor"):
        v = b[role]
        controllers[role] = {"unit": case["controller_prefix"] + "-" + role + ".service",
            "runtime_max_usec": v["runtime_seconds"] * 10**6,
            "timeout_stop_usec": v["stop_seconds"] * 10**6,
            "memory_bytes": v["memory_bytes"], "tasks_max": v["tasks_max"],
            "cpu_quota_per_sec_usec": v["cpu_quota_per_sec_usec"],
            "limit_cpu_seconds": v["runtime_seconds"],
            "storage_bytes": v["storage_bytes"], "storage_inodes": v["storage_inodes"]}
    m = b["management"]
    settings = {"identity": identity, "original_budgets": b["operation"],
        "limits": {"max_queued": 1, "max_running": 1, "retained_bytes": 8388608,
                   "ledger_emergency_bytes": 65536, "requests_per_minute": 1},
        "controllers": controllers,
        "management": {"receive_ns": NS, "stop_ns": NS, "storage_bytes": 1048576,
            "storage_inodes": 64, "accept_ns": NS, "max_connections": 4,
            "stages": {v["stage"]: {"cpu_ns": v["cpu_seconds"] * NS,
                "memory_bytes": v["memory_bytes"], "pids": v["tasks_max"],
                "output_bytes": v["output_bytes"], "runtime_ns": v["runtime_seconds"] * NS}
                       for v in m["stages"]}},
        "capacity_management": {"storage_bytes": m["storage_bytes"],
            "storage_inodes": m["storage_inodes"], "cpu_ns": m["cpu_seconds"] * NS,
            "memory_bytes": m["memory_bytes"], "pids": m["pids"],
            "output_bytes": m["output_bytes"]},
        "owner": {"runtime_ns": OWNER_NS, "cpu_ns": b["owner"]["cpu_seconds"] * NS,
            "memory_bytes": b["owner"]["memory_bytes"], "pids": b["owner"]["tasks_max"],
            "storage_bytes": b["owner"]["storage_bytes"],
            "storage_inodes": b["owner"]["storage_inodes"],
            "output_bytes": b["owner"]["output_bytes"]}}
    if case["index"] != 2:
        settings["schema"] = "local-hand-q2-system-preparation-settings/v1"
    return settings


def _prep_pin(value):
    return {"path": value["path"], "device": value.get("device", value.get("dev")),
            "inode": value.get("inode", value.get("ino"))}


def _prep_make_plan(effects, case, expires_at):
    admission = effects._admission
    detail = getattr(effects, "_admission_detail", None)
    _prep_require(type(detail) is dict and {"quota_mount", "quota_inventory", "retained_before"}
             <= set(detail), 'CURRENT_FACTS_REQUIRED')
    _prep_require(case["index"] == 2 or type(detail.get("system_geometry")) is dict,
             'GEOMETRY_REQUIRED')
    paths = effects.preparation_paths(case, effects.context["manifest"]["locators"])
    guest = admission["guest"]
    retained = _approved_inputs_envelope(effects.context)["retained_preparation"]
    plan = {"schema": "local-hand-q2-system-preparation-plan/v1" if case["index"] != 2
                    else "local-hand-q2-core-preparation-plan/v1",
        "purpose": "ISOLATED_Q2_CORE_PREPARATION", "scope": SCOPE,
        "baseline": BASELINE["commit"], "preparation_id": case["preparation_id"],
        "host": {key: guest[key] for key in ("hostname", "dmi_vendor", "dmi_product", "boot_id")},
        "account": {"name": guest["ordinary_user"], "uid": guest["ordinary_uid"],
                    "gid": guest["ordinary_gid"]},
        "directories": {role: {"path": row["path"], "owner": row["owner"],
            "mode": row["mode"], "filesystem": row["parent_role"]}
            for role, row in paths["directories"].items()},
        "roots": paths["roots"], "candidate": copy.deepcopy(effects._installation_receipt["source"]),
        "retained": copy.deepcopy(retained["paths"]),
        "retained_domains": copy.deepcopy(retained["domains"]),
        "mounts": {"quota": copy.deepcopy(detail["quota_mount"])},
        "tools": {key: {"path": val["path"], "sha256": val["sha256"]}
                  for key, val in admission["programs"].items()},
        "settings": _prep_settings(case, expires_at)}
    plan["host"]["initial_userns"] = {"device": guest["initial_userns"]["dev"],
                                        "inode": guest["initial_userns"]["ino"]}
    if case["index"] != 2:
        plan["retained_ordinary_parent"] = _prep_pin(admission["parents"]["retained_ordinary_cgroup"])
        plan["retained_ordinary_parent"]["path"] = plan["retained_ordinary_parent"]["path"].removeprefix("/sys/fs/cgroup")
    return plan


def _prep_translate(case, plan, receipt, children, helpers):
    """The original candidate constructor is authoritative; only schema changes."""
    driver, assembly = helpers["q2_prepare_driver"], helpers["q2_prepare_assembly"]
    _prep_require(case in CASES and plan["scope"] == SCOPE and plan["baseline"] == BASELINE["commit"]
             and plan["preparation_id"] == case["preparation_id"], 'SCOPE')
    _exact(receipt, ("schema", "preparation_id", "plan_sha256", "status", "reason", "facts",
                    "q2_accepted", "q3_accepted", "production_supported", "fixture_generated"),
           "CORE_EFFECT_PREPARATION_RESULT")
    _prep_require(receipt["schema"] == "local-hand-q2-fixture-preparation/v1"
             and receipt["preparation_id"] == case["preparation_id"]
             and receipt["plan_sha256"] == _sha(driver.encoded(plan))
             and receipt["status"] == "RESOURCES_PREPARED" and receipt["reason"] is None
             and all(receipt[key] is False for key in
                     ("q2_accepted", "q3_accepted", "production_supported", "fixture_generated")),
             'RESULT')
    observed = receipt["facts"]
    _prep_require(observed["retained_before"] == observed["retained_after"],
             'RETAINED_CHANGED')
    authority = {"schema": "local-hand-q2-preparation-authority/v1", "scope": SCOPE,
        "baseline": BASELINE["commit"], "plan_sha256": receipt["plan_sha256"],
        "preparation_id": case["preparation_id"], "receipt_sha256": _sha(driver.encoded(receipt))}
    original, bound, manifest = driver.facts_from_observed(plan, observed, children, authority)
    _prep_require(bound == authority, 'AUTHORITY_CHANGED')
    facts = copy.deepcopy(original)
    schemas = {1: "local-hand-q2-system-assembly-facts/v1",
               2: "local-hand-q4-cancel-assembly-facts/v1", 3: "local-hand-q4-h11-assembly-facts/v1"}
    _prep_require(original["schema"] == ("local-hand-q2-assembly-facts/v1" if case["index"] == 2
             else "local-hand-q2-system-assembly-facts/v1"), 'SCHEMA')
    facts["schema"] = schemas[case["index"]]
    assembled = assembly.assemble(facts)
    return {"facts": facts, "authority": authority, "manifest": manifest, "assembled": assembled}




class _PrepIO:
    """Guard each syscall; retain late-opened fds for release, never retry I/O."""
    def __init__(self, effects, deadline):
        self.effects, self.deadline, self.fds = effects, deadline, []

    def call(self, function, *args, **kwargs):
        _prep_guard(self.effects, self.deadline)
        value = function(*args, **kwargs)
        _prep_guard(self.effects, self.deadline)
        return value

    def open(self, *args, **kwargs):
        _prep_guard(self.effects, self.deadline)
        fd = os.open(*args, **kwargs)
        self.fds.append(fd)
        _prep_guard(self.effects, self.deadline)
        return fd

    def directory(self, path):
        FieldEffects._absolute(path, "CORE_EFFECT_PREPARATION_PATH")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = self.open("/", flags)
        for part in PurePosixPath(path).parts[1:]:
            child = self.open(part, flags, dir_fd=fd)
            self.fds.remove(fd)
            os.close(fd)
            fd = child
        return fd

    def __enter__(self):
        return self

    def __exit__(self, *_):
        for fd in reversed(self.fds):
            os.close(fd)


def _prep_directory(effects, path, uid, gid, mode, deadline):
    with _PrepIO(effects, deadline) as io:
        parent = io.directory(str(PurePosixPath(path).parent))
        name = PurePosixPath(path).name
        io.call(os.mkdir, name, mode, dir_fd=parent)
        fd = io.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                     dir_fd=parent)
        io.call(os.fchown, fd, uid, gid)
        io.call(os.fchmod, fd, mode)
        io.call(os.fsync, fd)
        io.call(os.fsync, parent)
        info = io.call(os.fstat, fd)
        named = io.call(os.stat, name, dir_fd=parent, follow_symlinks=False)
        _prep_require((info.st_dev, info.st_ino) == (named.st_dev, named.st_ino)
                 and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, mode),
                 'DIRECTORY_OWNER')
        return {"path": path, "device": info.st_dev, "inode": info.st_ino,
                "uid": uid, "gid": gid, "mode": info.st_mode}


def _prep_file(effects, path, raw, deadline, *, uid=0, gid=0):
    _prep_require(type(raw) is bytes and len(raw) <= MEMBER_LIMIT,
             'FILE_LIMIT')
    with _PrepIO(effects, deadline) as io:
        parent = io.directory(str(PurePosixPath(path).parent))
        name = PurePosixPath(path).name
        fd = io.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NOATIME,
                     0o600, dir_fd=parent)
        io.call(os.fchown, fd, uid, gid)
        io.call(os.fchmod, fd, 0o600)
        view = memoryview(raw)
        while view:
            count = io.call(os.write, fd, view)
            _prep_require(count > 0, 'SHORT_WRITE')
            view = view[count:]
        io.call(os.fsync, fd)
        io.call(os.fsync, parent)
        info = io.call(os.fstat, fd)
        reread = io.call(os.pread, fd, len(raw) + 1, 0)
        _prep_require(reread == raw and info.st_nlink == 1 and stat.S_ISREG(info.st_mode)
                 and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, 384),
                 'FILE')
        identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        named = io.call(os.stat, name, dir_fd=parent, follow_symlinks=False)
        _prep_require((named.st_dev, named.st_ino, named.st_size, named.st_mtime_ns, named.st_ctime_ns)
                 == identity, 'SOURCE_CHANGED')
        result = {"path": path, "fd": fd, "identity": identity, "raw": raw,
                  "uid": uid, "gid": gid}
        effects.held.append(fd)
        io.fds.remove(fd)
        return result


def _prep_reread(effects, record, deadline):
    with _PrepIO(effects, deadline) as io:
        before = io.call(os.fstat, record["fd"])
        raw = io.call(os.pread, record["fd"], len(record["raw"]) + 1, 0)
        parent = io.directory(str(PurePosixPath(record["path"]).parent))
        named = io.call(os.stat, PurePosixPath(record["path"]).name,
                        dir_fd=parent, follow_symlinks=False)
        after = io.call(os.fstat, record["fd"])
        for info in (before, named, after):
            _prep_require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                     == record["identity"] and info.st_nlink == 1 and stat.S_ISREG(info.st_mode)
                     and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
                     == (record["uid"], record["gid"], 384) and raw == record["raw"],
                     'SOURCE_CHANGED')
        return raw


def _prep_quota(source, command, project, values=None):
    """Share the verified read ABI; this mutator accepts only fixed new limits."""
    _prep_require(command in (0x800007, 0x800008), 'QUOTA_ABI')
    if command == 0x800008:
        _prep_require(project in {i for c in CASES for i in c["project_ids"]}
                 and values == {"hard": 1024, "ihard": 128, "valid": 5},
                 'QUOTA_MUTATION')
    quota = _CapQuota(source)
    if command == 0x800007:
        _prep_require(values is None, 'QUOTA_MUTATION')
        return quota.block(project)
    block = quota.Block()
    for key, value in values.items(): setattr(block, key, value)
    quota.ct.set_errno(0)
    if quota.lib.quotactl(quota.ct.c_int((command << 8) | 2), quota.device,
                         quota.ct.c_int(project), quota.ct.byref(block)):
        raise OSError(quota.ct.get_errno(), "core project quota operation")
    return {name: getattr(block, name) for name, _ in block._fields_}




def _prep_quota_retained(rows):
    result = copy.deepcopy(rows)
    for row in result:
        # Ordinary unassigned directories are charged to project zero before
        # assignment. Only that unconstrained domain's own usage may advance;
        # all configured limits and every nonzero historical row stay exact.
        if row["project"] == 0 and all(row[key] == 0 for key in ("hard", "soft", "ihard", "isoft")):
            row["space"] = row["inodes"] = 0
    return result


def _prep_root(effects, planned, account, mount, deadline):
    import errno
    import fcntl
    project = planned["project_id"]
    _prep_require(project in {i for c in CASES for i in c["project_ids"]}
             and planned["hard_bytes"] == 1048576 and planned["inode_hard_limit"] == 128,
             'QUOTA_MUTATION')
    with _PrepIO(effects, deadline) as io:
        try:
            old = io.call(_prep_quota, mount["source"], 0x800007, project)
        except OSError as error:
            if error.errno != errno.ESRCH: raise
            old = {}
        _prep_require(all(v == 0 for k, v in old.items() if k not in ("valid", "project")),
                 'PROJECT_EXISTS')
        created = _prep_directory(effects, planned["path"], account["uid"], account["gid"], 448, deadline)
        fd = io.directory(planned["path"])
        values = list(struct.unpack("=IIIII8s", io.call(fcntl.ioctl, fd, 0x801c581f, bytes(28))))
        _prep_require(values[3] == 0, 'INHERITED_PROJECT')
        values[0] |= 512
        values[3] = project
        io.call(fcntl.ioctl, fd, 0x401c5820, struct.pack("=IIIII8s", *values))
        assigned = io.call(_prep_quota, mount["source"], 0x800007, project)
        _prep_require(assigned["inodes"] == 1 and all(assigned[k] == 0 for k in
                 ("hard", "soft", "ihard", "isoft", "btime", "itime")),
                 'PROJECT_ASSIGNMENT')
        io.call(_prep_quota, mount["source"], 0x800008, project,
                {"hard": 1024, "ihard": 128, "valid": 5})
        io.call(os.fsync, fd)
        flags, _, _, actual, _, _ = struct.unpack("=IIIII8s", io.call(fcntl.ioctl, fd, 0x801c581f, bytes(28)))
        quota = io.call(_prep_quota, mount["source"], 0x800007, project)
        for info in (io.call(os.fstat, fd), io.call(os.stat, planned["path"], follow_symlinks=False)):
            _prep_require((info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode)
                     == tuple(created[k] for k in ("device", "inode", "uid", "gid", "mode")),
                     'ROOT_CHANGED')
        _prep_require(actual == project and flags & 512 and quota["valid"] & 5 == 5
                 and quota["hard"] == 1024 and quota["ihard"] == 128
                 and io.call(effects._capacity_quota_enforcement) & 48 == 48,
                 'QUOTA_ENFORCEMENT')
        return dict(planned, **{k: v for k, v in created.items() if k != "path"},
                    filesystem="ext4", filesystem_uuid=mount["uuid"], xflags=flags,
                    accounting=True, enforcement=True, identity_unchanged=True)


def _prep_initialize(effects, prepared, deadline):
    facts, assembled = prepared["facts"], prepared["assembled"]
    uid, gid = facts["ordinary"]["uid"], facts["ordinary"]["gid"]
    policy = canonical(assembled["policy"], newline=True)
    sources = prepared["source_objects"]
    sources["policy"] = _prep_file(effects, facts["paths"]["policy"], policy, deadline, uid=uid, gid=gid)
    authority = {"authority_id": facts["identity"]["authority_id"],
        "ledger_id": facts["identity"]["ledger_id"], "state_root": facts["paths"]["broker_root"]}
    sources["authority"] = _prep_file(effects, facts["paths"]["authority_root"] + "/authority.json",
        canonical(authority, newline=True), deadline, uid=uid, gid=gid)
    name = "tests/e3_host/q2_prepare_assembly.py"
    # Execute the fixed projected constructor as the ordinary identity, not
    # its CLI (which would require the deliberately unprojected contract).
    program = """import hashlib,importlib.util,json,os,stat,sys
source,expected,policy,digest,ledger,tools,installed=sys.argv[1:]
def read(path,limit,owner,digest):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  before=os.fstat(fd); raw=os.read(fd,limit+1); after=os.fstat(fd)
  assert all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
  assert stat.S_ISREG(after.st_mode) and after.st_nlink==1
  assert after.st_uid==owner and not after.st_mode&18
  assert path!=policy or (stat.S_IMODE(after.st_mode)==384 and after.st_gid==os.getgid())
  assert len(raw)<=limit and hashlib.sha256(raw).hexdigest()==digest
  return raw
 finally: os.close(fd)
raw=read(source,262144,0,expected)
payload=read(policy,65536,os.getuid(),digest)
sys.path[:0]=[installed,tools]
module=importlib.util.module_from_spec(importlib.util.spec_from_file_location('_core_ledger',source))
exec(compile(raw,source,'exec'),module.__dict__)
value=module.initialize_ledger(json.loads(payload),ledger)
print(json.dumps(value,sort_keys=True,separators=(',',':')))
"""
    argv = [facts["setpriv"]["path"], "--reuid=" + str(uid), "--regid=" + str(gid),
        "--clear-groups", "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all",
        "--no-new-privs", facts["installation"]["programs"]["python"]["path"], "-I", "-B", "-c",
        program, facts["source"]["root"] + "/" + name, facts["source"]["files"][name],
        facts["paths"]["policy"], _sha(policy), facts["identity"]["ledger_id"],
        facts["source"]["root"] + "/tools", facts["installation"]["package_root"]]
    original = effects._effect_guard
    def guard():
        _prep_guard(effects, deadline)
        return original()
    effects._effect_guard = guard
    try:
        ledger = document(effects._installation_command(argv), limit=32768)
    finally:
        effects._effect_guard = original
    _exact(ledger, ("path", "device", "inode", "uid", "mode", "ledger_id", "generation"),
           "CORE_EFFECT_PREPARATION_LEDGER")
    _prep_require(ledger["path"] == facts["paths"]["broker_root"] + "/jobs.sqlite"
             and ledger["uid"] == uid and ledger["mode"] == 384
             and ledger["ledger_id"] == facts["identity"]["ledger_id"]
             and ledger["generation"] == assembled["chain"]["broker_generation"],
             'LEDGER')
    with _PrepIO(effects, deadline) as io:
        info = io.call(os.stat, ledger["path"], follow_symlinks=False)
        _prep_require((info.st_dev, info.st_ino, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
                 == (ledger["device"], ledger["inode"], uid, gid, 384)
                 and stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                 'LEDGER')
    result = dict(schema="local-hand-q2-preparation-result/v1", status="PREPARED",
        source_commit=facts["source"]["commit"], preparation_id=prepared["case"]["preparation_id"],
        policy={"path": facts["paths"]["policy"], "sha256": _sha(policy)}, ledger=ledger,
        authority_sha256=_sha(canonical(prepared["authority"], newline=True)),
        manifest_sha256=_sha(canonical(prepared["manifest"], newline=True)),
        q2_accepted=False, q3_accepted=False, production_supported=False)
    _prep_file(effects, prepared["paths"]["reservation"] + "/prepared.json",
               canonical(result, newline=True), deadline)
    prepared["prepared_result"] = result




def _plan_from_prepared(case, prepared, deadlines):
    facts, assembled = prepared["facts"], prepared["assembled"]
    identity = facts["identity"]
    _require(all(identity.get(key) == val for key, val in _identity(case).items()),
             "CORE_EFFECT_PLAN_IDENTITY")
    by_project = {root["project_id"]: root for root in prepared["receipt"]["facts"]["roots"]}
    wrappers = []
    for planned in _planned_roots(case):
        root = by_project.get(planned["project_id"])
        _require(root is not None, "CORE_EFFECT_PLAN_ROOT")
        observed = {key: root[key] for key in ("path", "role", "device", "inode", "uid", "gid",
            "mode", "filesystem", "filesystem_uuid", "project_id", "xflags", "hard_bytes",
            "accounting", "enforcement", "identity_unchanged")}
        actual = next(r for r in prepared["plan"]["roots"] if r["project_id"] == planned["project_id"])
        _require(observed["path"] == actual["path"], "CORE_EFFECT_PLAN_ROOT_PATH")
        # The case-plan's path is relative; the preparation preimage retains the
        # matching absolute root. No observed identity/quota field is replaced.
        observed["path"] = planned["path"]
        observed["hard_inodes"] = root["inode_hard_limit"]
        wrappers.append({"ref": planned["ref"], "slot": planned["slot"],
                         "planned": planned, "observed": observed})
    ledger_path = facts["paths"]["broker_root"] + "/jobs.sqlite"
    plan = {"schema": PLAN_SCHEMA, **{k: build_intent(case)[k] for k in
        ("session_id", "index", "case_id", "kind", "predecessor", "preparation_id", "operation_id", "budgets")},
        "identity": copy.deepcopy(identity), "principal": copy.deepcopy(assembled["resident"]["principal"]),
        "authority_path": facts["paths"]["authority_root"] + "/authority.json", "ledger_path": ledger_path,
        "request": copy.deepcopy(assembled["resident"]["request"]), "roots": wrappers,
        "controllers": copy.deepcopy(facts["controllers"]),
        "system_geometry": copy.deepcopy(facts.get("system_geometry")),
        "phases": _phase_units(case["operation_id"], case["phases"]),
        "empty_ledger_expectation": {"ledger_path": ledger_path, "authority_id": identity["authority_id"],
            "ledger_id": identity["ledger_id"], "expected_operations": 0, "expected_events": 0,
            "expected_leases": 0, "expected_sidecars": []}, "deadlines": dict(deadlines)}
    return validate_plan(case, build_intent(case), plan, deadlines)




































# Historical role vector reconstructs the exact approved 4549-byte placement
# preimage; it never takes its roles from current filesystem observations.








class _CapQuota:
    """The candidate's bounded Linux project quota observation UAPI only."""
    def __init__(self, source):
        import ctypes
        import platform
        _require(platform.system() == 'Linux' and platform.machine() == 'x86_64',
                 'CORE_CAP_QUOTA_ABI')
        self.ct = ctypes
        class Block(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ('hard', 'soft', 'space', 'ihard', 'isoft', 'inodes', 'btime', 'itime')]
            _fields_ += [('valid', ctypes.c_uint32), ('project', ctypes.c_uint32)]
        self.Block = Block
        _require(ctypes.sizeof(Block) == 72, 'CORE_CAP_QUOTA_ABI')
        self.lib = ctypes.CDLL(None, use_errno=True)
        self.lib.quotactl.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        self.lib.quotactl.restype = ctypes.c_int
        self.device = os.fsencode(source)

    def call(self, command, project, buffer):
        _require(command in (0x800007, 0x800009, (ord('X') << 8) | 8), 'CORE_CAP_QUOTA_READ_ONLY')
        self.ct.set_errno(0)
        if self.lib.quotactl(self.ct.c_int((command << 8) | 2), self.device,
                             self.ct.c_int(project), self.ct.byref(buffer)):
            raise OSError(self.ct.get_errno(), 'quota observation failed')

    def block(self, project):
        value = self.Block(); self.call(0x800007, project, value)
        return {key: getattr(value, key) for key, _ in value._fields_ if key != 'project'}

    def unused(self, project):
        import errno
        try:
            value = self.block(project)
        except OSError as error:
            if error.errno == errno.ESRCH:
                return
            raise
        _require(all(number == 0 for key, number in value.items() if key != 'valid'),
                 'CORE_CAP_PROJECT_OCCUPIED')

    def inventory(self, guard):
        import errno
        rows = []; start = 0
        for _ in range(128):
            guard(); value = self.Block()
            try:
                self.call(0x800009, start, value)
            except OSError as error:
                if error.errno == errno.ENOENT:
                    return rows
                raise
            guard()
            _require(start <= value.project < 2**32 - 1, 'CORE_CAP_QUOTA_ORDER')
            rows.append({key: getattr(value, key) for key, _ in value._fields_})
            start = value.project + 1
        raise DispatchError('CORE_CAP_QUOTA_INVENTORY_LIMIT')

    def enforcement(self):
        buffer = self.ct.create_string_buffer(160); buffer[0] = b'\x01'
        self.call((ord('X') << 8) | 8, 0, buffer)
        raw = bytes(buffer); flags = int.from_bytes(raw[2:4], 'little')
        _require(raw[0] == 1 and flags & 48 == 48, 'CORE_CAP_QUOTA_ENFORCEMENT')
        return flags




class FieldEffects:
    """Inert construction; protected fd-relative effects. See field_readiness gaps."""

    def __init__(self, context):
        self.context = context
        self.held = []
        self._admission = None
        self._installation = None
        self._candidate_root = None
        self._persistence_ready = False
        self._installation_receipt = None
        self._install_roots = []
        self._install_temp = None
        self._install_commands = []
        self._shared_observed_bytes = 0
        self._shared_observed_inodes = 0
        self._venv_alias_pending = False
        self._started_boottime_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        self._started_cpu_ns = time.process_time_ns()
        self._unit_counts = {"job_units_started": 0, "controller_units_started": 0,
                             "quota_query_units_started": 0,
                             "dynamic_quota_units_started": 0,
                             "native_children_started": 0}

    def close(self):
        while self.held:
            os.close(self.held.pop())

    def readiness(self):
        return field_readiness()

    def now(self):
        parent = self._held_directory("/proc/sys/kernel/random")
        try:
            fd = os.open("boot_id", os.O_RDONLY | os.O_CLOEXEC
                         | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent)
            try:
                before = os.fstat(fd)
                raw = os.read(fd, 65)
                _require(len(raw) <= 64 and os.read(fd, 1) == b"",
                         "CORE_EFFECT_BOOT_ID")
                after = os.fstat(fd)
                _require(stat.S_ISREG(before.st_mode)
                         and (before.st_dev, before.st_ino, before.st_mode)
                         == (after.st_dev, after.st_ino, after.st_mode),
                         "CORE_EFFECT_BOOT_ID")
            finally:
                os.close(fd)
        finally:
            os.close(parent)
        try:
            boot_id = raw.decode("ascii", "strict").strip()
        except UnicodeError as error:
            raise DispatchError("CORE_EFFECT_BOOT_ID") from error
        _require(re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
                              boot_id) is not None, "CORE_EFFECT_BOOT_ID")
        return {"boot_id": boot_id,
                "boottime_ns": time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                "monotonic_ns": time.clock_gettime_ns(time.CLOCK_MONOTONIC)}

    @staticmethod
    def _absolute(path, code="CORE_EFFECT_ABSOLUTE_PATH"):
        _require(type(path) is str and path.isascii() and path.startswith("/")
                 and not path.startswith("//") and len(path) <= 4096
                 and "\\" not in path and "\0" not in path, code)
        parsed = PurePosixPath(path)
        _require(parsed.as_posix() == path and all(part not in ("", ".", "..")
                                                   for part in parsed.parts[1:]), code)
        return parsed

    @staticmethod
    def _held_directory(path):
        """Walk an absolute directory from a held slash fd without symlinks."""
        parsed = FieldEffects._absolute(path)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
        current = os.open("/", flags)
        try:
            for component in parsed.parts[1:]:
                following = os.open(component, flags, dir_fd=current)
                os.close(current)
                current = following
            info = os.fstat(current)
            _require(stat.S_ISDIR(info.st_mode), "CORE_EFFECT_DIRECTORY")
            return current
        except BaseException:
            os.close(current)
            raise

    @staticmethod
    def stable_read_at(directory_fd, name, *, maximum, expected_mode=None,
                       noatime=True):
        _require(type(directory_fd) is int and type(name) is str
                 and re.fullmatch(r"[A-Za-z0-9._-]+", name) is not None
                 and type(maximum) is int and 0 <= maximum <= MEMBER_LIMIT,
                 "CORE_EFFECT_READ_INPUT")
        flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
        if noatime:
            flags |= getattr(os, "O_NOATIME", 0)
        fd = os.open(name, flags, dir_fd=directory_fd)
        try:
            before = os.fstat(fd)
            _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                     and 0 <= before.st_size <= maximum, "CORE_EFFECT_READ_FILE")
            if expected_mode is not None:
                _require(stat.S_IMODE(before.st_mode) == expected_mode,
                         "CORE_EFFECT_READ_MODE")
            raw = bytearray()
            while len(raw) <= maximum:
                part = os.read(fd, min(65536, maximum + 1 - len(raw)))
                if not part:
                    break
                raw.extend(part)
            after = os.fstat(fd)
            stable = lambda value: (value.st_dev, value.st_ino, value.st_mode,
                                    value.st_uid, value.st_gid, value.st_nlink,
                                    value.st_size, value.st_mtime_ns, value.st_ctime_ns)
            _require(len(raw) <= maximum and stable(before) == stable(after)
                     and len(raw) == after.st_size, "CORE_EFFECT_READ_CHANGED")
            result = bytes(raw)
            return result, {"dev": after.st_dev, "ino": after.st_ino,
                            "mode": stat.S_IMODE(after.st_mode), "uid": after.st_uid,
                            "gid": after.st_gid, "nlink": after.st_nlink,
                            "bytes": after.st_size, "sha256": _sha(result)}
        finally:
            os.close(fd)

    @staticmethod
    def stable_read(path, *, maximum, expected_mode=None, noatime=True):
        parsed = FieldEffects._absolute(path)
        _require(len(parsed.parts) > 1, "CORE_EFFECT_READ_PATH")
        parent = FieldEffects._held_directory(str(parsed.parent))
        try:
            return FieldEffects.stable_read_at(parent, parsed.name, maximum=maximum,
                                               expected_mode=expected_mode,
                                               noatime=noatime)
        finally:
            os.close(parent)

    @staticmethod
    def create_only_at(directory_fd, name, raw, *, mode):
        _require(type(directory_fd) is int and type(name) is str
                 and re.fullmatch(r"[A-Za-z0-9._-]+", name) is not None
                 and type(raw) is bytes and mode in (384, 420, 493),
                 "CORE_EFFECT_CREATE_INPUT")
        parent_before = os.fstat(directory_fd)
        _require(stat.S_ISDIR(parent_before.st_mode), "CORE_EFFECT_CREATE_PARENT")
        flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
                 | getattr(os, "O_NOFOLLOW", 0))
        fd = os.open(name, flags, mode, dir_fd=directory_fd)
        created = None
        try:
            os.fchmod(fd, mode)
            offset = 0
            while offset < len(raw):
                wrote = os.write(fd, raw[offset:])
                _require(wrote > 0, "CORE_EFFECT_CREATE_WRITE")
                offset += wrote
            os.fsync(fd)
            created = os.fstat(fd)
            _require(stat.S_ISREG(created.st_mode) and created.st_nlink == 1
                     and created.st_size == len(raw)
                     and stat.S_IMODE(created.st_mode) == mode,
                     "CORE_EFFECT_CREATE_FILE")
        finally:
            os.close(fd)
        reread, identity = FieldEffects.stable_read_at(
            directory_fd, name, maximum=len(raw), expected_mode=mode)
        _require(reread == raw and created is not None
                 and (identity["dev"], identity["ino"]) == (created.st_dev, created.st_ino),
                 "CORE_EFFECT_CREATE_REREAD")
        os.fsync(directory_fd)
        parent_after = os.fstat(directory_fd)
        _require((parent_before.st_dev, parent_before.st_ino)
                 == (parent_after.st_dev, parent_after.st_ino),
                 "CORE_EFFECT_CREATE_PARENT_CHANGED")
        return identity

    @staticmethod
    def create_only(path, raw, *, mode):
        parsed = FieldEffects._absolute(path)
        _require(len(parsed.parts) > 1, "CORE_EFFECT_CREATE_PATH")
        parent = FieldEffects._held_directory(str(parsed.parent))
        try:
            return FieldEffects.create_only_at(parent, parsed.name, raw, mode=mode)
        finally:
            os.close(parent)

    def verify_install_inputs(self):
        return verify_install_inputs(self.context)

    @staticmethod
    def preparation_paths(case, locators):
        """Map A's relative intents to fixed absolute candidate preparation paths."""
        _prep_require(case in CASES and type(locators) is dict,
                 'PATH_INPUT')
        parents = {role: locators.get(role + "_parent")
                   for role in ("state", "quota", "journal", "evidence")}
        for value in parents.values():
            FieldEffects._absolute(value, "CORE_EFFECT_PREPARATION_PARENT")
        _prep_require(len(set(parents.values())) == len(parents),
                 'PARENT_ALIAS')
        directories = {}
        for row in _planned_directories(case):
            relative = PurePosixPath(row["relative_path"])
            target = PurePosixPath(parents[row["parent_role"]]).joinpath(relative)
            directories[row["role"]] = dict(row, path=target.as_posix())
        roots = []
        for planned in _planned_roots(case):
            role = "store_parent" if planned["slot"] == "store" else \
                "profile_" + planned["role"]
            basename = PurePosixPath(planned["path"]).name
            roots.append(dict(planned, path=(PurePosixPath(directories[role]["path"])
                                              / basename).as_posix()))
        _prep_require(len({row["path"] for row in directories.values()}) == len(DIRECTORY_ROLES)
                 and len({row["path"] for row in roots}) == 7,
                 'PATH_ALIAS')
        return {"directories": directories, "roots": roots}

    def _persistence_path(self, case_id, logical):
        _path(logical, "CORE_EFFECT_PERSIST_LOGICAL")
        locators = self.context["manifest"]["locators"]
        if logical.startswith("carrier/"):
            suffix = logical.split("/", 1)[1]
            _require("/" not in suffix, "CORE_EFFECT_PERSIST_LOGICAL")
            return str(PurePosixPath(locators["state_parent"]) / SESSION / "carrier" / suffix)
        prefix = "cases/" + case_id + "/"
        _require(case_id in {case["case_id"] for case in CASES}
                 and logical.startswith(prefix), "CORE_EFFECT_PERSIST_CASE")
        suffix = logical[len(prefix):]
        if suffix == "intent.json":
            return str(PurePosixPath(locators["state_parent"]) / SESSION / "carrier"
                       / "intents" / (case_id + ".json"))
        _require(suffix.startswith("reservation/")
                 and "/" not in suffix[len("reservation/"):],
                 "CORE_EFFECT_PERSIST_LOGICAL")
        return str(PurePosixPath(locators["state_parent"]) / SESSION / case_id
                   / "reservation" / suffix[len("reservation/"):])













    def admit(self, _expected):
        raise DispatchError("CORE_EFFECT_ADMISSION_COLLECTOR_INCOMPLETE")

    def install(self, expected):
        _exact(expected, ("manifest", "members", "admission"),
               "CORE_EFFECT_INSTALLATION_INPUT")
        verified = self.verify_install_inputs()
        _require(self._admission is not None and expected["admission"] == self._admission,
                 "CORE_EFFECT_INSTALLATION_ADMISSION_REQUIRED")
        _require(expected["manifest"] == self.context["manifest"]
                 and expected["members"] == self.context["members"]
                 and self._installation is None and self._candidate_root is None,
                 "CORE_EFFECT_INSTALLATION_BINDING")
        _require(os.geteuid() == os.getegid() == 0, "CORE_EFFECT_INSTALLATION_OWNER")
        self._effect_guard()
        self._verify_install_programs()
        manifest = self.context["manifest"]
        locators = manifest["locators"]
        parent = self._held_directory(locators["install_parent"])
        try:
            parent_pin = self._admission["parents"]["install"]
            info = os.fstat(parent)
            _require((info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode),
                      info.st_uid, info.st_gid) ==
                     (parent_pin["dev"], parent_pin["ino"], parent_pin["mode"],
                      parent_pin["uid"], parent_pin["gid"]),
                     "CORE_EFFECT_INSTALLATION_PARENT_CHANGED")
            # Both names must be absent before the first mutation. O_EXCL
            # remains authoritative if another writer races this observation.
            for name in (STAGING_BASENAME, INSTALL_BASENAME):
                try:
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise DispatchError("CORE_EFFECT_INSTALLATION_EXISTS")
            self._prepare_carrier_storage()
            self._effect_guard()
            staging_fd = self._mkdir_at(parent, STAGING_BASENAME, 0o700)
        finally:
            os.close(parent)
        staging = str(PurePosixPath(locators["install_parent"]) / STAGING_BASENAME)
        destination = str(PurePosixPath(locators["install_parent"]) / INSTALL_BASENAME)
        self._install_roots = [staging, destination]
        try:
            self._effect_guard()
            temporary_fd = self._mkdir_at(staging_fd, ".build-tmp", 0o700)
            os.close(temporary_fd)
            self._effect_guard()
            self._install_temp = staging + "/.build-tmp"
            self._extract_install_members(staging_fd)
        finally:
            os.close(staging_fd)
        self._candidate_root = staging + "/candidate"
        self._observe_install_storage()
        build = self._candidate_helper("q2_prepare_build", verified)
        wheel_row = next(row for row in manifest["members"] if row["role"] == "wheel")
        programs = self._admission["programs"]
        guest = self._admission["guest"]
        self._effect_guard()
        receipt = build.install_candidate(
            source=self._candidate_root, source_commit=CANDIDATE["commit"],
            source_tree=CANDIDATE["tree"], wheel=staging + "/" + wheel_row["path"],
            wheel_sha256=WHEEL["sha256"], destination=destination,
            python=programs["python"]["path"], compiler=programs["cc"]["path"],
            ordinary_uid=guest["ordinary_uid"], ordinary_gid=guest["ordinary_gid"],
            command=self._installation_command)
        self._effect_guard()
        self._verify_install_programs()
        _require(type(receipt) is dict and receipt.get("status") == "INSTALLED"
                 and receipt.get("ordinary_verified") is True
                 and receipt.get("fixture_provisioned") is False
                 and receipt["source"]["commit"] == CANDIDATE["commit"]
                 and receipt["source"]["tree"] == CANDIDATE["tree"]
                 and receipt["source"]["manifest_sha256"] == PROJECTION["sha256"]
                 and receipt["installed"]["payload_digest"] == verified["payload_digest"],
                 "CORE_EFFECT_INSTALLATION_RECEIPT")
        projection_raw, _ = self.stable_read(
            destination + "/source/.local-hand-source-projection.json", maximum=262144)
        _require(_sha(projection_raw) == PROJECTION["sha256"],
                 "CORE_EFFECT_INSTALLATION_PROJECTION")
        # Only the dispatcher D blob is installed alongside the frozen
        # candidate. Private approved inputs stay exclusively in bootstrap RAM.
        installed_fd = self._held_directory(destination)
        try:
            self._effect_guard()
            self.create_only_at(installed_fd, "core-dispatcher.py",
                                bytes(self.context["members"]["field/dispatcher.py"]), mode=420)
            self._effect_guard()
            info = os.fstat(installed_fd)
        finally:
            os.close(installed_fd)
        observed = self._observe_install_storage()
        self._effect_guard()
        self._installation_receipt = receipt
        result = {"destination": destination, "staging": staging,
                  "receipt_path": str(PurePosixPath(locators["state_parent"]) / SESSION
                                      / "carrier" / "installation.json"),
                  "dev": info.st_dev, "ino": info.st_ino,
                  "mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid,
                  "members_sha256": verified["members_sha256"],
                  "native_sha256": receipt["native_build"]["program"]["sha256"],
                  "projection_sha256": PROJECTION["sha256"], "wheel_sha256": WHEEL["sha256"],
                  "allocated_bytes": observed["bytes"], "allocated_inodes": observed["inodes"],
                  "status": "INSTALLED"}
        self._installation = _validate_installation(result, manifest)
        return self._installation

    def _effect_guard(self):
        # A reserves the final 45 seconds for bounded stop/final output only.
        # Installation, extraction and new child work cannot borrow it. Keep
        # the original outer deadlines unchanged for the remote finalizer.
        outer = self.context["guest_deadlines"]
        return _clock(self, {
            "boot_id": outer["boot_id"],
            "boottime_deadline_ns": outer["boottime_deadline_ns"] - REMOTE_FINAL_RESERVE_NS,
            "monotonic_deadline_ns": outer["monotonic_deadline_ns"] - REMOTE_FINAL_RESERVE_NS,
        })

    def _prepare_carrier_storage(self):
        _require(not self._persistence_ready and self._admission is not None,
                 "CORE_EFFECT_CARRIER_STORAGE_STATE")
        parent = self._held_directory(self.context["manifest"]["locators"]["state_parent"])
        opened = [parent]
        try:
            expected = self._admission["parents"]["state"]
            info = os.fstat(parent)
            _require((info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid)
                     == (expected["dev"], expected["ino"], expected["mode"],
                         expected["uid"], expected["gid"]), "CORE_EFFECT_CARRIER_PARENT_CHANGED")
            for name, mode in ((SESSION, 0o755), ("carrier", 0o700), ("intents", 0o700)):
                self._effect_guard()
                parent = self._mkdir_at(parent, name, mode)
                opened.append(parent)
                self._effect_guard()
            self._persistence_ready = True
        finally:
            for fd in reversed(opened):
                os.close(fd)

    def _verify_install_programs(self):
        _require(self._admission is not None, "CORE_EFFECT_INSTALLATION_ADMISSION_REQUIRED")
        for name in ("python", "git", "cc", "setpriv", "systemctl", "systemd_run"):
            expected = self._admission["programs"][name]
            self._effect_guard()
            raw, identity = self.stable_read(expected["path"], maximum=MEMBER_LIMIT,
                                             expected_mode=expected["mode"])
            _require(dict(path=expected["path"], **identity) == expected
                     and identity["uid"] == 0 and not identity["mode"] & 0o6022
                     and identity["mode"] & 0o111 and raw.startswith(b"\x7fELF"),
                     "CORE_EFFECT_INSTALL_PROGRAM_CHANGED")
        _require(self._admission["programs"]["git"]["path"] == "/usr/bin/git"
                 and self._admission["programs"]["setpriv"]["path"] == "/usr/bin/setpriv",
                 "CORE_EFFECT_INSTALL_PROGRAM_ALIAS")

    @staticmethod
    def _mkdir_at(parent, name, mode):
        _require(type(name) is str and re.fullmatch(r"[A-Za-z0-9._-]+", name)
                 and name not in (".", "..") and mode in (0o700, 0o755),
                 "CORE_EFFECT_MKDIR_INPUT")
        os.mkdir(name, mode, dir_fd=parent)
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                     dir_fd=parent)
        try:
            os.fchmod(fd, mode)
            info = os.fstat(fd)
            _require(info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == mode,
                     "CORE_EFFECT_MKDIR_OWNER")
            os.fsync(fd)
            os.fsync(parent)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _extract_install_members(self, staging_fd):
        directories = {"": staging_fd}
        try:
            for row in self.context["manifest"]["members"]:
                self._effect_guard()
                # This private source relation must never reach installation,
                # ordinary projection, sys.path or public output.
                if row["role"] == "approved-inputs":
                    continue
                relative = PurePosixPath(_path(row["path"], "CORE_EFFECT_INSTALL_MEMBER_PATH"))
                for index in range(1, len(relative.parts)):
                    name = PurePosixPath(*relative.parts[:index]).as_posix()
                    if name not in directories:
                        previous = PurePosixPath(*relative.parts[:index - 1]).as_posix()
                        self._effect_guard()
                        directories[name] = self._mkdir_at(
                            directories["" if previous == "." else previous],
                            relative.parts[index - 1], 0o700)
                        self._effect_guard()
                parent_name = relative.parent.as_posix()
                fd = directories["" if parent_name == "." else parent_name]
                raw = bytes(self.context["members"][row["path"]])
                _require(len(raw) == row["bytes"] and _sha(raw) == row["sha256"],
                         "CORE_EFFECT_INSTALL_MEMBER_CHANGED")
                self._effect_guard()
                self.create_only_at(fd, relative.name, raw, mode=row["mode"])
                self._effect_guard()
                reread, identity = self.stable_read_at(fd, relative.name,
                    maximum=row["bytes"], expected_mode=row["mode"])
                _require(identity["uid"] == identity["gid"] == 0 and reread == raw,
                         "CORE_EFFECT_INSTALL_MEMBER_CHANGED")
                self._observe_install_storage()
                self._effect_guard()
        finally:
            for path, fd in directories.items():
                if path:
                    os.close(fd)

    def _candidate_helper(self, name, verified):
        _require(name in (*PREPARATION_HELPERS, "q2_prepare_build"), "CORE_EFFECT_HELPER_NAME")
        return self._candidate_modules((name,), verified)[name]

    def _candidate_modules(self, names, verified=None):
        """Held-byte imports, including lazy imports, never expose the checkout."""
        import builtins
        import sys
        import types
        verified = self.verify_install_inputs() if verified is None else verified
        pin = _sha(canonical(verified))
        prior = getattr(self, "_candidate_loader", None)
        if prior is not None:
            _require(prior[0] == pin, "CORE_EFFECT_HELPER_SOURCE_CHANGED")
            return {name: prior[1](name) for name in names}
        sources = copy.deepcopy(verified)
        cache = {}
        roots = frozenset((*WHEEL_PACKAGES, "admin"))
        helpers = frozenset((*PREPARATION_HELPERS, "q2_prepare_build"))
        namespaces = {"admin", "admin.local_hand_quota_observer"}

        def load(name):
            _require(type(name) is str and re.fullmatch(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*", name)
                     and (name in helpers or name.split(".")[0] in roots
                          or "tests/e3_host/" + name + ".py" in PROJECTION_HARNESS),
                     "CORE_EFFECT_HELPER_NAME")
            if name in cache:
                return cache[name]
            package = name in namespaces
            relative = "tools/" + name.replace(".", "/")
            if name in helpers:
                _require(self._candidate_root is not None, "CORE_EFFECT_HELPER_INSTALLATION_REQUIRED")
                relative = "tests/e3_host/" + name + ".py"
                path = self._candidate_root + "/" + relative
                digest = sources["source_files"].get(relative)
            elif name in namespaces:
                path, digest = "<core-namespace>", None
            else:
                receipt = self._installation_receipt
                _require(receipt is not None and self._installation is not None,
                         "CORE_EFFECT_HELPER_INSTALLATION_REQUIRED")
                package = relative + "/__init__.py" in sources["projection"]["files"]
                relative = (relative + "/__init__.py" if package else relative + ".py") \
                    if name.split(".")[0] in roots else "tests/e3_host/" + name + ".py"
                entry = sources["projection"]["files"].get(relative)
                _require(entry is not None and _projection_path(relative), "CORE_EFFECT_HELPER_PROJECTION")
                digest = entry["sha256"]
                if name.split(".")[0] in WHEEL_PACKAGES:
                    _require(sources["wheel_files"].get(relative[6:]) == digest,
                             "CORE_EFFECT_HELPER_WHEEL")
                    path = receipt["installed"]["package_root"] + "/" + relative[6:]
                else:
                    path = receipt["source"]["root"] + "/" + relative
            raw = b""
            if digest is not None:
                self._effect_guard()
                raw, identity = self.stable_read(path, maximum=MEMBER_LIMIT, expected_mode=420)
                self._effect_guard()
                _require(identity["uid"] == identity["gid"] == 0 and _sha(raw) == digest,
                         "CORE_EFFECT_HELPER_CHANGED")
            else:
                _require(name in namespaces, "CORE_EFFECT_HELPER_SOURCE_MISSING")
            parent, _, child = name.rpartition(".")
            if parent:
                load(parent)
                if name in cache:
                    return cache[name]
            module = types.ModuleType(name)
            module.__file__, module.__package__ = path, name if package else parent
            if package:
                module.__path__ = []
            module.__dict__["__builtins__"] = dict(vars(builtins), __import__=import_bound)
            cache[name] = module
            previous = sys.modules.get(name)
            existed = name in sys.modules
            try:
                sys.modules[name] = module
                exec(compile(raw, path, "exec"), module.__dict__)
                if name == "q2_prepare_driver":
                    module.helper = lambda helper: load(helper) if helper in PREPARATION_HELPERS else \
                        _require(False, "CORE_EFFECT_HELPER_NAME")
            except BaseException:
                cache.pop(name, None)
                raise
            finally:
                if existed:
                    sys.modules[name] = previous
                else:
                    sys.modules.pop(name, None)
            if parent:
                setattr(cache[parent], child, module)
            return module

        def import_bound(name, globals=None, locals=None, fromlist=(), level=0):
            if level:
                name = importlib.util.resolve_name("." * level + name, globals["__package__"])
            root = name.split(".")[0]
            if root not in roots and name not in helpers and not name.startswith(("q2_", "q4_")):
                _require(root in sys.stdlib_module_names, "CORE_EFFECT_HELPER_IMPORT")
                return builtins.__import__(name, globals, locals, fromlist, 0)
            module = load(name)
            for item in fromlist or ():
                if item != "*" and not hasattr(module, item):
                    load(name + "." + item)
            return module if fromlist else load(root)

        result = {name: load(name) for name in names}
        self._candidate_loader = (pin, load)
        return result

    def _observe_install_storage(self):
        """Charge actual simultaneous owned files; this is not a peak proof."""
        total_bytes = total_inodes = 0
        seen = set()
        for root in self._install_roots:
            try:
                root_fd = self._held_directory(root)
            except FileNotFoundError:
                continue
            pending = [(root_fd, root)]
            try:
                while pending:
                    fd, directory = pending.pop()
                    try:
                        info = os.fstat(fd)
                        _require(info.st_uid == 0 and not info.st_mode & 0o022,
                                 "CORE_EFFECT_INSTALL_STORAGE_OWNER")
                        key = (info.st_dev, info.st_ino)
                        _require(key not in seen, "CORE_EFFECT_INSTALL_STORAGE_ALIAS")
                        seen.add(key)
                        total_bytes += info.st_blocks * 512
                        total_inodes += 1
                        with os.scandir(fd) as entries:
                            for entry in entries:
                                item = entry.stat(follow_symlinks=False)
                                if stat.S_ISLNK(item.st_mode):
                                    # The frozen installer removes only this
                                    # venv-generated convenience alias directly
                                    # after the venv child returns. Count its
                                    # inode without traversing it meanwhile.
                                    _require(self._venv_alias_pending
                                             and directory == self._install_roots[1] + "/runtime"
                                             and entry.name == "lib64"
                                             and os.readlink(entry.name, dir_fd=fd) == "lib",
                                             "CORE_EFFECT_INSTALL_STORAGE_SYMLINK")
                                    total_bytes += item.st_blocks * 512
                                    total_inodes += 1
                                    continue
                                if stat.S_ISDIR(item.st_mode):
                                    pending.append((os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY
                                        | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd),
                                        directory + "/" + entry.name))
                                else:
                                    _require(stat.S_ISREG(item.st_mode) and item.st_nlink == 1
                                             and item.st_uid == 0 and not item.st_mode & 0o022,
                                             "CORE_EFFECT_INSTALL_STORAGE_FILE")
                                    key = (item.st_dev, item.st_ino)
                                    _require(key not in seen, "CORE_EFFECT_INSTALL_STORAGE_ALIAS")
                                    seen.add(key)
                                    total_bytes += item.st_blocks * 512
                                    total_inodes += 1
                                _require(total_bytes <= LIMITS["shared_bytes"]
                                         and total_inodes + len(pending) <= LIMITS["shared_inodes"],
                                         "CORE_EFFECT_INSTALL_STORAGE_LIMIT")
                    finally:
                        os.close(fd)
            finally:
                for fd, _ in pending:
                    os.close(fd)
        _require(total_bytes <= LIMITS["shared_bytes"]
                 and total_inodes <= LIMITS["shared_inodes"], "CORE_EFFECT_INSTALL_STORAGE_LIMIT")
        self._shared_observed_bytes = max(self._shared_observed_bytes, total_bytes)
        self._shared_observed_inodes = max(self._shared_observed_inodes, total_inodes)
        return {"bytes": total_bytes, "inodes": total_inodes}

    def _installation_command(self, argv):
        """One real child, wait4 accounting and paired EOF; never retry.

        Normal work cannot borrow the remote-final reserve. After a failure,
        only kill/reap/drain is permitted inside the unchanged outer window.
        Child rusage is retained as a measured component, not a substitute for
        the still-missing all-unit CPU/memory/pid/storage accounting.
        """
        _require(type(argv) in (list, tuple) and 1 <= len(argv) <= 128
                 and all(type(arg) is str and "\0" not in arg and len(arg) <= 65536 for arg in argv)
                 and argv[0].startswith("/"), "CORE_EFFECT_INSTALL_COMMAND")
        self._effect_guard()
        self._observe_install_storage()
        self._effect_guard()
        output = {"stdout": bytearray(), "stderr": bytearray()}
        eof = set()
        proc = selector = None
        failure = cleanup_failure = waited = None
        attempted = False
        killed = False

        def call(function, *args, stopping=False, returned=None, **kwargs):
            guard = (lambda: _clock(self, self.context["guest_deadlines"])) if stopping else self._effect_guard
            guard()
            value = function(*args, **kwargs)
            # Preserve completed effects even when a syscall returns late.
            if returned is not None:
                returned(value)
            guard()
            return value

        def set_process(value):
            nonlocal proc
            proc = value

        def set_selector(value):
            nonlocal selector
            selector = value

        def reap(stopping=False):
            nonlocal waited
            if waited is not None:
                return
            def retain(value):
                nonlocal waited
                pid, status, usage = value
                if pid:
                    _require(pid == proc.pid, "CORE_EFFECT_INSTALL_COMMAND_WAIT_IDENTITY")
                    proc.returncode = os.waitstatus_to_exitcode(status)
                    # Linux ru_maxrss is KiB. Round CPU upward, never to an
                    # optimistic zero for a positive sub-nanosecond value.
                    waited = {"pid": pid, "wait_status": status,
                              "user_cpu_ns": math.ceil(usage.ru_utime * NS),
                              "system_cpu_ns": math.ceil(usage.ru_stime * NS),
                              "max_rss_bytes": usage.ru_maxrss * 1024}
            call(os.wait4, proc.pid, os.WNOHANG, stopping=stopping, returned=retain)

        def read_pipe(name, stopping=False):
            stream = getattr(proc, name)
            room = 32768 - sum(map(len, output.values()))
            def retain(block):
                if not block:
                    eof.add(name)
                else:
                    # A remaining+1 sentinel is observed but never retained.
                    output[name].extend(block[:room])
            try:
                block = call(os.read, stream.fileno(), 4096 if stopping else min(4096, room + 1),
                             stopping=stopping, returned=retain)
            except BlockingIOError:
                return
            if not stopping:
                _require(len(block) <= room, "CORE_EFFECT_INSTALL_COMMAND_OUTPUT_LIMIT")

        try:
            attempted = True
            call(subprocess.Popen, argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, cwd=self._candidate_root, close_fds=True,
                start_new_session=True, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C",
                                            "LANG": "C", "PYTHONDONTWRITEBYTECODE": "1",
                                            "TMPDIR": self._install_temp or self._candidate_root,
                                            "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1",
                                            "GIT_CONFIG_GLOBAL": "/dev/null"}, returned=set_process)
            call(selectors.DefaultSelector, returned=set_selector)
            for name in output:
                stream = getattr(proc, name)
                call(os.set_blocking, stream.fileno(), False)
                call(selector.register, stream, selectors.EVENT_READ, name)
            while len(eof) != 2 or waited is None:
                for key, _ in call(selector.select, 0.02):
                    read_pipe(key.data)
                    if key.data in eof:
                        call(selector.unregister, key.fileobj)
                reap()
            _require(proc.returncode == 0, "CORE_EFFECT_INSTALL_COMMAND_FAILED")
            self._effect_guard()
            self._venv_alias_pending = list(argv[1:7]) == ["-I", "-B", "-m", "venv", "--copies", "--without-pip"]
            try:
                self._observe_install_storage()
            finally:
                self._venv_alias_pending = False
            self._effect_guard()
            return bytes(output["stdout"])
        except BaseException as error:
            failure = str(error)[:128] if isinstance(error, DispatchError) else type(error).__name__
            if proc is not None:
                try:
                    # The leader may already be reaped while a descendant
                    # still owns a pipe. Signal its original process group.
                    def kill():
                        nonlocal killed
                        killed = True
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    if waited is None or len(eof) != 2:
                        call(kill, stopping=True)
                    for name in output:
                        call(os.set_blocking, getattr(proc, name).fileno(), False, stopping=True)
                    # Do not depend on selector construction succeeding. A
                    # bounded empty poll allows kill/reap even under EMFILE.
                    while waited is None or len(eof) != 2:
                        reap(stopping=True)
                        for name in output:
                            if name not in eof:
                                read_pipe(name, stopping=True)
                        if waited is None or len(eof) != 2:
                            call(time.sleep, 0.005, stopping=True)
                except BaseException as cleanup_error:
                    cleanup_failure = (str(cleanup_error)[:128]
                        if isinstance(cleanup_error, DispatchError) else type(cleanup_error).__name__)
            raise
        finally:
            if attempted:
                self._install_commands.append({"argv": list(argv),
                    "returncode": proc.returncode if proc is not None else None,
                    "eof": sorted(eof), "failure": failure, "cleanup_failure": cleanup_failure,
                    "kill_sent": killed, "wait4": waited,
                    "stdout": bytes(output["stdout"]), "stderr": bytes(output["stderr"])})
            # Local descriptor release is not evidence of EOF or child exit.
            try:
                if selector is not None:
                    selector.close()
            finally:
                if proc is not None:
                    for name in output:
                        getattr(proc, name).close()

    def persist(self, case_id, path, raw, mode):
        _require(self._persistence_ready, "CORE_EFFECT_PERSISTENCE_NOT_READY")
        target = self._persistence_path(case_id, path)
        self.create_only(target, raw, mode=mode)
        role = ("session" if path == "carrier/session.json" else
                "admission" if path == "carrier/admission.json" else
                "installation" if path == "carrier/installation.json" else
                "intent" if path.endswith("/intent.json") else
                "phase-receipt" if "/phase-" in path and path.endswith("-receipt.json") else
                "recovery-proof" if path.endswith("/h11-recovery-proof.json") else
                "verdict" if path.endswith("/case-verdict.json") else None)
        _require(role is not None, "CORE_EFFECT_PERSIST_ROLE")
        return {"path": path, "role": role, "mode": mode, "raw": raw}

    def preparation_helpers(self):
        _require(self._candidate_root is not None, "CORE_EFFECT_HELPER_INSTALLATION_REQUIRED")
        verified = self.verify_install_inputs()
        return {name: self._candidate_helper(name, verified) for name in PREPARATION_HELPERS}

    def prepare_case(self, case, intent, preparation_deadline_ns):
        _prep_require(case in CASES and intent == build_intent(case), 'INPUT')
        _integer(preparation_deadline_ns, 1, code="CORE_EFFECT_PREPARATION_DEADLINE")
        _prep_require(self._installation_receipt is not None and self._persistence_ready
                 and self._admission is not None and os.geteuid() == os.getegid() == 0,
                 'INSTALLATION_REQUIRED')
        _prep_require(all(callable(getattr(self, "_capacity_" + name, None)) for name in
                 ("retained_snapshot", "quota_inventory", "quota_enforcement")),
                 'CURRENT_FACTS_REQUIRED')
        deadline = preparation_deadline_ns
        with _PrepIO(self, deadline) as io:
            intent_path = self._persistence_path(case["case_id"], "cases/" + case["case_id"] + "/intent.json")
            actual, pin = io.call(self.stable_read, intent_path, maximum=65536, expected_mode=384)
            _prep_require(actual == canonical(intent, newline=True) and pin["uid"] == pin["gid"] == 0,
                     'INTENT_REQUIRED')
            helpers = io.call(self.preparation_helpers)
            driver = helpers["q2_prepare_driver"]
            # Fixed before the first write; never refresh expiry after preparation.
            plan = _prep_make_plan(self, case, (time.time_ns() + OWNER_NS) // NS)
            driver.validate_plan(plan)
            parents, directories, children = self._admission["parents"], {}, {}
            before = io.call(self._capacity_retained_snapshot)
            inventory = io.call(self._capacity_quota_inventory)
            _prep_require(before == self._admission_detail["retained_before"]
                     and not set(case["project_ids"]) & {r["project"] for r in inventory},
                     'RETAINED_CHANGED')
            for role in ("state", "quota", "journal", "evidence"):
                pin = parents[role]
                info = io.call(os.fstat, io.directory(pin["path"]))
                _prep_require((info.st_dev, info.st_ino, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
                         == tuple(pin[k] for k in ("dev", "ino", "uid", "gid", "mode")),
                         'PARENT_CHANGED')
            def directory(path, uid=0, gid=0, mode=493):
                return _prep_directory(self, path, uid, gid, mode, deadline)
            def save(path, value):
                return _prep_file(self, path, canonical(value, newline=True), deadline)
            reservation = plan["directories"]["reservation"]["path"]
            directory(parents["state"]["path"] + "/" + SESSION + "/" + case["case_id"])
            directories["reservation"] = directory(reservation, mode=448)
            # Durable preimage precedes every other case resource.
            objects = {"preparation-plan": save(reservation + "/preparation-plan.json", plan)}
            for role in ("state", "quota", "journal", "evidence"):
                session = parents[role]["path"] + "/" + SESSION
                if role != "state" and case["index"] == 1: directory(session)
                info = io.call(os.fstat, io.directory(session))
                _prep_require(info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 493,
                         'SESSION_PROTECTION')
                if role != "state": directory(session + "/" + case["case_id"])
            account = plan["account"]
            for role, row in plan["directories"].items():
                if role == "reservation": continue
                uid, gid = (account["uid"], account["gid"]) if row["owner"] == "ordinary" else (0, 0)
                directories[role] = directory(row["path"], uid, gid, row["mode"])
            for name in ("preflight", "business", "evidence", "management_evidence", "launcher_output",
                         "supervisor_output", "owner_output", "launcher_declarations",
                         "supervisor_declarations", "owner_declarations"):
                parent = directories["declarations" if name.endswith("declarations") else "capture"]["path"]
                children[name] = _prep_pin(directory(parent + "/" + name,
                    mode=493 if name == "launcher_declarations" else 448))
            roots = [_prep_root(self, row, account, plan["mounts"]["quota"], deadline) for row in plan["roots"]]
            after = io.call(self._capacity_retained_snapshot)
            remaining = [r for r in io.call(self._capacity_quota_inventory) if r["project"] not in case["project_ids"]]
            _prep_require(before == after and _prep_quota_retained(inventory) == _prep_quota_retained(remaining),
                     'RETAINED_CHANGED')
            pins = {}
            for role in ("controller", "management", "query", "supervisor", "ordinary"):
                key = "retained_ordinary_cgroup" if role == "ordinary" and case["index"] == 2 else role + "_cgroup"
                pins[role] = _prep_pin(parents[key])
                pins[role]["path"] = pins[role]["path"].removeprefix("/sys/fs/cgroup")
            observed = dict(host=plan["host"], ordinary=account, directories=directories, parents=pins,
                mounts=plan["mounts"], roots=roots, installation=self._installation_receipt,
                capacity_observed={"quota_inventory": inventory}, retained_before=before, retained_after=after)
            if case["index"] != 2: observed["system_geometry"] = self._admission_detail["system_geometry"]
            result = dict(schema="local-hand-q2-fixture-preparation/v1", preparation_id=case["preparation_id"],
                plan_sha256=_sha(objects["preparation-plan"]["raw"]), status="RESOURCES_PREPARED", reason=None,
                facts=observed, q2_accepted=False, q3_accepted=False, production_supported=False, fixture_generated=False)
            objects["preparation-result"] = save(reservation + "/preparation-result.json", result)
            prepared = dict(case=case, intent=intent, plan=plan, receipt=result, children=children,
                source_objects=objects, **_prep_translate(case, plan, result, children, helpers))
            prepared["paths"] = {k: v["path"] for k, v in {**directories, **children}.items()}
            prepared["paths"]["retained_store"] = next(r["path"] for r in roots if r["slot"] == "store")
            for name in ("authority", "manifest"): save(reservation + "/" + name + ".json", prepared[name])
            io.call(_prep_initialize, self, prepared, deadline)
            return prepared

    def plan_case(self, case, prepared, deadlines):
        _require(case in CASES and prepared.get("case") == case,
                 "CORE_EFFECT_PLAN_PREPARATION_REQUIRED")
        now = _prep_guard(self, deadlines["owner_deadline_ns"])
        realtime = time.time_ns()
        expires = prepared["facts"]["identity"]["expires_at"]
        _require(realtime // NS < expires
                 and expires * NS <= realtime + deadlines["owner_deadline_ns"] - now["boottime_ns"],
                 "CORE_EFFECT_PLAN_REQUEST_EXPIRED")
        plan = _plan_from_prepared(case, prepared, deadlines)
        owner = dict(prepared["plan"]["settings"]["owner"])
        owner.pop("runtime_ns")
        owner.update(issued_ns=now["boottime_ns"], deadline_ns=deadlines["owner_deadline_ns"])
        runtime = self._candidate_modules(("q2_prepare_run",))["q2_prepare_run"]
        schema, purpose = {1: (runtime.SYSTEM_SCHEMA, "ONE_ORIGINAL_Q2_HANDOFF"),
            2: (runtime.CANCEL_SCHEMA, runtime.CANCEL_PURPOSE),
            3: (runtime.H11_SCHEMA, runtime.H11_PURPOSE)}[case["index"]]
        handoff = {"schema": schema, "purpose": purpose,
            "preparation_id": prepared["facts"]["identity"]["id"],
            "boot_id": self.context["guest_deadlines"]["boot_id"],
            "template": prepared["assembled"]["supervisor_template"],
            "supervisor_parent": prepared["assembled"]["supervisor_parent"],
            "output": prepared["children"]["owner_output"],
            "declarations": prepared["children"]["owner_declarations"], "owner_envelope": owner}
        raw = runtime.encoded(handoff)
        runtime.decode(raw, _sha(raw))
        prepared["handoff"] = prepared["handoff_plan"] = handoff
        prepared["handoff_path"] = prepared["paths"]["reservation"] + "/handoff.json"
        prepared["handoff_sha256"] = _sha(raw)
        prepared["source_objects"]["handoff"] = _prep_file(self, prepared["handoff_path"], raw,
                                                           deadlines["owner_deadline_ns"])
        sources = []
        for role in ("preparation-plan", "preparation-result", "authority"):
            record = prepared["source_objects"][role]
            raw = _prep_reread(self, record, deadlines["owner_deadline_ns"])
            suffix = "authority/authority.json" if role == "authority" else "reservation/" + role + ".json"
            sources.append({"path": "cases/" + case["case_id"] + "/" + suffix,
                            "role": role, "mode": 384, "raw": raw})
        raw = canonical(plan, newline=True)
        prepared["source_objects"]["case-plan"] = _prep_file(self,
            prepared["paths"]["reservation"] + "/case-plan.json", raw, deadlines["owner_deadline_ns"])
        sources.append({"path": "cases/" + case["case_id"] + "/reservation/case-plan.json",
                        "role": "plan", "mode": 384, "raw": raw})
        prepared["sources"] = list(sources)
        return {"plan": plan, "sources": sources}

    def _exec_empty_ledger_gate(self, case, prepared, plan):
        import sqlite3
        self._exec_guard(plan)
        modules = self._candidate_modules(("q2_fixture_check", "local_hand_jobs.policy"))
        checker = modules["q2_fixture_check"]
        policy = modules["local_hand_jobs.policy"].Policy(prepared["assembled"]["policy"])
        fd, held = prepared["_exec_ledger_fd"], prepared["_exec_ledger_identity"]
        path, uid = plan["ledger_path"], prepared["facts"]["ordinary"]["uid"]
        _require(held["path"] == path == policy.broker_root + "/jobs.sqlite",
                 "CORE_EFFECT_EMPTY_LEDGER_PATH")
        parent = self._held_directory(policy.broker_root)
        def snapshot():
            self._exec_guard(plan)
            info = os.fstat(fd)
            _require((info.st_dev, info.st_ino) == (held["dev"], held["ino"])
                and stat.S_ISREG(info.st_mode) and info.st_uid == uid
                and info.st_gid == prepared["facts"]["ordinary"]["gid"]
                and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 384
                and 100 <= info.st_size <= 33554432,
                "CORE_EFFECT_EMPTY_LEDGER_IDENTITY")
            for suffix in ("-wal", "-shm", "-journal"):
                try: os.stat("jobs.sqlite" + suffix, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError: continue
                raise DispatchError("CORE_EFFECT_EMPTY_LEDGER_SIDECAR")
            raw = os.pread(fd, info.st_size + 1, 0)
            _require(len(raw) == info.st_size and checker.identity(info) == checker.identity(os.fstat(fd))
                == checker.identity(os.stat("jobs.sqlite", dir_fd=parent, follow_symlinks=False)),
                "CORE_EFFECT_EMPTY_LEDGER_CHANGED")
            self._exec_guard(plan)
            return raw, checker.identity(info), checker.identity(os.fstat(parent))
        try:
            before = snapshot()
            checker.empty_ledger(policy, uid, prepared["assembled"]["chain"]["broker_generation"])
            self._exec_guard(plan)
            db = sqlite3.connect(":memory:")
            try:
                raw = before[0]
                db.deserialize(raw[:18] + b"\1\1" + raw[20:])
                db.execute("PRAGMA query_only=ON")
                db.set_progress_handler(lambda: (self._exec_guard(plan), 0)[1], 100)
                rows = db.execute("SELECT key,value FROM metadata").fetchall()
                _require(len(rows) == 3 and dict(rows) == {"schema": "1",
                    "authority_id": plan["identity"]["authority_id"],
                    "ledger_id": plan["identity"]["ledger_id"]}, "CORE_EFFECT_EMPTY_LEDGER_METADATA")
            finally:
                db.close()
            _require(snapshot() == before, "CORE_EFFECT_EMPTY_LEDGER_CHANGED")
        finally:
            os.close(parent)
        gate = {"schema": "local-hand-q2-core-empty-ledger-gate/v1", "session_id": SESSION,
            "index": case["index"], "case_id": case["case_id"], "ledger_path": path,
            "dev": held["dev"], "ino": held["ino"],
            "authority_id": plan["identity"]["authority_id"], "ledger_id": plan["identity"]["ledger_id"],
            "snapshot_sha256": _sha(before[0]), "operations": 0, "events": 0, "leases": 0,
            "sidecars": [], "checked_boottime_ns": self.now()["boottime_ns"],
            "stage": "fixture", "before_submit": True}
        raw = canonical(gate, newline=True)
        _prep_file(self, prepared["paths"]["reservation"] + "/empty-ledger-gate.json", raw,
                   plan["deadlines"]["owner_deadline_ns"])
        return {"path": "cases/" + case["case_id"] + "/reservation/empty-ledger-gate.json",
                "role": "empty-ledger-gate", "mode": 384, "raw": raw}

    def _exec_ledger_export(self, case, prepared, plan):
        """Read the closed original ledger; preserve its SQLite TEXT verbatim.

        The case runner calls this only after verifying owner wait/EOF, both
        control seals and the original units' complete stop acknowledgements.
        The descriptor was held before that same original owner was started.
        """
        import sqlite3
        _require(case in CASES[:2], "CORE_EFFECT_LEDGER_EXPORT_CASE")
        held = prepared["_exec_ledger_identity"]
        fd = prepared["_exec_ledger_fd"]
        path = plan["ledger_path"]
        _require(held["path"] == path, "CORE_EFFECT_LEDGER_EXPORT_IDENTITY")
        parent = self._held_directory(str(PurePosixPath(path).parent))
        name = PurePosixPath(path).name
        def identity():
            self._exec_guard(plan)
            info = os.fstat(fd)
            named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _require(stat.S_ISREG(info.st_mode) and stat.S_ISREG(named.st_mode)
                     and info.st_nlink == named.st_nlink == 1
                     and (info.st_dev, info.st_ino) == (held["dev"], held["ino"])
                     == (named.st_dev, named.st_ino)
                     and 0 < info.st_size <= 33554432, "CORE_EFFECT_LEDGER_EXPORT_IDENTITY")
            for suffix in ("-wal", "-shm", "-journal"):
                try:
                    os.stat(name + suffix, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise DispatchError("CORE_EFFECT_LEDGER_EXPORT_SIDECAR")
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        def digest():
            value = hashlib.sha256()
            offset = 0
            while True:
                self._exec_guard(plan)
                chunk = os.pread(fd, min(65536, 33554433 - offset), offset)
                if not chunk:
                    break
                offset += len(chunk)
                _require(offset <= 33554432, "CORE_EFFECT_LEDGER_EXPORT_SIZE")
                value.update(chunk)
            return offset, value.hexdigest()
        def text_object(raw):
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError("duplicate key")
                    result[key] = value
                return result
            def number(value):
                result = float(value)
                if not math.isfinite(result):
                    raise ValueError("nonfinite number")
                return result
            _require(type(raw) is str, "CORE_EFFECT_LEDGER_EXPORT_TEXT")
            try:
                value = json.loads(raw, object_pairs_hook=pairs,
                                   parse_constant=number, parse_float=number)
                _require(type(value) is dict, "CORE_EFFECT_LEDGER_EXPORT_TEXT")
                raw.encode("utf-8", "strict")
            except (ValueError, TypeError, RecursionError, UnicodeError) as error:
                raise DispatchError("CORE_EFFECT_LEDGER_EXPORT_TEXT") from error
        connection = None
        try:
            before = identity()
            size, sha = digest()
            _require(size == before[2], "CORE_EFFECT_LEDGER_EXPORT_CHANGED")
            # immutable avoids a read-only WAL connection creating -shm. The
            # prior quiescence/sidecar checks and held-fd reread enforce its premise.
            connection = sqlite3.connect("file:/proc/self/fd/" + str(fd)
                + "?mode=ro&immutable=1", uri=True, timeout=0)
            connection.row_factory = sqlite3.Row
            connection.set_progress_handler(lambda: (self._exec_guard(plan), 0)[1], 100)
            connection.execute("PRAGMA query_only=ON")
            _require(connection.execute("PRAGMA quick_check").fetchall()[0][0] == "ok",
                     "CORE_EFFECT_LEDGER_EXPORT_DATABASE")
            metadata = dict(connection.execute("SELECT key,value FROM metadata"))
            identity_fields = plan["identity"]
            _require(metadata == {"schema": "1", "authority_id": identity_fields["authority_id"],
                                   "ledger_id": identity_fields["ledger_id"]},
                     "CORE_EFFECT_LEDGER_EXPORT_METADATA")
            rows = connection.execute("SELECT namespace,id,parent,principal,digest,reserved_bytes,"
                "request_json,plan_json,record_json FROM operations LIMIT 2").fetchall()
            _require(len(rows) == 1, "CORE_EFFECT_LEDGER_EXPORT_OPERATION")
            operation = dict(rows[0])
            _require(operation["namespace"] == "job" and operation["id"] == case["operation_id"]
                     and operation["principal"] == identity_fields["principal_id"]
                     and operation["digest"] == plan["request"]["request_digest"]
                     and type(operation["reserved_bytes"]) is int and operation["reserved_bytes"] > 0,
                     "CORE_EFFECT_LEDGER_EXPORT_OPERATION")
            for key in ("request_json", "plan_json", "record_json"):
                text_object(operation[key])
            events = []
            cursor = connection.execute("SELECT seq,namespace,id,kind,"
                "printf('%.17g',observed_at) AS observed_at,data_json FROM events ORDER BY seq")
            for row in cursor:
                self._exec_guard(plan)
                event = dict(row)
                _require(type(event["seq"]) is int and event["seq"] > 0
                         and (not events or event["seq"] > events[-1]["seq"])
                         and event["namespace"] == "job" and event["id"] == case["operation_id"]
                         and type(event["kind"]) is str and event["kind"]
                         and re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?", event["observed_at"])
                         is not None, "CORE_EFFECT_LEDGER_EXPORT_EVENT")
                text_object(event["data_json"])
                events.append(event)
                _require(len(events) <= 4096, "CORE_EFFECT_LEDGER_EXPORT_SIZE")
            connection.close(); connection = None
            _require(identity() == before and digest() == (size, sha)
                     and identity() == before, "CORE_EFFECT_LEDGER_EXPORT_CHANGED")
            exported = self.now()["boottime_ns"]
            value = {"schema": "local-hand-q2-core-ledger-export/v1", "session_id": SESSION,
                "index": case["index"], "case_id": case["case_id"],
                "authority_id": identity_fields["authority_id"], "ledger_id": identity_fields["ledger_id"],
                "operation_id": case["operation_id"], "ledger_identity": dict(path=path,
                    dev=before[0], ino=before[1], bytes=size, sha256=sha),
                "operation": operation, "events": events, "sidecars": [],
                "exported_boottime_ns": exported}
            raw = canonical(value, newline=True, limit=1048576)
            logical = "cases/" + case["case_id"] + "/records/ledger-export.json"
            destination = self._persistence_path(case["case_id"],
                "cases/" + case["case_id"] + "/reservation/ledger-export.json")
            deadline = min(plan["deadlines"]["owner_deadline_ns"],
                self.context["guest_deadlines"]["boottime_deadline_ns"] - REMOTE_FINAL_RESERVE_NS)
            record = _prep_file(self, destination, raw, deadline)
            _require(_prep_reread(self, record, deadline) == raw, "CORE_EFFECT_LEDGER_EXPORT_CHANGED")
            return {"path": logical, "role": "ledger", "mode": 384, "raw": raw}
        finally:
            if connection is not None: connection.close()
            os.close(parent)

    def _exec_guard(self, plan, *, parent_guard=None):
        (self._effect_guard if parent_guard is None else parent_guard)()
        now = self.now(); original = getattr(self, "_active_case_deadlines", {})
        _require(original.get("owner_deadline_ns") == plan["deadlines"]["owner_deadline_ns"]
            and type(original.get("owner_monotonic_deadline_ns")) is int
            and now["boottime_ns"] < original["owner_deadline_ns"]
            and now["monotonic_ns"] < original["owner_monotonic_deadline_ns"],
            "CORE_EFFECT_CASE_DEADLINE")

    def _exec_child(self, argv, plan):
        """Reuse the bounded original wait4/EOF collector with both earlier clocks."""
        original = self._effect_guard
        previous = self.__dict__.get("_effect_guard")
        self._effect_guard = lambda: self._exec_guard(plan, parent_guard=original)
        try:
            # 32 KiB is stricter than the owner 68 KiB maximum; overflow fails.
            raw = self._installation_command(argv)
            _require(self._install_commands[-1]["stderr"] == b"", "CORE_EFFECT_OWNER_STDERR")
            return raw
        finally:
            if previous is None: del self._effect_guard
            else: self._effect_guard = previous

    def _exec_source(self, case, prepared, plan, suffix, role, mode=384):
        _path(suffix, "CORE_EFFECT_CASE_SOURCE_PATH")
        root, relative = suffix.split("/", 1)
        self._exec_guard(plan)
        if role == "result":
            _require(case["index"] == 1 and suffix == "business/result-03c94c57c840717302854a3f.json",
                     "CORE_EFFECT_CASE_RESULT_SOURCE")
            physical = prepared["facts"]["slots"][0]["roots"]["evidence"]["path"] + "/" + relative
        elif role.startswith("business-evidence-"):
            _require(case["index"] == 1, "CORE_EFFECT_CASE_RESULT_SOURCE")
            physical = prepared["paths"]["retained_store"] + "/" + relative
        else:
            _require(root in prepared["paths"], "CORE_EFFECT_CASE_SOURCE_ROOT")
            physical = prepared["paths"][root] + "/" + relative
        raw, identity = self.stable_read(physical, maximum=MEMBER_LIMIT, expected_mode=mode)
        self._exec_guard(plan)
        owner = prepared["facts"]["ordinary"] if role == "result" or role.startswith("business-evidence-") else {"uid": 0, "gid": 0}
        _require(identity["nlink"] == 1 and identity["uid"] == owner["uid"]
            and identity["gid"] == owner["gid"], "CORE_EFFECT_CASE_SOURCE_OWNER")
        source = {"path": "cases/" + case["case_id"] + "/" + suffix,
                  "role": role, "mode": mode, "raw": raw}
        prepared.setdefault("_exec_physical", {})[source["path"]] = physical
        return source

    def _exec_controls(self, case, prepared, plan, sources, child):
        prefix = "cases/" + case["case_id"] + "/"
        for folder, status in (("supervisor_output", "CONTROLLER_CLOSED"),
                               ("owner_output", "SUPERVISOR_CLOSED")):
            stop = _parse_source(sources, prefix + folder + "/stop.json")
            seal = _parse_source(sources, prefix + folder + "/seal.json")
            _require(stop.get("attempted") is True and stop.get("acknowledged") is True
                and stop.get("parent_empty") is True and stop.get("complete") is True
                and type(stop.get("closed_ns")) is int
                and 0 < stop["closed_ns"] < plan["deadlines"]["owner_deadline_ns"]
                and seal.get("status") == status and seal.get("production_supported") is False,
                "CORE_EFFECT_CASE_STOP_UNPROVEN")
            before, after = stop["before"], stop["after"]
            _require(before["Id"] == after["Id"] == plan["controllers"][
                    "target" if folder == "supervisor_output" else "supervisor"]["unit"]
                and before["InvocationID"] == seal["original"]["invocation_id"]
                and after["MainPID"] == after["ControlPID"] == "0"
                and (after["LoadState"] == "not-found" or (after["LoadState"] == "loaded"
                    and after["ActiveState"] in ("inactive", "failed")
                    and after["InvocationID"] == before["InvocationID"])),
                "CORE_EFFECT_CASE_STOP_IDENTITY")
            for source in sources:
                physical = prepared["_exec_physical"].get(source["path"])
                if physical in seal.get("files", {}):
                    _require(seal["files"][physical] == {"sha256": _sha(source["raw"]),
                        "bytes": len(source["raw"])}, "CORE_EFFECT_CASE_CONTROL_SEAL")
            own = next(s for s in sources if s["path"] == prefix + folder + "/stop.json")
            _require(seal.get("files", {}).get(prepared["_exec_physical"][own["path"]]) ==
                {"sha256": _sha(own["raw"]), "bytes": len(own["raw"])}, "CORE_EFFECT_CASE_CONTROL_SEAL")
        _require(child.get("status") == "SUPERVISOR_CLOSED" and child.get("sealed") is True
            and not child.get("cleanup_errors"), "CORE_EFFECT_CASE_OWNER_UNCLOSED")
        return {"requested": True, "acknowledged": True, "tree_exited": True,
                "writers_stopped": True, "deadline_ns": plan["deadlines"]["owner_deadline_ns"]}

    def _exec_case(self, case, prepared, plan):
        _require(case in CASES and prepared.get("case") == case
            and plan["case_id"] == case["case_id"] and plan["operation_id"] == case["operation_id"],
            "CORE_EFFECT_CASE_INPUT")
        _require(not prepared.get("_exec_attempted"), "CORE_EFFECT_CASE_ALREADY_ATTEMPTED")
        self._exec_guard(plan)
        handoff = prepared["handoff"]
        for record in prepared["source_objects"].values():
            _prep_reread(self, record, plan["deadlines"]["owner_deadline_ns"])
        _require(handoff["owner_envelope"]["deadline_ns"] == plan["deadlines"]["owner_deadline_ns"],
                 "CORE_EFFECT_CASE_OWNER_DEADLINE")
        raw, _ = self.stable_read(prepared["handoff_path"], maximum=2097152, expected_mode=384)
        _require(document(raw, limit=2097152, newline=True) == handoff, "CORE_EFFECT_CASE_HANDOFF_CHANGED")
        verified = self.verify_install_inputs()
        source_pin = handoff["template"]["launcher"]["source"]
        _require(source_pin["commit"] == CANDIDATE["commit"]
            and all(verified["source_files"].get(k) == v for k, v in source_pin["files"].items()),
            "CORE_EFFECT_CASE_CANDIDATE")
        runtime_root = prepared["facts"]["source"]["root"]
        _require(runtime_root == self._installation_receipt["source"]["root"],
                 "CORE_EFFECT_CASE_RUNTIME_ROOT")
        for name, digest in source_pin["files"].items():
            content, _ = self.stable_read(runtime_root + "/" + name,
                                          maximum=MEMBER_LIMIT, expected_mode=420)
            _require(_sha(content) == digest, "CORE_EFFECT_CASE_SOURCE_CHANGED")
        python = prepared["facts"]["installation"]["programs"]["python"]
        executable, _ = self.stable_read(python["path"], maximum=MEMBER_LIMIT)
        _require(_sha(executable) == python["sha256"], "CORE_EFFECT_CASE_PYTHON_CHANGED")
        parent = self._held_directory(str(PurePosixPath(plan["ledger_path"]).parent))
        fd = -1
        try:
            fd = os.open("jobs.sqlite", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK | os.O_NOATIME,
                         dir_fd=parent)
            info = os.fstat(fd)
            _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 384, "CORE_EFFECT_CASE_LEDGER")
            prepared["_exec_ledger_fd"] = fd
            prepared["_exec_ledger_identity"] = {"path": plan["ledger_path"], "dev": info.st_dev, "ino": info.st_ino}
            gate_source = self._exec_empty_ledger_gate(case, prepared, plan)
            prepared.setdefault("sources", []).append(gate_source)
            prepared["_exec_attempted"] = True
            child_raw = self._exec_child([python["path"], "-I", "-B", runtime_root +
                "/tests/e3_host/q2_prepare_run.py", "--plan", prepared["handoff_path"], "--sha256", _sha(raw)], plan)
            child = document(child_raw, limit=69632, newline=True)
            for record in prepared["source_objects"].values():
                _prep_reread(self, record, plan["deadlines"]["owner_deadline_ns"])
            current = os.stat("jobs.sqlite", dir_fd=parent, follow_symlinks=False)
            _require((current.st_dev, current.st_ino) == (info.st_dev, info.st_ino)
                and stat.S_ISREG(current.st_mode), "CORE_EFFECT_CASE_LEDGER_CHANGED")
            sources = [gate_source]
            # Only approved fixed names: H11 never touches a business result,
            # raw ledger contents, wildcard or business evidence directory.
            rows = _h01_special("00000000-0000-4000-8000-000000000000") if case["index"] == 1 else (
                Q4_SPECIAL if case["index"] == 2 else H11_SPECIAL)
            for suffix, role, mode in rows:
                if role in ("phase-receipt", "recovery-proof", "ledger", "result") or role.startswith("business-evidence-"):
                    continue
                sources.append(self._exec_source(case, prepared, plan, suffix, role, mode))
            sources.append(self._exec_source(case, prepared, plan, "owner_declarations/fixture-check.json", "fixture-check"))
            stop = self._exec_controls(case, prepared, plan, sources, child)
            prefix = "cases/" + case["case_id"] + "/"
            cap = _parse_source(sources, prefix + "launcher_output/capture.json")
            launch = _parse_source(sources, prefix + "launcher_output/result.json")
            _require(cap.get("complete") is True and cap.get("returncode") == 0
                and set(cap.get("eof", [])) == {"stdout", "stderr"}
                and launch.get("resident_capture") == cap and not launch.get("cleanup_errors")
                and next(s["raw"] for s in sources if s["path"] == prefix +
                         "launcher_output/resident.stderr") == b"", "CORE_EFFECT_CASE_QUIESCENCE")
            if case["index"] != 3:
                sources.append(self._exec_ledger_export(case, prepared, plan))
            return self._exec_observations(case, prepared, plan, sources, stop, verified)
        finally:
            prepared.pop("_exec_ledger_fd", None)
            if fd >= 0: os.close(fd)
            os.close(parent)

    def _exec_observations(self, case, prepared, plan, sources, stop, verified):
        prefix = "cases/" + case["case_id"] + "/"
        get = lambda suffix: _parse_source(sources, prefix + suffix)
        launch, capture = get("launcher_output/result.json"), get("launcher_output/capture.json")
        _require(capture.get("complete") is True and capture.get("returncode") == 0
            and set(capture.get("eof", [])) == {"stdout", "stderr"}
            and launch.get("resident_capture") == capture and not launch.get("cleanup_errors"),
            "CORE_EFFECT_CASE_RESIDENT_CAPTURE")
        stdout = next(s["raw"] for s in sources if s["path"] == prefix + "launcher_output/resident.stdout")
        stderr = next(s["raw"] for s in sources if s["path"] == prefix + "launcher_output/resident.stderr")
        _require(stderr == b"", "CORE_EFFECT_CASE_RESIDENT_STDERR")
        resident = document(stdout, limit=32768, newline=True)
        gate = next(s for s in prepared["sources"] if s["role"] == "empty-ledger-gate")
        obs = {"empty_ledger_gate": _plain_reference(gate)}
        proof = seal_id = None; summary = {}
        if case["index"] == 3:
            proof = self._exec_h11_proof(case, prepared, plan, sources, verified, launch, resident)
            obs.update({k: proof[k] for k in ("recovery_plan", "recovery_summary", "launcher_result",
                "gateway_snapshot", "origin_capture", "ledger_identity", "result_identity")})
            obs.update({k: proof["assertions"][k] for k in ("future_start_blocked", "tree_exited",
                "writers_stopped", "collectors_stopped", "effects_checked", "outcome", "leases_retained",
                "result_reread", "start_replayed", "business_evidence_sealed")})
            proof_raw = canonical(proof, newline=True)
            obs.update(original_request_accepted=True, control_closure_sealed=True,
                recovery_proof={"path": prefix + "reservation/h11-recovery-proof.json",
                                "bytes": len(proof_raw), "sha256": _sha(proof_raw)})
            # The exact pinned origin submits once after compose's empty gate;
            # candidate recovery asserts the unchanged original ACCEPTED row.
            accepted = self._exec_h11_accepted(case, prepared, plan)
        else:
            export = get("records/ledger-export.json"); operation = export["operation"]
            record = json.loads(operation["record_json"])
            events = export["events"]; accepts = [x for x in events if x["kind"] == "ACCEPTED"]
            _require(len(accepts) == 1 and operation["id"] == case["operation_id"]
                and operation["digest"] == plan["request"]["request_digest"], "CORE_EFFECT_CASE_ACCEPTED")
            accepted = accepts[0]["seq"]
            if case["index"] == 1:
                _require(launch.get("status") == resident.get("status") == "CHAIN_CLOSED"
                    and resident.get("operation_id") == case["operation_id"]
                    and record.get("lifecycle") == "TERMINAL" and record.get("outcome") == "SUCCEEDED"
                    and record.get("evidence") == "SEALED", "CORE_EFFECT_H01_TERMINAL")
                seals = record.get("seals", [])
                _require(len(seals) == 1, "CORE_EFFECT_H01_SEAL_REGISTRATION")
                seal_id = seals[0]["seal_id"]; _h01_special(seal_id)
                for suffix, role, mode in _h01_special(seal_id):
                    if role == "result" or role.startswith("business-evidence-"):
                        sources.append(self._exec_source(case, prepared, plan, suffix, role, mode))
                reader = self._candidate_modules(("local_hand_jobs.result_reader",))["local_hand_jobs.result_reader"]
                business_raw = next(s["raw"] for s in sources if s["role"] == "result")
                business_value = reader._result(reader._strict_json(business_raw, reader.MAX_RESULT_BYTES),
                    "job-" + case["operation_id"] + "-business", "business")
                retained = record.get("quota_pending", {}).get("business", {}).get("proof", {})
                _require(retained.get("helper_result_verified") is True and retained.get("result") == business_value
                    and business_value.get("outcome") == "SUCCEEDED" and business_value.get("effects_checked") is True,
                    "CORE_EFFECT_H01_RESULT_BINDING")
                seal_source = next(s for s in sources if s["path"] == prefix + "business-evidence/" + seal_id + "/seal.json")
                seal = document(seal_source["raw"], limit=MEMBER_LIMIT, newline=False)
                _require(all(seal.get(k) == v for k, v in seals[0].items() if k in seal)
                    and seal.get("operation_id") == case["operation_id"] and seal.get("complete") is True
                    and _sha(seal_source["raw"]) == seals[0]["seal_sha256"], "CORE_EFFECT_H01_BUSINESS_SEAL")
                for artifact in seal["artifacts"]:
                    filename = "evidence.zip" if artifact["role"] == "zip" else "manifest.json"
                    content = next(s["raw"] for s in sources if s["path"] == prefix +
                                   "business-evidence/" + seal_id + "/" + filename)
                    _require(len(content) == artifact["size"] and _sha(content) == artifact["sha256"],
                             "CORE_EFFECT_H01_BUSINESS_EVIDENCE")
                units = []
                for phase in case["phases"]:
                    value = get("launcher_output/phase-" + phase + ".json")
                    fence = value.get("fence", {})
                    _require(value.get("status") == "PHASE_CLOSED" and fence.get("execution_id") ==
                        "job-" + case["operation_id"] + "-" + phase, "CORE_EFFECT_H01_PHASE")
                    for stage in ("bootstrap", "helper", "result_reader"):
                        closed = fence["stages"]["reader" if stage == "result_reader" else stage]; identity = closed["identity"]
                        _require(all(closed.get(k) is True for k in ("delivery_settled", "future_start_blocked", "job_empty",
                            "unit_terminal", "tree_empty", "collectors_stopped", "stdout_eof", "stderr_eof")),
                            "CORE_EFFECT_H01_EXIT")
                        units.append({"phase": phase, "stage": stage, "unit": identity["unit"],
                                      "invocation_id": identity["invocation_id"]})
                units.sort(key=lambda row: (row["phase"], row["stage"], row["unit"]))
                _validate_units(units, case)
                gateway = get("launcher_output/gateway.json")
                _require(gateway.get("failure") is None, "CORE_EFFECT_H01_GATEWAY")
                for row in units:
                    match = [x for x in gateway["stages"] if all(x.get(k) == v for k, v in row.items())]
                    _require(len(match) == 1 and match[0].get("sealed") is True
                        and type(match[0].get("returncode")) is int, "CORE_EFFECT_H01_GATEWAY_UNIT")
                business = next(x for x in gateway["stages"] if x["phase"] == "business" and x["stage"] == "helper")
                summary = {"business_invocation_id": business["invocation_id"], "business_wait_status": business["returncode"]}
                obs.update({k: True for k in H01_OBSERVATIONS if k not in
                    ("empty_ledger_gate", "resident_empty_gate", "unit_identities")})
                obs["unit_identities"] = units
            else:
                modules = self._candidate_modules(("q2_launcher", "q4_cancel_case"))
                report = modules["q2_launcher"].validate_cancel_result(launch,
                    prepared["handoff"]["template"]["launcher"]["resident"], modules["q4_cancel_case"])
                _require(report == get("launcher_output/phase.json")["case"] == resident.get("case")
                    and report["status"] == "EXERCISED" and report["helper_exit_proven"] is True,
                    "CORE_EFFECT_Q4_NOT_EXERCISED")
                cancels = [x for x in events if x["kind"] == "CANCEL_REQUESTED"]
                _require(len(cancels) == 1 and cancels[0]["seq"] == report["ledger"]["cancel_event"]["seq"]
                    and record.get("cancel_requested") is True, "CORE_EFFECT_Q4_CANCEL_LEDGER")
                units = [{"phase": "preflight", "stage": stage, "unit": item["unit"],
                    "invocation_id": item["invocation_id"]} for stage, item in
                    record["handles"]["preflight"]["manager"].items() if stage in ("bootstrap", "helper", "result_reader")]
                units.sort(key=lambda row: (row["phase"], row["stage"], row["unit"]))
                _validate_units(units, case)
                obs.update({k: True for k in Q4_OBSERVATIONS if k not in
                    ("empty_ledger_gate", "resident_empty_gate", "unit_identities", "chain_closed", "ordinary_phase_closed", "full_h07")})
                obs.update(unit_identities=units, chain_closed=False, ordinary_phase_closed=False, full_h07=False)
        obs["resident_empty_gate"] = {"passed": True, "candidate_commit": CANDIDATE["commit"],
            "resident_source_sha256": verified["source_files"]["tests/e3_host/q2_resident.py"],
            "accepted_operation_id": case["operation_id"], "accepted_event_seq": accepted}
        return {"sources": sources, "observations": obs, "stop": stop, "proof": proof,
                "seal_id": seal_id, "summary": summary}

    def _exec_h11_proof(self, case, prepared, plan, sources, verified, launch, resident):
        prefix = "cases/" + case["case_id"] + "/"
        item = lambda suffix: next(s for s in sources if s["path"] == prefix + suffix)
        get = lambda suffix: _parse_source(sources, prefix + suffix)
        declaration = get("launcher_declarations/recovery-resident.json")
        modules = self._candidate_modules(("q2_launcher", "q4_h11_recovery"))
        recovery = modules["q4_h11_recovery"].validate(declaration["recovery"])
        report = modules["q2_launcher"].validate_h11_result(launch,
            prepared["handoff"]["template"]["launcher"]["resident"])
        gateway = get("launcher_output/gateway.json")
        origin = get("launcher_output/origin-capture.json")
        _require(report == resident == get("launcher_output/recovery.json")
            and launch["origin_capture"] == origin and origin.get("complete") is True
            and set(origin.get("eof", [])) == {"stdout", "stderr"}
            and origin.get("returncode") == -signal.SIGKILL
            and recovery["operation_id"] == case["operation_id"]
            and recovery["request_digest"] == plan["request"]["request_digest"]
            and report["units"] == recovery["units"]
            and report["original_deadline_ns"] == recovery["budget_deadline_ns"]
            and report["phase_deadline_ns"] == recovery["phase_deadline_ns"]
            and report["controller_deadline_ns"] == recovery["controller_deadline_ns"]
            and report["original_event_seq"] == recovery["event_seq"]
            and report["event_kinds"].count("RECOVERY_BARRIER") == 1
            and report["event_kinds"].count("QUOTA_EXIT_PENDING") == 1
            and set(report["event_kinds"]) <= modules["q4_h11_recovery"].RECOVERY_EVENTS,
            "CORE_EFFECT_H11_ORIGINAL_BINDING")
        _require(gateway.get("failure") is None and gateway.get("recovery_finished") is True
            and gateway.get("recovery_only") is True and gateway.get("recovery_rebinds") == 1
            and gateway.get("recovery_arm_ack") is True
            and gateway.get("recovery_plan_sha256") == _sha(canonical(recovery)),
            "CORE_EFFECT_H11_GATEWAY_BINDING")
        expected_units = _phase_units(case["operation_id"], ["preflight"])[0]
        for stage, unit in recovery["units"].items():
            _require(unit == expected_units[stage + "_unit"], "CORE_EFFECT_H11_UNIT")
            rows = [r for r in gateway["stages"] if r["stage"] == stage and r["phase"] == "preflight"]
            _require(len(rows) == 1 and rows[0]["unit"] == unit
                and rows[0].get("recovery_observed") is True, "CORE_EFFECT_H11_UNIT")
        for stream in ("stdout", "stderr"):
            _require(item("launcher_output/origin-resident." + stream)["raw"] == b"",
                     "CORE_EFFECT_H11_ORIGIN_OUTPUT")
        refs = {key: _plain_reference(item(suffix)) for key, suffix in (
            ("recovery_plan", "launcher_declarations/recovery-resident.json"),
            ("recovery_summary", "launcher_output/recovery.json"),
            ("launcher_result", "launcher_output/result.json"),
            ("gateway_snapshot", "launcher_output/gateway.json"),
            ("origin_capture", "launcher_output/origin-capture.json"),
            ("control_seal", "owner_output/seal.json"))}
        refs["recovery_plan"]["embedded_plan_sha256"] = _sha(canonical(recovery))
        candidate = {"commit": CANDIDATE["commit"], "tree": CANDIDATE["tree"]}
        for role, name in (("h11", "q4_h11_recovery"), ("resident", "q2_resident"), ("launcher", "q2_launcher")):
            relative = "tests/e3_host/" + name + ".py"
            candidate.update({role + "_source_path": relative,
                              role + "_source_sha256": verified["source_files"][relative]})
        assertions = {key: report[key] for key in ("future_start_blocked", "tree_exited", "writers_stopped",
            "collectors_stopped", "effects_checked", "outcome", "leases_retained", "result_reread", "start_replayed")}
        # These are explicitly the pinned recovery helper's assertions, not
        # invented raw before-snapshots. validate_h11_result has checked them.
        assertions.update({key: True for key in ("same_operation", "same_request_digest",
            "original_handle_admitted", "same_original_stage_units", "same_grant_and_deadlines",
            "delivery_intents_unchanged", "recovery_launch_forbidden", "gateway_parts_unchanged")})
        assertions.update(recovery_barrier_count=1, quota_exit_pending_count=1,
                          deadline_extended=False, business_evidence_sealed=False)
        basename = "result-f7b176ecb6b8081fac3a7a47.json"
        return {"schema": PROOF_SCHEMA, "session_id": SESSION, "index": case["index"],
            "case_id": case["case_id"], "candidate": candidate, **refs,
            "ledger_identity": {**prepared["_exec_ledger_identity"], "unchanged": True},
            "result_identity": {"expected_path": prepared["facts"]["slots"][0]["roots"]["evidence"]["path"] + "/" + basename,
                "expected_basename": basename, "stat_performed": False, "opened": False, "hashed": False},
            "assertions": assertions}

    def _exec_h11_accepted(self, case, prepared, plan):
        import sqlite3
        self._exec_guard(plan)
        _require(case == CASES[2], "CORE_EFFECT_H11_ACCEPTED_CASE")
        fd = prepared["_exec_ledger_fd"]
        path = PurePosixPath(plan["ledger_path"])
        parent = self._held_directory(str(path.parent))
        def identity():
            self._exec_guard(plan)
            info = os.fstat(fd)
            named = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            _require(stat.S_ISREG(info.st_mode) and stat.S_ISREG(named.st_mode)
                and info.st_nlink == named.st_nlink == 1
                and (info.st_dev, info.st_ino) == (named.st_dev, named.st_ino),
                "CORE_EFFECT_H11_LEDGER_CHANGED")
            for suffix in ("-wal", "-shm", "-journal"):
                try: os.stat(path.name + suffix, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError: continue
                raise DispatchError("CORE_EFFECT_H11_LEDGER_SIDECAR")
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        db = None
        try:
            before = identity()
            # Closed WAL-format files must not create reader sidecars.
            db = sqlite3.connect("file:/proc/self/fd/" + str(fd) + "?mode=ro&immutable=1",
                                 uri=True, timeout=0)
            db.execute("PRAGMA query_only=ON")
            db.set_progress_handler(lambda: (self._exec_guard(plan), 0)[1], 500)
            rows = db.execute("SELECT seq FROM events WHERE namespace='job' AND id=? AND kind='ACCEPTED'",
                              (case["operation_id"],)).fetchmany(2)
            _require(len(rows) == 1 and type(rows[0][0]) is int and rows[0][0] > 0,
                     "CORE_EFFECT_H11_ACCEPTED_EVENT")
            db.close(); db = None
            _require(identity() == before, "CORE_EFFECT_H11_LEDGER_CHANGED")
        finally:
            if db is not None: db.close()
            os.close(parent)
        self._exec_guard(plan)
        return rows[0][0]

    def run_h01(self, case, prepared, plan):
        _require(case == CASES[0], "CORE_EFFECT_H01_CASE")
        return self._exec_case(case, prepared, plan)

    def run_q4(self, case, prepared, plan):
        _require(case == CASES[1], "CORE_EFFECT_Q4_CASE")
        return self._exec_case(case, prepared, plan)

    def recover_h11(self, case, prepared, plan):
        _require(case == CASES[2], "CORE_EFFECT_H11_CASE")
        return self._exec_case(case, prepared, plan)

    def phase_facts(self, case, phase, plan, sources):
        names = ("admin.local_hand_quota_observer.q2_config", "local_hand_jobs.budget",
                 "admin.local_hand_quota_observer.controller_guard")
        modules = self._candidate_modules(names)
        return _phase_extract(case, phase, plan, sources, *(modules[name] for name in names))

    def usage(self):
        # process_time/ru_maxrss cover only this process and cannot account for
        # its installer/compiler children or the separately managed job units.
        # Sampled installation allocation is also not the guest-wide peak.
        # Until those observations are integrated, emitting pids=1 or storage=0
        # would turn missing evidence into fabricated successful accounting.
        raise DispatchError("CORE_EFFECT_USAGE_ACCOUNTING_INCOMPLETE")


def _phase_extract(case, phase, plan, sources, config_api, budget_api, controller_api):
    """Rebuild receipts from original candidate bytes, never from plan defaults."""
    _require(case in CASES and phase in case["phases"], "CORE_EFFECT_PHASE_CASE")
    by_path = {}
    for source in sources:
        _source(source, case_id=case["case_id"])
        _require(source["path"] not in by_path, "CORE_EFFECT_PHASE_DUPLICATE")
        by_path[source["path"]] = source
    rows = {}
    for path, role in phase_source_specs(case, phase):
        item = by_path.get(path)
        _require(item is not None and item["role"] == role
                 and item["mode"] == (420 if role == "recovery-plan" else 384),
                 "CORE_EFFECT_PHASE_SOURCE")
        rows[role] = item
    values = {role: document(item["raw"], limit=MEMBER_LIMIT,
                           newline=role == "preparation-result")
              for role, item in rows.items()}
    try:
        prepared = values["preparation-result"]
        _exact(prepared, ("schema", "preparation_id", "plan_sha256", "status", "reason",
                         "facts", "q2_accepted", "q3_accepted", "production_supported",
                         "fixture_generated"), "CORE_EFFECT_PHASE_PREPARATION")
        _require(prepared["schema"] == "local-hand-q2-fixture-preparation/v1"
                 and prepared["status"] == "RESOURCES_PREPARED" and prepared["reason"] is None
                 and prepared["preparation_id"] == plan["preparation_id"]
                 and all(prepared[key] is False for key in
                         ("q2_accepted", "q3_accepted", "production_supported", "fixture_generated")),
                 "CORE_EFFECT_PHASE_PREPARATION")
        observed = prepared["facts"]
        raw = rows["observer-config"]["raw"]
        path = observed["directories"]["capture"]["path"] + "/" + phase + "/observer.json"
        config = config_api.decode(raw, path, _sha(raw))
        grant = config.active()
        data, request = grant.as_dict(), grant.request.as_dict()
        execution = "job-" + case["operation_id"] + "-" + phase
        _require(config.data()["source_commit"] == CANDIDATE["commit"]
                 and request["execution_id"] == execution and request["phase"] == phase
                 and request["boot_id"] == observed["host"]["boot_id"]
                 and request["generation"] == plan["identity"]["slot_generation"]
                 and all(request[key] == plan["identity"][key]
                         for key in ("authority_digest", "manifest_digest", "epoch")),
                 "CORE_EFFECT_PHASE_GRANT_BINDING")
        budget = data["budget"]
        budget_api.validate_grant(budget, execution_id=execution, phase=phase,
            namespace="job", operation_id=case["operation_id"], record_id=case["operation_id"],
            original_budgets=plan["budgets"]["operation"])
        original_roots = {row["project_id"]: row for row in observed["roots"]}
        _require(len(original_roots) == 7 and set(original_roots) == set(case["project_ids"]),
                 "CORE_EFFECT_PHASE_ROOTS")
        projects = case["project_ids"][3:] if phase == "evidence" else case["project_ids"][:3]
        _require(len(data["roots"]) == len(projects)
                 and {row["project_id"] for row in data["roots"]} == set(projects),
                 "CORE_EFFECT_PHASE_ROOTS")
        for root in data["roots"]:
            original = original_roots.get(root["project_id"])
            _require(original is not None and all(original[key] == value for key, value in root.items()),
                     "CORE_EFFECT_PHASE_ROOTS")
        reservation = values["launcher-reservation"]
        _exact(reservation, ("schema", "fixture_digest", "session", "controller", "started_ns"),
               "CORE_EFFECT_PHASE_RESERVATION")
        _require(reservation["schema"] == ("local-hand-q2-system-launcher-reservation/v1"
                 if case["index"] == 1 else "local-hand-q2-launcher-reservation/v1"
                 if case["index"] == 2 else "local-hand-q4-h11-launcher-reservation/v1")
                 and reservation["session"] == plan["identity"]["session"],
                 "CORE_EFFECT_PHASE_RESERVATION")
        _digest(reservation["fixture_digest"])
        envelope = reservation["controller"]
        _exact(envelope, ("controller", "issued_ns", "deadline_ns", "output_bytes",
                          "storage_bytes", "storage_inodes"), "CORE_EFFECT_PHASE_CONTROLLER")
        _integer(envelope["issued_ns"], 1)
        _integer(reservation["started_ns"], 1)
        controller_api.decode_controller(envelope["controller"])
        target = plan["controllers"]["target"]
        _require(all(envelope["controller"][key] == value for key, value in target.items())
                 and envelope["issued_ns"] <= reservation["started_ns"] < envelope["deadline_ns"]
                 and envelope["deadline_ns"] <= plan["deadlines"]["owner_deadline_ns"]
                 and envelope["deadline_ns"] - envelope["issued_ns"]
                     <= envelope["controller"]["runtime_max_usec"] * 1000
                 and envelope["output_bytes"] == 32768
                 and all(envelope[key] == plan["controllers"]["target_" + key]
                         for key in ("storage_bytes", "storage_inodes")),
                 "CORE_EFFECT_PHASE_CONTROLLER")
        digest = grant.request.digest
        facts = dict(quota_request_id=request["request_id"], quota_request_sha256=digest,
            query_unit=grant.request.query_unit, listener_unit="lhqoc-" + digest + ".service",
            admission_unit="lhqoa-" + digest + ".service",
            budget_deadline_ns=budget["deadline_boottime_ns"],
            phase_deadline_ns=budget_api.phase_deadline_ns(budget),
            stage_deadline_ns=budget_api.phase_deadline_ns(budget) - budget["limits"]["terminate_grace_seconds"] * NS,
            controller_deadline_ns=envelope["deadline_ns"])
        _require(request["deadline_ns"] <= facts["stage_deadline_ns"]
                 and facts["budget_deadline_ns"] <= facts["controller_deadline_ns"],
                 "CORE_EFFECT_PHASE_DEADLINE")
        _phase_raw_binding(case, phase, plan, values, grant.digest, facts)
        _phase_receipt(case, phase, facts, sources)
        return facts
    except DispatchError:
        raise
    except Exception as error:
        raise DispatchError("CORE_EFFECT_PHASE_RAW_INVALID") from error


def _phase_raw_binding(case, phase, plan, values, grant_digest, facts):
    launcher = values["launcher-result"]
    _require(launcher["q3_accepted"] is False and launcher["production_supported"] is False,
             "CORE_EFFECT_PHASE_LAUNCHER")
    if case["index"] != 3:
        result = values["phase-result"]
        _require(result["grant_digest"] == grant_digest and result["q3_accepted"] is False
                 and result["production_supported"] is False, "CORE_EFFECT_PHASE_RESULT")
        if case["index"] == 1:
            _require(result["status"] == "PHASE_CLOSED" and launcher["status"] == "CHAIN_CLOSED"
                     and launcher["grant_digests"][phase] == grant_digest
                     and result["fence"]["request_digest"] == facts["quota_request_sha256"],
                     "CORE_EFFECT_PHASE_RESULT")
        else:
            report = result["case"]
            _require(result["status"] == launcher["status"] == "CANCEL_CASE_RECORDED"
                     and launcher["grant_digest"] == grant_digest and launcher["case"] == report
                     and report["operation_id"] == case["operation_id"]
                     and report["request_digest"] == plan["request"]["request_digest"]
                     and report["phase_deadline_ns"] == facts["stage_deadline_ns"],
                     "CORE_EFFECT_PHASE_CANCEL_BINDING")
    else:
        original = values["recovery-plan"]["recovery"]
        summary = values["recovery-summary"]
        _require(launcher["status"] == "RECOVERY_RECORDED" and launcher["recovery"] == summary,
                 "CORE_EFFECT_PHASE_RECOVERY")
        for item, budget_name in ((original, "budget_deadline_ns"), (summary, "original_deadline_ns")):
            _require(item["operation_id"] == case["operation_id"] and item["phase"] == phase
                     and item[budget_name] == facts["budget_deadline_ns"]
                     and all(item[key] == facts[key] for key in ("phase_deadline_ns", "controller_deadline_ns")),
                     "CORE_EFFECT_PHASE_RECOVERY_DEADLINE")
        expected = next(row for row in plan["phases"] if row["phase"] == phase)
        _require(original["units"] == summary["units"] ==
                 {key: expected[key + "_unit"] for key in ("bootstrap", "helper", "result_reader")},
                 "CORE_EFFECT_PHASE_RECOVERY_UNITS")


def _clock(effects, deadlines):
    now = effects.now()
    _exact(now, ("boot_id", "boottime_ns", "monotonic_ns"), "CORE_DISPATCH_CLOCK_FIELDS")
    _require(now["boot_id"] == deadlines["boot_id"], "CORE_DISPATCH_BOOT_CHANGED")
    _integer(now["boottime_ns"], 1, code="CORE_DISPATCH_CLOCK")
    _integer(now["monotonic_ns"], 1, code="CORE_DISPATCH_CLOCK")
    _require(now["boottime_ns"] < deadlines["boottime_deadline_ns"]
             and now["monotonic_ns"] < deadlines["monotonic_deadline_ns"],
             "CORE_DISPATCH_DEADLINE")
    return now


def _persist(effects, case_id, path, role, value, *, mode=384, raw=False):
    content = value if raw else canonical(value, newline=True)
    returned = effects.persist(case_id, path, content, mode)
    _source(returned, case_id=None if case_id == "carrier" else case_id)
    _require(returned == {"path": path, "role": role, "mode": mode, "raw": content},
             "CORE_DISPATCH_PERSIST_RESULT")
    return returned


def _validate_phase_receipts(case, sources, phase_facts, owner_deadline):
    _require(type(phase_facts) is dict and set(phase_facts) == set(case["phases"]),
             "CORE_DISPATCH_PHASE_FACTS")
    generated = []
    for phase in case["phases"]:
        facts = phase_facts[phase]
        _require(facts["controller_deadline_ns"] <= owner_deadline,
                 "CORE_DISPATCH_CONTROLLER_DEADLINE")
        generated.append((phase, _phase_receipt(case, phase, facts, sources)))
    return generated


def _case_outcome(effects, case, intent, intent_source, deadlines):
    effects._active_case_deadlines = dict(deadlines)
    prepared = effects.prepare_case(case, intent, deadlines["preparation_deadline_ns"])
    _require(type(prepared) is dict, "CORE_DISPATCH_PREPARED")
    now = _clock(effects, effects.context["guest_deadlines"])
    _require(now["boottime_ns"] < deadlines["preparation_deadline_ns"]
             and now["monotonic_ns"] < deadlines["preparation_monotonic_deadline_ns"],
             "CORE_DISPATCH_PREPARATION_DEADLINE")
    owner_deadline = min(now["boottime_ns"] + OWNER_NS, deadlines["remote_final_deadline_ns"])
    owner_mono_deadline = min(now["monotonic_ns"] + OWNER_NS,
                              deadlines["remote_final_monotonic_deadline_ns"])
    effects._active_case_deadlines.update(owner_deadline_ns=owner_deadline,
                                          owner_monotonic_deadline_ns=owner_mono_deadline)
    plan_deadlines = {
        "case_origin_ns": deadlines["case_origin_ns"],
        "preparation_deadline_ns": deadlines["preparation_deadline_ns"],
        "owner_deadline_ns": owner_deadline,
        "remote_final_deadline_ns": deadlines["remote_final_deadline_ns"],
        "carrier_deadline_ns": deadlines["carrier_deadline_ns"],
    }
    planned = effects.plan_case(case, prepared, plan_deadlines)
    _require(type(planned) is dict and set(planned) == {"plan", "sources"},
             "CORE_DISPATCH_PLANNED")
    plan = validate_plan(case, intent, planned["plan"], plan_deadlines)
    sources = [intent_source, *planned["sources"]]
    for source in sources:
        _source(source, case_id=case["case_id"])
    plan_path = "cases/" + case["case_id"] + "/reservation/case-plan.json"
    plan_source = next((item for item in sources if item["path"] == plan_path), None)
    _require(plan_source == {"path": plan_path, "role": "plan", "mode": 384,
                             "raw": canonical(plan, newline=True)},
             "CORE_DISPATCH_PLAN_SOURCE")
    if case["index"] == 1:
        outcome = effects.run_h01(case, prepared, plan)
    elif case["index"] == 2:
        outcome = effects.run_q4(case, prepared, plan)
    else:
        outcome = effects.recover_h11(case, prepared, plan)
    _exact(outcome, ("sources", "observations", "stop", "proof", "seal_id", "summary"),
           "CORE_DISPATCH_OUTCOME_FIELDS")
    sources.extend(outcome["sources"])
    for source in sources:
        _source(source, case_id=case["case_id"])
    phase_facts = {phase: effects.phase_facts(case, phase, plan, sources)
                   for phase in case["phases"]}
    receipts = _validate_phase_receipts(case, sources, phase_facts, owner_deadline)
    prefix = "cases/" + case["case_id"] + "/"
    for phase, receipt in receipts:
        sources.append(_persist(effects, case["case_id"],
                                prefix + "reservation/phase-" + phase + "-receipt.json",
                                "phase-receipt", receipt, mode=384))
    proof = outcome["proof"]
    if case["index"] == 3:
        _validate_h11_proof(proof, case, sources, owner_deadline)
        sources.append(_persist(effects, case["case_id"],
                                prefix + "reservation/h11-recovery-proof.json",
                                "recovery-proof", proof, mode=384))
    else:
        _require(proof is None, "CORE_DISPATCH_UNEXPECTED_PROOF")
    # Add a temporary verdict source only after all other exact members exist.
    expected_without_verdict = set(required_paths(case, seal_id=outcome["seal_id"]))
    expected_without_verdict = {row for row in expected_without_verdict if row[1] != "verdict"}
    actual_without_verdict = {(item["path"], item["role"], item["mode"]) for item in sources}
    _require(actual_without_verdict == expected_without_verdict,
             "CORE_DISPATCH_PREVERDICT_SET")
    placeholder = {"path": prefix + "reservation/case-verdict.json", "role": "verdict",
                   "mode": 384, "raw": b""}
    verdict = _validate_verdict(case, outcome["observations"], outcome["stop"],
                                sources + [placeholder], proof, owner_deadline)
    verdict_source = _persist(effects, case["case_id"], placeholder["path"],
                              "verdict", verdict, mode=384)
    sources.append(verdict_source)
    _validate_source_set(case, sources, seal_id=outcome["seal_id"])
    _require(type(outcome["summary"]) is dict, "CORE_DISPATCH_SUMMARY")
    if case["index"] == 1:
        summary = _h01_summary(case, sources, outcome["summary"], outcome["seal_id"])
    else:
        _require(outcome["summary"] == {} and outcome["seal_id"] is None,
                 "CORE_DISPATCH_NON_H01_SUMMARY")
        summary = {"seal_id": None}
    return sources, verdict, summary, owner_mono_deadline


def _h01_summary(case, sources, observed, seal_id):
    _exact(observed, ("business_invocation_id", "business_wait_status"),
           "CORE_DISPATCH_H01_SUMMARY_INPUT")
    _require(re.fullmatch(r"[0-9a-f]{32}", observed["business_invocation_id"] or "") is not None,
             "CORE_DISPATCH_H01_SUMMARY_INPUT")
    _integer(observed["business_wait_status"], 0, 255,
             "CORE_DISPATCH_H01_SUMMARY_INPUT")
    prefix = "cases/" + case["case_id"] + "/"
    result = next(item for item in sources
                  if item["path"] == prefix + "business/result-03c94c57c840717302854a3f.json")
    evidence = next(item for item in sources
                    if item["path"] == prefix + "business-evidence/" + seal_id + "/seal.json")
    references = [_reference(item, sealed=None) for item in sources]
    references.sort(key=lambda row: (row["role"].encode("ascii"), row["path"].encode("ascii")))
    result_ref = _reference(result, sealed=None)
    execution_id = "job-" + case["operation_id"] + "-business"
    business_unit = next(item["helper_unit"] for item in _phase_units(
        case["operation_id"], case["phases"]) if item["phase"] == "business")
    return {
        "seal_id": seal_id,
        "h01_business_execution": {
            "status": "VERIFIED", "operation_id": case["operation_id"],
            "execution_id": execution_id, "unit": business_unit,
            "invocation_id": observed["business_invocation_id"],
            "wait_status": observed["business_wait_status"], "business_started": True,
            "outcome": "SUCCEEDED", "evidence_sha256": _sha(evidence["raw"]),
        },
        "h01_result_package": {
            "status": "VERIFIED", "result_member": result_ref,
            "result_sha256": result_ref["sha256"],
            "required_members_sha256": _sha(canonical(references)),
        },
    }


def _case_deadlines(now, outer):
    remote_boot = outer["boottime_deadline_ns"] - REMOTE_FINAL_RESERVE_NS
    remote_mono = outer["monotonic_deadline_ns"] - REMOTE_FINAL_RESERVE_NS
    _require(remote_boot - now["boottime_ns"] >= CASE_GATE_NS
             and remote_mono - now["monotonic_ns"] >= CASE_GATE_NS,
             "CORE_DISPATCH_CASE_GATE")
    return {
        "case_origin_ns": now["boottime_ns"],
        "preparation_deadline_ns": min(now["boottime_ns"] + PREPARATION_NS,
                                       remote_boot - OWNER_NS),
        "preparation_monotonic_deadline_ns": min(now["monotonic_ns"] + PREPARATION_NS,
                                                 remote_mono - OWNER_NS),
        "remote_final_deadline_ns": remote_boot,
        "remote_final_monotonic_deadline_ns": remote_mono,
        "carrier_deadline_ns": outer["boottime_deadline_ns"],
    }


def _usage(value, context, frame_bytes):
    fields = ("guest_elapsed_ns", "carrier_cpu_ns", "carrier_memory_peak_bytes",
              "carrier_pids_peak", "stdin_bytes_received", "output_frame_bytes",
              "guest_allocated_bytes", "guest_allocated_inodes", "job_units_started",
              "controller_units_started", "quota_query_units_started",
              "dynamic_quota_units_started", "native_children_started")
    _exact(value, fields, "CORE_DISPATCH_USAGE_FIELDS")
    for key in fields:
        _integer(value[key], 0, code="CORE_DISPATCH_USAGE")
    _require(value["stdin_bytes_received"] == context["stdin_bytes_received"]
             and value["output_frame_bytes"] in (0, frame_bytes), "CORE_DISPATCH_USAGE_BINDING")
    ceilings = {"carrier_cpu_ns": 800 * NS, "carrier_memory_peak_bytes": 1073741824,
                "carrier_pids_peak": 128, "guest_allocated_bytes": 188743680,
                "guest_allocated_inodes": 13440, "job_units_started": 15,
                "controller_units_started": 6, "quota_query_units_started": 5,
                "dynamic_quota_units_started": 15, "native_children_started": 16}
    _require(all(value[key] <= limit for key, limit in ceilings.items()),
             "CORE_DISPATCH_USAGE_LIMIT")
    return value


def _session(context, admission, installation):
    manifest, bind, hello = context["manifest"], context["bind"], context["hello"]
    return {
        "schema": SESSION_SCHEMA, "scope": SCOPE,
        "rule": RULE, "baseline": BASELINE, "owner_decision": OWNER_DECISION,
        "closure": CLOSURE, "implementation": manifest["implementation"],
        "amendment": manifest["amendment"],
        "package": {"basename": bind["package_basename"], "bytes": bind["package_bytes"],
                    "sha256": bind["package_sha256"],
                    "manifest_sha256": _sha(canonical(manifest, newline=True))},
        "entry": manifest["entry"], "locators": manifest["locators"],
        "consumption": _consumption_info(context),
        "session_id": SESSION,
        "outer": {"host_boottime_origin_ns": bind["host_boottime_origin_ns"],
                  "host_monotonic_origin_ns": bind["host_monotonic_origin_ns"],
                  "host_boottime_deadline_ns": bind["host_boottime_deadline_ns"],
                  "host_monotonic_deadline_ns": bind["host_monotonic_deadline_ns"],
                  "clock_margin_ns": bind["clock_margin_ns"],
                  "host_boottime_bind_ns": bind["host_boottime_bind_ns"],
                  "host_monotonic_bind_ns": bind["host_monotonic_bind_ns"],
                  "hello_sha256": bind["hello_sha256"],
                  "mapped_duration_ns": bind["mapped_duration_ns"],
                  "host_remaining_floor_ns": bind["host_remaining_floor_ns"],
                  "guest_duration_cap_ns": bind["guest_duration_cap_ns"],
                  "guest_duration_ns": bind["guest_duration_ns"],
                  "guest_boot_id": hello["guest_boot_id"],
                  "guest_boottime_origin_ns": hello["guest_boottime_origin_ns"],
                  "guest_monotonic_origin_ns": hello["guest_monotonic_origin_ns"],
                  "guest_boottime_deadline_ns": context["guest_deadlines"]["boottime_deadline_ns"],
                  "guest_monotonic_deadline_ns": context["guest_deadlines"]["monotonic_deadline_ns"],
                  "remote_final_reserve_ns": REMOTE_FINAL_RESERVE_NS,
                  "local_final_reserve_ns": bind["local_final_reserve_ns"]},
        "admission": admission, "installation": installation,
        "output": {"stdout_basename": ".lhqcore-20261003a.stdout",
                   "stderr_basename": ".lhqcore-20261003a.stderr",
                   "remote_result_basename": ".lhqcore-20261003a.remote-result.json",
                   "capture_manifest_basename": ".lhqcore-20261003a.capture-manifest.json",
                   "local_receipt_basename": ".lhqcore-20261003a.acceptance-receipt.json",
                   "output_package_bytes": FRAME_LIMIT, "stderr_bytes": STDERR_LIMIT},
        "limits": LIMITS, "cases": [{key: case[key] for key in
                                      ("index", "case_id", "kind", "predecessor",
                                       "preparation_id", "operation_id", "controller_prefix",
                                       "project_ids", "phases")} for case in CASES],
        "state": "REMOTE_FINALIZED",
    }


def _absolute_text(value, code):
    FieldEffects._absolute(value, code)
    return value


def _program_identity(value, code):
    _exact(value, ("path", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes", "sha256"),
           code)
    _absolute_text(value["path"], code)
    for key in ("dev", "uid", "gid", "bytes"):
        _integer(value[key], 0, code=code)
    _integer(value["ino"], 1, code=code)
    _require(value["mode"] in (365, 493) and value["nlink"] == 1,
             code)
    _digest(value["sha256"], code)
    return value


def _validate_admission(value, context):
    _exact(value, ("guest", "programs", "policies", "parents", "filesystems", "capacity", "absence", "binding"),
           "CORE_DISPATCH_ADMISSION_FIELDS")
    _validate_admission_binding(value["binding"], context)
    guest = _exact(value["guest"], (
        "hostname", "dmi_vendor", "dmi_product", "initial_userns", "boot_id", "pid1_exe",
        "pid1_version", "cgroup_version", "ordinary_user", "ordinary_uid", "ordinary_gid",
        "ordinary_groups", "user_manager_unit", "user_manager_invocation_id",
        "user_manager_cgroup",
    ), "CORE_DISPATCH_ADMISSION_GUEST_FIELDS")
    _require(type(guest["hostname"]) is str and 1 <= len(guest["hostname"]) <= 253
             and (guest["dmi_vendor"] in ("QEMU", "KVM") or guest["dmi_product"] == "KVM")
             and guest["cgroup_version"] == 2
             and type(guest["ordinary_user"]) is str
             and type(guest["ordinary_groups"]) is list
             and all(type(item) is int and item >= 0 for item in guest["ordinary_groups"]),
             "CORE_DISPATCH_ADMISSION_GUEST")
    _exact(guest["initial_userns"], ("dev", "ino"),
           "CORE_DISPATCH_ADMISSION_NAMESPACE")
    _integer(guest["initial_userns"]["dev"], 0, code="CORE_DISPATCH_ADMISSION_NAMESPACE")
    _integer(guest["initial_userns"]["ino"], 1, code="CORE_DISPATCH_ADMISSION_NAMESPACE")
    _integer(guest["ordinary_uid"], 1, 2**32 - 2, "CORE_DISPATCH_ADMISSION_ACCOUNT")
    _integer(guest["ordinary_gid"], 1, 2**32 - 2, "CORE_DISPATCH_ADMISSION_ACCOUNT")
    _absolute_text(guest["pid1_exe"], "CORE_DISPATCH_ADMISSION_PID1")
    _require(type(guest["pid1_version"]) is str and guest["pid1_version"].startswith("systemd ")
             and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
                              guest["boot_id"] or "") is not None
             and re.fullmatch(r"[0-9a-f]{32}", guest["user_manager_invocation_id"] or "")
             is not None, "CORE_DISPATCH_ADMISSION_GUEST")
    _absolute_text(guest["user_manager_cgroup"], "CORE_DISPATCH_ADMISSION_GUEST")
    programs = _exact(value["programs"],
                      ("python", "git", "cc", "setpriv", "systemctl", "systemd_run"),
                      "CORE_DISPATCH_ADMISSION_PROGRAM_FIELDS")
    for item in programs.values():
        _program_identity(item, "CORE_DISPATCH_ADMISSION_PROGRAM")
    _require(programs["setpriv"]["path"] == "/usr/bin/setpriv"
             and programs["systemctl"]["path"] == "/usr/bin/systemctl"
             and programs["systemd_run"]["path"] == "/usr/bin/systemd-run",
             "CORE_DISPATCH_ADMISSION_PROGRAM")
    policies = _exact(value["policies"], ("sudo", "sshd", "authorized_keys", "rc"),
                      "CORE_DISPATCH_ADMISSION_POLICY_FIELDS")
    basis = _approved_inputs_envelope(context)["policy_basis"]
    for name, item in policies.items():
        relation = _exact(item.get("relation"), ("stage", "pre_entry_containment", "policy_basis_sha256",
            "predicate_sha256", "snapshot_sha256", "facts_sha256", "matched"), "CORE_ADMIT_POLICY_RELATION")
        _require(relation["stage"] == "POST_ENTRY_PRE_H01_INTENT"
                 and relation["pre_entry_containment"] is False and relation["matched"] is True
                 and relation["policy_basis_sha256"] == _sha(canonical(basis))
                 and relation["predicate_sha256"] == basis["policies"][name]["predicate_sha256"]
                 and relation["snapshot_sha256"] == item["sha256"], "CORE_ADMIT_POLICY_RELATION")
        for key in ("predicate_sha256", "snapshot_sha256", "facts_sha256"):
            _digest(relation[key], "CORE_ADMIT_POLICY_RELATION")
        _exact(item, ("paths", "bytes", "sha256", "relation"),
               "CORE_DISPATCH_ADMISSION_POLICY")
        _require(type(item["paths"]) is list and item["paths"]
                 and all(type(path) is str and path.startswith("/") for path in item["paths"])
                 and type(item["bytes"]) is int and item["bytes"] >= 0
                 and type(item["relation"]) is dict, "CORE_DISPATCH_ADMISSION_POLICY")
        _digest(item["sha256"], "CORE_DISPATCH_ADMISSION_POLICY")
    directory_roles = ("state", "quota", "install", "journal", "evidence")
    cgroup_roles = ("controller_cgroup", "management_cgroup", "supervisor_cgroup",
                    "query_cgroup", "ordinary_cgroup", "retained_ordinary_cgroup")
    parents = _exact(value["parents"], directory_roles + cgroup_roles,
                     "CORE_DISPATCH_ADMISSION_PARENT_FIELDS")
    for role in directory_roles:
        item = _exact(parents[role], ("path", "dev", "ino", "mode", "uid", "gid", "nlink",
                                             "mount_id", "fs_uuid"),
                      "CORE_DISPATCH_ADMISSION_DIRECTORY")
        _absolute_text(item["path"], "CORE_DISPATCH_ADMISSION_DIRECTORY")
        for key in ("dev", "uid", "gid", "mount_id"):
            _integer(item[key], 0, code="CORE_DISPATCH_ADMISSION_DIRECTORY")
        _integer(item["ino"], 1, code="CORE_DISPATCH_ADMISSION_DIRECTORY")
        _require(item["mode"] in (448, 493) and item["nlink"] >= 2
                 and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
                                  item["fs_uuid"] or "") is not None,
                 "CORE_DISPATCH_ADMISSION_DIRECTORY")
    for role in cgroup_roles:
        item = _exact(parents[role], ("path", "dev", "ino", "unit", "invocation_id", "controllers"),
                      "CORE_DISPATCH_ADMISSION_CGROUP")
        _absolute_text(item["path"], "CORE_DISPATCH_ADMISSION_CGROUP")
        _integer(item["dev"], 0, code="CORE_DISPATCH_ADMISSION_CGROUP")
        _integer(item["ino"], 1, code="CORE_DISPATCH_ADMISSION_CGROUP")
        _require(type(item["unit"]) is str and item["unit"].endswith((".slice", ".service"))
                 and re.fullmatch(r"[0-9a-f]{32}", item["invocation_id"] or "") is not None
                 and type(item["controllers"]) is list
                 and all(controller in ("cpu", "memory", "pids")
                         for controller in item["controllers"]),
                 "CORE_DISPATCH_ADMISSION_CGROUP")
    filesystems = _exact(value["filesystems"], directory_roles,
                         "CORE_DISPATCH_ADMISSION_FILESYSTEM_FIELDS")
    for role, item in filesystems.items():
        _exact(item, ("mount_id", "dev", "fs_uuid", "fstype", "mount_options",
                      "bytes_available", "inodes_available"),
               "CORE_DISPATCH_ADMISSION_FILESYSTEM")
        for key in ("mount_id", "dev", "bytes_available", "inodes_available"):
            _integer(item[key], 0, code="CORE_DISPATCH_ADMISSION_FILESYSTEM")
        _require(item["mount_id"] == parents[role]["mount_id"]
                 and item["dev"] == parents[role]["dev"]
                 and item["fs_uuid"] == parents[role]["fs_uuid"]
                 and item["fstype"] == "ext4"
                 and type(item["mount_options"]) is list
                 and all(type(option) is str for option in item["mount_options"]),
                 "CORE_DISPATCH_ADMISSION_FILESYSTEM")
    capacity = value["capacity"]
    _require(type(capacity) is list and capacity, "CORE_DISPATCH_ADMISSION_CAPACITY")
    ordering = []
    seen_roles = set()
    for row in capacity:
        _exact(row, ("dev", "fs_uuid", "roles", "historical_bytes", "historical_inodes",
                     "new_required_bytes", "new_required_inodes", "bytes_available",
                     "inodes_available", "admitted"), "CORE_DISPATCH_ADMISSION_CAPACITY")
        for key in ("dev", "historical_bytes", "historical_inodes", "new_required_bytes",
                    "new_required_inodes", "bytes_available", "inodes_available"):
            _integer(row[key], 0, code="CORE_DISPATCH_ADMISSION_CAPACITY")
        _require(type(row["roles"]) is list and row["roles"]
                 and row["roles"] == sorted(row["roles"])
                 and not (seen_roles & set(row["roles"]))
                 and set(row["roles"]) <= set(directory_roles)
                 and row["admitted"] is True
                 and row["bytes_available"] >= row["historical_bytes"] + row["new_required_bytes"]
                 and row["inodes_available"] >= row["historical_inodes"] + row["new_required_inodes"],
                 "CORE_DISPATCH_ADMISSION_CAPACITY")
        seen_roles.update(row["roles"]); ordering.append((row["dev"], row["fs_uuid"]))
    _require(seen_roles == set(directory_roles) and ordering == sorted(ordering),
             "CORE_DISPATCH_ADMISSION_CAPACITY")
    absence = value["absence"]
    _require(type(absence) is list and absence, "CORE_DISPATCH_ADMISSION_ABSENCE")
    ordering = []
    for row in absence:
        _exact(row, ("kind", "name", "parent_dev", "parent_ino", "project_id", "unit",
                     "absent", "collision"), "CORE_DISPATCH_ADMISSION_ABSENCE")
        _require(row["kind"] in ("path", "project", "unit")
                 and type(row["name"]) is str and row["name"]
                 and row["absent"] is True and row["collision"] is False,
                 "CORE_DISPATCH_ADMISSION_ABSENCE")
        for key in ("parent_dev", "parent_ino", "project_id"):
            _require(row[key] is None or type(row[key]) is int and row[key] >= 0,
                     "CORE_DISPATCH_ADMISSION_ABSENCE")
        _require(row["unit"] is None or type(row["unit"]) is str,
                 "CORE_DISPATCH_ADMISSION_ABSENCE")
        ordering.append((row["kind"], row["name"]))
    _require(ordering == sorted(ordering) and len(ordering) == len(set(ordering)),
             "CORE_DISPATCH_ADMISSION_ABSENCE")
    return value


def _validate_installation(value, manifest):
    _exact(value, ("destination", "staging", "receipt_path", "dev", "ino", "mode", "uid", "gid",
                   "members_sha256", "native_sha256", "projection_sha256", "wheel_sha256",
                   "allocated_bytes", "allocated_inodes", "status"),
           "CORE_DISPATCH_INSTALLATION_FIELDS")
    expected_members = _sha(canonical(manifest["members"]))
    locators = manifest["locators"]
    expected_destination = str(PurePosixPath(locators["install_parent"]) / INSTALL_BASENAME)
    expected_staging = str(PurePosixPath(locators["install_parent"]) / STAGING_BASENAME)
    expected_receipt = str(PurePosixPath(locators["state_parent"]) / SESSION / "carrier"
                           / "installation.json")
    _require(value["members_sha256"] == expected_members
             and value["projection_sha256"] == PROJECTION["sha256"]
             and value["wheel_sha256"] == WHEEL["sha256"] and value["status"] == "INSTALLED"
             and value["destination"] == expected_destination
             and value["staging"] == expected_staging
             and value["receipt_path"] == expected_receipt
             and value["mode"] == 493 and value["uid"] == value["gid"] == 0
             and type(value["dev"]) is int and value["dev"] >= 0
             and type(value["ino"]) is int and value["ino"] > 0
             and type(value["allocated_bytes"]) is int and value["allocated_bytes"] > 0
             and type(value["allocated_inodes"]) is int and value["allocated_inodes"] > 0
             and value["allocated_bytes"] <= LIMITS["shared_bytes"]
             and value["allocated_inodes"] <= LIMITS["shared_inodes"],
             "CORE_DISPATCH_INSTALLATION")
    _digest(value["native_sha256"], "CORE_DISPATCH_INSTALLATION")
    return value


def dispatch(context, effects):
    """Run the exact H01 -> Q4 -> H11 chain and return one complete frame."""
    _validate_context(context)
    _require(isinstance(effects, FieldEffects) or all(hasattr(effects, name) for name in (
        "now", "admit", "install", "persist", "prepare_case", "plan_case", "run_h01",
        "run_q4", "recover_h11", "phase_facts", "usage")), "CORE_DISPATCH_EFFECTS")
    # The first clock/deadline gate precedes every persistent field effect.
    _clock(effects, context["guest_deadlines"])
    admission = _validate_admission(effects.admit({"hello": context["hello"],
                                                   "manifest": context["manifest"],
                                                   "guest_deadlines": context["guest_deadlines"]}), context)
    installation = _validate_installation(effects.install({"manifest": context["manifest"],
                                                           "members": context["members"],
                                                           "admission": admission}),
                                            context["manifest"])
    all_sources = []
    admission_source = _persist(effects, "carrier", "carrier/admission.json",
                                "admission", admission)
    installation_source = _persist(effects, "carrier", "carrier/installation.json",
                                   "installation", installation)
    all_sources.extend((admission_source, installation_source))
    cases_index = []
    h01_execution = h01_package = None
    for case in CASES:
        now = _clock(effects, context["guest_deadlines"])
        deadlines = _case_deadlines(now, context["guest_deadlines"])
        intent = build_intent(case)
        prefix = "cases/" + case["case_id"] + "/"
        intent_source = _persist(effects, case["case_id"], prefix + "intent.json",
                                 "intent", intent)
        sources, verdict, summary, _owner_mono = _case_outcome(
            effects, case, intent, intent_source, deadlines)
        _validate_source_set(case, sources, seal_id=summary.get("seal_id"))
        verdict_source = next(item for item in sources if item["role"] == "verdict")
        cases_index.append({"index": case["index"], "case_id": case["case_id"], "status": "PASS",
                            "semantic_pass": True, "verdict_path": verdict_source["path"],
                            "verdict_sha256": _sha(verdict_source["raw"])})
        if case["index"] == 1:
            _exact(summary, ("seal_id", "h01_business_execution", "h01_result_package"),
                   "CORE_DISPATCH_H01_SUMMARY_FIELDS")
            h01_execution = summary["h01_business_execution"]
            h01_package = summary["h01_result_package"]
        else:
            _require(summary == {"seal_id": None}, "CORE_DISPATCH_NON_H01_SUMMARY")
        all_sources.extend(sources)
    session = _session(context, admission, installation)
    session_source = _persist(effects, "carrier", "carrier/session.json", "session", session)
    all_sources.append(session_source)
    carrier_specs = {(item["path"], item["role"], item["mode"]) for item in all_sources
                     if item["path"].startswith("carrier/")}
    _require(carrier_specs == {("carrier/session.json", "session", 384),
                               ("carrier/admission.json", "admission", 384),
                               ("carrier/installation.json", "installation", 384)},
             "CORE_DISPATCH_CARRIER_SET")
    members = []
    raw_by_path = {}
    for source in all_sources:
        _source(source)
        _require(source["path"] not in raw_by_path, "CORE_DISPATCH_MEMBER_DUPLICATE")
        case_id = "carrier" if source["path"].startswith("carrier/") else source["path"].split("/")[1]
        members.append(_member(source, case_id)); raw_by_path[source["path"]] = source["raw"]
    members.sort(key=lambda row: row["path"].encode("ascii"))
    _require(len(members) == 3 + 32 + 21 + 26 and len(members) <= MEMBER_COUNT_LIMIT,
             "CORE_DISPATCH_MEMBER_COUNT")
    remote = {"schema": REMOTE_SCHEMA, "session_id": SESSION,
              "consumption_sha256": context["bind"]["consumption_sha256"],
              "state": "REMOTE_FINALIZED", "cases": cases_index,
              "h01_business_execution": h01_execution, "h01_result_package": h01_package,
              "usage": None, "missing": []}
    manifest = {"schema": OUTPUT_SCHEMA, "session_id": SESSION, "remote_result": remote,
                "cases": cases_index, "members": members, "limits": OUTPUT_LIMITS}
    # Frame length participates in usage.  Iterate to the unique fixed point.
    usage = effects.usage()
    for _ in range(4):
        remote["usage"] = _usage(usage, context, usage.get("output_frame_bytes", 0))
        raw_manifest = canonical(manifest, newline=True, limit=MANIFEST_LIMIT)
        frame = OUTPUT_MAGIC + struct.pack(">Q", len(raw_manifest)) + raw_manifest + b"".join(
            raw_by_path[item["path"]] for item in members)
        _require(len(frame) <= FRAME_LIMIT, "CORE_DISPATCH_FRAME_LIMIT")
        if usage["output_frame_bytes"] == len(frame):
            break
        usage = dict(usage, output_frame_bytes=len(frame))
    _require(usage["output_frame_bytes"] == len(frame), "CORE_DISPATCH_USAGE_FRAME")
    remote["usage"] = _usage(usage, context, len(frame))
    raw_manifest = canonical(manifest, newline=True, limit=MANIFEST_LIMIT)
    frame = OUTPUT_MAGIC + struct.pack(">Q", len(raw_manifest)) + raw_manifest + b"".join(
        raw_by_path[item["path"]] for item in members)
    _require(len(frame) == usage["output_frame_bytes"] and len(frame) <= FRAME_LIMIT,
             "CORE_DISPATCH_FRAME_LIMIT")
    return frame


__all__ = [
    "DispatchError", "FieldEffects", "build_intent", "validate_plan", "required_paths",
    "phase_source_specs", "dispatch",
]
