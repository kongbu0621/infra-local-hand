"""Private, bounded read-only collection for one supervisor-startup retry.

Only the approved plan and its original delivery window may select inputs.
Collection retains bytes and current observations; it never grants Q2 acceptance
or supplies retrospective stop/EOF/seal evidence for either failed predecessor.
The sole output is bounded stdout. Invoking without arguments does not inspect
host state or create files or processes.
"""
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import time

SCHEMA = "local-hand-q2-supervisor-startup-retry-collection/v1"
BUNDLE_SCHEMA = "local-hand-q2-supervisor-startup-retry-evidence-bundle/v1"
RECEIPT_SCHEMA = "local-hand-q2-supervisor-startup-retry-preparation/v1"
RECEIPT_NAME = "startup-retry-preparation.json"
SCOPE = "LH-Q2-SUPERVISOR-STARTUP-RETRY-v1"
OUTPUT_LIMIT = 2 * 1024**2
NS = 10**9
PRESERVATION_FLAGS = ("old_files_preserved", "old_ledgers_preserved", "old_trees_preserved",
                      "q1_records_preserved", "old_units_preserved")
RECEIPT_FIELDS = {"schema", "status", "attempt_id", "retry_sha256", "plan_sha256", "facts", "retry",
    "q2_accepted", "q3_accepted", "production_supported", "fixture_generated", "delivery_envelope",
    "delivery_sha256", "clock_anchor_sha256"}
ATTESTATION_FIELDS = {"predecessors", "ledgers", "unused_ledgers", "unused_roots", "roots", "old_snapshots",
    "q1_snapshot", "historical_units", "reservations", "original_files_preserved"}


def require(ok, code):
    if not ok: raise ValueError(code)


def helper(name):
    spec = importlib.util.spec_from_file_location("_startup_collect_" + name,
                                                 Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


# These primitives do no installation, provisioning, ledger bootstrap or unit
# mutation. The unchanged module is part of the pinned orchestration closure.
io = helper("q2_retry_collect")
decode = io.decode
identity = io.identity
command = io.command
rows = io.rows


def failure(error):
    """Safe fixed reason, never an exception filename, input, or traceback."""
    value = str(error) if isinstance(error, ValueError) else type(error).__name__
    return value if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else type(error).__name__


def error_record(stage, error):
    number = error.errno if isinstance(error, OSError) else None
    if type(number) is not int or not 0 <= number <= 4095: number = None
    return dict(stage=stage, type=type(error).__name__[:64], reason=failure(error), errno=number)


class Reader(io.Reader):
    """Retain final-fd NOATIME, reject aliases, and verify observed atimes."""
    def __init__(self, *args, **kwargs):
        self.atimes = {}; self.aliases = {}
        super().__init__(*args, **kwargs)

    def opened(self, path, *, directory=False):
        self.guard(); io.absolute(path)
        relative = PurePosixPath(path).relative_to(self.root)
        require(relative.parts, "COLLECT_ROOT_OBJECT")
        fd = os.dup(self.fd)
        try:
            for index, part in enumerate(relative.parts):
                final = index == len(relative.parts)-1
                folder = directory or not final
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
                if final: flags |= os.O_NOATIME
                child = os.open(part, flags | (os.O_DIRECTORY if folder else 0), dir_fd=fd)
                os.close(fd); fd = child
                info = os.fstat(fd)
                require(info.st_uid in self.uids and not info.st_mode & 0o6022, "COLLECT_PROTECTION")
                require(stat.S_ISDIR(info.st_mode) if folder else
                        stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "COLLECT_OBJECT_TYPE")
            key = (info.st_dev, info.st_ino)
            require(self.aliases.get(key, path) == path, "COLLECT_OBJECT_ALIAS")
            self.aliases[key] = path
            require(self.atimes.get(path, info.st_atime_ns) == info.st_atime_ns, "COLLECT_ATIME_CHANGED")
            self.atimes[path] = info.st_atime_ns
            return fd
        except BaseException:
            os.close(fd); raise

    def tree(self, path):
        queue = [str(path)]; entries = []
        large_names = io.LARGE_NAMES | {RECEIPT_NAME, "startup-retry-intent.json", "startup-retry.json"}
        while queue:
            self.guard(); current = queue.pop(); fd = self.opened(current, directory=True)
            try:
                before = identity(os.fstat(fd)); self.seen[current] = before
                require(len(self.seen) <= self.max_entries, "COLLECT_ENTRY_LIMIT")
                entries.append(dict(path=current, kind="directory", identity=before))
                with os.scandir(fd) as iterator:
                    names = []
                    for item in iterator:
                        require(len(self.seen)+len(queue)+len(names) < self.max_entries, "COLLECT_ENTRY_LIMIT")
                        names.append(item.name)
                for name in sorted(names):
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    child = str(PurePosixPath(current)/name)
                    if stat.S_ISDIR(info.st_mode): queue.append(child)
                    else:
                        require(stat.S_ISREG(info.st_mode), "COLLECT_OBJECT_TYPE")
                        raw = self.read(child, limit=2*1024**2 if name in large_names else io.FILE_LIMIT)
                        entries.append(dict(path=child, kind="file", identity=self.seen[child],
                            sha256=sha(raw), content_base64=base64.b64encode(raw).decode()))
                require(identity(os.fstat(fd)) == before, "COLLECT_DIRECTORY_CHANGED")
            finally: os.close(fd)
        return entries


def fixed_envelope(anchor, envelope, attempt_id, *, boot_id, now_ns, anchor_sha256=None):
    d = helper("q2_startup_retry_delivery")
    d.keys(envelope, d.ENVELOPE_FIELDS); d.token(attempt_id); d.boot(boot_id)
    require(envelope["schema"] == d.ENVELOPE_SCHEMA and envelope["attempt_id"] == attempt_id
            and envelope["boot_id"] == boot_id, "COLLECT_ENVELOPE_CHANGED")
    for key in ("issued_ns", "deadline_ns", "preparation_deadline_ns", "stop_ns", "guest_outer_deadline_ns"):
        d.number(envelope[key], 1)
    require(envelope["issued_ns"] < envelope["deadline_ns"] <= envelope["issued_ns"] + d.GUEST_NS
            and envelope["deadline_ns"] + 10*NS <= envelope["guest_outer_deadline_ns"] <= envelope["issued_ns"] + d.HOST_NS
            and envelope["stop_ns"] == d.STOP_NS
            and envelope["issued_ns"] < envelope["preparation_deadline_ns"] <= envelope["issued_ns"] + d.PREPARATION_NS
            and envelope["preparation_deadline_ns"] + d.OWNER_NS + d.STOP_NS + d.FINALIZATION_NS <= envelope["deadline_ns"],
            "COLLECT_ENVELOPE_BUDGET")
    require(type(anchor_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", anchor_sha256), "COLLECT_ANCHOR_DIGEST")
    require(envelope["clock_anchor_sha256"] == anchor_sha256, "COLLECT_ANCHOR_DIGEST")
    if anchor is not None:
        d.validate_clock_anchor(anchor)
        require(sha(d.encoded(anchor)) == anchor_sha256, "COLLECT_ANCHOR_DIGEST")
        require(d.guest_envelope(anchor, attempt_id=attempt_id, guest_boot_id=boot_id,
                                guest_now_ns=envelope["issued_ns"]) == envelope, "COLLECT_ENVELOPE_CHANGED")
    require(type(now_ns) is int and envelope["issued_ns"] <= now_ns < envelope["guest_outer_deadline_ns"]-2*NS,
            "COLLECT_ORIGINAL_WINDOW_EXPIRED")
    return envelope["guest_outer_deadline_ns"]-2*NS


def observe_runtime(plan, retry, reader, deadline_ns):
    # Current stopped/empty observations are explicitly distinct from the
    # original independent stop proof. Reuse only the finite read-only observer.
    return io.observe_runtime(plan, retry, reader, deadline_ns)


def checked_receipt(retry, envelope, reader, plan_sha256):
    path = retry["directories"]["reservation"]["path"] + "/" + RECEIPT_NAME
    result = decode(reader.read(path, limit=2*1024**2))
    require(set(result) == RECEIPT_FIELDS, "COLLECT_RECEIPT_FIELDS")
    require(result.get("schema") == RECEIPT_SCHEMA and result.get("status") == "STARTUP_RETRY_RESOURCES_PREPARED"
            and result.get("attempt_id") == retry["attempt_id"] and result.get("retry_sha256") == sha(encoded(retry))
            and result.get("plan_sha256") == plan_sha256
            and all(result.get(key) is False for key in
                    ("q2_accepted", "q3_accepted", "production_supported", "fixture_generated")), "COLLECT_RECEIPT_BINDING")
    require(type(result["retry"]) is dict and set(result["retry"]) ==
            {"directory", "attestation", "attestation_sha256", "original_files_preserved"}, "COLLECT_RECEIPT_FIELDS")
    attestation = result["retry"]["attestation"]
    require(type(attestation) is dict and set(attestation) == ATTESTATION_FIELDS, "COLLECT_ATTESTATION_FIELDS")
    require(sha(encoded(attestation)) == result["retry"]["attestation_sha256"], "COLLECT_ATTESTATION_BINDING")
    require(result["retry"]["original_files_preserved"] is True and
            all(attestation[key] is True for key in ("unused_ledgers", "unused_roots", "original_files_preserved")),
            "COLLECT_ATTESTATION_BINDING")
    require(type(attestation.get("ledgers")) is list and len(attestation["ledgers"]) == 2,
            "COLLECT_TWO_LEDGERS_REQUIRED")
    # Preparation retains these before issuing children. A new caller cannot
    # attach a renewed envelope to the same retained preparation and plan.
    require(result["delivery_envelope"] == envelope and result["delivery_sha256"] == sha(encoded(envelope))
            and result["clock_anchor_sha256"] == envelope.get("clock_anchor_sha256"),
            "COLLECT_ORIGINAL_DELIVERY_CHANGED")
    return result


def preserve(original, retry, receipt, *, guard, deadline_ns):
    # Dedicated backend API rechecks only historical objects against this
    # receipt's live preflight attestation; it cannot call preflight/prepare.
    return helper("q2_startup_retry").collect_preservation(original, retry, receipt, guard=guard, deadline_ns=deadline_ns)


def collect(retry, original, envelope, anchor, *, plan_sha256, guard, reader, deadline_ns,
            runtime_observer=observe_runtime, preservation_observer=preserve):
    value = dict(schema=BUNDLE_SCHEMA, scope=SCOPE, attempt_id=retry["attempt_id"],
        retry_sha256=sha(encoded(retry)), source=retry["source"], candidate=retry["candidate"],
        clock_anchor=anchor, delivery=envelope, predecessors=retry["predecessors"],
        delivery_sha256=sha(encoded(envelope)), clock_anchor_sha256=envelope.get("clock_anchor_sha256"),
        files=[], roots=[], errors=[], complete=False, reason=None,
        q2_accepted=False, q3_accepted=False, production_supported=False,
        **dict.fromkeys(PRESERVATION_FLAGS, False))
    def attempt(stage, operation):
        try:
            guard(); return operation()
        except Exception as error:
            value["errors"].append(error_record(stage, error))
            return None
    # Roots can contain this new operation's output after execution. Observe
    # actual identities and names; never label them unused from this snapshot.
    for root in original["roots"]:
        def observe_root(root=root):
            fd = reader.opened(root["path"], directory=True)
            try:
                before = identity(os.fstat(fd)); names = []
                with os.scandir(fd) as entries:
                    for item in entries:
                        require(len(names) < 128, "COLLECT_ROOT_MEMBERS"); names.append(item.name)
                require(identity(os.fstat(fd)) == before, "COLLECT_DIRECTORY_CHANGED")
                return dict(path=root["path"], project_id=root["project_id"], identity=before, members=sorted(names))
            finally: os.close(fd)
        observed = attempt("current-root", observe_root)
        if observed is not None: value["roots"].append(observed)
    for role in ("reservation", "authority", "state", "capture", "declarations", "journal"):
        path = retry["directories"][role]["path"]
        try:
            guard(); value["files"].extend(dict(role=role, **entry) for entry in reader.tree(path))
        except FileNotFoundError:
            value["files"].append(dict(role=role, path=path, kind="missing"))
        except Exception as error:
            value["errors"].append(error_record("new-tree:"+role, error))
    receipt = attempt("preparation-receipt", lambda: checked_receipt(retry, envelope, reader, plan_sha256))
    if receipt is not None:
        retained = attempt("historical-preservation", lambda: preservation_observer(original, retry, receipt,
                                                                                   guard=guard, deadline_ns=deadline_ns))
        if retained is not None:
            require(type(retained) is dict, "COLLECT_PRESERVATION_RESULT")
            # Do not permit a backend result to overwrite collection identity or
            # any acceptance flag, even if that API later grows other fields.
            value["preservation"] = retained
            for key in PRESERVATION_FLAGS: value[key] = retained.get(key) is True
    runtime_plan = dict(original)
    if receipt is not None: runtime_plan["_prepared_parents"] = receipt.get("facts", {}).get("parents", {})
    value["runtime"] = attempt("current-runtime", lambda: runtime_observer(runtime_plan, retry, reader, deadline_ns))
    attempt("stable-read-set", reader.stable)
    value["raw_bytes_read"] = reader.total; value["entries_read"] = len(reader.seen)
    value["complete"] = not value["errors"] and all(value[key] for key in PRESERVATION_FLAGS)
    value["reason"] = None if value["complete"] else "COLLECTION_OR_PRESERVATION_INCOMPLETE"
    value["evidence_scope"] = "RETAINED_BYTES_AND_CURRENT_STATE_ONLY; NO_REPLAY_OR_RETROSPECTIVE_EOF_STOP_SEAL"
    return value


def bundle_report(value, *, output_limit):
    require(type(output_limit) is int and 16384 <= output_limit <= OUTPUT_LIMIT, "COLLECT_OUTPUT_LIMIT")
    value = copy.deepcopy(value)
    def package(data):
        raw = encoded(data); require(len(raw) <= 32*1024**2, "COLLECT_BUNDLE_LIMIT")
        compressed = gzip.compress(raw, compresslevel=6, mtime=0)
        return dict(format="gzip+base64", raw_bytes=len(raw), compressed_bytes=len(compressed),
                    raw_sha256=sha(raw), sha256=sha(compressed), data=base64.b64encode(compressed).decode())
    report = dict(schema=SCHEMA, scope=SCOPE, status="COLLECTED" if value.get("complete") is True else "INCOMPLETE",
        attempt_id=value.get("attempt_id"), reason=value.get("reason"),
        retry_sha256=value.get("retry_sha256"), delivery_sha256=value.get("delivery_sha256"),
        clock_anchor_sha256=value.get("clock_anchor_sha256"),
        read_only=True, replay_allowed=False, remote_stop_proven=False, original_eof_proven=False,
        q2_accepted=False, q3_accepted=False, production_supported=False,
        **{key:value.get(key) is True for key in PRESERVATION_FLAGS}, bundle=package(value))
    if len(encoded(report)) > output_limit:
        for entry in value.get("files", []):
            if "content_base64" in entry:
                entry.pop("content_base64"); entry["content_omitted"] = "WIRE_OUTPUT_LIMIT"
        value.update(complete=False, reason="COLLECT_WIRE_CONTENT_LIMIT")
        report.update(status="INCOMPLETE", reason=value["reason"], bundle=package(value))
    if len(encoded(report)) > output_limit:
        report.pop("bundle"); report.update(status="INCOMPLETE", reason="COLLECT_WIRE_METADATA_LIMIT")
    require(len(encoded(report)) <= output_limit, "COLLECT_OUTPUT_LIMIT")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("retry", "sha256", "clock-anchor", "clock-anchor-sha256", "delivery-envelope", "delivery-sha256"):
        parser.add_argument("--"+name)
    parser.add_argument("--output-limit", type=int, default=OUTPUT_LIMIT)
    args = parser.parse_args(argv); reader = None
    try:
        require(all(getattr(args, name) for name in
            ("retry", "sha256", "clock_anchor_sha256", "delivery_envelope", "delivery_sha256")),
            "EXPLICIT_ORIGINAL_STARTUP_RETRY_WINDOW_REQUIRED")
        require(sys.platform.startswith("linux") and sys.flags.isolated and sys.dont_write_bytecode
                and os.getuid() == os.geteuid() == 0, "COLLECT_ISOLATED_ROOT_REQUIRED")
        require(type(args.output_limit) is int and 16384 <= args.output_limit <= OUTPUT_LIMIT, "COLLECT_OUTPUT_LIMIT")
        first = time.clock_gettime_ns(time.CLOCK_BOOTTIME); bound = [first+2*NS]
        guard = lambda: require(time.clock_gettime_ns(time.CLOCK_BOOTTIME) < bound[0], "COLLECT_ORIGINAL_WINDOW_EXPIRED")
        reader = Reader(guard); anchor = None
        if args.clock_anchor:
            raw = reader.read(args.clock_anchor, limit=16384)
            require(sha(raw) == args.clock_anchor_sha256, "COLLECT_ANCHOR_DIGEST"); anchor = decode(raw)
        raw = reader.read(args.delivery_envelope, limit=16384)
        require(sha(raw) == args.delivery_sha256, "COLLECT_DELIVERY_DIGEST"); envelope = decode(raw)
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        contract = helper("q2_startup_retry_contract")
        retry = contract.decode(reader.read(args.retry, limit=2*1024**2), args.sha256)
        bound[0] = fixed_envelope(anchor, envelope, retry["attempt_id"], boot_id=boot,
            now_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME), anchor_sha256=args.clock_anchor_sha256)
        guard()
        original = helper("q2_prepare_contract").decode(
            reader.read(retry["original_plan_path"], limit=2*1024**2), retry["original_plan_sha256"])
        previous = retry["predecessors"][1]
        previous_plan = helper("q2_retry_contract").decode(
            reader.read(previous["plan_path"], limit=2*1024**2), previous["plan_sha256"])
        plan = contract.bind(original, retry, previous_plan)
        reader.uids.add(original["account"]["uid"])
        for path, digest in retry["source"]["files"].items():
            require(sha(reader.read(path, limit=2*1024**2)) == digest, "COLLECT_SOURCE_CHANGED")
        require(str(Path(__file__).resolve()) in retry["source"]["files"], "COLLECT_SOURCE_NOT_PINNED")
        value = collect(retry, original, envelope, anchor, plan_sha256=sha(encoded(plan)),
                        guard=guard, reader=reader, deadline_ns=bound[0])
        guard(); value["finished_boottime_ns"] = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        report = bundle_report(value, output_limit=args.output_limit)
        guard(); print(encoded(report).decode(), end="", flush=True)
        return 0 if report["status"] == "COLLECTED" else 3
    except Exception as error:
        report = dict(schema=SCHEMA, scope=SCOPE, status="BLOCKED" if not args.retry else "INCOMPLETE",
            **error_record("entry", error), read_only=True, replay_allowed=False,
            q2_accepted=False, q3_accepted=False, production_supported=False)
        print(encoded(report).decode(), end="", flush=True); return 3
    finally:
        if reader is not None: reader.close()


if __name__ == "__main__": raise SystemExit(main())
