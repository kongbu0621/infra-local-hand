"""Two qualified procfs reads approved by LH-Q2-KERNEL-FACT-READ-v1.

This is not an evidence-file reader or a generic /proc API. It never retries with
weaker flags, changes privileges, enters namespaces, or creates a host file.
The original-host terminal's PID/proc alignment remains an explicit assumption.
"""
from __future__ import annotations

import ctypes as ct
import hashlib
import os
import platform
import stat
import sys


PROC_SUPER_MAGIC = 0x9FA0
STATX_BASIC_STATS = 0x7FF
STATX_MNT_ID = 0x1000
AT_EMPTY_PATH = 0x1000
AT_SYMLINK_NOFOLLOW = 0x100
_STABLE = ("device", "inode", "mode", "uid", "gid", "nlink")


class KernelFactError(ValueError):
    def __init__(self, reason, operation, target, *, errno=None):
        super().__init__(reason)
        self.reason, self.operation, self.target, self.errno = reason, operation, target, errno
        self.detail = dict(reason=reason, operation=operation, target=target, errno=errno)


def _require(condition, reason, operation, target):
    if not condition:
        raise KernelFactError(reason, operation, target)


class _Statfs(ct.Structure):
    _fields_ = [("type", ct.c_long), ("bsize", ct.c_long),
        ("blocks", ct.c_ulong), ("bfree", ct.c_ulong), ("bavail", ct.c_ulong),
        ("files", ct.c_ulong), ("ffree", ct.c_ulong), ("fsid", ct.c_int * 2),
        ("namelen", ct.c_long), ("frsize", ct.c_long), ("flags", ct.c_long),
        ("spare", ct.c_long * 4)]


class _Timestamp(ct.Structure):
    _fields_ = [("sec", ct.c_int64), ("nsec", ct.c_uint32), ("reserved", ct.c_int32)]


class _Statx(ct.Structure):
    _fields_ = [("mask", ct.c_uint32), ("blksize", ct.c_uint32),
        ("attributes", ct.c_uint64), ("nlink", ct.c_uint32), ("uid", ct.c_uint32),
        ("gid", ct.c_uint32), ("mode", ct.c_uint16), ("spare0", ct.c_uint16),
        ("ino", ct.c_uint64), ("size", ct.c_uint64), ("blocks", ct.c_uint64),
        ("attributes_mask", ct.c_uint64), ("atime", _Timestamp), ("btime", _Timestamp),
        ("ctime", _Timestamp), ("mtime", _Timestamp), ("rdev_major", ct.c_uint32),
        ("rdev_minor", ct.c_uint32), ("dev_major", ct.c_uint32),
        ("dev_minor", ct.c_uint32), ("mnt_id", ct.c_uint64), ("spare", ct.c_uint64 * 13)]


def _layout_supported():
    expected_fs = dict(type=0, bsize=8, blocks=16, bfree=24, bavail=32,
        files=40, ffree=48, fsid=56, namelen=64, frsize=72, flags=80, spare=88)
    expected_sx = dict(mask=0, blksize=4, attributes=8, nlink=16, uid=20, gid=24,
        mode=28, spare0=30, ino=32, size=40, blocks=48, attributes_mask=56,
        atime=64, btime=80, ctime=96, mtime=112, rdev_major=128, rdev_minor=132,
        dev_major=136, dev_minor=140, mnt_id=144, spare=152)
    return (sys.platform == "linux" and platform.machine() == "x86_64"
        and sys.byteorder == "little" and ct.sizeof(ct.c_void_p) == 8
        and ct.sizeof(ct.c_long) == 8 and ct.sizeof(ct.c_int) == 4
        and ct.sizeof(_Statfs) == 120 and ct.alignment(_Statfs) == 8
        and ct.sizeof(_Statx) == 256 and ct.alignment(_Statx) == 8
        and ct.sizeof(_Timestamp) == 16 and _Timestamp.nsec.offset == 8
        and all(getattr(_Statfs, name).offset == offset for name, offset in expected_fs.items())
        and all(getattr(_Statx, name).offset == offset for name, offset in expected_sx.items()))


def _load_abi(target):
    _require(_layout_supported() and all(hasattr(os, name) for name in
        ("O_PATH", "O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC", "O_NONBLOCK")),
        "HOST_LOCAL_KERNEL_ABI_UNSUPPORTED", "abi_layout", target)
    try:
        library = ct.CDLL(None, use_errno=True)
        fs, sx = library.fstatfs, library.statx
    except (AttributeError, OSError) as error:
        raise KernelFactError("HOST_LOCAL_KERNEL_ABI_UNSUPPORTED", "abi_symbols", target,
            errno=getattr(error, "errno", None)) from error
    fs.argtypes, fs.restype = [ct.c_int, ct.POINTER(_Statfs)], ct.c_int
    sx.argtypes, sx.restype = [ct.c_int, ct.c_char_p, ct.c_int, ct.c_uint, ct.POINTER(_Statx)], ct.c_int
    return fs, sx


def _metadata(info):
    return dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode,
        uid=info.st_uid, gid=info.st_gid, nlink=info.st_nlink, size=info.st_size,
        blocks=info.st_blocks, atime_ns=info.st_atime_ns,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns)


def _same(left, right):
    return all(left[key] == right[key] for key in _STABLE)


class _Reader:
    def __init__(self, kind, guard, report):
        self.kind, self.guard, self.report = kind, guard, report
        self.operation, self.target = "select_target", kind
        self.held, self.open_fds = [], []
        self.proc_identity = None
        self.abi = None
        self.allowed_uids = None

    def check(self, operation, target):
        self.operation, self.target = "deadline_guard", target
        self.guard()
        self.operation = operation

    def call(self, operation, target, function, *args, **kwargs):
        self.check(operation, target)
        try:
            return function(*args, **kwargs)
        except OSError as error:
            raise KernelFactError("HOST_LOCAL_KERNEL_SYSCALL", operation, target,
                errno=error.errno) from error

    def opened(self, name, flags, label, *, parent=None):
        kwargs = {} if parent is None else dict(dir_fd=parent)
        fd = self.call("open_path" if flags & os.O_PATH else "open_read", label,
            os.open, name, flags, **kwargs)
        self.open_fds.append(fd)
        return fd

    def close_one(self, fd, label):
        # Never retry close: an interrupted close may already have released fd.
        self.open_fds.remove(fd)
        try:
            os.close(fd)
        except OSError as error:
            raise KernelFactError("HOST_LOCAL_KERNEL_SYSCALL", "close", label,
                errno=error.errno) from error

    def snapshot(self, fd, label, directory):
        info = self.call("fstat", label, os.fstat, fd)
        value = _metadata(info)
        self.report["last_metadata_observation"] = dict(target=label, **value)
        _require(info.st_uid in self.allowed_uids and not info.st_mode & 0o6022,
            "HOST_LOCAL_KERNEL_UNPROTECTED", "protect", label)
        _require(stat.S_ISDIR(info.st_mode) if directory else
            stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
            "HOST_LOCAL_KERNEL_OBJECT_TYPE", "protect", label)
        fs, sx = _Statfs(), _Statx()
        self.check("fstatfs", label)
        ct.set_errno(0)
        if self.abi[0](fd, ct.byref(fs)) != 0:
            raise KernelFactError("HOST_LOCAL_KERNEL_SYSCALL", "fstatfs", label, errno=ct.get_errno())
        self.check("statx", label)
        ct.set_errno(0)
        if self.abi[1](fd, b"", AT_EMPTY_PATH | AT_SYMLINK_NOFOLLOW,
                STATX_BASIC_STATS | STATX_MNT_ID, ct.byref(sx)) != 0:
            raise KernelFactError("HOST_LOCAL_KERNEL_SYSCALL", "statx", label, errno=ct.get_errno())
        _require(sx.mask & (STATX_BASIC_STATS | STATX_MNT_ID) == STATX_BASIC_STATS | STATX_MNT_ID,
            "HOST_LOCAL_KERNEL_STATX_MASK", "statx_mask", label)
        # Python's native fstat/fstatvfs implementations independently interpret
        # libc/kernel layouts. Cross-check stable identity and filesystem units.
        _require((sx.ino, sx.mode, sx.uid, sx.gid, sx.nlink, sx.dev_major, sx.dev_minor,
                  sx.rdev_major, sx.rdev_minor) ==
                 (info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink,
                  os.major(info.st_dev), os.minor(info.st_dev),
                  os.major(info.st_rdev), os.minor(info.st_rdev))
                 and all(0 <= item.nsec < 1000000000 for item in (sx.atime, sx.ctime, sx.mtime)),
            "HOST_LOCAL_KERNEL_ABI_METADATA", "statx_crosscheck", label)
        vfs = self.call("fstatvfs", label, os.fstatvfs, fd)
        _require((fs.bsize, fs.frsize, fs.namelen) == (vfs.f_bsize, vfs.f_frsize, vfs.f_namemax),
            "HOST_LOCAL_KERNEL_ABI_METADATA", "fstatfs_crosscheck", label)
        value.update(procfs_magic=fs.type, mount_id=sx.mnt_id, statx_mask=sx.mask)
        if label != "root":
            _require(fs.type == PROC_SUPER_MAGIC, "HOST_LOCAL_KERNEL_NOT_PROCFS", "procfs", label)
            identity = (info.st_dev, sx.mnt_id)
            if self.proc_identity is None:
                self.proc_identity = identity
            _require(identity == self.proc_identity, "HOST_LOCAL_KERNEL_MOUNT_CHANGED", "mount_identity", label)
        qualification = self.report.get("qualification")
        if qualification is not None:
            qualification["native_metadata_crosschecks_completed"] += 1
        self.report["last_metadata_observation"] = dict(target=label, **value)
        return value

    def equal(self, left, right, label):
        _require(_same(left, right) and left["mount_id"] == right["mount_id"]
            and left["procfs_magic"] == right["procfs_magic"],
            "HOST_LOCAL_KERNEL_IDENTITY_CHANGED", "identity", label)

    def verify(self, *, post_read=False):
        result = []
        if post_read:
            self.report["after"] = result
        for index, item in enumerate(self.held):
            name, fd, label, directory, before = item
            current = self.snapshot(fd, label, directory)
            result.append(dict(target=label, **current))
            self.equal(before, current, label)
            flags = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC | (os.O_DIRECTORY if directory else 0)
            # Reopen each name as O_PATH to detect same-inode bind mount changes.
            check_fd = self.opened(name, flags, label,
                parent=None if index == 0 else self.held[index - 1][1])
            try:
                named = self.snapshot(check_fd, label, directory)
                self.equal(before, named, label)
            finally:
                self.close_one(check_fd, label)
        return result

    def read(self):
        self.check("abi_layout", self.kind)
        self.abi = _load_abi(self.kind)
        euid = self.call("geteuid", self.kind, os.geteuid)
        self.allowed_uids = {0, euid}
        if self.kind == "boot":
            parts = (("/", "root"), ("proc", "proc"), ("sys", "boot_sys"),
                ("kernel", "boot_kernel"), ("random", "boot_random"), ("boot_id", "boot"))
            maximum = 64
        else:
            pid = self.call("getpid", "mountinfo", os.getpid)
            _require(type(pid) is int and pid > 0, "HOST_LOCAL_KERNEL_PID", "getpid", "mountinfo")
            parts = (("/", "root"), ("proc", "proc"), (str(pid), "own_pid"), ("mountinfo", "mountinfo"))
            maximum = 1024**2
        self.report.update(maximum_bytes=maximum, euid=euid,
            qualification=dict(abi="linux-x86_64-lp64", layout_checked=True,
                native_metadata_crosscheck_required=True, native_metadata_crosschecks_completed=0,
                native_metadata_crosscheck_complete=False, content_open_noatime=False,
                all_names_nofollow_required=True, same_proc_mount_required=True))
        for index, (name, label) in enumerate(parts):
            directory = index < len(parts) - 1
            flags = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC | (os.O_DIRECTORY if directory else 0)
            fd = self.opened(name, flags, label, parent=None if index == 0 else self.held[-1][1])
            value = self.snapshot(fd, label, directory)
            self.held.append((name, fd, label, directory, value))
            self.report["before"].append(dict(target=label, **value))
        read_fd = self.opened(parts[-1][0], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            self.kind, parent=self.held[-2][1])
        opened_before = self.snapshot(read_fd, self.kind, False)
        self.equal(self.held[-1][4], opened_before, self.kind)
        self.report["read_fd_before"] = opened_before
        self.verify()
        self.report["qualification"]["qualified_before_content"] = True
        pieces, total = [], 0
        while True:
            raw = self.call("read", self.kind, os.read, read_fd, min(65536, maximum + 1 - total))
            if not raw:
                break
            total += len(raw)
            self.report["bytes_observed"] = total
            _require(total <= maximum, "HOST_LOCAL_KERNEL_READ_LIMIT", "read_limit", self.kind)
            pieces.append(raw)
        opened_after = self.snapshot(read_fd, self.kind, False)
        self.report["read_fd_after"] = opened_after
        self.equal(opened_before, opened_after, self.kind)
        self.verify(post_read=True)
        raw = b"".join(pieces)
        self.report["qualification"]["native_metadata_crosscheck_complete"] = True
        self.report.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
            dynamic_kernel_metadata_may_change=True, historical_metadata_preservation_claimed=False)
        return raw

    def close(self):
        failures = []
        for fd in reversed(self.open_fds):
            try:
                os.close(fd)
            except OSError as error:
                failures.append(dict(reason="HOST_LOCAL_KERNEL_SYSCALL", operation="close",
                    target=self.kind, errno=error.errno))
        self.open_fds.clear()
        if failures:
            self.report["cleanup_errors"] = failures
            return KernelFactError(**failures[0])
        return None


def read_fact(kind, guard, report):
    """Read fixed ``boot`` or ``mountinfo``; fill a bounded observation dict.

    Deadline exceptions from guard retain their original type and reason. Errors
    from this component carry operation/target/errno without raw exception text.
    No returned data establishes namespace alignment, a boot pin or admission.
    """
    _require(type(kind) is str and kind in ("boot", "mountinfo"),
        "HOST_LOCAL_KERNEL_KIND", "select_target", "invalid")
    _require(callable(guard) and type(report) is dict, "HOST_LOCAL_KERNEL_API", "arguments", kind)
    report.update(status="READING", target=kind, before=[], after=[], bytes_observed=0,
        namespace_alignment=dict(status="ENVIRONMENT_ASSUMPTION_NOT_PROVEN",
            required="original_host_terminal_and_matching_pid_proc_namespaces",
            namespace_changed=False))
    reader = _Reader(kind, guard, report)
    active_error = False
    try:
        raw = reader.read()
        report["status"] = "OBSERVED"
        return raw
    except BaseException as error:
        active_error = True
        report["status"] = "BLOCKED"
        report["error"] = error.detail if isinstance(error, KernelFactError) else dict(
            reason="HOST_LOCAL_KERNEL_GUARD_OR_INTERNAL_ERROR", operation=reader.operation,
            target=reader.target, errno=getattr(error, "errno", None), error_type=type(error).__name__)
        raise
    finally:
        error = reader.close()
        if error is not None and not active_error:
            report.update(status="BLOCKED", error=error.detail)
            raise error
