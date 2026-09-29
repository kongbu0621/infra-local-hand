"""Pure local-host and common host/guest accounting for the fixed window.

Inputs are complete protected observations and independently source-validated
obligation declarations, never assertions that an unknown cost is zero. This
module does not read either machine or acquire consumption/execution authority.
The host identity namespaces physical devices independently from guest st_dev.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath as P
import re
import stat


def helper(name):
    spec = importlib.util.spec_from_file_location("_host_window_billing_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b = helper("q2_reconciliation_billing")
SCHEMA = "local-hand-q2-host-window-bill/v1"
JOINT_SCHEMA = "local-hand-q2-host-guest-bill/v1"
PARENT_BILL_SCHEMA = "local-hand-q2-host-window-bill/v2"
PARENT_JOINT_SCHEMA = "local-hand-q2-host-guest-bill/v2"
PARENT_ALLOCATION_SCHEMA = "local-hand-q2-host-window-parent-allocation/v1"
PARENT_ALLOCATION_FIELDS = {"schema", "span", "binding_sha256", "location_sha256",
    "intent_sha256", "precheck_sha256", "window", "parent_path", "parent_before",
    "parent_after", "marker_snapshot_sha256"}
STARTUP_C = "d4a925c883672fadc7d1b10a8dfe58df18b922cd"
MARKER_NAME = "q2-startup-window-" + hashlib.sha256(STARTUP_C.encode()).hexdigest()
MARKER_FILE = "host-window-intent.json"
MARKER_PEAK = dict(bytes=65536, inodes=4)
MARKER_LOGICAL = 16384
CAPTURE_LOGICAL = 3 * 1024**2
CAPTURE_FILES = 32
CAPTURE_INODES = CAPTURE_FILES + 1
INVENTORY_KEYS = {"host_id", "guest_id", "scans", "expected_roots", "devices", "obligations",
    "marker", "early_audit", "coverage_sha256"}
OBLIGATION_KEYS = {"id", "kind", "category", "commitment", "covered_paths", "devices", "evidence_sha256"}
KINDS = {"historical", "capture", "audit", "marker"}


def require(value, code):
    if not value:
        raise ValueError("HOST_WINDOW_BILL_" + code)


def encoded(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
            allow_nan=False).encode("utf-8") + b"\n"
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("HOST_WINDOW_BILL_JSON") from error


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def pin(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "DIGEST")
    return value


def host_capture_peak(allocation_unit_bytes, *, metadata_bound_bytes):
    """Reserve bounded flat-file output on an independently qualified FS.

    The caller must prove allocation unit and additional directory/metadata
    bound from the actual filesystem; f_frsize alone is not that proof. Unknown
    metadata bounds cannot be omitted or defaulted to zero. This formula uses
    total logical size plus per-file rounding rather than 32 full-size copies.
    """
    b.integer(allocation_unit_bytes, 512); b.integer(metadata_bound_bytes, 1)
    require(allocation_unit_bytes <= 65536 and allocation_unit_bytes & (allocation_unit_bytes - 1) == 0,
        "ALLOCATION_UNIT")
    require(metadata_bound_bytes >= allocation_unit_bytes, "METADATA_ALLOCATION_BOUND")
    rounded = ((CAPTURE_LOGICAL + allocation_unit_bytes - 1) // allocation_unit_bytes) * allocation_unit_bytes
    return dict(bytes=b.add(rounded, (CAPTURE_FILES - 1) * allocation_unit_bytes, metadata_bound_bytes),
        inodes=CAPTURE_INODES)


def _unique_device_rows(rows):
    require(type(rows) is list and 1 <= len(rows) <= 4, "DEVICES")
    result = {}
    for row in rows:
        b.keys(row, ("device", "available_bytes", "free_inodes"))
        for key in row:
            b.integer(row[key], 1 if key == "device" else 0)
        require(row["device"] not in result, "DEVICE_ALIAS")
        result[row["device"]] = row
    return result


def _marker(inventory, objects):
    marker = inventory["marker"]
    b.keys(marker, ("path", "device", "state"))
    b.path(marker["path"]); b.integer(marker["device"], 1)
    require(P(marker["path"]).name == MARKER_NAME and marker["state"] in ("ABSENT", "DURABLE"), "MARKER")
    selected = [row for row in objects.values() if b.contains(marker["path"], row["path"])]
    if marker["state"] == "ABSENT":
        require(not selected and marker["path"] not in inventory["scans"], "MARKER_ALREADY_EXISTS")
        return dict(bytes=0, inodes=0), None
    require(marker["path"] in inventory["scans"]
        and inventory["expected_roots"][marker["path"]] == "capture", "MARKER_SCAN")
    scan = inventory["scans"][marker["path"]]
    entries = {row["relative_path"]: row for row in scan["entries"]}
    require(set(entries) == {".", MARKER_FILE} and entries["."]["type"] == "directory"
        and entries[MARKER_FILE]["type"] == "file" and scan["device"] == marker["device"], "MARKER_MEMBERS")
    require(b.add(*(row["source_metadata"]["size"] for row in scan["entries"])) <= MARKER_LOGICAL,
        "MARKER_LOGICAL")
    actual = b._sum(selected)
    require(all(actual[key] <= MARKER_PEAK[key] for key in actual), "MARKER_SUBBUDGET")
    return actual, entries[MARKER_FILE]["sha256"]


def quote_host(inventory):
    """Quote all known host costs and fixed marker; no guest admission claim.

    The caller derives expected_roots, coverage_sha256 and obligations from
    fixed original carriers/records. A missing declaration, unknown amount or
    unproved native-log bound must fail before calling this pure calculator.
    There is no default historical obligation list or early-log zero value.
    """
    b.keys(inventory, INVENTORY_KEYS)
    pin(inventory["host_id"]); pin(inventory["guest_id"]); pin(inventory["coverage_sha256"])
    require(inventory["host_id"] != inventory["guest_id"], "MACHINE_ALIAS")
    roots = inventory["expected_roots"]
    require(type(roots) is dict and roots and all(value in ("capture", "journal") for value in roots.values()),
        "HOST_CATEGORIES")
    objects = b._scans(inventory["scans"], roots)
    devices = _unique_device_rows(inventory["devices"])
    require(all(row["device"] in devices for row in objects.values()), "UNKNOWN_DEVICE")
    marker_actual, marker_sha = _marker(inventory, objects)
    require(inventory["marker"]["device"] in devices, "MARKER_DEVICE")
    declarations = inventory["obligations"]
    require(type(declarations) is list and 2 <= len(declarations) <= 128, "OBLIGATIONS")
    categories = {category: dict(actual=b._sum(row for row in objects.values() if row["category"] == category),
        future=dict(bytes=0, inodes=0)) for category in ("capture", "journal")}
    actual = b._sum(objects.values()); future = dict(bytes=0, inodes=0)
    by_device = {str(device): dict(actual=b._sum(row for row in objects.values() if row["device"] == device),
        future=dict(bytes=0, inodes=0), available=dict(bytes=values["available_bytes"], inodes=values["free_inodes"]))
        for device, values in devices.items()}
    proofs = []; ids = set(); covered_identities = set(); coverage_paths = []
    for declaration in declarations:
        b.keys(declaration, OBLIGATION_KEYS)
        identity = b.text(declaration["id"])
        require(identity not in ids and declaration["kind"] in KINDS, "OBLIGATION_ID")
        ids.add(identity); pin(declaration["evidence_sha256"])
        require(declaration["category"] in categories, "CATEGORY")
        commitment = b.amount(declaration["commitment"])
        require(all(commitment[key] > 0 for key in commitment), "UNKNOWN_OR_ZERO_COMMITMENT")
        paths = b._paths(declaration["covered_paths"])
        coverage_paths.extend(paths)
        devs = declaration["devices"]
        require(type(devs) is list and 1 <= len(devs) <= 4, "DEVICES")
        for device in devs:
            b.integer(device, 1)
        require(len(set(devs)) == len(devs) and set(devs) <= devices.keys(), "DEVICE_ALIAS")
        observed = b._covered(objects, paths)
        require(all(row["category"] == declaration["category"] and row["device"] in devs for row in observed),
            "COVERAGE_CATEGORY_OR_DEVICE")
        if declaration["kind"] == "historical":
            require(all(path in objects for path in paths), "MISSING_HISTORICAL_TREE")
        for row in observed:
            key = (row["device"], row["inode"])
            require(key not in covered_identities, "DOUBLE_CREDIT")
            covered_identities.add(key)
        used = b._sum(observed)
        if declaration["kind"] == "marker":
            require(identity == "host-window-marker" and commitment == MARKER_PEAK
                and declaration["category"] == "capture"
                and paths == [inventory["marker"]["path"]] and devs == [inventory["marker"]["device"]]
                and used == marker_actual, "MARKER_COMMITMENT")
        elif declaration["kind"] == "capture":
            require(declaration["category"] == "capture", "NEW_CAPTURE_CATEGORY")
            require(commitment["bytes"] >= CAPTURE_LOGICAL and commitment["inodes"] >= CAPTURE_INODES
                and len(paths) == len(devs) == 1, "NEW_CAPTURE_PEAK")
            if observed:
                require(paths[0] in inventory["scans"], "NEW_CAPTURE_SCAN")
                scan = inventory["scans"][paths[0]]
                require(scan["logical_bytes"] <= CAPTURE_LOGICAL and scan["inodes"] <= CAPTURE_INODES
                    and all(entry["relative_path"] == "." and entry["type"] == "directory"
                        or entry["type"] == "file" and "/" not in entry["relative_path"]
                        for entry in scan["entries"])
                    and all(used[key] <= commitment[key] for key in used), "NEW_CAPTURE_SUBBUDGET")
        unspent = {key: max(0, commitment[key] - used[key]) for key in commitment}
        for key in future:
            future[key] = b.add(future[key], unspent[key])
            selected = categories[declaration["category"]]["future"]
            selected[key] = b.add(selected[key], unspent[key])
            for device in devs:
                selected = by_device[str(device)]["future"]
                selected[key] = b.add(selected[key], unspent[key])
        proofs.append(dict(id=identity, kind=declaration["kind"], category=declaration["category"],
            commitment=copy.deepcopy(commitment), actual=used, unspent=unspent,
            coverage_count=len(observed), coverage_sha256=digest(sorted(observed, key=lambda row: row["path"])),
            evidence_sha256=declaration["evidence_sha256"], devices=list(devs)))
    b._paths(coverage_paths)
    require(sum(row["kind"] == "marker" for row in proofs) == 1
        and sum(row["kind"] == "capture" for row in proofs) == 1, "FIXED_NEW_POOLS")
    audit = inventory["early_audit"]
    b.keys(audit, ("evidence_sha256", "host_obligation_ids", "guest_obligation_id", "guest_reserved"))
    pin(audit["evidence_sha256"])
    require(type(audit["host_obligation_ids"]) is list and len(audit["host_obligation_ids"]) <= 128,
        "EARLY_AUDIT")
    for identity in audit["host_obligation_ids"]:
        b.text(identity)
    require(len(set(audit["host_obligation_ids"])) == len(audit["host_obligation_ids"])
        and set(audit["host_obligation_ids"]) == {row["id"] for row in proofs if row["kind"] == "audit"},
        "EARLY_AUDIT_COVERAGE")
    require(audit["guest_obligation_id"] == "new-owner-pool", "EARLY_GUEST_AUDIT_POOL")
    reserved = b.amount(audit["guest_reserved"])
    require(all(0 < reserved[key] <= b.OWNER_POOL[key] for key in reserved), "EARLY_GUEST_AUDIT_BOUND")
    for category, values in categories.items():
        values["admitted"] = {key: b.add(values["actual"][key], values["future"][key]) for key in actual}
        values["ceiling"] = copy.deepcopy(b.CEILINGS[category])
        values["within_ceiling"] = all(values["admitted"][key] <= values["ceiling"][key] for key in actual)
    for values in by_device.values():
        values["within_capacity"] = all(values["future"][key] <= values["available"][key] for key in actual)
    summary = dict(host_id=inventory["host_id"], guest_id=inventory["guest_id"],
        inventory_sha256=digest(inventory), coverage_sha256=inventory["coverage_sha256"],
        actual=actual, future=future, total={key: b.add(actual[key], future[key]) for key in actual},
        categories=categories, by_device=by_device, obligations=proofs,
        marker=dict(inventory["marker"], commitment=copy.deepcopy(MARKER_PEAK), actual=marker_actual,
            logical_limit=MARKER_LOGICAL, intent_sha256=marker_sha), early_audit=copy.deepcopy(audit),
        local_admissible=all(row["within_ceiling"] for row in categories.values())
            and all(row["within_capacity"] for row in by_device.values()), joint_admission_proven=False)
    require(len(encoded(summary)) <= 8192, "INTENT_SUMMARY_BOUND")
    return dict(schema=SCHEMA, inventory=copy.deepcopy(inventory), summary=summary)


def validate_host_bill(value, *, require_admission=True):
    """Recompute supplied observations, returning only the bounded intent view."""
    require(type(require_admission) is bool, "ADMISSION_ARGUMENT")
    b.keys(value, ("schema", "inventory", "summary"))
    require(value["schema"] == SCHEMA, "SCHEMA")
    expected = quote_host(value["inventory"])
    require(encoded(value) == encoded(expected), "QUOTE_CHANGED")
    if require_admission:
        require(expected["summary"]["local_admissible"], "LOCAL_CAPACITY")
    return copy.deepcopy(expected["summary"])


def precheck_costs(inventory):
    """Compute and admit only local host costs before marker creation."""
    quote = quote_host(inventory)
    require(quote["summary"]["marker"]["state"] == "ABSENT", "PRECHECK_ALREADY_CONSUMED")
    validate_host_bill(quote)
    return quote


def validate_marker_transition(precheck_bill, consumed_bill):
    """A consumed quote must contain the actual marker and retained old scans."""
    before = validate_host_bill(precheck_bill)
    after = validate_host_bill(consumed_bill)
    return _marker_transition(precheck_bill["inventory"], consumed_bill["inventory"], before, after)


def _marker_transition(a, z, before, after):
    """Shared unchanged-history checks after explicit schema validation."""
    require(before["marker"]["state"] == "ABSENT" and after["marker"]["state"] == "DURABLE", "MARKER_TRANSITION")
    for key in ("host_id", "guest_id", "obligations", "early_audit", "coverage_sha256"):
        require(a[key] == z[key], "MARKER_DECLARATION_DRIFT")
    for key in ("path", "device"):
        require(a["marker"][key] == z["marker"][key], "MARKER_LOCATION_DRIFT")
    root = a["marker"]["path"]
    require(z["expected_roots"] == dict(a["expected_roots"], **{root: "capture"})
        and set(z["scans"]) == set(a["scans"]) | {root}, "MARKER_SCAN_COVERAGE")
    require(all(a["scans"][name] == z["scans"][name] for name in a["scans"]), "HOST_HISTORY_DRIFT")
    require({row["device"] for row in a["devices"]} == {row["device"] for row in z["devices"]}, "HOST_DEVICE_DRIFT")
    return dict(precheck_inventory_sha256=before["inventory_sha256"],
        consumed_inventory_sha256=after["inventory_sha256"], marker=after["marker"],
        host_id=after["host_id"], guest_id=after["guest_id"])


def _parent_unproven():
    return dict(baseline_parent_cost_status="UNPROVEN", baseline_parent_cost_proven=False,
        full_bill_proven=False, filesystem_proven=False, field_ready=False)


def _parent_allocation_inputs(inventory, base_quote, *, raw, expected_binding, location, window):
    """Bind a first endpoint observation; never infer cause, peak or provenance."""
    c = helper("q2_host_window_contract")
    intent = c.verify_intent_ordinary(raw, expected_binding, location)
    require(intent["window"] == c.validate_window(window), "PARENT_WINDOW")
    require(all(base_quote["summary"][key] == intent["precheck"]["host_bill_summary"][key]
        for key in ("host_id", "guest_id")), "PARENT_MACHINE_BINDING")
    value = inventory["parent_allocation"]
    b.keys(value, PARENT_ALLOCATION_FIELDS)
    require(value["schema"] == PARENT_ALLOCATION_SCHEMA
        and value["span"] == "precheck-parent-to-first-marker-budget", "PARENT_SCHEMA")
    require(c.validate_window(value["window"]) == intent["window"]
        and value["parent_path"] == location["parent"]
        and value["binding_sha256"] == digest(expected_binding)
        and value["location_sha256"] == digest(location)
        and value["intent_sha256"] == c.sha(raw)
        and value["precheck_sha256"] == intent["precheck_sha256"], "PARENT_BINDING")
    before, after = value["parent_before"], value["parent_after"]
    for metadata in (before, after):
        b.keys(metadata, b._METADATA)
        for key in metadata:
            b.integer(metadata[key], 1 if key in ("device", "inode", "nlink") else 0)
        require(stat.S_ISDIR(metadata["st_mode"])
            and metadata["blocks"] <= b.MAX_INTEGER // 512, "PARENT_METADATA")
    require(before == intent["precheck"]["parent_metadata"]
        and all(before[key] == after[key] for key in ("device", "inode", "st_mode", "uid", "gid")),
        "PARENT_IDENTITY")
    require(after["blocks"] >= before["blocks"], "PARENT_ALLOCATION_SHRANK")
    growth = (after["blocks"] - before["blocks"]) * 512
    require(growth <= intent["precheck"]["filesystem"]["block_size"], "PARENT_GROWTH_BOUND")
    marker = base_quote["summary"]["marker"]
    require(marker["state"] == "DURABLE" and marker["path"] == location["directory"]
        and marker["device"] == before["device"] and marker["intent_sha256"] == c.sha(raw),
        "PARENT_MARKER_BINDING")
    scan = inventory["scans"][location["directory"]]
    require(value["marker_snapshot_sha256"] == digest(scan), "PARENT_MARKER_SNAPSHOT")
    rows = {row["relative_path"]: row for row in scan["entries"]}
    root, leaf = rows["."]["source_metadata"], rows[MARKER_FILE]["source_metadata"]
    identity = intent["directory_identity"]
    require(all(root[key] == identity[key] for key in ("device", "inode", "uid", "gid"))
        and root["st_mode"] == (stat.S_IFDIR | 0o700) and root["nlink"] == 2
        and root["device"] == before["device"] and root["inode"] != before["inode"],
        "PARENT_MARKER_IDENTITY")
    require(leaf["st_mode"] == (stat.S_IFREG | 0o400) and leaf["nlink"] == 1
        and leaf["uid"] == identity["uid"] and leaf["gid"] == identity["gid"]
        and leaf["device"] == before["device"]
        and leaf["inode"] not in (before["inode"], root["inode"])
        and leaf["size"] == len(raw) and rows[MARKER_FILE]["sha256"] == c.sha(raw),
        "PARENT_MARKER_CONTENT")
    parent = location["parent"]
    require(all(not b.contains(root_path, parent) for root_path in inventory["scans"]),
        "PARENT_BASELINE_SCAN_COVERED")
    objects = b._scans(inventory["scans"], inventory["expected_roots"])
    require(all(row["path"] != parent
        and (row["device"], row["inode"]) != (before["device"], before["inode"])
        for row in objects.values()), "PARENT_BASELINE_OBJECT_COVERED")
    require(all(not b.contains(covered, parent) for declaration in inventory["obligations"]
        for covered in declaration["covered_paths"]), "PARENT_BASELINE_OBLIGATION_COVERED")
    require(b.add(marker["actual"]["bytes"], growth) <= MARKER_PEAK["bytes"], "PARENT_MARKER_SUBBUDGET")
    return growth


def quote_host_parent_allocation(inventory, *, raw, expected_binding, location, window):
    """Explicit consumed v2 arithmetic over one retained first observation.

    The old parent baseline is neither classified nor credited here. This
    narrow profile rejects any ordinary scan/obligation already covering it;
    passing arithmetic still does not establish a complete bill or field gate.
    """
    b.keys(inventory, INVENTORY_KEYS | {"parent_allocation"})
    base = quote_host({key: inventory[key] for key in INVENTORY_KEYS})
    growth = _parent_allocation_inputs(inventory, base, raw=raw,
        expected_binding=expected_binding, location=location, window=window)
    summary = copy.deepcopy(base["summary"])
    marker = summary["marker"]
    subtree = copy.deepcopy(marker["actual"])
    marker.update(subtree_actual=subtree, parent_growth=dict(bytes=growth, inodes=0),
        parent_allocation_sha256=digest(inventory["parent_allocation"]))
    marker["actual"]["bytes"] = b.add(subtree["bytes"], growth)
    proof = next(row for row in summary["obligations"] if row["kind"] == "marker")
    require(proof["actual"] == subtree and proof["unspent"]["bytes"] >= growth,
        "PARENT_MARKER_CREDIT")
    proof["actual"]["bytes"] = b.add(proof["actual"]["bytes"], growth)
    proof["unspent"]["bytes"] -= growth
    # The allocation debit is not a new inode/object or a second coverage path.
    # Its evidence is linked explicitly; all old path coverage hashes stay put.
    proof["parent_allocation_sha256"] = marker["parent_allocation_sha256"]
    for values in (summary, summary["categories"]["capture"],
                   summary["by_device"][str(marker["device"])]):
        require(values["future"]["bytes"] >= growth, "PARENT_FUTURE_CREDIT")
        values["actual"]["bytes"] = b.add(values["actual"]["bytes"], growth)
        values["future"]["bytes"] -= growth
    summary["total"] = {key: b.add(summary["actual"][key], summary["future"][key])
        for key in ("bytes", "inodes")}
    for values in summary["categories"].values():
        values["admitted"] = {key: b.add(values["actual"][key], values["future"][key])
            for key in ("bytes", "inodes")}
        values["within_ceiling"] = all(values["admitted"][key] <= values["ceiling"][key]
            for key in ("bytes", "inodes"))
    for values in summary["by_device"].values():
        values["within_capacity"] = all(values["future"][key] <= values["available"][key]
            for key in ("bytes", "inodes"))
    summary["local_admissible"] = all(row["within_ceiling"] for row in summary["categories"].values()) \
        and all(row["within_capacity"] for row in summary["by_device"].values())
    require(summary["total"] == base["summary"]["total"], "PARENT_TOTAL_CHANGED")
    summary["inventory_sha256"] = digest(inventory)
    summary.update(_parent_unproven())
    require(len(encoded(summary)) <= 8192, "INTENT_SUMMARY_BOUND")
    return dict(schema=PARENT_BILL_SCHEMA, inventory=copy.deepcopy(inventory), summary=summary)


def validate_host_bill_parent_allocation(value, *, raw, expected_binding, location, window):
    b.keys(value, ("schema", "inventory", "summary"))
    require(value["schema"] == PARENT_BILL_SCHEMA, "PARENT_BILL_SCHEMA")
    expected = quote_host_parent_allocation(value["inventory"], raw=raw,
        expected_binding=expected_binding, location=location, window=window)
    require(encoded(value) == encoded(expected), "PARENT_QUOTE_CHANGED")
    require(expected["summary"]["local_admissible"], "LOCAL_CAPACITY")
    return copy.deepcopy(expected["summary"])


def validate_marker_transition_parent_allocation(precheck_bill, consumed_bill, *,
                                                raw, expected_binding, location, window):
    before = validate_host_bill(precheck_bill)
    after = validate_host_bill_parent_allocation(consumed_bill, raw=raw,
        expected_binding=expected_binding, location=location, window=window)
    c = helper("q2_host_window_contract")
    intent = c.verify_intent_ordinary(raw, expected_binding, location)
    require(intent["precheck"]["host_bill_sha256"] == digest(precheck_bill)
        and intent["precheck"]["host_bill_summary"] == before, "PARENT_PRECHECK_BILL")
    proof = _marker_transition(precheck_bill["inventory"], consumed_bill["inventory"], before, after)
    return dict(proof, parent_allocation_sha256=after["marker"]["parent_allocation_sha256"],
        **_parent_unproven())


def joint_quote(guest_quote, host_bill):
    """Combine one host and one guest without crediting unrelated pools.

    The guest quote is freshly produced by the strict guest bill calculator.
    Its previous two target U values are untouched. Host costs apply equally to
    before and after, so the only amendment delta remains those same two U.
    """
    host = validate_host_bill(host_bill)
    return _joint_quote(guest_quote, host_bill, host, schema=JOINT_SCHEMA)


def joint_quote_parent_allocation(guest_quote, host_bill, *, raw, expected_binding, location, window):
    """A v2 arithmetic comparison, deliberately rejected by the v1 run gate."""
    host = validate_host_bill_parent_allocation(host_bill, raw=raw,
        expected_binding=expected_binding, location=location, window=window)
    result = _joint_quote(guest_quote, host_bill, host, schema=PARENT_JOINT_SCHEMA)
    result.update(_parent_unproven())
    return result


def _joint_quote(guest_quote, host_bill, host, *, schema):
    require(host["marker"]["state"] == "DURABLE", "DURABLE_MARKER_REQUIRED")
    require(type(guest_quote) is dict and guest_quote.get("schema") == "local-hand-q2-reconciliation-bill/v1"
        and type(guest_quote.get("sealed")) is bool, "GUEST_QUOTE")
    guest_pool = [row for row in guest_quote["obligations"] if row["id"] == host["early_audit"]["guest_obligation_id"]]
    require(len(guest_pool) == 1 and guest_pool[0]["origin"] == "new"
        and guest_pool[0]["accounting_categories"] == ["capture", "journal"]
        and guest_pool[0]["commitment"] == b.OWNER_POOL
        and all(host["early_audit"]["guest_reserved"][key] <= guest_pool[0]["commitment"][key]
            for key in ("bytes", "inodes")), "EARLY_GUEST_AUDIT_UNCOVERED")
    def combine(guest):
        result = copy.deepcopy(guest)
        for category in ("capture", "journal"):
            old = guest["categories"][category]; extra = host["categories"][category]
            require(old["ceiling"] == extra["ceiling"] == b.CEILINGS[category], "SHARED_CEILING")
            combined = result["categories"][category]
            for kind in ("actual", "future", "admitted"):
                combined[kind] = {key: b.add(old[kind][key], extra[kind][key]) for key in ("bytes", "inodes")}
            combined["within_ceiling"] = all(combined["admitted"][key] <= combined["ceiling"][key]
                for key in ("bytes", "inodes"))
        for kind in ("actual", "future", "total"):
            result[kind] = {key: b.add(guest[kind][key], host[kind][key]) for key in ("bytes", "inodes")}
        result["by_device"] = {}
        for machine, rows in ((host["host_id"], host["by_device"]), (host["guest_id"], guest["by_device"])):
            for device, row in rows.items():
                # A guest and host may report the same numeric st_dev. They
                # never share physical available capacity or actual objects.
                label = machine + ":" + str(device)
                require(label not in result["by_device"], "CROSS_MACHINE_DEVICE_ALIAS")
                result["by_device"][label] = copy.deepcopy(row)
        result["admissible"] = all(row["within_ceiling"] for row in result["categories"].values())
        result["admissible"] = result["admissible"] and all(row["within_capacity"] for row in result["by_device"].values())
        return result
    before = combine(guest_quote["before"]); after = combine(guest_quote["proposed_after"])
    delta = copy.deepcopy(guest_quote["terminated_unspent"])
    require(all(before["total"][key] - after["total"][key] == delta[key]
        and before["actual"][key] == after["actual"][key] for key in ("bytes", "inodes")), "AMENDMENT_DELTA")
    return dict(schema=schema, before=before, proposed_after=after,
        current=copy.deepcopy(after if guest_quote["sealed"] else before), sealed=guest_quote["sealed"],
        terminated_unspent=delta, guest_quote_sha256=digest(guest_quote), host_bill_sha256=digest(host_bill),
        host_inventory_sha256=host["inventory_sha256"], marker=host["marker"],
        early_audit=host["early_audit"], independent_machine_devices=True,
        shared_capture_ceiling=copy.deepcopy(b.CEILINGS["capture"]), historical_results_unchanged=True)


def require_joint_admissible(quote, *, proposed=False):
    require(type(proposed) is bool and type(quote) is dict and quote.get("schema") == JOINT_SCHEMA,
        "JOINT_QUOTE")
    if not proposed:
        require(quote.get("sealed") is True, "GUEST_SEAL_REQUIRED")
    selected = quote["proposed_after" if proposed else "current"]
    require(selected["admissible"] is True, "JOINT_CAPACITY")
    return copy.deepcopy(selected)
