"""Finish stopped preflight work without inventing missing result evidence.

Execution leases exclude concurrent business work. Bootstrap directory leases
retain files and remain owned by their original allocation. A lost result pipe
does not keep an already stopped, read-only preflight executing forever.
"""
from __future__ import annotations

import json

from . import quota_binding, quota_closure
from .contract import JobError


def complete_stopped_preflight(broker, tx, row):
    """Trusted ledger transition, also usable with a retained installation.

    No new supervisor observation, submission, filesystem mutation, deadline,
    result read or evidence seal is created. The original durable exit proof
    must already establish stopped writers and blocked future starts.
    """
    record = row["record"]
    if (row["namespace"] != "job" or row["request"]["kind"] not in ("host.inspect", "workspace.edit")
            or record["phase"] not in ("PREFLIGHT", "EXITED") or record["lifecycle"] == "TERMINAL"
            or not (record["cancel_requested"] or record.get("recovered"))
            or record.get("business_started") is not False
            or set(record.get("handles", {})) != {"preflight"}
            or set(record.get("quota_preparations", {})) != {"preflight"}
            or "preflight" not in record.get("quota_pending", {})
            or ("job", row["id"]) in broker._active
            or ("job", row["id"]) in broker._recovering):
        return False
    if quota_binding.admission_version(tx, row) != 1:
        return False
    pending = quota_binding.original(tx, row, "preflight", "QUOTA_EXIT_PENDING", "quota_pending")
    proof = pending["proof"]
    if record["phase"] == "EXITED":
        if set(record.get("quota_closed", {})) != {"preflight"}:
            return False
        quota_binding.original(tx, row, "preflight", "QUOTA_PHASE_CLOSED", "quota_closed")
        if record.get("exit_proof") != proof:
            raise JobError("IO_UNCERTAIN", "Original completed preflight exit changed before cancellation")
    execution = "job-" + row["id"] + "-preflight"
    if (record["handles"]["preflight"].get("execution_id") != execution
            or proof.get("execution_id") != execution or proof.get("state") != "EXITED"
            or not all(proof.get(key) is True for key in
                       ("future_start_blocked", "tree_exited", "writers_stopped"))
            or not (proof.get("collectors_stopped") is True or record.get("recovered") is True)):
        return False
    # Check actual delivery history, not only a mutable business_started label.
    deliveries = []
    for event in tx.execute("SELECT kind,data_json FROM events WHERE namespace='job' AND id=? "
                            "AND kind IN ('EXECUTION_INTENT','MANAGER_DELIVERY_INTENT') ORDER BY seq",
                            (row["id"],)):
        data = json.loads(event["data_json"])
        if event["kind"] == "EXECUTION_INTENT":
            if data.get("phase") != "PREFLIGHT" or set(data.get("handles", {})) != {"preflight"}:
                return False
        else:
            current = data.get("delivery_intents", [])
            if current[:len(deliveries)] != deliveries:
                raise JobError("IO_UNCERTAIN", "Original preflight delivery history changed")
            deliveries = current
    allowed = [execution + ":" + stage for stage in ("bootstrap", "helper", "result_reader")]
    if ((not deliveries and proof.get("launch_prevented") is not True) or deliveries != allowed[:len(deliveries)]
            or deliveries != record.get("delivery_intents", [])):
        return False
    for item in broker.state.all(tx):
        if item["namespace"] == "reconcile" and item["parent"] == row["id"] and item["record"]["lifecycle"] != "TERMINAL":
            return False
    broker.resources.assert_owned(tx, row["id"], row["request"]["expected"]["deployment_epoch"],
                                  row["plan"]["resource_ids"])
    # Business was never delivered. This proves absence of business effects;
    # it does not rewrite the original collector/effects flags or result code.
    broker.resources.release(tx, row["id"], future_start_blocked=True, tree_exited=True, effects_checked=True)
    broker.state.update(tx, "job", row["id"], "PREFLIGHT_STOPPED", {
        "lifecycle": "TERMINAL", "phase": "EXITED",
        "outcome": "CANCELLED" if record["cancel_requested"] else "UNKNOWN",
        "exit_proof": proof, "side_effects": "NONE",
        "execution_resources_released": True, "artifacts_retained": True,
        "preflight_completion": {"execution_id": execution, "proof_digest": quota_closure.digest(proof),
                                 "business_not_started": True},
        "gaps": ([] if record["cancel_requested"] else
                 ["Preflight stopped before business; original result collection remains incomplete"]),
    })
    return True
