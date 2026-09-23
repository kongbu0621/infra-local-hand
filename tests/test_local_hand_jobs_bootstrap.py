"""Fixed bootstrap lifecycle simulations; no real cgroup claim is made here."""
from __future__ import annotations

import contextlib
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from local_hand_jobs import bootstrap, budget, runner
from test_local_hand_jobs_runner import admitted_bootstrap_plan, budgeted_plan


class Receipt:
    returncode = 0
    def poll(self): return self.returncode


@contextlib.contextmanager
def admitted_plan(operation_id="fixture", phase="preflight"):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        roots = {name: str(root / name) for name in ("work", "temporary", "evidence")}
        execution = {"kind": "host.inspect", "roots": roots, "budgets": {}, "python": sys.executable,
                     "writable": list(roots.values()), "readonly": [], "storage": {},
                     "environment": runner.ledger_jobs.clean_environment(roots["temporary"])}
        plan = budgeted_plan({"execution": execution, "phase": phase}, operation_id=operation_id)
        with admitted_bootstrap_plan(plan, folder):
            identity = {"job_key": plan["budget_grant"]["operation_id"], "execution_id": plan["execution_id"],
                "phase": plan["phase"], "unit": "lhj-" + runner.hashlib.sha256(plan["execution_id"].encode()).hexdigest() + ".service"}
            manager = runner.SystemdManager({"slice": "fixture.slice", "cgroup": "/sys/fs/cgroup/fixture"})
            with patch.object(manager, "support", return_value={"supported": True}):
                yield manager, identity, plan


def prepared_proof(handle):
    return {"state": "EXITED", "execution_id": handle["identity"]["execution_id"],
        "unit": handle["bootstrap"]["unit"], "future_start_blocked": True, "tree_exited": True,
        "collectors_stopped": True, "writers_stopped": True, "effects_checked": True, "exit_code": 0,
        "facts": {}, "result": {"outcome": "SUCCEEDED", "bootstrap_prepared": True,
                                "business_started": False, "helper_started": True}, "missing": []}


class BootstrapLifecycleTests(unittest.TestCase):
    def test_first_delivery_does_not_read_or_create_job_roots_or_plan(self):
        with admitted_plan() as (manager, identity, plan):
            deliveries = []
            def guard(execution_id, launch, **options):
                deliveries.append((execution_id, options))
                return launch()
            manager.set_start_guard(guard)
            with patch.object(Path, "mkdir", side_effect=AssertionError("broker mkdir")), \
                    patch.object(Path, "open", side_effect=AssertionError("broker plan I/O")), \
                    patch.object(Path, "resolve", side_effect=AssertionError("broker root resolve")), \
                    patch.object(runner, "_verify_project_quota", side_effect=AssertionError("broker quota I/O")), \
                    patch.object(runner.subprocess, "Popen", return_value=Receipt()) as launch:
                handle = manager.start(identity, plan, threading.Event())
            self.assertEqual(deliveries, [(identity["execution_id"], {"stage": "bootstrap"})])
            command = launch.call_args.args[0]
            self.assertIn("--unit=" + manager._bootstrap_unit(identity["execution_id"]), command)
            payload = bootstrap.decode_payload(command[command.index("--bootstrap") + 1])
            self.assertEqual(payload["allocation"], plan["bootstrap_allocation"])
            self.assertEqual(set(payload["execution"]["writable"]), set(plan["bootstrap_allocation"]["paths"]))
            self.assertIsNone(handle["helper"])
            for path in plan["bootstrap_allocation"]["roots"].values():
                self.assertEqual(list(Path(path).iterdir()), [])

    def test_bootstrap_exit_proof_does_not_read_a_plan_or_report(self):
        with admitted_plan() as (manager, identity, plan):
            manager.set_start_guard(lambda execution_id, launch, **options: launch())
            with patch.object(runner.subprocess, "Popen", return_value=Receipt()):
                handle = manager.start(identity, plan, threading.Event())
            part = handle["bootstrap"]
            fields = {"LoadState": "loaded", "ActiveState": "active", "SubState": "exited",
                      "ControlGroup": "/fixture/" + part["unit"], "InvocationID": "1" * 32,
                      "Job": "0", "ExecMainCode": "1", "ExecMainStatus": "0", "Result": "success"}
            def read(path, *args, **kwargs):
                if str(path) == "/proc/sys/kernel/random/boot_id": return part["boot_id"]
                if str(path).endswith("/cgroup.events"): return "populated 0\n"
                raise AssertionError("Unexpected filesystem observation: " + str(path))
            with patch.object(manager, "_command", return_value=subprocess.CompletedProcess([], 0,
                    "\n".join(key + "=" + value for key, value in fields.items()).encode())), \
                    patch.object(Path, "read_text", read), \
                    patch.object(runner.ledger_jobs, "bounded_regular_bytes", side_effect=AssertionError("bootstrap report read")):
                proof = manager._inspect_unit(part)
            self.assertTrue(proof["result"]["bootstrap_prepared"])
            self.assertTrue(proof["effects_checked"])
            self.assertEqual(proof["unit"], part["unit"])

    def test_helper_delivery_requires_new_guard_after_verified_bootstrap(self):
        for mode in ("accepted", "revoked", "cancelled_at_guard"):
            with self.subTest(mode=mode), admitted_plan() as (manager, identity, plan):
                calls = []
                cancel = threading.Event()
                def guard(execution_id, launch, **options):
                    calls.append(options)
                    if options["stage"] == "helper":
                        self.assertTrue(options["bootstrap_proof"]["result"]["bootstrap_prepared"])
                        if mode == "revoked": return None
                        if mode == "cancelled_at_guard": cancel.set()
                    return launch()
                manager.set_start_guard(guard)
                with patch.object(runner.subprocess, "Popen", return_value=Receipt()) as launch:
                    handle = manager.start(identity, plan, cancel)
                    first = prepared_proof(handle)
                    def observe(part):
                        if part["stage"] == "bootstrap": return first
                        if part["cancel_before_launch"]:
                            return {**first, "result": {"outcome": "CANCELLED", "helper_started": False}}
                        return {**runner._unknown(), "state": "RUNNING"}
                    with patch.object(manager, "_inspect_unit", side_effect=observe):
                        result = manager.inspect(handle)
                        manager.inspect(handle)
                self.assertEqual([item["stage"] for item in calls], ["bootstrap", "helper"])
                self.assertEqual(launch.call_count, 2 if mode == "accepted" else 1)
                if mode == "accepted":
                    self.assertEqual(result["state"], "RUNNING")
                else:
                    self.assertTrue(result["result"]["helper_started"])
                    self.assertFalse(result["result"]["business_started"])
                    self.assertEqual(result["result"]["outcome"], "CANCELLED")

    def test_failed_bootstrap_never_delivers_helper_or_claims_clean_effects(self):
        with admitted_plan() as (manager, identity, plan):
            manager.set_start_guard(lambda execution_id, launch, **options: launch())
            with patch.object(runner.subprocess, "Popen", return_value=Receipt()) as launch:
                handle = manager.start(identity, plan, threading.Event())
                failure = prepared_proof(handle)
                failure.update(exit_code=1, effects_checked=False)
                failure["result"].update(outcome="FAILED", bootstrap_prepared=False)
                with patch.object(manager, "_inspect_unit", return_value=failure):
                    proof = manager.inspect(handle)
            self.assertEqual(launch.call_count, 1)
            self.assertIsNone(handle["helper"])
            self.assertFalse(proof["effects_checked"])
            self.assertTrue(proof["result"]["helper_started"])

    def test_prepared_but_refused_helper_is_failed_in_the_real_broker(self):
        from test_local_hand_jobs_broker import BrokerTests
        for phase in ("preflight", "business"):
            with self.subTest(phase=phase):
                fixture = BrokerTests()
                fixture.setUp()
                try:
                    fixture.submit()
                    fixture.broker.tick()
                    if phase == "business":
                        fixture.runner.finish(fixture.runner.starts[0][1])
                        fixture.broker.tick()
                        fixture.broker.tick()
                    operation = fixture.request["operation_id"]
                    self.assertEqual(fixture.db.get("job", operation)["record"]["phase"], phase.upper())
                    with admitted_plan(operation, phase) as (manager, identity, plan):
                        manager.set_start_guard(lambda execution_id, launch, **options:
                                                launch() if options["stage"] == "bootstrap" else None)
                        with patch.object(runner.subprocess, "Popen", return_value=Receipt()):
                            handle = manager.start(identity, plan, threading.Event())
                        with patch.object(manager, "_inspect_unit", return_value=prepared_proof(handle)):
                            proof = manager.inspect(handle)
                    self.assertEqual(proof["exit_code"], 1)
                    self.assertEqual(proof["bootstrap_exit_proof"]["exit_code"], 0)
                    fixture.broker._complete("job", operation, proof)
                    record = fixture.db.get("job", operation)["record"]
                    self.assertEqual(record["outcome"], "FAILED")
                    self.assertEqual(record["phase"], "EXITED")
                    self.assertTrue(record["helper_started"])
                    self.assertFalse(record["business_started"])
                finally:
                    fixture.doCleanups()

    def test_expired_original_phase_cannot_gain_time_from_bootstrap_completion(self):
        with admitted_plan() as (manager, identity, plan):
            clock = budget.current_clock()
            manager.set_start_guard(lambda execution_id, launch, **options: launch())
            with patch.object(runner.subprocess, "Popen", return_value=Receipt()) as launch, \
                    patch.object(budget, "current_clock", side_effect=lambda: dict(clock)):
                handle = manager.start(identity, plan, threading.Event())
                clock["boottime_ns"] = budget.phase_deadline_ns(plan["budget_grant"])
                with patch.object(manager, "_inspect_unit", return_value=prepared_proof(handle)):
                    first = manager.inspect(handle)
                    second = manager.inspect(handle)
            self.assertEqual(launch.call_count, 1)
            self.assertEqual(first, second)
            self.assertEqual(first["result"]["error"], "LIMIT_EXCEEDED")
            self.assertTrue(first["result"]["helper_started"])
            self.assertFalse(first["result"]["business_started"])

    def test_receipt_lost_recovery_observes_and_stops_both_original_units(self):
        for corrupted_budget in (False, True):
            with self.subTest(corrupted_budget=corrupted_budget), admitted_plan() as (manager, identity, plan):
                restored_plan = copy.deepcopy(plan)
                if corrupted_budget:
                    restored_plan["budget_grant"]["deadline_boottime_ns"] = "broken"
                with patch.object(runner.subprocess, "Popen", side_effect=AssertionError("recovery launch")):
                    handle = manager.reattach(identity, restored_plan, threading.Event())
                    with patch.object(manager, "_inspect_unit", side_effect=lambda part: (
                            prepared_proof(handle) if part["stage"] == "bootstrap" else runner._unknown("helper delivery uncertain"))):
                        proof = manager.inspect(handle)
                    with patch.object(manager, "_stop_unit", return_value=runner._unknown()) as stopped:
                        manager.stop(handle)
                self.assertEqual(proof["state"], "UNKNOWN")
                self.assertEqual([call.args[0]["unit"] for call in stopped.call_args_list],
                                 [manager._bootstrap_unit(identity["execution_id"]), identity["unit"]])
                self.assertIs(handle["helper"]["budget_grant"] is None, corrupted_budget)
                self.assertTrue(handle["recovered"])

    def test_valid_saved_receipt_is_bound_to_allocation_and_has_no_resume_path(self):
        with admitted_plan() as (manager, identity, plan):
            manager.set_start_guard(lambda execution_id, launch, **options: launch())
            with patch.object(runner.subprocess, "Popen", return_value=Receipt()):
                handle = manager.start(identity, plan, threading.Event())
            saved = manager.export_handle(handle)
            saved["manager"]["allocation_digest"] = "0" * 64
            with self.assertRaisesRegex(runner.RunnerError, "allocation differs"):
                manager.reattach(saved, plan, threading.Event())

    def test_recovery_does_not_need_transient_evidence_launch_inputs(self):
        with admitted_plan(phase="evidence") as (manager, identity, plan):
            self.assertNotIn("evidence_snapshot", plan)
            self.assertNotIn("evidence_store_root", plan)
            with patch.object(manager, "_admit", side_effect=AssertionError("recovery cannot readmit execution")), \
                    patch.object(runner.subprocess, "Popen", side_effect=AssertionError("recovery cannot launch")):
                handle = manager.reattach(identity, plan, threading.Event())
                with patch.object(manager, "_stop_unit", return_value=runner._unknown()) as stopped:
                    manager.stop(handle)
            self.assertEqual(stopped.call_count, 2)

    def test_one_stage_observation_or_stop_failure_does_not_starve_the_other(self):
        with admitted_plan() as (manager, identity, plan):
            handle = manager.reattach(identity, plan, threading.Event())
            inspected, stopped = [], []
            def observe(part):
                inspected.append(part["stage"])
                if part["stage"] == "bootstrap":
                    raise runner.RunnerError("IO_UNCERTAIN", "bootstrap manager query failed")
                return runner._unknown("helper stopping observed")
            def stop(part):
                stopped.append(part["stage"])
                if part["stage"] == "bootstrap":
                    raise runner.RunnerError("IO_UNCERTAIN", "bootstrap stop query failed")
                return runner._unknown("helper stop issued")
            with patch.object(manager, "_inspect_unit", side_effect=observe):
                result = manager.inspect(handle)
            with patch.object(manager, "_stop_unit", side_effect=stop):
                with self.assertRaisesRegex(runner.RunnerError, "bootstrap stop query failed"):
                    manager.stop(handle)
            self.assertEqual(inspected, ["bootstrap", "helper"])
            self.assertEqual(stopped, ["bootstrap", "helper"])
            self.assertEqual(result["state"], "UNKNOWN")

    def test_transport_is_bounded_canonical_and_excludes_credentials(self):
        for payload in ({"token": "never transported"}, {"env": {"SSH_AUTH_SOCK": "/private"}},
                        {"value": "x" * bootstrap.MAX_PAYLOAD_BYTES}):
            with self.subTest(keys=list(payload)), self.assertRaises(runner.JobError):
                bootstrap.encode_payload(payload)
        for encoded in ("not base64", "e30=\n", "eyJhIjoxLCJhIjoyfQ=="):
            with self.subTest(encoded=encoded), self.assertRaises(runner.JobError):
                bootstrap.decode_payload(encoded)
        payload = {"execution": {"environment": {"PATH": "/usr/bin:/bin"}}, "allocation": {}}
        self.assertEqual(bootstrap.decode_payload(bootstrap.encode_payload(payload)), payload)
        with patch.object(os, "sysconf", side_effect=lambda key: 4096 if key == "SC_PAGE_SIZE" else 4096):
            with self.assertRaises(runner.JobError):
                bootstrap.check_argv(["/usr/bin/fixed", "x" * 3000], {})
        with patch.object(os, "sysconf", side_effect=lambda key: 4096 if key == "SC_PAGE_SIZE" else 2**22):
            with self.assertRaises(runner.JobError):
                bootstrap.check_argv(["/usr/bin/fixed", "x" * (4096 * 32)], {})


if __name__ == "__main__":
    unittest.main()
