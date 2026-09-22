"""Strict, language-independent ``lh-job-v1`` request contract.

The raw decoder belongs ahead of an SDK's JSON parser. Validating a parsed
mapping cannot recover duplicate keys that a permissive parser has discarded.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping

SCHEMA_VERSION = "lh-job-v1"
MAX_SAFE_INTEGER = 2**53 - 1
MAX_REQUEST_BYTES = 64 * 1024
MAX_CANONICAL_BYTES = 16 * 1024
MAX_DEPTH = 8
KINDS = (
    "host.inspect", "ledger.prepare", "ledger.test.source",
    "ledger.test.resources", "ledger.test.installed_local", "ledger.nas.roundtrip",
)
SUITES = ("a1_resources", "a1_response_boundaries", "a2_snapshot_resources", "a2_semantic_resources")
REF_PATTERN = r"[a-z0-9][a-z0-9._-]{0,127}"
UUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
UUID4_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
DIGEST_PATTERN = r"[0-9a-f]{64}"


class JobError(Exception):
    """A structured, deliberately path/token-free protocol error."""

    def __init__(self, code: str, message: str, details: Any = None):
        self.code, self.message, self.details = code, message, details
        super().__init__(message)

    def as_dict(self) -> dict[str, Any]:
        result = {"code": self.code, "message": self.message}
        if self.details is not None:
            result["details"] = self.details
        return result


@dataclass(frozen=True)
class Principal:
    """Identity populated by a verified in-process authenticator, never JSON."""

    principal_id: str
    scopes: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, str) or not self.principal_id or len(self.principal_id) > 256:
            raise JobError("UNAUTHORIZED", "Invalid authenticated principal")
        if not isinstance(self.scopes, frozenset) or any(not isinstance(s, str) for s in self.scopes):
            raise JobError("UNAUTHORIZED", "Invalid authenticated scopes")


def _invalid(message: str = "Request does not match the fixed contract") -> JobError:
    return JobError("INVALID_REQUEST", message)


def _integer(text: str) -> int:
    # Limit before constructing an attacker-controlled arbitrary precision int.
    if len(text.lstrip("-")) > 16:
        raise _invalid("JSON integer exceeds the interoperable range")
    value = int(text)
    if abs(value) > MAX_SAFE_INTEGER:
        raise _invalid("JSON integer exceeds the interoperable range")
    return value


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise _invalid("Duplicate JSON object key")
        result[key] = value
    return result


def _tree(value: Any, depth: int = 0) -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise _invalid("JSON contains an unpaired surrogate")
    elif type(value) is int:
        if abs(value) > MAX_SAFE_INTEGER:
            raise _invalid("JSON integer exceeds the interoperable range")
    elif isinstance(value, dict):
        if depth >= MAX_DEPTH:
            raise _invalid("JSON nesting exceeds the request limit")
        for key, item in value.items():
            if not isinstance(key, str):
                raise _invalid()
            _tree(key, depth + 1)
            _tree(item, depth + 1)
    elif isinstance(value, list):
        if depth >= MAX_DEPTH:
            raise _invalid("JSON nesting exceeds the request limit")
        for item in value:
            _tree(item, depth + 1)
    elif value is None or type(value) is bool:
        pass  # JSON-RPC may contain these; tool schemas reject them as needed.
    else:
        raise _invalid("Floating point and unsupported JSON values are forbidden")


def strict_loads(raw: bytes | str) -> Any:
    """Decode a bounded raw JSON request without lossy parser behavior."""
    if isinstance(raw, bytes):
        if len(raw) > MAX_REQUEST_BYTES:
            raise JobError("LIMIT_EXCEEDED", "Request body exceeds 64 KiB")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeError:
            raise _invalid("Request body is not valid UTF-8") from None
    elif isinstance(raw, str):
        try:
            if len(raw.encode("utf-8", errors="strict")) > MAX_REQUEST_BYTES:
                raise JobError("LIMIT_EXCEEDED", "Request body exceeds 64 KiB")
        except UnicodeError:
            raise _invalid("Request body is not valid UTF-8") from None
        text = raw
    else:
        raise _invalid("Raw JSON must be bytes or text")
    # Bound nesting before invoking the recursive JSON implementation. Quoted
    # braces do not affect depth; malformed escape sequences still fail json.loads.
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise _invalid("JSON nesting exceeds the request limit")
        elif char in "]}":
            depth -= 1
    def reject_number(_: str) -> Any:
        raise _invalid("Floating point and non-finite JSON values are forbidden")
    try:
        result = json.loads(text, object_pairs_hook=_pairs, parse_int=_integer,
                            parse_float=reject_number, parse_constant=reject_number)
    except (ValueError, RecursionError):
        raise _invalid("Malformed JSON request") from None
    _tree(result)
    return result


def _object(properties: dict, required: tuple | list | None = None) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties if required is None else required), "additionalProperties": False}


def _string(pattern: str) -> dict:
    return {"type": "string", "pattern": "^(?:" + pattern + ")$"}


REF = _string(REF_PATTERN)
UUID = _string(UUID_PATTERN)
UUID4 = _string(UUID4_PATTERN)
DIGEST = _string(DIGEST_PATTERN)
NATURAL = {"type": "integer", "minimum": 0, "maximum": MAX_SAFE_INTEGER}
POSITIVE = {"type": "integer", "minimum": 1, "maximum": MAX_SAFE_INTEGER}
EXPECTED_SCHEMA = _object({"node_id": REF, "install_uuid": UUID, "deployment_epoch": POSITIVE,
                           "profile_digest": DIGEST, "policy_digest": DIGEST, "registry_digest": DIGEST})
INPUT_SCHEMAS = {
    "host.inspect": _object({}),
    "ledger.prepare": _object({"source_ref": REF, "build_cache_ref": REF}),
    "ledger.test.source": _object({"prepared_ref": REF}),
    "ledger.test.resources": _object({"prepared_ref": REF, "suite": {"type": "string", "enum": list(SUITES)}}),
    "ledger.test.installed_local": _object({"prepared_ref": REF}),
    "ledger.nas.roundtrip": _object({"prepared_ref": REF, "storage_ref": REF}),
}
_COMMON = {"schema_version": {"const": SCHEMA_VERSION}, "operation_id": UUID4,
           "kind": {"type": "string", "enum": list(KINDS)}, "profile_ref": REF,
           "expected": EXPECTED_SCHEMA, "inputs": _object({}), "expires_at": NATURAL,
           "request_digest": DIGEST}
SUBMIT_SCHEMA = {"type": "object", "oneOf": [
    _object({**_COMMON, "kind": {"const": kind}, "inputs": INPUT_SCHEMAS[kind]}) for kind in KINDS
]}
_CURSOR = _string(r"[A-Za-z0-9_-]{1,2048}")
_PAGE = {"type": "integer", "minimum": 1, "maximum": 100}
CANCEL_TARGET_SCHEMA = {"oneOf": [
    _object({"kind": {"const": "job"}}),
    _object({"kind": {"const": "reconcile"}, "reconcile_id": UUID4}),
]}
TOOL_SCHEMAS = {
    "lh_capabilities": _object({"cursor": _CURSOR, "page_size": _PAGE}, ()),
    "lh_job_submit": SUBMIT_SCHEMA,
    "lh_job_status": _object({"operation_id": UUID4, "reconcile_id": UUID4}, ("operation_id",)),
    "lh_job_cancel": _object({"operation_id": UUID4, "expected_request_digest": DIGEST, "target": CANCEL_TARGET_SCHEMA}),
    "lh_job_reconcile": _object({"operation_id": UUID4, "expected_request_digest": DIGEST, "reconcile_id": UUID4}),
    "lh_evidence_manifest": _object({"operation_id": UUID4, "cursor": _CURSOR, "page_size": _PAGE}, ("operation_id",)),
    "lh_evidence_read_chunk": _object({"artifact_id": REF, "offset": NATURAL,
        "length": {"type": "integer", "minimum": 1, "maximum": 256 * 1024}, "expected_sha256": DIGEST},
        ("artifact_id", "offset", "expected_sha256")),
}
TOOL_SCOPES = {
    "lh_capabilities": "lh:inspect", "lh_job_submit": "lh:submit", "lh_job_status": "lh:read",
    "lh_job_cancel": "lh:cancel", "lh_job_reconcile": "lh:reconcile",
    "lh_evidence_manifest": "lh:evidence", "lh_evidence_read_chunk": "lh:evidence",
}


def _matches(value: Any, schema: Mapping[str, Any]) -> bool:
    if "oneOf" in schema:
        return sum(_matches(value, candidate) for candidate in schema["oneOf"]) == 1
    if "const" in schema:
        return type(value) is type(schema["const"]) and value == schema["const"]
    typ = schema.get("type")
    if typ == "object":
        if type(value) is not dict or not set(schema["required"]) <= value.keys():
            return False
        return not (value.keys() - schema["properties"].keys()) and all(
            _matches(item, schema["properties"][key]) for key, item in value.items())
    if typ == "string":
        return type(value) is str and ("enum" not in schema or value in schema["enum"]) and (
            "pattern" not in schema or re.fullmatch(schema["pattern"], value) is not None)
    if typ == "integer":
        return type(value) is int and schema.get("minimum", -MAX_SAFE_INTEGER) <= value <= schema.get("maximum", MAX_SAFE_INTEGER)
    return False


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _submit_without_digest(request: Any) -> dict:
    if type(request) is not dict:
        raise _invalid()
    candidate = dict(request)
    candidate.setdefault("request_digest", "0" * 64)
    _tree(candidate)
    if not _matches(candidate, SUBMIT_SCHEMA):
        raise _invalid()
    candidate.pop("request_digest")
    if len(canonical_bytes(candidate)) > MAX_CANONICAL_BYTES:
        raise JobError("LIMIT_EXCEEDED", "Canonical submission exceeds 16 KiB")
    return candidate


def request_digest(request: Mapping[str, Any]) -> str:
    """Compute a digest after validating every field; digest itself is excluded."""
    return hashlib.sha256(canonical_bytes(_submit_without_digest(request))).hexdigest()


def validate_submit(request: Any) -> dict:
    if isinstance(request, (str, bytes)):
        request = strict_loads(request)
    if type(request) is not dict or "request_digest" not in request:
        raise _invalid()
    expected = request_digest(request)
    if request["request_digest"] != expected:
        raise JobError("CONFLICT", "Request digest does not match canonical request")
    # Return a detached structure so the caller cannot mutate validated inputs.
    return json.loads(canonical_bytes(request))


def validate_tool_args(tool_name: str, arguments: Any) -> dict:
    if tool_name not in TOOL_SCHEMAS:
        raise JobError("UNSUPPORTED", "Unknown restricted job tool")
    if isinstance(arguments, (str, bytes)):
        arguments = strict_loads(arguments)
    if tool_name == "lh_job_submit":
        return validate_submit(arguments)
    _tree(arguments)
    if not _matches(arguments, TOOL_SCHEMAS[tool_name]):
        raise _invalid()
    return json.loads(canonical_bytes(arguments))


TOOL_SCHEMA_DIGEST = hashlib.sha256(canonical_bytes(TOOL_SCHEMAS)).hexdigest()
CONTRACT_DIGEST = TOOL_SCHEMA_DIGEST
