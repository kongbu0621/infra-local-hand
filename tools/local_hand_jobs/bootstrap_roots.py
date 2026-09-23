"""Durable, one-use admission of administrator-precreated helper root slots.

This module performs no filesystem I/O. Identity and quota observations belong
to the supervised bootstrap, before any job-root write. Consumed slots are not
released, including after failure, cancellation, UNKNOWN, or a broker restart.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import PurePosixPath
import re

from .contract import JobError, MAX_SAFE_INTEGER, REF_PATTERN, canonical_bytes, strict_loads

ROOT_NAMES = frozenset(("work", "evidence", "temporary"))
_PHASES = {"job": {"preflight", "business", "evidence"},
           "reconcile": {"reconcile", "evidence"}}
_IDENTITY_KEYS = {"device", "inode", "uid"}
_GRANT_KEYS = {"version", "namespace", "record_id", "operation_id", "execution_id",
               "phase", "slot_id", "allocation_id", "roots", "paths",
               "retained_paths", "fresh", "source_roots", "grant_digest"}


def _invalid(message="Bootstrap root admission is unresolved"):
    return JobError("IO_UNCERTAIN", message)


def _digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _path(value):
    if (type(value) is not str or not value.startswith("/") or value.startswith("//")
            or value == "/" or str(PurePosixPath(value)) != value
            or ".." in PurePosixPath(value).parts
            or any(char.isspace() or ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF
                   or char in "\\%$" for char in value)):
        raise _invalid("Bootstrap root path is not canonical")
    return value


def _overlap(left, right):
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def validate_root(value, *, expected_uid=None):
    """Validate a declared binding; this does not prove the directory exists."""
    if type(value) is not dict or set(value) != {"path", *_IDENTITY_KEYS}:
        raise _invalid("Bootstrap root identity fields are incomplete")
    _path(value["path"])
    for name in _IDENTITY_KEYS:
        if type(value[name]) is not int or not (1 if name == "inode" else 0) <= value[name] <= MAX_SAFE_INTEGER:
            raise _invalid("Bootstrap root identity is malformed")
    if expected_uid is not None and value["uid"] != expected_uid:
        raise _invalid("Bootstrap root belongs to another admitted account")
    return copy.deepcopy(value)


def validate_slots(slots, *, parent_roots=None, expected_uid=None, forbidden_roots=()):
    """Validate a finite in-memory pool without probing private or mounted paths.

    Each slot has three independent, already-created root directories. A slot
    root is a strict descendant of its corresponding profile parent, never the
    parent itself. Inode aliases and lexical overlaps cannot form extra slots.
    """
    if type(slots) is not list or not 1 <= len(slots) <= 1024:
        raise _invalid("A finite precreated bootstrap slot pool is required")
    if parent_roots is not None:
        if type(parent_roots) is not dict or set(parent_roots) != ROOT_NAMES:
            raise _invalid("Bootstrap profile roots are incomplete")
        for path in parent_roots.values():
            _path(path)
    denied = [_path(path) for path in forbidden_roots]
    seen_ids, seen_inodes, seen_paths = set(), set(), []
    for slot in slots:
        if (type(slot) is not dict or set(slot) != {"slot_id", "roots"}
                or type(slot["slot_id"]) is not str or re.fullmatch(REF_PATTERN, slot["slot_id"]) is None
                or slot["slot_id"] in seen_ids or type(slot["roots"]) is not dict
                or set(slot["roots"]) != ROOT_NAMES):
            raise _invalid("Bootstrap slot identity is ambiguous")
        seen_ids.add(slot["slot_id"])
        for name, root in slot["roots"].items():
            root = validate_root(root, expected_uid=expected_uid)
            path, inode = root["path"], (root["device"], root["inode"])
            if (parent_roots is not None and not path.startswith(parent_roots[name] + "/")):
                raise _invalid("Bootstrap slot would grant its profile parent or escape it")
            if (inode in seen_inodes or any(_overlap(path, old) for old in seen_paths)
                    or any(_overlap(path, old) for old in denied)):
                raise _invalid("Bootstrap slots alias, overlap, or enter a forbidden root")
            seen_inodes.add(inode)
            seen_paths.append(path)
    return copy.deepcopy(slots)


def _allocation_id(namespace, record_id, slot_id, roots, paths):
    return _digest({"namespace": namespace, "record_id": record_id, "slot_id": slot_id,
                    "roots": roots, "paths": {path: paths[path] for path in roots.values()}})


def validate_grant(grant, *, execution_id=None, phase=None, operation_id=None,
                   namespace=None, record_id=None):
    if (type(grant) is not dict or set(grant) != _GRANT_KEYS or type(grant["version"]) is not int
            or grant["version"] != 1 or type(grant["namespace"]) is not str
            or grant["namespace"] not in _PHASES
            or type(grant["phase"]) is not str or grant["phase"] not in _PHASES[grant["namespace"]]):
        raise _invalid()
    for name in ("record_id", "operation_id", "execution_id", "slot_id"):
        if type(grant[name]) is not str or not 1 <= len(grant[name]) <= 256:
            raise _invalid()
    if (re.fullmatch(REF_PATTERN, grant["slot_id"]) is None
            or grant["execution_id"] != f"{grant['namespace']}-{grant['record_id']}-{grant['phase']}"
            or (grant["namespace"] == "job" and grant["record_id"] != grant["operation_id"])
            or type(grant["fresh"]) is not bool or grant["fresh"] != (grant["phase"] != "business")):
        raise _invalid()
    for name, expected in (("execution_id", execution_id), ("phase", phase),
                           ("operation_id", operation_id), ("namespace", namespace), ("record_id", record_id)):
        if expected is not None and grant[name] != expected:
            raise _invalid("Bootstrap roots belong to another execution")
    for name in ("roots", "source_roots"):
        if type(grant[name]) is not dict or set(grant[name]) != ROOT_NAMES:
            raise _invalid()
        values = list(grant[name].values())
        for index, path in enumerate(values):
            _path(path)
            if any(_overlap(path, other) for other in values[index + 1:]):
                raise _invalid()
    paths, retained = grant["paths"], grant["retained_paths"]
    if (type(paths) is not dict or type(retained) is not list or len(retained) > 1
            or any(type(path) is not str for path in retained)
            or len(set(retained)) != len(retained)
            or set(paths) != set(grant["roots"].values()) | set(retained)
            or set(retained) & set(grant["roots"].values())
            or (retained and grant["phase"] != "evidence")):
        raise _invalid()
    identities, all_paths = set(), list(paths)
    for index, path in enumerate(all_paths):
        identity = paths[path]
        if type(identity) is not dict or set(identity) != _IDENTITY_KEYS:
            raise _invalid()
        validate_root({"path": path, **identity})
        inode = identity["device"], identity["inode"]
        if inode in identities or any(_overlap(path, other) for other in all_paths[index + 1:]):
            raise _invalid()
        identities.add(inode)
    if (grant["allocation_id"] != _allocation_id(grant["namespace"], grant["record_id"],
                                                 grant["slot_id"], grant["roots"], paths)
            or grant["grant_digest"] != _digest({key: value for key, value in grant.items() if key != "grant_digest"})):
        raise _invalid("Bootstrap root grant digest or slot binding differs")
    return copy.deepcopy(grant)


def _lease_resources(grant):
    resources = []
    for path in grant["roots"].values():
        identity = grant["paths"][path]
        resources.extend(("bootstrap-path:" + path,
                          f"bootstrap-inode:{identity['device']}:{identity['inode']}"))
    return resources


def _owner(grant):
    return "bootstrap:" + grant["allocation_id"]


def _available(tx, roots):
    """Inspect only the existing local lease table, including consumed history."""
    for root in roots.values():
        path = root["path"]
        key = "bootstrap-path:" + path
        ancestors = ["bootstrap-path:" + str(parent) for parent in PurePosixPath(path).parents]
        for resource in [key, *ancestors, f"bootstrap-inode:{root['device']}:{root['inode']}"]:
            if tx.execute("SELECT 1 FROM leases WHERE resource=?", (resource,)).fetchone() is not None:
                return False
        # Exact binary prefix range: '/' <= next character < '0'. No LIKE
        # wildcard semantics for admitted '%' or '_' path characters.
        if tx.execute("SELECT 1 FROM leases WHERE resource>=? AND resource<? LIMIT 1",
                      (key + "/", key + "0")).fetchone() is not None:
            return False
    return True


def assert_reserved(tx, grant):
    """A valid digest alone cannot replace the durable one-use consumption."""
    validate_grant(grant)
    for resource in _lease_resources(grant):
        row = tx.execute("SELECT owner FROM leases WHERE resource=?", (resource,)).fetchone()
        if row is None or row[0] != _owner(grant):
            raise _invalid("Bootstrap root consumption is missing or belongs to another operation")


def reserve(state, tx, row, phase, slots, *, extra_roots=None):
    """Consume roots in the same transaction as the caller's execution intent.

    ``row`` is an existing StateStore record. No slot can be released through a
    normal operation's ResourceManager.release, because these permanent leases
    use a distinct allocation owner. Cancellation never refunds a slot.
    """
    slots = validate_slots(slots)
    namespace, record_id, parent = row["namespace"], row["id"], row["parent"]
    if namespace not in _PHASES or phase not in _PHASES[namespace]:
        raise _invalid()
    extras = {} if extra_roots is None else copy.deepcopy(extra_roots)
    if type(extras) is not dict or set(extras) - {"evidence_store"} or (extras and phase != "evidence"):
        raise _invalid("Only an admitted evidence store may be an extra bootstrap writer")
    for root in extras.values():
        validate_root(root)
    current = state.get(namespace, record_id, tx)
    if current is None or current["parent"] != parent or current["digest"] != row["digest"]:
        raise _invalid()
    grants = copy.deepcopy(current["record"].get("bootstrap_grants", {}))
    if type(grants) is not dict or set(grants) - _PHASES[namespace]:
        raise _invalid()
    last = tx.execute("SELECT data_json FROM events WHERE namespace=? AND id=? "
                      "AND kind='BOOTSTRAP_ROOTS_RESERVED' ORDER BY seq DESC LIMIT 1",
                      (namespace, record_id)).fetchone()
    if last is None:
        if grants:
            raise _invalid("Bootstrap allocation has no durable consumption event")
    else:
        try:
            historical = strict_loads(last[0].encode("utf-8"))
        except (JobError, UnicodeError) as error:
            raise _invalid("Bootstrap consumption event is malformed") from error
        if historical != {"bootstrap_grants": grants}:
            raise _invalid("Bootstrap consumption record differs from its immutable event")
    for prior_phase, prior in grants.items():
        validate_grant(prior, namespace=namespace, record_id=record_id,
                       operation_id=parent, phase=prior_phase)
    selected = None
    inherited = grants.get(phase) or (grants.get("preflight") if phase == "business" else None)
    if inherited is not None:
        validate_grant(inherited, namespace=namespace, record_id=record_id, operation_id=parent)
        assert_reserved(tx, inherited)
        selected = next((slot for slot in slots if slot["slot_id"] == inherited["slot_id"]), None)
        if selected is None:
            raise _invalid("Consumed bootstrap slot is no longer admitted")
        for name, root in selected["roots"].items():
            if inherited["roots"][name] != root["path"] or inherited["paths"][root["path"]] != {key: root[key] for key in _IDENTITY_KEYS}:
                raise _invalid("Consumed bootstrap slot was rebound")
    elif phase == "business":
        raise _invalid("Business execution has no consumed preflight roots")
    else:
        selected = next((slot for slot in slots if _available(tx, slot["roots"])), None)
        if selected is None:
            raise JobError("LIMIT_EXCEEDED", "No unused precreated bootstrap root slot remains")
    roots = {name: root["path"] for name, root in selected["roots"].items()}
    paths = {root["path"]: {key: root[key] for key in _IDENTITY_KEYS} for root in selected["roots"].values()}
    retained = []
    for root in extras.values():
        if root["path"] in paths:
            raise _invalid()
        paths[root["path"]] = {key: root[key] for key in _IDENTITY_KEYS}
        retained.append(root["path"])
    source_roots = copy.deepcopy(row["plan"]["execution"]["roots"])
    grant = {"version": 1, "namespace": namespace, "record_id": record_id, "operation_id": parent,
             "execution_id": f"{namespace}-{record_id}-{phase}", "phase": phase,
             "slot_id": selected["slot_id"], "roots": roots, "paths": paths,
             "retained_paths": sorted(retained), "fresh": phase != "business", "source_roots": source_roots,
             "allocation_id": _allocation_id(namespace, record_id, selected["slot_id"], roots, paths)}
    grant["grant_digest"] = _digest(grant)
    validate_grant(grant)
    if phase in grants:
        if grant != grants[phase]:
            raise _invalid("Bootstrap phase cannot be rebound")
        return grant
    if inherited is None:
        # Epoch is deliberately not authority for reuse. These leases remain
        # consumed across deployment epochs and are never reclaimed by timeout.
        for resource in _lease_resources(grant):
            tx.execute("INSERT INTO leases VALUES(?,?,?)", (resource, _owner(grant), 1))
    grants[phase] = grant
    state.update(tx, namespace, record_id, "BOOTSTRAP_ROOTS_RESERVED", {"bootstrap_grants": grants})
    return grant


def bind_execution(execution, grant):
    """Bind generated writable paths, preserving source/prepared/storage inputs.

    Call for normal preflight/business plans or to recover the original job's
    actual roots before constructing a separate observation. Evidence and
    reconciliation phase-specific readonly handling remains the runner's job.
    """
    validate_grant(grant)
    result = copy.deepcopy(execution)
    source, target = grant["source_roots"], grant["roots"]
    if result.get("roots") == target:
        return result
    if result.get("roots") != source:
        raise _invalid("Execution roots do not match their admitted allocation source")
    def mapped(value):
        if type(value) is str:
            for name, path in source.items():
                if value == path or value.startswith(path + "/"):
                    return target[name] + value[len(path):]
            return value
        if type(value) is list:
            return [mapped(item) for item in value]
        if type(value) is dict:
            return {key: mapped(item) for key, item in value.items()}
        return value
    result["roots"] = copy.deepcopy(target)
    for name in ("stages", "writable", "environment"):
        if name in result:
            result[name] = mapped(result[name])
    if result.get("kind") == "ledger.prepare" and "prepared" in result:
        result["prepared"] = mapped(result["prepared"])
    return result
