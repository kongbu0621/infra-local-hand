import json
import copy

import pytest

from e3_host import q2_core_delivery_contract as c


def bind_record():
    origin = 1_000_000_000_000
    bind = origin + 1_000_000_000
    deadline = origin + 900_000_000_000
    floor = (deadline - bind) // 1_000_000 * 1_000_000
    return {
        "schema": "local-hand-q2-core-carrier-bind/v1", "scope": c.SCOPE,
        "session_id": c.SESSION_ID, "hello_sha256": "1" * 64,
        "consumption_sha256": "2" * 64, "package_basename": "lhqcore-20261005a.lhfp",
        "package_bytes": 1024, "package_sha256": "3" * 64,
        "host_boottime_origin_ns": origin, "host_monotonic_origin_ns": origin,
        "host_boottime_deadline_ns": deadline, "host_monotonic_deadline_ns": deadline,
        "host_boottime_bind_ns": bind, "host_monotonic_bind_ns": bind,
        "host_remaining_floor_ns": floor, "clock_margin_ns": 2_000_000_000,
        "local_final_reserve_ns": 15_000_000_000,
        "mapped_duration_ns": floor - 17_000_000_000,
        "guest_duration_cap_ns": 750_000_000_000,
        "guest_duration_ns": min(floor - 17_000_000_000, 750_000_000_000),
    }


def test_frozen_authority_and_budget_values_are_exact():
    assert c.RULE["commit"] == "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
    assert c.BASELINE["commit"] == "74366b3fe41e675b1aa2d677228714a5606c275c"
    assert c.CLOSURE["commit"] == "a8dd077392ebb656770c8f94ca3b051e93fc296d"
    assert c.CANDIDATE["commit"] == "4b6e4a7c403362358192086b88679e1326dcb2e1"
    assert c.WHEEL["sha256"] == "ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9"
    assert c.LIMITS["total_guest_physical_bytes"] == 180 * 1024**2
    assert c.LIMITS["total_guest_admission_bytes"] == 276 * 1024**2
    assert (c.LIMITS["total_cpu_seconds"], c.LIMITS["peak_pids"]) == (2090, 1160)
    assert [item["kind"] for item in c.CASES] == [
        "H01_NORMAL", "Q4_HELPER_RUNNING_CANCEL_SUBSET", "H11_SAME_LEDGER_RECOVERY"]
    assert [item["project_ids"] for item in c.CASES] == [
        list(range(12201, 12208)), list(range(12208, 12215)), list(range(12215, 12222))]


def test_canonical_json_rejects_duplicate_float_noncanonical_and_newline_mismatch():
    value = {"z": [1, True, None], "a": "ascii"}
    raw = c.canonical(value, newline=True)
    assert raw == b'{"a":"ascii","z":[1,true,null]}\n'
    assert c.document(raw, limit=1024, newline=True) == value
    with pytest.raises(c.ContractError, match="CORE_JSON_DUPLICATE_KEY"):
        c.document(b'{"a":1,"a":2}', limit=1024)
    with pytest.raises(c.ContractError, match="CORE_JSON_FLOAT"):
        c.document(b'{"a":1.5}', limit=1024)
    with pytest.raises(c.ContractError, match="CORE_JSON_CANONICAL"):
        c.document(b'{"z":1, "a":2}', limit=1024)
    with pytest.raises(c.ContractError, match="CORE_JSON_NEWLINE"):
        c.document(raw, limit=1024, newline=False)
    with pytest.raises(c.ContractError, match="CORE_JSON_FLOAT"):
        c.canonical({"a": 1.5})


def test_all_protocol_records_have_closed_top_level_keys():
    assert len(c.SCHEMA_FIELDS) == 18
    assert set(c.SCHEMA_FIELDS[c.REMOTE_RESULT_SCHEMA]) == {
        *c.SCHEMA_FIELDS["local-hand-q2-core-remote-result/v1"], "resource_accounting"}
    for schema, fields in c.SCHEMA_FIELDS.items():
        value = {field: None for field in fields}
        value["schema"] = schema
        assert c.validate_record(value) is value
        value["extra"] = None
        with pytest.raises(c.ContractError, match="CORE_RECORD_FIELDS"):
            c.validate_record(value)


def test_bind_clock_mapping_is_mechanical_and_nonrefreshable():
    value = bind_record()
    assert c.validate_bind(value) is value
    changed = dict(value, guest_duration_ns=value["guest_duration_ns"] + 1)
    with pytest.raises(c.ContractError, match="CORE_BIND_MAPPING"):
        c.validate_bind(changed)
    changed = dict(value, host_boottime_bind_ns=value["host_boottime_deadline_ns"])
    with pytest.raises(c.ContractError, match="CORE_BIND_MAPPING"):
        c.validate_bind(changed)
    changed = dict(value,
                   host_boottime_deadline_ns=value["host_boottime_deadline_ns"]
                       + 300_000_000_000,
                   host_monotonic_deadline_ns=value["host_monotonic_deadline_ns"]
                       + 300_000_000_000,
                   host_remaining_floor_ns=value["host_remaining_floor_ns"]
                       + 300_000_000_000,
                   mapped_duration_ns=value["mapped_duration_ns"]
                       + 300_000_000_000)
    with pytest.raises(c.ContractError, match="CORE_BIND_HOST_WINDOW"):
        c.validate_bind(changed)


def hello_record():
    aliases = {"shell": "/bin/bash", "sudo": "/usr/bin/sudo", "env": "/usr/bin/env",
               "systemd_run": "/usr/bin/systemd-run", "python": "/usr/bin/python3"}
    remote = {"account": "q1admin", "uid": 1000, "gid": 1000, "home": "/home/q1admin",
        "login_shell": "/bin/bash", "parser_profile": "bash-noninteractive-c-v1",
        "remote_tokens_sha256": "a" * 64, "remote_command_sha256": "b" * 64}
    remote.update({role: {"path": alias, "resolved_path": alias, "symlink_chain": [],
        "dev": 1, "ino": 2, "mode": 0o755, "uid": 0, "gid": 0, "nlink": 1,
        "bytes": 3, "sha256": "3" * 64} for role, alias in aliases.items()})
    return {"schema": c.HELLO_SCHEMA, "scope": c.SCOPE,
        "loader_sha256": "1" * 64, "bootstrap_sha256": "2" * 64,
        "guest_boot_id": "11111111-2222-3333-4444-555555555555",
        "guest_boottime_origin_ns": 1, "guest_monotonic_origin_ns": 2, "pid": 3,
        "uid": 0, "gid": 0, "euid": 0, "egid": 0,
        "python": {"path": "/usr/bin/python3", "dev": 1, "ino": 2, "mode": 0o755,
                   "uid": 0, "gid": 0, "nlink": 1, "bytes": 3, "sha256": "3" * 64},
        "carrier_unit": {"name": c.CARRIER_UNIT,
            "control_group": "/system.slice/" + c.CARRIER_UNIT, "invocation_id": "4" * 32,
            "active_state": "active", "sub_state": "running", "runtime_max_usec": 800_000_000,
            "timeout_stop_usec": 30_000_000, "memory_max": 1_073_741_824,
            "memory_swap_max": 0, "tasks_max": 128, "cpu_quota_per_sec_usec": 1_000_000,
            "restart": "no", "kill_mode": "control-group", "exit_type": "cgroup"},
        "process_limits": {"cpu_soft": 800, "cpu_hard": 800, "nofile_soft": 256,
            "nofile_hard": 256, "fsize_soft": 67_108_864, "fsize_hard": 67_108_864,
            "umask": 0o077}, "remote_management": remote}


def test_hello_requires_real_carrier_limits_and_root_identity():
    value = hello_record()
    assert c.validate_hello(value, loader_sha256="1" * 64, bootstrap_sha256="2" * 64) is value
    value["carrier_unit"]["memory_max"] += 1
    with pytest.raises(c.ContractError, match="CORE_HELLO_CARRIER"):
        c.validate_hello(value)


@pytest.mark.parametrize("mutation", ["v1", "remote_missing", "python_alias", "extra_entity",
    "home", "bool_uid", "oversized_entity", "duplicate_link", "token_mismatch"])
def test_hello_v2_rejects_mixed_or_drifted_identity(mutation):
    value = hello_record()
    remote = value["remote_management"]
    expectation = {"account": "q1admin", "home_path": "/home/q1admin", "login_shell": "/bin/bash",
        "hello_schema": c.HELLO_SCHEMA, "parser_profile": "bash-noninteractive-c-v1",
        "aliases": {key: remote[key]["path"] for key in ("shell", "sudo", "env", "systemd_run", "python")},
        "remote_tokens_sha256": remote["remote_tokens_sha256"],
        "remote_command_sha256": remote["remote_command_sha256"], "remote_entity_preimages_stage": "HELLO_JIT"}
    if mutation == "v1":
        value["schema"] = "local-hand-q2-core-carrier-hello/v1"
    elif mutation == "remote_missing":
        del value["remote_management"]
    elif mutation == "python_alias":
        remote["python"]["resolved_path"] = "/usr/bin/python3.12"
    elif mutation == "extra_entity":
        remote["sudo"]["current"] = True
    elif mutation == "home":
        remote["home"] = "/root"
    elif mutation == "bool_uid":
        remote["uid"] = True
    elif mutation == "oversized_entity":
        remote["sudo"]["bytes"] = 16777217
    elif mutation == "duplicate_link":
        remote["python"]["symlink_chain"] = [{"path": "/usr/bin/python3", "target": "python3.12"}] * 2
    else:
        remote["remote_tokens_sha256"] = "c" * 64
    with pytest.raises(c.ContractError):
        c.validate_hello(value, remote_expectation=expectation)


def test_python_alias_and_resolved_identity_are_distinct_but_bound():
    value = hello_record()
    value["remote_management"]["python"].update(resolved_path="/usr/bin/python3.12",
        symlink_chain=[{"path": "/usr/bin/python3", "target": "python3.12"}])
    value["python"]["path"] = "/usr/bin/python3.12"
    assert c.validate_hello(value) is value


@pytest.mark.parametrize("mutation", ["extra", "old_a", "old_c", "old_d", "zero_d", "mismatch"])
def test_amendment_requires_exact_approved_chain(mutation):
    implementation = {"commit": "b" * 40, "tree": "c" * 40}
    value = c.make_amendment(implementation)
    if mutation == "extra":
        value["scope"] = c.AMENDMENT_SCOPE
    elif mutation == "old_a":
        value["baseline"] = c.BASELINE
    elif mutation == "old_c":
        value["closure"] = c.CLOSURE
    elif mutation == "old_d":
        value["implementation"]["commit"] = "520f77f578b90d31870517e33e29bee42918f3c0"
    elif mutation == "zero_d":
        value["implementation"]["commit"] = "0" * 40
    else:
        value["implementation"]["tree"] = "d" * 40
    with pytest.raises(c.ContractError):
        c.validate_amendment(value, implementation=implementation)


def test_admission_digests_bind_nine_distinct_preimages():
    from e3_host.q2_core_policy_basis import remote_expectation
    hello = hello_record()
    expectation = remote_expectation(["/fixture/executable", "fixed"])
    hello["remote_management"].update({key: expectation[key] for key in
        ("remote_tokens_sha256", "remote_command_sha256")})
    local = {key: {} for key in c.SCHEMA_FIELDS[c.MANAGEMENT_BINDING_SCHEMA]}
    local.update(schema=c.MANAGEMENT_BINDING_SCHEMA, remote_expectation=expectation)
    approved = {"schema": c.APPROVED_INPUTS_SCHEMA, "scope": c.SCOPE,
        "amendment": c.make_amendment({"commit": "b" * 40, "tree": "c" * 40}),
        **{key: {"fixture_component": key} for key in c.APPROVED_COMPONENTS}}
    raw = c.canonical(approved, newline=True)
    bound = c.admission_binding(raw, local, hello)
    assert len(bound) == len(set(bound.values())) == 9
    assert bound["approved_inputs_sha256"] == c.sha256(raw)
    assert bound["approved_source_relation_sha256"] == c.sha256(c.canonical(approved["source_relation"]))
    assert bound["local_management_binding_sha256"] == c.sha256(c.canonical(local, newline=True))
    assert bound["hello_sha256"] == c.sha256(c.canonical(hello, newline=True))
    assert bound["remote_management_sha256"] == c.sha256(c.canonical(hello["remote_management"]))
    assert c.validate_admission_binding(bound, approved_inputs_raw=raw,
        local_management_binding=local, hello=hello) is bound
    wrong = copy.deepcopy(bound)
    wrong["approved_source_relation_sha256"] = c.sha256(c.canonical(approved["source_relation"], newline=True))
    with pytest.raises(c.ContractError, match="CORE_ADMISSION_BINDING"):
        c.validate_admission_binding(wrong, approved_inputs_raw=raw, local_management_binding=local, hello=hello)


@pytest.mark.parametrize("mutation", [None, "extra", "ns_zero", "pid_bool", "uid_drift", "groups_order", "groups_duplicate"])
def test_bound_writer_identity_requires_complete_stable_credentials(mutation):
    writer = {"schema": c.LOCAL_WRITER_SCHEMA, "user_namespace": {"dev": 1, "ino": 2},
        "pid_namespace": {"dev": 1, "ino": 3}, "process": {"pid": 123, "starttime_ticks": 456},
        "uid": dict.fromkeys(("real", "effective", "saved", "filesystem"), 1000),
        "gid": dict.fromkeys(("real", "effective", "saved", "filesystem"), 1000),
        "supplementary_gids": [27, 1000]}
    if mutation is None:
        assert c.validate_local_writer(writer) is writer
        return
    if mutation == "extra":
        writer["root"] = True
    elif mutation == "ns_zero":
        writer["pid_namespace"]["ino"] = 0
    elif mutation == "pid_bool":
        writer["process"]["pid"] = True
    elif mutation == "uid_drift":
        writer["uid"]["filesystem"] = 0
    elif mutation == "groups_order":
        writer["supplementary_gids"] = [1000, 27]
    else:
        writer["supplementary_gids"] = [27, 27]
    with pytest.raises(c.ContractError):
        c.validate_local_writer(writer)


def test_state_paths_allow_only_a_prefix_or_a_terminal_stop():
    assert c.validate_state_path(list(c.LOCAL_STATES))[-1] == "COMPLETE"
    assert c.validate_state_path(list(c.REMOTE_STATES))[-1] == "REMOTE_FINALIZED"
    assert c.validate_state_path(["STATIC_VERIFIED", "CARRIER_CONSUMED", "STOP_AND_RETAIN"])
    assert c.validate_state_path(["REMOTE_PREFIX_STARTED", "BOUND", "REMOTE_STOP_AND_RETAIN"])
    with pytest.raises(c.ContractError, match="CORE_STATE_PATH"):
        c.validate_state_path(["STATIC_VERIFIED", "TRANSPORT_STARTED"])
    with pytest.raises(c.ContractError, match="CORE_STATE_PATH"):
        c.validate_state_path(["STOP_AND_RETAIN"])


def test_path_and_integer_guards_reject_python_bool_and_aliases():
    with pytest.raises(c.ContractError, match="CORE_INTEGER"):
        c.integer(True)
    for bad in ("/absolute", "a/../b", "a//b", "a\\b", "./a"):
        with pytest.raises(c.ContractError, match="CORE_PATH"):
            c.relative_path(bad)
    assert c.relative_path("candidate/.git/HEAD") == "candidate/.git/HEAD"
