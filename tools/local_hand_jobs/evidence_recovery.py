"""Trusted publication recovery for an existing completed business result.

Kept separate so an administrator can use this callback with the retained
installation without replacing its business implementation or policy.
"""
from __future__ import annotations

import hashlib
import json

from . import budget
from .broker import thaw
from .contract import JobError
from .state import encoded


def release_completed_evidence(broker, tx, row):
    """Release execution capacity after durably completed evidence recovery.

    Retained directory allocations and historical quota phase records stay put.
    The completed recovery already proves the old units absent and all new
    writers stopped; repeating the failed evidence phase provides no new fact.
    """
    record = row["record"]
    proof = record.get("exit_proof") or {}
    if (row["namespace"] != "job" or row["request"]["kind"] not in ("host.inspect", "workspace.edit")
            or record["lifecycle"] != "TERMINAL" or record["phase"] != "EXITED"
            or record["evidence"] != "SEALED" or record.get("execution_resources_released")
            or record["outcome"] not in ("SUCCEEDED", "FAILED", "CANCELLED")
            or record["outcome"] != record.get("business_outcome")
            or proof.get("kind") != "EVIDENCE_RECOVERY"
            or ("job", row["id"]) in broker._active or ("job", row["id"]) in broker._recovering):
        return False
    if tx.execute("SELECT 1 FROM leases WHERE owner=? LIMIT 1", (row["id"],)).fetchone() is None:
        return False  # Earlier installations may already have released capacity.
    events = [json.loads(item["data_json"]) for item in tx.execute(
        "SELECT data_json FROM events WHERE namespace='job' AND id=? AND kind='EVIDENCE_RECOVERY_COMPLETED'",
        (row["id"],))]
    sealed = tx.execute("SELECT data_json FROM events WHERE namespace='job' AND id=? "
                        "AND kind='EVIDENCE_SEALED' ORDER BY seq DESC LIMIT 1", (row["id"],)).fetchone()
    flags = ("future_start_blocked", "tree_exited", "collectors_stopped", "writers_stopped", "effects_checked")
    original = record.get("business_exit_proof") or {}
    if (len(events) != 1 or events[0].get("exit_proof") != proof
            or sealed is None or json.loads(sealed["data_json"]).get("seals") != record.get("seals")
            or proof.get("operation_id") != row["id"] or proof.get("request_digest") != row["digest"]
            or proof.get("prior_units_absent") is not True
            or proof.get("state") != "EXITED" or proof.get("exit_code") != 0
            or not all(proof.get(key) is True and original.get(key) is True for key in flags)
            or proof.get("snapshot_sha256") != hashlib.sha256(encoded(record.get("frozen_snapshot")).encode()).hexdigest()):
        raise JobError("IO_UNCERTAIN", "Completed evidence recovery differs from its durable proof")
    for item in broker.state.all(tx):
        if item["namespace"] == "reconcile" and item["parent"] == row["id"] and item["record"]["lifecycle"] != "TERMINAL":
            return False
    broker.resources.assert_owned(tx, row["id"], row["request"]["expected"]["deployment_epoch"], row["plan"]["resource_ids"])
    broker.resources.release(tx, row["id"], future_start_blocked=True, tree_exited=True, effects_checked=True)
    broker.state.update(tx, "job", row["id"], "EXECUTION_RESOURCES_RELEASED", {
        "execution_resources_released": True, "artifacts_retained": True})
    return True


def complete_recovered_evidence(broker, operation_id, expected_request_digest, seal, proof):
    """Trusted recovery callback after a separately supervised publication.

    This handles a completed business whose evidence bootstrap was the only
    delivered evidence stage before a reboot. The recovery supervisor must
    observe the original units absent, publish the unchanged frozen snapshot,
    and prove its own exit. No transport route exposes this callback. Original
    handles, deadlines, quota records and failed attempts remain unchanged.
    """
    with broker.fence, broker.state.transaction() as tx:
        row = broker.state.get("job", operation_id, tx)
        if row is None:
            raise JobError("NOT_FOUND", "No original operation for evidence recovery")
        if row["digest"] != expected_request_digest:
            raise JobError("CONFLICT", "Evidence recovery request digest differs")
        record = row["record"]
        existing = [item for item in record.get("seals", []) if item.get("seal_id") == seal.get("seal_id")]
        if existing:
            if len(existing) != 1 or existing[0] != dict(thaw(seal), evidence_state="SEALED"):
                raise JobError("CONFLICT", "Evidence recovery publication differs")
            release_completed_evidence(broker, tx, row)
            return broker._view(broker.state.get("job", operation_id, tx))
        original = record.get("business_exit_proof", {})
        frozen = record.get("frozen_snapshot", {})
        handle = record.get("handles", {}).get("evidence", {})
        manager = handle.get("manager", {})
        bootstrap = manager.get("bootstrap") or {}
        execution_id = "job-" + operation_id + "-evidence"
        flags = ("future_start_blocked", "tree_exited", "collectors_stopped",
                 "writers_stopped", "effects_checked")
        if (record["phase"] not in ("EVIDENCE", "EXITED") or record["evidence"] == "SEALED"
                or record.get("business_outcome") not in ("SUCCEEDED", "FAILED", "CANCELLED")
                or record["outcome"] != record["business_outcome"]
                or original.get("state") != "EXITED"
                or not all(original.get(key) is True for key in flags)
                or frozen.get("operation_id") != operation_id
                or handle.get("execution_id") != execution_id
                or not bootstrap or manager.get("helper") is not None
                or manager.get("result_reader") is not None
                or any(item in record.get("delivery_intents", []) for item in
                       (execution_id + ":helper", execution_id + ":result_reader"))):
            raise JobError("IO_UNCERTAIN", "Original business or evidence delivery is unresolved")
        frozen_event = tx.execute("SELECT data_json FROM events WHERE namespace='job' AND id=? "
                                  "AND kind='SEAL_SNAPSHOT_FROZEN' ORDER BY seq DESC LIMIT 1",
                                  (operation_id,)).fetchone()
        expected = {"frozen_snapshot": frozen, "business_outcome": record["business_outcome"],
                    "business_exit_proof": original}
        if frozen_event is None or frozen_event["data_json"] != encoded(expected):
            raise JobError("IO_UNCERTAIN", "Original frozen result is not durably bound")
        current_boot = budget.current_clock()["boot_id"]
        recovery_id = proof.get("execution_id", "")
        if (proof.get("kind") != "EVIDENCE_RECOVERY" or proof.get("operation_id") != operation_id
                or proof.get("request_digest") != row["digest"]
                or proof.get("snapshot_sha256") != hashlib.sha256(encoded(frozen).encode()).hexdigest()
                or proof.get("prior_boot_id") != bootstrap.get("boot_id")
                or proof.get("boot_id") != current_boot or proof["prior_boot_id"] == current_boot
                or proof.get("prior_units_absent") is not True
                or not isinstance(recovery_id, str) or not recovery_id.startswith("evidence-recovery-")
                or proof.get("unit") != "lhj-" + hashlib.sha256(recovery_id.encode()).hexdigest() + ".service"
                or not isinstance(proof.get("invocation_id"), str) or len(proof["invocation_id"]) != 32
                or proof.get("state") != "EXITED" or proof.get("exit_code") != 0
                or not all(proof.get(key) is True for key in flags)
                or proof.get("stdout_eof") is not True or proof.get("stderr_eof") is not True
                or proof.get("publication_sha256") != hashlib.sha256(encoded(seal).encode()).hexdigest()):
            raise JobError("IO_UNCERTAIN", "Recovered evidence supervisor proof is incomplete")
        if seal.get("operation_id") != operation_id or seal.get("reconcile_id") is not None:
            raise JobError("CONFLICT", "Recovered evidence belongs to another observation")
        broker.state.update(tx, "job", operation_id, "EVIDENCE_RECOVERY_COMPLETED", {
            "phase": "EXITED", "lifecycle": "TERMINAL", "outcome": record["business_outcome"],
            "exit_proof": thaw(proof), "gaps": []})
        broker._register_seal(tx, seal)
        current = broker.state.get("job", operation_id, tx)
        if not release_completed_evidence(broker, tx, current):
            broker._release(tx, current, original)
        result = broker._view(broker.state.get("job", operation_id, tx))
    broker._catalog(broker.state.get("job", operation_id))
    return result
