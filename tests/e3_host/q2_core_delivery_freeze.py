"""Read-only inputs for the one approved core field-package freeze.

This module has no carrier entry point. It builds packages only in memory,
never creates a marker and never contacts the fixture. Static source closure
precedes the current local binding, which uses the original host window.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import fields, is_dataclass
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import subprocess
import tarfile
import time


def _helper(name):
    spec = importlib.util.spec_from_file_location(
        "_q2_core_delivery_freeze_" + name, Path(__file__).with_name(name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p = _helper("q2_core_delivery_package")
entry_api = _helper("q2_core_delivery_entry")
bootstrap_api = _helper("q2_core_delivery_bootstrap")
c = p.c

FREEZE_SCHEMA = "local-hand-q2-core-static-freeze/v1"
SOURCE_MAP_SCHEMA = "local-hand-q2-core-private-locator-source-map/v1"

# These pins identify the retained return, not arbitrary byte-identical loose
# files.  The caller must also supply the common protected retained directory;
# each named input is opened relative to that held directory.
RETAINED_PINS = {
    "collection-capture.json": {
        "bytes": 1835,
        "sha256": "56c29ed9ffe2cf79235baca6b000afaec9ae84b51b2356c664e44d6b34a4fb18",
    },
    "guest-raw.tar.gz": {
        "bytes": 20164157,
        "sha256": "078b4a5bc198caa42760c31d2a4f8d0be1dd3564090ea316c799bfe6d9e653f7",
    },
    "guest-manifest.json": {
        "bytes": 3419814,
        "sha256": "82c8c13e250ac0be0957b766e84827514dd50cc5cc53d461c126d6dd0523f735",
    },
    "guest-inventory.jsonl": {
        "bytes": 922584,
        "sha256": "0b1f337f219d3b8d06f2d2a22fc30d2d034afef40decfa7db26051c0ea009a62",
    },
}

TARGET_MEMBERS = {
    "plan": {
        "archive_path": "root/q2-transfer-20260926a/plan.json",
        "bytes": 9814,
        "sha256": "efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c",
    },
    "retry": {
        "archive_path": "root/q2-retry-setup-20260927a/retry-preparation.json",
        "bytes": 61119,
        "sha256": "586f0fd79ceb869a8e1ed238d925b6cdbf2cceaddf233687df81ea320bded4fb",
    },
}

# field -> (document role, exact JSON pointer, transformation)
LOCATOR_MAPPING = {
    "state_parent": ("plan", "/directories/state/path", "dirname"),
    "quota_parent": ("plan", "/mounts/quota/path", "identity"),
    "install_parent": ("plan", "/candidate/destination", "dirname"),
    "journal_parent": ("plan", "/mounts/journal/path", "identity"),
    "evidence_parent": ("plan", "/mounts/evidence/path", "identity"),
    "ordinary_user": ("plan", "/account/name", "identity"),
    "ordinary_group": ("plan", "/account/name", "identity"),
    "user_manager_unit": ("retry", "/facts/parents/manager/unit", "identity"),
    "query_parent_unit": ("plan", "/parents/query/unit", "identity"),
    "controller_parent_unit": ("plan", "/parents/controller/unit", "identity"),
    "management_parent_unit": ("plan", "/parents/management/unit", "identity"),
    "supervisor_parent_unit": ("plan", "/parents/supervisor/unit", "identity"),
    "ordinary_parent_unit": ("plan", "/parents/ordinary/unit", "identity"),
    "retained_ordinary_parent_path": (
        "retry", "/facts/parents/ordinary/path", "identity"
    ),
}

CAPTURE_FIELDS = {
    "schema", "completed_realtime_ns", "connection", "files", "gate_rule_http_status",
    "guest", "guest_attestation_stderr_bytes", "guest_boot_id", "guest_entries",
    "guest_regular_bytes", "guest_regular_files", "guest_tar_stderr_bytes", "host",
    "host_entries", "host_regular_bytes", "host_regular_files", "inventory_stderr_bytes",
    "known_deviation_file", "private_bundle_present", "prohibited_actions",
    "source_repository_commit",
}
CAPTURE_FILE_FIELDS = {
    "guest_archive", "guest_inventory", "guest_manifest", "host_archive", "host_manifest",
}
PROHIBITED_FIELDS = {
    "file_delete_or_reservation_release", "guest_started_or_rebooted", "new_batch_issued",
    "preparation_executed", "qcow2_mount_attach_or_hash", "recovery_executed",
    "retry_executed", "service_start_stop_restart_or_reset_failed",
}
MANIFEST_FIELDS = {
    "schema", "archive", "archive_bytes", "archive_sha256", "entries", "entry_count",
    "origin", "regular_file_bytes", "regular_file_count",
}
SOURCE_METADATA_FIELDS = {
    "atime_ns", "blocks", "ctime_ns", "device", "gid", "inode", "mode", "mtime_ns",
    "nlink", "path", "size", "st_mode", "type", "uid",
}
ARCHIVE_METADATA_FIELDS = {"gid", "mode", "mtime_ns", "pax_headers", "size", "uid"}

FIELD_SOURCE_PATHS = {
    "field/loader.py": "tests/e3_host/q2_core_delivery_loader.py",
    "field/bootstrap.py": "tests/e3_host/q2_core_delivery_bootstrap.py",
    "field/dispatcher.py": "tests/e3_host/q2_core_delivery_dispatcher.py",
}

# These exact historical bytes were reviewed for the pre-business stop
# premise. Checking their pins is not a claim of historical remote exit.
PRIOR_SOURCE_PROFILES = (
    {"commit": "605a2a38d1db5ef85c961b4d357cafa157bdd7d5",
     "tree": "ced38519fe6e3b86973de5ccf0dff60fc62322e4",
     "sources": {"loader": "6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61",
                 "bootstrap": "039fe87cc91a64c0327dc404e0ccf9728c32a1cc07e3e6fb11ed74c979f904f3"}},
    {"commit": "59d7c32bbe10d580603b8e5e62dd49ad6a538e56",
     "tree": "15bfe2192ced5aad0acf5c74a58b6e865afe34d1",
     "sources": {"loader": "6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61",
                 "bootstrap": "c9f6e89f874d83856552e65810b04a5d88e7ab0687395dfa5dfd80d7affdee83",
                 "dispatcher": "30d8e9fe9a9bbf39dc5261d0eb0d47c7349fe7e8229132f394a31aa934216eb4"}},
    {"commit": "8704a24b6c3c79ce4a36028ae2182dec2a35843e",
     "tree": "89a5f221883c11838a10a452be2dcb756abb5a17",
     "sources": {"loader": "6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61",
                 "bootstrap": "4a58b342ea4fabb95903e9362cc9b0007c6aafda5a5ece3203692c5033982ce3",
                 "dispatcher": "319c651f05998f812ac8faab51a354c7445b584bc6442a26c9800e79ae776e96"}},
    {"commit": "657b1bcd749cb4281b0193b2bc9430b0662faf98",
     "tree": "4bb00b2e9ccbec3c43160159811e51eec76702cd",
     "sources": {"loader": "6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61",
                 "bootstrap": "7e2d08800951528c81f9078eb772cc4937dc76a3fd1ed7a1ccadde2a12a23cf5",
                 "dispatcher": "714bbb8039aadc3ab58195adde1f61cc273cb4822b46e60de26c2315d459a11b"}},
)

ANCHOR_FILES = {
    "ssh.sh": (0o700, entry_api.WRAPPER_SHA256, "wrapper"),
    "start.sh": (0o700, entry_api.START_SHA256, "fixture_start"),
    "user-data": (0o600, entry_api.CLOUD_CONFIG_SHA256, "fixture_cloud_config"),
    "id_ed25519.pub": (0o600, entry_api.PUBLIC_KEY_SHA256, "identity_public"),
    "known_hosts": (0o644, entry_api.KNOWN_HOSTS_SHA256, "known_hosts"),
}

LOCAL_DEPENDENCIES = (
    ("env", "/usr/bin/env"),
    ("bash", "/usr/bin/bash"),
    ("ssh", "/usr/bin/ssh"),
    ("ssh-keygen", "/usr/bin/ssh-keygen"),
)


def _same_stat(left, right):
    return (
        left.st_dev, left.st_ino, left.st_mode, left.st_uid, left.st_gid,
        left.st_nlink, left.st_size, left.st_mtime_ns, left.st_ctime_ns,
    ) == (
        right.st_dev, right.st_ino, right.st_mode, right.st_uid, right.st_gid,
        right.st_nlink, right.st_size, right.st_mtime_ns, right.st_ctime_ns,
    )


def _direct_call(function, *args, **kwargs):
    return function(*args, **kwargs)


def _read_fd(fd, limit, code, call=_direct_call):
    raw = bytearray()
    while True:
        chunk = call(os.read, fd, min(65536, limit + 1 - len(raw)))
        if not chunk:
            return bytes(raw)
        raw.extend(chunk)
        c.require(len(raw) <= limit, code)


def _read_regular(path, *, limit, code, noatime=True, call=_direct_call):
    """Read one stable single-link regular file without following an alias."""
    path = os.path.abspath(os.fspath(path))
    before_path = call(os.lstat, path)
    c.require(stat.S_ISREG(before_path.st_mode) and before_path.st_nlink == 1
              and 0 <= before_path.st_size <= limit, code)
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    if noatime:
        c.require(hasattr(os, "O_NOATIME"), code)
        flags |= os.O_NOATIME
    try:
        fd = call(os.open, path, flags)
    except OSError as error:
        raise c.ContractError(code) from error
    try:
        before = call(os.fstat, fd)
        c.require(_same_stat(before_path, before), code)
        raw = _read_fd(fd, limit, code, call)
        after = call(os.fstat, fd)
        c.require(_same_stat(before, after) and len(raw) == before.st_size, code)
        return raw, before
    finally:
        os.close(fd)


def _open_bound_executable(expected, *, limit, code, call=_direct_call):
    """Open, hash and hold the exact executable described by ``expected``.

    Callers execute the returned descriptor through ``/proc/self/fd``.  This
    prevents a pathname replacement after verification from selecting a
    different program.  The caller owns the returned descriptor.
    """
    c.require(type(expected) is dict and set(expected) == {
        "role", "path", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes",
        "sha256",
    }, code)
    path = expected["path"]
    c.require(type(path) is str and path.startswith("/"), code)
    path_stat = call(os.lstat, path)
    c.require(stat.S_ISREG(path_stat.st_mode) and path_stat.st_nlink == 1
              and stat.S_IMODE(path_stat.st_mode) & 0o111
              and 0 < path_stat.st_size <= limit, code)
    # This fixed executable role keeps the original read profile. The owned
    # private source and capture roles separately require O_NOATIME; their
    # failures never cause an alternate open here.
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = call(os.open, path, flags)
    except OSError as error:
        raise c.ContractError(code) from error
    try:
        before = call(os.fstat, fd)
        c.require(_same_stat(path_stat, before), code)
        raw = _read_fd(fd, limit, code, call)
        after = call(os.fstat, fd)
        actual = {"role": expected["role"], **_file_identity(path, after, raw)}
        c.require(_same_stat(before, after) and actual == expected
                  and _same_stat(call(os.lstat, path), after), code)
        return fd, after
    except BaseException:
        os.close(fd)
        raise


def _read_retained_inputs(*, retained_root, capture_path, archive_path,
                          manifest_path, inventory_path):
    root = os.path.abspath(os.fspath(retained_root))
    root_stat = os.lstat(root)
    c.require(stat.S_ISDIR(root_stat.st_mode) and not stat.S_ISLNK(root_stat.st_mode)
              and stat.S_IMODE(root_stat.st_mode) == 0o700
              and root_stat.st_uid == os.geteuid(), "CORE_FREEZE_RETAINED_ROOT")
    supplied = {
        "collection-capture.json": capture_path,
        "guest-raw.tar.gz": archive_path,
        "guest-manifest.json": manifest_path,
        "guest-inventory.jsonl": inventory_path,
    }
    for basename, path in supplied.items():
        c.require(os.path.abspath(os.fspath(path)) == os.path.join(root, basename),
                  "CORE_FREEZE_RETAINED_RELATION")
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        root_fd = os.open(root, flags)
    except OSError as error:
        raise c.ContractError("CORE_FREEZE_RETAINED_ROOT") from error
    raw_by_name = {}
    try:
        held_root = os.fstat(root_fd)
        c.require(_same_stat(root_stat, held_root), "CORE_FREEZE_RETAINED_ROOT")
        for basename, pin in RETAINED_PINS.items():
            child_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
            c.require(hasattr(os, "O_NOATIME"), "CORE_FREEZE_RETAINED_FILE")
            child_flags |= os.O_NOATIME
            try:
                fd = os.open(basename, child_flags, dir_fd=root_fd)
            except OSError as error:
                raise c.ContractError("CORE_FREEZE_RETAINED_FILE") from error
            try:
                before = os.fstat(fd)
                c.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                          and stat.S_IMODE(before.st_mode) == 0o600
                          and before.st_uid == held_root.st_uid
                          and before.st_gid == held_root.st_gid
                          and before.st_size == pin["bytes"],
                          "CORE_FREEZE_RETAINED_FILE")
                raw = _read_fd(fd, pin["bytes"], "CORE_FREEZE_RETAINED_FILE")
                after = os.fstat(fd)
                c.require(_same_stat(before, after) and len(raw) == pin["bytes"]
                          and c.sha256(raw) == pin["sha256"],
                          "CORE_FREEZE_RETAINED_PIN")
                raw_by_name[basename] = raw
            finally:
                os.close(fd)
        c.require(_same_stat(held_root, os.fstat(root_fd)), "CORE_FREEZE_RETAINED_CHANGED")
    finally:
        os.close(root_fd)
    return raw_by_name


def _file_identity(path, info, raw):
    return {
        "path": path,
        "dev": info.st_dev,
        "ino": info.st_ino,
        "mode": stat.S_IMODE(info.st_mode),
        "uid": info.st_uid,
        "gid": info.st_gid,
        "nlink": info.st_nlink,
        "bytes": info.st_size,
        "sha256": c.sha256(raw),
    }


def inspect_management_anchor(*, anchor_root, cwd, origins, tokens, environment=None,
                              clock_gettime_ns=time.clock_gettime_ns):
    """Freeze the complete local binding inside the caller's original window.

    There are no current guest reads here.  The returned held ``directory_fd``
    belongs to the caller and must be reused for marker/capture, then closed.
    Static source and release checks must precede this current-host operation.
    """
    deadline = entry_api.capture_contract.Deadline(origins, clock_gettime_ns)
    deadline.check()
    call = deadline.call
    writer = entry_api.capture_contract.observe_writer(call)
    # Bind every local dependency before invoking any one of them.  The
    # ssh-keygen object is then opened, re-hashed and held across exec below.
    dependencies = []
    for role, path in LOCAL_DEPENDENCIES:
        raw, info = _read_regular(path, limit=4 * 1024 * 1024,
                                  code="CORE_FREEZE_ANCHOR_DEPENDENCY", noatime=False, call=call)
        dependencies.append({"role": role, **_file_identity(path, info, raw)})
    dependency_by_role = {item["role"]: item for item in dependencies}

    root = os.path.abspath(os.fspath(anchor_root))
    root_path_stat = call(os.lstat, root)
    c.require(stat.S_ISDIR(root_path_stat.st_mode) and not stat.S_ISLNK(root_path_stat.st_mode)
              and stat.S_IMODE(root_path_stat.st_mode) == 0o700
              and all(value == root_path_stat.st_uid for value in writer["uid"].values())
              and all(value == root_path_stat.st_gid for value in writer["gid"].values()),
              "CORE_FREEZE_ANCHOR_ROOT")
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        root_fd = call(os.open, root, flags)
    except OSError as error:
        raise c.ContractError("CORE_FREEZE_ANCHOR_ROOT") from error
    local = {}
    policy_source_raw = {}
    wrapper_raw = None
    cloud_config_raw = None
    try:
        held_root = call(os.fstat, root_fd)
        c.require(_same_stat(root_path_stat, held_root), "CORE_FREEZE_ANCHOR_ROOT")
        for basename, (mode, digest, role) in ANCHOR_FILES.items():
            child_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
            c.require(hasattr(os, "O_NOATIME"), "CORE_FREEZE_ANCHOR_FILE")
            child_flags |= os.O_NOATIME
            try:
                fd = call(os.open, basename, child_flags, dir_fd=root_fd)
            except OSError as error:
                raise c.ContractError("CORE_FREEZE_ANCHOR_FILE") from error
            try:
                before = call(os.fstat, fd)
                c.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                          and stat.S_IMODE(before.st_mode) == mode
                          and before.st_uid == held_root.st_uid
                          and before.st_gid == held_root.st_gid
                          and before.st_size <= 2 * 1024 * 1024,
                          "CORE_FREEZE_ANCHOR_FILE")
                raw = _read_fd(fd, 2 * 1024 * 1024, "CORE_FREEZE_ANCHOR_FILE", call)
                after = call(os.fstat, fd)
                named = call(os.stat, basename, dir_fd=root_fd, follow_symlinks=False)
                c.require(_same_stat(before, after) and _same_stat(after, named)
                          and c.sha256(raw) == digest,
                          "CORE_FREEZE_ANCHOR_PIN")
                identity = _file_identity(os.path.join(root, basename), after, raw)
                local[role] = identity
                if role in ("fixture_cloud_config", "identity_public", "known_hosts"):
                    policy_source_raw[role] = raw
                if role == "wrapper":
                    wrapper_raw = raw
                elif role == "fixture_cloud_config":
                    cloud_config_raw = raw
            finally:
                os.close(fd)

        private_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
        private_flags |= os.O_NOATIME
        try:
            private_fd = call(os.open, "id_ed25519", private_flags, dir_fd=root_fd)
        except OSError as error:
            raise c.ContractError("CORE_FREEZE_ANCHOR_IDENTITY") from error
        try:
            before = call(os.fstat, private_fd)
            c.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                      and stat.S_IMODE(before.st_mode) == 0o600
                      and before.st_uid == held_root.st_uid
                      and before.st_gid == held_root.st_gid
                      and 0 < before.st_size <= 16384,
                      "CORE_FREEZE_ANCHOR_IDENTITY")
            executable_fd, executable_stat = _open_bound_executable(
                dependency_by_role["ssh-keygen"], limit=4 * 1024 * 1024,
                code="CORE_FREEZE_ANCHOR_DEPENDENCY", call=call,
            )
            command = ["/usr/bin/ssh-keygen", "-y", "-f", f"/proc/self/fd/{private_fd}"]
            try:
                try:
                    derived = call(subprocess.run,
                        command, executable=f"/proc/self/fd/{executable_fd}",
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                        pass_fds=(executable_fd, private_fd), timeout=10, check=False,
                    )
                except (OSError, subprocess.TimeoutExpired) as error:
                    raise c.ContractError("CORE_FREEZE_ANCHOR_IDENTITY") from error
                c.require(_same_stat(executable_stat, call(os.fstat, executable_fd))
                          and _same_stat(call(os.lstat, "/usr/bin/ssh-keygen"), executable_stat),
                          "CORE_FREEZE_ANCHOR_DEPENDENCY")
            finally:
                os.close(executable_fd)
            after = call(os.fstat, private_fd)
            named = call(os.stat, "id_ed25519", dir_fd=root_fd, follow_symlinks=False)
            c.require(derived.returncode == 0 and len(derived.stderr) <= 4096
                      and _same_stat(before, after) and _same_stat(after, named)
                      and c.sha256(derived.stdout) == entry_api.PUBLIC_KEY_SHA256,
                      "CORE_FREEZE_ANCHOR_IDENTITY")
            local["identity"] = {
                "path": os.path.join(root, "id_ed25519"),
                "dev": after.st_dev,
                "ino": after.st_ino,
                "mode": stat.S_IMODE(after.st_mode),
                "uid": after.st_uid,
                "gid": after.st_gid,
                "nlink": after.st_nlink,
                "bytes": after.st_size,
                "derived_public_key_sha256": c.sha256(derived.stdout),
            }
        finally:
            os.close(private_fd)
        c.require(_same_stat(held_root, call(os.fstat, root_fd))
                  and _same_stat(held_root, call(os.lstat, root)),
                  "CORE_FREEZE_ANCHOR_CHANGED")
    except BaseException:
        os.close(root_fd)
        raise

    try:
        return _finish_local_binding(root_fd, held_root, root, cwd, local, dependencies,
            wrapper_raw, cloud_config_raw, policy_source_raw, writer, tokens, environment, deadline)
    except BaseException:
        os.close(root_fd)
        raise


def _finish_local_binding(root_fd, held_root, root, cwd, local, dependencies,
                          wrapper_raw, cloud_config_raw, policy_source_raw,
                          writer, tokens, environment, deadline):
    call = deadline.call
    cwd_path = os.path.abspath(os.fspath(cwd))
    cwd_path_stat = call(os.lstat, cwd_path)
    c.require(stat.S_ISDIR(cwd_path_stat.st_mode) and not stat.S_ISLNK(cwd_path_stat.st_mode),
              "CORE_FREEZE_ANCHOR_CWD")
    cwd_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_DIRECTORY", 0)
    cwd_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        cwd_fd = call(os.open, cwd_path, cwd_flags)
    except OSError as error:
        raise c.ContractError("CORE_FREEZE_ANCHOR_CWD") from error
    try:
        cwd_stat = call(os.fstat, cwd_fd)
        c.require(_same_stat(cwd_path_stat, cwd_stat)
                  and _same_stat(call(os.lstat, cwd_path), cwd_stat), "CORE_FREEZE_ANCHOR_CWD")
    finally:
        os.close(cwd_fd)
    local_environment = entry_api.controlled_environment(environment)
    c.require(cloud_config_raw is not None
              and cloud_config_raw.count(b'ALL=(ALL) NOPASSWD:ALL') == 1,
              "CORE_FREEZE_ANCHOR_SUDO_SOURCE")
    transport = {
        "no_pty": True,
        "stdin_binary": True,
        "stdout_stderr_separate": True,
        "known_host_preexisting": True,
        "batch_mode": True,
        "invocation_matches_frozen_command": True,
        "sudo_noninteractive": True,
        "sudo_no_password": True,
        "sudo_policy_is_exact": False,
        "fixture_policy_broader_than_command": True,
    }
    anchor = {"path": root, "dev": held_root.st_dev, "ino": held_root.st_ino,
              "mode": stat.S_IMODE(held_root.st_mode), "uid": held_root.st_uid,
              "gid": held_root.st_gid, "nlink": held_root.st_nlink}
    binding = {
        "schema": c.MANAGEMENT_BINDING_SCHEMA,
        "anchor": anchor,
        "writer": writer,
        "wrapper": local["wrapper"],
        "fixture_start": local["fixture_start"],
        "fixture_cloud_config": local["fixture_cloud_config"],
        "profile": "env-bash-literal-ssh-v1",
        "environment": local_environment,
        "dependencies": dependencies,
        "identity": local["identity"],
        "identity_public": local["identity_public"],
        "known_hosts": local["known_hosts"],
        "cwd": {
            "path": cwd_path, "dev": cwd_stat.st_dev, "ino": cwd_stat.st_ino,
            "mode": stat.S_IMODE(cwd_stat.st_mode), "uid": cwd_stat.st_uid,
            "gid": cwd_stat.st_gid,
        },
        "remote_expectation": entry_api.static_remote_expectation(tokens),
        "transport": transport,
    }
    c.require(_same_stat(held_root, call(os.fstat, root_fd))
              and _same_stat(held_root, call(os.lstat, root)), "CORE_FREEZE_ANCHOR_CHANGED")
    c.require(entry_api.capture_contract.observe_writer(call) == writer,
              "CORE_FREEZE_WRITER_CHANGED")
    argv = entry_api.wrapper_argv(binding["wrapper"]["path"], wrapper_raw, tokens)
    digest = entry_api.local_management_binding_digest(
        binding, tokens=tokens, argv=argv, wrapper_raw=wrapper_raw)
    deadline.check()
    return {
        "schema": FREEZE_SCHEMA,
        "state": "LOCAL_ANCHOR_FROZEN",
        "issuance": "NOT_ISSUED",
        "missing": [],
        "package": None,
        "binding_preimage": binding,
        "local_management_binding_sha256": digest,
        "private_local_anchor": binding,
        "wrapper_bytes": wrapper_raw,
        # Private in-memory input only: never a package member or public log.
        "policy_source_raw": policy_source_raw,
        "directory_fd": root_fd,
        "origins": dict(deadline.origins),
        "tokens": list(tokens),
        "argv": argv,
    }


def _pairs(items):
    result = {}
    for key, value in items:
        c.require(type(key) is str and key not in result, "CORE_FREEZE_JSON_DUPLICATE")
        result[key] = value
    return result


def _reject_number(_value):
    raise c.ContractError("CORE_FREEZE_JSON_NUMBER")


def _shape(value, depth=0, count=None):
    count = [0] if count is None else count
    count[0] += 1
    c.require(depth <= 32 and count[0] <= 262144, "CORE_FREEZE_JSON_COMPLEXITY")
    c.require(not isinstance(value, float), "CORE_FREEZE_JSON_NUMBER")
    if isinstance(value, dict):
        c.require(all(type(key) is str for key in value), "CORE_FREEZE_JSON_KEY")
        for child in value.values():
            _shape(child, depth + 1, count)
    elif isinstance(value, list):
        for child in value:
            _shape(child, depth + 1, count)
    else:
        c.require(value is None or type(value) in (str, int, bool), "CORE_FREEZE_JSON_VALUE")
    return value


def _json(raw, code="CORE_FREEZE_JSON"):
    c.require(type(raw) is bytes and raw, code)
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                           parse_float=_reject_number, parse_constant=_reject_number)
    except c.ContractError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise c.ContractError(code) from error
    return _shape(value)


def _validate_capture(value):
    c.exact(value, CAPTURE_FIELDS, "CORE_FREEZE_CAPTURE_FIELDS")
    c.require(value["schema"] == "local-hand-q2-readonly-return-capture/v1"
              and value["known_deviation_file"] == "collection-metadata-note.json"
              and value["private_bundle_present"] is False,
              "CORE_FREEZE_CAPTURE_AUTHORITY")
    for key in ("guest_attestation_stderr_bytes", "guest_tar_stderr_bytes",
                "inventory_stderr_bytes"):
        c.require(value[key] == 0, "CORE_FREEZE_CAPTURE_STDERR")
    c.exact(value["prohibited_actions"], PROHIBITED_FIELDS,
            "CORE_FREEZE_CAPTURE_PROHIBITED")
    c.require(all(value["prohibited_actions"][key] is False for key in PROHIBITED_FIELDS),
              "CORE_FREEZE_CAPTURE_PROHIBITED")
    c.exact(value["files"], CAPTURE_FILE_FIELDS, "CORE_FREEZE_CAPTURE_FILE_FIELDS")
    expected = {
        "guest_archive": RETAINED_PINS["guest-raw.tar.gz"],
        "guest_inventory": RETAINED_PINS["guest-inventory.jsonl"],
        "guest_manifest": RETAINED_PINS["guest-manifest.json"],
    }
    for role, pin in expected.items():
        c.require(value["files"][role] == pin, "CORE_FREEZE_CAPTURE_PIN")
    return value


def _inventory(raw):
    lines = raw.splitlines(keepends=True)
    c.require(lines and b"".join(lines) == raw and all(
        line.endswith(b"\n") and not line.endswith(b"\r\n") and line != b"\n"
        for line in lines
    ), "CORE_FREEZE_INVENTORY_LINES")
    result = {}
    for line in lines:
        value = _json(line[:-1], "CORE_FREEZE_INVENTORY_JSON")
        c.exact(value, SOURCE_METADATA_FIELDS, "CORE_FREEZE_INVENTORY_FIELDS")
        path = value["path"]
        c.absolute_path(path, "CORE_FREEZE_INVENTORY_PATH")
        c.require(path not in result and value["type"] in ("regular", "directory"),
                  "CORE_FREEZE_INVENTORY_PATH")
        result[path] = value
    return result


def _validate_evidence_bytes(raw_by_name):
    c.require(type(raw_by_name) is dict and set(raw_by_name) == set(RETAINED_PINS),
              "CORE_FREEZE_EVIDENCE_SET")
    for basename, pin in RETAINED_PINS.items():
        raw = raw_by_name[basename]
        c.require(type(raw) is bytes and len(raw) == pin["bytes"]
                  and c.sha256(raw) == pin["sha256"], "CORE_FREEZE_RETAINED_PIN")

    capture = _validate_capture(_json(raw_by_name["collection-capture.json"]))
    manifest = _json(raw_by_name["guest-manifest.json"])
    c.exact(manifest, MANIFEST_FIELDS, "CORE_FREEZE_MANIFEST_FIELDS")
    archive_pin = RETAINED_PINS["guest-raw.tar.gz"]
    c.require(manifest["schema"] == "local-hand-q2-readonly-return-manifest/v1"
              and manifest["archive"] == "q2_guest_raw.tar.gz"
              and manifest["archive_bytes"] == archive_pin["bytes"]
              and manifest["archive_sha256"] == archive_pin["sha256"]
              and type(manifest["entries"]) is list
              and manifest["entry_count"] == len(manifest["entries"]),
              "CORE_FREEZE_MANIFEST_AUTHORITY")
    inventory = _inventory(raw_by_name["guest-inventory.jsonl"])
    c.require(len(inventory) == manifest["entry_count"], "CORE_FREEZE_INVENTORY_COUNT")

    manifest_paths = []
    regular_files = 0
    regular_bytes = 0
    target_raw = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(raw_by_name["guest-raw.tar.gz"]),
                          mode="r:gz") as archive:
            tar_members = archive.getmembers()
            c.require(len(tar_members) == manifest["entry_count"],
                      "CORE_FREEZE_ARCHIVE_COUNT")
            for described, member in zip(manifest["entries"], tar_members, strict=True):
                kind = described.get("type") if type(described) is dict else None
                expected_fields = {
                    "archive_metadata", "archive_path", "source_metadata", "source_path", "type"
                } | ({"sha256"} if kind == "regular" else set())
                c.exact(described, expected_fields, "CORE_FREEZE_MANIFEST_ENTRY_FIELDS")
                c.require(kind in ("regular", "directory"), "CORE_FREEZE_MANIFEST_ENTRY_TYPE")
                archive_path = c.relative_path(
                    described["archive_path"], "CORE_FREEZE_MANIFEST_ARCHIVE_PATH"
                )
                source_path = c.absolute_path(
                    described["source_path"], "CORE_FREEZE_MANIFEST_SOURCE_PATH"
                )
                c.require(source_path == "/" + archive_path and archive_path not in manifest_paths,
                          "CORE_FREEZE_MANIFEST_PATH_RELATION")
                manifest_paths.append(archive_path)
                c.exact(described["archive_metadata"], ARCHIVE_METADATA_FIELDS,
                        "CORE_FREEZE_ARCHIVE_METADATA_FIELDS")
                archive_metadata = described["archive_metadata"]
                c.require(type(archive_metadata["pax_headers"]) is dict
                          and archive_metadata["pax_headers"] == member.pax_headers
                          and member.name == archive_path
                          and member.uid == archive_metadata["uid"]
                          and member.gid == archive_metadata["gid"]
                          and member.mode == archive_metadata["mode"]
                          and member.size == archive_metadata["size"]
                          and int(member.mtime * 1_000_000_000)
                              == archive_metadata["mtime_ns"],
                          "CORE_FREEZE_ARCHIVE_METADATA")
                c.exact(described["source_metadata"], SOURCE_METADATA_FIELDS,
                        "CORE_FREEZE_SOURCE_METADATA_FIELDS")
                c.require(inventory.get(source_path) == described["source_metadata"]
                          and described["source_metadata"]["type"] == kind,
                          "CORE_FREEZE_INVENTORY_MISMATCH")
                if kind == "regular":
                    c.require(member.isreg(), "CORE_FREEZE_ARCHIVE_TYPE")
                    stream = archive.extractfile(member)
                    c.require(stream is not None, "CORE_FREEZE_ARCHIVE_READ")
                    raw = stream.read(member.size + 1)
                    c.require(len(raw) == member.size
                              and c.sha256(raw) == described["sha256"],
                              "CORE_FREEZE_ARCHIVE_DIGEST")
                    regular_files += 1
                    regular_bytes += len(raw)
                    for role, pin in TARGET_MEMBERS.items():
                        if archive_path == pin["archive_path"]:
                            c.require(len(raw) == pin["bytes"]
                                      and c.sha256(raw) == pin["sha256"],
                                      "CORE_FREEZE_LOCATOR_MEMBER_PIN")
                            target_raw[role] = raw
                else:
                    c.require(member.isdir(), "CORE_FREEZE_ARCHIVE_TYPE")
    except c.ContractError:
        raise
    except (OSError, tarfile.TarError, EOFError) as error:
        raise c.ContractError("CORE_FREEZE_ARCHIVE") from error

    c.require(set(target_raw) == set(TARGET_MEMBERS), "CORE_FREEZE_LOCATOR_MEMBERS")
    c.require(regular_files == manifest["regular_file_count"]
              and regular_bytes == manifest["regular_file_bytes"]
              and manifest["entry_count"] == capture["guest_entries"]
              and regular_files == capture["guest_regular_files"]
              and regular_bytes == capture["guest_regular_bytes"],
              "CORE_FREEZE_COUNT_MISMATCH")
    return capture, manifest, target_raw


def _pointer(value, pointer):
    c.require(type(pointer) is str and pointer.startswith("/") and pointer != "/",
              "CORE_FREEZE_JSON_POINTER")
    current = value
    for encoded in pointer[1:].split("/"):
        c.require(re.search(r"~(?:[^01]|$)", encoded) is None,
                  "CORE_FREEZE_JSON_POINTER")
        key = encoded.replace("~1", "/").replace("~0", "~")
        c.require(type(current) is dict and key in current, "CORE_FREEZE_JSON_POINTER")
        current = current[key]
    return current


def _locator_source(raw_by_name):
    capture, _manifest, target_raw = _validate_evidence_bytes(raw_by_name)
    documents = {role: _json(raw, "CORE_FREEZE_LOCATOR_JSON")
                 for role, raw in target_raw.items()}
    values = {}
    mapping = {}
    for field, (role, pointer, transform) in LOCATOR_MAPPING.items():
        source = _pointer(documents[role], pointer)
        c.require(type(source) is str and source, "CORE_FREEZE_LOCATOR_VALUE")
        if transform == "dirname":
            c.absolute_path(source, "CORE_FREEZE_LOCATOR_SOURCE_PATH")
            value = posixpath.dirname(source)
            c.require(value not in ("", "/"), "CORE_FREEZE_LOCATOR_SOURCE_PATH")
        else:
            c.require(transform == "identity", "CORE_FREEZE_LOCATOR_TRANSFORM")
            value = source
        values[field] = value
        mapping[field] = {
            "member": TARGET_MEMBERS[role]["archive_path"],
            "member_sha256": TARGET_MEMBERS[role]["sha256"],
            "json_pointer": pointer,
            "transform": transform,
            "source_value": source,
            "value": value,
        }
    source_map = {
        "schema": SOURCE_MAP_SCHEMA,
        "evidence": {
            key: {"basename": key, **pin} for key, pin in RETAINED_PINS.items()
        },
        "members": {role: dict(pin) for role, pin in TARGET_MEMBERS.items()},
        "mapping": mapping,
        "observation_record_sha256": c.sha256(
            raw_by_name["collection-capture.json"]
        ),
        "zero_mismatch": True,
        "historical_only": True,
        "capture_completed_realtime_ns": capture["completed_realtime_ns"],
    }
    return values, source_map


def _not_prepared(*, missing, source_map=None):
    result = {
        "schema": FREEZE_SCHEMA,
        "state": "NOT_PREPARED",
        "issuance": "NOT_ISSUED",
        "missing": list(missing),
        "package": None,
    }
    if source_map is not None:
        result["locators"] = None
        result["private_source_map"] = source_map
    return result


def freeze_private_locators(*, retained_root, capture_path, archive_path,
                            manifest_path, inventory_path,
                            local_management_binding_preimage=None,
                            management_tokens=None, management_argv=None,
                            management_wrapper_raw=None):
    """Freeze A locators from the one retained source, or return NOT_PREPARED.

    A digest supplied by itself is deliberately not accepted.  The complete
    management binding preimage must be validated by the entry contract first.
    Returned ``private_source_map`` contains raw private values and is a freeze
    input only; callers must not publish it in repository documentation.
    """
    raw_by_name = _read_retained_inputs(
        retained_root=retained_root, capture_path=capture_path, archive_path=archive_path,
        manifest_path=manifest_path, inventory_path=inventory_path,
    )
    values, source_map = _locator_source(raw_by_name)
    supplied = {
        "management_anchor.local_binding_preimage": local_management_binding_preimage,
        "management_anchor.tokens": management_tokens,
        "management_anchor.argv": management_argv,
        "management_anchor.wrapper_bytes": management_wrapper_raw,
    }
    missing = [name for name, value in supplied.items() if value is None]
    if missing:
        return _not_prepared(missing=missing, source_map=source_map)
    management_digest = entry_api.local_management_binding_digest(
        local_management_binding_preimage, tokens=management_tokens, argv=management_argv,
        wrapper_raw=management_wrapper_raw,
    )
    c.digest(management_digest, "CORE_FREEZE_MANAGEMENT_BINDING")
    locators = {
        "schema": c.LOCATORS_SCHEMA,
        "observation_record_sha256": source_map["observation_record_sha256"],
        "source_relation_sha256": "0" * 64,
        **values,
        "carrier_unit": c.CARRIER_UNIT,
    }
    relation = p.locator_relation(locators, management_digest)
    locators["source_relation_sha256"] = c.sha256(c.canonical(relation))
    p.validate_locators(locators, management_digest)
    source_map = dict(source_map)
    source_map["local_management_binding_sha256"] = management_digest
    source_map["source_relation_sha256"] = locators["source_relation_sha256"]
    return {
        "schema": FREEZE_SCHEMA,
        "state": "PRIVATE_LOCATORS_FROZEN",
        "issuance": "NOT_ISSUED",
        "missing": [],
        "package": None,
        "locators": locators,
        "local_management_binding_sha256": management_digest,
        "private_source_map": source_map,
    }


def _git(repository, git_path, *args, limit=16 * 1024 * 1024):
    repository = os.path.abspath(os.fspath(repository))
    c.require(git_path == "/usr/bin/git" and all(
        type(item) is str and item and "\0" not in item for item in args
    ), "CORE_FREEZE_GIT_COMMAND")
    command = [
        git_path, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
        "-c", "core.autocrlf=false", "-c", "safe.directory=" + repository,
        "-C", repository, *args,
    ]
    environment = {
        "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=environment, check=False,
                                timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise c.ContractError("CORE_FREEZE_GIT_COMMAND") from error
    c.require(result.returncode == 0 and len(result.stdout) <= limit
              and len(result.stderr) <= 1024 * 1024, "CORE_FREEZE_GIT_COMMAND")
    return result.stdout


def _filesystem_files(root, *, exclude_git=False):
    root = os.path.abspath(os.fspath(root))
    result = {}
    directories = set()
    for current, names, files in os.walk(root, topdown=True, followlinks=False):
        relative_root = os.path.relpath(current, root)
        if relative_root == ".":
            relative_root = ""
        names.sort(key=lambda item: os.fsencode(item))
        files.sort(key=lambda item: os.fsencode(item))
        if exclude_git and not relative_root and ".git" in names:
            names.remove(".git")
        for name in list(names):
            absolute = os.path.join(current, name)
            info = os.lstat(absolute)
            c.require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),
                      "CORE_FREEZE_CHECKOUT_TYPE")
            relative = posixpath.join(relative_root, name) if relative_root else name
            c.relative_path(relative, "CORE_FREEZE_CHECKOUT_PATH")
            directories.add(relative)
        for name in files:
            relative = posixpath.join(relative_root, name) if relative_root else name
            c.relative_path(relative, "CORE_FREEZE_CHECKOUT_PATH")
            raw, info = _read_regular(os.path.join(current, name),
                                      limit=c.PACKAGE_LIMITS["member_bytes"],
                                      code="CORE_FREEZE_CHECKOUT_FILE")
            c.require(relative not in result, "CORE_FREEZE_CHECKOUT_PATH")
            result[relative] = (raw, info)
    return result, directories


def _candidate_tree(checkout, git_path):
    identity = _git(checkout, git_path, "rev-parse", "HEAD^{commit}", "HEAD^{tree}")
    c.require(identity.decode("ascii").split() == [
        c.CANDIDATE["commit"], c.CANDIDATE["tree"]
    ], "CORE_FREEZE_CANDIDATE_ID")
    raw = _git(checkout, git_path, "ls-tree", "-rz", "-r", "--full-tree",
               c.CANDIDATE["commit"])
    result = {}
    for record in filter(None, raw.split(b"\0")):
        try:
            header, encoded = record.split(b"\t", 1)
            mode, kind, blob = header.split()
            path = encoded.decode("ascii")
        except (ValueError, UnicodeError) as error:
            raise c.ContractError("CORE_FREEZE_CANDIDATE_TREE") from error
        c.relative_path(path, "CORE_FREEZE_CANDIDATE_TREE")
        c.require(mode in (b"100644", b"100755") and kind == b"blob"
                  and re.fullmatch(rb"[0-9a-f]{40}", blob) is not None
                  and path not in result, "CORE_FREEZE_CANDIDATE_TREE")
        result[path] = (int(mode[-3:], 8), blob.decode("ascii"))
    c.require(result, "CORE_FREEZE_CANDIDATE_TREE")
    return result


def _git_metadata(checkout):
    git_dir = os.path.join(os.path.abspath(os.fspath(checkout)), ".git")
    info = os.lstat(git_dir)
    c.require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),
              "CORE_FREEZE_GIT_DIRECTORY")
    files, directories = _filesystem_files(git_dir)
    renamed = {".git/" + path: value for path, value in files.items()}
    forbidden_exact = {
        ".git/commondir", ".git/info/grafts", ".git/objects/info/alternates",
        ".git/objects/info/http-alternates", ".git/shallow", ".git/shallow.lock",
        ".git/config.worktree", ".git/info/sparse-checkout",
    }
    c.require(not (set(renamed) & forbidden_exact)
              and not any(path.startswith(".git/hooks/")
                          or path.startswith(".git/refs/replace/")
                          or path.endswith(".lock") or path.endswith(".promisor")
                          for path in renamed)
              and not any(path == "hooks" or path.startswith("hooks/")
                          or path == "worktrees" or path.startswith("worktrees/")
                          for path in directories), "CORE_FREEZE_GIT_DEPENDENCY")
    c.require(".git/HEAD" in renamed and ".git/config" in renamed
              and any(path.startswith(".git/objects/") for path in renamed),
              "CORE_FREEZE_GIT_METADATA")
    try:
        config = renamed[".git/config"][0].decode("ascii", "strict")
    except UnicodeError as error:
        raise c.ContractError("CORE_FREEZE_GIT_CONFIG") from error
    section = None
    entries = {}
    for line in config.splitlines():
        stripped = line.strip()
        c.require(stripped and not stripped.startswith(("#", ";")),
                  "CORE_FREEZE_GIT_DEPENDENCY")
        if stripped.startswith("["):
            match = re.fullmatch(r"\[([A-Za-z][A-Za-z0-9-]*)\]", stripped)
            c.require(match is not None and match.group(1).lower() == "core",
                      "CORE_FREEZE_GIT_DEPENDENCY")
            section = "core"
            continue
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9-]*)\s*=\s*([^\s#;]+)", stripped)
        c.require(section == "core" and match is not None,
                  "CORE_FREEZE_GIT_DEPENDENCY")
        key = match.group(1).lower()
        value = match.group(2).lower()
        c.require(key not in entries, "CORE_FREEZE_GIT_DEPENDENCY")
        entries[key] = value
    # A package checkout is prepared specifically for this one freeze.  A
    # minimal config removes every config-controlled worktree, hook, object,
    # replacement, include and network source instead of trying to blacklist
    # Git's open-ended configuration namespace.
    c.require(entries == {
        "repositoryformatversion": "0",
        "filemode": "true",
        "bare": "false",
        "logallrefupdates": "true",
    }, "CORE_FREEZE_GIT_DEPENDENCY")
    return renamed


def _same_file_map(left, right):
    if set(left) != set(right):
        return False
    return all(left[path][0] == right[path][0]
               and _same_stat(left[path][1], right[path][1]) for path in left)


def _implementation_blobs(repository, implementation_commit, implementation_tree,
                          git_path):
    c.commit(implementation_commit, "CORE_FREEZE_IMPLEMENTATION")
    c.commit(implementation_tree, "CORE_FREEZE_IMPLEMENTATION")
    identity = _git(repository, git_path, "rev-parse", implementation_commit + "^{commit}",
                    implementation_commit + "^{tree}")
    c.require(identity.decode("ascii").split() == [implementation_commit, implementation_tree],
              "CORE_FREEZE_IMPLEMENTATION")
    for prior in PRIOR_SOURCE_PROFILES:
        identity = _git(repository, git_path, "rev-parse", prior['commit'] + "^{tree}")
        c.require(identity.decode('ascii').strip() == prior['tree'], 'CORE_FREEZE_PRIOR_TREE')
        _git(repository, git_path, 'merge-base', '--is-ancestor', prior['commit'], implementation_commit)
        for role, digest in prior['sources'].items():
            raw = _git(repository, git_path, 'show', prior['commit'] + ':' + FIELD_SOURCE_PATHS['field/' + role + '.py'])
            c.require(c.sha256(raw) == digest, 'CORE_FREEZE_PRIOR_SOURCE')
    # Final D must descend from every independent amendment/new-batch closure.
    # Authority stays offline; no replacement wire amendment or extra member.
    for baseline, decision, closure in (
            (c.AMENDMENT_BASELINE, c.AMENDMENT_OWNER_DECISION, c.AMENDMENT_CLOSURE),
            (c.WRITER_TRANSPORT_BASELINE, c.WRITER_TRANSPORT_OWNER_DECISION,
             c.WRITER_TRANSPORT_CLOSURE),
            (c.COMPLETION_ADJUSTMENT_BASELINE, c.COMPLETION_ADJUSTMENT_OWNER_DECISION,
             c.COMPLETION_ADJUSTMENT_CLOSURE),
            (c.CLOUD_INIT_GRANT_BASELINE, c.CLOUD_INIT_GRANT_OWNER_DECISION,
             c.CLOUD_INIT_GRANT_CLOSURE),
            (c.NEXT_ACCEPTANCE_BASELINE, c.NEXT_ACCEPTANCE_OWNER_DECISION,
             c.NEXT_ACCEPTANCE_CLOSURE),
            (c.HOST_CAPACITY_BOUNDARY_BASELINE, c.HOST_CAPACITY_BOUNDARY_OWNER_DECISION,
             c.HOST_CAPACITY_BOUNDARY_CLOSURE),
            (c.POST_SUDO_BASELINE, c.POST_SUDO_OWNER_DECISION, c.POST_SUDO_CLOSURE),
            (c.LOCALE_GRAMMAR_BASELINE, c.LOCALE_GRAMMAR_OWNER_DECISION, c.LOCALE_GRAMMAR_CLOSURE),
            (c.POST_LOCALE_BASELINE, c.POST_LOCALE_OWNER_DECISION, c.POST_LOCALE_CLOSURE),
            (c.MINIMAL_BASELINE, c.MINIMAL_OWNER_DECISION, c.MINIMAL_CLOSURE),
            (c.SERIAL_BASELINE, c.SERIAL_OWNER_DECISION, c.SERIAL_CLOSURE),
            (c.SYSTEMCTL_BASELINE, c.SYSTEMCTL_OWNER_DECISION, c.SYSTEMCTL_CLOSURE),
            (c.TEMPLATE_BASELINE, c.TEMPLATE_OWNER_DECISION, c.TEMPLATE_CLOSURE),
            (c.NAMES_BASELINE, c.NAMES_OWNER_DECISION, c.NAMES_CLOSURE),
            (c.EXEC_BASELINE, c.EXEC_OWNER_DECISION, c.EXEC_CLOSURE),
            (c.GS_BASELINE, c.GS_OWNER_DECISION, c.GS_CLOSURE),
            (c.QI_BASELINE, c.QI_OWNER_DECISION, c.QI_CLOSURE),
            (c.DS_BASELINE, c.DS_OWNER_DECISION, c.DS_CLOSURE)):
        c.require(implementation_commit != closure["commit"], "CORE_FREEZE_IMPLEMENTATION_PARENT")
        for authority in (baseline, closure):
            actual = _git(repository, git_path, "rev-parse", authority["commit"] + "^{tree}")
            c.require(actual.decode("ascii").strip() == authority["tree"],
                      "CORE_FREEZE_AUTHORITY_TREE")
        _git(repository, git_path, "merge-base", "--is-ancestor", baseline["commit"], closure["commit"])
        _git(repository, git_path, "merge-base", "--is-ancestor", closure["commit"], implementation_commit)
        for path, expected in baseline["documents_sha256"].items():
            for commit_id in (baseline["commit"], closure["commit"], implementation_commit):
                raw = _git(repository, git_path, "show", commit_id + ":" + path, limit=1_048_576)
                c.require(c.sha256(raw) == expected, "CORE_FREEZE_AUTHORITY_DOCUMENT")
        for commit_id in (closure["commit"], implementation_commit):
            raw = _git(repository, git_path, "show", commit_id + ":" + decision["record_path"],
                       limit=1_048_576)
            c.require(c.sha256(raw) == decision["record_sha256"], "CORE_FREEZE_OWNER_DECISION")
    source_paths = list(FIELD_SOURCE_PATHS.values())
    tree = _git(repository, git_path, "ls-tree", "-z", implementation_commit, "--",
                *source_paths)
    objects = {}
    for record in filter(None, tree.split(b"\0")):
        try:
            header, encoded = record.split(b"\t", 1)
            mode, kind, blob = header.split()
            path = encoded.decode("ascii")
        except (ValueError, UnicodeError) as error:
            raise c.ContractError("CORE_FREEZE_FIELD_TREE") from error
        c.require(mode == b"100644" and kind == b"blob"
                  and path in source_paths and path not in objects,
                  "CORE_FREEZE_FIELD_TREE")
        raw = _git(repository, git_path, "cat-file", "blob", blob.decode("ascii"),
                   limit=c.PACKAGE_LIMITS["member_bytes"])
        c.require(p._git_blob(raw) == blob.decode("ascii"), "CORE_FREEZE_FIELD_BLOB")
        objects[path] = raw
    c.require(set(objects) == set(source_paths), "CORE_FREEZE_FIELD_SET")
    loader = objects[FIELD_SOURCE_PATHS["field/loader.py"]]
    bootstrap = objects[FIELD_SOURCE_PATHS["field/bootstrap.py"]]
    dispatcher = objects[FIELD_SOURCE_PATHS["field/dispatcher.py"]]
    original_dispatcher = _git(repository, git_path, 'show', c.LOCALE_REPAIR + ':'
        + FIELD_SOURCE_PATHS['field/dispatcher.py'], limit=c.PACKAGE_LIMITS['member_bytes'])
    _git(repository, git_path, 'merge-base', '--is-ancestor', c.LOCALE_REPAIR, implementation_commit)
    _validate_locale_source_preserved(original_dispatcher, dispatcher)
    original_bootstrap = _git(repository, git_path, 'show', c.LOCALE_REPAIR + ':'
        + FIELD_SOURCE_PATHS['field/bootstrap.py'], limit=c.PACKAGE_LIMITS['member_bytes'])
    c.require(bootstrap == original_bootstrap.replace(b'20261005b', b'20261007a'),
              'CORE_FREEZE_BOOTSTRAP_DELTA')
    c.require(c.sha256(loader) == PRIOR_SOURCE_PROFILES[0]['sources']['loader'],
              'CORE_FREEZE_LOADER_UNCHANGED')
    try:
        parsed = ast.parse(bootstrap.decode("utf-8", "strict"), filename="field/bootstrap.py")
    except (UnicodeError, SyntaxError) as error:
        raise c.ContractError("CORE_FREEZE_BOOTSTRAP_SOURCE") from error
    bindings = []
    for node in parsed.body:
        if (isinstance(node, (ast.Assign, ast.AnnAssign))
                and ((isinstance(node, ast.Assign) and len(node.targets) == 1
                      and isinstance(node.targets[0], ast.Name)
                      and node.targets[0].id == "LOADER_SHA256")
                     or (isinstance(node, ast.AnnAssign)
                         and isinstance(node.target, ast.Name)
                         and node.target.id == "LOADER_SHA256"))):
            value = node.value
            if isinstance(value, ast.Constant) and type(value.value) is str:
                bindings.append(value.value)
    c.require(bindings == [c.sha256(loader)], "CORE_FREEZE_LOADER_BINDING")
    return loader, bootstrap, dispatcher


def _validate_locale_source_preserved(original, current):
    """Compare source bytes, never replay the consumed private snapshot parse."""
    names = {'_admit_sshd_source', '_admit_text', '_require'}
    def functions(raw):
        tree = ast.parse(raw.decode('utf-8', 'strict'))
        lines = raw.splitlines(keepends=True)
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        c.require(len(nodes) == len(names), 'CORE_FREEZE_LOCALE_SOURCE')
        return {node.name: b''.join(lines[min([node.lineno] +
            [item.lineno for item in node.decorator_list]) - 1:node.end_lineno]) for node in nodes}
    c.require(functions(original) == functions(current), 'CORE_FREEZE_LOCALE_SOURCE')


def _artifact(path, expected, role):
    c.require(Path(path).name == expected["basename"], "CORE_FREEZE_ARTIFACT_BASENAME")
    raw, _info = _read_regular(path, limit=c.PACKAGE_LIMITS["member_bytes"],
                               code="CORE_FREEZE_ARTIFACT")
    c.require(len(raw) == expected["bytes"] and c.sha256(raw) == expected["sha256"],
              "CORE_FREEZE_ARTIFACT_PIN")
    if role == "projection":
        value = c.document(raw, limit=c.PACKAGE_LIMITS["member_bytes"], newline=True)
        c.exact(value, {"schema", "source_commit", "source_tree", "files"},
                "CORE_FREEZE_PROJECTION_FIELDS")
        c.require(value["schema"] == "local-hand-q2-source-projection/v1"
                  and value["source_commit"] == c.CANDIDATE["commit"]
                  and value["source_tree"] == c.CANDIDATE["tree"]
                  and type(value["files"]) is dict
                  and len(value["files"]) == expected["file_count"],
                  "CORE_FREEZE_PROJECTION")
        for name, item in value["files"].items():
            c.relative_path(name, "CORE_FREEZE_PROJECTION_PATH")
            c.exact(item, {"mode", "sha256"}, "CORE_FREEZE_PROJECTION_ENTRY")
            c.require(item["mode"] in (0o644, 0o755), "CORE_FREEZE_PROJECTION_ENTRY")
            c.digest(item["sha256"], "CORE_FREEZE_PROJECTION_ENTRY")
    return raw


def freeze_package_members(*, candidate_checkout, wheel_path, projection_path,
                           implementation_repository, implementation_commit=None,
                           implementation_tree=None, git_path="/usr/bin/git"):
    """Return the complete static member closure; never serialize a package.

    The candidate input must already be a standalone clean checkout whose
    ``.git`` directory has no alternates, hooks, replacement objects, partial
    clone/promisor state, or configured network dependency.  D field bytes are
    read from the explicit committed Git object, never from its working tree.
    """
    missing = []
    if implementation_commit is None:
        missing.append("implementation.commit")
    if implementation_tree is None:
        missing.append("implementation.tree")
    if missing:
        return _not_prepared(missing=missing)

    checkout = os.path.abspath(os.fspath(candidate_checkout))
    c.require(stat.S_ISDIR(os.lstat(checkout).st_mode), "CORE_FREEZE_CHECKOUT_ROOT")
    # This filesystem-only inspection must precede the first Git invocation;
    # core.worktree, core.hooksPath, extensions.worktreeConfig and other
    # config-driven object/worktree sources must never influence a subprocess.
    metadata = _git_metadata(checkout)
    candidate_tree = _candidate_tree(checkout, git_path)
    worktree, directories = _filesystem_files(checkout, exclude_git=True)
    c.require(set(worktree) == set(candidate_tree), "CORE_FREEZE_CHECKOUT_SET")
    expected_directories = set()
    for path in candidate_tree:
        parent = PurePosixPath(path).parent
        while parent.as_posix() != ".":
            expected_directories.add(parent.as_posix())
            parent = parent.parent
    c.require(directories == expected_directories, "CORE_FREEZE_CHECKOUT_DIRECTORIES")
    for path, (mode, blob) in candidate_tree.items():
        raw, info = worktree[path]
        c.require(stat.S_IMODE(info.st_mode) & 0o111 == (0o111 if mode == 0o755 else 0)
                  and p._git_blob(raw) == blob, "CORE_FREEZE_CHECKOUT_BYTES")

    _git(checkout, git_path, "fsck", "--strict", "--no-dangling", "--no-reflogs",
         c.CANDIDATE["commit"], limit=1024 * 1024)
    # Prove neither the checkout identity nor any packaged Git metadata moved
    # during the read.  The second snapshot is compared byte-for-byte.
    c.require(_candidate_tree(checkout, git_path) == candidate_tree
              and _same_file_map(_git_metadata(checkout), metadata),
              "CORE_FREEZE_CHECKOUT_CHANGED")

    wheel = _artifact(wheel_path, c.WHEEL, "wheel")
    projection = _artifact(projection_path, c.PROJECTION, "projection")
    loader, bootstrap, dispatcher = _implementation_blobs(
        implementation_repository, implementation_commit, implementation_tree, git_path
    )
    field_rows, field_bytes = p.field_member_blobs(
        loader, bootstrap, dispatcher, implementation_commit=implementation_commit,
        source_paths=FIELD_SOURCE_PATHS,
    )

    rows = []
    member_bytes = {}
    for path, (mode, blob) in candidate_tree.items():
        raw = worktree[path][0]
        package_path = "candidate/" + path
        rows.append(p.member(package_path, "candidate-worktree", mode, raw, {
            "kind": "candidate-blob", "commit": c.CANDIDATE["commit"],
            "path": path, "blob": blob,
        }))
        member_bytes[package_path] = raw
    for git_path_name, (raw, _info) in metadata.items():
        package_path = "candidate/" + git_path_name
        mode = 0o755 if stat.S_IMODE(_info.st_mode) & 0o111 else 0o644
        rows.append(p.member(package_path, "candidate-git-metadata", mode, raw, {
            "kind": "candidate-git-metadata", "commit": c.CANDIDATE["commit"],
            "git_path": git_path_name,
        }))
        member_bytes[package_path] = raw
    artifacts = (
        ("artifacts/" + c.WHEEL["basename"], "wheel", wheel, c.WHEEL),
        ("artifacts/" + c.PROJECTION["basename"], "projection", projection, c.PROJECTION),
    )
    for path, role, raw, expected in artifacts:
        rows.append(p.member(path, role, 0o644, raw, {
            "kind": role, "basename": expected["basename"], "sha256": expected["sha256"],
        }))
        member_bytes[path] = raw
    rows.extend(field_rows)
    member_bytes.update(field_bytes)
    rows.sort(key=lambda item: item["path"].encode("ascii"))
    c.require(len(rows) <= c.PACKAGE_LIMITS["members"]
              and len(rows) == len(member_bytes)
              and {row["path"] for row in rows} == set(member_bytes),
              "CORE_FREEZE_MEMBER_SET")
    for row in rows:
        p.validate_member(row)
        raw = member_bytes[row["path"]]
        c.require(len(raw) == row["bytes"] and c.sha256(raw) == row["sha256"],
                  "CORE_FREEZE_MEMBER_BYTES")
    derived_directories = set()
    for row in rows:
        parent = PurePosixPath(row["path"]).parent
        while parent.as_posix() != ".":
            derived_directories.add(parent.as_posix())
            parent = parent.parent
    c.require(len(rows) + len(derived_directories) <= c.PACKAGE_LIMITS["shared_entries"]
              and sum(len(raw) for raw in member_bytes.values())
                  <= c.PACKAGE_LIMITS["package_bytes"], "CORE_FREEZE_MEMBER_LIMIT")
    prior_api=p._approved_module().prior_attempt
    journal_sources = {name: _git(implementation_repository,git_path,'show',implementation_commit
        + ':tests/e3_host/' + name,limit=524288) for name in prior_api.JOURNAL_SOURCE_NAMES}
    return {
        "schema": FREEZE_SCHEMA,
        "state": "STATIC_MEMBERS_FROZEN",
        "journal_sources": journal_sources,
        "issuance": "NOT_ISSUED",
        "missing": [],
        "package": None,
        "implementation": {"commit": implementation_commit, "tree": implementation_tree},
        "members": rows,
        "member_bytes": member_bytes,
        "member_count": len(rows),
        "derived_directory_count": len(derived_directories),
        "logical_member_bytes": sum(len(raw) for raw in member_bytes.values()),
    }


def _validate_static_freeze(static_freeze):
    c.require(type(static_freeze) is dict and static_freeze.get("state") == "STATIC_MEMBERS_FROZEN",
              "CORE_FREEZE_STATE")
    rows, values = static_freeze["members"], static_freeze["member_bytes"]
    c.require(type(rows) is list and type(values) is dict
              and len(rows) == len(values) <= c.PACKAGE_LIMITS["members"]
              and {row["path"] for row in rows} == set(values), "CORE_FREEZE_MEMBER_SET")
    c.make_amendment(static_freeze["implementation"])
    fields = {}
    for item in rows:
        p.validate_member(item)
        raw = values[item["path"]]
        c.require(type(raw) is bytes and item["bytes"] == len(raw)
                  and item["sha256"] == c.sha256(raw), "CORE_FREEZE_MEMBER_BYTES")
        if item["role"] in ("candidate-worktree", "field-code"):
            c.require(item["origin"]["blob"] == p._git_blob(raw), "CORE_FREEZE_MEMBER_BLOB")
        if item["role"] == "field-code":
            c.require(item["path"] in FIELD_SOURCE_PATHS
                      and item["origin"]["path"] == FIELD_SOURCE_PATHS[item["path"]]
                      and item["origin"]["commit"] == static_freeze["implementation"]["commit"],
                      "CORE_FREEZE_FIELD_SOURCE")
            fields[item["path"]] = raw
        c.require(item["role"] != "approved-inputs", "CORE_FREEZE_APPROVED_DUPLICATE")
    c.require(set(fields) == set(FIELD_SOURCE_PATHS), "CORE_FREEZE_FIELD_SET")
    return values


def build_frozen_package(*, static_freeze, local_anchor, locators, approved_inputs_raw):
    """Bind approved inputs and exact committed field bytes into a v3 package.

    This is an in-memory construction, not a release or an independent review
    of the private source set. The caller obtains ``approved_inputs_raw`` from
    the approved source builders and keeps its private source evidence.
    """
    _validate_static_freeze(static_freeze)
    c.require(local_anchor["state"] == "LOCAL_ANCHOR_FROZEN", "CORE_FREEZE_STATE")
    implementation = static_freeze["implementation"]
    amendment = c.make_amendment(implementation)
    approved_row, approved_header = p.approved_input_member(
        approved_inputs_raw, amendment=amendment)
    approved = c.document(approved_inputs_raw, limit=1_048_576, newline=True)
    c.require(approved['reconciliation']['journal_transition']['source_files'] == {
        name:dict(bytes=len(raw),sha256=c.sha256(raw))
        for name,raw in static_freeze['journal_sources'].items()}, 'CORE_FREEZE_JOURNAL_SOURCE')
    binding = local_anchor["binding_preimage"]
    writer = copy.deepcopy(c.validate_local_writer(binding["writer"]))
    tokens, argv = local_anchor["tokens"], local_anchor["argv"]
    local_digest = entry_api.local_management_binding_digest(
        binding, tokens=tokens, argv=argv, wrapper_raw=local_anchor["wrapper_bytes"])
    c.require(binding["remote_expectation"] == approved["policy_basis"]["remote_expectation"],
              "CORE_FREEZE_REMOTE_EXPECTATION")
    policy_raw = c.exact(local_anchor.get("policy_source_raw"),
                        {"fixture_cloud_config", "identity_public", "known_hosts"},
                        "CORE_FREEZE_POLICY_RAW_SET")
    for role in ("fixture_cloud_config", "identity_public", "known_hosts"):
        source = approved["policy_basis"][role]
        raw = policy_raw[role]
        c.require(source["binding_pointer"] == "/" + role
                  and type(raw) is bytes and len(raw) == binding[role]["bytes"]
                  and c.sha256(raw) == source["sha256"] == binding[role]["sha256"],
                  "CORE_FREEZE_POLICY_SOURCE")
    # A source-less envelope verifier cannot derive the authorized key from a
    # digest. Reconstruct all predicates from the bytes actually held above;
    # a different valid key plus recomputed predicate hashes must still fail.
    rebuilt_policy = entry_api.static_policy_basis(source_raw=policy_raw, tokens=tokens)
    c.require(c.canonical(approved["policy_basis"]) == c.canonical(rebuilt_policy),
              "CORE_FREEZE_POLICY_RAW_RELATION")
    p.validate_locators(locators, local_digest)
    rows = list(static_freeze["members"])
    values = dict(static_freeze["member_bytes"])
    c.require(approved_row["path"] not in values
              and not any(row["path"] == approved_row["path"] for row in rows),
              "CORE_FREEZE_APPROVED_DUPLICATE")
    rows.append(approved_row)
    values[approved_row["path"]] = approved_inputs_raw
    frozen_entry = {"carrier_argv_sha256": entry_api.argv_digest(argv),
                    "local_management_binding_sha256": local_digest, "writer": writer}
    for role in ("loader", "bootstrap", "dispatcher"):
        path = f"field/{role}.py"
        raw = values[path]
        frozen_entry.update({role + "_path": path, role + "_bytes": len(raw),
                             role + "_sha256": c.sha256(raw)})
    c.require(tokens == entry_api.remote_tokens(values["field/loader.py"],
                                                values["field/bootstrap.py"]),
              "CORE_FREEZE_REMOTE_TOKENS")
    manifest = p.make_manifest(implementation=implementation, amendment=amendment,
        approved_inputs=approved_header, entry=frozen_entry, locators=locators, members=rows)
    raw = p.build_package(manifest, values)
    # An independent framing construction checks ordering and exact byte
    # lengths; it does not stand in for D4's independent source/release review.
    serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
    second = b"LHCFP1\n" + len(serialized).to_bytes(8, "big") + serialized
    second += b"".join(values[row["path"]] for row in sorted(rows, key=lambda row: row["path"]))
    c.require(raw == second, "CORE_FREEZE_PACKAGE_DOUBLE_BUILD")
    first_manifest, first_values = p.parse_package(raw)
    second_manifest, second_views = bootstrap_api.parse_package(
        second, bootstrap_sha256=frozen_entry["bootstrap_sha256"])
    second_values = {path: bytes(raw) for path, raw in second_views.items()}
    c.require(first_manifest == second_manifest == manifest and first_values == second_values == values,
              "CORE_FREEZE_PACKAGE_ROUNDTRIP")
    c.require(c.canonical(first_manifest["entry"]["writer"]) == c.canonical(binding["writer"]),
              "CORE_FREEZE_WRITER_BINDING")
    return {"schema": FREEZE_SCHEMA, "state": "PACKAGE_FROZEN", "issuance": "NOT_ISSUED",
            "missing": [], "package": {"bytes": len(raw), "sha256": c.sha256(raw)},
            "package_raw": raw, "manifest": manifest, "member_bytes": values,
            "binding_preimage": binding, "wrapper_bytes": local_anchor["wrapper_bytes"],
            "origins": dict(local_anchor["origins"]), "directory_fd": local_anchor["directory_fd"]}


def prepare_delivery_package(*, static_freeze, approved_inputs_raw, retained_paths,
                             anchor_root, cwd, approved_sources=None, environment=None,
                             clock_gettime_ns=time.clock_gettime_ns):
    """Freeze one releasable package in the same window as subsequent delivery.

    The static dispatcher gate is checked before any current anchor, process,
    absence or filesystem observation. Unreviewed field bytes cannot pass it.
    A successful result transfers the held directory fd to the caller; any
    failure closes it and creates no marker or persistent output.
    """
    values = _validate_static_freeze(static_freeze)
    # This second source-aware validation is mandatory for the delivery-facing
    # API. A format-valid standalone artifact does not prove its private inputs.
    approved_sources = _validate_approved_sources(approved_inputs_raw, approved_sources)
    c.require(approved_sources.journal_sources == static_freeze['journal_sources'],
              'CORE_FREEZE_JOURNAL_SOURCE')
    p.approved_input_member(approved_inputs_raw,
                           amendment=c.make_amendment(static_freeze["implementation"]))
    c.require(c.sha256(values["field/dispatcher.py"])
              in entry_api.RELEASABLE_DISPATCHER_SHA256, "CORE_FIELD_IMPLEMENTATION_NOT_RELEASABLE")
    tokens = entry_api.remote_tokens(values["field/loader.py"], values["field/bootstrap.py"])
    c.require(approved_sources.remote_tokens == tokens, "CORE_FREEZE_APPROVED_SOURCE_TOKENS")
    origins = entry_api.freeze_host_window(clock_gettime_ns)
    local = inspect_management_anchor(anchor_root=anchor_root, cwd=cwd, origins=origins,
        tokens=tokens, environment=environment, clock_gettime_ns=clock_gettime_ns)
    try:
        deadline = entry_api.capture_contract.Deadline(origins, clock_gettime_ns)
        c.require(local["policy_source_raw"] == approved_sources.policy_sources,
                  "CORE_FREEZE_APPROVED_LOCAL_SOURCE")
        approved = c.document(approved_inputs_raw, limit=c.APPROVED_INPUTS_LIMIT, newline=True)
        prior_files, diagnostic_files, journal_files = entry_api.read_prior_originals(local['directory_fd'],
            local['binding_preimage']['anchor'], approved, deadline)
        c.require(journal_files == approved_sources.journal_files,'CORE_FREEZE_JOURNAL_LOCAL_SOURCE')
        c.require(prior_files == approved_sources.prior_core_files, 'CORE_FREEZE_PRIOR_LOCAL_SOURCE')
        c.require(diagnostic_files == approved_sources.prior_diagnostic_files, 'CORE_FREEZE_DIAGNOSTIC_LOCAL_SOURCE')
        deadline.call(entry_api.encoded_argv_environment_size,
                      local["argv"], local["binding_preimage"]["environment"])
        frozen_locators = deadline.call(freeze_private_locators, **retained_paths,
            local_management_binding_preimage=local["binding_preimage"],
            management_tokens=tokens, management_argv=local["argv"],
            management_wrapper_raw=local["wrapper_bytes"])
        frozen = deadline.call(build_frozen_package, static_freeze=static_freeze,
            local_anchor=local, locators=frozen_locators["locators"],
            approved_inputs_raw=approved_inputs_raw)
        deadline.call(entry_api.field_release_gate, frozen["manifest"], frozen["member_bytes"])
        c.require(entry_api.capture_contract.observe_writer(deadline.call)
                  == local["binding_preimage"]["writer"], "CORE_FREEZE_WRITER_CHANGED")
        deadline.check()
        return frozen
    except BaseException:
        os.close(local["directory_fd"])
        raise


def _validate_approved_sources(raw, sources):
    """Bridge ordinary/package imports without relaxing raw-source validation.

    Dataclass identity depends on its import namespace. Transfer only the exact
    documented data fields into the verifier's own class, then run that full
    verifier. A same-named class, loose dictionary or extra field is insufficient.
    """
    c.require(sources is not None, "CORE_FREEZE_APPROVED_SOURCES_REQUIRED")
    names = {"amendment", "locator_carriers", "horizon_archives", "legacy_frame",
             "historical_tools", "policy_sources", "remote_tokens", "later_reviews", "producer_raw",
             "prior_core_files", "prior_diagnostic_files", "journal_files", "journal_sources", "journal_frozen"}
    c.require(not isinstance(sources, type) and is_dataclass(sources)
              and {field.name for field in fields(sources)} == names,
              "CORE_FREEZE_APPROVED_SOURCE_FIELDS")
    module = p._approved_module()
    values = {name: copy.deepcopy(getattr(sources, name)) for name in names}
    converted = module.ApprovedInputSources(**values)
    module.validate(raw, sources=converted)
    return converted
