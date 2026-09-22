"""Trusted DI simulations are distinguished from real cgroup integration."""
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


class RunnerTests(unittest.TestCase):
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
            def guard(identity, launch):
                launch()
                delivered.set()
                raise runner.RunnerError("UNSUPPORTED", "fixture failure after manager delivery")
            manager.set_start_guard(guard)
            supervisor = runner.Runner(manager)
            with patch.object(runner.subprocess, "Popen", return_value=object()) as launch:
                handle = supervisor.start("job", "post-delivery-business", {"execution": execution, "phase": "business"})
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
                return {**runner._unknown(), "state": "EXITED" if handle["stop_requested"] else "RUNNING",
                        "tree_exited": handle["stop_requested"], "future_start_blocked": handle["stop_requested"]}
            def stop(self, handle): handle["stop_requested"] = True
        with tempfile.TemporaryDirectory() as directory:
            roots = {name: str(Path(directory) / name) for name in ("work", "temporary", "evidence")}
            limits = {"wall_seconds": 30, "terminate_grace_seconds": 2, "cpu_seconds": 30,
                "memory_bytes": 1024**2, "processes": 8, "temporary_bytes": 1024**2,
                "nas_bytes": 0, "log_bytes": 1024, "reservation_bytes": 4 * 1024**2}
            execution = {"roots": roots, "budgets": limits, "python": sys.executable,
                "writable": list(roots.values()), "readonly": [], "environment": {"PATH": "/usr/bin:/bin"}}
            manager = DeliveredManager({"slice": "fixture.slice", "cgroup": "/sys/fs/cgroup/fixture"})
            def uncertain_receipt(identity, launch):
                launch()
                raise runner.RunnerError("IO_UNCERTAIN", "receipt failed after manager delivery")
            manager.set_start_guard(uncertain_receipt)
            supervisor = runner.Runner(manager)
            with patch.object(runner.subprocess, "Popen", return_value=Receipt()) as launch:
                handle = supervisor.start("job", "delivered-no-receipt-business", {"execution": execution, "phase": "business"})
                await_state(supervisor, handle, "RUNNING")
                supervisor.stop(handle)
                proof = await_state(supervisor, handle, "EXITED")
                self.assertTrue(proof["future_start_blocked"])
                self.assertEqual(proof["recovery_handle"]["execution_id"], handle["execution_id"])
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

    def test_bootstrap_gap_blocks_even_an_otherwise_supported_host(self):
        manager = runner.SystemdManager({"uid": 1000, "slice": "admitted.slice",
            "cgroup": "/sys/fs/cgroup/admitted.slice"})
        with patch.object(runner.sys, "platform", "linux"), patch.object(os, "geteuid", return_value=1000), \
                patch.object(Path, "read_text", return_value="systemd\n"), \
                patch.object(Path, "is_file", return_value=True), patch.object(os, "access", return_value=True):
            support = manager.support()
        self.assertFalse(support["supported"])
        self.assertEqual(support["status"], "UNSUPPORTED")
        self.assertEqual(support["reasons"], ["SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED"])

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

    def test_reconcile_missing_original_root_never_proves_effects_checked(self):
        import json
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            roots = {name: str(root / name) for name in ("work", "temporary", "evidence")}
            for path in roots.values(): Path(path).mkdir()
            plan = {"phase": "reconcile", "execution_id": "missing-root-reconcile",
                    "kind": "ledger.test.source", "roots": roots,
                    "observed_roots": {"work": str(root / "missing-original")},
                    "environment": runner.ledger_jobs.clean_environment(roots["temporary"]),
                    "parent_mount_namespace": "original-namespace",
                    "result_path": str(root / "evidence" / "result.json")}
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
        import subprocess
        class AdmittedManagerProbe(runner.SystemdManager):
            def support(self): return {"supported": True}
            def _command(self, *args, **kwargs):
                return subprocess.CompletedProcess([], 0, b"/fixture\n")
        manager = AdmittedManagerProbe({"slice": "fixture.slice", "cgroup": "/sys/fs/cgroup/fixture", "uid": 1000})
        execution = {"storage": {"archive_root": "/synthetic/archive", "stable_mount_binding": {
            "source": "synthetic-nas", "root": "/synthetic", "type": "nfs", "device": 123, "inode": 456}}}
        with patch.object(Path, "resolve", lambda path: path), patch.object(os, "access", return_value=True):
            with self.assertRaisesRegex(runner.RunnerError, "network archive hard quota adapter is not implemented"):
                manager._admit({"execution": execution})

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
                        self.assertEqual(proof["facts"], {})
                        self.assertEqual(proof["result"], {"outcome": "UNKNOWN"})
                        self.assertTrue(proof["missing"])
                path.write_text(json.dumps(dict(foreign, execution_id="execution-fixture")))
                self.assertTrue(manager.inspect(handle)["effects_checked"])

    def test_manager_capture_enforces_limit_while_reading(self):
        import subprocess
        actual = subprocess.Popen
        def noisy(*args, **kwargs):
            return actual([sys.executable, "-I", "-c", "import os;os.write(1,b'x'*(2*1024*1024))"], **kwargs)
        with patch.object(subprocess, "Popen", side_effect=noisy):
            with self.assertRaisesRegex(runner.RunnerError, "manager output exceeds bound"):
                runner.SystemdManager()._command("list-units", "lhj-*.service")

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
                identity = {"job_key": "job-fixture", "execution_id": "guard-fixture", "phase": "business",
                            "unit": "lhj-guard-fixture.service"}
                cancel = threading.Event()
                in_fence = [False]
                guard_calls = []
                if mode != "missing":
                    def guard(execution_id, launch):
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
                    self.assertTrue(in_fence[0])
                    self.assertIn("--unit=lhj-guard-fixture.service", args[0])
                    return receipt
                with patch.object(runner.subprocess, "Popen", side_effect=delivered) as launch:
                    if mode == "missing":
                        with self.assertRaisesRegex(runner.RunnerError, "startup guard is not bound"):
                            manager.start(identity, {"execution": execution, "phase": "business"}, cancel)
                        launch.assert_not_called()
                    else:
                        handle = manager.start(identity, {"execution": execution, "phase": "business"}, cancel)
                        self.assertEqual(guard_calls, ["guard-fixture"])
                        if mode == "authorized":
                            launch.assert_called_once()
                            self.assertIs(handle["launch"], receipt)
                            self.assertFalse(handle["cancel_before_launch"])
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
