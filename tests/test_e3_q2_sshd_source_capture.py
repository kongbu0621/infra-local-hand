"""Offline fixtures only; no guest, real marker, SSH session or field PASS."""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux descriptor and resource limits", allow_module_level=True)

import resource

PATH = Path(__file__).parent / "e3_host" / "q2_sshd_source_capture.py"
spec = importlib.util.spec_from_file_location("_sshd_capture_test", PATH)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
r = c.reader


@pytest.fixture(autouse=True)
def private_test_umask():
    old = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(old)


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "root"
    ssh = root / "etc" / "ssh"
    ssh.mkdir(parents=True)
    (ssh / "sshd_config").write_bytes(b"Include /etc/ssh/sshd_config.d/*.conf\nAcceptEnv LANG LC_*\n")
    (ssh / "sshd_config.d").mkdir()
    return root


def collect(tree, check=lambda: None):
    fd = os.open(tree, os.O_RDONLY | os.O_DIRECTORY | os.O_NOATIME)
    snapshot = r.Snapshot(fd, check, owner=os.geteuid())
    try:
        return snapshot.collect()
    finally:
        snapshot.close()
        os.close(fd)


def envelope(snapshot):
    # Synthetic metadata for testing the host validator, NOT machine evidence.
    value = copy.deepcopy(snapshot)
    for file in value["files"]:
        for stage in ("before", "after", "final"):
            file[stage]["uid"] = 0
    value.update(schema=r.SCHEMA, session=r.SESSION, source_sha256="1" * 64, euid=0,
                 limits=r.LIMITS.copy(), elapsed_ns=1, status="COMPLETE")
    return value


def test_snapshot_exact_bytes_sorted_and_nonselected_untouched(tree):
    directory = tree / "etc/ssh/sshd_config.d"
    (directory / "z.conf").write_bytes(b"\xff\x00\r\n")
    (directory / "a.conf").write_bytes(b"Match User somebody\n")
    (directory / "not-selected").symlink_to("/nonexistent")
    result = collect(tree)
    assert [x["path"] for x in result["files"]] == [r.MAIN, r.DIRECTORY + "/a.conf", r.DIRECTORY + "/z.conf"]
    assert base64.b64decode(result["files"][-1]["base64"]) == b"\xff\x00\r\n"
    assert c.validate_snapshot(c.canonical(envelope(result)), "1" * 64)[r.MAIN].endswith(b"LC_*\n")


def test_optional_directory_absent(tree):
    (tree / "etc/ssh/sshd_config.d").rmdir()
    assert collect(tree)["directory"] == {"state": "ABSENT", "names": []}


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "directory", "writable", "missing"])
def test_bad_main_refused_before_read(tree, kind):
    path = tree / "etc/ssh/sshd_config"
    if kind == "symlink":
        path.unlink()
        path.symlink_to("/nonexistent")
    elif kind == "hardlink":
        os.link(path, path.with_name("alias"))
    elif kind == "fifo":
        path.unlink()
        os.mkfifo(path)
    elif kind == "directory":
        path.unlink()
        path.mkdir()
    elif kind == "writable":
        path.chmod(0o666)
    else:
        path.unlink()
    with pytest.raises(r.CaptureError):
        collect(tree)


@pytest.mark.parametrize("component", ["etc", "etc/ssh", "etc/ssh/sshd_config.d"])
def test_writable_parent_refused(tree, component):
    (tree / component).chmod(0o777)
    with pytest.raises(r.CaptureError, match="PROTECTION"):
        collect(tree)


@pytest.mark.parametrize("size", [0, 262144, 262145])
def test_file_size_boundary(tree, size):
    (tree / "etc/ssh/sshd_config").write_bytes(b"x" * size)
    if size > 262144:
        with pytest.raises(r.CaptureError, match="FILE_LIMIT"):
            collect(tree)
    else:
        assert collect(tree)["files"][0]["bytes"] == size


@pytest.mark.parametrize("count", [64, 65, 256, 257])
def test_directory_and_selected_boundaries(tree, count):
    directory = tree / "etc/ssh/sshd_config.d"
    suffix = ".conf" if count < 100 else ".ignored"
    for i in range(count):
        (directory / (str(i) + suffix)).touch()
    if count in (65, 257):
        with pytest.raises(r.CaptureError, match="FILE_COUNT|DIRECTORY_LIMIT"):
            collect(tree)
    else:
        assert len(collect(tree)["directory"]["names"]) == count


@pytest.mark.parametrize("extra", [False, True])
def test_total_limit(tree, extra):
    main = tree / "etc/ssh/sshd_config"
    main.write_bytes(b"x" * 262144)
    for i in range(3):
        (main.parent / "sshd_config.d" / f"{i}.conf").write_bytes(b"x" * 262144)
    if extra:
        (main.parent / "sshd_config.d/extra.conf").write_bytes(b"x")
        with pytest.raises(r.CaptureError, match="TOTAL_LIMIT"):
            collect(tree)
    else:
        assert sum(x["bytes"] for x in collect(tree)["files"]) == 1048576


def test_nonascii_directory_name_rejected(tree):
    (tree / "etc/ssh/sshd_config.d/非.conf").touch()
    with pytest.raises(r.CaptureError, match="DIRECTORY_LIMIT"):
        collect(tree)


def test_noatime_denial_has_no_fallback(tree, monkeypatch):
    original = os.open
    attempted = []
    def denied(path, flags, *args, **kwargs):
        if path == "sshd_config":
            attempted.append(flags)
            raise PermissionError("private detail")
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", denied)
    with pytest.raises(PermissionError):
        collect(tree)
    assert len(attempted) == 1 and attempted[0] & os.O_NOATIME


@pytest.mark.parametrize("what", ["name", "content", "listing", "absence"])
def test_final_drift_rejected(tree, monkeypatch, what):
    original = r.Snapshot.recheck
    main = tree / "etc/ssh/sshd_config"
    directory = main.parent / "sshd_config.d"
    if what == "absence":
        directory.rmdir()
    changed = False
    def recheck(self):
        nonlocal changed
        if not changed:
            changed = True
            if what == "name":
                main.rename(main.with_name("old"))
                main.write_bytes(b"changed")
            elif what == "content":
                main.write_bytes(b"changed")
            elif what == "listing":
                (directory / "new.conf").touch()
            else:
                directory.mkdir()
        return original(self)
    monkeypatch.setattr(r.Snapshot, "recheck", recheck)
    with pytest.raises(r.CaptureError, match="DRIFT"):
        collect(tree)


def test_reader_time_checks(tree):
    count = 0
    def check():
        nonlocal count
        count += 1
        r.require(count < 5, "DEADLINE")
    with pytest.raises(r.CaptureError, match="DEADLINE"):
        collect(tree, check)


@pytest.mark.parametrize("mutation", ["extra", "duplicate", "trailing", "encoding", "elapsed", "uid", "limitbool",
                                     "source", "count", "path", "sha", "base64", "size", "metadata", "unknown"])
def test_invalid_results_cannot_pass(tree, mutation):
    value = envelope(collect(tree))
    if mutation == "extra": value["extra"] = 0
    elif mutation == "elapsed": value["elapsed_ns"] = 20_000_000_000
    elif mutation == "uid": value["euid"] = False
    elif mutation == "limitbool": value["limits"]["core"] = False
    elif mutation == "source": value["source_sha256"] = "2" * 64
    elif mutation == "count": value["files"] = []
    elif mutation == "path": value["files"][0]["path"] = "/etc/shadow"
    elif mutation == "sha": value["files"][0]["sha256"] = "0" * 64
    elif mutation == "base64": value["files"][0]["base64"] = "!"
    elif mutation == "size": value["files"][0]["bytes"] = 262145
    elif mutation == "metadata": value["files"][0]["final"]["ino"] += 1
    elif mutation == "unknown": value["status"] = "UNKNOWN"
    raw = c.canonical(value)
    if mutation == "duplicate": raw = raw.replace(b'"euid":0', b'"euid":0,"euid":0')
    elif mutation == "trailing": raw += b"{}"
    elif mutation == "encoding": raw = b"\xff"
    with pytest.raises((r.CaptureError, ValueError, UnicodeError)):
        c.validate_snapshot(raw, "1" * 64)


def test_fixed_argv_has_no_business_or_transport_fallback():
    argv = c.make_argv("/private/anchor", b"pass\n")
    options = [argv[i + 1] for i, v in enumerate(argv[:-1]) if v == "-o"]
    for value in ("StrictHostKeyChecking=yes", "ConnectionAttempts=1", "ControlPath=none", "UpdateHostKeys=no",
                  "BatchMode=yes", "ProxyCommand=none", "RequestTTY=no", "IdentityAgent=none"):
        assert value in options
    assert argv[-2] == "q1admin@127.0.0.1"
    assert "systemd-run" not in argv[-1] and "sshd -T" not in argv[-1]
    assert "-I -B" in argv[-1] and "/usr/bin/sudo -n --" in argv[-1]


def test_source_limit():
    with pytest.raises(c.CaptureError, match="READER_SIZE"):
        c.make_argv("/private/anchor", b"x" * 32768)


@pytest.mark.parametrize("hashed", [False, True])
def test_known_hosts_existing_target(hashed):
    name = b"[127.0.0.1]:22221"
    if hashed:
        salt = b"s" * 20
        mac = c.hmac.new(salt, name, hashlib.sha1).digest()
        name = b"|1|" + base64.b64encode(salt) + b"|" + base64.b64encode(mac)
    c.known_endpoint(name + b" ssh-ed25519 dummy\n")
    with pytest.raises(c.CaptureError):
        c.known_endpoint(b"some-other-host ssh-ed25519 dummy\n")


class Clock:
    seconds = 0
    def __call__(self, _):
        return 1_000_000_000 + int(self.seconds * 1e9)


def test_original_two_clock_deadline_does_not_refresh():
    clock = Clock()
    deadline = c.Deadline(clock)
    clock.seconds = 54
    assert deadline.remaining() == 1
    clock.seconds = 55
    with pytest.raises(c.CaptureError, match="DEADLINE"):
        deadline.check()
    assert deadline.remaining(60) == 5
    clock.seconds = 60
    with pytest.raises(c.CaptureError, match="DEADLINE"):
        deadline.remaining(60)


@pytest.fixture
def anchor(tmp_path):
    path = tmp_path / "capture"
    path.mkdir(mode=0o700)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOATIME)
    value = SimpleNamespace(path=str(path), fd=fd, info=c.metadata(os.fstat(fd)), writer=c.observe_writer(),
                            ssh=0, recheck=lambda **kw: None, capacity=lambda: None)
    def absent(name):
        if os.path.lexists(path / name):
            raise c.CaptureError("OBJECT_EXISTS")
    value.absent = absent
    yield value
    os.close(fd)


def binding():
    return {"D": "a" * 40, "argv": ["never-ssh"], "environment": {}}


@pytest.mark.parametrize("failure", ["spawn", "create", "sync", "exists"])
def test_failure_consumption_never_retries(anchor, monkeypatch, failure):
    calls = []
    def spawn(*args, **kwargs):
        calls.append(1)
        raise OSError("private detail")
    if failure == "create":
        original = c.Capture.create
        def create(self, role):
            if role == "stderr": raise OSError("private")
            return original(self, role)
        monkeypatch.setattr(c.Capture, "create", create)
    elif failure == "sync":
        monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("private")))
    elif failure == "exists":
        (Path(anchor.path) / c.NAMES["stdout"]).write_bytes(b"existing")
    result = c.run_once(anchor, b"pass", binding(), c.Deadline(), popen=spawn)
    assert not result["snapshot_complete"]
    assert len(calls) == (1 if failure == "spawn" else 0)
    assert (Path(anchor.path) / c.NAMES["marker"]).exists() == (failure != "exists")
    second = c.run_once(anchor, b"pass", binding(), c.Deadline(), popen=spawn)
    assert second["requests_attempted"] == 0
    assert len(calls) == (1 if failure == "spawn" else 0)
    assert "private" not in c.canonical(result).decode()


def test_exclusive_marker_competition(anchor):
    a, b = c.Capture(anchor, c.Deadline()), c.Capture(anchor, c.Deadline())
    try:
        a.create("marker")
        with pytest.raises(FileExistsError): b.create("marker")
        with pytest.raises(c.CaptureError): b.create("marker")
    finally:
        a.close()
        b.close()


def test_short_writes_and_on_disk_digest(anchor, monkeypatch):
    cap = c.Capture(anchor, c.Deadline())
    original = os.write
    monkeypatch.setattr(os, "write", lambda fd, raw: original(fd, raw[:3]))
    try:
        cap.create("marker")
        cap.write("marker", b"abcdefghi")
        cap.sync()
        assert cap.sizes["marker"] == 9
        os.pwrite(cap.fds["marker"], b"X", 0)
        with pytest.raises(c.CaptureError, match="DRIFT|DIGEST"): cap.sync()
    finally:
        cap.close()


@pytest.mark.parametrize("role", ["stdout", "stderr", "receipt", "marker"])
def test_capture_rejects_over_limit_before_write(anchor, role):
    cap = c.Capture(anchor, c.Deadline())
    try:
        cap.create(role)
        with pytest.raises(c.CaptureError, match="CAPTURE_LIMIT"):
            cap.write(role, b"x" * (c.CAPS[role] + 1))
        assert cap.sizes[role] == 0
    finally:
        cap.close()


@pytest.mark.parametrize("mode", ["valid", "exit", "malformed", "oversize", "stderr"])
def test_real_local_child_streams_not_ssh(anchor, tree, mode):
    source = b"offline-source"
    value = envelope(collect(tree))
    value["source_sha256"] = c.digest(source)
    raw = c.canonical(value)
    if mode == "malformed": raw = b"{}"
    elif mode == "oversize": raw = b"x" * (c.CAPS["stdout"] + 1)
    def child(*args, **kwargs):
        assert kwargs["stdin"] == subprocess.DEVNULL
        if mode == "oversize":
            code = "import os; os.write(1,b'x'*2097153)"
        elif mode == "stderr":
            code = "import os; os.write(2,b'x'*65537)"
        else:
            code = "import os; os.write(1," + repr(raw) + "); raise SystemExit(" + ("3" if mode == "exit" else "0") + ")"
        return subprocess.Popen([sys.executable, "-I", "-B", "-c", code], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = c.run_once(anchor, source, binding(), c.Deadline(), popen=child)
    assert result["requests_attempted"] == 1
    assert result["snapshot_complete"] == (mode == "valid")
    assert result["remote_supervision_proven"] is False
    assert result["state"] == ("COMPLETE" if mode == "valid" else "FAILED")


def test_reader_limits_exact_without_changing_pytest_process(monkeypatch):
    seen = {}
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(resource, "setrlimit", lambda key, values: seen.__setitem__(key, values))
    monkeypatch.setattr(resource, "getrlimit", lambda key: seen[key])
    r.configure_limits()
    assert seen == {resource.RLIMIT_CPU: (5, 5), resource.RLIMIT_AS: (134217728, 134217728),
                    resource.RLIMIT_NOFILE: (128, 128), resource.RLIMIT_FSIZE: (0, 0), resource.RLIMIT_CORE: (0, 0)}


def test_reader_unprivileged_main_stops_without_config_reads(monkeypatch, capfd):
    with monkeypatch.context() as patch:
        patch.setattr(os, "geteuid", lambda: 1000)
        patch.setattr(os, "open", lambda *a, **kw: pytest.fail("no data read before limits"))
        assert r.main() == 3
    captured = capfd.readouterr()
    assert not captured.out
    assert json.loads(captured.err)["reason"] == "EUID"


def test_management_pins_match_existing_approved_sources():
    path = PATH.with_name("q2_core_delivery_freeze.py")
    spec = importlib.util.spec_from_file_location("_sshd_existing_freeze", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert c.PINS == {name: (mode, sha) for name, (mode, sha, role) in module.ANCHOR_FILES.items()}


@pytest.mark.parametrize("action", ["backwards", "expired"])
def test_deadline_clock_fail_closed(action):
    clock = Clock()
    deadline = c.Deadline(clock)
    clock.seconds = -1 if action == "backwards" else 61
    with pytest.raises(c.CaptureError): deadline.check()


def test_late_no_eof_child_stopped_no_retry(anchor, monkeypatch):
    clock = Clock()
    deadline = c.Deadline(clock)
    calls = []
    original = c.selectors.DefaultSelector.select
    def select(self, timeout):
        result = original(self, min(timeout, 0.01))
        clock.seconds = 55
        return result
    monkeypatch.setattr(c.selectors.DefaultSelector, "select", select)
    def child(*args, **kwargs):
        process = subprocess.Popen([sys.executable, "-I", "-B", "-c", "import time; time.sleep(5)"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        calls.append(process)
        return process
    result = c.run_once(anchor, b"x", binding(), deadline, popen=child)
    assert len(calls) == 1 and calls[0].poll() is not None
    assert not result["snapshot_complete"] and result["reason"] == "DEADLINE"
    assert result["remote_exit"] == "UNKNOWN"


def test_unconfirmed_child_exit_stays_unknown(anchor):
    pipes = []
    for _ in range(2):
        readfd, writefd = os.pipe()
        os.close(writefd)
        pipes.append(os.fdopen(readfd, "rb"))
    killed = []
    def wait(*args, **kwargs): raise subprocess.TimeoutExpired("synthetic", 0)
    process = SimpleNamespace(stdout=pipes[0], stderr=pipes[1], poll=lambda: None,
                              kill=lambda: killed.append(1), wait=wait)
    result = c.run_once(anchor, b"x", binding(), c.Deadline(), popen=lambda *a, **kw: process)
    assert killed == [1] and result["state"] == "UNKNOWN" and result["remote_exit"] == "UNKNOWN"
    assert not result["snapshot_complete"]


def test_capacity_precheck_no_marker_or_spawn(anchor):
    anchor.capacity = lambda: (_ for _ in ()).throw(c.CaptureError("HOST_CAPACITY"))
    result = c.run_once(anchor, b"x", binding(), c.Deadline(), popen=lambda *a, **kw: pytest.fail("no spawn"))
    assert result["requests_attempted"] == 0 and not result["marker_creation_attempted"]
    assert list(Path(anchor.path).iterdir()) == []


def test_writer_change_prevents_marker(anchor):
    anchor.writer = dict(anchor.writer, pid=-1)
    result = c.run_once(anchor, b"x", binding(), c.Deadline(), popen=lambda *a, **kw: pytest.fail("no spawn"))
    assert result["requests_attempted"] == 0 and not result["marker_creation_attempted"]


def test_create_failure_after_marker_never_connects_again(anchor, monkeypatch):
    original = os.open
    def open_(path, flags, *args, **kwargs):
        if path == c.NAMES["stdout"]: raise OSError("disk full")
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", open_)
    for _ in range(2):
        result = c.run_once(anchor, b"x", binding(), c.Deadline(), popen=lambda *a, **kw: pytest.fail("no spawn"))
        assert result["requests_attempted"] == 0
    assert (Path(anchor.path) / c.NAMES["marker"]).exists()


def test_capture_late_return_is_failure(anchor, monkeypatch):
    clock = Clock()
    deadline = c.Deadline(clock)
    cap = c.Capture(anchor, deadline)
    original = os.write
    def write(fd, raw):
        number = original(fd, raw)
        clock.seconds = 60
        return number
    try:
        cap.create("marker")
        monkeypatch.setattr(os, "write", write)
        with pytest.raises(c.CaptureError, match="DEADLINE"):
            cap.write("marker", b"retained")
        assert cap.sizes["marker"] == 8
    finally:
        cap.close()


def test_real_local_process_resource_limits():
    # Ordinary test child can lower its own limits. No root claim or data read.
    code = "import resource,json; pairs=[(resource.RLIMIT_CPU,5),(resource.RLIMIT_AS,134217728),(resource.RLIMIT_NOFILE,128),(resource.RLIMIT_FSIZE,0),(resource.RLIMIT_CORE,0)]; [resource.setrlimit(k,(v,v)) for k,v in pairs]; print(json.dumps([resource.getrlimit(k) for k,v in pairs]))"
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, timeout=5)
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout) == [[5, 5], [134217728, 134217728], [128, 128], [0, 0], [0, 0]]


def test_offline_exact_pair_does_not_claim_historical_cause(tree):
    value = envelope(collect(tree))
    results = c.analyze_snapshot(c.canonical(value), "1" * 64)
    assert [v["baseline"] for v in results] == list(c.PARSERS)
    assert results[0]["code"] == "CORE_ADMIT_SSHD_GRAMMAR"
    assert results[1]["code"].startswith("CORE_ADMIT_SSHD_GRAMMAR_GLOB_F1_L2_")
    assert "AcceptEnv" not in c.canonical(results).decode()
    assert all(v["state"] == "REJECTED" for v in results)


def test_offline_pair_source_failure_no_second_try(tree, monkeypatch):
    calls = []
    def run(*args, **kwargs):
        calls.append(1)
        raise subprocess.TimeoutExpired("git", 5)
    monkeypatch.setattr(subprocess, "run", run)
    result = c.analyze_snapshot(c.canonical(envelope(collect(tree))), "1" * 64)
    assert len(calls) == len(result) == 1 and result[0]["state"] == "UNKNOWN"


@pytest.mark.parametrize("bad", [None, "digest", "mode", "cert", "key", "capacity"])
def test_synthetic_management_preflight_never_connects(tmp_path, monkeypatch, bad):
    path = tmp_path / "management"
    path.mkdir(mode=0o700)
    raw_by_name = {"ssh.sh": (f"q1_vm={path}\n").encode(), "start.sh": b"fixture-only\n",
                   "user-data": b"fixture-only\n", "id_ed25519.pub": b"synthetic-public\n",
                   "known_hosts": b"[127.0.0.1]:22221 ssh-ed25519 synthetic\n"}
    pins = {}
    for name, raw in raw_by_name.items():
        mode = c.PINS[name][0]
        (path / name).write_bytes(raw)
        (path / name).chmod(mode)
        pins[name] = (mode, c.digest(raw))
    (path / "id_ed25519").write_bytes(b"synthetic-not-a-real-key")
    (path / "id_ed25519").chmod(0o600)
    if bad == "digest": (path / "user-data").write_bytes(b"changed")
    if bad == "mode": (path / "id_ed25519").chmod(0o644)
    if bad == "cert": (path / "id_ed25519-cert.pub").touch()
    monkeypatch.setattr(c, "PINS", pins)
    original_dir = c.open_directory
    def directory(value, owner):
        if value == str(path):
            return os.open(path, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW)
        return original_dir(value, owner)
    monkeypatch.setattr(c, "open_directory", directory)
    # This tests anchor/argv binding, not host root mapping; the latter has its
    # own native test below. Sandboxes may expose host root as uid 65534.
    def executable(value):
        fd = os.open(value, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
        return fd, c.metadata(os.fstat(fd))
    monkeypatch.setattr(c, "bound_executable", executable)
    calls = []
    def local_only(argv, **kwargs):
        calls.append(argv)
        if argv[0] == "/usr/bin/ssh-keygen":
            return SimpleNamespace(returncode=0, stdout=b"wrong" if bad == "key" else raw_by_name["id_ed25519.pub"], stderr=b"")
        assert argv[:2] == ["/usr/bin/ssh", "-G"]
        return SimpleNamespace(returncode=0, stdout=b"config\n", stderr=b"")
    monkeypatch.setattr(subprocess, "run", local_only)
    if bad == "capacity":
        monkeypatch.setattr(os, "fstatvfs", lambda fd: SimpleNamespace(f_bavail=0, f_frsize=4096, f_favail=100))
    before = sorted(os.listdir(path))
    held = None
    try:
        if bad:
            with pytest.raises(c.CaptureError):
                held = c.Anchor(str(path), c.Deadline())
                c.preflight(held, b"pass\n", "a" * 40)
        else:
            held = c.Anchor(str(path), c.Deadline())
            value = c.preflight(held, b"pass\n", "a" * 40)
            assert value["D"] == "a" * 40 and len(calls) == 2
    finally:
        if held is not None: held.close()
    assert sorted(os.listdir(path)) == before


def test_native_system_executable_identity():
    if os.lstat("/usr/bin/ssh").st_uid != 0 or os.lstat("/usr").st_uid != 0:
        pytest.skip("tool namespace does not expose host root uid; not a host verdict")
    fd, before = c.bound_executable("/usr/bin/ssh")
    try:
        assert before == c.metadata(os.fstat(fd)) and before["uid"] == 0
    finally:
        os.close(fd)


def test_nonroot_executable_refused(tmp_path, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("requires unprivileged owned executable")
    program = tmp_path / "program"
    program.write_bytes(b"not-executed")
    program.chmod(0o700)
    monkeypatch.setattr(c, "open_directory", lambda path, owner: os.open(path, os.O_PATH | os.O_DIRECTORY))
    with pytest.raises(c.CaptureError, match="LOCAL_EXECUTABLE"):
        c.bound_executable(str(program))
