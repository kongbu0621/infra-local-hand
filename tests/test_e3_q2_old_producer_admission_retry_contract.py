"""Strict contract and non-executable prototype tests for P2/P3."""
from __future__ import annotations

import copy
import io
import json
import stat
import zipfile

import pytest

from e3_host import q2_old_producer_admission_retry_contract as c


D = "a" * 40
TREE = "b" * 40


def parent(path, *, mode=0o755, uid=1000, gid=1000, device=10, inode=20):
    return dict(schema=c.PARENT_SCHEMA, path=path, type="directory", uid=uid, gid=gid,
        mode=mode, device=device, inode=inode)


def inputs():
    locator = c.encoded(dict(schema=c.LOCATOR_SCHEMA,
        parent=parent("/private/consumption-parent")))
    context = c.encoded(dict(schema=c.CONTEXT_SCHEMA, locator_sha256=c.sha(locator),
        expected_host_boot_id="11111111-2222-3333-4444-555555555555",
        operator=dict(schema=c.OPERATOR_SCHEMA, uid=[1000, 1000, 1000],
            gid=[1000, 1000, 1000], groups=[4, 1000, 1000]),
        ssh_identity_sha256="c" * 64, guest_identity_sha256="d" * 64,
        evidence_parent=parent("/private/evidence-parent", device=11, inode=21)))
    evidence = dict(basename="local-hand-20261002a-evidence.zip",
        evidence_max_frame_bytes=1049600,
        evidence_max_archive_logical_bytes=1048576,
        evidence_max_archive_allocated_bytes=2097152,
        evidence_archive_inode_count=1)
    return locator, context, evidence


def manifest():
    locator, context, evidence = inputs()
    return c.make_manifest(implementation_commit=D, implementation_tree=TREE,
        locator_raw=locator, context_raw=context, evidence=evidence), locator, context


def test_exact_authority_objects_and_permanent_non_executable_boundary():
    value, locator, context = manifest()
    assert value == c.validate_manifest(value, locator, context)
    assert value["authority"] == dict(rule=c.RULE, baseline=c.BASELINE, closure=c.CLOSURE,
        owner_decision_event=c.OWNER_DECISION,
        owner_decision_record_ref=c.OWNER_DECISION_RECORD,
        implementation_commit=D, implementation_tree=TREE,
        p4_event=dict(issued=False, event=None, record_ref=None))
    assert value["private_helper"] == c.PRIVATE_HELPER
    assert value["kernel_reader"] == c.KERNEL_READER
    assert value["new_objects"]["projects"] == c.PROJECTS
    assert value["new_objects"]["project_quota"] == {
        "logical_bytes": 1024**2, "inodes": 128}
    assert value["predecessor"] == c.PREDECESSOR
    assert value["product"]["artifacts"] == {
        "source.bundle": "36fddae6dd57b2d80b90b4eff5d5bf40cb2f6a29d91d946c1bbefabdb5ae2fc0",
        "wheel": "76a2573f9b5f0a1e9e260bf215f57d6cd011f49736653e0939ebd1b2ba034d9a",
        "code-manifest.json": "c764a4f6a05d2b6aaa6f8c1d35617a520dba1c1e91fad54b0e93e02ba856fe86",
    }
    assert value["components"]["consumer_integration"] == {
        "scope": c.SCOPE, "result_schema": c.CONSUMER_RESULT_SCHEMA,
        "implementation_commit": D}
    assert value["governance"] == c.GOVERNANCE
    assert value["qualifications"] == c.QUALIFICATIONS
    assert value["qualifications"]["contract_completeness"] == (
        "PARTIAL_NON_EXECUTABLE_PROTOTYPE")
    assert "P2_FUTURE_PACKAGE_CONTRACT_INCOMPLETE" in value["status"]["blockers"]
    assert value["host_record"]["clock_order"] == {
        "anchor": ["CLOCK_BOOTTIME", "CLOCK_MONOTONIC"],
        "guard": ["CLOCK_MONOTONIC", "CLOCK_BOOTTIME"]}
    assert value["host_record"]["deadlines_seconds"] == {
        "outer": 300, "preparation": 150, "owner": 120}
    assert value["host_record"]["refresh_allowed"] is False
    assert c.DIRECTORY_NAME.endswith(
        "cf8319dc8c8bed098a6917c5777d60b00ac0efcb5fecd813d14fec4e64af6bf3")
    assert all(value["status"][name] is False for name in
        ("field_ready", "allow_run", "guest_executed", "q2_accepted", "q3_accepted",
         "production_supported", "executable", "task_member_present"))
    assert value["status"]["future_package_contract_complete"] is False
    assert value["status"]["p4_contract_qualified"] is False


def test_locator_context_are_strict_and_caller_cannot_override_paths_or_identity():
    locator, context, _ = inputs()
    assert c.validate_locator(locator)["parent"]["path"] == "/private/consumption-parent"
    assert c.validate_context(context, locator)["evidence_parent"]["path"] == "/private/evidence-parent"
    bad = (
        locator.replace(b'"schema":', b'"unknown":1,"schema":', 1),
        locator.replace(b'"path":"/private/consumption-parent"', b'"path":"/private/../escape"'),
        locator.replace(b'"mode":493', b'"mode":511'),
        locator[:-1] + b" trailing",
        locator.replace(b'"schema":', b'"schema":"duplicate","schema":', 1),
    )
    for raw in bad:
        with pytest.raises(ValueError):
            c.validate_locator(raw)
    changed = json.loads(context)
    changed["operator"]["groups"] = [1000, 4]
    with pytest.raises(ValueError, match="GROUPS"):
        c.validate_context(c.encoded(changed), locator)
    changed = json.loads(context)
    changed["evidence_parent"]["uid"] = 1001
    with pytest.raises(ValueError, match="BINDING"):
        c.validate_context(c.encoded(changed), locator)


def test_root_mixed_identity_old_schema_and_bad_limits_rejected():
    locator, context, evidence = inputs()
    parsed = json.loads(context)
    cases = []
    for key, value in (("uid", [0, 0, 0]), ("uid", [1000, 1001, 1000]),
                       ("gid", [1000, 1000, 1001])):
        changed = copy.deepcopy(parsed)
        changed["operator"][key] = value
        cases.append(c.encoded(changed))
    changed = copy.deepcopy(parsed)
    changed["schema"] = "local-hand-q2-host-window-sources/v1"
    cases.append(c.encoded(changed))
    for raw in cases:
        with pytest.raises(ValueError):
            c.validate_context(raw, locator)
    for key, value in (("evidence_archive_inode_count", 2),
                       ("evidence_archive_inode_count", True),
                       ("evidence_max_frame_bytes", evidence["evidence_max_archive_logical_bytes"]),
                       ("basename", "../escape.zip"),
                       ("basename", "evidence-without-zip"),
                       ("basename", "TASK.txt"),
                       ("basename", "MANIFEST.json")):
        changed = dict(evidence)
        changed[key] = value
        with pytest.raises(ValueError):
            c.validate_evidence(changed)


def test_fixed_contract_objects_use_type_sensitive_equality():
    value, locator, context = manifest()
    cases = (
        (("product", "payload_sha256"), False, "FIXED_INPUTS"),
        (("kernel_reader", "scope"), False, "FIXED_INPUTS"),
        (("private_helper", "repair_zip_bytes"), True, "FIXED_INPUTS"),
        (("predecessor", "normal_chain_executions"), False, "OLD_FAILURE"),
        (("predecessor", "outer_exit_status"), True, "OLD_FAILURE"),
        (("components", "host_window", "implementation"), False, "COMPONENTS"),
        (("components", "consumer_integration", "implementation_commit"), False,
            "COMPONENTS"),
        (("new_objects", "projects", "work-a"), True, "NEW_OBJECTS"),
        (("new_objects", "create_only"), 1, "NEW_OBJECTS"),
        (("locator", "bytes"), True, "MEMBER_BINDING"),
        (("context", "bytes"), True, "MEMBER_BINDING"),
        (("host_record", "record_max_inodes"), True, "HOST_RECORD"),
        (("governance", "trusted_storage_no_same_uid_tamper", "owner_accepted"), 1,
            "GOVERNANCE"),
        (("qualifications", "p4", "stable_event_issued"), 0, "QUALIFICATIONS"),
        (("status", "field_ready"), 0, "NON_EXECUTABLE_BOUNDARY"),
        (("status", "normal_chain_executions"), False, "NON_EXECUTABLE_BOUNDARY"),
    )
    for path, replacement, reason in cases:
        changed = copy.deepcopy(value)
        target = changed
        for name in path[:-1]:
            target = target[name]
        target[path[-1]] = replacement
        with pytest.raises(ValueError, match=reason):
            c.validate_manifest(changed, locator, context)


def test_no_claim_can_fill_p4_event_or_qualification_chain():
    value, locator, context = manifest()
    changed = copy.deepcopy(value)
    changed["authority"]["p4_event"] = {
        "issued": True, "event": "invented", "record_ref": "invented"}
    with pytest.raises(ValueError, match="P4_AUTHORITY"):
        c.validate_manifest(changed, locator, context)

    changed = copy.deepcopy(value)
    changed["qualifications"]["h07"]["supplemental_approval_chain"] = ["invented"]
    with pytest.raises(ValueError, match="QUALIFICATIONS"):
        c.validate_manifest(changed, locator, context)

    assert value["qualifications"]["namespace_alignment"] == (
        "EXTERNAL_ASSUMPTION_NOT_PROVEN")
    assert value["qualifications"]["p4"] == {
        "stable_event_issued": False,
        "stable_event": None,
        "stable_record_ref": None,
        "executable_package_authorized": False,
        "task_member_present": False,
        "field_execution_authorized": False,
        "retry_allowed": False,
    }


def test_json_failures_do_not_chain_private_input_or_encoder_errors():
    with pytest.raises(ValueError, match="OLD_PRODUCER_RETRY_JSON") as malformed:
        c.document(b'{"private-material":"not-closed"')
    assert malformed.value.__cause__ is None
    assert malformed.value.__suppress_context__ is True

    with pytest.raises(ValueError, match="OLD_PRODUCER_RETRY_JSON") as unencodable:
        c.encoded({"private-material": object()})
    assert unencodable.value.__cause__ is None
    assert unencodable.value.__suppress_context__ is True


def test_deterministic_flat_0600_prototype_has_no_task_or_executable_member():
    value, locator, context = manifest()
    first = c.build_prototype(value, locator, context)
    second = c.build_prototype(value, locator, context)
    assert first == second
    result = c.validate_prototype(first, implementation_commit=D, implementation_tree=TREE)
    assert result["status"] == "OFFLINE_PARTIAL_PROTOTYPE_VERIFIED"
    assert result["allow_run"] is result["field_ready"] is result["guest_executed"] is False
    assert result["future_package_contract_complete"] is False
    assert result["p4_contract_qualified"] is False
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert tuple(info.filename for info in archive.infolist()) == c.PROTOTYPE_MEMBERS
        assert "TASK.txt" not in archive.namelist()
        assert all(stat.S_IFMT(info.external_attr >> 16) == stat.S_IFREG
            and stat.S_IMODE(info.external_attr >> 16) == 0o600 for info in archive.infolist())


def rewrite(raw, name, value, *, mode=0o600):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(output, "w") as target:
        for info in source.infolist():
            payload = value if info.filename == name else source.read(info)
            cloned = zipfile.ZipInfo(info.filename, info.date_time)
            cloned.create_system = 3
            cloned.compress_type = zipfile.ZIP_STORED
            cloned.external_attr = (stat.S_IFREG | (mode if info.filename == name else 0o600)) << 16
            target.writestr(cloned, payload)
    return output.getvalue()


def test_tampering_wrong_mode_wrong_d_and_extra_task_are_rejected():
    value, locator, context = manifest()
    raw = c.build_prototype(value, locator, context)
    with pytest.raises(ValueError, match="DIGESTS"):
        c.validate_prototype(rewrite(raw, "NON_EXECUTABLE.txt", b"run it\n"),
            implementation_commit=D, implementation_tree=TREE)
    with pytest.raises(ValueError, match="MEMBER"):
        c.validate_prototype(rewrite(raw, "host-context.json", context, mode=0o644),
            implementation_commit=D, implementation_tree=TREE)
    with pytest.raises(ValueError, match="IMPLEMENTATION"):
        c.validate_prototype(raw, implementation_commit="e" * 40, implementation_tree=TREE)
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(output, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info))
        info = zipfile.ZipInfo("TASK.txt")
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | 0o600) << 16
        target.writestr(info, b"forbidden")
    with pytest.raises(ValueError, match="MEMBERS"):
        c.validate_prototype(output.getvalue(), implementation_commit=D, implementation_tree=TREE)


def test_caller_claims_never_close_field_readiness():
    for value in (None, True, {"field_ready": True}, manifest()[0]):
        with pytest.raises(ValueError, match="FIELD_READINESS_UNPROVEN"):
            c.require_field_readiness(value)
