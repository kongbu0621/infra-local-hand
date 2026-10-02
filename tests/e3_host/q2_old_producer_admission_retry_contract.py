"""Public-safe partial contract prototype for the old-producer admission retry.

The module can only build and inspect a non-executable contract prototype.  It
does not know a host path, SSH target, credential, command, or field authority;
it never reads the host, creates a marker, or starts a process.  A future field
package is deliberately a different artifact and requires a complete contract,
qualification evidence, and separate approval.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
import stat
import zipfile


SCOPE = "LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1"
BATCH = "20261002a"
RULE = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
BASELINE = "68424df2ddbf812b9479ffa7a64dcaa59a2a9f76"
CLOSURE = "179652cb9487163d83c004d358e4d4b49409694c"
OWNER_DECISION = "LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-CLOSURE-20261002-01"
OWNER_DECISION_RECORD = (
    "docs/governance/Q2_OLD_PRODUCER_ADMISSION_RETRY_OWNER_DECISION.md"
)

PRODUCT = dict(
    commit="1a900e4a38e9567655f21cbf3c3f17941de1a8d5",
    tree="ffffce7258036a974d44f6dc8b3ed022d4127aac",
    payload_sha256="fbd773a9a669440ad015dfe0967b3d505d3cabc91b11fee7ddb4015d90aae118",
    artifacts={
        "source.bundle": "36fddae6dd57b2d80b90b4eff5d5bf40cb2f6a29d91d946c1bbefabdb5ae2fc0",
        "wheel": "76a2573f9b5f0a1e9e260bf215f57d6cd011f49736653e0939ebd1b2ba034d9a",
        "code-manifest.json": "c764a4f6a05d2b6aaa6f8c1d35617a520dba1c1e91fad54b0e93e02ba856fe86",
    },
)
KERNEL_READER = dict(
    scope="LH-Q2-KERNEL-FACT-READ-v1",
    baseline="887b640b394f9983f37dfe97c58ba35aaa099359",
    closure="f7f8b503470725ca1ba18d1cb8d8b39e09a15ea8",
    implementation="e15c633adbdfbf1e29cb12b2410975fe4911458d",
)
PRIVATE_HELPER = dict(
    before_sha256="4014a80998469607f8a279a4fc7b7abbeff61e349657b7d8224429d142dfa8db",
    after_sha256="3e6521f6065a3bb61e12b0f2cdcbf1c7f2d40e138269bf85d386aeb2741ab21a",
    repair_zip_bytes=12864,
    repair_zip_sha256="2ddb55db15f73738116377de6fb8fa8fba9c5cc2cf23f1f59e2dc112ce63be70",
    normalized_empty_fields=["ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost"],
)

PREDECESSOR = dict(
    batch="20261001e",
    history_type="PRE_PROVISION_FAILURE",
    status="FAILED_RETAINED",
    delivery_zip={
        "bytes": 3887651,
        "sha256": "5805dcd2a45f150f0e5b7062a17b46137d53e889e1ea160601d7c75fb529e886",
    },
    evidence_zip={
        "bytes": 129584,
        "sha256": "f352d1d8bc70d3d4c419c21de493efca2c51a3453dc90d04fba3ec654e7e33b6",
    },
    records={
        "intent": "c4e45fc7fa217722fe57f7576d85c72181ad93a9cdf422e0a3919b77a1493a48",
        "receipt": "1bc8d61538d0c48f604e3bf2fb7002b481bb62e7f0c3c7ffc433c0818ef5b1f5",
        "plan": "85633b837718282ba6590b7a6679d51aa60addfb0f5be39ea929af83de4a45c1",
        "preflight": "eabe18b207e68967e65b9dc9d114466aad7284063cff6e90814938a0ae9fb086",
        "failure": "79ccccf1745bcad29089c381e692ca777c7fc2165cd31cc1f54ed825db545b85",
        "consumed": "ba29f6c3dcfab18708f1d67de58a5bb8bff1918b4d01c3fd49b67ee1c70156ee",
        "staged": "63fd8aa4b3f8cc406b47b94109d547d4ecdc85d147034e45b068e65e222a08ae",
        "client-result": "ef898352c22ffc601f2617327918a0f0baa45d45def99e487bde45e41e1878cd",
    },
    failure_stage="OLD_PRODUCER_ADMISSION",
    first_error="KeyError: ExecStartPre",
    outer_exit_status=1,
    field_authority_consumed=True,
    provision_reached=False,
    normal_chain_executions=0,
    resource_refund=False,
    retained=True,
)

HOST_COMPONENTS = dict(
    host_window={
        "baseline": "8402f0cc82d8a0ac0b9a56716bf276f41cafea37",
        "closure": "271c07cd16140aa5942dcf3fad468003c58b6b0e",
        "implementation": "f1814b27adbc1bcdb6d6ac14875e9d2ec6a795ff",
        "read_only_preflight": "0a456a909821fd1fc6a4fdec43b9e16bc88679f2",
    },
    ordinary_writer={"implementation": "c2373313eb78aa55373cb0318d08d5f60424dafd"},
    parent_allocation={"implementation": "530a2a45bc6e96270771ccf266793e471d8408ee"},
    kernel_reader=copy.deepcopy(KERNEL_READER),
)

PROTOTYPE_SCHEMA = "local-hand-q2-old-producer-admission-retry-prototype/v1"
LOCATOR_SCHEMA = "local-hand-q2-old-producer-admission-retry-host-locator/v1"
CONTEXT_SCHEMA = "local-hand-q2-old-producer-admission-retry-host-context/v1"
PARENT_SCHEMA = "local-hand-q2-old-producer-admission-retry-parent/v1"
OPERATOR_SCHEMA = "local-hand-q2-old-producer-admission-retry-operator/v1"
INTENT_SCHEMA = "local-hand-q2-old-producer-admission-retry-host-intent/v1"
CONSUMER_RESULT_SCHEMA = "local-hand-q2-old-producer-admission-retry-kernel-observation/v1"
HANDSHAKE_SCHEMA = "local-hand-q2-old-producer-admission-retry-handshake/v1"
RUN_PERMISSION = "old_producer_admission_retry_20261002a_once"
DIRECTORY_NAME = "q2-old-producer-admission-retry-" + hashlib.sha256(
    (SCOPE + ":" + BATCH).encode("utf-8")
).hexdigest()
INTENT_NAME = "host-intent.json"

BASE = "/opt/local-hand-resume-5ca9753-20261002a"
CODE = "/opt/local-hand-code-20261002a"
OUTER_UNIT = "local-hand-resume-5ca9753-20261002a.service"
ORDINARY_SLICE = "lhqq2controller-ordinary20261002a.slice"
SUPERVISOR_UNIT = "lhqnormal20261002a-supervisor.service"
TARGET_UNIT = "lhqnormal20261002a-target.service"
PROJECTS = {
    "work-a": 12061,
    "evidence-a": 12062,
    "temporary-a": 12063,
    "work-b": 12064,
    "evidence-b": 12065,
    "temporary-b": 12066,
    "retained_store": 12067,
}

PROJECT_QUOTA = {"logical_bytes": 1024**2, "inodes": 128}
HOST_RECORD = dict(
    directory=DIRECTORY_NAME,
    directory_mode=0o700,
    intent_name=INTENT_NAME,
    intent_mode=0o400,
    intent_schema=INTENT_SCHEMA,
    run_permission=RUN_PERMISSION,
    intent_file_max_logical_bytes=12 * 1024,
    record_total_max_logical_bytes=16 * 1024,
    record_max_allocated_bytes=64 * 1024,
    record_max_inodes=4,
    clock_order={
        "anchor": ["CLOCK_BOOTTIME", "CLOCK_MONOTONIC"],
        "guard": ["CLOCK_MONOTONIC", "CLOCK_BOOTTIME"],
    },
    deadlines_seconds={"outer": 300, "preparation": 150, "owner": 120},
    floor_unit_ns=1000000,
    sampling_margin_ns=2000000000,
    refresh_allowed=False,
    handshake={
        "schema": HANDSHAKE_SCHEMA,
        "version": 1,
        "order": ["HELLO", "BIND", "READY"],
        "single_remote_exec_ssh_channel": True,
        "second_ssh_or_scp_allowed": False,
    },
)

GOVERNANCE = {
    "trusted_storage_no_same_uid_tamper": {
        "owner_accepted": True,
        "technical_rollback_proof": False,
        "same_host_boot_only": True,
        "unknown_or_violation_result": "BLOCKED_UNKNOWN",
    }
}

QUALIFICATIONS = dict(
    contract_completeness="PARTIAL_NON_EXECUTABLE_PROTOTYPE",
    h07={
        "status": "OPEN",
        "whole_run_rate_pause_proven": False,
        "independent_remote_stop_proven": False,
        "supplemental_approval_chain": [],
    },
    consumption_parent={
        "filesystem_qualified": False,
        "peak_and_persistence_qualified": False,
        "supplemental_approval_chain": [],
    },
    evidence_parent={
        "filesystem_qualified": False,
        "evidence_limits_qualified": False,
        "peak_and_persistence_qualified": False,
        "supplemental_approval_chain": [],
    },
    namespace_alignment="EXTERNAL_ASSUMPTION_NOT_PROVEN",
    p4={
        "stable_event_issued": False,
        "stable_event": None,
        "stable_record_ref": None,
        "executable_package_authorized": False,
        "task_member_present": False,
        "field_execution_authorized": False,
        "retry_allowed": False,
    },
)

PROTOTYPE_MEMBERS = (
    "MANIFEST.json",
    "NON_EXECUTABLE.txt",
    "SHA256SUMS",
    "host-context.json",
    "host-locator.json",
)
NOTICE = (
    b"PARTIAL NON-EXECUTABLE CONTRACT PROTOTYPE ONLY\n"
    b"field_ready=false; allow_run=false; no TASK.txt; no guest execution authority.\n"
)
BLOCKERS = (
    "P2_FUTURE_PACKAGE_CONTRACT_INCOMPLETE",
    "H07_RATE_PAUSE_AND_INDEPENDENT_REMOTE_STOP_UNPROVEN",
    "CONSUMPTION_PARENT_FILESYSTEM_UNPROVEN",
    "CONSUMPTION_PARENT_PEAK_AND_PERSISTENCE_UNPROVEN",
    "EVIDENCE_PARENT_FILESYSTEM_UNPROVEN",
    "EVIDENCE_PARENT_LIMITS_PEAK_AND_PERSISTENCE_UNPROVEN",
    "OWNER_P4_STABLE_EVENT_NOT_ISSUED",
)
INPUT_LIMIT = 256 * 1024
ZIP_LIMIT = 512 * 1024
INTEGER_LIMIT = 2**63 - 1


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    require(type(raw) is bytes, "OLD_PRODUCER_RETRY_BYTES")
    return hashlib.sha256(raw).hexdigest()


def _number(value, low=0, high=INTEGER_LIMIT):
    require(type(value) is int and low <= value <= high, "OLD_PRODUCER_RETRY_INTEGER")
    return value


def _token(value, pattern, maximum=256):
    require(type(value) is str and len(value.encode("utf-8")) <= maximum
        and re.fullmatch(pattern, value) is not None, "OLD_PRODUCER_RETRY_TOKEN")
    return value


def _digest(value, length=64):
    return _token(value, rf"[0-9a-f]{{{length}}}")


def _keys(value, names, reason="OLD_PRODUCER_RETRY_FIELDS"):
    require(type(value) is dict and set(value) == set(names), reason)


def _same(value, expected):
    """Compare JSON-like values without Python's bool/int aliasing."""
    if type(value) is not type(expected):
        return False
    if type(expected) is dict:
        return set(value) == set(expected) and all(
            _same(value[name], expected[name]) for name in expected
        )
    if type(expected) is list:
        return len(value) == len(expected) and all(
            _same(item, wanted) for item, wanted in zip(value, expected)
        )
    return value == expected


def _path(value):
    _token(value, r"/[A-Za-z0-9_@./-]+", 4096)
    parsed = PurePosixPath(value)
    require(value != "/" and not value.startswith("//") and str(parsed) == value
        and ".." not in parsed.parts, "OLD_PRODUCER_RETRY_PATH")
    return value


def document(raw, *, limit=INPUT_LIMIT):
    require(type(raw) is bytes and 0 < len(raw) <= limit, "OLD_PRODUCER_RETRY_INPUT_LIMIT")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "OLD_PRODUCER_RETRY_DUPLICATE_KEY")
            result[key] = value
        return result

    def reject(_):
        raise ValueError("OLD_PRODUCER_RETRY_NUMBER")

    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_float=reject,
            parse_constant=reject)
    except (UnicodeError, RecursionError, json.JSONDecodeError):
        raise ValueError("OLD_PRODUCER_RETRY_JSON") from None
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        require(depth <= 24 and count <= 8192, "OLD_PRODUCER_RETRY_COMPLEXITY")
        if type(item) is dict:
            require(len(item) <= 256 and all(type(key) is str for key in item),
                "OLD_PRODUCER_RETRY_COMPLEXITY")
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            require(len(item) <= 65536, "OLD_PRODUCER_RETRY_COMPLEXITY")
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is int:
            _number(item)
        elif type(item) is str:
            require(len(item.encode("utf-8")) <= limit, "OLD_PRODUCER_RETRY_STRING")
        else:
            require(item is None or type(item) is bool, "OLD_PRODUCER_RETRY_VALUE")
    return value


def encoded(value, *, limit=INPUT_LIMIT):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
    except (TypeError, ValueError, RecursionError):
        raise ValueError("OLD_PRODUCER_RETRY_JSON") from None
    require(len(raw) <= limit, "OLD_PRODUCER_RETRY_INPUT_LIMIT")
    return raw


def validate_operator(value):
    _keys(value, ("schema", "uid", "gid", "groups"))
    require(value["schema"] == OPERATOR_SCHEMA, "OLD_PRODUCER_RETRY_OPERATOR_SCHEMA")
    for name in ("uid", "gid"):
        triple = value[name]
        require(type(triple) is list and len(triple) == 3,
            "OLD_PRODUCER_RETRY_ORDINARY_IDENTITY")
        for item in triple:
            _number(item, 1, 2**32 - 2)
        require(triple[0] == triple[1] == triple[2],
            "OLD_PRODUCER_RETRY_ORDINARY_IDENTITY")
    groups = value["groups"]
    require(type(groups) is list and len(groups) <= 65536,
        "OLD_PRODUCER_RETRY_ORDINARY_GROUPS")
    for item in groups:
        _number(item, 0, 2**32 - 2)
    require(groups == sorted(groups), "OLD_PRODUCER_RETRY_ORDINARY_GROUPS")
    return copy.deepcopy(value)


def validate_parent(value):
    _keys(value, ("schema", "path", "type", "uid", "gid", "mode", "device", "inode"))
    require(value["schema"] == PARENT_SCHEMA and value["type"] == "directory",
        "OLD_PRODUCER_RETRY_PARENT_SCHEMA")
    _path(value["path"])
    _number(value["uid"], 1, 2**32 - 2)
    _number(value["gid"], 1, 2**32 - 2)
    _number(value["device"], 1)
    _number(value["inode"], 1)
    require(type(value["mode"]) is int and 0 <= value["mode"] <= 0o7777
        and value["mode"] & 0o6022 == 0, "OLD_PRODUCER_RETRY_PARENT_MODE")
    return copy.deepcopy(value)


def validate_locator(raw):
    value = document(raw)
    _keys(value, ("schema", "parent"))
    require(value["schema"] == LOCATOR_SCHEMA, "OLD_PRODUCER_RETRY_LOCATOR_SCHEMA")
    value["parent"] = validate_parent(value["parent"])
    return value


def _boot(value):
    return _token(value,
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", 36)


def validate_context(raw, locator_raw):
    locator = validate_locator(locator_raw)
    value = document(raw)
    _keys(value, ("schema", "locator_sha256", "expected_host_boot_id", "operator",
        "ssh_identity_sha256", "guest_identity_sha256", "evidence_parent"))
    require(value["schema"] == CONTEXT_SCHEMA and value["locator_sha256"] == sha(locator_raw),
        "OLD_PRODUCER_RETRY_CONTEXT_BINDING")
    _boot(value["expected_host_boot_id"])
    value["operator"] = validate_operator(value["operator"])
    _digest(value["ssh_identity_sha256"])
    _digest(value["guest_identity_sha256"])
    value["evidence_parent"] = validate_parent(value["evidence_parent"])
    uid, gid = value["operator"]["uid"][0], value["operator"]["gid"][0]
    require(locator["parent"]["uid"] == value["evidence_parent"]["uid"] == uid
        and locator["parent"]["gid"] == value["evidence_parent"]["gid"] == gid,
        "OLD_PRODUCER_RETRY_PARENT_OPERATOR_BINDING")
    return value


def validate_evidence(value):
    fields = ("basename", "evidence_max_frame_bytes", "evidence_max_archive_logical_bytes",
        "evidence_max_archive_allocated_bytes", "evidence_archive_inode_count")
    _keys(value, fields)
    basename = _token(value["basename"], r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
    control_members = set(PROTOTYPE_MEMBERS) | {"TASK.txt"}
    require("/" not in basename and basename.endswith(".zip")
        and basename not in control_members,
        "OLD_PRODUCER_RETRY_EVIDENCE_NAME")
    frame = _number(value["evidence_max_frame_bytes"], 1, 16 * 1024**2)
    logical = _number(value["evidence_max_archive_logical_bytes"], 1, 20 * 1024**2)
    _number(value["evidence_max_archive_allocated_bytes"], 1, 20 * 1024**2)
    inode_count = _number(value["evidence_archive_inode_count"], 1, 1)
    require(inode_count == 1 and frame > logical,
        "OLD_PRODUCER_RETRY_EVIDENCE_LIMITS")
    return copy.deepcopy(value)


def _reference(name, raw, schema):
    return dict(member=name, bytes=len(raw), sha256=sha(raw), parser_schema=schema)


def make_manifest(*, implementation_commit, implementation_tree, locator_raw,
                  context_raw, evidence):
    _digest(implementation_commit, 40)
    _digest(implementation_tree, 40)
    locator = validate_locator(locator_raw)
    context = validate_context(context_raw, locator_raw)
    evidence = validate_evidence(evidence)
    components = copy.deepcopy(HOST_COMPONENTS)
    components["consumer_integration"] = {
        "scope": SCOPE,
        "result_schema": CONSUMER_RESULT_SCHEMA,
        "implementation_commit": implementation_commit,
    }
    value = dict(
        schema=PROTOTYPE_SCHEMA,
        purpose="NON_EXECUTABLE_PARTIAL_CONTRACT_PROTOTYPE",
        authority=dict(rule=RULE, baseline=BASELINE, closure=CLOSURE,
            owner_decision_event=OWNER_DECISION,
            owner_decision_record_ref=OWNER_DECISION_RECORD,
            implementation_commit=implementation_commit,
            implementation_tree=implementation_tree,
            p4_event=dict(issued=False, event=None, record_ref=None)),
        scope=SCOPE,
        batch=BATCH,
        product=copy.deepcopy(PRODUCT),
        kernel_reader=copy.deepcopy(KERNEL_READER),
        private_helper=copy.deepcopy(PRIVATE_HELPER),
        predecessor=copy.deepcopy(PREDECESSOR),
        components=components,
        new_objects=dict(base=BASE, code=CODE, outer_unit=OUTER_UNIT,
            ordinary_slice=ORDINARY_SLICE, supervisor_unit=SUPERVISOR_UNIT,
            target_unit=TARGET_UNIT, suffix=BATCH, create_only=True,
            projects=copy.deepcopy(PROJECTS), project_quota=copy.deepcopy(PROJECT_QUOTA)),
        locator=_reference("host-locator.json", locator_raw, LOCATOR_SCHEMA),
        context=_reference("host-context.json", context_raw, CONTEXT_SCHEMA),
        host_record=copy.deepcopy(HOST_RECORD),
        evidence=evidence,
        governance=copy.deepcopy(GOVERNANCE),
        qualifications=copy.deepcopy(QUALIFICATIONS),
        status=dict(field_ready=False, allow_run=False, guest_executed=False,
            normal_chain_executions=0, q2_accepted=False, q3_accepted=False,
            production_supported=False, executable=False, task_member_present=False,
            future_package_contract_complete=False, p4_contract_qualified=False,
            blockers=list(BLOCKERS)),
    )
    return validate_manifest(value, locator_raw, context_raw)


def validate_manifest(value, locator_raw, context_raw, *, implementation_commit=None,
                      implementation_tree=None):
    _keys(value, ("schema", "purpose", "authority", "scope", "batch", "product",
        "kernel_reader", "private_helper", "predecessor", "components", "new_objects",
        "locator", "context", "host_record", "evidence", "governance",
        "qualifications", "status"))
    require(value["schema"] == PROTOTYPE_SCHEMA
        and value["purpose"] == "NON_EXECUTABLE_PARTIAL_CONTRACT_PROTOTYPE"
        and value["scope"] == SCOPE and value["batch"] == BATCH,
        "OLD_PRODUCER_RETRY_PROTOTYPE_IDENTITY")
    authority = value["authority"]
    _keys(authority, ("rule", "baseline", "closure", "owner_decision_event",
        "owner_decision_record_ref", "implementation_commit", "implementation_tree",
        "p4_event"))
    require(tuple(authority[name] for name in ("rule", "baseline", "closure",
        "owner_decision_event", "owner_decision_record_ref"))
        == (RULE, BASELINE, CLOSURE, OWNER_DECISION, OWNER_DECISION_RECORD),
        "OLD_PRODUCER_RETRY_AUTHORITY")
    require(_same(authority["p4_event"],
        {"issued": False, "event": None, "record_ref": None}),
        "OLD_PRODUCER_RETRY_P4_AUTHORITY")
    _digest(authority["implementation_commit"], 40)
    _digest(authority["implementation_tree"], 40)
    if implementation_commit is not None:
        require(authority["implementation_commit"] == implementation_commit,
            "OLD_PRODUCER_RETRY_IMPLEMENTATION")
    if implementation_tree is not None:
        require(authority["implementation_tree"] == implementation_tree,
            "OLD_PRODUCER_RETRY_IMPLEMENTATION")
    require(authority["implementation_commit"] not in
        (RULE, BASELINE, CLOSURE, PRODUCT["commit"], KERNEL_READER["baseline"],
         KERNEL_READER["closure"], KERNEL_READER["implementation"]),
        "OLD_PRODUCER_RETRY_IMPLEMENTATION")
    require(_same(value["product"], PRODUCT)
        and _same(value["kernel_reader"], KERNEL_READER)
        and _same(value["private_helper"], PRIVATE_HELPER),
        "OLD_PRODUCER_RETRY_FIXED_INPUTS")
    require(_same(value["predecessor"], PREDECESSOR),
        "OLD_PRODUCER_RETRY_OLD_FAILURE")
    expected_components = copy.deepcopy(HOST_COMPONENTS)
    expected_components["consumer_integration"] = {
        "scope": SCOPE,
        "result_schema": CONSUMER_RESULT_SCHEMA,
        "implementation_commit": authority["implementation_commit"],
    }
    require(_same(value["components"], expected_components),
        "OLD_PRODUCER_RETRY_COMPONENTS")
    expected_objects = dict(base=BASE, code=CODE, outer_unit=OUTER_UNIT,
        ordinary_slice=ORDINARY_SLICE, supervisor_unit=SUPERVISOR_UNIT,
        target_unit=TARGET_UNIT, suffix=BATCH, create_only=True,
        projects=PROJECTS, project_quota=PROJECT_QUOTA)
    require(_same(value["new_objects"], expected_objects),
        "OLD_PRODUCER_RETRY_NEW_OBJECTS")
    validate_locator(locator_raw)
    validate_context(context_raw, locator_raw)
    require(_same(value["locator"],
            _reference("host-locator.json", locator_raw, LOCATOR_SCHEMA))
        and _same(value["context"],
            _reference("host-context.json", context_raw, CONTEXT_SCHEMA)),
        "OLD_PRODUCER_RETRY_MEMBER_BINDING")
    require(_same(value["host_record"], HOST_RECORD),
        "OLD_PRODUCER_RETRY_HOST_RECORD")
    validate_evidence(value["evidence"])
    require(_same(value["governance"], GOVERNANCE),
        "OLD_PRODUCER_RETRY_GOVERNANCE")
    require(_same(value["qualifications"], QUALIFICATIONS),
        "OLD_PRODUCER_RETRY_QUALIFICATIONS")
    expected_status = dict(field_ready=False, allow_run=False, guest_executed=False,
        normal_chain_executions=0, q2_accepted=False, q3_accepted=False,
        production_supported=False, executable=False, task_member_present=False,
        future_package_contract_complete=False, p4_contract_qualified=False,
        blockers=list(BLOCKERS))
    require(_same(value["status"], expected_status),
        "OLD_PRODUCER_RETRY_NON_EXECUTABLE_BOUNDARY")
    return copy.deepcopy(value)


def _zip_info(name):
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    return info


def build_prototype(manifest, locator_raw, context_raw):
    """Return deterministic non-executable ZIP bytes; no filesystem is touched."""
    manifest = validate_manifest(manifest, locator_raw, context_raw)
    files = {
        "MANIFEST.json": encoded(manifest),
        "NON_EXECUTABLE.txt": NOTICE,
        "host-context.json": context_raw,
        "host-locator.json": locator_raw,
    }
    sums = b"".join(
        (sha(files[name]) + "  " + name + "\n").encode("ascii") for name in sorted(files)
    )
    files["SHA256SUMS"] = sums
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", allowZip64=False) as archive:
        archive.comment = b""
        for name in PROTOTYPE_MEMBERS:
            archive.writestr(_zip_info(name), files[name])
    raw = output.getvalue()
    require(len(raw) <= ZIP_LIMIT, "OLD_PRODUCER_RETRY_PROTOTYPE_LIMIT")
    validate_prototype(raw, implementation_commit=manifest["authority"]["implementation_commit"],
        implementation_tree=manifest["authority"]["implementation_tree"])
    return raw


def validate_prototype(raw, *, implementation_commit, implementation_tree):
    """Validate a prototype.  This function has no execution or field mode."""
    require(type(raw) is bytes and 0 < len(raw) <= ZIP_LIMIT,
        "OLD_PRODUCER_RETRY_PROTOTYPE_LIMIT")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(archive.comment == b"", "OLD_PRODUCER_RETRY_ZIP_COMMENT")
        infos = archive.infolist()
        names = [info.filename for info in infos]
        require(tuple(names) == PROTOTYPE_MEMBERS and len(set(names)) == len(names)
            and "TASK.txt" not in names, "OLD_PRODUCER_RETRY_ZIP_MEMBERS")
        for info in infos:
            mode = info.external_attr >> 16
            require("/" not in info.filename and info.compress_type == zipfile.ZIP_STORED
                and not info.flag_bits & 1 and stat.S_IFMT(mode) == stat.S_IFREG
                and stat.S_IMODE(mode) == 0o600 and 0 < info.file_size <= INPUT_LIMIT,
                "OLD_PRODUCER_RETRY_ZIP_MEMBER")
        files = {name: archive.read(name) for name in names}
    expected_sums = b"".join(
        (sha(files[name]) + "  " + name + "\n").encode("ascii")
        for name in sorted(set(PROTOTYPE_MEMBERS) - {"SHA256SUMS"})
    )
    require(files["SHA256SUMS"] == expected_sums and files["NON_EXECUTABLE.txt"] == NOTICE,
        "OLD_PRODUCER_RETRY_ZIP_DIGESTS")
    locator_raw, context_raw = files["host-locator.json"], files["host-context.json"]
    manifest = validate_manifest(document(files["MANIFEST.json"]), locator_raw, context_raw,
        implementation_commit=implementation_commit, implementation_tree=implementation_tree)
    return dict(schema=PROTOTYPE_SCHEMA, status="OFFLINE_PARTIAL_PROTOTYPE_VERIFIED",
        prototype_sha256=sha(raw), prototype_bytes=len(raw),
        implementation_commit=implementation_commit, implementation_tree=implementation_tree,
        member_count=len(PROTOTYPE_MEMBERS), field_ready=False, allow_run=False,
        guest_executed=False, q2_accepted=False, q3_accepted=False,
        production_supported=False, future_package_contract_complete=False,
        p4_contract_qualified=False, blockers=list(BLOCKERS), manifest=manifest)


def require_field_readiness(_candidate=None):
    """No caller claim can close H07, dual-parent filesystem, or P4 authority."""
    raise ValueError("OLD_PRODUCER_RETRY_FIELD_READINESS_UNPROVEN")
