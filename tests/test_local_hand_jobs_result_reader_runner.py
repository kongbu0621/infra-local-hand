"""Reader-unit lifecycle simulations with real anonymous pipes and file parsing.

The OS manager and isolation facts are controlled fixtures, not real E3 proof.
"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from local_hand_jobs import budget, result_reader, runner
from test_local_hand_jobs_bootstrap import Receipt, admitted_plan, prepared_proof


class PipeProcess:
    """A live systemd-run client, independently of the simulated service state."""
    def __init__(self):
        read, self.write_fd = os.pipe()
        self.stdout = os.fdopen(read, "rb", buffering=0)
        self.returncode = None
        self.kills = 0

    def poll(self): return self.returncode

    def kill(self):
        self.kills += 1
        self.returncode = -9

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("synthetic pipe client", timeout)
        return self.returncode

    def send(self, data):
        assert len(data) <= 4096, "large-frame tests must use bounded synthetic reads"
        assert os.write(self.write_fd, data) == len(data)

    def close(self):
        if not self.stdout.closed:
            self.stdout.close()
        if self.write_fd is not None:
            os.close(self.write_fd)
            self.write_fd = None


class ReaderLifecycle:
    """Shared fixture for the migrated real-result regressions below."""
    def __init__(self, manager, identity, plan, helper_exit=0, guard=None):
        self.manager, self.identity, self.plan = manager, identity, plan
        self.plan["supervision_version"] = 3
        self.cancel = threading.Event()
        self.launches, self.guards, self.clients = [], [], []
        self.helper_exit = helper_exit
        self.helper_state = "EXITED"
        self.reader_state = "RUNNING"
        self.reader_exit = 0
        self.reader_overrides = {}
        self.guard = guard
        self.actual_popen = subprocess.Popen
        manager.set_start_guard(self._guard)

    def _guard(self, execution_id, launch, **options):
        self.guards.append(options)
        if self.guard is not None:
            return self.guard(execution_id, launch, **options)
        return launch()

    def popen(self, argv, **options):
        if Path(argv[0]).name != "systemd-run":
            return self.actual_popen(argv, **options)
        self.launches.append((list(argv), options))
        if "--result-reader" in argv:
            client = PipeProcess()
            self.clients.append(client)
            self.payload = result_reader.decode_payload(argv[argv.index("--result-reader") + 1])
            return client
        return Receipt()

    def start(self):
        self.handle = self.manager.start(self.identity, self.plan, self.cancel)
        return self

    def observed_identity(self, stage):
        unit = (self.manager._bootstrap_unit(self.identity["execution_id"]) if stage == "bootstrap"
                else self.manager._result_reader_unit(self.identity["execution_id"]) if stage == "result_reader"
                else self.identity["unit"])
        return {"boot_id": self.plan["budget_grant"]["boot_id"],
                "invocation_id": {"bootstrap": "a", "helper": "b", "result_reader": "c"}[stage] * 32,
                "cgroup": "/fixture/" + unit}

    def observe(self, part):
        stage = part["stage"]
        if stage == "bootstrap":
            return {**prepared_proof(self.handle), "identity": self.observed_identity(stage)}
        state = self.helper_state if stage == "helper" else self.reader_state
        proof = {**runner._unknown(), "state": state, "execution_id": self.identity["execution_id"],
                 "unit": part["unit"], "identity": self.observed_identity(stage),
                 "exit_code": self.helper_exit if stage == "helper" else self.reader_exit}
        if state == "EXITED":
            proof.update(future_start_blocked=True, tree_exited=True, collectors_stopped=True, writers_stopped=True)
        if stage == "result_reader":
            proof.update(self.reader_overrides)
        return proof

    def inspect(self):
        with patch.object(self.manager, "_inspect_unit", side_effect=self.observe):
            return self.manager.inspect(self.handle)

    def value(self, **changes):
        return {"execution_id": self.identity["execution_id"], "phase": self.plan["phase"],
                "outcome": "SUCCEEDED", "effects_checked": True, "facts": {"elapsed_seconds": 1.25},
                "helper_started": True, **changes}

    def wire(self, value=None):
        ready = {"version": 1, "type": "READY", "execution_id": self.identity["execution_id"],
                 "phase": self.plan["phase"], "reader_identity": {"unit": self.payload["unit"],
                 **self.observed_identity("result_reader")}, "helper_identity": self.payload["helper_identity"]}
        return result_reader._frame_bytes(ready) + result_reader._frame_bytes({**ready, "type": "RESULT",
                "result": self.value() if value is None else value})

    def read_existing_file(self):
        """Run the actual child reader; only namespace/cgroup facts are simulated."""
        client = self.clients[-1]
        with os.fdopen(os.dup(client.write_fd), "wb", buffering=0) as output, \
                patch.object(result_reader.sys, "stdout", SimpleNamespace(buffer=output)), \
                patch.object(os, "readlink", return_value="synthetic-child-namespace"), \
                patch.object(os, "access", return_value=False), \
                patch.object(runner, "_mount_for", return_value={"options": "ro"}), \
                patch.object(runner, "_verify_cgroup_limits", return_value={"cgroup": self.observed_identity("result_reader")["cgroup"]}), \
                patch.dict(os.environ, {"INVOCATION_ID": self.observed_identity("result_reader")["invocation_id"]}):
            try:
                self.reader_exit = result_reader.run(self.payload)
            except runner.JobError:
                self.reader_exit = 1
        self.reader_state = "EXITED"
        return self.inspect()


@contextlib.contextmanager
def reader_lifecycle(*, phase="preflight", helper_exit=0, guard=None):
    with admitted_plan(phase=phase) as (manager, identity, plan):
        fixture = ReaderLifecycle(manager, identity, plan, helper_exit=helper_exit, guard=guard)
        with patch.object(runner.subprocess, "Popen", side_effect=fixture.popen):
            try:
                yield fixture.start()
            finally:
                for client in fixture.clients:
                    client.close()


class ResultReaderRunnerTests(unittest.TestCase):
    def test_cancel_stops_original_reader_unit_while_pipe_client_is_alive(self):
        with reader_lifecycle() as flow:
            flow.inspect()
            client = flow.clients[0]
            reader = flow.handle["result_reader"]
            self.assertIsNone(client.poll())
            stops = []
            def command(*args, **kwargs):
                if args[0] == "stop":
                    stops.append(args[-1])
                    return subprocess.CompletedProcess(args, 0, b"")
                unit = args[1]
                stage = next(name for name in ("bootstrap", "helper", "result_reader") if flow.handle[name]["unit"] == unit)
                observed = flow.observed_identity(stage)
                raw = (observed["invocation_id"] + "\n" if "--value" in args else
                       "InvocationID=" + observed["invocation_id"] + "\nControlGroup=" + observed["cgroup"] + "\n")
                return subprocess.CompletedProcess(args, 0, raw.encode())
            with patch.object(flow.manager, "_command", side_effect=command):
                proof = flow.manager.stop(flow.handle)
            self.assertIn(reader["unit"], stops)
            self.assertEqual(set(stops), {flow.handle[name]["unit"] for name in ("bootstrap", "helper", "result_reader")})
            self.assertTrue(reader["stop_acked"])
            self.assertFalse(proof["tree_exited"])
            self.assertIsNone(client.poll())
            self.assertEqual(client.kills, 0)

    def test_complete_result_cannot_override_unknown_reader_manager_or_tree_proof(self):
        cases = [{"state": "UNKNOWN"}, {"tree_exited": False}, {"future_start_blocked": False},
                 {"collectors_stopped": False}, {"writers_stopped": False}]
        for missing in cases:
            with self.subTest(missing=missing), reader_lifecycle() as flow:
                flow.inspect()
                flow.clients[0].send(flow.wire())
                flow.reader_state = "EXITED"
                flow.reader_overrides = missing
                proof = flow.inspect()
                self.assertIsNone(flow.handle["result_reader"]["reader"].result)
                self.assertFalse(proof.get("helper_result_verified", False))
                self.assertNotEqual(proof.get("result", {}).get("outcome"), "SUCCEEDED")
                self.assertEqual(flow.clients[0].kills, 0)

    def test_recovery_observes_and_stops_three_identities_despite_first_failure(self):
        with admitted_plan() as (manager, identity, plan):
            plan["supervision_version"] = 3
            with patch.object(runner.subprocess, "Popen", side_effect=AssertionError("recovery start")), \
                    patch.object(result_reader, "_read_result", side_effect=AssertionError("recovery storage read")):
                handle = manager.reattach(identity, plan, threading.Event())
                observed, stopped = [], []
                def observe(part):
                    observed.append(part["stage"])
                    if part["stage"] == "bootstrap":
                        raise runner.RunnerError("IO_UNCERTAIN", "first observation failed")
                    return runner._unknown()
                def stop(part):
                    stopped.append(part["stage"])
                    if part["stage"] == "bootstrap":
                        raise runner.RunnerError("IO_UNCERTAIN", "first stop failed")
                    return runner._unknown()
                with patch.object(manager, "_inspect_unit", side_effect=observe):
                    proof = manager.inspect(handle)
                with patch.object(manager, "_stop_unit", side_effect=stop):
                    with self.assertRaisesRegex(runner.RunnerError, "first stop failed"):
                        manager.stop(handle)
            self.assertEqual(observed, ["bootstrap", "helper", "result_reader"])
            self.assertEqual(stopped, observed)
            self.assertEqual(proof["state"], "UNKNOWN")

    def test_lost_delivery_receipt_recovery_never_redelivers_or_rereads_result(self):
        def lost_receipt(execution_id, launch, **options):
            result = launch()
            if options["stage"] == "result_reader":
                raise OSError("receipt lost after delivery")
            return result
        with reader_lifecycle(guard=lost_receipt) as flow:
            with self.assertRaisesRegex(runner.RunnerError, "acknowledgement missing"):
                flow.inspect()
            original_units = [flow.handle[name]["unit"] for name in ("bootstrap", "helper", "result_reader")]
            for saved in (flow.identity, flow.manager.export_handle(flow.handle)):
                with self.subTest(saved_receipt="manager" in saved), \
                        patch.object(runner.subprocess, "Popen", side_effect=AssertionError("recovery launch")), \
                        patch.object(result_reader, "_read_result", side_effect=AssertionError("recovery result read")):
                    restored = flow.manager.reattach(saved, flow.plan, threading.Event())
                    seen = []
                    def observe(part):
                        seen.append(part["unit"])
                        result = flow.observe(part)
                        if part["stage"] == "result_reader":
                            result.update(state="EXITED", future_start_blocked=True, tree_exited=True,
                                          collectors_stopped=True, writers_stopped=True)
                        return result
                    with patch.object(flow.manager, "_inspect_unit", side_effect=observe):
                        proof = flow.manager.inspect(restored)
                    self.assertEqual(seen, original_units)
                    self.assertEqual(proof["state"], "EXITED")
                    self.assertTrue(proof["tree_exited"])
                    self.assertTrue(proof["future_start_blocked"])
                    self.assertFalse(proof["collectors_stopped"])
                    self.assertFalse(proof["effects_checked"])
                    self.assertEqual([restored[name]["unit"] for name in ("bootstrap", "helper", "result_reader")], original_units)
            self.assertEqual(len(flow.launches), 3)

    def test_reader_guard_refusal_or_precancel_cannot_promote_helper_exit_zero(self):
        for mode in ("refused", "cancelled"):
            def guard(execution_id, launch, **options):
                return None if options["stage"] == "result_reader" else launch()
            with self.subTest(mode=mode), reader_lifecycle(guard=guard if mode == "refused" else None) as flow:
                flow.helper_state = "RUNNING"
                flow.inspect()
                flow.helper_state = "EXITED"
                if mode == "cancelled":
                    flow.cancel.set()
                first, second = flow.inspect(), flow.inspect()
                self.assertEqual(first["exit_code"], 0)
                self.assertFalse(first["effects_checked"])
                self.assertFalse(first["helper_result_verified"])
                self.assertEqual(first["result"]["outcome"], "UNKNOWN")
                self.assertEqual(first, second)
                self.assertEqual(len(flow.launches), 2)

    def test_reader_keeps_original_deadline_and_exhaustion_never_gets_fresh_start(self):
        with reader_lifecycle() as flow:
            flow.helper_state = "RUNNING"
            flow.inspect()
            original = flow.handle["execution"]["phase_deadline_boottime_ns"]
            clock = budget.current_clock()
            clock["boottime_ns"] = original
            flow.helper_state = "EXITED"
            with patch.object(budget, "current_clock", return_value=clock):
                first, second = flow.inspect(), flow.inspect()
            self.assertEqual(flow.handle["bootstrap"]["phase_deadline_boottime_ns"], original)
            self.assertEqual(flow.handle["helper"]["phase_deadline_boottime_ns"], original)
            self.assertEqual(flow.handle["result_reader"]["phase_deadline_boottime_ns"], original)
            self.assertEqual(len(flow.launches), 2)
            self.assertFalse(first["helper_result_verified"])
            self.assertFalse(second["effects_checked"])
            self.assertTrue(flow.handle["reader_attempted"])

    def test_live_empty_and_fragmented_pipe_is_nonblocking_and_waits_for_unit_exit(self):
        with reader_lifecycle() as flow:
            flow.inspect()
            client = flow.clients[0]
            self.assertFalse(os.get_blocking(client.stdout.fileno()))
            raw = flow.wire()
            before = time.monotonic()
            self.assertEqual(flow.inspect()["state"], "RUNNING")
            self.assertLess(time.monotonic() - before, .5)
            for block in (raw[:3], raw[3:51], raw[51:]):
                client.send(block)
                self.assertEqual(flow.inspect()["state"], "RUNNING")
                self.assertIsNone(flow.handle["result_reader"]["reader"].result)
            flow.reader_state = "EXITED"
            proof = flow.inspect()
            self.assertTrue(proof["helper_result_verified"])
            self.assertEqual(proof["result"], flow.value())
            self.assertEqual(client.kills, 1)

    def test_large_valid_frame_is_drained_in_bounded_ticks(self):
        with reader_lifecycle() as flow:
            flow.inspect()
            value = flow.value(facts={"large": "x" * 140000})
            pending = bytearray(flow.wire(value))
            original_read = os.read
            reads = []
            def read(descriptor, maximum):
                if descriptor != flow.clients[0].stdout.fileno():
                    return original_read(descriptor, maximum)
                data = bytes(pending[:maximum]); del pending[:maximum]
                reads.append(len(data))
                return data
            with patch.object(os, "read", side_effect=read):
                flow.inspect()
                self.assertEqual(sum(reads), 65536)
                self.assertTrue(pending)
                flow.inspect(); flow.inspect()
                self.assertFalse(pending)
                self.assertIsNone(flow.handle["result_reader"]["reader"].result)
                flow.reader_state = "EXITED"
                proof = flow.inspect()
            self.assertEqual(proof["result"], value)
            self.assertTrue(proof["helper_result_verified"])

    def test_nonblocking_setup_failure_never_reads_possibly_blocking_pipe(self):
        with reader_lifecycle() as flow:
            with patch.object(os, "set_blocking", side_effect=OSError("nonblocking setup failed")):
                with self.assertRaises(runner.RunnerError):
                    flow.inspect()
            reader = flow.handle["result_reader"]
            self.assertTrue(reader["delivery_attempted"])
            with patch.object(os, "read", side_effect=AssertionError("blocking result pipe read")), \
                    patch.object(flow.manager, "_stop_unit", return_value=runner._unknown()) as stop:
                proof = flow.inspect()
            self.assertFalse(proof.get("helper_result_verified", False))
            self.assertTrue(any(call.args[0] is reader for call in stop.call_args_list))

    def test_reader_collector_is_cleaned_even_when_prior_unit_observation_fails(self):
        for failed_stage in ("bootstrap", "helper"):
            with self.subTest(failed_stage=failed_stage), reader_lifecycle() as flow:
                flow.inspect()
                flow.clients[0].send(flow.wire())
                flow.reader_state = "EXITED"
                observed = []
                def observe(part):
                    observed.append(part["stage"])
                    if part["stage"] == failed_stage:
                        raise runner.RunnerError("IO_UNCERTAIN", "original unit observation failed")
                    return flow.observe(part)
                with patch.object(flow.manager, "_inspect_unit", side_effect=observe):
                    proof = flow.manager.inspect(flow.handle)
                self.assertEqual(observed, ["bootstrap", "helper", "result_reader"])
                self.assertEqual(proof["state"], "UNKNOWN")
                self.assertFalse(proof.get("helper_result_verified", False))
                self.assertEqual(flow.clients[0].kills, 1)
                self.assertTrue(flow.clients[0].stdout.closed)

    def test_recovered_reader_transport_loss_allows_explicit_new_reconcile_without_success(self):
        import copy
        import hashlib
        import uuid
        from test_local_hand_jobs_result_reader_broker import ResultReaderBrokerTests, deliver_reader
        fixture = ResultReaderBrokerTests()
        self.addCleanup(fixture.doCleanups)
        case = fixture.fixture()
        execution_id = fixture.ready_reader(case)
        self.assertIsNotNone(deliver_reader(case, execution_id))
        original = copy.deepcopy(case.row()["record"])
        plan = case.runner.starts[-1][2]
        manager = runner.SystemdManager({"cgroup": "/sys/fs/cgroup/fixture"})
        identity = {"execution_id": execution_id, "job_key": case.f.request["operation_id"],
                    "phase": "preflight", "supervision_version": 3,
                    "unit": "lhj-" + hashlib.sha256(execution_id.encode()).hexdigest() + ".service"}
        observed = []
        def observe(part):
            observed.append(part["stage"])
            return {**runner._unknown(), "state": "EXITED", "future_start_blocked": True,
                    "tree_exited": True, "collectors_stopped": True, "writers_stopped": True,
                    "execution_id": execution_id, "unit": part["unit"], "exit_code": 0,
                    "identity": {"boot_id": plan["budget_grant"]["boot_id"],
                        "invocation_id": "a" * 32, "cgroup": "/fixture/" + part["unit"]}}
        with patch.object(manager, "support", return_value={"supported": True}), \
                patch.object(manager, "_inspect_unit", side_effect=observe), \
                patch.object(runner.subprocess, "Popen", side_effect=AssertionError("old phase redelivered")), \
                patch.object(result_reader, "_read_result", side_effect=AssertionError("old result reread")):
            recovered = manager.reattach(identity, plan, threading.Event())
            proof = manager.inspect(recovered)
        self.assertEqual(observed, ["bootstrap", "helper", "result_reader"])
        self.assertEqual(proof["state"], "EXITED")
        self.assertTrue(proof["tree_exited"])
        self.assertTrue(proof["future_start_blocked"])
        self.assertFalse(proof["collectors_stopped"])
        self.assertFalse(proof["effects_checked"])
        self.assertFalse(proof["helper_result_verified"])
        self.assertEqual(proof["result"]["outcome"], "UNKNOWN")
        # Feed the actual manager observation through real Broker._complete and
        # its durable status before authorizing a distinct reconciliation round.
        case.runner.proofs[execution_id] = proof
        case.broker.tick()
        case.broker.tick()
        saved = case.row()["record"]
        self.assertEqual(saved["outcome"], "UNKNOWN")
        self.assertEqual(saved["lifecycle"], "RECONCILE_REQUIRED")
        self.assertEqual(saved["exit_proof"], proof)
        self.assertEqual(saved["bootstrap_grants"], original["bootstrap_grants"])
        self.assertEqual(saved["execution_budget"], original["execution_budget"])
        self.assertNotIn("business", saved["handles"])
        self.assertEqual(len(case.runner.starts), 1)
        round_id = str(uuid.uuid4())
        case.f.reconcile(round_id)
        case.broker.tick()
        self.assertEqual(len(case.runner.starts), 2)
        self.assertEqual(case.runner.starts[-1][2]["phase"], "reconcile")
        self.assertNotEqual(case.runner.starts[-1][1], execution_id)
        self.assertEqual(case.row()["record"]["outcome"], "UNKNOWN")
        self.assertFalse(case.row()["record"].get("seals"))
        fixture.assert_code("RESOURCE_BUSY", lambda: case.broker.call(
            "lh_job_submit", case.f.make_request(), case.f.owner))

    def test_legacy_and_version_two_exit_observation_never_reads_result_storage(self):
        with admitted_plan() as (manager, identity, plan):
            manager.set_start_guard(lambda execution_id, launch, **options: launch())
            with patch.object(runner.subprocess, "Popen", return_value=Receipt()):
                handle = manager.start(identity, plan, threading.Event())
                with patch.object(manager, "_inspect_unit", side_effect=lambda part: prepared_proof(handle)
                                  if part["stage"] == "bootstrap" else runner._unknown()):
                    manager.inspect(handle)
            helper = handle["helper"]
            actual_inspect_unit = manager._inspect_unit
            fields = {"LoadState": "loaded", "ActiveState": "active", "SubState": "exited",
                      "ControlGroup": "/fixture/" + helper["unit"], "InvocationID": "b" * 32,
                      "Job": "0", "ExecMainCode": "1", "ExecMainStatus": "0", "Result": "success"}
            def read(path, *args, **kwargs):
                if str(path) == "/proc/sys/kernel/random/boot_id": return helper["boot_id"]
                if str(path).endswith("/cgroup.events"): return "populated 0\n"
                raise AssertionError("legacy observer read job storage")
            with patch.object(Path, "read_text", read), \
                    patch.object(runner.ledger_jobs, "bounded_regular_bytes", side_effect=AssertionError("legacy result read")), \
                    patch.object(result_reader, "_read_result", side_effect=AssertionError("legacy result reader")), \
                    patch.object(manager, "_command", return_value=subprocess.CompletedProcess([], 0,
                        "\n".join(key + "=" + value for key, value in fields.items()).encode())):
                for version in (None, 2):
                    with self.subTest(version=version):
                        legacy = dict(helper)
                        if version is None:
                            legacy.pop("stage")
                            proof = manager.inspect(legacy)
                        else:
                            with patch.object(manager, "_inspect_unit", side_effect=lambda part:
                                    prepared_proof(handle) if part["stage"] == "bootstrap" else actual_inspect_unit(part)):
                                proof = manager.inspect(handle)
                        self.assertTrue(proof["tree_exited"])
                        self.assertFalse(proof["helper_result_verified"])
                        self.assertFalse(proof["effects_checked"])
