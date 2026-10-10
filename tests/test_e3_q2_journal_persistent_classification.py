"""Unissued historical locations stay protected without inventing artifacts."""
import copy
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux maintenance bindings", allow_module_level=True)

from e3_host import q2_core_obligation_inputs as o
from e3_host import q2_journal_growth as h
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_dispatcher as d
from test_e3_q2_core_minimal_continuation import originals
from test_e3_q2_journal_runtime_failure import local_inventory


UNISSUED = ("/pending-transfer", "/pending-transfer.intent.json")


@pytest.fixture
def classification(monkeypatch):
    monkeypatch.setattr(o, "UNISSUED_STARTUP_PATH_PINS", tuple(
        (len(path.encode()), h.digest(path.encode())) for path in UNISSUED))
    return dict(protected_roots=["/evidence", *UNISSUED],
                essential_paths=["/evidence/receipt", *UNISSUED])


def test_classification_preserves_protection_and_input(classification):
    before = copy.deepcopy(classification)
    value = o.persistent_inventory(classification)
    assert value == dict(before, essential_paths=["/evidence/receipt"])
    assert classification == before


@pytest.mark.parametrize("fault", ["partial", "duplicate", "unprotected"])
def test_incomplete_source_classification_rejects(classification, fault):
    if fault == "partial":
        classification["essential_paths"].remove(UNISSUED[0])
    elif fault == "duplicate":
        classification["essential_paths"].append(UNISSUED[0])
    else:
        classification["protected_roots"].remove(UNISSUED[1])
    with pytest.raises(o.c.ContractError, match="PERSISTENT_CLASSIFICATION"):
        o.persistent_inventory(classification)


def test_similar_names_and_other_requirements_are_not_suppressed(classification):
    others = [UNISSUED[0] + "-other", UNISSUED[0] + "/receipt", "/other/receipt"]
    classification["essential_paths"].extend(others)
    value = o.persistent_inventory(classification)
    assert value["essential_paths"] == ["/evidence/receipt", *others]


@pytest.mark.parametrize("exists", [False, True])
def test_real_persistent_walker_still_requires_evidence(classification, local_inventory, exists):
    inv, root, calls, reads = local_inventory
    inv.description = o.persistent_inventory(classification)
    if exists:
        target = root / "evidence/receipt"
        target.write_bytes(b"retained evidence")
        target.chmod(0o600)
        assert inv.persistent()["count"] == 1
    else:
        with pytest.raises(FileNotFoundError):
            inv.persistent()
        assert inv.context["path_sha256"] == h.digest(b"/evidence/receipt")
    assert calls == ["/", "evidence", "receipt"]
    assert reads[0] == "/proc/self/mountinfo"


@pytest.fixture
def classified_originals(classification, monkeypatch, request):
    import q1_binding_fixture
    original = q1_binding_fixture.inventory
    def inventory():
        value = original()
        for key in ("protected_roots", "essential_paths"):
            value[key] = sorted([*value[key], *UNISSUED])
        return value
    monkeypatch.setattr(q1_binding_fixture, "inventory", inventory)
    return request.getfixturevalue("originals")


def test_both_completion_consumers_accept_the_exact_classification(classified_originals):
    files, args = classified_originals
    frozen = args["frozen"]
    old, proof = h.q1_declaration(frozen["q1_raw"])
    assert set(UNISSUED) <= set(old["essential_paths"])
    assert not set(UNISSUED) & set(frozen["inventory"]["essential_paths"])
    assert set(UNISSUED) <= set(frozen["inventory"]["protected_roots"])
    assert h.validate_q1_frozen(frozen) == proof
    value = p.build_journal_transition(files, **args)
    assert d._validate_journal_transition(value, priors=args["priors"],
        implementation=args["implementation"], current_boot=value["new_boot_id"]) == value
    assert value["old_commitments_refunded"] is False


@pytest.mark.parametrize("fault", ["old_requirements", "dropped_evidence", "dropped_protection"])
def test_completion_consumer_rejects_other_inventory_changes(classified_originals, fault):
    files, args = classified_originals
    args = copy.deepcopy(args)
    inventory = args["frozen"]["inventory"]
    if fault == "old_requirements":
        inventory["essential_paths"].extend(UNISSUED)
        inventory["essential_paths"].sort()
    elif fault == "dropped_evidence":
        inventory["essential_paths"].clear()
    else:
        inventory["protected_roots"].remove(UNISSUED[0])
    with pytest.raises((h.prior.r.ObservationError, p.c.ContractError)):
        p.build_journal_transition(files, **args)
