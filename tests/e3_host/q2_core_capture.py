"""Live-only six-file persistence for approved amendment A 0bdb49c.

This is a local component, not a carrier entry or a restart verifier. The caller
must already have qualified the held management anchor and frozen binding within
the original window. No file is adopted, overwritten, removed or reopened for
writing. Failure permanently poisons this instance, retaining all created bytes.
Allocation accounting observes owned files, not the whole filesystem's peak.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import time

_spec = importlib.util.spec_from_file_location(
    "_core_capture_contract", Path(__file__).with_name("q2_core_delivery_contract.py"))
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)


WINDOW_NS = 1800000000000
STREAM_LIMIT = 109051904
ALLOCATION_LIMIT = 134217728
ROLE_LIMITS = {"marker": 32768, "stdout": STREAM_LIMIT, "stderr": 8388608,
               "remote_result": 524288, "capture_manifest": 524288,
               "local_receipt": 131072}
BASENAMES = {"marker": c.MARKER_BASENAME,
             **{key.removesuffix("_basename"): name for key, name in c.OUTPUT_BASENAMES.items()}}
ACCOUNTING_MODE = "APPLICATION_LIMIT_AND_OBSERVED_FILE_ALLOCATION"


class CaptureError(RuntimeError):
    """A fixed, non-private reason; no exception authorizes a retry."""


def _require(condition, reason):
    if not condition:
        raise CaptureError("CORE_CAPTURE_" + reason)


def _integer(value):
    return type(value) is int and 0 <= value < 2**63


class Deadline:
    """Strict original dual-clock window; every observation is BOOTTIME first."""

    def __init__(self, origins, clock_gettime_ns=time.clock_gettime_ns):
        names = {"host_" + clock + "_" + point + "_ns"
                 for clock in ("boottime", "monotonic") for point in ("origin", "deadline")}
        _require(type(origins) is dict and set(origins) == names, "CLOCK_FIELDS")
        _require(all(_integer(origins[key]) for key in names), "CLOCK_VALUE")
        for clock in ("boottime", "monotonic"):
            _require(origins[f"host_{clock}_deadline_ns"]
                     == origins[f"host_{clock}_origin_ns"] + WINDOW_NS, "CLOCK_WINDOW")
        _require(hasattr(time, "CLOCK_BOOTTIME"), "CLOCK_UNSUPPORTED")
        self.origins = dict(origins)
        self.clock = clock_gettime_ns
        self.previous = (origins["host_boottime_origin_ns"], origins["host_monotonic_origin_ns"])
        self.failed = False

    def check(self):
        _require(not self.failed, "CLOCK_STOPPED")
        try:
            now = (self.clock(time.CLOCK_BOOTTIME), self.clock(time.CLOCK_MONOTONIC))
            limits = (self.origins["host_boottime_deadline_ns"],
                      self.origins["host_monotonic_deadline_ns"])
            _require(all(_integer(value) and earlier <= value < limit
                         for earlier, value, limit in zip(self.previous, now, limits)), "DEADLINE")
            self.previous = now
        except BaseException:
            self.failed = True
            raise
        return now

    def call(self, function, *args, returned=None, **kwargs):
        self.check()
        try:
            value = function(*args, **kwargs)
            # Account positive writes / exclusive creation even on late return.
            if returned is not None:
                returned(value)
        except BaseException:
            self.check()
            raise
        self.check()
        return value


def _bounded_proc(path, limit, call):
    _require(hasattr(os, "O_NOATIME") and hasattr(os, "O_NOFOLLOW"), "READ_FLAGS")
    fd = call(os.open, path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NOATIME)
    raw = bytearray()
    try:
        while True:
            chunk = call(os.read, fd, min(4096, limit + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
            _require(len(raw) <= limit, "PROCESS_LIMIT")
        return bytes(raw)
    finally:
        # Do not start a late persistence/termination boundary, even on error.
        call(os.close, fd)


def observe_writer(call):
    """Read only this process' fixed proc views; no guest identity is substituted."""
    raw_status = _bounded_proc("/proc/self/status", 65_536, call)
    raw_stat = _bounded_proc("/proc/self/stat", 16_384, call)
    try:
        status = {}
        for line in raw_status.decode("ascii").splitlines():
            key, _, value = line.partition(":")
            if key in ("Uid", "Gid", "Groups"):
                _require(key not in status, "PROCESS_DUPLICATE")
                status[key] = [int(part) for part in value.split()]
        _require(set(status) == {"Uid", "Gid", "Groups"}
                 and len(status["Uid"]) == len(status["Gid"]) == 4
                 and all(_integer(v) for row in status.values() for v in row), "PROCESS_IDS")
        stat_text = raw_stat.decode("ascii")
        head, separator, tail = stat_text.rpartition(") ")
        pid_text, left, _ = head.partition(" (")
        fields = tail.split()
        _require(separator and left and len(fields) >= 20, "PROCESS_STAT")
        pid, start = int(pid_text), int(fields[19])
        _require(_integer(pid) and pid > 0 and _integer(start), "PROCESS_STAT")
    except (ValueError, UnicodeError) as error:
        raise CaptureError("CORE_CAPTURE_PROCESS_PARSE") from error
    namespaces = {}
    for role, name in (("user_namespace", "user"), ("pid_namespace", "pid")):
        # These two explicitly permitted proc namespace handles are magic links.
        fd = call(os.open, "/proc/self/ns/" + name, os.O_RDONLY | os.O_CLOEXEC)
        try:
            observed = call(os.fstat, fd)
            namespaces[role] = dict(dev=observed.st_dev, ino=observed.st_ino)
        finally:
            call(os.close, fd)
    keys = ("real", "effective", "saved", "filesystem")
    return dict(schema="local-hand-q2-core-local-writer/v1", **namespaces,
                process=dict(pid=pid, starttime_ticks=start),
                uid=dict(zip(keys, status["Uid"])), gid=dict(zip(keys, status["Gid"])),
                supplementary_gids=sorted(set(status["Groups"])))


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid, value.st_nlink)


def _stable(value):
    return (*_identity(value), value.st_size, value.st_blocks, value.st_mtime_ns, value.st_ctime_ns)


class LiveCapture:
    """One original caller, one marker, five outputs; no recovery constructor.

    ``writer_observer`` and clock injection are solely deterministic test seams.
    Production callers use the fixed observer and actual BOOTTIME/MONOTONIC.
    Held observation descriptors survive a poisoned instance for retained-failure
    diagnosis; descriptor closure is explicit and itself remains deadline-bound.
    """

    def __init__(self, directory_fd, *, anchor, writer, origins,
                 clock_gettime_ns=time.clock_gettime_ns, writer_observer=observe_writer):
        self.deadline = Deadline(origins, clock_gettime_ns)
        self.directory_fd = directory_fd
        self.anchor = dict(anchor)
        self.writer = c.document(c.canonical(writer), limit=65_536)
        self.observer = writer_observer
        self.objects = {}
        self.attempted = set()
        self.failed = False
        self.logical = 0
        self.max_allocated = 0
        self.allocated = 0
        self._descriptors = set()
        self._validate_binding()
        self._context()

    def _validate_binding(self):
        _require(set(self.anchor) == {"path", "dev", "ino", "mode", "uid", "gid", "nlink"}
                 and self.anchor["mode"] == 0o700, "ANCHOR_BINDING")
        c.absolute_path(self.anchor["path"], "CORE_CAPTURE_ANCHOR_PATH")
        _require(all(_integer(self.anchor[key]) for key in self.anchor if key != "path"),
                 "ANCHOR_BINDING")
        _require(set(self.writer) == {"schema", "user_namespace", "pid_namespace", "process",
                                     "uid", "gid", "supplementary_gids"}
                 and self.writer["schema"] == "local-hand-q2-core-local-writer/v1", "WRITER_BINDING")
        for key in ("uid", "gid"):
            _require(type(self.writer[key]) is dict
                     and set(self.writer[key]) == {"real", "effective", "saved", "filesystem"}
                     and all(type(v) is int and v == self.anchor[key]
                             for v in self.writer[key].values()), "WRITER_IDS")

    def _context(self):
        _require(not self.failed, "STOPPED")
        call = self.deadline.call
        before = call(os.fstat, self.directory_fd)
        named = call(os.stat, self.anchor["path"], follow_symlinks=False)
        after = call(os.fstat, self.directory_fd)
        expected = (self.anchor["dev"], self.anchor["ino"], stat.S_IFDIR | 0o700,
                    self.anchor["uid"], self.anchor["gid"], self.anchor["nlink"])
        _require(_identity(before) == _identity(named) == _identity(after) == expected,
                 "ANCHOR_CHANGED")
        observed = self.observer(call)
        _require(c.canonical(observed) == c.canonical(self.writer), "WRITER_CHANGED")
        self.deadline.check()

    def _io(self, function, *args, returned=None, **kwargs):
        self._context()
        value = self.deadline.call(function, *args, returned=returned, **kwargs)
        self._context()
        return value

    def _sample(self):
        self._context()
        total = 0
        for role, record in self.objects.items():
            fd = record["sample_fd"]
            first = self.deadline.call(os.fstat, fd)
            named = self.deadline.call(os.stat, BASENAMES[role], dir_fd=self.directory_fd,
                                       follow_symlinks=False)
            last = self.deadline.call(os.fstat, fd)
            _require(_stable(first) == _stable(named) == _stable(last)
                     and _identity(last) == record["identity"]
                     and last.st_size == record["written"] and _integer(last.st_blocks),
                     "FILE_CHANGED")
            total += last.st_blocks * 512
            record["allocated_bytes"] = last.st_blocks * 512
        self.max_allocated = max(self.max_allocated, total)
        self.allocated = total
        _require(total <= ALLOCATION_LIMIT and len(self.objects) <= 6, "OBSERVED_BUDGET")
        self._context()
        return total

    def _prewrite(self, role, amount):
        _require(_integer(amount), "WRITE_SIZE")
        current = self.objects.get(role, {}).get("written", 0)
        _require(current + amount <= ROLE_LIMITS[role], "ROLE_LIMIT")
        streams = sum(self.objects.get(key, {}).get("written", 0) for key in ("stdout", "stderr"))
        _require(streams + (amount if role in ("stdout", "stderr") else 0) <= STREAM_LIMIT,
                 "STREAM_LIMIT")
        _require(self.logical + amount <= ALLOCATION_LIMIT, "LOGICAL_LIMIT")
        self._sample()

    def _created(self, role, fd):
        # Mark consumption before any post-return operation can fail.
        self._descriptors.add(fd)
        self.objects[role] = dict(write_fd=fd, sample_fd=fd, written=0, complete=False)

    def create(self, role, raw):
        """Persist one whole, bounded object once, with positive short-write charging."""
        try:
            _require(not self.failed and role in ROLE_LIMITS and role not in self.attempted,
                     "CREATE_ONCE")
            _require(type(raw) is bytes and len(self.objects) < 6, "CREATE_INPUT")
            _require(role == "marker" or self.objects.get("marker", {}).get("complete") is True,
                     "MARKER_FIRST")
            self._prewrite(role, len(raw))
            self.attempted.add(role)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
            fd = self._io(os.open, BASENAMES[role], flags, 0o600, dir_fd=self.directory_fd,
                          returned=lambda value: self._created(role, value))
            record = self.objects[role]
            created = self.deadline.call(os.fstat, fd)
            _require(stat.S_ISREG(created.st_mode) and created.st_nlink == 1
                     and stat.S_IMODE(created.st_mode) == 0o600 and created.st_size == 0
                     and created.st_uid == self.anchor["uid"] and created.st_gid == self.anchor["gid"],
                     "CREATED_IDENTITY")
            record["identity"] = _identity(created)
            # Keep a held observation fd while the prescribed writer and reread
            # handles are closed. dup creates no additional filesystem object.
            sample_fd = self.deadline.call(os.dup, fd, returned=self._descriptors.add)
            record["sample_fd"] = sample_fd
            self._sample()
            while record["written"] < len(raw):
                chunk = raw[record["written"]:]
                self._prewrite(role, len(chunk))
                def charged(count):
                    _require(type(count) is int and 0 < count <= len(chunk), "SHORT_WRITE")
                    record["written"] += count
                    self.logical += count
                self._io(os.write, fd, chunk, returned=charged)
                self._sample()
            self._io(os.fsync, fd)
            self._sample()
            self.deadline.call(os.fstat, fd)
            self._io(os.close, fd, returned=lambda _: self._descriptors.discard(fd))
            reread_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC
            read_fd = self._io(os.open, BASENAMES[role], reread_flags, dir_fd=self.directory_fd,
                               returned=self._descriptors.add)
            before = self.deadline.call(os.fstat, read_fd)
            _require(_identity(before) == record["identity"] and before.st_size == len(raw),
                     "REREAD_IDENTITY")
            reread = bytearray()
            while True:
                chunk = self._io(os.read, read_fd, min(65_536, len(raw) + 1 - len(reread)))
                if not chunk:
                    break
                reread.extend(chunk)
                _require(len(reread) <= len(raw), "REREAD_LIMIT")
            after = self.deadline.call(os.fstat, read_fd)
            _require(bytes(reread) == raw and _stable(before) == _stable(after), "REREAD")
            self._io(os.close, read_fd, returned=lambda _: self._descriptors.discard(read_fd))
            self._io(os.fsync, self.directory_fd)
            self._sample()
            self.deadline.check()
            record["complete"] = True
            record["sha256"] = hashlib.sha256(raw).hexdigest()
            return dict(basename=BASENAMES[role], bytes=record["written"],
                        allocated_bytes=record["allocated_bytes"], sha256=record["sha256"],
                        dev=created.st_dev, ino=created.st_ino, mode=0o600, nlink=1)
        except BaseException:
            self.failed = True
            raise

    def finish(self):
        """Only this original live instance can finish; disk text is not consulted."""
        try:
            _require(not self.failed and self.objects.get("local_receipt", {}).get("complete") is True,
                     "LIVE_RECEIPT")
            self._sample()
            self.deadline.check()
            return dict(mode=ACCOUNTING_MODE, logical_bytes_written=self.logical,
                        created_inodes=len(self.objects), max_observed_allocated_bytes=self.max_allocated,
                        full_filesystem_peak_proven=False)
        except BaseException:
            self.failed = True
            raise

    def sample(self):
        """Public checked observation; a failed sample cannot be retried."""
        try:
            return self._sample()
        except BaseException:
            self.failed = True
            raise

    def close_handles(self):
        """Close only owned descriptors, never persisted files, and never after expiry."""
        for fd in tuple(self._descriptors):
            self.deadline.call(os.close, fd, returned=lambda _, fd=fd: self._descriptors.discard(fd))
