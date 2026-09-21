"""Process-lifetime single-instance lock for one Local Hand state root."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

from .protocol import LocalHandError


@contextmanager
def worker_instance_lock(state_root: Path) -> Iterator[None]:
    """Allow exactly one worker process to own a state root at a time."""
    state_root.mkdir(parents=True, exist_ok=True)
    lock_path = state_root / "worker-instance.lock"
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
                    "worker_instance_busy",
                    f"another Local Hand worker owns state_root: {state_root}",
                    "rejected",
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise LocalHandError(
                    "worker_instance_busy",
                    f"another Local Hand worker owns state_root: {state_root}",
                    "rejected",
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
