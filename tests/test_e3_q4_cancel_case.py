"""Real Broker/SQLite cancellation; unit, transport and delivery facts are modeled.

No systemd, cgroup, host account, quota or real host acceptance occurs here.
"""
from __future__ import annotations

import copy
import contextlib
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest import mock

from e3_host import q4_cancel_case as case_module
if sys.platform.startswith("linux"):
    from local_hand_jobs.broker import Broker
    from local_hand_jobs.contract import JobError, Principal, request_digest
    from local_hand_jobs.state import StateStore
    from local_hand_jobs import budget, quota_contract, quota_lifecycle as life, runner
    from test_local_hand_jobs_broker import PolicyFixture, RegistryFixture, SupervisorFixture
else:
    SupervisorFixture = object


class Pending:
    returncode = None
    def poll(self):
        return self.returncode


class ModeledRunner(SupervisorFixture):
    def __init__(self, manager):
        super().__init__()
        self.manager, self.part = manager, None

    def set_start_guard(self, callback):
        self.manager.set_start_guard(callback)

    def stop(self, handle):
        super().stop(handle)
        self.manager.stop(self.part)
        try:
            return self.manager._inspect_unit(self.part)
        except Exception:
            return runner._unknown("modeled kernel has not proven original exit")


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux execution-core imports")
class CancelCaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = StateStore(Path(directory.name) / "state.sqlite", "authority", "ledger", initialize=True)
        self.addCleanup(self.state.close)
        self.manager = case_module.observe_manager(runner._SystemdExecutionCore)()
        self.driver = ModeledRunner(self.manager)
        self.policy = PolicyFixture()
        self.broker = Broker(self.state, self.policy, RegistryFixture(), self.driver)
        self.owner = Principal("owner", frozenset({"lh:submit", "lh:read", "lh:cancel", "lh:evidence"}))
        self.request = dict(schema_version="lh-job-v1", operation_id=str(uuid.uuid4()), kind="host.inspect",
            profile_ref="fixture", expected=self.policy.expected(None), inputs={}, expires_at=int(time.time()) + 120)
        self.request["request_digest"] = request_digest(self.request)
        self.broker.submit(self.request, self.owner)
        self.case = case_module.Case(self.broker, self.request["operation_id"], self.owner).attach(self.manager)
        self.addCleanup(self.case.close)
        self.broker.tick()  # Real durable execution intent; modeled manager delivery.
        self.case.poll()
        report = self.case.snapshot()
        execution = report["target_execution_id"]
        self.unit = "lhj-" + hashlib.sha256(execution.encode()).hexdigest() + ".service"
        self.pin = dict(path="/modeled.slice", device=4, inode=81)
        self.part = dict(stage="helper", execution_id=execution, unit=self.unit, boot_id=report["boot_id"],
            cgroup_parent="/sys/fs/cgroup/modeled.slice", quota_parent=self.pin,
            invocation_id=None, launch=Pending(), launch_acked=False, stop_requested=False, stop_acked=False,
            quota_transport=life.Transport(65536), phase_deadline_boottime_ns=report["phase_deadline_ns"],
            budget_grant=budget.stored_grant(self.state.get("job", self.request["operation_id"]), "preflight"),
            cancel_event=threading.Event(), pipe_nonblocking=True, delivery_attempted=True)
        self.driver.part = self.part
        self.values = dict.fromkeys(life.FIELDS, "")
        self.values.update(Id=self.unit, LoadState="loaded", ActiveState="active", SubState="running",
            ControlGroup=self.pin["path"] + "/" + self.unit, InvocationID="a" * 32, ExecMainCode="0",
            ExecMainStatus="0", Result="success", Restart="no", KillMode="control-group", Type="exec",
            ExitType="cgroup", RemainAfterExit="yes")
        self.calls = []
        def command(_manager, *args, **kwargs):
            self.calls.append(args)
            if args == ("stop", self.unit):
                raw = b""
            elif "--value" in args:
                raw = (self.values["InvocationID"] + "\n").encode()
            else:
                raw = "".join(key + "=" + value + "\n" for key, value in self.values.items()).encode()
            return subprocess.CompletedProcess(args, 0, raw)
        self.command = command
        self.patches = [mock.patch.object(runner._SystemdExecutionCore, "_command", command),
            mock.patch.object(self.part["quota_transport"], "pump"),
            mock.patch.object(life, "parent", return_value=(self.pin, False))]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        # Synthetic OS delivery is explicitly separate from the real cancel API.
        # Its durable event/observer records exercise the report binding only.
        with self.state.transaction() as tx:
            self.state.update(tx, "job", self.request["operation_id"], "MANAGER_DELIVERY_INTENT",
                {"delivery_intents": [execution + ":bootstrap", execution + ":helper"]})
        self.case._delivery("launch_callback_return", execution, "helper", attempted=True, returned=True)

    def trigger(self):
        result = self.manager._inspect_unit(self.part)
        self.assertEqual(result["state"], "RUNNING")
        self.case._thread.join(1)
        self.assertFalse(self.case._thread.is_alive())

    def finish_at_record_deadline(self):
        report = self.case.snapshot()
        now = dict(boot_id=report["boot_id"], boottime_ns=report["record_deadline_ns"])
        with mock.patch.object(case_module, "_clock", return_value=now):
            report = self.case.poll()
        self.assertEqual(case_module.validate_report(report), [])
        return report

    def test_real_cancel_persists_once_and_running_stop_keeps_unknown_and_lease(self):
        self.trigger()
        self.broker.tick()
        self.case.poll()
        self.manager._inspect_unit(self.part)  # A second observation cannot cancel again.
        report = self.finish_at_record_deadline()
        self.assertEqual(report["status"], "EXERCISED")
        self.assertTrue(report["ready_for_finish"])
        self.assertTrue(report["ledger"]["leases_retained"])
        self.assertEqual(report["ledger"]["outcome"], "UNKNOWN")
        self.assertFalse(report["helper_exit_proven"])
        self.assertFalse(report["chain_closed"])
        self.assertFalse(report["ledger"]["reader_delivered"])
        self.assertEqual(sum(item["kind"] == "CANCEL_REQUESTED" for item in self.state.events("job", self.request["operation_id"])), 1)
        self.assertEqual([item for item in self.calls if item[0] == "stop"], [("stop", self.unit)])
        self.assertEqual(report, self.case.close())
        self.assertEqual(report, self.case.poll())
        self.assertEqual(quota_contract._load(case_module.encode_report(report), 16384, 20), report)

    def test_running_observation_never_waits_on_held_broker_fence(self):
        with self.broker.fence:
            self.manager._inspect_unit(self.part)
            self.assertFalse(self.state.get("job", self.request["operation_id"])["record"]["cancel_requested"])
        self.case._thread.join(1)
        self.assertFalse(self.case._thread.is_alive())
        self.assertTrue(self.state.get("job", self.request["operation_id"])["record"]["cancel_requested"])

    def test_natural_end_or_no_running_before_record_deadline_is_not_exercised(self):
        report = self.finish_at_record_deadline()
        self.assertEqual(report["status"], "NOT_EXERCISED")
        self.assertFalse(report["cancel"]["attempted"])
        self.case._thread.join(1)
        self.assertFalse(self.case._thread.is_alive())
        self.assertFalse(any(item["kind"] == "CANCEL_REQUESTED" for item in self.state.events("job", self.request["operation_id"])))

    def test_helper_naturally_terminal_before_cancel_never_counts_as_hit(self):
        self.values.update(ActiveState="active", SubState="exited", ExecMainCode="1", ExecMainStatus="0")
        self.manager._inspect_unit(self.part)
        report = self.finish_at_record_deadline()
        self.assertEqual(report["status"], "NOT_EXERCISED")
        self.assertFalse(report["cancel"]["attempted"])
        self.assertFalse(report["stops"][0]["nonterminal"])

    def test_lost_cancel_reply_retains_durable_event_and_does_not_retry(self):
        original = self.broker.cancel
        def lost_reply(*args, **kwargs):
            original(*args, **kwargs)
            raise JobError("IO_UNCERTAIN", "modeled lost reply after durable cancellation")
        with mock.patch.object(self.broker, "cancel", side_effect=lost_reply) as cancel:
            self.trigger()
            self.case.poll()
            self.assertFalse(self.case.snapshot()["ready_for_finish"])
            self.broker.tick()
            report = self.finish_at_record_deadline()
        self.assertEqual(cancel.call_count, 1)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["cancel"]["error"], "IO_UNCERTAIN")
        self.assertIsNotNone(report["ledger"]["cancel_event"])
        self.assertFalse(report["helper_exit_proven"])

    def test_poll_cannot_freeze_old_ledger_when_cancel_finishes_after_database_read(self):
        original_transaction = self.state.transaction
        first, triggered = True, threading.Event()
        @contextlib.contextmanager
        def transaction():
            nonlocal first
            with original_transaction() as tx:
                yield tx
            if first and threading.current_thread() is threading.main_thread():
                first = False
                self.manager._inspect_unit(self.part)
                self.case._thread.join(1)
                triggered.set()
        with mock.patch.object(self.state, "transaction", transaction):
            snapshot = self.case.poll()
        self.assertTrue(triggered.is_set())
        self.assertFalse(snapshot["ready_for_finish"])
        report = self.case.poll()
        self.assertIsNotNone(report["ledger"]["cancel_event"])
        self.assertTrue(report["ledger"]["cancel_requested"])

    def test_observer_factory_requires_actual_core_and_keeps_guard_launch_result(self):
        with self.assertRaisesRegex(ValueError, "CASE_REAL_CORE_REQUIRED"):
            case_module.observe_manager(object)
        called, sentinel = [], object()
        def launch():
            called.append(True)
            return sentinel
        # This focused wrapper test models authorization; the other cases use
        # real Broker/SQLite authorization and durable cancellation.
        observed = case_module.observe_manager(runner._SystemdExecutionCore)()
        observed._q4_case = self.case
        observed.set_start_guard(lambda execution_id, callback, **options: callback())
        with mock.patch.object(self.case, "_delivery", side_effect=ValueError("modeled diagnostic failure")):
            result = observed._start_guard(self.part["execution_id"], launch)
        self.assertIs(result, sentinel)
        self.assertEqual(called, [True])
        self.assertEqual(self.case.snapshot()["status"], "INCOMPLETE")

    def test_cancel_uses_same_owner_and_requires_actual_policy_capability(self):
        for owner in (Principal("foreign", self.owner.scopes), Principal("owner", frozenset({"lh:read"}))):
            with self.subTest(owner=owner):
                with self.assertRaises((JobError, ValueError)):
                    case_module.Case(self.broker, self.request["operation_id"], owner)

    def test_cancel_committed_before_api_return_is_not_misclassified(self):
        original = self.broker.cancel
        committed, allow_return = threading.Event(), threading.Event()
        def delayed_return(*args, **kwargs):
            result = original(*args, **kwargs)
            committed.set()
            self.assertTrue(allow_return.wait(1))
            return result
        with mock.patch.object(self.broker, "cancel", side_effect=delayed_return):
            self.manager._inspect_unit(self.part)
            self.assertTrue(committed.wait(1))
            self.broker.tick()
            self.assertIsNone(self.case.snapshot()["cancel"]["returned_ns"])
            allow_return.set()
            self.case._thread.join(1)
        report = self.finish_at_record_deadline()
        self.assertEqual(report["status"], "EXERCISED")
        self.assertFalse(report["stops"][0]["cancel_returned_before_stop"])
        self.assertTrue(report["stops"][0]["cancel_effective_before_stop"])

    def test_failed_stop_delivery_is_not_exercised(self):
        self.trigger()
        command = self.command
        def failed(manager, *args, **kwargs):
            if args[0] == "stop":
                raise FileNotFoundError("modeled systemctl is unavailable")
            return command(manager, *args, **kwargs)
        with mock.patch.object(runner._SystemdExecutionCore, "_command", failed):
            self.broker.tick()
        report = self.finish_at_record_deadline()
        self.assertNotEqual(report["status"], "EXERCISED")
        self.assertEqual(report["stops"][0]["error"], "FileNotFoundError")
        self.assertFalse(report["helper_exit_proven"])

    def test_observer_error_does_not_change_core_return_or_prevent_stop(self):
        with mock.patch.object(self.case, "_observation", side_effect=ValueError("modeled logger fault")):
            self.assertEqual(self.manager._inspect_unit(self.part)["state"], "RUNNING")
        self.assertEqual(self.case.snapshot()["status"], "INCOMPLETE")
        self.trigger()
        with mock.patch.object(self.case, "_stop_before", side_effect=ValueError("modeled logger fault")):
            self.broker.tick()
        self.assertIn(("stop", self.unit), self.calls)

    def test_log_overflow_is_bounded_and_never_hidden(self):
        for _ in range(200):
            self.case._delivery("launch_callback_enter", self.part["execution_id"], "helper")
        report = self.finish_at_record_deadline()
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertGreater(report["logs"]["dropped"], 0)
        self.assertLessEqual(len(case_module.encode_report(report)), 16384)

    def test_decoder_rejects_invented_success_or_changed_identities(self):
        self.trigger()
        self.broker.tick()
        original = self.finish_at_record_deadline()
        mutations = (
            lambda r: r.update(chain_closed=True),
            lambda r: r.update(helper_exit_proven=True),
            lambda r: r["trigger"]["identity"].update(invocation_id="b" * 32),
            lambda r: r["stops"][0].update(nonterminal=False),
            lambda r: r["stops"][0].update(ack=None),
            lambda r: r["ledger"].update(no_delivery_after_cancel=False),
            lambda r: r["ledger"]["cancel_event"].update(observed_at_hex="nan"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                broken = copy.deepcopy(original)
                mutate(broken)
                self.assertTrue(case_module.validate_report(broken))


if __name__ == "__main__":
    unittest.main()
