"""Frozen installer with real temporary I/O and injected late returns, not F1."""
from __future__ import annotations

import ast
import errno
import hashlib
import os
from pathlib import Path
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Frozen installer is Linux-only", allow_module_level=True)

from test_e3_q2_core_candidate_loader import ROOT, d, setup_loader

RELATIVE = "tests/e3_host/q2_prepare_build.py"
RAW = (ROOT / RELATIVE).read_bytes()


class Deadline:
    def __init__(self):
        self.expired = False
        self.checks = 0

    def __call__(self):
        self.checks += 1
        if self.expired:
            raise d.DispatchError("TEST_ORIGINAL_DEADLINE")


def load_build(guard):
    effects, verified, _, _ = setup_loader({RELATIVE: RAW})
    effects._effect_guard = guard
    return effects._candidate_helper("q2_prepare_build", verified)


def test_exact_frozen_source_and_private_bindings():
    assert hashlib.sha256(RAW).hexdigest() == "8c13ddb7c57161f315d83c63f2c13b3b0806e851d3d978005a6d4d74d7e8bbc6"
    original_open, original_stat = os.open, Path.stat
    build = load_build(Deadline())
    assert build.os is not os and build.Path is not Path
    assert os.open is original_open and Path.stat is original_stat
    assert build.install_candidate.__globals__["os"] is build.os
    assert build.regular.__globals__["Path"] is build.Path
    # All direct os accesses in the unchanged frozen source are supplied.
    tree = ast.parse(RAW)
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
             and isinstance(n.value, ast.Name) and n.value.id == "os"}
    assert names <= set(vars(build.os))


def test_frozen_create_read_and_inventory_use_real_files(tmp_path):
    guard = Deadline()
    build = load_build(guard)
    root = build.Path(tmp_path / "installation")
    build.mkdir_new(root)
    payload = bytes(range(256)) * 1000
    build.write_new(root / "payload", payload)
    assert build.regular(root / "payload") == payload
    inventory = build.bounded_inventory(root, protected=False)
    assert inventory["entries"] == 2
    assert inventory["bytes"] >= len(payload)
    assert guard.checks > 30
    with pytest.raises(FileExistsError):
        build.write_new(root / "payload", b"replacement")
    assert (root / "payload").read_bytes() == payload


@pytest.mark.parametrize("operation", ["open", "fstat", "read", "fchmod", "write", "fsync"])
def test_late_frozen_file_operation_stops_and_closes_fd(tmp_path, monkeypatch, operation):
    payload = tmp_path / "input"
    payload.write_bytes(b"x" * 131072)
    output = tmp_path / "partial"
    guard = Deadline()
    calls, opened, closed = [], [], []
    original = getattr(os, operation)
    original_open, original_close = os.open, os.close

    def record_open(*args, **kwargs):
        fd = original_open(*args, **kwargs)
        opened.append(fd)
        return fd

    def close(fd):
        closed.append(fd)
        return original_close(fd)

    def late(*args, **kwargs):
        calls.append(operation)
        value = (record_open if operation == "open" else original)(*args, **kwargs)
        guard.expired = True
        return value

    monkeypatch.setattr(os, "open", record_open)
    monkeypatch.setattr(os, "close", close)
    monkeypatch.setattr(os, operation, late)
    build = load_build(guard)
    writing = operation in ("open", "fchmod", "write", "fsync")
    with pytest.raises(d.DispatchError, match="TEST_ORIGINAL_DEADLINE"):
        if writing:
            build.write_new(build.Path(output), b"y" * 131072)
        else:
            build.regular(build.Path(payload))
    assert calls == [operation] and closed == opened and len(opened) == 1
    with pytest.raises(OSError) as failure:
        os.fstat(opened[0])
    assert failure.value.errno == errno.EBADF
    if writing:
        expected = {"open": 0, "fchmod": 0, "write": 65536, "fsync": 131072}[operation]
        assert output.read_bytes() == b"y" * expected
    assert payload.read_bytes() == b"x" * 131072


def test_frozen_short_writes_are_bounded_and_complete(tmp_path, monkeypatch):
    chunks = []
    original = os.write

    def short(fd, raw):
        chunks.append(len(raw))
        return original(fd, raw[:103])

    monkeypatch.setattr(os, "write", short)
    build = load_build(Deadline())
    target = tmp_path / "payload"
    raw = b"z" * 70000
    build.write_new(build.Path(target), raw)
    assert target.read_bytes() == raw
    assert max(chunks) == 65536 and min(chunks) > 0


@pytest.mark.parametrize("count", [0, -1, 70001, True])
def test_invalid_write_result_does_not_fsync(tmp_path, monkeypatch, count):
    syncs = []
    monkeypatch.setattr(os, "write", lambda *args: count)
    monkeypatch.setattr(os, "fsync", lambda *args: syncs.append(args))
    build = load_build(Deadline())
    with pytest.raises(d.DispatchError, match="INSTALL_STREAM_WRITE"):
        build.write_new(build.Path(tmp_path / "partial"), b"data")
    assert (tmp_path / "partial").read_bytes() == b"" and syncs == []


@pytest.mark.parametrize("operation", ["mkdir", "chmod", "stat", "listdir", "unlink", "readlink"])
def test_late_path_effect_has_no_followup_operation(tmp_path, monkeypatch, operation):
    root = tmp_path / "existing"
    root.mkdir()
    (root / "payload").write_bytes(b"retained")
    alias = root / "lib64"
    alias.symlink_to("lib")
    guard = Deadline()
    original = getattr(os, operation)
    calls = []

    def late(*args, **kwargs):
        value = original(*args, **kwargs)
        calls.append(str(args[0]))
        guard.expired = True
        return value

    monkeypatch.setattr(os, operation, late)
    build = load_build(guard)
    with pytest.raises(d.DispatchError, match="TEST_ORIGINAL_DEADLINE"):
        if operation in ("mkdir", "chmod"):
            build.mkdir_new(build.Path(tmp_path / "new"))
        elif operation in ("stat", "listdir"):
            build.bounded_inventory(build.Path(root), protected=False)
        elif operation == "unlink":
            build.Path(alias).unlink()
        else:
            build.os.readlink(alias)
    assert len(calls) == 1
    if operation == "mkdir":
        assert (tmp_path / "new").stat().st_mode & 0o777 == 0o755
    assert (root / "payload").read_bytes() == b"retained"


@pytest.mark.parametrize("method", ["lexists", "exists", "is_symlink"])
def test_late_missing_path_is_not_accepted_as_absence(tmp_path, monkeypatch, method):
    guard = Deadline()
    name = "lstat" if method == "lexists" else "stat"
    original = getattr(os, name)

    def missing(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        finally:
            guard.expired = True

    monkeypatch.setattr(os, name, missing)
    build = load_build(guard)
    path = build.Path(tmp_path / "missing")
    with pytest.raises(d.DispatchError, match="TEST_ORIGINAL_DEADLINE"):
        build.os.path.lexists(path) if method == "lexists" else getattr(path, method)()


def test_late_capability_absence_does_not_become_success(tmp_path, monkeypatch):
    target = tmp_path / "file"
    target.write_bytes(b"data")
    guard = Deadline()
    original = os.getxattr

    def missing(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        finally:
            guard.expired = True

    monkeypatch.setattr(os, "getxattr", missing)
    build = load_build(guard)
    with pytest.raises(d.DispatchError, match="TEST_ORIGINAL_DEADLINE"):
        build.os.getxattr(target, "security.capability", follow_symlinks=False)


def test_walk_preserves_regular_tree_inventory_and_rejects_links(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "one").write_bytes(b"one")
    (tmp_path / "two").write_bytes(b"two")
    build = load_build(Deadline())
    normalize = lambda rows: sorted((p, sorted(dirs), sorted(files)) for p, dirs, files in rows)
    assert normalize(build.os.walk(tmp_path)) == normalize(os.walk(tmp_path))
    (tmp_path / "alias").symlink_to("a")
    with pytest.raises(d.DispatchError, match="INSTALL_WALK_ALIAS"):
        list(build.os.walk(tmp_path))


def test_walk_does_not_enter_next_directory_after_deadline(tmp_path):
    (tmp_path / "a").mkdir()
    guard = Deadline()
    build = load_build(guard)
    walker = build.os.walk(tmp_path)
    assert next(walker)[1] == ["a"]
    guard.expired = True
    with pytest.raises(d.DispatchError, match="TEST_ORIGINAL_DEADLINE"):
        next(walker)


@pytest.mark.parametrize("name", ["/usr/bin/systemctl", "/usr/bin/systemd-run"])
def test_resolve_retains_only_admitted_literal_program(name):
    if not Path(name).is_file():
        pytest.skip("Test machine lacks the fixed systemd program")
    build = load_build(Deadline())
    assert build.Path(name).resolve(strict=True) == Path(name).resolve(strict=True)
    with pytest.raises(d.DispatchError, match="INSTALL_RESOLVE_PATH"):
        build.Path(name).resolve()


def test_resolve_checks_each_ancestor_and_rejects_alias(tmp_path, monkeypatch):
    target = tmp_path / "alias"
    target.symlink_to("missing")
    link = target.lstat()
    original = os.stat
    calls = []

    def inspect(path, **kwargs):
        calls.append(str(path))
        return link if str(path) == "/usr/bin/systemctl" else original(path, **kwargs)

    monkeypatch.setattr(os, "stat", inspect)
    build = load_build(Deadline())
    with pytest.raises(d.DispatchError, match="INSTALL_RESOLVE_ALIAS"):
        build.Path("/usr/bin/systemctl").resolve(strict=True)
    assert calls == ["/", "/usr", "/usr/bin", "/usr/bin/systemctl"]


def test_stream_does_not_close_callers_fd_or_flush_after_failure(tmp_path):
    guard = Deadline()
    bindings = d._InstallIO(guard)
    fd = os.open(tmp_path / "partial", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with pytest.raises(d.DispatchError, match="TEST_ORIGINAL_DEADLINE"):
            with bindings.os.fdopen(fd, "wb", closefd=False) as stream:
                stream.write(b"first")
                guard.expired = True
                stream.write(b"second")
        assert os.fstat(fd).st_size == 5
    finally:
        os.close(fd)
    assert (tmp_path / "partial").read_bytes() == b"first"
