"""Protected, pinned Q1 administrator inputs; never a client-path interface.

All filesystem operations here can block. Call them only in a separately
supervised preparation/query process, never in a listener's control thread.
The trust model excludes concurrent malicious administrator modification.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import errno
import hashlib
import json
import os
from pathlib import PurePosixPath
import stat

from .admission import (fields, integer, path, require, strict_json, token)
from .supervision import Binding, bind_query


MAX_RUNTIME_BYTES = 16384
MAX_FILE_BYTES = 64 * 1024 * 1024
PACKAGE_FILES = ("admission.py", "protected_inputs.py", "supervision.py")


@dataclass(frozen=True)
class RuntimeConfig:
    digest: str
    manifest_path: str
    manifest_digest: str
    python_path: str
    python_sha256: str
    worker_path: str
    worker_sha256: str
    native_path: str
    native_sha256: str
    systemd_run_path: str
    systemd_run_sha256: str
    systemctl_path: str
    systemctl_sha256: str
    package_files: tuple[tuple[str, str], ...]
    query_slice: str
    cgroup_parent_device: int
    cgroup_parent_inode: int
    initial_userns_device: int
    initial_userns_inode: int
    memory_bytes: int
    tasks_max: int
    cpu_seconds: int
    max_output_bytes: int


def decode_runtime(raw, expected_digest):
    token(expected_digest, r"[0-9a-f]{64}")
    require(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == expected_digest,
            "RUNTIME_DIGEST")
    value = fields(strict_json(raw, MAX_RUNTIME_BYTES), (
        "schema", "manifest_path", "manifest_digest", "python_path", "python_sha256",
        "worker_path", "worker_sha256", "native_path", "native_sha256", "systemd_run_path",
        "systemd_run_sha256", "systemctl_path", "systemctl_sha256", "package_files",
        "query_slice", "cgroup_parent_device", "cgroup_parent_inode", "initial_userns_device",
        "initial_userns_inode", "memory_bytes",
        "tasks_max", "cpu_seconds", "max_output_bytes"))
    require(value["schema"] == "local-hand-quota-runtime/v1", "RUNTIME_VERSION")
    files = fields(value["package_files"], PACKAGE_FILES)
    digests = tuple((name, token(files[name], r"[0-9a-f]{64}")) for name in PACKAGE_FILES)
    paths = tuple(path(value[key]) for key in ("manifest_path", "python_path", "worker_path", "native_path",
                                             "systemd_run_path", "systemctl_path"))
    require(len(set(paths)) == len(paths), "RUNTIME_PATH_ALIAS")
    require(PurePosixPath(paths[2]).name == "worker.py", "WORKER_NAME")
    require(PurePosixPath(paths[2]).parent != PurePosixPath("/"), "PACKAGE_ROOT")
    query_slice = token(value["query_slice"], r"lhq[a-z0-9]{1,40}\.slice")
    return RuntimeConfig(expected_digest, paths[0], token(value["manifest_digest"], r"[0-9a-f]{64}"),
                         paths[1], token(value["python_sha256"], r"[0-9a-f]{64}"),
                         paths[2], token(value["worker_sha256"], r"[0-9a-f]{64}"),
                         paths[3], token(value["native_sha256"], r"[0-9a-f]{64}"),
                         paths[4], token(value["systemd_run_sha256"], r"[0-9a-f]{64}"),
                         paths[5], token(value["systemctl_sha256"], r"[0-9a-f]{64}"), digests, query_slice,
                         integer(value["cgroup_parent_device"]), integer(value["cgroup_parent_inode"], 1),
                         integer(value["initial_userns_device"]), integer(value["initial_userns_inode"], 1),
                         integer(value["memory_bytes"], 16 * 1024**2, 1024**3),
                         integer(value["tasks_max"], 1, 8), integer(value["cpu_seconds"], 1, 30),
                         integer(value["max_output_bytes"], 8192, 32768))


def _protected(metadata, *, directory):
    require((stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode))
            and metadata.st_uid == 0 and metadata.st_mode & 0o022 == 0, "UNPROTECTED_INPUT")
    if not directory:
        require(metadata.st_nlink == 1 and metadata.st_mode & 0o6000 == 0, "INPUT_LINK_OR_SETID")


def open_protected(filename, *, directory=False):
    """Return an owned CLOEXEC FD; every ancestor is protected and no-follow."""
    path(filename)
    current = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        _protected(os.fstat(current), directory=True)
        parts = PurePosixPath(filename).parts[1:]
        for index, part in enumerate(parts):
            is_directory = directory or index < len(parts) - 1
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            if is_directory:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=current)
            try:
                _protected(os.fstat(child), directory=is_directory)
            except BaseException:
                try:
                    os.close(child)
                except OSError:
                    pass  # The original rejection remains authoritative; no retry.
                raise
            old, current = current, child
            os.close(old)
        return current
    except BaseException:
        retained, current = current, -1
        try:
            os.close(retained)
        except OSError:
            pass
        raise


def read_fd(fd, maximum):
    """One finite byte budget, retaining no more than maximum plus one bytes."""
    integer(maximum, 1, MAX_FILE_BYTES)
    result = bytearray()
    while len(result) <= maximum:
        data = os.read(fd, min(65536, maximum + 1 - len(result)))
        if not data:
            return bytes(result)
        result.extend(data)
    require(False, "INPUT_BYTE_LIMIT")


def file_identity(metadata):
    # Reading may change atime; inode/content metadata must remain stable.
    return tuple(getattr(metadata, name) for name in (
        "st_dev", "st_ino", "st_uid", "st_gid", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))


def read_protected(filename, maximum=MAX_RUNTIME_BYTES):
    fd = open_protected(filename)
    try:
        before = os.fstat(fd)
        require(before.st_size <= maximum, "INPUT_BYTE_LIMIT")
        raw = read_fd(fd, maximum)
        require(file_identity(os.fstat(fd)) == file_identity(before), "INPUT_CHANGED")
        return raw
    finally:
        os.close(fd)


def load_runtime(filename, expected_digest):
    return decode_runtime(read_protected(filename), expected_digest)


def verify_file(filename, digest, *, executable=False):
    """Return verified CLOEXEC FD for exec, or close after verifying a source."""
    token(digest, r"[0-9a-f]{64}")
    fd = open_protected(filename)
    try:
        before = os.fstat(fd)
        require(before.st_size <= MAX_FILE_BYTES, "INPUT_BYTE_LIMIT")
        raw = read_fd(fd, MAX_FILE_BYTES)
        require(hashlib.sha256(raw).hexdigest() == digest, "INSTALLATION_DIGEST")
        require(file_identity(os.fstat(fd)) == file_identity(before), "INPUT_CHANGED")
        if executable:
            require(before.st_mode & 0o111 and raw.startswith(b"\x7fELF"), "EXECUTABLE_FORMAT")
            try:
                os.getxattr(fd, "security.capability")
            except OSError as error:
                # Only a confirmed absent xattr proves this file-capability
                # precondition. Unsupported/error paths are not absence.
                require(error.errno == errno.ENODATA, "FILE_CAPABILITY_UNPROVEN")
            else:
                require(False, "FILE_CAPABILITY_PRESENT")
            return fd
        closing, fd = fd, -1
        os.close(closing)
        return None
    except BaseException:
        if fd >= 0:
            closing, fd = fd, -1
            try:
                os.close(closing)
            except OSError:
                pass
        raise


def installation_digest(config):
    """Bind the immutable installation without a manifest/config hash cycle."""
    require(type(config) is RuntimeConfig, "RUNTIME_REQUIRED")
    names = ("python_path", "python_sha256", "worker_path", "worker_sha256", "native_path",
             "native_sha256", "systemd_run_path", "systemd_run_sha256", "systemctl_path", "systemctl_sha256")
    value = {name: getattr(config, name) for name in names}
    value["package_files"] = dict(config.package_files)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_installation(config):
    # Pin these executables and Python modules, not the entire trusted OS:
    # interpreter stdlib, ELF loader and shared libraries require a separately
    # admitted host installation. File hashes alone do not prove that baseline.
    require(type(config) is RuntimeConfig, "RUNTIME_REQUIRED")
    for name, digest in config.package_files:
        verify_file(str(PurePosixPath(config.worker_path).parent / name), digest)
    verify_file(config.worker_path, config.worker_sha256)
    for filename, digest in ((config.systemd_run_path, config.systemd_run_sha256),
                             (config.systemctl_path, config.systemctl_sha256)):
        os.close(verify_file(filename, digest, executable=True))
    python_fd = verify_file(config.python_path, config.python_sha256, executable=True)
    try:
        # sys.executable is a string, /proc/self/exe identifies the running ELF.
        require(os.stat("/proc/self/exe")[:3] == os.fstat(python_fd)[:3], "PYTHON_IDENTITY")
    finally:
        os.close(python_fd)
    return verify_file(config.native_path, config.native_sha256, executable=True)


def encode_ticket(binding):
    require(type(binding) is Binding, "BINDING_REQUIRED")
    value = {"schema": "local-hand-quota-ticket/v1", "slot_ref": binding.slot.ref,
             "generation": binding.slot.generation, "request_id": binding.request_id,
             "allocation_digest": binding.allocation_digest, "execution_id": binding.execution_id,
             "phase": binding.phase, "issued_ns": binding.issued_ns, "deadline_ns": binding.deadline_ns}
    return base64.b64encode(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).decode("ascii")


def decode_ticket(encoded, manifest):
    token(encoded, r"[A-Za-z0-9+/]{1,10922}={0,2}")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError:
        require(False, "TICKET_BASE64")
    require(base64.b64encode(raw).decode("ascii") == encoded, "TICKET_CANONICAL")
    value = fields(strict_json(raw, 8192, depth=4), (
        "schema", "slot_ref", "generation", "request_id", "allocation_digest", "execution_id",
        "phase", "issued_ns", "deadline_ns"))
    require(value["schema"] == "local-hand-quota-ticket/v1", "TICKET_VERSION")
    binding = bind_query(manifest, slot_ref=value["slot_ref"], generation=value["generation"],
                         request_id=value["request_id"], allocation_digest=value["allocation_digest"],
                         execution_id=value["execution_id"], phase=value["phase"],
                         now_ns=value["issued_ns"], phase_deadline_ns=value["deadline_ns"])
    require(binding.deadline_ns == value["deadline_ns"], "TICKET_DEADLINE")
    return binding
