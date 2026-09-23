"""One query-unit worker. No installation, activation, quota setting or retry.

Invoke only as the pinned interpreter: ``python -I -B worker.py CONFIG SHA TICKET``.
Configuration/source reads and target-root opens happen inside this unit because
even reads may block. Successful READY is identity evidence, never an exit proof.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat
import sys
import time
import types


CAPABILITIES = 0x200004  # CAP_SYS_ADMIN and CAP_DAC_READ_SEARCH, no ambient caps.
MAX_READY_BYTES = 2048


def _bootstrap_read(filename, maximum):
    """Small independent loader: do not import unverified neighboring modules."""
    if (type(filename) is not str or not re.fullmatch(r"/[A-Za-z0-9_./-]{1,1023}", filename)
            or str(PurePosixPath(filename)) != filename or ".." in PurePosixPath(filename).parts
            or filename.startswith("//") or filename == "/"):
        raise ValueError("BOOTSTRAP_PATH")
    current = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        parts = PurePosixPath(filename).parts[1:]
        root = os.fstat(current)
        if root.st_uid != 0 or root.st_mode & 0o022:
            raise ValueError("BOOTSTRAP_PROTECTION")
        for index, part in enumerate(parts):
            directory = index < len(parts) - 1
            child = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
                            | (os.O_DIRECTORY if directory else 0), dir_fd=current)
            old, current = current, child
            os.close(old)
            metadata = os.fstat(current)
            valid_kind = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
            if (not valid_kind or metadata.st_uid != 0 or metadata.st_mode & 0o022
                    or (not directory and (metadata.st_nlink != 1 or metadata.st_mode & 0o6000))):
                raise ValueError("BOOTSTRAP_PROTECTION")
        if metadata.st_size > maximum:
            raise ValueError("BOOTSTRAP_SIZE")
        data = bytearray()
        while len(data) <= maximum:
            piece = os.read(current, min(65536, maximum + 1 - len(data)))
            if not piece:
                break
            data.extend(piece)
        after = os.fstat(current)
        for name in ("st_dev", "st_ino", "st_uid", "st_gid", "st_mode", "st_nlink",
                     "st_size", "st_mtime_ns", "st_ctime_ns"):
            if getattr(after, name) != getattr(metadata, name):
                raise ValueError("BOOTSTRAP_CHANGED")
        if len(data) > maximum:
            raise ValueError("BOOTSTRAP_SIZE")
        return bytes(data)
    finally:
        os.close(current)


def _bootstrap(config_path, digest):
    if not sys.flags.isolated or not sys.dont_write_bytecode:
        raise ValueError("ISOLATED_PYTHON_REQUIRED")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("BOOTSTRAP_DIGEST")
    raw = _bootstrap_read(config_path, 16384)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("BOOTSTRAP_DIGEST")

    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("BOOTSTRAP_DUPLICATE")
            result[key] = value
        return result

    value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=unique)
    if type(value) is not dict or value.get("worker_path") != os.path.abspath(__file__):
        raise ValueError("BOOTSTRAP_WORKER")
    actual_worker = _bootstrap_read(value["worker_path"], 512 * 1024)
    if hashlib.sha256(actual_worker).hexdigest() != value.get("worker_sha256"):
        raise ValueError("BOOTSTRAP_WORKER_DIGEST")
    names = ("admission.py", "supervision.py", "protected_inputs.py")
    file_map = value.get("package_files")
    if type(file_map) is not dict or set(file_map) != set(names):
        raise ValueError("BOOTSTRAP_MODULES")
    sources = {}
    for filename in names:
        source = _bootstrap_read(str(PurePosixPath(value["worker_path"]).parent / filename), 512 * 1024)
        if hashlib.sha256(source).hexdigest() != file_map[filename]:
            raise ValueError("BOOTSTRAP_MODULE_DIGEST")
        sources[filename] = source
    # No namespace search paths: execute only bytes that were just verified.
    namespace = "_local_hand_quota_pinned"
    package = types.ModuleType(namespace)
    package.__path__ = []
    sys.modules[namespace] = package
    for filename, source in sources.items():
        name = namespace + "." + filename[:-3]
        module = types.ModuleType(name)
        module.__package__ = namespace
        module.__file__ = str(PurePosixPath(value["worker_path"]).parent / filename)
        sys.modules[name] = module
        exec(compile(source, module.__file__, "exec"), module.__dict__)
    globals()["__package__"] = namespace


def _proc_bytes(filename, maximum=16384):
    from .protected_inputs import read_fd
    fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        return read_fd(fd, maximum)
    finally:
        os.close(fd)


def parse_status(raw):
    from .admission import require
    wanted = ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb", "NoNewPrivs")
    result = {}
    for line in raw.decode("ascii", "strict").splitlines():
        key, separator, value = line.partition(":")
        if key in wanted:
            require(separator and key not in result, "PROCESS_STATUS")
            value = value.strip()
            require(re.fullmatch(r"[0-9a-f]{16}" if key != "NoNewPrivs" else r"[01]", value),
                    "PROCESS_STATUS")
            result[key] = int(value, 16 if key != "NoNewPrivs" else 10)
    require(set(result) == set(wanted), "PROCESS_STATUS")
    require(result["NoNewPrivs"] == 1, "NO_NEW_PRIVS_REQUIRED")
    require(all(result[key] == CAPABILITIES for key in ("CapPrm", "CapEff", "CapBnd"))
            and result["CapInh"] == result["CapAmb"] == 0, "QUERY_CAPABILITIES")
    return result


def verify_process(config, binding):
    from .admission import require, token
    from .protected_inputs import open_protected
    require(os.getuid() == os.geteuid() == binding.manifest.query_uid == binding.manifest.query_euid == 0,
            "QUERY_UID")
    parse_status(_proc_bytes("/proc/self/status"))
    userns = os.stat("/proc/self/ns/user")
    require((userns.st_dev, userns.st_ino) == (config.initial_userns_device, config.initial_userns_inode),
            "INITIAL_USER_NAMESPACE_REQUIRED")
    require(_proc_bytes("/proc/sys/kernel/random/boot_id", 128).decode("ascii").strip()
            == binding.manifest.boot_id, "BOOT_CHANGED")
    invocation = token(os.environ.get("INVOCATION_ID"), r"[0-9a-f]{32}")
    require(binding.manifest.cgroup_parent == "/" + config.query_slice, "QUERY_SLICE")
    require(_proc_bytes("/proc/self/cgroup", 4096) == ("0::" + binding.cgroup + "\n").encode(),
            "QUERY_CGROUP")
    parent = open_protected("/sys/fs/cgroup" + binding.manifest.cgroup_parent, directory=True)
    try:
        observed = os.fstat(parent)
        require((observed.st_dev, observed.st_ino) == (config.cgroup_parent_device, config.cgroup_parent_inode),
                "CGROUP_PARENT_CHANGED")
    finally:
        os.close(parent)
    now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    require(binding.issued_ns <= now < binding.deadline_ns, "QUERY_DEADLINE")
    return invocation


def _mount_path(value):
    from .admission import require
    def replace(match):
        escapes = {"040": " ", "011": "\t", "012": "\n", "134": "\\"}
        require(match.group(1) in escapes, "MOUNTINFO_ESCAPE")
        return escapes[match.group(1)]
    require(re.search(r"\\(?![0-7]{3})", value) is None, "MOUNTINFO_ESCAPE")
    return re.sub(r"\\([0-7]{3})", replace, value)


def match_mount(fdinfo, mountinfo, slot):
    """Same-namespace mount ID binds FD to filesystem type and st_dev.

    filesystem_uuid remains a protected administrator assertion bound to st_dev;
    this does not independently query a superblock UUID or compare IDs across NS.
    """
    from .admission import require
    ids = re.findall(rb"^mnt_id:\s*([0-9]+)$", fdinfo, re.MULTILINE)
    require(len(ids) == 1 and int(ids[0]) > 0, "FD_MOUNT_ID")
    records = []
    for line in mountinfo.decode("utf-8", "strict").splitlines():
        fields = line.split(" ")
        require(len(fields) >= 10, "MOUNTINFO_FORMAT")
        require(fields[0].isdigit(), "MOUNTINFO_FORMAT")
        if int(fields[0]) != int(ids[0]):
            continue
        require(fields.count("-") == 1, "MOUNTINFO_FORMAT")
        split = fields.index("-")
        require(split >= 6 and len(fields) == split + 4, "MOUNTINFO_FORMAT")
        records.append(fields)
    require(len(records) == 1, "FD_MOUNT_UNRESOLVED")
    fields = records[0]
    split = fields.index("-")
    require(fields[split + 1] == slot.filesystem, "FILESYSTEM_CHANGED")
    require(fields[2] == f"{os.major(slot.root.device)}:{os.minor(slot.root.device)}", "MOUNT_DEVICE_CHANGED")
    root, point = _mount_path(fields[3]), _mount_path(fields[4])
    require(root.startswith("/") and point.startswith("/"), "MOUNTINFO_PATH")
    require(slot.path == point or point == "/" or slot.path.startswith(point + "/"), "MOUNT_PATH_CHANGED")
    require("rw" in fields[5].split(",") and "ro" not in fields[5].split(",")
            and "rw" in fields[split + 3].split(",") and "ro" not in fields[split + 3].split(","),
            "WRITABLE_QUOTA_FILESYSTEM_REQUIRED")


def open_slot(slot):
    from .admission import Root, require
    from .protected_inputs import open_protected
    parent_path = str(PurePosixPath(slot.path).parent)
    if parent_path == "/":
        parent = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        observed = os.fstat(parent)
        if observed.st_uid != 0 or observed.st_mode & 0o022:
            os.close(parent)
            require(False, "ROOT_PARENT_UNPROTECTED")
    else:
        parent = open_protected(parent_path, directory=True)
    root = None
    try:
        root = os.open(PurePosixPath(slot.path).name,
                       os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                       dir_fd=parent)
    finally:
        try:
            os.close(parent)
        except BaseException:
            if root is not None:
                try:
                    os.close(root)
                except OSError:
                    pass
            raise
    try:
        observed = os.fstat(root)
        require(Root(observed.st_dev, observed.st_ino, observed.st_uid, observed.st_gid, observed.st_mode)
                == slot.root, "ROOT_CHANGED")
        match_mount(_proc_bytes(f"/proc/self/fdinfo/{root}", 4096),
                    _proc_bytes("/proc/self/mountinfo", 1024 * 1024), slot)
        return root
    except BaseException:
        os.close(root)
        raise


def run(config_path, config_digest, ticket):
    from .admission import MAX_MANIFEST_BYTES, decode_manifest, require
    from .protected_inputs import (decode_ticket, installation_digest, load_runtime,
                                   read_protected, verify_installation)
    config = load_runtime(config_path, config_digest)
    manifest = decode_manifest(read_protected(config.manifest_path, MAX_MANIFEST_BYTES), config.manifest_digest)
    require(manifest.installation_digest == installation_digest(config), "INSTALLATION_BINDING")
    binding = decode_ticket(ticket, manifest)
    invocation = verify_process(config, binding)
    native = verify_installation(config)
    # Do not let dup2(root, 3) overwrite the verified executable FD.
    exec_fd = None
    try:
        try:
            exec_fd = fcntl.fcntl(native, fcntl.F_DUPFD_CLOEXEC, 10)
        finally:
            os.close(native)
    except BaseException:
        if exec_fd is not None:
            try:
                os.close(exec_fd)
            except OSError:
                pass
        raise
    root = None
    try:
        root = open_slot(binding.slot)
        # Recheck the deadline and process identity after all potentially blocking I/O.
        require(verify_process(config, binding) == invocation, "INVOCATION_CHANGED")
        ready = {"schema": "local-hand-quota-worker-ready/v1", "boot_id": manifest.boot_id,
                 "unit": binding.unit, "invocation_id": invocation, "cgroup": binding.cgroup,
                 "manifest_digest": manifest.digest, "runtime_digest": config.digest,
                 "request_id": binding.request_id}
        raw = (json.dumps(ready, sort_keys=True, separators=(",", ":")) + "\n").encode()
        require(len(raw) <= MAX_READY_BYTES, "READY_BYTE_LIMIT")
        # A full write is mandatory. Partial/EINTR output never starts quota.
        require(os.write(1, raw) == len(raw), "READY_WRITE")
        require(os.execve in os.supports_fd, "EXEC_FD_UNSUPPORTED")
        descriptors = os.listdir("/proc/self/fd")
        require(len(descriptors) <= 1024, "DESCRIPTOR_LIMIT")
        for value in descriptors:
            if value.isdecimal() and int(value) > 2 and int(value) != root:
                try:
                    os.set_inheritable(int(value), False)
                except OSError as error:
                    # listdir's temporary descriptor is already closed.
                    if error.errno != 9:
                        raise
        if root != 3:
            os.dup2(root, 3, inheritable=True)
            closing, root = root, 3
            os.close(closing)
        else:
            os.set_inheritable(root, True)
        require(binding.issued_ns <= time.clock_gettime_ns(time.CLOCK_BOOTTIME) < binding.deadline_ns,
                "QUERY_DEADLINE")
        # All other FDs created here are CLOEXEC. Native stdout/stderr are the
        # original unit pipes; there are no shell/environment command inputs.
        os.execve(exec_fd, [config.native_path], {"LANG": "C", "LC_ALL": "C"})
        require(False, "EXEC_RETURNED")
    finally:
        try:
            if root is not None:
                os.close(root)
        finally:
            os.close(exec_fd)


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    try:
        if len(arguments) != 3:
            raise ValueError("WORKER_ARGUMENTS")
        _bootstrap(arguments[0], arguments[1])
        run(*arguments)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RuntimeError, RecursionError):
        # No path, private object, environment value or exception repr is echoed.
        try:
            os.write(2, b"QUOTA_WORKER_REJECTED\n")
        except OSError:
            pass
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
