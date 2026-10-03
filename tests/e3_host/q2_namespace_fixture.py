"""Pure contract model for the Q2 namespace delivery fixture.

This module deliberately performs no filesystem access, process creation,
namespace observation, cgroup mutation, or guest contact.  It models the
plan-independent parts of ``LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1`` so that the
privileged fixture can reject an invalid plan or observation before it uses a
live object.  A modeled success is never a native qualification result.

The live implementation must supply held-object identity, raw counter bytes,
clock samples, durable owner acknowledgements, and typed process evidence.  A
boolean supplied by a caller cannot turn the native status in this module into
PASS.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import errno
import re
from typing import Mapping, Sequence


SCOPE = "LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1"
CASE_IDS = tuple(f"N{number:02d}" for number in range(1, 13))
MAX_CASES = 12
MAX_ACTIONS = 37
MAX_SELF_WRITES = 76

NS = 1_000_000_000
CASE_WORK_NS = 20 * NS
CASE_STOP_NS = 25 * NS
CASE_DRAIN_NS = 30 * NS
CASE_FINAL_NS = 40 * NS
FINAL_SUCCESS_RESERVE_NS = 110 * NS

BUNDLE_MAX_FILES = 8
BUNDLE_MAX_BYTES = 1024 * 1024
ACTION_JOURNAL_BYTES = 64 * 1024
ACTION_SLOT_BYTES = 1024
RESULT_JOURNAL_BYTES = 752 * 1024
CONTEXT_BYTES = 16 * 1024
RESULT_HEADER_BYTES = 8 * 1024
RESULT_CASE_SLOT_BYTES = 48 * 1024
RESULT_CASES_OFFSET = 8192
RESULT_EXCURSION_OFFSET = 598016
RESULT_EXCURSION_SLOT_BYTES = 4096
RESULT_TERMINAL_OFFSET = 753664
RESULT_TERMINAL_BYTES = 16 * 1024
STAGE_MAX_LOGICAL_BYTES = 2_080_768
STAGE_MAX_REGULAR_FILES = 22
STAGE_MAX_INODES_WITH_DIRECTORY = 23

_DIGEST = re.compile(r"[0-9a-f]{64}")
_BASENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,126}")
_COUNTER = re.compile(r"0|[1-9][0-9]{0,19}")
_KEY_VALUE = re.compile(r"([a-z][a-z0-9_.]*) (0|[1-9][0-9]{0,19})")
_MAX_COUNTER = (1 << 63) - 1


class FixtureContractError(ValueError):
    """A stable fail-closed rejection with a machine-readable reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise FixtureContractError(reason)


def _integer(value: object, reason: str, low: int = 0, high: int = _MAX_COUNTER) -> int:
    _require(type(value) is int and low <= value <= high, reason)
    return value


def _digest(value: object, reason: str = "FIXTURE_DIGEST") -> str:
    _require(type(value) is str and _DIGEST.fullmatch(value) is not None, reason)
    return value


def _strict_tuple(values: Sequence[str], reason: str) -> tuple[str, ...]:
    _require(type(values) in (tuple, list) and bool(values), reason)
    result = tuple(values)
    _require(all(type(value) is str and _KEY_VALUE.fullmatch(f"{value} 0") for value in result), reason)
    _require(len(result) == len(set(result)), reason)
    return result


def _ascii(raw: object, reason: str, maximum: int = 64 * 1024) -> str:
    _require(type(raw) in (bytes, str), reason)
    if type(raw) is bytes:
        _require(0 <= len(raw) <= maximum, reason)
        try:
            value = raw.decode("ascii", "strict")
        except UnicodeError:
            raise FixtureContractError(reason) from None
    else:
        value = raw
        try:
            encoded = value.encode("ascii", "strict")
        except UnicodeError:
            raise FixtureContractError(reason) from None
        _require(len(encoded) <= maximum, reason)
    _require("\x00" not in value and "\r" not in value, reason)
    return value


def _lines(raw: object, reason: str, *, empty: bool = False) -> list[str]:
    value = _ascii(raw, reason)
    if value == "":
        _require(empty, reason)
        return []
    _require(value.endswith("\n"), reason)
    lines = value[:-1].split("\n")
    _require(all(lines), reason)
    return lines


@dataclass(frozen=True)
class ResultRegion:
    name: str
    index: int
    offset: int
    length: int

    @property
    def end(self) -> int:
        return self.offset + self.length


def result_region(name: str, index: int = 0) -> ResultRegion:
    """Return one immutable result-journal region from the fixed A layout."""

    _require(type(name) is str and type(index) is int, "FIXTURE_RESULT_REGION")
    if name == "header":
        _require(index == 0, "FIXTURE_RESULT_REGION")
        region = ResultRegion(name, index, 0, RESULT_HEADER_BYTES)
    elif name == "case":
        _require(1 <= index <= MAX_CASES, "FIXTURE_RESULT_CASE_INDEX")
        region = ResultRegion(name, index, RESULT_CASES_OFFSET + (index - 1) * RESULT_CASE_SLOT_BYTES,
                              RESULT_CASE_SLOT_BYTES)
    elif name in {"case_stdout", "case_stderr", "case_metadata"}:
        _require(1 <= index <= MAX_CASES, "FIXTURE_RESULT_CASE_INDEX")
        case_offset = RESULT_CASES_OFFSET + (index - 1) * RESULT_CASE_SLOT_BYTES
        relative, length = {
            "case_stdout": (0, 32 * 1024),
            "case_stderr": (32 * 1024, 8 * 1024),
            "case_metadata": (40 * 1024, 8 * 1024),
        }[name]
        region = ResultRegion(name, index, case_offset + relative, length)
    elif name == "excursion":
        _require(1 <= index <= 38, "FIXTURE_RESULT_EXCURSION_INDEX")
        region = ResultRegion(name, index, RESULT_EXCURSION_OFFSET + (index - 1) * RESULT_EXCURSION_SLOT_BYTES,
                              RESULT_EXCURSION_SLOT_BYTES)
    elif name == "terminal":
        _require(index == 0, "FIXTURE_RESULT_REGION")
        region = ResultRegion(name, index, RESULT_TERMINAL_OFFSET, RESULT_TERMINAL_BYTES)
    else:
        raise FixtureContractError("FIXTURE_RESULT_REGION")
    _require(region.end <= RESULT_JOURNAL_BYTES, "FIXTURE_RESULT_LAYOUT_OVERFLOW")
    return region


def validate_action_slots(slots: Sequence[tuple[int, int]]) -> tuple[ResultRegion, ...]:
    """Validate a manifest-selected action layout without inventing an A offset."""

    _require(type(slots) in (tuple, list) and len(slots) == MAX_ACTIONS,
             "FIXTURE_ACTION_LAYOUT")
    regions = []
    previous_end = 0
    for index, row in enumerate(slots, 1):
        _require(type(row) in (tuple, list) and len(row) == 2,
                 "FIXTURE_ACTION_LAYOUT")
        offset = _integer(row[0], "FIXTURE_ACTION_OFFSET", 0, ACTION_JOURNAL_BYTES - 1)
        length = _integer(row[1], "FIXTURE_ACTION_LENGTH", 1, ACTION_SLOT_BYTES)
        _require(offset >= previous_end and offset + length <= ACTION_JOURNAL_BYTES,
                 "FIXTURE_ACTION_LAYOUT_OVERFLOW")
        regions.append(ResultRegion("action", index, offset, length))
        previous_end = offset + length
    return tuple(regions)


def intent_basename(case_id: str) -> str:
    _require(case_id in CASE_IDS, "FIXTURE_CASE_ID")
    return f"case-{case_id}.intent"


@dataclass(frozen=True)
class StageLayout:
    bundle_members: tuple[tuple[str, int], ...]
    regular_files: int
    inodes_with_directory: int
    logical_bytes: int
    fixed_names: tuple[str, ...]


def validate_stage_layout(bundle_members: Mapping[str, int]) -> StageLayout:
    """Validate names and exact logical ceilings without touching a filesystem."""

    _require(type(bundle_members) is dict and 1 <= len(bundle_members) <= BUNDLE_MAX_FILES,
             "FIXTURE_BUNDLE_COUNT")
    reserved = {"action.journal", "result.journal", *(intent_basename(case_id) for case_id in CASE_IDS)}
    rows: list[tuple[str, int]] = []
    total = 0
    for name, size in sorted(bundle_members.items()):
        _require(type(name) is str and _BASENAME.fullmatch(name) is not None and name not in reserved,
                 "FIXTURE_BUNDLE_BASENAME")
        _integer(size, "FIXTURE_BUNDLE_MEMBER_SIZE", 1, BUNDLE_MAX_BYTES)
        total += size
        _require(total <= BUNDLE_MAX_BYTES, "FIXTURE_BUNDLE_BYTES")
        rows.append((name, size))
    fixed_names = ("action.journal", "result.journal", *(intent_basename(case_id) for case_id in CASE_IDS))
    regular = len(rows) + len(fixed_names)
    logical = total + ACTION_JOURNAL_BYTES + RESULT_JOURNAL_BYTES + MAX_CASES * CONTEXT_BYTES
    _require(regular <= STAGE_MAX_REGULAR_FILES and regular + 1 <= STAGE_MAX_INODES_WITH_DIRECTORY,
             "FIXTURE_STAGE_INODES")
    _require(logical <= STAGE_MAX_LOGICAL_BYTES, "FIXTURE_STAGE_LOGICAL_BYTES")
    return StageLayout(tuple(rows), regular, regular + 1, logical, fixed_names)


@dataclass(frozen=True)
class CounterSchema:
    cpu_fields: tuple[str, ...]
    memory_event_fields: tuple[str, ...]
    pids_event_fields: tuple[str, ...]
    controls: tuple[tuple[str, str], ...]

    @classmethod
    def make(cls, *, cpu_fields: Sequence[str], memory_event_fields: Sequence[str],
             pids_event_fields: Sequence[str], controls: Mapping[str, str]) -> "CounterSchema":
        cpu = _strict_tuple(cpu_fields, "FIXTURE_CPU_SCHEMA")
        memory = _strict_tuple(memory_event_fields, "FIXTURE_MEMORY_EVENT_SCHEMA")
        pids = _strict_tuple(pids_event_fields, "FIXTURE_PIDS_EVENT_SCHEMA")
        _require(type(controls) is dict and bool(controls), "FIXTURE_CONTROL_SCHEMA")
        rows = []
        for name, expected in sorted(controls.items()):
            _require(type(name) is str and _KEY_VALUE.fullmatch(f"{name} 0") is not None,
                     "FIXTURE_CONTROL_SCHEMA")
            _require(type(expected) is str and "\n" not in expected and "\x00" not in expected,
                     "FIXTURE_CONTROL_SCHEMA")
            _ascii(expected, "FIXTURE_CONTROL_SCHEMA", 4096)
            rows.append((name, expected))
        return cls(cpu, memory, pids, tuple(rows))


def controls_for(kind: str, *, cpus: str = "2", mems: str = "0") -> dict[str, str]:
    """Return A's exact control values for one new cgroup role."""

    _require(kind in {"batch", "guardian", "supervisor", "case"}, "FIXTURE_CGROUP_KIND")
    _require(type(cpus) is str and _COUNTER.fullmatch(cpus) is not None and
             int(cpus, 10) <= _MAX_COUNTER, "FIXTURE_CPUSET")
    _require(type(mems) is str and mems and "\n" not in mems, "FIXTURE_MEMSET")
    values = {
        "cgroup.controllers": "cpu cpuset memory pids",
        "cgroup.type": "domain",
        "cgroup.subtree_control": "cpu cpuset memory pids" if kind == "batch" else "",
        "cgroup.freeze": "0",
        "cpuset.cpus": cpus,
        "cpuset.mems": mems,
        "cpuset.cpus.effective": cpus,
        "cpuset.mems.effective": mems,
        "cpu.max.burst": "0",
        "memory.swap.max": "0",
        "memory.min": "0",
        "memory.low": "0",
        "memory.high": "max",
    }
    if kind == "batch":
        values.update({"cpu.max": "100000 100000", "memory.max": str(320 * 1024 * 1024),
                       "pids.max": "5", "cgroup.max.depth": "1", "cgroup.max.descendants": "3"})
    elif kind == "guardian":
        values.update({"cpu.max": "20000 100000", "memory.max": str(64 * 1024 * 1024),
                       "pids.max": "1"})
    elif kind == "supervisor":
        values.update({"cpu.max": "50000 100000", "memory.max": str(192 * 1024 * 1024),
                       "pids.max": "1"})
    else:
        values.update({"cpu.max": "5000 100000", "memory.max": str(96 * 1024 * 1024),
                       "pids.max": "3"})
    return values


def parse_procs(raw: object) -> tuple[int, ...]:
    rows = _lines(raw, "FIXTURE_CGROUP_PROCS", empty=True)
    values = []
    for row in rows:
        _require(_COUNTER.fullmatch(row) is not None, "FIXTURE_CGROUP_PROCS")
        value = int(row)
        _require(0 < value <= _MAX_COUNTER and value not in values, "FIXTURE_CGROUP_PROCS")
        values.append(value)
    return tuple(values)


def parse_scalar(raw: object, reason: str) -> int:
    rows = _lines(raw, reason)
    _require(len(rows) == 1 and _COUNTER.fullmatch(rows[0]) is not None, reason)
    value = int(rows[0])
    _require(value <= _MAX_COUNTER, reason)
    return value


def parse_counters(raw: object, fields: Sequence[str], reason: str) -> tuple[tuple[str, int], ...]:
    expected = _strict_tuple(fields, reason + "_SCHEMA")
    rows = _lines(raw, reason)
    result = []
    for row in rows:
        match = _KEY_VALUE.fullmatch(row)
        _require(match is not None, reason)
        value = int(match[2])
        _require(value <= _MAX_COUNTER, reason)
        result.append((match[1], value))
    _require(tuple(name for name, _ in result) == expected, reason + "_FIELDS")
    return tuple(result)


def parse_control(raw: object, expected: str, reason: str, *, unordered_tokens: bool = False) -> str:
    value = _ascii(raw, reason, 4096)
    if expected == "":
        _require(value in {"", "\n"}, reason)
        return expected
    _require(value.endswith("\n") and value.count("\n") == 1, reason)
    observed = value[:-1]
    if unordered_tokens:
        expected_tokens = expected.split(" ")
        observed_tokens = observed.split(" ")
        _require(all(observed_tokens) and len(observed_tokens) == len(set(observed_tokens)) and
                 set(observed_tokens) == set(expected_tokens), reason)
    else:
        _require(observed == expected, reason)
    return expected


@dataclass(frozen=True)
class CgroupSnapshot:
    procs: tuple[int, ...]
    populated: int
    frozen: int
    nr_descendants: int
    nr_dying_descendants: int
    cpu: tuple[tuple[str, int], ...]
    memory_current: int
    memory_peak: int
    memory_events: tuple[tuple[str, int], ...]
    memory_events_local: tuple[tuple[str, int], ...]
    pids_current: int
    pids_peak: int
    pids_events: tuple[tuple[str, int], ...]
    controls: tuple[tuple[str, str], ...]

    def cpu_value(self, name: str) -> int:
        values = dict(self.cpu)
        _require(name in values, "FIXTURE_CPU_FIELD")
        return values[name]


def parse_cgroup_snapshot(raw: Mapping[str, object], schema: CounterSchema) -> CgroupSnapshot:
    _require(type(raw) is dict and type(schema) is CounterSchema, "FIXTURE_SNAPSHOT_INPUT")
    control_names = tuple(name for name, _ in schema.controls)
    fixed = {
        "cgroup.procs", "cgroup.events", "cgroup.stat", "cpu.stat", "memory.current", "memory.peak",
        "memory.events", "memory.events.local", "pids.current", "pids.peak", "pids.events",
    }
    _require(set(raw) == fixed | set(control_names), "FIXTURE_SNAPSHOT_FILES")
    events = dict(parse_counters(raw["cgroup.events"], ("populated", "frozen"), "FIXTURE_CGROUP_EVENTS"))
    stat = dict(parse_counters(raw["cgroup.stat"], ("nr_descendants", "nr_dying_descendants"),
                               "FIXTURE_CGROUP_STAT"))
    controls = tuple((name, parse_control(
        raw[name], expected, "FIXTURE_CONTROL_" + name.upper(),
        unordered_tokens=name in {"cgroup.controllers", "cgroup.subtree_control"},
    ))
                     for name, expected in schema.controls)
    return CgroupSnapshot(
        parse_procs(raw["cgroup.procs"]), events["populated"], events["frozen"],
        stat["nr_descendants"], stat["nr_dying_descendants"],
        parse_counters(raw["cpu.stat"], schema.cpu_fields, "FIXTURE_CPU_STAT"),
        parse_scalar(raw["memory.current"], "FIXTURE_MEMORY_CURRENT"),
        parse_scalar(raw["memory.peak"], "FIXTURE_MEMORY_PEAK"),
        parse_counters(raw["memory.events"], schema.memory_event_fields, "FIXTURE_MEMORY_EVENTS"),
        parse_counters(raw["memory.events.local"], schema.memory_event_fields,
                       "FIXTURE_MEMORY_EVENTS_LOCAL"),
        parse_scalar(raw["pids.current"], "FIXTURE_PIDS_CURRENT"),
        parse_scalar(raw["pids.peak"], "FIXTURE_PIDS_PEAK"),
        parse_counters(raw["pids.events"], schema.pids_event_fields, "FIXTURE_PIDS_EVENTS"),
        controls,
    )


def validate_initial_snapshot(snapshot: CgroupSnapshot) -> CgroupSnapshot:
    _require(type(snapshot) is CgroupSnapshot, "FIXTURE_INITIAL_SNAPSHOT")
    _require(not snapshot.procs and snapshot.populated == 0 and snapshot.frozen == 0,
             "FIXTURE_INITIAL_TASKS")
    _require(snapshot.nr_descendants == 0 and snapshot.nr_dying_descendants == 0,
             "FIXTURE_INITIAL_DESCENDANTS")
    counters = (*snapshot.cpu, *snapshot.memory_events, *snapshot.memory_events_local, *snapshot.pids_events)
    _require(all(value == 0 for _, value in counters), "FIXTURE_INITIAL_COUNTER_NONZERO")
    _require(snapshot.memory_current == 0 and snapshot.memory_peak == 0 and
             snapshot.pids_current == 0 and snapshot.pids_peak == 0,
             "FIXTURE_INITIAL_COUNTER_NONZERO")
    return snapshot


@dataclass(frozen=True)
class ResourceCeiling:
    cpu_usage_usec: int
    memory_peak_bytes: int
    pids_peak: int


RESOURCE_CEILINGS = {
    "batch": ResourceCeiling(170_000_000, 320 * 1024 * 1024, 5),
    "guardian": ResourceCeiling(10_000_000, 64 * 1024 * 1024, 1),
    "supervisor": ResourceCeiling(100_000_000, 192 * 1024 * 1024, 1),
    "case": ResourceCeiling(5_000_000, 128 * 1024 * 1024, 3),
}


def validate_final_snapshot(snapshot: CgroupSnapshot, kind: str) -> CgroupSnapshot:
    _require(type(snapshot) is CgroupSnapshot and kind in RESOURCE_CEILINGS, "FIXTURE_FINAL_SNAPSHOT")
    ceiling = RESOURCE_CEILINGS[kind]
    _require(not snapshot.procs and snapshot.populated == 0 and snapshot.frozen == 0,
             "FIXTURE_FINAL_TASKS")
    _require(snapshot.nr_descendants == 0 and snapshot.nr_dying_descendants == 0,
             "FIXTURE_FINAL_DESCENDANTS")
    _require(snapshot.memory_current == 0 and snapshot.pids_current == 0,
             "FIXTURE_FINAL_CURRENT")
    _require(snapshot.cpu_value("usage_usec") <= ceiling.cpu_usage_usec,
             "FIXTURE_FINAL_CPU_CEILING")
    _require(snapshot.memory_peak <= ceiling.memory_peak_bytes, "FIXTURE_FINAL_MEMORY_CEILING")
    _require(snapshot.pids_peak <= ceiling.pids_peak, "FIXTURE_FINAL_PIDS_CEILING")
    return snapshot


class ReclaimStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ReclaimRound:
    before: int
    payload: bytes
    error: int | None
    bytes_written: int
    after: int


@dataclass(frozen=True)
class ReclaimState:
    current: int
    rounds: tuple[ReclaimRound, ...] = ()
    status: ReclaimStatus = ReclaimStatus.ACTIVE
    reason: str | None = None


def begin_reclaim(current: int) -> ReclaimState:
    _integer(current, "FIXTURE_RECLAIM_CURRENT")
    return ReclaimState(current, status=ReclaimStatus.COMPLETE if current == 0 else ReclaimStatus.ACTIVE)


def reclaim_round(state: ReclaimState, *, observed_before: int, payload: bytes,
                  write_errno: int | None, observed_after: int,
                  bytes_written: int | None = None) -> ReclaimState:
    """Apply one current-sized reclaim observation; never performs the write."""

    _require(type(state) is ReclaimState and state.status is ReclaimStatus.ACTIVE,
             "FIXTURE_RECLAIM_STATE")
    _integer(observed_before, "FIXTURE_RECLAIM_BEFORE", 1)
    _integer(observed_after, "FIXTURE_RECLAIM_AFTER")
    _require(observed_before == state.current and type(payload) is bytes and
             payload == str(observed_before).encode("ascii"), "FIXTURE_RECLAIM_REQUEST")
    _require(write_errno is None or type(write_errno) is int, "FIXTURE_RECLAIM_ERRNO")
    if bytes_written is None:
        bytes_written = len(payload) if write_errno is None else 0
    _integer(bytes_written, "FIXTURE_RECLAIM_BYTES", 0, len(payload))
    record = ReclaimRound(observed_before, payload, write_errno, bytes_written, observed_after)
    rounds = (*state.rounds, record)
    if write_errno not in (None, errno.EAGAIN):
        return ReclaimState(observed_after, rounds, ReclaimStatus.FAILED, "FIXTURE_RECLAIM_WRITE")
    if ((write_errno is None and bytes_written != len(payload)) or
            (write_errno is not None and bytes_written != 0)):
        return ReclaimState(observed_after, rounds, ReclaimStatus.FAILED,
                            "FIXTURE_RECLAIM_PARTIAL_WRITE")
    if observed_after > observed_before:
        return ReclaimState(observed_after, rounds, ReclaimStatus.FAILED, "FIXTURE_RECLAIM_CHARGE_INCREASED")
    if observed_after == 0:
        return ReclaimState(0, rounds, ReclaimStatus.COMPLETE)
    if len(rounds) >= 4:
        return ReclaimState(observed_after, rounds, ReclaimStatus.FAILED, "FIXTURE_RECLAIM_NOT_ZERO")
    return ReclaimState(observed_after, rounds)


def require_reclaimed(state: ReclaimState) -> ReclaimState:
    _require(type(state) is ReclaimState and state.status is ReclaimStatus.COMPLETE and state.current == 0,
             "FIXTURE_RECLAIM_INCOMPLETE")
    return state


class CasePhase(str, Enum):
    WORK = "WORK"
    STOP = "STOP"
    DRAIN = "DRAIN"
    FINAL = "FINAL"
    EXPIRED = "EXPIRED"


class CaseOperation(str, Enum):
    INTENT = "INTENT"
    CREATE = "CREATE"
    ACTION = "ACTION"
    OBSERVE = "OBSERVE"
    STOP = "STOP"
    DRAIN = "DRAIN"
    RECLAIM = "RECLAIM"
    FINALIZE = "FINALIZE"


@dataclass(frozen=True)
class CaseClock:
    case_id: str
    t0_boottime_ns: int
    t0_monotonic_ns: int

    def __post_init__(self) -> None:
        _require(self.case_id in CASE_IDS, "FIXTURE_CASE_ID")
        _integer(self.t0_boottime_ns, "FIXTURE_CASE_T0")
        _integer(self.t0_monotonic_ns, "FIXTURE_CASE_T0")


def case_phase(clock: CaseClock, *, boottime_ns: int, monotonic_ns: int) -> CasePhase:
    _require(type(clock) is CaseClock, "FIXTURE_CASE_CLOCK")
    _integer(boottime_ns, "FIXTURE_CASE_NOW")
    _integer(monotonic_ns, "FIXTURE_CASE_NOW")
    boot_elapsed = boottime_ns - clock.t0_boottime_ns
    mono_elapsed = monotonic_ns - clock.t0_monotonic_ns
    _require(boot_elapsed >= 0 and mono_elapsed >= 0, "FIXTURE_CASE_CLOCK_REWIND")
    elapsed = max(boot_elapsed, mono_elapsed)
    if elapsed < CASE_WORK_NS:
        return CasePhase.WORK
    if elapsed < CASE_STOP_NS:
        return CasePhase.STOP
    if elapsed < CASE_DRAIN_NS:
        return CasePhase.DRAIN
    if elapsed < CASE_FINAL_NS:
        return CasePhase.FINAL
    return CasePhase.EXPIRED


def require_case_operation(clock: CaseClock, *, operation: CaseOperation,
                           boottime_ns: int, monotonic_ns: int) -> CasePhase:
    """Reject phase borrowing across the immutable +20/+25/+30/+40 bounds."""

    _require(type(operation) is CaseOperation, "FIXTURE_CASE_OPERATION")
    phase = case_phase(clock, boottime_ns=boottime_ns, monotonic_ns=monotonic_ns)
    allowed = {
        CasePhase.WORK: {CaseOperation.INTENT, CaseOperation.CREATE, CaseOperation.ACTION,
                         CaseOperation.OBSERVE},
        CasePhase.STOP: {CaseOperation.STOP},
        CasePhase.DRAIN: {CaseOperation.DRAIN},
        CasePhase.FINAL: {CaseOperation.RECLAIM, CaseOperation.FINALIZE},
        CasePhase.EXPIRED: set(),
    }
    _require(operation in allowed[phase], "FIXTURE_CASE_PHASE_OPERATION")
    return phase


def require_case_reserve(clock: CaseClock, *, boottime_ns: int, monotonic_ns: int,
                         work_deadline_boottime_ns: int, work_deadline_monotonic_ns: int) -> None:
    _require(case_phase(clock, boottime_ns=boottime_ns, monotonic_ns=monotonic_ns) is CasePhase.WORK,
             "FIXTURE_CASE_NOT_WORK")
    _integer(work_deadline_boottime_ns, "FIXTURE_WORK_DEADLINE")
    _integer(work_deadline_monotonic_ns, "FIXTURE_WORK_DEADLINE")
    boot_need = clock.t0_boottime_ns + CASE_FINAL_NS - boottime_ns + FINAL_SUCCESS_RESERVE_NS
    mono_need = clock.t0_monotonic_ns + CASE_FINAL_NS - monotonic_ns + FINAL_SUCCESS_RESERVE_NS
    _require(work_deadline_boottime_ns - boottime_ns >= boot_need and
             work_deadline_monotonic_ns - monotonic_ns >= mono_need,
             "FIXTURE_CASE_RESERVE")


@dataclass(frozen=True)
class CompletedCase:
    case_id: str
    clock: CaseClock
    finished_boottime_ns: int
    finished_monotonic_ns: int
    outcome: str


@dataclass(frozen=True)
class CaseSequence:
    completed: tuple[CompletedCase, ...] = ()
    active: CaseClock | None = None
    terminal_reason: str | None = None


def start_case(sequence: CaseSequence, *, case_id: str, t0_boottime_ns: int, t0_monotonic_ns: int,
               work_deadline_boottime_ns: int, work_deadline_monotonic_ns: int) -> CaseSequence:
    _require(type(sequence) is CaseSequence and sequence.terminal_reason is None and sequence.active is None,
             "FIXTURE_CASE_SEQUENCE")
    _require(len(sequence.completed) < MAX_CASES and case_id == CASE_IDS[len(sequence.completed)],
             "FIXTURE_CASE_ORDER")
    clock = CaseClock(case_id, t0_boottime_ns, t0_monotonic_ns)
    require_case_reserve(clock, boottime_ns=t0_boottime_ns, monotonic_ns=t0_monotonic_ns,
                         work_deadline_boottime_ns=work_deadline_boottime_ns,
                         work_deadline_monotonic_ns=work_deadline_monotonic_ns)
    return replace(sequence, active=clock)


def close_case(sequence: CaseSequence, *, case_id: str, boottime_ns: int, monotonic_ns: int,
               outcome: str) -> CaseSequence:
    _require(type(sequence) is CaseSequence and sequence.active is not None and
             sequence.active.case_id == case_id, "FIXTURE_CASE_ACTIVE")
    _require(outcome in {"PASSED", "EXPECTED_REJECTION"}, "FIXTURE_CASE_OUTCOME")
    _require(case_phase(sequence.active, boottime_ns=boottime_ns,
                        monotonic_ns=monotonic_ns) is CasePhase.FINAL, "FIXTURE_CASE_CLOSE_PHASE")
    completed = CompletedCase(case_id, sequence.active, boottime_ns, monotonic_ns, outcome)
    return CaseSequence((*sequence.completed, completed))


def abort_case(sequence: CaseSequence, *, reason: str) -> CaseSequence:
    _require(type(sequence) is CaseSequence and sequence.active is not None and
             type(reason) is str and reason, "FIXTURE_CASE_ABORT")
    return replace(sequence, active=None, terminal_reason=reason)


class ReleaseOutcome(str, Enum):
    NOT_SENT = "NOT_SENT"
    CLEAN_REJECTED = "CLEAN_REJECTED"
    ACCEPTED = "ACCEPTED"
    UNKNOWN = "UNKNOWN"


class Qualification(str, Enum):
    NOT_RUN = "NOT_RUN"
    BLOCKED_RETAINED = "BLOCKED_RETAINED"
    UNKNOWN_RETAINED = "UNKNOWN_RETAINED"
    FAILED_RETAINED = "FAILED_RETAINED"
    FIXTURE_LIVE_REFERENCE_MATCHED = "FIXTURE_LIVE_REFERENCE_MATCHED"


@dataclass(frozen=True)
class IssuanceState:
    delivery_issued: bool = False
    batch_release_issued: bool = False
    batch_release_accepted: bool = False
    batch_release_outcome: ReleaseOutcome = ReleaseOutcome.NOT_SENT
    qualification: Qualification = Qualification.NOT_RUN
    modeled_only: bool = True
    durability_proven: bool = False
    live_proven: bool = False

    def __post_init__(self) -> None:
        _require(
            all(type(value) is bool for value in (
                self.delivery_issued, self.batch_release_issued,
                self.batch_release_accepted,
            ))
            and type(self.batch_release_outcome) is ReleaseOutcome
            and type(self.qualification) is Qualification
            and self.modeled_only is True
            and self.durability_proven is False
            and self.live_proven is False
            and self.qualification is not Qualification.FIXTURE_LIVE_REFERENCE_MATCHED,
            "FIXTURE_PURE_MODEL_LIVE_MATCH",
        )


def issue_delivery(state: IssuanceState) -> IssuanceState:
    _require(type(state) is IssuanceState and not state.delivery_issued,
             "FIXTURE_DELIVERY_RETRY")
    return replace(state, delivery_issued=True)


def issue_batch_release(state: IssuanceState, *, owner_record_fsynced: bool) -> IssuanceState:
    _require(type(state) is IssuanceState and state.delivery_issued and not state.batch_release_issued and
             state.batch_release_outcome is ReleaseOutcome.NOT_SENT and owner_record_fsynced is True,
             "FIXTURE_BATCH_RELEASE_RETRY")
    return replace(state, batch_release_issued=True)


def accept_batch_release(state: IssuanceState, *, owner_capture_fsynced: bool) -> IssuanceState:
    _require(type(state) is IssuanceState and state.batch_release_issued and
             not state.batch_release_accepted and state.batch_release_outcome is ReleaseOutcome.NOT_SENT and
             owner_capture_fsynced is True, "FIXTURE_BATCH_ACCEPTANCE")
    return replace(state, batch_release_accepted=True, batch_release_outcome=ReleaseOutcome.ACCEPTED)


def finish_release(state: IssuanceState, outcome: ReleaseOutcome, *,
                   clean_closure_complete: bool = False) -> IssuanceState:
    _require(type(state) is IssuanceState and outcome in {ReleaseOutcome.CLEAN_REJECTED, ReleaseOutcome.UNKNOWN}
             and state.batch_release_outcome is ReleaseOutcome.NOT_SENT,
             "FIXTURE_RELEASE_OUTCOME")
    _require(state.delivery_issued, "FIXTURE_RELEASE_OUTCOME")
    if outcome is ReleaseOutcome.CLEAN_REJECTED:
        _require(clean_closure_complete is True, "FIXTURE_CLEAN_REJECTION_EVIDENCE")
        qualification = Qualification.BLOCKED_RETAINED
    else:
        _require(type(clean_closure_complete) is bool, "FIXTURE_RELEASE_OUTCOME")
        qualification = Qualification.UNKNOWN_RETAINED
    return replace(state, batch_release_outcome=outcome, qualification=qualification)


def finish_fixture(state: IssuanceState, qualification: Qualification, *,
                   complete_evidence: bool) -> IssuanceState:
    """Set a non-success terminal result without rewriting release history.

    This pure model cannot authenticate the outer capture, wait/EOF chain,
    guardian output history, or final seals required for a live match.  Keep the
    success enum for parsing A's state vocabulary, but never originate it here.
    """

    _require(type(state) is IssuanceState and state.batch_release_accepted and
             state.batch_release_outcome is ReleaseOutcome.ACCEPTED and
             state.qualification is Qualification.NOT_RUN and
             qualification in {Qualification.UNKNOWN_RETAINED, Qualification.FAILED_RETAINED} and
             type(complete_evidence) is bool,
             "FIXTURE_QUALIFICATION")
    if qualification is Qualification.FAILED_RETAINED:
        _require(complete_evidence, "FIXTURE_QUALIFICATION_EVIDENCE")
    return replace(state, qualification=qualification)


class Membership(str, Enum):
    CARRIER = "CARRIER"
    GUARDIAN = "GUARDIAN"


class ActionPhase(str, Enum):
    JOURNALED = "JOURNALED"
    CARRIER_ENTERED = "CARRIER_ENTERED"
    OWNER_COMMITTED = "OWNER_COMMITTED"
    GUARDIAN_REENTERED = "GUARDIAN_REENTERED"
    SLOT_SEALED = "SLOT_SEALED"
    RELEASED = "RELEASED"
    ERROR = "ERROR"


_ACTION_FLOW = (
    ActionPhase.JOURNALED,
    ActionPhase.CARRIER_ENTERED,
    ActionPhase.OWNER_COMMITTED,
    ActionPhase.GUARDIAN_REENTERED,
    ActionPhase.SLOT_SEALED,
    ActionPhase.RELEASED,
)


@dataclass(frozen=True)
class ActionRecord:
    counter: int
    kind: str
    case_id: str
    digest: str
    phase: ActionPhase = ActionPhase.JOURNALED
    owner_committed: bool = False
    attempted: bool = False
    attempt_result: str | None = None
    error: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return self.kind, self.case_id


@dataclass(frozen=True)
class ActionLedger:
    records: tuple[ActionRecord, ...] = ()
    membership: Membership = Membership.CARRIER
    initial_guardian_entered: bool = False
    carrier_writes: int = 0
    guardian_writes: int = 0
    final_carrier_entered: bool = False
    locked_reason: str | None = None
    modeled_only: bool = True
    durability_proven: bool = False
    live_proven: bool = False

    def __post_init__(self) -> None:
        _require(
            self.modeled_only is True
            and self.durability_proven is False
            and self.live_proven is False,
            "FIXTURE_ACTION_MODEL_ONLY",
        )

    @property
    def self_writes(self) -> int:
        return self.carrier_writes + self.guardian_writes


def enter_initial_guardian(ledger: ActionLedger) -> ActionLedger:
    _require(type(ledger) is ActionLedger and not ledger.initial_guardian_entered and
             ledger.membership is Membership.CARRIER and not ledger.records,
             "FIXTURE_INITIAL_GUARDIAN")
    return replace(ledger, membership=Membership.GUARDIAN, initial_guardian_entered=True,
                   guardian_writes=1)


def _action_plan() -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = [("native_batch", CASE_IDS[0])]
    for case_id in CASE_IDS:
        rows.extend((("clone", case_id), ("exec_go", case_id), ("g_go", case_id)))
    _require(len(rows) == MAX_ACTIONS, "FIXTURE_ACTION_PLAN")
    return tuple(rows)


ACTION_PLAN = _action_plan()


def begin_action(ledger: ActionLedger, *, kind: str, case_id: str, digest: str) -> ActionLedger:
    _require(type(ledger) is ActionLedger and ledger.initial_guardian_entered and
             ledger.membership is Membership.GUARDIAN and ledger.locked_reason is None and
             not ledger.final_carrier_entered, "FIXTURE_ACTION_STATE")
    _require(len(ledger.records) < MAX_ACTIONS and (kind, case_id) == ACTION_PLAN[len(ledger.records)],
             "FIXTURE_ACTION_ORDER")
    if ledger.records:
        previous = ledger.records[-1]
        _require(previous.phase is ActionPhase.RELEASED and previous.attempted,
                 "FIXTURE_ACTION_PREVIOUS_NOT_ATTEMPTED")
    record = ActionRecord(len(ledger.records) + 1, kind, case_id, _digest(digest))
    return replace(ledger, records=(*ledger.records, record))


def advance_action(ledger: ActionLedger, phase: ActionPhase) -> ActionLedger:
    _require(type(ledger) is ActionLedger and ledger.records and ledger.locked_reason is None,
             "FIXTURE_ACTION_STATE")
    current = ledger.records[-1]
    _require(current.phase in _ACTION_FLOW and type(phase) is ActionPhase,
             "FIXTURE_ACTION_PHASE")
    index = _ACTION_FLOW.index(current.phase)
    _require(index + 1 < len(_ACTION_FLOW) and phase is _ACTION_FLOW[index + 1],
             "FIXTURE_ACTION_PHASE")
    carrier_writes, guardian_writes, membership = ledger.carrier_writes, ledger.guardian_writes, ledger.membership
    owner_committed = current.owner_committed
    if phase is ActionPhase.CARRIER_ENTERED:
        _require(membership is Membership.GUARDIAN, "FIXTURE_ACTION_MEMBERSHIP")
        membership = Membership.CARRIER
        carrier_writes += 1
    elif phase is ActionPhase.OWNER_COMMITTED:
        _require(membership is Membership.CARRIER, "FIXTURE_ACTION_MEMBERSHIP")
        owner_committed = True
    elif phase is ActionPhase.GUARDIAN_REENTERED:
        _require(membership is Membership.CARRIER and owner_committed, "FIXTURE_ACTION_MEMBERSHIP")
        membership = Membership.GUARDIAN
        guardian_writes += 1
    elif phase in (ActionPhase.SLOT_SEALED, ActionPhase.RELEASED):
        _require(membership is Membership.GUARDIAN and owner_committed,
                 "FIXTURE_ACTION_MEMBERSHIP")
    updated = replace(current, phase=phase, owner_committed=owner_committed)
    result = replace(ledger, records=(*ledger.records[:-1], updated), membership=membership,
                     carrier_writes=carrier_writes, guardian_writes=guardian_writes)
    _require(result.carrier_writes <= 38 and result.guardian_writes <= 38 and
             result.self_writes <= MAX_SELF_WRITES, "FIXTURE_SELF_WRITE_BUDGET")
    return result


def fail_action(ledger: ActionLedger, *, reason: str) -> ActionLedger:
    _require(type(ledger) is ActionLedger and ledger.records and ledger.locked_reason is None and
             type(reason) is str and reason, "FIXTURE_ACTION_FAILURE")
    current = ledger.records[-1]
    _require(current.phase is not ActionPhase.RELEASED and current.phase is not ActionPhase.ERROR,
             "FIXTURE_ACTION_FAILURE")
    updated = replace(current, phase=ActionPhase.ERROR, error=reason)
    return replace(ledger, records=(*ledger.records[:-1], updated), locked_reason=reason)


def record_action_attempt(ledger: ActionLedger, *, result: str) -> ActionLedger:
    _require(type(ledger) is ActionLedger and ledger.records and ledger.locked_reason is None,
             "FIXTURE_ACTION_ATTEMPT")
    current = ledger.records[-1]
    _require(current.phase is ActionPhase.RELEASED and not current.attempted and
             result in {"SUCCEEDED", "FAILED", "SHORT"}, "FIXTURE_ACTION_ATTEMPT")
    updated = replace(current, attempted=True, attempt_result=result)
    locked = None if result == "SUCCEEDED" else "FIXTURE_ACTION_" + result
    return replace(ledger, records=(*ledger.records[:-1], updated), locked_reason=locked)


def enter_final_carrier(ledger: ActionLedger, *, write_performed: bool) -> ActionLedger:
    _require(type(ledger) is ActionLedger and ledger.initial_guardian_entered and
             not ledger.final_carrier_entered and type(write_performed) is bool,
             "FIXTURE_FINAL_CARRIER")
    carrier_writes = ledger.carrier_writes
    if write_performed:
        _require(ledger.membership is Membership.GUARDIAN and
                 (ledger.locked_reason is not None or not ledger.records or
                  (ledger.records[-1].phase is ActionPhase.RELEASED and
                   ledger.records[-1].attempted)),
                 "FIXTURE_FINAL_CARRIER")
        carrier_writes += 1
        membership = Membership.CARRIER
    else:
        _require(ledger.membership is Membership.CARRIER and ledger.locked_reason is not None,
                 "FIXTURE_FINAL_CARRIER")
        membership = Membership.CARRIER
    result = replace(ledger, carrier_writes=carrier_writes, membership=membership,
                     final_carrier_entered=True)
    _require(result.carrier_writes <= 38 and result.guardian_writes <= 38 and
             result.self_writes <= MAX_SELF_WRITES, "FIXTURE_SELF_WRITE_BUDGET")
    return result


def issued_action_bits(ledger: ActionLedger) -> dict[str, object]:
    _require(type(ledger) is ActionLedger, "FIXTURE_ACTION_LEDGER")
    cases = {case_id: {"clone_issued": False, "exec_go_issued": False, "g_go_issued": False}
             for case_id in CASE_IDS}
    native = False
    for record in ledger.records:
        # The append-only journal record is the issued bit.  Carrier movement,
        # owner ACK loss, or any later failure must never make it appear unused.
        if record.kind == "native_batch":
            native = True
        else:
            cases[record.case_id][record.kind + "_issued"] = True
    return {
        "modeled_only": True,
        "durability_proven": False,
        "live_proven": False,
        "fixture_native_batch_issued": native,
        "cases": cases,
    }


@dataclass(frozen=True)
class CpuLedger:
    start_sample_ns: int
    last_sample_ns: int
    membership: Membership
    rounding_ns: int
    guardian_ns: int = 0
    carrier_ns: int = 0
    handoff_sample_ns: int | None = None
    handoff_resumed: bool = False

    @property
    def process_sample_ns(self) -> int:
        return self.last_sample_ns


def begin_cpu_ledger(*, sample_ns: int, membership: Membership, rounding_ns: int) -> CpuLedger:
    _integer(sample_ns, "FIXTURE_CPU_SAMPLE")
    _require(type(membership) is Membership, "FIXTURE_CPU_MEMBERSHIP")
    _integer(rounding_ns, "FIXTURE_CPU_ROUNDING", 1, NS)
    initial_charge = sample_ns + rounding_ns
    return CpuLedger(
        sample_ns,
        sample_ns,
        membership,
        rounding_ns,
        guardian_ns=initial_charge if membership is Membership.GUARDIAN else 0,
        carrier_ns=initial_charge if membership is Membership.CARRIER else 0,
    )


def charge_cpu(ledger: CpuLedger, *, sample_ns: int, membership: Membership) -> CpuLedger:
    _require(type(ledger) is CpuLedger and membership is ledger.membership,
             "FIXTURE_CPU_MEMBERSHIP")
    _integer(sample_ns, "FIXTURE_CPU_SAMPLE", ledger.last_sample_ns)
    charge = sample_ns - ledger.last_sample_ns + ledger.rounding_ns
    if membership is Membership.GUARDIAN:
        return replace(ledger, last_sample_ns=sample_ns, guardian_ns=ledger.guardian_ns + charge)
    return replace(ledger, last_sample_ns=sample_ns, carrier_ns=ledger.carrier_ns + charge)


def migrate_cpu(ledger: CpuLedger, *, before_ns: int, after_ns: int,
                to_membership: Membership) -> CpuLedger:
    """Charge known old-domain time once and the ambiguous migration interval twice."""

    _require(type(ledger) is CpuLedger and type(to_membership) is Membership and
             to_membership is not ledger.membership, "FIXTURE_CPU_MIGRATION")
    _integer(before_ns, "FIXTURE_CPU_SAMPLE", ledger.last_sample_ns)
    _integer(after_ns, "FIXTURE_CPU_SAMPLE", before_ns)
    old = ledger.membership
    guardian, carrier = ledger.guardian_ns, ledger.carrier_ns
    known = before_ns - ledger.last_sample_ns
    if known or before_ns == ledger.last_sample_ns:
        known += ledger.rounding_ns
        if old is Membership.GUARDIAN:
            guardian += known
        else:
            carrier += known
    ambiguous = after_ns - before_ns + ledger.rounding_ns
    guardian += ambiguous
    carrier += ambiguous
    return replace(ledger, last_sample_ns=after_ns, membership=to_membership,
                   guardian_ns=guardian, carrier_ns=carrier)


def cpu_handoff(ledger: CpuLedger, *, sample_ns: int) -> CpuLedger:
    _require(type(ledger) is CpuLedger and ledger.membership is Membership.CARRIER and
             ledger.handoff_sample_ns is None, "FIXTURE_CPU_HANDOFF")
    charged = charge_cpu(ledger, sample_ns=sample_ns, membership=Membership.CARRIER)
    return replace(charged, handoff_sample_ns=sample_ns)


def cpu_resume_after_exec(ledger: CpuLedger, *, sample_ns: int) -> CpuLedger:
    _require(type(ledger) is CpuLedger and ledger.membership is Membership.CARRIER and
             ledger.handoff_sample_ns is not None and not ledger.handoff_resumed and
             ledger.last_sample_ns == ledger.handoff_sample_ns,
             "FIXTURE_CPU_RESUME")
    _integer(sample_ns, "FIXTURE_CPU_SAMPLE", ledger.handoff_sample_ns)
    charge = sample_ns - ledger.handoff_sample_ns + ledger.rounding_ns
    return replace(ledger, last_sample_ns=sample_ns, carrier_ns=ledger.carrier_ns + charge,
                   handoff_resumed=True)


def validate_cpu_limits(ledger: CpuLedger, *, success: bool, tail_cpu_ns: int = 0,
                        guardian_cpu_stat_usec: int | None = None) -> CpuLedger:
    _require(type(ledger) is CpuLedger and type(success) is bool, "FIXTURE_CPU_LIMIT")
    _integer(tail_cpu_ns, "FIXTURE_CPU_TAIL", 0, NS - 1)
    _require(ledger.guardian_ns <= 10 * NS and ledger.carrier_ns <= 10 * NS and
             ledger.process_sample_ns <= 20 * NS, "FIXTURE_CPU_PHYSICAL_LIMIT")
    if success:
        _require(tail_cpu_ns > 0 and type(guardian_cpu_stat_usec) is int and
                 0 <= guardian_cpu_stat_usec <= 9_000_000,
                 "FIXTURE_CPU_SUCCESS_CROSSCHECK")
        _require(ledger.guardian_ns <= 9 * NS and ledger.carrier_ns + tail_cpu_ns <= 9 * NS and
                 ledger.process_sample_ns + tail_cpu_ns <= 18 * NS, "FIXTURE_CPU_SUCCESS_LIMIT")
    return ledger


def validate_pre_action_cpu(ledger: CpuLedger, *, observed_sigxcpu: bool,
                            pending_sigxcpu: bool) -> CpuLedger:
    _require(type(ledger) is CpuLedger and type(observed_sigxcpu) is bool and
             type(pending_sigxcpu) is bool, "FIXTURE_PRE_ACTION_CPU")
    _require(ledger.process_sample_ns < 19 * NS and not observed_sigxcpu and
             not pending_sigxcpu, "FIXTURE_PRE_ACTION_CPU")
    return ledger


def segment_expiry(ledger: CpuLedger, *, now_process_ns: int,
                   envelope_ns: Mapping[str, int], stop_reserve_ns: Mapping[str, int],
                   fatal_overshoot_ns: int, remaining_success_ns: Mapping[str, int] | None = None,
                   tail_reserve_ns: Mapping[str, int] | None = None,
                   applicable_domains: Sequence[str] | None = None,
                   normal_worst_ns: int = 0) -> int:
    """Calculate A's earliest fail-closed process-clock expiry for one segment."""

    _require(type(ledger) is CpuLedger and type(envelope_ns) is dict and
             type(stop_reserve_ns) is dict, "FIXTURE_CPU_SEGMENT")
    _integer(now_process_ns, "FIXTURE_CPU_SAMPLE", ledger.last_sample_ns)
    _integer(fatal_overshoot_ns, "FIXTURE_CPU_OVERSHOOT", 1)
    _integer(normal_worst_ns, "FIXTURE_CPU_NORMAL_WORST")
    keys = {"guardian", "carrier", "process"}
    _require(set(envelope_ns) == keys and set(stop_reserve_ns) == keys, "FIXTURE_CPU_SEGMENT")
    if applicable_domains is None:
        applicable = ({"guardian"} if ledger.membership is Membership.GUARDIAN else {"carrier"}) | {"process"}
    else:
        _require(type(applicable_domains) in (tuple, list, set), "FIXTURE_CPU_SEGMENT")
        applicable = set(applicable_domains)
        _require(applicable <= {"guardian", "carrier"} and bool(applicable),
                 "FIXTURE_CPU_SEGMENT")
        applicable.add("process")
    current = {"guardian": ledger.guardian_ns, "carrier": ledger.carrier_ns, "process": now_process_ns}
    physical_limits = {"guardian": 10 * NS, "carrier": 10 * NS, "process": 20 * NS}
    candidates = []
    for name in sorted(applicable):
        envelope = _integer(envelope_ns[name], "FIXTURE_CPU_ENVELOPE")
        stop = _integer(stop_reserve_ns[name], "FIXTURE_CPU_STOP_RESERVE")
        margin = physical_limits[name] - current[name] - stop
        _require(envelope <= margin, "FIXTURE_CPU_STOP_RESERVE")
        candidates.append(now_process_ns + envelope)
        candidates.append(now_process_ns + margin)
    if remaining_success_ns is not None or tail_reserve_ns is not None:
        _require(type(remaining_success_ns) is dict and type(tail_reserve_ns) is dict and
                 set(remaining_success_ns) == keys and set(tail_reserve_ns) == keys,
                 "FIXTURE_CPU_SUCCESS_RESERVE")
        success_limits = {"guardian": 9 * NS, "carrier": 9 * NS, "process": 18 * NS}
        for name in sorted(applicable):
            remaining = _integer(remaining_success_ns[name], "FIXTURE_CPU_SUCCESS_RESERVE")
            tail = _integer(tail_reserve_ns[name], "FIXTURE_CPU_SUCCESS_RESERVE")
            margin = success_limits[name] - current[name] - remaining - tail
            _require(envelope_ns[name] <= margin, "FIXTURE_CPU_SUCCESS_RESERVE")
            candidates.append(now_process_ns + margin)
    expiry = min(candidates) - fatal_overshoot_ns
    _require(expiry > now_process_ns and now_process_ns + normal_worst_ns < expiry,
             "FIXTURE_CPU_FATAL_EXPIRY")
    return expiry


class NodePhase(str, Enum):
    ABSENT = "ABSENT"
    CREATED = "CREATED"
    CONFIGURED = "CONFIGURED"
    CONTROLLERS_ENABLED = "CONTROLLERS_ENABLED"
    INITIAL_VERIFIED = "INITIAL_VERIFIED"
    OCCUPIED = "OCCUPIED"
    EMPTY = "EMPTY"
    RECLAIMED = "RECLAIMED"
    FINAL_VERIFIED = "FINAL_VERIFIED"
    REMOVED = "REMOVED"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class Node:
    kind: str
    name: str
    phase: NodePhase = NodePhase.ABSENT


@dataclass(frozen=True)
class TreeState:
    batch: Node = Node("batch", "B")
    guardian: Node = Node("guardian", "guardian")
    supervisor: Node = Node("supervisor", "supervisor")
    active_case: Node | None = None
    completed_cases: tuple[str, ...] = ()
    anchor_d0: int = 0
    anchor_restored: bool = False


def new_tree(*, anchor_d0: int) -> TreeState:
    _integer(anchor_d0, "FIXTURE_ANCHOR_D0")
    return TreeState(anchor_d0=anchor_d0)


def _replace_node(tree: TreeState, node: Node) -> TreeState:
    if node.kind == "batch":
        return replace(tree, batch=node)
    if node.kind == "guardian":
        return replace(tree, guardian=node)
    if node.kind == "supervisor":
        return replace(tree, supervisor=node)
    _require(node.kind == "case" and tree.active_case is not None and tree.active_case.name == node.name,
             "FIXTURE_TREE_NODE")
    return replace(tree, active_case=node)


def create_node(tree: TreeState, kind: str, *, case_id: str | None = None) -> TreeState:
    _require(type(tree) is TreeState and kind in {"batch", "guardian", "supervisor", "case"},
             "FIXTURE_TREE_NODE")
    if kind == "batch":
        _require(tree.batch.phase is NodePhase.ABSENT, "FIXTURE_BATCH_CREATE")
        return replace(tree, batch=replace(tree.batch, phase=NodePhase.CREATED))
    _require(tree.batch.phase is NodePhase.INITIAL_VERIFIED, "FIXTURE_CHILD_BEFORE_BATCH")
    if kind == "guardian":
        _require(tree.guardian.phase is NodePhase.ABSENT, "FIXTURE_GUARDIAN_CREATE")
        return replace(tree, guardian=replace(tree.guardian, phase=NodePhase.CREATED))
    if kind == "supervisor":
        _require(tree.supervisor.phase is NodePhase.ABSENT, "FIXTURE_SUPERVISOR_CREATE")
        return replace(tree, supervisor=replace(tree.supervisor, phase=NodePhase.CREATED))
    _require(tree.guardian.phase is NodePhase.OCCUPIED and tree.supervisor.phase is NodePhase.OCCUPIED and
             tree.active_case is None and len(tree.completed_cases) < MAX_CASES and
             case_id == CASE_IDS[len(tree.completed_cases)], "FIXTURE_CASE_CREATE")
    return replace(tree, active_case=Node("case", case_id, NodePhase.CREATED))


def configure_node(tree: TreeState, kind: str) -> TreeState:
    _require(type(tree) is TreeState and kind in {"batch", "guardian", "supervisor", "case"},
             "FIXTURE_TREE_NODE")
    node = getattr(tree, kind) if kind in {"batch", "guardian", "supervisor"} else tree.active_case
    _require(type(node) is Node and node.phase is NodePhase.CREATED, "FIXTURE_NODE_CONFIGURE")
    return _replace_node(tree, replace(node, phase=NodePhase.CONFIGURED))


def enable_batch_controllers(tree: TreeState) -> TreeState:
    _require(type(tree) is TreeState and tree.batch.phase is NodePhase.CONFIGURED,
             "FIXTURE_BATCH_CONTROLLERS")
    return replace(tree, batch=replace(tree.batch, phase=NodePhase.CONTROLLERS_ENABLED))


def verify_node_initial(tree: TreeState, kind: str, snapshot: CgroupSnapshot) -> TreeState:
    _require(type(tree) is TreeState and kind in {"batch", "guardian", "supervisor", "case"},
             "FIXTURE_TREE_NODE")
    node = getattr(tree, kind) if kind in {"batch", "guardian", "supervisor"} else tree.active_case
    expected = NodePhase.CONTROLLERS_ENABLED if kind == "batch" else NodePhase.CONFIGURED
    _require(type(node) is Node and node.phase is expected, "FIXTURE_NODE_INITIAL_PHASE")
    validate_initial_snapshot(snapshot)
    return _replace_node(tree, replace(node, phase=NodePhase.INITIAL_VERIFIED))


def occupy_leaf(tree: TreeState, kind: str) -> TreeState:
    _require(kind in {"guardian", "supervisor", "case"}, "FIXTURE_LEAF_OCCUPY")
    node = getattr(tree, kind) if kind != "case" else tree.active_case
    _require(type(node) is Node and node.phase is NodePhase.INITIAL_VERIFIED,
             "FIXTURE_LEAF_OCCUPY")
    return _replace_node(tree, replace(node, phase=NodePhase.OCCUPIED))


def empty_leaf(tree: TreeState, kind: str) -> TreeState:
    _require(kind in {"guardian", "supervisor", "case"}, "FIXTURE_LEAF_EMPTY")
    node = getattr(tree, kind) if kind != "case" else tree.active_case
    _require(type(node) is Node and node.phase is NodePhase.OCCUPIED, "FIXTURE_LEAF_EMPTY")
    if kind == "supervisor":
        _require(tree.active_case is None, "FIXTURE_SUPERVISOR_HAS_CASE")
    if kind == "guardian":
        _require(tree.active_case is None and tree.supervisor.phase is NodePhase.CLOSED,
                 "FIXTURE_GUARDIAN_HAS_CHILDREN")
    return _replace_node(tree, replace(node, phase=NodePhase.EMPTY))


def reclaim_node(tree: TreeState, kind: str, state: ReclaimState) -> TreeState:
    _require(type(tree) is TreeState and kind in {"batch", "guardian", "supervisor", "case"},
             "FIXTURE_TREE_NODE")
    node = getattr(tree, kind) if kind in {"batch", "guardian", "supervisor"} else tree.active_case
    expected = NodePhase.INITIAL_VERIFIED if kind == "batch" else NodePhase.EMPTY
    _require(type(node) is Node and node.phase is expected, "FIXTURE_NODE_RECLAIM_PHASE")
    if kind == "batch":
        _require(tree.active_case is None and tree.guardian.phase is NodePhase.CLOSED and
                 tree.supervisor.phase is NodePhase.CLOSED, "FIXTURE_BATCH_HAS_CHILDREN")
    require_reclaimed(state)
    return _replace_node(tree, replace(node, phase=NodePhase.RECLAIMED))


def verify_node_final(tree: TreeState, kind: str, snapshot: CgroupSnapshot) -> TreeState:
    _require(type(tree) is TreeState and kind in {"batch", "guardian", "supervisor", "case"},
             "FIXTURE_TREE_NODE")
    node = getattr(tree, kind) if kind in {"batch", "guardian", "supervisor"} else tree.active_case
    _require(type(node) is Node and node.phase is NodePhase.RECLAIMED, "FIXTURE_NODE_FINAL_PHASE")
    validate_final_snapshot(snapshot, kind)
    return _replace_node(tree, replace(node, phase=NodePhase.FINAL_VERIFIED))


def remove_node(tree: TreeState, kind: str) -> TreeState:
    _require(type(tree) is TreeState and kind in {"batch", "guardian", "supervisor", "case"},
             "FIXTURE_TREE_NODE")
    node = getattr(tree, kind) if kind in {"batch", "guardian", "supervisor"} else tree.active_case
    _require(type(node) is Node and node.phase is NodePhase.FINAL_VERIFIED,
             "FIXTURE_NODE_REMOVE_PHASE")
    return _replace_node(tree, replace(node, phase=NodePhase.REMOVED))


def close_node(tree: TreeState, kind: str, *, parent_dying_descendants: int,
               anchor_descendants: int | None = None) -> TreeState:
    _require(type(tree) is TreeState and kind in {"batch", "guardian", "supervisor", "case"},
             "FIXTURE_TREE_NODE")
    node = getattr(tree, kind) if kind in {"batch", "guardian", "supervisor"} else tree.active_case
    _require(type(node) is Node and node.phase is NodePhase.REMOVED and
             type(parent_dying_descendants) is int and parent_dying_descendants == 0,
             "FIXTURE_NODE_CLOSE")
    tree = _replace_node(tree, replace(node, phase=NodePhase.CLOSED))
    if kind == "case":
        _require(tree.active_case is not None, "FIXTURE_CASE_CLOSE")
        completed = (*tree.completed_cases, tree.active_case.name)
        return replace(tree, completed_cases=completed, active_case=None)
    if kind == "batch":
        _require(type(anchor_descendants) is int and anchor_descendants == tree.anchor_d0,
                 "FIXTURE_ANCHOR_NOT_RESTORED")
        return replace(tree, anchor_restored=True)
    return tree


def validate_tree_success(tree: TreeState) -> TreeState:
    _require(type(tree) is TreeState and tree.completed_cases == CASE_IDS and
             tree.active_case is None and tree.supervisor.phase is NodePhase.CLOSED and
             tree.guardian.phase is NodePhase.CLOSED and tree.batch.phase is NodePhase.CLOSED and
             tree.anchor_restored,
             "FIXTURE_TREE_NOT_SUCCESSFULLY_CLOSED")
    return tree


@dataclass(frozen=True)
class NativeCapability:
    status: str
    reason: str
    native_pass: bool = False

    def __post_init__(self) -> None:
        _require(self.status in {"NOT_RUN", "ELIGIBLE_NOT_EXECUTED"},
                 "FIXTURE_NATIVE_STATUS")
        _require(type(self.reason) is str and 1 <= len(self.reason) <= 128 and
                 re.fullmatch(r"[A-Z][A-Z0-9_]*", self.reason) is not None,
                 "FIXTURE_NATIVE_REASON")
        _require(self.native_pass is False, "FIXTURE_NATIVE_PASS_FORBIDDEN")


def native_capability(*, explicit_fixture: bool, linux: bool, root: bool,
                      cgroup2: bool, cgroup_writable: bool, bridge_built: bool) -> NativeCapability:
    """Classify prerequisites without probing or upgrading them to native PASS."""

    values = (explicit_fixture, linux, root, cgroup2, cgroup_writable, bridge_built)
    _require(all(type(value) is bool for value in values), "FIXTURE_NATIVE_FACTS")
    checks = (
        (explicit_fixture, "NOT_RUN_NO_EXPLICIT_FIXTURE"),
        (linux, "NOT_RUN_NON_LINUX"),
        (root, "NOT_RUN_ROOT_REQUIRED"),
        (cgroup2, "NOT_RUN_CGROUP2_REQUIRED"),
        (cgroup_writable, "NOT_RUN_CGROUP_WRITE_REQUIRED"),
        (bridge_built, "NOT_RUN_BRIDGE_REQUIRED"),
    )
    for ok, reason in checks:
        if not ok:
            return NativeCapability("NOT_RUN", reason)
    return NativeCapability("ELIGIBLE_NOT_EXECUTED", "NATIVE_EXECUTION_REQUIRES_SEPARATE_EXPLICIT_ENTRY")


__all__ = [name for name in globals() if not name.startswith("_")]
