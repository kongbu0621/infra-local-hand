"""Real registry/persistence/phase transforms; quota observations are synthetic."""
import copy
import tempfile
from pathlib import Path
import unittest

from local_hand_jobs import bootstrap_roots, local_a2_jobs as a2, runner
from local_hand_jobs.broker import phase_plan
from local_hand_jobs.contract import Principal, TOOL_SCOPES, request_digest
from local_hand_jobs.policy import Policy, thaw
from local_hand_jobs.registry import Registry
from local_hand_jobs.state import StateStore
from q2_fixtures import SECOND, grant_data
from test_local_hand_jobs_contract import submit_fixture
from test_local_hand_jobs_local_a2_admission import local_a2_policy_fixture


class LocalA2ExecutionChainTests(unittest.TestCase):
    provenance_fields = ("expected", "local_hand_source_commit",
        "local_hand_installed_payload_digest", "local_hand_execution_entrypoint")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = StateStore(Path(temporary.name) / "state.sqlite", "authority", "ledger", initialize=True)
        self.addCleanup(self.state.close)
        request = submit_fixture(a2.KIND, runtime_ref="installed-a2")
        self.observation = grant_data(operation=request["operation_id"])
        original = dict(self.observation["budget"]["limits"])
        for key in ("wall_seconds", "cpu_seconds", "log_bytes"):
            original[key] *= 3
        config = local_a2_policy_fixture()
        config["profiles"]["fixture"]["budgets"][a2.KIND] = original
        config["limits"]["retained_bytes"] = 16 * 1024 ** 2
        self.policy = Policy(config)
        request["expected"] = self.policy.expected("fixture")
        request["request_digest"] = request_digest(request)
        self.request = request
        self.plan = thaw(Registry().resolve(request, self.policy,
            principal=Principal("owner", frozenset(TOOL_SCOPES.values()))))
        with self.state.transaction() as tx:
            self.state.insert(tx, "job", request["operation_id"], request["operation_id"],
                "owner", request["request_digest"], request, self.plan, self.plan["reservation_bytes"])

    def execution(self, phase):
        row = self.state.get("job", self.request["operation_id"])
        observed = grant_data(operation=row["id"], phase=phase,
            predecessors=[] if phase == "preflight" else ["a" * 32])
        allocation = observed["allocation"]
        allocation["source_roots"] = copy.deepcopy(row["plan"]["execution"]["roots"])
        allocation["grant_digest"] = bootstrap_roots._digest({
            key: value for key, value in allocation.items() if key != "grant_digest"})
        declaration = phase_plan(row, phase, observed["budget"], allocation=allocation, observation=observed)
        return runner._quota_prepared_execution(declaration,
            parent_mount_namespace="mnt:[123]", now_ns=2 * SECOND)

    def test_real_registry_provenance_survives_persistence_and_local_scope_check(self):
        execution = self.state.get("job", self.request["operation_id"])["plan"]["execution"]
        self.assertEqual(self.request["expected"], execution["bindings"]["expected"])
        self.assertEqual(self.policy.source_commit, execution["bindings"]["local_hand_source_commit"])
        self.assertEqual(self.policy.installed_payload_digest,
                         execution["bindings"]["local_hand_installed_payload_digest"])
        self.assertEqual(self.policy.execution_entrypoint,
                         execution["bindings"]["local_hand_execution_entrypoint"])
        self.assertTrue(a2.local_effects_only(execution))

    def test_registry_provenance_is_complete_and_strict_when_present(self):
        original = self.plan["execution"]
        for name in self.provenance_fields:
            execution = copy.deepcopy(original)
            del execution["bindings"][name]
            with self.subTest(missing=name):
                self.assertFalse(a2.local_effects_only(execution))
        invalid = {
            "expected": (None, {}, "unbound", dict(self.request["expected"], deployment_epoch=True)),
            "local_hand_source_commit": (None, True, "a" * 39, "A" * 40),
            "local_hand_installed_payload_digest": (None, True, "a" * 63, "A" * 64),
            "local_hand_execution_entrypoint": (None, "relative/cli.py", "//outside/cli.py", "/outside/../cli.py"),
        }
        for name, values in invalid.items():
            for value in values:
                execution = copy.deepcopy(original)
                execution["bindings"][name] = value
                with self.subTest(field=name, value=value):
                    self.assertFalse(a2.local_effects_only(execution))
        for extra in ("argv", "unrecognized_receipt", "runtime_python"):
            execution = copy.deepcopy(original)
            execution["bindings"][extra] = "unexpected"
            with self.subTest(extra=extra):
                self.assertFalse(a2.local_effects_only(execution))

    def test_payload_bindings_cannot_change_and_optional_outer_expected_must_match(self):
        original = self.plan["execution"]
        for name, value in (("source_commit", "f" * 40), ("source_commit_evidence", "ATTESTED"),
                ("runtime_descriptor_digest", "f" * 64), ("wheel_digest", "f" * 64),
                ("script_blobs", {})):
            execution = copy.deepcopy(original)
            execution["bindings"][name] = value
            with self.subTest(field=name):
                self.assertFalse(a2.local_effects_only(execution))
        execution = copy.deepcopy(original)
        execution["expected"] = copy.deepcopy(self.request["expected"])
        self.assertTrue(a2.local_effects_only(execution))
        execution["expected"]["node_id"] = "another-node"
        self.assertFalse(a2.local_effects_only(execution))
        execution = copy.deepcopy(original)
        for name in self.provenance_fields:
            del execution["bindings"][name]
        self.assertTrue(a2.local_effects_only(execution))

    def test_preflight_and_business_scope_survive_actual_quota_root_remapping(self):
        original = self.plan["execution"]
        for phase in ("preflight", "business"):
            with self.subTest(phase=phase):
                execution = self.execution(phase)
                self.assertNotEqual(original["roots"], execution["roots"])
                self.assertEqual(original["local_a2_runtime"], execution["local_a2_runtime"])
                self.assertEqual(original["bindings"], execution["bindings"])
                self.assertEqual(original["readonly"], execution["readonly"])
                self.assertEqual(execution["roots"]["work"], execution["stages"][0]["cwd"])
                self.assertIn(execution["roots"]["work"] + "/local-parent", execution["stages"][0]["argv"])
                self.assertEqual(execution["roots"]["temporary"], execution["stages"][0]["env"]["TMPDIR"])
                self.assertEqual(execution["budget_grant"]["limits"], execution["budgets"])
                self.assertTrue(a2.local_effects_only(execution))

    def test_unit_properties_keep_inputs_read_only_and_reader_has_no_writable_roots(self):
        manager = runner._SystemdExecutionCore({"uid": 1234, "slice": "fixture.slice",
            "cgroup": "/sys/fs/cgroup/fixture.slice"})
        for phase in ("preflight", "business"):
            execution = self.execution(phase)
            for stage in ("bootstrap", "helper", "result_reader"):
                with self.subTest(phase=phase, stage=stage):
                    properties = manager._properties(execution, stage)
                    self.assertEqual("strict", properties["ProtectSystem"])
                    self.assertEqual("yes", properties["PrivateMounts"])
                    self.assertEqual("yes", properties["PrivateNetwork"])
                    readonly = set(properties["ReadOnlyPaths"].split())
                    self.assertLessEqual(set(execution["readonly"]), readonly)
                    writable = set(properties["ReadWritePaths"].split())
                    if stage == "result_reader":
                        self.assertEqual(set(), writable)
                        self.assertLessEqual(set(execution["roots"].values()), readonly)
                    else:
                        self.assertEqual(set(execution["roots"].values()), writable)
                    self.assertFalse(writable & set(execution["readonly"]))


if __name__ == "__main__":
    unittest.main()
