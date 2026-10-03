import json

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
        "consumption_sha256": "2" * 64, "package_basename": "fixed.lhfp",
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
        list(range(12101, 12108)), list(range(12108, 12115)), list(range(12115, 12122))]


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


def test_all_fourteen_protocol_records_have_closed_top_level_keys():
    assert len(c.SCHEMA_FIELDS) == 14
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


def test_hello_requires_real_carrier_limits_and_root_identity():
    value = {"schema": "local-hand-q2-core-carrier-hello/v1", "scope": c.SCOPE,
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
            "umask": 0o077}}
    assert c.validate_hello(value, loader_sha256="1" * 64, bootstrap_sha256="2" * 64) is value
    value["carrier_unit"]["memory_max"] += 1
    with pytest.raises(c.ContractError, match="CORE_HELLO_CARRIER"):
        c.validate_hello(value)


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
