"""Internal, non-refundable execution envelopes for one durable operation.

Public profile limits remain unchanged. Every helper receives a conservative
share plus the same boot-bound operation deadline; no helper report refunds
capacity or establishes actual group CPU consumption.
"""
from __future__ import annotations

import hashlib
import re
import threading
import time

from .contract import JobError, MAX_SAFE_INTEGER, UUID_PATTERN, canonical_bytes
from .policy import BUDGET_FIELDS

NANOSECONDS = 1_000_000_000
_boot_id = None
_clock_failed = False
_clock_lock = threading.Lock()
_SHARED = {"wall_seconds", "cpu_seconds", "log_bytes"}
_PHASES = {"job": ("preflight", "business", "evidence"), "reconcile": ("reconcile", "evidence")}
_GRANT_KEYS = {"version", "namespace", "record_id", "operation_id", "execution_id", "phase",
               "budget_digest", "boot_id", "started_boottime_ns", "reserved_boottime_ns",
               "deadline_boottime_ns", "limits"}
_STATE_KEYS = {"version", "namespace", "record_id", "operation_id", "budget_digest", "boot_id",
               "started_boottime_ns", "last_boottime_ns", "deadline_boottime_ns", "grants"}


class BudgetExhausted(JobError):
    """An operation's own allocation cannot authorize another helper."""

    def __init__(self, message):
        super().__init__("LIMIT_EXCEEDED", message)


def _invalid(message="Execution budget identity is unresolved"):
    return JobError("IO_UNCERTAIN", message)


def initialize_clock():
    """Read the fixed kernel boot identity once, before broker transactions."""
    global _boot_id, _clock_failed
    with _clock_lock:
        if _clock_failed:
            raise _invalid("Trusted operation clock is unavailable")
        if _boot_id is None:
            try:
                if not hasattr(time, "CLOCK_BOOTTIME"):
                    raise ValueError("boot clock unavailable")
                with open("/proc/sys/kernel/random/boot_id", "rb") as stream:
                    raw = stream.read(38)
                value = raw.decode("ascii").strip()
                if re.fullmatch(UUID_PATTERN, value) is None or len(raw) > 37:
                    raise ValueError("boot identity unavailable")
                _boot_id = value
            except (OSError, UnicodeError, ValueError) as error:
                _clock_failed = True
                raise _invalid("Trusted operation clock is unavailable") from error


def current_clock():
    initialize_clock()
    try:
        now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    except (OSError, ValueError) as error:
        raise _invalid("Trusted operation clock is unavailable") from error
    result = {"boot_id": _boot_id, "boottime_ns": now}
    _validate_clock(result)
    return result


def _validate_clock(value):
    if (type(value) is not dict or set(value) != {"boot_id", "boottime_ns"}
            or type(value["boot_id"]) is not str or re.fullmatch(UUID_PATTERN, value["boot_id"]) is None
            or type(value["boottime_ns"]) is not int or value["boottime_ns"] < 0):
        raise _invalid("Trusted operation clock is malformed")


def _validate_limits(limits):
    if type(limits) is not dict or set(limits) != BUDGET_FIELDS:
        raise _invalid("Execution budget fields are incomplete")
    for key, value in limits.items():
        if type(value) is not int or not (0 if key == "nas_bytes" else 1) <= value <= MAX_SAFE_INTEGER:
            raise _invalid("Execution budget limits are malformed")


def allocated_limits(original, namespace):
    _validate_limits(original)
    if namespace not in _PHASES:
        raise _invalid()
    shares = dict(original)
    for key in _SHARED:
        shares[key] //= len(_PHASES[namespace])
    if (any(shares[key] < 1 for key in _SHARED)
            or shares["wall_seconds"] <= shares["terminate_grace_seconds"]):
        raise BudgetExhausted("Operation budget cannot fund a bounded helper and its stop grace")
    return shares


def validate_grant(grant, *, execution_id=None, phase=None, budgets=None, namespace=None,
                   record_id=None, operation_id=None, original_budgets=None):
    if type(grant) is not dict or set(grant) != _GRANT_KEYS or type(grant["version"]) is not int or grant["version"] != 1:
        raise _invalid()
    kind = grant["namespace"]
    if type(kind) is not str or kind not in _PHASES or grant["phase"] not in _PHASES[kind]:
        raise _invalid()
    for key in ("record_id", "operation_id", "execution_id"):
        if type(grant[key]) is not str or not 1 <= len(grant[key]) <= 256:
            raise _invalid()
    if (grant["execution_id"] != f"{kind}-{grant['record_id']}-{grant['phase']}"
            or (kind == "job" and grant["record_id"] != grant["operation_id"])):
        raise _invalid()
    if (type(grant["boot_id"]) is not str or re.fullmatch(UUID_PATTERN, grant["boot_id"]) is None
            or type(grant["budget_digest"]) is not str or re.fullmatch(r"[0-9a-f]{64}", grant["budget_digest"]) is None):
        raise _invalid()
    for key in ("started_boottime_ns", "reserved_boottime_ns", "deadline_boottime_ns"):
        if type(grant[key]) is not int or grant[key] < 0:
            raise _invalid()
    if not grant["started_boottime_ns"] <= grant["reserved_boottime_ns"] < grant["deadline_boottime_ns"]:
        raise _invalid()
    _validate_limits(grant["limits"])
    if grant["limits"]["wall_seconds"] <= grant["limits"]["terminate_grace_seconds"]:
        raise _invalid("Helper wall envelope does not include its stop grace")
    for key, expected in (("execution_id", execution_id), ("phase", phase), ("namespace", namespace),
                          ("record_id", record_id), ("operation_id", operation_id)):
        if expected is not None and grant[key] != expected:
            raise _invalid()
    if budgets is not None:
        _validate_limits(budgets)
        if grant["limits"] != budgets:
            raise _invalid("Helper limits differ from their durable reservation")
    if original_budgets is not None:
        _validate_limits(original_budgets)
        if (grant["budget_digest"] != hashlib.sha256(canonical_bytes(original_budgets)).hexdigest()
                or grant["limits"] != allocated_limits(original_budgets, kind)
                or grant["deadline_boottime_ns"] != grant["started_boottime_ns"] + original_budgets["wall_seconds"] * NANOSECONDS):
            raise _invalid("Durable helper reservation differs from the admitted operation budget")


def remaining_ns(grant, now=None):
    validate_grant(grant)
    now = current_clock() if now is None else now
    _validate_clock(now)
    if now["boot_id"] != grant["boot_id"] or now["boottime_ns"] < grant["reserved_boottime_ns"]:
        raise _invalid("Operation deadline belongs to another or uncertain clock")
    remaining = grant["deadline_boottime_ns"] - now["boottime_ns"]
    if remaining <= 0:
        raise BudgetExhausted("Operation wall deadline is exhausted")
    return remaining


def remaining_seconds(grant, now=None):
    return remaining_ns(grant, now) / NANOSECONDS


def phase_deadline_ns(grant):
    """The phase end is fixed at reservation, including its final stop grace.

    Internal preparation, manager queueing and the actual helper all consume
    this same interval. A later subprocess may never renew a phase's wall cap.
    """
    validate_grant(grant)
    return min(grant["deadline_boottime_ns"],
               grant["reserved_boottime_ns"] + grant["limits"]["wall_seconds"] * NANOSECONDS)


def phase_remaining_ns(grant, now=None):
    now = current_clock() if now is None else now
    remaining_ns(grant, now=now)  # Includes the boot identity/clock checks.
    remaining = phase_deadline_ns(grant) - now["boottime_ns"]
    if remaining <= 0:
        raise BudgetExhausted("Execution phase wall deadline is exhausted")
    return remaining


def substage_limits(grant, stage):
    """Fixed, non-refundable CPU shares inside an already reserved phase.

    The units run sequentially and share storage and a single absolute wall
    envelope. Bootstrap stdout/stderr are null; only the helper gets a log
    capture. Its existing log allowance is therefore not granted twice.
    """
    validate_grant(grant)
    if stage not in ("bootstrap", "helper"):
        raise _invalid("Unknown fixed execution substage")
    limits = dict(grant["limits"])
    preparation = limits["cpu_seconds"] // 2
    if preparation < 1:
        raise BudgetExhausted("Phase CPU budget cannot fund preparation and its helper")
    limits["cpu_seconds"] = preparation if stage == "bootstrap" else limits["cpu_seconds"] - preparation
    return limits


def _validate_state(row, state):
    namespace, identity, parent = row["namespace"], row["id"], row["parent"]
    original = row["plan"]["budgets"]
    _validate_limits(original)
    digest = hashlib.sha256(canonical_bytes(original)).hexdigest()
    if (type(state) is not dict or set(state) != _STATE_KEYS
            or type(state["version"]) is not int or state["version"] != 1
            or (state["namespace"], state["record_id"], state["operation_id"], state["budget_digest"])
            != (namespace, identity, parent, digest) or type(state["grants"]) is not dict
            or set(state["grants"]) - set(_PHASES[namespace])):
        raise _invalid()
    for key in ("started_boottime_ns", "last_boottime_ns", "deadline_boottime_ns"):
        if type(state[key]) is not int or state[key] < 0:
            raise _invalid()
    if (type(state["boot_id"]) is not str or re.fullmatch(UUID_PATTERN, state["boot_id"]) is None
            or not state["started_boottime_ns"] <= state["last_boottime_ns"] < state["deadline_boottime_ns"]
            or state["deadline_boottime_ns"] != state["started_boottime_ns"] + original["wall_seconds"] * NANOSECONDS):
        raise _invalid()
    handles = row["record"].get("handles", {})
    if type(handles) is not dict or set(state["grants"]) != set(handles):
        raise _invalid("Execution intent and aggregate budget reservations differ")
    for old_phase, old in state["grants"].items():
        validate_grant(old, namespace=namespace, record_id=identity, operation_id=parent,
                       phase=old_phase, original_budgets=original)
        if (any(old[key] != state[key] for key in ("boot_id", "started_boottime_ns", "deadline_boottime_ns"))
                or old["reserved_boottime_ns"] > state["last_boottime_ns"]
                or type(handles[old_phase]) is not dict or handles[old_phase].get("execution_id") != old["execution_id"]):
            raise _invalid()
    if any(sum(item["limits"][key] for item in state["grants"].values()) > original[key] for key in _SHARED):
        raise _invalid("Helper reservations exceed the admitted operation budget")


def stored_grant(row, phase):
    state = row["record"].get("execution_budget")
    _validate_state(row, state)
    grant = state["grants"].get(phase)
    if grant is None:
        raise _invalid("Execution has no durable helper budget reservation")
    return grant


def reserve(row, phase, now=None):
    """Return a new state/grant; the caller commits both with execution intent."""
    namespace, identity, parent = row["namespace"], row["id"], row["parent"]
    if namespace not in _PHASES or phase not in _PHASES[namespace]:
        raise _invalid()
    original = row["plan"]["budgets"]
    limits = allocated_limits(original, namespace)
    now = current_clock() if now is None else now
    _validate_clock(now)
    digest = hashlib.sha256(canonical_bytes(original)).hexdigest()
    previous = row["record"].get("execution_budget")
    if previous is None:
        record = row["record"]
        if (record.get("handles") != {} or record.get("phase") != "QUEUED"
                or record.get("lifecycle") != "ACCEPTED"
                or record.get("business_started") is not False or record.get("helper_started") is not False
                or record.get("exit_proof") is not None or record.get("facts") or record.get("runner_result")
                or record.get("business_outcome") or record.get("frozen_snapshot")
                or phase != _PHASES[namespace][0]):
            raise _invalid("Prior execution has no durable aggregate budget; no new helper is authorized")
        previous = {"version": 1, "namespace": namespace, "record_id": identity, "operation_id": parent,
                    "budget_digest": digest, "boot_id": now["boot_id"], "started_boottime_ns": now["boottime_ns"],
                    "last_boottime_ns": now["boottime_ns"],
                    "deadline_boottime_ns": now["boottime_ns"] + original["wall_seconds"] * NANOSECONDS,
                    "grants": {}}
    _validate_state(row, previous)
    if previous["boot_id"] != now["boot_id"] or now["boottime_ns"] < previous["last_boottime_ns"]:
        raise _invalid("Operation deadline belongs to another or uncertain clock")
    expected_phase = "PREFLIGHT_COMPLETE" if phase == "business" else "AWAITING_SEAL" if phase == "evidence" else "QUEUED"
    if (row["record"]["phase"] != expected_phase
            or (phase == "business" and "preflight" not in previous["grants"])
            or (phase == "evidence" and not previous["grants"])):
        raise _invalid("Helper phase is not consistent with prior budget reservations")
    if phase in previous["grants"]:
        raise JobError("CONFLICT", "Helper budget reservation cannot be repeated or refunded")
    grant = {key: previous[key] for key in ("version", "namespace", "record_id", "operation_id", "budget_digest",
                                          "boot_id", "started_boottime_ns", "deadline_boottime_ns")}
    grant.update(execution_id=f"{namespace}-{identity}-{phase}", phase=phase,
                 reserved_boottime_ns=now["boottime_ns"], limits=limits)
    # Reject exhaustion before constructing a grant whose reservation time
    # would no longer precede its immutable deadline.
    if previous["deadline_boottime_ns"] - now["boottime_ns"] <= limits["terminate_grace_seconds"] * NANOSECONDS:
        raise BudgetExhausted("Operation has no runtime left after its required stop grace")
    validate_grant(grant, original_budgets=original)
    grants = dict(previous["grants"], **{phase: grant})
    if any(sum(item["limits"][key] for item in grants.values()) > original[key] for key in _SHARED):
        raise _invalid("Helper reservations exceed the admitted operation budget")
    state = dict(previous, grants=grants, last_boottime_ns=now["boottime_ns"])
    return state, grant
