"""Real A2 helper output through broker sealing and authenticated readback.

OS namespace/cgroup observations and Ledger's smoke payload are synthetic.
Runtime byte verification, subprocess capture, result validation, Registry,
SQLite, evidence publication and download are real. This is not field evidence.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

if sys.platform != "linux":
    raise unittest.SkipTest("Local A2 helper requires Linux")

from local_hand_jobs import local_a2_jobs as a2, result_reader, runner
from local_hand_jobs.contract import DISABLED_JOB_KINDS, request_digest
from local_hand_jobs.evidence_client import BoundedFileWriter, EvidenceClient, verify_local_bundle
import test_local_hand_jobs_integration as integration
from test_local_hand_jobs_contract import submit_fixture
from test_local_hand_jobs_local_a2_runtime import synthetic_runtime


class HelperManager(integration.SyntheticManager):
    """Model only host supervision; preserve the actual helper's complete result."""

    def start(self, handle, plan, cancel):
        if plan["phase"] == "evidence":
            return super().start(handle, plan, cancel)
        with self.lock:
            self.started.append((handle["execution_id"], copy.deepcopy(plan)))
        try:
            execution = copy.deepcopy(plan["execution"])
            execution.update(phase=plan["phase"], execution_id=handle["execution_id"],
                budgets=plan["budgets"], budget_grant=plan["budget_grant"],
                parent_mount_namespace="synthetic-original-namespace")
            for root in execution["roots"].values():
                Path(root).mkdir(mode=0o700, parents=True, exist_ok=True)
            target = Path(execution["roots"]["evidence"]) / result_reader.result_name(handle["execution_id"])
            execution["result_path"] = str(target)
            readlink = os.readlink
            mount = dict(source="SYNTHETIC_FILESYSTEM_OBSERVATION", root="/", type="ext4", options="ro")
            with patch.dict(os.environ, dict(os.environ)), patch.object(tempfile, "tempdir", None), \
                    patch.object(os, "readlink", side_effect=lambda p, *a, **k:
                        "synthetic-private-namespace" if str(p) == "/proc/self/ns/mnt" else readlink(p, *a, **k)), \
                    patch.object(os, "access", return_value=False), \
                    patch.object(runner, "_mount_for", return_value=mount), \
                    patch.object(runner, "_verify_cgroup_limits", return_value={"verification_class": "SYNTHETIC"}):
                code = runner._helper(execution)
            output = result_reader._result(json.loads(target.read_bytes()), handle["execution_id"], plan["phase"])
            proof = dict(state="EXITED", execution_id=handle["execution_id"], exit_code=code,
                future_start_blocked=True, tree_exited=True, collectors_stopped=True, writers_stopped=True,
                effects_checked=output["effects_checked"], helper_result_verified=True,
                facts=output["facts"], result=output)
            with self.lock:
                self.proofs[handle["execution_id"]] = proof
            return dict(handle)
        except BaseException as error:
            self.errors.append(error)
            raise


class LocalA2EvidenceTests(unittest.TestCase):
    def setUp(self):
        # HelperManager runs the helper directly, without systemd applying
        # runner's UMask=0077. Match that boundary and restore the caller's
        # setting so this test does not depend on the invoking shell.
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)

    def test_real_registry_helper_result_is_sealed_and_read_back_with_all_bindings(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        descriptor, blobs = synthetic_runtime(root / "inputs")
        # The smoke program's report is explicitly synthetic. Its bytes remain
        # pinned and actually executed; no verify_inputs/scope check is mocked.
        script = """import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--scratch-parent');p.add_argument('--source-commit');a=p.parse_args()
work=pathlib.Path(a.scratch_parent)/'a2-installed-synthetic';work.mkdir()
report=REPORT
report.update(work_dir=str(work),source_commit=a.source_commit)
print(json.dumps(report,sort_keys=True))
"""
        report = dict(result="PASS", python="SYNTHETIC_SMOKE", sqlite="SYNTHETIC_SMOKE", platform="SYNTHETIC_SMOKE",
            package_version="0.2.0a1", module_path=str(Path(descriptor["package_root"]) / "__init__.py"),
            source_commit_evidence=a2.SOURCE_EVIDENCE,
            wheel_bytes_evidence="NOT_ATTESTED_BY_THIS_SMOKE_TOOL; bind wheel digest separately",
            calls=[dict(entry=entry, operation=operation, status="PASS") for entry in ("api", "cli")
                   for operation in ("create", "verify", "restore", "check_restore")],
            nas_publish_flow="NOT_RUN", nas_capability_acceptance="NOT_ATTESTED", nas_loss_exercise="NOT_RUN")
        raw = script.replace("REPORT", repr(report)).encode()
        (Path(descriptor["source_root"]) / a2.SCRIPT_FILE).write_bytes(raw)
        blobs[a2.SCRIPT_FILE] = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        descriptor["source_blobs"] = blobs
        original_config = integration._config

        def config(path):
            value = original_config(path)
            profile = value["profiles"]["fixture"]
            profile["local_a2_runtimes"] = {"installed-a2": descriptor}
            profile["budgets"][a2.KIND].update(nas_bytes=0, wall_seconds=60)
            access = value["principals"]["owner"]["profiles"]["fixture"]
            access["kinds"].append(a2.KIND)
            access["runtime_refs"] = ["installed-a2"]
            return value

        with patch.object(a2, "SOURCE_BLOBS", blobs), patch.object(integration, "_config", config), \
                patch.object(integration, "SyntheticManager", HelperManager):
            case = integration.JobIntegrationTests()
            case.setUp()
            try:
                # Seed an admission from before retirement. All execution,
                # sealing and retrieval below use the current disabled policy.
                request = submit_fixture(a2.KIND, runtime_ref="installed-a2")
                request.update(expected=case.policy.expected('fixture'), expires_at=int(time.time()) + 300)
                request['request_digest'] = request_digest(request)
                case.client._save(case.client._record_name('job', 'installed-a2'),
                    dict(authority_id=case.policy.authority_id, request=request))
                with patch('local_hand_jobs.broker.DISABLED_JOB_KINDS', DISABLED_JOB_KINDS - {a2.KIND}):
                    case.broker.submit(request, case.owner)
                status = case.finish(request['operation_id'])
                operation = status["operation_id"]
                row = case.state.get("job", operation)
                original_plan = row["plan"]["execution"]
                self.assertEqual(3, len(case.manager.started))
                self.assertTrue(row["record"]["facts"]["local_a2_runtime_verified"])
                self.assertTrue(row["record"]["facts"]["installed_bytecode_verified"])
                page = case.callback("lh_evidence_manifest", {"operation_id": operation})
                artifacts = {item["role"]: item for item in page["artifacts"]}
                client = EvidenceClient(case.callback)
                writer = BoundedFileWriter(case.root / "a2-downloads", max_bytes=8 * 1024**2)
                downloaded = {role: client.download(artifact, writer).read_bytes()
                              for role, artifact in artifacts.items()}
                zip_artifact = artifacts["zip"]
                verify_local_bundle(downloaded["zip"], downloaded["manifest"], downloaded["seal"],
                    operation_id=operation, seal_id=zip_artifact["seal_id"], seal_sha256=zip_artifact["seal_sha256"])
                manifest = json.loads(downloaded["manifest"])
                bindings = manifest["bindings"]
                for key, value in original_plan["bindings"].items():
                    self.assertEqual(value, bindings[key], key)
                for key in ("installed_payload_digest", "runtime_python_digest", "console_script_digest", "environment_fingerprint"):
                    self.assertEqual(64, len(bindings[key]), key)
                import io
                with zipfile.ZipFile(io.BytesIO(downloaded["zip"])) as archive:
                    results = [json.loads(archive.read(name)) for name in archive.namelist()
                               if name.startswith("result-") and name.endswith(".json")]
                    business = next(item for item in results if item["phase"] == "business")
                    self.assertEqual("SUCCEEDED", business["outcome"])
                    self.assertEqual(bindings, business["bindings"])
                    self.assertEqual(report["calls"], business["local_a2"]["report"]["calls"])
                    self.assertEqual("NOT_RUN", business["local_a2"]["report"]["nas_publish_flow"])
                    self.assertEqual("SYNTHETIC_FILESYSTEM_OBSERVATION",
                        business["facts"]["environment"]["filesystems"]["work"]["source"])
                    self.assertIn("BROKER_EVENTS.json", archive.namelist())
                    self.assertIn("STOP_PROOF.json", archive.namelist())
                    self.assertTrue(any(name.endswith("a2-installed-local.stdout") for name in archive.namelist()))
                    self.assertTrue(any(name.endswith("a2-runtime-bytecode.stdout") for name in archive.namelist()))
                before = case.state.events("job", operation)
                repeated = case.callback('lh_job_submit', request)
                for key in ("operation_id", "outcome", "evidence", "seal_refs"):
                    self.assertEqual(status[key], repeated[key])
                self.assertEqual(status, case.client.observe(job_key='installed-a2')['latest'])
                self.assertEqual(before, case.state.events("job", operation))
                self.assertEqual(3, len(case.manager.started))
            finally:
                case.tearDown()


if __name__ == "__main__":
    unittest.main()
