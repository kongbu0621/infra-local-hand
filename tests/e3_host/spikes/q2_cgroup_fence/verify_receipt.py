"""Bounded, offline verifier for the separately approved H07 laboratory receipts.

This module grants no execution authority and does not attest a hostile collector.
It independently derives fixture predicates from the retained original event and
stream records; aggregate success booleans never substitute for missing facts.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

MAX_REPORT = 2 * 1024 * 1024
APPROVED_A = "71c7e842c724650a0e949a63bb898699b41107be"
CLOSURE_C = "8deeed492edeb7e5fa79cbe95c123a27e69f9f92"
APPROVED_CONTINUATION_A = "a08a5055c35009a896ad6c6059d709758cc78436"
CLOSURE_CONTINUATION_C = "7d33c698ff6c1bf34733ee2429d0404ace2abd55"
SOURCE_DIR = "tests/e3_host/spikes/q2_cgroup_fence/"
DOCUMENT_DIR = "docs/a2-execution/q2-h07-cgroup-fence-spike/"
DOCUMENT_HASHES = {
    "REQUIREMENTS.md": "41706c5b07cfceea319f10dcab1fcc8b2606995b029566f3e13bb00e41affd51",
    "ARCHITECTURE.md": "6b7ef2487658e759df565084393e5de010db8f35de4966a4790320eea060116c",
    "IMPLEMENTATION_PLAN.md": "0bd3dab26e10e2fa9717ef218fa70846cf5ad3b5888ad2f17596c7b7b385e99d",
}
REQUIRED_SOURCE_PATHS = {
    SOURCE_DIR + "helper.c", SOURCE_DIR + "run_fixture.py", SOURCE_DIR + "verify_receipt.py",
    ".github/workflows/q2-cgroup-fence-spike.yml", "AGENTS.md",
    "docs/governance/Q2_H07_CGROUP_FENCE_SPIKE_OWNER_DECISION.md",
} | {DOCUMENT_DIR + name for name in DOCUMENT_HASHES}
CONTINUATION_DOCUMENT_DIR = "docs/a2-execution/q2-h07-r1-continuation/"
CONTINUATION_DOCUMENT_HASHES = {
    "REQUIREMENTS.md": "74ad594f4446cdf49c4b8d72ff4e5ffb3bd411780e91eeee5a130e58d03eb7f2",
    "ARCHITECTURE.md": "18a248d9398f73405e8836a9586e9c98b8ed9aab2c71242ecdc1c8eaa3823e2b",
    "IMPLEMENTATION_PLAN.md": "9c5726f80f4cb779f658b4d075ee50568ff9818b9f49814e57de71c07aedbe2b",
}
REQUIRED_CONTINUATION_SOURCE_PATHS = REQUIRED_SOURCE_PATHS | {
    SOURCE_DIR + name for name in (
        "account_evidence.py", "test_account_evidence.py", "continuation.py",
        "test_continuation.py", "test_fixture_admission.py", "test_verify_receipt.py")
} | {CONTINUATION_DOCUMENT_DIR + name for name in CONTINUATION_DOCUMENT_HASHES} | {
    "docs/governance/Q2_H07_R1_CONTINUATION_OWNER_DECISION.md",
    "docs/governance/Q2_H07_R1_CONTINUATION_BASELINE.md",
    "docs/a2-execution/evidence/q2-h07-cgroup-fence-spike/round-1-verification.json",
    "docs/a2-execution/evidence/q2-h07-cgroup-fence-spike/round-1-repair-ci.json",
}
LIMITS = {
    "prep_seconds": 120, "cases_seconds": 180, "cleanup_seconds": 30,
    "case_seconds": 20, "stop_seconds": 3,
    "E_memory_bytes": 134217728, "G_memory_bytes": 67108864,
    "B_memory_bytes": 67108864, "E_pids": 32, "G_pids": 4, "B_pids": 16,
    "cpu_max": "100000 100000", "swap_bytes": 0,
    "case_stream_bytes": 131072, "suite_stream_bytes": 786432,
    "diagnostic_bytes": 262144, "report_bytes": MAX_REPORT,
    "file_logical_bytes": 33554432, "file_count": 128,
}
STATUSES = {"QUALIFIED_IN_FIXTURE", "UNSUPPORTED", "UNKNOWN_RETAINED",
            "INCONCLUSIVE", "REJECTED"}
EVENTS = {
    "g_created", "g_armed", "s_created", "s_armed", "request_sent",
    "request_received", "worker_created", "worker_identity", "worker_pidfd",
    "worker_exit", "close_requested", "s_exit", "b_empty", "streams_eof",
    "control_eof", "fenced", "g_summary", "barrier_ready", "lost_reply",
    "s_crash", "streams_held", "burst_ready", "burst_at_close", "g_crash",
    "late_attempt", "late_rejected", "t_g_exit", "t_cleanup",
    "stream_originals", "probe_clone", "probe_seccomp", "probe_denial",
    "probe_kill", "probe_exit", "probe_cleanup", "protocol_rejected",
    "worker_request", "t_cleanup_verified", "t_b_empty", "t_streams_eof", "late_send_result",
    "native_error", "protocol_error", "b_kill", "probe_armed", "probe_ready",
    "probe_created", "t_probe_exit", "clone_error", "group_error",
    "probe_capabilities",
    "worker_receipt", "payload_started", "payload_confirmed",
    "s_credentials", "s_capabilities", "s_restrictions",
    "e_identity", "g_identity", "b_identity", "s_identity", "w_identity",
}
NATIVE_KEYS = {
    "schema_version", "kind", "case_id", "status", "reason", "start_mono_ns",
    "start_boot_ns", "end_mono_ns", "end_boot_ns", "events",
    "guardian_pidfd_exit", "guardian_wait_code", "guardian_stream_eof",
    "tree_empty", "streams", "cleanup_attempted", "cleanup_verified",
    "deadline_met", "output_exceeded",
}
TOP_KEYS = {"schema_version", "source", "run", "provenance", "limits",
            "capability", "cases", "cleanup", "status", "budget", "reason"}
TOP_V2_KEYS = TOP_KEYS | {"account_setup", "continuation"}
SOURCE_KEYS = {"expected_commit", "github_sha", "head", "closure_sha256", "approved_A", "closure_C"}
SOURCE_V2_KEYS = SOURCE_KEYS | {"approved_continuation_A", "closure_continuation_C"}


class ReceiptError(ValueError):
    """Malformed or over-budget input, rather than an experimental verdict."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_report(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_REPORT:
        raise ReceiptError("report byte limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               ReceiptError("non-finite JSON constant")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ReceiptError("invalid or truncated JSON") from exc
    _bounded(value)
    if not isinstance(value, dict):
        raise ReceiptError("report must be an object")
    return value


def _bounded(value: Any) -> None:
    todo = [(value, 0)]
    count = 0
    while todo:
        item, depth = todo.pop()
        count += 1
        if depth > 24 or count > 40000:
            raise ReceiptError("report structure limit")
        if isinstance(item, dict):
            if any(not isinstance(k, str) for k in item):
                raise ReceiptError("non-string object key")
            todo.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            todo.extend((v, depth + 1) for v in item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise ReceiptError("non-finite number")
        elif not isinstance(item, (str, int, float, bool, type(None))):
            raise ReceiptError("not a JSON value")


def _integer(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= 2**63 - 1


def _wait_code(value: Any) -> bool:
    return type(value) is int and -64 <= value <= 255


def _number(value: Any) -> bool:
    return type(value) in (int, float) and 0 <= value <= 2**63 - 1 and math.isfinite(value)


def _hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None


def _shape(value: Any, keys: set[str], at: str, errors: list[str],
           optional: set[str] | None = None) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{at}: object required")
        return False
    missing = keys - value.keys()
    extra = value.keys() - keys - (optional or set())
    if missing or extra:
        errors.append(f"{at}: missing={sorted(missing)} extra={sorted(extra)}")
    return not missing and not extra


def validate_native(receipt: Any) -> list[str]:
    errors: list[str] = []
    if not _shape(receipt, NATIVE_KEYS, "native", errors):
        return errors
    r = receipt
    if type(r["schema_version"]) is not int or r["schema_version"] != 1:
        errors.append("native: schema version")
    if r["kind"] not in ("probe", "case") or r["case_id"] not in (
            "PROBE", "C1", "C2", "C3", "C4", "C5", "C6"):
        errors.append("native: case identity")
    if (r["kind"] == "probe") != (r["case_id"] == "PROBE"):
        errors.append("native: kind/case mismatch")
    if r["status"] not in ("OBSERVED", "UNSUPPORTED", "UNKNOWN_RETAINED"):
        errors.append("native: status")
    if not isinstance(r["reason"], str) or len(r["reason"]) > 4096:
        errors.append("native: reason")
    for key in ("guardian_pidfd_exit", "guardian_stream_eof", "tree_empty",
                "cleanup_attempted", "cleanup_verified", "deadline_met", "output_exceeded"):
        if type(r[key]) is not bool:
            errors.append(f"native: {key} is not bool")
    if r["guardian_wait_code"] is not None and not _wait_code(r["guardian_wait_code"]):
        errors.append("native: guardian wait code")
    clocks = ("start_mono_ns", "start_boot_ns", "end_mono_ns", "end_boot_ns")
    valid_clocks = all(_integer(r[k]) for k in clocks)
    if not valid_clocks:
        errors.append("native: clock integer")
    elif any(r[f"end_{clock}_ns"] < r[f"start_{clock}_ns"] for clock in ("mono", "boot")):
        errors.append("native: clock regression")
    elif r["deadline_met"] and any(r[f"end_{c}_ns"] - r[f"start_{c}_ns"] > 20_000_000_000
                                    for c in ("mono", "boot")):
        errors.append("native: falsely asserted deadline")
    total = 0
    if _shape(r["streams"], {"stdout", "stderr"}, "streams", errors):
        for name, stream in r["streams"].items():
            if not _shape(stream, {"bytes", "data_base64", "eof"}, name, errors):
                continue
            if not _integer(stream["bytes"]) or type(stream["eof"]) is not bool:
                errors.append(f"{name}: byte count/EOF")
                continue
            try:
                raw = base64.b64decode(stream["data_base64"], validate=True)
            except (ValueError, TypeError, binascii.Error):
                errors.append(f"{name}: invalid base64")
                continue
            if len(raw) != stream["bytes"]:
                errors.append(f"{name}: stream length mismatch")
            total += len(raw)
    if total > 131072:
        errors.append("native: stream budget")
    events = r["events"]
    if not isinstance(events, list) or len(events) > 256:
        errors.append("native: event count")
        return errors
    for index, event in enumerate(events, 1):
        if not _shape(event, {"event", "seq", "mono_ns", "boot_ns", "a", "b", "c"},
                      f"event {index}", errors):
            continue
        if not isinstance(event["event"], str) or event["event"] not in EVENTS:
            errors.append(f"event {index}: unknown event")
        if type(event["seq"]) is not int or event["seq"] != index:
            errors.append(f"event {index}: duplicate, missing or reordered sequence")
        if (any(not _integer(event[k]) for k in ("mono_ns", "boot_ns")) or
                any(not _integer(event[k], -(2**63) + 1) for k in ("a", "b", "c"))):
            errors.append(f"event {index}: integer fields")
            continue
        if valid_clocks and any(not r[f"start_{c}_ns"] <= event[f"{c}_ns"] <= r[f"end_{c}_ns"]
                                for c in ("mono", "boot")):
            errors.append(f"event {index}: clock outside retained case")
    # Event clocks can precede an earlier-appended message from another process;
    # the single collector sequence is not falsely equated with global causality.
    return errors


def derive_case(receipt: dict[str, Any]) -> dict[str, Any]:
    errors = validate_native(receipt)
    out: dict[str, Any] = {
        "case_id": receipt.get("case_id"), "case_expectation_met": False,
        "fence_observed": False, "identity_complete": None, "tree_empty": None,
        "streams_eof": None, "guardian_exit_observed": None,
        "deadline_met": None, "cleanup_verified": None,
        "classification": "UNKNOWN_RETAINED", "errors": errors,
    }
    if errors:
        return out
    r = receipt
    events = r["events"]
    by_name = {name: [e for e in events if e["event"] == name] for name in EVENTS}
    one = lambda name: len(by_name[name]) == 1
    get = lambda name: by_name[name][0] if one(name) else None
    before = lambda first, second: bool(get(first) and get(second) and
        all(get(first)[f"{c}_ns"] <= get(second)[f"{c}_ns"] for c in ("mono", "boot")))
    final = get("t_cleanup_verified")
    out["cleanup_verified"] = bool(r["cleanup_verified"] and r["tree_empty"] and final and
                                    (final["a"], final["b"], final["c"]) == (1, 1, 1))
    out["tree_empty"] = r["tree_empty"] and (one("b_empty") or one("t_b_empty"))
    out["streams_eof"] = all(s["eof"] for s in r["streams"].values()) and (one("streams_eof") or one("t_streams_eof"))
    out["guardian_exit_observed"] = (r["guardian_pidfd_exit"] and r["guardian_stream_eof"]
                                      and r["guardian_wait_code"] is not None and one("t_g_exit") and
                                      get("t_g_exit")["a"] == r["guardian_wait_code"] and
                                      get("t_g_exit")["b"] == 1)
    arm = get("g_armed")
    deadline = bool(arm and arm["a"] == arm["mono_ns"] + 20_000_000_000 and
                    arm["b"] == arm["boot_ns"] + 20_000_000_000 and
                    arm["c"] == arm["mono_ns"] + 17_000_000_000 and
                    r["end_mono_ns"] <= arm["a"] and r["end_boot_ns"] <= arm["b"])
    out["deadline_met"] = deadline and r["deadline_met"]
    created = by_name["worker_created"]
    identities = by_name["worker_identity"]
    pidfds = by_name["worker_pidfd"]
    requests = by_name["request_sent"]
    req_ids = [e["a"] for e in requests]
    creator_ids = [e["a"] for e in created]
    received = by_name["request_received"]
    if len(requests) > 8 or len(set(req_ids)) != len(req_ids):
        errors.append("request identity/count")
    if len({e["a"] for e in received}) != len(received):
        errors.append("duplicate accepted request")
    if len(created) > 8 or len(set(creator_ids)) != len(creator_ids):
        errors.append("duplicate creation or descendant limit")
    worker_requests = by_name["worker_request"]
    if len(worker_requests) != len(created) or len({e["a"] for e in worker_requests}) != len(worker_requests):
        errors.append("worker/request binding cardinality")
    if any(e["c"] != 1 or e["b"] <= 0 for e in created):
        errors.append("creation lacks atomic placement")
    for create in created:
        bindings = [e for e in worker_requests if e["a"] == create["a"] and e["c"] == 1]
        if len(bindings) != 1:
            errors.append("missing worker/request binding")
            continue
        accepted = [e for e in received if e["a"] == bindings[0]["b"]]
        sent = [e for e in requests if e["a"] == bindings[0]["b"]]
        if len(accepted) != 1 or len(sent) != 1 or any(
                not sent[0][f"{c}_ns"] <= accepted[0][f"{c}_ns"] <= create[f"{c}_ns"]
                for c in ("mono", "boot")):
            errors.append("creation lacks causally preceding accepted request")
    if any(e["a"] not in creator_ids or e["b"] != 1 or e["c"] != 1 for e in pidfds):
        errors.append("invalid pidfd handoff/count")
    if len({e["a"] for e in pidfds}) != len(pidfds):
        errors.append("duplicate pidfd handoff")
    if any(e["a"] not in creator_ids or e["c"] != 1 or not any(
            c["a"] == e["a"] and c["b"] == e["b"] for c in created) for e in identities):
        errors.append("worker identity mismatch")
    identity_complete = (len(identities) == len(created) == len(pidfds) and
                         len({e["a"] for e in identities}) == len(identities))
    out["identity_complete"] = identity_complete
    close = get("close_requested")
    fence = get("fenced")
    if fence and any(any(e[f"{c}_ns"] > fence[f"{c}_ns"] for c in ("mono", "boot"))
                     for e in created):
        errors.append("creation after fence/no-reinjection violation")
    if close and any(any(e[f"{c}_ns"] > close[f"{c}_ns"] for c in ("mono", "boot"))
                     for e in received):
        errors.append("new request accepted after close")
    if arm and any(e["mono_ns"] >= arm["c"] or e["boot_ns"] >= arm["b"] - 3_000_000_000
                   for e in by_name["request_received"]):
        errors.append("request accepted after original cutoff")
    if any(len(by_name[n]) > 1 for n in ("g_created", "g_armed", "s_created", "s_armed",
                                        "close_requested", "fenced", "g_summary")):
        errors.append("rearming/reinjection/duplicate terminal event")
    if any(not any(s["a"] == e["a"] for s in requests) for e in by_name["request_received"]):
        errors.append("stale/unknown request received")
    originals = get("stream_originals")
    stream_binding = bool(originals and (originals["a"], originals["b"], originals["c"]) == (2, 1, 1))
    gcreate, screate, sarm = get("g_created"), get("s_created"), get("s_armed")
    credentials, capabilities, restrictions = (get(n) for n in (
        "s_credentials", "s_capabilities", "s_restrictions"))
    reduced = bool(credentials and credentials["a"] > 0 and credentials["b"] > 0 and
                   credentials["c"] == 1 and capabilities and
                   (capabilities["a"], capabilities["b"], capabilities["c"]) == (0, 0, 0) and
                   restrictions and (restrictions["a"], restrictions["b"], restrictions["c"]) == (1, 2, 1) and
                   all(e["mono_ns"] >= restrictions["mono_ns"] and e["boot_ns"] >= restrictions["boot_ns"]
                       for e in received))
    placement = bool(gcreate and screate and sarm and gcreate["a"] > 0 and
                     screate["a"] == sarm["a"] > 0 and gcreate["b"] == screate["b"] == 3 and
                     gcreate["c"] == screate["c"] == 1 and sarm["b"] > 0 and sarm["c"] == 2 and
                     reduced and credentials["a"] == sarm["b"] and
                     before("g_armed", "s_created") and
                     before("s_created", "s_armed"))
    closed = bool(placement and stream_binding and close and one("s_exit") and
                  one("control_eof") and out["tree_empty"] and out["streams_eof"] and
                  one("b_kill") and get("b_kill")["a"] == 1 and
                  get("s_exit")["b"] == 1 and _wait_code(get("s_exit")["a"]) and
                  one("b_empty") and get("b_empty")["a"] == 1 and
                  one("streams_eof") and get("streams_eof")["a"] == get("streams_eof")["b"] == 1 and
                  get("control_eof")["a"] == 1 and one("fenced") and get("fenced")["a"] == 1 and
                  before("close_requested", "fenced") and before("s_exit", "fenced") and
                  before("b_empty", "fenced") and before("streams_eof", "fenced") and
                  before("control_eof", "fenced") and before("fenced", "g_summary") and
                  before("g_summary", "t_g_exit"))
    out["fence_observed"] = closed
    summary = get("g_summary")
    if summary and (bool(summary["a"]) != identity_complete or
                    bool(summary["b"]) != closed or bool(summary["c"]) != out["deadline_met"]):
        errors.append("guardian summary contradicts retained independent facts")
    clean = bool(out["cleanup_verified"] and out["guardian_exit_observed"] and
                 out["deadline_met"] and not r["output_exceeded"])
    if any(by_name[name] for name in ("native_error", "protocol_error", "clone_error", "group_error")):
        errors.append("native failure retained")
    cid = r["case_id"]
    expected_status, expected_reason = {
        "C3": ("UNKNOWN_RETAINED", "expected_lost_identity"),
        "C6": ("UNKNOWN_RETAINED", "expected_guardian_loss"),
    }.get(cid, ("OBSERVED", "fixed_case_observed"))
    if (r["status"], r["reason"]) != (expected_status, expected_reason):
        errors.append("native status/reason is not this case's expected result")
    expected = False
    if cid == "C1":
        exits = by_name["worker_exit"]
        expected = bool(closed and identity_complete and len(created) == 2 and len(exits) == 2 and
                        {e["a"] for e in exits} == set(creator_ids) and
                        all(e["b"] == 0 and e["c"] == 1 for e in exits))
    elif cid == "C2":
        late = by_name["late_rejected"]
        expected = bool(closed and identity_complete and not created and
                        before("request_received", "barrier_ready") and
                        before("barrier_ready", "close_requested") and
                        before("close_requested", "late_attempt") and
                        one("late_send_result") and get("late_send_result")["c"] == 1 and
                        len(late) == 2 and {e["a"] for e in late} == {2, 9} and
                        {e["b"] for e in late} == {1, 2} and
                        all(e["c"] == 1 and e["mono_ns"] >= get("late_attempt")["mono_ns"] and
                            e["boot_ns"] >= get("late_attempt")["boot_ns"] for e in late))
    elif cid == "C3":
        expected = bool(closed and created and not identity_complete and one("lost_reply") and
                        before("lost_reply", "close_requested"))
        out["classification"] = "UNKNOWN_RETAINED"
    elif cid == "C4":
        expected = bool(closed and identity_complete and created and one("streams_held") and
                        one("payload_started") and one("payload_confirmed") and
                        get("payload_started")["a"] > 0 and get("payload_started")["b"] > 0 and
                        get("payload_started")["c"] == 1 and
                        get("payload_confirmed")["a"] == get("payload_confirmed")["b"] == 1 and
                        before("payload_started", "payload_confirmed") and before("payload_confirmed", "s_crash") and
                        before("worker_identity", "s_crash") and before("s_crash", "streams_held") and
                        before("streams_held", "close_requested") and
                        get("streams_held")["a"] == get("streams_held")["b"] == 1 and
                        get("streams_held")["c"] >= 1)
    elif cid == "C5":
        burst = get("burst_at_close") or get("burst_ready")
        prerequisite = bool(burst and close and burst["a"] >= 1 and burst["b"] == 1 and
                            1 <= burst["c"] <= 7 and burst["a"] + burst["c"] <= 8 and
                            all(0 <= close[f"{c}_ns"] - burst[f"{c}_ns"] <= 100_000_000
                                for c in ("mono", "boot")))
        expected = bool(closed and identity_complete and prerequisite and arm and
                        close["mono_ns"] >= arm["c"])
        if not prerequisite:
            out["classification"] = "INCONCLUSIVE"
    elif cid == "C6":
        expected = bool(placement and stream_binding and one("g_crash") and
                        not by_name["g_summary"] and not by_name["fenced"] and
                        r["status"] == "UNKNOWN_RETAINED" and r["guardian_wait_code"] != 0 and
                        out["tree_empty"] and out["streams_eof"])
        out["identity_complete"] = None
        out["fence_observed"] = False
    if cid not in ("C3", "C6") and expected and clean:
        out["classification"] = "OBSERVED"
    out["case_expectation_met"] = bool(expected and clean and not errors)
    return out


def derive_capability(receipt: Any) -> dict[str, Any]:
    """Require the unique probe's original atomic entry, denial and exit facts."""
    errors = validate_native(receipt)
    if errors:
        return {"supported": False, "errors": errors}
    r = receipt
    by_name = {name: [e for e in r["events"] if e["event"] == name] for name in EVENTS}
    def one(name: str) -> dict[str, Any] | None:
        values = by_name[name]
        return values[0] if len(values) == 1 else None
    created, armed, ready = one("probe_created"), one("probe_armed"), one("probe_ready")
    caps, killed, exited, final = (one(n) for n in (
        "probe_capabilities", "probe_kill", "t_probe_exit", "t_cleanup_verified"))
    if r["kind"] != "probe" or r["case_id"] != "PROBE":
        errors.append("not the unique capability probe")
    if not created or created["a"] <= 0 or (created["b"], created["c"]) != (3, 1):
        errors.append("probe lacks atomic placement/original pidfd")
    if not armed or armed["a"] <= 0 or (armed["b"], armed["c"]) != (1, 2):
        errors.append("probe lacks ordinary UID/NNP/seccomp")
    if not caps or (caps["a"], caps["b"], caps["c"]) != (0, 0, 0):
        errors.append("probe capabilities not independently recorded clear")
    # Linux x86_64 syscall numbers; no host architecture-dependent lookup.
    expected_denials = {41, 42, 257, 59, 272, 308, 101, 311, 165, 435}
    denials = by_name["probe_denial"]
    if (len(denials) != len(expected_denials) or {e["a"] for e in denials} != expected_denials or
            any((e["b"], e["c"]) != (1, 1) for e in denials)):
        errors.append("probe missing exact syscall denial coverage")
    if not ready or ready["a"] != 1 or not killed or killed["a"] != 1:
        errors.append("probe readiness/kill unproved")
    if armed and ready and killed and any(not armed[f"{c}_ns"] <= ready[f"{c}_ns"] <= killed[f"{c}_ns"]
                                         for c in ("mono", "boot")):
        errors.append("probe causal ordering")
    if not exited or exited["a"] != r["guardian_wait_code"] or exited["b"] != 1:
        errors.append("probe original exit missing")
    if not final or (final["a"], final["b"], final["c"]) != (1, 1, 1):
        errors.append("probe original stream/tree cleanup unproved")
    if not (r["guardian_pidfd_exit"] and r["guardian_stream_eof"] and r["tree_empty"] and
            r["cleanup_verified"] and r["deadline_met"] and not r["output_exceeded"] and
            all(s["eof"] for s in r["streams"].values()) and r["status"] == "OBSERVED" and
            r["reason"] == "fixed_case_observed"):
        errors.append("probe did not complete within its original limits")
    if any(by_name[n] for n in ("native_error", "protocol_error", "clone_error", "group_error")):
        errors.append("probe native failure")
    return {"supported": not errors, "errors": errors}


def _validate_fixture(fixture: Any, case_count: int) -> list[str]:
    errors: list[str] = []
    if not _shape(fixture, {"account", "cgroup_objects", "resource_observations"}, "fixture", errors):
        return errors
    account = fixture["account"]
    if _shape(account, {"uid", "gid", "supplementary_groups", "home_created"}, "account", errors):
        if (not _integer(account["uid"], 1) or not _integer(account["gid"], 1) or
                account["supplementary_groups"] != [] or account["home_created"] is not False):
            errors.append("dedicated account does not match approved restrictions")
    groups = fixture["cgroup_objects"]
    labels = {"E", "G", "B", "B/S", "B/W"}
    if not isinstance(groups, list) or len(groups) != 5:
        errors.append("held cgroup identity set missing")
        return errors
    seen = set()
    ids = set()
    for group in groups:
        if not _shape(group, {"relative", "dev", "ino", "limits"}, "cgroup", errors):
            continue
        name = group["relative"]
        if not isinstance(name, str) or name not in labels or name in seen:
            errors.append("cgroup label duplicate/unknown")
            continue
        seen.add(name)
        if not _integer(group["dev"], 1) or not _integer(group["ino"], 1):
            errors.append("held cgroup identity missing")
        else:
            ids.add((group["dev"], group["ino"]))
        config = group["limits"]
        if not isinstance(config, dict):
            errors.append("actual cgroup configuration missing")
            continue
        if name in ("E", "G", "B"):
            expected = {"memory.max": LIMITS[name + "_memory_bytes"], "memory.swap.max": 0,
                        "pids.max": LIMITS[name + "_pids"], "cpu.max": LIMITS["cpu_max"]}
            if any(config.get(k) != val or type(config.get(k)) is not type(val) for k, val in expected.items()):
                errors.append(f"actual {name} limits do not match approved caps")
    if seen != labels or len(ids) != 5:
        errors.append("cgroup identities missing/aliased")
    observations = fixture["resource_observations"]
    required = {f"{c}-{boundary}" for c in ["probe"] + [f"C{i}" for i in range(1, case_count + 1)]
                for boundary in ("before", "after")}
    if not isinstance(observations, list) or len(observations) != len(required):
        errors.append("resource observation coverage")
        return errors
    boundaries: set[str] = set()
    for observation in observations:
        if not _shape(observation, {"boundary", "mono_ns", "boot_ns", "cgroups"}, "resource", errors):
            continue
        boundary = observation["boundary"]
        if not isinstance(boundary, str) or boundary not in required or boundary in boundaries:
            errors.append("resource boundary duplicate/unknown")
            continue
        boundaries.add(boundary)
        if any(not _integer(observation[c], 1) for c in ("mono_ns", "boot_ns")):
            errors.append("resource observation clock missing")
        rows = observation["cgroups"]
        if not isinstance(rows, dict) or set(rows) != labels:
            errors.append("resource cgroup coverage")
            continue
        for row in rows.values():
            keys = {"cpu_stat", "memory_current", "memory_peak", "pids_current", "pids_peak",
                    "memory_events", "pids_events", "populated"}
            if not _shape(row, keys, "resource row", errors):
                continue
            if any(not _integer(row[k]) for k in ("memory_current", "pids_current", "populated")):
                errors.append("resource current counts")
            for k in ("memory_peak", "pids_peak"):
                if row[k] is not None and not _integer(row[k]):
                    errors.append("resource peak observation")
            for k in ("cpu_stat", "memory_events", "pids_events"):
                if not isinstance(row[k], dict) or not row[k] or any(not _integer(x) for x in row[k].values()):
                    errors.append("resource counter missing/invalid")
            if isinstance(row["cpu_stat"], dict) and "usage_usec" not in row["cpu_stat"]:
                errors.append("actual CPU use missing")
            if boundary.endswith("-after") and row["populated"] != 0:
                errors.append("resource observation retains populated cgroup")
    return errors


def _validate_report_v1(report: Any) -> list[str]:
    errors: list[str] = []
    try:
        _bounded(report)
    except ReceiptError as exc:
        return [str(exc)]
    if not _shape(report, TOP_KEYS, "report", errors):
        return errors
    r = report
    if type(r["schema_version"]) is not int or r["schema_version"] != 1:
        errors.append("report schema version")
    if not isinstance(r["status"], str) or r["status"] not in STATUSES or not isinstance(r["reason"], str):
        errors.append("report status/reason")
    source = r["source"]
    if _shape(source, {"expected_commit", "github_sha", "head", "closure_sha256", "approved_A", "closure_C"},
              "source", errors):
        pins = [source[k] for k in ("expected_commit", "github_sha", "head")]
        if not all(_hex(v, 40) for v in pins) or len(set(pins)) != 1:
            errors.append("source exact D mismatch")
        closure = source["closure_sha256"]
        if not isinstance(closure, dict) or not closure or len(closure) > 32:
            errors.append("source closure required")
        elif any(not isinstance(p, str) or p.startswith("/") or ".." in p.split("/") or
                 not _hex(v, 64) for p, v in closure.items()):
            errors.append("source closure path/digest")
        else:
            if not REQUIRED_SOURCE_PATHS <= closure.keys():
                errors.append("source closure missing mandatory executable/governance paths")
            if any(closure.get(DOCUMENT_DIR + name) != value for name, value in DOCUMENT_HASHES.items()):
                errors.append("approved document bytes differ")
        if source["approved_A"] != APPROVED_A or source["closure_C"] != CLOSURE_C:
            errors.append("approved A/C identity mismatch")
    run = r["run"]
    if _shape(run, {"id", "attempt", "round"}, "run", errors):
        if not isinstance(run["id"], str) or not re.fullmatch(r"[1-9][0-9]{0,19}", run["id"]):
            errors.append("run identity")
        if type(run["attempt"]) is not int or run["attempt"] != 1:
            errors.append("rerun attempt prohibited")
        if type(run["round"]) is not int or run["round"] not in (1, 2, 3):
            errors.append("dispatch quota")
    if not isinstance(r["limits"], dict) or r["limits"] != LIMITS or any(
            type(r["limits"].get(k)) is not type(v) for k, v in LIMITS.items()):
        errors.append("approved limits changed")
    provenance_keys = {"runner_environment", "runner_os", "runner_arch", "image_os", "image_version",
        "kernel", "machine", "python", "compiler", "uid", "euid", "cap_eff", "cap_bnd",
        "no_new_privs", "seccomp", "boot_id", "cgroup_mount", "cgroup_parent_controllers",
        "cgroup_parent_subtree_control", "os_release", "native_sha256", "fixture"}
    if _shape(r["provenance"], provenance_keys, "provenance", errors):
        p = r["provenance"]
        if r["cases"] or r["status"] == "QUALIFIED_IN_FIXTURE":
            if (p["runner_environment"], p["runner_os"], p["runner_arch"], p["machine"]) != (
                    "github-hosted", "Linux", "X64", "x86_64"):
                errors.append("fixture platform")
            if p["os_release"] != {"id": "ubuntu", "version_id": "24.04"}:
                errors.append("fixture OS release")
            if (type(p["uid"]) is not int or type(p["euid"]) is not int or
                    p["uid"] != 0 or p["euid"] != 0 or not _hex(p["native_sha256"], 64)):
                errors.append("fixture build/identity missing")
            if any(not p[k] for k in ("image_os", "image_version", "kernel", "python", "boot_id",
                                      "cgroup_mount", "cap_eff", "cap_bnd")):
                errors.append("fixture provenance incomplete")
            if (p["image_os"] != "ubuntu24" or not isinstance(p["compiler"], dict) or
                    not p["compiler"].get("path") or not p["compiler"].get("version")):
                errors.append("fixture image/compiler provenance missing")
            for key in ("cgroup_parent_controllers", "cgroup_parent_subtree_control"):
                if not isinstance(p[key], list) or not all(isinstance(x, str) for x in p[key]) or not {"cpu", "memory", "pids"} <= set(p[key]):
                    errors.append("fixture parent controller availability missing")
        if r["cases"] or r["status"] == "QUALIFIED_IN_FIXTURE":
            errors.extend(_validate_fixture(p["fixture"], len(r["cases"]) if isinstance(r["cases"], list) else 0))
    budget_keys = {"prep_elapsed_seconds", "cases_elapsed_seconds", "cleanup_elapsed_seconds",
        "diagnostic_bytes", "report_bytes", "file_logical_bytes", "file_count", "allocated_bytes",
        "inode_count", "suite_stream_bytes"}
    if _shape(r["budget"], budget_keys, "budget", errors):
        for k, value in r["budget"].items():
            if not _number(value):
                errors.append(f"budget {k}: number required")
            if not k.endswith("_elapsed_seconds") and not _integer(value):
                errors.append(f"budget {k}: integer count required")
            bound = LIMITS.get(k.replace("_elapsed", ""), LIMITS.get(k))
            if _number(value) and bound is not None and value > bound:
                errors.append(f"budget {k}: exceeded")
    cleanup = r["cleanup"]
    if _shape(cleanup, {"verified", "records", "residuals"}, "cleanup", errors):
        if type(cleanup["verified"]) is not bool or not isinstance(cleanup["records"], list) or not isinstance(cleanup["residuals"], list):
            errors.append("cleanup shape")
        elif cleanup["verified"] and (cleanup["residuals"] or any(
                not isinstance(x, dict) or x.get("identity_match") is not True or x.get("removed") is not True
                for x in cleanup["records"])):
            errors.append("cleanup assertion lacks removal/identity facts")
        elif cleanup["verified"] and isinstance(r["cases"], list) and r["cases"]:
            run = r["run"]
            if isinstance(run, dict) and "id" in run and "round" in run:
                prefix = f"q2-h07-{run['id']}-1-r{run['round']}"
                expected_objects = {prefix + suffix for suffix in ("", "/G", "/B", "/B/S", "/B/W")}
                expected_objects |= {"dedicated-account", "build/helper"}
                objects = [record.get("object") for record in cleanup["records"]]
                if (not all(isinstance(obj, str) for obj in objects) or
                        not expected_objects <= set(objects) or len(objects) != len(set(objects)) or
                        any(not re.fullmatch(r"original-subprocess-[1-9][0-9]*", obj)
                            for obj in set(objects) - expected_objects)):
                    errors.append("cleanup lacks exact complete registered object set")
    cap = r["capability"]
    if cap is not None:
        errors.extend("capability: " + e for e in validate_native(cap))
        if isinstance(cap, dict) and cap.get("case_id") != "PROBE":
            errors.append("capability: wrong case")
    cases = r["cases"]
    if not isinstance(cases, list) or len(cases) > 6:
        errors.append("case list")
    else:
        expected = [f"C{i}" for i in range(1, len(cases) + 1)]
        if [x.get("case_id") if isinstance(x, dict) else None for x in cases] != expected:
            errors.append("case order/identity/repeat")
        for case in cases:
            case_id = case.get("case_id", "?") if isinstance(case, dict) else "?"
            errors.extend(f"{case_id}: {e}" for e in validate_native(case))
        if all(not validate_native(c) for c in cases):
            total = sum(s["bytes"] for c in cases for s in c["streams"].values())
            if isinstance(r["budget"], dict) and total != r["budget"].get("suite_stream_bytes"):
                errors.append("suite stream bill mismatch")
            if cases:
                errors.extend(_bind_fixture_receipts(r))
    return errors


_SUPPORT_MODULES: dict[str, Any] = {}


def _support_module(name: str) -> Any:
    """Load only fixed sibling validators; schema 1 never imports new code."""
    if name not in {"account_evidence", "continuation"}:
        raise ReceiptError("unknown receipt support module")
    if name not in _SUPPORT_MODULES:
        spec = importlib.util.spec_from_file_location(
            __name__ + "_" + name, Path(__file__).with_name(name + ".py"))
        if spec is None or spec.loader is None:
            raise ReceiptError("receipt support module unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(spec.name, None)
            raise
        _SUPPORT_MODULES[name] = module
    return _SUPPORT_MODULES[name]


def _v2_encoding_size(report: dict[str, Any]) -> int:
    """Bound direct Python inputs as well as bytes passed through load_report."""
    size = 1  # The fixture's final LF is part of its existing report ceiling.
    try:
        encoder = json.JSONEncoder(ensure_ascii=True, allow_nan=False, sort_keys=True,
                                   separators=(",", ":"))
        for chunk in encoder.iterencode(report):
            size += len(chunk.encode("utf-8", "strict"))
            if size > MAX_REPORT:
                raise ReceiptError("report byte limit")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise ReceiptError("invalid schema 2 JSON encoding") from exc
    return size


def _account_facts(report: dict[str, Any]) -> dict[str, Any]:
    return _support_module("account_evidence").account_setup_facts(report["account_setup"])


def _bind_account_budget(report: dict[str, Any], account: Any) -> list[str]:
    """Count original captures in the one diagnostic bill and stage windows."""
    setup = report["account_setup"]
    errors: list[str] = []
    observations = setup["observations"]
    audits = [row["audit"] for row in observations]
    if setup["create_command"] is not None:
        audits.append(setup["create_command"])
    audits.extend(setup["delete_commands"])
    if any(account.validate_audit(audit) for audit in audits):
        return []  # The strict account validator supplies shape diagnostics.
    captured = sum(audit[stream]["bytes"] for audit in audits for stream in ("stdout", "stderr"))
    budget = report["budget"]
    if not _integer(budget.get("diagnostic_bytes")) or captured > budget["diagnostic_bytes"]:
        errors.append("account captures exceed the original diagnostic byte bill")
    prep = [audit for audit in audits if audit["role"] in ("pre_create", "useradd", "post_create")]
    cleanup = [audit for audit in audits if audit["role"] in
               ("pre_cleanup", "userdel", "post_userdel", "groupdel", "post_groupdel")]
    for stage, entries in (("prep", prep), ("cleanup", cleanup)):
        if not entries:
            continue
        elapsed = budget.get(stage + "_elapsed_seconds")
        for clock in ("mono", "boot"):
            span = max(a["end_" + clock + "_ns"] for a in entries) - min(
                a["start_" + clock + "_ns"] for a in entries)
            if not _number(elapsed) or span > (elapsed + 0.000000001) * 1_000_000_000:
                errors.append("account " + stage + " clocks exceed the original stage bill")
    capability = report["capability"]
    if capability is not None and not validate_native(capability):
        if not prep or any(max(a["end_" + c + "_ns"] for a in prep) > capability["start_" + c + "_ns"]
                           for c in ("mono", "boot")):
            errors.append("capability preceded completed account admission")
        native = [capability] + report["cases"]
        if cleanup and all(not validate_native(receipt) for receipt in native) and any(
                min(a["start_" + c + "_ns"] for a in cleanup) < max(
                    r["end_" + c + "_ns"] for r in native) for c in ("mono", "boot")):
            errors.append("account cleanup preceded completion of native work")
    return errors


def _validate_report_v2(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        _bounded(report)
        report_size = _v2_encoding_size(report)
    except ReceiptError as exc:
        return [str(exc)]
    if not _shape(report, TOP_V2_KEYS, "report schema 2", errors):
        return errors
    if (not isinstance(report["budget"], dict) or
            type(report["budget"].get("report_bytes")) is not int or
            report["budget"]["report_bytes"] != report_size):
        errors.append("schema 2 report byte bill differs from its complete encoded envelope")
    source = report["source"]
    if not _shape(source, SOURCE_V2_KEYS, "source schema 2", errors):
        return errors
    if (source["approved_continuation_A"] != APPROVED_CONTINUATION_A or
            source["closure_continuation_C"] != CLOSURE_CONTINUATION_C):
        errors.append("approved continuation A/C identity mismatch")
    closure = source["closure_sha256"]
    if isinstance(closure, dict):
        if not REQUIRED_CONTINUATION_SOURCE_PATHS <= closure.keys():
            errors.append("source closure missing mandatory continuation paths")
        if any(closure.get(CONTINUATION_DOCUMENT_DIR + name) != value
               for name, value in CONTINUATION_DOCUMENT_HASHES.items()):
            errors.append("approved continuation document bytes differ")
    # Check the unchanged native/fixture contract using a new shallow envelope.
    # No retained original is filled, migrated, or modified, and schema 1 keeps
    # its own original validation path and verdicts.
    common = {key: report[key] for key in TOP_KEYS}
    common["schema_version"] = 1
    common["source"] = {key: source[key] for key in SOURCE_KEYS}
    try:
        errors.extend(_validate_report_v1(common))
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
        errors.append("malformed schema 2 common facts: " + type(exc).__name__)
    # The sibling pure validators bind account evidence and continuation facts
    # to the same run, provenance and registered cleanup; neither grants native
    # capability, fencing, or historical cleanup credit.
    try:
        account = _support_module("account_evidence")
        provenance = report["provenance"]
        fixture = provenance.get("fixture") if isinstance(provenance, dict) else None
        fixture_account = fixture.get("account") if isinstance(fixture, dict) else None
        account_errors = account.validate_account_setup(
            report["account_setup"], run=report["run"], fixture_account=fixture_account,
            cleanup=report["cleanup"])
        errors.extend("account_setup: " + error for error in account_errors)
        if not account_errors:
            errors.extend("account_setup: " + error for error in _bind_account_budget(report, account))
        facts = account.account_setup_facts(report["account_setup"])
        if (report["capability"] is not None or report["cases"]) and (
                facts["errors"] or facts["admitted"] is not True):
            errors.append("account_setup: native work without a fully admitted identity")
        if report["status"] == "QUALIFIED_IN_FIXTURE" and (
                facts["errors"] or facts["admitted"] is not True or
                facts["cleanup_verified"] is not True):
            errors.append("account_setup: qualification lacks independently derived account cleanup")
    except (ImportError, OSError, KeyError, TypeError, ValueError, AttributeError) as exc:
        errors.append("account_setup validator unavailable or malformed facts: " + type(exc).__name__)
    try:
        continuation = _support_module("continuation")
        errors.extend("continuation: " + error for error in continuation.validate_continuation(
            report["continuation"], run=report["run"], source=source,
            provenance=report["provenance"]))
    except (ImportError, OSError, KeyError, TypeError, ValueError, AttributeError) as exc:
        errors.append("continuation validator unavailable or malformed facts: " + type(exc).__name__)
    return errors


def validate_report(report: Any) -> list[str]:
    """Select an explicit contract, with no default or legacy promotion."""
    if not isinstance(report, dict) or type(report.get("schema_version")) is not int:
        return ["report schema version"]
    if report["schema_version"] == 1:
        return _validate_report_v1(report)
    if report["schema_version"] == 2:
        return _validate_report_v2(report)
    return ["report schema version"]


def _bind_fixture_receipts(report: dict[str, Any]) -> list[str]:
    """Join native held FDs and original intervals to the outer fixture ledger."""
    errors: list[str] = []
    if not isinstance(report["provenance"], dict):
        return []
    fixture = report["provenance"].get("fixture", {})
    if _validate_fixture(fixture, len(report["cases"])):
        return []  # Detailed shape diagnostics are already retained by the caller.
    groups = {g["relative"]: (g["dev"], g["ino"]) for g in fixture["cgroup_objects"]}
    observations = {o["boundary"]: o for o in fixture["resource_observations"]}
    previous = None
    for receipt in [report["capability"]] + report["cases"]:
        if receipt is None or validate_native(receipt):
            errors.append("case followed an absent/invalid capability receipt")
            continue
        case_id = "probe" if receipt["case_id"] == "PROBE" else receipt["case_id"]
        names = {"e_identity": "E", "g_identity": "G", "b_identity": "B",
                 "s_identity": "B/S", "w_identity": "B/W"}
        for name, label in names.items():
            events = [e for e in receipt["events"] if e["event"] == name]
            if (len(events) != 1 or (events[0]["a"], events[0]["b"]) != groups[label] or
                    events[0]["c"] & 0o170000 != 0o040000):
                errors.append(f"{case_id}: held {label} identity differs from fixture")
        if case_id != "probe":
            credentials = [e for e in receipt["events"] if e["event"] == "s_credentials"]
            if len(credentials) != 1 or (credentials[0]["a"], credentials[0]["b"]) != (
                    fixture["account"]["uid"], fixture["account"]["gid"]):
                errors.append(f"{case_id}: launcher/account binding missing")
        before, after = observations[case_id + "-before"], observations[case_id + "-after"]
        if any(not before[f"{c}_ns"] <= receipt[f"start_{c}_ns"] <= receipt[f"end_{c}_ns"] <= after[f"{c}_ns"]
               for c in ("mono", "boot")):
            errors.append(f"{case_id}: receipt outside resource observation interval")
        if previous and any(receipt[f"start_{c}_ns"] < previous[f"end_{c}_ns"] for c in ("mono", "boot")):
            errors.append(f"{case_id}: overlapping/reused original case clock")
        previous = receipt
    return errors


def derive_report(report: dict[str, Any]) -> dict[str, Any]:
    errors = validate_report(report)
    if errors:
        return {"status": "REJECTED", "errors": errors, "case_results": []}
    results = [derive_case(case) for case in report["cases"]]
    cap = report["capability"]
    supported = bool(cap and derive_capability(cap)["supported"])
    account_qualified = True
    if report["schema_version"] == 2:
        facts = _account_facts(report)
        account_qualified = (not facts["errors"] and facts["admitted"] is True and
                             facts["cleanup_verified"] is True)
    if (supported and account_qualified and not report["reason"] and len(results) == 6 and
            all(c["case_expectation_met"] for c in results) and report["cleanup"]["verified"]):
        status = "QUALIFIED_IN_FIXTURE"
    elif any(c["classification"] == "INCONCLUSIVE" for c in results):
        status = "INCONCLUSIVE"
    elif not results and report["status"] in ("UNSUPPORTED", "REJECTED"):
        status = report["status"]
    else:
        status = "UNKNOWN_RETAINED"
    if report["status"] == "QUALIFIED_IN_FIXTURE" and status != "QUALIFIED_IN_FIXTURE":
        errors.append("qualification claim not established by retained evidence")
    return {"status": status, "errors": errors, "case_results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        with args.path.open("rb") as stream:
            report = load_report(stream.read(MAX_REPORT + 1))
        result = derive_report(report)
    except (OSError, ReceiptError) as exc:
        result = {"status": "REJECTED", "errors": [str(exc)], "case_results": []}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "QUALIFIED_IN_FIXTURE" and not result["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
