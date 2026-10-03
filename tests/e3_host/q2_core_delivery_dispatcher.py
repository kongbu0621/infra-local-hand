"""Strict field dispatcher for the closed Q2 core acceptance delivery.

The module is a field blob: it is deliberately self-contained and must not
import another D helper.  ``dispatch`` owns all ordering and validation.  The
``FieldEffects`` object owns operating-system effects and is injected into the
dispatcher so the contract can be tested without substituting modeled case
results for field evidence.

The default effect implementation contains only clock and protected
create-only/held-file primitives.  High-level admission, installation and case
execution remain fail-closed until their real implementations are supplied in
this same blob; this is intentional -- constructing a successful result is
never a fallback.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import PurePosixPath
import re
import resource
import stat
import struct
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

# These are not facts that a field implementation may discover and silently
# adopt.  The approved package schema carries only a digest of their private
# source relation.  It does not carry the expected current policy entities or
# the retained obligation rows needed to prove the admission totals and build
# the candidate preparation plan.  Keep this distinction separate from code
# that simply has not been implemented yet.
UNBOUND_APPROVED_INPUTS = (
    "admission.policy_expected_entities",
    "admission.historical_capacity_obligations",
    "preparation.retained_paths_and_domains",
)
UNIMPLEMENTED_FIELD_EFFECTS = (
    "admission.current_guest_collector",
    "installation.protected_staging_and_native_build",
    "preparation.existing_account_completion",
    "execution.h01_normal",
    "execution.q4_running_cancel_subset",
    "execution.h11_same_ledger_recovery",
    "evidence.dynamic_phase_fact_extraction",
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
CONSUMPTION_SCHEMA = "local-hand-q2-core-carrier-consumption/v1"

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


def _validate_context(context):
    _exact(context, ("schema", "hello", "bind", "manifest", "members", "guest_deadlines",
                     "stdin_bytes_received"), "CORE_DISPATCH_CONTEXT_FIELDS")
    _require(context["schema"] == CONTEXT_SCHEMA, "CORE_DISPATCH_CONTEXT_SCHEMA")
    hello, bind, manifest = context["hello"], context["bind"], context["manifest"]
    _exact(hello, ("schema", "scope", "loader_sha256", "bootstrap_sha256", "guest_boot_id",
                   "guest_boottime_origin_ns", "guest_monotonic_origin_ns", "pid", "uid", "gid",
                   "euid", "egid", "python", "carrier_unit", "process_limits"),
           "CORE_DISPATCH_HELLO_FIELDS")
    _require(hello["schema"] == "local-hand-q2-core-carrier-hello/v1"
             and hello["scope"] == SCOPE and hello["uid"] == hello["gid"] == 0
             and hello["euid"] == hello["egid"] == 0, "CORE_DISPATCH_HELLO")
    for key in ("loader_sha256", "bootstrap_sha256"):
        _digest(hello[key], "CORE_DISPATCH_HELLO")
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
                      "members", "limits"), "CORE_DISPATCH_MANIFEST_FIELDS")
    _require(manifest["schema"] == "local-hand-q2-core-field-package/v1"
             and manifest["scope"] == SCOPE and manifest["rule"] == RULE
             and manifest["baseline"] == BASELINE and manifest["owner_decision"] == OWNER_DECISION
             and manifest["closure"] == CLOSURE and manifest["candidate"] == CANDIDATE
             and manifest["wheel"] == WHEEL and manifest["projection"] == PROJECTION
             and manifest["limits"] == PACKAGE_LIMITS, "CORE_DISPATCH_MANIFEST_AUTHORITY")
    _exact(manifest["implementation"], ("commit", "tree"), "CORE_DISPATCH_IMPLEMENTATION")
    _commit(manifest["implementation"]["commit"], "CORE_DISPATCH_IMPLEMENTATION")
    _commit(manifest["implementation"]["tree"], "CORE_DISPATCH_IMPLEMENTATION")
    _require(manifest["implementation"] != CLOSURE, "CORE_DISPATCH_IMPLEMENTATION")
    entry = manifest["entry"]
    _require(type(entry) is dict and entry.get("loader_path") == "field/loader.py"
             and entry.get("bootstrap_path") == "field/bootstrap.py"
             and entry.get("dispatcher_path") == "field/dispatcher.py"
             and hello["loader_sha256"] == entry.get("loader_sha256")
             and hello["bootstrap_sha256"] == entry.get("bootstrap_sha256"),
             "CORE_DISPATCH_ENTRY")
    members = context["members"]
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
    _consumption_info(context)
    return context


def _consumption_info(context):
    manifest, bind = context["manifest"], context["bind"]
    package = {"basename": bind["package_basename"], "bytes": bind["package_bytes"],
               "sha256": bind["package_sha256"],
               "manifest_sha256": _sha(canonical(manifest, newline=True))}
    marker = {
        "schema": CONSUMPTION_SCHEMA, "scope": SCOPE, "session_id": SESSION,
        "baseline": BASELINE, "owner_decision": OWNER_DECISION, "closure": CLOSURE,
        "implementation": manifest["implementation"], "candidate": CANDIDATE,
        "package": package,
        "management_entry_binding_sha256": manifest["entry"]["management_entry_binding_sha256"],
        "carrier_argv_sha256": manifest["entry"]["carrier_argv_sha256"],
        "host_boottime_origin_ns": bind["host_boottime_origin_ns"],
        "host_monotonic_origin_ns": bind["host_monotonic_origin_ns"],
        "host_boottime_deadline_ns": bind["host_boottime_deadline_ns"],
        "host_monotonic_deadline_ns": bind["host_monotonic_deadline_ns"],
        "state": "CONSUMPTION_RECORD_COMPLETE",
    }
    raw = canonical(marker, newline=True, limit=16384)
    _require(_sha(raw) == bind["consumption_sha256"], "CORE_DISPATCH_CONSUMPTION_BINDING")
    return {"basename": ".lhqcore-20261003a.carrier-consumed.json",
            "bytes": len(raw), "sha256": _sha(raw),
            "state": "CONSUMPTION_RECORD_COMPLETE"}


def field_readiness():
    """Return the non-field readiness boundary without performing an effect.

    ``unbound_approved_inputs`` means the exact approved schema does not make
    the required expected facts available to the remote dispatcher.  Those
    facts must not be guessed or adopted from the current machine.
    ``unimplemented_effects`` is ordinary D work that can be completed after
    the inputs are bound.  Keeping the two lists separate prevents a code
    implementation from laundering an input/governance gap into live PASS.
    """
    return {
        "schema": "local-hand-q2-core-field-readiness/v1",
        "scope": SCOPE,
        "releasable": False,
        "unbound_approved_inputs": list(UNBOUND_APPROVED_INPUTS),
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
    """Verify package members needed by the protected installer, in RAM.

    This creates no path, invokes no program and does not turn the package into
    a live-ready package.  It is the deterministic first half of P5 and is
    useful even while P4's expected admission inputs remain unbound.
    """
    manifest, members = context["manifest"], context["members"]
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
        _require(row["mode"] in (420, 493) and row["role"] in (
            "candidate-worktree", "candidate-git-metadata", "wheel", "projection", "field-code"),
            "CORE_EFFECT_PACKAGE_ROW")
        view = members.get(path)
        _require(type(view) is bytes or (isinstance(view, memoryview) and view.readonly),
                 "CORE_EFFECT_PACKAGE_MEMBER")
        raw = bytes(view)
        _require(len(raw) == row["bytes"] and _sha(raw) == row["sha256"],
                 "CORE_EFFECT_PACKAGE_MEMBER")
        origin = row["origin"]
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


class FieldEffects:
    """Field-side effect surface with real, fail-closed storage primitives.

    Construction is inert.  The path primitives below walk from a held root
    descriptor, use ``openat``/``O_NOFOLLOW``, preserve the created inode
    through reread, and fsync both file and parent.  High-level methods remain
    non-releasable for the accurately enumerated reasons returned by
    :func:`field_readiness`; no caller-supplied boolean can bypass them.
    """

    def __init__(self, context):
        self.context = context
        self.held = []
        self._admission = None
        self._installation = None
        self._candidate_root = None
        self._persistence_ready = False
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
                 and type(raw) is bytes and mode in (384, 420),
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
        """Resolve intent-relative objects to the five fixed held parents.

        The intent remains relative as required by A.  This conversion is the
        mandatory boundary before calling candidate preparation validators,
        which require absolute paths.
        """
        _require(case in CASES and type(locators) is dict,
                 "CORE_EFFECT_PREPARATION_PATH_INPUT")
        parents = {role: locators.get(role + "_parent")
                   for role in ("state", "quota", "journal", "evidence")}
        for value in parents.values():
            FieldEffects._absolute(value, "CORE_EFFECT_PREPARATION_PARENT")
        _require(len(set(parents.values())) == len(parents),
                 "CORE_EFFECT_PREPARATION_PARENT_ALIAS")
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
        _require(len({row["path"] for row in directories.values()}) == len(DIRECTORY_ROLES)
                 and len({row["path"] for row in roots}) == 7,
                 "CORE_EFFECT_PREPARATION_PATH_ALIAS")
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

    def admit(self, expected):
        _exact(expected, ("hello", "manifest", "guest_deadlines"),
               "CORE_EFFECT_ADMISSION_INPUT")
        # The current policy objects can be read only after consumption, but A
        # provides no expected entity preimage against which to compare them.
        # Likewise its admission record has only aggregate historical amounts,
        # while the candidate adapter requires exact retained rows.  Adopting
        # either set from the current guest would violate the approved boundary.
        raise DispatchError("CORE_EFFECT_ADMISSION_POLICY_PREIMAGE_UNBOUND")

    def install(self, expected):
        _exact(expected, ("manifest", "members", "admission"),
               "CORE_EFFECT_INSTALLATION_INPUT")
        self.verify_install_inputs()
        _require(self._admission is not None and expected["admission"] == self._admission,
                 "CORE_EFFECT_INSTALLATION_ADMISSION_REQUIRED")
        raise DispatchError("CORE_EFFECT_INSTALLATION_SEQUENCE_UNIMPLEMENTED")

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
        modules = {}
        for name in PREPARATION_HELPERS:
            path = self._candidate_root + "/tests/e3_host/" + name + ".py"
            raw, _identity = self.stable_read(path, maximum=MEMBER_LIMIT, expected_mode=420)
            _require(_sha(raw) == verified["helper_digests"][name],
                     "CORE_EFFECT_HELPER_CHANGED")
            spec = importlib.util.spec_from_file_location("_core_field_" + name, path)
            _require(spec is not None and spec.loader is not None, "CORE_EFFECT_HELPER_LOADER")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules[name] = module
        return modules

    def prepare_case(self, case, intent, preparation_deadline_ns):
        _require(case in CASES and intent == build_intent(case),
                 "CORE_EFFECT_PREPARATION_INPUT")
        _integer(preparation_deadline_ns, 1, code="CORE_EFFECT_PREPARATION_DEADLINE")
        # Even the pure candidate constructor needs exact retained path/domain
        # rows.  They are not present in A's remote package/admission schema.
        raise DispatchError("CORE_EFFECT_PREPARATION_RETAINED_OBLIGATIONS_UNBOUND")

    def plan_case(self, _case, _prepared, _deadlines):
        raise DispatchError("CORE_EFFECT_PLAN_IMPLEMENTATION_HOOK_UNFILLED")

    def run_h01(self, _case, _prepared, _plan):
        raise DispatchError("CORE_EFFECT_H01_IMPLEMENTATION_HOOK_UNFILLED")

    def run_q4(self, _case, _prepared, _plan):
        raise DispatchError("CORE_EFFECT_Q4_IMPLEMENTATION_HOOK_UNFILLED")

    def recover_h11(self, _case, _prepared, _plan):
        # Deliberately no generic run_h11/business-start method exists.
        raise DispatchError("CORE_EFFECT_H11_IMPLEMENTATION_HOOK_UNFILLED")

    def phase_facts(self, _case, _phase, _plan, _sources):
        raise DispatchError("CORE_EFFECT_PHASE_FACTS_IMPLEMENTATION_HOOK_UNFILLED")

    def usage(self):
        elapsed = max(0, time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                      - self._started_boottime_ns)
        cpu = max(0, time.process_time_ns() - self._started_cpu_ns)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KiB.  The field package is Linux-only.
        memory = int(peak) * 1024
        return {"guest_elapsed_ns": elapsed, "carrier_cpu_ns": cpu,
                "carrier_memory_peak_bytes": memory, "carrier_pids_peak": 1,
                "stdin_bytes_received": self.context["stdin_bytes_received"],
                "output_frame_bytes": 0, "guest_allocated_bytes": 0,
                "guest_allocated_inodes": 0, **self._unit_counts}


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
        _require(facts["controller_deadline_ns"] == owner_deadline,
                 "CORE_DISPATCH_CONTROLLER_DEADLINE")
        generated.append((phase, _phase_receipt(case, phase, facts, sources)))
    return generated


def _case_outcome(effects, case, intent, intent_source, deadlines):
    prepared = effects.prepare_case(case, intent, deadlines["preparation_deadline_ns"])
    _require(type(prepared) is dict, "CORE_DISPATCH_PREPARED")
    now = _clock(effects, effects.context["guest_deadlines"])
    _require(now["boottime_ns"] < deadlines["preparation_deadline_ns"]
             and now["monotonic_ns"] < deadlines["preparation_monotonic_deadline_ns"],
             "CORE_DISPATCH_PREPARATION_DEADLINE")
    owner_deadline = min(now["boottime_ns"] + OWNER_NS, deadlines["remote_final_deadline_ns"])
    owner_mono_deadline = min(now["monotonic_ns"] + OWNER_NS,
                              deadlines["remote_final_monotonic_deadline_ns"])
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
        "schema": "local-hand-q2-core-dispatch-session/v1", "scope": SCOPE,
        "rule": RULE, "baseline": BASELINE, "owner_decision": OWNER_DECISION,
        "closure": CLOSURE, "implementation": manifest["implementation"],
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


def _validate_admission(value):
    _exact(value, ("guest", "programs", "policies", "parents", "filesystems", "capacity", "absence"),
           "CORE_DISPATCH_ADMISSION_FIELDS")
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
    for item in policies.values():
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
                                                   "guest_deadlines": context["guest_deadlines"]}))
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
