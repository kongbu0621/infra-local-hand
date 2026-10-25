"""Data-only bindings, public exit semantics and durable security repair scope."""
import contextlib
import copy
import io
import unittest
from unittest.mock import Mock, patch

import test_local_hand_deploy_runtime as fixture
import test_local_hand_deploy_coordinator as control
from admin.local_hand_deploy import cli
from admin.local_hand_deploy.binding import BINDING_SCHEMA, RELEASE_SCHEMA, release_plan
from admin.local_hand_deploy.model import DeployError, digest, seal_plan
from admin.local_hand_deploy.planner import build_plan, validate_profile
from admin.local_hand_deploy.report import report
from admin.local_hand_deploy.runtime import ConcreteEnvironment


def safety_spec():
    return {"authority": "fixture.invalid", "checks": [
        {"path": "/mcp", "statuses": [401], "purpose": "anonymous_protected"},
        {"path": "/admin/", "statuses": [404], "purpose": "management_hidden"},
        {"path": "/issuer", "statuses": [200], "purpose": "issuer_metadata",
         "json_equals": {"issuer": "https://fixture.invalid/issuer"}},
        {"path": "/resource", "statuses": [200], "purpose": "resource_metadata",
         "json_equals": {"resource": "https://fixture.invalid/mcp", "authorization_servers": ["https://fixture.invalid/issuer"]}}]}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.RuntimeTests(methodName="runTest")
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.binding = {"schema": BINDING_SCHEMA, "node_id": "node", "state": str(f.root / "state"), "profile": f.profile}
        self.release = {"schema": RELEASE_SCHEMA, "node_id": "node", "request_id": "one",
                        "target": f.target, "files": f.manifest["files"]}

    def test_binding_plan_observes_generated_source_and_is_read_only(self):
        f = self.fixture
        source = copy.deepcopy(f.source["selection"])
        source["decision_id"] = "actual-import-decision"
        f.write(f.selection, source)
        before = {p: (p.stat().st_ino, p.stat().st_mtime_ns) for p in f.root.rglob("*")}
        result = release_plan(self.binding, self.release)
        self.assertEqual(source, result["source"]["selection"])
        self.assertEqual(before, {p: (p.stat().st_ino, p.stat().st_mtime_ns) for p in f.root.rglob("*")})
        self.assertEqual(["file"], [item["kind"] for item in result["steps"]])

    def test_other_node_callback_and_private_installer_are_not_binding_inputs(self):
        for key, value in (("node_id", "other"), ("shell", "false"), ("installer", "/tmp/legacy.py")):
            with self.subTest(key=key), self.assertRaises(DeployError):
                release_plan(self.binding, {**self.release, key: value})

    def test_unfinished_selection_cannot_be_replanned_as_a_new_baseline(self):
        f = self.fixture
        selection = copy.deepcopy(f.source["selection"])
        selection.update(mode="blocked", owner="old-op", decision_id=None)
        f.write(f.selection, selection)
        with self.assertRaisesRegex(DeployError, "unfinished"):
            release_plan(self.binding, self.release)

    def test_binding_executes_through_real_coordinator_and_same_recovery_record(self):
        f = self.fixture
        plan = release_plan(self.binding, self.release)
        store = f.store()
        coordinator = control.Coordinator(store, f.gate, ConcreteEnvironment(plan, store, f.gate))
        first = coordinator.apply(plan)
        self.assertEqual("COMMITTED", first["decision"])
        self.assertTrue(first["released"])
        self.assertEqual(first, coordinator.apply(plan))
        restored = coordinator.rollback(first["id"])
        self.assertTrue(restored["released"])
        self.assertEqual(restored["id"], coordinator.rollback(first["id"])["id"])

    def test_resealed_plan_cannot_move_file_write_before_drain(self):
        f = self.fixture
        plan = release_plan(self.binding, self.release)
        plan["steps"][0]["action"]["phase"] = "isolate"
        plan = seal_plan(plan)
        store = f.store()
        op = control.Coordinator(store, f.gate, ConcreteEnvironment(plan, store, f.gate)).apply(plan)
        self.assertEqual("INVALID_SCHEDULE", op["waiting"]["detail"]["code"])
        self.assertEqual(f.old_config, fixture.json.loads(f.config.read_bytes()))
        self.assertEqual("OPEN", f.gate.snapshot()["state"])

    def test_cli_binding_cannot_be_overridden_and_unpassed_public_is_nonzero(self):
        with patch.object(cli, "read_document", return_value=self.binding), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, cli.main(["--binding", "binding", "--node", "other", "status"]))
        for status, expected in (("PASSED", 0), ("NOT_PASSED", 4), ("SECURITY_FAILED", 4)):
            with self.subTest(status=status), patch.object(cli, "read_document", return_value={}), \
                 patch.object(cli, "check_public", return_value={"status": status}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(expected, cli.main(["check-public", "spec"]))

    def test_six_report_layers_and_stale_client_evidence(self):
        f = self.fixture
        store = f.store(); plan = release_plan(self.binding, self.release)
        op = control.Coordinator(store, f.gate, ConcreteEnvironment(plan, store, f.gate)).apply(plan)
        output = report(op, client={"status": "PASSED", "deployment_digest": f.a, "observed_ns": 1})
        self.assertEqual("STALE", output["client_acceptance"]["status"])
        for layer in ("deployment", "admission", "recovery", "diagnostics", "public_reachability", "client_acceptance"):
            self.assertIn("evidence", output[layer])
        self.assertIsNone(output["public_reachability"]["evidence"]["observed_ns"])

    def security_profile(self):
        f = self.fixture
        profile = copy.deepcopy(f.profile)
        profile.update(gateway={"component": "gateway"}, gateway_checks=safety_spec(), security_repair={
            "unsafe_deployment_digest": f.a, "reason": "anonymous_protected", "evidence_digest": "e" * 64})
        return profile

    def test_security_plan_marks_only_gateway_stop_as_before_drain(self):
        f = self.fixture
        manifest = copy.deepcopy(f.manifest); manifest["profile"] = self.security_profile()
        manifest["source"]["gateway"] = {"present": True, "running": True}
        manifest["target"]["gateway"] = {"present": True, "running": True}
        observer = Mock()
        observer.plan_gateway.return_value = [
            {"kind": "gateway_stop", "target": "gateway", "phase": "quiesced_before_files"},
            {"kind": "gateway_start", "target": "gateway", "phase": "after_create"}]
        plan = build_plan(manifest, observer)
        self.assertEqual(("gateway", "isolate"), (plan["steps"][0]["kind"], plan["steps"][0]["action"]["phase"]))
        self.assertEqual("files", plan["steps"][1]["action"]["phase"])

    def test_safety_repair_cannot_omit_checks_or_bind_other_baseline(self):
        f = self.fixture
        for transform in (lambda p: p.pop("gateway_checks"),
                          lambda p: p["security_repair"].update(unsafe_deployment_digest=f.b),
                          lambda p: p["gateway_checks"]["checks"].pop()):
            profile = self.security_profile(); transform(profile)
            with self.assertRaises(DeployError): validate_profile(profile, f.source, f.target)

    def test_unsafe_rollback_cannot_publish_stable_or_release(self):
        f = self.fixture
        plan = build_plan(f.manifest)
        plan["profile"] = self.security_profile(); plan = seal_plan(plan)
        store = f.store()
        with store.locked():
            op = store.create(plan)
            op.update(decision="ROLLED_BACK", decision_id="decision", gate_owned=True)
            f.gate.close(op["id"])
            env = ConcreteEnvironment(plan, store, f.gate)
            self.assertEqual({"passed": False, "reason": "UNSAFE_BASELINE_REQUIRES_REPAIR"}, env.release_valid(op))
            with self.assertRaises(DeployError): env.restored_plan(op, "unsafe-rollback")
        self.assertEqual("CLOSED", f.gate.snapshot()["state"])


class SecurityRecoveryTests(unittest.TestCase):
    def test_isolation_survives_drain_wait_and_process_loss_without_repeating(self):
        f = control.CoordinatorTests(methodName="runTest"); f.setUp(); self.addCleanup(f.doCleanups)
        planned = control.plan()
        planned["steps"].insert(0, {"id": "isolate", "kind": "gateway", "action": {
            "key": "gateway", "before": "open", "after": "closed", "phase": "isolate"}})
        planned["profile"]["security_repair"] = {"unsafe_deployment_digest": digest("old")}
        planned = seal_plan(planned)
        f.effects.actual["gateway"] = "open"; f.effects.drain_ready = False
        failed = f.coordinator.apply(planned)
        self.assertEqual("DRAIN", failed["waiting"]["reason"])
        self.assertEqual("old", f.effects.actual["config"])
        self.assertEqual("closed", f.effects.actual["gateway"])
        self.assertEqual("CLOSED", f.gate.snapshot()["state"])
        f.effects.drain_ready = True
        final = control.Coordinator(f.store, f.gate, f.effects).resume(failed["id"])
        self.assertEqual("COMMITTED", final["decision"])
        self.assertEqual(1, f.effects.changes.count(("gateway", "closed")))


if __name__ == "__main__": unittest.main()
