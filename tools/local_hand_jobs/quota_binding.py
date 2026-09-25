"""Internal Q2 broker binding and bounded bootstrap receipt transport.

These APIs have no MCP/CLI operation. The trusted installation prepares grants
from an already committed phase reservation; receipt claims alone grant nothing.
"""
from __future__ import annotations

import hashlib
import json
import struct

from . import quota_contract as q, quota_grant as g, budget
from .contract import JobError


def execution(grant):
    data = grant.as_dict()
    return {"execution_id": data["request"]["execution_id"], "phase": data["request"]["phase"],
        "operation_id": data["allocation"]["operation_id"], "budget_grant": data["budget"],
        "budgets": data["budget"]["limits"], "quota_grant_digest": grant.digest,
        "phase_deadline_boottime_ns": budget.phase_deadline_ns(data["budget"]) -
            data["budget"]["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS}


def validate_observation(value, grant, *, now_ns):
    q._keys(value, {"schema", "grant_digest", "request_digest", "receipt_digest", "domain_hard_bytes", "receipt"})
    receipt = q.decode_receipt(q._canonical(value["receipt"], q.RESPONSE_LIMIT), grant.request,
                              grant.as_dict()["roots"], now_ns=now_ns)
    q.require(value["schema"] == "local-hand-bootstrap-quota/v1" and value["grant_digest"] == grant.digest
        and value["request_digest"] == grant.request.digest and value["receipt_digest"] == hashlib.sha256(receipt.wire).hexdigest()
        and type(value["domain_hard_bytes"]) is int and value["domain_hard_bytes"] == receipt.domain_hard_bytes
        and receipt.as_dict()["status"] == "OBSERVED"
        and receipt.as_dict()["query"]["cgroup"] == grant.as_dict()["query_parent"]["path"] + "/" + grant.request.query_unit,
        "BOOTSTRAP_OBSERVATION")
    g.check_execution(grant, execution(grant), grant.as_dict()["allocation"], now_ns=now_ns)
    return q._load(q._canonical(value, q.RESPONSE_LIMIT), q.RESPONSE_LIMIT, 8)


def frame(value):
    raw = q._canonical(value, q.RESPONSE_LIMIT)
    return struct.pack("!I", len(raw)) + raw


class Pipe:
    """EOF is supplied only by a zero-byte OS read, never by closing a pipe."""
    def __init__(self):
        self.raw = bytearray()
        self.eof = False
        self.error = False

    def feed(self, data):
        if self.eof or len(self.raw) + len(data) > q.RESPONSE_LIMIT + 4:
            self.error = True
            return
        if not data:
            self.eof = True
        self.raw.extend(data)

    def finish(self, grant, *, now_ns):
        q.require(self.eof and not self.error and len(self.raw) >= 4, "RECEIPT_EOF")
        size = struct.unpack("!I", self.raw[:4])[0]
        q.require(0 < size <= q.RESPONSE_LIMIT and len(self.raw) == size + 4, "RECEIPT_FRAME")
        return validate_observation(q._load(bytes(self.raw[4:]), q.RESPONSE_LIMIT, 8), grant, now_ns=now_ns)


def recorded(tx, row, phase, kind):
    """A lost snapshot does not make an already committed intent reusable."""
    events = tx.execute("SELECT data_json FROM events WHERE namespace=? AND id=? AND kind=?",
                        (row["namespace"], row["id"], kind)).fetchall()
    return any(json.loads(event["data_json"]).get("quota_event_phase") == phase for event in events)


def original(tx, row, phase, kind, field):
    """Mutable snapshot must equal its unique immutable event, without repair."""
    events = tx.execute("SELECT data_json FROM events WHERE namespace=? AND id=? AND kind=? ORDER BY seq",
                        (row["namespace"], row["id"], kind)).fetchall()
    data = [json.loads(event["data_json"]) for event in events]
    values = [item.get(field, {}).get(phase) for item in data if item.get("quota_event_phase") == phase]
    values = [value for value in values if value is not None and value.get("phase") == phase]
    value = row["record"].get(field, {}).get(phase)
    if len(values) != 1 or values[0] != value:
        raise JobError("IO_UNCERTAIN", "Original quota binding is missing or changed")
    return value


def admission_version(tx, row):
    kind = "ADMISSION_BOUND" if row["namespace"] == "job" else "OBSERVATION_BOUND"
    event = tx.execute("SELECT data_json FROM events WHERE namespace=? AND id=? AND kind=? ORDER BY seq LIMIT 1",
                       (row["namespace"], row["id"], kind)).fetchone()
    initial = json.loads(event["data_json"]).get("quota_binding_version") if event else None
    current = row["record"].get("quota_binding_version")
    if initial != current or (current is not None and (type(current) is not int or current != 1)):
        raise JobError("IO_UNCERTAIN", "Quota admission version differs from its original event")
    return current


def selected(tx, row, phase, *, session, now_ns):
    q.require(admission_version(tx, row) == 1, "QUOTA_ADMISSION")
    prep = original(tx, row, phase, "QUOTA_PREPARATION", "quota_preparations")
    q.require(prep["session"] == session, "QUOTA_RECOVERY_BARRIER")
    item = original(tx, row, phase, "QUOTA_OBSERVATION_BOUND", "quota_bindings")
    grant = g.decode_grant(q._canonical(item["grant"], g.GRANT_LIMIT))
    q.require(item["grant_digest"] == grant.digest and grant.as_dict()["allocation"] == prep["allocation"]
              and grant.as_dict()["budget"] == prep["budget"], "QUOTA_PREPARATION_CHANGED")
    if now_ns is not None:
        g.check_execution(grant, execution(grant), prep["allocation"], now_ns=now_ns)
    return grant
