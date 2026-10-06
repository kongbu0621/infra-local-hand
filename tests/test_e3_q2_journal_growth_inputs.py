"""Pure fixed-source transforms only; never inspect the actual guest or VM."""
from __future__ import annotations

import copy
import sys
import io
import tarfile
import zipfile

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux maintenance bindings", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_core_approved_inputs as approved
from e3_host import q2_local_source_delivery as source


def carrier(monkeypatch, content):
    raw = content.encode()
    monkeypatch.setattr(h, "GROWTH_CARRIER_PIN", (len(raw), h.digest(raw)))
    return raw


def frame(monkeypatch, raw, *, duplicate=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("sources/P", raw)
        if duplicate:
            archive.writestr("sources/P", raw)
    result = source.frame_bytes(stream.getvalue())
    monkeypatch.setattr(h, "GROWTH_FRAME_PIN", (len(result), h.digest(result)))
    return result


def test_management_anchor_is_literal_and_never_executes_source(monkeypatch):
    raw = carrier(monkeypatch, "WRAPPER = '/synthetic/private-vm/ssh.sh'\nraise Exception('never execute')\n")
    assert h._growth_frame_anchor(frame(monkeypatch, raw)) == "/synthetic/private-vm"


@pytest.mark.parametrize("text", [
    "WRAPPER = '/x/ssh.sh'\nWRAPPER = '/y/ssh.sh'\n",
    "WRAPPER = '/x/ssh.sh'\ndef change():\n global WRAPPER\n WRAPPER = '/y/ssh.sh'\n",
    "WRAPPER = '/x' + '/ssh.sh'\n",
    "WRAPPER = '/x/not-ssh'\n",
    "WRAPPER = '/x/../y/ssh.sh'\n",
    "WRAPPER = '/ssh.sh'\n",
    "WRAPPER = '/x/ssh.sh'\ndel WRAPPER\n",
])
def test_ambiguous_or_nonliteral_management_anchor_rejected(monkeypatch, text):
    raw = carrier(monkeypatch, text)
    with pytest.raises(h.prior.r.ObservationError):
        h._growth_carrier_anchor(raw)


def test_alternate_frame_cannot_be_used(monkeypatch):
    raw = carrier(monkeypatch, "WRAPPER = '/x/ssh.sh'\n")
    value = frame(monkeypatch, raw)
    with pytest.raises(h.prior.r.ObservationError, match="FRAME_PIN"):
        h._growth_frame_anchor(value + b"\n")


def test_duplicate_archive_carrier_rejected(monkeypatch):
    raw = carrier(monkeypatch, "WRAPPER = '/x/ssh.sh'\n")
    with pytest.warns(UserWarning, match="Duplicate"):
        value = frame(monkeypatch, raw, duplicate=True)
    with pytest.raises(h.prior.r.ObservationError, match="MEMBERS"):
        h._growth_frame_anchor(value)


def test_exact_plan_members_not_basename_or_alternate_path(monkeypatch):
    document = b'{"source":"synthetic"}\n'
    monkeypatch.setattr(approved, "LOCATOR_MEMBERS", (("original_plan", "fixed/plan.json",
                                                     len(document), h.digest(document)),))
    def make(name, kind=tarfile.REGTYPE):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            row = tarfile.TarInfo(name)
            row.type = kind
            row.size = len(document) if kind == tarfile.REGTYPE else 0
            archive.addfile(row, io.BytesIO(document) if row.size else None)
        raw = stream.getvalue()
        monkeypatch.setattr(h.prior, "PLAN_ARCHIVE", (len(raw), h.digest(raw)))
        return raw
    assert h._growth_plan_members(make("fixed/plan.json")) == {"original_plan": {"source": "synthetic"}}
    with pytest.raises(h.prior.r.ObservationError, match="MEMBER_SET"):
        h._growth_plan_members(make("other/plan.json"))
    with pytest.raises(h.prior.r.ObservationError, match="PLAN_MEMBER"):
        h._growth_plan_members(make("fixed/plan.json", tarfile.SYMTYPE))


@pytest.fixture
def inventory_sources():
    boot = "10000000-0000-4000-8000-000000000001"
    paths = {key: "/synthetic/" + key for key in ("state", "quota", "install", "journal", "evidence")}
    plan = dict(host=dict(boot_id=boot), retained=[dict(path="/synthetic/old/ledger.sqlite")],
                retained_inputs=[dict(path="/synthetic/old/installation.json")],
                directories=dict(state=dict(path="/synthetic/new-state")),
                candidate=dict(destination="/synthetic/installed", source="/synthetic/source"),
                parents=dict(query=dict(unit="lhqquery.slice"), ordinary=dict(unit="lhqordinary.slice")),
                settings=dict(controllers=dict(target=dict(unit="lhqtarget.service"))))
    retry = dict(facts=dict(parents=dict(ordinary=dict(unit="lhqordinary.slice",
                 path="/user.slice/user-1100.slice/user@1100.service/lhqordinary.slice"),
                 manager=dict(unit="user@1100.service", MainPID="42"))))
    rows = [dict(covered_paths=["/synthetic/old/row-" + str(i)],
                 evidence=["/synthetic/old/evidence-" + str(i)]) for i in range(36)]
    return plan, retry, {}, dict(effective_rows=rows), paths


def test_inventory_separates_active_manager_domains_and_required_evidence(inventory_sources):
    inventory, boot = h._growth_inventory(*inventory_sources)
    assert boot == inventory_sources[0]["host"]["boot_id"]
    names = {row["name"] for row in inventory["expected_units"]}
    assert "lhqtarget.service" in names
    assert "user@1100.service" not in names
    assert len(names & {s.replace("-", "", 1) + "-carrier.service" for s in h.GROWTH_CORE_SESSIONS}) == 4
    assert any(row["manager"] == "user" for row in inventory["domain_units"])
    assert "/lhqquery.slice" in inventory["domain_cgroups"]
    core_root = "/synthetic/state/lhqcore-20261005c"
    assert core_root in inventory["protected_roots"] and core_root not in inventory["essential_paths"]
    assert "/synthetic/old/evidence-35" in inventory["essential_paths"]
    assert "/synthetic/old/ledger.sqlite" in inventory["essential_paths"]
    assert "/synthetic/new-state" not in inventory["essential_paths"]


def test_multiple_historical_boots_reject(inventory_sources):
    plan, retry, documents, horizon, paths = inventory_sources
    newer = copy.deepcopy(plan)
    newer["host"]["boot_id"] = "20000000-0000-4000-8000-000000000001"
    documents["later", "plan"] = newer
    with pytest.raises(h.prior.r.ObservationError, match="BOOT_DRIFT"):
        h._growth_inventory(plan, retry, documents, horizon, paths)


def test_missing_ordinary_domain_not_invented(inventory_sources):
    plan, retry, documents, horizon, paths = inventory_sources
    retry["facts"]["parents"].pop("ordinary")
    with pytest.raises(h.prior.r.ObservationError, match="ORDINARY_DOMAIN"):
        h._growth_inventory(plan, retry, documents, horizon, paths)


def test_system_manager_ordinary_domain_and_original_user_tree_both_retained(inventory_sources):
    plan, retry, documents, horizon, paths = inventory_sources
    plan["parents"]["controller"] = dict(unit="lhqcontroller.slice")
    plan["parents"]["ordinary"] = dict(unit="lhqcontroller-ordinary.slice")
    inventory, _ = h._growth_inventory(plan, retry, documents, horizon, paths)
    assert "/lhqcontroller.slice/lhqcontroller-ordinary.slice" in inventory["domain_cgroups"]
    assert "/user.slice/user-1100.slice/user@1100.service/lhqordinary.slice" in inventory["domain_cgroups"]


@pytest.mark.parametrize("change", ["evidence_alias", "missing_row", "overlong_unit", "relative_domain"])
def test_inventory_malformed_or_incomplete_fails_closed(inventory_sources, change):
    plan, retry, documents, horizon, paths = inventory_sources
    if change == "evidence_alias":
        horizon["effective_rows"][0]["evidence"] = ["/synthetic/../alias"]
    elif change == "missing_row":
        horizon["effective_rows"].pop()
    elif change == "overlong_unit":
        plan["settings"]["controllers"]["target"]["unit"] = "a" * 200 + ".service"
    else:
        retry["facts"]["parents"]["ordinary"]["path"] = "relative/cgroup"
    with pytest.raises(h.prior.r.ObservationError):
        h._growth_inventory(plan, retry, documents, horizon, paths)
