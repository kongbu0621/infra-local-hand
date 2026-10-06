"""Fixed five-parent capacity observation. No children, listings or business I/O.

The owner/root seams on Observation are solely for local synthetic fixtures.
The executable entry always uses /, uid/gid 0 and the exact encoded description.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import re
import signal
import stat
import struct
import sys
import time
import uuid

SCHEMA = "lhq-core-capacity-observation/v1"
SESSION = "lhqcap-20261006a"
ROLES = ("state", "quota", "install", "journal", "evidence")
PLAN_SHA = "efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c"
LIMITS = dict(cpu_seconds=5, address_space_bytes=134217728, nofile=128,
              fsize=0, core=0, alarm_seconds=20)
IDENTITY = ("dev", "ino", "mode", "uid", "gid")
STATVFS = ("f_bsize", "f_frsize", "f_blocks", "f_bfree", "f_bavail",
           "f_files", "f_ffree", "f_favail", "f_flag", "f_namemax")


class ObservationError(RuntimeError):
    pass


def require(ok, code):
    if not ok:
        raise ObservationError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def integer(value, low=0, high=2**63 - 1):
    require(type(value) is int and low <= value <= high, "INTEGER")
    return value


def parse(raw, limit):
    require(type(raw) is bytes and 0 < len(raw) <= limit, "JSON_SIZE")
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "JSON_DUPLICATE")
            value[key] = item
        return value
    def invalid(_):
        raise ObservationError("JSON_NUMBER")
    return json.loads(raw.decode("ascii", "strict"), object_pairs_hook=pairs,
                      parse_float=invalid, parse_constant=invalid)


def path_value(path):
    require(type(path) is str and path.isascii() and 1 < len(path) <= 512 and
            path.startswith("/") and "\\" not in path and "\0" not in path, "PATH")
    parts = path.split("/")[1:]
    require(len(parts) <= 16 and all(part not in ("", ".", "..") for part in parts), "PATH_ALIAS")
    return parts


def description(raw):
    value = parse(raw, 8192)
    require(type(value) is dict and set(value) == {"schema", "session", "plan_sha256", "paths"}
            and value["schema"] == "lhq-core-capacity-paths/v1" and value["session"] == SESSION
            and value["plan_sha256"] == PLAN_SHA, "DESCRIPTION")
    require(type(value["paths"]) is dict and set(value["paths"]) == set(ROLES), "ROLES")
    for path in value["paths"].values():
        path_value(path)
    return value


def identity(info):
    return {key: getattr(info, "st_" + key) for key in IDENTITY}


def qualify(info, *, final=False, owner=0, group=0):
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == owner and
            not info.st_mode & 0o022, "DIRECTORY_PROTECTION")
    if final:
        require(info.st_gid == group and stat.S_IMODE(info.st_mode) in (0o700, 0o755),
                "FINAL_PROTECTION")


def filesystem_type(fd):
    library = ctypes.CDLL(None, use_errno=True)
    value = ctypes.create_string_buffer(256)
    library.fstatfs.argtypes = [ctypes.c_int, ctypes.c_void_p]
    library.fstatfs.restype = ctypes.c_int
    if library.fstatfs(fd, ctypes.byref(value)):
        raise OSError(ctypes.get_errno(), "filesystem identity")
    return ctypes.c_long.from_buffer(value).value


def kernel_read(path, limit, check):
    require(path == "/proc/self/mountinfo" or re.fullmatch(r"/proc/self/fdinfo/[0-9]+", path),
            "KERNEL_PATH")
    check()
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NOATIME)
    try:
        check()
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and
                filesystem_type(fd) == 0x9FA0, "PROCFS")
        data = bytearray()
        while True:
            check()
            block = os.read(fd, min(65536, limit + 1 - len(data)))
            check()
            if not block:
                break
            data.extend(block)
            require(len(data) <= limit, "KERNEL_LIMIT")
        require(identity(before) == identity(os.fstat(fd)) and
                identity(before) == identity(os.stat(path, follow_symlinks=False)), "KERNEL_DRIFT")
        check()
        return bytes(data)
    finally:
        os.close(fd)


def mounts(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 1048576, "MOUNT_SIZE")
    rows = {}
    for line in raw.decode("ascii", "strict").splitlines():
        words = line.split()
        require(words.count("-") == 1, "MOUNT_FORMAT")
        sep = words.index("-")
        require(sep >= 6 and len(words) == sep + 4, "MOUNT_FORMAT")
        mid = integer(int(words[0]), 1)
        major, minor = (integer(int(v), 0, 2**32 - 1) for v in words[2].split(":"))
        require(mid not in rows and not any("\\" in words[i] for i in (3, 4, sep + 2)), "MOUNT_ALIAS")
        rows[mid] = dict(mount_id=mid, device=os.makedev(major, minor), root=words[3],
                         path=words[4], fstype=words[sep + 1], source=words[sep + 2],
                         options=sorted(set(words[5].split(",") + words[sep + 3].split(","))))
    require(rows, "MOUNT_EMPTY")
    return rows


def mount_id(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 4096, "FDINFO_SIZE")
    entries = [line.split(":", 1)[1].strip() for line in raw.decode("ascii").splitlines()
               if line.startswith("mnt_id:")]
    require(len(entries) == 1 and re.fullmatch(r"[0-9]+", entries[0]), "MOUNT_ID")
    return integer(int(entries[0]), 1)


def fs_uuid(fd):
    import fcntl
    value = bytearray(struct.pack("=II", 16, 0) + bytes(16))
    fcntl.ioctl(fd, 0x8008662c, value, True)
    require(struct.unpack("=II", value[:8]) == (16, 0) and any(value[8:]), "FILESYSTEM_UUID")
    return str(uuid.UUID(bytes=bytes(value[8:])))


def amounts(raw):
    require(type(raw) is dict and set(raw) == set(STATVFS), "STATVFS_FIELDS")
    for name, value in raw.items():
        integer(value, -(2**63) if name in ("f_bavail", "f_favail") else 0)
    require(raw["f_frsize"] > 0 and raw["f_bsize"] > 0, "STATVFS_UNIT")
    return dict(bytes=integer(raw["f_bavail"] * raw["f_frsize"], -(2**63)),
                inodes=raw["f_favail"])


class Observation:
    def __init__(self, paths, check, *, root="/", owner=0, group=0, clock=time.monotonic_ns):
        self.paths, self.check, self.root = paths, check, root
        self.owner, self.group, self.clock = owner, group, clock
        self.held = {}
        self.stage, self.role = "ROOT", None

    def call(self, function, *args, **kwargs):
        self.check()
        result = function(*args, **kwargs)
        self.check()
        return result

    def open(self, name, parent=None):
        self.check()
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC,
                     **({} if parent is None else {"dir_fd": parent}))
        try:
            self.check()
            return fd
        except BaseException:
            os.close(fd)
            raise

    def keep(self, key, fd):
        try:
            info = self.call(os.fstat, fd)
            qualify(info, owner=self.owner, group=self.group)
            self.held[key] = (fd, identity(info))
        except BaseException:
            os.close(fd)
            raise

    def open_paths(self):
        self.keep((), self.open(self.root))
        for role in ROLES:
            parts = path_value(self.paths[role])
            for depth, name in enumerate(parts, 1):
                key = tuple(parts[:depth])
                if key not in self.held:
                    self.keep(key, self.open(name, self.held[key[:-1]][0]))
            qualify(self.call(os.fstat, self.held[tuple(parts)][0]), final=True,
                    owner=self.owner, group=self.group)
        require(len(self.held) <= 81, "FD_COUNT")

    def filesystem(self, fd, table):
        mid = mount_id(kernel_read("/proc/self/fdinfo/" + str(fd), 4096, self.check))
        require(mid in table, "MOUNT_BINDING")
        mount = table[mid]
        info = self.call(os.fstat, fd)
        require(mount["device"] == info.st_dev and mount["fstype"] == "ext4" and
                mount["root"] == "/" and "rw" in mount["options"] and "ro" not in mount["options"],
                "FILESYSTEM")
        return dict(mount=mount, uuid=self.call(fs_uuid, fd))

    def reopen(self):
        # Keep at most two temporary directory fds, not a second 81-fd tree.
        for role in ROLES:
            self.role = role
            temp = self.open(self.root)
            try:
                require(identity(self.call(os.fstat, temp)) == self.held[()][1], "ROOT_DRIFT")
                parts = path_value(self.paths[role])
                for depth, name in enumerate(parts, 1):
                    new = self.open(name, temp)
                    os.close(temp)
                    temp = new
                    key = tuple(parts[:depth])
                    require(identity(self.call(os.fstat, temp)) == self.held[key][1], "NAME_DRIFT")
            finally:
                os.close(temp)
        for fd, before in self.held.values():
            require(identity(self.call(os.fstat, fd)) == before, "FD_DRIFT")

    def collect(self):
        self.open_paths()
        self.stage = "MOUNT_BEFORE"
        before = kernel_read("/proc/self/mountinfo", 1048576, self.check)
        table = mounts(before)
        rows = []
        for role in ROLES:
            self.stage, self.role = "SAMPLE", role
            fd, info = self.held[tuple(path_value(self.paths[role]))]
            filesystem = self.filesystem(fd, table)
            start = self.call(self.clock)
            values = self.call(os.fstatvfs, fd)  # Exactly once per role.
            end = self.call(self.clock)
            raw = {name: getattr(values, name) for name in STATVFS}
            rows.append(dict(role=role, path=self.paths[role], directory=info, filesystem=filesystem,
                             statvfs=raw, available=amounts(raw), start_ns=start, end_ns=end))
        self.stage = "RECHECK"
        self.reopen()
        after = kernel_read("/proc/self/mountinfo", 1048576, self.check)
        require(before == after, "MOUNT_DRIFT")
        for row in rows:
            self.role = row["role"]
            fd, info = self.held[tuple(path_value(row["path"]))]
            require(identity(self.call(os.fstat, fd)) == info and
                    self.filesystem(fd, table) == row["filesystem"], "FILESYSTEM_DRIFT")
        self.check()
        return rows

    def close(self):
        for fd, _ in reversed(list(self.held.values())):
            os.close(fd)
        self.held.clear()


def configure_limits():
    import resource
    require(os.geteuid() == 0, "EUID")
    for key, number in ((resource.RLIMIT_CPU, 5), (resource.RLIMIT_AS, 134217728),
                        (resource.RLIMIT_NOFILE, 128), (resource.RLIMIT_FSIZE, 0), (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(key, (number, number))
        require(resource.getrlimit(key) == (number, number), "RLIMIT")


def main():
    observation = None
    stage = "LIMITS"
    start = time.monotonic_ns()
    previous = start
    def alarm(_signum, _frame):
        raise ObservationError("DEADLINE")
    def check():
        nonlocal previous
        current = time.monotonic_ns()
        require(previous <= current < start + 20_000_000_000, "DEADLINE")
        previous = current
    try:
        configure_limits()
        signal.signal(signal.SIGALRM, alarm)
        signal.alarm(20)
        start = previous = time.monotonic_ns()
        stage = "DESCRIPTION"
        raw = base64.b64decode(sys.argv[3], validate=True)
        require(digest(raw) == sys.argv[4], "DESCRIPTION_DIGEST")
        desc = description(raw)
        require(re.fullmatch("[0-9a-f]{64}", sys.argv[2]), "SOURCE_DIGEST")
        observation = Observation(desc["paths"], check)
        rows = observation.collect()
        value = dict(schema=SCHEMA, session=SESSION, status="CURRENT_CAPACITY_OBSERVATION",
                     source_sha256=sys.argv[2], description_sha256=digest(raw), euid=0, limits=LIMITS,
                     start_ns=start, end_ns=time.monotonic_ns(), rows=rows)
        encoded = canonical(value)
        require(len(encoded) <= 65536, "OUTPUT_LIMIT")
        check()
        offset = 0
        while offset < len(encoded):
            check()
            count = os.write(1, encoded[offset:])
            require(count > 0, "OUTPUT_WRITE")
            offset += count
        check()
        return 0
    except (Exception, KeyboardInterrupt) as error:
        reason = str(error) if type(error) is ObservationError else "IO_OR_RUNTIME"
        try:
            os.write(2, canonical(dict(schema=SCHEMA, session=SESSION, status="FAILED", reason=reason,
                stage=observation.stage if observation else stage, role=observation.role if observation else None)))
        except OSError:
            pass
        return 3
    finally:
        if observation is not None:
            observation.close()


if __name__ == "__main__":
    sys.exit(main())
