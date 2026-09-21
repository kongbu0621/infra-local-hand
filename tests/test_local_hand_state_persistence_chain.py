"""Local JSON persistence failures retain replay barriers and report uncertainty."""
from __future__ import annotations

from contextlib import ExitStack
import errno
import json
import os
from pathlib import Path
import unittest
from unittest import mock

from test_local_hand_state_lookup_chain import StateLookupChainTests
from local_hand import worker
from local_hand.protocol import LocalHandError
from local_hand_connect import controller


@unittest.skipIf(os.name == 'nt', 'POSIX persistence injection; Windows deferred')
class StatePersistenceChainTests(unittest.TestCase):
    def setUp(self):
        self.chain = StateLookupChainTests()
        self.chain.setUp()
        self.addCleanup(self.chain.doCleanups)

    def _assert_uncertain(self, exc, code='local_state_write_failed'):
        self.assertIsInstance(exc, LocalHandError)
        self.assertEqual(exc.code, code)
        self.assertEqual(exc.status, 'indeterminate')

    def test_zero_write_stops_immediately_without_replacing_old_state(self):
        target = self.chain.f.root/'state.json'
        target.write_bytes(b'old evidence')
        calls = 0
        def no_progress(fd, data):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise AssertionError('writer retried after zero progress')
            return 0
        error = None
        with mock.patch.object(os, 'write', side_effect=no_progress):
            try:
                worker.write_json_atomic(target, {'value': 'new'})
            except Exception as exc:
                error = exc
        self._assert_uncertain(error)
        self.assertEqual(calls, 1)
        self.assertEqual(target.read_bytes(), b'old evidence')
        self.assertFalse(list(target.parent.glob('.state.json.local-hand-*')))

    def test_partial_writes_commit_complete_json_and_keep_unrelated_temp(self):
        target = self.chain.f.root/'state.json'
        unrelated = target.parent/'.state.json.local-hand-preserved'
        unrelated.write_bytes(b'prior failed attempt')
        value = {'unicode': '完整结果', 'number': 12}
        original = os.write
        def partial(fd, data):
            return original(fd, data[:3])
        with mock.patch.object(os, 'write', side_effect=partial):
            worker.write_json_atomic(target, value)
        self.assertEqual(json.loads(target.read_text()), value)
        self.assertEqual(unrelated.read_bytes(), b'prior failed attempt')
        self.assertEqual(list(target.parent.glob('.state.json.local-hand-*')), [unrelated])

    def test_atomic_writer_failures_preserve_the_correct_side_of_replace(self):
        for operation in ('mkdir', 'mkstemp', 'write', 'fsync', 'close', 'replace', 'parent-fsync'):
            with self.subTest(operation=operation):
                directory = self.chain.f.root/operation
                directory.mkdir()
                target = directory/'state.json'
                target.write_bytes(b'old evidence')
                value = {'value': 'new evidence'}
                error = None
                with ExitStack() as patches:
                    failure = OSError(errno.EIO, 'fixture '+operation+' failure')
                    if operation == 'mkdir':
                        patches.enter_context(mock.patch.object(Path, 'mkdir', side_effect=failure))
                    elif operation == 'mkstemp':
                        patches.enter_context(mock.patch.object(worker.tempfile, 'mkstemp', side_effect=failure))
                    elif operation == 'parent-fsync':
                        patches.enter_context(mock.patch.object(worker, '_fsync_parent', side_effect=failure))
                    elif operation == 'close':
                        original_close = os.close
                        closed = []
                        def fail_after_close(fd):
                            closed.append(fd)
                            if len(closed) > 1:
                                raise AssertionError('close retried after descriptor ownership ended')
                            original_close(fd)
                            raise failure
                        patches.enter_context(mock.patch.object(os, 'close', side_effect=fail_after_close))
                    else:
                        patches.enter_context(mock.patch.object(os, operation, side_effect=failure))
                    try:
                        worker.write_json_atomic(target, value)
                    except Exception as exc:
                        error = exc
                code = 'local_state_durability_unconfirmed' if operation == 'parent-fsync' else 'local_state_write_failed'
                self._assert_uncertain(error, code)
                self.assertEqual(error.__cause__.errno, errno.EIO)
                if operation == 'parent-fsync':
                    self.assertEqual(json.loads(target.read_text()), value)
                else:
                    self.assertEqual(target.read_bytes(), b'old evidence')
                self.assertFalse(list(directory.glob('.state.json.local-hand-*')))

    def _persistence_recovery(self, task_id, stage, *, after_replace=False):
        c = self.chain
        task = c._submit(task_id)
        receipt = c.state/'receipts'/f'{task_id}.json'
        outbox = c.state/'outbox'/f'{task_id}.json'
        original = worker.write_json_atomic
        def injected(path, value, **kwargs):
            selected = ((stage == 'intent' and path == receipt and 'result' not in value)
                or (stage == 'outbox' and path == outbox)
                or (stage == 'receipt' and path == receipt and 'result' in value))
            if selected:
                owner, method = (worker, '_fsync_parent') if after_replace else (os, 'write')
                with mock.patch.object(owner, method, side_effect=OSError(errno.ENOSPC, 'fixture persistence failure')):
                    return original(path, value, **kwargs)
            return original(path, value, **kwargs)
        failure = None
        with mock.patch.object(worker, 'write_json_atomic', side_effect=injected), mock.patch.object(worker, 'execute_task', wraps=worker.execute_task) as execute:
            try:
                worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
            except Exception as exc:
                failure = exc
        self.assertEqual(execute.call_count, 0 if stage == 'intent' else 1)
        self._assert_uncertain(failure, 'local_state_durability_unconfirmed' if after_replace else 'local_state_write_failed')
        self.assertFalse((c.f.mailbox/'_executor_spike/results'/f'{task_id}.json').exists())
        self.assertFalse(list((c.state/'outbox').glob('.*.local-hand-*')))
        self.assertFalse(list((c.state/'receipts').glob('.*.local-hand-*')))
        if stage == 'intent':
            self.assertFalse(receipt.exists())
            self.assertFalse(outbox.exists())
            self.assertEqual((c.repo/'sample.txt').read_bytes(), b'before\n')
            with mock.patch.object(worker, 'execute_task', wraps=worker.execute_task) as execute:
                worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
            self.assertEqual(execute.call_count, 1)
            self.assertEqual((c.repo/'sample.txt').read_bytes(), b'after\n')
        else:
            self.assertEqual((c.repo/'sample.txt').read_bytes(), b'after\n')
            self.assertTrue(receipt.exists())
            payload_retained = stage == 'receipt' or after_replace
            self.assertEqual(outbox.exists(), payload_retained)
            if payload_retained:
                self.assertEqual(json.loads(outbox.read_text())['status'], 'succeeded')
            # A new execution would be observable even for the same CAS input.
            (c.repo/'sample.txt').write_bytes(b'before\n')
            with mock.patch.object(worker, 'execute_task', side_effect=AssertionError('blind replay')):
                worker.process_once(c.f.mailbox, c.f.branch, c.profile, c.state)
            self.assertEqual((c.repo/'sample.txt').read_bytes(), b'before\n')
        result = controller.wait_for_result(c.f.mailbox, c.f.branch, task, timeout_seconds=0,
            expected_provenance=worker.build_provenance(c.profile))
        expected = 'indeterminate' if stage == 'outbox' and not after_replace else 'succeeded'
        self.assertEqual(result['status'], expected)
        if expected == 'indeterminate':
            self.assertEqual(result['error_code'], 'outcome_unknown')
        self.assertEqual(json.loads(receipt.read_text())['result'], result)
        self.assertFalse(outbox.exists())

    def test_failed_intent_write_stops_before_execution_then_retries_once(self):
        self._persistence_recovery('LH9600', 'intent')

    def test_failed_outbox_write_after_cas_recovers_unknown_without_replay(self):
        self._persistence_recovery('LH9601', 'outbox')

    def test_failed_completed_receipt_keeps_successful_outbox_for_recovery(self):
        self._persistence_recovery('LH9602', 'receipt')

    def test_outbox_directory_sync_failure_keeps_result_and_prevents_replay(self):
        self._persistence_recovery('LH9603', 'outbox', after_replace=True)

    def test_receipt_directory_sync_failure_keeps_result_and_prevents_replay(self):
        self._persistence_recovery('LH9604', 'receipt', after_replace=True)
