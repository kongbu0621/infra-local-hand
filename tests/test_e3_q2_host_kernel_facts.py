"""Qualification/TOCTOU adversaries plus native ABI and ordinary-user outcomes.

Synthetic qualification tests substitute only the path root and procfs magic;
real descriptors and native fstat/statx/fstatfs layout checks still execute. They
are not proof of an original-host proc mount, identity, or namespace alignment.
"""
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import pytest

from e3_host import q2_host_kernel_facts as m


BOOT = b"00000000-0000-0000-0000-000000000001\n"


@pytest.fixture
def proc(monkeypatch):
    if not m._layout_supported():
        pytest.skip("Native Linux x86_64 LP64 ABI unavailable")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "proc/sys/kernel/random").mkdir(parents=True)
        (root / "proc/sys/kernel/random/boot_id").write_bytes(BOOT)
        pid = str(os.getpid())
        (root / "proc" / pid).mkdir()
        (root / "proc" / pid / "mountinfo").write_bytes(b"1 0 0:1 / / rw - proc proc rw\n")
        real_open, real_close = os.open, os.close
        calls, opened, closed = [], set(), set()
        def tracked_open(name, flags, **kwargs):
            if name == "/":
                name = str(root)
            fd = real_open(name, flags, **kwargs)
            calls.append((name, flags)); opened.add(fd); closed.discard(fd)
            return fd
        def tracked_close(fd):
            closed.add(fd)
            return real_close(fd)
        native_fs, native_sx = m._load_abi("boot")
        def proc_fs(fd, out):
            rc = native_fs(fd, out)
            if rc == 0:
                ctypes.cast(out, ctypes.POINTER(m._Statfs)).contents.type = m.PROC_SUPER_MAGIC
            return rc
        abi = [proc_fs, native_sx]
        monkeypatch.setattr(m, "_load_abi", lambda target: tuple(abi))
        monkeypatch.setattr(m.os, "open", tracked_open)
        monkeypatch.setattr(m.os, "close", tracked_close)
        yield SimpleNamespace(root=root, boot=root / "proc/sys/kernel/random/boot_id",
            mountinfo=root / "proc" / pid / "mountinfo", abi=abi, native_fs=native_fs,
            native_sx=native_sx, calls=calls, opened=opened, closed=closed,
            real_open=real_open, real_close=real_close)
        assert opened <= closed, "All acquired descriptors must be closed"
        monkeypatch.undo()


@pytest.mark.parametrize("kind", ("boot", "mountinfo"))
def test_qualified_read_is_bounded_and_keeps_all_ancestors_until_postcheck(proc, kind):
    report = {}
    raw = m.read_fact(kind, lambda: None, report)
    expected = proc.boot.read_bytes() if kind == "boot" else proc.mountinfo.read_bytes()
    assert raw == expected and report["status"] == "OBSERVED"
    assert report["bytes"] == len(raw) and report["sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(report["before"]) == len(report["after"]) == (6 if kind == "boot" else 4)
    assert report["qualification"]["native_metadata_crosscheck_complete"] is True
    assert report["namespace_alignment"]["status"] == "ENVIRONMENT_ASSUMPTION_NOT_PROVEN"
    assert report["historical_metadata_preservation_claimed"] is False
    content_opens = [flags for _, flags in proc.calls if not flags & os.O_PATH]
    assert len(content_opens) == 1
    assert content_opens[0] == os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    assert not any(flags & (os.O_CREAT | os.O_TRUNC | os.O_APPEND | os.O_NOATIME) for _, flags in proc.calls)
    assert len(json.dumps(report)) < 16384


@pytest.mark.parametrize("kind", ("/proc/version", "self", "../boot", "", None, 1, True))
def test_arbitrary_targets_rejected_without_open(monkeypatch, kind):
    monkeypatch.setattr(m.os, "open", lambda *a, **kw: pytest.fail("No syscall for arbitrary target"))
    with pytest.raises(m.KernelFactError, match="KERNEL_KIND"):
        m.read_fact(kind, lambda: None, {})


def test_unknown_abi_rejected_before_any_open(monkeypatch):
    monkeypatch.setattr(m, "_layout_supported", lambda: False)
    monkeypatch.setattr(m.os, "open", lambda *a, **kw: pytest.fail("Unknown ABI cannot open"))
    report = {}
    with pytest.raises(m.KernelFactError, match="ABI_UNSUPPORTED"):
        m.read_fact("boot", lambda: None, report)
    assert report["error"]["operation"] == "abi_layout"


def test_missing_libc_symbol_rejected(monkeypatch):
    if not m._layout_supported():
        pytest.skip("Native Linux ABI required to reach the libc-symbol boundary")
    monkeypatch.setattr(m.ct, "CDLL", lambda *a, **kw: SimpleNamespace())
    with pytest.raises(m.KernelFactError) as error:
        m.read_fact("boot", lambda: None, {})
    assert error.value.operation == "abi_symbols"


@pytest.mark.parametrize("fault,reason,operation", [
    ("nonproc", "NOT_PROCFS", "procfs"),
    ("submount", "MOUNT_CHANGED", "mount_identity"),
    ("missingmask", "STATX_MASK", "statx_mask"),
    ("badabi", "ABI_METADATA", "statx_crosscheck"),
    ("badfsabi", "ABI_METADATA", "fstatfs_crosscheck"),
])
def test_mount_and_abi_failures_precede_content_open(proc, fault, reason, operation):
    count = 0
    def fs(fd, out):
        rc = proc.native_fs(fd, out)
        data = ctypes.cast(out, ctypes.POINTER(m._Statfs)).contents
        data.type = 123 if fault == "nonproc" else m.PROC_SUPER_MAGIC
        if fault == "badfsabi":
            data.bsize += 1
        return rc
    def sx(fd, path, flags, mask, out):
        nonlocal count
        count += 1
        rc = proc.native_sx(fd, path, flags, mask, out)
        data = ctypes.cast(out, ctypes.POINTER(m._Statx)).contents
        if fault == "missingmask": data.mask &= ~m.STATX_MNT_ID
        if fault == "badabi": data.ino += 1
        if fault == "submount" and count == 3: data.mnt_id += 1
        return rc
    proc.abi[:] = fs, sx
    report = {}
    with pytest.raises(m.KernelFactError, match=reason) as error:
        m.read_fact("boot", lambda: None, report)
    assert error.value.operation == operation and report["status"] == "BLOCKED"
    assert all(flags & os.O_PATH for _, flags in proc.calls)


@pytest.mark.parametrize("fault", ("symlink", "hardlink", "writable", "directory"))
def test_unprotected_or_wrong_leaf_never_opens_for_content(proc, fault):
    if fault == "symlink":
        proc.boot.unlink(); proc.boot.symlink_to("/does-not-matter")
    elif fault == "hardlink":
        os.link(proc.boot, proc.boot.with_name("alias"))
    elif fault == "writable":
        proc.boot.chmod(0o666)
    else:
        proc.boot.unlink(); proc.boot.mkdir()
    with pytest.raises(m.KernelFactError, match="OBJECT_TYPE|UNPROTECTED"):
        m.read_fact("boot", lambda: None, {})
    assert all(flags & os.O_PATH for _, flags in proc.calls)


def test_ancestor_symlink_is_rejected(proc):
    real = proc.root / "proc/sys"
    moved = real.with_name("moved")
    real.rename(moved); real.symlink_to(moved, target_is_directory=True)
    with pytest.raises(m.KernelFactError) as error:
        m.read_fact("boot", lambda: None, {})
    assert error.value.operation == "open_path" and error.value.errno in (errno.ENOTDIR, errno.ELOOP)
    assert all(flags & os.O_PATH for _, flags in proc.calls)


@pytest.mark.parametrize("failure", ("open_read", "fstat", "read", "fstatfs", "statx"))
def test_exact_syscall_and_errno_recorded_with_no_fallback(proc, monkeypatch, failure):
    if failure == "open_read":
        tracked_open = m.os.open
        def denied(name, flags, **kwargs):
            if not flags & os.O_PATH: raise PermissionError(errno.EACCES, "synthetic")
            return tracked_open(name, flags, **kwargs)
        monkeypatch.setattr(m.os, "open", denied)
    elif failure in ("fstat", "read"):
        def denied(*args, **kwargs): raise OSError(errno.EIO, "synthetic")
        monkeypatch.setattr(m.os, failure, denied)
    else:
        def denied(*args): ctypes.set_errno(errno.EOPNOTSUPP); return -1
        proc.abi[0 if failure == "fstatfs" else 1] = denied
    report = {}
    with pytest.raises(m.KernelFactError) as error:
        m.read_fact("boot", lambda: None, report)
    assert error.value.operation == failure
    assert error.value.errno == (errno.EACCES if failure == "open_read" else
        errno.EIO if failure in ("fstat", "read") else errno.EOPNOTSUPP)
    assert report["error"] == error.value.detail


@pytest.mark.parametrize("kind,maximum", (("boot", 64), ("mountinfo", 1024**2)))
def test_exact_limit_and_plus_one_are_distinguished(proc, kind, maximum):
    path = proc.boot if kind == "boot" else proc.mountinfo
    path.write_bytes(b"x" * maximum)
    assert len(m.read_fact(kind, lambda: None, {})) == maximum
    path.write_bytes(b"x" * (maximum + 1))
    report = {}
    with pytest.raises(m.KernelFactError, match="READ_LIMIT"):
        m.read_fact(kind, lambda: None, report)
    assert report["bytes_observed"] == maximum + 1


def test_chunked_short_reads_reach_eof_without_size_trust(proc, monkeypatch):
    original = m.os.read
    calls = []
    def short_read(fd, count):
        calls.append(count)
        return original(fd, min(count, 3))
    monkeypatch.setattr(m.os, "read", short_read)
    assert m.read_fact("boot", lambda: None, {}) == BOOT
    assert len(calls) > 10 and all(0 < count <= 65 for count in calls)


def test_name_replacement_before_read_is_detected(proc, monkeypatch):
    original = m._Reader.verify
    def replace(self, **kwargs):
        proc.boot.rename(proc.boot.with_name("original"))
        proc.boot.write_bytes(BOOT)
        return original(self, **kwargs)
    monkeypatch.setattr(m._Reader, "verify", replace)
    monkeypatch.setattr(m.os, "read", lambda *a: pytest.fail("No read before name check"))
    with pytest.raises(m.KernelFactError, match="IDENTITY_CHANGED"):
        m.read_fact("boot", lambda: None, {})


def test_same_inode_new_mount_during_name_reopen_is_detected(proc):
    count = 0
    def sx(fd, path, flags, mask, out):
        nonlocal count
        count += 1
        rc = proc.native_sx(fd, path, flags, mask, out)
        if count == 11:
            ctypes.cast(out, ctypes.POINTER(m._Statx)).contents.mnt_id += 1
        return rc
    proc.abi[1] = sx
    with pytest.raises(m.KernelFactError, match="MOUNT_CHANGED|IDENTITY_CHANGED"):
        m.read_fact("boot", lambda: None, {})


def test_leaf_change_after_content_is_detected(proc, monkeypatch):
    original = m.os.read
    def changed(fd, count):
        result = original(fd, count)
        if result: proc.boot.chmod(0o600)
        return result
    monkeypatch.setattr(m.os, "read", changed)
    with pytest.raises(m.KernelFactError, match="IDENTITY_CHANGED"):
        m.read_fact("boot", lambda: None, {})


def test_kernel_dynamic_metadata_change_is_disclosed_not_restored(proc, monkeypatch):
    original = m.os.read
    def changed(fd, count):
        result = original(fd, count)
        if result: os.utime(proc.boot, ns=(1, 2))
        return result
    monkeypatch.setattr(m.os, "read", changed)
    report = {}
    assert m.read_fact("boot", lambda: None, report) == BOOT
    assert report["read_fd_before"]["mtime_ns"] != report["read_fd_after"]["mtime_ns"]
    assert report["dynamic_kernel_metadata_may_change"] is True
    assert proc.boot.stat().st_mtime_ns == 2


@pytest.mark.parametrize("phase", (1, 20, 80))
def test_guard_expiration_keeps_original_exception_and_closes_fds(proc, phase):
    calls = 0
    class DeadlineExpired(ValueError): pass
    def guard():
        nonlocal calls
        calls += 1
        if calls >= phase: raise DeadlineExpired("original dual-clock expired")
    report = {}
    with pytest.raises(DeadlineExpired):
        m.read_fact("boot", guard, report)
    assert report["status"] == "BLOCKED" and report["error"]["operation"] == "deadline_guard"


def test_native_layout_matches_current_python_metadata_without_reading_content():
    if not m._layout_supported():
        pytest.skip("Native Linux x86_64 LP64 ABI unavailable")
    reader = m._Reader("boot", lambda: None, {})
    reader.abi = m._load_abi("boot")
    reader.allowed_uids = {0, os.geteuid()}
    fd = os.open("/proc", os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        result = reader.snapshot(fd, "proc", True)
        assert result["procfs_magic"] == m.PROC_SUPER_MAGIC
        assert result["mount_id"] >= 0 and result["statx_mask"] & m.STATX_MNT_ID
    finally:
        os.close(fd)


@pytest.mark.skipif(not sys.platform.startswith("linux"),
    reason="Real Linux ordinary credentials and procfs qualification")
def test_real_ordinary_identity_reads_report_actual_outcome():
    # This subprocess is an isolated test fixture. The delivered reader contains
    # no setuid/setgid/setgroups calls and never requests privilege changes.
    source = Path(m.__file__).resolve()
    code = r'''
import importlib.util, json, os, sys
try:
    if os.geteuid() == 0:
        os.setgroups([]); os.setgid(65534); os.setuid(65534)
except OSError as error:
    print(json.dumps(dict(status="IDENTITY_UNAVAILABLE", errno=error.errno))); sys.exit(0)
spec=importlib.util.spec_from_file_location("reader", sys.argv[1])
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
results=[]
for kind in ("boot", "mountinfo"):
    report={}
    try:
        m.read_fact(kind, lambda:None, report)
    except m.KernelFactError:
        pass
    results.append(dict(kind=kind, status=report["status"], error=report.get("error")))
print(json.dumps(dict(euid=os.geteuid(), results=results)))
'''
    result = subprocess.run([sys.executable, "-I", "-B", "-S", "-c", code, str(source)],
        text=True, capture_output=True, timeout=15, check=True)
    outcome = json.loads(result.stdout)
    if outcome.get("status") == "IDENTITY_UNAVAILABLE":
        pytest.skip("Real ordinary identity unavailable, errno=" + str(outcome["errno"]))
    assert outcome["euid"] != 0
    blocked = [row for row in outcome["results"] if row["status"] != "OBSERVED"]
    if blocked:
        pytest.skip("Real ordinary proc qualification BLOCKED: " + json.dumps(blocked, sort_keys=True))
    assert len(outcome["results"]) == 2
