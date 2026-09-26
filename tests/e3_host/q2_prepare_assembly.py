"""Pure Q2 fixture assembly from observed preparation facts.

The returned supervisor template intentionally has no issued/deadline times or
future service identity. Only the original delivery owner may issue its envelope;
only the running same-PID entry may bind its own dynamic service identity.
No account, quota, service, grant reservation or acceptance is created here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat

SCHEMA = "local-hand-q2-assembly-facts/v1"
PHASES = ("preflight", "business", "evidence")
DYNAMIC = {"invocation_id", "cgroup_device", "cgroup_inode"}


def require(value, code):
    if not value:
        raise ValueError(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _keys(value, keys):
    require(type(value) is dict and set(value) == set(keys), "PREP_ASSEMBLY_FIELDS")


def _root(root, role):
    from local_hand_jobs import quota_contract as q, bootstrap_roots
    _keys(root, {"path", "hard_inodes", *q._ROOT_KEYS})
    require(root["role"] == role, "PREP_ASSEMBLY_ROLE")
    bootstrap_roots.validate_root({k: root[k] for k in ("path", "device", "inode", "uid")})
    q.integer(root["hard_inodes"], 1, 4096)
    require(root["hard_bytes"] <= 64 * 1024**2, "PREP_ASSEMBLY_QUOTA_CEILING")
    return {k: root[k] for k in q._ROOT_KEYS}


def _allocation(slot, phase, operation, source_roots, store):
    from local_hand_jobs import bootstrap_roots as b
    roots = {role: item["path"] for role, item in slot["roots"].items()}
    paths = {item["path"]: {key: item[key] for key in ("device", "inode", "uid")}
             for item in slot["roots"].values()}
    retained = []
    if phase == "evidence":
        retained.append(store["path"])
        paths[store["path"]] = {key: store[key] for key in ("device", "inode", "uid")}
    value = dict(version=1, namespace="job", record_id=operation, operation_id=operation,
        execution_id="job-" + operation + "-" + phase, phase=phase, slot_id=slot["slot_id"],
        roots=roots, paths=paths, retained_paths=retained, fresh=phase != "business",
        source_roots=copy.deepcopy(source_roots))
    value["allocation_id"] = b._allocation_id("job", operation, slot["slot_id"], roots, paths)
    value["grant_digest"] = b._digest(value)
    return b.validate_grant(value)


def assemble(facts):
    """Return private policy + resident/chain/launcher/static-supervisor objects.

    Exact input groups are checked below. Observed roots contain quota-contract
    expected fields plus path and hard_inodes; the provisioner is responsible
    for verifying these facts against the selected guest before calling this
    pure function. Every amount/name/identity is explicit, with no host defaults.
    `source`, `installation`, `admin`, and `python_identity` are the matching
    verified candidate installation receipt fields (source additionally has root).
    `controllers` contains static target/supervisor specs, four parent pins and
    each envelope's storage_bytes/storage_inodes. Envelope wall times are absent.
    """
    from local_hand_jobs import contract, policy as p, quota_contract as q, quota_grant as g
    from local_hand_jobs.registry import Registry
    from admin.local_hand_quota_observer import q2_chain, q2_config, controller_guard

    f = copy.deepcopy(facts)
    _keys(f, {"schema", "identity", "source", "installation", "admin", "python_identity", "ordinary",
        "paths", "slots", "store", "capacity", "management", "controllers", "setpriv", "original_budgets", "limits"})
    require(f["schema"] == SCHEMA, "PREP_ASSEMBLY_SCHEMA")
    ident = f["identity"]
    _keys(ident, {"id", "authority_id", "node_id", "install_uuid", "deployment_epoch", "generation",
        "operation_id", "profile_ref", "principal_id", "epoch", "authority_digest", "manifest_digest",
        "slot_generation", "expires_at", "session", "ledger_id"})
    q.match(ident["id"], r"[0-9a-f]{32}")
    q.match(ident["session"], r"[0-9a-f]{64}")
    q.match(ident["principal_id"], r"q2-synthetic-[a-z0-9-]{1,64}")
    q.match(ident["ledger_id"], r"[a-z0-9][a-z0-9._-]{0,127}")
    source, install, admin = f["source"], f["installation"], f["admin"]
    _keys(source, {"root", "commit", "files"})
    _keys(install, {"package_root", "source_commit", "payload_digest", "files", "programs"})
    _keys(admin, {"programs", "entry", "abi", "package_files"})
    require(source["commit"] == install["source_commit"], "PREP_ASSEMBLY_SOURCE")
    q.match(source["commit"], r"[0-9a-f]{40}"); q.canonical_path(source["root"])
    q._keys(install["programs"], {"python", "systemctl", "systemd_run"})
    q._keys(admin["programs"], {"python", "native", "systemctl", "systemd_run"})
    require(1 <= len(source["files"]) <= 512 and 1 <= len(install["files"]) <= 512, "PREP_ASSEMBLY_FILES")
    for name, checksum in source["files"].items():
        q.match(name, r"(?:tools|tests/e3_host)/(?:[a-z_][a-z0-9_]*/)*[a-z_][a-z0-9_]*\.py")
        q.match(checksum, r"[0-9a-f]{64}")
    for name, checksum in install["files"].items():
        q.match(name, r"(?:local_hand|local_hand_jobs|local_hand_mcp|local_hand_connect)/[a-z_][a-z0-9_]*\.py")
        require(source["files"].get("tools/" + name) == checksum, "PREP_ASSEMBLY_INSTALLED_SOURCE")
    for name, checksum in admin["package_files"].items():
        require(source["files"].get("tools/" + name) == checksum, "PREP_ASSEMBLY_ADMIN_SOURCE")
    for entry in ("q2_launcher", "q2_resident", "q2_supervisor", "q2_fixture_check"):
        require("tests/e3_host/" + entry + ".py" in source["files"], "PREP_ASSEMBLY_ENTRY")
    require(admin["entry"] == dict(path=source["root"] + "/tools/admin/local_hand_quota_observer/q2_entry.py",
        sha256=admin["package_files"].get("admin/local_hand_quota_observer/q2_entry.py")), "PREP_ASSEMBLY_ADMIN_ENTRY")
    for key in ("python", "systemctl", "systemd_run"):
        require(install["programs"][key] == admin["programs"][key], "PREP_ASSEMBLY_PROGRAM_BINDING")
    q._keys(f["setpriv"], {"path", "sha256"})
    require(f["setpriv"]["path"] == "/usr/bin/setpriv", "PREP_ASSEMBLY_SETPRIV")
    q.match(f["setpriv"]["sha256"], r"[0-9a-f]{64}")
    ordinary = f["ordinary"]
    _keys(ordinary, {"uid", "gid", "parent", "initial_userns"})
    q.integer(ordinary["uid"], 1, 2**32-2); q.integer(ordinary["gid"], 1, 2**32-2)
    q2_config.identity(ordinary["parent"]); q2_config.identity(ordinary["initial_userns"], path=False)
    q2_config.identity(f["python_identity"], path=False)
    paths = f["paths"]
    _keys(paths, {"broker_root", "authority_root", "policy", "profile_roots", "forbidden_roots", "journal",
        "management_evidence", "phase_outputs", "endpoint_dir", "launcher_output", "launcher_declarations",
        "supervisor_output", "supervisor_declarations"})
    _keys(paths["profile_roots"], {"work", "evidence", "temporary"})
    _keys(paths["phase_outputs"], set(PHASES))
    for key in ("broker_root", "authority_root", "policy", "endpoint_dir"):
        q.canonical_path(paths[key])
    for key in ("journal", "management_evidence", "launcher_output", "launcher_declarations",
                "supervisor_output", "supervisor_declarations"):
        q2_config.identity(paths[key])
    for pin in paths["phase_outputs"].values(): q2_config.identity(pin)
    require(type(f["slots"]) is list and len(f["slots"]) == 2, "PREP_ASSEMBLY_SLOT_COUNT")
    roots = []
    slots = []
    for slot in f["slots"]:
        _keys(slot, {"slot_id", "roots"}); _keys(slot["roots"], {"work", "evidence", "temporary"})
        for role, root in slot["roots"].items():
            roots.append(root); _root(root, role)
        slots.append(dict(slot_id=slot["slot_id"], roots={role: {key: root[key] for key in
            ("path", "device", "inode", "uid")} for role, root in slot["roots"].items()}))
    _root(f["store"], "retained_store"); roots.append(f["store"])
    require(all((root["uid"], root["gid"]) == (ordinary["uid"], ordinary["gid"]) for root in roots),
        "PREP_ASSEMBLY_ROOT_OWNER")
    require(len({(root["filesystem_uuid"], root["project_id"]) for root in roots}) == 7, "PREP_ASSEMBLY_DOMAIN_REUSE")
    controllers = f["controllers"]
    _keys(controllers, {"target", "supervisor", "controller_parent", "query_parent", "management_parent", "supervisor_parent",
        "target_storage_bytes", "target_storage_inodes", "supervisor_storage_bytes", "supervisor_storage_inodes"})
    for key in ("target", "supervisor"):
        _keys(controllers[key], set(controller_guard.SPEC_FIELDS) - DYNAMIC)
        controller_guard.decode_controller(dict(controllers[key], invocation_id="0"*32, cgroup_device=0, cgroup_inode=1))
    for key in ("controller_parent", "query_parent", "management_parent", "supervisor_parent"):
        q2_config.identity(controllers[key]); q.match(controllers[key]["path"], r"/lhq[a-z0-9]+\.slice")
    require(str(Path(controllers["target"]["cgroup"]).parent) == controllers["controller_parent"]["path"] and
            str(Path(controllers["supervisor"]["cgroup"]).parent) == controllers["supervisor_parent"]["path"], "PREP_ASSEMBLY_CONTROLLER_PARENT")
    parents = [ordinary["parent"], *(controllers[key] for key in ("controller_parent", "query_parent", "management_parent", "supervisor_parent"))]
    require(all(not q2_config.overlap(left["path"], right["path"]) and
        (left["device"], left["inode"]) != (right["device"], right["inode"])
        for i, left in enumerate(parents) for right in parents[i+1:]), "PREP_ASSEMBLY_PARENT_OVERLAP")
    profile = dict((role + "_root", path) for role, path in paths["profile_roots"].items())
    budgets = {kind: copy.deepcopy(f["original_budgets"]) for kind in (*contract.KINDS, "reconcile")}
    # The inaccessible NAS kind still needs a well-formed dormant policy budget.
    budgets["ledger.nas.roundtrip"]["nas_bytes"] = max(1, budgets["ledger.nas.roundtrip"]["nas_bytes"])
    profile.update(python=install["programs"]["python"]["path"], sources={}, build_caches={}, storages={},
        budgets=budgets, resource_ids=["q2-" + ident["id"]], bootstrap_slots=slots,
        bootstrap_evidence_store={key: f["store"][key] for key in ("path", "device", "inode", "uid")})
    scopes = ["lh:submit", "lh:read", "lh:evidence"]
    config = dict(schema_version="lh-policy-v1", **{key: ident[key] for key in
        ("authority_id", "node_id", "install_uuid", "deployment_epoch", "generation")},
        broker_root=paths["broker_root"], authority_root=paths["authority_root"], forbidden_roots=paths["forbidden_roots"],
        limits=f["limits"], profiles={ident["profile_ref"]: profile}, principals={ident["principal_id"]: dict(scopes=scopes,
        profiles={ident["profile_ref"]: dict(kinds=["host.inspect"], source_refs=[], build_cache_refs=[], storage_refs=[],
        prepared_refs=[], prepared_access="owned")})}, installed_payload_digest=install["payload_digest"],
        execution_entrypoint=install["package_root"] + "/local_hand_jobs/cli.py", source_commit=source["commit"],
        local_peers={str(ordinary["uid"]): ident["principal_id"]}, process_manager=dict(uid=ordinary["uid"],
        slice=Path(ordinary["parent"]["path"]).name, cgroup="/sys/fs/cgroup" + ordinary["parent"]["path"]))
    policy = p.Policy(config)
    request = dict(schema_version="lh-job-v1", operation_id=ident["operation_id"], kind="host.inspect",
        profile_ref=ident["profile_ref"], expected=policy.expected(ident["profile_ref"]), inputs={}, expires_at=ident["expires_at"])
    request["request_digest"] = contract.request_digest(request)
    plan = p.thaw(Registry().resolve(request, policy, principal=contract.Principal(ident["principal_id"], frozenset(scopes))))
    capacity = g.decode_capacity(q._canonical(f["capacity"], g.GRANT_LIMIT))
    require(all(capacity[key] == ident[key] for key in ("epoch", "authority_digest")), "PREP_ASSEMBLY_CAPACITY_BINDING")
    domain_map = {(root["filesystem_uuid"], root["project_id"]): root for root in capacity["domains"]}
    for root in roots:
        dom = domain_map.get((root["filesystem_uuid"], root["project_id"]))
        require(dom is not None and dom["hard_bytes"] == root["hard_bytes"] and dom["hard_inodes"] == root["hard_inodes"],
            "PREP_ASSEMBLY_CAPACITY_DOMAIN")
    installation = dict(schema="local-hand-quota-service/v1", source_commit=source["commit"], tools_path=source["root"] + "/tools",
        **copy.deepcopy(admin), initial_userns=ordinary["initial_userns"], capacity=capacity, evidence=paths["management_evidence"])
    peer = dict(parent=ordinary["parent"], executable=dict(path=install["programs"]["python"]["path"], **f["python_identity"]),
        runner=dict(path=install["package_root"] + "/local_hand_jobs/runner.py", sha256=install["files"]["local_hand_jobs/runner.py"]))
    mgmt = f["management"]
    _keys(mgmt, {"receive_ns", "stop_ns", "storage_bytes", "storage_inodes", "stages", "accept_ns", "max_connections"})
    chain = dict(schema=q2_chain.SCHEMA, purpose="ISOLATED_Q2_THREE_PHASE", id=ident["id"], installation=installation,
        original_budgets=f["original_budgets"], broker_generation=[policy.generation, 1], journal=paths["journal"], phases={})
    for phase in PHASES:
        slot = f["slots"][1 if phase == "evidence" else 0]
        allocation = _allocation(slot, phase, ident["operation_id"], plan["execution"]["roots"], f["store"])
        expected = [_root(slot["roots"][role], role) for role in q.ROOT_ROLES[:3]]
        if phase == "evidence": expected.append(_root(f["store"], "retained_store"))
        request_id = digest(dict(preparation_id=ident["id"], phase=phase, role="query"))[:32]
        query = dict(schema="local-hand-quota-observe/v1", operation="observe", request_id=request_id,
            authority_digest=ident["authority_digest"], installation_digest=digest(dict(ordinary=install, admin=admin)),
            manifest_digest=ident["manifest_digest"], epoch=ident["epoch"], generation=ident["slot_generation"],
            boot_id=capacity["boot_id"], slot_ref=slot["slot_id"], execution_id=allocation["execution_id"], phase=phase,
            allocation_digest=allocation["allocation_id"])
        management = {key: copy.deepcopy(mgmt[key]) for key in ("receive_ns", "stop_ns", "storage_bytes", "storage_inodes", "stages")}
        management.update(id=digest(dict(preparation_id=ident["id"], phase=phase, role="management"))[:32], capacity_digest=g.digest(capacity))
        grant = dict(schema="local-hand-quota-grant/v1", request=query, allocation=allocation, roots=expected,
            endpoint=dict(path=paths["endpoint_dir"] + "/" + phase + ".sock", uid=0, gid=ordinary["gid"], boot_id=capacity["boot_id"]),
            query_parent=controllers["query_parent"], management_parent=controllers["management_parent"], management=management)
        chain["phases"][phase] = dict(grant=grant, output=paths["phase_outputs"][phase], peer=peer,
            service=dict(parent=controllers["management_parent"], control_path=paths["endpoint_dir"] + "/" + phase + "-ctl.sock",
                         accept_ns=mgmt["accept_ns"], max_connections=mgmt["max_connections"]))
    raw = q._canonical(chain, q2_config.LIMIT)
    checked = q2_chain.decode(raw, hashlib.sha256(raw).hexdigest())
    q2_chain.check_policy(checked, policy, ident["profile_ref"])
    resident = dict(schema="local-hand-q2-resident/v2", purpose="ISOLATED_Q2_CHAIN",
        entry=dict(path=source["root"] + "/tests/e3_host/q2_resident.py", sha256=source["files"]["tests/e3_host/q2_resident.py"]),
        installation=install, policy=dict(path=paths["policy"], digest=policy.policy_digest),
        ordinary=dict(ordinary, broker_cgroup=controllers["target"]["cgroup"]), principal=dict(principal_id=ident["principal_id"], scopes=scopes),
        request=request, plan=plan, phases=list(PHASES))
    envelope = lambda key: dict(controller=controllers[key], output_bytes=32768,
        storage_bytes=controllers[key + "_storage_bytes"], storage_inodes=controllers[key + "_storage_inodes"])
    launcher = dict(schema="local-hand-q2-launcher/v2", purpose="ISOLATED_Q2_CHAIN", source={key: source[key] for key in ("commit", "files")},
        resident=resident, assembly=chain, controller_envelope=envelope("target"), setpriv=f["setpriv"],
        output=paths["launcher_output"], declarations=paths["launcher_declarations"], session=ident["session"])
    supervisor = dict(schema="local-hand-q2-supervisor/v1", purpose="ISOLATED_Q2_SUPERVISION", launcher=launcher,
        controller_parent=controllers["controller_parent"], supervisor_envelope=envelope("supervisor"),
        output=paths["supervisor_output"], declarations=paths["supervisor_declarations"])
    require(controllers["target"]["runtime_max_usec"] + controllers["target"]["timeout_stop_usec"] + 2_000_000
        <= controllers["supervisor"]["runtime_max_usec"], "PREP_ASSEMBLY_CLEANUP_BUDGET")
    # Account both original controller levels before any time is issued. This
    # is the same finite conservative charge the running supervisor verifies.
    totals = q2_chain.declared_totals(checked)
    for name, output in (("target", 3 * 32768 + 32768 + 4096), ("supervisor", 3 * 32768 + 4096)):
        spec = controllers[name]
        amount = dict(storage_bytes=controllers[name + "_storage_bytes"], storage_inodes=controllers[name + "_storage_inodes"],
            cpu_ns=((spec["runtime_max_usec"] + spec["timeout_stop_usec"] + 1_000_000) * spec["cpu_quota_per_sec_usec"] + 999)//1000,
            memory_bytes=spec["memory_bytes"], pids=spec["tasks_max"], output_bytes=output)
        q.integer(amount["storage_bytes"], (1 if name == "target" else 8) * 1024**2)
        q.integer(amount["storage_inodes"], 9 if name == "target" else 16)
        for key, count in amount.items():
            totals[key] += q.integer(count, 1)
            require(totals[key] <= capacity["management"][key], "PREP_ASSEMBLY_COMBINED_CAPACITY")
    protected_paths = [source["root"], install["package_root"], paths["journal"]["path"], paths["management_evidence"]["path"],
                      *(pin["path"] for pin in paths["phase_outputs"].values()),
                      *(paths[key]["path"] for key in ("launcher_output", "launcher_declarations", "supervisor_output", "supervisor_declarations"))]
    require(all(not q2_config.overlap(left,right) for i,left in enumerate(protected_paths) for right in protected_paths[i+1:]),
            "PREP_ASSEMBLY_OUTPUT_OVERLAP")
    pins = [paths[key] for key in ("journal", "management_evidence", "launcher_output", "launcher_declarations",
                                 "supervisor_output", "supervisor_declarations")] + list(paths["phase_outputs"].values())
    require(len({(pin["device"],pin["inode"]) for pin in pins}) == len(pins), "PREP_ASSEMBLY_OUTPUT_ALIAS")
    ordinary_paths = [paths["broker_root"], paths["authority_root"],
                      *paths["profile_roots"].values(), f["store"]["path"]]
    require(all(not q2_config.overlap(pin["path"], root) for pin in pins for root in ordinary_paths),
            "PREP_ASSEMBLY_ORDINARY_OUTPUT_OVERLAP")
    require(all((pin["device"], pin["inode"]) != (root["device"], root["inode"])
                for pin in pins for root in roots), "PREP_ASSEMBLY_ORDINARY_OUTPUT_ALIAS")
    return dict(schema="local-hand-q2-static-assembly/v1", status="ASSEMBLED", policy=config,
        policy_digest=policy.policy_digest, resident=resident, chain=chain, launcher=launcher,
        supervisor_template=supervisor, supervisor_parent=controllers["supervisor_parent"],
        ledger_id=ident["ledger_id"], q2_accepted=False, q3_accepted=False, production_supported=False)


def initialize_ledger(config, ledger_id):
    """Create the core schema once under the actual ordinary identity.

    The provisioner invokes this in a dedicated bounded ordinary child. This
    helper never changes credentials, creates parent directories, clears an old
    database, submits an operation or repairs a partially created ledger.
    """
    from local_hand_jobs.policy import Policy
    from local_hand_jobs.state import StateStore
    policy = Policy(config)
    require(os.getuid() == os.geteuid() == policy.config["process_manager"]["uid"] > 0, "PREP_LEDGER_ORDINARY_REQUIRED")
    require(type(ledger_id) is str and 0 < len(ledger_id) <= 128, "PREP_LEDGER_ID")
    root = Path(policy.broker_root)
    require(root.resolve() == root and not root.is_symlink(), "PREP_LEDGER_PATH")
    with os.scandir(root) as entries:
        require(next(entries, None) is None, "PREP_LEDGER_CONSUMED")
    state = StateStore(root / "jobs.sqlite", policy.authority_id, ledger_id, initialize=True)
    try:
        with state.transaction() as tx:
            require(all(tx.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
                for table in ("operations", "events", "leases")), "PREP_LEDGER_NOT_EMPTY")
            generation = tx.execute("SELECT value FROM counters WHERE key='generation'").fetchone()[0]
            require(generation == 1, "PREP_LEDGER_GENERATION")
    finally:
        state.close()
    require(not any((root / ("jobs.sqlite" + suffix)).exists() for suffix in ("-wal", "-shm", "-journal")), "PREP_LEDGER_SIDECAR")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)
    info = (root / "jobs.sqlite").lstat()
    return dict(path=str(root / "jobs.sqlite"), device=info.st_dev, inode=info.st_ino,
        uid=info.st_uid, mode=stat.S_IMODE(info.st_mode), ledger_id=ledger_id, generation=[policy.generation, generation])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(dict(schema="local-hand-q2-static-assembly/v1", status="BLOCKED",
        reason="EXPLICIT_PREPARATION_FACTS_REQUIRED", q2_accepted=False, q3_accepted=False, production_supported=False)))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
