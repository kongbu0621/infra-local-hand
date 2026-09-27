"""Bounded, no-follow/no-atime reads for the isolated Q2 amendment.

No syscall fallback, timestamp repair or guest action lives here. A caller must
retain HeldRead objects through its final admission check. Snapshot is a complete
observation, not a lock; callers compare it again immediately before issuance.
"""
from __future__ import annotations

import hashlib
import os
import stat
import sys


MAX_BYTES = 512 * 1024**2
MAX_ENTRIES = 32768
META_FIELDS = ("device", "inode", "st_mode", "uid", "gid", "nlink", "size",
               "blocks", "atime_ns", "mtime_ns", "ctime_ns")
ANCESTOR_FIELDS = ("device", "inode", "st_mode", "uid", "gid")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def metadata(info):
    return dict(device=info.st_dev, inode=info.st_ino, st_mode=info.st_mode,
                uid=info.st_uid, gid=info.st_gid, nlink=info.st_nlink,
                size=info.st_size, blocks=info.st_blocks, atime_ns=info.st_atime_ns,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns)


def absolute(path):
    path = os.fspath(path)
    require(type(path) is str and path.startswith("/") and "\0" not in path
            and len(path.encode("utf-8")) <= 4096, "RECONCILIATION_PATH")
    require(path == "/" or (not path.endswith("/") and all(
        part not in ("", ".", "..") for part in path[1:].split("/"))), "RECONCILIATION_PATH_ALIAS")
    return path


def supported():
    require(sys.platform.startswith("linux") and all(hasattr(os, name) for name in
        ("O_NOATIME", "O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC", "O_PATH")), "RECONCILIATION_IO_UNSUPPORTED")


def allowed_owners(allowed_uids=None):
    values = (0, os.geteuid()) if allowed_uids is None else allowed_uids
    require(type(values) in (tuple, list, set, frozenset) and 0 < len(values) <= 16
            and all(type(value) is int and 0 <= value <= 2**32 - 2 for value in values),
            "RECONCILIATION_OWNER_SET")
    return frozenset(values)


def protected(info, directory=False, *, allowed_uids=None):
    require(info.st_uid in allowed_owners(allowed_uids) and not info.st_mode & 0o6022,
            "RECONCILIATION_UNPROTECTED_PATH")
    require(stat.S_ISDIR(info.st_mode) if directory else
            stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "RECONCILIATION_OBJECT_TYPE")


def flags(directory=False):
    supported()
    return (os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOATIME
            | (os.O_DIRECTORY if directory else 0))


class HeldPath:
    """Every ancestor stays open, and every name-to-inode binding is rechecked."""
    def __init__(self, path, guard, *, directory=False, allowed_uids=None):
        supported()
        self.path, self.guard, self.chain = absolute(path), guard, []
        self.allowed_uids = allowed_owners(allowed_uids)
        self.closed = False
        try:
            guard()
            # Ancestors are stat-only O_PATH handles. They are not enumerated
            # or read, so no atime operation occurs. Keeping the whole identity
            # chain prevents substitution while allowing authorized siblings to
            # be created without falsely declaring ancestor-time preservation.
            ancestor_flags = os.O_PATH | os.O_NOFOLLOW | os.O_DIRECTORY | os.O_CLOEXEC
            fd = os.open("/", flags(True) if self.path == "/" else ancestor_flags)
            self.chain.append((None, fd, metadata(os.fstat(fd))))
            protected(os.fstat(fd), True, allowed_uids=self.allowed_uids)
            parts = self.path[1:].split("/") if self.path != "/" else []
            for index, part in enumerate(parts):
                guard()
                is_directory = directory or index < len(parts) - 1
                child = os.open(part, flags(is_directory) if index == len(parts) - 1 else ancestor_flags,
                                dir_fd=fd)
                info = os.fstat(child)
                self.chain.append((part, child, metadata(info)))
                protected(info, is_directory, allowed_uids=self.allowed_uids)
                require(metadata(os.stat(part, dir_fd=fd, follow_symlinks=False)) == metadata(info),
                        "RECONCILIATION_PATH_CHANGED")
                fd = child
            self.fd = fd
            self.verify()
        except BaseException:
            self.close()
            raise

    def verify(self):
        require(not self.closed, "RECONCILIATION_FD_CLOSED")
        for index, (name, fd, before) in enumerate(self.chain):
            self.guard()
            fields = META_FIELDS if index == len(self.chain) - 1 else ANCESTOR_FIELDS
            current = metadata(os.fstat(fd))
            require(all(current[key] == before[key] for key in fields), "RECONCILIATION_METADATA_CHANGED")
            by_name = os.stat("/", follow_symlinks=False) if index == 0 else os.stat(
                name, dir_fd=self.chain[index - 1][1], follow_symlinks=False)
            current_name = metadata(by_name)
            require(all(current_name[key] == before[key] for key in fields), "RECONCILIATION_PATH_CHANGED")
        return self.chain[-1][2]

    def refresh_written_directory(self):
        """Only for the caller's own create-only child writes, never old evidence."""
        name, fd, before = self.chain[-1]
        after = metadata(os.fstat(fd))
        require(stat.S_ISDIR(after["st_mode"]), "RECONCILIATION_OBJECT_TYPE")
        require(all(after[key] == before[key] for key in
                    ("device", "inode", "st_mode", "uid", "gid")), "RECONCILIATION_DIRECTORY_IDENTITY")
        self.chain[-1] = name, fd, after
        return self.verify()

    def close(self):
        if not self.closed:
            self.closed = True
            for _, fd, _ in reversed(self.chain):
                os.close(fd)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _read(fd, guard, maximum):
    before = metadata(os.fstat(fd))
    require(before["size"] <= maximum, "RECONCILIATION_READ_LIMIT")
    os.lseek(fd, 0, os.SEEK_SET)
    pieces, total = [], 0
    while True:
        guard()
        part = os.read(fd, min(65536, maximum + 1 - total))
        if not part:
            break
        pieces.append(part)
        total += len(part)
        require(total <= maximum, "RECONCILIATION_READ_LIMIT")
    require(metadata(os.fstat(fd)) == before and total == before["size"],
            "RECONCILIATION_CONTENT_CHANGED")
    return b"".join(pieces)


def _digest(fd, guard, maximum):
    before = metadata(os.fstat(fd))
    require(before["size"] <= maximum, "RECONCILIATION_READ_LIMIT")
    os.lseek(fd, 0, os.SEEK_SET)
    digest, total = hashlib.sha256(), 0
    while True:
        guard()
        part = os.read(fd, min(65536, maximum + 1 - total))
        if not part:
            break
        total += len(part)
        require(total <= maximum, "RECONCILIATION_READ_LIMIT")
        digest.update(part)
    require(metadata(os.fstat(fd)) == before and total == before["size"],
            "RECONCILIATION_CONTENT_CHANGED")
    return digest.hexdigest()


class HeldRead(HeldPath):
    def __init__(self, path, guard, expected=None, max_bytes=8 * 1024**2, *, allowed_uids=None):
        require(type(max_bytes) is int and 0 <= max_bytes <= MAX_BYTES, "RECONCILIATION_READ_LIMIT")
        super().__init__(path, guard, allowed_uids=allowed_uids)
        try:
            self.maximum = max_bytes
            self.data = _read(self.fd, guard, max_bytes)
            self.metadata = dict(self.chain[-1][2])
            self.sha256 = hashlib.sha256(self.data).hexdigest()
            if expected is not None:
                require(type(expected) is dict and set(expected) <= {
                    "sha256", "bytes", "source_metadata"}, "RECONCILIATION_PIN_FIELDS")
                if "sha256" in expected:
                    require(expected["sha256"] == self.sha256, "RECONCILIATION_PIN_DIGEST")
                if "bytes" in expected:
                    require(type(expected["bytes"]) is int and expected["bytes"] == len(self.data),
                            "RECONCILIATION_PIN_SIZE")
                if "source_metadata" in expected:
                    require(expected["source_metadata"] == self.metadata, "RECONCILIATION_PIN_METADATA")
            self.verify()
        except BaseException:
            self.close()
            raise

    def verify(self):
        result = super().verify()
        if hasattr(self, "data"):
            require(_read(self.fd, self.guard, self.maximum) == self.data, "RECONCILIATION_CONTENT_CHANGED")
            super().verify()
        return result


def read_pinned(path, guard, expected=None, *, max_bytes=8 * 1024**2, allowed_uids=None):
    return HeldRead(path, guard, expected, max_bytes, allowed_uids=allowed_uids)


def verify_held(held, guard=None):
    if guard is not None:
        guard()
    return held.verify()


def _expected_entries(expected):
    if expected is None:
        return None
    value = expected["entries"] if type(expected) is dict else expected
    require(type(value) is list and len(value) <= MAX_ENTRIES, "RECONCILIATION_EXPECTED_ENTRIES")
    by_path = {}
    for item in value:
        require(type(item) is dict and type(item.get("relative_path")) is str
                and item["relative_path"] not in by_path, "RECONCILIATION_EXPECTED_ENTRIES")
        by_path[item["relative_path"]] = item
    return by_path


def snapshot(path, guard, expected=None, seen=None, *, allowed_uids=None):
    """Complete tree, exact metadata and allocated 512-byte blocks, including root.

    Symlink reads have no Linux per-fd NOATIME operation. They are therefore
    supported only on a kernel-reported noatime mount and with a fixed target.
    A relatime mount is rejected BEFORE readlink; O_PATH is not a substitute.
    """
    path = absolute(path)
    allowed_uids = allowed_owners(allowed_uids)
    expected_map = _expected_entries(expected)
    observed, aliases = [], set()
    charged = set() if seen is None else set(seen)
    new_keys, total_bytes, total_logical = set(), 0, 0

    def emit(relative, info, kind, **extra):
        nonlocal total_bytes, total_logical
        guard()
        require(len(observed) < MAX_ENTRIES, "RECONCILIATION_ENTRY_LIMIT")
        require(info.st_dev == root_device, "RECONCILIATION_DEVICE_CHANGED")
        key = info.st_dev, info.st_ino
        require(key not in aliases, "RECONCILIATION_OBJECT_ALIAS")
        aliases.add(key)
        if key not in charged:
            total_bytes += info.st_blocks * 512
            new_keys.add(key)
            charged.add(key)
        if kind == "file":
            total_logical += info.st_size
        require(total_bytes <= MAX_BYTES and total_logical <= MAX_BYTES, "RECONCILIATION_TREE_LIMIT")
        row = dict(relative_path=relative, type=kind, source_metadata=metadata(info), **extra)
        if expected_map is not None:
            require(expected_map.get(relative) == row, "RECONCILIATION_TREE_CHANGED")
        observed.append(row)

    def visit(fd, relative):
        before = os.fstat(fd)
        protected(before, True, allowed_uids=allowed_uids)
        names = []
        with os.scandir(fd) as items:
            for item in items:
                guard()
                require(len(names) + len(observed) < MAX_ENTRIES, "RECONCILIATION_ENTRY_LIMIT")
                require(item.name not in (".", "..") and "/" not in item.name,
                        "RECONCILIATION_PATH_ALIAS")
                names.append(item.name)
        for name in sorted(names):
            guard()
            rel = name if relative == "." else relative + "/" + name
            require(len((path + "/" + rel).encode("utf-8")) <= 4096, "RECONCILIATION_PATH")
            prior = os.stat(name, dir_fd=fd, follow_symlinks=False)
            require(prior.st_dev == root_device, "RECONCILIATION_DEVICE_CHANGED")
            if stat.S_ISLNK(prior.st_mode):
                pin = None if expected_map is None else expected_map.get(rel)
                require(pin is not None and pin.get("type") == "symlink"
                        and type(pin.get("link_target")) is str, "RECONCILIATION_SYMLINK_UNPINNED")
                require(prior.st_uid in allowed_uids and prior.st_nlink == 1,
                        "RECONCILIATION_SYMLINK_IDENTITY")
                link_fd = os.open(name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                try:
                    require(metadata(os.fstat(link_fd)) == metadata(prior), "RECONCILIATION_PATH_CHANGED")
                    require(hasattr(os, "ST_NOATIME") and os.fstatvfs(link_fd).f_flag & os.ST_NOATIME,
                            "RECONCILIATION_SYMLINK_NOATIME_UNSUPPORTED")
                    # Empty-path readlinkat targets the held symlink itself,
                    # never a name that can be swapped to a different link.
                    target = os.readlink("", dir_fd=link_fd)
                    require(metadata(os.fstat(link_fd)) == metadata(prior) and metadata(os.stat(
                        name, dir_fd=fd, follow_symlinks=False)) == metadata(prior),
                        "RECONCILIATION_METADATA_CHANGED")
                    emit(rel, prior, "symlink", link_target=target)
                finally:
                    os.close(link_fd)
                continue
            directory = stat.S_ISDIR(prior.st_mode)
            protected(prior, directory, allowed_uids=allowed_uids)
            child = os.open(name, flags(directory), dir_fd=fd)
            try:
                require(metadata(os.fstat(child)) == metadata(prior), "RECONCILIATION_PATH_CHANGED")
                if directory:
                    visit(child, rel)
                else:
                    digest = _digest(child, guard, MAX_BYTES - total_logical)
                    emit(rel, prior, "file", sha256=digest)
                require(metadata(os.fstat(child)) == metadata(prior)
                        and metadata(os.stat(name, dir_fd=fd, follow_symlinks=False)) == metadata(prior),
                        "RECONCILIATION_PATH_CHANGED")
            finally:
                os.close(child)
        require(metadata(os.fstat(fd)) == metadata(before), "RECONCILIATION_DIRECTORY_CHANGED")
        emit(relative, before, "directory")

    # The root may be a regular evidence file; open it without following links.
    parent, _, name = path.rpartition("/")
    with HeldPath(parent or "/", guard, directory=True, allowed_uids=allowed_uids) as ancestry:
        info = os.stat(name, dir_fd=ancestry.fd, follow_symlinks=False) if name else os.fstat(ancestry.fd)
        directory = stat.S_ISDIR(info.st_mode)
        protected(info, directory, allowed_uids=allowed_uids)
        root_device = info.st_dev
        root_fd = os.open(name, flags(directory), dir_fd=ancestry.fd) if name else os.dup(ancestry.fd)
        try:
            require(metadata(os.fstat(root_fd)) == metadata(info), "RECONCILIATION_PATH_CHANGED")
            if directory:
                visit(root_fd, ".")
            else:
                digest = _digest(root_fd, guard, MAX_BYTES)
                emit(".", info, "file", sha256=digest)
            require(metadata(os.fstat(root_fd)) == metadata(info), "RECONCILIATION_METADATA_CHANGED")
            if name:
                require(metadata(os.stat(name, dir_fd=ancestry.fd, follow_symlinks=False)) == metadata(info),
                        "RECONCILIATION_PATH_CHANGED")
            ancestry.verify()
        finally:
            os.close(root_fd)
    observed.sort(key=lambda row: row["relative_path"])
    if expected_map is not None:
        require(len(observed) == len(expected_map), "RECONCILIATION_TREE_CHANGED")
    if seen is not None:
        seen.update(new_keys)
    return dict(path=path, entries=observed, bytes=total_bytes, inodes=len(new_keys),
                device=root_device, logical_bytes=total_logical)
