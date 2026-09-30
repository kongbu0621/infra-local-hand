"""Pure offline report-v3/native-v2 receipt semantics for H07 V1--V4.

No producer, process launch, host mutation or dispatch lives here. Synthetic
transcripts check this contract; they do not attest an implemented laboratory
producer or authorize a third run. Old report/native contracts remain separate.
"""
from __future__ import annotations

import base64
import binascii
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

_SPEC = importlib.util.spec_from_file_location(__name__ + "_legacy", Path(__file__).with_name("verify_receipt.py"))
assert _SPEC and _SPEC.loader
v = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v)
_integer, _wait_code, _number, _hex, _shape = v._integer, v._wait_code, v._number, v._hex, v._shape
ReceiptError, LIMITS = v.ReceiptError, v.LIMITS
GENERATIONS = ("PROBE", "C1", "C2", "C3", "C4", "C5", "C6")
NATIVE_KEYS = v.NATIVE_KEYS | {"generation"}
EVENTS = v.EVENTS | {"s_exit_before_arm", "s_arm_rejected", "kill_requested", "kill_result"}
# Bit positions: frame PID, frame UID, frame mode, original pidfd, credentials,
# supplementary groups, capabilities, NNP/seccomp. Unread facts occupy failed bits.
ARM_CHECKS = ("frame_pid", "frame_uid", "frame_mode", "original_pidfd",
              "credentials", "supplementary_groups", "capabilities", "nnp_seccomp")
ARM_MASK = (1 << len(ARM_CHECKS)) - 1
# Actor 1 is the original guardian G; actor 2 is the original native collector T.
KILL_ACTORS = {1, 2}
# 1..6 case closure; 80 probe; 81 collector cleanup; 82 deadline;
# 90 protocol; 91 arm reject; 92 worker identity; 93 worker exit;
# 94 unexpected frame; 95 control; 96 unarmed exit; 97 capture; 98 budget.
KILL_REASONS = set(range(1, 7)) | {80, 81, 82, 90, 91, 92, 93, 94, 95, 96, 97, 98}

def _validate_native(receipt: Any) -> list[str]:
    errors: list[str] = []
    if not _shape(receipt, NATIVE_KEYS, "native", errors):
        return errors
    r = receipt
    if r["generation"] not in GENERATIONS or r["generation"] != r["case_id"]:
        errors.append("native: generation mismatch")
    if type(r["schema_version"]) is not int or r["schema_version"] != 2:
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
    errors.extend(_diagnostics(r))
    # Event clocks can precede an earlier-appended message from another process;
    # the single collector sequence is not falsely equated with global causality.
    return errors


def validate_native(receipt: Any) -> list[str]:
    try:
        return _validate_native(receipt)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return ["native v2: malformed original data"]


def derive_case(receipt: dict[str, Any]) -> dict[str, Any]:
    errors = validate_native(receipt)
    out: dict[str, Any] = {
        "case_id": receipt.get("case_id") if isinstance(receipt, dict) else None, "case_expectation_met": False,
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
    out["identity_complete"] = identity_complete if placement else None
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
    expected_summary = (-1 if not placement else int(identity_complete), int(closed),
                        -1 if arm is None else int(out["deadline_met"]))
    if summary and (summary["a"], summary["b"], summary["c"]) != expected_summary:
        errors.append("guardian summary contradicts retained independent facts")
    if any(e["c"] != 0 for e in by_name["kill_result"]):
        errors.append("native kill failure retained")
    clean = bool(out["cleanup_verified"] and out["guardian_exit_observed"] and
                 out["deadline_met"] and not r["output_exceeded"])
    if any(by_name[name] for name in ("native_error", "protocol_error", "clone_error", "group_error")):
        errors.append("native failure retained")
    cid = r["case_id"]
    expected_status, expected_reason = {
        "C3": ("UNKNOWN_RETAINED", "expected_lost_identity"),
        "C6": ("UNKNOWN_RETAINED", "expected_guardian_loss"),
    }.get(cid, ("OBSERVED", "fixed_case_observed"))
    if by_name["s_exit_before_arm"] or by_name["s_arm_rejected"]:
        expected_status = "UNKNOWN_RETAINED"
        expected_reason = "launcher_arm_rejected" if by_name["s_arm_rejected"] else "launcher_exit_before_arm"
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
    if any(e["c"] != 0 for e in by_name["kill_result"]):
        errors.append("probe kill failure retained")
    return {"supported": not errors, "errors": errors}


def _diagnostics(r: dict[str, Any]) -> list[str]:
    """Correlate new diagnostics with retained originals, never manufacture facts."""
    errors: list[str] = []
    if not isinstance(r.get("events"), list) or any(not isinstance(e, dict) or
            set(e) != {"event", "seq", "mono_ns", "boot_ns", "a", "b", "c"} or
            any(not _integer(e[k], -(2**63) + 1) for k in ("a", "b", "c", "seq", "mono_ns", "boot_ns"))
            for e in r["events"]):
        return errors  # Structural diagnostics already identify malformed fields.
    events = r["events"]
    by = lambda name: [e for e in events if e["event"] == name]
    if any(len(by(n)) > 1 for n in ("s_exit_before_arm", "s_arm_rejected", "g_summary")):
        errors.append("native v2: duplicate diagnostic/summary")
    for summary in by("g_summary"):
        if any(summary[k] not in (-1, 0, 1) for k in ("a", "b", "c")):
            errors.append("native v2: summary is not three-state")
    for early in by("s_exit_before_arm"):
        exits, created = by("s_exit"), by("s_created")
        if (len(exits) != 1 or len(created) != 1 or created[0]["a"] <= 0 or
                (created[0]["b"], created[0]["c"]) != (3, 1) or
                not _wait_code(early["a"]) or (early["b"], early["c"]) != (1, 0) or
                (exits[0]["a"], exits[0]["b"]) != (early["a"], 1) or
                any(by(n) for n in ("s_armed", "request_sent", "request_received", "worker_created")) or
                any(not created[0][f"{c}_ns"] <= exits[0][f"{c}_ns"] <= early[f"{c}_ns"]
                    for c in ("mono", "boot"))):
            errors.append("native v2: unbound early launcher exit")
        close = by("close_requested")
        if close and (len(close) != 1 or close[0]["a"] != 96 or any(
                close[0][f"{c}_ns"] < early[f"{c}_ns"] for c in ("mono", "boot"))):
            errors.append("native v2: early exit mislabelled as normal closure")
    for rejected in by("s_arm_rejected"):
        created = by("s_created")
        if (len(created) != 1 or created[0]["a"] <= 0 or (created[0]["b"], created[0]["c"]) != (3, 1) or
                any(created[0][f"{clock}_ns"] > rejected[f"{clock}_ns"] for clock in ("mono", "boot"))):
            errors.append("native v2: arm rejection lacks original launcher identity")
        a, passed, failed = (rejected[k] for k in ("a", "b", "c"))
        if (not 1 <= a <= len(ARM_CHECKS) or not 0 <= passed <= ARM_MASK or
                not 1 <= failed <= ARM_MASK or passed & failed or passed | failed != ARM_MASK or
                not failed & (1 << (a - 1)) or any(by(n) for n in
                    ("s_armed", "request_sent", "request_received", "worker_created"))):
            errors.append("native v2: invalid arm rejection mask/originals")
    requested, results = by("kill_requested"), by("kill_result")
    if len(requested) > 8 or len(results) > 8:
        errors.append("native v2: kill diagnostic bound")
    seen: set[tuple[int, int]] = set()
    for request in requested:
        actor, reason, attempt = (request[k] for k in ("a", "b", "c"))
        key = (actor, attempt)
        if actor not in KILL_ACTORS or reason not in KILL_REASONS or not 1 <= attempt <= 8 or key in seen:
            errors.append("native v2: kill request identity")
        seen.add(key)
        if r.get("kind") == "probe" and (actor, reason) != (2, 80):
            errors.append("native v2: probe kill role/reason")
        if r.get("kind") == "case":
            case_reason = int(r["case_id"][1:])
            if actor == 1 and reason not in ({case_reason} | set(range(90, 99))):
                errors.append("native v2: guardian kill reason differs from case")
            if actor == 2 and reason not in {81, 82, 97, 98}:
                errors.append("native v2: collector kill reason")
        matches = [e for e in results if (e["a"], e["b"]) == key]
        if len(matches) != 1 or any(matches[0][f"{c}_ns"] < request[f"{c}_ns"]
                                    for c in ("mono", "boot")):
            errors.append("native v2: missing/earlier kill result")
    if any((e["a"], e["b"]) not in seen or not 0 <= e["c"] <= 4095 for e in results):
        errors.append("native v2: unbound kill result/errno")
    for actor in KILL_ACTORS:
        attempts = [e["c"] for e in requested if e["a"] == actor]
        if attempts != list(range(1, len(attempts) + 1)):
            errors.append("native v2: skipped/reused kill attempt")
    # Each successful old effect consumes a distinct preceding request/result pair.
    consumed: set[tuple[int, int]] = set()
    for name, actor in (("b_kill", 1), ("probe_kill", 2), ("t_cleanup", 2)):
        for effect in by(name):
            successful = [e for e in results if e["a"] == actor and e["c"] == 0 and (e["a"], e["b"]) not in consumed and
                          all(e[f"{c}_ns"] <= effect[f"{c}_ns"] for c in ("mono", "boot"))]
            if effect["a"] == 1:
                if not successful:
                    errors.append("native v2: kill effect lacks distinct original successful result")
                else:
                    match = successful[0]
                    consumed.add((match["a"], match["b"]))
    if r.get("kind") == "probe" and any(by(n) for n in ("s_exit_before_arm", "s_arm_rejected", "g_summary")):
        errors.append("native v2: case diagnostics inside probe")
    return errors


TOP_KEYS = v.TOP_V2_KEYS | {"generations", "primary_failure", "validation_errors"}
SOURCE_KEYS = v.SOURCE_V2_KEYS | {"approved_r2_continuation_A", "closure_r2_continuation_C"}
OBJECT_KEYS = {"relative", "role", "dev", "ino", "creation_order", "created_mono_ns", "created_boot_ns", "limits"}
GENERATION_KEYS = {"generation", "sequence", "run", "state", "window", "e", "objects", "before", "after", "helper", "native", "retirement"}
STATES = {"PREPARING", "ADMITTED", "EXECUTED", "RETIRING", "RETIRED", "FAILED"}
PHASES = {"admission", "preparation", "probe", "cases", "retirement", "cleanup", "validation", "budget"}
FAILURE_CODES = {"SOURCE_REJECTED", "ENVIRONMENT_UNSUPPORTED", "ACCOUNT_SETUP_FAILED", "GENERATION_SETUP_FAILED",
                 "PROBE_UNSUPPORTED", "CASE_EXPECTATION_UNMET", "LAUNCHER_EXIT_BEFORE_ARM", "LAUNCHER_ARM_REJECTED",
                 "NATIVE_CAPTURE_FAILED", "GENERATION_RETIREMENT_FAILED", "CLEANUP_FAILED", "BUDGET_EXCEEDED",
                 "REPORT_VALIDATION_FAILED"}
VALIDATION_STAGES = {"source", "continuation", "account", "generation", "native", "report", "cleanup", "budget"}
VALIDATION_CODES = {"INVALID_FACTS", "MISSING_FACTS", "IDENTITY_MISMATCH", "BUDGET_EXCEEDED", "UNKNOWN_VERSION", "VALIDATOR_UNAVAILABLE"}


def _text(value: Any, limit: int, *, empty: bool = True) -> bool:
    try:
        return (isinstance(value, str) and (empty or bool(value)) and len(value.encode("utf-8")) <= limit and
                not any(ord(ch) < 32 for ch in value))
    except UnicodeError:
        return False


def validate_failures(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    failure = report.get("primary_failure")
    if failure is not None:
        if _shape(failure, {"phase", "generation", "code", "detail", "mono_ns", "boot_ns", "native_event"}, "primary failure", errors):
            if (failure["phase"] not in PHASES or failure["generation"] not in (None, *GENERATIONS) or
                    failure["code"] not in FAILURE_CODES or not _text(failure["detail"], 512, empty=False) or
                    any(not _integer(failure[k], 1) for k in ("mono_ns", "boot_ns"))):
                errors.append("primary failure: bounded identity/detail/clock")
            ref = failure["native_event"]
            if ref is not None and _shape(ref, {"generation", "seq"}, "failure native reference", errors):
                candidates = [r for r in [report.get("capability")] + report.get("cases", []) if isinstance(r, dict) and
                              r.get("generation") == ref["generation"]]
                if (ref["generation"] != failure["generation"] or not _integer(ref["seq"], 1) or
                        len(candidates) != 1 or not isinstance(candidates[0].get("events"), list) or
                        ref["seq"] > len(candidates[0]["events"])):
                    errors.append("primary failure: native event reference not retained")
                else:
                    event = candidates[0]["events"][ref["seq"] - 1]
                    if any(not _integer(event.get(k), 1) or failure[k] < event[k] for k in ("mono_ns", "boot_ns")):
                        errors.append("primary failure: observation precedes referenced event")
        if not _text(report.get("reason"), 512, empty=False):
            errors.append("primary failure erased by empty/invalid reason")
    elif report.get("reason"):
        errors.append("nonempty failure reason lacks primary failure")
    value = report.get("validation_errors")
    if _shape(value, {"items", "exceeded"}, "validation errors", errors):
        if type(value["exceeded"]) is not bool or not isinstance(value["items"], list) or len(value["items"]) > 16:
            errors.append("validation error list bound/type")
        else:
            total = 0
            for item in value["items"]:
                if not _shape(item, {"stage", "code", "detail"}, "validation error", errors):
                    continue
                if item["stage"] not in VALIDATION_STAGES or item["code"] not in VALIDATION_CODES or not _text(item["detail"], 4096, empty=False):
                    errors.append("validation error enum/detail")
                total += sum(len(str(item[k]).encode("utf-8")) for k in ("stage", "code", "detail"))
            if total > 4096:
                errors.append("validation error text budget")
            if value["exceeded"]:
                errors.append("validation error list exceeded (retained)")
            if value["items"] and failure is None:
                errors.append("validation errors lack first failure")
    return errors


def _object(obj: Any, *, relative: str, role: str, order: int, complete: bool, errors: list[str]) -> bool:
    if not _shape(obj, OBJECT_KEYS, "generation object", errors):
        return False
    if (obj["relative"] != relative or obj["role"] != role or type(obj["creation_order"]) is not int or
            obj["creation_order"] != order or any(not _integer(obj[k], 1) for k in
                ("dev", "ino", "created_mono_ns", "created_boot_ns"))):
        errors.append("generation object identity/order/clock")
    limits = obj["limits"]
    if limits is None and not complete:
        return True
    if _shape(limits, {"memory.max", "memory.swap.max", "pids.max", "cpu.max"}, "object limits", errors):
        for key in ("memory.max", "memory.swap.max", "pids.max"):
            if limits[key] is not None and not _integer(limits[key]):
                errors.append("generation object limit type")
        if not isinstance(limits["cpu.max"], str) or re.fullmatch(r"(?:max|[1-9][0-9]*) [1-9][0-9]*", limits["cpu.max"]) is None:
            errors.append("generation object CPU limit")
        if role in ("E", "G", "B"):
            expected = {"memory.max": LIMITS[role + "_memory_bytes"], "memory.swap.max": 0,
                        "pids.max": LIMITS[role + "_pids"], "cpu.max": LIMITS["cpu_max"]}
            if any(type(limits[k]) is not type(val) or limits[k] != val for k, val in expected.items()):
                errors.append("generation object cap differs from approved " + role)
    return True


def _sample(sample: Any, *, generation: str, boundary: str, groups: dict[str, dict[str, Any]], errors: list[str]) -> None:
    if not _shape(sample, {"generation", "boundary", "mono_ns", "boot_ns", "cgroups"}, "resource sample", errors):
        return
    if (sample["generation"] != generation or sample["boundary"] != generation + "-" + boundary or
            any(not _integer(sample[k], 1) for k in ("mono_ns", "boot_ns"))):
        errors.append("resource sample generation/boundary/clock")
    rows = sample["cgroups"]
    if not isinstance(rows, dict) or set(rows) != set(groups):
        errors.append("resource sample exact object coverage")
        return
    keys = {"dev", "ino", "cpu_stat", "memory_current", "memory_peak", "pids_current", "pids_peak", "memory_events", "pids_events", "populated"}
    for name, row in rows.items():
        if not _shape(row, keys, "resource row", errors):
            continue
        if any(type(row[k]) is not int or row[k] != groups[name][k] for k in ("dev", "ino")):
            errors.append("resource sample wrong held identity")
        for k in ("memory_current", "pids_current", "populated"):
            if not _integer(row[k]): errors.append("resource count type")
        if row["populated"] not in (0, 1): errors.append("resource populated flag")
        for k in ("memory_peak", "pids_peak"):
            if row[k] is not None and not _integer(row[k]): errors.append("resource peak type")
        for k in ("cpu_stat", "memory_events", "pids_events"):
            if not isinstance(row[k], dict) or not row[k] or any(not isinstance(n, str) or not _integer(val) for n, val in row[k].items()):
                errors.append("resource counter shape")
        if not isinstance(row["cpu_stat"], dict) or "usage_usec" not in row["cpu_stat"]:
            errors.append("resource CPU usage missing")
        if boundary == "after" and row["populated"] != 0:
            errors.append("resource retains populated object")


def _retirement(row: dict[str, Any], *, errors: list[str]) -> bool:
    retire = row["retirement"]
    keys = {"started_mono_ns", "started_boot_ns", "end_mono_ns", "end_boot_ns", "verified", "records", "failure"}
    if not _shape(retire, keys, "retirement", errors): return False
    if type(retire["verified"]) is not bool or retire["failure"] is not None and not _text(retire["failure"], 512, empty=False):
        errors.append("retirement flags/failure")
    for clock in ("mono", "boot"):
        start, end = retire["started_" + clock + "_ns"], retire["end_" + clock + "_ns"]
        if not _integer(start) or not _integer(end) or end < start:
            errors.append("retirement clock")
        elif row["after"] is not None and start < row["after"][clock + "_ns"]:
            errors.append("retirement precedes original after sample")
    records = retire["records"]
    if not isinstance(records, list) or len(records) > 4:
        errors.append("retirement record count"); return False
    objects = {obj["relative"]: obj for obj in row["objects"]}
    names = [r.get("relative") if isinstance(r, dict) else None for r in records]
    expected_order = [obj["relative"] for role in ("S", "W", "B", "G") for obj in row["objects"] if obj["role"] == role]
    if names != expected_order[:len(names)]: errors.append("retirement child-before-parent order")
    all_complete = True
    previous_record = None
    for record in records:
        if not _shape(record, {"relative", "dev", "ino", "identity_match", "empty", "removed", "fd_closed", "mono_ns", "boot_ns"}, "retirement record", errors):
            all_complete = False; continue
        obj = objects.get(record["relative"])
        if obj is None or any(type(record[k]) is not int or record[k] != obj[k] for k in ("dev", "ino")):
            errors.append("retirement wrong original object")
        for flag in ("identity_match", "empty", "removed", "fd_closed"):
            if type(record[flag]) is not bool: errors.append("retirement flag type")
            all_complete = all_complete and record[flag] is True
        for clock in ("mono", "boot"):
            at = record[clock + "_ns"]
            if not _integer(at, 1) or not retire["started_" + clock + "_ns"] <= at <= retire["end_" + clock + "_ns"]:
                errors.append("retirement record interval")
            if previous_record is not None and at < previous_record[clock + "_ns"]:
                errors.append("retirement record clocks contradict child-before-parent order")
        previous_record = record
    complete = bool(all_complete and len(records) == len(objects) == 4 and retire["failure"] is None)
    if retire["verified"] and not complete:
        errors.append("retirement summary lacks complete original facts")
    if row["state"] == "RETIRED" and not retire["verified"]:
        errors.append("retired state without complete retirement")
    return complete and retire["verified"] and row["state"] == "RETIRED"

def validate_generations(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rows = report["generations"]
    fixture = report["provenance"]["fixture"]
    if not _shape(fixture, {"account", "cgroup_objects", "resource_observations"}, "fixture v3", errors): return errors
    account = fixture["account"]
    if _shape(account, {"uid", "gid", "supplementary_groups", "home_created"}, "fixture account", errors):
        if (not _integer(account["uid"], 1) or not _integer(account["gid"], 1) or
                account["supplementary_groups"] != [] or account["home_created"] is not False):
            errors.append("fixture account restrictions")
    history = fixture["cgroup_objects"]
    if not isinstance(history, list) or len(history) > 29 or not isinstance(rows, list) or len(rows) > 7:
        return errors + ["generation/history count"]
    if not rows:
        if history or fixture["resource_observations"] or report["capability"] is not None or report["cases"]:
            errors.append("generation history absent despite retained objects/work")
        return errors
    if not history or not _object(history[0], relative="E", role="E", order=1, complete=True, errors=errors):
        return errors + ["common E object missing"]
    common = history[0]
    expected_history = [common]
    expected_observations: list[Any] = []
    natives = [report["capability"]] + report["cases"]
    previous = None
    previous_continues = False
    phase_windows: dict[str, dict[str, int]] = {}
    last_e: dict[str, Any] | None = None
    for index, row in enumerate(rows):
        if not _shape(row, GENERATION_KEYS, "generation", errors): continue
        name = GENERATIONS[index]
        if row["generation"] != name or type(row["sequence"]) is not int or row["sequence"] != index + 1 or row["run"] != report["run"] or row["state"] not in STATES:
            errors.append("generation fixed order/run/state")
        if previous is not None and not previous_continues:
            errors.append("generation follows unretired/failed predecessor")
        objects = row["objects"]
        complete = row["state"] not in ("PREPARING", "FAILED")
        if not isinstance(objects, list) or len(objects) > 4 or complete and len(objects) != 4:
            errors.append("generation exact four object set"); continue
        window = row["window"]
        if not _shape(window, {"start_mono_ns", "start_boot_ns", "deadline_mono_ns", "deadline_boot_ns"}, "phase window", errors): continue
        phase = "preparation" if name == "PROBE" else "cases"
        ceiling = 120 if name == "PROBE" else 180
        for clock in ("mono", "boot"):
            start, end = window[f"start_{clock}_ns"], window[f"deadline_{clock}_ns"]
            if not _integer(start, 1) or not _integer(end, 1) or not 0 < end - start <= ceiling * 10**9:
                errors.append("phase original window bound")
        if phase in phase_windows and window != phase_windows[phase]:
            errors.append("phase window refreshed across generations")
        phase_windows[phase] = window
        if name == "PROBE":
            for clock in ("mono", "boot"):
                if not window[f"start_{clock}_ns"] <= common[f"created_{clock}_ns"] <= window[f"deadline_{clock}_ns"]:
                    errors.append("common E created outside original preparation phase")
        if row["e"] != {k: common[k] for k in ("relative", "dev", "ino")}:
            errors.append("generation changed common E identity")
        relatives = ["G-" + name, "B-" + name, "B-" + name + "/S", "B-" + name + "/W"]
        prior_created = common
        for offset, obj in enumerate(objects):
            if not _object(obj, relative=relatives[offset], role=("G", "B", "S", "W")[offset],
                           order=len(expected_history) + offset + 1, complete=complete, errors=errors): continue
            for clock in ("mono", "boot"):
                at = obj[f"created_{clock}_ns"]
                if not window[f"start_{clock}_ns"] <= at <= window[f"deadline_{clock}_ns"]:
                    errors.append("object created outside original phase")
                if at < prior_created[f"created_{clock}_ns"]:
                    errors.append("object creation clocks contradict fixed original order")
                if row["before"] is not None and at > row["before"][clock + "_ns"]:
                    errors.append("object created after original before sample")
                if previous is not None and at < previous["retirement"][f"end_{clock}_ns"]:
                    errors.append("object created before prior original retirement")
            prior_created = obj
        expected_history.extend(objects)
        groups = {o["relative"]: o for o in [common] + objects}
        if len(groups) != len(objects) + 1 or len({(o["dev"], o["ino"]) for o in groups.values()}) != len(groups):
            errors.append("simultaneously visible object alias")
        for boundary in ("before", "after"):
            sample = row[boundary]
            if sample is not None:
                _sample(sample, generation=name, boundary=boundary, groups=groups, errors=errors)
                expected_observations.append(sample)
                e = sample["cgroups"].get("E") if isinstance(sample.get("cgroups"), dict) else None
                if e and last_e:
                    for counter in ("cpu_stat", "memory_events", "pids_events"):
                        if any(key not in e[counter] or e[counter][key] < count for key, count in last_e[counter].items()):
                            errors.append("common E cumulative counters regressed")
                    for peak in ("memory_peak", "pids_peak"):
                        if last_e[peak] is not None and (e[peak] is None or e[peak] < last_e[peak]):
                            errors.append("common E peak observation reset")
                if e: last_e = e
        native = natives[index] if index < len(natives) else None
        helper = row["helper"]
        helper_complete = False
        if helper is not None:
            keys = {"exit_observed", "rc", "stdout_eof", "stderr_eof", "deadline_met", "pending", "started_mono_ns", "started_boot_ns", "end_mono_ns", "end_boot_ns"}
            if _shape(helper, keys, "original helper capture", errors):
                if any(type(helper[k]) is not bool for k in ("exit_observed", "stdout_eof", "stderr_eof", "deadline_met", "pending")) or helper["rc"] is not None and not _wait_code(helper["rc"]):
                    errors.append("original helper flags/exit")
                for clock in ("mono", "boot"):
                    start, end = helper[f"started_{clock}_ns"], helper[f"end_{clock}_ns"]
                    if not _integer(start, 1) or not _integer(end, 1) or end < start:
                        errors.append("original helper clock")
                    if row["before"] is not None and row["after"] is not None and not row["before"][clock + "_ns"] <= start <= end <= row["after"][clock + "_ns"]:
                        errors.append("helper outside original resource samples")
                helper_complete = bool(helper["exit_observed"] and helper["stdout_eof"] and helper["stderr_eof"] and helper["deadline_met"] and not helper["pending"] and helper["rc"] is not None)
        native_ok = False
        if native is not None:
            nerrors = validate_native(native)
            errors.extend(name + ": " + e for e in nerrors)
            if not nerrors:
                if row["native"] != {k: native[k] for k in ("schema_version", "generation", "kind", "case_id")} or native["generation"] != name:
                    errors.append("native generation reference mismatch")
                if len(objects) != 4 or helper is None or row["before"] is None or row["after"] is None:
                    errors.append("native lacks complete original generation/capture/samples")
                else:
                    expected_rc = {"OBSERVED": 0, "UNSUPPORTED": 2, "UNKNOWN_RETAINED": 3}[native["status"]]
                    if helper["rc"] != expected_rc:
                        errors.append("original helper exit contradicts native status")
                    for clock in ("mono", "boot"):
                        if not helper[f"started_{clock}_ns"] <= native[f"start_{clock}_ns"] <= native[f"end_{clock}_ns"] <= helper[f"end_{clock}_ns"]:
                            errors.append("native outside original helper capture")
                    events = native["events"]
                    for event_name, relative in zip(("e_identity", "g_identity", "b_identity", "s_identity", "w_identity"), ["E"] + relatives):
                        found = [e for e in events if e["event"] == event_name]
                        if len(found) != 1 or (found[0]["a"], found[0]["b"]) != (groups[relative]["dev"], groups[relative]["ino"]) or found[0]["c"] & 0o170000 != 0o040000:
                            errors.append(name + ": held object identity not bound to this generation")
                    # An explicitly observed pre-arm failure is structurally retainable,
                    # but supplies no launcher/account identity and never qualifies.
                    creds = [e for e in events if e["event"] == "s_credentials"]
                    early = any(e["event"] in ("s_exit_before_arm", "s_arm_rejected") for e in events)
                    if name != "PROBE" and not early and (len(creds) != 1 or (creds[0]["a"], creds[0]["b"]) != (account["uid"], account["gid"])):
                        errors.append(name + ": launcher/account binding missing")
                    if creds and (len(creds) != 1 or (creds[0]["a"], creds[0]["b"]) != (account["uid"], account["gid"])):
                        errors.append(name + ": contradictory launcher/account binding")
                    if name == "PROBE":
                        armed = [e for e in events if e["event"] == "probe_armed"]
                        if len(armed) != 1 or armed[0]["a"] != account["uid"]:
                            errors.append("probe/account binding missing")
                native_ok = derive_capability(native)["supported"] if name == "PROBE" else derive_case(native)["case_expectation_met"]
        elif row["native"] is not None:
            errors.append("native generation reference without original receipt")
        retired = _retirement(row, errors=errors)
        if retired and (not helper_complete or row["before"] is None or row["after"] is None):
            errors.append("retired generation lacks original helper completion/captures")
        if retired:
            for clock in ("mono", "boot"):
                if row["retirement"][f"end_{clock}_ns"] > window[f"deadline_{clock}_ns"]:
                    errors.append("retirement outside original phase deadline")
        bill = report["budget"].get("prep_elapsed_seconds" if name == "PROBE" else "cases_elapsed_seconds")
        for clock in ("mono", "boot"):
            observed_end = max([obj[f"created_{clock}_ns"] for obj in objects] +
                               [row["retirement"][f"end_{clock}_ns"], window[f"start_{clock}_ns"]])
            if not _number(bill) or observed_end - window[f"start_{clock}_ns"] > (bill + 1e-9) * 1e9:
                errors.append("generation actual phase span exceeds original stage bill")
        previous_continues = bool(retired and native_ok and helper_complete)
        previous = row
    if expected_history != history:
        errors.append("append-only exact created-object history differs from ledger")
    if fixture["resource_observations"] != expected_observations:
        errors.append("resource observation history differs from original generation samples")
    if len(natives) > len(rows):
        errors.append("native receipt without generation")
    return errors

def _continuation() -> Any:
    spec = importlib.util.spec_from_file_location(__name__ + "_continuation_v2", Path(__file__).with_name("continuation_v2.py"))
    if spec is None or spec.loader is None: raise ReceiptError("continuation v2 unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_report(report: Any) -> list[str]:
    errors: list[str] = []
    v._bounded(report)
    size = v._v2_encoding_size(report)
    if not _shape(report, TOP_KEYS, "report v3", errors): return errors
    r = report
    if type(r["schema_version"]) is not int or r["schema_version"] != 3: errors.append("report v3 version")
    if r["status"] not in v.STATUSES or not _text(r["reason"], 512): errors.append("report v3 status/reason")
    if not _shape(r["source"], SOURCE_KEYS, "source v3", errors): return errors
    source = r["source"]
    c = _continuation()
    pins = [source[k] for k in ("expected_commit", "github_sha", "head")]
    if any(not _hex(pin, 40) for pin in pins) or len(set(pins)) != 1: errors.append("source exact D mismatch")
    expected_authority = {"approved_A": v.APPROVED_A, "closure_C": v.CLOSURE_C,
        "approved_continuation_A": v.APPROVED_CONTINUATION_A, "closure_continuation_C": v.CLOSURE_CONTINUATION_C,
        "approved_r2_continuation_A": c.CONTINUATION_A, "closure_r2_continuation_C": c.CONTINUATION_C}
    if any(source[k] != val for k, val in expected_authority.items()): errors.append("source exact authorization mismatch")
    closure = source["closure_sha256"]
    required = v.REQUIRED_CONTINUATION_SOURCE_PATHS | c.REQUIRED_SOURCE_PATHS | {
        v.SOURCE_DIR + "receipt_v3.py", v.SOURCE_DIR + "test_receipt_v3.py"}
    if not isinstance(closure, dict) or len(closure) > 64 or not required <= closure.keys():
        errors.append("source v3 closure mandatory paths/bound")
    elif any(not isinstance(path, str) or path.startswith("/") or ".." in path.split("/") or not _hex(sha, 64) for path, sha in closure.items()):
        errors.append("source v3 closure path/digest")
    else:
        pinned = {**{v.DOCUMENT_DIR + key: val for key, val in v.DOCUMENT_HASHES.items()},
                  **{v.CONTINUATION_DOCUMENT_DIR + key: val for key, val in v.CONTINUATION_DOCUMENT_HASHES.items()},
                  **c.PINNED_DOCUMENTS, **c.PINNED_FACTS}
        if any(closure.get(path) != sha for path, sha in pinned.items()): errors.append("source v3 pinned bytes differ")
    if _shape(r["run"], {"id", "attempt", "round"}, "run", errors):
        if (not isinstance(r["run"]["id"], str) or re.fullmatch(r"[1-9][0-9]{0,19}", r["run"]["id"]) is None or
                type(r["run"]["attempt"]) is not int or r["run"]["attempt"] != 1 or
                type(r["run"]["round"]) is not int or r["run"]["round"] != 3): errors.append("run v3 exact final round/attempt")
    if not isinstance(r["limits"], dict) or r["limits"] != LIMITS or any(type(r["limits"].get(k)) is not type(val) for k, val in LIMITS.items()):
        errors.append("approved limits changed")
    pkeys = {"runner_environment", "runner_os", "runner_arch", "image_os", "image_version", "kernel", "kernel_version", "machine", "python", "compiler", "uid", "euid", "cap_eff", "cap_bnd", "no_new_privs", "seccomp", "boot_id", "cgroup_mount", "cgroup_parent_controllers", "cgroup_parent_subtree_control", "os_release", "native_sha256", "fixture"}
    if _shape(r["provenance"], pkeys, "provenance v3", errors):
        p = r["provenance"]
        if not _text(p["kernel_version"], 1024): errors.append("kernel version byte bound")
        if r["generations"] or r["capability"] is not None or r["cases"]:
            if (p["runner_environment"], p["runner_os"], p["runner_arch"], p["machine"], p["image_os"]) != ("github-hosted", "Linux", "X64", "x86_64", "ubuntu24") or p["os_release"] != {"id": "ubuntu", "version_id": "24.04"}:
                errors.append("fixture v3 platform")
            if type(p["uid"]) is not int or p["uid"] != 0 or type(p["euid"]) is not int or p["euid"] != 0 or not _hex(p["native_sha256"], 64): errors.append("fixture v3 build/identity")
            if any(not _text(p[k], 4096, empty=False) for k in ("image_version", "kernel", "kernel_version", "python", "boot_id", "cgroup_mount", "cap_eff", "cap_bnd")):
                errors.append("fixture v3 provenance incomplete")
            if not isinstance(p["compiler"], dict) or not p["compiler"].get("path") or not p["compiler"].get("version"): errors.append("fixture v3 compiler missing")
            for key in ("cgroup_parent_controllers", "cgroup_parent_subtree_control"):
                if not isinstance(p[key], list) or any(not isinstance(x, str) for x in p[key]) or not {"cpu", "memory", "pids"} <= set(p[key]): errors.append("fixture v3 parent controller availability")
    budget_keys = {"prep_elapsed_seconds", "cases_elapsed_seconds", "cleanup_elapsed_seconds", "diagnostic_bytes", "report_bytes", "file_logical_bytes", "file_count", "allocated_bytes", "inode_count", "suite_stream_bytes"}
    if _shape(r["budget"], budget_keys, "budget", errors):
        for key, val in r["budget"].items():
            if not _number(val) or not key.endswith("_elapsed_seconds") and not _integer(val): errors.append("budget value type")
            bound = LIMITS.get(key.replace("_elapsed", ""), LIMITS.get(key))
            if _number(val) and bound is not None and val > bound: errors.append("budget exceeded: " + key)
        if r["budget"]["report_bytes"] != size: errors.append("report v3 complete encoding byte bill mismatch")
    cleanup = r["cleanup"]
    if _shape(cleanup, {"verified", "records", "residuals"}, "cleanup", errors):
        if type(cleanup["verified"]) is not bool or not isinstance(cleanup["records"], list) or not isinstance(cleanup["residuals"], list): errors.append("cleanup field types")
        else:
            names = [record.get("object") if isinstance(record, dict) else None for record in cleanup["records"]]
            if any(not isinstance(name, str) for name in names) or len(names) != len(set(names)): errors.append("cleanup duplicate/invalid object")
            if cleanup["verified"]:
                if cleanup["residuals"] or any(not isinstance(x, dict) or x.get("identity_match") is not True or x.get("removed") is not True for x in cleanup["records"]): errors.append("cleanup missing original removal facts")
                prefix = f"q2-h07-{r['run']['id']}-1-r3"
                expected = {prefix, "dedicated-account", "build/helper"} if r["generations"] else set()
                for row in r["generations"]:
                    retired_names = {record["relative"] for record in row["retirement"]["records"] if record.get("identity_match") is True and record.get("empty") is True and record.get("removed") is True and record.get("fd_closed") is True}
                    expected |= {prefix + "/" + obj["relative"] for obj in row["objects"] if obj["relative"] not in retired_names}
                    if any(prefix + "/" + name in names for name in retired_names): errors.append("cleanup repeats already retired original object")
                if not expected <= set(names) or any(re.fullmatch(r"original-subprocess-[1-9][0-9]*", name) is None for name in set(names) - expected): errors.append("cleanup exact active registered object coverage")
    cases = r["cases"]
    if not isinstance(cases, list) or len(cases) > 6: return errors + ["case count"]
    if [item.get("case_id") if isinstance(item, dict) else None for item in cases] != list(GENERATIONS[1:len(cases) + 1]): errors.append("case exact order")
    native_errors = []
    for native in ([r["capability"]] if r["capability"] is not None else []) + cases:
        native_errors.extend(validate_native(native))
    errors.extend(native_errors)
    if not native_errors:
        if r["budget"].get("suite_stream_bytes") != sum(s["bytes"] for case in cases for s in case["streams"].values()): errors.append("suite stream bill mismatch")
        errors.extend(validate_generations(r))
    errors.extend(validate_failures(r))
    account = v._support_module("account_evidence")
    account_errors = account.validate_account_setup(r["account_setup"], run=r["run"], fixture_account=r["provenance"]["fixture"]["account"], cleanup=cleanup)
    errors.extend("account_setup: " + e for e in account_errors)
    if not account_errors: errors.extend(_bind_account_budget(r, account))
    facts = account.account_setup_facts(r["account_setup"])
    if (r["capability"] is not None or cases) and (facts["errors"] or facts["admitted"] is not True): errors.append("native work without admitted account")
    errors.extend("continuation: " + e for e in c.validate_continuation(r["continuation"], run=r["run"], source=source, provenance=r["provenance"]))
    return errors


def validate_report(report: Any) -> list[str]:
    """Fail closed for malformed direct values as well as decoded JSON."""
    try:
        return _validate_report(report)
    except (ReceiptError, OSError, ImportError, KeyError, TypeError, ValueError, AttributeError, OverflowError, RecursionError) as exc:
        return ["malformed report v3 or unavailable validator: " + type(exc).__name__]


def derive_report(report: Any) -> dict[str, Any]:
    errors = validate_report(report)
    if errors:
        return {"status": "REJECTED", "errors": errors, "case_results": [], "evidence_basis": "INPUT_CONSISTENCY_ONLY"}
    results = [derive_case(case) for case in report["cases"]]
    supported = bool(report["capability"] and derive_capability(report["capability"])["supported"])
    facts = v._account_facts(report)
    full = (supported and not facts["errors"] and facts["admitted"] is True and facts["cleanup_verified"] is True and
            len(results) == 6 and all(c["case_expectation_met"] for c in results) and
            len(report["generations"]) == 7 and all(g["state"] == "RETIRED" and g["retirement"]["verified"] for g in report["generations"]) and
            report["cleanup"]["verified"] and report["primary_failure"] is None and not report["validation_errors"]["items"] and not report["validation_errors"]["exceeded"] and not report["reason"])
    if full:
        status = "QUALIFIED_IN_FIXTURE"
    elif any(c["classification"] == "INCONCLUSIVE" for c in results): status = "INCONCLUSIVE"
    elif not results and report["status"] in ("UNSUPPORTED", "REJECTED"): status = report["status"]
    else: status = "UNKNOWN_RETAINED"
    if report["status"] == "QUALIFIED_IN_FIXTURE" and status != "QUALIFIED_IN_FIXTURE": errors.append("qualification claim not established by retained evidence")
    return {"status": status, "errors": errors, "case_results": results, "evidence_basis": "INPUT_CONSISTENCY_ONLY"}


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
    # Retirement consumes preparation/cases time before final account cleanup.
    # A failed retirement still has an original observed end; this ordering does
    # not require a successful seal or manufacture retirement/cleanup credit.
    if cleanup and report["generations"]:
        for clock in ("mono", "boot"):
            earliest_cleanup = min(a[f"start_{clock}_ns"] for a in cleanup)
            latest_retirement = max(row["retirement"][f"end_{clock}_ns"]
                                    for row in report["generations"])
            if earliest_cleanup < latest_retirement:
                errors.append("account cleanup preceded recorded generation retirement: " + clock)
    return errors

