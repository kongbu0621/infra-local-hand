"""Real assembly/contracts with modeled resident transport; no host execution."""
import copy
import hashlib
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

from test_e3_quota_q2_prepare_assembly import a, facts, system_facts, host_module

resident = host_module("q2_resident")


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux isolated fixture")
class AssemblyTests(unittest.TestCase):
    def test_system_cancel_uses_existing_gateway_and_single_phase_contract(self):
        declaration = system_facts()
        declaration["schema"] = a.SYSTEM_CANCEL_SCHEMA
        original = copy.deepcopy(declaration)
        assembled = a.assemble(declaration)
        self.assertEqual(original, declaration)
        self.assertEqual(["preflight"], assembled["resident"]["phases"])
        self.assertEqual(resident.SYSTEM_CANCEL_SCHEMA, assembled["resident"]["schema"])
        self.assertEqual(resident.PHASES, resident.fixture_phases(assembled["resident"]))
        self.assertEqual(declaration["ordinary"]["manager_binding"],
                         assembled["policy"]["process_manager"]["manager_binding"])
        launcher = host_module("q2_launcher")
        raw = launcher.encoded(assembled["launcher"], launcher.LIMIT)
        self.assertEqual(assembled["launcher"], launcher.decode(raw, hashlib.sha256(raw).hexdigest()))
        supervisor = host_module("q2_supervisor")
        raw = supervisor.encoded(assembled["supervisor_template"], supervisor.LIMIT)
        checked = supervisor.decode(raw, supervisor.sha(raw))
        self.assertTrue(supervisor.cancel_fixture(checked))
        self.assertTrue(supervisor.system_fixture(checked))
        review = host_module("q2_evidence_review")
        self.assertTrue(review.cancel_fixture(checked))
        self.assertTrue(review.system_fixture(checked))
        self.assertEqual("CANCEL_CASE_RECORDED", supervisor.expected_status(assembled["launcher"]))
        handoff = host_module("q2_prepare_run")
        handoff.static_template(checked, cancel=True, system=True)
        with self.assertRaisesRegex(ValueError, "TEMPLATE_SCHEMA"):
            handoff.static_template(checked, cancel=True, system=False)
        from local_hand_jobs.policy import Policy
        host_module("q2_fixture_check").cancel_policy_binding(assembled["launcher"], Policy(assembled["policy"]))

    def test_separate_owner_policy_and_single_original_phase(self):
        from admin.local_hand_quota_observer import q2_assembly
        declaration = facts()
        normal = a.assemble(declaration)
        original = copy.deepcopy(declaration)
        declaration["schema"] = a.CANCEL_SCHEMA
        changed = a.assemble(declaration)
        owner = declaration["identity"]["principal_id"]
        self.assertNotIn("lh:cancel", normal["policy"]["principals"][owner]["scopes"])
        self.assertIn("lh:cancel", changed["policy"]["principals"][owner]["scopes"])
        self.assertNotEqual(normal["policy_digest"], changed["policy_digest"])
        self.assertNotEqual(normal["resident"]["request"]["request_digest"],
                            changed["resident"]["request"]["request_digest"])
        self.assertEqual(["preflight"], changed["resident"]["phases"])
        self.assertEqual(resident.PHASES, resident.fixture_phases(changed["resident"]))
        self.assertEqual(original | {"schema": a.CANCEL_SCHEMA}, declaration)
        launcher = host_module("q2_launcher")
        raw = launcher.encoded(changed["launcher"], launcher.LIMIT)
        self.assertEqual(changed["launcher"], launcher.decode(raw, hashlib.sha256(raw).hexdigest()))
        raw = launcher.encoded(changed["launcher"]["assembly"], launcher.LIMIT)
        parsed = q2_assembly.decode(raw, hashlib.sha256(raw).hexdigest()).data()
        self.assertEqual("preflight", parsed["grant"]["request"]["phase"])
        self.assertEqual(original["original_budgets"], parsed["original_budgets"])
        self.assertEqual(original["capacity"], parsed["installation"]["capacity"])
        supervisor = host_module("q2_supervisor")
        raw = supervisor.encoded(changed["supervisor_template"], supervisor.LIMIT)
        self.assertEqual(changed["supervisor_template"], supervisor.decode(raw, hashlib.sha256(raw).hexdigest()))

    def test_cancel_sources_are_required_and_legacy_does_not_select_case(self):
        for missing in ("q4_cancel_case", "q4_cancel_runtime"):
            declaration = facts()
            declaration["schema"] = a.CANCEL_SCHEMA
            declaration["source"]["files"].pop("tests/e3_host/" + missing + ".py", None)
            with self.assertRaisesRegex(ValueError, "PREP_ASSEMBLY_ENTRY"):
                a.assemble(declaration)
        for schema, purpose in ((resident.SCHEMA, "ISOLATED_Q4_CANCEL_HELPER"),
                                (resident.CANCEL_SCHEMA, "ISOLATED_Q2_RESIDENT")):
            with self.assertRaisesRegex(ValueError, "RESIDENT_SCHEMA"):
                resident.fixture_phases(dict(schema=schema, purpose=purpose, phases=["preflight"]))

    def test_resident_case_module_is_fixed_and_digest_checked_before_execution(self):
        path = str(resident.Path(resident.__file__).with_name("q4_cancel_case.py"))
        value = dict(schema=resident.CANCEL_SCHEMA, cancel_case=dict(path=path, sha256="0" * 64))
        with mock.patch.object(resident, "protected", return_value=b"raise AssertionError('executed')"):
            with self.assertRaisesRegex(ValueError, "RESIDENT_CANCEL_DIGEST"):
                resident.load_cancel_case(value)
        value["cancel_case"]["path"] = "/different/q4_cancel_case.py"
        with mock.patch.object(resident, "protected") as read:
            with self.assertRaisesRegex(ValueError, "RESIDENT_CANCEL_ENTRY"):
                resident.load_cancel_case(value)
            read.assert_not_called()


class ResidentTransportTests(unittest.TestCase):
    def test_system_cancel_entry_passes_observer_to_composition_and_case_runner(self):
        from local_hand_jobs import cli, system_manager
        peer = dict(pid=123, uid=0, gid=0, start_ticks=456, boot_id="boot", deadline_ns=100)
        value = dict(schema=resident.SYSTEM_CANCEL_SCHEMA,
            bridge=dict(peer, fd=7), manager_channel=dict(peer, fd=8))
        channel, manager, broker, observer = mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()
        result = dict(schema="local-hand-q4-cancel-resident-result/v1", status="CANCEL_CASE_RECORDED")
        with mock.patch.object(resident, "bootstrap", return_value=value), \
             mock.patch.object(resident, "load_cancel_case", return_value=observer), \
             mock.patch.object(resident, "channel_from_pin", return_value=channel), \
             mock.patch.object(system_manager, "channel_from_pin", return_value=manager), \
             mock.patch.object(resident, "compose", return_value=broker) as compose, \
             mock.patch.object(resident, "run", return_value=result) as run, \
             mock.patch.object(cli, "close_service"), mock.patch.object(resident.os, "write"):
            self.assertEqual(0, resident.main(["--fixture", "private", "--sha256", "digest"]))
        compose.assert_called_once_with(value, cancel_module=observer, manager_channel=manager)
        run.assert_called_once_with(value, channel, broker, cancel_module=observer)
        manager.close.assert_called_once()

    def invoke(self, commands, ready=True):
        from local_hand_jobs import quota_bridge
        case = mock.Mock()
        case.snapshot.return_value = {"ready_for_finish": ready}
        module = SimpleNamespace(Case=mock.Mock(return_value=case))
        channel = mock.Mock(sock=object())
        channel.receive.side_effect = commands
        broker = mock.Mock()
        phase = mock.Mock()
        phase.snapshot.return_value = phase.handle.return_value = {
            "preparation": {}, "observation": None, "pending": None, "closed": None}
        with mock.patch.object(quota_bridge, "Phase", return_value=phase), \
             mock.patch.object(resident.select, "select", return_value=([channel.sock], [], [])):
            result = resident.run_cancel({}, channel, broker, module, "operation", "owner")
        return result, broker, phase, case, channel

    def test_cancel_case_rejects_normal_phase_close_and_retains_diagnostics(self):
        result, broker, phase, case, _ = self.invoke([{"action": "close", "value": {}}])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("RESIDENT_CANCEL_ACTION", result["reason"])
        phase.handle.assert_not_called()
        broker.close_observation.assert_not_called()
        case.close.assert_called_once()
        self.assertIn("case", result)

    def test_finish_requires_original_start_and_recording_completion(self):
        finish = {"action": "finish", "value": None}
        for commands, ready in (([finish], True),
                                ([{"action": "start", "value": None}, finish], False)):
            result, *_ = self.invoke(commands, ready)
            self.assertEqual("INCOMPLETE", result["status"])
            self.assertEqual("RESIDENT_CANCEL_NOT_READY", result["reason"])

    def test_completed_recording_never_claims_phase_closure(self):
        result, broker, phase, _, channel = self.invoke([
            {"action": "bind", "value": {"fixed": "grant"}},
            {"action": "start", "value": None},
            {"action": "snapshot", "value": None},
            {"action": "finish", "value": None}])
        self.assertEqual("CANCEL_CASE_RECORDED", result["status"])
        self.assertFalse(result["production_supported"])
        self.assertNotIn("closure_digest", result)
        broker.close_observation.assert_not_called()
        self.assertEqual(3, phase.handle.call_count)
        self.assertEqual("local-hand-q4-cancel-snapshot/v1", channel.send.call_args.args[0]["schema"])


if __name__ == "__main__":
    unittest.main()
