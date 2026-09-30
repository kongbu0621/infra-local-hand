"""Pure data tests. Synthetic current identities are never dispatched."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("h07_v2_test", Path(__file__).with_name("continuation_v2.py"))
assert _spec and _spec.loader
v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2)
REPO = Path(__file__).resolve().parents[4]


def context():
    closure = {p: "a" * 64 for p in v2.REQUIRED_SOURCE_PATHS}
    closure.update(v2.PINNED_DOCUMENTS)
    closure.update(v2.PINNED_FACTS)
    source = {"expected_commit": "d" * 40, "github_sha": "d" * 40, "head": "d" * 40,
              "closure_sha256": closure, "approved_A": v2.legacy.APPROVED_A,
              "closure_C": v2.legacy.CLOSURE_C,
              "approved_continuation_A": v2.legacy.APPROVED_CONTINUATION_A,
              "closure_continuation_C": v2.legacy.CLOSURE_CONTINUATION_C,
              "approved_r2_continuation_A": v2.CONTINUATION_A,
              "closure_r2_continuation_C": v2.CONTINUATION_C}
    run = {"id": "39999999999", "attempt": 1, "round": 3}
    provenance = {"boot_id": "33333333-3333-4333-8333-333333333333"}
    value = v2.build_continuation(REPO, run=run, source=source, provenance=provenance,
                                  reason=v2.ROUND3_REASON)
    return value, run, source, provenance


def validate(ctx):
    value, run, source, provenance = ctx
    return v2.validate_continuation(value, run=run, source=source, provenance=provenance)


def test_exact_two_historical_failures_are_retained_without_reclassification():
    ctx = context()
    assert validate(ctx) == []
    records = [json.loads(row["content"]) for row in ctx[0]["prior_records"]]
    assert [r["status"] for r in records] == ["UNKNOWN_RETAINED", "UNKNOWN_RETAINED"]
    assert [r["cleanup"]["verified"] for r in records] == [False, True]
    assert records[1]["further_dispatch_blocked"] is True
    assert ctx[0]["used_before"] == 2 and ctx[0]["limit"] == 3


@pytest.mark.parametrize("change", [
    {"schema_version": True}, {"schema_version": 1}, {"schema_version": 3},
    {"used_before": 1}, {"limit": 4}, {"reason": "quota remains"},
    {"disposition": "ANY_UNKNOWN_ACCEPTED"}, {"prior_records": []},
    {"decision": "another-owner-decision"}, {"previous_safe": True},
])
def test_approval_versions_quota_and_reason_are_not_generalized(change):
    ctx = context(); ctx[0].update(change)
    assert validate(ctx)


@pytest.mark.parametrize("field,value", [("round", 2), ("round", 4), ("round", True),
                                         ("attempt", 2), ("attempt", True),
                                         ("id", v2.ROUND2_RUN_ID), ("id", v2.legacy.ROUND1_RUN_ID)])
def test_only_one_distinct_last_round_is_representable(field, value):
    ctx = context(); ctx[1][field] = value
    assert validate(ctx)


@pytest.mark.parametrize("path", sorted(v2.PINNED_DOCUMENTS | v2.PINNED_FACTS))
def test_every_immutable_source_pin_matters(path):
    ctx = context(); ctx[2]["closure_sha256"][path] = "0" * 64
    assert validate(ctx)


@pytest.mark.parametrize("index", [0, 1])
def test_self_consistent_changed_history_cannot_override_the_exact_byte_pin(index):
    ctx = context(); wrapper = ctx[0]["prior_records"][index]
    record = json.loads(wrapper["content"]); record["status"] = "REJECTED"
    wrapper["content"] = json.dumps(record)
    raw = wrapper["content"].encode()
    wrapper["bytes"] = len(raw); wrapper["sha256"] = hashlib.sha256(raw).hexdigest()
    ctx[2]["closure_sha256"][wrapper["path"]] = wrapper["sha256"]
    assert validate(ctx)


def test_history_order_and_cardinality_are_strict():
    ctx = context(); ctx[0]["prior_records"].reverse()
    assert validate(ctx)
    ctx = context(); ctx[0]["prior_records"].append(ctx[0]["prior_records"][1])
    assert validate(ctx)


@pytest.mark.parametrize("prior", [v2.ROUND2_BOOT_SHA256, v2.legacy.ROUND1_BOOT_SHA256])
def test_prior_boot_digest_still_rejects_after_exact_history_acceptance(monkeypatch, prior):
    ctx = context()
    monkeypatch.setattr(v2.legacy, "boot_sha256", lambda _: prior)
    ctx[0]["current_boot_sha256"] = prior
    assert validate(ctx)


@pytest.mark.parametrize("field", ["approved_A", "closure_C", "approved_continuation_A",
                                    "closure_continuation_C", "approved_r2_continuation_A",
                                    "closure_r2_continuation_C", "head"])
def test_all_authority_and_current_source_identities_are_required(field):
    ctx = context(); ctx[2][field] = "0" * 40
    assert validate(ctx)


def test_pins_match_committed_documents_and_new_owner_decision():
    for path, expected in {**v2.PINNED_DOCUMENTS, **v2.PINNED_FACTS}.items():
        assert hashlib.sha256((REPO / path).read_bytes()).hexdigest() == expected


def test_missing_second_index_remains_a_refusal(tmp_path):
    ctx = context(); first = tmp_path / v2.legacy.ROUND1_RECORD_PATH
    first.parent.mkdir(parents=True); first.write_bytes((REPO / v2.legacy.ROUND1_RECORD_PATH).read_bytes())
    with pytest.raises(ValueError, match="prior verification index"):
        v2.build_continuation(tmp_path, run=ctx[1], source=ctx[2], provenance=ctx[3], reason=v2.ROUND3_REASON)
