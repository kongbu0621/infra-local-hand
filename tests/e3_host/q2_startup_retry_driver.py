"""Assemble one new authorized Q2 run after both issued historical failures.

Both issued old owners and all of their incomplete evidence remain unchanged. This
entry installs no runtime patches and executes the frozen replacement candidate
once. No arguments create no files or processes.
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
import time

SCHEMA = "local-hand-q2-supervisor-startup-retry-driver-result/v1"
DELIVERY_SCHEMA = "local-hand-q2-supervisor-startup-retry-delivery/v1"
AUTHORITY_SCHEMA = "local-hand-q2-supervisor-startup-retry-authority/v1"
PREPARATION_NS = 140 * 10**9
GUEST_NS = 270 * 10**9
STOP_NS = 3 * 10**9
FINALIZATION_NS = 5 * 10**9
LIMIT = 2 * 1024 * 1024
ASSEMBLY_FILES = {"delivery-envelope.json": 4096, "new-request-issuance.json": 4096,
    "new-request.json": 16384, "authority.json": 65536, "manifest.json": 262144,
    "policy.json": 65536, "prepared.json": 65536, "handoff.json": LIMIT, "driver-failed.json": 65536}
ASSEMBLY_RESERVATION_INODES = len(ASSEMBLY_FILES) + 4
ASSEMBLY_RESERVATION_BYTES = sum(ASSEMBLY_FILES.values()) + ASSEMBLY_RESERVATION_INODES * 4096


def write(files, parent, name, value, **kwargs):
    require(name in ASSEMBLY_FILES and len(encoded(value)) <= ASSEMBLY_FILES[name], "STARTUP_RETRY_DRIVER_ASSEMBLY_SIZE")
    return files.write(parent, name, value, **kwargs)


def require(value, code):
    if not value:
        raise ValueError(code)


def reason(error):
    value = getattr(error, "code", str(error) if isinstance(error, ValueError) else type(error).__name__)
    return value if type(value) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else type(error).__name__


def error_details(error):
    """Keep typed errno evidence without exception text or private input paths."""
    if not isinstance(error, OSError):
        return None
    name = type(error).__name__
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name) is None:
        name = "OSError"
    number = error.errno
    return dict(type=name, errno=number if type(number) is int and 0 <= number <= 4095 else None)


def helper(name):
    filename = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("_startup_retry_driver_" + name, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encoded(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    require(len(raw) <= LIMIT, "STARTUP_RETRY_DRIVER_RECORD_LIMIT")
    return raw


def sha(value):
    return hashlib.sha256(value).hexdigest()


def first_clock():
    # Capture before argument parsing, helper imports or any protected read.
    return dict(monotonic_ns=time.monotonic_ns(), boottime_ns=
        time.clock_gettime_ns(time.CLOCK_BOOTTIME) if sys.platform.startswith("linux") else 0)


def current_clock():
    # A read-only clock needs no import from staged runtime code before attestation.
    return dict(boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME))


def deduplicated_observed(plan, observed):
    """Adapt the frozen translator while retaining the full live inventory.

    The frozen preparation translator appends newly created roots to the old
    inventory. Here the seven roots already occur in that inventory. Remove only
    exact matching entries in an isolated copy; never change the receipt or
    refund an unrelated retained project.
    """
    result = copy.deepcopy(observed)
    roots = {root["project_id"]: root for root in observed["roots"]}
    require(len(roots) == 7, "STARTUP_RETRY_DRIVER_ROOT_COUNT")
    inventory = observed["capacity_observed"]["quota_inventory"]
    seen, retained = set(), []
    for item in inventory:
        project = item["project"]
        require(project not in seen, "STARTUP_RETRY_DRIVER_DUPLICATE_QUOTA_DOMAIN")
        seen.add(project)
        if project in roots:
            root = roots[project]
            require(root["filesystem_uuid"] == plan["mounts"]["quota"]["uuid"]
                and item["hard"] * 1024 == root["hard_bytes"]
                and item["ihard"] == root["inode_hard_limit"], "STARTUP_RETRY_DRIVER_REUSED_QUOTA_CHANGED")
        else:
            retained.append(item)
    require(set(roots) <= seen, "STARTUP_RETRY_DRIVER_REUSED_QUOTA_MISSING")
    result["capacity_observed"]["quota_inventory"] = retained
    return result


def predecessor_bindings(retry):
    """Bind both ordered issued failures to their preserved plan and evidence."""
    predecessors = retry["predecessors"]
    require(type(predecessors) is list and len(predecessors) == 2
        and [item.get("kind") for item in predecessors] ==
        ["CPUQUOTA_PARSE_BEFORE_CHILD", "SUPERVISOR_STARTED_PERMISSION_FAILURE"],
        "STARTUP_RETRY_DRIVER_PREDECESSORS")
    files = retry["old_files"]
    result = []
    for item in predecessors:
        require(files[item["plan_path"]] == item["plan_sha256"], "STARTUP_RETRY_DRIVER_PREDECESSOR_PLAN")
        ledger = item["ledger"]
        result.append(dict(kind=item["kind"], plan_path=item["plan_path"], plan_sha256=item["plan_sha256"],
            prepared_path=item["prepared_path"], prepared_sha256=files[item["prepared_path"]],
            handoff_path=item["handoff_path"], handoff_sha256=files[item["handoff_path"]],
            owner_output=item["owner_output"], policy_path=item["policy_path"],
            policy_sha256=files[item["policy_path"]], ledger=dict(ledger, sha256=files[ledger["path"]]),
            failed_units=copy.deepcopy(item["failed_units"])))
    require(result[0]["ledger"]["path"] != result[1]["ledger"]["path"],
        "STARTUP_RETRY_DRIVER_LEDGER_ALIAS")
    return result


def facts_from_retry(plan, retry, receipt, children, issuance=None):
    """Bind new authority to the full dual predecessor and unused-root proof."""
    d = helper("q2_prepare_driver")
    require(receipt.get("schema") == "local-hand-q2-supervisor-startup-retry-preparation/v1"
        and receipt.get("status") == "STARTUP_RETRY_RESOURCES_PREPARED"
        and all(receipt.get(key) is False for key in
            ("fixture_generated", "q2_accepted", "q3_accepted", "production_supported")),
        "STARTUP_RETRY_DRIVER_RESOURCES_NOT_PREPARED")
    require(receipt.get("attempt_id") == retry["attempt_id"]
        and plan["preparation_id"] == retry["attempt_id"]
        and receipt.get("plan_sha256") == sha(encoded(plan))
        and receipt.get("retry_sha256") == sha(encoded(retry)), "STARTUP_RETRY_DRIVER_PLAN_CHANGED")
    provenance = receipt["retry"]
    attestation = provenance["attestation"]
    require(provenance["attestation_sha256"] == sha(encoded(attestation))
        and provenance["original_files_preserved"] is True
        and all(attestation.get(key) is True for key in
            ("original_files_preserved", "unused_roots", "unused_ledgers"))
        and attestation.get("roots") == receipt["facts"]["roots"], "STARTUP_RETRY_DRIVER_PROVENANCE")
    bindings = predecessor_bindings(retry)
    claims, ledgers = attestation.get("predecessors"), attestation.get("ledgers")
    require(type(claims) is list and type(ledgers) is list and len(claims) == len(ledgers) == 2,
        "STARTUP_RETRY_DRIVER_DUAL_ATTESTATION")
    for binding, claim, ledger in zip(bindings, claims, ledgers):
        require(type(claim) is dict and all(claim.get(key) == binding[key] for key in
            ("kind", "plan_sha256", "prepared_sha256", "handoff_sha256", "owner_output"))
            and claim.get("original_owner_issued") is True and claim.get("original_status") == "INCOMPLETE",
            "STARTUP_RETRY_DRIVER_PREDECESSOR_CHANGED")
        require(type(ledger) is dict and all(ledger.get(key) == value for key, value in binding["ledger"].items())
            and ledger.get("unused") is True, "STARTUP_RETRY_DRIVER_LEDGER_CHANGED")
    observed = receipt["facts"]
    require(observed["retained_after"] == observed["retained_before"], "STARTUP_RETRY_DRIVER_RETAINED_CHANGED")
    require(all(observed["host"][key] == plan["host"][key] for key in ("boot_id", "initial_userns")),
        "STARTUP_RETRY_DRIVER_HOST_CHANGED")
    mapping = dict(schema="local-hand-q2-unused-root-operation-binding/v1",
        operation_id=plan["settings"]["identity"]["operation_id"],
        attestation_sha256=provenance["attestation_sha256"], roots=copy.deepcopy(observed["roots"]))
    authority = dict(schema=AUTHORITY_SCHEMA, scope=retry["scope"], rule=retry["rule"], baseline=retry["baseline"],
        closure=retry["closure"], owner_decision=copy.deepcopy(retry["owner_decision"]),
        orchestration_source=copy.deepcopy(retry["source"]), candidate=copy.deepcopy(retry["candidate"]),
        attempt_id=retry["attempt_id"], retry_plan_sha256=sha(encoded(retry)), derived_plan_sha256=sha(encoded(plan)),
        original_plan_sha256=retry["original_plan_sha256"], original_files_sha256=sha(encoded(retry["old_files"])),
        retry_receipt_sha256=sha(encoded(receipt)), unused_root_operation_binding=mapping,
        delivery_sha256=receipt["delivery_sha256"], clock_anchor_sha256=receipt["clock_anchor_sha256"],
        original_owners_issued=True, original_verdicts_retained=True,
        predecessors=copy.deepcopy(retry["predecessors"]), reservations=copy.deepcopy(retry["reservations"]),
        predecessor_attestations=copy.deepcopy(claims), ledger_attestations=copy.deepcopy(ledgers),
        supersedes_failed_attempt=bindings)
    if issuance is not None:
        authority["new_request_issuance"] = copy.deepcopy(issuance)
    facts, authority, manifest = d.facts_from_observed(plan, deduplicated_observed(plan, observed), children, authority)
    if issuance is not None:
        facts["identity"]["expires_at"] = issuance["expires_at"]
    require(len(encoded(authority)) <= ASSEMBLY_FILES["authority.json"]
        and len(encoded(manifest)) <= ASSEMBLY_FILES["manifest.json"], "STARTUP_RETRY_DRIVER_ASSEMBLY_SIZE")
    return facts, authority, manifest


def new_request(plan, retry, settings, now, wall_ns, delivery_envelope, entry):
    helper("q2_startup_retry_delivery").owner_admission(settings, delivery_envelope, now, entry)
    require(type(wall_ns) is int and wall_ns > 0, "STARTUP_RETRY_DRIVER_WALL_CLOCK")
    seconds = min(settings["owner"]["runtime_ns"] // 10**9,
        (delivery_envelope["deadline_ns"] - now["boottime_ns"] - STOP_NS - FINALIZATION_NS) // 10**9)
    issued = wall_ns // 10**9
    require(seconds >= settings["original_budgets"]["wall_seconds"] + 10,
        "STARTUP_RETRY_DRIVER_REQUEST_TIME_UNFUNDED")
    return dict(schema="local-hand-q2-new-request-issuance/v1", attempt_id=retry["attempt_id"],
        retry_plan_sha256=sha(encoded(retry)), operation_id=settings["identity"]["operation_id"],
        planned_expires_at=settings["identity"]["expires_at"], issued_at=issued,
        issued_boottime_ns=now["boottime_ns"], expires_at=issued + seconds,
        deadline_boottime_ns=now["boottime_ns"] + seconds * 10**9,
        original_owners_issued=True, original_verdicts_retained=True,
        supersedes_handoff_sha256=[item["handoff_sha256"] for item in predecessor_bindings(retry)])


class TrackedFiles:
    """Append a bounded intent before each assembly mutation."""
    def __init__(self, files, event):
        self.files, self.event = files, event

    def directory(self, parent, name, mode=0o700):
        self.event("assembly-intent", dict(kind="directory", parent=parent, name=name, mode=mode))
        result = self.files.directory(parent, name, mode)
        self.event("assembly-result", result)
        return result

    def write(self, parent, name, value, **kwargs):
        self.event("assembly-intent", dict(kind="file", parent=parent, name=name,
            sha256=sha(encoded(value)), **kwargs))
        result = self.files.write(parent, name, value, **kwargs)
        self.event("assembly-result", result)
        return result


def complete(plan, retry, receipt, *, files, command, clock, entry, delivery_envelope, verify_preserved,
             measure_costs, wall_clock=time.time_ns):
    """Append a new assembly and issue its owner once; retain the issued old one."""
    d = helper("q2_prepare_driver")
    a = helper("q2_prepare_assembly")
    handoff = helper("q2_prepare_run")
    settings = d.validate_plan(plan)
    require(receipt.get("delivery_envelope") == delivery_envelope
        and receipt.get("delivery_sha256") == sha(encoded(delivery_envelope))
        and receipt.get("clock_anchor_sha256") == delivery_envelope["clock_anchor_sha256"],
        "STARTUP_RETRY_DRIVER_DELIVERY_CHANGED")
    # Validate provenance and observation shape before any child creation.
    placeholder = {name: {"path": "/unissued/" + name, "device": 0, "inode": 1}
        for name in (*a.PHASES, "management_evidence", "launcher_output", "launcher_declarations",
            "supervisor_output", "supervisor_declarations")}
    facts_from_retry(plan, retry, receipt, placeholder)
    helper("q2_startup_retry_delivery").owner_admission(settings, delivery_envelope, clock(), entry)
    observed = receipt["facts"]
    directories = observed["directories"]
    costs = measure_costs()
    block = max([4096] + [mount.get("block_bytes", 4096) for mount in observed["mounts"].values()])
    require(type(block) is int and block <= 65536 and block & (block - 1) == 0,
            "STARTUP_RETRY_DRIVER_ALLOCATION_BLOCK")
    state_bytes = sum((limit + block - 1) // block * block for limit in ASSEMBLY_FILES.values())
    state_bytes += ASSEMBLY_RESERVATION_INODES * block
    child_directories = len(a.PHASES) + 7
    require(costs["state"]["bytes"] + max(ASSEMBLY_RESERVATION_BYTES, state_bytes) <= plan["budgets"]["state_bytes"]
        and costs["state"]["inodes"] + ASSEMBLY_RESERVATION_INODES <= plan["budgets"]["state_inodes"]
        and costs["capture"]["bytes"] + (child_directories + 2) * block <= plan["budgets"]["capture_bytes"]
        and costs["capture"]["inodes"] + child_directories <= plan["budgets"]["capture_inodes"],
        "STARTUP_RETRY_DRIVER_ASSEMBLY_CAPACITY")
    reservation = receipt["retry"]["directory"]
    require(reservation["path"] == plan["directories"]["reservation"]["path"],
            "STARTUP_RETRY_DRIVER_RESERVATION_BINDING")
    verify_preserved()
    write(files, reservation, "delivery-envelope.json", delivery_envelope)
    children = {}
    for name in (*a.PHASES, "management_evidence", "launcher_output", "supervisor_output", "owner_output"):
        children[name] = files.directory(directories["capture"], name)
    for name in ("launcher_declarations", "supervisor_declarations", "owner_declarations"):
        children[name] = files.directory(directories["declarations"], name, 0o755 if name == "launcher_declarations" else 0o700)
    issuance = new_request(plan, retry, settings, clock(), wall_clock(), delivery_envelope, entry)
    # New create-only children and new ledger belong to this attempt only.
    # The old owner was issued and is never reclassified as unissued.
    write(files, reservation, "new-request-issuance.json", issuance)
    facts, authority, manifest = facts_from_retry(plan, retry, receipt, children, issuance)
    assembled = a.assemble(facts)
    actual_request = assembled["supervisor_template"]["launcher"]["resident"]["request"]
    require(actual_request["operation_id"] == issuance["operation_id"]
        and actual_request["expires_at"] == issuance["expires_at"], "STARTUP_RETRY_DRIVER_REQUEST_BINDING")
    write(files, reservation, "new-request.json", dict(issuance=issuance, request=actual_request,
        authority_sha256=sha(encoded(authority))))
    write(files, reservation, "authority.json", authority)
    write(files, reservation, "manifest.json", manifest)
    uid, gid = facts["ordinary"]["uid"], facts["ordinary"]["gid"]
    policy = write(files, directories["authority"], "policy.json", assembled["policy"], owner=uid, gid=gid)
    python = facts["installation"]["programs"]["python"]["path"]
    # Ordinary initialization executes the pinned replacement candidate unchanged.
    driver = facts["source"]["root"] + "/tests/e3_host/q2_prepare_driver.py"
    args = [facts["setpriv"]["path"], "--reuid=" + str(uid), "--regid=" + str(gid), "--clear-groups",
        "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all", "--no-new-privs", python, "-I", "-B", driver,
        "--initialize-ledger", policy["path"], "--sha256", policy["sha256"], "--ledger-id", assembled["ledger_id"]]
    ledger = helper("q2_prepare_contract").document(command(args))
    require(ledger["uid"] == uid and ledger["ledger_id"] == assembled["ledger_id"]
        and ledger["generation"] == assembled["chain"]["broker_generation"]
        and ledger["path"] == facts["paths"]["broker_root"] + "/jobs.sqlite", "STARTUP_RETRY_DRIVER_LEDGER_BINDING")
    prepared = dict(schema=SCHEMA, status="STARTUP_RETRY_PREPARED", source_commit=facts["source"]["commit"],
        scope=retry["scope"], rule=retry["rule"], baseline=retry["baseline"], closure=retry["closure"],
        owner_decision=copy.deepcopy(retry["owner_decision"]),
        orchestration_source=copy.deepcopy(retry["source"]),
        runtime_candidate={key: plan["candidate"][key] for key in ("commit", "tree", "wheel_sha256")},
        attempt_id=retry["attempt_id"], original_owners_issued=True, original_verdicts_retained=True,
        delivery_sha256=sha(encoded(delivery_envelope)), clock_anchor_sha256=delivery_envelope["clock_anchor_sha256"],
        supersedes_failed_attempt=predecessor_bindings(retry),
        retry_receipt_sha256=sha(encoded(receipt)), policy=policy, ledger=ledger,
        new_request_issuance=issuance, request_digest=actual_request["request_digest"],
        authority_sha256=sha(encoded(authority)), manifest_sha256=sha(encoded(manifest)),
        q2_accepted=False, q3_accepted=False, production_supported=False)
    write(files, reservation, "prepared.json", prepared)
    verify_preserved()
    now = clock()
    duration = helper("q2_startup_retry_delivery").owner_admission(settings, delivery_envelope, now, entry)
    require(now["boottime_ns"] + (settings["original_budgets"]["wall_seconds"] + 10) * 10**9
        < issuance["deadline_boottime_ns"] and wall_clock() // 10**9
        + settings["original_budgets"]["wall_seconds"] + 10 < issuance["expires_at"],
        "STARTUP_RETRY_DRIVER_REQUEST_TIME_UNFUNDED")
    owner = dict(settings["owner"])
    owner.pop("runtime_ns")
    owner.update(issued_ns=now["boottime_ns"], deadline_ns=now["boottime_ns"] + duration)
    envelope = dict(schema=handoff.SCHEMA, purpose="ONE_ORIGINAL_Q2_HANDOFF", preparation_id=facts["identity"]["id"],
        boot_id=now["boot_id"], template=assembled["supervisor_template"], supervisor_parent=assembled["supervisor_parent"],
        output=children["owner_output"], declarations=children["owner_declarations"], owner_envelope=owner)
    raw = encoded(envelope)
    handoff.decode(raw, sha(raw))
    handoff_file = write(files, reservation, "handoff.json", envelope)
    # Count the final handoff and all other actual assembly writes before any
    # runtime process is issued. Old/new retained state share the same ceilings.
    verify_preserved()
    final_now = clock()
    helper("q2_startup_retry_delivery").owner_admission(settings, delivery_envelope, final_now, entry)
    require(final_now["boottime_ns"] + (settings["original_budgets"]["wall_seconds"] + 10) * 10**9
        < issuance["deadline_boottime_ns"] and wall_clock() // 10**9
        + settings["original_budgets"]["wall_seconds"] + 10 < issuance["expires_at"],
        "STARTUP_RETRY_DRIVER_REQUEST_TIME_UNFUNDED")
    # Do not create another owner if this create-only file or any child exists.
    return prepared, [python, "-I", "-B", facts["source"]["root"] + "/tests/e3_host/q2_prepare_run.py",
        "--plan", handoff_file["path"], "--sha256", handoff_file["sha256"]]


def main(argv=None):
    entry = first_clock()
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("retry", "sha256", "delivery-envelope", "delivery-sha256"):
        parser.add_argument("--" + flag)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    backend = None
    guest = None
    stage = "admission"
    try:
        require(args.execute and all(getattr(args, flag.replace("-", "_")) for flag in
            ("retry", "sha256", "delivery-envelope", "delivery-sha256")), "EXPLICIT_STARTUP_RETRY_AND_DELIVERY_REQUIRED")
        require(sys.platform.startswith("linux") and sys.flags.isolated and sys.dont_write_bytecode
            and os.getuid() == os.geteuid() == 0, "STARTUP_RETRY_DRIVER_ISOLATED_ROOT_REQUIRED")
        protected = helper("q2_prepare")
        contract = helper("q2_startup_retry_contract")
        delivery = helper("q2_startup_retry_delivery")
        retry = contract.decode(protected.read(args.retry, LIMIT, noatime=True), args.sha256)
        original = helper("q2_prepare_contract").decode(
            protected.read(retry["original_plan_path"], LIMIT, noatime=True), retry["original_plan_sha256"])
        previous_pin = retry["predecessors"][1]
        previous = helper("q2_retry_contract").decode(
            protected.read(previous_pin["plan_path"], LIMIT, noatime=True), previous_pin["plan_sha256"])
        plan = contract.bind(original, retry, previous)
        guest = delivery.validate_delivery(protected.read(args.delivery_envelope, LIMIT, noatime=True),
            args.delivery_sha256, retry["attempt_id"], entry)
        d = helper("q2_prepare_driver")
        settings = d.validate_plan(plan)
        delivery.owner_admission(settings, guest, current_clock(), entry)
        issued, deadline = delivery.preparation_window(guest, entry)
        backend = helper("q2_startup_retry").StartupRetryBackend(plan, retry, issued_ns=issued,
            deadline_ns=deadline, boot_deadline_ns=guest["preparation_deadline_ns"], delivery_envelope=guest)
        backend.guard = delivery.preparation_guard(backend.guard, guest, current_clock)
        stage = "preflight"
        backend.preflight()
        stage = "reservation"
        backend.reserve()
        stage = "preparation"
        receipt = backend.prepare()
        if receipt.get("status") != "STARTUP_RETRY_RESOURCES_PREPARED":
            print(encoded(receipt).decode(), end="", flush=True)
            return 3
        # Backend verified and installed this exact immutable replacement source.
        sys.path.insert(0, receipt["facts"]["installation"]["source"]["root"] + "/tools")
        files = TrackedFiles(d.Files(backend.guard), backend.event)
        stage = "assembly"
        prepared, invocation = complete(plan, retry, receipt, files=files, command=backend.command,
            clock=current_clock, entry=entry, delivery_envelope=guest, verify_preserved=backend.verify_preserved,
            measure_costs=backend.measure_costs)
        print(encoded(prepared).decode(), end="", flush=True)
        stage = "owner_exec"
        os.execv(invocation[0], invocation)
        raise RuntimeError("STARTUP_RETRY_DRIVER_EXEC_RETURNED")
    except Exception as error:
        result = dict(schema=SCHEMA, status="INCOMPLETE" if backend is not None
            and getattr(backend, "reservation", None) is not None else "BLOCKED", reason=reason(error),
            q2_accepted=False, q3_accepted=False, production_supported=False,
            original_management_session_exit_required=True, old_verdicts_retained=True,
            automatic_replay_permitted=False, stage=stage)
        if guest is not None:
            result.update(attempt_id=retry["attempt_id"], retry_sha256=sha(encoded(retry)),
                delivery_sha256=sha(encoded(guest)), clock_anchor_sha256=guest["clock_anchor_sha256"])
        detail = error_details(error)
        if detail is not None:
            result["error_details"] = detail
        if backend is not None:
            directory = getattr(backend, "retry_directory", None)
            if directory is None and getattr(backend, "reservation", None) is not None:
                directory = dict(path=str(backend.reservation))
            result["retry_directory"] = directory
            detail = getattr(backend, "last_command_failure", None)
            if detail is not None:
                result["command_failure"] = detail
            if directory is not None:
                try:
                    backend.verify_preserved()
                    result["original_files_preserved"] = True
                except Exception as verify_error:
                    result["original_files_preserved"] = False
                    result["preservation_check_error"] = reason(verify_error)
                # This bounded final record is charged in the assembly reserve
                # and remains inside the outer envelope after preparation expiry.
                try:
                    now = current_clock()
                    require(guest is not None and now["boot_id"] == guest["boot_id"]
                        and guest["issued_ns"] <= now["boottime_ns"] < guest["deadline_ns"],
                        "STARTUP_RETRY_DRIVER_FINAL_RECORD_DEADLINE")
                    failure_raw = encoded(result)
                    require(len(failure_raw) <= ASSEMBLY_FILES["driver-failed.json"], "STARTUP_RETRY_DRIVER_ASSEMBLY_SIZE")
                    helper("q2_prepare").create_file(Path(directory["path"]) / "driver-failed.json", failure_raw)
                except Exception as persist_error:
                    result["failure_record_error"] = reason(persist_error)
        print(encoded(result).decode(), end="", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
