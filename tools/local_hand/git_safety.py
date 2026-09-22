"""Git execution boundary helpers for Local Hand."""
from __future__ import annotations

import hashlib
import os
import re
import shlex
import sys
import tempfile
import uuid
from pathlib import Path

from .bounded_io import run_process_bounded
from .protocol import LocalHandError

SAFE_ENV_KEYS = {
    "PATH", "HOME", "USER", "LOGNAME", "USERPROFILE", "SYSTEMROOT", "WINDIR",
    "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "PATHEXT", "COMSPEC",
}
WINDOWS_SAFE_ENV_KEYS = {"PROGRAMDATA"}
FILTER_CONFIG_RE = r"^filter\..*\.(clean|smudge|process)$"
GIT_CONFIG_OUTPUT_LIMIT = 256 * 1024


def _bound_executable(variable: str, fallback: str) -> str:
    value = os.environ.get(variable, "").strip()
    if not value:
        return fallback
    path = Path(value)
    if not path.is_absolute() or not path.is_file() or (os.name != "nt" and not os.access(path, os.X_OK)):
        raise LocalHandError(
            "runtime_binding_invalid",
            f"{variable} must name an existing absolute executable file",
            "indeterminate",
        )
    return str(path)


def _ssh_shell_path(value: str) -> str:
    """Render native Windows paths for Git for Windows' POSIX shell."""
    return value.replace("\\", "/") if os.name == "nt" else value


def validate_runtime_bindings() -> None:
    """Fail startup when a deployed runtime binding is absent or ambiguous."""
    for variable in ("LOCAL_HAND_GIT_EXECUTABLE", "LOCAL_HAND_SSH_EXECUTABLE"):
        if not os.environ.get(variable, "").strip():
            raise LocalHandError(
                "runtime_binding_invalid",
                f"{variable} is required for deployed worker startup",
                "indeterminate",
            )
        _bound_executable(variable, "")
    python = Path(sys.executable)
    if not python.is_absolute() or not python.is_file() or (os.name != "nt" and not os.access(python, os.X_OK)):
        raise LocalHandError(
            "runtime_binding_invalid",
            "the running Python interpreter must be an existing absolute executable file",
            "indeterminate",
        )
    install_instance = os.environ.get("LOCAL_HAND_INSTALL_INSTANCE_ID", "").strip()
    try:
        parsed = uuid.UUID(install_instance)
    except ValueError as exc:
        raise LocalHandError(
            "runtime_binding_invalid",
            "LOCAL_HAND_INSTALL_INSTANCE_ID must be a canonical UUID",
            "indeterminate",
        ) from exc
    if str(parsed) != install_instance:
        raise LocalHandError(
            "runtime_binding_invalid",
            "LOCAL_HAND_INSTALL_INSTANCE_ID must be a lowercase canonical UUID",
            "indeterminate",
        )
    implementation_commit = os.environ.get("LOCAL_HAND_IMPLEMENTATION_COMMIT", "").strip()
    if re.fullmatch(r"[0-9a-f]{40,64}", implementation_commit) is None:
        raise LocalHandError(
            "runtime_binding_invalid",
            "LOCAL_HAND_IMPLEMENTATION_COMMIT must be a lowercase 40-64 character hexadecimal commit",
            "indeterminate",
        )
    uses_ssh = os.environ.get("LOCAL_HAND_MAILBOX_USES_SSH", "").strip()
    if uses_ssh != "1":
        raise LocalHandError(
            "runtime_binding_invalid",
            "LOCAL_HAND_MAILBOX_USES_SSH must be 1 for the v0.1 writable mailbox",
            "indeterminate",
        )
    for variable in ("LOCAL_HAND_MAILBOX_SSH_KEY", "LOCAL_HAND_KNOWN_HOSTS"):
        path = Path(os.environ.get(variable, ""))
        if not path.is_absolute() or not path.is_file():
            raise LocalHandError(
                "runtime_binding_invalid",
                f"{variable} must name an existing absolute file for SSH mailbox startup",
                "indeterminate",
            )


def _ssh_command() -> str:
    key = _ssh_shell_path(os.environ.get("LOCAL_HAND_MAILBOX_SSH_KEY", "").strip())
    known_hosts = _ssh_shell_path(os.environ.get("LOCAL_HAND_KNOWN_HOSTS", "").strip())
    parts = [
        _ssh_shell_path(_bound_executable("LOCAL_HAND_SSH_EXECUTABLE", "ssh")),
        "-F", _ssh_shell_path(os.devnull),
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
        "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none",
        "-o", "PermitLocalCommand=no", "-o", "ClearAllForwardings=yes",
    ]
    if key:
        parts.extend(["-i", key])
    if known_hosts:
        parts.extend(["-o", f"UserKnownHostsFile={known_hosts}", "-o", "StrictHostKeyChecking=yes"])
    else:
        parts.extend(["-o", "StrictHostKeyChecking=accept-new"])
    return " ".join(shlex.quote(part) for part in parts)


def sanitized_git_env(*, allow_ssh: bool = False) -> dict[str, str]:
    allowed_upper = {item.upper() for item in SAFE_ENV_KEYS}
    if os.name == "nt":
        allowed_upper.update(WINDOWS_SAFE_ENV_KEYS)
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed_upper}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_PAGER"] = "cat"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    if allow_ssh:
        env["GIT_SSH_COMMAND"] = _ssh_command()
    return env


def disabled_hooks_dir(repo: Path) -> Path:
    if os.name != "nt":
        return Path(os.devnull)

    key = hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()[:24]
    root = Path(tempfile.gettempdir()) / "local-hand-disabled-hooks" / key
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise LocalHandError("git_hooks_boundary_dirty", f"Local Hand disabled-hooks directory is not empty: {root}", "indeterminate")
    return root


def _safe_directory_value(repo: Path) -> str:
    """Return one canonical repository path for command-scoped Git trust."""
    try:
        resolved = repo.resolve(strict=True)
    except OSError as exc:
        raise LocalHandError(
            "git_repository_invalid",
            f"cannot resolve Git repository directory: {repo}",
            "indeterminate",
        ) from exc
    if not resolved.is_dir():
        raise LocalHandError(
            "git_repository_invalid",
            f"Git repository path is not a directory: {resolved}",
            "indeterminate",
        )
    value = str(resolved)
    return value.replace("\\", "/") if os.name == "nt" else value


def hardened_git_prefix(repo: Path) -> list[str]:
    safe_directory = _safe_directory_value(repo)
    hooks = disabled_hooks_dir(repo)
    return [
        _bound_executable("LOCAL_HAND_GIT_EXECUTABLE", "git"), "--no-pager",
        # The bootstrap owns Windows checkouts as Administrators while the
        # worker runs as Local Service.  Trust only this already-confined
        # repository, in Git's protected command scope, for this invocation.
        "-c", f"safe.directory={safe_directory}",
        "-c", f"core.hooksPath={hooks}",
        "-c", "core.fsmonitor=false",
        # Automatic housekeeping may detach and rewrite object packs while
        # mailbox admission is measuring the same repository. Keep it out of
        # controlled operations; do not weaken quota checks on moving files.
        "-c", "maintenance.auto=false",
        "-c", "gc.auto=0",
        "-c", "submodule.recurse=false",
        "-c", "credential.helper=",
        # Never allow Git's ext:: remote-helper protocol to turn a repository
        # configuration/URL rewrite into local command execution.
        "-c", "protocol.ext.allow=never",
    ]


def run_hardened_git(
    repo: Path,
    args: list[str],
    *,
    allow_ssh: bool,
    timeout: float,
    max_stdout: int,
    max_stderr: int,
    text: bool,
    extra_env: dict[str, str] | None = None,
):
    env = sanitized_git_env(allow_ssh=allow_ssh)
    if extra_env:
        env.update(extra_env)
    command = [*hardened_git_prefix(repo), *args]
    return run_process_bounded(
        command, cwd=repo, env=env, timeout=timeout,
        max_stdout=max_stdout, max_stderr=max_stderr,
        code_prefix="git", text=text,
    )


def assert_no_execution_filters(repo: Path, env: dict[str, str] | None = None) -> None:
    effective_env = env or sanitized_git_env()
    command = [*hardened_git_prefix(repo), "config", "--get-regexp", FILTER_CONFIG_RE]
    proc = run_process_bounded(
        command, cwd=repo, env=effective_env, timeout=5.0,
        max_stdout=GIT_CONFIG_OUTPUT_LIMIT, max_stderr=GIT_CONFIG_OUTPUT_LIMIT,
        code_prefix="git_config", text=True,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        names = [line.split(None, 1)[0].strip() for line in proc.stdout.splitlines() if line.strip()]
        raise LocalHandError("git_filter_rejected", f"execution-capable Git filter configuration is forbidden: {', '.join(sorted(set(names))) or 'filter.*'}")
    if proc.returncode not in (0, 1):
        raise LocalHandError("git_config_failed", proc.stderr.strip() or "cannot inspect effective Git filter configuration", "failed")
