"""Bounded, create-only Q2 transport primitives; no host values or SSH defaults.

The original management session owns the outer process and its own exit/EOF.
Successful SSH capture is transport evidence, never proof of remote tree stop.
An interrupted transfer retains its intent and cannot be replayed into a new
name by this module. This file stays outside the installed product wheel.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import selectors
import signal
import socket
import stat
import subprocess
import tarfile
import time

CEILING = 256 * 1024 * 1024
SCHEMA = "local-hand-q2-delivery/v1"


def require(ok, code):
    if not ok:
        raise ValueError(code)


def integer(value, minimum=0, maximum=CEILING):
    require(type(value) is int and minimum <= value <= maximum, "DELIVERY_INTEGER")


def canonical(path):
    path = str(path)
    require(path.startswith("/") and not path.startswith("//") and str(Path(path)) == path
            and ".." not in Path(path).parts and path != "/", "DELIVERY_PATH")
    return Path(path)


def protected_parent(path):
    path = canonical(path)
    for item in reversed(path.parents):
        info = item.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
                "DELIVERY_PARENT")
    return path


def new_file(path, mode=0o600):
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)


def write(path, raw, mode=0o600):
    fd = new_file(path, mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw); stream.flush(); os.fsync(fd)
    finally:
        os.close(fd)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def raw_json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def archive_members(raw, expected_sha256, *, maximum_bytes, maximum_entries=8192):
    """Verify the whole pinned tar before creating any destination object."""
    integer(maximum_bytes, 4096); integer(maximum_entries, 1, 8192)
    require(type(raw) is bytes and len(raw) <= maximum_bytes
            and hashlib.sha256(raw).hexdigest() == expected_sha256, "DELIVERY_ARCHIVE_DIGEST")
    if raw[:2] == b"\x1f\x8b":
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            decoded = stream.read(maximum_bytes + 1)
        require(len(decoded) <= maximum_bytes, "DELIVERY_DECOMPRESSION_LIMIT")
    else:
        decoded = raw
    require(len(decoded) <= maximum_bytes, "DELIVERY_ARCHIVE_LIMIT")
    members = []; names = set(); staging_bytes = 4096
    with tarfile.open(fileobj=io.BytesIO(decoded), mode="r:") as archive:
        for member in archive:
            name = member.name; relative = PurePosixPath(name)
            require(type(name) is str and 0 < len(name) <= 1024 and bool(relative.parts) and not relative.is_absolute()
                    and relative.as_posix() == name and not any(p in (".", "..") for p in relative.parts)
                    and name not in names and "\\" not in name and "\0" not in name,
                    "DELIVERY_ARCHIVE_PATH")
            require(member.isfile() or member.isdir(), "DELIVERY_ARCHIVE_TYPE")
            require(not member.mode & 0o7022 and member.size >= 0
                    and member.size <= maximum_bytes and not member.pax_headers,
                    "DELIVERY_ARCHIVE_MODE")
            require(relative.parts[-4:] != (".git", "objects", "info", "alternates")
                    and relative.parts[-4:] != (".git", "objects", "info", "http-alternates"),
                    "DELIVERY_GIT_ALTERNATES")
            names.add(name); require(len(names) <= maximum_entries, "DELIVERY_ARCHIVE_COUNT")
            if member.isdir():
                require(member.size == 0, "DELIVERY_ARCHIVE_DIRECTORY")
                data = None; staging_bytes += 4096
            else:
                staging_bytes += max(4096, (member.size + 4095) // 4096 * 4096)
                require(staging_bytes <= maximum_bytes, "DELIVERY_STAGING_LIMIT")
                stream = archive.extractfile(member)
                require(stream is not None, "DELIVERY_ARCHIVE_FILE")
                with stream:
                    data = stream.read(member.size + 1)
                require(len(data) == member.size, "DELIVERY_ARCHIVE_FILE")
            require(staging_bytes <= maximum_bytes, "DELIVERY_STAGING_LIMIT")
            members.append({"name": name, "kind": "directory" if member.isdir() else "file",
                            "mode": 0o755 if member.isdir() or member.mode & 0o111 else 0o644,
                            "data": data})
    require(members, "DELIVERY_ARCHIVE_EMPTY")
    kinds = {m["name"]: m["kind"] for m in members}
    for name in names:
        # Explicit parent entries avoid implicit, uncharged directories.
        require(all(str(parent) == "." or kinds.get(str(parent)) == "directory"
                    for parent in PurePosixPath(name).parents), "DELIVERY_ARCHIVE_PARENT")
    return {"members": members, "staging_bytes": staging_bytes, "entries": len(members),
            "sha256": expected_sha256}


def original_deadline(issued_ns, deadline_ns):
    integer(issued_ns, 1, 2**63-1); integer(deadline_ns, issued_ns+1, 2**63-1)
    require(issued_ns <= time.monotonic_ns() < deadline_ns, "DELIVERY_DEADLINE")


def verify_guest(expected):
    require(type(expected) is dict and set(expected) == {"hostname", "boot_id", "initial_userns"}, "DELIVERY_GUEST_FIELDS")
    info = os.stat("/proc/1/ns/user"); own = os.stat("/proc/self/ns/user")
    current = {"hostname": socket.gethostname(), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
               "initial_userns": {"device": info.st_dev, "inode": info.st_ino}}
    require(os.getuid() == os.geteuid() == 0 and current == expected
            and (own.st_dev, own.st_ino) == (info.st_dev, info.st_ino), "DELIVERY_GUEST_IDENTITY")
    return current


def reserve_and_extract(raw, expected_sha256, *, destination, reservation_path, guest_pin,
                        installation_reservation_bytes, retained_delivery_bytes, ceiling_bytes,
                        issued_ns, deadline_ns):
    """Guest-side transfer stage; original finite envelope precedes its intent."""
    original_deadline(issued_ns, deadline_ns)
    integer(ceiling_bytes, 4096); integer(installation_reservation_bytes, 4096)
    integer(retained_delivery_bytes, 0)
    guest = verify_guest(guest_pin)
    destination = protected_parent(destination); reservation = protected_parent(reservation_path)
    require(destination != reservation and destination not in reservation.parents
            and reservation not in destination.parents, "DELIVERY_PATH_ALIAS")
    require(not os.path.lexists(destination) and not os.path.lexists(reservation), "DELIVERY_ALREADY_RESERVED")
    available = ceiling_bytes - installation_reservation_bytes - retained_delivery_bytes - 8192
    require(available >= 4096, "DELIVERY_TOTAL_BUDGET")
    checked = archive_members(raw, expected_sha256, maximum_bytes=available)
    charged = checked["staging_bytes"] + installation_reservation_bytes + retained_delivery_bytes + 8192
    require(charged <= ceiling_bytes, "DELIVERY_TOTAL_BUDGET")
    require(available >= len(raw), "DELIVERY_ARCHIVE_BUDGET")
    storage = os.statvfs(destination.parent)
    require(storage.f_bavail * storage.f_frsize >= checked["staging_bytes"] + 8192
            and storage.f_favail >= checked["entries"] + 3, "DELIVERY_STORAGE")
    original_deadline(issued_ns, deadline_ns)
    intent = {"schema": SCHEMA, "status": "RESERVED", "guest": guest, "archive_sha256": expected_sha256,
              "destination": str(destination), "issued_ns": issued_ns, "deadline_ns": deadline_ns,
              "staging_bytes": checked["staging_bytes"], "installation_reservation_bytes": installation_reservation_bytes,
              "retained_delivery_bytes": retained_delivery_bytes, "ceiling_bytes": ceiling_bytes,
              "fixture_provisioned": False, "q2_accepted": False}
    write(reservation, raw_json(intent)); sync_dir(reservation.parent)
    # Any subsequent exception intentionally retains both intent and partial tree.
    destination.mkdir(mode=0o755); destination.chmod(0o755)
    for member in sorted(checked["members"], key=lambda m: (len(PurePosixPath(m["name"]).parts), m["name"])):
        original_deadline(issued_ns, deadline_ns)
        target = destination / member["name"]
        if member["kind"] == "directory":
            target.mkdir(mode=0o755); target.chmod(0o755)
        else:
            write(target, member["data"], member["mode"])
    for member in sorted(checked["members"], key=lambda m: -len(PurePosixPath(m["name"]).parts)):
        if member["kind"] == "directory":
            sync_dir(destination / member["name"])
    sync_dir(destination); sync_dir(destination.parent)
    original_deadline(issued_ns, deadline_ns)
    require(verify_guest(guest_pin) == guest, "DELIVERY_GUEST_CHANGED")
    return {**intent, "status": "EXTRACTED", "entries": checked["entries"]}


def capture(argv, *, issued_ns, deadline_ns, output_limit, stdout_path, stderr_path, stdin_path=None):
    """Host-side capture for exactly one SSH call, preserving its original clock.

    stdin is a finished regular file, never a producer pipe. Capture never retries
    the command or treats terminating an SSH client as stopping its remote tree.
    A collector failure returns INCOMPLETE even when a later client kill exits.
    """
    original_deadline(issued_ns, deadline_ns)
    integer(output_limit, 1024, 16 * 1024 * 1024)
    require(type(argv) in (list, tuple) and 0 < len(argv) <= 64
            and all(type(s) is str and len(s) <= 65536 and "\0" not in s for s in argv), "DELIVERY_COMMAND")
    paths = [canonical(stdout_path), canonical(stderr_path)]
    require(paths[0] != paths[1] and not any(os.path.lexists(p) for p in paths), "DELIVERY_CAPTURE_EXISTS")
    incoming = None; input_identity = None; files = {}; proc = None; selector = selectors.DefaultSelector()
    eof = set(); total = 0; failure = None; started = None
    stop_reserve_ns = min(10**9, (deadline_ns-issued_ns)//5)
    try:
        if stdin_path is not None:
            input_path = canonical(stdin_path)
            require(input_path not in paths, "DELIVERY_CAPTURE_ALIAS")
            fd = os.open(input_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
            incoming = os.fdopen(fd, "rb")
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= CEILING,
                    "DELIVERY_STDIN_FILE")
            input_identity = tuple(getattr(info, key) for key in
                                   ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink"))
        for name, path in zip(("stdout", "stderr"), paths):
            files[name] = os.fdopen(new_file(path), "wb")
        original_deadline(issued_ns, deadline_ns)
        proc = subprocess.Popen(argv, stdin=incoming if incoming else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, start_new_session=True)
        started = time.monotonic_ns()
        for name in files:
            stream = getattr(proc, name); os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while len(eof) != 2 or proc.poll() is None:
            remaining = deadline_ns - time.monotonic_ns()
            if remaining <= stop_reserve_ns:
                failure = "DELIVERY_CAPTURE_TIMEOUT"; break
            for key, _ in selector.select(min(0.05, remaining / 1e9)):
                block = os.read(key.fd, 65536)
                if not block:
                    eof.add(key.data); selector.unregister(key.fileobj); continue
                room = max(0, output_limit - total); kept = block[:room]
                files[key.data].write(kept); total += len(kept)
                if len(block) > room:
                    failure = "DELIVERY_CAPTURE_LIMIT"; break
            if failure:
                break
    except BaseException as error:
        failure = type(error).__name__
    finally:
        if proc is not None:
            # A fork can keep a stream open after the original client has exited.
            # On incomplete capture stop the original group regardless of poll().
            if failure or proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            try:
                proc.wait(timeout=min(1, max(0, (deadline_ns-time.monotonic_ns())/1e9)))
            except subprocess.TimeoutExpired:
                failure = failure or "DELIVERY_CLIENT_EXIT_UNPROVEN"
            for name in ("stdout", "stderr"):
                stream = getattr(proc, name)
                if stream is not None:
                    stream.close()
        selector.close()
        if incoming is not None:
            info = os.fstat(incoming.fileno())
            if input_identity is not None and input_identity != tuple(getattr(info, key) for key in
                    ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")):
                failure = failure or "DELIVERY_STDIN_CHANGED"
            incoming.close()
        for stream in files.values():
            try:
                stream.flush(); os.fsync(stream.fileno())
            except OSError:
                failure = failure or "DELIVERY_CAPTURE_DURABILITY"
            finally:
                stream.close()
        for parent in {p.parent for p in paths}:
            try:
                sync_dir(parent)
            except OSError:
                failure = failure or "DELIVERY_CAPTURE_DURABILITY"
    finished_ns = time.monotonic_ns()
    within = finished_ns <= deadline_ns
    complete = proc is not None and proc.returncode == 0 and eof == {"stdout", "stderr"} and failure is None and within
    return {"schema": SCHEMA, "status": "CAPTURED" if complete else "INCOMPLETE", "complete": complete,
            "issued_ns": issued_ns, "deadline_ns": deadline_ns, "started_ns": started,
            "returncode": proc.returncode if proc is not None else None, "eof": sorted(eof), "error": failure,
            "captured_bytes": total, "finished_ns": finished_ns, "within_original_deadline": within,
            "remote_stop_proven": False, "q2_accepted": False}


def main():
    print(json.dumps({"schema": SCHEMA, "status": "BLOCKED", "reason": "ORIGINAL_DELIVERY_REQUIRED"}))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
