"""Actual temporary metadata → independent sender/host resource validators."""
from __future__ import annotations

import copy
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux metadata observer", allow_module_level=True)

from test_e3_q2_core_pool_accounting import fixture as pool_fixture, create, shared, d as producer
from test_e3_q2_core_resource_result import c, load


field = load("q2_core_delivery_dispatcher")
UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def observed(pool_fixture, monkeypatch):
    f = pool_fixture
    # The engine fixture's stub UUID is deliberately not an admission document;
    # supply the real contract shape for this producer/consumer boundary test.
    monkeypatch.setattr(producer, "_cap_uuid", lambda fd: UUID)
    for role, parent in f.e._admission["parents"].items():
        parent["fs_uuid"] = UUID
        f.e._admission["filesystems"][role]["fs_uuid"] = UUID
    f.engine.observe("ADMISSION")
    implementation = dict(commit="1" * 40, tree="2" * 40)
    arguments = dict(implementation=implementation, locators=f.e.context["manifest"]["locators"],
        guest_deadlines=dict(boottime_origin_ns=1, monotonic_origin_ns=1,
                             boottime_deadline_ns=10000, monotonic_deadline_ns=10000),
        admission=f.e._admission, plans=())
    return f, arguments


def validate(report, arguments, *, complete=True):
    assert c.validate_resource_accounting(report, **arguments, complete=complete) is report
    context = dict(manifest={key: arguments[key] for key in ("implementation", "locators")},
                   hello=dict(guest_boottime_origin_ns=1, guest_monotonic_origin_ns=1),
                   guest_deadlines=arguments["guest_deadlines"])
    extras = {key: arguments[key] for key in ("admission", "plans", "installation", "preparations")
              if key in arguments}
    assert field._validate_resource_accounting(report, context, **extras, complete=complete) is report


def snapshot(f, arguments):
    return f.engine.snapshot(c.make_completion_adjustment(arguments["implementation"]))


def test_initial_absence_then_final_boundary_consumes_without_invented_usage(observed):
    f, arguments = observed
    f.engine.observe("FINALIZATION")
    report = snapshot(f, arguments)
    validate(report, arguments)
    assert report["observed_maxima_sum"] == dict(bytes=0, inodes=0)
    assert all(row["status"] == "ABSENT" for row in report["pools"])


def test_partial_roots_and_absence_parents_in_same_pool(observed):
    f, arguments = observed
    path = shared(f)
    create(f, path + "/temporary", b"actual allocation")
    prefix = "/evidence/lhqcore-20261005b"
    create(f, prefix)
    prefix += "/c01-h01-normal"
    create(f, prefix)
    create(f, prefix + "/capture")
    f.engine.observe("FINALIZATION")
    report = snapshot(f, arguments)
    validate(report, arguments)
    for pool_id in ("shared_install", "c01-h01-normal/capture"):
        row = next(row for row in report["pools"] if row["pool_id"] == pool_id)
        assert {pin["role"] for pin in row["last_observation"]["identities"]} == {
            "POOL_ROOT", "ABSENCE_PARENT"}


def test_early_absence_maximum_and_late_failure_remain_incomplete(observed, monkeypatch):
    f, arguments = observed
    path = shared(f)
    original_maximum = copy.deepcopy(f.engine.rows["shared_install"]["bytes_maximum"])
    assert original_maximum["method"] == "VERIFIED_ABSENCE"
    monkeypatch.setattr(f.e, "_capacity_protection", lambda info: (_ for _ in ()).throw(OSError("test failure")))
    with pytest.raises(OSError):
        f.engine.observe("FINALIZATION", ["shared_install"])
    report = snapshot(f, arguments)
    validate(report, arguments, complete=False)
    assert report["observed_maxima_sum"] == dict(bytes=None, inodes=None)
    assert report["pools"][0]["bytes_maximum"] == original_maximum


def test_created_root_can_gain_neighbor_without_relabeling_old_maximum(observed):
    f, arguments = observed
    path = shared(f)
    temporary = create(f, path + "/temporary", b"x" * 16384)
    f.engine.observe("CHILD_AFTER", ["shared_install"])
    before = copy.deepcopy(f.engine.rows["shared_install"]["bytes_maximum"])
    temporary.unlink()  # Frozen child temporary lifetime modeled in the fixture.
    create(f, "/install/local-hand-core-acceptance-20261005b")
    f.engine.observe("FINALIZATION")
    report = snapshot(f, arguments)
    validate(report, arguments)
    assert report["pools"][0]["bytes_maximum"] == before
    assert any(pin["role"] == "ABSENCE_PARENT" for pin in before["identities"])
    assert all(pin["role"] == "POOL_ROOT" for pin in report["pools"][0]["last_observation"]["identities"])


def quota_parents(f, arguments):
    prefix = "/quota/lhqcore-20261005b"
    create(f, prefix)
    prefix += "/c01-h01-normal"
    create(f, prefix)
    directories = {}
    for name in ("profile-work", "profile-evidence", "profile-temporary", "store-parent"):
        path = prefix + "/" + name
        info = create(f, path).stat()
        directories[name] = dict(path=path, device=info.st_dev, inode=info.st_ino)
    arguments["preparations"] = [{"facts": {"directories": directories}}]
    return [p for p in f.engine.definitions if p["case_id"] == "c01-h01-normal"
            and p["measurement_kind"] == "PROJECT_QUOTA"]


def test_absence_parent_created_during_preparation_binds_original_directory(observed):
    f, arguments = observed
    quota_parents(f, arguments)
    f.engine.observe("FINALIZATION")
    report = snapshot(f, arguments)
    validate(report, arguments)
    quota = next(row for row in report["pools"] if row["pool_id"] == "c01-h01-normal/quota/work-a")
    assert quota["last_observation"]["identities"][0]["path"].endswith("/profile-work")
    changed = copy.deepcopy(arguments)
    changed["preparations"][0]["facts"]["directories"]["profile-work"]["inode"] += 1
    with pytest.raises(c.ContractError, match="ABSENCE_BINDING"):
        c.validate_resource_accounting(report, **changed)


def test_quota_ready_binds_original_plan_without_business_reads(observed, monkeypatch):
    f, arguments = observed
    definitions = quota_parents(f, arguments)
    roots = []
    for definition in definitions:
        path = definition["roots"][0]["path"]
        info = create(f, path).stat()
        roots.append(dict(path=path, device=info.st_dev, inode=info.st_ino, filesystem_uuid=UUID,
            project_id=definition["project_id"], hard_bytes=1048576, inode_hard_limit=128,
            accounting=True, enforcement=True, identity_unchanged=True, xflags=512))
    f.engine.observe("FINALIZATION")
    partial = snapshot(f, arguments)
    validate(partial, arguments, complete=False)
    assert all(row["status"] == "INCOMPLETE" for row in partial["pools"]
               if row["pool_id"].startswith("c01-h01-normal/quota/"))
    f.engine.quota_ready("c01-h01-normal", roots)
    arguments["plans"] = [{"case_id": "c01-h01-normal", "roots": [{"observed": dict(
        path=root["path"].removeprefix("/quota/"), device=root["device"], inode=root["inode"],
        filesystem_uuid=UUID, project_id=root["project_id"])} for root in roots]}]
    f.e._capacity_quota_inventory = lambda **kwargs: [dict(project=root["project_id"], hard=1024, ihard=128,
                                                 space=4096, inodes=1) for root in roots]
    original = f.engine._locate
    # Registered roots must use the bound pins; any filesystem inspection of
    # those roots, including H11 business outputs in production, is prohibited.
    forbidden = {root["path"] for root in roots}
    def protected(root):
        assert root["path"] not in forbidden
        return original(root)
    monkeypatch.setattr(f.engine, "_locate", protected)
    f.engine.observe("FINALIZATION")
    report = snapshot(f, arguments)
    validate(report, arguments)
    assert all(row["status"] == "OBSERVED" for row in report["pools"]
               if row["pool_id"].startswith("c01-h01-normal/quota/"))
