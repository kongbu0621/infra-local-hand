"""Profile loading and repository/path confinement for Local Hand."""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .protocol import LocalHandError
from .config import TransportPolicy, read_config, validate_profile_shape

_REPO_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
    *(f"COM{i}" for i in ("\u00b9", "\u00b2", "\u00b3")),
    *(f"LPT{i}" for i in ("\u00b9", "\u00b2", "\u00b3")),
}
_WINDOWS_FORBIDDEN = frozenset('<>:"|?*')


@dataclass(frozen=True)
class ValidationSpec:
    argv: tuple[str, ...]
    timeout_seconds: float
    replay_safe: bool


@dataclass(frozen=True)
class RepositorySpec:
    name: str
    relative_path: str
    validations: dict[str, ValidationSpec]
    single_writer: bool


@dataclass(frozen=True)
class NodeProfile:
    node_id: str
    projects_root: Path
    repositories: dict[str, RepositorySpec]
    profile_sha256: str
    transport_policy: TransportPolicy


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocalHandError("invalid_profile", f"{field} must be a non-empty string")
    return value.strip()


def _canonical_relative_posix(value: str, field: str, *, allow_root: bool = False) -> PurePosixPath:
    """Parse the transport path syntax, independent of the host OS.

    Local Hand v0.1 task/profile paths are POSIX-style relative paths. Rejecting
    backslashes, drive/ADS colons and Win32-normalized aliases prevents a string
    from acquiring different meaning when the same task is executed on Windows.
    """
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise LocalHandError("path_syntax_rejected", f"{field} contains an ASCII control character")
    if unicodedata.normalize("NFC", value) != value:
        raise LocalHandError(
            "path_unicode_normalization_rejected",
            f"{field} must already use NFC-normalized Unicode: {value}",
        )
    if "\\" in value:
        raise LocalHandError(
            "path_separator_rejected",
            f"{field} must use canonical '/' separators, not backslashes: {value}",
        )
    p = PurePosixPath(value)
    if p.is_absolute() or ".." in p.parts:
        raise LocalHandError("path_escape", f"{field} must be a confined relative POSIX path")
    if not p.parts:
        if allow_root and value == ".":
            return PurePosixPath(".")
        if allow_root:
            raise LocalHandError(
                "path_not_canonical",
                f"{field} must use '.' as the only repository-root spelling: {value}",
            )
        raise LocalHandError("invalid_path", f"{field} must not be empty/root")
    if str(p) != value:
        raise LocalHandError(
            "path_not_canonical",
            f"{field} is not in canonical POSIX form: {value}",
        )

    for part in p.parts:
        forbidden = sorted(set(part) & _WINDOWS_FORBIDDEN)
        if forbidden:
            raise LocalHandError(
                "windows_path_alias_rejected",
                f"{field} contains a character forbidden by the cross-platform path contract: {value}",
            )
        if part.endswith((" ", ".")):
            raise LocalHandError(
                "windows_path_alias_rejected",
                f"{field} contains a trailing space/dot component: {value}",
            )
        normalized = part.rstrip(" .")
        if normalized.casefold() == ".git":
            raise LocalHandError(
                "git_metadata_rejected",
                f"generic filesystem access to Git metadata is forbidden: {value}",
            )
        # Win32 also treats spaces immediately before the first extension as
        # part of the reserved-device alias (for example ``CON .txt``).
        device_base = normalized.split(".", 1)[0].rstrip(" ").upper()
        if device_base in _WINDOWS_RESERVED:
            raise LocalHandError(
                "windows_path_alias_rejected",
                f"{field} contains a reserved Windows device component: {value}",
            )
    return p


def _relative_posix(value: str, field: str) -> PurePosixPath:
    try:
        return _canonical_relative_posix(value, field)
    except LocalHandError as exc:
        raise LocalHandError("invalid_profile", f"{field} must be a canonical confined relative POSIX path") from exc


def _resolve_existing_prefix(path: Path) -> Path:
    """Resolve the longest existing prefix and preserve the requested suffix.

    This is used before bootstrap creates a repository.  Resolving only with
    ``strict=False`` can conceal an inaccessible component as though it were
    absent; walking to an existing prefix gives bootstrap a fail-closed native
    identity check without requiring the final repository to exist yet.
    """
    missing: list[str] = []
    cursor = path
    while True:
        try:
            cursor.lstat()
        except FileNotFoundError:
            parent = cursor.parent
            if parent == cursor:
                raise LocalHandError(
                    "path_identity_indeterminate",
                    f"cannot find an existing prefix for repository target: {path}",
                    "indeterminate",
                )
            missing.append(cursor.name)
            cursor = parent
            continue
        except OSError as exc:
            raise LocalHandError(
                "path_identity_indeterminate",
                f"cannot inspect repository target identity: {cursor}",
                "indeterminate",
            ) from exc
        try:
            resolved = cursor.resolve(strict=True)
        except OSError as exc:
            raise LocalHandError(
                "path_identity_indeterminate",
                f"cannot resolve repository target identity: {cursor}",
                "indeterminate",
            ) from exc
        return resolved.joinpath(*reversed(missing))


def repository_target(projects_root: Path, relative_path: str) -> Path:
    """Validate and resolve a prospective repository target without writing.

    The returned path has the native identity of every existing component.
    Exact part comparison rejects case/normalization aliases on filesystems
    where two different transport spellings would otherwise name one object.
    """
    if not isinstance(relative_path, str) or not relative_path:
        raise LocalHandError("invalid_path", "repository path must be a non-empty string")
    rel = _canonical_relative_posix(relative_path, "repository path")
    projects = _resolve_existing_prefix(Path(projects_root))
    resolved = _resolve_existing_prefix(projects.joinpath(*rel.parts))
    if not resolved.is_relative_to(projects):
        raise LocalHandError("path_escape", "repository target escapes projects_root")
    if resolved.relative_to(projects).parts != rel.parts:
        raise LocalHandError(
            "path_identity_mismatch",
            "repository path spelling does not match the native filesystem identity",
        )
    return resolved


def load_profile(path: Path) -> NodeProfile:
    raw_bytes, raw = read_config(path)
    policy = validate_profile_shape(raw)

    node_id = _nonempty_string(raw.get("node_id"), "node_id")
    projects_raw = _nonempty_string(raw.get("projects_root"), "projects_root")
    projects_root = Path(os.path.expanduser(os.path.expandvars(projects_raw))).resolve()

    repos_raw = raw.get("repositories")
    if not isinstance(repos_raw, dict) or not repos_raw:
        raise LocalHandError("invalid_profile", "repositories must be a non-empty object")

    repositories: dict[str, RepositorySpec] = {}
    for name, spec_raw in repos_raw.items():
        if not isinstance(name, str) or not _REPO_NAME.fullmatch(name):
            raise LocalHandError("invalid_profile", f"invalid repository name: {name!r}")
        if not isinstance(spec_raw, dict):
            raise LocalHandError("invalid_profile", f"repository {name} must be an object")
        rel = spec_raw.get("path")
        if not isinstance(rel, str) or not rel:
            raise LocalHandError("invalid_profile", f"repositories.{name}.path must be a non-empty string")
        _relative_posix(rel, f"repositories.{name}.path")
        single_writer = spec_raw.get("single_writer", False)
        if not isinstance(single_writer, bool):
            raise LocalHandError(
                "invalid_profile",
                f"repositories.{name}.single_writer must be boolean",
            )

        validations_raw = spec_raw.get("validations", {})
        if not isinstance(validations_raw, dict):
            raise LocalHandError("invalid_profile", f"repositories.{name}.validations must be an object")
        validations: dict[str, ValidationSpec] = {}
        for profile_id, vraw in validations_raw.items():
            if not isinstance(profile_id, str) or not _REPO_NAME.fullmatch(profile_id):
                raise LocalHandError("invalid_profile", f"invalid validation profile id: {profile_id!r}")
            if not isinstance(vraw, dict):
                raise LocalHandError("invalid_profile", f"validation {profile_id} must be an object")
            argv = vraw.get("argv")
            if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x for x in argv):
                raise LocalHandError("invalid_profile", f"validation {profile_id}.argv must be non-empty strings")
            timeout = vraw.get("timeout_seconds", 60)
            if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 3600:
                raise LocalHandError("invalid_profile", f"validation {profile_id}.timeout_seconds out of range")
            if "replay_safe" not in vraw or not isinstance(vraw["replay_safe"], bool):
                raise LocalHandError(
                    "invalid_profile",
                    f"validation {profile_id}.replay_safe must be explicitly declared boolean",
                )
            validations[profile_id] = ValidationSpec(tuple(argv), float(timeout), vraw["replay_safe"])

        repositories[name] = RepositorySpec(
            name=name,
            relative_path=rel,
            validations=validations,
            single_writer=single_writer,
        )

    return NodeProfile(
        node_id=node_id,
        projects_root=projects_root,
        repositories=repositories,
        profile_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        transport_policy=policy,
    )


def repository_root(profile: NodeProfile, repository: str) -> Path:
    if repository not in profile.repositories:
        raise LocalHandError("repository_not_allowlisted", f"repository not allowlisted: {repository}")
    projects = profile.projects_root.resolve(strict=True)
    candidate = repository_target(projects, profile.repositories[repository].relative_path)
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise LocalHandError("repository_missing", f"repository missing: {repository}") from exc
    if not resolved.is_relative_to(projects):
        raise LocalHandError("path_escape", f"repository escapes projects_root: {repository}")
    if not resolved.is_dir() or not (resolved / ".git").exists():
        raise LocalHandError("not_git_repository", f"not a Git working copy: {repository}")
    return resolved


def _reject_resolved_git_metadata(repo_root: Path, resolved: Path, relative_path: str) -> None:
    """Second boundary check after native-OS resolution.

    This catches host aliases that resolve to the actual .git object even if the
    lexical spelling was not literally '.git'. Worktree .git files are covered
    by equality; normal repository .git directories also cover descendants.
    """
    git_path = repo_root / ".git"
    try:
        resolved_git = git_path.resolve(strict=True)
    except (FileNotFoundError, OSError):
        return
    if resolved == resolved_git or (resolved_git.is_dir() and resolved.is_relative_to(resolved_git)):
        raise LocalHandError(
            "git_metadata_rejected",
            f"resolved path targets Git metadata: {relative_path}",
        )


def safe_existing_path(repo_root: Path, relative_path: str, *, expect: str | None = None) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise LocalHandError("invalid_path", "relative_path must be a non-empty string")
    p = _canonical_relative_posix(relative_path, "relative_path", allow_root=True)

    canonical_repo = repo_root.resolve(strict=True)
    raw = canonical_repo.joinpath(*p.parts)
    cursor = canonical_repo
    for part in p.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise LocalHandError("symlink_rejected", f"symlink path component rejected: {relative_path}")

    try:
        resolved = raw.resolve(strict=True)
    except FileNotFoundError as exc:
        raise LocalHandError("path_missing", f"path does not exist: {relative_path}") from exc
    if not resolved.is_relative_to(canonical_repo):
        raise LocalHandError("path_escape", f"path escapes repository: {relative_path}")
    if resolved.relative_to(canonical_repo).parts != p.parts:
        raise LocalHandError(
            "path_identity_mismatch",
            f"path spelling does not match the native filesystem identity: {relative_path}",
        )
    _reject_resolved_git_metadata(canonical_repo, resolved, relative_path)

    if expect == "file" and not resolved.is_file():
        raise LocalHandError("not_regular_file", f"not a regular file: {relative_path}")
    if expect == "directory" and not resolved.is_dir():
        raise LocalHandError("not_directory", f"not a directory: {relative_path}")
    return resolved
