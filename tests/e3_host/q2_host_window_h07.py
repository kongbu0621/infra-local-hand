"""Fixed call-domain and queue-model consistency, never H07 admission.

Only supplied bytes are examined. Trusted repository helpers load as normal
tool code; no input path, live clock, host/guest process or private source code
is read or run. A self-consistent model is not an observation or a capability.
The existing dispatch, field-readiness and frozen runtime remain unchanged.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
from pathlib import Path, PurePosixPath


def helper(name):
    spec = importlib.util.spec_from_file_location("_host_window_h07_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = helper("q2_reconciliation_contract")
h = helper("q2_host_window_contract")
entry = helper("q2_reconciliation_entry")
delivery = helper("q2_host_window_delivery")
require, sha, encoded = c.require, c.sha, c.encoded
SCHEMA = "local-hand-q2-host-window-h07-consistency/v1"
MODEL_SCHEMA = "local-hand-q2-host-window-h07-model-trace/v1"
TOOL_NAME = "q2_host_window_h07.py"
INPUT_LIMIT = 16 * 1024**2
CONFIG_LIMIT = c.INPUT_LIMIT
TRACE_LIMIT = 64 * 1024
REPORT_LIMIT = 256 * 1024
EVENT_LIMIT = 128
PARENT_ROLES = ("query", "management", "controller", "supervisor", "ordinary")
EDGE_IDS = ("owner_supervisor", "supervisor_target")
FALSE_FIELDS = ("source_admission_proven", "source_code_git_verified", "h07_proven",
    "actual_closed", "remote_stop_proven", "dispatch_allowed", "field_ready", "allow_run",
    "allow_consume", "all_domains_covered", "original_window_proven", "q2_accepted",
    "q3_accepted", "production_supported")
MISSING = (
    "PRE_FIRST_REMOTE_ARMING_NOT_PROVEN",
    "CURRENT_HOST_GUEST_CLOCK_MAPPING_NOT_PROVEN",
    "WHOLE_WINDOW_CLOCK_RATE_AND_PAUSE_BOUND_NOT_PROVEN",
    "PENDING_REQUEST_FENCE_NOT_PROVEN",
    "ORDINARY_ACTUAL_PARENT_NOT_OBSERVED",
    "ISSUED_REQUEST_DIGEST_DOMAINS_NOT_AVAILABLE",
    "SSH_PROBE_AND_COLLECTOR_DOMAINS_NOT_OBSERVED",
    "ALL_DOMAIN_STOP_AND_EOF_NOT_PROVEN",
    "SUPERVISION_AND_NATIVE_AUDIT_COST_NOT_PROVEN",
)


def _raw(value, limit, reason):
    require(type(value) is bytes and 0 < len(value) <= limit, reason)
    return value


def _inputs(config_raw, manifest_raw, blobs, implementation_commit,
            carrier_raw, host_attestation_raw):
    _raw(config_raw, CONFIG_LIMIT, "H07_CONFIG_BYTES")
    _raw(manifest_raw, c.INPUT_LIMIT, "H07_MANIFEST_BYTES")
    require(type(blobs) is dict and 0 < len(blobs) <= c.REFERENCE_LIMIT, "H07_BLOBS")
    total = 0
    for pin, raw in blobs.items():
        c.digest(pin)
        require(type(raw) is bytes, "H07_BLOB_BYTES")
        total += len(raw)
        require(total <= INPUT_LIMIT and sha(raw) == pin, "H07_BLOB_CONTENT")
    _raw(carrier_raw, h.CARRIER_BYTES, "H07_CARRIER_BYTES")
    _raw(host_attestation_raw, h.ATTESTATION_BYTES, "H07_HOST_ATTESTATION_BYTES")
    config = c.document(config_raw, limit=CONFIG_LIMIT)
    # Existing verification retains all authority/source-class/history checks.
    # Its input is a plain, detached mapping, never a caller-provided accessor.
    inputs = dict(manifest_raw=base64.b64encode(manifest_raw).decode("ascii"),
        manifest_sha256=sha(manifest_raw), implementation_commit=implementation_commit,
        blobs={pin: base64.b64encode(raw).decode("ascii") for pin, raw in blobs.items()})
    verified, location = entry.offline_inputs(config, inputs, carrier_raw, host_attestation_raw)
    files = verified.execution["source"]["files"]
    require(sum(PurePosixPath(name).name == TOOL_NAME for name in files) == 1,
        "H07_EXTRA_SOURCE_CLOSURE_REQUIRED")
    return config, verified, location


def _domains(plan, config):
    rows = []

    def add(role, kind, unit, parent_role, planned_cgroup, source_fields):
        rows.append(dict(role=role, kind=kind, unit=unit, parent_role=parent_role,
            planned_cgroup=planned_cgroup, source_fields=source_fields,
            actual_identity_observed=False))

    for role in PARENT_ROLES:
        unit = plan["parents"][role]["unit"]
        add("parent." + role, "PLANNED_PARENT", unit, None,
            None if role == "ordinary" else "/" + unit, ["plan.parents." + role])
    for role, parent in (("target", "controller"), ("supervisor", "supervisor")):
        unit = plan["settings"]["controllers"][role]["unit"]
        add("controller." + role, "PLANNED_CONTROLLER", unit, "parent." + parent,
            "/" + plan["parents"][parent]["unit"] + "/" + unit,
            ["plan.settings.controllers." + role, "plan.parents." + parent])
    operation = plan["settings"]["identity"]["operation_id"]
    for phase in ("preflight", "business", "evidence"):
        execution_id = "job-" + operation + "-" + phase
        for stage, suffix in (("main", ""), ("bootstrap", ":bootstrap"),
                              ("result_reader", ":result_reader")):
            unit = "lhj-" + hashlib.sha256((execution_id + suffix).encode()).hexdigest() + ".service"
            add("ordinary." + phase + "." + stage, "EXPECTED_NAME_ONLY", unit,
                "parent.ordinary", None, ["plan.settings.identity.operation_id",
                    "q2_prepare_assembly._allocation", "q2_startup_retry.historical_child_units"])
        for stage, parent in (("query", "query"), ("listener", "management"),
                              ("admission", "management")):
            add("quota." + phase + "." + stage, "ISSUED_REQUEST_REQUIRED", None,
                "parent." + parent, None, ["quota_contract.issued_request.digest"])
    add("outer", "CONFIGURATION_DECLARATION", config["guest_outer_unit"], None, None,
        ["config.guest_outer_unit"])
    for role, source in (("host_client", "q2_startup_retry_entry.guest_command"),
                         ("guest_session", "q2_startup_retry_entry.guest_command"),
                         ("guest_shell", "q2_startup_retry_entry.guest_command"),
                         ("guest_sudo", "q2_startup_retry_entry.guest_command"),
                         ("first_probe", "q2_startup_retry_entry.PROBE"),
                         ("guest_loader", "q2_host_window_delivery.framed_loader"),
                         ("collector", "q2_reconciliation_entry.collection_command"),
                         ("owner_process", "plan.settings.owner"),
                         ("stop_finalizer_endpoint", "H07_UNPROVEN_REQUIREMENT"),
                         ("pre_dispatch_supervision", "H07_UNPROVEN_REQUIREMENT")):
        add(role, "UNRESOLVED_CONTROL_DOMAIN", None, None, None, [source])
    by_role = {row["role"]: row for row in rows}
    edges = []
    for edge, source, target in ((EDGE_IDS[0], "owner_process", "controller.supervisor"),
                                  (EDGE_IDS[1], "controller.supervisor", "controller.target")):
        item = by_role[target]
        edges.append(dict(id=edge, source_role=source, target_role=target,
            expected_unit=item["unit"], planned_cgroup=item["planned_cgroup"]))
    return rows, edges


def _unmodeled_edges():
    rows = [dict(id="host_to_" + role, source_role="host_client", target_role=role,
        missing="PRE_DISPATCH_BOUNDARY_AND_REQUEST_IDENTITY")
        for role in ("first_probe", "outer", "collector")]
    rows.extend(dict(id="phase_" + phase + "_" + role,
        source_role="controller.target", target_role="quota." + phase + "." + role,
        missing="COMPLETE_ISSUED_REQUEST_DIGEST_AND_LIVE_DOMAIN_IDENTITY")
        for phase in ("preflight", "business", "evidence")
        for role in ("query", "listener", "admission"))
    return rows


def _state(edge):
    return dict(edge=edge["id"], submitted=False, job_id=None, instance=None,
        cancel_acknowledged=False, job_absent_reported=False, stop_requested=False,
        stop_acknowledged=False, empty_snapshot_reported=False, eof=[],
        queue_after_absence=False, activation_after_cancel=False,
        activation_after_stop_ack=False, pending_resolved=False,
        activation_may_still_occur=True,
        state="MODEL_NO_SUBMISSION_REPORTED", actual_closed=False)


def _model(trace_raw, original_window_raw, binding_sha256, edges):
    _raw(trace_raw, TRACE_LIMIT, "H07_TRACE_BYTES")
    _raw(original_window_raw, 4096, "H07_WINDOW_BYTES")
    window = h.validate_window(c.document(original_window_raw, limit=4096))
    trace = c.document(trace_raw, limit=TRACE_LIMIT)
    c.keys(trace, ("schema", "binding_sha256", "original_window_sha256", "events"))
    require(trace["schema"] == MODEL_SCHEMA and trace["binding_sha256"] == binding_sha256
        and trace["original_window_sha256"] == sha(original_window_raw), "H07_MODEL_BINDING")
    events = trace["events"]
    require(type(events) is list and len(events) <= EVENT_LIMIT, "H07_MODEL_EVENTS")
    expected = {edge["id"]: edge for edge in edges}
    states = {key: _state(expected[key]) for key in EDGE_IDS}
    last_mono, last_boot = window["issued_ns"], window["boottime_issued_ns"]
    fields = {
        "SUBMITTED": (), "QUEUED": ("job_id",),
        "INSTANCE_BOUND": ("unit", "cgroup", "invocation_id", "pid", "cgroup_device", "cgroup_inode"),
        "CANCEL_ACK": ("job_id",), "JOB_ABSENT": (), "STOP_REQUESTED": (),
        "STOP_ACK": (), "EMPTY_SNAPSHOT": (), "EOF": ("stream",),
    }
    for event in events:
        c.keys(event, ("edge", "kind", "monotonic_ns", "boottime_ns", "data"))
        edge_id, kind = event["edge"], event["kind"]
        require(type(edge_id) is str and edge_id in states and type(kind) is str and kind in fields,
            "H07_MODEL_EVENT_KIND")
        mono, boot = event["monotonic_ns"], event["boottime_ns"]
        c.number(mono, last_mono, window["deadline_ns"] - 1)
        c.number(boot, last_boot, window["boottime_deadline_ns"] - 1)
        # Inherited host-guard diagnostic, not a rate/pause qualification.
        require(abs((boot - window["boottime_issued_ns"]) - (mono - window["issued_ns"])) <= 2 * h.NS,
            "H07_MODEL_CLOCK_DIVERGED")
        last_mono, last_boot = mono, boot
        data = event["data"]; c.keys(data, fields[kind])
        state = states[edge_id]
        if kind == "SUBMITTED":
            require(not state["submitted"], "H07_MODEL_RESUBMISSION")
            state["submitted"] = True
        else:
            require(state["submitted"], "H07_MODEL_BEFORE_SUBMISSION")
        if kind in ("QUEUED", "CANCEL_ACK"):
            job = c.number(data["job_id"], 1, 2**32 - 1)
            if kind == "QUEUED":
                require(state["instance"] is None and state["job_id"] in (None, job)
                    and (not state["job_absent_reported"] or state["job_id"] is None),
                    "H07_MODEL_JOB_CHANGED")
                if state["job_absent_reported"]:
                    state["queue_after_absence"] = True
                state["job_id"] = job
            else:
                require(state["job_id"] == job and not state["cancel_acknowledged"],
                    "H07_MODEL_CANCEL_JOB")
                state["cancel_acknowledged"] = True
        elif kind == "INSTANCE_BOUND":
            target = expected[edge_id]
            require(data["unit"] == target["expected_unit"] and data["cgroup"] == target["planned_cgroup"],
                "H07_MODEL_INSTANCE_TARGET")
            c.token(data["invocation_id"], r"[0-9a-f]{32}")
            require(data["invocation_id"] != "0" * 32, "H07_MODEL_INSTANCE_ID")
            for key in ("pid", "cgroup_device", "cgroup_inode"):
                c.number(data[key], 1)
            require(state["instance"] in (None, data), "H07_MODEL_INSTANCE_CHANGED")
            if state["instance"] is None and state["cancel_acknowledged"]:
                state["activation_after_cancel"] = True
            if state["instance"] is None and state["stop_acknowledged"]:
                state["activation_after_stop_ack"] = True
            state["instance"] = copy.deepcopy(data)
        elif kind == "JOB_ABSENT":
            state["job_absent_reported"] = True
        elif kind == "STOP_REQUESTED":
            require(not state["stop_requested"], "H07_MODEL_REPEAT_STOP")
            state["stop_requested"] = True
        elif kind == "STOP_ACK":
            require(state["stop_requested"] and not state["stop_acknowledged"], "H07_MODEL_STOP_ORDER")
            state["stop_acknowledged"] = True
        elif kind == "EMPTY_SNAPSHOT":
            state["empty_snapshot_reported"] = True
        elif kind == "EOF":
            stream = data["stream"]
            require(type(stream) is str and stream in ("stdout", "stderr") and stream not in state["eof"],
                "H07_MODEL_EOF")
            state["eof"].append(stream)
    for state in states.values():
        if state["submitted"]:
            if state["instance"] is None:
                state["state"] = "MODEL_UNOBSERVED_PENDING" if (
                    state["cancel_acknowledged"] or state["job_absent_reported"] or state["stop_requested"]
                ) else "MODEL_JOB_QUEUED" if state["job_id"] is not None else "MODEL_REQUEST_SUBMITTED"
            else:
                state["state"] = ("MODEL_STOP_ACK_REPORTED" if state["stop_acknowledged"] else
                    "MODEL_STOP_REQUESTED" if state["stop_requested"] else "MODEL_INSTANCE_REPORTED")
        state["eof"].sort()
    return dict(schema=MODEL_SCHEMA, model_trace_consistent=True, event_count=len(events),
        trace_sha256=sha(trace_raw), original_window_sha256=sha(original_window_raw),
        original_window=window, edges=[states[key] for key in EDGE_IDS],
        evidence_use="UNTRUSTED_MODEL_ONLY", future_activation_fenced=False,
        original_window_proven=False, actual_closed=False, remote_stop_proven=False)


def review_h07(config_raw, manifest_raw, blobs, *, implementation_commit,
               carrier_raw, host_attestation_raw, retained_anchors=(),
               original_window_raw=None, trace_raw=None):
    """Recompute finite source/plan bindings and optional *model* consistency.

    This API neither accepts a VerifiedSources token nor caller domain lists.
    The caller's expected D and internally consistent source hashes do not
    certify actual Git bytes. Models have no supported fence/CLOSED operation;
    all execution, actual-stop and source-adoption conclusions remain false.
    Existing helpers may dynamically load trusted repository code during this
    call. No supplied path is opened for field observation, and no live clock,
    process or network operation is performed.
    The separately supplied window is a model input: its digest and 300-second
    shape do not establish a consumed intent, actual boot or observed origin.
    """
    require((trace_raw is None) == (original_window_raw is None), "H07_TRACE_WINDOW_PAIR")
    config, verified, location = _inputs(config_raw, manifest_raw, blobs, implementation_commit,
        carrier_raw, host_attestation_raw)
    plan, execution = verified.plan, verified.execution
    domains, edges = _domains(plan, config)
    binding = dict(scope=h.SCOPE, rule=h.RULE, baseline=h.BASELINE, closure=h.CLOSURE,
        startup_authority=copy.deepcopy(h.STARTUP_AUTHORITY),
        reconciliation_authority=copy.deepcopy(h.RECONCILIATION_AUTHORITY),
        manifest_sha256=sha(manifest_raw), configuration_sha256=sha(config_raw),
        implementation_commit=verified.implementation_commit, source_tree=execution["source"]["tree"],
        source_files_sha256=sha(encoded(execution["source"]["files"])),
        plan_sha256=sha(encoded(plan)), attempt_id=execution["attempt_id"],
        location_sha256=sha(encoded(location)), host_boot_id=location["expected_boot_id"],
        guest_boot_id=plan["host"]["boot_id"], initial_userns=copy.deepcopy(plan["host"]["initial_userns"]),
        candidate={key: plan["candidate"][key] for key in ("commit", "tree", "wheel_sha256")})
    binding_sha256 = sha(encoded(binding))
    clock = delivery.remote_deadline_proof(retained_anchors,
        host_boot_id=binding["host_boot_id"], guest_boot_id=binding["guest_boot_id"])
    model = None if trace_raw is None else _model(trace_raw, original_window_raw, binding_sha256, edges)
    result = dict(schema=SCHEMA, status="CONSISTENT_BUT_BLOCKED", evidence_use="OFFLINE_INPUT_CONSISTENCY",
        inputs_consistent=True, binding=binding, binding_sha256=binding_sha256,
        domains=domains, request_edges=edges, model=model, retained_clock_review=clock,
        modeled_edges=list(EDGE_IDS), unmodeled_required_edges=_unmodeled_edges(),
        outer_declaration=dict(config_unit=config["guest_outer_unit"], execution_service=execution["service"],
            names_equal=config["guest_outer_unit"] == execution["service"],
            actual_outer_identity_proven=False, equality_required_by_existing_contract=False),
        missing=list(MISSING), **dict.fromkeys(FALSE_FIELDS, False))
    encoded(result, limit=REPORT_LIMIT)
    return result
