import base64
import copy
import hashlib
import io
import os
from pathlib import Path
import struct
import shlex
import sys
import time
from types import SimpleNamespace

import pytest
from core_writer_fixture import writer

if not sys.platform.startswith("linux"):
    pytest.skip("Core bootstrap requires Linux resource limits and CLOCK_BOOTTIME",
                allow_module_level=True)

from e3_host import q2_core_delivery_bootstrap as b
from e3_host import q2_core_delivery_package as p


IMPLEMENTATION = {"commit": "b" * 40, "tree": "c" * 40}


def hello(bootstrap_sha):
    remote = {"account": "q1admin", "uid": 1000, "gid": 1000, "home": "/home/q1admin",
              "login_shell": "/bin/bash", "parser_profile": "bash-noninteractive-c-v1",
              "remote_tokens_sha256": "6" * 64, "remote_command_sha256": "7" * 64}
    for index, (name, alias) in enumerate(b.REMOTE_ALIASES.items()):
        remote[name] = {"path": alias, "resolved_path": alias, "symlink_chain": [],
                        "dev": 1, "ino": index + 2, "mode": 0o755, "uid": 0, "gid": 0,
                        "nlink": 1, "bytes": 100, "sha256": "4" * 64}
    return {
        "schema": b.HELLO_SCHEMA, "scope": b.SCOPE, "loader_sha256": b.LOADER_SHA256,
        "bootstrap_sha256": bootstrap_sha, "guest_boot_id": "11111111-2222-3333-4444-555555555555",
        "guest_boottime_origin_ns": time.clock_gettime_ns(time.CLOCK_BOOTTIME),
        "guest_monotonic_origin_ns": time.clock_gettime_ns(time.CLOCK_MONOTONIC),
        "pid": 1234, "uid": 0, "gid": 0, "euid": 0, "egid": 0,
        "remote_management": remote,
        "python": {"path": "/usr/bin/python3", "dev": 1, "ino": 6, "mode": 0o755,
                   "uid": 0, "gid": 0, "nlink": 1, "bytes": 100,
                   "sha256": "4" * 64},
        "carrier_unit": {"name": b.CARRIER_UNIT,
            "control_group": "/system.slice/" + b.CARRIER_UNIT, "invocation_id": "5" * 32,
            "active_state": "active", "sub_state": "running", "runtime_max_usec": 800_000_000,
            "timeout_stop_usec": 30_000_000, "memory_max": 1_073_741_824,
            "memory_swap_max": 0, "tasks_max": 128, "cpu_quota_per_sec_usec": 1_000_000,
            "restart": "no", "kill_mode": "control-group", "exit_type": "cgroup"},
        "process_limits": {"cpu_soft": 800, "cpu_hard": 800, "nofile_soft": 256,
                           "nofile_hard": 256, "fsize_soft": 67_108_864,
                           "fsize_hard": 67_108_864, "umask": 0o077},
    }


def package_fixture(monkeypatch):
    # This fixture exercises independent framing/envelope validation. Historical
    # source reconstruction is covered by the approved-input module tests.
    monkeypatch.setattr(p, "_approved_module", lambda: SimpleNamespace(
        validate=lambda raw: p.c.validate_approved_inputs(p.c.document(
            raw, limit=1048576, newline=True))))
    amendment = p.c.make_amendment(IMPLEMENTATION)
    approved_raw = p.c.canonical({"schema": p.c.APPROVED_INPUTS_SCHEMA, "scope": p.c.SCOPE,
        "amendment": amendment, **{key: {"test_fixture": True} for key in p.c.APPROVED_COMPONENTS}},
        newline=True)
    approved_row, approved_header = p.approved_input_member(approved_raw, amendment=amendment)
    loader = Path("tests/e3_host/q2_core_delivery_loader.py").read_bytes()
    bootstrap = Path("tests/e3_host/q2_core_delivery_bootstrap.py").read_bytes()
    bootstrap_sha = hashlib.sha256(bootstrap).hexdigest()
    dispatcher = (b"class FieldEffects:\n def __init__(self,context): self.context=context\n"
                  b"def dispatch(context,effects): return b'LHCOUT1\\n'\n")
    wheel, projection = b"wheel", b"projection\n"
    wheel_record = {"basename": p.c.WHEEL["basename"], "bytes": len(wheel),
                    "sha256": hashlib.sha256(wheel).hexdigest(), "payload_digest": "d" * 64}
    projection_record = {"basename": p.c.PROJECTION["basename"], "bytes": len(projection),
                         "sha256": hashlib.sha256(projection).hexdigest(), "file_count": 1}
    monkeypatch.setattr(p.c, "WHEEL", wheel_record); monkeypatch.setattr(b, "WHEEL", wheel_record)
    monkeypatch.setattr(p.c, "PROJECTION", projection_record); monkeypatch.setattr(b, "PROJECTION", projection_record)
    rows, field_bytes = p.field_member_blobs(
        loader, bootstrap, dispatcher, implementation_commit=IMPLEMENTATION["commit"])
    rows.append(approved_row)
    candidate, git_head = b"candidate\n", b"4b6e4a7c403362358192086b88679e1326dcb2e1\n"
    rows.extend([
        p.member("candidate/README.md", "candidate-worktree", 0o644, candidate,
                 {"kind": "candidate-blob", "commit": p.c.CANDIDATE["commit"],
                  "path": "README.md", "blob": p._git_blob(candidate)}),
        p.member("candidate/.git/HEAD", "candidate-git-metadata", 0o644, git_head,
                 {"kind": "candidate-git-metadata", "commit": p.c.CANDIDATE["commit"],
                  "git_path": ".git/HEAD"}),
        p.member("artifacts/" + wheel_record["basename"], "wheel", 0o644, wheel,
                 {"kind": "wheel", "basename": wheel_record["basename"],
                  "sha256": wheel_record["sha256"]}),
        p.member("artifacts/" + projection_record["basename"], "projection", 0o644, projection,
                 {"kind": "projection", "basename": projection_record["basename"],
                  "sha256": projection_record["sha256"]}),
    ])
    members = {**field_bytes, "private/approved-inputs.json": approved_raw, "candidate/README.md": candidate,
               "candidate/.git/HEAD": git_head,
               "artifacts/" + wheel_record["basename"]: wheel,
               "artifacts/" + projection_record["basename"]: projection}
    field = {row["path"]: row for row in rows if row["role"] == "field-code"}
    management = "e" * 64
    entry = {"loader_path": "field/loader.py", "loader_bytes": len(loader),
             "loader_sha256": hashlib.sha256(loader).hexdigest(),
             "bootstrap_path": "field/bootstrap.py", "bootstrap_bytes": len(bootstrap),
             "bootstrap_sha256": bootstrap_sha,
             "dispatcher_path": "field/dispatcher.py", "dispatcher_bytes": len(dispatcher),
             "dispatcher_sha256": hashlib.sha256(dispatcher).hexdigest(),
             "carrier_argv_sha256": "f" * 64,
             "local_management_binding_sha256": management, "writer": writer()}
    locators = {"schema": p.c.LOCATORS_SCHEMA, "observation_record_sha256": "1" * 64,
        "source_relation_sha256": "0" * 64, "state_parent": "/fixture/state",
        "quota_parent": "/fixture/quota", "install_parent": "/fixture/install",
        "journal_parent": "/fixture/journal", "evidence_parent": "/fixture/evidence",
        "ordinary_user": "q2job", "ordinary_group": "q2job",
        "user_manager_unit": "user@1100.service", "query_parent_unit": "lhq-query.slice",
        "controller_parent_unit": "lhq-controller.slice",
        "management_parent_unit": "lhq-management.slice",
        "supervisor_parent_unit": "lhq-supervisor.slice",
        "ordinary_parent_unit": "lhq-ordinary.slice",
        "retained_ordinary_parent_path": "/system.slice/lhq-retained.slice",
        "carrier_unit": p.c.CARRIER_UNIT}
    locators["source_relation_sha256"] = p.c.sha256(p.c.canonical(
        p.locator_relation(locators, management)))
    manifest = p.make_manifest(implementation=IMPLEMENTATION, entry=entry,
                               amendment=amendment, approved_inputs=approved_header,
                               locators=locators, members=rows)
    package = p.build_package(manifest, members)
    return bootstrap_sha, package


def input_stream(hello_value, package, *, trailing=b""):
    hello_raw = b.encoded(hello_value)
    origin = 1_000_000_000_000
    bind_at = origin + 1_000_000_000
    deadline = origin + 900_000_000_000
    floor = (deadline - bind_at) // 1_000_000 * 1_000_000
    value = {"schema": b.BIND_SCHEMA, "scope": b.SCOPE, "session_id": b.SESSION_ID,
        "hello_sha256": b.sha(hello_raw), "consumption_sha256": "2" * 64,
        "package_basename": "frozen.lhfp", "package_bytes": len(package),
        "package_sha256": b.sha(package), "host_boottime_origin_ns": origin,
        "host_monotonic_origin_ns": origin, "host_boottime_deadline_ns": deadline,
        "host_monotonic_deadline_ns": deadline, "host_boottime_bind_ns": bind_at,
        "host_monotonic_bind_ns": bind_at, "host_remaining_floor_ns": floor,
        "clock_margin_ns": 2_000_000_000, "local_final_reserve_ns": 15_000_000_000,
        "mapped_duration_ns": floor - 17_000_000_000,
        "guest_duration_cap_ns": 750_000_000_000,
        "guest_duration_ns": min(floor - 17_000_000_000, 750_000_000_000)}
    raw = b.encoded(value)
    return io.BytesIO(b.BIND_MAGIC + struct.pack(">Q", len(raw)) + raw + package + trailing)


def test_bootstrap_validates_complete_input_before_dispatch_and_writes_two_frames(monkeypatch):
    bootstrap_sha, package = package_fixture(monkeypatch)
    h = hello(bootstrap_sha); output = io.BytesIO(); called = []
    def dispatch(context):
        called.append(context)
        return b.OUTPUT_MAGIC
    context = b.serve(stdin=input_stream(h, package), stdout=output,
                      bootstrap_sha256=bootstrap_sha, hello_factory=lambda _: h,
                      dispatch=dispatch)
    assert called == [context]
    assert context["schema"] == b.CONTEXT_SCHEMA
    assert all(isinstance(value, memoryview) and value.readonly
               for value in context["members"].values())
    assert context["members"]["field/bootstrap.py"] == Path(
        "tests/e3_host/q2_core_delivery_bootstrap.py").read_bytes()
    raw = output.getvalue()
    assert raw.startswith(b.HELLO_MAGIC)
    length = struct.unpack(">Q", raw[len(b.HELLO_MAGIC):len(b.HELLO_MAGIC) + 8])[0]
    assert raw[len(b.HELLO_MAGIC) + 8 + length:] == b.OUTPUT_MAGIC


def test_bootstrap_refuses_trailing_stdin_without_dispatch(monkeypatch):
    bootstrap_sha, package = package_fixture(monkeypatch); h = hello(bootstrap_sha)
    called = []
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_PACKAGE_EOF"):
        b.serve(stdin=input_stream(h, package, trailing=b"x"), stdout=io.BytesIO(),
                bootstrap_sha256=bootstrap_sha, hello_factory=lambda _: h,
                dispatch=lambda context: called.append(context))
    assert called == []


def test_bootstrap_bind_rejects_refreshed_host_window(monkeypatch):
    bootstrap_sha, package = package_fixture(monkeypatch)
    h = hello(bootstrap_sha)
    stream = input_stream(h, package)
    assert stream.read(len(b.BIND_MAGIC)) == b.BIND_MAGIC
    length = struct.unpack(">Q", stream.read(8))[0]
    value = b.document(stream.read(length), 4096)
    value["host_boottime_deadline_ns"] += 300_000_000_000
    value["host_monotonic_deadline_ns"] += 300_000_000_000
    value["host_remaining_floor_ns"] += 300_000_000_000
    value["mapped_duration_ns"] += 300_000_000_000
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_BIND_MAPPING"):
        b.validate_bind(value, b.encoded(h))


def test_deadline_checked_before_and_after_non_fd_stream_io(monkeypatch):
    values = {time.CLOCK_BOOTTIME: 9, time.CLOCK_MONOTONIC: 9}
    monkeypatch.setattr(b.time, "clock_gettime_ns", lambda clock: values[clock])
    assert b._read_exact(io.BytesIO(b"x"), 1, (10, 10)) == b"x"
    values[time.CLOCK_BOOTTIME] = 10
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_DEADLINE"):
        b._read_exact(io.BytesIO(b"x"), 1, (10, 10))


def test_bootstrap_refuses_mutated_member_before_dispatch(monkeypatch):
    bootstrap_sha, package = package_fixture(monkeypatch); h = hello(bootstrap_sha)
    changed = bytearray(package); changed[-1] ^= 1
    called = []
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_(MEMBER_BYTES|APPROVED_INPUTS)"):
        b.serve(stdin=input_stream(h, bytes(changed)), stdout=io.BytesIO(),
                bootstrap_sha256=bootstrap_sha, hello_factory=lambda _: h,
                dispatch=lambda context: called.append(context))
    assert called == []


def test_dispatcher_without_executable_effect_surface_fails_closed():
    context = {"members": {"field/dispatcher.py": b"def dispatch(context,effects): return b'LHCOUT1\\n'\n"}}
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_DISPATCHER_ABI"):
        b._execute(context)


def test_bootstrap_main_reports_bounded_code_and_never_synthesizes_output(monkeypatch):
    bootstrap_sha, package = package_fixture(monkeypatch); h = hello(bootstrap_sha)
    out, err = io.BytesIO(), io.BytesIO()
    status = b.main(input_stream(h, package, trailing=b"x"), out, err,
                    bootstrap_sha256=bootstrap_sha, hello_factory=lambda _: h,
                    dispatch=lambda _context: pytest.fail("dispatch called"))
    assert status == 3
    assert out.getvalue().startswith(b.HELLO_MAGIC)
    assert b.OUTPUT_MAGIC not in out.getvalue()
    assert err.getvalue() == b"CORE_BOOTSTRAP_PACKAGE_EOF\n"


def test_bootstrap_blob_and_loader_binding_fit_approved_limits():
    bootstrap = Path("tests/e3_host/q2_core_delivery_bootstrap.py").read_bytes()
    loader = Path("tests/e3_host/q2_core_delivery_loader.py").read_bytes()
    assert 0 < len(bootstrap) <= 49152
    assert 0 < len(loader) <= 8192
    assert hashlib.sha256(loader).hexdigest() == b.LOADER_SHA256


def _temporary_program_root(tmp_path, monkeypatch):
    """Model a guest root with user-owned real FDs and unchanged open flags.

    The ordinary CI user cannot O_NOATIME-open the machine's actual root.
    Redirect only the synthetic '/' to this test directory, not production
    reads; simulate guest ownership while retaining real inode/content checks.
    """
    original_stat, original_fstat, original_open = os.stat, os.fstat, os.open
    def root_record(info):
        values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
        values.update(st_uid=0, st_gid=0)
        return SimpleNamespace(**values)
    def rooted_stat(path, *args, **kwargs):
        return root_record(original_stat(tmp_path if path == "/" else path, *args, **kwargs))
    def rooted_open(path, flags, *args, **kwargs):
        return original_open(tmp_path if path == "/" else path, flags, *args, **kwargs)
    monkeypatch.setattr(b.os, "stat", rooted_stat)
    monkeypatch.setattr(b.os, "fstat", lambda *args, **kwargs: root_record(original_fstat(*args, **kwargs)))
    monkeypatch.setattr(b.os, "open", rooted_open)


def test_held_program_resolves_relative_and_absolute_aliases_without_follow_open(tmp_path, monkeypatch):
    program = tmp_path / "program"
    program.write_bytes(b"fixed-program-content")
    program.chmod(0o755)
    alias = tmp_path / "alias"
    alias.symlink_to("program")
    outer = tmp_path / "outer"
    outer.symlink_to("/alias")
    _temporary_program_root(tmp_path, monkeypatch)
    original_open = os.open; opens = []
    def checked_open(path, flags, *args, **kwargs):
        opens.append((path, flags))
        assert flags & os.O_NOFOLLOW and flags & os.O_NOATIME
        return original_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(b.os, "open", checked_open)
    value = b._program("/outer")
    assert value["path"] == "/outer" and value["resolved_path"] == "/program"
    assert value["symlink_chain"] == [{"path": "/outer", "target": "/alias"},
                                       {"path": "/alias", "target": "program"}]
    assert value["sha256"] == b.sha(b"fixed-program-content")
    assert opens


@pytest.mark.parametrize("case", ["parent", "loop", "nine_hops", "magic"])
def test_held_program_refuses_unsafe_aliases(tmp_path, monkeypatch, case):
    program = tmp_path / "program"; program.write_bytes(b"program"); program.chmod(0o755)
    alias = tmp_path / "alias"
    if case == "parent": alias.symlink_to("../program")
    elif case == "loop": alias.symlink_to("alias")
    elif case == "magic": alias.symlink_to("/proc/self/exe")
    else:
        alias.symlink_to("link0")
        for index in range(8):
            (tmp_path / f"link{index}").symlink_to(f"link{index + 1}" if index < 7 else "program")
    _temporary_program_root(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_(ALIAS|MAGIC_LINK)"):
        b._program("/alias")


def test_held_program_detects_alias_retarget_after_read(tmp_path, monkeypatch):
    first = tmp_path / "first"; first.write_bytes(b"first"); first.chmod(0o755)
    second = tmp_path / "second"; second.write_bytes(b"second"); second.chmod(0o755)
    alias = tmp_path / "alias"; alias.symlink_to("first")
    _temporary_program_root(tmp_path, monkeypatch)
    read = os.read; changed = False
    def changed_read(fd, maximum):
        nonlocal changed
        raw = read(fd, maximum)
        if raw and not changed:
            alias.unlink(); alias.symlink_to("second"); changed = True
        return raw
    monkeypatch.setattr(b.os, "read", changed_read)
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_ALIAS_DRIFT"):
        b._program("/alias")


def test_held_program_does_not_fallback_when_noatime_open_denied(tmp_path, monkeypatch):
    path = tmp_path / "program"; path.write_bytes(b"program"); path.chmod(0o755)
    _temporary_program_root(tmp_path, monkeypatch)
    original = os.open; attempts = []
    def denied(name, flags, *args, **kwargs):
        if name == "program":
            attempts.append(flags); raise PermissionError("NOATIME denied")
        return original(name, flags, *args, **kwargs)
    monkeypatch.setattr(b.os, "open", denied)
    with pytest.raises(PermissionError): b._program("/program")
    assert len(attempts) == 1 and attempts[0] & os.O_NOATIME


def test_jit_command_digests_reconstruct_the_same_fixed_vector(monkeypatch):
    from e3_host import q2_core_delivery_entry as entry
    loader = Path("tests/e3_host/q2_core_delivery_loader.py").read_bytes()
    bootstrap = Path("tests/e3_host/q2_core_delivery_bootstrap.py").read_bytes()
    digest = b.sha(bootstrap); encoded = base64.b64encode(bootstrap).decode("ascii")
    original = ["/usr/bin/python3", "-I", "-B", "-c", loader.decode("utf-8"), encoded, digest]
    monkeypatch.setattr(b.sys, "orig_argv", original)
    monkeypatch.setattr(b.sys, "argv", ["-c", encoded, digest])
    tokens = entry.remote_tokens(loader, bootstrap)
    assert b._remote_command_digests(digest) == (
        b.sha(b.encoded(tokens, newline=False)), b.sha(shlex.join(tokens).encode("utf-8")))
    original[4] += "\n"
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_INVOKED_LOADER"):
        b._remote_command_digests(digest)


def test_hello_v2_alias_projection_limit_and_old_schema_rejection():
    value = hello("1" * 64)
    value["remote_management"]["python"].update(resolved_path="/usr/bin/python3.12",
        symlink_chain=[{"path": "/usr/bin/python3", "target": "python3.12"}])
    value["python"]["path"] = "/usr/bin/python3.12"
    assert b.validate_hello(value, "1" * 64) == value
    assert len(b.encoded(value)) <= 4096
    invalid = copy.deepcopy(value); invalid["python"]["path"] = "/usr/bin/python3"
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_PYTHON_PROJECTION"):
        b.validate_hello(invalid, "1" * 64)
    invalid = copy.deepcopy(value); invalid["schema"] = "local-hand-q2-core-carrier-hello/v1"
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_HELLO_AUTHORITY"):
        b.validate_hello(invalid, "1" * 64)
    invalid = copy.deepcopy(value)
    invalid["remote_management"]["shell"]["resolved_path"] = "/" + "x" * 4000
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_HELLO_LIMIT"):
        b.validate_hello(invalid, "1" * 64)


@pytest.mark.parametrize("mutation", ["schema", "v2", "writer_missing", "writer_extra", "writer_invalid",
                                      "amendment", "mode", "source_relation", "legacy_entry"])
def test_standalone_package_rejects_mixed_or_unbound_v3(monkeypatch, mutation):
    bootstrap_sha, raw = package_fixture(monkeypatch)
    manifest, members = b.parse_package(raw, bootstrap_sha)
    if mutation == "schema": manifest["schema"] = "local-hand-q2-core-field-package/v1"
    elif mutation == "v2": manifest["schema"] = "local-hand-q2-core-field-package/v2"
    elif mutation == "writer_missing": manifest["entry"].pop("writer")
    elif mutation == "writer_extra": manifest["entry"]["writer_hash"] = "0" * 64
    elif mutation == "writer_invalid": manifest["entry"]["writer"]["process"]["pid"] = True
    elif mutation == "amendment": manifest["amendment"]["closure"]["commit"] = "f" * 40
    elif mutation == "mode":
        next(row for row in manifest["members"] if row["role"] == "approved-inputs")["mode"] = 0o644
    elif mutation == "source_relation": manifest["approved_inputs"]["approved_source_relation_sha256"] = "0" * 64
    else:
        manifest["entry"]["management_entry_binding_sha256"] = manifest["entry"].pop("local_management_binding_sha256")
    encoded = b.encoded(manifest)
    changed = b.PACKAGE_MAGIC + struct.pack(">Q", len(encoded)) + encoded
    changed += b"".join(members[row["path"]] for row in manifest["members"])
    with pytest.raises(ValueError): b.parse_package(changed, bootstrap_sha)


def test_account_collector_uses_one_current_record_and_refuses_wrong_home(monkeypatch):
    calls = []
    def lookup(name):
        calls.append(name)
        return SimpleNamespace(pw_name=name, pw_uid=1000, pw_gid=1000,
                               pw_dir="/changed", pw_shell="/bin/bash")
    monkeypatch.setattr(b.pwd, "getpwnam", lookup)
    monkeypatch.setattr(b, "_program", lambda *_: pytest.fail("program collection after wrong account"))
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_ACCOUNT"):
        b.collect_remote_management("1" * 64)
    assert calls == ["q1admin"]


def test_held_program_refuses_fifo_before_open(tmp_path, monkeypatch):
    path = tmp_path / "program"; os.mkfifo(path)
    _temporary_program_root(tmp_path, monkeypatch)
    original = os.open
    def checked(name, flags, *args, **kwargs):
        assert name != "program", "must reject FIFO before a potentially blocking open"
        return original(name, flags, *args, **kwargs)
    monkeypatch.setattr(b.os, "open", checked)
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_PROGRAM"):
        b._program("/program")
