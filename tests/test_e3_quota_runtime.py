"""LOGIC_ONLY Q1 controller assembly against fake manager/process observations.

No systemd command, quota syscall, protected host preparation or process launch.
Real parsing, unit argv, binding, monitor and run/recovery transitions are used;
_admit_host, journal and manager capture are explicit test doubles. These checks
are source regression evidence, never a real system-manager acceptance result.
"""
from contextlib import ExitStack
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from admin.local_hand_quota_observer import admission as a, protected_inputs as p, systemd_runtime as r
from test_e3_quota_monitor import binding, decode, encoded, fixture, report, INVOCATION, NOW
from test_e3_quota_worker import runtime


class FakeClock:
    def __init__(self):
        self.now = NOW

    def sleep(self, seconds):
        self.now += max(1, int(seconds * 1_000_000_000))


class FakeJournal:
    control_dir = "/synthetic-control/observer"

    def __init__(self, prior=None):
        self.record = prior
        self.deliveries = 0
        self.remembered = []
        self.marked = []
        self.read_error = None
        self.remember_error = None
        self.mark_error = None

    def verify_directory(self):
        pass

    def read(self, bound):
        if self.read_error is not None:
            raise self.read_error
        if self.record is None:
            raise a.Rejected("INTENT_REQUIRED")
        return self.record

    def deliver_once(self, bound, deliver):
        if self.record is not None:
            return SimpleNamespace(delivered=False, record=self.record)
        self.record = SimpleNamespace(status="INTENT", invocation_id=None, reason=None)
        self.deliveries += 1
        deliver(bound)
        return SimpleNamespace(delivered=True, record=self.record)

    def remember_invocation(self, bound, invocation):
        self.remembered.append(invocation)
        if self.remember_error is not None:
            raise self.remember_error
        self.record.invocation_id = invocation

    def mark_unknown(self, bound, reason):
        self.marked.append(reason)
        if self.mark_error is not None:
            raise self.mark_error
        self.record.status = "UNKNOWN"
        self.record.reason = reason


class FakeCapture:
    """In-memory fake pipe/process; pump is deterministic, never spawns."""
    def __init__(self, limit, *, plan=None, settled=False):
        self.limit = limit
        self.plan = plan
        self.process = SimpleNamespace(returncode=0 if settled else None, pid=4242)
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.error = None
        self.eof = {"stdout", "stderr"} if settled else set()
        self.started = []
        self.pumps = 0
        self.closed = False

    def start(self, argv):
        self.started.append(argv)
        self.stdout.extend(self.plan.output)

    def pump(self):
        self.pumps += 1
        if self.plan is not None and self.pumps >= self.plan.finish_after:
            self.process.returncode = self.plan.returncode
            if self.plan.eof_at is not None and self.plan.clock.now >= self.plan.eof_at:
                self.eof.update(("stdout", "stderr"))
            self.error = self.plan.capture_error

    @property
    def exited(self):
        return self.process.returncode is not None

    @property
    def settled(self):
        return self.exited and len(self.eof) == 2

    @property
    def done(self):
        return self.settled and self.error is None

    def close_pipes(self):
        self.closed = True
        if self.plan is not None and self.plan.close_error:
            self.error = "CAPTURE_CLOSE_UNCERTAIN"


class Scenario:
    def __init__(self, case, *, prior=None):
        self.clock = FakeClock()
        self.config = runtime()
        value = fixture()
        value["cgroup_parent"] = "/" + self.config.query_slice
        value["installation_digest"] = p.installation_digest(self.config)
        self.bound = binding(decode(value))
        self.journal = FakeJournal(prior)
        self.controller = object.__new__(r.Q1Controller)
        self.controller.config_path = "/synthetic/admin/runtime.json"
        self.controller.config = self.config
        self.controller.manifest = self.bound.manifest
        self.controller.journal = self.journal
        self.controller.launcher = None
        self.controller.controls = []
        self.controller._used = False
        self.host_admissions = []
        self.commands = []
        self.started = []
        self.show_values = []
        self.parent_empty = True
        self.stop_advance_ns = 0
        self.finish_on_stop = False
        self.unsettled_command = None
        self.capture_plan = SimpleNamespace(clock=self.clock, finish_after=1, returncode=0,
                                            eof_at=NOW, output=self.output(), capture_error=None, close_error=False)
        self.stack = ExitStack()
        case.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(r, "boottime_ns", side_effect=lambda: self.clock.now))
        self.stack.enter_context(patch.object(r.time, "sleep", side_effect=self.clock.sleep))
        self.stack.enter_context(patch.object(r, "_boot_id", return_value=self.bound.manifest.boot_id))
        self.stack.enter_context(patch.object(r, "Capture", side_effect=self.make_capture))
        self.controller._admit_host = lambda bound, **kwargs: self.host_admissions.append(kwargs)
        self.controller._parent_empty = lambda bound: self.parent_empty
        self.controller._command = self.command

    def make_capture(self, limit):
        capture = FakeCapture(limit, plan=self.capture_plan)
        self.started.append(capture)
        return capture

    def output(self, *, invocation=INVOCATION, **changes):
        ready = {"schema": "local-hand-quota-worker-ready/v1", "boot_id": self.bound.manifest.boot_id,
                 "unit": self.bound.unit, "invocation_id": invocation, "cgroup": self.bound.cgroup,
                 "manifest_digest": self.bound.manifest.digest, "runtime_digest": self.config.digest,
                 "request_id": self.bound.request_id}
        ready.update(changes)
        return encoded(ready) + encoded(report(self.bound.manifest))

    def values(self, *, missing=False, **changes):
        values = dict.fromkeys(r.SHOW_FIELDS, "")
        values.update(Id=self.bound.unit, LoadState="not-found" if missing else "loaded", ActiveState="active",
                      SubState="exited", InvocationID=INVOCATION, ControlGroup=self.bound.cgroup,
                      Job="0", ExecMainCode="1", ExecMainStatus="0", Result="success", Slice=self.config.query_slice,
                      Type="exec", ExitType="cgroup", RemainAfterExit="yes", Restart="no", KillMode="control-group")
        values.update(changes)
        return values

    def normal(self):
        self.show_values = [self.values(missing=True), self.values(), self.values(),
                            self.values(ActiveState="inactive", SubState="dead")]
        return self

    def command(self, args, *, absolute_end_ns):
        # Match real command preconditions; no replacement client after UNKNOWN.
        a.require(len(self.controller.controls) < r.MAX_CONTROL_CALLS
                  and all(item.settled for item in self.controller.controls), "CONTROL_PROCESS_UNRESOLVED")
        a.require(self.clock.now < absolute_end_ns, "CONTROL_DEADLINE_EXPIRED")
        self.commands.append(tuple(args))
        capture = FakeCapture(r.CONTROL_BYTES, settled=True)
        self.controller.controls.append(capture)
        if self.unsettled_command == len(self.commands):
            capture.process.returncode = None
            capture.eof.clear()
            raise a.Rejected("MANAGER_COMMAND_UNCERTAIN")
        if args[0] == "show":
            if not self.show_values:
                raise AssertionError("unexpected additional manager show")
            values = self.show_values.pop(0)
            return ("\n".join(key + "=" + values[key] for key in r.SHOW_FIELDS) + "\n").encode()
        if args[0] == "stop":
            self.clock.now += self.stop_advance_ns
            if self.finish_on_stop:
                self.capture_plan.finish_after = 0
                self.controller.launcher.pump()
            return b""
        raise AssertionError("unexpected manager command")

    def run(self):
        return self.controller.run(p.encode_ticket(self.bound))

    def recover(self):
        return self.controller.recover_original(p.encode_ticket(self.bound))

    def stops(self):
        return [command for command in self.commands if command[0] == "stop"]


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux controller assembly")
class ControllerAssemblyTests(unittest.TestCase):
    def test_normal_assembly_uses_real_argv_ready_and_native_monitor(self):
        case = Scenario(self).normal()
        result = case.run()
        self.assertEqual(result.decision.status, "OBSERVED")
        self.assertTrue(result.decision.query_stopped and result.decision.facts_match)
        self.assertFalse(result.decision.real_e3_accepted or result.decision.production_supported)
        self.assertEqual(case.journal.deliveries, 1)
        self.assertEqual(case.journal.remembered, [INVOCATION])
        self.assertEqual(len(case.stops()), 1)
        command = case.started[0].started[0]
        self.assertEqual(command[0], case.config.systemd_run_path)
        self.assertIn("--property=CapabilityBoundingSet=CAP_SYS_ADMIN CAP_DAC_READ_SEARCH", command)
        self.assertIn("--property=ReadWritePaths=" + case.bound.slot.path, command)
        self.assertIn("--property=InaccessiblePaths=" + case.journal.control_dir, command)
        self.assertEqual(command[-1], p.encode_ticket(case.bound))
        self.assertEqual(dict(result.unit_facts)["ExecMainStatus"], "0")

    def test_pending_not_found_and_loaded_without_invocation_wait_for_original(self):
        case = Scenario(self).normal()
        case.capture_plan.finish_after = 3
        case.show_values[1:1] = [case.values(missing=True, InvocationID=""), case.values(InvocationID="", SubState="start")]
        result = case.run()
        self.assertEqual(result.decision.status, "OBSERVED")
        self.assertEqual(case.journal.deliveries, 1)
        self.assertEqual(len(case.started), 1)
        self.assertEqual(case.journal.remembered, [INVOCATION])

    def test_failed_unit_retains_terminal_facts_and_stops_same_invocation(self):
        case = Scenario(self).normal()
        failed = case.values(ActiveState="failed", SubState="failed", Result="exit-code", ExecMainStatus="2")
        case.show_values[1] = failed
        case.capture_plan.returncode = 2
        result = case.run()
        self.assertEqual(result.decision.reason, "QUERY_UNIT_UNSUCCESSFUL")
        self.assertTrue(result.decision.query_stopped)
        self.assertEqual(dict(result.unit_facts)["ExecMainStatus"], "2")
        self.assertEqual(case.stops(), [("stop", case.bound.unit)])
        self.assertEqual(case.journal.record.status, "UNKNOWN")

    def test_parent_nonempty_stays_unknown_and_original_failure_survives_cleanup(self):
        case = Scenario(self).normal()
        case.parent_empty = False
        result = case.run()
        self.assertEqual(result.decision.reason, "QUERY_TREE_NOT_EMPTY")
        self.assertFalse(result.decision.query_stopped)
        self.assertEqual(result.cleanup_reason, "QUERY_TREE_NOT_EMPTY")
        self.assertEqual(len(case.stops()), 1)
        self.assertEqual(dict(result.unit_facts)["Result"], "success")

    def test_no_eof_retains_unknown_even_after_launcher_exit_and_stop_ack(self):
        case = Scenario(self).normal()
        case.capture_plan.eof_at = None
        result = case.run()
        self.assertEqual(result.decision.reason, "COLLECTOR_EXIT_UNPROVEN")
        self.assertFalse(result.decision.query_stopped)
        self.assertEqual(result.pending_clients, (4242,))
        self.assertFalse(case.started[0].closed)
        self.assertEqual(len(case.stops()), 1)

    def test_stop_and_pipe_eof_must_both_meet_original_deadline(self):
        for delayed in ("stop", "eof"):
            with self.subTest(delayed=delayed):
                case = Scenario(self).normal()
                if delayed == "stop":
                    case.stop_advance_ns = case.bound.deadline_ns - NOW
                else:
                    case.capture_plan.eof_at = case.bound.deadline_ns
                result = case.run()
                self.assertEqual(result.decision.reason, "DEADLINE_EXPIRED")
                self.assertTrue(result.decision.query_stopped)
                self.assertFalse(result.decision.facts_match)
                case.stack.close()

    def test_running_until_deadline_stops_original_without_inventing_timely_terminal(self):
        case = Scenario(self)
        case.capture_plan.finish_after = 999
        case.finish_on_stop = True
        case.show_values = ([case.values(missing=True)]
                            + [case.values(ActiveState="active", SubState="running")] * 25
                            + [case.values(), case.values(ActiveState="inactive", SubState="dead")])
        result = case.run()
        self.assertEqual(result.decision.reason, "TIMELY_TERMINAL_FACTS_MISSING")
        self.assertTrue(result.decision.query_stopped)
        self.assertEqual(dict(result.unit_facts), {})
        self.assertEqual(len(case.stops()), 1)
        self.assertEqual(case.journal.deliveries, 1)
        self.assertLessEqual(result.control_calls, r.MAX_CONTROL_CALLS)

    def test_early_launcher_exit_without_invocation_never_guesses_stop_target(self):
        case = Scenario(self)
        case.show_values = [case.values(missing=True), case.values(missing=True, InvocationID="")]
        result = case.run()
        self.assertEqual(result.decision.reason, "LAUNCHER_EXIT_BEFORE_PROOF")
        self.assertIsNone(result.invocation_id)
        self.assertEqual(case.stops(), [])
        self.assertEqual(case.journal.deliveries, 1)

    def test_control_process_uncertainty_does_not_spawn_replacement_stop(self):
        case = Scenario(self).normal()
        case.capture_plan.finish_after = 3
        case.show_values[1] = case.values(ActiveState="active", SubState="running")
        case.unsettled_command = 3
        result = case.run()
        self.assertEqual(result.decision.reason, "MANAGER_COMMAND_UNCERTAIN")
        self.assertEqual(result.cleanup_reason, "CONTROL_PROCESS_UNRESOLVED")
        self.assertEqual(len(case.commands), 3)
        self.assertEqual(case.stops(), [])
        self.assertTrue(result.pending_clients)

    def test_prior_intent_or_reused_controller_cannot_deliver_again(self):
        prior = SimpleNamespace(status="UNKNOWN", invocation_id=INVOCATION, reason="ORIGINAL_CRASH")
        case = Scenario(self, prior=prior)
        result = case.run()
        self.assertEqual(result.decision.reason, "ORIGINAL_INTENT_RETAINED")
        self.assertEqual(case.journal.deliveries, 0)
        self.assertEqual(case.started, [])
        self.assertEqual(case.commands, [])
        self.assertEqual(case.journal.marked, [])
        self.assertEqual(prior.reason, "ORIGINAL_CRASH")
        with self.assertRaisesRegex(a.Rejected, "CONTROLLER_ALREADY_USED"):
            case.run()

    def test_invocation_drift_never_stops_replacement(self):
        case = Scenario(self).normal()
        case.show_values[2] = case.values(InvocationID="b" * 32)
        result = case.run()
        self.assertEqual(result.decision.reason, "INVOCATION_CHANGED")
        self.assertEqual(case.stops(), [])
        self.assertFalse(result.decision.query_stopped)

    def test_ready_identity_mismatch_stays_unknown_after_verified_stop(self):
        for changes in ({"runtime_digest": "9" * 64}, {"request_id": "9" * 32}, {"invocation": "b" * 32}):
            with self.subTest(changes=changes):
                case = Scenario(self).normal()
                case.capture_plan.output = case.output(**changes)
                result = case.run()
                self.assertEqual(result.decision.status, "UNKNOWN")
                self.assertIn(result.decision.reason, ("WORKER_IDENTITY_CHANGED", "WORKER_INVOCATION_CHANGED"))
                self.assertTrue(result.decision.query_stopped)
                case.stack.close()

    def test_journal_write_failure_keeps_query_failure_and_in_memory_identity(self):
        case = Scenario(self).normal()
        case.journal.remember_error = a.Rejected("INVOCATION_FSYNC_FAILED")
        case.journal.mark_error = OSError(5, "journal I/O")
        result = case.run()
        self.assertEqual(result.decision.reason, "INVOCATION_FSYNC_FAILED")
        self.assertEqual(result.journal_reason, "JOURNAL_IO_UNCERTAIN")
        self.assertEqual(result.invocation_id, INVOCATION)
        self.assertEqual(len(case.stops()), 1)

    def test_pipe_close_error_prevents_observed_result(self):
        case = Scenario(self).normal()
        case.capture_plan.close_error = True
        result = case.run()
        self.assertEqual(result.decision.reason, "COLLECTOR_IO_UNCERTAIN")
        self.assertFalse(result.decision.facts_match)

    def test_recovery_without_original_invocation_only_observes_and_never_stops(self):
        case = Scenario(self, prior=SimpleNamespace(status="UNKNOWN", invocation_id=None, reason="LOST_ACK"))
        case.show_values = [case.values()]
        result = case.recover()
        self.assertEqual(result.decision.reason, "ORIGINAL_INVOCATION_REQUIRED")
        self.assertEqual(case.stops(), [])
        self.assertEqual(case.started, [])
        self.assertEqual(case.journal.deliveries, 0)
        self.assertEqual(case.journal.record.reason, "LOST_ACK")
        self.assertEqual(case.host_admissions, [{"require_empty": False}])

    def test_recovery_known_original_stops_but_cannot_restore_lost_collectors(self):
        case = Scenario(self, prior=SimpleNamespace(status="UNKNOWN", invocation_id=INVOCATION, reason="LOST_OUTPUT"))
        case.show_values = [case.values(), case.values(), case.values(ActiveState="inactive", SubState="dead")]
        result = case.recover()
        self.assertEqual(result.decision.reason, "ORIGINAL_COLLECTOR_AND_OUTPUT_LOST")
        self.assertFalse(result.decision.query_stopped or result.decision.facts_match)
        self.assertEqual(len(case.stops()), 1)
        self.assertEqual(case.started, [])
        self.assertEqual(case.journal.record.reason, "LOST_OUTPUT")

    def test_recovery_invocation_change_never_stops_replacement(self):
        case = Scenario(self, prior=SimpleNamespace(status="UNKNOWN", invocation_id=INVOCATION, reason="LOST_OUTPUT"))
        case.show_values = [case.values(InvocationID="b" * 32)]
        result = case.recover()
        self.assertEqual(result.decision.reason, "INVOCATION_CHANGED")
        self.assertEqual(case.stops(), [])
        self.assertEqual(case.journal.deliveries, 0)


if __name__ == "__main__":
    unittest.main()
