"""Pure Q2 protected declarations and permanent management accounting.

These are trusted installation/broker inputs, never wire-authorized settings.
Validation proves consistency, not provenance, filesystem capacity or OS limits.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from . import bootstrap_roots, budget
from .contract import JobError
from . import quota_contract as q

GRANT_LIMIT = 32768
MAX_GRANTS = 32
CELL_BYTES = 131072
BASE_BYTES = 131072
BASE_INODES = 4
STAGES = ("admission", "query", "collector")
_STAGE_KEYS = {"cpu_ns", "memory_bytes", "pids", "output_bytes", "runtime_ns"}
_MANAGEMENT_KEYS = {"id", "capacity_digest", "issued_ns", "receive_ns", "stop_ns",
                    "storage_bytes", "storage_inodes", "stages"}


def digest(value):
    return hashlib.sha256(q._canonical(value, GRANT_LIMIT)).hexdigest()


def _rounded(value):
    return ((value + 4095) // 4096) * 4096


def root_paths(allocation):
    result = dict(allocation["roots"])
    if allocation["retained_paths"]:
        result["retained_store"] = allocation["retained_paths"][0]
    return result


@dataclass(frozen=True, slots=True)
class Grant:
    wire: bytes

    @property
    def digest(self):
        return hashlib.sha256(self.wire).hexdigest()

    def as_dict(self):
        return json.loads(self.wire)

    @property
    def request(self):
        return q.decode_request(q._canonical(dict(self.as_dict()["request"],
            observation_grant_digest=self.digest), q.REQUEST_LIMIT))


def decode_grant(raw):
    value = q._load(raw, GRANT_LIMIT, 10)
    q._keys(value, {"schema", "request", "allocation", "budget", "endpoint",
                    "query_parent", "management_parent", "roots", "management", "predecessors"})
    q.require(value["schema"] == "local-hand-quota-grant/v1", "GRANT_SCHEMA")
    q.require(type(value["request"]) is dict
              and "observation_grant_digest" not in value["request"], "GRANT_REQUEST")
    request = q.decode_request(q._canonical(dict(value["request"],
        observation_grant_digest="0" * 64), q.REQUEST_LIMIT)).as_dict()
    try:
        allocation = bootstrap_roots.validate_grant(value["allocation"],
            execution_id=request["execution_id"], phase=request["phase"])
        phase = value["budget"]
        budget.validate_grant(phase, execution_id=request["execution_id"], phase=request["phase"],
            namespace=allocation["namespace"], record_id=allocation["record_id"],
            operation_id=allocation["operation_id"])
        last_ns = budget.phase_deadline_ns(phase) - phase["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS
    except (JobError, KeyError, TypeError, ValueError):
        raise q.QuotaError("ORIGINAL_GRANT") from None
    q.require(request["boot_id"] == phase["boot_id"]
              and request["allocation_digest"] == allocation["allocation_id"]
              and request["slot_ref"] == allocation["slot_id"]
              and request["deadline_ns"] <= last_ns, "ORIGINAL_BINDING")
    roots = q.validate_expected_roots(value["roots"], request["phase"])
    paths = root_paths(allocation)
    q.require({root["role"] for root in roots} == paths.keys(), "ROOT_BINDING")
    for path in paths.values():
        q.canonical_path(path)
    domains = {}
    for root in roots:
        identity = allocation["paths"][paths[root["role"]]]
        q.require(all(identity[key] == root[key] for key in ("device", "inode", "uid")), "ROOT_BINDING")
        limit = phase["limits"]["temporary_bytes" if root["role"] == "temporary" else "reservation_bytes"]
        q.require(root["hard_bytes"] <= limit, "ROOT_BUDGET")
        domains[root["filesystem_uuid"], root["project_id"]] = root["hard_bytes"]
    q.require(sum(domains.values()) <= phase["limits"]["reservation_bytes"], "ROOT_BUDGET")
    endpoint = value["endpoint"]
    q._keys(endpoint, {"path", "uid", "gid", "boot_id"})
    q.require(len(q.canonical_path(endpoint["path"]).encode()) <= 107, "ENDPOINT_LENGTH")
    q.integer(endpoint["uid"], 0, 2**32 - 2)
    q.integer(endpoint["gid"], 0, 2**32 - 2)
    q.require(endpoint["boot_id"] == request["boot_id"], "BOOT_BINDING")
    for parent in (value["query_parent"], value["management_parent"]):
        q._keys(parent, {"path", "device", "inode"})
        q.canonical_path(parent["path"])
        q.integer(parent["device"])
        q.integer(parent["inode"], 1)
    management = value["management"]
    q._keys(management, _MANAGEMENT_KEYS)
    q.match(management["id"], r"[0-9a-f]{32}")
    q.match(management["capacity_digest"], r"[0-9a-f]{64}")
    issued = q.integer(management["issued_ns"], phase["reserved_boottime_ns"])
    for key in ("receive_ns", "stop_ns", "storage_bytes", "storage_inodes"):
        q.integer(management[key], 1)
    q._keys(management["stages"], set(STAGES))
    for item in management["stages"].values():
        q._keys(item, _STAGE_KEYS)
        for key in _STAGE_KEYS:
            q.integer(item[key], 1)
    wall = sum(item["runtime_ns"] for item in management["stages"].values())
    q.require(issued + wall + management["receive_ns"] + management["stop_ns"]
              <= request["deadline_ns"], "MANAGEMENT_DEADLINE")
    q.require(management["stages"]["collector"]["output_bytes"] >= q.RESPONSE_LIMIT,
              "RECEIPT_BUDGET")
    # One retained cell plus finite stdout/stderr files and directory metadata.
    minimum = CELL_BYTES + sum(_rounded(stage["output_bytes"]) + 8192
                               for stage in management["stages"].values())
    q.require(management["storage_bytes"] >= minimum and management["storage_inodes"] >= 7,
              "MANAGEMENT_STORAGE")
    predecessors = value["predecessors"]
    q.require(type(predecessors) is list and len(predecessors) < MAX_GRANTS, "PREDECESSORS")
    for previous in predecessors:
        q.match(previous, r"[0-9a-f]{32}")
    q.require(len(set(predecessors)) == len(predecessors)
              and request["request_id"] not in predecessors, "PREDECESSORS")
    if request["phase"] in ("business", "evidence"):
        q.require(bool(predecessors), "PREDECESSORS")
    return Grant(q._canonical(value, GRANT_LIMIT))


def totals(grant):
    management = grant.as_dict()["management"]
    return {"storage_bytes": management["storage_bytes"], "storage_inodes": management["storage_inodes"],
            **{key: q.integer(sum(stage[key] for stage in management["stages"].values()))
               for key in ("cpu_ns", "memory_bytes", "pids", "output_bytes")}}


def decode_capacity(raw):
    value = q._load(raw, GRANT_LIMIT, 6)
    q._keys(value, {"schema", "boot_id", "epoch", "authority_digest", "domains",
        "ceiling_bytes", "ceiling_inodes", "retained_bytes", "retained_inodes", "management"})
    q.require(value["schema"] == "local-hand-quota-capacity/v1", "CAPACITY_SCHEMA")
    q.match(value["boot_id"], q.UUID_PATTERN)
    q.match(value["epoch"], r"[0-9a-f]{32}")
    q.match(value["authority_digest"], r"[0-9a-f]{64}")
    for key in ("ceiling_bytes", "ceiling_inodes", "retained_bytes", "retained_inodes"):
        q.integer(value[key])
    q._keys(value["management"], {"storage_bytes", "storage_inodes", "cpu_ns", "memory_bytes", "pids", "output_bytes"})
    for limit in value["management"].values():
        q.integer(limit, 1)
    domains = value["domains"]
    q.require(type(domains) is list and 0 < len(domains) <= MAX_GRANTS * 4, "DOMAIN_COUNT")
    seen = set()
    for domain in domains:
        q._keys(domain, {"filesystem_uuid", "project_id", "hard_bytes", "hard_inodes"})
        q.match(domain["filesystem_uuid"], q.UUID_PATTERN)
        q.integer(domain["project_id"], 1, 2**32 - 1)
        q.require(q.integer(domain["hard_bytes"], 1) % 1024 == 0, "HARD_LIMIT")
        q.integer(domain["hard_inodes"], 1)
        key = domain["filesystem_uuid"], domain["project_id"]
        q.require(key not in seen, "DUPLICATE_DOMAIN")
        seen.add(key)
    for kind, extra in (("bytes", BASE_BYTES), ("inodes", BASE_INODES)):
        used = sum(domain["hard_" + kind] for domain in domains)
        used += value["retained_" + kind] + value["management"]["storage_" + kind] + extra
        q.require(q.integer(used) <= value["ceiling_" + kind], "GLOBAL_CAPACITY")
    return value


def check_capacity(capacity, grants):
    """Charge all original intent grants, including unknown/completed work."""
    capacity = decode_capacity(q._canonical(capacity, GRANT_LIMIT))
    q.require(len(grants) <= MAX_GRANTS, "GRANT_COUNT")
    capacity_digest = digest(capacity)
    domains = {(item["filesystem_uuid"], item["project_id"]): item["hard_bytes"] for item in capacity["domains"]}
    used = dict.fromkeys(capacity["management"], 0)
    ids = set()
    for original in grants:
        grant = decode_grant(original.wire)
        value = grant.as_dict()
        request = grant.request.as_dict()
        q.require(all(request[key] == capacity[key] for key in ("boot_id", "epoch", "authority_digest"))
                  and value["management"]["capacity_digest"] == capacity_digest, "CAPACITY_BINDING")
        q.require(value["management"]["id"] not in ids, "MANAGEMENT_REUSE")
        ids.add(value["management"]["id"])
        for root in value["roots"]:
            q.require(domains.get((root["filesystem_uuid"], root["project_id"])) == root["hard_bytes"], "DOMAIN_BUDGET")
        for key, amount in totals(grant).items():
            used[key] += amount
            q.require(used[key] <= capacity["management"][key], "MANAGEMENT_EXHAUSTED")
    return used


def check_execution(grant, execution, allocation, *, now_ns):
    """Consume only a broker-selected grant within its original phase window."""
    grant = decode_grant(grant.wire)
    value = grant.as_dict()
    request = grant.request.as_dict()
    q.require(all(execution.get(key) == request[key] for key in ("execution_id", "phase"))
              and execution.get("operation_id") == allocation["operation_id"]
              and allocation == value["allocation"] and execution.get("budget_grant") == value["budget"]
              and execution.get("quota_grant_digest") == grant.digest
              and execution.get("budgets") == value["budget"]["limits"], "BOOTSTRAP_BINDING")
    q.require(request["deadline_ns"] <= q.integer(execution.get("phase_deadline_boottime_ns"), 1), "DEADLINE")
    q.require(value["management"]["issued_ns"] <= q.integer(now_ns) < request["deadline_ns"], "DEADLINE")
    return grant
