"""Private bounded launch preparation, executed only in a supervised unit.

The transport contains the fixed registry plan, never a profile or credentials.
Directory and quota observations belong here, not to the broker's observer
thread. Root slots are provisioned by deployment and consumed by the ledger.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from .contract import JobError

MAX_PAYLOAD_BYTES = 64 * 1024
MAX_ENCODED_BYTES = ((MAX_PAYLOAD_BYTES + 2) // 3) * 4
_SECRET_KEYS = frozenset(("token", "access_token", "refresh_token", "secret", "password",
                          "authorization", "cookie", "private_key", "client_secret"))
_ENVIRONMENT_KEYS = frozenset(("PATH", "LANG", "LC_ALL", "TMPDIR", "TMP", "TEMP",
    "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE", "PIP_CONFIG_FILE", "PIP_NO_INDEX",
    "PIP_DISABLE_PIP_VERSION_CHECK", "PIP_NO_CACHE_DIR", "PYTHONPATH", "A2_RESOURCE_TESTS"))


def _check_data(value, depth=0):
    if depth > 24:
        raise JobError("LIMIT_EXCEEDED", "Bootstrap plan nesting exceeds its fixed bound")
    if isinstance(value, dict):
        if any(not isinstance(key, str) or key.lower() in _SECRET_KEYS for key in value):
            raise JobError("UNSUPPORTED", "Bootstrap transport does not accept credential fields")
        for key, child in value.items():
            if key in ("env", "environment") and (
                    not isinstance(child, dict) or not set(child) <= _ENVIRONMENT_KEYS):
                raise JobError("UNSUPPORTED", "Bootstrap transport requires the fixed clean environment")
            _check_data(child, depth + 1)
    elif isinstance(value, list):
        for child in value: _check_data(child, depth + 1)
    elif value is not None and type(value) not in (str, int, bool):
        raise JobError("UNSUPPORTED", "Bootstrap transport requires fixed JSON data")


def encode_payload(payload):
    _check_data(payload)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                     allow_nan=False).encode("ascii")
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise JobError("LIMIT_EXCEEDED", "Bootstrap plan exceeds its bounded launch transport")
    return base64.b64encode(raw).decode("ascii")


def decode_payload(encoded):
    if isinstance(encoded, str) and encoded.startswith("lhq2-bootstrap-z1:"):
        from . import quota_payload
        return quota_payload.decode_bootstrap(encoded)
    if not isinstance(encoded, str) or len(encoded) > MAX_ENCODED_BYTES:
        raise JobError("LIMIT_EXCEEDED", "Bootstrap plan exceeds its bounded launch transport")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (ValueError, UnicodeError) as error:
        raise JobError("UNSUPPORTED", "Bootstrap plan encoding is invalid") from error
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise JobError("LIMIT_EXCEEDED", "Bootstrap plan exceeds its bounded launch transport")
    # This is an internal plan, deeper than the public seven-tool envelope.
    def unique_pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=unique_pairs,
                           parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        _check_data(value)
        if encode_payload(value) != encoded: raise ValueError("noncanonical payload")
    except (ValueError, UnicodeError, RecursionError) as error:
        raise JobError("UNSUPPORTED", "Bootstrap plan JSON is invalid") from error
    return value


def check_argv(command, environment):
    """Bound both Linux's single-argument limit and the total execve envelope."""
    try:
        argument_limit = int(os.sysconf("SC_PAGE_SIZE")) * 32
        total_limit = int(os.sysconf("SC_ARG_MAX"))
    except (OSError, ValueError) as error:
        raise JobError("UNSUPPORTED", "Host argument transport limits are unavailable") from error
    entries = [os.fsencode(value) + b"\0" for value in command]
    entries += [os.fsencode(key + "=" + value) + b"\0" for key, value in environment.items()]
    # Reserve at least half ARG_MAX for the manager's fixed execution overhead.
    if (not entries or any(len(value) >= argument_limit for value in entries)
            or sum(map(len, entries)) + 8 * (len(entries) + 2) > total_limit // 2):
        raise JobError("LIMIT_EXCEEDED", "Bootstrap command exceeds host argument transport limits")


def plan_name(execution_id):
    return "plan-" + hashlib.sha256(execution_id.encode()).hexdigest()[:24] + ".json"


def _close_all(descriptors, primary=None):
    failure = None
    for descriptor in descriptors:
        try:
            os.close(descriptor)
        except BaseException as error:
            if primary is not None:
                primary.add_note("Bootstrap descriptor cleanup: " + type(error).__name__)
            elif failure is None:
                failure = error
            else:
                failure.add_note("Additional bootstrap descriptor cleanup: " + type(error).__name__)
    if failure is not None:
        raise failure


def _root_descriptor(path, identity):
    if not isinstance(path, str) or str(Path(path)) != path or not Path(path).is_absolute():
        raise JobError("UNSUPPORTED", "Bootstrap requires canonical preprovisioned roots")
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077
                or (info.st_dev, info.st_ino, info.st_uid) != (
                    identity["device"], identity["inode"], identity["uid"])
                or Path(path).resolve() != Path(path)):
            raise JobError("IO_UNCERTAIN", "Preprovisioned root identity no longer matches")
        return descriptor
    except BaseException as error:
        _close_all([descriptor], error)
        raise


def verify_roots(execution):
    """Recheck bindings inside the final supervised helper before any writes."""
    from . import bootstrap_roots
    allocation = bootstrap_roots.validate_grant(execution["bootstrap_allocation"],
        execution_id=execution["execution_id"], phase=execution["phase"], operation_id=execution["operation_id"])
    if execution["roots"] != allocation["roots"] or set(execution["writable"]) != set(allocation["paths"]):
        raise JobError("IO_UNCERTAIN", "Helper writable roots differ from their consumed allocation")
    for path, identity in allocation["paths"].items():
        descriptor = _root_descriptor(path, identity)
        os.close(descriptor)


def prepare(payload):
    """Create only allocation-owned files after independent supervision exists."""
    from . import bootstrap_roots, budget, runner
    if not isinstance(payload, dict):
        raise JobError("UNSUPPORTED", "Bootstrap payload shape is invalid")
    modern = set(payload) == {"version", "execution", "allocation", "observation"}
    if modern:
        if type(payload["version"]) is not int or payload["version"] != 2:
            raise JobError("UNSUPPORTED", "Unknown bootstrap observation envelope")
    elif set(payload) != {"execution", "allocation"}:
        raise JobError("UNSUPPORTED", "Bootstrap payload shape is invalid")
    execution, allocation = payload["execution"], payload["allocation"]
    if modern != ("quota_grant_digest" in execution):
        raise JobError("UNSUPPORTED", "Bootstrap observation version and binding differ")
    bootstrap_roots.validate_grant(allocation, execution_id=execution["execution_id"],
                                   phase=execution["phase"], operation_id=execution["operation_id"])
    budget.validate_grant(execution["budget_grant"], execution_id=execution["execution_id"],
                          phase=execution["phase"], budgets=execution["budgets"])
    runner._deadline_remaining((execution["budget_grant"], execution["phase_deadline_boottime_ns"]))
    if execution["roots"] != allocation["roots"] or set(execution["writable"]) != set(allocation["paths"]):
        raise JobError("UNSUPPORTED", "Bootstrap writable paths differ from their consumed allocation")
    if os.readlink("/proc/self/ns/mnt") == execution["parent_mount_namespace"]:
        raise JobError("UNSUPPORTED", "Bootstrap filesystem namespace is not isolated")
    if "ro" not in runner._mount_for("/")["options"].split(","):
        raise JobError("UNSUPPORTED", "Bootstrap root filesystem write fence is not active")
    if any(os.access(path, os.W_OK) for path in ("/tmp", "/var/tmp", "/dev/shm")):
        raise JobError("UNSUPPORTED", "Bootstrap fallback write path remains accessible")
    runner._verify_cgroup_limits(dict(execution, unit=execution["bootstrap_unit"],
        budgets=budget.substage_limits(execution["budget_grant"], "bootstrap",
            supervision_version=execution.get("supervision_version", 2))))
    descriptors = {}
    try:
        for path, identity in allocation["paths"].items():
            descriptors[path] = _root_descriptor(path, identity)
        if modern:
            from . import quota_bootstrap, quota_contract
            try:
                quotas = quota_bootstrap.observe(execution, allocation, payload["observation"], descriptors)
            except quota_contract.QuotaError as error:
                raise JobError("IO_UNCERTAIN", "Quota observation unresolved: " + error.code) from error
        else:
            quotas = {}
            for path in allocation["paths"]:
                limit = execution["budgets"]["temporary_bytes"] if path == execution["roots"]["temporary"] else execution["budgets"]["reservation_bytes"]
                quotas[path] = runner._verify_project_quota(path, limit, expected_identity=allocation["paths"][path])
            distinct = {(item["mount"]["source"], item["project_id"]): item["hard_bytes"] for item in quotas.values()}
            if sum(distinct.values()) > execution["budgets"]["reservation_bytes"]:
                raise JobError("UNSUPPORTED", "Combined hard quotas exceed the reserved peak capacity")
        marker = json.dumps({"version": 1, "allocation_id": allocation["allocation_id"],
                             "operation_id": allocation["operation_id"], "slot_id": allocation["slot_id"]},
                            sort_keys=True, separators=(",", ":")).encode()
        if modern:
            from . import quota_payload
            if quota_payload.requires_extended(payload):
                filesystem = os.fstatvfs(descriptors[execution["roots"]["evidence"]])
                quota_payload.check_final_artifact(payload, quotas, marker,
                    block_size=filesystem.f_frsize or filesystem.f_bsize)
        # Observe every fresh root before writing the first marker. Partial
        # marker publication is retained after failure and never silently reused.
        if allocation["fresh"]:
            for path in allocation["roots"].values():
                if os.listdir(descriptors[path]):
                    raise JobError("IO_UNCERTAIN", "A consumed fresh root is not empty")
        for path in allocation["roots"].values():
            parent = descriptors[path]
            flags = os.O_NOFOLLOW | (os.O_WRONLY | os.O_CREAT | os.O_EXCL if allocation["fresh"] else os.O_RDONLY)
            descriptor = os.open(".lh-bootstrap-owner.json", flags, 0o400, dir_fd=parent)
            try:
                if allocation["fresh"]:
                    with os.fdopen(descriptor, "wb", closefd=False) as stream:
                        stream.write(marker); stream.flush(); os.fsync(descriptor)
                    os.fsync(parent)
                else:
                    info = os.fstat(descriptor)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid() or os.read(descriptor, len(marker) + 1) != marker:
                        raise JobError("IO_UNCERTAIN", "Consumed root belongs to another allocation")
            finally: _close_all([descriptor], sys.exc_info()[1])
        execution = dict(execution, quota_observation=quotas, bootstrap_allocation=allocation)
        raw = json.dumps(execution, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        runner._deadline_remaining((execution["budget_grant"], execution["phase_deadline_boottime_ns"]))
        parent = descriptors[execution["roots"]["evidence"]]
        descriptor = os.open(plan_name(execution["execution_id"]), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o400, dir_fd=parent)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(raw); stream.flush(); os.fsync(descriptor)
            os.fsync(parent)
        finally: _close_all([descriptor], sys.exc_info()[1])
        for path, descriptor in descriptors.items():
            now = os.stat(path, follow_symlinks=False)
            held = os.fstat(descriptor)
            if (now.st_dev, now.st_ino) != (held.st_dev, held.st_ino):
                raise JobError("IO_UNCERTAIN", "Root binding changed during launch preparation")
        runner._deadline_remaining((execution["budget_grant"], execution["phase_deadline_boottime_ns"]))
        if modern:
            from . import quota_binding
            packet = quota_binding.frame(quotas)
            if os.write(1, packet) != len(packet):
                raise JobError("IO_UNCERTAIN", "Bootstrap receipt pipe is incomplete")
        return 0
    finally:
        _close_all(descriptors.values(), sys.exc_info()[1])
