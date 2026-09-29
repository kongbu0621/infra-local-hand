"""Adversarial retained-evidence checks; these are not actual cgroup runs."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location("h07_spike_receipt", Path(__file__).with_name("verify_receipt.py"))
assert _SPEC and _SPEC.loader
v = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v)


def retained_case(case_id="C1"):
    """A human-specified fact transcript for checking evidence-loss mutations."""
    origin = 1_000_000_000
    boot_offset = 50_000_000_000
    events = []

    def event(name, a=0, b=0, c=0, at=None):
        t = origin + len(events) * 1_000_000 if at is None else at
        events.append(dict(event=name, seq=len(events) + 1, mono_ns=t,
                           boot_ns=t + boot_offset, a=a, b=b, c=c))

    event("g_created", 10, 3, 1)
    arm = origin + 1_000_000
    event("g_armed", arm + 20_000_000_000, arm + boot_offset + 20_000_000_000,
          arm + 17_000_000_000)
    event("s_created", 11, 3, 1)
    event("s_armed", 11, 60001, 2)
    event("s_credentials", 60001, 60001, 1)
    event("s_capabilities", 0, 0, 0)
    event("s_restrictions", 1, 2, 1)
    event("stream_originals", 2, 1, 1)
    event("request_sent", 1)
    event("request_received", 1)
    for number in range(1, 3 if case_id == "C1" else 2):
        if case_id != "C2":
            event("worker_created", number, 100 + number, 1)
            event("worker_request", number, 1, 1)
            if case_id != "C3":
                event("worker_pidfd", number, 1, 1)
                event("worker_identity", number, 100 + number, 1)
        if case_id == "C1":
            event("worker_exit", number, 0, 1)
    if case_id == "C2":
        event("barrier_ready")
    if case_id == "C3":
        event("lost_reply")
    if case_id == "C4":
        event("payload_started", 20, 20, 1)
        event("payload_confirmed", 1, 1, 0)
        event("s_crash")
        event("streams_held", 1, 1, 1)
    if case_id == "C5":
        event("burst_at_close", 1, 1, 6, at=arm + 17_000_000_000)
    tail = events[-1]["mono_ns"] + 1_000_000
    if case_id == "C6":
        event("g_crash", at=tail)
    else:
        event("close_requested", at=tail)
        event("b_kill", 1, at=tail)
        if case_id == "C2":
            event("late_attempt", 2, 3, 1, at=tail + 1_000_000)
            event("late_send_result", 2, 1, 1, at=tail + 2_000_000)
            event("late_rejected", 9, 1, 1, at=tail + 3_000_000)
            event("late_rejected", 2, 2, 1, at=tail + 4_000_000)
    tail = events[-1]["mono_ns"] + 1_000_000
    for name in ("s_exit", "b_empty", "streams_eof", "control_eof"):
        event(name, -9 if name == "s_exit" else 1,
              1 if name in ("s_exit", "streams_eof") else 0, at=tail)
        tail += 1_000_000
    if case_id != "C6":
        event("fenced", 1, at=tail)
        event("g_summary", 0 if case_id == "C3" else 1, 1, 1, at=tail + 1_000_000)
        tail += 2_000_000
    event("t_g_exit", 86 if case_id == "C6" else 0, 1, at=tail)
    event("t_cleanup_verified", 1, 1, 1, at=tail + 1_000_000)
    return dict(schema_version=1, kind="case", case_id=case_id,
                status="UNKNOWN_RETAINED" if case_id in ("C3", "C6") else "OBSERVED",
                reason={"C3": "expected_lost_identity", "C6": "expected_guardian_loss"}.get(case_id, "fixed_case_observed"), start_mono_ns=origin,
                start_boot_ns=origin + boot_offset, end_mono_ns=tail + 2_000_000,
                end_boot_ns=tail + 2_000_000 + boot_offset, events=events,
                guardian_pidfd_exit=True, guardian_wait_code=86 if case_id == "C6" else 0,
                guardian_stream_eof=True, tree_empty=True,
                streams={n: {"bytes": 0, "data_base64": "", "eof": True}
                         for n in ("stdout", "stderr")}, cleanup_attempted=True,
                cleanup_verified=True, deadline_met=True, output_exceeded=False)


def remove_event(r, name):
    r["events"] = [e for e in r["events"] if e["event"] != name]
    for seq, e in enumerate(r["events"], 1):
        e["seq"] = seq


def first(r, name):
    return next(e for e in r["events"] if e["event"] == name)


@pytest.mark.parametrize("case_id", ["C1", "C2", "C3", "C4", "C5", "C6"])
def test_expected_cases_are_distinct_from_complete_business_closure(case_id):
    result = v.derive_case(retained_case(case_id))
    assert result["errors"] == []
    assert result["case_expectation_met"]
    if case_id in ("C3", "C6"):
        assert result["classification"] == "UNKNOWN_RETAINED"
        assert result["identity_complete"] is not True
    if case_id == "C6":
        assert not result["fence_observed"]


@pytest.mark.parametrize("missing", ["g_created", "s_created", "s_armed", "stream_originals",
    "g_armed", "s_exit", "b_empty", "streams_eof", "control_eof", "fenced", "g_summary", "t_g_exit",
    "t_cleanup_verified", "worker_pidfd", "worker_identity", "worker_exit", "request_received",
    "worker_request"])
def test_aggregate_true_cannot_replace_a_missing_original_fact(missing):
    receipt = retained_case()
    remove_event(receipt, missing)
    assert not v.derive_case(receipt)["case_expectation_met"]


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"n":{"a":1,"a":2}}', b'{"x":NaN}',
                                 b'{"x":Infinity}', b'{"x":', b'\xff', b'[]'])
def test_ambiguous_or_truncated_input_is_rejected(raw):
    with pytest.raises(v.ReceiptError):
        v.load_report(raw)


def test_input_bytes_and_structure_are_bounded_before_processing():
    with pytest.raises(v.ReceiptError):
        v.load_report(b" " * (v.MAX_REPORT + 1))
    with pytest.raises(v.ReceiptError):
        v.load_report(b'{"x":' + b'[' * 30 + b'0' + b']' * 30 + b'}')


@pytest.mark.parametrize("field", ["guardian_pidfd_exit", "guardian_stream_eof", "tree_empty",
                                    "cleanup_verified", "deadline_met"])
def test_missing_independent_collector_fact_prevents_success(field):
    r = retained_case()
    r[field] = False
    assert not v.derive_case(r)["case_expectation_met"]


def test_base64_and_byte_count_must_describe_the_same_original_stream():
    r = retained_case()
    r["streams"]["stdout"] = dict(bytes=0, data_base64="YQ==", eof=True)
    assert "stdout: stream length mismatch" in v.validate_native(r)
    r["streams"]["stdout"] = dict(bytes=1, data_base64="YQ==!", eof=True)
    assert "stdout: invalid base64" in v.validate_native(r)


def test_bool_cannot_masquerade_as_identity_or_sequence():
    r = retained_case()
    r["events"][0]["seq"] = True
    r["events"][0]["a"] = True
    assert v.validate_native(r)


def test_duplicate_sequence_does_not_get_deduplicated_to_success():
    r = retained_case()
    r["events"][2]["seq"] = 2
    assert any("sequence" in e for e in v.validate_native(r))


def test_extra_fd_or_unverified_pidfd_cannot_count_as_original_identity():
    for b, c in ((2, 1), (0, 1), (1, 0)):
        r = retained_case()
        first(r, "worker_pidfd").update(b=b, c=c)
        result = v.derive_case(r)
        assert not result["case_expectation_met"]
        assert "invalid pidfd handoff/count" in result["errors"]


def test_stale_request_identity_and_replayed_create_are_rejected():
    r = retained_case()
    first(r, "worker_created")["a"] = 999
    assert not v.derive_case(r)["case_expectation_met"]
    r = retained_case()
    [e for e in r["events"] if e["event"] == "worker_created"][1]["a"] = 1
    assert "duplicate creation or descendant limit" in v.derive_case(r)["errors"]


def test_creation_after_fence_is_not_repaired_by_later_tree_empty():
    r = retained_case()
    created, closed = first(r, "worker_created"), first(r, "fenced")
    for clock in ("mono_ns", "boot_ns"):
        created[clock] = closed[clock] + 1
    assert "creation after fence/no-reinjection violation" in v.derive_case(r)["errors"]


def test_request_cutoff_uses_original_two_clocks_not_mutable_summary():
    r = retained_case("C5")
    arm, request = first(r, "g_armed"), first(r, "request_received")
    request["boot_ns"] = arm["b"] - 3_000_000_000
    assert "request accepted after original cutoff" in v.derive_case(r)["errors"]
    assert not v.derive_case(r)["case_expectation_met"]


def test_late_completion_and_refreshed_clock_cannot_relabel_success():
    r = retained_case()
    r["end_boot_ns"] += 21_000_000_000
    assert "native: falsely asserted deadline" in v.validate_native(r)
    r = retained_case()
    first(r, "g_armed")["a"] += 1_000_000_000
    assert not v.derive_case(r)["case_expectation_met"]


def test_missing_c5_actual_producer_at_close_is_inconclusive():
    for field, value in (("a", 0), ("b", 0), ("c", 0)):
        r = retained_case("C5")
        first(r, "burst_at_close")[field] = value
        result = v.derive_case(r)
        assert result["classification"] == "INCONCLUSIVE"
        assert not result["case_expectation_met"]


def test_c5_early_burst_does_not_prove_live_producer_at_close():
    r = retained_case("C5")
    e = first(r, "burst_at_close")
    e["mono_ns"] -= 1_000_000_000
    e["boot_ns"] -= 1_000_000_000
    assert v.derive_case(r)["classification"] == "INCONCLUSIVE"


def test_guardian_crash_cannot_be_sealed_by_external_cleanup():
    r = retained_case("C6")
    e = copy.deepcopy(r["events"][-1])
    e.update(event="g_summary", seq=len(r["events"]) + 1, a=1, b=1, c=1)
    r["events"].append(e)
    assert not v.derive_case(r)["case_expectation_met"]


def test_original_eof_is_not_synthesized_by_closing_reader():
    r = retained_case()
    first(r, "stream_originals")["c"] = 0
    assert not v.derive_case(r)["case_expectation_met"]


def test_failure_receipt_survives_json_roundtrip_without_reclassification():
    r = retained_case("C3")
    parsed = v.load_report(json.dumps(r).encode())
    assert v.derive_case(parsed)["classification"] == "UNKNOWN_RETAINED"


def retained_probe():
    r = retained_case()
    r.update(kind="probe", case_id="PROBE", guardian_wait_code=-9, events=[])
    facts = [("probe_created", 99, 3, 1), ("probe_capabilities", 0, 0, 0),
             ("probe_armed", 60001, 1, 2)]
    facts += [("probe_denial", nr, 1, 1) for nr in (41, 42, 257, 59, 272, 308, 101, 311, 165, 435)]
    facts += [("probe_ready", 1, 0, 0), ("probe_kill", 1, 0, 0),
              ("t_probe_exit", -9, 1, 0), ("t_cleanup_verified", 1, 1, 1)]
    for i, (name, a, b, c) in enumerate(facts, 1):
        r["events"].append(dict(event=name, seq=i, mono_ns=r["start_mono_ns"] + i,
                                boot_ns=r["start_boot_ns"] + i, a=a, b=b, c=c))
    return r


def test_probe_requires_actual_ordinary_permissions_and_every_denial():
    probe = retained_probe()
    assert v.derive_capability(probe)["supported"]
    for missing in ("probe_created", "probe_capabilities", "probe_armed", "probe_denial",
                    "probe_ready", "probe_kill", "t_probe_exit", "t_cleanup_verified"):
        broken = copy.deepcopy(probe)
        remove_event(broken, missing)
        assert not v.derive_capability(broken)["supported"]
    probe["events"][3]["b"] = 38  # ENOSYS is not a filter denial.
    assert not v.derive_capability(probe)["supported"]


def retained_report():
    groups = []
    for index, name in enumerate(("E", "G", "B", "B/S", "B/W"), 1):
        limit = {"memory.max": None, "memory.swap.max": None, "pids.max": None, "cpu.max": "max 100000"}
        if name in ("E", "G", "B"):
            limit = {"memory.max": v.LIMITS[name + "_memory_bytes"], "memory.swap.max": 0,
                     "pids.max": v.LIMITS[name + "_pids"], "cpu.max": v.LIMITS["cpu_max"]}
        groups.append(dict(relative=name, dev=20, ino=index, limits=limit))
    cases = [retained_case("C" + str(i)) for i in range(1, 7)]
    probe = retained_probe()
    observations = []
    for index, r in enumerate([probe] + cases):
        shift = index * 30_000_000_000
        for key in ("start_mono_ns", "start_boot_ns", "end_mono_ns", "end_boot_ns"):
            r[key] += shift
        for event in r["events"]:
            event["mono_ns"] += shift
            event["boot_ns"] += shift
            if event["event"] == "g_armed":
                for key in ("a", "b", "c"):
                    event[key] += shift
        for i, name in enumerate(("e_identity", "g_identity", "b_identity", "s_identity", "w_identity"), 1):
            r["events"].append(dict(event=name, seq=len(r["events"]) + 1,
                                    mono_ns=r["start_mono_ns"], boot_ns=r["start_boot_ns"],
                                    a=20, b=i, c=0o40755))
        for boundary in ("before", "after"):
            clock = "start" if boundary == "before" else "end"
            observations.append(dict(boundary=("probe" if index == 0 else "C" + str(index)) + "-" + boundary,
                mono_ns=r[clock + "_mono_ns"], boot_ns=r[clock + "_boot_ns"],
                cgroups={g["relative"]: dict(cpu_stat={"usage_usec": 10}, memory_current=0,
                    memory_peak=100, pids_current=0, pids_peak=2, memory_events={"oom_kill": 0},
                    pids_events={"max": 0}, populated=0) for g in groups}))
    closure = {name: "b" * 64 for name in v.REQUIRED_SOURCE_PATHS}
    closure.update({v.DOCUMENT_DIR + name: sha for name, sha in v.DOCUMENT_HASHES.items()})
    cleanup_objects = ["q2-h07-123-1-r1" + s for s in ("", "/G", "/B", "/B/S", "/B/W")]
    cleanup_objects += ["dedicated-account", "build/helper"]
    return dict(schema_version=1,
        source=dict(expected_commit="a" * 40, github_sha="a" * 40, head="a" * 40,
                    approved_A=v.APPROVED_A, closure_C=v.CLOSURE_C, closure_sha256=closure),
        run=dict(id="123", attempt=1, round=1), limits=dict(v.LIMITS), capability=probe, cases=cases,
        status="QUALIFIED_IN_FIXTURE", reason="",
        provenance=dict(runner_environment="github-hosted", runner_os="Linux", runner_arch="X64",
            image_os="ubuntu24", image_version="image-1", kernel="6.8.0-fixture", machine="x86_64",
            python="3.12", compiler={"path": "/usr/bin/cc", "version": "cc fixture"}, uid=0, euid=0,
            cap_eff="1", cap_bnd="1", no_new_privs=0, seccomp=0, boot_id="retained-fixture-boot",
            cgroup_mount="/sys/fs/cgroup", cgroup_parent_controllers=["cpu", "memory", "pids"],
            cgroup_parent_subtree_control=["cpu", "memory", "pids"], os_release={"id": "ubuntu", "version_id": "24.04"},
            native_sha256="c" * 64, fixture=dict(account=dict(uid=60001, gid=60001,
                supplementary_groups=[], home_created=False), cgroup_objects=groups,
                resource_observations=observations)),
        cleanup=dict(verified=True, residuals=[], records=[dict(object=x, operation="rmdir",
            identity_match=True, removed=True) for x in cleanup_objects]),
        budget=dict(prep_elapsed_seconds=10, cases_elapsed_seconds=150, cleanup_elapsed_seconds=1,
            diagnostic_bytes=0, report_bytes=20000, file_logical_bytes=100000, file_count=4,
            allocated_bytes=102400, inode_count=4, suite_stream_bytes=0))


def test_exact_fixture_evidence_can_qualify_with_expected_unknown_controls():
    result = v.derive_report(retained_report())
    assert result["errors"] == []
    assert result["status"] == "QUALIFIED_IN_FIXTURE"
    assert result["case_results"][2]["classification"] == "UNKNOWN_RETAINED"
    assert result["case_results"][5]["classification"] == "UNKNOWN_RETAINED"


@pytest.mark.parametrize("mutation", [
    "missing-source", "wrong-A", "wrong-document", "wrong-head", "retry", "quota",
    "empty-cleanup", "resource-gap", "aliased-cgroup", "weakened-limit", "wrong-held-cgroup",
    "reused-clock", "missing-probe", "probe-only-booleans", "wrong-platform", "wrong-account",
])
def test_fixture_claim_is_rejected_when_a_required_join_is_lost(mutation):
    r = retained_report()
    if mutation == "missing-source": r["source"]["closure_sha256"].pop(v.SOURCE_DIR + "helper.c")
    elif mutation == "wrong-A": r["source"]["approved_A"] = "d" * 40
    elif mutation == "wrong-document": r["source"]["closure_sha256"][v.DOCUMENT_DIR + "REQUIREMENTS.md"] = "d" * 64
    elif mutation == "wrong-head": r["source"]["head"] = "d" * 40
    elif mutation == "retry": r["run"]["attempt"] = 2
    elif mutation == "quota": r["run"]["round"] = 4
    elif mutation == "empty-cleanup": r["cleanup"]["records"] = []
    elif mutation == "resource-gap": r["provenance"]["fixture"]["resource_observations"].pop()
    elif mutation == "aliased-cgroup": r["provenance"]["fixture"]["cgroup_objects"][1]["ino"] = 1
    elif mutation == "weakened-limit": r["provenance"]["fixture"]["cgroup_objects"][0]["limits"]["memory.max"] *= 2
    elif mutation == "wrong-held-cgroup": first(r["cases"][0], "w_identity")["b"] = 999
    elif mutation == "reused-clock": r["cases"][1] = copy.deepcopy(r["cases"][0]); r["cases"][1]["case_id"] = "C2"
    elif mutation == "missing-probe": r["capability"] = None
    elif mutation == "probe-only-booleans": r["capability"]["events"] = []
    elif mutation == "wrong-platform": r["provenance"]["runner_environment"] = "self-hosted"
    elif mutation == "wrong-account": r["provenance"]["fixture"]["account"]["uid"] = 60002
    assert v.derive_report(r)["status"] != "QUALIFIED_IN_FIXTURE"


def test_queued_identity_after_close_does_not_imply_creation_after_close():
    r = retained_case()
    close = first(r, "close_requested")
    identity = first(r, "worker_identity")
    identity["mono_ns"] = close["mono_ns"] + 1
    identity["boot_ns"] = close["boot_ns"] + 1
    assert v.derive_case(r)["case_expectation_met"]


def test_g_created_observation_can_follow_child_arm_without_changing_birth():
    r = retained_case()
    created, arm = first(r, "g_created"), first(r, "g_armed")
    for clock in ("mono_ns", "boot_ns"):
        created[clock] = arm[clock] + 1
    assert v.derive_case(r)["case_expectation_met"]


@pytest.mark.parametrize("reason", ["capture_error", "native_deadline", "unexpected_control_loss"])
def test_explicit_collection_failure_is_not_erased_by_complete_aggregate_fields(reason):
    r = retained_case()
    r["reason"] = reason
    assert not v.derive_case(r)["case_expectation_met"]


def seal_report_size(report):
    """Use the fixture's unchanged final encoding, including its LF."""
    for _ in range(6):
        size = len((json.dumps(report, sort_keys=True, ensure_ascii=True,
                               separators=(",", ":")) + "\n").encode())
        if report["budget"]["report_bytes"] == size:
            return report
        report["budget"]["report_bytes"] = size
    raise AssertionError("synthetic report byte bill did not converge")


def retained_v2_envelope():
    """Only the envelope; account/continuation facts are deliberately missing."""
    report = retained_report()
    report["schema_version"] = 2
    report["run"] = dict(id="36599999999", attempt=1, round=2)
    report["provenance"]["boot_id"] = "11111111-1111-4111-8111-111111111111"
    for record in report["cleanup"]["records"]:
        record["object"] = record["object"].replace("q2-h07-123-1-r1", "q2-h07-36599999999-1-r2")
    source = report["source"]
    source.update(approved_continuation_A=v.APPROVED_CONTINUATION_A,
                  closure_continuation_C=v.CLOSURE_CONTINUATION_C)
    source["closure_sha256"].update({name: "b" * 64 for name in
                                     v.REQUIRED_CONTINUATION_SOURCE_PATHS - v.REQUIRED_SOURCE_PATHS})
    source["closure_sha256"].update({v.CONTINUATION_DOCUMENT_DIR + name: sha
                                     for name, sha in v.CONTINUATION_DOCUMENT_HASHES.items()})
    report.update(account_setup=None, continuation=None)
    return seal_report_size(report)


def test_schema_one_has_identical_verdict_and_no_backfilled_fields():
    report = retained_report()
    before = copy.deepcopy(report)
    assert v.validate_report(report) == v._validate_report_v1(report) == []
    assert v.derive_report(report)["status"] == "QUALIFIED_IN_FIXTURE"
    assert report == before
    assert "account_setup" not in report and "continuation" not in report
    report.update(status="UNKNOWN_RETAINED", reason="account preparation failed", capability=None,
                  cases=[], cleanup=dict(verified=False, records=[], residuals=["account unknown"]))
    report["budget"]["suite_stream_bytes"] = 0
    assert v.validate_report(report) == v._validate_report_v1(report) == []
    assert v.derive_report(report)["status"] == "UNKNOWN_RETAINED"


@pytest.mark.parametrize("version", [0, 3, "2", True, None])
def test_unknown_or_coerced_report_versions_are_not_guessed(version):
    report = retained_v2_envelope()
    report["schema_version"] = version
    assert v.derive_report(report)["status"] == "REJECTED"


@pytest.mark.parametrize("field", ["account_setup", "continuation"])
def test_schema_two_does_not_fill_missing_new_evidence(field):
    report = retained_v2_envelope()
    del report[field]
    assert any("missing" in error and field in error for error in v.validate_report(report))
    assert v.derive_report(report)["status"] == "REJECTED"


def test_new_fields_cannot_be_attached_to_schema_one_to_change_its_contract():
    report = retained_report()
    report["account_setup"] = {}
    report["continuation"] = {}
    assert v.derive_report(report)["status"] == "REJECTED"


@pytest.mark.parametrize("field", ["approved_A", "closure_C", "approved_continuation_A", "closure_continuation_C"])
def test_schema_two_requires_both_original_and_continuation_authorizations(field):
    report = retained_v2_envelope()
    report["source"][field] = "d" * 40
    seal_report_size(report)
    assert any("A/C identity" in error for error in v.validate_report(report))


@pytest.mark.parametrize("name", sorted(v.REQUIRED_CONTINUATION_SOURCE_PATHS))
def test_schema_two_source_closure_cannot_omit_a_required_input(name):
    report = retained_v2_envelope()
    del report["source"]["closure_sha256"][name]
    seal_report_size(report)
    assert any("source closure missing" in error for error in v.validate_report(report))


@pytest.mark.parametrize("name", sorted(v.CONTINUATION_DOCUMENT_HASHES))
def test_schema_two_requires_the_exact_approved_continuation_documents(name):
    report = retained_v2_envelope()
    report["source"]["closure_sha256"][v.CONTINUATION_DOCUMENT_DIR + name] = "0" * 64
    seal_report_size(report)
    assert "approved continuation document bytes differ" in v.validate_report(report)


def test_schema_two_extra_fields_and_duplicate_new_nested_keys_are_rejected():
    report = retained_v2_envelope()
    report["account_approved"] = True
    assert any("extra" in error for error in v.validate_report(report))
    report = retained_v2_envelope()
    report["source"]["new_authority"] = True
    seal_report_size(report)
    assert any("extra" in error for error in v.validate_report(report))
    with pytest.raises(v.ReceiptError, match="duplicate JSON key"):
        v.load_report(b'{"schema_version":2,"continuation":{"limit":3,"limit":99}}')


def test_schema_two_has_one_complete_report_budget_without_sidecar_allowance():
    report = retained_v2_envelope()
    report["budget"]["report_bytes"] -= 1
    assert any("byte bill" in error for error in v.validate_report(report))
    report["reason"] = "x" * v.MAX_REPORT
    assert v.derive_report(report)["status"] == "REJECTED"


def test_schema_two_success_booleans_without_account_facts_cannot_qualify():
    report = retained_v2_envelope()
    report["account_setup"] = {"admitted": True, "cleanup_verified": True}
    report["continuation"] = {"admitted": True}
    seal_report_size(report)
    result = v.derive_report(report)
    assert result["status"] == "REJECTED"
    assert any("account_setup" in error for error in result["errors"])


def retained_account_setup(report):
    """Pure account originals with no observer, account tools, or NSS calls."""
    account = v._support_module("account_evidence")
    run = report["run"]
    target = "q2hf" + run["id"][-15:] + "r" + str(run["round"])
    identity = dict(name=target, uid=60001, gid=60001, home="/nonexistent",
                    shell="/usr/sbin/nologin", supplementary_gids=[60001], group_member_count=0)
    empty_hash = hashlib.sha256(b"").hexdigest()

    def audit(role, seq, start, raw=b""):
        return dict(command_id=run["id"] + "-" + str(run["round"]) + "-" + str(seq),
            role=role, attempted=True, started=True, exit_observed=True, rc=0,
            timeout=False, termination_requested=False, deadline_met=True, pending=False,
            stdout=dict(eof=True, complete=True, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
            stderr=dict(eof=True, complete=True, bytes=0, sha256=empty_hash),
            start_mono_ns=start, start_boot_ns=start + 50_000_000_000,
            end_mono_ns=start + 30, end_boot_ns=start + 50_000_000_030,
            deadline_mono_ns=start + 100, deadline_boot_ns=start + 50_000_000_100)

    def observation(phase, seq, start, present, expected):
        value = dict(schema_version=1, target=target, expected_uid=60001 if expected else None,
            expected_gid=60001 if expected else None, classification="EXACT_PAIR" if present else "ABSENT_BOTH",
            complete=True, reason=None,
            sources=[dict(path=path, dev=1, ino=i + 1, size=10, mtime_ns=1, ctime_ns=1,
                          sha256="a" * 64) for i, path in enumerate(account.SOURCE_LIMITS)],
            providers=dict(passwd=["files"], group=["files"], initgroups=["files"]),
            identity=copy.deepcopy(identity) if present else None,
            group=dict(name=target, gid=60001, member_count=0) if present else None,
            conflicts=dict(uid_aliases=0, gid_aliases=0, other_primary_refs=0, group_members=0),
            nss_match=True, stable=True,
            clocks=dict(start_mono_ns=start + 10, end_mono_ns=start + 20,
                        start_boot_ns=start + 50_000_000_010, end_boot_ns=start + 50_000_000_020))
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
        return dict(phase=phase, audit=audit(phase, seq, start, raw), observation=value)

    setup = dict(schema_version=1, target=target, run_id=run["id"], round=run["round"],
        assumptions=copy.deepcopy(account.ASSUMPTIONS),
        tools=[dict(path=path, sha256="b" * 64, size=12, version=None,
                    version_basis="not_invoked", dev=1, ino=i + 1, mtime_ns=1, ctime_ns=1)
               for i, path in enumerate(account.TOOLS)],
        observations=[observation("pre_create", 1, 1000, False, False),
                      observation("post_create", 3, 3000, True, False),
                      observation("pre_cleanup", 4, 220_000_000_000, True, True),
                      observation("post_userdel", 6, 220_000_002_000, False, True)],
        create_command=audit("useradd", 2, 2000),
        observed_identity=copy.deepcopy(identity), admitted_identity=copy.deepcopy(identity),
        delete_commands=[audit("userdel", 5, 220_000_001_000)], cleanup_verified=True, failure=None)
    assert account.validate_account_setup(setup, run=run,
        fixture_account=report["provenance"]["fixture"]["account"], cleanup=report["cleanup"]) == []
    return setup


def retained_v2_report():
    report = retained_v2_envelope()
    continuation = v._support_module("continuation")
    source = report["source"]
    source["closure_sha256"].update({path: "b" * 64 for path in continuation.REQUIRED_SOURCE_PATHS})
    source["closure_sha256"].update(continuation.PINNED_DOCUMENTS)
    source["closure_sha256"].update(continuation.PINNED_FACTS)
    report["continuation"] = continuation.build_continuation(Path(__file__).resolve().parents[4],
        run=report["run"], source=source, provenance=report["provenance"], reason=continuation.ROUND2_REASON)
    report["account_setup"] = retained_account_setup(report)
    report["budget"]["diagnostic_bytes"] = v._account_facts(report)["diagnostic_bytes"]
    return seal_report_size(report)


def test_schema_two_full_pure_transcript_preserves_native_unknown_controls():
    report = retained_v2_report()
    before = copy.deepcopy(report)
    result = v.derive_report(v.load_report((json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()))
    assert result["errors"] == []
    assert result["status"] == "QUALIFIED_IN_FIXTURE"
    assert [r["classification"] for r in result["case_results"]] == [
        "OBSERVED", "OBSERVED", "UNKNOWN_RETAINED", "OBSERVED", "OBSERVED", "UNKNOWN_RETAINED"]
    assert all(r["case_expectation_met"] for r in result["case_results"])
    assert report == before


@pytest.mark.parametrize("where,field,value", [
    ("setup", "admitted_identity", None), ("setup", "run_id", "123"),
    ("setup", "cleanup_verified", False), ("create", "rc", 3),
    ("create", "rc", True), ("create", "exit_observed", False),
    ("create", "pending", True), ("create", "timeout", True),
    ("stdout", "eof", False), ("stdout", "complete", False),
    ("identity", "uid", 60002), ("identity", "home", "/home/other"),
])
def test_schema_two_native_work_requires_original_account_admission(where, field, value):
    report = retained_v2_report()
    setup = report["account_setup"]
    target = {"setup": setup, "create": setup["create_command"],
              "stdout": setup["create_command"]["stdout"], "identity": setup["admitted_identity"]}[where]
    target[field] = value
    seal_report_size(report)
    result = v.derive_report(report)
    assert result["status"] == "REJECTED"
    assert any("account_setup" in error for error in result["errors"])


@pytest.mark.parametrize("field", ["diagnostic_bytes", "prep_elapsed_seconds", "cleanup_elapsed_seconds"])
def test_schema_two_account_evidence_uses_the_existing_budget(field):
    report = retained_v2_report()
    report["budget"][field] = 0
    seal_report_size(report)
    result = v.derive_report(report)
    assert result["status"] == "REJECTED"
    assert any("account_setup" in error and "bill" in error for error in result["errors"])


@pytest.mark.parametrize("field,value", [
    ("used_before", 0), ("limit", 4), ("disposition", "CLEANED"),
    ("current_boot_sha256", "0" * 64), ("prior_boot_sha256", "0" * 64),
    ("approved_continuation_A", "0" * 40), ("closure_continuation_C", "0" * 40),
])
def test_schema_two_account_success_cannot_replace_continuation_evidence(field, value):
    report = retained_v2_report()
    report["continuation"][field] = value
    seal_report_size(report)
    result = v.derive_report(report)
    assert result["status"] == "REJECTED"
    assert any("continuation" in error for error in result["errors"])


def test_schema_two_cannot_rewrite_the_historical_unknown_as_cleanup_success():
    report = retained_v2_report()
    prior = report["continuation"]["prior_records"][0]
    value = json.loads(prior["content"])
    value["cleanup"]["verified"] = True
    prior["content"] = json.dumps(value, sort_keys=True, separators=(",", ":"))
    raw = prior["content"].encode()
    prior.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    report["source"]["closure_sha256"][prior["path"]] = prior["sha256"]
    seal_report_size(report)
    assert v.derive_report(report)["status"] == "REJECTED"


def test_schema_two_observed_but_unadmitted_account_remains_unknown():
    report = retained_v2_report()
    setup = report["account_setup"]
    setup["create_command"]["rc"] = 3
    setup.update(observations=setup["observations"][:2], admitted_identity=None,
                 delete_commands=[], cleanup_verified=False, failure="account_creation_not_confirmed")
    report.update(capability=None, cases=[], status="UNKNOWN_RETAINED",
                  reason="account_creation_not_confirmed",
                  cleanup=dict(verified=False, records=[], residuals=["dedicated-account"]))
    report["provenance"]["fixture"]["account"] = {}
    report["budget"]["diagnostic_bytes"] = v._account_facts(report)["diagnostic_bytes"]
    seal_report_size(report)
    result = v.derive_report(report)
    assert result == dict(status="UNKNOWN_RETAINED", errors=[], case_results=[])
    assert setup["observed_identity"] is not None and setup["admitted_identity"] is None
    report["cleanup"]["verified"] = True
    report["cleanup"]["residuals"] = []
    seal_report_size(report)
    assert any("outer cleanup hides account unknown" in error for error in v.validate_report(report))


@pytest.mark.parametrize("field", ["run", "provenance", "budget", "cleanup", "account_setup", "continuation"])
@pytest.mark.parametrize("value", [None, True, [], "missing"])
def test_schema_two_malformed_nested_evidence_fails_closed(field, value):
    report = retained_v2_report()
    report[field] = value
    if field != "budget":
        seal_report_size(report)
    assert v.derive_report(report)["status"] == "REJECTED"
