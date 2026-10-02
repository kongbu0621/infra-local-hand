"""Independent RAM-only H07 counterexamples; no host qualification claim."""
import base64
import copy
from functools import lru_cache
from pathlib import Path, PurePosixPath
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Inherited strict Q2 fixtures require Linux contracts", allow_module_level=True)

from e3_host import q2_host_window_h07 as m
from test_e3_q2_reconciliation_sources import manifest_fixture


MODEL_SCHEMA = "local-hand-q2-host-window-h07-model-trace/v1"
EDGE_IDS = ("owner_supervisor", "supervisor_target")
FALSE_FIELDS = ("source_admission_proven", "source_code_git_verified", "h07_proven",
    "actual_closed", "remote_stop_proven", "dispatch_allowed", "field_ready", "allow_run",
    "allow_consume", "all_domains_covered", "original_window_proven", "q2_accepted",
    "q3_accepted", "production_supported")
NS = 10**9
WINDOW = dict(issued_ns=10 * NS, deadline_ns=310 * NS,
    boottime_issued_ns=20 * NS, boottime_deadline_ns=320 * NS)


@lru_cache(maxsize=1)
def strict_plan():
    original, previous, manifest = manifest_fixture()
    raw = m.encoded(manifest)
    checked = m.c.decode(raw, m.sha(raw), implementation_commit="c" * 40)
    return m.c.bind(checked, original, previous)[1]


def edges():
    plan = strict_plan()
    result = []
    for edge, role, parent in ((EDGE_IDS[0], "supervisor", "supervisor"),
                              (EDGE_IDS[1], "target", "controller")):
        unit = plan["settings"]["controllers"][role]["unit"]
        result.append(dict(id=edge, expected_unit=unit,
            planned_cgroup="/" + plan["parents"][parent]["unit"] + "/" + unit))
    return result


def event(edge, kind, data=None):
    return dict(edge=edge, kind=kind, monotonic_ns=11 * NS, boottime_ns=21 * NS,
        data={} if data is None else data)


def instance(edge):
    target = next(row for row in edges() if row["id"] == edge)
    return dict(unit=target["expected_unit"], cgroup=target["planned_cgroup"],
        invocation_id=("1" if edge == EDGE_IDS[0] else "2") * 32,
        pid=101 if edge == EDGE_IDS[0] else 102, cgroup_device=4,
        cgroup_inode=1001 if edge == EDGE_IDS[0] else 1002)


def trace(events, *, binding="a" * 64, window_raw=None):
    window_raw = m.encoded(WINDOW) if window_raw is None else window_raw
    return dict(schema=MODEL_SCHEMA, binding_sha256=binding,
        original_window_sha256=m.sha(window_raw), events=copy.deepcopy(events))


def model(events, *, change=None, window_raw=None):
    window_raw = m.encoded(WINDOW) if window_raw is None else window_raw
    value = trace(events, window_raw=window_raw)
    if change is not None:
        change(value)
    return m._model(m.encoded(value), window_raw, "a" * 64, edges())


def model_edge(result, edge):
    return next(row for row in result["edges"] if row["edge"] == edge)


def assert_model_unproven(result):
    assert result["model_trace_consistent"] is True
    assert result["evidence_use"] == "UNTRUSTED_MODEL_ONLY"
    assert result["actual_closed"] is result["remote_stop_proven"] is False
    assert result["future_activation_fenced"] is False
    assert result["original_window_proven"] is False
    assert all(row["actual_closed"] is row["pending_resolved"] is False for row in result["edges"])
    assert all(row["activation_may_still_occur"] is True for row in result["edges"])


@pytest.mark.parametrize("edge", EDGE_IDS)
def test_submitted_without_original_remains_unknown_pending(edge):
    result = model([event(edge, "SUBMITTED")])
    row = model_edge(result, edge)
    assert row["submitted"] is True and row["instance"] is None
    assert row["state"] == "MODEL_REQUEST_SUBMITTED"
    assert_model_unproven(result)


@pytest.mark.parametrize("edge", EDGE_IDS)
def test_cancel_activation_race_retains_instance_and_does_not_resolve_pending(edge):
    result = model([event(edge, "SUBMITTED"), event(edge, "QUEUED", dict(job_id=42)),
        event(edge, "CANCEL_ACK", dict(job_id=42)), event(edge, "JOB_ABSENT"),
        event(edge, "INSTANCE_BOUND", instance(edge))])
    row = model_edge(result, edge)
    assert row["cancel_acknowledged"] is row["activation_after_cancel"] is True
    assert row["instance"] == instance(edge)
    assert row["state"] == "MODEL_INSTANCE_REPORTED"
    assert_model_unproven(result)


@pytest.mark.parametrize("edge", EDGE_IDS)
def test_pending_empty_snapshot_client_eof_and_stop_ack_do_not_clear_submission(edge):
    result = model([event(edge, "SUBMITTED"), event(edge, "QUEUED", dict(job_id=42)),
        event(edge, "CANCEL_ACK", dict(job_id=42)), event(edge, "JOB_ABSENT"),
        event(edge, "STOP_REQUESTED"), event(edge, "STOP_ACK"), event(edge, "EMPTY_SNAPSHOT"),
        event(edge, "EOF", dict(stream="stdout")), event(edge, "EOF", dict(stream="stderr"))])
    row = model_edge(result, edge)
    assert row["submitted"] is True and row["instance"] is None
    assert row["state"] == "MODEL_UNOBSERVED_PENDING"
    assert row["empty_snapshot_reported"] is row["stop_acknowledged"] is True
    assert row["eof"] == ["stderr", "stdout"]
    assert_model_unproven(result)


def test_target_stop_and_eof_cannot_close_owner_supervisor_edge():
    owner, target = EDGE_IDS
    result = model([event(owner, "SUBMITTED"), event(owner, "QUEUED", dict(job_id=42)),
        event(target, "SUBMITTED"), event(target, "INSTANCE_BOUND", instance(target)),
        event(target, "STOP_REQUESTED"), event(target, "STOP_ACK"), event(target, "EMPTY_SNAPSHOT"),
        event(target, "EOF", dict(stream="stdout")), event(target, "EOF", dict(stream="stderr"))])
    assert model_edge(result, owner)["state"] == "MODEL_JOB_QUEUED"
    assert model_edge(result, owner)["eof"] == []
    assert model_edge(result, owner)["stop_acknowledged"] is False
    assert model_edge(result, target)["state"] == "MODEL_STOP_ACK_REPORTED"
    assert_model_unproven(result)


@pytest.mark.parametrize("kind", ["CLOSED", "FENCE", "FENCED", "SEALED", "NOT_DISPATCHED"])
def test_caller_cannot_insert_a_closure_or_fence_operation(kind):
    with pytest.raises(ValueError, match="H07_MODEL_EVENT_KIND"):
        model([event(EDGE_IDS[0], "SUBMITTED"), event(EDGE_IDS[0], kind)])


@pytest.mark.parametrize("change", [
    lambda x: x.update(origin="sealed-field-evidence"),
    lambda x: x.update(actual_closed=True),
    lambda x: x.update(schema="local-hand-q2-host-window-h07-model-trace/v2"),
    lambda x: x.update(binding_sha256="b" * 64),
    lambda x: x.update(original_window_sha256="b" * 64),
    lambda x: x["events"][0].update(original=None),
    lambda x: x["events"][0]["data"].update(future_starts_blocked=True),
])
def test_trace_exact_fields_and_external_bindings_reject_self_authorization(change):
    with pytest.raises(ValueError):
        model([event(EDGE_IDS[0], "SUBMITTED")], change=change)


@pytest.mark.parametrize("fault", ["wrong_edge", "new_invocation", "new_pid", "new_inode",
    "new_unit", "new_cgroup", "zero_invocation"])
def test_instance_identity_and_edge_binding_cannot_follow_replacement(fault):
    edge = EDGE_IDS[0]
    data = instance(edge)
    if fault == "wrong_edge": data = instance(EDGE_IDS[1])
    elif fault == "new_invocation": data["invocation_id"] = "3" * 32
    elif fault == "new_pid": data["pid"] += 1
    elif fault == "new_inode": data["cgroup_inode"] += 1
    elif fault == "new_unit": data["unit"] = "lhqother.service"
    elif fault == "new_cgroup": data["cgroup"] += "-other"
    else: data["invocation_id"] = "0" * 32
    with pytest.raises(ValueError):
        model([event(edge, "SUBMITTED"), event(edge, "INSTANCE_BOUND", instance(edge)),
            event(edge, "INSTANCE_BOUND", data)])


@pytest.mark.parametrize("events", [
    [event(EDGE_IDS[0], "QUEUED", dict(job_id=42))],
    [event(EDGE_IDS[0], "SUBMITTED"), event(EDGE_IDS[0], "SUBMITTED")],
    [event(EDGE_IDS[0], "SUBMITTED"), event(EDGE_IDS[1], "STOP_ACK")],
    [event(EDGE_IDS[0], "SUBMITTED"), event(EDGE_IDS[0], "STOP_ACK")],
    [event(EDGE_IDS[0], "SUBMITTED"), event(EDGE_IDS[0], "QUEUED", dict(job_id=42)),
     event(EDGE_IDS[0], "CANCEL_ACK", dict(job_id=43))],
    [event(EDGE_IDS[0], "SUBMITTED"), event(EDGE_IDS[0], "QUEUED", dict(job_id=True))],
    [event(EDGE_IDS[0], "SUBMITTED"), event(EDGE_IDS[0], "EOF", dict(stream="stdout")),
     event(EDGE_IDS[0], "EOF", dict(stream="stdout"))],
])
def test_invalid_event_order_and_nonexact_identifiers_fail(events):
    with pytest.raises(ValueError):
        model(events)


@pytest.mark.parametrize("fault", ["mono_expired", "boot_expired", "mono_reverse", "boot_reverse",
    "clock_diverged", "bool_clock", "too_many"])
def test_original_dual_clock_window_and_event_bounds_cannot_be_renewed(fault):
    events = [event(EDGE_IDS[0], "SUBMITTED"), event(EDGE_IDS[0], "EMPTY_SNAPSHOT")]
    if fault == "mono_expired": events[-1]["monotonic_ns"] = WINDOW["deadline_ns"]
    elif fault == "boot_expired": events[-1]["boottime_ns"] = WINDOW["boottime_deadline_ns"]
    elif fault == "mono_reverse": events[-1]["monotonic_ns"] -= 1
    elif fault == "boot_reverse": events[-1]["boottime_ns"] -= 1
    elif fault == "clock_diverged": events[-1]["boottime_ns"] += 2 * NS + 1
    elif fault == "bool_clock": events[-1]["monotonic_ns"] = True
    else: events += [event(EDGE_IDS[0], "EMPTY_SNAPSHOT")] * 127
    with pytest.raises(ValueError):
        model(events)


@pytest.mark.parametrize("field", tuple(WINDOW))
def test_trace_cannot_supply_or_extend_its_original_window(field):
    changed = dict(WINDOW)
    changed[field] += 1
    with pytest.raises(ValueError):
        model([], window_raw=m.encoded(changed))


@pytest.mark.parametrize("blobs", [{}, {"a" * 64: bytearray(b"x")}, {"a" * 64: b"x"},
    {1: b"x"}, [("a" * 64, b"x")]])
def test_public_api_rejects_nonplain_or_unhashed_blob_inputs_before_provenance(blobs):
    with pytest.raises(ValueError):
        m.review_h07(b"{}", b"{}", blobs, implementation_commit="c" * 40,
            carrier_raw=b"x", host_attestation_raw=b"{}")


@pytest.fixture
def isolated_source_stage(monkeypatch):
    """Mock only full provenance, explicitly not an end-to-end verify fixture.

    The inherited manifest and plan still pass their real decode/bind checks.
    Full sources.verify requires the separately retained private evidence; its
    independent review is not replaced by this boundary/model test fixture.
    """
    original, previous, manifest = manifest_fixture()
    manifest["execution"]["source"]["files"]["/synthetic/startup-tools/" + m.TOOL_NAME] = "7" * 64
    manifest_raw = m.encoded(manifest)
    checked = m.c.decode(manifest_raw, m.sha(manifest_raw), implementation_commit="c" * 40)
    execution, plan, _ = m.c.bind(checked, original, previous)
    verified = SimpleNamespace(execution=execution, plan=plan, implementation_commit="c" * 40)
    location = dict(expected_boot_id="22222222-2222-2222-2222-222222222222")
    config = dict(schema=m.entry.SCHEMA, authority=copy.deepcopy(m.entry.AUTHORITY),
        host_window_authority=copy.deepcopy(m.entry.HOST_AUTHORITY),
        amendment_sha256=m.sha(manifest_raw), inputs_sha256=m.sha(manifest_raw),
        attempt_id=execution["attempt_id"], source_commit="c" * 40,
        source_tree=execution["source"]["tree"], candidate=plan["candidate"]["commit"],
        wheel_sha256=plan["candidate"]["wheel_sha256"],
        host_result_directory="/synthetic-host/results", old_host_files=[
            dict(path="/synthetic-host/old-1", sha256="1" * 64),
            dict(path="/synthetic-host/old-2", sha256="2" * 64)],
        guest_pin={key: copy.deepcopy(plan["host"][key]) for key in ("hostname", "boot_id", "initial_userns")},
        ssh_wrapper="/synthetic-host/ssh-wrapper", guest_python="/usr/bin/python3.12",
        guest_stage=str(PurePosixPath(plan["candidate"]["source"]).parent),
        guest_outer_unit="lhq-configured-outer.service")
    m.entry.validate_config(config)
    calls = []

    def only_provenance_is_mocked(config, inputs, carrier, attestation):
        calls.append(copy.deepcopy((config, inputs, carrier, attestation)))
        return verified, copy.deepcopy(location)

    monkeypatch.setattr(m.entry, "offline_inputs", only_provenance_is_mocked)
    raw = b"synthetic source member"
    return dict(config_raw=m.encoded(config), manifest_raw=manifest_raw,
        blobs={m.sha(raw): raw}, implementation_commit="c" * 40,
        carrier_raw=b"synthetic carrier", host_attestation_raw=b"synthetic attestation",
        verified=verified, location=location, calls=calls)


def isolated_review(fixture, **changes):
    args = {key: value for key, value in fixture.items() if key not in ("verified", "location", "calls")}
    args.update(changes)
    return m.review_h07(**args)


def assert_all_actual_flags_false(result):
    assert result["status"] == "CONSISTENT_BUT_BLOCKED"
    for key in FALSE_FIELDS:
        assert result[key] is False, key
    assert result["retained_clock_review"]["dispatch_allowed"] is False
    assert all(row["actual_identity_observed"] is False for row in result["domains"])


def test_strict_plan_derives_sibling_parents_three_phases_and_unresolved_domains():
    plan = strict_plan()
    original = copy.deepcopy(plan)
    rows, request_edges = m._domains(plan, dict(guest_outer_unit="lhq-configured-outer.service"))
    by_role = {row["role"]: row for row in rows}
    assert len(by_role) == len(rows) == 36
    assert plan == original
    for role in ("query", "management", "controller", "supervisor", "ordinary"):
        row = by_role["parent." + role]
        assert row["unit"] == plan["parents"][role]["unit"]
        assert row["planned_cgroup"] == (None if role == "ordinary" else "/" + row["unit"])
    assert by_role["controller.supervisor"]["parent_role"] == "parent.supervisor"
    assert by_role["controller.target"]["parent_role"] == "parent.controller"
    ordinary_units = set()
    for phase in ("preflight", "business", "evidence"):
        for stage, suffix in (("main", ""), ("bootstrap", ":bootstrap"), ("result_reader", ":result_reader")):
            row = by_role["ordinary." + phase + "." + stage]
            identity = "job-" + plan["settings"]["identity"]["operation_id"] + "-" + phase + suffix
            assert row["unit"] == "lhj-" + m.sha(identity.encode()) + ".service"
            assert row["kind"] == "EXPECTED_NAME_ONLY" and row["planned_cgroup"] is None
            assert row["parent_role"] == "parent.ordinary"
            ordinary_units.add(row["unit"])
        for stage, parent in (("query", "query"), ("listener", "management"), ("admission", "management")):
            row = by_role["quota." + phase + "." + stage]
            assert row["kind"] == "ISSUED_REQUEST_REQUIRED"
            assert row["unit"] is row["planned_cgroup"] is None
            assert row["parent_role"] == "parent." + parent
    assert len(ordinary_units) == 9
    for role in ("host_client", "guest_session", "guest_shell", "guest_sudo", "first_probe",
                 "guest_loader", "collector", "owner_process", "stop_finalizer_endpoint", "pre_dispatch_supervision"):
        row = by_role[role]
        assert row["kind"] == "UNRESOLVED_CONTROL_DOMAIN"
        assert row["unit"] is row["planned_cgroup"] is None
    assert [row["id"] for row in request_edges] == list(EDGE_IDS)
    assert request_edges[0]["source_role"] == "owner_process"
    assert request_edges[0]["target_role"] == request_edges[1]["source_role"] == "controller.supervisor"
    assert request_edges[1]["target_role"] == "controller.target"
    assert all(row["actual_identity_observed"] is False for row in rows)


def test_isolated_public_report_keeps_unmodeled_calls_and_all_actual_gates_false(isolated_source_stage):
    fixture = isolated_source_stage
    result = isolated_review(fixture)
    assert result["modeled_edges"] == list(EDGE_IDS)
    unresolved = result["unmodeled_required_edges"]
    assert {row["id"] for row in unresolved} == {
        "host_to_first_probe", "host_to_outer", "host_to_collector",
        *("phase_" + phase + "_" + stage for phase in ("preflight", "business", "evidence")
          for stage in ("query", "listener", "admission"))}
    assert result["outer_declaration"]["names_equal"] is False
    assert result["outer_declaration"]["actual_outer_identity_proven"] is False
    assert result["outer_declaration"]["equality_required_by_existing_contract"] is False
    assert result["model"] is None
    assert_all_actual_flags_false(result)
    binding = result["binding"]
    assert binding["manifest_sha256"] == m.sha(fixture["manifest_raw"])
    assert binding["configuration_sha256"] == m.sha(fixture["config_raw"])
    assert binding["plan_sha256"] == m.sha(m.encoded(fixture["verified"].plan))
    assert binding["source_files_sha256"] == m.sha(m.encoded(fixture["verified"].execution["source"]["files"]))
    assert binding["location_sha256"] == m.sha(m.encoded(fixture["location"]))
    assert result["binding_sha256"] == m.sha(m.encoded(binding))


def test_isolated_public_model_cannot_turn_complete_looking_observations_into_actual_closure(isolated_source_stage):
    fixture = isolated_source_stage
    binding = isolated_review(fixture)["binding_sha256"]
    events = []
    for edge in EDGE_IDS:
        events.extend([event(edge, "SUBMITTED"), event(edge, "INSTANCE_BOUND", instance(edge)),
            event(edge, "STOP_REQUESTED"), event(edge, "STOP_ACK"), event(edge, "EMPTY_SNAPSHOT"),
            event(edge, "EOF", dict(stream="stdout")), event(edge, "EOF", dict(stream="stderr"))])
    value = trace(events, binding=binding)
    result = isolated_review(fixture, original_window_raw=m.encoded(WINDOW), trace_raw=m.encoded(value))
    assert_all_actual_flags_false(result)
    assert_model_unproven(result["model"])


def test_isolated_input_boundary_copies_and_encodes_plain_bytes_without_source_execution(isolated_source_stage):
    fixture = isolated_source_stage
    before = copy.deepcopy(fixture["blobs"])
    isolated_review(fixture)
    config, inputs, carrier, attestation = fixture["calls"][-1]
    assert config == m.c.document(fixture["config_raw"])
    assert base64.b64decode(inputs["manifest_raw"], validate=True) == fixture["manifest_raw"]
    assert inputs["manifest_sha256"] == m.sha(fixture["manifest_raw"])
    assert inputs["implementation_commit"] == fixture["implementation_commit"]
    assert {pin: base64.b64decode(raw, validate=True) for pin, raw in inputs["blobs"].items()} == before
    inputs["blobs"].clear()
    assert fixture["blobs"] == before
    assert (carrier, attestation) == (fixture["carrier_raw"], fixture["host_attestation_raw"])


@pytest.mark.parametrize("fault", ["missing", "duplicate"])
def test_isolated_extra_source_closure_is_required_without_changing_legacy_list(isolated_source_stage, fault):
    fixture = isolated_source_stage
    files = fixture["verified"].execution["source"]["files"]
    assert m.TOOL_NAME not in m.c.REQUIRED_SOURCE_FILES
    assert m.TOOL_NAME not in m.c.old.REQUIRED_SOURCE_FILES
    if fault == "missing": files.pop("/synthetic/startup-tools/" + m.TOOL_NAME)
    else: files["/another-tool-directory/" + m.TOOL_NAME] = "8" * 64
    with pytest.raises(ValueError, match="H07_EXTRA_SOURCE_CLOSURE_REQUIRED"):
        isolated_review(fixture)


@pytest.mark.parametrize("field", ["config_raw", "manifest_raw", "carrier_raw", "host_attestation_raw"])
@pytest.mark.parametrize("form", ["bytearray", "empty", "oversized"])
def test_input_bytes_type_and_bounds_fail_before_mocked_provenance(isolated_source_stage, field, form):
    fixture = isolated_source_stage
    limits = dict(config_raw=m.CONFIG_LIMIT, manifest_raw=m.c.INPUT_LIMIT,
        carrier_raw=m.h.CARRIER_BYTES, host_attestation_raw=m.h.ATTESTATION_BYTES)
    raw = bytearray(fixture[field]) if form == "bytearray" else b"" if form == "empty" else b"x" * (limits[field] + 1)
    with pytest.raises(ValueError):
        isolated_review(fixture, **{field: raw})
    assert fixture["calls"] == []


def test_blob_total_bound_fails_before_provenance(isolated_source_stage):
    raw = b"x" * (m.INPUT_LIMIT + 1)
    with pytest.raises(ValueError, match="H07_BLOB_CONTENT"):
        isolated_review(isolated_source_stage, blobs={m.sha(raw): raw})
    assert isolated_source_stage["calls"] == []


@pytest.mark.parametrize("supplied", ["trace_raw", "original_window_raw"])
def test_window_and_trace_are_required_together_before_input_validation(supplied):
    with pytest.raises(ValueError, match="H07_TRACE_WINDOW_PAIR"):
        m.review_h07(None, None, None, implementation_commit=None, carrier_raw=None,
            host_attestation_raw=None, **{supplied: b"{}"})


@pytest.mark.parametrize("name,value", [("allow_run", True), ("field_ready", True),
    ("domains", []), ("original_window_proven", True), ("source_admission_proven", True),
    ("verified", object()), ("fence", "CLOSED")])
def test_public_api_has_no_caller_authority_domain_or_verified_token_override(name, value):
    with pytest.raises(TypeError):
        m.review_h07(b"{}", b"{}", {}, implementation_commit="c" * 40,
            carrier_raw=b"x", host_attestation_raw=b"{}", **{name: value})


def test_isolated_public_api_performs_no_field_io_or_process_operation(monkeypatch, isolated_source_stage):
    import builtins
    import os
    import socket
    import subprocess
    import time

    def forbidden(*args, **kwargs):
        raise AssertionError("pure H07 API attempted field operation")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        for name in ("open", "read_bytes", "read_text", "stat", "lstat", "iterdir"):
            guard.setattr(Path, name, forbidden)
        for name in ("open", "stat", "lstat", "scandir", "listdir", "system"):
            guard.setattr(os, name, forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(time, "clock_gettime_ns", forbidden)
        result = isolated_review(isolated_source_stage)
    assert_all_actual_flags_false(result)


def test_replacement_after_stop_ack_and_eof_keeps_late_activation_risk():
    edge = EDGE_IDS[0]
    result = model([event(edge, "SUBMITTED"), event(edge, "STOP_REQUESTED"),
        event(edge, "STOP_ACK"), event(edge, "EMPTY_SNAPSHOT"),
        event(edge, "EOF", dict(stream="stdout")), event(edge, "EOF", dict(stream="stderr")),
        event(edge, "INSTANCE_BOUND", instance(edge))])
    assert model_edge(result, edge)["activation_after_stop_ack"] is True
    assert_model_unproven(result)


@pytest.mark.parametrize("edge", EDGE_IDS)
def test_unobserved_request_can_enter_queue_after_job_absence(edge):
    result = model([event(edge, "SUBMITTED"), event(edge, "JOB_ABSENT"),
        event(edge, "EMPTY_SNAPSHOT"), event(edge, "EOF", dict(stream="stdout")),
        event(edge, "EOF", dict(stream="stderr")), event(edge, "QUEUED", dict(job_id=42))])
    row = model_edge(result, edge)
    assert row["queue_after_absence"] is True and row["job_id"] == 42
    assert row["instance"] is None and row["state"] == "MODEL_UNOBSERVED_PENDING"
    assert_model_unproven(result)


@pytest.mark.parametrize("replacement", [42, 43])
def test_previously_bound_job_cannot_reappear_or_change_after_absence(replacement):
    edge = EDGE_IDS[0]
    with pytest.raises(ValueError, match="H07_MODEL_JOB_CHANGED"):
        model([event(edge, "SUBMITTED"), event(edge, "QUEUED", dict(job_id=42)),
            event(edge, "JOB_ABSENT"), event(edge, "QUEUED", dict(job_id=replacement))])


def qualification_fixture():
    """All facts here are invented; independent external pins remain untrusted."""
    contract = m.qualification_contract(implementation_commit="c" * 40, source_binding_sha256="a" * 64)
    clocks = {role: dict(boot_id=str(index) * 8 + "-" + str(index) * 4 + "-" + str(index) * 4 +
        "-" + str(index) * 4 + "-" + str(index) * 12,
        monotonic_issued_ns=index * 1000 * NS, boottime_issued_ns=(index * 1000 + 10) * NS,
        monotonic_deadline_ns=(index * 1000 + 300) * NS, boottime_deadline_ns=(index * 1000 + 310) * NS)
        for index, role in enumerate(("host", "guest"), 1)}
    limits = dict(allocated_bytes=10000, inodes=10000, output_bytes=10000, cpu_ns=10000, calls=10000)
    budget = dict(ledger_sha256="b" * 64, reserves=dict(stop_ns=1, eof_ns=2, fsync_ns=3, seal_ns=4),
        reservations={"d" * 64: limits})
    requests, records = {}, []
    for index, edge in enumerate(contract["request_edges"], 1):
        requests[edge["id"]] = dict(request_sha256=m.sha(("request" + str(index)).encode()),
            intent_sha256=m.sha(("intent" + str(index)).encode()), command_sha256=m.sha(("command" + str(index)).encode()),
            deadline_ns=clocks[edge["clock_domain"]]["boottime_deadline_ns"],
            job_id=index if edge["manager_start"] else None,
            instance=dict(unit="synthetic-" + str(index) + ".service" if edge["manager_start"] else None,
                cgroup="/synthetic.slice/instance-" + str(index), invocation_id=f"{index:032x}" if edge["manager_start"] else None,
                pid=1000 + index, start_ticks=2000 + index, cgroup_device=3, cgroup_inode=3000 + index),
            clients={role: dict(pid=4000 + index * 2 + offset, start_ticks=5000 + index * 2 + offset)
                for offset, role in enumerate(edge["client_roles"])}, reservation_sha256="d" * 64)
        records.append(dict(edge=edge["id"], events=[], usage=dict.fromkeys(m.USAGE_FIELDS, 1)))
    fixture = dict(implementation_commit="c" * 40, source_binding_sha256="a" * 64,
        clocks=clocks, requests=requests, budget=budget)
    trace_value = dict(schema="local-hand-q2-h07-current-route-model/v1", contract_sha256=m.sha(m.encoded(contract)),
        clocks_sha256=m.sha(m.encoded(clocks)), requests_sha256=m.sha(m.encoded(requests)), budget_sha256=m.sha(m.encoded(budget)),
        system_manager_calls=0, root_control_calls=0, records=records)
    return fixture, trace_value, contract


def qualification_event(fixture, edge, kind, data=None, *, offset=1):
    _, _, contract = qualification_fixture()
    descriptor = next(row for row in contract["request_edges"] if row["id"] == edge)
    clock = fixture["clocks"][descriptor["clock_domain"]]
    return dict(kind=kind, monotonic_ns=clock["monotonic_issued_ns"] + offset,
        boottime_ns=clock["boottime_issued_ns"] + offset, data={} if data is None else copy.deepcopy(data))


def qualification_events(fixture, edge):
    pin = fixture["requests"][edge]
    event_data = [("SUBMITTED", {name: pin[name] for name in ("request_sha256", "intent_sha256", "command_sha256")})]
    if pin["job_id"] is not None:
        event_data.append(("QUEUED", dict(job_id=pin["job_id"])))
    event_data.append(("INSTANCE_BOUND", dict(instance=pin["instance"])))
    for kind in ("STOP_REQUESTED", "STOP_ACK"):
        event_data.append((kind, dict(instance_sha256=m.sha(m.encoded(pin["instance"])))))
    event_data.extend([("JOB_ABSENT", {}), ("TREE_EMPTY", {})])
    for role, client in pin["clients"].items():
        client_pin = dict(client_role=role, client_sha256=m.sha(m.encoded(client)))
        event_data.append(("CLIENT_EXIT", dict(client_pin, returncode=0)))
        event_data.extend(("EOF", dict(client_pin, stream=stream)) for stream in ("stdout", "stderr"))
    return [qualification_event(fixture, edge, kind, data, offset=index)
        for index, (kind, data) in enumerate(event_data, 1)]


def qualification_record(value, edge):
    return next(row for row in value["records"] if row["edge"] == edge)


def qualification_review(fixture, value):
    return m.review_qualification_model(m.encoded(value), **fixture)


def assert_qualification_unknown(result):
    assert result["qualification"] == "UNKNOWN"
    assert result["evidence_use"] == "UNTRUSTED_MODEL_ONLY"
    assert result["whole_run_rate_pause_proven"] is result["future_activation_fenced"] is False
    for key in FALSE_FIELDS:
        assert result[key] is result["contract"][key] is False
    assert all(row["qualification"] == "UNKNOWN" and row["actual_closed"] is False for row in result["edges"])


def test_current_route_contract_covers_nine_stages_and_existing_native_children_without_new_geometry():
    _, _, contract = qualification_fixture()
    ids = {row["id"] for row in contract["request_edges"]}
    expected = {"host_ssh", "ssh_session", "session_shell", "shell_sudo", "first_probe", "guest_loader", "loader_outer",
        "outer_owner", "owner_supervisor", "supervisor_target", "target_gateway", "host_collector", "remote_collector",
        "stop_finalizer", "pre_dispatch_supervision", "same_channel_evidence"}
    for phase in ("preflight", "business", "evidence"):
        expected.update("gateway_" + phase + "_" + stage for stage in ("bootstrap", "helper", "result_reader"))
        expected.update(phase + "_" + role for role in ("listener", "admission", "request", "worker_handoff", "query"))
        expected.add("management_" + phase)
        expected.update(phase + "_native_" + role for role in ("work", "evidence", "temporary"))
    expected.add("evidence_native_retained_store")
    assert ids == expected and len(ids) == len(contract["request_edges"]) == 53
    assert {row["id"] for row in contract["request_edges"] if row["coverage"] == "RETAINED_LEGACY_COUNTEREXAMPLE"} == {
        "first_probe", "host_collector", "remote_collector"}
    assert contract["proposed_delivery"] == "ONE_SSH_WITH_SAME_CHANNEL_COLLECTION_NO_SECOND_SSH"
    assert contract["parent_geometry"] == dict(controller_memory_bytes=512 * 1024**2, controller_tasks=64,
        target_memory_bytes=256 * 1024**2, target_tasks=32, ordinary_memory_bytes=256 * 1024**2, ordinary_tasks=32,
        ordinary_relation="CONTROLLER_CHILD_SIBLING_OF_TARGET")
    assert contract["existing_limits"] == dict(ordinary_deliveries=9, system_manager_calls=256, root_control_calls=256)


def test_complete_synthetic_route_still_has_no_future_fence_or_actual_qualification():
    fixture, value, _ = qualification_fixture()
    for row in value["records"]:
        row["events"] = qualification_events(fixture, row["edge"])
    result = qualification_review(fixture, value)
    assert_qualification_unknown(result)
    assert all(row["missing"] == ["FUTURE_ADMISSION_FENCE_NOT_PROVEN"] for row in result["edges"])
    assert result["budget_usage"]["d" * 64] == dict.fromkeys(m.USAGE_FIELDS, 53)


def test_lost_reply_cannot_be_closed_by_stop_absence_and_original_client_eof():
    fixture, value, _ = qualification_fixture()
    edge = "gateway_business_helper"
    events = qualification_events(fixture, edge)
    qualification_record(value, edge)["events"] = [row for row in events if row["kind"] not in ("QUEUED", "INSTANCE_BOUND")]
    result = qualification_review(fixture, value)
    row = model_edge(result, edge)
    assert row["state"] == "MODEL_UNOBSERVED_PENDING"
    assert "ORIGINAL_INSTANCE_UNPROVEN" in row["missing"]
    assert_qualification_unknown(result)


@pytest.mark.parametrize("kind", ["QUEUED", "INSTANCE_BOUND"])
def test_late_queue_or_activation_after_stop_and_empty_tree_restores_missing_proof(kind):
    fixture, value, _ = qualification_fixture()
    edge = "gateway_evidence_result_reader"
    events = qualification_events(fixture, edge)
    data = dict(job_id=fixture["requests"][edge]["job_id"]) if kind == "QUEUED" else dict(instance=fixture["requests"][edge]["instance"])
    events.append(qualification_event(fixture, edge, kind, data, offset=19))
    qualification_record(value, edge)["events"] = events
    result = qualification_review(fixture, value)
    row = model_edge(result, edge)
    assert row["late_queue" if kind == "QUEUED" else "late_activation"] is True
    assert row["job_absent" if kind == "QUEUED" else "tree_empty"] is False
    if kind == "QUEUED":
        assert "JOB_TERMINAL_UNPROVEN" in row["missing"]
    assert "ORIGINAL_STOP_UNPROVEN" in row["missing"] and "TREE_EMPTY_UNPROVEN" in row["missing"]
    assert_qualification_unknown(result)


@pytest.mark.parametrize("kind,missing", [("JOB_ABSENT", "JOB_TERMINAL_UNPROVEN"),
    ("TREE_EMPTY", "TREE_EMPTY_UNPROVEN")])
def test_snapshot_before_stop_ack_cannot_supply_final_closure_fact(kind, missing):
    fixture, value, _ = qualification_fixture()
    edge = "gateway_business_helper"
    events = qualification_events(fixture, edge)
    snapshot = next(event for event in events if event["kind"] == kind)
    events.remove(snapshot)
    ack_index = next(index for index, event in enumerate(events) if event["kind"] == "STOP_ACK")
    events.insert(ack_index, snapshot)
    qualification_record(value, edge)["events"] = [qualification_event(fixture, edge,
        event["kind"], event["data"], offset=index) for index, event in enumerate(events, 1)]
    result = qualification_review(fixture, value)
    row = model_edge(result, edge)
    assert row["stop_ack"] is True and row["late_queue"] is row["late_activation"] is False
    assert row["job_absent" if kind == "JOB_ABSENT" else "tree_empty"] is False
    assert missing in row["missing"]
    assert_qualification_unknown(result)


def test_target_closure_does_not_close_ordinary_sibling_or_finalizer_endpoint():
    fixture, value, _ = qualification_fixture()
    for edge in ("supervisor_target", "gateway_business_helper", "stop_finalizer"):
        events = qualification_events(fixture, edge)
        if edge == "gateway_business_helper":
            events = [row for row in events if row["kind"] in ("SUBMITTED", "QUEUED", "INSTANCE_BOUND")]
        elif edge == "stop_finalizer":
            events = [row for row in events if row["kind"] != "CLIENT_EXIT" and
                not (row["kind"] == "EOF" and row["data"]["stream"] == "stderr")]
        qualification_record(value, edge)["events"] = events
    result = qualification_review(fixture, value)
    assert model_edge(result, "supervisor_target")["missing"] == ["FUTURE_ADMISSION_FENCE_NOT_PROVEN"]
    assert "ORIGINAL_STOP_UNPROVEN" in model_edge(result, "gateway_business_helper")["missing"]
    endpoint = model_edge(result, "stop_finalizer")
    assert "ORIGINAL_CLIENT_EXIT_UNPROVEN" in endpoint["missing"] and "ORIGINAL_DOUBLE_EOF_UNPROVEN" in endpoint["missing"]
    assert_qualification_unknown(result)


@pytest.mark.parametrize("fault", ["domain_omitted", "domain_repeated", "request_changed", "job_changed", "instance_changed",
    "client_changed", "clock_reverse", "clock_expired", "clock_bool", "budget_overflow", "calls_overflow", "self_fence"])
def test_current_route_strict_bindings_deadlines_budget_and_no_self_fence(fault):
    fixture, value, _ = qualification_fixture()
    edge = "gateway_business_helper"
    row = qualification_record(value, edge)
    row["events"] = qualification_events(fixture, edge)
    if fault == "domain_omitted": value["records"].pop()
    elif fault == "domain_repeated": value["records"][-1] = copy.deepcopy(value["records"][0])
    elif fault == "request_changed": row["events"][0]["data"]["intent_sha256"] = "f" * 64
    elif fault == "job_changed": row["events"][1]["data"]["job_id"] += 1
    elif fault == "instance_changed": row["events"][2]["data"]["instance"]["start_ticks"] += 1
    elif fault == "client_changed": next(event for event in row["events"] if event["kind"] == "EOF")["data"]["client_sha256"] = "f" * 64
    elif fault == "clock_reverse": row["events"][-1]["monotonic_ns"] = row["events"][0]["monotonic_ns"]
    elif fault == "clock_expired": row["events"][-1]["boottime_ns"] = fixture["requests"][edge]["deadline_ns"]
    elif fault == "clock_bool": row["events"][-1]["monotonic_ns"] = True
    elif fault == "budget_overflow": row["usage"]["output_bytes"] = 10001
    elif fault == "calls_overflow": value["root_control_calls"] = 257
    else: row["events"].append(qualification_event(fixture, edge, "FENCE", offset=19))
    with pytest.raises(ValueError):
        qualification_review(fixture, value)


@pytest.mark.parametrize("field", ["contract_sha256", "clocks_sha256", "requests_sha256", "budget_sha256", "schema"])
def test_current_qualification_external_pins_cannot_be_rebound_by_trace(field):
    fixture, value, _ = qualification_fixture()
    value[field] = "f" * 64
    with pytest.raises(ValueError, match="H07_QUALIFICATION_BINDING"):
        qualification_review(fixture, value)


@pytest.mark.parametrize("name", ["stop_ns", "eof_ns", "fsync_ns", "seal_ns"])
def test_independent_existing_reserves_cannot_be_missing_or_zero(name):
    fixture, value, _ = qualification_fixture()
    fixture["budget"]["reserves"][name] = 0
    with pytest.raises(ValueError):
        qualification_review(fixture, value)


def test_same_ledger_budget_is_shared_across_request_edges():
    fixture, value, _ = qualification_fixture()
    fixture["budget"]["reservations"]["d" * 64]["inodes"] = 52
    value["budget_sha256"] = m.sha(m.encoded(fixture["budget"]))
    with pytest.raises(ValueError):
        qualification_review(fixture, value)


def test_current_qualification_model_performs_no_field_operation(monkeypatch):
    import builtins
    import os
    import socket
    import subprocess
    import time
    fixture, value, _ = qualification_fixture()
    raw = m.encoded(value)
    def forbidden(*args, **kwargs):
        raise AssertionError("qualification model attempted a field operation")
    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        for name in ("open", "read_bytes", "read_text", "stat", "lstat", "iterdir"):
            guard.setattr(Path, name, forbidden)
        for name in ("open", "stat", "lstat", "scandir", "listdir", "system"):
            guard.setattr(os, name, forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(time, "clock_gettime_ns", forbidden)
        result = m.review_qualification_model(raw, **fixture)
    assert_qualification_unknown(result)
