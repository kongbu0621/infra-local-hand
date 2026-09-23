"""Authority anchoring and conservative resource leases (no timeout stealing)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

from .contract import JobError


class AuthorityLock:
    """Acquire a preprovisioned common anchor, validating its admitted identity.

    An administrator provisions the file once; the broker never creates a missing
    anchor or follows a caller-selected second state root during recovery.
    """

    def __init__(self, anchor, *, authority_id, ledger_id, state_root):
        self.fd = None
        failed = True
        try:
            import fcntl
            descriptor = os.open(anchor, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
            self.fd = descriptor
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise JobError("UNAUTHORIZED", "Authority anchor is not privately owned")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            raw = os.read(descriptor, 8193)
            if len(raw) > 8192:
                raise JobError("CONFLICT", "Invalid authority registration")
            expected = {"authority_id": authority_id, "ledger_id": ledger_id,
                        "state_root": str(Path(state_root).absolute())}
            if json.loads(raw) != expected:
                raise JobError("CONFLICT", "Authority registration does not match")
            current = os.stat(anchor, follow_symlinks=False)
            after = os.fstat(descriptor)
            if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or (
                    current.st_dev, current.st_ino) != (after.st_dev, after.st_ino):
                raise JobError("IO_UNCERTAIN", "Authority registration changed while acquiring its lock")
            failed = False
        except BlockingIOError as exc:
            raise JobError("RESOURCE_BUSY", "Another broker owns this authority") from exc
        except (OSError, ValueError, ImportError) as exc:
            raise JobError("IO_UNCERTAIN", "Authority anchor cannot be proven") from exc
        finally:
            if failed:
                self._close(failed=True)

    def close(self):
        self._close(failed=False)

    def _close(self, *, failed):
        if self.fd is not None:
            descriptor, self.fd = self.fd, None
            try:
                # close may release the descriptor even when it reports an
                # error. Never retry a number another file can now own.
                os.close(descriptor)
            except OSError:
                if not failed:
                    raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        self._close(failed=exc_type is not None)


def verify_local_filesystem(path):
    """Production startup check; fixture StateStore tests do not claim this gate."""
    try:
        with open("/proc/self/mountinfo", "rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise JobError("LIMIT_EXCEEDED", "Mount inventory exceeds the startup budget")
        target = Path(path).absolute()
        device = os.stat(target, follow_symlinks=False).st_dev
        device_key = f"{os.major(device)}:{os.minor(device)}"
        matches = []
        for line in raw.decode("utf-8", "strict").splitlines():
            left, right = line.split(" - ", 1)
            fields = left.split()
            mount = fields[4]
            for escaped, plain in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
                mount = mount.replace(escaped, plain)
            root = Path(mount)
            if fields[2] == device_key and (target == root or root in target.parents):
                matches.append((len(root.parts), int(fields[0]), right.split()[0]))
        if not matches or max(matches)[2] not in ("ext4", "xfs", "btrfs"):
            raise JobError("UNSUPPORTED", "The authoritative ledger requires an admitted reliable local filesystem")
    except (OSError, UnicodeError, ValueError, IndexError) as exc:
        raise JobError("IO_UNCERTAIN", "Local ledger filesystem identity is unproven") from exc


class ResourceManager:
    """Only admitted stable IDs enter this API; aliases have no separate lease."""

    def __init__(self, aliases=None):
        self.aliases = dict(aliases or {})

    def canonical(self, resource):
        seen = set()
        while resource in self.aliases:
            if resource in seen:
                raise JobError("CONFLICT", "Resource aliases form a cycle")
            seen.add(resource)
            resource = self.aliases[resource]
        if not isinstance(resource, str) or not resource:
            raise JobError("UNSUPPORTED", "Resource lacks an admitted identity")
        return resource

    def acquire(self, tx, owner, epoch, resources):
        identities = sorted({self.canonical(item) for item in resources})
        if not identities:
            raise JobError("UNSUPPORTED", "Execution must bind at least one resource")
        for identity in identities:
            old = tx.execute("SELECT owner,epoch FROM leases WHERE resource=?", (identity,)).fetchone()
            if old is not None and (old[0], old[1]) != (owner, epoch):
                raise JobError("RESOURCE_BUSY", "A prior operation retains the resource barrier")
        for identity in identities:
            tx.execute("INSERT OR IGNORE INTO leases VALUES(?,?,?)", (identity, owner, epoch))

    def assert_owned(self, tx, owner, epoch, resources):
        for identity in {self.canonical(item) for item in resources}:
            row = tx.execute("SELECT owner,epoch FROM leases WHERE resource=?", (identity,)).fetchone()
            if row is None or (row[0], row[1]) != (owner, epoch):
                raise JobError("IO_UNCERTAIN", "Execution no longer owns its resource barrier")

    def release(self, tx, owner, *, future_start_blocked, tree_exited, effects_checked):
        if future_start_blocked is not True or tree_exited is not True or effects_checked is not True:
            raise JobError("IO_UNCERTAIN", "Incomplete exit or side-effect proof retains resources")
        tx.execute("DELETE FROM leases WHERE owner=?", (owner,))
