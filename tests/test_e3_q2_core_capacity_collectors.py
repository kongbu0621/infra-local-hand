"""Real retained-file I/O in a mapped test root; quota observations are doubles.

No guest connection, quota mutation, carrier marker or field acceptance occurs.
"""
from __future__ import annotations

from collections import Counter
import copy
import errno
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Project-quota collectors require Linux", allow_module_level=True)

from test_e3_q2_core_candidate_loader import d


class Deadline:
    def __init__(self):
        self.expired = False
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.expired:
            raise d.DispatchError("TEST_CAP_DEADLINE")


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    # Only absolute slash opens are mapped. All relative file operations are
    # actual syscalls on these test files, with production flags unchanged.
    tree = tmp_path / "kept"
    tree.mkdir(mode=0o700)
    (tree / "child").mkdir(mode=0o700)
    (tree / "child" / "payload").write_bytes(b"original payload")
    for path in (tree, tree / "child", tree / "child" / "payload"):
        os.utime(path, ns=(1000000000, 2000000000))
    pin = tree.stat()
    approved = {"retained_preparation": {"paths": [
        {"path": "/kept", "device": pin.st_dev, "inode": pin.st_ino}]}}
    e = d.FieldEffects({})
    clock = Deadline()
    e._effect_guard = clock
    e._capacity_owners = {0, os.getuid()}
    opened, closed, flags = [], [], []
    real_open, real_close = os.open, os.close

    def mapped_open(path, mode, *args, **kwargs):
        fd = real_open(str(tmp_path) if path == "/" else path, mode, *args, **kwargs)
        opened.append(fd)
        flags.append((str(path), mode))
        return fd

    def close(fd):
        closed.append(fd)
        return real_close(fd)

    monkeypatch.setattr(os, "open", mapped_open)
    monkeypatch.setattr(os, "close", close)
    monkeypatch.setattr(d, "_approved_inputs_envelope", lambda context: copy.deepcopy(approved))
    value = SimpleNamespace(e=e, clock=clock, tree=tree, root=tmp_path, approved=approved,
                            opened=opened, closed=closed, flags=flags, open=mapped_open)
    yield value
    assert Counter(opened) == Counter(closed), "collector leaked an owned descriptor"


def test_snapshot_reads_real_files_and_preserves_atime_and_order(fixture):
    f = fixture
    paths = [f.tree, f.tree / "child", f.tree / "child" / "payload"]
    before = {p: p.stat() for p in paths}
    rows = f.e._capacity_retained_snapshot()
    assert rows[0]["root"] == f.approved["retained_preparation"]["paths"][0]
    files = rows[0]["files"]
    assert [row["path"] for row in files] == ["/kept", "/kept/child", "/kept/child/payload"]
    assert files[-1]["sha256"] == d._sha(b"original payload")
    for path in paths:
        after = path.stat()
        assert before[path].st_atime_ns == after.st_atime_ns
        assert d._capacity_stat(before[path]) == d._capacity_stat(after)
    assert all(mode & os.O_NOATIME for name, mode in f.flags if name in (".", "payload"))


@pytest.mark.parametrize("field", ["inode", "device"])
def test_root_must_match_approved_object_before_enumeration(fixture, field):
    fixture.approved["retained_preparation"]["paths"][0][field] += 1
    with pytest.raises(d.DispatchError, match="RETAINED_IDENTITY"):
        fixture.e._capacity_retained_snapshot()
    assert not any(name == "." for name, _ in fixture.flags)


@pytest.mark.parametrize("kind", ["directory_link", "file_link", "hardlink", "fifo", "writable"])
def test_snapshot_rejects_aliases_special_files_and_unsafe_permissions(fixture, kind):
    f = fixture
    target = f.tree / "bad"
    if kind == "directory_link": target.symlink_to("child")
    elif kind == "file_link": target.symlink_to("child/payload")
    elif kind == "hardlink": os.link(f.tree / "child" / "payload", target)
    elif kind == "fifo": os.mkfifo(target, 0o600)
    else: (f.tree / "child" / "payload").chmod(0o666)
    with pytest.raises(d.DispatchError, match="RETAINED_|PATH_PROTECTION"):
        f.e._capacity_retained_snapshot()
    assert not any(name == "bad" for name, _ in f.flags)


def test_noatime_denial_never_falls_back_to_ordinary_read(fixture, monkeypatch):
    attempts = []
    def denied(path, flags, *args, **kwargs):
        if flags & os.O_NOATIME:
            attempts.append((str(path), flags))
            raise PermissionError(errno.EPERM, "test noatime denial")
        return fixture.open(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", denied)
    with pytest.raises(PermissionError): fixture.e._capacity_retained_snapshot()
    assert len(attempts) == 1 and attempts[0][0] == "."


@pytest.mark.parametrize("operation", ["open", "fstat", "stat", "read", "scandir"])
def test_late_effect_stops_snapshot_and_closes_owned_handles(fixture, monkeypatch, operation):
    f = fixture
    original = getattr(os, operation)
    calls, iterators = [], []
    def late(*args, **kwargs):
        value = original(*args, **kwargs)
        calls.append(args)
        if operation == "scandir": iterators.append(value)
        f.clock.expired = True
        return value
    monkeypatch.setattr(os, operation, late)
    with pytest.raises(d.DispatchError, match="TEST_CAP_DEADLINE"):
        f.e._capacity_retained_snapshot()
    assert len(calls) == 1
    assert all(next(it, None) is None for it in iterators)


@pytest.mark.parametrize("phase", ["item", "eof"])
def test_late_directory_iteration_is_not_a_complete_snapshot(fixture, monkeypatch, phase):
    f = fixture
    original = os.scandir
    closed = []
    class Entries:
        def __init__(self, fd): self.inner = original(fd)
        def __enter__(self): return self
        def __exit__(self, *args): self.close()
        def close(self): closed.append(True); self.inner.close()
        def __next__(self):
            value = next(self.inner, None)
            if (phase == "item" and value is not None) or (phase == "eof" and value is None):
                f.clock.expired = True
            if value is None: raise StopIteration
            return value
    monkeypatch.setattr(os, "scandir", Entries)
    with pytest.raises(d.DispatchError, match="TEST_CAP_DEADLINE"):
        f.e._capacity_retained_snapshot()
    assert closed


def test_leaf_change_after_read_is_rejected_by_named_recheck(fixture, monkeypatch):
    original = fixture.e.stable_read_at
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        (fixture.tree / "child" / "payload").write_bytes(b"changed contents")
        return result
    monkeypatch.setattr(fixture.e, "stable_read_at", mutate)
    with pytest.raises(d.DispatchError, match="RETAINED_DRIFT"):
        fixture.e._capacity_retained_snapshot()


def test_root_replacement_is_not_hidden_by_held_old_descriptor(fixture, monkeypatch):
    f = fixture
    original = f.e.stable_read_at
    def replace(*args, **kwargs):
        result = original(*args, **kwargs)
        f.tree.rename(f.root / "retained-old-tree")
        f.tree.mkdir(mode=0o700)
        return result
    monkeypatch.setattr(f.e, "stable_read_at", replace)
    with pytest.raises(d.DispatchError, match="RETAINED_DRIFT"):
        f.e._capacity_retained_snapshot()
    assert (f.root / "retained-old-tree" / "child" / "payload").read_bytes() == b"original payload"


def test_regular_to_fifo_race_cannot_block_in_open(fixture, monkeypatch):
    f = fixture
    def swap(path, flags, *args, **kwargs):
        if str(path) == "payload":
            assert flags & os.O_NONBLOCK, "must reject FIFO without waiting for a writer"
            target = f.tree / "child" / "payload"
            target.rename(target.with_name("retained-original"))
            os.mkfifo(target, 0o600)
        return f.open(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", swap)
    with pytest.raises(d.DispatchError, match="READ_FILE"):
        f.e._capacity_retained_snapshot()


def test_capacity_uses_supplied_original_preparation_clock(fixture):
    f = fixture
    prep = Deadline()
    f.clock.expired = True
    assert f.e._capacity_retained_snapshot(guard=prep)
    assert prep.calls > 20 and f.clock.calls == 0
    prep.expired = True
    with pytest.raises(d.DispatchError, match="TEST_CAP_DEADLINE"):
        f.e._capacity_retained_snapshot(guard=prep)


def test_parent_protection_is_checked_before_child_open(fixture):
    fixture.tree.chmod(0o777)
    with pytest.raises(d.DispatchError, match="PATH_PROTECTION"):
        fixture.e._capacity_retained_snapshot()
    assert not any(name == "." for name, _ in fixture.flags)


def test_oversized_retained_file_is_rejected_before_read(fixture, monkeypatch):
    monkeypatch.setattr(d, "MEMBER_LIMIT", 4)
    with pytest.raises(d.DispatchError, match="RETAINED_LIMIT"):
        fixture.e._capacity_retained_snapshot()
    assert not any(name == "payload" for name, _ in fixture.flags)


def test_quota_inventory_has_read_only_ordered_cursor_and_real_structure(monkeypatch):
    quota = d._CapQuota("/unused-test-device")
    calls = []
    def observe(command, project, value):
        calls.append((command, project))
        if project > 7: raise OSError(errno.ENOENT, "end of test inventory")
        value.project = 2 if project == 0 else 7
        value.hard, value.ihard = 1024, 128
    monkeypatch.setattr(quota, "call", observe)
    rows = quota.inventory(Deadline())
    assert [r["project"] for r in rows] == [2, 7]
    assert calls == [(0x800009, 0), (0x800009, 3), (0x800009, 8)]
    assert rows[0]["hard"] == 1024 and rows[0]["ihard"] == 128
    with pytest.raises(d.DispatchError, match="QUOTA_READ_ONLY"):
        d._CapQuota("/unused-test-device").call(0x800008, 2, quota.Block())


@pytest.mark.parametrize("fault", ["late_eof", "late_row", "late_error", "backward", "limit"])
def test_quota_inventory_never_promotes_partial_or_late_observations(monkeypatch, fault):
    quota = d._CapQuota("/unused-test-device")
    clock = Deadline()
    calls = []
    def observe(command, project, value):
        calls.append(project)
        if fault.startswith("late"):
            clock.expired = True
            if fault == "late_eof": raise OSError(errno.ENOENT, "late EOF")
            if fault == "late_error": raise OSError(errno.EIO, "late read error")
        value.project = 0 if fault == "backward" else project
    monkeypatch.setattr(quota, "call", observe)
    expected = "TEST_CAP_DEADLINE" if fault.startswith("late") else "QUOTA_ORDER|INVENTORY_LIMIT"
    with pytest.raises(d.DispatchError, match=expected): quota.inventory(clock)
    assert len(calls) == (128 if fault == "limit" else 2 if fault == "backward" else 1)


@pytest.fixture
def quota_device(fixture, monkeypatch):
    f = fixture
    # No block device is opened or created. Only its stat record and quota API
    # are modeled; the protected containing directory is a real held test fd.
    info = f.tree.stat()
    data = {key: getattr(info, key) for key in (
        "st_dev", "st_ino", "st_uid", "st_gid", "st_nlink", "st_size",
        "st_mtime_ns", "st_ctime_ns", "st_atime_ns")}
    data.update(st_mode=stat.S_IFBLK | 0o660, st_rdev=876)
    f.device = SimpleNamespace(**data)
    original = os.stat
    def observed(path, *args, **kwargs):
        return copy.copy(f.device) if str(path) == "device" else original(path, *args, **kwargs)
    monkeypatch.setattr(os, "stat", observed)
    f.e._admission_detail = {"quota_mount": {"source": "/device", "device": 876}}
    calls = []
    class Quota:
        def __init__(self, source): assert source == "/device"; calls.append("construct")
        def inventory(self, guard): guard(); calls.append("inventory"); guard(); return [{"project": 2}]
        def enforcement(self): calls.append("enforcement"); return 48
    monkeypatch.setattr(d, "_CapQuota", Quota)
    f.quota_calls, f.Quota = calls, Quota
    return f


def test_quota_collectors_bind_device_and_do_not_mutate(quota_device):
    f = quota_device
    assert f.e._capacity_quota_inventory() == [{"project": 2}]
    assert f.e._capacity_quota_enforcement() == 48
    assert f.quota_calls == ["construct", "inventory", "construct", "enforcement"]
    assert all(name == "/" for name, _ in f.flags)


@pytest.mark.parametrize("field,value", [("st_mode", stat.S_IFREG | 0o600), ("st_rdev", 999)])
def test_quota_device_mismatch_fails_before_native_call(quota_device, field, value):
    setattr(quota_device.device, field, value)
    with pytest.raises(d.DispatchError, match="QUOTA_DEVICE"):
        quota_device.e._capacity_quota_inventory()
    assert quota_device.quota_calls == []


def test_quota_device_replacement_rejects_returned_observation(quota_device, monkeypatch):
    f = quota_device
    def change(self): f.device.st_ino += 1; return 48
    monkeypatch.setattr(f.Quota, "enforcement", change)
    with pytest.raises(d.DispatchError, match="QUOTA_DEVICE_DRIFT"):
        f.e._capacity_quota_enforcement()


def test_quota_late_enforcement_does_not_return_success(quota_device, monkeypatch):
    f = quota_device
    def late(self): f.clock.expired = True; return 48
    monkeypatch.setattr(f.Quota, "enforcement", late)
    with pytest.raises(d.DispatchError, match="TEST_CAP_DEADLINE"):
        f.e._capacity_quota_enforcement()


def test_quota_requires_admission_details_before_io(monkeypatch):
    e = d.FieldEffects({})
    e._effect_guard = Deadline()
    monkeypatch.setattr(os, "open", lambda *a, **kw: pytest.fail("unexpected read"))
    with pytest.raises(d.DispatchError, match="CONTEXT_REQUIRED"):
        e._capacity_quota_inventory()


def test_guard_keyword_reaches_nested_operation_without_rebinding_outer_guard():
    outer, inner = Deadline(), Deadline()
    def observe(*, guard): assert guard is inner; guard(); return "observed"
    assert d._guard_call(outer, observe, guard=inner) == "observed"
    assert outer.calls == 2 and inner.calls == 1
