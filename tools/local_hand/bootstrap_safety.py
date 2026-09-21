"""Fail-closed bootstrap ownership and root-boundary helpers.

The platform bootstrap scripts call this module before changing ACLs, ownership,
or an existing service definition.  Keeping the semantic checks here gives the
Linux and Windows adapters one executable contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import uuid
from pathlib import Path
from typing import Iterable

from .paths import repository_target
from .protocol import LocalHandError

ROOT_MARKER_NAME = ".local-hand-root-owner.json"
ROOT_MARKER_SCHEMA = "local-hand-root-owner/v1"
SERVICE_OWNER_SCHEMA = "local-hand-service-owner/v1"


def new_install_instance_id() -> str:
    """Return a non-reusable identity for one bootstrap/switch attempt."""
    return str(uuid.uuid4())


def _absolute(path: str | os.PathLike[str]) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.path.expandvars(os.fspath(path)))))


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _is_reparse(st: os.stat_result) -> bool:
    attrs = getattr(st, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & reparse)


def assert_no_link_or_reparse_chain(path: str | os.PathLike[str]) -> Path:
    """Reject any existing symlink/reparse component without resolving through it."""
    target = _absolute(path)
    anchor = Path(target.anchor)
    cursor = anchor
    parts = target.parts[1:] if target.anchor else target.parts
    for part in parts:
        cursor = cursor / part
        try:
            st = cursor.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise LocalHandError(
                "bootstrap_root_indeterminate",
                f"cannot inspect bootstrap path component: {cursor}",
                "indeterminate",
            ) from exc
        if stat.S_ISLNK(st.st_mode) or _is_reparse(st):
            raise LocalHandError(
                "bootstrap_root_reparse_rejected",
                f"symlink/reparse bootstrap path component rejected: {cursor}",
            )
        if not stat.S_ISDIR(st.st_mode):
            raise LocalHandError(
                "bootstrap_root_invalid",
                f"bootstrap path component is not a directory: {cursor}",
            )
    return target


def _default_reserved_roots() -> tuple[Path, ...]:
    values: list[str] = []
    if os.name == "nt":
        for name in ("SystemRoot", "ProgramData", "ProgramFiles", "ProgramFiles(x86)", "USERPROFILE", "TEMP", "TMP"):
            value = os.environ.get(name)
            if value:
                values.append(value)
    else:
        values.extend(("/", "/home", "/root", "/etc", "/usr", "/var", "/opt", "/srv", "/tmp"))
    return tuple(_absolute(value) for value in values)


def validate_install_roots(
    state_root: str | os.PathLike[str],
    projects_root: str | os.PathLike[str],
    *,
    reserved_roots: Iterable[str | os.PathLike[str]] = (),
) -> tuple[Path, Path]:
    state = assert_no_link_or_reparse_chain(state_root)
    projects = assert_no_link_or_reparse_chain(projects_root)
    state_key = _path_key(state)
    anchor_key = _path_key(Path(state.anchor))
    reserved = {_path_key(path) for path in _default_reserved_roots()}
    reserved.update(_path_key(_absolute(path)) for path in reserved_roots)
    if state_key == anchor_key or state_key in reserved:
        raise LocalHandError(
            "bootstrap_state_root_rejected",
            f"StateRoot must not be a filesystem or reserved broad root: {state}",
        )
    try:
        common = Path(os.path.commonpath((str(state), str(projects))))
    except ValueError as exc:
        raise LocalHandError(
            "bootstrap_projects_root_rejected",
            "ProjectsRoot must be a strict descendant of StateRoot",
        ) from exc
    if _path_key(projects) == state_key or _path_key(common) != state_key:
        raise LocalHandError(
            "bootstrap_projects_root_rejected",
            "ProjectsRoot must be a strict descendant of StateRoot",
        )
    for label, path in (("StateRoot", state), ("ProjectsRoot", projects)):
        try:
            st = path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise LocalHandError(
                "bootstrap_root_indeterminate",
                f"cannot inspect existing {label}: {path}",
                "indeterminate",
            ) from exc
        if not stat.S_ISDIR(st.st_mode) or _is_reparse(st):
            raise LocalHandError("bootstrap_root_invalid", f"existing {label} is not a real directory: {path}")
    return state, projects


def _marker_bytes(node_id: str, service_id: str) -> bytes:
    value = {
        "node_id": node_id,
        "owner": "Local Hand",
        "schema_version": ROOT_MARKER_SCHEMA,
        "service_id": service_id,
    }
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def ensure_root_owner_marker(
    state_root: str | os.PathLike[str],
    node_id: str,
    service_id: str,
    *,
    allow_create: bool = False,
) -> Path:
    root = assert_no_link_or_reparse_chain(state_root)
    created_root = False
    try:
        st = root.lstat()
    except FileNotFoundError as exc:
        if not allow_create:
            raise LocalHandError(
                "bootstrap_state_root_invalid",
                f"StateRoot must exist before its ownership marker is established: {root}",
            ) from exc
        try:
            root.mkdir(mode=0o700)
            created_root = True
            st = root.lstat()
        except FileExistsError as race:
            raise LocalHandError(
                "bootstrap_root_owner_indeterminate",
                "StateRoot appeared during create-only ownership establishment; refusing adoption",
                "indeterminate",
            ) from race
        except OSError as create_exc:
            raise LocalHandError(
                "bootstrap_root_owner_indeterminate",
                f"cannot create StateRoot for ownership establishment: {root}",
                "indeterminate",
            ) from create_exc
    except OSError as exc:
        raise LocalHandError(
            "bootstrap_state_root_invalid",
            f"StateRoot must exist before its ownership marker is established: {root}",
        ) from exc
    if not stat.S_ISDIR(st.st_mode) or _is_reparse(st):
        raise LocalHandError("bootstrap_state_root_invalid", f"StateRoot is not a real directory: {root}")

    marker = root / ROOT_MARKER_NAME
    expected = _marker_bytes(node_id, service_id)
    if not marker.exists() and not marker.is_symlink():
        if not created_root:
            raise LocalHandError(
                "bootstrap_root_owner_missing",
                "existing StateRoot has no Local Hand ownership marker; refusing adoption",
            )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(marker, flags, 0o444)
    except FileExistsError:
        try:
            marker_stat = marker.lstat()
            if stat.S_ISLNK(marker_stat.st_mode) or _is_reparse(marker_stat) or not stat.S_ISREG(marker_stat.st_mode):
                raise LocalHandError("bootstrap_root_owner_mismatch", "root ownership marker is not a regular non-reparse file")
            read_flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                read_flags |= os.O_NOFOLLOW
            read_fd = os.open(marker, read_flags)
            try:
                opened = os.fstat(read_fd)
                if not stat.S_ISREG(opened.st_mode) or _is_reparse(opened):
                    raise LocalHandError("bootstrap_root_owner_mismatch", "opened root ownership marker is unsafe")
                chunks: list[bytes] = []
                remaining = 4097
                while remaining:
                    chunk = os.read(read_fd, remaining)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                actual = b"".join(chunks)
                if len(actual) > 4096:
                    raise LocalHandError("bootstrap_root_owner_mismatch", "root ownership marker is oversized")
            finally:
                os.close(read_fd)
        except LocalHandError:
            raise
        except OSError as exc:
            raise LocalHandError(
                "bootstrap_root_owner_indeterminate",
                "cannot read existing root ownership marker",
                "indeterminate",
            ) from exc
        if actual != expected:
            raise LocalHandError(
                "bootstrap_root_owner_mismatch",
                "StateRoot ownership marker does not match this node/service",
            )
        return marker
    except OSError as exc:
        raise LocalHandError(
            "bootstrap_root_owner_indeterminate",
            "cannot create root ownership marker",
            "indeterminate",
        ) from exc

    try:
        view = memoryview(expected)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fsync(fd)
    except OSError as exc:
        raise LocalHandError(
            "bootstrap_root_owner_indeterminate",
            "cannot durably write root ownership marker",
            "indeterminate",
        ) from exc
    finally:
        os.close(fd)
    if os.name != "nt":
        try:
            parent_fd = os.open(root, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        except OSError:
            pass
    return marker


def service_owner_token(state_root: str | os.PathLike[str], node_id: str, service_id: str) -> str:
    identity = {
        "node_id": node_id,
        "schema_version": SERVICE_OWNER_SCHEMA,
        "service_id": service_id,
        "state_root": _path_key(_absolute(state_root)),
    }
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{SERVICE_OWNER_SCHEMA}:{hashlib.sha256(canonical).hexdigest()}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Hand bootstrap safety helpers")
    sub = parser.add_subparsers(dest="command", required=True)
    roots = sub.add_parser("validate-roots")
    roots.add_argument("--state-root", required=True)
    roots.add_argument("--projects-root", required=True)
    roots.add_argument("--reserved-root", action="append", default=[])
    marker = sub.add_parser("ensure-root-marker")
    marker.add_argument("--state-root", required=True)
    marker.add_argument("--node-id", required=True)
    marker.add_argument("--service-id", required=True)
    marker.add_argument("--allow-create", action="store_true")
    token = sub.add_parser("service-owner-token")
    token.add_argument("--state-root", required=True)
    token.add_argument("--node-id", required=True)
    token.add_argument("--service-id", required=True)
    target = sub.add_parser("validate-repository-target")
    target.add_argument("--projects-root", required=True)
    target.add_argument("--repository-path", required=True)
    sub.add_parser("new-install-instance-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate-roots":
            validate_install_roots(args.state_root, args.projects_root, reserved_roots=args.reserved_root)
        elif args.command == "ensure-root-marker":
            ensure_root_owner_marker(
                args.state_root,
                args.node_id,
                args.service_id,
                allow_create=args.allow_create,
            )
        elif args.command == "service-owner-token":
            print(service_owner_token(args.state_root, args.node_id, args.service_id))
        elif args.command == "validate-repository-target":
            print(repository_target(Path(args.projects_root), args.repository_path))
        else:
            print(new_install_instance_id())
    except LocalHandError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
