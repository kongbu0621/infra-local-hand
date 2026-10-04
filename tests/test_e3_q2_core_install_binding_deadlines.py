"""Late executable-binding I/O must stop before another read or child launch."""
from __future__ import annotations

import errno
import os
from pathlib import Path
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Held executable binding requires Linux", allow_module_level=True)

from test_e3_q2_core_install_binding import bound, d


@pytest.mark.parametrize("late_at", [
    "open", "first_fstat", "getxattr_return", "getxattr_enodata",
    "getxattr_enotsup", "pread", "last_fstat", "stat",
])
def test_late_binding_io_stops_closes_and_never_spawns(bound, monkeypatch, late_at):
    program = bound._admission["programs"]["python"]["path"]
    original = {name: getattr(os, name) for name in
                ("open", "fstat", "getxattr", "pread", "stat", "close")}
    read = bound.stable_read
    binding_phase = False
    expired = False
    opened, closed, events, spawned = [], [], [], []
    binding_fd = None
    fstat_count = 0

    def guard():
        if expired:
            raise d.DispatchError("TEST_BINDING_DEADLINE")

    def validated_read(*args, **kwargs):
        nonlocal binding_phase
        result = read(*args, **kwargs)
        binding_phase = True
        return result

    def finish(name):
        nonlocal expired
        events.append(name)
        if name == late_at or (name == "getxattr" and late_at.startswith("getxattr_")):
            expired = True

    def opening(path, *args, **kwargs):
        nonlocal binding_fd
        fd = original["open"](path, *args, **kwargs)
        opened.append(fd)
        if binding_phase and path == Path(program).name and "dir_fd" in kwargs:
            binding_fd = fd
            finish("open")
        return fd

    def closing(fd):
        closed.append(fd)
        return original["close"](fd)

    def fstat(fd):
        nonlocal fstat_count
        result = original["fstat"](fd)
        if fd == binding_fd:
            fstat_count += 1
            finish("first_fstat" if fstat_count == 1 else "last_fstat")
        return result

    def getxattr(fd, *args, **kwargs):
        if fd != binding_fd:
            return original["getxattr"](fd, *args, **kwargs)
        if late_at == "getxattr_return":
            finish("getxattr")
            return b"late capability observation"
        if late_at == "getxattr_enotsup":
            finish("getxattr")
            raise OSError(errno.ENOTSUP, "test unsupported capability observation")
        try:
            return original["getxattr"](fd, *args, **kwargs)
        except OSError as error:
            # Exercise the real clean system ELF's absence result.
            assert error.errno == errno.ENODATA
            raise
        finally:
            finish("getxattr")

    def pread(fd, *args):
        result = original["pread"](fd, *args)
        if fd == binding_fd:
            finish("pread")
        return result

    def stat(path, *args, **kwargs):
        result = original["stat"](path, *args, **kwargs)
        if binding_phase and path == Path(program).name and "dir_fd" in kwargs:
            finish("stat")
        return result

    def popen(*args, **kwargs):
        spawned.append((args, kwargs))
        pytest.fail("A late executable-binding operation must not launch a child")

    # Actual stable reads and held-directory checks precede the injected late
    # operation. Neither the interpreter nor any field object is modified.
    monkeypatch.setattr(bound, "_effect_guard", guard)
    monkeypatch.setattr(bound, "stable_read", validated_read)
    monkeypatch.setattr(d.os, "open", opening)
    monkeypatch.setattr(d.os, "close", closing)
    monkeypatch.setattr(d.os, "fstat", fstat)
    monkeypatch.setattr(d.os, "getxattr", getxattr)
    monkeypatch.setattr(d.os, "pread", pread)
    monkeypatch.setattr(d.os, "stat", stat)
    monkeypatch.setattr(d.subprocess, "Popen", popen)
    with pytest.raises(d.DispatchError, match="TEST_BINDING_DEADLINE"):
        bound._installation_command([program, "-I", "-B", "-c", "pass"])

    target = "getxattr" if late_at.startswith("getxattr_") else late_at
    order = ["open", "first_fstat", "getxattr", "pread", "last_fstat", "stat"]
    assert events == order[:order.index(target) + 1]
    assert spawned == [] and bound._install_commands == []
    assert binding_fd is not None and sorted(opened) == sorted(closed)
    for fd in set(opened):
        with pytest.raises(OSError) as failure:
            original["fstat"](fd)
        assert failure.value.errno == errno.EBADF
