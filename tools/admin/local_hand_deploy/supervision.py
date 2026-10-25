"""One-shot, lock-inheriting supervision for fixed deployment adapters.

The child executes Python adapter operations, not an arbitrary command line.
systemd jobs / Docker requests remain external effects and must additionally be
reconciled by their adapter; a dead caller alone is never their completion proof.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import time


class AdapterError(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def boot_id():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def process_identity(pid):
    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text()
    except FileNotFoundError:
        return None
    fields = raw[raw.rindex(")") + 2:].split()
    return {"pid": int(pid), "start": int(fields[19]), "state": fields[0], "boot": boot_id()}


def verify_lock(fd, expected=None):
    """Check the same inode and a conflicting independent flock description.

    Never LOCK_UN this inherited open file description, even on an exception.
    """
    value = os.fstat(fd)
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise AdapterError("NODE_LOCK_NOT_REGULAR")
    identity = {"dev": value.st_dev, "ino": value.st_ino}
    if expected is not None and identity != expected:
        raise AdapterError("NODE_LOCK_CHANGED")
    fdinfo = Path(f"/proc/self/fdinfo/{fd}").read_text()
    if not any(line.startswith("lock:") and " FLOCK " in line and " WRITE " in line
               and line.rstrip().endswith(" 0 EOF") for line in fdinfo.splitlines()):
        raise AdapterError("NODE_LOCK_DESCRIPTION_NOT_HELD")
    probe = os.open(f"/proc/self/fd/{fd}", os.O_RDWR | os.O_CLOEXEC)
    try:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return identity
        raise AdapterError("NODE_LOCK_NOT_HELD")
    finally:
        os.close(probe)


def _read_json(path, maximum):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum or info.st_nlink != 1:
            raise AdapterError("SUPERVISION_RECORD_BOUND")
        value = os.read(fd, maximum + 1)
        if len(value) > maximum:
            raise AdapterError("SUPERVISION_RECORD_BOUND")
        return json.loads(value)
    finally:
        os.close(fd)


def _write_once(path, value, maximum):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(payload) > maximum:
        raise AdapterError("SUPERVISION_RECORD_BOUND")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if not written:
                raise OSError("short record write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


class SupervisedRunner:
    """Runs a trusted fixed adapter operation in a bounded forked child.

    The coordinator must be single threaded when dispatching. The child inherits
    the flock at fork (there is no launch-to-registration gap), persists its boot
    and start identity before calling the adapter, and never launches subprocesses.
    Parent timeouts leave the original attempt observable, never imply retry.
    """
    def __init__(self, state_dir, *, timeout=30.0, output_limit=65536, create=True):
        self.state_dir = Path(state_dir)
        self.timeout = float(timeout)
        self.output_limit = int(output_limit)
        self._children = {}
        self.create = bool(create)
        if not 0.05 <= self.timeout <= 600 or not 1024 <= self.output_limit <= 1048576:
            raise AdapterError("SUPERVISION_BOUND")
        if create:
            self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            info = self.state_dir.lstat()
        except FileNotFoundError:
            if not create:
                return
            raise
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise AdapterError("SUPERVISION_DIRECTORY_NOT_PRIVATE")

    def ensure_directory(self):
        """Explicitly enter the mutation path after a read-only observation."""
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.state_dir.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise AdapterError("SUPERVISION_DIRECTORY_NOT_PRIVATE")
        self.create = True

    def _directory(self, attempt_id):
        if not isinstance(attempt_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", attempt_id):
            raise AdapterError("ATTEMPT_ID")
        return self.state_dir / attempt_id

    def observe(self, binding, *, lock_fd=None):
        directory = self._directory(binding["attempt_id"])
        result = None
        process = None
        for name in ("binding.json", "process.json", "result.json"):
            try:
                value = _read_json(directory / name, self.output_limit)
            except FileNotFoundError:
                continue
            if name == "binding.json" and value != binding:
                raise AdapterError("SUPERVISION_BINDING_CONFLICT")
            if name == "process.json":
                process = value
            if name == "result.json":
                result = value
        events = []
        for index in range(32):
            try:
                events.append(_read_json(directory / f"event-{index:02}.json", self.output_limit))
            except FileNotFoundError:
                break
        if process is None:
            # With the node lock acquired, an unrecorded child cannot still run:
            # every child inherits it, and its first action is process.json.
            child = self._children.get(binding["attempt_id"])
            current = process_identity(os.getpid())
            original = binding.get("coordinator")
            recovered = original is not None and (current["boot"], current["pid"], current["start"]) != (original["boot"], original["pid"], original["start"])
            closed = lock_fd is not None and recovered
            if child is not None:
                live = process_identity(child["pid"])
                closed = live is None or live["start"] != child["start"] or live["state"] == "Z"
            if closed:
                # The protected store binds the durable node lock across boots.
                # Filesystem device numbers are runtime identities, so compare
                # the original open-description identity only within that boot.
                verify_lock(lock_fd, binding["lock"] if binding["boot"] == boot_id() else None)
        elif process["boot"] != boot_id():
            closed = True
        else:
            live = process_identity(process["pid"])
            closed = live is None or live["start"] != process["start"] or live["state"] == "Z"
        return {"binding": binding, "closed": closed, "result": result, "events": events,
                "outcome": "returned" if result is not None and closed else "unknown" if closed else "running"}

    def run(self, action, perform, *, attempt_id, lock_fd, persist_intent, previous=None):
        """persist_intent(binding) must durably finish before the child exists.

        perform(action, emit) is an internal adapter function. It must implement
        finite direct calls and cannot fork, exec, shell out or delegate file writes.
        The callback is never selected from a user-supplied import/name/command.
        """
        if not self.create:
            raise AdapterError("READ_ONLY_SUPERVISOR")
        lock = verify_lock(lock_fd)
        directory = self._directory(attempt_id)
        binding = {"version": 1, "attempt_id": attempt_id, "action_digest": digest(action),
                   "boot": boot_id(), "lock": lock, "timeout": self.timeout,
                   "coordinator": process_identity(os.getpid()),
                   "result_directory": str(directory)}
        if previous is not None:
            old = previous.get("binding", previous)
            if any(old.get(key) != binding[key] for key in ("attempt_id", "action_digest", "lock", "result_directory")):
                raise AdapterError("ATTEMPT_BINDING_CONFLICT")
            return self.observe(old, lock_fd=lock_fd)
        if directory.exists():
            old = _read_json(directory / "binding.json", self.output_limit)
            if any(old.get(key) != binding[key] for key in ("attempt_id", "action_digest", "lock", "result_directory")):
                raise AdapterError("ATTEMPT_BINDING_CONFLICT")
            return self.observe(old, lock_fd=lock_fd)
        directory.mkdir(mode=0o700)
        _write_once(directory / "binding.json", binding, self.output_limit)
        persist_intent(binding)
        # Forking an active multithreaded coordinator is intentionally unsupported.
        if len(list(Path("/proc/self/task").iterdir())) != 1:
            raise AdapterError("SUPERVISOR_REQUIRES_SINGLE_THREAD_DISPATCH")
        pid = os.fork()
        if pid == 0:
            try:
                verify_lock(lock_fd, lock)
                process = process_identity(os.getpid())
                _write_once(directory / "process.json", process, self.output_limit)
                index = 0
                def emit(value):
                    nonlocal index
                    if index >= 32:
                        raise AdapterError("SUPERVISION_EVENT_BOUND")
                    _write_once(directory / f"event-{index:02}.json", value, self.output_limit)
                    index += 1
                def expired(signum, frame):
                    raise TimeoutError("ADAPTER_DEADLINE")
                signal.signal(signal.SIGALRM, expired)
                signal.setitimer(signal.ITIMER_REAL, self.timeout)
                try:
                    value = {"status": "returned", "value": perform(action, emit)}
                except BaseException as error:
                    value = {"status": "unknown", "error_type": type(error).__name__,
                             "error": str(error)[:512]}
                signal.setitimer(signal.ITIMER_REAL, 0)
                _write_once(directory / "result.json", value, self.output_limit)
            except BaseException:
                # A reporting failure leaves the intent and possible effect intact.
                os._exit(125)
            os._exit(0)
        self._children[attempt_id] = process_identity(pid) or {"pid": pid, "start": -1}
        deadline = time.monotonic() + self.timeout + 0.25
        while time.monotonic() < deadline:
            ended, _ = os.waitpid(pid, os.WNOHANG)
            if ended:
                return self.observe(binding, lock_fd=lock_fd)
            time.sleep(0.01)
        # This child performs direct APIs and is forbidden to spawn descendants.
        # Kill only this known unreaped child when its bounded cleanup stalls;
        # daemon-owned jobs are separately observed, never cancelled here.
        os.kill(pid, signal.SIGKILL)
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            ended, _ = os.waitpid(pid, os.WNOHANG)
            if ended:
                return self.observe(binding, lock_fd=lock_fd)
            time.sleep(0.01)
        # Uninterruptible I/O still holds the inherited lock. Do not unlock it or
        # infer that an external request was undone just because our wait ended.
        return self.observe(binding)
