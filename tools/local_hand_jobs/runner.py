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
    from . import ledger_jobs
else:  # fixed -I script entry: importing only this installed sibling
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from local_hand_jobs import ledger_jobs


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
            # UNSUPPORTED before submitting anything is a proved no-start case.
            if isinstance(error, _NoStartError) and not item.launch_complete and not item.plan.get("_reattach"):
                proof.update(state="EXITED", future_start_blocked=True, tree_exited=True,
                             collectors_stopped=True, writers_stopped=True, effects_checked=True,
                             result={"outcome": "FAILED", "error": "UNSUPPORTED", "business_started": False, "helper_started": False}, missing=[])
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


def _verify_project_quota(path, byte_limit):
    """Require a real inherited kernel project hard quota, not a config bool."""
    mount = _mount_for(path)
    if mount["type"] not in ("ext4", "xfs"):
        raise RunnerError("UNSUPPORTED", "project quota filesystem is unsupported")
    existing = Path(path)
    while not existing.exists(): existing = existing.parent
    if existing.resolve() != existing: raise RunnerError("UNSUPPORTED", "linked writable root")
    descriptor = os.open(existing, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
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
        raise RunnerError("UNSUPPORTED", "project hard quota cannot be verified") from error
    finally:
        os.close(descriptor)


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
        # _start still performs directory/plan/quota I/O before the supervised
        # unit exists. A Python observer thread is not an independently stoppable
        # bootstrap execution. Block production even on an otherwise capable host
        # until that boundary has an admitted, persistent implementation.
        reasons = ["SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED"]
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
        support = self.support()
        if not support["supported"]: raise RunnerError("UNSUPPORTED", "; ".join(support["reasons"]))
        config = self.configuration
        slice_name = config.get("slice", "")
        delegate = config.get("cgroup", "")
        if not re.fullmatch(r"[a-z0-9-]+\.slice", slice_name) or not delegate.startswith("/sys/fs/cgroup/"):
            raise RunnerError("UNSUPPORTED", "invalid predelegated slice admission")
        delegation = Path(delegate)
        if delegation.resolve() != delegation or not os.access(delegation / "cgroup.procs", os.W_OK):
            raise RunnerError("UNSUPPORTED", "cgroup delegation unavailable")
        shown = self._command("show", slice_name, "--property=ControlGroup", "--value")
        if shown.returncode or shown.stdout.decode().strip() != delegate[len("/sys/fs/cgroup"):]:
            raise RunnerError("UNSUPPORTED", "slice and delegated cgroup differ")
        execution = _plain(plan.get("execution", plan))
        if plan.get("budgets"):
            execution["budgets"] = _plain(plan["budgets"])
        if plan.get("phase") == "reconcile":
            suffix = hashlib.sha256(plan["execution_id"].encode()).hexdigest()[:16]
            original_roots = dict(execution["roots"])
            execution["roots"] = {key: path + "-observe-" + suffix for key, path in original_roots.items()}
            execution["observed_roots"] = original_roots
            execution["writable"] = list(execution["roots"].values())
            execution["readonly"] = execution.get("readonly", []) + list(original_roots.values())
            execution["environment"] = ledger_jobs.clean_environment(execution["roots"]["temporary"])
            if execution.get("storage"):
                execution["observed_storage"] = execution.pop("storage")
                execution["readonly"].append(execution["observed_storage"]["archive_root"])
        if plan.get("phase") == "evidence":
            snapshot = plan.get("evidence_snapshot")
            store_root = plan.get("evidence_store_root")
            if not isinstance(snapshot, dict) or not isinstance(store_root, str):
                raise RunnerError("UNSUPPORTED", "trusted evidence snapshot is missing")
            suffix = hashlib.sha256(plan["execution_id"].encode()).hexdigest()[:16]
            original_readonly = execution.get("readonly", [])
            execution["roots"] = {key: path + "-seal-" + suffix for key, path in execution["roots"].items()}
            execution["writable"] = list(execution["roots"].values()) + [store_root]
            execution["readonly"] = original_readonly + [snapshot["root"]]
            execution["environment"] = ledger_jobs.clean_environment(execution["roots"]["temporary"])
            execution["evidence_snapshot"], execution["evidence_store_root"] = snapshot, store_root
            execution["broker_events"] = _plain(plan.get("broker_events", snapshot.get("broker_events", [])))
            execution["storage"] = {}
        if execution.get("storage"):
            binding = execution["storage"].get("stable_mount_binding")
            if not isinstance(binding, dict) or set(binding) != {"source", "root", "type", "device", "inode"}:
                raise RunnerError("UNSUPPORTED", "exact NAS namespace binding required")
            # Network filesystem server quotas cannot be proved using a local
            # boolean. This kernel query fails closed unless the OS exposes an
            # enforceable quota for this exact admitted writable archive root.
            raise RunnerError("UNSUPPORTED", "network archive hard quota adapter is not implemented; NAS execution is blocked")
        budgets = execution["budgets"]
        quotas = {name: _verify_project_quota(path, budgets["temporary_bytes"] if name == "temporary" else budgets["reservation_bytes"])
                  for name, path in execution["roots"].items()}
        for path in set(execution["writable"]) - set(execution["roots"].values()):
            quotas[path] = _verify_project_quota(path, budgets["reservation_bytes"])
        distinct = {(item["mount"]["source"], item["project_id"]): item["hard_bytes"] for item in quotas.values()}
        if sum(distinct.values()) > budgets["reservation_bytes"]:
            raise RunnerError("UNSUPPORTED", "combined hard quotas exceed the reserved peak capacity")
        return execution, quotas

    def start(self, identity, plan, cancel_event):
        try:
            return self._start(identity, plan, cancel_event)
        except RunnerError as error:
            handle = self._runs.get(identity["unit"])
            delivery_attempted = handle is not None and (handle.get("delivery_attempted") or handle.get("launch") is not None)
            if error.code == "UNSUPPORTED" and not delivery_attempted:
                raise _NoStartError(error.code, str(error)) from error
            raise

    def _start(self, identity, plan, cancel_event):
        plan = dict(plan, execution_id=identity["execution_id"])
        execution, quotas = self._admit(plan)
        unit = identity["unit"]
        if unit in self._runs: raise RunnerError("CONFLICT", "manager identity reuse")
        for root in execution["roots"].values():
            path = Path(root)
            path.mkdir(mode=0o700, parents=False, exist_ok=True)
            if path.resolve() != path or not path.is_dir() or path.stat().st_uid != os.geteuid():
                raise RunnerError("UNSUPPORTED", "job root ownership mismatch")
        execution = dict(execution)
        execution["phase"] = plan.get("phase", "business")
        execution["execution_id"] = identity["execution_id"]
        execution["unit"] = identity["unit"]
        execution["quota_observation"] = quotas
        execution["parent_mount_namespace"] = os.readlink("/proc/self/ns/mnt")
        evidence = Path(execution["roots"]["evidence"])
        suffix = hashlib.sha256(identity["execution_id"].encode()).hexdigest()[:24]
        plan_path = evidence / ("plan-" + suffix + ".json")
        result_path = evidence / ("result-" + suffix + ".json")
        execution["result_path"] = str(result_path)
        raw = json.dumps(execution, sort_keys=True, separators=(",", ":")).encode()
        with plan_path.open("xb") as stream:
            os.chmod(plan_path, 0o400); stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        limits = execution["budgets"]
        properties = {"Slice": self.configuration["slice"], "Type": "exec", "KillMode": "control-group",
            "SendSIGKILL": "yes", "RemainAfterExit": "yes", "RuntimeMaxSec": str(limits["wall_seconds"]),
            "TimeoutStopSec": str(limits["terminate_grace_seconds"]), "MemoryMax": str(limits["memory_bytes"]),
            "TasksMax": str(limits["processes"]), "CPUQuota": str(min(100, limits["cpu_seconds"] * 100 / limits["wall_seconds"])) + "%", "CPUQuotaPeriodSec": "1ms", "LimitCPU": str(limits["cpu_seconds"]),
            "LimitFSIZE": str(limits["temporary_bytes"]), "NoNewPrivileges": "yes", "ProtectSystem": "strict",
            "ProtectHome": "read-only", "PrivateUsers": "yes", "PrivateMounts": "yes", "PrivateNetwork": "yes", "PrivateDevices": "yes", "RestrictSUIDSGID": "yes",
            "ProtectKernelTunables": "yes", "ProtectKernelModules": "yes", "ProtectControlGroups": "yes",
            "RestrictNamespaces": "yes", "LockPersonality": "yes", "UMask": "0077",
            "InaccessiblePaths": "/tmp /var/tmp /dev/shm /run/dbus /run/user/" + str(os.geteuid()), "StandardOutput": "null", "StandardError": "null",
            "ReadWritePaths": " ".join(execution["writable"]), "ReadOnlyPaths": " ".join(execution.get("readonly", []))}
        if execution.get("storage"):
            archive = execution["storage"]["archive_root"]
            properties["PrivateMounts"] = "yes"
            properties["BindPaths"] = archive + ":" + archive
        if any(re.search(r"[\s\\]", p) for p in execution["writable"] + execution.get("readonly", [])):
            raise RunnerError("UNSUPPORTED", "systemd path admission requires unambiguous paths")
        command = ["/usr/bin/systemd-run", "--user", "--quiet", "--unit=" + unit]
        command.extend("--property=" + key + "=" + value for key, value in properties.items() if value)
        command.extend(["--", execution["python"], "-I", str(Path(__file__).resolve()), "--helper", str(plan_path)])
        handle = {"unit": unit, "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                  "result_path": str(result_path), "cgroup_parent": self.configuration["cgroup"],
                  "cancel_event": cancel_event, "launch": None, "launch_acked": False, "stop_acked": False,
                  "stop_requested": False, "started": time.monotonic(), "deadline": limits["wall_seconds"],
                  "invocation_id": None, "execution_id": identity["execution_id"], "cancel_before_launch": False,
                  "identity": dict(identity), "recovered": False, "delivery_attempted": False}
        self._runs[unit] = handle
        if cancel_event.is_set():
            handle["cancel_before_launch"] = True
            return handle
        # The last request delivery shares the broker's durable cancellation
        # and policy-generation fence. There is no event-only production path.
        # Popen enqueues the fixed manager client; it never waits for systemd's
        # acceptance. An already delivered client still needs delayed-start proof.
        if self._start_guard is None:
            raise RunnerError("UNSUPPORTED", "the durable broker startup guard is not bound")
        def deliver():
            if cancel_event.is_set():
                return None
            # Mark before Popen: an exception does not prove no process was created.
            handle["delivery_attempted"] = True
            handle["launch"] = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin", "XDG_RUNTIME_DIR": "/run/user/" + str(os.geteuid())})
            return handle["launch"]
        try:
            accepted = self._start_guard(identity["execution_id"], deliver)
        except OSError as error:
            raise RunnerError("IO_UNCERTAIN", "manager launch acknowledgement missing") from error
        if accepted is None:
            if handle["launch"] is not None:
                raise RunnerError("IO_UNCERTAIN", "startup guard returned no receipt after manager delivery")
            handle["cancel_before_launch"] = True
        return handle

    def export_handle(self, handle):
        fields = ("boot_id", "result_path", "cgroup_parent", "launch_acked", "stop_acked", "invocation_id", "execution_id")
        return {**{key: value for key, value in handle["identity"].items() if key != "manager"},
                "manager": {key: handle.get(key) for key in fields}}

    def _retained_delivery(self, identity):
        """Read only the original request receipt after a delivery exception."""
        handle = self._runs.get(identity.get("unit"))
        if (handle is not None and handle.get("delivery_attempted") is True
                and Runner._same_handle(handle.get("identity", {}), identity)):
            return handle
        return None

    def reattach(self, identity, plan, cancel_event):
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
        handle = {"unit": identity["unit"], "identity": dict(identity), "boot_id": saved.get("boot_id", current_boot),
                  "result_path": result_path, "cgroup_parent": expected_group, "cancel_event": cancel_event,
                  "launch": None, "launch_acked": saved.get("launch_acked") is True and saved.get("boot_id") == current_boot,
                  "stop_acked": saved.get("stop_acked") is True, "stop_requested": False,
                  "invocation_id": saved.get("invocation_id"), "execution_id": identity["execution_id"],
                  "started": time.monotonic(), "deadline": plan.get("budgets", execution["budgets"])["wall_seconds"],
                  "cancel_before_launch": False, "recovered": True}
        self._runs[identity["unit"]] = handle
        return handle

    def stop(self, handle):
        handle["stop_requested"] = True
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

    def inspect(self, handle):
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
            if idle or time.monotonic() - handle["started"] > handle["deadline"]:
                handle["stop_requested"] = True
                self.stop(handle)
            return {**_unknown(), "state": "RUNNING" if not idle else "UNKNOWN",
                    "identity": {"boot_id": handle["boot_id"], "invocation_id": invocation, "cgroup": group}}
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


def _capture_stage(stage, directory, limit, remaining):
    """Drain both pipes independently; truncate storage, continue draining."""
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


def _interpreter_temp_check(python, plan, directory):
    # The Ledger interpreters need not have Local Hand installed. Keep this
    # independent probe standard-library-only, with the same failure semantics.
    code = ("import os,pathlib,tempfile\n"
        "p=pathlib.Path(os.environ['TMPDIR'])\n"
        "assert p.is_dir() and p.resolve()==p\n"
        "assert pathlib.Path(tempfile.gettempdir())==p\n"
        "f,n=tempfile.mkstemp(dir=p)\n"
        "original_error=None\n"
        "try:\n"
        "    if os.write(f,b'lh') != 2: raise OSError('temporary probe write was incomplete')\n"
        "    os.fsync(f)\n"
        "except BaseException as error:\n"
        "    original_error=error\n"
        "    raise\n"
        "finally:\n"
        "    cleanup_error=None\n"
        "    for action in (lambda: os.close(f), lambda: os.unlink(n)):\n"
        "        try: action()\n"
        "        except BaseException as error:\n"
        "            if cleanup_error is None: cleanup_error=error\n"
        "    if cleanup_error is not None:\n"
        "        if original_error is not None: original_error.add_note('temporary probe cleanup was incomplete')\n"
        "        else: raise cleanup_error\n")
    stage = {"name": "temp-" + hashlib.sha256(python.encode()).hexdigest()[:12],
             "argv": [python, "-I", "-c", code], "cwd": plan["roots"]["work"], "env": plan["environment"]}
    observation = _capture_stage(stage, directory, min(16384, plan["budgets"]["log_bytes"]), 10)
    if observation["outcome"] != "SUCCEEDED": raise ledger_jobs.LedgerPlanError("actual interpreter temporary binding failed")


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
    phase = plan["phase"]
    output = {"execution_id": plan["execution_id"], "outcome": "FAILED", "effects_checked": False,
              "business_started": False, "helper_started": True, "facts": {}, "stages": [], "retention": plan.get("retention")}
    work, evidence = Path(plan["roots"]["work"]), Path(plan["roots"]["evidence"])
    directory = evidence / (phase + "-" + hashlib.sha256(plan["execution_id"].encode()).hexdigest()[:16])
    directory.mkdir(mode=0o700)
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
        output["facts"]["cgroup_limits"] = _verify_cgroup_limits(plan)
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
            for python in sorted(set(interpreters)): _interpreter_temp_check(python, plan, directory)
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
                max_source_bytes=plan["budgets"]["reservation_bytes"])
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
                import platform, sqlite3
                output["facts"].update(python=sys.version, sqlite=sqlite3.sqlite_version,
                    os=platform.system(), machine=platform.machine(), mounts={k: _mount_for(v) for k, v in plan["roots"].items()})
                output.update(outcome="SUCCEEDED", effects_checked=True)
            else:
                output["business_started"] = True
                ledger_jobs.copy_verified_source(plan)
                start = time.monotonic()
                remaining_logs = plan["budgets"]["log_bytes"]
                checked = set()
                for stage in plan["stages"]:
                    python = stage["argv"][0]
                    if python not in checked:
                        _interpreter_temp_check(python, plan, directory); checked.add(python)
                    observed = _capture_stage(stage, directory, remaining_logs, plan["budgets"]["wall_seconds"] - (time.monotonic() - start))
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
    return 0 if output["outcome"] == "SUCCEEDED" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private fixed runner helper; not a caller command interface")
    parser.add_argument("--helper", required=True)
    args = parser.parse_args(argv)
    path = Path(args.helper)
    if not path.is_absolute() or path.is_symlink(): return 2
    raw = ledger_jobs.bounded_regular_bytes(path, 4 * 1024 * 1024)
    return _helper(json.loads(raw))


if __name__ == "__main__":
    raise SystemExit(main())
