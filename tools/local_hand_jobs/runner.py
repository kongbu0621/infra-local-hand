"""Bounded asynchronous supervisor using predelegated systemd/cgroup v2.

No process-group fallback exists. A manager supplied by trusted Python code is
an integration seam for tests; no environment or transport field can select it.
Control methods perform no storage reads or subprocess waits. Slow work is
owned by an execution identity and runs in the host process manager.
"""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass, field
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import struct
import subprocess
import sys
import threading
import time
from typing import Mapping

if __package__:
    from . import bootstrap, bootstrap_roots, budget, ledger_jobs
    from .contract import JobError
else:  # fixed -I script entry: importing only this installed sibling
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from local_hand_jobs import bootstrap, bootstrap_roots, budget, ledger_jobs
    from local_hand_jobs.contract import JobError


class RunnerError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class _NoStartError(RunnerError):
    """Internal manager proof that no delivery was attempted, not an error-code inference."""


def _plain(value):
    if isinstance(value, Mapping): return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [_plain(v) for v in value]
    return value


def _unknown(reason="process ownership not yet proven"):
    return {"state": "UNKNOWN", "future_start_blocked": False, "tree_exited": False,
            "collectors_stopped": False, "writers_stopped": False, "effects_checked": False,
            "exit_code": None, "facts": {}, "result": {}, "missing": [reason]}


@dataclass
class _Execution:
    handle: dict
    plan: dict
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)
    proof: dict = field(default_factory=_unknown)
    manager_handle: object = None
    launch_complete: bool = False


class Runner:
    """The broker owns durable intentions and its startup/cancel fence."""
    def __init__(self, manager=None):
        self.manager = manager if manager is not None else SystemdManager()
        self._executions = {}
        self._lock = threading.Lock()

    def set_start_guard(self, callback):
        """Bind the broker's durable startup/cancel fence in trusted code only."""
        if not callable(callback):
            raise RunnerError("UNSUPPORTED", "trusted startup guard must be callable")
        if hasattr(self.manager, "set_start_guard"):
            self.manager.set_start_guard(callback)

    def start(self, job_key, execution_id, plan):
        """Reserve a unique identity and enqueue; never wait on external I/O."""
        if not isinstance(execution_id, str) or not re.fullmatch(r"[a-zA-Z0-9:_.-]{1,200}", execution_id):
            raise RunnerError("UNSUPPORTED", "invalid server execution identity")
        frozen = _plain(plan)
        phase = frozen.get("phase", "business")
        if phase not in ("preflight", "business", "reconcile", "evidence"):
            raise RunnerError("UNSUPPORTED", "unknown fixed execution phase")
        identity = {"job_key": str(job_key), "execution_id": execution_id, "phase": phase,
                    "unit": "lhj-" + hashlib.sha256(execution_id.encode()).hexdigest() + ".service"}
        with self._lock:
            if execution_id in self._executions:
                raise RunnerError("CONFLICT", "an execution identity is never started twice")
            item = _Execution(identity, frozen)
            self._executions[execution_id] = item
        threading.Thread(target=self._supervise, args=(item,), daemon=True,
                         name="lh-supervisor-" + execution_id[-12:]).start()
        return dict(identity)

    @staticmethod
    def _same_handle(left, right):
        return all(left.get(key) == right.get(key) for key in ("job_key", "execution_id", "phase", "unit"))

    def reattach(self, handle, plan):
        """Reobserve the original identity; never call manager.start again."""
        execution_id = handle.get("execution_id")
        if not isinstance(execution_id, str) or not re.fullmatch(r"[a-zA-Z0-9:_.-]{1,200}", execution_id):
            raise RunnerError("UNSUPPORTED", "invalid recovery identity")
        unit = "lhj-" + hashlib.sha256(execution_id.encode()).hexdigest() + ".service"
        if handle.get("unit", unit) != unit:
            raise RunnerError("CONFLICT", "recovery unit does not match execution")
        identity = dict(handle, unit=unit, phase=handle.get("phase", plan.get("phase", "business")),
                        job_key=handle.get("job_key", plan.get("operation_id", "")))
        with self._lock:
            if execution_id in self._executions:
                if not self._same_handle(self._executions[execution_id].handle, identity):
                    raise RunnerError("CONFLICT", "recovery identity differs")
                return dict(self._executions[execution_id].handle)
            item = _Execution(identity, dict(_plain(plan), _reattach=True))
            self._executions[execution_id] = item
        threading.Thread(target=self._supervise, args=(item,), daemon=True,
                         name="lh-reattach-" + execution_id[-12:]).start()
        return dict(identity)

    def inspect(self, handle):
        """Return the latest local observation; this is not a fresh storage scan."""
        item = self._executions.get(handle.get("execution_id"))
        if item is None or not self._same_handle(item.handle, handle):
            return _unknown("execution must be reconciled with the manager after restart")
        with item.lock:
            return _plain(item.proof)

    def stop(self, handle):
        """Queue controlled stopping. Only a later manager proof can prove exit."""
        item = self._executions.get(handle.get("execution_id"))
        if item is None or not self._same_handle(item.handle, handle):
            return _unknown("unknown prior manager request; future start not disproven")
        item.cancel.set()
        return self.inspect(handle)

    def _supervise(self, item):
        try:
            # The manager performs its own support and OS-boundary checks here,
            # outside the broker fence and database transactions.
            if item.cancel.is_set() and not item.plan.get("_reattach"):
                proof = _unknown()
                proof.update(state="EXITED", future_start_blocked=True, tree_exited=True,
                             collectors_stopped=True, writers_stopped=True, effects_checked=True,
                             exit_code=None, result={"outcome": "CANCELLED", "business_started": False, "helper_started": False}, missing=[])
                with item.lock: item.proof = proof
                return
            delivery_error = None
            try:
                handle = (self.manager.reattach(item.handle, item.plan, item.cancel) if item.plan.get("_reattach")
                          else self.manager.start(item.handle, item.plan, item.cancel))
            except Exception as error:
                # A manager can retain a delivered request even when returning
                # its receipt failed. Adopt only that exact in-memory identity;
                # never retry start or reinterpret the exception as no-start.
                if isinstance(error, _NoStartError) or item.plan.get("_reattach"):
                    raise
                recover = getattr(self.manager, "_retained_delivery", None)
                handle = recover(item.handle) if recover is not None else None
                if handle is None:
                    raise
                delivery_error = getattr(error, "code", "IO_UNCERTAIN")
            item.manager_handle = handle
            item.launch_complete = True
            while True:
                try:
                    if item.cancel.is_set(): self.manager.stop(handle)
                    proof = self.manager.inspect(handle)
                except RunnerError as error:
                    # A missing observation or stop acknowledgement says nothing
                    # about the execution's lifetime. Keep its original handle
                    # and observer alive so later cancellation still reaches it.
                    proof = _unknown(str(error))
                    proof["result"] = {"outcome": "UNKNOWN", "error": error.code}
                except Exception:
                    proof = _unknown("manager observation is uncertain")
                    if delivery_error is not None:
                        proof["result"] = {"outcome": "UNKNOWN", "error": delivery_error}
                if hasattr(self.manager, "export_handle"):
                    try:
                        proof["recovery_handle"] = self.manager.export_handle(handle)
                    except Exception:
                        proof = _unknown("manager recovery identity is uncertain")
                with item.lock: item.proof = _plain(proof)
                if proof.get("state") == "EXITED" and proof.get("future_start_blocked") and proof.get("tree_exited"):
                    return
                if proof.get("terminal_observation"):
                    return
                item.cancel.wait(0.05) if not item.cancel.is_set() else time.sleep(0.05)
        except RunnerError as error:
            proof = _unknown(str(error))
            proof["result"] = {"outcome": "UNKNOWN", "error": error.code}
            # Only an explicit manager no-delivery proof establishes no-start.
            if isinstance(error, _NoStartError) and not item.launch_complete and not item.plan.get("_reattach"):
                proof.update(state="EXITED", future_start_blocked=True, tree_exited=True,
                             collectors_stopped=True, writers_stopped=True, effects_checked=True,
                             result={"outcome": "FAILED", "error": error.code, "business_started": False, "helper_started": False}, missing=[])
            with item.lock: item.proof = proof
        except BaseException:
            with item.lock: item.proof = _unknown("manager operation is uncertain")


class _Dqblk(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ("bhard", "bsoft", "curspace", "ihard", "isoft", "curinodes", "btime", "itime")] + [("valid", ctypes.c_uint32)]


def _mount_for(path):
    """The fixed /proc observation is allowed only in the supervised worker."""
    candidates = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        fields, fs = left.split(), right.split()
        target = fields[4].replace("\\040", " ")
        if Path(path) == Path(target) or Path(target) in Path(path).parents:
            candidates.append({"id": fields[0], "root": fields[3], "target": target,
                               "type": fs[0], "source": fs[1], "options": fields[5] + "," + fs[2]})
    if not candidates: raise RunnerError("UNSUPPORTED", "mount identity unavailable")
    return max(candidates, key=lambda item: len(item["target"]))


def _verify_project_quota(path, byte_limit, *, expected_identity=None):
    """Require a real inherited kernel project hard quota, not a config bool."""
    mount = _mount_for(path)
    if mount["type"] not in ("ext4", "xfs"):
        raise RunnerError("UNSUPPORTED", "project quota filesystem is unsupported")
    existing = Path(path)
    while not existing.exists(): existing = existing.parent
    if existing.resolve() != existing: raise RunnerError("UNSUPPORTED", "linked writable root")
    descriptor = os.open(existing, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    original_error = None
    try:
        if expected_identity is not None:
            info = os.fstat(descriptor)
            if (str(existing) != str(path) or (info.st_dev, info.st_ino, info.st_uid) != (
                    expected_identity["device"], expected_identity["inode"], expected_identity["uid"])):
                raise RunnerError("IO_UNCERTAIN", "Quota observation belongs to another root identity")
        fsx = bytearray(28)
        fcntl.ioctl(descriptor, 0x801C581F, fsx, True)  # FS_IOC_FSGETXATTR
        flags, _, _, project_id, _ = struct.unpack("=IIIII", fsx[:20])
        if not project_id or not flags & 0x200:
            raise RunnerError("UNSUPPORTED", "inherited project quota missing")
        quota = _Dqblk()
        library = ctypes.CDLL(None, use_errno=True)
        # Q_GETQUOTA / PRJQUOTA is a fixed, read-only kernel query.
        rc = library.quotactl((0x800007 << 8) | 2, os.fsencode(mount["source"]), project_id, ctypes.byref(quota))
        if rc or not quota.bhard or quota.bhard * 1024 > byte_limit:
            raise RunnerError("UNSUPPORTED", "finite admitted project hard quota not proven")
        return {"project_id": project_id, "hard_bytes": quota.bhard * 1024, "mount": mount}
    except OSError as error:
        original_error = RunnerError("UNSUPPORTED", "project hard quota cannot be verified")
        raise original_error from error
    except BaseException as error:
        original_error = error
        raise
    finally:
        ledger_jobs._close_input(descriptor, original_error)


def _runtime_microseconds(grant, now=None):
    """Reserve the full stop grace inside the phase/operation wall envelope."""
    remaining = budget.phase_remaining_ns(grant, now=now)
    limits = grant["limits"]
    runtime = min(limits["wall_seconds"] * budget.NANOSECONDS, remaining)
    runtime -= limits["terminate_grace_seconds"] * budget.NANOSECONDS
    runtime //= 1000  # systemd time spans are encoded as integer microseconds.
    if runtime <= 0:
        raise JobError("LIMIT_EXCEEDED", "No helper runtime remains after its required stop grace")
    return runtime


def _cpu_quota(limits):
    # Always divide by the full envelope (runtime + reserved stop grace).
    # Six decimal places are floored using integers, never rounded upward.
    millionths = min(100_000_000, limits["cpu_seconds"] * 100_000_000 // limits["wall_seconds"])
    # systemd permits a period up to 1 s and requires at least a 1 ms quota.
    # Smaller requested rates cannot be represented without exceeding the cap.
    if millionths < 100_000:
        raise RunnerError("UNSUPPORTED", "CPU quota cannot be represented within its admitted envelope")
    whole, fraction = divmod(millionths, 1_000_000)
    return f"{whole}.{fraction:06d}%"


def _deadline_remaining(deadline):
    grant, phase_deadline = deadline
    now = budget.current_clock()
    remaining = min(budget.remaining_ns(grant, now=now), phase_deadline - now["boottime_ns"])
    if remaining <= 0:
        raise JobError("LIMIT_EXCEEDED", "Helper runtime deadline is exhausted")
    return remaining


class SystemdManager:
    """Manage only one fixed lhj-<execution digest>.service namespace.

    The host administrator supplies an existing delegated slice and account.
    This object never creates a slice, mounts storage, changes quotas, or grants
    delegation. Missing OS capabilities produce UNSUPPORTED, including here in
    a container with non-systemd PID 1 and read-only cgroup v2.
    """
    def __init__(self, configuration=None):
        self.configuration = _plain(configuration or {})
        self._runs = {}
        self._start_guard = None

    def set_start_guard(self, callback):
        if not callable(callback):
            raise RunnerError("UNSUPPORTED", "trusted startup guard must be callable")
        if self._start_guard is not None:
            raise RunnerError("CONFLICT", "the process manager already belongs to a broker startup fence")
        self._start_guard = callback

    def support(self):
        # Both launch stages are implemented, but this candidate has no real
        # delegated-host integration evidence. No configuration switch promotes
        # synthetic manager tests into production support.
        reasons = ["E3_SUPERVISION_UNVERIFIED"]
        if sys.platform != "linux": reasons.append("Linux is required")
        try:
            if Path("/proc/1/comm").read_text().strip() != "systemd": reasons.append("PID 1 is not systemd")
            if not Path("/sys/fs/cgroup/cgroup.controllers").is_file(): reasons.append("cgroup v2 is unavailable")
            delegated = self.configuration.get("cgroup")
            if delegated and (not delegated.startswith("/sys/fs/cgroup/") or
                              not os.access(Path(delegated) / "cgroup.procs", os.W_OK)):
                reasons.append("admitted cgroup subtree is not delegated")
        except OSError: reasons.append("host supervision facts unreadable")
        config = self.configuration
        if not config: reasons.append("no predelegated manager admission")
        if config.get("uid") != os.geteuid() or os.geteuid() == 0: reasons.append("dedicated non-root account is required")
        return {"supported": not reasons, "status": "UNSUPPORTED" if reasons else "CANDIDATE", "reasons": reasons}

    def scan(self, known_units=()):
        """Bounded manager inventory; orphan identities retain resource barriers."""
        support = self.support()
        if not support["supported"]: return {"status": "UNSUPPORTED", "orphans": [], "reasons": support["reasons"]}
        found = self._command("list-units", "lhj-*.service", "--all", "--plain", "--no-legend")
        if found.returncode: return {"status": "UNKNOWN", "orphans": [], "reasons": ["manager inventory failed"]}
        units = [line.split()[0] for line in found.stdout.decode().splitlines() if line.strip()]
        if len(units) > 10000: return {"status": "UNKNOWN", "orphans": [], "reasons": ["manager inventory exceeds bound"]}
        orphans = sorted(set(units) - set(known_units))
        return {"status": "UNKNOWN" if orphans else "READY", "orphans": orphans, "observed_units": units}

    def _command(self, *arguments, timeout=3):
        # Even a unit inventory is bounded while captured, not after allocation.
        command = ["/usr/bin/systemctl", "--user", *arguments]
        process = None
        selector = selectors.DefaultSelector()
        captured = bytearray()
        original_error = None
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={"PATH": "/usr/bin:/bin", "XDG_RUNTIME_DIR": "/run/user/" + str(os.geteuid())})
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + timeout
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise RunnerError("IO_UNCERTAIN", "manager observation timeout")
                for key, _ in selector.select(min(0.05, max(0, deadline - time.monotonic()))):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj); continue
                    if len(captured) + len(chunk) > 1024 * 1024:
                        raise RunnerError("IO_UNCERTAIN", "manager output exceeds bound")
                    captured.extend(chunk)
            returncode = process.wait(timeout=max(0.01, deadline - time.monotonic()))
            return subprocess.CompletedProcess(command, returncode, bytes(captured))
        except (OSError, subprocess.TimeoutExpired) as error:
            original_error = RunnerError("IO_UNCERTAIN", "process manager observation did not complete")
            raise original_error from error
        except BaseException as error:
            original_error = error
            raise
        finally:
            cleanup_error = None
            def cleanup(action):
                nonlocal cleanup_error
                try: action()
                except BaseException as error:
                    if cleanup_error is None: cleanup_error = error
            if process is not None:
                if process.poll() is None:
                    cleanup(process.kill)
                cleanup(lambda: process.wait(timeout=0.2))
                cleanup(process.stdout.close)
            cleanup(selector.close)
            if cleanup_error is not None:
                if original_error is not None:
                    original_error.add_note("manager client cleanup was incomplete")
                else:
                    raise RunnerError("IO_UNCERTAIN", "manager client cleanup was incomplete") from cleanup_error

    def _admit(self, plan):
        """Pure plan admission; writable storage is touched only by bootstrap."""
        support = self.support()
        if not support["supported"]:
            raise RunnerError("UNSUPPORTED", "; ".join(support["reasons"]))
        config = self.configuration
        if (not re.fullmatch(r"[a-z0-9-]+\.slice", config.get("slice", "")) or
                not config.get("cgroup", "").startswith("/sys/fs/cgroup/")):
            raise RunnerError("UNSUPPORTED", "invalid predelegated slice admission")
        execution = _plain(plan.get("execution", plan))
        if plan.get("budgets"):
            execution["budgets"] = _plain(plan["budgets"])
        phase = plan.get("phase", "business")
        allocation = bootstrap_roots.validate_grant(_plain(plan.get("bootstrap_allocation")),
            execution_id=plan["execution_id"], phase=phase, operation_id=execution["operation_id"])
        original_roots = _plain(plan.get("observed_roots", execution["roots"]))
        execution = bootstrap_roots.bind_execution(execution, allocation)
        if phase == "reconcile":
            execution["observed_roots"] = original_roots
            execution["readonly"] = execution.get("readonly", []) + list(original_roots.values())
            execution["environment"] = ledger_jobs.clean_environment(execution["roots"]["temporary"])
            if execution.get("storage"):
                execution["observed_storage"] = execution.pop("storage")
                execution["readonly"].append(execution["observed_storage"]["archive_root"])
        if phase == "evidence":
            snapshot, store_root = plan.get("evidence_snapshot"), plan.get("evidence_store_root")
            if (not isinstance(snapshot, dict) or not isinstance(store_root, str)
                    or allocation["retained_paths"] != [store_root]):
                raise RunnerError("UNSUPPORTED", "trusted evidence snapshot and store allocation are required")
            execution["readonly"] = execution.get("readonly", []) + [snapshot["root"]]
            execution["environment"] = ledger_jobs.clean_environment(execution["roots"]["temporary"])
            execution["evidence_snapshot"], execution["evidence_store_root"] = snapshot, store_root
            execution["broker_events"] = _plain(plan.get("broker_events", snapshot.get("broker_events", [])))
            execution["storage"] = {}
        if execution.get("storage"):
            raise RunnerError("UNSUPPORTED", "network archive hard quota adapter is not implemented; NAS execution is blocked")
        execution["writable"] = list(allocation["paths"])
        if any(re.search(r"[\s\\%$]", path) for path in execution["writable"] + execution.get("readonly", [])):
            raise RunnerError("UNSUPPORTED", "systemd path admission requires unambiguous paths")
        execution["bootstrap_allocation"] = allocation
        return execution, {}

    def start(self, identity, plan, cancel_event):
        try:
            return self._start(identity, plan, cancel_event)
        except RunnerError as error:
            handle = self._runs.get(identity["unit"])
            delivery_attempted = handle is not None and (handle.get("delivery_attempted") or handle.get("launch") is not None)
            if error.code in ("UNSUPPORTED", "LIMIT_EXCEEDED") and not delivery_attempted:
                raise _NoStartError(error.code, str(error)) from error
            raise

    @staticmethod
    def _bootstrap_unit(execution_id):
        return "lhj-" + hashlib.sha256((execution_id + ":bootstrap").encode()).hexdigest() + ".service"

    def _properties(self, execution, stage):
        limits = budget.substage_limits(execution["budget_grant"], stage)
        return {"Slice": self.configuration["slice"], "Type": "exec", "KillMode": "control-group",
            "SendSIGKILL": "yes", "RemainAfterExit": "yes", "RuntimeMaxSec": "1us",
            "TimeoutStopSec": str(limits["terminate_grace_seconds"]), "MemoryMax": str(limits["memory_bytes"]),
            "TasksMax": str(limits["processes"]), "CPUQuota": _cpu_quota(limits), "CPUQuotaPeriodSec": "1ms",
            "LimitCPU": str(limits["cpu_seconds"]), "LimitFSIZE": str(limits["temporary_bytes"]),
            "NoNewPrivileges": "yes", "ProtectSystem": "strict", "ProtectHome": "read-only",
            "PrivateUsers": "yes", "PrivateMounts": "yes", "PrivateNetwork": "yes", "PrivateDevices": "yes",
            "RestrictSUIDSGID": "yes", "ProtectKernelTunables": "yes", "ProtectKernelModules": "yes",
            "ProtectControlGroups": "yes", "RestrictNamespaces": "yes", "LockPersonality": "yes", "UMask": "0077",
            "InaccessiblePaths": "/tmp /var/tmp /dev/shm /run/dbus /run/user/" + str(os.geteuid()),
            "StandardOutput": "null", "StandardError": "null",
            "ReadWritePaths": " ".join(execution["writable"]),
            "ReadOnlyPaths": " ".join(execution.get("readonly", []))}

    def _new_stage(self, handle, stage):
        identity, execution = handle["identity"], handle["execution"]
        unit = self._bootstrap_unit(identity["execution_id"]) if stage == "bootstrap" else identity["unit"]
        return {"unit": unit, "boot_id": execution["budget_grant"]["boot_id"],
            "result_path": execution["result_path"], "cgroup_parent": self.configuration["cgroup"],
            "cancel_event": handle["cancel_event"], "launch": None, "launch_acked": False,
            "stop_acked": False, "stop_requested": False, "started": time.monotonic(),
            "deadline": execution["budgets"]["wall_seconds"], "invocation_id": None,
            "execution_id": identity["execution_id"], "cancel_before_launch": False,
            "identity": dict(identity, unit=unit), "recovered": False, "delivery_attempted": False,
            "budget_grant": execution["budget_grant"],
            "phase_deadline_boottime_ns": execution["phase_deadline_boottime_ns"], "stage": stage}

    def _deliver_stage(self, handle, stage, *, bootstrap_proof=None):
        try:
            return self._deliver_stage_impl(handle, stage, bootstrap_proof=bootstrap_proof)
        except JobError as error:
            raise RunnerError(error.code, str(error)) from error

    def _deliver_stage_impl(self, handle, stage, *, bootstrap_proof=None):
        execution = handle["execution"]
        part = handle[stage] = self._new_stage(handle, stage)
        properties = self._properties(execution, stage)
        command = ["/usr/bin/systemd-run", "--user", "--quiet", "--unit=" + part["unit"],
                   "--description=Local-Hand-supervised-" + stage]
        command.extend("--property=" + key + "=" + value for key, value in properties.items() if value)
        script = str(Path(__file__).absolute())
        if any(re.search(r"[\s\\%$]", path) for path in (script, execution["python"])):
            raise RunnerError("UNSUPPORTED", "systemd executable paths must not contain specifiers")
        if stage == "bootstrap":
            payload = {"execution": execution, "allocation": execution["bootstrap_allocation"]}
            command.extend(["--", execution["python"], "-I", script, "--bootstrap", bootstrap.encode_payload(payload)])
        else:
            command.extend(["--", execution["python"], "-I", script, "--helper", handle["plan_path"]])
        environment = {"PATH": "/usr/bin:/bin", "XDG_RUNTIME_DIR": "/run/user/" + str(os.geteuid())}
        bootstrap.check_argv(command, environment)
        if self._start_guard is None:
            raise RunnerError("UNSUPPORTED", "the durable broker startup guard is not bound")
        def deliver():
            if handle["cancel_event"].is_set():
                return None
            final_us = min(_runtime_microseconds(execution["budget_grant"]),
                _deadline_remaining((execution["budget_grant"], execution["phase_deadline_boottime_ns"])) // 1000)
            if final_us <= 0:
                raise JobError("LIMIT_EXCEEDED", "No bounded launch runtime remains")
            for index, argument in enumerate(command):
                if argument.startswith("--property=RuntimeMaxSec="):
                    command[index] = "--property=RuntimeMaxSec=" + str(final_us) + "us"
            # The durable guard records each unique stage before entering here.
            # Neither a Popen exception nor a lost return proves no delivery.
            handle["delivery_attempted"] = part["delivery_attempted"] = True
            part["launch"] = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, env=environment)
            return part["launch"]
        try:
            options = {"stage": stage}
            if stage == "helper": options["bootstrap_proof"] = bootstrap_proof
            accepted = self._start_guard(handle["identity"]["execution_id"], deliver, **options)
        except JobError as error:
            raise RunnerError(error.code, str(error)) from error
        except OSError as error:
            raise RunnerError("IO_UNCERTAIN", "manager launch acknowledgement missing") from error
        if accepted is None:
            if part["delivery_attempted"]:
                raise RunnerError("IO_UNCERTAIN", "startup guard returned no receipt after manager delivery")
            part["cancel_before_launch"] = True
        return part

    def _start(self, identity, plan, cancel_event):
        plan = dict(plan, execution_id=identity["execution_id"])
        try:
            execution, _ = self._admit(plan)
            allocation = bootstrap_roots.validate_grant(_plain(plan.get("bootstrap_allocation")),
                execution_id=identity["execution_id"], phase=identity["phase"], operation_id=identity["job_key"])
            grant = _plain(plan.get("budget_grant"))
            budget.validate_grant(grant, execution_id=identity["execution_id"], phase=identity["phase"],
                                  operation_id=identity["job_key"], budgets=execution["budgets"])
            runtime_us = _runtime_microseconds(grant)
            budget.substage_limits(grant, "bootstrap")
            budget.substage_limits(grant, "helper")
        except JobError as error:
            raise RunnerError(error.code, str(error)) from error
        if identity["unit"] in self._runs:
            raise RunnerError("CONFLICT", "manager identity reuse")
        execution = dict(execution, phase=identity["phase"], execution_id=identity["execution_id"],
            operation_id=identity["job_key"], budget_grant=grant, bootstrap_allocation=allocation,
            runtime_cap_us=runtime_us, unit=identity["unit"],
            bootstrap_unit=self._bootstrap_unit(identity["execution_id"]),
            parent_mount_namespace=os.readlink("/proc/self/ns/mnt"),
            phase_deadline_boottime_ns=budget.phase_deadline_ns(grant) - grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS)
        suffix = hashlib.sha256(identity["execution_id"].encode()).hexdigest()[:24]
        execution["result_path"] = str(Path(execution["roots"]["evidence"]) / ("result-" + suffix + ".json"))
        handle = {"version": 2, "unit": identity["unit"], "identity": dict(identity), "execution": execution,
            "plan_path": str(Path(execution["roots"]["evidence"]) / bootstrap.plan_name(identity["execution_id"])),
            "cancel_event": cancel_event, "bootstrap": None, "helper": None, "stage": "bootstrap",
            "delivery_attempted": False, "recovered": False, "helper_attempted": False,
            "bootstrap_proof": None, "transition_error": None}
        self._runs[identity["unit"]] = handle
        self._deliver_stage(handle, "bootstrap")
        return handle

    @staticmethod
    def _export_unit(handle):
        if handle is None:
            return None
        fields = ("unit", "boot_id", "result_path", "cgroup_parent", "launch_acked", "stop_acked",
                  "invocation_id", "execution_id", "phase_deadline_boottime_ns", "delivery_attempted")
        return {key: handle.get(key) for key in fields}

    def export_handle(self, handle):
        if handle.get("version") == 2:
            return {**handle["identity"], "manager": {"version": 2, "stage": handle["stage"],
                "bootstrap": self._export_unit(handle["bootstrap"]), "helper": self._export_unit(handle["helper"]),
                "allocation_digest": handle["execution"]["bootstrap_allocation"]["grant_digest"]}}
        fields = ("boot_id", "result_path", "cgroup_parent", "launch_acked", "stop_acked", "invocation_id", "execution_id", "phase_deadline_boottime_ns")
        return {**{key: value for key, value in handle["identity"].items() if key != "manager"},
                "manager": {key: handle.get(key) for key in fields}}

    def _bootstrap_terminal(self, handle, proof, outcome, error=None):
        result = {"outcome": outcome, "business_started": False,
                  "helper_started": not handle["bootstrap"].get("cancel_before_launch", False),
                  "bootstrap_prepared": proof.get("result", {}).get("bootstrap_prepared", False)}
        if error is not None:
            result["error"] = error
        # Zero here would describe preparation, not completion of this logical
        # phase. The broker must not promote a refused helper to SUCCEEDED.
        return {**proof, "exit_code": 1, "result": result,
                "bootstrap_exit_proof": _plain(proof)}

    def inspect(self, handle):
        if handle.get("version") != 2:
            return self._inspect_unit(handle)
        def observe(part):
            try:
                return self._inspect_unit(part)
            except RunnerError as error:
                return _unknown(str(error))
            except Exception:
                return _unknown("original stage observation is uncertain")
        first = observe(handle["bootstrap"])
        first_exited = (first.get("state") == "EXITED" and first.get("future_start_blocked") is True
                        and first.get("tree_exited") is True)
        if handle.get("recovered"):
            # A missing saved receipt cannot prove the old broker did not deliver
            # the deterministic helper unit. Observe that original identity only;
            # never resume the transition or manufacture a new start.
            second = observe(handle["helper"])
            if not first_exited:
                return _unknown("bootstrap exit is unresolved; helper identity was independently observed")
            if second.get("state") == "EXITED":
                second["effects_checked"] = (second.get("effects_checked") is True and
                    first.get("result", {}).get("bootstrap_prepared") is True)
            return second
        if not first_exited:
            if handle["helper"] is not None:
                # One failing manager observation cannot starve the other unit's
                # budget/exit checks once its delivery may have happened.
                observe(handle["helper"])
            return first
        if first.get("result", {}).get("bootstrap_prepared") is not True:
            return self._bootstrap_terminal(handle, first,
                "CANCELLED" if first.get("result", {}).get("outcome") == "CANCELLED" else "FAILED")
        handle["bootstrap_proof"] = first
        if handle["transition_error"] is not None and (
                handle["helper"] is None or not handle["helper"].get("delivery_attempted")):
            return self._bootstrap_terminal(handle, first, "FAILED", handle["transition_error"])
        if handle["helper"] is None:
            if handle["cancel_event"].is_set():
                return self._bootstrap_terminal(handle, first, "CANCELLED")
            if handle["helper_attempted"]:
                return self._bootstrap_terminal(handle, first, "FAILED", handle["transition_error"] or "IO_UNCERTAIN")
            # Set before validation/delivery. Any exception is observed under the
            # original identities, never by repeating this transition.
            handle["helper_attempted"] = True
            try:
                self._deliver_stage(handle, "helper", bootstrap_proof=first)
            except RunnerError as error:
                handle["transition_error"] = error.code
                if handle["helper"] is not None and handle["helper"].get("delivery_attempted"):
                    raise
                return self._bootstrap_terminal(handle, first, "FAILED", error.code)
            handle["stage"] = "helper"
        second = observe(handle["helper"])
        if handle["helper"].get("cancel_before_launch"):
            return self._bootstrap_terminal(handle, first, "CANCELLED")
        return second

    def stop(self, handle):
        if handle.get("version") != 2:
            return self._stop_unit(handle)
        handle["cancel_event"].set()
        failure = None
        for part in (handle["bootstrap"], handle["helper"]):
            if part is not None:
                try:
                    self._stop_unit(part)
                except BaseException as error:
                    if failure is None:
                        failure = error
                    else:
                        failure.add_note("Additional stage stop failure: " + type(error).__name__)
        if failure is not None:
            raise failure
        return _unknown("original bootstrap and helper identities are being stopped")

    def reattach(self, identity, plan, cancel_event):
        saved = identity.get("manager", {})
        if not saved and plan.get("bootstrap_allocation") is not None:
            # The broker may die before receiving the first manager observation.
            # Both deterministic identities still need observation, not replay.
            saved = {"version": 2, "stage": "UNKNOWN", "bootstrap": None, "helper": None,
                     "allocation_digest": plan["bootstrap_allocation"]["grant_digest"]}
        if saved.get("version") != 2:
            if plan.get("bootstrap_allocation") is not None:
                raise RunnerError("IO_UNCERTAIN", "New bootstrap execution has an incompatible recovery receipt")
            return self._reattach_legacy(identity, plan, cancel_event)
        support = self.support()
        if not support["supported"]:
            raise RunnerError("IO_UNCERTAIN", "original manager cannot be observed on this host")
        # Recovery does not authorize launch preparation. Rebuild only durable
        # root/unit identities, without demanding transient evidence snapshots,
        # current registry inputs, or a newly usable execution environment.
        allocation = bootstrap_roots.validate_grant(_plain(plan["bootstrap_allocation"]),
            execution_id=identity["execution_id"], phase=identity["phase"], operation_id=identity["job_key"])
        execution = bootstrap_roots.bind_execution(_plain(plan.get("execution", plan)), allocation)
        if plan.get("budgets"):
            execution["budgets"] = _plain(plan["budgets"])
        if saved.get("allocation_digest") != allocation["grant_digest"]:
            raise RunnerError("IO_UNCERTAIN", "recovery root allocation differs")
        original_grant = _plain(plan.get("budget_grant"))
        grant = original_grant
        try:
            budget.validate_grant(grant, execution_id=identity["execution_id"], phase=identity["phase"],
                                  operation_id=identity["job_key"], budgets=execution["budgets"])
            deadline = budget.phase_deadline_ns(grant) - grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS
        except JobError:
            # Broken timing never grants runtime and cannot disable observation
            # or stopping of independently preserved boot/unit identities.
            grant, deadline = None, None
        execution = dict(execution, budget_grant=grant, bootstrap_allocation=allocation,
                         phase_deadline_boottime_ns=deadline)
        suffix = hashlib.sha256(identity["execution_id"].encode()).hexdigest()[:24]
        execution["result_path"] = str(Path(execution["roots"]["evidence"]) / ("result-" + suffix + ".json"))
        handle = {"version": 2, "unit": identity["unit"], "identity": {key: value for key, value in identity.items() if key != "manager"},
            "execution": execution, "cancel_event": cancel_event, "stage": saved.get("stage"),
            "delivery_attempted": True, "recovered": True, "helper_attempted": True,
            "bootstrap_proof": None, "transition_error": None}
        for stage in ("bootstrap", "helper"):
            prior = saved.get(stage)
            unit = self._bootstrap_unit(identity["execution_id"]) if stage == "bootstrap" else identity["unit"]
            original_boot = original_grant.get("boot_id") if isinstance(original_grant, dict) else None
            if not isinstance(original_boot, str) or re.fullmatch(budget.UUID_PATTERN, original_boot) is None:
                original_boot = None
            part = {"unit": unit, "identity": dict(identity, unit=unit), "boot_id": original_boot,
                "result_path": execution["result_path"], "cgroup_parent": self.configuration["cgroup"],
                "cancel_event": cancel_event, "launch": None, "launch_acked": False, "stop_acked": False,
                "stop_requested": False, "invocation_id": None, "execution_id": identity["execution_id"],
                "cancel_before_launch": False, "recovered": True, "budget_grant": grant,
                "phase_deadline_boottime_ns": deadline, "stage": stage}
            if prior is not None:
                if (prior.get("unit") != part["unit"] or prior.get("result_path") != part["result_path"] or
                        prior.get("execution_id") != identity["execution_id"] or
                        prior.get("cgroup_parent") != self.configuration["cgroup"] or
                        (original_boot is not None and prior.get("boot_id") != original_boot)):
                    raise RunnerError("IO_UNCERTAIN", "recovery stage identity differs")
                part.update({key: prior.get(key) for key in ("boot_id", "invocation_id")})
                if (not isinstance(part["boot_id"], str) or re.fullmatch(budget.UUID_PATTERN, part["boot_id"]) is None):
                    raise RunnerError("IO_UNCERTAIN", "recovery boot identity differs")
                part["launch_acked"] = prior.get("launch_acked") is True
                part["stop_acked"] = prior.get("stop_acked") is True
            part["recovered"] = True
            # No valid saved runtime can renew an expired phase grant.
            part["budget_grant"] = grant
            handle[stage] = part
        self._runs[identity["unit"]] = handle
        return handle

    def _retained_delivery(self, identity):
        """Read only the original request receipt after a delivery exception."""
        handle = self._runs.get(identity.get("unit"))
        if (handle is not None and handle.get("delivery_attempted") is True
                and Runner._same_handle(handle.get("identity", {}), identity)):
            return handle
        return None

    def _reattach_legacy(self, identity, plan, cancel_event):
        support = self.support()
        if not support["supported"]:
            raise RunnerError("IO_UNCERTAIN", "original manager cannot be observed on this host")
        saved = identity.get("manager", {})
        expected_group = self.configuration["cgroup"]
        if saved.get("cgroup_parent", expected_group) != expected_group:
            raise RunnerError("IO_UNCERTAIN", "recovery delegation differs")
        execution = plan.get("execution", plan)
        evidence = execution["roots"]["evidence"]
        phase = identity["phase"]
        suffix = hashlib.sha256(identity["execution_id"].encode()).hexdigest()
        if phase == "evidence": evidence += "-seal-" + suffix[:16]
        if phase == "reconcile": evidence += "-observe-" + suffix[:16]
        result_path = str(Path(evidence) / ("result-" + suffix[:24] + ".json"))
        if saved.get("result_path", result_path) != result_path:
            raise RunnerError("IO_UNCERTAIN", "recovery result identity differs")
        current_boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        grant = _plain(plan.get("budget_grant"))
        if grant is not None:
            try:
                budget.validate_grant(grant, execution_id=identity["execution_id"], phase=phase,
                                      operation_id=identity["job_key"], budgets=plan["budgets"])
            except JobError:
                # An unusable budget never authorizes more runtime, but it
                # must not disable observation/stopping of the already bound
                # unit. All existing boot, unit, invocation and path checks stay.
                grant = None
        saved_deadline = saved.get("phase_deadline_boottime_ns") if grant is not None else None
        if saved_deadline is not None and (type(saved_deadline) is not int or grant is None
                or not grant["reserved_boottime_ns"] < saved_deadline <= (grant["deadline_boottime_ns"]
                    - grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS)):
            # Corrupt timing cannot grant runtime or disable stopping an
            # otherwise identity-bound unit. Missing time requests stop below.
            saved_deadline = None
        handle = {"unit": identity["unit"], "identity": dict(identity), "boot_id": saved.get("boot_id", current_boot),
                  "result_path": result_path, "cgroup_parent": expected_group, "cancel_event": cancel_event,
                  "launch": None, "launch_acked": saved.get("launch_acked") is True and saved.get("boot_id") == current_boot,
                  "stop_acked": saved.get("stop_acked") is True, "stop_requested": False,
                  "invocation_id": saved.get("invocation_id"), "execution_id": identity["execution_id"],
                  "cancel_before_launch": False, "recovered": True,
                  "budget_grant": grant, "phase_deadline_boottime_ns": saved_deadline}
        self._runs[identity["unit"]] = handle
        return handle

    def _stop_unit(self, handle):
        handle["stop_requested"] = True
        if not handle.get("boot_id"):
            return _unknown("original boot identity is unavailable; stop not retargeted")
        if handle.get("boot_id") and Path("/proc/sys/kernel/random/boot_id").read_text().strip() != handle["boot_id"]:
            return _unknown("original boot identity differs; stop not retargeted")
        if handle.get("invocation_id"):
            observed = self._command("show", handle["unit"], "--property=InvocationID", "--value")
            if observed.returncode or observed.stdout.decode().strip() != handle["invocation_id"]:
                return _unknown("original invocation differs; stop not retargeted")
        launch = handle["launch"]
        if not handle.get("recovered") and (launch is None or launch.poll() is None):
            return _unknown("manager start request remains in flight")
        # Ordered after launch completion. systemctl stop --no-block would not
        # prove queued start cancellation, so observe only after completed stop.
        if not handle["stop_acked"]:
            result = self._command("stop", "--no-block", handle["unit"])
            handle["stop_acked"] = result.returncode == 0
        return _unknown("stop accepted; awaiting job and tree exit proof")

    def _inspect_unit(self, handle):
        if handle["cancel_before_launch"]:
            return {**_unknown(), "state": "EXITED", "future_start_blocked": True, "tree_exited": True,
                "collectors_stopped": True, "writers_stopped": True, "effects_checked": True, "missing": [],
                "result": {"outcome": "CANCELLED", "business_started": False, "helper_started": False}}
        if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != handle["boot_id"]:
            return _unknown("boot identity changed; reconcile durable ownership")
        launch = handle["launch"]
        if not handle.get("recovered"):
            if launch is None or launch.poll() is None:
                return _unknown("manager start request has not been acknowledged")
            handle["launch_acked"] = launch.returncode == 0
            if not handle["launch_acked"]:
                return _unknown("manager rejected or lost the start receipt")
        observed = self._command("show", handle["unit"], "--property=LoadState,ActiveState,SubState,ControlGroup,InvocationID,Job,ExecMainCode,ExecMainStatus,Result")
        if observed.returncode: return _unknown("manager unit cannot be observed")
        values = dict(line.split("=", 1) for line in observed.stdout.decode().splitlines() if "=" in line)
        invocation = values.get("InvocationID")
        if not invocation or not re.fullmatch(r"[0-9a-f]{32}", invocation): return _unknown("invocation identity missing")
        if handle["invocation_id"] not in (None, invocation): return _unknown("unit invocation identity changed")
        handle["invocation_id"] = invocation
        group = values.get("ControlGroup", "")
        expected_prefix = handle["cgroup_parent"] + "/"
        cgroup = Path("/sys/fs/cgroup" + group)
        if not group or not str(cgroup).startswith(expected_prefix) or cgroup.name != handle["unit"]:
            return _unknown("cgroup ownership differs from execution")
        try:
            events = dict(line.split() for line in (cgroup / "cgroup.events").read_text().splitlines())
            # populated is recursive, and is not interchangeable with cgroup.procs.
            empty = events.get("populated") == "0"
        except FileNotFoundError:
            empty = values.get("ActiveState") in ("inactive", "failed") and not cgroup.exists()
        except OSError:
            empty = False
        job_empty = values.get("Job", "") in ("", "0")
        idle = values.get("ActiveState") in ("inactive", "failed") or values.get("SubState") == "exited"
        blocked = handle["launch_acked"] and job_empty and idle
        if not (blocked and empty):
            grant = handle.get("budget_grant")
            if grant is not None:
                try:
                    phase_deadline = handle.get("phase_deadline_boottime_ns")
                    expired = phase_deadline is None or _deadline_remaining((grant, phase_deadline)) <= 0
                except JobError:
                    expired = True  # Uncertain/other-boot budget never grants fresh runtime.
            else:
                expired = handle.get("recovered") or time.monotonic() - handle["started"] > handle["deadline"]
            if idle or expired:
                handle["stop_requested"] = True
                self._stop_unit(handle)
            return {**_unknown(), "state": "RUNNING" if not idle else "UNKNOWN",
                    "identity": {"boot_id": handle["boot_id"], "invocation_id": invocation, "cgroup": group}}
        if handle.get("stage") == "bootstrap":
            exit_code = int(values["ExecMainStatus"]) if values.get("ExecMainCode") == "1" and values.get("ExecMainStatus", "").isdigit() else None
            prepared = exit_code == 0
            # The fixed bootstrap entry returns zero only after its admitted
            # root/quota checks, create-only plan publication, fsync and final
            # root-binding/deadline checks. No result/plan storage read occurs in
            # the observer thread; failed/partial preparation keeps its barrier.
            return {"state": "EXITED", "future_start_blocked": True, "tree_exited": True,
                "collectors_stopped": True, "writers_stopped": True, "effects_checked": prepared,
                "exit_code": exit_code, "execution_id": handle["execution_id"], "unit": handle["unit"],
                "facts": {}, "result": {"outcome": "SUCCEEDED" if prepared else "FAILED",
                    "bootstrap_prepared": prepared, "business_started": False, "helper_started": True},
                "identity": {"boot_id": handle["boot_id"], "invocation_id": invocation, "cgroup": group},
                "missing": [] if prepared else ["bootstrap preparation failed; partial files remain allocated"]}
        result = {}
        try:
            raw = ledger_jobs.bounded_regular_bytes(handle["result_path"], 1024 * 1024)
            candidate = json.loads(raw)
            if type(candidate) is not dict or candidate.get("execution_id") != handle["execution_id"]:
                raise ValueError("helper identity differs")
            if (candidate.get("outcome") not in ("SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN") or
                    type(candidate.get("effects_checked", False)) is not bool or
                    type(candidate.get("facts", {})) is not dict):
                raise ValueError("helper result shape differs")
            result = candidate
        except (OSError, ValueError):
            result = {}
        exit_code = int(values["ExecMainStatus"]) if values.get("ExecMainCode") == "1" and values.get("ExecMainStatus", "").isdigit() else None
        outcome = result.get("outcome", "UNKNOWN")
        return {"state": "EXITED", "future_start_blocked": True, "tree_exited": True,
                "collectors_stopped": True, "writers_stopped": True, "effects_checked": result.get("effects_checked", False),
                # The business result is a separately verified observation;
                # helper exit can fail later while persisting that result.
                "helper_result_verified": bool(result),
                "exit_code": exit_code, "facts": result.get("facts", {}), "result": {**result, "outcome": outcome},
                "identity": {"boot_id": handle["boot_id"], "invocation_id": invocation, "cgroup": group},
                "missing": [] if result else ["helper result unavailable; side effects require reconciliation"]}


def _capture_stage(stage, directory, limit, remaining, deadline=None):
    """Drain both pipes independently; truncate storage, continue draining."""
    if deadline is not None:
        remaining = min(remaining, _deadline_remaining(deadline) / budget.NANOSECONDS)
    if remaining <= 0:
        # The prior stage or interpreter check may already have spent the job's
        # remaining budget. Terminating after Popen cannot undo a child's work.
        raise ledger_jobs.LedgerPlanError("stage wall budget exhausted before launch")
    start = time.monotonic()
    process = selector = None
    totals, retained, streams = {}, {}, {}
    exceeded = False
    drain_deadline = None
    original_error = None
    try:
        process = subprocess.Popen(stage["argv"], cwd=stage["cwd"], env=stage["env"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        selector = selectors.DefaultSelector()
        for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
            streams[name] = (Path(directory) / (stage["name"] + "." + name)).open("xb")
            totals[name] = retained[name] = 0
        # EOF only ends capture for that pipe; a fixed program may close both
        # outputs before finishing its own work. Keep its existing wall budget.
        while selector.get_map() or process.poll() is None:
            if time.monotonic() - start > remaining:
                exceeded = True
            if deadline is not None:
                try: _deadline_remaining(deadline)
                except JobError as error:
                    if error.code != "LIMIT_EXCEEDED": raise
                    exceeded = True
            if exceeded and drain_deadline is None:
                # The manager controls the whole unit. Helper exits nonzero;
                # KillMode=control-group removes descendants. No pgid fallback.
                process.terminate()
                drain_deadline = time.monotonic() + 2
            if drain_deadline is not None and time.monotonic() >= drain_deadline: break
            for key, _ in selector.select(0.05):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj); key.fileobj.close(); continue
                name = key.data
                totals[name] += len(chunk)
                available = max(0, limit - sum(retained.values()))
                take = min(len(chunk), available)
                if take: streams[name].write(chunk[:take]); retained[name] += take
                if take < len(chunk): exceeded = True
            if process.poll() is not None and drain_deadline is None:
                drain_deadline = time.monotonic() + 2  # descendants may retain a pipe
        try: code = process.wait(timeout=0.1)
        except subprocess.TimeoutExpired: code = None
    except BaseException as error:
        original_error = error
        raise
    finally:
        pending_pipes = selector is not None and bool(selector.get_map())
        cleanup_error = None
        def cleanup(action):
            nonlocal cleanup_error
            try: action()
            except BaseException as error:
                if cleanup_error is None: cleanup_error = error
        if process is not None:
            # Setup and storage failures must not strand this direct child.
            # Only the manager's later cgroup proof covers its descendants.
            if process.poll() is None:
                def kill_child():
                    try: process.kill()
                    except ProcessLookupError: pass
                cleanup(kill_child)
            cleanup(lambda: process.wait(timeout=0.2))
            for pipe in (process.stdout, process.stderr):
                if pipe is not None: cleanup(pipe.close)
        if selector is not None: cleanup(selector.close)
        for stream in streams.values():
            cleanup(stream.flush)
            cleanup(lambda stream=stream: os.fsync(stream.fileno()))
            cleanup(stream.close)
        if cleanup_error is not None and original_error is None: raise cleanup_error
    return {"name": stage["name"], "exit_code": code, "elapsed_seconds": time.monotonic() - start,
            "bytes_seen": totals, "bytes_retained": retained,
            "bytes_discarded": {k: totals[k] - retained[k] for k in totals},
            "truncated": exceeded, "drain_incomplete": pending_pipes,
            "outcome": "SUCCEEDED" if code == 0 and not exceeded and not pending_pipes else "FAILED"}


def _interpreter_temp_check(python, plan, directory, *, log_limit=None, remaining=10, observations=None, deadline=None):
    # The Ledger interpreters need not have Local Hand installed. Keep this
    # independent probe standard-library-only, with the same failure semantics.
    code = ("import os,pathlib,tempfile\n"
        "p=pathlib.Path(os.environ['TMPDIR'])\n"
        "assert p.is_dir() and p.resolve()==p\n"
        "assert pathlib.Path(tempfile.gettempdir())==p\n"
        "identity=lambda info:(info.st_dev,info.st_ino,info.st_mode)\n"
        "root_identity=identity(p.stat(follow_symlinks=False))\n"
        "d=f=None\n"
        "original_error=None\n"
        "try:\n"
        "    d=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)\n"
        "    def check_root():\n"
        "        if (identity(os.fstat(d))!=root_identity or p.resolve()!=p\n"
        "                or identity(p.stat(follow_symlinks=False))!=root_identity):\n"
        "            raise OSError('temporary root changed during probe')\n"
        "    check_root()\n"
        "    anonymous=getattr(os,'O_TMPFILE',None)\n"
        "    if anonymous is None: raise OSError('anonymous temporary probe is unsupported')\n"
        "    f=os.open('.',anonymous|os.O_RDWR,0o600,dir_fd=d)\n"
        "    if os.fstat(f).st_nlink!=0: raise OSError('temporary probe is not anonymous')\n"
        "    if os.write(f,b'lh') != 2: raise OSError('temporary probe write was incomplete')\n"
        "    os.fsync(f)\n"
        "    check_root()\n"
        "except BaseException as error:\n"
        "    original_error=error\n"
        "    raise\n"
        "finally:\n"
        "    cleanup_error=None\n"
        "    actions=[]\n"
        "    if f is not None: actions.append(lambda: os.close(f))\n"
        "    if d is not None: actions.append(lambda: os.close(d))\n"
        "    for action in actions:\n"
        "        try: action()\n"
        "        except BaseException as error:\n"
        "            if cleanup_error is None: cleanup_error=error\n"
        "    if cleanup_error is not None:\n"
        "        if original_error is not None: original_error.add_note('temporary probe cleanup was incomplete')\n"
        "        else: raise cleanup_error\n")
    stage = {"name": "temp-" + hashlib.sha256(python.encode()).hexdigest()[:12],
             "argv": [python, "-I", "-c", code], "cwd": plan["roots"]["work"], "env": plan["environment"]}
    if log_limit is None: log_limit = plan["budgets"]["log_bytes"]
    arguments = (stage, directory, min(16384, log_limit), min(10, remaining))
    observation = _capture_stage(*arguments, deadline) if deadline is not None else _capture_stage(*arguments)
    if observations is not None: observations.append(observation)
    if observation["outcome"] != "SUCCEEDED": raise ledger_jobs.LedgerPlanError("actual interpreter temporary binding failed")
    return observation


def _checked_walk(root, *, topdown=True):
    """Missing or unreadable owned trees are not successful empty observations."""
    root = Path(root)
    if root.resolve() != root or root.is_symlink() or not root.is_dir():
        raise ledger_jobs.LedgerPlanError("owned inventory root is unavailable")
    original = root.stat()
    def unreadable(_):
        raise ledger_jobs.LedgerPlanError("owned inventory cannot be completely observed")
    yield from os.walk(root, topdown=topdown, followlinks=False, onerror=unreadable)
    current = root.stat()
    if root.resolve() != root or (original.st_dev, original.st_ino) != (current.st_dev, current.st_ino):
        raise ledger_jobs.LedgerPlanError("owned inventory root changed")


def _inventory_prepared(plan):
    prepared = dict(plan["prepared"])
    root = Path(prepared["root"])
    files, links = {}, {}
    for directory, dirs, names in _checked_walk(root):
        for name in dirs[:]:
            path = Path(directory) / name
            if path.is_symlink():
                relative = path.relative_to(root).as_posix()
                if name != "lib64" or os.readlink(path) != "lib": raise ledger_jobs.LedgerPlanError("unexpected prepared symlink")
                links[relative] = "lib"; dirs.remove(name)
        for name in names:
            path = Path(directory) / name
            if path.is_symlink(): raise ledger_jobs.LedgerPlanError("unexpected prepared file symlink")
            files[path.relative_to(root).as_posix()] = hashlib.sha256(ledger_jobs._regular_bytes(path)).hexdigest()
    prepared.update(files=files, links=links, wheel_digest=hashlib.sha256(ledger_jobs._regular_bytes(prepared["wheel"])).hexdigest(),
                    source_blobs=plan["source"]["blobs"], readonly_enforced=True, sealed=False)
    # Keep both venvs exactly where installed, freeze instead of copying them.
    for directory, dirs, names in _checked_walk(root, topdown=False):
        for name in names:
            path = Path(directory) / name
            path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
        Path(directory).chmod(0o500)
    return prepared


def _verify_cgroup_limits(plan):
    groups = [line.split(":", 2)[2] for line in Path("/proc/self/cgroup").read_text().splitlines()
              if line.startswith("0::")]
    if len(groups) != 1 or Path(groups[0]).name != plan["unit"]:
        raise ledger_jobs.LedgerPlanError("helper is outside its assigned cgroup")
    group = Path("/sys/fs/cgroup" + groups[0])
    memory, processes = (group / "memory.max").read_text().strip(), (group / "pids.max").read_text().strip()
    cpu = (group / "cpu.max").read_text().split()
    budget = plan["budgets"]
    if (not memory.isdigit() or int(memory) > budget["memory_bytes"] or
        not processes.isdigit() or int(processes) > budget["processes"] or
        len(cpu) != 2 or not all(value.isdigit() for value in cpu) or
        int(cpu[0]) * budget["wall_seconds"] > budget["cpu_seconds"] * int(cpu[1])):
        raise ledger_jobs.LedgerPlanError("actual cgroup budget differs from admission")
    import resource
    file_limit = resource.getrlimit(resource.RLIMIT_FSIZE)[0]
    if file_limit < 0 or file_limit > budget["temporary_bytes"]:
        raise ledger_jobs.LedgerPlanError("file size limit is not active")
    return {"cgroup": groups[0], "memory_max": int(memory), "pids_max": int(processes),
            "cpu_max": [int(value) for value in cpu], "file_size_limit": file_limit}


def _verify_storage_namespace(plan):
    storage = plan["storage"]
    expected = storage["stable_mount_binding"]
    archive = Path(storage["archive_root"])
    mount = _mount_for(archive)
    info = archive.stat()
    if (archive.resolve() != archive or mount["target"] != str(archive) or
        os.readlink("/proc/self/ns/mnt") == plan["parent_mount_namespace"] or
        mount["type"] not in ("nfs", "nfs4", "cifs") or
        any(mount[key] != expected[key] for key in ("source", "root", "type")) or
        info.st_dev != expected["device"] or info.st_ino != expected["inode"]):
        raise ledger_jobs.LedgerPlanError("protected storage mount binding differs")
    return {**mount, "device": info.st_dev, "inode": info.st_ino,
            "namespace": os.readlink("/proc/self/ns/mnt")}


def _helper(plan):
    # This check precedes even helper-owned directory creation or input I/O.
    # A delayed systemd activation cannot turn an old grant into fresh time.
    grant = plan.get("budget_grant")
    budget.validate_grant(grant, execution_id=plan["execution_id"], phase=plan["phase"], budgets=plan["budgets"])
    now = budget.current_clock()
    runtime_us = _runtime_microseconds(grant, now=now)
    if "runtime_cap_us" in plan:
        cap = plan["runtime_cap_us"]
        if type(cap) is not int or cap <= 0:
            raise JobError("IO_UNCERTAIN", "Helper runtime cap is malformed")
        runtime_us = min(runtime_us, cap)
    fixed_deadline = budget.phase_deadline_ns(grant) - grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS
    if "phase_deadline_boottime_ns" in plan:
        supplied_deadline = plan["phase_deadline_boottime_ns"]
        if type(supplied_deadline) is not int or supplied_deadline != fixed_deadline:
            raise JobError("IO_UNCERTAIN", "Helper phase deadline differs from its original grant")
    deadline = (grant, min(fixed_deadline, now["boottime_ns"] + runtime_us * 1000))
    if "bootstrap_allocation" in plan:
        bootstrap.verify_roots(plan)
    started = time.monotonic()
    remaining_logs = plan["budgets"]["log_bytes"]
    phase = plan["phase"]
    output = {"execution_id": plan["execution_id"], "outcome": "FAILED", "effects_checked": False,
              "business_started": False, "helper_started": True, "facts": {}, "stages": [], "retention": plan.get("retention")}
    work, evidence = Path(plan["roots"]["work"]), Path(plan["roots"]["evidence"])
    directory = evidence / (phase + "-" + hashlib.sha256(plan["execution_id"].encode()).hexdigest()[:16])
    directory.mkdir(mode=0o700)
    def remaining_time():
        return min(runtime_us / 1_000_000 - (time.monotonic() - started),
                   _deadline_remaining(deadline) / budget.NANOSECONDS)
    def check_interpreter(python):
        nonlocal remaining_logs
        observation = _interpreter_temp_check(python, plan, directory,
            log_limit=remaining_logs, remaining=remaining_time(), observations=output["stages"], deadline=deadline)
        remaining_logs -= sum(observation["bytes_retained"].values())
    try:
        # Verify that requested namespace settings actually became effective.
        # systemd documents that user-manager mount isolation needs PrivateUsers.
        if os.readlink("/proc/self/ns/mnt") == plan["parent_mount_namespace"]:
            raise ledger_jobs.LedgerPlanError("private filesystem namespace is not active")
        if "ro" not in _mount_for("/")["options"].split(","):
            raise ledger_jobs.LedgerPlanError("root filesystem write fence is not active")
        if any(os.access(path, os.W_OK) for path in ("/tmp", "/var/tmp", "/dev/shm")):
            raise ledger_jobs.LedgerPlanError("unbounded fallback write path remains accessible")
        os.environ.clear(); os.environ.update(plan["environment"])
        supervision = plan
        if "bootstrap_allocation" in plan:
            supervision = dict(plan, budgets=budget.substage_limits(grant, "helper"))
        output["facts"]["cgroup_limits"] = _verify_cgroup_limits(supervision)
        output["facts"]["temporary"] = ledger_jobs.check_temp_binding(plan["roots"]["temporary"])
        import platform, sqlite3
        environment = {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
                       "os": platform.system(), "machine": platform.machine(),
                       "filesystems": {key: {field: _mount_for(path)[field] for field in ("source", "root", "type")}
                                       for key, path in plan["roots"].items()}}
        output["facts"]["environment_fingerprint"] = hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest()
        if plan.get("storage"):
            output["facts"]["storage_mount"] = _verify_storage_namespace(plan)
        if phase == "preflight":
            output["facts"].update(ledger_jobs.verify_inputs(plan))
            interpreters = [plan["python"]] if plan["kind"] in ("host.inspect", "ledger.prepare") else [plan["prepared"]["build_python"], plan["prepared"]["runtime_python"]]
            for python in sorted(set(interpreters)): check_interpreter(python)
            output.update(outcome="SUCCEEDED", effects_checked=True)
        elif phase == "evidence":
            from local_hand_jobs.evidence import EvidenceStore, FrozenSnapshot, QuiescenceProof
            data = plan["evidence_snapshot"]
            snapshot = FrozenSnapshot(operation_id=data["operation_id"], event_seq=data["event_seq"],
                root=Path(data["root"]), members=tuple(data["members"]),
                quiescence=QuiescenceProof(**data["quiescence"]), bindings=data["bindings"],
                previous_seal_id=data.get("previous_seal_id"), reconcile_id=data.get("reconcile_id"),
                broker_events=tuple(plan.get("broker_events", data.get("broker_events", []))))
            def forbidden_register(record):
                raise RuntimeError("only the broker can register a durable seal")
            store = EvidenceStore(Path(plan["evidence_store_root"]), snapshot_provider=lambda operation: snapshot,
                register_seal=forbidden_register, is_registered=lambda *args: False,
                max_source_bytes=plan["budgets"]["reservation_bytes"],
                **({"root_identity": plan["bootstrap_allocation"]["paths"][plan["evidence_store_root"]]}
                   if "bootstrap_allocation" in plan else {}))
            output["seal_record"] = store.publish_only(snapshot)
            output.update(outcome="SUCCEEDED", effects_checked=True)
        elif phase == "reconcile":
            original = Path(plan["observed_roots"]["work"])
            if plan["kind"] == "ledger.nas.roundtrip":
                output["result"] = ledger_jobs.discover_nas_run(original / "local-parent")
                output["outcome"] = "UNKNOWN"
            else:
                observations = {}
                for label, root in plan["observed_roots"].items():
                    facts = {}
                    for directory, dirs, names in _checked_walk(root):
                        for name in dirs:
                            if (Path(directory) / name).is_symlink():
                                if name == "lib64" and os.readlink(Path(directory) / name) == "lib": continue
                                raise ledger_jobs.LedgerPlanError("linked observation directory")
                        for name in names:
                            path = Path(directory) / name
                            facts[path.relative_to(root).as_posix()] = hashlib.sha256(ledger_jobs._regular_bytes(path)).hexdigest()
                    observations[label] = facts
                output["result"] = {"observed_files": observations, "original_outcome": "UNKNOWN",
                                    "scope": "READ_ONLY_OWNED_LOCAL_FACTS"}
                output.update(outcome="SUCCEEDED", effects_checked=True)
        elif phase == "business":
            # Recheck pinned inputs immediately before copying and running; the
            # source mappings remain read-only in this namespace for all stages.
            output["facts"].update(ledger_jobs.verify_inputs(plan))
            if plan["kind"] == "host.inspect":
                # This fixed business observation runs inside the helper; it
                # is still execution even though it spawns no separate child.
                output["business_started"] = True
                import platform, sqlite3
                output["facts"].update(python=sys.version, sqlite=sqlite3.sqlite_version,
                    os=platform.system(), machine=platform.machine(), mounts={k: _mount_for(v) for k, v in plan["roots"].items()})
                output.update(outcome="SUCCEEDED", effects_checked=True)
            else:
                output["business_started"] = True
                ledger_jobs.copy_verified_source(plan)
                checked = set()
                for stage in plan["stages"]:
                    python = stage["argv"][0]
                    if python not in checked:
                        check_interpreter(python); checked.add(python)
                    observed = _capture_stage(stage, directory, remaining_logs, remaining_time(), deadline)
                    output["stages"].append(observed)
                    remaining_logs -= sum(observed["bytes_retained"].values())
                    if observed["outcome"] != "SUCCEEDED": break
                else:
                    output["outcome"] = "SUCCEEDED"
                if plan["kind"] == "ledger.test.resources" and output["outcome"] == "SUCCEEDED":
                    suite = plan["inputs"]["suite"]
                    details = ledger_jobs.resource_result(suite, (directory / (suite + ".stdout")).read_text(), (directory / (suite + ".stderr")).read_text(), 0)
                    output.update(details)
                if plan["kind"] == "ledger.prepare" and output["outcome"] == "SUCCEEDED":
                    output["prepared"] = _inventory_prepared(plan)
                    prepared = output["prepared"]
                    payload = {name: digest for name, digest in prepared["files"].items()
                               if name.startswith("runtime-venv/") and "/site-packages/" in name}
                    # Deliver the exact wheel and fixed source alongside their
                    # build/install logs; original venvs stay bound in place.
                    import zipfile
                    with (evidence / "prepared-wheel.whl").open("xb") as target_wheel:
                        target_wheel.write(ledger_jobs._regular_bytes(prepared["wheel"]))
                        target_wheel.flush(); os.fsync(target_wheel.fileno())
                    with zipfile.ZipFile(evidence / "prepared-source.zip", "x", compression=zipfile.ZIP_STORED) as source_zip:
                        for name in sorted(prepared["source_blobs"]):
                            source_zip.writestr(name, ledger_jobs._regular_bytes(Path(prepared["source_root"]) / name))
                    source_fd = os.open(evidence / "prepared-source.zip", os.O_RDONLY | os.O_NOFOLLOW)
                    try: os.fsync(source_fd)
                    finally: os.close(source_fd)
                    prepared["bindings"] = {"source_commit": ledger_jobs.SOURCE_COMMIT,
                        "source_digest": output["facts"]["source_digest"], "wheel_digest": prepared["wheel_digest"],
                        "installed_payload_digest": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                        "runtime_digest": hashlib.sha256(ledger_jobs._regular_bytes(prepared["runtime_python"])).hexdigest(),
                        "environment_fingerprint": output["facts"]["environment_fingerprint"]}
                output["effects_checked"] = plan["kind"] != "ledger.nas.roundtrip" and output["outcome"] == "SUCCEEDED"
        else:
            raise ledger_jobs.LedgerPlanError("unsupported fixed helper phase")
    except BaseException as error:
        output.update(outcome="FAILED", error=type(error).__name__)
    helper_failed = False
    if output["outcome"] == "SUCCEEDED":
        try:
            if remaining_time() <= 0:
                raise JobError("LIMIT_EXCEEDED", "Helper completion budget exhausted")
        except BaseException as error:
            # A later helper budget/clock failure must not rewrite completed,
            # checked business facts. The nonzero helper exit keeps reporting
            # uncertainty separate from that already known business outcome.
            helper_failed = True
            output["helper_error"] = {"stage": "completion_budget", "type": type(error).__name__,
                                      "code": getattr(error, "code", "IO_UNCERTAIN")}
            if phase not in ("business", "reconcile") or output["effects_checked"] is not True:
                output.update(outcome="FAILED", effects_checked=False, error=type(error).__name__)
    output["bindings"] = dict(output.get("prepared", {}).get("bindings", plan.get("prepared", {}).get("bindings", {})))
    output["bindings"]["environment_fingerprint"] = output["facts"].get("environment_fingerprint")
    target = Path(plan["result_path"])
    members = []
    for parent, dirs, names in _checked_walk(evidence):
        if any((Path(parent) / name).is_symlink() for name in dirs):
            raise ledger_jobs.LedgerPlanError("linked evidence directory")
        members.extend((Path(parent) / name).relative_to(evidence).as_posix() for name in names)
    members.append(target.relative_to(evidence).as_posix())
    output["evidence_snapshot"] = {"root": str(evidence), "members": sorted(set(members))}
    raw = json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
    with target.open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return 0 if output["outcome"] == "SUCCEEDED" and not helper_failed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private fixed runner helper; not a caller command interface")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--helper")
    mode.add_argument("--bootstrap")
    args = parser.parse_args(argv)
    if args.bootstrap is not None:
        return bootstrap.prepare(bootstrap.decode_payload(args.bootstrap))
    path = Path(args.helper)
    if not path.is_absolute() or path.is_symlink(): return 2
    raw = ledger_jobs.bounded_regular_bytes(path, 4 * 1024 * 1024)
    return _helper(json.loads(raw))


if __name__ == "__main__":
    raise SystemExit(main())
