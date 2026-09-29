"""Review bounded byte references and pending cost claims, without admission.

No source is adopted and no observation schema is authenticated here. A JSON
container may contain several historical observations or just an unfinished
before-stat. Even a successful reference sum is neither actual inventory nor a
current lower bound. This module uses only stdlib and never follows input paths.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
import re


SCHEMA = "local-hand-q2-cost-source-claims/v1"
REPORT_SCHEMA = "local-hand-q2-cost-source-review/v1"
MANIFEST_LIMIT = 256 * 1024
INPUT_LIMIT = 16 * 1024**2
SOURCE_LIMIT = 8 * 1024**2
OUTPUT_LIMIT = 2 * 1024**2
MAX_INTEGER = 2**63 - 1
MAX_DIAGNOSTICS = 2048
MAX_REFERENCE_BYTES = 256 * 1024
MAX_REFERENCED_BYTES = 4 * 1024**2
MAX_RELATION_MEMBERSHIPS = 2048
FALSE_FIELDS = ("source_adoption_proven", "observation_completion_proven",
    "baseline_parent_cost_proven", "full_bill_proven", "filesystem_proven",
    "field_ready", "q2_accepted", "allow_consume", "allow_run")
CATEGORIES = {"installation", "state", "journal", "capture", "unknown"}
ROLES = {"ordinary", "parent_baseline", "marker_subtree", "unknown"}
KINDS = {"historical", "marker", "capture", "audit", "unknown"}


def require(condition, code):
    if not condition:
        raise ValueError("COST_SOURCE_" + code)


def encoded(value):
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"),
            allow_nan=False, ensure_ascii=True) + "\n").encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise ValueError("COST_SOURCE_JSON") from error


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _keys(value, names):
    require(type(value) is dict and set(value) == set(names), "FIELDS")


def _integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= MAX_INTEGER, "INTEGER")
    return value


def _text(value, limit=4096):
    require(type(value) is str and "\0" not in value, "TEXT")
    try:
        require(0 < len(value.encode("utf-8")) <= limit, "TEXT")
    except UnicodeError as error:
        raise ValueError("COST_SOURCE_TEXT") from error
    return value


def _id(value):
    _text(value, 128)
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) is not None, "ID")
    return value


def _rows(value, maximum, minimum=0):
    require(type(value) is list and minimum <= len(value) <= maximum, "ROWS")
    return value


def _json(raw, limit):
    require(type(raw) is bytes and 0 < len(raw) <= limit, "INPUT_LIMIT")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_KEY")
            result[key] = value
        return result

    def forbidden(_value):
        raise ValueError("COST_SOURCE_JSON_NUMBER")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
            parse_float=forbidden, parse_constant=forbidden)
    except (ValueError, UnicodeError, RecursionError) as error:
        if str(error).startswith("COST_SOURCE_"):
            raise
        raise ValueError("COST_SOURCE_JSON") from error
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        require(depth <= 64 and count <= 100000, "JSON_COMPLEXITY")
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
            pending.extend((key, depth + 1) for key in item)
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            try:
                item.encode("utf-8")
            except UnicodeError as error:
                raise ValueError("COST_SOURCE_TEXT") from error
        elif type(item) is int:
            require(-MAX_INTEGER <= item <= MAX_INTEGER, "INTEGER")
    return value


def _pointer(document, pointer):
    require(type(pointer) is str, "POINTER")
    try:
        require(len(pointer.encode("utf-8")) <= 4096 and "\0" not in pointer, "POINTER")
    except UnicodeError as error:
        raise ValueError("COST_SOURCE_POINTER") from error
    if pointer == "":
        return document
    require(pointer.startswith("/"), "POINTER")
    parts = pointer[1:].split("/")
    require(len(parts) <= 64, "POINTER")
    value = document
    for part in parts:
        require(re.search(r"~(?![01])", part) is None, "POINTER")
        key = part.replace("~1", "/").replace("~0", "~")
        if type(value) is dict:
            require(key in value, "POINTER_MISSING")
            value = value[key]
        elif type(value) is list:
            require(re.fullmatch(r"0|[1-9][0-9]*", key) is not None and len(key) <= 10,
                "POINTER_INDEX")
            index = int(key)
            require(index < len(value), "POINTER_MISSING")
            value = value[index]
        else:
            raise ValueError("COST_SOURCE_POINTER_MISSING")
    return value


def _identity(row):
    metadata = row["metadata"]
    if metadata is None or any(row[key] is None for key in ("machine", "boot")):
        return None
    if any(metadata[key] is None for key in ("device", "inode")):
        return None
    return row["machine"], row["boot"], metadata["device"], metadata["inode"]


def review_cost_sources(manifest_raw, sources):
    """Check references and claim conflicts; never calculate release or a bill.

    All pins are caller declarations under review. No source-group establishes
    an observation epoch, and separate pointers do not establish that identity
    and allocation were obtained together. Unknown quantities remain None.
    """
    manifest = _json(manifest_raw, MANIFEST_LIMIT)
    _keys(manifest, ("schema", "sources", "objects", "obligations", "relations"))
    require(manifest["schema"] == SCHEMA, "SCHEMA")
    require(type(sources) is dict and 1 <= len(sources) <= 32, "SOURCES")
    require(all(type(key) is str and type(value) is bytes for key, value in sources.items()), "SOURCES")
    declarations = _rows(manifest["sources"], 32, 1)
    pins = {}
    total = 0
    for row in declarations:
        _keys(row, ("id", "sha256", "bytes"))
        identity = _id(row["id"])
        require(identity not in pins, "DUPLICATE_SOURCE")
        require(type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "DIGEST")
        _integer(row["bytes"], 1)
        require(row["bytes"] <= SOURCE_LIMIT, "INPUT_LIMIT")
        pins[identity] = dict(row)
        total += row["bytes"]
    require(total <= INPUT_LIMIT and set(sources) == set(pins), "SOURCES")
    # Check every original before decoding even the first original.
    for identity, pin in pins.items():
        require(len(sources[identity]) == pin["bytes"]
            and _sha(sources[identity]) == pin["sha256"], "SOURCE_PIN")
    documents = {identity: _json(sources[identity], SOURCE_LIMIT) for identity in pins}
    references = {}
    referenced_size = 0

    def reference(source, pointer):
        nonlocal referenced_size
        require(type(source) is str and source in pins, "SOURCE_REFERENCE")
        if pointer is None:
            return None, None
        # Validation occurs before using pointer as a mapping key.
        value = _pointer(documents[source], pointer)
        key = source, pointer
        if key not in references:
            raw = encoded(value)
            require(len(raw) <= MAX_REFERENCE_BYTES, "REFERENCE_LIMIT")
            referenced_size += len(raw)
            require(referenced_size <= MAX_REFERENCED_BYTES, "REFERENCE_LIMIT")
            references[key] = dict(source_sha256=pins[source]["sha256"],
                pointer=pointer, value_sha256=_sha(raw))
        return value, dict(references[key])

    def evidence(values):
        result = []
        for value in _rows(values, 8):
            _keys(value, ("source", "pointer"))
            require(value["pointer"] is not None, "POINTER")
            _, proof = reference(value["source"], value["pointer"])
            result.append(proof)
        return result

    objects = []
    by_id = {}
    for row in _rows(manifest["objects"], 512):
        _keys(row, ("id", "source", "metadata_pointer", "machine_pointer", "boot_pointer",
            "path_pointer", "phase_pointer", "role_claim", "category_claim", "evidence"))
        identity = _id(row["id"])
        require(identity not in by_id, "DUPLICATE_OBJECT")
        require(type(row["role_claim"]) is str and row["role_claim"] in ROLES
            and type(row["category_claim"]) is str and row["category_claim"] in CATEGORIES, "CLAIM")
        selected, refs = {}, {}
        for name in ("metadata", "machine", "boot", "path", "phase"):
            selected[name], refs[name] = reference(row["source"], row[name + "_pointer"])
        metadata = selected["metadata"]
        amount = None
        if metadata is not None:
            require(type(metadata) is dict and {"device", "inode", "blocks"} <= set(metadata), "METADATA")
            metadata = {key: metadata[key] for key in ("device", "inode", "blocks")}
            for key, value in metadata.items():
                if value is not None:
                    _integer(value, 0 if key == "blocks" else 1)
            if metadata["blocks"] is not None:
                require(metadata["blocks"] <= MAX_INTEGER // 512, "OVERFLOW")
                amount = metadata["blocks"] * 512
        for name in ("machine", "boot", "path"):
            if selected[name] is not None:
                _text(selected[name])
        path = selected["path"]
        if path is not None:
            require(path.startswith("/") and not path.startswith("//") and str(PurePosixPath(path)) == path
                and ".." not in PurePosixPath(path).parts, "PATH")
        result = dict(id=identity, source_sha256=pins[row["source"]]["sha256"],
            metadata=metadata, machine=selected["machine"], boot=selected["boot"], path=path,
            referenced_allocated_bytes=amount, role_claim=row["role_claim"],
            category_claim=row["category_claim"], refs=refs, evidence=evidence(row["evidence"]),
            status="REFERENCED_NOT_OBSERVATION_VERIFIED", observation_completion_proven=False,
            identity_and_amount_same_observation_proven=False, category_proven=False)
        objects.append(result)
        by_id[identity] = result
    obligations = []
    obligations_by_id = {}
    for row in _rows(manifest["obligations"], 128):
        _keys(row, ("id", "source", "commitment_pointer", "kind_claim", "category_claim", "evidence"))
        identity = _id(row["id"])
        require(identity not in obligations_by_id, "DUPLICATE_OBLIGATION")
        require(type(row["kind_claim"]) is str and row["kind_claim"] in KINDS
            and type(row["category_claim"]) is str and row["category_claim"] in CATEGORIES, "CLAIM")
        amount, proof = reference(row["source"], row["commitment_pointer"])
        if amount is not None:
            _keys(amount, ("bytes", "inodes"))
            amount = {key: _integer(amount[key]) for key in amount}
            if row["kind_claim"] == "marker":
                require(amount == dict(bytes=65536, inodes=4), "MARKER_COMMITMENT")
        result = dict(id=identity, source_sha256=pins[row["source"]]["sha256"],
            referenced_commitment=amount, commitment_ref=proof, kind_claim=row["kind_claim"],
            category_claim=row["category_claim"], evidence=evidence(row["evidence"]),
            obligation_adoption_proven=False, release_applied=False, unspent=None)
        obligations.append(result)
        obligations_by_id[identity] = result
    diagnostics = []

    def diagnostic(code, **values):
        require(len(diagnostics) < MAX_DIAGNOSTICS, "DIAGNOSTIC_LIMIT")
        diagnostics.append(dict(code=code, **values))

    commitment_references = {}
    for obligation in obligations:
        proof = obligation["commitment_ref"]
        if proof is not None:
            key = proof["source_sha256"], proof["pointer"]
            if key in commitment_references:
                diagnostic("COMMITMENT_REFERENCE_REUSED",
                    obligation_ids=[commitment_references[key], obligation["id"]])
            else:
                commitment_references[key] = obligation["id"]
    conflicted_groups = set()
    for index, left in enumerate(objects):
        li = _identity(left)
        for right in objects[index + 1:]:
            ri = _identity(right)
            same_source = left["source_sha256"] == right["source_sha256"]
            ids = [left["id"], right["id"]]
            if li is not None and li == ri:
                diagnostic("PHYSICAL_ALIAS" if same_source else "CROSS_RECEIPT_IDENTITY", object_ids=ids)
                if same_source:
                    conflicted_groups.add(left["source_sha256"])
            if same_source and li is not None and ri is not None and li[:2] == ri[:2]:
                if left["path"] is not None and left["path"] == right["path"] and li != ri:
                    diagnostic("PATH_IDENTITY_CONFLICT", object_ids=ids)
                    conflicted_groups.add(left["source_sha256"])
                lp, rp = left["path"], right["path"]
                if lp and rp and lp != rp and (rp.startswith(lp.rstrip("/") + "/")
                        or lp.startswith(rp.rstrip("/") + "/")):
                    diagnostic("PATH_ANCESTRY", object_ids=ids)
    relations, relation_ids, selected_claims = [], set(), {}
    credit_obligations = {}
    memberships = 0
    for row in _rows(manifest["relations"], 512):
        _keys(row, ("id", "kind", "object_ids", "obligation_id", "evidence"))
        identity = _id(row["id"])
        require(identity not in relation_ids, "DUPLICATE_RELATION")
        relation_ids.add(identity)
        require(type(row["kind"]) is str and row["kind"] in {"coverage", "credit"}, "RELATION_KIND")
        require(type(row["obligation_id"]) is str and row["obligation_id"] in obligations_by_id,
            "OBLIGATION_REFERENCE")
        chosen = _rows(row["object_ids"], 512, 1)
        memberships += len(chosen)
        require(memberships <= MAX_RELATION_MEMBERSHIPS, "MEMBERSHIP_LIMIT")
        require(all(type(value) is str and value in by_id for value in chosen)
            and len(set(chosen)) == len(chosen), "OBJECT_REFERENCE")
        obligation = obligations_by_id[row["obligation_id"]]
        if row["kind"] == "credit":
            if row["obligation_id"] in credit_obligations:
                diagnostic("OBLIGATION_CREDIT_REUSED", obligation_ids=[row["obligation_id"]],
                    relation_ids=[credit_obligations[row["obligation_id"]], identity])
            else:
                credit_obligations[row["obligation_id"]] = identity
        for object_id in chosen:
            obj = by_id[object_id]
            oi = _identity(obj)
            if obj["role_claim"] == "parent_baseline":
                diagnostic("PARENT_BASELINE_UNPROVEN", object_ids=[object_id], relation_ids=[identity])
            if (obj["category_claim"] != "unknown" and obligation["category_claim"] != "unknown"
                    and obj["category_claim"] != obligation["category_claim"]):
                diagnostic("CATEGORY_CLAIM_CONFLICT", object_ids=[object_id], relation_ids=[identity])
            claim_key = ("physical",) + oi if oi is not None else ("object", object_id)
            for previous, previous_object in selected_claims.get(claim_key, ()):
                ids = [previous["id"], identity]
                if previous["kind"] == row["kind"] == "credit":
                    diagnostic("DOUBLE_CREDIT", object_ids=[previous_object["id"], object_id], relation_ids=ids)
                    if obj["source_sha256"] != previous_object["source_sha256"]:
                        diagnostic("CROSS_RECEIPT_CREDIT", object_ids=[previous_object["id"], object_id], relation_ids=ids)
                elif previous["kind"] == row["kind"] == "coverage" and previous["obligation_id"] == row["obligation_id"]:
                    diagnostic("DUPLICATE_COVERAGE", object_ids=[previous_object["id"], object_id], relation_ids=ids)
                elif previous["kind"] == row["kind"] == "coverage":
                    diagnostic("COVERAGE_OVERLAP", object_ids=[previous_object["id"], object_id], relation_ids=ids)
            selected_claims.setdefault(claim_key, []).append((row, obj))
        relations.append(dict(id=identity, kind=row["kind"], object_ids=list(chosen),
            obligation_id=row["obligation_id"], evidence=evidence(row["evidence"]),
            coverage_proven=False, credit_applied=False, status="UNPROVEN"))
    groups = []
    for source_sha in sorted({row["source_sha256"] for row in objects}):
        selected = [row for row in objects if row["source_sha256"] == source_sha]
        reasons = []
        if source_sha in conflicted_groups:
            reasons.append("REFERENCE_IDENTITY_CONFLICT")
        if any(row["referenced_allocated_bytes"] is None or _identity(row) is None for row in selected):
            reasons.append("UNKNOWN_QUANTITY_OR_IDENTITY")
        subtotal = None
        if not reasons:
            subtotal = sum(row["referenced_allocated_bytes"] for row in selected)
            require(subtotal <= MAX_INTEGER, "OVERFLOW")
        groups.append(dict(source_sha256=source_sha, object_ids=[row["id"] for row in selected],
            referenced_endpoint_sum_bytes=subtotal, unresolved=reasons,
            observation_epoch_proven=False, subtotal_eligible_as_observation=False))
    result = dict(schema=REPORT_SCHEMA, status="CLAIMS_REVIEWED", manifest_sha256=_sha(manifest_raw),
        sources=[dict(row) for row in declarations], objects=objects, obligations=obligations,
        relations=relations, source_groups=groups, diagnostics=diagnostics,
        marker_pool_adjustment_performed=False, **{key: False for key in FALSE_FIELDS})
    require(len(encoded(result)) <= OUTPUT_LIMIT, "OUTPUT_LIMIT")
    return result
