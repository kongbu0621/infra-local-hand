"""One finite resume/compensation protocol; effects never follow phase alone."""
from __future__ import annotations

import time
from local_hand_jobs.contract import JobError

from .model import DeployError, digest


class Coordinator:
    """The environment is a fixed trusted adapter set, not a manifest callback.

    All public mutation methods own the deployment flock. Durable intent always
    precedes an effect. Each explicit resume has a finite action/attempt budget;
    waiting preserves the exact unfinished action instead of replaying it.
    """
    def __init__(self, store, gate, environment, *, implementation=None):
        self.store, self.gate, self.environment = store, gate, environment
        self.implementation = None if implementation is None else dict(implementation)
        if self.implementation is not None:
            lengths = {"source_commit": 40, "source_tree": 40, "adapter_digest": 64}
            if (set(self.implementation) != set(lengths) or any(
                    not isinstance(self.implementation[key], str) or len(self.implementation[key]) != size
                    or any(character not in "0123456789abcdef" for character in self.implementation[key])
                    for key, size in lengths.items())):
                raise DeployError("INVALID_IMPLEMENTATION", "Actual implementation requires verified source identities")

    def _record_implementation(self, op):
        if (self.implementation is not None and not op["released"] and not op["handoff_complete"]
                and op.get("implementation") != self.implementation):
            op["implementation"] = dict(self.implementation)
            self.store.save(op, "IMPLEMENTATION_OBSERVED", self.implementation, recovery=True)

    def apply(self, plan):
        self.store.validate_plan(plan)
        with self.store.locked():
            existing = next((op for op in self.store.list() if op["plan"]["request_id"] == plan["request_id"]), None)
            if existing is None and self.store.list(unfinished=True):
                raise DeployError("RECOVERY_REQUIRED", "Resume or explicitly hand off the existing operation before creating another")
            if existing is None and plan["profile"].get("recovery_from"):
                raise DeployError("RECOVERY_REQUIRED", "A corrective plan must be linked with supersede, not applied independently")
            operation = self.store.create(plan)
            others = [op for op in self.store.list(unfinished=True)
                      if op["id"] != operation["id"] and op["successor"] != operation["id"]]
            if others and not operation["released"] and not operation["successor"]:
                raise DeployError("RECOVERY_REQUIRED", "Another recorded operation requires resume or explicit handoff")
            return self._run(operation)

    def resume(self, operation_id):
        with self.store.locked():
            return self._run(self.store.get(operation_id))

    def rollback(self, operation_id):
        with self.store.locked():
            op = self.store.get(operation_id)
            if hasattr(self.environment, "for_operation"):
                self.environment = self.environment.for_operation(op)
            # Routing precedes all phase/direction checks. Old invocations may
            # never reacquire a gate after a successful handoff or rollback.
            if op["successor"]:
                return self._handoff(op)
            if op["rollback_successor"]:
                return self._run(self.store.get(op["rollback_successor"]))
            if op["decision"] == "COMMITTED":
                request = "rollback-" + digest({"operation": op["id"], "decision": op["decision_id"]})[:48]
                plan = self.environment.restored_plan(op, request)
                successor = self.store.link(op, plan, rollback=True)
                return self._run(successor)
            if op["decision"]:
                return self._run(op)
            if op["direction"] != "ROLLBACK":
                op["direction"] = "ROLLBACK"
                self.store.save(op, "ROLLBACK_SELECTED", recovery=True)
            return self._run(op)

    def supersede(self, operation_id, plan):
        """Explicit corrected plan, linked before ownership can be transferred."""
        self.store.validate_plan(plan)
        with self.store.locked():
            op = self.store.get(operation_id)
            if hasattr(self.environment, "for_operation"):
                self.environment = self.environment.for_operation(op)
            if op["successor"]:
                if self.store.get(op["successor"])["plan"]["digest"] != plan["digest"]:
                    raise DeployError("REQUEST_CONFLICT", "A different handoff is already recorded")
                return self._handoff(op)
            if hasattr(self.environment, "validate_successor"):
                self.environment.validate_successor(op, plan)
            if op["released"]:
                # The old effect ownership has already ended. A later repair
                # is linked for history, but cannot reclaim its historical gate
                # or compensate the already completed deployment's effects.
                self.store.link(op, plan)
                return self._handoff(op)
            self._record_implementation(op)
            self._refresh(op)
            if self._unresolved(op):
                return self._wait(op, "CALLER_NOT_CLOSED")
            inherited = self._inheritance(op)
            successor = self.store.link(op, plan)
            if inherited:
                successor["inherited"] = inherited
                self.store.save(successor, "INHERITED_EFFECTS", {"predecessor": op["id"]}, recovery=True)
            return self._handoff(op)

    def _inheritance(self, op):
        if op["released"]:
            return []
        inherited = list(dict.fromkeys([*op.get("inherited", []), op["id"]])) if self._has_effects(op) else []
        if len(inherited) > 16:
            raise DeployError("STATE_LIMIT", "Recovery chain exceeds its fixed limit")
        return inherited

    def _handoff(self, op):
        if op["handoff_complete"]:
            return op
        self._record_implementation(op)
        successor = self.store.get(op["successor"])
        # A crash immediately after the atomic link must not lose responsibility.
        inherited = self._inheritance(op)
        if inherited and successor.get("inherited") != inherited:
            successor["inherited"] = inherited
            self.store.save(successor, "INHERITED_EFFECTS", recovery=True)
        if op["gate_owned"] and not op["released"]:
            state = self.gate.snapshot()
            if state["state"] == "CLOSED" and state["owner"] == op["id"]:
                self.store.save(op, "HANDOFF_INTENT", {"successor": successor["id"]}, recovery=True)
                state = self.gate.handoff(op["id"], successor["id"], expected=state)
            if state["state"] != "CLOSED" or state["owner"] != successor["id"]:
                raise DeployError("HANDOFF_CONFLICT", "Maintenance ownership does not match the linked handoff")
            successor["gate_owned"] = True
            successor["gate_sequence"] = state["sequence"]
            self.store.save(successor, "HANDOFF_RECEIVED", recovery=True)
        op["handoff_complete"] = True
        op["waiting"] = None
        self.store.save(op, "HANDED_OFF", recovery=True)
        return op

    def _wait(self, op, reason, detail=None):
        op["waiting"] = {"reason": reason, "detail": detail or {}, "observed_ns": time.time_ns(),
                         "resume": op["id"]}
        # Repeated observations must not consume the reserve needed to undo
        # effects and release the gate after the actual fault is removed.
        self.store.save(op, "WAITING", op["waiting"])
        return op

    def _error(self, op, error):
        category = "recovery" if op["direction"] == "ROLLBACK" else "primary"
        record = {"code": str(getattr(error, "code", type(error).__name__))[:128],
                  "phase": op["phase"], "time_ns": time.time_ns()}
        # Raw output, addresses and credentials belong in private adapter
        # evidence. Keep the bounded structured error chain independently.
        if len(op["errors"][category]) < 64:
            op["errors"][category].append(record)
        return self._wait(op, "ACTION_FAILED", record)

    def _run(self, op):
        if hasattr(self.environment, "for_operation"):
            self.environment = self.environment.for_operation(op)
        if op["successor"]:
            return self._handoff(op)
        if op["released"]:
            # Historical completion stays true. A status observation can report
            # later drift, but an old request does not redeploy or close admission.
            return op
        self._record_implementation(op)
        try:
            if op["decision"]:
                return self._release(op)
            if op["direction"] == "ROLLBACK":
                return self._rollback(op)
            return self._apply(op)
        except (OSError, RuntimeError, ValueError, JobError) as error:
            # If persistence itself fails there can be no invented success.
            # _error's own failure propagates; the last durable intent survives.
            return self._error(op, error)

    def _prepare(self, op):
        for step, record in zip(op["plan"]["steps"], op["steps"]):
            if record["prepared"] is None:
                self.store.save(op, "PREPARATION_INTENT", {"step": step["id"]})
                record["prepared"] = self.environment.prepare(step, op, record)
                self.store.save(op, "PREPARED_STEP", {"step": step["id"]})
        op["phase"] = "PREPARED"
        self.store.save(op, "PREPARED")

    def _close(self, op):
        if not op["gate_owned"]:
            op["record_budget"] = self.store.check_attempt_budget(op)
        state = self.gate.snapshot()
        if state["state"] == "CLOSED" and state["owner"] == op["id"]:
            pass
        else:
            self.store.save(op, "CLOSE_INTENT", {"expected": state["sequence"]})
            state = self.gate.close(op["id"], expected=state)
        op["gate_owned"] = True
        op["gate_sequence"] = state["sequence"]
        self.store.save(op, "CLOSED")

    def _block(self, op):
        self.store.save(op, "STARTUP_BLOCK_INTENT", recovery=op["direction"] == "ROLLBACK")
        op["startup"]["current"] = self.environment.block_startup(op)
        op["startup"]["blocked"] = True
        self.store.save(op, "STARTUP_BLOCKED", recovery=op["direction"] == "ROLLBACK")

    def _apply(self, op):
        if op["phase"] == "PLANNED":
            op["checks"]["preflight"] = self.environment.preflight(op)
            op["phase"] = "PREPARING"
            self.store.save(op, "PREFLIGHT")
        if op["phase"] == "PREPARING":
            self._prepare(op)
            if not op["plan"]["steps"] and op["plan"]["source"]["deployment_digest"] == op["plan"]["target"]["deployment_digest"]:
                checks = self.environment.check_local(op, rollback=False)
                op["checks"]["local"] = checks
                self.store.save(op, "NO_CHANGE_CHECK")
                if checks.get("passed") is not True:
                    return self._wait(op, "LOCAL_CHECK_FAILED")
                return self._decide(op, "COMMITTED")
        if not op["gate_owned"]:
            self._close(op)
        self._refresh(op)
        if self._unresolved(op):
            return self._wait(op, "CALLER_NOT_CLOSED")
        # Isolation is the only effect allowed before business drain. The
        # adapter's fixed action scope must prove it cannot stop business jobs.
        isolation = [(s, r) for s, r in zip(op["plan"]["steps"], op["steps"])
                     if s["action"].get("phase") == "isolate"]
        if isolation or op["plan"]["profile"].get("security_repair"):
            self._block(op)
            for step, record in isolation:
                if not self._step(op, step, record):
                    return op
        drain = self.environment.drain(op)
        active = self.gate.active()
        if active or drain.get("quiescent") is not True:
            return self._wait(op, "DRAIN", {"accepted_responsibilities": len(active), "observation": drain})
        if hasattr(self.environment, "quiesced_retention"):
            op["checks"]["retained"] = self.environment.quiesced_retention(op)
            self.store.save(op, "RETAINED_BINDINGS")
        op["phase"] = "QUIESCED"
        self.store.save(op, "QUIESCED")
        self._block(op)
        op["phase"] = "APPLYING"
        self.store.save(op, "APPLYING")
        for step, record in zip(op["plan"]["steps"], op["steps"]):
            if not self._step(op, step, record):
                return op
        checks = self.environment.check_local(op, rollback=False)
        op["checks"]["local"] = checks
        self.store.save(op, "LOCAL_CHECK")
        if checks.get("passed") is not True:
            return self._wait(op, "LOCAL_CHECK_FAILED")
        op["phase"] = "LOCAL_VERIFIED"
        self.store.save(op, "LOCAL_VERIFIED")
        return self._decide(op, "COMMITTED")

    def _refresh(self, op):
        if "compensation" in op:
            # The fixed compensation list is created only after every forward
            # caller closed. Restored files/services intentionally invalidate
            # forward postconditions; recovery now follows the inverse chain.
            self._refresh_compensation(op)
            return
        original = digest(op["steps"])
        covered = {}
        for step, record in reversed(list(zip(op["plan"]["steps"], op["steps"]))):
            if record["prepared"] is None or not (record["attempts"] or record["effective"]
                    or record["state"] in {"VERIFIED", "RESTORED"}):
                continue
            if self._retain_effect_identity(step, record):
                self.store.save(op, 'EFFECT_IDENTITY_RETAINED', {'step': step['id']}, recovery=True)
            key = self.environment.effect_key(step)
            if key in covered:
                record["covered_by"] = covered[key]
                continue
            record.pop("covered_by", None)
            attempt = record["attempts"][-1] if record["attempts"] else None
            observed = self.environment.observe(step, record["prepared"], attempt)
            record["observation"] = observed
            self._retain_effect_identity(step, record)
            record["effective"] = record["effective"] or observed.get("effective", False)
            if observed.get("state") == "target" and observed.get("closed") is True:
                covered[key] = step["id"]
        if digest(op["steps"]) != original:
            self.store.save(op, "RECONCILED", recovery=not self._unresolved(op))

    def _unresolved(self, op):
        if "compensation" in op:
            return any(r.get("restore_observation") and not r.get("covered_by") and
                       (r["restore_observation"].get("state") in {"running", "unknown"} or
                        r["restore_observation"].get("closed") is not True)
                       for r in (entry["record"] for entry in op["compensation"]))
        return any(r.get("observation") and not r.get("covered_by") and
                   (r["observation"].get("state") in {"running", "unknown"} or
                    r["observation"].get("closed") is not True) for r in op["steps"])

    def _has_effects(self, op):
        return (bool(op.get("inherited")) or any(record["effective"] for record in op["steps"])
                or bool(op["gate_owned"] and op["plan"]["profile"].get("security_repair")))

    def _refresh_compensation(self, op):
        original = digest(op["compensation"])
        covered = {}
        for entry in reversed(op["compensation"]):
            step, record = entry["step"], entry["record"]
            key = self.environment.effect_key(step)
            if key in covered:
                record["covered_by"] = covered[key]
                continue
            record.pop("covered_by", None)
            if record["restore_attempts"] or record["state"] == "RESTORED":
                if self._retain_effect_identity(step, record, restore=True):
                    self.store.save(op, 'EFFECT_IDENTITY_RETAINED', {'step': step['id'], 'restore': True}, recovery=True)
                previous = record["restore_attempts"][-1] if record["restore_attempts"] else None
                observed = self.environment.observe(step, record["restore"], previous)
                record["restore_observation"] = observed
                self._retain_effect_identity(step, record, restore=True)
                if observed.get("state") == "target" and observed.get("closed") is True:
                    covered[key] = step["id"]
        if digest(op["compensation"]) != original:
            self.store.save(op, "RESTORATION_RECONCILED", recovery=not self._unresolved(op))

    @staticmethod
    def _requires_sync(step):
        return step["kind"] == "file" or (step["kind"] == "service"
                and step["action"].get("kind") == "service_policy_link")

    def _retain_effect_identity(self, step, record, *, restore=False):
        if step['kind'] != 'gateway' or step['action'].get('kind') != 'gateway_create':
            return False
        attempts = record['restore_attempts' if restore else 'attempts']
        if not attempts or not attempts[-1].get('binding'):
            return False
        attempt = attempts[-1]
        before = digest(attempt)
        observed = record.get('restore_observation' if restore else 'observation') or {}
        prepared = record['restore' if restore else 'prepared']
        identity = (self.environment.effect_identity(step, prepared, attempt, observed)
                    if hasattr(self.environment, 'effect_identity') else observed.get('effect_identity'))
        if identity is not None:
            if attempt.get('effect_identity', identity) != identity:
                raise DeployError('EFFECT_IDENTITY_CONFLICT', 'Original effect identity cannot be rebound')
            attempt['effect_identity'] = identity
        elif record['state'] in {'VERIFIED', 'RESTORED'}:
            attempt['effect_identity_required'] = True
        return digest(attempt) != before

    @classmethod
    def _step_complete(cls, step, observed):
        return (observed.get("state") == "target" and observed.get("closed") is True
                and (not cls._requires_sync(step) or observed.get("synced") is True))

    def _step(self, op, step, record, *, restore=False):
        if not restore and record.get("covered_by"):
            return True
        key = "restore" if restore else "prepared"
        attempt_key = "restore_attempts" if restore else "attempts"
        observation_key = "restore_observation" if restore else "observation"
        attempts = record[attempt_key]
        previous = attempts[-1] if attempts else None
        observed = self.environment.observe(step, record[key], previous)
        if previous is not None and "dispatched" in observed:
            previous["dispatched"] = observed["dispatched"]
        record[observation_key] = observed
        self._retain_effect_identity(step, record, restore=restore)
        if not restore:
            record["effective"] = record["effective"] or observed.get("effective", False)
        self.store.save(op, "OBSERVATION", {"step": step["id"], "restore": restore},
                        recovery=restore and observed.get("closed") is True)
        if observed.get("state") == "target" and observed.get("closed") is True:
            # File publication and service policy links can be visible before
            # their required directory sync completed. Observations stay read-only.
            if self._requires_sync(step) and observed.get("synced") is not True:
                op["record_budget"] = self.store.check_attempt_budget(op, restore=restore)
                self.store.save(op, "SYNC_INTENT", {"step": step["id"], "restore": restore}, recovery=restore)
                observed = self.environment.execute(step, record[key], op, None, lambda _: None, previous=previous)
                record[observation_key] = observed
                if not self._step_complete(step, observed):
                    self._wait(op, "SYNC_PENDING", {"step": step["id"]})
                    return False
            record["state"] = "RESTORED" if restore else "VERIFIED"
            self.store.save(op, "RESTORED_STEP" if restore else "VERIFIED_STEP", {"step": step["id"]}, recovery=restore)
            return True
        if observed.get("state") in {"unknown", "running", "conflict"} or observed.get("closed") is not True:
            self._wait(op, "RECONCILE_REQUIRED", {"step": step["id"], "state": observed.get("state")})
            return False
        dispatched = sum(1 for attempt in attempts if attempt.get("dispatched") is not False
                         and (attempt.get("binding") is not None or attempt.get("command") != "not_attempted"))
        if dispatched >= self.store.limits.max_attempts:
            self._wait(op, "ATTEMPT_BUDGET", {"step": step["id"]})
            return False
        attempt_id = "a_" + digest({"operation": op["id"], "step": step["id"], "restore": restore, "number": len(attempts)})[:48]
        op["record_budget"] = self.store.check_attempt_budget(op, restore=restore)
        attempt = {"attempt_id": attempt_id, "binding": None, "command": "not_attempted", "dispatched": False}
        attempts.append(attempt)
        record["state"] = "INTENT_RECORDED"
        self.store.save(op, "RESTORE_INTENT" if restore else "ACTION_INTENT", {"step": step["id"], "attempt_id": attempt_id}, recovery=restore)
        self.store.save(op, "CANDIDATE_STARTUP_INTENT", {"step": step["id"], "attempt_id": attempt_id}, recovery=restore)
        self.environment.candidate_startup(op, step, attempt_id)
        def bind(binding):
            attempt["binding"] = binding
            attempt["command"] = "unknown"
            attempt["dispatched"] = None
            self.store.save(op, "SUPERVISOR_BOUND", {"step": step["id"], "attempt_id": attempt_id}, recovery=restore)
        observed = self.environment.execute(step, record[key], op, attempt_id, bind, previous=previous)
        attempt["command"] = "returned"
        attempt["dispatched"] = observed.get("dispatched", True)
        record[observation_key] = observed
        self._retain_effect_identity(step, record, restore=restore)
        if not restore:
            record["effective"] = record["effective"] or observed.get("effective", False)
        self.store.save(op, "ACTION_RETURNED", {"step": step["id"], "attempt_id": attempt_id}, recovery=restore)
        if self._step_complete(step, observed):
            record["state"] = "RESTORED" if restore else "VERIFIED"
            self.store.save(op, "RESTORED_STEP" if restore else "VERIFIED_STEP", {"step": step["id"]}, recovery=restore)
            return True
        self._wait(op, "POSTCONDITION_PENDING", {"step": step["id"], "state": observed.get("state")})
        return False

    def _rollback(self, op):
        self._refresh(op)
        if self._unresolved(op):
            return self._wait(op, "CALLER_NOT_CLOSED")
        if not self._has_effects(op):
            # No config/service effect: a long accepted task need not be killed
            # or drained merely to abandon an unused deployment plan.
            return self._decide(op, "ABORTED_NO_CHANGE")
        if not op["gate_owned"]:
            self._close(op)
        drain = self.environment.drain(op)
        active = self.gate.active()
        if active or drain.get("quiescent") is not True:
            return self._wait(op, "DRAIN", {"accepted_responsibilities": len(active), "observation": drain})
        self._block(op)
        # Compensation is a fixed dependency order, not naive reverse order:
        # stop candidate -> restore files -> reload -> restore original runtime.
        # Once prepared, this exact list survives a second recovery interruption.
        if "compensation" not in op:
            self.store.save(op, "RESTORE_PREPARATION_INTENT", recovery=True)
            actions = self.environment.prepare_compensation(op)
            if len(actions) > self.store.limits.max_steps:
                raise DeployError("STATE_LIMIT", "Compensation exceeds the fixed action count")
            op["compensation"] = [{"step": action["step"], "record": {
                "id": action["step"]["id"], "state": "PLANNED", "prepared": None,
                "restore": action["prepared"], "attempts": [], "restore_attempts": [],
                "observation": None, "restore_observation": None, "effective": False}}
                for action in actions]
            self.store.save(op, "RESTORE_PREPARED", recovery=True)
        self._refresh_compensation(op)
        for entry in op["compensation"]:
            if entry["record"].get("covered_by"):
                continue
            if not self._step(op, entry["step"], entry["record"], restore=True):
                return op
        checks = self.environment.check_local(op, rollback=True)
        op["checks"]["restored"] = checks
        self.store.save(op, "RESTORATION_CHECK", recovery=True)
        if checks.get("passed") is not True:
            return self._wait(op, "RESTORATION_CHECK_FAILED")
        return self._decide(op, "ROLLED_BACK")

    def _decide(self, op, decision):
        op["decision"] = decision
        op["decision_id"] = "decision-" + digest({"operation": op["id"], "decision": decision})[:48]
        op["phase"] = decision
        op["waiting"] = None
        self.store.save(op, "DECISION", {"decision": decision}, recovery=True)
        return self._release(op)

    def _release(self, op):
        if not op["gate_owned"]:
            op["released"] = True
            self.store.save(op, "NO_OWNED_GATE", recovery=True)
            return op
        state = self.gate.snapshot()
        selected = self.environment.selected_deployment(op)
        if (state["state"] == "OPEN" and state["decision_id"] == op["decision_id"]
                and state["deployment_digest"] == selected["deployment_digest"]):
            op["released"] = True
            self.store.save(op, "RELEASE_OBSERVED", recovery=True)
            return op
        proof = self.environment.release_valid(op)
        if proof.get("passed") is not True:
            return self._wait(op, "DECISION_REQUIRES_LINKED_REPAIR", proof)
        if hasattr(self.environment, "activate_retention"):
            op["checks"]["released_compatibility"] = self.environment.retention_decisions(op, selected)
            self.store.save(op, "COMPATIBILITY_DECISIONS", recovery=True)
            self.environment.activate_retention(op, selected)
        self.store.save(op, "STABLE_SELECTION_INTENT", recovery=True)
        op["startup"]["current"] = self.environment.publish_stable(op)
        self.store.save(op, "STABLE_SELECTION", recovery=True)
        self.store.save(op, "RELEASE_INTENT", recovery=True)
        self.gate.release(op["id"], op["decision_id"], selected["deployment_digest"], expected=state)
        op["released"] = True; op["waiting"] = None
        self.store.save(op, "RELEASED", recovery=True)
        return op
