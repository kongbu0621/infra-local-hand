"""One approved CPUQuota retry: immutable clock bounds and finite transport.

This test-only helper neither opens SSH nor chooses machine paths. Its caller
owns one create-only host reservation, one probe and one runtime delivery.
A final read-only collection may use the same remaining window and byte pool.
Nonzero client exit with both EOFs is complete capture of a failed command, not
lost evidence; transport completion never grants Q2 acceptance or remote stop.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import time

NS = 10**9
HOST_NS = 300 * NS
GUEST_NS = 270 * NS
PREPARATION_NS = 140 * NS
OWNER_NS = 120 * NS
STOP_NS = 3 * NS
FINALIZATION_NS = 5 * NS
OUTPUT_LIMIT = 2 * 1024**2
DOCUMENT_LIMIT = 16384
ANCHOR_SCHEMA = "local-hand-q2-cpuquota-retry-clock-anchor/v1"
ENVELOPE_SCHEMA = "local-hand-q2-cpuquota-retry-delivery/v1"
CAPTURE_SCHEMA = "local-hand-q2-cpuquota-retry-client-capture/v1"
REPORT_SCHEMA = "local-hand-q2-cpuquota-retry-transport/v1"
ANCHOR_FIELDS = {"schema", "host_issued_ns", "host_deadline_ns", "host_probe_send_ns", "host_probe_receive_ns",
                 "guest_boot_id", "guest_sample_ns", "guest_outer_deadline_ns", "sampling_margin_ns"}
ENVELOPE_FIELDS = {"schema", "attempt_id", "boot_id", "issued_ns", "preparation_deadline_ns", "deadline_ns",
                   "guest_outer_deadline_ns", "clock_anchor_sha256", "stop_ns"}


def require(value, code):
    if not value:
        raise ValueError(code)


def number(value, low=0, high=2**63-1):
    require(type(value) is int and low <= value <= high, "RETRY_DELIVERY_INTEGER")
    return value


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), "RETRY_DELIVERY_FIELDS")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def document(raw):
    require(type(raw) is bytes and 0 < len(raw) <= DOCUMENT_LIMIT, "RETRY_DELIVERY_DOCUMENT_SIZE")
    def pairs(items):
        value = {}
        for key, child in items:
            require(key not in value, "RETRY_DELIVERY_DUPLICATE_KEY")
            value[key] = child
        return value
    def noninteger(value):
        raise ValueError("RETRY_DELIVERY_JSON_NUMBER")
    value = json.loads(raw, object_pairs_hook=pairs, parse_float=noninteger, parse_constant=noninteger)
    require(type(value) is dict, "RETRY_DELIVERY_DOCUMENT")
    return value


def token(value):
    require(type(value) is str and re.fullmatch(r"[a-z][a-z0-9]{7,31}", value), "RETRY_DELIVERY_ATTEMPT")
    return value


def boot(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value),
            "RETRY_DELIVERY_BOOT")
    return value


def host_window(issued_ns, deadline_ns):
    number(issued_ns, 1); number(deadline_ns, issued_ns + 1)
    require(deadline_ns - issued_ns <= HOST_NS, "RETRY_DELIVERY_HOST_WINDOW")


def make_clock_anchor(*, host_issued_ns, host_deadline_ns, host_probe_send_ns, host_probe_receive_ns,
                      guest_boot_id, guest_sample_ns, expected_boot_id):
    """Pin exactly one probe with conservative receive-based remaining time."""
    host_window(host_issued_ns, host_deadline_ns)
    for value in (host_probe_send_ns, host_probe_receive_ns, guest_sample_ns):
        number(value, 1)
    boot(guest_boot_id)
    require(guest_boot_id == expected_boot_id, "RETRY_DELIVERY_BOOT")
    require(host_issued_ns <= host_probe_send_ns <= host_probe_receive_ns < host_deadline_ns,
            "RETRY_DELIVERY_HOST_WINDOW")
    remaining = host_deadline_ns - host_probe_receive_ns - 2 * NS
    require(remaining > 10 * NS, "RETRY_DELIVERY_PROBE_TIME_EXHAUSTED")
    number(guest_sample_ns + remaining, 1)
    return dict(schema=ANCHOR_SCHEMA, host_issued_ns=host_issued_ns, host_deadline_ns=host_deadline_ns,
                host_probe_send_ns=host_probe_send_ns, host_probe_receive_ns=host_probe_receive_ns,
                guest_boot_id=guest_boot_id, guest_sample_ns=guest_sample_ns,
                guest_outer_deadline_ns=guest_sample_ns + remaining, sampling_margin_ns=2 * NS)


def validate_clock_anchor(anchor):
    keys(anchor, ANCHOR_FIELDS)
    args = {key: anchor[key] for key in ("host_issued_ns", "host_deadline_ns", "host_probe_send_ns",
                                        "host_probe_receive_ns", "guest_boot_id", "guest_sample_ns")}
    require(make_clock_anchor(**args, expected_boot_id=anchor["guest_boot_id"]) == anchor,
            "RETRY_DELIVERY_ANCHOR_CHANGED")
    return anchor


def guest_envelope(anchor, *, attempt_id, guest_boot_id, guest_now_ns):
    """Issue once on guest entry, before staging or old-state evidence reads."""
    validate_clock_anchor(anchor); number(guest_now_ns, 1); token(attempt_id)
    require(guest_boot_id == anchor["guest_boot_id"], "RETRY_DELIVERY_BOOT")
    end = min(guest_now_ns + GUEST_NS, anchor["guest_outer_deadline_ns"] - 10 * NS)
    funded_owner = OWNER_NS + STOP_NS + FINALIZATION_NS
    require(anchor["guest_sample_ns"] <= guest_now_ns < end and end - guest_now_ns > funded_owner,
            "RETRY_DELIVERY_GUEST_TIME_EXHAUSTED")
    return dict(schema=ENVELOPE_SCHEMA, attempt_id=attempt_id, boot_id=guest_boot_id, issued_ns=guest_now_ns,
                preparation_deadline_ns=min(guest_now_ns + PREPARATION_NS, end - funded_owner),
                deadline_ns=end, guest_outer_deadline_ns=anchor["guest_outer_deadline_ns"],
                clock_anchor_sha256=sha(encoded(anchor)), stop_ns=STOP_NS)


def first_clock():
    """Sample MONOTONIC before BOOTTIME; conservative offset survives suspension."""
    return dict(monotonic_ns=time.monotonic_ns(), boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME))


def validate_delivery(raw, digest, attempt_id, entry, *, boot_id=None):
    """Validate a pinned bootstrap envelope; no new issuance at driver entry."""
    require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) and sha(raw) == digest,
            "RETRY_DELIVERY_DIGEST")
    value = document(raw); keys(value, ENVELOPE_FIELDS); token(attempt_id)
    require(value["schema"] == ENVELOPE_SCHEMA and value["attempt_id"] == attempt_id,
            "RETRY_DELIVERY_BINDING")
    boot(value["boot_id"])
    for key in ("issued_ns", "preparation_deadline_ns", "deadline_ns", "guest_outer_deadline_ns", "stop_ns"):
        number(value[key], 1)
    require(type(value["clock_anchor_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["clock_anchor_sha256"]),
            "RETRY_DELIVERY_ANCHOR_DIGEST")
    require(value["issued_ns"] < value["deadline_ns"] <= value["issued_ns"] + GUEST_NS
            and value["guest_outer_deadline_ns"] >= value["deadline_ns"] + 10 * NS
            and value["stop_ns"] == STOP_NS, "RETRY_DELIVERY_GUEST_BUDGET")
    require(value["issued_ns"] < value["preparation_deadline_ns"] <= value["issued_ns"] + PREPARATION_NS
            and value["preparation_deadline_ns"] + OWNER_NS + STOP_NS + FINALIZATION_NS <= value["deadline_ns"],
            "RETRY_DELIVERY_PREPARATION_BUDGET")
    number(entry["monotonic_ns"], 1); number(entry["boottime_ns"], 1)
    require(value["issued_ns"] <= entry["boottime_ns"] < value["preparation_deadline_ns"],
            "RETRY_DELIVERY_PREPARATION_EXPIRED")
    if boot_id is None:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    require(boot_id == value["boot_id"], "RETRY_DELIVERY_BOOT")
    return value


def remaining(envelope, anchor, *, guest_boot_id, guest_now_ns, owner_runtime_ns=OWNER_NS):
    keys(envelope, ENVELOPE_FIELDS)
    require(guest_envelope(anchor, attempt_id=envelope["attempt_id"], guest_boot_id=envelope["boot_id"],
                           guest_now_ns=envelope["issued_ns"]) == envelope, "RETRY_DELIVERY_ENVELOPE_CHANGED")
    number(guest_now_ns, 1); number(owner_runtime_ns, 1, OWNER_NS)
    require(guest_boot_id == envelope["boot_id"], "RETRY_DELIVERY_BOOT")
    require(envelope["issued_ns"] <= guest_now_ns < envelope["preparation_deadline_ns"]
            and guest_now_ns + owner_runtime_ns + STOP_NS + FINALIZATION_NS < envelope["deadline_ns"],
            "RETRY_DELIVERY_ISSUANCE_TIME_EXHAUSTED")
    return envelope["deadline_ns"] - guest_now_ns


def preparation_window(envelope, entry):
    """Include bootstrap time already spent; never start a fresh 140 seconds."""
    number(entry["monotonic_ns"], 1); number(entry["boottime_ns"], 1)
    offset = entry["monotonic_ns"] - entry["boottime_ns"]
    issued = envelope["issued_ns"] + offset
    deadline = envelope["preparation_deadline_ns"] + offset
    require(0 < issued <= entry["monotonic_ns"] < deadline and deadline - issued <= PREPARATION_NS,
            "RETRY_DELIVERY_PREPARATION_EXPIRED")
    return issued, deadline


def preparation_guard(original_guard, envelope, clock):
    def guard():
        original_guard()
        now = clock()
        require(now["boot_id"] == envelope["boot_id"], "RETRY_DELIVERY_BOOT")
        number(now["boottime_ns"], 1)
        require(envelope["issued_ns"] <= now["boottime_ns"] < envelope["preparation_deadline_ns"],
                "RETRY_DELIVERY_PREPARATION_EXPIRED")
    return guard


def owner_admission(settings, envelope, now, entry):
    require(now["boot_id"] == envelope["boot_id"], "RETRY_DELIVERY_BOOT")
    number(now["boottime_ns"], 1); number(entry["boottime_ns"], 1)
    require(envelope["issued_ns"] <= entry["boottime_ns"] <= now["boottime_ns"] < envelope["preparation_deadline_ns"],
            "RETRY_DELIVERY_PREPARATION_EXPIRED")
    duration = number(settings["owner"]["runtime_ns"], 1, OWNER_NS)
    require(now["boottime_ns"] + duration + STOP_NS + FINALIZATION_NS < envelope["deadline_ns"],
            "RETRY_DELIVERY_OWNER_TIME_UNFUNDED")
    return duration


def transport():
    path = Path(__file__).with_name("q2_prepare_delivery.py")
    spec = importlib.util.spec_from_file_location("_retry_delivery_transport", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def capture_once(argv, *, host_issued_ns, host_deadline_ns, stdout_path, stderr_path,
                 stdin_path=None, prior_captured_bytes=0, deadline_ns=None, output_limit=None):
    """One finite client; charge probe and guest output to the same 2 MiB pool.

    The host reservation is caller-owned. Output paths are create-only in the
    reused transport, so a second call with the same phase paths is rejected.
    """
    host_window(host_issued_ns, host_deadline_ns)
    number(prior_captured_bytes, 0, OUTPUT_LIMIT)
    end = host_deadline_ns if deadline_ns is None else number(deadline_ns, host_issued_ns + 1, host_deadline_ns)
    available = OUTPUT_LIMIT - prior_captured_bytes
    limit = available if output_limit is None else number(output_limit, 1024, available)
    require(limit >= 1024, "RETRY_DELIVERY_TOTAL_OUTPUT_BUDGET")
    result = transport().capture(argv, issued_ns=host_issued_ns, deadline_ns=end, output_limit=limit,
                                 stdout_path=stdout_path, stderr_path=stderr_path, stdin_path=stdin_path)
    # Legacy capture.complete deliberately required rc=0. Keep that source fact
    # while distinguishing a complete observed nonzero exit from missing EOF.
    transport_complete = (type(result["started_ns"]) is int and type(result["returncode"]) is int
                          and result["eof"] == ["stderr", "stdout"] and result["error"] is None
                          and result["within_original_deadline"] is True)
    return {**result, "schema": CAPTURE_SCHEMA, "legacy_capture_complete": result["complete"],
            "complete": transport_complete, "command_succeeded": transport_complete and result["returncode"] == 0,
            "status": "CAPTURED" if transport_complete else "INCOMPLETE",
            "host_issued_ns": host_issued_ns, "host_deadline_ns": host_deadline_ns,
            "prior_captured_bytes": prior_captured_bytes,
            "total_captured_bytes": prior_captured_bytes + result["captured_bytes"]}


def final_report(*, attempt_id, host_issued_ns, host_deadline_ns, probe_capture=None,
                 guest_capture=None, collect_capture=None, finished_ns=None, error=None):
    """Report the original clients only; runtime seals receive separate review."""
    token(attempt_id); host_window(host_issued_ns, host_deadline_ns)
    finished = time.monotonic_ns() if finished_ns is None else number(finished_ns, host_issued_ns)
    captures = [value for value in (probe_capture, guest_capture, collect_capture) if value is not None]
    total = 0
    for value in captures:
        require(value["schema"] == CAPTURE_SCHEMA and value["host_issued_ns"] == host_issued_ns
                and value["host_deadline_ns"] == host_deadline_ns
                and value["prior_captured_bytes"] == total, "RETRY_DELIVERY_CAPTURE_BINDING")
        total += number(value["captured_bytes"], 0, OUTPUT_LIMIT)
        require(total == value["total_captured_bytes"] and total <= OUTPUT_LIMIT, "RETRY_DELIVERY_TOTAL_OUTPUT_BUDGET")
    within = host_issued_ns <= finished <= host_deadline_ns
    complete = (probe_capture is not None and guest_capture is not None
                and all(value["complete"] is True for value in captures) and within)
    success = complete and all(value["command_succeeded"] is True for value in captures) and error is None
    return dict(schema=REPORT_SCHEMA, attempt_id=attempt_id, status="CAPTURED" if success else "INCOMPLETE",
                original_clients_capture_complete=complete, original_clients_succeeded=success,
                issued_ns=host_issued_ns, deadline_ns=host_deadline_ns, finished_ns=finished,
                within_management_deadline=within, total_captured_bytes=total, error=error,
                probe_capture=probe_capture, guest_capture=guest_capture, collect_capture=collect_capture,
                evidence_retained=True, replay_allowed=False,
                capture_status_scope="TRANSPORT_ONLY; RUNTIME_SEAL_AND_PRESERVATION_REQUIRE_SEPARATE_REVIEW",
                remote_stop_proven=False, q2_accepted=False, q3_accepted=False, production_supported=False)


def main():
    print(encoded(dict(schema=REPORT_SCHEMA, status="BLOCKED", reason="EXPLICIT_APPROVED_ONE_SHOT_INPUT_REQUIRED",
                       replay_allowed=False, q2_accepted=False, q3_accepted=False,
                       production_supported=False)).decode(), end="")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
