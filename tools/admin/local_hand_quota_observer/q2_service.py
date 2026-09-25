"""Q2 supervised-worker service core, not a socket listener or unit launcher.

The adapter supplies independently attested peers and fixed supervised dispatch.
No client-controlled path, command, identity report or quota override enters it.
All persistence/callback work runs under one finite external worker envelope.
"""
from __future__ import annotations

from dataclasses import dataclass

from local_hand_jobs import quota_contract as q, quota_grant as g, quota_client
from .q2_journal import peer_binding, invocation, closed_fence


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str
    receipt: bytes | None
    delivered: bool


def _clock():
    return {"boot_id": quota_client._boot_id(), "ns": quota_client._boottime_ns()}


def _resources(grant):
    data = grant.as_dict()
    result = {("slot", data["request"]["slot_ref"])}
    for root in data["roots"]:
        result.add(("inode", root["device"], root["inode"]))
        result.add(("domain", root["filesystem_uuid"], root["project_id"]))
    return result


class Service:
    def __init__(self, journal, *, clock=_clock):
        self.journal = journal
        self.clock = clock
        self.last_ns = 0

    def _now(self, grant=None):
        value = self.clock()
        q._keys(value, {"boot_id", "ns"})
        q.require(value["boot_id"] == self.journal.capacity["boot_id"], "BOOT_BINDING")
        now = q.integer(value["ns"], self.last_ns)
        self.last_ns = now
        if grant is not None:
            data = grant.as_dict()
            q.require(data["management"]["issued_ns"] <= now < data["request"]["deadline_ns"], "DEADLINE")
        return now

    def _grant(self, request):
        request = q.decode_request(request.wire)
        grant = self.journal.grants.get(request.as_dict()["request_id"])
        q.require(grant is not None and grant.request == request, "REQUEST_NOT_ADMITTED")
        return grant

    def _admit_new(self, grant, states, now):
        data = grant.as_dict()
        allocation = data["allocation"]
        prior = []
        occupied = []
        for key, state in states.items():
            if state["status"] == "READY":
                continue
            previous = self.journal.grants[key]
            old = previous.as_dict()
            q.require(state["status"] == "CLOSED", "PRIOR_EXIT_UNPROVEN")
            q.require(state["closed"]["closed_ns"] <= now, "CLOCK_REGRESSION")
            occupied.append(previous)
            same_operation = old["allocation"]["operation_id"] == allocation["operation_id"]
            q.require(old["request"]["execution_id"] != data["request"]["execution_id"], "PHASE_CONSUMED")
            overlap = _resources(grant) & _resources(previous)
            if overlap:
                q.require(same_operation and all(old["request"][k] == data["request"][k]
                    for k in ("generation", "installation_digest", "manifest_digest")), "RESOURCE_CONSUMED")
                if old["allocation"]["allocation_id"] != allocation["allocation_id"]:
                    # Only a declared evidence retained_store can reuse an old
                    # root/domain; fresh roots cannot acquire old charging domains.
                    retained = [r for r in data["roots"] if r["role"] == "retained_store"]
                    allowed = set()
                    if retained:
                        root = retained[0]
                        q.require(any(all(root[k] == r[k] for k in root if k != "role") for r in old["roots"]), "RETAINED_BINDING")
                        allowed = {("inode", root["device"], root["inode"]), ("domain", root["filesystem_uuid"], root["project_id"])}
                    q.require(overlap <= allowed, "RESOURCE_CONSUMED")
                    q.require(not any(("domain", r["filesystem_uuid"], r["project_id"]) in overlap
                                      for r in data["roots"] if r["role"] != "retained_store"), "RESOURCE_CONSUMED")
            if same_operation:
                prior.append(key)
                if old["allocation"]["namespace"] == allocation["namespace"] and old["allocation"]["record_id"] == allocation["record_id"]:
                    q.require(all(old["budget"][k] == data["budget"][k] for k in (
                        "boot_id", "budget_digest", "started_boottime_ns", "deadline_boottime_ns", "limits")), "ORIGINAL_BUDGET_CHANGED")
        q.require(set(prior) == set(data["predecessors"]), "PREDECESSOR_BINDING")
        if data["request"]["phase"] == "business":
            q.require(len(prior) == 1, "BUSINESS_PREDECESSOR")
            old = self.journal.grants[prior[0]].as_dict()
            q.require(old["request"]["phase"] == "preflight"
                      and old["allocation"]["allocation_id"] == allocation["allocation_id"]
                      and old["roots"] == data["roots"], "BUSINESS_ALLOCATION")
        g.check_capacity(self.journal.capacity, [*occupied, grant])

    def handle(self, raw, *, peer, expected_peer, dispatch):
        """Process exactly one admitted request. Repeats cannot call dispatch.

        peer comes from the accepted connection + independent OS inspection;
        expected_peer comes from the original durable broker start attestation.
        Neither is parsed from raw. dispatch MUST enforce the supplied grant's
        fixed limits and report invocation before returning native observations.
        """
        request = q.decode_request(raw)
        grant = self._grant(request)
        peer_binding(peer, grant)
        peer_binding(expected_peer, grant)
        q.require(peer == expected_peer, "PEER_ATTESTATION")
        self._now(grant)
        with self.journal.locked():
            states = self.journal.scan()
            now = self._now(grant)
            key = request.as_dict()["request_id"]
            state = states[key]
            if state["status"] != "READY":
                q.require(state["intent"]["peer"] == peer, "ORIGINAL_PEER_CHANGED")
                if "result" not in state:
                    return Outcome("UNKNOWN", None, False)
                item = state["result"]
                receipt = q.decode_receipt(q._canonical(item["receipt"], q.RESPONSE_LIMIT), request,
                    grant.as_dict()["roots"], now_ns=now)
                return Outcome(receipt.as_dict()["status"], receipt.wire, False)
            self._admit_new(grant, states, now)
            self.journal.append(key, "INTENT", {"request_digest": request.digest, "peer": peer, "reserved_ns": now})
            # An fsync timeout/exception cannot cause a later replay. If it
            # completed late, the intent remains consumed and dispatch is denied.
            self._now(grant)
            data = grant.as_dict()
            query_deadline = min(data["request"]["deadline_ns"] - data["management"]["receive_ns"] - data["management"]["stop_ns"],
                data["management"]["issued_ns"] + data["management"]["stages"]["admission"]["runtime_ns"]
                + data["management"]["stages"]["query"]["runtime_ns"])
            q.require(self._now(grant) < query_deadline, "QUERY_DEADLINE")
            recorded = None

            def remember(value):
                nonlocal recorded
                self._now(grant)
                q.require(recorded is None, "INVOCATION_ALREADY_RECORDED")
                invocation(value, grant)
                self.journal.append(key, "INVOCATION", value)
                recorded = q._load(q._canonical(value, 8192), 8192, 5)
                self._now(grant)

            response = dispatch(grant, query_deadline, remember)
            received = self._now(grant)
            receipt = q.decode_receipt(response, request, data["roots"], now_ns=received)
            facts = receipt.as_dict()
            if facts["query"] is not None:
                q.require(recorded is not None and facts["query"] == {k: recorded[k] for k in facts["query"]}, "QUERY_BINDING")
            if facts["status"] == "OBSERVED":
                q.require(facts["started_ns"] >= now and facts["finished_ns"] < query_deadline, "QUERY_DEADLINE")
            self.journal.append(key, "RESULT", {"receipt": facts, "received_ns": received})
            self._now(grant)
            return Outcome(facts["status"], receipt.wire, True)

    def close_phase(self, request, fence):
        """Persist trusted broker/OS exit proof, without refund or new query.

        Only the administrative adapter may call this, after independently
        verifying original stage identities. Wire observe has no close action.
        """
        grant = self._grant(request)
        now = self._now()
        with self.journal.locked():
            state = self.journal.scan()[request.as_dict()["request_id"]]
            if state["status"] == "CLOSED":
                q.require(state["closed"] == fence, "PHASE_FENCE_CONFLICT")
                return
            q.require(state["status"] == "RESULT" and state["result"]["receipt"]["status"] == "OBSERVED", "PHASE_EXIT_UNPROVEN")
            item = state["result"]
            receipt = q.decode_receipt(q._canonical(item["receipt"], q.RESPONSE_LIMIT), grant.request,
                grant.as_dict()["roots"], now_ns=item["received_ns"])
            closed_fence(fence, grant, receipt, state["intent"]["peer"])
            q.require(item["received_ns"] <= fence["closed_ns"] <= now, "PHASE_FENCE_TIME")
            self.journal.append(request.as_dict()["request_id"], "CLOSED", fence)
