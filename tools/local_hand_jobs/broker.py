"""Single-authority admission and durable execution coordination.

Transport methods only consult the local ledger and admitted in-memory policy.
Slow work belongs to the independently supervised runner, outside transactions.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Mapping
import hashlib
import json
import threading
import time
import uuid

from .contract import JobError, Principal, validate_submit, validate_tool_args
from . import bootstrap_roots, budget
from .resources import ResourceManager
from .state import encoded


def thaw(value):
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [thaw(item) for item in value]
    return value


def phase_plan(row, phase, grant, *, allocation=None, observation=None, parent=None, evidence_store_root=None):
    """Pure phase declaration used by original delivery and trusted inspection.

    Callers obtain row/grant/allocation through the existing durable authority
    fence. This transform neither reserves capacity nor authorizes execution.
    """
    namespace, identity = row["namespace"], row["id"]
    plan = dict(thaw(row["plan"]), phase=phase, execution_id=f"{namespace}-{identity}-{phase}",
                budget_grant=thaw(grant), budgets=thaw(grant["limits"]))
    if allocation is not None:
        plan["bootstrap_allocation"] = thaw(allocation)
        plan["supervision_version"] = 3
    if observation is not None:
        plan["quota_observation_grant"] = thaw(observation)
    if namespace == "reconcile":
        plan["execution"] = dict(plan.get("execution", {}), budgets=thaw(grant["limits"]))
        original = parent["record"].get("bootstrap_grants", {}).get("preflight")
        if original is not None:
            plan["observed_roots"] = thaw(original["roots"])
    plan["preflight_facts"] = thaw(row["record"].get("facts", {}))
    if phase == "evidence":
        plan["evidence_snapshot"] = thaw(row["record"]["frozen_snapshot"])
        plan["evidence_store_root"] = evidence_store_root
    return plan


REPORT_DURABILITY_GAP = "Verified business result retained; helper exit leaves report durability unresolved"


SCOPES = {
    "lh_capabilities": "lh:inspect", "lh_job_submit": "lh:submit",
    "lh_job_status": "lh:read", "lh_job_cancel": "lh:cancel",
    "lh_job_reconcile": "lh:reconcile", "lh_evidence_manifest": "lh:evidence",
    "lh_evidence_read_chunk": "lh:evidence",
}


class Broker:
    """All adapters share this instance, its state and its startup fence.

    Runner is an internal trusted dependency, not a client-selectable executor.
    start/stop must be bounded local enqueue operations. Their returned proof,
    never a timeout, establishes whether delayed launches can still occur.
    """

    def __init__(self, state, policy, registry, runner, evidence=None, *, resources=None, quota_required=False):
        try:
            budget.initialize_clock()
        except JobError:
            # Cache failure before transactions. Historical observation and
            # controlled cancellation remain available; new grants fail closed.
            pass
        self.state, self.policy, self.registry = state, policy, registry
        self.runner, self.evidence = runner, evidence
        if type(quota_required) is not bool:
            raise ValueError("quota_required must be an installation boolean")
        self.quota_required = quota_required
        self._quota_session = uuid.uuid4().hex
        self.resources = resources or ResourceManager()
        self.fence = threading.RLock()
        self._rates = {}
        self._wake = threading.Event()
        self._shutdown = threading.Event()
        self._thread = None
        self._active = {}
        self._execution_owners = {}
        if hasattr(self.runner, "set_start_guard"):
            self.runner.set_start_guard(self._guard_start)
        self._restore_catalog()

    def _restore_catalog(self):
        with self.state.transaction() as tx:
            rows = self.state.all(tx)
        for row in rows:
            if row["namespace"] == "job":
                self._catalog(row)

    def _catalog(self, row):
        if not hasattr(self.registry, "register_evidence"):
            return
        record, plan = row["record"], row["plan"]
        prepared = record.get("prepared_facts")
        if prepared and record["evidence"] == "SEALED" and record["outcome"] == "SUCCEEDED":
            self.registry.register_prepared(prepared["prepared_ref"], prepared)
            try:
                current_expected = thaw(self.policy.expected(prepared["profile_ref"]))
            except JobError as error:
                if error.code != "UNAUTHORIZED":
                    raise
                # Retiring a profile closes new use/discovery, not access to the
                # authoritative history or recovery of unrelated operations.
                current_expected = None
            if prepared.get("expected") == current_expected:
                self.policy.register_prepared_reference(prepared["prepared_ref"], owner=prepared["owner"],
                                                        profile_ref=prepared["profile_ref"])
        bindings = record.get("runner_result", {}).get("bindings", plan.get("execution", {}).get("bindings", {}))
        seals = record.get("seals", [])
        observation_seq, observed_at = record["event_seq"], record["observed_at"]
        if record["evidence"] == "SEALED":
            # Cancellation/administrative events do not constitute a new PASS
            # observation. Derive its ordering from immutable seal registration,
            # and its freshness from the actual frozen execution observation.
            with self.state.transaction() as tx:
                sealed = tx.execute("SELECT seq,observed_at FROM events WHERE namespace='job' AND id=? "
                                    "AND kind='EVIDENCE_SEALED' ORDER BY seq DESC LIMIT 1", (row["id"],)).fetchone()
                if sealed is None:
                    raise JobError("IO_UNCERTAIN", "Sealed observation has no durable registration event")
                observation_seq, observed_at = sealed["seq"], sealed["observed_at"]
                if seals:
                    observed = tx.execute("SELECT observed_at FROM events WHERE namespace='job' AND id=? AND seq=?",
                                          (row["id"], seals[-1]["event_seq"])).fetchone()
                    if observed is None:
                        raise JobError("IO_UNCERTAIN", "Seal has no original execution observation")
                    observed_at = observed["observed_at"]
        self.registry.register_evidence({
            "evidence_id": f"{row['id']}-{record['event_seq']}", "operation_id": row["id"], "kind": row["request"]["kind"],
            "profile_ref": row["request"]["profile_ref"], "owner": row["principal"],
            "observed_at": int(observed_at), "event_seq": observation_seq, "outcome": record["outcome"],
            "evidence_state": record["evidence"], "prepared_ref": row["request"]["inputs"].get("prepared_ref", "prepared-" + row["id"]),
            "suite": row["request"]["inputs"].get("suite"), "expected": row["request"]["expected"],
            "bindings": bindings, "coverage": record.get("runner_result", {}).get("coverage", "PASS"),
            "seal_digest": seals[-1].get("seal_sha256") if seals else None})

    def _authorize(self, principal, scope, request=None, owner=None, tx=None):
        self.policy.authorize(principal, scope, request=request, owner=owner)
        if tx is None:
            with self.state.transaction() as connection:
                return self._authorize(principal, scope, request, owner, connection)
        if tx.execute("SELECT 1 FROM revocations WHERE principal=?", (principal.principal_id,)).fetchone():
            raise JobError("UNAUTHORIZED", "Principal admission has been revoked")

    def _row(self, tx, namespace, identity, principal, scope):
        row = self.state.get(namespace, identity, tx)
        if row is None:
            raise JobError("NOT_FOUND", "No matching record in the healthy ledger")
        self._authorize(principal, scope, owner=row["principal"], tx=tx)
        if row["principal"] != principal.principal_id:
            raise JobError("UNAUTHORIZED", "Operation ownership does not match")
        return row

    def _view(self, row):
        result = dict(row["record"])
        result.update(operation_id=row["parent"], request_digest=row["digest"])
        if row["namespace"] == "reconcile":
            result["reconcile_id"] = row["id"]
        if result["evidence"] != "SEALED" or result["outcome"] != "SUCCEEDED":
            result["outputs"] = {}
        # Internal execution handles contain deployment paths; never expose them.
        for key in ("handles", "facts", "principal_scopes", "generation", "runner_result"):
            result.pop(key, None)
        for key in ("frozen_snapshot", "prepared_facts", "business_outcome", "business_exit_proof", "delivery_intents",
                    "execution_budget", "budget_grant", "bootstrap_grants", "bootstrap_completed", "helper_completed",
                    "quota_binding_version", "quota_preparations", "quota_bindings", "quota_observed", "quota_event_phase",
                    "quota_pending", "quota_closed"):
            result.pop(key, None)
        result["seal_refs"] = [{"seal_id": item["seal_id"], "seal_sha256": item.get("seal_sha256")}
                               for item in result.pop("seals", [])]
        proof = result.get("exit_proof")
        if isinstance(proof, dict):
            result["exit_proof"] = {key: proof.get(key) for key in (
                "future_start_blocked", "tree_exited", "collectors_stopped", "writers_stopped", "effects_checked", "exit_code")}
        return result

    def call(self, tool_name, arguments, principal):
        scope = SCOPES.get(tool_name)
        if scope is None:
            raise JobError("UNSUPPORTED", "Unknown tool")
        self._authorize(principal, scope)
        args = validate_tool_args(tool_name, arguments)
        self._rate(principal)
        if tool_name == "lh_capabilities":
            return self.capabilities(principal, **args)
        if tool_name == "lh_job_submit":
            return self.submit(args, principal)
        if tool_name == "lh_job_status":
            return self.status(principal=principal, **args)
        if tool_name == "lh_job_cancel":
            return self.cancel(principal=principal, **args)
        if tool_name == "lh_job_reconcile":
            return self.reconcile(principal=principal, **args)
        if self.evidence is None:
            raise JobError("NOT_SEALED", "Evidence service is unavailable")
        if tool_name == "lh_evidence_manifest":
            with self.state.transaction() as tx:
                self._row(tx, "job", args["operation_id"], principal, scope)
            return self.evidence.manifest(args["operation_id"], args.get("cursor"), page_size=args.get("page_size", 100), principal=principal)
        owner = self.evidence.owner_of(args["artifact_id"])
        with self.state.transaction() as tx:
            self._row(tx, "job", owner, principal, scope)
        args = dict(args)
        args["expected_digest"] = args.pop("expected_sha256")
        return self.evidence.read_chunk(principal=principal, **args)

    def capabilities(self, principal, cursor=None, page_size=100):
        self._authorize(principal, "lh:inspect")
        return thaw(self.policy.capabilities(principal, cursor=cursor, page_size=page_size))

    def _capacity(self, tx, principal, reserved):
        limits = self.policy.limits
        rows = self.state.all(tx)
        active = sum(row["record"]["lifecycle"] != "TERMINAL" for row in rows)
        total = sum(row["reserved_bytes"] for row in rows)
        if active >= limits["max_queued"] or total + reserved + limits["ledger_emergency_bytes"] > limits["retained_bytes"]:
            raise JobError("LIMIT_EXCEEDED", "Admitted queue or retained evidence budget is exhausted")

    def _rate(self, principal):
        with self.fence:
            now = time.monotonic()
            recent = self._rates.setdefault(principal.principal_id, deque())
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if len(recent) >= self.policy.limits["requests_per_minute"]:
                raise JobError("LIMIT_EXCEEDED", "Principal request rate is exhausted")
            recent.append(now)

    def submit(self, request, principal):
        self._authorize(principal, "lh:submit")
        request = validate_submit(request)
        identity, digest = request["operation_id"], request["request_digest"]
        with self.fence, self.state.transaction() as tx:
            old = self.state.get("job", identity, tx)
            if old is not None:
                self._authorize(principal, "lh:read", owner=old["principal"], tx=tx)
                if old["principal"] != principal.principal_id:
                    raise JobError("UNAUTHORIZED", "Operation ownership does not match")
                if old["digest"] != digest:
                    raise JobError("CONFLICT", "The operation ID already binds different content")
                return self._view(old)
            self._authorize(principal, "lh:submit", request=request, tx=tx)
            if request["expires_at"] <= time.time():
                raise JobError("STALE_DEPLOYMENT", "First admission deadline has expired")
            if request["expected"] != thaw(self.policy.expected(request["profile_ref"])):
                raise JobError("STALE_DEPLOYMENT", "Expected deployment binding does not match")
            plan = thaw(self.registry.resolve(request, self.policy, principal=principal))
            reserved = plan["reservation_bytes"]
            self._capacity(tx, principal, reserved)
            self.resources.acquire(tx, identity, request["expected"]["deployment_epoch"], plan["resource_ids"])
            row = self.state.insert(tx, "job", identity, identity, principal.principal_id,
                                    digest, request, plan, reserved)
            self.state.update(tx, "job", identity, "ADMISSION_BOUND", {
                "principal_scopes": sorted(principal.scopes),
                "generation": self._generation(tx), "handles": {},
                **({"quota_binding_version": 1} if self.quota_required else {})})
            result = self._view(self.state.get("job", identity, tx))
        self._wake.set()
        self._catalog(self.state.get("job", identity))
        return result

    def status(self, operation_id, principal, reconcile_id=None):
        with self.state.transaction() as tx:
            parent = self._row(tx, "job", operation_id, principal, "lh:read")
            if reconcile_id is not None:
                row = self._row(tx, "reconcile", reconcile_id, principal, "lh:read")
                if row["parent"] != operation_id:
                    raise JobError("CONFLICT", "Reconciliation belongs to a different operation")
                return self._view(row)
            result = self._view(parent)
            rounds = [row for row in self.state.all(tx)
                      if row["namespace"] == "reconcile" and row["parent"] == operation_id]
            result["reconciliations"] = [
                {"reconcile_id": row["id"], "lifecycle": row["record"]["lifecycle"],
                 "outcome": row["record"]["outcome"]} for row in rounds[-10:]]
            return result

    def _generation(self, tx):
        return [self.policy.generation, tx.execute("SELECT value FROM counters WHERE key='generation'").fetchone()[0]]

    def _release(self, tx, row, proof):
        from . import quota_binding
        if quota_binding.admission_version(tx, row) == 1:
            for phase in row["record"].get("quota_preparations", {}):
                if phase not in row["record"].get("quota_closed", {}):
                    return  # No refund from ordinary exit or current empty trees.
                quota_binding.original(tx, row, phase, "QUOTA_PHASE_CLOSED", "quota_closed")
        # Business and observation rounds share the parent's resource owner.
        # A late result cannot delete another admitted round's reservation.
        for item in tx.execute("SELECT id FROM operations WHERE namespace='reconcile' AND parent=?", (row["parent"],)):
            if row["namespace"] == "reconcile" and item["id"] == row["id"]:
                continue
            other = self.state.get("reconcile", item["id"], tx)
            if other["record"]["lifecycle"] != "TERMINAL":
                return
        if row["namespace"] == "reconcile":
            parent = self.state.get("job", row["parent"], tx)
            original = parent["record"].get("exit_proof") or {}
            if (parent["record"]["lifecycle"] in ("ACCEPTED", "RUNNING")
                    or parent["record"]["outcome"] == "UNKNOWN" or not all(original.get(name) is True for name in (
                    "future_start_blocked", "tree_exited", "effects_checked"))):
                return  # Observing original files is not proof of original side effects.
        self.resources.release(tx, row["parent"], future_start_blocked=proof.get("future_start_blocked"),
                               tree_exited=proof.get("tree_exited"), effects_checked=proof.get("effects_checked"))

    def cancel(self, operation_id, expected_request_digest, target, principal):
        namespace = target["kind"]
        identity = operation_id if namespace == "job" else target["reconcile_id"]
        with self.fence, self.state.transaction() as tx:
            parent = self._row(tx, "job", operation_id, principal, "lh:cancel")
            if parent["digest"] != expected_request_digest:
                raise JobError("CONFLICT", "Cancellation request digest does not match")
            row = self._row(tx, namespace, identity, principal, "lh:cancel")
            if row["parent"] != operation_id:
                raise JobError("CONFLICT", "Cancellation target belongs to another operation")
            record = row["record"]
            if not record["cancel_requested"]:
                changes = {"cancel_requested": True}
                if record["phase"] == "QUEUED":
                    changes.update(lifecycle="TERMINAL", outcome="CANCELLED", phase="CANCELLED_BEFORE_START",
                                   side_effects="NONE", exit_proof={"future_start_blocked": True,
                                   "tree_exited": True, "effects_checked": True})
                    self._release(tx, row, changes["exit_proof"])
                self.state.update(tx, namespace, identity, "CANCEL_REQUESTED", changes)
            result = self._view(self.state.get(namespace, identity, tx))
        self._wake.set()
        return result

    def reconcile(self, operation_id, expected_request_digest, reconcile_id, principal):
        with self.fence, self.state.transaction() as tx:
            parent = self._row(tx, "job", operation_id, principal, "lh:reconcile")
            if parent["digest"] != expected_request_digest:
                raise JobError("CONFLICT", "Reconciliation request digest does not match")
            old = self.state.get("reconcile", reconcile_id, tx)
            if old is not None:
                if old["principal"] != principal.principal_id:
                    raise JobError("UNAUTHORIZED", "Reconciliation ownership does not match")
                if old["parent"] != operation_id or old["digest"] != expected_request_digest:
                    raise JobError("CONFLICT", "Reconciliation ID binds another request")
                return self._view(old)
            # A new observation consumes capacity and may launch a helper. Its
            # current profile/input grant must hold before durable admission;
            # retrieving an existing observation retains the original identity.
            self._authorize(principal, "lh:reconcile", request=parent["request"], tx=tx)
            if parent["record"]["lifecycle"] in ("ACCEPTED", "RUNNING"):
                raise JobError("RESOURCE_BUSY", "Business execution has not become quiescent")
            for row in self.state.all(tx):
                if row["namespace"] == "reconcile" and row["parent"] == operation_id and row["record"]["lifecycle"] != "TERMINAL":
                    raise JobError("RESOURCE_BUSY", "An earlier reconciliation retains its barrier")
            plan = dict(parent["plan"])
            plan["phase"] = "reconcile"
            plan["observation_event_seq"] = parent["record"]["event_seq"]
            plan["parent_request_digest"] = parent["digest"]
            budgets = thaw(self.policy.profiles[parent["request"]["profile_ref"]]["budgets"]["reconcile"])
            plan["budgets"] = budgets
            plan["reservation_bytes"] = budgets["reservation_bytes"]
            self._capacity(tx, principal, plan["reservation_bytes"])
            self.resources.acquire(tx, operation_id, parent["request"]["expected"]["deployment_epoch"], plan["resource_ids"])
            self.state.insert(tx, "reconcile", reconcile_id, operation_id, principal.principal_id,
                              expected_request_digest, {"operation_id": operation_id,
                              "reconcile_id": reconcile_id, "expected_request_digest": expected_request_digest},
                              plan, plan["reservation_bytes"])
            self.state.update(tx, "reconcile", reconcile_id, "OBSERVATION_BOUND", {
                "principal_scopes": sorted(principal.scopes), "generation": self._generation(tx), "handles": {},
                **({"quota_binding_version": 1} if self.quota_required else {})})
            result = self._view(self.state.get("reconcile", reconcile_id, tx))
        self._wake.set()
        return result

    def revoke(self, principal_id):
        """Trusted administrative API; no MCP tool grants administrative revocation."""
        with self.fence, self.state.transaction() as tx:
            tx.execute("UPDATE counters SET value=value+1 WHERE key='generation'")
            generation = self._generation(tx)[1]
            tx.execute("INSERT INTO revocations VALUES(?,?) ON CONFLICT(principal) DO UPDATE SET generation=excluded.generation",
                       (principal_id, generation))
            targets = [row for row in self.state.all(tx) if row["principal"] == principal_id
                       and row["record"]["lifecycle"] != "TERMINAL"]
            for row in targets:
                self.state.update(tx, row["namespace"], row["id"], "GRANT_REVOKED", {"cancel_requested": True})
        self._wake.set()
        return {"new_admission_closed": True, "queued_launches": "PENDING_STOP_PROOF",
                "running_execution": "PENDING_STOP_PROOF", "affected": len(targets)}

    def recover(self):
        """Crash recovery records uncertainty; never reissues a persisted intent."""
        reconnect = []
        with self.fence, self.state.transaction() as tx:
            for row in self.state.all(tx):
                record = row["record"]
                if record["lifecycle"] != "TERMINAL" and record["phase"] != "QUEUED":
                    changes = {
                        "lifecycle": "RECONCILE_REQUIRED", "outcome": "UNKNOWN",
                        "recovered": True,
                        "gaps": ["Persisted execution intent requires independent launch and exit proof"]}
                    if (record["phase"] in ("AWAITING_SEAL", "EVIDENCE", "EXITED")
                            and "business_outcome" in record):
                        # The original execution was already observed and
                        # frozen before sealing. Recovery uncertainty belongs
                        # to the evidence helper, not that durable result.
                        changes.update(outcome=record["business_outcome"],
                                       gaps=["Business result retained; evidence publication requires recovery"])
                    if record["phase"] == "EVIDENCE":
                        changes["evidence"] = "DURABILITY_UNKNOWN"
                    if record["phase"] in ("PREFLIGHT", "BUSINESS", "RECONCILE", "EVIDENCE"):
                        # Older ledgers could carry the previous phase's proof
                        # through a new intent. Reobserve this exact execution.
                        changes["exit_proof"] = None
                    self.state.update(tx, row["namespace"], row["id"], "RECOVERY_BARRIER", changes)
                    phase = record["phase"].lower()
                    handle = record.get("handles", {}).get(phase)
                    if handle is not None:
                        plan = dict(row["plan"], phase=phase)
                        try:
                            grant = budget.stored_grant(row, phase)
                        except JobError:
                            # Legacy/uncertain budget records still permit
                            # observation and controlled stopping, never a new
                            # execution or a replacement operation deadline.
                            pass
                        else:
                            plan.update(budget_grant=grant, budgets=grant["limits"])
                        allocation = record.get("bootstrap_grants", {}).get(phase)
                        if allocation is not None:
                            # Original consumption only; recovery never reserves
                            # another slot or invents missing preparation state.
                            plan["bootstrap_allocation"] = thaw(allocation)
                            if "supervision_version" in handle:
                                plan["supervision_version"] = handle["supervision_version"]
                            if phase == "evidence":
                                plan["evidence_snapshot"] = thaw(record.get("frozen_snapshot", {}))
                                retained = allocation.get("retained_paths", [])
                                if len(retained) == 1:
                                    plan["evidence_store_root"] = retained[0]
                        plan["delivery_intents"] = thaw(record.get("delivery_intents", []))
                        if row["namespace"] == "reconcile":
                            parent = self.state.get("job", row["parent"], tx)
                            original = parent["record"].get("bootstrap_grants", {}).get("preflight")
                            if original is not None:
                                plan["observed_roots"] = thaw(original["roots"])
                        reconnect.append(((row["namespace"], row["id"]), handle, plan))
        for key, handle, plan in reconnect:
            if hasattr(self.runner, "reattach"):
                try:
                    attached = self.runner.reattach(handle, plan)
                    self._active[key] = attached if attached is not None else handle
                except Exception:
                    # A missing/uncertain manager never erases the persisted barrier.
                    pass

    def _unknown(self, namespace, identity, gap):
        with self.state.transaction() as tx:
            row = self.state.get(namespace, identity, tx)
            record = row["record"]
            changes = {"lifecycle": "RECONCILE_REQUIRED", "outcome": "UNKNOWN", "gaps": [gap]}
            if record["phase"] in ("AWAITING_SEAL", "EVIDENCE", "EXITED") and "business_outcome" in record:
                changes["outcome"] = record["business_outcome"]
            if record["phase"] == "EVIDENCE":
                changes["evidence"] = "DURABILITY_UNKNOWN"
            if all(record.get(name) == value for name, value in changes.items()):
                return  # Polling the same uncertainty is not a new durable observation.
            self.state.update(tx, namespace, identity, "EXECUTION_UNCERTAIN", changes)

    def _budget_blocked(self, namespace, identity):
        """An exhausted allocation cannot change an already observed business result."""
        with self.fence, self.state.transaction() as tx:
            row = self.state.get(namespace, identity, tx)
            record = row["record"]
            if record["lifecycle"] == "TERMINAL":
                return True
            if (namespace, identity) in self._active:
                return False  # An issued request still needs its own stop/exit proof.
            if record["phase"] == "AWAITING_SEAL":
                proof = record.get("business_exit_proof", {})
                outcome = record.get("business_outcome", "UNKNOWN")
            elif record["phase"] == "QUEUED" and not record.get("handles"):
                proof = {"future_start_blocked": True, "tree_exited": True, "effects_checked": True}
                outcome = "FAILED"
            elif record["phase"] == "PREFLIGHT_COMPLETE":
                proof = record.get("exit_proof") or {}
                outcome = "FAILED" if proof.get("effects_checked") is True else "UNKNOWN"
            else:
                return False
            certain = outcome != "UNKNOWN" and all(proof.get(key) is True for key in
                         ("future_start_blocked", "tree_exited", "effects_checked"))
            self.state.update(tx, namespace, identity, "EXECUTION_BUDGET_EXHAUSTED", {
                "phase": "EXITED", "lifecycle": "TERMINAL" if certain else "RECONCILE_REQUIRED",
                "outcome": outcome, "exit_proof": proof,
                "gaps": ["Operation budget prevents another helper; prior observed business facts retained"]})
            if certain:
                self._release(tx, row, proof)
            return True

    def _execution_slots(self, tx):
        # Losing a start acknowledgement or a recovery attachment does not
        # prove that a supervised process has stopped. Keep those durable
        # intents in the deployment-wide budget even without a live observer.
        owners = set(self._active)
        for row in self.state.all(tx):
            record = row["record"]
            phase = record["phase"].lower()
            proof = record.get("exit_proof") or {}
            if phase in record.get("handles", {}) and not (
                    proof.get("future_start_blocked") is True and proof.get("tree_exited") is True):
                owners.add((row["namespace"], row["id"]))
        return len(owners)

    def _first_recovered_evidence(self, tx, row, *, intent_committed):
        """Authorize only a first seal of already checked, durably frozen work.

        Recovery never clears its generic replay barrier. This narrow case is
        proved from immutable events and the same operation's retained grants,
        both before reserving the new evidence intent and at final delivery.
        """
        record = row["record"]
        expected_phase = "EVIDENCE" if intent_committed else "AWAITING_SEAL"
        if record.get("recovered") is not True or record["phase"] != expected_phase:
            return False
        observed = "business" if row["namespace"] == "job" else "reconcile"
        phases = {"preflight", "business"} if row["namespace"] == "job" else {"reconcile"}
        if intent_committed:
            phases.add("evidence")
        if set(record.get("handles", {})) != phases:
            return False
        try:
            prior = budget.stored_grant(row, observed)
        except JobError:
            return False
        outcome = record.get("business_outcome")
        proof = record.get("business_exit_proof", {})
        frozen = record.get("frozen_snapshot", {})
        quiescence = frozen.get("quiescence", {})
        if (outcome not in ("SUCCEEDED", "FAILED", "CANCELLED") or record["outcome"] != outcome
                or not all(proof.get(key) is True for key in ("future_start_blocked", "tree_exited",
                    "collectors_stopped", "writers_stopped", "effects_checked"))
                or not all(quiescence.get(key) is True for key in ("future_starts_blocked", "tree_exited",
                    "collectors_stopped", "writers_stopped"))
                or frozen.get("operation_id") != row["parent"]
                or frozen.get("reconcile_id") != (row["id"] if row["namespace"] == "reconcile" else None)
                or quiescence.get("execution_id") != prior["execution_id"]
                or type(frozen.get("event_seq")) is not int
                or quiescence.get("event_seq") != frozen["event_seq"]):
            return False
        keys = (row["namespace"], row["id"])
        frozen_event = tx.execute("SELECT seq,data_json FROM events WHERE namespace=? AND id=? "
                                 "AND kind='SEAL_SNAPSHOT_FROZEN' ORDER BY seq DESC LIMIT 1", keys).fetchone()
        recovery = tx.execute("SELECT seq FROM events WHERE namespace=? AND id=? "
                              "AND kind='RECOVERY_BARRIER' ORDER BY seq DESC LIMIT 1", keys).fetchone()
        if (frozen_event is None or recovery is None
                or not 0 < frozen["event_seq"] < frozen_event["seq"] < recovery["seq"]
                or frozen_event["data_json"] != encoded({"frozen_snapshot": frozen,
                    "business_outcome": outcome, "business_exit_proof": proof})):
            return False
        evidence_id = f"{row['namespace']}-{row['id']}-evidence"
        history = tx.execute("SELECT seq,kind,data_json FROM events WHERE namespace=? AND id=? "
                             "AND kind IN ('EXECUTION_INTENT','LAUNCH_ENQUEUED','MANAGER_DELIVERY_INTENT') "
                             "ORDER BY seq LIMIT 16", keys).fetchall()
        if len(history) > 15:
            return False  # Three phases; one intent/enqueue and up to three fixed deliveries each.
        expected_intent = {"execution_id": evidence_id, "intent_only": True}
        version = record.get("handles", {}).get("evidence", {}).get("supervision_version")
        if version is not None:
            if type(version) is not int or version != 3:
                return False
            expected_intent["supervision_version"] = version
        intents = []
        for event in history:
            data = json.loads(event["data_json"])
            if event["kind"] == "EXECUTION_INTENT" and data.get("phase") == "EVIDENCE":
                if (not intent_committed or event["seq"] <= recovery["seq"]
                        or data.get("execution_budget") != record.get("execution_budget")
                        or data.get("handles", {}).get("evidence") != expected_intent):
                    return False
                intents.append(event["seq"])
            elif event["seq"] < recovery["seq"] and (
                    "evidence" in data.get("handles", {}) or any(
                        item == evidence_id or item in (evidence_id + ":bootstrap", evidence_id + ":helper",
                                                       evidence_id + ":result_reader")
                        for item in data.get("delivery_intents", []))):
                return False
        return len(intents) == (1 if intent_committed else 0)

    def bind_observation(self, namespace, identity, phase, raw):
        """Trusted administrator/harness API; no transport route or grant issuance."""
        from . import quota_binding, quota_contract as q, quota_grant as g
        grant = g.decode_grant(raw)
        with self.fence, self.state.transaction() as tx:
            row = self.state.get(namespace, identity, tx)
            if (row is None or row["record"].get("quota_binding_version") != 1
                    or row["record"].get("recovered") or row["record"]["cancel_requested"]
                    or phase in row["record"]["handles"] or row["record"]["generation"] != self._generation(tx)):
                raise JobError("IO_UNCERTAIN", "Quota preparation cannot be bound")
            prep = quota_binding.original(tx, row, phase, "QUOTA_PREPARATION", "quota_preparations")
            q.require(prep["session"] == self._quota_session and grant.as_dict()["allocation"] == prep["allocation"]
                      and grant.as_dict()["budget"] == prep["budget"], "ORIGINAL_PREPARATION")
            g.check_execution(grant, quota_binding.execution(grant), prep["allocation"],
                              now_ns=budget.current_clock()["boottime_ns"])
            existing = row["record"].get("quota_bindings", {}).get(phase)
            history = tx.execute("SELECT data_json FROM events WHERE namespace=? AND id=? AND kind='QUOTA_OBSERVATION_BOUND'",
                                 (namespace, identity)).fetchall()
            already_bound = any(json.loads(event["data_json"]).get("quota_event_phase") == phase for event in history)
            if already_bound and existing is None:
                raise JobError("IO_UNCERTAIN", "Original quota binding snapshot is missing")
            if existing is not None:
                same = quota_binding.selected(tx, row, phase, session=self._quota_session,
                                              now_ns=budget.current_clock()["boottime_ns"])
                q.require(same == grant, "QUOTA_BINDING_CONFLICT")
                return
            item = {"phase": phase, "grant_digest": grant.digest, "grant": grant.as_dict()}
            self.state.update(tx, namespace, identity, "QUOTA_OBSERVATION_BOUND", {
                "quota_event_phase": phase, "quota_bindings": dict(row["record"].get("quota_bindings", {}), **{phase: item})})
        self._wake.set()

    def close_observation(self, namespace, identity, phase, fence):
        """Trusted internal bridge AFTER administrative journal closure.

        No public operation exposes this method. It consumes the immutable
        ordinary proof and all six original stage identities; it never launches
        an observer, substitutes a receipt, refunds quota, or renews a deadline.
        A restart cannot reconstruct the original private transport ownership.
        """
        from . import quota_binding, quota_closure, quota_contract as q
        with self.fence, self.state.transaction() as tx:
            row = self.state.get(namespace, identity, tx)
            if row is None:
                raise JobError("IO_UNCERTAIN", "Original quota phase is missing")
            grant = quota_binding.selected(tx, row, phase, session=self._quota_session, now_ns=None)
            saved = quota_binding.original(tx, row, phase, "QUOTA_OBSERVED", "quota_observed")["observation"]
            pending = quota_binding.original(tx, row, phase, "QUOTA_EXIT_PENDING", "quota_pending")["proof"]
            stages = quota_closure.ordinary(pending, grant)
            execution = grant.request.as_dict()["execution_id"]
            required = {execution + ":" + stage for stage in ("bootstrap", "helper", "result_reader")}
            deliveries = tx.execute("SELECT data_json FROM events WHERE namespace=? AND id=? AND kind='MANAGER_DELIVERY_INTENT'",
                                    (namespace, identity)).fetchall()
            history = [json.loads(item["data_json"]).get("delivery_intents", []) for item in deliveries]
            q.require(required <= set(row["record"].get("delivery_intents", []))
                      and all(any(item in saved for saved in history) for item in required), "ORIGINAL_DELIVERY_MISSING")
            receipt = q.decode_receipt(q._canonical(saved["receipt"], q.RESPONSE_LIMIT), grant.request,
                grant.as_dict()["roots"], now_ns=saved["receipt"]["finished_ns"])
            clock = budget.current_clock()
            q.require(clock["boot_id"] == grant.request.as_dict()["boot_id"], "BOOT_CHANGED")
            value = quota_closure.decode(fence, grant, receipt, stages["bootstrap"]["identity"],
                now_ns=clock["boottime_ns"], ordinary_digest=quota_closure.digest(pending),
                originals={name: item["identity"] for name, item in stages.items()})
            q.require(all(value["stages"][name] == item for name, item in stages.items()), "ORDINARY_PROOF_CHANGED")
            existing = row["record"].get("quota_closed", {}).get(phase)
            if existing is None and quota_binding.recorded(tx, row, phase, "QUOTA_PHASE_CLOSED"):
                raise JobError("IO_UNCERTAIN", "Original phase closure snapshot is missing")
            if existing is not None:
                original = quota_binding.original(tx, row, phase, "QUOTA_PHASE_CLOSED", "quota_closed")
                q.require(original["fence"] == value, "PHASE_FENCE_CONFLICT")
                return
            q.require(row["record"]["phase"].lower() == phase, "PHASE_CHANGED")
            self.state.update(tx, namespace, identity, "QUOTA_PHASE_CLOSED", {
                "quota_event_phase": phase, "quota_closed": dict(row["record"].get("quota_closed", {}),
                    **{phase: {"phase": phase, "fence": value}})})
        # The two journals are deliberately not claimed to commit atomically.
        # A crash here retains closure and pending proof without another launch.
        self._complete(namespace, identity, pending)

    def _start(self, namespace, identity, phase):
        # Slow preflight facts are produced by the runner; no filesystem access here.
        with self.fence:
            with self.state.transaction() as tx:
                row = self.state.get(namespace, identity, tx)
                if row is None or row["record"]["cancel_requested"]:
                    return
                if self._execution_slots(tx) >= self.policy.limits["max_running"]:
                    return
                principal = Principal(row["principal"], frozenset(row["record"]["principal_scopes"]))
                parent = row if namespace == "job" else self.state.get("job", row["parent"], tx)
                if phase == "reconcile":
                    # Admission may precede a late parent result which still
                    # needs its own evidence helper. Keep this round queued.
                    if parent["record"]["lifecycle"] in ("ACCEPTED", "RUNNING"):
                        return
                    previous = parent["record"].get("exit_proof") or {}
                    if previous.get("future_start_blocked") is not True or previous.get("tree_exited") is not True:
                        raise JobError("IO_UNCERTAIN", "Prior execution must have independent exit proof before another helper")
                self._authorize(principal, "lh:submit" if namespace == "job" else "lh:reconcile",
                                request=parent["request"], tx=tx)
                if row["record"]["generation"] != self._generation(tx) or parent["request"]["expected"] != thaw(self.policy.expected(parent["request"]["profile_ref"])):
                    raise JobError("STALE_DEPLOYMENT", "Startup authorization generation changed")
                self.resources.assert_owned(tx, row["parent"], parent["request"]["expected"]["deployment_epoch"], row["plan"]["resource_ids"])
                if phase == "business" and row["record"].get("facts", {}).get("inputs_stable") is not True:
                    raise JobError("IO_UNCERTAIN", "Preflight facts do not permit business execution")
                if phase == "business":
                    current = thaw(self.registry.resolve(parent["request"], self.policy, principal=principal))
                    if current.get("plan_digest") != row["plan"].get("plan_digest"):
                        raise JobError("STALE_DEPLOYMENT", "The immutable execution plan or prerequisite evidence changed")
                if row["record"].get("recovered") and not (
                        phase == "evidence" and self._first_recovered_evidence(tx, row, intent_committed=False)):
                    raise JobError("IO_UNCERTAIN", "Recovered execution does not prove a first evidence intent")
                if row["record"].get("execution_budget") is None:
                    history = tx.execute("SELECT 1 FROM events WHERE namespace=? AND id=? "
                                         "AND kind NOT IN ('ACCEPTED','ADMISSION_BOUND','OBSERVATION_BOUND') LIMIT 1",
                                         (namespace, identity)).fetchone()
                    if history is not None:
                        raise JobError("IO_UNCERTAIN", "Prior operation events cannot acquire a fresh execution budget")
                from . import quota_binding
                quota = quota_binding.admission_version(tx, row) == 1
                if self.quota_required and not quota:
                    raise JobError("IO_UNCERTAIN", "Historical admission cannot acquire a new quota binding")
                if quota:
                    for earlier in row["record"].get("quota_preparations", {}):
                        if earlier != phase:
                            quota_binding.original(tx, row, earlier, "QUOTA_PHASE_CLOSED", "quota_closed")
                preparation = row["record"].get("quota_preparations", {}).get(phase)
                if quota and preparation is not None:
                    from . import quota_binding
                    preparation = quota_binding.original(tx, row, phase, "QUOTA_PREPARATION", "quota_preparations")
                    if preparation["session"] != self._quota_session:
                        raise JobError("IO_UNCERTAIN", "Quota preparation retained across restart; no automatic continuation")
                    execution_budget = row["record"]["execution_budget"]
                    grant = budget.stored_grant(row, phase)
                    if budget.phase_remaining_ns(grant) <= grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS:
                        raise JobError("LIMIT_EXCEEDED", "Original quota preparation deadline expired")
                else:
                    execution_budget, grant = budget.reserve(row, phase)
                execution_id = f"{namespace}-{identity}-{phase}"
                handles = row["record"]["handles"]
                if phase in handles:
                    raise JobError("CONFLICT", "Execution intent cannot be replayed")
                profile = self.policy.profiles[parent["request"]["profile_ref"]]
                allocation = None
                if "bootstrap_slots" in profile:
                    # Reject an unfundable three-unit envelope before consuming
                    # any permanent root slot or committing execution intent.
                    budget.substage_limits(grant, "bootstrap", supervision_version=3)
                    extras = None
                    if phase == "evidence":
                        store = thaw(profile.get("bootstrap_evidence_store"))
                        if (store is None or self.evidence is None
                                or store["path"] != str(self.evidence.root)):
                            raise JobError("UNSUPPORTED", "Evidence writer has no exact bootstrap admission")
                        extras = {"evidence_store": store}
                    allocation = bootstrap_roots.reserve(self.state, tx, row, phase,
                        thaw(profile["bootstrap_slots"]), extra_roots=extras)
                observation = None
                if quota:
                    if allocation is None:
                        raise JobError("UNSUPPORTED", "Quota binding requires preprovisioned bootstrap slots")
                    if preparation is None:
                        prepared = {"phase": phase, "session": self._quota_session, "budget": grant,
                                    "allocation": allocation, "generation": row["record"]["generation"]}
                        self.state.update(tx, namespace, identity, "QUOTA_PREPARATION", {
                            "quota_event_phase": phase, "execution_budget": execution_budget,
                            "quota_preparations": dict(row["record"].get("quota_preparations", {}), **{phase: prepared})})
                        return  # No manager intent or fresh reservation on the next tick.
                    if phase not in row["record"].get("quota_bindings", {}):
                        return
                    from . import quota_binding
                    try:
                        observation = quota_binding.selected(tx, row, phase, session=self._quota_session,
                                                             now_ns=budget.current_clock()["boottime_ns"])
                    except ValueError as error:
                        raise JobError("IO_UNCERTAIN", "Quota observation binding is unresolved") from error
                handles[phase] = {"execution_id": execution_id, "intent_only": True}
                if allocation is not None:
                    # This immutable intent fixes the CPU split and the complete
                    # unit inventory even if the first manager receipt is lost.
                    handles[phase]["supervision_version"] = 3
                self.state.update(tx, namespace, identity, "EXECUTION_INTENT", {
                    "phase": phase.upper(), "lifecycle": "RUNNING", "handles": handles,
                    "execution_budget": execution_budget,
                    "exit_proof": None,
                    "business_started": None if phase == "business" else row["record"]["business_started"],
                    "helper_started": row["record"]["helper_started"] if row["record"]["helper_started"] is True or phase == "business" else None})
                plan = phase_plan(row, phase, grant, allocation=allocation,
                    observation=None if observation is None else observation.as_dict(), parent=parent,
                    evidence_store_root=str(self.evidence.root) if phase == "evidence" else None)
            # The runner enqueues locally; its manager provides the delayed-launch fence.
            self._execution_owners[execution_id] = (namespace, identity)
            handle = self.runner.start(row["parent"], execution_id, plan)
            # A failed acknowledgement COMMIT must still leave the accepted
            # execution reachable by the ledger-failure controlled-stop path.
            self._active[(namespace, identity)] = handle
            with self.state.transaction() as tx:
                saved = self.state.get(namespace, identity, tx)["record"]["handles"]
                saved[phase] = thaw(handle)
                if allocation is not None:
                    saved[phase]["supervision_version"] = 3
                self.state.update(tx, namespace, identity, "LAUNCH_ENQUEUED", {"handles": saved})

    def _guard_start(self, execution_id, launch, *, stage=None, bootstrap_proof=None, helper_proof=None):
        """Serialize final fixed manager delivery with durable cancel/revocation.

        Manager preparation and observation occur outside this fence. The callback
        is only the already fixed, short local Popen request, never a manager wait.
        Returning None proves this particular delivery was not issued.
        """
        if (stage not in (None, "bootstrap", "helper", "result_reader")
                or (stage != "helper" and bootstrap_proof is not None)
                or (stage != "result_reader" and helper_proof is not None)):
            raise JobError("IO_UNCERTAIN", "Unknown manager delivery substage")
        delivery_id = execution_id if stage is None else execution_id + ":" + stage
        with self.fence:
            owner = self._execution_owners.get(execution_id)
            if owner is None:
                return None
            namespace, identity = owner
            with self.state.transaction() as tx:
                row = self.state.get(namespace, identity, tx)
                if row is None:
                    return None
                record = row["record"]
                phase = record["phase"].lower()
                handle = record.get("handles", {}).get(phase, {})
                if handle.get("execution_id") != execution_id or record["cancel_requested"]:
                    return None
                if record.get("recovered") and not (
                        phase == "evidence" and self._first_recovered_evidence(tx, row, intent_committed=True)):
                    return None
                delivered = record.get("delivery_intents", [])
                if (execution_id in delivered or delivery_id in delivered
                        or (stage is None and any(item.startswith(execution_id + ":") for item in delivered))):
                    return None  # A prior delivery intent is never issued a second time.
                if stage == "bootstrap" and any(execution_id + ":" + later in delivered
                                                 for later in ("helper", "result_reader")):
                    return None
                if stage == "helper" and execution_id + ":result_reader" in delivered:
                    return None
                if stage == "helper":
                    if execution_id + ":bootstrap" not in delivered:
                        raise JobError("IO_UNCERTAIN", "Helper lacks its durable preparation intent")
                    proof = thaw(bootstrap_proof)
                    if (type(proof) is not dict or proof.get("execution_id") != execution_id
                            or proof.get("unit") != "lhj-" + hashlib.sha256((execution_id + ":bootstrap").encode()).hexdigest() + ".service"
                            or proof.get("state") != "EXITED" or type(proof.get("exit_code")) is not int
                            or proof["exit_code"] != 0
                            or not all(proof.get(key) is True for key in ("future_start_blocked", "tree_exited",
                                "collectors_stopped", "writers_stopped", "effects_checked"))
                            or type(proof.get("result")) is not dict
                            or proof["result"].get("bootstrap_prepared") is not True):
                        raise JobError("IO_UNCERTAIN", "Preparation completion is not proven")
                grant = budget.stored_grant(row, phase)
                if stage == "result_reader":
                    if (type(handle.get("supervision_version")) is not int
                            or handle["supervision_version"] != 3
                            or execution_id + ":bootstrap" not in delivered
                            or execution_id + ":helper" not in delivered):
                        raise JobError("IO_UNCERTAIN", "Result reader has no original three-stage reservation")
                    intent = tx.execute("SELECT data_json FROM events WHERE namespace=? AND id=? "
                                        "AND kind='EXECUTION_INTENT' ORDER BY seq DESC LIMIT 1",
                                        (namespace, identity)).fetchone()
                    intent_data = json.loads(intent["data_json"]) if intent else {}
                    if (intent_data.get("phase") != record["phase"]
                            or intent_data.get("handles", {}).get(phase) !=
                                {"execution_id": execution_id, "intent_only": True, "supervision_version": 3}):
                        raise JobError("IO_UNCERTAIN", "Result reader reservation differs from immutable execution intent")
                    budget.substage_limits(grant, "result_reader", supervision_version=3)
                    proof = thaw(helper_proof)
                    helper_unit = "lhj-" + hashlib.sha256(execution_id.encode()).hexdigest() + ".service"
                    manager_root = getattr(self.policy, "config", {}).get("process_manager", {}).get("cgroup", "")
                    expected_group = manager_root.removeprefix("/sys/fs/cgroup") + "/" + helper_unit
                    if (type(proof) is not dict or proof.get("execution_id") != execution_id
                            or proof.get("unit") != helper_unit
                            or proof.get("state") != "EXITED"
                            or not all(proof.get(key) is True for key in ("future_start_blocked", "tree_exited",
                                                                       "collectors_stopped", "writers_stopped"))
                            or type(proof.get("identity")) is not dict
                            or not manager_root.startswith("/sys/fs/cgroup/")
                            or proof["identity"].get("cgroup") != expected_group
                            or proof["identity"].get("boot_id") != grant["boot_id"]
                            or type(proof["identity"].get("invocation_id")) is not str
                            or len(proof["identity"]["invocation_id"]) != 32
                            or any(ch not in "0123456789abcdef" for ch in proof["identity"]["invocation_id"])):
                        raise JobError("IO_UNCERTAIN", "Original helper exit is not proven for result reading")
                if stage is not None:
                    allocation = record.get("bootstrap_grants", {}).get(phase)
                    bootstrap_roots.validate_grant(allocation, execution_id=execution_id,
                        phase=phase, operation_id=row["parent"], namespace=namespace, record_id=identity)
                    bootstrap_roots.assert_reserved(tx, allocation)
                remaining = budget.remaining_ns(grant) if stage is None else budget.phase_remaining_ns(grant)
                if remaining <= grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS:
                    raise JobError("LIMIT_EXCEEDED", "Operation has no runtime left after its required stop grace")
                parent = row if namespace == "job" else self.state.get("job", row["parent"], tx)
                if record["generation"] != self._generation(tx) or parent["request"]["expected"] != thaw(self.policy.expected(parent["request"]["profile_ref"])):
                    return None
                principal = Principal(row["principal"], frozenset(record["principal_scopes"]))
                try:
                    self._authorize(principal, "lh:submit" if namespace == "job" else "lh:reconcile",
                                    request=parent["request"], tx=tx)
                except JobError as error:
                    if error.code == "UNAUTHORIZED":
                        return None
                    raise
                self.resources.assert_owned(tx, row["parent"], parent["request"]["expected"]["deployment_epoch"], row["plan"]["resource_ids"])
                if phase == "business":
                    try:
                        current = thaw(self.registry.resolve(parent["request"], self.policy, principal=principal))
                    except JobError as error:
                        if error.code in ("UNAUTHORIZED", "STALE_DEPLOYMENT", "NOT_SEALED", "UNSUPPORTED"):
                            return None
                        raise
                    if current.get("plan_digest") != row["plan"].get("plan_digest"):
                        return None
                from . import quota_binding
                if quota_binding.admission_version(tx, row) == 1:
                    try:
                        observation_grant = quota_binding.selected(tx, row, phase, session=self._quota_session,
                            now_ns=None if stage == "result_reader" else budget.current_clock()["boottime_ns"])
                        if stage == "result_reader":
                            saved = quota_binding.original(tx, row, phase, "QUOTA_OBSERVED", "quota_observed")
                            quota_binding.validate_observation(saved["observation"], observation_grant,
                                now_ns=saved["observation"]["receipt"]["finished_ns"])
                        if stage is None:
                            raise ValueError("QUOTA_REQUIRES_THREE_STAGES")
                        if stage == "helper":
                            observed = quota_binding.validate_observation(proof["result"].get("quota_observation"),
                                observation_grant, now_ns=budget.current_clock()["boottime_ns"])
                            self.state.update(tx, namespace, identity, "QUOTA_OBSERVED", {
                                "quota_event_phase": phase, "quota_observed": dict(record.get("quota_observed", {}),
                                    **{phase: {"phase": phase, "observation": observed}})})
                    except ValueError as error:
                        raise JobError("IO_UNCERTAIN", "Original quota receipt is unresolved") from error
                if stage == "helper":
                    prepared = dict(record.get("bootstrap_completed", {}), **{phase: proof})
                    self.state.update(tx, namespace, identity, "BOOTSTRAP_COMPLETE", {"bootstrap_completed": prepared})
                if stage == "result_reader":
                    observed = dict(record.get("helper_completed", {}), **{phase: proof})
                    self.state.update(tx, namespace, identity, "HELPER_EXIT_OBSERVED", {"helper_completed": observed})
                self.state.update(tx, namespace, identity, "MANAGER_DELIVERY_INTENT", {
                    "delivery_intents": [*delivered, delivery_id]})
            return launch()

    def _complete(self, namespace, identity, proof):
        if not (proof.get("future_start_blocked") is True and proof.get("tree_exited") is True):
            self._unknown(namespace, identity, "Future launch or process-tree exit is unproven")
            return
        with self.state.transaction() as tx:
            row = self.state.get(namespace, identity, tx)
            record = row["record"]
            from . import quota_binding
            if quota_binding.admission_version(tx, row) == 1:
                phase = record["phase"].lower()
                if phase not in record.get("quota_closed", {}):
                    if quota_binding.recorded(tx, row, phase, "QUOTA_PHASE_CLOSED"):
                        raise JobError("IO_UNCERTAIN", "Original phase closure snapshot is missing")
                    existing = record.get("quota_pending", {}).get(phase)
                    if existing is None:
                        if quota_binding.recorded(tx, row, phase, "QUOTA_EXIT_PENDING"):
                            raise JobError("IO_UNCERTAIN", "Original pending exit snapshot is missing")
                        self.state.update(tx, namespace, identity, "QUOTA_EXIT_PENDING", {
                            "quota_event_phase": phase, "quota_pending": dict(record.get("quota_pending", {}),
                                **{phase: {"phase": phase, "proof": thaw(proof)}}),
                            "gaps": ["Original management and ordinary phase closure is pending"]})
                    else:
                        original = quota_binding.original(tx, row, phase, "QUOTA_EXIT_PENDING", "quota_pending")
                        if original["proof"] != thaw(proof):
                            raise JobError("IO_UNCERTAIN", "Original pending exit proof changed")
                    return
                quota_binding.original(tx, row, phase, "QUOTA_PHASE_CLOSED", "quota_closed")
            if record["phase"] == "EVIDENCE":
                result = thaw(proof.get("result", {}))
                publication = result.get("seal_record", result.get("publication"))
                if publication is None:
                    publication = result.get("evidence_publication")
                if (proof.get("exit_code") != 0 or not isinstance(publication, dict)
                        or publication.get("complete") is not True
                        or publication.get("operation_id") != row["parent"]
                        or publication.get("reconcile_id") != (identity if namespace == "reconcile" else None)
                        or proof.get("collectors_stopped") is not True or proof.get("writers_stopped") is not True):
                    self.state.update(tx, namespace, identity, "EVIDENCE_UNCERTAIN", {
                        "phase": "EXITED", "lifecycle": "RECONCILE_REQUIRED", "evidence": "DURABILITY_UNKNOWN",
                        "outcome": record.get("business_outcome", "UNKNOWN"),
                        "exit_proof": thaw(proof),
                        "gaps": ["Supervised evidence publication is not durably confirmed"]})
                    return
                self.state.update(tx, namespace, identity, "EVIDENCE_HELPER_EXIT", {
                    "phase": "EXITED", "lifecycle": "RECONCILE_REQUIRED" if record["business_outcome"] == "UNKNOWN" else "TERMINAL", "outcome": record["business_outcome"],
                    "exit_proof": thaw(proof)})
                self._register_seal(tx, publication)
                original = record.get("business_exit_proof", {})
                if original.get("effects_checked") is True:
                    self._release(tx, row, original)
                return
            if (record["phase"] == "PREFLIGHT" and not record["cancel_requested"]
                    and proof.get("exit_code") == 0 and proof.get("effects_checked") is True):
                facts = thaw(proof.get("facts", {}))
                if facts.get("inputs_stable") is not True:
                    raise JobError("IO_UNCERTAIN", "Preflight returned no stable input proof")
                self.state.update(tx, namespace, identity, "PREFLIGHT_COMPLETE", {
                    "phase": "EXITED" if record.get("recovered") else "PREFLIGHT_COMPLETE",
                    # A late proof can resolve an earlier UNKNOWN observation.
                    # The original job still owns its pending business phase;
                    # queued reconciliation must not treat it as quiescent.
                    "lifecycle": "RECONCILE_REQUIRED" if record.get("recovered") else "RUNNING",
                    "outcome": "UNKNOWN" if record.get("recovered") else "PENDING",
                    "helper_started": True, "facts": facts, "exit_proof": thaw(proof), "gaps": []})
                return
            effects_checked = proof.get("effects_checked") is True
            result = thaw(proof.get("result", {}))
            outcome = ("CANCELLED" if record["cancel_requested"] else
                       "SUCCEEDED" if proof.get("exit_code") == 0 else "FAILED") if effects_checked else "UNKNOWN"
            publication_uncertain = False
            if record["phase"] in ("BUSINESS", "RECONCILE") and proof.get("helper_result_verified") is True:
                # Only the trusted manager can attest a stable result from the
                # exact execution. Its business observation survives a later
                # helper/report failure or a stop request received after work.
                handle = record.get("handles", {}).get(record["phase"].lower(), {})
                bound = (result.get("execution_id") == handle.get("execution_id")
                         and isinstance(result.get("execution_id"), str)
                         and result.get("outcome") in ("SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN"))
                effects_checked = effects_checked and bound and result["outcome"] != "UNKNOWN"
                outcome = result["outcome"] if effects_checked else "UNKNOWN"
                proof = dict(proof, effects_checked=effects_checked)
                if not bound:
                    result = {}  # Foreign or malformed output cannot supply a seal snapshot.
                elif effects_checked:
                    expected_exit = 0 if outcome == "SUCCEEDED" else 1
                    publication_uncertain = proof.get("exit_code") != expected_exit
            snapshot = result.get("evidence_snapshot")
            will_seal = self.evidence is not None and isinstance(snapshot, dict) and not record["cancel_requested"]
            self.state.update(tx, namespace, identity, "EXECUTION_EXIT", {
                "phase": "AWAITING_SEAL" if will_seal else "EXITED",
                "lifecycle": "RUNNING" if will_seal else "TERMINAL" if effects_checked else "RECONCILE_REQUIRED",
                "outcome": outcome, "exit_proof": thaw(proof), "runner_result": result,
                "evidence": "DURABILITY_UNKNOWN" if publication_uncertain else record["evidence"],
                "business_started": result.get("business_started", record["business_started"]),
                "helper_started": True if record["helper_started"] is True else result.get("helper_started", True),
                "side_effects": result.get("side_effects", "CHECKED" if effects_checked else "UNOBSERVED"),
                "gaps": ([REPORT_DURABILITY_GAP]
                         if publication_uncertain else [] if effects_checked else
                         ["Side effects require independent reconciliation"])})
            if will_seal:
                updated = self.state.get(namespace, identity, tx)["record"]
                proof_fields = {"execution_id": record["handles"][record["phase"].lower()]["execution_id"],
                                "event_seq": updated["event_seq"], "future_starts_blocked": True,
                                "tree_exited": True, "collectors_stopped": proof.get("collectors_stopped") is True,
                                "writers_stopped": proof.get("writers_stopped") is True}
                frozen = dict(snapshot, operation_id=row["parent"], event_seq=updated["event_seq"],
                              quiescence=proof_fields, bindings=result.get("bindings", {}))
                frozen["broker_events"] = [dict(event) for event in tx.execute(
                    "SELECT * FROM events WHERE namespace=? AND id=? AND seq<=? ORDER BY seq",
                    (namespace, identity, updated["event_seq"]))]
                if namespace == "job" and row["request"]["kind"] == "ledger.prepare" and outcome == "SUCCEEDED":
                    frozen["bindings"] = dict(frozen["bindings"], prepared_ref="prepared-" + identity,
                                              source_operation_id=identity)
                if namespace == "reconcile":
                    frozen["reconcile_id"] = identity
                    parent = self.state.get("job", row["parent"], tx)
                    previous = parent["record"].get("seals", [])
                    frozen["previous_seal_id"] = previous[-1]["seal_id"] if previous else None
                self.state.update(tx, namespace, identity, "SEAL_SNAPSHOT_FROZEN", {
                    "frozen_snapshot": frozen, "business_outcome": outcome,
                    "business_exit_proof": thaw(proof)})
            elif effects_checked:
                self._release(tx, row, proof)

    def tick(self):
        """One bounded coordinator pass, also usable by deterministic fixture tests."""
        with self.state.transaction() as tx:
            rows = self.state.all(tx)
        for row in rows:
            key, record = (row["namespace"], row["id"]), row["record"]
            if key in self._active:
                try:
                    proof = (self.runner.stop(self._active[key]) if record["cancel_requested"]
                             else self.runner.inspect(self._active[key]))
                    recovery = proof.get("recovery_handle")
                    if recovery is not None:
                        with self.state.transaction() as tx:
                            current = self.state.get(*key, tx)["record"]
                            phase = current["phase"].lower()
                            saved = dict(current["handles"])
                            handle = dict(saved[phase], **thaw(recovery))
                            if saved[phase] != handle:
                                saved[phase] = handle
                                self.state.update(tx, *key, "SUPERVISOR_IDENTITY_OBSERVED", {"handles": saved})
                    if proof.get("state") == "EXITED":
                        if proof.get("future_start_blocked") is True and proof.get("tree_exited") is True:
                            del self._active[key]
                        self._complete(*key, proof)
                        if key[0] == "job":
                            self._catalog(self.state.get(*key))
                    elif proof.get("state") == "UNKNOWN":
                        self._unknown(*key, "Supervisor has not established execution identity or exit")
                except Exception:
                    self._unknown(*key, "Supervisor observation failed")
                continue
            if (record["outcome"] == "UNKNOWN" and record["phase"] != "AWAITING_SEAL") or (record["lifecycle"] != "ACCEPTED" and record["phase"] not in ("PREFLIGHT_COMPLETE", "AWAITING_SEAL")):
                continue
            if record["cancel_requested"]:
                with self.state.transaction() as tx:
                    if record["phase"] == "AWAITING_SEAL":
                        original = record.get("business_exit_proof", {})
                        effects_checked = original.get("effects_checked") is True
                        self.state.update(tx, *key, "EVIDENCE_START_BLOCKED", {
                            "phase": "EXITED", "lifecycle": "TERMINAL" if effects_checked else "RECONCILE_REQUIRED",
                            "outcome": record.get("business_outcome", "UNKNOWN"), "evidence": "STAGING",
                            "gaps": ["Evidence helper was cancelled before launch; original business facts retained"]})
                    else:
                        effects_checked = True  # QUEUED or proved readonly preflight exit.
                        self.state.update(tx, *key, "STARTUP_BLOCKED", {"lifecycle": "TERMINAL", "outcome": "CANCELLED",
                                          "phase": "CANCELLED_BEFORE_BUSINESS", "side_effects": record["side_effects"]})
                    if effects_checked:
                        self._release(tx, row, {"future_start_blocked": True, "tree_exited": True, "effects_checked": True})
                continue
            phase = ("evidence" if record["phase"] == "AWAITING_SEAL" else "reconcile" if key[0] == "reconcile" else
                     "business" if record["phase"] == "PREFLIGHT_COMPLETE" else "preflight")
            try:
                self._start(*key, phase)
            except JobError as error:
                if not isinstance(error, budget.BudgetExhausted) or not self._budget_blocked(*key):
                    self._unknown(*key, "Startup binding or supervisor acknowledgement is unresolved")
            except Exception:
                self._unknown(*key, "Startup binding or supervisor acknowledgement is unresolved")

    def start(self):
        if self._thread is not None:
            raise JobError("CONFLICT", "Coordinator is already running")
        self.recover()
        def coordinate():
            while not self._shutdown.is_set():
                try:
                    self.tick()
                except JobError:
                    # A broken local ledger stops admission, not just this iteration.
                    if not self.state.healthy:
                        for handle in self._active.values():
                            try:
                                self.runner.stop(handle)
                            except Exception:
                                pass
                        return
                self._wake.wait(0.05)
                self._wake.clear()
        self._thread = threading.Thread(target=coordinate, name="local-hand-coordinator", daemon=True)
        self._thread.start()

    def close(self):
        self._shutdown.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        # Supervised executions remain recorded. No implicit cancellation or deletion.

    def register_seal(self, seal):
        """Evidence callback; return only after the durable DB acknowledgement."""
        with self.state.transaction() as tx:
            self._register_seal(tx, seal)
        self._catalog(self.state.get("job", seal["operation_id"]))

    def _register_seal(self, tx, seal):
        identity = seal.get("reconcile_id") or seal["operation_id"]
        namespace = "reconcile" if seal.get("reconcile_id") else "job"
        row = self.state.get(namespace, identity, tx)
        if row is None:
            raise JobError("NOT_FOUND", "Seal has no operation")
        if row["parent"] != seal["operation_id"]:
            raise JobError("CONFLICT", "Seal operation differs from its reconciliation parent")
        if seal.get("complete") is not True:
            raise JobError("NOT_SEALED", "Seal publication is incomplete")
        if row["record"]["phase"] != "EXITED":
            raise JobError("NOT_SEALED", "Operation writers have not become quiescent")
        frozen = row["record"].get("frozen_snapshot", {})
        if frozen and (seal["event_seq"] != frozen["event_seq"] or seal.get("bindings", {}) != frozen.get("bindings", {})):
            raise JobError("CONFLICT", "Seal differs from its frozen observation")
        seals = list(row["record"].get("seals", []))
        if any(item["seal_id"] == seal["seal_id"] for item in seals):
            raise JobError("CONFLICT", "Seal identity already exists")
        seals.append(dict(thaw(seal), evidence_state="SEALED"))
        changes = {"evidence": "SEALED", "seals": seals, "outputs": {},
                   "gaps": [gap for gap in row["record"].get("gaps", []) if gap != REPORT_DURABILITY_GAP]}
        result = row["record"].get("runner_result", {})
        if namespace == "job" and row["request"]["kind"] == "ledger.prepare" and row["record"]["outcome"] == "SUCCEEDED":
            facts = result.get("prepared")
            if not isinstance(facts, dict):
                raise JobError("NOT_SEALED", "Preparation output is incomplete")
            ref = "prepared-" + row["id"]
            bindings = facts.get("bindings", {})
            required = ("source_digest", "wheel_digest", "installed_payload_digest", "runtime_digest", "environment_fingerprint")
            if any(not isinstance(bindings.get(name), str) or len(bindings[name]) != 64 for name in required):
                raise JobError("NOT_SEALED", "Preparation digest bindings are incomplete")
            facts = dict(facts, prepared_ref=ref, owner=row["principal"], profile_ref=row["request"]["profile_ref"],
                         expected=row["request"]["expected"], outcome="SUCCEEDED", evidence_state="SEALED", sealed=True, seal=seal["seal_id"])
            changes["prepared_facts"] = facts
            changes["outputs"] = {"schema_version": "lh-prepared-output-v1", "prepared_ref": ref,
                "source_commit": facts["source_commit"], "bindings": {name: bindings[name] for name in required},
                "source_operation_id": row["id"], "seal_ref": seal["seal_id"]}
        self.state.update(tx, namespace, identity, "EVIDENCE_SEALED", changes)

    def is_registered(self, seal_id, digest):
        with self.state.transaction() as tx:
            return any(seal.get("seal_id") == seal_id and
                       (seal.get("sha256") == digest or seal.get("seal_sha256") == digest)
                       for row in self.state.all(tx) for seal in row["record"].get("seals", []))

    def list_seals(self, operation_id):
        """Trusted bounded evidence lookup; transport authorization is separate.

        Registered seals, including reconciliation observations, come only from
        this ledger. An absent or corrupt artifact must not disappear from this
        list merely because its on-disk publication is incomplete.
        """
        with self.state.transaction() as tx:
            if self.state.get("job", operation_id, tx) is None:
                raise JobError("NOT_FOUND", "No matching record in the healthy ledger")
            refs, seen = [], set()
            identities = tx.execute("SELECT namespace,id FROM operations WHERE parent=? ORDER BY rowid LIMIT 1001",
                                    (operation_id,)).fetchall()
            if len(identities) > 1000:
                raise JobError("LIMIT_EXCEEDED", "Operation observation inventory exceeds its budget")
            for namespace, identity in identities:
                row = self.state.get(namespace, identity, tx)
                for seal in row["record"].get("seals", []):
                    if len(refs) >= 1000:
                        raise JobError("LIMIT_EXCEEDED", "Registered seal inventory exceeds its budget")
                    seal_id, digest = seal.get("seal_id"), seal.get("seal_sha256")
                    if not isinstance(seal_id, str) or not isinstance(digest, str) or seal_id in seen:
                        raise JobError("IO_UNCERTAIN", "Registered seal identity is unresolved")
                    refs.append({"seal_id": seal_id, "seal_sha256": digest})
                    seen.add(seal_id)
            return refs
