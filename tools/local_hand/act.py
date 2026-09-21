"""Mutating Local Hand actions."""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from .bounded_io import read_regular_file_bounded
from .paths import NodeProfile, repository_root, safe_existing_path
from .protocol import LocalHandError, MAX_TEXT_BYTES


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_cas_target(path: Path) -> bytes:
    """Read an existing CAS target under the same ceiling as fs.read_text."""
    try:
        return read_regular_file_bounded(path, MAX_TEXT_BYTES, "write_source_invalid")
    except LocalHandError as exc:
        if "exceeds" in exc.message:
            raise LocalHandError(
                "write_source_too_large",
                f"existing write target exceeds {MAX_TEXT_BYTES} bytes: {path.name}",
            ) from exc
        raise


def _regular_mode_no_follow(path: Path) -> int:
    try:
        st = path.lstat()
    except OSError as exc:
        raise LocalHandError("write_source_invalid", f"cannot lstat write target: {path.name}", "indeterminate") from exc
    attrs = getattr(st, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(st.st_mode) or bool(attrs & reparse) or not stat.S_ISREG(st.st_mode):
        raise LocalHandError("write_source_invalid", f"write target is not a regular non-reparse file: {path.name}")
    return stat.S_IMODE(st.st_mode)


@contextmanager
def _repository_write_lease(repo: Path, lease_root: Path | None) -> Iterator[None]:
    """Cross-process cooperative lease for Local Hand writers."""
    if lease_root is None:
        lease_root = Path(tempfile.gettempdir()) / "local-hand-write-leases"
    lease_root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()
    lock_path = lease_root / f"{key}.lock"
    handle: BinaryIO = lock_path.open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
                os.fsync(handle.fileno())
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise LocalHandError(
                    "workspace_lease_busy",
                    f"another Local Hand writer holds the repository lease: {repo}",
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise LocalHandError(
                    "workspace_lease_busy",
                    f"another Local Hand writer holds the repository lease: {repo}",
                ) from exc
        locked = True
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def fs_write_text_cas(
    profile: NodeProfile,
    repository: str,
    relative_path: str,
    expected_sha256: str,
    content: str,
    *,
    lease_root: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise LocalHandError("invalid_expected_sha256", "expected_sha256 must be a 64-character hex digest")
    try:
        int(expected_sha256, 16)
    except ValueError as exc:
        raise LocalHandError("invalid_expected_sha256", "expected_sha256 must be hexadecimal") from exc
    if not isinstance(content, str):
        raise LocalHandError("invalid_content", "content must be a string")
    try:
        desired = content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise LocalHandError("invalid_content_utf8", "content must be valid UTF-8 text") from exc
    if len(desired) > MAX_TEXT_BYTES:
        raise LocalHandError("write_too_large", f"encoded content exceeds {MAX_TEXT_BYTES} bytes")

    repo = repository_root(profile, repository)
    repo_spec = profile.repositories[repository]
    if not repo_spec.single_writer:
        raise LocalHandError(
            "workspace_not_single_writer",
            "fs.write_text_cas is disabled unless repository.single_writer=true in the Node Profile",
        )

    with _repository_write_lease(repo, lease_root):
        target = safe_existing_path(repo, relative_path, expect="file")
        current = _read_cas_target(target)
        current_hash = _sha256(current)
        desired_hash = _sha256(desired)

        if current_hash == desired_hash:
            return {
                "repository": repository,
                "relative_path": relative_path,
                "old_sha256": current_hash,
                "new_sha256": desired_hash,
                "bytes": len(desired),
                "already_applied": True,
                "read_back_verified": True,
                "cas_model": "single-writer-optimistic",
                "local_hand_lease": True,
                "bounded_existing_reads": True,
            }

        if current_hash != expected_sha256.lower():
            raise LocalHandError(
                "stale_write",
                f"file changed since observation: expected={expected_sha256.lower()} actual={current_hash}",
                "stale",
            )

        parent = target.parent
        original_mode = _regular_mode_no_follow(target)
        temp_path: Path | None = None
        try:
            fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.local-hand-", dir=str(parent))
            temp_path = Path(temp_name)
            with os.fdopen(fd, "wb") as handle:
                handle.write(desired)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temp_path, original_mode)
            except OSError:
                pass

            pre_replace_target = safe_existing_path(repo, relative_path, expect="file")
            if pre_replace_target.parent != parent:
                raise LocalHandError(
                    "stale_write",
                    f"file parent changed during CAS: {relative_path}",
                    "stale",
                )
            pre_replace = _read_cas_target(pre_replace_target)
            pre_replace_hash = _sha256(pre_replace)
            if pre_replace_hash != current_hash:
                raise LocalHandError(
                    "stale_write",
                    f"file changed during CAS: expected-current={current_hash} actual={pre_replace_hash}",
                    "stale",
                )

            os.replace(temp_path, pre_replace_target)
            target = pre_replace_target
            temp_path = None

            if os.name != "nt":
                try:
                    dir_fd = os.open(parent, os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError:
                    pass

            read_back = _read_cas_target(target)
            read_back_hash = _sha256(read_back)
            if read_back != desired or read_back_hash != desired_hash:
                raise LocalHandError(
                    "write_readback_mismatch",
                    f"atomic write occurred but read-back verification failed: {relative_path}",
                    "indeterminate",
                )

            return {
                "repository": repository,
                "relative_path": relative_path,
                "old_sha256": current_hash,
                "new_sha256": desired_hash,
                "bytes": len(desired),
                "already_applied": False,
                "read_back_verified": True,
                "cas_model": "single-writer-optimistic",
                "local_hand_lease": True,
                "bounded_existing_reads": True,
            }
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
