"""Bind one already-supervised controller incarnation, then exec its Q1 entry.

The external launch-input digest is the trust root; it pins installed source
bytes without a self-hash cycle. The outer administrator must pin the running
launcher/OS before Python starts. These checks cannot establish trust in already
executed code. No unit, ticket, deadline, journal or retry is created here.
Filesystem I/O and exec may block: existing independent supervision is required.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.machinery import EXTENSION_SUFFIXES
import json
import os
from pathlib import PurePosixPath
import stat
import sys

from .admission import decode_manifest, fields, integer, path, require, strict_json, token
from .controller_guard import SCHEMA, admit_controller, decode_controller
from .experiment import MAX_EXPERIMENT_BYTES, decode_experiment
from .protected_inputs import (decode_ticket, file_identity, installation_digest, load_runtime,
                               open_protected, read_fd, read_protected, validate_geometry,
                               verify_file, verify_installation)
from .systemd_runtime import ENVIRONMENT, _own_cgroup, boottime_ns


MAX_LAUNCH_BYTES = 32768
PACKAGE = "admin/local_hand_quota_observer/"
SOURCE_FILES = ("launch_q1_experiment.py", "run_q1_experiment.py", *(
    PACKAGE + name + ".py" for name in (
        "launcher", "admission", "protected_inputs", "supervision", "controller_guard",
        "experiment", "experiment_evidence", "systemd_runtime", "journal", "worker")))
STATIC_FIELDS = ("schema", "unit", "cgroup", "runtime_max_usec", "timeout_stop_usec",
                 "memory_bytes", "tasks_max", "cpu_quota_per_sec_usec", "limit_cpu_seconds")


@dataclass(frozen=True)
class LaunchInput:
    digest: str
    operation: str
    source_commit: str
    runtime_path: str
    runtime_digest: str
    journal: tuple
    ticket: str
    controller: tuple
    output_path: str
    parent_path: str
    parent_device: int
    parent_inode: int
    tools_path: str
    source_files: tuple


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def decode_launch_input(raw, expected_digest, expected_source_commit):
    """Pure strict decoder. Controller dynamic identity is never administrator guessed."""
    token(expected_digest, r"[0-9a-f]{64}")
    token(expected_source_commit, r"[0-9a-f]{40}")
    require(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == expected_digest, "LAUNCH_DIGEST")
    value = fields(strict_json(raw, MAX_LAUNCH_BYTES, depth=4), (
        "schema", "operation", "source_commit", "runtime_path", "runtime_digest", "journal",
        "ticket", "controller", "output", "installation"))
    require(value["schema"] == "local-hand-quota-q1-launch-input/v1", "LAUNCH_VERSION")
    require(value["operation"] in ("run", "recover_original"), "LAUNCH_OPERATION")
    source = token(value["source_commit"], r"[0-9a-f]{40}")
    require(source == expected_source_commit, "SOURCE_COMMIT_CHANGED")
    journal = fields(value["journal"], ("path", "owner_uid", "device", "inode"))
    path(journal["path"]); integer(journal["owner_uid"], 0, 0)
    integer(journal["device"]); integer(journal["inode"], 1)
    controller = fields(value["controller"], STATIC_FIELDS)
    require(controller["schema"] == SCHEMA, "CONTROLLER_VERSION")
    unit = token(controller["unit"], r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.service")
    group = PurePosixPath(path(controller["cgroup"]))
    require(group.name == unit and group.parent.name.endswith(".slice"), "CONTROLLER_CGROUP_LAYOUT")
    for key, low, high in (("runtime_max_usec", 1_000_000, 120_000_000),
                           ("timeout_stop_usec", 1000, 5_000_000),
                           ("memory_bytes", 16 * 1024**2, 1024**3), ("tasks_max", 2, 64),
                           ("cpu_quota_per_sec_usec", 1000, 1_000_000), ("limit_cpu_seconds", 1, 120)):
        integer(controller[key], low, high)
    output = fields(value["output"], ("path", "parent"))
    parent = fields(output["parent"], ("path", "owner_uid", "device", "inode"))
    target, parent_path = path(output["path"]), path(parent["path"])
    require(str(PurePosixPath(target).parent) == parent_path, "OUTPUT_PARENT")
    integer(parent["owner_uid"], 0, 0)
    install = fields(value["installation"], ("tools_path", "files"))
    digests = fields(install["files"], SOURCE_FILES)
    return LaunchInput(expected_digest, value["operation"], source, path(value["runtime_path"]),
                       token(value["runtime_digest"], r"[0-9a-f]{64}"), tuple(journal.items()),
                       token(value["ticket"], r"[A-Za-z0-9+/]{1,10922}={0,2}"),
                       tuple(controller.items()), target, parent_path, integer(parent["device"]),
                       integer(parent["inode"], 1), path(install["tools_path"]),
                       tuple((name, token(digests[name], r"[0-9a-f]{64}")) for name in SOURCE_FILES))


def _overlap(left, right):
    left, right = PurePosixPath(left), PurePosixPath(right)
    return left == right or left in right.parents or right in left.parents


def _geometry(spec, config, manifest, launch_path):
    journal_path = dict(spec.journal)["path"]
    validate_geometry(config, manifest, spec.runtime_path, journal_path, extra_input=launch_path)
    require(config.worker_path == str(PurePosixPath(spec.tools_path) / PACKAGE / "worker.py"),
            "LAUNCH_PACKAGE_LAYOUT")
    fixed = (spec.runtime_path, config.manifest_path, config.python_path, config.native_path,
             config.systemd_run_path, config.systemctl_path, launch_path,
             *(str(PurePosixPath(spec.tools_path) / name) for name, _ in spec.source_files))
    for index, filename in enumerate(fixed):
        require(all(not _overlap(filename, other) for other in fixed[index + 1:]), "LAUNCH_INPUT_OVERLAP")
        require(not _overlap(filename, journal_path), "CONTROL_INPUT_OVERLAP")
        require(not _overlap(filename, spec.parent_path), "OUTPUT_INPUT_OVERLAP")
        for slot in manifest.slots:
            require(not _overlap(filename, slot.path), "ROOT_INPUT_OVERLAP")
    require(not _overlap(spec.parent_path, journal_path), "OUTPUT_CONTROL_OVERLAP")
    for slot in manifest.slots:
        require(not _overlap(spec.parent_path, slot.path), "OUTPUT_ROOT_OVERLAP")
    digests = dict(spec.source_files)
    require(digests[PACKAGE + "worker.py"] == config.worker_sha256 and all(
        digests[PACKAGE + name] == digest for name, digest in config.package_files), "LAUNCH_INSTALLATION_BINDING")


def _no_implicit_code(tools_path):
    """Namespace packages and source-only imports; -B alone still reads stale pyc."""
    for dirname, names, source_names in (
        (tools_path, ("admin",), ()),
        (str(PurePosixPath(tools_path) / "admin"), ("__init__", "local_hand_quota_observer"), ()),
        (str(PurePosixPath(tools_path) / PACKAGE), ("__init__",),
         tuple(PurePosixPath(name).stem for name in SOURCE_FILES if name.startswith(PACKAGE))),
    ):
        # ExtensionFileLoader precedes source loading, including package
        # __init__ extensions. Reject every platform-recognized suffix.
        # FileFinder tries a same-name package directory before module files.
        forbidden = ("__pycache__", *source_names, *(name + suffix for name in names
                        for suffix in (".py", ".pyc", *EXTENSION_SUFFIXES)),
                     *(name + suffix for name in source_names for suffix in EXTENSION_SUFFIXES))
        fd = open_protected(dirname, directory=True)
        try:
            for name in forbidden:
                try:
                    os.stat(name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    require(False, "LAUNCH_IMPLICIT_CODE")
        finally:
            os.close(fd)


def _verify_sources(spec, config, launcher_path):
    require(path(launcher_path) == str(PurePosixPath(spec.tools_path) / "launch_q1_experiment.py") and
            os.path.abspath(__file__) == str(PurePosixPath(spec.tools_path) / PACKAGE / "launcher.py"),
            "LAUNCH_RUNNING_SOURCE")
    _no_implicit_code(spec.tools_path)
    snapshots = []
    for name, digest in spec.source_files:
        filename = str(PurePosixPath(spec.tools_path) / name)
        fd = open_protected(filename)
        try:
            before = os.fstat(fd)
            raw = read_fd(fd, 64 * 1024**2)
            require(hashlib.sha256(raw).hexdigest() == digest, "LAUNCH_SOURCE_DIGEST")
            require(file_identity(os.fstat(fd)) == file_identity(before), "INPUT_CHANGED")
            snapshots.append((filename, file_identity(before)))
        finally:
            os.close(fd)
    # This also checks /proc/self/exe against the fixed interpreter, all query
    # installation bytes, executable formats and file-capability absence.
    os.close(verify_installation(config))
    return tuple(snapshots)


def _input_identities(filenames):
    snapshots = []
    for filename in filenames:
        fd = open_protected(filename)
        try:
            snapshots.append((filename, file_identity(os.fstat(fd))))
        finally:
            os.close(fd)
    require(len({identity[:2] for _, identity in snapshots}) == len(snapshots), "LAUNCH_INPUT_ALIAS")
    return tuple(snapshots)


def _current_controller(spec):
    values = dict(spec.controller)
    require(_own_cgroup() == values["cgroup"], "CONTROLLER_CGROUP_CHANGED")
    # This is only a candidate. admit_controller compares actual manager facts.
    invocation = token(os.environ.get("INVOCATION_ID"), r"[0-9a-f]{32}")
    fd = open_protected("/sys/fs/cgroup" + values["cgroup"], directory=True)
    try:
        info = os.fstat(fd)
        values.update(invocation_id=invocation, cgroup_device=info.st_dev, cgroup_inode=info.st_ino)
    finally:
        os.close(fd)
    return decode_controller(values)


def _open_output_parent(spec):
    fd = open_protected(spec.parent_path, directory=True)
    try:
        info = os.fstat(fd)
        require((info.st_dev, info.st_ino) == (spec.parent_device, spec.parent_inode) and
                info.st_uid == 0 and info.st_mode & 0o077 == 0, "OUTPUT_PARENT_IDENTITY")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _write_experiment(spec, raw):
    """Exclusive durable delivery. Every failure retains any created bytes."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_EXPERIMENT_BYTES, "EXPERIMENT_BYTE_LIMIT")
    parent = _open_output_parent(spec)
    fd = None
    try:
        fd = os.open(PurePosixPath(spec.output_path).name,
                     os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     0o600, dir_fd=parent)
        initial = os.fstat(fd)
        require(stat.S_ISREG(initial.st_mode) and initial.st_uid == 0 and initial.st_nlink == 1 and
                stat.S_IMODE(initial.st_mode) == 0o600, "OUTPUT_FILE_IDENTITY")
        offset = 0
        while offset < len(raw):
            count = os.write(fd, raw[offset:offset + 4096])
            require(type(count) is int and 0 < count <= min(4096, len(raw) - offset), "OUTPUT_WRITE_FAILED")
            offset += count
        os.fsync(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        before = os.fstat(fd)
        require(read_fd(fd, MAX_EXPERIMENT_BYTES) == raw and
                file_identity(os.fstat(fd)) == file_identity(before), "OUTPUT_CHANGED")
        os.fsync(parent)
        again = _open_output_parent(spec)
        os.close(again)
        actual = open_protected(spec.output_path)
        try:
            require(file_identity(os.fstat(actual)) == file_identity(before), "OUTPUT_CHANGED")
        finally:
            os.close(actual)
        return file_identity(before)
    finally:
        try:
            if fd is not None:
                os.close(fd)
        finally:
            os.close(parent)


def _experiment_bytes(spec, controller):
    from dataclasses import asdict
    return _json({"schema": "local-hand-quota-q1-experiment-input/v1", "operation": spec.operation,
                  "source_commit": spec.source_commit, "runtime_path": spec.runtime_path,
                  "runtime_digest": spec.runtime_digest, "journal": dict(spec.journal),
                  "ticket": spec.ticket, "controller": {"schema": SCHEMA, **asdict(controller)}})


def _check_time(spec, binding):
    # Recovery must retain the expired original ticket; it never restarts query.
    if spec.operation == "run":
        now = boottime_ns()
        require(binding.issued_ns <= now < binding.deadline_ns, "DEADLINE_EXPIRED")


def _exec_entry(config, spec, digest):
    argv = (config.python_path, "-I", "-B", str(PurePosixPath(spec.tools_path) / "run_q1_experiment.py"),
            "--input", spec.output_path, "--sha256", digest, "--source-commit", spec.source_commit)
    # Keep the inherited pipe FDs and PID. Never Popen/fork the experiment; no
    # unit activation, budget reset or new deadline follows this transition.
    os.execve(config.python_path, argv, dict(ENVIRONMENT))
    require(False, "EXEC_RETURNED")


def launch_experiment(input_path, expected_digest, expected_source_commit, *, launcher_path):
    """Exec once or raise a refusal; does not construct/touch the original journal."""
    require(sys.platform.startswith("linux"), "CONTROLLER_LINUX_REQUIRED")
    require(os.getuid() == 0 and os.geteuid() == 0, "CONTROLLER_ADMIN_REQUIRED")
    input_path = path(input_path)
    original = read_protected(input_path, MAX_LAUNCH_BYTES)
    spec = decode_launch_input(original, expected_digest, expected_source_commit)
    config = load_runtime(spec.runtime_path, spec.runtime_digest)
    manifest_raw = read_protected(config.manifest_path, 32768)
    manifest = decode_manifest(manifest_raw, config.manifest_digest)
    require(manifest.source_commit == spec.source_commit, "SOURCE_COMMIT_CHANGED")
    require(installation_digest(config) == manifest.installation_digest, "INSTALLATION_BINDING")
    input_paths = (input_path, spec.runtime_path, config.manifest_path)
    identities = _input_identities(input_paths)
    _geometry(spec, config, manifest, input_path)
    binding = decode_ticket(spec.ticket, manifest)
    _check_time(spec, binding)
    sources = _verify_sources(spec, config, launcher_path)
    controller = _current_controller(spec)
    admit_controller(config, manifest, controller)
    raw = _experiment_bytes(spec, controller)
    digest = hashlib.sha256(raw).hexdigest()
    experiment = decode_experiment(raw, digest, spec.source_commit)
    require(experiment.ticket == spec.ticket, "ORIGINAL_TICKET_CHANGED")
    _check_time(spec, binding)
    identity = _write_experiment(spec, raw)
    # Recheck fixed provenance and output after durable delivery. A failure does
    # not unlink/replace the original output or fall back to another path/ID.
    require(read_protected(input_path, MAX_LAUNCH_BYTES) == original, "LAUNCH_INPUT_CHANGED")
    require(load_runtime(spec.runtime_path, spec.runtime_digest) == config and
            read_protected(config.manifest_path, 32768) == manifest_raw, "LAUNCH_INPUT_CHANGED")
    require(_input_identities(input_paths) == identities, "LAUNCH_INPUT_CHANGED")
    require(_verify_sources(spec, config, launcher_path) == sources, "LAUNCH_SOURCE_CHANGED")
    fd = open_protected(spec.output_path)
    try:
        require(file_identity(os.fstat(fd)) == identity and read_fd(fd, MAX_EXPERIMENT_BYTES) == raw and
                file_identity(os.fstat(fd)) == identity, "OUTPUT_CHANGED")
    finally:
        os.close(fd)
    # Actual entry re-runs the full guard after exec, using the same controller
    # identity. The original supervisor continues counting throughout.
    require(_current_controller(spec) == controller, "CONTROLLER_IDENTITY_CHANGED")
    _check_time(spec, binding)
    _exec_entry(config, spec, digest)
