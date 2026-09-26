"""One explicit preparation invocation followed by one original Q2 handoff.

The private plan supplies settings; the provisioner supplies observed host facts.
Only the combination produces static declarations. No guessed service identity,
query replay, ledger clearing or accepted verdict is available from this entry.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

SCHEMA = "local-hand-q2-preparation-result/v1"
LIMIT = 2 * 1024 * 1024


def require(ok, code):
    if not ok:
        raise ValueError(code)


def helper(name):
    filename = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("_driver_" + name, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encoded(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    require(len(raw) <= LIMIT, "DRIVER_RECORD_LIMIT")
    return raw


def sha(value):
    return hashlib.sha256(value).hexdigest()


def pin(value):
    return {key: value[key] for key in ("path", "device", "inode")}


def validate_settings(settings):
    """Reject malformed or unbounded settings before any provisioning effect."""
    c = helper("q2_prepare_contract")
    c.keys(settings, ("identity", "original_budgets", "limits", "management", "controllers", "capacity_management", "owner"))
    identity = settings["identity"]
    c.keys(identity, ("id", "authority_id", "node_id", "install_uuid", "deployment_epoch", "generation", "operation_id",
        "profile_ref", "principal_id", "epoch", "slot_generation", "expires_at", "session", "ledger_id"))
    for key in ("id", "epoch", "slot_generation"): c.token(identity[key], r"[0-9a-f]{32}")
    c.token(identity["session"], c.HEX)
    for key in ("authority_id", "node_id", "profile_ref", "ledger_id"):
        c.token(identity[key], r"[a-z0-9][a-z0-9._-]{0,127}")
    c.token(identity["principal_id"], r"q2-synthetic-[a-z0-9-]{1,64}")
    c.token(identity["install_uuid"], c.UUID)
    c.token(identity["operation_id"], r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
    for key in ("deployment_epoch", "generation", "expires_at"): c.number(identity[key], 1, 2**53-1)
    budgets = settings["original_budgets"]
    c.keys(budgets, ("wall_seconds", "terminate_grace_seconds", "cpu_seconds", "memory_bytes", "processes",
        "temporary_bytes", "nas_bytes", "log_bytes", "reservation_bytes"))
    for key, amount in budgets.items(): c.number(amount, 0 if key == "nas_bytes" else 1, 2**53-1)
    require(budgets["nas_bytes"] == 0 and budgets["wall_seconds"] <= 90
        and budgets["wall_seconds"] // 3 > budgets["terminate_grace_seconds"]
        and budgets["cpu_seconds"] >= 3 and budgets["log_bytes"] >= 3
        and budgets["memory_bytes"] <= 1024**3 and budgets["processes"] <= 64
        and budgets["reservation_bytes"] >= 3 * (budgets["temporary_bytes"] + budgets["log_bytes"]), "DRIVER_OPERATION_BUDGET")
    limits = settings["limits"]
    c.keys(limits, ("max_queued", "max_running", "retained_bytes", "ledger_emergency_bytes", "requests_per_minute"))
    for amount in limits.values(): c.number(amount, 1, 2**53-1)
    require(limits["max_running"] == limits["max_queued"] == 1
        and budgets["reservation_bytes"] <= limits["retained_bytes"], "DRIVER_POLICY_LIMITS")
    management = settings["management"]
    c.keys(management, ("receive_ns", "stop_ns", "storage_bytes", "storage_inodes", "stages", "accept_ns", "max_connections"))
    for key in ("receive_ns", "stop_ns", "accept_ns"): c.number(management[key], 1, 5 * 10**9)
    c.number(management["storage_bytes"], 65536, 16*1024**2)
    c.number(management["storage_inodes"], 7, 4096); c.number(management["max_connections"], 1, 16)
    c.keys(management["stages"], ("admission", "query", "collector"))
    for stage in management["stages"].values():
        c.keys(stage, ("cpu_ns", "memory_bytes", "pids", "output_bytes", "runtime_ns"))
        c.number(stage["cpu_ns"], 1, 30*10**9); c.number(stage["memory_bytes"], 1, 1024**3)
        c.number(stage["pids"], 1, 64); c.number(stage["output_bytes"], 1, 32768)
        c.number(stage["runtime_ns"], 1, 30*10**9)
    require(management["stages"]["collector"]["output_bytes"] == 32768, "DRIVER_RECEIPT_BUDGET")
    minimum_storage = 131072 + sum((stage["output_bytes"] + 4095) // 4096 * 4096 + 8192
        for stage in management["stages"].values())
    require(management["storage_bytes"] >= minimum_storage, "DRIVER_MANAGEMENT_STORAGE")
    require(sum(stage["runtime_ns"] for stage in management["stages"].values()) + management["receive_ns"]
        + management["stop_ns"] <= budgets["wall_seconds"] // 3 * 10**9, "DRIVER_MANAGEMENT_BUDGET")
    controllers = settings["controllers"]
    c.keys(controllers, ("target", "supervisor"))
    for control in controllers.values():
        c.keys(control, ("unit", "runtime_max_usec", "timeout_stop_usec", "memory_bytes", "tasks_max",
            "cpu_quota_per_sec_usec", "limit_cpu_seconds", "storage_bytes", "storage_inodes"))
        c.token(control["unit"], r"lhq[a-z0-9-]{1,100}\.service")
        c.number(control["runtime_max_usec"], 1000000, 120000000)
        c.number(control["timeout_stop_usec"], 1000, 5000000)
        c.number(control["memory_bytes"], 16*1024**2, 1024**3); c.number(control["tasks_max"], 2, 64)
        c.number(control["cpu_quota_per_sec_usec"], 1000, 1000000); c.number(control["limit_cpu_seconds"], 1, 120)
        c.number(control["storage_bytes"], 65536, 32*1024**2); c.number(control["storage_inodes"], 16, 4096)
    target, supervisor = controllers["target"], controllers["supervisor"]
    require(target["unit"] != supervisor["unit"] and budgets["wall_seconds"] * 1000000 < target["runtime_max_usec"]
        and target["runtime_max_usec"] + target["timeout_stop_usec"] + 2000000 <= supervisor["runtime_max_usec"],
        "DRIVER_CLEANUP_BUDGET")
    owner = settings["owner"]
    c.keys(owner, ("runtime_ns", "storage_bytes", "storage_inodes", "cpu_ns", "memory_bytes", "pids", "output_bytes"))
    c.number(owner["runtime_ns"], 1, 120*10**9); c.number(owner["storage_bytes"], 8*1024**2, 64*1024**2)
    c.number(owner["storage_inodes"], 20, 4096); c.number(owner["cpu_ns"], 1, 120*10**9)
    c.number(owner["memory_bytes"], 1, 1024**3); c.number(owner["pids"], 1, 64)
    require(owner["output_bytes"] == 69632 and (supervisor["runtime_max_usec"] + supervisor["timeout_stop_usec"]
        + 2000000) * 1000 < owner["runtime_ns"], "DRIVER_OWNER_BUDGET")
    cap = settings["capacity_management"]
    c.keys(cap, ("storage_bytes", "storage_inodes", "cpu_ns", "memory_bytes", "pids", "output_bytes"))
    for amount in cap.values(): c.number(amount, 1, 2**53-1)
    require(cap["storage_bytes"] <= 64*1024**2 and cap["storage_inodes"] <= 32768, "DRIVER_CAPTURE_CEILING")
    require(target["storage_bytes"] >= 1024**2 and supervisor["storage_bytes"] >= 8*1024**2,
        "DRIVER_CONTROLLER_STORAGE")
    # The same conservative charge used by supervisor.validate + owner.binding:
    # all three management grants, both retained controllers and the original owner.
    used = dict.fromkeys(cap, 0)
    for key in ("storage_bytes", "storage_inodes"): used[key] = 3 * management[key]
    for key in ("cpu_ns", "memory_bytes", "pids", "output_bytes"):
        used[key] = 3 * sum(stage[key] for stage in management["stages"].values())
    for control, extra_output in ((target, 3*32768 + 4096), (supervisor, 2*32768 + 4096)):
        for key in ("storage_bytes", "storage_inodes"): used[key] += control[key]
        used["cpu_ns"] += ((control["runtime_max_usec"] + control["timeout_stop_usec"] + 1000000)
            * control["cpu_quota_per_sec_usec"] + 999) // 1000
        used["memory_bytes"] += control["memory_bytes"]; used["pids"] += control["tasks_max"]
        used["output_bytes"] += 32768 + extra_output
    for key in used: used[key] += owner[key]
    require(all(used[key] <= cap[key] for key in used), "DRIVER_COMBINED_CAPACITY")
    return copy.deepcopy(settings)


def validate_plan(plan):
    settings = validate_settings(plan["settings"])
    budget = settings["original_budgets"]
    require(len(plan["roots"]) == 7, "DRIVER_ROOT_COUNT")
    slots = {key: [] for key in ("a", "b", "store")}
    for root in plan["roots"]:
        require(root["slot"] in slots, "DRIVER_ROOT_SLOT")
        slots[root["slot"]].append(root)
        maximum = budget["temporary_bytes"] if root["role"] == "temporary" else budget["reservation_bytes"]
        require(root["hard_bytes"] <= maximum, "DRIVER_ROOT_BUDGET")
    require(len(slots["a"]) == len(slots["b"]) == 3 and len(slots["store"]) == 1, "DRIVER_ROOT_COUNT")
    require(sum(item["hard_bytes"] for item in slots["a"]) <= budget["reservation_bytes"]
        and sum(item["hard_bytes"] for item in slots["b"] + slots["store"]) <= budget["reservation_bytes"],
        "DRIVER_ROOT_BUDGET")
    return settings


def facts_from_receipt(plan, receipt, children):
    """Translate observed pins, never planned inode/account/cgroup identities."""
    a = helper("q2_prepare_assembly")
    settings = validate_plan(plan)
    require(receipt["status"] == "RESOURCES_PREPARED", "DRIVER_RESOURCES_NOT_PREPARED")
    observed = receipt["facts"]
    installation = observed["installation"]
    require(installation["ordinary_verified"] is True, "DRIVER_ORDINARY_INSTALLATION")
    require(installation["source"]["commit"] == plan["candidate"]["commit"]
        and installation["source"]["tree"] == plan["candidate"]["tree"], "DRIVER_CANDIDATE_CHANGED")
    ordinary = {key: observed["ordinary"][key] for key in ("uid", "gid")}
    ordinary.update(parent=pin(observed["parents"]["ordinary"]), initial_userns=observed["host"]["initial_userns"])
    require(all(ordinary[k] == plan["account"][k] for k in ("uid", "gid")), "DRIVER_ACCOUNT_CHANGED")
    directories = observed["directories"]
    for role, original in plan["directories"].items():
        require(directories[role]["path"] == original["path"], "DRIVER_DIRECTORY_CHANGED")
    roots = observed["roots"]
    require(type(roots) is list and len(roots) == 7, "DRIVER_OBSERVED_ROOTS")
    by_path = {root["path"]: root for root in roots}
    require(len(by_path) == 7 and set(by_path) == {r["path"] for r in plan["roots"]}, "DRIVER_ROOT_CHANGED")
    slots = {slot: dict(slot_id=plan["preparation_id"] + "-" + slot, roots={}) for slot in ("a", "b")}
    store = None
    for planned in plan["roots"]:
        measured = by_path[planned["path"]]
        root = {key: measured[key] for key in ("path", "role", "device", "inode", "uid", "gid", "mode", "filesystem",
            "filesystem_uuid", "project_id", "xflags", "hard_bytes", "accounting", "enforcement", "identity_unchanged")}
        root["hard_inodes"] = measured["inode_hard_limit"]
        require(root["project_id"] == planned["project_id"] and root["hard_bytes"] == planned["hard_bytes"]
            and root["hard_inodes"] == planned["inode_hard_limit"] and root["role"] == planned["role"], "DRIVER_QUOTA_CHANGED")
        if planned["slot"] == "store": store = root
        else: slots[planned["slot"]]["roots"][planned["role"]] = root
    authority = dict(schema="local-hand-q2-preparation-authority/v1", scope=plan["scope"], baseline=plan["baseline"],
        plan_sha256=sha(encoded(plan)), preparation_id=plan["preparation_id"], receipt_sha256=sha(encoded(receipt)))
    manifest = dict(schema="local-hand-q2-preparation-manifest/v1", source=installation["source"], ordinary=ordinary,
        roots=roots, parents=observed["parents"], boot_id=observed["host"]["boot_id"], epoch=settings["identity"]["epoch"])
    identity = dict(settings["identity"], authority_digest=sha(encoded(authority)), manifest_digest=sha(encoded(manifest)))
    capobs = observed["mounts"]["quota"]
    domains = [dict(filesystem_uuid=root["filesystem_uuid"], project_id=root["project_id"],
        hard_bytes=root["hard_bytes"], hard_inodes=root["inode_hard_limit"]) for root in roots]
    domains.extend(dict(filesystem_uuid=plan["mounts"]["quota"]["uuid"], project_id=old["project"],
        hard_bytes=old["hard"]*1024, hard_inodes=old["ihard"])
        for old in observed["capacity_observed"]["quota_inventory"] if old["hard"] > 0)
    capacity = dict(schema="local-hand-quota-capacity/v1", boot_id=observed["host"]["boot_id"], epoch=identity["epoch"],
        authority_digest=identity["authority_digest"], domains=domains, ceiling_bytes=capobs["total_bytes"],
        ceiling_inodes=capobs["total_inodes"], retained_bytes=capobs["total_bytes"]-capobs["available_bytes"],
        retained_inodes=capobs["total_inodes"]-capobs["free_inodes"],
        management=settings["capacity_management"])
    controls = {}
    for key, parentrole in (("target", "controller"), ("supervisor", "supervisor")):
        spec = copy.deepcopy(settings["controllers"][key])
        for field in ("storage_bytes", "storage_inodes"): controls[key + "_" + field] = spec.pop(field)
        controls[key] = dict(spec, schema="local-hand-q1-controller/v1",
            cgroup=observed["parents"][parentrole]["path"] + "/" + spec["unit"])
    controls.update({role + "_parent": pin(observed["parents"][role])
        for role in ("query", "management", "controller", "supervisor")})
    paths = dict(broker_root=directories["state"]["path"], authority_root=directories["authority"]["path"],
        policy=directories["authority"]["path"] + "/policy.json", profile_roots={role: directories["profile_" + role]["path"]
        for role in ("work", "evidence", "temporary")}, forbidden_roots=[old["path"] for old in plan["retained"]],
        journal=pin(directories["journal"]), endpoint_dir=directories["control"]["path"],
        management_evidence=children["management_evidence"], phase_outputs={phase: children[phase] for phase in a.PHASES},
        **{key: children[key] for key in ("launcher_output", "launcher_declarations", "supervisor_output", "supervisor_declarations")})
    facts = dict(schema=a.SCHEMA, identity=identity, source={key: installation["source"][key] for key in ("root", "commit", "files")},
        installation=installation["installed"], admin=installation["admin"], python_identity=installation["python_identity"],
        ordinary=ordinary, paths=paths, slots=[slots["a"], slots["b"]], store=store, capacity=capacity,
        management=settings["management"], controllers=controls, setpriv=plan["tools"]["setpriv"],
        original_budgets=settings["original_budgets"], limits=settings["limits"])
    return facts, authority, manifest


class Files:
    """Create-only children under exact provisioned directory descriptors."""
    def __init__(self, guard=lambda: None):
        self.guard = guard

    def open_parent(self, pin, owner=0):
        self.guard()
        c = helper("q2_prepare_contract"); c.path(pin["path"])
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            for component in Path(pin["path"]).parts[1:]:
                new = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                os.close(fd); fd = new
                info = os.fstat(fd)
                require(info.st_uid in (0, owner) and not info.st_mode & 0o022, "DRIVER_PARENT_PROTECTION")
            info = os.fstat(fd)
            require((info.st_dev, info.st_ino, info.st_uid) == (pin["device"], pin["inode"], owner), "DRIVER_PARENT_CHANGED")
            return fd
        except BaseException:
            os.close(fd); raise

    def directory(self, parent, name, mode=0o700):
        require(re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name), "DRIVER_CHILD_NAME")
        fd = self.open_parent(parent)
        try:
            os.mkdir(name, mode, dir_fd=fd)
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            try:
                os.fchmod(child, mode); os.fsync(child); info = os.fstat(child)
            finally: os.close(child)
            os.fsync(fd)
            return dict(path=parent["path"] + "/" + name, device=info.st_dev, inode=info.st_ino)
        finally: os.close(fd)

    def write(self, parent, name, value, *, owner=0, gid=0):
        require(re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", name), "DRIVER_FILE_NAME")
        raw = encoded(value); fd = self.open_parent(parent, owner)
        try:
            child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
            try:
                os.fchown(child, owner, gid); os.fchmod(child, 0o600)
                view = memoryview(raw)
                while view:
                    count = os.write(child, view); require(count > 0, "DRIVER_SHORT_WRITE"); view = view[count:]
                os.fsync(child)
            finally: os.close(child)
            os.fsync(fd)
        finally: os.close(fd)
        return dict(path=parent["path"] + "/" + name, sha256=sha(raw))


def complete(plan, receipt, *, files, command, clock):
    """No query occurs here. Return a sealed one-use invocation for fresh exec."""
    a = helper("q2_prepare_assembly"); handoff = helper("q2_prepare_run")
    settings = validate_plan(plan)
    require(receipt["status"] == "RESOURCES_PREPARED", "DRIVER_RESOURCES_NOT_PREPARED")
    observed = receipt["facts"]; directories = observed["directories"]
    children = {}
    for name in (*a.PHASES, "management_evidence", "launcher_output", "supervisor_output", "owner_output"):
        children[name] = files.directory(directories["capture"], name)
    for name in ("launcher_declarations", "supervisor_declarations", "owner_declarations"):
        children[name] = files.directory(directories["declarations"], name, 0o755 if name == "launcher_declarations" else 0o700)
    facts, authority, manifest = facts_from_receipt(plan, receipt, children)
    assembled = a.assemble(facts)
    files.write(directories["reservation"], "authority.json", authority)
    files.write(directories["reservation"], "manifest.json", manifest)
    uid, gid = facts["ordinary"]["uid"], facts["ordinary"]["gid"]
    policy = files.write(directories["authority"], "policy.json", assembled["policy"], owner=uid, gid=gid)
    python = facts["installation"]["programs"]["python"]["path"]
    driver = facts["source"]["root"] + "/tests/e3_host/q2_prepare_driver.py"
    args = [facts["setpriv"]["path"], "--reuid=" + str(uid), "--regid=" + str(gid), "--clear-groups",
        "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all", "--no-new-privs", python, "-I", "-B", driver,
        "--initialize-ledger", policy["path"], "--sha256", policy["sha256"], "--ledger-id", assembled["ledger_id"]]
    ledger = helper("q2_prepare_contract").document(command(args))
    require(ledger["uid"] == uid and ledger["ledger_id"] == assembled["ledger_id"]
        and ledger["generation"] == assembled["chain"]["broker_generation"]
        and ledger["path"] == facts["paths"]["broker_root"] + "/jobs.sqlite", "DRIVER_LEDGER_BINDING")
    prepared = dict(schema=SCHEMA, status="PREPARED", source_commit=facts["source"]["commit"],
        preparation_id=plan["preparation_id"], policy=policy, ledger=ledger, authority_sha256=sha(encoded(authority)),
        manifest_sha256=sha(encoded(manifest)), q2_accepted=False, q3_accepted=False, production_supported=False)
    files.write(directories["reservation"], "prepared.json", prepared)
    now = clock()
    require(now["boot_id"] == observed["host"]["boot_id"], "DRIVER_BOOT_CHANGED")
    owner = dict(settings["owner"]); duration = owner.pop("runtime_ns")
    owner.update(issued_ns=now["boottime_ns"], deadline_ns=now["boottime_ns"] + duration)
    envelope = dict(schema=handoff.SCHEMA, purpose="ONE_ORIGINAL_Q2_HANDOFF", preparation_id=facts["identity"]["id"],
        boot_id=now["boot_id"], template=assembled["supervisor_template"], supervisor_parent=assembled["supervisor_parent"],
        output=children["owner_output"], declarations=children["owner_declarations"], owner_envelope=owner)
    raw = encoded(envelope); handoff.decode(raw, sha(raw))
    handoff_file = files.write(directories["reservation"], "handoff.json", envelope)
    return prepared, [python, "-I", "-B", facts["source"]["root"] + "/tests/e3_host/q2_prepare_run.py",
        "--plan", handoff_file["path"], "--sha256", handoff_file["sha256"]]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan"); parser.add_argument("--sha256"); parser.add_argument("--execute", action="store_true")
    parser.add_argument("--initialize-ledger"); parser.add_argument("--ledger-id")
    args = parser.parse_args(argv)
    if args.initialize_ledger:
        require(not args.plan and not args.execute and args.sha256 and args.ledger_id, "DRIVER_LEDGER_ARGUMENTS")
        from local_hand_jobs.policy import Policy, thaw
        policy = Policy.from_file(args.initialize_ledger)
        fd = os.open(args.initialize_ledger, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            raw = os.read(fd, 65537)
        finally: os.close(fd)
        require(len(raw) <= 65536 and sha(raw) == args.sha256, "DRIVER_POLICY_CHANGED")
        from local_hand_jobs.contract import strict_loads
        require(Policy(strict_loads(raw)).policy_digest == policy.policy_digest, "DRIVER_POLICY_CHANGED")
        result = helper("q2_prepare_assembly").initialize_ledger(thaw(policy.config), args.ledger_id)
        print(encoded(result).decode(), end=""); return 0
    if not args.plan or not args.sha256 or not args.execute:
        print(encoded(dict(schema=SCHEMA, status="BLOCKED", reason="EXPLICIT_PREPARATION_PLAN_AND_EXECUTE_REQUIRED",
            q2_accepted=False, q3_accepted=False, production_supported=False)).decode(), end="")
        return 3
    require(not args.ledger_id and os.getuid() == os.geteuid() == 0, "DRIVER_ROOT_REQUIRED")
    handoff = helper("q2_prepare_run"); contract = helper("q2_prepare_contract")
    plan = contract.decode(handoff.protected(args.plan), args.sha256)
    validate_plan(plan)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    provision = helper("q2_prepare")
    backend = provision.LinuxBackend(plan)
    receipt = provision.prepare(plan, backend=backend, validate_settings=lambda _: validate_plan(plan))
    if receipt["status"] != "RESOURCES_PREPARED":
        print(encoded(receipt).decode(), end=""); return 3
    from local_hand_jobs.budget import current_clock
    files = Files(backend.guard)
    try:
        prepared, invocation = complete(plan, receipt, files=files, command=backend.command, clock=current_clock)
    except Exception as error:
        code = getattr(error, "code", str(error) if isinstance(error, ValueError) else type(error).__name__)
        if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code): code = type(error).__name__
        files.write(receipt["facts"]["directories"]["reservation"], "driver-failed.json", dict(schema=SCHEMA,
            status="INCOMPLETE", reason=code, retained=True, q2_accepted=False, q3_accepted=False, production_supported=False))
        raise
    print(encoded(prepared).decode(), end="", flush=True)
    os.execv(invocation[0], invocation)
    raise RuntimeError("DRIVER_EXEC_RETURNED")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        code = getattr(error, "code", str(error) if isinstance(error, ValueError) else type(error).__name__)
        if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code): code = type(error).__name__
        print(encoded(dict(schema=SCHEMA, status="INCOMPLETE", reason=code, retained=True,
            q2_accepted=False, q3_accepted=False, production_supported=False)).decode(), end="")
        raise SystemExit(3)
