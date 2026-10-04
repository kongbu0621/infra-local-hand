"""Core adapter uses real candidate constructors; quota/machine facts are synthetic."""
import copy
import os
from pathlib import Path
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux protected case preparation", allow_module_level=True)

from test_e3_q2_core_delivery_dispatcher import d
from test_e3_quota_q2_prepare_driver import fixture, d as driver
from test_e3_quota_q2_system_prepare_driver import system_fixture


@pytest.mark.parametrize("case", d.CASES)
def test_unreleased_actual_preparation_stops_before_mutation(case, monkeypatch):
    effects = d.FieldEffects({})
    monkeypatch.setattr(d.os, "open", lambda *a, **kw: pytest.fail("file effect before release"))
    monkeypatch.setattr(d.os, "mkdir", lambda *a, **kw: pytest.fail("directory effect before release"))
    with pytest.raises(d.DispatchError, match="INSTALLATION_REQUIRED"):
        effects.prepare_case(case, d.build_intent(case), 100)


def translated(case):
    plan, original = fixture() if case["index"] == 2 else system_fixture()
    plan.update(scope=d.SCOPE, baseline=d.BASELINE["commit"], preparation_id=case["preparation_id"],
                settings=d._prep_settings(case, 1900000000))
    observed = original["facts"]
    plan["directories"]["state"]["path"] = "/synthetic-q2/state"
    observed["directories"]["state"]["path"] = "/synthetic-q2/state"
    for expected, planned, root in zip(d._planned_roots(case), plan["roots"], observed["roots"], strict=True):
        planned.update(project_id=expected["project_id"], ref=expected["ref"],
                       hard_bytes=expected["hard_bytes"], inode_hard_limit=128)
        root.update(planned)
    children = {name: {"path": "/synthetic-q2/capture/" + name, "device": 70, "inode": 9000 + n}
        for n, name in enumerate(("preflight", "business", "evidence", "management_evidence",
            "launcher_output", "supervisor_output", "owner_output", "launcher_declarations",
            "supervisor_declarations", "owner_declarations"))}
    receipt = {"schema": "local-hand-q2-fixture-preparation/v1", "preparation_id": case["preparation_id"],
        "plan_sha256": d._sha(driver.encoded(plan)), "status": "RESOURCES_PREPARED", "reason": None,
        "facts": observed, "q2_accepted": False, "q3_accepted": False,
        "production_supported": False, "fixture_generated": False}
    helpers = {"q2_prepare_driver": driver, "q2_prepare_assembly": driver.helper("q2_prepare_assembly")}
    return plan, receipt, children, helpers


@pytest.mark.parametrize("case", d.CASES)
def test_fixed_settings_validate_under_original_candidate(case):
    settings = d._prep_settings(case, 1900000000)
    assert driver.validate_settings(settings) == settings
    assert settings["identity"]["operation_id"] == case["operation_id"]
    assert settings["owner"]["runtime_ns"] == 120 * d.NS
    assert settings["original_budgets"] == d._budget(case["phases"])["operation"]


@pytest.mark.parametrize("case", d.CASES)
def test_exact_candidate_translation_and_scoped_schema_only(case):
    plan, receipt, children, helpers = translated(case)
    before = copy.deepcopy((plan, receipt))
    result = d._prep_translate(case, plan, receipt, children, helpers)
    assert (plan, receipt) == before
    original, authority, manifest = driver.facts_from_observed(plan, receipt["facts"], children,
                                                             result["authority"])
    actual = copy.deepcopy(result["facts"])
    actual["schema"] = original["schema"]
    assert actual == original
    assert authority == result["authority"] and manifest == result["manifest"]
    assert result["assembled"]["resident"]["request"]["operation_id"] == case["operation_id"]
    assert result["assembled"]["resident"]["principal"]["scopes"] == ["lh:submit", "lh:read", "lh:evidence"] + (
        ["lh:cancel"] if case["index"] == 2 else [])
    assert ("system_geometry" in manifest) == (case["index"] != 2)


@pytest.mark.parametrize("fault", ["scope", "baseline", "status", "digest", "retained", "accepted", "extra", "schema"])
def test_translation_rejects_changed_preimages(fault):
    case = d.CASES[0]
    plan, receipt, children, helpers = translated(case)
    if fault == "scope": plan["scope"] = "old-scope"
    elif fault == "baseline": plan["baseline"] = "0" * 40
    elif fault == "status": receipt["status"] = "INCOMPLETE"
    elif fault == "digest": receipt["plan_sha256"] = "0" * 64
    elif fault == "retained": receipt["facts"]["retained_after"] = ["changed"]
    elif fault == "accepted": receipt["q2_accepted"] = True
    elif fault == "extra": receipt["unapproved"] = True
    else: receipt["schema"] += "-changed"
    with pytest.raises(d.DispatchError):
        d._prep_translate(case, plan, receipt, children, helpers)


def test_case_plan_binds_candidate_request_and_absolute_root_preimage():
    case = d.CASES[0]
    plan, receipt, children, helpers = translated(case)
    prepared = dict(plan=plan, receipt=receipt, **d._prep_translate(case, plan, receipt, children, helpers))
    deadlines = {"case_origin_ns": 1, "preparation_deadline_ns": 150 * d.NS,
        "owner_deadline_ns": 270 * d.NS, "remote_final_deadline_ns": 705 * d.NS,
        "carrier_deadline_ns": 750 * d.NS}
    result = d._plan_from_prepared(case, prepared, deadlines)
    assert result["request"] == prepared["assembled"]["resident"]["request"]
    assert result["identity"]["authority_digest"] == d._sha(driver.encoded(prepared["authority"]))
    assert result["deadlines"] == deadlines
    for row in result["roots"]:
        original = next(v for v in receipt["facts"]["roots"] if v["project_id"] == row["observed"]["project_id"])
        assert row["observed"]["inode"] == original["inode"]
        assert row["observed"]["path"] == row["planned"]["path"]
    prepared["receipt"]["facts"]["roots"][0]["path"] = "/changed"
    with pytest.raises(d.DispatchError, match="ROOT_PATH"):
        d._plan_from_prepared(case, prepared, deadlines)


def effect():
    e = d.FieldEffects({"guest_deadlines": {"boot_id": "fixture", "boottime_deadline_ns": 750,
                                           "monotonic_deadline_ns": 760}})
    e.now = lambda: {"boot_id": "fixture", "boottime_ns": 100, "monotonic_ns": 110}
    e._active_case_deadlines = {"preparation_deadline_ns": 200, "preparation_monotonic_deadline_ns": 210,
                                "owner_deadline_ns": 101, "owner_monotonic_deadline_ns": 111}
    return e


def test_preparation_deadline_uses_original_clock_relation():
    e = effect()
    assert d._prep_guard(e, 101)["boottime_ns"] == 100
    e.now = lambda: {"boot_id": "fixture", "boottime_ns": 100, "monotonic_ns": 112}
    with pytest.raises(d.DispatchError, match="DEADLINE"):
        d._prep_guard(e, 101)


def test_create_only_retains_same_fd_and_detects_replacement(tmp_path):
    e = effect()
    try:
        record = d._prep_file(e, str(tmp_path / "source.json"), b"{}\n", 200, uid=os.getuid(), gid=os.getgid())
        assert d._prep_reread(e, record, 200) == b"{}\n"
        with pytest.raises(FileExistsError):
            d._prep_file(e, record["path"], b"{}\n", 200, uid=os.getuid(), gid=os.getgid())
        Path(record["path"]).rename(tmp_path / "retained.json")
        Path(record["path"]).write_bytes(b"{}\n")
        with pytest.raises(d.DispatchError, match="SOURCE_CHANGED"):
            d._prep_reread(e, record, 200)
    finally:
        e.close()


def test_expired_preparation_creates_nothing(tmp_path):
    e = effect()
    e._active_case_deadlines.update(preparation_deadline_ns=100, preparation_monotonic_deadline_ns=110)
    with pytest.raises(d.DispatchError, match="DEADLINE"):
        d._prep_file(e, str(tmp_path / "source.json"), b"{}\n", 100)
    assert not list(tmp_path.iterdir())


def test_suspended_guest_cannot_extend_original_case_monotonic_window():
    e = effect()
    e._active_case_deadlines.update(preparation_deadline_ns=400, preparation_monotonic_deadline_ns=120)
    e.now = lambda: {"boot_id": "fixture", "boottime_ns": 390, "monotonic_ns": 120}
    with pytest.raises(d.DispatchError, match="DEADLINE"):
        d._prep_guard(e, 400)
    e._active_case_deadlines = {}
    with pytest.raises(d.DispatchError, match="CLOCK_BINDING"):
        d._prep_guard(e, 400)


def test_quota_retention_ignores_only_unconfigured_project_zero_own_usage():
    rows = [{"project": 0, "hard": 0, "soft": 0, "ihard": 0, "isoft": 0,
             "space": 100, "inodes": 5},
            {"project": 1001, "hard": 64, "soft": 0, "ihard": 128, "isoft": 0,
             "space": 10, "inodes": 2}]
    changed = copy.deepcopy(rows)
    changed[0]["space"] += 4096
    assert d._prep_quota_retained(rows) == d._prep_quota_retained(changed)
    changed[0]["hard"] = 1
    assert d._prep_quota_retained(rows) != d._prep_quota_retained(changed)
    changed = copy.deepcopy(rows)
    changed[1]["space"] += 4096
    assert d._prep_quota_retained(rows) != d._prep_quota_retained(changed)
@pytest.mark.parametrize("project,values", [(1001, {"hard": 1024, "ihard": 128, "valid": 5}),
                                          (12101, {"hard": 2048, "ihard": 128, "valid": 5})])
def test_quota_mutator_rejects_other_ids_or_limits_before_kernel(project, values):
    with pytest.raises(d.DispatchError, match="QUOTA_MUTATION"):
        d._prep_quota("/not-a-device", 0x800008, project, values)


@pytest.mark.parametrize("case", d.CASES)
def test_plan_case_creates_original_candidate_handoff_once(case, tmp_path, monkeypatch):
    # Root ownership is a host premise; keep this decoder/persistence fixture
    # runnable by an ordinary CI account without changing the production writer.
    write = d._prep_file
    def owned_write(*args, **kwargs):
        kwargs.update(uid=os.getuid(), gid=os.getgid())
        return write(*args, **kwargs)
    monkeypatch.setattr(d, "_prep_file", owned_write)
    plan, receipt, children, helpers = translated(case)
    prepared = dict(case=case, plan=plan, receipt=receipt, children=children, paths={"reservation": str(tmp_path)},
        source_objects={}, **d._prep_translate(case, plan, receipt, children, helpers))
    boot = receipt["facts"]["host"]["boot_id"]
    e = d.FieldEffects({"guest_deadlines": {"boot_id": boot, "boottime_deadline_ns": 750 * d.NS,
                                           "monotonic_deadline_ns": 760 * d.NS}})
    e.now = lambda: {"boot_id": boot, "boottime_ns": 100 * d.NS, "monotonic_ns": 110 * d.NS}
    e._active_case_deadlines = {"preparation_deadline_ns": 200 * d.NS,
        "preparation_monotonic_deadline_ns": 210 * d.NS,
        "owner_deadline_ns": 220 * d.NS, "owner_monotonic_deadline_ns": 230 * d.NS}
    runtime = driver.helper("q2_prepare_run")
    e._candidate_modules = lambda names: {"q2_prepare_run": runtime}
    monkeypatch.setattr(d.time, "time_ns", lambda: 1899999950 * d.NS)
    try:
        for role, value in (("preparation-plan", plan), ("preparation-result", receipt),
                            ("authority", {"authority_id": prepared["facts"]["identity"]["authority_id"],
                                "ledger_id": prepared["facts"]["identity"]["ledger_id"],
                                "state_root": prepared["facts"]["paths"]["broker_root"]})):
            prepared["source_objects"][role] = d._prep_file(e, str(tmp_path / (role + ".json")),
                d.canonical(value, newline=True), 200 * d.NS, uid=os.getuid(), gid=os.getgid())
        deadlines = {"case_origin_ns": 1, "preparation_deadline_ns": 200 * d.NS,
            "owner_deadline_ns": 220 * d.NS, "remote_final_deadline_ns": 705 * d.NS,
            "carrier_deadline_ns": 750 * d.NS}
        result = e.plan_case(case, prepared, deadlines)
        raw = Path(prepared["handoff_path"]).read_bytes()
        assert runtime.decode(raw, d._sha(raw)) == prepared["handoff"]
        assert prepared["handoff"]["schema"] == {
            1: runtime.SYSTEM_SCHEMA, 2: runtime.CANCEL_SCHEMA, 3: runtime.H11_SCHEMA}[case["index"]]
        assert prepared["sources"] == result["sources"]
        assert prepared["handoff"]["owner_envelope"]["deadline_ns"] == 220 * d.NS
        with pytest.raises(FileExistsError):
            e.plan_case(case, prepared, deadlines)
    finally:
        e.close()
