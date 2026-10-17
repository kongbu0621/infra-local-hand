"""Historical A2 contracts still resolve pinned runtimes; new admission is retired."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from local_hand_jobs.contract import JobError, Principal, TOOL_SCOPES, request_digest, validate_tool_args
from local_hand_jobs.policy import Policy, thaw
from local_hand_jobs.registry import Registry
from test_local_hand_jobs_contract import submit_fixture
from test_local_hand_jobs_policy import policy_fixture


KIND = "ledger.test.local_a2"


def runtime_fixture(root):
    from local_hand_jobs.local_a2_jobs import SOURCE_BLOBS
    root = Path(root)
    runtime = root / "ledger-runtime"
    return dict(source_root=str(root / "ledger-source"), source_commit="a" * 40,
        source_blobs=dict(SOURCE_BLOBS), runtime_root=str(runtime),
        runtime_python=str(runtime / "bin/python"), runtime_python_realpath=str(root / "system/python"),
        runtime_python_sha256="b" * 64, venv_config_sha256="b" * 64,
        console_script_sha256="b" * 64,
        package_root=str(runtime / "lib/python3.12/site-packages/infra_artifact_ledger"),
        wheel=str(root / "wheels/ledger.whl"), wheel_sha256="b" * 64)


def local_a2_policy_fixture(root="/synthetic-local-a2"):
    config = policy_fixture(root)
    profile = config["profiles"]["fixture"]
    profile["local_a2_runtimes"] = {"installed-a2": runtime_fixture(root)}
    profile["budgets"][KIND] = dict(profile["budgets"]["host.inspect"], nas_bytes=0)
    owner = config["principals"]["owner"]["profiles"]["fixture"]
    owner["kinds"].append(KIND)
    owner["runtime_refs"] = ["installed-a2"]
    return config


class LocalA2AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.owner = Principal("owner", frozenset(TOOL_SCOPES.values()))

    def request(self, policy, runtime="installed-a2"):
        value = submit_fixture(KIND, runtime_ref=runtime)
        value["expected"] = policy.expected("fixture")
        value["request_digest"] = request_digest(value)
        return value

    def test_only_runtime_ref_crosses_prepare_and_submit_contract(self):
        args = dict(operation_id="12345678-1234-4234-9234-123456789abc",
            kind=KIND, profile_ref="fixture", inputs={"runtime_ref": "installed-a2"})
        self.assertEqual(args, validate_tool_args("lh_job_prepare", args))
        request = submit_fixture(KIND, runtime_ref="installed-a2")
        self.assertEqual(request, validate_tool_args("lh_job_submit", request))
        for key, value in (("argv", ["id"]), ("source_root", "/source"), ("runtime_python", "/python"),
                           ("prepared_ref", "prepared"), ("storage_ref", "nas"), ("content", "print(1)")):
            for name, original in (("lh_job_prepare", args), ("lh_job_submit", request)):
                altered = copy.deepcopy(original)
                altered["inputs"][key] = value
                with self.subTest(tool=name, key=key), self.assertRaises(JobError):
                    validate_tool_args(name, altered)
        for inputs in ({}, {"runtime_ref": "../runtime"}, {"runtime_ref": "/runtime"}):
            with self.subTest(inputs=inputs), self.assertRaises(JobError):
                validate_tool_args("lh_job_prepare", dict(args, inputs=inputs))

    def test_old_policy_stays_unchanged_and_cannot_gain_local_a2(self):
        config = policy_fixture("/synthetic-old")
        before = copy.deepcopy(config)
        policy = Policy(config)
        self.assertEqual(before, thaw(policy.config))
        profile = policy.capabilities(self.owner)["profiles"][0]
        self.assertNotIn(KIND, profile["allowed_kinds"])
        self.assertNotIn("runtime_refs", profile)
        self.assertNotIn(KIND, profile["budgets"])
        with self.assertRaises(JobError) as caught:
            Registry().resolve(self.request(policy), policy, principal=self.owner)
        self.assertEqual("UNAUTHORIZED", caught.exception.code)

    def test_retired_capability_is_hidden_even_with_historical_runtime_grants(self):
        config = local_a2_policy_fixture()
        policy = Policy(config)
        page = policy.capabilities(self.owner)
        profile = page["profiles"][0]
        self.assertNotIn(KIND, profile["allowed_kinds"])
        self.assertNotIn("runtime_refs", profile)
        self.assertNotIn(KIND, profile["budgets"])
        self.assertNotIn("ledger.nas.roundtrip", profile["allowed_kinds"])
        self.assertEqual([], profile["storage_refs"])
        self.assertNotIn("/synthetic-local-a2", json.dumps(page))
        other = Principal("other", self.owner.scopes)
        other_profile = policy.capabilities(other)["profiles"][0]
        self.assertNotIn(KIND, other_profile["allowed_kinds"])
        self.assertNotIn("runtime_refs", other_profile)
        with self.assertRaises(JobError) as caught:
            Registry().resolve(self.request(policy), policy, principal=other)
        self.assertEqual("UNAUTHORIZED", caught.exception.code)

    def test_runtime_grant_must_be_registered_and_nonempty(self):
        for refs in ([], ["missing"], ["installed-a2", "installed-a2"], "installed-a2"):
            config = local_a2_policy_fixture()
            config["principals"]["owner"]["profiles"]["fixture"]["runtime_refs"] = refs
            with self.subTest(refs=refs), self.assertRaises(JobError):
                Policy(config)
        config = local_a2_policy_fixture()
        del config["principals"]["owner"]["profiles"]["fixture"]["runtime_refs"]
        with self.assertRaises(JobError):
            Policy(config)

    def test_ungranted_registered_runtime_is_rejected_before_plan_resolution(self):
        config = local_a2_policy_fixture()
        config["profiles"]["fixture"]["local_a2_runtimes"]["other-runtime"] = runtime_fixture("/other")
        policy = Policy(config)
        with patch("local_hand_jobs.local_a2_jobs.build_plan") as build:
            with self.assertRaises(JobError) as caught:
                Registry().resolve(self.request(policy, "other-runtime"), policy, principal=self.owner)
            self.assertEqual("UNAUTHORIZED", caught.exception.code)
            build.assert_not_called()

    def test_writable_roots_cannot_overlap_registered_runtime_or_source(self):
        for field in ("source_root", "runtime_root", "wheel", "runtime_python_realpath"):
            config = local_a2_policy_fixture()
            runtime = config["profiles"]["fixture"]["local_a2_runtimes"]["installed-a2"]
            config["profiles"]["fixture"]["work_root"] = runtime[field]
            with self.subTest(field=field), self.assertRaises(JobError):
                Policy(config)

    def test_resolution_uses_exact_runtime_without_prepared_or_prerequisite_lookup(self):
        config = local_a2_policy_fixture()
        policy = Policy(config)
        prepared = Mock(side_effect=AssertionError("must not use prepared registry"))
        evidence = Mock(side_effect=AssertionError("must not use historical A2 prerequisites"))
        registry = Registry(prepared_lookup=prepared, evidence_lookup=evidence)
        request = self.request(policy)
        plan = thaw(registry.resolve(request, policy, principal=self.owner))
        self.assertEqual(KIND, plan["kind"])
        self.assertEqual({"runtime_ref": "installed-a2"}, plan["inputs"])
        self.assertEqual([], plan["prerequisites"])
        self.assertEqual(config["profiles"]["fixture"]["local_a2_runtimes"]["installed-a2"],
                         plan["execution"]["local_a2_runtime"])
        self.assertEqual(policy.source_commit, plan["execution"]["bindings"]["local_hand_source_commit"])
        self.assertEqual("a" * 40, plan["execution"]["bindings"]["source_commit"])
        self.assertEqual(request["expected"], plan["execution"]["bindings"]["expected"])
        prepared.assert_not_called()
        evidence.assert_not_called()


if __name__ == "__main__":
    unittest.main()
