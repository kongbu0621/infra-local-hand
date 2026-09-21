"""Shared, side-effect-free admission of explicit deployment configuration."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from .bounded_io import read_regular_file_bounded
from .protocol import LocalHandError

PROFILE_SCHEMA = "local-hand-profile/v2"
TRANSPORT_SCHEMA = "local-hand-git-mailbox/v1"
MAX_CONFIG_BYTES = 1024 * 1024
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SSH = re.compile(r"^(?:ssh://)?(?P<user>[A-Za-z0-9_][A-Za-z0-9._-]*)@(?P<host>[a-z0-9][a-z0-9.-]*)(?P<tail>[:/].+)$")


def _invalid(message: str) -> LocalHandError:
    return LocalHandError("invalid_profile", message)


def strict_json(raw: bytes) -> Any:
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise _invalid(f"duplicate configuration key: {key}")
            value[key] = item
        return value

    def constant(value):
        raise _invalid(f"non-finite JSON constant: {value}")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except LocalHandError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise _invalid("configuration must be bounded UTF-8 JSON") from exc


def read_config(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = read_regular_file_bounded(path, MAX_CONFIG_BYTES, "invalid_profile")
    except OSError as exc:
        raise _invalid("cannot read configuration file") from exc
    value = strict_json(raw)
    if not isinstance(value, dict):
        raise _invalid("configuration must be an object")
    return raw, value


def exact_keys(value: Any, keys: set[str], field: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise _invalid(f"{field} must have exactly these keys: {', '.join(sorted(keys))}")


def validate_branch(branch: Any) -> str:
    if (not isinstance(branch, str) or not branch or len(branch) > 240
            or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._/-]*", branch)
            or ".." in branch or branch.endswith(("/", "."))):
        raise _invalid("branch must be an explicit safe Git branch name")
    if any(not part or part.startswith(".") or part.endswith(".lock") for part in branch.split("/")):
        raise _invalid("invalid Git branch component")
    return branch


def ssh_identity(url: Any) -> tuple[str, str, int, str]:
    """Validate supported SSH Git-host spellings without broadening admission."""
    if not isinstance(url, str) or len(url) > 2048:
        raise _invalid("remote URL must be a bounded SSH URL")
    match = _SSH.fullmatch(url)
    if match is None:
        raise _invalid("only explicit user@host:path or ssh://user@host/path SSH remotes are supported")
    user, host, tail = match.group("user", "host", "tail")
    if len(host)>253 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
        raise _invalid("invalid SSH host")
    port = 22
    if url.startswith("ssh://"):
        if tail.startswith(":"):
            port_text, sep, tail_path = tail[1:].partition("/")
            if not sep or not re.fullmatch(r"[1-9][0-9]{0,4}", port_text) or int(port_text)>65535:
                raise _invalid("invalid SSH port")
            port = int(port_text); path = tail_path
        else:
            path = tail[1:]
    else:
        if not tail.startswith(":"):
            raise _invalid("SCP SSH remote requires ':'")
        path = tail[1:]
    if not path.endswith(".git") or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", part) or part in (".", "..") for part in path.split("/")):
        raise _invalid("remote must use an explicit canonical repository path ending in .git")
    return user, host, port, path


@dataclass(frozen=True)
class TransportPolicy:
    remote_url: str
    allowed_remote_urls: tuple[str, ...]
    branch: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema_version": TRANSPORT_SCHEMA, "remote_url": self.remote_url,
                "allowed_remote_urls": list(self.allowed_remote_urls), "branch": self.branch}

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def parse_transport(value: Any) -> TransportPolicy:
    exact_keys(value, {"schema_version", "remote_url", "allowed_remote_urls", "branch"}, "transport_policy")
    if value["schema_version"] != TRANSPORT_SCHEMA:
        raise _invalid("unsupported transport_policy schema")
    allowed = value["allowed_remote_urls"]
    if not isinstance(allowed, list) or not allowed or len(allowed)>16 or any(not isinstance(x,str) for x in allowed):
        raise _invalid("allowed_remote_urls must be a nonempty bounded list of strings")
    if len(set(allowed)) != len(allowed):
        raise _invalid("duplicate admitted remote spelling")
    identities = {ssh_identity(url) for url in allowed}
    identity = ssh_identity(value["remote_url"])
    if len(identities)!=1 or identity not in identities or value["remote_url"] not in allowed:
        raise _invalid("remote and every admitted spelling must name the same explicit SSH target")
    return TransportPolicy(value["remote_url"], tuple(allowed), validate_branch(value["branch"]))


def load_transport(path: Path) -> TransportPolicy:
    return parse_transport(read_config(path)[1])


def validate_profile_shape(value: Any) -> TransportPolicy:
    exact_keys(value, {"profile_schema", "node_id", "projects_root", "repositories", "transport_policy"}, "Node Profile v2")
    if value["profile_schema"] != PROFILE_SCHEMA:
        raise _invalid("profile v2 required; migrate legacy configuration explicitly")
    if not isinstance(value["node_id"],str) or not _ID.fullmatch(value["node_id"]):
        raise _invalid("invalid node_id")
    if not isinstance(value["projects_root"],str) or not value["projects_root"].strip():
        raise _invalid("projects_root must be explicit")
    repos=value["repositories"]
    if not isinstance(repos,dict) or not repos:
        raise _invalid("repositories must be nonempty")
    for name, spec in repos.items():
        if not _ID.fullmatch(name):raise _invalid("invalid repository name")
        exact_keys(spec,{"path","single_writer","validations"},f"repositories.{name}")
        if not isinstance(spec["path"],str) or not spec["path"]:raise _invalid("repository path required")
        if not isinstance(spec["single_writer"],bool):raise _invalid("single_writer must be boolean")
        if not isinstance(spec["validations"],dict):raise _invalid("validations must be an object")
        for key, val in spec["validations"].items():
            if not _ID.fullmatch(key):raise _invalid("invalid validation name")
            exact_keys(val,{"argv","timeout_seconds","replay_safe"},f"validation.{key}")
            if not isinstance(val["argv"],list) or not val["argv"] or any(not isinstance(v,str) or not v or '\0' in v for v in val["argv"]):
                raise _invalid("validation argv must be nonempty strings without NUL")
            timeout=val["timeout_seconds"]
            if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not 0<timeout<=3600 or not math.isfinite(timeout):
                raise _invalid("validation timeout must be finite, numeric, > 0 and <= 3600")
            if not isinstance(val["replay_safe"],bool):raise _invalid("replay_safe must be boolean")
    return parse_transport(value["transport_policy"])


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Validate an explicit Local Hand profile before installation")
    parser.add_argument("--profile",type=Path,required=True)
    parser.add_argument("--field",choices=("node_id","projects_root","remote_url","branch","digest","repository_path","single_writer"))
    parser.add_argument("--repository",help="repository selected for bootstrap seeding")
    for name in ("node-id","projects-root","repository-path","branch","remote-url"):
        parser.add_argument("--match-"+name)
    args=parser.parse_args(argv)
    try:
        from .paths import load_profile
        profile=load_profile(args.profile)
        values={"node_id":profile.node_id,"projects_root":str(profile.projects_root),"remote_url":profile.transport_policy.remote_url,
                "branch":profile.transport_policy.branch,"digest":profile.profile_sha256}
        if args.repository is not None:
            if args.repository not in profile.repositories:raise _invalid("bootstrap repository is not allowlisted")
            repo=profile.repositories[args.repository]
            values.update(repository_path=repo.relative_path,single_writer=repo.single_writer)
        for name in ("node_id","projects_root","repository_path","branch","remote_url"):
            expected=getattr(args,"match_"+name)
            if expected and expected!=values.get(name):raise _invalid(f"bootstrap {name} differs from profile")
        if args.field and args.field not in values:raise _invalid("repository selection is required")
        result=values[args.field] if args.field else values
        print(result if isinstance(result,str) else json.dumps(result))
        return 0
    except LocalHandError as exc:
        parser.exit(2,f"{exc.code}: {exc.message}\n")


if __name__ == "__main__":
    raise SystemExit(main())
