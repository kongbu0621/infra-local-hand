"""Plugin distribution and realistic client retry/control boundary tests."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from local_hand_jobs.contract import JobError, SCHEMA_VERSION, TOOL_SCHEMA_DIGEST, TOOL_SCHEMAS

PLUGIN = ROOT / "plugins" / "local-hand-a2"
spec = importlib.util.spec_from_file_location("local_hand_plugin_workflow", PLUGIN / "scripts" / "workflow.py")
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)

EXPECTED = {"node_id": "synthetic-node", "install_uuid": "12345678-1234-4234-8234-123456789abc",
            "deployment_epoch": 1, "profile_digest": "a" * 64,
            "policy_digest": "b" * 64, "registry_digest": "c" * 64}


class HostCallback:
    def __init__(self):
        self.calls = []
        self.page = {"schema_version": SCHEMA_VERSION, "tool_schema_digest": TOOL_SCHEMA_DIGEST,
                     "authority_id": "synthetic-authority", "catalog_version": "version-1",
                     "profiles": [{"profile_ref": "fixture", "expected": copy.deepcopy(EXPECTED),
                                   "allowed_kinds": ["host.inspect", "ledger.prepare", "ledger.test.source"],
                                   "source_refs": ["source"], "build_cache_refs": ["cache"],
                                   "prepared_refs": ["prepared"], "storage_refs": []}], "next_cursor": None}
        self.fail_submit_once = False
        self.fail_reconcile_once = False
        self.status = {"lifecycle": "RUNNING", "outcome": "PENDING", "evidence": "STAGING"}
        self.requests = {}

    def __call__(self, tool, args):
        self.calls.append((tool, copy.deepcopy(args)))
        if tool == "lh_capabilities":
            return copy.deepcopy(self.page)
        if tool == "lh_job_submit" and self.fail_submit_once:
            self.fail_submit_once = False
            raise TimeoutError("synthetic response loss after acceptance")
        if tool == "lh_job_reconcile" and self.fail_reconcile_once:
            self.fail_reconcile_once = False
            raise TimeoutError("synthetic reconcile response loss")
        if tool == "lh_job_submit":
            self.requests[args["operation_id"]] = copy.deepcopy(args)
        result = {"operation_id": args["operation_id"],
                  "request_digest": args.get("request_digest", args.get("expected_request_digest",
                      self.requests.get(args["operation_id"], {}).get("request_digest")))}
        reconcile = args.get("reconcile_id", args.get("target", {}).get("reconcile_id"))
        if reconcile is not None:
            result["reconcile_id"] = reconcile
        return {**result, **copy.deepcopy(self.status)} if tool == "lh_job_status" else {"accepted": True, **result}


class PluginDistributionTests(unittest.TestCase):
    def test_portable_manifests_and_disconnected_public_template(self):
        manifest = json.loads((PLUGIN / "plugin.json").read_text())
        self.assertEqual(manifest["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertEqual(manifest["name"], "local-hand-a2")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(set(manifest["extensions"]["com.openai"]), {"interface"})
        self.assertNotIn("license", manifest)
        self.assertEqual(json.loads((PLUGIN / "mcp.json").read_text()), {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json", "mcpServers": {}})

    def test_distribution_contract_is_the_actual_seven_tool_contract(self):
        frozen = json.loads((PLUGIN / "contract.json").read_text())
        self.assertEqual(frozen["tools"], TOOL_SCHEMAS)
        self.assertEqual(frozen["tool_schema_digest"], TOOL_SCHEMA_DIGEST)
        self.assertEqual(len(frozen["tools"]), 7)
        self.assertTrue(frozen["backend_contract_compatibility"]["digest_match_required"])
        self.assertEqual(frozen["connection_status"], "UNCONFIGURED_E4_REQUIRED")

    def test_four_complete_skills_have_valid_frontmatter_and_no_automatic_entry(self):
        paths = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(paths), 4)
        for path in paths:
            text = path.read_text()
            front = re.fullmatch(r"---\nname: ([a-z0-9-]+)\ndescription: ([^\n]+)\n---\n([\s\S]+)", text)
            self.assertIsNotNone(front, path.name)
            self.assertEqual(front[1], path.parent.name)
            self.assertLessEqual(len(front[1]), 64)
            self.assertLess(len(text.splitlines()), 100)
            self.assertNotIn("TODO", text)
            ui = (path.parent / "agents" / "openai.yaml").read_text()
            self.assertIn("$" + path.parent.name, ui)
        files = [p for p in PLUGIN.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        for path in files:
            self.assertFalse(path.is_symlink())
            self.assertNotIn("hooks", path.relative_to(PLUGIN).parts)
            text = path.read_text()
            for private_pattern in (r"plugin_asdk_app_[a-zA-Z0-9]", r"gh[pousr]_[A-Za-z0-9]{20}",
                                    r"/home/", r"/mnt/data1/", r"(?i)Bearer\s+[A-Za-z0-9._-]{20}"):
                self.assertNotRegex(text, private_pattern)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host = HostCallback()
        self.admission = {"authority_id": "synthetic-authority", "profiles": {"fixture": copy.deepcopy(EXPECTED)}}
        self.client = workflow.Workflow(self.host, Path(self.tmp.name) / "journal", self.admission,
                                        sleep=lambda _: None)
        self.client.preflight()

    def tearDown(self):
        self.tmp.cleanup()

    def reserve(self, key="inspect"):
        record = self.client.reserve_job(key, kind="host.inspect", profile_ref="fixture", inputs={})
        self.host.requests[record["request"]["operation_id"]] = copy.deepcopy(record["request"])
        return record

    def assert_error(self, code, fn, *args, **kwargs):
        with self.assertRaises(JobError) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_lost_submission_response_and_new_client_reuse_original_identity(self):
        first = self.reserve()
        self.host.fail_submit_once = True
        with self.assertRaises(TimeoutError):
            self.client.submit("inspect")
        restarted = workflow.Workflow(self.host, self.client.journal, self.admission, sleep=lambda _: None)
        restarted.preflight()
        second = restarted.reserve_job("inspect", kind="host.inspect", profile_ref="fixture", inputs={})
        self.assertEqual(first, second)
        restarted.submit("inspect")
        submissions = [args for name, args in self.host.calls if name == "lh_job_submit"]
        self.assertEqual(len(submissions), 2)
        self.assertEqual(submissions[0], submissions[1])

    def test_same_intent_cannot_change_job(self):
        self.reserve()
        self.assert_error("CONFLICT", self.client.reserve_job, "inspect", kind="ledger.prepare",
                          profile_ref="fixture", inputs={"source_ref": "source", "build_cache_ref": "cache"})

    def test_journal_directory_replacement_cannot_reserve_a_new_identity(self):
        original = self.reserve()
        old = self.client.journal.with_name("old-journal")
        self.client.journal.rename(old)
        self.client.journal.mkdir(mode=0o700)
        self.assert_error("IO_UNCERTAIN", self.reserve)
        preserved = json.loads((old / self.client._record_name("job", "inspect")).read_text())
        self.assertEqual(original, preserved)
        self.assertEqual(list(self.client.journal.iterdir()), [])

    def test_identity_publication_never_unlinks_a_concurrent_staging_replacement(self):
        replacements = []
        publish_name = "_publish_create_only" if hasattr(workflow, "_publish_create_only") else None
        original = getattr(workflow, publish_name) if publish_name else workflow.os.link
        def publish(source, target, **kwargs):
            result = original(source, target, **kwargs)
            path = self.client.journal / Path(source).name
            if path.exists():
                path.unlink()
            path.write_bytes(b"concurrent file")
            replacements.append(path)
            return result
        target = workflow if publish_name else workflow.os
        with patch.object(target, publish_name or "link", side_effect=publish):
            self.reserve()
        self.assertEqual(1, len(replacements))
        self.assertTrue(replacements[0].exists(), "publication removed a concurrent file")
        self.assertEqual(b"concurrent file", replacements[0].read_bytes())

    def test_published_identity_cannot_be_replaced_before_readback(self):
        original = workflow.os.fsync
        path = self.client.journal / self.client._record_name("job", "inspect")
        changed = []
        def sync(fd):
            result = original(fd)
            if not changed and path.exists() and workflow.stat.S_ISDIR(os.fstat(fd).st_mode):
                record = json.loads(path.read_text())
                record["request"]["operation_id"] = str(workflow.uuid.uuid4())
                record["request"]["request_digest"] = workflow.request_digest(record["request"])
                replacement = path.with_suffix(".replacement")
                replacement.write_text(json.dumps(record))
                replacement.chmod(0o600)
                replacement.replace(path)
                changed.append(record)
            return result
        with patch.object(workflow.os, "fsync", side_effect=sync):
            self.assert_error("IO_UNCERTAIN", self.reserve)
        self.assertEqual(1, len(changed))
        self.assertEqual(changed[0], json.loads(path.read_text()))

    def test_published_identity_cannot_be_rewritten_in_place_before_readback(self):
        original = workflow.os.fsync
        path = self.client.journal / self.client._record_name("job", "inspect")
        changed = []
        def sync(fd):
            result = original(fd)
            if not changed and path.exists() and workflow.stat.S_ISDIR(os.fstat(fd).st_mode):
                before = path.stat()
                record = json.loads(path.read_text())
                record["request"]["operation_id"] = str(workflow.uuid.uuid4())
                record["request"]["request_digest"] = workflow.request_digest(record["request"])
                path.write_text(json.dumps(record))
                after = path.stat()
                self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
                changed.append(record)
            return result
        with patch.object(workflow.os, "fsync", side_effect=sync):
            self.assert_error("IO_UNCERTAIN", self.reserve)
        self.assertEqual(1, len(changed))
        self.assertEqual(changed[0], json.loads(path.read_text()))
        self.assertFalse(any(name == "lh_job_submit" for name, _ in self.host.calls))

    def test_unknown_input_is_not_translated_to_a_path(self):
        self.assert_error("UNAUTHORIZED", self.client.reserve_job, "prepare", kind="ledger.prepare",
                          profile_ref="fixture", inputs={"source_ref": "/private/source", "build_cache_ref": "cache"})
        self.assertFalse(any(name == "lh_job_submit" for name, _ in self.host.calls))

    def test_execution_support_blocks_a_granted_but_unimplemented_kind(self):
        self.host.page["profiles"][0]["allowed_kinds"].append("ledger.nas.roundtrip")
        announcement = {"ledger.nas.roundtrip": {"status": "UNSUPPORTED", "reason": "NETWORK_ARCHIVE_HARD_QUOTA_ADAPTER_UNIMPLEMENTED"}}
        self.host.page["execution_support"] = announcement
        self.client.preflight()
        self.assertEqual(self.client.execution_support, announcement)
        self.assert_error("UNSUPPORTED", self.client.reserve_job, "nas", kind="ledger.nas.roundtrip",
                          profile_ref="fixture", inputs={"prepared_ref": "prepared", "storage_ref": "storage"})
        self.assertFalse(any(name == "lh_job_submit" for name, _ in self.host.calls))

    def test_durability_failure_prevents_first_submission(self):
        with patch.object(workflow.os, "fsync", side_effect=OSError("synthetic fsync failure")):
            self.assert_error("IO_UNCERTAIN", self.reserve)
        self.assertFalse(any(name == "lh_job_submit" for name, _ in self.host.calls))
        self.assert_error("NOT_FOUND", self.client.submit, "inspect")

    def test_corrupted_existing_identity_is_not_replaced(self):
        saved = self.reserve()
        path = self.client.journal / self.client._record_name("job", "inspect")
        path.write_bytes(b"{")
        self.assert_error("IO_UNCERTAIN", self.reserve)
        self.assertEqual(path.read_bytes(), b"{")
        self.assertFalse(any(name == "lh_job_submit" for name, _ in self.host.calls))

    def test_duplicate_persisted_request_keys_cannot_rebind_the_intent(self):
        record = self.reserve()
        path = self.client.journal / self.client._record_name("job", "inspect")
        raw = json.dumps(record)[0:-1] + ', "request": ' + json.dumps(record["request"]) + "}"
        path.write_text(raw)
        self.assert_error("IO_UNCERTAIN", self.reserve)
        self.assertEqual(path.read_text(), raw)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO boundary unavailable")
    def test_fifo_identity_cannot_block_client_control(self):
        path = self.client.journal / self.client._record_name("job", "inspect")
        os.mkfifo(path, 0o600)
        probe = """import importlib.util,json,pathlib,sys
spec=importlib.util.spec_from_file_location('workflow_probe',sys.argv[1])
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
client=module.Workflow(lambda *args: {},pathlib.Path(sys.argv[2]),json.loads(sys.argv[3]))
try:
    client.reserve_job('inspect',kind='host.inspect',profile_ref='fixture',inputs={})
except module.JobError as exc:
    assert exc.code == 'IO_UNCERTAIN', exc.code
else:
    raise AssertionError('FIFO was accepted')
"""
        environment = dict(os.environ, PYTHONPATH=str(ROOT / "tools"), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-c", probe, str(PLUGIN / "scripts/workflow.py"),
                                 str(self.client.journal), json.dumps(self.admission)],
                                env=environment, capture_output=True, timeout=2)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_failed_directory_commit_is_reconfirmed_before_resubmission(self):
        real_fsync = os.fsync
        calls = [0]
        def fail_directory_once(fd):
            calls[0] += 1
            if calls[0] == 2:
                raise OSError("synthetic directory persistence failure")
            return real_fsync(fd)
        with patch.object(workflow.os, "fsync", side_effect=fail_directory_once):
            self.assert_error("IO_UNCERTAIN", self.reserve)
        path = self.client.journal / self.client._record_name("job", "inspect")
        published_id = json.loads(path.read_bytes())["request"]["operation_id"]
        with patch.object(workflow.os, "fsync", side_effect=OSError("still uncertain")):
            self.assert_error("IO_UNCERTAIN", self.reserve)
            self.assert_error("IO_UNCERTAIN", self.client.submit, "inspect")
        self.assertEqual(self.reserve()["request"]["operation_id"], published_id)
        self.client.submit("inspect")
        self.assertEqual([args["operation_id"] for name, args in self.host.calls if name == "lh_job_submit"], [published_id])

    def test_untrusted_authority_and_changed_expected_stop_submission(self):
        self.reserve()
        for mutation in (lambda: self.host.page.update(authority_id="other-authority"),
                         lambda: self.host.page["profiles"][0]["expected"].update(deployment_epoch=2)):
            self.host.page["authority_id"] = "synthetic-authority"
            mutation()
            self.assert_error("STALE_DEPLOYMENT", self.client.preflight)
            self.assert_error("STALE_DEPLOYMENT", self.client.submit, "inspect")
        self.assertFalse(any(name == "lh_job_submit" for name, _ in self.host.calls))

    def test_contract_mismatch_retains_existing_query_path(self):
        original = self.reserve()
        self.host.page["tool_schema_digest"] = "d" * 64
        self.assert_error("UNSUPPORTED", self.client.preflight)
        observed = self.client.observe(job_key="inspect")
        self.assertEqual(observed["target"]["operation_id"], original["request"]["operation_id"])
        self.assertEqual(observed["latest"]["outcome"], "PENDING")

    def test_pagination_version_change_does_not_publish_partial_catalog(self):
        self.host.page["next_cursor"] = "page2"
        count = [0]
        def changing(tool, args):
            count[0] += 1
            if count[0] == 2:
                self.host.page["catalog_version"] = "version-2"
            return self.host(tool, args)
        self.client.call = changing
        self.assert_error("STALE_DEPLOYMENT", self.client.preflight)
        self.assert_error("UNAUTHORIZED", self.reserve)

    def test_reconcile_response_loss_and_cancel_targets_are_independent(self):
        job = self.reserve()
        first = self.client.reserve_reconcile("first-observation", "inspect")
        self.host.fail_reconcile_once = True
        with self.assertRaises(TimeoutError):
            self.client.reconcile("first-observation")
        self.assertEqual(first, self.client.reserve_reconcile("first-observation", "inspect"))
        self.client.reconcile("first-observation")
        self.client.cancel_job("inspect")
        self.client.cancel_reconcile("first-observation")
        cancels = [args for tool, args in self.host.calls if tool == "lh_job_cancel"]
        self.assertEqual(cancels[0]["target"], {"kind": "job"})
        self.assertEqual(cancels[1]["target"], {"kind": "reconcile", "reconcile_id": first["arguments"]["reconcile_id"]})
        self.assertEqual(cancels[0]["operation_id"], job["request"]["operation_id"])
        self.assertNotEqual(self.client.reserve_reconcile("new-observation", "inspect")["arguments"]["reconcile_id"],
                            first["arguments"]["reconcile_id"])

    def test_reconcile_identity_cannot_be_rebound_to_another_parent(self):
        self.reserve("one")
        self.reserve("two")
        self.client.reserve_reconcile("observe", "one")
        self.assert_error("CONFLICT", self.client.reserve_reconcile, "observe", "two")

    def test_polling_budget_does_not_change_unknown_or_resubmit(self):
        self.reserve()
        self.host.status["outcome"] = "UNKNOWN"
        result = self.client.observe(job_key="inspect")
        self.assertFalse(result["observation_complete"])
        self.assertEqual(result["latest"]["outcome"], "UNKNOWN")
        self.assertEqual(sum(tool == "lh_job_status" for tool, _ in self.host.calls), 12)
        self.assertFalse(any(tool == "lh_job_submit" for tool, _ in self.host.calls))

    def test_not_found_cancel_does_not_report_cancellation(self):
        self.reserve()
        self.client.call = lambda *_: {"error": {"code": "NOT_FOUND"}}
        self.assert_error("NOT_FOUND", self.client.cancel_job, "inspect")

    def test_reconcile_query_addresses_exact_saved_round(self):
        self.reserve()
        record = self.client.reserve_reconcile("observe", "inspect")
        self.host.status["lifecycle"] = "TERMINAL"
        result = self.client.observe(reconcile_key="observe")
        self.assertEqual(result["target"]["reconcile_id"], record["arguments"]["reconcile_id"])
        self.assertEqual(sum(tool == "lh_job_status" for tool, _ in self.host.calls), 1)

    def test_misrouted_status_cannot_complete_a_different_job_or_round(self):
        self.reserve()
        self.client.reserve_reconcile("observe", "inspect")
        self.host.status.update(lifecycle="TERMINAL", outcome="SUCCEEDED", evidence="SEALED")
        for mode in ("operation", "digest", "round", "missing"):
            def wrong(tool, args):
                result = self.host(tool, args)
                if mode == "operation":
                    result["operation_id"] = "00000000-0000-4000-8000-000000000000"
                elif mode == "digest":
                    result["request_digest"] = "0" * 64
                elif mode == "round":
                    result["reconcile_id"] = "00000000-0000-4000-8000-000000000000"
                else:
                    del result["operation_id"]
                return result
            self.client.call = wrong
            for target in ({"job_key": "inspect"}, {"reconcile_key": "observe"}):
                with self.subTest(mode=mode, target=target):
                    self.assert_error("IO_UNCERTAIN" if mode == "missing" else "CONFLICT",
                                      self.client.observe, **target)

    def test_misrouted_submit_and_cancel_receipts_are_not_accepted(self):
        self.reserve()
        self.client.reserve_reconcile("observe", "inspect")
        def wrong(tool, args):
            result = self.host(tool, args)
            result["request_digest"] = "0" * 64
            return result
        self.client.call = wrong
        for action, key in ((self.client.submit, "inspect"), (self.client.cancel_job, "inspect"),
                            (self.client.reconcile, "observe"), (self.client.cancel_reconcile, "observe")):
            with self.subTest(action=action.__name__):
                self.assert_error("CONFLICT", action, key)

    def test_prepared_reference_requires_success_and_seal(self):
        for evidence in ("STAGING", "DURABILITY_UNKNOWN", "FAILED"):
            self.assert_error("NOT_SEALED", self.client.prepared_reference,
                              {"outcome": "SUCCEEDED", "evidence": evidence, "outputs": {"prepared_ref": "prepared"}})
        origin = "12345678-1234-4234-8234-123456789abc"
        status = {"operation_id": origin, "outcome": "SUCCEEDED", "evidence": "SEALED", "outputs": {
            "schema_version": "lh-prepared-output-v1", "prepared_ref": "prepared",
            "source_commit": "6bd6acfbe5c35d581891eb87275e1173e17848fc", "source_operation_id": origin,
            "seal_ref": "seal-fixture", "bindings": {k: "a" * 64 for k in
                ("source_digest", "wheel_digest", "installed_payload_digest", "runtime_digest", "environment_fingerprint")}}}
        self.assertEqual(self.client.prepared_reference(status), "prepared")
        for key in status["outputs"]["bindings"]:
            damaged = copy.deepcopy(status)
            del damaged["outputs"]["bindings"][key]
            self.assert_error("IO_UNCERTAIN", self.client.prepared_reference, damaged)
        status["outputs"]["source_commit"] = "0" * 40
        self.assert_error("CONFLICT", self.client.prepared_reference, status)

    def test_world_readable_journal_is_rejected(self):
        self.client.journal.chmod(0o755)
        self.assert_error("UNAUTHORIZED", workflow.Workflow, self.host, self.client.journal, self.admission)


if __name__ == "__main__":
    unittest.main()
