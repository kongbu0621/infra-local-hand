"""Internal phase closure contract; no transport operation or host authority.

The producer must own the original launchers and attest OS facts independently.
Current empty trees cannot reconstruct a lost client's EOF or invocation.
Version 1 remains historical and cannot satisfy this runtime contract.
"""
from __future__ import annotations

import hashlib

from . import budget, quota_contract as q

SCHEMA = "local-hand-quota-phase-closed/v2"
STAGES = ("bootstrap", "helper", "reader", "query", "collector", "admission")
ORDINARY = STAGES[:3]
LIMIT = 32768


def digest(value):
    return hashlib.sha256(q._canonical(value, 2 * 1024 * 1024)).hexdigest()


def stage_identity(grant, stage, peer, invocation):
    q.require(stage in STAGES, "PHASE_STAGE")
    data = grant.as_dict()
    execution = data["request"]["execution_id"]
    if stage in ORDINARY:
        suffix = {"bootstrap": ":bootstrap", "helper": "", "reader": ":result_reader"}[stage]
        unit = "lhj-" + hashlib.sha256((execution + suffix).encode()).hexdigest() + ".service"
        parent = peer["parent"]
    elif stage == "query":
        unit, parent = grant.request.query_unit, data["query_parent"]
    else:
        unit = ("lhqoc-" if stage == "collector" else "lhqoa-") + grant.request.digest + ".service"
        parent = data["management_parent"]
    return dict(boot_id=data["request"]["boot_id"], unit=unit, invocation_id=invocation,
                cgroup=parent["path"] + "/" + unit, parent=parent)


def decode(value, grant, receipt, peer, *, now_ns, ordinary_digest=None, originals=None):
    """Validate one whole six-stage fence against original, trusted bindings."""
    q._keys(value, {"schema", "request_digest", "receipt_digest", "boot_id", "execution_id",
                   "ordinary_digest", "management_digest", "proof_digest", "closed_ns", "stages", "parents"})
    data = grant.as_dict()
    q.require(value["schema"] == SCHEMA and value["request_digest"] == grant.request.digest
        and value["receipt_digest"] == hashlib.sha256(receipt.wire).hexdigest()
        and value["boot_id"] == data["request"]["boot_id"]
        and value["execution_id"] == data["request"]["execution_id"]
        and receipt.as_dict()["status"] == "OBSERVED", "PHASE_FENCE")
    for key in ("ordinary_digest", "management_digest", "proof_digest"):
        q.match(value[key], r"[0-9a-f]{64}")
    unsigned = {k: v for k, v in value.items() if k != "proof_digest"}
    q.require(value["proof_digest"] == digest(unsigned), "PHASE_FENCE_DIGEST")
    if ordinary_digest is not None:
        q.require(value["ordinary_digest"] == ordinary_digest, "ORDINARY_PROOF_CHANGED")
    closed = q.integer(value["closed_ns"], receipt.as_dict()["finished_ns"],
                       min(q.integer(now_ns), budget.phase_deadline_ns(data["budget"])))
    q._keys(value["stages"], set(STAGES))
    for stage, proof in value["stages"].items():
        q._keys(proof, {*q.EXIT_FLAGS, "proof_digest", "identity", "observed_ns"})
        q.match(proof["proof_digest"], r"[0-9a-f]{64}")
        q.require(all(proof[key] is True for key in q.EXIT_FLAGS), "PHASE_EXIT_UNPROVEN")
        q.integer(proof["observed_ns"], receipt.as_dict()["started_ns"], closed)
        if stage not in ORDINARY:
            q.require(proof["observed_ns"] < data["request"]["deadline_ns"], "MANAGEMENT_EXIT_LATE")
        identity = proof["identity"]
        q._keys(identity, {"boot_id", "unit", "invocation_id", "cgroup", "parent"})
        q.match(identity["invocation_id"], r"[0-9a-f]{32}")
        q.require(identity == stage_identity(grant, stage, peer, identity["invocation_id"]), "PHASE_STAGE_IDENTITY")
        if stage == "bootstrap":
            q.require(identity == {key: peer[key] for key in identity}, "BOOTSTRAP_PEER_CHANGED")
        if stage == "query":
            q.require(all(identity[k] == v for k, v in receipt.as_dict()["query"].items())
                      and proof["proof_digest"] == receipt.as_dict()["exit"]["proof_digest"], "QUERY_PROOF_CHANGED")
        if originals is not None and stage in originals:
            q.require(identity == originals[stage], "ORIGINAL_STAGE_CHANGED")
    parents = {"ordinary": peer["parent"], "query": data["query_parent"], "management": data["management_parent"]}
    q._keys(value["parents"], set(parents))
    for name, identity in parents.items():
        item = value["parents"][name]
        q._keys(item, {"identity", "populated", "observed_ns", "proof_digest"})
        q.require(item["identity"] == identity and type(item["populated"]) is int
                  and item["populated"] == 0, "PHASE_PARENT_UNPROVEN")
        q.integer(item["observed_ns"], max(v["observed_ns"] for v in value["stages"].values()), closed)
        q.match(item["proof_digest"], r"[0-9a-f]{64}")
    return q._load(q._canonical(value, LIMIT), LIMIT, 10)


def ordinary(proof, grant):
    """Extract same-manager original stage attestations, never infer missing ones."""
    q.require(proof.get("state") == "EXITED" and all(proof.get(k) is True for k in
        ("future_start_blocked", "tree_exited", "collectors_stopped", "writers_stopped")), "ORDINARY_EXIT_UNPROVEN")
    stages = proof.get("quota_stage_exits")
    q._keys(stages, set(ORDINARY))
    for stage in ORDINARY:
        item = stages[stage]
        q._keys(item, {*q.EXIT_FLAGS, "proof_digest", "identity", "observed_ns"})
        q.require(all(item[k] is True for k in q.EXIT_FLAGS), "ORDINARY_EXIT_UNPROVEN")
        q.match(item["proof_digest"], r"[0-9a-f]{64}")
        q.integer(item["observed_ns"], 1, budget.phase_deadline_ns(grant.as_dict()["budget"]))
    return stages
