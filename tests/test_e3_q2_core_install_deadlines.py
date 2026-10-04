"""Real file I/O with injected late returns, never a field installation."""
from __future__ import annotations

import copy
import errno
import importlib.util
import os
from pathlib import Path
import stat
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Core installation uses Linux held descriptors", allow_module_level=True)

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "_core_install_deadlines_test", ROOT / "tests/e3_host/q2_core_delivery_dispatcher.py")
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def effects():
    outer = {"boot_id": "test-boot", "boottime_deadline_ns": 100 * d.NS,
             "monotonic_deadline_ns": 200 * d.NS}
    value = d.FieldEffects({"guest_deadlines": copy.deepcopy(outer)})
    now = {"boot_id": "test-boot", "boottime_ns": 10 * d.NS, "monotonic_ns": 110 * d.NS}
    value.now = lambda: dict(now)
    return value, now, outer


@pytest.mark.parametrize("clock,limit", [("boottime_ns", 55), ("monotonic_ns", 155)])
def test_installation_reserve_uses_each_original_clock_without_refresh(clock, limit):
    value, now, outer = effects()
    now[clock] = limit * d.NS - 1
    value._effect_guard()
    now[clock] += 1
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_DEADLINE"):
        value._effect_guard()
    assert value.context["guest_deadlines"] == outer


def test_late_create_retains_object_and_closes_new_descriptor(tmp_path, monkeypatch):
    value, now, _ = effects()
    parent = d.FieldEffects._held_directory(str(tmp_path))
    opened = []
    original = os.open

    def late_open(*args, **kwargs):
        fd = original(*args, **kwargs)
        opened.append(fd)
        now["boottime_ns"] = 55 * d.NS
        return fd

    monkeypatch.setattr(d.os, "open", late_open)
    try:
        with pytest.raises(d.DispatchError, match="CORE_DISPATCH_DEADLINE"):
            value.create_only_at(parent, "partial", b"unwritten", mode=384,
                                 guard=value._effect_guard)
        assert len(opened) == 1
        with pytest.raises(OSError) as failure:
            os.fstat(opened[0])
        assert failure.value.errno == errno.EBADF
        assert (tmp_path / "partial").read_bytes() == b""
        assert os.fstat(parent).st_ino == tmp_path.stat().st_ino
    finally:
        os.close(parent)


def test_late_short_write_never_writes_remaining_bytes_or_fsyncs(tmp_path, monkeypatch):
    value, now, _ = effects()
    writes, syncs = [], []
    original = os.write

    def late_write(fd, raw):
        count = original(fd, raw[:7])
        writes.append(count)
        now["monotonic_ns"] = 155 * d.NS
        return count

    monkeypatch.setattr(d.os, "write", late_write)
    monkeypatch.setattr(d.os, "fsync", lambda fd: syncs.append(fd))
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_DEADLINE"):
        value.create_only(str(tmp_path / "partial"), b"abcdefghijk", mode=384,
                          guard=value._effect_guard)
    assert writes == [7] and syncs == []
    assert (tmp_path / "partial").read_bytes() == b"abcdefg"


def test_late_read_rejects_chunk_and_does_not_read_again(tmp_path, monkeypatch):
    value, now, _ = effects()
    path = tmp_path / "payload"
    path.write_bytes(b"x" * 131072)
    original = os.read
    reads = []

    def late_read(fd, size):
        raw = original(fd, size)
        reads.append(len(raw))
        now["boottime_ns"] = 55 * d.NS
        return raw

    monkeypatch.setattr(d.os, "read", late_read)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_DEADLINE"):
        value.stable_read(str(path), maximum=131072, guard=value._effect_guard)
    assert reads == [65536]


def test_late_mkdir_retains_directory_but_does_not_open_it(tmp_path, monkeypatch):
    value, now, _ = effects()
    parent = value._held_directory(str(tmp_path))
    original = os.mkdir
    opened = []

    def late_mkdir(*args, **kwargs):
        original(*args, **kwargs)
        now["boottime_ns"] = 55 * d.NS

    monkeypatch.setattr(d.os, "mkdir", late_mkdir)
    monkeypatch.setattr(d.os, "open", lambda *args, **kwargs: opened.append(args))
    try:
        with pytest.raises(d.DispatchError, match="CORE_DISPATCH_DEADLINE"):
            value._mkdir_at(parent, "partial", 448, guard=value._effect_guard)
        assert opened == [] and (tmp_path / "partial").is_dir()
    finally:
        os.close(parent)


def test_late_extraction_stops_before_second_member(tmp_path, monkeypatch):
    value, now, _ = effects()
    blobs = {"first": b"first bytes", "second": b"second bytes"}
    value.context.update(members=blobs, manifest={"locators": {'install_parent': str(tmp_path)}, "members": [
        {"path": name, "role": "candidate-worktree", "bytes": len(raw),
         "sha256": d._sha(raw), "mode": 420} for name, raw in blobs.items()]})
    parent = value._held_directory(str(tmp_path))
    original = os.write

    def late_write(fd, raw):
        count = original(fd, raw)
        now["monotonic_ns"] = 155 * d.NS
        return count

    monkeypatch.setattr(d.os, "write", late_write)
    try:
        with pytest.raises(d.DispatchError, match="CORE_DISPATCH_DEADLINE"):
            value._extract_install_members(parent)
        assert (tmp_path / "first").read_bytes() == blobs["first"]
        assert not (tmp_path / "second").exists()
        assert os.fstat(parent).st_ino == tmp_path.stat().st_ino
    finally:
        os.close(parent)


@pytest.mark.parametrize("late_at", ["scandir", "next", "stat"])
def test_scan_rejects_late_directory_steps_and_closes_iterator(tmp_path, monkeypatch, late_at):
    if os.geteuid() != 0:
        pytest.skip("Protected installation storage requires root-owned fixture")
    value, now, _ = effects()
    (tmp_path / "payload").write_bytes(b"content")
    value._install_roots = [str(tmp_path)]
    original = os.scandir
    events = []

    def expire(point):
        events.append(point)
        if point == late_at:
            now["boottime_ns"] = 55 * d.NS

    class Entry:
        def __init__(self, entry):
            self.entry = entry
            self.name = entry.name

        def stat(self, **kwargs):
            result = self.entry.stat(**kwargs)
            expire("stat")
            return result

    class Scan:
        def __init__(self, fd):
            self.entries = original(fd)
            expire("scandir")

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

        def __iter__(self):
            return self

        def __next__(self):
            item = next(self.entries)
            expire("next")
            return Entry(item)

        def close(self):
            self.entries.close()
            events.append("close")

    monkeypatch.setattr(d.os, "scandir", Scan)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_DEADLINE"):
        value._observe_install_storage()
    assert events == ["scandir", "next", "stat"][:
        ["scandir", "next", "stat"].index(late_at) + 1] + ["close"]
    assert value._shared_observed_bytes == value._shared_observed_inodes == 0


def test_guarded_create_preserves_exact_mode_bytes_and_collision(tmp_path):
    value, _, _ = effects()
    path = str(tmp_path / "complete")
    identity = value.create_only(path, b"complete\n", mode=384, guard=value._effect_guard)
    raw, reread = value.stable_read(path, maximum=9, expected_mode=384, guard=value._effect_guard)
    assert raw == b"complete\n" and reread == identity
    with pytest.raises(FileExistsError):
        value.create_only(path, b"replacement", mode=384, guard=value._effect_guard)
    assert Path(path).read_bytes() == b"complete\n"


def test_final_parent_fsync_late_return_cannot_accept_complete_bytes(tmp_path, monkeypatch):
    value, now, _ = effects()
    original = os.fsync
    syncs = []

    def late_parent(fd):
        directory = stat.S_ISDIR(os.fstat(fd).st_mode)
        original(fd)
        syncs.append(directory)
        if directory:
            now["monotonic_ns"] = 155 * d.NS

    monkeypatch.setattr(d.os, "fsync", late_parent)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_DEADLINE"):
        value.create_only(str(tmp_path / "complete"), b"complete", mode=384,
                          guard=value._effect_guard)
    assert syncs == [False, True]
    assert (tmp_path / "complete").read_bytes() == b"complete"


@pytest.mark.parametrize("late", [False, True])
def test_missing_storage_error_cannot_hide_a_late_return(monkeypatch, late):
    value, now, _ = effects()
    value._install_roots = ["/absent/installation"]

    def missing(*args, **kwargs):
        if late:
            now["boottime_ns"] = 55 * d.NS
        raise FileNotFoundError(errno.ENOENT, "test absent installation")

    monkeypatch.setattr(d.os, "open", missing)
    if late:
        with pytest.raises(d.DispatchError, match="CORE_DISPATCH_DEADLINE"):
            value._observe_install_storage()
    else:
        assert value._observe_install_storage() == {"bytes": 0, "inodes": 0}
