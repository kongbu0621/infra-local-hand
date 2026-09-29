"""Synthetic parent-growth accounting; no live source, peak or field proof."""
import base64
import copy
import stat
import sys

import pytest

from e3_host import q2_host_window_contract as c
from e3_host import q2_reconciliation_bootstrap as bootstrap
from test_e3_q2_host_window_billing import m as billing
from test_e3_q2_host_window_ordinary_inputs import ordinary_inputs, rebind_precheck_bill
from test_e3_q2_reconciliation_billing import fixture as guest_fixture, m as guest_billing
from test_e3_q2_reconciliation_host_inputs import fixture_inputs


pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"),
    reason="Strict ordinary intent validation uses the Linux record validator")

ALLOCATION_SCHEMA = "local-hand-q2-host-window-parent-allocation/v1"
BILL_SCHEMA = "local-hand-q2-host-window-bill/v2"
JOINT_SCHEMA = "local-hand-q2-host-guest-bill/v2"
PROOF_FLAGS = ("baseline_parent_cost_proven", "full_bill_proven",
    "filesystem_proven", "field_ready")


def context(value):
    raw = base64.b64decode(value["intent_raw"])
    return dict(raw=raw, expected_binding=value["binding"],
        location=value["binding"]["location"], window=c.document(raw)["window"])


def add_observation(value, intent, *, growth=4096):
    inventory = copy.deepcopy(value["bill"]["inventory"])
    location = value["binding"]["location"]
    before = copy.deepcopy(intent["precheck"]["parent_metadata"])
    after = copy.deepcopy(before)
    after["blocks"] += growth // 512
    after["nlink"] += 1
    after["mtime_ns"] += 1
    after["ctime_ns"] += 1
    inventory["parent_allocation"] = dict(schema=ALLOCATION_SCHEMA,
        span="precheck-parent-to-first-marker-budget",
        binding_sha256=c.sha(c.encoded(value["binding"])),
        location_sha256=c.sha(c.encoded(location)), intent_sha256=value["intent_sha256"],
        precheck_sha256=intent["precheck_sha256"], window=copy.deepcopy(intent["window"]),
        parent_path=location["parent"], parent_before=before, parent_after=after,
        marker_snapshot_sha256=c.sha(c.encoded(inventory["scans"][location["directory"]])))
    return inventory


def inventory_inputs(monkeypatch, *, growth=4096, nested_parent=False):
    value, verified, intent = ordinary_inputs(monkeypatch)
    if nested_parent:
        location = copy.deepcopy(value["binding"]["location"])
        previous_directory = location["directory"]
        location["parent"] += "/nested"
        location["directory"] = location["parent"] + "/" + c.DIRECTORY_NAME
        value["binding"]["location"] = copy.deepcopy(location)
        intent["binding"] = copy.deepcopy(value["binding"])
        intent["precheck"]["location_sha256"] = c.sha(c.encoded(location))
        for name in ("precheck_bill", "bill"):
            inventory = value[name]["inventory"]
            inventory["marker"]["path"] = location["directory"]
            next(row for row in inventory["obligations"] if row["kind"] == "marker")["covered_paths"] = [location["directory"]]
        inventory = value["bill"]["inventory"]
        marker = inventory["scans"].pop(previous_directory)
        marker["path"] = location["directory"]
        inventory["scans"][location["directory"]] = marker
        inventory["expected_roots"][location["directory"]] = inventory["expected_roots"].pop(previous_directory)
        rebind_precheck_bill(value, intent)
    return value, verified, intent, add_observation(value, intent, growth=growth)


def inputs(monkeypatch, *, growth=4096):
    value, verified, intent, inventory = inventory_inputs(monkeypatch, growth=growth)
    value["bill"] = billing.quote_host_parent_allocation(inventory, **context(value))
    return value, verified, intent


def validate(value, verified, **overrides):
    args = context(value)
    args.update(precheck_bill=value["precheck_bill"], consumed_bill=value["bill"], plan=verified.plan)
    args.update(overrides)
    return bootstrap.validate_ordinary_host_window_parent_allocation(**args)


def legacy_inventory(inventory):
    result = copy.deepcopy(inventory)
    result.pop("parent_allocation")
    return result


def refresh_snapshot_hash(inventory):
    marker = inventory["scans"][inventory["marker"]["path"]]
    inventory["parent_allocation"]["marker_snapshot_sha256"] = c.sha(c.encoded(marker))


def assert_unproven(value):
    assert value["baseline_parent_cost_status"] == "UNPROVEN"
    for name in PROOF_FLAGS:
        assert value[name] is False


@pytest.mark.parametrize("growth", [0, 512, 4096])
def test_parent_growth_replaces_only_same_marker_future_on_every_accounting_axis(monkeypatch, growth):
    value, verified, _, inventory = inventory_inputs(monkeypatch, growth=growth)
    original = copy.deepcopy(inventory)
    legacy = value["bill"]
    bill = billing.quote_host_parent_allocation(inventory, **context(value))
    assert bill["schema"] == BILL_SCHEMA
    assert inventory == original
    assert bill["inventory"] == inventory
    summary, old = bill["summary"], legacy["summary"]
    marker = summary["marker"]
    assert marker["subtree_actual"] == old["marker"]["actual"]
    assert marker["parent_growth"] == dict(bytes=growth, inodes=0)
    assert marker["actual"] == dict(bytes=old["marker"]["actual"]["bytes"] + growth,
        inodes=old["marker"]["actual"]["inodes"])
    assert marker["commitment"] == dict(bytes=65536, inodes=4)
    assert marker["parent_allocation_sha256"] == c.sha(c.encoded(inventory["parent_allocation"]))
    assert summary["inventory_sha256"] == c.sha(c.encoded(inventory))
    assert summary["total"] == old["total"] == value["precheck_bill"]["summary"]["total"]
    axes = ((summary, old),
        (summary["categories"]["capture"], old["categories"]["capture"]),
        (summary["by_device"]["1"], old["by_device"]["1"]))
    for new_axis, old_axis in axes:
        assert new_axis["actual"]["bytes"] == old_axis["actual"]["bytes"] + growth
        assert new_axis["future"]["bytes"] == old_axis["future"]["bytes"] - growth
        for kind in ("actual", "future"):
            assert new_axis[kind]["inodes"] == old_axis[kind]["inodes"]
    assert summary["categories"]["journal"] == old["categories"]["journal"]
    assert summary["categories"]["capture"]["admitted"] == old["categories"]["capture"]["admitted"]
    for new_proof, old_proof in zip(summary["obligations"], old["obligations"]):
        if new_proof["kind"] != "marker":
            assert new_proof == old_proof
        else:
            assert new_proof["actual"] == marker["actual"]
            assert new_proof["unspent"] == dict(bytes=65536 - marker["actual"]["bytes"],
                inodes=4 - marker["actual"]["inodes"])
    assert_unproven(summary)
    assert summary["joint_admission_proven"] is False
    assert billing.validate_host_bill_parent_allocation(bill, **context(value)) == summary
    value["bill"] = bill
    result = validate(value, verified)
    assert result["status"] == "INPUT_CONSISTENT"
    assert result["host_bill_sha256"] == c.sha(c.encoded(bill))
    assert_unproven(result)
    for name in ("source_admission_proven", "allow_run", "joint_admission_proven", "q2_accepted"):
        assert result[name] is False
    with pytest.raises(ValueError, match="FIELD_READINESS_UNPROVEN"):
        c.require_field_readiness(result)


@pytest.mark.parametrize("fault", ["missing", "extra", "self_reported_growth", "schema", "span",
    "binding", "location", "intent", "precheck", "window", "parent_path", "snapshot",
    "before", "after_uid", "after_gid", "after_inode", "after_device", "after_mode",
    "after_extra", "bool_blocks", "negative_blocks", "overflow_blocks", "duplicate"])
def test_observation_exact_fields_and_cross_bindings_cannot_be_forged_by_requote(monkeypatch, fault):
    value, _, _, inventory = inventory_inputs(monkeypatch)
    observation = inventory["parent_allocation"]
    if fault == "missing": observation.pop("span")
    elif fault == "extra": observation["field_ready"] = True
    elif fault == "self_reported_growth": observation["growth_bytes"] = 4096
    elif fault == "schema": observation["schema"] = "local-hand-q2-host-window-parent-allocation/v2"
    elif fault == "span": observation["span"] = "exclusive-marker-peak"
    elif fault in ("binding", "location", "intent", "precheck"):
        observation[fault + "_sha256"] = "f" * 64
    elif fault == "window":
        observation["window"] = {key: number + 1 for key, number in observation["window"].items()}
    elif fault == "parent_path": observation["parent_path"] = "/another-parent"
    elif fault == "snapshot": observation["marker_snapshot_sha256"] = "f" * 64
    elif fault == "before": observation["parent_before"]["mtime_ns"] += 1
    elif fault.startswith("after_"):
        field = fault.removeprefix("after_")
        if field == "mode": observation["parent_after"]["st_mode"] = stat.S_IFREG | 0o700
        elif field == "extra": observation["parent_after"]["peak_proven"] = True
        else: observation["parent_after"][field] += 1
    elif fault == "bool_blocks": observation["parent_after"]["blocks"] = True
    elif fault == "negative_blocks": observation["parent_after"]["blocks"] = -1
    elif fault == "overflow_blocks": observation["parent_after"]["blocks"] = 2**63
    else: inventory["parent_allocation"] = [observation, copy.deepcopy(observation)]
    with pytest.raises(ValueError):
        billing.quote_host_parent_allocation(inventory, **context(value))


@pytest.mark.parametrize("growth", [-512, 4608])
def test_shrink_and_growth_beyond_original_parent_bound_fail(monkeypatch, growth):
    value, _, _, inventory = inventory_inputs(monkeypatch, growth=growth)
    with pytest.raises(ValueError):
        billing.quote_host_parent_allocation(inventory, **context(value))


@pytest.mark.parametrize("subtree_bytes, allowed", [(61440, True), (61952, False)])
def test_growth_and_marker_share_the_existing_65536_byte_reservation(monkeypatch, subtree_bytes, allowed):
    value, _, _, inventory = inventory_inputs(monkeypatch)
    scan = inventory["scans"][inventory["marker"]["path"]]
    scan["entries"][1]["source_metadata"]["blocks"] = (subtree_bytes - 4096) // 512
    scan["bytes"] = subtree_bytes
    refresh_snapshot_hash(inventory)
    assert billing.validate_host_bill(billing.quote_host(legacy_inventory(inventory)))
    if not allowed:
        with pytest.raises(ValueError):
            billing.quote_host_parent_allocation(inventory, **context(value))
    else:
        bill = billing.quote_host_parent_allocation(inventory, **context(value))
        marker = next(row for row in bill["summary"]["obligations"] if row["kind"] == "marker")
        assert marker["actual"]["bytes"] == 65536
        assert marker["unspent"]["bytes"] == 0


def test_existing_parent_identity_in_history_is_rejected_without_recrediting_it(monkeypatch):
    value, _, intent, inventory = inventory_inputs(monkeypatch)
    previous = inventory["scans"]["/synthetic-host/old-result"]
    previous["entries"][0]["source_metadata"]["inode"] = intent["precheck"]["parent_metadata"]["inode"]
    # The old calculator accepts this ordinary object. The new profile must
    # reject it rather than count its baseline and the delta a second time.
    legacy = billing.quote_host(legacy_inventory(inventory))
    assert billing.validate_host_bill(legacy)
    original = copy.deepcopy(inventory)
    with pytest.raises(ValueError):
        billing.quote_host_parent_allocation(inventory, **context(value))
    assert inventory == original


@pytest.mark.parametrize("kind", ["historical", "capture", "audit", "marker"])
def test_every_obligation_kind_is_forbidden_from_covering_parent_baseline(monkeypatch, kind):
    value, _, _, inventory = inventory_inputs(monkeypatch)
    if kind == "audit":
        row = dict(id="native-audit", kind="audit", category="journal",
            commitment=dict(bytes=4096, inodes=1), covered_paths=["/synthetic-host"],
            devices=[1], evidence_sha256="a" * 64)
        inventory["obligations"].append(row)
        inventory["early_audit"]["host_obligation_ids"] = ["native-audit"]
    else:
        next(row for row in inventory["obligations"] if row["kind"] == kind)["covered_paths"] = ["/synthetic-host"]
    with pytest.raises(ValueError):
        billing.quote_host_parent_allocation(inventory, **context(value))


@pytest.mark.parametrize("fault", ["parent_same_identity", "parent_other_identity", "ancestor_scan", "marker_alias"])
def test_parent_path_ancestor_scan_and_marker_alias_remain_unsupported(monkeypatch, fault):
    value, _, intent, inventory = inventory_inputs(monkeypatch, nested_parent=fault == "ancestor_scan")
    if fault == "marker_alias":
        marker = inventory["scans"][inventory["marker"]["path"]]
        marker["entries"][1]["source_metadata"]["inode"] = intent["precheck"]["parent_metadata"]["inode"]
        refresh_snapshot_hash(inventory)
        assert billing.validate_host_bill(billing.quote_host(legacy_inventory(inventory)))
    else:
        root = "/synthetic-host"
        # The ancestor case has a fully resealed /synthetic-host/nested parent;
        # its observation still binds the exact raw parent before rejection.
        meta = copy.deepcopy(intent["precheck"]["parent_metadata"])
        if fault != "parent_same_identity": meta["inode"] += 9000
        inventory["scans"][root] = dict(path=root, device=meta["device"], bytes=meta["blocks"] * 512,
            inodes=1, logical_bytes=0, entries=[dict(relative_path=".", type="directory", source_metadata=meta)])
        inventory["expected_roots"][root] = "capture"
    with pytest.raises(ValueError):
        billing.quote_host_parent_allocation(inventory, **context(value))


@pytest.mark.parametrize("fault", ["actual", "future", "marker", "obligation", "category", "device",
    "inventory_digest", "observation_digest", "baseline", *PROOF_FLAGS])
def test_recomputed_validation_rejects_changed_summary_or_proof_claim(monkeypatch, fault):
    value, _, _ = inputs(monkeypatch)
    summary = value["bill"]["summary"]
    if fault in ("actual", "future"): summary[fault]["bytes"] += 512
    elif fault == "marker": summary["marker"]["parent_growth"]["inodes"] = 1
    elif fault == "obligation": summary["obligations"][0]["unspent"]["bytes"] -= 4096
    elif fault == "category": summary["categories"]["capture"]["actual"]["bytes"] += 4096
    elif fault == "device": summary["by_device"]["1"]["future"]["bytes"] += 4096
    elif fault == "inventory_digest": summary["inventory_sha256"] = "f" * 64
    elif fault == "observation_digest": summary["marker"]["parent_allocation_sha256"] = "f" * 64
    elif fault == "baseline": summary["baseline_parent_cost_status"] = "EXCLUDED"
    else: summary[fault] = True
    with pytest.raises(ValueError):
        billing.validate_host_bill_parent_allocation(value["bill"], **context(value))


@pytest.mark.parametrize("fault", ["history", "obligation", "audit", "coverage", "device_set"])
def test_transition_rejects_requoted_old_inputs_drift(monkeypatch, fault):
    value, verified, _, inventory = inventory_inputs(monkeypatch)
    if fault == "history": inventory["scans"]["/synthetic-host/old-result"]["entries"][1]["sha256"] = "f" * 64
    elif fault == "obligation": inventory["obligations"][0]["commitment"]["bytes"] += 4096
    elif fault == "audit": inventory["early_audit"]["evidence_sha256"] = "f" * 64
    elif fault == "coverage": inventory["coverage_sha256"] = "f" * 64
    else: inventory["devices"].append(dict(device=2, available_bytes=2**28, free_inodes=10000))
    value["bill"] = billing.quote_host_parent_allocation(inventory, **context(value))
    assert billing.validate_host_bill_parent_allocation(value["bill"], **context(value))
    with pytest.raises(ValueError):
        billing.validate_marker_transition_parent_allocation(value["precheck_bill"], value["bill"], **context(value))
    with pytest.raises(ValueError):
        validate(value, verified)


@pytest.mark.parametrize("machine", ["host_id", "guest_id"])
def test_standalone_quote_cannot_move_machine_identity_from_bound_precheck(monkeypatch, machine):
    value, _, _, inventory = inventory_inputs(monkeypatch)
    inventory[machine] = "f" * 64
    assert billing.validate_host_bill(billing.quote_host(legacy_inventory(inventory)))
    with pytest.raises(ValueError):
        billing.quote_host_parent_allocation(inventory, **context(value))


def test_resealed_machine_replacement_still_cannot_replace_bound_plan_host(monkeypatch):
    value, verified, intent = ordinary_inputs(monkeypatch)
    for name in ("precheck_bill", "bill"):
        value[name]["inventory"]["guest_id"] = "f" * 64
    rebind_precheck_bill(value, intent)
    inventory = add_observation(value, intent)
    value["bill"] = billing.quote_host_parent_allocation(inventory, **context(value))
    assert billing.validate_marker_transition_parent_allocation(value["precheck_bill"], value["bill"], **context(value))
    with pytest.raises(ValueError, match="BILL_MACHINE_BINDING"):
        validate(value, verified)


@pytest.mark.parametrize("fault", ["root_uid", "leaf_gid", "leaf_writable", "leaf_length"])
def test_rehashed_snapshot_and_generic_quote_do_not_replace_actual_marker_identity(monkeypatch, fault):
    value, _, _, inventory = inventory_inputs(monkeypatch)
    marker = inventory["scans"][inventory["marker"]["path"]]
    root, leaf = (entry["source_metadata"] for entry in marker["entries"])
    if fault == "root_uid": root["uid"] += 1
    elif fault == "leaf_gid": leaf["gid"] += 1
    elif fault == "leaf_writable": leaf["st_mode"] = stat.S_IFREG | 0o600
    else:
        leaf["size"] += 1
        marker["logical_bytes"] += 1
    refresh_snapshot_hash(inventory)
    assert billing.validate_host_bill(billing.quote_host(legacy_inventory(inventory)))
    with pytest.raises(ValueError):
        billing.quote_host_parent_allocation(inventory, **context(value))


@pytest.mark.parametrize("fault", ["window", "plan", "plan_shape", "binding", "location", "precheck_bill"])
def test_bootstrap_preserves_expected_plan_window_and_precheck_bill(monkeypatch, fault):
    value, verified, intent = inputs(monkeypatch)
    if fault == "window": override = dict(window={key: number + 1 for key, number in intent["window"].items()})
    elif fault == "plan":
        plan = copy.deepcopy(verified.plan); plan["host"]["hostname"] = "other-guest"
        override = dict(plan=plan)
    elif fault == "plan_shape": override = dict(plan=[])
    elif fault == "binding":
        binding = copy.deepcopy(value["binding"]); binding["wrapper_sha256"] = "f" * 64
        override = dict(expected_binding=binding)
    elif fault == "location":
        location = copy.deepcopy(value["binding"]["location"])
        location["parent"] = "/other-parent"; location["directory"] = location["parent"] + "/" + c.DIRECTORY_NAME
        override = dict(location=location)
    else:
        before = copy.deepcopy(value["precheck_bill"]["inventory"])
        before["devices"][0]["available_bytes"] -= 4096
        override = dict(precheck_bill=billing.quote_host(before))
    with pytest.raises(ValueError):
        validate(value, verified, **override)


def test_joint_keeps_machine_devices_original_ceilings_and_guest_amendment_delta(monkeypatch):
    value, _, _ = inputs(monkeypatch)
    args, _ = guest_fixture(); guest = guest_billing.quote_bill(**args)
    original_guest = copy.deepcopy(guest); original_host = copy.deepcopy(value["bill"])
    joint = billing.joint_quote_parent_allocation(guest, value["bill"], **context(value))
    assert joint["schema"] == JOINT_SCHEMA
    assert guest == original_guest and value["bill"] == original_host
    assert joint["terminated_unspent"] == guest["terminated_unspent"]
    assert joint["before"]["actual"] == joint["proposed_after"]["actual"]
    for key in ("bytes", "inodes"):
        assert joint["before"]["total"][key] - joint["proposed_after"]["total"][key] == guest["terminated_unspent"][key]
    host = value["bill"]["summary"]
    for name in ("before", "proposed_after"):
        selected = joint[name]
        assert selected["categories"]["installation"] == guest[name]["categories"]["installation"]
        assert selected["categories"]["state"] == guest[name]["categories"]["state"]
        assert selected["categories"]["capture"]["ceiling"] == dict(bytes=64 * 1024**2, inodes=4096)
        assert set(selected["by_device"]) == {host["host_id"] + ":1", host["guest_id"] + ":1"}
        assert selected["by_device"][host["host_id"] + ":1"] == host["by_device"]["1"]
        assert selected["by_device"][host["guest_id"] + ":1"] == guest[name]["by_device"][1]
    assert joint["host_bill_sha256"] == c.sha(c.encoded(value["bill"]))
    assert_unproven(joint)
    with pytest.raises(ValueError):
        billing.require_joint_admissible(joint, proposed=True)


def test_changed_consistent_observation_changes_full_bill_and_joint_hashes_without_proving_source(monkeypatch):
    value, _, _ = inputs(monkeypatch)
    args, _ = guest_fixture(); guest = guest_billing.quote_bill(**args)
    original_bill = copy.deepcopy(value["bill"])
    original_joint = billing.joint_quote_parent_allocation(guest, original_bill, **context(value))
    changed = copy.deepcopy(original_bill["inventory"])
    changed["parent_allocation"]["parent_after"]["ctime_ns"] += 1
    value["bill"] = billing.quote_host_parent_allocation(changed, **context(value))
    joint = billing.joint_quote_parent_allocation(guest, value["bill"], **context(value))
    assert value["bill"]["summary"]["total"] == original_bill["summary"]["total"]
    assert joint["host_bill_sha256"] != original_joint["host_bill_sha256"]
    assert c.sha(c.encoded(joint)) != c.sha(c.encoded(original_joint))
    assert_unproven(value["bill"]["summary"])
    assert_unproven(joint)


def test_default_apis_do_not_auto_adopt_parent_allocation_bill(monkeypatch):
    value, verified, intent = inputs(monkeypatch)
    args, _ = guest_fixture(); guest = guest_billing.quote_bill(**args)
    with pytest.raises(ValueError): billing.quote_host(value["bill"]["inventory"])
    with pytest.raises(ValueError): billing.validate_host_bill(value["bill"])
    with pytest.raises(ValueError): billing.validate_marker_transition(value["precheck_bill"], value["bill"])
    with pytest.raises(ValueError): billing.joint_quote(guest, value["bill"])
    with pytest.raises(ValueError): bootstrap.load_host_window(value, verified)
    with pytest.raises(ValueError):
        bootstrap.validate_ordinary_host_window(base64.b64decode(value["intent_raw"]),
            expected_binding=value["binding"], location=value["binding"]["location"], window=intent["window"],
            precheck_bill=value["precheck_bill"], consumed_bill=value["bill"], plan=verified.plan)


def test_explicit_new_apis_reject_legacy_bill_missing_observation_and_root_intent(monkeypatch):
    value, _, _, inventory = inventory_inputs(monkeypatch)
    with pytest.raises(ValueError):
        billing.quote_host_parent_allocation(legacy_inventory(inventory), **context(value))
    with pytest.raises(ValueError):
        billing.validate_host_bill_parent_allocation(value["bill"], **context(value))
    root_value, _ = fixture_inputs(monkeypatch)
    with pytest.raises(ValueError):
        billing.quote_host_parent_allocation(inventory, **context(root_value))


def test_quotes_and_bootstrap_outputs_do_not_alias_input_observations(monkeypatch):
    value, verified, _ = inputs(monkeypatch)
    before = copy.deepcopy(value)
    result = validate(value, verified)
    summary = billing.validate_host_bill_parent_allocation(value["bill"], **context(value))
    summary["marker"]["parent_growth"]["bytes"] = 0
    result["intent"]["precheck"]["parent_metadata"]["blocks"] = 9999
    assert value == before
