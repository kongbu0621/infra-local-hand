"""Bounded read-only collection of the exact retained reconciliation attempt.

The original clock and independently classified input manifest are mandatory.
Collection reads existing bytes; it cannot prepare, adopt another source, issue
an owner, renew a window, or reconstruct the original management client's EOF.
"""
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import importlib.util
import os
from pathlib import Path
import stat
import sys
import time


def helper(name):
    spec = importlib.util.spec_from_file_location("_reconciliation_collect_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = helper("q2_startup_retry_collect")
io = helper("q2_reconciliation_io")
c = helper("q2_reconciliation_contract")
encoded, sha, require, decode = legacy.encoded, legacy.sha, legacy.require, legacy.decode
SCHEMA = "local-hand-q2-reconciliation-collection/v1"
BUNDLE_SCHEMA = "local-hand-q2-reconciliation-evidence-bundle/v1"
SCOPE = "LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1"
OUTPUT_LIMIT = 2 * 1024**2
MAX_RAW = 32 * 1024**2
MAX_ENTRIES = 4096
NS = 10**9


class Reader:
    """Keep no-atime file and ancestor handles until the final stable re-read."""
    def __init__(self, guard, *, uids=(0,), max_raw=MAX_RAW, max_entries=MAX_ENTRIES):
        self.guard, self.uids = guard, set(uids)
        self.max_raw, self.max_entries = max_raw, max_entries
        self.held, self.seen, self.raw, self.aliases, self.members = {}, {}, {}, {}, {}
        self.total = 0

    def hold(self, path, *, directory=False, limit=2*1024**2):
        path = io.absolute(path); self.guard()
        if path not in self.held:
            require(len(self.held) < self.max_entries, "COLLECT_ENTRY_LIMIT")
            held = (io.HeldPath(path, self.guard, directory=True, allowed_uids=self.uids) if directory
                else io.read_pinned(path, self.guard, max_bytes=limit, allowed_uids=self.uids))
            try:
                meta = held.verify(); key = meta["device"], meta["inode"]
                require(self.aliases.get(key, path) == path, "COLLECT_OBJECT_ALIAS")
                if not directory:
                    require(self.total + len(held.data) <= self.max_raw, "COLLECT_TOTAL_LIMIT")
                    self.total += len(held.data); self.raw[path] = held.data
                self.aliases[key] = path
                self.held[path], self.seen[path] = held, meta
            except BaseException:
                held.close(); raise
        held = self.held[path]
        require(stat.S_ISDIR(self.seen[path]["st_mode"]) == directory, "COLLECT_OBJECT_TYPE")
        held.verify()
        return held

    def read(self, path, *, limit=2*1024**2):
        held = self.hold(path, limit=limit)
        require(len(held.data) <= limit, "COLLECT_FILE_LIMIT")
        return held.data

    def names(self, path):
        held = self.hold(path, directory=True); names = []
        with os.scandir(held.fd) as entries:
            for entry in entries:
                self.guard(); require(len(names) < self.max_entries, "COLLECT_ENTRY_LIMIT")
                names.append(entry.name)
        held.verify(); names = sorted(names)
        require(self.members.get(path, names) == names, "COLLECT_DIRECTORY_CHANGED")
        self.members[path] = names
        return names

    def tree(self, path):
        queue, result = [path], []
        while queue:
            current = queue.pop(); held = self.hold(current, directory=True)
            result.append(dict(path=current, kind="directory", identity=self.seen[current]))
            for name in self.names(current):
                self.guard(); child = current + "/" + name
                info = os.stat(name, dir_fd=held.fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    require(len(queue) + len(self.held) < self.max_entries, "COLLECT_ENTRY_LIMIT")
                    queue.append(child)
                else:
                    require(stat.S_ISREG(info.st_mode), "COLLECT_OBJECT_TYPE")
                    raw = self.read(child)
                    result.append(dict(path=child, kind="file", identity=self.seen[child],
                        bytes=len(raw), sha256=sha(raw), content_base64=base64.b64encode(raw).decode()))
        return result

    def stable(self):
        for held in self.held.values(): held.verify()
        for path in self.members: self.names(path)

    def close(self):
        for held in self.held.values(): held.close()
        self.held.clear()


def fixed_envelope(anchor, envelope, attempt_id, *, boot_id, now_ns, anchor_sha256):
    require(sha(encoded(anchor)) == anchor_sha256 == envelope.get("clock_anchor_sha256"),
        "COLLECT_ANCHOR_DIGEST")
    return helper("q2_reconciliation_delivery").validate_envelope(anchor, envelope,
        attempt_id=attempt_id, boot_id=boot_id, now_ns=now_ns)


def checked_receipt(verified, envelope, reader, seal):
    retry, plan = verified.execution, verified.plan
    path = retry["directories"]["reservation"]["path"] + "/" + legacy.RECEIPT_NAME
    raw = reader.read(path); result = decode(raw)
    require(set(result) == legacy.RECEIPT_FIELDS, "COLLECT_RECEIPT_FIELDS")
    require(result.get("schema") == legacy.RECEIPT_SCHEMA
        and result.get("status") == "STARTUP_RETRY_RESOURCES_PREPARED"
        and result.get("attempt_id") == retry["attempt_id"]
        and result.get("retry_sha256") == sha(encoded(retry))
        and result.get("plan_sha256") == sha(encoded(plan))
        and all(result.get(key) is False for key in
            ("q2_accepted", "q3_accepted", "production_supported", "fixture_generated")),
        "COLLECT_RECEIPT_BINDING")
    require(type(result["retry"]) is dict and set(result["retry"]) ==
        {"directory", "attestation", "attestation_sha256", "original_files_preserved"},
        "COLLECT_RECEIPT_FIELDS")
    attest = result["retry"]["attestation"]
    require(type(attest) is dict and set(attest) == legacy.ATTESTATION_FIELDS | {"reconciliation"},
        "COLLECT_ATTESTATION_FIELDS")
    require(sha(encoded(attest)) == result["retry"]["attestation_sha256"]
        and result["retry"]["original_files_preserved"] is True
        and all(attest[key] is True for key in ("unused_ledgers", "unused_roots", "original_files_preserved"))
        and type(attest["ledgers"]) is list and len(attest["ledgers"]) == 2,
        "COLLECT_ATTESTATION_BINDING")
    require(attest["reconciliation"] == dict(seal=seal, source_classes=verified.source_classes,
        historical_atime_preservation_proven=False), "COLLECT_RECONCILIATION_RECEIPT")
    require(result["delivery_envelope"] == envelope and result["delivery_sha256"] == sha(encoded(envelope))
        and result["clock_anchor_sha256"] == envelope["clock_anchor_sha256"], "COLLECT_ORIGINAL_DELIVERY_CHANGED")
    directory = result["retry"]["directory"]
    require(directory["path"] == plan["directories"]["reservation"]["path"], "COLLECT_RECEIPT_DIRECTORY")
    actual = reader.hold(directory["path"], directory=True).verify()
    require(all(directory[key] == actual[key] for key in ("device", "inode")), "COLLECT_RECEIPT_DIRECTORY")
    return result


def checked_owner(verified, envelope, receipt, reader):
    """Bind actual owner member bytes; this is retained-artifact consistency only."""
    handoff = helper("q2_prepare_run")
    reservation = verified.plan["directories"]["reservation"]["path"]
    prepared_raw = reader.read(reservation + "/prepared.json")
    prepared = decode(prepared_raw)
    require(prepared.get("schema") == "local-hand-q2-supervisor-startup-retry-driver-result/v1"
        and prepared.get("status") == "STARTUP_RETRY_PREPARED"
        and prepared.get("attempt_id") == verified.execution["attempt_id"]
        and prepared.get("source_commit") == verified.plan["candidate"]["commit"]
        and prepared.get("retry_receipt_sha256") == sha(encoded(receipt))
        and prepared.get("orchestration_source") == verified.execution["source"]
        and prepared.get("runtime_candidate") == {key: verified.plan["candidate"][key]
            for key in ("commit", "tree", "wheel_sha256")}
        and all(prepared.get(key) == verified.execution[key] for key in
            ("scope", "rule", "baseline", "closure", "owner_decision"))
        and prepared.get("delivery_sha256") == sha(encoded(envelope))
        and prepared.get("clock_anchor_sha256") == envelope["clock_anchor_sha256"]
        and all(prepared.get(key) is False for key in ("q2_accepted", "q3_accepted", "production_supported")),
        "COLLECT_PREPARED_BINDING")
    raw_plan = reader.read(reservation + "/handoff.json")
    owner_plan = handoff.decode(raw_plan, sha(raw_plan))
    runtime_source = receipt["facts"]["installation"]["source"]
    require(runtime_source["commit"] == verified.plan["candidate"]["commit"]
        and runtime_source["tree"] == verified.plan["candidate"]["tree"]
        and owner_plan["template"]["launcher"]["source"] == {key: runtime_source[key]
            for key in ("commit", "files")}
        and owner_plan["template"]["launcher"]["assembly"]["installation"]["source_commit"]
            == verified.plan["candidate"]["commit"], "COLLECT_OWNER_RUNTIME_SOURCE")
    require(owner_plan["boot_id"] == envelope["boot_id"]
        and owner_plan["preparation_id"] == verified.plan["settings"]["identity"]["id"]
        and envelope["issued_ns"] <= owner_plan["owner_envelope"]["issued_ns"]
        < owner_plan["owner_envelope"]["deadline_ns"] <= envelope["deadline_ns"], "COLLECT_OWNER_WINDOW")
    paths = {"output": verified.plan["directories"]["capture"]["path"] + "/owner_output",
        "declarations": verified.plan["directories"]["declarations"]["path"] + "/owner_declarations"}
    groups, pins = {}, {}
    for role, limits in (("output", handoff.FILES), ("declarations", handoff.DECLARATIONS)):
        path = paths[role]; pin = owner_plan[role]
        require(pin["path"] == path and set(reader.names(path)) == set(limits), "COLLECT_OWNER_MEMBERS")
        meta = reader.hold(path, directory=True).verify()
        require(all(meta[key] == pin[key] for key in ("device", "inode")), "COLLECT_OWNER_DIRECTORY")
        groups[role] = {}
        for name, limit in limits.items():
            raw = reader.read(path + "/" + name, limit=limit); groups[role][name] = raw
            if name != "seal.json": pins[path + "/" + name] = dict(bytes=len(raw), sha256=sha(raw))
    output, declarations = groups["output"], groups["declarations"]
    seal = decode(output["seal.json"])
    require(set(seal) == {"schema", "status", "envelope_sha256", "original", "files",
        "owner_self_exit_verified", "original_management_session_exit_required", "q2_accepted",
        "q3_accepted", "production_supported"}, "COLLECT_OWNER_SEAL_FIELDS")
    require(seal["schema"] == "local-hand-q2-handoff-seal/v1" and seal["status"] == "SUPERVISOR_CLOSED"
        and seal["files"] == pins and seal["envelope_sha256"] == sha(declarations["envelope.json"])
        and seal["owner_self_exit_verified"] is False and seal["original_management_session_exit_required"] is True
        and all(seal[key] is False for key in ("q2_accepted", "q3_accepted", "production_supported")),
        "COLLECT_OWNER_SEAL_BINDING")
    issued = decode(declarations["envelope.json"])
    require(set(issued) == {"schema", "plan", "fixture"}
        and issued["schema"] == handoff.ENVELOPE_SCHEMA and issued["plan"] == owner_plan,
        "COLLECT_OWNER_HANDOFF_BINDING")
    issued_ns = issued["fixture"]["supervisor_envelope"]["issued_ns"]
    require(type(issued_ns) is int and owner_plan["owner_envelope"]["issued_ns"] <= issued_ns
        < owner_plan["owner_envelope"]["deadline_ns"], "COLLECT_OWNER_ISSUED_TIME")
    expected_fixture = copy.deepcopy(owner_plan["template"])
    for controller in (expected_fixture["supervisor_envelope"], expected_fixture["launcher"]["controller_envelope"]):
        runtime = controller["controller"]["runtime_max_usec"]
        require(type(runtime) is int and 0 < runtime <= 120_000_000, "COLLECT_OWNER_ISSUED_TIME")
        controller.update(issued_ns=issued_ns, deadline_ns=issued_ns + runtime * 1000)
    require(issued["fixture"] == expected_fixture, "COLLECT_OWNER_ISSUED_FIXTURE")
    owner_reservation = decode(output["reservation.json"])
    require(owner_reservation.get("schema") == handoff.SCHEMA
        and owner_reservation.get("plan_sha256") == sha(raw_plan)
        and owner_reservation.get("envelope_sha256") == seal["envelope_sha256"], "COLLECT_OWNER_RESERVATION")
    result = decode(output["result.json"])
    require(result.get("schema") == handoff.RESULT_SCHEMA
        and result.get("status") == "CLOSURE_OBSERVED_SEAL_PENDING" and result.get("sealed") is False
        and result.get("original") == seal["original"] == decode(output["invocation.json"])
        and result.get("evidence") == paths["output"] and result.get("stopped") is True
        and result.get("cleanup_errors") == [] and "reason" not in result
        and result.get("owner_self_exit_verified") is False
        and result.get("original_management_session_exit_required") is True
        and all(result.get(key) is False for key in ("q2_accepted", "q3_accepted", "production_supported")),
        "COLLECT_OWNER_RESULT_BINDING")
    child = decode(output["child-result.json"])
    require(child == decode(declarations["supervisor-result.json"])
        and child.get("schema") == "local-hand-q2-supervisor-handoff-result/v1"
        and child.get("envelope_sha256") == seal["envelope_sha256"]
        and child.get("original") == seal["original"]
        and child.get("result", {}).get("schema") == "local-hand-q2-supervisor-result/v1"
        and child.get("result", {}).get("status") == "CONTROLLER_CLOSED"
        and child["result"].get("sealed") is True
        and child["result"].get("q3_accepted") is False
        and child["result"].get("production_supported") is False
        and child["result"].get("independent_supervisor_stop_required") is True,
        "COLLECT_OWNER_CHILD_BINDING")
    supervisor_window = issued["fixture"]["supervisor_envelope"]
    require(type(child.get("completed_ns")) is int
        and supervisor_window["issued_ns"] <= child["completed_ns"] < supervisor_window["deadline_ns"],
        "COLLECT_OWNER_CHILD_WINDOW")
    bound_fixture = copy.deepcopy(issued["fixture"])
    bound_fixture["supervisor_envelope"]["controller"].update(
        {key: seal["original"][key] for key in handoff.DYNAMIC})
    require(declarations["bound-supervisor.json"] == encoded(bound_fixture)
        and child.get("bound_fixture_sha256") == sha(declarations["bound-supervisor.json"]),
        "COLLECT_OWNER_BOUND_FIXTURE")
    fixture_check = decode(declarations["fixture-check.json"])
    require(fixture_check.get("schema") == "local-hand-q2-fixture-check/v1"
        and fixture_check.get("status") == "CHECKED"
        and fixture_check.get("scope") == "READ_ONLY_EXISTING_PREREQUISITES"
        and all(fixture_check.get(key) is False for key in
            ("q2_accepted", "q3_accepted", "production_supported"))
        and fixture_check.get("independent_supervisor_stop_required") is True
        and type(fixture_check.get("checks")) is list and bool(fixture_check["checks"])
        and all(type(row) is dict and set(row) == {"check", "status"}
            and type(row["check"]) is str and bool(row["check"]) and row["status"] == "PASS"
            for row in fixture_check["checks"]), "COLLECT_OWNER_FIXTURE_CHECK")
    capture = decode(output["capture.json"])
    require(capture.get("schema") == "local-hand-q2-outer-capture/v1"
        and capture.get("complete") is True and type(capture.get("returncode")) is int
        and capture["returncode"] == 0 and capture.get("eof") == ["stderr", "stdout"]
        and capture.get("error") is None and capture.get("close_errors") == []
        and capture.get("independent_stop_required") is True
        and capture.get("q3_accepted") is False and capture.get("production_supported") is False
        and capture.get("stdout_sha256") == sha(output["supervisor.stdout"])
        and capture.get("stderr_sha256") == sha(output["supervisor.stderr"])
        and type(capture.get("started_ns")) is int
        and owner_plan["owner_envelope"]["issued_ns"] <= capture["started_ns"]
            < capture.get("deadline_ns") == owner_plan["owner_envelope"]["deadline_ns"]
        and output["supervisor.stderr"] == b""
        and decode(output["supervisor.stdout"]) == dict(schema=handoff.RESULT_SCHEMA,
            status="CONTROLLER_CLOSED", q3_accepted=False, production_supported=False),
        "COLLECT_OWNER_CAPTURE_BINDING")
    # A later reader cannot prove the original management client's exit. The
    # host must compare this retained-byte projection with its actual final line
    # and separately require both original pipes' EOF and original client exit.
    expected_terminal = dict(result, status="SUPERVISOR_CLOSED", sealed=True)
    return dict(schema="local-hand-q2-reconciliation-owner-artifacts/v1",
        evidence_scope="EXACT_RETAINED_MEMBERS_AND_BINDINGS_ONLY",
        handoff_sha256=sha(raw_plan), prepared_sha256=sha(prepared_raw),
        receipt_sha256=sha(encoded(receipt)), owner_seal_sha256=sha(output["seal.json"]),
        owner_result_sha256=sha(output["result.json"]), issued_envelope_sha256=seal["envelope_sha256"],
        sealed_members=pins, expected_terminal=expected_terminal)


def collect(verified, envelope, anchor, *, backend, reader, seal_sha256):
    retry, plan = verified.execution, verified.plan
    value = dict(schema=BUNDLE_SCHEMA, scope=SCOPE, attempt_id=retry["attempt_id"],
        amendment_sha256=verified.digest, inputs_sha256=verified.digest,
        source_commit=verified.implementation_commit, source_tree=retry["source"]["tree"],
        execution_sha256=sha(encoded(retry)), plan_sha256=sha(encoded(plan)),
        delivery_sha256=sha(encoded(envelope)), clock_anchor_sha256=sha(encoded(anchor)),
        reconciliation_seal_sha256=seal_sha256, delivery=envelope, clock_anchor=anchor,
        files=[], errors=[], complete=False, reason=None, read_only=True, replay_allowed=False,
        remote_stop_proven=False, original_eof_proven=False,
        q2_accepted=False, q3_accepted=False, production_supported=False)
    def attempt(stage, operation):
        try:
            reader.guard(); return operation()
        except Exception as error:
            value["errors"].append(legacy.error_record(stage, error)); return None
    records = helper("q2_reconciliation_records")
    def seal_check():
        folder = backend.reconciliation_directory
        documents = {name: reader.read(folder + "/" + name, limit=records.LIMITS[name])
            for name in records.DOCUMENT_NAMES}
        raw = reader.read(folder + "/" + records.SEAL_NAME, limit=records.LIMITS[records.SEAL_NAME])
        require(sha(raw) == seal_sha256, "COLLECT_RECONCILIATION_SEAL_DIGEST")
        sealed = backend.load_sealed_for_collection(documents)
        require(sealed["allow_run"] is False and sealed["replay"] is True
            and encoded(sealed["seal"]) == raw, "COLLECT_RECONCILIATION_SEAL_BINDING")
        return sealed
    sealed = attempt("reconciliation-seal", seal_check)
    receipt = None
    if sealed is not None:
        value["reconciliation"] = sealed
        receipt = attempt("preparation-receipt", lambda: checked_receipt(verified, envelope, reader, sealed["seal"]))
    if receipt is not None:
        value["preservation"] = attempt("historical-preservation", lambda: backend.collection_preservation(receipt))
        value["owner_proof"] = attempt("owner-retained-artifacts", lambda: checked_owner(verified, envelope, receipt, reader))
    for role in ("reservation", "authority", "state", "capture", "declarations", "journal"):
        rows = attempt("new-tree-" + role, lambda role=role: reader.tree(plan["directories"][role]["path"]))
        if rows is not None: value["files"].extend(dict(role=role, **row) for row in rows)
    if sealed is not None:
        rows = attempt("reconciliation-tree", lambda: reader.tree(backend.reconciliation_directory))
        if rows is not None: value["files"].extend(dict(role="reconciliation", **row) for row in rows)
    attempt("stable-read-set", reader.stable)
    value.update(raw_bytes_read=reader.total, entries_read=len(reader.seen))
    preservation = value.get("preservation") or {}
    value["complete"] = (not value["errors"] and value.get("owner_proof") is not None
        and all(preservation.get(key) is True for key in
            ("old_bytes_preserved", "old_ledgers_preserved", "historical_results_unchanged"))
        and preservation.get("historical_atime_preservation_proven") is False
        and preservation.get("source_classes") == verified.source_classes)
    value["reason"] = None if value["complete"] else "RECONCILIATION_COLLECTION_INCOMPLETE"
    return value


def bundle_report(value, *, output_limit):
    require(type(output_limit) is int and 16384 <= output_limit <= OUTPUT_LIMIT, "COLLECT_OUTPUT_LIMIT")
    value = copy.deepcopy(value)
    def package():
        raw = encoded(value); require(len(raw) <= 64*1024**2, "COLLECT_BUNDLE_LIMIT")
        compressed = gzip.compress(raw, compresslevel=6, mtime=0)
        return dict(format="gzip+base64", raw_bytes=len(raw), compressed_bytes=len(compressed),
            raw_sha256=sha(raw), sha256=sha(compressed), data=base64.b64encode(compressed).decode())
    fields = ("attempt_id", "amendment_sha256", "inputs_sha256", "source_commit", "source_tree",
        "execution_sha256", "plan_sha256", "delivery_sha256", "clock_anchor_sha256", "reconciliation_seal_sha256")
    report = dict(schema=SCHEMA, scope=SCOPE, status="COLLECTED" if value.get("complete") is True else "INCOMPLETE",
        **{key: value.get(key) for key in fields}, reason=value.get("reason"),
        read_only=True, replay_allowed=False, remote_stop_proven=False, original_eof_proven=False,
        q2_accepted=False, q3_accepted=False, production_supported=False, bundle=package())
    if len(encoded(report)) > output_limit:
        for item in value.get("files", []):
            if "content_base64" in item:
                item.pop("content_base64"); item["content_omitted"] = "WIRE_OUTPUT_LIMIT"
        value.update(complete=False, reason="COLLECT_WIRE_CONTENT_LIMIT")
        report.update(status="INCOMPLETE", reason=value["reason"], bundle=package())
    if len(encoded(report)) > output_limit:
        report.pop("bundle"); report.update(status="INCOMPLETE", reason="COLLECT_WIRE_METADATA_LIMIT")
    require(len(encoded(report)) <= output_limit, "COLLECT_OUTPUT_LIMIT")
    return report


def main(argv=None):
    class Parser(argparse.ArgumentParser):
        def error(self, _): raise ValueError("COLLECT_ARGUMENTS")
    parser = Parser(description=__doc__)
    fields = ("inputs", "sha256", "implementation-commit", "delivery-envelope", "delivery-sha256",
        "clock-anchor", "clock-anchor-sha256", "seal-sha256")
    for name in fields: parser.add_argument("--" + name)
    parser.add_argument("--output-limit", type=int, default=OUTPUT_LIMIT)
    reader = backend = None
    try:
        args = parser.parse_args(argv)
        require(all(getattr(args, name.replace("-", "_")) for name in fields), "EXPLICIT_RECONCILIATION_WINDOW_REQUIRED")
        require(sys.platform.startswith("linux") and sys.flags.isolated and sys.dont_write_bytecode
            and os.getuid() == os.geteuid() == 0, "COLLECT_ISOLATED_ROOT_REQUIRED")
        require(type(args.output_limit) is int and 16384 <= args.output_limit <= OUTPUT_LIMIT, "COLLECT_OUTPUT_LIMIT")
        first = time.clock_gettime_ns(time.CLOCK_BOOTTIME); bound = [first + 2*NS]
        guard = lambda: require(time.clock_gettime_ns(time.CLOCK_BOOTTIME) < bound[0], "COLLECT_ORIGINAL_WINDOW_EXPIRED")
        reader = Reader(guard)
        anchor_raw = reader.read(args.clock_anchor, limit=16384)
        envelope_raw = reader.read(args.delivery_envelope, limit=16384)
        require(sha(anchor_raw) == args.clock_anchor_sha256 and sha(envelope_raw) == args.delivery_sha256,
            "COLLECT_CLOCK_DIGEST")
        anchor, envelope = decode(anchor_raw), decode(envelope_raw)
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        # Only the two small clock records may be read before discovering the
        # retained absolute deadline. Never parse the large source archive on a
        # fresh collector-entry interval, including an already expired attempt.
        bound[0] = fixed_envelope(anchor, envelope, envelope["attempt_id"], boot_id=boot,
            now_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME), anchor_sha256=args.clock_anchor_sha256)
        guard()
        bundle = decode(reader.read(args.inputs, limit=16*1024**2))
        require(bundle.get("manifest_sha256") == args.sha256
            and bundle.get("implementation_commit") == args.implementation_commit, "COLLECT_INPUT_BINDING")
        verified = helper("q2_reconciliation_bootstrap").load_inputs(bundle)
        bound[0] = fixed_envelope(anchor, envelope, verified.execution["attempt_id"], boot_id=boot,
            now_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME), anchor_sha256=args.clock_anchor_sha256)
        reader.uids.add(verified.plan["account"]["uid"])
        stage = str(Path(verified.plan["candidate"]["source"]).parent)
        require(args.inputs == stage + "/reconciliation-inputs.json"
            and args.delivery_envelope == stage + "/delivery.json"
            and args.clock_anchor == stage + "/clock-anchor.json", "COLLECT_STAGED_PATHS")
        require(reader.read(stage + "/retry.json") == encoded(verified.execution), "COLLECT_EXECUTION_CHANGED")
        for path, digest in verified.execution["source"]["files"].items():
            require(sha(reader.read(path)) == digest, "COLLECT_SOURCE_CHANGED")
        require(os.path.abspath(__file__) in verified.execution["source"]["files"], "COLLECT_SOURCE_NOT_PINNED")
        mono, now = time.monotonic_ns(), time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        backend = helper("q2_reconciliation_backend").ReconciliationBackend(verified,
            issued_ns=mono, deadline_ns=mono + min(140*NS, bound[0] - now),
            boot_deadline_ns=envelope["guest_outer_deadline_ns"], delivery_envelope=envelope,
            reconciliation_directory=verified.plan["directories"]["reservation"]["path"] + ".reconciliation",
            read_only_collection=True)
        original_guard = backend.guard
        def both(): guard(); original_guard()
        backend.guard = both
        value = collect(verified, envelope, anchor, backend=backend, reader=reader, seal_sha256=args.seal_sha256)
        guard(); value["finished_boottime_ns"] = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        report = bundle_report(value, output_limit=args.output_limit)
        guard(); print(encoded(report).decode(), end="", flush=True)
        return 0 if report["status"] == "COLLECTED" else 3
    except Exception as error:
        report = dict(schema=SCHEMA, scope=SCOPE, status="INCOMPLETE", **legacy.error_record("entry", error),
            read_only=True, replay_allowed=False, remote_stop_proven=False, original_eof_proven=False,
            q2_accepted=False, q3_accepted=False, production_supported=False)
        print(encoded(report).decode(), end="", flush=True); return 3
    finally:
        if backend is not None: backend.close()
        if reader is not None: reader.close()


if __name__ == "__main__": raise SystemExit(main())
