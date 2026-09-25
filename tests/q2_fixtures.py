"""Synthetic trusted declarations only; never runtime admission defaults."""
import copy
import hashlib

from local_hand_jobs import bootstrap_roots, quota_contract as q, quota_grant as g
from test_local_hand_jobs_quota_contract import encoded, request_data, root_facts, receipt_data

BOOT = "11111111-2222-3333-4444-555555555555"
SECOND = 1_000_000_000


def capacity():
    return {"schema": "local-hand-quota-capacity/v1", "boot_id": BOOT,
        "epoch": "5" * 32, "authority_digest": "2" * 64,
        "ceiling_bytes": 2**31, "ceiling_inodes": 100000,
        "retained_bytes": 2**20, "retained_inodes": 100,
        "domains": [{"filesystem_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                     "project_id": 1001 + i, "hard_bytes": 65536, "hard_inodes": 128} for i in range(100)],
        "management": {"storage_bytes": 2**30, "storage_inodes": 10000, "cpu_ns": 100 * SECOND,
                       "memory_bytes": 2**30, "pids": 1000, "output_bytes": 2**25}}


def grant_data(*, number=1, phase="preflight", operation="fixture", offset=0,
               declared_capacity=None, predecessors=(), issued=SECOND, allocation=None, phase_budget=None):
    cap = capacity() if declared_capacity is None else declared_capacity
    roots = root_facts(fourth=phase == "evidence")
    for root in roots:
        root["inode"] += offset
        root["project_id"] += offset
    if allocation is None:
        paths = {root["role"]: "/synthetic/slot-" + str(offset) + "/" + root["role"] for root in roots}
        root_paths = {key: paths[key] for key in q.ROOT_ROLES[:3]}
        allocation = {"version": 1, "namespace": "job", "record_id": operation,
            "operation_id": operation, "execution_id": "job-" + operation + "-" + phase,
            "phase": phase, "slot_id": "slot-" + str(offset), "roots": root_paths,
            "paths": {paths[root["role"]]: {k: root[k] for k in ("device", "inode", "uid")} for root in roots},
            "retained_paths": [paths["retained_store"]] if phase == "evidence" else [],
            "fresh": phase != "business", "source_roots": dict(root_paths)}
        allocation["allocation_id"] = bootstrap_roots._allocation_id("job", operation,
            allocation["slot_id"], root_paths, allocation["paths"])
        allocation["grant_digest"] = bootstrap_roots._digest(allocation)
    else:
        allocation = copy.deepcopy(allocation)
        for root in roots:
            identity = allocation["paths"][g.root_paths(allocation)[root["role"]]]
            root.update(identity)
    if phase_budget is None:
        # Pure declaration: no Linux runner imports during Windows collection.
        limits = dict(wall_seconds=30, terminate_grace_seconds=1, cpu_seconds=9,
            memory_bytes=1024**2, processes=8, temporary_bytes=1024**2,
            nas_bytes=0, log_bytes=1024, reservation_bytes=4*1024**2)
        original = dict(limits)
        for key in ("wall_seconds", "cpu_seconds", "log_bytes"):
            original[key] *= 3
        phase_budget = {"version": 1, "namespace": "job", "record_id": operation,
            "operation_id": operation, "execution_id": "job-" + operation + "-" + phase,
            "phase": phase, "budget_digest": g.digest(original), "boot_id": BOOT,
            "started_boottime_ns": SECOND, "reserved_boottime_ns": SECOND,
            "deadline_boottime_ns": 91*SECOND, "limits": limits}
    request = request_data(phase, deadline=issued + 10 * SECOND)
    request.pop("observation_grant_digest")
    request.update(request_id=f"{number:032x}", slot_ref=allocation["slot_id"],
        execution_id=allocation["execution_id"], allocation_digest=allocation["allocation_id"], boot_id=phase_budget["boot_id"])
    return {"schema": "local-hand-quota-grant/v1", "request": request,
        "allocation": allocation, "budget": phase_budget, "roots": roots,
        "endpoint": {"path": "/synthetic/control/quota.sock", "uid": 0, "gid": 1234, "boot_id": phase_budget["boot_id"]},
        "query_parent": {"path": "/synthetic-query.slice", "device": 4, "inode": 82},
        "management_parent": {"path": "/synthetic-control.slice", "device": 4, "inode": 83},
        "predecessors": list(predecessors), "management": {"id": f"{number:032x}", "capacity_digest": g.digest(cap),
            "issued_ns": issued, "receive_ns": SECOND, "stop_ns": SECOND,
            "storage_bytes": 2**20, "storage_inodes": 10,
            "stages": {stage: {"cpu_ns": SECOND, "memory_bytes": 2**20, "pids": 4,
                               "output_bytes": 32768, "runtime_ns": SECOND} for stage in g.STAGES}}}


def make_grant(**kwargs):
    return g.decode_grant(encoded(grant_data(**kwargs)))


def peer(grant):
    data = grant.as_dict()
    root = data["roots"][0]
    unit = "lhj-" + hashlib.sha256((data["request"]["execution_id"] + ":bootstrap").encode()).hexdigest() + ".service"
    return {"uid": root["uid"], "gid": root["gid"], "pid": 4321, "start_ticks": 12345,
            "boot_id": BOOT, "unit": unit, "invocation_id": "a" * 32,
            "cgroup": "/synthetic-job.slice/" + unit,
            "parent": {"path": "/synthetic-job.slice", "device": 4, "inode": 81}}


def query(grant):
    parent = grant.as_dict()["query_parent"]
    return {"unit": grant.request.query_unit, "invocation_id": "b" * 32,
            "cgroup": parent["path"] + "/" + grant.request.query_unit, "parent": parent}


def receipt(grant, *, start=2*SECOND, finish=2*SECOND+10):
    data = receipt_data(grant.request, grant.as_dict()["roots"], start=start, finish=finish)
    data["query"] = {k: v for k, v in query(grant).items() if k != "parent"}
    return data


def fence(grant, wire, *, closed=3*SECOND):
    from json import loads
    request = grant.request.as_dict()
    client = peer(grant)
    identities = {"bootstrap": {k: client[k] for k in ("boot_id", "unit", "invocation_id", "cgroup", "parent")},
                  "query": dict(loads(wire)["query"], boot_id=BOOT, parent=grant.as_dict()["query_parent"])}
    for stage in ("helper", "reader", "collector"):
        parent = grant.as_dict()["management_parent"] if stage == "collector" else client["parent"]
        suffix = ":result_reader" if stage == "reader" else ""
        unit = ("lhqoc-" + grant.request.digest if stage == "collector" else
                "lhj-" + hashlib.sha256((request["execution_id"] + suffix).encode()).hexdigest()) + ".service"
        identities[stage] = {"boot_id": BOOT, "unit": unit, "invocation_id": "e" * 32,
                             "cgroup": parent["path"] + "/" + unit, "parent": parent}
    return {"schema": "local-hand-quota-phase-closed/v1", "request_digest": grant.request.digest,
        "receipt_digest": hashlib.sha256(wire).hexdigest(), "boot_id": BOOT,
        "execution_id": grant.request.as_dict()["execution_id"], "proof_digest": "c" * 64,
        "closed_ns": closed, "stages": {name: {**dict.fromkeys(q.EXIT_FLAGS, True), "proof_digest": "d" * 64, "identity": identities[name]}
        for name in ("bootstrap", "helper", "reader", "query", "collector")}}
