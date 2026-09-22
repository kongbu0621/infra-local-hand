"""Read-only Local Hand actions."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .bounded_io import list_directory_bounded, read_regular_file_bounded
from .git_safety import assert_no_execution_filters, run_hardened_git, sanitized_git_env
from .paths import NodeProfile, repository_root, safe_existing_path
from .protocol import CAPABILITIES, LocalHandError, MAX_TEXT_BYTES, WORKER_VERSION

MAX_GIT_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_LIST_ENTRIES = 1000
GIT_TIMEOUT_SECONDS = 20.0


def _effective_os_identity() -> tuple[str, int | None]:
    """Read identity from the process token/effective UID, never user env."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            buffer = ctypes.create_unicode_buffer(257)
            size = wintypes.DWORD(len(buffer))
            if not ctypes.windll.advapi32.GetUserNameW(buffer, ctypes.byref(size)):
                raise ctypes.WinError()
            value = buffer.value.strip()
        except Exception as exc:
            raise LocalHandError(
                "runtime_identity_indeterminate",
                "cannot read effective Windows process-token user",
                "indeterminate",
            ) from exc
        if not value:
            raise LocalHandError(
                "runtime_identity_indeterminate",
                "effective Windows process-token user is empty",
                "indeterminate",
            )
        return value, None

    try:
        import pwd

        uid = os.geteuid()
        return pwd.getpwuid(uid).pw_name, uid
    except (KeyError, OSError) as exc:
        raise LocalHandError(
            "runtime_identity_indeterminate",
            "cannot map effective UID to an OS user",
            "indeterminate",
        ) from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_git(repo: Path, args: list[str]):
    env = sanitized_git_env()
    assert_no_execution_filters(repo, env)
    return run_hardened_git(
        repo,
        args,
        allow_ssh=False,
        timeout=GIT_TIMEOUT_SECONDS,
        max_stdout=MAX_GIT_OUTPUT_BYTES,
        max_stderr=MAX_GIT_OUTPUT_BYTES,
        text=False,
    )


def _decode_output(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _sanitize_remote_url(url: str) -> str:
    value = url.strip()
    if not value:
        return "<redacted-remote>"
    if re.match(r"^[A-Za-z0-9._+-]+::", value):
        return "<redacted-remote-helper>"
    if "://" in value:
        try:
            parsed = urlsplit(value)
            host = parsed.hostname
            if not parsed.scheme or host is None:
                return "<redacted-remote>"
            rendered_host = host
            if ":" in host and not host.startswith("["):
                rendered_host = f"[{host}]"
            try:
                port = parsed.port
            except ValueError:
                return "<redacted-remote>"
            netloc = rendered_host + (f":{port}" if port is not None else "")
            return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
        except Exception:
            return "<redacted-remote>"
    scp = re.match(r"^[^/@\s]+@([^:\s]+):(.*)$", value)
    if scp:
        tail = scp.group(2).split("?", 1)[0].split("#", 1)[0]
        return f"***@{scp.group(1)}:{tail}"
    if value.startswith(("/", "./", "../", "~/")) or re.match(r"^[A-Za-z]:[\\/]", value):
        return "<local-path-remote>"
    return "<redacted-remote>"


def _sanitize_remote_lines(data: bytes) -> list[str]:
    sanitized: list[str] = []
    for line in _decode_output(data).splitlines():
        parts = line.split()
        if len(parts) < 2:
            sanitized.append("<redacted-remote-line>")
            continue
        name = parts[0]
        direction = parts[-1] if parts[-1] in {"(fetch)", "(push)"} else ""
        url_parts = parts[1:-1] if direction else parts[1:]
        rendered = f"{name}\t{_sanitize_remote_url(' '.join(url_parts))}"
        if direction:
            rendered += f"\t{direction}"
        sanitized.append(rendered)
    return sanitized


def node_status(profile: NodeProfile) -> dict[str, Any]:
    import platform
    import sys
    effective_user, effective_uid = _effective_os_identity()
    install_instance_id = os.environ.get("LOCAL_HAND_INSTALL_INSTANCE_ID", "").strip() or None
    return {
        "node_id": profile.node_id,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "worker_version": WORKER_VERSION,
        "worker_pid": os.getpid(),
        "effective_os_user": effective_user,
        "effective_uid": effective_uid,
        "service_account": effective_user,
        "install_instance_id": install_instance_id,
        "capabilities": list(CAPABILITIES),
        "projects_root": str(profile.projects_root),
        "repositories": sorted(profile.repositories),
        "repository_write_policy": {
            name: "single-writer" if spec.single_writer else "read-only"
            for name, spec in sorted(profile.repositories.items())
        },
    }


def repo_audit(profile: NodeProfile, repository: str) -> dict[str, Any]:
    repo = repository_root(profile, repository)
    branch = _run_git(repo, ["branch", "--show-current"])
    head = _run_git(repo, ["rev-parse", "HEAD"])
    status = _run_git(repo, ["status", "--porcelain=v1", "-b", "--ignore-submodules=all"])
    remotes = _run_git(repo, ["remote", "-v"])
    for proc, what in ((branch, "branch"), (head, "head"), (status, "status"), (remotes, "remotes")):
        if proc.returncode != 0:
            raise LocalHandError("git_failed", f"git {what} failed: {_decode_output(proc.stderr).strip()}", "failed")
    dirty = _run_git(repo, ["status", "--porcelain=v1", "--ignore-submodules=all"])
    if dirty.returncode != 0:
        raise LocalHandError("git_failed", _decode_output(dirty.stderr).strip() or "git status failed", "failed")
    return {
        "repository": repository,
        "path": str(repo),
        "branch": _decode_output(branch.stdout).strip(),
        "head": _decode_output(head.stdout).strip(),
        "status": _decode_output(status.stdout).splitlines(),
        "dirty": bool(dirty.stdout),
        "remotes": _sanitize_remote_lines(remotes.stdout),
        "remotes_sanitized": True,
        "git_helpers_disabled": {
            "ambient_git_env": True,
            "system_global_config": True,
            "hooks": True,
            "fsmonitor": True,
            "submodule_recurse": True,
            "execution_filters": True,
            "bounded_output": True,
        },
    }


def fs_list(profile: NodeProfile, repository: str, relative_path: str = ".") -> dict[str, Any]:
    repo = repository_root(profile, repository)
    target = safe_existing_path(repo, relative_path, expect="directory")
    entries = list_directory_bounded(target, MAX_LIST_ENTRIES, "directory_too_large")
    result = []
    for entry in entries:
        try:
            if entry.is_symlink():
                kind = "symlink"
            elif entry.is_dir(follow_symlinks=False):
                kind = "directory"
            elif entry.is_file(follow_symlinks=False):
                kind = "file"
            else:
                kind = "other"
        except OSError as exc:
            raise LocalHandError(
                "directory_entry_unavailable",
                f"cannot inspect directory entry {entry.name}; errno={exc.errno}",
                "indeterminate",
            ) from exc
        result.append({"name": entry.name, "kind": kind})
    return {"repository": repository, "relative_path": relative_path, "entries": result}


def fs_read_text(profile: NodeProfile, repository: str, relative_path: str) -> dict[str, Any]:
    repo = repository_root(profile, repository)
    target = safe_existing_path(repo, relative_path, expect="file")
    try:
        data = read_regular_file_bounded(target, MAX_TEXT_BYTES, "read_too_large")
    except LocalHandError as exc:
        if exc.code == "read_too_large" and "symlink/reparse" not in exc.message and "non-regular" not in exc.message:
            raise
        if "exceeds" in exc.message:
            raise LocalHandError("read_too_large", f"file exceeds {MAX_TEXT_BYTES} bytes") from exc
        raise LocalHandError("not_regular_file", exc.message) from exc
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LocalHandError("not_utf8", f"file is not valid UTF-8: {relative_path}") from exc
    return {
        "repository": repository,
        "relative_path": relative_path,
        "sha256": _sha256_bytes(data),
        "bytes": len(data),
        "encoding": "utf-8",
        "content": content,
    }


def git_status(profile: NodeProfile, repository: str) -> dict[str, Any]:
    repo = repository_root(profile, repository)
    proc = _run_git(repo, ["status", "--porcelain=v1", "-b", "--ignore-submodules=all"])
    if proc.returncode != 0:
        raise LocalHandError("git_failed", _decode_output(proc.stderr).strip() or "git status failed", "failed")
    return {
        "repository": repository,
        "lines": _decode_output(proc.stdout).splitlines(),
        "ambient_git_env_scrubbed": True,
        "fsmonitor_disabled": True,
        "execution_filters_rejected": True,
        "bounded_output": True,
    }


def git_diff(profile: NodeProfile, repository: str) -> dict[str, Any]:
    repo = repository_root(profile, repository)
    proc = _run_git(repo, ["diff", "--no-ext-diff", "--no-textconv", "--ignore-submodules=all", "--"])
    if proc.returncode != 0:
        raise LocalHandError("git_failed", _decode_output(proc.stderr).strip() or "git diff failed", "failed")
    return {
        "repository": repository,
        "diff": _decode_output(proc.stdout),
        "bytes": len(proc.stdout),
        "ambient_git_env_scrubbed": True,
        "ext_diff_disabled": True,
        "textconv_disabled": True,
        "execution_filters_rejected": True,
        "bounded_output": True,
    }
