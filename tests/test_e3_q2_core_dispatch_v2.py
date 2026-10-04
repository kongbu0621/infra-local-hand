"""Synthetic v2 transport tests; neither retained-source nor field acceptance.

The minimal private components below are envelope fixtures, not approved host
facts.  Full dispatch intentionally stops at the missing host writer preimage.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import struct
import sys

import pytest


if not sys.platform.startswith("linux"):
    pytest.skip("Core field dispatcher requires Linux resource limits", allow_module_level=True)


PATH = Path(__file__).parent / "e3_host/q2_core_delivery_dispatcher.py"
SPEC = importlib.util.spec_from_file_location("_q2_dispatch_v2_test", PATH)
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def repack(value):
    manifest, blobs = value["manifest"], value["members"]
    raw = d.canonical(manifest, newline=True)
    package = d.PACKAGE_MAGIC + struct.pack(">Q", len(raw)) + raw + b"".join(
        bytes(blobs[row["path"]]) for row in manifest["members"])
    value["bind"].update(package_bytes=len(package), package_sha256=d._sha(package),
                         hello_sha256=d._sha(d.canonical(value["hello"], newline=True)))
    value["stdin_bytes_received"] = 16 + len(d.canonical(value["bind"], newline=True)) + len(package)
    return value


def context_v2(*, guest_duration_ns=750 * d.NS):
    """Produce a coherent v2 transport envelope, not a releasable package."""
    implementation = {"commit": "9" * 40, "tree": "7" * 40}
    amendment = {"baseline": copy.deepcopy(d.AMENDMENT_BASELINE),
                 "owner_decision": copy.deepcopy(d.AMENDMENT_OWNER_DECISION),
                 "closure": copy.deepcopy(d.AMENDMENT_CLOSURE),
                 "implementation": implementation}
    remote = {"account": "q1admin", "uid": 1000, "gid": 1000, "home": "/home/q1admin",
              "login_shell": "/bin/bash", "parser_profile": "bash-noninteractive-c-v1",
              "remote_tokens_sha256": "a" * 64, "remote_command_sha256": "b" * 64}
    for index, (name, path) in enumerate(d.REMOTE_ALIASES.items()):
        remote[name] = {"path": path, "resolved_path": path, "symlink_chain": [],
                        "dev": 1, "ino": index + 10, "mode": 0o755, "uid": 0,
                        "gid": 0, "nlink": 1, "bytes": 100, "sha256": str(index + 1) * 64}
    expectation = {"account": "q1admin", "home_path": "/home/q1admin", "login_shell": "/bin/bash",
                   "hello_schema": d.HELLO_SCHEMA, "parser_profile": "bash-noninteractive-c-v1",
                   "aliases": d.REMOTE_ALIASES, "remote_tokens_sha256": "a" * 64,
                   "remote_command_sha256": "b" * 64, "remote_entity_preimages_stage": "HELLO_JIT"}
    approved = {"schema": "local-hand-q2-core-approved-inputs/v1", "scope": d.SCOPE,
                "amendment": amendment, "source_relation": {"synthetic": "source"},
                "policy_basis": {"remote_expectation": expectation},
                "historical_capacity_obligations": {"synthetic": "obligations"},
                "retained_preparation": {"synthetic": "retained"},
                "reconciliation": {"synthetic": "reconciliation"}}
    approved_raw = d.canonical(approved, newline=True)
    descriptor = {"path": d.APPROVED_INPUTS_PATH, "bytes": len(approved_raw),
                  "sha256": d._sha(approved_raw),
                  "approved_source_relation_sha256": d._sha(d.canonical(approved["source_relation"]))}
    blobs = {"field/loader.py": b"loader", "field/bootstrap.py": b"bootstrap",
             "field/dispatcher.py": PATH.read_bytes(), d.APPROVED_INPUTS_PATH: approved_raw}
    rows = []
    entry = {"carrier_argv_sha256": "c" * 64, "local_management_binding_sha256": "d" * 64}
    for name in ("loader", "bootstrap", "dispatcher"):
        path, raw = "field/" + name + ".py", blobs["field/" + name + ".py"]
        entry.update({name + "_path": path, name + "_bytes": len(raw), name + "_sha256": d._sha(raw)})
        rows.append({"path": path, "role": "field-code", "mode": 420, "bytes": len(raw),
                     "sha256": d._sha(raw), "origin": {"kind": "implementation-blob",
                     "commit": implementation["commit"], "path": "tests/e3_host/q2_core_delivery_" + name + ".py",
                     "blob": d._git_blob(raw)}})
    rows.append({"path": descriptor["path"], "role": "approved-inputs", "mode": 384,
                 "bytes": descriptor["bytes"], "sha256": descriptor["sha256"], "origin": {
                     "kind": "approved-inputs", "bytes": descriptor["bytes"],
                     "sha256": descriptor["sha256"],
                     "approved_source_relation_sha256": descriptor["approved_source_relation_sha256"]}})
    rows.sort(key=lambda row: row["path"].encode("ascii"))
    locators = {"schema": "local-hand-q2-core-private-locators/v1",
                "observation_record_sha256": "e" * 64, "source_relation_sha256": "0" * 64,
                "state_parent": "/state", "quota_parent": "/quota", "install_parent": "/install",
                "journal_parent": "/journal", "evidence_parent": "/evidence",
                "ordinary_user": "q2job", "ordinary_group": "q2job",
                "user_manager_unit": "user@1100.service", "query_parent_unit": "query.slice",
                "controller_parent_unit": "controller.slice", "management_parent_unit": "management.slice",
                "supervisor_parent_unit": "supervisor.slice", "ordinary_parent_unit": "ordinary.slice",
                "retained_ordinary_parent_path": "/sys/fs/cgroup/retained.slice",
                "carrier_unit": "lhqcore20261003a-carrier.service"}
    relation = {"schema": "local-hand-q2-core-locator-relation/v2",
                "local_management_binding_sha256": entry["local_management_binding_sha256"],
                "observation_record_sha256": locators["observation_record_sha256"],
                "locators": {key: item for key, item in locators.items() if key != "source_relation_sha256"}}
    locators["source_relation_sha256"] = d._sha(d.canonical(relation))
    manifest = {"schema": d.PACKAGE_SCHEMA, "scope": d.SCOPE, "rule": copy.deepcopy(d.RULE),
                "baseline": copy.deepcopy(d.BASELINE), "owner_decision": copy.deepcopy(d.OWNER_DECISION),
                "closure": copy.deepcopy(d.CLOSURE), "implementation": implementation,
                "amendment": amendment, "approved_inputs": descriptor,
                "candidate": copy.deepcopy(d.CANDIDATE), "wheel": copy.deepcopy(d.WHEEL),
                "projection": copy.deepcopy(d.PROJECTION), "entry": entry, "locators": locators,
                "members": rows, "limits": copy.deepcopy(d.PACKAGE_LIMITS)}
    guest_origin, host_origin = 1000 * d.NS, 2000 * d.NS
    hello = {"schema": d.HELLO_SCHEMA, "scope": d.SCOPE,
             "loader_sha256": entry["loader_sha256"], "bootstrap_sha256": entry["bootstrap_sha256"],
             "guest_boot_id": "11111111-2222-3333-4444-555555555555",
             "guest_boottime_origin_ns": guest_origin, "guest_monotonic_origin_ns": guest_origin + d.NS,
             "pid": 123, "uid": 0, "gid": 0, "euid": 0, "egid": 0, "remote_management": remote,
             "python": {key: remote["python"][key] for key in d.PROGRAM_FIELDS},
             "carrier_unit": {"name": locators["carrier_unit"],
                 "control_group": "/system.slice/" + locators["carrier_unit"], "invocation_id": "f" * 32,
                 "active_state": "active", "sub_state": "running", "runtime_max_usec": 800000000,
                 "timeout_stop_usec": 30000000, "memory_max": 1073741824, "memory_swap_max": 0,
                 "tasks_max": 128, "cpu_quota_per_sec_usec": 1000000, "restart": "no",
                 "kill_mode": "control-group", "exit_type": "cgroup"},
             "process_limits": {"cpu_soft": 800, "cpu_hard": 800, "nofile_soft": 256,
                 "nofile_hard": 256, "fsize_soft": 67108864, "fsize_hard": 67108864, "umask": 0o077}}
    remaining = guest_duration_ns + 17 * d.NS
    bind = {"schema": "local-hand-q2-core-carrier-bind/v1", "scope": d.SCOPE, "session_id": d.SESSION,
            "hello_sha256": "0" * 64, "consumption_sha256": "1" * 64, "package_basename": "only.lhfp",
            "package_bytes": 1, "package_sha256": "0" * 64,
            "host_boottime_origin_ns": host_origin, "host_monotonic_origin_ns": host_origin + d.NS,
            "host_boottime_deadline_ns": host_origin + 900 * d.NS,
            "host_monotonic_deadline_ns": host_origin + 901 * d.NS,
            "host_boottime_bind_ns": host_origin + 900 * d.NS - remaining,
            "host_monotonic_bind_ns": host_origin + 901 * d.NS - remaining,
            "host_remaining_floor_ns": remaining, "clock_margin_ns": 2 * d.NS,
            "local_final_reserve_ns": 15 * d.NS, "mapped_duration_ns": guest_duration_ns,
            "guest_duration_cap_ns": 750 * d.NS, "guest_duration_ns": guest_duration_ns}
    value = {"schema": d.CONTEXT_SCHEMA, "hello": hello, "bind": bind, "manifest": manifest,
             "members": blobs, "guest_deadlines": {"boot_id": hello["guest_boot_id"],
                 "boottime_deadline_ns": guest_origin + guest_duration_ns,
                 "monotonic_deadline_ns": guest_origin + d.NS + guest_duration_ns},
             "stdin_bytes_received": 0}
    return repack(value)


def test_v2_envelope_and_exact_nine_preimages_are_bound():
    value = context_v2()
    assert d._validate_context_envelope(value) is value
    inputs = d._approved_inputs_envelope(value)
    binding = d._admission_binding(value)
    assert len(binding) == 9
    assert binding["approved_inputs_sha256"] == d._sha(value["members"][d.APPROVED_INPUTS_PATH])
    assert binding["hello_sha256"] == value["bind"]["hello_sha256"]
    for component in d.ADMISSION_COMPONENTS:
        name = "approved_source_relation" if component == "source_relation" else component
        assert binding[name + "_sha256"] == d._sha(d.canonical(inputs[component]))
    assert binding["remote_management_sha256"] == d._sha(d.canonical(value["hello"]["remote_management"]))
    assert binding["approved_source_relation_sha256"] != value["manifest"]["locators"]["source_relation_sha256"]


@pytest.mark.parametrize("area,key,replacement,reason", [
    ("hello", "schema", "local-hand-q2-core-carrier-hello/v1", "CORE_DISPATCH_HELLO"),
    ("manifest", "schema", "local-hand-q2-core-field-package/v1", "CORE_DISPATCH_MANIFEST_AUTHORITY"),
    ("hello", "uid", False, "CORE_DISPATCH_HELLO"),
    ("hello", "python", {}, "CORE_DISPATCH_PYTHON_PROJECTION"),
])
def test_mixed_protocol_or_malformed_current_identity_rejected(area, key, replacement, reason):
    value = context_v2()
    value[area][key] = replacement
    repack(value)
    with pytest.raises(d.DispatchError, match=reason):
        d._validate_context_envelope(value)


def test_private_descriptor_digest_and_mode_cannot_drift():
    value = context_v2()
    value["manifest"]["approved_inputs"]["sha256"] = "0" * 64
    repack(value)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_APPROVED_MEMBER"):
        d._validate_context_envelope(value)
    value = context_v2()
    value["manifest"]["members"][-1]["mode"] = 420
    repack(value)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_PACKAGE_ROW"):
        d._validate_context_envelope(value)


def test_amendment_and_static_remote_expectation_are_not_adopted_from_hello():
    value = context_v2()
    value["manifest"]["amendment"]["closure"]["tree"] = "0" * 40
    repack(value)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_AMENDMENT_AUTHORITY"):
        d._validate_context_envelope(value)
    value = context_v2()
    value["hello"]["remote_management"]["remote_command_sha256"] = "c" * 64
    repack(value)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_REMOTE_EXPECTATION"):
        d._validate_context_envelope(value)


def test_writer_gap_stops_dispatch_before_any_effect_and_does_not_fake_receipt(deep_context):
    value = deep_context
    class NoEffects:
        def __getattr__(self, name):
            pytest.fail("an effect was inspected or called: " + name)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_HOST_WRITER_UNBOUND"):
        d.dispatch(value, NoEffects())
    assert d.field_readiness()["releasable"] is False
    assert "consumption.host_writer_preimage_unbound" in d.field_readiness()["protocol_blockers"]


def test_json_signed_integer_and_duplicate_key_limits():
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_JSON_INTEGER"):
        d.document(b'{"n":9223372036854775808}\n', limit=1024)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_JSON_DUPLICATE"):
        d.document(b'{"n":1,"n":1}\n', limit=1024)


@pytest.mark.parametrize("key", [
    "approved_inputs_sha256", "approved_source_relation_sha256", "policy_basis_sha256",
    "historical_capacity_obligations_sha256", "retained_preparation_sha256", "reconciliation_sha256",
    "local_management_binding_sha256", "hello_sha256", "remote_management_sha256",
])
def test_admission_rejects_each_wrong_preimage_digest(key):
    value = context_v2()
    binding = d._admission_binding(value)
    assert d._validate_admission_binding(binding, value) is binding
    binding[key] = "0" * 64
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_ADMISSION_BINDING"):
        d._validate_admission_binding(binding, value)


def test_admission_binding_rejects_self_digest_missing_or_extra_fields():
    value = context_v2()
    binding = d._admission_binding(value)
    binding["approved_inputs_sha256"] = d._sha(d.canonical(binding))
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_ADMISSION_BINDING"):
        d._validate_admission_binding(binding, value)
    binding = d._admission_binding(value)
    binding.pop("remote_management_sha256")
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_ADMISSION_BINDING_FIELDS"):
        d._validate_admission_binding(binding, value)
    binding = d._admission_binding(value)
    binding["private_approved_inputs"] = {}
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_ADMISSION_BINDING_FIELDS"):
        d._validate_admission_binding(binding, value)


def _set_approved(value, artifact):
    artifact = copy.deepcopy(artifact)
    artifact["amendment"] = copy.deepcopy(value["manifest"]["amendment"])
    raw = d.canonical(artifact, newline=True)
    descriptor = {"path": d.APPROVED_INPUTS_PATH, "bytes": len(raw), "sha256": d._sha(raw),
                  "approved_source_relation_sha256": d._sha(d.canonical(artifact["source_relation"]))}
    value["manifest"]["approved_inputs"] = descriptor
    value["members"][d.APPROVED_INPUTS_PATH] = raw
    row = next(row for row in value["manifest"]["members"] if row["role"] == "approved-inputs")
    row.update(bytes=len(raw), sha256=d._sha(raw), origin={
        "kind": "approved-inputs", "bytes": len(raw), "sha256": d._sha(raw),
        "approved_source_relation_sha256": descriptor["approved_source_relation_sha256"]})
    for key in ("remote_tokens_sha256", "remote_command_sha256"):
        value["hello"]["remote_management"][key] = artifact["policy_basis"]["remote_expectation"][key]
    return repack(value)


@pytest.fixture
def deep_context(monkeypatch):
    # Use the aggregate parser's explicitly synthetic source vectors. Patch
    # only their fixed pins/derived templates, never either parser function.
    # This is a protocol test, not validation of an actual private artifact.
    from test_e3_q2_core_approved_inputs import artifact
    from e3_host import q2_core_approved_inputs as a
    value, _sources, _tokens = artifact.__wrapped__(monkeypatch)
    for name, replacement in (
        ("APPROVED_VECTOR_PINS", a.horizon.VECTOR_PINS),
        ("APPROVED_PREFIX_SHA256", a.horizon.PREFIX_SHA256),
        ("APPROVED_TAIL_SHA256", a.horizon.TAIL_SHA256),
        ("APPROVED_RETAINED_PINS", a.RETAINED_PINS),
        ("APPROVED_POLICY_SOURCE_PINS", a.policy.SOURCE_PINS),
    ):
        monkeypatch.setattr(d, name, copy.deepcopy(replacement))
    fixed = copy.deepcopy(d.APPROVED_FIXED)
    fixed.update(horizon=a._horizon_relation(), placement=a._placement_relation())
    monkeypatch.setattr(d, "APPROVED_FIXED", fixed)
    return _set_approved(context_v2(), value)


def test_standalone_component_parser_has_no_host_import_or_pin_drift():
    from e3_host import q2_core_approved_inputs as a
    import ast
    tree = ast.parse(PATH.read_text())
    assert all(not isinstance(node, ast.ImportFrom) or node.level == 0 for node in ast.walk(tree))
    for key in ("locator", "later", "horizon", "producer", "quota", "placement"):
        assert d.APPROVED_FIXED[key] == getattr(a, "_" + key + "_relation")()
    assert d.APPROVED_FIXED["legacy"] == a._legacy_fixed()
    assert d.APPROVED_VECTOR_PINS == a.horizon.VECTOR_PINS
    assert d.APPROVED_RETAINED_PINS == a.RETAINED_PINS
    assert d.APPROVED_POLICY_SOURCE_PINS == a.policy.SOURCE_PINS
    assert PATH.stat().st_size <= 262144
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_APPROVED_FIELDS"):
        d._validate_approved_components(d._approved_inputs_envelope(context_v2()))


def test_standalone_deep_parser_binds_all_components_without_host_modules(deep_context, monkeypatch):
    from e3_host import q2_core_approved_inputs as a
    value = d._approved_inputs_envelope(deep_context)
    monkeypatch.setattr(a, "validate", lambda *_args, **_kwargs: pytest.fail("host validator invoked"))
    assert d._validate_approved_components(value) is value
    assert d._validate_context_envelope(deep_context) is deep_context
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_HOST_WRITER_UNBOUND"):
        d._validate_context(deep_context)


@pytest.mark.parametrize("change", [
    "locator", "legacy_forward", "permission", "horizon", "producer", "snapshot", "double_credit",
    "quota", "placement", "source_union", "retained", "refund", "later_issued", "atime",
    "policy_runas", "policy_argv", "policy_timeout", "policy_rc", "extra",
])
def test_standalone_deep_parser_rejects_rehashed_component_substitutions(deep_context, change):
    value = d._approved_inputs_envelope(deep_context)
    relation, capacity = value["source_relation"], value["historical_capacity_obligations"]
    obligations, policies = relation["obligations"], value["policy_basis"]["policies"]
    if change == "locator": relation["locator"]["mappings"].reverse()
    elif change == "legacy_forward": obligations["legacy_20260927"]["adoption"]["forward_baseline_entries"].pop()
    elif change == "permission": obligations["run_permission_adopted"] = True
    elif change == "horizon": obligations["source_horizon"] = "20261001d"
    elif change == "producer": obligations["producer"]["device_selectors"]["management"] = "quota_parent"
    elif change == "snapshot": capacity["snapshot_rows"][0]["commitment"]["bytes"] += 1
    elif change == "double_credit": capacity["effective_rows"] += capacity["snapshot_rows"][:7]
    elif change == "quota": capacity["configured_quota_rows"].pop()
    elif change == "placement": obligations["placement"]["split_allowed"] = True
    elif change == "source_union": obligations["source_union_sha256"] = "f" * 64
    elif change == "retained": value["retained_preparation"]["paths"][0]["inode"] += 1
    elif change == "refund": value["reconciliation"]["released_bytes"] = 1
    elif change == "later_issued": relation["later_nonissuance"][0]["state"] = "ISSUED"
    elif change == "atime": obligations["legacy_20260927"]["adoption"]["disclosed_atime_changes"] = {}
    elif change == "policy_runas": policies["sudo"]["predicate"]["parameters"]["required_grant"]["runas_groups"] = ["ALL"]
    elif change == "policy_argv": policies["sudo"]["argv"].append("-S")
    elif change == "policy_timeout": policies["sshd"]["limits"]["command_seconds"] = 6
    elif change == "policy_rc": policies["rc"]["predicate"]["parameters"]["required_absent"] = []
    elif change == "extra": value["admission_pass"] = True
    if change != "source_union":
        digest = d._sha(d.canonical(d._approved_union(relation)))
        obligations["source_union_sha256"] = capacity["source_union_sha256"] = digest
    for item in policies.values():
        item["predicate_sha256"] = d._sha(d.canonical(item["predicate"]))
    value["policy_basis"]["policy_predicates_sha256"] = d._sha(d.canonical(policies))
    with pytest.raises(d.DispatchError):
        d._validate_approved_components(value)
