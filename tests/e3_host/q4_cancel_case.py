"""Fixed test-only cancellation case, composed with the real broker and core.

This observer never starts a task, changes a manager result, or manufactures an
exit proof. The one action is the existing owner's broker.cancel request after
the original preflight helper is observed RUNNING. Local tests model OS facts;
only a separately admitted fixture can provide host evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import threading

SCHEMA = "local-hand-q4-cancel-case/v1"
PURPOSE = "ISOLATED_Q4_CANCELLATION"
MAX_REPORT_BYTES = 16384
MAX_LOG_BYTES = 4096
MAX_LOG_ITEMS = 24
MAX_STOPS = 4
STATUSES = {"PENDING", "EXERCISED", "NOT_EXERCISED", "INCOMPLETE"}
_SHOW_FIELDS = ("Id", "LoadState", "ActiveState", "SubState", "ControlGroup", "InvocationID", "Job")
_EXIT_FLAGS = ("future_start_blocked", "tree_exited", "collectors_stopped", "writers_stopped")
_KEYS = {"schema", "purpose", "operation_id", "request_digest", "principal_id", "target_execution_id", "phase", "boot_id",
         "phase_deadline_ns", "record_deadline_ns",
         "observed_ns", "status", "ready_for_finish", "completion_reason", "trigger", "cancel", "stops",
         "helper", "helper_exit_proven", "chain_closed", "ledger", "logs", "errors"}


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def _clock():
    from local_hand_jobs import budget
    return budget.current_clock()


def _require(ok, code):
    if not ok:
        raise ValueError(code)


def _error(error):
    code = getattr(error, "code", None)
    if isinstance(error, ValueError) and re.fullmatch(r"CASE_[A-Z_]{1,70}", str(error)):
        return str(error)
    return code if isinstance(code, str) and re.fullmatch(r"[A-Z_]{1,80}", code) else type(error).__name__[:80]


def _terminal(values):
    return values.get("SubState") == "exited" or values.get("ActiveState") in ("inactive", "failed")


def _positive(value):
    return type(value) is int and value > 0


def validate_report(value):
    """Validate intermediate/final case records; never authorize chain closure."""
    errors = []
    try:
        _require(type(value) is dict and set(value) == _KEYS, "CASE_KEYS")
        _require(len(_encode(value)) <= MAX_REPORT_BYTES, "CASE_SIZE")
        _require(value["schema"] == SCHEMA and value["purpose"] == PURPOSE, "CASE_SCHEMA")
        _require(isinstance(value["operation_id"], str) and re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value["operation_id"]), "CASE_OPERATION")
        _require(isinstance(value["request_digest"], str) and re.fullmatch(r"[0-9a-f]{64}", value["request_digest"]), "CASE_DIGEST")
        _require(isinstance(value["principal_id"], str) and 1 <= len(value["principal_id"]) <= 200, "CASE_OWNER")
        _require(value["target_execution_id"] == "job-" + value["operation_id"] + "-preflight", "CASE_EXECUTION")
        _require(value["phase"] == "preflight" and isinstance(value["boot_id"], str)
                 and 1 <= len(value["boot_id"]) <= 64, "CASE_PHASE_BOOT")
        _require((value["phase_deadline_ns"] is None and value["record_deadline_ns"] is None) or
            _positive(value["record_deadline_ns"]) and _positive(value["phase_deadline_ns"])
            and value["record_deadline_ns"] < value["phase_deadline_ns"], "CASE_ORIGINAL_DEADLINES")
        _require(_positive(value["observed_ns"]) and value["status"] in STATUSES, "CASE_STATUS")
        _require(type(value["ready_for_finish"]) is bool and type(value["helper_exit_proven"]) is bool
                 and value["chain_closed"] is False, "CASE_PROOF_FLAGS")
        _require(value["completion_reason"] in (None, "HELPER_EXIT", "RECORD_DEADLINE", "NATURAL_END",
                 "CANCEL_FAILED", "OBSERVATION_ERROR", "CLOSED"), "CASE_COMPLETION")
        _require((value["completion_reason"] is not None) == value["ready_for_finish"], "CASE_COMPLETION_STATE")
        cancel = value["cancel"]
        _require(type(cancel) is dict and set(cancel) == {"attempted", "request_ns", "returned_ns", "error"}
                 and type(cancel["attempted"]) is bool, "CASE_CANCEL")
        _require((cancel["request_ns"] is not None) == cancel["attempted"], "CASE_CANCEL_REQUEST")
        if cancel["attempted"]:
            _require(_positive(cancel["request_ns"]), "CASE_CANCEL_TIME")
            if cancel["returned_ns"] is not None:
                _require(_positive(cancel["returned_ns"]) and cancel["returned_ns"] >= cancel["request_ns"], "CASE_CANCEL_RETURN")
            _require(not value["ready_for_finish"] or cancel["returned_ns"] is not None, "CASE_CANCEL_INFLIGHT")
        else:
            _require(cancel["returned_ns"] is None and cancel["error"] is None, "CASE_CANCEL_ABSENCE")
        _require(cancel["error"] is None or isinstance(cancel["error"], str) and len(cancel["error"]) <= 80, "CASE_CANCEL_ERROR")
        trigger = value["trigger"]
        if trigger is not None:
            _require(type(trigger) is dict and set(trigger) == {"identity", "observed_ns", "deadline_ns", "record_deadline_ns"}, "CASE_TRIGGER")
            _identity(trigger["identity"], value["target_execution_id"])
            _require(trigger["identity"]["boot_id"] == value["boot_id"], "CASE_TRIGGER_BOOT")
            _require(all(_positive(trigger[k]) for k in ("observed_ns", "deadline_ns", "record_deadline_ns"))
                     and trigger["observed_ns"] < trigger["record_deadline_ns"] < trigger["deadline_ns"], "CASE_TRIGGER_WINDOW")
            _require(trigger["deadline_ns"] == value["phase_deadline_ns"] and
                trigger["record_deadline_ns"] == value["record_deadline_ns"], "CASE_TRIGGER_DEADLINE_BINDING")
            _require(not cancel["attempted"] or trigger["observed_ns"] <= cancel["request_ns"] < trigger["record_deadline_ns"], "CASE_TRIGGER_CANCEL")
        _require(not cancel["attempted"] or trigger is not None, "CASE_TRIGGER_MISSING")
        ledger = value["ledger"]
        _require(type(ledger) is dict and set(ledger) == {"cancel_event", "delivery_events", "no_delivery_after_cancel",
            "lifecycle", "outcome", "evidence", "phase", "cancel_requested", "reader_delivered", "leases_retained",
            "observed_ns", "state_converged"}, "CASE_LEDGER")
        _require(_positive(ledger["observed_ns"]) and ledger["observed_ns"] <= value["observed_ns"]
                 and ledger["state_converged"] is False, "CASE_LEDGER_ASOF")
        _require(type(ledger["delivery_events"]) is list and len(ledger["delivery_events"]) <= 12, "CASE_DELIVERY_BOUND")
        previous = 0
        for row in ledger["delivery_events"]:
            _require(type(row) is dict and set(row) == {"seq", "delivery_ids"} and _positive(row["seq"])
                     and row["seq"] > previous and type(row["delivery_ids"]) is list and len(row["delivery_ids"]) <= 9
                     and all(isinstance(item, str) and len(item) <= 160 for item in row["delivery_ids"]), "CASE_DELIVERY_EVENT")
            previous = row["seq"]
        event = ledger["cancel_event"]
        if event is not None:
            _require(type(event) is dict and set(event) == {"seq", "observed_at_hex", "cancel_requested"}
                     and _positive(event["seq"]) and isinstance(event["observed_at_hex"], str)
                     and len(event["observed_at_hex"]) <= 64 and event["cancel_requested"] is True, "CASE_DURABLE_CANCEL")
            wall = float.fromhex(event["observed_at_hex"])
            _require(math.isfinite(wall) and wall > 0 and wall.hex() == event["observed_at_hex"], "CASE_DURABLE_CANCEL_TIME")
        derived = None if event is None else all(row["seq"] < event["seq"] for row in ledger["delivery_events"])
        _require(ledger["no_delivery_after_cancel"] is derived, "CASE_DELIVERY_ORDER")
        for key in ("cancel_requested", "reader_delivered", "leases_retained"):
            _require(type(ledger[key]) is bool, "CASE_LEDGER_BOOL")
        _require(ledger["reader_delivered"] == any(value["target_execution_id"] + ":result_reader" in row["delivery_ids"]
            for row in ledger["delivery_events"]), "CASE_READER_BINDING")
        for key in ("lifecycle", "outcome", "evidence", "phase"):
            _require(isinstance(ledger[key], str) and len(ledger[key]) <= 80, "CASE_LEDGER_STATE")
        stops = value["stops"]
        _require(type(stops) is list and len(stops) <= MAX_STOPS, "CASE_STOP_BOUND")
        for stop in stops:
            _require(type(stop) is dict and set(stop) == {"identity", "observed_ns", "deadline_ns", "nonterminal",
                "identity_rechecked", "cancel_returned_before_stop", "ack", "returned_ns", "error",
                "before", "rechecked_invocation_id", "stop_requested", "cancel_event_set", "cancel_effective_before_stop"}, "CASE_STOP")
            _identity(stop["identity"], value["target_execution_id"])
            _require(stop["identity"]["boot_id"] == value["boot_id"], "CASE_STOP_BOOT")
            _require(_positive(stop["observed_ns"]) and _positive(stop["deadline_ns"]), "CASE_STOP_WINDOW")
            _require(stop["deadline_ns"] == value["phase_deadline_ns"], "CASE_STOP_DEADLINE_BINDING")
            before = stop["before"]
            _require(before is None or type(before) is dict and set(before) == set(_SHOW_FIELDS)
                and all(isinstance(item, str) and len(item) <= 512 for item in before.values()), "CASE_STOP_BEFORE")
            _require(stop["rechecked_invocation_id"] is None or isinstance(stop["rechecked_invocation_id"], str)
                and len(stop["rechecked_invocation_id"]) <= 32, "CASE_STOP_RECHECK")
            same = bool(before and before["Id"] == stop["identity"]["unit"] and before["LoadState"] == "loaded"
                and before["InvocationID"] == stop["identity"]["invocation_id"] and before["ControlGroup"] == stop["identity"]["cgroup"]
                and stop["rechecked_invocation_id"] == stop["identity"]["invocation_id"])
            _require(stop["identity_rechecked"] is same and stop["nonterminal"] is bool(before and not _terminal(before)), "CASE_STOP_DERIVATION")
            for key in ("nonterminal", "identity_rechecked", "cancel_returned_before_stop", "stop_requested", "cancel_event_set", "cancel_effective_before_stop"):
                _require(type(stop[key]) is bool, "CASE_STOP_FACT")
            _require(stop["cancel_effective_before_stop"] is bool(cancel["attempted"]
                and (stop["stop_requested"] or stop["cancel_event_set"])
                and stop["observed_ns"] >= cancel["request_ns"]), "CASE_STOP_CANCEL_CAUSALITY")
            _require(stop["ack"] is None or type(stop["ack"]) is bool, "CASE_STOP_ACK")
            _require(stop["returned_ns"] is None or _positive(stop["returned_ns"])
                and stop["returned_ns"] >= stop["observed_ns"], "CASE_STOP_RETURN")
            _require(stop["error"] is None or isinstance(stop["error"], str) and len(stop["error"]) <= 80, "CASE_STOP_ERROR")
        helper = value["helper"]
        if helper is not None:
            _require(type(helper) is dict and set(helper) == {"observed_ns", "state", "identity", "exit_flags",
                "exit_code", "stdout_eof", "stderr_eof", "client_returncode", "error"}, "CASE_HELPER")
            _require(_positive(helper["observed_ns"]) and helper["state"] in ("RUNNING", "UNKNOWN", "EXITED"), "CASE_HELPER_STATE")
            if helper["identity"] is not None:
                _identity(helper["identity"], value["target_execution_id"])
                _require(helper["identity"]["boot_id"] == value["boot_id"], "CASE_HELPER_BOOT")
            _require(type(helper["exit_flags"]) is dict and set(helper["exit_flags"]) == set(_EXIT_FLAGS)
                and all(type(item) is bool for item in helper["exit_flags"].values()), "CASE_HELPER_EXIT_FLAGS")
            for key in ("stdout_eof", "stderr_eof"):
                _require(type(helper[key]) is bool, "CASE_HELPER_EOF")
            for key in ("exit_code", "client_returncode"):
                _require(helper[key] is None or type(helper[key]) is int, "CASE_HELPER_EXIT_CODE")
            _require(helper["error"] is None or isinstance(helper["error"], str) and len(helper["error"]) <= 80, "CASE_HELPER_ERROR")
        helper_exit = _helper_exit(value)
        _require(value["helper_exit_proven"] is helper_exit, "CASE_HELPER_PROOF")
        logs = value["logs"]
        _require(type(logs) is dict and set(logs) == {"items", "dropped"} and type(logs["items"]) is list
                 and len(logs["items"]) <= MAX_LOG_ITEMS and type(logs["dropped"]) is int and logs["dropped"] >= 0
                 and len(_encode(logs["items"])) <= MAX_LOG_BYTES, "CASE_LOG_BOUND")
        for index, item in enumerate(logs["items"], 1):
            _require(type(item) is dict and set(item) == {"seq", "event", "observed_ns", "data"}
                     and item["seq"] == index and _positive(item["observed_ns"])
                     and isinstance(item["event"], str) and len(item["event"]) <= 40
                     and type(item["data"]) is dict and len(_encode(item["data"])) <= 768, "CASE_LOG_EVENT")
        _require(type(value["errors"]) is list and len(value["errors"]) <= 8
                 and all(isinstance(item, str) and len(item) <= 80 for item in value["errors"]), "CASE_ERRORS")
        exercised = _exercised(value)
        if value["status"] == "EXERCISED":
            _require(exercised and not value["errors"] and logs["dropped"] == 0, "CASE_EXERCISE_UNPROVEN")
        if logs["dropped"] or value["errors"]:
            _require(value["status"] == "INCOMPLETE", "CASE_ERRORS_HIDDEN")
        if value["ready_for_finish"]:
            _require(value["status"] != "PENDING", "CASE_FINAL_PENDING")
        return errors
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        return [str(error) if isinstance(error, ValueError) and re.fullmatch(r"CASE_[A-Z_]+", str(error)) else "CASE_MALFORMED"]


def _identity(value, execution):
    _require(type(value) is dict and set(value) == {"boot_id", "unit", "invocation_id", "cgroup"}, "CASE_IDENTITY")
    expected = "lhj-" + hashlib.sha256(execution.encode()).hexdigest() + ".service"
    _require(value["unit"] == expected and isinstance(value["boot_id"], str) and 1 <= len(value["boot_id"]) <= 64
        and isinstance(value["invocation_id"], str) and re.fullmatch(r"[0-9a-f]{32}", value["invocation_id"])
        and isinstance(value["cgroup"], str) and value["cgroup"].startswith("/") and len(value["cgroup"]) <= 512
        and value["cgroup"].endswith("/" + expected) and ".." not in value["cgroup"].split("/"), "CASE_IDENTITY_BINDING")


def _exercised(report):
    trigger, cancel, ledger = report["trigger"], report["cancel"], report["ledger"]
    return bool(trigger and cancel["attempted"] and cancel["returned_ns"] is not None and cancel["error"] is None
        and ledger["cancel_event"] is not None and ledger["no_delivery_after_cancel"] is True
        and any(report["target_execution_id"] + ":helper" in row["delivery_ids"] for row in ledger["delivery_events"])
        and any(row["event"] == "launch_callback_return" and row["data"].get("execution_id") == report["target_execution_id"]
            and row["data"].get("stage") == "helper" and row["data"].get("delivery_attempted") is True for row in report["logs"]["items"])
        and any(stop["identity"] == trigger["identity"] and stop["identity_rechecked"] and stop["nonterminal"]
            and stop["cancel_effective_before_stop"] and stop["observed_ns"] < stop["deadline_ns"]
            and stop["observed_ns"] >= cancel["request_ns"] and stop["returned_ns"] is not None
            and stop["error"] is None and stop["ack"] is True
            for stop in report["stops"]))


def _helper_exit(report):
    helper, trigger, deadline = report["helper"], report["trigger"], report["phase_deadline_ns"]
    return bool(helper and helper["state"] == "EXITED" and helper["identity"] is not None
        and helper["error"] is None and all(helper["exit_flags"].values()) and helper["stdout_eof"]
        and helper["stderr_eof"] and helper["exit_code"] is not None
        and helper["exit_code"] == helper["client_returncode"] and deadline is not None
        and helper["observed_ns"] < deadline and (trigger is None or helper["identity"] == trigger["identity"]))


def encode_report(value):
    _require(not validate_report(value), "CASE_INVALID")
    return _encode(value)


class Case:
    def __init__(self, broker, identity, principal):
        row = broker.state.get("job", identity)
        _require(row is not None and row["principal"] == principal.principal_id and row["request"]["kind"] == "host.inspect"
            and row["request"]["inputs"] == {} and not row["record"]["cancel_requested"], "CASE_ORIGINAL_OWNER")
        broker.policy.authorize(principal, "lh:cancel", request=row["request"], owner=row["principal"])
        self.broker, self.identity, self.principal = broker, identity, principal
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._closed = False
        self._thread = self._manager = self._frozen = None
        self._done = False
        self._cancel_version = 0
        now = _clock()
        self._report = dict(schema=SCHEMA, purpose=PURPOSE, operation_id=identity, request_digest=row["digest"],
            principal_id=principal.principal_id, target_execution_id="job-" + identity + "-preflight",
            phase="preflight", boot_id=now["boot_id"],
            phase_deadline_ns=None, record_deadline_ns=None,
            observed_ns=now["boottime_ns"], status="PENDING", ready_for_finish=False, completion_reason=None,
            trigger=None, cancel=dict(attempted=False, request_ns=None, returned_ns=None, error=None), stops=[],
            helper=None, helper_exit_proven=False, chain_closed=False,
            ledger=dict(cancel_event=None, delivery_events=[], no_delivery_after_cancel=None,
                lifecycle=row["record"]["lifecycle"], outcome=row["record"]["outcome"], evidence=row["record"]["evidence"],
                phase=row["record"]["phase"], cancel_requested=False, reader_delivered=False, leases_retained=True,
                observed_ns=now["boottime_ns"], state_converged=False),
            logs=dict(items=[], dropped=0), errors=[])

    def attach(self, manager):
        _require(getattr(manager, "_q4_observer", False) and getattr(self.broker.runner, "manager", None) is manager
                 and manager._q4_case is None and not manager._runs and self._thread is None, "CASE_MANAGER_BINDING")
        self._manager = manager
        manager._q4_case = self
        self._thread = threading.Thread(target=self._cancel_once, name="q4-owner-cancel", daemon=True)
        self._thread.start()
        return self

    def _log(self, event, data, now):
        # Caller holds only this small in-memory lock, never waits for a broker.
        if self._frozen is not None:
            return
        logs = self._report["logs"]
        item = dict(seq=len(logs["items"]) + 1, event=event, observed_ns=now, data=data)
        if (len(logs["items"]) >= MAX_LOG_ITEMS or len(_encode(data)) > 768
                or len(_encode(logs["items"] + [item])) > MAX_LOG_BYTES):
            logs["dropped"] += 1
            self._report["status"] = "INCOMPLETE"
        else:
            logs["items"].append(item)

    def _fail(self, code):
        with self._lock:
            if self._frozen is None:
                if code not in self._report["errors"] and len(self._report["errors"]) < 8:
                    self._report["errors"].append(code[:80])
                self._report["status"] = "INCOMPLETE"

    def _cancel_once(self):
        self._wake.wait()
        try:
            now = _clock()
            with self._lock:
                trigger = self._report["trigger"]
                if self._closed or trigger is None:
                    return
                if now["boot_id"] != trigger["identity"]["boot_id"] or now["boottime_ns"] >= trigger["record_deadline_ns"]:
                    self._done = True
                    return
                self._report["cancel"].update(attempted=True, request_ns=now["boottime_ns"])
                self._cancel_version += 1
                self._log("cancel_called", {}, now["boottime_ns"])
            error = None
            try:
                self.broker.cancel(self.identity, self._report["request_digest"], {"kind": "job"}, self.principal)
            except Exception as exc:
                error = _error(exc)
            finished = _clock()["boottime_ns"]
            with self._lock:
                self._report["cancel"].update(returned_ns=finished, error=error)
                self._cancel_version += 1
                self._log("cancel_returned", {"error": error}, finished)
                self._done = True
        except Exception as error:
            self._fail(_error(error))
            with self._lock:
                self._done = True

    def _observation(self, part, proof, error=None):
        if part.get("stage") != "helper" or part.get("execution_id") != self._report["target_execution_id"]:
            return
        now = _clock()
        identity = proof.get("identity")
        if identity is not None:
            identity = dict(identity, unit=part["unit"])
            _identity(identity, self._report["target_execution_id"])
        cap = part.get("quota_transport")
        client = part.get("launch")
        current = dict(observed_ns=now["boottime_ns"], state=proof.get("state", "UNKNOWN"), identity=identity,
            exit_flags={key: proof.get(key) is True for key in _EXIT_FLAGS}, exit_code=proof.get("exit_code"),
            stdout_eof=bool(cap and "stdout" in cap.eof), stderr_eof=bool(cap and "stderr" in cap.eof),
            client_returncode=None if client is None else client.poll(), error=error)
        deadline = part.get("phase_deadline_boottime_ns")
        grace = part.get("budget_grant", {}).get("limits", {}).get("terminate_grace_seconds")
        record_deadline = deadline - grace * 1_000_000_000 if _positive(deadline) and _positive(grace) else None
        with self._lock:
            if self._frozen is not None:
                return
            previous = self._report["helper"]
            self._report["helper"] = current
            self._report["helper_exit_proven"] = _helper_exit(self._report)
            if previous is None or any(current[key] != previous[key] for key in ("state", "identity", "error", "exit_flags")):
                self._log("helper_observed", {"state": current["state"], "error": error}, now["boottime_ns"])
            if (not self._closed and self._report["trigger"] is None and current["state"] == "RUNNING"
                    and identity is not None and identity["boot_id"] == now["boot_id"] and record_deadline is not None
                    and now["boottime_ns"] < record_deadline
                    and deadline == self._report["phase_deadline_ns"] and record_deadline == self._report["record_deadline_ns"]):
                self._report["trigger"] = dict(identity=identity, observed_ns=now["boottime_ns"],
                    deadline_ns=deadline, record_deadline_ns=record_deadline)
                self._log("running_trigger", {"deadline_ns": deadline, "record_deadline_ns": record_deadline}, now["boottime_ns"])
                self._wake.set()

    def _stop_before(self, part, facts, rechecked):
        if part.get("stage") != "helper" or part.get("execution_id") != self._report["target_execution_id"]:
            return None
        now = _clock()
        identity = dict(boot_id=part["boot_id"], unit=part["unit"], invocation_id=part["invocation_id"],
                        cgroup=part["quota_parent"]["path"] + "/" + part["unit"])
        _identity(identity, self._report["target_execution_id"])
        with self._lock:
            if self._frozen is not None:
                return None
            if len(self._report["stops"]) >= MAX_STOPS:
                self._report["logs"]["dropped"] += 1
                return None
            cancel = self._report["cancel"]
            same = bool(facts and facts.get("Id") == part["unit"] and facts.get("LoadState") == "loaded"
                and facts.get("InvocationID") == part["invocation_id"] and facts.get("ControlGroup") == identity["cgroup"]
                and now["boot_id"] == part["boot_id"] and rechecked == part["invocation_id"])
            row = dict(identity=identity, observed_ns=now["boottime_ns"], deadline_ns=part["phase_deadline_boottime_ns"],
                nonterminal=bool(facts and not _terminal(facts)), identity_rechecked=same,
                before=copy.deepcopy(facts), rechecked_invocation_id=rechecked,
                stop_requested=part.get("stop_requested") is True,
                cancel_event_set=bool(part.get("cancel_event") and part["cancel_event"].is_set()),
                cancel_effective_before_stop=bool(cancel["attempted"] and now["boottime_ns"] >= cancel["request_ns"]
                    and (part.get("stop_requested") is True or part.get("cancel_event") and part["cancel_event"].is_set())),
                cancel_returned_before_stop=bool(cancel["returned_ns"] is not None and cancel["error"] is None
                    and now["boottime_ns"] >= cancel["returned_ns"]), ack=None, returned_ns=None, error=None)
            self._report["stops"].append(row)
            self._log("stop_delivered", {"attempt": len(self._report["stops"]), "nonterminal": row["nonterminal"]}, now["boottime_ns"])
            return row

    def _stop_after(self, row, response, error):
        if row is None:
            return
        now = _clock()["boottime_ns"]
        with self._lock:
            if self._frozen is None:
                row.update(ack=None if response is None else response.returncode == 0, returned_ns=now, error=error)
                self._log("stop_returned", {"ack": row["ack"], "error": error}, now)

    def _delivery(self, event, execution, stage, *, attempted=None, returned=None):
        if execution not in {"job-" + self.identity + "-" + phase for phase in ("preflight", "business", "evidence")}:
            return
        now = _clock()["boottime_ns"]
        with self._lock:
            self._log(event, dict(execution_id=execution, stage=stage, delivery_attempted=attempted, returned=returned), now)

    def poll(self):
        if self._frozen is not None:
            return self.snapshot()
        try:
            now = _clock()
            with self._lock:
                version = self._cancel_version
            with self.broker.state.transaction() as tx:
                row = self.broker.state.get("job", self.identity, tx)
                _require(row is not None and row["digest"] == self._report["request_digest"]
                    and row["principal"] == self.principal.principal_id, "CASE_LEDGER_CHANGED")
                events = tx.execute("SELECT seq,kind,observed_at,data_json FROM events WHERE namespace='job' AND id=? "
                    "AND kind IN ('CANCEL_REQUESTED','MANAGER_DELIVERY_INTENT') ORDER BY seq LIMIT 15", (self.identity,)).fetchall()
                _require(len(events) < 15, "CASE_LEDGER_EVENT_BOUND")
                leases = tx.execute("SELECT COUNT(*) FROM leases WHERE owner=?", (self.identity,)).fetchone()[0]
                from local_hand_jobs import budget, quota_binding
                grant = None
                if "preflight" in row["record"].get("quota_preparations", {}):
                    grant = quota_binding.original(tx, row, "preflight", "QUOTA_PREPARATION", "quota_preparations")["budget"]
                    _require(grant == budget.stored_grant(row, "preflight"), "CASE_ORIGINAL_BUDGET")
                elif row["record"].get("execution_budget") is not None:
                    grant = budget.stored_grant(row, "preflight")
                deadline = record_deadline = None
                if grant is not None:
                    _require(grant["boot_id"] == self._report["boot_id"], "CASE_BUDGET_BOOT")
                    grace = grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS
                    deadline = budget.phase_deadline_ns(grant) - grace
                    record_deadline = deadline - grace
                    _require(record_deadline > 0, "CASE_RECORD_WINDOW")
            cancellations, deliveries = [], []
            ledger_observed_ns = _clock()["boottime_ns"]
            for item in events:
                data = json.loads(item["data_json"])
                if item["kind"] == "CANCEL_REQUESTED":
                    cancellations.append(dict(seq=item["seq"], observed_at_hex=float(item["observed_at"]).hex(), cancel_requested=data.get("cancel_requested")))
                else:
                    deliveries.append(dict(seq=item["seq"], delivery_ids=data.get("delivery_intents")))
            _require(len(cancellations) <= 1 and len(deliveries) <= 12, "CASE_LEDGER_DUPLICATE")
            event = cancellations[0] if cancellations else None
            record = row["record"]
            ledger = dict(cancel_event=event, delivery_events=deliveries,
                no_delivery_after_cancel=None if event is None else all(item["seq"] < event["seq"] for item in deliveries),
                **{key: record[key] for key in ("lifecycle", "outcome", "evidence", "phase", "cancel_requested")},
                reader_delivered=any(self._report["target_execution_id"] + ":result_reader" in item["delivery_ids"] for item in deliveries),
                leases_retained=leases > 0, observed_ns=ledger_observed_ns, state_converged=False)
            with self._lock:
                if version != self._cancel_version:
                    return copy.deepcopy(self._report)  # Retry observation next tick, never freeze a mixed snapshot.
                now = _clock()
                report = self._report
                if report["phase_deadline_ns"] not in (None, deadline) or report["record_deadline_ns"] not in (None, record_deadline):
                    raise ValueError("CASE_ORIGINAL_DEADLINE_CHANGED")
                report.update(observed_ns=now["boottime_ns"], ledger=ledger,
                              phase_deadline_ns=deadline, record_deadline_ns=record_deadline)
                helper = report["helper"]
                report["helper_exit_proven"] = _helper_exit(report)
                trigger, cancel = report["trigger"], report["cancel"]
                reason = None
                if report["helper_exit_proven"]:
                    reason = "HELPER_EXIT" if cancel["attempted"] else "NATURAL_END"
                elif record_deadline is not None and (now["boot_id"] != report["boot_id"] or now["boottime_ns"] >= record_deadline):
                    reason = "RECORD_DEADLINE"
                elif self._done and cancel["error"] is not None and ledger["cancel_event"] is None:
                    reason = "CANCEL_FAILED"
                elif not trigger and record["lifecycle"] == "TERMINAL":
                    reason = "NATURAL_END"
                elif self._closed:
                    reason = "CLOSED"
                if report["errors"] or report["logs"]["dropped"] or cancel["error"] is not None:
                    report["status"] = "INCOMPLETE"
                elif _exercised(report):
                    report["status"] = "EXERCISED"
                else:
                    report["status"] = "NOT_EXERCISED" if reason else "PENDING"
                if reason and (not cancel["attempted"] or self._done) and all(stop["returned_ns"] is not None for stop in report["stops"]):
                    self._closed = True
                    self._wake.set()
                    report.update(ready_for_finish=True, completion_reason=reason)
                    self._frozen = copy.deepcopy(report)
        except Exception as error:
            self._fail(_error(error))
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            result = copy.deepcopy(self._frozen or self._report)
        _require(len(_encode(result)) <= MAX_REPORT_BYTES, "CASE_SIZE")
        return result

    def close(self, timeout=1):
        _require(type(timeout) in (int, float) and 0 <= timeout <= 1, "CASE_CLOSE_BOUND")
        with self._lock:
            self._closed = True
            self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
        return self.snapshot()


def observe_manager(core):
    """Wrap exactly the installed core; all management/inspection calls pass through."""
    from local_hand_jobs.runner import _SystemdExecutionCore
    _require(core is _SystemdExecutionCore, "CASE_REAL_CORE_REQUIRED")

    class Observed(core):
        _q4_observer = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._q4_case = None
            self._q4_local = threading.local()

        def _record(self, function, *args, **kwargs):
            try:
                return function(*args, **kwargs)
            except Exception as error:
                # Recording failure never replaces the original core action or
                # its error. The case is incomplete instead of changing control.
                self._q4_case._fail(_error(error))
                return None

        def set_start_guard(self, callback):
            def guard(execution_id, launch, **options):
                stage = options.get("stage")
                def recorded():
                    case = self._q4_case
                    if case is not None:
                        self._record(case._delivery, "launch_callback_enter", execution_id, stage)
                    response = None
                    try:
                        response = launch()
                        return response
                    finally:
                        if case is not None:
                            unit = "lhj-" + hashlib.sha256(execution_id.encode()).hexdigest() + ".service"
                            part = self._runs.get(unit, {}).get(stage) if stage is not None else None
                            self._record(case._delivery, "launch_callback_return", execution_id, stage,
                                attempted=part.get("delivery_attempted") if part else None, returned=response is not None)
                return callback(execution_id, recorded, **options)
            return super().set_start_guard(guard)

        def _inspect_unit(self, part):
            self._q4_local.part = part
            self._q4_local.facts = None
            self._q4_local.rechecked = None
            try:
                proof = super()._inspect_unit(part)
            except Exception as error:
                if self._q4_case is not None:
                    self._record(self._q4_case._observation, part, {"state": "UNKNOWN"}, _error(error))
                raise
            else:
                if self._q4_case is not None:
                    self._record(self._q4_case._observation, part, proof)
                return proof
            finally:
                self._q4_local.part = None

        def _command(self, *args, **kwargs):
            part = getattr(self._q4_local, "part", None)
            case, stop = self._q4_case, None
            if case is not None and part is not None and args == ("stop", part["unit"]):
                stop = self._record(case._stop_before, part, self._q4_local.facts, self._q4_local.rechecked)
            try:
                response = super()._command(*args, **kwargs)
            except Exception as error:
                if case is not None:
                    self._record(case._stop_after, stop, None, _error(error))
                raise
            if case is not None:
                self._record(case._stop_after, stop, response, None)
            if part is not None and args[:2] == ("show", part["unit"]) and response.returncode == 0:
                try:
                    if "--value" in args and "--property=InvocationID" in args:
                        self._q4_local.rechecked = response.stdout.decode().strip()
                    elif len(response.stdout) <= 65536:
                        pairs = [line.split("=", 1) for line in response.stdout.decode().splitlines()]
                        values = dict(pairs)
                        if len(values) == len(pairs) and all(key in values and len(values[key]) <= 512 for key in _SHOW_FIELDS):
                            self._q4_local.facts = {key: values[key] for key in _SHOW_FIELDS}
                except (UnicodeError, ValueError, TypeError) as error:
                    if case is not None:
                        case._fail(_error(error))
            return response

    return Observed
