"""Pure raw-source reconstruction; synthetic inputs do not prove a field run."""
import copy
import importlib.util
from pathlib import Path
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("The approved candidate decoder is Linux-only", allow_module_level=True)

from admin.local_hand_quota_observer import q2_config, controller_guard
from local_hand_jobs import budget, quota_grant
from q2_fixtures import grant_data, SECOND
from test_e3_quota_q2_runtime import declaration

SPEC = importlib.util.spec_from_file_location("_core_phase_test",
    Path(__file__).parent / "e3_host/q2_core_delivery_dispatcher.py")
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def fixture(index=1, phase="preflight"):
    case = d.CASES[index - 1]
    cfg = declaration()
    grant = grant_data(operation=case["operation_id"], phase=phase,
                       predecessors=() if phase == "preflight" else ("f" * 32,))
    old = next(iter(cfg["grants"].values()))
    grant["query_parent"] = old["query_parent"]
    grant["management_parent"] = old["management_parent"]
    grant["endpoint"]["gid"] = old["endpoint"]["gid"]
    grant["management"] = old["management"]
    projects = case["project_ids"][3:] if phase == "evidence" else case["project_ids"][:3]
    for root, project in zip(grant["roots"], projects):
        root["project_id"] = project
    cfg["capacity"]["domains"] = [dict(filesystem_uuid=root["filesystem_uuid"],
        project_id=root["project_id"], hard_bytes=root["hard_bytes"], hard_inodes=128)
        for root in grant["roots"]]
    grant["management"]["capacity_digest"] = quota_grant.digest(cfg["capacity"])
    original = d._budget(case["phases"])["operation"]
    limits = budget.allocated_limits(original, "job")
    grant["budget"].update(limits=limits, budget_digest=d._sha(d.canonical(original)),
                           deadline_boottime_ns=73 * SECOND)
    cfg["grants"] = {grant["request"]["request_id"]: grant}
    cfg["source_commit"] = d.CANDIDATE["commit"]
    root_rows = copy.deepcopy(grant["roots"])
    for project in case["project_ids"]:
        if project not in projects:
            root_rows.append(dict(root_rows[0], project_id=project))
    identity = dict(d._identity(case), **{key: grant["request"][key]
        for key in ("authority_digest", "manifest_digest", "epoch")})
    identity["slot_generation"] = grant["request"]["generation"]
    target = dict(schema=controller_guard.SCHEMA,
        unit=case["controller_prefix"] + "-target.service", invocation_id="a" * 32,
        cgroup="/lhqcore.slice/" + case["controller_prefix"] + "-target.service",
        cgroup_device=9, cgroup_inode=80, runtime_max_usec=85000000,
        timeout_stop_usec=1000000, memory_bytes=268435456, tasks_max=32,
        cpu_quota_per_sec_usec=1000000, limit_cpu_seconds=85)
    plan = dict(preparation_id=case["preparation_id"], identity=identity,
        budgets=d._budget(case["phases"]), controllers={"target": target,
            "target_storage_bytes": 1048576, "target_storage_inodes": 64},
        request={"request_digest": "4" * 64}, phases=d._phase_units(case["operation_id"], case["phases"]),
        deadlines={"owner_deadline_ns": 120 * SECOND})
    preparation = dict(schema="local-hand-q2-fixture-preparation/v1",
        preparation_id=case["preparation_id"], plan_sha256="8" * 64,
        status="RESOURCES_PREPARED", reason=None,
        facts={"directories": {"capture": {"path": "/synthetic/capture"}},
               "host": {"boot_id": grant["request"]["boot_id"]}, "roots": root_rows},
        q2_accepted=False, q3_accepted=False, production_supported=False, fixture_generated=False)
    active = q2_config.decode(d.canonical(cfg), "/synthetic/capture/" + phase + "/observer.json",
                              d._sha(d.canonical(cfg))).active()
    reservation = dict(schema="local-hand-q2-system-launcher-reservation/v1" if index == 1 else
        "local-hand-q2-launcher-reservation/v1" if index == 2 else "local-hand-q4-h11-launcher-reservation/v1",
        fixture_digest="9" * 64, session=identity["session"],
        controller={"controller": target, "issued_ns": SECOND, "deadline_ns": 86 * SECOND,
                    "output_bytes": 32768, "storage_bytes": 1048576, "storage_inodes": 64},
        started_ns=2 * SECOND)
    common = {"q3_accepted": False, "production_supported": False}
    values = {"observer-config": cfg, "preparation-result": preparation,
              "launcher-reservation": reservation}
    if index == 1:
        values["phase-result"] = dict(common, status="PHASE_CLOSED", grant_digest=active.digest,
                                     fence={"request_digest": active.request.digest})
        values["launcher-result"] = dict(common, status="CHAIN_CLOSED", grant_digests={phase: active.digest})
    elif index == 2:
        report = dict(operation_id=case["operation_id"], request_digest=plan["request"]["request_digest"],
                      phase_deadline_ns=24 * SECOND)
        values["phase-result"] = dict(common, status="CANCEL_CASE_RECORDED", grant_digest=active.digest, case=report)
        values["launcher-result"] = copy.deepcopy(values["phase-result"])
    else:
        units = {key: plan["phases"][0][key + "_unit"] for key in ("bootstrap", "helper", "result_reader")}
        recovery = dict(operation_id=case["operation_id"], phase=phase, budget_deadline_ns=73 * SECOND,
                        phase_deadline_ns=25 * SECOND, controller_deadline_ns=86 * SECOND, units=units)
        summary = dict(recovery)
        summary["original_deadline_ns"] = summary.pop("budget_deadline_ns")
        values.update({"recovery-plan": {"recovery": recovery}, "recovery-summary": summary,
            "gateway": {}, "origin-capture": {},
            "launcher-result": dict(common, status="RECOVERY_RECORDED", recovery=summary)})
    sources = [{"path": path, "role": role, "mode": 420 if role == "recovery-plan" else 384,
                "raw": d.canonical(values[role], newline=role == "preparation-result")}
               for path, role in d.phase_source_specs(case, phase)]
    return case, phase, plan, sources


def extract(args):
    return d._phase_extract(*args, q2_config, budget, controller_guard)


def change(args, role, callback):
    source = next(row for row in args[3] if row["role"] == role)
    value = d.document(source["raw"], limit=d.MEMBER_LIMIT, newline=role == "preparation-result")
    callback(value)
    source["raw"] = d.canonical(value, newline=role == "preparation-result")


@pytest.mark.parametrize("index,phase", [(1, "preflight"), (1, "business"), (1, "evidence"), (2, "preflight"), (3, "preflight")])
def test_actual_decoder_reconstructs_original_budget_and_complete_request_digest(index, phase):
    args = fixture(index, phase)
    facts = extract(args)
    cfg = next(row for row in args[3] if row["role"] == "observer-config")
    active = q2_config.decode(cfg["raw"], "/synthetic/capture/" + phase + "/observer.json",
                              d._sha(cfg["raw"])).active()
    assert facts["quota_request_sha256"] == active.request.digest != active.digest
    assert facts["stage_deadline_ns"] == 24 * SECOND
    assert facts["phase_deadline_ns"] == 25 * SECOND
    assert facts["budget_deadline_ns"] == 73 * SECOND
    assert facts["controller_deadline_ns"] == 86 * SECOND
    assert facts["controller_deadline_ns"] < args[2]["deadlines"]["owner_deadline_ns"]


@pytest.mark.parametrize("fault", ["missing", "duplicate", "mode", "role", "newline", "bad_config"])
def test_source_closure_has_no_missing_or_ambiguous_fallback(fault):
    args = fixture()
    rows = args[3]
    if fault == "missing": rows.pop()
    elif fault == "duplicate": rows.append(copy.deepcopy(rows[0]))
    elif fault == "mode": rows[0]["mode"] = 420
    elif fault == "role": rows[0]["role"] = "stdout"
    elif fault == "newline": rows[0]["raw"] += b"\n"
    else: change(args, "observer-config", lambda value: value["grants"].clear())
    with pytest.raises(d.DispatchError): extract(args)


@pytest.mark.parametrize("role,mutate", [
    ("preparation-result", lambda v: v.update(status="INCOMPLETE")),
    ("preparation-result", lambda v: v["facts"]["roots"][0].update(inode=99999)),
    ("observer-config", lambda v: v.update(source_commit="f" * 40)),
    ("launcher-reservation", lambda v: v.update(session="f" * 64)),
    ("launcher-reservation", lambda v: v["controller"].update(deadline_ns=101 * SECOND)),
    ("launcher-reservation", lambda v: v["controller"].update(issued_ns=True)),
    ("launcher-reservation", lambda v: v["controller"].update(storage_bytes=1)),
    ("launcher-reservation", lambda v: v["controller"]["controller"].update(unit="other.service")),
    ("phase-result", lambda v: v.update(grant_digest="f" * 64)),
    ("phase-result", lambda v: v["fence"].update(request_digest="f" * 64)),
])
def test_reencoded_wrong_preimage_never_becomes_phase_facts(role, mutate):
    args = fixture()
    change(args, role, mutate)
    with pytest.raises(d.DispatchError): extract(args)


def test_q4_report_stage_cutoff_cannot_replace_phase_deadline():
    args = fixture(2)
    for role in ("phase-result", "launcher-result"):
        change(args, role, lambda v: v["case"].update(phase_deadline_ns=25 * SECOND))
    with pytest.raises(d.DispatchError, match="CANCEL_BINDING"): extract(args)


@pytest.mark.parametrize("key", ["budget_deadline_ns", "phase_deadline_ns", "controller_deadline_ns"])
def test_h11_original_deadlines_cannot_be_renewed(key):
    args = fixture(3)
    change(args, "recovery-plan", lambda v: v["recovery"].__setitem__(key, v["recovery"][key] + 1))
    with pytest.raises(d.DispatchError, match="RECOVERY_DEADLINE"): extract(args)


def test_field_method_uses_verified_candidate_loader(monkeypatch):
    args = fixture()
    effects = object.__new__(d.FieldEffects)
    calls = []
    modules = {"admin.local_hand_quota_observer.q2_config": q2_config,
               "local_hand_jobs.budget": budget,
               "admin.local_hand_quota_observer.controller_guard": controller_guard}
    monkeypatch.setattr(effects, "_candidate_modules", lambda names: calls.append(names) or modules)
    assert effects.phase_facts(*args) == extract(args)
    assert tuple(modules) == calls[0]


def test_receipt_accepts_actual_85_second_controller_inside_120_second_owner():
    case, phase, plan, sources = fixture(2)
    facts = extract((case, phase, plan, sources))
    receipts = d._validate_phase_receipts(case, sources, {phase: facts}, 120 * SECOND)
    assert receipts[0][1]["controller_deadline_ns"] == 86 * SECOND
    with pytest.raises(d.DispatchError, match="CONTROLLER_DEADLINE"):
        d._validate_phase_receipts(case, sources, {phase: facts}, 85 * SECOND)


def test_slot_generation_is_distinct_from_policy_generation():
    args = fixture()
    assert args[2]["identity"]["generation"] == 1
    assert extract(args)["quota_request_id"]
    args[2]["identity"]["slot_generation"] = "f" * 32
    with pytest.raises(d.DispatchError, match="GRANT_BINDING"): extract(args)


def test_evidence_cannot_use_preflight_root_projects():
    args = fixture(1, "evidence")
    # Keep the observer's Config validity but try to relabel the case domain map.
    wrong = copy.deepcopy(args[0])
    wrong["project_ids"] = wrong["project_ids"][3:] + wrong["project_ids"][:3]
    original_cases = d.CASES
    try:
        d.CASES = (wrong, *d.CASES[1:])
        with pytest.raises(d.DispatchError, match="PHASE_ROOTS"):
            extract((wrong, *args[1:]))
    finally:
        d.CASES = original_cases
