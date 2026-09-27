"""Pure accounting for the exact approved installation amendment.

This module performs no I/O and grants no release or execution authority. The
caller supplies source-validated obligations and complete, protected live scans;
only a separately verified durable seal may select ``after`` for admission.
Every quote is recomputed from one observation, including actual record growth.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import PurePosixPath as P
import re
import stat

MAX_INTEGER = 2**63 - 1
MIB = 1024**2
CATEGORIES = ("installation", "state", "journal", "capture")
CEILINGS = {"installation": dict(bytes=256 * MIB, inodes=16384),
    "state": dict(bytes=32 * MIB, inodes=4096),
    "journal": dict(bytes=64 * MIB, inodes=4096),
    "capture": dict(bytes=64 * MIB, inodes=4096)}
INSTALLATIONS = (dict(bytes=192 * MIB, inodes=8192), dict(bytes=64 * MIB, inodes=4096))
OWNER_POOL = dict(bytes=20 * MIB, inodes=384)
BASE_STATE = dict(bytes=13185024, inodes=33)
RECONCILIATION_STATE = dict(bytes=MIB, inodes=16)
NEW_IDS = {"new-installation", "new-state", "new-owner-pool", "reconciliation-state", "new-staging"}
_METADATA = {"device", "inode", "st_mode", "uid", "gid", "nlink", "size", "blocks",
    "atime_ns", "mtime_ns", "ctime_ns"}
_LEGACY_KEYS = {"id", "category", "commitment", "covered_paths", "evidence", "accounting_categories"}
_NEW_KEYS = {"id", "category", "commitment", "covered_paths", "excluded_paths", "accounting_categories", "devices"}


def require(condition, code):
    if not condition:
        raise ValueError("RECONCILIATION_BILL_" + code)


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), "FIELDS")


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= MAX_INTEGER, "INTEGER")
    return value


def add(*values):
    result = 0
    for value in values:
        result += integer(value)
        require(result <= MAX_INTEGER, "OVERFLOW")
    return result


def amount(value):
    keys(value, ("bytes", "inodes"))
    return {key: integer(value[key]) for key in ("bytes", "inodes")}


def text(value, limit=128):
    require(type(value) is str and 0 < len(value.encode("utf-8")) <= limit and "\0" not in value,
        "TEXT")
    return value


def path(value):
    text(value, 4096)
    require(value.startswith("/") and value != "/" and str(P(value)) == value
        and all(part not in ("", ".", "..") for part in value.split("/")[1:]), "PATH_ALIAS")
    return value


def contains(parent, child):
    # All callers validate canonical paths before membership comparisons.
    return parent == child or child.startswith(parent + "/")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def _paths(values, *, empty=False):
    require(type(values) is list and (empty or bool(values)) and len(values) <= 128, "PATHS")
    for name in values:
        path(name)
    require(len(set(values)) == len(values), "PATH_ALIAS")
    require(all(not contains(a, b) and not contains(b, a)
        for index, a in enumerate(values) for b in values[index + 1:]), "PATH_OVERLAP")
    return values


def _scans(scans, expected_roots):
    require(type(scans) is dict and type(expected_roots) is dict and scans
        and set(scans) == set(expected_roots) and len(scans) <= 128, "SCAN_COVERAGE")
    roots = list(scans)
    for root in roots:
        path(root)
    # Complete Q1 trees can enclose separately accounted capture/journal trees.
    # This is duplicate observation of an exact path, not another actual inode.
    # Both observations must match every recorded field and complete membership.
    for index, root in enumerate(roots):
        for other in roots[index + 1:]:
            if contains(root, other):
                require(expected_roots[root] == "quota", "SCAN_OVERLAP")
            if contains(other, root):
                require(expected_roots[other] == "quota", "SCAN_OVERLAP")
    objects = {}; identities = {}; evidence = {}; members = {}; logical_actual = {}
    for root in roots:
        category = expected_roots[root]
        require(category in (*CATEGORIES, "quota"), "CATEGORY")
        scan = scans[root]
        keys(scan, ("path", "entries", "bytes", "inodes", "device", "logical_bytes"))
        require(scan["path"] == root, "SCAN_ROOT")
        integer(scan["device"], 1)
        entries = scan["entries"]
        require(type(entries) is list and 0 < len(entries) <= 32768, "SCAN_ENTRIES")
        local = {}; allocated = logical = 0
        for entry in entries:
            require(type(entry) is dict and entry.get("type") in ("directory", "file", "symlink"), "ENTRY_TYPE")
            kind = entry["type"]
            extra = ("sha256",) if kind == "file" else ("link_target",) if kind == "symlink" else ()
            keys(entry, ("relative_path", "type", "source_metadata", *extra))
            relative = text(entry["relative_path"], 4096)
            require(relative == "." or not relative.startswith("/") and str(P(relative)) == relative
                and all(part not in ("", ".", "..") for part in relative.split("/")), "RELATIVE_PATH")
            name = root if relative == "." else root + "/" + relative
            path(name)
            require(relative not in local, "PATH_ALIAS")
            metadata = entry["source_metadata"]
            keys(metadata, _METADATA)
            for key in _METADATA:
                integer(metadata[key], 1 if key in ("device", "inode", "nlink") else 0)
            require(metadata["device"] == scan["device"], "TREE_DEVICE")
            identifier = (metadata["device"], metadata["inode"])
            require(identifier not in identities or identities[identifier] == name, "ACTUAL_ALIAS")
            identities[identifier] = name
            expected_type = {"directory": stat.S_IFDIR, "file": stat.S_IFREG, "symlink": stat.S_IFLNK}[kind]
            require(stat.S_IFMT(metadata["st_mode"]) == expected_type, "ENTRY_MODE")
            if kind == "file":
                require(metadata["nlink"] == 1, "HARDLINK")
                require(type(entry["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), "SHA256")
                logical = add(logical, metadata["size"])
                logical_actual[name] = metadata["size"]
            if kind == "symlink":
                text(entry["link_target"], 4096)
            require(metadata["blocks"] <= MAX_INTEGER // 512, "OVERFLOW")
            cost = dict(bytes=metadata["blocks"] * 512, inodes=1)
            allocated = add(allocated, cost["bytes"])
            observed = {key: value for key, value in entry.items() if key != "relative_path"}
            require(name not in evidence or evidence[name] == observed, "REPEATED_OBSERVATION_CHANGED")
            evidence[name] = observed
            # The narrower protected cost root owns objects also visible in
            # Q1's complete preservation scan. Never credit two obligations.
            selected_root = max((candidate for candidate in roots if contains(candidate, name)), key=len)
            objects[name] = dict(path=name, device=metadata["device"], inode=metadata["inode"],
                category=expected_roots[selected_root], **cost)
            local[relative] = kind
            require(len(objects) <= 32768, "SCAN_ENTRIES")
        require("." in local, "MISSING_ROOT")
        for relative in local:
            if relative != ".":
                require(local.get(str(P(relative).parent)) == "directory", "MISSING_PARENT")
        for key, actual in (("bytes", allocated), ("inodes", len(entries)), ("logical_bytes", logical)):
            require(integer(scan[key]) == actual, "SCAN_TOTAL")
        members[root] = {root if relative == "." else root + "/" + relative for relative in local}
    for root in roots:
        require(members[root] == {name for name in objects if contains(root, name)}, "NESTED_SCAN_COVERAGE")
    require(add(*logical_actual.values()) <= 512 * MIB
        and add(*(row["bytes"] for row in objects.values())) <= 512 * MIB, "SCAN_BYTES")
    return objects


def _sum(objects):
    result = dict(bytes=0, inodes=0)
    for row in objects:
        for key in result:
            result[key] = add(result[key], row[key])
    return result


def _covered(objects, paths, excluded=()):
    return [row for name, row in objects.items() if any(contains(root, name) for root in paths)
        and not any(contains(root, name) for root in excluded)]


def _old_obligations(obligations, targets):
    require(type(obligations) is list and len(obligations) == 7, "OLD_OBLIGATIONS")
    require(type(targets) in (tuple, list) and len(targets) == 2, "TARGETS")
    _paths(list(targets))
    expected = (INSTALLATIONS[0], dict(bytes=18788352, inodes=0), OWNER_POOL,
        INSTALLATIONS[1], dict(bytes=11071488, inodes=608), OWNER_POOL,
        dict(bytes=290816, inodes=17))
    seen = set()
    for index, row in enumerate(obligations):
        keys(row, _LEGACY_KEYS)
        text(row["id"])
        require(row["id"] not in seen, "OBLIGATION_ALIAS")
        seen.add(row["id"])
        owner = index in (2, 5)
        categories = ["capture", "journal"] if owner else ["installation"]
        require(row["category"] == categories[0] and row["accounting_categories"] == categories,
            "OBLIGATION_CATEGORY")
        require(amount(row["commitment"]) == expected[index], "OLD_COMMITMENT")
        _paths(row["covered_paths"])
        _paths(row["evidence"])
        if index in (0, 3):
            require(row["covered_paths"] == [targets[index // 3]], "TARGET_BINDING")
    # Logical nested aliases are rejected even if currently empty; no actual
    # from staging/owner pools may cancel a target's future commitment.
    _paths([name for row in obligations for name in row["covered_paths"]])


def _new_obligations(rows):
    require(type(rows) is list and len(rows) == len(NEW_IDS), "NEW_OBLIGATIONS")
    require(all(type(row) is dict for row in rows), "FIELDS")
    for row in rows:
        text(row.get("id"))
    require({row.get("id") for row in rows} == NEW_IDS, "NEW_IDS")
    by_id = {row["id"]: row for row in rows}
    for row in rows:
        keys(row, _NEW_KEYS)
        _paths(row["covered_paths"])
        _paths(row["excluded_paths"], empty=True)
        amount(row["commitment"])
        categories = ["capture", "journal"] if row["id"] == "new-owner-pool" else [
            "state" if row["id"] in ("new-state", "reconciliation-state") else "installation"]
        require(row["category"] == categories[0] and row["accounting_categories"] == categories,
            "OBLIGATION_CATEGORY")
        require(type(row["devices"]) is list and row["devices"] and len(row["devices"]) <= 3, "DEVICES")
        for value in row["devices"]:
            integer(value, 1)
        require(len(set(row["devices"])) == len(row["devices"]), "DEVICE_ALIAS")
        if row["id"] != "new-state":
            require(row["excluded_paths"] == [], "EXCLUSIONS")
    for identity, expected in (("new-installation", INSTALLATIONS[1]), ("new-state", BASE_STATE),
            ("new-owner-pool", OWNER_POOL), ("reconciliation-state", RECONCILIATION_STATE)):
        require(by_id[identity]["commitment"] == expected, "NEW_COMMITMENT")
    reconciliation = by_id["reconciliation-state"]["covered_paths"]
    require(len(reconciliation) == 1, "RECONCILIATION_ROOT")
    expected_exclusions = reconciliation if any(contains(root, reconciliation[0])
        for root in by_id["new-state"]["covered_paths"]) else []
    require(by_id["new-state"]["excluded_paths"] == expected_exclusions, "EXCLUSIONS")
    # Otherwise different new obligations must describe disjoint future space,
    # including before any of their paths has been created.
    for index, row in enumerate(rows):
        for other in rows[index + 1:]:
            for a in row["covered_paths"]:
                for b in other["covered_paths"]:
                    if contains(a, b) or contains(b, a):
                        require({row["id"], other["id"]} == {"new-state", "reconciliation-state"}
                            and a != b, "FUTURE_OVERLAP")
    return by_id


def quote_bill(scans, obligations, new_obligations, quotas, devices, *, installation_targets,
        expected_roots, quota_expected, sealed=False):
    """Return before/proposed-after and selected current accounting.

    ``scans`` maps exact roots to q2_reconciliation_io snapshots;
    ``expected_roots`` maps those same complete roots to four cost categories or
    ``quota``. All seven normalized historical rows come from the unchanged
    reservation_obligations adapter, in its original order. Five named new rows
    reserve installation, base state, shared owner pool, reconciliation state and
    staging separately. New paths may be genuinely absent; old paths may not.
    ``sealed`` is caller state after independent seal verification, never input
    permission. Quoting does not reject the historical over-limit before bill.
    """
    require(type(sealed) is bool, "SEALED_STATE")
    objects = _scans(scans, expected_roots)
    _old_obligations(obligations, installation_targets)
    new_by_id = _new_obligations(new_obligations)
    require(type(devices) is list and 0 < len(devices) <= 4, "DEVICES")
    device_map = {}
    for row in devices:
        keys(row, ("device", "available_bytes", "free_inodes"))
        for key in row:
            integer(row[key], 1 if key == "device" else 0)
        require(row["device"] not in device_map, "DEVICE_ALIAS")
        device_map[row["device"]] = row
    require(all(row["device"] in device_map for row in objects.values()), "UNKNOWN_DEVICE")
    actual = _sum(objects.values())
    actual_categories = {category: _sum(row for row in objects.values() if row["category"] == category)
        for category in (*CATEGORIES, "quota")}
    actual_devices = {device: _sum(row for row in objects.values() if row["device"] == device)
        for device in device_map}
    proofs = []; ownership = {}; all_old_paths = [name for row in obligations for name in row["covered_paths"]]
    for is_new, rows in ((False, obligations), (True, new_obligations)):
        for index, row in enumerate(rows):
            paths = row["covered_paths"]
            excluded = row["excluded_paths"] if is_new else []
            if not is_new:
                require(all(name in objects for name in paths), "MISSING_OLD_TREE")
            else:
                require(all(not contains(a, b) and not contains(b, a)
                    for a in paths for b in all_old_paths), "NEW_OLD_OVERLAP")
            covered = _covered(objects, paths, excluded)
            require(all(item["category"] in row["accounting_categories"] for item in covered), "COVERAGE_CATEGORY")
            for item in covered:
                identifier = (item["device"], item["inode"])
                require(identifier not in ownership, "DOUBLE_CREDIT")
                ownership[identifier] = row["id"]
            observed_devices = {item["device"] for item in covered}
            target_devices = set(row["devices"]) if is_new else observed_devices
            require(target_devices and target_devices <= device_map.keys()
                and observed_devices <= target_devices, "OBLIGATION_DEVICE")
            used = _sum(covered)
            unspent = {key: max(0, row["commitment"][key] - used[key]) for key in used}
            terminated = not is_new and index in (0, 3)
            if is_new and row["id"] == "reconciliation-state":
                require(all(used[key] <= RECONCILIATION_STATE[key] for key in used), "STATE_SUBBUDGET")
            proofs.append(dict(id=row["id"], origin="new" if is_new else "historical",
                category=row["category"], accounting_categories=copy.deepcopy(row["accounting_categories"]),
                commitment=copy.deepcopy(row["commitment"]), actual=used, unspent=unspent,
                terminated_by_amendment=terminated, covered_paths=copy.deepcopy(paths),
                excluded_paths=copy.deepcopy(excluded), devices=sorted(target_devices),
                coverage_count=len(covered), coverage_sha256=digest(sorted(covered, key=lambda item: item["path"]))))
    quota_proofs = _quotas(quotas, quota_expected, device_map)
    def bill(amended):
        categories = {name: dict(actual=copy.deepcopy(actual_categories[name]), future=dict(bytes=0, inodes=0))
            for name in CATEGORIES}
        by_device = {device: dict(actual=copy.deepcopy(actual_devices[device]), future=dict(bytes=0, inodes=0),
            available=dict(bytes=row["available_bytes"], inodes=row["free_inodes"])) for device, row in device_map.items()}
        future = dict(bytes=0, inodes=0)
        for proof in proofs:
            if amended and proof["terminated_by_amendment"]:
                continue
            for key in future:
                future[key] = add(future[key], proof["unspent"][key])
                for name in proof["accounting_categories"]:
                    categories[name]["future"][key] = add(categories[name]["future"][key], proof["unspent"][key])
                # A shared pool is counted once per possible device, never once
                # per category on the same device. Categories retain worst-case
                # exposure because no narrower durable allocation exists.
                for device in proof["devices"]:
                    by_device[device]["future"][key] = add(by_device[device]["future"][key], proof["unspent"][key])
        for proof in quota_proofs:
            for key in future:
                future[key] = add(future[key], proof["unspent"][key])
                device = by_device[proof["device"]]
                device["future"][key] = add(device["future"][key], proof["unspent"][key])
        for name, row in categories.items():
            row["admitted"] = {key: add(row["actual"][key], row["future"][key]) for key in future}
            row["ceiling"] = copy.deepcopy(CEILINGS[name])
            row["within_ceiling"] = all(row["admitted"][key] <= row["ceiling"][key] for key in future)
        for row in by_device.values():
            row["within_capacity"] = all(row["future"][key] <= row["available"][key] for key in future)
        return dict(actual=copy.deepcopy(actual), future=future,
            total={key: add(actual[key], future[key]) for key in future}, categories=categories,
            by_device=by_device, admissible=all(row["within_ceiling"] for row in categories.values())
                and all(row["within_capacity"] for row in by_device.values()))
    before, after = bill(False), bill(True)
    terminated = {key: add(*(proof["unspent"][key] for proof in proofs if proof["terminated_by_amendment"]))
        for key in ("bytes", "inodes")}
    require(all(before["total"][key] - after["total"][key] == terminated[key] for key in terminated), "DELTA")
    return dict(schema="local-hand-q2-reconciliation-bill/v1", before=before, proposed_after=after,
        current=copy.deepcopy(after if sealed else before), sealed=sealed, terminated_unspent=terminated,
        obligations=proofs, quota_domains=quota_proofs, actual_count=len(objects),
        actual_sha256=digest(sorted(objects.values(), key=lambda item: item["path"])),
        observations_sha256=digest(scans), historical_results_unchanged=True)


def _quotas(quotas, expected, devices):
    require(type(quotas) is list and 11 <= len(quotas) <= 32768
        and type(expected) is list and len(expected) == 11, "QUOTA_COVERAGE")
    pins = {}
    for row in expected:
        keys(row, ("uuid", "project", "hard_bytes", "hard_inodes"))
        text(row["uuid"])
        for key in ("project", "hard_bytes", "hard_inodes"):
            integer(row[key], 1)
        identity = (row["uuid"], row["project"])
        require(identity not in pins, "QUOTA_ALIAS")
        pins[identity] = row
    new = [row for row in expected if row["hard_bytes"] == MIB and row["hard_inodes"] == 128]
    retained = [row for row in expected if row not in new]
    require(len(new) == 7 and len(retained) == 4 and add(*(row["hard_bytes"] for row in retained)) == 196 * MIB,
        "QUOTA_FIXED_COMMITMENTS")
    seen = set(); result = []; filesystem_devices = {}; device_filesystems = {}
    for row in quotas:
        keys(row, ("uuid", "device", "project", "hard_bytes", "hard_inodes", "used_bytes", "used_inodes"))
        text(row["uuid"])
        for key in ("device", "project", "hard_bytes", "hard_inodes", "used_bytes", "used_inodes"):
            # quotactl's complete inventory includes the project-0 background
            # row and may contain other unbounded zero-hard rows. Preserve
            # their observed usage; zero is not a new issued commitment. Only
            # the eleven exact scope domains above require positive hard pins.
            integer(row[key], 1 if key == "device" else 0)
        identity = (row["uuid"], row["project"])
        require(identity not in seen and row["device"] in devices, "QUOTA_ALIAS")
        require(filesystem_devices.get(row["uuid"], row["device"]) == row["device"]
            and device_filesystems.get(row["device"], row["uuid"]) == row["uuid"], "QUOTA_DEVICE_ALIAS")
        filesystem_devices[row["uuid"]] = row["device"]
        device_filesystems[row["device"]] = row["uuid"]
        seen.add(identity)
        if identity in pins:
            require(all(row[key] == pins[identity][key] for key in ("hard_bytes", "hard_inodes")), "QUOTA_CHANGED")
        # Usage above hard limits remains actual, never creates negative future.
        result.append(dict(row, unspent={key: max(0, row["hard_" + key] - row["used_" + key])
            for key in ("bytes", "inodes")}))
    require(pins.keys() <= seen, "QUOTA_MISSING")
    return result


def require_admissible(quote, *, proposed=False):
    """Choose the write-time proposal or seal-time current bill, never before."""
    require(type(proposed) is bool, "PROPOSED_STATE")
    require(type(quote) is dict and quote.get("schema") == "local-hand-q2-reconciliation-bill/v1", "QUOTE")
    if not proposed:
        require(quote.get("sealed") is True, "MISSING_SEAL")
    selected = quote["proposed_after" if proposed else "current"]
    require(selected["admissible"] is True, "CAPACITY")
    return copy.deepcopy(selected)


def startup_costs(quote, *, proposed=False):
    """Translate an admitted quote for existing downstream bounded assembly."""
    selected = require_admissible(quote, proposed=proposed)
    result = {}
    for category, row in selected["categories"].items():
        result[category] = dict(row["actual"])
        for key in ("bytes", "inodes"):
            retained = add(*(proof["unspent"][key] for proof in quote["obligations"]
                if proof["origin"] == "historical" and not proof["terminated_by_amendment"]
                and category in proof["accounting_categories"]))
            new = [proof for proof in quote["obligations"] if proof["origin"] == "new"
                and category in proof["accounting_categories"]]
            result[category].update({"retained_unspent_" + key: retained,
                "new_future_" + key: add(*(proof["commitment"][key] for proof in new)),
                "new_unspent_" + key: add(*(proof["unspent"][key] for proof in new)),
                "admitted_" + key: row["admitted"][key]})
    return result
