"""Minimal controller adapter for Local Hand's Git mailbox transport.

This module deliberately does not expose a shell, a desktop, or a generic
command API.  It only publishes already-valid Local Hand tasks and accepts a
Result that is bound to the exact task digest, action, and target node.
"""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import stat
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol, runtime_checkable

from local_hand.bounded_io import list_directory_bounded, read_regular_file_bounded
from local_hand.config import TransportPolicy, parse_transport, strict_json, validate_branch
from local_hand.mailbox_safety import atomic_create_control_file, target_lexists, validate_control_target
from local_hand.protocol import (
    MAX_TASK_ID_DIGITS,
    MAX_RESULT_JSON_BYTES,
    MAX_TASK_JSON_BYTES,
    TASK_ID_RE,
    TASK_SCHEMA,
    LocalHandError,
    conflict_filename,
    task_digest,
)
from local_hand.worker import (
    load_json_bounded,
    run_git,
    sync_mailbox,
    validate_remote_result,
    validate_task,
)

CONNECT_MARKER_SCHEMA = "local-hand-connect-mailbox/v2"
CONNECT_MARKER_NAME = "local-hand-connect.json"
PUSH_ATTEMPTS = 4
MAX_CONFLICT_FILES = 4096
MAX_SLEEP_SLICE_SECONDS = 60.0
_THREAD_LOCK = threading.Lock()
_PROVENANCE_FIELDS = ("implementation_commit", "package_digest", "profile_digest")
_TASK_FIELDS = frozenset({"schema_version", "task_id", "target_node", "action", "params"})
_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "task_digest",
        "target_node",
        "node_id",
        "action",
        "worker_version",
        "implementation_commit",
        "package_digest",
        "profile_digest",
        "status",
        "details",
        "error_code",
        "error",
    }
)
_COMMIT_RE = re.compile(r"^[0-9a-f]{40,64}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _json_bytes(value: Any, maximum: int, code: str) -> bytes:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(data) > maximum:
        raise LocalHandError(code, f"serialized JSON exceeds {maximum} bytes")
    return data


def _absolute_file_from_env(name: str, *, executable: bool = False) -> Path:
    value = os.environ.get(name, "").strip()
    path = Path(value)
    if not value or not path.is_absolute() or not path.is_file():
        raise LocalHandError(
            "controller_binding_invalid",
            f"{name} must name an existing absolute file",
            "indeterminate",
        )
    if executable and os.name != "nt" and not os.access(path, os.X_OK):
        raise LocalHandError(
            "controller_binding_invalid",
            f"{name} must name an executable file",
            "indeterminate",
        )
    return path


def validate_controller_bindings() -> None:
    """Require pinned Git/SSH paths and a dedicated mailbox credential."""
    _absolute_file_from_env("LOCAL_HAND_GIT_EXECUTABLE", executable=True)
    _absolute_file_from_env("LOCAL_HAND_SSH_EXECUTABLE", executable=True)
    _absolute_file_from_env("LOCAL_HAND_MAILBOX_SSH_KEY")
    _absolute_file_from_env("LOCAL_HAND_KNOWN_HOSTS")
    raw_timeout = os.environ.get("LOCAL_HAND_GIT_TIMEOUT_SECONDS")
    if raw_timeout is not None:
        try:
            git_timeout = float(raw_timeout)
        except (TypeError, ValueError) as exc:
            raise LocalHandError(
                "controller_binding_invalid",
                "LOCAL_HAND_GIT_TIMEOUT_SECONDS must be a finite positive number",
                "indeterminate",
            ) from exc
        if not math.isfinite(git_timeout) or git_timeout <= 0:
            raise LocalHandError(
                "controller_binding_invalid",
                "LOCAL_HAND_GIT_TIMEOUT_SECONDS must be a finite positive number",
                "indeterminate",
            )


def new_task_id() -> str:
    """Create a sortable, collision-resistant id accepted by Task v1."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"LH{timestamp}{secrets.randbelow(1_000_000):06d}"


def _validate_branch(branch: str) -> str:
    try:
        return validate_branch(branch)
    except LocalHandError as exc:
        raise LocalHandError("controller_branch_rejected", exc.message) from exc


def _validate_controller_task(task: Any) -> dict[str, Any]:
    if not isinstance(task, dict) or set(task) != _TASK_FIELDS:
        raise LocalHandError(
            "controller_task_shape_invalid",
            "Task v1 must contain exactly schema_version, task_id, target_node, action and params",
        )
    if not isinstance(task.get("task_id"), str) or TASK_ID_RE.fullmatch(task["task_id"]) is None:
        raise LocalHandError(
            "controller_task_id_invalid",
            f"Controller task_id must match LH plus 4-{MAX_TASK_ID_DIGITS} decimal digits",
        )
    return validate_task(task)


def _validate_controller_result(
    value: Any,
    task: dict[str, Any],
) -> dict[str, Any]:
    result = validate_remote_result(
        value,
        task["task_id"],
        task["action"],
        task["target_node"],
        task_digest(task),
    )
    if set(result) != _RESULT_FIELDS or not isinstance(result.get("details"), dict):
        raise LocalHandError(
            "controller_result_shape_invalid",
            "Result v1 must contain the exact envelope and structured details",
            "indeterminate",
        )
    succeeded = result["status"] == "succeeded"
    error_code = result.get("error_code")
    error = result.get("error")
    if succeeded:
        valid_error = error_code is None and error is None
    else:
        valid_error = (
            isinstance(error_code, str)
            and bool(error_code)
            and isinstance(error, str)
            and bool(error)
        )
    if not valid_error:
        raise LocalHandError(
            "controller_result_shape_invalid",
            "Result v1 status/error fields are inconsistent",
            "indeterminate",
        )
    return result


def _validate_wait_timing(timeout_seconds: float, poll_seconds: float) -> tuple[float, float]:
    values = ((timeout_seconds, True), (poll_seconds, False))
    for value, allow_zero in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            or (not allow_zero and value == 0)
        ):
            raise LocalHandError(
                "controller_wait_invalid",
                "timeout must be finite and >= 0; poll interval must be finite and > 0",
            )
    return float(timeout_seconds), float(poll_seconds)


def build_task(
    target_node: str,
    action: str,
    params: dict[str, Any],
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    task = {
        "schema_version": TASK_SCHEMA,
        "task_id": task_id or new_task_id(),
        "target_node": target_node,
        "action": action,
        "params": params,
    }
    _validate_controller_task(task)
    _json_bytes(task, MAX_TASK_JSON_BYTES, "task_too_large")
    return task


def _marker_path(mailbox: Path) -> Path:
    git_dir = mailbox / ".git"
    try:
        git_stat = git_dir.lstat()
    except OSError as exc:
        raise LocalHandError(
            "controller_mailbox_not_dedicated",
            "controller mailbox must be a dedicated Git clone with a .git directory",
            "indeterminate",
        ) from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        stat.S_ISLNK(git_stat.st_mode)
        or bool(getattr(git_stat, "st_file_attributes", 0) & reparse_flag)
        or not stat.S_ISDIR(git_stat.st_mode)
    ):
        raise LocalHandError(
            "controller_mailbox_not_dedicated",
            "controller mailbox .git must be a real local directory",
            "indeterminate",
        )
    return git_dir / CONNECT_MARKER_NAME


def _read_remote_urls(mailbox: Path) -> tuple[str, str]:
    fetch = run_git(["remote", "get-url", "--all", "origin"], mailbox).stdout.splitlines()
    push = run_git(["remote", "get-url", "--push", "--all", "origin"], mailbox).stdout.splitlines()
    if len(fetch) != 1 or len(push) != 1 or not fetch[0] or not push[0]:
        raise LocalHandError(
            "controller_mailbox_invalid",
            "origin must resolve to exactly one fetch URL and one push URL",
            "indeterminate",
        )
    return fetch[0], push[0]


def _assert_exact_toplevel(mailbox: Path) -> Path:
    try:
        resolved = mailbox.resolve(strict=True)
    except OSError as exc:
        raise LocalHandError("controller_mailbox_invalid", "mailbox root does not exist", "indeterminate") from exc
    proc = run_git(["rev-parse", "--show-toplevel"], resolved)
    try:
        top = Path(proc.stdout.strip()).resolve(strict=True)
    except OSError as exc:
        raise LocalHandError("controller_mailbox_invalid", "cannot resolve mailbox Git top-level", "indeterminate") from exc
    if top != resolved:
        raise LocalHandError(
            "controller_mailbox_not_dedicated",
            "mailbox path must be the exact root of a dedicated Git clone",
            "indeterminate",
        )
    return resolved


def _resolve_existing_mailbox(mailbox: Path) -> Path:
    try:
        return mailbox.resolve(strict=True)
    except OSError as exc:
        raise LocalHandError("controller_mailbox_invalid", "mailbox root does not exist", "indeterminate") from exc


@contextmanager
def _controller_mailbox_lock(mailbox: Path):
    """Serialize all Git state transitions for one admitted controller clone."""
    lock_path = _marker_path(mailbox).parent / "local-hand-connect.lock"
    with _THREAD_LOCK:
        handle = lock_path.open("a+b")
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
                        "controller_mailbox_busy",
                        "another Local Hand Connect process owns this mailbox clone",
                    ) from exc
            else:
                import fcntl

                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    raise LocalHandError(
                        "controller_mailbox_busy",
                        "another Local Hand Connect process owns this mailbox clone",
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


def _write_create_only(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise LocalHandError("controller_mailbox_already_initialized", f"marker already exists: {path}") from exc
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fsync(fd)
    finally:
        os.close(fd)


def initialize_controller_mailbox(
    mailbox: Path,
    branch: str,
    *,
    policy: TransportPolicy,
) -> dict[str, Any]:
    """Mark a clean, exact mailbox clone as reset-safe controller state."""
    validate_controller_bindings()
    _validate_branch(branch)
    policy = parse_transport(policy.as_dict())
    if branch != policy.branch:
        raise LocalHandError("controller_branch_rejected", "branch differs from the admitted policy")
    mailbox = _assert_exact_toplevel(mailbox)
    remote_url, push_url = _read_remote_urls(mailbox)
    allowed = frozenset(policy.allowed_remote_urls)
    if remote_url not in allowed or push_url not in allowed:
        raise LocalHandError("controller_remote_rejected", "mailbox origin is not allowlisted")
    status = run_git(["status", "--porcelain=v1", "--untracked-files=all"], mailbox)
    if status.stdout.strip():
        raise LocalHandError(
            "controller_mailbox_dirty",
            "mailbox clone must be clean before it is admitted for reset-based synchronization",
        )
    marker = {
        "schema_version": CONNECT_MARKER_SCHEMA,
        "mailbox_root": str(mailbox),
        "branch": branch,
        "remote_url": remote_url,
        "push_url": push_url,
        "transport_policy": policy.as_dict(),
        "transport_policy_digest": policy.digest,
    }
    _write_create_only(_marker_path(mailbox), _json_bytes(marker, 16 * 1024, "controller_marker_too_large"))
    return marker


def _read_admitted_marker(mailbox: Path) -> tuple[dict[str, Any], TransportPolicy]:
    try:
        marker = strict_json(read_regular_file_bounded(_marker_path(mailbox), 16 * 1024, "controller_marker_invalid"))
        expected = {"schema_version", "mailbox_root", "branch", "remote_url", "push_url", "transport_policy", "transport_policy_digest"}
        if not isinstance(marker, dict) or set(marker) != expected or marker["schema_version"] != CONNECT_MARKER_SCHEMA:
            raise ValueError("marker shape/schema")
        policy = parse_transport(marker["transport_policy"])
        if marker["transport_policy_digest"] != policy.digest or marker["branch"] != policy.branch:
            raise ValueError("marker policy digest/branch")
        return marker, policy
    except (OSError, ValueError, LocalHandError) as exc:
        raise LocalHandError("controller_marker_invalid", "controller mailbox marker is invalid", "indeterminate") from exc


def validate_controller_mailbox(mailbox: Path, branch: str, *, expected_policy: TransportPolicy | None = None) -> dict[str, Any]:
    validate_controller_bindings()
    _validate_branch(branch)
    mailbox = _assert_exact_toplevel(mailbox)
    marker, policy = _read_admitted_marker(mailbox)
    if expected_policy is not None and policy.digest != parse_transport(expected_policy.as_dict()).digest:
        raise LocalHandError("controller_marker_mismatch", "admitted transport policy changed", "indeterminate")
    if marker.get("mailbox_root") != str(mailbox) or marker.get("branch") != branch:
        raise LocalHandError("controller_marker_mismatch", "controller mailbox root/branch changed", "indeterminate")
    remote_url, push_url = _read_remote_urls(mailbox)
    if remote_url not in policy.allowed_remote_urls or push_url not in policy.allowed_remote_urls:
        raise LocalHandError("controller_remote_rejected", "mailbox origin is not allowlisted", "indeterminate")
    if marker.get("remote_url") != remote_url or marker.get("push_url") != push_url:
        raise LocalHandError("controller_marker_mismatch", "controller mailbox origin changed", "indeterminate")
    return marker


def _load_task_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_regular_file_bounded(path, MAX_TASK_JSON_BYTES, "controller_task_invalid").decode("utf-8"))
    except LocalHandError:
        raise
    except Exception as exc:
        raise LocalHandError("controller_task_invalid", "task file is not valid UTF-8 JSON") from exc
    return _validate_controller_task(value)


def _same_task(existing_path: Path, task: dict[str, Any]) -> bool:
    try:
        existing = load_json_bounded(existing_path, MAX_TASK_JSON_BYTES, "controller_remote_task_invalid")
        existing = _validate_controller_task(existing)
    except LocalHandError as exc:
        raise LocalHandError("controller_remote_task_invalid", exc.message, "indeterminate") from exc
    return task_digest(existing) == task_digest(task)


def _is_push_race(returncode: int, stdout: str, stderr: str) -> bool:
    if returncode == 0:
        return False
    rendered = f"{stdout}\n{stderr}".lower()
    return any(token in rendered for token in ("non-fast-forward", "fetch first", "[rejected]"))


def _submit_task_locked(mailbox: Path, branch: str, task: dict[str, Any]) -> dict[str, Any]:
    task = _validate_controller_task(task)
    data = _json_bytes(task, MAX_TASK_JSON_BYTES, "task_too_large")
    digest = task_digest(task)
    validate_controller_mailbox(mailbox, branch)

    for attempt in range(1, PUSH_ATTEMPTS + 1):
        sync_mailbox(mailbox, branch)
        target = mailbox / "_executor_spike" / "tasks" / f"{task['task_id']}.json"
        validate_control_target(mailbox, target)
        if target_lexists(target):
            if _same_task(target, task):
                return {
                    "operation": "submit",
                    "status": "already_present",
                    "task_id": task["task_id"],
                    "task_digest": digest,
                }
            raise LocalHandError(
                "controller_task_id_conflict",
                f"task id already exists with different digest: {task['task_id']}",
                "indeterminate",
            )

        atomic_create_control_file(mailbox, target, data)
        relative = target.relative_to(mailbox).as_posix()
        run_git(["add", "--", relative], mailbox)
        run_git(
            [
                "-c", "user.name=local-hand-connect",
                "-c", "user.email=local-hand-connect@local.invalid",
                "-c", "commit.gpgsign=false",
                "commit", "-m", f"local-hand-task-{task['task_id']}",
            ],
            mailbox,
        )
        pushed = run_git(["push", "origin", f"HEAD:{branch}"], mailbox, check=False)
        if pushed.returncode == 0:
            return {
                "operation": "submit",
                "status": "submitted",
                "task_id": task["task_id"],
                "task_digest": digest,
                "attempt": attempt,
            }
        if not _is_push_race(pushed.returncode, pushed.stdout, pushed.stderr) or attempt == PUSH_ATTEMPTS:
            raise LocalHandError(
                "controller_publish_failed",
                f"task push failed ({pushed.returncode}) attempt={attempt}",
                "indeterminate",
            )
    raise LocalHandError("controller_publish_failed", "task publication attempts exhausted", "indeterminate")


def submit_task(mailbox: Path, branch: str, task: dict[str, Any]) -> dict[str, Any]:
    mailbox = _resolve_existing_mailbox(mailbox)
    with _controller_mailbox_lock(mailbox):
        return _submit_task_locked(mailbox, branch, task)


def _matching_conflict(mailbox: Path, task: dict[str, Any]) -> dict[str, Any] | None:
    conflicts = mailbox / "_executor_spike" / "conflicts"
    # Preserve the bounded directory-count gate before exact lookup.
    list_directory_bounded(conflicts, MAX_CONFLICT_FILES, "controller_conflict_count_exceeded")
    path = conflicts / conflict_filename(task_digest(task))
    if not target_lexists(path):
        return None
    validate_control_target(mailbox, path, require_existing=True)
    value = load_json_bounded(path, MAX_RESULT_JSON_BYTES, "controller_conflict_invalid")
    return _validate_controller_result(value, task)


def validate_expected_provenance(expected: dict[str, Any]) -> dict[str, str]:
    if not isinstance(expected, dict) or set(expected) != set(_PROVENANCE_FIELDS):
        raise LocalHandError(
            "controller_provenance_policy_invalid",
            "expected provenance must contain exactly implementation_commit, package_digest and profile_digest",
        )
    normalized: dict[str, str] = {}
    for field in _PROVENANCE_FIELDS:
        value = expected.get(field)
        if not isinstance(value, str):
            raise LocalHandError("controller_provenance_policy_invalid", f"expected {field} must be a string")
        pattern = _COMMIT_RE if field == "implementation_commit" else _DIGEST_RE
        if pattern.fullmatch(value) is None:
            raise LocalHandError("controller_provenance_policy_invalid", f"expected {field} has invalid format")
        normalized[field] = value
    return normalized


def _enforce_expected_provenance(result: dict[str, Any], expected: dict[str, Any] | None) -> dict[str, Any]:
    if expected is None:
        return result
    policy = validate_expected_provenance(expected)
    mismatched_fields = [
        field
        for field in _PROVENANCE_FIELDS
        if str(result.get(field, "")).lower() != policy[field]
    ]
    if mismatched_fields:
        raise LocalHandError(
            "controller_provenance_mismatch",
            "result provenance does not match the admitted deployment: " + ", ".join(mismatched_fields),
            "indeterminate",
        )
    return result


def _wait_for_result_locked(
    mailbox: Path,
    branch: str,
    task: dict[str, Any],
    *,
    timeout_seconds: float = 120.0,
    poll_seconds: float = 2.0,
    expected_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task = _validate_controller_task(task)
    timeout_seconds, poll_seconds = _validate_wait_timing(timeout_seconds, poll_seconds)
    validate_controller_mailbox(mailbox, branch)
    deadline = time.monotonic() + timeout_seconds
    while True:
        sync_mailbox(mailbox, branch)
        result_path = mailbox / "_executor_spike" / "results" / f"{task['task_id']}.json"
        validate_control_target(mailbox, result_path)
        if target_lexists(result_path):
            value = load_json_bounded(result_path, MAX_RESULT_JSON_BYTES, "controller_result_invalid")
            return _enforce_expected_provenance(
                _validate_controller_result(value, task),
                expected_provenance,
            )
        conflict = _matching_conflict(mailbox, task)
        if conflict is not None:
            return _enforce_expected_provenance(conflict, expected_provenance)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LocalHandError(
                "controller_wait_timeout",
                f"no exact result before timeout for {task['task_id']}",
                "indeterminate",
            )
        time.sleep(min(poll_seconds, remaining, MAX_SLEEP_SLICE_SECONDS))


def wait_for_result(
    mailbox: Path,
    branch: str,
    task: dict[str, Any],
    *,
    timeout_seconds: float = 120.0,
    poll_seconds: float = 2.0,
    expected_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mailbox = _resolve_existing_mailbox(mailbox)
    with _controller_mailbox_lock(mailbox):
        return _wait_for_result_locked(
            mailbox,
            branch,
            task,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
            expected_provenance=expected_provenance,
        )


def call_task(
    mailbox: Path,
    branch: str,
    task: dict[str, Any],
    *,
    timeout_seconds: float = 120.0,
    poll_seconds: float = 2.0,
    expected_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mailbox = _resolve_existing_mailbox(mailbox)
    with _controller_mailbox_lock(mailbox):
        _submit_task_locked(mailbox, branch, task)
        return _wait_for_result_locked(
            mailbox,
            branch,
            task,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
            expected_provenance=expected_provenance,
        )


def load_task_file(path: Path) -> dict[str, Any]:
    return _load_task_file(path)


@runtime_checkable
class LocalHandControllerAdapter(Protocol):
    """Runtime-neutral port exposed to an authorized Cognitive/Control Plane."""

    def build(
        self,
        target_node: str,
        action: str,
        params: dict[str, Any],
        *,
        task_id: str | None = None,
    ) -> dict[str, Any]: ...

    def submit(self, task: dict[str, Any]) -> dict[str, Any]: ...

    def wait(
        self,
        task: dict[str, Any],
        *,
        timeout_seconds: float = 120.0,
        poll_seconds: float = 2.0,
    ) -> dict[str, Any]: ...

    def call(
        self,
        task: dict[str, Any],
        *,
        timeout_seconds: float = 120.0,
        poll_seconds: float = 2.0,
    ) -> dict[str, Any]: ...


class GitMailboxControllerAdapter:
    """P0 implementation of the Controller port over one admitted Git clone."""

    __slots__ = ("mailbox", "branch", "policy", "_expected_provenance")

    def __init__(
        self,
        mailbox: Path,
        *,
        branch: str | None = None,
        policy: TransportPolicy | None = None,
        expected_provenance: dict[str, Any] | None = None,
    ) -> None:
        self.mailbox = Path(mailbox)
        self.policy = parse_transport(policy.as_dict()) if policy is not None else _read_admitted_marker(self.mailbox)[1]
        self.branch = _validate_branch(self.policy.branch if branch is None else branch)
        if self.branch != self.policy.branch:
            raise LocalHandError("controller_branch_rejected", "branch differs from explicit policy")
        self._expected_provenance = (
            validate_expected_provenance(expected_provenance)
            if expected_provenance is not None
            else None
        )

    @property
    def expected_provenance(self) -> dict[str, str] | None:
        if self._expected_provenance is None:
            return None
        return dict(self._expected_provenance)

    def initialize(self) -> dict[str, Any]:
        return initialize_controller_mailbox(self.mailbox, self.branch, policy=self.policy)

    def build(
        self,
        target_node: str,
        action: str,
        params: dict[str, Any],
        *,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        return build_task(target_node, action, params, task_id=task_id)

    def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        validate_controller_mailbox(self.mailbox, self.branch, expected_policy=self.policy)
        return submit_task(self.mailbox, self.branch, task)

    def wait(
        self,
        task: dict[str, Any],
        *,
        timeout_seconds: float = 120.0,
        poll_seconds: float = 2.0,
    ) -> dict[str, Any]:
        validate_controller_mailbox(self.mailbox, self.branch, expected_policy=self.policy)
        return wait_for_result(
            self.mailbox,
            self.branch,
            task,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
            expected_provenance=self._expected_provenance,
        )

    def call(
        self,
        task: dict[str, Any],
        *,
        timeout_seconds: float = 120.0,
        poll_seconds: float = 2.0,
    ) -> dict[str, Any]:
        validate_controller_mailbox(self.mailbox, self.branch, expected_policy=self.policy)
        return call_task(
            self.mailbox,
            self.branch,
            task,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
            expected_provenance=self._expected_provenance,
        )


def render_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
