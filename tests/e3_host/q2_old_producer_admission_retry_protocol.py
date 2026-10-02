"""Offline arithmetic contracts for the single old-producer retry channel.

All inputs are supplied data. No clocks, processes, files or peers are observed.
Ordered sample labels describe the approved sampling order, without proving an
actual sampling event. Arithmetic consistency cannot qualify H07 or authorize
any field action.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re


HANDSHAKE_SCHEMA = "local-hand-q2-old-producer-admission-retry-handshake/v1"
WINDOW_SCHEMA = "local-hand-q2-old-producer-admission-retry-window-arithmetic/v1"
OWNER_SCHEMA = "local-hand-q2-old-producer-admission-retry-owner-deadline/v1"
NS = 10**9
INTEGER_LIMIT = 2**63 - 1
OUTER_NS = 300 * NS
PREPARATION_NS = 150 * NS
OWNER_NS = 120 * NS
FLOOR_NS = 1000000
MARGIN_NS = 2 * NS
WINDOW_FIELDS = (
    "boottime_issued_ns", "monotonic_issued_ns",
    "boottime_outer_deadline_ns", "monotonic_outer_deadline_ns",
    "boottime_preparation_deadline_ns", "monotonic_preparation_deadline_ns",
)
HELLO_FIELDS = ("schema", "kind", "guest_boot_id", "hello_boottime_ns", "nonce")
RESERVE_FIELDS = ("stop_ns", "eof_ns", "fsync_ns", "seal_ns")
FLAGS = dict(field_ready=False, allow_run=False, arithmetic_only=True)


def _require(condition, reason):
    if not condition:
        raise ValueError("Q2_RETRY_PROTOCOL_" + reason)


def _keys(value, names, reason):
    _require(type(value) is dict and set(value) == set(names), reason)


def _number(value, *, minimum=1):
    _require(type(value) is int and minimum <= value <= INTEGER_LIMIT, "INTEGER")
    return value


def _add(left, right):
    _require(left <= INTEGER_LIMIT - right, "OVERFLOW")
    return left + right


def _digest(value):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        "DIGEST")
    return value


def _boot(value):
    _require(type(value) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value) is not None,
        "BOOT_FORMAT")
    return value


def _same(value, expected):
    if type(value) is not type(expected):
        return False
    if type(expected) is dict:
        return set(value) == set(expected) and all(
            _same(value[name], expected[name]) for name in expected)
    if type(expected) is list:
        return len(value) == len(expected) and all(
            _same(item, wanted) for item, wanted in zip(value, expected))
    return value == expected


def _sha(value):
    # Only internally validated, shallow protocol objects reach serialization.
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
    return hashlib.sha256(raw).hexdigest()


def _window(value):
    _keys(value, WINDOW_FIELDS, "WINDOW_FIELDS")
    for name in WINDOW_FIELDS:
        _number(value[name])
    for clock in ("boottime", "monotonic"):
        issued = value[clock + "_issued_ns"]
        _require(value[clock + "_outer_deadline_ns"] == _add(issued, OUTER_NS)
            and value[clock + "_preparation_deadline_ns"] == _add(issued, PREPARATION_NS),
            "WINDOW_DEADLINES")
    return copy.deepcopy(value)


def validate_window(window):
    """Validate the six supplied fields, without observing anchor order/time."""
    return dict(schema=WINDOW_SCHEMA, window=_window(window), **FLAGS)


def _hello(value, expected_guest_boot_id):
    _keys(value, HELLO_FIELDS, "HELLO_FIELDS")
    _require(value["schema"] == HANDSHAKE_SCHEMA and value["kind"] == "HELLO",
        "HELLO_SCHEMA")
    _require(_boot(value["guest_boot_id"]) == _boot(expected_guest_boot_id),
        "GUEST_BOOT_CHANGED")
    _number(value["hello_boottime_ns"])
    _digest(value["nonce"])
    return copy.deepcopy(value)


def _sample(value):
    _require(type(value) is list and len(value) == 2, "SAMPLE_ORDER")
    result = {}
    for item, name in zip(value, ("CLOCK_MONOTONIC", "CLOCK_BOOTTIME")):
        _require(type(item) is list and len(item) == 2 and item[0] == name,
            "SAMPLE_ORDER")
        result[name] = _number(item[1])
    return result


def _guard(window, sample, previous):
    for name, clock in (("CLOCK_MONOTONIC", "monotonic"),
                        ("CLOCK_BOOTTIME", "boottime")):
        _require(sample[name] >= previous[name], "CLOCK_ROLLBACK")
        _require(sample[name] < window[clock + "_preparation_deadline_ns"]
            and sample[name] < window[clock + "_outer_deadline_ns"], "WINDOW_EXPIRED")
    mono_elapsed = sample["CLOCK_MONOTONIC"] - window["monotonic_issued_ns"]
    boot_elapsed = sample["CLOCK_BOOTTIME"] - window["boottime_issued_ns"]
    _require(abs(boot_elapsed - mono_elapsed) <= MARGIN_NS, "CLOCK_DIVERGED")


def make_bind(window, hello, received, before_bind, *, expected_guest_boot_id,
              intent_sha256, package_sha256):
    """Recompute the approved conservative mapping using each machine's clock.

    Guest absolute deadlines use the HELLO guest origin. Host samples are only
    subtracted from host deadlines; their numerical values are never compared
    with guest clock values. A current guest check belongs to READY.
    """
    window = _window(window)
    hello = _hello(hello, expected_guest_boot_id)
    intent_sha256, package_sha256 = _digest(intent_sha256), _digest(package_sha256)
    at_receive, at_bind = _sample(received), _sample(before_bind)
    origin = {"CLOCK_MONOTONIC": window["monotonic_issued_ns"],
        "CLOCK_BOOTTIME": window["boottime_issued_ns"]}
    _guard(window, at_receive, origin)
    _guard(window, at_bind, at_receive)
    values = {}
    for purpose in ("outer", "preparation"):
        raw = min(window["monotonic_" + purpose + "_deadline_ns"]
                  - at_receive["CLOCK_MONOTONIC"],
                  window["boottime_" + purpose + "_deadline_ns"]
                  - at_receive["CLOCK_BOOTTIME"])
        duration = raw // FLOOR_NS * FLOOR_NS - MARGIN_NS
        _require(duration > 0, "DURATION_EXHAUSTED")
        values["raw_" + purpose + "_ns"] = raw
        values["duration_" + purpose + "_ns"] = duration
        values["guest_" + purpose + "_deadline_ns"] = _add(
            hello["hello_boottime_ns"], duration)
    return dict(schema=HANDSHAKE_SCHEMA, kind="BIND",
        guest_boot_id=hello["guest_boot_id"], nonce=hello["nonce"],
        hello_sha256=_sha(hello), window_sha256=_sha(window),
        host_hello_received_samples=copy.deepcopy(received),
        host_before_bind_samples=copy.deepcopy(before_bind),
        floor_unit_ns=FLOOR_NS, sampling_margin_ns=MARGIN_NS,
        intent_sha256=intent_sha256, package_sha256=package_sha256, **values, **FLAGS)


def validate_bind(bind, window, hello, received, before_bind, *, expected_guest_boot_id,
                  intent_sha256, package_sha256):
    """Require exact recomputation against external inputs and expected pins."""
    expected = make_bind(window, hello, received, before_bind,
        expected_guest_boot_id=expected_guest_boot_id, intent_sha256=intent_sha256,
        package_sha256=package_sha256)
    _require(_same(bind, expected), "BIND_MISMATCH")
    return expected


def validate_ready(ready, bind, hello, *, window, received, before_bind,
                   expected_guest_boot_id, intent_sha256, package_sha256):
    """Validate a supplied guest READY and its same-origin current-time check."""
    bind = validate_bind(bind, window, hello, received, before_bind,
        expected_guest_boot_id=expected_guest_boot_id, intent_sha256=intent_sha256,
        package_sha256=package_sha256)
    _keys(ready, ("schema", "kind", "guest_boot_id", "nonce", "hello_sha256",
        "bind_sha256", "guest_outer_deadline_ns", "guest_preparation_deadline_ns",
        "ready_boottime_ns", "field_ready", "allow_run", "arithmetic_only"), "READY_FIELDS")
    now = _number(ready["ready_boottime_ns"])
    _require(hello["hello_boottime_ns"] <= now, "GUEST_CLOCK_ROLLBACK")
    _require(now < bind["guest_outer_deadline_ns"]
        and now < bind["guest_preparation_deadline_ns"], "READY_EXPIRED")
    expected = dict(schema=HANDSHAKE_SCHEMA, kind="READY",
        guest_boot_id=bind["guest_boot_id"], nonce=bind["nonce"],
        hello_sha256=bind["hello_sha256"], bind_sha256=_sha(bind),
        guest_outer_deadline_ns=bind["guest_outer_deadline_ns"],
        guest_preparation_deadline_ns=bind["guest_preparation_deadline_ns"],
        ready_boottime_ns=now, **FLAGS)
    _require(_same(ready, expected), "READY_MISMATCH")
    return expected


def owner_deadline(owner_now, outer_deadline, reserves, other_deadlines):
    """Retain the 120s owner maximum and every separately supplied reserve.

    All numbers belong to the same guest BOOTTIME domain. This does not prove
    that supplied reserves are adequate or that any remote process has stopped.
    """
    _number(owner_now)
    _number(outer_deadline)
    _keys(reserves, RESERVE_FIELDS, "RESERVE_FIELDS")
    total = 0
    for name in RESERVE_FIELDS:
        total = _add(total, _number(reserves[name]))
    _require(type(other_deadlines) is list and len(other_deadlines) <= 32,
        "OTHER_DEADLINES")
    for deadline in other_deadlines:
        _number(deadline)
    maximum = _add(owner_now, OWNER_NS)
    _require(outer_deadline > total, "OWNER_BUDGET_EXHAUSTED")
    after_reserves = outer_deadline - total
    deadline = min(maximum, after_reserves, *other_deadlines)
    _require(deadline > owner_now, "OWNER_BUDGET_EXHAUSTED")
    return dict(schema=OWNER_SCHEMA, owner_now_ns=owner_now,
        outer_deadline_ns=outer_deadline, reserves=copy.deepcopy(reserves),
        other_deadlines=copy.deepcopy(other_deadlines), owner_limit_ns=OWNER_NS,
        owner_limit_deadline_ns=maximum, outer_after_reserves_ns=after_reserves,
        owner_deadline_ns=deadline, **FLAGS)
