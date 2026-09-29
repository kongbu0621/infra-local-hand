"""Independent, synthetic byte-only cost-reference counterexamples.

These tests establish a bounded consistency contract, never an adopted source,
host observation, bill, release, or permission to consume the Q2 window.
"""

import builtins
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess

import pytest

from e3_host import q2_cost_source_review as m


SCHEMA = "local-hand-q2-cost-source-claims/v1"
MAX_INT = (1 << 63) - 1
FALSE_FIELDS = (
    "source_adoption_proven", "observation_completion_proven",
    "baseline_parent_cost_proven", "full_bill_proven", "filesystem_proven",
    "field_ready", "q2_accepted", "allow_consume", "allow_run",
    "marker_pool_adjustment_performed",
)
POINTER_FIELDS = (
    "metadata_pointer", "machine_pointer", "boot_pointer", "path_pointer",
    "phase_pointer",
)


def encoded(value):
    """Fixture encoder deliberately independent of the implementation."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_row(source_id, raw):
    return {"id": source_id, "sha256": sha(raw), "bytes": len(raw)}


def object_claim(object_id="ordinary", source_id="receipt", pointer="/items/0"):
    return {
        "id": object_id, "source": source_id,
        "metadata_pointer": pointer + "/before",
        "machine_pointer": "/machine", "boot_pointer": "/boot",
        "path_pointer": pointer + "/path", "phase_pointer": "/phase",
        "role_claim": "ordinary", "category_claim": "capture",
        "evidence": [{"source": source_id, "pointer": "/evidence"}],
    }


def obligation_claim(obligation_id="historical", source_id="receipt"):
    return {
        "id": obligation_id, "source": source_id,
        "commitment_pointer": "/commitments/historical",
        "kind_claim": "historical", "category_claim": "capture",
        "evidence": [{"source": source_id, "pointer": "/evidence"}],
    }


def relation_claim(relation_id="coverage", kind="coverage", object_ids=None,
                   obligation_id="historical"):
    return {
        "id": relation_id, "kind": kind,
        "object_ids": ["ordinary"] if object_ids is None else object_ids,
        "obligation_id": obligation_id,
        "evidence": [{"source": "receipt", "pointer": "/evidence"}],
    }


def fixture():
    document = {
        "machine": "synthetic-machine", "boot": "synthetic-boot",
        "phase": {"status": "OBSERVED_PARTIAL", "failed_at": "open"},
        "items": [
            {"path": "/synthetic-q2-cost/capture/payload",
             "before": {"device": 11, "inode": 101, "blocks": 8,
                        "mode": 0o100664, "untrusted_extra": "retained-source-only"}},
            {"path": "/synthetic-q2-cost/capture/second",
             "before": {"device": 11, "inode": 102, "blocks": 16}},
            {"path": "/synthetic-q2-cost/capture",
             "before": {"device": 11, "inode": 100, "blocks": 24}},
        ],
        "commitments": {
            "historical": {"bytes": 16384, "inodes": 2},
            "marker": {"bytes": 65536, "inodes": 4},
        },
        "evidence": {"claim": "synthetic-original-field", "M": 4096,
                     "G": 8192, "B": 12288, "already_billed": 12288},
        "null": None,
        "escapes": {"a/b": {"~key": [{"device": 13, "inode": 7, "blocks": 3}]}},
    }
    raw = encoded(document)
    manifest = {
        "schema": SCHEMA, "sources": [source_row("receipt", raw)],
        "objects": [object_claim()], "obligations": [obligation_claim()],
        "relations": [relation_claim()],
    }
    return document, manifest, {"receipt": raw}


def repin(manifest, sources, source_id, document):
    sources[source_id] = encoded(document)
    row = next(row for row in manifest["sources"] if row["id"] == source_id)
    row.update(sha256=sha(sources[source_id]), bytes=len(sources[source_id]))


def review(manifest, sources):
    return m.review_cost_sources(encoded(manifest), sources)


def row(result, collection, item_id):
    return next(item for item in result[collection] if item["id"] == item_id)


def codes(result):
    return {item["code"] for item in result["diagnostics"]}


def assert_no_authority(result):
    assert result["schema"] == "local-hand-q2-cost-source-review/v1"
    assert result["status"] == "CLAIMS_REVIEWED"
    for key in FALSE_FIELDS:
        assert result[key] is False, key
    for item in result["objects"]:
        assert item["observation_completion_proven"] is False
        assert item["identity_and_amount_same_observation_proven"] is False
        assert item["category_proven"] is False
        assert item["status"] == "REFERENCED_NOT_OBSERVATION_VERIFIED"
    for item in result["source_groups"]:
        assert item["observation_epoch_proven"] is False
        assert item["subtotal_eligible_as_observation"] is False
    for item in result["relations"]:
        assert item["coverage_proven"] is False
        assert item["credit_applied"] is False
    for item in result["obligations"]:
        assert item["release_applied"] is False
        assert item["unspent"] is None


def test_partial_before_stat_is_an_exact_reference_never_an_actual_observation():
    document, manifest, sources = fixture()
    result = review(manifest, sources)
    item = row(result, "objects", "ordinary")
    assert item["metadata"] == {"device": 11, "inode": 101, "blocks": 8}
    assert item["referenced_allocated_bytes"] == 4096
    assert item["source_sha256"] == sha(sources["receipt"])
    assert result["manifest_sha256"] == sha(encoded(manifest))
    assert item["refs"]["metadata"] == {
        "source_sha256": sha(sources["receipt"]),
        "pointer": "/items/0/before",
        "value_sha256": sha(encoded(document["items"][0]["before"])),
    }
    assert item["refs"]["phase"]["value_sha256"] == sha(encoded(document["phase"]))
    assert item["machine"] == document["machine"]
    assert item["boot"] == document["boot"]
    assert item["path"] == document["items"][0]["path"]
    assert item["role_claim"] == "ordinary"
    assert item["category_claim"] == "capture"
    assert result["source_groups"][0]["referenced_endpoint_sum_bytes"] == 4096
    assert_no_authority(result)


@pytest.mark.parametrize("phase", ["SUCCESS", {"complete": True, "status": "SUCCESS"}])
def test_caller_completion_word_or_phase_value_never_proves_observation(phase):
    document, manifest, sources = fixture()
    document["phase"] = phase
    repin(manifest, sources, "receipt", document)
    assert_no_authority(review(manifest, sources))


def test_single_container_may_hold_multiple_times_and_never_proves_an_epoch():
    document, manifest, sources = fixture()
    document["items"][0]["phase"] = {"time": 10, "status": "SUCCESS"}
    document["items"][1]["phase"] = {"time": 99, "status": "SUCCESS"}
    manifest["objects"].append(object_claim("later", pointer="/items/1"))
    manifest["objects"][0]["phase_pointer"] = "/items/0/phase"
    manifest["objects"][1]["phase_pointer"] = "/items/1/phase"
    repin(manifest, sources, "receipt", document)
    result = review(manifest, sources)
    assert len(result["source_groups"]) == 1
    assert result["source_groups"][0]["referenced_endpoint_sum_bytes"] == 12288
    assert_no_authority(result)


@pytest.mark.parametrize("pointer_field,unknown_pointer", [("metadata_pointer", None), ("machine_pointer", "/null"), ("phase_pointer", None)])
def test_null_reference_remains_unknown_without_fabricated_completion(pointer_field, unknown_pointer):
    _, manifest, sources = fixture()
    manifest["objects"][0][pointer_field] = unknown_pointer
    result = review(manifest, sources)
    item = row(result, "objects", "ordinary")
    if pointer_field != "phase_pointer":
        output_key = pointer_field.removesuffix("_pointer")
        assert item[output_key] is None
    if pointer_field == "metadata_pointer":
        assert item["referenced_allocated_bytes"] is None
    if pointer_field in ("metadata_pointer", "machine_pointer", "boot_pointer"):
        assert result["source_groups"][0]["referenced_endpoint_sum_bytes"] is None
        assert result["source_groups"][0]["unresolved"]
    assert_no_authority(result)


def test_unknown_allocation_is_distinct_from_explicit_zero_blocks():
    document, manifest, sources = fixture()
    document["items"][0]["before"]["blocks"] = 0
    repin(manifest, sources, "receipt", document)
    zero = review(manifest, sources)
    assert row(zero, "objects", "ordinary")["referenced_allocated_bytes"] == 0
    manifest["objects"][0]["metadata_pointer"] = None
    unknown = review(manifest, sources)
    assert row(unknown, "objects", "ordinary")["referenced_allocated_bytes"] is None
    assert unknown["source_groups"][0]["referenced_endpoint_sum_bytes"] is None


def test_no_selected_objects_does_not_manufacture_zero_inventory():
    _, manifest, sources = fixture()
    manifest["objects"] = []
    manifest["relations"] = []
    result = review(manifest, sources)
    assert not result["objects"]
    assert all(group["referenced_endpoint_sum_bytes"] is None
               for group in result["source_groups"])
    assert_no_authority(result)


@pytest.mark.parametrize("bad_pin", ["digest", "length"])
def test_all_sources_are_pinned_before_any_source_is_decoded(bad_pin):
    _, manifest, _ = fixture()
    sources = {"receipt": b"{malformed first source", "later": b"{}"}
    manifest["sources"] = [source_row(key, raw) for key, raw in sources.items()]
    manifest["sources"][1]["sha256" if bad_pin == "digest" else "bytes"] = (
        "0" * 64 if bad_pin == "digest" else 3)
    with pytest.raises(ValueError, match="^COST_SOURCE_SOURCE_PIN"):
        review(manifest, sources)


@pytest.mark.parametrize("change", [lambda manifest, sources: sources.pop("receipt"), lambda manifest, sources: sources.update(receipt=sources["receipt"] + b" ")])
def test_sources_are_exactly_declared_and_bound_to_original_bytes(change):
    _, manifest, sources = fixture()
    change(manifest, sources)
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


@pytest.mark.parametrize("raw", [b'{"nested":{"x":0,"x":1}}', b'{"n":1.0}', b'{"n":NaN}', b'{"n":9223372036854775808}', b'{"n":"\\ud800"}'])
def test_strict_json_applies_even_to_unreferenced_source_fields(raw):
    _, manifest, _ = fixture()
    manifest["sources"] = [source_row("receipt", raw)]
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, {"receipt": raw})


def test_manifest_duplicate_keys_and_non_integer_numbers_are_rejected():
    suffix = b',"schema":"' + SCHEMA.encode() + b'"}'
    _, manifest, sources = fixture()
    raw = encoded(manifest).rstrip()[:-1] + suffix
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        m.review_cost_sources(raw, sources)


@pytest.mark.parametrize("collection,extra", [(None, "limits"), ("objects", "epoch"), ("relations", "release"), ("obligations", "amount")])
def test_exact_schema_rejects_authority_amount_growth_release_and_limit_overrides(collection, extra):
    _, manifest, sources = fixture()
    target = manifest if collection is None else manifest[collection][0]
    target[extra] = True
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_duplicate_logical_ids_are_rejected():
    collection = "sources"
    _, manifest, sources = fixture()
    manifest[collection].append(copy.deepcopy(manifest[collection][0]))
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_missing_required_fields_are_rejected():
    collection = "objects"
    _, manifest, sources = fixture()
    target = manifest if collection is None else manifest[collection][0]
    for key in tuple(target):
        candidate = copy.deepcopy(manifest)
        selected = candidate if collection is None else candidate[collection][0]
        del selected[key]
        with pytest.raises(ValueError, match="^COST_SOURCE_"):
            review(candidate, sources)


@pytest.mark.parametrize("pointer", ["/items/00/before", "/escapes/a~2b", "/absent"])
def test_strict_pointer_rejects_invalid_escapes_indices_and_missing_targets(pointer):
    _, manifest, sources = fixture()
    manifest["objects"][0]["metadata_pointer"] = pointer
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_pointer_root_empty_keys_escaped_slash_tilde_and_array_zero_are_supported():
    document, manifest, sources = fixture()
    document[""] = {"device": 17, "inode": 8, "blocks": 1}
    repin(manifest, sources, "receipt", document)
    manifest["objects"][0]["metadata_pointer"] = "/escapes/a~1b/~0key/0"
    manifest["objects"][0]["evidence"] = [{"source": "receipt", "pointer": ""}]
    result = review(manifest, sources)
    assert row(result, "objects", "ordinary")["referenced_allocated_bytes"] == 1536
    manifest["objects"][0]["metadata_pointer"] = "/"
    assert row(review(manifest, sources), "objects", "ordinary")[
        "referenced_allocated_bytes"] == 512


def test_evidence_pointer_must_be_nonnull_string_and_resolve():
    bad = None
    _, manifest, sources = fixture()
    manifest["objects"][0]["evidence"] = [{"source": "receipt", "pointer": bad}]
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_metadata_requires_exact_integer_types_and_ranges():
    field,values = ("blocks", [False, -1, "8"])
    for value in values:
        document, manifest, sources = fixture()
        document["items"][0]["before"][field] = value
        repin(manifest, sources, "receipt", document)
        with pytest.raises(ValueError, match="^COST_SOURCE_"):
            review(manifest, sources)


def test_partial_metadata_cannot_be_completed_with_zero():
    field = "blocks"
    document, manifest, sources = fixture()
    del document["items"][0]["before"][field]
    repin(manifest, sources, "receipt", document)
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)

    document["items"][0]["before"][field] = None
    repin(manifest, sources, "receipt", document)
    result = review(manifest, sources)
    assert row(result, "objects", "ordinary")["metadata"][field] is None
    assert row(result, "objects", "ordinary")["referenced_allocated_bytes"] is None
    assert result["source_groups"][0]["referenced_endpoint_sum_bytes"] is None


@pytest.mark.parametrize("pointer_field,value", [("machine_pointer", True), ("path_pointer", "x" * 8193)])
def test_identity_and_path_values_are_nonempty_bounded_strings(pointer_field, value):
    document, manifest, sources = fixture()
    document["bad"] = value
    manifest["objects"][0][pointer_field] = "/bad"
    repin(manifest, sources, "receipt", document)
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


@pytest.mark.parametrize("path", ["relative/path", "/x/../y"])
def test_path_comparison_requires_canonical_absolute_paths(path):
    document, manifest, sources = fixture()
    document["items"][0]["path"] = path
    repin(manifest, sources, "receipt", document)
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_object_enums_and_source_reference_are_closed():
    key,value = ("role_claim", "actual")
    _, manifest, sources = fixture()
    manifest["objects"][0][key] = value
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


@pytest.mark.parametrize("collection,key,value", [("relations", "kind", "growth"), ("relations", "object_ids", ["ordinary", "ordinary"])])
def test_obligation_and_relation_schema_reject_unsupported_claims(collection, key, value):
    _, manifest, sources = fixture()
    manifest[collection][0][key] = value
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


@pytest.mark.parametrize("key,value", [("bytes", True), ("extra", 0)])
def test_commitment_is_exact_nonnegative_integer_pair(key, value):
    document, manifest, sources = fixture()
    document["commitments"]["historical"][key] = value
    repin(manifest, sources, "receipt", document)
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_marker_claim_requires_exact_original_64k_four_inode_commitment():
    key,value = ("bytes", 65535)
    document, manifest, sources = fixture()
    manifest["obligations"][0].update(kind_claim="marker",
                                      commitment_pointer="/commitments/marker")
    document["commitments"]["marker"][key] = value
    repin(manifest, sources, "receipt", document)
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_unknown_marker_commitment_never_becomes_zero_or_released():
    pointer = None
    _, manifest, sources = fixture()
    manifest["obligations"][0].update(kind_claim="marker", commitment_pointer=pointer)
    result = review(manifest, sources)
    assert row(result, "obligations", "historical")["referenced_commitment"] is None
    assert_no_authority(result)


def test_original_marker_m_plus_g_reference_cannot_apply_growth_twice_or_release():
    _, manifest, sources = fixture()
    manifest["objects"][0]["role_claim"] = "marker_subtree"
    manifest["obligations"][0].update(kind_claim="marker",
                                      commitment_pointer="/commitments/marker")
    manifest["relations"][0]["kind"] = "credit"
    result = review(manifest, sources)
    assert row(result, "objects", "ordinary")["referenced_allocated_bytes"] == 4096
    assert row(result, "obligations", "historical")["referenced_commitment"] == {
        "bytes": 65536, "inodes": 4}
    assert_no_authority(result)


def two_objects(document=None):
    source_document, manifest, sources = fixture()
    if document is not None:
        source_document = document
    manifest["objects"].append(object_claim("second", pointer="/items/1"))
    repin(manifest, sources, "receipt", source_document)
    return source_document, manifest, sources


def test_same_source_valid_subtotal_is_only_the_selected_endpoints():
    _, manifest, sources = two_objects()
    result = review(manifest, sources)
    assert result["source_groups"][0]["referenced_endpoint_sum_bytes"] == 12288
    assert set(result["source_groups"][0]["object_ids"]) == {"ordinary", "second"}
    assert_no_authority(result)


def test_same_source_physical_alias_is_diagnostic_and_has_no_subtotal():
    same_path = False
    document, manifest, sources = two_objects()
    document["items"][1]["before"] = copy.deepcopy(document["items"][0]["before"])
    if same_path:
        document["items"][1]["path"] = document["items"][0]["path"]
    repin(manifest, sources, "receipt", document)
    result = review(manifest, sources)
    assert "PHYSICAL_ALIAS" in codes(result)
    assert result["source_groups"][0]["referenced_endpoint_sum_bytes"] is None
    assert result["source_groups"][0]["unresolved"]
    assert_no_authority(result)


def test_same_path_different_inode_is_conflict_and_never_summed():
    document, manifest, sources = two_objects()
    document["items"][1]["path"] = document["items"][0]["path"]
    repin(manifest, sources, "receipt", document)
    result = review(manifest, sources)
    assert "PATH_IDENTITY_CONFLICT" in codes(result)
    assert result["source_groups"][0]["referenced_endpoint_sum_bytes"] is None


def test_physical_identity_never_omits_machine_boot_device_or_inode():
    for difference in ["machine", "boot", "device", "inode"]:
        document, manifest, sources = two_objects()
        document["items"][1]["before"] = copy.deepcopy(document["items"][0]["before"])
        if difference in ("device", "inode"):
            document["items"][1]["before"][difference] += 1
        else:
            document["other_identity"] = "different-" + difference
            manifest["objects"][1][difference + "_pointer"] = "/other_identity"
        repin(manifest, sources, "receipt", document)
        result = review(manifest, sources)
        assert "PHYSICAL_ALIAS" not in codes(result)
        assert result["source_groups"][0]["referenced_endpoint_sum_bytes"] == 8192
        assert_no_authority(result)


def test_path_ancestry_does_not_expand_relation_to_unselected_descendant():
    _, manifest, sources = fixture()
    parent = object_claim("parent", pointer="/items/2")
    parent["role_claim"] = "parent_baseline"
    manifest["objects"].append(parent)
    manifest["relations"][0]["object_ids"] = ["parent"]
    result = review(manifest, sources)
    assert {"PATH_ANCESTRY", "PARENT_BASELINE_UNPROVEN"} <= codes(result)
    assert row(result, "relations", "coverage")["object_ids"] == ["parent"]
    assert_no_authority(result)


def add_second_source(manifest, sources, *, same_bytes=False):
    raw = sources["receipt"] if same_bytes else sources["receipt"] + b" "
    sources["receipt_two"] = raw
    manifest["sources"].append(source_row("receipt_two", raw))
    manifest["objects"].append(object_claim("other_receipt", "receipt_two"))


def test_source_ids_do_not_split_identical_original_bytes_into_independent_groups():
    _, manifest, sources = fixture()
    add_second_source(manifest, sources, same_bytes=True)
    result = review(manifest, sources)
    assert len(result["source_groups"]) == 1
    assert result["source_groups"][0]["source_sha256"] == sha(sources["receipt"])
    assert "PHYSICAL_ALIAS" in codes(result)
    assert result["source_groups"][0]["referenced_endpoint_sum_bytes"] is None


def test_distinct_raw_receipts_never_merge_even_when_decoded_json_is_identical():
    _, manifest, sources = fixture()
    add_second_source(manifest, sources)
    result = review(manifest, sources)
    assert len(result["source_groups"]) == 2
    assert {group["source_sha256"] for group in result["source_groups"]} == {
        sha(raw) for raw in sources.values()}
    assert "CROSS_RECEIPT_IDENTITY" in codes(result)
    assert "referenced_endpoint_sum_bytes" not in result
    assert "actual" not in result and "total_actual_bytes" not in result
    assert_no_authority(result)


@pytest.mark.parametrize("alias", [False, True])
def test_credit_reuse_by_object_or_complete_physical_alias_is_conflict(alias):
    document, manifest, sources = two_objects()
    if alias:
        document["items"][1]["before"] = copy.deepcopy(document["items"][0]["before"])
        repin(manifest, sources, "receipt", document)
    manifest["obligations"].append(obligation_claim("other_obligation"))
    manifest["relations"] = [relation_claim("first_credit", "credit"),
        relation_claim("second_credit", "credit", ["second" if alias else "ordinary"],
                       "other_obligation")]
    result = review(manifest, sources)
    assert "DOUBLE_CREDIT" in codes(result)
    assert_no_authority(result)


def test_same_obligation_selected_by_two_credits_is_conflict_even_for_distinct_objects():
    _, manifest, sources = two_objects()
    manifest["relations"] = [relation_claim("first_credit", "credit"),
        relation_claim("second_credit", "credit", ["second"])]
    result = review(manifest, sources)
    assert "OBLIGATION_CREDIT_REUSED" in codes(result)
    assert_no_authority(result)


def test_cross_receipt_credit_cannot_bypass_reuse_with_a_new_source_id_or_digest():
    _, manifest, sources = fixture()
    add_second_source(manifest, sources)
    manifest["obligations"].append(obligation_claim("other_obligation", "receipt_two"))
    manifest["relations"] = [relation_claim("first_credit", "credit"),
        relation_claim("second_credit", "credit", ["other_receipt"], "other_obligation")]
    result = review(manifest, sources)
    assert "CROSS_RECEIPT_CREDIT" in codes(result)
    assert_no_authority(result)


@pytest.mark.parametrize("kind", ["coverage", "credit"])
def test_baseline_parent_claim_cannot_become_paid_or_proven_via_a_relation(kind):
    _, manifest, sources = fixture()
    manifest["objects"][0].update(role_claim="parent_baseline", category_claim="capture")
    manifest["relations"][0]["kind"] = kind
    result = review(manifest, sources)
    assert "PARENT_BASELINE_UNPROVEN" in codes(result)
    assert row(result, "objects", "ordinary")["role_claim"] == "parent_baseline"
    assert_no_authority(result)


def test_category_mismatch_remains_a_claim_and_does_not_reclassify():
    _, manifest, sources = fixture()
    manifest["objects"][0]["category_claim"] = "installation"
    result = review(manifest, sources)
    assert row(result, "objects", "ordinary")["category_claim"] == "installation"
    assert row(result, "obligations", "historical")["category_claim"] == "capture"
    assert_no_authority(result)


def test_manifest_collection_bounds():
    for where,limit in [("objects", 512), ("obligations", 128),
                                        ("relations", 512), ("sources", 32)]:
        _, manifest, sources = fixture()
        template = manifest[where][0]
        manifest[where] = []
        for index in range(limit + 1):
            item = copy.deepcopy(template)
            item["id"] = "bounded_" + str(index)
            manifest[where].append(item)
            if where == "sources":
                sources[item["id"]] = sources["receipt"]
        if where == "sources":
            del sources["receipt"]
        with pytest.raises(ValueError, match="^COST_SOURCE_"):
            review(manifest, sources)


def test_at_least_one_source_is_required():
    _, manifest, _ = fixture()
    manifest.update(sources=[], objects=[], obligations=[], relations=[])
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, {})


def test_evidence_reference_count_is_bounded():
    where = "objects"
    _, manifest, sources = fixture()
    manifest[where][0]["evidence"] *= 9
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


@pytest.mark.parametrize("pointer", ["/" + "界" * 1366, "/" + "/".join(["x"] * 65)])
def test_pointer_byte_and_segment_limits_are_enforced(pointer):
    _, manifest, sources = fixture()
    manifest["objects"][0]["metadata_pointer"] = pointer
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_manifest_size_is_bounded_before_parsing():
    _, manifest, sources = fixture()
    raw = encoded(manifest) + b" " * (256 * 1024)
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        m.review_cost_sources(raw, sources)


def test_source_size_is_bounded_even_with_correct_digest():
    _, manifest, _ = fixture()
    raw = b'"' + b"x" * (8 * 1024 * 1024) + b'"'
    manifest["sources"] = [source_row("receipt", raw)]
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, {"receipt": raw})


def test_total_source_size_is_bounded_below_each_individual_limit():
    _, manifest, _ = fixture()
    raw = b'"' + b"x" * (6 * 1024 * 1024) + b'"'
    sources = {key: raw for key in ("receipt", "two", "three")}
    manifest["sources"] = [source_row(key, value) for key, value in sources.items()]
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


@pytest.mark.parametrize("raw", [b"[" * 2000 + b"0" + b"]" * 2000, b"[" + b"0," * 100000 + b"0]"])
def test_source_depth_and_node_bounds_report_valueerror_not_recursionerror(raw):
    _, manifest, _ = fixture()
    manifest["sources"] = [source_row("receipt", raw)]
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, {"receipt": raw})


def test_allocated_bytes_multiplication_checks_signed_64_bit_overflow():
    document, manifest, sources = fixture()
    document["items"][0]["before"]["blocks"] = MAX_INT // 512 + 1
    repin(manifest, sources, "receipt", document)
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_source_subtotal_checks_overflow_even_when_each_amount_is_valid():
    document, manifest, sources = two_objects()
    for item in document["items"][:2]:
        item["before"]["blocks"] = MAX_INT // 512
    repin(manifest, sources, "receipt", document)
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_diagnostic_bound_catches_alias_amplification():
    _, manifest, sources = fixture()
    manifest["objects"] = [object_claim("alias_" + str(index)) for index in range(512)]
    manifest["relations"] = []
    assert len(encoded(manifest)) <= 256 * 1024
    with pytest.raises(ValueError, match="^COST_SOURCE_DIAGNOSTIC_LIMIT"):
        review(manifest, sources)


def test_output_bytes_bound_catches_long_referenced_paths():
    document, manifest, sources = fixture()
    document["items"] = [{
        "path": "/" + "x" * 4000 + "/" + str(index),
        "before": {"device": 11, "inode": 100 + index, "blocks": 1},
    } for index in range(512)]
    manifest["objects"] = [object_claim("object_" + str(index),
        pointer="/items/" + str(index)) for index in range(512)]
    manifest["relations"] = []
    repin(manifest, sources, "receipt", document)
    assert len(encoded(manifest)) <= 256 * 1024
    with pytest.raises(ValueError, match="^COST_SOURCE_OUTPUT_LIMIT"):
        review(manifest, sources)


def test_actual_source_map_cannot_exceed_declared_source_bound():
    _, manifest, sources = fixture()
    sources.update({"extra_" + str(index): b"{}" for index in range(32)})
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_total_relation_memberships_are_bounded():
    _, manifest, sources = fixture()
    manifest["objects"] = [object_claim("object_" + str(index)) for index in range(410)]
    for item in manifest["objects"]:
        item.update(metadata_pointer=None, path_pointer=None)
    identifiers = [item["id"] for item in manifest["objects"]]
    manifest["relations"] = [relation_claim("relation_" + str(index),
        kind="coverage" if index < 2 else "credit",
        object_ids=identifiers[:409] if index == 4 else identifiers)
        for index in range(5)]
    assert sum(len(item["object_ids"]) for item in manifest["relations"]) == 2049
    assert len(encoded(manifest)) <= 256 * 1024
    with pytest.raises(ValueError, match="^COST_SOURCE_MEMBERSHIP_LIMIT"):
        review(manifest, sources)


def test_manifest_api_requires_bytes():
    manifest_raw = "{}"
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        m.review_cost_sources(manifest_raw, {})


def test_source_api_requires_original_bytes():
    source_value = bytearray(b"{}")
    _, manifest, sources = fixture()
    sources["receipt"] = source_value
    with pytest.raises(ValueError, match="^COST_SOURCE_"):
        review(manifest, sources)


def test_determinism_canonical_encoding_and_inputs_are_unchanged():
    _, manifest, sources = fixture()
    add_second_source(manifest, sources)
    manifest_before, sources_before = copy.deepcopy(manifest), copy.deepcopy(sources)
    first = review(manifest, sources)
    second = review(manifest, dict(reversed(tuple(sources.items()))))
    assert first == second
    assert m.encoded(first) == encoded(first)
    assert encoded(first).endswith(b"\n") and not encoded(first).endswith(b"\n\n")
    assert manifest == manifest_before and sources == sources_before


def test_review_does_not_read_reference_paths_import_helpers_or_execute_payloads(monkeypatch):
    document, manifest, sources = fixture()
    document["evidence"]["payload"] = "__import__('os').system('do-not-execute')"
    document["items"][0]["path"] = "/proc/self/environ"
    repin(manifest, sources, "receipt", document)
    raw = encoded(manifest)

    def forbidden(*args, **kwargs):
        raise AssertionError("byte-only review attempted I/O, import, or execution")

    # Load the component before these guards; the public call must be pure bytes.
    with monkeypatch.context() as guard:
        for target, names in (
            (builtins, ("open", "eval", "exec")),
            (io, ("open",)),
            (os, ("open", "stat", "lstat", "listdir", "scandir", "readlink", "system")),
            (Path, ("open", "read_bytes", "read_text", "stat")),
            (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        guard.setattr(builtins, "__import__", forbidden)
        result = m.review_cost_sources(raw, sources)
    assert_no_authority(result)
    assert b"do-not-execute" not in encoded(result)
    assert b"synthetic-original-field" not in encoded(result)
