"""Pure, versioned system-manager identity; no OS access or execution authority.

The protected fixture authenticates these fields separately. Merely decoding a
binding never authorizes a launch or turns a user-manager receipt into one.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
import re

from .contract import JobError, MAX_SAFE_INTEGER, REF_PATTERN, UUID_PATTERN

SCHEMA = "local-hand-manager-binding/v1"
SYSTEM_CONFIGURATION_KEYS = {"uid", "gid", "slice", "cgroup", "manager_binding"}


def _reject():
    raise JobError("IO_UNCERTAIN", "Original process manager identity is unresolved")


def _copy(value):
    if isinstance(value, Mapping):
        return {key: _copy(item) for key, item in value.items()}
    return value


def validate(value, *, authority_id=None, boot_id=None, parent=None):
    """Decode only the new system identity, optionally checking trusted pins."""
    value = _copy(value)
    if (type(value) is not dict or set(value) !=
            {"schema", "manager_kind", "authority_id", "boot_id", "parent"}
            or value["schema"] != SCHEMA or value["manager_kind"] != "system"):
        _reject()
    for key, pattern in (("authority_id", REF_PATTERN), ("boot_id", UUID_PATTERN)):
        if type(value[key]) is not str or re.fullmatch(pattern, value[key]) is None:
            _reject()
    pin = value["parent"]
    if type(pin) is not dict or set(pin) != {"path", "device", "inode"}:
        _reject()
    path = pin["path"]
    if (type(path) is not str or len(path) > 512 or
            re.fullmatch(r"/[a-z0-9][a-z0-9_]*\.slice/[a-z0-9][a-z0-9_-]*\.slice", path) is None):
        _reject()
    parsed = PurePosixPath(path)
    # systemd derives the parent from the hyphenated child name. A supplied
    # path must not pretend that an unrelated slice is nested here.
    stem = parsed.parent.name.removesuffix(".slice")
    leaf = parsed.name.removesuffix(".slice")
    if not leaf.startswith(stem + "-") or "-" in leaf[len(stem) + 1:]:
        _reject()
    for key, minimum in (("device", 0), ("inode", 1)):
        if type(pin[key]) is not int or not minimum <= pin[key] <= MAX_SAFE_INTEGER:
            _reject()
    if (authority_id is not None and value["authority_id"] != authority_id
            or boot_id is not None and value["boot_id"] != boot_id
            or parent is not None and pin != _copy(parent)):
        _reject()
    return value


def from_configuration(configuration, *, authority_id=None):
    """Return an explicit system binding; legacy configuration returns None."""
    if configuration is None:
        return None
    configuration = _copy(configuration)
    if type(configuration) is not dict:
        _reject()
    if "manager_binding" not in configuration:
        if "manager_kind" in configuration or "gid" in configuration:
            _reject()
        return None
    if set(configuration) != SYSTEM_CONFIGURATION_KEYS:
        _reject()
    value = validate(configuration["manager_binding"], authority_id=authority_id)
    if (configuration["cgroup"] != "/sys/fs/cgroup" + value["parent"]["path"]
            or configuration["slice"] != PurePosixPath(value["parent"]["path"]).name):
        _reject()
    for key in ("uid", "gid"):
        if type(configuration[key]) is not int or not 1 <= configuration[key] <= 2**32 - 2:
            _reject()
    return value


def check(expected, actual):
    """Reject missing, added or changed identity, including user/system swaps."""
    if expected is None:
        if actual is not None:
            _reject()
        return None
    expected = validate(expected)
    if actual is None or validate(actual) != expected:
        _reject()
    return expected
