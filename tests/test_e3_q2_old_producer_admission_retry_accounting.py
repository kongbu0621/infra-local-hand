"""Accounting faults and complete predecessor coverage use only synthetic data."""
from __future__ import annotations

import copy

import pytest

from e3_host import q2_old_producer_admission_retry_accounting as a
from e3_host import q2_old_producer_admission_retry_contract as c


def observed(name, device, inode, amount=4096):
    return dict(object_id=name, device=device, inode=inode, allocated_bytes=amount,
        inodes=1, reflected_in_free=True)


def phase_object(name, device, inode, amount):
    value = observed(name, device, inode, amount)
    del value["reflected_in_free"]
    return value


def peak(kind, device, parent_inode, coverage):
    snapshots = []
    for phase in a.PHASES[kind]:
        if kind == "record":
            objects = [phase_object("directory", device, 201, 4096)]
            if phase != "create":
                objects.append(phase_object("intent", device, 202, 8192))
        else:
            objects = [phase_object("archive", device, 203,
                128 * 1024 if phase == "partial" else 256 * 1024)]
        metadata = [phase_object("sync-overhead", device, 204,
            4096 if kind == "record" else 64 * 1024)] if phase == "file_sync" else []
        snapshots.append(dict(phase=phase, objects=objects, parent_growth_bytes=4096,
            metadata_sync=metadata))
    return dict(device=device, parent_baseline=dict(device=device, inode=parent_inode,
        allocated_bytes=4096, inodes=1, coverage=coverage),
        qualification="SYNTHETIC_BOUND", snapshots=snapshots)


def accounting():
    commitments = []
    for batch in (a.OLD_BATCH, a.NEW_BATCH):
        for category, (amount, inodes) in a.FULL_BUDGETS.items():
            if batch == a.NEW_BATCH and category == "capture":
                continue
            commitments.append(dict(reservation_id=batch + ":" + category,
                batch=batch, category=category, device=10, allocated_bytes=amount,
                inodes=inodes, status="UNRELEASED"))
    commitments.append(dict(reservation_id="earlier-retained", batch="earlier-failure",
        category="protected-state", device=11, allocated_bytes=1024**2,
        inodes=128, status="UNRELEASED"))
    actual = observed("capture-output", 11, 103, 128 * 1024)
    observations = [observed("consumption-parent", 10, 101),
        observed("evidence-parent", 11, 102), observed("old-code", 10, 104, 1024**2), actual]
    return dict(schema=a.ACCOUNTING_SCHEMA, predecessor=copy.deepcopy(c.PREDECESSOR),
        historical_inventory=dict(status="SYNTHETIC_COMPLETE", expected_reservation_ids=
            [item["reservation_id"] for item in commitments if item["batch"] != a.NEW_BATCH]),
        devices=[dict(device=10, available_bytes=1024**3, available_inodes=100000),
            dict(device=11, available_bytes=1024**3, available_inodes=100000)],
        commitments=commitments, observed_allocations=observations,
        capture=dict(actual=[copy.deepcopy(actual)], future=[dict(reservation_id="capture-unspent",
            device=11, allocated_bytes=1024**2, inodes=32, excludes_peak_subreservations=True)],
            record_peak=peak("record", 10, 101, a.OLD_BATCH + ":code_pool"),
            evidence_peak=peak("evidence", 11, 102, "earlier-retained")))


def inventory():
    return dict(schema=a.INVENTORY_SCHEMA, predecessor=copy.deepcopy(c.PREDECESSOR),
        directories=[dict(object_id="directory-" + str(i), state="ABSENT") for i in range(1, 13)],
        roots=[dict(object_id=role, state="ABSENT") for role in a.QUOTA_ROLES],
        ordinary_slice=dict(state="ABSENT"), projects=[dict(project_id=i,
            inventory_state="ABSENT", usage_state="UNUSED") for i in range(12051, 12058)])


def device_bill(result, device):
    return next(item for item in result["devices"] if item["device"] == device)


def test_exact_full_commitments_and_actual_is_never_a_third_capacity_addend():
    value = accounting()
    original = copy.deepcopy(value)
    result = a.evaluate_accounting(value)
    assert value == original
    assert result["offline_admitted"] is True
    assert result["field_ready"] is result["allow_run"] is result["guest_executed"] is False
    assert result["field_qualification"] == "NOT_ESTABLISHED_BY_SYNTHETIC_DATA"
    bill = device_bill(result, 10)
    assert bill["historical_bytes"] == sum(amount for amount, _ in a.FULL_BUDGETS.values())
    assert bill["historical_inodes"] == sum(inodes for _, inodes in a.FULL_BUDGETS.values())
    assert bill["future_demand_bytes"] == (bill["historical_bytes"]
        + bill["current_commitment_bytes"] + bill["capture_peak_bytes"])
    value["observed_allocations"][2]["allocated_bytes"] = 20 * 1024**2
    larger = a.evaluate_accounting(value)
    assert device_bill(larger, 10)["future_demand_bytes"] == bill["future_demand_bytes"]
    assert device_bill(larger, 10)["observed_free_reflected_bytes"] > bill["observed_free_reflected_bytes"]
    assert larger["resource_refund"] is False


def test_partial_final_and_sync_use_peak_of_sums_not_sum_of_states():
    result = a.evaluate_accounting(accounting())
    assert result["peaks"]["record"]["allocated_bytes"] == 20 * 1024
    assert result["peaks"]["record"]["inodes"] == 3
    assert result["peaks"]["evidence"]["allocated_bytes"] == 324 * 1024
    assert result["peaks"]["evidence"]["inodes"] == 2
    assert result["capture"]["peak_bytes"] == (20 + 324) * 1024
    assert result["capture"]["total_bytes"] == (128 + 1024 + 20 + 324) * 1024
    assert result["capture"]["ceiling_bytes"] == 20 * 1024**2
    assert result["capture"]["ceiling_inodes"] == 384
    assert result["capture"]["record_max_allocated_bytes"] == 64 * 1024
    assert result["capture"]["record_max_inodes"] == 4


def test_uncovered_sync_bytes_can_require_no_new_inode():
    value = accounting()
    value["capture"]["evidence_peak"]["snapshots"][2]["metadata_sync"][0]["inodes"] = 0
    result = a.evaluate_accounting(value)
    assert result["peaks"]["evidence"]["allocated_bytes"] == 324 * 1024
    assert result["peaks"]["evidence"]["inodes"] == 1


def test_actual_physical_aliases_deduplicate_across_capture_and_free_observations():
    value = accounting()
    first = a.evaluate_accounting(value)
    alias = dict(value["capture"]["actual"][0], object_id="capture-alias")
    value["capture"]["actual"].append(alias)
    value["observed_allocations"].append(copy.deepcopy(alias))
    second = a.evaluate_accounting(value)
    assert second["capture"] == first["capture"]
    assert second["devices"] == first["devices"]
    value["capture"]["actual"][-1]["allocated_bytes"] += 4096
    with pytest.raises(ValueError, match="PHYSICAL_ALIAS_CONFLICT"):
        a.evaluate_accounting(value)


def test_capture_actual_changes_ceiling_but_does_not_change_free_addend():
    value = accounting()
    first = a.evaluate_accounting(value)
    value["capture"]["actual"][0]["allocated_bytes"] += 4096
    value["observed_allocations"][-1]["allocated_bytes"] += 4096
    second = a.evaluate_accounting(value)
    assert second["capture"]["total_bytes"] == first["capture"]["total_bytes"] + 4096
    assert device_bill(second, 11)["future_demand_bytes"] == device_bill(first, 11)["future_demand_bytes"]


@pytest.mark.parametrize("field", ["available_bytes", "available_inodes"])
def test_each_device_must_pass_each_free_dimension_independently(field):
    value = accounting()
    good = a.evaluate_accounting(value)
    bill = device_bill(good, 10)
    required_field = "future_demand_bytes" if field == "available_bytes" else "future_demand_inodes"
    value["devices"][0][field] = bill[required_field] - 1
    value["devices"][1][field] = 2**50
    blocked = a.evaluate_accounting(value)
    assert blocked["offline_admitted"] is False
    assert "DEVICE_10_CAPACITY_EXCEEDED" in blocked["blockers"]
    value["devices"][0][field] += 1
    assert a.evaluate_accounting(value)["offline_admitted"] is True


@pytest.mark.parametrize("field,amount", [("allocated_bytes", 20 * 1024**2), ("inodes", 384)])
def test_capture_has_one_global_ceiling_even_across_different_devices(field, amount):
    value = accounting()
    value["capture"]["future"][0][field] = amount
    result = a.evaluate_accounting(value)
    assert "GLOBAL_CAPTURE_CEILING_EXCEEDED" in result["blockers"]
    assert result["offline_admitted"] is False
    assert all(item["offline_within_free"] for item in result["devices"])


@pytest.mark.parametrize("kind", ["record", "evidence"])
@pytest.mark.parametrize("unknown", ["baseline", "coverage", "qualification", "snapshots"])
def test_unknown_parent_baseline_or_peak_is_not_filled_with_zero(kind, unknown):
    value = accounting()
    item = value["capture"][kind + "_peak"]
    if unknown == "baseline":
        item["parent_baseline"]["allocated_bytes"] = None
    elif unknown == "coverage":
        item["parent_baseline"]["coverage"] = "UNKNOWN"
    elif unknown == "qualification":
        item["qualification"] = "UNKNOWN"
    else:
        item["qualification"], item["snapshots"] = "UNKNOWN", None
    result = a.evaluate_accounting(value)
    assert result["offline_admitted"] is False
    assert result["capture"]["peak_bytes"] is result["capture"]["total_bytes"] is None
    assert result["peaks"][kind]["allocated_bytes"] is None
    assert all(item["future_demand_bytes"] is item["capture_peak_bytes"] is None
        for item in result["devices"])
    assert any(kind.upper() in reason for reason in result["blockers"])


def test_record_subreservation_includes_sync_peak_and_does_not_expand_capture():
    value = accounting()
    value["capture"]["record_peak"]["snapshots"][2]["metadata_sync"][0]["allocated_bytes"] = 64 * 1024
    with pytest.raises(ValueError, match="RECORD_SUBRESERVATION_EXCEEDED"):
        a.evaluate_accounting(value)
    value = accounting()
    value["capture"]["future"][0]["excludes_peak_subreservations"] = False
    with pytest.raises(ValueError, match="SUBRESERVATION_DOUBLE_CHARGE"):
        a.evaluate_accounting(value)


def test_record_inode_subreservation_and_exact_global_ceiling_boundary():
    value = accounting()
    metadata = value["capture"]["record_peak"]["snapshots"][2]["metadata_sync"]
    metadata.extend([phase_object("sync-second", 10, 205, 0),
        phase_object("sync-third", 10, 206, 0)])
    with pytest.raises(ValueError, match="RECORD_SUBRESERVATION_EXCEEDED"):
        a.evaluate_accounting(value)
    value = accounting()
    original = a.evaluate_accounting(value)
    future = value["capture"]["future"][0]
    future["allocated_bytes"] = a.CAPTURE_BYTES - original["capture"]["actual_bytes"] \
        - original["capture"]["peak_bytes"]
    future["inodes"] = a.CAPTURE_INODES - original["capture"]["actual_inodes"] \
        - original["capture"]["peak_inodes"]
    result = a.evaluate_accounting(value)
    assert result["offline_admitted"] is True
    assert (result["capture"]["total_bytes"], result["capture"]["total_inodes"]) \
        == (a.CAPTURE_BYTES, a.CAPTURE_INODES)
    future["allocated_bytes"] += 1
    assert "GLOBAL_CAPTURE_CEILING_EXCEEDED" in a.evaluate_accounting(value)["blockers"]


def test_fixed_historical_full_commitments_cannot_be_refunded_or_dropped():
    value = accounting()
    value["commitments"][0]["allocated_bytes"] -= 1024**2
    with pytest.raises(ValueError, match="FULL_COMMITMENT_CHANGED"):
        a.evaluate_accounting(value)
    value = accounting()
    value["commitments"][0]["status"] = "RELEASED"
    with pytest.raises(ValueError, match="RELEASE_OR_REFUND"):
        a.evaluate_accounting(value)
    value = accounting()
    value["commitments"].pop(0)
    with pytest.raises(ValueError, match="FULL_COMMITMENT_MISSING"):
        a.evaluate_accounting(value)


def test_historical_inventory_cannot_drop_prior_obligations_and_unknown_blocks():
    value = accounting()
    value["historical_inventory"]["expected_reservation_ids"].pop()
    with pytest.raises(ValueError, match="HISTORICAL_INVENTORY_COVERAGE"):
        a.evaluate_accounting(value)
    value = accounting()
    value["historical_inventory"]["status"] = "UNKNOWN"
    result = a.evaluate_accounting(value)
    assert result["offline_admitted"] is False
    assert "HISTORICAL_OBLIGATION_INVENTORY_UNKNOWN" in result["blockers"]


def test_new_capture_cannot_also_be_a_full_device_reservation():
    value = accounting()
    value["commitments"].append(dict(reservation_id="duplicate-current-capture", batch=a.NEW_BATCH,
        category="capture", device=10, allocated_bytes=a.CAPTURE_BYTES,
        inodes=a.CAPTURE_INODES, status="UNRELEASED"))
    with pytest.raises(ValueError, match="CURRENT_CAPTURE_DOUBLE_RESERVATION"):
        a.evaluate_accounting(value)


def test_archive_identity_drift_and_double_charge_of_covered_metadata_refuse():
    value = accounting()
    value["capture"]["evidence_peak"]["snapshots"][1]["objects"][0]["inode"] += 1
    with pytest.raises(ValueError, match="PEAK_IDENTITY_DRIFT"):
        a.evaluate_accounting(value)
    value = accounting()
    snapshot = value["capture"]["record_peak"]["snapshots"][2]
    snapshot["metadata_sync"][0]["inode"] = snapshot["objects"][0]["inode"]
    with pytest.raises(ValueError, match="PEAK_PHYSICAL_OVERLAP"):
        a.evaluate_accounting(value)


def test_record_evidence_allocations_must_not_overlap_physically():
    value = accounting()
    evidence = value["capture"]["evidence_peak"]
    evidence["device"] = evidence["parent_baseline"]["device"] = 10
    evidence["parent_baseline"]["coverage"] = a.OLD_BATCH + ":code_pool"
    value["observed_allocations"][1]["device"] = 10
    for snapshot in evidence["snapshots"]:
        for item in snapshot["objects"] + snapshot["metadata_sync"]:
            item["device"] = 10
        snapshot["objects"][0]["inode"] = 202
    with pytest.raises(ValueError, match="PEAK_PHYSICAL_OVERLAP"):
        a.evaluate_accounting(value)


@pytest.mark.parametrize("kind,object_id", [("record", "intent"), ("evidence", "archive")])
def test_new_record_and_archive_cannot_alias_retained_non_capture_allocations(kind, object_id):
    value = accounting()
    old_code = value["observed_allocations"][2]
    assert old_code["object_id"] == "old-code"
    assert all((item["device"], item["inode"]) != (old_code["device"], old_code["inode"])
        for item in value["capture"]["actual"])
    retained = dict(old_code, object_id="retained-on-peak-device",
        device=value["capture"][kind + "_peak"]["device"])
    value["observed_allocations"].append(retained)
    for snapshot in value["capture"][kind + "_peak"]["snapshots"]:
        for item in snapshot["objects"]:
            if item["object_id"] == object_id:
                item["inode"] = retained["inode"]
    with pytest.raises(ValueError, match="PEAK_PHYSICAL_OVERLAP"):
        a.evaluate_accounting(value)


def test_shared_parent_growth_without_joint_peak_is_explicitly_unknown():
    value = accounting()
    evidence = value["capture"]["evidence_peak"]
    evidence["device"] = 10
    evidence["parent_baseline"] = copy.deepcopy(value["capture"]["record_peak"]["parent_baseline"])
    for snapshot in evidence["snapshots"]:
        for item in snapshot["objects"] + snapshot["metadata_sync"]:
            item["device"] = 10
            item["inode"] += 100
    result = a.evaluate_accounting(value)
    assert "SHARED_PARENT_JOINT_PEAK_UNKNOWN" in result["blockers"]
    assert result["capture"]["total_bytes"] is None


@pytest.mark.parametrize("bad", [True, False, -1, 1.0, "1", 2**63])
@pytest.mark.parametrize("location", ["free", "commitment", "observed", "baseline", "phase"])
def test_numeric_schema_rejects_bool_coercion_negative_float_and_overflow(bad, location):
    value = accounting()
    if location == "free":
        value["devices"][0]["available_bytes"] = bad
    elif location == "commitment":
        value["commitments"][0]["allocated_bytes"] = bad
    elif location == "observed":
        value["observed_allocations"][0]["allocated_bytes"] = bad
    elif location == "baseline":
        value["capture"]["record_peak"]["parent_baseline"]["allocated_bytes"] = bad
    else:
        value["capture"]["record_peak"]["snapshots"][0]["objects"][0]["allocated_bytes"] = bad
    with pytest.raises(ValueError, match="INTEGER"):
        a.evaluate_accounting(value)


@pytest.mark.parametrize("field", ["devices", "commitments", "observed_allocations"])
def test_duplicate_input_rows_refuse(field):
    value = accounting()
    value[field].append(copy.deepcopy(value[field][0]))
    with pytest.raises(ValueError, match="DUPLICATE"):
        a.evaluate_accounting(value)


def test_missing_device_uncovered_parent_and_invalid_actual_claim_refuse():
    value = accounting()
    value["devices"].pop()
    with pytest.raises(ValueError, match="DEVICE_MISSING"):
        a.evaluate_accounting(value)
    value = accounting()
    value["capture"]["record_peak"]["parent_baseline"]["coverage"] = "self-reported-new-category"
    with pytest.raises(ValueError, match="PARENT_BASELINE_COVERAGE"):
        a.evaluate_accounting(value)
    value = accounting()
    value["observed_allocations"][0]["reflected_in_free"] = 1
    with pytest.raises(ValueError, match="ACTUAL_NOT_FREE_REFLECTED"):
        a.evaluate_accounting(value)


def test_sum_overflow_and_extra_fields_are_rejected():
    value = accounting()
    value["commitments"][-1]["allocated_bytes"] = 2**63 - 1
    with pytest.raises(ValueError, match="INTEGER"):
        a.evaluate_accounting(value)
    value = accounting()
    value["capture"]["record_peak"]["parent_baseline"]["caller_override"] = True
    with pytest.raises(ValueError, match="FIELDS"):
        a.evaluate_accounting(value)


def test_complete_12_directories_7_roots_slice_and_unused_project_coverage():
    value = inventory()
    original = copy.deepcopy(value)
    result = a.validate_predecessor_inventory(value)
    assert value == original
    assert result["offline_covered"] is True
    assert (result["directory_count"], result["root_count"], result["ordinary_slice_count"],
        result["project_count"]) == (12, 7, 1, 7)
    assert result["history_type"] == "PRE_PROVISION_FAILURE"
    assert result["lstat_performed"] is result["live_inventory_qualified"] is result["field_ready"] is False
    assert result["resource_refund"] is False


@pytest.mark.parametrize("field", ["directories", "roots", "projects"])
def test_short_missing_list_and_duplicate_predecessor_observations_refuse(field):
    value = inventory()
    value[field].pop()
    with pytest.raises(ValueError, match="COVERAGE"):
        a.validate_predecessor_inventory(value)
    value = inventory()
    value[field].append(copy.deepcopy(value[field][0]))
    with pytest.raises(ValueError, match="DUPLICATE"):
        a.validate_predecessor_inventory(value)


@pytest.mark.parametrize("field", ["directories", "roots", "ordinary_slice", "projects"])
@pytest.mark.parametrize("state", ["PRESENT", "UNKNOWN"])
def test_existing_or_unknown_predecessor_objects_block_without_cleanup(field, state):
    value = inventory()
    if field == "ordinary_slice":
        value[field]["state"] = state
    elif field == "projects":
        value[field][0]["inventory_state"] = state
    else:
        value[field][0]["state"] = state
    result = a.validate_predecessor_inventory(value)
    assert result["offline_covered"] is False
    assert result["field_ready"] is result["allow_run"] is False
    assert result["blockers"]


def test_inventory_absence_is_not_project_unused_proof():
    value = inventory()
    value["projects"][0]["usage_state"] = "USED"
    assert a.validate_predecessor_inventory(value)["offline_covered"] is False
    value["projects"][0]["usage_state"] = "UNKNOWN"
    assert a.validate_predecessor_inventory(value)["offline_covered"] is False
    value["projects"][0]["project_id"] = True
    with pytest.raises(ValueError, match="INTEGER"):
        a.validate_predecessor_inventory(value)


@pytest.mark.parametrize("api,factory", [(a.evaluate_accounting, accounting),
    (a.validate_predecessor_inventory, inventory)])
def test_pre_provision_failure_is_immutable_and_cannot_become_prior_normal(api, factory):
    value = factory()
    value["predecessor"]["history_type"] = "PRIOR_NORMAL"
    with pytest.raises(ValueError, match="PREDECESSOR_IMMUTABLE"):
        api(value)
    value = factory()
    value["predecessor"]["normal_chain_executions"] = False
    with pytest.raises(ValueError, match="PREDECESSOR_IMMUTABLE"):
        api(value)
