"""Input consistency only: no fixture supplies actual field readiness."""
import base64
import copy
import stat
from types import SimpleNamespace

import pytest

from e3_host import q2_reconciliation_bootstrap as m
from e3_host import q2_host_window_contract as c
from e3_host import q2_host_window_record as record
from test_e3_q2_host_window_billing import fixture, consume, scan, m as billing


def fixture_inputs(monkeypatch):
    location = dict(schema=c.SOURCES_SCHEMA, parent="/synthetic-host",
        directory="/synthetic-host/" + c.DIRECTORY_NAME,
        expected_boot_id="12345678-1234-1234-1234-123456789abc",
        startup_closure=c.STARTUP_AUTHORITY["closure"], carrier_sha256=c.CARRIER_SHA256,
        carrier_bytes=c.CARRIER_BYTES, host_attestation_sha256=c.ATTESTATION_SHA256,
        host_attestation_bytes=c.ATTESTATION_BYTES)
    plan = dict(host=dict(hostname="synthetic-guest", boot_id="22345678-1234-1234-1234-123456789abc",
        initial_userns=dict(device=3, inode=4)), candidate=dict(source="/guest/stage/source",
        commit=c.prior.old.CANDIDATE_COMMIT, wheel_sha256=c.prior.old.CANDIDATE_WHEEL_SHA256))
    verified = SimpleNamespace(implementation_commit="a"*40, digest="b"*64, plan=plan,
        execution=dict(attempt_id="synthetic-once", source=dict(tree="d"*40, files={"/guest/tool.py":"e"*64})))
    configuration = dict(attempt_id="synthetic-once", source_commit="a"*40, source_tree="d"*40,
        amendment_sha256="b"*64, inputs_sha256="b"*64, guest_stage="/guest/stage",
        guest_pin=plan["host"], candidate=plan["candidate"]["commit"],
        wheel_sha256=plan["candidate"]["wheel_sha256"])
    wrapper = b"synthetic wrapper bytes; never executed\n"
    binding = c.make_binding(implementation_commit="a"*40, source_tree="d"*40,
        source_files_sha256=c.sha(c.encoded(verified.execution["source"]["files"])),
        attempt_id="synthetic-once", plan_sha256=c.sha(c.encoded(plan)), amendment_sha256="b"*64,
        configuration_sha256=c.sha(c.encoded(configuration)), wrapper_sha256=c.sha(wrapper), location=location)
    inventory = fixture()
    inventory.update(host_id=c.ATTESTATION_SHA256, guest_id=c.sha(c.encoded(plan["host"])))
    precheck_bill = billing.quote_host(inventory)
    window = dict(issued_ns=100, deadline_ns=100+300*c.NS,
        boottime_issued_ns=200, boottime_deadline_ns=200+300*c.NS)
    meta = copy.deepcopy(scan("/synthetic-host", 10)["entries"][0]["source_metadata"])
    meta.update(uid=0, gid=0, size=4096, blocks=8)
    fs = dict(schema=record.FILESYSTEM_SCHEMA, device=1, mount_id=4, mountpoint="/",
        source="/dev/synthetic", mountinfo_sha256="1"*64, superblock_sha256="2"*64,
        block_size=4096, cluster_size=4096, parent_flags=record.FS_EXTENTS_FL,
        parent_size=4096, available_bytes=128*1024**2, free_inodes=10000,
        allocation_bound=65536, logical_bound=16384, inode_bound=4)
    precheck = dict(schema=record.PRECHECK_SCHEMA, location_sha256=c.sha(c.encoded(location)),
        window=window, boot_id=location["expected_boot_id"], parent_metadata=meta, filesystem=fs,
        host_bill_sha256=c.sha(c.encoded(precheck_bill)), host_bill_summary=precheck_bill["summary"],
        limits=dict(c.RESERVATION))
    intent = dict(schema=c.INTENT_SCHEMA, scope=c.SCOPE, binding=binding, window=window,
        directory_identity=dict(device=1, inode=200, uid=0, gid=0, mode=0o700),
        precheck=precheck, precheck_sha256=c.sha(c.encoded(precheck)), reservation=dict(c.RESERVATION),
        window_consumed=True, owner_issued=False, run_permission="existing_startup_once")
    raw = c.encoded(intent)
    after = consume(inventory)
    marker = scan(location["directory"], 200, logical=len(raw),
        allocated=4096 + ((len(raw)+4095)//4096)*4096, filename=c.INTENT_NAME)
    marker["entries"][0]["source_metadata"].update(uid=0, gid=0, nlink=2)
    marker["entries"][1]["source_metadata"].update(uid=0, gid=0, st_mode=stat.S_IFREG | 0o400)
    marker["entries"][1]["sha256"] = c.sha(raw)
    after["scans"][location["directory"]] = marker
    value = dict(binding=binding, carrier_raw=base64.b64encode(b"synthetic carrier").decode(),
        host_attestation_raw=base64.b64encode(b"synthetic attestation").decode(),
        configuration=configuration, wrapper_raw=base64.b64encode(wrapper).decode(),
        intent_raw=base64.b64encode(raw).decode(), intent_sha256=c.sha(raw),
        precheck_bill=precheck_bill, bill=billing.quote_host(after))
    # These two independently tested parsers require private originals/full host
    # configuration. Substitute only their output to test the cross-bindings.
    monkeypatch.setattr(c, "sources", lambda *args:copy.deepcopy(location))
    original = m.helper
    monkeypatch.setattr(m, "helper", lambda name: c if name == "q2_host_window_contract" else
        SimpleNamespace(validate_config=lambda value:value) if name == "q2_reconciliation_entry" else original(name))
    return value, verified


def test_host_input_proof_keeps_old_reconciliation_and_actual_field_gate_separate(monkeypatch):
    value, verified = fixture_inputs(monkeypatch)
    result = m.load_host_window(value, verified)
    combined = m.VerifiedInputs(verified, result)
    assert combined.reconciliation is verified
    assert combined.plan is verified.plan
    assert copy.deepcopy(combined).plan == verified.plan
    assert result["intent_sha256"] == c.sha(result["intent_raw"])
    assert result["intent"]["directory_identity"]["uid"] == 0
    assert result["intent"]["directory_identity"]["gid"] == 0
    with pytest.raises(ValueError, match="HOST_WINDOW_FIELD_READINESS_UNPROVEN"):
        c.require_field_readiness(result)


@pytest.mark.parametrize("fault", ["configuration", "wrapper", "source_map", "marker_bytes",
    "marker_identity", "precheck_digest", "machine_identity", "unknown_field"])
def test_host_input_cross_bindings_reject_self_consistent_but_different_material(monkeypatch, fault):
    value, verified = fixture_inputs(monkeypatch)
    if fault == "configuration": value["configuration"]["guest_stage"] = "/guest/other"
    elif fault == "wrapper": value["wrapper_raw"] = base64.b64encode(b"different wrapper").decode()
    elif fault == "source_map": verified.execution["source"]["files"]["/guest/tool.py"] = "f"*64
    elif fault in ("marker_bytes", "marker_identity"):
        inventory = value["bill"]["inventory"]
        marker = inventory["scans"][inventory["marker"]["path"]]
        if fault == "marker_bytes": marker["entries"][1]["sha256"] = "f"*64
        else: marker["entries"][0]["source_metadata"]["inode"] += 10
        value["bill"] = billing.quote_host(inventory)
    elif fault == "precheck_digest": value["precheck_bill"]["summary"]["inventory_sha256"] = "f"*64
    elif fault == "machine_identity":
        for name in ("precheck_bill", "bill"):
            inventory = value[name]["inventory"]; inventory["host_id"] = "f"*64
            value[name] = billing.quote_host(inventory)
    else: value["pretend_ready"] = True
    with pytest.raises(ValueError): m.load_host_window(value, verified)


def reseal_marker_input(value, intent):
    """Recompute bytes, file accounting and the bill, as a hostile sender can.

    This supplies internally consistent synthetic inputs, never a live marker
    or an independently qualified source. Cross-object checks must still run.
    """
    raw = c.encoded(intent)
    value["intent_raw"] = base64.b64encode(raw).decode()
    value["intent_sha256"] = c.sha(raw)
    inventory = value["bill"]["inventory"]
    marker = inventory["scans"][inventory["marker"]["path"]]
    leaf = marker["entries"][1]
    leaf["sha256"] = c.sha(raw)
    leaf["source_metadata"]["size"] = len(raw)
    leaf["source_metadata"]["blocks"] = (len(raw) + 4095) // 4096 * 8
    marker["logical_bytes"] = len(raw)
    marker["bytes"] = sum(row["source_metadata"]["blocks"] * 512 for row in marker["entries"])
    value["bill"] = billing.quote_host(inventory)
    # A stale checksum or invalid generic quote must not explain rejection.
    assert billing.validate_host_bill(value["bill"])
    assert c.sha(base64.b64decode(value["intent_raw"])) == value["intent_sha256"]
    return raw


@pytest.mark.parametrize("fault", ["uid", "gid", "device", "parent_inode"])
def test_intent_rejects_writer_identity_conflicts_even_after_all_rehashing(monkeypatch, fault):
    value, verified = fixture_inputs(monkeypatch)
    intent = c.document(base64.b64decode(value["intent_raw"]))
    identity = intent["directory_identity"]
    inventory = value["bill"]["inventory"]
    marker = inventory["scans"][inventory["marker"]["path"]]
    root = marker["entries"][0]["source_metadata"]
    if fault in ("uid", "gid"):
        identity[fault] = root[fault] = 1000
    elif fault == "parent_inode":
        identity["inode"] = root["inode"] = intent["precheck"]["parent_metadata"]["inode"]
    else:
        # Keep the after-bill internally consistent on another device while
        # retaining the original precheck's parent device in the intent.
        identity["device"] = 2
        marker["device"] = inventory["marker"]["device"] = 2
        for row in marker["entries"]:
            row["source_metadata"]["device"] = 2
        inventory["devices"].append(dict(device=2, available_bytes=128*1024**2, free_inodes=10000))
        next(row for row in inventory["obligations"] if row["kind"] == "marker")["devices"] = [2]
    raw = reseal_marker_input(value, intent)
    # The pure intent boundary must itself reject; later billing transition
    # checks or the unconditional field-readiness gate cannot mask this test.
    with pytest.raises(ValueError):
        c.verify_intent(raw, value["binding"], value["binding"]["location"])
    with pytest.raises(ValueError):
        m.load_host_window(value, verified)


@pytest.mark.parametrize("fault", ["root_nlink", "leaf_uid", "leaf_gid", "leaf_writable",
    "leaf_group_readable", "leaf_setgid", "leaf_parent_inode"])
def test_marker_profile_rejects_valid_requoted_but_nonwriter_metadata(monkeypatch, fault):
    value, verified = fixture_inputs(monkeypatch)
    intent = c.document(base64.b64decode(value["intent_raw"]))
    inventory = value["bill"]["inventory"]
    marker = inventory["scans"][inventory["marker"]["path"]]
    root, leaf = (row["source_metadata"] for row in marker["entries"])
    if fault == "root_nlink": root["nlink"] = 3
    elif fault == "leaf_uid": leaf["uid"] = 1000
    elif fault == "leaf_gid": leaf["gid"] = 1000
    elif fault == "leaf_writable": leaf["st_mode"] = stat.S_IFREG | 0o600
    elif fault == "leaf_group_readable": leaf["st_mode"] = stat.S_IFREG | 0o440
    elif fault == "leaf_setgid": leaf["st_mode"] = stat.S_IFREG | 0o2400
    else: leaf["inode"] = intent["precheck"]["parent_metadata"]["inode"]
    raw = reseal_marker_input(value, intent)
    assert c.verify_intent(raw, value["binding"], value["binding"]["location"]) == intent
    with pytest.raises(ValueError):
        m.validate_marker_scan(value["bill"], intent, raw, value["binding"]["location"])
    with pytest.raises(ValueError):
        m.load_host_window(value, verified)


@pytest.mark.parametrize("fault", ["root_type", "root_mode", "leaf_type", "leaf_nlink",
    "leaf_device", "root_leaf_alias"])
def test_marker_scan_boundary_independently_rejects_invalid_physical_shape(monkeypatch, fault):
    value, _ = fixture_inputs(monkeypatch)
    raw = base64.b64decode(value["intent_raw"])
    intent = c.document(raw)
    marker = value["bill"]["inventory"]["scans"][value["binding"]["location"]["directory"]]
    root_row, leaf_row = marker["entries"]
    root, leaf = root_row["source_metadata"], leaf_row["source_metadata"]
    if fault == "root_type":
        root_row["type"] = "file"; root["st_mode"] = stat.S_IFREG | 0o700
    elif fault == "root_mode": root["st_mode"] = stat.S_IFDIR | 0o2700
    elif fault == "leaf_type":
        leaf_row["type"] = "directory"; leaf["st_mode"] = stat.S_IFDIR | 0o400
    elif fault == "leaf_nlink": leaf["nlink"] = 2
    elif fault == "leaf_device": leaf["device"] += 1
    else: leaf["inode"] = root["inode"]
    # Generic billing already rejects several of these shapes. Exercise this
    # standalone boundary directly so that it cannot depend on call order.
    with pytest.raises(ValueError):
        m.validate_marker_scan(value["bill"], intent, raw, value["binding"]["location"])
