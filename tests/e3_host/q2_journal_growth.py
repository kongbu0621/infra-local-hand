"""J1 journal maintenance primitives; never an old carrier/recovery entry.

The field entry remains closed until the complete J2 execution manifest exists.
In particular, a native image test is not a guest quiescence attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import selectors
import shlex
import stat
import subprocess
import sys
import time
import select

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from e3_host import q2_core_capacity_capture as prior

local = prior.local
require, canonical, digest = prior.require, prior.canonical, prior.digest
R = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
A = "59948ec4fedb807a31cdbff77acc134e84414160"
C = "6493b1ae035dfa852952165046417c78f0f5383c"
SESSION = "lhqjgrow-20261006a"
MIB = 1048576
OLD_SIZE, NEW_SIZE = 256 * MIB, 512 * MIB
BACKUP_CAP, IMAGE_CAP, CAPTURE_CAP = 320 * MIB, 576 * MIB, 8 * MIB
HOST_BYTES, HOST_INODES = 1296 * MIB, 370
STATES = ("LOCAL_CHECKED", "CONSUMED", "GUEST_QUIET", "POWERED_OFF",
          "BACKED_UP", "IMAGE_GROWN", "BOOTED", "FILESYSTEM_GROWN", "VERIFIED")
SUFFIXES = ("consumed.json", "events.jsonl", "pre.stdout", "pre.stderr", "post.stdout",
            "post.stderr", "receipt.json", "vm.pid", "journal.backup.qcow2")
NAMES = {suffix: "." + SESSION + "." + suffix for suffix in SUFFIXES}
DOC_PINS = {
    "REQUIREMENTS.md": "93ac5383bb1823086dc0546fb4eebcf1f70ffd7e7a824247b3f6c9e210417f4d",
    "ARCHITECTURE.md": "5b703c51afab91676851af1bcaf4464469ea2183f7bd5dbc79d120a1efcc6f28",
    "IMPLEMENTATION_PLAN.md": "aa3c04b8fce9a914dd7009644ac0a3a853a8d4f38de8f85b73a0d644dd723e60",
}
CAPACITY_PINS = {
    "consumed.json": (939, "537f3f93f47034ae253c735052cbae443eea3aa3f775849698830e4b26cec9ff"),
    "stdout": (3609, "00cc8b744b8d63bf7d83a4044921fc1a80b7a21b289cf62b4e6f33cd9548b8db"),
    "stderr": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "receipt.json": (1807, "575e74006d530fd562a67d66d5ce066a8e941d914da1f84bec2eb839b7ee4270"),
}


class Window(local.Deadline):
    def remaining(self, limit=900):
        return super().remaining(limit)

    def change(self):
        self.remaining(780)


class Sequence:
    """No resume, rollback, repetition or skipped state, even after exceptions."""
    def __init__(self, check, record):
        self.state = "LOCAL_CHECKED"
        self.check, self.record = check, record
        self.started = set()

    def step(self, target, effect):
        require(self.state in STATES and target in STATES and
                STATES.index(target) == STATES.index(self.state) + 1,
                "GROWTH_SEQUENCE")
        require(target not in self.started, "GROWTH_NO_RETRY")
        self.started.add(target)
        try:
            self.check()
            self.record(dict(step=target, state="STARTED"))
            result = effect()
            self.check()
            self.record(dict(step=target, state="RETURNED", result=result))
            self.state = target
            return result
        except BaseException:
            self.state = "STOP_AND_RETAIN"
            raise


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink)


def stable_identity(info):
    return identity(info) + (info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def validate_file(info, cap, owner):
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == owner
            and stat.S_IMODE(info.st_mode) == 0o600 and 0 <= info.st_size <= cap
            and info.st_blocks * 512 <= cap, "GROWTH_FILE")


def write_all(fd, raw, check):
    view = memoryview(raw)
    while view:
        check()
        count = os.write(fd, view)
        require(count > 0, "GROWTH_SHORT_WRITE")
        view = view[count:]
    check()


def hash_fd(fd, cap, check):
    before = os.fstat(fd)
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
            "GROWTH_HASH_FILE")
    os.lseek(fd, 0, os.SEEK_SET)
    value, count = hashlib.sha256(), 0
    while True:
        check()
        part = os.read(fd, min(65536, cap + 1 - count))
        check()
        if not part:
            break
        count += len(part)
        require(count <= cap, "GROWTH_HASH_LIMIT")
        value.update(part)
    require(count == before.st_size and stable_identity(os.fstat(fd)) == stable_identity(before),
            "GROWTH_HASH_DRIFT")
    return dict(bytes=count, sha256=value.hexdigest())


class Store:
    """Fixed create-only output namespace. Failures deliberately leave files."""
    def __init__(self, fd, check):
        self.fd, self.check = fd, check
        self.owner = os.geteuid()
        self.opened = {}

    def absent(self):
        for name in NAMES.values():
            try:
                os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise prior.r.ObservationError("GROWTH_OUTPUT_EXISTS")

    def capacity(self):
        self.check()
        value = os.fstatvfs(self.fd)
        require(value.f_bavail * value.f_frsize >= HOST_BYTES and value.f_favail >= HOST_INODES,
                "GROWTH_HOST_CAPACITY")

    def create(self, suffix):
        require(suffix in NAMES and suffix not in self.opened, "GROWTH_OUTPUT_NAME")
        self.check()
        fd = os.open(NAMES[suffix], os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                     | os.O_CLOEXEC | os.O_NOATIME, 0o600, dir_fd=self.fd)
        self.opened[suffix] = fd
        require(stat.S_IMODE(os.fstat(fd).st_mode) == 0o600, "GROWTH_OUTPUT_MODE")
        os.fsync(self.fd)
        return fd

    def budget(self):
        logical = allocated = count = 0
        for suffix, fd in self.opened.items():
            info = os.fstat(fd)
            require(stable_identity(info) == stable_identity(os.stat(NAMES[suffix], dir_fd=self.fd,
                                                                   follow_symlinks=False)), "GROWTH_OUTPUT_DRIFT")
            cap = BACKUP_CAP if suffix == "journal.backup.qcow2" else CAPTURE_CAP
            validate_file(info, cap, self.owner)
            if suffix != "journal.backup.qcow2":
                count += 1
                logical += info.st_size
                allocated += info.st_blocks * 512
        require(max(logical, allocated) <= CAPTURE_CAP and count <= 32, "GROWTH_CAPTURE_BUDGET")
        return dict(logical_bytes=logical, allocated_bytes=allocated, inodes=count)

    def put(self, suffix, raw):
        require(type(raw) is bytes and len(raw) <= (MIB if suffix.endswith(("stdout", "stderr"))
                                                  else 65536), "GROWTH_OUTPUT_LIMIT")
        fd = self.create(suffix)
        write_all(fd, raw, self.check)
        os.fsync(fd)
        self.budget()
        return fd

    def event(self, value):
        raw = canonical(value)
        require(len(raw) <= 65536, "GROWTH_EVENT_LIMIT")
        fd = self.opened.get("events.jsonl")
        if fd is None:
            fd = self.create("events.jsonl")
        require(os.fstat(fd).st_size + len(raw) <= MIB, "GROWTH_EVENTS_LIMIT")
        write_all(fd, raw, self.check)
        os.fsync(fd)
        self.budget()

    def close(self):
        for fd in self.opened.values():
            os.close(fd)
        self.opened.clear()


def full_backup(store, source_fd):
    """Call only after independent VM-exit and exclusive image checks."""
    store.capacity()
    before = os.fstat(source_fd)
    validate_file(before, BACKUP_CAP, os.geteuid())
    source_digest = hash_fd(source_fd, BACKUP_CAP, store.check)
    target = store.create("journal.backup.qcow2")
    os.lseek(source_fd, 0, os.SEEK_SET)
    count = 0
    while count < before.st_size:
        store.check()
        raw = os.read(source_fd, min(65536, before.st_size - count))
        require(raw, "GROWTH_BACKUP_SHORT_READ")
        write_all(target, raw, store.check)
        count += len(raw)
        store.budget()
    os.fsync(target)
    require(stable_identity(os.fstat(source_fd)) == stable_identity(before), "GROWTH_BACKUP_DRIFT")
    copied_digest = hash_fd(target, BACKUP_CAP, store.check)
    require(copied_digest == source_digest and os.fstat(target).st_ino != before.st_ino,
            "GROWTH_BACKUP_MISMATCH")
    store.budget()
    store.capacity()
    return copied_digest


def qemu_argv(start, anchor, serial):
    """Parse pinned literal launcher, never evaluate its shell or mktemp."""
    require(digest(start) == local.PINS["start.sh"][1], "GROWTH_START_PIN")
    require(re.fullmatch(r"/[A-Za-z0-9_./-]+", anchor) and os.path.normpath(anchor) == anchor,
            "GROWTH_ANCHOR")
    text = start.decode("utf-8", "strict")
    require("q1_vm=" + anchor + "\n" in text, "GROWTH_START_ANCHOR")
    pieces = text.split("\nqemu-system-x86_64 \\\n")
    require(len(pieces) == 2, "GROWTH_START_FORMAT")
    command = pieces[1].split("\n\n", 1)[0].replace("\\\n", " ")
    args = shlex.split(command)
    require(all(arg.isascii() for arg in args), "GROWTH_START_ENCODING")
    args = [arg.replace("$q1_vm", anchor).replace("$q1_log", serial) for arg in args]
    require(not any("$" in arg or "`" in arg for arg in args), "GROWTH_START_EXPANSION")
    require(args.count("-pidfile") == args.count("-serial") == 1 and
            args[args.index("-pidfile") + 1] == anchor + "/vm.pid" and
            args[args.index("-serial") + 1] == "file:" + serial, "GROWTH_START_OUTPUT")
    original = ["/usr/bin/qemu-system-x86_64", *args]
    new = original.copy()
    new[new.index("-pidfile") + 1] = anchor + "/" + NAMES["vm.pid"]
    new[new.index("-serial") + 1] = "null"
    require(sum(a != b for a, b in zip(original, new)) == 2, "GROWTH_START_DELTA")
    return original, new


def image_commands(path, backup):
    """No repair, force-share, shrink, shell or format auto-detection."""
    return dict(info=["info", "--output=json", "-f", "qcow2", path],
                check=["check", "--output=json", "-f", "qcow2", path],
                resize=["resize", "-f", "qcow2", path, str(NEW_SIZE)],
                compare=["compare", "-f", "qcow2", "-F", "qcow2", backup, path])


def validate_image_info(raw, expected_size):
    value = prior.r.parse(raw, 65536)
    require(expected_size in (OLD_SIZE, NEW_SIZE) and value.get("format") == "qcow2"
            and value.get("virtual-size") == expected_size and not value.get("encrypted", False)
            and not value.get("snapshots") and not value.get("backing-filename")
            and not value.get("full-backing-filename"), "GROWTH_IMAGE_INFO")
    data = value.get("format-specific", {}).get("data", {})
    require(data.get("compat") == "1.1" and data.get("corrupt") is False
            and not data.get("bitmaps") and not data.get("encrypt"), "GROWTH_IMAGE_FEATURES")
    return value


def control_limits():
    """Never apply to QEMU: its approved RAM is eight GiB."""
    resource.setrlimit(resource.RLIMIT_AS, (256 * MIB, 256 * MIB))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # No RLIMIT_CPU/FSIZE: mutators must not be killed by such limits.


class Command:
    """Bounded observation; timeout retains a live mutator, never kills it.

    No subprocess context manager: __exit__ would wait past the window.
    The caller owns the live handle after an incomplete result.
    """
    def __init__(self, argv, check, *, executable=None, pass_fds=(), limit=MIB, limits=True):
        require(0 < limit <= MIB, "GROWTH_STREAM_CAP")
        check()
        self.check, self.limit = check, limit
        self.process = subprocess.Popen(argv, executable=executable, pass_fds=pass_fds,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            preexec_fn=control_limits if limits else None, start_new_session=True)
        self.output = {"stdout": bytearray(), "stderr": bytearray()}
        self.eof = {"stdout": False, "stderr": False}
        self.selector = selectors.DefaultSelector()
        for name in self.output:
            stream = getattr(self.process, name)
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, name)

    def collect(self):
        try:
            while self.selector.get_map() or self.process.poll() is None:
                self.check()
                for key, _ in self.selector.select(0.05):
                    name = key.data
                    raw = os.read(key.fileobj.fileno(), min(65536, self.limit + 1 - len(self.output[name])))
                    self.check()
                    if not raw:
                        self.eof[name] = True
                        self.selector.unregister(key.fileobj)
                        continue
                    self.output[name].extend(raw)
                    require(len(self.output[name]) <= self.limit, "GROWTH_STREAM_LIMIT")
            self.check()
            return dict(returncode=self.process.returncode, eof=self.eof.copy(),
                        **{name: bytes(value) for name, value in self.output.items()})
        finally:
            self.selector.close()
            for name in self.output:
                getattr(self.process, name).close()
            # Closing streams can affect writers. It is not remote exit proof.


def run_tool(argv, check, **kwargs):
    command = Command(argv, check, **kwargs)
    try:
        result = command.collect()
    except BaseException as error:
        # Keep the handle with the failure. A future dispatcher must record
        # this PID/start identity, not discard it or call wait/kill on timeout.
        error.growth_command = command
        raise
    require(result["returncode"] == 0 and all(result["eof"].values()), "GROWTH_TOOL_FAILED")
    return result


def proc_start(raw):
    tail = raw.rpartition(b") ")[2].split()
    require(len(tail) >= 20 and tail[19].isdigit(), "GROWTH_PROC_STAT")
    return int(tail[19])


class Tool:
    """Existing root-owned O_PATH execution binding; no byte-read fallback.

    Host A requires file identity/version. Guest resize2fs additionally needs
    a full byte digest, read by its already-root helper, not this class.
    """
    def __init__(self, path, check):
        self.path, self.check = path, check
        self.fd, self.info = local.bound_executable(path)
        require(os.fstat(self.fd).st_nlink == 1, "GROWTH_TOOL_LINK")
        try:
            result = self.run(["--version"])
            self.version = result["stdout"] + result["stderr"]
            require(0 < len(self.version) <= 16384, "GROWTH_TOOL_VERSION")
        except BaseException:
            self.close()
            raise

    def recheck(self):
        self.check()
        parent = local.open_directory(str(Path(self.path).parent), 0)
        try:
            current = os.stat(Path(self.path).name, dir_fd=parent, follow_symlinks=False)
            require(local.metadata(current) == self.info == local.metadata(os.fstat(self.fd))
                    and current.st_nlink == 1, "GROWTH_TOOL_DRIFT")
        finally:
            os.close(parent)

    def run(self, args, *, vm=False):
        self.recheck()
        result = run_tool([self.path, *args], self.check, executable=f"/proc/self/fd/{self.fd}",
                          pass_fds=(self.fd,), limits=not vm)
        self.recheck()
        return result

    def binding(self):
        self.recheck()
        value = dict(path=self.path, identity=self.info, version_sha256=digest(self.version))
        return value | dict(binding_sha256=digest(canonical(value)))

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def proc_bytes(pid, name, cap, check):
    require(type(pid) is int and pid > 0 and name in ("stat", "cmdline", "status"), "GROWTH_PROC_PATH")
    path = f"/proc/{pid}/{name}"
    check()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC)
    try:
        require(prior.r.filesystem_type(fd) == 0x9FA0, "GROWTH_PROCFS")
        raw = os.read(fd, cap + 1)
        require(len(raw) <= cap and identity(os.fstat(fd)) == identity(os.stat(path, follow_symlinks=False)),
                "GROWTH_PROC_DRIFT")
        check()
        return raw
    finally:
        os.close(fd)


class ProcessIdentity:
    """Pidfile is only a locator; held pidfd + start time + executable + argv."""
    def __init__(self, pid, argv, tool_fd, check):
        require(type(pid) is int and pid > 1 and hasattr(os, "pidfd_open"), "GROWTH_PID")
        self.pid, self.argv, self.tool_fd, self.check = pid, argv, tool_fd, check
        self.fd = os.pidfd_open(pid, 0)
        self.start = None
        try:
            self.recheck()
        except BaseException:
            self.close()
            raise

    def exited(self):
        self.check()
        return bool(select.select([self.fd], [], [], 0)[0])

    def recheck(self):
        require(not self.exited(), "GROWTH_PROCESS_EXITED")
        start = proc_start(proc_bytes(self.pid, "stat", 16384, self.check))
        require(self.start in (None, start), "GROWTH_PID_REUSED")
        self.start = start
        expected = b"\0".join(os.fsencode(word) for word in self.argv) + b"\0"
        require(proc_bytes(self.pid, "cmdline", 65536, self.check) == expected, "GROWTH_PROCESS_ARGV")
        # /proc/PID/exe is an intentional kernel magic link; compare the held
        # root-owned executable, never trust its displayed pathname alone.
        exe = os.open(f"/proc/{self.pid}/exe", os.O_PATH | os.O_CLOEXEC)
        try:
            require(identity(os.fstat(exe)) == identity(os.fstat(self.tool_fd)), "GROWTH_PROCESS_EXE")
        finally:
            os.close(exe)
        require(proc_start(proc_bytes(self.pid, "stat", 16384, self.check)) == start and not self.exited(),
                "GROWTH_PROCESS_DRIFT")
        return dict(pid=self.pid, starttime=start, argv_sha256=digest(expected))

    def close(self):
        os.close(self.fd)


def verify_writers(observations, expected_pid, expected_images):
    """Validate a complete fixed-image fd inventory, not a process-name guess."""
    require(type(observations) is list and all(type(row) is dict for row in observations), "GROWTH_WRITERS")
    require(all(row.get("complete") is True for row in observations), "GROWTH_WRITERS_UNKNOWN")
    actual = {(row["pid"], item) for row in observations for item in row["writable_images"]}
    expected = set() if expected_pid is None else {(expected_pid, item) for item in expected_images}
    require(actual == expected, "GROWTH_UNEXPECTED_WRITER")


def continue_token(nonce, pre_digest):
    require(re.fullmatch("[0-9a-f]{64}", nonce) and re.fullmatch("[0-9a-f]{64}", pre_digest),
            "GROWTH_TOKEN_BINDING")
    return ("POWER_OFF " + SESSION + " " + nonce + " " + pre_digest + "\n").encode("ascii")


def field_readiness():
    # Not a runtime authorization flag. Remove only after concrete J1 wiring
    # and all J2 evidence exist; never make this caller-selectable.
    return dict(state="BLOCKED", code="GROWTH_J2_NOT_FROZEN", marker_created=False,
                ssh_requests=0, business_cases=0,
                missing=["fixed guest quiescence/autostart and durable-evidence inventory",
                         "live pidfd/image-writer binding and two-phase dispatcher",
                         "complete narrow/native verification and exact private manifest"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.parse_args()
    print(canonical(field_readiness()).decode("ascii"), end="")
    return 3


if __name__ == "__main__":
    sys.exit(main())
