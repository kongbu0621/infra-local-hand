"""Isolated synthetic tests. These never connect to a guest or claim field PASS."""
from __future__ import annotations

import ast
import base64
import copy
import io
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tarfile
import time
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only directory descriptors and resource limits", allow_module_level=True)

import resource
from e3_host import q2_core_capacity_capture as c
from e3_host import q2_core_capacity_reader as r


@pytest.fixture(autouse=True)
def private_umask():
    previous = os.umask(0o077)
    yield
    os.umask(previous)


def desc(paths=None):
    return r.canonical(dict(schema="lhq-core-capacity-paths/v1", session=r.SESSION, plan_sha256=r.PLAN_SHA,
        paths=paths or {role: "/fixture/" + role for role in r.ROLES}))


def horizon():
    # Synthetic rows, not historical machine evidence; shared obligations are
    # deliberately distinct from disjoint totals to detect incorrect addition.
    return dict(normalized_placement_rows=[dict(pool_roles=["system", "quota"], full_commitment=dict(bytes=100, inodes=10)),
        dict(pool_roles=["journal", "evidence"], full_commitment=dict(bytes=200, inodes=20))],
        delta_rows=[dict(device_selector=role + "_parent", commitment=dict(bytes=30, inodes=3)) for role in r.ROLES],
        configured_quota_rows=[dict(hard_bytes=400, inode_hard_limit=40)])


def result(source=b"fixture", paths=None):
    paths = paths or r.description(desc())["paths"]
    rows = []
    for index, role in enumerate(r.ROLES):
        values = dict(zip(r.STATVFS, [4096, 4096, 1000000, 900000, 800000, 100000, 90000, 80000, 0, 255]))
        rows.append(dict(role=role, path=paths[role], directory=dict(dev=1, ino=index + 1, mode=stat.S_IFDIR | 0o755, uid=0, gid=0),
            filesystem=dict(uuid="11111111-1111-1111-1111-111111111111", mount=dict(mount_id=1, device=1,
                root="/", path="/", fstype="ext4", source="/dev/fixture", options=["rw"])),
            statvfs=values, available=r.amounts(values), start_ns=2 + index * 2, end_ns=3 + index * 2))
    return dict(schema=r.SCHEMA, session=r.SESSION, status="CURRENT_CAPACITY_OBSERVATION", source_sha256=r.digest(source),
        description_sha256=r.digest(desc(paths)), euid=0, limits=r.LIMITS.copy(), start_ns=1, end_ns=12, rows=rows)


@pytest.mark.parametrize("path", ["relative", "/", "//a", "/a/", "/a//b", "/./a", "/a/../b", "/a\\b",
                                 "/\0", "/中文", "/" + "a" * 512, "/" + "/".join(["a"] * 17)])
def test_path_alias_and_limits(path):
    with pytest.raises(r.ObservationError):
        r.description(desc({role: path for role in r.ROLES}))


def test_path_bounds_preserve_original_path_grammar():
    for path in ("/" + "a" * 511, "/" + "/".join(["a"] * 16), "/a b"):
        c.contract.absolute_path(path)
        assert r.path_value(path)


@pytest.mark.parametrize("kind", ["extra", "missing", "duplicate", "encoding", "plan", "session", "big"])
def test_description_rejected(kind):
    raw = desc()
    value = json.loads(raw)
    if kind == "extra": value["paths"]["extra"] = "/extra"
    elif kind == "missing": del value["paths"]["state"]
    elif kind == "plan": value["plan_sha256"] = "0" * 64
    elif kind == "session": value["session"] = "another"
    raw = r.canonical(value)
    if kind == "duplicate": raw = raw.replace(b'"session":', b'"session":"x","session":')
    elif kind == "encoding": raw = b"\xff"
    elif kind == "big": raw = b" " * 8193
    with pytest.raises((r.ObservationError, ValueError, UnicodeError)):
        r.description(raw)


def test_unpinned_plan_is_not_accepted():
    with pytest.raises(r.ObservationError, match="PLAN_PIN"):
        c.plan_description(b"{}")
    with pytest.raises(r.ObservationError, match="PLAN_ARCHIVE_PIN"):
        c.plan_from_archive(b"anything")


@pytest.fixture
def observation(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir(mode=0o755)
    for role in r.ROLES:
        (root / role).mkdir(mode=0o755)
    device = root.stat().st_dev
    mount = f"1 0 {os.major(device)}:{os.minor(device)} / / rw - ext4 /dev/fixture rw\n".encode()
    calls = []
    def kernel(path, size, check):
        check()
        calls.append(path)
        return mount if path.endswith("mountinfo") else b"pos:\t0\nmnt_id:\t1\n"
    monkeypatch.setattr(r, "kernel_read", kernel)
    monkeypatch.setattr(r, "fs_uuid", lambda fd: "11111111-1111-1111-1111-111111111111")
    obj = r.Observation({role: "/" + role for role in r.ROLES}, lambda: None,
                        root=str(root), owner=os.geteuid(), group=os.getegid())
    yield SimpleNamespace(obj=obj, root=root, calls=calls, mount=mount, kernel=kernel)
    obj.close()


def test_five_samples_ten_fdinfo_two_mountinfo_no_listing(observation, monkeypatch):
    original = os.fstatvfs
    samples = []
    def statvfs(fd):
        samples.append(fd)
        return original(fd)
    monkeypatch.setattr(os, "fstatvfs", statvfs)
    monkeypatch.setattr(os, "scandir", lambda *a: pytest.fail("no listing"))
    monkeypatch.setattr(os, "listdir", lambda *a: pytest.fail("no listing"))
    before = {p: p.stat().st_atime_ns for p in [observation.root, *[observation.root / role for role in r.ROLES]]}
    rows = observation.obj.collect()
    assert len(rows) == len(samples) == 5
    assert observation.calls.count("/proc/self/mountinfo") == 2
    assert sum("fdinfo" in p for p in observation.calls) == 10
    assert before == {p: p.stat().st_atime_ns for p in before}
    assert rows[0]["available"]["bytes"] == rows[0]["statvfs"]["f_bavail"] * rows[0]["statvfs"]["f_frsize"]


@pytest.mark.parametrize("kind", ["symlink", "writable", "mode", "owner", "group", "nofollow_denied"])
def test_directory_protection_without_fallback(observation, monkeypatch, kind):
    path = observation.root / "state"
    if kind == "symlink":
        path.rmdir(); path.symlink_to("quota")
    elif kind == "writable": path.chmod(0o777)
    elif kind == "mode": path.chmod(0o750)
    elif kind == "owner": observation.obj.owner = os.geteuid() + 1
    elif kind == "group": observation.obj.group = os.getegid() + 1
    else:
        original, attempts = os.open, []
        def denied(name, flags, **kw):
            if name == "state":
                attempts.append(flags)
                raise PermissionError()
            return original(name, flags, **kw)
        monkeypatch.setattr(os, "open", denied)
    with pytest.raises((r.ObservationError, OSError)):
        observation.obj.collect()
    if kind == "nofollow_denied":
        assert len(attempts) == 1 and attempts[0] & os.O_NOATIME and attempts[0] & os.O_NOFOLLOW


@pytest.mark.parametrize("kind", ["replace", "overmount", "uuid", "fdinfo", "type", "readonly", "mountroot", "dev"])
def test_changed_identity_rejected(observation, monkeypatch, kind):
    if kind == "replace":
        original = observation.obj.reopen
        def replace():
            path = observation.root / "state"
            path.rename(path.with_name("old")); path.mkdir(mode=0o755)
            original()
        monkeypatch.setattr(observation.obj, "reopen", replace)
    elif kind == "uuid":
        count = 0
        def uuid(fd):
            nonlocal count
            count += 1
            return ("1" if count <= 5 else "2") * 36
        monkeypatch.setattr(r, "fs_uuid", uuid)
    else:
        count = 0
        def kernel(path, size, check):
            nonlocal count
            raw = observation.kernel(path, size, check)
            if kind == "fdinfo" and "fdinfo" in path: return b"mnt_id:\t2\n"
            if path.endswith("mountinfo"):
                count += 1
                if kind == "overmount" and count == 2: return raw.replace(b"1 0", b"2 0")
                if kind == "type": return raw.replace(b"ext4", b"tmpfs")
                if kind == "readonly": return raw.replace(b"rw", b"ro")
                if kind == "mountroot": return raw.replace(b" / / ", b" /sub / ")
                if kind == "dev": return b"1 0 999:1 / / rw - ext4 /dev/test rw\n"
            return raw
        monkeypatch.setattr(r, "kernel_read", kernel)
    with pytest.raises(r.ObservationError): observation.obj.collect()


def test_nonidentity_directory_timestamp_changes_not_quiescence(observation, monkeypatch):
    original = observation.obj.reopen
    def change():
        for role in r.ROLES:
            os.utime(observation.root / role, ns=(123, 456))
        original()
    monkeypatch.setattr(observation.obj, "reopen", change)
    assert len(observation.obj.collect()) == 5


def test_maximum_component_fds_and_incremental_reopen(observation, monkeypatch):
    paths = {}
    for index, role in enumerate(r.ROLES):
        parts = [role] + ["x" + str(j) for j in range(15)]
        path = observation.root
        for name in parts:
            path /= name
            path.mkdir(exist_ok=True, mode=0o755)
        paths[role] = "/" + "/".join(parts)
    observation.obj.paths = paths
    assert len(observation.obj.collect()) == 5 and len(observation.obj.held) == 81


@pytest.mark.parametrize("raw", [b"", b"mnt_id: 1\nmnt_id: 1\n", b"mnt_id: -1", b"x" * 4097])
def test_bad_fdinfo(raw):
    with pytest.raises(r.ObservationError): r.mount_id(raw)


@pytest.mark.parametrize("raw", [b"", b"x" * 1048577, b"1 0 1:1 / / rw ext4 /dev/x rw\n",
                                b"1 0 1:1 / / rw - ext4 /dev/x rw\n" * 2])
def test_bad_mountinfo(raw):
    with pytest.raises(r.ObservationError): r.mounts(raw)


@pytest.mark.parametrize("kind", ["size", "empty", "notproc", "shorts"])
def test_bounded_proc_reader(tmp_path, monkeypatch, kind):
    source = tmp_path / "kernel"
    raw = b"x" * (4097 if kind == "size" else 12)
    source.write_bytes(raw)
    realopen, realstat, realread, realfstat = os.open, os.stat, os.read, os.fstat
    monkeypatch.setattr(os, "open", lambda path, flags: realopen(source, flags))
    monkeypatch.setattr(os, "stat", lambda *a, **kw: realstat(source))
    monkeypatch.setattr(r, "filesystem_type", lambda fd: 1 if kind == "notproc" else 0x9FA0)
    # Source ownership seam for a synthetic regular file only.
    def fakeinfo(info):
        return SimpleNamespace(**{k: getattr(info, k) for k in dir(info) if k.startswith("st_")} | {"st_uid": 0})
    monkeypatch.setattr(os, "fstat", lambda fd: fakeinfo(realfstat(fd)))
    monkeypatch.setattr(os, "stat", lambda *a, **kw: fakeinfo(realstat(source)))
    if kind == "empty": monkeypatch.setattr(os, "read", lambda *a: b"")
    elif kind == "shorts": monkeypatch.setattr(os, "read", lambda fd, n: realread(fd, min(n, 2)))
    if kind in ("size", "notproc"):
        with pytest.raises(r.ObservationError): r.kernel_read("/proc/self/fdinfo/5", 4096, lambda: None)
    else:
        data = r.kernel_read("/proc/self/fdinfo/5", 4096, lambda: None)
        assert data == (b"" if kind == "empty" else raw)
        if kind == "empty":
            with pytest.raises(r.ObservationError): r.mount_id(data)


@pytest.mark.parametrize("kind", ["source", "desc", "uid", "limitbool", "time", "sample", "roles", "fields", "uuid",
                                 "device", "mount", "options", "mode", "available", "number", "duplicate", "trailing"])
def test_host_validator_does_not_promote_malformed_results(kind):
    value = result()
    row = value["rows"][0]
    if kind == "source": value["source_sha256"] = "0" * 64
    elif kind == "desc": value["description_sha256"] = "0" * 64
    elif kind == "uid": value["euid"] = False
    elif kind == "limitbool": value["limits"]["core"] = False
    elif kind == "time": value["end_ns"] = 20_000_000_001
    elif kind == "sample": row["end_ns"] = 99
    elif kind == "roles": value["rows"].reverse()
    elif kind == "fields": row["extra"] = 0
    elif kind == "uuid": row["filesystem"]["uuid"] = "00000000-0000-0000-0000-000000000000"
    elif kind == "device": row["directory"]["dev"] = 2
    elif kind == "mount": row["filesystem"]["mount"]["root"] = "/sub"
    elif kind == "options": row["filesystem"]["mount"]["options"] = ["ro"]
    elif kind == "mode": row["directory"]["mode"] |= 0o022
    elif kind == "available": row["available"]["bytes"] += 1
    elif kind == "number": row["statvfs"]["f_frsize"] = False
    raw = r.canonical(value)
    if kind == "duplicate": raw = raw.replace(b'"euid":0', b'"euid":0,"euid":0')
    elif kind == "trailing": raw += b"{}"
    with pytest.raises((r.ObservationError, ValueError)):
        c.validate_result(raw, r.digest(b"fixture"), desc())


def test_negative_available_is_truthful_not_root_free():
    value = result()
    value["rows"][0]["statvfs"].update(f_bavail=-1, f_favail=-2)
    value["rows"][0]["available"] = r.amounts(value["rows"][0]["statvfs"])
    checked = c.validate_result(r.canonical(value), r.digest(b"fixture"), desc())
    pool = c.compare(checked, horizon())["pools"][0]
    assert pool["bytes"]["available"] == -4096 and pool["inodes"]["available"] == -2
    assert pool["bytes"]["deficit"] == pool["bytes"]["required"] + 4096


@pytest.mark.parametrize("parts", list(c.partitions(["system", "quota", "journal", "evidence"])))
def test_all_fifteen_layouts_full_reservations_and_dedup(parts):
    mapping = {role: index for index, group in enumerate(parts) for role in group}
    mapping["state"] = mapping["install"] = mapping.pop("system")
    pools = c.threshold(horizon(), mapping)
    for category in pools.values():
        assert category["prior"] == [3 * x for x in category["05c"]]
    assert sum(p["quota"][0] for p in pools.values()) == 400
    for roles, size in ((["state", "quota"], 100), (["journal", "evidence"], 200)):
        assert sum(p["snapshot"][0] for p in pools.values()) >= size * len({mapping[x] for x in roles})
    if len(parts) == 1:
        assert next(iter(pools.values()))["05c"] == [289406976, 16512]
        assert next(iter(pools.values()))["snapshot"] == [300, 30]
    if len(parts) == 4:
        expected = {"state": [201326592, 12288], "quota": [55574528, 7808],
                    "journal": [36700160, 5504], "evidence": [96468992, 6272]}
        for role, values in expected.items(): assert pools[mapping[role]]["05c"] == values


@pytest.mark.parametrize("field,delta", [("bytes", 0), ("bytes", -1), ("inodes", -1)])
def test_equality_deficit_and_same_pool_min(field, delta):
    value = result()
    pool = c.compare(value, horizon())["pools"][0]
    for row in value["rows"]:
        row["available"] = {key: pool[key]["required"] for key in ("bytes", "inodes")}
    value["rows"][-1]["available"][field] += delta
    actual = c.compare(value, horizon())["pools"][0]
    assert actual[field]["deficit"] == -delta
    assert actual[field]["available"] == actual[field]["required"] + delta


def test_comparison_original_deadline_and_split():
    ticks = iter([1, 2, 5_000_000_001])
    with pytest.raises(r.ObservationError, match="DEADLINE"):
        c.compare(result(), horizon(), clock=lambda: next(ticks))
    value = result()
    value["rows"][2]["directory"]["dev"] = 2
    with pytest.raises(r.ObservationError, match="SPLIT"):
        c.compare(value, horizon())


def test_transport_is_fixed_quoted_empty_stdin_and_under_budget():
    source = Path(r.__file__).read_bytes()
    argv = c.make_argv("/private/anchor", source, desc())
    options = [argv[i + 1] for i, x in enumerate(argv[:-1]) if x == "-o"]
    for item in ("IdentityAgent=none", "ConnectionAttempts=1", "ConnectTimeout=10", "ControlMaster=no", "ControlPath=none",
                 "StrictHostKeyChecking=yes", "UpdateHostKeys=no", "VerifyHostKeyDNS=no", "ProxyJump=none", "ProxyCommand=none",
                 "ClearAllForwardings=yes", "ForwardAgent=no", "ForwardX11=no", "RequestTTY=no", "PermitLocalCommand=no"):
        assert item in options
    remote = shlex.split(argv[-1])
    assert remote[:5] == ["exec", "/usr/bin/sudo", "-n", "--", "/usr/bin/env"]
    assert remote[-4:] == [base64.b64encode(source).decode(), r.digest(source), base64.b64encode(desc()).decode(), r.digest(desc())]
    assert sum(len(x.encode()) + 1 for x in argv) < 65536
    with pytest.raises(r.ObservationError, match="READER_SIZE"):
        c.make_argv("/private/anchor", b"x" * 32769, desc())


@pytest.fixture
def anchor(tmp_path):
    path = tmp_path / "capture"
    path.mkdir(mode=0o700)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOATIME)
    value = SimpleNamespace(path=str(path), fd=fd, info=c.local.metadata(os.fstat(fd)), writer=c.local.observe_writer(),
                            ssh=0, recheck=lambda **kw: None, capacity=lambda: None)
    def absent(name):
        if os.path.lexists(path / name): raise r.ObservationError("OBJECT_EXISTS")
    value.absent = absent
    yield value
    os.close(fd)


def binding():
    return dict(D="a" * 40, argv=["never-ssh"], environment={}, inputs_sha256="1" * 64,
                retained_sha256="2" * 64, source_set_sha256="3" * 64)


def run(anchor, **kw):
    return c.run_once(anchor, b"fixture", desc(), horizon(), binding(), kw.pop("deadline", c.local.Deadline()), **kw)


@pytest.mark.parametrize("mode", ["valid", "exit", "malformed", "stdout_limit", "stderr_limit"])
def test_local_child_transport_bounded_no_guest(anchor, mode):
    calls = []
    raw = r.canonical(result())
    def child(*args, **kwargs):
        assert kwargs["stdin"] == subprocess.DEVNULL and kwargs["pass_fds"] == (0,)
        assert kwargs["start_new_session"] and args == (["never-ssh"],)
        calls.append(1)
        code = "import os; os.write(1," + repr(raw) + ")"
        if mode.endswith("_limit"): code = "import os; os.write(" + ("1" if mode == "stdout_limit" else "2") + ",b'x'*65537)"
        elif mode == "exit": code += "; raise SystemExit(3)"
        elif mode == "malformed": code = "print('{}')"
        return subprocess.Popen([sys.executable, "-I", "-B", "-c", code], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    value = run(anchor, popen=child)
    assert calls == [1] and value["observation_complete"] == (mode == "valid")
    assert value["remote_supervision_proven"] is False and value["old_commitments_refunded"] is False
    receipt = json.loads((Path(anchor.path) / c.NAMES["receipt"]).read_bytes())
    assert "comparison" not in receipt and value["files"]["receipt"]["bytes"] > 0
    if mode == "valid":
        assert value["comparison"]["state"] == "CONDITIONAL_05C_THRESHOLD_COMPARISON"
    if mode.endswith("_limit"):
        role = mode.split("_")[0]
        assert (Path(anchor.path) / c.NAMES[role]).stat().st_size == 65536
    again = run(anchor, popen=lambda *a, **kw: pytest.fail("no second request"))
    assert again["requests_attempted"] == 0


@pytest.mark.parametrize("kind", ["capacity", "exists", "spawn", "create", "sync", "writer"])
def test_failure_before_or_after_marker_never_retries(anchor, monkeypatch, kind):
    calls = []
    def spawn(*a, **kw):
        calls.append(1)
        raise OSError("secret path")
    if kind == "capacity": anchor.capacity = lambda: r.require(False, "HOST_CAPACITY")
    elif kind == "exists": (Path(anchor.path) / c.NAMES["stdout"]).write_bytes(b"partial")
    elif kind == "writer": anchor.writer = dict(anchor.writer, pid=-1)
    elif kind == "sync": monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("secret")))
    elif kind == "create":
        original = c.Capture.create
        def create(self, role):
            if role == "stdout": raise OSError("secret")
            return original(self, role)
        monkeypatch.setattr(c.Capture, "create", create)
    value = run(anchor, popen=spawn)
    assert len(calls) == (1 if kind == "spawn" else 0)
    assert value["marker_creation_attempted"] == (kind in ("spawn", "create", "sync"))
    assert not value["observation_complete"] and b"secret" not in r.canonical(value)


def test_marker_only_one_winner_and_no_recreation(anchor):
    a, b = c.Capture(anchor, c.local.Deadline()), c.Capture(anchor, c.local.Deadline())
    try:
        a.create("marker")
        with pytest.raises(FileExistsError): b.create("marker")
        with pytest.raises(r.ObservationError, match="REPLAY"): b.create("marker")
    finally:
        a.close(); b.close()


@pytest.mark.parametrize("role", list(c.NAMES))
def test_capture_caps_and_digest_identity(anchor, role, monkeypatch):
    cap = c.Capture(anchor, c.local.Deadline())
    original = os.write
    monkeypatch.setattr(os, "write", lambda fd, raw: original(fd, raw[:3]))
    try:
        cap.create(role)
        cap.write(role, b"abcdef")
        cap.sync()
        with pytest.raises(r.ObservationError, match="LIMIT"): cap.write(role, b"x" * c.CAPS[role])
        os.pwrite(cap.fds[role], b"X", 0)
        with pytest.raises(r.ObservationError, match="DRIFT|DIGEST"): cap.sync()
    finally:
        cap.close()


class Clock:
    seconds = 0
    def __call__(self, clock): return 1_000_000_000 + int(self.seconds * 1e9)


def test_no_eof_at_stop_only_owned_child_killed(anchor, monkeypatch):
    clock, calls = Clock(), []
    deadline = c.local.Deadline(clock)
    original = c.selectors.DefaultSelector.select
    def select(self, timeout):
        events = original(self, min(timeout, .01)); clock.seconds = 55
        return events
    monkeypatch.setattr(c.selectors.DefaultSelector, "select", select)
    monkeypatch.setattr(os, "killpg", lambda *a: pytest.fail("no process group kill"))
    def child(*a, **kw):
        process = subprocess.Popen([sys.executable, "-I", "-B", "-c", "import time; time.sleep(10)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        calls.append(process)
        return process
    value = run(anchor, popen=child, deadline=deadline)
    assert len(calls) == 1 and calls[0].poll() is not None
    assert not value["observation_complete"] and value["reason"] == "DEADLINE"
    assert deadline.remaining(60) == 5 and value["remote_exit"] == "UNKNOWN"


def test_unwaitable_stays_unknown(anchor):
    streams = []
    for _ in range(2):
        readfd, writefd = os.pipe(); os.close(writefd)
        streams.append(os.fdopen(readfd, "rb"))
    killed = []
    def wait(**kw): raise subprocess.TimeoutExpired("synthetic", 0)
    process = SimpleNamespace(stdout=streams[0], stderr=streams[1], poll=lambda: None,
                              kill=lambda: killed.append(True), wait=wait)
    value = run(anchor, popen=lambda *a, **kw: process)
    assert killed == [True] and value["state"] == "UNKNOWN" and value["remote_exit"] == "UNKNOWN"


def test_limits_and_failure_before_data_operations(monkeypatch, capfd):
    limits = {}
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(resource, "setrlimit", lambda key, val: limits.__setitem__(key, val))
    monkeypatch.setattr(resource, "getrlimit", lambda key: limits[key])
    r.configure_limits()
    assert limits == {resource.RLIMIT_CPU: (5, 5), resource.RLIMIT_AS: (134217728, 134217728),
        resource.RLIMIT_NOFILE: (128, 128), resource.RLIMIT_FSIZE: (0, 0), resource.RLIMIT_CORE: (0, 0)}
    with monkeypatch.context() as patch:
        patch.setattr(os, "geteuid", lambda: 1000)
        patch.setattr(os, "open", lambda *a, **kw: pytest.fail("no reads before limits"))
        assert r.main() == 3
    captured = capfd.readouterr()
    assert not captured.out and json.loads(captured.err)["reason"] == "EUID"


def test_source_boundary_and_fixed_authority():
    assert c.A == "1ba20d196facc82cf74aea88e7df3d4fe31e0584" and c.C != c.A
    assert c.SESSION == "lhqcap-20261006a" and len(c.NAMES) == 4
    reader = Path(r.__file__).read_bytes(); runner = Path(c.__file__).read_bytes()
    assert len(reader) <= 32768 and len(runner) <= 65536
    for node in ast.walk(ast.parse(reader)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in ("scandir", "listdir", "Popen", "system", "fork", "unlink", "mkdir")
    for name in ("_capacity_admission(", "FieldEffects", "_cap_charge(", "local.run_once(", "analyze_snapshot("):
        assert name.encode() not in runner


def test_exact_plan_mapping_matches_issued_source_table():
    # Read existing source data only, not its package builder or execution API.
    path = Path(c.__file__).with_name("q2_core_delivery_freeze.py")
    tree = ast.parse(path.read_text())
    table = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "LOCATOR_MAPPING" for t in node.targets))
    assert {role: table[role + "_parent"][1:] for role in r.ROLES} == c.MAPPING


def test_pinned_plan_is_derived_without_reading_other_objects(monkeypatch):
    value = dict(directories=dict(state=dict(path="/var/lib/fixed/old")),
        mounts={role: dict(path="/srv/fixed/" + role) for role in ("quota", "journal", "evidence")},
        candidate=dict(destination="/opt/fixed/runtime"))
    raw = r.canonical(value)
    raw += b" " * (9814 - len(raw))
    monkeypatch.setattr(r, "PLAN_SHA", r.digest(raw))
    actual = r.description(c.plan_description(raw))
    assert actual["paths"]["state"] == "/var/lib/fixed" and actual["paths"]["install"] == "/opt/fixed"
    assert actual["paths"]["quota"] == "/srv/fixed/quota"
    value["directories"]["state"]["path"] = "/var/../alias"
    bad = r.canonical(value); bad += b" " * (9814 - len(bad))
    monkeypatch.setattr(r, "PLAN_SHA", r.digest(bad))
    with pytest.raises(c.contract.ContractError): c.plan_description(bad)


@pytest.mark.parametrize("kind", ["ok", "replace", "hardlink", "symlink", "writable", "digest"])
def test_stable_input_fd_name_noatime_pins(tmp_path, monkeypatch, kind):
    path = tmp_path / "fixed"
    path.write_bytes(b"fixed")
    if kind == "hardlink": os.link(path, path.with_name("alias"))
    elif kind == "symlink":
        path.rename(path.with_name("raw")); path.symlink_to("raw")
    elif kind == "writable": path.chmod(0o666)
    # Only the fixture parent is substituted; production parent traversal remains unchanged.
    monkeypatch.setattr(c.local, "open_directory", lambda path, owner: os.open(path, os.O_PATH | os.O_DIRECTORY))
    inputs = c.Inputs()
    before = path.stat().st_atime_ns
    try:
        if kind in ("ok", "replace"):
            assert inputs.read(path, 5, r.digest(b"fixed"), "fixture") == b"fixed"
            assert path.stat().st_atime_ns == before
            if kind == "replace":
                path.rename(path.with_name("retained")); path.write_bytes(b"fixed")
                with pytest.raises(r.ObservationError, match="DRIFT"): inputs.recheck()
            else: inputs.recheck()
        else:
            with pytest.raises((r.ObservationError, c.local.CaptureError, OSError)):
                inputs.read(path, 5, "0" * 64 if kind == "digest" else r.digest(b"fixed"), "fixture")
    finally:
        inputs.close()


@pytest.mark.parametrize("size,count,good", [(276824064, 80, True), (276824063, 80, False),
                                          (276824064, 79, False), (-1, 80, False)])
def test_host_full_commitment_floor(size, count, good, monkeypatch):
    anchor = object.__new__(c.Anchor)
    anchor.fd, anchor.deadline = 10, c.local.Deadline()
    monkeypatch.setattr(os, "fstatvfs", lambda fd: SimpleNamespace(f_frsize=1, f_bavail=size, f_favail=count))
    if good: anchor.capacity()
    else:
        with pytest.raises(r.ObservationError, match="HOST_CAPACITY"): anchor.capacity()


def test_true_concurrent_marker_exclusion(anchor):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier = Barrier(2)
    def attempt(_):
        cap = c.Capture(anchor, c.local.Deadline())
        try:
            barrier.wait(timeout=2)
            cap.create("marker")
            return True
        except FileExistsError:
            return False
        finally:
            cap.close()
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(attempt, range(2))) == [False, True]


def test_only_directory_uuid_ioctl_no_fallback(monkeypatch):
    import fcntl
    import struct
    calls = []
    def ioctl(fd, request, value, mutate):
        calls.append((fd, request, mutate))
        assert struct.unpack("=II", value[:8]) == (16, 0)
        value[8:] = bytes(range(1, 17))
    monkeypatch.setattr(fcntl, "ioctl", ioctl)
    assert r.fs_uuid(11) == "01020304-0506-0708-090a-0b0c0d0e0f10"
    assert calls == [(11, 0x8008662c, True)]
    monkeypatch.setattr(fcntl, "ioctl", lambda *a: (_ for _ in ()).throw(OSError("unsupported")))
    with pytest.raises(OSError): r.fs_uuid(11)


def test_expired_operation_never_refreshes_reader_clock(observation, monkeypatch):
    ticks = 0
    def check():
        nonlocal ticks
        ticks += 1
        r.require(ticks < 8, "DEADLINE")
    observation.obj.check = check
    with pytest.raises(r.ObservationError, match="DEADLINE"): observation.obj.collect()


def test_late_capture_write_preserved_but_not_success(anchor, monkeypatch):
    clock = Clock(); cap = c.Capture(anchor, c.local.Deadline(clock))
    original = os.write
    def write(fd, raw):
        result = original(fd, raw); clock.seconds = 60
        return result
    try:
        cap.create("marker")
        monkeypatch.setattr(os, "write", write)
        with pytest.raises(c.local.CaptureError, match="DEADLINE"): cap.write("marker", b"retained")
        assert cap.sizes["marker"] == 8
    finally:
        cap.close()


def test_failed_limits_stop_before_reader_io(monkeypatch, capfd):
    with monkeypatch.context() as patch:
        patch.setattr(os, "geteuid", lambda: 0)
        patch.setattr(resource, "setrlimit", lambda *a: (_ for _ in ()).throw(OSError("not supported")))
        patch.setattr(os, "open", lambda *a, **kw: pytest.fail("no data read"))
        assert r.main() == 3
    output = capfd.readouterr()
    assert not output.out and json.loads(output.err)["reason"] == "IO_OR_RUNTIME"
