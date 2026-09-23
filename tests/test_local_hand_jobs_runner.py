"""Trusted DI simulations are distinguished from real cgroup integration."""
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from local_hand_jobs import runner


class DelayedManager:
    """Only instantiated inside tests, never selected by any runtime field."""
    def __init__(self):
        self.gate = threading.Event()
        self.entered = threading.Event()
        self.launches = 0
        self.stops = 0
        self.exit = False
    def start(self, handle, plan, cancel):
        self.entered.set()
        self.gate.wait(2)
        self.cancelled_before_launch = cancel.is_set()
        if not self.cancelled_before_launch: self.launches += 1
        return dict(handle)
    def stop(self, handle): self.stops += 1
    def inspect(self, handle):
        if self.cancelled_before_launch or self.exit:
            return {**runner._unknown(), "state": "EXITED", "future_start_blocked": True,
                    "tree_exited": True, "collectors_stopped": True, "writers_stopped": True,
                    "effects_checked": True, "exit_code": 0, "result": {"outcome": "SUCCEEDED"}}
        return {**runner._unknown("delayed manager acknowledgement"), "state": "RUNNING"}


def await_state(supervisor, handle, expected):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        value = supervisor.inspect(handle)
        if value["state"] == expected: return value
        time.sleep(.01)
    raise AssertionError(supervisor.inspect(handle))


def budgeted_plan(plan, *, operation_id="fixture", record_id=None, now=None):
    """Trusted test admission: create a real internal grant, never a bypass."""
    phase = plan["phase"]
    namespace = "reconcile" if phase == "reconcile" else "job"
    record_id = record_id or operation_id
    execution = plan.get("execution", plan)
    limits = dict(wall_seconds=30, terminate_grace_seconds=1, cpu_seconds=9,
                  memory_bytes=1024**2, processes=8, temporary_bytes=1024**2,
                  nas_bytes=0, log_bytes=1024, reservation_bytes=4 * 1024**2)
    limits.update(execution.get("budgets", {}))
    original = dict(limits)
    for key in ("wall_seconds", "cpu_seconds", "log_bytes"):
        original[key] *= 2 if namespace == "reconcile" else 3
    now = runner.budget.current_clock() if now is None else now
    row = {"namespace": namespace, "id": record_id, "parent": operation_id,
           "plan": {"budgets": original}, "record": {"handles": {}, "phase": "QUEUED",
               "lifecycle": "ACCEPTED", "business_started": False, "helper_started": False,
               "exit_proof": None}}
    phases = ("reconcile", "evidence") if namespace == "reconcile" else ("preflight", "business", "evidence")
    for predecessor in phases:
        row["record"]["phase"] = ("PREFLIGHT_COMPLETE" if predecessor == "business" else
                                  "AWAITING_SEAL" if predecessor == "evidence" else "QUEUED")
        state, grant = runner.budget.reserve(row, predecessor, now=now)
        row["record"]["execution_budget"] = state
        row["record"]["handles"][predecessor] = {"execution_id": grant["execution_id"]}
        if predecessor == phase: break
    execution["budgets"] = grant["limits"]
    plan.update(execution_id=grant["execution_id"], budgets=grant["limits"], budget_grant=grant)
    return plan


@contextlib.contextmanager
def admitted_bootstrap_plan(plan, directory):
    """Consume real precreated roots in a private ledger for manager fixtures.

    The manager remains a trusted OS simulation; root identity and one-use
    consumption use the same allocator as the broker, not a fabricated grant.
    """
    from local_hand_jobs import bootstrap_roots
    from local_hand_jobs.state import StateStore

    execution, grant = plan["execution"], plan["budget_grant"]
    execution["operation_id"] = grant["operation_id"]
    slot = {"slot_id": "runner-fixture", "roots": {}}
    for name, value in execution["roots"].items():
        path = Path(value)
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.stat()
        slot["roots"][name] = {"path": str(path), "device": info.st_dev,
                                "inode": info.st_ino, "uid": info.st_uid}
    state_root = Path(directory) / "admission-state"
    state_root.mkdir(mode=0o700)
    state = StateStore(state_root / "roots.sqlite3", "fixture-authority", "fixture-ledger", initialize=True)
    try:
        with state.transaction() as tx:
            row = state.insert(tx, grant["namespace"], grant["record_id"], grant["operation_id"],
                               "fixture-owner", "fixture-digest", {}, plan,
                               execution["budgets"]["reservation_bytes"])
            if plan["phase"] == "business":
                bootstrap_roots.reserve(state, tx, row, "preflight", [slot])
            allocation = bootstrap_roots.reserve(state, tx, row, plan["phase"], [slot])
        plan["bootstrap_allocation"] = allocation
        yield plan
    finally:
        state.close()


@contextlib.contextmanager
def helper_budget_fixture(phase):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        roots = {name: str(root / name) for name in ("work", "temporary", "evidence")}
        for path in roots.values(): Path(path).mkdir()
        environment = runner.ledger_jobs.clean_environment(roots["temporary"])
        target = root / "evidence" / "result.json"
        plan = {"phase": phase, "execution_id": "budget-" + phase, "kind": "ledger.test.source",
            "roots": roots, "prepared": {"build_python": sys.executable,
                "runtime_python": str(Path(sys.executable).resolve())},
            "environment": environment, "parent_mount_namespace": "original-namespace",
            "result_path": str(target), "budgets": {"log_bytes": 10, "wall_seconds": 10},
            "stages": [{"name": "business-output", "argv": [sys.executable, "-I", "-c",
                "import os;os.write(1,b'1234567890')"], "cwd": roots["work"], "env": environment}]}
        # Use distinct names even when the test interpreter is not a venv.
        alternate = root / "other-python"
        alternate.symlink_to(Path(sys.executable).resolve())
        plan["prepared"]["runtime_python"] = str(alternate)
        mount = {"source": "fixture", "root": "/", "type": "ext4", "options": "ro"}
        with patch.dict(os.environ, {}, clear=True), patch.object(tempfile, "tempdir", None), \
                patch.object(os, "readlink", return_value="private-namespace"), \
                patch.object(os, "access", return_value=False), \
                patch.object(runner, "_mount_for", return_value=mount), \
                patch.object(runner, "_verify_cgroup_limits", return_value={}), \
                patch.object(runner.ledger_jobs, "verify_inputs", return_value={"inputs_stable": True}), \
                patch.object(runner.ledger_jobs, "copy_verified_source"):
            yield budgeted_plan(plan), target


class RunnerTests(unittest.TestCase):
    def test_host_inspection_records_business_entry_separately_from_preflight(self):
        import platform
        for mode in ("complete", "partial_failure", "late_budget_failure", "preflight", "input_rejected"):
            phase = "preflight" if mode == "preflight" else "business"
            with self.subTest(mode=mode), helper_budget_fixture(phase) as (plan, target):
                plan.update(kind="host.inspect", python=sys.executable)
                observations = []
                def host_system():
                    observations.append("host observation")
                    if mode == "partial_failure" and len(observations) == 2:
                        raise OSError("host observation failed after business entry")
                    return "Linux"
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(platform, "system", side_effect=host_system))
                    launched = stack.enter_context(patch.object(runner.subprocess, "Popen"))
                    stack.enter_context(patch.object(runner, "_interpreter_temp_check",
                        return_value={"outcome": "SUCCEEDED", "bytes_retained": {}}))
                    if mode == "input_rejected":
                        stack.enter_context(patch.object(runner.ledger_jobs, "verify_inputs",
                            side_effect=runner.ledger_jobs.LedgerPlanError("input rejected")))
                    if mode == "late_budget_failure":
                        stack.enter_context(patch.object(runner, "_deadline_remaining",
                            side_effect=runner.JobError("LIMIT_EXCEEDED", "completion exhausted")))
                    code = runner._helper(plan)
                launched.assert_not_called()
                result = json.loads(target.read_text())
                started = mode not in ("preflight", "input_rejected")
                failed = mode in ("partial_failure", "input_rejected")
                self.assertIs(result["business_started"], started)
                self.assertTrue(result["helper_started"])
                self.assertEqual(len(observations), 2 if started else 1)
                self.assertEqual(code, 1 if failed or mode == "late_budget_failure" else 0)
                self.assertEqual(result["outcome"], "FAILED" if failed else "SUCCEEDED")
                self.assertIs(result["effects_checked"], not failed)

    def test_quota_descriptor_cleanup_preserves_admission_errors_and_reports_its_own_failure(self):
        import struct
        for mode in ("missing_quota", "io_failure", "verified"):
            for close_failure in (False, True):
                with self.subTest(mode=mode, close_failure=close_failure), tempfile.TemporaryDirectory() as folder:
                    real_close = os.close
                    closed = []
                    def close(descriptor):
                        real_close(descriptor)
                        closed.append(descriptor)
                        if close_failure: raise OSError("quota close acknowledgement failed")
                    def ioctl(descriptor, request, buffer, mutate):
                        if mode == "io_failure": raise OSError("quota read failed")
                        if mode == "verified": buffer[:20] = struct.pack("=IIIII", 0x200, 0, 0, 8, 0)
                        return 0
                    class QuotaLibrary:
                        def quotactl(self, command, source, project_id, quota):
                            quota._obj.bhard = 1
                            return 0
                    with patch.object(runner, "_mount_for", return_value={"type": "ext4", "source": "fixture"}), \
                            patch.object(runner.fcntl, "ioctl", side_effect=ioctl), \
                            patch.object(runner.ctypes, "CDLL", return_value=QuotaLibrary()), \
                            patch.object(os, "close", side_effect=close):
                        if mode != "verified":
                            with self.assertRaises(runner.RunnerError) as failure:
                                runner._verify_project_quota(folder, 4096)
                            self.assertEqual(failure.exception.code, "UNSUPPORTED")
                            message = "inherited project quota missing" if mode == "missing_quota" else "project hard quota cannot be verified"
                            self.assertEqual(str(failure.exception), message)
                            self.assertEqual(bool(getattr(failure.exception, "__notes__", [])), close_failure)
                        elif close_failure:
                            with self.assertRaisesRegex(OSError, "quota close acknowledgement failed"):
                                runner._verify_project_quota(folder, 4096)
                        else:
                            proof = runner._verify_project_quota(folder, 4096)
                            self.assertEqual(proof["project_id"], 8)
                            self.assertEqual(proof["hard_bytes"], 1024)
                    self.assertEqual(len(closed), 1)
                    with self.assertRaises(OSError): os.fstat(closed[0])

    def test_final_helper_budget_failure_preserves_checked_business_facts(self):
        import hashlib
        from local_hand_jobs import evidence
        for phase in ("business", "reconcile", "preflight", "evidence"):
            for error_code in ("LIMIT_EXCEEDED", "IO_UNCERTAIN", "relative_timeout"):
                with self.subTest(phase=phase, error=error_code), helper_budget_fixture(phase) as (plan, target):
                    plan.update(kind="host.inspect", python=sys.executable,
                                observed_roots={"work": plan["roots"]["work"]})
                    source = Path(plan["roots"]["work"]) / "known-work"
                    source.write_bytes(b"known complete work")
                    plan["evidence_store_root"] = str(target.parent / "store")
                    plan["evidence_snapshot"] = {"operation_id": "fixture", "event_seq": 7,
                        "root": plan["roots"]["work"], "members": ["known-work"], "bindings": {},
                        "quiescence": {"execution_id": "previous-phase", "event_seq": 7,
                            "future_starts_blocked": True, "tree_exited": True,
                            "collectors_stopped": True, "writers_stopped": True}}
                    observation = {"outcome": "SUCCEEDED", "bytes_retained": {"stdout": 0, "stderr": 0}}
                    publication = {"operation_id": "fixture", "complete": True}
                    final_check = (-1 if error_code == "relative_timeout" else
                                   runner.JobError(error_code, "completion budget failure"))
                    checks = [1_000_000_000, final_check] if phase == "preflight" else [final_check]
                    with patch.object(runner, "_interpreter_temp_check", return_value=observation), \
                            patch.object(runner, "_deadline_remaining", side_effect=checks), \
                            patch.object(evidence, "EvidenceStore") as store:
                        store.return_value.publish_only.return_value = publication
                        code = runner._helper(plan)
                    result = json.loads(target.read_text())
                    checked_business = phase in ("business", "reconcile")
                    self.assertEqual(code, 1)
                    self.assertEqual(result["outcome"], "SUCCEEDED" if checked_business else "FAILED")
                    self.assertEqual(result["effects_checked"], checked_business)
                    self.assertEqual(result["helper_error"]["code"],
                                     "LIMIT_EXCEEDED" if error_code == "relative_timeout" else error_code)
                    self.assertEqual(result["helper_error"]["stage"], "completion_budget")
                    self.assertEqual(source.read_bytes(), b"known complete work")
                    if phase == "business": self.assertIn("python", result["facts"])
                    if phase == "reconcile":
                        self.assertEqual(result["result"]["observed_files"]["work"]["known-work"],
                                         hashlib.sha256(b"known complete work").hexdigest())
                    if phase == "evidence": self.assertEqual(result["seal_record"], publication)

    def test_expired_operation_grant_blocks_helper_before_output_io(self):
        with helper_budget_fixture("business") as (plan, target):
            grant = plan["budget_grant"]
            clock = {"boot_id": grant["boot_id"], "boottime_ns": grant["deadline_boottime_ns"] + 1}
            with patch.object(runner.budget, "current_clock", return_value=clock), \
                    patch.object(Path, "mkdir", side_effect=AssertionError("expired output creation")) as create:
                with self.assertRaises(runner.JobError) as failure: runner._helper(plan)
            self.assertEqual(failure.exception.code, "LIMIT_EXCEEDED")
            create.assert_not_called()
            self.assertEqual(list(target.parent.iterdir()), [])

    def test_manager_final_delivery_caps_deadline_and_reserves_stop_grace(self):
        class Prepared(runner.SystemdManager):
            def _admit(self, plan): return runner._plain(plan["execution"]), {}
        # The phase now starts at durable reservation, not delayed delivery.
        for elapsed in (0, 7, 9, 10):
            with self.subTest(elapsed=elapsed), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                roots = {key: str(root / key) for key in ("work", "temporary", "evidence")}
                clock = dict(runner.budget.current_clock(), boottime_ns=100_000_000_000)
                execution = {"roots": roots, "budgets": {"wall_seconds": 10, "cpu_seconds": 3},
                             "python": sys.executable, "writable": list(roots.values()), "readonly": []}
                plan = budgeted_plan({"phase": "business", "execution": execution}, now=clock)
                identity = {"job_key": "fixture", "phase": "business", "execution_id": plan["execution_id"],
                            "unit": "lhj-test-budget.service"}
                manager = Prepared({"slice": "fixture.slice", "cgroup": "/sys/fs/cgroup/fixture"})
                def guard(execution_id, launch, *, stage):
                    self.assertEqual(stage, "bootstrap")
                    clock["boottime_ns"] += elapsed * runner.budget.NANOSECONDS
                    return launch()
                manager.set_start_guard(guard)
                with admitted_bootstrap_plan(plan, folder), \
                        patch.object(runner.budget, "current_clock", side_effect=lambda: dict(clock)), \
                        patch.object(runner.subprocess, "Popen", return_value=object()) as launched:
                    if elapsed >= 9:
                        with self.assertRaises(runner._NoStartError) as failure:
                            manager.start(identity, plan, threading.Event())
                        self.assertEqual(failure.exception.code, "LIMIT_EXCEEDED")
                        launched.assert_not_called()
                        continue
                    handle = manager.start(identity, plan, threading.Event())
                properties = dict(item.removeprefix("--property=").split("=", 1)
                                  for item in launched.call_args.args[0] if item.startswith("--property="))
                self.assertEqual(properties["RuntimeMaxSec"], "9000000us" if elapsed == 0 else "2000000us")
                self.assertEqual(properties["TimeoutStopSec"], "1")
                self.assertEqual(properties["CPUQuota"], "10.000000%")
                self.assertEqual(properties["LimitCPU"], "1")
                self.assertEqual(handle["bootstrap"]["phase_deadline_boottime_ns"], 109_000_000_000)
                self.assertLessEqual(handle["bootstrap"]["phase_deadline_boottime_ns"] + runner.budget.NANOSECONDS,
                                     plan["budget_grant"]["deadline_boottime_ns"])

    def test_cpu_quota_is_floored_and_rejects_unrepresentable_small_rates(self):
        self.assertEqual(runner._cpu_quota({"cpu_seconds": 1, "wall_seconds": 3}), "33.333333%")
        self.assertEqual(runner._cpu_quota({"cpu_seconds": 1, "wall_seconds": 1000}), "0.100000%")
        self.assertEqual(runner._cpu_quota({"cpu_seconds": 100, "wall_seconds": 3}), "100.000000%")
        for wall in (1001, 2**53 - 1):
            with self.subTest(wall=wall), self.assertRaises(runner.RunnerError) as failure:
                runner._cpu_quota({"cpu_seconds": 1, "wall_seconds": wall})
            self.assertEqual(failure.exception.code, "UNSUPPORTED")

    def test_absolute_deadline_blocks_child_when_boottime_advances(self):
        with helper_budget_fixture("business") as (plan, target):
            grant = plan["budget_grant"]
            deadline = grant["started_boottime_ns"] + 9 * runner.budget.NANOSECONDS
            clock = {"boot_id": grant["boot_id"], "boottime_ns": deadline + 1}
            stage = plan["stages"][0]
            with patch.object(runner.budget, "current_clock", return_value=clock), \
                    patch.object(runner.subprocess, "Popen") as launched:
                with self.assertRaises(runner.JobError) as failure:
                    runner._capture_stage(stage, target.parent, 100, 100, (grant, deadline))
            self.assertEqual(failure.exception.code, "LIMIT_EXCEEDED")
            launched.assert_not_called()
            self.assertEqual(list(target.parent.iterdir()), [])

    def test_recovery_does_not_renew_phase_deadline_or_legacy_runtime(self):
        import hashlib
        import subprocess
        for mode in ("retained", "missing_receipt", "legacy", "lost_budget_with_receipt", "damaged_budget",
                     "damaged_receipt_type", "damaged_receipt_grace"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                roots = {key: str(root / key) for key in ("work", "temporary", "evidence")}
                clock = dict(runner.budget.current_clock(), boottime_ns=100_000_000_000)
                plan = budgeted_plan({"phase": "business", "execution": {"roots": roots, "budgets": {"wall_seconds": 10}}}, now=clock)
                execution_id = plan["execution_id"]
                suffix = hashlib.sha256(execution_id.encode()).hexdigest()
                unit = "lhj-" + suffix + ".service"
                old_deadline = 109_000_000_000 if mode in ("retained", "lost_budget_with_receipt", "damaged_budget") else None
                if mode == "damaged_receipt_type": old_deadline = "109000000000"
                if mode == "damaged_receipt_grace": old_deadline = plan["budget_grant"]["deadline_boottime_ns"]
                identity = {"job_key": "fixture", "execution_id": execution_id, "phase": "business", "unit": unit,
                    "manager": {"boot_id": clock["boot_id"], "cgroup_parent": "/sys/fs/cgroup/fixture", "launch_acked": True,
                        "result_path": str(root / "evidence" / ("result-" + suffix[:24] + ".json")),
                        "invocation_id": "a" * 32, "phase_deadline_boottime_ns": old_deadline}}
                if mode in ("legacy", "lost_budget_with_receipt"): plan.pop("budget_grant")
                if mode == "damaged_budget": plan["budget_grant"]["version"] = 2
                manager = runner.SystemdManager({"cgroup": "/sys/fs/cgroup/fixture"})
                with patch.object(manager, "support", return_value={"supported": True}):
                    handle = manager.reattach(identity, plan, threading.Event())
                retained_deadline = old_deadline if mode == "retained" else None
                self.assertEqual(handle["phase_deadline_boottime_ns"], retained_deadline)
                clock["boottime_ns"] = 112_000_000_000
                show = ("ActiveState=active\nSubState=running\nControlGroup=/fixture/" + unit +
                        "\nInvocationID=" + "a" * 32 + "\nJob=\n")
                original_read = Path.read_text
                def read(path, *args, **kwargs):
                    if str(path).endswith("/cgroup.events"): return "populated 1\n"
                    return original_read(path, *args, **kwargs)
                with patch.object(runner.budget, "current_clock", return_value=clock), \
                        patch.object(Path, "read_text", read), \
                        patch.object(manager, "_command", return_value=subprocess.CompletedProcess([], 0, show.encode())), \
                        patch.object(manager, "_stop_unit", return_value=runner._unknown()) as stop:
                    proof = manager.inspect(handle)
                stop.assert_called_once_with(handle)
                self.assertFalse(proof["future_start_blocked"])
                self.assertFalse(proof["tree_exited"])
                self.assertEqual(handle["phase_deadline_boottime_ns"], retained_deadline)

    def test_helper_probe_logs_share_preflight_and_business_log_budget(self):
        for phase in ("preflight", "business"):
            for limit in (10, 20):
                with self.subTest(phase=phase, limit=limit), helper_budget_fixture(phase) as (plan, target):
                    plan["budgets"]["log_bytes"] = limit
                    budgeted_plan(plan)
                    capture = runner._capture_stage
                    def noisy_probe(stage, *args):
                        if stage["name"].startswith("temp-"):
                            stage = dict(stage, argv=list(stage["argv"]))
                            stage["argv"][-1] += "\nos.write(1,b'1234567890')\n"
                        return capture(stage, *args)
                    with patch.object(runner, "_capture_stage", side_effect=noisy_probe):
                        code = runner._helper(plan)
                    logs = list(target.parent.rglob("*.stdout")) + list(target.parent.rglob("*.stderr"))
                    self.assertEqual(len(logs), 4)
                    self.assertEqual(sum(path.stat().st_size for path in logs), limit)
                    result = json.loads(target.read_text())
                    self.assertEqual(len(result["stages"]), 2)
                    self.assertEqual(sum(sum(stage["bytes_retained"].values()) for stage in result["stages"]), limit)
                    self.assertEqual(any(stage["truncated"] for stage in result["stages"]), limit == 10)
                    self.assertEqual(result["outcome"], "SUCCEEDED" if limit == 20 else "FAILED")
                    self.assertEqual(code, 0 if limit == 20 else 1)

    def test_helper_cannot_launch_probe_after_input_checks_exhaust_wall_budget(self):
        for phase in ("preflight", "business"):
            with self.subTest(phase=phase), helper_budget_fixture(phase) as (plan, target):
                clock = [0.0]
                def slow_inputs(plan):
                    clock[0] = 11.0
                    return {"inputs_stable": True}
                with patch.object(runner.time, "monotonic", side_effect=lambda: clock[0]), \
                        patch.object(runner.ledger_jobs, "verify_inputs", side_effect=slow_inputs), \
                        patch.object(runner.subprocess, "Popen", side_effect=AssertionError("expired launch")) as launched:
                    code = runner._helper(plan)
                launched.assert_not_called()
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(target.read_text())["outcome"], "FAILED")

    def test_unsupported_after_manager_delivery_is_not_no_start_proof(self):
        class AdmittedManager(runner.SystemdManager):
            def _admit(self, plan):
                return runner._plain(plan["execution"]), {}
        with tempfile.TemporaryDirectory() as directory:
            roots = {name: str(Path(directory) / name) for name in ("work", "temporary", "evidence")}
            limits = {"wall_seconds": 30, "terminate_grace_seconds": 2, "cpu_seconds": 30,
                "memory_bytes": 1024**2, "processes": 8, "temporary_bytes": 1024**2,
                "nas_bytes": 0, "log_bytes": 1024, "reservation_bytes": 4 * 1024**2}
            execution = {"roots": roots, "budgets": limits, "python": sys.executable,
                "writable": list(roots.values()), "readonly": [], "environment": {"PATH": "/usr/bin:/bin"}}
            manager = AdmittedManager({"slice": "fixture.slice", "cgroup": "/sys/fs/cgroup/fixture"})
            self.addCleanup(setattr, manager, "inspect", lambda handle: {
                **runner._unknown("fixture observation complete"), "terminal_observation": True})
            delivered = threading.Event()
            def guard(identity, launch, *, stage):
                self.assertEqual(stage, "bootstrap")
                launch()
                delivered.set()
                raise runner.RunnerError("UNSUPPORTED", "fixture failure after manager delivery")
            manager.set_start_guard(guard)
            supervisor = runner.Runner(manager)
            plan = budgeted_plan({"execution": execution, "phase": "business"}, operation_id="job")
            with admitted_bootstrap_plan(plan, directory), \
                    patch.object(runner.subprocess, "Popen", return_value=object()) as launch:
                handle = supervisor.start("job", plan["execution_id"], plan)
                self.assertTrue(delivered.wait(1))
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    proof = supervisor.inspect(handle)
                    if proof["result"].get("error") == "UNSUPPORTED": break
                    time.sleep(.01)
                launch.assert_called_once()
                self.assertEqual(proof["state"], "UNKNOWN")
                self.assertFalse(proof["future_start_blocked"])
                self.assertFalse(proof["tree_exited"])
                self.assertFalse(proof["effects_checked"])

    def test_transient_observer_error_retains_handle_and_cancel_control(self):
        class UncertainOnce(DelayedManager):
            def __init__(self):
                super().__init__()
                self.observations = 0
            def inspect(self, handle):
                self.observations += 1
                if self.observations == 1:
                    raise runner.RunnerError("IO_UNCERTAIN", "one unavailable manager read")
                return super().inspect(handle)
            def stop(self, handle):
                super().stop(handle)
                self.exit = True
        manager = UncertainOnce(); manager.gate.set()
        supervisor = runner.Runner(manager)
        handle = supervisor.start("job", "transient-observer-business", {"phase": "business"})
        self.addCleanup(setattr, manager, "exit", True)
        await_state(supervisor, handle, "RUNNING")
        supervisor.stop(handle)
        proof = await_state(supervisor, handle, "EXITED")
        self.assertTrue(proof["tree_exited"])
        self.assertEqual(manager.launches, 1)
        self.assertGreater(manager.stops, 0)

    def test_transient_stop_error_is_retried_without_restarting_execution(self):
        class StopUncertainOnce(DelayedManager):
            def stop(self, handle):
                super().stop(handle)
                if self.stops == 1:
                    raise runner.RunnerError("IO_UNCERTAIN", "one unavailable stop receipt")
                self.exit = True
        manager = StopUncertainOnce(); manager.gate.set()
        supervisor = runner.Runner(manager)
        handle = supervisor.start("job", "transient-stop-business", {"phase": "business"})
        self.addCleanup(setattr, manager, "exit", True)
        await_state(supervisor, handle, "RUNNING")
        supervisor.stop(handle)
        proof = await_state(supervisor, handle, "EXITED")
        self.assertTrue(proof["future_start_blocked"])
        self.assertEqual(manager.launches, 1)
        self.assertGreaterEqual(manager.stops, 2)

    def test_delivery_exception_keeps_original_manager_handle_cancellable(self):
        class Receipt:
            returncode = 0
            def poll(self): return 0
        class DeliveredManager(runner.SystemdManager):
            def _admit(self, plan): return runner._plain(plan["execution"]), {}
            def inspect(self, handle):
                stopped = handle["bootstrap"]["stop_requested"]
                return {**runner._unknown(), "state": "EXITED" if stopped else "RUNNING",
                        "tree_exited": stopped, "future_start_blocked": stopped}
            def stop(self, handle): handle["bootstrap"]["stop_requested"] = True
        with tempfile.TemporaryDirectory() as directory:
            roots = {name: str(Path(directory) / name) for name in ("work", "temporary", "evidence")}
            limits = {"wall_seconds": 30, "terminate_grace_seconds": 2, "cpu_seconds": 30,
                "memory_bytes": 1024**2, "processes": 8, "temporary_bytes": 1024**2,
                "nas_bytes": 0, "log_bytes": 1024, "reservation_bytes": 4 * 1024**2}
            execution = {"roots": roots, "budgets": limits, "python": sys.executable,
                "writable": list(roots.values()), "readonly": [], "environment": {"PATH": "/usr/bin:/bin"}}
            manager = DeliveredManager({"slice": "fixture.slice", "cgroup": "/sys/fs/cgroup/fixture"})
            def uncertain_receipt(identity, launch, *, stage):
                self.assertEqual(stage, "bootstrap")
                launch()
                raise runner.RunnerError("IO_UNCERTAIN", "receipt failed after manager delivery")
            manager.set_start_guard(uncertain_receipt)
            supervisor = runner.Runner(manager)
            plan = budgeted_plan({"execution": execution, "phase": "business"}, operation_id="job")
            with admitted_bootstrap_plan(plan, directory), \
                    patch.object(runner.subprocess, "Popen", return_value=Receipt()) as launch:
                handle = supervisor.start("job", plan["execution_id"], plan)
                await_state(supervisor, handle, "RUNNING")
                supervisor.stop(handle)
                proof = await_state(supervisor, handle, "EXITED")
                self.assertTrue(proof["future_start_blocked"])
                self.assertEqual(proof["recovery_handle"]["execution_id"], handle["execution_id"])
                self.assertEqual(proof["recovery_handle"]["manager"]["version"], 2)
                self.assertIsNone(supervisor._executions[handle["execution_id"]].manager_handle["helper"])
                launch.assert_called_once()

    def test_delayed_start_cancel_remains_responsive_and_blocks_future_spawn(self):
        manager = DelayedManager(); supervisor = runner.Runner(manager)
        before = time.monotonic()
        handle = supervisor.start("job", "job-1-preflight", {"phase": "preflight"})
        self.assertLess(time.monotonic() - before, .2)
        self.assertTrue(manager.entered.wait(1))
        self.assertFalse(supervisor.stop(handle)["future_start_blocked"])
        self.assertLess(time.monotonic() - before, .3)
        manager.gate.set()
        proof = await_state(supervisor, handle, "EXITED")
        self.assertTrue(proof["future_start_blocked"])
        self.assertTrue(proof["tree_exited"])
        self.assertEqual(manager.launches, 0)

    def test_cancel_ack_without_tree_exit_retains_unknown_barrier(self):
        manager = DelayedManager(); manager.gate.set()
        supervisor = runner.Runner(manager)
        handle = supervisor.start("job", "job-2-business", {"phase": "business"})
        await_state(supervisor, handle, "RUNNING")
        supervisor.stop(handle)
        time.sleep(.08)
        proof = supervisor.inspect(handle)
        self.assertFalse(proof["tree_exited"])
        self.assertFalse(proof["future_start_blocked"])
        self.assertGreater(manager.stops, 0)
        manager.exit = True
        await_state(supervisor, handle, "EXITED")

    def test_identity_reuse_forgery_and_restart_never_spawn_again(self):
        manager = DelayedManager(); manager.gate.set(); manager.exit = True
        supervisor = runner.Runner(manager)
        handle = supervisor.start("job", "job-3-business", {"phase": "business"})
        await_state(supervisor, handle, "EXITED")
        with self.assertRaises(runner.RunnerError): supervisor.start("job", "job-3-business", {"phase": "business"})
        self.assertEqual(supervisor.inspect(dict(handle, unit="forged"))["state"], "UNKNOWN")
        self.assertEqual(runner.Runner(manager).inspect(handle)["state"], "UNKNOWN")
        self.assertEqual(manager.launches, 1)

    def test_original_cancel_does_not_cancel_independent_reconcile(self):
        manager = DelayedManager(); manager.gate.set(); manager.exit = True
        supervisor = runner.Runner(manager)
        business = supervisor.start("job", "job-4-business", {"phase": "business"})
        await_state(supervisor, business, "EXITED")
        reconciliation = supervisor.start("job", "reconcile-4-reconcile", {"phase": "reconcile"})
        supervisor.stop(business)
        self.assertFalse(supervisor._executions[reconciliation["execution_id"]].cancel.is_set())
        await_state(supervisor, reconciliation, "EXITED")

    def test_recovery_observes_original_unit_without_replaying_start(self):
        class RecoverableManager(DelayedManager):
            def __init__(self):
                super().__init__(); self.reattaches = 0
            def reattach(self, identity, plan, cancel):
                self.reattaches += 1
                return dict(identity)
        manager = RecoverableManager(); manager.gate.set(); manager.exit = True
        original = runner.Runner(manager)
        handle = original.start("job", "job-5-business", {"phase": "business"})
        await_state(original, handle, "EXITED")
        recovered = runner.Runner(manager)
        recovered_handle = recovered.reattach(handle, {"phase": "business"})
        self.assertEqual(await_state(recovered, recovered_handle, "EXITED")["state"], "EXITED")
        self.assertEqual(manager.launches, 1)
        self.assertEqual(manager.reattaches, 1)
        recovered.reattach(handle, {"phase": "business"})
        self.assertEqual(manager.reattaches, 1)

    def test_production_default_honestly_reports_unsupported(self):
        manager = runner.SystemdManager()
        self.assertEqual(manager.support()["status"], "UNSUPPORTED")
        supervisor = runner.Runner(manager)
        handle = supervisor.start("job", "unsupported-business", {"phase": "business"})
        proof = await_state(supervisor, handle, "EXITED")
        self.assertEqual(proof["result"]["error"], "UNSUPPORTED")
        self.assertEqual(proof["result"]["outcome"], "FAILED")
        self.assertFalse(proof["result"]["business_started"])

    def test_unverified_e3_blocks_even_an_otherwise_supported_host(self):
        manager = runner.SystemdManager({"uid": 1000, "slice": "admitted.slice",
            "cgroup": "/sys/fs/cgroup/admitted.slice"})
        with patch.object(runner.sys, "platform", "linux"), patch.object(os, "geteuid", return_value=1000), \
                patch.object(Path, "read_text", return_value="systemd\n"), \
                patch.object(Path, "is_file", return_value=True), patch.object(os, "access", return_value=True):
            support = manager.support()
        self.assertFalse(support["supported"])
        self.assertEqual(support["status"], "UNSUPPORTED")
        self.assertEqual(support["reasons"], ["E3_SUPERVISION_UNVERIFIED"])

    def test_limited_capture_drains_stdout_stderr_and_retains_truncation(self):
        with tempfile.TemporaryDirectory() as root:
            stage = {"name": "noisy", "argv": [sys.executable, "-I", "-c", "import os;os.write(1,b'x'*16384);os.write(2,b'y'*16384)"],
                     "cwd": root, "env": {"PATH": "/usr/bin:/bin"}}
            observed = runner._capture_stage(stage, root, 1024, 2)
            self.assertEqual(sum(observed["bytes_retained"].values()), 1024)
            self.assertGreater(sum(observed["bytes_discarded"].values()), 0)
            self.assertTrue(observed["truncated"])
            self.assertEqual(observed["outcome"], "FAILED")
            self.assertLessEqual(sum(Path(root, "noisy." + kind).stat().st_size for kind in ("stdout", "stderr")), 1024)

    def test_actual_interpreter_temp_probe_rejects_zero_write(self):
        from local_hand_jobs import runner
        import sys
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            temporary = root / "temporary"; temporary.mkdir()
            plan = {"roots": {"work": str(root), "temporary": str(temporary)},
                    "environment": runner.ledger_jobs.clean_environment(str(temporary)),
                    "budgets": {"log_bytes": 16384}}
            capture = runner._capture_stage
            def inject_zero_write(stage, *args):
                stage = dict(stage, argv=list(stage["argv"]))
                stage["argv"][-1] = ("import os\noriginal_write = os.write\n"
                    "os.write = lambda fd, data: 0 if data == b'lh' else original_write(fd, data)\n"
                    + stage["argv"][-1])
                return capture(stage, *args)
            with patch.object(runner, "_capture_stage", side_effect=inject_zero_write):
                with self.assertRaises(runner.ledger_jobs.LedgerPlanError):
                    runner._interpreter_temp_check(sys.executable, plan, root)
            self.assertEqual(list(temporary.iterdir()), [])

    def test_actual_interpreter_temp_probe_close_failure_still_unlinks(self):
        from local_hand_jobs import runner
        import sys
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            temporary = root / "temporary"; temporary.mkdir()
            plan = {"roots": {"work": str(root), "temporary": str(temporary)},
                    "environment": runner.ledger_jobs.clean_environment(str(temporary)),
                    "budgets": {"log_bytes": 16384}}
            capture = runner._capture_stage
            def inject_close_failure(stage, *args):
                stage = dict(stage, argv=list(stage["argv"]))
                stage["argv"][-1] = ("import os\noriginal_write, original_close = os.write, os.close\n"
                    "probe_descriptor = None\n"
                    "def track_write(fd, data):\n"
                    "    global probe_descriptor\n"
                    "    if data == b'lh': probe_descriptor = fd\n"
                    "    return original_write(fd, data)\n"
                    "def close_then_fail(fd):\n"
                    "    original_close(fd)\n"
                    "    if fd == probe_descriptor: raise OSError('probe close acknowledgement unavailable')\n"
                    "os.write, os.close = track_write, close_then_fail\n"
                    + stage["argv"][-1])
                return capture(stage, *args)
            with patch.object(runner, "_capture_stage", side_effect=inject_close_failure):
                with self.assertRaises(runner.ledger_jobs.LedgerPlanError):
                    runner._interpreter_temp_check(sys.executable, plan, root)
            self.assertEqual(list(temporary.iterdir()), [])

    def test_actual_interpreter_anonymous_probe_retains_concurrent_files(self):
        for mutation in ("file", "directory", "before-create", "unsupported"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                temporary = root / "temporary"; temporary.mkdir()
                plan = {"roots": {"work": str(root), "temporary": str(temporary)},
                        "environment": runner.ledger_jobs.clean_environment(str(temporary)),
                        "budgets": {"log_bytes": 16384}}
                capture = runner._capture_stage
                def inject(stage, *args):
                    stage = dict(stage, argv=list(stage["argv"]))
                    if mutation in ("before-create", "unsupported"):
                        injection = (
                            "import os,pathlib\noriginal_open=os.open\n"
                            "def replace_before_create(path,flags,*args,**kwargs):\n"
                            "    if flags & os.O_TMPFILE == os.O_TMPFILE:\n"
                            "        root=pathlib.Path(os.environ['TMPDIR'])\n"
                            + ("        raise OSError('anonymous file capability unavailable')\n" if mutation == "unsupported" else
                               "        root.rename(root.parent/'retained-original'); root.mkdir()\n"
                               "        (root/'concurrent-owner').write_bytes(b'concurrent-owner-data')\n")
                            +
                            "    return original_open(path,flags,*args,**kwargs)\n"
                            "os.open=replace_before_create\n")
                    else:
                        injection = (
                            "import os,pathlib\noriginal_fsync=os.fsync\n"
                            "def replace_after_sync(fd):\n"
                            "    original_fsync(fd)\n"
                            "    root=pathlib.Path(os.environ['TMPDIR'])\n"
                            "    assert os.fstat(fd).st_nlink==0 and list(root.iterdir())==[]\n"
                            + ("" if mutation == "file" else
                               "    root.rename(root.parent/'retained-original'); root.mkdir()\n")
                            + "    (root/'concurrent-owner').write_bytes(b'concurrent-owner-data')\n"
                            + "os.fsync=replace_after_sync\n")
                    stage["argv"][-1] = injection + stage["argv"][-1]
                    return capture(stage, *args)
                with patch.object(runner, "_capture_stage", side_effect=inject):
                    if mutation == "file":
                        runner._interpreter_temp_check(sys.executable, plan, root)
                    else:
                        with self.assertRaises(runner.ledger_jobs.LedgerPlanError):
                            runner._interpreter_temp_check(sys.executable, plan, root)
                expected = [] if mutation == "unsupported" else [b"concurrent-owner-data"]
                self.assertEqual([p.read_bytes() for p in temporary.iterdir()], expected)
                if mutation in ("directory", "before-create"):
                    self.assertEqual(list((root / "retained-original").iterdir()), [])

    def test_expired_stage_budget_cannot_start_a_side_effecting_program(self):
        import subprocess
        actual_popen = subprocess.Popen
        for remaining in (0, -1):
            with self.subTest(remaining=remaining), tempfile.TemporaryDirectory() as root:
                stage = {"name": "expired", "argv": [sys.executable, "-I", "-c",
                    "import pathlib;pathlib.Path('effect').write_text('executed')"],
                    "cwd": root, "env": {"PATH": "/usr/bin:/bin"}}
                # A child may run while its launching thread is descheduled.
                # Waiting here makes that normal scheduling window deterministic.
                def delivered(*args, **kwargs):
                    child = actual_popen(*args, **kwargs)
                    child.wait(timeout=2)
                    return child
                with patch.object(runner.subprocess, "Popen", side_effect=delivered) as launch:
                    with self.assertRaisesRegex(runner.ledger_jobs.LedgerPlanError, "budget exhausted"):
                        runner._capture_stage(stage, root, 1024, remaining)
                    launch.assert_not_called()
                self.assertFalse(Path(root, "effect").exists())

    def test_pipe_eof_does_not_end_the_childs_remaining_execution_budget(self):
        with tempfile.TemporaryDirectory() as root:
            stage = {"name": "closed-output", "argv": [sys.executable, "-I", "-c",
                "import os,pathlib,time;os.close(1);os.close(2);time.sleep(.35);pathlib.Path('completed').write_text('done')"],
                "cwd": root, "env": {"PATH": "/usr/bin:/bin"}}
            observed = runner._capture_stage(stage, root, 1024, 2)
            self.assertEqual(observed["outcome"], "SUCCEEDED")
            self.assertEqual(observed["exit_code"], 0)
            self.assertEqual(Path(root, "completed").read_text(), "done")
            self.assertFalse(observed["drain_incomplete"])

    def test_pipe_eof_does_not_disable_the_childs_execution_deadline(self):
        with tempfile.TemporaryDirectory() as root:
            stage = {"name": "closed-output-timeout", "argv": [sys.executable, "-I", "-c",
                "import os,time;os.close(1);os.close(2);time.sleep(60)"],
                "cwd": root, "env": {"PATH": "/usr/bin:/bin"}}
            observed = runner._capture_stage(stage, root, 1024, .15)
            self.assertEqual(observed["outcome"], "FAILED")
            self.assertTrue(observed["truncated"])
            self.assertLess(observed["elapsed_seconds"], 3)

    def test_capture_setup_failure_reaps_direct_child_and_closes_both_pipes(self):
        import subprocess
        actual_popen = subprocess.Popen
        for fault in ("stdout", "stderr", "selector"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as root:
                stage = {"name": "setup", "argv": [sys.executable, "-I", "-c", "import time;time.sleep(60)"],
                         "cwd": root, "env": {"PATH": "/usr/bin:/bin"}}
                if fault != "selector":
                    Path(root, "setup." + fault).write_bytes(b"preserve prior evidence")
                children = []
                def launch(*args, **kwargs):
                    child = actual_popen(*args, **kwargs)
                    children.append(child)
                    return child
                try:
                    with patch.object(runner.subprocess, "Popen", side_effect=launch):
                        if fault == "selector":
                            with patch.object(runner.selectors, "DefaultSelector", side_effect=OSError("selector unavailable")):
                                with self.assertRaises(OSError): runner._capture_stage(stage, root, 1024, 2)
                        else:
                            with self.assertRaises(FileExistsError): runner._capture_stage(stage, root, 1024, 2)
                    self.assertEqual(len(children), 1)
                    self.assertIsNotNone(children[0].poll(), "setup failure left the stage running")
                    self.assertTrue(children[0].stdout.closed)
                    self.assertTrue(children[0].stderr.closed)
                    if fault != "selector":
                        self.assertEqual(Path(root, "setup." + fault).read_bytes(), b"preserve prior evidence")
                finally:
                    for child in children:
                        if child.poll() is None: child.kill()
                        child.wait(timeout=2)
                        child.stdout.close(); child.stderr.close()

    def test_capture_log_sync_failure_closes_every_retained_stream(self):
        with tempfile.TemporaryDirectory() as root:
            stage = {"name": "sync", "argv": [sys.executable, "-I", "-c", "import os;os.write(1,b'out');os.write(2,b'err')"],
                     "cwd": root, "env": {"PATH": "/usr/bin:/bin"}}
            actual_open = Path.open
            streams = []
            def opened(path, *args, **kwargs):
                stream = actual_open(path, *args, **kwargs)
                streams.append(stream)
                return stream
            try:
                with patch.object(Path, "open", opened), patch.object(os, "fsync", side_effect=OSError("evidence sync unavailable")):
                    with self.assertRaisesRegex(OSError, "evidence sync unavailable"):
                        runner._capture_stage(stage, root, 1024, 2)
                self.assertEqual(len(streams), 2)
                self.assertTrue(all(stream.closed for stream in streams))
                self.assertEqual(Path(root, "sync.stdout").read_bytes(), b"out")
                self.assertEqual(Path(root, "sync.stderr").read_bytes(), b"err")
            finally:
                for stream in streams: stream.close()

    def test_capture_cleanup_failure_is_not_hidden_by_a_callers_handled_error(self):
        with tempfile.TemporaryDirectory() as root:
            stage = {"name": "ambient", "argv": [sys.executable, "-I", "-c", "print('complete')"],
                     "cwd": root, "env": {"PATH": "/usr/bin:/bin"}}
            try:
                raise LookupError("unrelated caller recovery")
            except LookupError as ambient:
                with patch.object(os, "fsync", side_effect=OSError("stage log sync unavailable")):
                    with self.assertRaisesRegex(OSError, "stage log sync unavailable"):
                        runner._capture_stage(stage, root, 1024, 2)
                self.assertFalse(hasattr(ambient, "__notes__"))
            self.assertEqual(Path(root, "ambient.stdout").read_text(), "complete\n")

    def test_reconcile_missing_original_root_never_proves_effects_checked(self):
        import json
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            roots = {name: str(root / name) for name in ("work", "temporary", "evidence")}
            for path in roots.values(): Path(path).mkdir()
            plan = {"phase": "reconcile", "execution_id": "missing-root-reconcile",
                    "kind": "ledger.test.source", "roots": roots,
                    "budgets": {"log_bytes": 1024, "wall_seconds": 10},
                    "observed_roots": {"work": str(root / "missing-original")},
                    "environment": runner.ledger_jobs.clean_environment(roots["temporary"]),
                    "parent_mount_namespace": "original-namespace",
                    "result_path": str(root / "evidence" / "result.json")}
            budgeted_plan(plan)
            mount = {"source": "fixture", "root": "/", "type": "ext4", "options": "ro"}
            # This is a helper-unit fixture, not real cgroup/bootstrap acceptance.
            with patch.dict(os.environ, {}, clear=True), patch.object(tempfile, "tempdir", None), \
                    patch.object(os, "readlink", return_value="private-namespace"), \
                    patch.object(os, "access", return_value=False), patch.object(runner, "_mount_for", return_value=mount), \
                    patch.object(runner, "_verify_cgroup_limits", return_value={}):
                code = runner._helper(plan)
            result = json.loads(Path(plan["result_path"]).read_text())
            self.assertEqual(code, 1)
            self.assertEqual(result["outcome"], "FAILED")
            self.assertFalse(result["effects_checked"])
            self.assertNotIn("observed_files", result.get("result", {}))

    def test_prepared_inventory_scan_error_cannot_claim_complete_readonly_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "wheel.whl").write_bytes(b"fixture wheel")
            hidden = root / "runtime-venv"; hidden.mkdir()
            (hidden / "unseen.py").write_bytes(b"must be inventoried")
            plan = {"prepared": {"root": str(root), "wheel": str(root / "wheel.whl")},
                    "source": {"blobs": {}}}
            scan = os.scandir
            def unavailable(path):
                if Path(path) == hidden:
                    raise PermissionError("injected runtime inventory failure")
                return scan(path)
            with patch.object(os, "scandir", side_effect=unavailable):
                with self.assertRaises(runner.ledger_jobs.LedgerPlanError):
                    runner._inventory_prepared(plan)

    def test_empty_group_does_not_prove_unacknowledged_start_cancelled(self):
        class Pending:
            def poll(self): return None
        manager = runner.SystemdManager()
        handle = {"launch": Pending(), "stop_requested": False}
        proof = manager.stop(handle)
        self.assertFalse(proof["future_start_blocked"])
        self.assertFalse(proof["tree_exited"])

    def test_nas_quota_is_explicitly_unsupported_not_boolean_admitted(self):
        class AdmittedManagerProbe(runner.SystemdManager):
            def support(self): return {"supported": True}
        manager = AdmittedManagerProbe({"slice": "fixture.slice", "cgroup": "/sys/fs/cgroup/fixture", "uid": 1000})
        with tempfile.TemporaryDirectory() as directory:
            roots = {name: str(Path(directory) / name) for name in ("work", "temporary", "evidence")}
            execution = {"roots": roots, "writable": list(roots.values()), "readonly": [],
                "storage": {"archive_root": "/synthetic/archive", "stable_mount_binding": {
                    "source": "synthetic-nas", "root": "/synthetic", "type": "nfs", "device": 123, "inode": 456}}}
            plan = budgeted_plan({"execution": execution, "phase": "business"})
            with admitted_bootstrap_plan(plan, directory), \
                    patch.object(manager, "_command", side_effect=AssertionError("NAS rejection must precede launch")) as command:
                with self.assertRaisesRegex(runner.RunnerError, "network archive hard quota adapter is not implemented"):
                    manager._admit(plan)
                command.assert_not_called()

    def test_manager_requires_recursive_exit_and_no_queued_job(self):
        import json, subprocess
        class Receipt:
            returncode = 0
            def poll(self): return 0
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "result.json"
            result.write_text(json.dumps({"execution_id": "execution-fixture", "outcome": "SUCCEEDED", "effects_checked": True}))
            manager = runner.SystemdManager()
            unit = "lhj-fixture.service"
            handle = {"unit": unit, "boot_id": "boot-fixture", "result_path": str(result),
                      "cgroup_parent": "/sys/fs/cgroup/admitted", "launch": Receipt(), "launch_acked": False,
                      "stop_acked": False, "stop_requested": False, "started": time.monotonic(),
                      "deadline": 10, "invocation_id": None, "execution_id": "execution-fixture",
                      "cancel_before_launch": False}
            values = {"LoadState": "loaded", "ActiveState": "active", "SubState": "exited",
                      "ControlGroup": "/admitted/" + unit, "InvocationID": "a" * 32, "Job": "",
                      "ExecMainCode": "1", "ExecMainStatus": "0", "Result": "success"}
            population = ["0"]
            original_read = Path.read_text
            def fixed_read(path, *args, **kwargs):
                if str(path) == "/proc/sys/kernel/random/boot_id": return "boot-fixture"
                if str(path).endswith("/cgroup.events"): return "populated " + population[0] + "\n"
                return original_read(path, *args, **kwargs)
            def show(*args, **kwargs):
                if "--property=InvocationID" in args:
                    return subprocess.CompletedProcess([], 0, (values["InvocationID"] + "\n").encode())
                return subprocess.CompletedProcess([], 0, "\n".join(key + "=" + value for key, value in values.items()).encode())
            with patch.object(Path, "read_text", fixed_read), patch.object(manager, "_command", side_effect=show):
                self.assertTrue(manager.inspect(handle)["tree_exited"])
                values["Job"] = "73"
                self.assertFalse(manager.inspect(handle)["future_start_blocked"])
                values["Job"] = ""; population[0] = "1"
                self.assertFalse(manager.inspect(handle)["tree_exited"])
                population[0] = "0"; values["InvocationID"] = "b" * 32
                self.assertEqual(manager.inspect(handle)["state"], "UNKNOWN")

    def test_manager_discards_foreign_and_nonobject_results_after_proven_exit(self):
        import json, subprocess
        class Receipt:
            returncode = 0
            def poll(self): return 0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            manager = runner.SystemdManager()
            unit = "lhj-result-fixture.service"
            handle = {"unit": unit, "boot_id": "boot-fixture", "result_path": str(path),
                "cgroup_parent": "/sys/fs/cgroup/admitted", "launch": Receipt(), "launch_acked": True,
                "stop_acked": False, "stop_requested": False, "started": time.monotonic(), "deadline": 10,
                "invocation_id": "a" * 32, "execution_id": "execution-fixture", "cancel_before_launch": False}
            show = ("LoadState=loaded\nActiveState=active\nSubState=exited\nControlGroup=/admitted/" + unit +
                    "\nInvocationID=" + "a" * 32 + "\nJob=\nExecMainCode=1\nExecMainStatus=0\nResult=success\n")
            original_read = Path.read_text
            def observation(path, *args, **kwargs):
                if str(path) == "/proc/sys/kernel/random/boot_id": return "boot-fixture"
                if str(path).endswith("/cgroup.events"): return "populated 0\n"
                return original_read(path, *args, **kwargs)
            foreign = {"execution_id": "another-execution", "outcome": "SUCCEEDED", "effects_checked": True,
                       "facts": {"inputs_stable": True}, "prepared": {"root": "/foreign"}}
            malformed = dict(foreign, execution_id="execution-fixture", facts=[])
            with patch.object(Path, "read_text", observation), patch.object(manager, "_command",
                    return_value=subprocess.CompletedProcess([], 0, show.encode())):
                for candidate in (foreign, [], None, "foreign", 7, {}, malformed):
                    with self.subTest(candidate=candidate):
                        path.write_text(json.dumps(candidate))
                        proof = manager.inspect(handle)
                        self.assertEqual(proof["state"], "EXITED")
                        self.assertTrue(proof["tree_exited"])
                        self.assertFalse(proof["effects_checked"])
                        self.assertFalse(proof["helper_result_verified"])
                        self.assertEqual(proof["facts"], {})
                        self.assertEqual(proof["result"], {"outcome": "UNKNOWN"})
                        self.assertTrue(proof["missing"])
                path.write_text(json.dumps(dict(foreign, execution_id="execution-fixture")))
                proof = manager.inspect(handle)
                self.assertTrue(proof["effects_checked"])
                self.assertTrue(proof["helper_result_verified"])
                path.write_text(json.dumps(dict(foreign, execution_id="execution-fixture", outcome="UNKNOWN")))
                handle["stop_requested"] = True
                proof = manager.inspect(handle)
                self.assertTrue(proof["helper_result_verified"])
                self.assertEqual(proof["result"]["outcome"], "UNKNOWN")

    def test_business_result_survives_helper_result_directory_sync_failure(self):
        import json, subprocess
        class Receipt:
            returncode = 0
            def poll(self): return 0
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roots = {name: str(root / name) for name in ("work", "temporary", "evidence")}
            for path in roots.values(): Path(path).mkdir()
            environment = runner.ledger_jobs.clean_environment(roots["temporary"])
            target = root / "evidence" / "result.json"
            plan = {"phase": "business", "execution_id": "durable-result-business",
                "kind": "ledger.test.source", "roots": roots, "prepared": {},
                "environment": environment, "parent_mount_namespace": "original-namespace",
                "result_path": str(target), "budgets": {"log_bytes": 1024, "wall_seconds": 10},
                "stages": [{"name": "fixed-fixture", "argv": [sys.executable, "-I", "-c",
                    "import pathlib;pathlib.Path('business-complete').write_text('done')"],
                    "cwd": roots["work"], "env": environment}]}
            budgeted_plan(plan)
            evidence_identity = (target.parent.stat().st_dev, target.parent.stat().st_ino)
            actual_fsync = os.fsync
            sync_failed = False
            def failed_result_directory_sync(descriptor):
                nonlocal sync_failed
                info = os.fstat(descriptor)
                if (info.st_dev, info.st_ino) == evidence_identity:
                    sync_failed = True
                    raise OSError("result directory durability unavailable")
                return actual_fsync(descriptor)
            mount = {"source": "fixture", "root": "/", "type": "ext4", "options": "ro"}
            # Only host admission and upstream input preparation are simulated;
            # the business child, result bytes and failed fsync are exercised.
            with patch.dict(os.environ, {}, clear=True), patch.object(tempfile, "tempdir", None), \
                    patch.object(os, "readlink", return_value="private-namespace"), \
                    patch.object(os, "access", return_value=False), patch.object(runner, "_mount_for", return_value=mount), \
                    patch.object(runner, "_verify_cgroup_limits", return_value={}), \
                    patch.object(runner.ledger_jobs, "verify_inputs", return_value={"inputs_stable": True}), \
                    patch.object(runner.ledger_jobs, "copy_verified_source"), \
                    patch.object(os, "fsync", side_effect=failed_result_directory_sync):
                with self.assertRaisesRegex(OSError, "result directory durability unavailable"):
                    runner._helper(plan)
            self.assertTrue(sync_failed)
            self.assertEqual((root / "work" / "business-complete").read_text(), "done")
            candidate = json.loads(target.read_text())
            self.assertEqual(candidate["outcome"], "SUCCEEDED")
            self.assertTrue(candidate["effects_checked"])
            manager = runner.SystemdManager()
            unit = "lhj-result-fixture.service"
            handle = {"unit": unit, "boot_id": "boot-fixture", "result_path": str(target),
                "cgroup_parent": "/sys/fs/cgroup/admitted", "launch": Receipt(), "launch_acked": True,
                "stop_acked": False, "stop_requested": False, "started": time.monotonic(), "deadline": 10,
                "invocation_id": "a" * 32, "execution_id": plan["execution_id"], "cancel_before_launch": False}
            show = ("LoadState=loaded\nActiveState=failed\nSubState=failed\nControlGroup=/admitted/" + unit +
                    "\nInvocationID=" + "a" * 32 + "\nJob=\nExecMainCode=1\nExecMainStatus=1\nResult=exit-code\n")
            original_read = Path.read_text
            def observation(path, *args, **kwargs):
                if str(path) == "/proc/sys/kernel/random/boot_id": return "boot-fixture"
                if str(path).endswith("/cgroup.events"): return "populated 0\n"
                return original_read(path, *args, **kwargs)
            with patch.object(Path, "read_text", observation), patch.object(manager, "_command",
                    return_value=subprocess.CompletedProcess([], 0, show.encode())):
                proof = manager.inspect(handle)
            self.assertTrue(proof.get("helper_result_verified"))
            self.assertEqual(proof["exit_code"], 1)
            self.assertEqual(proof["result"]["outcome"], "SUCCEEDED")
            self.assertTrue(proof["effects_checked"])
            self.assertEqual(proof["result"]["execution_id"], plan["execution_id"])

    def test_manager_capture_enforces_limit_while_reading(self):
        import subprocess
        actual = subprocess.Popen
        def noisy(*args, **kwargs):
            return actual([sys.executable, "-I", "-c", "import os;os.write(1,b'x'*(2*1024*1024))"], **kwargs)
        with patch.object(subprocess, "Popen", side_effect=noisy):
            with self.assertRaisesRegex(runner.RunnerError, "manager output exceeds bound"):
                runner.SystemdManager()._command("list-units", "lhj-*.service")

    def test_manager_selector_close_failure_still_reaps_direct_child(self):
        import json, subprocess
        actual_popen = subprocess.Popen
        selector = runner.selectors.DefaultSelector()
        actual_close = selector.close
        children = []
        def launch(*args, **kwargs):
            child = actual_popen([sys.executable, "-I", "-c", "import time;time.sleep(60)"], **kwargs)
            children.append(child)
            return child
        def failed_close():
            actual_close()
            raise OSError("selector close acknowledgement unavailable")
        try:
            with patch.object(runner.subprocess, "Popen", side_effect=launch), \
                    patch.object(runner.selectors, "DefaultSelector", return_value=selector), \
                    patch.object(selector, "close", side_effect=failed_close) as closed:
                try:
                    runner.SystemdManager()._command("show", "fixture.service", timeout=.05)
                except Exception as error:
                    observed_error = error
                else:
                    self.fail("timed out manager command unexpectedly succeeded")
            facts = {"error": type(observed_error).__name__, "child_running": children[0].poll() is None,
                     "stdout_closed": children[0].stdout.closed, "selector_close_calls": closed.call_count}
            print(json.dumps(facts, sort_keys=True))
            self.assertFalse(facts["child_running"], "selector cleanup failure stranded the direct manager client")
            self.assertTrue(facts["stdout_closed"])
            self.assertEqual(facts["selector_close_calls"], 1)
            self.assertIsInstance(observed_error, runner.RunnerError)
            self.assertEqual(observed_error.code, "IO_UNCERTAIN")
            self.assertIn("manager observation timeout", str(observed_error))
        finally:
            for child in children:
                if child.poll() is None: child.kill()
                child.wait(timeout=2)
                child.stdout.close()
            actual_close()

    def test_manager_cleanup_failure_is_not_hidden_by_a_callers_handled_error(self):
        import subprocess
        actual_popen = subprocess.Popen
        selector = runner.selectors.DefaultSelector()
        actual_close = selector.close
        children = []
        def launch(*args, **kwargs):
            child = actual_popen([sys.executable, "-I", "-c", "print('complete')"], **kwargs)
            children.append(child)
            return child
        def failed_close():
            actual_close()
            raise OSError("selector close acknowledgement unavailable")
        try:
            try:
                raise LookupError("unrelated caller recovery")
            except LookupError as ambient:
                with patch.object(runner.subprocess, "Popen", side_effect=launch), \
                        patch.object(runner.selectors, "DefaultSelector", return_value=selector), \
                        patch.object(selector, "close", side_effect=failed_close):
                    with self.assertRaises(runner.RunnerError) as failed:
                        runner.SystemdManager()._command("show", "fixture.service")
                self.assertEqual(failed.exception.code, "IO_UNCERTAIN")
                self.assertFalse(hasattr(ambient, "__notes__"))
            self.assertEqual(children[0].poll(), 0)
            self.assertTrue(children[0].stdout.closed)
        finally:
            for child in children:
                if child.poll() is None: child.kill()
                child.wait(timeout=2)
                child.stdout.close()
            actual_close()

    def test_final_manager_delivery_requires_durable_guard_and_honors_denial(self):
        class PreparedManager(runner.SystemdManager):
            def _admit(self, plan):
                return runner._plain(plan["execution"]), {}
        for mode in ("missing", "denied", "cancelled_at_guard", "authorized"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                roots = {name: str(Path(directory) / name) for name in ("work", "temporary", "evidence")}
                limits = {"wall_seconds": 30, "terminate_grace_seconds": 2, "cpu_seconds": 30,
                    "memory_bytes": 1024**2, "processes": 8, "temporary_bytes": 1024**2,
                    "nas_bytes": 0, "log_bytes": 1024, "reservation_bytes": 4 * 1024**2}
                execution = {"roots": roots, "budgets": limits, "python": sys.executable,
                    "writable": list(roots.values()), "readonly": [], "environment": {"PATH": "/usr/bin:/bin"}}
                manager = PreparedManager({"slice": "fixture.slice", "cgroup": "/sys/fs/cgroup/fixture"})
                plan = budgeted_plan({"execution": execution, "phase": "business"}, operation_id="job-fixture")
                identity = {"job_key": "job-fixture", "execution_id": plan["execution_id"], "phase": "business",
                            "unit": "lhj-guard-fixture.service"}
                cancel = threading.Event()
                in_fence = [False]
                guard_calls = []
                if mode != "missing":
                    def guard(execution_id, launch, *, stage):
                        self.assertEqual(stage, "bootstrap")
                        guard_calls.append(execution_id)
                        in_fence[0] = True
                        try:
                            if mode == "denied": return None
                            if mode == "cancelled_at_guard": cancel.set()
                            return launch()
                        finally: in_fence[0] = False
                    manager.set_start_guard(guard)
                receipt = object()
                def delivered(*args, **kwargs):
                    import hashlib
                    self.assertTrue(in_fence[0])
                    expected_unit = "lhj-" + hashlib.sha256((plan["execution_id"] + ":bootstrap").encode()).hexdigest() + ".service"
                    self.assertIn("--unit=" + expected_unit, args[0])
                    self.assertIn("--bootstrap", args[0])
                    self.assertNotIn("--helper", args[0])
                    return receipt
                with admitted_bootstrap_plan(plan, directory), \
                        patch.object(runner.subprocess, "Popen", side_effect=delivered) as launch:
                    if mode == "missing":
                        with self.assertRaisesRegex(runner.RunnerError, "startup guard is not bound"):
                            manager.start(identity, plan, cancel)
                        launch.assert_not_called()
                    else:
                        handle = manager.start(identity, plan, cancel)
                        self.assertEqual(guard_calls, [plan["execution_id"]])
                        if mode == "authorized":
                            launch.assert_called_once()
                            self.assertIs(handle["bootstrap"]["launch"], receipt)
                            self.assertFalse(handle["bootstrap"]["cancel_before_launch"])
                            self.assertIsNone(handle["helper"])
                        else:
                            launch.assert_not_called()
                            self.assertTrue(manager.inspect(handle)["future_start_blocked"])
                            self.assertTrue(manager.inspect(handle)["tree_exited"])

    def test_real_delegated_cgroup_integration_is_not_a_simulated_pass(self):
        support = runner.SystemdManager().support()
        if not support["supported"]:
            self.skipTest("UNSUPPORTED real systemd/cgroup integration: " + "; ".join(support["reasons"]))
        self.fail("A real admitted manager fixture must be supplied before deployment acceptance")


if __name__ == "__main__": unittest.main()
