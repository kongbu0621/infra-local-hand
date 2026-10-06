"""R2 offline adversaries. No sudo, original VM, marker or maintenance window."""
from __future__ import annotations

import ast
import base64
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only journal host-read contract", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g
from e3_host import q2_host_kernel_facts as k

BOOT = "11111111-2222-3333-4444-555555555555"
KEYS = {name: (42, index) for index, name in enumerate(
    ("system", "quota", "journal", "evidence", "seed"), 1)}
NOW = 100_000_000_000


def request():
    return dict(schema="lhq-journal-writer/v1", scope="LH-Q2-CORE-JOURNAL-HOST-READ-v1",
        session=h.SESSION, D="d" * 40, nonce="a" * 64, images={n: list(v) for n, v in KEYS.items()},
        origins=[NOW - 1, NOW - 1], boot_id=BOOT, started=[NOW, NOW], checkpoint=1)


def report(value):
    return dict(schema="lhq-journal-writer-result/v1", request=value, complete=True,
        rows=[dict(pid=77, starttime=23, complete=True,
                   writable_images=["system", "quota", "journal", "evidence"])],
        usage=dict(cpu_us=100, peak_rss_bytes=1024))


@pytest.fixture
def sources():
    root = Path(h.__file__).parent
    return {name: root.joinpath(name).read_bytes() for name in (
        "q2_journal_growth.py", "q2_journal_growth_guest.py", "q2_host_kernel_facts.py")}


@pytest.fixture
def observer(monkeypatch):
    value = object.__new__(h.WriterObserver)
    value.host, value.guest = h, g
    value.window = SimpleNamespace(check=lambda: None, binding=dict(boot_id=BOOT, origins=[NOW - 1] * 2))
    value.commit, value.nonce = "d" * 40, "a" * 64
    value.terminal = {"mode": "terminal", "sid": 7, "dev": 8, "ino": 9,
                      "rdev": 10, "uid": 1000, "gid": 1000, "perm": 0o600}
    value.images = {n: list(v) for n, v in KEYS.items()}
    value.payload = b"fixed-test-only-payload"
    value.reports, value.failed, value.io_bytes = [], False, 0
    value.prior_cpu_us = value.prior_rss = 0
    value.tools, value.python_link = {}, None
    events, calls, clock = [], [], [NOW]
    value.record = events.append
    monkeypatch.setattr(g.time, "clock_gettime_ns", lambda _: clock[0])
    monkeypatch.setattr(h, "management_usage", lambda: dict(cpu_seconds=0,
        rss_upper_observation_bytes=0, complete=True, live_children=0))
    monkeypatch.setattr(h, "terminal_binding", lambda expected=None: value.terminal)

    class Command:
        def __init__(self, argv, guard, **options):
            calls.append((argv, options))
            self.guard = guard
            self.request = json.loads(base64.b64decode(argv[-1]))
            self.output = dict(stdout=bytearray(), stderr=bytearray())
            self.process = SimpleNamespace(pid=888, poll=lambda: 0)

        def collect(self):
            self.guard()
            raw = h.canonical(report(self.request))
            self.output["stdout"].extend(raw)
            return dict(returncode=0, eof=dict(stdout=True, stderr=True), stdout=raw, stderr=b"")

    monkeypatch.setattr(h, "Command", Command)
    return SimpleNamespace(value=value, events=events, calls=calls, clock=clock, Command=Command)


def test_root_source_is_bounded_and_has_only_fixed_readonly_entry(sources):
    raw = g.writer_payload(*(sources[n] for n in sources), "d" * 40)
    assert len(raw) <= 32768
    tree = ast.parse(raw)
    assert not any(isinstance(node, (ast.ImportFrom,)) and node.module.startswith("e3_host")
                   for node in ast.walk(tree))
    calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert not calls & {"os.write", "os.unlink", "os.rename", "os.kill", "subprocess.run",
                        "socket.socket", "os.chmod", "os.chown", "os.system"}
    assert "cmdline" not in raw.decode() and "environ" not in raw.decode()
    assert b"mount_reader=lambda:read_fact('mountinfo'" in raw
    compile(raw, "fixed-payload", "exec")


@pytest.mark.parametrize("change", [
    {"extra": 1}, {"D": "bad"}, {"nonce": "bad"}, {"scope": "other"}, {"session": "other"},
    {"checkpoint": 0}, {"checkpoint": 9}, {"checkpoint": True}, {"origins": [True, 0]},
    {"started": [-1, 0]}, {"boot_id": "bad"}, {"images": {"path": "/etc/shadow"}},
    {"images": {n: [42, 1] for n in KEYS}}, {"schema": "other"},
])
def test_nonfixed_request_rejected(change):
    with pytest.raises((g.r.ObservationError, ValueError)):
        g.writer_request(h.canonical(request() | change))


def test_request_duplicate_and_size_are_rejected():
    raw = h.canonical(request())
    assert g.writer_request(raw) == request()
    with pytest.raises(g.r.ObservationError):
        g.writer_request(raw[:-2] + b',"D":"bad"}\n')
    with pytest.raises(g.r.ObservationError):
        g.writer_request(b" " * 65537)


def test_loader_rejects_modified_source_without_executing_it():
    payload = b"raise RuntimeError('MUST_NOT_EXECUTE')"
    result = subprocess.run([sys.executable, "-I", "-B", "-c", g.WRITER_LOADER,
        base64.b64encode(payload).decode(), "0" * 64, "e30="], capture_output=True, timeout=5)
    assert result.returncode != 0 and b"WRITER_SOURCE_PIN" in result.stderr
    assert b"MUST_NOT_EXECUTE" not in result.stderr


@pytest.mark.parametrize("failure", ["uid", "D", "deadline", "boot", "visibility"])
def test_root_entry_rejects_without_writing_or_scanning_arbitrary_objects(sources, monkeypatch, failure):
    raw = g.writer_payload(*(sources[n] for n in sources), "d" * 40)
    tree = ast.parse(raw)
    tree.body.pop()  # Suppress entry invocation; execute definitions only in an isolated namespace.
    namespace = {"__name__": "offline_test"}
    exec(compile(tree, "offline-test", "exec"), namespace)
    value = request()
    if failure == "D": value["D"] = "e" * 40
    if failure == "deadline": value["started"] = [NOW - 15_000_000_000] * 2
    monkeypatch.setattr(os, "geteuid", lambda: 1000 if failure == "uid" else 0)
    monkeypatch.setattr(g.resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(g.time, "clock_gettime_ns", lambda _: NOW)
    namespace["read_fact"] = lambda kind, check, details: (BOOT if failure != "boot" else "other").encode() + b"\n"
    scans = []
    def scan(images, check, **kwargs):
        scans.append(images)
        raise PermissionError(13, "private diagnostic", "/private/never/publish")
    namespace["collect_image_writers"] = scan
    monkeypatch.setattr(sys, "argv", ["fixed", "unused", "unused", base64.b64encode(h.canonical(value)).decode()])
    stream = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=stream))
    assert namespace["writer_entry"]() == 3
    result = json.loads(stream.getvalue())
    assert result["complete"] is False and "private" not in stream.getvalue().decode()
    assert bool(scans) is (failure == "visibility")


def test_exact_eight_calls_fixed_argv_and_no_ninth(observer):
    value = observer.value
    for count in range(1, 9):
        rows = value.observe(KEYS, lambda: None)
        h.verify_writers(rows, 77, ("system", "quota", "journal", "evidence"))
        assert len(value.reports) == count
        assert value.reports[-1]["request"]["checkpoint"] == count
    with pytest.raises(g.r.ObservationError, match="NO_RETRY"):
        value.observe(KEYS, lambda: None)
    assert len(observer.calls) == 8
    for argv, options in observer.calls:
        assert argv[:4] == ["/usr/bin/sudo", "--", "/usr/bin/env", "-i"]
        assert argv[7:11] == ["/usr/bin/python3", "-I", "-B", "-c"]
        assert not ({"-n", "-S", "-A", "-v"} & set(argv))
        assert options == dict(limit=65536, stderr_limit=4096, terminal=True)


def test_two_cli_observations_share_manifest_and_do_not_reuse_pass(observer, sources, tmp_path, monkeypatch):
    (tmp_path / "python3").touch()
    monkeypatch.setattr(h.local, "open_directory", lambda *_: os.open(tmp_path, os.O_PATH | os.O_DIRECTORY))
    class Tool:
        def __init__(self, path, check, *, version):
            assert version is False  # No sudo --version, -v or -l permission probe.
            self.path = path
        def recheck(self): pass
        def binding(self): return dict(path=self.path, identity="synthetic")
        def close(self): pass
    monkeypatch.setattr(h, "Tool", Tool)
    first = h.WriterObserver(sources, "d" * 40, observer.value.window, KEYS,
                             observer.value.terminal)
    assert observer.calls == []
    first.observe(KEYS, lambda: None)
    static = first.binding()
    handoff = first.handoff()
    second = h.WriterObserver(sources, "d" * 40, first.window, KEYS,
                              observer.value.terminal, h.canonical(handoff))
    assert len(observer.calls) == 1 and len(second.reports) == 1
    second.observe(KEYS, lambda: None)
    assert len(observer.calls) == 2 and len(second.reports) == 2
    assert second.binding() == static
    assert static["auth"] == dict(A=h.TERM_A, C=h.TERM_C, mode="terminal",
                                   terminal=observer.value.terminal)
    assert [json.loads(base64.b64decode(argv[-1]))["checkpoint"] for argv, _ in observer.calls] == [1, 2]
    for field in ("cpu_us", "rss_bytes", "io_bytes"):
        bad = copy.deepcopy(handoff); bad[field] = 0
        with pytest.raises(g.r.ObservationError, match="USAGE"):
            h.WriterObserver(sources, "d" * 40, first.window, KEYS,
                             observer.value.terminal, h.canonical(bad))
    changed_terminal = observer.value.terminal | {"ino": 10}
    with pytest.raises(g.r.ObservationError, match="PREFLIGHT"):
        h.WriterObserver(sources, "d" * 40, first.window, KEYS,
                         changed_terminal, h.canonical(handoff))
    assert len(observer.calls) == 2


@pytest.mark.parametrize("failure", ["sudo", "eof", "bad_report", "timeout", "launch"])
def test_failed_checkpoint_cannot_retry(observer, monkeypatch, failure):
    def collect(command):
        if failure == "launch": raise OSError("synthetic launch failure")
        if failure == "timeout":
            observer.clock[0] += 15_000_000_000
            command.guard()
        return dict(returncode=1 if failure == "sudo" else 0,
            eof=dict(stdout=True, stderr=failure != "eof"), stdout=b"{}", stderr=b"denied")
    monkeypatch.setattr(observer.Command, "collect", collect)
    with pytest.raises(Exception):
        observer.value.observe(KEYS, lambda: None)
    with pytest.raises(g.r.ObservationError, match="NO_RETRY"):
        observer.value.observe(KEYS, lambda: None)
    assert len(observer.calls) == 1


def test_fixed_root_failure_reason_is_retained_and_cannot_retry(observer, monkeypatch):
    def collect(command):
        raw = h.canonical(dict(schema="lhq-journal-writer-result/v1",
            request=command.request, complete=False,
            reason="GROWTH_WRITER_DEADLINE", errno=None))
        command.output["stdout"].extend(raw)
        return dict(returncode=3, eof=dict(stdout=True, stderr=True), stdout=raw, stderr=b"")
    monkeypatch.setattr(observer.Command, "collect", collect)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_WRITER_DEADLINE$"):
        observer.value.observe(KEYS, lambda: None)
    with pytest.raises(g.r.ObservationError, match="NO_RETRY"):
        observer.value.observe(KEYS, lambda: None)
    assert len(observer.calls) == 1 and observer.value.reports == []


def test_terminal_loss_after_return_is_terminal_and_cannot_retry(observer, monkeypatch):
    calls = []
    def terminal(expected=None):
        calls.append(expected)
        if len(calls) == 2:
            raise g.r.ObservationError("GROWTH_TERMINAL_FOREGROUND")
        return observer.value.terminal
    monkeypatch.setattr(h, "terminal_binding", terminal)
    with pytest.raises(g.r.ObservationError, match="TERMINAL_FOREGROUND"):
        observer.value.observe(KEYS, lambda: None)
    with pytest.raises(g.r.ObservationError, match="NO_RETRY"):
        observer.value.observe(KEYS, lambda: None)
    assert len(observer.calls) == 1 and calls == [observer.value.terminal] * 2


@pytest.mark.parametrize("change", ["nonce", "checkpoint", "D", "boot_id", "origins", "images", "started"])
def test_report_binding_is_not_transferable(observer, change):
    value = request()
    if change in ("nonce", "D"): value[change] = "b" * len(value[change])
    elif change == "checkpoint": value[change] = 2
    elif change == "boot_id": value[change] = "22222222-2222-2222-2222-222222222222"
    elif change in ("origins", "started"): value[change] = [NOW + 1] * 2
    else: value[change]["system"][1] = 900
    with pytest.raises(g.r.ObservationError):
        observer.value.validate(report(value), value, 1)


@pytest.mark.parametrize("field", ["prior_cpu_us", "prior_rss", "io_bytes"])
def test_cumulative_budget_rejects(observer, field):
    setattr(observer.value, field, 10**12)
    with pytest.raises(g.r.ObservationError, match="BUDGET"):
        observer.value.check()


def test_partial_stderr_is_bounded_and_never_killed():
    command = h.Command([sys.executable, "-I", "-B", "-c", "import sys; sys.stderr.write('x'*4097)"],
                        lambda: None, limit=65536, stderr_limit=4096)
    try:
        with pytest.raises(g.r.ObservationError, match="STREAM_LIMIT"):
            command.collect()
        assert len(command.output["stderr"]) == 4097
    finally:
        command.process.wait(timeout=5)


def test_host_reader_uses_qualified_fixed_module_not_guest_fallback(monkeypatch):
    calls, details = [], {}
    def read(kind, check, report):
        calls.append(kind); report["status"] = "OBSERVED"
        return (BOOT + "\n").encode()
    monkeypatch.setattr(k, "read_fact", read)
    monkeypatch.setattr(g, "read_kernel", lambda *args: pytest.fail("guest fallback"))
    assert g.host_boot_id(lambda: None, details) == BOOT
    assert calls == ["boot"] and details["status"] == "OBSERVED"


def test_host_reader_retains_sanitized_qualification_failure(monkeypatch):
    def denied(*args):
        raise k.KernelFactError("HOST_LOCAL_KERNEL_SUBMOUNT", "mount_id", "boot", errno=13)
    monkeypatch.setattr(k, "read_fact", denied)
    with pytest.raises(g.r.ObservationError, match="HOST_KERNEL_FACT") as caught:
        g.host_boot_id(lambda: None)
    assert caught.value.diagnostic == dict(reason="HOST_LOCAL_KERNEL_SUBMOUNT", operation="mount_id", target="boot", errno=13)
