"""Real protocol/policy/ledger/evidence integration with a synthetic OS manager.

Only the process-manager boundary is simulated. SyntheticManager stands in for
the supervised fixed programs and labels every retained output accordingly.
These tests do not prove the Ledger source programs, real cgroups or NAS work.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from local_hand_jobs.broker import Broker
from local_hand_jobs.cli import MaintenanceServer, request as local_request
from local_hand_jobs.contract import KINDS, SUITES, TOOL_SCOPES, JobError, Principal
from local_hand_jobs.evidence import EvidenceStore, FrozenSnapshot, QuiescenceProof
from local_hand_jobs.evidence_client import BoundedFileWriter, EvidenceClient
from local_hand_jobs.policy import Policy
from local_hand_jobs.registry import Registry, SCRIPT_BLOBS, SOURCE_COMMIT
from local_hand_jobs.runner import Runner
from local_hand_jobs.state import StateStore

_spec = importlib.util.spec_from_file_location("integration_plugin_workflow", ROOT / "plugins/local-hand-a2/scripts/workflow.py")
_workflow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_workflow)


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _config(root):
    budget = {"wall_seconds": 30, "terminate_grace_seconds": 2, "cpu_seconds": 20,
              "memory_bytes": 16 * 1024 * 1024, "processes": 8,
              "temporary_bytes": 1024 * 1024, "nas_bytes": 1024 * 1024,
              "log_bytes": 1024 * 1024, "reservation_bytes": 6 * 1024 * 1024}
    profile = {"work_root": str(root / "work"), "evidence_root": str(root / "job-evidence"),
               "temporary_root": str(root / "temporary"), "python": str(root / "synthetic-python"),
               "sources": {"source": {"root": str(root / "source-cache"), "commit": SOURCE_COMMIT,
                                       "blobs": dict(SCRIPT_BLOBS)}},
               "build_caches": {"cache": {"root": str(root / "build-cache"),
                                           "files": {"fixture.whl": _hash(b"synthetic build cache")}}},
               "storages": {}, "budgets": {kind: dict(budget) for kind in (*KINDS, "reconcile")},
               "resource_ids": ["synthetic-project"]}
    access = {"kinds": [kind for kind in KINDS if kind != "ledger.nas.roundtrip"],
              "source_refs": ["source"], "build_cache_refs": ["cache"], "storage_refs": [],
              "prepared_refs": [], "prepared_access": "owned"}
    return {"schema_version": "lh-policy-v1", "authority_id": "synthetic-integration-authority",
            "node_id": "synthetic-integration-node", "install_uuid": "12345678-1234-4234-8234-123456789abc",
            "deployment_epoch": 1, "generation": 1, "source_commit": "a" * 40,
            "installed_payload_digest": "b" * 64, "execution_entrypoint": str(root / "synthetic-broker.py"),
            "broker_root": str(root / "state"), "authority_root": str(root / "authority"),
            "forbidden_roots": [str(root / "excluded-live")],
            "limits": {"max_queued": 30, "max_running": 2, "retained_bytes": 256 * 1024 * 1024,
                       "ledger_emergency_bytes": 1024 * 1024, "requests_per_minute": 100,
                       "control_response_seconds": 2}, "profiles": {"fixture": profile},
            "principals": {owner: {"scopes": sorted(set(TOOL_SCOPES.values())),
                                   "profiles": {"fixture": copy.deepcopy(access)}} for owner in ("owner", "other")},
            "local_peers": {str(os.getuid()): "owner"}}


class SyntheticManager:
    """Trusted test DI, never a policy/environment-selectable runtime manager.

    Actual authorization, plan resolution, leases, persistent intentions, Runner
    ownership, snapshot freezing, seal registration and download remain real.
    The manager's synthetic bytes are fixtures, not asserted upstream execution.
    """

    def __init__(self, root):
        self.root = Path(root)
        self.store = None
        self.started, self.proofs, self.errors = [], {}, []
        self.lock = threading.Lock()

    def start(self, handle, plan, cancel):
        with self.lock:
            self.started.append((handle["execution_id"], copy.deepcopy(plan)))
        try:
            result, facts = {}, {}
            if cancel.is_set():
                result = {"outcome": "CANCELLED", "business_started": False}
            elif plan["phase"] == "preflight":
                facts = {"inputs_stable": True, "verification_class": "SYNTHETIC_MANAGER"}
            elif plan["phase"] == "evidence":
                value = plan["evidence_snapshot"]
                frozen = FrozenSnapshot(value["operation_id"], value["event_seq"], Path(value["root"]),
                    tuple(sorted(value["members"])), QuiescenceProof(**value["quiescence"]), value["bindings"],
                    value.get("previous_seal_id"), value.get("reconcile_id"), tuple(value["broker_events"]))
                def no_helper_registration(_):
                    raise AssertionError("The publication helper cannot register a ledger seal")
                helper_store = EvidenceStore(self.store.root, snapshot_provider=lambda _: frozen,
                    register_seal=no_helper_registration, is_registered=lambda *_: False)
                result = {"seal_record": helper_store.publish_only(frozen)}
            else:
                result = self._program(handle, plan)
            proof = {"state": "EXITED", "future_start_blocked": True, "tree_exited": True,
                     "collectors_stopped": True, "writers_stopped": True, "effects_checked": True,
                     "exit_code": 0, "facts": facts, "result": result}
            with self.lock:
                self.proofs[handle["execution_id"]] = proof
            return dict(handle)
        except BaseException as exc:
            self.errors.append(exc)
            raise

    def inspect(self, handle):
        with self.lock:
            return copy.deepcopy(self.proofs[handle["execution_id"]])

    def stop(self, handle):
        # These synthetic programs finish before acknowledging their start.
        return self.inspect(handle)

    def _program(self, handle, plan):
        execution = plan["execution"]
        operation = execution["operation_id"]
        if plan["phase"] == "reconcile":
            evidence_root = self.root / "observations" / handle["execution_id"]
        else:
            evidence_root = Path(execution["roots"]["evidence"])
        evidence_root.mkdir(mode=0o700, parents=True)
        # All fixture output is marked synthetic, including the downloaded ZIP.
        transcript = {"verification_class": "SYNTHETIC_MANAGER", "kind": execution["kind"],
                      "phase": plan["phase"], "fixed_stages": execution["stages"]}
        (evidence_root / "commands.json").write_text(json.dumps(transcript, sort_keys=True))
        (evidence_root / "stdout.log").write_bytes(b"SYNTHETIC_MANAGER: fixed-program result fixture\n")
        (evidence_root / "stderr.log").write_bytes(b"")
        bindings = copy.deepcopy(execution["bindings"])
        bindings["environment_fingerprint"] = _hash(b"synthetic integration environment")
        result = {"outcome": "SUCCEEDED", "business_started": plan["phase"] == "business",
                  "side_effects": "SYNTHETIC_FIXTURE_FILES_ONLY", "bindings": bindings,
                  "coverage": "LOGIC_ONLY" if execution["kind"] == "ledger.test.resources" else "PASS",
                  "evidence_snapshot": {"root": str(evidence_root),
                                        "members": ["commands.json", "stdout.log", "stderr.log"]}}
        if execution["kind"] == "ledger.prepare" and plan["phase"] == "business":
            prepared = copy.deepcopy(execution["prepared"])
            root = Path(prepared["root"])
            # Simulated fixed-program output; no fake source program is executed.
            files = {"source/synthetic-source.txt": b"SYNTHETIC_MANAGER source payload",
                     "build-venv/bin/python": b"SYNTHETIC_MANAGER build runtime",
                     "runtime-venv/bin/python": b"SYNTHETIC_MANAGER installed runtime",
                     str(Path(prepared["wheel"]).relative_to(root)): b"SYNTHETIC_MANAGER wheel payload"}
            for relative, data in files.items():
                target = root / relative
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(0o400)
            identity = {"source_digest": _hash(files["source/synthetic-source.txt"]),
                        "wheel_digest": _hash(files[str(Path(prepared["wheel"]).relative_to(root))]),
                        "installed_payload_digest": _hash(files["runtime-venv/bin/python"]),
                        "runtime_digest": _hash(files["build-venv/bin/python"]),
                        "environment_fingerprint": bindings["environment_fingerprint"]}
            prepared.update(source_blobs=dict(SCRIPT_BLOBS), files={name: _hash(data) for name, data in files.items()},
                            readonly_enforced=True, bindings=identity)
            result["bindings"].update(identity)
            result["prepared"] = prepared
        return result


class JobIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = _config(self.root)
        self.owner = Principal("owner", frozenset(TOOL_SCOPES.values()))
        self.calls = []
        self.state = self.broker = self.maintenance = None
        self.open_backend(initialize=True)
        self.admission = {"authority_id": self.policy.authority_id,
                          "profiles": {"fixture": self.policy.expected("fixture")}}
        self.client = _workflow.Workflow(self.callback, self.root / "client-journal", self.admission,
                                         sleep=lambda _: None)

    def tearDown(self):
        if self.maintenance is not None:
            self.maintenance.close()
        if self.broker is not None:
            self.broker.close()
        if self.state is not None:
            self.state.close()
        self.temporary.cleanup()

    def open_backend(self, initialize=False):
        self.policy, self.registry = Policy(copy.deepcopy(self.config)), Registry()
        path = self.root / "state"
        path.mkdir(mode=0o700, exist_ok=True)
        self.state = StateStore(path / "ledger.sqlite", self.policy.authority_id,
                                "synthetic-ledger", initialize=initialize)
        self.manager = SyntheticManager(self.root)
        self.runner = Runner(self.manager)
        self.store = EvidenceStore(self.root / "sealed", snapshot_provider=self.no_direct_seal,
                                    register_seal=lambda record: self.broker.register_seal(record),
                                    is_registered=lambda seal, digest: self.broker.is_registered(seal, digest))
        self.manager.store = self.store
        self.broker = Broker(self.state, self.policy, self.registry, self.runner, evidence=self.store)
        self.broker.recover()

    @staticmethod
    def no_direct_seal(_):
        raise AssertionError("Integration must use supervised publish then broker seal registration")

    def callback(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        return self.broker.call(name, arguments, self.owner)

    def finish(self, operation_id, reconcile_id=None):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.broker.tick()
            if self.manager.errors:
                raise AssertionError(repr(self.manager.errors))
            status = self.broker.status(operation_id, self.owner, reconcile_id)
            if status["lifecycle"] == "TERMINAL":
                self.assertEqual(status["outcome"], "SUCCEEDED", status)
                self.assertEqual(status["evidence"], "SEALED", status)
                return status
            time.sleep(0.005)
        raise AssertionError(status)

    def run_job(self, key, kind, inputs=None):
        self.client.preflight()
        record = self.client.reserve_job(key, kind=kind, profile_ref="fixture", inputs=inputs or {})
        result = self.client.submit(key)
        self.assertEqual(result["operation_id"], record["request"]["operation_id"])
        return self.finish(result["operation_id"])

    def test_seven_tool_chain_delivers_real_sealed_files_from_synthetic_execution(self):
        inspected = self.run_job("inspect", "host.inspect")
        prepared = self.run_job("prepare", "ledger.prepare", {"source_ref": "source", "build_cache_ref": "cache"})
        prepared_ref = self.client.prepared_reference(prepared)
        discovered = self.client.preflight()
        self.assertIn(prepared_ref, discovered["fixture"]["prepared_refs"])
        source = self.run_job("source-test", "ledger.test.source", {"prepared_ref": prepared_ref})
        for suite in SUITES:
            self.run_job(suite.replace("_", "-"), "ledger.test.resources", {"prepared_ref": prepared_ref, "suite": suite})
        self.run_job("installed-local", "ledger.test.installed_local", {"prepared_ref": prepared_ref})
        page = self.callback("lh_evidence_manifest", {"operation_id": source["operation_id"]})
        artifact = next(item for item in page["artifacts"] if item["role"] == "zip")
        delivered = EvidenceClient(self.callback).download(artifact, BoundedFileWriter(self.root / "downloads", max_bytes=2 * 1024 * 1024))
        self.assertEqual(_hash(delivered.read_bytes()), artifact["sha256"])
        self.assertEqual(delivered.stat().st_size, artifact["size"])
        import zipfile
        with zipfile.ZipFile(delivered) as archive:
            self.assertIn("MANIFEST.json", archive.namelist())
            self.assertIn("BROKER_EVENTS.json", archive.namelist())
            self.assertIn("STOP_PROOF.json", archive.namelist())
            commands = json.loads(archive.read("commands.json"))
            self.assertEqual(commands["verification_class"], "SYNTHETIC_MANAGER")
            self.assertEqual(commands["fixed_stages"][0]["argv"][1:], ["-m", "unittest", "discover", "-s", "tests", "-v"])

        # Cancellation and independent reconciliation use the remaining tools.
        self.client.reserve_job("cancelled-inspect", kind="host.inspect", profile_ref="fixture", inputs={})
        accepted = self.client.submit("cancelled-inspect")
        cancelled = self.client.cancel_job("cancelled-inspect")
        self.assertEqual(cancelled["outcome"], "CANCELLED")
        round_record = self.client.reserve_reconcile("observe-cancelled", "cancelled-inspect")
        self.client.reconcile("observe-cancelled")
        self.client.cancel_job("cancelled-inspect")
        observation = self.finish(accepted["operation_id"], round_record["arguments"]["reconcile_id"])
        self.assertFalse(observation["cancel_requested"])
        # Query through the workflow rather than test-only direct ledger access.
        self.client.observe(job_key="inspect")
        self.assertEqual({name for name, _ in self.calls}, set(TOOL_SCOPES))
        self.assertTrue(self.broker.is_registered(artifact["seal_id"], artifact["seal_sha256"]))

    def test_restart_restores_prepared_catalog_and_cross_client_deduplication(self):
        self.run_job("inspect", "host.inspect")
        prepared = self.run_job("prepare", "ledger.prepare", {"source_ref": "source", "build_cache_ref": "cache"})
        ref = self.client.prepared_reference(prepared)
        self.broker.close()
        self.state.close()
        self.open_backend()
        discovered = self.client.preflight()
        self.assertIn(ref, discovered["fixture"]["prepared_refs"])
        retried = self.client.submit("prepare")
        self.assertEqual(retried["outputs"], prepared["outputs"])
        self.assertFalse(self.manager.started)

        second_client = _workflow.Workflow(self.callback, self.client.journal, self.admission, sleep=lambda _: None)
        second_client.preflight()
        self.assertEqual(second_client.submit("prepare")["outputs"]["prepared_ref"], ref)
        self.assertFalse(self.manager.started)
        self.run_job("source-after-restart", "ledger.test.source", {"prepared_ref": ref})
        self.assertEqual([plan["kind"] for _, plan in self.manager.started if plan["phase"] == "business"], ["ledger.test.source"])

    def test_real_maintenance_transport_shares_broker_and_original_identity(self):
        # Keep a host socket restriction separate from the real restart check.
        socket_path = self.root / "maintenance.sock"
        self.maintenance = MaintenanceServer(self.broker, socket_path, {os.getuid(): self.owner})
        try:
            self.maintenance.start()
        except JobError as exc:
            if isinstance(exc.__cause__, PermissionError):
                self.skipTest("UNSUPPORTED: this host forbids the real Unix maintenance socket")
            raise
        prepared = self.run_job("prepare", "ledger.prepare", {"source_ref": "source", "build_cache_ref": "cache"})
        before = len(self.manager.started)
        original = self.client._job("prepare")["request"]
        via_maintenance = local_request(socket_path, "lh_job_submit", original)
        self.assertEqual(via_maintenance["outputs"], prepared["outputs"])
        self.assertEqual(len(self.manager.started), before)

    def test_discovery_and_real_registry_reject_foreign_prepared_use(self):
        prepared = self.run_job("prepare", "ledger.prepare", {"source_ref": "source", "build_cache_ref": "cache"})
        ref = self.client.prepared_reference(prepared)
        other = Principal("other", self.owner.scopes)
        discovery = self.broker.call("lh_capabilities", {}, other)
        self.assertNotIn(ref, discovery["profiles"][0]["prepared_refs"])
        with self.assertRaises(JobError) as caught:
            self.broker.call("lh_job_status", {"operation_id": prepared["operation_id"]}, other)
        self.assertEqual(caught.exception.code, "UNAUTHORIZED")
        before = len(self.manager.started)
        self.broker.revoke("owner")
        with self.assertRaises(JobError) as caught:
            self.client.submit("prepare")
        self.assertEqual(caught.exception.code, "UNAUTHORIZED")
        self.assertEqual(len(self.manager.started), before)


if __name__ == "__main__":
    unittest.main()
