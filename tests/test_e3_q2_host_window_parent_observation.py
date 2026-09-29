"""First-span RAM evidence, independent of qualification or field admission.

Real syscall cases reuse the mandatory actual-ordinary fixture. Root runners
skip those cases; geometry and readiness remain explicit isolated models.
"""
import copy
from types import SimpleNamespace

import pytest

from test_e3_q2_host_window_ordinary import ordinary, modeled, pure_intent
from e3_host import q2_host_window_billing as billing
from e3_host import q2_host_window_contract as c
from e3_host import q2_host_window_record as r


def held_model():
    """Pure allocation arithmetic model; never an ordinary execution claim."""
    intent, _ = pure_intent()
    return r.HeldConsumption(SimpleNamespace(parent=SimpleNamespace(fd=-99),
        proof=intent["precheck"])), intent["precheck"]["parent_metadata"]


@pytest.mark.parametrize("first_blocks,later_blocks", [(8, 16), (16, 8), (7, 16)])
def test_first_budget_retains_exact_endpoint_without_later_replacement(monkeypatch, first_blocks, later_blocks):
    held, before = held_model()
    current = dict(before, blocks=first_blocks, ctime_ns=2)
    monkeypatch.setattr(r.os, "fstat", lambda fd: current)
    monkeypatch.setattr(r.io, "metadata", lambda info: dict(info))
    scan = dict(bytes=8192, inodes=2, entries=[dict(source_metadata=dict(size=4096))])
    expected = copy.deepcopy(current)
    first = held._budget(scan)
    current.update(blocks=later_blocks, ctime_ns=3)
    assert held._budget(scan) == first
    assert held._first_parent_metadata == expected
    assert first["parent_growth_bytes"] == max(0, first_blocks-before["blocks"]) * 512
    # A negative first delta is retained, not laundered to equal metadata;
    # the new pure billing profile rejects it rather than claiming no growth.
    assert held._first_allocation_observation is None


def test_failed_first_budget_does_not_cache_success(monkeypatch):
    held, before = held_model()
    monkeypatch.setattr(r.os, "fstat", lambda fd: dict(before, blocks=24))
    monkeypatch.setattr(r.io, "metadata", lambda info: dict(info))
    with pytest.raises(ValueError, match="ACTUAL_LIMIT"):
        held._budget(dict(bytes=8192, inodes=2, entries=[]))
    assert held._first_parent_metadata is None
    assert held.parent_growth_bytes is None


@pytest.mark.parametrize("closed,durable,available", [
    (False, False, False), (True, True, True), (False, True, False)])
def test_partial_closed_or_legacy_record_cannot_export_observation(closed, durable, available):
    held, _ = held_model()
    held.closed, held.durable = closed, durable
    held._first_allocation_observation = {} if available else None
    with pytest.raises(ValueError, match="NOT_DURABLE|UNAVAILABLE"):
        held.first_allocation_observation()


def test_real_first_observation_is_bound_immutable_and_exports_without_io(modeled, monkeypatch):
    held = modeled.consume()
    intent = c.document(held.intent_raw)
    first = held.first_allocation_observation()
    assert first == dict(schema=r.PARENT_ALLOCATION_SCHEMA,
        span="precheck-parent-to-first-marker-budget",
        binding_sha256=c.sha(c.encoded(intent["binding"])),
        location_sha256=intent["precheck"]["location_sha256"],
        intent_sha256=held.intent_sha256, precheck_sha256=intent["precheck_sha256"],
        window=intent["window"], parent_path=modeled.location["parent"],
        parent_before=intent["precheck"]["parent_metadata"],
        parent_after=held._first_parent_metadata,
        marker_snapshot_sha256=c.sha(c.encoded(held.snapshot)))
    frozen = copy.deepcopy(first)
    inventory = copy.deepcopy(modeled.bill["inventory"])
    marker = modeled.location["directory"]
    inventory["marker"]["state"] = "DURABLE"
    inventory["scans"][marker] = copy.deepcopy(held.snapshot)
    inventory["expected_roots"][marker] = "capture"
    inventory["parent_allocation"] = first
    arguments = dict(raw=held.intent_raw, expected_binding=modeled.binding,
        location=modeled.location, window=intent["window"])
    bill = billing.quote_host_parent_allocation(inventory, **arguments)
    transition = billing.validate_marker_transition_parent_allocation(modeled.bill, bill, **arguments)
    assert transition["parent_allocation_sha256"] == c.sha(c.encoded(frozen))
    assert transition["full_bill_proven"] is False
    assert bill["summary"]["marker"]["parent_growth"] == dict(
        bytes=(first["parent_after"]["blocks"]-first["parent_before"]["blocks"])*512, inodes=0)
    first["parent_after"]["blocks"] += 100
    first["window"]["deadline_ns"] += 100
    def forbidden(*args, **kwargs):
        pytest.fail("historical RAM export performed new observation or I/O")
    with monkeypatch.context() as patcher:
        for name in ("open", "fstat", "stat", "getxattr", "read", "pread", "listdir",
                     "scandir", "write", "fsync", "getresuid", "getresgid", "getgroups"):
            patcher.setattr(r.os, name, forbidden)
        patcher.setattr(held, "verify", forbidden)
        patcher.setattr(held.preflight, "guard", forbidden)
        assert held.first_allocation_observation() == frozen
    held.close()
    with pytest.raises(ValueError, match="NOT_DURABLE"):
        held.first_allocation_observation()


def test_real_sibling_change_and_rechecks_do_not_rewrite_first_observation(modeled):
    held = modeled.consume()
    first = held.first_allocation_observation()
    (modeled.root / "later-isolated-sibling").write_bytes(b"later change\n")
    held.verify()
    evidence = held.evidence
    assert held.first_allocation_observation() == first
    assert evidence["schema"] == r.ORDINARY_EVIDENCE_SCHEMA
    assert "parent_allocation" not in evidence and "first_allocation" not in evidence
    assert evidence["actual"]["parent_growth_bytes"] == held.parent_growth_bytes
    historical = r.verify_existing_ordinary(modeled.location, modeled.binding,
        modeled.window, held.intent_sha256)
    assert "parent_allocation" not in historical and "first_allocation" not in historical
