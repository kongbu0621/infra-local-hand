"""Bounded filesystem and subprocess I/O primitives for Local Hand.

These helpers turn protocol limits into resource limits: readers never materialize
more than limit+1 bytes, directory scans stop at a fixed ceiling, and subprocess
stdout/stderr are drained continuously while retained bytes stay bounded.
"""
from __future__ import annotations

import os
import selectors
import signal
import stat
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Sequence

from .protocol import LocalHandError


class FileReadUnavailable(LocalHandError):
    """An OS read failure is uncertainty, not proof of invalid file content."""


@dataclass
class CaptureState:
    data: bytearray = field(default_factory=bytearray)
    observed_bytes: int = 0
    too_large: bool = False
    error: str | None = None


def _is_reparse(stat_result: os.stat_result) -> bool:
    attrs = getattr(stat_result, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & flag)


def _lstat_regular(path: Path, code: str) -> os.stat_result:
    try:
        st = path.lstat()
    except OSError as exc:
        raise FileReadUnavailable(code, f"cannot lstat regular file {path.name}; errno={exc.errno}", "indeterminate") from exc
    if stat.S_ISLNK(st.st_mode) or _is_reparse(st):
        raise LocalHandError(code, f"symlink/reparse file rejected: {path.name}", "indeterminate")
    if not stat.S_ISREG(st.st_mode):
        raise LocalHandError(code, f"non-regular file rejected: {path.name}", "indeterminate")
    return st


def read_regular_file_bounded(path: Path, limit: int, code: str) -> bytes:
    """Read at most ``limit+1`` bytes from a non-symlink regular file."""
    before = _lstat_regular(path, code)
    flags = os.O_RDONLY
    # A regular file may become a FIFO after lstat. Open without waiting for
    # a writer, then reject any non-regular descriptor in the fstat check.
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise FileReadUnavailable(code, f"cannot open regular file {path.name}; errno={exc.errno}", "indeterminate") from exc
    read_completed = False
    try:
        after = os.fstat(fd)
        if not stat.S_ISREG(after.st_mode) or _is_reparse(after):
            raise LocalHandError(code, f"opened object is not a regular file: {path.name}", "indeterminate")
        if os.name != "nt" and (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise LocalHandError(code, f"file identity changed during open: {path.name}", "indeterminate")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        read_completed = True
    except OSError as exc:
        raise FileReadUnavailable(code, f"cannot read regular file {path.name}; errno={exc.errno}", "indeterminate") from exc
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            # Close once; a failed close can already have released this fd.
            # Preserve an earlier read/validation error if cleanup also fails.
            if read_completed:
                raise FileReadUnavailable(code, f"cannot close regular file {path.name}; errno={exc.errno}", "indeterminate") from exc
    if len(data) > limit:
        raise LocalHandError(code, f"file exceeds {limit} bytes: {path.name}", "indeterminate")
    return data


def list_directory_bounded(path: Path, limit: int, code: str) -> list[os.DirEntry[str]]:
    """Enumerate at most ``limit+1`` entries, never materializing an unbounded directory."""
    entries: list[os.DirEntry[str]] = []
    try:
        with os.scandir(path) as iterator:
            for entry in iterator:
                entries.append(entry)
                if len(entries) > limit:
                    raise LocalHandError(code, f"directory has more than {limit} entries")
    except LocalHandError:
        raise
    except OSError as exc:
        raise LocalHandError(code, f"cannot enumerate directory: {exc}", "indeterminate") from exc
    entries.sort(key=lambda item: item.name)
    return entries


def directory_usage_bounded(path: Path, *, max_bytes: int, max_entries: int, code: str) -> tuple[int, int]:
    """Measure a directory tree without following symlinks and stop at hard ceilings."""
    total_bytes = 0
    total_entries = 0
    stack = [path]
    try:
        while stack:
            current = stack.pop()
            with os.scandir(current) as iterator:
                for entry in iterator:
                    total_entries += 1
                    if total_entries > max_entries:
                        raise LocalHandError(code, f"directory tree exceeds {max_entries} entries")
                    st = entry.stat(follow_symlinks=False)
                    if stat.S_ISREG(st.st_mode):
                        total_bytes += max(int(st.st_size), 0)
                        if total_bytes > max_bytes:
                            raise LocalHandError(code, f"directory tree exceeds {max_bytes} bytes")
                    elif stat.S_ISDIR(st.st_mode) and not _is_reparse(st):
                        stack.append(Path(entry.path))
    except LocalHandError:
        raise
    except OSError as exc:
        raise LocalHandError(code, f"cannot measure directory tree: {exc}", "indeterminate") from exc
    return total_entries, total_bytes


def drain_pipe_bounded(
    stream: BinaryIO, state: CaptureState, limit: int, stop: threading.Event,
) -> None:
    """Own, drain and close one pipe; cancellation must never become clean EOF.

    POSIX pipe reads are nonblocking so an inherited writer cannot strand the
    reader during cleanup. Only this reader closes its stream: closing a
    BufferedReader from the controlling thread can block on the read lock.
    """
    selector = None
    try:
        if os.name != "nt":
            fd = stream.fileno()
            os.set_blocking(fd, False)
            selector = selectors.DefaultSelector()
            selector.register(fd, selectors.EVENT_READ)
        while not stop.is_set():
            if selector is not None:
                if not selector.select(0.05):
                    continue
                try:
                    chunk = os.read(fd, 64 * 1024)
                except BlockingIOError:
                    continue
            else:
                chunk = stream.read(64 * 1024)
            if not chunk:
                return
            state.observed_bytes += len(chunk)
            remaining = limit - len(state.data)
            if remaining > 0:
                state.data.extend(chunk[:remaining])
            if state.observed_bytes > limit:
                state.too_large = True
        state.error = "capture cancelled before EOF"
    except (OSError, ValueError) as exc:
        state.error = f"{type(exc).__name__}: {exc}"
    finally:
        if selector is not None:
            selector.close()
        try:
            stream.close()
        except (OSError, ValueError) as exc:
            state.error = f"{type(exc).__name__}: {exc}"


def _posix_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_posix_group_gone(pgid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _posix_group_exists(pgid):
            return True
        time.sleep(0.02)
    return not _posix_group_exists(pgid)


def _kill_tree(proc: subprocess.Popen[bytes], *, root_exit_is_confirmation: bool = False) -> bool:
    """Terminate the complete process tree and positively confirm the required boundary.

    Windows has a small race where a short-lived process can exit naturally after
    the output ceiling is observed but before ``taskkill /T`` opens the PID. In
    that output-only case the root process having already exited is acceptable;
    any descendant that still owns the inherited stdout/stderr pipes is caught by
    the bounded capture join below. Timeout termination remains strict and never
    uses this relaxation.
    """
    if os.name == "nt":
        if root_exit_is_confirmation and proc.poll() is not None:
            return True
        try:
            killer = subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
                shell=False,
            )
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                return False
            if killer.returncode == 0:
                return True
            return root_exit_is_confirmation and proc.poll() is not None
        except (OSError, subprocess.TimeoutExpired):
            return False

    pgid = proc.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        return False

    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    if _wait_posix_group_gone(pgid, 0.25):
        return True

    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        return False
    return _wait_posix_group_gone(pgid, 3.0)


def run_process_bounded(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    max_stdout: int,
    max_stderr: int,
    code_prefix: str,
    text: bool = False,
) -> subprocess.CompletedProcess:
    """Run a command with bounded retained output and verified tree termination."""
    creationflags = 0
    start_new_session = False
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        start_new_session = True
    try:
        proc: subprocess.Popen[bytes] = subprocess.Popen(
            list(argv),
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            shell=False,
            creationflags=creationflags,
            start_new_session=start_new_session,
        )
    except OSError as exc:
        raise LocalHandError(f"{code_prefix}_start_failed", f"command start failed: {exc}", "failed") from exc

    assert proc.stdout is not None and proc.stderr is not None
    out_state, err_state = CaptureState(), CaptureState()
    capture_stop = threading.Event()
    out_thread = threading.Thread(target=drain_pipe_bounded, args=(proc.stdout, out_state, max_stdout, capture_stop), daemon=True)
    err_thread = threading.Thread(target=drain_pipe_bounded, args=(proc.stderr, err_state, max_stderr, capture_stop), daemon=True)
    out_thread.start()
    err_thread.start()

    stop_reason: str | None = None
    deadline = time.monotonic() + timeout
    try:
        # The root exiting does not finish its process group or inherited pipes.
        # Keep the same deadline until all three completion boundaries agree.
        while (proc.poll() is None or out_thread.is_alive() or err_thread.is_alive()
               or (os.name != "nt" and _posix_group_exists(proc.pid))):
            if out_state.too_large or err_state.too_large:
                stop_reason = "output"
                break
            if time.monotonic() >= deadline:
                stop_reason = "timeout"
                break
            time.sleep(0.02)
        if stop_reason is not None:
            if not _kill_tree(proc, root_exit_is_confirmation=(stop_reason == "output")):
                raise LocalHandError(
                    f"{code_prefix}_termination_unconfirmed",
                    f"{stop_reason} limit reached and process-tree termination was not confirmed",
                    "indeterminate",
                )
        returncode = proc.poll()
        if returncode is None:
            returncode = proc.wait(timeout=1)

        out_thread.join(2)
        err_thread.join(2)
        if out_thread.is_alive() or err_thread.is_alive() or out_state.error or err_state.error:
            raise LocalHandError(f"{code_prefix}_capture_unconfirmed", "output capture did not terminate cleanly", "indeterminate")
    finally:
        capture_stop.set()
        out_thread.join(2)
        err_thread.join(2)

    if stop_reason == "timeout":
        raise LocalHandError(f"{code_prefix}_timeout", f"command timed out after {timeout:.0f}s", "failed")
    if stop_reason == "output" or out_state.too_large or err_state.too_large:
        raise LocalHandError(
            f"{code_prefix}_output_too_large",
            f"command output exceeded limits stdout={max_stdout} stderr={max_stderr}",
            "failed",
        )

    stdout_b, stderr_b = bytes(out_state.data), bytes(err_state.data)
    if text:
        return subprocess.CompletedProcess(
            list(argv), int(returncode),
            stdout_b.decode("utf-8", errors="replace"),
            stderr_b.decode("utf-8", errors="replace"),
        )
    return subprocess.CompletedProcess(list(argv), int(returncode), stdout_b, stderr_b)
