"""Q2 bounded wire facts. Parsing grants no query, start, or release authority.

This module is pure and independent of the privileged observer. The caller must
obtain requests and expected roots from protected admission, not from a peer.
Successful decoding checks claims; it does not independently prove OS facts.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
import re

REQUEST_LIMIT = 8192
RESPONSE_LIMIT = 32768
MAX_INTEGER = 2**63 - 1
ROOT_ROLES = ("work", "evidence", "temporary", "retained_store")
CALL_OPERATIONS = ("STATE_BEFORE", "GET_QUOTA", "STATE_AFTER")
EXIT_FLAGS = ("delivery_settled", "future_start_blocked", "job_empty",
              "unit_terminal", "tree_empty", "collectors_stopped",
              "stdout_eof", "stderr_eof")
UUID_PATTERN = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
_REQUEST_KEYS = frozenset(("schema", "operation", "request_id", "authority_digest",
    "installation_digest", "manifest_digest", "epoch", "generation", "boot_id",
    "slot_ref", "execution_id", "phase", "allocation_digest",
    "observation_grant_digest", "deadline_ns"))
_ROOT_KEYS = frozenset(("role", "device", "inode", "uid", "gid", "mode",
    "filesystem", "filesystem_uuid", "project_id", "xflags", "hard_bytes",
    "accounting", "enforcement", "identity_unchanged"))
_ROOT_FLAGS = frozenset(("accounting", "enforcement", "identity_unchanged"))
_RECEIPT_KEYS = frozenset(("schema", "request_digest", "status", "reason",
    "deadline_ns", "started_ns", "finished_ns", "query", "roots", "calls", "exit"))
_PHASES = {"job": {"preflight", "business", "evidence"},
           "reconcile": {"reconcile", "evidence"}}


class QuotaError(ValueError):
    """Fixed, path-free diagnostic; all client errors leave admission unresolved."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise QuotaError(code)


def integer(value, low=0, high=MAX_INTEGER):
    require(type(value) is int and low <= value <= high, "INTEGER")
    return value


def match(value, pattern):
    require(type(value) is str and re.fullmatch(pattern, value, re.ASCII) is not None,
            "IDENTITY")
    return value


def _keys(value, keys):
    require(type(value) is dict and value.keys() == keys, "FIELDS")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_KEY")
        result[key] = value
    return result


def _not_integer(_value):
    raise QuotaError("NON_INTEGER_NUMBER")


def _load(raw, limit, max_depth):
    require(type(raw) is bytes and 0 < len(raw) <= limit, "BYTE_LIMIT")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_float=_not_integer, parse_constant=_not_integer)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, QuotaError):
            raise
        raise QuotaError("JSON") from None

    def walk(item, depth):
        require(depth <= max_depth, "DEPTH")
        if type(item) is str:
            require(not any(0xD800 <= ord(char) <= 0xDFFF for char in item), "SURROGATE")
        elif type(item) is int:
            integer(item, -MAX_INTEGER, MAX_INTEGER)
        elif type(item) is dict:
            for key, child in item.items():
                walk(key, depth + 1)
                walk(child, depth + 1)
        elif type(item) is list:
            for child in item:
                walk(child, depth + 1)

    walk(value, 1)
    return value


def _canonical(value, limit):
    wire = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")
    require(len(wire) <= limit, "BYTE_LIMIT")
    return wire


def canonical_path(value):
    require(type(value) is str and 1 < len(value) <= 4096
            and value.startswith("/") and not value.startswith("//")
            and str(PurePosixPath(value)) == value
            and ".." not in PurePosixPath(value).parts
            and re.fullmatch(r"/[A-Za-z0-9/._-]+", value) is not None, "PATH")
    return value


@dataclass(frozen=True, slots=True)
class Request:
    wire: bytes

    @property
    def digest(self):
        return hashlib.sha256(self.wire).hexdigest()

    @property
    def query_unit(self):
        return "lhqo-" + self.digest + ".service"

    def as_dict(self):
        return json.loads(self.wire)


@dataclass(frozen=True, slots=True)
class Receipt:
    wire: bytes
    domain_hard_bytes: int

    def as_dict(self):
        return json.loads(self.wire)


def decode_request(raw):
    value = _load(raw, REQUEST_LIMIT, 4)
    _keys(value, _REQUEST_KEYS)
    require(value["schema"] == "local-hand-quota-observe/v1"
            and value["operation"] == "observe", "SCHEMA")
    for key in ("request_id", "epoch", "generation"):
        match(value[key], r"[0-9a-f]{32}")
    for key in ("authority_digest", "installation_digest", "manifest_digest",
                "allocation_digest", "observation_grant_digest"):
        match(value[key], r"[0-9a-f]{64}")
    match(value["boot_id"], UUID_PATTERN)
    match(value["slot_ref"], r"[a-z0-9][a-z0-9._-]{0,127}")
    execution = match(value["execution_id"], r"[a-zA-Z0-9:_.-]{1,200}")
    namespace, _, record_phase = execution.partition("-")
    record, _, suffix = record_phase.rpartition("-")
    require(type(value["phase"]) is str and namespace in _PHASES
            and value["phase"] in _PHASES[namespace] and bool(record)
            and suffix == value["phase"], "EXECUTION_PHASE")
    integer(value["deadline_ns"], 1)
    return Request(_canonical(value, REQUEST_LIMIT))


def _root(value):
    _keys(value, _ROOT_KEYS)
    require(type(value["role"]) is str and value["role"] in ROOT_ROLES, "ROOT_ROLE")
    for key, low, high in (("device", 0, MAX_INTEGER), ("inode", 1, MAX_INTEGER),
            ("uid", 1, 2**32 - 2), ("gid", 0, 2**32 - 2),
            ("project_id", 1, 2**32 - 1), ("xflags", 0, 2**32 - 1)):
        integer(value[key], low, high)
    require(integer(value["mode"]) == 0o40700, "ROOT_MODE")
    require(type(value["filesystem"]) is str and value["filesystem"] in {"ext4", "xfs"},
            "FILESYSTEM")
    match(value["filesystem_uuid"], UUID_PATTERN)
    require(value["xflags"] & 0x200 != 0, "PROJECT_INHERITANCE")
    require(integer(value["hard_bytes"], 1) % 1024 == 0, "HARD_LIMIT")
    for key in _ROOT_FLAGS:
        require(type(value[key]) is bool, "ROOT_FLAG")


def _roots(values, phase, *, complete):
    require(type(values) is list and len(values) <= 4, "ROOT_COUNT")
    by_role, identities, fs_devices, device_fs, domains = {}, set(), {}, {}, {}
    for value in values:
        _root(value)
        role = value["role"]
        require(role not in by_role and (role != "retained_store" or phase == "evidence"),
                "ROOT_ROLE")
        identity = value["device"], value["inode"]
        require(identity not in identities, "ROOT_ALIAS")
        identities.add(identity)
        fs, device = value["filesystem_uuid"], value["device"]
        require(fs_devices.get(fs, device) == device
                and device_fs.get(device, (fs, value["filesystem"])) == (fs, value["filesystem"]),
                "FILESYSTEM_ALIAS")
        fs_devices[fs], device_fs[device] = device, (fs, value["filesystem"])
        domain = fs, value["project_id"]
        require(domains.get(domain, value["hard_bytes"]) == value["hard_bytes"],
                "DOMAIN_LIMIT_CONFLICT")
        domains[domain] = value["hard_bytes"]
        by_role[role] = value
    if complete:
        require(set(ROOT_ROLES[:3]) <= by_role.keys(), "ROOT_COUNT")
    return by_role, integer(sum(domains.values()))


def validate_expected_roots(values, phase):
    """Return a detached validated declaration; not a filesystem observation."""
    require(type(phase) is str and phase in {"preflight", "business", "reconcile", "evidence"},
            "EXECUTION_PHASE")
    # Check the finite declaration before serializing it as a detached snapshot.
    roots, _ = _roots(values, phase, complete=True)
    require(all(all(root[key] for key in _ROOT_FLAGS) for root in roots.values()),
            "EXPECTED_ENFORCEMENT")
    return _load(_canonical(values, RESPONSE_LIMIT), RESPONSE_LIMIT, 6)


def _calls(values, expected, observed):
    require(type(values) is list and len(values) <= 12, "CALL_COUNT")
    positions, active, failed = {}, None, False
    for value in values:
        _keys(value, {"role", "operation", "rc", "errno"})
        role = value["role"]
        require(type(role) is str and role in expected, "CALL_ROLE")
        require(not failed, "CALL_AFTER_FAILURE")
        if active != role:
            require(role not in positions and (active is None or positions[active] == 3),
                    "CALL_ORDER")
            active = role
        position = positions.get(role, 0)
        require(position < 3 and value["operation"] == CALL_OPERATIONS[position], "CALL_ORDER")
        integer(value["rc"], -1, 0)
        integer(value["errno"], 0, 4095)
        failed = value["rc"] == -1
        positions[role] = position + 1
    if observed:
        require(not failed and positions == {role: 3 for role in expected}, "CALLS_INCOMPLETE")


def decode_receipt(raw, request, expected_roots, *, now_ns):
    """Bind all reported roots and exit claims to this exact original request."""
    request = decode_request(request.wire)  # Dataclass construction is not admission.
    original = request.as_dict()
    expected = validate_expected_roots(expected_roots, original["phase"])
    expected, _ = _roots(expected, original["phase"], complete=True)
    value = _load(raw, RESPONSE_LIMIT, 6)
    _keys(value, _RECEIPT_KEYS)
    require(value["schema"] == "local-hand-quota-receipt/v1", "SCHEMA")
    require(value["request_digest"] == request.digest, "REQUEST_BINDING")
    require(type(value["status"]) is str
            and value["status"] in {"OBSERVED", "UNKNOWN", "REJECTED", "UNSUPPORTED"}, "STATUS")
    match(value["reason"], r"[A-Z][A-Z0-9_]{0,63}")
    observed = value["status"] == "OBSERVED"
    deadline = integer(value["deadline_ns"], 1, original["deadline_ns"])
    require(integer(now_ns) < deadline, "DEADLINE")
    start, finish = value["started_ns"], value["finished_ns"]
    if start is not None:
        integer(start, 0, now_ns)
    if finish is not None:
        require(start is not None, "TIMING")
        integer(finish, start, now_ns)
    if observed:
        require(start is not None and finish is not None and finish < deadline, "TIMING")
    query = value["query"]
    if query is not None:
        _keys(query, {"unit", "invocation_id", "cgroup"})
        require(query["unit"] == request.query_unit, "QUERY_BINDING")
        match(query["invocation_id"], r"[0-9a-f]{32}")
        require(PurePosixPath(canonical_path(query["cgroup"])).name == request.query_unit,
                "QUERY_BINDING")
    require(not observed or query is not None, "QUERY_MISSING")
    roots, total = _roots(value["roots"], original["phase"], complete=observed)
    require(roots.keys() <= expected.keys() and (not observed or roots.keys() == expected.keys()),
            "ROOT_BINDING")
    for role, root in roots.items():
        keys = _ROOT_KEYS if observed else _ROOT_KEYS - _ROOT_FLAGS
        require(all(root[key] == expected[role][key] for key in keys), "ROOT_BINDING")
    _calls(value["calls"], expected, observed)
    proof = value["exit"]
    _keys(proof, {*EXIT_FLAGS, "proof_digest", "exec_main_code", "exec_main_status",
                  "client_returncode"})
    for key in EXIT_FLAGS:
        require(type(proof[key]) is bool, "EXIT_FLAG")
    if proof["proof_digest"] is not None:
        match(proof["proof_digest"], r"[0-9a-f]{64}")
    for key, low, high in (("exec_main_code", 0, 6), ("exec_main_status", 0, 255),
                            ("client_returncode", -255, 255)):
        if proof[key] is not None:
            integer(proof[key], low, high)
    if observed:
        require(all(proof[key] for key in EXIT_FLAGS) and proof["proof_digest"] is not None
                and (proof["exec_main_code"], proof["exec_main_status"], proof["client_returncode"])
                == (1, 0, 0), "EXIT_UNPROVEN")
    return Receipt(_canonical(value, RESPONSE_LIMIT), total)
