"""Human-specified offline transcripts, not a native producer or live evidence."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location("receipt_v3_test_" + name, Path(__file__).with_name(name + ".py"))
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


v = module("receipt_v3")
old = module("test_verify_receipt")
c = module("continuation_v2")
REPO = Path(__file__).resolve().parents[4]


def native_v2(original):
    r = copy.deepcopy(original)
    r.update(schema_version=2, generation=r["case_id"])
    events = []
    attempts = {1: 0, 2: 0}
    for event in r["events"]:
        if event["event"] in ("b_kill", "probe_kill", "t_cleanup"):
            actor = 1 if event["event"] == "b_kill" else 2
            reason = int(r["case_id"][1:]) if actor == 1 else 80 if r["kind"] == "probe" else 81
            attempts[actor] += 1
            for name, a, b, cc in (("kill_requested", actor, reason, attempts[actor]),
                                   ("kill_result", actor, attempts[actor], 0)):
                value = copy.deepcopy(event); value.update(event=name, a=a, b=b, c=cc)
                events.append(value)
        events.append(event)
    # C6's sole native collector cleanup is independently retained here.
    if r["case_id"] == "C6":
        e = copy.deepcopy(next(e for e in events if e["event"] == "t_g_exit"))
        for name, a, b, cc in (("kill_requested", 2, 81, 1), ("kill_result", 2, 1, 0), ("t_cleanup", 1, 0, 0)):
            value = copy.deepcopy(e); value.update(event=name, a=a, b=b, c=cc); events.append(value)
    for seq, event in enumerate(events, 1): event["seq"] = seq
    r["events"] = events
    return r


def retained_v3_report():
    r = old.retained_report()
    r.update(schema_version=3, run={"id": "39999999999", "attempt": 1, "round": 3},
             primary_failure=None, validation_errors={"items": [], "exceeded": False})
    r["provenance"].update(boot_id="33333333-3333-4333-8333-333333333333", kernel_version="#1 fixture")
    r["source"].update(approved_continuation_A=v.v.APPROVED_CONTINUATION_A,
                       closure_continuation_C=v.v.CLOSURE_CONTINUATION_C,
                       approved_r2_continuation_A=c.CONTINUATION_A, closure_r2_continuation_C=c.CONTINUATION_C)
    closure = r["source"]["closure_sha256"]
    closure.update({path: "b" * 64 for path in v.v.REQUIRED_CONTINUATION_SOURCE_PATHS | c.REQUIRED_SOURCE_PATHS | {v.v.SOURCE_DIR + "receipt_v3.py", v.v.SOURCE_DIR + "test_receipt_v3.py"}})
    closure.update({v.v.DOCUMENT_DIR + k: val for k, val in v.v.DOCUMENT_HASHES.items()})
    closure.update({v.v.CONTINUATION_DOCUMENT_DIR + k: val for k, val in v.v.CONTINUATION_DOCUMENT_HASHES.items()})
    closure.update(c.PINNED_DOCUMENTS); closure.update(c.PINNED_FACTS)
    r["capability"] = native_v2(r["capability"])
    r["cases"] = [native_v2(case) for case in r["cases"]]
    fixture = r["provenance"]["fixture"]
    e = dict(relative="E", role="E", dev=20, ino=1, creation_order=1, created_mono_ns=100, created_boot_ns=50_000_000_100,
             limits=copy.deepcopy(fixture["cgroup_objects"][0]["limits"]))
    history, observations, generations = [e], [], []
    for index, native in enumerate([r["capability"]] + r["cases"]):
        name = native["generation"]
        objects = []
        for offset, role in enumerate(("G", "B", "S", "W")):
            relative = ("G-" + name, "B-" + name, "B-" + name + "/S", "B-" + name + "/W")[offset]
            limits = {"memory.max": None, "memory.swap.max": None, "pids.max": None, "cpu.max": "max 100000"}
            if role in ("G", "B"):
                limits = {"memory.max": v.LIMITS[role + "_memory_bytes"], "memory.swap.max": 0, "pids.max": v.LIMITS[role + "_pids"], "cpu.max": v.LIMITS["cpu_max"]}
            objects.append(dict(relative=relative, role=role, dev=20, ino=2 + index * 4 + offset,
                creation_order=2 + index * 4 + offset, created_mono_ns=native["start_mono_ns"] - 100 + offset,
                created_boot_ns=native["start_boot_ns"] - 100 + offset, limits=limits))
        groups = [e] + objects
        history.extend(objects)
        for event_name, obj in zip(("e_identity", "g_identity", "b_identity", "s_identity", "w_identity"), groups):
            old.first(native, event_name).update(a=obj["dev"], b=obj["ino"])
        samples = {}
        for boundary in ("before", "after"):
            clock = "start" if boundary == "before" else "end"
            samples[boundary] = dict(generation=name, boundary=name + "-" + boundary,
                mono_ns=native[clock + "_mono_ns"] + (-20 if boundary == "before" else 20),
                boot_ns=native[clock + "_boot_ns"] + (-20 if boundary == "before" else 20),
                cgroups={obj["relative"]: dict(dev=obj["dev"], ino=obj["ino"], cpu_stat={"usage_usec": 10},
                    memory_current=0, memory_peak=100, pids_current=0, pids_peak=2,
                    memory_events={"oom_kill": 0}, pids_events={"max": 0}, populated=0) for obj in groups})
            observations.append(samples[boundary])
        retirement = dict(started_mono_ns=native["end_mono_ns"] + 30, started_boot_ns=native["end_boot_ns"] + 30,
                          end_mono_ns=native["end_mono_ns"] + 40, end_boot_ns=native["end_boot_ns"] + 40,
                          verified=True, failure=None, records=[])
        for role in ("S", "W", "B", "G"):
            obj = next(obj for obj in objects if obj["role"] == role)
            retirement["records"].append(dict(relative=obj["relative"], dev=obj["dev"], ino=obj["ino"], identity_match=True,
                empty=True, removed=True, fd_closed=True, mono_ns=native["end_mono_ns"] + 35, boot_ns=native["end_boot_ns"] + 35))
        phase_start = 1 if index == 0 else 30_000_000_000
        phase_limit = 120_000_000_000 if index == 0 else 180_000_000_000
        generations.append(dict(generation=name, sequence=index + 1, run=copy.deepcopy(r["run"]), state="RETIRED",
            window=dict(start_mono_ns=phase_start, start_boot_ns=phase_start + 50_000_000_000,
                        deadline_mono_ns=phase_start + phase_limit, deadline_boot_ns=phase_start + phase_limit + 50_000_000_000),
            e={k: e[k] for k in ("relative", "dev", "ino")}, objects=objects, before=samples["before"], after=samples["after"],
            helper=dict(exit_observed=True, rc=0 if native["status"] == "OBSERVED" else 3, stdout_eof=True, stderr_eof=True,
                        deadline_met=True, pending=False, started_mono_ns=native["start_mono_ns"] - 10,
                        started_boot_ns=native["start_boot_ns"] - 10, end_mono_ns=native["end_mono_ns"] + 10,
                        end_boot_ns=native["end_boot_ns"] + 10),
            native={k: native[k] for k in ("schema_version", "generation", "kind", "case_id")}, retirement=retirement))
    fixture["cgroup_objects"] = history; fixture["resource_observations"] = observations
    r["generations"] = generations
    r["cleanup"]["records"] = [dict(object=name, operation="rmdir", identity_match=True, removed=True) for name in
                                 ("q2-h07-39999999999-1-r3", "dedicated-account", "build/helper")]
    r["account_setup"] = old.retained_account_setup(r)
    r["budget"]["diagnostic_bytes"] = v.v._account_facts(r)["diagnostic_bytes"]
    r["budget"]["cases_elapsed_seconds"] = 180
    r["continuation"] = c.build_continuation(REPO, run=r["run"], source=r["source"], provenance=r["provenance"], reason=c.ROUND3_REASON)
    return old.seal_report_size(r)


def test_full_six_case_input_chain_uses_real_validators_and_preserves_negative_controls():
    report = retained_v3_report(); before = copy.deepcopy(report)
    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    result = old.v.derive_report(old.v.load_report(encoded))
    assert result["errors"] == []
    assert result["status"] == "QUALIFIED_IN_FIXTURE"
    assert result["evidence_basis"] == "INPUT_CONSISTENCY_ONLY"
    assert all(case["case_expectation_met"] for case in result["case_results"])
    assert [case["classification"] for case in result["case_results"]] == ["OBSERVED", "OBSERVED", "UNKNOWN_RETAINED", "OBSERVED", "OBSERVED", "UNKNOWN_RETAINED"]
    assert result["case_results"][2]["identity_complete"] is False
    assert result["case_results"][5]["identity_complete"] is None
    assert report == before


@pytest.mark.parametrize("case_id", v.GENERATIONS[1:])
def test_every_v2_case_positive_and_original_fact_loss(case_id):
    native = native_v2(old.retained_case(case_id))
    assert v.derive_case(native)["case_expectation_met"]
    for event in ("s_created", "s_armed", "s_credentials", "stream_originals", "t_g_exit", "t_cleanup_verified"):
        broken = copy.deepcopy(native); old.remove_event(broken, event)
        assert not v.derive_case(broken)["case_expectation_met"]


def early_exit_native(original=None):
    native = native_v2(old.retained_case("C1")) if original is None else copy.deepcopy(original)
    drop = {"s_armed", "s_credentials", "s_capabilities", "s_restrictions", "request_sent", "request_received",
            "worker_created", "worker_request", "worker_pidfd", "worker_identity", "worker_exit", "fenced"}
    native["events"] = [event for event in native["events"] if event["event"] not in drop]
    end = old.first(native, "s_exit")
    # Preserve independently recorded exit before the closure request.
    old.first(native, "close_requested").update(a=96)
    old.first(native, "kill_requested").update(b=96)
    for clock in ("mono_ns", "boot_ns"):
        end[clock] = old.first(native, "close_requested")[clock]
    diag = copy.deepcopy(end); diag.update(event="s_exit_before_arm", c=0)
    native["events"].append(diag)
    old.first(native, "g_summary").update(a=-1, b=0, c=1)
    for seq, event in enumerate(native["events"], 1): event["seq"] = seq
    native.update(status="UNKNOWN_RETAINED", reason="launcher_exit_before_arm")
    return native


def test_early_exit_has_unknown_identity_despite_empty_tree_and_zero_workers():
    native = early_exit_native()
    result = v.derive_case(native)
    assert result["errors"] == []
    assert result["classification"] == "UNKNOWN_RETAINED"
    assert result["identity_complete"] is None and not result["fence_observed"]
    assert not result["case_expectation_met"]
    native_before = copy.deepcopy(native)
    assert old.v.validate_native(native)  # Old native 1 API never promotes version 2.
    assert native == native_before


@pytest.mark.parametrize("field,value", [("a", 1), ("b", 1), ("c", -1), ("a", 2)])
def test_three_state_summary_cannot_fill_missing_original_facts(field, value):
    native = early_exit_native(); old.first(native, "g_summary")[field] = value
    assert v.derive_case(native)["errors"]


@pytest.mark.parametrize("mutation", ["wrong_generation", "kill_result_missing", "kill_replay", "kill_errno", "early_wait", "normal_close", "early_request", "arm_mask", "unknown_event"])
def test_new_diagnostics_are_bound_and_finite(mutation):
    n = early_exit_native()
    if mutation == "wrong_generation": n["generation"] = "C2"
    elif mutation == "kill_result_missing": old.remove_event(n, "kill_result")
    elif mutation == "kill_replay": old.first(n, "kill_requested")["c"] = 2
    elif mutation == "kill_errno": old.first(n, "kill_result")["c"] = 5000
    elif mutation == "early_wait": old.first(n, "s_exit_before_arm")["a"] = 0
    elif mutation == "normal_close": old.first(n, "close_requested")["a"] = 1
    elif mutation == "early_request": old.first(n, "s_exit_before_arm")["c"] = 1
    elif mutation == "arm_mask": old.first(n, "s_exit_before_arm").update(event="s_arm_rejected", a=1, b=255, c=255)
    elif mutation == "unknown_event": n["events"][0]["event"] = "invented_success"
    assert v.validate_native(n)


@pytest.mark.parametrize("mutation", ["generation_swap", "generation_repeat", "E_replaced", "alias", "wrong_resource", "old_fd", "missing_helper_eof", "helper_pending", "helper_exit", "unretired", "remove_fail", "fd_open", "nonempty", "retirement_order", "phase_refresh", "created_before_retirement", "extra_object", "reset_E", "weakened_caps", "wrong_account", "missing_native", "wrong_native_version", "report_extra", "round", "source", "kernel_bytes", "bill", "repeat_cleanup"])
def test_report_exact_joins_do_not_accept_summary_flags(mutation):
    r = retained_v3_report(); row = r["generations"][2]
    if mutation == "generation_swap": r["generations"][1:3] = reversed(r["generations"][1:3])
    elif mutation == "generation_repeat": row["generation"] = "C1"
    elif mutation == "E_replaced": row["e"]["ino"] = 99
    elif mutation == "alias": row["objects"][1]["ino"] = row["objects"][0]["ino"]
    elif mutation == "wrong_resource": row["before"]["generation"] = "C1"
    elif mutation == "old_fd": old.first(r["cases"][1], "g_identity")["b"] = 2
    elif mutation == "missing_helper_eof": row["helper"]["stderr_eof"] = False
    elif mutation == "helper_pending": row["helper"]["pending"] = True
    elif mutation == "helper_exit": row["helper"]["rc"] = 3
    elif mutation == "unretired": row["retirement"]["verified"] = False
    elif mutation == "remove_fail": row["retirement"]["records"][0]["removed"] = False
    elif mutation == "fd_open": row["retirement"]["records"][0]["fd_closed"] = False
    elif mutation == "nonempty": row["retirement"]["records"][0]["empty"] = False
    elif mutation == "retirement_order": row["retirement"]["records"].reverse()
    elif mutation == "phase_refresh": row["window"]["deadline_mono_ns"] += 1
    elif mutation == "created_before_retirement": row["objects"][0]["created_mono_ns"] = 30_000_000_000
    elif mutation == "extra_object": r["provenance"]["fixture"]["cgroup_objects"].append(copy.deepcopy(row["objects"][0]))
    elif mutation == "reset_E": row["before"]["cgroups"]["E"]["cpu_stat"]["usage_usec"] = 0
    elif mutation == "weakened_caps": row["objects"][0]["limits"]["pids.max"] = 40
    elif mutation == "wrong_account": r["provenance"]["fixture"]["account"]["uid"] = 60002
    elif mutation == "missing_native": r["cases"].pop()
    elif mutation == "wrong_native_version": r["cases"][0]["schema_version"] = 1
    elif mutation == "report_extra": r["previous_safe"] = True
    elif mutation == "round": r["run"]["round"] = 4
    elif mutation == "source": r["source"]["closure_r2_continuation_C"] = "d" * 40
    elif mutation == "kernel_bytes": r["provenance"]["kernel_version"] = "中" * 342
    elif mutation == "bill": r["budget"]["report_bytes"] = 1
    elif mutation == "repeat_cleanup": r["cleanup"]["records"].append(dict(object="q2-h07-39999999999-1-r3/G-C1", identity_match=True, removed=True))
    if mutation != "bill": old.seal_report_size(r)
    assert v.derive_report(r)["status"] == "REJECTED"


def test_old_contracts_and_original_inputs_are_not_migrated():
    for report in (old.retained_report(), old.retained_v2_report()):
        original = copy.deepcopy(report)
        assert old.v.derive_report(report)["status"] == "QUALIFIED_IN_FIXTURE"
        assert report == original
    for version in (True, 1, "3", 4, None):
        r = retained_v3_report(); r["schema_version"] = version; old.seal_report_size(r)
        assert old.v.derive_report(r)["status"] != "QUALIFIED_IN_FIXTURE"


def test_first_failure_and_later_errors_remain_separate_and_bounded():
    r = retained_v3_report()
    r.update(status="UNKNOWN_RETAINED", reason="first failure",
        primary_failure=dict(phase="validation", generation=None, code="REPORT_VALIDATION_FAILED", detail="first failure",
                             mono_ns=200_000_000_000, boot_ns=250_000_000_000, native_event=None))
    r["validation_errors"]["items"] = [dict(stage="report", code="INVALID_FACTS", detail="later error")]
    old.seal_report_size(r)
    before = copy.deepcopy(r)
    assert v.derive_report(r)["status"] == "UNKNOWN_RETAINED"
    assert r == before
    for mutate in (lambda x: x.update(reason=""), lambda x: x["primary_failure"].update(detail="中" * 171),
                   lambda x: x["validation_errors"].update(exceeded=True),
                   lambda x: x["validation_errors"].update(items=x["validation_errors"]["items"] * 17)):
        broken = copy.deepcopy(r); mutate(broken); old.seal_report_size(broken)
        assert v.derive_report(broken)["status"] == "REJECTED"

def truncate_after(report, count):
    """Retain a prefix of synthetic originals; never create a NOT_RUN success."""
    report["cases"] = report["cases"][:count]
    report["generations"] = report["generations"][:count + 1]
    report["provenance"]["fixture"]["cgroup_objects"] = report["provenance"]["fixture"]["cgroup_objects"][:1 + 4 * (count + 1)]
    report["provenance"]["fixture"]["resource_observations"] = report["provenance"]["fixture"]["resource_observations"][:2 * (count + 1)]


def test_v3_early_failure_is_retainable_without_promoting_missing_account_binding():
    r = retained_v3_report(); truncate_after(r, 1)
    n = early_exit_native(r["cases"][0]); r["cases"][0] = n
    r["generations"][1]["helper"]["rc"] = 3
    event = old.first(n, "s_exit_before_arm")
    r.update(status="UNKNOWN_RETAINED", reason="launcher exited before arm",
        primary_failure=dict(phase="cases", generation="C1", code="LAUNCHER_EXIT_BEFORE_ARM", detail="launcher exited before arm",
                             mono_ns=n["end_mono_ns"], boot_ns=n["end_boot_ns"], native_event={"generation": "C1", "seq": event["seq"]}))
    old.seal_report_size(r)
    result = v.derive_report(r)
    assert result["errors"] == []
    assert result["status"] == "UNKNOWN_RETAINED"
    assert result["case_results"][0]["identity_complete"] is None
    assert not result["case_results"][0]["case_expectation_met"]
    # A second original case following this failure is prohibited even after cleanup.
    full = retained_v3_report()
    r["cases"].append(full["cases"][1]); r["generations"].append(full["generations"][2])
    old.seal_report_size(r)
    assert v.derive_report(r)["status"] == "REJECTED"


def test_historical_inode_reuse_after_complete_retirement_is_not_an_alias():
    r = retained_v3_report(); row = r["generations"][2]
    former = r["generations"][1]["objects"]
    for obj, old_obj in zip(row["objects"], former):
        obj["ino"] = old_obj["ino"]
        for sample in (row["before"], row["after"]): sample["cgroups"][obj["relative"]]["ino"] = obj["ino"]
        for retirement in row["retirement"]["records"]:
            if retirement["relative"] == obj["relative"]: retirement["ino"] = obj["ino"]
    for event_name, obj in zip(("g_identity", "b_identity", "s_identity", "w_identity"), row["objects"]):
        old.first(r["cases"][1], event_name)["b"] = obj["ino"]
    old.seal_report_size(r)
    assert v.derive_report(r)["status"] == "QUALIFIED_IN_FIXTURE"


@pytest.mark.parametrize("mutation", ["birth_after_sample", "late_E", "creation_order_clock", "retirement_clock_order", "zero_case_bill", "zero_prep_bill"])
def test_actual_creation_retirement_and_phase_costs_must_be_causal(mutation):
    r = retained_v3_report(); row = r["generations"][1]
    if mutation == "birth_after_sample": row["objects"][0]["created_mono_ns"] = row["after"]["mono_ns"] + 100
    elif mutation == "late_E": r["provenance"]["fixture"]["cgroup_objects"][0]["created_boot_ns"] = row["after"]["boot_ns"]
    elif mutation == "creation_order_clock": row["objects"][1]["created_mono_ns"] = row["objects"][0]["created_mono_ns"] - 1
    elif mutation == "retirement_clock_order": row["retirement"]["records"][0]["boot_ns"] += 1
    elif mutation == "zero_case_bill": r["budget"]["cases_elapsed_seconds"] = 0
    elif mutation == "zero_prep_bill": r["budget"]["prep_elapsed_seconds"] = 0
    old.seal_report_size(r)
    assert v.derive_report(r)["status"] == "REJECTED"


def test_successful_kill_result_cannot_be_borrowed_for_two_effects_or_wrong_reason():
    n = native_v2(old.retained_probe())
    effect = copy.deepcopy(old.first(n, "probe_kill")); effect.update(event="t_cleanup", seq=len(n["events"]) + 1)
    n["events"].append(effect)
    assert v.validate_native(n)
    n = native_v2(old.retained_probe()); old.first(n, "kill_requested")["b"] = 1
    assert v.validate_native(n)


@pytest.mark.parametrize("bad", [None, [], 1, True, "native", {}, {"schema_version": 2, "generation": []}])
def test_public_pure_entry_points_return_closed_results_for_bad_values(bad):
    assert v.validate_native(bad)
    assert not v.derive_case(bad)["case_expectation_met"]
    assert not v.derive_capability(bad)["supported"]
    assert v.derive_report(bad)["status"] == "REJECTED"


def test_c5_inconclusive_is_retained_and_never_qualifies_last_round():
    r = retained_v3_report(); truncate_after(r, 5)
    old.first(r["cases"][-1], "burst_at_close")["a"] = 0
    r.update(status="INCONCLUSIVE", reason="burst prerequisite absent", primary_failure=dict(
        phase="cases", generation="C5", code="CASE_EXPECTATION_UNMET", detail="burst prerequisite absent",
        mono_ns=190_000_000_000, boot_ns=240_000_000_000, native_event=None))
    old.seal_report_size(r)
    result = v.derive_report(r)
    assert result["errors"] == [] and result["status"] == "INCONCLUSIVE"

def test_common_E_creation_is_charged_inside_original_preparation_phase():
    r = retained_v3_report()
    for clock in ("mono", "boot"): r["generations"][0]["window"][f"start_{clock}_ns"] += 10000
    old.seal_report_size(r)
    assert v.derive_report(r)["status"] == "REJECTED"


def test_arm_rejection_without_original_launcher_identity_is_not_retainable():
    n = early_exit_native()
    old.first(n, "s_exit_before_arm").update(event="s_arm_rejected", a=1, b=0, c=255)
    old.first(n, "close_requested")["a"] = 91
    old.first(n, "kill_requested")["b"] = 91
    n["reason"] = "launcher_arm_rejected"
    assert not v.validate_native(n)
    old.remove_event(n, "s_created")
    assert v.validate_native(n)


def test_partial_generation_creation_can_retain_failure_without_invented_limits_or_retirement():
    r = retained_v3_report(); truncate_after(r, 0)
    r["capability"] = None
    row = r["generations"][0]
    row.update(state="FAILED", before=None, after=None, helper=None, native=None)
    row["objects"] = row["objects"][:1]; row["objects"][0]["limits"] = None
    row["retirement"].update(verified=False, records=[], failure="setup incomplete")
    fixture = r["provenance"]["fixture"]
    fixture["resource_observations"] = []
    fixture["cgroup_objects"] = [fixture["cgroup_objects"][0]] + row["objects"]
    r["cleanup"].update(verified=False, records=[], residuals=["G-PROBE"])
    r.update(status="UNKNOWN_RETAINED", reason="setup incomplete", primary_failure=dict(phase="preparation", generation="PROBE",
        code="GENERATION_SETUP_FAILED", detail="setup incomplete", mono_ns=2_000_000_000, boot_ns=52_000_000_000, native_event=None))
    # Retained successful account deletion remains an independent account fact.
    # The original account validator requires its one registered cleanup record.
    r["cleanup"]["records"] = [dict(object="dedicated-account", identity_match=True, removed=True)]
    old.seal_report_size(r)
    result = v.derive_report(r)
    assert result["errors"] == [] and result["status"] == "UNKNOWN_RETAINED"

@pytest.mark.parametrize("clock", ["mono", "boot"])
def test_account_cleanup_follows_recorded_retirement_on_each_original_clock(clock):
    import hashlib

    r = retained_v3_report()
    setup = r["account_setup"]
    cleanup_observations = [o for o in setup["observations"] if o["phase"] in ("pre_cleanup", "post_userdel", "post_groupdel")]
    cleanup_audits = [o["audit"] for o in cleanup_observations] + setup["delete_commands"]
    retirement = r["generations"][-1]["retirement"]
    # Move the original account cleanup transcript to exactly the retirement
    # boundary, preserving each internal observation/capture duration and hash.
    for cclock in ("mono", "boot"):
        delta = retirement[f"end_{cclock}_ns"] - min(a[f"start_{cclock}_ns"] for a in cleanup_audits)
        if cclock == clock:
            delta -= 1  # Still after native exit; one original clock is too early.
        for audit in cleanup_audits:
            for prefix in ("start", "end", "deadline"):
                audit[f"{prefix}_{cclock}_ns"] += delta
        for observation in cleanup_observations:
            for prefix in ("start", "end"):
                observation["observation"]["clocks"][f"{prefix}_{cclock}_ns"] += delta
    for observation in cleanup_observations:
        raw = (json.dumps(observation["observation"], sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
        observation["audit"]["stdout"].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    account = v.v._support_module("account_evidence")
    assert account.validate_account_setup(setup, run=r["run"], fixture_account=r["provenance"]["fixture"]["account"], cleanup=r["cleanup"]) == []
    r["budget"]["diagnostic_bytes"] = v.v._account_facts(r)["diagnostic_bytes"]
    old.seal_report_size(r)
    result = v.derive_report(r)
    assert result["status"] == "REJECTED"
    assert result["errors"] == ["account cleanup preceded recorded generation retirement: " + clock]
    # The same original association is required when retirement reports failure.
    r["generations"][-1]["retirement"]["verified"] = False
    assert "account cleanup preceded recorded generation retirement: " + clock in v._bind_account_budget(r, account)
