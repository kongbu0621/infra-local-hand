"""Isolated execution plumbing; none of these tests constitutes a field PASS."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sqlite3
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Core execution uses Linux wait4 and protected directory FDs", allow_module_level=True)

SPEC = importlib.util.spec_from_file_location("_case_execution_test", Path(__file__).parent / "e3_host/q2_core_delivery_dispatcher.py")
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def effects(tmp_path):
    value = d.FieldEffects({})
    # Test this collector independently of the admission/executable binder.
    value._installation_binding = lambda argv: (list(argv), {}, {}, [])
    value._candidate_root = str(tmp_path)
    now = value.now()
    value.context["guest_deadlines"] = dict(boot_id=now["boot_id"],
        boottime_deadline_ns=now["boottime_ns"] + 60 * d.NS,
        monotonic_deadline_ns=now["monotonic_ns"] + 60 * d.NS)
    value._active_case_deadlines = dict(owner_deadline_ns=now["boottime_ns"] + 10 * d.NS,
        owner_monotonic_deadline_ns=now["monotonic_ns"] + 10 * d.NS)
    return value, {"deadlines": {"owner_deadline_ns": value._active_case_deadlines["owner_deadline_ns"]}}


def test_owner_collector_real_child_waits_and_keeps_both_eof(tmp_path):
    value, plan = effects(tmp_path)
    raw = value._exec_child([sys.executable, "-I", "-B", "-c", "print('owner')"], plan)
    assert raw == b"owner\n"
    call = value._install_commands[-1]
    assert call["returncode"] == 0 and call["eof"] == ["stderr", "stdout"]
    assert call["wait4"]["wait_status"] == 0 and call["wait4"]["max_rss_bytes"] > 0
    assert "_effect_guard" not in value.__dict__


def test_owner_nonzero_is_not_promoted_or_retried(tmp_path):
    value, plan = effects(tmp_path)
    with pytest.raises(d.DispatchError, match="INSTALL_COMMAND_FAILED"):
        value._exec_child([sys.executable, "-I", "-B", "-c", "raise SystemExit(3)"], plan)
    assert len(value._install_commands) == 1
    assert value._install_commands[0]["returncode"] == 3
    assert "_effect_guard" not in value.__dict__


def test_owner_stderr_is_not_hidden_by_zero_exit(tmp_path):
    value, plan = effects(tmp_path)
    with pytest.raises(d.DispatchError, match="OWNER_STDERR"):
        value._exec_child([sys.executable, "-I", "-B", "-c", "import sys; print('bad',file=sys.stderr)"], plan)
    assert value._install_commands[-1]["stderr"] == b"bad\n"


def test_expired_owner_cannot_start_and_does_not_refresh_window(tmp_path, monkeypatch):
    value, plan = effects(tmp_path)
    plan["deadlines"]["owner_deadline_ns"] = 1
    monkeypatch.setattr(d.subprocess, "Popen", lambda *a, **k: pytest.fail("child started"))
    with pytest.raises(d.DispatchError, match="CASE_DEADLINE"):
        value._exec_child([sys.executable, "-c", "pass"], plan)
    assert value._install_commands == []


@pytest.mark.parametrize("method,index", [("run_h01", 0), ("run_q4", 1), ("recover_h11", 2)])
def test_entry_rejects_wrong_fixed_case(tmp_path, method, index):
    value, plan = effects(tmp_path)
    with pytest.raises(d.DispatchError, match="_CASE"):
        getattr(value, method)(d.CASES[(index + 1) % 3], {}, plan)


def test_once_attempt_barrier_precedes_another_child(tmp_path, monkeypatch):
    value, plan = effects(tmp_path); case = d.CASES[0]
    plan.update(case_id=case["case_id"], operation_id=case["operation_id"])
    prepared = {"case": case, "_exec_attempted": True}
    monkeypatch.setattr(value, "_exec_child", lambda *a: pytest.fail("replayed"))
    with pytest.raises(d.DispatchError, match="ALREADY_ATTEMPTED"):
        value.run_h01(case, prepared, plan)


def test_h11_source_reader_cannot_read_business_result(tmp_path, monkeypatch):
    value, plan = effects(tmp_path)
    monkeypatch.setattr(value, "stable_read", lambda *a, **k: pytest.fail("result opened"))
    with pytest.raises(d.DispatchError, match="RESULT_SOURCE"):
        value._exec_source(d.CASES[2], {"paths": {}}, plan,
            "business/result-03c94c57c840717302854a3f.json", "result")


def test_h01_result_reads_original_evidence_slot_not_capture_directory(tmp_path):
    value, plan = effects(tmp_path)
    directory = tmp_path / "slot-evidence"; directory.mkdir()
    name = "result-03c94c57c840717302854a3f.json"
    (directory / name).write_bytes(b"raw-result"); (directory / name).chmod(0o600)
    prepared = {"paths": {"business": str(tmp_path / "incorrect-capture")}, "facts": {
        "ordinary": {"uid": os.geteuid(), "gid": os.getegid()},
        "slots": [{"roots": {"evidence": {"path": str(directory)}}}]}}
    source = value._exec_source(d.CASES[0], prepared, plan, "business/" + name, "result")
    assert source["raw"] == b"raw-result" and source["mode"] == 384
    assert prepared["_exec_physical"][source["path"]] == str(directory / name)


def ledger(tmp_path):
    path = tmp_path / "jobs.sqlite"
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("CREATE TABLE events(seq INTEGER,namespace TEXT,id TEXT,kind TEXT);")
    db.execute("INSERT INTO events VALUES(7,'job',?,'ACCEPTED')", (d.CASES[2]["operation_id"],))
    db.commit(); db.close(); path.chmod(0o600)
    return path


def test_h11_accepted_seq_is_observed_not_assumed_one(tmp_path):
    value, plan = effects(tmp_path); path = ledger(tmp_path)
    plan["ledger_path"] = str(path)
    before = path.read_bytes(); fd = os.open(path, os.O_RDONLY)
    assert before[18:20] == b"\x02\x02"
    try:
        assert value._exec_h11_accepted(d.CASES[2], {"_exec_ledger_fd": fd}, plan) == 7
    finally: os.close(fd)
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["jobs.sqlite"]


def test_h11_accepted_rejects_path_replacement_during_sqlite_read(tmp_path, monkeypatch):
    value, plan = effects(tmp_path); path = ledger(tmp_path)
    plan["ledger_path"] = str(path); fd = os.open(path, os.O_RDONLY)
    connect = sqlite3.connect
    def replaced(database, **kwargs):
        connection = connect(database, **kwargs)
        raw = path.read_bytes()
        path.rename(tmp_path / "original.sqlite")
        path.write_bytes(raw)
        return connection
    monkeypatch.setattr(sqlite3, "connect", replaced)
    try:
        with pytest.raises(d.DispatchError, match="LEDGER_CHANGED"):
            value._exec_h11_accepted(d.CASES[2], {"_exec_ledger_fd": fd}, plan)
    finally: os.close(fd)


def test_h11_accepted_missing_fails_without_export(tmp_path):
    value, plan = effects(tmp_path); path = ledger(tmp_path)
    db = sqlite3.connect(path); db.execute("DELETE FROM events"); db.commit(); db.close()
    plan["ledger_path"] = str(path); fd = os.open(path, os.O_RDONLY)
    try:
        with pytest.raises(d.DispatchError, match="ACCEPTED_EVENT"):
            value._exec_h11_accepted(d.CASES[2], {"_exec_ledger_fd": fd}, plan)
    finally: os.close(fd)
    assert not (tmp_path / "ledger-export.json").exists()


def test_h11_sidecar_blocks_before_sqlite_open(tmp_path, monkeypatch):
    value, plan = effects(tmp_path); path = ledger(tmp_path)
    (tmp_path / "jobs.sqlite-wal").write_bytes(b"retained")
    plan["ledger_path"] = str(path); fd = os.open(path, os.O_RDONLY)
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: pytest.fail("SQLite opened"))
    try:
        with pytest.raises(d.DispatchError, match="LEDGER_SIDECAR"):
            value._exec_h11_accepted(d.CASES[2], {"_exec_ledger_fd": fd}, plan)
    finally: os.close(fd)


def test_h11_incomplete_recovery_preserves_candidate_rejection(tmp_path, monkeypatch):
    value, plan = effects(tmp_path); case = d.CASES[2]
    def source(suffix, document):
        return {"path": "cases/" + case["case_id"] + "/" + suffix,
                "role": "recovery-plan", "mode": 420, "raw": d.canonical(document, newline=True)}
    sources = [source("launcher_declarations/recovery-resident.json", {"recovery": {}})]
    spec = importlib.util.spec_from_file_location("_fixed_h11", Path(__file__).parent / "e3_host/q4_h11_recovery.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(value, "_candidate_modules", lambda names: {"q4_h11_recovery": module})
    with pytest.raises(ValueError, match="H11_PLAN_SCHEMA"):
        value._exec_h11_proof(case, {}, plan, sources, {}, {}, {})


def h11_transcript():
    """Modeled retained artifacts, for proof construction only; no live claims."""
    case = d.CASES[2]; execution = "job-" + case["operation_id"] + "-preflight"
    units = {stage: d._phase_units(case["operation_id"], ["preflight"])[0][stage + "_unit"]
             for stage in ("bootstrap", "helper", "result_reader")}
    recovery = dict(schema="local-hand-q4-h11-recovery-plan/v1", namespace="job",
        operation_id=case["operation_id"], request_digest="a" * 64, phase="preflight",
        execution_id=execution, event_seq=9, handle_sha256="b" * 64,
        budget_deadline_ns=80, phase_deadline_ns=70, controller_deadline_ns=90,
        units=units, collector_started=False)
    report = dict(schema="local-hand-q4-h11-recovery-result/v1", status="RECOVERY_RECORDED",
        operation_id=case["operation_id"], execution_id=execution, phase="preflight",
        original_event_seq=9, recovery_event_seq=12,
        event_kinds=["RECOVERY_BARRIER", "QUOTA_EXIT_PENDING"], ticks=1, units=units,
        original_deadline_ns=80, phase_deadline_ns=70, controller_deadline_ns=90,
        future_start_blocked=True, tree_exited=True, writers_stopped=True,
        collectors_stopped=False, effects_checked=False, outcome="UNKNOWN", leases_retained=True,
        result_reread=False, start_replayed=False, q3_accepted=False, production_supported=False)
    origin = dict(complete=True, returncode=-9, eof=["stdout", "stderr"])
    launch = dict(schema="local-hand-q4-h11-launcher-result/v1", status="RECOVERY_RECORDED",
        operation_id=case["operation_id"], execution_id=execution, q3_accepted=False,
        production_supported=False, independent_controller_stop_required=True,
        ordinary_phase_closed=False, independent_ordinary_cleanup_required=True,
        collectors_stopped=False, result_reread=False, start_replayed=False,
        original_resident_pid=100, recovery_resident_pid=101, origin_capture=origin,
        origin_coordinator={"status": "ORIGIN_PEER_EXITED", "reason": "BRIDGE_PEER_EXITED"}, recovery=report)
    gateway = dict(failure=None, recovery_finished=True, recovery_only=True, recovery_rebinds=1,
        recovery_arm_ack=True, recovery_plan_sha256=d._sha(d.canonical(recovery)),
        stages=[dict(phase="preflight", stage=k, unit=v, recovery_observed=True) for k,v in units.items()])
    documents = {
        "launcher_declarations/recovery-resident.json": ("recovery-plan", {"recovery": recovery}),
        "launcher_output/recovery.json": ("recovery-summary", report),
        "launcher_output/result.json": ("launcher-result", launch),
        "launcher_output/gateway.json": ("gateway", gateway),
        "launcher_output/origin-capture.json": ("origin-capture", origin),
        "owner_output/seal.json": ("control-seal", {}),
        "launcher_output/reservation.json": ("launcher-reservation", {"controller": {"deadline_ns": 90}})}
    prefix = "cases/" + case["case_id"] + "/"
    sources = [dict(path=prefix+k, role=role, mode=420 if role=="recovery-plan" else 384,
                    raw=d.canonical(v, newline=True)) for k,(role,v) in documents.items()]
    sources += [dict(path=prefix+"launcher_output/origin-resident."+name,
                     role=name,mode=384,raw=b"") for name in ("stdout","stderr")]
    prepared = {"handoff": {"template": {"launcher": {"resident": {
        "request": {"operation_id": case["operation_id"]}}}}},
        "_exec_ledger_identity": {"path": "/case/state/jobs.sqlite", "dev": 4, "ino": 5},
        "facts": {"slots": [{"roots": {"evidence": {"path": "/case/slot-a/evidence"}}}]}}
    verified = {"source_files": {"tests/e3_host/"+name+".py": "f"*64
        for name in ("q4_h11_recovery", "q2_resident", "q2_launcher")}}
    modules = {}
    for name in ("q2_launcher", "q4_h11_recovery"):
        spec = importlib.util.spec_from_file_location("_proof_"+name,
            Path(__file__).parent / "e3_host" / (name+".py"))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); modules[name]=module
    return case, prepared, {"request": {"request_digest": "a"*64}}, sources, verified, launch, report, modules


def test_h11_proof_preserves_unknown_and_never_reads_business_result(tmp_path, monkeypatch):
    value, _ = effects(tmp_path)
    case, prepared, plan, sources, verified, launch, report, modules = h11_transcript()
    monkeypatch.setattr(value, "_candidate_modules", lambda names: modules)
    monkeypatch.setattr(value, "stable_read", lambda *a, **k: pytest.fail("H11 business read"))
    proof = value._exec_h11_proof(case, prepared, plan, sources, verified, launch, report)
    assert proof["assertions"]["outcome"] == "UNKNOWN"
    assert not proof["assertions"]["result_reread"] and not proof["assertions"]["start_replayed"]
    assert not proof["result_identity"]["stat_performed"] and not proof["result_identity"]["opened"]
    assert proof["result_identity"]["expected_path"].startswith("/case/slot-a/evidence/")
    assert d._validate_h11_proof(proof, case, sources, 90) == proof


@pytest.mark.parametrize("field,value", [("recovery_rebinds", 2), ("recovery_finished", False),
                                         ("recovery_plan_sha256", "0"*64)])
def test_h11_gateway_replay_or_unfinished_recovery_fails(tmp_path, monkeypatch, field, value):
    effect, _ = effects(tmp_path)
    case, prepared, plan, sources, verified, launch, report, modules = h11_transcript()
    monkeypatch.setattr(effect, "_candidate_modules", lambda names: modules)
    gateway = next(s for s in sources if s["role"] == "gateway")
    doc = d.document(gateway["raw"],limit=d.MEMBER_LIMIT); doc[field]=value
    gateway["raw"] = d.canonical(doc,newline=True)
    with pytest.raises(d.DispatchError, match="GATEWAY_BINDING"):
        effect._exec_h11_proof(case, prepared, plan, sources, verified, launch, report)


@pytest.fixture
def cancelled_transcript():
    """Original Broker/SQLite/report code; manager, pipes and receipts are modeled."""
    import io
    import json
    from unittest import mock
    import test_e3_q4_cancel_case as original
    fixed = d.CASES[1]
    fixture = original.CancelCaseTests()
    try:
        with mock.patch.object(original.uuid, "uuid4", return_value=original.uuid.UUID(fixed["operation_id"])):
            fixture.setUp()
        fixture.trigger()
        fixture.broker.tick()
        fixture.values.update(ActiveState="inactive", SubState="dead", ExecMainCode="1", ExecMainStatus="0")
        fixture.part["launch"].returncode = 0
        fixture.part["launch"].stdout = io.BytesIO()
        fixture.part["launch"].stderr = io.BytesIO()
        fixture.part["quota_transport"].eof.update(("stdout", "stderr"))
        with mock.patch.object(original.life, "parent", return_value=(fixture.pin, True)):
            fixture.manager._inspect_unit(fixture.part)
        report = fixture.case.poll()
        assert original.case_module.validate_report(report) == []
        assert report["status"] == "EXERCISED" and report["helper_exit_proven"]
        assert report["ledger"]["reader_delivered"] is False
        row = fixture.state.get("job", fixed["operation_id"])
        record = row["record"]
        names = d._phase_units(fixed["operation_id"], ["preflight"])[0]
        record["handles"] = {"preflight": {"manager": {
            "bootstrap": {"unit": names["bootstrap_unit"], "invocation_id": "b" * 32},
            "helper": dict(report["helper"]["identity"]), "result_reader": None}}}
        export = {"operation": {"id": fixed["operation_id"], "digest": row["digest"],
                               "record_json": json.dumps(record)},
                  "events": [{key: event[key] for key in ("seq", "kind", "data_json")}
                             for event in fixture.state.events("job", fixed["operation_id"])]}
        capture = {"complete": True, "returncode": 0, "eof": ["stdout", "stderr"]}
        launch = {"schema": "local-hand-q4-cancel-launcher-result/v1", "status": "CANCEL_CASE_RECORDED",
            "q3_accepted": False, "production_supported": False, "ordinary_phase_closed": False,
            "independent_ordinary_cleanup_required": True, "case": report,
            "resident_capture": capture, "cleanup_errors": []}
        prefix = "cases/" + fixed["case_id"] + "/"
        documents = {"launcher_output/result.json": launch, "launcher_output/capture.json": capture,
            "launcher_output/phase.json": {"case": report}, "records/ledger-export.json": export,
            "launcher_output/resident.stdout": {"case": report}}
        sources = [{"path": prefix + suffix, "role": "test", "mode": 384,
                    "raw": d.canonical(doc, newline=True)} for suffix, doc in documents.items()]
        sources.append({"path": prefix + "launcher_output/resident.stderr", "role": "stderr", "mode": 384, "raw": b""})
        prepared = {"sources": [{"path": prefix + "reservation/empty-ledger-gate.json",
            "role": "empty-ledger-gate", "mode": 384, "raw": b"{}\n"}], "handoff": {"template": {"launcher": {
            "resident": {"request": fixture.request, "principal": {"principal_id": fixture.owner.principal_id}}}}}}
        spec = importlib.util.spec_from_file_location("_fixed_cancel_launcher",
            Path(__file__).parent / "e3_host/q2_launcher.py")
        launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)
        modules = {"q2_launcher": launcher, "q4_cancel_case": original.case_module}
        yield fixed, prepared, {"request": fixture.request}, sources, modules, report
    finally:
        fixture.doCleanups()


def test_q4_original_cancel_report_needs_no_unstarted_reader(tmp_path, monkeypatch, cancelled_transcript):
    value, _ = effects(tmp_path)
    case, prepared, plan, sources, modules, report = cancelled_transcript
    monkeypatch.setattr(value, "_candidate_modules", lambda names: modules)
    result = value._exec_observations(case, prepared, plan, sources, {},
        {"source_files": {"tests/e3_host/q2_resident.py": "a" * 64}})
    units = result["observations"]["unit_identities"]
    assert [row["stage"] for row in units] == ["bootstrap", "helper"]
    assert units[1]["invocation_id"] == report["trigger"]["identity"]["invocation_id"]
    d._validate_units(units, case)
    assert result["observations"]["full_h07"] is False


@pytest.mark.parametrize("mutation,reason", [("reader", "READER_DELIVERED"),
    ("late_delivery", "READER_DELIVERED"), ("helper", "HELPER_IDENTITY")])
def test_q4_ledger_cannot_invent_reader_or_replace_helper(tmp_path, monkeypatch, cancelled_transcript, mutation, reason):
    import json
    value, _ = effects(tmp_path)
    case, prepared, plan, sources, modules, report = cancelled_transcript
    monkeypatch.setattr(value, "_candidate_modules", lambda names: modules)
    source = next(row for row in sources if row["path"].endswith("ledger-export.json"))
    export = d.document(source["raw"], limit=d.MEMBER_LIMIT)
    record = json.loads(export["operation"]["record_json"])
    manager = record["handles"]["preflight"]["manager"]
    if mutation == "reader":
        manager["result_reader"] = {"unit": d._phase_units(case["operation_id"], ["preflight"])[0]["result_reader_unit"],
                                    "invocation_id": "c" * 32}
    elif mutation == "helper":
        manager["helper"]["invocation_id"] = "c" * 32
    else:
        export["events"].append({"seq": max(row["seq"] for row in export["events"]) + 1,
            "kind": "MANAGER_DELIVERY_INTENT", "data_json": json.dumps({
                "delivery_intents": [report["target_execution_id"] + ":result_reader"]})})
    export["operation"]["record_json"] = json.dumps(record)
    source["raw"] = d.canonical(export, newline=True)
    with pytest.raises(d.DispatchError, match=reason):
        value._exec_observations(case, prepared, plan, sources, {},
            {"source_files": {"tests/e3_host/q2_resident.py": "a" * 64}})


@pytest.mark.parametrize("index", [0, 2])
def test_non_cancel_unit_validation_still_requires_reader(index):
    case = d.CASES[index]
    units = [{"phase": phase, "stage": stage, "unit": names[stage + "_unit"], "invocation_id": "a" * 32}
             for phase in case["phases"]
             for names in d._phase_units(case["operation_id"], [phase])
             for stage in ("bootstrap", "helper")]
    units.sort(key=lambda row: (row["phase"], row["stage"], row["unit"]))
    with pytest.raises(d.DispatchError, match="UNIT_IDENTITIES"):
        d._validate_units(units, case)
