"""Exact local-source evidence contract; pure decoding, no field I/O.

Only the three pinned artifacts can produce inspection targets. Source paths
remain private inputs, not defaults, and neither old metadata nor a matching
control-file hash grants execution, historical adoption or billing admission.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import PurePosixPath
import re


SCHEMA = "local-hand-q2-local-source-evidence/v1"
TARGET_SCHEMA = "local-hand-q2-local-source-targets/v1"
SCOPE = "LH-Q2-LOCAL-SOURCE-EVIDENCE-v1"
RULE = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
BASELINE = "b8b9ec3da3de43b72e4e17416ea6633494d50c1d"
CLOSURE = "8e7545199bde66583e1d643656dece867ab1dbda"
OWNER_DECISION = "LH-Q2-LOCAL-SOURCE-EVIDENCE-CLOSURE-20260928-01"
STARTUP_CLOSURE = "d4a925c883672fadc7d1b10a8dfe58df18b922cd"
KERNEL_AUTHORITY = dict(rule=RULE, baseline="887b640b394f9983f37dfe97c58ba35aaa099359",
    closure="f7f8b503470725ca1ba18d1cb8d8b39e09a15ea8",
    owner_decision="LH-Q2-KERNEL-FACT-READ-CLOSURE-20260927-01",
    scope="LH-Q2-KERNEL-FACT-READ-v1")
SOURCE_PINS = {
    "P": {"bytes": 5426689, "sha256": "5eef22e497e9e0a867470c6c490336dc80fadd0e506e3419847e6c37b687918b"},
    "M": {"bytes": 50266, "sha256": "7672ac050609fc7e05481443c9239df0d36f25b4ec9860c2bb833024b962647a"},
    "T": {"bytes": 5913, "sha256": "76cc2c698dbe882ed246509746bc7088ba55df4199f550af8bad42c9f925dd65"},
}
SIBLING_SIZES = (9844, 5426689, 4564, 4779775, 5353, 258348, 4095)
CONTROL_FILES = (
    ("ssh.sh", 328, "aed91e80483d4df103f95c1d4cd5bf9bd18720f4dc51720702c329c937f93c63"),
    ("start.sh", 1162, "1acc8c4cb09bc5b14c32adc35e87d8500098cbf3968d53f406269e96df30f96a"),
    ("known_hosts", 99, "d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd"),
    ("id_ed25519.pub", 95, "e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c"),
)
INPUT_LIMIT = 16 * 1024**2
OUTPUT_LIMIT = 2 * 1024**2
REPORT_LIMIT = OUTPUT_LIMIT - 16384
CONTENT_LIMIT = 10490352
READ_LIMIT = 10490363
KERNEL_READ_LIMIT = 1048707
FILE_COUNT, PARENT_COUNT = 11, 2
PREPARATION_SECONDS, TOTAL_SECONDS, NS = 140, 300, 10**9
INTEGER_LIMIT = 2**63 - 1
DENIED_FLAGS = ("allow_consume", "allow_run", "wrapper_executed", "remote_attempted",
    "host_persistence_attempted", "window_consumed_by_this_invocation",
    "q2_accepted", "q3_accepted", "production_accepted", "production_supported", "k4_trees_reread",
    "full_host_inventory_complete", "allocation_peak_proven", "durability_proven")
UNPROVEN = ("HISTORICAL_COST_ADOPTION", "COMPLETE_JOINT_BILL", "H07",
    "HOST_ALLOCATION_PEAK", "HOST_DURABILITY", "NATIVE_AUDIT_COST")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


DIRECTORY_NAME = "q2-startup-window-" + sha(STARTUP_CLOSURE.encode("utf-8"))


def keys(value, names):
    require(type(value) is dict and set(value) == set(names), "LOCAL_SOURCE_FIELDS")


def number(value, low=0, high=INTEGER_LIMIT):
    require(type(value) is int and low <= value <= high, "LOCAL_SOURCE_INTEGER")
    return value


def digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        "LOCAL_SOURCE_DIGEST")
    return value


def commit(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None,
        "LOCAL_SOURCE_COMMIT")
    return value


def path(value):
    require(type(value) is str and len(value) <= 4096
        and re.fullmatch(r"/[A-Za-z0-9_@./-]+", value) is not None,
        "LOCAL_SOURCE_PATH")
    require(str(PurePosixPath(value)) == value and not value.startswith("//")
        and value != "/" and ".." not in PurePosixPath(value).parts, "LOCAL_SOURCE_PATH")
    return value


def boot(value):
    require(type(value) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value) is not None,
        "LOCAL_SOURCE_BOOT")
    return value


def _values(value, limit):
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        require(depth <= 32 and count <= 65536, "LOCAL_SOURCE_COMPLEXITY")
        if type(item) is dict:
            require(len(item) <= 4096, "LOCAL_SOURCE_COMPLEXITY")
            require(all(type(key) is str and len(key.encode("utf-8")) <= 4096 for key in item),
                "LOCAL_SOURCE_KEY")
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            require(len(item) <= 4096, "LOCAL_SOURCE_COMPLEXITY")
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is int:
            number(item)
        elif type(item) is str:
            require(len(item.encode("utf-8")) <= limit, "LOCAL_SOURCE_STRING")
        else:
            require(item is None or type(item) is bool, "LOCAL_SOURCE_VALUE")


def document(raw, *, limit=INPUT_LIMIT):
    require(type(raw) is bytes and len(raw) <= limit, "LOCAL_SOURCE_INPUT_LIMIT")
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "LOCAL_SOURCE_DUPLICATE_KEY")
            value[key] = item
        return value
    def reject(_):
        raise ValueError("LOCAL_SOURCE_NUMBER")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
            parse_float=reject, parse_constant=reject)
        _values(value, limit)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError("LOCAL_SOURCE_JSON") from error
    return value


def encoded(value, *, limit=INPUT_LIMIT):
    try:
        _values(value, limit)
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    except (UnicodeError, TypeError, RecursionError) as error:
        raise ValueError("LOCAL_SOURCE_JSON") from error
    require(len(raw) <= limit, "LOCAL_SOURCE_OUTPUT_LIMIT")
    return raw


def _carrier(raw):
    try:
        tree = ast.parse(raw)
    except (SyntaxError, UnicodeError, RecursionError) as error:
        raise ValueError("LOCAL_SOURCE_CARRIER_AST") from error
    constants, accepted = {}, set()
    names = {"HOST_RESULT", "HOST_OLD"}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id in names:
                require(target.id not in constants and isinstance(value, ast.Constant)
                    and type(value.value) is str, "LOCAL_SOURCE_CARRIER_CONSTANT")
                constants[target.id] = path(value.value)
                accepted.add(id(target))
    require(set(constants) == names, "LOCAL_SOURCE_CARRIER_CONSTANT")
    require(all(id(node) in accepted for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in names
        and isinstance(node.ctx, (ast.Store, ast.Del))), "LOCAL_SOURCE_CARRIER_CONSTANT")
    parents = {str(PurePosixPath(value).parent) for value in constants.values()}
    require(len(parents) == 1 and len(set(constants.values())) == 2, "LOCAL_SOURCE_CARRIER_PARENT")
    return path(parents.pop()), set(constants.values())


def _manifest(raw, host_parent, carrier_roots):
    value = document(raw, limit=SOURCE_PINS["M"]["bytes"])
    keys(value, ("archive", "archive_bytes", "archive_sha256", "entries", "entry_count",
        "origin", "regular_file_bytes", "regular_file_count", "schema"))
    require(value["schema"] == "local-hand-q2-readonly-return-manifest/v1",
        "LOCAL_SOURCE_MANIFEST_SCHEMA")
    rows = value["entries"]
    require(type(rows) is list and len(rows) == number(value["entry_count"]) == 49,
        "LOCAL_SOURCE_MANIFEST_COUNT")
    roots, siblings, paths = set(), [], set()
    for index, row in enumerate(rows):
        require(type(row) is dict and row.get("type") in ("directory", "regular"),
            "LOCAL_SOURCE_MANIFEST_TYPE")
        fields = ("archive_metadata", "archive_path", "source_metadata", "source_path", "type")
        keys(row, fields + (("sha256",) if row["type"] == "regular" else ()))
        metadata = row["source_metadata"]
        keys(metadata, ("atime_ns", "ctime_ns", "device", "gid", "inode", "mode", "mtime_ns",
            "nlink", "path", "size", "type", "uid"))
        name = path(row["source_path"])
        require(name not in paths and metadata["path"] == name and metadata["type"] == row["type"]
            and name.startswith(host_parent + "/"), "LOCAL_SOURCE_MANIFEST_PATH")
        paths.add(name)
        parent = str(PurePosixPath(name).parent)
        if row["type"] == "directory":
            require(parent == host_parent, "LOCAL_SOURCE_MANIFEST_ROOT")
            roots.add(name)
        else:
            digest(row["sha256"])
            if parent == host_parent:
                siblings.append((name, index, number(metadata["size"]), row["sha256"]))
    require(len(roots) == 5 and len(siblings) == 7 and carrier_roots <= roots,
        "LOCAL_SOURCE_MANIFEST_COVERAGE")
    require(all(name in roots or str(PurePosixPath(name).parent) == host_parent
        or str(PurePosixPath(name).parent) in roots for name in paths), "LOCAL_SOURCE_MANIFEST_COVERAGE")
    siblings.sort()
    require(tuple(item[2] for item in siblings) == SIBLING_SIZES, "LOCAL_SOURCE_SIBLING_SIZES")
    return [dict(id="M%02d" % (offset + 1), path=name, parent=host_parent, source="M",
        source_role="KNOWN_OBJECT_LOCATOR_ONLY", source_index=index, size_cap=size,
        sha256=expected, return_raw=False)
        for offset, (name, index, size, expected) in enumerate(siblings)]


def _controls(raw):
    value = document(raw, limit=SOURCE_PINS["T"]["bytes"])
    require(type(value) is dict and value.get("schema") == "local-hand-q2-host-current-attestation/v1",
        "LOCAL_SOURCE_ATTESTATION_SCHEMA")
    expected_boot = boot(value.get("boot_id"))
    rows = value.get("vm_control_files")
    require(type(rows) is list and len(rows) == 4, "LOCAL_SOURCE_CONTROL_COUNT")
    selected, parents, paths = {}, set(), set()
    allowed = {name for name, _, _ in CONTROL_FILES}
    for index, row in enumerate(rows):
        # Other attestation fields, including historical stat, are not adopted.
        require(type(row) is dict and {"path", "size", "sha256"} <= set(row),
            "LOCAL_SOURCE_CONTROL_FIELDS")
        name = path(row["path"])
        basename = PurePosixPath(name).name
        require(basename in allowed and basename not in selected and name not in paths,
            "LOCAL_SOURCE_CONTROL_PATH")
        paths.add(name)
        parents.add(str(PurePosixPath(name).parent))
        selected[basename] = (index, name, number(row["size"]), digest(row["sha256"]))
    require(len(parents) == 1 and set(selected) == allowed, "LOCAL_SOURCE_CONTROL_PARENT")
    parent = path(parents.pop())
    result = []
    for offset, (basename, size, expected) in enumerate(CONTROL_FILES):
        index, name, observed_size, observed_sha = selected[basename]
        require((observed_size, observed_sha) == (size, expected), "LOCAL_SOURCE_CONTROL_PIN")
        result.append(dict(id="T%02d" % (offset + 1), path=name, parent=parent, source="T",
            source_role="CONTROL_RAW_MATCH_ONLY", source_index=index, size_cap=size,
            sha256=expected, return_raw=True))
    return expected_boot, parent, result


def targets(carrier_raw, manifest_raw, attestation_raw):
    """Derive exactly 11 targets from verified bytes; accept no path overrides.

    P's complete byte pin also preserves its seven old pins without adopting
    another P field or turning those historical files into new read targets.
    """
    for source, raw in (("P", carrier_raw), ("M", manifest_raw), ("T", attestation_raw)):
        pin = SOURCE_PINS[source]
        require(type(raw) is bytes and len(raw) == pin["bytes"] and sha(raw) == pin["sha256"],
            "LOCAL_SOURCE_" + source + "_PIN")
    host_parent, roots = _carrier(carrier_raw)
    siblings = _manifest(manifest_raw, host_parent, roots)
    expected_boot, control_parent, controls = _controls(attestation_raw)
    selected = siblings + controls
    require(host_parent != control_parent and len({item["path"] for item in selected}) == FILE_COUNT,
        "LOCAL_SOURCE_TARGET_ALIAS")
    require(sum(item["size_cap"] for item in selected) == CONTENT_LIMIT
        and sum(item["size_cap"] + 1 for item in selected) == READ_LIMIT, "LOCAL_SOURCE_READ_LIMIT")
    result = dict(schema=TARGET_SCHEMA, scope=SCOPE,
        location=dict(host_parent=host_parent, control_parent=control_parent,
            marker_name=DIRECTORY_NAME, marker_path=host_parent + "/" + DIRECTORY_NAME,
            expected_boot_id=expected_boot, startup_closure=STARTUP_CLOSURE),
        sources={key: dict(value) for key, value in SOURCE_PINS.items()}, targets=selected)
    result["target_manifest_sha256"] = sha(encoded(result))
    return result
