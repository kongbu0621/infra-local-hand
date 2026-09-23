from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs import bootstrap_roots as roots
from local_hand_jobs.contract import JobError, canonical_bytes
from local_hand_jobs.resources import ResourceManager
from local_hand_jobs.state import StateStore


class BootstrapRootTests(unittest.TestCase):
    """Synthetic durable-allocation checks; no production quota claim."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite"
        self.db = StateStore(self.path, "authority", "ledger", initialize=True)
        self.addCleanup(lambda: self.db.close())
        self.parents = {name: "/synthetic/" + name for name in roots.ROOT_NAMES}
        self.slots = [{"slot_id": f"slot-{index}", "roots": {
            name: {"path": f"/synthetic/{name}/slot-{index}", "device": 7,
                   "inode": 100 + 3 * index + offset, "uid": 1234}
            for offset, name in enumerate(sorted(roots.ROOT_NAMES))}}
            for index in range(6)]

    def insert(self, identity="operation-a", namespace="job", parent=None):
        parent = identity if parent is None else parent
        original = {name: f"{root}/{parent}" for name, root in self.parents.items()}
        plan = {"execution": {"roots": original}, "expected": {"deployment_epoch": 1}}
        with self.db.transaction() as tx:
            return self.db.insert(tx, namespace, identity, parent, "owner", "request-digest", {}, plan, 4096)

    def reserve(self, row, phase, slots=None, **kwargs):
        with self.db.transaction() as tx:
            return roots.reserve(self.db, tx, row, phase, self.slots if slots is None else slots, **kwargs)

    def test_preflight_business_share_exact_slot_and_evidence_consumes_another(self):
        row = self.insert()
        preflight = self.reserve(row, "preflight")
        business = self.reserve(row, "business")
        evidence = self.reserve(row, "evidence")
        self.assertEqual(preflight["roots"], business["roots"])
        self.assertEqual(preflight["allocation_id"], business["allocation_id"])
        self.assertNotEqual(preflight["execution_id"], business["execution_id"])
        self.assertTrue(preflight["fresh"])
        self.assertFalse(business["fresh"])
        self.assertTrue(evidence["fresh"])
        self.assertNotEqual(preflight["roots"], evidence["roots"])
        self.assertEqual(3, len([event for event in self.db.events("job", row["id"])
                                 if event["kind"] == "BOOTSTRAP_ROOTS_RESERVED"]))

    def test_restart_reuses_same_grant_but_never_reassigns_a_consumed_slot(self):
        row = self.insert()
        first = self.reserve(row, "preflight")
        self.db.close()
        self.db = StateStore(self.path, "authority", "ledger")
        same = self.reserve(self.db.get("job", row["id"]), "preflight")
        self.assertEqual(first, same)
        next_grant = self.reserve(self.insert("operation-b"), "preflight")
        self.assertNotEqual(first["slot_id"], next_grant["slot_id"])
        self.assertEqual(1, len([event for event in self.db.events("job", row["id"])
                                 if event["kind"] == "BOOTSTRAP_ROOTS_RESERVED"]))

    def test_unknown_cancel_and_successful_resource_release_never_refund_slot(self):
        row = self.insert()
        allocated = self.reserve(row, "preflight", self.slots[:1])
        with self.db.transaction() as tx:
            self.db.update(tx, "job", row["id"], "UNCERTAIN_CANCEL", {
                "outcome": "UNKNOWN", "cancel_requested": True})
            ResourceManager().release(tx, row["parent"], future_start_blocked=True,
                                      tree_exited=True, effects_checked=True)
            roots.assert_reserved(tx, allocated)
        with self.assertRaises(JobError) as failure:
            self.reserve(self.insert("operation-b"), "preflight", self.slots[:1])
        self.assertEqual("LIMIT_EXCEEDED", failure.exception.code)

    def test_same_slot_id_path_or_inode_cannot_create_new_capacity(self):
        row = self.insert()
        self.reserve(row, "preflight", self.slots[:1])
        other = self.insert("operation-b")
        for mode in ("new-id", "inode-alias", "child", "parent"):
            slot = copy.deepcopy(self.slots[0])
            slot["slot_id"] = "renamed-slot"
            for name, root in slot["roots"].items():
                if mode == "inode-alias":
                    root["path"] = f"/elsewhere/{name}"
                elif mode == "child":
                    root["path"] += "/nested"
                    root["inode"] += 1000
                elif mode == "parent":
                    root["path"] = self.parents[name]
                    root["inode"] += 1000
            with self.subTest(mode), self.assertRaises(JobError) as failure:
                self.reserve(other, "preflight", [slot])
            self.assertEqual("LIMIT_EXCEEDED", failure.exception.code)

    def test_consumption_and_intent_can_rollback_as_one_transaction(self):
        row = self.insert()
        with self.assertRaisesRegex(RuntimeError, "intent rejected"):
            with self.db.transaction() as tx:
                roots.reserve(self.db, tx, row, "preflight", self.slots[:1])
                raise RuntimeError("intent rejected")
        self.assertNotIn("bootstrap_grants", self.db.get("job", row["id"])["record"])
        self.assertEqual("slot-0", self.reserve(row, "preflight", self.slots[:1])["slot_id"])

    def test_missing_or_modified_record_cannot_allocate_again_over_immutable_history(self):
        row = self.insert()
        self.reserve(row, "preflight")
        with self.db.transaction() as tx:
            self.db.update(tx, "job", row["id"], "DAMAGED_RECORD", {"bootstrap_grants": {}})
        with self.assertRaises(JobError) as failure:
            self.reserve(row, "preflight")
        self.assertEqual("IO_UNCERTAIN", failure.exception.code)

    def test_missing_consumption_lease_and_rebound_slot_are_rejected(self):
        row = self.insert()
        grant = self.reserve(row, "preflight")
        changed = copy.deepcopy(self.slots)
        changed[0]["roots"]["work"]["inode"] += 1000
        with self.assertRaises(JobError):
            self.reserve(row, "business", changed)
        with self.db.transaction() as tx:
            tx.execute("DELETE FROM leases WHERE resource=?", ("bootstrap-path:" + grant["roots"]["work"],))
        with self.assertRaises(JobError):
            self.reserve(row, "preflight")

    def test_reconcile_has_separate_identity_and_preserves_parent_operation(self):
        parent = self.insert()
        original = self.reserve(parent, "preflight")
        observation = self.insert("observation-a", namespace="reconcile", parent=parent["id"])
        grant = self.reserve(observation, "reconcile")
        self.assertEqual(parent["id"], grant["operation_id"])
        self.assertEqual("reconcile-observation-a-reconcile", grant["execution_id"])
        self.assertNotEqual(original["allocation_id"], grant["allocation_id"])
        self.assertNotEqual(original["roots"], grant["roots"])

    def test_slot_validation_is_pure_and_rejects_parent_overlap_alias_and_bool(self):
        with mock.patch("os.stat", side_effect=AssertionError("no filesystem probe")), \
             mock.patch("builtins.open", side_effect=AssertionError("no filesystem read")):
            roots.validate_slots(self.slots, parent_roots=self.parents, expected_uid=1234)
        for mode in ("parent", "overlap", "inode-alias", "boolean", "wrong-uid", "linked-lexical", "specifier", "environment-expansion", "forbidden"):
            slots = copy.deepcopy(self.slots)
            kwargs = {"parent_roots": self.parents, "expected_uid": 1234}
            if mode == "parent": slots[0]["roots"]["work"]["path"] = self.parents["work"]
            elif mode == "overlap": slots[1]["roots"]["work"]["path"] = slots[0]["roots"]["work"]["path"] + "/nested"
            elif mode == "inode-alias": slots[1]["roots"]["work"]["inode"] = slots[0]["roots"]["work"]["inode"]
            elif mode == "boolean": slots[0]["roots"]["work"]["device"] = True
            elif mode == "wrong-uid": slots[0]["roots"]["work"]["uid"] = 2
            elif mode == "linked-lexical": slots[0]["roots"]["work"]["path"] += "/../escape"
            elif mode == "specifier": slots[0]["roots"]["work"]["path"] += "/%h"
            elif mode == "environment-expansion": slots[0]["roots"]["work"]["path"] += "/$HOME"
            else: kwargs["forbidden_roots"] = [self.parents["work"]]
            with self.subTest(mode), self.assertRaises(JobError):
                roots.validate_slots(slots, **kwargs)

    def test_binding_rewrites_generated_paths_without_mutating_fixed_inputs(self):
        row = self.insert()
        grant = self.reserve(row, "preflight")
        old = grant["source_roots"]
        prepared = {"root": old["work"], "wheel": old["work"] + "/wheel.whl"}
        execution = {"kind": "ledger.prepare", "roots": old,
            "writable": list(old.values()), "readonly": ["/fixed/source"],
            "source": {"root": "/fixed/source"}, "storage": {"config": "/fixed/config"},
            "prepared": prepared,
            "stages": [{"argv": ["/fixed/python", old["work"] + "/build", old["work"] + "-prefix-collision"],
                        "cwd": old["work"], "env": {"TMPDIR": old["temporary"]}}],
            "environment": {"TMPDIR": old["temporary"]}}
        before = copy.deepcopy(execution)
        bound = roots.bind_execution(execution, grant)
        self.assertEqual(before, execution)
        self.assertEqual(grant["roots"], bound["roots"])
        self.assertEqual(grant["roots"]["work"] + "/wheel.whl", bound["prepared"]["wheel"])
        self.assertEqual(old["work"] + "-prefix-collision", bound["stages"][0]["argv"][2])
        for name in ("readonly", "source", "storage"):
            self.assertEqual(before[name], bound[name])
        execution["kind"] = "ledger.test.source"
        self.assertEqual(prepared, roots.bind_execution(execution, grant)["prepared"])
        self.assertEqual(bound, roots.bind_execution(bound, grant))

    def test_evidence_retained_root_binding_is_exact_and_cannot_expand_on_retry(self):
        row = self.insert()
        extra = {"evidence_store": {"path": "/synthetic/store", "device": 8, "inode": 2000, "uid": 1234}}
        grant = self.reserve(row, "evidence", extra_roots=extra)
        self.assertEqual(["/synthetic/store"], grant["retained_paths"])
        self.assertEqual(extra["evidence_store"]["inode"], grant["paths"]["/synthetic/store"]["inode"])
        changed = copy.deepcopy(extra)
        changed["evidence_store"]["inode"] += 1
        with self.assertRaises(JobError): self.reserve(row, "evidence", extra_roots=changed)
        with self.assertRaises(JobError): self.reserve(row, "preflight", extra_roots=extra)

    def test_grant_wrong_identity_tamper_and_digest_only_forgery_fail(self):
        row = self.insert()
        grant = self.reserve(row, "preflight")
        with self.assertRaises(JobError): roots.validate_grant(grant, execution_id="other")
        with self.assertRaises(JobError): roots.validate_grant(grant, operation_id="other")
        damaged = copy.deepcopy(grant)
        damaged["fresh"] = False
        damaged["grant_digest"] = hashlib.sha256(canonical_bytes({k: v for k, v in damaged.items() if k != "grant_digest"})).hexdigest()
        with self.assertRaises(JobError): roots.validate_grant(damaged)
        forged = copy.deepcopy(grant)
        forged["paths"][forged["roots"]["work"]]["inode"] += 10
        forged["allocation_id"] = roots._allocation_id(forged["namespace"], forged["record_id"],
            forged["slot_id"], forged["roots"], forged["paths"])
        forged["grant_digest"] = hashlib.sha256(canonical_bytes({k: v for k, v in forged.items() if k != "grant_digest"})).hexdigest()
        roots.validate_grant(forged)
        with self.assertRaises(JobError), self.db.transaction() as tx: roots.assert_reserved(tx, forged)


if __name__ == "__main__":
    unittest.main()
