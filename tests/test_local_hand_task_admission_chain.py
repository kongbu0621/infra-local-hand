"""Unrepresentable Task identities must not wedge later admitted work."""
from __future__ import annotations

import hashlib
import json
import os
import unittest
from unittest import mock

from local_hand import worker
from local_hand.protocol import conflict_filename, task_digest
from test_local_hand_state_lookup_chain import StateLookupChainTests


@unittest.skipIf(os.name == "nt", "POSIX local Git fixtures; Windows deferred")
class TaskAdmissionChainTests(unittest.TestCase):
    def setUp(self):
        self.chain = StateLookupChainTests()
        self.chain.setUp()
        self.addCleanup(self.chain.doCleanups)

    def _cas_task(self, task_id):
        return self.chain.f._task(task_id=task_id, action="fs.write_text_cas", params={
            "repository": "demo", "relative_path": "sample.txt",
            "expected_sha256": hashlib.sha256(b"before\n").hexdigest(),
            "content": "after\n",
        })

    def _publish_raw_tasks(self, tasks):
        c = self.chain
        originals = {}
        for task in tasks:
            relative = f"_executor_spike/tasks/{task['task_id']}.json"
            raw = json.dumps(task, ensure_ascii=False, indent=2) + "\n"
            (c.f.seed / relative).write_text(raw, encoding="utf-8")
            originals[relative] = raw
        c.f._git(c.f.seed, "add", "--", "_executor_spike/tasks")
        c.f._git(c.f.seed, "commit", "-qm", "fixture unrepresentable and valid task identities")
        c.f._git(c.f.seed, "push", "origin", "HEAD:refs/heads/" + c.f.branch)
        return originals

    def _assert_task_blobs_unchanged(self, originals):
        c = self.chain
        for relative, raw in originals.items():
            with self.subTest(path=relative):
                actual = c.f._git(c.f.root, "--git-dir", str(c.f.remote), "show",
                                  "refs/heads/" + c.f.branch + ":" + relative).stdout
                self.assertEqual(actual, raw)
                self.assertEqual((c.f.mailbox / relative).read_bytes(), raw.encode("utf-8"))

    def _run(self):
        c = self.chain
        with mock.patch.object(worker, "execute_task", wraps=worker.execute_task) as execute:
            worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
        return [call.args[0]["task_id"] for call in execute.call_args_list]

    def _assert_healthy_repeat_does_not_reexecute(self, task):
        c = self.chain
        receipt = c.state / "receipts" / (task["task_id"] + ".json")
        original_receipt = receipt.read_bytes()
        original_result = (c.f.mailbox / "_executor_spike/results" / receipt.name).read_bytes()
        # Make an illicit second CAS observable, independent of call counting.
        (c.repo / "sample.txt").write_bytes(b"before\n")
        self.assertEqual(self._run(), [])
        self.assertEqual((c.repo / "sample.txt").read_bytes(), b"before\n")
        self.assertEqual(receipt.read_bytes(), original_receipt)
        self.assertEqual((c.f.mailbox / "_executor_spike/results" / receipt.name).read_bytes(), original_result)

    def test_unrepresentable_actions_preserve_blobs_and_allow_later_cas(self):
        c = self.chain
        malformed = []
        # Empty is first so the baseline demonstrates the queue-stopping path.
        for index, action in enumerate(("", None, [], {}, 0, 42, False)):
            task = c.f._task(task_id=f"LH{9910 + index}")
            task["action"] = action
            malformed.append(task)
        missing = c.f._task(task_id="LH9917")
        del missing["action"]
        malformed.append(missing)
        valid = self._cas_task("LH9921")
        originals = self._publish_raw_tasks([*malformed, valid])

        self.assertEqual(self._run(), [valid["task_id"]])
        self.assertEqual((c.repo / "sample.txt").read_bytes(), b"after\n")
        result = json.loads((c.f.mailbox / "_executor_spike/results/LH9921.json").read_text())
        worker.validate_remote_result(result, valid["task_id"], valid["action"], c.profile.node_id, task_digest(valid))
        self.assertEqual(result["status"], "succeeded")
        for task in malformed:
            with self.subTest(action=task.get("action", "<missing>")):
                name = task["task_id"] + ".json"
                self.assertFalse((c.state / "receipts" / name).exists(), "invalid identity gained a receipt")
                self.assertFalse((c.state / "outbox" / name).exists(), "invalid identity gained a Result")
                self.assertFalse((c.f.mailbox / "_executor_spike/results" / name).exists(), "invalid identity gained a remote Result")
                conflict = conflict_filename(task_digest(task))
                self.assertFalse((c.state / "conflicts" / conflict).exists())
                self.assertFalse((c.f.mailbox / "_executor_spike/conflicts" / conflict).exists())
        self._assert_task_blobs_unchanged(originals)
        self._assert_healthy_repeat_does_not_reexecute(valid)
        self._assert_task_blobs_unchanged(originals)

    def test_unknown_nonempty_action_retains_identity_in_rejected_result(self):
        c = self.chain
        unknown = c.f._task(task_id="LH9930")
        unknown["action"] = "unsupported.fixture.action"
        valid = self._cas_task("LH9931")
        originals = self._publish_raw_tasks([unknown, valid])

        self.assertEqual(self._run(), [valid["task_id"]])
        rejected = json.loads((c.f.mailbox / "_executor_spike/results/LH9930.json").read_text())
        worker.validate_remote_result(rejected, unknown["task_id"], unknown["action"], c.profile.node_id, task_digest(unknown))
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error_code"], "action_not_allowlisted")
        receipt = json.loads((c.state / "receipts/LH9930.json").read_text())
        self.assertEqual(receipt["result"], rejected)
        self.assertEqual(receipt["task_digest"], task_digest(unknown))
        self.assertEqual((c.repo / "sample.txt").read_bytes(), b"after\n")
        succeeded = json.loads((c.f.mailbox / "_executor_spike/results/LH9931.json").read_text())
        self.assertEqual(succeeded["status"], "succeeded")
        self._assert_task_blobs_unchanged(originals)
        self._assert_healthy_repeat_does_not_reexecute(valid)
        self._assert_task_blobs_unchanged(originals)
