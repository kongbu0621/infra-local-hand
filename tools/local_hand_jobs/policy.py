"""Protected private admission, bounded budgets, and per-principal discovery.

Configuration is loaded once at service startup. Authorization and discovery
only inspect the admitted in-memory snapshot; they never touch mounted storage.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import threading
from types import MappingProxyType
from typing import Any, Mapping

from .contract import (DIGEST_PATTERN, KINDS, MAX_SAFE_INTEGER, REF_PATTERN,
                       SCHEMA_VERSION, TOOL_SCOPES, TOOL_SCHEMA_DIGEST, UUID_PATTERN,
                       JobError, Principal, canonical_bytes, strict_loads)

BUDGET_FIELDS = frozenset(("wall_seconds", "terminate_grace_seconds", "cpu_seconds",
    "memory_bytes", "processes", "temporary_bytes", "nas_bytes", "log_bytes", "reservation_bytes"))
LIMIT_FIELDS = frozenset(("max_queued", "max_running", "retained_bytes", "ledger_emergency_bytes", "requests_per_minute"))


def freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(item) for item in value)
    return value


def thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [thaw(item) for item in value]
    return value


def _bad() -> JobError:
    return JobError("UNAUTHORIZED", "Private admission configuration is invalid")


def _keys(value: Any, required: set | frozenset, optional: set | frozenset = frozenset()) -> None:
    if type(value) is not dict or not required <= value.keys() or value.keys() - required - optional:
        raise _bad()


def _ref(value: Any) -> None:
    if type(value) is not str or re.fullmatch(REF_PATTERN, value) is None:
        raise _bad()


def _digest(value: Any, length: int = 64) -> None:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{%d}" % length, value) is None:
        raise _bad()


def _positive(value: Any, allow_zero: bool = False) -> None:
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= MAX_SAFE_INTEGER:
        raise _bad()


def _path(value: Any) -> str:
    if type(value) is not str or not value.startswith("/") or value.startswith("//") or "\x00" in value:
        raise _bad()
    path = Path(value)
    if ".." in path.parts or str(path) != value or value == "/":
        raise _bad()
    return value


def _refs(value: Any, allowed: set | frozenset | None = None) -> None:
    if type(value) is not list or len(set(value)) != len(value):
        raise _bad()
    for item in value:
        _ref(item)
        if allowed is not None and item not in allowed:
            raise _bad()


def _overlap(left: str, right: str) -> bool:
    a, b = Path(left), Path(right)
    return a == b or a in b.parents or b in a.parents


def _trusted_directory(info) -> bool:
    # Directory owners can chmod or replace descendants even when group/other
    # write bits are clear. Only root-owned sticky ancestors such as /tmp may
    # retain shared write access around the privately owned admitted roots.
    return (stat.S_ISDIR(info.st_mode) and info.st_uid in {0, os.geteuid()}
            and (not info.st_mode & 0o022 or (info.st_uid == 0 and info.st_mode & stat.S_ISVTX)))


def _file_names(files: Any, digest_length: int) -> None:
    if type(files) is not dict:
        raise _bad()
    for name, digest in files.items():
        if type(name) is not str or not name or Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name:
            raise _bad()
        _digest(digest, digest_length)


class Policy:
    """An immutable policy snapshot plus a bounded server-owned output catalog.

    ``Policy(mapping)`` is also useful for synthetic dependency-injected tests.
    Production entrypoints load ``Policy.from_file`` and independently verify
    the complete installed release before constructing the broker.
    """

    def __init__(self, config: dict[str, Any]):
        try:
            config = json.loads(json.dumps(config, allow_nan=False))
            self._validate(config)
        except JobError:
            raise
        except (ValueError, TypeError, OverflowError, RecursionError):
            raise _bad() from None
        self.config = freeze(config)
        self.policy_digest = hashlib.sha256(canonical_bytes(config)).hexdigest()
        self.generation = config["generation"]
        self.limits = self.config["limits"]
        self.authority_id = config["authority_id"]
        self.broker_root = config["broker_root"]
        self.authority_root = config["authority_root"]
        self.installed_payload_digest = config["installed_payload_digest"]
        self.execution_entrypoint = config["execution_entrypoint"]
        self.source_commit = config["source_commit"]
        self.profiles = self.config["profiles"]
        self.principals = self.config["principals"]
        self.local_peers = self.config.get("local_peers", MappingProxyType({}))
        self._prepared: dict[str, dict[str, str]] = {}
        self._catalog_lock = threading.RLock()
        self._cursor_key = os.urandom(32)

    @staticmethod
    def _validate(config: dict) -> None:
        _keys(config, {"schema_version", "authority_id", "node_id", "install_uuid", "deployment_epoch",
            "generation", "broker_root", "authority_root", "forbidden_roots", "limits", "profiles", "principals",
            "installed_payload_digest", "execution_entrypoint", "source_commit"}, {"local_peers", "process_manager"})
        if config["schema_version"] != "lh-policy-v1":
            raise _bad()
        for field in ("authority_id", "node_id"):
            _ref(config[field])
        if type(config["install_uuid"]) is not str or re.fullmatch(UUID_PATTERN, config["install_uuid"]) is None:
            raise _bad()
        for field in ("deployment_epoch", "generation"):
            _positive(config[field])
        _digest(config["source_commit"], 40)
        _digest(config["installed_payload_digest"])
        for field in ("broker_root", "authority_root", "execution_entrypoint"):
            _path(config[field])
        if type(config["forbidden_roots"]) is not list or not config["forbidden_roots"]:
            raise _bad()
        forbidden = [_path(path) for path in config["forbidden_roots"]]
        _keys(config["limits"], LIMIT_FIELDS, {"control_response_seconds"})
        for value in config["limits"].values():
            _positive(value)
        if type(config["profiles"]) is not dict or not config["profiles"]:
            raise _bad()
        writable = [config["broker_root"], config["authority_root"]]
        profile_roots = []
        archives = []
        readonly = [config["execution_entrypoint"]]
        for ref, profile in config["profiles"].items():
            _ref(ref)
            _keys(profile, {"work_root", "evidence_root", "temporary_root", "python", "sources", "build_caches",
                "storages", "budgets", "resource_ids"}, {"execution_admission", "display_name"})
            for field in ("work_root", "evidence_root", "temporary_root", "python"):
                _path(profile[field])
            roots = [profile[field] for field in ("work_root", "evidence_root", "temporary_root")]
            if any(_overlap(left, right) for index, left in enumerate(roots) for right in roots[index + 1:]):
                raise _bad()
            writable.extend(roots)
            readonly.append(profile["python"])
            _refs(profile["resource_ids"])
            if not profile["resource_ids"]:
                raise _bad()
            profile_roots.append((roots, set(profile["resource_ids"])))
            if "display_name" in profile and (type(profile["display_name"]) is not str or len(profile["display_name"]) > 256):
                raise _bad()
            if "execution_admission" in profile:
                _keys(profile["execution_admission"], {"quota_enforced", "filesystem_isolation", "stable_inputs"})
                if any(value is not True for value in profile["execution_admission"].values()):
                    raise _bad()
            for category in ("sources", "build_caches", "storages"):
                if type(profile[category]) is not dict:
                    raise _bad()
                for input_ref, item in profile[category].items():
                    _ref(input_ref)
                    if category == "sources":
                        _keys(item, {"root", "commit", "blobs"})
                        _path(item["root"])
                        readonly.append(item["root"])
                        _digest(item["commit"], 40)
                        _file_names(item["blobs"], 40)
                    elif category == "build_caches":
                        _keys(item, {"root", "files"})
                        _path(item["root"])
                        readonly.append(item["root"])
                        _file_names(item["files"], 64)
                    else:
                        _keys(item, {"config", "config_digest", "resource_id", "archive_root", "stable_mount_binding"})
                        _path(item["config"])
                        _path(item["archive_root"])
                        _digest(item["config_digest"])
                        _ref(item["resource_id"])
                        binding = item["stable_mount_binding"]
                        _keys(binding, {"source", "root", "type", "device", "inode"})
                        if (type(binding["source"]) is not str or not 1 <= len(binding["source"]) <= 1024
                                or any(ord(char) < 32 for char in binding["source"])
                                or type(binding["root"]) is not str or not binding["root"].startswith("/")
                                or binding["root"].startswith("//")
                                or str(Path(binding["root"])) != binding["root"] or ".." in Path(binding["root"]).parts
                                or binding["type"] not in ("nfs", "nfs4", "cifs")):
                            raise _bad()
                        _positive(binding["device"], allow_zero=True)
                        _positive(binding["inode"])
                        writable.append(item["archive_root"])
                        readonly.append(item["config"])
                        archives.append((item["archive_root"], item["resource_id"], binding))
            _keys(profile["budgets"], set(KINDS) | {"reconcile"})
            for kind, budget in profile["budgets"].items():
                _keys(budget, BUDGET_FIELDS)
                for field, value in budget.items():
                    _positive(value, allow_zero=field == "nas_bytes" and kind != "ledger.nas.roundtrip")
                # Reservation includes originals, staging ZIP and final ZIP.
                if budget["reservation_bytes"] < 3 * (budget["temporary_bytes"] + budget["log_bytes"]):
                    raise _bad()
                if budget["reservation_bytes"] > config["limits"]["retained_bytes"]:
                    raise _bad()
        if any(_overlap(root, denied) for root in writable for denied in forbidden):
            raise _bad()
        if any(_overlap(root, source) for root in writable for source in readonly):
            raise _bad()
        # Execution writers must never include either authoritative control
        # root, even when a private profile mistakenly assigns the same path.
        execution_roots = [root for roots, _ in profile_roots for root in roots]
        execution_roots.extend(root for root, _, _ in archives)
        if any(_overlap(root, control) for root in execution_roots
               for control in (config["broker_root"], config["authority_root"])):
            raise _bad()
        # An archive alias can overlap a different profile's local working
        # storage. Both kinds of job must acquire the archive's same lease;
        # checking only archive/archive and work/work pairs misses this case.
        for archive_root, archive_id, _ in archives:
            for roots, resource_ids in profile_roots:
                if any(_overlap(archive_root, root) for root in roots) and archive_id not in resource_ids:
                    raise _bad()
        for index, (left_root, left_id, left_binding) in enumerate(archives):
            for right_root, right_id, right_binding in archives[index + 1:]:
                same_mount_object = (left_binding["source"], left_binding["root"], left_binding["type"],
                    left_binding["device"], left_binding["inode"]) == (right_binding["source"], right_binding["root"],
                    right_binding["type"], right_binding["device"], right_binding["inode"])
                if (_overlap(left_root, right_root) or same_mount_object) and left_id != right_id:
                    raise _bad()
        for index, (left_roots, left_ids) in enumerate(profile_roots):
            for right_roots, right_ids in profile_roots[index + 1:]:
                if any(_overlap(a, b) for a in left_roots for b in right_roots) and not left_ids & right_ids:
                    raise _bad()
        if type(config["principals"]) is not dict or not config["principals"]:
            raise _bad()
        for principal_id, grant in config["principals"].items():
            _ref(principal_id)
            _keys(grant, {"scopes", "profiles"})
            if type(grant["scopes"]) is not list or not set(grant["scopes"]) <= set(TOOL_SCOPES.values()):
                raise _bad()
            if type(grant["profiles"]) is not dict or not grant["profiles"]:
                raise _bad()
            for profile_ref, access in grant["profiles"].items():
                if profile_ref not in config["profiles"]:
                    raise _bad()
                _keys(access, {"kinds", "source_refs", "build_cache_refs", "storage_refs", "prepared_refs", "prepared_access"})
                _refs(access["kinds"], set(KINDS))
                profile = config["profiles"][profile_ref]
                for field, category in (("source_refs", "sources"), ("build_cache_refs", "build_caches"), ("storage_refs", "storages")):
                    _refs(access[field], set(profile[category]))
                _refs(access["prepared_refs"])
                if access["prepared_access"] not in ("owned", "listed"):
                    raise _bad()
                if access["prepared_access"] == "owned" and access["prepared_refs"]:
                    raise _bad()
        peers = config.get("local_peers", {})
        if type(peers) is not dict:
            raise _bad()
        for uid, principal_id in peers.items():
            if not isinstance(uid, str) or re.fullmatch(r"0|[1-9][0-9]{0,9}", uid) is None or principal_id not in config["principals"]:
                raise _bad()
        if "process_manager" in config:
            manager = config["process_manager"]
            _keys(manager, {"uid", "slice", "cgroup"})
            _positive(manager["uid"], allow_zero=True)
            if (type(manager["slice"]) is not str or
                    re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,100}\.slice", manager["slice"]) is None):
                raise _bad()
            _path(manager["cgroup"])
            if not manager["cgroup"].startswith("/sys/fs/cgroup/"):
                raise _bad()

    @classmethod
    def from_file(cls, path: str | Path) -> "Policy":
        """Open a private regular config with no symlink or writeable ancestors."""
        try:
            target = Path(path)
            if not target.is_absolute():
                raise _bad()
            parents = {}
            for parent in target.parents:
                info = parent.lstat()
                if not _trusted_directory(info):
                    raise _bad()
                parents[parent] = (info.st_dev, info.st_ino, info.st_mode, info.st_uid)
            def check_parents():
                # O_NOFOLLOW protects the file itself, not earlier path
                # components. A substituted parent must not rebind admission.
                for parent, identity in parents.items():
                    info = parent.lstat()
                    if (info.st_dev, info.st_ino, info.st_mode, info.st_uid) != identity:
                        raise _bad()
            descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            body_failed = False
            try:
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid() or before.st_mode & 0o077 or before.st_nlink != 1:
                    raise _bad()
                check_parents()
                raw = os.read(descriptor, 65537)
                if len(raw) != min(before.st_size, 65537):
                    raise JobError("IO_UNCERTAIN", "Private admission read is incomplete")
                after = os.fstat(descriptor)
                current = target.lstat()
                if (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or (
                        before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
                    raise _bad()
                check_parents()
            except BaseException:
                body_failed = True
                raise
            finally:
                try:
                    os.close(descriptor)
                except OSError:
                    # Do not replace a prior admission rejection or retry a
                    # descriptor number that close may already have released.
                    if not body_failed:
                        raise
            policy = cls(strict_loads(raw))
            policy.validate_paths()
            return policy
        except OSError:
            raise JobError("IO_UNCERTAIN", "Private admission could not be verified") from None

    def validate_paths(self) -> None:
        """Startup-only metadata admission, before any request service starts."""
        directories = [self.broker_root, self.authority_root]
        files = [self.execution_entrypoint]
        for profile in self.profiles.values():
            directories.extend(profile[key] for key in ("work_root", "evidence_root", "temporary_root"))
            files.append(profile["python"])
            directories.extend(item["root"] for category in ("sources", "build_caches") for item in profile[category].values())
            # Do not touch NAS here: source/content and mounts require registered
            # supervised preflight. Only lexical path admission occurs at load.
        try:
            for value in directories + files:
                path = Path(value)
                for parent in reversed((path, *path.parents)):
                    info = parent.lstat()
                    if stat.S_ISLNK(info.st_mode):
                        raise _bad()
                    if parent != path and not _trusted_directory(info):
                        raise _bad()
                info = path.lstat()
                if value in directories:
                    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                        raise _bad()
                elif (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022
                      or info.st_uid not in {0, os.geteuid()}):
                    raise _bad()
        except OSError:
            raise JobError("IO_UNCERTAIN", "Private admission paths could not be verified") from None

    def authorize(self, principal: Principal, scope: str, request: Mapping | None = None, owner: str | None = None) -> None:
        if not isinstance(principal, Principal):
            raise JobError("UNAUTHORIZED", "A verified principal is required")
        grant = self.principals.get(principal.principal_id)
        if grant is None or scope not in principal.scopes or scope not in grant["scopes"]:
            raise JobError("UNAUTHORIZED", "Current principal does not have the required grant")
        if owner is not None and owner != principal.principal_id:
            raise JobError("UNAUTHORIZED", "Resource belongs to a different principal")
        if request is not None and "profile_ref" in request:
            access = grant["profiles"].get(request["profile_ref"])
            if access is None or request.get("kind") not in access["kinds"]:
                raise JobError("UNAUTHORIZED", "Job kind or profile is not granted")
            for field, allowed in (("source_ref", "source_refs"), ("build_cache_ref", "build_cache_refs"), ("storage_ref", "storage_refs")):
                if field in request.get("inputs", {}) and request["inputs"][field] not in access[allowed]:
                    raise JobError("UNAUTHORIZED", "Logical input is not granted")
            prepared_ref = request.get("inputs", {}).get("prepared_ref")
            if prepared_ref is not None and access["prepared_access"] == "listed" and prepared_ref not in access["prepared_refs"]:
                raise JobError("UNAUTHORIZED", "Prepared reference is not granted")
            # Dynamic prepared references are authorized against their sealed
            # server facts in Registry. A client-supplied ref is never a grant.

    def profile(self, profile_ref: str) -> Mapping:
        try:
            return self.profiles[profile_ref]
        except KeyError:
            raise JobError("UNAUTHORIZED", "Profile is not admitted") from None

    def expected(self, profile_ref: str) -> dict:
        from .registry import REGISTRY_DIGEST
        profile = self.profile(profile_ref)
        return {"node_id": self.config["node_id"], "install_uuid": self.config["install_uuid"],
            "deployment_epoch": self.config["deployment_epoch"],
            "profile_digest": hashlib.sha256(canonical_bytes(thaw(profile))).hexdigest(),
            "policy_digest": self.policy_digest, "registry_digest": REGISTRY_DIGEST}

    def register_prepared_reference(self, ref: str, *, owner: str, profile_ref: str, expected: Mapping | None = None) -> None:
        _ref(ref)
        fact = {"owner": owner, "profile_ref": profile_ref,
                "expected": thaw(expected) if expected is not None else self.expected(profile_ref)}
        with self._catalog_lock:
            if ref in self._prepared and self._prepared[ref] != fact:
                raise JobError("CONFLICT", "Prepared reference cannot be rebound")
            self._prepared[ref] = fact

    def capabilities(self, principal: Principal, cursor: str | None = None, page_size: int = 100) -> dict:
        self.authorize(principal, "lh:inspect")
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise JobError("LIMIT_EXCEEDED", "Capability page size exceeds its bound")
        profiles = []
        with self._catalog_lock:
            prepared_catalog = list(self._prepared.items())
        for ref, access in sorted(self.principals[principal.principal_id]["profiles"].items()):
            if not access["kinds"]:
                continue
            prepared_refs = sorted(ref_ for ref_, fact in prepared_catalog
                                   if fact == {"owner": principal.principal_id, "profile_ref": ref, "expected": self.expected(ref)}
                                   and (access["prepared_access"] == "owned" or ref_ in access["prepared_refs"]))
            profiles.append({"profile_ref": ref, "expected": self.expected(ref), "allowed_kinds": list(access["kinds"]),
                "source_refs": list(access["source_refs"]), "build_cache_refs": list(access["build_cache_refs"]),
                "storage_refs": list(access["storage_refs"]), "prepared_refs": prepared_refs,
                "budgets": {kind: thaw(self.profiles[ref]["budgets"][kind]) for kind in access["kinds"]}})
        version = hashlib.sha256(canonical_bytes({"principal": principal.principal_id,
                    "policy": self.policy_digest, "profiles": profiles})).hexdigest()
        offset = 0
        if cursor is not None:
            try:
                packed = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
                raw, signature = packed[:-32], packed[-32:]
                if not hmac.compare_digest(signature, hmac.digest(self._cursor_key, raw, "sha256")):
                    raise ValueError()
                data = json.loads(raw)
                if data["principal"] != principal.principal_id or data["version"] != version:
                    raise JobError("STALE_DEPLOYMENT", "Capability cursor no longer matches this catalog")
                offset = data["offset"]
                if type(offset) is not int or not 0 <= offset <= len(profiles):
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                raise JobError("INVALID_REQUEST", "Invalid capability cursor") from None
        page, next_offset = [], offset
        while next_offset < len(profiles) and len(page) < page_size:
            candidate = profiles[next_offset]
            if len(canonical_bytes(page + [candidate])) > 500 * 1024:
                if not page:
                    raise JobError("LIMIT_EXCEEDED", "Profile catalog exceeds the response bound")
                break
            page.append(candidate)
            next_offset += 1
        next_cursor = None
        if next_offset < len(profiles):
            raw = canonical_bytes({"principal": principal.principal_id, "version": version, "offset": next_offset})
            next_cursor = base64.urlsafe_b64encode(raw + hmac.digest(self._cursor_key, raw, "sha256")).rstrip(b"=").decode("ascii")
        return {"schema_version": SCHEMA_VERSION, "supported_versions": [SCHEMA_VERSION],
            "tool_schema_digest": TOOL_SCHEMA_DIGEST, "authority_id": self.authority_id,
            "policy_digest": self.policy_digest, "generation": self.generation, "catalog_version": version,
            "execution_support": {"ledger.nas.roundtrip": {"status": "UNSUPPORTED",
                "reason": "NETWORK_ARCHIVE_HARD_QUOTA_ADAPTER_UNIMPLEMENTED"}},
            "profiles": page, "next_cursor": next_cursor}


def load_policy(path: str | Path) -> Policy:
    return Policy.from_file(path)
