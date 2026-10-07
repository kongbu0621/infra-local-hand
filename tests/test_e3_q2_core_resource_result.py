"""Synthetic wire evidence only; no guest observation or acceptance is claimed."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / "e3_host" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = load("q2_core_delivery_contract")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def seal(value):
    for pool in value["pools"]:
        for field in ("last_observation", "bytes_maximum", "inodes_maximum"):
            item = pool[field]
            if item is not None:
                item["source_sha256"] = digest({"pool_id": pool["pool_id"], "case_id": pool["case_id"],
                    "observation": {key: actual for key, actual in item.items() if key != "source_sha256"}})
    value["snapshot_sha256"] = digest({key: value[key] for key in
        ("completion_adjustment", "pools", "observed_maxima_sum")})
    return value


def missing(role):
    return {"code": "SYNTHETIC_UNOBSERVED", "role": role, "detail_sha256": digest({"role": role})}


def fixture():
    implementation = {"commit": "1" * 40, "tree": "2" * 40}
    locators = {role + "_parent": "/test/" + role for role in ("state", "quota", "journal", "evidence", "install")}
    uuid = "11111111-2222-3333-4444-555555555555"
    parents = {role: {"path": locators[role + "_parent"], "dev": index + 1,
                      "ino": index + 10, "fs_uuid": uuid}
               for index, role in enumerate(("state", "quota", "journal", "evidence", "install"))}
    # Independent literal classification from A, not the consumer's constructor.
    definitions = [("shared_install", None, 67108864, 4096,
                    [("install", "local-hand-core-acceptance-20261007a"),
                     ("install", ".local-hand-core-acceptance-20261007a.staging")], None),
                   ("carrier_audit", None, 8388608, 512,
                    [(role, "lhqcore-20261007a") for role in ("state", "quota", "journal", "evidence")], None)]
    ids = ("c01-h01-normal", "c02-q4-cancel", "c03-h11-recovery")
    refs = ("work-a", "evidence-a", "temporary-a", "work-b", "evidence-b", "temporary-b", "retained_store")
    directories = ("profile-work", "profile-evidence", "profile-temporary", "profile-work",
                   "profile-evidence", "profile-temporary", "store-parent")
    for case_index, case in enumerate(ids):
        prefix = "lhqcore-20261007a/" + case
        definitions.extend([
            (case + "/state", case, 8388608, 1536,
             [(role, prefix) for role in ("state", "quota", "journal", "evidence")], None),
            (case + "/journal", case, 1048576, 128, [("journal", prefix + "/journal")], None),
            (case + "/capture", case, 20971520, 384,
             [("evidence", prefix + "/capture"), ("evidence", prefix + "/declarations")], None)])
        definitions.extend((case + "/quota/" + ref, case, 1048576, 128,
                            [("quota", prefix + "/" + directory + "/" + ref)], 12501 + case_index * 7 + index)
                           for index, (ref, directory) in enumerate(zip(refs, directories)))
    plans = {case: {"case_id": case, "roots": []} for case in ids}
    pools = []; inode = 100; absence = []
    for name, case, amount, inodes, roots, project in definitions:
        identities = []
        for role, suffix in roots:
            path = locators[role + "_parent"] + "/" + suffix
            inode += 1
            identity = dict(path=path, role="POOL_ROOT", dev=parents[role]["dev"], ino=inode,
                            fs_uuid=uuid, project_id=project)
            identities.append(identity)
            absence.append(dict(kind="path", name=path, absent=True, collision=False))
            if project is not None:
                plans[case]["roots"].append({"observed": {"path": suffix, "device": identity["dev"],
                    "inode": inode, "filesystem_uuid": uuid, "project_id": project}})
        kind = "PROJECT_QUOTA" if project is not None else "OWNED_ALLOCATION"
        allocated = len(roots) * 4096
        observation = dict(method=kind, boundary="FINALIZATION", boottime_ns=500, monotonic_ns=600,
            allocated_bytes=allocated, allocated_inodes=len(roots), identities=sorted(identities, key=lambda v: v["path"]),
            quota=None if project is None else dict(project_id=project, hard_bytes=amount,
                hard_inodes=inodes, used_bytes=allocated, used_inodes=len(roots), enforcement_flags=0x30), source_sha256="")
        pools.append(dict(pool_id=name, case_id=case, measurement_kind=kind, byte_limit=amount,
            inode_limit=inodes, status="OBSERVED", controlled_io=dict(written_bytes=0, created_inodes=0),
            last_observation=copy.deepcopy(observation), bytes_maximum=copy.deepcopy(observation),
            inodes_maximum=copy.deepcopy(observation), missing=[]))
    value = dict(schema="local-hand-q2-core-resource-accounting/v1",
        completion_adjustment=c.make_completion_adjustment(implementation),
        basis="APPLICATION_AND_OBSERVED_OWNED_ALLOCATION", full_guest_filesystem_peak_proven=False,
        pools=pools, observed_maxima_sum=dict(bytes=sum(p["bytes_maximum"]["allocated_bytes"] for p in pools),
                                           inodes=sum(p["inodes_maximum"]["allocated_inodes"] for p in pools)),
        snapshot_sha256="", missing=[])
    arguments = dict(implementation=implementation, locators=locators,
        guest_deadlines=dict(boottime_origin_ns=100, monotonic_origin_ns=200,
                             boottime_deadline_ns=1000, monotonic_deadline_ns=1100),
        admission=dict(parents=parents, absence=absence), plans=list(plans.values()))
    return seal(value), arguments


def incomplete_fixture():
    value, arguments = fixture()
    missing_rows = []
    for pool in value["pools"]:
        pool["status"] = "INCOMPLETE"
        pool["controlled_io"] = {"written_bytes": None, "created_inodes": None}
        for field in ("last_observation", "bytes_maximum", "inodes_maximum"):
            pool[field] = None
        pool["missing"] = sorted([missing(pool["pool_id"] + "/" + field) for field in
            ("controlled_io", "last_observation", "bytes_maximum", "inodes_maximum")],
            key=lambda row: (row["code"], row["role"], row["detail_sha256"]))
        missing_rows.extend(pool["missing"])
    value["missing"] = sorted(missing_rows, key=lambda row: (row["code"], row["role"], row["detail_sha256"]))
    value["observed_maxima_sum"] = dict(bytes=None, inodes=None)
    return seal(value), arguments


def test_fixed_pools_and_complete_evidence():
    value, arguments = fixture()
    assert len(value["pools"]) == 32
    assert sum(row["byte_limit"] for row in value["pools"]) == 180 * 1024**2
    assert c.validate_resource_accounting(value, **arguments) is value
    assert value["full_guest_filesystem_peak_proven"] is False


@pytest.mark.parametrize("mutation,error", [
    (lambda v: v.update(full_guest_filesystem_peak_proven=True), "GUARANTEE"),
    (lambda v: v.update(extra=0), "FIELDS"),
    (lambda v: v["pools"].reverse(), "POOL_BINDING"),
    (lambda v: v["pools"].pop(), "POOL_SET"),
    (lambda v: v["pools"][0].update(byte_limit=67108865), "POOL_BINDING"),
    (lambda v: v["completion_adjustment"]["implementation"].update(commit="3" * 40), "AUTHORITY"),
    (lambda v: v["pools"][0]["last_observation"].update(boottime_ns=1000), "WINDOW"),
    (lambda v: v["pools"][0]["last_observation"].update(monotonic_ns=199), "WINDOW"),
    (lambda v: v["pools"][0]["bytes_maximum"].update(boottime_ns=501), "TIME_ORDER"),
    (lambda v: v["pools"][0]["inodes_maximum"].update(monotonic_ns=601), "TIME_ORDER"),
    (lambda v: v["pools"][0]["bytes_maximum"].update(allocated_bytes=0), "MAXIMUM"),
    (lambda v: v["pools"][0]["last_observation"].update(boundary="CHILD_AFTER"), "FINAL_BOUNDARY"),
    (lambda v: v["pools"][0]["last_observation"]["identities"].pop(), "ROOT_COVERAGE"),
    (lambda v: v["pools"][0]["last_observation"]["identities"][0].update(dev=999), "DEVICE_BINDING"),
    (lambda v: v["pools"][5]["last_observation"]["identities"][0].update(ino=999), "PREPARATION_BINDING"),
    (lambda v: v["pools"][5]["last_observation"]["quota"].update(enforcement_flags=0x10), "ENFORCEMENT"),
    (lambda v: v["pools"][5]["last_observation"]["quota"].update(used_bytes=1), "QUOTA"),
    (lambda v: v["pools"][0]["controlled_io"].update(written_bytes=None), "IO_MISSING"),
    (lambda v: v["observed_maxima_sum"].update(bytes=0), "TOTAL_BINDING"),
])
def test_consumer_rejects_semantic_forgery_even_with_recomputed_digests(mutation, error):
    value, arguments = fixture()
    mutation(value)
    seal(value)
    with pytest.raises(c.ContractError, match=error):
        c.validate_resource_accounting(value, **arguments)


def test_source_and_snapshot_are_independently_recomputed():
    value, arguments = fixture()
    value["pools"][0]["last_observation"]["source_sha256"] = "f" * 64
    value["snapshot_sha256"] = digest({key: value[key] for key in
        ("completion_adjustment", "pools", "observed_maxima_sum")})
    with pytest.raises(c.ContractError, match="SOURCE_DIGEST"):
        c.validate_resource_accounting(value, **arguments)
    seal(value)["snapshot_sha256"] = "f" * 64
    with pytest.raises(c.ContractError, match="SNAPSHOT_DIGEST"):
        c.validate_resource_accounting(value, **arguments)


def test_unknown_values_stay_incomplete_and_are_not_zero():
    value, arguments = incomplete_fixture()
    arguments.update(admission=None, plans=(), complete=False)
    assert c.validate_resource_accounting(value, **arguments) is value
    with pytest.raises(c.ContractError, match="INCOMPLETE"):
        c.validate_resource_accounting(value, **dict(arguments, complete=True))
    value["observed_maxima_sum"] = dict(bytes=0, inodes=0)
    seal(value)
    with pytest.raises(c.ContractError, match="TOTAL_BINDING"):
        c.validate_resource_accounting(value, **arguments)


def test_last_and_independent_maxima_may_differ_without_refunding():
    value, arguments = fixture()
    pool = value["pools"][0]
    pool["bytes_maximum"].update(allocated_bytes=16384, allocated_inodes=2, boottime_ns=300, monotonic_ns=400,
                                 boundary="CHILD_AFTER")
    pool["inodes_maximum"].update(allocated_bytes=8192, allocated_inodes=5, boottime_ns=400, monotonic_ns=500,
                                  boundary="CHILD_AFTER")
    value["observed_maxima_sum"]["bytes"] += 8192
    value["observed_maxima_sum"]["inodes"] += 3
    seal(value)
    assert c.validate_resource_accounting(value, **arguments) is value


def test_absence_cannot_hide_a_root_created_by_the_bound_plan():
    value, arguments = fixture()
    pool = value["pools"][5]
    parent = arguments["admission"]["parents"]["quota"]
    for field in ("last_observation", "bytes_maximum", "inodes_maximum"):
        pool[field].update(method="VERIFIED_ABSENCE", allocated_bytes=0, allocated_inodes=0,
                           quota=None, identities=[dict(parent, role="ABSENCE_PARENT", project_id=None)])
    pool["status"] = "ABSENT"
    value["observed_maxima_sum"]["bytes"] -= 4096
    value["observed_maxima_sum"]["inodes"] -= 1
    seal(value)
    with pytest.raises(c.ContractError, match="ABSENCE_IO"):
        c.validate_resource_accounting(value, **arguments)


def test_partial_report_retains_known_maximum_but_not_false_total():
    value, arguments = fixture()
    pool = value["pools"][0]
    pool["status"] = "INCOMPLETE"
    pool["last_observation"] = None
    pool["missing"] = [missing("shared_install/last_observation")]
    value["missing"] = list(pool["missing"])
    value["observed_maxima_sum"] = dict(bytes=None, inodes=None)
    seal(value)
    assert c.validate_resource_accounting(value, **arguments, complete=False) is value
    pool["status"] = "OBSERVED"
    seal(value)
    with pytest.raises(c.ContractError, match="OBSERVATION_MISSING"):
        c.validate_resource_accounting(value, **arguments, complete=False)


def test_actual_over_limit_can_be_retained_but_never_completed():
    value, arguments = fixture()
    pool = value["pools"][0]
    for field in ("last_observation", "bytes_maximum", "inodes_maximum"):
        pool[field]["allocated_bytes"] = 67108865
    value["observed_maxima_sum"]["bytes"] += 67108865 - 8192
    seal(value)
    assert c.validate_resource_accounting(value, **arguments, complete=False) is value
    with pytest.raises(c.ContractError, match="POOL_LIMIT"):
        c.validate_resource_accounting(value, **arguments)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Entry uses Linux field-contract dependencies")
def test_v2_consumer_preserves_unknown_usage_and_requires_the_exact_missing_role():
    e = load("q2_core_delivery_entry")
    from test_e3_q2_core_delivery_entry import not_run_output, hello
    raw = not_run_output("3" * 64, 123)
    manifest, members = e.parse_output(raw)
    _, arguments = incomplete_fixture()
    context = {"manifest": {key: arguments[key] for key in ("implementation", "locators")},
               "hello": hello(), "bind": {"guest_duration_ns": 750000000000}}
    kwargs = dict(consumption_sha256="3" * 64, stdin_bytes_received=123,
                  frame_bytes=len(raw), expected_context=context)
    checked = e.validate_output_semantics(manifest, members, **kwargs)
    assert checked["remote"]["usage"]["guest_allocated_bytes"] is None
    remote = manifest["remote_result"]
    remote["missing"] = [row for row in remote["missing"] if row["role"] != "usage/guest_allocated_bytes"]
    with pytest.raises(e.contract.ContractError, match="USAGE_MISSING"):
        e.validate_output_semantics(manifest, members, **kwargs)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Entry uses Linux field-contract dependencies")
def test_all_business_passes_cannot_promote_unknown_resources_to_finalized(monkeypatch):
    e = load("q2_core_delivery_entry")
    from test_e3_q2_core_delivery_entry import not_run_output
    raw = not_run_output("3" * 64, 123)
    manifest, members = e.parse_output(raw)
    manifest["remote_result"]["state"] = "REMOTE_FINALIZED"
    # Isolate the independent finalization gate from business producers, which
    # have their own raw-evidence tests. Three returned PASS flags are inadequate.
    monkeypatch.setattr(e, "_validate_case_index", lambda *args: ["PASS"] * 3)
    with pytest.raises(e.contract.ContractError, match="FINAL_MISSING"):
        e.validate_output_semantics(manifest, members, consumption_sha256="3" * 64,
                                    stdin_bytes_received=123, frame_bytes=len(raw))


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Entry uses Linux field-contract dependencies")
def test_old_remote_result_remains_parseable_but_cannot_enter_new_output_path():
    e = load("q2_core_delivery_entry")
    old = {key: None for key in c.SCHEMA_FIELDS["local-hand-q2-core-remote-result/v1"]}
    old.update(schema="local-hand-q2-core-remote-result/v1", cases=[])
    assert c.validate_record(old) is old
    manifest = dict(schema="local-hand-q2-core-output-package/v1", session_id=c.SESSION_ID,
                    remote_result=old, cases=[], members=[], limits={})
    raw = e.frame(c.OUTPUT_MAGIC, manifest, json_limit=1048576)
    with pytest.raises(e.contract.ContractError, match="SCHEMA"):
        e.parse_output(raw)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Entry uses Linux field-contract dependencies")
def test_output_frame_fixed_point_includes_all_resource_records():
    e = load("q2_core_delivery_entry")
    value, _ = fixture()
    remote = {key: None for key in c.SCHEMA_FIELDS[c.REMOTE_RESULT_SCHEMA]}
    remote.update(schema=c.REMOTE_RESULT_SCHEMA, cases=[], resource_accounting=value,
                  usage={"output_frame_bytes": 0})
    manifest = dict(schema="local-hand-q2-core-output-package/v1", session_id=c.SESSION_ID,
                    remote_result=remote, cases=[], members=[], limits={})
    for _ in range(8):
        raw = e.frame(c.OUTPUT_MAGIC, manifest, json_limit=1048576)
        if remote["usage"]["output_frame_bytes"] == len(raw):
            break
        remote["usage"]["output_frame_bytes"] = len(raw)
    else:
        pytest.fail("output frame length did not converge")
    assert len(c.canonical(remote)) < e.REMOTE_RESULT_LIMIT
    assert len(raw) > 65536
    parsed, members = e.parse_output(raw)
    assert parsed == manifest and not members
