"""Observe Linux mount aliases before writing an archive read's output.

This protects the consumer's complete store, including directories outside its
Ledger database. It assumes the archive's existing trusted-user, cooperative
writer profile and stable mounts during access, not hostile mount replacement.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat

from .evidence import _close_descriptors


MAX_MOUNTINFO = 1024 * 1024
MAX_FDINFO = 4096


def _fail(message, code="IO_UNCERTAIN"):
    from .artifact_archive import ArchiveError
    raise ArchiveError(code, message)


def _read_proc(path, limit):
    # proc files report size zero; bound the read itself, not st_size.
    with open(path, "rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        _fail("Archive output mount observation exceeds its limit")
    return os.fsdecode(raw)


def _mounts():
    records = {}
    for line in _read_proc("/proc/self/mountinfo", MAX_MOUNTINFO).split("\n"):
        if not line:
            continue
        # Only ASCII space/LF are delimiters. Other Unicode whitespace is a
        # legitimate part of a Linux filename.
        fields = line.split(" ")
        if (len(fields) < 10 or "-" not in fields[6:]
                or re.fullmatch(r"[0-9]{1,20}", fields[0]) is None
                or re.fullmatch(r"[0-9]{1,20}:[0-9]{1,20}", fields[2]) is None):
            _fail("Archive output mount observation is malformed")
        mount_id = int(fields[0])
        if mount_id in records:
            _fail("Archive output mount observation is ambiguous")
        def unescape(value):
            return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)
        root, point = Path(unescape(fields[3])), Path(unescape(fields[4]))
        if not point.is_absolute() or ".." in root.parts or ".." in point.parts:
            _fail("Archive output mount observation is malformed")
        records[mount_id] = dict(device=tuple(map(int, fields[2].split(":"))),
                                 root=root, point=point)
    if not records:
        _fail("Archive output mount observation is empty")
    return records


def _mount_id(fd):
    values = [line.removeprefix("mnt_id:").strip(" \t")
              for line in _read_proc(f"/proc/self/fdinfo/{fd}", MAX_FDINFO).split("\n")
              if line.startswith("mnt_id:")]
    if len(values) != 1 or re.fullmatch(r"[0-9]+", values[0]) is None:
        _fail("Archive output descriptor mount identity is unavailable")
    return int(values[0])


def _projected_identity(source_fd, relative_parts):
    """Inspect a visible view from the admitted source FD without write rules."""
    directory = os.dup(source_fd)
    failure = None
    try:
        for component in relative_parts:
            try:
                nxt = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=directory)
            except FileNotFoundError:
                # A higher mount can hide a lower view, including its children.
                return None
            except NotADirectoryError:
                # O_NOFOLLOW | O_DIRECTORY can return ENOTDIR for both a file
                # and a symlink. Only a confirmed ordinary file proves that
                # this hidden projection cannot expose the output directory.
                info = os.stat(component, dir_fd=directory, follow_symlinks=False)
                if stat.S_ISREG(info.st_mode):
                    return None
                raise
            previous, directory = directory, nxt
            _close_descriptors(previous)
        info = os.fstat(directory)
        return info.st_dev, info.st_ino
    except BaseException as error:
        failure = error
        raise
    finally:
        _close_descriptors(directory, failure=failure)


def assert_output_outside_store(source: Path, source_fd: int, parent: Path, parent_fd: int):
    """Reject visible bind aliases into any part of the input archive."""
    # Linux treats // as /; pathlib deliberately preserves the POSIX spelling.
    # Normalize only that anchor, after the caller's no-follow descriptor walk.
    source, parent = (Path("/", *path.parts[1:]) if path.anchor == "//" else path
                      for path in (source, parent))
    try:
        records = _mounts()
        bindings = []
        for path, fd in ((source, source_fd), (parent, parent_fd)):
            info = os.fstat(fd)
            mount_id = _mount_id(fd)
            mount = records.get(mount_id)
            if (mount is None or not mount["root"].is_absolute()
                    or mount["device"] != (os.major(info.st_dev), os.minor(info.st_dev))
                    or not path.is_relative_to(mount["point"])):
                _fail("Archive output mount binding could not be confirmed")
            bindings.append((info, mount, mount_id))
        source_info, _, _ = bindings[0]
        parent_info, parent_mount, _ = bindings[1]
        identity = parent_info.st_dev, parent_info.st_ino
        if parent.is_relative_to(source) or identity == (source_info.st_dev, source_info.st_ino):
            _fail("Read output must be outside the archive store", "INVALID_INPUT")
        position = parent_mount["root"] / parent.relative_to(parent_mount["point"])
        for mount in records.values():
            if (mount["device"] != parent_mount["device"] or not mount["root"].is_absolute()
                    or not position.is_relative_to(mount["root"])):
                continue
            projected = mount["point"] / position.relative_to(mount["root"])
            if projected.is_relative_to(source):
                visible = _projected_identity(source_fd, projected.relative_to(source).parts)
                if visible == identity:
                    _fail("Read output must be outside the archive store", "INVALID_INPUT")
        for fd, (_, _, mount_id) in zip((source_fd, parent_fd), bindings):
            if _mount_id(fd) != mount_id:
                _fail("Archive output mount binding changed during observation")
    except OSError as error:
        from .artifact_archive import ArchiveError
        raise ArchiveError("IO_UNCERTAIN", "Archive output separation could not be observed") from error
