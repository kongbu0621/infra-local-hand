"""Finish stopped core work while preserving unobserved business results."""
from __future__ import annotations

import json

from . import preflight_completion, quota_binding, quota_closure
from .contract import JobError


def complete_stopped_execution(broker, tx, row):
    return (preflight_completion.complete_stopped_preflight(broker, tx, row)
            or complete_stopped_business_start(broker, tx, row)
            or complete_cancelled_inspection(broker, tx, row))


def complete_stopped_business_start(broker, tx, row):
    """Consume a durable exit proof without a new launch, observation or seal.

    Cancelling after business bootstrap but before the business helper prevents
    QUOTA_OBSERVED and the ordinary three-stage closure. The append-only delivery
    history, stopped bootstrap and original preflight closure establish that no
    business effects need reconciliation. Directory protection leases remain.
    """
    return _complete_stopped_business(broker, tx, row, helper_delivered=False)


def complete_cancelled_inspection(broker, tx, row):
    """Finish a stopped host.inspect helper without collecting a new result.

    The fixed inspection has no external write stages. Its owned local files
    remain protected, so a proved stopped writer can release the execution
    lease. Neither its exit code nor cancellation establishes a business result:
    keep UNKNOWN, the original start facts, collector proof and missing result.
    """
    return _complete_stopped_business(broker, tx, row, helper_delivered=True)


def _complete_stopped_business(broker, tx, row, *, helper_delivered):
    record = row["record"]
    if (row["namespace"] != "job" or row["request"]["kind"] != "host.inspect"
            or record["phase"] != "BUSINESS" or record["lifecycle"] == "TERMINAL"
            or record["cancel_requested"] is not True
            or (not helper_delivered and record.get("business_started") is True)
            or set(record.get("handles", {})) != {"preflight", "business"}
            or set(record.get("quota_preparations", {})) != {"preflight", "business"}
            or set(record.get("quota_closed", {})) != {"preflight"}
            or "business" not in record.get("quota_pending", {})
            or ("job", row["id"]) in broker._active
            or ("job", row["id"]) in broker._recovering):
        return False
    if helper_delivered:
        execution_plan = row["plan"]["execution"]
        if (row["plan"]["kind"] != "host.inspect" or execution_plan.get("kind") != "host.inspect"
                or execution_plan.get("stages") != []
                or any(execution_plan.get(key) for key in ("source", "storage", "build_cache", "prepared"))
                or sorted(execution_plan.get("writable", [])) != sorted(execution_plan["roots"].values())):
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
            or (not helper_delivered and proof.get("result", {}).get("business_started") is not False)
            or not all(proof.get(key) is True for key in
                       ("future_start_blocked", "tree_exited", "writers_stopped", "collectors_stopped"))):
        return False
    if helper_delivered:
        if (proof.get("helper_result_verified") is not False or proof.get("effects_checked") is not False
                or proof.get("result", {}).get("outcome") != "UNKNOWN"
                or proof.get("result", {}).get("helper_started") is not True):
            return False
        quota_binding.original(tx, row, "business", "QUOTA_OBSERVED", "quota_observed")
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
    if helper_delivered:
        allowed.append(execution + ":helper")
    if (phases != ["PREFLIGHT", "BUSINESS"] or deliveries != allowed
            or deliveries != record.get("delivery_intents")):
        return False
    if any(item["namespace"] == "reconcile" and item["parent"] == row["id"]
           and item["record"]["lifecycle"] != "TERMINAL" for item in broker.state.all(tx)):
        return False
    broker.resources.assert_owned(tx, row["id"], row["request"]["expected"]["deployment_epoch"],
                                  row["plan"]["resource_ids"])
    broker.resources.release(tx, row["id"], future_start_blocked=True, tree_exited=True, effects_checked=True)
    # Only the execution owner is released; allocation-owned directory leases
    # retain the inspection's local writes. The exit proof is never rewritten.
    broker.state.update(tx, "job", row["id"], "INSPECTION_CANCELLED" if helper_delivered else "BUSINESS_START_STOPPED", {
        "lifecycle": "TERMINAL", "phase": "EXITED", "outcome": "UNKNOWN" if helper_delivered else "CANCELLED",
        "business_started": record.get("business_started") if helper_delivered else False,
        "exit_proof": proof, "side_effects": "RETAINED_LOCAL_FILES" if helper_delivered else "NONE",
        "execution_resources_released": True, "artifacts_retained": True,
        "gaps": ["Business result was not collected before cancellation; owned files retained"] if helper_delivered else [],
        "stopped_completion": {"execution_id": execution, "proof_digest": quota_closure.digest(proof),
                               **({"business_result_unknown": True, "effect_scope": "OWNED_LOCAL_FILES"}
                                  if helper_delivered else {"business_not_started": True})},
    })
    return True
