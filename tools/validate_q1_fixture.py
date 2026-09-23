#!/usr/bin/env python3
"""Read two explicit Q1 snapshots and report offline configuration consistency.

Run with ``python -I -B`` from a trusted source checkout. This command performs
no host admission, quota observation, installation, or journal operation. Its
snapshot reads are byte-bounded, but do not promise a wall-time bound for storage
I/O. Snapshot paths may be relative; no component may be a symbolic link.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys


SCHEMA = "local-hand-quota-q1-offline-validation/v1"
MAX_MANIFEST_BYTES = 32768
MAX_RUNTIME_BYTES = 16384


class SnapshotError(ValueError):
    """A fixed code, never snapshot bytes, paths, or OS exception text."""


def _failure(status, code):
    return {
        "schema": SCHEMA, "status": status, "code": code,
        "evidence_class": "OFFLINE_ONLY", "host_readiness": "NOT_VERIFIED",
        "admission_proven": False, "real_e3_accepted": False,
        "production_supported": False,
    }


def _emit(value):
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _identity(metadata):
    # Reads may change atime. Every other relevant inode/content field is fixed.
    return tuple(getattr(metadata, name) for name in (
        "st_dev", "st_ino", "st_uid", "st_gid", "st_mode", "st_nlink",
        "st_size", "st_mtime_ns", "st_ctime_ns"))


def _open_snapshot(filename):
    """Open an explicit snapshot without following leaf or ancestor symlinks."""
    parts = PurePosixPath(filename).parts
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    current = os.open("/" if filename.startswith("/") else ".", flags | os.O_DIRECTORY)
    if parts and parts[0] == "/":
        parts = parts[1:]
    try:
        for index, part in enumerate(parts):
            child = os.open(part, flags | (os.O_DIRECTORY if index < len(parts) - 1 else 0),
                            dir_fd=current)
            old, current = current, child
            os.close(old)
        result, current = current, -1
        return result
    finally:
        if current >= 0:
            os.close(current)


def read_snapshot(filename, maximum):
    """Check regular-file type before reading at most maximum plus one bytes."""
    descriptor = _open_snapshot(filename)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SnapshotError("SNAPSHOT_NOT_REGULAR")
        if not 0 <= before.st_size <= maximum:
            raise SnapshotError("SNAPSHOT_BYTE_LIMIT")
        raw = bytearray()
        while len(raw) <= maximum:
            block = os.read(descriptor, maximum + 1 - len(raw))
            if not block:
                break
            raw.extend(block)
        if len(raw) > maximum:
            raise SnapshotError("SNAPSHOT_BYTE_LIMIT")
        if _identity(before) != _identity(os.fstat(descriptor)):
            raise SnapshotError("SNAPSHOT_CHANGED")
        return bytes(raw)
    finally:
        os.close(descriptor)


def main(argv=None):
    # Check before any repository import: even validation must not create caches
    # or admit ambient PYTHONPATH/user-site modules.
    if not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        _emit(_failure("REJECTED", "ISOLATED_PYTHON_REQUIRED"))
        return 2
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--manifest-snapshot", required=True, metavar="FILE")
    parser.add_argument("--manifest-sha256", required=True, metavar="SHA256")
    parser.add_argument("--runtime-snapshot", required=True, metavar="FILE")
    parser.add_argument("--runtime-sha256", required=True, metavar="SHA256")
    parser.add_argument("--source-commit", required=True, metavar="FULL40")
    parser.add_argument("--runtime-path", required=True, metavar="INSTALLED_ABSPATH")
    parser.add_argument("--journal-path", required=True, metavar="ABSPATH")
    args = parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        _emit(_failure("UNSUPPORTED", "LINUX_REQUIRED"))
        return 3

    # This is a trusted-source utility; the declared installation paths below
    # are passed as data and are never searched for or imported.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from admin.local_hand_quota_observer.admission import Rejected
    from admin.local_hand_quota_observer.fixture_inputs import validate_fixture_inputs

    try:
        manifest = read_snapshot(args.manifest_snapshot, MAX_MANIFEST_BYTES)
        runtime = read_snapshot(args.runtime_snapshot, MAX_RUNTIME_BYTES)
        result = validate_fixture_inputs(
            manifest, runtime, manifest_digest=args.manifest_sha256,
            runtime_digest=args.runtime_sha256, expected_source_commit=args.source_commit,
            runtime_path=args.runtime_path, journal_path=args.journal_path)
    except SnapshotError as error:
        _emit(_failure("REJECTED", str(error)))
        return 2
    except Rejected as error:
        code = str(error)
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code) is None:
            code = "CONFIG_REJECTED"
        _emit(_failure("REJECTED", code))
        return 2
    except (OSError, ValueError):
        _emit(_failure("REJECTED", "SNAPSHOT_IO"))
        return 2
    _emit(result.as_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
