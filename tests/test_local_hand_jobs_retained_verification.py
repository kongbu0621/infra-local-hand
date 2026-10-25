"""Linux job retention: real SQLite/sealed bytes and authenticated routing."""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from local_hand_jobs import cli, maintenance, retained_probe, startup
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError
from local_hand_jobs.state import StateStore
from local_hand_jobs.policy import Policy
from local_hand_mcp.resident import ResidentBroker
from admin.local_hand_deploy.runtime import PlanningEnvironment
import test_local_hand_jobs_integration as integration_fixtures


def production_fixture():
    """Real production storage layout; only the task process is synthetic."""
    class Fixture(integration_fixtures.JobIntegrationTests):
        def open_backend(self, initialize=False):
            self.policy = Policy(copy.deepcopy(self.config))
            self.registry = integration_fixtures.Registry()
            for name in ("state", "authority", "work", "job-evidence", "temporary", "source-cache", "build-cache"):
                (self.root / name).mkdir(mode=0o700)
            for name in ("synthetic-python", "synthetic-broker.py"):
                (self.root / name).write_text("# synthetic execution fixture\n")
                (self.root / name).chmod(0o600)
            anchor = self.root / "authority" / "authority.json"
            anchor.write_text(json.dumps({"authority_id": self.policy.authority_id,
                "ledger_id": "synthetic-ledger", "state_root": self.policy.broker_root}))
            anchor.chmod(0o600)
            self.manager = integration_fixtures.SyntheticManager(self.root)
            self.manager.scan = lambda units: {"status": "READY"}
            self.broker = cli._compose_broker(self.policy, self.manager, initialize=initialize)
            self.state, self.store = self.broker.state, self.broker.evidence
            self.runner = self.broker.runner
            self.manager.store = self.store
        def tearDown(self):
            if self.broker is not None:
                cli.close_service(self.broker, None)
                self.broker = self.state = None
            super().tearDown()
    return Fixture()


class RetainedReadbackTests(unittest.TestCase):
    def setUp(self):
        self.f = integration_fixtures.JobIntegrationTests(); self.f.setUp(); self.addCleanup(self.f.tearDown)
        self.status = self.f.run_job("retained-probe", "host.inspect")
        self.state = StateStore(self.f.state.path, self.f.policy.authority_id, "synthetic-ledger", read_only=True)
        self.addCleanup(self.state.close)
        self.broker = Broker(self.state, self.f.policy, self.f.registry, None, evidence=self.f.store)
        self.addCleanup(self.broker.close)
        def authorize(principal, operation):
            with self.state.transaction() as tx:
                self.broker._row(tx, "job", operation, principal, "lh:evidence")
        self.f.store.authorize = authorize
        self.events = self.f.state.events("job", self.status["operation_id"])
        self.starts = list(self.f.manager.started)

    def call(self, request):
        return retained_probe.handle(self.broker, request)

    def capture(self, call=None, **kwargs):
        return retained_probe.collect(call or self.call, deadline=time.monotonic()+10, **kwargs)

    def test_exact_full_byte_readback_does_not_execute_or_write_original_ledger(self):
        snapshot = self.capture()
        self.assertEqual(1, len(snapshot["tasks"]))
        self.assertEqual(3, len(snapshot["tasks"][0]["artifacts"]))
        self.assertGreater(snapshot["bytes_verified"], 0)
        self.assertEqual(snapshot, self.capture())
        self.assertEqual(self.events, self.f.state.events("job", self.status["operation_id"]))
        self.assertEqual(self.starts, self.f.manager.started)

    def test_result_identity_survives_new_mcp_route_without_hiding_conflicts(self):
        snapshot = self.capture()
        # The first MCP may replace a stopped-manager reader or expose the
        # same old ledger twice; neither may change the comparison identity.
        self.assertEqual(snapshot, retained_probe.merge_readbacks([snapshot, copy.deepcopy(snapshot)]))
        changed = copy.deepcopy(snapshot)
        changed["tasks"][0]["status_digest"] = "0" * 64
        with self.assertRaisesRegex(JobError, "disagree"):
            retained_probe.merge_readbacks([snapshot, changed])

    def test_inventory_releases_new_readers_without_caching_unused_preparations(self):
        catalog = self.f.root / "catalog"
        catalog.mkdir(mode=0o700)
        operation = "11111111-1111-4111-8111-111111111111"
        (catalog / (operation + ".json")).write_text(json.dumps({
            "operation_id": operation, "state": "READY", "policy_path": "original-ready"}))
        closed = []
        class EmptyState:
            def transaction(self):
                from contextlib import nullcontext
                return nullcontext(self)
            def execute(self, *_): return self
            def fetchall(self): return []
            def close(self): closed.append("state")
        reader = SimpleNamespace(read_only=True, state=EmptyState(), policy=self.f.policy,
            close=lambda: closed.append("reader"),
            authority_lock=SimpleNamespace(close=lambda: closed.append("authority")))
        self.broker.authority_lock = SimpleNamespace(close=lambda: None)
        adapter = ResidentBroker(self.broker, {"retained": [], "catalog": str(catalog)}, None, lambda _: reader)
        # The descriptor UID gate is covered by its own root fixtures; this
        # nonroot case exercises ownership and lifetime of newly opened readers.
        descriptor = patch("local_hand_jobs.retained_probe.read_descriptor",
                           side_effect=lambda path: json.loads(Path(path).read_bytes()))
        descriptor.start(); self.addCleanup(descriptor.stop)
        # Index acquires the same adapter lock as ordinary routing, and must
        # release new authority descriptors even if an unrelated route fails.
        for broken in (False, True):
            closed.clear()
            with self.subTest(broken=broken):
                if broken:
                    with patch.object(reader.state, "fetchall", side_effect=JobError("CONFLICT", "ledger damaged")), self.assertRaises(JobError):
                        retained_probe.index(adapter)
                else:
                    self.assertEqual(1, len(retained_probe.index(adapter)))
                self.assertEqual({}, adapter.readers)
                self.assertEqual(["reader", "state", "authority"], closed)

    def test_actual_guarded_unix_endpoint_reaches_selected_read_route(self):
        if os.geteuid() != 0:
            self.skipTest("Root-only deployment verifier; independent nonroot rejection also tested")
        path = self.f.root / "verification.sock"
        self.broker.deployment_proof = {**startup.instance(os.getpid()), "component": "mcp", "protocol_ready": True,
            "node_id": "node", "deployment_digest": "a"*64, "configuration_digest": "b"*64, "payload_digest": "c"*64}
        server = cli.MaintenanceServer(self.broker, path, {})
        self.addCleanup(server.close); server.start()
        environment = PlanningEnvironment({"probes": {"mcp": {"kind": "mcp", "socket": str(path), "peer_uid": os.geteuid()}}})
        snapshot = self.capture(lambda request: environment._probe("mcp", retention=request)["readback"])
        self.assertEqual(self.capture(), snapshot)
        self.assertEqual(self.events, self.f.state.events("job", self.status["operation_id"]))

    def test_budget_refuses_before_requesting_any_artifact_bytes(self):
        calls = []
        def call(request):
            calls.append(request.get("tool")); return self.call(request)
        with self.assertRaises(JobError) as caught:
            self.capture(call, maximum_bytes=0)
        self.assertEqual("LIMIT_EXCEEDED", caught.exception.code)
        self.assertNotIn("lh_evidence_read_chunk", calls)

    def test_corrupted_full_stream_not_hidden_by_valid_chunk_hashes(self):
        import base64
        def call(request):
            result = self.call(request)
            if request.get("tool") == "lh_evidence_read_chunk":
                raw = base64.b64decode(result["data_base64"])
                raw = bytes([raw[0] ^ 1]) + raw[1:]
                result.update(data_base64=base64.b64encode(raw).decode(), chunk_sha256=hashlib.sha256(raw).hexdigest())
            return result
        with self.assertRaisesRegex(JobError, "full-byte digest"):
            self.capture(call)

    def test_private_root_protocol_still_rejects_owner_change_and_all_writes(self):
        request = {"action": "deployment_retention_read", "principal_id": "other", "tool": "lh_job_status",
                   "arguments": {"operation_id": self.status["operation_id"]}}
        with self.assertRaises(JobError) as caught:
            self.call(request)
        self.assertEqual("UNAUTHORIZED", caught.exception.code)
        for tool in ("lh_job_prepare", "lh_job_submit", "lh_job_cancel", "lh_job_reconcile"):
            with self.assertRaises(JobError):
                self.call(dict(request, tool=tool, principal_id="owner"))
        self.assertFalse(retained_probe.private_verification())
        self.assertEqual(self.starts, self.f.manager.started)

    def test_private_probe_does_not_exhaust_owner_interactive_rate_budget(self):
        self.broker._rates.clear()
        self.capture(); self.capture()
        self.assertEqual({}, self.broker._rates)
        self.broker.call("lh_job_status", {"operation_id": self.status["operation_id"]}, self.f.owner)
        self.assertEqual(1, len(self.broker._rates["owner"]))

    def test_snapshot_rejects_original_status_drift(self):
        calls = 0
        def call(request):
            nonlocal calls
            result = self.call(request)
            if request.get("tool") == "lh_job_status":
                calls += 1
                if calls > 1: result = dict(result, outcome="UNKNOWN")
            return result
        with self.assertRaisesRegex(JobError, "changed during"):
            self.capture(call)

    def test_current_reader_admission_does_not_rewrite_original_writer_identity(self):
        identity = {"source_commit": "f"*40, "installed_payload_digest": "e"*64, "execution_entrypoint": cli.__file__}
        original = (self.f.policy.source_commit, self.f.policy.installed_payload_digest)
        with patch("local_hand_jobs.deployment.verify_release", return_value=identity) as verify, \
                patch("local_hand_jobs.policy.Policy.from_file", return_value=self.f.policy), \
                patch.object(cli, "_compose_broker", return_value=self.broker) as compose:
            reader = cli.create_retained_broker("original-policy", actual_entrypoint=cli.__file__, reader_identity=identity)
        self.assertIs(reader, self.broker)
        self.assertEqual(original, (reader.policy.source_commit, reader.policy.installed_payload_digest))
        compose.assert_called_once_with(self.f.policy, None, quota_required=True, read_only=True)
        self.assertEqual(identity["source_commit"], verify.call_args.kwargs["expected_source_commit"])
        with patch("local_hand_jobs.deployment.verify_release", side_effect=JobError("PROVENANCE_MISMATCH", "wrong runtime")), \
                patch.object(cli, "_compose_broker") as compose, self.assertRaises(JobError):
            cli.create_retained_broker("original-policy", actual_entrypoint=cli.__file__, reader_identity=identity)
        compose.assert_not_called()


class RetainedCompositionTests(unittest.TestCase):
    def test_offline_reader_preserves_old_v1_owner_without_inventing_v2_policy(self):
        from admin.local_hand_deploy.retained_reader import data_identity
        from admin.local_hand_deploy.model import DeployError
        import pwd
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            policy = {'broker_root': directory}
            self.assertEqual((os.geteuid(), pwd.getpwuid(os.geteuid()).pw_gid), data_identity(policy))
            self.assertEqual({'broker_root': directory}, policy)
            original = {'uid': os.geteuid(), 'gid': os.getegid()}
            self.assertEqual((os.geteuid(), os.getegid()), data_identity({**policy, 'process_manager': original}))
            with self.assertRaises(DeployError):
                data_identity({**policy, 'process_manager': {**original, 'uid': os.geteuid()+1}})
            Path(directory).chmod(0o755)
            with self.assertRaises(DeployError):
                data_identity(policy)

    def test_reader_cleanup_releases_all_resources_and_preserves_primary_error(self):
        closed = []
        def bad_close(name):
            closed.append(name)
            raise OSError("secondary cleanup failure")
        def reader(name):
            return SimpleNamespace(close=lambda: bad_close(name),
                state=SimpleNamespace(close=lambda: closed.append(name + " state")),
                authority_lock=SimpleNamespace(close=lambda: closed.append(name + " lock")))
        for primary in (False, True):
            closed.clear()
            with self.subTest(primary=primary):
                with self.assertRaisesRegex(JobError if primary else OSError,
                                            "primary read failure" if primary else "secondary cleanup"):
                    with retained_probe.owned_readers() as temporary:
                        temporary(lambda: reader("first"))
                        temporary(lambda: reader("second"))
                        if primary:
                            raise JobError("CONFLICT", "primary read failure")
                self.assertEqual(["second", "second state", "second lock", "first", "first state", "first lock"], closed)

    def test_new_reader_composes_original_policy_ledger_and_artifacts_without_writes(self):
        f = production_fixture(); f.setUp(); self.addCleanup(f.tearDown)
        status = f.run_job("prior-writer", "host.inspect")
        policy = f.root / "original-policy.json"
        policy.write_text(json.dumps(f.config)); policy.chmod(0o600)
        cli.close_service(f.broker, None); f.broker = f.state = None
        paths = [policy, *(f.root / "state").rglob("*")]
        original = {str(p): p.read_bytes() for p in paths if p.is_file()}
        identity = {"source_commit": "f"*40, "installed_payload_digest": "e"*64, "execution_entrypoint": cli.__file__}
        with patch("local_hand_jobs.deployment.verify_release", return_value=identity):
            reader = cli.create_retained_broker(policy, actual_entrypoint=cli.__file__, reader_identity=identity)
        try:
            result = retained_probe.collect(lambda r: retained_probe.handle(reader, r), deadline=time.monotonic()+10)
            self.assertEqual(status["operation_id"], result["tasks"][0]["operation_id"])
            self.assertEqual(3, len(result["tasks"][0]["artifacts"]))
            self.assertIsNone(reader.runner)
            self.assertEqual("a"*40, reader.policy.source_commit)
            self.assertEqual(original, {str(p): p.read_bytes() for p in paths if p.is_file()})
        finally:
            cli.close_service(reader, None)
