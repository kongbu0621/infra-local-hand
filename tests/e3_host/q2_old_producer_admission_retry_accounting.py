"""Pure synthetic accounting and predecessor-coverage checks for the retry.

All identities and observations must be supplied as data.  Nothing here reads a
machine, qualifies a filesystem, writes a record, or grants field authority.
In particular, an offline bill cannot establish that its inventory is complete.
"""
from __future__ import annotations

import copy
import re

from . import q2_old_producer_admission_retry_contract as c


ACCOUNTING_SCHEMA = "local-hand-q2-old-producer-admission-retry-accounting-input/v1"
RESULT_SCHEMA = "local-hand-q2-old-producer-admission-retry-accounting-result/v1"
INVENTORY_SCHEMA = "local-hand-q2-old-producer-admission-retry-predecessor-inventory/v1"
INVENTORY_RESULT_SCHEMA = "local-hand-q2-old-producer-admission-retry-predecessor-coverage/v1"
MAX_INTEGER = 2**63 - 1
MAX_ROWS = 8192
CAPTURE_BYTES = 20 * 1024**2
CAPTURE_INODES = 384
RECORD_BYTES = 64 * 1024
RECORD_INODES = 4
OLD_BATCH = "20261001e"
NEW_BATCH = c.BATCH
QUOTA_ROLES = tuple(c.PROJECTS)
FULL_BUDGETS = {
    "code_pool": (64 * 1024**2, 4096),
    "management": (32 * 1024**2, 1024),
    "state": (8 * 1024**2, 1536),
    "journal": (1024**2, 128),
    "capture": (CAPTURE_BYTES, CAPTURE_INODES),
    **{"quota." + role: (1024**2, 128) for role in QUOTA_ROLES},
}
PHASES = {
    "record": ("create", "write", "file_sync", "directory_sync", "parent_sync"),
    "evidence": ("partial", "final", "file_sync", "parent_sync"),
}


def _require(condition, reason):
    if not condition:
        raise ValueError("OLD_PRODUCER_RETRY_ACCOUNTING_" + reason)


def _keys(value, names):
    _require(type(value) is dict and set(value) == set(names), "FIELDS")


def _integer(value, low=0, high=MAX_INTEGER):
    _require(type(value) is int and low <= value <= high, "INTEGER")
    return value


def _token(value):
    _require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value)
        is not None, "TOKEN")
    return value


def _rows(value, *, minimum=0):
    _require(type(value) is list and minimum <= len(value) <= MAX_ROWS, "ROWS")
    return value


def _add(left, right):
    return _integer(left + right)


def _same(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _object(value):
    _keys(value, ("object_id", "device", "inode", "allocated_bytes", "inodes",
        "reflected_in_free"))
    _token(value["object_id"])
    _integer(value["device"], 1)
    _integer(value["inode"], 1)
    _integer(value["allocated_bytes"])
    _integer(value["inodes"], 1, 1)
    _require(value["reflected_in_free"] is True, "ACTUAL_NOT_FREE_REFLECTED")
    return copy.deepcopy(value)


def _objects(values):
    """Deduplicate physical aliases; conflicting observations never coalesce."""
    result, object_ids = {}, set()
    for raw in _rows(values):
        item = _object(raw)
        _require(item["object_id"] not in object_ids, "DUPLICATE_OBJECT_ID")
        object_ids.add(item["object_id"])
        key = (item["device"], item["inode"])
        if key in result:
            _require((item["allocated_bytes"], item["inodes"])
                == (result[key]["allocated_bytes"], result[key]["inodes"]),
                "PHYSICAL_ALIAS_CONFLICT")
        else:
            result[key] = item
    return result


def _totals(objects):
    amount, inodes = 0, 0
    for item in objects.values():
        amount = _add(amount, item["allocated_bytes"])
        inodes = _add(inodes, item["inodes"])
    return amount, inodes


def _phase_object(value, *, metadata=False):
    _keys(value, ("object_id", "device", "inode", "allocated_bytes", "inodes"))
    _token(value["object_id"])
    _integer(value["device"], 1)
    _integer(value["inode"], 1)
    _integer(value["allocated_bytes"])
    _integer(value["inodes"], 0 if metadata else 1, 1)
    return copy.deepcopy(value)


def calculate_peak(value, *, kind):
    """Calculate a synthetic write/sync peak, preserving unknowns explicitly.

    Phase snapshots describe physical objects at one instant, rather than
    cumulative allocations.  The same archive inode occurs in partial and final
    snapshots and contributes only to the maximum.  Extra metadata/sync objects
    must have distinct physical identities, so covered allocations cannot be
    charged a second time.
    """
    _require(type(kind) is str and kind in PHASES, "PEAK_KIND")
    _keys(value, ("device", "parent_baseline", "qualification", "snapshots"))
    device = _integer(value["device"], 1)
    baseline = value["parent_baseline"]
    _keys(baseline, ("device", "inode", "allocated_bytes", "inodes", "coverage"))
    _require(_integer(baseline["device"], 1) == device, "PARENT_DEVICE")
    _integer(baseline["inode"], 1)
    _integer(baseline["inodes"], 1, 1)
    _token(baseline["coverage"])
    if baseline["allocated_bytes"] is not None:
        _integer(baseline["allocated_bytes"], 4096)
    _require(value["qualification"] in ("SYNTHETIC_BOUND", "UNKNOWN"),
        "PEAK_QUALIFICATION")
    blockers = []
    if baseline["allocated_bytes"] is None or baseline["coverage"] == "UNKNOWN":
        blockers.append(kind.upper() + "_PARENT_BASELINE_UNKNOWN")
    if value["qualification"] == "UNKNOWN":
        blockers.append(kind.upper() + "_PEAK_UNKNOWN")
    snapshots = value["snapshots"]
    if snapshots is None:
        _require(value["qualification"] == "UNKNOWN", "PEAK_SNAPSHOTS")
        return dict(kind=kind, device=device, complete=False, allocated_bytes=None,
            inodes=None, objects={}, parent_growth_bytes=None, blockers=blockers)
    _rows(snapshots, minimum=len(PHASES[kind]))
    _require(tuple(item.get("phase") if type(item) is dict else None for item in snapshots)
        == PHASES[kind], "PEAK_PHASES")
    maximum_bytes, maximum_inodes, growth_max = 0, 0, 0
    identities, role_identities = {}, {}
    phase_totals = []
    for snapshot in snapshots:
        _keys(snapshot, ("phase", "objects", "parent_growth_bytes", "metadata_sync"))
        objects, names = {}, set()
        for field in ("objects", "metadata_sync"):
            for raw in _rows(snapshot[field]):
                item = _phase_object(raw, metadata=field == "metadata_sync")
                _require(item["device"] == device, "PEAK_DEVICE")
                _require(item["object_id"] not in names, "DUPLICATE_OBJECT_ID")
                names.add(item["object_id"])
                key = (device, item["inode"])
                _require(key != (device, baseline["inode"]) and key not in objects,
                    "PEAK_PHYSICAL_OVERLAP")
                objects[key] = item
                role = (field, item["object_id"])
                if role in role_identities:
                    _require(role_identities[role] == key, "PEAK_IDENTITY_DRIFT")
                role_identities[role] = key
                old = identities.get(key)
                if old is None:
                    identities[key] = dict(item)
                else:
                    _require((old["object_id"], old["inodes"])
                        == (item["object_id"], item["inodes"]), "PEAK_IDENTITY_DRIFT")
                    old["allocated_bytes"] = max(old["allocated_bytes"], item["allocated_bytes"])
        object_names = {item["object_id"] for item in snapshot["objects"]}
        required = ({"directory"} if kind == "record" and snapshot["phase"] == "create"
            else {"directory", "intent"} if kind == "record" else {"archive"})
        _require(object_names == required, "PEAK_OBJECT_COVERAGE")
        growth = _integer(snapshot["parent_growth_bytes"])
        growth_max = max(growth_max, growth)
        amount, inode_count = _totals(objects)
        amount = _add(amount, growth)
        maximum_bytes = max(maximum_bytes, amount)
        maximum_inodes = max(maximum_inodes, inode_count)
        phase_totals.append(dict(phase=snapshot["phase"], allocated_bytes=amount,
            inodes=inode_count))
    if kind == "record":
        _require(maximum_bytes <= RECORD_BYTES and maximum_inodes <= RECORD_INODES,
            "RECORD_SUBRESERVATION_EXCEEDED")
    _require(maximum_bytes <= CAPTURE_BYTES and maximum_inodes <= CAPTURE_INODES,
        "PEAK_CAPTURE_EXCEEDED")
    return dict(kind=kind, device=device, complete=not blockers,
        allocated_bytes=None if blockers else maximum_bytes,
        inodes=None if blockers else maximum_inodes, objects=identities,
        parent_growth_bytes=None if blockers else growth_max, phase_totals=phase_totals,
        blockers=blockers)


def _commitments(values):
    result, categories = {}, set()
    for value in _rows(values):
        _keys(value, ("reservation_id", "batch", "category", "device", "allocated_bytes",
            "inodes", "status"))
        for field in ("reservation_id", "batch", "category"):
            _token(value[field])
        _integer(value["device"], 1)
        _integer(value["allocated_bytes"])
        _integer(value["inodes"])
        _require(value["status"] == "UNRELEASED", "RELEASE_OR_REFUND")
        _require(value["reservation_id"] not in result, "DUPLICATE_RESERVATION")
        key = (value["batch"], value["category"])
        _require(key not in categories, "DUPLICATE_COMMITMENT_CATEGORY")
        categories.add(key)
        if value["batch"] in (OLD_BATCH, NEW_BATCH):
            _require(value["category"] in FULL_BUDGETS, "FIXED_BUDGET_CATEGORY")
            _require((value["allocated_bytes"], value["inodes"])
                == FULL_BUDGETS[value["category"]], "FULL_COMMITMENT_CHANGED")
            _require(not (value["batch"] == NEW_BATCH and value["category"] == "capture"),
                "CURRENT_CAPTURE_DOUBLE_RESERVATION")
        result[value["reservation_id"]] = copy.deepcopy(value)
    for batch in (OLD_BATCH, NEW_BATCH):
        wanted = {(batch, category) for category in FULL_BUDGETS
            if batch == OLD_BATCH or category != "capture"}
        _require(wanted <= categories, "FULL_COMMITMENT_MISSING")
    return result


def evaluate_accounting(value):
    """Return synthetic capture and per-device admission, with no field mode."""
    _keys(value, ("schema", "predecessor", "historical_inventory", "devices",
        "commitments", "observed_allocations", "capture"))
    _require(value["schema"] == ACCOUNTING_SCHEMA, "SCHEMA")
    _require(_same(value["predecessor"], c.PREDECESSOR), "PREDECESSOR_IMMUTABLE")
    commitments = _commitments(value["commitments"])
    inventory = value["historical_inventory"]
    _keys(inventory, ("status", "expected_reservation_ids"))
    _require(inventory["status"] in ("SYNTHETIC_COMPLETE", "UNKNOWN"), "INVENTORY_STATUS")
    expected = [_token(item) for item in _rows(inventory["expected_reservation_ids"])]
    _require(len(expected) == len(set(expected)), "DUPLICATE_INVENTORY_RESERVATION")
    historical_ids = {name for name, item in commitments.items() if item["batch"] != NEW_BATCH}
    _require(set(expected) == historical_ids, "HISTORICAL_INVENTORY_COVERAGE")
    blockers = []
    if inventory["status"] == "UNKNOWN":
        blockers.append("HISTORICAL_OBLIGATION_INVENTORY_UNKNOWN")
    devices = {}
    for item in _rows(value["devices"], minimum=1):
        _keys(item, ("device", "available_bytes", "available_inodes"))
        device = _integer(item["device"], 1)
        _require(device not in devices, "DUPLICATE_DEVICE")
        _integer(item["available_bytes"])
        _integer(item["available_inodes"])
        devices[device] = dict(item, historical_bytes=0, historical_inodes=0,
            current_commitment_bytes=0, current_commitment_inodes=0,
            capture_future_bytes=0, capture_future_inodes=0, capture_peak_bytes=0,
            capture_peak_inodes=0, observed_free_reflected_bytes=0,
            observed_free_reflected_inodes=0)
    observed = _objects(value["observed_allocations"])
    capture = value["capture"]
    _keys(capture, ("actual", "future", "record_peak", "evidence_peak"))
    actual = _objects(capture["actual"])
    for identity, item in actual.items():
        _require(identity in observed and (item["allocated_bytes"], item["inodes"])
            == (observed[identity]["allocated_bytes"], observed[identity]["inodes"]),
            "CAPTURE_ACTUAL_OBSERVATION")
    for item in observed.values():
        _require(item["device"] in devices, "DEVICE_MISSING")
        device = devices[item["device"]]
        for field, source in (("observed_free_reflected_bytes", "allocated_bytes"),
            ("observed_free_reflected_inodes", "inodes")):
            device[field] = _add(device[field], item[source])
    for item in commitments.values():
        _require(item["device"] in devices, "DEVICE_MISSING")
        device = devices[item["device"]]
        prefix = "current_commitment" if item["batch"] == NEW_BATCH else "historical"
        device[prefix + "_bytes"] = _add(device[prefix + "_bytes"], item["allocated_bytes"])
        device[prefix + "_inodes"] = _add(device[prefix + "_inodes"], item["inodes"])
    future_bytes, future_inodes, future_ids = 0, 0, set()
    for item in _rows(capture["future"]):
        _keys(item, ("reservation_id", "device", "allocated_bytes", "inodes",
            "excludes_peak_subreservations"))
        reservation = _token(item["reservation_id"])
        _require(reservation not in commitments and reservation not in future_ids,
            "DUPLICATE_RESERVATION")
        future_ids.add(reservation)
        device_id = _integer(item["device"], 1)
        _require(device_id in devices, "DEVICE_MISSING")
        amount, inode_count = _integer(item["allocated_bytes"]), _integer(item["inodes"])
        _require(item["excludes_peak_subreservations"] is True,
            "CAPTURE_SUBRESERVATION_DOUBLE_CHARGE")
        future_bytes = _add(future_bytes, amount)
        future_inodes = _add(future_inodes, inode_count)
        device = devices[device_id]
        device["capture_future_bytes"] = _add(device["capture_future_bytes"], amount)
        device["capture_future_inodes"] = _add(device["capture_future_inodes"], inode_count)
    peaks = {kind: calculate_peak(capture[kind + "_peak"], kind=kind) for kind in PHASES}
    # Every new record/archive/metadata object is exclusive, including with
    # respect to retained objects outside the current capture category.
    used_identities = set(observed)
    parent_growth = {}
    shared_parent_unknown = False
    for kind, peak in peaks.items():
        _require(peak["device"] in devices, "DEVICE_MISSING")
        blockers.extend(peak["blockers"])
        baseline = capture[kind + "_peak"]["parent_baseline"]
        identity = (baseline["device"], baseline["inode"])
        coverage = baseline["coverage"]
        if coverage != "UNKNOWN" and baseline["allocated_bytes"] is not None:
            _require(identity in observed and observed[identity]["allocated_bytes"]
                == baseline["allocated_bytes"], "PARENT_BASELINE_OBSERVATION")
            if coverage == "capture.actual":
                _require(identity in actual, "PARENT_BASELINE_COVERAGE")
            else:
                _require(coverage in commitments and commitments[coverage]["device"]
                    == baseline["device"], "PARENT_BASELINE_COVERAGE")
        _require(not (set(peak["objects"]) & used_identities), "PEAK_PHYSICAL_OVERLAP")
        used_identities.update(peak["objects"])
        if not peak["complete"]:
            continue
        # Matching parent aliases are one existing allocation.  If both paths
        # can grow it, independent phase snapshots do not establish a bound on
        # their joint peak.  Refuse that unknown rather than adding it twice or
        # subtracting a speculative overlap.
        if identity in parent_growth:
            prior = parent_growth[identity]
            _require(_same(prior["baseline"], baseline), "PARENT_BASELINE_ALIAS_CONFLICT")
            if peak["parent_growth_bytes"] or prior["growth"]:
                blockers.append("SHARED_PARENT_JOINT_PEAK_UNKNOWN")
                shared_parent_unknown = True
        else:
            parent_growth[identity] = dict(baseline=copy.deepcopy(baseline),
                growth=peak["parent_growth_bytes"])
        device = devices[peak["device"]]
        device["capture_peak_bytes"] = _add(device["capture_peak_bytes"], peak["allocated_bytes"])
        device["capture_peak_inodes"] = _add(device["capture_peak_inodes"], peak["inodes"])
    actual_bytes, actual_inodes = _totals(actual)
    complete = all(peak["complete"] for peak in peaks.values()) and not shared_parent_unknown
    peak_bytes = sum(item["capture_peak_bytes"] for item in devices.values())
    peak_inodes = sum(item["capture_peak_inodes"] for item in devices.values())
    _integer(peak_bytes)
    _integer(peak_inodes)
    total_bytes = _add(_add(actual_bytes, future_bytes), peak_bytes) if complete else None
    total_inodes = _add(_add(actual_inodes, future_inodes), peak_inodes) if complete else None
    if complete and (total_bytes > CAPTURE_BYTES or total_inodes > CAPTURE_INODES):
        blockers.append("GLOBAL_CAPTURE_CEILING_EXCEEDED")
    bills = []
    for device in sorted(devices):
        bill = devices[device]
        demand_bytes = _add(_add(bill["historical_bytes"], bill["current_commitment_bytes"]),
            _add(bill["capture_future_bytes"], bill["capture_peak_bytes"]))
        demand_inodes = _add(_add(bill["historical_inodes"], bill["current_commitment_inodes"]),
            _add(bill["capture_future_inodes"], bill["capture_peak_inodes"]))
        if not complete:
            demand_bytes = demand_inodes = None
            bill["capture_peak_bytes"] = bill["capture_peak_inodes"] = None
        within_free = (complete and demand_bytes <= bill["available_bytes"]
            and demand_inodes <= bill["available_inodes"])
        if complete and not within_free:
            blockers.append("DEVICE_" + str(device) + "_CAPACITY_EXCEEDED")
        bills.append(dict(bill, future_demand_bytes=demand_bytes,
            future_demand_inodes=demand_inodes, offline_within_free=within_free))
    return dict(schema=RESULT_SCHEMA, status="OFFLINE_ACCOUNTING_VERIFIED"
        if not blockers else "OFFLINE_ACCOUNTING_BLOCKED", offline_admitted=not blockers,
        field_ready=False, allow_run=False, guest_executed=False,
        field_qualification="NOT_ESTABLISHED_BY_SYNTHETIC_DATA",
        normal_chain_executions=0, resource_refund=False, blockers=blockers,
        capture=dict(actual_bytes=actual_bytes, actual_inodes=actual_inodes,
            future_bytes=future_bytes, future_inodes=future_inodes,
            peak_bytes=peak_bytes if complete else None,
            peak_inodes=peak_inodes if complete else None, total_bytes=total_bytes,
            total_inodes=total_inodes, ceiling_bytes=CAPTURE_BYTES,
            ceiling_inodes=CAPTURE_INODES, record_max_allocated_bytes=RECORD_BYTES,
            record_max_inodes=RECORD_INODES, physical_actual_count=len(actual)),
        devices=bills, peaks={kind: {name: item for name, item in peak.items()
            if name != "objects"} for kind, peak in peaks.items()})


def validate_predecessor_inventory(value):
    """Require every synthetic pre-provision object observation, without lstat.

    Directory IDs are logical fixture slots.  They are deliberately not machine
    locators; an eventual approved collector must bind and observe its actual
    fixed plan, including all slots, rather than a short missing-object list.
    """
    _keys(value, ("schema", "predecessor", "directories", "roots", "ordinary_slice",
        "projects"))
    _require(value["schema"] == INVENTORY_SCHEMA, "INVENTORY_SCHEMA")
    _require(_same(value["predecessor"], c.PREDECESSOR), "PREDECESSOR_IMMUTABLE")
    blockers = []
    for field, wanted in (("directories", {"directory-" + str(i) for i in range(1, 13)}),
        ("roots", set(QUOTA_ROLES))):
        ids = set()
        for item in _rows(value[field]):
            _keys(item, ("object_id", "state"))
            ident = _token(item["object_id"])
            _require(ident not in ids, "DUPLICATE_INVENTORY_OBJECT")
            ids.add(ident)
            _require(item["state"] in ("ABSENT", "PRESENT", "UNKNOWN"), "OBJECT_STATE")
            if item["state"] != "ABSENT":
                blockers.append(field.upper() + "_" + ident + "_" + item["state"])
        _require(ids == wanted, "PREDECESSOR_OBJECT_COVERAGE")
    _keys(value["ordinary_slice"], ("state",))
    _require(value["ordinary_slice"]["state"] in ("ABSENT", "PRESENT", "UNKNOWN"),
        "OBJECT_STATE")
    if value["ordinary_slice"]["state"] != "ABSENT":
        blockers.append("ORDINARY_SLICE_" + value["ordinary_slice"]["state"])
    projects = set()
    for item in _rows(value["projects"]):
        _keys(item, ("project_id", "inventory_state", "usage_state"))
        project = _integer(item["project_id"], 12051, 12057)
        _require(project not in projects, "DUPLICATE_PROJECT")
        projects.add(project)
        _require(item["inventory_state"] in ("ABSENT", "PRESENT", "UNKNOWN")
            and item["usage_state"] in ("UNUSED", "USED", "UNKNOWN"), "PROJECT_STATE")
        if item["inventory_state"] != "ABSENT" or item["usage_state"] != "UNUSED":
            blockers.append("PROJECT_" + str(project) + "_NOT_PROVEN_UNUSED")
    _require(projects == set(range(12051, 12058)), "PROJECT_COVERAGE")
    return dict(schema=INVENTORY_RESULT_SCHEMA,
        status="OFFLINE_PREDECESSOR_COVERAGE_VERIFIED" if not blockers
            else "OFFLINE_PREDECESSOR_COVERAGE_BLOCKED", offline_covered=not blockers,
        directory_count=12, root_count=7, ordinary_slice_count=1, project_count=7,
        field_ready=False, allow_run=False, guest_executed=False,
        lstat_performed=False, live_inventory_qualified=False,
        history_type="PRE_PROVISION_FAILURE", resource_refund=False,
        normal_chain_executions=0, blockers=blockers)
