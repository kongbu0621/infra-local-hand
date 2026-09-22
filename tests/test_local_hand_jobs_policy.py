"""Private admission, immutable fixed plans and server-only prerequisite tests."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_hand_jobs.contract import KINDS, SUITES, TOOL_SCOPES, Principal, JobError, request_digest
from local_hand_jobs.policy import Policy, thaw
from local_hand_jobs.registry import Registry, SCRIPT_BLOBS, SOURCE_COMMIT
from test_local_hand_jobs_contract import submit_fixture


def policy_fixture(root):
    root = Path(root)
    budget = dict(wall_seconds=60, terminate_grace_seconds=2, cpu_seconds=30,
        memory_bytes=1024 * 1024, processes=8, temporary_bytes=4096, nas_bytes=4096,
        log_bytes=4096, reservation_bytes=65536)
    profile = {"work_root": str(root / "work"), "evidence_root": str(root / "evidence"),
        "temporary_root": str(root / "temporary"), "python": str(root / "python"),
        "sources": {"source": {"root": str(root / "source"), "commit": SOURCE_COMMIT, "blobs": dict(SCRIPT_BLOBS)}},
        "build_caches": {"cache": {"root": str(root / "cache"), "files": {"fixture.whl": "a" * 64}}},
        "storages": {"storage": {"config": str(root / "storage-config.json"), "config_digest": "b" * 64,
            "resource_id": "archive-resource", "archive_root": str(root / "synthetic-archive"),
            "stable_mount_binding": {"source": "synthetic-storage:/archive", "root": "/", "type": "nfs4", "device": 5, "inode": 10}}},
        "budgets": {kind: dict(budget) for kind in (*KINDS, "reconcile")}, "resource_ids": ["fixture-work"]}
    grant = {"scopes": sorted(set(TOOL_SCOPES.values())), "profiles": {"fixture": {"kinds": list(KINDS),
        "source_refs": ["source"], "build_cache_refs": ["cache"], "storage_refs": ["storage"], "prepared_refs": [], "prepared_access": "owned"}}}
    return {"schema_version": "lh-policy-v1", "authority_id": "fixture-authority", "node_id": "fixture-node",
        "install_uuid": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", "deployment_epoch": 1, "generation": 1,
        "broker_root": str(root / "broker"), "authority_root": str(root / "authority"),
        "forbidden_roots": [str(root / "legacy")], "source_commit": "c" * 40,
        "installed_payload_digest": "d" * 64, "execution_entrypoint": str(root / "broker.py"),
        "limits": {"max_queued": 4, "max_running": 2, "retained_bytes": 1048576,
            "ledger_emergency_bytes": 65536, "requests_per_minute": 20},
        "profiles": {"fixture": profile}, "principals": {"owner": grant, "other": copy.deepcopy(grant)},
        "local_peers": {str(os.getuid()): "owner"}}


class PolicyAndRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = policy_fixture(self.root)
        self.policy = Policy(self.config)
        self.owner = Principal("owner", frozenset(TOOL_SCOPES.values()))
        self.other = Principal("other", self.owner.scopes)
        self.registry = Registry(clock=lambda: 1000)

    def request(self, kind="host.inspect", **inputs):
        request = submit_fixture(kind, **inputs)
        request["expected"] = self.policy.expected("fixture")
        request["request_digest"] = request_digest(request)
        return request

    def prepared(self):
        root = self.root / "work" / "prepare-root"
        return {"owner": "owner", "profile_ref": "fixture", "outcome": "SUCCEEDED", "evidence_state": "SEALED",
            "seal": "prepare-seal", "expected": self.policy.expected("fixture"), "root": str(root), "source_root": str(root / "source"),
            "build_python": str(root / "build-venv/bin/python"), "runtime_python": str(root / "runtime-venv/bin/python"),
            "wheel": str(root / "wheels/ledger.whl"), "source_commit": SOURCE_COMMIT,
            "source_blobs": dict(SCRIPT_BLOBS), "files": {"wheels/ledger.whl": "1" * 64}, "readonly_enforced": True,
            "bindings": {"source_commit": SOURCE_COMMIT, "source_digest": "1" * 64, "wheel_digest": "2" * 64,
                "installed_payload_digest": "3" * 64, "runtime_digest": "4" * 64, "environment_fingerprint": "5" * 64}}

    def register_all_prerequisites(self):
        prepared = self.prepared()
        self.registry.register_prepared("prepared", prepared)
        facts = []
        for index, kind in enumerate(("host.inspect", "ledger.prepare", "ledger.test.source", *SUITES, "ledger.test.installed_local")):
            item = {"evidence_id": "evidence-" + str(index), "kind": "ledger.test.resources" if kind in SUITES else kind,
                "profile_ref": "fixture", "owner": "owner", "observed_at": 990, "prepared_ref": "prepared",
                "outcome": "SUCCEEDED", "evidence_state": "SEALED", "coverage": "LOGIC_ONLY" if kind in SUITES else "PASS",
                "expected": self.policy.expected("fixture"), "bindings": prepared["bindings"], "seal_digest": "6" * 64}
            if kind in SUITES:
                item["suite"] = kind
            self.registry.register_evidence(item)
            facts.append(item)
        return facts

    def test_private_config_is_strict_and_not_a_disable_safety_switch(self):
        for field in ("mock", "skip_preflight", "allow_unsafe", "shell"):
            config = copy.deepcopy(self.config)
            config[field] = True
            with self.subTest(field=field), self.assertRaises(JobError):
                Policy(config)
        for field in ("source_commit", "installed_payload_digest", "execution_entrypoint"):
            config = copy.deepcopy(self.config)
            del config[field]
            with self.subTest(field=field), self.assertRaises(JobError):
                Policy(config)

    def test_prepared_bindings_cannot_inject_control_plane_provenance(self):
        for name, value in (("expected", {"node_id": "foreign-node"}),
                            ("local_hand_source_commit", "f" * 40),
                            ("script_blobs", {})):
            prepared = self.prepared()
            prepared["bindings"][name] = value
            with self.subTest(name=name), self.assertRaises(JobError):
                self.registry.register_prepared("prepared", prepared)
    def test_all_capacity_limits_and_job_budgets_are_finite_and_reserved_for_peak(self):
        for field in self.config["limits"]:
            for value in (True, 0, -1, None, float("inf")):
                config = copy.deepcopy(self.config)
                config["limits"][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(JobError):
                    Policy(config)
        for field in self.config["profiles"]["fixture"]["budgets"]["host.inspect"]:
            config = copy.deepcopy(self.config)
            del config["profiles"]["fixture"]["budgets"]["host.inspect"][field]
            with self.subTest(field=field), self.assertRaises(JobError):
                Policy(config)
        config = copy.deepcopy(self.config)
        config["profiles"]["fixture"]["budgets"]["host.inspect"]["reservation_bytes"] = 10
        with self.assertRaises(JobError):
            Policy(config)

    def test_forbidden_legacy_roots_and_unrelated_resource_aliases_are_rejected(self):
        for root in (str(self.root / "legacy/work"), str(self.root), "/", str(self.root / "work/../legacy")):
            config = copy.deepcopy(self.config)
            config["profiles"]["fixture"]["work_root"] = root
            with self.subTest(root=root), self.assertRaises(JobError):
                Policy(config)
        config = copy.deepcopy(self.config)
        config["profiles"]["alias"] = copy.deepcopy(config["profiles"]["fixture"])
        config["profiles"]["alias"]["resource_ids"] = ["different-resource"]
        with self.assertRaises(JobError):
            Policy(config)

    def test_double_slash_roots_cannot_bypass_path_admission(self):
        # POSIX Path preserves exactly two leading slashes, while Linux may
        # resolve them to the same object as the corresponding single slash.
        self.assertTrue(Path("/" + str(self.root)).samefile(self.root))
        accepted = []
        for value in ("//", "/" + self.config["broker_root"],
                      "/" + self.config["forbidden_roots"][0],
                      "/" + self.config["profiles"]["fixture"]["sources"]["source"]["root"]):
            config = copy.deepcopy(self.config)
            config["profiles"]["fixture"]["work_root"] = value
            try:
                Policy(config)
            except JobError as error:
                self.assertEqual("UNAUTHORIZED", error.code)
            else:
                accepted.append(value)
        self.assertEqual([], accepted, "Noncanonical root aliases must be rejected before overlap checks")

    def test_double_slash_mount_and_prepared_bindings_are_rejected(self):
        accepted = []
        config = copy.deepcopy(self.config)
        config["profiles"]["fixture"]["storages"]["storage"]["stable_mount_binding"]["root"] = "//"
        try:
            Policy(config)
        except JobError as error:
            self.assertEqual("UNAUTHORIZED", error.code)
        else:
            accepted.append("mount root")
        prepared = self.prepared()
        for field in ("root", "source_root", "build_python", "runtime_python", "wheel"):
            prepared[field] = "/" + prepared[field]
        try:
            self.registry.register_prepared("prepared", prepared)
        except JobError as error:
            self.assertEqual("NOT_SEALED", error.code)
        else:
            accepted.append("prepared paths")
        self.assertEqual([], accepted, "Identity bindings must use one canonical absolute root spelling")

    def test_archive_aliases_cannot_claim_independent_resource_ids(self):
        for alias in ("same-path", "same-mount-object"):
            config = copy.deepcopy(self.config)
            second = copy.deepcopy(config["profiles"]["fixture"])
            for field in ("work_root", "evidence_root", "temporary_root"):
                second[field] += "-other"
            second["resource_ids"] = ["other-work"]
            second["storages"]["storage"]["resource_id"] = "other-archive"
            if alias == "same-mount-object":
                second["storages"]["storage"]["archive_root"] += "-alias"
            config["profiles"]["other"] = second
            with self.subTest(alias=alias), self.assertRaises(JobError):
                Policy(config)

    def test_execution_roots_cannot_overlap_broker_or_authority_storage(self):
        for control in ("broker_root", "authority_root"):
            for field in ("work_root", "evidence_root", "temporary_root", "archive_root"):
                for relation in ("equal", "child", "parent"):
                    config = copy.deepcopy(self.config)
                    profile = config["profiles"]["fixture"]
                    target = profile["storages"]["storage"] if field == "archive_root" else profile
                    if relation == "parent":
                        config[control] = target[field] + "/control"
                    else:
                        target[field] = config[control] + ("/jobs" if relation == "child" else "")
                    with self.subTest(control=control, field=field, relation=relation), self.assertRaises(JobError):
                        Policy(config)

    def test_archive_and_profile_work_aliases_require_one_shared_lease(self):
        for field in ("work_root", "evidence_root", "temporary_root"):
            config = copy.deepcopy(self.config)
            second = copy.deepcopy(config["profiles"]["fixture"])
            for name in ("work_root", "evidence_root", "temporary_root"):
                second[name] += "-other"
            second["resource_ids"] = ["other-work"]
            second["storages"] = {}
            config["profiles"]["other"] = second
            storage = config["profiles"]["fixture"]["storages"]["storage"]
            storage["archive_root"] = second[field]
            with self.subTest(field=field), self.assertRaises(JobError):
                Policy(config)
            second["resource_ids"].append(storage["resource_id"])
            Policy(config)  # Both job plans now necessarily acquire this lease.

    def test_writable_root_cannot_enclose_fixed_source_or_interpreter(self):
        for field in ("python", "source"):
            config = copy.deepcopy(self.config)
            profile = config["profiles"]["fixture"]
            if field == "python":
                profile["python"] = profile["work_root"] + "/python"
            else:
                profile["sources"]["source"]["root"] = profile["work_root"] + "/source"
            with self.subTest(field=field), self.assertRaises(JobError):
                Policy(config)

    def test_prepared_grant_mode_is_explicit_and_listed_mode_restricts_use(self):
        config = copy.deepcopy(self.config)
        access = config["principals"]["owner"]["profiles"]["fixture"]
        access["prepared_refs"] = ["allowed"]
        with self.assertRaises(JobError):
            Policy(config)  # An owned mode cannot silently discard restrictions.
        access["prepared_access"] = "listed"
        policy = Policy(config)
        request = self.request("ledger.test.source", prepared_ref="prepared")
        with self.assertRaises(JobError):
            policy.authorize(self.owner, "lh:submit", request=request)
        request["inputs"]["prepared_ref"] = "allowed"
        policy.authorize(self.owner, "lh:submit", request=request)
        for ref in ("allowed", "prepared"):
            policy.register_prepared_reference(ref, owner="owner", profile_ref="fixture")
        self.assertEqual(policy.capabilities(self.owner)["profiles"][0]["prepared_refs"], ["allowed"])

    def test_process_manager_schema_matches_fixed_server_configuration(self):
        config = copy.deepcopy(self.config)
        config["process_manager"] = {"uid": os.getuid(), "slice": "fixture-jobs.slice", "cgroup": "/sys/fs/cgroup/fixture-jobs.slice"}
        self.assertEqual(Policy(config).config["process_manager"]["uid"], os.getuid())
        for value in ({"uid": 1, "slice": "fixture.slice", "cgroup": str(self.root)},
                      {"uid": 1, "slice": "../escape.slice", "cgroup": "/sys/fs/cgroup/fixture"},
                      {"uid": 1, "slice": "fixture.slice", "cgroup": "/sys/fs/cgroup/fixture", "disable_limits": True}):
            config["process_manager"] = value
            with self.subTest(value=value), self.assertRaises(JobError):
                Policy(config)

    def test_current_scope_kind_input_and_owner_grants_are_all_required(self):
        self.policy.authorize(self.owner, "lh:submit", request=self.request("ledger.prepare", source_ref="source", build_cache_ref="cache"))
        for principal in (Principal("stranger", self.owner.scopes), Principal("owner", frozenset({"lh:read"}))):
            with self.assertRaises(JobError):
                self.policy.authorize(principal, "lh:submit")
        with self.assertRaises(JobError):
            self.policy.authorize(self.other, "lh:read", owner="owner")
        request = self.request("ledger.prepare", source_ref="source", build_cache_ref="cache")
        request["inputs"]["source_ref"] = "unlisted"
        with self.assertRaises(JobError):
            self.policy.authorize(self.owner, "lh:submit", request=request)

    def test_policy_expected_and_plans_are_detached_from_mutable_config(self):
        before = self.policy.expected("fixture")
        self.config["deployment_epoch"] = 42
        self.assertEqual(self.policy.expected("fixture"), before)
        with self.assertRaises(TypeError):
            self.policy.config["deployment_epoch"] = 42
        plan = self.registry.resolve(self.request(), self.policy, principal=self.owner)
        with self.assertRaises(TypeError):
            plan["execution"]["bindings"]["source_commit"] = "0" * 40
        unwrapped = thaw(plan)
        digest = unwrapped.pop("plan_digest")
        self.assertEqual(digest, hashlib.sha256(json.dumps(unwrapped, sort_keys=True, separators=(",", ":")).encode()).hexdigest())

    def test_control_authorization_discovery_and_resolve_do_no_filesystem_io(self):
        with patch("pathlib.Path.stat", side_effect=AssertionError("control path touched FS")), patch("builtins.open", side_effect=AssertionError("control path read bytes")):
            self.policy.authorize(self.owner, "lh:inspect")
            self.policy.expected("fixture")
            self.policy.capabilities(self.owner)
            self.registry.resolve(self.request(), self.policy, principal=self.owner)

    def test_capability_filters_private_paths_and_foreign_prepared_refs(self):
        self.registry.resolve(self.request(), self.policy, principal=self.owner)
        self.registry.register_prepared("prepared", self.prepared())
        owner = self.policy.capabilities(self.owner)
        other = self.policy.capabilities(self.other)
        self.assertEqual(owner["profiles"][0]["prepared_refs"], ["prepared"])
        self.assertEqual(other["profiles"][0]["prepared_refs"], [])
        self.assertNotIn(str(self.root), json.dumps(owner))
        self.assertEqual(set(owner["profiles"][0]["expected"]), set(self.policy.expected("fixture")))
        self.assertEqual(owner["execution_support"]["ledger.nas.roundtrip"], {
            "status": "UNSUPPORTED", "reason": "NETWORK_ARCHIVE_HARD_QUOTA_ADAPTER_UNIMPLEMENTED"})

    def test_capability_cursor_is_principal_and_catalog_bound(self):
        config = copy.deepcopy(self.config)
        config["profiles"]["second"] = copy.deepcopy(config["profiles"]["fixture"])
        for grant in config["principals"].values():
            grant["profiles"]["second"] = copy.deepcopy(grant["profiles"]["fixture"])
        policy = Policy(config)
        first = policy.capabilities(self.owner, page_size=1)
        self.assertIsNotNone(first["next_cursor"])
        second = policy.capabilities(self.owner, cursor=first["next_cursor"], page_size=1)
        self.assertNotEqual(first["profiles"][0]["profile_ref"], second["profiles"][0]["profile_ref"])
        with self.assertRaises(JobError):
            policy.capabilities(self.other, cursor=first["next_cursor"])
        policy.register_prepared_reference("new", owner="owner", profile_ref="fixture")
        with self.assertRaises(JobError) as raised:
            policy.capabilities(self.owner, cursor=first["next_cursor"])
        self.assertEqual(raised.exception.code, "STALE_DEPLOYMENT")

    def test_fixed_source_and_script_bytes_are_required_for_preparation_plan(self):
        request = self.request("ledger.prepare", source_ref="source", build_cache_ref="cache")
        plan = self.registry.resolve(request, self.policy, principal=self.owner)
        self.assertEqual(plan["execution"]["source"]["commit"], SOURCE_COMMIT)
        self.assertNotIn("GITHUB_TOKEN", plan["execution"]["environment"])
        for mutation in ("commit", "blob"):
            config = copy.deepcopy(self.config)
            source = config["profiles"]["fixture"]["sources"]["source"]
            if mutation == "commit":
                source["commit"] = "0" * 40
            else:
                source["blobs"][next(iter(SCRIPT_BLOBS))] = "0" * 40
            policy = Policy(config)
            request["expected"] = policy.expected("fixture")
            request["request_digest"] = request_digest(request)
            with self.subTest(mutation=mutation), self.assertRaises(JobError):
                self.registry.resolve(request, policy, principal=self.owner)

    def test_prepared_refs_require_owner_seal_actual_inventory_and_immutable_paths(self):
        fact = self.prepared()
        self.registry.register_prepared("prepared", fact)
        request = self.request("ledger.test.source", prepared_ref="prepared")
        self.registry.resolve(request, self.policy, principal=self.owner)
        for principal in (None, self.other):
            with self.assertRaises(JobError):
                self.registry.resolve(request, self.policy, principal=principal)
        modified = copy.deepcopy(fact)
        modified["runtime_python"] = str(self.root / "outside-python")
        with self.assertRaises(JobError):
            self.registry.register_prepared("prepared", modified)
        for key, value in (("evidence_state", "DURABILITY_UNKNOWN"), ("files", {}), ("readonly_enforced", False)):
            modified = copy.deepcopy(fact)
            modified[key] = value
            registry = Registry(prepared_lookup=lambda _: modified)
            with self.subTest(key=key), self.assertRaises(JobError):
                registry.resolve(request, self.policy, principal=self.owner)
        stale = copy.deepcopy(fact)
        stale["expected"]["deployment_epoch"] += 1
        with self.assertRaises(JobError) as raised:
            Registry(prepared_lookup=lambda _: stale).resolve(request, self.policy, principal=self.owner)
        self.assertEqual(raised.exception.code, "STALE_DEPLOYMENT")

    def test_prepared_repeated_provenance_fields_cannot_disagree(self):
        for name in ("source_commit", "source_digest", "wheel_digest", "installed_payload_digest",
                     "runtime_digest", "environment_fingerprint"):
            fact = self.prepared()
            if name == "source_commit":
                fact["bindings"][name] = "0" * 40
            else:
                fact[name] = "0" * 64
            with self.subTest(name=name), self.assertRaises(JobError) as raised:
                self.registry.register_prepared("prepared", fact)
            self.assertEqual(raised.exception.code, "CONFLICT")

    def test_resources_use_exact_a1_main_entry_and_explicit_a2_enable_flag(self):
        self.registry.register_prepared("prepared", self.prepared())
        for suite in SUITES:
            request = self.request("ledger.test.resources", prepared_ref="prepared", suite=suite)
            plan = self.registry.resolve(request, self.policy, principal=self.owner)
            stage = plan["execution"]["stages"][0]
            self.assertEqual(stage["env"]["PYTHONPATH"], "src")
            if suite.startswith("a1_"):
                self.assertNotIn("discover", stage["argv"])
                self.assertNotIn("A2_RESOURCE_TESTS", stage["env"])
            else:
                self.assertEqual(stage["env"]["A2_RESOURCE_TESTS"], "1")
            for key in ("TMPDIR", "TMP", "TEMP"):
                self.assertEqual(stage["env"][key], plan["execution"]["roots"]["temporary"])

    def test_nas_refuses_missing_or_newer_failed_prerequisite_and_wrong_bindings(self):
        self.registry.register_prepared("prepared", self.prepared())
        request = self.request("ledger.nas.roundtrip", prepared_ref="prepared", storage_ref="storage")
        with self.assertRaises(JobError):
            self.registry.resolve(request, self.policy, principal=self.owner)
        facts = self.register_all_prerequisites()
        plan = self.registry.resolve(request, self.policy, principal=self.owner)
        self.assertEqual(len(plan["prerequisites"]), 8)
        for changed in ("FAILED", "PENDING", "UNKNOWN"):
            failed = copy.deepcopy(facts[2])
            failed.update(evidence_id="later-" + changed.lower(), observed_at=999, outcome=changed)
            self.registry.register_evidence(failed)
            with self.subTest(outcome=changed), self.assertRaises(JobError):
                self.registry.resolve(request, self.policy, principal=self.owner)

    def test_logic_only_host_expired_and_candidate_drift_never_satisfy_nas(self):
        for key in ("logic_host", "expired", "drift", "mount"):
            self.registry = Registry(clock=lambda: 1000)
            facts = self.register_all_prerequisites()
            request = self.request("ledger.nas.roundtrip", prepared_ref="prepared", storage_ref="storage")
            if key == "expired":
                self.registry._clock = lambda: 100000
            elif key == "mount":
                config = copy.deepcopy(self.config)
                config["profiles"]["fixture"]["storages"]["storage"]["stable_mount_binding"] = False
                with self.assertRaises(JobError):
                    Policy(config)
                continue
            else:
                item = copy.deepcopy(facts[0 if key == "logic_host" else 2])
                item.update(evidence_id="later", observed_at=999)
                if key == "logic_host":
                    item["coverage"] = "LOGIC_ONLY"
                else:
                    item["bindings"]["wheel_digest"] = "9" * 64
                self.registry.register_evidence(item)
            with self.subTest(key=key), self.assertRaises(JobError):
                self.registry.resolve(request, self.policy, principal=self.owner)

    def test_durable_event_sequence_resolves_same_second_and_clock_rollback(self):
        facts = self.register_all_prerequisites()
        request = self.request("ledger.nas.roundtrip", prepared_ref="prepared", storage_ref="storage")
        pending = copy.deepcopy(facts[0])
        pending.update(evidence_id="host-pending", observed_at=990, event_seq=1, outcome="PENDING")
        self.registry.register_evidence(pending)
        sealed = copy.deepcopy(facts[0])
        sealed.update(evidence_id="host-sealed", observed_at=990, event_seq=2)
        self.registry.register_evidence(sealed)
        self.registry.resolve(request, self.policy, principal=self.owner)
        failed = copy.deepcopy(facts[0])
        failed.update(evidence_id="host-later-failed", observed_at=980, event_seq=3, outcome="FAILED")
        self.registry.register_evidence(failed)
        with self.assertRaises(JobError):
            self.registry.resolve(request, self.policy, principal=self.owner)

    def test_file_loader_rejects_public_config_symlink_and_path_symlink(self):
        path = self.root / "policy.json"
        path.write_text(json.dumps(self.config))
        os.chmod(path, 0o644)
        with self.assertRaises(JobError):
            Policy.from_file(path)

        os.chmod(path, 0o600)
        alias = self.root / "alias.json"
        alias.symlink_to(path)
        with self.assertRaises(JobError):
            Policy.from_file(alias)
        for name in ("broker", "authority", "work", "evidence", "temporary", "source", "cache"):
            (self.root / name).mkdir(mode=0o700)
        for name in ("python", "broker.py"):
            (self.root / name).write_text("synthetic fixture bytes")
            os.chmod(self.root / name, 0o600)
        self.assertEqual(Policy.from_file(path).policy_digest, self.policy.policy_digest)
        (self.root / "work").rmdir()
        (self.root / "work").symlink_to(self.root / "evidence", target_is_directory=True)
        with self.assertRaises(JobError):
            Policy.from_file(path)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO boundary unavailable")
    def test_private_config_special_file_does_not_block_at_open(self):
        fifo = self.root / "config-fifo"
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(JobError):
            Policy.from_file(fifo)


if __name__ == "__main__":
    unittest.main()
