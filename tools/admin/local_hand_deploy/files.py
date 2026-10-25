"""Bounded, restartable file actions for the administrator deployment coordinator.

This adapter never stores coordinator state.  Persist the returned prepared action
as an intent *before* calling execute_file.  The protected, cooperative single
writer contract is required: rename is not a filesystem compare-and-swap.

Identity is an ordinary Linux file handle plus f_fsid, not st_dev/st_ino or a
content-only claim.  The deployment support profile must independently validate
that these bindings survive a normal restart on the selected filesystem.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import ctypes
from dataclasses import asdict, dataclass
import errno
import hashlib
import os
from pathlib import Path
import re
import stat
import uuid


class FileError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FileLimits:
    max_files: int = 64
    max_file_bytes: int = 4 * 1024 * 1024
    max_total_bytes: int = 64 * 1024 * 1024
    max_preparation_files: int = 16
    max_directory_entries: int = 4096

    def __post_init__(self):
        for value in asdict(self).values():
            if type(value) is not int or value <= 0:
                raise FileError("INVALID_SPEC", "File limits must be positive integers")


_NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
_HANDLE_MAX = 128
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")


class _FileHandle(ctypes.Structure):
    _fields_ = [("handle_bytes", ctypes.c_uint), ("handle_type", ctypes.c_int),
                ("handle", ctypes.c_ubyte * _HANDLE_MAX)]


def _binding(fd: int) -> dict:
    """AT_EMPTY_PATH binds the already opened object, never a second path lookup."""
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "name_to_handle_at", None)
    if function is None:
        raise FileError("UNSUPPORTED", "Persistent Linux file handles are unavailable")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(_FileHandle),
                         ctypes.POINTER(ctypes.c_int), ctypes.c_int]
    function.restype = ctypes.c_int
    handle = _FileHandle()
    handle.handle_bytes = _HANDLE_MAX
    mount_id = ctypes.c_int()
    if function(fd, b"", ctypes.byref(handle), ctypes.byref(mount_id), 0x1000):
        value = ctypes.get_errno()
        if value in (errno.EOPNOTSUPP, errno.ENOSYS, errno.EINVAL, errno.EOVERFLOW):
            raise FileError("UNSUPPORTED", "Target filesystem has no supported persistent file handle")
        raise OSError(value, "Cannot obtain persistent file handle")
    fsid = os.fstatvfs(fd).f_fsid
    if type(fsid) is not int or fsid <= 0 or not 0 < handle.handle_bytes <= _HANDLE_MAX:
        raise FileError("UNSUPPORTED", "A nonzero persistent filesystem identity is required")
    return {"filesystem_id": fsid, "handle_type": handle.handle_type,
            "handle": bytes(handle.handle[:handle.handle_bytes]).hex()}


def _path(value: str | os.PathLike) -> Path:
    raw = os.fspath(value)
    if not isinstance(raw, str) or "\x00" in raw:
        raise FileError("INVALID_SPEC", "A filesystem path must be text")
    path = Path(raw)
    if not path.is_absolute() or ".." in path.parts or path == Path("/"):
        raise FileError("INVALID_SPEC", "An absolute, non-root path without traversal is required")
    return path


def _trusted_uid(uid: int, owner_uid: int):
    if uid not in (0, owner_uid):
        raise FileError("CONFLICT", "An object is owned by an untrusted account")


@contextmanager
def _directory(path: Path, owner_uid: int, *, private: bool = False):
    """Walk without symlinks and retain the final directory descriptor.

    The final protected directory is the authority boundary.  Ancestor renames
    cannot redirect an operation through this retained fd; reacquisition checks
    its persistent binding.  Protocol-external concurrent admin writes are not
    supported, as specified by the deployment contract.
    """
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | _NOFOLLOW)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | _NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        _trusted_uid(info.st_uid, owner_uid)
        forbidden = 0o077 if private else 0o022
        if info.st_mode & forbidden:
            raise FileError("CONFLICT", "The containing directory is not protected")
        yield fd
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise FileError("CONFLICT", "A deployment directory contains a link or non-directory") from error
        raise
    finally:
        os.close(fd)


def _directory_snapshot(fd: int) -> dict:
    info = os.fstat(fd)
    return {"binding": _binding(fd), "mode": stat.S_IMODE(info.st_mode),
            "uid": info.st_uid, "gid": info.st_gid}


def _read_fd(fd: int, maximum: int, owner_uid: int) -> tuple[dict, bytes]:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise FileError("CONFLICT", "Only regular, single-link files are supported")
    if stat.S_IMODE(before.st_mode) > 0o777:
        raise FileError("UNSUPPORTED", "Special file mode bits are outside the deployment profile")
    _trusted_uid(before.st_uid, owner_uid)
    if before.st_mode & 0o022:
        raise FileError("CONFLICT", "A file allows writes outside its owner")
    if before.st_size > maximum:
        raise FileError("LIMIT_EXCEEDED", "File exceeds its remaining byte budget")
    identity = _binding(fd)
    chunks = []
    remaining = maximum
    while remaining:
        part = os.read(fd, min(remaining, 128 * 1024))
        if not part:
            break
        chunks.append(part)
        remaining -= len(part)
    # A zero-byte-budget read never consumes data; the preceding size check is
    # the admission boundary.  Detect growth without reading an excess byte.
    after = os.fstat(fd)
    stable = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mode,
                           item.st_uid, item.st_gid, item.st_nlink,
                           item.st_mtime_ns, item.st_ctime_ns)
    data = b"".join(chunks)
    if stable(before) != stable(after) or len(data) != before.st_size:
        raise FileError("CONFLICT", "File changed during its bounded read")
    return {"exists": True, "binding": identity, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "mode": stat.S_IMODE(before.st_mode), "uid": before.st_uid,
            "gid": before.st_gid}, data


def _read_at(directory_fd: int, name: str, maximum: int,
             owner_uid: int, *, missing: bool = False) -> tuple[dict, bytes | None]:
    try:
        fd = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=directory_fd)
    except FileNotFoundError:
        if missing:
            return {"exists": False}, None
        raise FileError("CONFLICT", "A required file is missing") from None
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise FileError("CONFLICT", "Links are not supported deployment files") from None
        raise
    try:
        return _read_fd(fd, maximum, owner_uid)
    finally:
        os.close(fd)


def _read_path(path: Path, maximum: int, owner_uid: int) -> tuple[dict, bytes]:
    with _directory(path.parent, owner_uid) as parent:
        return _read_at(parent, path.name, maximum, owner_uid)


def _value(snapshot: dict) -> dict:
    return {key: value for key, value in snapshot.items() if key != "binding"}


def plan_files(specs, *, limits: FileLimits | None = None,
               owner_uid: int | None = None) -> dict:
    """Read-only plan.  Byte budget includes backups and recovery staging reserve.

    Each spec is {target, source, mode?, uid?, gid?} or {target, remove: True}.
    Both paths must be absolute;
    target parents already exist.  Symlinks, hardlinks and conflicting aliases are
    rejected.  Source metadata and digest are rechecked during preparation.
    """
    limits = limits or FileLimits()
    owner_uid = os.geteuid() if owner_uid is None else owner_uid
    if type(owner_uid) is not int or owner_uid < 0:
        raise FileError("INVALID_SPEC", "Invalid trusted owner")
    if not isinstance(specs, (list, tuple)) or len(specs) > limits.max_files:
        raise FileError("LIMIT_EXCEEDED", "Too many planned files")
    entries, targets, identities = [], set(), set()
    remaining = limits.max_total_bytes
    for spec in specs:
        removing = isinstance(spec, dict) and spec.get("remove") is True
        if not isinstance(spec, dict) or (set(spec) != {"target", "remove"} if removing else
                not {"target", "source"} <= spec.keys() or spec.keys() - {"target", "source", "mode", "uid", "gid"}):
            raise FileError("INVALID_SPEC", "Invalid file specification")
        target = _path(spec["target"])
        source = None if removing else _path(spec["source"])
        if str(target) in targets:
            raise FileError("INVALID_SPEC", "Duplicate deployment target")
        targets.add(str(target))
        with _directory(target.parent, owner_uid) as parent:
            directory = _directory_snapshot(parent)
            original, _ = _read_at(parent, target.name,
                                   min(limits.max_file_bytes, remaining), owner_uid, missing=True)
        identity = (str(directory["binding"]), target.name)
        if identity in identities:
            raise FileError("INVALID_SPEC", "Two target paths alias the same object")
        identities.add(identity)
        original_size = original.get("size", 0)
        candidate = {"exists": False, "size": 0} if removing else _read_path(source, min(
            limits.max_file_bytes, remaining - original_size), owner_uid)[0]
        attributes = {"mode": spec.get("mode", candidate.get("mode", 0o600)),
                      "uid": spec.get("uid", original.get("uid", owner_uid)),
                      "gid": spec.get("gid", original.get("gid", os.getegid()))}
        if (any(type(value) is not int or value < 0 for value in attributes.values())
                or attributes["mode"] > 0o777 or attributes["mode"] & 0o022
                or not attributes["mode"] & 0o400):
            raise FileError("INVALID_SPEC", "Unsupported file attributes")
        _trusted_uid(attributes["uid"], owner_uid)
        # Reserve one original backup, one publication and one recovery/failure
        # staging object.  Enumeration also counts failed preparatory objects.
        reservation = original_size + 2 * max(original_size, candidate["size"])
        if reservation > remaining:
            raise FileError("LIMIT_EXCEEDED", "Insufficient preparation and recovery byte budget")
        remaining -= reservation
        entries.append({"schema": "lh-deploy-file-plan-v1", "target": str(target),
                        "parent": directory, "original": original,
                        "source": None if removing else {"path": str(source), "snapshot": candidate},
                        "attributes": attributes, "owner_uid": owner_uid,
                        "limits": asdict(limits), "preparation_budget_bytes": reservation})
    # Distribute the explicit remaining budget; retries cannot silently grow it.
    for index, entry in enumerate(entries):
        entry["preparation_budget_bytes"] += remaining // len(entries) + (index < remaining % len(entries))
    return {"schema": "lh-deploy-files-plan-v1", "files": entries,
            "limits": asdict(limits), "reserved_bytes": limits.max_total_bytes - remaining}


def _lock_binding(lock_fd: int) -> dict:
    if type(lock_fd) is not int or lock_fd < 0:
        raise FileError("LOCK_REQUIRED", "An inherited deployment lock descriptor is required")
    try:
        info = os.fstat(lock_fd)
        with open(f"/proc/self/fdinfo/{lock_fd}", "rb") as stream:
            data = stream.read(16385)
    except OSError as error:
        raise FileError("LOCK_REQUIRED", "Deployment lock is unavailable") from error
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o022
            or info.st_uid not in (0, os.geteuid())
            or len(data) > 16384
            or not any(re.search(rb"\bFLOCK\s+ADVISORY\s+WRITE\b", line)
                       for line in data.splitlines() if line.startswith(b"lock:"))):
        raise FileError("LOCK_REQUIRED", "Descriptor does not hold an exclusive flock")
    return _binding(lock_fd)


def _namespace(operation_id: str, attempt_id: str, target: Path) -> str:
    if any(not isinstance(value, str) or _ID.fullmatch(value) is None
           for value in (operation_id, attempt_id)):
        raise FileError("INVALID_SPEC", "Invalid operation or attempt identifier")
    # All attempts of a step share the namespace, so failed files count against
    # the same budget.  The step's staging_dir is supplied by the coordinator.
    digest = hashlib.sha256((operation_id + "\0" + str(target)).encode()).hexdigest()[:24]
    return ".lh-deploy-" + digest + "-"


def _usage(directory_fd: int, prefixes: tuple[str, ...] | None, limits: FileLimits) -> tuple[int, int]:
    count = total = 0
    with os.scandir(directory_fd) as entries:
        for index, entry in enumerate(entries):
            if index >= limits.max_directory_entries:
                raise FileError("LIMIT_EXCEEDED", "Directory enumeration budget exceeded")
            if prefixes is not None and not entry.name.startswith(prefixes):
                continue
            info = entry.stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise FileError("CONFLICT", "Unexpected preparation object")
            count += 1
            total += info.st_size
    return count, total


def _reserve_creation(state_fds: list[int], parent_fd: int, prefixes: tuple[str, ...],
                      size: int, limits: FileLimits, byte_budget: int):
    states = state_bytes = 0
    seen = set()
    for fd in state_fds:
        identity = repr(_binding(fd))
        if identity in seen:
            continue
        seen.add(identity)
        count, total = _usage(fd, None, limits)
        states += count
        state_bytes += total
    targets, target_bytes = _usage(parent_fd, prefixes, limits)
    if states + targets >= limits.max_preparation_files or state_bytes + target_bytes + size > byte_budget:
        raise FileError("LIMIT_EXCEEDED", "Preparation retention budget exhausted")


def _write_new(directory_fd: int, name: str, data: bytes, attributes: dict,
               owner_uid: int) -> dict:
    fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                 0o600, dir_fd=directory_fd)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError(errno.EIO, "Short preparation write")
            view = view[written:]
        current = os.fstat(fd)
        if (current.st_uid, current.st_gid) != (attributes["uid"], attributes["gid"]):
            os.fchown(fd, attributes["uid"], attributes["gid"])
        os.fchmod(fd, attributes["mode"])
        os.fsync(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        snapshot, actual = _read_fd(fd, len(data), owner_uid)
        if actual != data:
            raise FileError("CONFLICT", "Preparation readback failed")
        os.fsync(directory_fd)
        return snapshot
    finally:
        os.close(fd)


@contextmanager
def _state_directory(path: Path, owner_uid: int):
    # The coordinator creates this protected step directory before preparation.
    # Do not catch body exceptions here: a missing member is not a missing root.
    with _directory(path, owner_uid, private=True) as fd:
        yield fd


def _matching(actual: dict, expected: dict):
    if actual != expected:
        raise FileError("CONFLICT", "An object no longer matches its recorded identity and value")


def preparation_objects(action: dict) -> list[dict]:
    """Bind retained same-directory preparation files, with bounded enumeration.

    This inventory does not exempt names from configuration checks. A reload
    consumer must persist the exact returned objects and recheck their handles.
    Already moved candidates need not still exist at their former staging path.
    """
    _validate_action(action)
    target, owner = _path(action["target"]), action["owner_uid"]
    limits = FileLimits(**action["limits"])
    known = {item["path"]: item["snapshot"] for item in action.get("retained_objects", [])}
    result, total = [], 0
    with _directory(target.parent, owner) as parent:
        _matching(_directory_snapshot(parent), action["parent"])
        with os.scandir(parent) as entries:
            for index, entry in enumerate(entries):
                if index >= limits.max_directory_entries:
                    raise FileError("LIMIT_EXCEEDED", "Preparation inventory enumeration exceeded its bound")
                if not entry.name.startswith(tuple(action["retained_namespaces"])):
                    continue
                if len(result) >= limits.max_preparation_files:
                    raise FileError("LIMIT_EXCEEDED", "Preparation inventory count exceeded its bound")
                snapshot, _ = _read_at(parent, entry.name, min(limits.max_file_bytes,
                    action["preparation_budget_bytes"] - total), owner)
                path = str(target.parent / entry.name)
                if path in known:
                    _matching(snapshot, known[path])
                total += snapshot["size"]
                result.append({"path": path, "snapshot": snapshot})
    return sorted(result, key=lambda item: item["path"])


def verify_preparation_objects(objects: list[dict], *, owner_uid: int,
                               limits: FileLimits | None = None):
    """Recheck exact retained objects; a same-byte replacement is a conflict."""
    limits = limits or FileLimits()
    if len(objects) > limits.max_files * limits.max_preparation_files:
        raise FileError("LIMIT_EXCEEDED", "Retained reload inventory exceeds its count budget")
    remaining = limits.max_total_bytes
    for item in objects:
        snapshot, _ = _read_path(_path(item["path"]), min(limits.max_file_bytes, remaining), owner_uid)
        _matching(snapshot, item["snapshot"])
        remaining -= snapshot["size"]


def _retain_objects(action):
    action["retained_objects"] = preparation_objects(action)
    return action


def prepare_file(entry: dict, staging_dir, *, operation_id: str,
                 attempt_id: str, lock_fd: int) -> dict:
    """Prepare durable backup and same-directory candidate, without publishing.

    The coordinator provides a private directory dedicated to this step.  A
    failed partial object is retained and counted; complete backups can be reused
    after full bounded readback.  Fresh candidate names avoid adopting or
    overwriting an unrecorded publication object.
    """
    if entry.get("schema") != "lh-deploy-file-plan-v1":
        raise FileError("INVALID_SPEC", "Invalid file plan schema")
    limits = FileLimits(**entry["limits"])
    target, state = _path(entry["target"]), _path(staging_dir)
    if state == target.parent:
        raise FileError("INVALID_SPEC", "Step staging must be separate from the target directory")
    owner = entry["owner_uid"]
    lock = _lock_binding(lock_fd)
    namespace = _namespace(operation_id, attempt_id, target)
    if entry["source"] is None:
        candidate, data = {"exists": False}, b""
    else:
        candidate, data = _read_path(_path(entry["source"]["path"]), limits.max_file_bytes, owner)
        _matching(candidate, entry["source"]["snapshot"])
    with _directory(target.parent, owner) as parent, _state_directory(state, owner) as state_fd:
        _matching(_directory_snapshot(parent), entry["parent"])
        original, old_bytes = _read_at(parent, target.name, limits.max_file_bytes, owner, missing=True)
        _matching(original, entry["original"])
        expected_value = dict(_value(candidate), **entry["attributes"]) if candidate["exists"] else candidate
        action = {"schema": "lh-deploy-file-action-v1", "action": "noop",
                  "target": str(target), "parent": entry["parent"], "expected": original,
                  "desired": original, "original": original, "backup": None, "staged": None,
                  "operation_id": operation_id, "attempt_id": attempt_id, "lock_binding": lock,
                  "owner_uid": owner, "limits": entry["limits"], "stage_dir": str(state),
                  "namespace": namespace, "preparation_budget_bytes": entry["preparation_budget_bytes"],
                  "preparation_reservations": {namespace: entry["preparation_budget_bytes"]},
                  "retained_state_dirs": [str(state)], "retained_namespaces": [namespace]}
        if _value(original) == expected_value:
            return _retain_objects(action)
        if original["exists"]:
            name = "original-" + hashlib.sha256(str(target).encode()).hexdigest()[:24]
            backup, backup_bytes = _read_at(state_fd, name, limits.max_file_bytes, owner, missing=True)
            if not backup["exists"]:
                _reserve_creation([state_fd], parent, (namespace,), len(old_bytes), limits,
                                  entry["preparation_budget_bytes"])
                # Write under a unique incomplete name.  If interrupted, preserve
                # it and create a fresh object next time; never truncate evidence.
                temporary = "incomplete-" + uuid.uuid4().hex
                backup = _write_new(state_fd, temporary, old_bytes,
                                    {"mode": 0o600, "uid": os.geteuid(), "gid": os.getegid()}, owner)
                os.rename(temporary, name, src_dir_fd=state_fd, dst_dir_fd=state_fd)
                os.fsync(state_fd)
                backup_bytes = old_bytes
            if (backup_bytes != old_bytes or backup["mode"] != 0o600
                    or backup["uid"] != os.geteuid()):
                raise FileError("CONFLICT", "Existing backup is not complete and protected")
            # A preceding preparation can have renamed this complete backup but
            # lost its directory-sync result.  Readback alone is not durability.
            backup_fd = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=state_fd)
            try:
                snapshot, _ = _read_fd(backup_fd, limits.max_file_bytes, owner)
                _matching(snapshot, backup)
                os.fsync(backup_fd)
            finally:
                os.close(backup_fd)
            os.fsync(state_fd)
            action["backup"] = {"path": str(state / name), "snapshot": backup}
        if not candidate["exists"]:
            return _retain_objects(dict(action, action="delete", desired={"exists": False}))
        _reserve_creation([state_fd], parent, (namespace,), len(data), limits,
                          entry["preparation_budget_bytes"])
        name = namespace + uuid.uuid4().hex
        candidate = _write_new(parent, name, data, entry["attributes"], owner)
        action.update(action="replace", desired=candidate,
                      staged={"path": str(target.parent / name), "snapshot": candidate})
        return _retain_objects(action)


def _validate_action(action: dict):
    if not isinstance(action, dict) or action.get("schema") != "lh-deploy-file-action-v1" or (
            action.get("action") not in ("replace", "delete", "noop")):
        raise FileError("INVALID_SPEC", "Invalid file action")
    target = _path(action["target"])
    FileLimits(**action["limits"])
    _path(action["stage_dir"])
    reservations = action.get("preparation_reservations")
    if (not isinstance(reservations, dict) or not reservations
            or len(reservations) > action["limits"]["max_preparation_files"]
            or any(not isinstance(key, str) or type(value) is not int or value < 0 for key, value in reservations.items())
            or sum(reservations.values()) != action["preparation_budget_bytes"]):
        raise FileError("INVALID_SPEC", "Preparation reservations do not match their exact byte budget")
    if action["namespace"] != _namespace(action["operation_id"], action["attempt_id"], target):
        raise FileError("INVALID_SPEC", "Invalid preparation namespace")
    if (not isinstance(action["retained_state_dirs"], list)
            or not isinstance(action["retained_namespaces"], list)
            or len(action["retained_state_dirs"]) > action["limits"]["max_preparation_files"]
            or len(action["retained_namespaces"]) > action["limits"]["max_preparation_files"]
            or action["stage_dir"] not in action["retained_state_dirs"]
            or action["namespace"] not in action["retained_namespaces"]):
        raise FileError("INVALID_SPEC", "Invalid retained preparation scope")
    if action["action"] == "replace":
        staged = action["staged"]
        path = _path(staged["path"])
        if (path.parent != target.parent or not path.name.startswith(action["namespace"])
                or staged["snapshot"] != action["desired"]):
            raise FileError("INVALID_SPEC", "Publication staging binding is invalid")
    if action["action"] == "delete" and action["desired"] != {"exists": False}:
        raise FileError("INVALID_SPEC", "Deletion target must be absence")


def observe_file(action: dict) -> dict:
    """Read-only observation: target, original, or conflict (including missing).

    A restored original file is a *new* object: observe its saved restore action,
    not the old publication action.  A delete target that is already absent is
    satisfied_observed, not a claim about who deleted it.
    """
    _validate_action(action)
    target, owner = _path(action["target"]), action["owner_uid"]
    try:
        with _directory(target.parent, owner) as parent:
            directory = _directory_snapshot(parent)
            _matching(directory, action["parent"])
            actual, _ = _read_at(parent, target.name,
                                 action["limits"]["max_file_bytes"], owner, missing=True)
        if actual == action["desired"]:
            return {"state": "target", "actual": actual,
                    "proof": ("original_identity" if action["action"] == "noop" else
                              "published_identity" if actual["exists"] else "satisfied_observed")}
        if actual == action["expected"]:
            return {"state": "original", "actual": actual, "proof": "original_identity"}
        return {"state": "conflict", "actual": actual, "reason": "identity_or_value_changed"}
    except FileError as error:
        if error.code == "CONFLICT":
            return {"state": "conflict", "reason": str(error)}
        raise


def execute_file(action: dict, *, lock_fd: int) -> dict:
    """Execute only after the caller durably saved this exact action as intent.

    Existing target identity means rename/unlink already happened.  Only pending
    synchronization and observation are repeated, never the publication itself.
    """
    _validate_action(action)
    _matching(_lock_binding(lock_fd), action["lock_binding"])
    target, owner = _path(action["target"]), action["owner_uid"]
    maximum = action["limits"]["max_file_bytes"]
    with _directory(target.parent, owner) as parent:
        _matching(_directory_snapshot(parent), action["parent"])
        actual, _ = _read_at(parent, target.name, maximum, owner, missing=True)
        if actual == action["desired"]:
            changed = False
        elif actual != action["expected"]:
            raise FileError("CONFLICT", "Target changed independently; refusing publication")
        elif action["action"] == "replace":
            staged = _path(action["staged"]["path"])
            snapshot, _ = _read_at(parent, staged.name, maximum, owner)
            _matching(snapshot, action["desired"])
            os.rename(staged.name, target.name, src_dir_fd=parent, dst_dir_fd=parent)
            changed = True
        elif action["action"] == "delete":
            os.unlink(target.name, dir_fd=parent)
            changed = True
        else:
            raise FileError("CONFLICT", "A no-change action no longer matches")
        if action["desired"]["exists"]:
            fd = os.open(target.name, os.O_RDONLY | _NOFOLLOW, dir_fd=parent)
            try:
                snapshot, _ = _read_fd(fd, maximum, owner)
                _matching(snapshot, action["desired"])
                if action["action"] != "noop":
                    os.fsync(fd)
            finally:
                os.close(fd)
        if action["action"] != "noop":
            os.fsync(parent)
    observed = observe_file(action)
    if observed["state"] != "target":
        raise FileError("CONFLICT", "Publication postcondition is not established")
    return dict(observed, changed=changed, synced=True)


def prepare_restore(published: dict, staging_dir, *, operation_id: str,
                    attempt_id: str, lock_fd: int, baseline: dict | None = None) -> dict:
    """Create a separate compensating action; the caller persists its own intent.

    If a restore action already exists in the store, observe/execute that action
    instead.  A new handle from an earlier restore is deliberately not adopted
    by content resemblance through this original-publication interface. A linked
    recovery may supply its earliest prepared baseline; current identity still
    comes exclusively from the latest saved publication/compensation action.
    """
    _validate_action(published)
    baseline = published if baseline is None else baseline
    _validate_action(baseline)
    for key in ("target", "parent", "owner_uid", "limits", "lock_binding"):
        _matching(published[key], baseline[key])
    lock = _lock_binding(lock_fd)
    _matching(lock, published["lock_binding"])
    observed = observe_file(published)
    if observed["state"] == "conflict":
        raise FileError("CONFLICT", "Published file changed independently; cannot restore")
    target, state = _path(published["target"]), _path(staging_dir)
    owner, limits = published["owner_uid"], FileLimits(**published["limits"])
    namespace = _namespace(operation_id, attempt_id, target)
    action = dict(published, expected=observed["actual"], desired=observed["actual"],
                  action="noop", operation_id=operation_id, attempt_id=attempt_id,
                  namespace=namespace, staged=None, stage_dir=str(state), lock_binding=lock,
                  original=baseline["original"], backup=baseline["backup"],
                  retained_state_dirs=list(dict.fromkeys(published["retained_state_dirs"] + [str(state)])),
                  retained_namespaces=list(dict.fromkeys(published["retained_namespaces"] + [namespace])))
    _validate_action(action)
    original = baseline["original"]
    actual = observed["actual"]
    fields = ("exists", "size", "sha256", "mode", "uid", "gid")
    if all(actual.get(key) == original.get(key) for key in fields):
        return _retain_objects(action)
    if not original["exists"]:
        return _retain_objects(dict(action, action="delete", desired={"exists": False}))
    backup = baseline["backup"]
    path = _path(backup["path"])
    if path.parent != _path(baseline["stage_dir"]):
        raise FileError("INVALID_SPEC", "Backup is outside the protected step directory")
    with _state_directory(path.parent, owner) as backup_parent:
        snapshot, data = _read_at(backup_parent, path.name, limits.max_file_bytes, owner)
    _matching(snapshot, backup["snapshot"])
    if snapshot["size"] != original["size"] or snapshot["sha256"] != original["sha256"]:
        raise FileError("CONFLICT", "Backup does not match the original file")
    with ExitStack() as stack:
        parent = stack.enter_context(_directory(target.parent, owner))
        state_fds = [stack.enter_context(_state_directory(_path(path), owner))
                     for path in action["retained_state_dirs"]]
        _matching(_directory_snapshot(parent), published["parent"])
        current, _ = _read_at(parent, target.name, limits.max_file_bytes, owner, missing=True)
        _matching(current, observed["actual"])
        _reserve_creation(state_fds, parent, tuple(action["retained_namespaces"]), len(data), limits,
                          published["preparation_budget_bytes"])
        name = namespace + uuid.uuid4().hex
        restored = _write_new(parent, name, data,
                              {key: original[key] for key in ("mode", "uid", "gid")}, owner)
        return _retain_objects(dict(action, action="replace", desired=restored,
                    staged={"path": str(target.parent / name), "snapshot": restored}))
