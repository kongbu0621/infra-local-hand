"""Fixed data-only snapshot for LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1.

No configuration is executed, no Include is followed, and no process is spawned.
The root/owner arguments of Snapshot are local fixture seams, not CLI options.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
import stat
import sys
import time

SCHEMA = "lhq-sshd-source-capture-v1"
SESSION = "lhqsshd-20261005a"
MAIN = "/etc/ssh/sshd_config"
DIRECTORY = "/etc/ssh/sshd_config.d"
FILE_LIMIT = 262144
TOTAL_LIMIT = 1048576
OUTPUT_LIMIT = 2097152
LIMITS = {"cpu_seconds": 5, "address_space_bytes": 134217728,
          "nofile": 128, "fsize": 0, "core": 0, "alarm_seconds": 20}
META = ("dev", "ino", "mode", "uid", "gid", "nlink", "size", "blocks", "mtime_ns", "ctime_ns")


class CaptureError(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise CaptureError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"


def metadata(info):
    return {name: getattr(info, "st_" + name) for name in META}


class Snapshot:
    def __init__(self, root_fd, check, *, owner=0):
        self.check = check
        self.owner = owner
        self.root_fd = root_fd
        self.root_meta = metadata(os.fstat(root_fd))
        self.objects = []
        self.absent = []
        self.listings = []
        self.total = 0
        self.stage = "ROOT"
        self.index = 0
        self.qualify(os.fstat(root_fd), directory=True)

    def qualify(self, info, *, directory):
        require(info.st_uid == self.owner and not info.st_mode & 0o022, "PROTECTION")
        require(stat.S_ISDIR(info.st_mode) if directory else
                stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "TYPE")

    def open(self, parent, name, *, directory=False, optional=False):
        self.check()
        try:
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            require(optional, "MISSING")
            self.absent.append((parent, name))
            self.check()
            return None
        self.qualify(before, directory=directory)
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NOATIME | os.O_NONBLOCK
        if directory:
            flags |= os.O_DIRECTORY
        fd = os.open(name, flags, dir_fd=parent)
        self.objects.append((parent, name, fd, metadata(before)))
        self.check()
        require(metadata(os.fstat(fd)) == metadata(before), "OPEN_DRIFT")
        self.qualify(os.fstat(fd), directory=directory)
        return fd

    def names(self, fd):
        values = []
        with os.scandir(fd) as entries:
            for entry in entries:
                self.check()
                require(len(values) < 256 and entry.name.isascii(), "DIRECTORY_LIMIT")
                values.append(entry.name)
        values.sort()
        require(len(canonical(values)) <= 65536, "DIRECTORY_LIMIT")
        return values

    def read(self, fd):
        before = metadata(os.fstat(fd))
        require(0 <= before["size"] <= FILE_LIMIT, "FILE_LIMIT")
        require(self.total + before["size"] <= TOTAL_LIMIT, "TOTAL_LIMIT")
        raw = bytearray()
        while True:
            self.check()
            block = os.read(fd, min(65536, before["size"] + 1 - len(raw)))
            self.check()
            if not block:
                break
            raw.extend(block)
            require(len(raw) <= before["size"], "READ_GROWTH")
        after = metadata(os.fstat(fd))
        require(before == after and len(raw) == before["size"], "READ_DRIFT")
        self.total += len(raw)
        return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                    base64=base64.b64encode(raw).decode("ascii"), before=before, after=after)

    def recheck(self):
        self.check()
        for fd, names in self.listings:
            require(self.names(fd) == names, "LISTING_DRIFT")
        require(metadata(os.fstat(self.root_fd)) == self.root_meta, "ROOT_DRIFT")
        for parent, name, fd, before in self.objects:
            self.check()
            require(metadata(os.fstat(fd)) == before and
                    metadata(os.stat(name, dir_fd=parent, follow_symlinks=False)) == before,
                    "FINAL_DRIFT")
        for parent, name in self.absent:
            self.check()
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise CaptureError("ABSENCE_DRIFT")
        self.check()

    def collect(self):
        self.stage = "PARENTS"
        etc = self.open(self.root_fd, "etc", directory=True)
        ssh = self.open(etc, "ssh", directory=True)
        self.stage = "MAIN"
        self.index = 1
        main = self.open(ssh, "sshd_config")
        self.stage = "DIRECTORY"
        directory = self.open(ssh, "sshd_config.d", directory=True, optional=True)
        names = [] if directory is None else self.names(directory)
        if directory is not None:
            self.listings.append((directory, names))
        selected = [name for name in names if name.endswith(".conf")]
        require(len(selected) <= 64, "FILE_COUNT")
        self.stage = "READ"
        held = [(MAIN, main)]
        for name in selected:
            self.index = len(held) + 1
            held.append((DIRECTORY + "/" + name, self.open(directory, name)))
        files = []
        for self.index, (path, fd) in enumerate(held, 1):
            files.append(dict(path=path, **self.read(fd)))
        self.stage = "FINAL"
        if directory is not None:
            require(self.names(directory) == names, "LISTING_DRIFT")
        self.recheck()
        for record, (_, fd) in zip(files, held):
            record["final"] = metadata(os.fstat(fd))
            require(record["before"] == record["final"], "FINAL_DRIFT")
        self.recheck()
        return dict(directory={"state": "ABSENT" if directory is None else "PRESENT", "names": names},
                    files=files)

    def close(self):
        for _, _, fd, _ in reversed(self.objects):
            os.close(fd)
        self.objects.clear()


def configure_limits():
    import resource
    require(os.geteuid() == 0, "EUID")
    for key, number in ((resource.RLIMIT_CPU, 5), (resource.RLIMIT_AS, 134217728),
                        (resource.RLIMIT_NOFILE, 128), (resource.RLIMIT_FSIZE, 0),
                        (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(key, (number, number))
        require(resource.getrlimit(key) == (number, number), "RLIMIT")


def main():
    snapshot = None
    root = None
    start = time.monotonic_ns()
    stage = "LIMITS"
    def alarm(_signum, _frame):
        raise CaptureError("DEADLINE")
    def check():
        require(start <= time.monotonic_ns() < start + 20_000_000_000, "DEADLINE")
    try:
        configure_limits()
        signal.signal(signal.SIGALRM, alarm)
        signal.alarm(20)
        start = time.monotonic_ns()
        stage = "ROOT"
        root = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NOATIME)
        snapshot = Snapshot(root, check)
        result = snapshot.collect()
        require(metadata(os.stat("/", follow_symlinks=False)) == snapshot.root_meta, "ROOT_DRIFT")
        result.update(schema=SCHEMA, session=SESSION, source_sha256=sys.argv[2], euid=os.geteuid(),
                      limits=LIMITS, elapsed_ns=time.monotonic_ns() - start, status="COMPLETE")
        raw = canonical(result)
        require(len(raw) <= OUTPUT_LIMIT, "OUTPUT_LIMIT")
        check()
        offset = 0
        while offset < len(raw):
            check()
            count = os.write(1, raw[offset:offset + 65536])
            require(count > 0, "OUTPUT_WRITE")
            offset += count
        check()
        return 0
    except (Exception, KeyboardInterrupt) as error:
        reason = str(error) if type(error) is CaptureError else "IO_OR_RUNTIME"
        # No paths, configuration, or arbitrary exception text leave stderr.
        report = dict(schema=SCHEMA, session=SESSION, status="FAILED", reason=reason,
                      stage=snapshot.stage if snapshot else stage, index=snapshot.index if snapshot else 0)
        try:
            os.write(2, canonical(report))
        except OSError:
            pass
        return 3
    finally:
        if snapshot is not None:
            snapshot.close()
        if root is not None:
            os.close(root)


if __name__ == "__main__":
    sys.exit(main())
