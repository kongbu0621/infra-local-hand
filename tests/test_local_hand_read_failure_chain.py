"""I/O uncertainty must not permanently quarantine readable, valid evidence."""
from __future__ import annotations
from contextlib import ExitStack
import errno
import json
import os
from pathlib import Path
import unittest
from unittest import mock
from local_hand import bounded_io, worker
from local_hand.protocol import LocalHandError, conflict_filename, task_digest
from local_hand_connect import controller
from test_local_hand_state_lookup_chain import StateLookupChainTests

@unittest.skipIf(os.name == 'nt', 'POSIX local Git/read-failure fixtures; Windows deferred')
class ReadFailureChainTests(unittest.TestCase):
    def setUp(self):
        self.c = StateLookupChainTests()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)

    def _read_fault(self, target):
        original = worker.read_regular_file_bounded
        def read(path, *args, **kwargs):
            if path == target:
                with mock.patch.object(os, 'read', side_effect=OSError(errno.EIO, 'fixture payload read failure')):
                    return original(path, *args, **kwargs)
            return original(path, *args, **kwargs)
        return mock.patch.object(worker, 'read_regular_file_bounded', side_effect=read)

    def _uncertain(self, exc):
        self.assertIsInstance(exc, LocalHandError)
        self.assertEqual(exc.code, 'json_read_unavailable')
        self.assertEqual(exc.status, 'indeterminate')
        self.assertIn('errno=5', exc.message)

    def _run_failure(self, target, operation):
        error = None
        with self._read_fault(target), mock.patch.object(worker, 'execute_task', side_effect=AssertionError('must not execute through read uncertainty')):
            try: operation()
            except LocalHandError as exc: error = exc
        self._uncertain(error)

    def _process(self, state=None):
        c = self.c
        return worker.process_once(c.f.mailbox, c.f.branch, c.profile, state or c.state)

    def _no_false_conflict(self, task, state=None):
        state = state or self.c.state
        name = conflict_filename(task_digest(task))
        self.assertFalse((state/'conflicts'/name).exists())
        self.assertFalse((self.c.f.mailbox/'_executor_spike/conflicts'/name).exists())
        self.assertFalse(list((state/'quarantine').glob('*')))

    def test_json_read_io_errors_keep_io_identity(self):
        target = self.c.f.root/'valid.json';target.write_bytes(b'{"ok": true}\n')
        for stage in ('lstat', 'open', 'fstat', 'read', 'close', 'read-and-close'):
            with self.subTest(stage=stage):
                failure = OSError(errno.EIO, 'fixture '+stage)
                owner, operation = (Path, 'lstat') if stage == 'lstat' else (os, stage)
                original_close = os.close
                def fail_close(fd):
                    original_close(fd)
                    raise OSError(errno.EIO if stage == 'close' else errno.EBADF, 'fixture close')
                error = None
                with ExitStack() as patches:
                    if stage == 'read-and-close':
                        patches.enter_context(mock.patch.object(os, 'read', side_effect=failure))
                        patches.enter_context(mock.patch.object(os, 'close', side_effect=fail_close))
                    else:
                        patches.enter_context(mock.patch.object(owner, operation, side_effect=fail_close if stage == 'close' else failure))
                    try: worker.load_json_bounded(target, 1024, 'fixture_invalid')
                    except LocalHandError as exc: error = exc
                self._uncertain(error)
        self.assertEqual(worker.load_json_bounded(target, 1024, 'fixture_invalid'), {'ok': True})
        for content, limit in ((b'{broken', 1024), (b'\xff',1024), (b'{"long":"value"}',2)):
            target.write_bytes(content)
            with self.assertRaises(LocalHandError) as raised: worker.load_json_bounded(target, limit, 'fixture_invalid')
            self.assertEqual(raised.exception.code, 'fixture_invalid')
        target.unlink();target.symlink_to(self.c.f.root/'absent')
        with self.assertRaises(LocalHandError) as raised: worker.load_json_bounded(target, 1024, 'fixture_invalid')
        self.assertEqual(raised.exception.code, 'fixture_invalid')

    def test_task_read_failure_is_not_idle_success(self):
        task = self.c._submit('LH9800')
        target = self.c.f.mailbox/'_executor_spike/tasks/LH9800.json'
        self._run_failure(target, self._process)
        self.assertFalse((self.c.state/'receipts/LH9800.json').exists())
        self.assertEqual((self.c.repo/'sample.txt').read_bytes(), b'before\n')
        self._process()
        self.assertEqual((self.c.repo/'sample.txt').read_bytes(), b'after\n')
        self._no_false_conflict(task)

    def test_receipt_read_failure_does_not_create_permanent_conflict(self):
        task = self.c._submit('LH9801');self._process()
        receipt = self.c.state/'receipts/LH9801.json';saved = receipt.read_bytes()
        (self.c.repo/'sample.txt').write_bytes(b'before\n')
        self._run_failure(receipt, self._process)
        self.assertEqual(receipt.read_bytes(), saved);self._no_false_conflict(task)
        self._process()
        self.assertEqual(receipt.read_bytes(), saved)
        self.assertEqual((self.c.repo/'sample.txt').read_bytes(), b'before\n')

    def test_outbox_read_failure_retains_success_with_only_intent_receipt(self):
        c=self.c;task=c._submit('LH9802')
        receipt=c.state/'receipts/LH9802.json';pending=c.state/'outbox/LH9802.json'
        worker.write_json_atomic(receipt,{'task_id':task['task_id'],'task_digest':task_digest(task),'source':'local_execution_started'})
        intent=receipt.read_bytes();result=worker.execute_task(task,c.profile,c.state)
        worker.write_json_atomic(pending,result);saved=pending.read_bytes()
        (c.repo/'sample.txt').write_bytes(b'before\n')
        self._run_failure(pending,self._process)
        self.assertEqual(pending.read_bytes(),saved);self.assertEqual(receipt.read_bytes(),intent)
        self._no_false_conflict(task)
        self._process()
        self.assertFalse(pending.exists())
        self.assertEqual(json.loads(receipt.read_text())['result'],result)
        actual=controller.wait_for_result(c.f.mailbox,c.f.branch,task,timeout_seconds=0,expected_provenance=worker.build_provenance(c.profile))
        self.assertEqual(actual,result);self.assertEqual(actual['status'],'succeeded')
        self.assertEqual((c.repo/'sample.txt').read_bytes(),b'before\n')

    def test_remote_result_read_failure_with_fresh_state_is_recoverable(self):
        c=self.c;task=c._submit('LH9803');self._process()
        target=c.f.mailbox/'_executor_spike/results/LH9803.json';saved=target.read_bytes()
        fresh=c.f.root/'fresh-state';(c.repo/'sample.txt').write_bytes(b'before\n')
        self._run_failure(target,lambda:self._process(fresh))
        self._no_false_conflict(task,fresh);self.assertFalse((fresh/'receipts/LH9803.json').exists())
        self._process(fresh)
        self.assertEqual(json.loads((fresh/'receipts/LH9803.json').read_text())['result'],json.loads(saved))
        self.assertEqual((c.repo/'sample.txt').read_bytes(),b'before\n')

    def test_remote_ack_read_failure_preserves_pending_without_conflict(self):
        c=self.c;task=c._submit('LH9804');self._process()
        target=c.f.mailbox/'_executor_spike/results/LH9804.json';saved=target.read_bytes()
        pending=c.state/'outbox/LH9804.json';pending.write_bytes(saved)
        self._run_failure(target,lambda:worker.publish_outbox(c.f.mailbox,c.f.branch,c.state/'outbox'))
        self.assertEqual(pending.read_bytes(),saved);self._no_false_conflict(task)
        self.assertEqual(list((c.state/'outbox').iterdir()),[pending])
        worker.publish_outbox(c.f.mailbox,c.f.branch,c.state/'outbox')
        self.assertFalse(pending.exists());self.assertEqual(target.read_bytes(),saved)

    def test_controller_wait_read_failure_preserves_evidence_and_retries(self):
        c=self.c;task=c._submit('LH9805');self._process()
        target=c.f.mailbox/'_executor_spike/results/LH9805.json';saved=target.read_bytes()
        call=lambda:controller.wait_for_result(c.f.mailbox,c.f.branch,task,timeout_seconds=0,expected_provenance=worker.build_provenance(c.profile))
        self._run_failure(target,call)
        self.assertEqual(call(),json.loads(saved));self.assertEqual(target.read_bytes(),saved)
        self._no_false_conflict(task)

    def test_controller_submit_read_failure_preserves_io_identity(self):
        c=self.c;task=c._submit('LH9806');target=c.f.mailbox/'_executor_spike/tasks/LH9806.json';saved=target.read_bytes()
        self._run_failure(target,lambda:controller.submit_task(c.f.mailbox,c.f.branch,task))
        self.assertEqual(target.read_bytes(),saved)
        self.assertEqual(controller.submit_task(c.f.mailbox,c.f.branch,task)['status'],'already_present')
        self.assertFalse((c.state/'receipts/LH9806.json').exists())
