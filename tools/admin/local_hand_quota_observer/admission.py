"""Q1 fixed-object data checks, not an OS admission or a client interface.

The caller must acquire a protected administrator manifest before using this
module. These routines do no filesystem I/O and do not establish that protection.
They accept a pinned byte snapshot, never paths/FDs supplied by a job. All returned
objects are immutable. Loading, namespace binding and launch remain separate.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat


MAX_MANIFEST_BYTES = 32768
MAX_SLOTS = 32
MAX_REPORT_BYTES = 4095
UINT64_MAX = 2**64 - 1
PROJECT_INHERIT = 0x200
FS_MAGIC = {"ext4": 0xEF53, "xfs": 0x58465342}
UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"


class Rejected(ValueError):
    """Stable internal reason; no arbitrary input is echoed in error text."""


def require(condition, code):
    if not condition:
        raise Rejected(code)


def fields(value, expected):
    require(type(value) is dict and set(value) == set(expected), "FIELDS")
    return value


def integer(value, low=0, high=UINT64_MAX):
    require(type(value) is int and low <= value <= high, "INTEGER")
    return value


def token(value, pattern):
    require(type(value) is str and re.fullmatch(pattern, value) is not None, "TOKEN")
    return value


def path(value):
    # Keep future argv and systemd property serialization unambiguous. This is
    # lexical validation only; it does NOT prove mount type or reject symlinks.
    # Instantiated systemd user managers contain a literal @ (user@UID.service).
    token(value, r"/[A-Za-z0-9_./@-]{1,1023}")
    require(str(PurePosixPath(value)) == value and not value.startswith("//")
            and ".." not in PurePosixPath(value).parts and value != "/", "PATH")
    return value


def strict_json(raw, maximum, *, depth=6):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "BYTE_LIMIT")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_KEY")
            result[key] = value
        return result

    def no_constant(_):
        raise Rejected("JSON_CONSTANT")

    def small_int(value):
        require(len(value) <= 21, "INTEGER_SIZE")
        return int(value)

    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                           parse_constant=no_constant, parse_float=no_constant,
                           parse_int=small_int)
        pending = [(value, 0)]
        nodes = 0
        while pending:
            item, level = pending.pop()
            nodes += 1
            require(level <= depth and nodes <= 4096, "JSON_COMPLEXITY")
            if type(item) is dict:
                pending.extend((child, level + 1) for pair in item.items() for child in pair)
            elif type(item) is list:
                pending.extend((child, level + 1) for child in item)
            elif type(item) is str:
                item.encode("utf-8", "strict")
        return value
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, Rejected):
            raise
        raise Rejected("JSON") from error


@dataclass(frozen=True)
class Root:
    device: int
    inode: int
    uid: int
    gid: int
    mode: int

    @classmethod
    def decode(cls, value):
        fields(value, ("device", "inode", "uid", "gid", "mode"))
        root = cls(integer(value["device"]), integer(value["inode"], 1),
                   integer(value["uid"], 1, 2**32 - 2),
                   integer(value["gid"], 0, 2**32 - 2), integer(value["mode"], 0, 0o177777))
        require(stat.S_ISDIR(root.mode) and root.mode & 0o7777 == 0o700, "PRIVATE_ROOT")
        return root


@dataclass(frozen=True)
class Slot:
    ref: str
    generation: str
    path: str
    filesystem: str
    filesystem_uuid: str
    root: Root
    project_id: int
    xflags: int
    hard_bytes: int

    @classmethod
    def decode(cls, value):
        fields(value, ("ref", "generation", "path", "filesystem", "filesystem_uuid",
                       "root", "project_id", "xflags", "hard_bytes"))
        fs = token(value["filesystem"], r"ext4|xfs")
        flags = integer(value["xflags"], 0, 2**32 - 1)
        limit = integer(value["hard_bytes"], 1024)
        require(flags & PROJECT_INHERIT and limit % 1024 == 0, "PROJECT_LIMIT")
        return cls(token(value["ref"], r"[a-z0-9][a-z0-9_.-]{0,63}"),
                   token(value["generation"], r"[0-9a-f]{32}"), path(value["path"]), fs,
                   token(value["filesystem_uuid"], UUID), Root.decode(value["root"]),
                   integer(value["project_id"], 1, 2**32 - 1), flags, limit)


@dataclass(frozen=True)
class Manifest:
    digest: str
    authority_digest: str
    installation_digest: str
    source_commit: str
    boot_id: str
    epoch: str
    query_uid: int
    query_euid: int
    abi: tuple[int, int, int]
    cgroup_parent: str
    max_query_ns: int
    slots: tuple[Slot, ...]
    hard_capacity_bytes: int

    def slot(self, ref, generation):
        token(ref, r"[a-z0-9][a-z0-9_.-]{0,63}")
        token(generation, r"[0-9a-f]{32}")
        matches = [slot for slot in self.slots if slot.ref == ref and slot.generation == generation]
        require(len(matches) == 1, "SLOT_GENERATION")
        return matches[0]


def decode_manifest(raw, expected_digest):
    """Validate exact pinned bytes; digest equality is not origin authentication."""
    token(expected_digest, r"[0-9a-f]{64}")
    require(type(raw) is bytes and len(raw) <= MAX_MANIFEST_BYTES, "BYTE_LIMIT")
    require(hashlib.sha256(raw).hexdigest() == expected_digest, "MANIFEST_DIGEST")
    value = fields(strict_json(raw, MAX_MANIFEST_BYTES), (
        "schema", "authority_digest", "installation_digest", "source_commit", "boot_id", "epoch",
        "query_uid", "query_euid", "abi", "cgroup_parent", "max_query_ns", "slots"))
    require(value["schema"] == "local-hand-quota-q1-manifest/v1", "MANIFEST_VERSION")
    abi = fields(value["abi"], ("fsxattr_bytes", "dqblk_bytes", "qstatv_bytes"))
    sizes = tuple(integer(abi[key], 1, 1024) for key in ("fsxattr_bytes", "dqblk_bytes", "qstatv_bytes"))
    require(sizes[0] == 28, "FSXATTR_ABI")
    require(type(value["slots"]) is list and 1 <= len(value["slots"]) <= MAX_SLOTS, "SLOT_LIMIT")
    slots = tuple(Slot.decode(item) for item in value["slots"])
    require(len({slot.ref for slot in slots}) == len(slots), "SLOT_ALIAS")
    require(len({(slot.root.device, slot.root.inode) for slot in slots}) == len(slots), "ROOT_ALIAS")
    paths = [PurePosixPath(slot.path) for slot in slots]
    for index, current in enumerate(paths):
        for other in paths[index + 1:]:
            require(current != other and current not in other.parents and other not in current.parents,
                    "ROOT_OVERLAP")
    devices, filesystems, domains = {}, {}, {}
    for slot in slots:
        fs = (slot.filesystem_uuid, slot.filesystem)
        require(devices.setdefault(slot.root.device, fs) == fs, "FILESYSTEM_ALIAS")
        require(filesystems.setdefault(slot.filesystem_uuid, (slot.root.device, slot.filesystem))
                == (slot.root.device, slot.filesystem), "FILESYSTEM_ALIAS")
        domain = (slot.filesystem_uuid, slot.project_id)
        require(domains.setdefault(domain, slot.hard_bytes) == slot.hard_bytes, "DOMAIN_LIMIT")
    capacity = integer(sum(domains.values()), 1024)
    return Manifest(expected_digest, token(value["authority_digest"], r"[0-9a-f]{64}"),
                    token(value["installation_digest"], r"[0-9a-f]{64}"),
                    token(value["source_commit"], r"[0-9a-f]{40}"), token(value["boot_id"], UUID),
                    token(value["epoch"], r"[0-9a-f]{32}"), integer(value["query_uid"], 0, 2**32 - 2),
                    integer(value["query_euid"], 0, 2**32 - 2), sizes, path(value["cgroup_parent"]),
                    integer(value["max_query_ns"], 1, 30_000_000_000), slots, capacity)


SUCCESS_CALLS = ("fstat.before", "fcntl.getfl", "fstatfs", "ioctl.fsgetxattr.before",
                 "prctl.no_new_privs", "seccomp.install",
                 "quotactl_fd.state.before", "quotactl_fd.getquota", "ioctl.fsgetxattr.after",
                 "fstat.after", "quotactl_fd.state.after", "close.root")
REPORT_FIELDS = ("schema", "status", "code", "real_e3_accepted", "production_supported",
                 "admission_proven", "quota_syscall_attempts", "uid", "euid", "root_fd", "abi",
                 "root", "filesystem_magic", "project", "enforcement", "quota", "root_after",
                 "project_after", "enforcement_after", "calls", "restriction")


def match_report(raw, manifest, slot):
    """Return decoded native facts only if they match the pinned Q1 object.

    The caller must additionally prove the independent query invocation exited.
    Magic equality alone does not verify ext4 vs ext2/3, UUID or namespace.
    """
    require(slot in manifest.slots, "FOREIGN_SLOT")
    require(type(raw) is bytes and raw.endswith(b"\n"), "INCOMPLETE_REPORT")
    value = fields(strict_json(raw, MAX_REPORT_BYTES, depth=4), REPORT_FIELDS)
    require(value["schema"] == "local-hand-quota-abi/v2", "REPORT_VERSION")
    require(value["status"] == "OBSERVED" and value["code"] == "QUOTA_FACTS_OBSERVED", "QUERY_FAILED")
    for flag in ("real_e3_accepted", "production_supported", "admission_proven"):
        require(value[flag] is False, "UNSUPPORTED_CLAIM")
    require(integer(value["uid"], 0, 2**32 - 2) == manifest.query_uid
            and integer(value["euid"], 0, 2**32 - 2) == manifest.query_euid, "QUERY_UID")
    require(integer(value["root_fd"]) == 3 and integer(value["quota_syscall_attempts"]) == 3, "QUERY_SHAPE")
    restriction = fields(value["restriction"], ("profile", "no_new_privs", "filter_installed", "project_id"))
    require(restriction["profile"] == "quota-fd-readonly/v1"
            and restriction["no_new_privs"] is True and restriction["filter_installed"] is True
            and integer(restriction["project_id"], 1, 2**32 - 1) == slot.project_id, "QUERY_RESTRICTION")
    abi = fields(value["abi"], ("fsxattr_bytes", "dqblk_bytes", "qstatv_bytes"))
    require(tuple(integer(abi[key], 1, 1024) for key in
                  ("fsxattr_bytes", "dqblk_bytes", "qstatv_bytes")) == manifest.abi, "ABI_CHANGED")
    for key in ("root", "root_after"):
        require(Root.decode(value[key]) == slot.root, "ROOT_CHANGED")
    require(integer(value["filesystem_magic"]) == FS_MAGIC[slot.filesystem], "FILESYSTEM_CHANGED")
    for key in ("project", "project_after"):
        project = fields(value[key], ("id", "xflags"))
        require(integer(project["id"], 1, 2**32 - 1) == slot.project_id
                and integer(project["xflags"], 0, 2**32 - 1) == slot.xflags, "PROJECT_CHANGED")
    states = []
    for key in ("enforcement", "enforcement_after"):
        state = fields(value[key], ("version", "flags"))
        require(integer(state["version"]) == 1 and integer(state["flags"], 0, 65535) & 0x30 == 0x30,
                "ENFORCEMENT_UNPROVEN")
        states.append(state)
    require(states[0] == states[1], "ENFORCEMENT_CHANGED")
    quota = fields(value["quota"], ("valid_mask", "hard_blocks_1024", "hard_bytes"))
    require(integer(quota["valid_mask"], 0, 255) & 1 == 1, "LIMIT_UNPROVEN")
    require(integer(quota["hard_blocks_1024"], 1, UINT64_MAX // 1024) * 1024 == slot.hard_bytes
            and integer(quota["hard_bytes"], 1) == slot.hard_bytes, "LIMIT_CHANGED")
    calls = value["calls"]
    require(type(calls) is list and len(calls) == len(SUCCESS_CALLS), "CALL_SEQUENCE")
    for call, name in zip(calls, SUCCESS_CALLS):
        fields(call, ("name", "rc", "errno"))
        require(call["name"] == name, "CALL_SEQUENCE")
        rc = integer(call["rc"], 0, 2**63 - 1)
        integer(call["errno"], 0, 4095)  # A successful call may leave stale errno.
        if name == "fcntl.getfl":
            require(hasattr(os, "O_PATH") and rc & (os.O_ACCMODE | os.O_PATH) == 0, "FD_MODE")
        else:
            require(rc == 0, "CALL_FAILED")
    return value
