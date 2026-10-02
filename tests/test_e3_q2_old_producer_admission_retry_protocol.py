"""Synthetic deadline, ordering and identity adversaries for offline mapping."""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json

import pytest

from e3_host import q2_old_producer_admission_retry_protocol as m


BOOT = "11111111-2222-3333-4444-555555555555"
INTENT = "b" * 64
PACKAGE = "c" * 64


@pytest.fixture
def inputs():
    return dict(
        window={
            "boottime_issued_ns": 10 * m.NS,
            "monotonic_issued_ns": 20 * m.NS,
            "boottime_outer_deadline_ns": 310 * m.NS,
            "monotonic_outer_deadline_ns": 320 * m.NS,
            "boottime_preparation_deadline_ns": 160 * m.NS,
            "monotonic_preparation_deadline_ns": 170 * m.NS,
        },
        hello=dict(schema=m.HANDSHAKE_SCHEMA, kind="HELLO", guest_boot_id=BOOT,
            hello_boottime_ns=700 * m.NS, nonce="a" * 64),
        received=[["CLOCK_MONOTONIC", 25 * m.NS + 1234567],
            ["CLOCK_BOOTTIME", 15 * m.NS + 1234567]],
        before_bind=[["CLOCK_MONOTONIC", 26 * m.NS],
            ["CLOCK_BOOTTIME", 16 * m.NS]],
        expected_guest_boot_id=BOOT, intent_sha256=INTENT, package_sha256=PACKAGE,
    )


def canonical_digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
    return hashlib.sha256(raw).hexdigest()


def ready_for(bind, *, now):
    return dict(schema=m.HANDSHAKE_SCHEMA, kind="READY",
        guest_boot_id=bind["guest_boot_id"], nonce=bind["nonce"],
        hello_sha256=bind["hello_sha256"], bind_sha256=canonical_digest(bind),
        guest_outer_deadline_ns=bind["guest_outer_deadline_ns"],
        guest_preparation_deadline_ns=bind["guest_preparation_deadline_ns"],
        ready_boottime_ns=now, field_ready=False, allow_run=False, arithmetic_only=True)


def validate_ready(ready, bind, inputs):
    return m.validate_ready(ready, bind, inputs["hello"], window=inputs["window"],
        received=inputs["received"], before_bind=inputs["before_bind"],
        expected_guest_boot_id=inputs["expected_guest_boot_id"],
        intent_sha256=inputs["intent_sha256"], package_sha256=inputs["package_sha256"])


def test_exact_mapping_rounds_down_before_margin_and_keeps_distinct_origins(inputs):
    original = copy.deepcopy(inputs)
    bind = m.make_bind(**inputs)

    assert bind["raw_preparation_ns"] == 145 * m.NS - 1234567
    assert bind["duration_preparation_ns"] == 142998000000
    assert bind["raw_outer_ns"] == 295 * m.NS - 1234567
    assert bind["duration_outer_ns"] == 292998000000
    assert bind["guest_preparation_deadline_ns"] == 842998000000
    assert bind["guest_outer_deadline_ns"] == 992998000000
    assert bind["hello_sha256"] == canonical_digest(inputs["hello"])
    assert bind["window_sha256"] == canonical_digest(inputs["window"])
    assert bind["host_hello_received_samples"] == inputs["received"]
    assert bind["host_before_bind_samples"] == inputs["before_bind"]
    assert bind["floor_unit_ns"] == 1000000
    assert bind["sampling_margin_ns"] == 2000000000
    assert bind["intent_sha256"] == INTENT
    assert bind["package_sha256"] == PACKAGE
    assert m.validate_bind(bind, **inputs) == bind
    assert bind["field_ready"] is False and bind["allow_run"] is False
    assert bind["arithmetic_only"] is True
    assert inputs == original
    bind["host_hello_received_samples"][0][1] = 1
    assert inputs == original


def test_guest_and_host_numeric_origins_are_never_compared(inputs):
    inputs["hello"]["hello_boottime_ns"] = 1
    bind = m.make_bind(**inputs)
    ready = ready_for(bind, now=2)
    assert validate_ready(ready, bind, inputs) == ready
    assert ready["field_ready"] is False and ready["allow_run"] is False


def test_each_clock_uses_its_earlier_remainder_and_divergence_boundary(inputs):
    inputs["received"] = [["CLOCK_MONOTONIC", 25 * m.NS],
        ["CLOCK_BOOTTIME", 17 * m.NS]]
    inputs["before_bind"] = [["CLOCK_MONOTONIC", 26 * m.NS],
        ["CLOCK_BOOTTIME", 18 * m.NS]]
    bind = m.make_bind(**inputs)
    assert bind["raw_preparation_ns"] == 143 * m.NS
    assert bind["duration_preparation_ns"] == 141 * m.NS


@pytest.mark.parametrize(("remaining", "accepted", "duration"), [
    (2000000000, False, None),
    (2000999999, False, None),
    (2001000000, True, 1000000),
])
def test_floor_and_margin_boundary_is_strict(inputs, remaining, accepted, duration):
    mono = inputs["window"]["monotonic_preparation_deadline_ns"] - remaining
    boot = inputs["window"]["boottime_preparation_deadline_ns"] - remaining
    inputs["received"] = [["CLOCK_MONOTONIC", mono], ["CLOCK_BOOTTIME", boot]]
    inputs["before_bind"] = [["CLOCK_MONOTONIC", mono + 1], ["CLOCK_BOOTTIME", boot + 1]]
    if not accepted:
        with pytest.raises(ValueError, match="DURATION_EXHAUSTED"):
            m.make_bind(**inputs)
    else:
        assert m.make_bind(**inputs)["duration_preparation_ns"] == duration


def test_window_validation_retains_exact_input_and_false_readiness(inputs):
    result = m.validate_window(inputs["window"])
    assert result["window"] == inputs["window"]
    assert result["field_ready"] is False and result["allow_run"] is False
    assert result["arithmetic_only"] is True
    result["window"]["boottime_issued_ns"] = 1
    assert inputs["window"]["boottime_issued_ns"] == 10 * m.NS


@pytest.mark.parametrize(("field", "value"), [
    ("extra", 1), ("boottime_issued_ns", True),
    ("monotonic_issued_ns", -1), ("boottime_outer_deadline_ns", 310 * m.NS + 1),
    ("monotonic_preparation_deadline_ns", m.INTEGER_LIMIT + 1),
])
def test_malformed_window_is_rejected(inputs, field, value):
    inputs["window"][field] = value
    with pytest.raises(ValueError):
        m.make_bind(**inputs)


def test_window_addition_must_fit_signed_integer_range(inputs):
    inputs["window"]["boottime_issued_ns"] = m.INTEGER_LIMIT
    with pytest.raises(ValueError, match="OVERFLOW"):
        m.validate_window(inputs["window"])


@pytest.mark.parametrize(("field", "value"), [
    ("schema", "local-hand-q2-host-window-binding/v1"), ("kind", "READY"),
    ("guest_boot_id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
    ("guest_boot_id", "11111111-2222-3333-4444-55555555555A"), ("nonce", "a" * 63),
    ("nonce", "A" * 64), ("hello_boottime_ns", True),
    ("hello_boottime_ns", 0), ("hello_boottime_ns", m.INTEGER_LIMIT + 1),
    ("extra", 1),
])
def test_hello_is_strict_and_bound_to_expected_boot(inputs, field, value):
    inputs["hello"][field] = value
    with pytest.raises(ValueError):
        m.make_bind(**inputs)


@pytest.mark.parametrize("name", ["intent_sha256", "package_sha256"])
@pytest.mark.parametrize("value", [True, "", "a" * 63, "A" * 64])
def test_expected_digest_pins_are_strict(inputs, name, value):
    inputs[name] = value
    with pytest.raises(ValueError, match="DIGEST"):
        m.make_bind(**inputs)


@pytest.mark.parametrize("name", ["received", "before_bind"])
@pytest.mark.parametrize("sample", [
    [["CLOCK_BOOTTIME", 15 * m.NS], ["CLOCK_MONOTONIC", 25 * m.NS]],
    [["CLOCK_MONOTONIC", 25 * m.NS], ["CLOCK_MONOTONIC", 15 * m.NS]],
    [["CLOCK_MONOTONIC", True], ["CLOCK_BOOTTIME", 15 * m.NS]],
    [["CLOCK_MONOTONIC", 25 * m.NS]],
    (("CLOCK_MONOTONIC", 25 * m.NS), ("CLOCK_BOOTTIME", 15 * m.NS)),
])
def test_samples_require_exact_order_and_integer_shape(inputs, name, sample):
    inputs[name] = sample
    with pytest.raises(ValueError):
        m.make_bind(**inputs)


@pytest.mark.parametrize(("name", "clock_index", "value", "reason"), [
    ("received", 0, 20 * m.NS - 1, "CLOCK_ROLLBACK"),
    ("before_bind", 1, 15 * m.NS, "CLOCK_ROLLBACK"),
    ("received", 0, 170 * m.NS, "WINDOW_EXPIRED"),
    ("before_bind", 1, 160 * m.NS, "WINDOW_EXPIRED"),
    ("received", 1, 18 * m.NS, "CLOCK_DIVERGED"),
    ("before_bind", 1, 19 * m.NS, "CLOCK_DIVERGED"),
])
def test_before_bind_guard_blocks_clock_races(inputs, name, clock_index, value, reason):
    inputs[name][clock_index][1] = value
    with pytest.raises(ValueError, match=reason):
        m.make_bind(**inputs)


@pytest.mark.parametrize(("field", "value"), [
    ("schema", "old/v1"), ("kind", "HELLO"), ("nonce", "d" * 64),
    ("guest_boot_id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
    ("hello_sha256", "d" * 64), ("window_sha256", "d" * 64),
    ("intent_sha256", "d" * 64), ("package_sha256", "d" * 64),
    ("floor_unit_ns", 1), ("sampling_margin_ns", 0),
    ("raw_outer_ns", True), ("duration_preparation_ns", 1),
    ("guest_outer_deadline_ns", 1), ("field_ready", True),
    ("allow_run", True), ("arithmetic_only", 1), ("extra", 1),
])
def test_bind_is_recomputed_against_external_inputs(inputs, field, value):
    bind = m.make_bind(**inputs)
    bind[field] = value
    with pytest.raises(ValueError, match="BIND_MISMATCH"):
        m.validate_bind(bind, **inputs)


def test_bind_cannot_refresh_original_window_or_replace_external_pins(inputs):
    bind = m.make_bind(**inputs)
    inputs["received"][0][1] += 1
    with pytest.raises(ValueError, match="BIND_MISMATCH"):
        m.validate_bind(bind, **inputs)


def test_guest_deadline_addition_must_not_overflow(inputs):
    inputs["hello"]["hello_boottime_ns"] = m.INTEGER_LIMIT
    with pytest.raises(ValueError, match="OVERFLOW"):
        m.make_bind(**inputs)


@pytest.mark.parametrize(("field", "value"), [
    ("schema", "old/v1"), ("kind", "BIND"), ("nonce", "d" * 64),
    ("guest_boot_id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
    ("hello_sha256", "d" * 64), ("bind_sha256", "d" * 64),
    ("guest_outer_deadline_ns", 1), ("guest_preparation_deadline_ns", 1),
    ("field_ready", True), ("allow_run", True), ("arithmetic_only", 1),
    ("ready_boottime_ns", True), ("extra", 1),
])
def test_ready_binds_hello_bind_and_all_deadlines(inputs, field, value):
    bind = m.make_bind(**inputs)
    ready = ready_for(bind, now=inputs["hello"]["hello_boottime_ns"] + 1)
    ready[field] = value
    with pytest.raises(ValueError):
        validate_ready(ready, bind, inputs)


@pytest.mark.parametrize("boundary", ["hello", "preparation", "outer"])
def test_ready_refuses_guest_rollback_and_either_deadline_equality(inputs, boundary):
    bind = m.make_bind(**inputs)
    now = (inputs["hello"]["hello_boottime_ns"] - 1 if boundary == "hello"
        else bind["guest_" + boundary + "_deadline_ns"])
    ready = ready_for(bind, now=now)
    with pytest.raises(ValueError, match="GUEST_CLOCK_ROLLBACK|READY_EXPIRED"):
        validate_ready(ready, bind, inputs)


def test_ready_accepts_exact_hello_origin_and_last_nanosecond_before_deadline(inputs):
    bind = m.make_bind(**inputs)
    for now in (inputs["hello"]["hello_boottime_ns"],
                bind["guest_preparation_deadline_ns"] - 1):
        ready = ready_for(bind, now=now)
        assert validate_ready(ready, bind, inputs) == ready


def reserves():
    return dict(stop_ns=3 * m.NS, eof_ns=5 * m.NS, fsync_ns=7 * m.NS, seal_ns=11 * m.NS)


@pytest.mark.parametrize(("outer", "others", "expected"), [
    (500 * m.NS, [], 130 * m.NS),
    (150 * m.NS, [], 124 * m.NS),
    (500 * m.NS, [110 * m.NS, 90 * m.NS], 90 * m.NS),
])
def test_owner_preserves_original_maximum_and_each_reserve(outer, others, expected):
    result = m.owner_deadline(10 * m.NS, outer, reserves(), others)
    assert result["owner_deadline_ns"] == expected
    assert result["owner_limit_ns"] == 120 * m.NS
    assert result["outer_after_reserves_ns"] == outer - 26 * m.NS
    assert result["reserves"] == reserves()
    assert result["field_ready"] is False and result["allow_run"] is False


@pytest.mark.parametrize("name", ["stop_ns", "eof_ns", "fsync_ns", "seal_ns"])
@pytest.mark.parametrize("mutation", ["missing", "zero", "bool"])
def test_owner_reserves_cannot_be_omitted_or_disabled(name, mutation):
    values = reserves()
    if mutation == "missing":
        del values[name]
    else:
        values[name] = 0 if mutation == "zero" else True
    with pytest.raises(ValueError):
        m.owner_deadline(10 * m.NS, 500 * m.NS, values, [])


@pytest.mark.parametrize("outer", [26 * m.NS, 36 * m.NS, 36 * m.NS - 1])
def test_owner_refuses_exhausted_reserve_budget(outer):
    with pytest.raises(ValueError, match="OWNER_BUDGET_EXHAUSTED"):
        m.owner_deadline(10 * m.NS, outer, reserves(), [])


@pytest.mark.parametrize("others", [[10 * m.NS], [True], [0], tuple(), [1] * 33])
def test_owner_other_deadlines_are_bounded_and_cannot_allow_expired_run(others):
    with pytest.raises(ValueError):
        m.owner_deadline(10 * m.NS, 500 * m.NS, reserves(), others)


def test_owner_integer_addition_and_reserve_sum_are_bounded():
    with pytest.raises(ValueError, match="OVERFLOW"):
        m.owner_deadline(m.INTEGER_LIMIT, m.INTEGER_LIMIT, reserves(), [])
    values = reserves()
    values["stop_ns"] = m.INTEGER_LIMIT
    with pytest.raises(ValueError, match="OVERFLOW"):
        m.owner_deadline(1, m.INTEGER_LIMIT, values, [])


def test_protocol_has_no_observation_process_or_field_activation_primitive():
    tree = ast.parse(inspect.getsource(m))
    forbidden_names = {"open", "exec", "eval", "time", "os", "subprocess", "socket"}
    assert not any(isinstance(node, ast.Name) and node.id in forbidden_names
        for node in ast.walk(tree))
    imports = {node.name for item in ast.walk(tree) if isinstance(item, ast.Import)
        for node in item.names}
    assert imports == {"copy", "hashlib", "json", "re"}
