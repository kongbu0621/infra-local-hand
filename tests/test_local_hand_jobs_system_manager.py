"""Shared Runner transport tests; systemd facts are modeled, pipes are real.

These tests do not claim PID1/guest qualification. The protocol suite separately
checks real SCM_CREDENTIALS/SCM_RIGHTS between original processes.
"""
import copy
import math
import os
import subprocess
import sys
import threading
import unittest
from unittest import mock

from local_hand_jobs import budget, manager_binding, quota_contract as q
from q2_fixtures import BOOT, SECOND
if sys.platform.startswith("linux"):
    from local_hand_jobs import quota_lifecycle as life, runner, system_manager as system


def configuration():
    binding = dict(schema=manager_binding.SCHEMA, manager_kind="system", authority_id="fixture-authority",
                   boot_id=BOOT, parent=dict(path="/fixture.slice/fixture-ordinary.slice", device=4, inode=81))
    return dict(uid=1100, gid=1100, slice="fixture-ordinary.slice",
                cgroup="/sys/fs/cgroup" + binding["parent"]["path"], manager_binding=binding)


class Channel:
    """Modeled administrator responses with actual anonymous read-only pipes."""
    def __init__(self, test, *, pending=False):
        self.calls = []
        self.closed = False
        self.fail = None
        self.state = dict(token="c" * 64, pid=os.getpid(), start_ticks=1, returncode=0)
        self.reads, self.writes = [], []
        for _ in range(2):
            read, write = os.pipe()
            self.reads.append(read); self.writes.append(write)
        test.addCleanup(self.cleanup)
        if not pending:
            self.finish()
        self.part = None

    def finish(self):
        for fd in self.writes:
            os.close(fd)
        self.writes = []

    def cleanup(self):
        self.finish()
        for fd in self.reads:
            os.close(fd)
        self.reads = []

    def close(self):
        self.closed = True

    def request(self, operation, **body):
        self.calls.append((operation, copy.deepcopy(body)))
        if self.fail == operation:
            raise q.QuotaError("MODELED_LOST_REPLY")
        if operation == "launch":
            return dict(client_state=dict(self.state)), tuple(os.dup(fd) for fd in self.reads)
        if operation == "support":
            return dict(supported=True, status="CANDIDATE", reasons=[],
                        manager_binding=configuration()["manager_binding"]), ()
        if operation == "inventory":
            return dict(returncode=0, stdout="", stderr=""), ()
        if operation == "stop":
            self.props.update(ActiveState="inactive", SubState="dead", ControlGroup="")
            return dict(returncode=0, stdout="", stderr="", client_state=dict(self.state)), ()
        if operation == "observe":
            view = body["view"]
            raw = (self.props["InvocationID"] + "\n" if view == "invocation" else
                   "".join(key + "=" + value + "\n" for key, value in self.props.items()))
            return dict(returncode=0, stdout=raw, stderr="", client_state=dict(self.state)), ()
        if operation == "seal":
            if not (self.part["launch"].stdout.closed and self.part["launch"].stderr.closed):
                raise AssertionError("ordinary pipes must close before root seal")
            return dict(closed=True, client_state=dict(self.state)), ()
        if operation == "client_stop":
            return dict(client_state=dict(self.state)), ()
        raise AssertionError(operation)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux pipe supervision")
class SystemManagerTests(unittest.TestCase):
    def fixture(self, *, pending=False):
        channel = Channel(self, pending=pending)
        manager = system.SystemManager(configuration(), channel=channel)
        binding = manager.execution_binding()
        identity = dict(job_key="fixture", execution_id="fixture:preflight", phase="preflight",
                        unit="lhj-" + "a" * 64 + ".service", manager_binding=binding)
        part = dict(unit=identity["unit"], identity=identity, execution_id=identity["execution_id"],
            manager_binding=binding, boot_id=BOOT, stage="helper", invocation_id=None,
            cgroup_parent=configuration()["cgroup"], quota_parent=binding["parent"],
            phase_deadline_boottime_ns=30 * SECOND, pipe_nonblocking=True,
            quota_transport=life.Transport(65536), cancel_event=threading.Event(), launch=None,
            recovered=False, cancel_before_launch=False, launch_acked=False, stop_acked=False,
            stop_requested=False)
        handle = dict(identity=identity, unit=identity["unit"], manager_binding=binding, version=3,
            execution=dict(quota_grant_digest="d" * 64,
                           bootstrap_allocation=dict(grant_digest="e" * 64)), helper=part,
            bootstrap=None, result_reader=None)
        manager._runs[identity["unit"]] = handle
        part["launch"] = manager._launch_stage(handle, part, ["not-transmitted"], {"NOT": "transmitted"})
        for stream in (part["launch"].stdout, part["launch"].stderr):
            os.set_blocking(stream.fileno(), False)
            self.addCleanup(stream.close)
        channel.part = part
        channel.props = dict(Id=part["unit"], LoadState="loaded", ActiveState="active", SubState="exited",
            ControlGroup=binding["parent"]["path"] + "/" + part["unit"], InvocationID="a" * 32,
            Job="", ExecMainCode="1", ExecMainStatus="0", Result="success", Restart="no", TriggeredBy="",
            ExecStop="", ExecStopPost="", ExecReload="", KillMode="control-group", Type="exec", ExitType="cgroup",
            RemainAfterExit="yes", ExecStartPre="", ExecStartPost="", OnFailure="", OnSuccess="", RestartForceExitStatus="")
        clock = mock.patch.object(budget, "current_clock", return_value=dict(boot_id=BOOT, boottime_ns=2 * SECOND))
        parent = mock.patch.object(life, "parent", return_value=(binding["parent"], True))
        clock.start(); parent.start()
        self.addCleanup(clock.stop); self.addCleanup(parent.stop)
        return manager, handle, part, channel

    def test_launch_sends_only_reference_and_bound_digests_and_uses_real_pipes(self):
        with mock.patch.object(subprocess, "Popen", side_effect=AssertionError("ordinary may not launch")):
            manager, handle, part, channel = self.fixture()
        self.assertEqual([("launch", dict(ref=dict(execution_id="fixture:preflight", phase="preflight", stage="helper"),
            bindings=dict(allocation_digest="e" * 64, grant_digest="d" * 64)))], channel.calls)
        self.assertNotEqual(os.fstat(part["launch"].stdout.fileno()).st_ino,
                            os.fstat(part["launch"].stderr.fileno()).st_ino)
        self.assertEqual(0, part["launch"].poll())
        self.assertEqual(1, len(channel.calls))  # poll is the observed original state, not another RPC.

    def test_shared_observer_requires_dual_eof_client_exit_stop_and_root_seal(self):
        manager, handle, part, channel = self.fixture()
        self.assertEqual("UNKNOWN", manager._inspect_unit(part)["state"])
        result = manager._inspect_unit(part)
        self.assertEqual("EXITED", result["state"])
        self.assertTrue(part["system_sealed"])
        self.assertTrue(all(part["quota_exit"][key] for key in q.EXIT_FLAGS))
        self.assertEqual(["launch", "observe", "observe", "stop", "observe", "seal"],
                         [item[0] for item in channel.calls])
        before = len(channel.calls)
        self.assertEqual(result, manager._inspect_unit(part))
        self.assertEqual(before, len(channel.calls))

    def test_one_open_stream_prevents_seal_and_stage_completion(self):
        manager, handle, part, channel = self.fixture(pending=True)
        os.close(channel.writes.pop(0))
        manager._inspect_unit(part)
        with self.assertRaisesRegex(q.QuotaError, "ORIGINAL_CLIENT_EOF_UNPROVEN"):
            manager._inspect_unit(part)
        self.assertNotIn("seal", [item[0] for item in channel.calls])
        channel.finish()
        self.assertEqual("EXITED", manager._inspect_unit(part)["state"])

    def test_lost_seal_ack_never_reuses_cached_local_success_or_resends(self):
        manager, handle, part, channel = self.fixture()
        channel.fail = "seal"
        manager._inspect_unit(part)
        with self.assertRaises(runner.RunnerError):
            manager._inspect_unit(part)
        self.assertEqual("EXITED", part["quota_final"]["state"])
        self.assertEqual("UNKNOWN", manager._inspect_unit(part)["state"])
        self.assertEqual(1, sum(op == "seal" for op, _ in channel.calls))
        self.assertTrue(channel.closed)

    def test_manager_binding_is_checked_before_cached_exit_or_rpc(self):
        manager, handle, part, channel = self.fixture()
        manager._inspect_unit(part); manager._inspect_unit(part)
        before = len(channel.calls)
        for key in ("manager_kind", "authority_id", "boot_id", "parent"):
            with self.subTest(key=key):
                changed = dict(part, manager_binding=copy.deepcopy(part["manager_binding"]))
                changed["manager_binding"][key] = "changed"
                with self.assertRaises(runner.RunnerError):
                    manager._inspect_unit(changed)
        self.assertEqual(before, len(channel.calls))

    def test_wrong_client_token_or_changed_exit_code_is_not_accepted(self):
        for field, value in (("token", "f" * 64), ("pid", 999), ("start_ticks", 2), ("returncode", 1)):
            with self.subTest(field=field):
                manager, handle, part, channel = self.fixture()
                channel.state[field] = value
                with self.assertRaises(runner.RunnerError):
                    manager._command("show", part["unit"], "--property=InvocationID", "--value")
                self.assertTrue(channel.closed)

    def test_unrecognized_command_and_unit_never_reach_gateway(self):
        manager, handle, part, channel = self.fixture()
        before = len(channel.calls)
        for arguments in (("start", part["unit"]), ("set-property", part["unit"], "User=0"),
                          ("show", "unrelated.service", "--property=InvocationID", "--value")):
            with self.subTest(arguments=arguments), self.assertRaises((runner.RunnerError, q.QuotaError)):
                manager._command(*arguments)
        self.assertEqual(before, len(channel.calls))

    def test_legacy_or_nonquota_plan_is_rejected_before_rpc(self):
        manager, handle, part, channel = self.fixture()
        before = len(channel.calls)
        for plan in (dict(supervision_version=2, quota_observation_grant={}),
                     dict(supervision_version=3)):
            with self.assertRaises(runner.RunnerError):
                manager._admit(dict(plan, manager_binding=manager.execution_binding()))
        self.assertEqual(before, len(channel.calls))

    def test_lost_launch_reply_consumes_channel_without_an_ordinary_retry(self):
        manager, handle, part, channel = self.fixture()
        channel.fail = "launch"
        with self.assertRaises(runner.RunnerError):
            manager._launch_stage(handle, part, [], {})
        with self.assertRaises(runner.RunnerError):
            manager._launch_stage(handle, part, [], {})
        self.assertEqual(2, sum(op == "launch" for op, _ in channel.calls))  # first fixture + one lost reply
        self.assertTrue(channel.closed)

    def test_recovery_does_not_reconstruct_lost_pipes_or_redeliver(self):
        manager, handle, part, channel = self.fixture()
        part["recovered"] = True
        before = len(channel.calls)
        self.assertEqual("UNKNOWN", manager._inspect_unit(part)["state"])
        self.assertEqual(before, len(channel.calls))

    def test_runner_freezes_manager_identity_before_enqueuing(self):
        manager = system.SystemManager(configuration(), channel=mock.Mock())
        supervisor = runner.Runner(manager)
        binding = manager.execution_binding()
        with mock.patch.object(threading, "Thread") as thread:
            with self.assertRaises(Exception):
                supervisor.start("fixture", "fixture:one", dict(phase="preflight", supervision_version=3))
            thread.assert_not_called()
            identity = supervisor.start("fixture", "fixture:one", dict(phase="preflight",
                supervision_version=3, manager_binding=binding))
            self.assertEqual(binding, identity["manager_binding"])
            self.assertEqual(1, thread.call_count)

    def test_production_wrapper_remains_closed(self):
        manager = runner.SystemdManager(configuration())
        self.assertFalse(manager.support()["supported"])
        self.assertIn("E3_SUPERVISION_UNVERIFIED", manager.support()["reasons"])

    def test_nine_slow_stages_fit_original_shared_call_budget(self):
        # Exercise the real Runner polling loop and quota lifecycle. Host
        # manager facts are modeled; each stage keeps real pipes and consumes
        # seven seconds of a virtual original clock before its stop/EOF seal.
        elapsed = [0.0]
        calls = []
        intervals = []
        for phase_index, phase in enumerate(("preflight", "business", "evidence")):
            phase_start = elapsed[0]
            for stage in ("bootstrap", "helper", "result_reader"):
                manager, handle, part, channel = self.fixture()
                part["identity"]["phase"] = phase
                part["stage"] = stage
                part["phase_deadline_boottime_ns"] = int((phase_start + 23) * SECOND)
                began = elapsed[0]
                channel.props.update(SubState="running", ExecMainCode="0")
                original_inspect = manager._inspect_unit
                def inspect(current):
                    if elapsed[0] - began >= 7 and channel.props["ActiveState"] == "active":
                        channel.props.update(SubState="exited", ExecMainCode="1")
                    return original_inspect(current)
                manager.start = lambda identity, plan, cancel: part
                manager.inspect = inspect
                manager.export_handle = lambda current: dict(part["identity"])
                class ClockEvent:
                    def is_set(self): return False
                    def wait(self, interval):
                        intervals.append(interval)
                        elapsed[0] += interval
                        return False
                item = runner._Execution(part["identity"], {}, cancel=ClockEvent())
                with mock.patch.object(budget, "current_clock", side_effect=lambda:
                        dict(boot_id=BOOT, boottime_ns=int(elapsed[0] * SECOND))):
                    runner.Runner(manager)._supervise(item)
                self.assertEqual("EXITED", item.proof["state"])
                self.assertTrue(part["system_sealed"])
                calls.extend(op for op, _ in channel.calls)
            self.assertLess(elapsed[0] - phase_start, 23)
        self.assertEqual({0.5}, set(intervals))
        self.assertEqual(67.5, elapsed[0])
        # Root control counts include one prelaunch absence query, the stop's
        # independent show+stop pair, and two management readiness queries per
        # bootstrap. Support uses no external manager command.
        wire_calls = len(calls) + 5 + 1  # initial/per-phase support and inventory
        controls = sum({"launch": 1, "observe": 1, "stop": 2, "seal": 1}[op] for op in calls) + 6 + 1
        maximum_observations = math.ceil(72 / manager.observation_interval()) + 9
        self.assertLessEqual(wire_calls, maximum_observations + 42)
        self.assertLessEqual(controls, maximum_observations + 52)
        self.assertLessEqual(maximum_observations + 52, 256)
        self.assertEqual(0.05, runner._SystemdExecutionCore().observation_interval())

    def test_system_cadence_wait_is_interrupted_by_original_cancel_event(self):
        manager = system.SystemManager(configuration(), channel=mock.Mock())
        waiting = threading.Event()
        cancellation = threading.Event()
        stopped = threading.Event()
        observed_intervals = []
        class CancelEvent:
            def is_set(self): return cancellation.is_set()
            def wait(self, interval):
                observed_intervals.append(interval)
                waiting.set()
                return cancellation.wait(interval)
        manager.start = lambda identity, plan, cancel: identity
        manager.stop = lambda handle: stopped.set()
        manager.inspect = lambda handle: ({**runner._unknown(), "state": "EXITED",
            "future_start_blocked": True, "tree_exited": True} if stopped.is_set() else runner._unknown())
        manager.export_handle = lambda handle: handle
        identity = dict(execution_id="fixture:cancel", phase="preflight", job_key="fixture",
                        unit="fixture", manager_binding=manager.execution_binding())
        item = runner._Execution(identity, {}, cancel=CancelEvent())
        thread = threading.Thread(target=runner.Runner(manager)._supervise, args=(item,))
        thread.start()
        try:
            self.assertTrue(waiting.wait(1))
            cancellation.set()
            self.assertTrue(stopped.wait(1))
            thread.join(1)
            self.assertFalse(thread.is_alive())
            self.assertEqual([0.5], observed_intervals)
            self.assertEqual("EXITED", item.proof["state"])
        finally:
            cancellation.set()
            thread.join(1)


if __name__ == "__main__":
    unittest.main()
