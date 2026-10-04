import copy
import hashlib
import io
import json
import warnings
import zipfile

import pytest

from e3_host import q2_core_obligation_inputs as o


def test_delta_is_exact_approved_transform_and_not_legacy_rows():
    rows = o.delta_rows()
    assert len(rows) == 12
    assert (o._total(rows, "bytes"), o._total(rows, "inodes")) == (138412032, 8064)
    assert o._vector(rows, "delta") == o.c.canonical(rows)
    assert [r["device_selector"] for r in rows] == [
        "install_parent", "state_parent", "state_parent", "journal_parent",
        "evidence_parent", *(["quota_parent"] * 7)]
    assert all(r["status"] == "UNRELEASED" and "device" not in r for r in rows)
    changed = copy.deepcopy(rows)
    changed[0]["commitment"]["bytes"] -= 1
    with pytest.raises(o.c.ContractError, match="VECTOR_DELTA"):
        o._vector(changed, "delta")
    # Every call owns its arrays: consumers cannot mutate the frozen source.
    rows[0]["evidence"].append("/unexpected")
    assert len(o.delta_rows()[0]["evidence"]) == 4


def test_source_member_order_paths_and_carrier_identity_are_fixed():
    rows = o.source_members()
    assert len(rows) == 26
    assert [r["role"] for r in rows[-12:]] == [r[0] for r in o.DELTA_PINS]
    assert len({(r["batch"], r["path"]) for r in rows}) == 26
    assert rows[-5]["path"].endswith("/0023-plan.json")
    assert rows[-2]["path"].endswith("/0048-resource-preflight.json")
    assert not any("0022-resume" in r["path"] or "0049-preflight" in r["path"] for r in rows)
    with pytest.raises(o.c.ContractError, match="CARRIER_SET"):
        o.read_horizon({})
    with pytest.raises(o.c.ContractError, match="CARRIER_PIN"):
        o.read_horizon({r[0]: b"unqualified replacement" for r in o.ARCHIVES})


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":1.0}', b'{"x":NaN}',
                                b'{"x":9223372036854775808}', b'\xef\xbb\xbf{}', b'[]'])
def test_retained_json_rejects_ambiguous_or_out_of_range_values(raw):
    with pytest.raises(o.c.ContractError):
        o._json(raw)


def test_json_permits_original_noncanonical_layout_but_not_changed_bytes():
    raw = b'{ "x": 1, "y": -1 }\n'
    assert o._json(raw) == {"x": 1, "y": -1}
    with pytest.raises(o.c.ContractError, match="SOURCE_PIN"):
        o._pin(raw + b" ", len(raw), hashlib.sha256(raw).hexdigest(), "SOURCE_PIN")


def test_pinned_historical_decimal_is_never_promoted_to_new_artifact():
    value = o._json(b'{"elapsed":1.25}', historical_client_intent=True)
    assert str(value["elapsed"]) == "1.25"
    with pytest.raises(o.c.ContractError):
        o.c.canonical(value)
    with pytest.raises(o.c.ContractError):
        o._json(b'{"elapsed":NaN}', historical_client_intent=True)


def archive_fixture(monkeypatch, *, target="fixed/plan.json", duplicate=False):
    content = b'{"actual":true}\n'
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(target, content)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                z.writestr(target, content)
    raw = out.getvalue()
    monkeypatch.setattr(o, "ARCHIVES", (("fixture", "fixture.zip", len(raw), hashlib.sha256(raw).hexdigest()),))
    monkeypatch.setattr(o, "source_members", lambda: [dict(batch="fixture", role="plan",
        path="fixed/plan.json", bytes=len(content), sha256=hashlib.sha256(content).hexdigest())])
    return {"fixture": raw}


def test_zip_reads_only_exact_member_without_extraction(monkeypatch):
    inputs = archive_fixture(monkeypatch)
    def forbidden(*_args, **_kwargs):
        pytest.fail("archive must never be extracted")
    monkeypatch.setattr(zipfile.ZipFile, "extract", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "extractall", forbidden)
    assert o.read_horizon(inputs) == {("fixture", "plan"): {"actual": True}}


@pytest.mark.parametrize("target,duplicate,code", [
    ("alternate/plan.json", False, "ARCHIVE"),
    ("../fixed/plan.json", False, "ZIP_PATH"),
    ("fixed/plan.json", True, "ZIP_MEMBERS"),
])
def test_zip_rejects_alias_or_duplicate_even_if_bytes_match(monkeypatch, target, duplicate, code):
    inputs = archive_fixture(monkeypatch, target=target, duplicate=duplicate)
    with pytest.raises(o.c.ContractError, match=code):
        o.read_horizon(inputs)


def quota_source():
    pairs = [(10001, 67108864, 4096), (10002, 67108864, 4096),
             (10003, 4194304, 128), (10004, 67108864, 4096)]
    for start in (11001, 12001, 12011, 12021, 12031, 12041):
        pairs += [(project, 1048576, 128) for project in range(start, start + 7)]
    return {"capacity_observed": {"quota_inventory": [
        dict(project=project, hard=size // 1024, ihard=inodes)
        for project, size, inodes in pairs]}}


def test_configured_quota_is_separate_fixed_liability_not_usage_credit():
    value = quota_source()
    value["capacity_observed"]["quota_inventory"].append(dict(project=12051, hard=0, ihard=0))
    rows = o._quota(value)
    assert len(rows) == 46
    assert sum(r["hard_bytes"] for r in rows) == 249561088
    assert sum(r["inode_hard_limit"] for r in rows) == 17792
    assert all(set(r) == {"project_id", "hard_bytes", "inode_hard_limit"} for r in rows)


@pytest.mark.parametrize("change", ["duplicate", "reorder", "overflow", "float", "delta_present"])
def test_quota_drift_fails_closed(change):
    value = quota_source()
    rows = value["capacity_observed"]["quota_inventory"]
    if change == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif change == "reorder":
        rows.reverse()
    elif change == "overflow":
        rows[0]["hard"] = 2**63 - 1
    elif change == "float":
        rows[0]["hard"] = 1.0
    else:
        rows.append(dict(project=12051, hard=1024, ihard=128))
    with pytest.raises(o.c.ContractError):
        o._quota(value)


def test_snapshot_rejects_adopted_permission_and_refund():
    for name in ("historical_plan_executed", "released_or_refunded"):
        value = dict(historical_plan_executed=False, released_or_refunded=False)
        value[name] = True
        with pytest.raises(o.c.ContractError, match="SNAPSHOT_PERMISSION"):
            o._snapshot(value)
