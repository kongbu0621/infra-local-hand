"""Closed-A constants and strict records for the one-shot core acceptance delivery.

This module is deliberately side-effect free.  It is shared by the offline
packager, the local carrier client and their tests, but is not an alternate
field entry point.  The three field blobs are self-contained because no code
may be imported before their enclosing package has been completely verified.
"""
from __future__ import annotations

import hashlib
import json
import copy
from pathlib import PurePosixPath
import re


class ContractError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ContractError(code)


SCOPE = "LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1"
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
AMENDMENT_SCOPE = "LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-v1"
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
# Offline lineage only: the wire amendment continues to name its original A/B/C.
WRITER_TRANSPORT_BASELINE = {
    "commit": "60756caedf6a2d978627272e44784d11009ac309",
    "tree": "82df6a8ec23fce903dbb09ca3feb51baacac503c",
    "documents_sha256": {
        "docs/a2-execution/q2-core-writer-transport/REQUIREMENTS.md":
            "8d2f0dcc113eaab0fb086ef5163376e0ca5c17ab3a96fb4bcc90c1fb12a9d213",
        "docs/a2-execution/q2-core-writer-transport/ARCHITECTURE.md":
            "0327482634a6c62abde72b2bfdf8566abda90b6f0dd411fea8f15f1eda175b8f",
        "docs/a2-execution/q2-core-writer-transport/IMPLEMENTATION_PLAN.md":
            "1b0d745142929dfe6d377fad826cab2fce9a40d1fffffc583517721d8c97b109",
    },
}
WRITER_TRANSPORT_OWNER_DECISION = {
    "event": "LH-Q2-CORE-WRITER-TRANSPORT-CLOSURE-20261004-01",
    "record_path": "docs/governance/Q2_CORE_WRITER_TRANSPORT_OWNER_DECISION.md",
    "record_sha256": "f62b3fe38c6b39e9063858a6a03e5fe8285fb78f90c3a2810b2163fc28932f3a",
}
WRITER_TRANSPORT_CLOSURE = {
    "commit": "8e891e11fb6e563353013ac94c201f30a1df66c9",
    "tree": "2c2ae6e075176ca359d411c127267ea1a959ddce",
}
COMPLETION_ADJUSTMENT_BASELINE = {
    "commit": "851a1afe4e55196212aa6913e81e0722deed1032",
    "tree": "5b6c8d3a55d8d0678f2b4543f13df32016630fdd",
    "documents_sha256": {
        "docs/a2-execution/q2-core-completion-adjustment/REQUIREMENTS.md":
            "08bba40c9d9c49b2b8af3a15310597514ea61641512b5ca43c70de35f06d46d1",
        "docs/a2-execution/q2-core-completion-adjustment/ARCHITECTURE.md":
            "adc7e6be062c6b85deacc774d148bce515aa51c965b3dd31152cee4a73f1455f",
        "docs/a2-execution/q2-core-completion-adjustment/IMPLEMENTATION_PLAN.md":
            "a70d51557f034f5f0ec7e626eb6226064a4e604fd6f217267282fe524495f60c",
    },
}
COMPLETION_ADJUSTMENT_OWNER_DECISION = {
    "event": "LH-Q2-CORE-COMPLETION-ADJUSTMENT-CLOSURE-20261004-01",
    "record_path": "docs/governance/Q2_CORE_COMPLETION_ADJUSTMENT_OWNER_DECISION.md",
    "record_sha256": "0f6ec728c28ca658b4c77ab035cc42bbb57e1dbe72a1a8606e579ce08b2a1757",
}
COMPLETION_ADJUSTMENT_CLOSURE = {
    "commit": "c32799c03a32d81deec02f7492c1b71eb47b2b6d",
    "tree": "1ccf7b10f65e43f5099c17c7c7fb7e9f5e5da77b",
}
CANDIDATE = {
    "commit": "4b6e4a7c403362358192086b88679e1326dcb2e1",
    "tree": "4d4349580c9f4b67cc26f601126849c2bc8d76a4",
}
CANDIDATE_PARENT = "607100a57206f7dc7cfcbd6cae8507cfa599b813"
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

SESSION_ID = "lhqcore-20261003a"
INSTALL_BASENAME = "local-hand-core-acceptance-20261003a"
STAGING_BASENAME = ".local-hand-core-acceptance-20261003a.staging"
INSTALL_UUID = "2ba06c6f-d3e5-4e36-a41f-d5991cdd7232"
CARRIER_UNIT = "lhqcore20261003a-carrier.service"
MARKER_BASENAME = ".lhqcore-20261003a.carrier-consumed.json"
OUTPUT_BASENAMES = {
    "stdout_basename": ".lhqcore-20261003a.stdout",
    "stderr_basename": ".lhqcore-20261003a.stderr",
    "remote_result_basename": ".lhqcore-20261003a.remote-result.json",
    "capture_manifest_basename": ".lhqcore-20261003a.capture-manifest.json",
    "local_receipt_basename": ".lhqcore-20261003a.acceptance-receipt.json",
}

PACKAGE_MAGIC = b"LHCFP1\n"
HELLO_MAGIC = b"LHCHLO1\n"
BIND_MAGIC = b"LHCBND1\n"
OUTPUT_MAGIC = b"LHCOUT1\n"
PACKAGE_SCHEMA = "local-hand-q2-core-field-package/v3"
LOCATORS_SCHEMA = "local-hand-q2-core-private-locators/v1"
LOCATOR_RELATION_SCHEMA = "local-hand-q2-core-locator-relation/v2"
CONSUMPTION_SCHEMA = "local-hand-q2-core-carrier-consumption/v2"
HELLO_SCHEMA = "local-hand-q2-core-carrier-hello/v2"
SESSION_SCHEMA = "local-hand-q2-core-dispatch-session/v2"
APPROVED_INPUTS_SCHEMA = "local-hand-q2-core-approved-inputs/v1"
APPROVED_INPUTS_PATH = "private/approved-inputs.json"
APPROVED_INPUTS_LIMIT = 1048576
CARRIER_ARGV_SCHEMA = "local-hand-q2-core-carrier-argv/v1"
MANAGEMENT_BINDING_SCHEMA = "local-hand-q2-core-local-management-binding/v1"
LOCAL_WRITER_SCHEMA = "local-hand-q2-core-local-writer/v1"
TRUTH_EVIDENCE_SCHEMA = "local-hand-q2-core-local-truth-evidence/v1"
PREPARATION_INPUT_SCHEMA = "local-hand-q2-core-preparation-input/v1"

PACKAGE_LIMITS = {
    "package_bytes": 33550320,
    "manifest_bytes": 1048576,
    "members": 4096,
    "member_bytes": 16777216,
    "shared_allocated_bytes": 67108864,
    "shared_entries": 4096,
    "carrier_audit_bytes": 8388608,
    "carrier_audit_inodes": 512,
    "carrier_output_bytes": 62914560,
}
LIMITS = {
    "carrier_seconds": 900,
    "remote_unit_seconds": 800,
    "guest_duration_cap_seconds": 750,
    "preparation_seconds": 150,
    "owner_seconds": 120,
    "case_gate_seconds": 315,
    "hello_frame_bytes": 4112,
    "bind_frame_bytes": 4112,
    "package_bytes": 33550320,
    "carrier_input_bytes": 33554432,
    "output_package_bytes": 58716144,
    "carrier_stderr_bytes": 4194304,
    "carrier_output_bytes": 62914560,
    "host_capture_bytes": 67108864,
    "host_capture_inodes": 16,
    "carrier_cpu_seconds": 800,
    "carrier_memory_bytes": 1073741824,
    "carrier_pids": 128,
    "carrier_audit_bytes": 8388608,
    "carrier_audit_inodes": 512,
    "shared_bytes": 67108864,
    "shared_inodes": 4096,
    "case_physical_bytes": 37748736,
    "case_physical_inodes": 2944,
    "all_case_physical_bytes": 113246208,
    "all_case_physical_inodes": 8832,
    "case_admission_bytes": 71303168,
    "case_admission_inodes": 3968,
    "all_case_admission_bytes": 213909504,
    "all_case_admission_inodes": 11904,
    "all_case_cpu_seconds": 1290,
    "total_cpu_seconds": 2090,
    "all_case_output_bytes": 50331648,
    "peak_memory_bytes": 2751463424,
    "peak_pids": 1160,
    "job_units": 15,
    "controller_units": 6,
    "quota_query_units": 5,
    "dynamic_quota_units": 15,
    "native_children": 16,
    "total_guest_physical_bytes": 188743680,
    "total_guest_physical_inodes": 13440,
    "total_guest_admission_bytes": 289406976,
    "total_guest_admission_inodes": 16512,
}

DIRECTORY_ROLES = (
    "reservation", "state", "authority", "journal", "capture", "declarations",
    "session", "control", "profile_work", "profile_evidence", "profile_temporary",
    "store_parent",
)
ROOT_REFS = (
    "work-a", "evidence-a", "temporary-a", "work-b", "evidence-b", "temporary-b",
    "retained_store",
)
CASES = (
    {
        "index": 1, "case_id": "c01-h01-normal", "kind": "H01_NORMAL", "predecessor": None,
        "preparation_id": "lhqc01h01normal", "operation_id": "b6638120-ed28-4ed1-b603-a153fab1c93d",
        "controller_prefix": "lhqcore20261003a-c01", "project_ids": list(range(12101, 12108)),
        "phases": ["preflight", "business", "evidence"],
    },
    {
        "index": 2, "case_id": "c02-q4-cancel", "kind": "Q4_HELPER_RUNNING_CANCEL_SUBSET",
        "predecessor": "c01-h01-normal", "preparation_id": "lhqc02q4cancel",
        "operation_id": "ade1b42f-f03d-48dc-b690-e588b44289f6",
        "controller_prefix": "lhqcore20261003a-c02", "project_ids": list(range(12108, 12115)),
        "phases": ["preflight"],
    },
    {
        "index": 3, "case_id": "c03-h11-recovery", "kind": "H11_SAME_LEDGER_RECOVERY",
        "predecessor": "c02-q4-cancel", "preparation_id": "lhqc03h11recovery",
        "operation_id": "4b035797-229a-4cdc-8eca-8195869b7ac9",
        "controller_prefix": "lhqcore20261003a-c03", "project_ids": list(range(12115, 12122)),
        "phases": ["preflight"],
    },
)

SCHEMA_FIELDS = {
    HELLO_SCHEMA: (
        "schema", "scope", "loader_sha256", "bootstrap_sha256", "guest_boot_id",
        "guest_boottime_origin_ns", "guest_monotonic_origin_ns", "pid", "uid", "gid",
        "euid", "egid", "python", "carrier_unit", "process_limits", "remote_management",
    ),
    "local-hand-q2-core-carrier-bind/v1": (
        "schema", "scope", "session_id", "hello_sha256", "consumption_sha256",
        "package_basename", "package_bytes", "package_sha256", "host_boottime_origin_ns",
        "host_monotonic_origin_ns", "host_boottime_deadline_ns", "host_monotonic_deadline_ns",
        "host_boottime_bind_ns", "host_monotonic_bind_ns", "host_remaining_floor_ns",
        "clock_margin_ns", "local_final_reserve_ns", "mapped_duration_ns",
        "guest_duration_cap_ns", "guest_duration_ns",
    ),
    SESSION_SCHEMA: (
        "schema", "scope", "rule", "baseline", "owner_decision", "closure",
        "implementation", "amendment", "package", "entry", "locators", "consumption", "session_id",
        "outer", "admission", "installation", "output", "limits", "cases", "state",
    ),
    "local-hand-q2-core-case-intent/v1": (
        "schema", "session_id", "index", "case_id", "kind", "predecessor",
        "preparation_id", "identity", "operation_id", "controller_prefix", "project_ids",
        "directory_roles", "planned_directories", "planned_roots", "preparation_input_sha256",
        "phases", "budgets", "state",
    ),
    "local-hand-q2-core-case-plan/v1": (
        "schema", "session_id", "index", "case_id", "kind", "predecessor",
        "preparation_id", "identity", "principal", "authority_path", "ledger_path", "request",
        "operation_id", "roots", "controllers", "system_geometry", "phases",
        "empty_ledger_expectation", "deadlines", "budgets",
    ),
    "local-hand-q2-core-phase-receipt/v1": (
        "schema", "session_id", "index", "case_id", "phase", "quota_request_id",
        "quota_request_sha256", "query_unit", "listener_unit", "admission_unit",
        "budget_deadline_ns", "phase_deadline_ns", "stage_deadline_ns",
        "controller_deadline_ns", "source_artifacts", "source_artifacts_sha256",
    ),
    "local-hand-q2-core-empty-ledger-gate/v1": (
        "schema", "session_id", "index", "case_id", "ledger_path", "dev", "ino",
        "authority_id", "ledger_id", "snapshot_sha256", "operations", "events", "leases",
        "sidecars", "checked_boottime_ns", "stage", "before_submit",
    ),
    "local-hand-q2-core-ledger-export/v1": (
        "schema", "session_id", "index", "case_id", "authority_id", "ledger_id",
        "operation_id", "ledger_identity", "operation", "events", "sidecars",
        "exported_boottime_ns",
    ),
    "local-hand-q2-core-case-verdict/v1": (
        "schema", "session_id", "index", "case_id", "status", "semantic_pass",
        "observations", "artifacts", "missing", "stop",
    ),
    "local-hand-q2-core-h11-recovery-proof/v1": (
        "schema", "session_id", "index", "case_id", "candidate", "ledger_identity",
        "recovery_plan", "recovery_summary", "launcher_result", "gateway_snapshot",
        "origin_capture", "control_seal", "result_identity", "assertions",
    ),
    "local-hand-q2-core-remote-result/v1": (
        "schema", "session_id", "consumption_sha256", "state", "cases",
        "h01_business_execution", "h01_result_package", "usage", "missing",
    ),
    "local-hand-q2-core-output-package/v1": (
        "schema", "session_id", "remote_result", "cases", "members", "limits",
    ),
    "local-hand-q2-core-capture-manifest/v1": (
        "schema", "session_id", "consumption_sha256", "stdout", "stderr",
        "output_package", "wait", "files", "logical_bytes", "allocated_bytes", "inodes",
        "fsync_complete", "reread_equal", "missing",
    ),
    "local-hand-q2-core-local-acceptance-receipt/v1": (
        "schema", "scope", "session_id", "consumption", "transport", "remote_result",
        "wait", "capture", "real_task_execution", "result_evidence_collection", "state",
        "missing",
    ),
    CONSUMPTION_SCHEMA: (
        "schema", "scope", "session_id", "baseline", "owner_decision", "closure",
        "implementation", "amendment", "candidate", "package", "approved_inputs_sha256",
        "local_management_binding_sha256", "writer", "carrier_argv_sha256",
        "host_boottime_origin_ns", "host_monotonic_origin_ns", "host_boottime_deadline_ns",
        "host_monotonic_deadline_ns", "state",
    ),
    MANAGEMENT_BINDING_SCHEMA: (
        "schema", "anchor", "writer", "wrapper", "fixture_start", "fixture_cloud_config",
        "profile", "environment", "dependencies", "identity", "identity_public", "known_hosts",
        "cwd", "remote_expectation", "transport",
    ),
    LOCAL_WRITER_SCHEMA: (
        "schema", "user_namespace", "pid_namespace", "process", "uid", "gid", "supplementary_gids",
    ),
}

REMOTE_STATES = (
    "REMOTE_PREFIX_STARTED", "BOUND", "REMOTE_ADMITTED", "INSTALLED", "H01_INTENT",
    "H01_PLANNED", "H01_PASS", "Q4_INTENT", "Q4_PLANNED", "Q4_PASS", "H11_INTENT",
    "H11_PLANNED", "H11_RECOVERY_PASS", "REMOTE_FINALIZING", "REMOTE_FINALIZED",
)
LOCAL_STATES = (
    "STATIC_VERIFIED", "CARRIER_CONSUMED", "CONSUMPTION_RECORD_COMPLETE",
    "TRANSPORT_STARTED", "LOCAL_AWAITING_REMOTE", "LOCAL_FINALIZING", "COMPLETE",
)


def sha256(raw):
    require(type(raw) is bytes, "CORE_BYTES")
    return hashlib.sha256(raw).hexdigest()


def _pairs(items):
    value = {}
    for key, item in items:
        require(type(key) is str and key not in value, "CORE_JSON_DUPLICATE_KEY")
        value[key] = item
    return value


def _constant(value):
    raise ContractError("CORE_JSON_NONFINITE")


def _shape(value, depth=0, count=None):
    count = [0] if count is None else count
    count[0] += 1
    require(depth <= 32 and count[0] <= 262144, "CORE_JSON_COMPLEXITY")
    require(not isinstance(value, float), "CORE_JSON_FLOAT")
    if isinstance(value, dict):
        require(all(type(k) is str for k in value), "CORE_JSON_KEY")
        for item in value.values():
            _shape(item, depth + 1, count)
    elif isinstance(value, list):
        for item in value:
            _shape(item, depth + 1, count)
    else:
        require(value is None or type(value) in (str, int, bool), "CORE_JSON_VALUE")
    return value


def canonical(value, *, newline=False, limit=None):
    _shape(value)
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                         allow_nan=False).encode("ascii") + (b"\n" if newline else b"")
    except (TypeError, ValueError, UnicodeError) as error:
        raise ContractError("CORE_JSON_ENCODE") from error
    if limit is not None:
        require(type(limit) is int and 0 <= len(raw) <= limit, "CORE_JSON_LIMIT")
    return raw


def document(raw, *, limit, newline=False):
    require(type(raw) is bytes and 0 < len(raw) <= limit, "CORE_JSON_LIMIT")
    if newline:
        require(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), "CORE_JSON_NEWLINE")
    else:
        require(not raw.endswith(b"\n"), "CORE_JSON_NEWLINE")
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs, parse_constant=_constant)
    except ContractError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractError("CORE_JSON_DECODE") from error
    _shape(value)
    require(canonical(value, newline=newline) == raw, "CORE_JSON_CANONICAL")
    return value


def exact(value, fields, code="CORE_FIELDS"):
    require(type(value) is dict and set(value) == set(fields), code)
    return value


def digest(value, code="CORE_DIGEST"):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, code)
    return value


def commit(value, code="CORE_COMMIT"):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None, code)
    return value


def integer(value, low=0, high=2**63 - 1, code="CORE_INTEGER"):
    require(type(value) is int and low <= value <= high, code)
    return value


def relative_path(value, code="CORE_PATH"):
    require(type(value) is str and value.isascii() and 0 < len(value) <= 4096
            and re.fullmatch(r"[A-Za-z0-9._/-]+", value) is not None
            and "//" not in value and "\\" not in value and "\0" not in value, code)
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value
            and all(part not in ("", ".", "..") for part in path.parts), code)
    return value


def absolute_path(value, code="CORE_ABSOLUTE_PATH"):
    require(type(value) is str and value.isascii() and value.startswith("/")
            and not value.startswith("//") and "\\" not in value and "\0" not in value
            and len(value) <= 4096, code)
    path = PurePosixPath(value)
    require(path.as_posix() == value and ".." not in path.parts, code)
    return value


def validate_record(value, schema=None):
    require(type(value) is dict and type(value.get("schema")) is str, "CORE_RECORD")
    selected = value["schema"] if schema is None else schema
    require(value["schema"] == selected and selected in SCHEMA_FIELDS, "CORE_SCHEMA")
    exact(value, SCHEMA_FIELDS[selected], "CORE_RECORD_FIELDS")
    return value


def validate_amendment(value, *, implementation=None):
    """Check the frozen A/B/C chain; Git ancestry of D is checked at freeze."""
    exact(value, {"baseline", "owner_decision", "closure", "implementation"}, "CORE_AMENDMENT_FIELDS")
    require(value["baseline"] == AMENDMENT_BASELINE
            and value["owner_decision"] == AMENDMENT_OWNER_DECISION
            and value["closure"] == AMENDMENT_CLOSURE, "CORE_AMENDMENT_AUTHORITY")
    current = exact(value["implementation"], {"commit", "tree"}, "CORE_AMENDMENT_IMPLEMENTATION")
    for field in ("commit", "tree"):
        commit(current[field], "CORE_AMENDMENT_IMPLEMENTATION")
        require(current[field] != "0" * 40, "CORE_AMENDMENT_IMPLEMENTATION")
    require(current["commit"] not in {
        BASELINE["commit"], CLOSURE["commit"], AMENDMENT_BASELINE["commit"],
        AMENDMENT_CLOSURE["commit"], "520f77f578b90d31870517e33e29bee42918f3c0",
    }, "CORE_AMENDMENT_IMPLEMENTATION")
    require(implementation is None or current == implementation, "CORE_AMENDMENT_IMPLEMENTATION")
    return value


def validate_local_writer(value):
    """Validate a bound host identity; do not observe or infer current identity."""
    validate_record(value, LOCAL_WRITER_SCHEMA)
    for field in ("user_namespace", "pid_namespace"):
        namespace = exact(value[field], {"dev", "ino"}, "CORE_LOCAL_WRITER_NAMESPACE")
        integer(namespace["dev"], code="CORE_LOCAL_WRITER_NAMESPACE")
        integer(namespace["ino"], 1, code="CORE_LOCAL_WRITER_NAMESPACE")
    process = exact(value["process"], {"pid", "starttime_ticks"}, "CORE_LOCAL_WRITER_PROCESS")
    integer(process["pid"], 1, code="CORE_LOCAL_WRITER_PROCESS")
    integer(process["starttime_ticks"], code="CORE_LOCAL_WRITER_PROCESS")
    for field in ("uid", "gid"):
        identities = exact(value[field], {"real", "effective", "saved", "filesystem"},
                           "CORE_LOCAL_WRITER_CREDENTIALS")
        for item in identities.values():
            integer(item, code="CORE_LOCAL_WRITER_CREDENTIALS")
        require(len(set(identities.values())) == 1, "CORE_LOCAL_WRITER_CREDENTIALS")
    groups = value["supplementary_gids"]
    require(type(groups) is list, "CORE_LOCAL_WRITER_GROUPS")
    for item in groups:
        integer(item, code="CORE_LOCAL_WRITER_GROUPS")
    require(groups == sorted(set(groups)), "CORE_LOCAL_WRITER_GROUPS")
    canonical(value, limit=4096)
    return value


def make_amendment(implementation):
    return validate_amendment({"baseline": copy.deepcopy(AMENDMENT_BASELINE),
        "owner_decision": copy.deepcopy(AMENDMENT_OWNER_DECISION),
        "closure": copy.deepcopy(AMENDMENT_CLOSURE),
        "implementation": copy.deepcopy(implementation)})


APPROVED_COMPONENTS = (
    "source_relation", "policy_basis", "historical_capacity_obligations",
    "retained_preparation", "reconciliation",
)
ADMISSION_BINDING_FIELDS = (
    "approved_inputs_sha256", "approved_source_relation_sha256", "policy_basis_sha256",
    "historical_capacity_obligations_sha256", "retained_preparation_sha256", "reconciliation_sha256",
    "local_management_binding_sha256", "hello_sha256", "remote_management_sha256",
)


def validate_approved_inputs(value, *, amendment=None):
    """Validate only the wire envelope, not private source or live admission."""
    exact(value, {"schema", "scope", "amendment", *APPROVED_COMPONENTS}, "CORE_APPROVED_INPUTS_FIELDS")
    require(value["schema"] == APPROVED_INPUTS_SCHEMA and value["scope"] == SCOPE,
            "CORE_APPROVED_INPUTS_SCHEMA")
    validate_amendment(value["amendment"])
    require(amendment is None or value["amendment"] == amendment, "CORE_APPROVED_INPUTS_AMENDMENT")
    require(all(type(value[key]) is dict and value[key] for key in APPROVED_COMPONENTS),
            "CORE_APPROVED_INPUTS_COMPONENT")
    canonical(value, newline=True, limit=APPROVED_INPUTS_LIMIT)
    return value


def admission_binding(approved_inputs_raw, local_management_binding, hello, *, amendment=None):
    """Compute nine distinct preimages, without claiming source/live admission."""
    approved = validate_approved_inputs(document(approved_inputs_raw,
        limit=APPROVED_INPUTS_LIMIT, newline=True), amendment=amendment)
    validate_record(local_management_binding, MANAGEMENT_BINDING_SCHEMA)
    validate_hello(hello, remote_expectation=local_management_binding["remote_expectation"])
    result = {"approved_inputs_sha256": sha256(approved_inputs_raw)}
    for component, field in zip(APPROVED_COMPONENTS, ADMISSION_BINDING_FIELDS[1:6], strict=True):
        result[field] = sha256(canonical(approved[component]))
    result.update(local_management_binding_sha256=sha256(canonical(local_management_binding, newline=True)),
        hello_sha256=sha256(canonical(hello, newline=True)),
        remote_management_sha256=sha256(canonical(hello["remote_management"])))
    return result


def validate_admission_binding(value, *, approved_inputs_raw, local_management_binding, hello,
                               amendment=None):
    exact(value, ADMISSION_BINDING_FIELDS, "CORE_ADMISSION_BINDING_FIELDS")
    require(value == admission_binding(approved_inputs_raw, local_management_binding, hello,
                                       amendment=amendment), "CORE_ADMISSION_BINDING")
    return value


def validate_bind(value):
    validate_record(value, "local-hand-q2-core-carrier-bind/v1")
    require(value["scope"] == SCOPE and value["session_id"] == SESSION_ID, "CORE_BIND_AUTHORITY")
    for key in ("hello_sha256", "consumption_sha256", "package_sha256"):
        digest(value[key], "CORE_BIND_DIGEST")
    relative_path(value["package_basename"], "CORE_BIND_PACKAGE")
    require(value["package_basename"].endswith(".lhfp"), "CORE_BIND_PACKAGE")
    integer(value["package_bytes"], 1, PACKAGE_LIMITS["package_bytes"], "CORE_BIND_PACKAGE")
    for key in SCHEMA_FIELDS[value["schema"]][8:]:
        integer(value[key], 1 if key in ("mapped_duration_ns", "guest_duration_ns") else 0,
                code="CORE_BIND_CLOCK")
    require(value["host_boottime_deadline_ns"]
            == value["host_boottime_origin_ns"] + 900_000_000_000
            and value["host_monotonic_deadline_ns"]
            == value["host_monotonic_origin_ns"] + 900_000_000_000
            and value["host_boottime_bind_ns"] >= value["host_boottime_origin_ns"]
            and value["host_monotonic_bind_ns"] >= value["host_monotonic_origin_ns"],
            "CORE_BIND_HOST_WINDOW")
    require(value["clock_margin_ns"] == 2_000_000_000
            and value["local_final_reserve_ns"] == 15_000_000_000
            and value["guest_duration_cap_ns"] == 750_000_000_000, "CORE_BIND_LIMIT")
    remaining = min(value["host_boottime_deadline_ns"] - value["host_boottime_bind_ns"],
                    value["host_monotonic_deadline_ns"] - value["host_monotonic_bind_ns"])
    expected_floor = remaining // 1_000_000 * 1_000_000
    require(value["host_boottime_deadline_ns"]
                == value["host_boottime_origin_ns"] + 900_000_000_000
            and value["host_monotonic_deadline_ns"]
                == value["host_monotonic_origin_ns"] + 900_000_000_000
            and value["host_boottime_origin_ns"] <= value["host_boottime_bind_ns"]
            and value["host_monotonic_origin_ns"] <= value["host_monotonic_bind_ns"]
            and remaining > 0 and value["host_remaining_floor_ns"] == expected_floor
            and value["mapped_duration_ns"] == expected_floor - value["clock_margin_ns"]
                - value["local_final_reserve_ns"] > 0
            and value["guest_duration_ns"] == min(value["mapped_duration_ns"],
                                                  value["guest_duration_cap_ns"]),
            "CORE_BIND_MAPPING")
    return value


def validate_remote_management(value, *, expectation=None):
    fields = {"account", "uid", "gid", "home", "login_shell", "parser_profile", "shell",
              "sudo", "env", "systemd_run", "python", "remote_tokens_sha256", "remote_command_sha256"}
    exact(value, fields, "CORE_HELLO_REMOTE_FIELDS")
    require(value["account"] == "q1admin" and value["home"] == "/home/q1admin"
            and value["login_shell"] == "/bin/bash"
            and value["parser_profile"] == "bash-noninteractive-c-v1", "CORE_HELLO_REMOTE_ACCOUNT")
    integer(value["uid"], 1, code="CORE_HELLO_REMOTE_ACCOUNT")
    integer(value["gid"], 1, code="CORE_HELLO_REMOTE_ACCOUNT")
    aliases = {"shell": value["login_shell"], "sudo": "/usr/bin/sudo", "env": "/usr/bin/env",
               "systemd_run": "/usr/bin/systemd-run", "python": "/usr/bin/python3"}
    entity_fields = {"path", "resolved_path", "symlink_chain", "dev", "ino", "mode", "uid", "gid",
                     "nlink", "bytes", "sha256"}
    for role, alias in aliases.items():
        entity = exact(value[role], entity_fields, "CORE_HELLO_REMOTE_ENTITY_FIELDS")
        require(entity["path"] == alias, "CORE_HELLO_REMOTE_ALIAS")
        absolute_path(entity["resolved_path"], "CORE_HELLO_REMOTE_PATH")
        require(len(PurePosixPath(entity["resolved_path"]).parts) - 1 <= 64, "CORE_HELLO_REMOTE_PATH")
        integer(entity["dev"], code="CORE_HELLO_REMOTE_ENTITY")
        integer(entity["ino"], 1, code="CORE_HELLO_REMOTE_ENTITY")
        integer(entity["mode"], 0, 0o7777, "CORE_HELLO_REMOTE_ENTITY")
        integer(entity["uid"], 0, 0, "CORE_HELLO_REMOTE_ENTITY")
        integer(entity["gid"], 0, 0, "CORE_HELLO_REMOTE_ENTITY")
        integer(entity["nlink"], 1, 1, "CORE_HELLO_REMOTE_ENTITY")
        integer(entity["bytes"], 1, 16777216, "CORE_HELLO_REMOTE_ENTITY")
        require(entity["mode"] & 0o111 and not entity["mode"] & 0o022, "CORE_HELLO_REMOTE_ENTITY")
        digest(entity["sha256"], "CORE_HELLO_REMOTE_ENTITY")
        chain = entity["symlink_chain"]
        require(type(chain) is list and len(chain) <= 8, "CORE_HELLO_REMOTE_SYMLINK")
        seen = set()
        for link in chain:
            exact(link, {"path", "target"}, "CORE_HELLO_REMOTE_SYMLINK")
            absolute_path(link["path"], "CORE_HELLO_REMOTE_SYMLINK")
            target = link["target"]
            require(type(target) is str and target and "\0" not in target
                    and len(target.encode("utf-8")) <= 4096 and ".." not in PurePosixPath(target).parts
                    and len(PurePosixPath(target).parts) <= 65
                    and link["path"] not in seen, "CORE_HELLO_REMOTE_SYMLINK")
            seen.add(link["path"])
    for field in ("remote_tokens_sha256", "remote_command_sha256"):
        digest(value[field], "CORE_HELLO_REMOTE_COMMAND")
    if expectation is not None:
        exact(expectation, {"account", "home_path", "login_shell", "hello_schema", "parser_profile",
              "aliases", "remote_tokens_sha256", "remote_command_sha256", "remote_entity_preimages_stage"},
              "CORE_HELLO_EXPECTATION_FIELDS")
        require(expectation["account"] == value["account"]
                and expectation["home_path"] == value["home"]
                and expectation["login_shell"] == value["login_shell"]
                and expectation["hello_schema"] == HELLO_SCHEMA
                and expectation["parser_profile"] == value["parser_profile"]
                and expectation["aliases"] == aliases
                and expectation["remote_entity_preimages_stage"] == "HELLO_JIT"
                and all(expectation[k] == value[k] for k in
                        ("remote_tokens_sha256", "remote_command_sha256")), "CORE_HELLO_REMOTE_EXPECTATION")
    return value


def validate_hello(value, *, loader_sha256=None, bootstrap_sha256=None, remote_expectation=None):
    validate_record(value, HELLO_SCHEMA)
    require(value["scope"] == SCOPE, "CORE_HELLO_AUTHORITY")
    for key, expected in (("loader_sha256", loader_sha256),
                          ("bootstrap_sha256", bootstrap_sha256)):
        digest(value[key], "CORE_HELLO_DIGEST")
        require(expected is None or value[key] == expected, "CORE_HELLO_DIGEST")
    require(type(value["guest_boot_id"]) is str
            and re.fullmatch(r"[0-9a-f-]{36}", value["guest_boot_id"])
            and all(type(value[key]) is int and value[key] > 0 for key in
                    ("guest_boottime_origin_ns", "guest_monotonic_origin_ns", "pid"))
            and all(type(value[key]) is int and value[key] == 0 for key in ("uid", "gid", "euid", "egid")),
            "CORE_HELLO_IDENTITY")
    python = exact(value["python"],
        {"path", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes", "sha256"},
        "CORE_HELLO_PYTHON")
    absolute_path(python["path"], "CORE_HELLO_PYTHON")
    digest(python["sha256"], "CORE_HELLO_PYTHON")
    require(all(type(python[key]) is int for key in
                ("dev", "ino", "mode", "uid", "gid", "nlink", "bytes"))
            and python["dev"] >= 0 and python["ino"] > 0 and python["mode"] & 0o111
            and python["uid"] == python["gid"] == 0 and python["nlink"] == 1
            and python["bytes"] > 0, "CORE_HELLO_PYTHON")
    remote = validate_remote_management(value["remote_management"], expectation=remote_expectation)
    projected = {key: remote["python"][key] for key in python if key != "path"}
    projected["path"] = remote["python"]["resolved_path"]
    require(python == projected, "CORE_HELLO_PYTHON_BINDING")
    unit = exact(value["carrier_unit"],
        {"name", "control_group", "invocation_id", "active_state", "sub_state",
         "runtime_max_usec", "timeout_stop_usec", "memory_max", "memory_swap_max",
         "tasks_max", "cpu_quota_per_sec_usec", "restart", "kill_mode", "exit_type"},
        "CORE_HELLO_CARRIER")
    require(unit["name"] == CARRIER_UNIT and unit["control_group"].endswith("/" + CARRIER_UNIT)
            and re.fullmatch(r"[0-9a-f]{32}", unit["invocation_id"] or "")
            and unit["active_state"] == "active" and unit["sub_state"] in ("running", "start")
            and unit["runtime_max_usec"] == 800_000_000
            and unit["timeout_stop_usec"] == 30_000_000
            and unit["memory_max"] == 1_073_741_824 and unit["memory_swap_max"] == 0
            and unit["tasks_max"] == 128 and unit["cpu_quota_per_sec_usec"] == 1_000_000
            and unit["restart"] == "no" and unit["kill_mode"] == "control-group"
            and unit["exit_type"] == "cgroup", "CORE_HELLO_CARRIER")
    process = exact(value["process_limits"],
        {"cpu_soft", "cpu_hard", "nofile_soft", "nofile_hard", "fsize_soft", "fsize_hard", "umask"},
        "CORE_HELLO_PROCESS_LIMITS")
    require(process == {"cpu_soft": 800, "cpu_hard": 800, "nofile_soft": 256,
                        "nofile_hard": 256, "fsize_soft": 67_108_864,
                        "fsize_hard": 67_108_864, "umask": 0o077},
            "CORE_HELLO_PROCESS_LIMITS")
    require(len(canonical(value, newline=True)) <= 4096, "CORE_HELLO_LIMIT")
    return value


def validate_state_path(states):
    require(type(states) is list and states, "CORE_STATE_PATH")
    require(states[0] in (LOCAL_STATES[0], REMOTE_STATES[0]), "CORE_STATE_PATH")
    local = states[0] == LOCAL_STATES[0]
    chain = list(LOCAL_STATES if local else REMOTE_STATES)
    terminal = "STOP_AND_RETAIN" if local else "REMOTE_STOP_AND_RETAIN"
    require(all(type(item) is str for item in states), "CORE_STATE_PATH")
    if states[-1] == terminal:
        body = states[:-1]
    else:
        body = states
    require(body == chain[:len(body)] and (states[-1] == terminal or len(body) == len(states)),
            "CORE_STATE_PATH")
    return states
