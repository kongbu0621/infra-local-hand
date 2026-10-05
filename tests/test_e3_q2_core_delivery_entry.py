from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import struct
import sys
import threading
import time
from types import SimpleNamespace

import pytest
from core_writer_fixture import writer, host_marker
from test_e3_q2_core_resource_result import incomplete_fixture, missing as resource_missing

if not sys.platform.startswith("linux"):
    pytest.skip("Core delivery entry requires Linux clocks, ownership and pipe I/O",
                allow_module_level=True)


def load(name):
    path = Path(__file__).parent / "e3_host" / f"{name}.py"
    spec = importlib.util.spec_from_file_location("_test_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


e = load("q2_core_delivery_entry")
c = e.contract


def live_capture(directory_fd, path, origins):
    """Isolated local file tests, not a field-management binding or F1."""
    st = os.fstat(directory_fd)
    anchor = dict(path=str(path), dev=st.st_dev, ino=st.st_ino, mode=0o700,
                  uid=st.st_uid, gid=st.st_gid, nlink=st.st_nlink)
    def clock(which):
        return origins["host_boottime_origin_ns" if which == time.CLOCK_BOOTTIME
                       else "host_monotonic_origin_ns"]
    writer = e.capture_contract.observe_writer(e.capture_contract.Deadline(origins, clock).call)
    return e.capture_contract.LiveCapture(directory_fd, anchor=anchor, writer=writer,
                                         origins=origins, clock_gettime_ns=clock)


def remote_expectation():
    return e.static_remote_expectation(["synthetic-fixed-command"])


def hello():
    expected = remote_expectation()
    entities = {key: dict(identity(path), resolved_path=path, symlink_chain=[])
                for key, path in expected["aliases"].items()}
    entities["python"]["sha256"] = "3" * 64
    entities["python"]["bytes"] = 3
    remote = dict(account="q1admin", uid=1000, gid=1000, home="/home/q1admin",
                  login_shell="/bin/bash", parser_profile="bash-noninteractive-c-v1", **entities,
                  remote_tokens_sha256=expected["remote_tokens_sha256"],
                  remote_command_sha256=expected["remote_command_sha256"])
    return {
        "schema": "local-hand-q2-core-carrier-hello/v2",
        "scope": c.SCOPE,
        "loader_sha256": "1" * 64,
        "bootstrap_sha256": "2" * 64,
        "remote_management": remote,
        "guest_boot_id": "11111111-2222-3333-4444-555555555555",
        "guest_boottime_origin_ns": 100,
        "guest_monotonic_origin_ns": 200,
        "pid": 1,
        "uid": 0,
        "gid": 0,
        "euid": 0,
        "egid": 0,
        "python": {
            "path": "/usr/bin/python3", "dev": 1, "ino": 2, "mode": 0o755,
            "uid": 0, "gid": 0, "nlink": 1, "bytes": 3, "sha256": "3" * 64,
        },
        "carrier_unit": {
            "name": c.CARRIER_UNIT,
            "control_group": "/system.slice/" + c.CARRIER_UNIT,
            "invocation_id": "4" * 32, "active_state": "active",
            "sub_state": "running", "runtime_max_usec": 800_000_000,
            "timeout_stop_usec": 30_000_000, "memory_max": 1_073_741_824,
            "memory_swap_max": 0, "tasks_max": 128,
            "cpu_quota_per_sec_usec": 1_000_000, "restart": "no",
            "kill_mode": "control-group", "exit_type": "cgroup",
        },
        "process_limits": {
            "cpu_soft": 800, "cpu_hard": 800, "nofile_soft": 256,
            "nofile_hard": 256, "fsize_soft": 67_108_864,
            "fsize_hard": 67_108_864, "umask": 0o077,
        },
    }


def remote_result(cases=None):
    cases = [] if cases is None else cases
    return {
        "schema": c.REMOTE_RESULT_SCHEMA,
        "session_id": c.SESSION_ID,
        "consumption_sha256": "3" * 64,
        "state": "REMOTE_STOP_AND_RETAIN",
        "cases": cases,
        "h01_business_execution": {},
        "h01_result_package": {},
        "usage": {},
        "missing": [],
        "resource_accounting": {},
    }


def not_run_output(consumption_sha256, stdin_bytes):
    accounting, _ = incomplete_fixture()
    cases = [{"index": fixed["index"], "case_id": fixed["case_id"],
              "status": "NOT_RUN", "semantic_pass": False,
              "verdict_path": None, "verdict_sha256": None}
             for fixed in c.CASES]
    result = {
        "schema": c.REMOTE_RESULT_SCHEMA,
        "session_id": c.SESSION_ID, "consumption_sha256": consumption_sha256,
        "state": "REMOTE_STOP_AND_RETAIN", "cases": cases,
        "h01_business_execution": {
            "status": "NOT_RUN", "operation_id": None, "execution_id": None,
            "unit": None, "invocation_id": None, "wait_status": None,
            "business_started": False, "outcome": "NOT_RUN", "evidence_sha256": None,
        },
        "h01_result_package": {
            "status": "NOT_RUN", "result_member": None, "result_sha256": None,
            "required_members_sha256": None,
        },
        "usage": {
            "guest_elapsed_ns": 1, "carrier_cpu_ns": 1,
            "carrier_memory_peak_bytes": 1, "carrier_pids_peak": 1,
            "stdin_bytes_received": stdin_bytes, "output_frame_bytes": 0,
            "guest_allocated_bytes": None, "guest_allocated_inodes": None,
            "job_units_started": 0, "controller_units_started": 0,
            "quota_query_units_started": 0, "dynamic_quota_units_started": 0,
            "native_children_started": 0,
        },
        "resource_accounting": accounting,
        "missing": sorted(accounting["missing"] + [resource_missing("usage/" + key) for key in
            ("guest_allocated_bytes", "guest_allocated_inodes")],
            key=lambda row: (row["code"], row["role"], row["detail_sha256"])),
    }
    manifest = {
        "schema": "local-hand-q2-core-output-package/v1", "session_id": c.SESSION_ID,
        "remote_result": result, "cases": cases, "members": [],
        "limits": dict(e.OUTPUT_LIMITS),
    }
    for _ in range(8):
        raw = e.frame(c.OUTPUT_MAGIC, manifest, json_limit=1_048_576)
        if result["usage"]["output_frame_bytes"] == len(raw):
            return raw
        result["usage"]["output_frame_bytes"] = len(raw)
    raise AssertionError("frame length did not converge")


def test_fixed_remote_tokens_and_wrapper_profile():
    loader = b"pass\n"
    bootstrap = b"x=1\n"
    tokens = e.remote_tokens(loader, bootstrap)
    assert tokens[:11] == [
        "exec", "/usr/bin/sudo", "-n", "--", "/usr/bin/env", "-i",
        "HOME=/root", "PATH=/usr/bin:/bin", "LANG=C", "LC_ALL=C", "SYSTEMD_COLORS=0",
    ]
    assert tokens[-7:-3] == ["/usr/bin/python3", "-I", "-B", "-c"]
    wrapper = (Path(__file__).parents[2] / "labs" / "infra-local-hand-q1" / "vm" / "ssh.sh")
    # CI does not carry the private fixture; use the exact admitted source bytes.
    raw = (b"#!/usr/bin/env bash\nset -euo pipefail\n"
           b"q1_vm=/mnt/data1/work/labs/infra-local-hand-q1/vm\n"
           b"exec ssh -F /dev/null \\\n"
           b"  -i \"$q1_vm/id_ed25519\" -p 22221 \\\n"
           b"  -o IdentitiesOnly=yes -o BatchMode=yes \\\n"
           b"  -o StrictHostKeyChecking=accept-new \\\n"
           b"  -o UserKnownHostsFile=\"$q1_vm/known_hosts\" \\\n"
           b"  -o ConnectTimeout=10 \\\n"
           b"  q1admin@127.0.0.1 \"$@\"\n")
    assert hashlib.sha256(raw).hexdigest() == e.WRAPPER_SHA256
    argv = e.wrapper_argv(str(wrapper), raw, tokens)
    assert argv[:3] == ["/usr/bin/env", "bash", "-c"]
    assert e.argv_digest(argv) == hashlib.sha256(c.canonical({
        "schema": c.CARRIER_ARGV_SCHEMA, "argv": argv,
    }, newline=True)).hexdigest()


def test_controlled_environment_drops_agent_and_startup_injection():
    value = e.controlled_environment({
        "HOME": "/h", "USER": "u", "LOGNAME": "u", "SSH_AUTH_SOCK": "/bad",
        "SSH_AGENT_PID": "42", "BASH_ENV": "/bad", "ENV": "/bad", "PATH": "/bad",
    })
    assert value == {
        "HOME": "/h", "USER": "u", "LOGNAME": "u", "PATH": "/usr/bin:/bin",
        "LANG": "C", "LC_ALL": "C", "SYSTEMD_COLORS": "0",
    }


def test_arg_environment_checks_current_arg_max(monkeypatch):
    monkeypatch.setattr(e.os, "sysconf", lambda name: 8)
    with pytest.raises(c.ContractError, match="CORE_LOCAL_ARG_ENV_LIMIT"):
        e.encoded_argv_environment_size(["/bin/true"], {"LANG": "C"})


def test_consumed_post_locale_release_is_closed_and_requires_exact_digest(monkeypatch):
    raw = Path("tests/e3_host/q2_core_delivery_dispatcher.py").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    manifest = {"entry": {"dispatcher_path": "field/dispatcher.py",
                           "dispatcher_sha256": digest}}
    assert e.RELEASABLE_DISPATCHER_SHA256 == frozenset()
    # The issued 05c digest and a subsequently repaired dispatcher both stay closed.
    assert '714bbb8039aadc3ab58195adde1f61cc273cb4822b46e60de26c2315d459a11b' not in e.RELEASABLE_DISPATCHER_SHA256
    assert '319c651f05998f812ac8faab51a354c7445b584bc6442a26c9800e79ae776e96' not in e.RELEASABLE_DISPATCHER_SHA256
    with pytest.raises(c.ContractError, match="CORE_DELIVERY_RELEASE_GATE"):
        e.field_release_gate(manifest, {"field/dispatcher.py": raw})
    monkeypatch.setattr(e, "RELEASABLE_DISPATCHER_SHA256", frozenset({digest}))
    assert e.dispatcher_contract.field_readiness()["releasable"] is True
    assert e.field_release_gate(manifest, {"field/dispatcher.py": raw}) == {
        "dispatcher_sha256": digest, "releasable": True}
    changed = raw + b"\n# not reviewed\n"
    manifest["entry"]["dispatcher_sha256"] = hashlib.sha256(changed).hexdigest()
    with pytest.raises(c.ContractError, match="CORE_DELIVERY_RELEASE_GATE"):
        e.field_release_gate(manifest, {"field/dispatcher.py": changed})


def test_reviewed_digest_cannot_override_incomplete_readiness(monkeypatch):
    raw = Path("tests/e3_host/q2_core_delivery_dispatcher.py").read_bytes()
    manifest = {"entry": {"dispatcher_path": "field/dispatcher.py",
                           "dispatcher_sha256": hashlib.sha256(raw).hexdigest()}}
    monkeypatch.setattr(e, "RELEASABLE_DISPATCHER_SHA256",
                        frozenset({manifest["entry"]["dispatcher_sha256"]}))
    readiness = e.dispatcher_contract.field_readiness()
    readiness["protocol_blockers"] = ["unresolved"]
    monkeypatch.setattr(e.dispatcher_contract, "field_readiness", lambda: readiness)
    with pytest.raises(c.ContractError, match="CORE_DELIVERY_RELEASE_GATE"):
        e.field_release_gate(manifest, {"field/dispatcher.py": raw})


@pytest.mark.parametrize("changed", [False, True])
def test_deliver_once_checks_release_gate_before_anchor_marker_or_request(
        monkeypatch, tmp_path, changed):
    loader, bootstrap = b"loader\n", b"bootstrap\n"
    dispatcher = Path("tests/e3_host/q2_core_delivery_dispatcher.py").read_bytes()
    if changed:
        dispatcher += b"\n# unreviewed\n"
    else:
        monkeypatch.setattr(e, 'RELEASABLE_DISPATCHER_SHA256', frozenset())
    entry = {"loader_path": "field/loader.py",
             "bootstrap_path": "field/bootstrap.py",
             "dispatcher_path": "field/dispatcher.py",
             "dispatcher_sha256": hashlib.sha256(dispatcher).hexdigest()}
    manifest = {"entry": entry}
    members = {"field/loader.py": loader, "field/bootstrap.py": bootstrap,
               "field/dispatcher.py": dispatcher}
    original_helper = e._helper
    monkeypatch.setattr(e, "_helper", lambda name: (
        SimpleNamespace(parse_package=lambda _raw: (manifest, members))
        if name == "q2_core_delivery_package" else original_helper(name)))
    monkeypatch.setattr(e, "requalify_management_anchor",
                        lambda *_args, **_kwargs: pytest.fail("anchor touched"))
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(c.ContractError, match="CORE_DELIVERY_RELEASE_GATE"):
            e.deliver_once(
                directory_fd, binding={}, package_basename="blocked.lhfp",
                package_raw=b"syntactically-valid-placeholder", loader_raw=loader,
                bootstrap_raw=bootstrap, wrapper_raw=b"", popen_factory=lambda *_a, **_k:
                pytest.fail("request issued"))
        assert list(tmp_path.iterdir()) == []
    finally:
        os.close(directory_fd)


def test_deliver_once_arg_max_failure_precedes_anchor_marker_and_request(
        monkeypatch, tmp_path):
    loader, bootstrap = b"pass\n", b"x=1\n"
    entry = {"loader_path": "field/loader.py",
             "bootstrap_path": "field/bootstrap.py"}
    manifest = {"entry": entry}
    members = {"field/loader.py": loader, "field/bootstrap.py": bootstrap}
    original_helper = e._helper
    monkeypatch.setattr(e, "_helper", lambda name: (
        SimpleNamespace(parse_package=lambda _raw: (manifest, members))
        if name == "q2_core_delivery_package" else original_helper(name)))
    # Reach the existing ARG_MAX check without changing the production allowlist.
    monkeypatch.setattr(e, "field_release_gate", lambda *_args: None)
    environment = e.controlled_environment({
        "HOME": "/synthetic", "USER": "test", "LOGNAME": "test",
    })
    monkeypatch.setattr(e, "controlled_environment", lambda: environment)
    checked = []

    def arg_max(name):
        checked.append(name)
        return 8

    monkeypatch.setattr(e.os, "sysconf", arg_max)

    def forbidden(*_args, **_kwargs):
        pytest.fail("ARG_MAX rejection must precede anchor, marker and request")

    for name in ("requalify_management_anchor", "marker_absent",
                 "output_names_absent", "freeze_host_window",
                 "create_consumption_marker", "execute_carrier_once",
                 "finalize_carrier"):
        monkeypatch.setattr(e, name, forbidden)
    wrapper_raw = (b"#!/usr/bin/env bash\nset -euo pipefail\n"
                   b"q1_vm=/mnt/data1/work/labs/infra-local-hand-q1/vm\n"
                   b"exec ssh -F /dev/null \\\n"
                   b"  -i \"$q1_vm/id_ed25519\" -p 22221 \\\n"
                   b"  -o IdentitiesOnly=yes -o BatchMode=yes \\\n"
                   b"  -o StrictHostKeyChecking=accept-new \\\n"
                   b"  -o UserKnownHostsFile=\"$q1_vm/known_hosts\" \\\n"
                   b"  -o ConnectTimeout=10 \\\n"
                   b"  q1admin@127.0.0.1 \"$@\"\n")
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(c.ContractError, match="CORE_LOCAL_ARG_ENV_LIMIT"):
            e.deliver_once(
                directory_fd,
                binding={"wrapper": {"path": "/synthetic/ssh.sh"}},
                package_basename="lhqcore-20261005c.lhfp", package_raw=b"synthetic-package",
                loader_raw=loader, bootstrap_raw=bootstrap, wrapper_raw=wrapper_raw,
                popen_factory=forbidden)
        assert checked == ["SC_ARG_MAX"]
        assert list(tmp_path.iterdir()) == []
        assert e.RELEASABLE_DISPATCHER_SHA256 == frozenset()
    finally:
        os.close(directory_fd)


def identity(path, sha="a" * 64):
    return {"path": path, "dev": 1, "ino": 2, "mode": 0o755, "uid": 0, "gid": 0,
            "nlink": 1, "bytes": 10, "sha256": sha}


def test_management_binding_discloses_broad_sudo_and_binds_command():
    loader = b"pass\n"
    bootstrap = b"x=1\n"
    tokens = e.remote_tokens(loader, bootstrap)
    wrapper_raw = (b"#!/usr/bin/env bash\nset -euo pipefail\n"
                   b"q1_vm=/mnt/data1/work/labs/infra-local-hand-q1/vm\n"
                   b"exec ssh -F /dev/null \\\n"
                   b"  -i \"$q1_vm/id_ed25519\" -p 22221 \\\n"
                   b"  -o IdentitiesOnly=yes -o BatchMode=yes \\\n"
                   b"  -o StrictHostKeyChecking=accept-new \\\n"
                   b"  -o UserKnownHostsFile=\"$q1_vm/known_hosts\" \\\n"
                   b"  -o ConnectTimeout=10 \\\n"
                   b"  q1admin@127.0.0.1 \"$@\"\n")
    wrapper_path = "/mnt/data1/work/labs/infra-local-hand-q1/vm/ssh.sh"
    argv = e.wrapper_argv(wrapper_path, wrapper_raw, tokens)
    binding = {
        "schema": c.MANAGEMENT_BINDING_SCHEMA,
        "wrapper": identity(wrapper_path, e.WRAPPER_SHA256),
        "fixture_start": identity("/mnt/data1/work/labs/infra-local-hand-q1/vm/start.sh",
                                   e.START_SHA256),
        "fixture_cloud_config": identity(
            "/mnt/data1/work/labs/infra-local-hand-q1/vm/user-data", e.CLOUD_CONFIG_SHA256),
        "profile": "env-bash-literal-ssh-v1",
        "environment": {"HOME": "/home/u", "USER": "u", "LOGNAME": "u",
                        "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                        "SYSTEMD_COLORS": "0"},
        "dependencies": [dict(identity(path), role=role) for role, path in (
            ("env", "/usr/bin/env"), ("bash", "/usr/bin/bash"),
            ("ssh", "/usr/bin/ssh"), ("ssh-keygen", "/usr/bin/ssh-keygen"))],
        "identity": {"path": "/private/id_ed25519", "dev": 1, "ino": 3, "mode": 0o600,
                     "uid": 1000, "gid": 1000, "nlink": 1, "bytes": 399,
                     "derived_public_key_sha256": e.PUBLIC_KEY_SHA256},
        "identity_public": identity("/private/id_ed25519.pub", e.PUBLIC_KEY_SHA256),
        "known_hosts": identity("/private/known_hosts", e.KNOWN_HOSTS_SHA256),
        "cwd": {"path": "/work", "dev": 1, "ino": 4, "mode": 0o755,
                "uid": 1000, "gid": 1000},
        "anchor": {"path": str(Path(wrapper_path).parent), "dev": 1, "ino": 2,
                   "mode": 0o700, "uid": 1000, "gid": 1000, "nlink": 2},
        "writer": {"schema": "local-hand-q2-core-local-writer/v1",
                   "user_namespace": {"dev": 1, "ino": 2}, "pid_namespace": {"dev": 1, "ino": 3},
                   "process": {"pid": 4, "starttime_ticks": 5},
                   "uid": dict.fromkeys(("real", "effective", "saved", "filesystem"), 1000),
                   "gid": dict.fromkeys(("real", "effective", "saved", "filesystem"), 1000),
                   "supplementary_gids": [1000]},
        "remote_expectation": e.static_remote_expectation(tokens),
        "transport": {
            "no_pty": True, "stdin_binary": True, "stdout_stderr_separate": True,
            "known_host_preexisting": True, "batch_mode": True,
            "invocation_matches_frozen_command": True, "sudo_noninteractive": True,
            "sudo_no_password": True, "sudo_policy_is_exact": False,
            "fixture_policy_broader_than_command": True,
        },
    }
    digest = e.local_management_binding_digest(binding, tokens=tokens, argv=argv,
                                         wrapper_raw=wrapper_raw)
    assert digest == hashlib.sha256(c.canonical(binding, newline=True)).hexdigest()
    binding["transport"]["sudo_policy_is_exact"] = True
    with pytest.raises(c.ContractError, match="CORE_MANAGEMENT_TRANSPORT"):
        e.local_management_binding_digest(binding, tokens=tokens, argv=argv,
                                    wrapper_raw=wrapper_raw)


def test_host_window_and_bind_mapping_are_not_refreshed():
    values = iter((10_000, 20_000))
    origins = e.freeze_host_window(lambda _clock: next(values))
    package = b"package"
    entry = {
        "loader_path": "field/loader.py", "loader_bytes": 1,
        "loader_sha256": "1" * 64,
        "bootstrap_path": "field/bootstrap.py", "bootstrap_bytes": 1,
        "bootstrap_sha256": "2" * 64,
        "dispatcher_path": "field/dispatcher.py", "dispatcher_bytes": 1,
        "dispatcher_sha256": "3" * 64,
        "carrier_argv_sha256": "4" * 64,
        "local_management_binding_sha256": "5" * 64,
        "writer": writer(),
    }
    assert set(entry) == e._helper("q2_core_delivery_package").ENTRY_FIELDS
    bind = e.build_bind(hello(), "a" * 64, "lhqcore-20261005c.lhfp", package, origins,
                        package_entry=entry, remote_expectation=remote_expectation(), boot_bind_ns=30_000,
                        mono_bind_ns=40_000)
    assert bind["host_remaining_floor_ns"] == 899_999_000_000
    assert bind["mapped_duration_ns"] == 882_999_000_000
    assert bind["guest_duration_ns"] == 750_000_000_000
    changed = dict(bind,
                   host_boottime_deadline_ns=bind["host_boottime_deadline_ns"] + 1_000_000,
                   host_monotonic_deadline_ns=bind["host_monotonic_deadline_ns"] + 1_000_000)
    with pytest.raises(c.ContractError, match="CORE_BIND_HOST_WINDOW"):
        c.validate_bind(changed)


@pytest.mark.parametrize("change,code", [
    ("missing", "CORE_BIND_PACKAGE_ENTRY"),
    ("extra", "CORE_BIND_PACKAGE_ENTRY"),
    ("invalid", "CORE_LOCAL_WRITER_CREDENTIALS"),
])
def test_bind_rejects_missing_extra_or_invalid_v3_writer(change, code):
    entry = {"loader_path": "field/loader.py", "loader_bytes": 1,
        "loader_sha256": "1" * 64, "bootstrap_path": "field/bootstrap.py",
        "bootstrap_bytes": 1, "bootstrap_sha256": "2" * 64,
        "dispatcher_path": "field/dispatcher.py", "dispatcher_bytes": 1,
        "dispatcher_sha256": "3" * 64, "carrier_argv_sha256": "4" * 64,
        "local_management_binding_sha256": "5" * 64, "writer": writer()}
    assert set(entry) == e._helper("q2_core_delivery_package").ENTRY_FIELDS
    if change == "missing":
        del entry["writer"]
    elif change == "extra":
        entry["unapproved"] = True
    else:
        entry["writer"]["uid"]["effective"] += 1
    origins = e.freeze_host_window(lambda _clock: 10)
    with pytest.raises(c.ContractError, match=code):
        e.build_bind(hello(), "a" * 64, "lhqcore-20261005c.lhfp", b"package", origins,
            package_entry=entry, remote_expectation=remote_expectation(),
            boot_bind_ns=20, mono_bind_ns=20)


def test_frame_rejects_duplicate_and_trailing_json():
    raw = e.frame(c.HELLO_MAGIC, hello(), json_limit=4096)
    value, rest = e.parse_frame(raw, c.HELLO_MAGIC, json_limit=4096, total_limit=4112)
    assert value == hello() and rest == b""
    duplicate = c.HELLO_MAGIC + struct.pack(">Q", 14) + b'{"a":1,"a":2}\n'
    with pytest.raises(c.ContractError, match="CORE_JSON_DUPLICATE_KEY"):
        e.parse_frame(duplicate, c.HELLO_MAGIC, json_limit=4096, total_limit=4112)
    with pytest.raises(c.ContractError, match="CORE_FRAME_BOUNDARY"):
        e.parse_frame(raw + b"x", c.HELLO_MAGIC, json_limit=4096, total_limit=4112)


def marker_value(origins):
    implementation = {"commit": "4" * 40, "tree": "5" * 40}
    writer = e.capture_contract.observe_writer(lambda fn, *args, **kwargs: fn(*args, **kwargs))
    return e.consumption_record(
        amendment=c.make_amendment(implementation), writer=writer,
        approved_inputs_sha256="3" * 64,
        implementation={"commit": "4" * 40, "tree": "5" * 40},
        package={"basename": "lhqcore-20261005c.lhfp", "bytes": 1, "sha256": "6" * 64,
                 "manifest_sha256": "7" * 64},
        local_management_binding_sha256="8" * 64,
        carrier_argv_sha256="9" * 64,
        origins=origins,
    )


def test_marker_is_final_name_exclusive_and_never_replaced(tmp_path):
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        origins = {
            "host_boottime_origin_ns": 1,
            "host_monotonic_origin_ns": 2,
            "host_boottime_deadline_ns": 1 + e.HOST_WINDOW_NS,
            "host_monotonic_deadline_ns": 2 + e.HOST_WINDOW_NS,
        }
        capture = live_capture(directory_fd, tmp_path, origins)
        result = e.create_consumption_marker(directory_fd, marker_value(origins), capture=capture)
        assert result["object_created"] is True and result["record_complete"] is True
        before = (tmp_path / c.MARKER_BASENAME).read_bytes()
        with pytest.raises(e.ConsumedError, match="ALREADY_CONSUMED"):
            e.create_consumption_marker(directory_fd, marker_value(origins), capture=capture)
        assert (tmp_path / c.MARKER_BASENAME).read_bytes() == before
    finally:
        capture.close_handles()
        os.close(directory_fd)


def test_marker_and_bind_reject_refreshed_or_non_exact_host_window():
    origins = {
        "host_boottime_origin_ns": 10,
        "host_monotonic_origin_ns": 20,
        "host_boottime_deadline_ns": 10 + 1_200_000_000_000,
        "host_monotonic_deadline_ns": 20 + 1_200_000_000_000,
    }
    with pytest.raises(c.ContractError, match="CORE_MARKER_HOST_WINDOW"):
        marker_value(origins)
    entry = {
        "loader_path": "field/loader.py", "loader_bytes": 1,
        "loader_sha256": "1" * 64,
        "bootstrap_path": "field/bootstrap.py", "bootstrap_bytes": 1,
        "bootstrap_sha256": "2" * 64,
        "dispatcher_path": "field/dispatcher.py", "dispatcher_bytes": 1,
        "dispatcher_sha256": "3" * 64, "carrier_argv_sha256": "4" * 64,
        "local_management_binding_sha256": "5" * 64,
        "writer": writer(),
    }
    with pytest.raises(c.ContractError, match="CORE_BIND_HOST_WINDOW"):
        e.build_bind(hello(), "a" * 64, "lhqcore-20261005c.lhfp", b"p", origins,
                     package_entry=entry, remote_expectation=remote_expectation(), boot_bind_ns=30, mono_bind_ns=40)


def test_absence_checks_treat_any_existing_type_as_consumed(tmp_path):
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        assert e.marker_absent(directory_fd)
        os.mkdir(tmp_path / c.MARKER_BASENAME)
        with pytest.raises(e.ConsumedError, match="ALREADY_CONSUMED"):
            e.marker_absent(directory_fd)
    finally:
        os.close(directory_fd)


def test_capture_file_is_create_only_and_stable(tmp_path):
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    origins = e.freeze_host_window()
    capture = live_capture(directory_fd, tmp_path, origins)
    try:
        e.create_consumption_marker(directory_fd, marker_value(origins), capture=capture)
        basename = c.OUTPUT_BASENAMES["stderr_basename"]
        item = e.create_capture_file(directory_fd, basename, b"stderr", limit=1024, capture=capture)
        assert item["bytes"] == 6 and item["mode"] == 0o600 and item["nlink"] == 1
        with pytest.raises(e.capture_contract.CaptureError, match="CREATE_ONCE"):
            e.create_capture_file(directory_fd, basename, b"again", limit=1024, capture=capture)
    finally:
        capture.close_handles()
        os.close(directory_fd)


def test_output_frame_checks_order_digest_and_true_eof():
    members = [
        {"path": "carrier/a", "case_id": "carrier", "role": "session", "mode": 384,
         "bytes": 1, "sha256": hashlib.sha256(b"a").hexdigest()},
        {"path": "carrier/b", "case_id": "carrier", "role": "admission", "mode": 384,
         "bytes": 1, "sha256": hashlib.sha256(b"b").hexdigest()},
    ]
    result = remote_result([])
    manifest = {
        "schema": "local-hand-q2-core-output-package/v1",
        "session_id": c.SESSION_ID,
        "remote_result": result,
        "cases": [],
        "members": members,
        "limits": {},
    }
    raw = e.frame(c.OUTPUT_MAGIC, manifest, json_limit=1_048_576) + b"ab"
    checked, values = e.parse_output(raw)
    assert checked == manifest and values == {"carrier/a": b"a", "carrier/b": b"b"}
    with pytest.raises(c.ContractError, match="CORE_OUTPUT_TRAILING"):
        e.parse_output(raw + b"x")
    bad = dict(manifest, members=list(reversed(members)))
    with pytest.raises(c.ContractError, match="CORE_OUTPUT_ORDER"):
        e.parse_output(e.frame(c.OUTPUT_MAGIC, bad, json_limit=1_048_576) + b"ba")


@pytest.mark.parametrize("boundary, remaining", [
    ("stderr", 7), ("stderr", 0), ("combined", 7),
])
def test_carrier_remaining_plus_one_is_rejected_without_capturing_overflow(
        monkeypatch, boundary, remaining):
    # The amendment's 52 MiB stream gate precedes the retained 60 MiB outer
    # refusal. Leave exactly `remaining` combined bytes before the sentinel.
    hello_raw = e.frame(c.HELLO_MAGIC, hello(), json_limit=e.HELLO_JSON_LIMIT)
    stdout_bytes = (e.STREAM_CAPTURE_LIMIT - e.STDERR_LIMIT
                    if boundary == "combined" else len(hello_raw))
    stderr_bytes = e.STDERR_LIMIT - remaining
    segments = [{"role": "stdout", "raw": hello_raw, "bytes": len(hello_raw)}]
    if stdout_bytes > len(hello_raw):
        segments.append({"role": "stdout", "raw": None,
                         "bytes": stdout_bytes - len(hello_raw)})
    segments.extend([
        {"role": "stderr", "raw": None, "bytes": stderr_bytes},
        {"role": "stderr", "raw": b"!" * (remaining + 1),
         "bytes": remaining + 1},
    ])
    reads, calls = [], []

    class Stream:
        def __init__(self, fd):
            self.fd, self.closed = fd, False

        def fileno(self):
            return self.fd

        def close(self):
            self.closed = True

    class Process:
        def __init__(self):
            self.stdin, self.stdout, self.stderr = (Stream(fd) for fd in range(100001, 100004))
            self.returncode = None
            self.terminations = 0

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminations += 1
            self.returncode = -15

        def kill(self):
            pytest.fail("terminated fake carrier must not need another stop")

    process = Process()
    roles = {process.stdout.fd: "stdout", process.stderr.fd: "stderr"}

    class Selector:
        def __init__(self):
            self.registered = {}

        def register(self, fd, events, data):
            self.registered[fd] = SimpleNamespace(fd=fd, data=data)

        def unregister(self, fd):
            del self.registered[fd]

        def select(self, _timeout):
            if process.stdin.fd in self.registered:
                return [(self.registered[process.stdin.fd], e.selectors.EVENT_WRITE)]
            assert segments, "carrier must stop at the overflowing read"
            fd = getattr(process, segments[0]["role"]).fd
            return [(self.registered[fd], e.selectors.EVENT_READ)]

        def close(self):
            self.registered.clear()

    original_read, original_write = os.read, os.write
    original_set_blocking = os.set_blocking

    def read(fd, count):
        if fd not in roles:
            return original_read(fd, count)
        segment = segments[0]
        assert segment["role"] == roles[fd]
        reads.append((roles[fd], count))
        size = min(count, segment["bytes"])
        raw = segment["raw"]
        result = b"x" * size if raw is None else raw[:size]
        segment["bytes"] -= size
        if raw is not None:
            segment["raw"] = raw[size:]
        if not segment["bytes"]:
            segments.pop(0)
        return result

    def write(fd, raw):
        if fd == process.stdin.fd:
            return len(raw)
        return original_write(fd, raw)

    def set_blocking(fd, blocking):
        if fd not in roles and fd != process.stdin.fd:
            original_set_blocking(fd, blocking)

    def factory(*args, **kwargs):
        calls.append((args, kwargs))
        return process

    argv = ["/usr/bin/env", "synthetic-carrier"]
    entry = {
        "loader_path": "field/loader.py", "loader_bytes": 1,
        "loader_sha256": "1" * 64,
        "bootstrap_path": "field/bootstrap.py", "bootstrap_bytes": 1,
        "bootstrap_sha256": "2" * 64,
        "dispatcher_path": "field/dispatcher.py", "dispatcher_bytes": 1,
        "dispatcher_sha256": "3" * 64,
        "carrier_argv_sha256": e.argv_digest(argv),
        "local_management_binding_sha256": "5" * 64,
        "writer": writer(),
    }
    origins = e.freeze_host_window()
    marker = {"object_created": True, "record_complete": True, "sha256": "a" * 64}
    with monkeypatch.context() as io_patch:
        io_patch.setattr(e.os, "read", read)
        io_patch.setattr(e.os, "write", write)
        io_patch.setattr(e.os, "set_blocking", set_blocking)
        exchange = e.execute_carrier_once(
            argv=argv, environment={"LANG": "C"}, cwd="/synthetic",
            origins=origins, marker=marker, package_basename="lhqcore-20261005c.lhfp",
            package_raw=b"synthetic-package", package_entry=entry, remote_expectation=remote_expectation(),
            popen_factory=factory, selector_factory=Selector)
    assert len(calls) == 1
    assert reads[-1] == ("stderr", remaining + 1)
    assert exchange["errors"] == [e._missing(
        "CORE_CARRIER_OUTPUT_LIMIT", "stderr",
        {"stdout": stdout_bytes, "stderr": stderr_bytes, "additional": remaining + 1})]
    assert len(exchange["stdout"]) == stdout_bytes
    assert exchange["stderr"] == b"x" * stderr_bytes
    assert exchange["transport"]["stdin_eof"] is True
    assert process.stdin.closed and process.stdout.closed and process.stderr.closed
    assert process.terminations == 1 and exchange["wait"]["status"] == -15
    if boundary == "combined":
        assert stdout_bytes + stderr_bytes + remaining == e.STREAM_CAPTURE_LIMIT


def test_one_fake_pipe_request_and_not_run_finalization(tmp_path, monkeypatch):
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    origins = e.freeze_host_window()
    capture = live_capture(directory_fd, tmp_path, origins)
    marker = e.create_consumption_marker(directory_fd, marker_value(origins), capture=capture)
    package_raw = b"bounded-package"
    argv = ["/usr/bin/env", "fixed-fake-carrier"]
    entry = {
        "loader_path": "field/loader.py", "loader_bytes": 1,
        "loader_sha256": "1" * 64,
        "bootstrap_path": "field/bootstrap.py", "bootstrap_bytes": 1,
        "bootstrap_sha256": "2" * 64,
        "dispatcher_path": "field/dispatcher.py", "dispatcher_bytes": 1,
        "dispatcher_sha256": "3" * 64,
        "carrier_argv_sha256": e.argv_digest(argv),
        "local_management_binding_sha256": "5" * 64,
        "writer": writer(),
    }
    assert set(entry) == e._helper("q2_core_delivery_package").ENTRY_FIELDS
    environment = {"HOME": "/h", "USER": "u", "LOGNAME": "u",
                   "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                   "SYSTEMD_COLORS": "0"}
    calls = []

    class FakePopen:
        def __init__(self):
            input_read, input_write = os.pipe()
            output_read, output_write = os.pipe()
            error_read, error_write = os.pipe()
            self.stdin = os.fdopen(input_write, "wb", buffering=0)
            self.stdout = os.fdopen(output_read, "rb", buffering=0)
            self.stderr = os.fdopen(error_read, "rb", buffering=0)
            self.returncode = None

            def child():
                try:
                    os.write(output_write, e.frame(c.HELLO_MAGIC, hello(), json_limit=4096))
                    received = bytearray()
                    while True:
                        chunk = os.read(input_read, 65_536)
                        if not chunk:
                            break
                        received.extend(chunk)
                    os.write(output_write, not_run_output(marker["sha256"], len(received)))
                    self.returncode = 0
                finally:
                    os.close(input_read); os.close(output_write); os.close(error_write)

            self.thread = threading.Thread(target=child, daemon=True)
            self.thread.start()

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.thread.join(timeout)
            if self.thread.is_alive():
                raise TimeoutError
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

    def factory(*args, **kwargs):
        calls.append((args, kwargs))
        return FakePopen()

    try:
        exchange = e.execute_carrier_once(
            argv=argv, environment=environment, cwd=str(tmp_path), origins=origins,
            marker=marker, package_basename="lhqcore-20261005c.lhfp", package_raw=package_raw,
            package_entry=entry, remote_expectation=remote_expectation(), popen_factory=factory)
        assert len(calls) == 1
        assert exchange["transport"] == {
            "execve_succeeded": True, "hello_valid": True, "bind_written": True,
            "package_written": True,
            "stdin_bytes_written": exchange["bind_frame_bytes"] + len(package_raw),
            "stdin_eof": True,
        }
        assert exchange["wait"] == {
            "status": 0, "stdout_eof": True, "stderr_eof": True,
            "host_deadline_met": True,
        }
        _, resource_context = incomplete_fixture()
        from core_prior_fixture import triple_fixture as prior_fixture
        from e3_host import q2_core_prior_attempt as prior_module
        prior, _ = prior_fixture(monkeypatch)
        prior_api = e._helper('q2_core_delivery_package')._approved_module().prior_attempt
        monkeypatch.setattr(prior_api, 'PINS', prior_module.PINS)
        monkeypatch.setattr(prior_api, 'TOTAL_BYTES', prior_module.TOTAL_BYTES)
        monkeypatch.setattr(prior_api, 'SECOND_PINS', prior_module.SECOND_PINS)
        monkeypatch.setattr(prior_api, 'SECOND_TOTAL_BYTES', prior_module.SECOND_TOTAL_BYTES)
        monkeypatch.setattr(prior_api, 'THIRD_PINS', prior_module.THIRD_PINS)
        monkeypatch.setattr(prior_api, 'THIRD_TOTAL_BYTES', prior_module.THIRD_TOTAL_BYTES)
        binding = dict(anchor=capture.anchor, writer=capture.writer)
        condition = prior_api.observe_capture_condition(directory_fd, binding=binding, prior=prior,
            diagnostic=prior_api.diagnostic_retention(),
            implementation=resource_context['implementation'], deadline=capture.deadline,
            writer_observer=e.capture_contract.observe_writer)
        expected_context = {"manifest": {key: resource_context[key] for key in ("implementation", "locators")},
                            "hello": hello(), "bind": {"guest_duration_ns": 750_000_000_000},
                            "binding": binding, "approved_inputs_raw": c.canonical(
                                dict(reconciliation=dict(prior_core_attempts=prior,
                                    prior_diagnostic_capture=prior_api.diagnostic_retention())), newline=True)}
        expected_context['manifest']['entry'] = dict(
            local_management_binding_sha256=condition['local_management_binding_sha256'])
        final = e.finalize_carrier(directory_fd, marker=marker, exchange=exchange, capture=capture,
                                   expected_context=expected_context, host_capacity_condition=condition)
        assert final['host_capacity_condition'] is condition
        assert condition['earlier_host_obligations']['bytes'] is None
        assert condition['complete_host_admission_proven'] is False
        assert final["receipt"]["state"] == "STOP_AND_RETAIN"
        assert final["receipt"]["real_task_execution"]["status"] == "NO"
        assert final["receipt"]["result_evidence_collection"]["status"] == "NO"
        assert final["receipt"]["remote_result"]["present"] is True
        assert final["total_allocated_bytes"] <= e.CAPTURE_LIMIT
        assert final["total_inodes"] == 6
        assert final["capture_accounting"]["full_filesystem_peak_proven"] is False
        assert final["capture_accounting"]["created_inodes"] == 6
    finally:
        capture.close_handles()
        os.close(directory_fd)


@pytest.mark.parametrize("late_return", [False, True])
def test_transport_deadline_never_starts_or_retries_late_request(late_return):
    origins = {"host_boottime_origin_ns": 1, "host_monotonic_origin_ns": 2,
               "host_boottime_deadline_ns": 1 + e.HOST_WINDOW_NS,
               "host_monotonic_deadline_ns": 2 + e.HOST_WINDOW_NS}
    expired = not late_return
    calls = []
    def clock(which):
        return (1 if which == time.CLOCK_BOOTTIME else 2) + (e.HOST_WINDOW_NS if expired else 0)
    def factory(*args, **kwargs):
        nonlocal expired
        calls.append((args, kwargs))
        expired = True
        return SimpleNamespace()
    argv = ["/usr/bin/env", "synthetic-carrier"]
    exchange = e.execute_carrier_once(argv=argv, environment={"LANG": "C"}, cwd="/synthetic",
        origins=origins, marker=dict(object_created=True, record_complete=True, sha256="a" * 64),
        package_basename="lhqcore-20261005c.lhfp", package_raw=b"fixture",
        package_entry=dict(carrier_argv_sha256=e.argv_digest(argv)),
        remote_expectation=remote_expectation(),
        popen_factory=factory, clock_gettime_ns=clock,
        selector_factory=lambda: pytest.fail("no later I/O after a late request"))
    assert len(calls) == int(late_return)
    assert exchange["transport"]["execve_succeeded"] is late_return
    assert exchange["wait"]["status"] is None
    assert exchange["wait"]["host_deadline_met"] is False
    assert exchange["errors"][0]["code"] == ("CORE_EXECVE_LATE" if late_return else "CORE_EXECVE_FAILED")


def test_hello_command_digest_must_match_frozen_expectation():
    observed = hello()
    observed["remote_management"]["remote_command_sha256"] = "a" * 64
    raw = bytearray(e.frame(c.HELLO_MAGIC, observed, json_limit=e.HELLO_JSON_LIMIT))
    entry = {"loader_sha256": "1" * 64, "bootstrap_sha256": "2" * 64}
    with pytest.raises(c.ContractError, match="CORE_HELLO_REMOTE_EXPECTATION"):
        e._hello_prefix(raw, entry, remote_expectation())


def test_marker_writer_mismatch_rejected_before_exclusive_create(tmp_path):
    origins = {"host_boottime_origin_ns": 1, "host_monotonic_origin_ns": 2,
               "host_boottime_deadline_ns": 1 + e.HOST_WINDOW_NS,
               "host_monotonic_deadline_ns": 2 + e.HOST_WINDOW_NS}
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    capture = live_capture(directory_fd, tmp_path, origins)
    try:
        record = marker_value(origins)
        record["writer"]["process"]["pid"] += 1
        with pytest.raises(c.ContractError, match="CORE_MARKER_CAPTURE_WRITER"):
            e.create_consumption_marker(directory_fd, record, capture=capture)
        assert list(tmp_path.iterdir()) == []
    finally:
        capture.close_handles()
        os.close(directory_fd)


@pytest.mark.parametrize("expired", [False, True, "writer"])
def test_delivery_never_refreshes_window_or_substitutes_writer(monkeypatch, expired):
    entry = {"loader_path": "field/loader.py", "bootstrap_path": "field/bootstrap.py", "writer": writer()}
    members = {"field/loader.py": b"loader", "field/bootstrap.py": b"bootstrap"}
    original_helper = e._helper
    monkeypatch.setattr(e, "_helper", lambda name: SimpleNamespace(
        parse_package=lambda raw: ({"entry": entry}, members))
        if name == "q2_core_delivery_package" else original_helper(name))
    monkeypatch.setattr(e, "field_release_gate", lambda *_: None)
    monkeypatch.setattr(e, "remote_tokens", lambda *_: ["fixed"])
    monkeypatch.setattr(e, "wrapper_argv", lambda *_: ["/usr/bin/true"])
    monkeypatch.setattr(e, "encoded_argv_environment_size", lambda *_: None)
    environment = e.controlled_environment({
        "HOME": "/synthetic", "USER": "test", "LOGNAME": "test",
    })
    monkeypatch.setattr(e, "controlled_environment", lambda: environment)
    def forbidden(*args, **kwargs):
        pytest.fail("no new window, anchor read, marker or request permitted")
    monkeypatch.setattr(e, "freeze_host_window", forbidden)
    monkeypatch.setattr(e, "requalify_management_anchor", forbidden)
    monkeypatch.setattr(e, "marker_absent", forbidden)
    monkeypatch.setattr(e, "create_consumption_marker", forbidden)
    if expired == "writer": entry["writer"]["process"]["pid"] += 1
    origins = ({"host_boottime_origin_ns": 1, "host_monotonic_origin_ns": 2,
                "host_boottime_deadline_ns": 1 + e.HOST_WINDOW_NS,
                "host_monotonic_deadline_ns": 2 + e.HOST_WINDOW_NS} if expired else None)
    with pytest.raises((c.ContractError, e.capture_contract.CaptureError),
                       match="CORE_DELIVERY_ORIGIN_REQUIRED|CORE_CAPTURE_DEADLINE|CORE_DELIVERY_WRITER_BINDING"):
        e.deliver_once(-1, binding={"wrapper": {"path": "/fixed"}, "anchor": {}, "writer": writer()},
            package_basename="lhqcore-20261005c.lhfp", package_raw=b"fixture", loader_raw=b"loader",
            bootstrap_raw=b"bootstrap", wrapper_raw=b"wrapper", origins=origins,
            clock_gettime_ns=lambda _clock: 2 + e.HOST_WINDOW_NS, popen_factory=forbidden)


def test_output_carrier_requires_frozen_preimages_not_only_member_hashes():
    with pytest.raises(c.ContractError, match="CORE_OUTPUT_FROZEN_CONTEXT_REQUIRED"):
        e._validate_carrier_bindings({}, None)


def test_changed_session_amendment_is_rejected_even_with_recomputed_raw_digest():
    # Isolate the first host-owned cross-binding; actual case verification is
    # separate and cannot be reached by this altered carrier document.
    session = {key: {} for key in c.SCHEMA_FIELDS["local-hand-q2-core-dispatch-session/v2"]}
    session["schema"] = "local-hand-q2-core-dispatch-session/v2"
    session["amendment"] = {"baseline": "different"}
    frozen = {key: {} for key in ("scope", "rule", "baseline", "owner_decision", "closure",
                                  "implementation", "amendment", "entry", "locators")}
    values = {"carrier/session.json": c.canonical(session, newline=True),
              "carrier/admission.json": b"{}\n", "carrier/installation.json": b"{}\n"}
    with pytest.raises(c.ContractError, match="CORE_OUTPUT_SESSION_BINDING"):
        e._validate_carrier_bindings(values, {"manifest": frozen})


@pytest.mark.parametrize("drift", [None, "writer", "marker_bytes", "marker_digest", "bind_marker",
                                  "session_bytes", "session_digest", "package", "clock"])
def test_carrier_return_uses_original_context_for_admission_and_installation(monkeypatch, drift):
    # Synthetic transport documents exercise both real validators. This is not
    # a current guest observation, approved source closure or field execution.
    spec = importlib.util.spec_from_file_location("_host_return_fixture",
        Path(__file__).with_name("test_e3_q2_core_delivery_dispatcher.py"))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    from core_prior_fixture import fixture as prior_fixture
    prior_fixture(monkeypatch, fixture.d, e.dispatcher_contract)
    context = fixture.context()
    frozen = context["manifest"]
    approved_raw = context["members"][fixture.d.APPROVED_INPUTS_PATH]
    approved = c.document(approved_raw, limit=c.APPROVED_INPUTS_LIMIT, newline=True)
    binding = {key: {} for key in c.SCHEMA_FIELDS[c.MANAGEMENT_BINDING_SCHEMA]}
    binding.update(schema=c.MANAGEMENT_BINDING_SCHEMA,
                   remote_expectation=approved["policy_basis"]["remote_expectation"], writer=writer())
    frozen["entry"]["local_management_binding_sha256"] = hashlib.sha256(
        c.canonical(binding, newline=True)).hexdigest()
    marker = host_marker(context)[1]
    context["bind"]["consumption_sha256"] = marker["sha256"]
    effects = fixture.FakeEffects(context)
    admission = effects.admit({})
    installation = effects.install({"manifest": frozen})
    session = fixture.d._session(context, admission, installation)
    expected = {"manifest": frozen, "approved_inputs_raw": approved_raw,
                "binding": binding, "hello": context["hello"], "marker": marker,
                "bind": context["bind"]}
    def documents():
        return {"carrier/session.json": c.canonical(session, newline=True),
                "carrier/admission.json": c.canonical(admission, newline=True),
                "carrier/installation.json": c.canonical(installation, newline=True)}
    if drift:
        if drift == "writer": binding["writer"]["process"]["pid"] += 1
        elif drift == "marker_bytes": marker["bytes"] += 1
        elif drift == "marker_digest": marker["sha256"] = "0" * 64
        elif drift == "bind_marker": context["bind"]["consumption_sha256"] = "0" * 64
        elif drift == "session_bytes": session["consumption"]["bytes"] += 1
        elif drift == "session_digest": session["consumption"]["sha256"] = "0" * 64
        elif drift == "package": context["bind"]["package_sha256"] = "0" * 64
        elif drift == "clock": context["bind"]["host_monotonic_origin_ns"] += 1
        with pytest.raises(c.ContractError): e._validate_carrier_bindings(documents(), expected)
        return
    e._validate_carrier_bindings(documents(), expected)
    installation["members_sha256"] = "0" * 64
    with pytest.raises(e.dispatcher_contract.DispatchError, match="INSTALLATION"):
        e._validate_carrier_bindings(documents(), expected)
    installation["members_sha256"] = hashlib.sha256(c.canonical(frozen["members"])).hexdigest()
    admission["binding"]["hello_sha256"] = "0" * 64
    with pytest.raises(c.ContractError, match="CORE_ADMISSION_BINDING"):
        e._validate_carrier_bindings(documents(), expected)
