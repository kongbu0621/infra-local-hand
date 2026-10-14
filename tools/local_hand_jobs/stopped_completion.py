"""Finish stopped core work while preserving unobserved business results."""
from __future__ import annotations

import hashlib
import json

from . import preflight_completion, quota_binding, quota_closure
from .contract import JobError


def complete_stopped_execution(broker, tx, row):
    return (preflight_completion.complete_stopped_preflight(broker, tx, row)
            or complete_stopped_business_start(broker, tx, row)
            or complete_cancelled_inspection(broker, tx, row)
            or complete_cancelled_evidence(broker, tx, row))


def complete_stopped_business_start(broker, tx, row):
    """Consume a durable exit proof without a new launch, observation or seal.

    Cancelling after business bootstrap but before the business helper prevents
    QUOTA_OBSERVED and the ordinary three-stage closure. The append-only delivery
    history, stopped bootstrap and original preflight closure establish that no
    business effects need reconciliation. Directory protection leases remain.
    """
    return _complete_stopped_phase(broker, tx, row, helper_delivered=False)


def complete_cancelled_inspection(broker, tx, row):
    """Finish a stopped host.inspect helper without collecting a new result.

    The fixed inspection has no external write stages. Its owned local files
    remain protected, so a proved stopped writer can release the execution
    lease. Neither its exit code nor cancellation establishes a business result:
    keep UNKNOWN, the original start facts, collector proof and missing result.
    """
    return _complete_stopped_phase(broker, tx, row, helper_delivered=True)


def complete_cancelled_evidence(broker, tx, row):
    """Stop evidence work while retaining the immutable prior business result."""
    return _complete_stopped_phase(broker, tx, row, helper_delivered=None, phase="evidence")


def _reader_exited(broker, proof, execution, row, phase):
    reader = proof.get("result_reader_exit_proof", {})
    unit = "lhj-" + hashlib.sha256((execution + ":result_reader").encode()).hexdigest() + ".service"
    identity = reader.get("identity", {})
    original = row["record"]["handles"][phase].get("manager", {}).get("result_reader") or {}
    parent = getattr(broker.policy, "config", {}).get("process_manager", {}).get("cgroup", "")
    return (reader.get("execution_id") == execution and reader.get("unit") == unit
            and reader.get("state") == "EXITED"
            and all(reader.get(key) is True for key in
                    ("future_start_blocked", "tree_exited", "writers_stopped", "collectors_stopped"))
            and identity.get("boot_id") == row["record"]["quota_preparations"][phase]["budget"]["boot_id"]
            and parent.startswith("/sys/fs/cgroup/")
            and identity.get("cgroup") == parent.removeprefix("/sys/fs/cgroup") + "/" + unit
            and isinstance(identity.get("invocation_id"), str) and len(identity["invocation_id"]) == 32
            and all(ch in "0123456789abcdef" for ch in identity["invocation_id"])
            and all(original.get(key) in (None, value) for key, value in
                    (("unit", unit), ("execution_id", execution), ("boot_id", identity.get("boot_id")),
                     ("invocation_id", identity.get("invocation_id")))))


def _complete_stopped_phase(broker, tx, row, *, helper_delivered, phase="business"):
    record = row["record"]
    previous = ["preflight"] if phase == "business" else ["preflight", "business"]
    expected_phases = previous + [phase]
    if (row["namespace"] != "job" or row["request"]["kind"] != "host.inspect"
            or record["phase"] != phase.upper() or record["lifecycle"] == "TERMINAL"
            or record["cancel_requested"] is not True
            or (helper_delivered is False and record.get("business_started") is True)
            or set(record.get("handles", {})) != set(expected_phases)
            or set(record.get("quota_preparations", {})) != set(expected_phases)
            or set(record.get("quota_closed", {})) != set(previous)
            or phase not in record.get("quota_pending", {})
            or ("job", row["id"]) in broker._active
            or ("job", row["id"]) in broker._recovering):
        return False
    if helper_delivered is not False:
        execution_plan = row["plan"]["execution"]
        if (row["plan"]["kind"] != "host.inspect" or execution_plan.get("kind") != "host.inspect"
                or execution_plan.get("stages") != []
                or any(execution_plan.get(key) for key in ("source", "storage", "build_cache", "prepared"))
                or sorted(execution_plan.get("writable", [])) != sorted(execution_plan["roots"].values())):
            return False
    if quota_binding.admission_version(tx, row) != 1:
        return False
    for earlier in previous:
        quota_binding.original(tx, row, earlier, "QUOTA_PHASE_CLOSED", "quota_closed")
    for current in expected_phases:
        quota_binding.original(tx, row, current, "QUOTA_PREPARATION", "quota_preparations")
    proof = quota_binding.original(tx, row, phase, "QUOTA_EXIT_PENDING", "quota_pending")["proof"]
    execution = "job-" + row["id"] + "-" + phase
    if (record["handles"][phase].get("execution_id") != execution
            or proof.get("execution_id") != execution or proof.get("state") != "EXITED"
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
            expected = set(expected_phases[:len(phases)])
            if (phases != [p.upper() for p in expected_phases[:len(phases)]]
                    or set(data.get("handles", {})) != expected
                    or any(data["handles"][p].get("execution_id") != "job-" + row["id"] + "-" + p
                           for p in expected)):
                return False
        else:
            current = data.get("delivery_intents", [])
            if len(current) != len(deliveries) + 1 or current[:-1] != deliveries:
                raise JobError("IO_UNCERTAIN", "Original stopped execution delivery history changed")
            deliveries = current
    prior = ["job-" + row["id"] + "-" + earlier + ":" + stage
             for earlier in previous for stage in ("bootstrap", "helper", "result_reader")]
    count = len(deliveries) - len(prior)
    allowed = prior + [execution + ":" + stage for stage in ("bootstrap", "helper", "result_reader")[:count]]
    if (phases != [p.upper() for p in expected_phases] or not 0 <= count <= 3 or deliveries != allowed
            or (count == 0 and proof.get("launch_prevented") is not True)
            or (helper_delivered is False and count > 1) or (helper_delivered is True and count < 2)
            or deliveries != record.get("delivery_intents")):
        return False
    if count <= 1:
        if proof.get("result", {}).get("business_started") is not False:
            return False
    else:
        if (proof.get("helper_result_verified") is not False or proof.get("effects_checked") is not False
                or proof.get("result", {}).get("outcome") != "UNKNOWN"
                or proof.get("result", {}).get("helper_started") is not True):
            return False
        quota_binding.original(tx, row, phase, "QUOTA_OBSERVED", "quota_observed")
    if count == 3 and not _reader_exited(broker, proof, execution, row, phase):
        return False
    if phase == "evidence":
        frozen = [json.loads(event[0]) for event in tx.execute(
            "SELECT data_json FROM events WHERE namespace='job' AND id=? AND kind='SEAL_SNAPSHOT_FROZEN'",
            (row["id"],))]
        fields = ("business_outcome", "business_exit_proof", "frozen_snapshot")
        if len(frozen) != 1 or any(frozen[0].get(key) != record.get(key) for key in fields):
            raise JobError("IO_UNCERTAIN", "Original business result changed before evidence cancellation")
        business = quota_binding.original(tx, row, "business", "QUOTA_EXIT_PENDING", "quota_pending")["proof"]
        if business != record["business_exit_proof"] or record.get("seals"):
            return False
    if any(item["namespace"] == "reconcile" and item["parent"] == row["id"]
           and item["record"]["lifecycle"] != "TERMINAL" for item in broker.state.all(tx)):
        return False
    broker.resources.assert_owned(tx, row["id"], row["request"]["expected"]["deployment_epoch"],
                                  row["plan"]["resource_ids"])
    broker.resources.release(tx, row["id"], future_start_blocked=True, tree_exited=True, effects_checked=True)
    # Only the execution owner is released; allocation-owned directory leases
    # retain the inspection's local writes. The exit proof is never rewritten.
    changes = {
        "lifecycle": "TERMINAL", "phase": "EXITED", "outcome": "UNKNOWN" if helper_delivered else "CANCELLED",
        "business_started": record.get("business_started") if helper_delivered else False,
        "exit_proof": proof, "side_effects": "RETAINED_LOCAL_FILES" if helper_delivered else "NONE",
        "execution_resources_released": True, "artifacts_retained": True,
        "gaps": ["Business result was not collected before cancellation; owned files retained"] if helper_delivered else [],
        "stopped_completion": {"execution_id": execution, "proof_digest": quota_closure.digest(proof),
                               **({"business_result_unknown": True, "effect_scope": "OWNED_LOCAL_FILES"}
                                  if helper_delivered else {"business_not_started": True})},
    }
    event = "INSPECTION_CANCELLED" if helper_delivered else "BUSINESS_START_STOPPED"
    if phase == "evidence":
        changes.update(outcome=record["business_outcome"], business_started=record.get("business_started"),
            side_effects=record["side_effects"], evidence="STAGING" if count <= 1 else "DURABILITY_UNKNOWN",
            gaps=["Evidence collection was cancelled; original business result and files retained"],
            stopped_completion=dict(execution_id=execution, proof_digest=quota_closure.digest(proof),
                                    business_result_preserved=True))
        event = "EVIDENCE_CANCELLED"
    broker.state.update(tx, "job", row["id"], event, changes)
    return True
