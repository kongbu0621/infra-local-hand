"""Exact approved host-consumption authority; pure decoding, no field reads."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
from pathlib import Path, PurePosixPath
import re


def helper(name):
    spec = importlib.util.spec_from_file_location("_host_window_contract_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = helper("q2_reconciliation_contract")
require, keys, number, digest, commit, path = (prior.require, prior.keys, prior.number,
    prior.digest, prior.commit, prior.path)
encoded, document, sha = prior.encoded, prior.document, prior.sha
SCHEMA = "local-hand-q2-host-window-binding/v1"
INTENT_SCHEMA = "local-hand-q2-host-window-intent/v1"
ORDINARY_INTENT_SCHEMA = "local-hand-q2-host-window-intent/v2"
OPERATOR_SCHEMA = "local-hand-q2-host-window-operator/v1"
OPERATOR_FIELDS = ("schema", "uid", "gid", "groups")
SOURCES_SCHEMA = "local-hand-q2-host-window-sources/v1"
SCOPE = "LH-Q2-HOST-WINDOW-CONSUMPTION-v1"
RULE = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
BASELINE = "8402f0cc82d8a0ac0b9a56716bf276f41cafea37"
CLOSURE = "271c07cd16140aa5942dcf3fad468003c58b6b0e"
OWNER_DECISION = "LH-Q2-HOST-WINDOW-CONSUMPTION-CLOSURE-20260927-01"
STARTUP_AUTHORITY = dict(baseline=prior.old.BASELINE, closure=prior.old.CLOSURE,
    owner_decision=prior.old.OWNER_DECISION)
RECONCILIATION_AUTHORITY = dict(baseline=prior.BASELINE, closure=prior.CLOSURE,
    owner_decision=prior.OWNER_DECISION)
CARRIER_SHA256 = "5eef22e497e9e0a867470c6c490336dc80fadd0e506e3419847e6c37b687918b"
CARRIER_BYTES = 5426689
ATTESTATION_SHA256 = "76cc2c698dbe882ed246509746bc7088ba55df4199f550af8bad42c9f925dd65"
ATTESTATION_BYTES = 5913
DIRECTORY_NAME = "q2-startup-window-" + sha(STARTUP_AUTHORITY["closure"].encode("utf-8"))
INTENT_NAME = "host-window-intent.json"
LOGICAL_LIMIT, BYTE_LIMIT, INODE_LIMIT = 16384, 65536, 4
RESERVATION = dict(logical_bytes=LOGICAL_LIMIT, bytes=BYTE_LIMIT, inodes=INODE_LIMIT)
NS = 10**9
WINDOW_FIELDS = ("issued_ns", "deadline_ns", "boottime_issued_ns", "boottime_deadline_ns")
LOCATION_FIELDS = ("schema", "parent", "directory", "expected_boot_id", "startup_closure",
    "carrier_sha256", "carrier_bytes", "host_attestation_sha256", "host_attestation_bytes")
BINDING_FIELDS = ("schema", "scope", "rule", "baseline", "closure", "owner_decision",
    "implementation_commit", "source_tree", "source_files_sha256", "startup_authority",
    "reconciliation_authority", "attempt_id", "plan_sha256", "amendment_sha256",
    "configuration_sha256", "wrapper_sha256", "location", "run_permission")
INTENT_FIELDS = ("schema", "scope", "binding", "window", "directory_identity", "precheck",
    "precheck_sha256", "reservation", "window_consumed", "owner_issued", "run_permission")


def boot(value):
    require(type(value) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value),
        "HOST_WINDOW_BOOT")
    return value


def validate_location(value):
    keys(value, LOCATION_FIELDS)
    require(value["schema"] == SOURCES_SCHEMA and value["startup_closure"] == STARTUP_AUTHORITY["closure"]
        and (value["carrier_sha256"], value["carrier_bytes"]) == (CARRIER_SHA256, CARRIER_BYTES)
        and (value["host_attestation_sha256"], value["host_attestation_bytes"])
            == (ATTESTATION_SHA256, ATTESTATION_BYTES), "HOST_WINDOW_SOURCE_PINS")
    path(value["parent"]); path(value["directory"]); boot(value["expected_boot_id"])
    require(value["directory"] == value["parent"] + "/" + DIRECTORY_NAME, "HOST_WINDOW_LOCATION")
    return copy.deepcopy(value)


def sources(carrier_raw, host_attestation_raw):
    """Read only two exact source artifacts; never execute the original carrier."""
    require(type(carrier_raw) is bytes and len(carrier_raw) == CARRIER_BYTES
        and sha(carrier_raw) == CARRIER_SHA256, "HOST_WINDOW_CARRIER_PIN")
    require(type(host_attestation_raw) is bytes and len(host_attestation_raw) == ATTESTATION_BYTES
        and sha(host_attestation_raw) == ATTESTATION_SHA256, "HOST_WINDOW_ATTESTATION_PIN")
    constants = {}
    try:
        tree = ast.parse(carrier_raw)
    except (SyntaxError, UnicodeError, RecursionError) as error:
        raise ValueError("HOST_WINDOW_CARRIER_AST") from error
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id in ("HOST_RESULT", "HOST_OLD"):
                require(target.id not in constants and isinstance(value, ast.Constant)
                    and type(value.value) is str, "HOST_WINDOW_CARRIER_CONSTANT")
                constants[target.id] = path(value.value)
    require(set(constants) == {"HOST_RESULT", "HOST_OLD"}, "HOST_WINDOW_CARRIER_CONSTANT")
    parents = {str(PurePosixPath(value).parent) for value in constants.values()}
    require(len(parents) == 1, "HOST_WINDOW_CARRIER_PARENT")
    parent = path(parents.pop())
    attestation = document(host_attestation_raw, limit=ATTESTATION_BYTES)
    require(type(attestation) is dict and "boot_id" in attestation, "HOST_WINDOW_ATTESTATION_BOOT")
    result = dict(schema=SOURCES_SCHEMA, parent=parent, directory=parent + "/" + DIRECTORY_NAME,
        expected_boot_id=boot(attestation["boot_id"]), startup_closure=STARTUP_AUTHORITY["closure"],
        carrier_sha256=CARRIER_SHA256, carrier_bytes=CARRIER_BYTES,
        host_attestation_sha256=ATTESTATION_SHA256, host_attestation_bytes=ATTESTATION_BYTES)
    return validate_location(result)


def make_binding(*, implementation_commit, source_tree, source_files_sha256, attempt_id,
                 plan_sha256, amendment_sha256, configuration_sha256, wrapper_sha256, location):
    value = dict(schema=SCHEMA, scope=SCOPE, rule=RULE, baseline=BASELINE, closure=CLOSURE,
        owner_decision=OWNER_DECISION, implementation_commit=implementation_commit,
        source_tree=source_tree, source_files_sha256=source_files_sha256,
        startup_authority=copy.deepcopy(STARTUP_AUTHORITY),
        reconciliation_authority=copy.deepcopy(RECONCILIATION_AUTHORITY), attempt_id=attempt_id,
        plan_sha256=plan_sha256, amendment_sha256=amendment_sha256,
        configuration_sha256=configuration_sha256, wrapper_sha256=wrapper_sha256,
        location=copy.deepcopy(location), run_permission="existing_startup_once")
    return validate_binding(value, location)


def validate_binding(value, location):
    keys(value, BINDING_FIELDS)
    require(tuple(value[key] for key in ("schema", "scope", "rule", "baseline", "closure", "owner_decision"))
        == (SCHEMA, SCOPE, RULE, BASELINE, CLOSURE, OWNER_DECISION), "HOST_WINDOW_AUTHORITY")
    require(value["startup_authority"] == STARTUP_AUTHORITY and
        value["reconciliation_authority"] == RECONCILIATION_AUTHORITY, "HOST_WINDOW_OLD_AUTHORITIES")
    commit(value["implementation_commit"]); commit(value["source_tree"])
    require(value["implementation_commit"] not in (RULE, BASELINE, CLOSURE, prior.BASELINE,
        prior.CLOSURE, prior.old.BASELINE, prior.old.CLOSURE, prior.old.CANDIDATE_COMMIT),
        "HOST_WINDOW_IMPLEMENTATION")
    for key in ("source_files_sha256", "plan_sha256", "amendment_sha256", "configuration_sha256", "wrapper_sha256"):
        digest(value[key])
    prior.token(value["attempt_id"], r"[A-Za-z0-9][A-Za-z0-9_.-]{7,127}")
    require(value["location"] == validate_location(location) and
        value["run_permission"] == "existing_startup_once", "HOST_WINDOW_BINDING")
    return copy.deepcopy(value)


def validate_window(value):
    keys(value, WINDOW_FIELDS)
    for key in WINDOW_FIELDS:
        number(value[key], 1)
    require(value["deadline_ns"] == value["issued_ns"] + 300 * NS and
        value["boottime_deadline_ns"] == value["boottime_issued_ns"] + 300 * NS,
        "HOST_WINDOW_DEADLINE")
    return copy.deepcopy(value)


def validate_operator(value):
    """Validate a retained ordinary issuer, not the current reader or FS identity.

    These fields describe real/effective/saved credentials and supplementary
    groups only. They say nothing about fsuid/fsgid, capabilities or userns.
    Full sorted group lists are retained, including any repeated entries.
    """
    keys(value, OPERATOR_FIELDS)
    require(value["schema"] == OPERATOR_SCHEMA, "HOST_WINDOW_OPERATOR_SCHEMA")
    for kind in ("uid", "gid"):
        values = value[kind]
        require(type(values) is list and len(values) == 3, "HOST_WINDOW_OPERATOR_CREDENTIALS")
        for item in values:
            number(item, 1, 2**32 - 2)
        require(values[0] == values[1] == values[2], "HOST_WINDOW_OPERATOR_CREDENTIALS")
    groups = value["groups"]
    require(type(groups) is list and len(groups) <= 65536, "HOST_WINDOW_OPERATOR_GROUPS")
    for item in groups:
        number(item, 0, 2**32 - 2)
    require(groups == sorted(groups), "HOST_WINDOW_OPERATOR_GROUPS")
    return copy.deepcopy(value)


def _verify_intent(raw, expected_binding, location, *, ordinary):
    value = document(raw, limit=LOGICAL_LIMIT)
    keys(value, INTENT_FIELDS + (("operator",) if ordinary else ()))
    require(value["schema"] == (ORDINARY_INTENT_SCHEMA if ordinary else INTENT_SCHEMA) and value["scope"] == SCOPE and
        value["binding"] == validate_binding(expected_binding, location), "HOST_WINDOW_INTENT_BINDING")
    operator = validate_operator(value["operator"]) if ordinary else None
    validate_window(value["window"])
    identity = value["directory_identity"]
    keys(identity, ("device", "inode", "uid", "gid", "mode"))
    for key in ("device", "inode"):
        number(identity[key], 1)
    for key in ("uid", "gid"):
        number(identity[key], 0, 2**32 - 2)
    require(identity["mode"] == 0o700 and type(identity["mode"]) is int, "HOST_WINDOW_DIRECTORY_MODE")
    require(value["reservation"] == RESERVATION and all(type(x) is int for x in value["reservation"].values()),
        "HOST_WINDOW_RESERVATION")
    require(value["window_consumed"] is True and value["owner_issued"] is False and
        value["run_permission"] == "existing_startup_once", "HOST_WINDOW_INTENT_STATE")
    require(type(value["precheck"]) is dict and sha(encoded(value["precheck"])) == digest(value["precheck_sha256"]),
        "HOST_WINDOW_PRECHECK_DIGEST")
    # The record module supplies the strict observation schema without creating
    # a second authority decoder or permitting arbitrary fields in this object.
    record = helper("q2_host_window_record")
    validator = record.validate_precheck_ordinary if ordinary else record.validate_precheck
    precheck = validator(value["precheck"], location, value["window"])
    parent = precheck["parent_metadata"]
    # v1 records can only be emitted by the root-only writer. Independent
    # integer validation (or a recomputed digest) is not a parent/child bind.
    # Ordinary-identity support must not be inferred from arbitrary uid fields.
    if ordinary:
        require(precheck["operator"] == operator and parent["uid"] == operator["uid"][1]
            and parent["gid"] == operator["gid"][1]
            and identity["uid"] == operator["uid"][1] and identity["gid"] == operator["gid"][1],
            "HOST_WINDOW_DIRECTORY_BINDING")
    else:
        require(identity["uid"] == identity["gid"] == 0, "HOST_WINDOW_DIRECTORY_BINDING")
    require(identity["device"] == parent["device"] and identity["inode"] != parent["inode"],
        "HOST_WINDOW_DIRECTORY_BINDING")
    return value


def verify_intent(raw, expected_binding, location):
    """Pure strict v1 verification; never a new fsync or replay right."""
    return _verify_intent(raw, expected_binding, location, ordinary=False)


def verify_intent_ordinary(raw, expected_binding, location):
    """Pure explicit v2 issuer binding; current-reader checks belong to record."""
    return _verify_intent(raw, expected_binding, location, ordinary=True)


def require_field_readiness(host_window):
    """The closed approval is not a substitute for still-missing field facts.

    Pure decoding, billing and consumption primitives do not establish the
    original first-probe absolute deadline or complete host future/native-audit
    source coverage. No caller boolean, quote or callback can supply those
    absent facts. Entrypoints call this before any live observation or write.
    """
    raise ValueError("HOST_WINDOW_FIELD_READINESS_UNPROVEN")
