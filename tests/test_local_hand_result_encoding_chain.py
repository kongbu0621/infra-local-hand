"""Malformed Result text must retain evidence without blocking unrelated work."""
from __future__ import annotations

import json
import os
import unittest
from unittest import mock

import test_local_hand_state_lookup_chain as fixtures
from local_hand import worker
from local_hand.protocol import LocalHandError, conflict_filename, result_error, result_success, task_digest
from local_hand_connect import controller


class ResultEncodingValidationTests(unittest.TestCase):
    def test_invalid_unicode_in_details_keys_and_errors_has_typed_failure(self):
        task = controller.build_task("fixture", "node.status", {}, task_id="LH9957")
        provenance = {"implementation_commit": "a" * 40, "package_digest": "b" * 64,
                      "profile_digest": "c" * 64}
        results = [result_success(task, "fixture", details, provenance)
                   for details in ({"value": "\ud800"}, {"\udfff": "key"}, {"nested": ["\ud800"]})]
        results.append(result_error(task, "fixture", LocalHandError("bad", "\ud800"), provenance))
        for result in results:
            raw = json.dumps(result, ensure_ascii=True)
            with self.subTest(raw=raw), self.assertRaises(LocalHandError) as raised:
                worker.validate_remote_result(json.loads(raw), task["task_id"])
            self.assertEqual(raised.exception.code, "remote_result_invalid")
            self.assertEqual(raised.exception.status, "indeterminate")

    def test_valid_unicode_and_legacy_values_preserve_result_content(self):
        task = controller.build_task("fixture", "node.status", {}, task_id="LH9958")
        provenance = {"implementation_commit": "a" * 40, "package_digest": "b" * 64,
                      "profile_digest": "c" * 64}
        result = result_success(task, "fixture", {"中文😀": ["完成", "", float("inf")]}, provenance)
        before = worker._json_bytes(result)
        self.assertEqual(worker.validate_remote_result(result, task["task_id"]), result)
        self.assertEqual(worker._json_bytes(result), before)


@unittest.skipIf(os.name == "nt", "POSIX local Git fixture; Windows deferred")
class ResultEncodingChainTests(unittest.TestCase):
    def setUp(self):
        self.c = fixtures.StateLookupChainTests()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)

    def _result(self, task, details):
        return result_success(task, self.c.profile.node_id, details,
                              worker.build_provenance(self.c.profile))

    def _remote_bytes(self, relative, raw):
        c = self.c
        c.f._git(c.f.seed, "fetch", "origin", c.f.branch)
        c.f._git(c.f.seed, "reset", "--hard", "FETCH_HEAD")
        (c.f.seed / relative).write_bytes(raw)
        c.f._git(c.f.seed, "add", "--", relative)
        c.f._git(c.f.seed, "commit", "-qm", "synthetic malformed result")
        c.f._git(c.f.seed, "push", "origin", "HEAD:refs/heads/" + c.f.branch)

    def test_remote_invalid_unicode_retains_raw_result_and_runs_later_task(self):
        c = self.c
        bad = c._submit("LH9950")
        good = c._submit("LH9951")
        relative = "_executor_spike/results/LH9950.json"
        raw = (json.dumps(self._result(bad, {"value": "\ud800"}), ensure_ascii=True) + "\n").encode()
        self._remote_bytes(relative, raw)
        with mock.patch.object(worker, "execute_task", wraps=worker.execute_task) as execute:
            worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
        self.assertEqual([call.args[0]["task_id"] for call in execute.call_args_list], [good["task_id"]])
        self.assertEqual((c.repo / "sample.txt").read_bytes(), b"after\n")
        self.assertEqual((c.f.mailbox / relative).read_bytes(), raw)
        conflict = c.state / "conflicts" / conflict_filename(task_digest(bad))
        self.assertEqual(json.loads(conflict.read_bytes())["error_code"], "remote_result_invalid")
        (c.repo / "sample.txt").write_bytes(b"before\n")
        with mock.patch.object(worker, "execute_task", side_effect=AssertionError("blind replay")):
            worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
        self.assertEqual((c.repo / "sample.txt").read_bytes(), b"before\n")
        self.assertEqual((c.f.mailbox / relative).read_bytes(), raw)

    def test_invalid_local_outbox_is_preserved_while_healthy_result_is_published(self):
        c = self.c
        outbox = c.state / "outbox"
        outbox.mkdir(parents=True)
        bad, good = c.f._task(task_id="LH9952"), c.f._task(task_id="LH9953")
        raw = json.dumps(self._result(bad, {"\udfff": "invalid key"}), ensure_ascii=True).encode()
        (outbox / "LH9952.json").write_bytes(raw)
        valid = self._result(good, {"value": "中文😀"})
        worker.write_json_atomic(outbox / "LH9953.json", valid)
        worker.publish_outbox(c.f.mailbox, c.f.branch, outbox)
        self.assertEqual(list(outbox.iterdir()), [])
        quarantined = list((c.state / "quarantine").iterdir())
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0].read_bytes(), raw)
        self.assertEqual(json.loads((c.f.mailbox / "_executor_spike/results/LH9953.json").read_bytes()), valid)
        self.assertFalse((c.f.mailbox / "_executor_spike/results/LH9952.json").exists())

    def test_invalid_saved_receipt_blocks_replay_but_allows_next_task(self):
        c = self.c
        bad, good = c._submit("LH9954"), c._submit("LH9955")
        receipt = c.state / "receipts/LH9954.json"
        receipt.parent.mkdir(parents=True)
        raw = json.dumps({"task_id": bad["task_id"], "task_digest": task_digest(bad),
                          "result": self._result(bad, {"value": ["\ud800"]})}, ensure_ascii=True).encode()
        receipt.write_bytes(raw)
        with mock.patch.object(worker, "execute_task", wraps=worker.execute_task) as execute:
            worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
        self.assertEqual([call.args[0]["task_id"] for call in execute.call_args_list], [good["task_id"]])
        self.assertEqual(receipt.read_bytes(), raw)
        self.assertEqual((c.repo / "sample.txt").read_bytes(), b"after\n")
        conflict = c.state / "conflicts" / conflict_filename(task_digest(bad))
        self.assertEqual(json.loads(conflict.read_bytes())["error_code"], "local_receipt_invalid")

    def test_controller_reports_typed_uncertainty_for_invalid_result(self):
        c = self.c
        task = c._submit("LH9956")
        relative = "_executor_spike/results/LH9956.json"
        raw = json.dumps(self._result(task, {"value": "\ud800"}), ensure_ascii=True).encode()
        self._remote_bytes(relative, raw)
        with self.assertRaises(LocalHandError) as raised:
            controller.wait_for_result(c.f.mailbox, c.f.branch, task, timeout_seconds=0,
                                       expected_provenance=worker.build_provenance(c.profile))
        self.assertEqual(raised.exception.code, "remote_result_invalid")
        self.assertEqual(raised.exception.status, "indeterminate")
        self.assertEqual((c.f.mailbox / relative).read_bytes(), raw)
