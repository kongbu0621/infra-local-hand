"""Real SQLite sequencing and fixed argv; host/delegation facts are not simulated PASS."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from local_hand_jobs import budget, quota_contract as q
from local_hand_jobs.contract import JobError
from q2_fixtures import BOOT, SECOND, make_grant
import test_local_hand_jobs_quota_binding as binding_tests

PATH = Path(__file__).parent / "e3_host" / "q2_resident.py"
SPEC = importlib.util.spec_from_file_location("resident_fixture_entry", PATH)
resident = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resident)
if sys.platform.startswith("linux"):
    from local_hand_jobs import runner


class ResidentEntryTests(unittest.TestCase):
    def test_no_fixture_never_composes_or_provisions(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(PATH)], capture_output=True, timeout=5)
        self.assertEqual(3, result.returncode)
        value = json.loads(result.stdout)
        self.assertEqual("BLOCKED", value["status"])
        self.assertEqual("EXPLICIT_PRIVATE_FIXTURE_REQUIRED", value["reason"])
        self.assertIs(value["production_supported"], False)
        self.assertIs(value["q3_accepted"], False)

    def test_fixed_synthetic_scope_rejects_ordinary_client_identity(self):
        for principal in ({"principal_id": "real-user", "scopes": ["lh:read"]},
                          {"principal_id": "q2-synthetic-check", "scopes": ["lh:read", "lh:read"]}):
            broker = mock.Mock()
            with self.assertRaises(ValueError):
                resident.prepare_request({"principal": principal}, broker)
            broker.submit.assert_not_called()

    def test_typed_job_failure_and_cleanup_uncertainty_emit_bounded_summary(self):
        for cleanup_failure in (False, True):
            broker = mock.Mock()
            channel = mock.Mock()
            if cleanup_failure:
                channel.close.side_effect = JobError("IO_UNCERTAIN", "private diagnostic detail")
            with mock.patch.object(resident, "bootstrap", return_value={"bridge": {}, "schema": resident.SCHEMA}), \
                 mock.patch.object(resident, "channel_from_pin", return_value=channel), \
                 mock.patch.object(resident, "compose", return_value=broker), \
                 mock.patch.object(resident, "run", side_effect=JobError("CONFLICT", "private diagnostic detail")), \
                 mock.patch("local_hand_jobs.cli.close_service") as close, \
                 mock.patch.object(resident.os, "write") as write:
                self.assertEqual(3, resident.main(["--fixture", "/pinned", "--sha256", "a"*64]))
            close.assert_called_once_with(broker, None, failed=True)
            raw = write.call_args.args[1]
            self.assertLessEqual(len(raw), 4096)
            self.assertNotIn(b"private", raw)
            self.assertEqual("INCOMPLETE", json.loads(raw)["status"])
            self.assertEqual("IO_UNCERTAIN" if cleanup_failure else "CONFLICT", json.loads(raw)["reason"])

    def test_only_explicit_v2_can_select_the_fixed_complete_phase_sequence(self):
        self.assertEqual(resident.PHASES, resident.fixture_phases(dict(schema=resident.SCHEMA,
            purpose="ISOLATED_Q2_RESIDENT", phases=["preflight"])))
        self.assertEqual(resident.CHAIN_PHASES, resident.fixture_phases(dict(schema=resident.CHAIN_SCHEMA,
            purpose="ISOLATED_Q2_CHAIN", phases=list(resident.CHAIN_PHASES))))
        for version,purpose,phases in ((resident.SCHEMA,"ISOLATED_Q2_RESIDENT",list(resident.CHAIN_PHASES)),
                (resident.CHAIN_SCHEMA,"ISOLATED_Q2_CHAIN",["preflight","evidence"]),
                (resident.CHAIN_SCHEMA,"ISOLATED_Q2_CHAIN",["preflight","business","business"]),
                (resident.CHAIN_SCHEMA,"ISOLATED_Q2_RESIDENT",list(resident.CHAIN_PHASES))):
            with self.subTest(phases=phases), self.assertRaisesRegex(ValueError,"RESIDENT_SCHEMA"):
                resident.fixture_phases(dict(schema=version,purpose=purpose,phases=phases))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux production manager and exact Q2 argv")
class FixedExecutionTests(unittest.TestCase):
    def plan(self):
        self.grant = make_grant()
        data = self.grant.as_dict()
        return dict(phase="preflight", execution_id=data["budget"]["execution_id"],
            budget_grant=data["budget"], budgets=data["budget"]["limits"],
            bootstrap_allocation=data["allocation"], supervision_version=3,
            quota_observation_grant=data,
            execution=dict(python="/usr/bin/python3", kind="host.inspect", operation_id=data["budget"]["operation_id"],
                           roots=data["allocation"]["source_roots"], readonly=[], storage={}, stages=[]))

    def test_production_remains_closed_even_when_real_core_reports_supported(self):
        with mock.patch.object(runner._SystemdExecutionCore, "support", return_value={
                "supported": True, "status": "CANDIDATE", "reasons": []}):
            value = runner.SystemdManager().support()
        self.assertEqual({"supported": False, "status": "UNSUPPORTED",
                          "reasons": ["E3_SUPERVISION_UNVERIFIED"]}, value)

    def test_delayed_launch_preserves_argv_while_actual_runtime_shrinks(self):
        plan = self.plan()
        original = copy.deepcopy(plan)
        first = runner._quota_prepared_execution(plan, parent_mount_namespace="mnt:[123]", now_ns=2*SECOND)
        later = runner._quota_prepared_execution(plan, parent_mount_namespace="mnt:[123]", now_ns=3*SECOND)
        self.assertEqual(first, later)
        self.assertEqual(runner.quota_bootstrap_argv(first, self.grant, now_ns=2*SECOND),
                         runner.quota_bootstrap_argv(later, self.grant, now_ns=3*SECOND))
        self.assertLess(runner._runtime_microseconds(plan["budget_grant"], now={"boot_id": BOOT,"boottime_ns":3*SECOND}),
                        runner._runtime_microseconds(plan["budget_grant"], now={"boot_id": BOOT,"boottime_ns":2*SECOND}))
        self.assertEqual(original, plan)

    def test_frozen_payload_does_not_renew_expired_or_wrong_binding(self):
        plan = self.plan()
        for fault in ("deadline", "namespace", "allocation", "budget", "version"):
            candidate = copy.deepcopy(plan)
            now = 2*SECOND
            namespace = "mnt:[123]"
            if fault == "deadline":
                now = self.grant.request.as_dict()["deadline_ns"]
            if fault == "namespace":
                namespace = "untrusted"
            if fault == "allocation":
                candidate["bootstrap_allocation"]["slot_id"] = "other"
            if fault == "budget":
                candidate["budget_grant"]["reserved_boottime_ns"] += SECOND
            if fault == "version":
                candidate["supervision_version"] = 2
            with self.subTest(fault=fault), self.assertRaises((ValueError, JobError)):
                runner._quota_prepared_execution(candidate, parent_mount_namespace=namespace, now_ns=now)

    def test_actual_manager_uses_same_argv_and_original_guard(self):
        plan = self.plan()
        execution = plan["execution_id"]
        unit = "lhj-" + __import__("hashlib").sha256(execution.encode()).hexdigest() + ".service"
        identity = dict(execution_id=execution, job_key=plan["budget_grant"]["operation_id"], phase="preflight", unit=unit)
        manager = runner._SystemdExecutionCore({"uid": 1234, "slice": "fixture.slice",
                                               "cgroup": "/sys/fs/cgroup/fixture.slice"})
        actual = []
        manager.set_start_guard(lambda execution_id, deliver, **kw: actual.append((execution_id, deliver, kw)))
        from local_hand_jobs import quota_lifecycle
        with mock.patch.object(manager, "support", return_value={"supported": True}), \
             mock.patch.object(runner.os, "readlink", return_value="mnt:[123]"), \
             mock.patch.object(budget, "current_clock", return_value={"boot_id": BOOT,"boottime_ns":3*SECOND}), \
             mock.patch.object(quota_lifecycle, "parent", return_value=({"path":"/fixture.slice","device":4,"inode":81}, True)):
            handle = manager._start(identity, plan, __import__("threading").Event())
        expected = runner._quota_prepared_execution(plan, parent_mount_namespace="mnt:[123]", now_ns=2*SECOND)
        self.assertEqual(expected, handle["execution"])
        self.assertEqual(1, len(actual))
        self.assertEqual("bootstrap", actual[0][2]["stage"])
        self.assertFalse(handle["delivery_attempted"])


class ResidentSequencingTests(unittest.TestCase):
    def fixture(self):
        item = binding_tests.BrokerBindingTests()
        item.setUp()
        self.addCleanup(item.doCleanups)
        return item

    def test_bind_does_not_autotick_until_explicit_start_ack(self):
        item = self.fixture()
        sent = []
        commands = []
        ticks = []

        class Channel:
            sock = object()
            peer = (123, 0, 0)
            def _time(self):
                return None
            def send(self, value):
                sent.append(value)
                if value.get("event") == "prepared":
                    grant = item.grant(value["snapshot"]["preparation"])
                    commands.extend([dict(action="bind", value=grant.as_dict()), dict(action="start", value=None)])
            def receive(self):
                if not commands:
                    raise q.QuotaError("FIXTURE_STOP")
                return commands.pop(0)

        original = item.broker.tick
        def tick():
            ticks.append((len(sent), len(item.runner.starts)))
            return original()
        channel = Channel()
        with mock.patch.object(resident.select, "select", return_value=([channel.sock], [], [])), \
             mock.patch.object(item.broker, "tick", side_effect=tick):
            with self.assertRaisesRegex(q.QuotaError, "FIXTURE_STOP"):
                resident.run_phase(item.broker, item.id, "preflight", channel)
        self.assertEqual([(3, 1)], ticks)
        self.assertEqual(1, len(item.runner.starts))
        self.assertEqual("prepared", sent[0]["event"])
        self.assertEqual(item.broker._quota_session, sent[0]["snapshot"]["preparation"]["session"])

    def test_an_unexpected_command_retains_preparation_without_launch(self):
        item = self.fixture()
        channel = mock.Mock(peer=(123, 0, 0), receive=lambda: {"action":"finish", "value":None})
        with mock.patch.object(resident.select, "select", return_value=([channel.sock], [], [])):
            with self.assertRaises(q.QuotaError):
                resident.run_phase(item.broker, item.id, "preflight", channel)
        self.assertEqual([], item.runner.starts)
        self.assertIn("preflight", item.row()["record"]["quota_preparations"])
        self.assertNotIn("preflight", item.row()["record"]["handles"])


if __name__ == "__main__":
    unittest.main()
