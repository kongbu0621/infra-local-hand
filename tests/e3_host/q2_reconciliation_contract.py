"""Exact, independent contract for the approved installation amendment.

This decoder never manufactures a startup-v1 authorization. Its execution
view carries this amendment schema, with historical pins separate from the
two prospectively adopted values. D is supplied by the caller, never self-hashed.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath as P
import re

SCHEMA = "local-hand-q2-installation-reconciliation/v1"
SCOPE = "LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1"
RULE = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
BASELINE = "c65ff4e25ea6373aabf8db25d304ee7614b96eb5"
CLOSURE = "1491765c64c60a63d6bddf10a049308e404885ca"
OWNER_DECISION = "LH-Q2-INSTALLATION-RECONCILIATION-CLOSURE-20260927-01"
INPUT_LIMIT = 8 * 1024**2
PARSED_TOTAL_LIMIT = 16 * 1024**2
RESERVATION_LIMIT = 1024**2
ENTRY_LIMIT = 32768
REFERENCE_LIMIT = 128
INTEGER_LIMIT = 2**63 - 1
ARCHIVE_SHA256 = "869a859fcbe7a952d11e22db6f6534c9b9a3025cec27471fe3e2a054a6a96018"
EVIDENCE = {
    "guest_manifest": ("82c8c13e250ac0be0957b766e84827514dd50cc5cc53d461c126d6dd0523f735", 3419814),
    "metadata_note": ("5a99256c38bb28b9188114f47763f7cc5d54b4b90f52fc01f2c7ad44cd68a1e6", 3529),
    "forward_baseline": ("9b5b5ec8dd1516cb8807bf26f657c652079843a3669783db215a4f9c5dd5852e", 239944),
    "history": ("874df85143b4314467273a526223ebbde10fbb59b47caa56bcdfe9f24c3d59ee", 1381288),
}
CURRENT_RAW = {
    "second-bootstrap-intent": ("58992ee2ff0d66fec5e10c7e138e8de4529089ca35d76f71200db1a05ac160b6", 556),
    "second-bootstrap-attestation": ("cfc6c07265b4edc6d0b26e67a6ca9cfc19c652b4d011a2386b9bd95e945a34cb", 7766),
}
SOURCE_CLASSES = {"HISTORICAL_PIN", "HISTORICAL_TREE_MEMBER", "CURRENT_OWNER_SUPPLIED_RAW"}
EXECUTION_FIELDS = ("attempt_id", "original_plan_path", "original_plan_sha256", "old_files",
    "predecessors", "reservations", "source", "candidate", "directories", "settings",
    "retained_inputs", "service")
REQUIRED_SOURCE_FILES = frozenset({
    "q2_reconciliation_contract.py", "q2_reconciliation_sources.py", "q2_reconciliation_io.py",
    "q2_reconciliation_records.py", "q2_reconciliation_billing.py", "q2_reconciliation_backend.py",
    "q2_reconciliation_driver.py", "q2_reconciliation_bootstrap.py", "q2_reconciliation_delivery.py",
    "q2_reconciliation_entry.py", "q2_reconciliation_collect.py",
})


def helper(name):
    spec = importlib.util.spec_from_file_location("_reconciliation_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = helper("q2_startup_retry_contract")
c = old.c
require = c.require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def keys(value, names):
    require(type(value) is dict and set(value) == set(names), "RECONCILIATION_FIELDS")


def number(value, low=0, high=INTEGER_LIMIT):
    require(type(value) is int and low <= value <= high, "RECONCILIATION_INTEGER")
    return value


def token(value, pattern, *, maximum=128):
    require(type(value) is str and len(value.encode("utf-8")) <= maximum
        and re.fullmatch(pattern, value) is not None, "RECONCILIATION_TOKEN")
    return value


def digest(value):
    return token(value, r"[0-9a-f]{64}")


def commit(value):
    return token(value, r"[0-9a-f]{40}")


def path(value):
    token(value, r"/[A-Za-z0-9_@./-]+", maximum=4096)
    require(str(P(value)) == value and not value.startswith("//")
        and value != "/" and ".." not in P(value).parts, "RECONCILIATION_PATH")
    return value


def document(raw, *, limit=INPUT_LIMIT):
    require(type(raw) is bytes and len(raw) <= limit, "RECONCILIATION_INPUT_LIMIT")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "RECONCILIATION_DUPLICATE_KEY")
            result[key] = value
        return result
    def reject(_):
        raise ValueError("RECONCILIATION_NUMBER")
    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_float=reject, parse_constant=reject)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError("RECONCILIATION_JSON") from error
    pending = [(value, 0)]; count = 0
    while pending:
        item, depth = pending.pop(); count += 1
        # Per-entry manifests contain many fixed metadata scalars. The
        # entry bound is separately checked at every collection boundary.
        require(depth <= 32 and count <= ENTRY_LIMIT * 64, "RECONCILIATION_COMPLEXITY")
        if type(item) is dict:
            require(len(item) <= ENTRY_LIMIT, "RECONCILIATION_ENTRIES")
            require(all(type(k) is str and len(k.encode()) <= 4096 for k in item), "RECONCILIATION_KEY")
            pending.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            require(len(item) <= ENTRY_LIMIT, "RECONCILIATION_ENTRIES")
            pending.extend((v, depth + 1) for v in item)
        elif type(item) is int:
            number(item)
        elif type(item) is str:
            require(len(item.encode()) <= limit, "RECONCILIATION_STRING")
        else:
            require(item is None or type(item) is bool, "RECONCILIATION_VALUE")
    return value


def encoded(value, *, limit=INPUT_LIMIT):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    except (ValueError, TypeError, RecursionError) as error:
        raise ValueError("RECONCILIATION_JSON") from error
    require(len(raw) <= limit, "RECONCILIATION_INPUT_LIMIT")
    return raw


def reference(value, *, location=False, limit=INPUT_LIMIT):
    keys(value, ("path", "sha256", "bytes") if location else ("sha256", "bytes"))
    if location: path(value["path"])
    digest(value["sha256"]); number(value["bytes"], 0, limit)


def _sources(rows):
    require(type(rows) is list and 10 <= len(rows) <= REFERENCE_LIMIT, "RECONCILIATION_SOURCES")
    seen_ids, seen_paths, current = set(), set(), set()
    for row in rows:
        keys(row, ("id", "path", "sha256", "bytes", "source_class", "proof_id"))
        token(row["id"], r"[a-z][a-z0-9._-]{0,127}")
        path(row["path"]); digest(row["sha256"]); number(row["bytes"], 0, RESERVATION_LIMIT)
        require(row["id"] not in seen_ids and row["path"] not in seen_paths, "RECONCILIATION_SOURCE_ALIAS")
        seen_ids.add(row["id"]); seen_paths.add(row["path"])
        require(row["source_class"] in SOURCE_CLASSES, "RECONCILIATION_SOURCE_CLASS")
        if row["source_class"] == "CURRENT_OWNER_SUPPLIED_RAW":
            require(row["id"] in CURRENT_RAW and (row["sha256"], row["bytes"]) == CURRENT_RAW[row["id"]]
                and row["proof_id"] == "owner-adoption", "RECONCILIATION_CURRENT_ADOPTION")
            current.add(row["id"])
        else:
            require(row["id"] not in CURRENT_RAW and row["sha256"] not in
                {value[0] for value in CURRENT_RAW.values()}, "RECONCILIATION_FALSE_HISTORY")
            token(row["proof_id"], r"[a-z][a-z0-9._-]{0,127}")
    require(current == set(CURRENT_RAW), "RECONCILIATION_CURRENT_SET")


def _reservations(execution, sources):
    rows = execution["reservations"]
    require(type(rows) is list and len(rows) == 10, "RECONCILIATION_RESERVATIONS")
    by_path = {row["path"]: row for row in sources}
    for row in rows:
        keys(row, ("kind", "path", "category", "covered_paths"))
        require(row["kind"] in old.RESERVATION_KINDS, "RECONCILIATION_RESERVATION_KIND")
        require(row["category"] == old.RESERVATION_KINDS[row["kind"]][1], "RECONCILIATION_RESERVATION_CATEGORY")
        path(row["path"]); require(row["path"] in by_path, "RECONCILIATION_RESERVATION_SOURCE")
        coverage = row["covered_paths"]
        expected = 2 if row["kind"] in ("OWNER_COMMITMENT", "BOOTSTRAP_COMMITMENT") else 1 if row["kind"] == "RECOVERY_STAGE" else 0
        require(type(coverage) is list and len(coverage) == expected, "RECONCILIATION_RESERVATION_COVERAGE")
        for name in coverage: path(name)
        require(all(not c.overlap(a, b) for i, a in enumerate(coverage) for b in coverage[i + 1:]), "RECONCILIATION_PATH_ALIAS")
    require(len({row["path"] for row in rows}) == 10 and all(sum(row["kind"] == kind for row in rows) == count
        for kind, (count, _) in old.RESERVATION_KINDS.items()), "RECONCILIATION_RESERVATION_COUNT")


def _execution(value, sources, implementation):
    """Port strict v1 structural checks without its all-inputs-historical claim."""
    keys(value, EXECUTION_FIELDS)
    token(value["attempt_id"], r"[a-z][a-z0-9]{7,31}")
    token(value["service"], r"lhq[a-z0-9-]{1,100}\.service")
    path(value["original_plan_path"]); digest(value["original_plan_sha256"])
    pins = value["old_files"]
    require(type(pins) is dict and 24 <= len(pins) <= REFERENCE_LIMIT, "RECONCILIATION_HISTORY_PINS")
    source_paths = {row["path"]: row for row in sources}
    for name, pin in pins.items():
        path(name); digest(pin)
        require(name in source_paths and source_paths[name]["sha256"] == pin
            and source_paths[name]["source_class"] != "CURRENT_OWNER_SUPPLIED_RAW", "RECONCILIATION_FALSE_HISTORY")
    require(all(row["path"] not in pins for row in sources if row["source_class"] == "CURRENT_OWNER_SUPPLIED_RAW"),
        "RECONCILIATION_FALSE_HISTORY")
    old._predecessors(value)
    _reservations(value, sources)
    require(set(source_paths) == set(pins) | {row["path"] for row in value["reservations"]},
        "RECONCILIATION_SOURCE_COVERAGE")
    source = value["source"]; keys(source, ("commit", "tree", "files"))
    require(source["commit"] == implementation, "RECONCILIATION_IMPLEMENTATION")
    commit(source["tree"])
    files = source["files"]
    require(type(files) is dict and len(old.REQUIRED_SOURCE_FILES | REQUIRED_SOURCE_FILES) <= len(files) <= 64,
        "RECONCILIATION_SOURCE_FILES")
    for name, pin in files.items():
        path(name); digest(pin); token(P(name).name, r"q2_[a-z0-9_]+\.py")
    require(len({str(P(name).parent) for name in files}) == 1 and
        old.REQUIRED_SOURCE_FILES | REQUIRED_SOURCE_FILES <= {P(name).name for name in files}, "RECONCILIATION_SOURCE_CLOSURE")
    candidate = value["candidate"]; keys(candidate, ("source", "commit", "tree", "wheel", "wheel_sha256", "destination"))
    for key in ("source", "wheel", "destination"): path(candidate[key])
    require(tuple(candidate[key] for key in ("commit", "tree", "wheel_sha256")) ==
        (old.CANDIDATE_COMMIT, old.CANDIDATE_TREE, old.CANDIDATE_WHEEL_SHA256), "RECONCILIATION_FIXED_CANDIDATE")
    directories = value["directories"]; keys(directories, c.DIRECTORY_ROLES)
    for role, item in directories.items(): old.legacy._directory(role, item)
    outputs = [item["path"] for item in directories.values()] + [candidate["destination"]]
    require(all(not c.overlap(a, b) for i, a in enumerate(outputs) for b in outputs[i + 1:]), "RECONCILIATION_NEW_PATH_ALIAS")
    inputs = [candidate["source"], candidate["wheel"], *files]
    require(not c.overlap(candidate["source"], candidate["wheel"])
        and all(not c.overlap(name, candidate[k]) for name in files for k in ("source", "wheel"))
        and all(not c.overlap(name, output) for name in inputs for output in outputs), "RECONCILIATION_INPUT_OUTPUT_ALIAS")
    retained = value["retained_inputs"]
    require(type(retained) is list and 8 <= len(retained) <= REFERENCE_LIMIT, "RECONCILIATION_RETAINED_INPUTS")
    for row in retained:
        keys(row, ("path", "category")); path(row["path"])
        require(row["category"] in old.CATEGORIES, "RECONCILIATION_RETAINED_CATEGORY")
    require(all(not c.overlap(a["path"], b["path"]) for i, a in enumerate(retained) for b in retained[i + 1:]),
        "RECONCILIATION_RETAINED_ALIAS")
    fresh = [directories[k]["path"] for k in c.DIRECTORY_ROLES if k not in old.REUSED_DIRECTORIES] + [candidate["destination"]]
    require(all(not c.overlap(new, before) for new in fresh for before in [*source_paths, *(x["path"] for x in retained)]),
        "RECONCILIATION_OLD_PATH_ALIAS")
    reconciliation_directory = directories["reservation"]["path"] + ".reconciliation"
    path(reconciliation_directory)
    require(all(not c.overlap(reconciliation_directory, name) for name in
        [*source_paths, *outputs, *inputs, *(x["path"] for x in retained)]), "RECONCILIATION_RECORD_PATH_ALIAS")
    old.helper("q2_prepare_driver").validate_settings(value["settings"])
    require(value["settings"]["identity"]["generation"] == 1, "RECONCILIATION_NEW_GENERATION")
    cap = value["settings"]["capacity_management"]
    require(cap["cpu_ns"] <= 400 * 10**9 and cap["memory_bytes"] <= 1536 * 1024**2 and cap["pids"] <= 1024,
        "RECONCILIATION_RUNTIME_CAPACITY")


def decode(raw, expected_sha256, *, implementation_commit):
    digest(expected_sha256); commit(implementation_commit)
    require(type(raw) is bytes and sha(raw) == expected_sha256, "RECONCILIATION_MANIFEST_DIGEST")
    value = document(raw)
    keys(value, ("schema", "scope", "rule", "baseline", "closure", "owner_decision", "implementation_commit",
        "operation_id", "startup_authority", "original_plan", "previous_plan", "execution", "sources", "evidence"))
    require(tuple(value[k] for k in ("schema", "scope", "rule", "baseline", "closure", "owner_decision")) ==
        (SCHEMA, SCOPE, RULE, BASELINE, CLOSURE, OWNER_DECISION), "RECONCILIATION_AUTHORITY")
    require(value["implementation_commit"] == implementation_commit and implementation_commit not in
        (RULE, BASELINE, CLOSURE, old.BASELINE, old.CLOSURE, old.CANDIDATE_COMMIT), "RECONCILIATION_IMPLEMENTATION")
    token(value["operation_id"], r"[a-z][a-z0-9._-]{7,127}")
    keys(value["startup_authority"], ("baseline", "closure", "owner_decision"))
    require(value["startup_authority"] == dict(baseline=old.BASELINE, closure=old.CLOSURE, owner_decision=old.OWNER_DECISION),
        "RECONCILIATION_STARTUP_AUTHORITY")
    for key in ("original_plan", "previous_plan"): reference(value[key], location=True, limit=RESERVATION_LIMIT)
    keys(value["evidence"], EVIDENCE)
    for role, expected in EVIDENCE.items():
        ref = value["evidence"][role]; reference(ref)
        require((ref["sha256"], ref["bytes"]) == expected, "RECONCILIATION_EVIDENCE_PIN")
    _sources(value["sources"])
    _execution(value["execution"], value["sources"], implementation_commit)
    require(len(value["sources"]) + len(value["evidence"]) + 2 <= REFERENCE_LIMIT, "RECONCILIATION_REFERENCE_LIMIT")
    require(value["original_plan"]["path"] == value["execution"]["original_plan_path"]
        and value["original_plan"]["sha256"] == value["execution"]["original_plan_sha256"]
        and value["previous_plan"]["path"] == value["execution"]["predecessors"][1]["plan_path"]
        and value["previous_plan"]["sha256"] == value["execution"]["predecessors"][1]["plan_sha256"],
        "RECONCILIATION_PLAN_REFERENCES")
    return value


def bind(manifest, original, previous_retry):
    """Bind already independently decoded historical schemas to a new view."""
    retry = copy.deepcopy(manifest["execution"])
    original = c.decode(c.encoded(original), retry["original_plan_sha256"])
    previous = old.legacy.decode(c.encoded(previous_retry), retry["predecessors"][1]["plan_sha256"])
    historical = old.legacy.bind(original, previous)
    require((previous["source"]["commit"], previous["source"]["tree"]) ==
        (old.PREVIOUS_SOURCE_COMMIT, old.PREVIOUS_SOURCE_TREE), "RECONCILIATION_PREVIOUS_SOURCE")
    require(retry["source"]["commit"] != previous["source"]["commit"]
        and retry["source"]["tree"] != previous["source"]["tree"], "RECONCILIATION_ORCHESTRATION_REUSE")
    require(previous["original_plan_path"] == retry["original_plan_path"]
        and previous["original_plan_sha256"] == retry["original_plan_sha256"]
        and all(retry["old_files"].get(name) == pin for name, pin in previous["old_files"].items()),
        "RECONCILIATION_HISTORY_CHAIN")
    first, second = retry["predecessors"]
    require(first["prepared_path"] == previous["old_prepared"] and first["handoff_path"] == previous["old_handoff"]
        and first["owner_output"] == previous["old_owner_output"] and first["ledger"] == previous["old_ledger"],
        "RECONCILIATION_FIRST_PREDECESSOR")
    require([x["unit"] for x in first["failed_units"]] == ["lhq" + original["preparation_id"] + ".service",
        "lhq" + P(first["prepared_path"]).parent.name + ".service"], "RECONCILIATION_ORIGINAL_UNIT")
    for item, plan in zip((first, second), (original, historical)):
        require(item["ledger"]["path"] == str(P(plan["directories"]["state"]["path"]) / "jobs.sqlite")
            and item["ledger"]["uid"] == original["account"]["uid"]
            and item["ledger"]["ledger_id"] == plan["settings"]["identity"]["ledger_id"]
            and item["policy_path"] == str(P(plan["directories"]["authority"]["path"]) / "policy.json")
            and item["owner_output"] == str(P(plan["directories"]["capture"]["path"]) / "owner_output"),
            "RECONCILIATION_PREDECESSOR_LOCATION")
    require(second["prepared_path"] == str(P(previous["directories"]["reservation"]["path"]) / "prepared.json")
        and second["handoff_path"] == str(P(previous["directories"]["reservation"]["path"]) / "handoff.json")
        and [x["unit"] for x in second["failed_units"]] == [previous["service"], previous["settings"]["controllers"]["supervisor"]["unit"]],
        "RECONCILIATION_SECOND_PREDECESSOR")
    old._bind_paths(original, historical, previous, retry)
    old._bind_reservations(original, historical, retry)
    old._bind_identities(original, historical, previous, retry)
    identities = {str(value) for candidate in (original, historical)
        for value in candidate["settings"]["identity"].values()}
    identities.update(str(value) for value in retry["settings"]["identity"].values())
    identities.update((original["preparation_id"], previous["attempt_id"], retry["attempt_id"]))
    require(manifest["operation_id"] not in identities, "RECONCILIATION_OPERATION_ID_REUSE")
    retry.update(schema=SCHEMA, scope=SCOPE, rule=RULE, baseline=BASELINE, closure=CLOSURE, owner_decision=OWNER_DECISION,
        implementation_commit=manifest["implementation_commit"], startup_authority=copy.deepcopy(manifest["startup_authority"]))
    plan = copy.deepcopy(original)
    plan.update(schema=SCHEMA, purpose="ISOLATED_Q2_INSTALLATION_RECONCILIATION", scope=SCOPE, baseline=BASELINE,
        preparation_id=retry["attempt_id"], candidate=retry["candidate"], directories=retry["directories"], settings=retry["settings"])
    plan["budgets"]["preparation_seconds"] = old.PREPARATION_SECONDS
    old.helper("q2_prepare_driver").validate_plan(plan)
    return retry, plan, historical
