"""One explicit, bounded preparation recovery followed by the unissued Q2 run.

Original preparation bytes and candidate code remain unchanged. The recovery
receipt and derived authority have their own provenance; successful recovery
never rewrites the failed preparation receipt. No arguments perform no work.
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

SCHEMA = "local-hand-q2-recovery-driver-result/v1"
DELIVERY_SCHEMA = "local-hand-q2-recovery-delivery/v1"
AUTHORITY_SCHEMA = "local-hand-q2-recovery-authority/v1"
PREPARATION_NS = 140 * 10**9
GUEST_NS = 270 * 10**9
STOP_NS = 3 * 10**9
FINALIZATION_NS = 5 * 10**9
LIMIT = 2 * 1024 * 1024
ASSEMBLY_FILES = {"delivery-envelope.json": 4096, "first-request-issuance.json": 4096,
    "first-request.json": 16384, "authority.json": 65536, "manifest.json": 262144,
    "policy.json": 65536, "prepared.json": 65536, "handoff.json": LIMIT, "driver-failed.json": 65536}
ASSEMBLY_RESERVATION_INODES = len(ASSEMBLY_FILES) + 4
ASSEMBLY_RESERVATION_BYTES = sum(ASSEMBLY_FILES.values()) + ASSEMBLY_RESERVATION_INODES * 4096


def write(files, parent, name, value, **kwargs):
    require(name in ASSEMBLY_FILES and len(encoded(value)) <= ASSEMBLY_FILES[name], "RECOVERY_DRIVER_ASSEMBLY_SIZE")
    return files.write(parent, name, value, **kwargs)


def require(value, code):
    if not value:
        raise ValueError(code)


def reason(error):
    value = getattr(error, "code", str(error) if isinstance(error, ValueError) else type(error).__name__)
    return value if type(value) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else type(error).__name__


def helper(name):
    filename = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("_recovery_driver_" + name, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encoded(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    require(len(raw) <= LIMIT, "RECOVERY_DRIVER_RECORD_LIMIT")
    return raw


def sha(value):
    return hashlib.sha256(value).hexdigest()


def first_clock():
    """Anchor local clocks before reads; the caller's 140-second bound is inherited."""
    return dict(monotonic_ns=time.monotonic_ns(), boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME))


def delivery(raw, digest, recovery_id, entry):
    """The existing management caller supplies a durable absolute guest bound."""
    handoff = helper("q2_prepare_run")
    value = handoff.document(raw, digest)
    handoff.keys(value, {"schema", "recovery_id", "boot_id", "issued_ns", "deadline_ns", "stop_ns", "guest_outer_deadline_ns", "clock_anchor_sha256", "preparation_deadline_ns"})
    require(value["schema"] == DELIVERY_SCHEMA and value["recovery_id"] == recovery_id, "RECOVERY_DRIVER_DELIVERY_BINDING")
    handoff.integer(value["issued_ns"], 1)
    handoff.integer(value["deadline_ns"], value["issued_ns"] + 1)
    handoff.integer(value["guest_outer_deadline_ns"], value["deadline_ns"] + 10 * 10**9)
    require(type(value["clock_anchor_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["clock_anchor_sha256"]),
            "RECOVERY_DRIVER_CLOCK_ANCHOR")
    require(value["deadline_ns"] - value["issued_ns"] <= GUEST_NS and value["stop_ns"] == STOP_NS,
            "RECOVERY_DRIVER_DELIVERY_BUDGET")
    handoff.integer(value["preparation_deadline_ns"], value["issued_ns"] + 1)
    require(value["preparation_deadline_ns"] <= value["issued_ns"] + PREPARATION_NS
        and value["preparation_deadline_ns"] + 120 * 10**9 + STOP_NS + FINALIZATION_NS <= value["deadline_ns"],
        "RECOVERY_DRIVER_PREPARATION_BUDGET")
    require(value["issued_ns"] <= entry["boottime_ns"] < value["preparation_deadline_ns"], "RECOVERY_DRIVER_DELIVERY_EXPIRED")
    require(Path("/proc/sys/kernel/random/boot_id").read_text().strip() == value["boot_id"], "RECOVERY_DRIVER_BOOT_CHANGED")
    return value


def owner_admission(settings, delivery_envelope, now, entry):
    """Original first issuance only, with full owner/stop/EOF costs still left."""
    require(now["boot_id"] == delivery_envelope["boot_id"], "RECOVERY_DRIVER_BOOT_CHANGED")
    require(entry["boottime_ns"] <= now["boottime_ns"] < delivery_envelope["preparation_deadline_ns"],
            "RECOVERY_DRIVER_PREPARATION_EXPIRED")
    duration = settings["owner"]["runtime_ns"]
    require(duration <= 120 * 10**9 and now["boottime_ns"] + duration + STOP_NS + FINALIZATION_NS
            < delivery_envelope["deadline_ns"], "RECOVERY_DRIVER_OWNER_TIME_UNFUNDED")
    return duration


def preparation_window(delivery_envelope, entry):
    """Translate the bootstrap's fixed bound, including time already spent.

    BOOTTIME and MONOTONIC have a local offset; neither is a fresh preparation
    issuance. The monotonic sample precedes the boottime sample, making this
    translation conservative by the small sampling interval.
    """
    offset = entry["monotonic_ns"] - entry["boottime_ns"]
    issued = delivery_envelope["issued_ns"] + offset
    deadline = delivery_envelope["preparation_deadline_ns"] + offset
    require(issued > 0 and issued <= entry["monotonic_ns"] < deadline
        and deadline - issued <= PREPARATION_NS, "RECOVERY_DRIVER_PREPARATION_EXPIRED")
    return issued, deadline


def preparation_guard(original_guard, delivery_envelope, clock):
    """Also retain BOOTTIME expiry if the guest suspends during preparation."""
    def guard():
        original_guard()
        now = clock()
        require(now["boot_id"] == delivery_envelope["boot_id"], "RECOVERY_DRIVER_BOOT_CHANGED")
        require(delivery_envelope["issued_ns"] <= now["boottime_ns"]
            < delivery_envelope["preparation_deadline_ns"], "RECOVERY_DRIVER_PREPARATION_EXPIRED")
    return guard


def facts_from_recovery(plan, recovery, receipt, children, issuance=None):
    """Admit the real recovery result without changing any preparation status."""
    d = helper("q2_prepare_driver")
    require(receipt.get("schema") == "local-hand-q2-preparation-recovery/v1"
        and receipt.get("status") == "RESOURCES_RECOVERED"
        and all(receipt.get(key) is False for key in
            ("fixture_generated", "q2_accepted", "q3_accepted", "production_supported")),
        "RECOVERY_DRIVER_RESOURCES_NOT_RECOVERED")
    require(receipt.get("preparation_id") == plan["preparation_id"]
            and receipt.get("plan_sha256") == sha(encoded(plan)), "RECOVERY_DRIVER_PLAN_CHANGED")
    provenance = receipt["recovery"]
    require(provenance["id"] == recovery["recovery_id"]
            and provenance["plan_sha256"] == sha(encoded(recovery))
            and provenance["source"] == recovery["recovery_source"]
            and provenance["original_receipt_sha256"] == recovery["original_files"]["preparation-result.json"]
            and provenance["attested"] is True and provenance["original_files_preserved"] is True,
            "RECOVERY_DRIVER_PROVENANCE")
    observed = receipt["facts"]
    require(observed["retained_after"] == observed["retained_before"], "RECOVERY_DRIVER_RETAINED_CHANGED")
    authority = dict(schema=AUTHORITY_SCHEMA, scope=recovery["scope"], baseline=recovery["baseline"],
        preparation_id=plan["preparation_id"], plan_sha256=sha(encoded(plan)),
        original_failure_sha256=recovery["original_files"]["preparation-result.json"],
        recovery_plan_sha256=sha(encoded(recovery)), recovery_receipt_sha256=sha(encoded(receipt)),
        recovery_source=recovery["recovery_source"], recovery_id=recovery["recovery_id"],
        original_preparation_scope=plan["scope"], original_preparation_baseline=plan["baseline"])
    if issuance is not None:
        authority["first_request_issuance"] = copy.deepcopy(issuance)
    facts, authority, manifest = d.facts_from_observed(plan, observed, children, authority)
    if issuance is not None:
        # The preserved plan supplies identity/policy. Only the never-issued
        # synthetic request receives its explicit first expiry under this gate.
        facts["identity"]["expires_at"] = issuance["expires_at"]
    return facts, authority, manifest


def first_request(plan, recovery, settings, now, wall_ns, delivery_envelope, entry):
    owner_admission(settings, delivery_envelope, now, entry)
    require(type(wall_ns) is int and wall_ns > 0, "RECOVERY_DRIVER_WALL_CLOCK")
    seconds = min(900, settings["owner"]["runtime_ns"] // 10**9,
        (delivery_envelope["deadline_ns"] - now["boottime_ns"] - STOP_NS - FINALIZATION_NS) // 10**9)
    issued = wall_ns // 10**9
    require(seconds >= settings["original_budgets"]["wall_seconds"] + 10,
            "RECOVERY_DRIVER_REQUEST_TIME_UNFUNDED")
    return dict(schema="local-hand-q2-first-request-issuance/v1", preparation_id=plan["preparation_id"],
        recovery_id=recovery["recovery_id"], plan_sha256=sha(encoded(plan)),
        operation_id=settings["identity"]["operation_id"],
        old_template_expires_at=settings["identity"]["expires_at"],
        first_request_issued_at=issued, issued_boottime_ns=now["boottime_ns"], expires_at=issued + seconds,
        deadline_boottime_ns=now["boottime_ns"] + seconds * 10**9,
        original_request_unissued=True)


def complete(plan, recovery, receipt, *, files, command, clock, entry, delivery_envelope, verify_preserved,
             measure_costs, wall_clock=time.time_ns):
    """Append one real recovered assembly and issue the original owner once."""
    d = helper("q2_prepare_driver")
    a = helper("q2_prepare_assembly")
    handoff = helper("q2_prepare_run")
    settings = d.validate_plan(plan)
    # Validate provenance and observation shape before any child creation.
    placeholder = {name: {"path": "/unissued/" + name, "device": 0, "inode": 1}
        for name in (*a.PHASES, "management_evidence", "launcher_output", "launcher_declarations",
            "supervisor_output", "supervisor_declarations")}
    facts_from_recovery(plan, recovery, receipt, placeholder)
    owner_admission(settings, delivery_envelope, clock(), entry)
    observed = receipt["facts"]
    directories = observed["directories"]
    costs = measure_costs()
    block = max([4096] + [mount.get("block_bytes", 4096) for mount in observed["mounts"].values()])
    require(type(block) is int and block <= 65536 and block & (block - 1) == 0,
            "RECOVERY_DRIVER_ALLOCATION_BLOCK")
    state_bytes = sum((limit + block - 1) // block * block for limit in ASSEMBLY_FILES.values())
    state_bytes += ASSEMBLY_RESERVATION_INODES * block
    child_directories = len(a.PHASES) + 7
    require(costs["state"]["bytes"] + max(ASSEMBLY_RESERVATION_BYTES, state_bytes) <= plan["budgets"]["state_bytes"]
        and costs["state"]["inodes"] + ASSEMBLY_RESERVATION_INODES <= plan["budgets"]["state_inodes"]
        and costs["capture"]["bytes"] + (child_directories + 2) * block <= plan["budgets"]["capture_bytes"]
        and costs["capture"]["inodes"] + child_directories <= plan["budgets"]["capture_inodes"],
        "RECOVERY_DRIVER_ASSEMBLY_CAPACITY")
    reservation = receipt["recovery"]["directory"]
    require(reservation["path"] == plan["directories"]["reservation"]["path"] + "/" + recovery["recovery_id"],
            "RECOVERY_DRIVER_RESERVATION_BINDING")
    write(files, reservation, "delivery-envelope.json", delivery_envelope)
    children = {}
    for name in (*a.PHASES, "management_evidence", "launcher_output", "supervisor_output", "owner_output"):
        children[name] = files.directory(directories["capture"], name)
    for name in ("launcher_declarations", "supervisor_declarations", "owner_declarations"):
        children[name] = files.directory(directories["declarations"], name, 0o755 if name == "launcher_declarations" else 0o700)
    issuance = first_request(plan, recovery, settings, clock(), wall_clock(), delivery_envelope, entry)
    # Every required child was create-only; preflight proved the original
    # ledger and all handoff/grant/run objects absent. A prior assembly cannot
    # reach this single publication a second time.
    write(files, reservation, "first-request-issuance.json", issuance)
    facts, authority, manifest = facts_from_recovery(plan, recovery, receipt, children, issuance)
    assembled = a.assemble(facts)
    actual_request = assembled["supervisor_template"]["launcher"]["resident"]["request"]
    require(actual_request["operation_id"] == issuance["operation_id"]
        and actual_request["expires_at"] == issuance["expires_at"], "RECOVERY_DRIVER_REQUEST_BINDING")
    write(files, reservation, "first-request.json", dict(issuance=issuance, request=actual_request,
        authority_sha256=sha(encoded(authority))))
    write(files, reservation, "authority.json", authority)
    write(files, reservation, "manifest.json", manifest)
    uid, gid = facts["ordinary"]["uid"], facts["ordinary"]["gid"]
    policy = write(files, directories["authority"], "policy.json", assembled["policy"], owner=uid, gid=gid)
    python = facts["installation"]["programs"]["python"]["path"]
    # This ordinary initialization executes the unchanged original D entry.
    driver = facts["source"]["root"] + "/tests/e3_host/q2_prepare_driver.py"
    args = [facts["setpriv"]["path"], "--reuid=" + str(uid), "--regid=" + str(gid), "--clear-groups",
        "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all", "--no-new-privs", python, "-I", "-B", driver,
        "--initialize-ledger", policy["path"], "--sha256", policy["sha256"], "--ledger-id", assembled["ledger_id"]]
    ledger = helper("q2_prepare_contract").document(command(args))
    require(ledger["uid"] == uid and ledger["ledger_id"] == assembled["ledger_id"]
        and ledger["generation"] == assembled["chain"]["broker_generation"]
        and ledger["path"] == facts["paths"]["broker_root"] + "/jobs.sqlite", "RECOVERY_DRIVER_LEDGER_BINDING")
    prepared = dict(schema=SCHEMA, status="RECOVERED_PREPARED", source_commit=facts["source"]["commit"],
        preparation_id=plan["preparation_id"], recovery_id=recovery["recovery_id"],
        original_failure_sha256=recovery["original_files"]["preparation-result.json"],
        recovery_receipt_sha256=sha(encoded(receipt)), policy=policy, ledger=ledger,
        first_request_issuance=issuance, request_digest=actual_request["request_digest"],
        authority_sha256=sha(encoded(authority)), manifest_sha256=sha(encoded(manifest)),
        q2_accepted=False, q3_accepted=False, production_supported=False)
    write(files, reservation, "prepared.json", prepared)
    verify_preserved()
    now = clock()
    duration = owner_admission(settings, delivery_envelope, now, entry)
    require(now["boottime_ns"] + (settings["original_budgets"]["wall_seconds"] + 10) * 10**9
        < issuance["deadline_boottime_ns"] and wall_clock() // 10**9
        + settings["original_budgets"]["wall_seconds"] + 10 < issuance["expires_at"],
        "RECOVERY_DRIVER_REQUEST_TIME_UNFUNDED")
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
    owner_admission(settings, delivery_envelope, final_now, entry)
    require(final_now["boottime_ns"] + (settings["original_budgets"]["wall_seconds"] + 10) * 10**9
        < issuance["deadline_boottime_ns"] and wall_clock() // 10**9
        + settings["original_budgets"]["wall_seconds"] + 10 < issuance["expires_at"],
        "RECOVERY_DRIVER_REQUEST_TIME_UNFUNDED")
    # Do not create another owner if this create-only file or any child exists.
    return prepared, [python, "-I", "-B", facts["source"]["root"] + "/tests/e3_host/q2_prepare_run.py",
        "--plan", handoff_file["path"], "--sha256", handoff_file["sha256"]]


def main(argv=None):
    entry = first_clock()
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("plan", "sha256", "recovery", "recovery-sha256", "delivery-envelope", "delivery-sha256"):
        parser.add_argument("--" + flag)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    result = dict(schema=SCHEMA, status="BLOCKED", q2_accepted=False, q3_accepted=False, production_supported=False,
        original_management_session_exit_required=True)
    backend = None
    try:
        require(args.execute and all(getattr(args, flag.replace("-", "_")) for flag in
            ("plan", "sha256", "recovery", "recovery-sha256", "delivery-envelope", "delivery-sha256")),
            "EXPLICIT_RECOVERY_AND_DELIVERY_REQUIRED")
        require(sys.platform.startswith("linux") and sys.flags.isolated and sys.dont_write_bytecode
            and os.getuid() == os.geteuid() == 0, "RECOVERY_DRIVER_ISOLATED_ROOT_REQUIRED")
        handoff = helper("q2_prepare_run")
        contract = helper("q2_prepare_contract")
        recovery_module = helper("q2_prepare_recovery")
        recovery = recovery_module.decode(handoff.protected(args.recovery), args.recovery_sha256)
        plan = contract.decode(handoff.protected(args.plan), args.sha256)
        require(sha(encoded(plan)) == recovery["plan_sha256"], "RECOVERY_DRIVER_PLAN_CHANGED")
        guest = delivery(handoff.protected(args.delivery_envelope), args.delivery_sha256, recovery["recovery_id"], entry)
        # Original runtime/assembly libraries stay bound to the original candidate.
        sys.path.insert(0, plan["candidate"]["source"] + "/tools")
        d = helper("q2_prepare_driver")
        settings = d.validate_plan(plan)
        from local_hand_jobs.budget import current_clock
        owner_admission(settings, guest, current_clock(), entry)
        # Leave the entire original owner plus stop/EOF allowance untouched.
        # A shortened management window can only reduce preparation time.
        issued, deadline = preparation_window(guest, entry)
        backend = recovery_module.RecoveryBackend(plan, recovery, issued_ns=issued, deadline_ns=deadline)
        backend.guard = preparation_guard(backend.guard, guest, current_clock)
        receipt = recovery_module.recover(plan, recovery, backend=backend,
            validate_settings=lambda _: d.validate_plan(plan), issued_ns=issued, deadline_ns=deadline)
        result = receipt
        if receipt.get("status") != "RESOURCES_RECOVERED":
            print(encoded(result).decode(), end="", flush=True)
            return 3
        files = d.Files(backend.guard)
        prepared, invocation = complete(plan, recovery, receipt, files=files, command=backend.command,
            clock=current_clock, entry=entry, delivery_envelope=guest, verify_preserved=backend.verify_preserved,
            measure_costs=backend.measure_costs)
        print(encoded(prepared).decode(), end="", flush=True)
        os.execv(invocation[0], invocation)
        raise RuntimeError("RECOVERY_DRIVER_EXEC_RETURNED")
    except Exception as error:
        result = dict(schema=SCHEMA, status="INCOMPLETE" if args.execute else "BLOCKED", reason=reason(error),
            q2_accepted=False, q3_accepted=False, production_supported=False,
            original_management_session_exit_required=True)
        if backend is not None:
            result["recovery_directory"] = backend.recovery_directory
            detail = getattr(backend, "last_command_failure", None)
            if detail is not None:
                result["command_failure"] = detail
            if backend.recovery_directory is not None:
                # One bounded append is owned by the still-running outer
                # management envelope even when preparation time has expired.
                try:
                    failure_raw = encoded(result)
                    require(len(failure_raw) <= ASSEMBLY_FILES["driver-failed.json"], "RECOVERY_DRIVER_ASSEMBLY_SIZE")
                    helper("q2_prepare").create_file(
                        Path(backend.recovery_directory["path"]) / "driver-failed.json", failure_raw)
                except Exception as persist_error:
                    result["failure_record_error"] = reason(persist_error)
        print(encoded(result).decode(), end="", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
