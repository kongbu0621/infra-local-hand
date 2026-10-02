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
QUALIFICATION_SCHEMA = "local-hand-q2-h07-current-route-contract/v1"
QUALIFICATION_MODEL_SCHEMA = "local-hand-q2-h07-current-route-model/v1"
QUALIFICATION_LIMIT = 256 * 1024
QUALIFICATION_EVENT_LIMIT = 20
USAGE_FIELDS = ("allocated_bytes", "inodes", "output_bytes", "cpu_ns", "calls")


def qualification_contract(*, implementation_commit, source_binding_sha256):
    """Fixed existing route obligations, without adopting supplied source pins."""
    c.commit(implementation_commit); c.digest(source_binding_sha256)
    edges = []

    def add(key, source, target, *, clock="guest", manager=False, clients=("original",)):
        coverage = "RETAINED_LEGACY_COUNTEREXAMPLE" if key in (
            "first_probe", "host_collector", "remote_collector") else (
            "UNPROVEN_QUALIFICATION_OBLIGATION" if key in (
                "pre_dispatch_supervision", "stop_finalizer", "same_channel_evidence") else "CURRENT_SOURCE_OBLIGATION")
        edges.append(dict(id=key, source=source, target=target, clock_domain=clock,
            manager_start=manager, client_roles=list(clients), coverage=coverage))

    for key, source, target, clock, manager in (
        ("host_ssh", "host_consumer", "host_client", "host", False),
        ("ssh_session", "host_client", "guest_session", "guest", False),
        ("session_shell", "guest_session", "guest_shell", "guest", False),
        ("shell_sudo", "guest_shell", "guest_sudo", "guest", False),
        ("first_probe", "guest_sudo", "first_probe", "guest", False),
        ("guest_loader", "guest_sudo", "guest_loader", "guest", False),
        ("loader_outer", "guest_loader", "outer", "guest", True),
        ("outer_owner", "outer", "owner", "guest", False),
        ("owner_supervisor", "owner", "supervisor", "guest", True),
        ("supervisor_target", "supervisor", "target", "guest", True),
        ("target_gateway", "target", "gateway", "guest", False),
        ("host_collector", "host_consumer", "collector_client", "host", False),
        ("remote_collector", "collector_client", "collector", "guest", False),
        ("same_channel_evidence", "guest_loader", "same_ssh_evidence_stream", "guest", False),
        ("stop_finalizer", "supervisor", "stop_finalizer_endpoint", "guest", False),
        ("pre_dispatch_supervision", "pre_dispatch_supervision", "host_client", "host", False),
    ):
        add(key, source, target, clock=clock, manager=manager)
    for phase in ("preflight", "business", "evidence"):
        for stage in ("bootstrap", "helper", "result_reader"):
            add("gateway_" + phase + "_" + stage, "gateway", "ordinary." + phase + "." + stage,
                manager=True, clients=("original", "manager"))
        add("management_" + phase, "target", "management." + phase)
        for role in ("listener", "admission"):
            add(phase + "_" + role, "management." + phase, "quota." + phase + "." + role, manager=True)
        add(phase + "_request", "ordinary." + phase + ".bootstrap", "quota." + phase + ".listener")
        add(phase + "_worker_handoff", "quota." + phase + ".listener", "quota." + phase + ".admission")
        add(phase + "_query", "quota." + phase + ".admission", "quota." + phase + ".query", manager=True)
        roots = ("work", "evidence", "temporary") + (("retained_store",) if phase == "evidence" else ())
        for root in roots:
            add(phase + "_native_" + root, "quota." + phase + ".query", "quota." + phase + ".native." + root)
    domains = sorted({edge[key] for edge in edges for key in ("source", "target")})
    return dict(schema=QUALIFICATION_SCHEMA, implementation_commit=implementation_commit,
        source_binding_sha256=source_binding_sha256, domains=domains, request_edges=edges,
        topology="SOURCE_OBLIGATIONS_AND_LEGACY_COUNTEREXAMPLES_NOT_DEPLOYED",
        proposed_delivery="ONE_SSH_WITH_SAME_CHANNEL_COLLECTION_NO_SECOND_SSH",
        parent_geometry=dict(controller_memory_bytes=512 * 1024**2, controller_tasks=64,
            target_memory_bytes=256 * 1024**2, target_tasks=32,
            ordinary_memory_bytes=256 * 1024**2, ordinary_tasks=32,
            ordinary_relation="CONTROLLER_CHILD_SIBLING_OF_TARGET"),
        existing_limits=dict(ordinary_deliveries=9, system_manager_calls=256, root_control_calls=256),
        requirements=list(MISSING), evidence_use="UNTRUSTED_MODEL_ONLY", qualification="UNKNOWN",
        **dict.fromkeys(FALSE_FIELDS, False))


def _qualification_clocks(clocks):
    c.keys(clocks, ("host", "guest"))
    for window in clocks.values():
        c.keys(window, ("boot_id", "monotonic_issued_ns", "boottime_issued_ns",
            "monotonic_deadline_ns", "boottime_deadline_ns"))
        c.token(window["boot_id"], r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
        for clock in ("monotonic", "boottime"):
            origin = c.number(window[clock + "_issued_ns"], 1)
            end = c.number(window[clock + "_deadline_ns"], origin + 1)
            require(end - origin <= 300 * h.NS, "H07_QUALIFICATION_WINDOW")


def _qualification_instance(value, *, manager):
    if value is None:
        return
    c.keys(value, ("unit", "cgroup", "invocation_id", "pid", "start_ticks", "cgroup_device", "cgroup_inode"))
    c.path(value["cgroup"])
    for name in ("pid", "start_ticks", "cgroup_device", "cgroup_inode"):
        c.number(value[name], 0 if name == "cgroup_device" else 1)
    if manager:
        c.token(value["unit"], r"[a-zA-Z0-9_.@-]+\.service", maximum=255)
        c.token(value["invocation_id"], r"[0-9a-f]{32}")
        require(value["invocation_id"] != "0" * 32, "H07_QUALIFICATION_INVOCATION")
    else:
        require(value["unit"] is value["invocation_id"] is None, "H07_QUALIFICATION_PROCESS")


def review_qualification_model(trace_raw, *, implementation_commit, source_binding_sha256,
                               clocks, requests, budget):
    """Check a bounded synthetic trace against separately supplied original pins.

    Supplied clock, request, identity and budget pins are not authenticated facts.
    No source adoption, clock-rate/pause proof or future-admission fence operation
    is supported. A complete-looking trace therefore still returns UNKNOWN.
    """
    contract = qualification_contract(implementation_commit=implementation_commit,
        source_binding_sha256=source_binding_sha256)
    _qualification_clocks(clocks)
    edges = {row["id"]: row for row in contract["request_edges"]}
    c.keys(requests, edges)
    c.keys(budget, ("ledger_sha256", "reserves", "reservations"))
    c.digest(budget["ledger_sha256"])
    c.keys(budget["reserves"], ("stop_ns", "eof_ns", "fsync_ns", "seal_ns"))
    reserve = sum(c.number(value, 1) for value in budget["reserves"].values())
    c.number(reserve, 1)
    reservations = budget["reservations"]
    require(type(reservations) is dict and 0 < len(reservations) <= len(edges), "H07_QUALIFICATION_BUDGET")
    for pin, limits in reservations.items():
        c.digest(pin); c.keys(limits, USAGE_FIELDS)
        for value in limits.values():
            c.number(value)
    used_reservations = set()
    for key, pin in requests.items():
        edge = edges[key]; window = clocks[edge["clock_domain"]]
        c.keys(pin, ("request_sha256", "intent_sha256", "command_sha256", "deadline_ns", "job_id",
            "instance", "clients", "reservation_sha256"))
        for name in ("request_sha256", "intent_sha256", "command_sha256", "reservation_sha256"):
            c.digest(pin[name])
        require(pin["reservation_sha256"] in reservations, "H07_QUALIFICATION_RESERVATION")
        used_reservations.add(pin["reservation_sha256"])
        c.number(pin["deadline_ns"], window["boottime_issued_ns"] + 1, window["boottime_deadline_ns"])
        if pin["job_id"] is not None:
            require(edge["manager_start"], "H07_QUALIFICATION_JOB")
            c.number(pin["job_id"], 1, 2**32 - 1)
        _qualification_instance(pin["instance"], manager=edge["manager_start"])
        c.keys(pin["clients"], edge["client_roles"])
        for client in pin["clients"].values():
            c.keys(client, ("pid", "start_ticks"))
            c.number(client["pid"], 1); c.number(client["start_ticks"], 1)
    require(used_reservations == set(reservations), "H07_QUALIFICATION_UNUSED_RESERVATION")
    _raw(trace_raw, QUALIFICATION_LIMIT, "H07_QUALIFICATION_TRACE")
    trace = c.document(trace_raw, limit=QUALIFICATION_LIMIT)
    c.keys(trace, ("schema", "contract_sha256", "clocks_sha256", "requests_sha256", "budget_sha256",
        "system_manager_calls", "root_control_calls", "records"))
    require(trace["schema"] == QUALIFICATION_MODEL_SCHEMA and
        all(trace[name + "_sha256"] == sha(encoded(value)) for name, value in (
            ("contract", contract), ("clocks", clocks), ("requests", requests), ("budget", budget))),
        "H07_QUALIFICATION_BINDING")
    for name in ("system_manager_calls", "root_control_calls"):
        c.number(trace[name], 0, contract["existing_limits"][name])
    records = trace["records"]
    require(type(records) is list and len(records) == len(edges), "H07_QUALIFICATION_RECORDS")
    totals = {pin: dict.fromkeys(USAGE_FIELDS, 0) for pin in reservations}
    states = []
    seen = set()
    for row in records:
        c.keys(row, ("edge", "events", "usage"))
        key = row["edge"]
        require(type(key) is str and key in edges and key not in seen, "H07_QUALIFICATION_EDGE")
        seen.add(key); edge = edges[key]; pin = requests[key]; window = clocks[edge["clock_domain"]]
        c.keys(row["usage"], USAGE_FIELDS)
        for name, value in row["usage"].items():
            c.number(value); totals[pin["reservation_sha256"]][name] += value
            c.number(totals[pin["reservation_sha256"]][name], 0, reservations[pin["reservation_sha256"]][name])
        events = row["events"]
        require(type(events) is list and len(events) <= QUALIFICATION_EVENT_LIMIT, "H07_QUALIFICATION_EVENTS")
        state = dict(edge=key, submitted=False, job_id=None, instance_bound=False, stop_requested=False,
            stop_ack=False, job_absent=False, tree_empty=False, exits=[], eof=[], late_queue=False,
            late_activation=False, state="MODEL_UNSUBMITTED", qualification="UNKNOWN", actual_closed=False)
        last_mono, last_boot = window["monotonic_issued_ns"], window["boottime_issued_ns"]
        for event in events:
            c.keys(event, ("kind", "monotonic_ns", "boottime_ns", "data"))
            mono = c.number(event["monotonic_ns"], last_mono, window["monotonic_deadline_ns"] - 1)
            boot = c.number(event["boottime_ns"], last_boot, pin["deadline_ns"] - 1)
            require(abs((boot - window["boottime_issued_ns"]) - (mono - window["monotonic_issued_ns"])) <= 2 * h.NS,
                "H07_QUALIFICATION_CLOCK_DIVERGED")
            last_mono, last_boot = mono, boot
            kind, data = event["kind"], event["data"]
            require(type(kind) is str and kind in ("SUBMITTED", "QUEUED", "INSTANCE_BOUND", "STOP_REQUESTED",
                "STOP_ACK", "JOB_ABSENT", "TREE_EMPTY", "CLIENT_EXIT", "EOF"), "H07_QUALIFICATION_EVENT_KIND")
            if kind == "SUBMITTED":
                c.keys(data, ("request_sha256", "intent_sha256", "command_sha256"))
                require(not state["submitted"] and all(data[name] == pin[name] for name in data),
                    "H07_QUALIFICATION_REQUEST")
                require(boot + reserve < pin["deadline_ns"] and mono + reserve < window["monotonic_deadline_ns"],
                    "H07_QUALIFICATION_RESERVES")
                state["submitted"] = True
                continue
            require(state["submitted"], "H07_QUALIFICATION_BEFORE_SUBMISSION")
            if kind == "QUEUED":
                c.keys(data, ("job_id",)); job = c.number(data["job_id"], 1, 2**32 - 1)
                require(edge["manager_start"] and pin["job_id"] == job and state["job_id"] in (None, job),
                    "H07_QUALIFICATION_JOB")
                state["late_queue"] |= state["job_absent"] or state["stop_ack"] or state["tree_empty"]
                state["job_id"] = job
            elif kind == "INSTANCE_BOUND":
                c.keys(data, ("instance",))
                _qualification_instance(data["instance"], manager=edge["manager_start"])
                require(pin["instance"] is not None and data["instance"] == pin["instance"],
                    "H07_QUALIFICATION_INSTANCE")
                state["late_activation"] |= state["stop_ack"] or state["tree_empty"]
                state["instance_bound"] = True
            elif kind in ("STOP_REQUESTED", "STOP_ACK"):
                c.keys(data, ("instance_sha256",))
                expected = None if pin["instance"] is None else sha(encoded(pin["instance"]))
                require(data["instance_sha256"] == expected, "H07_QUALIFICATION_STOP_INSTANCE")
                require(not state["stop_requested"] if kind == "STOP_REQUESTED" else
                    state["stop_requested"] and not state["stop_ack"], "H07_QUALIFICATION_STOP_ORDER")
                state["stop_requested" if kind == "STOP_REQUESTED" else "stop_ack"] = True
            elif kind in ("JOB_ABSENT", "TREE_EMPTY"):
                c.keys(data, ())
                state["job_absent" if kind == "JOB_ABSENT" else "tree_empty"] = True
            else:
                c.keys(data, ("client_role", "client_sha256", "returncode" if kind == "CLIENT_EXIT" else "stream"))
                role = data["client_role"]
                require(type(role) is str and role in pin["clients"] and
                    data["client_sha256"] == sha(encoded(pin["clients"][role])), "H07_QUALIFICATION_CLIENT")
                if kind == "CLIENT_EXIT":
                    c.number(data["returncode"], 0, 255)
                    require(role not in state["exits"], "H07_QUALIFICATION_EXIT")
                    state["exits"].append(role)
                else:
                    require(type(data["stream"]) is str and data["stream"] in ("stdout", "stderr"), "H07_QUALIFICATION_EOF")
                    label = role + "." + data["stream"]
                    require(label not in state["eof"], "H07_QUALIFICATION_EOF")
                    state["eof"].append(label)
        state["state"] = "MODEL_ORIGINAL_INSTANCE" if state["instance_bound"] else (
            "MODEL_UNOBSERVED_PENDING" if state["submitted"] else "MODEL_UNSUBMITTED")
        state["missing"] = ["FUTURE_ADMISSION_FENCE_NOT_PROVEN"]
        for condition, reason in ((state["instance_bound"], "ORIGINAL_INSTANCE_UNPROVEN"),
            (state["instance_bound"] and state["stop_ack"] and not state["late_activation"] and not state["late_queue"], "ORIGINAL_STOP_UNPROVEN"),
            (state["job_absent"] or not edge["manager_start"], "JOB_TERMINAL_UNPROVEN"),
            (state["tree_empty"] and not state["late_activation"] and not state["late_queue"], "TREE_EMPTY_UNPROVEN"),
            (set(state["exits"]) == set(edge["client_roles"]), "ORIGINAL_CLIENT_EXIT_UNPROVEN"),
            (set(state["eof"]) == {role + "." + stream for role in edge["client_roles"]
                for stream in ("stdout", "stderr")}, "ORIGINAL_DOUBLE_EOF_UNPROVEN")):
            if not condition:
                state["missing"].append(reason)
        states.append(state)
    result = dict(schema=QUALIFICATION_MODEL_SCHEMA, contract=contract, model_trace_consistent=True,
        trace_sha256=sha(trace_raw), clocks_sha256=trace["clocks_sha256"], requests_sha256=trace["requests_sha256"],
        budget_sha256=trace["budget_sha256"], budget_usage=totals, edges=states, qualification="UNKNOWN",
        missing=list(MISSING),
        evidence_use="UNTRUSTED_MODEL_ONLY", whole_run_rate_pause_proven=False,
        future_activation_fenced=False, **dict.fromkeys(FALSE_FIELDS, False))
    encoded(result, limit=REPORT_LIMIT)
    return result


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
