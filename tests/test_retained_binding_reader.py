"""Recovery declaration reads using real descriptors and synthetic admin metadata."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from admin.local_hand_system_manager import retained_reader as reader
from local_hand_jobs import quota_contract as q
from local_hand_jobs.contract import JobError, MAX_REQUEST_BYTES, Principal, TOOL_SCOPES


@unittest.skipUnless(sys.platform == 'linux', 'Linux protected declaration descriptors')
class RetainedBindingReaderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'binding.json'
        self.value = {'schema': 'synthetic-declaration', 'value': 17}
        self.path.write_text(json.dumps(self.value))
        self.path.chmod(0o600)

    @contextmanager
    def administrator_metadata(self, alter=None):
        real_fstat = os.fstat
        selected = self.path.stat().st_ino

        def observed(fd):
            info = real_fstat(fd)
            value = SimpleNamespace(**{k: getattr(info, k) for k in dir(info) if k.startswith('st_')})
            # Only admin ownership and /tmp's shared-write mode are synthetic.
            # All descriptors, object types, links, sizes and timestamps are real.
            value.st_uid = 0
            value.st_mode &= ~0o022
            if alter is not None and info.st_ino == selected:
                alter(value)
            return value

        with patch.object(reader.os, 'fstat', side_effect=observed):
            yield

    def close_fault(self, *, reuse=False):
        real_open, real_close = os.open, os.close
        owned, replacement, closes = set(), [], []

        def opened(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            owned.add(fd)
            return fd

        def closed(fd):
            closes.append(fd)
            real_close(fd)
            owned.discard(fd)
            if len(closes) == 1:
                if reuse:
                    replacement.append(opened('/dev/null', os.O_RDONLY))
                    self.assertEqual(fd, replacement[0])
                raise OSError('synthetic close failure after release')

        try:
            with patch.object(reader.os, 'open', side_effect=opened), \
                 patch.object(reader.os, 'close', side_effect=closed):
                with self.assertRaises((OSError, JobError)):
                    reader.read_descriptor(str(self.path))
            self.assertEqual(set(replacement), owned, 'new child leaked or reused descriptor closed')
            self.assertEqual(len(closes), len(set(closes)), 'released descriptor was closed again')
            for fd in replacement:
                os.fstat(fd)
        finally:
            for fd in owned:
                real_close(fd)
        with self.administrator_metadata():
            self.assertEqual(self.value, reader.read_descriptor(str(self.path)))

    def test_final_cleanup_failure_cannot_return_success(self):
        selected = self.path.stat().st_ino
        real_close, real_fstat = os.close, os.fstat

        def close(fd):
            final = real_fstat(fd).st_ino == selected
            real_close(fd)
            if final:
                raise OSError('synthetic close failure after valid declaration')

        before = set(os.listdir('/proc/self/fd'))
        with self.administrator_metadata(), patch.object(reader.os, 'close', side_effect=close):
            with self.assertRaises(JobError) as failed:
                reader.read_descriptor(str(self.path))
            self.assertEqual('IO_UNCERTAIN', failed.exception.code)
        self.assertEqual(before, set(os.listdir('/proc/self/fd')))
        with self.administrator_metadata():
            self.assertEqual(self.value, reader.read_descriptor(str(self.path)))

    def test_short_reads_and_exact_byte_limit_then_oversize_rejection(self):
        raw = json.dumps(self.value).encode()
        self.path.write_bytes(raw + b' ' * (MAX_REQUEST_BYTES - len(raw)))
        real_read = os.read
        with self.administrator_metadata(), \
             patch.object(reader.os, 'read', side_effect=lambda fd, size: real_read(fd, min(size, 97))):
            self.assertEqual(self.value, reader.read_descriptor(str(self.path)))
        self.path.write_bytes(self.path.read_bytes() + b' ')
        with self.administrator_metadata(), patch.object(reader.os, 'read') as read:
            with self.assertRaises(q.QuotaError) as failed:
                reader.read_descriptor(str(self.path))
            self.assertEqual('SESSION_SIZE', failed.exception.code)
            read.assert_not_called()

    def test_protection_links_and_object_types_remain_required(self):
        for key, value in (('st_uid', 1), ('st_mode', 0o100622), ('st_nlink', 2)):
            with self.subTest(field=key), \
                 self.administrator_metadata(lambda info: setattr(info, key, value)):
                with self.assertRaises(q.QuotaError) as failed:
                    reader.read_descriptor(str(self.path))
                self.assertEqual('SESSION_PROTECTION', failed.exception.code)
        alias = self.root / 'alias'
        alias.symlink_to(self.path)
        parent_alias = self.root / 'parent-alias'
        parent_alias.symlink_to(self.root, target_is_directory=True)
        hardlink = self.root / 'hardlink'
        os.link(self.path, hardlink)
        fifo = self.root / 'fifo'
        os.mkfifo(fifo, 0o600)
        directory = self.root / 'directory'
        directory.mkdir(mode=0o700)
        for path in (alias, parent_alias / self.path.name, hardlink, fifo, directory):
            with self.subTest(path=path.name), self.administrator_metadata():
                with self.assertRaises((OSError, q.QuotaError)):
                    reader.read_descriptor(str(path))
        hardlink.unlink()
        with self.administrator_metadata():
            self.assertEqual(self.value, reader.read_descriptor(str(self.path)))

    def test_parser_limits_and_invalid_paths_remain_required(self):
        cases = ((b'{"x":1,"x":2}', 'DUPLICATE_KEY'), (b'{"x":1.0}', 'NON_INTEGER_NUMBER'),
                 (b'{"x":NaN}', 'NON_INTEGER_NUMBER'), (b'"\\ud800"', 'SURROGATE'),
                 (b'[' * 13 + b'0' + b']' * 13, 'DEPTH'), (b'9223372036854775808', 'INTEGER'))
        for raw, code in cases:
            self.path.write_bytes(raw)
            with self.subTest(code=code), self.administrator_metadata():
                with self.assertRaises(q.QuotaError) as failed:
                    reader.read_descriptor(str(self.path))
                self.assertEqual(code, failed.exception.code)
        for path in ('/', 'relative', '//root/file', '/root/../file', '/root/file\x00'):
            with self.subTest(path=repr(path)), patch.object(reader.os, 'open') as opened:
                with self.assertRaises(q.QuotaError):
                    reader.read_descriptor(path)
                opened.assert_not_called()

    def test_metadata_changes_and_interrupted_reads_release_descriptors(self):
        for field in ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
                      'st_size', 'st_mtime_ns', 'st_ctime_ns'):
            calls = 0

            def drift(info):
                nonlocal calls
                calls += 1
                if calls == 2:
                    setattr(info, field, getattr(info, field) + 1)

            before = set(os.listdir('/proc/self/fd'))
            with self.subTest(field=field), self.administrator_metadata(drift):
                with self.assertRaises(q.QuotaError) as failed:
                    reader.read_descriptor(str(self.path))
                self.assertEqual('SESSION_CHANGED', failed.exception.code)
            self.assertEqual(before, set(os.listdir('/proc/self/fd')))
        interrupted = KeyboardInterrupt('synthetic interruption')
        with self.administrator_metadata(), patch.object(reader.os, 'read', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt) as failed:
                reader.read_descriptor(str(self.path))
            self.assertIs(interrupted, failed.exception)
        self.assertEqual(before, set(os.listdir('/proc/self/fd')))
        with self.administrator_metadata():
            self.assertEqual(self.value, reader.read_descriptor(str(self.path)))

    def test_declaration_failure_precedes_ledger_then_same_readonly_request_retries(self):
        from test_retained_filesystem_reader import RetainedFilesystemTests, OP
        fixture = RetainedFilesystemTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        config, policy, binding = fixture.prepare_ledger()
        database = Path(config['broker_root']) / 'jobs.sqlite'
        original = database.read_bytes(), policy.read_bytes()
        read = reader.read_descriptor

        def protected(path):
            with self.administrator_metadata():
                return read(path)

        self.path.write_bytes(b'{invalid')
        with patch.object(reader, 'read_descriptor', side_effect=protected), \
             patch.object(reader, 'verify_release'), patch.object(reader, 'observe_filesystem'):
            with patch.object(reader, 'StateStore') as state, patch.object(reader, 'AuthorityLock') as lock:
                with self.assertRaises(q.QuotaError):
                    reader.open_reader(policy, self.path)
                state.assert_not_called()
                lock.assert_not_called()
            self.path.write_text(json.dumps(binding))
            declared = self.path.read_bytes()
            broker = reader.open_reader(policy, self.path)
            try:
                broker.start()
                self.assertTrue(broker.read_only)
                principal = Principal('owner', frozenset(TOOL_SCOPES.values()))
                result = broker.call('lh_job_status', {'operation_id': OP}, principal)
                self.assertEqual('original-digest', result['request_digest'])
                with self.assertRaises(JobError):
                    broker.call('lh_job_submit', {}, principal)
            finally:
                reader.cli.close_service(broker, None)
        self.assertEqual(original, (database.read_bytes(), policy.read_bytes()))
        self.assertEqual(declared, self.path.read_bytes())

    def test_failed_parent_close_releases_new_child_then_allows_retry(self):
        self.close_fault()

    def test_failed_parent_close_never_closes_reused_descriptor(self):
        self.close_fault(reuse=True)

    def test_primary_parse_error_survives_final_close_failure(self):
        self.path.write_bytes(b'{invalid')
        selected = self.path.stat().st_ino
        real_close, real_fstat = os.close, os.fstat
        before = set(os.listdir('/proc/self/fd'))

        def close(fd):
            final = real_fstat(fd).st_ino == selected
            real_close(fd)
            if final:
                raise OSError('synthetic final close failure after release')

        with self.administrator_metadata(), patch.object(reader.os, 'close', side_effect=close):
            with self.assertRaises(q.QuotaError) as failed:
                reader.read_descriptor(str(self.path))
            self.assertEqual('JSON', failed.exception.code)
            self.assertTrue(failed.exception.__notes__)
        self.assertEqual(before, set(os.listdir('/proc/self/fd')))
        self.path.write_text(json.dumps(self.value))
        with self.administrator_metadata():
            self.assertEqual(self.value, reader.read_descriptor(str(self.path)))
