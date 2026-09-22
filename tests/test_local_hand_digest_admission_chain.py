"""Canonical UTF-8 identity failures cannot stop later committed Tasks."""
from __future__ import annotations

import hashlib
import json
import os
import unittest
from unittest import mock

from local_hand import worker
from local_hand.protocol import LocalHandError, task_digest
from local_hand_connect import controller
import test_local_hand_state_lookup_chain as chain_fixtures


class CanonicalTaskDigestTests(unittest.TestCase):
    def test_lone_surrogates_fail_with_typed_identity_error(self):
        for value in ("\ud800", "\udfff", {"\ud800": "key"}, ["\ud800"]):
            with self.subTest(value=repr(value)), self.assertRaises(LocalHandError) as raised:
                task_digest({"params": value})
            self.assertEqual(raised.exception.code, "task_digest_invalid")

    def test_existing_unicode_and_legacy_digest_spelling_is_unchanged(self):
        # The legacy Task v1 canonical algorithm stays intact, including its
        # existing non-finite-number behavior; this is not a new JSON schema.
        for value in ("中文😀", "", {"nested": ["😀", "中文"]}, float("nan")):
            task = {"schema_version": "local-hand-task/v1", "task_id": "LH9940",
                    "target_node": "fixture", "action": "node.status", "params": {"value": value}}
            expected = hashlib.sha256(json.dumps(task, ensure_ascii=False, sort_keys=True,
                                                separators=(",", ":")).encode("utf-8")).hexdigest()
            self.assertEqual(task_digest(task), expected)

    def test_controller_build_rejects_unencodable_task_without_traceback(self):
        with self.assertRaises(LocalHandError) as raised:
            controller.build_task("fixture", "fs.write_text_cas", {
                "repository": "demo", "relative_path": "sample.txt",
                "expected_sha256": "0" * 64, "content": "\ud800"}, task_id="LH9941")
        self.assertEqual(raised.exception.status, "rejected")


@unittest.skipIf(os.name == "nt", "POSIX local Git fixture; Windows deferred")
class DigestAdmissionChainTests(unittest.TestCase):
    def setUp(self):
        self.c = chain_fixtures.StateLookupChainTests()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)

    def test_unencodable_task_identities_preserve_raw_blobs_and_allow_later_cas(self):
        c = self.c
        tasks = []
        for index, value in enumerate(("\ud800", "\udfff", {"\ud800": "key"}, ["\ud800"])):
            task = c.f._task(task_id=f"LH{9942 + index}")
            task["params"] = {"invalid": value}
            tasks.append(task)
        invalid_action = c.f._task(task_id="LH9946")
        invalid_action["action"] = "\ud800"
        tasks.append(invalid_action)
        good = c.f._task(task_id="LH9947", action="fs.write_text_cas", params={
            "repository": "demo", "relative_path": "sample.txt",
            "expected_sha256": hashlib.sha256(b"before\n").hexdigest(), "content": "after\n"})
        tasks.append(good)
        originals = {}
        for task in tasks:
            relative = f"_executor_spike/tasks/{task['task_id']}.json"
            # JSON escapes make these real UTF-8 bytes accepted by Git and
            # json.loads, while the decoded lone surrogate has no UTF-8 digest.
            raw = (json.dumps(task, ensure_ascii=True) + "\n").encode("ascii")
            (c.f.seed / relative).write_bytes(raw)
            originals[relative] = raw
        c.f._git(c.f.seed, "add", "--", "_executor_spike/tasks")
        c.f._git(c.f.seed, "commit", "-qm", "fixture invalid Unicode task identities")
        c.f._git(c.f.seed, "push", "origin", "HEAD:refs/heads/" + c.f.branch)

        with mock.patch.object(worker, "execute_task", wraps=worker.execute_task) as execute:
            worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
        self.assertEqual([call.args[0]["task_id"] for call in execute.call_args_list], [good["task_id"]])
        self.assertEqual((c.repo / "sample.txt").read_bytes(), b"after\n")
        receipt = c.state / "receipts/LH9947.json"
        result = c.f.mailbox / "_executor_spike/results/LH9947.json"
        saved_receipt, saved_result = receipt.read_bytes(), result.read_bytes()
        worker.validate_remote_result(json.loads(saved_result), good["task_id"], good["action"],
                                      c.profile.node_id, task_digest(good))
        self.assertEqual(json.loads(saved_result)["status"], "succeeded")
        for task in tasks[:-1]:
            for parent in (c.state / "receipts", c.state / "outbox", c.f.mailbox / "_executor_spike/results"):
                self.assertFalse((parent / (task["task_id"] + ".json")).exists())
        self.assertEqual(list((c.state / "conflicts").iterdir()), [])
        # A second CAS would visibly alter restored bytes; do not only rely
        # on execution call counting to verify that the receipt prevents replay.
        (c.repo / "sample.txt").write_bytes(b"before\n")
        with mock.patch.object(worker, "execute_task", side_effect=AssertionError("blind replay")):
            worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
        self.assertEqual((c.repo / "sample.txt").read_bytes(), b"before\n")
        self.assertEqual(receipt.read_bytes(), saved_receipt)
        self.assertEqual(result.read_bytes(), saved_result)
        for relative, raw in originals.items():
            self.assertEqual((c.f.mailbox / relative).read_bytes(), raw)
            committed = c.f._git(c.f.root, "--git-dir", str(c.f.remote), "show",
                                 "refs/heads/" + c.f.branch + ":" + relative).stdout
            self.assertEqual(committed.encode("utf-8"), raw)
