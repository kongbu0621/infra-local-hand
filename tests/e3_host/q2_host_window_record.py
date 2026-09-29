"""Create-only host consumption; no remote command and no replacement clock.

Filesystem support is deliberately narrow: small, linear directories on an
ext4 filesystem whose real block-device superblock proves 4 KiB non-bigalloc
geometry. Unsupported or unreadable storage is rejected before mkdir. Tests
which substitute qualification exercise syscalls, not production durability.
"""
from __future__ import annotations

import copy
import errno
import fcntl
import importlib.util
import os
from pathlib import Path
import re
import stat
import struct


def helper(name):
    spec = importlib.util.spec_from_file_location("_host_window_record_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c, io = helper("q2_host_window_contract"), helper("q2_reconciliation_io")
require, keys, number, sha, encoded = c.require, c.keys, c.number, c.sha, c.encoded
PRECHECK_SCHEMA = "local-hand-q2-host-window-precheck/v1"
ORDINARY_PRECHECK_SCHEMA = "local-hand-q2-host-window-precheck/v2"
FILESYSTEM_SCHEMA = "local-hand-q2-host-window-ext4/v1"
EVIDENCE_SCHEMA = "local-hand-q2-host-window-consumption/v1"
ORDINARY_EVIDENCE_SCHEMA = "local-hand-q2-host-window-consumption/v2"
PARENT_ALLOCATION_SCHEMA = "local-hand-q2-host-window-parent-allocation/v1"
PRECHECK_FIELDS = ("schema", "location_sha256", "window", "boot_id", "parent_metadata",
    "filesystem", "host_bill_sha256", "host_bill_summary", "limits")
FILESYSTEM_FIELDS = ("schema", "device", "mount_id", "mountpoint", "source", "mountinfo_sha256",
    "superblock_sha256", "block_size", "cluster_size", "parent_flags", "parent_size",
    "available_bytes", "free_inodes", "allocation_bound", "logical_bound", "inode_bound")
BLOCK = 4096
# Mapped-object bound: at most three payload blocks, one child-directory block
# and one parent-growth block. Each object stays within the four extent slots
# in its inode; the parent starts with exactly one block and filesystem-wide
# directory indexing is disabled. Filesystem journal/allocator work is NOT
# proved by geometry: original native-audit coverage remains field-blocked.
ALLOCATION_BOUND = 16 * BLOCK
INTENT_LIMIT = c.LOGICAL_LIMIT - BLOCK
FS_IOC_GETFLAGS = 0x80086601
FS_INDEX_FL, FS_EXTENTS_FL = 0x1000, 0x80000
BOOT_PATH = "/proc/sys/kernel/random/boot_id"


def _identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, uid=info.st_uid,
        gid=info.st_gid, mode=stat.S_IMODE(info.st_mode))


def _acl_absent(fd):
    for name in ("system.posix_acl_access", "system.posix_acl_default"):
        try:
            os.getxattr(fd, name)
        except OSError as error:
            require(error.errno == errno.ENODATA, "HOST_WINDOW_ACL_UNPROVEN")
        else:
            raise ValueError("HOST_WINDOW_ACL_PRESENT")


def _protected_chain(held):
    """O_PATH ancestors are re-opened only through their held fd for ACL reads."""
    for _, fd, before in held.chain:
        held.guard()
        opened = os.open(".", io.flags(True), dir_fd=fd)
        try:
            info = os.fstat(opened)
            require(all(io.metadata(info)[key] == before[key] for key in io.ANCESTOR_FIELDS),
                "HOST_WINDOW_ANCESTOR_CHANGED")
            io.protected(info, True, allowed_uids={0})
            _acl_absent(opened)
        finally:
            os.close(opened)


def _current_operator():
    """Capture stable process credentials only; no procfs or privilege query.

    Repeating the sample rejects observed transitions, not changes which occur
    and revert entirely between samples. No fsuid/capability/userns claim.
    """
    require(all(hasattr(os, name) for name in ("getresuid", "getresgid", "getgroups")),
        "HOST_WINDOW_OPERATOR_UNSUPPORTED")
    first_uid, first_gid = os.getresuid(), os.getresgid()
    first_groups = sorted(os.getgroups())
    last_uid, last_gid = os.getresuid(), os.getresgid()
    last_groups = sorted(os.getgroups())
    require(first_uid == last_uid and first_gid == last_gid and first_groups == last_groups,
        "HOST_WINDOW_OPERATOR_CHANGED")
    return c.validate_operator(dict(schema=c.OPERATOR_SCHEMA, uid=list(first_uid),
        gid=list(first_gid), groups=first_groups))


def _ordinary_acl_absent(fd, guard):
    for name in ("system.posix_acl_access", "system.posix_acl_default"):
        guard()
        try:
            os.getxattr(fd, name)
        except OSError as error:
            require(error.errno == errno.ENODATA, "HOST_WINDOW_ACL_UNPROVEN")
        else:
            raise ValueError("HOST_WINDOW_ACL_PRESENT")
        guard()


def _protected_chain_ordinary(held):
    """Metadata-only ancestor ACL checks; these fds never read or enumerate."""
    for _, fd, before in held.chain:
        held.guard()
        opened = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        try:
            held.guard()
            info = os.fstat(opened)
            current = io.metadata(info)
            require(all(current[key] == before[key] for key in io.ANCESTOR_FIELDS),
                "HOST_WINDOW_ANCESTOR_CHANGED")
            io.protected(info, True, allowed_uids=held.allowed_uids)
            _ordinary_acl_absent(opened, held.guard)
            held.guard()
            require(io.metadata(os.fstat(opened)) == current, "HOST_WINDOW_ANCESTOR_CHANGED")
        finally:
            os.close(opened)
    _ordinary_chain_binding(held)


def _ordinary_chain_binding(held):
    """Rebind all names after ACL work, without freezing parent timestamps."""
    for index, (name, fd, before) in enumerate(held.chain):
        held.guard()
        current = io.metadata(os.fstat(fd))
        by_name = io.metadata(os.stat("/", follow_symlinks=False) if index == 0 else
            os.stat(name, dir_fd=held.chain[index-1][1], follow_symlinks=False))
        require(all(current[key] == by_name[key] == before[key] for key in io.ANCESTOR_FIELDS),
            "HOST_WINDOW_ANCESTOR_CHANGED")
    held.guard()


def _special(path, guard, limit):
    # proc reports zero st_size for bounded text; ordinary raw sources continue
    # to use read_pinned and its exact size/content checks.
    with io.HeldPath(path, guard, allowed_uids={0}) as held:
        guard()
        raw = os.read(held.fd, limit + 1)
        require(len(raw) <= limit and not os.read(held.fd, 1), "HOST_WINDOW_KERNEL_FACT_LIMIT")
        held.verify()
        return raw


def _boot(guard):
    raw = _special(BOOT_PATH, guard, 64)
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "HOST_WINDOW_BOOT_FORMAT")
    return c.boot(raw[:-1].decode("ascii"))


def _absent(parent_fd):
    try:
        os.stat(c.DIRECTORY_NAME, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise ValueError("HOST_WINDOW_ALREADY_CONSUMED")


def _mount(parent, guard):
    raw = _special("/proc/" + str(os.getpid()) + "/mountinfo", guard, 1024**2)
    rows = []
    for line in raw.decode("ascii").splitlines():
        parts = line.split(" ")
        require("-" in parts, "HOST_WINDOW_MOUNTINFO")
        sep = parts.index("-")
        require(sep >= 6 and len(parts) == sep + 4, "HOST_WINDOW_MOUNTINFO")
        mountpoint = parts[4]
        if parent.path == mountpoint or parent.path.startswith(mountpoint.rstrip("/") + "/"):
            rows.append((len(mountpoint), parts, sep))
    require(rows, "HOST_WINDOW_MOUNT_NOT_FOUND")
    _, row, sep = max(rows, key=lambda value: value[0])
    info = os.fstat(parent.fd)
    require(row[2] == str(os.major(info.st_dev)) + ":" + str(os.minor(info.st_dev))
        and row[3] == "/" and row[sep + 1] == "ext4", "HOST_WINDOW_FILESYSTEM_UNSUPPORTED")
    options = set(row[5].split(",")) | set(row[sep + 3].split(","))
    require("rw" in options and "ro" not in options and not options.intersection(
        {"nobarrier", "barrier=0", "dax", "dax=always", "data=writeback", "fsync=volatile"}),
        "HOST_WINDOW_DURABILITY_UNPROVEN")
    source = c.path(row[sep + 2])
    require(source.startswith("/dev/") and "\\" not in row[4], "HOST_WINDOW_DEVICE_SOURCE")
    return dict(mount_id=int(row[0]), mountpoint=c.path(row[4]) if row[4] != "/" else "/",
        source=source, mountinfo_sha256=sha(raw))


def _superblock(source, device, guard):
    # Mountinfo supplies the kernel-selected device name. Its actual block rdev
    # must match the held directory's device; aliases/symlinks are refused.
    parent_path, name = source.rsplit("/", 1)
    with io.HeldPath(parent_path, guard, directory=True, allowed_uids={0}) as parent:
        _protected_chain(parent)
        guard()
        fd = os.open(name, io.flags(), dir_fd=parent.fd)
        try:
            before = os.fstat(fd)
            require(stat.S_ISBLK(before.st_mode) and before.st_rdev == device and before.st_uid == 0
                and before.st_nlink == 1 and not before.st_mode & 0o6022, "HOST_WINDOW_BLOCK_DEVICE")
            require(io.metadata(os.stat(name, dir_fd=parent.fd, follow_symlinks=False)) == io.metadata(before),
                "HOST_WINDOW_BLOCK_DEVICE_CHANGED")
            _acl_absent(fd)
            guard()
            raw = os.pread(fd, 1024, 1024)
            require(len(raw) == 1024 and io.metadata(os.fstat(fd)) == io.metadata(before),
                "HOST_WINDOW_SUPERBLOCK_READ")
            require(io.metadata(os.stat(name, dir_fd=parent.fd, follow_symlinks=False)) == io.metadata(before),
                "HOST_WINDOW_BLOCK_DEVICE_CHANGED")
            parent.verify()
            return raw
        finally:
            os.close(fd)


def _geometry(raw):
    require(type(raw) is bytes and len(raw) == 1024 and struct.unpack_from("<H", raw, 56)[0] == 0xEF53,
        "HOST_WINDOW_EXT4_SUPERBLOCK")
    block_log, cluster_log = struct.unpack_from("<II", raw, 24)
    compat, incompat, rocompat = struct.unpack_from("<III", raw, 92)
    require(block_log == cluster_log == 2 and compat & 0x4 and not compat & 0x20 and incompat & 0x40
        and not incompat & (0x1 | 0x8 | 0x8000 | 0x10000 | 0x20000)
        and not rocompat & 0x200, "HOST_WINDOW_EXT4_GEOMETRY")
    return BLOCK, BLOCK


def filesystem(parent, guard):
    """Read-only local proof. No trial writes, caller asserted limits or fallback."""
    guard(); mount = _mount(parent, guard)
    info = os.fstat(parent.fd)
    raw = _superblock(mount["source"], info.st_dev, guard)
    block_size, cluster_size = _geometry(raw)
    flags = struct.unpack("I", fcntl.ioctl(parent.fd, FS_IOC_GETFLAGS, struct.pack("I", 0))[:4])[0]
    require(flags & FS_EXTENTS_FL and not flags & ~FS_EXTENTS_FL,
        "HOST_WINDOW_PARENT_FLAGS_UNSUPPORTED")
    require(info.st_size == BLOCK and info.st_blocks * 512 == BLOCK,
        "HOST_WINDOW_PARENT_GEOMETRY")
    available = os.fstatvfs(parent.fd)
    require(available.f_bsize == available.f_frsize == BLOCK
        and available.f_bavail * available.f_frsize >= ALLOCATION_BOUND
        and available.f_favail >= c.INODE_LIMIT, "HOST_WINDOW_LOCAL_CAPACITY")
    parent.verify()
    return dict(schema=FILESYSTEM_SCHEMA, device=info.st_dev, **mount,
        superblock_sha256=sha(raw), block_size=block_size, cluster_size=cluster_size,
        parent_flags=flags, parent_size=info.st_size,
        available_bytes=available.f_bavail * available.f_frsize, free_inodes=available.f_favail,
        allocation_bound=ALLOCATION_BOUND, logical_bound=c.LOGICAL_LIMIT, inode_bound=c.INODE_LIMIT)


def _validate_precheck(value, location, window, *, ordinary):
    keys(value, PRECHECK_FIELDS + (("operator",) if ordinary else ()))
    c.validate_location(location); c.validate_window(window)
    require(value["schema"] == (ORDINARY_PRECHECK_SCHEMA if ordinary else PRECHECK_SCHEMA)
        and value["location_sha256"] == sha(encoded(location))
        and value["window"] == window and value["boot_id"] == location["expected_boot_id"]
        and value["limits"] == c.RESERVATION, "HOST_WINDOW_PRECHECK_BINDING")
    meta = value["parent_metadata"]
    keys(meta, io.META_FIELDS)
    for key in meta:
        number(meta[key], 0)
    operator = c.validate_operator(value["operator"]) if ordinary else None
    require(stat.S_ISDIR(meta["st_mode"]) and meta["uid"] == (operator["uid"][1] if ordinary else 0)
        and not meta["st_mode"] & 0o6022,
        "HOST_WINDOW_PARENT_PROTECTION")
    if ordinary:
        require(meta["gid"] == operator["gid"][1], "HOST_WINDOW_PARENT_PROTECTION")
    fs = value["filesystem"]
    keys(fs, FILESYSTEM_FIELDS)
    require(fs["schema"] == FILESYSTEM_SCHEMA and fs["device"] == meta["device"]
        and fs["block_size"] == fs["cluster_size"] == BLOCK and fs["parent_flags"] == FS_EXTENTS_FL
        and fs["parent_size"] == meta["size"] == BLOCK and meta["blocks"] * 512 == BLOCK
        and (fs["allocation_bound"], fs["logical_bound"], fs["inode_bound"])
            == (ALLOCATION_BOUND, c.LOGICAL_LIMIT, c.INODE_LIMIT), "HOST_WINDOW_FILESYSTEM_PROOF")
    for key in ("device", "mount_id", "block_size", "cluster_size", "parent_flags", "parent_size",
                "available_bytes", "free_inodes", "allocation_bound", "logical_bound", "inode_bound"):
        number(fs[key], 1)
    require(fs["available_bytes"] >= ALLOCATION_BOUND and fs["free_inodes"] >= c.INODE_LIMIT,
        "HOST_WINDOW_LOCAL_CAPACITY")
    if fs["mountpoint"] != "/":
        c.path(fs["mountpoint"])
    c.path(fs["source"])
    require(fs["source"].startswith("/dev/"), "HOST_WINDOW_DEVICE_SOURCE")
    for key in ("mountinfo_sha256", "superblock_sha256"):
        c.digest(fs[key])
    c.digest(value["host_bill_sha256"])
    summary = value["host_bill_summary"]
    keys(summary, ("host_id", "guest_id", "inventory_sha256", "coverage_sha256", "actual", "future",
        "total", "categories", "by_device", "obligations", "marker", "early_audit",
        "local_admissible", "joint_admission_proven"))
    for name in ("host_id", "guest_id", "inventory_sha256", "coverage_sha256"):
        c.digest(summary[name])
    require(summary["host_id"] == c.ATTESTATION_SHA256 and summary.get("local_admissible") is True
        and summary.get("joint_admission_proven") is False and type(summary.get("marker")) is dict,
        "HOST_WINDOW_HOST_BILL")
    keys(summary["marker"], ("path", "device", "state", "commitment", "actual", "logical_limit", "intent_sha256"))
    require(summary["marker"].get("path") == location["directory"]
        and summary["marker"].get("device") == meta["device"]
        and summary["marker"].get("state") == "ABSENT"
        and summary["marker"]["commitment"] == dict(bytes=c.BYTE_LIMIT, inodes=c.INODE_LIMIT)
        and summary["marker"]["actual"] == dict(bytes=0, inodes=0)
        and summary["marker"]["logical_limit"] == c.LOGICAL_LIMIT
        and summary["marker"]["intent_sha256"] is None, "HOST_WINDOW_HOST_BILL_MARKER")
    require(len(encoded(value)) <= INTENT_LIMIT, "HOST_WINDOW_PRECHECK_LIMIT")
    return copy.deepcopy(value)


def validate_precheck(value, location, window):
    return _validate_precheck(value, location, window, ordinary=False)


def validate_precheck_ordinary(value, location, window):
    return _validate_precheck(value, location, window, ordinary=True)


class HeldPrecheck:
    proof_schema = PRECHECK_SCHEMA
    intent_schema = c.INTENT_SCHEMA
    evidence_schema = EVIDENCE_SCHEMA
    owner_uid = owner_gid = 0
    allowed_uids = frozenset({0})
    maximum_identity_number = 2**63 - 1

    def __init__(self, location, binding, window, host_costs):
        c.require_field_readiness(binding)
        self.location = c.validate_location(location)
        self.binding = c.validate_binding(binding, self.location)
        self.window, self.origin = window, c.validate_window(window.fields())
        self.closed = False; self.spent = False; self.parent = None
        try:
            self._initialize_identity()
            self.preparation_guard()
            self.parent = io.HeldPath(location["parent"], self.preparation_guard, directory=True,
                allowed_uids=self.allowed_uids)
            self._check_parent(); self._protect_chain(self.parent); _absent(self.parent.fd)
            require(_boot(self.guard) == location["expected_boot_id"], "HOST_WINDOW_BOOT_CHANGED")
            facts = filesystem(self.parent, self.guard)
            summary = helper("q2_host_window_billing").validate_host_bill(host_costs)
            self.proof = self._validate_proof(dict(schema=self.proof_schema,
                location_sha256=sha(encoded(self.location)), window=self.origin,
                boot_id=location["expected_boot_id"], parent_metadata=io.metadata(os.fstat(self.parent.fd)),
                filesystem=facts, host_bill_sha256=sha(encoded(host_costs)), host_bill_summary=summary,
                limits=dict(c.RESERVATION), **self._operator_fields()), self.location, self.origin)
            self.bill = copy.deepcopy(host_costs)
            # Full worst-width identity encoded before the first write. Actual
            # directory identity can only shorten this bounded intent.
            maximum = self.intent(dict(device=self.maximum_identity_number, inode=self.maximum_identity_number,
                uid=self.owner_uid, gid=self.owner_gid, mode=0o700))
            require(len(encoded(maximum)) <= INTENT_LIMIT, "HOST_WINDOW_INTENT_LIMIT")
            self.verify()
        except BaseException:
            self.close()
            raise

    def _initialize_identity(self):
        pass

    def _identity_guard(self):
        require(os.geteuid() == 0 and os.getegid() == 0, "HOST_WINDOW_ROOT_REQUIRED")

    def _check_parent(self):
        pass

    def _operator_fields(self):
        return {}

    def _protect_chain(self, held):
        _protected_chain(held)

    def _acl(self, fd):
        _acl_absent(fd)

    def _created_file_check(self, fd, directory_fd):
        pass

    def _created_directory_check(self, fd):
        pass

    def _before_mkdir(self):
        pass

    def _validate_proof(self, value, location, window):
        return validate_precheck(value, location, window)

    def _verify_intent(self, raw):
        return c.verify_intent(raw, self.binding, self.location)

    def guard(self):
        # v1's writer identity is fixed across every observation, write and
        # retained-record verification, not just at constructor entry.
        self._identity_guard()
        require(self.window.fields() == self.origin, "HOST_WINDOW_ORIGIN_CHANGED")
        self.window.guard()

    def preparation_guard(self):
        self.guard()
        require(self.window.remaining_ns(self.origin["issued_ns"] + 140*c.NS) > 0,
            "HOST_WINDOW_PREPARATION_EXPIRED")

    def intent(self, identity):
        return dict(schema=self.intent_schema, scope=c.SCOPE, binding=copy.deepcopy(self.binding),
            window=dict(self.origin), directory_identity=identity, precheck=copy.deepcopy(self.proof),
            precheck_sha256=sha(encoded(self.proof)), reservation=dict(c.RESERVATION),
            window_consumed=True, owner_issued=False, run_permission="existing_startup_once",
            **self._operator_fields())

    def verify(self):
        require(not self.closed and not self.spent, "HOST_WINDOW_PRECHECK_SPENT")
        self.preparation_guard(); _absent(self.parent.fd)
        self.parent.verify(); self._check_parent(); self._protect_chain(self.parent)
        require(_boot(self.guard) == self.location["expected_boot_id"], "HOST_WINDOW_BOOT_CHANGED")
        _absent(self.parent.fd)
        require(helper("q2_host_window_billing").validate_host_bill(self.bill) == self.proof["host_bill_summary"],
            "HOST_WINDOW_HOST_BILL_CHANGED")
        return copy.deepcopy(self.proof)

    def consume(self):
        c.require_field_readiness(self.binding)
        self.verify(); self.spent = True
        record = HeldConsumption(self)
        try:
            record._create()
            self.parent = None  # ownership of every retained fd moves to record
            return record
        except BaseException:
            record.close(); self.parent = None
            raise

    def close(self):
        if not self.closed:
            self.closed = True
            if self.parent is not None:
                self.parent.close()


def precheck(location, binding, window, host_costs):
    return HeldPrecheck(location, binding, window, host_costs)


class HeldOrdinaryPrecheck(HeldPrecheck):
    """Explicit v2 writer; an ordinary process cannot opt into the v1 writer."""
    proof_schema = ORDINARY_PRECHECK_SCHEMA
    intent_schema = c.ORDINARY_INTENT_SCHEMA
    evidence_schema = ORDINARY_EVIDENCE_SCHEMA
    maximum_identity_number = 2**64 - 1

    def _initialize_identity(self):
        self._operator = _current_operator()

    @property
    def operator(self):
        return copy.deepcopy(self._operator)

    @property
    def owner_uid(self):
        return self._operator["uid"][1]

    @property
    def owner_gid(self):
        return self._operator["gid"][1]

    @property
    def allowed_uids(self):
        return frozenset({0, self.owner_uid})

    def _identity_guard(self):
        require(_current_operator() == self._operator, "HOST_WINDOW_OPERATOR_CHANGED")
        if hasattr(self, "proof"):
            require(self.proof.get("operator") == self._operator, "HOST_WINDOW_OPERATOR_CHANGED")

    def _operator_fields(self):
        return dict(operator=self.operator)

    def _check_parent(self):
        self.guard()
        info = os.fstat(self.parent.fd)
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == self.owner_uid
            and info.st_gid == self.owner_gid and not info.st_mode & 0o6022,
            "HOST_WINDOW_PARENT_PROTECTION")
        self.guard()

    def _protect_chain(self, held):
        _protected_chain_ordinary(held)

    def _acl(self, fd):
        _ordinary_acl_absent(fd, self.guard)

    def _created_file_check(self, fd, directory_fd):
        # Creation can be influenced by FS credentials or mount semantics not
        # described by getresuid/getresgid. Verify the real object BEFORE data.
        self.preparation_guard()
        self._created_directory_check(directory_fd)
        info = os.fstat(fd)
        before = io.metadata(info)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == 0
            and info.st_uid == self.owner_uid and info.st_gid == self.owner_gid
            and stat.S_IMODE(info.st_mode) == 0o400
            and info.st_dev == self.proof["parent_metadata"]["device"], "HOST_WINDOW_INTENT_IDENTITY")
        require(io.metadata(os.stat(c.INTENT_NAME, dir_fd=directory_fd, follow_symlinks=False)) == before,
            "HOST_WINDOW_INTENT_REPLACED")
        self._acl(fd)
        self.preparation_guard()
        require(io.metadata(os.fstat(fd)) == before, "HOST_WINDOW_INTENT_CHANGED")
        require(io.metadata(os.stat(c.INTENT_NAME, dir_fd=directory_fd, follow_symlinks=False)) == before,
            "HOST_WINDOW_INTENT_REPLACED")
        self._created_directory_check(directory_fd)
        self.preparation_guard()

    def _created_directory_check(self, fd):
        self.preparation_guard()
        _ordinary_chain_binding(self.parent)
        info = os.fstat(fd)
        require(stat.S_ISDIR(info.st_mode) and info.st_nlink == 2
            and info.st_dev == self.proof["parent_metadata"]["device"]
            and info.st_uid == self.owner_uid and info.st_gid == self.owner_gid
            and stat.S_IMODE(info.st_mode) == 0o700, "HOST_WINDOW_DIRECTORY_IDENTITY")
        require(io.metadata(os.stat(c.DIRECTORY_NAME, dir_fd=self.parent.fd, follow_symlinks=False))
            == io.metadata(info), "HOST_WINDOW_DIRECTORY_CHANGED")
        self.preparation_guard()

    def _before_mkdir(self):
        self.preparation_guard()
        _protected_chain_ordinary(self.parent)
        # No authorized child write has happened yet; retain the precheck's
        # full parent metadata here. After mkdir only ancestor fields apply.
        self.parent.verify()
        self.preparation_guard()

    def _validate_proof(self, value, location, window):
        return validate_precheck_ordinary(value, location, window)

    def _verify_intent(self, raw):
        return c.verify_intent_ordinary(raw, self.binding, self.location)


def precheck_ordinary(location, binding, window, host_costs):
    return HeldOrdinaryPrecheck(location, binding, window, host_costs)


class HeldConsumption:
    def __init__(self, preflight):
        self.preflight = preflight
        self.parent = preflight.parent
        self.directory_fd = self.file_fd = None
        self.closed = False; self.durable = False; self.window_consumed = False
        self.snapshot = None
        self.parent_growth_bytes = None
        self._first_parent_metadata = None
        self._first_allocation_observation = None

    def _parent_verify(self):
        require(not self.closed, "HOST_WINDOW_CLOSED")
        self.preflight.guard()
        # The parent is now an ancestor. Later authorized sibling captures may
        # change its timestamps, but never its identity, protection or binding.
        for index, (name, fd, before) in enumerate(self.parent.chain):
            info = io.metadata(os.fstat(fd))
            by_name = io.metadata(os.stat("/", follow_symlinks=False) if index == 0 else
                os.stat(name, dir_fd=self.parent.chain[index-1][1], follow_symlinks=False))
            require(all(info[key] == by_name[key] == before[key] for key in io.ANCESTOR_FIELDS),
                "HOST_WINDOW_PARENT_CHANGED")
        self.preflight._protect_chain(self.parent)

    def _create(self):
        self.preflight.preparation_guard()
        self.preflight._before_mkdir()
        try:
            os.mkdir(c.DIRECTORY_NAME, 0o700, dir_fd=self.parent.fd)
        except FileExistsError as error:
            self.window_consumed = True
            raise ValueError("HOST_WINDOW_ALREADY_CONSUMED") from error
        self.window_consumed = True
        self.preflight.preparation_guard()
        self.directory_fd = os.open(c.DIRECTORY_NAME, io.flags(True), dir_fd=self.parent.fd)
        info = os.fstat(self.directory_fd)
        require(_identity(info) == dict(device=self.proof_device, inode=info.st_ino,
            uid=self.preflight.owner_uid, gid=self.preflight.owner_gid, mode=0o700)
            and stat.S_ISDIR(info.st_mode) and info.st_nlink == 2, "HOST_WINDOW_DIRECTORY_IDENTITY")
        self.directory_identity = _identity(info)
        self.preflight._acl(self.directory_fd); self._parent_verify()
        self.preflight.preparation_guard(); os.fsync(self.directory_fd)
        self.preflight.preparation_guard(); os.fsync(self.parent.fd)
        self.intent_raw = encoded(self.preflight.intent(self.directory_identity))
        require(len(self.intent_raw) <= INTENT_LIMIT, "HOST_WINDOW_INTENT_LIMIT")
        self.intent_sha256 = sha(self.intent_raw)
        self.preflight.preparation_guard()
        self.preflight._created_directory_check(self.directory_fd)
        self.file_fd = os.open(c.INTENT_NAME,
            os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC,
            0o400, dir_fd=self.directory_fd)
        self.preflight.preparation_guard()
        self.preflight._created_file_check(self.file_fd, self.directory_fd)
        count = os.write(self.file_fd, self.intent_raw)
        require(count == len(self.intent_raw), "HOST_WINDOW_SHORT_WRITE")
        self.preflight.preparation_guard(); os.fsync(self.file_fd)
        self.preflight.preparation_guard(); os.fsync(self.directory_fd)
        self.preflight.preparation_guard(); os.fsync(self.parent.fd)
        self.file_metadata = io.metadata(os.fstat(self.file_fd))
        self.directory_metadata = io.metadata(os.fstat(self.directory_fd))
        self._verify_files()
        observed = io.snapshot(self.preflight.location["directory"], self.preflight.guard,
            allowed_uids=self.preflight.allowed_uids)
        self._budget(observed)
        self.snapshot = observed
        if self.preflight.intent_schema == c.ORDINARY_INTENT_SCHEMA:
            # Retain only facts already read by the original first budget
            # check. No later recheck may replace this historical endpoint.
            intent = c.document(self.intent_raw)
            self._first_allocation_observation = dict(schema=PARENT_ALLOCATION_SCHEMA,
                span="precheck-parent-to-first-marker-budget",
                binding_sha256=sha(encoded(intent["binding"])),
                location_sha256=intent["precheck"]["location_sha256"],
                intent_sha256=self.intent_sha256,
                precheck_sha256=intent["precheck_sha256"], window=copy.deepcopy(intent["window"]),
                parent_path=self.preflight.location["parent"],
                parent_before=copy.deepcopy(intent["precheck"]["parent_metadata"]),
                parent_after=copy.deepcopy(self._first_parent_metadata),
                marker_snapshot_sha256=sha(encoded(observed)))
        self.durable = True
        self.parent.guard = self.preflight.guard
        self.verify()
        self.preflight.preparation_guard()

    @property
    def proof_device(self):
        return self.preflight.proof["parent_metadata"]["device"]

    def _budget(self, observed):
        parent_before = self.preflight.proof["parent_metadata"]
        parent_now = io.metadata(os.fstat(self.parent.fd))
        parent_growth = (max(0, parent_now["blocks"] - parent_before["blocks"]) * 512
            if self.parent_growth_bytes is None else self.parent_growth_bytes)
        logical = sum(row["source_metadata"]["size"] for row in observed["entries"])
        require(logical <= c.LOGICAL_LIMIT and observed["bytes"] + parent_growth <= c.BYTE_LIMIT
            and observed["inodes"] <= c.INODE_LIMIT and parent_growth <= BLOCK,
            "HOST_WINDOW_ACTUAL_LIMIT")
        if self._first_parent_metadata is None:
            self._first_parent_metadata = copy.deepcopy(parent_now)
        self.parent_growth_bytes = parent_growth
        return dict(logical_bytes=logical, bytes=observed["bytes"],
            parent_growth_bytes=parent_growth, inodes=observed["inodes"])

    def _verify_files(self):
        self._parent_verify()
        require(_boot(self.preflight.guard) == self.preflight.location["expected_boot_id"], "HOST_WINDOW_BOOT_CHANGED")
        directory = os.fstat(self.directory_fd)
        require(io.metadata(directory) == self.directory_metadata
            and io.metadata(os.stat(c.DIRECTORY_NAME, dir_fd=self.parent.fd, follow_symlinks=False))
                == self.directory_metadata, "HOST_WINDOW_DIRECTORY_CHANGED")
        self.preflight._acl(self.directory_fd)
        require(os.listdir(self.directory_fd) == [c.INTENT_NAME], "HOST_WINDOW_MEMBERS")
        current = os.fstat(self.file_fd)
        require(io.metadata(current) == self.file_metadata and stat.S_ISREG(current.st_mode)
            and current.st_nlink == 1 and current.st_uid == self.preflight.owner_uid
            and current.st_gid == self.preflight.owner_gid
            and stat.S_IMODE(current.st_mode) == 0o400 and current.st_dev == self.proof_device,
            "HOST_WINDOW_INTENT_IDENTITY")
        require(io.metadata(os.stat(c.INTENT_NAME, dir_fd=self.directory_fd, follow_symlinks=False)) == self.file_metadata,
            "HOST_WINDOW_INTENT_REPLACED")
        self.preflight._acl(self.file_fd)
        require(io._read(self.file_fd, self.preflight.guard, INTENT_LIMIT) == self.intent_raw,
            "HOST_WINDOW_INTENT_CHANGED")
        self.preflight._verify_intent(self.intent_raw)

    def verify(self):
        require(self.durable, "HOST_WINDOW_NOT_DURABLE")
        self._verify_files()
        current = io.snapshot(self.preflight.location["directory"], self.preflight.guard,
            expected=self.snapshot, allowed_uids=self.preflight.allowed_uids)
        self._budget(current)
        self._verify_files()
        return copy.deepcopy(current)

    @property
    def evidence(self):
        observed = self.verify()
        return dict(schema=self.preflight.evidence_schema, status="HOST_INTENT_DURABLE", window_consumed=True,
            owner_issued=False, allow_run=False, intent_sha256=self.intent_sha256,
            directory_identity=dict(self.directory_identity), window=dict(self.preflight.origin),
            actual=self._budget(observed), **self.preflight._operator_fields())

    def first_allocation_observation(self):
        """Copy the historical first span; no new I/O or freshness assertion.

        This ordinary-profile companion is not a causal, allocation-peak,
        baseline-cost, durability or live-dispatch proof. Existing evidence
        schemas and historical readback cannot synthesize this observation.
        """
        require(not self.closed and self.durable, "HOST_WINDOW_NOT_DURABLE")
        require(self._first_allocation_observation is not None,
            "HOST_WINDOW_PARENT_ALLOCATION_UNAVAILABLE")
        return copy.deepcopy(self._first_allocation_observation)

    def close(self):
        if not self.closed:
            self.closed = True
            for fd in (self.file_fd, self.directory_fd):
                if fd is not None:
                    os.close(fd)
            if self.parent is not None:
                self.parent.close()


def verify_existing(location, binding, window, expected_intent_sha256):
    """Read-only historical verification: never a receipt permitting dispatch."""
    location = c.validate_location(location); c.validate_binding(binding, location)
    c.digest(expected_intent_sha256); origin = c.validate_window(window.fields())
    def guard():
        require(window.fields() == origin, "HOST_WINDOW_ORIGIN_CHANGED")
        window.guard()
    require(_boot(guard) == location["expected_boot_id"], "HOST_WINDOW_BOOT_CHANGED")
    with io.HeldPath(location["directory"], guard, directory=True, allowed_uids={0}) as directory:
        _protected_chain(directory)
        with io.read_pinned(location["directory"] + "/" + c.INTENT_NAME, guard,
                dict(sha256=expected_intent_sha256), max_bytes=INTENT_LIMIT, allowed_uids={0}) as held:
            value = c.verify_intent(held.data, binding, location)
            require(value["window"] == origin, "HOST_WINDOW_ORIGIN_CHANGED")
            require(stat.S_IMODE(held.metadata["st_mode"]) == 0o400 and held.metadata["uid"] == held.metadata["gid"] == 0,
                "HOST_WINDOW_INTENT_IDENTITY")
            _acl_absent(held.fd)
            observed = io.snapshot(location["directory"], guard, allowed_uids={0})
            require({row["relative_path"] for row in observed["entries"]} == {".", c.INTENT_NAME}
                and observed["bytes"] <= c.BYTE_LIMIT and observed["inodes"] <= c.INODE_LIMIT
                and sum(row["source_metadata"]["size"] for row in observed["entries"]) <= c.LOGICAL_LIMIT,
                "HOST_WINDOW_EXISTING_MEMBERS")
            require(value["directory_identity"] == _identity(os.fstat(directory.fd)), "HOST_WINDOW_DIRECTORY_CHANGED")
            held.verify(); directory.verify()
            return dict(schema=EVIDENCE_SCHEMA, status="CONSUMED_READ_ONLY", allow_run=False,
                window_consumed=True, owner_issued=False, intent_sha256=held.sha256, intent=value, snapshot=observed)


def verify_existing_ordinary(location, binding, window, expected_intent_sha256):
    """Explicit v2 readback, with a fresh stable same-owner reader.

    The retained issuer's groups/GID are historical facts, not a permanent
    credential pin for this new reader. Neither identity grants another run.
    The production kernel/FS-read boundaries remain unchanged.
    """
    location = c.validate_location(location); c.validate_binding(binding, location)
    c.digest(expected_intent_sha256); origin = c.validate_window(window.fields())
    reader = _current_operator()
    owner_uid = reader["uid"][1]
    owners = frozenset({0, owner_uid})

    def guard():
        require(_current_operator() == reader, "HOST_WINDOW_OPERATOR_CHANGED")
        require(window.fields() == origin, "HOST_WINDOW_ORIGIN_CHANGED")
        window.guard()

    guard()
    require(_boot(guard) == location["expected_boot_id"], "HOST_WINDOW_BOOT_CHANGED")
    with io.HeldPath(location["directory"], guard, directory=True, allowed_uids=owners) as directory:
        _protected_chain_ordinary(directory)
        guard()
        directory_info = os.fstat(directory.fd)
        require(directory_info.st_uid == owner_uid and stat.S_IMODE(directory_info.st_mode) == 0o700,
            "HOST_WINDOW_DIRECTORY_IDENTITY")
        with io.HeldPath(location["directory"] + "/" + c.INTENT_NAME, guard,
                allowed_uids=owners) as held:
            # Check owner/type before reading: allowing root-owned ancestors
            # does not authorize a different issuer's leaf content.
            guard()
            info = os.fstat(held.fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == owner_uid
                and info.st_dev == directory_info.st_dev and stat.S_IMODE(info.st_mode) == 0o400,
                "HOST_WINDOW_INTENT_IDENTITY")
            _ordinary_acl_absent(held.fd, guard)
            raw = io._read(held.fd, guard, INTENT_LIMIT)
            require(sha(raw) == expected_intent_sha256, "RECONCILIATION_PIN_DIGEST")
            value = c.verify_intent_ordinary(raw, binding, location)
            require(value["window"] == origin, "HOST_WINDOW_ORIGIN_CHANGED")
            issuer = value["operator"]
            require(issuer["uid"][1] == owner_uid and info.st_gid == issuer["gid"][1],
                "HOST_WINDOW_INTENT_IDENTITY")
            require(value["directory_identity"] == _identity(directory_info), "HOST_WINDOW_DIRECTORY_CHANGED")
            parent = io.metadata(os.fstat(directory.chain[-2][1]))
            historical_parent = value["precheck"]["parent_metadata"]
            require(all(parent[key] == historical_parent[key] for key in io.ANCESTOR_FIELDS),
                "HOST_WINDOW_PARENT_CHANGED")
            observed = io.snapshot(location["directory"], guard, allowed_uids=owners)
            require({row["relative_path"] for row in observed["entries"]} == {".", c.INTENT_NAME}
                and observed["bytes"] <= c.BYTE_LIMIT and observed["inodes"] <= c.INODE_LIMIT
                and sum(row["source_metadata"]["size"] for row in observed["entries"]) <= c.LOGICAL_LIMIT,
                "HOST_WINDOW_EXISTING_MEMBERS")
            # Snapshot and held read must describe the same exact immutable
            # file, rather than merely a member with the same relative name.
            rows = {row["relative_path"]: row for row in observed["entries"]}
            require(rows[c.INTENT_NAME]["source_metadata"] == io.metadata(info)
                and rows[c.INTENT_NAME].get("sha256") == expected_intent_sha256,
                "HOST_WINDOW_INTENT_CHANGED")
            held.verify(); directory.verify(); _protected_chain_ordinary(directory)
            guard()
            return dict(schema=ORDINARY_EVIDENCE_SCHEMA, status="CONSUMED_READ_ONLY", allow_run=False,
                window_consumed=True, owner_issued=False, intent_sha256=expected_intent_sha256,
                operator=copy.deepcopy(issuer), reader_operator=copy.deepcopy(reader), intent=value, snapshot=observed)
