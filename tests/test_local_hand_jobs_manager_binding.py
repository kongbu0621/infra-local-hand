"""Explicit manager authority; synthetic cgroup facts do not qualify a host."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from local_hand_jobs import manager_binding as binding
from local_hand_jobs.broker import Broker, phase_plan
from local_hand_jobs.cli import _known_manager_units
from local_hand_jobs.contract import JobError
from local_hand_jobs.policy import Policy, freeze
from test_local_hand_jobs_policy import policy_fixture
import test_local_hand_jobs_bootstrap_broker as broker_fixtures


BOOT = "11111111-1111-4111-8111-111111111111"


def manager_fixture():
    value = dict(schema=binding.SCHEMA, manager_kind="system", authority_id="fixture-authority",
                 boot_id=BOOT, parent=dict(path="/lhqfixture.slice/lhqfixture-ordinary.slice", device=4, inode=81))
    return dict(uid=1100, gid=1100, slice="lhqfixture-ordinary.slice",
                cgroup="/sys/fs/cgroup" + value["parent"]["path"], manager_binding=value)


class ManagerBindingTests(unittest.TestCase):
    def test_new_policy_and_frozen_binding_are_explicit_and_detached(self):
        with tempfile.TemporaryDirectory() as directory:
            config = policy_fixture(Path(directory))
            config.update(schema_version="lh-policy-v2", process_manager=manager_fixture())
            policy = Policy(config)
            bound = binding.from_configuration(policy.config["process_manager"], authority_id=policy.authority_id)
            self.assertEqual(bound, config["process_manager"]["manager_binding"])
            bound["parent"]["inode"] += 1
            self.assertNotEqual(bound, binding.from_configuration(policy.config["process_manager"]))

    def test_new_policy_cannot_be_selected_through_legacy_or_partial_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            original = policy_fixture(Path(directory))
            for fault in ("v1_system", "v2_absent", "v2_legacy", "authority", "kind", "gid", "parent", "extra"):
                config = copy.deepcopy(original)
                config.update(schema_version="lh-policy-v2", process_manager=manager_fixture())
                manager = config["process_manager"]
                if fault == "v1_system": config["schema_version"] = "lh-policy-v1"
                elif fault == "v2_absent": config.pop("process_manager")
                elif fault == "v2_legacy":
                    manager.pop("manager_binding"); manager.pop("gid")
                elif fault == "authority": manager["manager_binding"]["authority_id"] = "another-authority"
                elif fault == "kind": manager["manager_binding"]["manager_kind"] = "user"
                elif fault == "gid": manager["gid"] = 0
                elif fault == "parent": manager["cgroup"] = "/sys/fs/cgroup/another.slice"
                else: manager["fallback"] = True
                with self.subTest(fault=fault), self.assertRaises(JobError) as caught:
                    Policy(config)
                self.assertEqual(caught.exception.code, "UNAUTHORIZED")

    def test_changed_and_absent_manager_identity_never_cross_admit(self):
        expected = manager_fixture()["manager_binding"]
        self.assertIsNone(binding.check(None, None))
        for actual in (None, {**expected, "boot_id": "22222222-2222-4222-8222-222222222222"},
                       {**expected, "authority_id": "foreign"},
                       {**expected, "parent": {**expected["parent"], "inode": 82}}):
            with self.subTest(actual=actual), self.assertRaises(JobError):
                binding.check(expected, actual)
        with self.assertRaises(JobError): binding.check(None, expected)
        self.assertEqual(expected, binding.check(expected, freeze(expected)))

    def test_parent_cannot_fake_systemd_slice_hierarchy_or_numeric_identity(self):
        expected = manager_fixture()["manager_binding"]
        for mutation in (dict(path="/lhqfixture.slice/foreign-ordinary.slice"),
                         dict(path="/lhqfixture.slice/lhqfixture-ordinary-extra.slice"),
                         dict(path="/lhqfixture.slice/../lhqfixture-ordinary.slice"),
                         dict(device=True), dict(inode=0), dict(inode=2**63)):
            value = copy.deepcopy(expected); value["parent"].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(JobError): binding.validate(value)

    def test_inventory_requires_the_same_binding_even_when_unit_digest_matches(self):
        expected = manager_fixture()["manager_binding"]
        execution = "job-original-preflight"
        row = dict(namespace="job", id="original", record=dict(handles=dict(preflight=
            dict(execution_id=execution, manager_binding=expected))))
        wanted = "lhj-" + hashlib.sha256(execution.encode()).hexdigest() + ".service"
        self.assertEqual([wanted], _known_manager_units([row], manager_binding=expected))
        for actual in (None, {**expected, "authority_id": "foreign"}):
            altered = copy.deepcopy(row)
            altered["record"]["handles"]["preflight"]["manager_binding"] = actual
            with self.subTest(actual=actual), self.assertRaises(JobError):
                _known_manager_units([altered], manager_binding=expected)
        with self.assertRaises(JobError): _known_manager_units([row])
        row["record"]["handles"]["preflight"]["manager"] = {"version": 1,
            "helper": {"manager_binding": {**expected, "boot_id": "22222222-2222-4222-8222-222222222222"}}}
        with self.assertRaises(JobError): _known_manager_units([row], manager_binding=expected)


class BrokerManagerBindingTests(unittest.TestCase):
    def fixture(self):
        case = broker_fixtures.BootstrapBrokerTests(); case.setUp()
        self.addCleanup(case.doCleanups)
        config = manager_fixture()
        case.f.policy.config = {"process_manager": config}
        case.f.policy.authority_id = config["manager_binding"]["authority_id"]
        case.broker = Broker(case.f.db, case.f.policy, broker_fixtures.BootstrapRegistry(), case.runner)
        case.f.broker = case.broker
        original = case.runner.start
        def start(parent, execution, plan):
            returned = original(parent, execution, plan)
            return dict(returned, manager_binding=copy.deepcopy(plan["manager_binding"]))
        case.runner.start = start
        return case, config["manager_binding"]

    def test_lost_first_ack_retains_manager_binding_before_any_launch_reply(self):
        case, expected = self.fixture()
        original = case.runner.start
        def lost(parent, execution, plan):
            original(parent, execution, plan)
            raise JobError("IO_UNCERTAIN", "Synthetic lost first acknowledgement")
        case.runner.start = lost
        case.start()
        handle = case.row()["record"]["handles"]["preflight"]
        self.assertTrue(handle["intent_only"])
        self.assertEqual(expected, handle["manager_binding"])
        self.assertEqual(expected, case.runner.starts[0][2]["manager_binding"])
        self.assertEqual(3, len(_known_manager_units([case.row()], manager_binding=expected)))
        self.assertEqual("UNKNOWN", case.row()["record"]["outcome"])
        with case.f.db.transaction() as tx:
            self.assertTrue(tx.execute("SELECT count(*) FROM leases").fetchone()[0])

    def test_durable_returned_identity_and_guard_cannot_switch_authority(self):
        case, expected = self.fixture()
        execution = case.start()
        self.assertEqual(expected, case.row()["record"]["handles"]["preflight"]["manager_binding"])
        with case.f.db.transaction() as tx:
            row = case.f.db.get("job", case.f.request["operation_id"], tx)
            handles = copy.deepcopy(row["record"]["handles"])
            handles["preflight"]["manager_binding"]["authority_id"] = "foreign"
            case.f.db.update(tx, "job", case.f.request["operation_id"], "SYNTHETIC_BINDING_FAULT", {"handles": handles})
        with self.assertRaises(JobError): case.deliver(execution, "bootstrap")
        self.assertEqual([], case.runner.delivered)
        with self.assertRaises(JobError): case.broker.recover()
        self.assertEqual(1, len(case.runner.starts))

    def test_phase_declaration_binds_original_grant_boot_without_altering_legacy(self):
        case, expected = self.fixture(); case.start()
        row = case.row(); grant = case.runner.starts[0][2]["budget_grant"]
        legacy = phase_plan(row, "preflight", grant)
        self.assertNotIn("manager_binding", legacy)
        current = phase_plan(row, "preflight", grant, manager_binding=expected)
        self.assertEqual(expected, current.pop("manager_binding"))
        self.assertEqual(legacy, current)
        with self.assertRaises(JobError):
            phase_plan(row, "preflight", {**grant, "boot_id": "22222222-2222-4222-8222-222222222222"},
                       manager_binding=expected)

    def test_changed_recovery_receipt_cannot_overwrite_intent_or_release_resources(self):
        case, expected = self.fixture(); execution = case.start()
        original = copy.deepcopy(case.row()["record"]["handles"])
        case.runner.finish(execution, recovery_handle={"manager_binding": {**expected, "authority_id": "foreign"}})
        case.broker.tick()
        current = case.row()["record"]
        self.assertEqual(original, current["handles"])
        self.assertEqual("UNKNOWN", current["outcome"])
        self.assertEqual(1, len(case.broker._active))
        with case.f.db.transaction() as tx:
            self.assertTrue(tx.execute("SELECT count(*) FROM leases").fetchone()[0])


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux pipe lifecycle")
class LifecycleManagerBindingTests(unittest.TestCase):
    def fixture(self):
        from test_local_hand_jobs_quota_lifecycle import LifecycleTests
        case = LifecycleTests(); self.addCleanup(case.doCleanups)
        part, properties, manager, calls = case.setup_part()
        config = manager_fixture(); config["manager_binding"]["boot_id"] = part["boot_id"]
        bound = config["manager_binding"]
        part.update(manager_binding=copy.deepcopy(bound), quota_parent=copy.deepcopy(bound["parent"]),
                    cgroup_parent=config["cgroup"])
        properties["ControlGroup"] = bound["parent"]["path"] + "/" + part["unit"]
        manager.configuration = config
        return part, properties, manager, calls

    def test_system_proof_keeps_real_original_pipe_and_stop_requirements(self):
        from local_hand_jobs import quota_lifecycle as life, runner
        part, _, manager, calls = self.fixture()
        self.assertEqual("UNKNOWN", life.observe(manager, part, runner._unknown)["state"])
        self.assertEqual("EXITED", life.observe(manager, part, runner._unknown)["state"])
        self.assertEqual(1, sum(args[0] == "stop" for args in calls))
        self.assertEqual({"stdout", "stderr"}, part["quota_transport"].eof)

    def test_binding_is_checked_before_cached_proof_pipe_reads_or_manager_calls(self):
        from local_hand_jobs import quota_lifecycle as life, runner
        for fault in ("missing", "legacy_manager", "authority", "boot", "parent", "cached"):
            with self.subTest(fault=fault):
                part, _, manager, calls = self.fixture()
                if fault == "missing": part.pop("manager_binding")
                elif fault == "legacy_manager": manager.configuration = {}
                elif fault == "authority": part["manager_binding"]["authority_id"] = "foreign"
                elif fault == "boot":
                    manager.configuration["manager_binding"]["boot_id"] = "22222222-2222-4222-8222-222222222222"
                    part["manager_binding"] = copy.deepcopy(manager.configuration["manager_binding"])
                elif fault == "parent": part["quota_parent"]["inode"] += 1
                else:
                    part["quota_final"] = dict(state="EXITED")
                    part["manager_binding"]["authority_id"] = "foreign"
                with mock.patch.object(part["quota_transport"], "pump") as pump, self.assertRaises(JobError):
                    life.observe(manager, part, runner._unknown)
                pump.assert_not_called(); self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
