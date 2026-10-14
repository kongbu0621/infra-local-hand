"""Finish an observation-only recovery between fully closed core phases."""
from __future__ import annotations

import json

from . import quota_binding, quota_closure
from .contract import JobError


def complete_between_phases(broker, tx, row):
    record = row["record"]
    phases = {"PREFLIGHT_COMPLETE": ("preflight",), "AWAITING_SEAL": ("preflight", "business")}
    previous = phases.get(record["phase"])
    session = broker.task_session
    if (previous is None or record["lifecycle"] == "TERMINAL" or row["request"]["kind"] not in ("host.inspect", "workspace.edit")
            or record.get("recovered") is not True or session is None or session.value["mode"] != "recover"
            or not session._recovery_acknowledged):
        return False
    following = "business" if len(previous) == 1 else "evidence"
    key = (row["namespace"], row["id"])
    def require(condition):
        if not condition:
            raise JobError("IO_UNCERTAIN", "Original phase handover is not proved safe to finish")
    require(row["namespace"] == "job" and key not in broker._active and key not in broker._recovering
            and quota_binding.admission_version(tx, row) == 1
            and set(record.get("handles", {})) == set(previous)
            and set(record.get("quota_closed", {})) == set(previous)
            and set(record.get("quota_pending", {})) == set(previous)
            and set(record.get("quota_preparations", {})) in (set(previous), {*previous, following}))
    proof = None
    for phase in previous:
        quota_binding.original(tx, row, phase, "QUOTA_PREPARATION", "quota_preparations")
        proof = quota_binding.original(tx, row, phase, "QUOTA_EXIT_PENDING", "quota_pending")["proof"]
        fence = quota_binding.original(tx, row, phase, "QUOTA_PHASE_CLOSED", "quota_closed")["fence"]
        execution = "job-" + row["id"] + "-" + phase
        # The closure binds the exact proof digest and execution identity;
        # older accepted proofs do not repeat that identity themselves.
        require(proof.get("execution_id", execution) == fence.get("execution_id") == execution
                == record["handles"][phase].get("execution_id") and proof.get("state") == "EXITED"
                and fence.get("ordinary_digest") == quota_closure.digest(proof)
                and all(proof.get(k) is True for k in
                        ("future_start_blocked", "tree_exited", "collectors_stopped", "writers_stopped", "effects_checked")))
    # Mutable snapshots cannot erase an issued next phase or add a new delivery.
    intended, delivered = [], []
    expected = ["job-" + row["id"] + "-" + phase + ":" + stage
                for phase in previous for stage in ("bootstrap", "helper", "result_reader")]
    for event in tx.execute("SELECT kind,data_json FROM events WHERE namespace='job' AND id=? AND kind IN "
                           "('EXECUTION_INTENT','LAUNCH_ENQUEUED','MANAGER_DELIVERY_INTENT') ORDER BY seq", (row["id"],)):
        data = json.loads(event["data_json"])
        if event["kind"] == "EXECUTION_INTENT":
            intended.append(data.get("phase"))
        if event["kind"] in ("EXECUTION_INTENT", "LAUNCH_ENQUEUED"):
            require(set(data.get("handles", {})) <= set(previous))
        else:
            current = data.get("delivery_intents", [])
            require(current == expected[:len(delivered) + 1] and len(current) == len(delivered) + 1)
            delivered = current
    require(intended == [p.upper() for p in previous] and delivered == expected
            and delivered == record.get("delivery_intents") and record.get("exit_proof") == proof)
    if following == "business":
        require(record.get("business_started") is False)
        outcome, effects = "UNKNOWN", "NONE"
        gap = "Business was not started after API recovery; completed preflight retained"
    else:
        fields = ("business_outcome", "business_exit_proof", "frozen_snapshot")
        frozen = [json.loads(e[0]) for e in tx.execute("SELECT data_json FROM events WHERE namespace='job' AND id=? "
                  "AND kind='SEAL_SNAPSHOT_FROZEN'", (row["id"],))]
        require(len(frozen) == 1 and all(frozen[0].get(k) == record.get(k) for k in fields)
                and record.get("business_exit_proof") == proof and not record.get("seals")
                and record.get("business_outcome") in ("SUCCEEDED", "FAILED", "CANCELLED")
                and record["outcome"] == record["business_outcome"])
        outcome, effects = record["business_outcome"], record["side_effects"]
        gap = "Evidence was not started after API recovery; original business result retained"
    broker._release(tx, row, proof)
    require(tx.execute("SELECT 1 FROM leases WHERE owner=? LIMIT 1", (row["id"],)).fetchone() is None)
    broker.state.update(tx, "job", row["id"], "RECOVERED_BETWEEN_PHASES", {
        "lifecycle": "TERMINAL", "phase": "EXITED", "outcome": outcome, "side_effects": effects,
        "execution_resources_released": True, "artifacts_retained": True, "gaps": [gap],
    })
    return True
