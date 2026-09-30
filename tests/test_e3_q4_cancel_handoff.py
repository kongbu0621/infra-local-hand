"""Fixed-cancel owner contracts and original pipes; no host services or quotas.

The assembly uses explicitly modeled host facts and the real policy/planner.
The client cases reuse real local pipes with modeled systemd identity/stop.
"""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import test_e3_quota_q2_prepare_run as base
from test_e3_quota_q2_prepare_assembly import a, facts

r = base.r


def plan():
    observed = facts()
    observed["schema"] = a.CANCEL_SCHEMA
    assembled = a.assemble(observed)
    value = base.plan()
    value.update(schema=r.CANCEL_SCHEMA, purpose=r.CANCEL_PURPOSE,
                 preparation_id=observed["identity"]["id"], template=assembled["supervisor_template"],
                 supervisor_parent=assembled["supervisor_parent"])
    return value


def child_result():
    return dict(schema="local-hand-q4-cancel-supervisor-result/v1", status="CONTROLLER_CLOSED",
        scope="TARGET_CONTROLLER_CLOSURE_ONLY", seal_required=True, sealed=True,
        controller_stopped=True, launcher_status="CANCEL_CASE_RECORDED",
        q3_accepted=False, production_supported=False, independent_supervisor_stop_required=True)


@unittest.skipUnless(sys.platform.startswith("linux"), "Modeled Linux assembly and controller identity")
class ContractTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan()
        self.now = dict(boot_id=base.BOOT, boottime_ns=2 * base.SECOND)

    def issue(self):
        return r.issue(self.plan, base.s, self.now)

    def test_real_cancel_assembly_reaches_existing_owner_binding(self):
        original = copy.deepcopy(self.plan)
        raw = r.encoded(self.plan, r.LIMIT)
        self.assertEqual(self.plan, r.decode(raw, r.sha(raw)))
        issued = self.issue()
        self.assertEqual("local-hand-q4-cancel-issued-handoff/v1", issued["schema"])
        encoded = r.encoded(issued, r.LIMIT)
        self.assertEqual(issued, r.envelope(encoded, r.sha(encoded), base.s))
        with mock.patch.object(base.budget, "current_clock", return_value=self.now):
            bound = r.binding(issued, base.s, base.launcher)
        self.assertEqual(bound["totals"]["output_bytes"] + 69632, bound["costs_with_owner"]["output_bytes"])
        self.assertEqual(original, self.plan)
        self.assertEqual(1, len(base.s.templates(issued["fixture"]["launcher"])))
        self.assertEqual(["preflight"], issued["fixture"]["launcher"]["resident"]["phases"])

    def test_plan_template_launcher_resident_cannot_mix_families(self):
        for path, replacement in (
            (("schema",), r.SCHEMA), (("purpose",), "ONE_ORIGINAL_Q2_HANDOFF"),
            (("template", "schema"), "local-hand-q2-supervisor/v1"),
            (("template", "purpose"), "ISOLATED_Q2_SUPERVISION"),
            (("template", "launcher", "schema"), "local-hand-q2-launcher/v2"),
            (("template", "launcher", "purpose"), "ISOLATED_Q2_CHAIN"),
            (("template", "launcher", "resident", "schema"), "local-hand-q2-resident/v2"),
            (("template", "launcher", "resident", "purpose"), "ISOLATED_Q2_CHAIN"),
            (("template", "launcher", "resident", "phases"), ["preflight", "business", "evidence"]),
        ):
            value = copy.deepcopy(self.plan)
            target = value
            for key in path[:-1]: target = target[key]
            target[path[-1]] = replacement
            raw = r.encoded(value, r.LIMIT)
            with self.subTest(path=path), self.assertRaises(ValueError): r.decode(raw, r.sha(raw))
        value = base.plan(); value["template"] = self.plan["template"]
        raw = r.encoded(value, r.LIMIT)
        with self.assertRaisesRegex(ValueError, "HANDOFF_TEMPLATE_SCHEMA"): r.decode(raw, r.sha(raw))

    def test_issued_envelope_cannot_change_family_time_or_target(self):
        for mutation in ("schema", "plan", "deadline", "target", "resident"):
            value = self.issue()
            if mutation == "schema": value["schema"] = r.ENVELOPE_SCHEMA
            if mutation == "plan": value["plan"] = base.plan()
            if mutation == "deadline": value["fixture"]["supervisor_envelope"]["deadline_ns"] += 1
            if mutation == "target": value["fixture"]["launcher"]["controller_envelope"]["controller"]["tasks_max"] += 1
            if mutation == "resident": value["fixture"]["launcher"]["resident"]["phases"] = ["preflight", "business"]
            raw = r.encoded(value, r.LIMIT)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): r.envelope(raw, r.sha(raw), base.s)

    def test_original_time_owner_ceiling_and_cleanup_margins_remain_strict(self):
        for mutation in ("duration", "issued", "identity", "margin", "expired", "capacity"):
            self.plan = plan()
            if mutation == "duration": self.plan["owner_envelope"]["deadline_ns"] = 122 * base.SECOND
            if mutation == "issued": self.plan["template"]["supervisor_envelope"]["issued_ns"] = base.SECOND
            if mutation == "identity": self.plan["template"]["supervisor_envelope"]["controller"]["invocation_id"] = "a" * 32
            if mutation == "margin": self.plan["template"]["supervisor_envelope"]["controller"]["runtime_max_usec"] = 119_000_000
            if mutation == "expired": self.now["boottime_ns"] = 120 * base.SECOND
            if mutation == "capacity": self.plan["owner_envelope"]["memory_bytes"] = 1024**3
            raw = r.encoded(self.plan, r.LIMIT)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                checked = r.decode(raw, r.sha(raw))
                with mock.patch.object(base.budget, "current_clock", return_value=self.now):
                    r.clock(checked)
                    r.binding(self.issue(), base.s, base.launcher)
            self.now["boottime_ns"] = 2 * base.SECOND

    def test_child_schema_and_closure_cannot_assert_normal_chain_or_full_acceptance(self):
        r.cancel_child_result(self.plan, child_result())
        with self.assertRaisesRegex(ValueError, "HANDOFF_CHILD_SCENARIO"):
            r.cancel_child_result(base.plan(), child_result())
        for key, value in (("schema", "local-hand-q2-supervisor-result/v1"),
                           ("scope", "ALL_CLOSED"), ("seal_required", False),
                           ("launcher_status", "CHAIN_CLOSED"), ("controller_stopped", False),
                           ("q3_accepted", True), ("production_supported", True),
                           ("independent_supervisor_stop_required", False)):
            result = child_result(); result[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): r.cancel_child_result(self.plan, result)

    def test_child_marker_binds_family_original_identity_and_exact_bound_fixture(self):
        value = self.issue()
        original = dict(invocation_id="b" * 32, pid=1234, cgroup_device=70, cgroup_inode=999)
        bound = copy.deepcopy(value["fixture"])
        bound["supervisor_envelope"]["controller"].update({key: original[key] for key in r.DYNAMIC})
        valid = dict(schema="local-hand-q4-cancel-supervisor-handoff-result/v1",
            envelope_sha256=r.sha(r.encoded(value, r.LIMIT)), original=original, result=child_result(),
            completed_ns=3 * base.SECOND, bound_fixture_sha256=r.sha(r.encoded(bound, r.LIMIT)))
        with mock.patch.object(base.launcher, "protected", return_value=r.encoded(valid)):
            self.assertEqual(valid, r.marker(value, original, base.launcher))
        for mutation in ("schema", "nested", "identity", "bound", "envelope", "deadline"):
            item = copy.deepcopy(valid)
            if mutation == "schema": item["schema"] = "local-hand-q2-supervisor-handoff-result/v1"
            if mutation == "nested": item["result"]["schema"] = "local-hand-q2-supervisor-result/v1"
            if mutation == "identity": item["original"]["pid"] += 1
            if mutation == "bound": item["bound_fixture_sha256"] = "f" * 64
            if mutation == "envelope": item["envelope_sha256"] = "f" * 64
            if mutation == "deadline": item["completed_ns"] = value["fixture"]["supervisor_envelope"]["deadline_ns"]
            with self.subTest(mutation=mutation), mock.patch.object(base.launcher, "protected", return_value=r.encoded(item)), self.assertRaises(ValueError):
                r.marker(value, original, base.launcher)

    def test_cancel_source_loader_rechecks_existing_owner_entry_bytes(self):
        template = self.plan["template"]
        def raw(path): return Path(path).read_bytes()
        with mock.patch.object(r, "protected", side_effect=raw), \
             mock.patch.object(r, "sha", return_value="bad"), \
             self.assertRaisesRegex(ValueError, "HANDOFF_SOURCE_DIGEST"):
            r.modules(template, base.PATH.parents[2])

    def test_bound_failure_after_validation_retains_cancel_family_and_diagnostic(self):
        issued = self.issue()
        with mock.patch.object(r.sys, "flags", SimpleNamespace(isolated=1)), \
             mock.patch.object(r.sys, "dont_write_bytecode", True), \
             mock.patch.object(r, "protected", return_value=r.encoded(issued, r.LIMIT)), \
             mock.patch.object(r, "modules", return_value=(base.s, mock.Mock(), base.launcher)), \
             mock.patch.object(r, "bound_role", side_effect=PermissionError(13, "private details")), \
             mock.patch("builtins.print") as output:
            raw = r.encoded(issued, r.LIMIT)
            self.assertEqual(3, r.main(["--bind", "--envelope", "/private/envelope", "--sha256", r.sha(raw)]))
        result = json.loads(output.call_args.args[0])
        self.assertEqual("local-hand-q4-cancel-handoff-result/v1", result["schema"])
        self.assertEqual("bound_role", result["diagnostic"]["stage"])
        self.assertTrue(result["independent_ordinary_cleanup_required"])
        self.assertFalse(result["ordinary_phase_closed"])
        self.assertFalse(result["owner_self_exit_verified"])
        self.assertNotIn("private", output.call_args.args[0])


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux same-process identity model")
class SamePidTests(base.SamePidTests):
    def setUp(self):
        super().setUp()
        self.plan = plan()
        self.value = r.issue(self.plan, base.s, self.now)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux original anonymous pipes")
class ClientTests(base.OriginalClientTests):
    def setUp(self):
        super().setUp()
        original = self.plan
        self.plan = plan()
        for key in ("output", "declarations", "owner_envelope"):
            self.plan[key] = original[key]

    def test_cancel_seal_and_all_owner_records_keep_their_family_and_limits(self):
        result = self.run_model()
        self.assertEqual("SUPERVISOR_CLOSED", result["status"], result)
        output = Path(self.plan["output"]["path"])
        seal = json.loads((output / "seal.json").read_bytes())
        persisted = json.loads((output / "result.json").read_bytes())
        reservation = json.loads((output / "reservation.json").read_bytes())
        self.assertEqual(r.CANCEL_SCHEMA, reservation["schema"])
        self.assertEqual("local-hand-q4-cancel-handoff-result/v1", result["schema"])
        self.assertEqual(result["schema"], persisted["schema"])
        self.assertEqual("local-hand-q4-cancel-handoff-seal/v1", seal["schema"])
        self.assertEqual(r.CANCEL_PURPOSE, result["scope"])
        for record in (result, persisted, seal):
            for flag in ("ordinary_phase_closed", "q2_accepted", "q3_accepted", "production_supported", "owner_self_exit_verified"):
                self.assertIs(False, record[flag])
            self.assertIs(True, record["independent_ordinary_cleanup_required"])
            self.assertIs(True, record["original_management_session_exit_required"])

    def test_legacy_stdout_cannot_complete_cancel_handoff(self):
        original = r.child_summary
        def summary(selected, status):
            if self.processes:
                return original(selected, status)
            return dict(schema=r.RESULT_SCHEMA, status=status, q3_accepted=False, production_supported=False)
        with mock.patch.object(r, "child_summary", side_effect=summary):
            result = self.run_model()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertFalse(result["sealed"])
        self.assertEqual("HANDOFF_SUPERVISOR_NOT_CLOSED", result["primary_reason"])


if __name__ == "__main__":
    unittest.main()
