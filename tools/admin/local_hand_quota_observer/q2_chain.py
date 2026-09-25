"""Finite administrator assembly for one original three-phase operation.

The protected declaration fixes all authority and permanent capacity before
launch. Original broker reservations are bound only when each phase exists.
One append-only journal retains every earlier grant and actual CLOSED fence.
No directory, account, quota domain, mount or process parent is provisioned.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os

from local_hand_jobs import bootstrap_roots, budget, quota_contract as q, quota_grant as g
from local_hand_jobs.contract import JobError
from . import q2_assembly as a, q2_config as c
from .protected_inputs import read_protected, verify_file
from .q2_journal import Journal

SCHEMA = "local-hand-q2-chain/v1"
PHASES = ("preflight", "business", "evidence")
_PHASE = {"grant", "output", "service", "peer"}


@dataclass(frozen=True, slots=True)
class Chain:
    wire: bytes

    @property
    def digest(self):
        return hashlib.sha256(self.wire).hexdigest()

    def data(self):
        return q._load(self.wire, c.LIMIT, 18)


def _totals(value):
    capacity = g.decode_capacity(q._canonical(value["installation"]["capacity"], g.GRANT_LIMIT))
    result = dict.fromkeys(capacity["management"], 0)
    ids = set()
    domains = {(x["filesystem_uuid"], x["project_id"]): x["hard_bytes"] for x in capacity["domains"]}
    for phase in PHASES:
        grant = value["phases"][phase]["grant"]
        management = grant["management"]
        q.require(management["capacity_digest"] == g.digest(capacity), "CHAIN_CAPACITY_BINDING")
        q.require(management["id"] not in ids, "CHAIN_MANAGEMENT_REUSE")
        ids.add(management["id"])
        q.require(all(grant["request"][key] == capacity[key] for key in ("boot_id", "epoch", "authority_digest")),
                  "CHAIN_CAPACITY_BINDING")
        for root in grant["roots"]:
            q.require(domains.get((root["filesystem_uuid"], root["project_id"])) == root["hard_bytes"], "DOMAIN_BUDGET")
        for key in result:
            amount = management[key] if key.startswith("storage_") else sum(stage[key] for stage in management["stages"].values())
            result[key] += amount
            q.require(result[key] <= capacity["management"][key], "MANAGEMENT_EXHAUSTED")
    return result


def decode(raw, digest):
    q.require(hashlib.sha256(raw).hexdigest() == digest, "CHAIN_DIGEST")
    value = q._load(raw, c.LIMIT, 18)
    q._keys(value, {"schema", "purpose", "id", "installation", "original_budgets",
                    "broker_generation", "journal", "phases"})
    q.require(value["schema"] == SCHEMA and value["purpose"] == "ISOLATED_Q2_THREE_PHASE", "CHAIN_SCHEMA")
    q.match(value["id"], r"[0-9a-f]{32}")
    q._keys(value["installation"], a._STATIC)
    q._keys(value["phases"], set(PHASES))
    c.identity(value["journal"])
    generation = value["broker_generation"]
    q.require(type(generation) is list and len(generation) == 2, "ASSEMBLY_GENERATION")
    for item in generation: q.integer(item, 1)
    try:
        budget._validate_limits(value["original_budgets"])
        limits = budget.allocated_limits(value["original_budgets"], "job")
    except JobError: raise q.QuotaError("ASSEMBLY_ORIGINAL_BUDGET") from None
    installation = value["installation"]
    q.require(installation["schema"] == "local-hand-quota-service/v1", "CONFIG_SCHEMA")
    q.match(installation["source_commit"], r"[0-9a-f]{40}")
    q.canonical_path(installation["tools_path"])
    c.identity(installation["evidence"])
    c.identity(installation["initial_userns"], path=False)
    q._keys(installation["programs"], {"python", "native", "systemctl", "systemd_run"})
    for pin in (installation["entry"], *installation["programs"].values()):
        q._keys(pin, {"path", "sha256"}); q.canonical_path(pin["path"]); q.match(pin["sha256"], r"[0-9a-f]{64}")
    protected = [value["journal"]["path"], installation["evidence"]["path"], installation["tools_path"],
                 *(item["path"] for item in installation["programs"].values())]
    identities = {(value["journal"]["device"], value["journal"]["inode"]),
                  (installation["evidence"]["device"], installation["evidence"]["inode"])}
    q.require(len(identities) == 2, "ASSEMBLY_DIRECTORY_ALIAS")
    first = value["phases"]["preflight"]
    requests = set(); roots = []
    for phase in PHASES:
        declaration = value["phases"][phase]
        q._keys(declaration, _PHASE)
        fixed = declaration["grant"]
        q._keys(fixed, a._GRANT)
        q.require(fixed["schema"] == "local-hand-quota-grant/v1", "GRANT_SCHEMA")
        q._keys(fixed["request"], q._REQUEST_KEYS - {"deadline_ns", "observation_grant_digest"})
        # Validate only the fixed request fields. This is not an issued grant
        # or a prediction of any future reservation/deadline.
        q.decode_request(q._canonical(dict(fixed["request"], deadline_ns=1, observation_grant_digest="0"*64), q.REQUEST_LIMIT))
        request = fixed["request"]
        q.require(request["phase"] == phase and request["request_id"] not in requests, "CHAIN_PHASE")
        requests.add(request["request_id"])
        try:
            allocation = bootstrap_roots.validate_grant(fixed["allocation"], execution_id=request["execution_id"], phase=phase)
        except JobError: raise q.QuotaError("ORIGINAL_GRANT") from None
        q.require(allocation["namespace"] == "job" and allocation["operation_id"] == first["grant"]["allocation"]["operation_id"]
                  and allocation["record_id"] == allocation["operation_id"], "CHAIN_OPERATION")
        q.require(request["allocation_digest"] == allocation["allocation_id"] and request["slot_ref"] == allocation["slot_id"], "ORIGINAL_BINDING")
        q.require(all(request[key] == first["grant"]["request"][key] for key in
                      ("boot_id", "epoch", "authority_digest", "generation", "installation_digest", "manifest_digest")), "CHAIN_AUTHORITY")
        expected = q.validate_expected_roots(fixed["roots"], phase)
        paths = g.root_paths(allocation)
        q.require({root["role"] for root in expected} == paths.keys(), "ROOT_BINDING")
        charged = {}
        for root in expected:
            path = paths[root["role"]]; q.canonical_path(path)
            q.require(all(root[key] == allocation["paths"][path][key] for key in ("device", "inode", "uid")), "ROOT_BINDING")
            q.require(root["hard_bytes"] <= limits["temporary_bytes" if root["role"] == "temporary" else "reservation_bytes"], "ROOT_BUDGET")
            charged[root["filesystem_uuid"], root["project_id"]] = root["hard_bytes"]
        q.require(sum(charged.values()) <= limits["reservation_bytes"], "ROOT_BUDGET")
        q.require(all(not c.overlap(x, y) for i, x in enumerate(paths.values()) for y in list(paths.values())[i+1:]), "ROOT_OVERLAP")
        roots.extend(paths.values())
        if phase == "business":
            q.require(allocation["allocation_id"] == first["grant"]["allocation"]["allocation_id"]
                      and expected == first["grant"]["roots"], "BUSINESS_ALLOCATION")
        if phase == "evidence":
            retained = next(root for root in expected if root["role"] == "retained_store")
            retained_path = paths["retained_store"]
            old_paths = g.root_paths(first["grant"]["allocation"])
            q.require(any(retained_path == old_paths[old["role"]]
                          and all(retained[key] == old[key] for key in retained if key != "role")
                          for old in first["grant"]["roots"]), "RETAINED_BINDING")
            q.require(all(not c.overlap(path, old) for role, path in paths.items()
                          if role != "retained_store" for old in old_paths.values()), "RESOURCE_CONSUMED")
            old_domains = {(root["filesystem_uuid"], root["project_id"]) for root in first["grant"]["roots"]}
            q.require(all((root["filesystem_uuid"], root["project_id"]) not in old_domains
                          for root in expected if root["role"] != "retained_store"), "RESOURCE_CONSUMED")
        q._keys(fixed["endpoint"], {"path", "uid", "gid", "boot_id"})
        endpoint = fixed["endpoint"]
        q.require(len(q.canonical_path(endpoint["path"]).encode()) <= 107 and endpoint["uid"] == 0
                  and endpoint["gid"] == next(root for root in expected if root["role"] == "work")["gid"]
                  and endpoint["boot_id"] == request["boot_id"], "ENDPOINT_OWNER")
        for name in ("query_parent", "management_parent"):
            c.identity(fixed[name])
            q.require(fixed[name] == first["grant"][name], "CHAIN_PROCESS_PARENT")
        management = fixed["management"]
        q._keys(management, g._MANAGEMENT_KEYS - {"issued_ns"})
        q.match(management["id"], r"[0-9a-f]{32}")
        q.match(management["capacity_digest"], r"[0-9a-f]{64}")
        for key in ("receive_ns", "stop_ns", "storage_bytes", "storage_inodes"): q.integer(management[key], 1)
        q._keys(management["stages"], set(g.STAGES))
        for stage in management["stages"].values():
            q._keys(stage, g._STAGE_KEYS)
            for amount in stage.values(): q.integer(amount, 1)
            q.require(stage["cpu_ns"] >= 1_000_000_000 and stage["memory_bytes"] >= 16*1024**2
                      and 2 <= stage["pids"] <= 32 and stage["output_bytes"] >= q.RESPONSE_LIMIT, "RUNTIME_LIMITS")
        wall = sum(stage["runtime_ns"] for stage in management["stages"].values())
        q.require(wall + management["receive_ns"] + management["stop_ns"]
                  <= (limits["wall_seconds"] - limits["terminate_grace_seconds"]) * budget.NANOSECONDS,
                  "CHAIN_MANAGEMENT_DEADLINE")
        baseline = g.CELL_BYTES + sum(g._rounded(stage["output_bytes"]) + 8192 for stage in management["stages"].values())
        q.require(management["storage_bytes"] >= baseline + 3*4096 + 65536 and management["storage_inodes"] >= 11, "ASSEMBLY_STORAGE")
        c.identity(declaration["output"])
        identity = declaration["output"]["device"], declaration["output"]["inode"]
        q.require(identity not in identities, "ASSEMBLY_DIRECTORY_ALIAS"); identities.add(identity)
        q._keys(declaration["service"], {"parent", "control_path", "accept_ns", "max_connections"})
        service = declaration["service"]
        c.identity(service["parent"])
        q.require(service["parent"] == fixed["management_parent"], "MANAGEMENT_PARENT")
        q.require(len(q.canonical_path(service["control_path"]).encode()) <= 107, "ENDPOINT_LENGTH")
        q.integer(service["accept_ns"], 1, 2_000_000_000); q.integer(service["max_connections"], 1, g.MAX_GRANTS)
        peer = declaration["peer"]
        q._keys(peer, {"parent", "executable", "runner"})
        c.identity(peer["parent"]); c.identity(peer["executable"])
        q._keys(peer["runner"], {"path", "sha256"})
        q.canonical_path(peer["runner"]["path"]); q.match(peer["runner"]["sha256"], r"[0-9a-f]{64}")
        q.require(peer == first["peer"], "CHAIN_INSTALLED_PEER")
        protected.extend((declaration["output"]["path"], endpoint["path"], service["control_path"]))
    q.require(all(not c.overlap(x, y) for i, x in enumerate(protected) for y in protected[i+1:]), "CHAIN_GEOMETRY")
    q.require(all(not c.overlap(root, path) for root in roots for path in protected), "CHAIN_GEOMETRY")
    _totals(value)
    return Chain(raw)


def load(path, digest):
    return decode(read_protected(path, c.LIMIT), digest)


def declared_totals(chain):
    """Charge every fixed management envelope before any phase starts."""
    return _totals(decode(chain.wire, chain.digest).data())


def phase_template(chain, phase):
    value = decode(chain.wire, chain.digest).data()
    q.require(phase in PHASES, "CHAIN_PHASE")
    view = dict(schema=a.SCHEMA, purpose="ISOLATED_Q2_THREE_PHASE", id=value["id"],
                **{key: value[key] for key in ("installation", "original_budgets", "broker_generation", "journal")},
                **value["phases"][phase])
    return a.Template(q._canonical(view, c.LIMIT))


def _fixed(grant):
    value = grant.as_dict()
    return {key: ({k: v for k, v in child.items() if k != "deadline_ns"} if key == "request" else
                  {k: v for k, v in child.items() if k != "issued_ns"} if key == "management" else child)
            for key, child in value.items() if key in a._GRANT}


def _previous(chain, previousconfigs):
    q.require(type(previousconfigs) in (tuple, list) and len(previousconfigs) < len(PHASES), "CHAIN_PREFIX")
    value = chain.data(); cumulative = {}; peers = {}; pin = None
    for index, original in enumerate(previousconfigs):
        config = c.decode(original.wire, original.path, original.digest)
        data = config.data(); phase = PHASES[index]; fixed = value["phases"][phase]
        key = fixed["grant"]["request"]["request_id"]
        q.require(config.path == fixed["output"]["path"] + "/observer.json"
                  and all(data[k] == v for k, v in value["installation"].items())
                  and data["service"] == dict(fixed["service"], request_id=key, end_ns=config.active().request.as_dict()["deadline_ns"])
                  and data["journal"]["path"] == value["journal"]["path"]
                  and data["session"]["path"] == fixed["output"]["path"] + "/session", "CHAIN_CONFIG_BINDING")
        grant = config.active()
        q.require(_fixed(grant) == fixed["grant"] and grant.as_dict()["predecessors"] == list(cumulative), "CHAIN_GRANT_BINDING")
        cumulative[key] = grant.as_dict()
        peer = data["peers"][key]
        q.require(peer["parent"] == fixed["peer"]["parent"] and peer["executable"] == fixed["peer"]["executable"], "CHAIN_PEER_BINDING")
        peers[key] = peer
        q.require(data["grants"] == cumulative and data["peers"] == peers, "CHAIN_PREFIX")
        current = data["journal"]["pin"]
        q.require(current["directory"] == {k: value["journal"][k] for k in ("device", "inode")}, "ASSEMBLY_JOURNAL_CHANGED")
        if pin is not None:
            q.require(all(current["files"].get(name) == identity for name, identity in pin["files"].items()), "CHAIN_JOURNAL_REPLACED")
        pin = current
    return cumulative, peers, pin


def build_grant(chain, snapshot, *, previousconfigs=(), session, clock):
    chain = decode(chain.wire, chain.digest); value = chain.data()
    previous, unused, unused_pin = _previous(chain, previousconfigs)
    phase = PHASES[len(previousconfigs)]; fixed = value["phases"][phase]["grant"]
    q.match(session, r"[0-9a-f]{64}")
    try: budget._validate_clock(clock)
    except JobError: raise q.QuotaError("ASSEMBLY_CLOCK") from None
    q._keys(snapshot, {"preparation", "observation", "pending", "closed"})
    q.require(all(snapshot[key] is None for key in ("observation", "pending", "closed")), "ASSEMBLY_ALREADY_STARTED")
    prep = snapshot["preparation"]
    q._keys(prep, {"phase", "session", "budget", "allocation", "generation"})
    q.require(prep["phase"] == phase and prep["session"] == session and prep["generation"] == value["broker_generation"]
              and prep["allocation"] == fixed["allocation"], "ASSEMBLY_PREPARATION")
    allocation = fixed["allocation"]
    try:
        budget.validate_grant(prep["budget"], namespace="job", phase=phase,
            execution_id=allocation["execution_id"], record_id=allocation["record_id"],
            operation_id=allocation["operation_id"], original_budgets=value["original_budgets"])
    except JobError: raise q.QuotaError("ASSEMBLY_ORIGINAL_BUDGET") from None
    for old in previous.values():
        q.require(all(prep["budget"][key] == old["budget"][key] for key in
                      ("boot_id", "budget_digest", "started_boottime_ns", "deadline_boottime_ns", "limits")), "ORIGINAL_BUDGET_CHANGED")
        q.require(prep["budget"]["reserved_boottime_ns"] >= old["budget"]["reserved_boottime_ns"], "CLOCK_REGRESSION")
    q.require(clock["boot_id"] == fixed["request"]["boot_id"] == prep["budget"]["boot_id"]
              and prep["budget"]["reserved_boottime_ns"] <= clock["boottime_ns"], "ASSEMBLY_CLOCK")
    end = budget.phase_deadline_ns(prep["budget"]) - prep["budget"]["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS
    candidate = dict(fixed, request=dict(fixed["request"], deadline_ns=end), budget=prep["budget"],
        predecessors=list(previous), management=dict(fixed["management"], issued_ns=clock["boottime_ns"]))
    grant = g.decode_grant(q._canonical(candidate, g.GRANT_LIMIT))
    g.check_capacity(value["installation"]["capacity"], [*(g.decode_grant(q._canonical(x, g.GRANT_LIMIT)) for x in previous.values()), grant])
    return grant


def _configuration(chain, grant, command, previousconfigs, journal_pin, session_pin):
    value = chain.data(); phase = grant.request.as_dict()["phase"]; declaration = value["phases"][phase]
    grants, peers, unused = _previous(chain, previousconfigs)
    key = grant.request.as_dict()["request_id"]; peer = declaration["peer"]
    grants[key] = grant.as_dict()
    peers[key] = dict(parent=peer["parent"], executable=peer["executable"], command_sha256=command)
    data = dict(value["installation"], grants=grants, peers=peers,
        journal=dict(path=value["journal"]["path"], pin=journal_pin), session=session_pin,
        service=dict(declaration["service"], request_id=key, end_ns=grant.request.as_dict()["deadline_ns"]))
    raw = q._canonical(data, c.LIMIT)
    return c.decode(raw, declaration["output"]["path"] + "/observer.json", hashlib.sha256(raw).hexdigest())


def install(chain, grant, *, bootstrap_argv, previousconfigs=(), session, clock):
    """Consume one fixed phase once; every uncertain partial write is retained."""
    a._administrator()
    chain = decode(chain.wire, chain.digest); value = chain.data()
    previous, unused, old_pin = _previous(chain, previousconfigs)
    grant = g.decode_grant(grant.wire); phase = PHASES[len(previousconfigs)]
    view = phase_template(chain, phase); declaration = value["phases"][phase]
    for index, original in enumerate(previousconfigs):
        checked = c.load(original.path, original.digest)
        q.require(checked.wire == original.wire, "CHAIN_CONFIG_CHANGED")
        old_phase = PHASES[index]; output = value["phases"][old_phase]["output"]
        fd = a._directory(output); os.close(fd)
        record = q._load(read_protected(output["path"] + "/reservation.json", 4096), 4096, 4)
        q.require(record == dict(schema="local-hand-q2-chain-reservation/v1", id=value["id"],
            template_digest=chain.digest, grant_digest=original.active().digest, session=session,
            phase=old_phase, previous_config_digests=[x.digest for x in previousconfigs[:index]],
            created_ns=record.get("created_ns")), "CHAIN_RESERVATION_CHANGED")
        q.integer(record["created_ns"], original.active().as_dict()["management"]["issued_ns"],
                  original.active().request.as_dict()["deadline_ns"] - 1)
    prep = dict(phase=phase, session=session, budget=grant.as_dict()["budget"],
                allocation=grant.as_dict()["allocation"], generation=value["broker_generation"])
    built = build_grant(chain, dict(preparation=prep, observation=None, pending=None, closed=None),
        previousconfigs=previousconfigs, session=session,
        clock=dict(clock, boottime_ns=grant.as_dict()["management"]["issued_ns"]))
    q.require(built == grant, "ASSEMBLY_GRANT_CHANGED")
    try: budget._validate_clock(clock)
    except JobError: raise q.QuotaError("ASSEMBLY_CLOCK") from None
    q.require(clock["boot_id"] == grant.request.as_dict()["boot_id"]
              and grant.as_dict()["management"]["issued_ns"] <= clock["boottime_ns"] < grant.request.as_dict()["deadline_ns"], "ASSEMBLY_DEADLINE")
    command = a._argv(view, grant, bootstrap_argv, clock["boottime_ns"])
    output = declaration["output"]["path"]; key = grant.request.as_dict()["request_id"]
    dummy = {"device": 0, "inode": 1}
    files = {name: dummy for name in ("lock", "policy")} if old_pin is None else dict(old_pin["files"])
    files[key + ".cell"] = dummy
    preview = _configuration(chain, grant, command, previousconfigs,
        dict(directory={k: value["journal"][k] for k in dummy}, files=files), dict(dummy, path=output + "/session"))
    management = grant.as_dict()["management"]
    baseline = g.CELL_BYTES + sum(g._rounded(stage["output_bytes"]) + 8192 for stage in management["stages"].values())
    overhead = g._rounded(len(preview.wire) + 1024) + 4096 + 65536 + 4096
    q.require(management["storage_bytes"] >= baseline + overhead and management["storage_inodes"] >= 11, "ASSEMBLY_STORAGE")
    reservation = q._canonical(dict(schema="local-hand-q2-chain-reservation/v1", id=value["id"],
        template_digest=chain.digest, grant_digest=grant.digest, session=session, phase=phase,
        previous_config_digests=[x.digest for x in previousconfigs], created_ns=clock["boottime_ns"]), 4096) + b"\n"
    descriptors = []
    try:
        target = a._directory(declaration["output"], empty=True); descriptors.append(target)
        journal = a._directory(value["journal"], empty=not previousconfigs); descriptors.append(journal)
        evidence = a._directory(value["installation"]["evidence"], empty=not previousconfigs); descriptors.append(evidence)
        peer = declaration["peer"]
        fd = c.open_protected(peer["executable"]["path"])
        try:
            info = os.fstat(fd)
            q.require((info.st_dev, info.st_ino) == (peer["executable"]["device"], peer["executable"]["inode"])
                      and info.st_mode & 0o111, "ASSEMBLY_PEER_EXECUTABLE")
        finally: os.close(fd)
        verify_file(peer["runner"]["path"], peer["runner"]["sha256"])
        reserved = a._file(target, "reservation.json", reservation); os.fsync(target)
        session_pin = a._file(target, "session", b"")
        record_pin = a._file(target, "management.jsonl", b"")
        if previousconfigs:
            pin = Journal.extend(value["journal"]["path"], old_pin, value["installation"]["capacity"],
                [g.decode_grant(q._canonical(x, g.GRANT_LIMIT)) for x in previous.values()], grant)
        else:
            pin = Journal.provision_chain(value["journal"]["path"], value["installation"]["capacity"], [grant])
        q.require(pin["directory"] == {k: value["journal"][k] for k in dummy}, "ASSEMBLY_JOURNAL_CHANGED")
        config = _configuration(chain, grant, command, previousconfigs, pin, dict(session_pin, path=output + "/session"))
        a._file(target, "observer.json", config.wire); os.fsync(target)
        checked = c.load(config.path, config.digest)
        return dict(config=checked, management_record=dict(record_pin, path=output + "/management.jsonl"),
                    reservation=dict(reserved, path=output + "/reservation.json"))
    finally:
        for descriptor in reversed(descriptors): os.close(descriptor)
