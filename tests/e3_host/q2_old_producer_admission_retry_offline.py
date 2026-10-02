"""Pure offline intent, execution-trace and evidence contracts for Q2.

All supplied events and filesystem facts are synthetic model inputs.  None of
these APIs reads a host, writes an intent/archive, starts a channel, or issues
P4 authority.  The historical partial prototype and its blocked status remain
unchanged.  Arithmetic and model coverage cannot qualify a field package.
"""
from __future__ import annotations

import copy

from e3_host import q2_old_producer_admission_retry_contract as c
from e3_host import q2_old_producer_admission_retry_accounting as a
from e3_host import q2_old_producer_admission_retry_protocol as p


BINDINGS_SCHEMA = "local-hand-q2-old-producer-admission-retry-offline-bindings/v1"
P4_FIXTURE_SCHEMA = "local-hand-q2-old-producer-admission-retry-p4-fixture/v1"
FRAME_SCHEMA = "local-hand-q2-old-producer-admission-retry-evidence-frame/v1"
WRITE_SCHEMA = "local-hand-q2-old-producer-admission-retry-evidence-write-fixture/v1"
RESULT_SCHEMA = "local-hand-q2-old-producer-admission-retry-offline-result/v1"
INTENT_LIMIT = 12 * 1024
TOTAL_RECORD_LOGICAL_LIMIT = 16 * 1024

BUDGETS = dict(
    outer_seconds=300, preparation_seconds=150, owner_seconds=120,
    operation_seconds=72, operation_cpu_seconds=30, operation_output_bytes=98304,
    management_cpu_seconds=400, management_memory_bytes=1536 * 1024**2,
    management_pids=1024, management_output_bytes=16 * 1024**2,
    management_storage_bytes=32 * 1024**2, management_storage_inodes=1024,
    state_bytes=8 * 1024**2, state_inodes=1536,
    journal_bytes=1024**2, journal_inodes=128,
    capture_bytes=20 * 1024**2, capture_inodes=384,
    code_delivery_bytes=64 * 1024**2, code_delivery_inodes=4096,
    host_record_allocated_bytes=64 * 1024, host_record_inodes=4,
)

STAGES = (
    "OFFLINE_VERIFIED", "WINDOW_ANCHORED", "LOCAL_PREFLIGHT",
    "HOST_RECORD_ADMITTED", "HOST_WINDOW_CONSUMED", "HOST_INTENT_DURABLE",
    "SSH_STARTED", "HELLO_VALIDATED", "GUEST_DEADLINE_BOUND", "PAYLOAD_SENT",
    "DECLARED", "CONSUMED", "STAGED", "CODE_INSTALLED", "PREFLIGHTED",
    "ADMITTED", "PROVISIONED", "ISSUED", "RECORDED",
)
WRITE_STEPS = (
    "FRAME_ACCEPTED", "OPEN_EXCLUSIVE", "FD_CHMOD_0600", "WRITE_COMPLETE",
    "FSYNC_FILE", "FSYNC_PARENT", "PREAD_VERIFY", "NAME_REBOUND",
    "FILE_METADATA_VERIFIED",
)
WRITE_FAILURE_AT = dict(EXISTS=1, SYMLINK=1, FCHMOD_FAILED=2, SHORT_WRITE=3,
    FSYNC_FILE_FAILED=4, FSYNC_PARENT_FAILED=5, PREAD_FAILED=6,
    NAME_REBOUND_FAILED=7, METADATA_FAILED=8)


def _result(status, **fields):
    return dict(schema=RESULT_SCHEMA, status=status, field_ready=False,
        allow_run=False, guest_executed=False, normal_chain_executions=0,
        p4_contract_qualified=False, future_package_contract_complete=False,
        **fields)


def _artifact(value):
    c._keys(value, ("basename", "bytes", "sha256"))
    c._token(value["basename"], r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
    c.require(value["basename"].endswith(".zip"), "OFFLINE_PACKAGE_NAME")
    c._number(value["bytes"], 1, BUDGETS["code_delivery_bytes"])
    c._digest(value["sha256"])
    return copy.deepcopy(value)


def _bindings(value, manifest):
    c._keys(value, ("schema", "package", "bootstrap", "ssh_argv_sha256",
        "expected_guest_boot_id", "p4_fixture"))
    c.require(value["schema"] == BINDINGS_SCHEMA, "OFFLINE_BINDINGS_SCHEMA")
    _artifact(value["package"])
    c._keys(value["bootstrap"], ("bytes", "sha256"))
    c._number(value["bootstrap"]["bytes"], 1, BUDGETS["management_output_bytes"])
    c._digest(value["bootstrap"]["sha256"])
    c._digest(value["ssh_argv_sha256"])
    c._boot(value["expected_guest_boot_id"])
    fixture = value["p4_fixture"]
    c._keys(fixture, ("schema", "fixture_only", "issued", "event", "record_ref",
        "scope", "batch", "baseline", "closure", "implementation_commit",
        "implementation_tree", "package", "evidence", "once", "retry_allowed"))
    c.require(fixture["schema"] == P4_FIXTURE_SCHEMA
        and fixture["fixture_only"] is True and fixture["issued"] is False
        and fixture["once"] is True and fixture["retry_allowed"] is False,
        "OFFLINE_P4_FIXTURE_ONLY")
    c._token(fixture["event"], r"SYNTHETIC_[A-Za-z0-9_-]{1,100}")
    c._token(fixture["record_ref"], r"synthetic://[A-Za-z0-9_./-]{1,180}")
    authority = manifest["authority"]
    c.require(c._same({key: fixture[key] for key in
        ("scope", "batch", "baseline", "closure", "implementation_commit",
         "implementation_tree", "package", "evidence")}, dict(
        scope=c.SCOPE, batch=c.BATCH, baseline=c.BASELINE, closure=c.CLOSURE,
        implementation_commit=authority["implementation_commit"],
        implementation_tree=authority["implementation_tree"],
        package=value["package"], evidence=manifest["evidence"])),
        "OFFLINE_P4_BINDING")
    return copy.deepcopy(value)


def make_intent_fixture(manifest_raw, locator_raw, context_raw, window, bindings,
                        *, implementation_commit, implementation_tree):
    """Construct bounded canonical model bytes, without creating a marker.

    P4 references here must explicitly be unissued synthetic fixtures.  The
    same fields cannot be used to supply real execution authority to this API.
    """
    manifest = c.validate_manifest(c.document(manifest_raw), locator_raw, context_raw,
        implementation_commit=implementation_commit, implementation_tree=implementation_tree)
    locator = c.validate_locator(locator_raw)
    context = c.validate_context(context_raw, locator_raw)
    p.validate_window(window)
    binding = _bindings(bindings, manifest)
    value = dict(schema=c.INTENT_SCHEMA, fixture_only=True,
        scope=c.SCOPE, batch=c.BATCH, run_permission=c.RUN_PERMISSION,
        authority=copy.deepcopy(manifest["authority"]),
        p4_fixture=binding["p4_fixture"], product=copy.deepcopy(c.PRODUCT),
        package=binding["package"], helper_sha256=c.PRIVATE_HELPER["after_sha256"],
        bootstrap=binding["bootstrap"], ssh_argv_sha256=binding["ssh_argv_sha256"],
        locator_sha256=c.sha(locator_raw), context_sha256=c.sha(context_raw),
        consumption_parent=locator["parent"], evidence_parent=context["evidence_parent"],
        evidence=manifest["evidence"], operator=context["operator"],
        host_boot_id=context["expected_host_boot_id"],
        ssh_identity_sha256=context["ssh_identity_sha256"],
        guest_identity_sha256=context["guest_identity_sha256"],
        expected_guest_boot_id=binding["expected_guest_boot_id"],
        window=copy.deepcopy(window), budgets=copy.deepcopy(BUDGETS),
        host_record=copy.deepcopy(c.HOST_RECORD),
        protocol_schema=c.HANDSHAKE_SCHEMA, window_consumed=True, owner_issued=False)
    raw = c.encoded(value, limit=INTENT_LIMIT)
    c.require(4096 + len(raw) <= TOTAL_RECORD_LOGICAL_LIMIT, "OFFLINE_INTENT_SIZE")
    return raw


def validate_intent_fixture(raw, manifest_raw, locator_raw, context_raw, window,
                            bindings, *, implementation_commit, implementation_tree):
    c.document(raw, limit=INTENT_LIMIT)
    expected = make_intent_fixture(manifest_raw, locator_raw, context_raw, window,
        bindings, implementation_commit=implementation_commit,
        implementation_tree=implementation_tree)
    c.require(raw == expected, "OFFLINE_INTENT_BINDING_OR_CANONICAL_BYTES")
    return _result("OFFLINE_INTENT_FIXTURE_VERIFIED", intent_bytes=len(raw),
        intent_sha256=c.sha(raw), record_total_logical_bytes=4096 + len(raw),
        host_persistence_attempted=False, fixture_only=True)


def replay_barrier(existing_kind):
    c.require(type(existing_kind) is str and existing_kind in {
        "ABSENT", "EMPTY_DIRECTORY", "PARTIAL_FILE", "COMPLETE_FILE", "SYMLINK",
        "IDENTITY_CHANGED", "ROLLBACK_OBSERVED", "BOOT_CHANGED", "UNKNOWN"},
        "OFFLINE_REPLAY_OBSERVATION")
    return _result("LOCAL_BLOCKED_UNCONSUMED" if existing_kind == "ABSENT"
        else "BLOCKED_RETAINED", existing_kind=existing_kind,
        modeled_consumption_barrier=existing_kind != "ABSENT", retry_allowed=False,
        host_persistence_attempted=False)


def validate_trace(events, facts):
    """Validate a synthetic single-channel trace and retain distinct outcomes."""
    c.require(type(events) is list and len(events) <= 64
        and all(type(event) is str for event in events), "OFFLINE_TRACE_FORMAT")
    c._keys(facts, ("remote_exit_status", "stdout_eof", "stderr_eof",
        "remote_stop_proven", "normal_chain_completed", "first_error"))
    for name in ("stdout_eof", "stderr_eof", "remote_stop_proven", "normal_chain_completed"):
        c.require(type(facts[name]) is bool, "OFFLINE_TRACE_FACT")
    exit_status = facts["remote_exit_status"]
    if exit_status is not None:
        c._number(exit_status, 0, 255)
    error = facts["first_error"]
    c.require(error is None or type(error) is str and 0 < len(error.encode()) <= 4096,
        "OFFLINE_TRACE_FIRST_ERROR")

    index = 0
    while index < len(events) and index < len(STAGES) and events[index] == STAGES[index]:
        index += 1
    stages, tail = events[:index], events[index:]
    failed = bool(tail and tail[0] == "FAILED")
    if failed:
        tail = tail[1:]
    c.require(failed == (error is not None), "OFFLINE_TRACE_FIRST_ERROR")
    c.require(index == len(STAGES) or failed or not tail, "OFFLINE_TRACE_STAGE_ORDER")
    c.require(len(set(events)) == len(events), "OFFLINE_TRACE_REPLAY")
    consumed = "HOST_WINDOW_CONSUMED" in stages
    remote = "SSH_STARTED" in stages
    if not remote:
        c.require(not tail, "OFFLINE_TRACE_REMOTE_BEFORE_DURABLE_INTENT")
    stop = None
    if tail and tail[0] in ("REMOTE_STOP_PROVEN", "REMOTE_STOP_UNPROVEN"):
        stop, tail = tail[0], tail[1:]
    if tail and tail[0] == "EVIDENCE_FRAME":
        c.require(stop == "REMOTE_STOP_PROVEN", "OFFLINE_TRACE_EVIDENCE_WITHOUT_STOP")
        tail = tail[1:]
        c.require(tail and tail[0] == "EVIDENCE_FILE_VERIFIED",
            "OFFLINE_TRACE_EVIDENCE_NOT_VERIFIED")
        tail = tail[1:]
    eof = []
    while tail and tail[0] in ("STDOUT_EOF", "STDERR_EOF"):
        eof.append(tail[0])
        tail = tail[1:]
    if tail and tail[0] == "SSH_EXIT":
        tail = tail[1:]
    c.require(not tail, "OFFLINE_TRACE_CHANNEL_OR_ORDER")
    c.require(facts["stdout_eof"] == ("STDOUT_EOF" in eof)
        and facts["stderr_eof"] == ("STDERR_EOF" in eof)
        and facts["remote_stop_proven"] == (stop == "REMOTE_STOP_PROVEN")
        and (exit_status is not None) == ("SSH_EXIT" in events)
        and facts["normal_chain_completed"] == ("RECORDED" in stages),
        "OFFLINE_TRACE_FACT_BINDING")
    if not remote:
        status = "CONSUMED_PARTIAL" if consumed and "HOST_INTENT_DURABLE" not in stages \
            else "BLOCKED_RETAINED" if consumed else "LOCAL_BLOCKED_UNCONSUMED"
    elif not facts["remote_stop_proven"] or not all(facts[name] for name in
            ("stdout_eof", "stderr_eof")) or exit_status is None:
        status = "REMOTE_UNKNOWN_CONSUMED"
    elif failed or exit_status != 0 or not facts["normal_chain_completed"]:
        status = "BLOCKED_RETAINED"
    else:
        c.require("EVIDENCE_FILE_VERIFIED" in events, "OFFLINE_TRACE_EVIDENCE_MISSING")
        status = "OFFLINE_NORMAL_CHAIN_TRACE_VERIFIED"
    return _result(status, fixture_only=True, modeled_window_consumed=consumed,
        modeled_normal_chain_executions=int("ISSUED" in stages),
        remote_attempted=False, retry_allowed=False, first_error=error,
        original_failure_retained=True)


def validate_evidence_frame(header_raw, archive_raw, limits):
    """Check the canonical header plus payload before any modeled file open."""
    limits = c.validate_evidence(limits)
    header = c.document(header_raw, limit=4096)
    c._keys(header, ("schema", "kind", "archive_length", "archive_sha256"))
    c.require(header["schema"] == FRAME_SCHEMA and header["kind"] == "FINAL_EVIDENCE_ARCHIVE",
        "OFFLINE_EVIDENCE_FRAME_SCHEMA")
    c._number(header["archive_length"], 1, limits["evidence_max_archive_logical_bytes"])
    c._digest(header["archive_sha256"])
    c.require(type(archive_raw) is bytes and len(archive_raw) == header["archive_length"]
        and c.sha(archive_raw) == header["archive_sha256"], "OFFLINE_EVIDENCE_PAYLOAD")
    c.require(header_raw == c.encoded(header), "OFFLINE_EVIDENCE_CANONICAL_HEADER")
    frame_bytes = len(header_raw) + len(archive_raw)
    c.require(frame_bytes <= limits["evidence_max_frame_bytes"]
        and frame_bytes <= BUDGETS["management_output_bytes"], "OFFLINE_EVIDENCE_FRAME_LIMIT")
    return _result("OFFLINE_EVIDENCE_FRAME_VERIFIED", fixture_only=True,
        header_bytes=len(header_raw), archive_bytes=len(archive_raw), frame_bytes=frame_bytes,
        archive_sha256=c.sha(archive_raw), host_file_created=False)


def validate_evidence_write(value, header_raw, archive_raw, context_raw, locator_raw, limits):
    """Check a synthetic held-FD write receipt; no file is opened by this API."""
    c._keys(value, ("schema", "fixture_only", "steps", "failure", "metadata"))
    c.require(value["schema"] == WRITE_SCHEMA and value["fixture_only"] is True,
        "OFFLINE_EVIDENCE_WRITE_SCHEMA")
    # Recompute from bounded raw bytes instead of trusting a caller's receipt.
    frame = validate_evidence_frame(header_raw, archive_raw, limits)
    context = c.validate_context(context_raw, locator_raw)
    limits = c.validate_evidence(limits)
    steps, failure = value["steps"], value["failure"]
    c.require(type(steps) is list and all(type(step) is str for step in steps)
        and tuple(steps) == WRITE_STEPS[:len(steps)], "OFFLINE_EVIDENCE_WRITE_ORDER")
    c.require(len(steps) <= len(WRITE_STEPS), "OFFLINE_EVIDENCE_WRITE_ORDER")
    if failure is not None:
        c.require(type(failure) is str and failure in WRITE_FAILURE_AT
            and len(steps) == WRITE_FAILURE_AT[failure] and value["metadata"] is None,
            "OFFLINE_EVIDENCE_WRITE_FAILURE")
        return _result("BLOCKED_RETAINED", fixture_only=True,
            modeled_partial_file_retained="OPEN_EXCLUSIVE" in steps,
            fixed_basename=limits["basename"], first_error=failure,
            retry_allowed=False, rename_or_cleanup_allowed=False, host_file_created=False)
    c.require(tuple(steps) == WRITE_STEPS, "OFFLINE_EVIDENCE_WRITE_INCOMPLETE")
    metadata = value["metadata"]
    c._keys(metadata, ("type", "uid", "gid", "mode", "device", "inode", "nlink",
        "acl_present", "logical_bytes", "allocated_bytes", "parent_device", "parent_inode",
        "fixed_name_rebound", "held_fd_identity_matches", "pread_bytes", "pread_sha256"))
    parent = context["evidence_parent"]
    c.require(metadata["type"] == "regular" and metadata["acl_present"] is False
        and metadata["fixed_name_rebound"] is True and metadata["held_fd_identity_matches"] is True,
        "OFFLINE_EVIDENCE_FILE_IDENTITY")
    for name in ("uid", "gid", "device", "inode", "nlink", "parent_device", "parent_inode"):
        c._number(metadata[name], 1)
    c.require(type(metadata["mode"]) is int and metadata["mode"] == 0o600
        and metadata["nlink"] == 1
        and (metadata["uid"], metadata["gid"], metadata["device"]) ==
            (parent["uid"], parent["gid"], parent["device"])
        and (metadata["parent_device"], metadata["parent_inode"]) ==
            (parent["device"], parent["inode"])
        and metadata["inode"] != parent["inode"], "OFFLINE_EVIDENCE_FILE_IDENTITY")
    c._number(metadata["logical_bytes"], 1, limits["evidence_max_archive_logical_bytes"])
    c._number(metadata["allocated_bytes"], 1, limits["evidence_max_archive_allocated_bytes"])
    c.require(metadata["logical_bytes"] == frame["archive_bytes"], "OFFLINE_EVIDENCE_FILE_LENGTH")
    c._number(metadata["pread_bytes"], 1, limits["evidence_max_archive_logical_bytes"])
    c._digest(metadata["pread_sha256"])
    c.require(metadata["pread_bytes"] == frame["archive_bytes"]
        and metadata["pread_sha256"] == frame["archive_sha256"], "OFFLINE_EVIDENCE_PREAD_CONTENT")
    return _result("OFFLINE_EVIDENCE_WRITE_FIXTURE_VERIFIED", fixture_only=True,
        fixed_basename=limits["basename"], host_file_created=False,
        modeled_allocated_bytes=metadata["allocated_bytes"], retry_allowed=False)


def _bind_accounting_fixture(value, locator_raw, context_raw, limits, write_receipt):
    """Bind synthetic observations and reserve maxima before modeled writes.

    The observed peak is retained unchanged.  Admission separately reserves the
    full 64 KiB / four-inode record envelope and the manifest's maximum archive
    allocation plus modeled filesystem growth/sync costs.  No measured smaller
    archive can reduce that reservation.  Unknown qualification stays unknown.
    Called only after the complete write receipt has been validated.
    """
    result = a.evaluate_accounting(value)
    locator = c.validate_locator(locator_raw)
    context = c.validate_context(context_raw, locator_raw)
    limits = c.validate_evidence(limits)
    capture = value["capture"]
    for kind, parent in (("record", locator["parent"]),
                         ("evidence", context["evidence_parent"])):
        peak = capture[kind + "_peak"]
        c.require((peak["device"], peak["parent_baseline"]["device"],
            peak["parent_baseline"]["inode"]) ==
            (parent["device"], parent["device"], parent["inode"]),
            "OFFLINE_ACCOUNTING_PARENT_BINDING")
    evidence = capture["evidence_peak"]
    padded = copy.deepcopy(evidence)
    if evidence["snapshots"] is not None:
        for snapshot, padded_snapshot in zip(evidence["snapshots"], padded["snapshots"]):
            archive = snapshot["objects"][0]
            c.require(archive["allocated_bytes"] <=
                limits["evidence_max_archive_allocated_bytes"], "OFFLINE_ACCOUNTING_ARCHIVE_CAP")
            padded_snapshot["objects"][0]["allocated_bytes"] = \
                limits["evidence_max_archive_allocated_bytes"]
        if write_receipt["failure"] is None:
            metadata = write_receipt["metadata"]
            final = evidence["snapshots"][-1]["objects"][0]
            c.require((final["device"], final["inode"], final["allocated_bytes"], final["inodes"])
                == (metadata["device"], metadata["inode"], metadata["allocated_bytes"], 1),
                "OFFLINE_ACCOUNTING_ARCHIVE_IDENTITY")
    reserved_peak = a.calculate_peak(padded, kind="evidence")
    blockers = list(result["blockers"])
    if not reserved_peak["complete"] or result["capture"]["peak_bytes"] is None:
        return _result("OFFLINE_ACCOUNTING_BLOCKED", fixture_only=True,
            observed=result, reserved_capture_bytes=None, reserved_capture_inodes=None,
            reserved_devices=None, blockers=blockers, retry_allowed=False)
    additions = {kind: (reserved_bytes - result["peaks"][kind]["allocated_bytes"],
        reserved_inodes - result["peaks"][kind]["inodes"]) for kind, reserved_bytes,
        reserved_inodes in (("record", a.RECORD_BYTES, a.RECORD_INODES),
            ("evidence", reserved_peak["allocated_bytes"], reserved_peak["inodes"]))}
    for amount, inodes in additions.values():
        a._integer(amount)
        a._integer(inodes)
    reserved_bytes = result["capture"]["total_bytes"] + sum(x[0] for x in additions.values())
    reserved_inodes = result["capture"]["total_inodes"] + sum(x[1] for x in additions.values())
    a._integer(reserved_bytes)
    a._integer(reserved_inodes)
    if reserved_bytes > a.CAPTURE_BYTES or reserved_inodes > a.CAPTURE_INODES:
        blockers.append("RESERVED_GLOBAL_CAPTURE_CEILING_EXCEEDED")
    bills = copy.deepcopy(result["devices"])
    for bill in bills:
        for kind, (amount, inodes) in additions.items():
            if capture[kind + "_peak"]["device"] == bill["device"]:
                bill["future_demand_bytes"] = a._add(bill["future_demand_bytes"], amount)
                bill["future_demand_inodes"] = a._add(bill["future_demand_inodes"], inodes)
        bill["offline_within_free"] = (bill["future_demand_bytes"] <= bill["available_bytes"]
            and bill["future_demand_inodes"] <= bill["available_inodes"])
        if not bill["offline_within_free"]:
            blockers.append("RESERVED_DEVICE_" + str(bill["device"]) + "_CAPACITY_EXCEEDED")
    return _result("OFFLINE_ACCOUNTING_VERIFIED" if not blockers else "OFFLINE_ACCOUNTING_BLOCKED",
        fixture_only=True, observed=result, reserved_capture_bytes=reserved_bytes,
        reserved_capture_inodes=reserved_inodes, reserved_devices=bills,
        record_reservation_bytes=a.RECORD_BYTES, record_reservation_inodes=a.RECORD_INODES,
        evidence_reservation_bytes=reserved_peak["allocated_bytes"],
        evidence_reservation_inodes=reserved_peak["inodes"], blockers=blockers, retry_allowed=False)


def verify_offline_case(value, *, implementation_commit, implementation_tree):
    """Recompute a complete synthetic case from independently pinned inputs."""
    c._keys(value, ("manifest_raw", "locator_raw", "context_raw", "window", "bindings",
        "intent_raw", "handshake", "accounting", "inventory", "trace", "facts",
        "header_raw", "archive_raw", "write_receipt"))
    manifest = c.validate_manifest(c.document(value["manifest_raw"]), value["locator_raw"],
        value["context_raw"], implementation_commit=implementation_commit,
        implementation_tree=implementation_tree)
    intent = validate_intent_fixture(value["intent_raw"], value["manifest_raw"],
        value["locator_raw"], value["context_raw"], value["window"], value["bindings"],
        implementation_commit=implementation_commit, implementation_tree=implementation_tree)
    handshake = value["handshake"]
    c._keys(handshake, ("hello", "received", "before_bind", "bind", "ready"))
    p.validate_ready(handshake["ready"], handshake["bind"], handshake["hello"],
        window=value["window"], received=handshake["received"], before_bind=handshake["before_bind"],
        expected_guest_boot_id=value["bindings"]["expected_guest_boot_id"],
        intent_sha256=intent["intent_sha256"], package_sha256=value["bindings"]["package"]["sha256"])
    inventory = a.validate_predecessor_inventory(value["inventory"])
    frame = validate_evidence_frame(value["header_raw"], value["archive_raw"], manifest["evidence"])
    receipt = validate_evidence_write(value["write_receipt"], value["header_raw"], value["archive_raw"],
        value["context_raw"], value["locator_raw"], manifest["evidence"])
    accounting = _bind_accounting_fixture(value["accounting"], value["locator_raw"],
        value["context_raw"], manifest["evidence"], value["write_receipt"])
    trace = validate_trace(value["trace"], value["facts"])
    c.require(("EVIDENCE_FILE_VERIFIED" in value["trace"]) ==
        (receipt["status"] == "OFFLINE_EVIDENCE_WRITE_FIXTURE_VERIFIED"),
        "OFFLINE_TRACE_WRITE_RECEIPT_BINDING")
    blockers = list(inventory["blockers"]) + accounting["blockers"]
    if trace["status"] != "OFFLINE_NORMAL_CHAIN_TRACE_VERIFIED":
        blockers.append(trace["status"])
    return _result("OFFLINE_CASE_VERIFIED" if not blockers else "OFFLINE_CASE_BLOCKED",
        fixture_only=True, blockers=blockers, intent=intent, accounting=accounting,
        inventory=inventory, trace=trace, frame=frame, receipt=receipt, retry_allowed=False,
        field_qualification="NOT_ESTABLISHED_BY_SYNTHETIC_DATA")
