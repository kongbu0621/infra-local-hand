"""Bounded, JSON-only deployment plans and durable operation records."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
import time

SCHEMA = "local-hand-deployment/v1"
PLAN_SCHEMA = "local-hand-deployment-plan/v1"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
KINDS = frozenset({"file", "service", "gateway"})


class DeployError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise DeployError("INVALID_RECORD", "Record must be finite JSON") from exc


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate field")
            value[key] = item
        return value
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite")))
    except (ValueError, UnicodeError, TypeError) as exc:
        raise DeployError("INVALID_RECORD", "Record is not unambiguous JSON") from exc


def identity(value, field="identity"):
    if not isinstance(value, str) or ID.fullmatch(value) is None:
        raise DeployError("INVALID_PLAN", f"Invalid {field}")
    return value


@dataclass(frozen=True)
class Limits:
    max_operations: int = 128
    max_steps: int = 128
    max_record_bytes: int = 2 * 1024 * 1024
    max_events: int = 8192
    recovery_events: int = 2048
    max_database_bytes: int = 128 * 1024 * 1024
    max_attempts: int = 8
    wait_seconds: int = 30

    def __post_init__(self):
        if any(type(x) is not int or x <= 0 for x in asdict(self).values()):
            raise DeployError("INVALID_LIMIT", "Limits must be positive integers")
        if self.recovery_events >= self.max_events:
            raise DeployError("INVALID_LIMIT", "Recovery event reserve must be below total event limit")


def validate_plan(plan, limits=Limits()):
    keys = {"schema", "request_id", "node_id", "source", "target", "steps", "profile", "digest"}
    if not isinstance(plan, dict) or set(plan) != keys or plan["schema"] != PLAN_SCHEMA:
        raise DeployError("INVALID_PLAN", "Unknown deployment plan format")
    identity(plan["request_id"], "request ID"); identity(plan["node_id"], "node ID")
    for key in ("source", "target"):
        if not isinstance(plan[key], dict) or not HEX.fullmatch(str(plan[key].get("deployment_digest", ""))):
            raise DeployError("INVALID_PLAN", "Source and target require exact deployment digests")
    if (not isinstance(plan["profile"], dict) or not isinstance(plan["steps"], list)
            or not 0 <= len(plan["steps"]) <= limits.max_steps):
        raise DeployError("INVALID_PLAN", "Plan exceeds its supported action count")
    seen = set()
    for step in plan["steps"]:
        if (not isinstance(step, dict) or set(step) != {"id", "kind", "action"}
                or step["kind"] not in KINDS or not isinstance(step["action"], dict)):
            raise DeployError("INVALID_PLAN", "Unsupported deployment action")
        identity(step["id"], "step ID")
        if step["id"] in seen:
            raise DeployError("INVALID_PLAN", "Duplicate deployment step")
        seen.add(step["id"])
    without = {key: value for key, value in plan.items() if key != "digest"}
    if plan["digest"] != digest(without) or len(canonical(plan)) > limits.max_record_bytes // 2:
        raise DeployError("INVALID_PLAN", "Plan digest or size is invalid")
    return plan


def seal_plan(value):
    value = decode(canonical(value))
    value["digest"] = digest({key: item for key, item in value.items() if key != "digest"})
    return validate_plan(value)


def operation_id(request_id):
    return "deploy-" + hashlib.sha256(identity(request_id).encode("ascii")).hexdigest()[:32]


def new_operation(plan, *, predecessor=None):
    validate_plan(plan)
    now = time.time_ns()
    return {"schema": SCHEMA, "id": operation_id(plan["request_id"]), "plan": plan,
            "created_ns": now, "updated_ns": now, "phase": "PLANNED", "direction": "APPLY",
            "decision": None, "decision_id": None, "released": False, "waiting": None,
            "gate_sequence": None, "gate_owned": False, "predecessor": predecessor,
            "successor": None, "handoff_complete": False, "rollback_successor": None,
            "steps": [{"id": step["id"], "state": "PLANNED", "prepared": None,
                       "restore": None, "attempts": [], "restore_attempts": [],
                       "observation": None, "restore_observation": None,
                       "effective": False} for step in plan["steps"]],
            "errors": {"primary": [], "recovery": [], "diagnostics": []},
            "checks": {}, "startup": {"blocked": False, "current": None}}
