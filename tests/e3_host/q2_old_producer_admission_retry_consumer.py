"""Narrow kernel observation consumer for the old-producer retry scope.

Only a mutually bound ``MANIFEST.json``, ``host-locator.json`` and
``host-context.json`` are accepted. After establishing the original dual
clock window and proving the fixed ordinary identity, the consumer invokes the
already-qualified kernel reader for exactly two facts: host boot ID and this
process' mountinfo. It cannot create state, connect to a guest, or make a
candidate field-ready.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path, PurePosixPath
import re
import time


def _load_companion(filename, module_name):
    source = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(
        "_old_producer_admission_retry_" + module_name, source)
    if spec is None or spec.loader is None:
        raise ValueError("OLD_PRODUCER_COMPANION_IMPORT")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract = _load_companion("q2_old_producer_admission_retry_contract.py", "contract")
kernel = _load_companion("q2_host_kernel_facts.py", "kernel_facts")

SCOPE = contract.SCOPE
RULE = contract.RULE
BASELINE = contract.BASELINE
CLOSURE = contract.CLOSURE
KERNEL_AUTHORITY = dict(contract.KERNEL_READER)
RESULT_SCHEMA = contract.CONSUMER_RESULT_SCHEMA
NS = 10**9
OUTER_NS = 300 * NS
PREPARATION_NS = 150 * NS
MOUNTINFO_LIMIT = 1024**2
_BOOT_BYTES = re.compile(
    rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\n")
_DEVICE = re.compile(r"[0-9]+:[0-9]+")
_ESCAPE = re.compile(r"\\(040|011|012|134)")
_NSFS_ROOT = re.compile(r"(?:cgroup|ipc|mnt|net|pid|time|user|uts):\[([1-9][0-9]*)\]")


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _current_identity():
    _require(all(hasattr(os, name) for name in ("getresuid", "getresgid", "getgroups")),
        "OLD_PRODUCER_IDENTITY_UNSUPPORTED")
    return contract.validate_operator({"schema": contract.OPERATOR_SCHEMA,
        "uid": list(os.getresuid()), "gid": list(os.getresgid()),
        "groups": sorted(os.getgroups())})


class _Window:
    def __init__(self):
        # The approved anchor is BOOTTIME-first, immediately followed by MONOTONIC.
        boot = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        mono = time.monotonic_ns()
        _require(type(boot) is int and type(mono) is int and 0 < boot < 2**63
            and 0 < mono < 2**63, "OLD_PRODUCER_CLOCK_FORMAT")
        self.boot_origin = self.last_boot = boot
        self.mono_origin = self.last_mono = mono

    def fields(self):
        return {
            "boottime_issued_ns": self.boot_origin,
            "monotonic_issued_ns": self.mono_origin,
            "boottime_outer_deadline_ns": self.boot_origin + OUTER_NS,
            "monotonic_outer_deadline_ns": self.mono_origin + OUTER_NS,
            "boottime_preparation_deadline_ns": self.boot_origin + PREPARATION_NS,
            "monotonic_preparation_deadline_ns": self.mono_origin + PREPARATION_NS,
        }

    def guard(self):
        # Post-anchor guards use the approved MONOTONIC then BOOTTIME order.
        mono = time.monotonic_ns()
        boot = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        _require(type(boot) is int and type(mono) is int,
            "OLD_PRODUCER_CLOCK_FORMAT")
        _require(boot >= self.last_boot and mono >= self.last_mono,
            "OLD_PRODUCER_CLOCK_ROLLBACK")
        _require(boot < self.boot_origin + PREPARATION_NS
            and mono < self.mono_origin + PREPARATION_NS
            and boot < self.boot_origin + OUTER_NS
            and mono < self.mono_origin + OUTER_NS,
            "OLD_PRODUCER_PREPARATION_EXPIRED")
        _require(abs((boot - self.boot_origin) - (mono - self.mono_origin)) <= 2 * NS,
            "OLD_PRODUCER_CLOCK_DIVERGED")
        self.last_boot, self.last_mono = boot, mono
        return {"boottime_ns": boot, "monotonic_ns": mono}


def _unescape(value):
    result = _ESCAPE.sub(lambda match: chr(int(match[1], 8)), value)
    _require("\\" not in result and "\0" not in result,
        "OLD_PRODUCER_MOUNTINFO_ESCAPE")
    return result


def _mount_path(value):
    parsed = PurePosixPath(value)
    _require(value.startswith("/") and not value.startswith("//")
        and ".." not in parsed.parts and str(parsed) == value,
        "OLD_PRODUCER_MOUNTINFO_PATH")
    return value


def _mount_root(value, filesystem):
    # Namespace dentries have a kernel name such as mnt:[4026531840], not a
    # filesystem path. This exception applies only to an nsfs row's root.
    if filesystem == "nsfs" and not value.startswith("/"):
        match = _NSFS_ROOT.fullmatch(value)
        _require(match is not None and len(match[1]) <= 19
            and int(match[1]) < 2**63, "OLD_PRODUCER_MOUNTINFO_NSFS_ROOT")
        return value
    return _mount_path(value)


def parse_mountinfo(raw):
    """Purely parse the one bounded mountinfo byte string returned by K."""
    _require(type(raw) is bytes and 0 < len(raw) <= MOUNTINFO_LIMIT
        and b"\0" not in raw and b"\r" not in raw,
        "OLD_PRODUCER_MOUNTINFO_BYTES")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise ValueError("OLD_PRODUCER_MOUNTINFO_UTF8") from None
    lines = text.splitlines()
    _require(lines and len(lines) <= 65536 and all(lines),
        "OLD_PRODUCER_MOUNTINFO_ROWS")
    rows, identifiers = [], set()
    for line in lines:
        fields = line.split(" ")
        _require(all(fields) and fields.count("-") == 1,
            "OLD_PRODUCER_MOUNTINFO_ROW")
        split = fields.index("-")
        _require(split >= 6 and len(fields) == split + 4
            and fields[0].isdigit() and fields[1].isdigit()
            and _DEVICE.fullmatch(fields[2]) is not None,
            "OLD_PRODUCER_MOUNTINFO_ROW")
        mount_id, parent_mount_id = int(fields[0]), int(fields[1])
        _require(0 < mount_id < 2**63 and 0 <= parent_mount_id < 2**63
            and mount_id not in identifiers, "OLD_PRODUCER_MOUNTINFO_ID")
        identifiers.add(mount_id)
        mount_options = fields[5].split(",")
        super_options = fields[split + 3].split(",")
        _require(all(mount_options) and all(super_options),
            "OLD_PRODUCER_MOUNTINFO_OPTIONS")
        rows.append({
            "mount_id": mount_id,
            "parent_mount_id": parent_mount_id,
            "device": fields[2],
            "root": _mount_root(_unescape(fields[3]), fields[split + 1]),
            "mountpoint": _mount_path(_unescape(fields[4])),
            "mount_options": mount_options,
            "optional_fields": fields[6:split],
            "filesystem": fields[split + 1],
            "source": _unescape(fields[split + 2]),
            "super_options": super_options,
        })
    return rows


def _containing_mount(rows, parent):
    matches = [row for row in rows if parent == row["mountpoint"]
        or parent.startswith(row["mountpoint"].rstrip("/") + "/")]
    _require(matches, "OLD_PRODUCER_MOUNT_NOT_FOUND")
    longest = max(len(row["mountpoint"]) for row in matches)
    selected = [row for row in matches if len(row["mountpoint"]) == longest]
    _require(len(selected) == 1, "OLD_PRODUCER_MOUNT_AMBIGUOUS")
    return dict(selected[0])


def observe(manifest_raw, locator_raw, context_raw, *, implementation_commit,
            implementation_tree):
    """Observe both fixed facts once, bound to independently pinned D/tree.

    The pins are supplied by the package/CI verifier rather than trusted from
    the manifest itself.  This function still cannot prove Git ancestry; that
    remains external qualification evidence recorded before packaging.
    """
    window = _Window()

    # These are in-memory package bytes. Their three-way binding is verified
    # before the first proc content read and no path is accepted separately.
    locator = contract.validate_locator(locator_raw)
    context = contract.validate_context(context_raw, locator_raw)
    manifest = contract.validate_manifest(
        contract.document(manifest_raw), locator_raw, context_raw,
        implementation_commit=implementation_commit,
        implementation_tree=implementation_tree)

    expected_identity = context["operator"]
    observed_identity = _current_identity()
    _require(observed_identity == expected_identity,
        "OLD_PRODUCER_IDENTITY_CONTEXT")

    def guard():
        sample = window.guard()
        _require(_current_identity() == observed_identity,
            "OLD_PRODUCER_IDENTITY_CHANGED")
        return sample

    reads = []
    guard()
    boot_detail = {}
    reads.append({"kind": "boot", "detail": boot_detail})
    boot_raw = kernel.read_fact("boot", guard, boot_detail)
    guard()
    _require(type(boot_raw) is bytes and len(boot_raw) <= 64
        and _BOOT_BYTES.fullmatch(boot_raw) is not None,
        "OLD_PRODUCER_BOOT_FORMAT")
    boot_id = boot_raw[:-1].decode("ascii")
    _require(boot_id == context["expected_host_boot_id"],
        "OLD_PRODUCER_BOOT_CHANGED")

    mount_detail = {}
    reads.append({"kind": "mountinfo", "detail": mount_detail})
    mount_raw = kernel.read_fact("mountinfo", guard, mount_detail)
    guard()
    mounts = parse_mountinfo(mount_raw)
    paths = {"consumption": locator["parent"]["path"],
        "evidence": context["evidence_parent"]["path"]}
    parents = {role: {"path": path,
        "containing_mount": _containing_mount(mounts, path),
        "filesystem_qualified": False,
        "peak_and_persistence_qualified": False}
        for role, path in paths.items()}
    return {
        "schema": RESULT_SCHEMA,
        "scope": SCOPE,
        "authority": {"rule": RULE, "baseline": BASELINE, "closure": CLOSURE,
            "implementation_commit": manifest["authority"]["implementation_commit"],
            "implementation_tree": manifest["authority"]["implementation_tree"],
            "kernel": dict(KERNEL_AUTHORITY)},
        "package_binding": {"manifest_sha256": contract.sha(manifest_raw),
            "locator_sha256": contract.sha(locator_raw),
            "context_sha256": contract.sha(context_raw)},
        "status": "OBSERVED_NOT_READY",
        "field_ready": False,
        "allow_run": False,
        "guest_executed": False,
        "remote_attempted": False,
        "host_persistence_attempted": False,
        "normal_chain_executions": 0,
        "window": window.fields(),
        "operator": observed_identity,
        "boot_id": boot_id,
        "parents": parents,
        "kernel_reads": reads,
        "namespace_alignment": {
            "status": contract.QUALIFICATIONS["namespace_alignment"],
            "required": "original_host_terminal_and_matching_pid_proc_namespaces",
        },
        "blockers": list(contract.BLOCKERS),
    }
