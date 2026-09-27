"""Read-only dual-predecessor admission and create-only startup retry preparation.

This is test-only orchestration. Historical attempts and the separately pinned
runtime are immutable inputs; neither is imported under a replacement identity.
"""
from __future__ import annotations

import copy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import time


def helper(name):
    spec = importlib.util.spec_from_file_location("_startup_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = helper("q2_retry")
p, c = legacy.p, legacy.c
SCHEMA = "local-hand-q2-supervisor-startup-retry-preparation/v1"
KINDS = ("CPUQUOTA_PARSE_BEFORE_CHILD", "SUPERVISOR_STARTED_PERMISSION_FAILURE")
CATEGORIES = legacy.CATEGORIES
REUSED = legacy.REUSED
INSTALL_PEAK = dict(bytes=64 * 1024**2, inodes=4096)
PERMISSION_FAILURE = dict(original_management_session_exit_required=True,
    owner_self_exit_verified=False, production_supported=False, q2_accepted=False,
    q3_accepted=False, reason="PermissionError", schema="local-hand-q2-handoff-result/v1", status="BLOCKED")
FAILED_PROPERTIES = ("Id", "LoadState", "ActiveState", "SubState", "InvocationID", "MainPID",
    "ControlPID", "Job", "ControlGroup", "ExecMainCode", "ExecMainStatus", "Result")


def fields(raw):
    result = {}
    for line in raw.decode("utf-8").splitlines():
        c.require("=" in line, "STARTUP_UNIT_OUTPUT")
        key, value = line.split("=", 1)
        c.require(key not in result, "STARTUP_UNIT_DUPLICATE")
        result[key] = value
    return result


def supervisor_argv(envelope, envelope_path, digest):
    """Reconstruct the second predecessor's fixed, repaired CPUQuota command."""
    argv = legacy.legacy_argv(envelope, envelope_path, digest)
    quota = c.cpu_quota_percent(envelope["fixture"]["supervisor_envelope"]["controller"]["cpu_quota_per_sec_usec"])
    return ["--property=CPUQuota=" + quota if item.startswith("--property=CPUQuota=") else item for item in argv]


def owner_records(raw, envelope_raw, handoff_raw, returncode):
    """Shared historical capture checks; none infer successful stopping."""
    c.require(set(raw) == legacy.OWNER_FILES, "STARTUP_OWNER_MEMBERS")
    records = {name: c.document(value) for name, value in raw.items() if name.endswith(".json")}
    capture = records["capture.json"]
    c.keys(capture, ("client_pid", "close_errors", "complete", "deadline_ns", "eof", "error",
        "independent_stop_required", "pipe_identities", "production_supported", "q3_accepted", "returncode",
        "schema", "started_ns", "stderr_sha256", "stdout_sha256"))
    c.require(capture["schema"] == "local-hand-q2-outer-capture/v1" and capture["complete"] is True
        and type(capture["returncode"]) is int and capture["returncode"] == returncode
        and capture["independent_stop_required"] is True and capture["production_supported"] is False
        and capture["q3_accepted"] is False, "STARTUP_CAPTURE_SCHEMA")
    c.number(capture["client_pid"], 1); c.number(capture["started_ns"], 1)
    c.number(capture["deadline_ns"], capture["started_ns"] + 1)
    pipes = capture["pipe_identities"]; c.keys(pipes, ("stdout", "stderr"))
    for identity in pipes.values():
        c.require(type(identity) is list and len(identity) == 2, "STARTUP_PIPE_IDENTITY")
        c.number(identity[0], 1); c.number(identity[1], 1)
    c.require(pipes["stdout"] != pipes["stderr"], "STARTUP_PIPE_ALIAS")
    result = records["result.json"]
    c.keys(result, ("cleanup_errors", "evidence", "original_management_session_exit_required", "owner_self_exit_verified",
        "production_supported", "q2_accepted", "q3_accepted", "reason", "schema", "scope", "sealed", "status"))
    c.require(result["schema"] == "local-hand-q2-handoff-result/v1"
        and result["owner_self_exit_verified"] is False and result["original_management_session_exit_required"] is True
        and result["production_supported"] is False and result["q3_accepted"] is False, "STARTUP_OWNER_RESULT_SCHEMA")
    envelope, handoff = c.document(envelope_raw), c.document(handoff_raw)
    c.keys(envelope, ("schema", "plan", "fixture"))
    c.require(envelope["plan"] == handoff, "STARTUP_ENVELOPE_BINDING")
    expected = copy.deepcopy(handoff["template"])
    issued = envelope["fixture"]["supervisor_envelope"]["issued_ns"]
    c.number(issued, handoff["owner_envelope"]["issued_ns"])
    for role in (expected["supervisor_envelope"], expected["launcher"]["controller_envelope"]):
        role.update(issued_ns=issued, deadline_ns=issued + role["controller"]["runtime_max_usec"] * 1000)
    c.require(envelope["fixture"] == expected, "STARTUP_ISSUED_TEMPLATE_CHANGED")
    c.require(expected["supervisor_envelope"]["deadline_ns"] < handoff["owner_envelope"]["deadline_ns"],
        "STARTUP_ORIGINAL_DEADLINE")
    return records


def attest_supervisor_startup(raw, envelope_raw, handoff_raw, prepared):
    """Validate the actual executed failure, retaining its incomplete stop proof."""
    c.require(set(raw) == legacy.OWNER_FILES and raw["supervisor.stdout"] == c.encoded(PERMISSION_FAILURE)
        and raw["supervisor.stderr"] == b"", "STARTUP_FAILURE_BOUNDARY")
    records = owner_records(raw, envelope_raw, handoff_raw, 3)
    envelope, handoff = c.document(envelope_raw), c.document(handoff_raw)
    c.require(envelope.get("schema") == "local-hand-q2-issued-handoff/v1" and envelope.get("plan") == handoff,
        "STARTUP_ENVELOPE_BINDING")
    capture, delivery, result = (records[name] for name in ("capture.json", "delivery.json", "result.json"))
    c.require(capture.get("complete") is True and type(capture.get("returncode")) is int
        and capture["returncode"] == 3 and capture.get("eof") == ["stderr", "stdout"]
        and capture.get("error") is None and capture.get("close_errors") == []
        and capture.get("stdout_sha256") == p.sha(raw["supervisor.stdout"])
        and capture.get("stderr_sha256") == p.sha(raw["supervisor.stderr"]), "STARTUP_CAPTURE")
    c.require(result.get("status") == "INCOMPLETE" and result.get("reason") == "SUPERVISOR_DELIVERY_UNCERTAIN"
        and result.get("sealed") is False and result.get("q2_accepted") is False
        and result.get("cleanup_errors") == [] and records["stop.json"] == {}, "STARTUP_ORIGINAL_VERDICT")
    argv = supervisor_argv(envelope, handoff["declarations"]["path"] + "/envelope.json", p.sha(envelope_raw))
    unit = envelope["fixture"]["supervisor_envelope"]["controller"]["unit"]
    c.require(delivery.get("argv_sha256") == p.sha(c.encoded(argv)) and delivery.get("unit") == unit
        and delivery.get("cpu_quota_format") == "systemd-percent-hundredths/v1"
        and delivery.get("started_ns") == capture.get("started_ns")
        and delivery.get("deadline_ns") == capture.get("deadline_ns") == handoff["owner_envelope"]["deadline_ns"],
        "STARTUP_COMMAND_BINDING")
    reservation = records["reservation.json"]
    c.require(reservation.get("envelope_sha256") == p.sha(envelope_raw)
        and reservation.get("plan_sha256") == p.sha(handoff_raw), "STARTUP_ISSUANCE")
    controls = records["controls.json"]
    c.require(type(controls) is list and len(controls) == 2, "STARTUP_CONTROLS")
    for index, record in enumerate(controls):
        c.require(record.get("complete") is True and record.get("returncode") == 0
            and record.get("eof") == ["stderr", "stdout"] and record.get("error") is None
            and record.get("stderr_hex") == "", "STARTUP_CONTROLS")
        observed = fields(bytes.fromhex(record["stdout_hex"]))
        c.require(observed.get("Id") == unit and observed.get("ActiveState") == "inactive"
            and observed.get("SubState") == "dead" and observed.get("MainPID") == observed.get("ControlPID") == "0"
            and observed.get("InvocationID") == observed.get("ControlGroup") == "", "STARTUP_ORIGINAL_CONTROL_BOUNDARY")
        if index == 0:
            c.require(observed.get("LoadState") == "not-found" and observed.get("Job") == "", "STARTUP_BEFORE_DELIVERY")
        else:
            # This is the actual old queued observation. It is not exit/stop
            # evidence; the separately pinned FAILED instance is checked live.
            c.require(observed.get("LoadState") == "loaded" and re.fullmatch(r"[1-9][0-9]*", observed.get("Job", ""))
                and observed.get("ExecMainCode") == observed.get("ExecMainStatus") == "0", "STARTUP_ORIGINAL_QUEUE")
    c.require(prepared.get("schema") == "local-hand-q2-cpuquota-retry-driver-result/v1"
        and prepared.get("status") == "RETRY_PREPARED" and prepared.get("q2_accepted") is False
        and prepared.get("original_owner_issued") is True and prepared.get("original_verdict_retained") is True,
        "STARTUP_PREPARED")
    return dict(kind=KINDS[1], original_owner_issued=True, original_status="INCOMPLETE",
        original_reason="SUPERVISOR_DELIVERY_UNCERTAIN", argv_sha256=delivery["argv_sha256"],
        capture_sha256=p.sha(raw["capture.json"]), original_stop_proven=False, original_seal_proven=False)


def attest_cpuquota_startup(raw, envelope_raw, handoff_raw, prepared):
    owner_records(raw, envelope_raw, handoff_raw, 1)
    result = legacy.attest_startup(raw, envelope_raw, handoff_raw, prepared)
    return dict(result, kind=KINDS[0], original_stop_proven=False, original_seal_proven=False)


def attest_failed_unit(pin, observed):
    c.require(set(observed) == set(FAILED_PROPERTIES), "STARTUP_FAILED_UNIT_FIELDS")
    c.require(observed["Id"] == pin["unit"] and observed["LoadState"] == "loaded"
        and observed["ActiveState"] == observed["SubState"] == "failed"
        and observed["InvocationID"] == pin["invocation_id"] and re.fullmatch(r"[0-9a-f]{32}", observed["InvocationID"])
        and observed["ExecMainCode"] == str(pin["exec_main_code"]) == "1"
        and observed["ExecMainStatus"] == str(pin["exec_main_status"]) == "3"
        and observed["Result"] == "exit-code" and observed["MainPID"] == observed["ControlPID"] == "0"
        and observed["Job"] in ("", "0") and observed["ControlGroup"] == "", "STARTUP_FAILED_UNIT_CHANGED")
    return dict(pin, observed=observed)


def tree_snapshot(path, guard, *, seen=None, hash_files=True):
    """Count physical occupancy once and preserve atime as part of the proof."""
    pending = [Path(path)]; seen = set() if seen is None else seen
    rows = []; total = 0; device = None
    while pending:
        guard(); name = pending.pop(); info = name.lstat(); key = (info.st_dev, info.st_ino)
        c.require(key not in seen and not stat.S_ISLNK(info.st_mode), "STARTUP_TREE_ALIAS")
        if device is None: device = info.st_dev
        c.require(info.st_dev == device, "STARTUP_TREE_MOUNT")
        seen.add(key); total += max(info.st_size, info.st_blocks * 512)
        c.require(len(rows) < 32768 and total <= 256 * 1024**2, "STARTUP_TREE_LIMIT")
        row = p.identity(info, str(name))
        row.update(size=info.st_size, atime_ns=info.st_atime_ns, mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns)
        directory = stat.S_ISDIR(info.st_mode)
        c.require(directory or stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "STARTUP_TREE_TYPE")
        fd = p.opened(name, directory=directory, owner=info.st_uid, noatime=True)
        try:
            c.require(p.identity(os.fstat(fd)) == p.identity(info), "STARTUP_TREE_CHANGED")
            if directory:
                with os.scandir(fd) as entries:
                    for entry in entries:
                        c.require(len(pending) + len(rows) < 32768, "STARTUP_TREE_LIMIT")
                        pending.append(name / entry.name)
            elif hash_files:
                row["sha256"] = p.sha(p.read_fd(fd, 256 * 1024**2))
            after = os.fstat(fd)
            c.require(all(getattr(info, key) == getattr(after, key) for key in
                ("st_dev", "st_ino", "st_size", "st_atime_ns", "st_mtime_ns", "st_ctime_ns")), "STARTUP_TREE_CHANGED")
        finally: os.close(fd)
        rows.append(row)
    guard()
    return dict(path=str(path), device=device, bytes=total, inodes=len(rows),
        sha256=p.sha(c.encoded(sorted(rows, key=lambda row: row["path"]))))


def runtime_storage(settings):
    return {key: 3 * settings["management"]["storage_" + key] + settings["owner"]["storage_" + key]
        + sum(row["storage_" + key] for row in settings["controllers"].values()) for key in ("bytes", "inodes")}


def historical_child_units(handoff):
    """Names fixed before delivery; never invent clocks for unissued grants."""
    names = set()
    for phase in handoff["template"]["launcher"]["assembly"]["phases"].values():
        request = phase["grant"]["request"]
        execution = request["execution_id"]
        for suffix in ("", ":bootstrap", ":result_reader"):
            names.add("lhj-" + hashlib.sha256((execution + suffix).encode()).hexdigest() + ".service")
        # Actual historical chain templates have no issued clock. If a full
        # issued request is present, its exact canonical digest also fixes the
        # query/listener/admission identities; absent clocks confer no identity.
        if "issued_ns" in request or "deadline_ns" in request:
            from local_hand_jobs import quota_contract
            issued = quota_contract.decode_request(c.encoded(request))
            names.update(prefix + issued.digest + ".service" for prefix in ("lhqo-", "lhqoc-", "lhqoa-"))
    return names


def reservation_obligations(retry, histories, records):
    """Normalize nested historical reservations without treating ceilings as grants.

    The original installation's 192 MiB appears in preparation and recovery;
    it is one retained obligation. The second bootstrap's base includes old
    actual occupancy, so only its separately declared 64 MiB increment is new.
    Neither successful installation nor expired execution time releases these
    retained storage commitments.
    """
    rows = retry["reservations"]; by_kind = {}
    for row in rows:
        by_kind.setdefault(row["kind"], []).append(row)
        c.require(row["path"] in records, "STARTUP_RESERVATION_MISSING")
    def one(kind):
        selected = by_kind.get(kind, [])
        c.require(len(selected) == 1, "STARTUP_RESERVATION_COVERAGE")
        return selected[0], records[selected[0]["path"]]
    original, previous = histories
    _, initial = one("PREPARATION_CEILING")
    c.require(initial == original, "STARTUP_ORIGINAL_CEILING_CHANGED")
    _, preflight = one("PREPARATION_SNAPSHOT")
    c.require(preflight["host"] == original["host"], "STARTUP_PREFLIGHT_BINDING")
    _, recovery = one("RECOVERY_SNAPSHOT")
    c.require(recovery["plan"]["plan_sha256"] == retry["original_plan_sha256"], "STARTUP_RECOVERY_RESERVATION_BINDING")
    _, retry_intent = one("RETRY_SNAPSHOT")
    c.require(p.sha(c.encoded(retry_intent["retry"])) == retry["predecessors"][1]["plan_sha256"],
        "STARTUP_PREVIOUS_RESERVATION_BINDING")
    stage_descriptor, stage = one("RECOVERY_STAGE")
    roots = {str(Path(name).parent) for name in recovery["plan"]["recovery_source"]["files"]}
    c.require(len(roots) == 1 and str(Path(stage_descriptor["path"]).parent) in roots
        and Path(stage_descriptor["path"]).name == "stage.json"
        and stage["schema"] == "local-hand-q2-recovery-stage/v1"
        and stage["original_plan_sha256"] == retry["original_plan_sha256"]
        and stage["source_commit"] == recovery["plan"]["recovery_source"]["commit"]
        and stage["source_tree"] == recovery["plan"]["recovery_source"]["tree"]
        and stage["recovery_id"] == recovery["plan"]["recovery_id"] and stage["q2_accepted"] is False,
        "STARTUP_RECOVERY_STAGE_BINDING")
    _, bootstrap = one("BOOTSTRAP_ATTESTATION")
    boot_rows = by_kind.get("BOOTSTRAP_COMMITMENT", [])
    owners = by_kind.get("OWNER_COMMITMENT", [])
    c.require(len(boot_rows) == len(owners) == 2, "STARTUP_RESERVATION_COVERAGE")
    result = []
    def add(identity, category, amount, paths, evidence, *, shared=False):
        for key in ("bytes", "inodes"): c.number(amount[key], 0)
        result.append(dict(id=identity, category=category, commitment=amount, covered_paths=list(paths), evidence=list(evidence),
            accounting_categories=["capture", "journal"] if shared else [category]))
    for index, plan in enumerate(histories):
        candidate = plan["candidate"]
        intent_path = str(Path(candidate["source"]).parent) + ".intent.json"
        matches = [row for row in boot_rows if row["path"] == intent_path]
        c.require(len(matches) == 1, "STARTUP_BOOTSTRAP_RESERVATION_BINDING")
        record = records[intent_path]
        c.require(record["schema"] == "local-hand-q2-delivery/v1" and record["status"] == "RESERVED"
            and record["destination"] == str(Path(candidate["source"]).parent)
            and record["ceiling_bytes"] == original["budgets"]["installation_bytes"]
            and record["fixture_provisioned"] is False and record["q2_accepted"] is False,
            "STARTUP_BOOTSTRAP_RECORD")
        for key in ("staging_bytes", "installation_reservation_bytes", "retained_delivery_bytes"):
            c.number(record[key], 0)
        c.number(record["issued_ns"], 1); c.number(record["deadline_ns"], record["issued_ns"] + 1)
        if index == 0:
            c.require(record["installation_reservation_bytes"] == stage["installation_future_reserved_bytes"] == 192 * 1024**2,
                "STARTUP_NESTED_INSTALLATION_COMMITMENT")
            # RecoveryBackend.install/preflight bound this same installed
            # candidate to 8192 inodes. This is its retained implementation
            # reservation, not the plan's larger installation inode ceiling.
            install = dict(bytes=record["installation_reservation_bytes"], inodes=8192)
            # The initial archive did not issue a separate inode grant. Its
            # current staged objects remain counted as actual occupancy.
            staging_inodes = 0
        else:
            transfer = dict(bootstrap["transfer"])
            c.require(transfer.pop("status") == "EXTRACTED", "STARTUP_BOOTSTRAP_TRANSFER")
            staging_inodes = transfer.pop("entries") + 3
            c.require(dict(transfer, status="RESERVED") == record, "STARTUP_BOOTSTRAP_TRANSFER")
            base = bootstrap["costs"]["installation"]["bytes"]; c.number(base, 0)
            c.require(record["installation_reservation_bytes"] - base == INSTALL_PEAK["bytes"]
                and record["retained_delivery_bytes"] == 0, "STARTUP_BOOTSTRAP_INCREMENT")
            install = dict(INSTALL_PEAK)
        add(intent_path + "#installation", "installation", install, [candidate["destination"]], [intent_path])
        add(intent_path + "#staging", "installation",
            dict(bytes=record["staging_bytes"] + record["retained_delivery_bytes"] + 8192, inodes=staging_inodes),
            [record["destination"], intent_path], [intent_path])
        owner_path = retry["predecessors"][index]["owner_output"] + "/reservation.json"
        owner = records[owner_path]; expected = runtime_storage(plan["settings"])
        c.require(all(owner["costs"]["storage_" + key] == expected[key] for key in expected),
            "STARTUP_OWNER_STORAGE_COMMITMENT")
        owner_row = next(row for row in owners if row["path"] == owner_path)
        # The issued management budget covers its journal cells and capture
        # together. Credit all three actual trees against this one pool;
        # journal is not a second independently issued reservation.
        add(owner_path, "capture", expected,
            [*owner_row["covered_paths"], plan["directories"]["journal"]["path"]], [owner_path], shared=True)
    stage_root = str(Path(stage_descriptor["path"]).parent.parent)
    add(stage_descriptor["path"], "installation",
        dict(bytes=stage["reserved_new_bytes"], inodes=stage["reserved_new_inodes"]), [stage_root],
        [stage_descriptor["path"]])
    # No two obligations may spend the same actual object to cancel unspent
    # reservations. The shared original installation was normalized above.
    paths = [name for row in result for name in row["covered_paths"]]
    c.require(all(not c.overlap(a, b) for i, a in enumerate(paths) for b in paths[i + 1:]), "STARTUP_RESERVATION_DOUBLE_COVERAGE")
    return result


class StartupRetryBackend(legacy.RetryBackend):
    """Reuse bounded OS primitives, never the old single-predecessor admission."""
    def __init__(self, plan, retry, issued_ns, deadline_ns, *, boot_deadline_ns=None, delivery_envelope=None):
        p.LinuxBackend.__init__(self, plan)
        c.require(type(issued_ns) is int and type(deadline_ns) is int and
            issued_ns <= time.monotonic_ns() < deadline_ns <= issued_ns + 140 * 10**9, "STARTUP_DEADLINE")
        self.issued_ns, self.deadline, self.boot_deadline_ns = issued_ns, deadline_ns, boot_deadline_ns
        self.delivery_envelope = copy.deepcopy(delivery_envelope)
        contract = helper("q2_startup_retry_contract")
        self.retry = contract.decode(c.encoded(retry), p.sha(c.encoded(retry)))
        self.old = c.decode(p.read(retry["original_plan_path"], c.LIMIT, noatime=True), retry["original_plan_sha256"])
        prior = retry["predecessors"][1]
        self.previous_retry = helper("q2_retry_contract").decode(
            p.read(prior["plan_path"], c.LIMIT, noatime=True), prior["plan_sha256"])
        self.previous = helper("q2_retry_contract").bind(self.old, self.previous_retry)
        c.require(contract.bind(self.old, retry, self.previous_retry) == plan, "STARTUP_DERIVED_PLAN")
        self.histories = [self.old, self.previous]
        self.old_prepared = self.old_handoff = None
        self.old_snapshots = self.attestation = None
        self.old_hashes = dict(retry["old_files"])
        self.costs = {}; self.started = set(); self.configuration = {}
        self.candidate_checked = False; self.skip_candidate = False
        self.prepared_history = []; self.handoff_history = []
        self.reservation_records = {}; self.reservation_proofs = []

    def old_file_owner(self, name):
        for plan in self.histories:
            for item in plan["directories"].values():
                if item["owner"] == "ordinary" and (str(name) == item["path"] or Path(item["path"]) in Path(name).parents):
                    return plan["account"]["uid"]
        return 0

    def old_raw(self, name):
        self.guard(); name = str(name)
        c.require(name in self.retry["old_files"], "STARTUP_OLD_PIN_MISSING")
        maximum = 8 * 1024**2 if name in {item["ledger"]["path"] for item in self.retry["predecessors"]} else c.LIMIT
        raw = p.read(name, maximum, owner=self.old_file_owner(name), noatime=True)
        c.require(p.sha(raw) == self.retry["old_files"][name], "STARTUP_OLD_FILE_CHANGED")
        return raw

    def old_document(self, name):
        return c.document(self.old_raw(name))

    def verify_old_hashes(self):
        for name in self.retry["old_files"]: self.old_raw(name)

    def attest_bundle(self, index, prepared, handoff):
        item = self.retry["predecessors"][index]; plan = self.histories[index]
        parent = Path(item["prepared_path"]).parent
        authority = self.old_document(parent / "authority.json")
        manifest_raw = self.old_raw(parent / "manifest.json")
        c.require(prepared["authority_sha256"] == p.sha(self.old_raw(parent / "authority.json"))
            and prepared["manifest_sha256"] == p.sha(manifest_raw)
            and prepared["source_commit"] == plan["candidate"]["commit"]
            and prepared["ledger"] == item["ledger"] and prepared["policy"]["path"] == item["policy_path"],
            "STARTUP_PREPARED_BINDING")
        policy = self.old_document(item["policy_path"])
        c.require(policy["authority_id"] == plan["settings"]["identity"]["authority_id"]
            and policy["source_commit"] == plan["candidate"]["commit"], "STARTUP_POLICY_BINDING")
        if index == 0:
            receipt = self.old_document(parent / "recovery-result.json")
            c.require(receipt["schema"] == "local-hand-q2-preparation-recovery/v1"
                and receipt["status"] == "RESOURCES_RECOVERED" and receipt["q2_accepted"] is False
                and authority["recovery_receipt_sha256"] == p.sha(self.old_raw(parent / "recovery-result.json")),
                "STARTUP_RECOVERY_BINDING")
            issuance = self.old_document(parent / "first-request-issuance.json")
            request = self.old_document(parent / "first-request.json")
            c.require(prepared["first_request_issuance"] == authority["first_request_issuance"] == issuance,
                "STARTUP_FIRST_ISSUANCE_BINDING")
            c.require(prepared["recovery_id"] == parent.name, "STARTUP_RECOVERY_INSTANCE_BINDING")
            recovery = self.old_document(parent / "recovery-intent.json")["plan"]["recovery_source"]
            c.require(any(Path(name).name == "q2_prepare_recovery.py" for name in recovery["files"]),
                "STARTUP_RECOVERY_RESERVATION_SOURCE")
            for name, digest in recovery["files"].items():
                self.guard()
                c.require(p.sha(p.read(name, c.LIMIT, noatime=True)) == digest, "STARTUP_RECOVERY_SOURCE_CHANGED")
        else:
            receipt = self.old_document(parent / "retry-preparation.json")
            intent = self.old_document(parent / "retry-intent.json")
            c.require(receipt["schema"] == "local-hand-q2-cpuquota-retry-preparation/v1"
                and receipt["status"] == "RETRY_RESOURCES_PREPARED" and receipt["q2_accepted"] is False
                and prepared["retry_receipt_sha256"] == authority["retry_receipt_sha256"]
                    == p.sha(self.old_raw(parent / "retry-preparation.json"))
                and receipt["retry_sha256"] == authority["retry_plan_sha256"] == item["plan_sha256"]
                and receipt["plan_sha256"] == authority["derived_plan_sha256"] == p.sha(c.encoded(plan))
                and intent["retry"] == self.previous_retry and intent["attestation"] == receipt["retry"]["attestation"]
                and intent["attestation_sha256"] == receipt["retry"]["attestation_sha256"]
                    == p.sha(c.encoded(intent["attestation"])), "STARTUP_PREVIOUS_RETRY_BINDING")
            c.require(prepared["supersedes_handoff_sha256"] == self.retry["old_files"][self.retry["predecessors"][0]["handoff_path"]],
                "STARTUP_PREDECESSOR_CHAIN")
            issuance = self.old_document(parent / "new-request-issuance.json")
            request = self.old_document(parent / "new-request.json")
            c.require(prepared["new_request_issuance"] == authority["new_request_issuance"] == issuance,
                "STARTUP_NEW_ISSUANCE_BINDING")
        c.require(request["authority_sha256"] == prepared["authority_sha256"] and request["issuance"] == issuance
            and request["request"]["request_digest"] == prepared["request_digest"]
            and request["request"] == handoff["template"]["launcher"]["resident"]["request"], "STARTUP_REQUEST_BINDING")
        source = handoff["template"]["launcher"]["source"]
        installation = handoff["template"]["launcher"]["assembly"]["installation"]
        c.require(source["commit"] == installation["source_commit"] == plan["candidate"]["commit"], "STARTUP_RUNTIME_BINDING")
        root = Path(plan["candidate"]["destination"]) / "source"
        for name, digest in source["files"].items():
            self.guard(); c.require(not Path(name).is_absolute() and ".." not in Path(name).parts, "STARTUP_SOURCE_PATH")
            c.require(p.sha(p.read(root / name, 4 * 1024**2, noatime=True)) == digest, "STARTUP_SOURCE_CHANGED")
        for program in installation["programs"].values():
            c.require(p.sha(p.read(program["path"], 64 * 1024**2, noatime=True)) == program["sha256"], "STARTUP_PROGRAM_CHANGED")
        return policy

    def attest_predecessors(self):
        proofs, ledgers, prepared_all, handoffs = [], [], [], []
        for index, item in enumerate(self.retry["predecessors"]):
            self.guard(); prepared = self.old_document(item["prepared_path"])
            handoff_raw = self.old_raw(item["handoff_path"]); handoff = c.document(handoff_raw)
            envelope_path = handoff["declarations"]["path"] + "/envelope.json"
            envelope_raw = self.old_raw(envelope_path)
            legacy.require_members(item["owner_output"], legacy.OWNER_FILES, "STARTUP_OWNER_MEMBERS")
            raw = {name: self.old_raw(Path(item["owner_output"]) / name) for name in legacy.OWNER_FILES}
            if index == 0:
                proof = attest_cpuquota_startup(raw, envelope_raw, handoff_raw, prepared)
            else: proof = attest_supervisor_startup(raw, envelope_raw, handoff_raw, prepared)
            policy = self.attest_bundle(index, prepared, handoff)
            legacy.require_members(handoff["declarations"]["path"], {"envelope.json"}, "STARTUP_OLD_CHILD_CREATED")
            fixture = c.document(envelope_raw)["fixture"]
            for pin in (fixture["declarations"], fixture["output"], fixture["launcher"]["declarations"], fixture["launcher"]["output"]):
                legacy.require_members(pin["path"], set(), "STARTUP_OLD_CHILD_CREATED")
            ledger = legacy.attest_ledger(item["ledger"]["path"], item["ledger"], policy["authority_id"], self.guard)
            c.require(ledger["sha256"] == self.retry["old_files"][item["ledger"]["path"]], "STARTUP_LEDGER_CHANGED")
            current = os.stat(item["ledger"]["path"], follow_symlinks=False)
            c.require((current.st_dev, current.st_ino, current.st_uid, stat.S_IMODE(current.st_mode)) ==
                tuple(item["ledger"][key] for key in ("device", "inode", "uid", "mode")), "STARTUP_LEDGER_PATH_CHANGED")
            proof.update(plan_sha256=item["plan_sha256"], prepared_sha256=self.retry["old_files"][item["prepared_path"]],
                handoff_sha256=self.retry["old_files"][item["handoff_path"]], owner_output=item["owner_output"])
            proofs.append(proof); ledgers.append(ledger); prepared_all.append(prepared); handoffs.append(handoff)
        self.prepared_history, self.handoff_history = prepared_all, handoffs
        self.old_prepared, self.old_handoff = prepared_all[0], handoffs[0]
        return proofs, ledgers

    def old_root_pins(self):
        result = None
        for handoff in self.handoff_history:
            current = {}
            for phase in handoff["template"]["launcher"]["assembly"]["phases"].values():
                grant = phase["grant"]
                for root in grant["roots"]:
                    paths = [name for name, pin in grant["allocation"]["paths"].items()
                        if (pin["device"], pin["inode"]) == (root["device"], root["inode"])]
                    c.require(len(paths) == 1, "STARTUP_ROOT_PIN")
                    row = dict(root, path=paths[0]); key = root["project_id"]
                    c.require(key not in current or current[key] == row, "STARTUP_ROOT_CONFLICT")
                    current[key] = row
            c.require(len(current) == 7 and (result is None or current == result), "STARTUP_JOINT_ROOT_BINDING")
            result = current
        c.require(result is not None, "STARTUP_ROOT_ATTESTATION_REQUIRED")
        return result

    def historical_show(self, unit):
        raw = self.command([self.tool("systemctl"), "--system", "show", unit,
            "--property=" + ",".join(FAILED_PROPERTIES)])
        value = fields(raw)
        c.require(set(value) == set(FAILED_PROPERTIES), "STARTUP_UNIT_FIELDS")
        return value

    def historical_units(self):
        result = []
        for item in self.retry["predecessors"]:
            for pin in item["failed_units"]:
                result.append(attest_failed_unit(pin, self.historical_show(pin["unit"])))
        absent = {self.old["settings"]["controllers"]["supervisor"]["unit"]}
        absent.update(plan["settings"]["controllers"]["target"]["unit"] for plan in self.histories)
        children = set().union(*(historical_child_units(handoff) for handoff in self.handoff_history))
        fresh = {self.retry["service"], *(row["unit"] for row in self.plan["settings"]["controllers"].values())}
        c.require(not children & fresh, "STARTUP_HISTORICAL_UNIT_REUSE")
        absent.update(children)
        for unit in sorted(absent):
            value = self.historical_show(unit)
            c.require(value["Id"] == unit and value["LoadState"] == "not-found" and value["ActiveState"] == "inactive"
                and value["SubState"] == "dead" and value["MainPID"] == value["ControlPID"] == "0"
                and value["Job"] == value["InvocationID"] == value["ControlGroup"] == "", "STARTUP_TARGET_OR_OLD_CHILD_CREATED")
            result.append(dict(role="absent", unit=unit, observed=value))
        return result

    def old_snapshot(self):
        return [tree_snapshot(item["path"], self.guard) for item in self.retry["retained_inputs"] if not self.new_staging(item)]

    def verify_candidate(self):
        build = p.sibling("q2_prepare_build"); candidate = self.plan["candidate"]
        source = Path(candidate["source"])
        self.guard(); build.parents(source, protected=True); build.bounded_inventory(source, protected=True)
        files = build.verify_source(source, candidate["commit"], candidate["tree"], self.command)
        build.verify_wheel(Path(candidate["wheel"]), candidate["wheel_sha256"], candidate["commit"], files)
        required = helper("q2_startup_retry_contract").REQUIRED_SOURCE_FILES
        c.require({str(Path(__file__).with_name(name)) for name in required} <= set(self.retry["source"]["files"]),
            "STARTUP_SOURCE_CLOSURE")
        for name, digest in self.retry["source"]["files"].items():
            self.guard(); c.require(p.sha(p.read(name, c.LIMIT, noatime=True)) == digest, "STARTUP_ORCHESTRATION_CHANGED")
        self.candidate_checked = True

    def measure_costs(self):
        self.guard()
        records = {row["path"]: self.old_document(row["path"]) for row in self.retry["reservations"]}
        obligations = reservation_obligations(self.retry, self.histories, records)
        items = list(self.retry["retained_inputs"])
        mapping = dict(reservation="state", state="state", authority="state", journal="journal",
            capture="capture", declarations="capture", session="state", control="state")
        for role, category in mapping.items():
            name = self.plan["directories"][role]["path"]
            if os.path.lexists(name): items.append(dict(path=name, category=category))
        for key in ("source", "wheel", "destination"):
            name = self.plan["candidate"][key]
            if os.path.lexists(name) and not any(name == row["path"] or Path(row["path"]) in Path(name).parents for row in items):
                items.append(dict(path=name, category="installation"))
        costs = {category: dict(bytes=0, inodes=0, retained_unspent_bytes=0, retained_unspent_inodes=0)
            for category in CATEGORIES}
        seen = set(); devices = {}; new_actual = {role: dict(bytes=0, inodes=0) for role in CATEGORIES}
        for item in items:
            if self.skip_candidate and self.new_staging(item) and not os.path.lexists(item["path"]): continue
            value = tree_snapshot(item["path"], self.guard, seen=seen, hash_files=False)
            devices.setdefault(value["device"], dict(bytes=0, inodes=0))
            for key in ("bytes", "inodes"):
                costs[item["category"]][key] += value[key]; devices[value["device"]][key] += value[key]
                if item not in self.retry["retained_inputs"] and not self.new_staging(item):
                    new_actual[item["category"]][key] += value[key]
        proof = []
        for obligation in obligations:
            actual = dict(bytes=0, inodes=0); covered_devices = set()
            for name in obligation["covered_paths"]:
                c.require(any(row["category"] in obligation["accounting_categories"] and
                    (name == row["path"] or Path(row["path"]) in Path(name).parents) for row in self.retry["retained_inputs"]),
                    "STARTUP_RESERVATION_ACCOUNTING_COVERAGE")
                value = tree_snapshot(name, self.guard, hash_files=False)
                covered_devices.add(value["device"])
                for key in actual: actual[key] += value[key]
            unspent = {key: max(0, obligation["commitment"][key] - actual[key]) for key in actual}
            # With no narrower durable allocation, the remaining shared pool
            # might be spent on either category/device. Check each original
            # ceiling at that worst case; physical capacity counts the pool
            # once per possible device, never once per category on that device.
            for category in obligation["accounting_categories"]:
                for key in actual: costs[category]["retained_unspent_" + key] += unspent[key]
            proof.append(dict(obligation, actual_covered=actual, unspent=unspent, devices=sorted(covered_devices)))
        runtime = runtime_storage(self.plan["settings"])
        # Future SQLite, bounded assembly and final diagnostics are charged even
        # before their first file exists. Command logging is separately capped
        # to the remaining state capacity before a subprocess can be launched.
        assembly = helper("q2_startup_retry_driver")
        future = dict(installation=dict(INSTALL_PEAK), capture=runtime,
            state=dict(bytes=8 * 1024**2 + assembly.ASSEMBLY_RESERVATION_BYTES + c.LIMIT,
                inodes=16 + assembly.ASSEMBLY_RESERVATION_INODES + 4),
            journal=runtime)
        for category, values in costs.items():
            for key in ("bytes", "inodes"):
                # New installation staging is actual, not a credit against the
                # separately reserved installed runtime/build peak.
                covered = (new_actual["capture"][key] + new_actual["journal"][key]
                    if category in ("capture", "journal") else new_actual[category][key])
                unspent = max(0, future[category][key] - covered)
                values["new_future_" + key] = future[category][key]
                values["new_unspent_" + key] = unspent
                values["admitted_" + key] = values[key] + values["retained_unspent_" + key] + unspent
                c.require(values["admitted_" + key] <= self.plan["budgets"][category + "_" + key], "STARTUP_CUMULATIVE_CAPACITY")
        self.costs, self.reservation_proofs = costs, proof
        self.reservation_records = {name: p.sha(c.encoded(value)) for name, value in records.items()}
        self.actual_devices = devices
        return costs

    def capacity(self, mounts, inventory):
        costs = self.measure_costs(); unique = {}; by_device = {}
        for role, mount in mounts.items():
            current = by_device.setdefault(mount["device"], dict(available_bytes=mount["available_bytes"],
                free_inodes=mount["free_inodes"], future_bytes=0, future_inodes=0))
            # Role aliases are sampled sequentially; bounded command logging
            # can consume this same device between samples. Keep the lower
            # available amounts while mount identity remains checked upstream.
            current["available_bytes"] = min(current["available_bytes"], mount["available_bytes"])
            current["free_inodes"] = min(current["free_inodes"], mount["free_inodes"])
        for row in inventory:
            key = (self.plan["mounts"]["quota"]["uuid"], row["project"])
            c.require(key not in unique, "STARTUP_QUOTA_DOMAIN_ALIAS"); unique[key] = row
        quota = by_device[mounts["quota"]["device"]]
        quota["future_bytes"] += sum(max(0, row["hard"] * 1024 - row["space"]) for row in unique.values())
        quota["future_inodes"] += sum(max(0, row["ihard"] - row["inodes"]) for row in unique.values())
        for proof in self.reservation_proofs:
            for device in proof["devices"]:
                c.require(device in by_device, "STARTUP_RESERVATION_DEVICE")
                for key in ("bytes", "inodes"): by_device[device]["future_" + key] += proof["unspent"][key]
        mapping = dict(installation={"system"},
            state={self.plan["directories"][role]["filesystem"] for role in ("state", "authority", "reservation", "session", "control")},
            capture={self.plan["directories"][role]["filesystem"] for role in ("capture", "declarations", "journal")})
        for category, roles in mapping.items():
            for device in {mounts[role]["device"] for role in roles}:
                for key in ("bytes", "inodes"): by_device[device]["future_" + key] += costs[category]["new_unspent_" + key]
        for values in by_device.values():
            c.require(values["future_bytes"] <= values["available_bytes"] and values["future_inodes"] <= values["free_inodes"],
                "STARTUP_DEVICE_CAPACITY")
        return dict(cumulative_actual=costs, reservations=self.reservation_proofs, reservation_records=self.reservation_records,
            quota_inventory=inventory, by_device=by_device,
            quota_unique=dict(hard_bytes=sum(row["hard"] * 1024 for row in unique.values()),
                hard_inodes=sum(row["ihard"] for row in unique.values())))

    def stage_admission(self, staging_bytes, staging_entries):
        c.number(staging_bytes, 4096); c.number(staging_entries, 1, 32768)
        costs = self.measure_costs(); selected = costs["installation"]
        admitted_bytes = selected["admitted_bytes"] + staging_bytes + 8192
        admitted_inodes = selected["admitted_inodes"] + staging_entries + 3
        c.require(admitted_bytes <= self.plan["budgets"]["installation_bytes"]
            and admitted_inodes <= self.plan["budgets"]["installation_inodes"], "STARTUP_STAGE_CAPACITY")
        mount = self.mounts()["system"]
        future_bytes = selected["retained_unspent_bytes"] + selected["new_unspent_bytes"] + staging_bytes + 8192
        future_inodes = selected["retained_unspent_inodes"] + selected["new_unspent_inodes"] + staging_entries + 3
        c.require(future_bytes <= mount["available_bytes"] and future_inodes <= mount["free_inodes"], "STARTUP_STAGE_DEVICE_CAPACITY")
        return dict(installation_reservation_bytes=selected["admitted_bytes"],
            installation_reservation_inodes=selected["admitted_inodes"], admitted_bytes=admitted_bytes,
            admitted_inodes=admitted_inodes, staging_bytes=staging_bytes, staging_entries=staging_entries, costs=costs)

    def verify_host(self):
        c.require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0
            and p.kernel("/proc/1/comm").strip() == b"systemd", "STARTUP_ROOT_SYSTEMD")
        own, initial = os.stat("/proc/self/ns/user"), os.stat("/proc/1/ns/user")
        actual = dict(hostname=socket.gethostname(), boot_id=p.kernel("/proc/sys/kernel/random/boot_id").decode().strip(),
            initial_userns=dict(device=own.st_dev, inode=own.st_ino),
            dmi_vendor=p.kernel("/sys/class/dmi/id/sys_vendor").decode().strip(),
            dmi_product=p.kernel("/sys/class/dmi/id/product_name").decode().strip())
        c.require(actual == self.plan["host"] == self.old["host"] == self.previous["host"]
            and (own.st_dev, own.st_ino) == (initial.st_dev, initial.st_ino), "STARTUP_GUEST_NAMESPACE_CHANGED")
        return actual

    def preflight(self, *, skip_candidate=False):
        self.guard(); self.skip_candidate = skip_candidate
        actual = self.verify_host(); self.verify_old_hashes()
        predecessors, ledgers = self.attest_predecessors()
        units = self.historical_units(); self.account()
        for tool in self.plan["tools"].values():
            self.guard(); raw = p.read(tool["path"], 64 * 1024**2, noatime=True)
            c.require(raw.startswith(b"\x7fELF") and p.sha(raw) == tool["sha256"]
                and os.stat(tool["path"]).st_mode & 0o111, "STARTUP_TOOL_CHANGED")
        roots = self.roots(); mounts = self.mounts()
        inventory = p.Quota(self.plan["mounts"]["quota"]["source"]).inventory(self.guard)
        for retained in self.plan["retained_domains"]:
            matching = [row for row in inventory if row["project"] == retained["project_id"]]
            c.require(len(matching) == 1 and matching[0]["hard"] * 1024 == retained["hard_bytes"]
                and matching[0]["ihard"] == retained["inode_hard_limit"], "STARTUP_Q1_QUOTA_CHANGED")
        self.check_parents(start=False)
        for role, item in self.plan["directories"].items():
            if role not in REUSED: self.absent(item["path"], device=self.plan["mounts"][item["filesystem"]]["device"])
        self.absent(self.plan["candidate"]["destination"], device=self.plan["mounts"]["system"]["device"])
        targets = [self.plan["candidate"]["destination"], *[item["path"] for role, item in self.plan["directories"].items()
            if role not in REUSED and (item["owner"] == "ordinary" or role in ("control", "session", "declarations"))]]
        account = self.plan["account"]
        for target in targets:
            for ancestor in reversed(Path(target).parents):
                self.guard(); info = ancestor.stat()
                shift = 6 if info.st_uid == account["uid"] else 3 if info.st_gid == account["gid"] else 0
                c.require(info.st_mode >> shift & 5 == 5, "STARTUP_ORDINARY_ANCESTOR_ACCESS")
                for key in ("system.posix_acl_access", "system.posix_acl_default"):
                    try: os.getxattr(ancestor, key, follow_symlinks=False)
                    except OSError as error:
                        if error.errno in (errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP): continue
                        raise
                    raise ValueError("STARTUP_ANCESTOR_ACL_UNPROVEN")
        if not skip_candidate: self.verify_candidate()
        snapshots = self.old_snapshot(); q1 = self.snapshot()
        capacity = self.capacity(mounts, inventory)
        self.old_snapshots = snapshots
        self.attestation = dict(predecessors=predecessors, ledgers=ledgers, unused_ledgers=True,
            unused_roots=True, roots=roots, old_snapshots=snapshots, q1_snapshot=q1,
            historical_units=units, reservations=dict(records=self.reservation_records, obligations=self.reservation_proofs),
            original_files_preserved=True)
        self.observed = dict(host=actual, mounts=mounts, retained_before=q1, capacity_observed=capacity)
        self.log_block = mounts[self.plan["directories"]["reservation"]["filesystem"]]["block_bytes"]
        self.max_events = 4096
        self.log_byte_limit = min(self.plan["budgets"]["state_bytes"] * 3 // 4,
            self.plan["budgets"]["state_bytes"] - self.costs["state"]["admitted_bytes"])
        self.log_inode_limit = min(4096, self.plan["budgets"]["state_inodes"] - self.costs["state"]["admitted_inodes"])
        c.require(self.log_byte_limit > 3 * c.LIMIT and self.log_inode_limit > 128, "STARTUP_LOG_CAPACITY")
        self.guard(); return self.observed

    def verify_preserved(self):
        self.guard(); c.require(self.attestation is not None, "STARTUP_ATTESTATION_REQUIRED")
        self.verify_host(); self.verify_old_hashes()
        predecessors, ledgers = self.attest_predecessors()
        c.require(predecessors == self.attestation["predecessors"] and ledgers == self.attestation["ledgers"], "STARTUP_PREDECESSOR_CHANGED")
        c.require(self.old_snapshot() == self.attestation["old_snapshots"] and self.snapshot() == self.attestation["q1_snapshot"],
            "STARTUP_OLD_TREE_CHANGED")
        c.require(self.historical_units() == self.attestation["historical_units"] and self.roots() == self.attestation["roots"],
            "STARTUP_OLD_RUNTIME_CHANGED")
        self.account(); self.check_parents(start=False)
        inventory = p.Quota(self.plan["mounts"]["quota"]["source"]).inventory(self.guard)
        c.require(inventory == self.observed["capacity_observed"]["quota_inventory"], "STARTUP_QUOTA_CHANGED")
        self.capacity(self.mounts(), inventory); return True

    def reserve(self, plan=None):
        c.require(self.candidate_checked and self.reservation is None, "STARTUP_CANDIDATE_OR_RESERVATION")
        c.require(self.delivery_envelope is not None and self.delivery_envelope["attempt_id"] == self.retry["attempt_id"]
            and self.delivery_envelope["boot_id"] == self.plan["host"]["boot_id"]
            and self.delivery_envelope["preparation_deadline_ns"] == self.boot_deadline_ns, "STARTUP_DELIVERY_REQUIRED")
        self.verify_preserved()
        path = Path(self.plan["directories"]["reservation"]["path"])
        pin = p.create_directory(path); self.reservation = path
        value = dict(schema=SCHEMA, retry=self.retry, issued_ns=self.issued_ns, deadline_ns=self.deadline,
            attestation=self.attestation, attestation_sha256=p.sha(c.encoded(self.attestation)), costs=self.costs,
            delivery_envelope=self.delivery_envelope, delivery_sha256=p.sha(c.encoded(self.delivery_envelope)),
            clock_anchor_sha256=self.delivery_envelope["clock_anchor_sha256"])
        raw = c.encoded(value); p.create_file(path / "startup-retry-intent.json", raw)
        self.log_bytes = ((len(raw) + self.log_block - 1) // self.log_block) * self.log_block
        return pin

    def prepare(self):
        c.require(self.reservation is not None, "STARTUP_RESERVATION_REQUIRED")
        facts = dict(self.observed)
        for name, operation in (("ordinary", self.account), ("directories", self.directories), ("installation", self.install),
            ("roots", self.roots), ("parents", lambda: self.check_parents(start=True))):
            self.guard(); self.event("step-intent", dict(step=name)); facts[name] = operation()
            self.event("step-result", dict(step=name)); self.measure_costs()
        self.verify_preserved(); facts["retained_after"] = self.snapshot()
        result = dict(schema=SCHEMA, status="STARTUP_RETRY_RESOURCES_PREPARED", attempt_id=self.retry["attempt_id"],
            retry_sha256=p.sha(c.encoded(self.retry)), plan_sha256=p.sha(c.encoded(self.plan)), facts=facts,
            retry=dict(directory=p.identity(self.reservation.stat(), str(self.reservation)), attestation=self.attestation,
                attestation_sha256=p.sha(c.encoded(self.attestation)), original_files_preserved=True),
            delivery_envelope=self.delivery_envelope, delivery_sha256=p.sha(c.encoded(self.delivery_envelope)),
            clock_anchor_sha256=self.delivery_envelope["clock_anchor_sha256"],
            q2_accepted=False, q3_accepted=False, production_supported=False, fixture_generated=False)
        p.create_file(self.reservation / "startup-retry-preparation.json", c.encoded(result))
        return result


def collect_preservation(original, retry, receipt, *, guard, deadline_ns):
    """Recheck old evidence after a new run; new quota-root payload is permitted."""
    guard(); now = time.monotonic_ns(); boot_now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    c.require(boot_now < deadline_ns, "STARTUP_COLLECTION_DEADLINE")
    contract = helper("q2_startup_retry_contract")
    previous = helper("q2_retry_contract").decode(p.read(retry["predecessors"][1]["plan_path"], c.LIMIT, noatime=True),
        retry["predecessors"][1]["plan_sha256"])
    plan = contract.bind(original, retry, previous)
    end = now + min(140 * 10**9, deadline_ns - boot_now)
    backend = StartupRetryBackend(plan, retry, now, end, boot_deadline_ns=deadline_ns)
    bounded_guard = backend.guard
    def checked_guard(): guard(); bounded_guard()
    backend.guard = checked_guard
    backend.plan = copy.deepcopy(plan); backend.plan["budgets"]["command_seconds"] = 2
    attestation = receipt["retry"]["attestation"]
    c.require(receipt["retry"]["attestation_sha256"] == p.sha(c.encoded(attestation)), "STARTUP_COLLECTION_RECEIPT")
    backend.verify_host(); backend.verify_old_hashes()
    predecessors, ledgers = backend.attest_predecessors()
    trees, q1, units = backend.old_snapshot(), backend.snapshot(), backend.historical_units()
    c.require(predecessors == attestation["predecessors"] and ledgers == attestation["ledgers"]
        and trees == attestation["old_snapshots"] and q1 == attestation["q1_snapshot"]
        and units == attestation["historical_units"], "STARTUP_COLLECTION_PRESERVATION_CHANGED")
    guard()
    return dict(old_files_preserved=True, old_ledgers_preserved=True, old_trees_preserved=True,
        q1_records_preserved=True, old_units_preserved=True, predecessors=predecessors,
        ledgers=ledgers, trees=trees, q1=q1, units=units)


Backend = StartupRetryBackend
