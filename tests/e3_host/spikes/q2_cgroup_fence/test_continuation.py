"""No-host-action tests of the sole historical exception and remaining quota."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location("h07_continuation_test", Path(__file__).with_name("continuation.py"))
assert SPEC and SPEC.loader
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)
REPO = Path(__file__).resolve().parents[4]
BOOT2 = "11111111-1111-4111-8111-111111111111"
BOOT3 = "22222222-2222-4222-8222-222222222222"


def round_two_context():
    """Synthetic current identity plus the actual frozen historical file bytes."""
    closure = {path: "a" * 64 for path in c.REQUIRED_SOURCE_PATHS}
    closure.update(c.PINNED_DOCUMENTS)
    closure.update(c.PINNED_FACTS)
    source = {"expected_commit": "d" * 40, "github_sha": "d" * 40, "head": "d" * 40,
              "approved_A": c.APPROVED_A, "closure_C": c.CLOSURE_C,
              "approved_continuation_A": c.APPROVED_CONTINUATION_A,
              "closure_continuation_C": c.CLOSURE_CONTINUATION_C,
              "closure_sha256": closure}
    run = {"id": "36599999999", "attempt": 1, "round": 2}
    provenance = {"boot_id": BOOT2}
    value = c.build_continuation(REPO, run=run, source=source, provenance=provenance,
                                 reason=c.ROUND2_REASON)
    return value, run, source, provenance


def validate(context):
    value, run, source, provenance = context
    return c.validate_continuation(value, run=run, source=source, provenance=provenance)


def test_only_the_exact_historical_unknown_is_accepted_and_unchanged():
    context = round_two_context()
    value, run, source, provenance = context
    assert validate(context) == []
    assert c.admit_continuation(REPO, run=run, source=source, provenance=provenance,
                                reason=c.ROUND2_REASON) == value
    original = json.loads(value["prior_records"][0]["content"])
    assert original["status"] == "UNKNOWN_RETAINED"
    assert original["cleanup"]["verified"] is False
    assert original["cases_executed"] == 0
    assert original["further_dispatch_blocked"] is True  # Historical statement is not rewritten.
    assert original["artifact"]["id"] == 11038133434
    assert value["used_before"] == 1 and value["limit"] == 3


@pytest.mark.parametrize("key", sorted(c.KEYS))
def test_missing_continuation_field_is_not_defaulted(key):
    context = round_two_context()
    del context[0][key]
    assert validate(context)


@pytest.mark.parametrize("mutation", [
    {"schema_version": True}, {"schema_version": 2}, {"used_before": True},
    {"used_before": 0}, {"limit": 4}, {"decision": "later-owner-event"},
    {"disposition": "CLEANED"}, {"reason": "There is still quota"},
    {"prior_records": []}, {"prior_boot_sha256": []}, {"prior_safe": True},
])
def test_summary_booleans_and_changed_authority_cannot_replace_history(mutation):
    context = round_two_context()
    context[0].update(mutation)
    assert validate(context)


@pytest.mark.parametrize("field,value", [("round", 1), ("round", 4), ("round", True),
                                         ("attempt", 2), ("attempt", True),
                                         ("id", c.ROUND1_RUN_ID)])
def test_no_round_reset_rerun_or_historical_run_reuse(field, value):
    context = round_two_context()
    context[1][field] = value
    assert validate(context)


@pytest.mark.parametrize("field", ["approved_A", "closure_C", "approved_continuation_A",
                                    "closure_continuation_C", "head"])
def test_both_old_and_new_source_authorities_are_bound(field):
    context = round_two_context()
    context[2][field] = "0" * 40
    assert validate(context)


@pytest.mark.parametrize("path", sorted(c.PINNED_DOCUMENTS | c.PINNED_FACTS))
def test_each_document_and_historical_record_requires_original_bytes(path):
    context = round_two_context()
    context[2]["closure_sha256"][path] = "0" * 64
    assert validate(context)


def test_even_a_self_consistent_edited_historical_index_cannot_change_cleanup():
    context = round_two_context()
    wrapper = context[0]["prior_records"][0]
    original = json.loads(wrapper["content"])
    original["cleanup"]["verified"] = True
    wrapper["content"] = json.dumps(original)
    wrapper["bytes"] = len(wrapper["content"].encode())
    wrapper["sha256"] = hashlib.sha256(wrapper["content"].encode()).hexdigest()
    context[2]["closure_sha256"][c.ROUND1_RECORD_PATH] = wrapper["sha256"]
    assert validate(context)


@pytest.mark.parametrize("field,value", [("bytes", True), ("sha256", "0" * 64),
                                         ("path", "round-one.json"), ("content", "{}")])
def test_prior_wrapper_cannot_redirect_or_drop_original_bytes(field, value):
    context = round_two_context()
    context[0]["prior_records"][0][field] = value
    assert validate(context)


@pytest.mark.parametrize("boot", [None, "", "1" * 32, BOOT2 + "\n", BOOT2.upper().replace("1", "A", 1)])
def test_unavailable_or_noncanonical_boot_refuses(boot):
    context = round_two_context()
    context[3]["boot_id"] = boot
    assert validate(context)


def test_first_round_boot_cannot_be_reused(monkeypatch):
    context = round_two_context()
    monkeypatch.setattr(c, "boot_sha256", lambda _: c.ROUND1_BOOT_SHA256)
    context[0]["current_boot_sha256"] = c.ROUND1_BOOT_SHA256
    assert any("boot reuse" in message for message in validate(context))


def test_third_round_currently_lacks_second_round_original_and_must_refuse():
    value, run, source, provenance = round_two_context()
    run["round"] = 3
    assert not (REPO / c.ROUND2_RECORD_PATH).exists()
    with pytest.raises(c.ContinuationError, match="prior verification index"):
        c.admit_continuation(REPO, run=run, source=source, provenance=provenance,
                             reason="Another independently verified source defect")
    value["used_before"] = 2
    assert c.validate_continuation(value, run=run, source=source, provenance=provenance)


def future_index(context, status="REJECTED"):
    """Synthetic future index; policy tests independently stub receipt derivation.

    This is not a real round-two record, a successful kernel test, or permission
    to dispatch. Integration receipt tests exercise the real schema-2 validator.
    """
    _, run, source, _ = context
    path = "tests/e3_host/spikes/q2_cgroup_fence/run_fixture.py"
    source["closure_sha256"][path] = "b" * 64
    previous_source = copy.deepcopy(source)
    previous_source["closure_sha256"][path] = "a" * 64
    report = {"schema_version": 2, "run": copy.deepcopy(run), "source": previous_source,
              "status": status, "cleanup": {"verified": True}, "capability": None,
              "provenance": {"boot_id": BOOT2}}
    raw = json.dumps(report)
    record = {"schema_version": 2, "execution_kind": "real_hosted_lab_round_review",
              "run": copy.deepcopy(run), "artifact": {"id": 11049999999,
                  "sha256": "c" * 64, "report_sha256": hashlib.sha256(raw.encode()).hexdigest()},
              "original_report": raw, "lab_dispatches_consumed": 2, "lab_dispatches_limit": 3,
              "workflow_runs": [{"id": c.ROUND1_RUN_ID, "attempt": 1, "round": 1}, copy.deepcopy(run)],
              "next_repair": {"reason": "Fix independently identified source defect", "defect": "Recorded deterministic fixture source defect",
                  "commit": "e" * 40, "changed_source_sha256": {path: {"before": "a" * 64, "after": "b" * 64}},
                  "offline_checks": [{"command": "python -m pytest targeted_tests", "exit_code": 0,
                                      "log_sha256": "f" * 64}],
                  "ordinary_ci": {"id": "36600000001", "attempt": 1, "head_sha": "e" * 40,
                                  "conclusion": "success"}}}
    return record


def round_three_context(monkeypatch, status="REJECTED"):
    context = round_two_context()
    value, run, source, provenance = context
    record = future_index(context, status)
    monkeypatch.setattr(c, "_receipt_verifier", lambda: SimpleNamespace(
        derive_report=lambda report: {"status": report["status"], "errors": [], "case_results": []}))
    raw = json.dumps(record)
    sha = hashlib.sha256(raw.encode()).hexdigest()
    source["closure_sha256"][c.ROUND2_RECORD_PATH] = sha
    value["prior_records"].append({"path": c.ROUND2_RECORD_PATH, "sha256": sha,
                                    "bytes": len(raw.encode()), "content": raw})
    value.update(used_before=2, prior_boot_sha256=[c.ROUND1_BOOT_SHA256, c.boot_sha256(BOOT2)],
                 current_boot_sha256=c.boot_sha256(BOOT3), reason=record["next_repair"]["reason"])
    run.update(id="36611111111", round=3)
    provenance["boot_id"] = BOOT3
    return context


def test_future_index_must_bind_original_receipt_and_actual_repaired_source(monkeypatch):
    context = round_three_context(monkeypatch)
    assert validate(context) == []
    context[2]["closure_sha256"]["tests/e3_host/spikes/q2_cgroup_fence/run_fixture.py"] = "0" * 64
    assert validate(context)


@pytest.mark.parametrize("status", ["UNKNOWN_RETAINED", "UNSUPPORTED", "QUALIFIED_IN_FIXTURE", "INCONCLUSIVE"])
def test_new_unknown_unsupported_or_success_cannot_inherit_historical_exception(monkeypatch, status):
    assert validate(round_three_context(monkeypatch, status))


def test_second_round_boot_reuse_refuses_even_with_complete_source_bound_index(monkeypatch):
    context = round_three_context(monkeypatch)
    context[3]["boot_id"] = BOOT2
    context[0]["current_boot_sha256"] = c.boot_sha256(BOOT2)
    assert any("boot reuse" in message for message in validate(context))


def test_current_round_three_cannot_use_uncommitted_or_arbitrary_previous_safe_input(monkeypatch):
    context = round_three_context(monkeypatch)
    del context[2]["closure_sha256"][c.ROUND2_RECORD_PATH]
    assert validate(context)
    context = round_three_context(monkeypatch)
    context[0]["prior_records"][1] = {"previous_safe": True, "cleanup_verified": True}
    assert validate(context)


def test_real_prior_receipt_validator_does_not_accept_a_summary_as_a_report():
    context = round_two_context()
    record = future_index(context)
    with pytest.raises(c.ContinuationError, match="blocking result"):
        c._round2(record, context[2], record["next_repair"]["reason"])


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"a":NaN}', '[]', '{"a":' + '[' * 30 + '0' + ']' * 30 + '}'])
def test_prior_json_is_strict_and_bounded(raw):
    with pytest.raises(c.ContinuationError):
        c._json(raw)


def test_workflow_keeps_manual_fixed_vm_attempt_and_new_ancestor_contract():
    text = (REPO / ".github/workflows/q2-cgroup-fence-spike.yml").read_text()
    assert 'options: ["2", "3"]' in text
    assert "runs-on: ubuntu-24.04" in text
    assert "  workflow_dispatch:" in text
    assert "  push:" not in text and "  schedule:" not in text and "container:" not in text
    assert 'GITHUB_RUN_ATTEMPT"] == "1"' in text
    assert c.CLOSURE_CONTINUATION_C in text
    assert "continuation.admit_continuation(" in text
    assert "cancel-in-progress: false" in text
