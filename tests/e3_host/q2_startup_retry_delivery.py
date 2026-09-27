"""One approved supervisor-startup retry: immutable clock bounds and finite transport.

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
import os
import selectors
import signal
import stat
import subprocess
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
ANCHOR_SCHEMA = "local-hand-q2-supervisor-startup-retry-clock-anchor/v1"
ENVELOPE_SCHEMA = "local-hand-q2-supervisor-startup-retry-delivery/v1"
CAPTURE_SCHEMA = "local-hand-q2-supervisor-startup-retry-client-capture/v1"
REPORT_SCHEMA = "local-hand-q2-supervisor-startup-retry-transport/v1"
ANCHOR_FIELDS = {"schema", "host_issued_ns", "host_deadline_ns", "host_probe_send_ns", "host_probe_receive_ns",
                 "guest_boot_id", "guest_sample_ns", "guest_outer_deadline_ns", "sampling_margin_ns"}
ENVELOPE_FIELDS = {"schema", "attempt_id", "boot_id", "issued_ns", "preparation_deadline_ns", "deadline_ns",
                   "guest_outer_deadline_ns", "clock_anchor_sha256", "stop_ns"}


def require(value, code):
    if not value:
        raise ValueError(code)


def number(value, low=0, high=2**63-1):
    require(type(value) is int and low <= value <= high, "STARTUP_RETRY_DELIVERY_INTEGER")
    return value


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), "STARTUP_RETRY_DELIVERY_FIELDS")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def document(raw, *, maximum=DOCUMENT_LIMIT):
    number(maximum, 1, OUTPUT_LIMIT)
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "STARTUP_RETRY_DELIVERY_DOCUMENT_SIZE")
    def pairs(items):
        value = {}
        for key, child in items:
            require(key not in value, "STARTUP_RETRY_DELIVERY_DUPLICATE_KEY")
            value[key] = child
        return value
    def noninteger(value):
        raise ValueError("STARTUP_RETRY_DELIVERY_JSON_NUMBER")
    value = json.loads(raw, object_pairs_hook=pairs, parse_float=noninteger, parse_constant=noninteger)
    require(type(value) is dict, "STARTUP_RETRY_DELIVERY_DOCUMENT")
    return value


def token(value):
    require(type(value) is str and re.fullmatch(r"[a-z][a-z0-9]{7,31}", value), "STARTUP_RETRY_DELIVERY_ATTEMPT")
    return value


def boot(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value),
            "STARTUP_RETRY_DELIVERY_BOOT")
    return value


def host_window(issued_ns, deadline_ns):
    number(issued_ns, 1); number(deadline_ns, issued_ns + 1)
    require(deadline_ns - issued_ns <= HOST_NS, "STARTUP_RETRY_DELIVERY_HOST_WINDOW")


def validate_host_clock(*, issued_ns, deadline_ns, boottime_issued_ns, monotonic_now_ns, boottime_now_ns):
    """Fail closed when host suspension would invalidate the single mapping.

    The anchor already subtracts a fixed two-second sampling margin. Only a
    clock difference within that exact margin may proceed; a longer suspension
    cannot donate MONOTONIC-only time to a fresh remote service.
    """
    host_window(issued_ns, deadline_ns)
    number(boottime_issued_ns, 1); number(monotonic_now_ns, issued_ns)
    number(boottime_now_ns, boottime_issued_ns)
    mono_elapsed = monotonic_now_ns - issued_ns
    boot_elapsed = boottime_now_ns - boottime_issued_ns
    require(abs(boot_elapsed - mono_elapsed) <= 2 * NS, "STARTUP_RETRY_DELIVERY_HOST_CLOCK_DIVERGED")
    require(monotonic_now_ns < deadline_ns and boot_elapsed < deadline_ns - issued_ns,
            "STARTUP_RETRY_DELIVERY_HOST_EXPIRED")
    return dict(monotonic_elapsed_ns=mono_elapsed, boottime_elapsed_ns=boot_elapsed,
                sampling_margin_ns=2 * NS)


def make_clock_anchor(*, host_issued_ns, host_deadline_ns, host_probe_send_ns, host_probe_receive_ns,
                      guest_boot_id, guest_sample_ns, expected_boot_id):
    """Pin exactly one probe with conservative receive-based remaining time."""
    host_window(host_issued_ns, host_deadline_ns)
    for value in (host_probe_send_ns, host_probe_receive_ns, guest_sample_ns):
        number(value, 1)
    boot(guest_boot_id)
    require(guest_boot_id == expected_boot_id, "STARTUP_RETRY_DELIVERY_BOOT")
    require(host_issued_ns <= host_probe_send_ns <= host_probe_receive_ns < host_deadline_ns,
            "STARTUP_RETRY_DELIVERY_HOST_WINDOW")
    remaining = host_deadline_ns - host_probe_receive_ns - 2 * NS
    require(remaining > 10 * NS, "STARTUP_RETRY_DELIVERY_PROBE_TIME_EXHAUSTED")
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
            "STARTUP_RETRY_DELIVERY_ANCHOR_CHANGED")
    return anchor


def guest_envelope(anchor, *, attempt_id, guest_boot_id, guest_now_ns):
    """Issue once on guest entry, before staging or old-state evidence reads."""
    validate_clock_anchor(anchor); number(guest_now_ns, 1); token(attempt_id)
    require(guest_boot_id == anchor["guest_boot_id"], "STARTUP_RETRY_DELIVERY_BOOT")
    end = min(guest_now_ns + GUEST_NS, anchor["guest_outer_deadline_ns"] - 10 * NS)
    funded_owner = OWNER_NS + STOP_NS + FINALIZATION_NS
    require(anchor["guest_sample_ns"] <= guest_now_ns < end and end - guest_now_ns > funded_owner,
            "STARTUP_RETRY_DELIVERY_GUEST_TIME_EXHAUSTED")
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
            "STARTUP_RETRY_DELIVERY_DIGEST")
    value = document(raw); keys(value, ENVELOPE_FIELDS); token(attempt_id)
    require(value["schema"] == ENVELOPE_SCHEMA and value["attempt_id"] == attempt_id,
            "STARTUP_RETRY_DELIVERY_BINDING")
    boot(value["boot_id"])
    for key in ("issued_ns", "preparation_deadline_ns", "deadline_ns", "guest_outer_deadline_ns", "stop_ns"):
        number(value[key], 1)
    require(type(value["clock_anchor_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["clock_anchor_sha256"]),
            "STARTUP_RETRY_DELIVERY_ANCHOR_DIGEST")
    require(value["issued_ns"] < value["deadline_ns"] <= value["issued_ns"] + GUEST_NS
            and value["guest_outer_deadline_ns"] >= value["deadline_ns"] + 10 * NS
            and value["stop_ns"] == STOP_NS, "STARTUP_RETRY_DELIVERY_GUEST_BUDGET")
    require(value["issued_ns"] < value["preparation_deadline_ns"] <= value["issued_ns"] + PREPARATION_NS
            and value["preparation_deadline_ns"] + OWNER_NS + STOP_NS + FINALIZATION_NS <= value["deadline_ns"],
            "STARTUP_RETRY_DELIVERY_PREPARATION_BUDGET")
    number(entry["monotonic_ns"], 1); number(entry["boottime_ns"], 1)
    require(value["issued_ns"] <= entry["boottime_ns"] < value["preparation_deadline_ns"],
            "STARTUP_RETRY_DELIVERY_PREPARATION_EXPIRED")
    if boot_id is None:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    require(boot_id == value["boot_id"], "STARTUP_RETRY_DELIVERY_BOOT")
    return value


def remaining(envelope, anchor, *, guest_boot_id, guest_now_ns, owner_runtime_ns=OWNER_NS):
    keys(envelope, ENVELOPE_FIELDS)
    require(guest_envelope(anchor, attempt_id=envelope["attempt_id"], guest_boot_id=envelope["boot_id"],
                           guest_now_ns=envelope["issued_ns"]) == envelope, "STARTUP_RETRY_DELIVERY_ENVELOPE_CHANGED")
    number(guest_now_ns, 1); number(owner_runtime_ns, 1, OWNER_NS)
    require(guest_boot_id == envelope["boot_id"], "STARTUP_RETRY_DELIVERY_BOOT")
    require(envelope["issued_ns"] <= guest_now_ns < envelope["preparation_deadline_ns"]
            and guest_now_ns + owner_runtime_ns + STOP_NS + FINALIZATION_NS < envelope["deadline_ns"],
            "STARTUP_RETRY_DELIVERY_ISSUANCE_TIME_EXHAUSTED")
    return envelope["deadline_ns"] - guest_now_ns


def preparation_window(envelope, entry):
    """Include bootstrap time already spent; never start a fresh 140 seconds."""
    number(entry["monotonic_ns"], 1); number(entry["boottime_ns"], 1)
    offset = entry["monotonic_ns"] - entry["boottime_ns"]
    issued = envelope["issued_ns"] + offset
    deadline = envelope["preparation_deadline_ns"] + offset
    require(0 < issued <= entry["monotonic_ns"] < deadline and deadline - issued <= PREPARATION_NS,
            "STARTUP_RETRY_DELIVERY_PREPARATION_EXPIRED")
    return issued, deadline


def preparation_guard(original_guard, envelope, clock):
    def guard():
        original_guard()
        now = clock()
        require(now["boot_id"] == envelope["boot_id"], "STARTUP_RETRY_DELIVERY_BOOT")
        number(now["boottime_ns"], 1)
        require(envelope["issued_ns"] <= now["boottime_ns"] < envelope["preparation_deadline_ns"],
                "STARTUP_RETRY_DELIVERY_PREPARATION_EXPIRED")
    return guard


def owner_admission(settings, envelope, now, entry):
    require(now["boot_id"] == envelope["boot_id"], "STARTUP_RETRY_DELIVERY_BOOT")
    number(now["boottime_ns"], 1); number(entry["boottime_ns"], 1)
    require(envelope["issued_ns"] <= entry["boottime_ns"] <= now["boottime_ns"] < envelope["preparation_deadline_ns"],
            "STARTUP_RETRY_DELIVERY_PREPARATION_EXPIRED")
    duration = number(settings["owner"]["runtime_ns"], 1, OWNER_NS)
    require(now["boottime_ns"] + duration + STOP_NS + FINALIZATION_NS < envelope["deadline_ns"],
            "STARTUP_RETRY_DELIVERY_OWNER_TIME_UNFUNDED")
    return duration


def transport():
    path = Path(__file__).with_name("q2_prepare_delivery.py")
    spec = importlib.util.spec_from_file_location("_startup_retry_delivery_transport", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def _capture(argv, *, issued_ns, deadline_ns, boottime_issued_ns, output_limit, stdout_path, stderr_path, stdin_path=None):
    """Finite pipes use MONOTONIC and BOOTTIME so suspension spends the window.

    stdin is a finished regular file, never a producer pipe. Capture never retries
    the command or treats terminating an SSH client as stopping its remote tree.
    A collector failure returns INCOMPLETE even when a later client kill exits.
    """
    base = transport()
    boot_deadline = boottime_issued_ns + deadline_ns - issued_ns
    def original_deadline(start, end):
        base.original_deadline(start, end)
        require(boottime_issued_ns <= time.clock_gettime_ns(time.CLOCK_BOOTTIME) < boot_deadline,
                "STARTUP_RETRY_DELIVERY_HOST_SUSPENDED")
    original_deadline(issued_ns, deadline_ns)
    base.integer(output_limit, 1024, 16 * 1024 * 1024)
    require(type(argv) in (list, tuple) and 0 < len(argv) <= 64
            and all(type(s) is str and len(s) <= 65536 and "\0" not in s for s in argv), "DELIVERY_COMMAND")
    paths = [base.canonical(stdout_path), base.canonical(stderr_path)]
    require(paths[0] != paths[1] and not any(os.path.lexists(p) for p in paths), "DELIVERY_CAPTURE_EXISTS")
    incoming = None; input_identity = None; files = {}; proc = None; selector = selectors.DefaultSelector()
    eof = set(); total = 0; failure = None; started = None
    stop_reserve_ns = min(10**9, (deadline_ns-issued_ns)//5)
    try:
        if stdin_path is not None:
            input_path = base.canonical(stdin_path)
            require(input_path not in paths, "DELIVERY_CAPTURE_ALIAS")
            fd = os.open(input_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
            incoming = os.fdopen(fd, "rb")
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= base.CEILING,
                    "DELIVERY_STDIN_FILE")
            input_identity = tuple(getattr(info, key) for key in
                                   ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink"))
        for name, path in zip(("stdout", "stderr"), paths):
            files[name] = os.fdopen(base.new_file(path), "wb")
        original_deadline(issued_ns, deadline_ns)
        proc = subprocess.Popen(argv, stdin=incoming if incoming else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, start_new_session=True)
        started = time.monotonic_ns()
        for name in files:
            stream = getattr(proc, name); os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while len(eof) != 2 or proc.poll() is None:
            remaining = min(deadline_ns - time.monotonic_ns(),
                            boot_deadline - time.clock_gettime_ns(time.CLOCK_BOOTTIME))
            if remaining <= stop_reserve_ns:
                failure = "DELIVERY_CAPTURE_TIMEOUT"; break
            for key, _ in selector.select(min(0.05, remaining / 1e9)):
                block = os.read(key.fd, 65536)
                if not block:
                    eof.add(key.data); selector.unregister(key.fileobj); continue
                room = max(0, output_limit - total); kept = block[:room]
                files[key.data].write(kept); total += len(kept)
                if len(block) > room:
                    failure = "DELIVERY_CAPTURE_LIMIT"; break
            if failure:
                break
    except BaseException as error:
        failure = type(error).__name__
    finally:
        if proc is not None:
            # A fork can keep a stream open after the original client has exited.
            # On incomplete capture stop the original group regardless of poll().
            if failure or proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            try:
                # Even an already-expired/suspended client needs finite reap after
                # SIGKILL. This is containment only; the unchanged deadline and
                # BOOTTIME verdict remain expired, never a new delivery window.
                proc.wait(timeout=max(0.1, min(1, max(0, min(deadline_ns-time.monotonic_ns(),
                    boot_deadline-time.clock_gettime_ns(time.CLOCK_BOOTTIME))/1e9))))
            except subprocess.TimeoutExpired:
                failure = failure or "DELIVERY_CLIENT_EXIT_UNPROVEN"
            for name in ("stdout", "stderr"):
                stream = getattr(proc, name)
                if stream is not None:
                    stream.close()
        selector.close()
        if incoming is not None:
            info = os.fstat(incoming.fileno())
            if input_identity is not None and input_identity != tuple(getattr(info, key) for key in
                    ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")):
                failure = failure or "DELIVERY_STDIN_CHANGED"
            incoming.close()
        for stream in files.values():
            try:
                stream.flush(); os.fsync(stream.fileno())
            except OSError:
                failure = failure or "DELIVERY_CAPTURE_DURABILITY"
            finally:
                stream.close()
        for parent in {p.parent for p in paths}:
            try:
                base.sync_dir(parent)
            except OSError:
                failure = failure or "DELIVERY_CAPTURE_DURABILITY"
    finished_ns = time.monotonic_ns()
    finished_boot = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    within = finished_ns <= deadline_ns and finished_boot <= boot_deadline
    complete = proc is not None and proc.returncode == 0 and eof == {"stdout", "stderr"} and failure is None and within
    return {"schema": "local-hand-q2-supervisor-startup-retry-capture-primitive/v1", "status": "CAPTURED" if complete else "INCOMPLETE", "complete": complete,
            "issued_ns": issued_ns, "deadline_ns": deadline_ns, "started_ns": started,
            "returncode": proc.returncode if proc is not None else None, "eof": sorted(eof), "error": failure,
            "captured_bytes": total, "finished_ns": finished_ns, "within_original_deadline": within,
            "boottime_issued_ns": boottime_issued_ns, "boottime_deadline_ns": boot_deadline,
            "finished_boottime_ns": finished_boot, "remote_stop_proven": False, "q2_accepted": False}


def capture_once(argv, *, host_issued_ns, host_deadline_ns, stdout_path, stderr_path,
                 stdin_path=None, prior_captured_bytes=0, deadline_ns=None, output_limit=None, host_boottime_issued_ns=None):
    """One finite client; charge probe and guest output to the same 2 MiB pool.

    The host reservation is caller-owned. Output paths are create-only in the
    reused transport, so a second call with the same phase paths is rejected.
    """
    host_window(host_issued_ns, host_deadline_ns)
    number(prior_captured_bytes, 0, OUTPUT_LIMIT)
    end = host_deadline_ns if deadline_ns is None else number(deadline_ns, host_issued_ns + 1, host_deadline_ns)
    available = OUTPUT_LIMIT - prior_captured_bytes
    limit = available if output_limit is None else number(output_limit, 1024, available)
    require(limit >= 1024, "STARTUP_RETRY_DELIVERY_TOTAL_OUTPUT_BUDGET")
    require(hasattr(time, "CLOCK_BOOTTIME"), "STARTUP_RETRY_DELIVERY_BOOTTIME_REQUIRED")
    if host_boottime_issued_ns is None:
        # Independent primitive callers get a conservative current offset;
        # the one-shot entry always supplies its original pre-read BOOTTIME.
        current_boot = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        current_mono = time.monotonic_ns()
        host_boottime_issued_ns = host_issued_ns + current_boot - current_mono
    number(host_boottime_issued_ns, 1)
    result = _capture(argv, issued_ns=host_issued_ns, deadline_ns=end,
                      boottime_issued_ns=host_boottime_issued_ns, output_limit=limit,
                      stdout_path=stdout_path, stderr_path=stderr_path, stdin_path=stdin_path)
    # The finite capture primitive requires rc=0. Keep that source fact
    # while distinguishing a complete observed nonzero exit from missing EOF.
    transport_complete = (type(result["started_ns"]) is int and type(result["returncode"]) is int
                          and result["eof"] == ["stderr", "stdout"] and result["error"] is None
                          and result["within_original_deadline"] is True)
    return {**result, "schema": CAPTURE_SCHEMA, "primitive_capture_complete": result["complete"],
            "complete": transport_complete, "command_succeeded": transport_complete and result["returncode"] == 0,
            "status": "CAPTURED" if transport_complete else "INCOMPLETE",
            "host_issued_ns": host_issued_ns, "host_deadline_ns": host_deadline_ns,
            "prior_captured_bytes": prior_captured_bytes,
            "total_captured_bytes": prior_captured_bytes + result["captured_bytes"]}


def final_report(*, attempt_id, host_issued_ns, host_deadline_ns, host_boottime_issued_ns,
                 probe_capture=None, guest_capture=None, collect_capture=None, finished_ns=None,
                 finished_boottime_ns=None, error=None):
    """Report the original clients only; runtime seals receive separate review."""
    token(attempt_id); host_window(host_issued_ns, host_deadline_ns)
    finished = time.monotonic_ns() if finished_ns is None else number(finished_ns, host_issued_ns)
    number(host_boottime_issued_ns, 1)
    boot_deadline = host_boottime_issued_ns + host_deadline_ns - host_issued_ns
    finished_boot = (time.clock_gettime_ns(time.CLOCK_BOOTTIME) if finished_boottime_ns is None
                     else number(finished_boottime_ns, host_boottime_issued_ns))
    captures = [value for value in (probe_capture, guest_capture, collect_capture) if value is not None]
    total = 0
    for value in captures:
        require(value["schema"] == CAPTURE_SCHEMA and value["host_issued_ns"] == host_issued_ns
                and value["host_deadline_ns"] == host_deadline_ns
                and value["boottime_issued_ns"] == host_boottime_issued_ns
                and value["prior_captured_bytes"] == total, "STARTUP_RETRY_DELIVERY_CAPTURE_BINDING")
        total += number(value["captured_bytes"], 0, OUTPUT_LIMIT)
        require(total == value["total_captured_bytes"] and total <= OUTPUT_LIMIT, "STARTUP_RETRY_DELIVERY_TOTAL_OUTPUT_BUDGET")
    within = (host_issued_ns <= finished <= host_deadline_ns
              and host_boottime_issued_ns <= finished_boot <= boot_deadline)
    complete = (probe_capture is not None and guest_capture is not None
                and all(value["complete"] is True for value in captures) and within)
    success = complete and all(value["command_succeeded"] is True for value in captures) and error is None
    return dict(schema=REPORT_SCHEMA, attempt_id=attempt_id, status="CAPTURED" if success else "INCOMPLETE",
                original_clients_capture_complete=complete, original_clients_succeeded=success,
                issued_ns=host_issued_ns, deadline_ns=host_deadline_ns, finished_ns=finished,
                boottime_issued_ns=host_boottime_issued_ns, boottime_deadline_ns=boot_deadline,
                finished_boottime_ns=finished_boot, within_management_deadline=within, total_captured_bytes=total, error=error,
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
