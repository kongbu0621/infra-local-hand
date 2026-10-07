"""Approved proc limits with synthetic entries/reads; no live procfs or sudo."""
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
from test_e3_q2_journal_host_read import KEYS, observer, request as writer_request
from test_e3_q2_journal_writer_payload import BOOT, payload, run_entry


PRIVATE_PATH = "/synthetic/PRIVATE_PROC_PATH"
STAT = ("27 (private process title) " + " ".join(["S", *(["0"] * 18), "17"])).encode()
INFO = SimpleNamespace(st_dev=42, st_ino=1, st_mode=0, st_uid=0, st_gid=0, st_nlink=1)
LIMITS = [
    ("PID_ENTRIES", 32768, 0, 0), ("TASK_ENTRIES", 32768, 27, 0),
    ("FD_ENTRIES", 65536, 27, 29), ("TASK_TOTAL", 65536, 27, 29),
    ("FD_STAT_CALLS", 2097152, 27, 29), ("PID_STAT_BYTES", 16384, 27, 0),
    ("TASK_STAT_BYTES", 16384, 27, 29),
    ("FDINFO_BYTES", 4096, 27, 29), ("MAPS_BYTES", 1048576, 27, 29),
    ("MAPS_TOTAL_BYTES", 536870912, 27, 29), ("MOUNTINFO_BYTES", 1048576, 0, 0),
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
def test_approved_limit_allows_exact_cap_and_reports_first_excess(scanner, kind, cap, pid, tid):
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
    progress = scanner.ns["scan_progress"]()
    monkeypatch.setattr(scanner.os, "scandir", lambda path:
        Entries((str(n) for n in range(65536 + extra)), stats))
    if extra:
        with pytest.raises(scanner.error) as caught:
            scanner.ns["_fd_snapshot"](PRIVATE_PATH, lambda: None, 27, 29, kind=kind, progress=progress)
        assert str(caught.value) == reason(kind, 65537, 65536, 27, 29)
    else:
        assert len(scanner.ns["_fd_snapshot"](PRIVATE_PATH, lambda: None, 27, 29, kind=kind, progress=progress)) == 65536
    assert len(stats) == 65536
    assert sum(progress[k] for k in ("fd_initial_stat_attempts", "fd_recheck_stat_attempts", "fd_match_stat_attempts")) == 65536


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


def synthetic_scan(scanner, monkeypatch, pids, tasks, *, fds=None, maps=None, check=None):
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
    return lambda: scanner.ns["collect_image_writers"]({"journal": (42, 2)}, check or (lambda: None),
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



def maps_block(size):
    line = b"1000-2000 r--p 0 00:00 0 /synthetic/PRIVATE_MAP_CONTENT"
    assert len(line) < size <= 1048576
    return line + b" " * (size - len(line) - 1) + b"\n"


@pytest.mark.parametrize("extra_bytes", [0, 1, 1048576])
def test_maps_total_counts_every_task_at_new_exact_boundary(scanner, monkeypatch, extra_bytes):
    # Reuse one 1-MiB value; never allocate a 512-MiB fixture. The extra task after
    # a rejecting read proves that rejection does not continue collecting data.
    block = maps_block(1048576)
    reads = []
    def maps(path):
        reads.append(path)
        if len(reads) <= 512:
            return block
        assert len(reads) == 513 and extra_bytes
        return b"\n" if extra_bytes == 1 else block
    tids = [str(n) for n in range(1, 513 + (2 if extra_bytes else 0))]
    scan = synthetic_scan(scanner, monkeypatch, ["27"], {"27": tids}, maps=maps)
    if extra_bytes:
        with pytest.raises(scanner.error) as caught:
            scan()
        assert str(caught.value) == reason("MAPS_TOTAL_BYTES", 536870912 + extra_bytes,
                                           536870912, 27, 513)
        assert "PRIVATE_MAP_CONTENT" not in str(caught.value)
    else:
        assert len(scan()) == 1
    assert len(reads) == 512 + bool(extra_bytes)


@pytest.mark.parametrize("late,expected", [
    ("complete", None), ("mapped_writer", None), ("fd_writer", None),
    ("malformed_maps", "GROWTH_PROC_MAPS"), ("unreadable_maps", "GROWTH_WRITERS_UNKNOWN"),
    ("task_identity", "GROWTH_PROC_DRIFT_TASK_START"), ("pid_identity", "GROWTH_PROC_DRIFT_PID_START"),
    ("task_set", "GROWTH_PROC_DRIFT_PID_TASK_SET"), ("pid_set", "GROWTH_PROC_DRIFT_PID_SET"),
    ("fd_drift", "GROWTH_PROC_DRIFT_FD_SNAPSHOT"), ("deadline", "GROWTH_WRITER_DEADLINE"),
])
def test_old_field_rejection_value_does_not_skip_later_checks(scanner, monkeypatch, late, expected):
    block, remainder = maps_block(1048576), maps_block(6778)
    reads, calls = [], []
    last_task = PRIVATE_PATH + "/27/task/66/"

    def maps(path):
        reads.append(path)
        if len(reads) <= 64:
            return block
        if len(reads) == 65:
            return remainder
        assert len(reads) == 66
        if late == "malformed_maps":
            return b"invalid maps\n"
        if late == "unreadable_maps":
            raise PermissionError(13, "synthetic only", PRIVATE_PATH)
        if late == "mapped_writer":
            return b"1000-2000 rw-s 0 00:2a 2 /synthetic/PRIVATE_MAP_CONTENT\n"
        return b""

    def guard():
        if late == "deadline" and len(reads) == 65:
            raise scanner.error("GROWTH_WRITER_DEADLINE")

    scan = synthetic_scan(scanner, monkeypatch, ["27"],
        {"27": [str(n) for n in range(1, 67)]}, maps=maps, check=guard)
    original_read, original_names = scanner.ns["_proc_read"], scanner.ns["_bounded_names"]
    fd_info = SimpleNamespace(**(vars(INFO) | {"st_ino": 2}))

    def read(path, cap, check, kind="PID_STAT_BYTES", *context):
        calls.append(kind)
        if late == "task_identity" and path == last_task + "stat" and kind == "TASK_STAT_BYTES_RECHECK":
            return STAT[:-2] + b"18"
        if late == "pid_identity" and kind == "PID_STAT_BYTES_RECHECK":
            return STAT[:-2] + b"18"
        if late == "fd_writer" and path.startswith(last_task + "fdinfo/"):
            return b"flags:\t02\n"
        return original_read(path, cap, check, kind, *context)

    def names(path, cap, check, **options):
        kind = options.get("kind", "PID_ENTRIES")
        calls.append(kind)
        if late == "task_set" and kind == "TASK_ENTRIES_RECHECK":
            return ["changed"]
        if late == "pid_set" and kind == "PID_ENTRIES_RECHECK":
            return []
        return original_names(path, cap, check, **options)

    def fds(path, check, pid=0, tid=0, kind="FD_ENTRIES", *, progress=None):
        if path != last_task + "fd":
            return {}
        if late in ("fd_writer", "deadline"):
            return {"8": fd_info}
        if late == "fd_drift" and kind == "FD_ENTRIES_RECHECK":
            return {"8": fd_info}
        return {}

    monkeypatch.setitem(scanner.ns, "_proc_read", read)
    monkeypatch.setitem(scanner.ns, "_bounded_names", names)
    monkeypatch.setitem(scanner.ns, "_fd_snapshot", fds)
    monkeypatch.setattr(scanner.os, "stat", lambda path: fd_info)
    if expected:
        with pytest.raises(scanner.error, match="^" + expected + "$"):
            scan()
    else:
        rows = scan()
        assert rows == [dict(pid=27, starttime=17, complete=True,
                            writable_images=["journal"] if late.endswith("writer") else [])]
        assert "TASK_ENTRIES_RECHECK" in calls and "PID_STAT_BYTES_RECHECK" in calls
        assert calls[-1] == "PID_ENTRIES_RECHECK"
    # All cases reached the exact former field failure before the later outcome.
    assert len(reads) >= 65 and 64 * len(block) + len(remainder) == 67115642
    assert len(reads) == (65 if late in ("fd_drift", "deadline") else 66)


@pytest.mark.parametrize("kind", ["PID_ENTRIES", "TASK_ENTRIES", "PID_ENTRIES_RECHECK",
                                  "TASK_ENTRIES_RECHECK"])
def test_duplicate_enumeration_names_report_only_fixed_kind(scanner, monkeypatch, kind):
    calls, checks = [], []
    def entries(path):
        calls.append(path)
        return Entries(["29", "PRIVATE_NOT_NUMERIC", "29"], [])
    monkeypatch.setattr(scanner.os, "scandir", entries)
    with pytest.raises(scanner.error) as caught:
        scanner.ns["_bounded_names"](PRIVATE_PATH, 32768, lambda: checks.append(True),
                                     numeric=True, kind=kind, pid="27")
    assert str(caught.value) == "GROWTH_PROC_DRIFT_DUPLICATE_" + kind
    assert re.fullmatch(r"[A-Z0-9_]{1,160}", str(caught.value))
    assert calls == [PRIVATE_PATH] and len(checks) == 3


PID_RECHECK_CASES = [
    ("duplicate", "GROWTH_PROC_DRIFT_DUPLICATE_TASK_ENTRIES_RECHECK"),
    ("same_size_set", "GROWTH_PROC_DRIFT_PID_TASK_SET"),
    ("larger_set", "GROWTH_PROC_DRIFT_PID_TASK_SET"),
    ("pid_start", "GROWTH_PROC_DRIFT_PID_START"),
]


def pid_recheck_scan(scanner, monkeypatch, failure):
    """Real enumeration and scan control flow; all filesystem operations are synthetic."""
    events, task_lists = [], []
    root, task_dir = PRIVATE_PATH, PRIVATE_PATH + "/27/task"
    def entries(path):
        events.append(("scandir", path))
        if path == root:
            names = ["27"]
        elif path == task_dir:
            task_lists.append(True)
            names = (["29", "29"] if failure == "duplicate" else
                     ["30"] if failure == "same_size_set" else
                     ["29", "30"] if failure == "larger_set" else ["29"])
            if len(task_lists) == 1:
                names = ["29"]
        else:
            assert path == task_dir + "/29/fd"
            names = []
        return Entries(names, [])
    def read(path, cap, check, kind, *context):
        events.append((kind, path))
        check()
        if kind == "MAPS_BYTES":
            assert path == task_dir + "/29/maps" and cap == 1048576
            return b""
        assert path.endswith("/stat") and cap == 16384
        return STAT[:-2] + b"18" if failure == "pid_start" and kind == "PID_STAT_BYTES_RECHECK" else STAT
    monkeypatch.setattr(scanner.os, "scandir", entries)
    monkeypatch.setitem(scanner.ns, "_proc_read", read)
    original_scan = scanner.ns["collect_image_writers"]
    def scan(*, progress, check=lambda: None):
        return original_scan({"journal": (42, 2)}, check, proc_root=root, progress=progress)
    return scan, events


@pytest.mark.parametrize("failure,expected", [(None, None), *PID_RECHECK_CASES])
def test_pid_recheck_distinguishes_predicate_without_extra_reads(scanner, monkeypatch, failure, expected):
    scan, events = pid_recheck_scan(scanner, monkeypatch, failure)
    progress = scanner.ns["scan_progress"]()
    if expected:
        with pytest.raises(scanner.error) as caught:
            scan(progress=progress)
        assert str(caught.value) == expected
        assert re.fullmatch(r"[A-Z0-9_]{1,160}", str(caught.value))
        assert progress["phase"] == "PID_RECHECK" and progress["pids_completed"] == 0
    else:
        assert scan(progress=progress) == [dict(pid=27, starttime=17, complete=True, writable_images=[])]
        assert progress["phase"] == "FINAL_PID_RECHECK" and progress["pids_completed"] == 1
    root, task = PRIVATE_PATH, PRIVATE_PATH + "/27/task/29"
    expected_events = [("scandir", root), ("PID_STAT_BYTES", root + "/27/stat"),
        ("scandir", root + "/27/task"), ("TASK_STAT_BYTES", task + "/stat"),
        ("scandir", task + "/fd"), ("scandir", task + "/fd"),
        ("MAPS_BYTES", task + "/maps"), ("TASK_STAT_BYTES_RECHECK", task + "/stat"),
        ("scandir", root + "/27/task")]
    if failure in (None, "pid_start"):
        expected_events.append(("PID_STAT_BYTES_RECHECK", root + "/27/stat"))
    if failure is None:
        expected_events.append(("scandir", root))
    # In particular, list mismatch/duplicates do not cause a diagnostic PID-stat reread.
    assert events == expected_events
    assert progress["pids_listed"] == progress["tasks_started"] == progress["tasks_completed"] == 1
    assert progress["maps_files_read"] == 1 and progress["maps_bytes_read"] == 0
    assert not progress["scan_complete"]
    g.validate_progress(progress, writer_request())


@pytest.mark.parametrize("failure,expected", [("identity", "GROWTH_PROC_DRIFT_FD_IDENTITY"),
                                              ("fdinfo", "GROWTH_PROC_DRIFT_FDINFO")])
def test_matching_fd_drift_keeps_identity_before_fdinfo_order(scanner, monkeypatch, failure, expected):
    synthetic_scan(scanner, monkeypatch, ["27"], {"27": ["29"]}, fds={"8": INFO})
    progress, events = scanner.ns["scan_progress"](), []
    original_read = scanner.ns["_proc_read"]
    def read(path, cap, check, kind, *context):
        events.append(kind)
        if kind == "FDINFO_BYTES_RECHECK":
            return b"flags:\t02\n"
        return original_read(path, cap, check, kind, *context)
    def stat(path):
        events.append("matching_stat")
        return SimpleNamespace(**(vars(INFO) | {"st_ino": 2})) if failure == "identity" else INFO
    monkeypatch.setitem(scanner.ns, "_proc_read", read)
    monkeypatch.setattr(scanner.os, "stat", stat)
    with pytest.raises(scanner.error, match="^" + expected + "$"):
        scanner.ns["collect_image_writers"]({"journal": (42, 1)}, lambda: None,
                                           proc_root=PRIVATE_PATH, progress=progress)
    assert events == ["PID_STAT_BYTES", "TASK_STAT_BYTES", "FDINFO_BYTES", "matching_stat"] + (
        ["FDINFO_BYTES_RECHECK"] if failure == "fdinfo" else [])
    assert progress["phase"] == "FD_MATCH" and progress["fd_match_stat_attempts"] == 1
    assert progress["tasks_completed"] == progress["maps_files_read"] == 0


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
    def fd_snapshot(path, check, pid=0, tid=0, kind="FD_ENTRIES", *, progress=None):
        if kind == expected_kind:
            scanner.ns["_proc_limit"](kind, 65537, 65536, pid, tid)
        return snapshot(path, check, pid, tid, kind=kind, progress=progress)
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
    assert g.writer_failure(raw, result["request"]) == dict(reason=expected, errno=None, progress=result["progress"])
    def collect(command):
        assert result["request"] == command.request
        command.output["stdout"].extend(raw)
        command.process.poll = lambda: 3
        return dict(returncode=3, eof=dict(stdout=True, stderr=True), stdout=raw, stderr=b"")
    monkeypatch.setattr(observer.Command, "collect", collect)
    with pytest.raises(g.r.ObservationError) as caught:
        observer.value.observe(KEYS, lambda: None)
    assert str(caught.value) == h.prior.safe_reason(caught.value) == expected
    assert caught.value.diagnostic["child_failure"] == dict(reason=expected, errno=None, progress=result["progress"])
    assert observer.value.failed and observer.value.reports == [] and len(observer.calls) == 1
    retained = json.dumps(caught.value.diagnostic)
    assert PRIVATE_PATH not in retained and "private process title" not in retained
    assert set(result) == {"schema", "request", "complete", "reason", "errno", "progress"}


@pytest.mark.parametrize("failure,expected", PID_RECHECK_CASES)
def test_actual_pid_recheck_reason_survives_generated_entry_and_parent(payload, observer,
                                                                    monkeypatch, failure, expected):
    monkeypatch.setitem(payload, "os", SimpleNamespace(**vars(payload["os"])))
    scan, events = pid_recheck_scan(SimpleNamespace(ns=payload, os=payload["os"]), monkeypatch, failure)
    monkeypatch.setitem(payload, "collect_image_writers", lambda images, check, **options:
                        scan(progress=options["progress"], check=check))
    monkeypatch.setitem(payload, "read_fact", lambda *args: (BOOT + "\n").encode())
    result = run_entry(payload)
    assert result["reason"] == expected and result["errno"] is None
    progress = result["progress"]
    assert progress["phase"] == "PID_RECHECK" and progress["pids_completed"] == 0
    assert progress["tasks_started"] == progress["tasks_completed"] == 1
    assert progress["last_valid_elapsed_ns"] == [0, 0] and not progress["scan_complete"]
    assert sum(kind == "PID_STAT_BYTES_RECHECK" for kind, _ in events) == (failure == "pid_start")
    raw, child = h.canonical(result), dict(reason=expected, errno=None, progress=progress)
    assert g.writer_failure(raw, result["request"]) == child
    def collect(command):
        assert command.request == result["request"]
        command.output["stdout"].extend(raw)
        command.process.poll = lambda: 3
        return dict(returncode=3, eof=dict(stdout=True, stderr=True), stdout=raw, stderr=b"")
    monkeypatch.setattr(observer.Command, "collect", collect)
    with pytest.raises(g.r.ObservationError) as caught:
        observer.value.observe(KEYS, lambda: None)
    assert str(caught.value) == h.prior.safe_reason(caught.value) == expected
    assert caught.value.diagnostic["child_failure"] == child
    assert PRIVATE_PATH not in json.dumps(caught.value.diagnostic)
    assert "private process title" not in raw.decode()
    assert observer.value.failed and observer.value.reports == [] and len(observer.calls) == 1
    with pytest.raises(g.r.ObservationError, match="^GROWTH_WRITER_NO_RETRY$"):
        observer.value.observe(KEYS, lambda: None)
    assert len(observer.calls) == 1
