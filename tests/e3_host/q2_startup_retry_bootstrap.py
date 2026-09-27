"""Read-only admission before the one approved startup-retry staging effect.

The private delivery supplies exact pins and archive bytes. This module owns
the sequencing and budget checks; it never chooses host paths, contacts SSH,
changes the frozen runtime, or executes an old preparation/recovery entry.
Call inside the pinned orchestration loader, leave that context, then fresh
exec the returned argv. The original entry clock precedes loader imports.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import time

SCHEMA = "local-hand-q2-supervisor-startup-retry-bootstrap-result/v1"
READY_SCHEMA = "local-hand-q2-supervisor-startup-retry-bootstrap-ready/v1"
FIELDS = {"attempt_id", "stage", "tools_directory", "guest_pin", "original_plan_path",
          "original_plan_sha256", "previous_plan_path", "previous_plan_sha256", "retry",
          "archive", "archive_sha256", "files", "file_hashes", "clock_anchor"}
MAX_ARCHIVE_BYTES = 64 * 1024**2
METADATA_LIMITS = {"bootstrap-attestation.json": 4 * 1024**2, "retry.json": 2 * 1024**2,
                   "delivery.json": 16384, "bootstrap-failed.json": 128 * 1024}
METADATA_INODES = len(METADATA_LIMITS)
METADATA_BYTES = sum((size + 4095) // 4096 * 4096 for size in METADATA_LIMITS.values())


def require(value, code):
    if not value:
        raise ValueError(code)


def helper(name):
    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("_startup_bootstrap_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_metadata(base, root, name, raw, guard):
    require(name in METADATA_LIMITS and type(raw) is bytes and len(raw) <= METADATA_LIMITS[name],
            "STARTUP_BOOTSTRAP_METADATA_SIZE")
    guard()
    base.write(root / name, raw)
    guard()


def current_clock():
    return dict(boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME))


def check_archive_sources(checked, files, file_hashes, tools_directory):
    """The bytes imported before staging must be the same bytes later exec'd."""
    require(type(files) is dict and type(file_hashes) is dict and
            1 <= len(files) <= 64 and set(files) == set(file_hashes), "STARTUP_BOOTSTRAP_FILES")
    members = {item["name"]: item for item in checked["members"]}
    require(len(members) == len(checked["members"]), "STARTUP_BOOTSTRAP_ARCHIVE_DUPLICATE")
    expected = set()
    for path, text in files.items():
        require(type(path) is str and str(PurePosixPath(path)) == path and
                str(PurePosixPath(path).parent) == tools_directory and
                re.fullmatch(r"q2_[a-z0-9_]+\.py", PurePosixPath(path).name) and
                type(text) is str, "STARTUP_BOOTSTRAP_SOURCE_PATH")
        raw = text.encode("utf-8")
        require(sha(raw) == file_hashes[path], "STARTUP_BOOTSTRAP_SOURCE_DIGEST")
        name = "tools/" + PurePosixPath(path).name
        expected.add(name)
        item = members.get(name)
        require(item is not None and item["kind"] == "file" and item["data"] == raw,
                "STARTUP_BOOTSTRAP_SOURCE_MISMATCH")
    require({name for name in members if name.startswith("tools/")} == expected,
            "STARTUP_BOOTSTRAP_UNPINNED_SOURCE")


def diagnostic(error, stage):
    reason = str(error) if isinstance(error, ValueError) else type(error).__name__
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason):
        reason = type(error).__name__
    return dict(stage=stage, type=type(error).__name__[:64],
                errno=error.errno if isinstance(error, OSError) else None, reason=reason)


def check_stage_layout(config, retry, plan, checked):
    root = PurePosixPath(config["stage"])
    candidate = retry["candidate"]
    wheel = "infra_local_hand-0.2.0a1-py3-none-any.whl"
    require(candidate["source"] == str(root / "source") and
            candidate["wheel"] == str(root / wheel), "STARTUP_BOOTSTRAP_CANDIDATE_LAYOUT")
    retained = {item["path"]: item["category"] for item in retry["retained_inputs"]}
    require(retained.get(str(root)) == retained.get(str(root) + ".intent.json") == "installation",
            "STARTUP_BOOTSTRAP_STAGE_COVERAGE")
    for path in [*retry["old_files"], candidate["destination"],
                 *(value["path"] for value in retry["directories"].values())]:
        for stage_path in (root, PurePosixPath(str(root) + ".intent.json")):
            other = PurePosixPath(path)
            require(stage_path != other and stage_path not in other.parents and other not in stage_path.parents,
                    "STARTUP_BOOTSTRAP_STAGE_ALIAS")
    require(all(PurePosixPath(item["name"]).parts[0] in {"source", "tools", wheel} and
                (PurePosixPath(item["name"]).parts[0] != wheel or item["name"] == wheel)
                for item in checked["members"]), "STARTUP_BOOTSTRAP_ARCHIVE_LAYOUT")
    require({item["name"]: item["kind"] for item in checked["members"]}.get(wheel) == "file",
            "STARTUP_BOOTSTRAP_WHEEL_MISSING")


def guarded_extract(base, checked, expected_sha256, *, destination, guest_pin,
                    admission, ceiling_bytes, system_device, issued_ns, deadline_ns, guard):
    """Charge one create-only stage and check both clocks at every effect.

    The old transfer helper checks MONOTONIC only. Keeping the BOOTTIME guard
    here prevents a suspended guest from resuming its staging writes after
    the original window, without changing the historical helper's contract.
    """
    guard()
    guest = base.verify_guest(guest_pin)
    root = base.protected_parent(destination)
    reservation = base.protected_parent(str(root) + ".intent.json")
    require(not os.path.lexists(root) and not os.path.lexists(reservation), "STARTUP_BOOTSTRAP_ALREADY_RESERVED")
    parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        require(os.fstat(parent_fd).st_dev == system_device, "STARTUP_BOOTSTRAP_STAGE_DEVICE")
    finally:
        os.close(parent_fd)
    reserved = admission["installation_reservation_bytes"]
    require(type(reserved) is int and reserved >= 4096 and
            reserved + checked["staging_bytes"] + METADATA_BYTES + 8192 <= ceiling_bytes,
            "STARTUP_BOOTSTRAP_INSTALLATION_BUDGET")
    storage = os.statvfs(root.parent)
    require(storage.f_bavail * storage.f_frsize >= checked["staging_bytes"] + METADATA_BYTES + 8192 and
            storage.f_favail >= checked["entries"] + METADATA_INODES + 3, "STARTUP_BOOTSTRAP_STORAGE")
    intent = dict(schema="local-hand-q2-supervisor-startup-retry-transfer/v1", status="RESERVED",
                  guest=guest, archive_sha256=expected_sha256, destination=str(root),
                  issued_ns=issued_ns, deadline_ns=deadline_ns,
                  staging_bytes=checked["staging_bytes"], staging_entries=checked["entries"],
                  metadata_reserved_bytes=METADATA_BYTES, metadata_reserved_inodes=METADATA_INODES,
                  installation_reservation_bytes=reserved, ceiling_bytes=ceiling_bytes,
                  q2_accepted=False)
    guard(); base.write(reservation, encoded(intent))
    guard(); base.sync_dir(root.parent)
    guard(); root.mkdir(mode=0o755)
    guard(); root.chmod(0o755)
    for member in sorted(checked["members"], key=lambda row: (len(Path(row["name"]).parts), row["name"])):
        guard()
        target = root / member["name"]
        if member["kind"] == "directory":
            target.mkdir(mode=0o755)
            guard(); target.chmod(0o755)
        else:
            base.write(target, member["data"], member["mode"])
        guard()
    for member in sorted(checked["members"], key=lambda row: -len(Path(row["name"]).parts)):
        if member["kind"] == "directory":
            guard(); base.sync_dir(root / member["name"])
    guard(); base.sync_dir(root)
    guard(); base.sync_dir(root.parent)
    guard()
    require(base.verify_guest(guest_pin) == guest, "STARTUP_BOOTSTRAP_GUEST_CHANGED")
    guard()
    return dict(intent, status="EXTRACTED", entries=checked["entries"])


def bootstrap(config, entry):
    """Return a new driver argv or retained failure; never issue a retry here."""
    backend = None
    stage_owned = False
    stage = "configuration"
    attempt = None
    try:
        require(type(config) is dict and set(config) == FIELDS, "STARTUP_BOOTSTRAP_FIELDS")
        attempt = config["attempt_id"]
        transport = helper("q2_startup_retry_delivery")
        base = helper("q2_prepare_delivery")
        provision = helper("q2_prepare")
        contract = helper("q2_startup_retry_contract")
        backend_module = helper("q2_startup_retry")
        root = base.canonical(config["stage"])
        require(config["tools_directory"] == str(root / "tools") and
                config["tools_directory"] == str(Path(__file__).parent) and
                config["retry"]["attempt_id"] == attempt and
                config["retry"]["source"]["files"] == config["file_hashes"],
                "STARTUP_BOOTSTRAP_BINDING")
        require(type(entry) is dict and set(entry) == {"monotonic_ns", "boottime_ns"},
                "STARTUP_BOOTSTRAP_ENTRY_CLOCK")
        # The guest origin is supplied by the very first line of the one input.
        base.verify_guest(config["guest_pin"])
        envelope = transport.guest_envelope(config["clock_anchor"], attempt_id=attempt,
            guest_boot_id=config["guest_pin"]["boot_id"], guest_now_ns=entry["boottime_ns"])
        issued, deadline = transport.preparation_window(envelope, entry)
        retry_raw = encoded(config["retry"])
        retry = contract.decode(retry_raw, sha(retry_raw))
        require(retry["original_plan_path"] == config["original_plan_path"] and
                retry["original_plan_sha256"] == config["original_plan_sha256"] and
                retry["predecessors"][1]["plan_path"] == config["previous_plan_path"] and
                retry["predecessors"][1]["plan_sha256"] == config["previous_plan_sha256"],
                "STARTUP_BOOTSTRAP_ORIGINAL_BINDING")
        stage = "historical_plans"
        original = provision.c.decode(provision.read(config["original_plan_path"],
            2 * 1024**2, noatime=True), config["original_plan_sha256"])
        previous_raw = provision.read(config["previous_plan_path"], 2 * 1024**2, noatime=True)
        previous = helper("q2_retry_contract").decode(previous_raw, config["previous_plan_sha256"])
        # bind also pins the previous plan path/digest against the new chain.
        plan = contract.bind(original, retry, previous)
        backend = backend_module.StartupRetryBackend(plan, retry, issued_ns=issued, deadline_ns=deadline)
        backend.guard = transport.preparation_guard(backend.guard, envelope, current_clock)
        stage = "preflight"
        facts = backend.preflight(skip_candidate=True)
        backend.guard()
        stage = "archive_admission"
        require(type(config["archive"]) is str and len(config["archive"]) <=
                (MAX_ARCHIVE_BYTES + 2) // 3 * 4, "STARTUP_BOOTSTRAP_ARCHIVE_SIZE")
        archive = base64.b64decode(config["archive"], validate=True)
        checked = base.archive_members(archive, config["archive_sha256"], maximum_bytes=MAX_ARCHIVE_BYTES)
        check_archive_sources(checked, config["files"], config["file_hashes"], config["tools_directory"])
        check_stage_layout(config, retry, plan, checked)
        admission = backend.stage_admission(checked["staging_bytes"] + METADATA_BYTES,
                                            checked["entries"] + METADATA_INODES)
        backend.guard()
        stage = "extract"
        transfer = guarded_extract(base, checked, config["archive_sha256"],
            destination=str(root), guest_pin=config["guest_pin"], admission=admission,
            ceiling_bytes=plan["budgets"]["installation_bytes"],
            system_device=plan["mounts"]["system"]["device"],
            issued_ns=issued, deadline_ns=deadline, guard=backend.guard)
        stage_owned = True
        backend.guard()
        stage = "records"
        write_metadata(base, root, "bootstrap-attestation.json",
            encoded(dict(facts=facts, admission=admission, transfer=transfer)), backend.guard)
        write_metadata(base, root, "retry.json", retry_raw, backend.guard)
        env_raw = encoded(envelope)
        write_metadata(base, root, "delivery.json", env_raw, backend.guard)
        base.sync_dir(root)
        backend.guard()
        argv = [plan["tools"]["python"]["path"], "-I", "-B",
                str(root / "tools/q2_startup_retry_driver.py"), "--retry", str(root / "retry.json"),
                "--sha256", sha(retry_raw), "--delivery-envelope", str(root / "delivery.json"),
                "--delivery-sha256", sha(env_raw), "--execute"]
        ready = dict(schema=READY_SCHEMA, status="STARTUP_RETRY_BOOTSTRAP_READY", attempt_id=attempt,
                     retry_sha256=sha(retry_raw), delivery_sha256=sha(env_raw),
                     clock_anchor_sha256=sha(encoded(config["clock_anchor"])),
                     q2_accepted=False, q3_accepted=False, production_supported=False)
        print(encoded(ready).decode(), end="", flush=True)
        return dict(ready=True, argv=argv, record=ready)
    except Exception as error:
        detail = diagnostic(error, stage)
        result = dict(schema=SCHEMA, status="INCOMPLETE", attempt_id=attempt,
                      reason=detail["reason"], diagnostic=detail, q2_accepted=False,
                      q3_accepted=False, production_supported=False, old_verdicts_retained=True)
        if backend is not None and getattr(backend, "last_command_failure", None) is not None:
            result["command_failure"] = backend.last_command_failure
        if stage_owned:
            try:
                write_metadata(base, root, "bootstrap-failed.json", encoded(result), backend.guard)
                backend.guard()
                base.sync_dir(root)
            except Exception as recording:
                result["recording_error"] = type(recording).__name__[:64]
        print(encoded(result).decode(), end="", flush=True)
        return dict(ready=False, argv=None, record=result)


if __name__ == "__main__":
    print("BLOCKED: requires the exact approved private one-shot delivery")
