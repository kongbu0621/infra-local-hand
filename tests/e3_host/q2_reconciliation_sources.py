"""Pure provenance verification and exact live comparison for one amendment.

The returned archive is a carrier, not historical authority. Historical tree
hashes are recomputed over every original algorithm field and member. The two
new values and the 610-entry comparison baseline have explicitly different uses.
No guest reads, commands, writes, fee changes or run authorization occur here.
"""
import base64
import copy
from dataclasses import dataclass
import importlib.util
from pathlib import Path, PurePosixPath as P
import stat


def helper(name):
    spec = importlib.util.spec_from_file_location("_reconciliation_sources_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = helper("q2_reconciliation_contract")
require, sha = c.require, c.sha
META_FIELDS = ("device", "inode", "st_mode", "uid", "gid", "nlink", "size", "blocks",
    "atime_ns", "mtime_ns", "ctime_ns")
TREE_LIMIT = 512 * 1024**2


@dataclass(frozen=True)
class VerifiedSources:
    manifest: dict
    digest: str
    implementation_commit: str
    original: dict
    previous_retry: dict
    previous: dict
    execution: dict
    plan: dict
    raw_by_path: dict
    source_classes: dict
    metadata_baselines: dict
    forward_baseline: dict
    preservation_baselines: dict
    historical_trees: tuple
    reservation_records: dict
    obligations: tuple
    adoption: dict


class _Inputs:
    def __init__(self, blobs, initial_bytes):
        require(hasattr(blobs, "__getitem__"), "RECONCILIATION_BLOBS")
        self.blobs, self.parsed = blobs, initial_bytes
        self.documents, self.read_digests = {}, {}
        self.total_read = 0

    def raw(self, pin, size, *, maximum=TREE_LIMIT):
        c.digest(pin); c.number(size, 0, maximum)
        try:
            raw = self.blobs[pin]
        except (KeyError, TypeError) as error:
            raise ValueError("RECONCILIATION_MISSING_BLOB") from error
        require(type(raw) is bytes and len(raw) == size, "RECONCILIATION_BLOB_SIZE")
        if pin not in self.read_digests:
            self.total_read += size
            require(self.total_read <= TREE_LIMIT, "RECONCILIATION_TREE_BYTES")
            require(sha(raw) == pin, "RECONCILIATION_BLOB_DIGEST")
            self.read_digests[pin] = raw
        else:
            require(self.read_digests[pin] == raw, "RECONCILIATION_BLOB_CHANGED")
        return raw

    def document(self, ref, *, limit=c.INPUT_LIMIT):
        raw = self.raw(ref["sha256"], ref["bytes"], maximum=limit)
        if ref["sha256"] not in self.documents:
            self.parsed += len(raw)
            require(self.parsed <= c.PARSED_TOTAL_LIMIT, "RECONCILIATION_PARSE_TOTAL")
            self.documents[ref["sha256"]] = c.document(raw, limit=limit)
        return self.documents[ref["sha256"]]


def _metadata(value):
    require(type(value) is dict and set(META_FIELDS) <= set(value), "RECONCILIATION_METADATA_FIELDS")
    for key in META_FIELDS: c.number(value[key])
    require(value["device"] > 0 and value["inode"] > 0 and value["nlink"] > 0, "RECONCILIATION_METADATA_IDENTITY")
    return {key: value[key] for key in META_FIELDS}


def _guest_entries(guest):
    c.keys(guest, ("schema", "origin", "archive", "archive_bytes", "archive_sha256", "entries",
        "entry_count", "regular_file_bytes", "regular_file_count"))
    rows = guest["entries"]
    require(type(rows) is list and 0 < len(rows) <= c.ENTRY_LIMIT and guest["entry_count"] == len(rows),
        "RECONCILIATION_GUEST_ENTRIES")
    result, files, total, identities = {}, 0, 0, set()
    for entry in rows:
        name = c.path(entry["source_path"]); meta = entry["source_metadata"]
        require(meta["path"] == name and name not in result, "RECONCILIATION_GUEST_PATH")
        current = _metadata(meta)
        require(entry["type"] == meta["type"], "RECONCILIATION_GUEST_TYPE")
        kind = meta["type"]
        require(kind in ("regular", "directory", "symlink"), "RECONCILIATION_GUEST_TYPE")
        identity = (meta["device"], meta["inode"])
        require(identity not in identities, "RECONCILIATION_GUEST_ALIAS")
        identities.add(identity)
        row = dict(source_metadata=dict(current, path=name, type=kind), sha256=None)
        if kind == "regular":
            require(stat.S_ISREG(meta["st_mode"]) and meta["nlink"] == 1, "RECONCILIATION_REGULAR_TYPE")
            pin = c.digest(entry["sha256"])
            # The exact approved manifest supplies the complete leaf digest
            # inventory. Live admission must hash the original files again;
            # transporting every archived source file is neither required nor
            # an authorization to exceed the original staging/input budget.
            row["sha256"] = pin; files += 1; total += meta["size"]
        elif kind == "directory":
            require(stat.S_ISDIR(meta["st_mode"]), "RECONCILIATION_DIRECTORY_TYPE")
        else:
            require(stat.S_ISLNK(meta["st_mode"]) and type(entry.get("linkname")) is str,
                "RECONCILIATION_SYMLINK_TYPE")
            row["link_target"] = entry["linkname"]
        result[name] = row
    require(files == guest["regular_file_count"] and total == guest["regular_file_bytes"], "RECONCILIATION_GUEST_COUNTS")
    return result


def historical_snapshot(root, rows):
    """Reproduce q2_retry.snapshot_tree, including max(size, blocks*512)."""
    c.path(root)
    require(type(rows) in (list, tuple) and 0 < len(rows) <= c.ENTRY_LIMIT, "RECONCILIATION_HISTORY_ENTRIES")
    projected, names, identities = [], set(), set()
    allocated = logical = 0; device = None
    for entry in rows:
        meta = entry["source_metadata"]; name = c.path(meta["path"])
        require(c.old.contains(root, name) and name not in names, "RECONCILIATION_HISTORY_PATH")
        _metadata(meta)
        identity = meta["device"], meta["inode"]
        require(identity not in identities, "RECONCILIATION_HISTORY_ALIAS")
        names.add(name); identities.add(identity)
        if device is None: device = meta["device"]
        require(meta["device"] == device, "RECONCILIATION_HISTORY_DEVICE")
        row = {key: meta[key] for key in ("path", "device", "inode", "uid", "gid", "size", "mtime_ns", "ctime_ns")}
        row["mode"] = meta["st_mode"]
        if stat.S_ISREG(meta["st_mode"]):
            require(meta["nlink"] == 1, "RECONCILIATION_HISTORY_LINK")
            row["sha256"] = c.digest(entry["sha256"])
        else:
            require(stat.S_ISDIR(meta["st_mode"]) and entry["sha256"] is None, "RECONCILIATION_HISTORY_TYPE")
        allocated += max(meta["size"], meta["blocks"] * 512); logical += meta["size"]
        require(allocated <= TREE_LIMIT and logical <= TREE_LIMIT, "RECONCILIATION_HISTORY_BYTES")
        projected.append(row)
    require(root in names, "RECONCILIATION_HISTORY_ROOT")
    for name in names - {root}:
        require(str(P(name).parent) in names, "RECONCILIATION_HISTORY_PARENT")
    return dict(path=root, bytes=allocated, inodes=len(rows), logical_bytes=logical,
        sha256=sha(c.encoded(sorted(projected, key=lambda row: row["path"]))))


def compare_historical_tree(expected, rows):
    c.keys(expected, ("path", "bytes", "inodes", "logical_bytes", "sha256"))
    observed = historical_snapshot(expected["path"], rows)
    require(observed == expected, "RECONCILIATION_HISTORICAL_TREE_CHANGED")
    return observed


def _history(history, entries, inputs):
    snapshots = history["old_snapshots"]
    require(type(snapshots) is list and len(snapshots) == 12 and len({row["path"] for row in snapshots}) == 12,
        "RECONCILIATION_HISTORY_TREE_SET")
    tree_members, preservation = {}, {}
    for expected in snapshots:
        rows = [entry for name, entry in entries.items() if c.old.contains(expected["path"], name)]
        compare_historical_tree(expected, rows)
        preservation[expected["path"]] = rows
        for row in rows:
            if row["sha256"] is not None:
                tree_members[row["source_metadata"]["path"]] = row["sha256"]
    pins, old_raw = {}, {}
    for row in history["files"]:
        if row["kind"] != "file": continue
        name = c.path(row["path"]); pin = c.digest(row["sha256"])
        try:
            raw = base64.b64decode(row["content_base64"], validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError("RECONCILIATION_HISTORICAL_ENCODING") from error
        require(len(raw) == row["identity"]["size"] and sha(raw) == pin
            and (name not in pins or pins[name] == pin), "RECONCILIATION_HISTORICAL_RAW")
        pins[name] = pin; old_raw[name] = raw
    old_files = history["old_files"]
    require(type(old_files) is list and len(old_files) == 15 and len({row["path"] for row in old_files}) == 15,
        "RECONCILIATION_OLD_PIN_SET")
    for row in old_files:
        name = c.path(row["path"]); pin = c.digest(row["expected_sha256"])
        require(row["sha256"] == pin and (pins.get(name) == pin or tree_members.get(name) == pin),
            "RECONCILIATION_HISTORICAL_PIN")
        entry = entries.get(name)
        # The old return is retained when the new package omitted a file.
        if entry is not None: require(entry["sha256"] == pin, "RECONCILIATION_OLD_PIN_CHANGED")
        pins[name] = pin
    for name, pin in pins.items():
        if name in entries: require(entries[name]["sha256"] == pin, "RECONCILIATION_HISTORICAL_OVERLAP")
    return pins, tree_members, old_raw, preservation, snapshots


def _forward(value, entries, second):
    c.keys(value, ("schema", "scope", "source_archive_sha256", "guest_manifest_sha256", "proposed_only",
        "historical_identity_claim", "entries"))
    require(value["schema"] == "q2-return-forward-comparison-evidence/v1"
        and value["source_archive_sha256"] == c.ARCHIVE_SHA256
        and value["guest_manifest_sha256"] == c.EVIDENCE["guest_manifest"][0]
        and value["proposed_only"] is True and value["historical_identity_claim"] is False,
        "RECONCILIATION_FORWARD_CLASS")
    root = str(P(second["candidate"]["source"]).parent); intent = root + ".intent.json"
    expected = [row for name, row in entries.items() if c.old.contains(root, name) or name == intent]
    expected.sort(key=lambda row: row["source_metadata"]["path"])
    require(len(expected) == 610 and type(value["entries"]) is list and value["entries"] == expected,
        "RECONCILIATION_FORWARD_MEMBERS")
    require(sum(row["source_metadata"]["path"] == intent for row in expected) == 1
        and entries[root]["source_metadata"]["type"] == "directory", "RECONCILIATION_FORWARD_ROOT")
    return dict(source_class="CURRENT_PRESERVATION_BASELINE", root=root, adjacent_intent=intent,
        sha256=c.EVIDENCE["forward_baseline"][0], historical_identity_claim=False, entries=expected)


def _post_read(note, entries, original, second, execution):
    c.keys(note, ("schema", "event", "files", "instruction_met_for_atime", "instruction_met_for_content_mtime_ctime_identity"))
    require(note["schema"] == "local-hand-q2-collection-metadata-note/v1" and note["instruction_met_for_atime"] is False,
        "RECONCILIATION_METADATA_DISCLOSURE")
    stage = next(row["path"] for row in execution["reservations"] if row["kind"] == "RECOVERY_STAGE")
    expected = {str(P(original["candidate"]["source"]).parent) + ".intent.json",
        str(P(second["candidate"]["source"]).parent) + ".intent.json",
        str(P(execution["predecessors"][0]["prepared_path"]).parent / "recovery-intent.json"), stage,
        str(P(second["candidate"]["source"]).parent / "bootstrap-attestation.json")}
    changed = [row for row in note["files"] if row["atime_changed_during_preliminary_unprotected_hash_probe"] is True]
    require(len(changed) == 5 and {row["path"] for row in changed} == expected, "RECONCILIATION_METADATA_SET")
    result = {}
    for item in changed:
        name = item["path"]; row = entries[name]; meta = row["source_metadata"]
        for key in ("atime_ns", "mtime_ns", "ctime_ns", "inode", "size"):
            require(meta[key] == item["post_probe_" + key], "RECONCILIATION_POST_READ_VALUE")
        result[name] = dict(source_class="POST_READ_METADATA_BASELINE", sha256=row["sha256"],
            source_metadata=_metadata(meta), historical_atime_preservation_proven=False)
    return result


def verify(manifest_raw, manifest_sha256, blobs, *, implementation_commit):
    """Validate all raw input, exact provenance and relationships, without I/O."""
    manifest = c.decode(manifest_raw, manifest_sha256, implementation_commit=implementation_commit)
    inputs = _Inputs(blobs, len(manifest_raw))
    evidence = {key: inputs.document(ref) for key, ref in manifest["evidence"].items()}
    entries = _guest_entries(evidence["guest_manifest"])
    pins, tree_members, old_raw, preservation, trees = _history(evidence["history"], entries, inputs)
    original_ref, previous_ref = manifest["original_plan"], manifest["previous_plan"]
    original_raw = inputs.raw(original_ref["sha256"], original_ref["bytes"], maximum=c.RESERVATION_LIMIT)
    previous_raw = inputs.raw(previous_ref["sha256"], previous_ref["bytes"], maximum=c.RESERVATION_LIMIT)
    # Charge parse limits before invoking the separately retained old decoders.
    inputs.document(original_ref, limit=c.RESERVATION_LIMIT); inputs.document(previous_ref, limit=c.RESERVATION_LIMIT)
    original = c.c.decode(original_raw, original_ref["sha256"])
    previous_retry = c.old.legacy.decode(previous_raw, previous_ref["sha256"])
    require(evidence["history"]["retry_sha256"] == previous_ref["sha256"], "RECONCILIATION_PREVIOUS_HISTORY_PIN")
    require(original_ref["sha256"] == previous_retry["original_plan_sha256"], "RECONCILIATION_ORIGINAL_HISTORY_PIN")
    pins[previous_ref["path"]] = previous_ref["sha256"]
    execution, plan, previous = c.bind(manifest, original, previous_retry)
    raw_by_path, classes, records = {}, {}, {}
    required = set(execution["old_files"]) | {row["path"] for row in execution["reservations"]}
    require({row["path"] for row in manifest["sources"]} == required, "RECONCILIATION_SOURCE_COVERAGE")
    reservation_paths = {row["path"] for row in execution["reservations"]}
    adopted_paths = {
        "second-bootstrap-intent": str(P(previous["candidate"]["source"]).parent) + ".intent.json",
        "second-bootstrap-attestation": str(P(previous["candidate"]["source"]).parent / "bootstrap-attestation.json"),
    }
    for row in manifest["sources"]:
        name, pin, kind = row["path"], row["sha256"], row["source_class"]
        raw = inputs.raw(pin, row["bytes"], maximum=c.RESERVATION_LIMIT)
        if kind == "HISTORICAL_PIN":
            require(row["proof_id"] == "history-pin" and pins.get(name) == pin, "RECONCILIATION_PIN_PROOF")
            if name in old_raw: require(raw == old_raw[name], "RECONCILIATION_PIN_BYTES")
        elif kind == "HISTORICAL_TREE_MEMBER":
            require(row["proof_id"] == "history-tree" and tree_members.get(name) == pin,
                "RECONCILIATION_TREE_MEMBER_PROOF")
        else:
            require(adopted_paths.get(row["id"]) == name and name not in pins and name not in tree_members,
                "RECONCILIATION_CURRENT_LOCATION")
            require(entries[name]["sha256"] == pin, "RECONCILIATION_CURRENT_MANIFEST")
        raw_by_path[name] = raw; classes[name] = kind
        if name in reservation_paths: records[name] = inputs.document(row, limit=c.RESERVATION_LIMIT)
    # The established pure interpreter checks all ten source relationships and
    # returns obligations. It does not consult old_files or release anything.
    obligations = helper("q2_startup_retry").reservation_obligations(execution, [original, previous], records)
    forward = _forward(evidence["forward_baseline"], entries, previous)
    post = _post_read(evidence["metadata_note"], entries, original, previous, execution)
    adoption = dict(schema="local-hand-q2-evidence-adoption/v1", scope=c.SCOPE, rule=c.RULE, baseline=c.BASELINE,
        closure=c.CLOSURE, owner_decision=c.OWNER_DECISION, implementation_commit=implementation_commit,
        operation_id=manifest["operation_id"], manifest_sha256=manifest_sha256,
        sources=copy.deepcopy(manifest["sources"]), evidence=copy.deepcopy(manifest["evidence"]),
        prospective_only=True, historical_atime_preservation_proven=False,
        current_preservation_baseline=dict(sha256=forward["sha256"], entries=610, root=forward["root"],
            adjacent_intent=forward["adjacent_intent"], historical_identity_claim=False),
        post_read_metadata=copy.deepcopy(post), run_permission="existing_startup_once")
    c.encoded(adoption, limit=256 * 1024)
    return VerifiedSources(copy.deepcopy(manifest), manifest_sha256, implementation_commit, original, previous_retry,
        previous, execution, plan, raw_by_path, classes, post, forward, preservation,
        tuple(copy.deepcopy(trees)), records, tuple(obligations), adoption)


def _flatten_scans(scans):
    require(type(scans) is dict and len(scans) <= c.REFERENCE_LIMIT, "RECONCILIATION_LIVE_SCANS")
    flattened = {}; count = 0
    for root, scan in scans.items():
        c.path(root)
        c.keys(scan, ("path", "entries", "bytes", "inodes", "device", "logical_bytes"))
        require(scan["path"] == root and type(scan["entries"]) is list,
            "RECONCILIATION_LIVE_SCAN")
        c.number(scan["inodes"], 1, c.ENTRY_LIMIT)
        c.number(scan["device"], 1)
        c.number(scan["bytes"], 0, TREE_LIMIT)
        c.number(scan["logical_bytes"], 0, TREE_LIMIT)
        require(scan["inodes"] == len(scan["entries"]) and 0 < len(scan["entries"]) <= c.ENTRY_LIMIT,
            "RECONCILIATION_LIVE_COUNT")
        local, identities = {}, set()
        allocated = logical = 0
        for observed in scan["entries"]:
            require(type(observed) is dict and observed.get("type") in ("file", "directory", "symlink"),
                "RECONCILIATION_LIVE_TYPE")
            kind = observed["type"]
            extra = ("sha256",) if kind == "file" else ("link_target",) if kind == "symlink" else ()
            c.keys(observed, ("relative_path", "type", "source_metadata", *extra))
            c.keys(observed["source_metadata"], META_FIELDS)
            relative = observed["relative_path"]
            require(type(relative) is str and (relative == "." or
                not P(relative).is_absolute() and str(P(relative)) == relative and ".." not in P(relative).parts),
                "RECONCILIATION_LIVE_RELATIVE_PATH")
            name = root if relative == "." else str(P(root) / relative)
            c.path(name); require(name not in local, "RECONCILIATION_LIVE_DUPLICATE")
            local[name] = kind; count += 1
            require(count <= c.ENTRY_LIMIT, "RECONCILIATION_LIVE_ENTRIES")
            meta = _metadata(observed["source_metadata"])
            identity = meta["device"], meta["inode"]
            require(meta["device"] == scan["device"] and identity not in identities, "RECONCILIATION_LIVE_IDENTITY")
            identities.add(identity)
            expected_type = {"file": stat.S_IFREG, "directory": stat.S_IFDIR, "symlink": stat.S_IFLNK}[kind]
            require(stat.S_IFMT(meta["st_mode"]) == expected_type, "RECONCILIATION_LIVE_TYPE")
            if kind == "file":
                require(meta["nlink"] == 1, "RECONCILIATION_LIVE_LINK")
                c.digest(observed["sha256"]); logical += meta["size"]
            if kind == "symlink":
                require(type(observed["link_target"]) is str and len(observed["link_target"].encode()) <= 4096
                    and "\0" not in observed["link_target"], "RECONCILIATION_LIVE_SYMLINK")
            allocated += meta["blocks"] * 512
            require(allocated <= TREE_LIMIT and logical <= TREE_LIMIT, "RECONCILIATION_LIVE_BYTES")
            row = dict(source_metadata=dict(meta, path=name,
                type="regular" if kind == "file" else kind), sha256=observed.get("sha256"))
            if kind == "symlink": row["link_target"] = observed["link_target"]
            require(name not in flattened or flattened[name] == row, "RECONCILIATION_LIVE_OVERLAP")
            flattened[name] = row
        require(root in local, "RECONCILIATION_LIVE_ROOT")
        require(allocated == scan["bytes"] and logical == scan["logical_bytes"], "RECONCILIATION_LIVE_TOTALS")
        for name in set(local) - {root}:
            require(local.get(str(P(name).parent)) == "directory", "RECONCILIATION_LIVE_PARENT")
    return flattened


def verify_live_sources(verified, scans):
    """Compare full protected scans with original anchors and limited new baselines."""
    entries = _flatten_scans(scans)
    historical = []
    for expected in verified.historical_trees:
        rows = [row for name, row in entries.items() if c.old.contains(expected["path"], name)]
        historical.append(compare_historical_tree(expected, rows))
    baseline = verified.forward_baseline
    forward = [row for name, row in entries.items() if c.old.contains(baseline["root"], name)
        or name == baseline["adjacent_intent"]]
    forward.sort(key=lambda row: row["source_metadata"]["path"])
    require(len(forward) == 610 and forward == baseline["entries"], "RECONCILIATION_CURRENT_BASELINE_CHANGED")
    for name, expected in verified.metadata_baselines.items():
        require(name in entries and entries[name]["sha256"] == expected["sha256"]
            and _metadata(entries[name]["source_metadata"]) == expected["source_metadata"],
            "RECONCILIATION_POST_READ_DRIFT")
    for name, raw in verified.raw_by_path.items():
        require(name in entries and entries[name]["sha256"] == sha(raw)
            and entries[name]["source_metadata"]["size"] == len(raw), "RECONCILIATION_LIVE_SOURCE_MISSING")
    return dict(historical_trees=historical, forward_entries=len(forward),
        forward_sha256=baseline["sha256"], metadata_entries=len(verified.metadata_baselines),
        source_entries=len(verified.raw_by_path), historical_atime_preservation_proven=False)
