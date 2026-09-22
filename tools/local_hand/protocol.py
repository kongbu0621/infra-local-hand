"""Protocol primitives for Local Hand v0.1."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

TASK_SCHEMA = "local-hand-task/v1"
RESULT_SCHEMA = "local-hand-result/v1"
WORKER_VERSION = "local-hand-v0.1"
MAX_TASK_ID_DIGITS = 64
TASK_ID_RE = re.compile(rf"^LH[0-9]{{4,{MAX_TASK_ID_DIGITS}}}$")
_DIGEST_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# v0.1 resource ceilings. Keep write <= read so Local Hand never creates a text
# object that its own bounded read capability cannot subsequently observe. The
# task envelope allows encoding overhead for a full-size UTF-8 write payload.
MAX_TEXT_BYTES = 1024 * 1024
MAX_TASK_JSON_BYTES = 8 * 1024 * 1024
MAX_RESULT_JSON_BYTES = 8 * 1024 * 1024
RESULT_STATUSES = frozenset({"succeeded", "failed", "rejected", "stale", "indeterminate"})
TASK_FIELDS = frozenset({"schema_version", "task_id", "target_node", "action", "params"})
RESULT_FIELDS = frozenset({
    "schema_version", "task_id", "task_digest", "target_node", "node_id", "action",
    "worker_version", "implementation_commit", "package_digest", "profile_digest",
    "status", "details", "error_code", "error",
})

CAPABILITIES = (
    "node.status",
    "repo.audit",
    "fs.list",
    "fs.read_text",
    "fs.write_text_cas",
    "git.status",
    "git.diff",
    "validation.run_profile",
)


@dataclass
class LocalHandError(RuntimeError):
    code: str
    message: str
    status: str = "rejected"

    def __str__(self) -> str:
        return self.message


def validate_result_contract(value: Any) -> None:
    """The same exact Result v1 shape applies at worker and controller ingress."""
    if not isinstance(value, dict) or set(value) != RESULT_FIELDS or not isinstance(value.get("details"), dict):
        raise LocalHandError("result_invalid", "Result v1 requires the exact envelope and structured details", "indeterminate")
    status = value["status"]
    if not isinstance(status, str) or status not in RESULT_STATUSES:
        raise LocalHandError("result_invalid", "Result v1 status invalid", "indeterminate")
    if status == "succeeded":
        valid_error = value["error_code"] is None and value["error"] is None
    else:
        valid_error = all(isinstance(value[key], str) and bool(value[key]) for key in ("error_code", "error"))
    if not valid_error:
        raise LocalHandError("result_invalid", "Result v1 status/error fields are inconsistent", "indeterminate")


def conflict_filename(digest: str) -> str:
    """Map a canonical task digest to its bounded conflict record name."""
    if not isinstance(digest, str) or _DIGEST_RE.fullmatch(digest) is None:
        raise LocalHandError("conflict_identity_invalid", "unsafe conflict digest", "indeterminate")
    return f"CONFLICT-{digest.lower()}.json"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def task_digest(task: dict[str, Any]) -> str:
    try:
        encoded = canonical_json(task).encode("utf-8")
    except UnicodeEncodeError as exc:
        # JSON escapes can decode to a lone surrogate, which has no canonical
        # UTF-8 spelling. Never replace or escape it to invent another identity.
        raise LocalHandError("task_digest_invalid", "Task has no canonical UTF-8 identity") from exc
    return hashlib.sha256(encoded).hexdigest()


def _base_result(
    task: dict[str, Any],
    node_id: str,
    provenance: dict[str, str] | None,
) -> dict[str, Any]:
    provenance = provenance or {}
    return {
        "schema_version": RESULT_SCHEMA,
        "task_id": str(task.get("task_id", "UNKNOWN")),
        "task_digest": task_digest(task) if isinstance(task, dict) else None,
        "target_node": node_id,
        "node_id": node_id,
        "action": str(task.get("action", "UNKNOWN")),
        "worker_version": WORKER_VERSION,
        "implementation_commit": provenance.get("implementation_commit"),
        "package_digest": provenance.get("package_digest"),
        "profile_digest": provenance.get("profile_digest"),
    }


def result_success(
    task: dict[str, Any],
    node_id: str,
    details: dict[str, Any],
    provenance: dict[str, str] | None = None,
) -> dict[str, Any]:
    result = _base_result(task, node_id, provenance)
    result.update({
        "status": "succeeded",
        "details": details,
        "error_code": None,
        "error": None,
    })
    return result


def result_error(
    task: dict[str, Any],
    node_id: str,
    exc: Exception,
    provenance: dict[str, str] | None = None,
) -> dict[str, Any]:
    if isinstance(exc, LocalHandError):
        status, code, message = exc.status, exc.code, exc.message
    else:
        status, code, message = "failed", "internal_error", f"{type(exc).__name__}: {exc}"
    result = _base_result(task, node_id, provenance)
    result.update({
        "status": status,
        "details": getattr(exc, "details", {}) if isinstance(getattr(exc, "details", {}), dict) else {},
        "error_code": code,
        "error": message,
    })
    return result
