"""Guest-side bounded journal preservation primitives (J1, test only).

No executable poweroff/resize entry until exact old-domain and boot-risk
inventory are wired and verified. Importing this module has no effects.
"""
from __future__ import annotations

import hashlib
import fcntl
import os
import stat

from e3_host import q2_core_capacity_reader as r

require, canonical, digest = r.require, r.canonical, r.digest
MAX_BYTES, MAX_ENTRIES = 268435456, 32768


def metadata(value):
    # atime is deliberately not normalized: O_NOATIME must preserve it.
    return {name: getattr(value, "st_" + name) for name in
            ("dev", "ino", "mode", "uid", "gid", "nlink", "size", "mtime_ns", "ctime_ns", "atime_ns")}


def preservation(value):
    return {name: value[name] for name in
            ("ino", "mode", "uid", "gid", "nlink", "size", "mtime_ns", "atime_ns")}


def file_hash(fd, remaining, check):
    before = metadata(os.fstat(fd))
    require(stat.S_ISREG(before["mode"]) and before["size"] <= remaining, "GROWTH_TREE_BYTES")
    h, count = hashlib.sha256(), 0
    while True:
        check()
        raw = os.read(fd, min(65536, remaining + 1 - count))
        check()
        if not raw:
            break
        count += len(raw)
        require(count <= remaining, "GROWTH_TREE_BYTES")
        h.update(raw)
    require(count == before["size"] and before == metadata(os.fstat(fd)), "GROWTH_TREE_FILE_DRIFT")
    return h.hexdigest(), count


def tree_digest(root_fd, check, *, max_bytes=MAX_BYTES, max_entries=MAX_ENTRIES, mount_id=None):
    """Stable bounded fd traversal; reject symlinks and special files.

    The caller has bound root to the exact ext4 UUID/mount. mount_id is a
    required production check against bind mounts, including same-device ones.
    Synthetic tests may supply an identity callback without mounting fixtures.
    """
    require(callable(mount_id), "GROWTH_TREE_MOUNT_CHECK")
    require(fcntl.fcntl(root_fd, fcntl.F_GETFL) & os.O_NOATIME, "GROWTH_TREE_NOATIME")
    root_info = os.fstat(root_fd)
    require(stat.S_ISDIR(root_info.st_mode), "GROWTH_TREE_ROOT")
    root_mount = mount_id(root_fd)
    rows, nodes, content_bytes = [], [], 0
    stack = [(root_fd, "", False)]
    try:
        while stack:
            fd, path, owned = stack.pop()
            if owned:
                nodes.append(fd)
            check()
            before = metadata(os.fstat(fd))
            require(before["dev"] == root_info.st_dev and mount_id(fd) == root_mount,
                    "GROWTH_TREE_CROSS_MOUNT")
            require(stat.S_ISDIR(before["mode"]), "GROWTH_TREE_DIRECTORY")
            names = []
            with os.scandir(fd) as entries:
                for entry in entries:
                    check()
                    names.append(entry.name)
                    require(len(rows) + len(stack) + len(names) + 1 <= max_entries,
                            "GROWTH_TREE_ENTRIES")
            names.sort()
            rows.append(dict(path=path, metadata=before))
            for name in names:
                check()
                require(name not in (".", "..") and "/" not in name and "\0" not in name,
                        "GROWTH_TREE_NAME")
                encoded = os.fsencode(name)
                require(len(encoded) <= 255 and encoded.decode("utf-8", "strict") == name,
                        "GROWTH_TREE_ENCODING")
                child_path = path + "/" + name
                require(len(child_path.encode("utf-8")) <= 4096, "GROWTH_TREE_PATH")
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), "GROWTH_TREE_OBJECT")
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC
                                | os.O_NONBLOCK | (os.O_DIRECTORY if stat.S_ISDIR(info.st_mode) else 0), dir_fd=fd)
                try:
                    require(metadata(os.fstat(child)) == metadata(info), "GROWTH_TREE_NAME_DRIFT")
                    require(info.st_dev == root_info.st_dev and mount_id(child) == root_mount,
                            "GROWTH_TREE_CROSS_MOUNT")
                    if stat.S_ISDIR(info.st_mode):
                        require(len(stack) + len(nodes) < 64, "GROWTH_TREE_FDS")
                        stack.append((child, child_path, True))
                        child = None
                    else:
                        sha, count = file_hash(child, max_bytes - content_bytes, check)
                        content_bytes += count
                        rows.append(dict(path=child_path, metadata=metadata(info), sha256=sha))
                    require(metadata(os.stat(name, dir_fd=fd, follow_symlinks=False)) == metadata(info),
                            "GROWTH_TREE_NAME_DRIFT")
                    require(len(rows) + len(stack) <= max_entries, "GROWTH_TREE_ENTRIES")
                finally:
                    if child is not None:
                        os.close(child)
            require(metadata(os.fstat(fd)) == before, "GROWTH_TREE_DIRECTORY_DRIFT")
            if owned:
                nodes.remove(fd)
                os.close(fd)
        rows.sort(key=lambda row: row["path"])
        require(len(rows) <= max_entries and content_bytes <= max_bytes, "GROWTH_TREE_LIMIT")
        # Reopen every path relative to the held root without following links.
        # This detects a file changed after its hash, without hashing it twice.
        for row in rows:
            check()
            fd = os.dup(root_fd)
            try:
                for name in row["path"].split("/")[1:]:
                    next_fd = os.open(name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                    os.close(fd)
                    fd = next_fd
                    require(not stat.S_ISLNK(os.fstat(fd).st_mode), "GROWTH_TREE_REOPEN_LINK")
                require(metadata(os.fstat(fd)) == row["metadata"] and mount_id(fd) == root_mount,
                        "GROWTH_TREE_FINAL_DRIFT")
            finally:
                os.close(fd)
        preserved = [dict(path=row["path"], metadata=preservation(row["metadata"]),
                          **({"sha256": row["sha256"]} if "sha256" in row else {})) for row in rows]
        return dict(entries=len(rows), content_bytes=content_bytes,
                    sha256=digest(canonical(preserved)), observation_sha256=digest(canonical(rows)))
    finally:
        for fd in nodes:
            os.close(fd)
        for fd, _, owned in stack:
            if owned:
                os.close(fd)


def verify_preservation(before, after):
    require(set(before) == set(after) == {"entries", "content_bytes", "sha256", "observation_sha256"},
            "GROWTH_TREE_REPORT")
    require(all(before[key] == after[key] for key in ("entries", "content_bytes", "sha256")),
            "GROWTH_TREE_CHANGED")


def validate_quiet_unit(value):
    """A unit alone does NOT prove boot quietness or durable old evidence."""
    require(type(value) is dict and set(value) == {"Id", "ActiveState", "SubState", "MainPID",
        "ControlPID", "Restart", "UnitFileState", "Triggers", "TriggeredBy", "WantedBy", "RequiredBy",
        "UpheldBy", "OnSuccess", "OnFailure", "Job", "Transient", "FragmentPath", "DropInPaths"},
        "GROWTH_UNIT_FIELDS")
    require(value["ActiveState"] in ("inactive", "failed") and value["SubState"] in ("dead", "failed")
            and value["MainPID"] == value["ControlPID"] == "0" and value["Restart"] == "no",
            "GROWTH_UNIT_ACTIVE")
    require(value["UnitFileState"] in ("", "disabled", "static", "transient")
            and all(not value[key] for key in ("Triggers", "TriggeredBy", "WantedBy", "RequiredBy",
                                               "UpheldBy", "OnSuccess", "OnFailure", "Job")),
            "GROWTH_UNIT_AUTOSTART")
    return value


def validate_durable_filesystem(row):
    require(row["mount"]["fstype"] == "ext4" and row["mount"]["root"] == "/"
            and "rw" in row["mount"]["options"] and row["uuid"], "GROWTH_VOLATILE_EVIDENCE")


def validate_completion(before_rows, after_rows):
    require(len(before_rows) == len(after_rows) == 5, "GROWTH_PARENT_COUNT")
    for before, after in zip(before_rows, after_rows):
        require(before["role"] == after["role"] and before["path"] == after["path"]
                and before["filesystem"]["uuid"] == after["filesystem"]["uuid"], "GROWTH_PARENT_IDENTITY")
        for key in ("ino", "mode", "uid", "gid"):
            require(before["directory"][key] == after["directory"][key], "GROWTH_PARENT_DIRECTORY")
        for key in ("root", "path", "fstype", "options"):
            require(before["filesystem"]["mount"][key] == after["filesystem"]["mount"][key],
                    "GROWTH_PARENT_MOUNT")
        if after["role"] == "journal":
            require(after["available"]["bytes"] >= 400 * 1048576 and after["available"]["inodes"] >= 32768,
                    "GROWTH_TARGET_CAPACITY")
