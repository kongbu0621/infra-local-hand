"""Synthetic failures and cross-binding tests for non-executing Q2 contracts."""
from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from e3_host import q2_old_producer_admission_retry_contract as c
from e3_host import q2_old_producer_admission_retry_offline as m
from e3_host import q2_old_producer_admission_retry_protocol as p
from e3_host import q2_old_producer_admission_retry_accounting as a

from test_e3_q2_old_producer_admission_retry_accounting import accounting, inventory


D, TREE = "a" * 40, "b" * 40
HOST_BOOT = "11111111-2222-3333-4444-555555555555"
GUEST_BOOT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def fixture():
    def parent(path, inode):
        return dict(schema=c.PARENT_SCHEMA, path=path, type="directory", uid=1000,
            gid=1000, mode=0o755, device=10, inode=inode)
    locator = c.encoded(dict(schema=c.LOCATOR_SCHEMA,
        parent=parent("/synthetic/consumption", 20)))
    context = c.encoded(dict(schema=c.CONTEXT_SCHEMA, locator_sha256=c.sha(locator),
        expected_host_boot_id=HOST_BOOT,
        operator=dict(schema=c.OPERATOR_SCHEMA, uid=[1000] * 3, gid=[1000] * 3,
            groups=[4, 1000, 1000]), ssh_identity_sha256="c" * 64,
        guest_identity_sha256="d" * 64, evidence_parent=parent("/synthetic/evidence", 21)))
    limits = dict(basename="synthetic-20261002a-evidence.zip", evidence_max_frame_bytes=4096,
        evidence_max_archive_logical_bytes=1024, evidence_max_archive_allocated_bytes=8192,
        evidence_archive_inode_count=1)
    manifest = c.make_manifest(implementation_commit=D, implementation_tree=TREE,
        locator_raw=locator, context_raw=context, evidence=limits)
    package = dict(basename="synthetic-20261002a.zip", bytes=1000, sha256="e" * 64)
    bindings = dict(schema=m.BINDINGS_SCHEMA, package=package,
        bootstrap=dict(bytes=256, sha256="f" * 64), ssh_argv_sha256="1" * 64,
        expected_guest_boot_id=GUEST_BOOT,
        p4_fixture=dict(schema=m.P4_FIXTURE_SCHEMA, fixture_only=True, issued=False,
            event="SYNTHETIC_P4_CONTRACT", record_ref="synthetic://p4/record",
            scope=c.SCOPE, batch=c.BATCH, baseline=c.BASELINE, closure=c.CLOSURE,
            implementation_commit=D, implementation_tree=TREE, package=copy.deepcopy(package),
            evidence=copy.deepcopy(limits), once=True, retry_allowed=False))
    window = dict(boottime_issued_ns=10 * p.NS, monotonic_issued_ns=20 * p.NS,
        boottime_outer_deadline_ns=310 * p.NS, monotonic_outer_deadline_ns=320 * p.NS,
        boottime_preparation_deadline_ns=160 * p.NS,
        monotonic_preparation_deadline_ns=170 * p.NS)
    return c.encoded(manifest), locator, context, window, bindings, limits


def make_intent(values):
    manifest, locator, context, window, bindings, _ = values
    return m.make_intent_fixture(manifest, locator, context, window, bindings,
        implementation_commit=D, implementation_tree=TREE)


def validate_intent(raw, values, **pins):
    manifest, locator, context, window, bindings, _ = values
    return m.validate_intent_fixture(raw, manifest, locator, context, window, bindings,
        implementation_commit=pins.get("commit", D), implementation_tree=pins.get("tree", TREE))


def evidence():
    payload = b"synthetic archive bytes"
    header = c.encoded(dict(schema=m.FRAME_SCHEMA, kind="FINAL_EVIDENCE_ARCHIVE",
        archive_length=len(payload), archive_sha256=c.sha(payload)))
    return header, payload


def write_fixture():
    return dict(schema=m.WRITE_SCHEMA, fixture_only=True, steps=list(m.WRITE_STEPS), failure=None,
        metadata=dict(type="regular", uid=1000, gid=1000, mode=0o600, device=10, inode=30,
            nlink=1, acl_present=False, logical_bytes=len(evidence()[1]), allocated_bytes=4096,
            parent_device=10, parent_inode=21, fixed_name_rebound=True, held_fd_identity_matches=True,
            pread_bytes=len(evidence()[1]), pread_sha256=c.sha(evidence()[1])))


def write(value, limits=None, *, header=None, archive=None):
    _, locator, context, _, _, fixed_limits = fixture()
    fixed_header, fixed_archive = evidence()
    return m.validate_evidence_write(value, fixed_header if header is None else header,
        fixed_archive if archive is None else archive, context, locator,
        fixed_limits if limits is None else limits)


def facts(**changes):
    value = dict(remote_exit_status=0, stdout_eof=True, stderr_eof=True,
        remote_stop_proven=True, normal_chain_completed=True, first_error=None)
    value.update(changes)
    return value


def complete_trace():
    return [*m.STAGES, "REMOTE_STOP_PROVEN", "EVIDENCE_FRAME", "EVIDENCE_FILE_VERIFIED",
        "STDOUT_EOF", "STDERR_EOF", "SSH_EXIT"]


def test_intent_binds_independent_artifacts_identity_p4_fixture_and_original_clocks():
    values = fixture()
    raw = make_intent(values)
    result = validate_intent(raw, values)
    value = c.document(raw)
    assert value["window"] == values[3]
    assert value["operator"]["groups"] == [4, 1000, 1000]
    assert value["authority"]["p4_event"]["issued"] is False
    assert value["p4_fixture"]["issued"] is False
    assert value["package"] == values[4]["package"]
    assert value["budgets"]["capture_bytes"] == 20 * 1024**2
    assert "intent_sha256" not in value
    assert result["intent_sha256"] == c.sha(raw)
    assert result["host_persistence_attempted"] is False
    assert result["field_ready"] is result["allow_run"] is False
    assert result["normal_chain_executions"] == 0
    assert result["intent_bytes"] <= 12 * 1024
    assert result["record_total_logical_bytes"] <= 16 * 1024


@pytest.mark.parametrize(("path", "replacement"), [
    (("scope",), "other"), (("run_permission",), "old_v2"),
    (("schema",), "local-hand-q2-host-window-intent/v2"),
    (("host_boot_id",), GUEST_BOOT), (("helper_sha256",), "0" * 64),
    (("window", "boottime_issued_ns"), 1), (("owner_issued",), True),
    (("operator", "groups"), [4, 1000]), (("package", "sha256"), "0" * 64),
    (("evidence", "basename"), "different.zip"),
])
def test_intent_tamper_is_rejected_against_independent_inputs(path, replacement):
    values = fixture()
    value = c.document(make_intent(values))
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    with pytest.raises(ValueError):
        validate_intent(c.encoded(value), values)


def test_intent_external_source_pin_duplicate_key_and_noncanonical_bytes_are_rejected():
    values = fixture()
    raw = make_intent(values)
    for pins in (dict(commit="0" * 40), dict(tree="0" * 40)):
        with pytest.raises(ValueError, match="IMPLEMENTATION"):
            validate_intent(raw, values, **pins)
    with pytest.raises(ValueError, match="DUPLICATE_KEY"):
        validate_intent(raw.replace(b'"owner_issued":false',
            b'"owner_issued":false,"owner_issued":false'), values)
    with pytest.raises(ValueError, match="CANONICAL"):
        validate_intent(raw + b" ", values)
    value = c.document(raw)
    value["intent_sha256"] = c.sha(raw)
    with pytest.raises(ValueError):
        validate_intent(c.encoded(value), values)


@pytest.mark.parametrize(("field", "value"), [("issued", True), ("once", False),
    ("retry_allowed", True), ("fixture_only", False), ("event", "REAL_P4_EVENT")])
def test_p4_fixture_cannot_issue_or_replay_field_authority(field, value):
    values = fixture()
    values[4]["p4_fixture"][field] = value
    with pytest.raises(ValueError):
        make_intent(values)


def test_large_groups_are_not_truncated_to_fit_intent_budget():
    manifest_raw, locator, context_raw, window, bindings, limits = fixture()
    context = c.document(context_raw)
    context["operator"]["groups"] = list(range(8000))
    context_raw = c.encoded(context)
    manifest = c.make_manifest(implementation_commit=D, implementation_tree=TREE,
        locator_raw=locator, context_raw=context_raw, evidence=limits)
    with pytest.raises(ValueError, match="INPUT_LIMIT"):
        make_intent((c.encoded(manifest), locator, context_raw, window, bindings, limits))


def test_intent_and_hello_bind_and_ready_share_original_external_digests():
    values = fixture()
    raw = make_intent(values)
    hello = dict(schema=p.HANDSHAKE_SCHEMA, kind="HELLO", guest_boot_id=GUEST_BOOT,
        hello_boottime_ns=2 * p.NS, nonce="2" * 64)
    received = [["CLOCK_MONOTONIC", 21 * p.NS], ["CLOCK_BOOTTIME", 11 * p.NS]]
    before_bind = [["CLOCK_MONOTONIC", 22 * p.NS], ["CLOCK_BOOTTIME", 12 * p.NS]]
    pins = dict(expected_guest_boot_id=GUEST_BOOT, intent_sha256=c.sha(raw),
        package_sha256=values[4]["package"]["sha256"])
    bind = p.make_bind(values[3], hello, received, before_bind, **pins)
    ready = dict(schema=p.HANDSHAKE_SCHEMA, kind="READY", guest_boot_id=GUEST_BOOT,
        nonce=hello["nonce"], hello_sha256=bind["hello_sha256"], bind_sha256=c.sha(c.encoded(bind)),
        guest_outer_deadline_ns=bind["guest_outer_deadline_ns"],
        guest_preparation_deadline_ns=bind["guest_preparation_deadline_ns"],
        ready_boottime_ns=3 * p.NS, **p.FLAGS)
    assert p.validate_ready(ready, bind, hello, window=values[3], received=received,
        before_bind=before_bind, **pins)["allow_run"] is False
    with pytest.raises(ValueError, match="BIND_MISMATCH"):
        p.validate_ready(ready, bind, hello, window=values[3], received=received,
            before_bind=before_bind, **{**pins, "intent_sha256": "0" * 64})


@pytest.mark.parametrize("kind", ["EMPTY_DIRECTORY", "PARTIAL_FILE", "COMPLETE_FILE", "SYMLINK",
    "IDENTITY_CHANGED", "ROLLBACK_OBSERVED", "BOOT_CHANGED", "UNKNOWN"])
def test_existing_or_unknown_objects_remain_replay_barriers(kind):
    result = m.replay_barrier(kind)
    assert result["modeled_consumption_barrier"] is True
    assert result["allow_run"] is result["retry_allowed"] is False
    assert m.replay_barrier("ABSENT")["allow_run"] is False


def test_complete_single_channel_trace_is_a_model_and_not_a_real_normal_execution():
    result = m.validate_trace(complete_trace(), facts())
    assert result["status"] == "OFFLINE_NORMAL_CHAIN_TRACE_VERIFIED"
    assert result["modeled_normal_chain_executions"] == 1
    assert result["normal_chain_executions"] == 0
    assert result["guest_executed"] is result["remote_attempted"] is result["allow_run"] is False
    reverse_eofs = complete_trace()
    reverse_eofs[-3:-1] = ["STDERR_EOF", "STDOUT_EOF"]
    assert m.validate_trace(reverse_eofs, facts())["status"] == result["status"]


@pytest.mark.parametrize(("index", "expected"), [(3, "LOCAL_BLOCKED_UNCONSUMED"),
    (5, "CONSUMED_PARTIAL"), (6, "BLOCKED_RETAINED")])
def test_failure_state_preserves_the_first_consumption_boundary(index, expected):
    result = m.validate_trace([*m.STAGES[:index], "FAILED"], facts(remote_exit_status=None,
        stdout_eof=False, stderr_eof=False, remote_stop_proven=False,
        normal_chain_completed=False, first_error="original failure"))
    assert result["status"] == expected
    assert result["retry_allowed"] is False


@pytest.mark.parametrize("missing", ["REMOTE_STOP_PROVEN", "STDOUT_EOF", "STDERR_EOF", "SSH_EXIT"])
def test_exit_and_eof_cannot_substitute_for_independent_remote_stop(missing):
    events = complete_trace()
    if missing == "REMOTE_STOP_PROVEN":
        events = [*m.STAGES, "REMOTE_STOP_UNPROVEN", "STDOUT_EOF", "STDERR_EOF", "SSH_EXIT"]
    else:
        events.remove(missing)
    changes = {"remote_stop_proven": missing != "REMOTE_STOP_PROVEN",
        "stdout_eof": missing != "STDOUT_EOF", "stderr_eof": missing != "STDERR_EOF",
        "remote_exit_status": None if missing == "SSH_EXIT" else 0}
    assert m.validate_trace(events, facts(**changes))["status"] == "REMOTE_UNKNOWN_CONSUMED"


@pytest.mark.parametrize("addition", ["SSH_STARTED", "SCP", "SFTP", "JOURNAL_RECONNECT", "PAYLOAD_SENT"])
def test_second_channel_replay_or_post_archive_output_is_rejected(addition):
    events = complete_trace()
    events.insert(-3, addition)
    with pytest.raises(ValueError):
        m.validate_trace(events, facts())


def test_success_cannot_skip_evidence_or_claim_a_missing_stop_event():
    events = [*m.STAGES, "REMOTE_STOP_PROVEN", "STDOUT_EOF", "STDERR_EOF", "SSH_EXIT"]
    with pytest.raises(ValueError, match="EVIDENCE_MISSING"):
        m.validate_trace(events, facts())
    with pytest.raises(ValueError, match="FACT_BINDING"):
        m.validate_trace([*m.STAGES, "STDOUT_EOF", "STDERR_EOF", "SSH_EXIT"], facts())
    with pytest.raises(ValueError, match="INTEGER"):
        m.validate_trace(complete_trace(), facts(remote_exit_status=True))


def test_evidence_limits_are_independent_and_checked_before_a_file_open():
    header, archive = evidence()
    limits = fixture()[-1]
    result = m.validate_evidence_frame(header, archive, limits)
    assert result["frame_bytes"] == len(header) + len(archive)
    assert result["host_file_created"] is False
    # The archive fits its logical limit; only the full frame fails.
    changed = {**limits, "evidence_max_archive_logical_bytes": len(archive),
        "evidence_max_frame_bytes": len(header) + len(archive) - 1}
    with pytest.raises(ValueError, match="FRAME_LIMIT"):
        m.validate_evidence_frame(header, archive, changed)
    with pytest.raises(ValueError):
        m.validate_evidence_frame(header, archive,
            {**limits, "evidence_max_archive_logical_bytes": len(archive) - 1})
    with pytest.raises(ValueError, match="PAYLOAD"):
        m.validate_evidence_frame(header, archive[:-1] + b"X", limits)
    with pytest.raises(ValueError, match="FILE_IDENTITY"):
        write({**write_fixture(), "metadata": {**write_fixture()["metadata"], "nlink": 2}})
    with pytest.raises(ValueError):
        write(write_fixture(), {**limits, "evidence_max_archive_allocated_bytes": 4095})


@pytest.mark.parametrize(("field", "value"), [("uid", 1001), ("gid", 1001),
    ("mode", 0o644), ("device", 11), ("parent_inode", 22), ("acl_present", True),
    ("fixed_name_rebound", False), ("held_fd_identity_matches", False),
    ("logical_bytes", 10), ("inode", True), ("inode", 21),
    ("pread_bytes", 10), ("pread_sha256", "0" * 64)])
def test_final_archive_held_fd_identity_and_exact_parent_are_required(field, value):
    record = write_fixture()
    record["metadata"][field] = value
    with pytest.raises(ValueError):
        write(record)


@pytest.mark.parametrize(("failure", "index"), list(m.WRITE_FAILURE_AT.items()))
def test_partial_archive_failures_keep_fixed_name_and_never_retry(failure, index):
    record = dict(schema=m.WRITE_SCHEMA, fixture_only=True,
        steps=list(m.WRITE_STEPS[:index]), failure=failure, metadata=None)
    result = write(record)
    assert result["status"] == "BLOCKED_RETAINED"
    assert result["first_error"] == failure
    assert result["modeled_partial_file_retained"] == (index >= 2)
    assert result["retry_allowed"] is result["rename_or_cleanup_allowed"] is False
    assert result["fixed_basename"] == fixture()[-1]["basename"]
    assert result["host_file_created"] is False


def test_complete_evidence_write_model_and_missing_sync_or_rebinding():
    result = write(write_fixture())
    assert result["status"] == "OFFLINE_EVIDENCE_WRITE_FIXTURE_VERIFIED"
    assert result["host_file_created"] is result["field_ready"] is False
    for skipped in ["FD_CHMOD_0600", "FSYNC_FILE", "FSYNC_PARENT", "PREAD_VERIFY", "NAME_REBOUND"]:
        record = write_fixture()
        record["steps"].remove(skipped)
        with pytest.raises(ValueError, match="ORDER"):
            write(record)


def test_offline_model_has_no_runtime_or_field_side_effects_and_keeps_old_prototype_blocked():
    tree = ast.parse(Path(m.__file__).read_text())
    forbidden = {"os", "socket", "subprocess", "time", "shutil", "tempfile"}
    assert not any(isinstance(node, ast.Import) and any(alias.name in forbidden
        for alias in node.names) for node in ast.walk(tree))
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in {"open", "exec", "eval", "compile"} for node in ast.walk(tree))
    manifest, locator, context, _, _, _ = fixture()
    old = c.validate_prototype(c.build_prototype(c.document(manifest), locator, context),
        implementation_commit=D, implementation_tree=TREE)
    assert old["future_package_contract_complete"] is old["p4_contract_qualified"] is False
    assert "P2_FUTURE_PACKAGE_CONTRACT_INCOMPLETE" in old["blockers"]
    with pytest.raises(ValueError, match="FIELD_READINESS_UNPROVEN"):
        c.require_field_readiness(old)


def integrated_case():
    manifest, locator, context, window, bindings, _ = values = fixture()
    intent = make_intent(values)
    hello = dict(schema=p.HANDSHAKE_SCHEMA, kind="HELLO", guest_boot_id=GUEST_BOOT,
        hello_boottime_ns=2 * p.NS, nonce="2" * 64)
    received = [["CLOCK_MONOTONIC", 21 * p.NS], ["CLOCK_BOOTTIME", 11 * p.NS]]
    before_bind = [["CLOCK_MONOTONIC", 22 * p.NS], ["CLOCK_BOOTTIME", 12 * p.NS]]
    bind = p.make_bind(window, hello, received, before_bind, expected_guest_boot_id=GUEST_BOOT,
        intent_sha256=c.sha(intent), package_sha256=bindings["package"]["sha256"])
    ready = dict(schema=p.HANDSHAKE_SCHEMA, kind="READY", guest_boot_id=GUEST_BOOT,
        nonce=hello["nonce"], hello_sha256=bind["hello_sha256"], bind_sha256=c.sha(c.encoded(bind)),
        guest_outer_deadline_ns=bind["guest_outer_deadline_ns"],
        guest_preparation_deadline_ns=bind["guest_preparation_deadline_ns"],
        ready_boottime_ns=3 * p.NS, **p.FLAGS)
    bill = accounting()
    bill["observed_allocations"][0]["inode"] = 20
    bill["observed_allocations"][1].update(device=10, inode=21)
    bill["capture"]["record_peak"]["parent_baseline"]["inode"] = 20
    evidence_peak = bill["capture"]["evidence_peak"]
    evidence_peak["device"] = 10
    evidence_peak["parent_baseline"].update(device=10, inode=21, coverage=a.OLD_BATCH + ":code_pool")
    for snapshot in evidence_peak["snapshots"]:
        snapshot["objects"][0].update(device=10, inode=30, allocated_bytes=4096)
        for extra in snapshot["metadata_sync"]:
            extra.update(device=10, inode=405)
    header, archive = evidence()
    return dict(manifest_raw=manifest, locator_raw=locator, context_raw=context,
        window=window, bindings=bindings, intent_raw=intent,
        handshake=dict(hello=hello, received=received, before_bind=before_bind, bind=bind, ready=ready),
        accounting=bill, inventory=inventory(), trace=complete_trace(), facts=facts(),
        header_raw=header, archive_raw=archive, write_receipt=write_fixture())


def verify_case(value):
    return m.verify_offline_case(value, implementation_commit=D, implementation_tree=TREE)


def test_integrated_case_recomputes_every_binding_and_reserves_full_future_maxima():
    value = integrated_case()
    original = copy.deepcopy(value)
    result = verify_case(value)
    assert value == original
    assert result["status"] == "OFFLINE_CASE_VERIFIED"
    assert result["allow_run"] is result["field_ready"] is result["guest_executed"] is False
    assert result["normal_chain_executions"] == 0
    assert result["p4_contract_qualified"] is result["future_package_contract_complete"] is False
    assert result["accounting"]["record_reservation_bytes"] == 64 * 1024
    assert result["accounting"]["record_reservation_inodes"] == 4
    assert result["accounting"]["evidence_reservation_bytes"] == (8 + 64 + 4) * 1024
    assert result["accounting"]["observed"]["peaks"]["evidence"]["allocated_bytes"] == 72 * 1024
    assert result["accounting"]["reserved_capture_bytes"] > \
        result["accounting"]["observed"]["capture"]["total_bytes"]


@pytest.mark.parametrize("phase", a.PHASES["evidence"])
def test_archive_allocated_cap_applies_to_every_partial_final_and_sync_phase(phase):
    value = integrated_case()
    for snapshot in value["accounting"]["capture"]["evidence_peak"]["snapshots"]:
        if snapshot["phase"] == phase:
            snapshot["objects"][0]["allocated_bytes"] = 8193
    with pytest.raises(ValueError, match="ARCHIVE_CAP"):
        verify_case(value)


@pytest.mark.parametrize("kind", ["record", "evidence"])
def test_accounting_peak_parent_must_match_exact_external_locator_and_context(kind):
    value = integrated_case()
    peak = value["accounting"]["capture"][kind + "_peak"]
    parent_inode = peak["parent_baseline"]["inode"]
    peak["parent_baseline"]["inode"] += 1000
    next(row for row in value["accounting"]["observed_allocations"]
        if row["inode"] == parent_inode)["inode"] += 1000
    with pytest.raises(ValueError, match="PARENT_BINDING"):
        verify_case(value)


def test_trace_cannot_claim_a_verified_file_when_receipt_failed_before_exclusive_open():
    value = integrated_case()
    value["write_receipt"] = dict(schema=m.WRITE_SCHEMA, fixture_only=True,
        steps=["FRAME_ACCEPTED"], failure="EXISTS", metadata=None)
    with pytest.raises(ValueError, match="TRACE_WRITE_RECEIPT_BINDING"):
        verify_case(value)


def test_final_peak_inode_and_allocation_must_match_verified_archive_receipt():
    value = integrated_case()
    value["write_receipt"]["metadata"]["inode"] += 100
    with pytest.raises(ValueError, match="ARCHIVE_IDENTITY"):
        verify_case(value)


def test_prewrite_reserved_capacity_cannot_use_smaller_observed_record_or_archive():
    value = integrated_case()
    observed = a.evaluate_accounting(value["accounting"])
    device = next(row for row in value["accounting"]["devices"] if row["device"] == 10)
    bill = next(row for row in observed["devices"] if row["device"] == 10)
    device["available_bytes"] = bill["future_demand_bytes"]
    device["available_inodes"] = bill["future_demand_inodes"]
    result = verify_case(value)
    assert result["accounting"]["observed"]["offline_admitted"] is True
    assert result["status"] == "OFFLINE_CASE_BLOCKED"
    assert "RESERVED_DEVICE_10_CAPACITY_EXCEEDED" in result["blockers"]


def test_full_maximum_subreservations_remain_inside_one_global_capture_ceiling():
    value = integrated_case()
    observed = a.evaluate_accounting(value["accounting"])
    extra = a.CAPTURE_BYTES - observed["capture"]["total_bytes"]
    value["accounting"]["capture"]["future"][0]["allocated_bytes"] += extra
    result = verify_case(value)
    assert result["accounting"]["observed"]["offline_admitted"] is True
    assert "RESERVED_GLOBAL_CAPTURE_CEILING_EXCEEDED" in result["blockers"]


def test_unknown_parent_peak_or_predecessor_usage_keeps_joint_case_blocked():
    value = integrated_case()
    peak = value["accounting"]["capture"]["evidence_peak"]
    peak.update(qualification="UNKNOWN", snapshots=None)
    result = verify_case(value)
    assert result["status"] == "OFFLINE_CASE_BLOCKED"
    assert result["accounting"]["reserved_capture_bytes"] is None
    value = integrated_case()
    value["inventory"]["projects"][0]["usage_state"] = "UNKNOWN"
    assert verify_case(value)["status"] == "OFFLINE_CASE_BLOCKED"


def test_integrated_handshake_rejects_caller_supplied_digest_unbound_to_actual_intent():
    value = integrated_case()
    value["handshake"]["bind"]["intent_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="BIND_MISMATCH"):
        verify_case(value)


@pytest.mark.parametrize("field", ["allocated_bytes", "inodes"])
def test_reserved_future_demands_reject_integer_overflow(field):
    value = integrated_case()
    bill = next(row for row in a.evaluate_accounting(value["accounting"])["devices"]
        if row["device"] == 10)
    source = "future_demand_bytes" if field == "allocated_bytes" else "future_demand_inodes"
    extra = dict(reservation_id="earlier-overflow-bound", batch="earlier-failure",
        category="retained-overflow-bound", device=10, allocated_bytes=0, inodes=0,
        status="UNRELEASED")
    extra[field] = a.MAX_INTEGER - bill[source]
    value["accounting"]["commitments"].append(extra)
    value["accounting"]["historical_inventory"]["expected_reservation_ids"].append(extra["reservation_id"])
    device = next(row for row in value["accounting"]["devices"] if row["device"] == 10)
    device["available_bytes" if field == "allocated_bytes" else "available_inodes"] = a.MAX_INTEGER
    assert a.evaluate_accounting(value["accounting"])["offline_admitted"] is True
    with pytest.raises(ValueError, match="ACCOUNTING_INTEGER"):
        verify_case(value)
