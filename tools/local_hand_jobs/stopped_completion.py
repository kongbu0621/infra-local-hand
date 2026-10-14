"""Finish original stopped work whose history proves business never started."""
from __future__ import annotations

import json

from . import preflight_completion, quota_binding, quota_closure
from .contract import JobError


def complete_stopped_execution(broker, tx, row):
    return (preflight_completion.complete_stopped_preflight(broker, tx, row)
            or complete_stopped_business_start(broker, tx, row))


def complete_stopped_business_start(broker, tx, row):
    """Consume a durable exit proof without a new launch, observation or seal.

    Cancelling after business bootstrap but before the business helper prevents
    QUOTA_OBSERVED and the ordinary three-stage closure. The append-only delivery
    history, stopped bootstrap and original preflight closure establish that no
    business effects need reconciliation. Directory protection leases remain.
    """
    record = row["record"]
    if (row["namespace"] != "job" or row["request"]["kind"] != "host.inspect"
            or record["phase"] != "BUSINESS" or record["lifecycle"] == "TERMINAL"
            or record["cancel_requested"] is not True
            or record.get("business_started") is True
            or set(record.get("handles", {})) != {"preflight", "business"}
            or set(record.get("quota_preparations", {})) != {"preflight", "business"}
            or set(record.get("quota_closed", {})) != {"preflight"}
            or "business" not in record.get("quota_pending", {})
            or ("job", row["id"]) in broker._active
            or ("job", row["id"]) in broker._recovering):
        return False
    if quota_binding.admission_version(tx, row) != 1:
        return False
    quota_binding.original(tx, row, "preflight", "QUOTA_PHASE_CLOSED", "quota_closed")
    for phase in ("preflight", "business"):
        quota_binding.original(tx, row, phase, "QUOTA_PREPARATION", "quota_preparations")
    proof = quota_binding.original(tx, row, "business", "QUOTA_EXIT_PENDING", "quota_pending")["proof"]
    execution = "job-" + row["id"] + "-business"
    if (record["handles"]["business"].get("execution_id") != execution
            or proof.get("execution_id") != execution or proof.get("state") != "EXITED"
            or proof.get("result", {}).get("business_started") is not False
            or not all(proof.get(key) is True for key in
                       ("future_start_blocked", "tree_exited", "writers_stopped", "collectors_stopped"))):
        return False
    deliveries, phases = [], []
    for event in tx.execute("SELECT kind,data_json FROM events WHERE namespace='job' AND id=? "
                            "AND kind IN ('EXECUTION_INTENT','MANAGER_DELIVERY_INTENT') ORDER BY seq",
                            (row["id"],)):
        data = json.loads(event["data_json"])
        if event["kind"] == "EXECUTION_INTENT":
            phases.append(data.get("phase"))
            expected = {"preflight"} if phases == ["PREFLIGHT"] else {"preflight", "business"}
            if (phases not in (["PREFLIGHT"], ["PREFLIGHT", "BUSINESS"])
                    or set(data.get("handles", {})) != expected
                    or any(data["handles"][p].get("execution_id") != "job-" + row["id"] + "-" + p
                           for p in expected)):
                return False
        else:
            current = data.get("delivery_intents", [])
            if len(current) != len(deliveries) + 1 or current[:-1] != deliveries:
                raise JobError("IO_UNCERTAIN", "Original stopped execution delivery history changed")
            deliveries = current
    allowed = ["job-" + row["id"] + "-preflight:" + stage
               for stage in ("bootstrap", "helper", "result_reader")] + [execution + ":bootstrap"]
    if (phases != ["PREFLIGHT", "BUSINESS"] or deliveries != allowed
            or deliveries != record.get("delivery_intents")):
        return False
    if any(item["namespace"] == "reconcile" and item["parent"] == row["id"]
           and item["record"]["lifecycle"] != "TERMINAL" for item in broker.state.all(tx)):
        return False
    broker.resources.assert_owned(tx, row["id"], row["request"]["expected"]["deployment_epoch"],
                                  row["plan"]["resource_ids"])
    broker.resources.release(tx, row["id"], future_start_blocked=True, tree_exited=True, effects_checked=True)
    broker.state.update(tx, "job", row["id"], "BUSINESS_START_STOPPED", {
        "lifecycle": "TERMINAL", "phase": "EXITED", "outcome": "CANCELLED",
        "business_started": False, "exit_proof": proof, "side_effects": "NONE",
        "execution_resources_released": True, "artifacts_retained": True, "gaps": [],
        "stopped_completion": {"execution_id": execution, "proof_digest": quota_closure.digest(proof),
                               "business_not_started": True},
    })
    return True
