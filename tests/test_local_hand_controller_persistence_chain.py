"""Controller admission and Task output publish only complete create-only files."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import errno
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

import test_local_hand_connect as connect_fixtures
from local_hand.protocol import LocalHandError
from local_hand_connect import cli, controller


@unittest.skipIf(os.name == 'nt', 'POSIX persistence injection; Windows deferred')
class ControllerPersistenceChainTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.value = {'unicode': '完整结果', 'number': 12}

    def _write(self, kind, path):
        if kind == 'marker':
            controller._write_create_only(path, controller._json_bytes(self.value, 16384, 'fixture_large'))
        else:
            cli._write_output(str(path), self.value)

    def _error(self, callback):
        try:
            callback()
        except Exception as exc:
            return exc
        return None

    def _assert_uncertain(self, exc, code='controller_file_write_failed'):
        self.assertIsInstance(exc, LocalHandError)
        self.assertEqual(exc.code, code)
        self.assertEqual(exc.status, 'indeterminate')

    def _partial_failure(self):
        original_write = os.write
        calls = 0
        def write(fd, data):
            nonlocal calls
            calls += 1
            if calls == 1:
                return original_write(fd, data[:3])
            raise OSError(errno.ENOSPC, 'fixture partial write then disk full')
        return mock.patch.object(os, 'write', side_effect=write)

    def test_short_writes_publish_complete_json_and_keep_unrelated_file(self):
        original_write = os.write
        for kind in ('marker', 'output'):
            with self.subTest(kind=kind):
                directory = self.root/kind
                directory.mkdir()
                target = directory/'record.json'
                unrelated = directory/'.local-hand-connect-unrelated.tmp'
                unrelated.write_bytes(b'prior evidence')
                with mock.patch.object(os, 'write', side_effect=lambda fd, data: original_write(fd, data[:3])):
                    self._write(kind, target)
                self.assertEqual(json.loads(target.read_bytes()), self.value)
                self.assertEqual(unrelated.read_bytes(), b'prior evidence')
                self.assertEqual(set(directory.iterdir()), {target, unrelated})

    def test_zero_progress_stops_and_leaves_final_name_retryable(self):
        for kind in ('marker', 'output'):
            with self.subTest(kind=kind):
                target = self.root/(kind+'.json')
                calls = 0
                def write(fd, data):
                    nonlocal calls
                    calls += 1
                    if calls > 1:
                        raise AssertionError('writer retried after zero progress')
                    return 0
                with mock.patch.object(os, 'write', side_effect=write):
                    error = self._error(lambda: self._write(kind, target))
                self._assert_uncertain(error)
                self.assertEqual(calls, 1)
                self.assertFalse(target.exists())
                self._write(kind, target)
                self.assertEqual(json.loads(target.read_bytes()), self.value)

    def test_prepublication_failures_do_not_occupy_final_name(self):
        original_close = os.close
        for kind in ('marker', 'output'):
            for operation in ('partial-write', 'fsync', 'close', 'write-and-close'):
                with self.subTest(kind=kind, operation=operation):
                    directory = self.root/(kind+'-'+operation)
                    directory.mkdir()
                    target = directory/'record.json'
                    closed = []
                    def close(fd):
                        closed.append(fd)
                        if len(closed) > 1:
                            raise AssertionError('owned descriptor closed twice')
                        original_close(fd)
                        raise OSError(errno.EBADF, 'fixture close reported failure')
                    with ExitStack() as patches:
                        if operation in ('partial-write', 'write-and-close'):
                            patches.enter_context(self._partial_failure())
                        if operation == 'fsync':
                            patches.enter_context(mock.patch.object(os, 'fsync', side_effect=OSError(errno.EIO, 'fixture fsync failure')))
                        if operation in ('close', 'write-and-close'):
                            patches.enter_context(mock.patch.object(os, 'close', side_effect=close))
                        error = self._error(lambda: self._write(kind, target))
                    self._assert_uncertain(error)
                    expected_errno = errno.ENOSPC if operation in ('partial-write', 'write-and-close') else errno.EIO if operation == 'fsync' else errno.EBADF
                    self.assertEqual(error.__cause__.errno, expected_errno)
                    if operation in ('close', 'write-and-close'):
                        self.assertEqual(len(closed), 1)
                    self.assertFalse(target.exists())
                    self.assertEqual(list(directory.iterdir()), [])
                    self._write(kind, target)
                    self.assertEqual(json.loads(target.read_bytes()), self.value)

    def test_atomic_publication_does_not_overwrite_concurrent_winner(self):
        original_link = os.link
        for kind in ('marker', 'output'):
            with self.subTest(kind=kind):
                directory = self.root/kind
                directory.mkdir()
                target = directory/'record.json'
                def competing_link(source, destination, **kwargs):
                    target.write_bytes(b'concurrent winner')
                    return original_link(source, destination, **kwargs)
                with mock.patch.object(os, 'link', side_effect=competing_link) as linked:
                    error = self._error(lambda: self._write(kind, target))
                self.assertEqual(linked.call_count, 1)
                self.assertIsInstance(error, LocalHandError)
                expected = 'controller_mailbox_already_initialized' if kind == 'marker' else 'controller_output_exists'
                self.assertEqual(error.code, expected)
                self.assertEqual(target.read_bytes(), b'concurrent winner')
                self.assertEqual(list(directory.iterdir()), [target])

    def test_existing_target_and_symlink_are_never_replaced(self):
        for kind in ('marker', 'output'):
            with self.subTest(kind=kind):
                target = self.root/(kind+'.json')
                original = self.root/(kind+'-original.json')
                original.write_bytes(b'existing evidence')
                target.symlink_to(original)
                error = self._error(lambda: self._write(kind, target))
                self.assertIsInstance(error, LocalHandError)
                expected = 'controller_mailbox_already_initialized' if kind == 'marker' else 'controller_output_exists'
                self.assertEqual(error.code, expected)
                self.assertTrue(target.is_symlink())
                self.assertEqual(original.read_bytes(), b'existing evidence')

    def test_directory_sync_failure_retains_complete_target_as_uncertain(self):
        original_fsync = os.fsync
        for kind in ('marker', 'output'):
            with self.subTest(kind=kind):
                directory = self.root/kind
                directory.mkdir()
                target = directory/'record.json'
                def sync(fd):
                    if stat.S_ISDIR(os.fstat(fd).st_mode):
                        raise OSError(errno.EIO, 'fixture directory synchronization failure')
                    return original_fsync(fd)
                with mock.patch.object(os, 'fsync', side_effect=sync):
                    error = self._error(lambda: self._write(kind, target))
                self._assert_uncertain(error, 'controller_file_durability_unconfirmed')
                self.assertEqual(json.loads(target.read_bytes()), self.value)
                self.assertEqual(list(directory.iterdir()), [target])

    def test_init_failure_then_healthy_retry_and_existing_rejection(self):
        fixture = connect_fixtures.LocalHandConnectTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        mailbox = fixture.root/'fresh-controller'
        fixture._git(fixture.root, 'clone', '--branch', fixture.branch, fixture.remote_url, str(mailbox))
        policy = fixture.root/'transport.json'
        policy.write_text(json.dumps(fixture.policy.as_dict()))
        argv = ['init', '--mailbox-repo', str(mailbox), '--policy', str(policy)]
        original_writer = controller._write_create_only
        def fault(path, data):
            with self._partial_failure():
                return original_writer(path, data)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, fixture.env), redirect_stdout(stdout), redirect_stderr(stderr):
            with mock.patch.object(controller, '_write_create_only', side_effect=fault):
                status = cli.main(argv)
            self.assertEqual(status, 3)
            self.assertEqual(stdout.getvalue(), '')
            self.assertEqual(json.loads(stderr.getvalue())['error_code'], 'controller_file_write_failed')
            self.assertFalse((mailbox/'.git'/controller.CONNECT_MARKER_NAME).exists())
            stdout.seek(0); stdout.truncate(); stderr.seek(0); stderr.truncate()
            self.assertEqual(cli.main(argv), 0)
            marker = mailbox/'.git'/controller.CONNECT_MARKER_NAME
            saved = marker.read_bytes()
            controller.validate_controller_mailbox(mailbox, fixture.branch, expected_policy=fixture.policy)
            stdout.seek(0); stdout.truncate(); stderr.seek(0); stderr.truncate()
            self.assertEqual(cli.main(argv), 2)
            self.assertEqual(json.loads(stderr.getvalue())['error_code'], 'controller_mailbox_already_initialized')
            self.assertEqual(marker.read_bytes(), saved)

    def test_build_output_failure_then_same_cli_retry(self):
        target = self.root/'task.json'
        argv = ['build', '--target-node', 'fixture-node', '--action', 'node.status', '--task-id', 'LH9900', '--output', str(target)]
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with self._partial_failure():
                status = cli.main(argv)
            self.assertEqual(status, 3)
            self.assertEqual(json.loads(stderr.getvalue())['error_code'], 'controller_file_write_failed')
            self.assertFalse(target.exists())
            self.assertEqual(cli.main(argv), 0)
            saved = target.read_bytes()
            self.assertEqual(json.loads(saved)['task_id'], 'LH9900')
            stderr.seek(0); stderr.truncate()
            self.assertEqual(cli.main(argv), 2)
            self.assertEqual(json.loads(stderr.getvalue())['error_code'], 'controller_output_exists')
            self.assertEqual(target.read_bytes(), saved)


if __name__ == '__main__':
    unittest.main()
