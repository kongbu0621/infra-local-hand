"""Bounded standalone G/R/O namespace-reference contract.

This module is deliberately test-only.  It contains no guest locator, caller
selected PID/path/command, product runner, or field-delivery entry point.  The
outer namespace fixture owns native process creation, cgroup supervision,
deadlines, stop/EOF evidence, and final qualification.  This component validates
the fixed G/R/O evidence and 15-packet exchange supplied through held interfaces.

The pure ``ReferenceEvidence`` boundary keeps procfs/nsfs acquisition separate
from protocol validation.  The field-facing Linux helpers inspect only an
already-held namespace fd or packet from an already-created anonymous socket.
The explicit ``run_synthetic_harness`` test entry additionally creates bounded
local anonymous sockets, pipe handles, and direct children, but never inspects
procfs/nsfs or claims those handles are namespaces; its fixture qualification is
always ``NOT_RUN``.  Nothing here enumerates processes, opens a caller path,
creates a persistent object, or connects to a network endpoint.
"""
from __future__ import annotations

import array
import ctypes
from dataclasses import dataclass, field
from enum import Enum
import errno
import fcntl
import hashlib
import json
import os
import re
import signal
import socket
import stat
import struct
import sys
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence


SCOPE = "LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1"
RULE = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
BASELINE = "ad5abaee642cba02d997149badf75a08c219a35c"
CLOSURE = "f5d60351c95c0276a95c7843215e02b0a69fdc3f"
OWNER_EVENT = "LH-Q2-NAMESPACE-FIXTURE-DELIVERY-CLOSURE-20261003-01"

CONTEXT_SCHEMA = "local-hand-q2-namespace-reference-context/v1"
FRAME_SCHEMA = "local-hand-q2-namespace-reference-frame/v1"
REPORT_SCHEMA = "local-hand-q2-namespace-reference-report/v1"
SYNTHETIC_HARNESS_SCHEMA = "local-hand-q2-namespace-synthetic-harness/v1"
BOOTSTRAP_READY_SCHEMA = "local-hand-q2-namespace-bootstrap-ready/v1"
G_GO_SCHEMA = "local-hand-q2-namespace-g-go/v1"
PURPOSE = "ISOLATED_NAMESPACE_FIXTURE"
CASE_IDS = tuple(f"N{number:02d}" for number in range(1, 13))

CONTEXT_BYTES_MAX = 16 * 1024
FRAME_BYTES_MAX = 4 * 1024
FRAME_COUNT = 15
FRAME_PAYLOAD_BYTES_MAX = 60 * 1024
STATUS_BYTES_MAX = 16 * 1024
STATUS_READS_MAX = 12
STATUS_BYTES_TOTAL_MAX = 192 * 1024
NAMESPACE_OPENS_MAX = 40
RANDOM_BYTES_EXACT = 64
STDOUT_BYTES_MAX = 32 * 1024
STDERR_BYTES_MAX = 8 * 1024
TASKS_EXACT = 3
MAX_SUPPLEMENTARY_GROUPS = 32
INSTALLED_FD_MAX = MappingProxyType({"G": 22, "R": 13, "O": 13})
INSTALLED_FD_TOTAL_MAX = 48
QUEUED_FD_MAX = 2
FD_REFERENCES_TOTAL_MAX = 50
SYNTHETIC_TIMEOUT_SECONDS = 5.0
SYNTHETIC_REAP_GRACE_SECONDS = 1.0
SYNTHETIC_RESULT_BYTES_MAX = 4 * 1024
SYNTHETIC_FAULTS = frozenset({"NONE", "STALE_SESSION", "EARLY_EXIT", "EXTRA_FRAME"})

PROC_SUPER_MAGIC = 0x9FA0
NSFS_MAGIC = 0x6E736673
CLONE_NEWNS = 0x00020000
CLONE_NEWPID = 0x20000000
# _IO(NSIO, 0x3); fixed by linux/uapi/linux/nsfs.h.
NS_GET_NSTYPE = 0xB703
_NAMESPACE_TYPES = MappingProxyType({"pid": CLONE_NEWPID, "mnt": CLONE_NEWNS})

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ERROR = re.compile(r"[A-Z][A-Z0-9_]{0,95}\Z")
_UCRED = struct.Struct("=3i")


class Outcome(str, Enum):
    """Typed outer outcomes from exact A.

    This standalone report may emit NOT_RUN/BLOCKED/UNKNOWN/FAILED.  It may not
    independently emit FIXTURE_LIVE_REFERENCE_MATCHED because outer stop, EOF,
    cgroup counters, accounting, and seals are intentionally outside this file.
    """

    NOT_RUN = "NOT_RUN"
    BLOCKED_RETAINED = "BLOCKED_RETAINED"
    UNKNOWN_RETAINED = "UNKNOWN_RETAINED"
    FAILED_RETAINED = "FAILED_RETAINED"
    FIXTURE_LIVE_REFERENCE_MATCHED = "FIXTURE_LIVE_REFERENCE_MATCHED"


class ComponentStatus(str, Enum):
    NOT_RUN = "NOT_RUN"
    REFERENCE_RELATION_MATCHED = "REFERENCE_RELATION_MATCHED"
    BLOCKED_RETAINED = "BLOCKED_RETAINED"
    UNKNOWN_RETAINED = "UNKNOWN_RETAINED"
    FAILED_RETAINED = "FAILED_RETAINED"


class ContractError(ValueError):
    """Fail-closed contract error carrying an exact typed outcome."""

    def __init__(self, code: str, outcome: Outcome = Outcome.BLOCKED_RETAINED):
        if not isinstance(code, str) or _ERROR.fullmatch(code) is None:
            raise ValueError("invalid contract error code")
        super().__init__(code)
        self.code = code
        self.outcome = outcome


def _fail(code: str, outcome: Outcome = Outcome.BLOCKED_RETAINED) -> None:
    raise ContractError(code, outcome)


def _keys(value: Any, expected: set[str], code: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != expected:
        _fail(code)
    return value


def _integer(value: Any, minimum: int, maximum: int, code: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(code)
    return value


def _text(value: Any, expected: str | None, code: str) -> str:
    if type(value) is not str or (expected is not None and value != expected):
        _fail(code)
    return value


def _digest(value: Any, code: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        _fail(code)
    return value


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if type(key) is not str or key in result:
            _fail("JSON_DUPLICATE_OR_NONSTRING_KEY")
        result[key] = value
    return result


def canonical(value: Any, limit: int) -> bytes:
    """Encode the deliberately small JSON subset used by the contract."""

    def check(item: Any) -> None:
        if item is None or type(item) in (bool, int, str):
            return
        if type(item) is list:
            for member in item:
                check(member)
            return
        if type(item) is dict:
            for key, member in item.items():
                if type(key) is not str:
                    _fail("JSON_NONSTRING_KEY")
                check(member)
            return
        _fail("JSON_TYPE")

    check(value)
    try:
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    except (UnicodeError, ValueError, TypeError):
        _fail("JSON_ENCODE")
    if not 0 < len(raw) <= limit:
        _fail("JSON_SIZE")
    return raw


def _decode_canonical(raw: bytes, limit: int, code: str) -> Mapping[str, Any]:
    if type(raw) is not bytes or not 0 < len(raw) <= limit:
        _fail(code + "_SIZE")
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(
            text,
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: _fail("JSON_NONFINITE"),
        )
    except ContractError:
        raise
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        _fail(code + "_JSON")
    if type(value) is not dict or canonical(value, limit) != raw:
        _fail(code + "_CANONICAL")
    return value


@dataclass(frozen=True, slots=True)
class Credential:
    pid: int
    uid: int
    gid: int

    def __post_init__(self) -> None:
        _integer(self.pid, 1, (1 << 31) - 1, "CREDENTIAL_PID")
        _integer(self.uid, 0, (1 << 32) - 2, "CREDENTIAL_UID")
        _integer(self.gid, 0, (1 << 32) - 2, "CREDENTIAL_GID")


@dataclass(frozen=True, slots=True)
class Context:
    case_id: str
    source_digest: str
    runtime_digest: str
    fixture_digest: str
    context_digest: str
    uid: int
    gid: int
    groups: tuple[int, ...]
    raw: bytes = field(repr=False)

    @property
    def credential_identity(self) -> tuple[int, int]:
        return self.uid, self.gid


def validate_context(
    raw: bytes,
    expected_digest: str | None = None,
    *,
    expected_identity: tuple[int, int, Sequence[int]] | None = None,
) -> Context:
    """Validate the only caller-supplied component input.

    No PID, path, command, fd, environment, namespace number, or caller-chosen
    deadline is present in this closed schema.  PIDs and clocks are bound later
    from the coordinator's direct fork and fixed clock source.
    """

    value = _decode_canonical(raw, CONTEXT_BYTES_MAX, "CONTEXT")
    _keys(
        value,
        {
            "schema",
            "scope",
            "purpose",
            "case_id",
            "source_digest",
            "runtime_digest",
            "fixture_digest",
            "ordinary",
        },
        "CONTEXT_KEYS",
    )
    _text(value["schema"], CONTEXT_SCHEMA, "CONTEXT_SCHEMA")
    _text(value["scope"], SCOPE, "CONTEXT_SCOPE")
    _text(value["purpose"], PURPOSE, "CONTEXT_PURPOSE")
    case_id = _text(value["case_id"], None, "CONTEXT_CASE")
    if case_id not in CASE_IDS:
        _fail("CONTEXT_CASE")
    source = _digest(value["source_digest"], "CONTEXT_SOURCE")
    runtime = _digest(value["runtime_digest"], "CONTEXT_RUNTIME")
    fixture = _digest(value["fixture_digest"], "CONTEXT_FIXTURE")
    ordinary = _keys(value["ordinary"], {"uid", "gid", "groups"}, "CONTEXT_ORDINARY")
    uid = _integer(ordinary["uid"], 1, (1 << 32) - 2, "CONTEXT_UID")
    gid = _integer(ordinary["gid"], 1, (1 << 32) - 2, "CONTEXT_GID")
    groups_value = ordinary["groups"]
    if (
        type(groups_value) is not list
        or len(groups_value) > MAX_SUPPLEMENTARY_GROUPS
    ):
        _fail("CONTEXT_GROUPS")
    groups = tuple(
        _integer(group, 1, (1 << 32) - 2, "CONTEXT_GROUP")
        for group in groups_value
    )
    # Preserve duplicates, but require one deterministic ordering.
    if groups != tuple(sorted(groups)):
        _fail("CONTEXT_GROUP_ORDER")
    actual_digest = hashlib.sha256(raw).hexdigest()
    if expected_digest is not None:
        if _digest(expected_digest, "CONTEXT_EXPECTED_DIGEST") != actual_digest:
            _fail("CONTEXT_DIGEST")
    if expected_identity is not None:
        if (
            type(expected_identity) is not tuple
            or len(expected_identity) != 3
            or (uid, gid, groups)
            != (
                expected_identity[0],
                expected_identity[1],
                tuple(expected_identity[2]),
            )
        ):
            _fail("CONTEXT_IDENTITY")
    return Context(case_id, source, runtime, fixture, actual_digest, uid, gid, groups, raw)


@dataclass(frozen=True, slots=True)
class StatusIdentity:
    pid: int
    threads: int
    nstgid: tuple[int, ...]
    nspid: tuple[int, ...]
    byte_count: int
    digest: str


def parse_status(raw: bytes, expected_pid: int) -> StatusIdentity:
    """Parse only the fixed namespace/single-thread fields from proc status."""

    _integer(expected_pid, 1, (1 << 31) - 1, "STATUS_EXPECTED_PID")
    if type(raw) is not bytes or not 0 < len(raw) <= STATUS_BYTES_MAX:
        _fail("STATUS_SIZE")
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError:
        _fail("STATUS_ENCODING")
    found: dict[str, tuple[int, ...]] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, payload = line.split(":", 1)
        if name not in {"Threads", "NStgid", "NSpid"}:
            continue
        if name in found:
            _fail("STATUS_DUPLICATE")
        tokens = payload.split()
        if not tokens or any(re.fullmatch(r"[1-9][0-9]*", token) is None for token in tokens):
            _fail("STATUS_INTEGER")
        numbers = tuple(int(token, 10) for token in tokens)
        if any(number > (1 << 31) - 1 for number in numbers):
            _fail("STATUS_INTEGER")
        found[name] = numbers
    if set(found) != {"Threads", "NStgid", "NSpid"}:
        _fail("STATUS_FIELDS")
    if found["Threads"] != (1,):
        _fail("STATUS_THREADS")
    if found["NStgid"] != (expected_pid,) or found["NSpid"] != (expected_pid,):
        _fail("STATUS_PID_VIEW")
    return StatusIdentity(
        expected_pid,
        1,
        found["NStgid"],
        found["NSpid"],
        len(raw),
        hashlib.sha256(raw).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class NamespaceIdentity:
    kind: str
    device: int
    inode: int
    namespace_type: int

    def __post_init__(self) -> None:
        if self.kind not in _NAMESPACE_TYPES:
            _fail("NAMESPACE_KIND")
        _integer(self.device, 0, (1 << 64) - 1, "NAMESPACE_DEVICE")
        _integer(self.inode, 1, (1 << 64) - 1, "NAMESPACE_INODE")
        if self.namespace_type != _NAMESPACE_TYPES[self.kind]:
            _fail("NAMESPACE_TYPE")

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "device": self.device,
            "inode": self.inode,
            "namespace_type": self.namespace_type,
        }


class _StatFS(ctypes.Structure):
    # Linux x86_64/LP64 struct statfs.  Use only after the exact platform gate.
    _fields_ = [
        ("f_type", ctypes.c_long),
        ("f_bsize", ctypes.c_long),
        ("f_blocks", ctypes.c_ulong),
        ("f_bfree", ctypes.c_ulong),
        ("f_bavail", ctypes.c_ulong),
        ("f_files", ctypes.c_ulong),
        ("f_ffree", ctypes.c_ulong),
        ("f_fsid", ctypes.c_int * 2),
        ("f_namelen", ctypes.c_long),
        ("f_frsize", ctypes.c_long),
        ("f_flags", ctypes.c_long),
        ("f_spare", ctypes.c_long * 4),
    ]


def _fstatfs_type(fd: int) -> int:
    if not sys.platform.startswith("linux") or struct.calcsize("P") != 8:
        _fail("FSTATFS_PLATFORM")
    libc = ctypes.CDLL(None, use_errno=True)
    function = libc.fstatfs
    function.argtypes = [ctypes.c_int, ctypes.POINTER(_StatFS)]
    function.restype = ctypes.c_int
    result = _StatFS()
    if function(fd, ctypes.byref(result)) != 0:
        error = ctypes.get_errno()
        raise ContractError("FSTATFS_FAILED") from OSError(error, os.strerror(error))
    return int(result.f_type)


def namespace_from_fd(fd: int, kind: str) -> NamespaceIdentity:
    """Qualify one already-held namespace handle; the caller retains ownership."""

    _integer(fd, 0, (1 << 31) - 1, "NAMESPACE_FD")
    if kind not in _NAMESPACE_TYPES:
        _fail("NAMESPACE_KIND")
    try:
        info = os.fstat(fd)
        if _fstatfs_type(fd) != NSFS_MAGIC:
            _fail("NAMESPACE_FS")
        namespace_type = fcntl.ioctl(fd, NS_GET_NSTYPE, 0)
    except ContractError:
        raise
    except (OSError, OverflowError, ValueError) as error:
        raise ContractError("NAMESPACE_QUERY") from error
    if not stat.S_ISREG(info.st_mode):
        _fail("NAMESPACE_MODE")
    return NamespaceIdentity(kind, info.st_dev, info.st_ino, namespace_type)


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    role: str
    credential: Credential
    groups: tuple[int, ...]
    status: StatusIdentity
    pid_namespace: NamespaceIdentity
    mnt_namespace: NamespaceIdentity
    generation: str

    def __post_init__(self) -> None:
        if self.role not in {"G", "R", "O"}:
            _fail("OBSERVATION_ROLE")
        if self.status.pid != self.credential.pid:
            _fail("OBSERVATION_PID")
        if self.pid_namespace.kind != "pid" or self.mnt_namespace.kind != "mnt":
            _fail("OBSERVATION_NAMESPACE_ROLE")
        _digest(self.generation, "OBSERVATION_GENERATION")
        if self.groups != tuple(sorted(self.groups)) or any(
            type(group) is not int or group < 0 for group in self.groups
        ):
            _fail("OBSERVATION_GROUPS")

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "pid": self.credential.pid,
            "ordinary": {
                "uid": self.credential.uid,
                "gid": self.credential.gid,
                "groups": list(self.groups),
            },
            "status_digest": self.status.digest,
            "status_bytes": self.status.byte_count,
            "pid_namespace": self.pid_namespace.as_dict(),
            "mnt_namespace": self.mnt_namespace.as_dict(),
            "generation": self.generation,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical(self.as_dict(), FRAME_BYTES_MAX)).hexdigest()


@dataclass(frozen=True, slots=True)
class ReferenceEvidence:
    """Held observations supplied by a fixed proc/ns acquisition layer.

    ``initial`` and ``rechecked`` are child self observations.  The coordinator
    maps are G's independent direct-child observations.  Keeping these sources
    separate prevents a child report from certifying itself.
    """

    initial: Mapping[str, ProcessObservation]
    rechecked: Mapping[str, ProcessObservation]
    coordinator_initial: Mapping[str, ProcessObservation]
    coordinator_rechecked: Mapping[str, ProcessObservation]
    pidfd_alive_initial: Mapping[str, bool]
    pidfd_alive_rechecked: Mapping[str, bool]
    namespace_open_count: int
    installed_fd_peak: Mapping[str, int]
    queued_fd_peak: int
    task_peak: int

    def validate(self, context: Context, pids: Mapping[str, int]) -> None:
        if set(pids) != {"G", "R", "O"}:
            _fail("EVIDENCE_PIDS")
        if len(set(pids.values())) != 3:
            _fail("EVIDENCE_PID_ALIAS")
        for mapping, keys, code in (
            (self.initial, {"G", "R", "O"}, "EVIDENCE_INITIAL"),
            (self.rechecked, {"G", "R", "O"}, "EVIDENCE_RECHECK"),
            (self.coordinator_initial, {"R", "O"}, "EVIDENCE_COORDINATOR_INITIAL"),
            (self.coordinator_rechecked, {"R", "O"}, "EVIDENCE_COORDINATOR_RECHECK"),
            (self.pidfd_alive_initial, {"R", "O"}, "EVIDENCE_PIDFD_INITIAL"),
            (self.pidfd_alive_rechecked, {"R", "O"}, "EVIDENCE_PIDFD_RECHECK"),
        ):
            if not isinstance(mapping, Mapping) or set(mapping) != keys:
                _fail(code)
        for phase in (self.initial, self.rechecked):
            for role in ("G", "R", "O"):
                observation = phase[role]
                if type(observation) is not ProcessObservation or observation.role != role:
                    _fail("EVIDENCE_ROLE")
                if observation.credential.pid != pids[role]:
                    _fail("EVIDENCE_PID")
                if (
                    observation.credential.uid,
                    observation.credential.gid,
                    observation.groups,
                ) != (context.uid, context.gid, context.groups):
                    _fail("EVIDENCE_ORDINARY_IDENTITY")
        for role in ("R", "O"):
            if self.pidfd_alive_initial[role] is not True or self.pidfd_alive_rechecked[role] is not True:
                _fail("EVIDENCE_PIDFD_NOT_ALIVE")
            for child, coordinator in (
                (self.initial[role], self.coordinator_initial[role]),
                (self.rechecked[role], self.coordinator_rechecked[role]),
            ):
                if coordinator.role != role or coordinator.credential.pid != pids[role]:
                    _fail("EVIDENCE_DIRECT_CHILD")
                if (
                    coordinator.credential.uid,
                    coordinator.credential.gid,
                    coordinator.groups,
                ) != (context.uid, context.gid, context.groups):
                    _fail("EVIDENCE_COORDINATOR_IDENTITY")
                if (
                    coordinator.status.threads != child.status.threads
                    or coordinator.status.nstgid != child.status.nstgid
                    or coordinator.status.nspid != child.status.nspid
                    or coordinator.pid_namespace != child.pid_namespace
                    or coordinator.mnt_namespace != child.mnt_namespace
                    or coordinator.generation != child.generation
                ):
                    _fail("EVIDENCE_CHILD_SOURCE_MISMATCH")
        for role in ("G", "R", "O"):
            first, second = self.initial[role], self.rechecked[role]
            if (
                first.credential != second.credential
                or first.groups != second.groups
                or first.pid_namespace != second.pid_namespace
                or first.mnt_namespace != second.mnt_namespace
                or first.generation != second.generation
            ):
                _fail("EVIDENCE_RECHECK_CHANGED")
        reference = self.initial["G"]
        for role in ("R", "O"):
            if self.initial[role].pid_namespace != reference.pid_namespace:
                _fail("EVIDENCE_PID_NAMESPACE_MISMATCH")
            if self.initial[role].mnt_namespace != reference.mnt_namespace:
                _fail("EVIDENCE_MNT_NAMESPACE_MISMATCH")
        _integer(
            self.namespace_open_count,
            20,
            NAMESPACE_OPENS_MAX,
            "EVIDENCE_NAMESPACE_OPENS",
        )
        if not isinstance(self.installed_fd_peak, Mapping) or set(self.installed_fd_peak) != {
            "G",
            "R",
            "O",
        }:
            _fail("EVIDENCE_FD_PEAKS")
        for role, maximum in INSTALLED_FD_MAX.items():
            _integer(
                self.installed_fd_peak[role],
                1,
                maximum,
                "EVIDENCE_FD_PEAK",
            )
        if sum(self.installed_fd_peak.values()) > INSTALLED_FD_TOTAL_MAX:
            _fail("EVIDENCE_FD_TOTAL")
        _integer(self.queued_fd_peak, 0, QUEUED_FD_MAX, "EVIDENCE_QUEUED_FD")
        if sum(self.installed_fd_peak.values()) + self.queued_fd_peak > FD_REFERENCES_TOTAL_MAX:
            _fail("EVIDENCE_FD_REFERENCES")
        if self.task_peak != TASKS_EXACT or type(self.task_peak) is not int:
            _fail("EVIDENCE_TASK_PEAK")

    def frozen_copy(self) -> "ReferenceEvidence":
        """Detach protocol state from caller-owned mutable dictionaries."""

        return ReferenceEvidence(
            MappingProxyType(dict(self.initial)),
            MappingProxyType(dict(self.rechecked)),
            MappingProxyType(dict(self.coordinator_initial)),
            MappingProxyType(dict(self.coordinator_rechecked)),
            MappingProxyType(dict(self.pidfd_alive_initial)),
            MappingProxyType(dict(self.pidfd_alive_rechecked)),
            self.namespace_open_count,
            MappingProxyType(dict(self.installed_fd_peak)),
            self.queued_fd_peak,
            self.task_peak,
        )


@dataclass(frozen=True, slots=True)
class FrameSpec:
    counter: int
    kind: str
    sender: str
    receiver: str
    rights: tuple[str, ...] = ()


FRAME_PLAN = (
    FrameSpec(1, "SETUP_R", "G", "R"),
    FrameSpec(2, "SOURCE_R", "R", "G", ("pid", "mnt")),
    FrameSpec(3, "SETUP_O", "G", "O"),
    FrameSpec(4, "SOURCE_O", "O", "G", ("pid", "mnt")),
    FrameSpec(5, "START_CHALLENGE", "G", "R"),
    FrameSpec(6, "CHALLENGE_A", "R", "O", ("pid", "mnt")),
    FrameSpec(7, "RESPONSE_A", "O", "R", ("pid", "mnt")),
    FrameSpec(8, "CHALLENGE_B", "O", "R"),
    FrameSpec(9, "RESPONSE_B", "R", "O"),
    FrameSpec(10, "ROUND1_RESULT", "R", "G"),
    FrameSpec(11, "ROUND1_RESULT", "O", "G"),
    FrameSpec(12, "RECHECK", "G", "R"),
    FrameSpec(13, "RECHECK", "G", "O"),
    FrameSpec(14, "ROUND2_RESULT", "R", "G"),
    FrameSpec(15, "ROUND2_RESULT", "O", "G"),
)


@dataclass(slots=True)
class CeilingAccount:
    frames: int = 0
    frame_bytes: int = 0
    status_reads: int = 0
    status_bytes: int = 0
    namespace_opens: int = 0
    random_bytes: int = 0
    tasks: int = 0
    installed_fd_peak: dict[str, int] = field(
        default_factory=lambda: {"G": 0, "R": 0, "O": 0}
    )
    queued_fd_peak: int = 0
    stdout_bytes: int = 0
    stderr_bytes: int = 0

    def add_frame(self, byte_count: int, rights_count: int) -> None:
        _integer(byte_count, 1, FRAME_BYTES_MAX, "CEILING_FRAME_BYTES")
        _integer(rights_count, 0, 2, "CEILING_FRAME_RIGHTS")
        self.frames += 1
        self.frame_bytes += byte_count
        self.queued_fd_peak = max(self.queued_fd_peak, rights_count)
        if self.frames > FRAME_COUNT or self.frame_bytes > FRAME_PAYLOAD_BYTES_MAX:
            _fail("CEILING_FRAMES")
        if self.queued_fd_peak > QUEUED_FD_MAX:
            _fail("CEILING_QUEUED_FD")

    def add_status(self, byte_count: int) -> None:
        _integer(byte_count, 1, STATUS_BYTES_MAX, "CEILING_STATUS_BYTES")
        self.status_reads += 1
        self.status_bytes += byte_count
        if self.status_reads > STATUS_READS_MAX or self.status_bytes > STATUS_BYTES_TOTAL_MAX:
            _fail("CEILING_STATUS")

    def add_namespace_opens(self, count: int) -> None:
        _integer(count, 0, NAMESPACE_OPENS_MAX, "CEILING_NAMESPACE_COUNT")
        self.namespace_opens += count
        if self.namespace_opens > NAMESPACE_OPENS_MAX:
            _fail("CEILING_NAMESPACE_OPENS")

    def add_random(self, count: int) -> None:
        _integer(count, 0, RANDOM_BYTES_EXACT, "CEILING_RANDOM_COUNT")
        self.random_bytes += count
        if self.random_bytes > RANDOM_BYTES_EXACT:
            _fail("CEILING_RANDOM")

    def observe_fd_peak(self, role: str, installed: int, queued: int = 0) -> None:
        if role not in INSTALLED_FD_MAX:
            _fail("CEILING_FD_ROLE")
        _integer(installed, 0, INSTALLED_FD_MAX[role], "CEILING_FD_INSTALLED")
        _integer(queued, 0, QUEUED_FD_MAX, "CEILING_FD_QUEUED")
        self.installed_fd_peak[role] = max(self.installed_fd_peak[role], installed)
        self.queued_fd_peak = max(self.queued_fd_peak, queued)
        if sum(self.installed_fd_peak.values()) > INSTALLED_FD_TOTAL_MAX:
            _fail("CEILING_FD_TOTAL")
        if sum(self.installed_fd_peak.values()) + self.queued_fd_peak > FD_REFERENCES_TOTAL_MAX:
            _fail("CEILING_FD_REFERENCES")

    def observe_tasks(self, count: int) -> None:
        _integer(count, 0, TASKS_EXACT, "CEILING_TASKS")
        self.tasks = max(self.tasks, count)

    def observe_output(self, stdout_bytes: int, stderr_bytes: int) -> None:
        _integer(stdout_bytes, 0, STDOUT_BYTES_MAX, "CEILING_STDOUT")
        _integer(stderr_bytes, 0, STDERR_BYTES_MAX, "CEILING_STDERR")
        self.stdout_bytes = max(self.stdout_bytes, stdout_bytes)
        self.stderr_bytes = max(self.stderr_bytes, stderr_bytes)

    def snapshot(self) -> dict[str, Any]:
        return {
            "frames": self.frames,
            "frame_bytes": self.frame_bytes,
            "status_reads": self.status_reads,
            "status_bytes": self.status_bytes,
            "namespace_opens": self.namespace_opens,
            "random_bytes": self.random_bytes,
            "tasks": self.tasks,
            "installed_fd_peak": dict(self.installed_fd_peak),
            "queued_fd_peak": self.queued_fd_peak,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
        }


def _observation_body(observation: ProcessObservation) -> dict[str, Any]:
    return {
        "observation": observation.as_dict(),
        "observation_digest": observation.digest,
    }


def _comparison_digest(
    role: str, own: ProcessObservation, peer: ProcessObservation, challenge: str
) -> str:
    value = {
        "domain": "local-hand-q2-namespace-reference-comparison/v1",
        "role": role,
        "own": own.digest,
        "peer": peer.digest,
        "challenge_digest": challenge,
    }
    return hashlib.sha256(canonical(value, FRAME_BYTES_MAX)).hexdigest()


def _challenge_digest(
    session_id: str,
    nonce_r: str,
    nonce_o: str,
    r_binding: str,
    o_binding: str,
) -> str:
    value = {
        "domain": "local-hand-q2-namespace-reference-challenge/v1",
        "session_id": session_id,
        "nonce_r": nonce_r,
        "nonce_o": nonce_o,
        "r_binding": r_binding,
        "o_binding": o_binding,
    }
    return hashlib.sha256(canonical(value, FRAME_BYTES_MAX)).hexdigest()


class ReferenceProtocol:
    """Strict central verifier for the fixed distributed G/R/O exchange."""

    def __init__(
        self,
        context: Context,
        evidence: ReferenceEvidence,
        *,
        g_pid: int,
        r_pid: int,
        o_pid: int,
        start_boottime_ns: int,
        start_monotonic_ns: int,
        deadline_boottime_ns: int,
        deadline_monotonic_ns: int,
        session_id: str | None = None,
    ):
        self.context = context
        self.pids = {"G": g_pid, "R": r_pid, "O": o_pid}
        for role, pid in self.pids.items():
            _integer(pid, 1, (1 << 31) - 1, "PROTOCOL_" + role + "_PID")
        for value, code in (
            (start_boottime_ns, "PROTOCOL_START_BOOTTIME"),
            (start_monotonic_ns, "PROTOCOL_START_MONOTONIC"),
            (deadline_boottime_ns, "PROTOCOL_DEADLINE_BOOTTIME"),
            (deadline_monotonic_ns, "PROTOCOL_DEADLINE_MONOTONIC"),
        ):
            _integer(value, 1, (1 << 63) - 1, code)
        if deadline_boottime_ns <= start_boottime_ns or deadline_monotonic_ns <= start_monotonic_ns:
            _fail("PROTOCOL_DEADLINE_ORDER")
        if (
            deadline_boottime_ns - start_boottime_ns > 20_000_000_000
            or deadline_monotonic_ns - start_monotonic_ns > 20_000_000_000
        ):
            _fail("PROTOCOL_DEADLINE_CEILING")
        evidence.validate(context, self.pids)
        self.evidence = evidence.frozen_copy()
        self.start_boottime_ns = start_boottime_ns
        self.start_monotonic_ns = start_monotonic_ns
        self.deadline_boottime_ns = deadline_boottime_ns
        self.deadline_monotonic_ns = deadline_monotonic_ns
        seed = {
            "domain": "local-hand-q2-namespace-reference-session/v1",
            "source_digest": context.source_digest,
            "runtime_digest": context.runtime_digest,
            "context_digest": context.context_digest,
            "fixture_digest": context.fixture_digest,
            "case_id": context.case_id,
            "g_pid": g_pid,
            "r_pid": r_pid,
            "o_pid": o_pid,
            "start_boottime_ns": start_boottime_ns,
            "start_monotonic_ns": start_monotonic_ns,
            "deadline_boottime_ns": deadline_boottime_ns,
            "deadline_monotonic_ns": deadline_monotonic_ns,
        }
        derived_session = hashlib.sha256(canonical(seed, CONTEXT_BYTES_MAX)).hexdigest()
        self.session_id = (
            derived_session
            if session_id is None
            else _digest(session_id, "PROTOCOL_SESSION")
        )
        self.deadline_binding = hashlib.sha256(
            canonical(
                {
                    "start_boottime_ns": start_boottime_ns,
                    "start_monotonic_ns": start_monotonic_ns,
                    "deadline_boottime_ns": deadline_boottime_ns,
                    "deadline_monotonic_ns": deadline_monotonic_ns,
                },
                FRAME_BYTES_MAX,
            )
        ).hexdigest()
        self.account = CeilingAccount()
        # Ten bounded observations: self G/R/O plus G's two child views, twice.
        for mapping in (
            self.evidence.initial,
            self.evidence.rechecked,
            self.evidence.coordinator_initial,
            self.evidence.coordinator_rechecked,
        ):
            for observation in mapping.values():
                self.account.add_status(observation.status.byte_count)
        self.account.add_namespace_opens(self.evidence.namespace_open_count)
        self.account.observe_tasks(self.evidence.task_peak)
        for role in ("G", "R", "O"):
            self.account.observe_fd_peak(
                role,
                self.evidence.installed_fd_peak[role],
                self.evidence.queued_fd_peak if role == "G" else 0,
            )
        self.counter = 0
        self.nonce_r: str | None = None
        self.nonce_o: str | None = None
        self.source_frame_digest: dict[str, str] = {}
        self.round1_frame_digest: dict[str, str] = {}
        self.challenge_digest: str | None = None
        self.frame_digests: list[str] = []

    @property
    def complete(self) -> bool:
        return self.counter == FRAME_COUNT

    def _expected_credential(self, role: str) -> Credential:
        return Credential(self.pids[role], self.context.uid, self.context.gid)

    def _challenge(self, nonce_r: str, nonce_o: str) -> str:
        return _challenge_digest(
            self.session_id,
            nonce_r,
            nonce_o,
            self.evidence.initial["R"].digest,
            self.evidence.initial["O"].digest,
        )

    def expected_body(self, nonce: bytes | None = None) -> dict[str, Any]:
        """Return the one permissible body for the next endpoint action.

        A nonce is accepted only at R's CHALLENGE_A or O's RESPONSE_A and must
        contain exactly 32 bytes.  There is no retry or replacement nonce.
        """

        if self.complete:
            _fail("PROTOCOL_ALREADY_COMPLETE")
        spec = FRAME_PLAN[self.counter]
        role = spec.sender
        if spec.counter == 1:
            return {
                "r_pid": self.pids["R"],
                "o_pid": self.pids["O"],
                "deadline_binding": self.deadline_binding,
            }
        if spec.counter == 2:
            return _observation_body(self.evidence.initial["R"])
        if spec.counter == 3:
            if "R" not in self.source_frame_digest:
                _fail("PROTOCOL_R_SOURCE_MISSING")
            return {
                "r_source_frame_digest": self.source_frame_digest["R"],
                "deadline_binding": self.deadline_binding,
            }
        if spec.counter == 4:
            return _observation_body(self.evidence.initial["O"])
        if spec.counter == 5:
            if set(self.source_frame_digest) != {"R", "O"}:
                _fail("PROTOCOL_SOURCE_MISSING")
            return {
                "r_source_frame_digest": self.source_frame_digest["R"],
                "o_source_frame_digest": self.source_frame_digest["O"],
            }
        if spec.counter == 6:
            if type(nonce) is not bytes or len(nonce) != 32 or self.nonce_r is not None:
                _fail("PROTOCOL_NONCE_R")
            return {"nonce_r": nonce.hex(), "own_digest": self.evidence.initial["R"].digest}
        if spec.counter == 7:
            if type(nonce) is not bytes or len(nonce) != 32 or self.nonce_o is not None:
                _fail("PROTOCOL_NONCE_O")
            if self.nonce_r is None or nonce.hex() == self.nonce_r:
                _fail("PROTOCOL_NONCE_INDEPENDENCE")
            return {
                "nonce_r": self.nonce_r,
                "nonce_o": nonce.hex(),
                "own_digest": self.evidence.initial["O"].digest,
            }
        if self.nonce_r is None or self.nonce_o is None or self.challenge_digest is None:
            _fail("PROTOCOL_NONCES_MISSING")
        common = {
            "nonce_r": self.nonce_r,
            "nonce_o": self.nonce_o,
            "challenge_digest": self.challenge_digest,
        }
        if spec.counter in (8, 9):
            peer = "O" if role == "R" else "R"
            return {
                **common,
                "own_digest": self.evidence.initial[role].digest,
                "peer_digest": self.evidence.initial[peer].digest,
            }
        if spec.counter in (10, 11):
            peer = "O" if role == "R" else "R"
            return {
                **common,
                "comparison_digest": _comparison_digest(
                    role,
                    self.evidence.initial[role],
                    self.evidence.initial[peer],
                    self.challenge_digest,
                ),
            }
        if spec.counter in (12, 13):
            target = spec.receiver
            if target not in self.round1_frame_digest:
                _fail("PROTOCOL_ROUND1_MISSING")
            return {
                "nonce_r": self.nonce_r,
                "nonce_o": self.nonce_o,
                "held_generation": self.evidence.initial[target].generation,
                "round1_frame_digest": self.round1_frame_digest[target],
            }
        if spec.counter in (14, 15):
            return {**common, **_observation_body(self.evidence.rechecked[role])}
        raise AssertionError(spec.counter)

    def encode_next(self, nonce: bytes | None = None) -> bytes:
        spec = FRAME_PLAN[self.counter]
        frame = {
            "schema": FRAME_SCHEMA,
            "kind": spec.kind,
            "sender": spec.sender,
            "receiver": spec.receiver,
            "counter": spec.counter,
            "session_id": self.session_id,
            "source_digest": self.context.source_digest,
            "runtime_digest": self.context.runtime_digest,
            "context_digest": self.context.context_digest,
            "body": self.expected_body(nonce),
        }
        return canonical(frame, FRAME_BYTES_MAX)

    def advance(
        self,
        raw: bytes,
        credential: Credential,
        rights: Sequence[NamespaceIdentity] = (),
    ) -> Mapping[str, Any]:
        if self.complete:
            _fail("PROTOCOL_EXTRA_FRAME")
        spec = FRAME_PLAN[self.counter]
        value = _decode_canonical(raw, FRAME_BYTES_MAX, "FRAME")
        _keys(
            value,
            {
                "schema",
                "kind",
                "sender",
                "receiver",
                "counter",
                "session_id",
                "source_digest",
                "runtime_digest",
                "context_digest",
                "body",
            },
            "FRAME_KEYS",
        )
        for key, expected, code in (
            ("schema", FRAME_SCHEMA, "FRAME_SCHEMA"),
            ("kind", spec.kind, "FRAME_KIND"),
            ("sender", spec.sender, "FRAME_SENDER"),
            ("receiver", spec.receiver, "FRAME_RECEIVER"),
            ("session_id", self.session_id, "FRAME_SESSION"),
            ("source_digest", self.context.source_digest, "FRAME_SOURCE"),
            ("runtime_digest", self.context.runtime_digest, "FRAME_RUNTIME"),
            ("context_digest", self.context.context_digest, "FRAME_CONTEXT"),
        ):
            _text(value[key], expected, code)
        if value["counter"] != spec.counter or type(value["counter"]) is not int:
            _fail("FRAME_COUNTER")
        if credential != self._expected_credential(spec.sender):
            _fail("FRAME_CREDENTIAL")
        if type(rights) not in (tuple, list) or len(rights) != len(spec.rights):
            _fail("FRAME_RIGHTS_COUNT")
        expected_observation = self.evidence.initial[spec.sender]
        for actual, kind in zip(rights, spec.rights, strict=True):
            if type(actual) is not NamespaceIdentity or actual.kind != kind:
                _fail("FRAME_RIGHTS_ROLE")
            expected = (
                expected_observation.pid_namespace
                if kind == "pid"
                else expected_observation.mnt_namespace
            )
            if actual != expected:
                _fail("FRAME_RIGHTS_OBJECT")

        supplied_nonce: bytes | None = None
        body = value["body"]
        if spec.counter == 6:
            if type(body) is not dict or type(body.get("nonce_r")) is not str:
                _fail("FRAME_BODY")
            try:
                supplied_nonce = bytes.fromhex(body["nonce_r"])
            except ValueError:
                _fail("FRAME_NONCE")
        elif spec.counter == 7:
            if type(body) is not dict or type(body.get("nonce_o")) is not str:
                _fail("FRAME_BODY")
            try:
                supplied_nonce = bytes.fromhex(body["nonce_o"])
            except ValueError:
                _fail("FRAME_NONCE")
        expected_body = self.expected_body(supplied_nonce)
        if body != expected_body:
            _fail("FRAME_BODY")

        frame_digest = hashlib.sha256(raw).hexdigest()
        self.account.add_frame(len(raw), len(rights))
        if spec.counter == 2:
            self.source_frame_digest["R"] = frame_digest
        elif spec.counter == 4:
            self.source_frame_digest["O"] = frame_digest
        elif spec.counter == 6:
            assert supplied_nonce is not None
            self.nonce_r = supplied_nonce.hex()
            self.account.add_random(32)
        elif spec.counter == 7:
            assert supplied_nonce is not None and self.nonce_r is not None
            self.nonce_o = supplied_nonce.hex()
            self.account.add_random(32)
            self.challenge_digest = self._challenge(self.nonce_r, self.nonce_o)
        elif spec.counter == 10:
            self.round1_frame_digest["R"] = frame_digest
        elif spec.counter == 11:
            self.round1_frame_digest["O"] = frame_digest
        self.frame_digests.append(frame_digest)
        self.counter += 1
        return value


@dataclass(frozen=True, slots=True)
class AncillaryPacket:
    payload: bytes
    credential: Credential
    fds: tuple[int, ...]


def _close_fds(fds: Sequence[int]) -> None:
    for fd in set(fds):
        try:
            os.close(fd)
        except OSError:
            pass


def validate_ancillary(
    ancillary: Sequence[tuple[int, int, bytes]],
    message_flags: int,
    *,
    expected_credential: Credential,
    expected_fd_count: int,
) -> tuple[int, ...]:
    """Validate SCM data and close every received right on any rejection."""

    _integer(expected_fd_count, 0, 2, "ANCILLARY_EXPECTED_FDS")
    received: list[int] = []
    credentials: list[Credential] = []
    rights_items = 0
    # Collect every complete descriptor number first.  Even a packet carrying
    # MSG_CTRUNC or an earlier unknown cmsg may already have installed rights
    # in this process; rejection must close them all.
    if type(ancillary) in (list, tuple):
        for level, kind, data in ancillary:
            if (
                level == socket.SOL_SOCKET
                and kind == socket.SCM_RIGHTS
                and type(data) is bytes
            ):
                values = array.array("i")
                usable = len(data) - len(data) % values.itemsize
                if usable:
                    values.frombytes(data[:usable])
                    received.extend(values.tolist())
    try:
        if type(ancillary) not in (list, tuple):
            _fail("ANCILLARY_TYPE")
        if message_flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            _fail("ANCILLARY_TRUNCATED")
        right_offset = 0
        for level, kind, data in ancillary:
            if level != socket.SOL_SOCKET or type(data) is not bytes:
                _fail("ANCILLARY_UNEXPECTED")
            if kind == socket.SCM_CREDENTIALS:
                if len(data) != _UCRED.size:
                    _fail("ANCILLARY_CREDENTIAL_SIZE")
                credentials.append(Credential(*_UCRED.unpack(data)))
            elif kind == socket.SCM_RIGHTS:
                rights_items += 1
                values = array.array("i")
                if len(data) == 0 or len(data) % values.itemsize:
                    _fail("ANCILLARY_RIGHTS_SIZE")
                values.frombytes(data)
                actual = values.tolist()
                if received[right_offset : right_offset + len(actual)] != actual:
                    _fail("ANCILLARY_RIGHTS_PARSE")
                right_offset += len(actual)
            else:
                _fail("ANCILLARY_UNEXPECTED")
        if right_offset != len(received):
            _fail("ANCILLARY_RIGHTS_PARSE")
        if credentials != [expected_credential]:
            _fail("ANCILLARY_CREDENTIAL")
        if len(received) != expected_fd_count:
            _fail("ANCILLARY_RIGHTS_COUNT")
        if rights_items != (1 if expected_fd_count else 0):
            _fail("ANCILLARY_RIGHTS_ITEMS")
        if len(set(received)) != len(received):
            _fail("ANCILLARY_RIGHTS_ALIAS")
        for fd in received:
            if os.get_inheritable(fd):
                _fail("ANCILLARY_RIGHTS_NOT_CLOEXEC")
        return tuple(received)
    except BaseException:
        _close_fds(received)
        raise


def enable_passcred(sock: socket.socket) -> None:
    if sock.family != socket.AF_UNIX or (sock.type & 0xF) != socket.SOCK_SEQPACKET:
        _fail("SOCKET_TYPE")
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    if sock.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) != 1:
        _fail("SOCKET_PASSCRED")


def _require_bounded_seqpacket(sock: socket.socket) -> None:
    timeout = sock.gettimeout()
    if (
        sock.family != socket.AF_UNIX
        or (sock.type & 0xF) != socket.SOCK_SEQPACKET
        or timeout is None
        or timeout < 0
        or timeout > SYNTHETIC_TIMEOUT_SECONDS
    ):
        _fail("SOCKET_NOT_BOUNDED_SEQPACKET")


def send_packet(sock: socket.socket, raw: bytes, fds: Sequence[int] = ()) -> None:
    _require_bounded_seqpacket(sock)
    if type(raw) is not bytes or not 0 < len(raw) <= FRAME_BYTES_MAX:
        _fail("SEND_SIZE")
    if type(fds) not in (tuple, list) or len(fds) not in (0, 2):
        _fail("SEND_RIGHTS_COUNT")
    ancillary: list[tuple[int, int, Any]] = []
    if fds:
        values = array.array("i")
        for fd in fds:
            _integer(fd, 0, (1 << 31) - 1, "SEND_FD")
            os.fstat(fd)
            values.append(fd)
        ancillary.append((socket.SOL_SOCKET, socket.SCM_RIGHTS, values))
    try:
        written = sock.sendmsg([raw], ancillary)
    except OSError as error:
        raise ContractError("SEND_FAILED", Outcome.UNKNOWN_RETAINED) from error
    if written != len(raw):
        _fail("SEND_PARTIAL", Outcome.UNKNOWN_RETAINED)


def receive_packet(
    sock: socket.socket,
    *,
    expected_credential: Credential,
    expected_fd_count: int,
) -> AncillaryPacket:
    """Receive one bounded packet; returned fds are owned by the caller."""

    _require_bounded_seqpacket(sock)
    ancillary_size = socket.CMSG_SPACE(_UCRED.size) + socket.CMSG_SPACE(
        2 * array.array("i").itemsize
    )
    try:
        payload, ancillary, flags, _ = sock.recvmsg(
            FRAME_BYTES_MAX + 1, ancillary_size, socket.MSG_CMSG_CLOEXEC
        )
    except OSError as error:
        raise ContractError("RECEIVE_FAILED", Outcome.UNKNOWN_RETAINED) from error
    if not payload:
        _fail("RECEIVE_EOF", Outcome.UNKNOWN_RETAINED)
    if len(payload) > FRAME_BYTES_MAX:
        # The kernel may report MSG_TRUNC or return the requested +1 bytes.
        provisional: list[int] = []
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                values = array.array("i")
                usable = len(data) - len(data) % values.itemsize
                values.frombytes(data[:usable])
                provisional.extend(values.tolist())
        _close_fds(provisional)
        _fail("RECEIVE_SIZE")
    fds = validate_ancillary(
        ancillary,
        flags,
        expected_credential=expected_credential,
        expected_fd_count=expected_fd_count,
    )
    return AncillaryPacket(payload, expected_credential, fds)


def receive_and_advance(
    sock: socket.socket,
    protocol: ReferenceProtocol,
    inspect_namespace: Callable[[int, str], NamespaceIdentity] = namespace_from_fd,
) -> Mapping[str, Any]:
    if protocol.complete:
        _fail("PROTOCOL_EXTRA_FRAME")
    spec = FRAME_PLAN[protocol.counter]
    packet = receive_packet(
        sock,
        expected_credential=protocol._expected_credential(spec.sender),
        expected_fd_count=len(spec.rights),
    )
    try:
        identities = tuple(
            inspect_namespace(fd, kind)
            for fd, kind in zip(packet.fds, spec.rights, strict=True)
        )
        return protocol.advance(packet.payload, packet.credential, identities)
    finally:
        _close_fds(packet.fds)


def build_report(
    protocol: ReferenceProtocol,
    *,
    reason: str = "OUTER_FIXTURE_EVIDENCE_NOT_PROVEN",
) -> bytes:
    """Build a standalone receipt that deliberately leaves fixture success NOT_RUN."""

    if _ERROR.fullmatch(reason) is None:
        _fail("REPORT_REASON")
    component = (
        ComponentStatus.REFERENCE_RELATION_MATCHED
        if protocol.complete
        else ComponentStatus.BLOCKED_RETAINED
    )
    def value() -> dict[str, Any]:
        return {
            "schema": REPORT_SCHEMA,
            "scope": SCOPE,
            "case_id": protocol.context.case_id,
            "source_digest": protocol.context.source_digest,
            "runtime_digest": protocol.context.runtime_digest,
            "fixture_digest": protocol.context.fixture_digest,
            "context_digest": protocol.context.context_digest,
            "session_id": protocol.session_id,
            "component_status": component.value,
            "fixture_qualification": Outcome.NOT_RUN.value,
            "reason": reason,
            "protocol": {
                "complete": protocol.complete,
                "frame_chain_digest": hashlib.sha256(
                    canonical(protocol.frame_digests, CONTEXT_BYTES_MAX)
                ).hexdigest(),
                **protocol.account.snapshot(),
            },
            "relations": {
                "direct_children": True,
                "pidfd_live_rechecked": True,
                "pid_namespace_matched": True,
                "mnt_namespace_matched": True,
                "credentials_matched": protocol.complete,
                "nonces_matched": protocol.complete,
            },
            "readiness": {
                "field_ready": False,
                "allow_run": False,
                "consumer_namespace_admitted": False,
                "normal_chain_executions": 0,
            },
        }

    # The report itself is G stdout.  Iterate until the decimal byte-count
    # field and the encoded length reach a fixed point (normally one pass).
    raw = canonical(value(), STDOUT_BYTES_MAX)
    for _ in range(3):
        protocol.account.observe_output(len(raw), 0)
        updated = canonical(value(), STDOUT_BYTES_MAX)
        if len(updated) == len(raw):
            return updated
        raw = updated
    _fail("REPORT_SIZE_FIXED_POINT")


def validate_report(
    raw: bytes,
    context: Context,
    *,
    expected_session_id: str,
    expected_frame_chain_digest: str,
    expected_account: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Validate a report against the receiver's current protocol commitments.

    Shape-only validation is insufficient: a canonical report from an old
    session has the same context pins.  The receiver must therefore supply the
    expected session, completed frame-chain digest, and exact local ceiling
    account obtained from the current held protocol.
    """

    expected_session = _digest(expected_session_id, "REPORT_EXPECTED_SESSION")
    expected_chain = _digest(
        expected_frame_chain_digest, "REPORT_EXPECTED_FRAME_CHAIN"
    )
    account_fields = {
        "frames",
        "frame_bytes",
        "status_reads",
        "status_bytes",
        "namespace_opens",
        "random_bytes",
        "tasks",
        "installed_fd_peak",
        "queued_fd_peak",
        "stdout_bytes",
        "stderr_bytes",
    }
    expected_account_value = _keys(
        expected_account, account_fields, "REPORT_EXPECTED_ACCOUNT_KEYS"
    )
    expected_account_raw = canonical(dict(expected_account_value), CONTEXT_BYTES_MAX)
    value = _decode_canonical(raw, STDOUT_BYTES_MAX, "REPORT")
    _keys(
        value,
        {
            "schema",
            "scope",
            "case_id",
            "source_digest",
            "runtime_digest",
            "fixture_digest",
            "context_digest",
            "session_id",
            "component_status",
            "fixture_qualification",
            "reason",
            "protocol",
            "relations",
            "readiness",
        },
        "REPORT_KEYS",
    )
    for key, expected, code in (
        ("schema", REPORT_SCHEMA, "REPORT_SCHEMA"),
        ("scope", SCOPE, "REPORT_SCOPE"),
        ("case_id", context.case_id, "REPORT_CASE"),
        ("source_digest", context.source_digest, "REPORT_SOURCE"),
        ("runtime_digest", context.runtime_digest, "REPORT_RUNTIME"),
        ("fixture_digest", context.fixture_digest, "REPORT_FIXTURE"),
        ("context_digest", context.context_digest, "REPORT_CONTEXT"),
        ("fixture_qualification", Outcome.NOT_RUN.value, "REPORT_QUALIFICATION"),
    ):
        _text(value[key], expected, code)
    if _digest(value["session_id"], "REPORT_SESSION") != expected_session:
        _fail("REPORT_SESSION_BINDING")
    component = _text(value["component_status"], None, "REPORT_COMPONENT_STATUS")
    if component not in {member.value for member in ComponentStatus}:
        _fail("REPORT_COMPONENT_STATUS")
    reason = _text(value["reason"], None, "REPORT_REASON")
    if _ERROR.fullmatch(reason) is None:
        _fail("REPORT_REASON")
    protocol = _keys(
        value["protocol"],
        {
            "complete",
            "frame_chain_digest",
            "frames",
            "frame_bytes",
            "status_reads",
            "status_bytes",
            "namespace_opens",
            "random_bytes",
            "tasks",
            "installed_fd_peak",
            "queued_fd_peak",
            "stdout_bytes",
            "stderr_bytes",
        },
        "REPORT_PROTOCOL_KEYS",
    )
    if type(protocol["complete"]) is not bool:
        _fail("REPORT_COMPLETE")
    if _digest(protocol["frame_chain_digest"], "REPORT_FRAME_CHAIN") != expected_chain:
        _fail("REPORT_FRAME_CHAIN_BINDING")
    for key, maximum in (
        ("frames", FRAME_COUNT),
        ("frame_bytes", FRAME_PAYLOAD_BYTES_MAX),
        ("status_reads", STATUS_READS_MAX),
        ("status_bytes", STATUS_BYTES_TOTAL_MAX),
        ("namespace_opens", NAMESPACE_OPENS_MAX),
        ("random_bytes", RANDOM_BYTES_EXACT),
        ("tasks", TASKS_EXACT),
        ("queued_fd_peak", QUEUED_FD_MAX),
        ("stdout_bytes", STDOUT_BYTES_MAX),
        ("stderr_bytes", STDERR_BYTES_MAX),
    ):
        _integer(protocol[key], 0, maximum, "REPORT_" + key.upper())
    if protocol["stdout_bytes"] != len(raw):
        _fail("REPORT_STDOUT_ACCOUNTING")
    peaks = _keys(protocol["installed_fd_peak"], {"G", "R", "O"}, "REPORT_FD_PEAK_KEYS")
    for role, maximum in INSTALLED_FD_MAX.items():
        _integer(peaks[role], 0, maximum, "REPORT_FD_PEAK")
    if sum(peaks.values()) > INSTALLED_FD_TOTAL_MAX:
        _fail("REPORT_FD_TOTAL")
    if sum(peaks.values()) + protocol["queued_fd_peak"] > FD_REFERENCES_TOTAL_MAX:
        _fail("REPORT_FD_REFERENCES")
    observed_account = {key: protocol[key] for key in account_fields}
    if canonical(observed_account, CONTEXT_BYTES_MAX) != expected_account_raw:
        _fail("REPORT_ACCOUNT_BINDING")
    if protocol["complete"]:
        if (
            protocol["frames"] != FRAME_COUNT
            or protocol["random_bytes"] != RANDOM_BYTES_EXACT
            or protocol["tasks"] != TASKS_EXACT
            or component != ComponentStatus.REFERENCE_RELATION_MATCHED.value
        ):
            _fail("REPORT_COMPLETE_CONSISTENCY")
    relations = _keys(
        value["relations"],
        {
            "direct_children",
            "pidfd_live_rechecked",
            "pid_namespace_matched",
            "mnt_namespace_matched",
            "credentials_matched",
            "nonces_matched",
        },
        "REPORT_RELATION_KEYS",
    )
    if any(type(item) is not bool for item in relations.values()):
        _fail("REPORT_RELATION_TYPE")
    if protocol["complete"] and not all(relations.values()):
        _fail("REPORT_RELATION_INCOMPLETE")
    readiness = _keys(
        value["readiness"],
        {
            "field_ready",
            "allow_run",
            "consumer_namespace_admitted",
            "normal_chain_executions",
        },
        "REPORT_READINESS_KEYS",
    )
    if (
        readiness["field_ready"] is not False
        or readiness["allow_run"] is not False
        or readiness["consumer_namespace_admitted"] is not False
        or readiness["normal_chain_executions"] != 0
        or type(readiness["normal_chain_executions"]) is not int
    ):
        _fail("REPORT_READINESS")
    return value


# ---------------------------------------------------------------------------
# Test-only executable G/R/O transport harness.
#
# This exercises real direct forks, AF_UNIX/SOCK_SEQPACKET credentials,
# SCM_RIGHTS installation/closure, the fixed 15-frame ordering, EOF, and wait.
# It deliberately substitutes anonymous handles for procfs/nsfs handles and
# therefore always leaves the fixture qualification NOT_RUN.


def _encode_reference_frame(
    context: Context, session_id: str, spec: FrameSpec, body: Mapping[str, Any]
) -> bytes:
    return canonical(
        {
            "schema": FRAME_SCHEMA,
            "kind": spec.kind,
            "sender": spec.sender,
            "receiver": spec.receiver,
            "counter": spec.counter,
            "session_id": session_id,
            "source_digest": context.source_digest,
            "runtime_digest": context.runtime_digest,
            "context_digest": context.context_digest,
            "body": dict(body),
        },
        FRAME_BYTES_MAX,
    )


def _decode_reference_frame(
    raw: bytes, context: Context, session_id: str, spec: FrameSpec
) -> Mapping[str, Any]:
    value = _decode_canonical(raw, FRAME_BYTES_MAX, "FRAME")
    _keys(
        value,
        {
            "schema",
            "kind",
            "sender",
            "receiver",
            "counter",
            "session_id",
            "source_digest",
            "runtime_digest",
            "context_digest",
            "body",
        },
        "FRAME_KEYS",
    )
    for key, expected, code in (
        ("schema", FRAME_SCHEMA, "FRAME_SCHEMA"),
        ("kind", spec.kind, "FRAME_KIND"),
        ("sender", spec.sender, "FRAME_SENDER"),
        ("receiver", spec.receiver, "FRAME_RECEIVER"),
        ("session_id", session_id, "FRAME_SESSION"),
        ("source_digest", context.source_digest, "FRAME_SOURCE"),
        ("runtime_digest", context.runtime_digest, "FRAME_RUNTIME"),
        ("context_digest", context.context_digest, "FRAME_CONTEXT"),
    ):
        _text(value[key], expected, code)
    if type(value["counter"]) is not int or value["counter"] != spec.counter:
        _fail("FRAME_COUNTER")
    if type(value["body"]) is not dict:
        _fail("FRAME_BODY")
    return value


def _anonymous_identity(fd: int, kind: str) -> NamespaceIdentity:
    """Describe one anonymous synthetic right without claiming nsfs."""

    _integer(fd, 0, (1 << 31) - 1, "SYNTHETIC_FD")
    if kind not in _NAMESPACE_TYPES:
        _fail("NAMESPACE_KIND")
    try:
        info = os.fstat(fd)
    except OSError as error:
        raise ContractError("SYNTHETIC_FD_QUERY") from error
    return NamespaceIdentity(kind, info.st_dev, info.st_ino, _NAMESPACE_TYPES[kind])


def _synthetic_observation(
    role: str,
    pid: int,
    context: Context,
    pid_handle: int,
    mnt_handle: int,
) -> ProcessObservation:
    status_raw = (
        f"Name:\tq2-synthetic-{role}\nThreads:\t1\n"
        f"NStgid:\t{pid}\nNSpid:\t{pid}\n"
    ).encode("ascii")
    pid_identity = _anonymous_identity(pid_handle, "pid")
    mnt_identity = _anonymous_identity(mnt_handle, "mnt")
    generation = hashlib.sha256(
        canonical(
            {
                "domain": "local-hand-q2-namespace-synthetic-generation/v1",
                "role": role,
                "pid": pid,
                "context_digest": context.context_digest,
                "pid_object": pid_identity.as_dict(),
                "mnt_object": mnt_identity.as_dict(),
            },
            FRAME_BYTES_MAX,
        )
    ).hexdigest()
    return ProcessObservation(
        role,
        Credential(pid, context.uid, context.gid),
        context.groups,
        parse_status(status_raw, pid),
        pid_identity,
        mnt_identity,
        generation,
    )


def _synthetic_evidence(
    context: Context,
    pids: Mapping[str, int],
    pid_handle: int,
    mnt_handle: int,
) -> ReferenceEvidence:
    first = {
        role: _synthetic_observation(role, pids[role], context, pid_handle, mnt_handle)
        for role in ("G", "R", "O")
    }
    second = dict(first)
    return ReferenceEvidence(
        first,
        second,
        {"R": first["R"], "O": first["O"]},
        {"R": second["R"], "O": second["O"]},
        {"R": True, "O": True},
        {"R": True, "O": True},
        20,
        {"G": 22, "R": 13, "O": 13},
        2,
        3,
    )


def _new_anonymous_handle() -> int:
    try:
        if hasattr(os, "pipe2"):
            read_fd, write_fd = os.pipe2(getattr(os, "O_CLOEXEC", 0))
        else:
            read_fd, write_fd = os.pipe()
            os.set_inheritable(read_fd, False)
            os.set_inheritable(write_fd, False)
        os.close(write_fd)
        return read_fd
    except OSError as error:
        raise ContractError("SYNTHETIC_HANDLE_CREATE") from error


def _close_socket(sock: socket.socket | None) -> None:
    if sock is not None:
        try:
            sock.close()
        except OSError:
            pass


def _fd_is_closed(fd: int) -> bool:
    try:
        os.fstat(fd)
    except OSError as error:
        return error.errno == errno.EBADF
    return False


def _synthetic_transport_available() -> bool:
    """Probe the exact anonymous credential/right transport before forking."""

    endpoints: list[socket.socket] = []
    handles: list[int] = []
    received: tuple[int, ...] = ()
    try:
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        endpoints.extend((left, right))
        for endpoint in endpoints:
            endpoint.settimeout(SYNTHETIC_TIMEOUT_SECONDS)
            enable_passcred(endpoint)
        handles.extend((_new_anonymous_handle(), _new_anonymous_handle()))
        send_packet(left, b'{"probe":"q2-synthetic-transport"}', handles)
        packet = receive_packet(
            right,
            expected_credential=Credential(os.getpid(), os.getuid(), os.getgid()),
            expected_fd_count=2,
        )
        received = packet.fds
        return packet.payload == b'{"probe":"q2-synthetic-transport"}'
    except (OSError, ContractError):
        return False
    finally:
        _close_fds(received)
        _close_fds(handles)
        for endpoint in endpoints:
            _close_socket(endpoint)


def _send_seqpacket(sock: socket.socket, raw: bytes, maximum: int, code: str) -> None:
    _require_bounded_seqpacket(sock)
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        _fail(code + "_SIZE")
    try:
        written = sock.send(raw)
    except OSError as error:
        raise ContractError(code + "_SEND", Outcome.UNKNOWN_RETAINED) from error
    if written != len(raw):
        _fail(code + "_PARTIAL", Outcome.UNKNOWN_RETAINED)


def _receive_seqpacket(sock: socket.socket, maximum: int, code: str) -> bytes:
    _require_bounded_seqpacket(sock)
    try:
        raw = sock.recv(maximum + 1)
    except OSError as error:
        raise ContractError(code + "_RECEIVE", Outcome.UNKNOWN_RETAINED) from error
    if not raw:
        _fail(code + "_EOF", Outcome.UNKNOWN_RETAINED)
    if len(raw) > maximum:
        _fail(code + "_SIZE")
    return raw


def _expect_eof(sock: socket.socket, code: str) -> None:
    _require_bounded_seqpacket(sock)
    try:
        raw = sock.recv(FRAME_BYTES_MAX + 1)
    except OSError as error:
        raise ContractError(code + "_RECEIVE", Outcome.UNKNOWN_RETAINED) from error
    if raw:
        _fail(code + "_EXTRA_FRAME")


def _receive_endpoint_frame(
    sock: socket.socket,
    context: Context,
    session_id: str,
    spec: FrameSpec,
    sender_pid: int,
) -> tuple[Mapping[str, Any], tuple[NamespaceIdentity, ...]]:
    packet = receive_packet(
        sock,
        expected_credential=Credential(sender_pid, context.uid, context.gid),
        expected_fd_count=len(spec.rights),
    )
    try:
        identities = tuple(
            _anonymous_identity(fd, kind)
            for fd, kind in zip(packet.fds, spec.rights, strict=True)
        )
        return (
            _decode_reference_frame(packet.payload, context, session_id, spec),
            identities,
        )
    finally:
        _close_fds(packet.fds)


def _require_body(value: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    if value["body"] != dict(expected):
        _fail("FRAME_BODY")


def _nonce(value: Any, code: str) -> bytes:
    text = _digest(value, code)
    return bytes.fromhex(text)


def _child_finish(control: socket.socket, cross: socket.socket) -> None:
    _expect_eof(control, "SYNTHETIC_CONTROL")
    try:
        cross.shutdown(socket.SHUT_WR)
    except OSError as error:
        raise ContractError("SYNTHETIC_CROSS_SHUTDOWN", Outcome.UNKNOWN_RETAINED) from error
    _expect_eof(cross, "SYNTHETIC_CROSS")


def _run_synthetic_r(
    control: socket.socket,
    cross: socket.socket,
    context: Context,
    session_id: str,
    g_pid: int,
    deadline_binding: str,
    pid_handle: int,
    mnt_handle: int,
    fault: str,
) -> int:
    try:
        r_pid = os.getpid()
        own = _synthetic_observation("R", r_pid, context, pid_handle, mnt_handle)
        setup, rights = _receive_endpoint_frame(
            control, context, session_id, FRAME_PLAN[0], g_pid
        )
        if rights:
            _fail("SYNTHETIC_SETUP_RIGHTS")
        body = _keys(
            setup["body"], {"r_pid", "o_pid", "deadline_binding"}, "FRAME_BODY"
        )
        if body["r_pid"] != r_pid or type(body["o_pid"]) is not int:
            _fail("SYNTHETIC_SETUP_PID")
        o_pid = _integer(body["o_pid"], 1, (1 << 31) - 1, "SYNTHETIC_O_PID")
        if o_pid == r_pid or body["deadline_binding"] != deadline_binding:
            _fail("SYNTHETIC_SETUP_BINDING")
        if fault == "EARLY_EXIT":
            return 71

        source_raw = _encode_reference_frame(
            context, session_id, FRAME_PLAN[1], _observation_body(own)
        )
        if fault == "STALE_SESSION":
            stale = "0" * 64 if session_id != "0" * 64 else "1" * 64
            source_value = dict(_decode_canonical(source_raw, FRAME_BYTES_MAX, "FRAME"))
            source_value["session_id"] = stale
            source_raw = canonical(source_value, FRAME_BYTES_MAX)
        send_packet(control, source_raw, (pid_handle, mnt_handle))
        r_source_digest = hashlib.sha256(source_raw).hexdigest()

        start, rights = _receive_endpoint_frame(
            control, context, session_id, FRAME_PLAN[4], g_pid
        )
        if rights:
            _fail("SYNTHETIC_START_RIGHTS")
        start_body = _keys(
            start["body"],
            {"r_source_frame_digest", "o_source_frame_digest"},
            "FRAME_BODY",
        )
        if start_body["r_source_frame_digest"] != r_source_digest:
            _fail("SYNTHETIC_R_SOURCE_BINDING")
        _digest(start_body["o_source_frame_digest"], "SYNTHETIC_O_SOURCE_DIGEST")

        nonce_r = os.getrandom(32)
        frame6 = _encode_reference_frame(
            context,
            session_id,
            FRAME_PLAN[5],
            {"nonce_r": nonce_r.hex(), "own_digest": own.digest},
        )
        send_packet(cross, frame6, (pid_handle, mnt_handle))

        response_a, peer_rights = _receive_endpoint_frame(
            cross, context, session_id, FRAME_PLAN[6], o_pid
        )
        peer = _synthetic_observation("O", o_pid, context, pid_handle, mnt_handle)
        if peer_rights != (peer.pid_namespace, peer.mnt_namespace):
            _fail("SYNTHETIC_PEER_RIGHTS")
        response_body = _keys(
            response_a["body"], {"nonce_r", "nonce_o", "own_digest"}, "FRAME_BODY"
        )
        nonce_o = _nonce(response_body["nonce_o"], "SYNTHETIC_NONCE_O")
        _require_body(
            response_a,
            {"nonce_r": nonce_r.hex(), "nonce_o": nonce_o.hex(), "own_digest": peer.digest},
        )
        if nonce_o == nonce_r:
            _fail("PROTOCOL_NONCE_INDEPENDENCE")
        challenge = _challenge_digest(
            session_id, nonce_r.hex(), nonce_o.hex(), own.digest, peer.digest
        )

        challenge_b, rights = _receive_endpoint_frame(
            cross, context, session_id, FRAME_PLAN[7], o_pid
        )
        if rights:
            _fail("SYNTHETIC_CHALLENGE_RIGHTS")
        common = {
            "nonce_r": nonce_r.hex(),
            "nonce_o": nonce_o.hex(),
            "challenge_digest": challenge,
        }
        _require_body(
            challenge_b, {**common, "own_digest": peer.digest, "peer_digest": own.digest}
        )
        response_b = _encode_reference_frame(
            context,
            session_id,
            FRAME_PLAN[8],
            {**common, "own_digest": own.digest, "peer_digest": peer.digest},
        )
        send_packet(cross, response_b)

        round1_raw = _encode_reference_frame(
            context,
            session_id,
            FRAME_PLAN[9],
            {
                **common,
                "comparison_digest": _comparison_digest(
                    "R", own, peer, challenge
                ),
            },
        )
        send_packet(control, round1_raw)

        recheck, rights = _receive_endpoint_frame(
            control, context, session_id, FRAME_PLAN[11], g_pid
        )
        if rights:
            _fail("SYNTHETIC_RECHECK_RIGHTS")
        _require_body(
            recheck,
            {
                "nonce_r": nonce_r.hex(),
                "nonce_o": nonce_o.hex(),
                "held_generation": own.generation,
                "round1_frame_digest": hashlib.sha256(round1_raw).hexdigest(),
            },
        )
        round2 = _encode_reference_frame(
            context, session_id, FRAME_PLAN[13], {**common, **_observation_body(own)}
        )
        send_packet(control, round2)
        _child_finish(control, cross)
        return 0
    except BaseException:
        return 72
    finally:
        _close_socket(control)
        _close_socket(cross)
        _close_fds((pid_handle, mnt_handle))


def _run_synthetic_o(
    control: socket.socket,
    cross: socket.socket,
    context: Context,
    session_id: str,
    g_pid: int,
    r_pid: int,
    deadline_binding: str,
    pid_handle: int,
    mnt_handle: int,
    fault: str,
) -> int:
    try:
        o_pid = os.getpid()
        own = _synthetic_observation("O", o_pid, context, pid_handle, mnt_handle)
        setup, rights = _receive_endpoint_frame(
            control, context, session_id, FRAME_PLAN[2], g_pid
        )
        if rights:
            _fail("SYNTHETIC_SETUP_RIGHTS")
        setup_body = _keys(
            setup["body"],
            {"r_source_frame_digest", "deadline_binding"},
            "FRAME_BODY",
        )
        _digest(setup_body["r_source_frame_digest"], "SYNTHETIC_R_SOURCE_DIGEST")
        if setup_body["deadline_binding"] != deadline_binding:
            _fail("SYNTHETIC_SETUP_BINDING")

        source_raw = _encode_reference_frame(
            context, session_id, FRAME_PLAN[3], _observation_body(own)
        )
        send_packet(control, source_raw, (pid_handle, mnt_handle))

        challenge_a, peer_rights = _receive_endpoint_frame(
            cross, context, session_id, FRAME_PLAN[5], r_pid
        )
        peer = _synthetic_observation("R", r_pid, context, pid_handle, mnt_handle)
        if peer_rights != (peer.pid_namespace, peer.mnt_namespace):
            _fail("SYNTHETIC_PEER_RIGHTS")
        challenge_body = _keys(
            challenge_a["body"], {"nonce_r", "own_digest"}, "FRAME_BODY"
        )
        nonce_r = _nonce(challenge_body["nonce_r"], "SYNTHETIC_NONCE_R")
        _require_body(
            challenge_a, {"nonce_r": nonce_r.hex(), "own_digest": peer.digest}
        )
        nonce_o = os.getrandom(32)
        if nonce_o == nonce_r:
            _fail("PROTOCOL_NONCE_INDEPENDENCE")
        response_a = _encode_reference_frame(
            context,
            session_id,
            FRAME_PLAN[6],
            {"nonce_r": nonce_r.hex(), "nonce_o": nonce_o.hex(), "own_digest": own.digest},
        )
        send_packet(cross, response_a, (pid_handle, mnt_handle))
        challenge = _challenge_digest(
            session_id, nonce_r.hex(), nonce_o.hex(), peer.digest, own.digest
        )
        common = {
            "nonce_r": nonce_r.hex(),
            "nonce_o": nonce_o.hex(),
            "challenge_digest": challenge,
        }
        challenge_b = _encode_reference_frame(
            context,
            session_id,
            FRAME_PLAN[7],
            {**common, "own_digest": own.digest, "peer_digest": peer.digest},
        )
        send_packet(cross, challenge_b)
        response_b, rights = _receive_endpoint_frame(
            cross, context, session_id, FRAME_PLAN[8], r_pid
        )
        if rights:
            _fail("SYNTHETIC_RESPONSE_RIGHTS")
        _require_body(
            response_b, {**common, "own_digest": peer.digest, "peer_digest": own.digest}
        )

        round1_raw = _encode_reference_frame(
            context,
            session_id,
            FRAME_PLAN[10],
            {
                **common,
                "comparison_digest": _comparison_digest(
                    "O", own, peer, challenge
                ),
            },
        )
        send_packet(control, round1_raw)
        recheck, rights = _receive_endpoint_frame(
            control, context, session_id, FRAME_PLAN[12], g_pid
        )
        if rights:
            _fail("SYNTHETIC_RECHECK_RIGHTS")
        _require_body(
            recheck,
            {
                "nonce_r": nonce_r.hex(),
                "nonce_o": nonce_o.hex(),
                "held_generation": own.generation,
                "round1_frame_digest": hashlib.sha256(round1_raw).hexdigest(),
            },
        )
        round2 = _encode_reference_frame(
            context, session_id, FRAME_PLAN[14], {**common, **_observation_body(own)}
        )
        send_packet(control, round2)
        if fault == "EXTRA_FRAME":
            extra = canonical(
                {
                    "schema": FRAME_SCHEMA,
                    "kind": "EXTRA",
                    "sender": "O",
                    "receiver": "G",
                    "counter": 16,
                    "session_id": session_id,
                },
                FRAME_BYTES_MAX,
            )
            send_packet(control, extra)
        _child_finish(control, cross)
        return 0
    except BaseException:
        return 73
    finally:
        _close_socket(control)
        _close_socket(cross)
        _close_fds((pid_handle, mnt_handle))


def _wait_child(pid: int, *, terminate: bool) -> dict[str, Any]:
    kill_sent = terminate
    if terminate:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + SYNTHETIC_TIMEOUT_SECONDS
    while True:
        try:
            waited, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return {"exited": False, "exit_code": None, "signal": None, "already_reaped": True}
        if waited == pid:
            return {
                "exited": os.WIFEXITED(status),
                "exit_code": os.WEXITSTATUS(status) if os.WIFEXITED(status) else None,
                "signal": os.WTERMSIG(status) if os.WIFSIGNALED(status) else None,
                "already_reaped": False,
            }
        now = time.monotonic()
        if now >= deadline and not kill_sent:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            kill_sent = True
            deadline = now + SYNTHETIC_REAP_GRACE_SECONDS
            continue
        if now >= deadline:
            # A child stuck in an uninterruptible kernel wait must not turn the
            # synthetic verifier into an unbounded wait.  The parent retains a
            # non-success result and exits; it never upgrades this to clean
            # EOF/reap evidence.
            return {
                "exited": False,
                "exit_code": None,
                "signal": None,
                "already_reaped": False,
            }
        time.sleep(0.001)


def _adopt_context_identity(context: Context) -> None:
    current = (
        os.getuid(),
        os.geteuid(),
        os.getgid(),
        os.getegid(),
        tuple(sorted(os.getgroups())),
    )
    expected = (
        context.uid,
        context.uid,
        context.gid,
        context.gid,
        context.groups,
    )
    if current == expected:
        return
    if os.geteuid() != 0 or not all(
        hasattr(os, name) for name in ("setgroups", "setresgid", "setresuid")
    ):
        _fail("SYNTHETIC_ORDINARY_IDENTITY_UNAVAILABLE")
    try:
        os.setgroups(list(context.groups))
        os.setresgid(context.gid, context.gid, context.gid)
        os.setresuid(context.uid, context.uid, context.uid)
    except OSError as error:
        raise ContractError("SYNTHETIC_IDENTITY_DROP") from error
    if (
        os.getresuid() != (context.uid, context.uid, context.uid)
        or os.getresgid() != (context.gid, context.gid, context.gid)
        or tuple(sorted(os.getgroups())) != context.groups
    ):
        _fail("SYNTHETIC_IDENTITY_DROP")


def _harness_result(
    *,
    status: str,
    reason: str,
    context: Context,
    session_id: str,
    direct_forks: int,
    protocol: ReferenceProtocol | None,
    child_waits: Mapping[str, Any],
    g_go_eof: bool,
    control_eof: bool,
    fd_cleanup_complete: bool,
) -> dict[str, Any]:
    if status not in {
        Outcome.NOT_RUN.value,
        Outcome.BLOCKED_RETAINED.value,
        Outcome.UNKNOWN_RETAINED.value,
        Outcome.FAILED_RETAINED.value,
    }:
        _fail("SYNTHETIC_STATUS")
    if type(reason) is not str or _ERROR.fullmatch(reason) is None:
        _fail("SYNTHETIC_REASON")
    frame_digests = [] if protocol is None else protocol.frame_digests
    account = None if protocol is None else protocol.account.snapshot()
    return {
        "schema": SYNTHETIC_HARNESS_SCHEMA,
        "scope": SCOPE,
        "status": status,
        "reason": reason,
        "fixture_qualification": Outcome.NOT_RUN.value,
        "context_digest": context.context_digest,
        "session_id": session_id,
        "direct_forks": direct_forks,
        "g_go_eof": g_go_eof,
        "control_eof": control_eof,
        "child_cross_eof_exit_bound": (
            direct_forks == 2
            and set(child_waits) == {"R", "O"}
            and control_eof
            and all(
            row.get("exit_code") == 0 for row in child_waits.values()
            )
        ),
        "fd_cleanup_complete": fd_cleanup_complete,
        "frames": 0 if protocol is None else protocol.counter,
        "frame_chain_digest": hashlib.sha256(
            canonical(frame_digests, CONTEXT_BYTES_MAX)
        ).hexdigest(),
        "account": account,
        "child_waits": dict(child_waits),
        "held_procfs_proven": False,
        "nsfs_proven": False,
        "native_fixture_executed": False,
        "field_ready": False,
        "allow_run": False,
    }


def _run_synthetic_g(
    bootstrap: socket.socket,
    result_socket: socket.socket,
    expected_context_raw: bytes,
    session_id: str,
    fault: str,
) -> None:
    context: Context | None = None
    protocol: ReferenceProtocol | None = None
    direct_forks = 0
    children: dict[str, int] = {}
    waits: dict[str, Any] = {}
    protocol_sockets: list[socket.socket] = []
    handles: list[int] = []
    created_handles: list[int] = []
    forked_roles: list[str] = []
    g_go_eof = False
    control_eof = False
    status = Outcome.UNKNOWN_RETAINED.value
    reason = "SYNTHETIC_INTERNAL"
    try:
        bootstrap.settimeout(SYNTHETIC_TIMEOUT_SECONDS)
        received_context = _receive_seqpacket(
            bootstrap, CONTEXT_BYTES_MAX, "SYNTHETIC_CONTEXT"
        )
        if received_context != expected_context_raw:
            _fail("SYNTHETIC_CONTEXT_BINDING")
        context = validate_context(
            received_context, hashlib.sha256(expected_context_raw).hexdigest()
        )
        _adopt_context_identity(context)
        ready = canonical(
            {
                "schema": BOOTSTRAP_READY_SCHEMA,
                "session_id": session_id,
                "context_digest": context.context_digest,
                "fixture_qualification": Outcome.NOT_RUN.value,
            },
            FRAME_BYTES_MAX,
        )
        send_packet(bootstrap, ready)
        g_go_raw = _receive_seqpacket(bootstrap, FRAME_BYTES_MAX, "SYNTHETIC_G_GO")
        g_go = _decode_canonical(g_go_raw, FRAME_BYTES_MAX, "G_GO")
        _keys(g_go, {"schema", "session_id", "context_digest"}, "G_GO_KEYS")
        _text(g_go["schema"], G_GO_SCHEMA, "G_GO_SCHEMA")
        _text(g_go["session_id"], session_id, "G_GO_SESSION")
        _text(g_go["context_digest"], context.context_digest, "G_GO_CONTEXT")
        try:
            trailing = bootstrap.recv(1)
        except OSError as error:
            raise ContractError("G_GO_EOF", Outcome.UNKNOWN_RETAINED) from error
        if trailing != b"":
            _fail("G_GO_TRAILING")
        g_go_eof = True
        _close_socket(bootstrap)

        pid_handle = _new_anonymous_handle()
        mnt_handle = _new_anonymous_handle()
        handles.extend((pid_handle, mnt_handle))
        created_handles.extend(handles)
        cross_r, cross_o = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        control_g_r, control_r = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        for item in (cross_r, cross_o, control_g_r, control_r):
            enable_passcred(item)
            item.settimeout(SYNTHETIC_TIMEOUT_SECONDS)
        protocol_sockets.extend((cross_r, cross_o, control_g_r, control_r))

        g_pid = os.getpid()
        start_boot = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        start_mono = time.monotonic_ns()
        deadline_boot = start_boot + 20_000_000_000
        deadline_mono = start_mono + 20_000_000_000
        deadline_binding = hashlib.sha256(
            canonical(
                {
                    "start_boottime_ns": start_boot,
                    "start_monotonic_ns": start_mono,
                    "deadline_boottime_ns": deadline_boot,
                    "deadline_monotonic_ns": deadline_mono,
                },
                FRAME_BYTES_MAX,
            )
        ).hexdigest()

        r_pid = os.fork()
        if r_pid == 0:
            _close_socket(result_socket)
            _close_socket(control_g_r)
            _close_socket(cross_o)
            code = _run_synthetic_r(
                control_r,
                cross_r,
                context,
                session_id,
                g_pid,
                deadline_binding,
                pid_handle,
                mnt_handle,
                fault,
            )
            os._exit(code)
        direct_forks += 1
        forked_roles.append("R")
        children["R"] = r_pid
        _close_socket(control_r)
        _close_socket(cross_r)

        control_g_o, control_o = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_SEQPACKET
        )
        enable_passcred(control_g_o)
        enable_passcred(control_o)
        control_g_o.settimeout(SYNTHETIC_TIMEOUT_SECONDS)
        control_o.settimeout(SYNTHETIC_TIMEOUT_SECONDS)
        protocol_sockets.extend((control_g_o, control_o))
        o_pid = os.fork()
        if o_pid == 0:
            _close_socket(result_socket)
            _close_socket(control_g_r)
            _close_socket(control_g_o)
            code = _run_synthetic_o(
                control_o,
                cross_o,
                context,
                session_id,
                g_pid,
                r_pid,
                deadline_binding,
                pid_handle,
                mnt_handle,
                fault,
            )
            os._exit(code)
        direct_forks += 1
        forked_roles.append("O")
        children["O"] = o_pid
        _close_socket(control_o)
        _close_socket(cross_o)

        evidence = _synthetic_evidence(
            context,
            {"G": g_pid, "R": r_pid, "O": o_pid},
            pid_handle,
            mnt_handle,
        )
        protocol = ReferenceProtocol(
            context,
            evidence,
            g_pid=g_pid,
            r_pid=r_pid,
            o_pid=o_pid,
            start_boottime_ns=start_boot,
            start_monotonic_ns=start_mono,
            deadline_boottime_ns=deadline_boot,
            deadline_monotonic_ns=deadline_mono,
            session_id=session_id,
        )
        g_credential = Credential(g_pid, context.uid, context.gid)

        def send_g(sock: socket.socket) -> None:
            raw = protocol.encode_next()
            send_packet(sock, raw)
            protocol.advance(raw, g_credential)

        send_g(control_g_r)  # 1 SETUP_R
        receive_and_advance(control_g_r, protocol, _anonymous_identity)  # 2 SOURCE_R
        send_g(control_g_o)  # 3 SETUP_O
        receive_and_advance(control_g_o, protocol, _anonymous_identity)  # 4 SOURCE_O
        send_g(control_g_r)  # 5 START_CHALLENGE

        round1_r = receive_packet(
            control_g_r,
            expected_credential=Credential(r_pid, context.uid, context.gid),
            expected_fd_count=0,
        )
        preview = _decode_canonical(round1_r.payload, FRAME_BYTES_MAX, "FRAME")
        preview_body = _keys(
            preview.get("body"),
            {"nonce_r", "nonce_o", "challenge_digest", "comparison_digest"},
            "FRAME_BODY",
        )
        nonce_r = _nonce(preview_body["nonce_r"], "SYNTHETIC_NONCE_R")
        nonce_o = _nonce(preview_body["nonce_o"], "SYNTHETIC_NONCE_O")
        if nonce_r == nonce_o:
            _fail("PROTOCOL_NONCE_INDEPENDENCE")
        for nonce, credential, rights in (
            (
                nonce_r,
                Credential(r_pid, context.uid, context.gid),
                (evidence.initial["R"].pid_namespace, evidence.initial["R"].mnt_namespace),
            ),
            (
                nonce_o,
                Credential(o_pid, context.uid, context.gid),
                (evidence.initial["O"].pid_namespace, evidence.initial["O"].mnt_namespace),
            ),
            (None, Credential(o_pid, context.uid, context.gid), ()),
            (None, Credential(r_pid, context.uid, context.gid), ()),
        ):
            raw = protocol.encode_next(nonce)
            protocol.advance(raw, credential, rights)
        protocol.advance(round1_r.payload, round1_r.credential)
        round1_o = receive_packet(
            control_g_o,
            expected_credential=Credential(o_pid, context.uid, context.gid),
            expected_fd_count=0,
        )
        protocol.advance(round1_o.payload, round1_o.credential)
        send_g(control_g_r)  # 12 RECHECK R
        send_g(control_g_o)  # 13 RECHECK O
        receive_and_advance(control_g_r, protocol, _anonymous_identity)  # 14
        receive_and_advance(control_g_o, protocol, _anonymous_identity)  # 15
        if not protocol.complete:
            _fail("SYNTHETIC_PROTOCOL_INCOMPLETE")

        control_g_r.shutdown(socket.SHUT_WR)
        control_g_o.shutdown(socket.SHUT_WR)
        _expect_eof(control_g_r, "SYNTHETIC_R_CONTROL")
        _expect_eof(control_g_o, "SYNTHETIC_O_CONTROL")
        control_eof = True
        _close_socket(control_g_r)
        _close_socket(control_g_o)
        for role, pid in children.items():
            waits[role] = _wait_child(pid, terminate=False)
        if any(row.get("exit_code") != 0 for row in waits.values()):
            _fail("SYNTHETIC_CHILD_WAIT", Outcome.UNKNOWN_RETAINED)
        children.clear()
        _close_fds(handles)
        handles.clear()
        status = Outcome.NOT_RUN.value
        reason = "HELD_PROCFS_NSFS_NATIVE_FIXTURE_NOT_PROVEN"
    except ContractError as error:
        status = error.outcome.value
        reason = error.code
    except BaseException:
        status = Outcome.UNKNOWN_RETAINED.value
        reason = "SYNTHETIC_INTERNAL"
    finally:
        _close_socket(bootstrap)
        for sock in protocol_sockets:
            _close_socket(sock)
        for role, pid in list(children.items()):
            waits[role] = _wait_child(pid, terminate=True)
        children.clear()
        _close_fds(handles)
        handles.clear()
        fd_cleanup_complete = (
            all(sock.fileno() == -1 for sock in (bootstrap, *protocol_sockets))
            and all(_fd_is_closed(fd) for fd in created_handles)
            and set(waits) == set(forked_roles)
            and all(row.get("already_reaped") is False for row in waits.values())
        )
        assert context is not None
        result = _harness_result(
            status=status,
            reason=reason,
            context=context,
            session_id=session_id,
            direct_forks=direct_forks,
            protocol=protocol,
            child_waits=waits,
            g_go_eof=g_go_eof,
            control_eof=control_eof,
            fd_cleanup_complete=fd_cleanup_complete,
        )
        try:
            send_packet(
                result_socket,
                canonical(result, SYNTHETIC_RESULT_BYTES_MAX),
            )
            _close_socket(result_socket)
            os._exit(0)
        except BaseException:
            _close_socket(result_socket)
            os._exit(90)


def _synthetic_not_run(context: Context, reason: str) -> Mapping[str, Any]:
    return _harness_result(
        status=Outcome.NOT_RUN.value,
        reason=reason,
        context=context,
        session_id="0" * 64,
        direct_forks=0,
        protocol=None,
        child_waits={},
        g_go_eof=False,
        control_eof=False,
        fd_cleanup_complete=True,
    )


def run_synthetic_harness(
    context_raw: bytes, *, fault: str = "NONE"
) -> Mapping[str, Any]:
    """Run the bounded local G/R/O transport without claiming native PASS.

    The only caller data is the closed context and one fixed test-fault token;
    there is no PID, path, command, network endpoint, or caller deadline.  All
    transport and rights objects are anonymous and created inside this call.
    """

    context = validate_context(context_raw)
    if type(fault) is not str or fault not in SYNTHETIC_FAULTS:
        _fail("SYNTHETIC_FAULT")
    required = (
        sys.platform.startswith("linux"),
        hasattr(os, "fork"),
        hasattr(os, "getrandom"),
        hasattr(socket, "SO_PASSCRED"),
        hasattr(socket, "SCM_CREDENTIALS"),
        hasattr(socket, "SCM_RIGHTS"),
        hasattr(socket, "MSG_CMSG_CLOEXEC"),
        hasattr(time, "CLOCK_BOOTTIME"),
    )
    if not all(required):
        return _synthetic_not_run(context, "SYNTHETIC_LINUX_INTERFACE_UNAVAILABLE")
    if not _synthetic_transport_available():
        return _synthetic_not_run(
            context, "SYNTHETIC_CREDENTIAL_TRANSPORT_UNAVAILABLE"
        )
    current_identity = (
        os.getuid(),
        os.geteuid(),
        os.getgid(),
        os.getegid(),
        tuple(sorted(os.getgroups())),
    )
    exact_identity = (
        context.uid,
        context.uid,
        context.gid,
        context.gid,
        context.groups,
    )
    can_drop = os.geteuid() == 0 and all(
        hasattr(os, name) for name in ("setgroups", "setresgid", "setresuid")
    )
    if current_identity != exact_identity and not can_drop:
        return _synthetic_not_run(context, "SYNTHETIC_ORDINARY_IDENTITY_UNAVAILABLE")

    seed = {
        "domain": "local-hand-q2-namespace-synthetic-session/v1",
        "context_digest": context.context_digest,
        "outer_nonce": os.getrandom(32).hex(),
    }
    session_id = hashlib.sha256(canonical(seed, CONTEXT_BYTES_MAX)).hexdigest()
    bootstrap_parent, bootstrap_g = socket.socketpair(
        socket.AF_UNIX, socket.SOCK_SEQPACKET
    )
    result_parent, result_g = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    for item in (bootstrap_parent, bootstrap_g, result_parent, result_g):
        enable_passcred(item)
        item.settimeout(SYNTHETIC_TIMEOUT_SECONDS)
    g_pid = os.fork()
    if g_pid == 0:
        _close_socket(bootstrap_parent)
        _close_socket(result_parent)
        _run_synthetic_g(bootstrap_g, result_g, context.raw, session_id, fault)
        os._exit(91)

    _close_socket(bootstrap_g)
    _close_socket(result_g)
    waited = False
    try:
        _send_seqpacket(
            bootstrap_parent, context.raw, CONTEXT_BYTES_MAX, "SYNTHETIC_CONTEXT"
        )
        ready_packet = receive_packet(
            bootstrap_parent,
            expected_credential=Credential(g_pid, context.uid, context.gid),
            expected_fd_count=0,
        )
        ready = _decode_canonical(ready_packet.payload, FRAME_BYTES_MAX, "BOOTSTRAP_READY")
        _keys(
            ready,
            {"schema", "session_id", "context_digest", "fixture_qualification"},
            "BOOTSTRAP_READY_KEYS",
        )
        for key, expected, code in (
            ("schema", BOOTSTRAP_READY_SCHEMA, "BOOTSTRAP_READY_SCHEMA"),
            ("session_id", session_id, "BOOTSTRAP_READY_SESSION"),
            ("context_digest", context.context_digest, "BOOTSTRAP_READY_CONTEXT"),
            ("fixture_qualification", Outcome.NOT_RUN.value, "BOOTSTRAP_READY_QUALIFICATION"),
        ):
            _text(ready[key], expected, code)
        g_go = canonical(
            {
                "schema": G_GO_SCHEMA,
                "session_id": session_id,
                "context_digest": context.context_digest,
            },
            FRAME_BYTES_MAX,
        )
        _send_seqpacket(bootstrap_parent, g_go, FRAME_BYTES_MAX, "SYNTHETIC_G_GO")
        bootstrap_parent.shutdown(socket.SHUT_WR)
        result_packet = receive_packet(
            result_parent,
            expected_credential=Credential(g_pid, context.uid, context.gid),
            expected_fd_count=0,
        )
        result = _decode_canonical(
            result_packet.payload, SYNTHETIC_RESULT_BYTES_MAX, "SYNTHETIC_RESULT"
        )
        wait = _wait_child(g_pid, terminate=False)
        waited = True
        if wait.get("exit_code") != 0:
            _fail("SYNTHETIC_G_WAIT", Outcome.UNKNOWN_RETAINED)
        _keys(
            result,
            {
                "schema", "scope", "status", "reason", "fixture_qualification",
                "context_digest", "session_id", "direct_forks", "g_go_eof",
                "control_eof", "child_cross_eof_exit_bound", "fd_cleanup_complete",
                "frames", "frame_chain_digest", "account", "child_waits",
                "held_procfs_proven", "nsfs_proven", "native_fixture_executed",
                "field_ready", "allow_run",
            },
            "SYNTHETIC_RESULT_KEYS",
        )
        _text(result["schema"], SYNTHETIC_HARNESS_SCHEMA, "SYNTHETIC_RESULT_SCHEMA")
        _text(result["scope"], SCOPE, "SYNTHETIC_RESULT_SCOPE")
        _text(result["context_digest"], context.context_digest, "SYNTHETIC_RESULT_CONTEXT")
        _text(result["session_id"], session_id, "SYNTHETIC_RESULT_SESSION")
        _text(
            result["fixture_qualification"],
            Outcome.NOT_RUN.value,
            "SYNTHETIC_RESULT_QUALIFICATION",
        )
        status = _text(result["status"], None, "SYNTHETIC_RESULT_STATUS")
        if status not in {
            Outcome.NOT_RUN.value,
            Outcome.BLOCKED_RETAINED.value,
            Outcome.UNKNOWN_RETAINED.value,
            Outcome.FAILED_RETAINED.value,
        }:
            _fail("SYNTHETIC_RESULT_STATUS")
        reason = _text(result["reason"], None, "SYNTHETIC_RESULT_REASON")
        if _ERROR.fullmatch(reason) is None:
            _fail("SYNTHETIC_RESULT_REASON")
        direct_forks = _integer(
            result["direct_forks"], 0, 2, "SYNTHETIC_RESULT_FORKS"
        )
        frames = _integer(
            result["frames"], 0, FRAME_COUNT, "SYNTHETIC_RESULT_FRAMES"
        )
        _digest(result["frame_chain_digest"], "SYNTHETIC_RESULT_FRAME_CHAIN")
        for key in (
            "g_go_eof",
            "control_eof",
            "child_cross_eof_exit_bound",
            "fd_cleanup_complete",
            "held_procfs_proven",
            "nsfs_proven",
            "native_fixture_executed",
            "field_ready",
            "allow_run",
        ):
            if type(result[key]) is not bool:
                _fail("SYNTHETIC_RESULT_BOOLEAN")
        waits = result["child_waits"]
        expected_wait_roles = (set(), {"R"}, {"R", "O"})[direct_forks]
        if type(waits) is not dict or set(waits) != expected_wait_roles:
            _fail("SYNTHETIC_RESULT_WAITS")
        for row in waits.values():
            wait = _keys(
                row,
                {"exited", "exit_code", "signal", "already_reaped"},
                "SYNTHETIC_RESULT_WAIT_KEYS",
            )
            if type(wait["exited"]) is not bool or type(wait["already_reaped"]) is not bool:
                _fail("SYNTHETIC_RESULT_WAIT_BOOLEAN")
            for key in ("exit_code", "signal"):
                if wait[key] is not None:
                    _integer(wait[key], 0, 255, "SYNTHETIC_RESULT_WAIT_VALUE")
        account = result["account"]
        if account is None:
            if frames != 0:
                _fail("SYNTHETIC_RESULT_ACCOUNT")
        else:
            account_value = _keys(
                account,
                {
                    "frames", "frame_bytes", "status_reads", "status_bytes",
                    "namespace_opens", "random_bytes", "tasks",
                    "installed_fd_peak", "queued_fd_peak", "stdout_bytes",
                    "stderr_bytes",
                },
                "SYNTHETIC_RESULT_ACCOUNT_KEYS",
            )
            for key, maximum in (
                ("frames", FRAME_COUNT),
                ("frame_bytes", FRAME_PAYLOAD_BYTES_MAX),
                ("status_reads", STATUS_READS_MAX),
                ("status_bytes", STATUS_BYTES_TOTAL_MAX),
                ("namespace_opens", NAMESPACE_OPENS_MAX),
                ("random_bytes", RANDOM_BYTES_EXACT),
                ("tasks", TASKS_EXACT),
                ("queued_fd_peak", QUEUED_FD_MAX),
                ("stdout_bytes", STDOUT_BYTES_MAX),
                ("stderr_bytes", STDERR_BYTES_MAX),
            ):
                _integer(
                    account_value[key], 0, maximum, "SYNTHETIC_RESULT_ACCOUNT"
                )
            if account_value["frames"] != frames:
                _fail("SYNTHETIC_RESULT_ACCOUNT")
            peaks = _keys(
                account_value["installed_fd_peak"],
                {"G", "R", "O"},
                "SYNTHETIC_RESULT_FD_PEAK_KEYS",
            )
            for role, maximum in INSTALLED_FD_MAX.items():
                _integer(peaks[role], 0, maximum, "SYNTHETIC_RESULT_FD_PEAK")
            if (
                sum(peaks.values()) > INSTALLED_FD_TOTAL_MAX
                or sum(peaks.values()) + account_value["queued_fd_peak"]
                > FD_REFERENCES_TOTAL_MAX
            ):
                _fail("SYNTHETIC_RESULT_FD_TOTAL")
        if any(
            result[key] is not False
            for key in (
                "held_procfs_proven", "nsfs_proven", "native_fixture_executed",
                "field_ready", "allow_run",
            )
        ):
            _fail("SYNTHETIC_RESULT_READINESS")
        return result
    finally:
        _close_socket(bootstrap_parent)
        _close_socket(result_parent)
        if not waited:
            _wait_child(g_pid, terminate=True)
