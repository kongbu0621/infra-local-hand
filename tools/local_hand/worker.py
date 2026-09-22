"""Cross-platform Local Hand v0.1 worker using the experimental Git mailbox transport."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from . import act, observe, validate
from .bounded_io import FileReadUnavailable, read_regular_file_bounded
from .git_safety import assert_no_execution_filters, run_hardened_git, sanitized_git_env, validate_runtime_bindings
from .mailbox_safety import (
    MAX_MAILBOX_CONTROL_BLOB_BYTES,
    admit_remote_tree,
    atomic_create_control_file,
    bounded_task_files,
    target_lexists,
    validate_checkout_control_dirs,
    validate_control_target,
)
from .paths import NodeProfile, load_profile
from .config import validate_branch
from .provenance import core_digest, implementation_commit
from .installation import verify_record
from .protocol import (
    CAPABILITIES, MAX_RESULT_JSON_BYTES, MAX_TASK_ID_DIGITS, MAX_TASK_JSON_BYTES,
    RESULT_SCHEMA, RESULT_STATUSES, TASK_SCHEMA, TASK_FIELDS, validate_result_contract,
    TASK_ID_RE, LocalHandError, canonical_json, conflict_filename, result_error, result_success, task_digest,
)
from .runtime_lock import worker_instance_lock

DIGEST_RE = re.compile(r"^[0-9a-fA-F]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40,64}$")
DEFAULT_GIT_TIMEOUT_SECONDS = 45.0
MAILBOX_PUSH_ATTEMPTS = 4
MAX_MAILBOX_GIT_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_RECEIPT_JSON_BYTES = MAX_RESULT_JSON_BYTES + 1024 * 1024
_PACKAGE_DIGEST_CACHE: str | None = None

_ACTION_PARAM_SCHEMAS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "node.status": (frozenset(), frozenset()),
    "repo.audit": (frozenset({"repository"}), frozenset()),
    "fs.list": (frozenset({"repository"}), frozenset({"relative_path"})),
    "fs.read_text": (frozenset({"repository", "relative_path"}), frozenset()),
    "fs.write_text_cas": (
        frozenset({"repository", "relative_path", "expected_sha256", "content"}),
        frozenset(),
    ),
    "git.status": (frozenset({"repository"}), frozenset()),
    "git.diff": (frozenset({"repository"}), frozenset()),
    "validation.run_profile": (frozenset({"repository", "profile"}), frozenset()),
}


def load_json_bounded(path: Path, max_bytes: int, code: str) -> Any:
    try:
        raw = read_regular_file_bounded(path, max_bytes, code)
        return json.loads(raw.decode("utf-8"))
    except FileReadUnavailable as exc:
        raise FileReadUnavailable("json_read_unavailable", exc.message, "indeterminate") from exc
    except LocalHandError as exc:
        raise LocalHandError(code, exc.message, "indeterminate") from exc
    except Exception as exc:
        raise LocalHandError(code, f"invalid UTF-8/JSON object: {path.name}", "indeterminate") from exc


def load_json(path: Path) -> Any:
    return load_json_bounded(path, MAX_RESULT_JSON_BYTES, "invalid_json")


def _fsync_parent(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _json_bytes(value: Any, max_bytes: int | None = None, code: str = "json_too_large") -> bytes:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if max_bytes is not None and len(data) > max_bytes:
        raise LocalHandError(code, f"serialized JSON exceeds {max_bytes} bytes", "failed")
    return data


def write_json_atomic(path: Path, value: Any, *, max_bytes: int | None = None, code: str = "json_too_large") -> None:
    data = _json_bytes(value, max_bytes, code)
    fd = -1
    temp: Path | None = None
    replaced = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.local-hand-", dir=str(path.parent))
        temp = Path(temp_name)
        view = memoryview(data)
        written = 0
        while written < len(view):
            count = os.write(fd, view[written:])
            if count <= 0:
                raise OSError("local state write made no progress")
            written += count
        os.fsync(fd)
        # A close error may still have released the descriptor. Relinquish
        # ownership before closing so cleanup cannot close a reused number.
        closing_fd, fd = fd, -1
        os.close(closing_fd)
        os.replace(temp, path)
        replaced = True
        _fsync_parent(path)
    except OSError as exc:
        raise LocalHandError(
            "local_state_durability_unconfirmed" if replaced else "local_state_write_failed",
            f"cannot confirm durable local state: {path.name}; errno={exc.errno}",
            "indeterminate",
        ) from exc
    finally:
        if fd >= 0:
            try: os.close(fd)
            except OSError: pass
        if temp is not None:
            try: temp.unlink()
            except OSError: pass


def _validate_task_envelope(task: Any) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise LocalHandError("invalid_task", "task must be an object")
    if task.get("schema_version") != TASK_SCHEMA:
        raise LocalHandError("unsupported_schema", "unsupported schema_version")
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or TASK_ID_RE.fullmatch(task_id) is None:
        raise LocalHandError("invalid_task_id", f"task_id must match LH[0-9]{{4,{MAX_TASK_ID_DIGITS}}}")
    target_node = task.get("target_node")
    if not isinstance(target_node, str) or not target_node:
        raise LocalHandError("target_node_required", "target_node required")
    return task


def _validate_task_contract(task: dict[str, Any]) -> None:
    action = task.get("action")
    if not isinstance(action, str) or not action:
        raise LocalHandError("action_not_allowlisted", "action must be a non-empty allowlisted string")
    if "params" not in task:
        raise LocalHandError("invalid_params", "params is required and must be an object")
    params = task["params"]
    if not isinstance(params, dict):
        raise LocalHandError("invalid_params", "params must be an object")
    _validate_action_params(action, params)
    if set(task) != TASK_FIELDS:
        raise LocalHandError("invalid_task", "Task v1 requires exactly schema_version, task_id, target_node, action and params")


def _validate_action_params(action: str, params: dict[str, Any]) -> None:
    schema = _ACTION_PARAM_SCHEMAS.get(action)
    if schema is None or action not in CAPABILITIES:
        raise LocalHandError("action_not_allowlisted", f"action not allowlisted: {action}")
    required, optional = schema
    supplied = set(params)
    missing = sorted(required - supplied)
    unknown = sorted(supplied - required - optional)
    if missing:
        raise LocalHandError("invalid_params", f"missing required params for {action}: {', '.join(missing)}")
    if unknown:
        raise LocalHandError("invalid_params", f"unknown params for {action}: {', '.join(unknown)}")
    for name in sorted(required | (optional & supplied)):
        value = params[name]
        if not isinstance(value, str):
            raise LocalHandError("invalid_params", f"{name} must be a string")
        if name != "content" and not value:
            raise LocalHandError("invalid_params", f"{name} must be a non-empty string")


def validate_task(task: Any) -> dict[str, Any]:
    task = _validate_task_envelope(task)
    _validate_task_contract(task)
    return task


def _validate_result_shape(value: Any) -> dict[str, Any]:
    validate_result_contract(value)
    if not isinstance(value, dict) or value.get("schema_version") != RESULT_SCHEMA:
        raise LocalHandError("result_invalid", "result schema/object invalid", "indeterminate")
    task_id, digest = value.get("task_id"), value.get("task_digest")
    if not isinstance(task_id, str) or TASK_ID_RE.fullmatch(task_id) is None:
        raise LocalHandError("result_invalid", "result task_id invalid", "indeterminate")
    if not isinstance(digest, str) or DIGEST_RE.fullmatch(digest) is None:
        raise LocalHandError("result_invalid", "result task_digest invalid", "indeterminate")
    if value.get("status") not in RESULT_STATUSES:
        raise LocalHandError("result_invalid", "result status invalid", "indeterminate")
    for field in ("action", "target_node", "node_id", "worker_version"):
        if not isinstance(value.get(field), str) or not value.get(field):
            raise LocalHandError("result_invalid", f"result {field} invalid", "indeterminate")
    if value["node_id"] != value["target_node"]:
        raise LocalHandError("result_invalid", "result node_id/target_node mismatch", "indeterminate")
    if not isinstance(value.get("implementation_commit"), str) or COMMIT_RE.fullmatch(value["implementation_commit"]) is None:
        raise LocalHandError("result_invalid", "result implementation_commit invalid", "indeterminate")
    for field in ("package_digest", "profile_digest"):
        if not isinstance(value.get(field), str) or DIGEST_RE.fullmatch(value[field]) is None:
            raise LocalHandError("result_invalid", f"result {field} invalid", "indeterminate")
    _json_bytes(value, MAX_RESULT_JSON_BYTES, "result_too_large")
    return value


def _bounded_execution_result(result: dict[str, Any]) -> dict[str, Any]:
    """Make a local execution outcome persistable without losing replay safety.

    Stream byte limits do not bound JSON size: control characters expand when
    encoded. Keep known failure states, but never turn a successful execution
    into an execution failure merely because its full Result cannot be sent.
    Ingress validation remains strict; malformed envelopes are not repaired.
    """
    try:
        return _validate_result_shape(result)
    except LocalHandError as exc:
        if exc.code != "result_too_large":
            raise
    original = _json_bytes(result)
    original_code = result["error_code"]
    summary = {
        "original_status": result["status"],
        "original_error_code": original_code[:128] if original_code is not None else None,
        "original_error_code_truncated": original_code is not None and len(original_code) > 128,
        "original_details_omitted": True,
        "original_result_json_bytes": len(original),
        "original_result_sha256": hashlib.sha256(original).hexdigest(),
        "result_limit_bytes": MAX_RESULT_JSON_BYTES,
    }
    reduced = {**result,
               "status": "indeterminate" if result["status"] == "succeeded" else result["status"],
               "error_code": "result_too_large",
               "error": "serialized Result exceeds the publication limit; original details omitted; do not replay execution",
               "details": summary}
    # Identity/provenance fields are never truncated to manufacture a valid
    # result. If even this envelope cannot fit, keep the existing failure path.
    return _validate_result_shape(reduced)


def validate_remote_result(
    value: Any,
    expected_task_id: str,
    expected_action: str | None = None,
    expected_target_node: str | None = None,
    expected_digest: str | None = None,
) -> dict[str, Any]:
    try:
        result = _validate_result_shape(value)
    except LocalHandError as exc:
        raise LocalHandError("remote_result_invalid", exc.message, "indeterminate") from exc
    if result["task_id"] != expected_task_id:
        raise LocalHandError("remote_result_invalid", "remote result task_id/path mismatch", "indeterminate")
    if expected_action is not None and result["action"] != expected_action:
        raise LocalHandError("remote_result_invalid", "remote result action/task mismatch", "indeterminate")
    if expected_target_node is not None and (result["target_node"] != expected_target_node or result["node_id"] != expected_target_node):
        raise LocalHandError("remote_result_invalid", "remote result node/target mismatch", "indeterminate")
    if expected_digest is not None and result["task_digest"].lower() != expected_digest.lower():
        raise LocalHandError("remote_result_invalid", "remote result digest/task mismatch", "indeterminate")
    return result


def _load_remote_result(path: Path, expected_task_id: str, expected_action: str | None = None, expected_target_node: str | None = None, expected_digest: str | None = None) -> dict[str, Any]:
    return validate_remote_result(load_json_bounded(path, MAX_RESULT_JSON_BYTES, "remote_result_invalid"), expected_task_id, expected_action, expected_target_node, expected_digest)


def _validate_local_outbox_result(value: Any, result_file: Path) -> dict[str, Any]:
    try:
        result = _validate_result_shape(value)
    except LocalHandError as exc:
        raise LocalHandError("local_outbox_invalid", exc.message, "indeterminate") from exc
    if _is_conflict_outbox(result_file):
        if result_file.name != conflict_filename(result["task_digest"]) or result["status"] == "succeeded":
            raise LocalHandError("local_outbox_invalid", "conflict filename/digest or status invalid", "indeterminate")
    elif result_file.stem != result["task_id"]:
        raise LocalHandError("local_outbox_invalid", "canonical outbox filename/task_id mismatch", "indeterminate")
    return result


def _package_digest() -> str:
    return core_digest()


def _implementation_commit() -> str:
    return implementation_commit()


def build_provenance(profile: NodeProfile) -> dict[str, str]:
    return {"implementation_commit": _implementation_commit(), "package_digest": _package_digest(), "profile_digest": profile.profile_sha256}


def execute_task(task: dict[str, Any], profile: NodeProfile, state_root: Path | None = None) -> dict[str, Any] | None:
    task = _validate_task_envelope(task)
    if task["target_node"] != profile.node_id:
        return None
    task = validate_task(task)
    action, params = task["action"], task["params"]
    provenance = build_provenance(profile)
    if action == "node.status":
        details = observe.node_status(profile)
        details["runtime_identity"] = dict(provenance)
    elif action == "repo.audit": details = observe.repo_audit(profile, params["repository"])
    elif action == "fs.list": details = observe.fs_list(profile, params["repository"], params.get("relative_path", "."))
    elif action == "fs.read_text": details = observe.fs_read_text(profile, params["repository"], params["relative_path"])
    elif action == "fs.write_text_cas":
        details = act.fs_write_text_cas(profile, params["repository"], params["relative_path"], params["expected_sha256"], params["content"], lease_root=(state_root / "write-leases") if state_root else None)
    elif action == "git.status": details = observe.git_status(profile, params["repository"])
    elif action == "git.diff": details = observe.git_diff(profile, params["repository"])
    elif action == "validation.run_profile": details = validate.run_profile(profile, params["repository"], params["profile"])
    else: raise LocalHandError("unreachable", "unreachable action", "failed")
    return _bounded_execution_result(result_success(task, profile.node_id, details, provenance))


def run_git(args: list[str], cwd: Path, *, check: bool = True, max_stdout: int = MAX_MAILBOX_GIT_OUTPUT_BYTES):
    timeout = float(os.environ.get("LOCAL_HAND_GIT_TIMEOUT_SECONDS", DEFAULT_GIT_TIMEOUT_SECONDS))
    env = sanitized_git_env(allow_ssh=True)
    assert_no_execution_filters(cwd, env)
    proc = run_hardened_git(cwd, args, allow_ssh=True, timeout=timeout, max_stdout=max_stdout, max_stderr=MAX_MAILBOX_GIT_OUTPUT_BYTES, text=True)
    if check and proc.returncode != 0:
        text = " | ".join(x.strip() for x in (proc.stdout, proc.stderr) if x.strip())
        raise LocalHandError("git_failed", f"git failed ({proc.returncode}): {' '.join(args)} :: {text}", "failed")
    return proc


def require_mailbox(mailbox: Path) -> None:
    if not mailbox.is_dir() or not (mailbox / ".git").is_dir():
        raise LocalHandError("mailbox_not_git", f"mailbox is not a Git working copy: {mailbox}", "failed")


def validate_worker_mailbox(mailbox: Path, branch: str, profile: NodeProfile) -> None:
    policy = profile.transport_policy
    if validate_branch(branch) != policy.branch:
        raise LocalHandError("mailbox_policy_mismatch", "branch differs from Node Profile")
    require_mailbox(mailbox)
    if (mailbox / ".git").is_symlink():
        raise LocalHandError("mailbox_policy_mismatch", "mailbox requires a dedicated real Git directory")
    top = run_git(["rev-parse", "--show-toplevel"], mailbox).stdout.strip()
    if Path(top).resolve() != mailbox.resolve():
        raise LocalHandError("mailbox_policy_mismatch", "mailbox must be an exact working-copy root")
    for args in (["remote", "get-url", "--all", "origin"], ["remote", "get-url", "--push", "--all", "origin"]):
        urls = run_git(args, mailbox).stdout.splitlines()
        if len(urls) != 1 or urls[0] not in policy.allowed_remote_urls:
            raise LocalHandError("mailbox_policy_mismatch", "mailbox remote differs from admitted policy")


def _git_state_path(mailbox: Path, name: str) -> Path:
    raw = run_git(["rev-parse", "--git-path", name], mailbox).stdout.strip(); p = Path(raw)
    return p if p.is_absolute() else mailbox / p


def _preserve_untracked_control_files(mailbox: Path) -> None:
    """Keep abandoned local files out of the committed mailbox snapshot.

    reset --hard does not remove untracked files. Preserve them privately before
    reset so neither controller nor worker can mistake them for remote evidence.
    Ignore rules are deliberately not applied to this listing.
    """
    listing = run_git(["ls-files", "--others", "-z", "--",
                       "_executor_spike/tasks", "_executor_spike/results",
                       "_executor_spike/conflicts"], mailbox).stdout
    for relative in filter(None, listing.split("\0")):
        target = mailbox / relative
        validate_control_target(mailbox, target, require_existing=True)
        raw = read_regular_file_bounded(target, MAX_MAILBOX_CONTROL_BLOB_BYTES, "mailbox_untracked_invalid")
        digest = hashlib.sha256(raw).hexdigest()
        archive_root = mailbox / ".git" / "local-hand-untracked"
        try:
            for directory in (mailbox / ".git", archive_root):
                if directory == archive_root and not target_lexists(directory):
                    directory.mkdir(mode=0o700)
                st = directory.lstat()
                reparse = getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode) or reparse:
                    raise LocalHandError("mailbox_untracked_preservation_failed", "archive directory is not a real directory", "indeterminate")
            _fsync_parent(archive_root)
            archive = Path(tempfile.mkdtemp(prefix="record-", dir=archive_root))
            _fsync_parent(archive)
            write_json_atomic(archive / "record.json", {
                "relative_path": relative, "bytes": len(raw), "sha256": digest,
                "reason": "untracked control file is not committed mailbox evidence",
            })
            payload = archive / "payload"
            os.rename(target, payload)
            if read_regular_file_bounded(payload, MAX_MAILBOX_CONTROL_BLOB_BYTES, "mailbox_untracked_invalid") != raw:
                raise LocalHandError("mailbox_untracked_preservation_failed", "preserved file changed during move", "indeterminate")
            with payload.open("rb") as stream:
                os.fsync(stream.fileno())
            _fsync_parent(payload)
            _fsync_parent(target)
        except OSError as exc:
            raise LocalHandError("mailbox_untracked_preservation_failed", f"cannot preserve untracked control file: {relative}", "indeterminate") from exc


def recover_mailbox_git_state(mailbox: Path) -> None:
    require_mailbox(mailbox); validate_checkout_control_dirs(mailbox)
    _preserve_untracked_control_files(mailbox)
    for command in (["rebase", "--abort"], ["merge", "--abort"], ["cherry-pick", "--abort"], ["revert", "--abort"]):
        run_git(command, mailbox, check=False)
    for state_dir in ("rebase-merge", "rebase-apply"):
        p = _git_state_path(mailbox, state_dir)
        if p.exists(): shutil.rmtree(p)
    for state_file in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        p = _git_state_path(mailbox, state_file)
        if p.exists(): p.unlink()
    run_git(["reset", "--hard", "HEAD"], mailbox); validate_checkout_control_dirs(mailbox)


def sync_mailbox(mailbox: Path, branch: str) -> None:
    branch = validate_branch(branch)
    recover_mailbox_git_state(mailbox)
    # Configured tracking refs may be absent or stale. Fetch the admitted
    # branch explicitly, then bind admission and checkout to this one commit.
    # A same-named tag must never substitute for a missing branch.
    run_git(["fetch", "--depth=1", "--no-tags", "--refmap=", f"--filter=blob:limit={MAX_MAILBOX_CONTROL_BLOB_BYTES}", "origin", f"refs/heads/{branch}"], mailbox)
    fetched_commit = run_git(["rev-parse", "--verify", "FETCH_HEAD^{commit}"], mailbox).stdout.strip()
    if re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", fetched_commit) is None:
        raise LocalHandError("mailbox_fetch_invalid", "fetched mailbox commit identity is invalid", "indeterminate")
    admit_remote_tree(mailbox, fetched_commit)
    run_git(["reset", "--hard", fetched_commit], mailbox)
    validate_checkout_control_dirs(mailbox)
    # Only committed files may qualify as mailbox evidence. Recheck after
    # reset as well: a leftover local file must not acknowledge publication
    # or become executable work merely because reset returned success.
    _preserve_untracked_control_files(mailbox)


def _is_push_race(proc) -> bool:
    text = f"{proc.stdout}\n{proc.stderr}".lower()
    return any(token in text for token in ("non-fast-forward", "fetch first", "[rejected]"))


def _conflict_filename(task_id: str, digest: str, observed_digest: str | None = None) -> str:
    if TASK_ID_RE.fullmatch(task_id) is None or DIGEST_RE.fullmatch(digest) is None:
        raise LocalHandError("conflict_identity_invalid", "unsafe conflict identity", "indeterminate")
    # The task digest binds the complete canonical task, including task_id.
    # Full identities and both digests remain inside the conflict payload.
    return conflict_filename(digest)


def _is_conflict_outbox(path: Path) -> bool:
    return path.name.startswith("CONFLICT-")


def _route_outbox_target(mailbox: Path, result_file: Path) -> Path:
    return mailbox / "_executor_spike" / ("conflicts" if _is_conflict_outbox(result_file) else "results") / result_file.name


def _quarantine_local_outbox_file(outbox: Path, result_file: Path, reason: str) -> None:
    q = outbox.parent / "quarantine"; q.mkdir(parents=True, exist_ok=True)
    stem = f"{result_file.name}.{hashlib.sha256(reason.encode()).hexdigest()[:12]}"
    dest = q / f"{stem}.invalid"
    index = 1
    while target_lexists(dest):
        dest = q / f"{stem}.{index}.invalid"
        index += 1
    try: os.replace(result_file, dest); _fsync_parent(dest)
    except OSError as exc: raise LocalHandError("local_outbox_quarantine_failed", f"cannot quarantine {result_file.name}", "indeterminate") from exc


def _result_digest(result: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()


def _quarantine_local_result_conflict(outbox: Path, result_file: Path, local: dict[str, Any], remote: dict[str, Any]) -> None:
    q = outbox.parent / "quarantine"; q.mkdir(parents=True, exist_ok=True)
    stem = f"{result_file.name}.{_result_digest(local)}.{_result_digest(remote)}"
    dest = q / f"{stem}.conflict"
    index = 1
    while target_lexists(dest):
        dest = q / f"{stem}.{index}.conflict"
        index += 1
    try: os.replace(result_file, dest); _fsync_parent(dest)
    except OSError as exc: raise LocalHandError("local_outbox_quarantine_failed", f"cannot quarantine {result_file.name}", "indeterminate") from exc


def _publish_conflict_from_collision(outbox: Path, local: dict[str, Any], remote: dict[str, Any]) -> None:
    digest_collision = remote["task_digest"] != local["task_digest"]
    code = "remote_result_digest_conflict" if digest_collision else "remote_result_content_conflict"
    label = "digest" if digest_collision else "content"
    conflict = dict(local)
    conflict.update({"status":"indeterminate","error_code":code,"error":f"remote result {label} conflict for {local['task_id']}","details":{"local_task_digest":local.get("task_digest"),"remote_task_digest":remote.get("task_digest"),"local_result_sha256":_result_digest(local),"remote_result_sha256":_result_digest(remote),"local_result_status":local.get("status"),"remote_result_status":remote.get("status")}})
    _validate_result_shape(conflict)
    write_json_atomic(outbox / _conflict_filename(local["task_id"], local["task_digest"], str(remote.get("task_digest") or "")), conflict, max_bytes=MAX_RESULT_JSON_BYTES, code="result_too_large")


def _publish_conflict_from_invalid_remote(outbox: Path, local: dict[str, Any], exc: LocalHandError) -> None:
    conflict = dict(local)
    conflict.update({"status":"indeterminate","error_code":"remote_result_invalid","error":f"canonical remote result is malformed/invalid for {local['task_id']}","details":{"local_task_digest":local.get("task_digest"),"remote_validation_error":exc.message,"canonical_result_preserved":True}})
    _validate_result_shape(conflict)
    write_json_atomic(outbox / _conflict_filename(local["task_id"], local["task_digest"], None), conflict, max_bytes=MAX_RESULT_JSON_BYTES, code="result_too_large")


def publish_outbox(mailbox: Path, branch: str, outbox: Path) -> None:
    # Path.glob can suppress directory I/O errors and make an unreadable
    # queue appear empty. Publication/recovery must stop on that uncertainty.
    try:
        pending = sorted(path for path in outbox.iterdir() if path.match("*.json"))
    except OSError as exc:
        raise LocalHandError("local_outbox_unreadable", "cannot enumerate pending local results", "indeterminate") from exc
    for result_file in pending:
        try: local = _validate_local_outbox_result(load_json_bounded(result_file, MAX_RESULT_JSON_BYTES, "local_outbox_invalid"), result_file)
        except FileReadUnavailable: raise
        except LocalHandError as exc: _quarantine_local_outbox_file(outbox, result_file, exc.message); continue
        for attempt in range(1, MAILBOX_PUSH_ATTEMPTS + 1):
            sync_mailbox(mailbox, branch); target = _route_outbox_target(mailbox, result_file); validate_control_target(mailbox, target)
            if target_lexists(target):
                if _is_conflict_outbox(result_file):
                    local_bytes = read_regular_file_bounded(result_file, MAX_RESULT_JSON_BYTES, "local_outbox_invalid")
                    remote_bytes = read_regular_file_bounded(target, MAX_RESULT_JSON_BYTES, "remote_result_invalid")
                    if local_bytes == remote_bytes: result_file.unlink()
                    else: _quarantine_local_outbox_file(outbox, result_file, "remote conflict record differs")
                    break
                try: remote = _load_remote_result(target, result_file.stem, local.get("action"), local.get("target_node"))
                except FileReadUnavailable: raise
                except LocalHandError as exc:
                    _publish_conflict_from_invalid_remote(outbox, local, exc)
                    _quarantine_local_outbox_file(outbox, result_file, "canonical remote result is invalid")
                    break
                if remote["task_digest"] != local["task_digest"] or _result_digest(remote) != _result_digest(local):
                    _publish_conflict_from_collision(outbox, local, remote)
                    _quarantine_local_result_conflict(outbox, result_file, local, remote)
                else: result_file.unlink()
                break
            data = read_regular_file_bounded(result_file, MAX_RESULT_JSON_BYTES, "local_outbox_invalid")
            atomic_create_control_file(mailbox, target, data)
            rel = target.relative_to(mailbox).as_posix()
            run_git(["add", "--", rel], mailbox)
            run_git(["-c","user.name=local-hand","-c","user.email=local-hand@local.invalid","-c","commit.gpgsign=false","commit","-m",f"local-hand-result-{result_file.stem}"], mailbox)
            try:
                push = run_git(["push","origin",f"HEAD:refs/heads/{branch}"], mailbox, check=False)
            except LocalHandError as exc:
                # The remote may have accepted the commit before a timeout or
                # capture failure. Keep the outbox for reconciliation.
                raise LocalHandError("mailbox_publish_failed",
                                     f"result delivery unconfirmed: {exc.code}: {exc.message}",
                                     "indeterminate") from exc
            if push.returncode == 0: result_file.unlink(); break
            if not _is_push_race(push) or attempt == MAILBOX_PUSH_ATTEMPTS:
                raise LocalHandError("mailbox_publish_failed", f"mailbox push failed ({push.returncode}) attempt={attempt}; delivery unconfirmed", "indeterminate")


def _trusted_local_identity(task_file: Path, task: Any, profile: NodeProfile) -> bool:
    return isinstance(task, dict) and task.get("target_node") == profile.node_id and isinstance(task.get("task_id"), str) and TASK_ID_RE.fullmatch(task["task_id"]) is not None and task["task_id"] == task_file.stem


def _conflict_marker_path(state_root: Path, task_id: str, digest: str, observed_digest: str | None = None) -> Path:
    return state_root / "conflicts" / _conflict_filename(task_id, digest, observed_digest)


def _has_conflict_marker(state_root: Path, task_id: str, digest: str) -> bool:
    return target_lexists(state_root / "conflicts" / _conflict_filename(task_id, digest))


def _load_task_conflict(path: Path, task: dict[str, Any], profile: NodeProfile, code: str) -> dict[str, Any]:
    try:
        result = validate_remote_result(
            load_json_bounded(path, MAX_RESULT_JSON_BYTES, code),
            task["task_id"], str(task.get("action", "")), profile.node_id, task_digest(task),
        )
        if result["status"] == "succeeded":
            raise LocalHandError(code, "conflict record cannot report success", "indeterminate")
        return result
    except FileReadUnavailable:
        raise
    except LocalHandError as exc:
        raise LocalHandError(code, exc.message, "indeterminate") from exc


def _recover_task_conflict(mailbox: Path, branch: str, state_root: Path, outbox: Path,
                           task: dict[str, Any], profile: NodeProfile) -> None:
    """Requeue a durable marker after interruption between marker and outbox."""
    digest = task_digest(task)
    name = _conflict_filename(task["task_id"], digest)
    saved = _load_task_conflict(state_root / "conflicts" / name, task, profile, "local_conflict_invalid")
    target = mailbox / "_executor_spike" / "conflicts" / name
    validate_control_target(mailbox, target)
    if target_lexists(target):
        remote = _load_task_conflict(target, task, profile, "remote_conflict_invalid")
        if _result_digest(remote) != _result_digest(saved):
            raise LocalHandError("remote_conflict_content_conflict", "remote conflict differs from durable marker", "indeterminate")
        return
    pending = outbox / name
    if target_lexists(pending):
        existing = _validate_local_outbox_result(
            load_json_bounded(pending, MAX_RESULT_JSON_BYTES, "local_outbox_invalid"), pending,
        )
        if _result_digest(existing) != _result_digest(saved):
            raise LocalHandError("local_conflict_invalid", "pending conflict differs from durable marker", "indeterminate")
    else:
        write_json_atomic(pending, saved, max_bytes=MAX_RESULT_JSON_BYTES, code="result_too_large")
    publish_outbox(mailbox, branch, outbox)


def _quarantine_task_conflict(*, state_root: Path, outbox: Path, task: dict[str, Any], profile: NodeProfile, code: str, message: str, observed_digest: str | None, status: str = "rejected", extra_details: dict[str, Any] | None = None) -> None:
    digest = task_digest(task); marker = _conflict_marker_path(state_root, task["task_id"], digest, observed_digest)
    if marker.exists(): return
    result = result_error(task, profile.node_id, LocalHandError(code, message, status), build_provenance(profile))
    result["details"] = {"incoming_task_digest":digest,"observed_task_digest":observed_digest,"quarantined":True,**(extra_details or {})}
    _validate_result_shape(result)
    write_json_atomic(marker, result, max_bytes=MAX_RESULT_JSON_BYTES, code="result_too_large")
    write_json_atomic(outbox / _conflict_filename(task["task_id"], digest, observed_digest), result, max_bytes=MAX_RESULT_JSON_BYTES, code="result_too_large")


def _persist_result(*, outbox: Path, receipts: Path, task: dict[str, Any], result: dict[str, Any]) -> None:
    digest = task_digest(task); result = _bounded_execution_result(result)
    write_json_atomic(outbox / f"{task['task_id']}.json", result, max_bytes=MAX_RESULT_JSON_BYTES, code="result_too_large")
    write_json_atomic(receipts / f"{task['task_id']}.json", {"task_id":task["task_id"],"task_digest":digest,"status":result["status"],"result":result}, max_bytes=MAX_RECEIPT_JSON_BYTES, code="receipt_too_large")


def _load_remote_or_quarantine(*, remote_result: Path, task: dict[str, Any], profile: NodeProfile, state_root: Path, outbox: Path) -> dict[str, Any] | None:
    digest = task_digest(task)
    try:
        existing = _load_remote_result(remote_result, task["task_id"], str(task.get("action","")), profile.node_id)
    except FileReadUnavailable:
        raise
    except LocalHandError as exc:
        _quarantine_task_conflict(state_root=state_root,outbox=outbox,task=task,profile=profile,code="remote_result_invalid",message="canonical remote result is malformed/invalid",observed_digest=None,status="indeterminate",extra_details={"remote_validation_error":exc.message,"canonical_result_preserved":True}); return None
    if existing["task_digest"] != digest:
        _quarantine_task_conflict(state_root=state_root,outbox=outbox,task=task,profile=profile,code="remote_task_id_digest_conflict",message="remote task_id digest conflict",observed_digest=existing["task_digest"],status="rejected"); return None
    return existing


def _validate_receipt(receipt: Any, task: dict[str, Any], profile: NodeProfile) -> dict[str, Any]:
    digest = task_digest(task)
    if not isinstance(receipt, dict) or receipt.get("task_id") != task["task_id"] or receipt.get("task_digest") != digest:
        raise LocalHandError("local_receipt_invalid", "durable local receipt identity/digest invalid", "indeterminate")
    saved = receipt.get("result")
    if saved is not None: validate_remote_result(saved, task["task_id"], str(task.get("action","")), profile.node_id, digest)
    return receipt


def process_once(mailbox: Path, branch: str, profile: NodeProfile, state_root: Path) -> None:
    validate_worker_mailbox(mailbox, branch, profile)
    outbox, receipts, conflicts = state_root/"outbox", state_root/"receipts", state_root/"conflicts"
    for p in (outbox,receipts,conflicts): p.mkdir(parents=True, exist_ok=True)
    publish_outbox(mailbox, branch, outbox); sync_mailbox(mailbox, branch)
    for task_file in bounded_task_files(mailbox):
        try: task = load_json_bounded(task_file, MAX_TASK_JSON_BYTES, "task_file_invalid")
        except FileReadUnavailable: raise
        except LocalHandError: continue
        if not _trusted_local_identity(task_file, task, profile): continue
        digest = task_digest(task)
        if _has_conflict_marker(state_root, task["task_id"], digest):
            _recover_task_conflict(mailbox, branch, state_root, outbox, task, profile)
            continue
        conflict_name = _conflict_filename(task["task_id"], digest)
        remote_conflict = mailbox / "_executor_spike" / "conflicts" / conflict_name
        validate_control_target(mailbox, remote_conflict)
        if target_lexists(remote_conflict):
            # Remote uncertainty is a replay barrier even with fresh local
            # state. Persist it before accepting any later mailbox snapshot.
            existing_conflict = _load_task_conflict(remote_conflict, task, profile, "remote_conflict_invalid")
            write_json_atomic(conflicts / conflict_name, existing_conflict,
                              max_bytes=MAX_RESULT_JSON_BYTES, code="result_too_large")
            continue
        receipt_file = receipts/f"{task['task_id']}.json"; remote_result = mailbox/"_executor_spike"/"results"/f"{task['task_id']}.json"
        if target_lexists(receipt_file):
            try: receipt = _validate_receipt(load_json_bounded(receipt_file, MAX_RECEIPT_JSON_BYTES, "local_receipt_invalid"), task, profile)
            except FileReadUnavailable: raise
            except LocalHandError as exc:
                _quarantine_task_conflict(state_root=state_root,outbox=outbox,task=task,profile=profile,code="local_receipt_invalid",message="durable local receipt is malformed/invalid",observed_digest=None,status="indeterminate",extra_details={"receipt_validation_error":exc.message}); publish_outbox(mailbox,branch,outbox); continue
            if target_lexists(remote_result):
                existing = _load_remote_or_quarantine(remote_result=remote_result,task=task,profile=profile,state_root=state_root,outbox=outbox)
                if existing is None:
                    publish_outbox(mailbox,branch,outbox)
                elif receipt.get("result") is None:
                    # A crash can leave only the pre-execution intent while the
                    # canonical result was published. Complete the local audit
                    # record from that already digest-bound remote result.
                    write_json_atomic(receipt_file,{"task_id":task["task_id"],"task_digest":digest,
                                      "source":"remote_result_recovery","result":existing},
                                      max_bytes=MAX_RECEIPT_JSON_BYTES,code="receipt_too_large")
                elif _result_digest(receipt["result"]) != _result_digest(existing):
                    _quarantine_task_conflict(state_root=state_root,outbox=outbox,task=task,profile=profile,
                                              code="remote_result_content_conflict",
                                              message="remote result content differs from durable local receipt",
                                              observed_digest=existing["task_digest"],status="indeterminate",
                                              extra_details={"local_result_sha256":_result_digest(receipt["result"]),
                                                             "remote_result_sha256":_result_digest(existing),
                                                             "canonical_result_preserved":True})
                    publish_outbox(mailbox,branch,outbox)
                continue
            saved = receipt.get("result")
            if isinstance(saved, dict):
                write_json_atomic(outbox/f"{task['task_id']}.json", saved, max_bytes=MAX_RESULT_JSON_BYTES, code="result_too_large"); publish_outbox(mailbox,branch,outbox); continue
            unknown = result_error(task, profile.node_id, LocalHandError("outcome_unknown","receipt exists but result payload is unavailable; refusing replay","indeterminate"), build_provenance(profile))
            _persist_result(outbox=outbox,receipts=receipts,task=task,result=unknown); publish_outbox(mailbox,branch,outbox); continue
        if target_lexists(remote_result):
            existing = _load_remote_or_quarantine(remote_result=remote_result,task=task,profile=profile,state_root=state_root,outbox=outbox)
            if existing is not None:
                write_json_atomic(receipt_file,{"task_id":task["task_id"],"task_digest":digest,"source":"remote_result","result":existing},max_bytes=MAX_RECEIPT_JSON_BYTES,code="receipt_too_large")
            else: publish_outbox(mailbox,branch,outbox)
            continue
        try: validate_task(task)
        except Exception as exc:
            result = result_error(task,profile.node_id,exc,build_provenance(profile)); _persist_result(outbox=outbox,receipts=receipts,task=task,result=result); publish_outbox(mailbox,branch,outbox); continue
        # Persist intent before any handler can produce a side effect. A crash
        # after this point is uncertain, so recovery must not execute it again.
        write_json_atomic(receipt_file, {"task_id": task["task_id"], "task_digest": digest,
                          "source": "local_execution_started"},
                          max_bytes=MAX_RECEIPT_JSON_BYTES, code="receipt_too_large")
        try:
            result = execute_task(task,profile,state_root)
            if result is None: continue
        except Exception as exc: result = result_error(task,profile.node_id,exc,build_provenance(profile))
        _persist_result(outbox=outbox,receipts=receipts,task=task,result=result); publish_outbox(mailbox,branch,outbox)


def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="Local Hand worker")
    p.add_argument("--profile",type=Path,required=True)
    p.add_argument("--mailbox-repo",type=Path,required=True)
    p.add_argument("--mailbox-branch",help="must match the explicit Node Profile policy")
    p.add_argument("--state-root",type=Path,required=True)
    p.add_argument("--poll-seconds",type=float,default=5.0)
    p.add_argument("--once",action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args=build_parser().parse_args(argv)
    try:
        import math
        profile=load_profile(args.profile); mailbox=args.mailbox_repo.resolve(); state_root=args.state_root.resolve()
        branch=profile.transport_policy.branch if args.mailbox_branch is None else args.mailbox_branch
        if not math.isfinite(args.poll_seconds) or args.poll_seconds <= 0:
            raise LocalHandError("invalid_poll_interval", "poll interval must be finite and positive")
        if branch != profile.transport_policy.branch:
            raise LocalHandError("mailbox_policy_mismatch", "branch differs from Node Profile")
        validate_runtime_bindings()
        verify_record(profile, args.profile, state_root=state_root, mailbox_root=mailbox)
        validate_worker_mailbox(mailbox, branch, profile)
        with worker_instance_lock(state_root):
            if args.once: process_once(mailbox,branch,profile,state_root); return 0
            while True:
                try: process_once(mailbox,branch,profile,state_root)
                except Exception as exc: print(f"local-hand poll error: {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
                time.sleep(max(args.poll_seconds,1.0))
    except LocalHandError as exc:
        print(f"local-hand startup rejected: {exc.code}: {exc.message}",file=sys.stderr,flush=True)
        return 3 if exc.status == "indeterminate" or exc.code == "worker_instance_busy" else 2


if __name__ == "__main__": raise SystemExit(main())
