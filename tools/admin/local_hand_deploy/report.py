"""Reconstructible reports: deployment, admission and external evidence differ."""
from __future__ import annotations

import time


def report(operation, *, admission=None, public=None, client=None):
    local = operation["checks"].get("local" if operation["decision"] == "COMMITTED" else "restored")
    disposition = operation["decision"] or ("SUPERSEDED" if operation["handoff_complete"] else "IN_PROGRESS")
    return {
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


def admission_view(gate):
    try:
        value = gate.snapshot()
        return {key: value[key] for key in ("state", "sequence", "owner", "decision_id", "deployment_digest")}
    except (OSError, RuntimeError, ValueError) as exc:
        return {"state": "UNKNOWN", "error": getattr(exc, "code", type(exc).__name__)}
