"""Memory-first bootstrap inside the sole approved outer clock window.

The full joint attestation and proposed-after bill precede all owned persistent
writes. The five-file seal then precedes charged staging and startup assembly.
"""
import base64
import copy
from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import re
import stat
import time


def helper(name):
    spec = importlib.util.spec_from_file_location("_reconciliation_bootstrap_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIELDS = {"manifest_raw", "manifest_sha256", "blobs", "implementation_commit", "stage",
    "archive", "archive_sha256", "files", "file_hashes", "clock_anchor", "guest_pin", "host_window"}
LIVE_SCHEMA = "local-hand-q2-reconciliation-live-admitted/v1"
ACK_SCHEMA = "local-hand-q2-host-window-live-ack/v1"
ACK_LIMIT = 16 * 1024
ACK_BINDINGS = ("attempt_id", "amendment_sha256", "source_commit", "source_tree",
    "clock_anchor_sha256", "host_binding_sha256", "host_marker_sha256", "host_bill_sha256",
    "joint_bill_sha256", "live_attestation_sha256")
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
        ("manifest_raw", "manifest_sha256", "blobs", "implementation_commit", "host_window")}


def load_inputs(value):
    require(type(value) is dict and set(value) == {"manifest_raw", "manifest_sha256", "blobs",
        "implementation_commit", "host_window"}, "RECONCILIATION_STAGED_INPUT_FIELDS")
    helper("q2_reconciliation_contract").encoded(value, limit=INPUTS_LIMIT)
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
    verified = source.verify(raw, value["manifest_sha256"], blobs,
        implementation_commit=value["implementation_commit"])
    return VerifiedInputs(verified, load_host_window(value["host_window"], verified))


@dataclass(frozen=True)
class VerifiedInputs:
    """Keep the new host authority outside the original reconciliation proof."""
    reconciliation: object
    host_window: dict

    def __getattr__(self, name):
        try:
            original = object.__getattribute__(self, "reconciliation")
        except AttributeError:
            raise AttributeError(name) from None
        return getattr(original, name)


def load_host_window(value, verified):
    """Check raw bytes and relationships, not live fsync or full host provenance.

    In particular a wrapper preimage binds the supplied bytes but does not make
    those bytes an adopted historical source. The separate, fixed field gate
    remains closed while wrapper/cost/deadline evidence is unproved.
    """
    contract = helper("q2_host_window_contract")
    billing = helper("q2_host_window_billing")
    contract.keys(value, ("binding", "carrier_raw", "host_attestation_raw", "configuration",
        "wrapper_raw", "intent_raw", "intent_sha256", "precheck_bill", "bill"))
    carrier = unbase64(value["carrier_raw"], contract.CARRIER_BYTES)
    attestation = unbase64(value["host_attestation_raw"], contract.ATTESTATION_BYTES)
    location = contract.sources(carrier, attestation)
    configuration = helper("q2_reconciliation_entry").validate_config(value["configuration"])
    execution, plan = verified.execution, verified.plan
    require(configuration["attempt_id"] == execution["attempt_id"]
        and configuration["source_commit"] == verified.implementation_commit
        and configuration["source_tree"] == execution["source"]["tree"]
        and configuration["amendment_sha256"] == configuration["inputs_sha256"] == verified.digest
        and configuration["guest_stage"] == str(Path(plan["candidate"]["source"]).parent)
        and configuration["guest_pin"] == plan["host"]
        and configuration["candidate"] == plan["candidate"]["commit"]
        and configuration["wheel_sha256"] == plan["candidate"]["wheel_sha256"],
        "RECONCILIATION_HOST_CONFIGURATION_BINDING")
    wrapper = unbase64(value["wrapper_raw"], 64 * 1024)
    require(bool(wrapper), "RECONCILIATION_HOST_WRAPPER_EMPTY")
    binding = contract.make_binding(implementation_commit=verified.implementation_commit,
        source_tree=execution["source"]["tree"], source_files_sha256=contract.sha(contract.encoded(execution["source"]["files"])),
        attempt_id=execution["attempt_id"], plan_sha256=contract.sha(contract.encoded(plan)),
        amendment_sha256=verified.digest, configuration_sha256=contract.sha(contract.encoded(configuration)),
        wrapper_sha256=contract.sha(wrapper), location=location)
    require(value["binding"] == binding, "RECONCILIATION_HOST_BINDING_CHANGED")
    raw = unbase64(value["intent_raw"], contract.LOGICAL_LIMIT)
    require(contract.sha(raw) == contract.digest(value["intent_sha256"]),
        "RECONCILIATION_HOST_MARKER_DIGEST")
    intent = contract.verify_intent(raw, binding, location)
    precheck = billing.validate_host_bill(value["precheck_bill"])
    require(intent["precheck"]["host_bill_sha256"] == contract.sha(contract.encoded(value["precheck_bill"]))
        and intent["precheck"]["host_bill_summary"] == precheck,
        "RECONCILIATION_HOST_PRECHECK_BILL")
    transition = billing.validate_marker_transition(value["precheck_bill"], value["bill"])
    require(transition["host_id"] == contract.ATTESTATION_SHA256
        and transition["guest_id"] == contract.sha(contract.encoded(plan["host"])),
        "RECONCILIATION_HOST_BILL_MACHINE_BINDING")
    validate_marker_scan(value["bill"], intent, raw, location)
    return dict(binding=binding, location=location, intent=intent, intent_raw=raw,
        intent_sha256=value["intent_sha256"], bill=copy.deepcopy(value["bill"]),
        configuration=copy.deepcopy(configuration))


def validate_marker_scan(bill, intent, raw, location):
    """Retain the root-v1 marker boundary; ordinary v2 needs its explicit API."""
    contract = helper("q2_host_window_contract")
    require(type(intent) is dict and intent.get("schema") == contract.INTENT_SCHEMA,
        "RECONCILIATION_HOST_MARKER_SCHEMA")
    _validate_marker_scan(bill, intent, raw, location, uid=0, gid=0)


def _validate_marker_scan(bill, intent, raw, location, *, uid, gid):
    """Internal shape check after the caller has selected one exact profile."""
    contract = helper("q2_host_window_contract")
    scan = bill["inventory"]["scans"][location["directory"]]
    require(scan["path"] == location["directory"], "RECONCILIATION_HOST_MARKER_LOCATION")
    rows = {row["relative_path"]: row for row in scan["entries"]}
    require(set(rows) == {".", contract.INTENT_NAME}, "RECONCILIATION_HOST_MARKER_MEMBERS")
    root = rows["."]["source_metadata"]
    identity = intent["directory_identity"]
    parent = intent["precheck"]["parent_metadata"]
    require(rows["."]["type"] == "directory"
        and all(root[key] == identity[key] for key in ("device", "inode", "uid", "gid"))
        and root["st_mode"] == (stat.S_IFDIR | 0o700) and root["nlink"] == 2
        and root["device"] == parent["device"] and root["inode"] != parent["inode"]
        and root["uid"] == uid and root["gid"] == gid, "RECONCILIATION_HOST_MARKER_IDENTITY")
    leaf = rows[contract.INTENT_NAME]
    meta = leaf["source_metadata"]
    require(leaf["type"] == "file" and meta["st_mode"] == (stat.S_IFREG | 0o400)
        and meta["nlink"] == 1 and meta["uid"] == uid and meta["gid"] == gid
        and meta["device"] == root["device"] and meta["inode"] not in (root["inode"], parent["inode"]),
        "RECONCILIATION_HOST_MARKER_FILE_IDENTITY")
    require(leaf["sha256"] == contract.sha(raw) and meta["size"] == len(raw),
        "RECONCILIATION_HOST_MARKER_CONTENT")


def validate_marker_scan_ordinary(bill, raw, expected_binding, location):
    """Check ordinary-v2 bytes and billed metadata without reading any machine.

    Ownership comes only from the strictly decoded issuer in these exact bytes,
    never from a caller-supplied UID or this reader's process credentials.
    This does not establish provenance, an actual fsync, or permission to run.
    """
    contract = helper("q2_host_window_contract")
    intent = contract.verify_intent_ordinary(raw, expected_binding, location)
    summary = helper("q2_host_window_billing").validate_host_bill(bill)
    require(summary["marker"]["state"] == "DURABLE"
        and summary["marker"]["path"] == location["directory"]
        and summary["marker"]["device"] == intent["directory_identity"]["device"]
        and summary["marker"]["intent_sha256"] == contract.sha(raw),
        "RECONCILIATION_HOST_ORDINARY_MARKER_BINDING")
    operator = contract.validate_operator(intent["operator"])
    _validate_marker_scan(bill, intent, raw, location,
        uid=operator["uid"][1], gid=operator["gid"][1])
    return copy.deepcopy(intent)


def validate_ordinary_host_window(raw, *, expected_binding, location, window,
                                  precheck_bill, consumed_bill, plan):
    """Pure, explicitly selected v2 consistency proof; never a startup loader.

    Plan bytes remain caller-provided evidence, but their digest must match the
    expected binding and their host must match both bills. No source is adopted
    by this check. The existing loader and field-readiness gate stay unchanged.
    Parent-allocation growth and all complete-field qualifications still require
    their independent evidence; a recomputed local quote cannot supply it.
    """
    contract = helper("q2_host_window_contract")
    billing = helper("q2_host_window_billing")
    binding = contract.validate_binding(expected_binding, location)
    expected_window = contract.validate_window(window)
    require(type(plan) is dict and type(plan.get("host")) is dict
        and contract.sha(contract.encoded(plan)) == binding["plan_sha256"],
        "RECONCILIATION_HOST_ORDINARY_PLAN_BINDING")
    intent = validate_marker_scan_ordinary(consumed_bill, raw, binding, location)
    require(intent["window"] == expected_window,
        "RECONCILIATION_HOST_ORDINARY_WINDOW_BINDING")
    precheck = billing.validate_host_bill(precheck_bill)
    precheck_sha256 = contract.sha(contract.encoded(precheck_bill))
    require(intent["precheck"]["host_bill_sha256"] == precheck_sha256
        and intent["precheck"]["host_bill_summary"] == precheck,
        "RECONCILIATION_HOST_PRECHECK_BILL")
    transition = billing.validate_marker_transition(precheck_bill, consumed_bill)
    require(transition["host_id"] == contract.ATTESTATION_SHA256
        and transition["guest_id"] == contract.sha(contract.encoded(plan["host"])),
        "RECONCILIATION_HOST_BILL_MACHINE_BINDING")
    return dict(schema="local-hand-q2-host-window-ordinary-inputs/v1",
        status="INPUT_CONSISTENT", binding=binding, location=copy.deepcopy(location),
        window=expected_window, intent=intent, intent_sha256=contract.sha(raw),
        precheck_bill_sha256=precheck_sha256,
        host_bill_sha256=contract.sha(contract.encoded(consumed_bill)),
        plan_sha256=binding["plan_sha256"], transition=transition,
        source_admission_proven=False, field_ready=False, allow_run=False,
        joint_admission_proven=False, q2_accepted=False)


def validate_ordinary_host_window_parent_allocation(raw, *, expected_binding, location, window,
                                                  precheck_bill, consumed_bill, plan):
    """Explicit v2-bill consistency only; this is not wired to any run loader.

    First parent endpoints are historical observations, not evidence of cause,
    peak allocation, or complete baseline costs. The original clocks, source
    prerequisites, filesystem qualification and fixed field gate stay intact.
    """
    contract = helper("q2_host_window_contract")
    billing = helper("q2_host_window_billing")
    binding = contract.validate_binding(expected_binding, location)
    expected_window = contract.validate_window(window)
    require(type(plan) is dict and type(plan.get("host")) is dict
        and contract.sha(contract.encoded(plan)) == binding["plan_sha256"],
        "RECONCILIATION_HOST_ORDINARY_PLAN_BINDING")
    transition = billing.validate_marker_transition_parent_allocation(precheck_bill, consumed_bill,
        raw=raw, expected_binding=binding, location=location, window=expected_window)
    intent = contract.verify_intent_ordinary(raw, binding, location)
    operator = contract.validate_operator(intent["operator"])
    _validate_marker_scan(consumed_bill, intent, raw, location,
        uid=operator["uid"][1], gid=operator["gid"][1])
    require(transition["host_id"] == contract.ATTESTATION_SHA256
        and transition["guest_id"] == contract.sha(contract.encoded(plan["host"])),
        "RECONCILIATION_HOST_BILL_MACHINE_BINDING")
    return dict(schema="local-hand-q2-host-window-ordinary-inputs/v2",
        status="INPUT_CONSISTENT", binding=binding, location=copy.deepcopy(location),
        window=expected_window, intent=intent, intent_sha256=contract.sha(raw),
        precheck_bill_sha256=contract.sha(contract.encoded(precheck_bill)),
        host_bill_sha256=contract.sha(contract.encoded(consumed_bill)),
        plan_sha256=binding["plan_sha256"], transition=transition,
        parent_allocation_sha256=transition["parent_allocation_sha256"],
        baseline_parent_cost_status="UNPROVEN", baseline_parent_cost_proven=False,
        full_bill_proven=False, filesystem_proven=False,
        source_admission_proven=False, field_ready=False, allow_run=False,
        joint_admission_proven=False, q2_accepted=False)


def host_reference(verified):
    contract = helper("q2_reconciliation_contract")
    value = verified.host_window
    return dict(binding=copy.deepcopy(value["binding"]),
        host_binding_sha256=contract.sha(contract.encoded(value["binding"])),
        host_marker_sha256=value["intent_sha256"], host_marker_bytes=len(value["intent_raw"]),
        host_bill_sha256=contract.sha(contract.encoded(value["bill"])))


def validate_live_ack(raw, event):
    """A bounded response to this exact LIVE event, never a renewed window."""
    contract = helper("q2_reconciliation_contract")
    value = contract.document(raw, limit=ACK_LIMIT)
    contract.keys(value, ("schema", "status", *ACK_BINDINGS))
    require(value["schema"] == ACK_SCHEMA and value["status"] == "HOST_JOINT_ACK",
        "RECONCILIATION_HOST_ACK_SCHEMA")
    require(all(value[key] == event[key] for key in ACK_BINDINGS),
        "RECONCILIATION_HOST_ACK_BINDING")
    return value


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
    window_consumed = None
    try:
        require(type(config) is dict and set(config) == FIELDS, "RECONCILIATION_BOOTSTRAP_FIELDS")
        require(type(entry) is dict and set(entry) == {"monotonic_ns", "boottime_ns"}
            and all(type(value) is int and value > 0 for value in entry.values()),
            "RECONCILIATION_ENTRY_CLOCK")
        require(callable(on_live), "RECONCILIATION_LIVE_CALLBACK_REQUIRED")
        contract = helper("q2_reconciliation_contract")
        delivery = helper("q2_reconciliation_delivery")
        base = helper("q2_prepare_delivery")
        old_boot = helper("q2_startup_retry_bootstrap")
        driver = helper("q2_reconciliation_driver")
        verified = load_inputs(input_bundle(config))
        window_consumed = verified.host_window["intent"]["window_consumed"]
        # Pure parsing and a caller-supplied quote do not prove complete original
        # host obligations, native audit bounds or an actual first-probe deadline.
        # The current fixed evidence cannot satisfy those prerequisites. There
        # is no input boolean, amount or callback that may waive this boundary.
        helper("q2_host_window_contract").require_field_readiness(verified.host_window)
        root = contract.path(config["stage"])
        execution, plan = verified.execution, verified.plan
        require(root == str(Path(plan["candidate"]["source"]).parent)
            and execution["source"]["files"] == config["file_hashes"],
            "RECONCILIATION_STAGE_BINDING")
        require(base.verify_guest(config["guest_pin"]) == config["guest_pin"],
            "RECONCILIATION_GUEST_CHANGED")
        window = verified.host_window["intent"]["window"]
        require(config["clock_anchor"]["host_issued_ns"] == window["issued_ns"]
            and config["clock_anchor"]["host_deadline_ns"] == window["deadline_ns"],
            "RECONCILIATION_HOST_WINDOW_CHANGED")
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
            **backend.host_bindings(), q2_accepted=False, q3_accepted=False, production_supported=False)
        backend.guard()
        print(contract.encoded(live_event).decode(), end="", flush=True)
        stage = "host_joint_acknowledgment"
        ack = validate_live_ack(on_live(copy.deepcopy(live_event)), live_event)
        backend.guard()
        require(backend.recheck_before_record() == live, "RECONCILIATION_LIVE_CHANGED_AFTER_ACK")
        backend.accept_host_ack(live_event, ack)
        stage = "reconciliation_records"
        result = helper("q2_reconciliation_records").write_once(backend.reconciliation_directory,
            documents, backend.record_guard)
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
            **backend.host_bindings(), q2_accepted=False, q3_accepted=False, production_supported=False)
        print(contract.encoded(ready).decode(), end="", flush=True)
        return dict(ready=True, backend=backend, envelope=envelope, entry=entry, record=ready)
    except Exception as error:
        value = str(error) if isinstance(error, ValueError) else type(error).__name__
        result = dict(schema=SCHEMA, status="BLOCKED_RETAINED", stage=stage,
            reason=value if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else type(error).__name__,
            window_consumed=window_consumed, automatic_replay_permitted=False, historical_results_unchanged=True,
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


def run(config, entry, *, on_live=None):
    result = bootstrap(config, entry, on_live=on_live)
    if not result["ready"]:
        return result["record"]
    return helper("q2_reconciliation_driver").execute(result["backend"], result["envelope"], entry)


if __name__ == "__main__":
    raise SystemExit("BLOCKED: requires the exact source-pinned private one-shot input")
