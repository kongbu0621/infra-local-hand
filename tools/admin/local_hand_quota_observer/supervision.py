"""Q1 bounded capture and independent-exit decision core; no launch capability.

An eventual trusted manager adapter supplies OS observations. Job input and the
query's JSON MUST NOT supply those observations. This module cannot authenticate
them, persist a launch intent or create a systemd unit. There is deliberately no
start/retry method: missing output after recovery stays missing.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import stat

from .admission import (MAX_REPORT_BYTES, Manifest, Rejected, Slot, integer,
                        match_report, require, token)


@dataclass(frozen=True)
class Binding:
    manifest: Manifest
    slot: Slot
    request_id: str
    allocation_digest: str
    execution_id: str
    phase: str
    issued_ns: int
    deadline_ns: int
    unit: str
    cgroup: str


def bind_query(manifest, *, slot_ref, generation, request_id, allocation_digest,
               execution_id, phase, now_ns, phase_deadline_ns):
    """Freeze one internal Q1 observation. Reopening it must retain this object.

    This does not grant an allocation or persist/deduplicate a request. Its caller
    must do both before any future manager delivery; that Q2 boundary is absent.
    """
    require(type(manifest) is Manifest, "MANIFEST_REQUIRED")
    slot = manifest.slot(slot_ref, generation)
    token(request_id, r"[0-9a-f]{32}")
    token(allocation_digest, r"[0-9a-f]{64}")
    token(execution_id, r"[0-9a-f]{32}")
    require(type(phase) is str and phase in ("preflight", "business", "reconcile", "evidence"), "PHASE")
    integer(now_ns)
    integer(phase_deadline_ns, now_ns + 1)
    deadline = min(phase_deadline_ns, integer(now_ns + manifest.max_query_ns))
    identity = [manifest.digest, slot.ref, slot.generation, request_id, allocation_digest, execution_id, phase]
    unit = "lhq-" + hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest() + ".service"
    return Binding(manifest, slot, request_id, allocation_digest, execution_id, phase,
                   now_ns, deadline, unit, manifest.cgroup_parent + "/" + unit)


@dataclass(frozen=True)
class UnitObservation:
    """Internal facts from a manager, never a deserialized worker receipt.

    delivery_settled: original launcher can no longer enqueue a start.
    admission_fenced: the durable start is consumed, restart/activation disabled.
    collectors_stopped: ALL auxiliary launcher/capture processes are proven gone.
    cgroup_empty: recursive cgroup.events populated=0, not just an empty main PID.
    A stop ACK, killed launcher, missing unit or absent cgroup is insufficient.
    """
    boot_id: str
    unit: str
    invocation_id: str
    cgroup: str
    observed_ns: int
    delivery_settled: bool
    admission_fenced: bool
    job_empty: bool
    unit_terminal: bool
    cgroup_empty: bool
    collectors_stopped: bool
    exec_main_code: int | None
    exec_main_status: int | None
    # Explicit evidence source: a fixed dedicated ancestor can prove recursive
    # emptiness after systemd prunes the leaf. Its identity is verified by the
    # trusted manager adapter; absence of either directory is never populated=0.
    empty_cgroup: str | None = None


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    query_stopped: bool = False
    facts_match: bool = False
    # This core never makes a resource-release, authentication or E3 decision.
    admission_proven: bool = False
    real_e3_accepted: bool = False
    production_supported: bool = False


class QueryMonitor:
    """Storage-free bounded collection for ONE previously recorded query intent.

    feed/eof support adapters that already own a nonblocking pipe. read_once is a
    one-read helper for an exclusively owned, nonblocking pipe FD. No method opens
    the target root, waits for a child, reads result files, starts or retries work.
    Resource retention/durable deduplication belong to the future service.
    """
    def __init__(self, binding, *, recovered=False, original_invocation=None):
        require(type(binding) is Binding and type(recovered) is bool, "BINDING_REQUIRED")
        if original_invocation is not None:
            token(original_invocation, r"[0-9a-f]{32}")
        self.binding = binding
        self._raw = bytearray()
        self._eof = False
        self._invocation = original_invocation
        self._recovered = recovered
        self._reason = "OUTPUT_LOST_ON_RECOVERY" if recovered else None
        self._last_ns = binding.issued_ns
        self._pipe_identity = None
        self._finished = None

    @property
    def raw_prefix(self):
        """At most MAX_REPORT_BYTES original bytes; never replace them by zeros."""
        return bytes(self._raw)

    @property
    def invocation_id(self):
        return self._invocation

    def _fail(self, code):
        if self._reason is None:
            self._reason = code

    def _clock(self, now_ns):
        try:
            integer(now_ns, self._last_ns)
        except Rejected:
            self._fail("CLOCK_UNCERTAIN")
            return False
        self._last_ns = now_ns
        if now_ns >= self.binding.deadline_ns:
            self._fail("DEADLINE_EXPIRED")
        return True

    def _open(self):
        require(self._finished is None, "MONITOR_FINISHED")

    def feed(self, data, *, now_ns):
        self._open()
        self._clock(now_ns)
        if type(data) is not bytes:
            self._fail("PIPE_DATA_TYPE")
            return
        if self._eof:
            self._fail("BYTES_AFTER_EOF")
            return
        remaining = MAX_REPORT_BYTES - len(self._raw)
        self._raw.extend(data[:remaining])
        if len(data) > remaining:
            self._fail("OUTPUT_LIMIT")

    def eof(self, *, now_ns):
        self._open()
        self._clock(now_ns)
        self._eof = True

    def read_once(self, fd, *, now_ns):
        """One bounded os.read, no select/wait loop, no descriptor ownership swap.

        The caller retains/ closes fd, and must not reuse it or toggle O_NONBLOCK
        concurrently. A missing EOF never becomes a successful empty result.
        """
        self._open()
        self._clock(now_ns)
        if self._eof:
            return
        try:
            integer(fd, 0, 2**31 - 1)
            observed = os.fstat(fd)
            require(stat.S_ISFIFO(observed.st_mode) and not os.get_blocking(fd), "NONBLOCKING_PIPE_REQUIRED")
            identity = (fd, observed.st_dev, observed.st_ino)
            require(self._pipe_identity in (None, identity), "PIPE_CHANGED")
            self._pipe_identity = identity
            data = os.read(fd, min(4096, MAX_REPORT_BYTES + 1 - len(self._raw)))
        except BlockingIOError:
            return
        except (OSError, Rejected) as error:
            self._fail(str(error) if isinstance(error, Rejected) else "PIPE_IO_UNCERTAIN")
            return
        if data:
            self.feed(data, now_ns=now_ns)
        else:
            self.eof(now_ns=now_ns)

    def _observe(self, observation, now_ns):
        require(type(observation) is UnitObservation, "UNIT_OBSERVATION_REQUIRED")
        require(not self._recovered or self._invocation is not None, "ORIGINAL_INVOCATION_REQUIRED")
        binding = self.binding
        require(observation.boot_id == binding.manifest.boot_id and observation.unit == binding.unit
                and observation.cgroup == binding.cgroup, "PROCESS_IDENTITY_CHANGED")
        token(observation.invocation_id, r"[0-9a-f]{32}")
        integer(observation.observed_ns, binding.issued_ns)
        require(observation.observed_ns == now_ns, "STALE_UNIT_OBSERVATION")
        require(self._invocation in (None, observation.invocation_id), "INVOCATION_CHANGED")
        self._invocation = observation.invocation_id
        flags = (observation.delivery_settled, observation.admission_fenced, observation.job_empty,
                 observation.unit_terminal, observation.cgroup_empty, observation.collectors_stopped)
        require(all(type(flag) is bool for flag in flags), "UNIT_FACT_TYPE")
        require(observation.empty_cgroup in (None, binding.cgroup, binding.manifest.cgroup_parent),
                "EMPTY_CGROUP_CHANGED")
        for number in (observation.exec_main_code, observation.exec_main_status):
            if number is not None:
                integer(number, 0, 2**31 - 1)
        return all(flags)

    def inspect(self, observation, *, now_ns):
        """Independent exit facts plus full EOF plus matching raw facts.

        UNKNOWN is sticky for data/identity/deadline errors. An incomplete live
        observation can later resolve, using the SAME invocation. Even after an
        error, original-identity stop facts may still be recorded independently.
        """
        if self._finished is not None:
            return self._finished
        clock_valid = self._clock(now_ns)
        stopped = False
        try:
            require(clock_valid, "CLOCK_UNCERTAIN")
            stopped = self._observe(observation, now_ns)
        except Rejected as error:
            self._fail(str(error))
        if self._reason:
            return Decision("UNKNOWN", self._reason, query_stopped=stopped)
        if not stopped:
            return Decision("WAITING", "EXIT_UNPROVEN")
        if not self._eof:
            return Decision("WAITING", "PIPE_EOF_REQUIRED", query_stopped=True)
        if observation.exec_main_code != 1 or observation.exec_main_status != 0:
            self._fail("QUERY_EXIT_UNSUCCESSFUL")
            return Decision("UNKNOWN", self._reason, query_stopped=True)
        try:
            match_report(bytes(self._raw), self.binding.manifest, self.binding.slot)
        except Rejected as error:
            self._fail(str(error))
            return Decision("UNKNOWN", self._reason, query_stopped=True)
        self._finished = Decision("OBSERVED", "PINNED_FACTS_MATCH", query_stopped=True, facts_match=True)
        return self._finished
