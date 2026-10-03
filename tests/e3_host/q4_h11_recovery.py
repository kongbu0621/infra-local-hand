"""Fixed H11 broker-restart observer for an already consumed real phase.

This test-only entry opens the original ledger and asks the existing Broker to
recover it.  It never submits a request, calls a runner start API, creates a
grant, reads a result file or advances a phase.  A successful case proves only
the original unit trees and future starts are closed; lost anonymous pipes
remain an explicit collector barrier.
"""
from __future__ import annotations

import hashlib
import json
import re
import time

PLAN_SCHEMA = "local-hand-q4-h11-recovery-plan/v1"
RESULT_SCHEMA = "local-hand-q4-h11-recovery-result/v1"
PHASES = ("preflight", "business", "evidence")
RECOVERY_EVENTS = frozenset({
    "RECOVERY_BARRIER", "SUPERVISOR_IDENTITY_OBSERVED",
    "EXECUTION_UNCERTAIN", "QUOTA_EXIT_PENDING",
})


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8")).hexdigest()


def validate(value):
    _require(type(value) is dict and set(value) == {
        "schema", "namespace", "operation_id", "request_digest", "phase",
        "execution_id", "event_seq", "handle_sha256", "budget_deadline_ns",
        "phase_deadline_ns", "controller_deadline_ns", "units",
        "collector_started"}, "H11_PLAN_SCHEMA")
    _require(value["schema"] == PLAN_SCHEMA and value["namespace"] == "job"
             and type(value["operation_id"]) is str
             and re.fullmatch(r"[0-9a-f-]{36}", value["operation_id"])
             and re.fullmatch(r"[0-9a-f]{64}", value["request_digest"] or "")
             and value["phase"] in PHASES
             and value["execution_id"] == "job-" + value["operation_id"] + "-" + value["phase"]
             and type(value["event_seq"]) is int and value["event_seq"] > 0
             and re.fullmatch(r"[0-9a-f]{64}", value["handle_sha256"] or "")
             and type(value["budget_deadline_ns"]) is int and value["budget_deadline_ns"] > 0
             and type(value["phase_deadline_ns"]) is int and 0 < value["phase_deadline_ns"]
             and value["phase_deadline_ns"] <= value["budget_deadline_ns"]
             and type(value["controller_deadline_ns"]) is int
             and value["controller_deadline_ns"] >= value["budget_deadline_ns"]
             and value["collector_started"] is False, "H11_PLAN_IDENTITY")
    units = value["units"]
    _require(type(units) is dict and set(units) == {"bootstrap", "helper", "result_reader"}
             and all(type(unit) is str and re.fullmatch(r"lhj-[0-9a-f]{64}\.service", unit)
                     for unit in units.values())
             and len(set(units.values())) == 3, "H11_PLAN_UNITS")
    return value


def _admit(broker, plan):
    from local_hand_jobs import budget
    validate(plan)
    with broker.state.transaction() as tx:
        rows = broker.state.all(tx)
        _require(len(rows) == 1, "H11_LEDGER_SCOPE")
        row = rows[0]
        _require(row["namespace"] == "job" and row["id"] == row["parent"] == plan["operation_id"]
                 and row["digest"] == plan["request_digest"], "H11_LEDGER_IDENTITY")
        record = row["record"]
        _require(record["event_seq"] == plan["event_seq"]
                 and record["lifecycle"] != "TERMINAL"
                 and record["phase"] == plan["phase"].upper()
                 and record.get("recovered") is not True
                 and record["cancel_requested"] is False
                 and not record.get("quota_pending") and not record.get("quota_closed")
                 and record.get("exit_proof") is None, "H11_LEDGER_STATE")
        handle = record.get("handles", {}).get(plan["phase"])
        _require(type(handle) is dict and handle.get("execution_id") == plan["execution_id"]
                 and handle.get("phase") == plan["phase"]
                 and handle.get("supervision_version") == 3
                 and _digest(handle) == plan["handle_sha256"], "H11_HANDLE_IDENTITY")
        manager = handle.get("manager")
        _require(type(manager) is dict and manager.get("version") == 3, "H11_MANAGER_RECEIPT")
        for stage, unit in plan["units"].items():
            saved = manager.get(stage)
            _require(type(saved) is dict and saved.get("unit") == unit
                     and saved.get("execution_id") == plan["execution_id"], "H11_UNIT_IDENTITY")
        reader = manager["result_reader"]
        _require(reader.get("h11_delivery_barrier") is True
                 and reader.get("collector_started") is False,
                 "H11_COLLECTOR_BARRIER")
        delivered = record.get("delivery_intents", [])
        expected = [plan["execution_id"] + ":" + stage
                    for stage in ("bootstrap", "helper", "result_reader")]
        _require(delivered == expected, "H11_THREE_STAGE_DELIVERY")
        grant = budget.stored_grant(row, plan["phase"])
        _require(grant["deadline_boottime_ns"] == plan["budget_deadline_ns"]
                 and budget.phase_deadline_ns(grant) == plan["phase_deadline_ns"]
                 and plan["controller_deadline_ns"] >= plan["budget_deadline_ns"],
                 "H11_ORIGINAL_DEADLINE")
        leases = [tuple(item) for item in tx.execute(
            "SELECT resource,owner,epoch FROM leases ORDER BY resource").fetchall()]
        _require(bool(leases), "H11_RETAINED_LEASES")
        immutable = dict(request=row["request"], plan=row["plan"], digest=row["digest"],
                         delivered=list(delivered), grant=grant, leases=leases,
                         event_seq=record["event_seq"], handle=handle)
    return immutable


def run(broker, plan, *, current_clock=None, max_ticks=512):
    """Recover once and return a bounded H11 observation-only report."""
    from local_hand_jobs import budget
    plan = validate(plan)
    before = _admit(broker, plan)
    clock = current_clock or budget.current_clock
    now = clock()
    stop_deadline = min(plan["phase_deadline_ns"], plan["budget_deadline_ns"],
                        plan["controller_deadline_ns"])
    _require(now["boottime_ns"] < stop_deadline, "H11_ORIGINAL_DEADLINE")
    broker.recover()
    ticks = 0
    key = ("job", plan["operation_id"])
    while ticks < max_ticks and clock()["boottime_ns"] < stop_deadline:
        broker.tick(); ticks += 1
        if key not in broker._active and key not in broker._recovering:
            break
        time.sleep(0.01)

    _require(clock()["boottime_ns"] < stop_deadline, "H11_ORIGINAL_DEADLINE")
    with broker.state.transaction() as tx:
        row = broker.state.get("job", plan["operation_id"], tx)
        _require(row is not None and row["request"] == before["request"]
                 and row["plan"] == before["plan"] and row["digest"] == before["digest"],
                 "H11_IMMUTABLE_OPERATION")
        record = row["record"]
        _require(record.get("delivery_intents", []) == before["delivered"], "H11_DELIVERY_REPLAY")
        after_grant = budget.stored_grant(row, plan["phase"])
        _require(after_grant == before["grant"]
                 and after_grant["deadline_boottime_ns"] == plan["budget_deadline_ns"],
                 "H11_DEADLINE_CHANGED")
        leases = [tuple(item) for item in tx.execute(
            "SELECT resource,owner,epoch FROM leases ORDER BY resource").fetchall()]
        _require(leases == before["leases"], "H11_RESOURCE_RELEASED")
        events = [dict(item) for item in tx.execute(
            "SELECT seq,kind FROM events WHERE namespace='job' AND id=? AND seq>? ORDER BY seq",
            (plan["operation_id"], before["event_seq"])).fetchall()]
        kinds = [item["kind"] for item in events]
        _require(kinds.count("RECOVERY_BARRIER") == 1
                 and kinds.count("QUOTA_EXIT_PENDING") == 1
                 and set(kinds) <= RECOVERY_EVENTS, "H11_RECOVERY_EVENTS")
        pending = record.get("quota_pending", {}).get(plan["phase"])
        proof = record.get("exit_proof")
        _require(type(pending) is dict and pending.get("proof") == proof,
                 "H11_CURRENT_EXIT_PROOF")
        _require(type(proof) is dict and proof.get("state") == "EXITED"
                 and proof.get("future_start_blocked") is True
                 and proof.get("tree_exited") is True
                 and proof.get("writers_stopped") is True
                 and proof.get("collectors_stopped") is False
                 and proof.get("effects_checked") is False
                 and proof.get("result", {}).get("outcome") == "UNKNOWN",
                 "H11_LOST_COLLECTOR_BARRIER")
        _require(record["lifecycle"] == "RECONCILE_REQUIRED"
                 and record["outcome"] == "UNKNOWN" and record["evidence"] != "SEALED",
                 "H11_RECOVERY_PROMOTION")
    return dict(schema=RESULT_SCHEMA, status="RECOVERY_RECORDED",
                operation_id=plan["operation_id"], execution_id=plan["execution_id"],
                phase=plan["phase"], original_event_seq=before["event_seq"],
                recovery_event_seq=record["event_seq"], event_kinds=kinds, ticks=ticks,
                units=dict(plan["units"]), original_deadline_ns=plan["budget_deadline_ns"],
                phase_deadline_ns=plan["phase_deadline_ns"],
                controller_deadline_ns=plan["controller_deadline_ns"],
                future_start_blocked=True, tree_exited=True, writers_stopped=True,
                collectors_stopped=False, effects_checked=False, outcome="UNKNOWN",
                leases_retained=True, result_reread=False, start_replayed=False,
                q3_accepted=False, production_supported=False)
