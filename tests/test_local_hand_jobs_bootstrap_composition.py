"""Production composition with real policy/ledger/root bindings and simulated OS."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from local_hand_jobs import bootstrap_roots
from local_hand_jobs.cli import _admitted_evidence_store, _known_manager_units, create_broker
from local_hand_jobs.contract import JobError, Principal, TOOL_SCOPES, request_digest
from local_hand_jobs.evidence import EvidenceStore, EvidenceError
from local_hand_jobs.policy import Policy, thaw
from local_hand_jobs.registry import Registry
from local_hand_jobs.state import StateStore
from test_local_hand_jobs_contract import submit_fixture
from test_local_hand_jobs_policy import policy_fixture


def binding(path):
    path.mkdir(mode=0o700, parents=True)
    info = path.stat()
    return {"path": str(path), "device": info.st_dev, "inode": info.st_ino, "uid": info.st_uid}


class BootstrapCompositionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.config = policy_fixture(self.root)
        profile = self.config["profiles"]["fixture"]
        profile["bootstrap_slots"] = [{"slot_id": "slot-1", "roots": {
            name: binding(Path(profile[name + "_root"]) / "slot-1")
            for name in ("work", "temporary", "evidence")}}]
        profile["bootstrap_evidence_store"] = binding(self.root / "retained-artifacts")
        self.policy = Policy(self.config)

    def _state_with_intent(self):
        Path(self.policy.broker_root).mkdir(mode=0o700)
        Path(self.policy.authority_root).mkdir(mode=0o700)
        anchor = Path(self.policy.authority_root) / "authority.json"
        anchor.write_text(json.dumps({"authority_id": self.policy.authority_id,
            "ledger_id": "fixture-ledger", "state_root": self.policy.broker_root}))
        anchor.chmod(0o600)
        state = StateStore(Path(self.policy.broker_root) / "jobs.sqlite", self.policy.authority_id,
                           "fixture-ledger", initialize=True)
        request = submit_fixture("host.inspect")
        request["expected"] = self.policy.expected("fixture")
        request["request_digest"] = request_digest(request)
        principal = Principal("owner", frozenset(TOOL_SCOPES.values()))
        plan = thaw(Registry().resolve(request, self.policy, principal=principal))
        with state.transaction() as tx:
            row = state.insert(tx, "job", request["operation_id"], request["operation_id"], "owner",
                               request["request_digest"], request, plan, plan["reservation_bytes"])
            allocation = bootstrap_roots.reserve(state, tx, row, "preflight",
                self.config["profiles"]["fixture"]["bootstrap_slots"])
            execution = allocation["execution_id"]
            unit = "lhj-" + hashlib.sha256(execution.encode()).hexdigest() + ".service"
            state.update(tx, "job", request["operation_id"], "EXECUTION_INTENT", {
                "handles": {"preflight": {"execution_id": execution, "unit": unit,
                    "manager": {"version": 2, "bootstrap": {"unit": "foreign.service"}}}}})
            row = state.get("job", request["operation_id"], tx)
        state.close()
        return row, allocation

    def test_factory_inventories_both_derived_units_and_binds_exact_external_store(self):
        row, allocation = self._state_with_intent()
        manager = Mock()
        manager.support.return_value = {"supported": True}
        manager.scan.return_value = {"status": "READY"}
        with patch("local_hand_jobs.policy.Policy.from_file", return_value=self.policy), \
                patch("local_hand_jobs.deployment.verify_release"), \
                patch("local_hand_jobs.resources.verify_local_filesystem"), \
                patch("local_hand_jobs.runner.SystemdManager", return_value=manager):
            broker = create_broker("synthetic", actual_entrypoint=self.policy.execution_entrypoint)
        try:
            known = manager.scan.call_args.args[0]
            execution = allocation["execution_id"]
            self.assertEqual(set(known), {"lhj-" + hashlib.sha256(value.encode()).hexdigest() + ".service"
                                         for value in (execution, execution + ":bootstrap")})
            self.assertNotIn("foreign.service", known)
            admitted = self.config["profiles"]["fixture"]["bootstrap_evidence_store"]
            self.assertEqual(broker.evidence.root, Path(admitted["path"]))
            self.assertEqual(broker.evidence.root_identity, {key: admitted[key] for key in ("device", "inode", "uid")})
            self.assertFalse((Path(self.policy.broker_root) / "artifacts").exists())
        finally:
            broker.close()
            broker.state.close()
            broker.authority_lock.close()

    def test_inventory_does_not_admit_a_bootstrap_without_valid_durable_allocation(self):
        row, allocation = self._state_with_intent()
        for mutation in ("missing", "changed", "foreign_execution"):
            value = copy.deepcopy(row)
            if mutation == "missing": value["record"]["bootstrap_grants"] = {}
            elif mutation == "changed": value["record"]["bootstrap_grants"]["preflight"]["grant_digest"] = "0" * 64
            else: value["record"]["handles"]["preflight"]["execution_id"] = "foreign"
            with self.subTest(mutation=mutation), self.assertRaises(JobError):
                _known_manager_units([value])

    def test_bootstrap_profiles_require_one_exact_store_but_legacy_remains_readable(self):
        missing = copy.deepcopy(self.config)
        del missing["profiles"]["fixture"]["bootstrap_evidence_store"]
        with self.assertRaisesRegex(JobError, "require an admitted"):
            _admitted_evidence_store(Policy(missing))
        mismatch = copy.deepcopy(self.config)
        second = copy.deepcopy(mismatch["profiles"]["fixture"])
        second["bootstrap_slots"] = [{"slot_id": "slot-2", "roots": {
            name: binding(Path(second[name + "_root"]) / "slot-2")
            for name in ("work", "temporary", "evidence")}}]
        second["bootstrap_evidence_store"] = binding(self.root / "different-artifacts")
        mismatch["profiles"]["second"] = second
        with self.assertRaisesRegex(JobError, "same exact"):
            _admitted_evidence_store(Policy(mismatch))
        legacy = Policy(policy_fixture(self.root))
        path, identity = _admitted_evidence_store(legacy)
        self.assertEqual(path, Path(legacy.broker_root) / "artifacts")
        self.assertIsNone(identity)

    def test_admitted_evidence_store_never_creates_and_rechecks_held_identity(self):
        admitted = self.config["profiles"]["fixture"]["bootstrap_evidence_store"]
        identity = {key: admitted[key] for key in ("device", "inode", "uid")}
        callbacks = {"snapshot_provider": lambda operation: None, "register_seal": lambda record: None,
                     "is_registered": lambda *args: False}
        root = Path(admitted["path"])
        with patch.object(Path, "mkdir", side_effect=AssertionError("admitted root creation")):
            store = EvidenceStore(root, root_identity=identity, **callbacks)
        replacement = root.with_name("old-artifacts")
        root.rename(replacement)
        root.mkdir(mode=0o700)
        with self.assertRaisesRegex(EvidenceError, "admitted identity"):
            with store._open_store(): pass
        with self.assertRaisesRegex(EvidenceError, "admitted identity"):
            EvidenceStore(root, root_identity=identity, **callbacks)
        missing = self.root / "must-not-create"
        with self.assertRaises((EvidenceError, OSError)):
            EvidenceStore(missing, root_identity=identity, **callbacks)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
