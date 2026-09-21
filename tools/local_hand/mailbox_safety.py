"""Mailbox checkout/tree confinement and admission rules for Local Hand."""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from .bounded_io import directory_usage_bounded, list_directory_bounded
from .protocol import LocalHandError

MAX_MAILBOX_TREE_RECORDS = 50000
MAX_MAILBOX_TRACKED_FILES = 20000
MAX_MAILBOX_TRACKED_BYTES = 256 * 1024 * 1024
MAX_MAILBOX_CONTROL_BLOB_BYTES = 8 * 1024 * 1024
MAX_MAILBOX_TASK_FILES = 4096
MAX_MAILBOX_TREE_LISTING_BYTES = 8 * 1024 * 1024
MAX_MAILBOX_DISK_BYTES = 512 * 1024 * 1024
MAX_MAILBOX_DISK_ENTRIES = 100000
CONTROL_DIRS = (
    "_executor_spike",
    "_executor_spike/tasks",
    "_executor_spike/results",
    "_executor_spike/conflicts",
)
_CONTROL_CHILDREN = {"tasks", "results", "conflicts"}


def _is_reparse(st: os.stat_result) -> bool:
    attrs = getattr(st, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & flag)


def _require_real_dir(path: Path, root: Path, code: str) -> Path:
    try:
        st = path.lstat()
    except OSError as exc:
        raise LocalHandError(code, f"required mailbox directory missing: {path}", "indeterminate") from exc
    if stat.S_ISLNK(st.st_mode) or _is_reparse(st) or not stat.S_ISDIR(st.st_mode):
        raise LocalHandError(code, f"mailbox control directory must be a real directory: {path}", "indeterminate")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise LocalHandError(code, f"mailbox control directory escapes root: {path}", "indeterminate")
    return resolved


def enforce_mailbox_disk_quota(repo: Path) -> dict[str, int]:
    entries, total_bytes = directory_usage_bounded(
        repo,
        max_bytes=MAX_MAILBOX_DISK_BYTES,
        max_entries=MAX_MAILBOX_DISK_ENTRIES,
        code="mailbox_disk_quota_exceeded",
    )
    return {"entries": entries, "bytes": total_bytes}


def _create_control_directory(path: Path) -> None:
    """Create a control leaf privately on POSIX and by inherited ACL on Windows."""
    if os.name == "nt":
        # Python 3.13 gives mode=0o700 Windows-specific ACL semantics.  The
        # elevated bootstrap must instead inherit the exact mailbox ACL that
        # grants the dedicated Local Service runtime identity access.
        os.mkdir(path)
    else:
        os.mkdir(path, 0o700)


def ensure_checkout_control_dirs(mailbox: Path) -> None:
    """Ensure optional control leaf directories exist without accepting links/reparse points."""
    root = mailbox.resolve(strict=True)
    enforce_mailbox_disk_quota(mailbox)
    control_root = _require_real_dir(mailbox / "_executor_spike", root, "mailbox_path_escape")
    for name in sorted(_CONTROL_CHILDREN):
        path = control_root / name
        if os.path.lexists(path):
            _require_real_dir(path, root, "mailbox_path_escape")
            continue
        try:
            _create_control_directory(path)
        except OSError as exc:
            raise LocalHandError("mailbox_path_escape", f"cannot create mailbox control directory: {path}", "indeterminate") from exc
        _require_real_dir(path, root, "mailbox_path_escape")


def validate_checkout_control_dirs(mailbox: Path) -> None:
    ensure_checkout_control_dirs(mailbox)
    root = mailbox.resolve(strict=True)
    for relative in CONTROL_DIRS:
        _require_real_dir(mailbox / relative, root, "mailbox_path_escape")


def target_lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _temporary_control_path(parent: Path, target: Path) -> Path:
    """Return a predictable-size temp path without repeating target.name."""
    token = hashlib.sha256(os.fsencode(target.name)).hexdigest()[:16]
    return parent / f".lh-{token}-{os.getpid()}.tmp"


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def validate_control_target(mailbox: Path, path: Path, *, require_existing: bool = False) -> None:
    root = mailbox.resolve(strict=True)
    try:
        rel = path.relative_to(mailbox)
    except ValueError as exc:
        raise LocalHandError("mailbox_path_escape", f"target outside mailbox: {path}", "indeterminate") from exc
    parts = rel.parts
    if len(parts) < 3 or parts[0] != "_executor_spike" or parts[1] not in _CONTROL_CHILDREN:
        raise LocalHandError("mailbox_path_escape", f"target outside mailbox control namespace: {rel}", "indeterminate")
    _require_real_dir(path.parent, root, "mailbox_path_escape")
    if target_lexists(path):
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode) or _is_reparse(st) or not stat.S_ISREG(st.st_mode):
            raise LocalHandError("mailbox_file_invalid", f"mailbox control object is not a regular file: {rel}", "indeterminate")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise LocalHandError("mailbox_path_escape", f"mailbox control file escapes root: {rel}", "indeterminate")
    elif require_existing:
        raise LocalHandError("mailbox_file_invalid", f"mailbox control object missing: {rel}", "indeterminate")


def atomic_create_control_file(mailbox: Path, target: Path, data: bytes) -> None:
    validate_control_target(mailbox, target, require_existing=False)
    if target_lexists(target):
        raise LocalHandError("mailbox_target_occupied", f"mailbox target already occupied: {target.name}", "indeterminate")
    parent = target.parent
    temp = _temporary_control_path(parent, target)
    if target_lexists(temp):
        raise LocalHandError("mailbox_temp_occupied", f"mailbox temp path occupied: {temp.name}", "indeterminate")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(temp, flags, 0o600)
    except FileExistsError as exc:
        raise LocalHandError("mailbox_temp_occupied", f"mailbox temp path occupied: {temp.name}", "indeterminate") from exc
    except OSError as exc:
        raise LocalHandError("mailbox_temp_create_failed", f"cannot create mailbox temp file: {temp.name}", "indeterminate") from exc
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        try:
            # Creating a hard link is an atomic no-overwrite publication on
            # NTFS, APFS and ordinary Linux filesystems.  Unlike os.replace(),
            # it cannot destroy a target created after the admission check.
            os.link(temp, target)
        except FileExistsError as exc:
            raise LocalHandError("mailbox_target_occupied", f"mailbox target became occupied: {target.name}", "indeterminate") from exc
        except OSError as exc:
            if target_lexists(target):
                raise LocalHandError("mailbox_target_occupied", f"mailbox target became occupied: {target.name}", "indeterminate") from exc
            raise LocalHandError("mailbox_atomic_publish_failed", f"cannot atomically publish mailbox target: {target.name}", "indeterminate") from exc
        _fsync_directory(parent)
    finally:
        if target_lexists(temp):
            try:
                os.unlink(temp)
            except OSError:
                pass


def bounded_task_files(mailbox: Path) -> list[Path]:
    validate_checkout_control_dirs(mailbox)
    tasks = mailbox / "_executor_spike" / "tasks"
    entries = list_directory_bounded(tasks, MAX_MAILBOX_TASK_FILES, "mailbox_task_count_exceeded")
    result: list[Path] = []
    for entry in entries:
        if not entry.name.startswith("LH") or not entry.name.endswith(".json"):
            continue
        path = tasks / entry.name
        validate_control_target(mailbox, path, require_existing=True)
        result.append(path)
    return result


def _control_path(path: str) -> bool:
    if path == "_executor_spike":
        return True
    if not path.startswith("_executor_spike/"):
        return False
    rest = path[len("_executor_spike/"):]
    first = rest.split("/", 1)[0]
    return first in _CONTROL_CHILDREN


def validate_ls_tree_records(records: bytes) -> None:
    tree_records = 0
    control_files = 0
    control_bytes = 0
    for record in records.split(b"\0"):
        if not record:
            continue
        tree_records += 1
        if tree_records > MAX_MAILBOX_TREE_RECORDS:
            raise LocalHandError("mailbox_tree_too_large", f"mailbox tree exceeds {MAX_MAILBOX_TREE_RECORDS} records")
        try:
            meta, raw_path = record.split(b"\t", 1)
            fields = meta.decode("ascii", errors="strict").split()
            mode, kind = fields[0], fields[1]
            path = raw_path.decode("utf-8", errors="strict")
        except Exception as exc:
            raise LocalHandError("mailbox_tree_invalid", "cannot parse mailbox tree record", "indeterminate") from exc

        in_control = _control_path(path)
        if in_control and (mode == "120000" or kind == "commit" or mode == "160000"):
            raise LocalHandError("mailbox_symlink_rejected", f"symlink/gitlink forbidden in control namespace: {path}")

        size_field = fields[3] if len(fields) >= 4 else "-"
        if kind == "blob" and in_control:
            control_files += 1
            if control_files > MAX_MAILBOX_TRACKED_FILES:
                raise LocalHandError("mailbox_tree_too_large", f"mailbox control namespace exceeds {MAX_MAILBOX_TRACKED_FILES} files")
            if size_field == "-":
                raise LocalHandError("mailbox_blob_unavailable", f"control blob unavailable under admission filter: {path}")
            try:
                size = int(size_field)
            except ValueError as exc:
                raise LocalHandError("mailbox_tree_invalid", f"invalid object size for {path}", "indeterminate") from exc
            if size > MAX_MAILBOX_CONTROL_BLOB_BYTES:
                raise LocalHandError("mailbox_blob_too_large", f"control blob exceeds {MAX_MAILBOX_CONTROL_BLOB_BYTES} bytes: {path}")
            control_bytes += max(size, 0)
            if control_bytes > MAX_MAILBOX_TRACKED_BYTES:
                raise LocalHandError("mailbox_tree_too_large", f"mailbox control bytes exceed {MAX_MAILBOX_TRACKED_BYTES}")


def admit_remote_tree(repo: Path, ref: str) -> None:
    from .git_safety import assert_no_execution_filters, run_hardened_git, sanitized_git_env

    enforce_mailbox_disk_quota(repo)
    env = sanitized_git_env(allow_ssh=False)
    assert_no_execution_filters(repo, env)
    proc = run_hardened_git(
        repo,
        ["ls-tree", "-r", "-l", "-z", ref],
        allow_ssh=False,
        timeout=20.0,
        max_stdout=MAX_MAILBOX_TREE_LISTING_BYTES,
        max_stderr=256 * 1024,
        text=False,
        extra_env={"GIT_NO_LAZY_FETCH": "1"},
    )
    if proc.returncode != 0:
        raise LocalHandError(
            "mailbox_tree_invalid",
            proc.stderr.decode("utf-8", errors="replace").strip() or "cannot inspect mailbox tree",
            "failed",
        )
    validate_ls_tree_records(proc.stdout)
