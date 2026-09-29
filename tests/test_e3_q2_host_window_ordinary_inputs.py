"""Synthetic v2 cross-object consistency; no actual host or writer admission."""
import base64
import copy
import stat
import sys

import pytest

from e3_host import q2_host_window_contract as c
from e3_host import q2_reconciliation_bootstrap as m
from test_e3_q2_host_window_billing import m as billing
from test_e3_q2_reconciliation_host_inputs import fixture_inputs, reseal_marker_input


# Strict intent validation loads the Linux record implementation (fcntl).
# These are input-model tests, not an ordinary-user filesystem positive.
pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"),
    reason="Strict ordinary host intent uses the Linux record validator")


def ordinary_inputs(monkeypatch, *, uid=1201, gid=1301, groups=None):
    value, verified = fixture_inputs(monkeypatch)
    intent = c.document(base64.b64decode(value["intent_raw"]))
    operator = dict(schema=c.OPERATOR_SCHEMA, uid=[uid] * 3, gid=[gid] * 3,
        groups=[gid, gid, 1401] if groups is None else groups)
    intent.update(schema=c.ORDINARY_INTENT_SCHEMA, operator=copy.deepcopy(operator))
    intent["precheck"].update(schema="local-hand-q2-host-window-precheck/v2",
        operator=copy.deepcopy(operator))
    intent["precheck"]["parent_metadata"].update(uid=uid, gid=gid)
    intent["directory_identity"].update(uid=uid, gid=gid)
    marker = value["bill"]["inventory"]["scans"][value["binding"]["location"]["directory"]]
    for row in marker["entries"]:
        row["source_metadata"].update(uid=uid, gid=gid)
    reseal(value, intent)
    return value, verified, intent


def reseal(value, intent):
    intent["precheck_sha256"] = c.sha(c.encoded(intent["precheck"]))
    return reseal_marker_input(value, intent)


def validate(value, verified, **overrides):
    raw = base64.b64decode(value["intent_raw"])
    args = dict(expected_binding=value["binding"], location=value["binding"]["location"],
        window=c.document(raw)["window"], precheck_bill=value["precheck_bill"],
        consumed_bill=value["bill"], plan=verified.plan)
    args.update(overrides)
    return m.validate_ordinary_host_window(raw, **args)


def rebind_precheck_bill(value, intent):
    value["precheck_bill"] = billing.quote_host(value["precheck_bill"]["inventory"])
    intent["precheck"]["host_bill_sha256"] = c.sha(c.encoded(value["precheck_bill"]))
    intent["precheck"]["host_bill_summary"] = copy.deepcopy(value["precheck_bill"]["summary"])
    return reseal(value, intent)


def test_ordinary_inputs_bind_exact_plan_window_bills_and_historical_issuer(monkeypatch):
    value, verified, intent = ordinary_inputs(monkeypatch)
    before = copy.deepcopy(value)
    result = validate(value, verified)
    assert result["status"] == "INPUT_CONSISTENT"
    assert result["intent"] == intent
    assert result["intent"]["operator"]["groups"] == [1301, 1301, 1401]
    assert result["intent_sha256"] == value["intent_sha256"]
    assert result["precheck_bill_sha256"] == c.sha(c.encoded(value["precheck_bill"]))
    assert result["host_bill_sha256"] == c.sha(c.encoded(value["bill"]))
    assert result["plan_sha256"] == c.sha(c.encoded(verified.plan))
    assert result["transition"]["guest_id"] == c.sha(c.encoded(verified.plan["host"]))
    for name in ("source_admission_proven", "field_ready", "allow_run",
                 "joint_admission_proven", "q2_accepted"):
        assert result[name] is False
    assert value == before
    result["intent"]["operator"]["uid"][0] = 9999
    assert value == before
    with pytest.raises(ValueError, match="HOST_WINDOW_FIELD_READINESS_UNPROVEN"):
        c.require_field_readiness(result)


def test_another_consistent_issuer_is_not_a_new_permanent_uid_pin(monkeypatch):
    value, verified, _ = ordinary_inputs(monkeypatch, uid=2201, gid=2301, groups=[])
    assert validate(value, verified)["intent"]["operator"]["uid"] == [2201] * 3
    # This only confirms modeled records; it does not establish who issued one.


def test_old_load_and_marker_apis_reject_v2_even_with_root_metadata(monkeypatch):
    value, verified, intent = ordinary_inputs(monkeypatch)
    raw = base64.b64decode(value["intent_raw"])
    with pytest.raises(ValueError):
        m.load_host_window(value, verified)
    with pytest.raises(ValueError, match="MARKER_SCHEMA"):
        m.validate_marker_scan(value["bill"], intent, raw, value["binding"]["location"])
    for row in value["bill"]["inventory"]["scans"][value["binding"]["location"]["directory"]]["entries"]:
        row["source_metadata"].update(uid=0, gid=0)
    intent["directory_identity"].update(uid=0, gid=0)
    raw = reseal(value, intent)
    with pytest.raises(ValueError, match="MARKER_SCHEMA"):
        m.validate_marker_scan(value["bill"], intent, raw, value["binding"]["location"])


def test_explicit_ordinary_api_rejects_legacy_root_record(monkeypatch):
    value, verified = fixture_inputs(monkeypatch)
    assert m.load_host_window(value, verified)["intent"]["schema"] == c.INTENT_SCHEMA
    with pytest.raises(ValueError):
        validate(value, verified)


@pytest.mark.parametrize("fault", ["window", "plan", "plan_shape", "binding", "location"])
def test_expected_external_bindings_cannot_follow_rehashed_input(monkeypatch, fault):
    value, verified, intent = ordinary_inputs(monkeypatch)
    if fault == "window":
        window = {key: amount + 1 for key, amount in intent["window"].items()}
        override = dict(window=window)
    elif fault == "plan":
        plan = copy.deepcopy(verified.plan); plan["host"]["hostname"] = "different-guest"
        override = dict(plan=plan)
    elif fault == "plan_shape":
        override = dict(plan=[])
    elif fault == "binding":
        binding = copy.deepcopy(value["binding"]); binding["wrapper_sha256"] = "f" * 64
        override = dict(expected_binding=binding)
    else:
        location = copy.deepcopy(value["binding"]["location"])
        location["parent"] = "/another-parent"
        location["directory"] = location["parent"] + "/" + c.DIRECTORY_NAME
        override = dict(location=location)
    with pytest.raises(ValueError):
        validate(value, verified, **override)


@pytest.mark.parametrize("fault", ["issuer", "parent_uid", "parent_gid", "directory_gid",
    "precheck_v1", "intent_v1", "unknown_intent", "unknown_precheck", "unknown_operator"])
def test_fully_resealed_cross_schema_and_identity_conflicts_fail(monkeypatch, fault):
    value, verified, intent = ordinary_inputs(monkeypatch)
    if fault == "issuer": intent["operator"]["groups"].append(1501)
    elif fault == "parent_uid": intent["precheck"]["parent_metadata"]["uid"] += 1
    elif fault == "parent_gid": intent["precheck"]["parent_metadata"]["gid"] += 1
    elif fault == "directory_gid": intent["directory_identity"]["gid"] += 1
    elif fault == "precheck_v1": intent["precheck"]["schema"] = "local-hand-q2-host-window-precheck/v1"
    elif fault == "intent_v1": intent["schema"] = c.INTENT_SCHEMA
    elif fault == "unknown_intent": intent["allow_run"] = True
    elif fault == "unknown_precheck": intent["precheck"]["filesystem_ready"] = True
    else: intent["operator"]["fsuid"] = intent["operator"]["uid"][1]
    raw = reseal(value, intent)
    with pytest.raises(ValueError):
        m.validate_marker_scan_ordinary(value["bill"], raw, value["binding"], value["binding"]["location"])
    with pytest.raises(ValueError):
        validate(value, verified)


@pytest.mark.parametrize("fault", ["root_uid", "root_gid", "root_nlink", "leaf_uid", "leaf_gid",
    "leaf_writable", "leaf_group_readable", "leaf_setgid", "leaf_parent_inode", "content_sha"])
def test_requoted_generic_bill_cannot_substitute_actual_writer_metadata(monkeypatch, fault):
    value, verified, intent = ordinary_inputs(monkeypatch)
    marker = value["bill"]["inventory"]["scans"][value["binding"]["location"]["directory"]]
    root, leaf = (row["source_metadata"] for row in marker["entries"])
    if fault == "root_uid": root["uid"] += 1
    elif fault == "root_gid": root["gid"] += 1
    elif fault == "root_nlink": root["nlink"] = 3
    elif fault == "leaf_uid": leaf["uid"] += 1
    elif fault == "leaf_gid": leaf["gid"] += 1
    elif fault == "leaf_writable": leaf["st_mode"] = stat.S_IFREG | 0o600
    elif fault == "leaf_group_readable": leaf["st_mode"] = stat.S_IFREG | 0o440
    elif fault == "leaf_setgid": leaf["st_mode"] = stat.S_IFREG | 0o2400
    elif fault == "leaf_parent_inode": leaf["inode"] = intent["precheck"]["parent_metadata"]["inode"]
    else: marker["entries"][1]["sha256"] = "f" * 64
    value["bill"] = billing.quote_host(value["bill"]["inventory"])
    assert billing.validate_host_bill(value["bill"])
    raw = base64.b64decode(value["intent_raw"])
    assert c.verify_intent_ordinary(raw, value["binding"], value["binding"]["location"]) == intent
    with pytest.raises(ValueError):
        m.validate_marker_scan_ordinary(value["bill"], raw, value["binding"], value["binding"]["location"])
    with pytest.raises(ValueError):
        validate(value, verified)


@pytest.mark.parametrize("fault", ["precheck_digest", "precheck_summary", "history", "obligation",
    "audit", "coverage", "device_set", "guest_machine"])
def test_recomputed_quotes_keep_original_history_obligations_and_machines(monkeypatch, fault):
    value, verified, intent = ordinary_inputs(monkeypatch)
    before = value["precheck_bill"]["inventory"]
    after = value["bill"]["inventory"]
    if fault == "precheck_digest":
        before["devices"][0]["available_bytes"] -= 4096
        value["precheck_bill"] = billing.quote_host(before)
    elif fault == "precheck_summary":
        intent["precheck"]["host_bill_summary"]["coverage_sha256"] = "f" * 64
        reseal(value, intent)
    elif fault == "history":
        after["scans"]["/synthetic-host/old-result"]["entries"][1]["sha256"] = "f" * 64
    elif fault == "obligation": after["obligations"][0]["commitment"]["bytes"] += 4096
    elif fault == "audit": after["early_audit"]["evidence_sha256"] = "f" * 64
    elif fault == "coverage": after["coverage_sha256"] = "f" * 64
    elif fault == "device_set":
        after["devices"].append(dict(device=2, available_bytes=128 * 1024**2, free_inodes=10000))
    else:
        before["guest_id"] = after["guest_id"] = "f" * 64
        rebind_precheck_bill(value, intent)
    value["bill"] = billing.quote_host(value["bill"]["inventory"])
    assert billing.validate_host_bill(value["precheck_bill"])
    assert billing.validate_host_bill(value["bill"])
    with pytest.raises(ValueError):
        validate(value, verified)


def test_raw_length_and_digest_are_both_checked_after_valid_requote(monkeypatch):
    value, verified, intent = ordinary_inputs(monkeypatch)
    marker = value["bill"]["inventory"]["scans"][value["binding"]["location"]["directory"]]
    marker["entries"][1]["source_metadata"]["size"] += 1
    marker["logical_bytes"] += 1
    value["bill"] = billing.quote_host(value["bill"]["inventory"])
    assert billing.validate_host_bill(value["bill"])
    with pytest.raises(ValueError, match="MARKER_CONTENT"):
        validate(value, verified)


def test_no_uid_override_or_unknown_combination_argument(monkeypatch):
    value, verified, _ = ordinary_inputs(monkeypatch)
    for extra in (dict(uid=1201), dict(allowed_uids=[0, 1201]), dict(profile="ordinary"),
                  dict(expected_guest_id="f" * 64), dict(allow_run=True)):
        with pytest.raises(TypeError):
            validate(value, verified, **extra)
