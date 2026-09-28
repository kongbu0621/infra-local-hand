"""Exact local-source RAM delivery; no disk field entry or execution mode.

The start command embeds these exact Git bytes and pins D/tree/package. Package
Git proof and fixed P/M/T are checked before any tool is compiled. The receiver
origin covers input, verification and observation; it cannot consume a Q2 batch.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import io
import json
import os
import re
import select
import shlex
import signal
import stat
import sys
import termios
import time
import types
import zipfile

RULE = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
BASELINE = "b8b9ec3da3de43b72e4e17416ea6633494d50c1d"
CLOSURE = "8e7545199bde66583e1d643656dece867ab1dbda"
KERNEL_A = "887b640b394f9983f37dfe97c58ba35aaa099359"
KERNEL_C = "f7f8b503470725ca1ba18d1cb8d8b39e09a15ea8"
AUTHORITY = dict(rule=RULE, baseline=BASELINE, closure=CLOSURE,
    owner_decision="LH-Q2-LOCAL-SOURCE-EVIDENCE-CLOSURE-20260928-01",
    scope="LH-Q2-LOCAL-SOURCE-EVIDENCE-v1")
CLOSURES = ("d4a925c883672fadc7d1b10a8dfe58df18b922cd",
    "1491765c64c60a63d6bddf10a049308e404885ca", "271c07cd16140aa5942dcf3fad468003c58b6b0e",
    KERNEL_C, CLOSURE)
TOOLS = ("q2_host_kernel_facts.py", "q2_local_source_contract.py", "q2_local_source_delivery.py",
    "q2_local_source_observe.py", "q2_reconciliation_io.py", "q2_retry_bundle.py")
SOURCES = {
    "sources/P": (5426689, "5eef22e497e9e0a867470c6c490336dc80fadd0e506e3419847e6c37b687918b"),
    "sources/M": (50266, "7672ac050609fc7e05481443c9239df0d36f25b4ec9860c2bb833024b962647a"),
    "sources/T": (5913, "76cc2c698dbe882ed246509746bc7088ba55df4199f550af8bad42c9f925dd65"),
}
AUTHORITY_FILES = {
    "authority/local/REQUIREMENTS.md": (BASELINE, "docs/a2-execution/q2-local-source-evidence/REQUIREMENTS.md", "0ae9ee2403851191be6863c4fdd685d477586d94fccfb9312e11d19f160b15f7"),
    "authority/local/ARCHITECTURE.md": (BASELINE, "docs/a2-execution/q2-local-source-evidence/ARCHITECTURE.md", "b31f342c6fbef4411daa63af1c4c7993cc28507fa989438959816c3e086bbc2d"),
    "authority/local/IMPLEMENTATION_PLAN.md": (BASELINE, "docs/a2-execution/q2-local-source-evidence/IMPLEMENTATION_PLAN.md", "9452714bcab444c68089e790f3e5ee378ec0c368fcd13f7fe5d0edc49212c200"),
    "authority/local/OWNER_DECISION.md": (CLOSURE, "docs/governance/Q2_LOCAL_SOURCE_EVIDENCE_OWNER_DECISION.md", "d7d5ed671273fabdcddbc20d2ec2c6483b053294cc4f0be2322f7f120f1d66d3"),
    "authority/local/C_AGENTS.md": (CLOSURE, "AGENTS.md", "929979c905f31ea36fec7951e38838a63595a253446f72751c0e9960f2c8614d"),
    "authority/kernel/REQUIREMENTS.md": (KERNEL_A, "docs/a2-execution/q2-kernel-fact-read/REQUIREMENTS.md", "8fff20a7a6c9b08a427ff6768b567d4a38cd0441e4a54ceaf8b3786c6abb1268"),
    "authority/kernel/ARCHITECTURE.md": (KERNEL_A, "docs/a2-execution/q2-kernel-fact-read/ARCHITECTURE.md", "c18ef78c8fa22994d0270ce8e731d5a690c1f38fa5d2ba9fdb23491127572954"),
    "authority/kernel/IMPLEMENTATION_PLAN.md": (KERNEL_A, "docs/a2-execution/q2-kernel-fact-read/IMPLEMENTATION_PLAN.md", "810c0f2d274b18536249076e0de8278b012b00d5f23fb6ea0ed6d569f65d61f8"),
    "authority/kernel/OWNER_DECISION.md": (KERNEL_C, "docs/governance/Q2_KERNEL_FACT_READ_OWNER_DECISION.md", "c66aa6cc9cf012170a94cbe680977fcbe6bced628eeab03811a3108502934351"),
    "authority/kernel/C_AGENTS.md": (KERNEL_C, "AGENTS.md", "5fa5283656669511d7f3002b8a28e38ba612334d42f2e536c596e5958eeae5fd"),
}
RULE_SHA256 = "c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5"
INPUT_LIMIT, OUTPUT_LIMIT = 16 * 1024**2, 2 * 1024**2
REPORT_LIMIT = OUTPUT_LIMIT - 16384
PACKAGE_LIMIT, EXPANDED_LIMIT = 11 * 1024**2, 32 * 1024**2
LINE_LIMIT = 1026
HEADER = b"#Q2-LOCAL-SOURCE-EVIDENCE "
END = b"#END-Q2-LOCAL-SOURCE-EVIDENCE\n"
READY = b"Q2_LOCAL_SOURCE_RAM_READY: paste the complete # frame now\n"
WINDOW_FIELDS = {"issued_ns", "deadline_ns", "boottime_issued_ns", "boottime_deadline_ns"}
TRANSPORT_FIELDS = {"receiver_source_sha256", "receiver_command_bytes", "frame_bytes", "payload_input_bytes", "package_bytes", "package_sha256"}
FALSE_FIELDS = ("allow_run", "allow_consume", "wrapper_executed", "remote_attempted", "host_persistence_attempted",
    "window_consumed_by_this_invocation", "q2_accepted", "q3_accepted", "production_supported")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def document(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "LOCAL_DELIVERY_DUPLICATE_KEY")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("LOCAL_DELIVERY_JSON_NUMBER")
    return json.loads(raw, object_pairs_hook=pairs, parse_float=invalid, parse_constant=invalid)


def _digest(value, length=64):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value), "LOCAL_DELIVERY_DIGEST")
    return value


def _number(value, low, high):
    require(type(value) is int and low <= value <= high, "LOCAL_DELIVERY_NUMBER")
    return value


def _window():
    boot, mono = time.clock_gettime_ns(time.CLOCK_BOOTTIME), time.monotonic_ns()
    return dict(issued_ns=mono, deadline_ns=mono + 300 * 10**9,
        boottime_issued_ns=boot, boottime_deadline_ns=boot + 300 * 10**9)


def _remaining(window, preparation=True):
    require(type(window) is dict and set(window) == WINDOW_FIELDS, "LOCAL_DELIVERY_WINDOW")
    for key in WINDOW_FIELDS:
        _number(window[key], 1, 2**63 - 1)
    require(window["deadline_ns"] == window["issued_ns"] + 300 * 10**9 and
        window["boottime_deadline_ns"] == window["boottime_issued_ns"] + 300 * 10**9, "LOCAL_DELIVERY_WINDOW")
    mono, boot = time.monotonic_ns(), time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    require(mono >= window["issued_ns"] and boot >= window["boottime_issued_ns"], "LOCAL_DELIVERY_CLOCK_REVERSED")
    duration = (140 if preparation else 300) * 10**9
    left = min(window["issued_ns"] + duration - mono, window["boottime_issued_ns"] + duration - boot)
    require(left > 0, "LOCAL_DELIVERY_PREPARATION_EXPIRED" if preparation else "LOCAL_DELIVERY_OUTPUT_EXPIRED")
    require(abs((mono - window["issued_ns"]) - (boot - window["boottime_issued_ns"])) <= 2 * 10**9,
        "LOCAL_DELIVERY_CLOCK_DIVERGED")
    return left / 10**9


def _read_package(raw):
    require(type(raw) is bytes and 0 < len(raw) <= PACKAGE_LIMIT, "LOCAL_DELIVERY_PACKAGE_BOUND")
    fixed = {"package.json", "package-index.json", "git-proof.json", "authority/rule.md"} | set(AUTHORITY_FILES) | set(SOURCES) | {"tools/" + n for n in TOOLS}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        require(len(infos) == len(fixed) and {x.filename for x in infos} == fixed, "LOCAL_DELIVERY_PACKAGE_MEMBERS")
        require(all(x.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and not x.flag_bits & 1
            and stat.S_IFMT(x.external_attr >> 16) in (0, stat.S_IFREG) for x in infos), "LOCAL_DELIVERY_PACKAGE_KIND")
        require(all(0 < x.file_size <= EXPANDED_LIMIT for x in infos) and
            sum(x.file_size for x in infos) <= EXPANDED_LIMIT, "LOCAL_DELIVERY_EXPANDED_BOUND")
        index_info = archive.getinfo("package-index.json")
        require(index_info.file_size <= 128 * 1024, "LOCAL_DELIVERY_INDEX_BOUND")
        index = document(archive.read(index_info))
        require(type(index) is dict and set(index) == {"schema", "files"} and
            index["schema"] == "q2-local-source-package-file-index/v1" and type(index["files"]) is dict and
            set(index["files"]) == fixed - {"package-index.json"}, "LOCAL_DELIVERY_INDEX")
        files = {}
        for name, pin in index["files"].items():
            require(type(pin) is dict and set(pin) == {"bytes", "sha256"}, "LOCAL_DELIVERY_INDEX_PIN")
            _number(pin["bytes"], 1, EXPANDED_LIMIT); _digest(pin["sha256"])
            require(archive.getinfo(name).file_size == pin["bytes"], "LOCAL_DELIVERY_MEMBER_SIZE")
            value = archive.read(name)
            require(len(value) == pin["bytes"] and sha(value) == pin["sha256"], "LOCAL_DELIVERY_MEMBER_DIGEST")
            files[name] = value
    return files


def _verify_git(proof, files, expected_commit, expected_tree):
    _digest(expected_commit, 40); _digest(expected_tree, 40)
    require(type(proof) is dict and set(proof) == {"schema", "implementation_commit", "implementation_tree", "required_closures", "objects"}
        and proof["schema"] == "q2-local-source-git-proof/v1" and proof["implementation_commit"] == expected_commit
        and proof["implementation_tree"] == expected_tree and proof["required_closures"] == list(CLOSURES), "LOCAL_DELIVERY_GIT_IDENTITIES")
    require(expected_commit not in (*CLOSURES, BASELINE, KERNEL_A), "LOCAL_DELIVERY_IMPLEMENTATION_AFTER_C")
    require(type(proof["objects"]) is dict and 0 < len(proof["objects"]) <= 4096, "LOCAL_DELIVERY_GIT_OBJECTS")
    objects, total = {}, 0
    for oid, item in proof["objects"].items():
        _digest(oid, 40)
        require(type(item) is dict and set(item) == {"kind", "data"} and item["kind"] in ("commit", "tree")
            and type(item["data"]) is str and len(item["data"]) <= 2 * 1024**2, "LOCAL_DELIVERY_GIT_OBJECT")
        raw = base64.b64decode(item["data"], validate=True)
        total += len(raw)
        require(total <= 8 * 1024**2, "LOCAL_DELIVERY_GIT_BOUND")
        kind = item["kind"]
        require(hashlib.sha1(kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == oid, "LOCAL_DELIVERY_GIT_HASH")
        objects[oid] = (kind, raw)
    def commit(oid):
        require(oid in objects and objects[oid][0] == "commit", "LOCAL_DELIVERY_COMMIT_MISSING")
        lines = objects[oid][1].split(b"\n\n", 1)[0].splitlines()
        trees = [x[5:].decode("ascii") for x in lines if x.startswith(b"tree ")]
        parents = [x[7:].decode("ascii") for x in lines if x.startswith(b"parent ")]
        require(len(trees) == 1, "LOCAL_DELIVERY_COMMIT_TREE")
        for value in trees + parents:
            _digest(value, 40)
        return trees[0], parents
    def ancestry(start):
        pending, reached = [start], set()
        while pending:
            oid = pending.pop()
            if oid in reached:
                continue
            reached.add(oid)
            pending.extend(p for p in commit(oid)[1] if p in objects)
        return reached
    require(set(CLOSURES) <= ancestry(expected_commit), "LOCAL_DELIVERY_C_ANCESTRY")
    require(BASELINE in ancestry(CLOSURE) and KERNEL_A in ancestry(KERNEL_C), "LOCAL_DELIVERY_A_C_ORDER")
    require(commit(expected_commit)[0] == expected_tree, "LOCAL_DELIVERY_D_TREE")
    def blob_at(source_commit, path):
        oid = commit(source_commit)[0]
        parts = path.split("/")
        for number, part in enumerate(parts):
            require(oid in objects and objects[oid][0] == "tree", "LOCAL_DELIVERY_TREE_MISSING")
            raw, cursor, entries = objects[oid][1], 0, {}
            while cursor < len(raw):
                space, nul = raw.index(b" ", cursor), raw.index(b"\0", cursor)
                mode, name = raw[cursor:space], raw[space + 1:nul].decode("utf-8")
                require(space < nul and name not in ("", ".", "..") and "/" not in name and name not in entries and
                    nul + 21 <= len(raw), "LOCAL_DELIVERY_TREE_ENTRY")
                entries[name] = (mode, raw[nul + 1:nul + 21].hex())
                cursor = nul + 21
            require(part in entries, "LOCAL_DELIVERY_GIT_PATH")
            mode, oid = entries[part]
            require(mode in ((b"100644", b"100755") if number == len(parts) - 1 else (b"40000",)), "LOCAL_DELIVERY_GIT_MODE")
        return oid
    for name, (source_commit, path, digest) in AUTHORITY_FILES.items():
        raw = files[name]
        require(sha(raw) == digest, "LOCAL_DELIVERY_AUTHORITY_DIGEST")
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(blob_at(source_commit, path) == blob, "LOCAL_DELIVERY_AUTHORITY_GIT_BLOB")
        if source_commit in (BASELINE, KERNEL_A):
            closure = CLOSURE if source_commit == BASELINE else KERNEL_C
            require(blob_at(closure, path) == blob_at(expected_commit, path) == blob, "LOCAL_DELIVERY_A_CHANGED")
        elif path != "AGENTS.md":
            require(blob_at(expected_commit, path) == blob, "LOCAL_DELIVERY_B_CHANGED")
    require(sha(files["authority/rule.md"]) == RULE_SHA256, "LOCAL_DELIVERY_RULE_PIN")
    for name in TOOLS:
        raw = files["tools/" + name]
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(blob_at(expected_commit, "tests/e3_host/" + name) == blob, "LOCAL_DELIVERY_TOOL_GIT_BLOB")
        if name in ("q2_host_kernel_facts.py", "q2_reconciliation_io.py", "q2_retry_bundle.py"):
            require(blob_at(CLOSURE, "tests/e3_host/" + name) == blob, "LOCAL_DELIVERY_SHARED_TOOL_CHANGED")
    return dict(closure_ancestry=True, authority_git_bound=True, tools_verified_before_execution=True, tools=len(TOOLS))


def run_package(raw, mode, *, expected_commit, expected_tree, reception_window=None, transport=None):
    require(mode in ("--check-offline", "--local-source-evidence"), "LOCAL_DELIVERY_MODE")
    local = mode == "--local-source-evidence"
    require((type(reception_window) is dict and type(transport) is dict) if local else
        (reception_window is None and transport is None), "LOCAL_DELIVERY_ORIGIN_REQUIRED")
    if local:
        _remaining(reception_window)
    files = _read_package(raw)
    package = document(files["package.json"])
    require(type(package) is dict and set(package) == {"schema", "authority", "implementation_commit", "implementation_tree", "tools", "field_delivery", "allow_run", "allow_consume"}
        and package == dict(schema="q2-local-source-private-package/v1", authority=AUTHORITY,
            implementation_commit=expected_commit, implementation_tree=expected_tree, tools=list(TOOLS),
            field_delivery="RAM_RECEIVER_ONLY", allow_run=False, allow_consume=False)
        and package["allow_run"] is False and package["allow_consume"] is False, "LOCAL_DELIVERY_PACKAGE_IDENTITY")
    for name, pin in SOURCES.items():
        require((len(files[name]), sha(files[name])) == pin, "LOCAL_DELIVERY_FIXED_SOURCE_PIN")
    proof = _verify_git(document(files["git-proof.json"]), files, expected_commit, expected_tree)
    hashes = {name: sha(files["tools/" + name]) for name in TOOLS}
    if local:
        _remaining(reception_window)
        require(set(transport) == TRANSPORT_FIELDS, "LOCAL_DELIVERY_TRANSPORT")
        require(transport["receiver_source_sha256"] == hashes["q2_local_source_delivery.py"]
            and transport["package_sha256"] == sha(raw) and transport["package_bytes"] == len(raw), "LOCAL_DELIVERY_TRANSPORT_BINDING")
        for key in ("receiver_command_bytes", "frame_bytes", "payload_input_bytes", "package_bytes"):
            _number(transport[key], 1, INPUT_LIMIT)
        require(transport["receiver_command_bytes"] + transport["frame_bytes"] == transport["payload_input_bytes"] <= INPUT_LIMIT,
            "LOCAL_DELIVERY_INPUT_LIMIT")
    loader = types.ModuleType("_verified_local_source_loader")
    exec(compile(files["tools/q2_retry_bundle.py"], "<verified-q2-retry-bundle>", "exec"), loader.__dict__)
    # Pure virtual paths identify verified modules, not original-host files.
    prefix = "/__q2_local_source_verified_tools__/"
    tool_files = {prefix + name: files["tools/" + name] for name in TOOLS}
    with loader.virtual_tools(tool_files, {prefix + name: value for name, value in hashes.items()}) as virtual:
        contract = virtual.load(prefix + "q2_local_source_contract.py", "_verified_local_source_contract")
        require(dict(rule=contract.RULE, baseline=contract.BASELINE, closure=contract.CLOSURE,
            owner_decision=contract.OWNER_DECISION, scope=contract.SCOPE) == AUTHORITY, "LOCAL_DELIVERY_CONTRACT_AUTHORITY")
        selected = contract.targets(files["sources/P"], files["sources/M"], files["sources/T"])
        if not local:
            return dict(schema="q2-local-source-offline-check/v1", status="OFFLINE_CHECK_PASS", authority=AUTHORITY,
                implementation_commit=expected_commit, implementation_tree=expected_tree, package_sha256=sha(raw),
                package_bytes=len(raw), tools_sha256=sha(encoded(hashes)), git=proof,
                target_manifest_sha256=selected["target_manifest_sha256"], target_count=len(selected["targets"]),
                field_reads_performed=False, ready=False, **{name: False for name in FALSE_FIELDS})
        binding = dict(authority=dict(AUTHORITY), implementation_commit=expected_commit, implementation_tree=expected_tree,
            tools_sha256=sha(encoded(hashes)), package_sha256=sha(raw), package_bytes=len(raw), transport=dict(transport))
        observer = virtual.load(prefix + "q2_local_source_observe.py", "_verified_local_source_observe")
        _remaining(reception_window)
        result = observer.run_local(files["sources/P"], files["sources/M"], files["sources/T"],
            reception_window=dict(reception_window), binding=binding)
    require(type(result) is dict and result.get("status") in ("OBSERVED_PARTIAL", "LOCAL_SOURCE_EVIDENCE_BLOCKED")
        and all(result.get(name) is False for name in FALSE_FIELDS), "LOCAL_DELIVERY_REPORT_BOUNDARY")
    require(len(encoded(result)) <= REPORT_LIMIT, "LOCAL_DELIVERY_REPORT_LIMIT")
    return result


def command_bytes(source, digest, size, commit, tree):
    require(type(source) is bytes and 0 < len(source) <= 128 * 1024, "LOCAL_DELIVERY_RECEIVER_SOURCE")
    _digest(digest); _number(size, 1, PACKAGE_LIMIT); _digest(commit, 40); _digest(tree, 40)
    return ("python3 -I -B -S -c " + shlex.quote(source.decode("utf-8")) + " " + digest + " " + str(size)
        + " " + commit + " " + tree + "\n").encode()


def frame_bytes(raw):
    require(type(raw) is bytes and 0 < len(raw) <= PACKAGE_LIMIT, "LOCAL_DELIVERY_PACKAGE_BOUND")
    payload = base64.b64encode(raw)
    return HEADER + sha(raw).encode() + b"\n" + b"".join(b"#" + payload[n:n + 1024] + b"\n"
        for n in range(0, len(payload), 1024)) + END


def _frame(fd, size, digest, window, transport):
    pending, decoded, first = bytearray(), bytearray(), True
    while True:
        ready, _, _ = select.select([fd], [], [], _remaining(window))
        require(ready, "LOCAL_DELIVERY_INPUT_TIMEOUT")
        chunk = os.read(fd, LINE_LIMIT)
        require(chunk, "LOCAL_DELIVERY_INPUT_EOF")
        transport["frame_bytes"] += len(chunk)
        transport["payload_input_bytes"] = transport["receiver_command_bytes"] + transport["frame_bytes"]
        require(transport["payload_input_bytes"] <= INPUT_LIMIT, "LOCAL_DELIVERY_INPUT_LIMIT")
        pending.extend(chunk)
        while b"\n" in pending:
            end = pending.index(b"\n")
            line = bytes(pending[:end + 1]); del pending[:end + 1]
            _remaining(window)
            require(len(line) <= LINE_LIMIT, "LOCAL_DELIVERY_LINE_LIMIT")
            if first:
                require(line == HEADER + digest.encode() + b"\n", "LOCAL_DELIVERY_HEADER")
                first = False
            elif line == END:
                require(not pending and len(decoded) == size and sha(decoded) == digest, "LOCAL_DELIVERY_PACKAGE_PIN")
                return bytes(decoded)
            else:
                require(line.startswith(b"#") and 0 < len(line[1:-1]) <= 1024, "LOCAL_DELIVERY_DATA_LINE")
                part = base64.b64decode(line[1:-1], validate=True)
                require(len(decoded) + len(part) <= size, "LOCAL_DELIVERY_PACKAGE_SIZE")
                decoded.extend(part)
        require(len(pending) < LINE_LIMIT, "LOCAL_DELIVERY_LINE_LIMIT")


def _blocked(reason, transport=None, *, prior=None, expected_commit=None, expected_tree=None):
    result = dict(schema="q2-local-source-ram-receiver/v1", status="LOCAL_SOURCE_EVIDENCE_BLOCKED",
        reason=reason[:192], ready=False, authority=dict(AUTHORITY), **{name: False for name in FALSE_FIELDS})
    if expected_commit is not None and expected_tree is not None:
        result.update(implementation_commit=expected_commit, implementation_tree=expected_tree)
    if transport is not None:
        result["transport"] = dict(transport)
    if type(prior) is dict:
        # Final encoding failure must retain the measured scope without raw data.
        def count(rows, key, cap):
            value = rows.get(key) if type(rows) is dict else None
            return value if type(value) is int and 0 <= value <= cap else None
        before = prior.get("completion")
        result["completion"] = {key: count(before, key, 11) for key in ("attempted", "observed", "matched")}
        result["completion"].update(expected_objects=11, raw_returned=0)
        omitted = count(prior, "raw_omitted_after_delivery_failure", 4)
        result["raw_omitted_after_delivery_failure"] = omitted if omitted is not None else count(before, "raw_returned", 4)
        measured = prior.get("byte_counts")
        result["byte_counts"] = dict(payload_input=count(measured, "payload_input", INPUT_LIMIT),
            ordinary_actual_read=count(measured, "ordinary_actual_read", 10490363),
            kernel_actual_read=count(measured, "kernel_actual_read", 1048707), output_json_bytes=0)
        phase = prior.get("phase")
        result["phase"] = phase if type(phase) is str and re.fullmatch(r"[a-z_]{1,64}", phase) else "UNKNOWN"
        result["report_detail_omitted_after_delivery_failure"] = True
    return result


def _response(result, ready_bytes, window=None):
    value = dict(result)
    if type(value.get("byte_counts")) is dict:
        value["byte_counts"] = dict(value["byte_counts"])
    for _ in range(8):
        if window is not None:
            _remaining(window)
        raw = encoded(value)
        if window is not None:
            _remaining(window)
        counters = dict(ready_stdout_bytes=ready_bytes, report_serialized_bytes=len(raw),
            complete_stdout_bytes=ready_bytes + len(raw), emitted_stderr_bytes=0)
        counts = value.get("byte_counts")
        counts_match = type(counts) is not dict or counts.get("output_json_bytes") == len(raw)
        if value.get("delivery_output") == counters and counts_match:
            require(counters["complete_stdout_bytes"] <= REPORT_LIMIT, "LOCAL_DELIVERY_REPORT_LIMIT")
            return raw
        value["delivery_output"] = counters
        if type(counts) is dict:
            counts["output_json_bytes"] = len(raw)
    raise ValueError("LOCAL_DELIVERY_OUTPUT_COUNT")


def _write_result(raw, window):
    before = fcntl.fcntl(1, fcntl.F_GETFL)
    try:
        fcntl.fcntl(1, fcntl.F_SETFL, before | os.O_NONBLOCK)
        offset = 0
        while offset < len(raw):
            _, writable, _ = select.select([], [1], [], min(_remaining(window, False), 1))
            if writable:
                try:
                    count = os.write(1, raw[offset:offset + 1024])
                except BlockingIOError:
                    continue
                require(count > 0, "LOCAL_DELIVERY_OUTPUT_CLOSED")
                offset += count
    finally:
        fcntl.fcntl(1, fcntl.F_SETFL, before)


def _interrupted(signum, _frame):
    raise ValueError("LOCAL_DELIVERY_INTERRUPTED_" + str(signum))


def main():
    require(len(sys.argv) == 5, "LOCAL_DELIVERY_ARGUMENTS")
    digest, size, commit, tree = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    _digest(digest); _number(size, 1, PACKAGE_LIMIT); _digest(commit, 40); _digest(tree, 40)
    original = sys.orig_argv
    require(len(original) == 10 and original[1:5] == ["-I", "-B", "-S", "-c"]
        and original[6:] == sys.argv[1:], "LOCAL_DELIVERY_RAM_COMMAND_REQUIRED")
    source = original[5].encode("utf-8")
    command = command_bytes(source, digest, size, commit, tree)
    require(len(command) < INPUT_LIMIT, "LOCAL_DELIVERY_INPUT_LIMIT")
    transport = dict(receiver_source_sha256=sha(source), receiver_command_bytes=len(command), frame_bytes=0,
        payload_input_bytes=len(command), package_bytes=size, package_sha256=digest)
    window = _window()
    terminal_before, handlers, result, ready_bytes = None, {}, None, 0
    try:
        require(os.isatty(0) and os.isatty(1), "LOCAL_DELIVERY_TERMINAL_REQUIRED")
        terminal_before = termios.tcgetattr(0)
        terminal_input = list(terminal_before)
        require(terminal_input[3] & termios.ICANON, "LOCAL_DELIVERY_CANONICAL_TERMINAL_REQUIRED")
        terminal_input[3] &= ~(termios.ECHO | termios.ECHONL)
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGALRM):
            handlers[signum] = signal.signal(signum, _interrupted)
        signal.setitimer(signal.ITIMER_REAL, _remaining(window))
        termios.tcsetattr(0, termios.TCSANOW, terminal_input)
        ready_bytes = os.write(1, READY)
        require(ready_bytes == len(READY), "LOCAL_DELIVERY_PROMPT_WRITE")
        raw = _frame(0, size, digest, window, transport)
        result = run_package(raw, "--local-source-evidence", expected_commit=commit, expected_tree=tree,
            reception_window=dict(window), transport=transport)
    except Exception as error:
        result = _blocked(type(error).__name__ + ":" + str(error), transport, prior=result,
            expected_commit=commit, expected_tree=tree)
        if terminal_before is not None:
            try:
                termios.tcflush(0, termios.TCIFLUSH)
            except OSError:
                result["terminal_input_flush"] = "UNKNOWN"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if terminal_before is not None:
            try:
                termios.tcsetattr(0, termios.TCSANOW, terminal_before)
            except OSError:
                result = _blocked("LOCAL_DELIVERY_TERMINAL_RESTORE_FAILED", transport, prior=result,
                    expected_commit=commit, expected_tree=tree)
        for signum, previous in handlers.items():
            signal.signal(signum, previous)
    try:
        raw = _response(result, ready_bytes, window)
    except (ValueError, TypeError, RecursionError, OverflowError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch(r"LOCAL_DELIVERY_[A-Z_]+", str(error)) else "LOCAL_DELIVERY_REPORT_LIMIT"
        result = _blocked(reason, transport, prior=result, expected_commit=commit, expected_tree=tree)
        raw = _response(result, ready_bytes)
    _write_result(raw, window)
    return 0 if result["status"] == "OBSERVED_PARTIAL" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt):
        raise SystemExit(2)
