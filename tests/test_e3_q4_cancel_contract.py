"""Fixed Q4 contract checks; no real systemd, cgroup or quota acceptance.

The existing test fixtures model all host authority. Files and any inherited
outer-capture fixture are test evidence only, never a runnable host fixture.
"""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]


def host_module(name):
    spec = importlib.util.spec_from_file_location("_q4_contract_" + name, ROOT / "tests/e3_host" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s = host_module("q2_supervisor")
r = host_module("q2_evidence_review")
c = host_module("q2_fixture_check")


def minimal(cancel=True):
    return dict(schema=s.CANCEL_SCHEMA if cancel else s.SCHEMA,
                purpose=s.CANCEL_PURPOSE if cancel else "ISOLATED_Q2_SUPERVISION",
                launcher=dict(schema=s.CANCEL_LAUNCHER if cancel else "local-hand-q2-launcher/v2",
                              purpose=s.CANCEL_PURPOSE if cancel else "ISOLATED_Q2_CHAIN"),
                controller_parent={}, supervisor_envelope={}, output={}, declarations={})


def modeled_cancel_result(value):
    """An explicitly unexercised modeled report, with no manager or task start."""
    value.update(schema=s.CANCEL_SCHEMA, purpose=s.CANCEL_PURPOSE)
    nested = value["launcher"]
    nested.update(schema=s.CANCEL_LAUNCHER, purpose=s.CANCEL_PURPOSE)
    resident = nested["resident"]
    operation = "12345678-1234-4234-9234-123456789abc"
    from local_hand_jobs import bootstrap_roots
    allocation = nested["assembly"]["grant"]["allocation"]
    allocation.update(operation_id=operation, record_id=operation, execution_id="job-" + operation + "-preflight")
    allocation["allocation_id"] = bootstrap_roots._allocation_id(
        "job", operation, allocation["slot_id"], allocation["roots"], allocation["paths"])
    allocation["grant_digest"] = bootstrap_roots._digest({key: val for key, val in allocation.items() if key != "grant_digest"})
    nested["assembly"]["grant"]["request"].update(execution_id=allocation["execution_id"], allocation_digest=allocation["allocation_id"])
    principal = SimpleNamespace(principal_id="q2-synthetic-cancel")
    request = dict(operation_id=operation, request_digest="a" * 64, kind="host.inspect", inputs={})
    relative = "tests/e3_host/q4_cancel_case.py"
    checksum = r.digest((ROOT / relative).read_bytes())
    nested["source"] = dict(commit="c" * 40, files={relative: checksum})
    resident.update(schema="local-hand-q4-cancel-resident/v1", purpose=s.CANCEL_PURPOSE,
                    phases=["preflight"], request=request, principal=dict(principal_id=principal.principal_id),
                    cancel_case=dict(path=str(ROOT / relative), sha256=checksum))
    resident["entry"] = dict(path=str(ROOT / "tests/e3_host/q2_resident.py"))
    row = dict(principal=principal.principal_id, request=request, digest=request["request_digest"],
               record=dict(cancel_requested=False, lifecycle="UNKNOWN", outcome="UNKNOWN", evidence="NONE", phase="PREFLIGHT"))
    broker = SimpleNamespace(state=SimpleNamespace(get=lambda *_: row), policy=SimpleNamespace(authorize=lambda *a, **k: None))
    contract = r.case_contract()
    clock = dict(boot_id=nested["assembly"]["installation"]["capacity"]["boot_id"],
                 boottime_ns=nested["controller_envelope"]["issued_ns"] + 1)
    with mock.patch.object(contract, "_clock", return_value=clock):
        report = contract.Case(broker, operation, principal).snapshot()
    report.update(status="NOT_EXERCISED", ready_for_finish=True, completion_reason="CLOSED")
    if contract.validate_report(report): raise AssertionError(contract.validate_report(report))
    return dict(schema="local-hand-q4-cancel-launcher-result/v1", status="CANCEL_CASE_RECORDED",
                q3_accepted=False, production_supported=False, independent_controller_stop_required=True,
                ordinary_phase_closed=False, independent_ordinary_cleanup_required=True, case=report)


class SchemaTests(unittest.TestCase):
    def test_cancellation_has_its_own_wrapper_status_and_evidence_schemas(self):
        value = minimal()
        raw = s.encoded(value, s.LIMIT)
        self.assertEqual(value, s.decode(raw, s.sha(raw)))
        self.assertTrue(r.cancel_fixture(value))
        self.assertEqual("CANCEL_CASE_RECORDED", s.expected_status(value["launcher"]))
        for name in ("controller-result", "supervisor-result", "controller-seal"):
            self.assertEqual("local-hand-q4-cancel-" + name + "/v1", s.record_schema(value, name))

    def test_legacy_and_cancellation_wrappers_cannot_be_mixed_in_either_direction(self):
        for cancel in (True, False):
            value = minimal(cancel)
            value["launcher"] = minimal(not cancel)["launcher"]
            raw = s.encoded(value, s.LIMIT)
            with self.subTest(cancel=cancel), self.assertRaisesRegex(ValueError, "SCENARIO_BINDING"):
                s.decode(raw, s.sha(raw))
            with self.subTest(offline=cancel), self.assertRaisesRegex(ValueError, "SCENARIO_BINDING"):
                r.cancel_fixture(value)

    def test_purpose_and_version_are_not_success_overrides(self):
        for key, value in (("purpose", "ISOLATED_Q2_SUPERVISION"), ("schema", "local-hand-q4-cancel-supervisor/v2")):
            record = minimal(); record[key] = value
            raw = s.encoded(record, s.LIMIT)
            with self.subTest(key=key), self.assertRaises(ValueError):
                s.decode(raw, s.sha(raw))
        record = minimal(); record["launcher"]["purpose"] = "ISOLATED_Q2_CHAIN"
        with self.assertRaises(ValueError): s.expected_status(record["launcher"])


@unittest.skipUnless(sys.platform.startswith("linux"), "Modeled Linux fixture declarations")
class GeometryTests(unittest.TestCase):
    def setUp(self):
        from test_e3_quota_q2_supervisor import fixture, launcher, BOOT, SECOND
        self.value = fixture(); self.launcher = launcher
        self.clock = dict(boot_id=BOOT, boottime_ns=2 * SECOND)

    def cancellation(self):
        value = copy.deepcopy(self.value)
        value.update(schema=s.CANCEL_SCHEMA, purpose=s.CANCEL_PURPOSE)
        value["launcher"].update(schema=s.CANCEL_LAUNCHER, purpose=s.CANCEL_PURPOSE)
        return value

    def test_single_original_grant_and_additional_report_buffer_are_charged(self):
        ordinary = s.validate(self.value, self.launcher, self.clock)
        value = self.cancellation()
        with mock.patch.object(s, "admit", side_effect=AssertionError("host operation")):
            cancel = s.validate(value, self.launcher, self.clock)
        self.assertEqual(1, len(s.templates(value["launcher"])))
        for key in ordinary["totals"]:
            increment = s.PIPE_LIMIT - 4096 if key == "output_bytes" else 0
            self.assertEqual(ordinary["totals"][key] + increment, cancel["totals"][key])

    def test_normal_chain_declaration_cannot_be_reinterpreted_as_single_cancel_grant(self):
        from test_e3_quota_q2_chain import declaration_chain
        value = self.cancellation(); value["launcher"]["assembly"] = declaration_chain()[0]
        with self.assertRaises(ValueError): s.templates(value["launcher"])

    def test_cancellation_cannot_ignore_outer_capacity_or_original_identity(self):
        value = self.cancellation()
        baseline = s.validate(value, self.launcher, self.clock)
        cap = value["launcher"]["assembly"]["installation"]["capacity"]
        cap["management"]["output_bytes"] = baseline["totals"]["output_bytes"] - 1
        from local_hand_jobs import quota_grant
        value["launcher"]["assembly"]["grant"]["management"]["capacity_digest"] = quota_grant.digest(cap)
        with self.assertRaisesRegex(ValueError, "SUPERVISOR_COMBINED_CAPACITY"):
            s.validate(value, self.launcher, self.clock)
        value = self.cancellation()
        value["launcher"]["controller_envelope"]["controller"]["invocation_id"] = "c" * 32
        with self.assertRaisesRegex(ValueError, "SUPERVISOR_STATIC_CONTROLLER"):
            s.validate(value, self.launcher, self.clock)

    def test_case_decoder_binds_request_owner_boot_and_fixed_module_without_reading_artifact_paths(self):
        value = self.cancellation(); result = modeled_cancel_result(value)
        with mock.patch.object(r, "case_contract", return_value=r.case_contract()):
            self.assertEqual("NOT_EXERCISED", r.cancel_case_facts(result, value)["status"])
            for key, bad in (("request_digest", "b" * 64), ("principal_id", "q2-synthetic-other"),
                             ("boot_id", "changed-boot")):
                changed = copy.deepcopy(result); changed["case"][key] = bad
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "REVIEW_CANCEL_BINDING"):
                    r.cancel_case_facts(changed, value)
        value["launcher"]["resident"]["cancel_case"]["path"] = "/evidence/untrusted.py"
        with mock.patch.object(r, "case_contract", side_effect=AssertionError("must reject before decoder")), \
             self.assertRaisesRegex(ValueError, "REVIEW_CANCEL_SOURCE"):
            r.cancel_case_facts(result, value)

    def test_case_record_never_substitutes_for_helper_exit_or_phase_closure(self):
        value = self.cancellation(); result = modeled_cancel_result(value)
        for mutate in (lambda item: item.update(ordinary_phase_closed=True),
                       lambda item: item["case"].update(helper_exit_proven=True),
                       lambda item: item["case"].update(status="EXERCISED"),
                       lambda item: item["case"].update(ready_for_finish=False)):
            changed = copy.deepcopy(result); mutate(changed)
            with self.assertRaises(ValueError): r.cancel_case_facts(changed, value)
        report = c.Report(); report.cancel = True; report.probe("snapshot", lambda: None)
        checked = report.result()
        self.assertEqual("local-hand-q4-cancel-fixture-check/v1", checked["schema"])
        self.assertIn("normal_chain_acceptance", checked["future_admission_required"])
        self.assertFalse(checked["q3_accepted"])


@unittest.skipUnless(sys.platform.startswith("linux"), "Modeled controller with retained local files")
class RetainedCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_e3_quota_q2_evidence_review as old
        cls.seed_model = type("Seed", (), {"chain": False})
        old.RetainedReviewTests.setUpClass.__func__(cls.seed_model)

    @classmethod
    def tearDownClass(cls):
        cls.seed_model.seed.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ("output", "declarations"):
            shutil.copytree(Path(self.seed_model.seed.name) / name, self.root / name)
        value = self.read("supervisor.json", "declarations")
        case_result = modeled_cancel_result(value)
        fixture_sha = r.digest(r.encoded(value))
        self.write("supervisor.json", value, "declarations")
        reservation = self.read("reservation.json")
        reservation.update(schema=s.CANCEL_SCHEMA, fixture_sha256=fixture_sha)
        reservation["capacity_costs"]["output_bytes"] += s.PIPE_LIMIT - 4096
        self.write("reservation.json", reservation)
        delivery = self.read("delivery.json")
        delivery["argv_sha256"] = r.delivery_digest(value, fixture_sha, cpu_quota_format=delivery["cpu_quota_format"])
        self.write("delivery.json", delivery)
        marker = self.read("controller-result.json")
        marker.update(schema=s.record_schema(value, "controller-result"), fixture_sha256=fixture_sha, result=case_result)
        self.write("controller-result.json", marker)
        self.write("controller-result.json", marker, "declarations")
        nested = copy.deepcopy(value["launcher"])
        nested["controller_envelope"]["controller"].update({key: marker["controller"][key] for key in s.DYNAMIC})
        self.write("launcher.json", nested, "declarations")
        summary = {key: case_result[key] for key in ("schema", "status", "q3_accepted", "production_supported",
                                                   "independent_controller_stop_required")}
        stdout = r.encoded(summary); (self.root / "output/controller.stdout").write_bytes(stdout)
        capture = self.read("capture.json"); capture["stdout_sha256"] = r.digest(stdout)
        self.write("capture.json", capture)
        result = self.read("result.json")
        result.update(schema=s.record_schema(value, "supervisor-result"), launcher_status="CANCEL_CASE_RECORDED")
        self.write("result.json", result)
        seal = self.read("seal.json")
        seal.update(schema=s.record_schema(value, "controller-seal"), fixture_sha256=fixture_sha)
        self.write("seal.json", seal)
        self.reseal()

    def read(self, name, group="output"):
        return json.loads((self.root / group / name).read_bytes())

    def write(self, name, value, group="output"):
        (self.root / group / name).write_bytes(r.encoded(value))

    def reseal(self):
        """Pin modeled bytes so semantic rejection cannot rely on hash drift."""
        value = self.read("supervisor.json", "declarations"); seal = self.read("seal.json")
        seal["files"] = {value[group]["path"] + "/" + name: dict(bytes=len(raw), sha256=r.digest(raw))
            for group, names in (("output", r.OUTPUT), ("declarations", r.DECLARATIONS))
            for name in names for raw in [(self.root / group / name).read_bytes()]}
        self.write("seal.json", seal)
        self.expected = r.digest(r.encoded(seal))

    def review(self):
        return r.review(str(self.root / "output"), str(self.root / "declarations"), self.expected)

    def test_sealed_unexercised_case_is_only_a_record_not_a_stopped_job(self):
        result = self.review()
        self.assertEqual("OFFLINE_ARTIFACTS_CONSISTENT", result["status"])
        self.assertEqual("local-hand-q4-cancel-offline-evidence-review/v1", result["schema"])
        self.assertEqual("NOT_EXERCISED", result["cancellation_case_status"])
        self.assertFalse(result["helper_exit_proven"]); self.assertFalse(result["ordinary_phase_closed"])
        self.assertTrue(result["independent_ordinary_cleanup_required"])
        self.assertFalse(result["q3_accepted"]); self.assertFalse(result["host_provenance_proven"])
        self.assertEqual(13, result["sealed_members"])

    def test_resealed_outer_success_cannot_hide_case_identity_drift(self):
        marker = self.read("controller-result.json"); marker["result"]["case"]["request_digest"] = "b" * 64
        self.write("controller-result.json", marker); self.write("controller-result.json", marker, "declarations")
        self.reseal()
        with self.assertRaisesRegex(ValueError, "REVIEW_CANCEL_BINDING"): self.review()

    def test_cancellation_does_not_relax_independent_controller_stop(self):
        stop = self.read("stop.json"); stop["complete"] = False
        self.write("stop.json", stop); self.reseal()
        with self.assertRaisesRegex(ValueError, "REVIEW_STOP_INCOMPLETE"): self.review()


@unittest.skipUnless(sys.platform.startswith("linux"), "Pure policy binding with modeled host inputs")
class PolicyBindingTests(unittest.TestCase):
    def setUp(self):
        from test_e3_quota_q2_prepare_assembly import a, facts
        from local_hand_jobs.policy import Policy
        self.facts = facts(); self.facts["schema"] = a.CANCEL_SCHEMA
        assembled = a.assemble(self.facts)
        self.value = assembled["supervisor_template"]
        self.nested = self.value["launcher"]
        self.policy = Policy(assembled["policy"])

    def resign_allocation(self):
        from local_hand_jobs import bootstrap_roots as b
        allocation = self.nested["assembly"]["grant"]["allocation"]
        allocation["allocation_id"] = b._allocation_id(allocation["namespace"], allocation["record_id"],
            allocation["slot_id"], allocation["roots"], allocation["paths"])
        allocation["grant_digest"] = b._digest({key: value for key, value in allocation.items() if key != "grant_digest"})

    def test_fixed_case_pin_and_policy_binding_are_admitted_without_runtime_io(self):
        c.cancel_policy_binding(self.nested, self.policy)
        repository = Path(self.facts["source"]["root"])
        with mock.patch.object(c, "protected", return_value=(ROOT / "tests/e3_host/q4_cancel_case.py").read_bytes()):
            self.assertEqual(1, len(c.static_binding(self.value, s, repository)))
            self.nested["resident"]["cancel_case"]["sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "FIXTURE_CANCEL_SOURCE"):
                c.static_binding(self.value, s, repository)

    def test_resigned_wrong_slot_and_wrong_inode_do_not_pass_read_only_admission(self):
        original = copy.deepcopy(self.nested)
        for fault in ("slot", "inode"):
            self.nested = copy.deepcopy(original)
            allocation = self.nested["assembly"]["grant"]["allocation"]
            if fault == "slot": allocation["slot_id"] = "slot-b"
            else: next(iter(allocation["paths"].values()))["inode"] += 1000
            self.resign_allocation()
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, "FIXTURE_CANCEL_POLICY_ROOTS"):
                c.cancel_policy_binding(self.nested, self.policy)

    def test_wrong_root_owner_or_ungranted_principal_cannot_become_checked(self):
        from local_hand_jobs.contract import JobError
        self.nested["assembly"]["grant"]["roots"][0]["uid"] += 1
        with self.assertRaisesRegex(ValueError, "FIXTURE_CANCEL_ROOT_OWNER"):
            c.cancel_policy_binding(self.nested, self.policy)
        self.nested["assembly"]["grant"]["roots"][0]["uid"] -= 1
        self.nested["resident"]["principal"]["principal_id"] = "q2-synthetic-other"
        with self.assertRaises(JobError): c.cancel_policy_binding(self.nested, self.policy)

    def test_case_cannot_add_retained_store_or_change_the_fixed_request(self):
        from local_hand_jobs.contract import JobError
        allocation = self.nested["assembly"]["grant"]["allocation"]
        store = self.facts["store"]
        allocation["retained_paths"] = [store["path"]]
        allocation["paths"][store["path"]] = {key: store[key] for key in ("device", "inode", "uid")}
        self.resign_allocation()
        with self.assertRaises(JobError): c.cancel_policy_binding(self.nested, self.policy)
        self.nested["resident"]["request"]["inputs"] = {"argv": ["anything"]}
        with self.assertRaises(JobError): c.cancel_policy_binding(self.nested, self.policy)


if __name__ == "__main__":
    unittest.main()
