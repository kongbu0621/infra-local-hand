"""Allowlisted validation profiles for Local Hand."""
from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
import time
from typing import Any, BinaryIO

from .bounded_io import CaptureState as _CaptureState, drain_pipe_bounded
from .paths import NodeProfile, repository_root
from .protocol import LocalHandError

MAX_OUTPUT_BYTES = 2 * 1024 * 1024
TERMINATE_GRACE_SECONDS = 2.0
KILL_GRACE_SECONDS = 2.0
CAPTURE_JOIN_SECONDS = 2.0


def _filtered_env() -> dict[str, str]:
    # Deliberately do not inherit PYTHONPATH or VIRTUAL_ENV from the Local Hand
    # service. Validation profiles must describe their own executable explicitly.
    allowed = {
        "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR",
        "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "PATHEXT", "COMSPEC",
    }
    env = {k: v for k, v in os.environ.items() if k in allowed}
    # The worker startup contract already binds this non-secret identity. Pass
    # only its canonical form so in-repository provenance tests remain
    # deterministic under service accounts; never forward other LOCAL_HAND_*
    # bindings, credentials, or Python import environment.
    implementation_commit = os.environ.get("LOCAL_HAND_IMPLEMENTATION_COMMIT", "").strip()
    if re.fullmatch(r"[0-9a-f]{40,64}", implementation_commit):
        env["LOCAL_HAND_IMPLEMENTATION_COMMIT"] = implementation_commit
    # Validation runs from inside the managed repository.  Prevent Python
    # commands (including pytest collection/imports) from manufacturing
    # __pycache__ entries that would make an otherwise clean worktree dirty.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _drain_bounded(stream: BinaryIO, state: _CaptureState, stop: threading.Event) -> None:
    """Continuously drain a child pipe while retaining at most MAX_OUTPUT_BYTES."""
    drain_pipe_bounded(stream, state, MAX_OUTPUT_BYTES, stop)


def _decoded_capture(state: _CaptureState) -> str:
    return bytes(state.data).decode("utf-8", errors="replace")


class ValidationFailed(LocalHandError):
    def __init__(self, code: str, message: str, details: dict[str, Any]) -> None:
        super().__init__(code, message, "failed")
        self.details = details


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


def _terminate_tree(proc: subprocess.Popen[Any]) -> tuple[int | None, bool, str]:
    """Boundedly terminate the whole process tree, not just the direct child."""
    if os.name == "nt":
        method = "windows-taskkill-tree"
        try:
            killer = subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                # taskkill emits text in the active Windows console code page.
                # Its output is intentionally unused, so do not create text pipes
                # whose background readers could decode those bytes as UTF-8.
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=TERMINATE_GRACE_SECONDS,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None, False, method
        try:
            exit_code = proc.wait(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            return None, False, method
        # A nonzero taskkill result means tree termination was not positively
        # confirmed; fail closed even if the direct child happened to exit.
        return exit_code, killer.returncode == 0, method

    method = "posix-process-group"
    pgid = proc.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return proc.poll(), True, method
    except OSError:
        return None, False, method

    try:
        exit_code = proc.wait(timeout=TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        exit_code = None

    if _wait_posix_group_gone(pgid, 0.25):
        return exit_code if exit_code is not None else proc.poll(), True, method

    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return exit_code if exit_code is not None else proc.poll(), True, method
    except OSError:
        return None, False, method

    if exit_code is None:
        try:
            exit_code = proc.wait(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            return None, False, method
    return exit_code, _wait_posix_group_gone(pgid, KILL_GRACE_SECONDS), method


def run_profile(profile: NodeProfile, repository: str, profile_id: str) -> dict[str, Any]:
    repo = repository_root(profile, repository)
    repo_spec = profile.repositories[repository]
    if profile_id not in repo_spec.validations:
        raise LocalHandError("validation_profile_not_allowlisted", f"unknown validation profile: {profile_id}")
    spec = repo_spec.validations[profile_id]
    if not spec.replay_safe:
        raise LocalHandError(
            "validation_profile_not_replay_safe",
            f"validation profile is not explicitly replay-safe: {profile_id}",
        )

    creationflags = 0
    start_new_session = False
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        start_new_session = True

    started = time.monotonic()
    timed_out = False
    termination_confirmed = True
    termination_scope = "none"
    termination_method = "none"

    try:
        proc = subprocess.Popen(
            list(spec.argv),
            cwd=str(repo),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_filtered_env(),
            shell=False,
            creationflags=creationflags,
            start_new_session=start_new_session,
        )
    except FileNotFoundError as exc:
        raise LocalHandError(
            "validation_executable_not_found",
            f"validation executable not found: {spec.argv[0]}",
            "failed",
        ) from exc
    except OSError as exc:
        raise LocalHandError("validation_start_failed", f"validation start failed: {exc}", "failed") from exc

    assert proc.stdout is not None and proc.stderr is not None
    stdout_state = _CaptureState()
    stderr_state = _CaptureState()
    capture_stop = threading.Event()
    stdout_thread = threading.Thread(target=_drain_bounded, args=(proc.stdout, stdout_state, capture_stop), daemon=True)
    stderr_thread = threading.Thread(target=_drain_bounded, args=(proc.stderr, stderr_state, capture_stop), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    try:
        deadline = started + spec.timeout_seconds
        while (proc.poll() is None or stdout_thread.is_alive() or stderr_thread.is_alive()
               or (os.name != "nt" and _posix_group_exists(proc.pid))):
            if time.monotonic() >= deadline:
                timed_out = True
                termination_scope = "process_tree"
                exit_code, termination_confirmed, termination_method = _terminate_tree(proc)
                break
            time.sleep(0.02)
        else:
            exit_code = proc.returncode

        stdout_thread.join(CAPTURE_JOIN_SECONDS)
        stderr_thread.join(CAPTURE_JOIN_SECONDS)
        capture_confirmed = not stdout_thread.is_alive() and not stderr_thread.is_alive()
        duration = time.monotonic() - started
        stdout = _decoded_capture(stdout_state)
        stderr = _decoded_capture(stderr_state)
    finally:
        # Readers own their pipes. A controller-side close can itself block;
        # cancellation is bounded and cannot promote incomplete capture to PASS.
        capture_stop.set()
        stdout_thread.join(CAPTURE_JOIN_SECONDS)
        stderr_thread.join(CAPTURE_JOIN_SECONDS)

    if not termination_confirmed:
        raise LocalHandError(
            "validation_termination_unconfirmed",
            "validation timed out and worker could not confirm process-tree termination",
            "indeterminate",
        )
    if not capture_confirmed or stdout_state.error or stderr_state.error:
        raise LocalHandError(
            "validation_output_capture_unconfirmed",
            "validation output pipes could not be boundedly drained/closed",
            "indeterminate",
        )

    details = {
        "repository": repository,
        "profile": profile_id,
        "replay_safe": True,
        "argv": list(spec.argv),
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_seconds": round(duration, 6),
        "timed_out": timed_out,
        "termination_confirmed": termination_confirmed,
        "termination_scope": termination_scope,
        "termination_method": termination_method,
        "output_too_large": stdout_state.too_large or stderr_state.too_large,
        "output_capture_model": "bounded-drain",
        "stdout_captured_bytes": len(stdout_state.data),
        "stderr_captured_bytes": len(stderr_state.data),
        "stdout_observed_bytes": stdout_state.observed_bytes,
        "stderr_observed_bytes": stderr_state.observed_bytes,
        "pipes_closed": True,
        "environment_sanitized": True,
        "bytecode_writes_disabled": True,
        "inherited_pythonpath": False,
        "inherited_virtual_env": False,
    }

    if stdout_state.too_large or stderr_state.too_large:
        raise ValidationFailed(
            "validation_output_too_large",
            f"validation output exceeded {MAX_OUTPUT_BYTES} bytes per stream",
            details,
        )
    if timed_out:
        raise ValidationFailed("validation_timeout", "validation timed out", details)
    if exit_code != 0:
        raise ValidationFailed("validation_failed", f"validation exited with code {exit_code}", details)
    return details
