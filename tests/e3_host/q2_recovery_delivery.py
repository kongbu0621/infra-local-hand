"""Private recovery transport evidence and cross-host monotonic clock binding.

No host paths or identities are defaults. This module does not open SSH, retry a
probe, provision a guest or revive the original failed preparation deadline.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

PROOF_SCHEMA = "local-hand-q2-original-capture-proof/v1"
ANCHOR_SCHEMA = "local-hand-q2-recovery-clock-anchor/v1"
ENVELOPE_SCHEMA = "local-hand-q2-recovery-delivery/v1"
NS = 10**9
FILE_LIMITS = {"intent.json": 32768, "report.json": 32768,
               "guest.stdout": 2*1024**2, "guest.stderr": 2*1024**2,
               "guest-input.py": 8*1024**2}
EXPECTED = {"source_commit", "source_tree", "archive_sha256", "wheel_sha256", "remote_unit",
            "guest_input_sha256", "plan_sha256", "receipt_sha256", "preparation_id"}


def require(value, code):
    if not value:
        raise ValueError(code)


def number(value, low=0, high=2**63-1):
    require(type(value) is int and low <= value <= high, "RECOVERY_DELIVERY_INTEGER")
    return value


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), "RECOVERY_DELIVERY_FIELDS")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def document(raw):
    def pairs(items):
        value = {}
        for key, child in items:
            require(key not in value, "RECOVERY_DELIVERY_DUPLICATE_KEY")
            value[key] = child
        return value
    def constant(value):
        raise ValueError("RECOVERY_DELIVERY_JSON_CONSTANT")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    require(type(value) is dict, "RECOVERY_DELIVERY_DOCUMENT")
    return value


def transport():
    """Use the existing finite capture/write/guest checks without copying them."""
    path = Path(__file__).with_name("q2_prepare_delivery.py")
    spec = importlib.util.spec_from_file_location("_recovery_delivery_transport", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(info):
    return tuple(getattr(info, key) for key in
                 ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink"))


def _open_directory(path):
    path = str(path)
    require(path.startswith("/") and not path.startswith("//") and str(Path(path)) == path
            and ".." not in Path(path).parts and path != "/", "RECOVERY_DELIVERY_PATH")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in Path(path).parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd); fd = child
        info = os.fstat(fd)
        require(info.st_uid == os.geteuid() and not info.st_mode & 0o022, "RECOVERY_DELIVERY_DIRECTORY_OWNER")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read(fd, name, limit):
    handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
    try:
        before = os.fstat(handle)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.geteuid() and not before.st_mode & 0o022
                and before.st_nlink == 1 and before.st_size <= limit, "RECOVERY_DELIVERY_FILE")
        result = bytearray()
        while len(result) <= limit:
            block = os.read(handle, min(65536, limit+1-len(result)))
            if not block:
                break
            result.extend(block)
        require(len(result) <= limit and len(result) == before.st_size
                and _identity(before) == _identity(os.fstat(handle)), "RECOVERY_DELIVERY_FILE_CHANGED")
        return bytes(result), _identity(before)
    finally:
        os.close(handle)


def validate_original_capture(directory, expected):
    """Bind the retained nonzero original client outcome before any recovery.

    The guest input is read and hashed, never executed. Small original documents
    and outputs retain exact bytes in the returned proof; the large pinned input
    is represented by size/digest. Remote termination still needs guest evidence.
    """
    keys(expected, EXPECTED)
    for name in ("source_commit", "source_tree"):
        require(type(expected[name]) is str and re.fullmatch(r"[0-9a-f]{40}", expected[name]), "RECOVERY_DELIVERY_SOURCE")
    for name in ("archive_sha256", "wheel_sha256", "guest_input_sha256", "plan_sha256", "receipt_sha256"):
        require(type(expected[name]) is str and re.fullmatch(r"[0-9a-f]{64}", expected[name]), "RECOVERY_DELIVERY_DIGEST")
    require(type(expected["remote_unit"]) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,120}\.service", expected["remote_unit"])
            and type(expected["preparation_id"]) is str and re.fullmatch(r"[a-z][a-z0-9]{7,31}", expected["preparation_id"]),
            "RECOVERY_DELIVERY_ORIGINAL_ID")
    fd = _open_directory(directory)
    try:
        info = os.fstat(fd); root_identity = _identity(info)
        raw = {}; identities = {}
        for name, limit in FILE_LIMITS.items():
            raw[name], identities[name] = _read(fd, name, limit)
        require(_identity(os.fstat(fd)) == root_identity, "RECOVERY_DELIVERY_DIRECTORY_CHANGED")
        for name in FILE_LIMITS:
            require(_identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) == identities[name],
                    "RECOVERY_DELIVERY_SET_CHANGED")
        require(sum(len(raw[name]) for name in ("guest.stdout", "guest.stderr")) <= 2*1024**2,
                "RECOVERY_DELIVERY_OUTPUT_LIMIT")
        require(sha(raw["guest-input.py"]) == expected["guest_input_sha256"], "RECOVERY_DELIVERY_INPUT_CHANGED")
        intent, report = (document(raw[name]) for name in ("intent.json", "report.json"))
        keys(intent, {"schema", "source_commit", "source_tree", "archive_sha256", "wheel_sha256", "issued_ns", "deadline_ns", "q2_accepted"})
        keys(report, {"schema", "status", "complete", "issued_ns", "deadline_ns", "started_ns", "returncode", "eof", "error",
                      "captured_bytes", "finished_ns", "within_original_deadline", "remote_stop_proven", "q2_accepted",
                      "guest.stdout_sha256", "guest.stderr_sha256", "guest-input.py_sha256", "source_commit", "source_tree",
                      "remote_unit", "q3_accepted", "production_supported"})
        require(intent["schema"] == "local-hand-q2-private-handoff/v1" and report["schema"] == "local-hand-q2-delivery/v1",
                "RECOVERY_DELIVERY_OLD_SCHEMA")
        require(all(intent[k] == expected[k] for k in ("source_commit", "source_tree", "archive_sha256", "wheel_sha256"))
                and all(report[k] == expected[k] for k in ("source_commit", "source_tree", "remote_unit")),
                "RECOVERY_DELIVERY_OLD_BINDING")
        for name in ("guest.stdout", "guest.stderr", "guest-input.py"):
            require(report[name+"_sha256"] == sha(raw[name]), "RECOVERY_DELIVERY_CAPTURE_DIGEST")
        require(report["status"] == "INCOMPLETE" and report["complete"] is False and type(report["returncode"]) is int
                and report["returncode"] == 3 and report["error"] is None and report["eof"] == ["stderr", "stdout"]
                and report["within_original_deadline"] is True and report["remote_stop_proven"] is False,
                "RECOVERY_DELIVERY_ORIGINAL_CAPTURE")
        require(all(value[key] is False for value, names in ((intent, ("q2_accepted",)),
                    (report, ("q2_accepted", "q3_accepted", "production_supported"))) for key in names),
                "RECOVERY_DELIVERY_ORIGINAL_VERDICT")
        for value in (intent, report):
            for name in ("issued_ns", "deadline_ns"):
                number(value[name], 1)
        for name in ("started_ns", "finished_ns", "captured_bytes"):
            number(report[name], 0)
        require(intent["issued_ns"] == report["issued_ns"] and intent["deadline_ns"] == report["deadline_ns"]
                and report["issued_ns"] <= report["started_ns"] <= report["finished_ns"] <= report["deadline_ns"]
                and 0 < report["deadline_ns"]-report["issued_ns"] <= 630*NS
                and report["captured_bytes"] == len(raw["guest.stdout"])+len(raw["guest.stderr"]),
                "RECOVERY_DELIVERY_ORIGINAL_TIMES")
        prefix = ("Q2_DELIVERY_READY source="+expected["source_commit"]+" plan_sha256="+expected["plan_sha256"]+"\n").encode()
        require(raw["guest.stdout"].startswith(prefix), "RECOVERY_DELIVERY_STDOUT_PREFIX")
        receipt_raw = raw["guest.stdout"][len(prefix):]
        require(sha(receipt_raw) == expected["receipt_sha256"], "RECOVERY_DELIVERY_RECEIPT_DIGEST")
        receipt = document(receipt_raw)
        require(encoded(receipt) == receipt_raw and receipt.get("schema") == "local-hand-q2-fixture-preparation/v1"
                and receipt.get("preparation_id") == expected["preparation_id"] and receipt.get("plan_sha256") == expected["plan_sha256"]
                and receipt.get("status") == "INCOMPLETE" and receipt.get("reason") == "PREPARE_COMMAND_FAILED"
                and receipt.get("fixture_generated") is False
                and all(receipt.get(k) is False for k in ("q2_accepted", "q3_accepted", "production_supported"))
                and type(receipt.get("facts")) is dict
                and set(receipt["facts"]) == {"capacity_observed", "host", "mounts", "retained_before"},
                "RECOVERY_DELIVERY_ORIGINAL_RECEIPT")
        return {"schema": PROOF_SCHEMA, "expected": copy.deepcopy(expected),
                "directory": dict(path=str(directory), device=info.st_dev, inode=info.st_ino, uid=info.st_uid),
                "files": {name: {"sha256": sha(value), "size": len(value),
                           **({"hex": value.hex()} if name != "guest-input.py" else {})} for name, value in raw.items()},
                "capture": {"report_sha256": sha(raw["report.json"]), "stdout_sha256": sha(raw["guest.stdout"]),
                            "stderr_sha256": sha(raw["guest.stderr"]), "receipt_sha256": sha(receipt_raw),
                            "returncode": 3, "eof": ["stderr", "stdout"], "failure": None},
                "receipt_sha256": sha(receipt_raw), "original_failure_fully_captured": True,
                "remote_stop_proven": False, "q2_accepted": False}
    finally:
        os.close(fd)


def make_clock_anchor(*, host_issued_ns, host_deadline_ns, host_probe_send_ns, host_probe_receive_ns,
                      guest_boot_id, guest_sample_ns, expected_boot_id):
    """Pin one probe; host MONOTONIC and guest BOOTTIME remain distinct clocks.

    Guest sample comes from CLOCK_BOOTTIME and must be bound to the expected
    boot. Host stamps use time.monotonic_ns(). Receive is later than the guest
    sample, so receive-based remaining time plus a fixed margin is conservative.
    This function neither samples a clock nor retries a probe.
    """
    values = (host_issued_ns, host_deadline_ns, host_probe_send_ns, host_probe_receive_ns, guest_sample_ns)
    for value in values:
        number(value, 1)
    require(type(guest_boot_id) is str and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", guest_boot_id)
            and guest_boot_id == expected_boot_id, "RECOVERY_DELIVERY_BOOT")
    require(host_issued_ns <= host_probe_send_ns <= host_probe_receive_ns < host_deadline_ns
            and 0 < host_deadline_ns-host_issued_ns <= 300*NS, "RECOVERY_DELIVERY_HOST_WINDOW")
    remaining = host_deadline_ns-host_probe_receive_ns-2*NS
    require(remaining > 10*NS, "RECOVERY_DELIVERY_PROBE_TIME_EXHAUSTED")
    number(guest_sample_ns+remaining, 1)
    return dict(schema=ANCHOR_SCHEMA, host_issued_ns=host_issued_ns, host_deadline_ns=host_deadline_ns,
                host_probe_send_ns=host_probe_send_ns, host_probe_receive_ns=host_probe_receive_ns,
                guest_boot_id=guest_boot_id, guest_sample_ns=guest_sample_ns,
                guest_outer_deadline_ns=guest_sample_ns+remaining, sampling_margin_ns=2*NS)


def validate_clock_anchor(anchor):
    keys(anchor, {"schema", "host_issued_ns", "host_deadline_ns", "host_probe_send_ns", "host_probe_receive_ns",
                  "guest_boot_id", "guest_sample_ns", "guest_outer_deadline_ns", "sampling_margin_ns"})
    arguments = {key: anchor[key] for key in ("host_issued_ns", "host_deadline_ns", "host_probe_send_ns",
                                             "host_probe_receive_ns", "guest_boot_id", "guest_sample_ns")}
    require(make_clock_anchor(**arguments, expected_boot_id=anchor["guest_boot_id"]) == anchor,
            "RECOVERY_DELIVERY_ANCHOR_CHANGED")
    return anchor


def guest_envelope(anchor, *, recovery_id, guest_boot_id, guest_now_ns):
    """Called once on guest entry, before the first preparation evidence read."""
    validate_clock_anchor(anchor); number(guest_now_ns, 1)
    require(type(recovery_id) is str and re.fullmatch(r"[a-z][a-z0-9]{7,31}", recovery_id),
            "RECOVERY_DELIVERY_RECOVERY_ID")
    require(guest_boot_id == anchor["guest_boot_id"], "RECOVERY_DELIVERY_BOOT")
    end = min(guest_now_ns+270*NS, anchor["guest_outer_deadline_ns"]-10*NS)
    require(anchor["guest_sample_ns"] <= guest_now_ns < end and end-guest_now_ns > 128*NS,
            "RECOVERY_DELIVERY_GUEST_TIME_EXHAUSTED")
    return dict(schema=ENVELOPE_SCHEMA, recovery_id=recovery_id, boot_id=guest_boot_id, issued_ns=guest_now_ns,
                preparation_deadline_ns=min(guest_now_ns+140*NS, end-128*NS),
                deadline_ns=end, guest_outer_deadline_ns=anchor["guest_outer_deadline_ns"],
                clock_anchor_sha256=sha(encoded(anchor)), stop_ns=3*NS)


def remaining(envelope, anchor, *, guest_boot_id, guest_now_ns, owner_runtime_ns=120*NS):
    """Check the same envelope before first runtime issuance, without refreshing."""
    keys(envelope, {"schema", "recovery_id", "boot_id", "issued_ns", "preparation_deadline_ns", "deadline_ns",
                    "guest_outer_deadline_ns", "clock_anchor_sha256", "stop_ns"})
    require(guest_envelope(anchor, recovery_id=envelope["recovery_id"], guest_boot_id=envelope["boot_id"],
                           guest_now_ns=envelope["issued_ns"]) == envelope,
            "RECOVERY_DELIVERY_ENVELOPE_CHANGED")
    number(guest_now_ns, 1); number(owner_runtime_ns, 1, 120*NS)
    require(guest_boot_id == envelope["boot_id"], "RECOVERY_DELIVERY_BOOT")
    require(envelope["issued_ns"] <= guest_now_ns < envelope["preparation_deadline_ns"]
            and guest_now_ns+owner_runtime_ns+8*NS <= envelope["deadline_ns"],
            "RECOVERY_DELIVERY_ISSUANCE_TIME_EXHAUSTED")
    return envelope["deadline_ns"]-guest_now_ns


def main():
    print(encoded(dict(status="BLOCKED", reason="EXPLICIT_ORIGINAL_CAPTURE_AND_CLOCK_BINDING_REQUIRED",
                       q2_accepted=False)).decode(), end="")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
