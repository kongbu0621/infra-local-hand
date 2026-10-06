"""Original proc limits with synthetic entries/reads; no live procfs or sudo."""
from __future__ import annotations

import json
import re
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only journal proc limits", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g
from test_e3_q2_journal_host_read import KEYS, observer
from test_e3_q2_journal_writer_payload import BOOT, payload, run_entry


PRIVATE_PATH = "/synthetic/PRIVATE_PROC_PATH"
STAT = ("27 (private process title) " + " ".join(["S", *(["0"] * 18), "17"])).encode()
INFO = SimpleNamespace(st_dev=42, st_ino=1, st_mode=0, st_uid=0, st_gid=0, st_nlink=1)
LIMITS = [
    ("PID_ENTRIES", 32768, 0, 0), ("TASK_ENTRIES", 32768, 27, 0),
    ("FD_ENTRIES", 65536, 27, 29), ("TASK_TOTAL", 65536, 27, 29),
    ("FD_TOTAL", 262144, 27, 29), ("PID_STAT_BYTES", 16384, 27, 0),
    ("TASK_STAT_BYTES", 16384, 27, 29),
    ("FDINFO_BYTES", 4096, 27, 29), ("MAPS_BYTES", 1048576, 27, 29),
    ("MAPS_TOTAL_BYTES", 67108864, 27, 29), ("MOUNTINFO_BYTES", 1048576, 0, 0),
    ("PID_ENTRIES_RECHECK", 32768, 0, 0), ("TASK_ENTRIES_RECHECK", 32768, 27, 0),
    ("FD_ENTRIES_RECHECK", 65536, 27, 29), ("PID_STAT_BYTES_RECHECK", 16384, 27, 0),
    ("TASK_STAT_BYTES_RECHECK", 16384, 27, 29), ("FDINFO_BYTES_RECHECK", 4096, 27, 29),
]


def reason(kind, observed, cap, pid=0, tid=0):
    return f"GROWTH_PROC_LIMIT_{kind}_N{observed}_MAX{cap}_P{pid}_T{tid}"


@pytest.fixture(params=["source", "generated"])
def scanner(request, payload, monkeypatch):
    namespace = vars(h) if request.param == "source" else payload
    # Replace the namespace's os facade, never the interpreter's shared os module.
    monkeypatch.setitem(namespace, "os", SimpleNamespace(**vars(namespace["os"])))
    error = h.prior.r.ObservationError if request.param == "source" else payload["WriterError"]
    return SimpleNamespace(ns=namespace, error=error, os=namespace["os"])


class Entries:
    def __init__(self, names, stats):
        self.names, self.stats = names, stats
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def __iter__(self):
        for name in self.names:
            def stat(*, follow_symlinks, name=name):
                assert follow_symlinks is True
                self.stats.append(name)
                return INFO
            yield SimpleNamespace(name=name, stat=stat)


@pytest.mark.parametrize("kind,cap,pid,tid", LIMITS)
def test_original_limit_allows_exact_cap_and_reports_first_excess(scanner, kind, cap, pid, tid):
    check = scanner.ns["_proc_limit"]
    check(kind, cap, cap, pid, tid)
    with pytest.raises(scanner.error) as caught:
        check(kind, cap + 1, cap, pid, tid)
    assert str(caught.value) == reason(kind, cap + 1, cap, pid, tid)
    assert re.fullmatch(r"[A-Z0-9_]{1,160}", str(caught.value))


@pytest.mark.parametrize("value,normalized", [("00027", 27), (27, 27), ("٢٧", 0),
    ("12345678901", 0), ("-1", 0), ("27/private", 0), ("", 0)])
def test_pid_tid_diagnostic_is_bounded_ascii_without_path_text(scanner, value, normalized):
    with pytest.raises(scanner.error) as caught:
        scanner.ns["_proc_limit"]("FD_ENTRIES", 65537, 65536, value, value)
    assert str(caught.value) == reason("FD_ENTRIES", 65537, 65536, normalized, normalized)


@pytest.mark.parametrize("kind,pid", [("PID_ENTRIES", 0), ("TASK_ENTRIES", 27),
    ("PID_ENTRIES_RECHECK", 0), ("TASK_ENTRIES_RECHECK", 27)])
@pytest.mark.parametrize("extra", [0, 1])
def test_enumeration_limit_counts_only_numeric_entries(scanner, monkeypatch, kind, pid, extra):
    names = ["not-a-pid", *(str(n) for n in range(32768 + extra))]
    monkeypatch.setattr(scanner.os, "scandir", lambda path: Entries(names, []))
    call = lambda: scanner.ns["_bounded_names"](PRIVATE_PATH, 32768, lambda: None,
        numeric=True, kind=kind, pid=pid)
    if extra:
        with pytest.raises(scanner.error) as caught:
            call()
        assert str(caught.value) == reason(kind, 32769, 32768, pid)
    else:
        assert len(call()) == 32768


@pytest.mark.parametrize("extra", [0, 1])
@pytest.mark.parametrize("kind", ["FD_ENTRIES", "FD_ENTRIES_RECHECK"])
def test_fd_snapshot_preserves_65536_limit_and_stops_before_extra_stat(scanner, monkeypatch, extra, kind):
    stats = []
    monkeypatch.setattr(scanner.os, "scandir", lambda path:
        Entries((str(n) for n in range(65536 + extra)), stats))
    if extra:
        with pytest.raises(scanner.error) as caught:
            scanner.ns["_fd_snapshot"](PRIVATE_PATH, lambda: None, 27, 29, kind=kind)
        assert str(caught.value) == reason(kind, 65537, 65536, 27, 29)
    else:
        assert len(scanner.ns["_fd_snapshot"](PRIVATE_PATH, lambda: None, 27, 29, kind=kind)) == 65536
    assert len(stats) == 65536


def test_nonnumeric_fd_is_distinct_and_never_stat_ed(scanner, monkeypatch):
    stats = []
    monkeypatch.setattr(scanner.os, "scandir", lambda path: Entries(["private-fd-name"], stats))
    with pytest.raises(scanner.error, match="^GROWTH_PROC_FD_NAME$"):
        scanner.ns["_fd_snapshot"](PRIVATE_PATH, lambda: None, 27, 29)
    assert stats == []


@pytest.mark.parametrize("kind,cap,pid,tid", [item for item in LIMITS if item[0] in {
    "PID_STAT_BYTES", "TASK_STAT_BYTES", "FDINFO_BYTES", "MAPS_BYTES", "MOUNTINFO_BYTES",
    "PID_STAT_BYTES_RECHECK", "TASK_STAT_BYTES_RECHECK", "FDINFO_BYTES_RECHECK"}])
@pytest.mark.parametrize("extra", [0, 1])
def test_per_file_read_caps_preserve_first_excess_byte_and_close(scanner, monkeypatch,
                                                               kind, cap, pid, tid, extra):
    remaining, total_read, closed = [cap + extra], [0], []
    def read(fd, amount):
        assert fd == 99 and 0 < amount <= 65536
        count = min(amount, remaining[0])
        remaining[0] -= count
        total_read[0] += count
        return b"x" * count
    monkeypatch.setattr(scanner.os, "open", lambda path, flags: 99)
    monkeypatch.setattr(scanner.os, "read", read)
    monkeypatch.setattr(scanner.os, "close", closed.append)
    call = lambda: scanner.ns["_proc_read"](PRIVATE_PATH, cap, lambda: None, kind, pid, tid)
    if extra:
        with pytest.raises(scanner.error) as caught:
            call()
        assert str(caught.value) == reason(kind, cap + 1, cap, pid, tid)
    else:
        assert len(call()) == cap
    assert total_read == [cap + extra] and closed == [99]


def synthetic_scan(scanner, monkeypatch, pids, tasks, *, fds=None, maps=None):
    """Supply logical proc records in memory; every production scan loop still runs."""
    root = PRIVATE_PATH
    def names(path, cap, check, **kwargs):
        assert cap == 32768 and kwargs["numeric"] is True
        return pids if path == root else tasks[path.split("/")[-2]]
    def read(path, cap, check, *args, **kwargs):
        if path.endswith("/stat"):
            assert cap == 16384
            return STAT
        if path.endswith("/maps"):
            assert cap == 1048576
            return b"" if maps is None else maps(path)
        if "/fdinfo/" in path:
            assert cap == 4096
            return b"flags:\t00\n"
        raise AssertionError(path)
    monkeypatch.setitem(scanner.ns, "_bounded_names", names)
    monkeypatch.setitem(scanner.ns, "_proc_read", read)
    monkeypatch.setitem(scanner.ns, "_fd_snapshot", lambda *args, **kwargs: {} if fds is None else fds)
    monkeypatch.setattr(scanner.os, "stat", lambda path: INFO)
    return lambda: scanner.ns["collect_image_writers"]({"journal": (42, 2)}, lambda: None,
                                                       proc_root=root)


@pytest.mark.parametrize("extra", [0, 1])
def test_task_total_uses_all_tasks_across_processes(scanner, monkeypatch, extra):
    tasks = {"1": [str(n) for n in range(32768)], "2": [str(n) for n in range(32768)]}
    if extra:
        tasks["3"] = ["29"]
    scan = synthetic_scan(scanner, monkeypatch, list(tasks), tasks)
    if extra:
        with pytest.raises(scanner.error) as caught:
            scan()
        assert str(caught.value) == reason("TASK_TOTAL", 65537, 65536, 3, 29)
    else:
        assert len(scan()) == 2


@pytest.mark.parametrize("extra", [0, 1])
def test_fd_total_counts_repeated_per_task_snapshots(scanner, monkeypatch, extra):
    fds = {str(n): INFO for n in range(65536)}
    tids = [str(n) for n in range(1, 5 + extra)]
    scan = synthetic_scan(scanner, monkeypatch, ["27"], {"27": tids}, fds=fds)
    if extra:
        with pytest.raises(scanner.error) as caught:
            scan()
        assert str(caught.value) == reason("FD_TOTAL", 262145, 262144, 27, 5)
    else:
        assert len(scan()) == 1


@pytest.mark.parametrize("extra", [0, 1])
def test_maps_total_counts_same_bytes_for_each_task_without_dedup(scanner, monkeypatch, extra):
    # One valid 1-MiB maps value is shared by tasks; no 64-MiB fixture is allocated.
    line = b"1000-2000 r--p 0 00:00 0 /synthetic/PRIVATE_MAP_CONTENT"
    block = line + b" " * (1048576 - len(line) - 1) + b"\n"
    reads = []
    def maps(path):
        reads.append(path)
        return block
    tids = [str(n) for n in range(1, 65 + extra)]
    scan = synthetic_scan(scanner, monkeypatch, ["27"], {"27": tids}, maps=maps)
    if extra:
        with pytest.raises(scanner.error) as caught:
            scan()
        assert str(caught.value) == reason("MAPS_TOTAL_BYTES", 65 * 1048576, 64 * 1048576, 27, 65)
        assert "PRIVATE_MAP_CONTENT" not in str(caught.value)
    else:
        assert len(scan()) == 1
    assert len(reads) == 64 + extra


@pytest.mark.parametrize("kind,cap,pid,tid", [item for item in LIMITS if item[0] in {
    "PID_STAT_BYTES", "TASK_STAT_BYTES", "FDINFO_BYTES", "MAPS_BYTES", "MOUNTINFO_BYTES",
    "PID_STAT_BYTES_RECHECK", "TASK_STAT_BYTES_RECHECK", "FDINFO_BYTES_RECHECK"}])
def test_scanner_passes_exact_file_kind_and_process_context(scanner, monkeypatch,
                                                          kind, cap, pid, tid):
    scan = synthetic_scan(scanner, monkeypatch, ["27"], {"27": ["29"]}, fds={"8": INFO})
    original = scanner.ns["_proc_read"]
    def read(path, observed_cap, check, observed_kind="PID_STAT_BYTES", observed_pid=0, observed_tid=0):
        if observed_kind == kind:
            assert (observed_kind, observed_cap, int(observed_pid), int(observed_tid)) == (kind, cap, pid, tid)
            scanner.ns["_proc_limit"](observed_kind, cap + 1, cap, observed_pid, observed_tid)
        return original(path, observed_cap, check)
    monkeypatch.setitem(scanner.ns, "_proc_read", read)
    if kind.startswith("FDINFO_BYTES"):
        scan = lambda: scanner.ns["collect_image_writers"]({"journal": (42, 1)}, lambda: None,
                                                          proc_root=PRIVATE_PATH)
    if kind == "MOUNTINFO_BYTES":
        scan = lambda: scanner.ns["collect_image_writers"]({"journal": (42, 1)}, lambda: None)
    with pytest.raises(scanner.error) as caught:
        scan()
    assert str(caught.value) == reason(kind, cap + 1, cap, pid, tid)


@pytest.mark.parametrize("kind,cap,pid,tid", [item for item in LIMITS if "ENTRIES" in item[0]])
def test_scanner_passes_exact_enumeration_and_recheck_context(scanner, monkeypatch, kind, cap, pid, tid):
    scan = synthetic_scan(scanner, monkeypatch, ["27"], {"27": ["29"]})
    names, snapshot = scanner.ns["_bounded_names"], scanner.ns["_fd_snapshot"]
    def bounded_names(path, cap, check, *, numeric=False, kind="PID_ENTRIES", pid=0, tid=0):
        if kind == expected_kind:
            scanner.ns["_proc_limit"](kind, cap + 1, cap, pid, tid)
        return names(path, cap, check, numeric=numeric, kind=kind, pid=pid, tid=tid)
    def fd_snapshot(path, check, pid=0, tid=0, kind="FD_ENTRIES"):
        if kind == expected_kind:
            scanner.ns["_proc_limit"](kind, 65537, 65536, pid, tid)
        return snapshot(path, check, pid, tid, kind=kind)
    expected_kind = kind
    monkeypatch.setitem(scanner.ns, "_bounded_names", bounded_names)
    monkeypatch.setitem(scanner.ns, "_fd_snapshot", fd_snapshot)
    with pytest.raises(scanner.error) as caught:
        scan()
    assert str(caught.value) == reason(kind, cap + 1, cap, pid, tid)


@pytest.mark.parametrize("kind,cap,pid,tid", LIMITS)
def test_generated_entry_failure_parser_parent_and_cli_retain_full_limit(payload, observer,
                                                                       monkeypatch, kind, cap, pid, tid):
    payload["read_fact"] = lambda *args: (BOOT + "\n").encode()
    def scan(*args, **kwargs):
        payload["_proc_limit"](kind, cap + 1, cap, pid, tid)
    payload["collect_image_writers"] = scan
    result = run_entry(payload)
    raw = h.canonical(result)
    expected = reason(kind, cap + 1, cap, pid, tid)
    assert result["reason"] == expected
    assert g.writer_failure(raw, result["request"]) == dict(reason=expected, errno=None)
    def collect(command):
        assert result["request"] == command.request
        command.output["stdout"].extend(raw)
        command.process.poll = lambda: 3
        return dict(returncode=3, eof=dict(stdout=True, stderr=True), stdout=raw, stderr=b"")
    monkeypatch.setattr(observer.Command, "collect", collect)
    with pytest.raises(g.r.ObservationError) as caught:
        observer.value.observe(KEYS, lambda: None)
    assert str(caught.value) == h.prior.safe_reason(caught.value) == expected
    assert caught.value.diagnostic["child_failure"] == dict(reason=expected, errno=None)
    assert observer.value.failed and observer.value.reports == [] and len(observer.calls) == 1
    retained = json.dumps(caught.value.diagnostic)
    assert PRIVATE_PATH not in retained and "private process title" not in retained
    assert set(result) == {"schema", "request", "complete", "reason", "errno"}
