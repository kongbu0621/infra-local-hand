"""W1 synthetic operation accounting, progress admission and source/transport bounds."""
from __future__ import annotations

import base64
import io
import json
import random
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import zlib

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only journal scan work", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g
from test_e3_q2_journal_host_read import KEYS, observer, report, request
from test_e3_q2_journal_proc_limits import INFO, STAT, maps_block, reason, scanner
from test_e3_q2_journal_writer_payload import BOOT, NOW, payload, proc_fixture
from test_e3_q2_journal_diagnostic_resume import source_git


FIELDS = ("fd_initial_stat_attempts", "fd_recheck_stat_attempts", "fd_match_stat_attempts")
LIMIT = 2097152


def counted_scan(scanner, monkeypatch, progress, *, tasks, per_task, maps=b"", writer=None):
    """Run real snapshot/stat/scan loops with synthetic proc operations, no live reads."""
    attempts = dict.fromkeys(FIELDS, 0)
    reads = []
    tids = [str(n) for n in range(1, tasks + 1)]
    matching = SimpleNamespace(**(vars(INFO) | {"st_ino": 2}))

    def names(path, cap, check, **options):
        check()
        return ["27"] if path == "/synthetic" else tids

    def read(path, cap, check, *args):
        check()
        if path.endswith("/stat"):
            return STAT
        if "/fdinfo/" in path:
            return b"flags:\t02\n"
        assert path.endswith("/maps")
        reads.append(path)
        if writer == "maps" and path.split("/")[-2] == tids[-1]:
            return b"1000-2000 rw-s 0 00:2a 2 /synthetic/private-map\n"
        return maps

    class Entries:
        def __init__(self, path): self.path = path
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def __iter__(self):
            for n in range(per_task):
                def stat(*, follow_symlinks, n=n):
                    assert follow_symlinks
                    field = "fd_initial_stat_attempts" if progress["phase"] == "FD_INITIAL" else "fd_recheck_stat_attempts"
                    # Production must charge immediately before the actual operation.
                    assert progress[field] == attempts[field] + 1
                    attempts[field] += 1
                    return matching if writer == "fd" and n == 0 and self.path.split("/")[-2] == tids[-1] else INFO
                yield SimpleNamespace(name=str(n), stat=stat)

    def stat(path):
        assert progress["fd_match_stat_attempts"] == attempts["fd_match_stat_attempts"] + 1
        attempts["fd_match_stat_attempts"] += 1
        return matching

    monkeypatch.setitem(scanner.ns, "_bounded_names", names)
    monkeypatch.setitem(scanner.ns, "_proc_read", read)
    monkeypatch.setattr(scanner.os, "scandir", Entries)
    monkeypatch.setattr(scanner.os, "stat", stat)
    call = lambda: scanner.ns["collect_image_writers"]({"journal": (42, 2)}, lambda: None,
        proc_root="/synthetic", progress=progress)
    return call, attempts, reads


@pytest.mark.parametrize("extra", [0, 1])
def test_joint_fd_maps_boundary_counts_actual_operations_and_stops_before_extra_task(scanner, monkeypatch, extra):
    progress = scanner.ns["scan_progress"]()
    scan, attempts, reads = counted_scan(scanner, monkeypatch, progress,
        tasks=512 + extra, per_task=2048, maps=maps_block(1048576))
    if extra:
        with pytest.raises(scanner.error) as caught:
            scan()
        assert str(caught.value) == reason("FD_STAT_CALLS", LIMIT + 1, LIMIT, 27, 513)
        assert progress["phase"] == "FD_INITIAL" and progress["pids_completed"] == 0
    else:
        assert scan() == [dict(pid=27, starttime=17, complete=True, writable_images=[])]
        assert progress["phase"] == "FINAL_PID_RECHECK" and progress["pids_completed"] == 1
    assert attempts == dict(fd_initial_stat_attempts=1048576, fd_recheck_stat_attempts=1048576,
                            fd_match_stat_attempts=0)
    assert all(progress[k] == v for k, v in attempts.items())
    assert progress["tasks_started"] == 512 + extra and progress["tasks_completed"] == 512
    assert progress["maps_files_read"] == len(reads) == 512
    assert progress["maps_bytes_read"] == 512 * 1048576
    assert progress["maps_max_file_bytes"] == 1048576 and not progress["scan_complete"]
    g.validate_progress(progress, request())


@pytest.mark.parametrize("writer", ["fd", "maps"])
def test_late_thread_private_writer_after_old_logical_fd_limit_is_still_observed(scanner, monkeypatch, writer):
    progress = scanner.ns["scan_progress"]()
    scan, attempts, reads = counted_scan(scanner, monkeypatch, progress,
        tasks=257, per_task=1024, writer=writer)
    assert scan()[0]["writable_images"] == ["journal"]
    assert attempts["fd_initial_stat_attempts"] == 263168 > 262144
    assert attempts["fd_recheck_stat_attempts"] == 263168
    assert attempts["fd_match_stat_attempts"] == (writer == "fd")
    assert len(reads) == 257 and progress["tasks_completed"] == 257


@pytest.mark.parametrize("kind,field", [("FD_ENTRIES", FIELDS[0]), ("FD_ENTRIES_RECHECK", FIELDS[1])])
@pytest.mark.parametrize("raises", [False, True])
def test_snapshot_uses_shared_remaining_budget_and_does_not_refund_errors(scanner, monkeypatch, kind, field, raises):
    progress = scanner.ns["scan_progress"]()
    progress[FIELDS[2]] = LIMIT - 1
    calls = []
    class Entries:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def __iter__(self):
            for name in ("1", "2"):
                def stat(*, follow_symlinks):
                    calls.append(True)
                    assert progress[field] == 1
                    if raises: raise PermissionError(13, "synthetic only")
                    return INFO
                yield SimpleNamespace(name=name, stat=stat)
    monkeypatch.setattr(scanner.os, "scandir", lambda _: Entries())
    with pytest.raises(PermissionError if raises else scanner.error):
        scanner.ns["_fd_snapshot"]("/synthetic/fd", lambda: None, 27, 29, kind,
                                      progress=progress)
    assert calls == [True] and progress[field] == 1
    assert sum(progress[k] for k in FIELDS) == LIMIT


def test_matching_stat_is_refused_before_call_when_snapshot_exhausted_shared_budget(scanner, monkeypatch):
    progress = scanner.ns["scan_progress"]()
    progress[FIELDS[1]] = LIMIT - 1
    scan, attempts, reads = counted_scan(scanner, monkeypatch, progress,
        tasks=1, per_task=1, writer="fd")
    with pytest.raises(scanner.error) as caught:
        scan()
    assert str(caught.value) == reason("FD_STAT_CALLS", LIMIT + 1, LIMIT, 27, 1)
    assert attempts[FIELDS[0]] == 1 and attempts[FIELDS[2]] == 0 and reads == []
    assert progress["phase"] == "FD_MATCH" and sum(progress[k] for k in FIELDS) == LIMIT


def test_matching_stat_failure_keeps_charge_and_stops_before_recheck(scanner, monkeypatch):
    progress = scanner.ns["scan_progress"]()
    scan, attempts, reads = counted_scan(scanner, monkeypatch, progress,
        tasks=1, per_task=1, writer="fd")
    calls = []
    def denied(path):
        assert progress["fd_match_stat_attempts"] == 1
        calls.append(path)
        raise PermissionError(13, "synthetic only")
    monkeypatch.setattr(scanner.os, "stat", denied)
    with pytest.raises(scanner.error, match="WRITERS_UNKNOWN"):
        scan()
    assert len(calls) == attempts[FIELDS[0]] == progress[FIELDS[2]] == 1
    assert progress[FIELDS[1]] == 0 and reads == []
    g.validate_progress(progress, request())


def prefix():
    return h.scan_progress() | dict(phase="FD_RECHECK", pids_listed=2, tasks_started=1,
        fd_initial_stat_attempts=2, fd_recheck_stat_attempts=3, fd_match_stat_attempts=1,
        last_valid_elapsed_ns=[123, 124])


INVALID = [(field, value) for field in (*FIELDS, "pids_completed", "tasks_started",
    "tasks_completed", "maps_files_read", "maps_bytes_read", "maps_max_file_bytes")
    for value in (-1, True, 0.5, 10**12)] + [
    ("phase", "private text"), ("phase", []), ("scan_complete", 1),
    ("scan_complete", True), ("pids_listed", True), ("pids_listed", None),
    ("pids_listed", 32769), ("last_valid_elapsed_ns", [0]),
    ("last_valid_elapsed_ns", [0, True]), ("last_valid_elapsed_ns", [-1, 0]),
    ("last_valid_elapsed_ns", [0, 15000000000]), ("last_valid_elapsed_ns", "x" * 4097),
    ("tasks_completed", 2), ("maps_files_read", 2), ("maps_bytes_read", 1),
    ("maps_max_file_bytes", 1), (FIELDS[0], LIMIT), ("pids_completed", 3),
]


@pytest.mark.parametrize("field,value", INVALID)
def test_v2_failure_rejects_invalid_progress(field, value):
    p = prefix() | {field: value}
    raw = h.canonical(dict(schema="lhq-journal-writer-result/v2", request=request(),
        complete=False, reason="GROWTH_PROC_DRIFT", errno=None, progress=p))
    with pytest.raises(g.r.ObservationError, match="^GROWTH_WRITER_FAILURE_REPORT$"):
        g.writer_failure(raw, request())


@pytest.mark.parametrize("change", ["missing", "extra", "null", "v1", "null_request", "different_request"])
def test_v2_failure_requires_exact_schema_request_and_progress(change):
    value = dict(schema="lhq-journal-writer-result/v2", request=request(), complete=False,
                 reason="GROWTH_PROC_DRIFT", errno=None, progress=prefix())
    if change == "missing": value["progress"].pop("phase")
    elif change == "extra": value["progress"]["private_path"] = "/synthetic"
    elif change == "null": value["progress"] = None
    elif change == "v1": value["schema"] = "lhq-journal-writer-result/v1"
    elif change == "null_request": value["request"] = None
    else: value["request"]["checkpoint"] = True
    with pytest.raises(g.r.ObservationError, match="FAILURE_REPORT"):
        g.writer_failure(h.canonical(value), request())


def test_v2_early_failure_and_report_failure_are_retained_without_admission(observer):
    early = dict(schema="lhq-journal-writer-result/v2", request=None, complete=False,
                 reason="GROWTH_WRITER_UID", errno=None, progress=None)
    assert g.writer_failure(h.canonical(early), request())["progress"] is None
    # A recheck can inspect added entries before drift; do not reject its valid prefix.
    late = early | dict(request=request(), progress=prefix(), reason="GROWTH_PROC_DRIFT")
    assert g.writer_failure(h.canonical(late), request())["progress"] == prefix()
    late["progress"] = report(request())["progress"]
    assert g.writer_failure(h.canonical(late), request())["progress"]["scan_complete"]
    with pytest.raises(g.r.ObservationError, match="WRITER_REPORT"):
        observer.value.validate(late, request(), 1)


@pytest.mark.parametrize("change", ["partial", "no_clock", "unknown_pids", "pid_unfinished",
    "task_unfinished", "maps_unfinished", "maps_over_limit", "wrong_phase", "v1", "missing"])
def test_success_never_admits_partial_or_old_progress(observer, change):
    value = report(request())
    p = value["progress"]
    if change == "partial": p["scan_complete"] = False
    elif change == "no_clock": p["last_valid_elapsed_ns"] = None
    elif change == "unknown_pids": p["pids_listed"] = None
    elif change == "pid_unfinished": p["pids_completed"] = 0
    elif change == "task_unfinished": p["tasks_completed"] = 0
    elif change == "maps_unfinished": p["maps_files_read"] = 0
    elif change == "maps_over_limit":
        p.update(tasks_started=513, tasks_completed=513, maps_files_read=513,
                 maps_bytes_read=513 * 1048576, maps_max_file_bytes=1048576)
    elif change == "wrong_phase": p["phase"] = "FINAL_PID_RECHECK"
    elif change == "v1": value["schema"] = "lhq-journal-writer-result/v1"
    else: value.pop("progress")
    with pytest.raises(g.r.ObservationError):
        observer.value.validate(value, request(), 1)


def generated_entry(payload, monkeypatch, *, elapsed=0):
    output, clock_calls = io.BytesIO(), []
    payload["os"] = SimpleNamespace(**(vars(payload["os"]) | {"geteuid": lambda: 0}))
    payload["resource"] = SimpleNamespace(**(vars(payload["resource"]) |
        {"setrlimit": lambda *a: None, "getrusage": lambda *a: SimpleNamespace(
            ru_utime=0, ru_stime=0, ru_maxrss=1)}))
    def clock(kind):
        clock_calls.append(kind)
        return NOW + elapsed
    payload["time"] = SimpleNamespace(clock_gettime_ns=clock, CLOCK_MONOTONIC=1, CLOCK_BOOTTIME=7)
    payload["sys"] = SimpleNamespace(argv=["fixed", "unused", "unused",
        base64.b64encode(h.canonical(request())).decode()], stdout=SimpleNamespace(buffer=output))
    payload["read_fact"] = lambda *a: (BOOT + "\n").encode()
    rc = payload["writer_entry"]()
    return rc, json.loads(output.getvalue()), clock_calls


@pytest.mark.parametrize("failure", [None, "maps", "final_deadline", "usage", "output"])
def test_generated_entry_progress_is_observed_prefix_and_final_check_precedes_complete(payload, proc_fixture,
                                                                                     monkeypatch, failure):
    root, task = proc_fixture
    if failure == "maps": (task / "maps").write_bytes(b"invalid\n")
    original = payload["collect_image_writers"]
    ticks = []
    def scan(images, check, **kw):
        rows = original(images, check, proc_root=str(root), progress=kw["progress"])
        if failure == "final_deadline":
            def overdue(kind):
                ticks.append(kind)
                return NOW + 15000000000
            payload["time"].clock_gettime_ns = overdue
        if failure == "usage":
            def unavailable(*a): raise OSError(5, "private usage error")
            payload["resource"].getrusage = unavailable
        if failure == "output":
            rows[0]["writable_images"] = ["journal"]
            rows *= 2000
        return rows
    payload["collect_image_writers"] = scan
    rc, result, calls = generated_entry(payload, monkeypatch, elapsed=123)
    p = result["progress"]
    assert p["last_valid_elapsed_ns"] == [123, 123]
    assert p["pids_listed"] == 1 and p["tasks_started"] == p["maps_files_read"] == 1
    assert rc == (0 if failure is None else 3)
    assert p["scan_complete"] is (failure in (None, "usage", "output"))
    assert p["phase"] == ("MAPS_PARSE" if failure == "maps" else
                           "FINAL_PID_RECHECK" if failure == "final_deadline" else "REPORT")
    if failure:
        assert g.writer_failure(h.canonical(result), request())["progress"] == p
    else:
        g.validate_progress(p, request(), success=True)
    if failure == "final_deadline": assert len(ticks) == 2  # No failure-time clock collection.
    if failure == "output": assert result["reason"] == "GROWTH_WRITER_OUTPUT"
    if failure == "maps": assert p["tasks_completed"] == p["pids_completed"] == 0


@pytest.mark.parametrize("name", ["q2_journal_growth.py", "q2_journal_growth_guest.py"])
@pytest.mark.parametrize("extra", [0, 1])
def test_source_admission_98304_boundary_only_for_maintenance_sources(source_git, monkeypatch, name, extra):
    original_read, original_run = h.local.stable_read, h.subprocess.run
    raw = b"#" + b"x" * (98303 + extra)
    def read(fd, cap, check):
        original, info = original_read(fd, cap, check)
        return (raw if original == Path(h.__file__).with_name(name).read_bytes() else original), info
    def run(argv, **kw):
        result = original_run(argv, **kw)
        if argv[-2:] == ["show", source_git.head + ":tests/e3_host/" + name]:
            result.stdout = raw
        return result
    monkeypatch.setattr(h.local, "stable_read", read)
    monkeypatch.setattr(h.subprocess, "run", run)
    if extra:
        with pytest.raises(g.r.ObservationError, match="SOURCE_LIMIT"): h.growth_sources(source_git.head)
    else:
        assert len(h.growth_sources(source_git.head)[name]) == 98304


@pytest.mark.parametrize("key,cap", [("guest", 98304), ("reader", 65536), ("input", 65536)])
@pytest.mark.parametrize("extra", [0, 1])
def test_bundle_and_actual_loader_apply_only_declared_source_limits(key, cap, extra):
    # Harmless synthetic code; the actual loader runs only in an unprivileged subprocess.
    entries = dict(reader=b"VALUE=1\n", guest=b"def entry(raw):\n return 0\n", input=b"{}")
    entries[key] += b" " * (cap + extra - len(entries[key]))
    packed = h.canonical({k: base64.b64encode(v).decode() for k, v in entries.items()})
    zipped = zlib.compress(packed, 9)
    result = subprocess.run([sys.executable, "-I", "-B", "-c", h.GUEST_LOADER,
        base64.b64encode(zipped).decode(), h.digest(zipped)], capture_output=True, timeout=5)
    assert (result.returncode == 0) is (not extra)
    if extra: assert (b"INPUT_BOUND" if key == "input" else b"SOURCE_BOUND") in result.stderr
    sources = {"q2_core_capacity_reader.py": entries["reader"], "q2_journal_growth_guest.py": entries["guest"]}
    # The bundle producer canonicalizes descriptor input; cover its exact byte boundary too.
    descriptor = {"padding": "x" * (cap + extra - len(h.canonical({"padding": ""})))} if key == "input" else {}
    if extra:
        with pytest.raises(g.r.ObservationError, match="BUNDLE_INPUT"): h.source_bundle(sources, descriptor)
    else:
        h.source_bundle(sources, descriptor)


@pytest.mark.parametrize("extra", [0, 1])
def test_fixed_writer_loader_keeps_32768_source_limit(extra):
    raw = b"pass\n" + b" " * (32768 + extra - 5)
    result = subprocess.run([sys.executable, "-I", "-B", "-c", g.WRITER_LOADER,
        base64.b64encode(raw).decode(), h.digest(raw), "e30="], capture_output=True, timeout=5)
    assert (result.returncode == 0) is (not extra)
    if extra: assert b"WRITER_SOURCE_PIN" in result.stderr


def test_generated_writer_code_still_refuses_oversized_payload():
    root = Path(h.__file__).parent
    host, guest, kernel = [(root / n).read_bytes() for n in (
        "q2_journal_growth.py", "q2_journal_growth_guest.py", "q2_host_kernel_facts.py")]
    with pytest.raises(g.r.ObservationError, match="WRITER_SOURCE_LIMIT"):
        g.writer_payload(host, guest, kernel + b"\n#" + b"x" * 32768, "d" * 40)


def test_compressed_bundle_and_argv_limits_remain_independent(monkeypatch):
    # Deterministic high-entropy synthetic input; each source is within its own cap.
    raw = random.Random(42).randbytes(98304)
    sources = {"q2_core_capacity_reader.py": b"#reader", "q2_journal_growth_guest.py": raw}
    with pytest.raises(g.r.ObservationError, match="BUNDLE_BOUND"):
        h.source_bundle(sources, {})
    zipped = b"x" * 49153
    result = subprocess.run([sys.executable, "-I", "-B", "-c", h.GUEST_LOADER,
        base64.b64encode(zipped).decode(), h.digest(zipped)], capture_output=True, timeout=5)
    assert result.returncode != 0 and b"BUNDLE_PIN" in result.stderr
    monkeypatch.setattr(h, "source_bundle", lambda *a: ("x" * 65536, "a" * 64))
    with pytest.raises(g.r.ObservationError, match="ARGV_LIMIT"):
        h.remote_argv("/synthetic/anchor", sources, {})


def test_completed_scan_still_requires_parent_writer_admission(observer):
    rows = observer.value.observe(KEYS, lambda: None)
    assert observer.value.reports[0]["progress"]["scan_complete"]
    with pytest.raises(g.r.ObservationError, match="UNEXPECTED_WRITER"):
        h.verify_writers(rows, None, ())
