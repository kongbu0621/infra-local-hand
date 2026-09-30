"""One fixed test-only cancellation case over the existing management bridge.

The ordinary resident owns the real broker cancellation. This administrator
only binds and starts the original preflight, observes the case transcript and
closes its own original management clients. It never closes the quota phase,
releases a reservation, sends a cancellation command or provisions a fixture.
"""
from __future__ import annotations

import copy
import time

from local_hand_jobs import budget, quota_contract as q
from admin.local_hand_quota_observer.q2_coordinator import (
    Coordinator as NormalCoordinator, SNAPSHOT_POLLS, MANAGEMENT_POLLS,
    MANAGEMENT_STOP_POLLS,
)
from admin.local_hand_quota_observer.q2_journal import Journal
from admin.local_hand_quota_observer.systemd_runtime import boottime_ns

SNAPSHOT_SCHEMA = "local-hand-q4-cancel-snapshot/v1"
RESULT_SCHEMA = "local-hand-q4-cancel-coordinator/v1"


class Coordinator(NormalCoordinator):
    def __init__(self, installation, envelope, record, client, *, report, request, principal_id):
        super().__init__(installation, envelope, record, client)
        self.report = report
        self.request = copy.deepcopy(request)
        self.principal_id = principal_id
        self.last_case = None
        self.last_phase = None

    def _accept(self, response):
        q._keys(response, {"schema", "phase", "case"})
        q.require(response["schema"] == SNAPSHOT_SCHEMA, "CANCEL_SNAPSHOT_SCHEMA")
        phase, case = response["phase"], response["case"]
        q._keys(phase, {"preparation", "observation", "pending", "closed"})
        data = self.config.active().as_dict()
        prep = phase["preparation"]
        q.require(prep["allocation"] == data["allocation"] and prep["budget"] == data["budget"]
                  and prep["phase"] == data["request"]["phase"] == "preflight",
                  "COORDINATOR_PREPARATION")
        q.require(phase["closed"] is None, "CANCEL_UNEXPECTED_PHASE_CLOSURE")
        q.require(not self.report.validate_report(case), "CANCEL_CASE_REPORT")
        q.require(len(self.report.encode_report(case)) <= 16384, "CANCEL_CASE_REPORT_LIMIT")
        q.require(case.get("operation_id") == data["allocation"]["operation_id"]
                  == self.request["operation_id"]
                  and case.get("target_execution_id") == data["allocation"]["execution_id"]
                  and case.get("request_digest") == self.request["request_digest"]
                  and case.get("principal_id") == self.principal_id
                  and case.get("boot_id") == data["budget"]["boot_id"]
                  and case.get("phase") == "preflight"
                  and case.get("chain_closed") is False, "CANCEL_CASE_BINDING")
        deadline = case.get("phase_deadline_ns")
        cutoff = case.get("record_deadline_ns")
        grace = data["budget"]["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS
        q.require((deadline is None and cutoff is None) or
                  (deadline == budget.phase_deadline_ns(data["budget"]) - grace
                   and cutoff == deadline - grace),
                  "CANCEL_CASE_ORIGINAL_DEADLINE")
        if self.last_case is not None and self.last_case.get("phase_deadline_ns") is not None:
            q.require(deadline == self.last_case["phase_deadline_ns"], "CANCEL_CASE_DEADLINE_LOST")
        if self.last_case is not None and self.last_case["ready_for_finish"]:
            q.require(case == self.last_case, "CANCEL_FROZEN_CASE_CHANGED")
        self.last_case, self.last_phase = copy.deepcopy(case), copy.deepcopy(phase)
        return phase

    def _snapshot(self):
        self._pump()
        return self._accept(self.client.call("snapshot"))

    def run(self):
        q.require(not self.used, "COORDINATOR_CONSUMED")
        self.used = True
        journal = None
        try:
            config = self.config
            data, grant = config.data(), config.active()
            value = grant.as_dict()
            snapshot = self._snapshot()
            q.require(all(snapshot[key] is None for key in ("observation", "pending", "closed"))
                      and self.last_case["ready_for_finish"] is False, "COORDINATOR_ALREADY_STARTED")
            self._event("PREPARATION", snapshot)
            journal = Journal(data["journal"]["path"], data["journal"]["pin"], data["capacity"],
                              list(config.grants().values()))
            with journal.locked():
                state = journal.scan()[grant.request.as_dict()["request_id"]]
                q.require(state["status"] == "READY", "COORDINATOR_REQUEST_CONSUMED")
            self.management.begin()
            self._wait_socket(data["service"]["control_path"], 0, 0o600)
            self.management.launch("admission")
            self._wait_socket(value["endpoint"]["path"], value["endpoint"]["gid"], 0o660)
            self.management.poll()
            q.require(all(part["invocation"] is not None for part in self.management.runs.values()),
                      "MANAGEMENT_IDENTITY_PENDING")
            self._event("ENDPOINT_READY", dict(config_digest=config.digest))
            self._accept(self.client.call("bind", value))
            self._accept(self.client.call("start"))
            q.require(self.last_case["record_deadline_ns"] is not None,
                      "CANCEL_CASE_ORIGINAL_DEADLINE")
            self._event("ORDINARY_START", dict(grant_digest=grant.digest))
            management = None
            next_snapshot = next_management = 0
            snapshot_polls = management_polls = stop_polls = 0
            while not self.last_case["ready_for_finish"] or management is None:
                self._pump()
                if management is None:
                    stopped = all(part.get("stop_ok") and part.get("after")
                                  for part in self.management.runs.values())
                    done = None
                    if stopped:
                        if all(part["capture"].done for part in self.management.runs.values()):
                            done = self.management.finish()
                    elif boottime_ns() >= next_management:
                        stopping = any(part.get("stop_attempted") and part.get("after") is None
                                       for part in self.management.runs.values())
                        if stopping:
                            q.require(stop_polls < MANAGEMENT_STOP_POLLS, "MANAGEMENT_STOP_POLL_LIMIT")
                            stop_polls += 1
                        else:
                            q.require(management_polls < MANAGEMENT_POLLS, "MANAGEMENT_POLL_LIMIT")
                            management_polls += 1
                        if self.management.poll() is not None:
                            done = self.management.finish()
                        else:
                            now = boottime_ns()
                            stopping = any(part.get("stop_attempted") and part.get("after") is None
                                           for part in self.management.runs.values())
                            interval = 10_000_000 if stopping else max(10_000_000,
                                (self.management.end - now) // (MANAGEMENT_POLLS + 1 - management_polls))
                            next_management = now + interval
                    if done is not None:
                        management = done
                        self.management_closed = True
                        self._event("MANAGEMENT_CLOSED", management)
                if not self.last_case["ready_for_finish"] and boottime_ns() >= next_snapshot:
                    q.require(snapshot_polls < SNAPSHOT_POLLS, "COORDINATOR_SNAPSHOT_LIMIT")
                    self._snapshot()
                    snapshot_polls += 1
                    now = boottime_ns()
                    # Use the resident's original, earlier recording cutoff so
                    # a final observation does not consume the output margin.
                    cutoff = self.last_case.get("record_deadline_ns")
                    poll_end = self.end if cutoff is None else min(self.end, q.integer(cutoff, 1))
                    next_snapshot = now + max(10_000_000,
                        (poll_end - now) // max(1, SNAPSHOT_POLLS - snapshot_polls))
                time.sleep(0.01)
            self._event("CASE_RECORDED", self.last_case)
            return dict(schema=RESULT_SCHEMA, status="CANCEL_CASE_RECORDED", phase="preflight",
                grant_digest=grant.digest, case=copy.deepcopy(self.last_case), management=management,
                events=self.events, ordinary_phase_closed=False, independent_ordinary_cleanup_required=True,
                q3_accepted=False, production_supported=False)
        except BaseException:
            self.failed = True
            raise
        finally:
            if journal is not None:
                journal.close()
