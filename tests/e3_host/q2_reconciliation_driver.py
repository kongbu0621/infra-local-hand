"""Bind one durable amendment to the original bounded startup assembly.

No command-line release switch, old-v1 mutation, fresh clock, or replay exists.
The caller must pass the live backend from the same newly sealed bootstrap.
"""
from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
import re
import sys


def helper(name):
    spec = importlib.util.spec_from_file_location("_reconciliation_driver_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract = helper("q2_reconciliation_contract")
legacy = helper("q2_startup_retry_driver")
encoded, sha, require = contract.encoded, contract.sha, contract.require
SCHEMA = "local-hand-q2-reconciliation-driver-result/v1"
DOCUMENT_NAMES = ("evidence-adoption.json", "reconciliation-intent.json",
    "live-attestation.json", "reconciliation-record.json")


def binding(verified, envelope, directory):
    manifest = verified.manifest
    return dict(rule=manifest["rule"], baseline=manifest["baseline"], closure=manifest["closure"],
        owner_decision=manifest["owner_decision"], implementation_commit=verified.implementation_commit,
        operation_id=manifest["operation_id"], attempt_id=verified.execution["attempt_id"],
        startup_authority=copy.deepcopy(manifest["startup_authority"]),
        amendment_sha256=verified.digest, inputs_sha256=verified.digest,
        execution_sha256=sha(encoded(verified.execution)), plan_sha256=sha(encoded(verified.plan)),
        source_tree=verified.execution["source"]["tree"],
        candidate={key: verified.plan["candidate"][key] for key in ("commit", "tree", "wheel_sha256")},
        reconciliation_directory=directory, delivery_sha256=sha(encoded(envelope)),
        clock_anchor_sha256=envelope["clock_anchor_sha256"],
        issued_ns=envelope["issued_ns"], preparation_deadline_ns=envelope["preparation_deadline_ns"],
        deadline_ns=envelope["deadline_ns"],
        future_only=True, actual_preserved=True, other_commitments_preserved=True,
        historical_results_unchanged=True, run_permission="existing_startup_once")


def make_documents(backend, live):
    """Construct evidence only after a complete, successful in-memory quote."""
    require(not backend.reconciliation_sealed and live == backend.live_document(),
        "RECONCILIATION_LIVE_DOCUMENT_CHANGED")
    backend._billing.require_admissible(backend.quote, proposed=True)
    common = binding(backend.verified, backend.delivery_envelope, backend.reconciliation_directory)
    obligations = backend.quote["obligations"]
    targets = [copy.deepcopy(row) for row in obligations if row["terminated_by_amendment"]]
    require(len(targets) == 2 and {row["covered_paths"][0] for row in targets}
        == {plan["candidate"]["destination"] for plan in backend.histories},
        "RECONCILIATION_TARGET_SET")
    adoption = copy.deepcopy(backend.verified.adoption)
    intent = dict(schema=contract.SCHEMA, kind="intent", binding=common,
        targets=targets, adoption_sha256=sha(encoded(adoption)))
    live_raw = encoded(live)
    intent_raw = encoded(intent)
    record = dict(schema=contract.SCHEMA, kind="record", binding=copy.deepcopy(common),
        intent_sha256=sha(intent_raw), adoption_sha256=sha(encoded(adoption)),
        live_attestation_sha256=sha(live_raw), targets=targets,
        before=copy.deepcopy(backend.quote["before"]), after=copy.deepcopy(backend.quote["proposed_after"]),
        obligations=copy.deepcopy(obligations), quota_domains=copy.deepcopy(backend.quote["quota_domains"]),
        terminated_unspent=copy.deepcopy(backend.quote["terminated_unspent"]))
    documents = {"evidence-adoption.json": encoded(adoption),
        "reconciliation-intent.json": intent_raw, "live-attestation.json": live_raw,
        "reconciliation-record.json": encoded(record)}
    limits = helper("q2_reconciliation_records").LIMITS
    require(all(len(raw) <= limits[name] for name, raw in documents.items()),
        "RECONCILIATION_DOCUMENT_LIMIT")
    validate_documents(backend.verified, backend.delivery_envelope,
        backend.reconciliation_directory, documents)
    return documents


def validate_documents(verified, envelope, directory, documents):
    """Check the complete retained semantic binding, not self-asserted booleans."""
    require(type(documents) is dict and set(documents) == set(DOCUMENT_NAMES),
        "RECONCILIATION_DOCUMENT_SET")
    limits = helper("q2_reconciliation_records").LIMITS
    parsed = {name: contract.document(raw, limit=limits[name]) for name, raw in documents.items()}
    adoption, intent, live, record = (parsed[name] for name in DOCUMENT_NAMES)
    require(adoption == verified.adoption, "RECONCILIATION_ADOPTION_CHANGED")
    expected = binding(verified, envelope, directory)
    contract.keys(intent, ("schema", "kind", "binding", "targets", "adoption_sha256"))
    contract.keys(record, ("schema", "kind", "binding", "intent_sha256", "adoption_sha256",
        "live_attestation_sha256", "targets", "before", "after", "obligations", "quota_domains", "terminated_unspent"))
    require(intent["schema"] == record["schema"] == contract.SCHEMA
        and intent["kind"] == "intent" and record["kind"] == "record"
        and intent["binding"] == record["binding"] == expected,
        "RECONCILIATION_RECORD_BINDING")
    require(record["intent_sha256"] == sha(documents["reconciliation-intent.json"])
        and record["adoption_sha256"] == intent["adoption_sha256"] == sha(documents["evidence-adoption.json"])
        and record["live_attestation_sha256"] == sha(documents["live-attestation.json"]),
        "RECONCILIATION_RECORD_REFERENCES")
    contract.keys(live, ("schema", "attempt_id", "amendment_sha256", "source_commit", "boot_before",
        "boot_after", "source_classes", "historical_atime_preservation_proven", "predecessors", "ledgers",
        "historical_units", "roots", "q1", "preserved_trees", "parents", "bill", "current_tree_coverage",
        "deadline_ns", "preparation_deadline_ns", "clock_anchor_sha256"))
    require(live["schema"] == "local-hand-q2-installation-reconciliation-live/v1"
        and live["boot_before"] == live["boot_after"] == verified.plan["host"]
        and live["source_classes"] == verified.source_classes,
        "RECONCILIATION_LIVE_IDENTITY")
    require(live["amendment_sha256"] == verified.digest
        and live["attempt_id"] == verified.execution["attempt_id"]
        and live["source_commit"] == verified.implementation_commit
        and live["clock_anchor_sha256"] == envelope["clock_anchor_sha256"]
        and live["preparation_deadline_ns"] == envelope["preparation_deadline_ns"]
        and live["deadline_ns"] == envelope["deadline_ns"]
        and live["historical_atime_preservation_proven"] is False,
        "RECONCILIATION_LIVE_BINDING")
    quote = live["bill"]
    require(quote["sealed"] is False and quote["current"] == quote["before"],
        "RECONCILIATION_PRESEAL_BILL")
    historical = [row for row in quote["obligations"] if row["origin"] == "historical"]
    require(len(historical) == len(verified.obligations) == 7 and all(
        all(proof[key] == original[key] for key in
            ("id", "category", "commitment", "covered_paths", "accounting_categories"))
        for proof, original in zip(historical, verified.obligations)),
        "RECONCILIATION_OBLIGATION_SOURCES")
    targets = [row for row in quote["obligations"] if row["terminated_by_amendment"]]
    require(len(targets) == 2 and intent["targets"] == record["targets"] == targets
        and [row["covered_paths"] for row in targets] ==
            [[verified.original["candidate"]["destination"]], [verified.previous["candidate"]["destination"]]],
        "RECONCILIATION_TARGET_SET")
    for row, ceiling in zip(targets, ((201326592, 8192), (67108864, 4096))):
        require(row["commitment"] == dict(zip(("bytes", "inodes"), ceiling)),
            "RECONCILIATION_TARGET_COMMITMENT")
        require(row["unspent"] == {key: max(0, row["commitment"][key] - row["actual"][key])
            for key in ("bytes", "inodes")}, "RECONCILIATION_TARGET_BALANCE")
    require(record["before"] == quote["before"] and record["after"] == quote["proposed_after"]
        and record["obligations"] == quote["obligations"] and record["quota_domains"] == quote["quota_domains"]
        and record["terminated_unspent"] == quote["terminated_unspent"],
        "RECONCILIATION_BILL_REFERENCES")
    for key in ("bytes", "inodes"):
        delta = sum(row["unspent"][key] for row in targets)
        require(delta == record["terminated_unspent"][key]
            and record["before"]["total"][key] - record["after"]["total"][key] == delta
            and record["before"]["actual"][key] == record["after"]["actual"][key],
            "RECONCILIATION_ONLY_UNUSED_TERMINATED")
    helper("q2_reconciliation_billing").require_admissible(quote, proposed=True)
    return parsed


def execute(backend, envelope, entry, *, execv=os.execv):
    """Continue this newly sealed process; no CLI or alternate-plan entry."""
    stage = "sealed_admission"
    issuance = None
    try:
        require(backend.delivery_envelope == envelope and not backend.read_only_collection,
            "RECONCILIATION_EXECUTION_ENVELOPE")
        require(backend.execution_entered is False, "RECONCILIATION_EXECUTION_ALREADY_ENTERED")
        backend.execution_entered = True
        backend.effect_admission()
        validate_documents(backend.verified, envelope, backend.reconciliation_directory,
            backend.sealed_documents)
        stage = "preflight"
        backend.preflight()
        stage = "reservation"
        backend.reserve()
        stage = "preparation"
        receipt = backend.prepare()
        require(receipt["status"] == "STARTUP_RETRY_RESOURCES_PREPARED", "RECONCILIATION_RESOURCES_NOT_PREPARED")
        sys.path.insert(0, receipt["facts"]["installation"]["source"]["root"] + "/tools")
        d = helper("q2_prepare_driver")
        files = legacy.TrackedFiles(d.Files(backend.guard), backend.event)
        stage = "assembly"
        prepared, invocation = legacy.complete(backend.plan, backend.retry, receipt,
            files=files, command=backend.command, clock=legacy.current_clock, entry=entry,
            delivery_envelope=envelope, verify_preserved=backend.verify_preserved,
            measure_costs=backend.measure_costs)
        issuance = prepared.get("new_request_issuance")
        print(encoded(prepared).decode(), end="", flush=True)
        stage = "owner_exec"
        backend.effect_admission()
        execv(invocation[0], invocation)
        raise RuntimeError("RECONCILIATION_EXEC_RETURNED")
    except Exception as error:
        value = str(error) if isinstance(error, ValueError) else type(error).__name__
        result = dict(schema=SCHEMA, status="BLOCKED_RETAINED", stage=stage,
            reason=value if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else type(error).__name__,
            attempt_id=backend.retry["attempt_id"], amendment_sha256=backend.verified.digest,
            reconciliation_sealed=backend.reconciliation_sealed,
            window_consumed=True, automatic_replay_permitted=False,
            owner_issuance_observed=issuance is not None, owner_request_issued=True if issuance is not None else None,
            historical_results_unchanged=True,
            q2_accepted=False, q3_accepted=False, production_supported=False)
        print(encoded(result).decode(), end="", flush=True)
        return result


if __name__ == "__main__":
    raise SystemExit("BLOCKED: requires the exact newly sealed in-process amendment")
