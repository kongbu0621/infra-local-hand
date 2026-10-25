"""Reconstructible reports: deployment, admission and external evidence differ."""
from __future__ import annotations

import time
from local_hand_jobs.contract import JobError
from .model import digest


def report(operation, *, admission=None, public=None, client=None):
    local = operation["checks"].get("local" if operation["decision"] == "COMMITTED" else "restored")
    disposition = operation["decision"] or ("SUPERSEDED" if operation["handoff_complete"] else "IN_PROGRESS")
    result = {
        "schema": "local-hand-deployment-report/v1", "operation_id": operation["id"],
        "plan_digest": operation["plan"]["digest"], "observed_ns": time.time_ns(),
        "deployment": {"decision": operation["decision"], "disposition": disposition, "phase": operation["phase"],
                       "source": operation["plan"]["source"]["deployment_digest"],
                       "target": operation["plan"]["target"]["deployment_digest"],
                       "local_evidence": local},
        "admission": {"release_recorded": operation["released"],
                      "current": admission if admission is not None else {"state": "UNKNOWN"}},
        "public_reachability": public if public is not None else {"status": "NOT_CHECKED"},
        "client_acceptance": client if client is not None else {"status": "NOT_CHECKED"},
        "recovery": {"direction": operation["direction"], "waiting": operation["waiting"],
                     "successor": operation["successor"], "handoff_complete": operation["handoff_complete"],
                     "rollback_successor": operation["rollback_successor"],
                     "steps": [{"id": record["id"], "state": record["state"],
                                "attempts": len(record["attempts"]), "effective": record["effective"]}
                               for record in operation["steps"]]},
        "errors": operation["errors"],
    }
    selected = operation["plan"]["target" if operation["decision"] == "COMMITTED" else "source"]
    binding = {"deployment_digest": selected["deployment_digest"],
               "binding_kind": "durable_decision" if operation["decision"] else "planned_source",
               "configuration_digest": digest(selected.get("selection", {})),
               "observed_ns": operation["updated_ns"],
               "evidence_ref": {"operation_id": operation["id"], "record_digest": digest(operation)}}
    for layer in ("deployment", "recovery"):
        result[layer]["evidence"] = binding
    result["admission"]["evidence"] = {**binding, "observed_ns": result["observed_ns"],
        "deployment_digest": result["admission"]["current"].get("deployment_digest"),
        "configuration_digest": None, "evidence_ref": {"snapshot_digest": digest(result["admission"]["current"])}}
    for layer in ("public_reachability", "client_acceptance"):
        value = result[layer]
        # External evidence is never upgraded or carried over to another
        # selected deployment. A report timestamp is not a probe timestamp.
        if value.get("status") != "NOT_CHECKED" and value.get("deployment_digest") != selected["deployment_digest"]:
            value = {"status": "STALE", "historical": value}
        result[layer] = {**value, "evidence": {"deployment_digest": value.get("deployment_digest"),
            "configuration_digest": value.get("configuration_digest"), "observed_ns": value.get("observed_ns"),
            "evidence_ref": None if value.get("status") == "NOT_CHECKED" else {"observation_digest": digest(value)}}}
    result["diagnostics"] = {"status": "RECORDED_ERRORS" if operation["errors"]["diagnostics"] else "NO_RECORDED_ERRORS",
                             "errors": operation["errors"]["diagnostics"], "evidence": binding}
    return result


def admission_view(gate):
    try:
        value = gate.snapshot()
        return {key: value[key] for key in ("state", "sequence", "owner", "decision_id", "deployment_digest")}
    except (OSError, RuntimeError, ValueError, JobError) as exc:
        return {"state": "UNKNOWN", "error": getattr(exc, "code", type(exc).__name__)}
