import copy
import os
import stat
import time
from types import SimpleNamespace

import pytest

from e3_host import q2_core_capture as cap

pytestmark = pytest.mark.skipif(not hasattr(time, "CLOCK_BOOTTIME") or not hasattr(os, "O_NOATIME"),
                                reason="Linux-only live capture component")

class Clock:
    def __init__(self):
        self.now = {time.CLOCK_BOOTTIME: 100, time.CLOCK_MONOTONIC: 200}
        self.calls = []

    def __call__(self, which):
        self.calls.append(which)
        return self.now[which]

    def origins(self):
        return {"host_boottime_origin_ns": 100, "host_monotonic_origin_ns": 200,
                "host_boottime_deadline_ns": 100 + cap.WINDOW_NS,
                "host_monotonic_deadline_ns": 200 + cap.WINDOW_NS}

    def expire(self):
        self.now[time.CLOCK_BOOTTIME] += cap.WINDOW_NS


@pytest.fixture
def capture(tmp_path):
    if not hasattr(os, "O_NOATIME") or not hasattr(time, "CLOCK_BOOTTIME"):
        pytest.skip("real local persistence test requires Linux proc/NOATIME/BOOTTIME")
    os.chmod(tmp_path, 0o700)
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    st = os.fstat(parent)
    anchor = dict(path=str(tmp_path), dev=st.st_dev, ino=st.st_ino, mode=0o700,
                  uid=st.st_uid, gid=st.st_gid, nlink=st.st_nlink)
    clock = Clock()
    writer = cap.observe_writer(cap.Deadline(clock.origins(), clock).call)
    current = copy.deepcopy(writer)
    def observer(_call):
        return current
    obj = cap.LiveCapture(parent, anchor=anchor, writer=writer, origins=clock.origins(),
                          clock_gettime_ns=clock, writer_observer=observer)
    yield obj, clock, tmp_path, current
    # Test harness cleanup closes descriptors, never deletes or rewrites the
    # retained capture files. This is outside the component's execution window.
    for fd in tuple(obj._descriptors):
        os.close(fd)
    os.close(parent)


def test_bound_writer_reads_process_not_guest_identity():
    if not hasattr(os, "O_NOATIME"):
        pytest.skip("requires Linux")
    clock = Clock()
    value = cap.observe_writer(cap.Deadline(clock.origins(), clock).call)
    assert value["process"]["pid"] == os.getpid()
    assert value["uid"]["filesystem"] == os.geteuid()
    assert value["gid"]["filesystem"] == os.getegid()
    assert value["supplementary_gids"] == sorted(set(os.getgroups()))
    assert value["user_namespace"]["ino"] == os.stat("/proc/self/ns/user").st_ino


def test_original_window_strict_order_and_no_extra_tail():
    if not hasattr(time, "CLOCK_BOOTTIME"):
        pytest.skip("requires BOOTTIME")
    clock = Clock()
    guard = cap.Deadline(clock.origins(), clock)
    guard.call(lambda: None)
    assert clock.calls == [time.CLOCK_BOOTTIME, time.CLOCK_MONOTONIC] * 2
    clock.expire()
    with pytest.raises(cap.CaptureError, match="DEADLINE"):
        guard.call(lambda: pytest.fail("expired syscall must not start"))
    with pytest.raises(cap.CaptureError, match="CLOCK_STOPPED"):
        guard.check()


@pytest.mark.parametrize("delta", [-1, 1, 5_000_000_000])
def test_reject_non_original_window(delta):
    clock = Clock()
    origins = clock.origins()
    origins["host_monotonic_deadline_ns"] += delta
    with pytest.raises(cap.CaptureError, match="CLOCK_WINDOW"):
        cap.Deadline(origins, clock)


def test_all_six_files_fsync_reread_and_observed_accounting(capture):
    obj, clock, path, _ = capture
    result = {}
    for role in cap.ROLE_LIMITS:
        result[role] = obj.create(role, role.encode("ascii"))
    accounting = obj.finish()
    assert set(p.name for p in path.iterdir()) == set(cap.BASENAMES.values())
    for role, item in result.items():
        st = os.stat(path / cap.BASENAMES[role])
        assert (path / cap.BASENAMES[role]).read_bytes() == role.encode()
        assert stat.S_IMODE(st.st_mode) == 0o600 and st.st_nlink == 1
        assert item["allocated_bytes"] == st.st_blocks * 512
    assert accounting == dict(mode=cap.ACCOUNTING_MODE,
        logical_bytes_written=sum(len(r) for r in cap.ROLE_LIMITS), created_inodes=6,
        max_observed_allocated_bytes=sum(p.stat().st_blocks * 512 for p in path.iterdir()),
        full_filesystem_peak_proven=False)
    assert clock.calls == [time.CLOCK_BOOTTIME, time.CLOCK_MONOTONIC] * (len(clock.calls) // 2)


def test_marker_is_first_and_failure_cannot_resume(capture):
    obj, _, path, _ = capture
    with pytest.raises(cap.CaptureError, match="MARKER_FIRST"):
        obj.create("stdout", b"x")
    assert not list(path.iterdir())
    with pytest.raises(cap.CaptureError, match="CREATE_ONCE"):
        obj.create("marker", b"x")


def test_existing_object_never_adopted_overwritten_or_retried(capture):
    obj, _, path, _ = capture
    target = path / cap.BASENAMES["marker"]
    target.write_bytes(b"old partial")
    with pytest.raises(FileExistsError):
        obj.create("marker", b"replacement")
    assert target.read_bytes() == b"old partial"
    with pytest.raises(cap.CaptureError):
        obj.create("marker", b"second")
    assert obj.logical == 0 and not obj.objects


def test_one_role_attempt_and_no_seventh_file(capture):
    obj, _, path, _ = capture
    obj.create("marker", b"marker")
    with pytest.raises(cap.CaptureError, match="CREATE_ONCE"):
        obj.create("attestation", b"forbidden")
    assert len(list(path.iterdir())) == 1


@pytest.mark.parametrize("role", list(cap.ROLE_LIMITS))
def test_fixed_role_caps_checked_before_creation(capture, monkeypatch, role):
    obj, _, path, _ = capture
    if role != "marker":
        obj.create("marker", b"m")
    monkeypatch.setitem(cap.ROLE_LIMITS, role, 3)
    with pytest.raises(cap.CaptureError, match="ROLE_LIMIT"):
        obj.create(role, b"1234")
    assert not (path / cap.BASENAMES[role]).exists()


def test_combined_stream_cap_cannot_borrow_remaining_files(capture, monkeypatch):
    obj, _, path, _ = capture
    monkeypatch.setattr(cap, "STREAM_LIMIT", 7)
    obj.create("marker", b"m")
    obj.create("stdout", b"12345")
    with pytest.raises(cap.CaptureError, match="STREAM_LIMIT"):
        obj.create("stderr", b"123")
    assert not (path / cap.BASENAMES["stderr"]).exists()
    assert obj.logical == 6


def test_short_positive_writes_each_charged_and_sampled(capture, monkeypatch):
    obj, _, _, _ = capture
    real_write = os.write
    counts = []
    def short(fd, raw):
        count = real_write(fd, raw[:2])
        counts.append(count)
        return count
    monkeypatch.setattr(os, "write", short)
    obj.create("marker", b"12345")
    assert counts == [2, 2, 1] and obj.logical == 5
    assert obj.objects["marker"]["written"] == 5


def test_zero_write_retains_partial_marker_no_retry(capture, monkeypatch):
    obj, _, path, _ = capture
    real_write = os.write
    calls = []
    def zero_after_one(fd, raw):
        calls.append(len(raw))
        return real_write(fd, raw[:1]) if len(calls) == 1 else 0
    monkeypatch.setattr(os, "write", zero_after_one)
    with pytest.raises(cap.CaptureError, match="SHORT_WRITE"):
        obj.create("marker", b"12345")
    assert (path / cap.BASENAMES["marker"]).read_bytes() == b"1"
    assert obj.logical == 1 and not obj.objects["marker"]["complete"]
    with pytest.raises(cap.CaptureError):
        obj.create("marker", b"retry")
    assert len(calls) == 2


def test_late_write_charged_then_no_fsync(capture, monkeypatch):
    obj, clock, path, _ = capture
    real_write = os.write
    def late(fd, raw):
        count = real_write(fd, raw)
        clock.expire()
        return count
    monkeypatch.setattr(os, "write", late)
    monkeypatch.setattr(os, "fsync", lambda _fd: pytest.fail("no fsync after expiry"))
    with pytest.raises(cap.CaptureError, match="DEADLINE"):
        obj.create("marker", b"12345")
    assert obj.logical == 5 and (path / cap.BASENAMES["marker"]).read_bytes() == b"12345"
    assert not obj.objects["marker"]["complete"]


def test_late_exclusive_create_is_still_consumed(capture, monkeypatch):
    obj, clock, path, _ = capture
    real_open = os.open
    def late(*args, **kwargs):
        fd = real_open(*args, **kwargs)
        clock.expire()
        return fd
    monkeypatch.setattr(os, "open", late)
    with pytest.raises(cap.CaptureError, match="DEADLINE"):
        obj.create("marker", b"never written")
    assert (path / cap.BASENAMES["marker"]).read_bytes() == b""
    assert len(obj.objects) == 1 and not obj.objects["marker"]["complete"]


def test_writer_change_prevents_next_persistence(capture):
    obj, _, path, writer = capture
    obj.create("marker", b"m")
    writer["uid"]["filesystem"] += 1
    with pytest.raises(cap.CaptureError, match="WRITER_CHANGED"):
        obj.create("stdout", b"x")
    assert not (path / cap.BASENAMES["stdout"]).exists()


def test_anchor_change_prevents_next_persistence(capture):
    obj, _, path, _ = capture
    obj.create("marker", b"m")
    os.chmod(path, 0o750)
    with pytest.raises(cap.CaptureError, match="ANCHOR_CHANGED"):
        obj.create("stdout", b"x")
    assert not (path / cap.BASENAMES["stdout"]).exists()


def test_one_owned_file_changed_stops_all_later_writes(capture):
    obj, _, path, _ = capture
    obj.create("marker", b"m")
    os.chmod(path / cap.BASENAMES["marker"], 0o640)
    with pytest.raises(cap.CaptureError, match="FILE_CHANGED"):
        obj.create("stdout", b"x")
    assert not (path / cap.BASENAMES["stdout"]).exists()


@pytest.mark.parametrize("boundary", ["create", "write", "file_fsync", "parent_fsync"])
def test_every_persistence_boundary_samples_real_blocks(capture, monkeypatch, boundary):
    obj, _, path, _ = capture
    real_open, real_write, real_fsync = os.open, os.write, os.fsync
    original_fstat, original_stat = os.fstat, os.stat
    exceed = False
    def opened(*args, **kwargs):
        nonlocal exceed
        fd = real_open(*args, **kwargs)
        if args[1] & os.O_CREAT and boundary == "create":
            exceed = True
        return fd
    def written(fd, raw):
        nonlocal exceed
        count = real_write(fd, raw)
        if boundary == "write":
            exceed = True
        return count
    def synced(fd):
        nonlocal exceed
        real_fsync(fd)
        if (fd == obj.directory_fd) == (boundary == "parent_fsync"):
            if boundary in ("file_fsync", "parent_fsync"):
                exceed = True
    def altered(st):
        if exceed and stat.S_ISREG(st.st_mode):
            data = {key: getattr(st, key) for key in dir(st) if key.startswith("st_")}
            data["st_blocks"] = cap.ALLOCATION_LIMIT // 512 + 1
            return SimpleNamespace(**data)
        return st
    monkeypatch.setattr(os, "open", opened)
    monkeypatch.setattr(os, "write", written)
    monkeypatch.setattr(os, "fsync", synced)
    monkeypatch.setattr(os, "fstat", lambda fd: altered(original_fstat(fd)))
    monkeypatch.setattr(os, "stat", lambda *a, **kw: altered(original_stat(*a, **kw)))
    with pytest.raises(cap.CaptureError, match="OBSERVED_BUDGET"):
        obj.create("marker", b"m")
    assert obj.max_allocated == cap.ALLOCATION_LIMIT + 512
    assert (path / cap.BASENAMES["marker"]).exists()
    assert not obj.objects["marker"]["complete"]


def test_noatime_read_failure_never_falls_back(capture, monkeypatch):
    obj, _, path, _ = capture
    real_open = os.open
    reads = []
    def failed_read(*args, **kwargs):
        if not args[1] & os.O_CREAT:
            reads.append(args[1])
            raise PermissionError("synthetic noatime failure")
        return real_open(*args, **kwargs)
    monkeypatch.setattr(os, "open", failed_read)
    with pytest.raises(PermissionError):
        obj.create("marker", b"m")
    assert len(reads) == 1 and reads[0] & os.O_NOATIME and reads[0] & os.O_NOFOLLOW
    assert (path / cap.BASENAMES["marker"]).read_bytes() == b"m"


def test_complete_text_is_not_success_after_late_receipt_parent_fsync(capture, monkeypatch):
    obj, clock, path, _ = capture
    for role in ("marker", "stdout", "stderr", "remote_result", "capture_manifest"):
        obj.create(role, b"{}")
    real_fsync = os.fsync
    def late_parent(fd):
        real_fsync(fd)
        if fd == obj.directory_fd:
            clock.expire()
    monkeypatch.setattr(os, "fsync", late_parent)
    raw = b'{"state":"COMPLETE"}'
    with pytest.raises(cap.CaptureError, match="DEADLINE"):
        obj.create("local_receipt", raw)
    assert (path / cap.BASENAMES["local_receipt"]).read_bytes() == raw
    with pytest.raises(cap.CaptureError, match="LIVE_RECEIPT"):
        obj.finish()
    with pytest.raises(cap.CaptureError):
        obj.create("local_receipt", b'{"state":"STOP_AND_RETAIN"}')
    assert len(list(path.iterdir())) == 6
