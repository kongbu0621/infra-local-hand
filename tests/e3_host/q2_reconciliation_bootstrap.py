"""Memory-first bootstrap inside the sole approved outer clock window.

The full joint attestation and proposed-after bill precede all owned persistent
writes. The five-file seal then precedes charged staging and startup assembly.
"""
from __future__ import annotations

import base64
import copy
import importlib.util
import os
from pathlib import Path
import re
import time


def helper(name):
    spec = importlib.util.spec_from_file_location("_reconciliation_bootstrap_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIELDS = {"manifest_raw", "manifest_sha256", "blobs", "implementation_commit", "stage",
    "archive", "archive_sha256", "files", "file_hashes", "clock_anchor", "guest_pin"}
LIVE_SCHEMA = "local-hand-q2-reconciliation-live-admitted/v1"
READY_SCHEMA = "local-hand-q2-reconciliation-bootstrap-ready/v1"
SCHEMA = "local-hand-q2-reconciliation-bootstrap-result/v1"
INPUTS_LIMIT = 16 * 1024**2
MAX_ARCHIVE_BYTES = 64 * 1024**2
METADATA_LIMITS = {"bootstrap-attestation.json": 4 * 1024**2,
    "retry.json": 2 * 1024**2, "delivery.json": 16 * 1024, "clock-anchor.json": 16 * 1024,
    "reconciliation-inputs.json": INPUTS_LIMIT, "bootstrap-failed.json": 64 * 1024}
METADATA_INODES = len(METADATA_LIMITS)
METADATA_BYTES = sum((size + 4095) // 4096 * 4096 for size in METADATA_LIMITS.values())


def require(value, code):
    if not value:
        raise ValueError(code)


def unbase64(value, limit):
    require(type(value) is str and len(value) <= (limit + 2) // 3 * 4,
        "RECONCILIATION_INPUT_BOUND")
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as error:
        raise ValueError("RECONCILIATION_BASE64") from error
    require(len(raw) <= limit, "RECONCILIATION_INPUT_BOUND")
    return raw


def input_bundle(config):
    # Persist only the inputs already checked in memory. No new source is read
    # after issuance of a private, source-pinned input package.
    return {key: copy.deepcopy(config[key]) for key in
        ("manifest_raw", "manifest_sha256", "blobs", "implementation_commit")}


def load_inputs(value):
    require(type(value) is dict and set(value) == {"manifest_raw", "manifest_sha256", "blobs",
        "implementation_commit"}, "RECONCILIATION_STAGED_INPUT_FIELDS")
    source = helper("q2_reconciliation_sources")
    contract = source.c
    raw = unbase64(value["manifest_raw"], contract.INPUT_LIMIT)
    require(type(value["blobs"]) is dict and len(value["blobs"]) <= 128,
        "RECONCILIATION_BLOB_COUNT")
    blobs = {}; total = 0
    for digest, encoded in value["blobs"].items():
        contract.digest(digest)
        data = unbase64(encoded, contract.INPUT_LIMIT)
        total += len(data)
        require(total <= INPUTS_LIMIT, "RECONCILIATION_BLOB_TOTAL")
        require(contract.sha(data) == digest, "RECONCILIATION_BLOB_DIGEST")
        blobs[digest] = data
    return source.verify(raw, value["manifest_sha256"], blobs,
        implementation_commit=value["implementation_commit"])


def guarded_extract(base, checked, digest, *, root, backend, admission, entry):
    """Charge metadata before create-only extraction, with the original guard."""
    backend.effect_admission()
    path = base.protected_parent(root)
    intent_path = base.protected_parent(root + ".intent.json")
    require(not os.path.lexists(path) and not os.path.lexists(intent_path),
        "RECONCILIATION_STAGE_ALREADY_RESERVED")
    io = backend._io
    with io.HeldPath(str(path.parent), backend.guard, directory=True) as parent:
        require(os.fstat(parent.fd).st_dev == backend.plan["mounts"]["system"]["device"],
            "RECONCILIATION_STAGE_DEVICE")
        fs = os.fstatvfs(parent.fd)
        block = fs.f_frsize
        require(type(block) is int and 512 <= block <= 65536 and block & (block - 1) == 0,
            "RECONCILIATION_STAGE_BLOCK_SIZE")
        metadata_peak = sum((limit + block - 1) // block * block for limit in METADATA_LIMITS.values())
        require(metadata_peak <= METADATA_BYTES, "RECONCILIATION_STAGE_METADATA_GEOMETRY")
        needed_bytes = checked["staging_bytes"] + metadata_peak + 2 * block
        needed_inodes = checked["entries"] + METADATA_INODES + 3
        require(needed_bytes <= backend.new_staging_peak["bytes"]
            and needed_inodes <= backend.new_staging_peak["inodes"]
            and needed_bytes <= fs.f_bavail * fs.f_frsize and needed_inodes <= fs.f_favail,
            "RECONCILIATION_STAGE_STORAGE")
    transfer = dict(schema="local-hand-q2-reconciliation-transfer/v1", status="RESERVED",
        attempt_id=backend.retry["attempt_id"], amendment_sha256=backend.verified.digest,
        archive_sha256=digest, destination=root, issued_ns=backend.issued_ns,
        deadline_ns=backend.deadline, delivery_sha256=helper("q2_reconciliation_contract").sha(
            helper("q2_reconciliation_contract").encoded(backend.delivery_envelope)),
        staging_bytes=checked["staging_bytes"], staging_entries=checked["entries"],
        metadata_reserved_bytes=METADATA_BYTES, metadata_reserved_inodes=METADATA_INODES,
        installation_reservation_bytes=admission["installation_reservation_bytes"],
        ceiling_bytes=backend.plan["budgets"]["installation_bytes"], q2_accepted=False)
    p = helper("q2_prepare")
    backend.guard(); p.create_file(intent_path, p.c.encoded(transfer))
    backend.guard(); p.create_directory(path, mode=0o755)
    for row in sorted(checked["members"], key=lambda item: (len(Path(item["name"]).parts), item["name"])):
        backend.guard()
        target = path / row["name"]
        if row["kind"] == "directory":
            p.create_directory(target, mode=0o755)
        else:
            p.create_file(target, row["data"], mode=row["mode"])
        backend.guard()
    backend.guard()
    backend.verify_host()
    return dict(transfer, status="EXTRACTED", entries=checked["entries"])


def write_metadata(root, name, raw, backend):
    require(name in METADATA_LIMITS and type(raw) is bytes and len(raw) <= METADATA_LIMITS[name],
        "RECONCILIATION_STAGE_METADATA_BOUND")
    backend.effect_admission()
    helper("q2_prepare").create_file(Path(root) / name, raw)
    backend.guard()


def bootstrap(config, entry, *, on_live=None):
    backend = None
    stage = "configuration"
    stage_owned = False
    try:
        require(type(config) is dict and set(config) == FIELDS, "RECONCILIATION_BOOTSTRAP_FIELDS")
        require(type(entry) is dict and set(entry) == {"monotonic_ns", "boottime_ns"}
            and all(type(value) is int and value > 0 for value in entry.values()),
            "RECONCILIATION_ENTRY_CLOCK")
        require(on_live is None or callable(on_live), "RECONCILIATION_LIVE_CALLBACK")
        contract = helper("q2_reconciliation_contract")
        delivery = helper("q2_reconciliation_delivery")
        base = helper("q2_prepare_delivery")
        old_boot = helper("q2_startup_retry_bootstrap")
        driver = helper("q2_reconciliation_driver")
        verified = load_inputs(input_bundle(config))
        root = contract.path(config["stage"])
        execution, plan = verified.execution, verified.plan
        require(root == str(Path(plan["candidate"]["source"]).parent)
            and execution["source"]["files"] == config["file_hashes"],
            "RECONCILIATION_STAGE_BINDING")
        require(base.verify_guest(config["guest_pin"]) == config["guest_pin"],
            "RECONCILIATION_GUEST_CHANGED")
        envelope = delivery.guest_envelope(config["clock_anchor"], attempt_id=execution["attempt_id"],
            guest_boot_id=config["guest_pin"]["boot_id"], guest_now_ns=entry["boottime_ns"])
        delivery.validate_envelope(config["clock_anchor"], envelope, attempt_id=execution["attempt_id"],
            boot_id=config["guest_pin"]["boot_id"], now_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME), preparation=True)
        issued, deadline = delivery.legacy.preparation_window(envelope, entry)
        backend = helper("q2_reconciliation_backend").ReconciliationBackend(verified,
            issued_ns=issued, deadline_ns=deadline, boot_deadline_ns=envelope["preparation_deadline_ns"],
            delivery_envelope=envelope, reconciliation_directory=plan["directories"]["reservation"]["path"] + ".reconciliation")
        stage = "archive_admission"
        archive = unbase64(config["archive"], MAX_ARCHIVE_BYTES)
        checked = base.archive_members(archive, config["archive_sha256"], maximum_bytes=MAX_ARCHIVE_BYTES)
        old_boot.check_archive_sources(checked, config["files"], config["file_hashes"], root + "/tools")
        old_boot.check_stage_layout(config, execution, plan, checked)
        staged_input_raw = contract.encoded(input_bundle(config), limit=INPUTS_LIMIT)
        backend.new_staging_peak = dict(bytes=checked["staging_bytes"] + METADATA_BYTES + 8192,
            inodes=checked["entries"] + METADATA_INODES + 3)
        stage = "joint_live_attestation"
        backend.preflight(skip_candidate=True)
        admission = backend.stage_admission(checked["staging_bytes"] + METADATA_BYTES,
            checked["entries"] + METADATA_INODES)
        live = backend.recheck_before_record()
        documents = driver.make_documents(backend, live)
        live_event = dict(schema=LIVE_SCHEMA, status="LIVE_ATTESTED", attempt_id=execution["attempt_id"],
            amendment_sha256=verified.digest, inputs_sha256=verified.digest,
            source_commit=verified.implementation_commit, source_tree=execution["source"]["tree"],
            clock_anchor_sha256=envelope["clock_anchor_sha256"],
            live_attestation_sha256=contract.sha(documents["live-attestation.json"]),
            q2_accepted=False, q3_accepted=False, production_supported=False)
        backend.guard()
        if on_live is not None:
            on_live(copy.deepcopy(live_event))
        print(contract.encoded(live_event).decode(), end="", flush=True)
        stage = "reconciliation_records"
        result = helper("q2_reconciliation_records").write_once(backend.reconciliation_directory,
            documents, backend.guard)
        backend.accept_new_seal(result, documents)
        stage = "staging"
        transfer = guarded_extract(base, checked, config["archive_sha256"], root=root,
            backend=backend, admission=admission, entry=entry)
        stage_owned = True
        stage = "staged_records"
        write_metadata(root, "reconciliation-inputs.json", staged_input_raw, backend)
        write_metadata(root, "retry.json", contract.encoded(execution), backend)
        write_metadata(root, "delivery.json", contract.encoded(envelope), backend)
        write_metadata(root, "clock-anchor.json", contract.encoded(config["clock_anchor"]), backend)
        write_metadata(root, "bootstrap-attestation.json", contract.encoded(dict(
            schema="local-hand-q2-reconciliation-bootstrap-attestation/v1", live=live,
            admission=admission, transfer=transfer, reconciliation_seal=backend.seal), limit=4 * 1024**2), backend)
        backend.verify_preserved()
        ready = dict(schema=READY_SCHEMA, status="RECONCILIATION_BOOTSTRAP_READY",
            amendment_sha256=verified.digest, inputs_sha256=verified.digest,
            delivery_sha256=contract.sha(contract.encoded(envelope)), clock_anchor_sha256=envelope["clock_anchor_sha256"],
            attempt_id=execution["attempt_id"], source_commit=verified.implementation_commit,
            source_tree=execution["source"]["tree"],
            reconciliation_seal_sha256=contract.sha(contract.encoded(backend.seal)),
            q2_accepted=False, q3_accepted=False, production_supported=False)
        print(contract.encoded(ready).decode(), end="", flush=True)
        return dict(ready=True, backend=backend, envelope=envelope, entry=entry, record=ready)
    except Exception as error:
        value = str(error) if isinstance(error, ValueError) else type(error).__name__
        result = dict(schema=SCHEMA, status="BLOCKED_RETAINED", stage=stage,
            reason=value if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else type(error).__name__,
            window_consumed=True, automatic_replay_permitted=False, historical_results_unchanged=True,
            q2_accepted=False, q3_accepted=False, production_supported=False)
        if backend is not None:
            result.update(attempt_id=backend.retry["attempt_id"], amendment_sha256=backend.verified.digest,
                reconciliation_sealed=backend.reconciliation_sealed)
            if stage_owned:
                try:
                    write_metadata(config["stage"], "bootstrap-failed.json", contract.encoded(result), backend)
                except Exception as recording:
                    result["recording_error"] = type(recording).__name__
            backend.close()
        print(helper("q2_reconciliation_contract").encoded(result).decode(), end="", flush=True)
        return dict(ready=False, backend=None, envelope=None, entry=entry, record=result)


def run(config, entry):
    result = bootstrap(config, entry)
    if not result["ready"]:
        return result["record"]
    return helper("q2_reconciliation_driver").execute(result["backend"], result["envelope"], entry)


if __name__ == "__main__":
    raise SystemExit("BLOCKED: requires the exact source-pinned private one-shot input")
