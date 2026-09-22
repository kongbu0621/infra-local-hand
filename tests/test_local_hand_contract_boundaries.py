"""Targeted action-result and installed flat-payload boundary checks."""
from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from config_fixtures import profile_v2
from local_hand import act, observe, provenance
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError


class ContractBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'projects/demo'
        (self.repo / '.git').mkdir(parents=True)
        (self.repo / 'sample.txt').write_bytes(b'before\n')
        path = self.root / 'profile.json'
        path.write_text(json.dumps(profile_v2({
            'node_id': 'fixture-node', 'projects_root': str(self.repo.parent),
            'repositories': {'demo': {'path': 'demo', 'single_writer': True, 'validations': {}}},
        })))
        self.profile = load_profile(path)

    def test_directory_entry_io_failure_is_not_successful_other(self):
        entries = observe.list_directory_bounded(self.repo, 1000, 'fixture_invalid')
        real = next(entry for entry in entries if entry.name == 'sample.txt')
        for method in ('is_symlink', 'is_dir', 'is_file'):
            for fault in (errno.EIO, errno.EACCES):
                with self.subTest(method=method, errno=fault):
                    entry = mock.Mock(wraps=real)
                    entry.name = real.name
                    getattr(entry, method).side_effect = OSError(fault, 'fixture entry metadata failure')
                    with mock.patch.object(observe, 'list_directory_bounded', return_value=[entry]):
                        with self.assertRaises(LocalHandError) as raised:
                            observe.fs_list(self.profile, 'demo')
                    self.assertEqual(raised.exception.code, 'directory_entry_unavailable')
                    self.assertEqual(raised.exception.status, 'indeterminate')
                    self.assertIn('errno=' + str(fault), raised.exception.message)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX special-file observation')
    def test_regular_directory_symlink_and_fifo_remain_distinct(self):
        (self.repo / 'folder').mkdir()
        (self.repo / 'alias').symlink_to('sample.txt')
        os.mkfifo(self.repo / 'channel')
        actual = {entry['name']: entry['kind'] for entry in observe.fs_list(self.profile, 'demo')['entries']}
        for name, kind in {'sample.txt': 'file', 'folder': 'directory', 'alias': 'symlink', 'channel': 'other'}.items():
            self.assertEqual(actual[name], kind)

    def test_invalid_digest_cannot_hide_behind_already_applied(self):
        invalid = ('+' + '0' * 63, ' ' + '0' * 63, '0' * 63 + ' ',
                   'a' * 31 + '_' + 'b' * 32, '\uff10' * 64, '-' + '0' * 63)
        for digest in invalid:
            for content in ('before\n', 'changed\n'):
                with self.subTest(digest=digest, content=content):
                    with self.assertRaises(LocalHandError) as raised:
                        act.fs_write_text_cas(self.profile, 'demo', 'sample.txt', digest, content,
                                              lease_root=self.root / 'leases')
                    self.assertEqual(raised.exception.code, 'invalid_expected_sha256')
                    self.assertEqual((self.repo / 'sample.txt').read_bytes(), b'before\n')

    def test_uppercase_digest_and_valid_already_applied_remain_supported(self):
        digest = hashlib.sha256(b'before\n').hexdigest().upper()
        actual = act.fs_write_text_cas(self.profile, 'demo', 'sample.txt', digest, 'after\n',
                                       lease_root=self.root / 'leases')
        self.assertFalse(actual['already_applied'])
        self.assertEqual((self.repo / 'sample.txt').read_bytes(), b'after\n')
        actual = act.fs_write_text_cas(self.profile, 'demo', 'sample.txt', digest, 'after\n',
                                       lease_root=self.root / 'leases')
        self.assertTrue(actual['already_applied'])

    def _payload(self, name, *, include_controller=True):
        target = self.root / name
        source = Path(provenance.__file__).parent.parent
        for package in ('local_hand', 'local_hand_connect') if include_controller else ('local_hand',):
            folder = target / package
            folder.mkdir(parents=True)
            for original in (source / package).iterdir():
                if original.suffix in ('.py', '.sh', '.ps1'):
                    shutil.copyfile(original, folder / original.name)
        metadata = {'schema_version': provenance.BUILD_SCHEMA, 'product_version': provenance.VERSION,
                    'source_commit': 'a' * 40, 'artifact_kind': 'wheel' if include_controller else 'source-staging',
                    'files': provenance.payload_hashes(target)}
        (target / 'local_hand/_build_metadata.json').write_text(json.dumps(metadata))
        return target, metadata

    def _fresh_metadata(self, target):
        code = """import json,sys
sys.path.insert(0,sys.argv[1])
from local_hand import observe,provenance
from local_hand.protocol import LocalHandError
try:
 metadata=provenance.build_metadata()
except LocalHandError as exc:
 print(json.dumps({'code':exc.code,'status':exc.status,'loaded':observe.__file__}));sys.exit(3)
print(json.dumps({'source_commit':metadata['source_commit'],'loaded':observe.__file__}))
"""
        return subprocess.run([sys.executable, '-I', '-c', code, str(target)],
                              text=True, capture_output=True, timeout=15, check=False)

    def test_same_name_import_package_cannot_keep_original_payload_identity(self):
        target, _ = self._payload('shadow-import')
        clean = self._fresh_metadata(target)
        self.assertEqual(clean.returncode, 0, clean.stderr)
        original = (target / 'local_hand/observe.py').read_bytes()
        shadow = target / 'local_hand/observe'
        shadow.mkdir()
        (shadow / '__init__.py').write_text('def node_status(profile):\n return {"fixture_shadow": True}\n')
        actual = self._fresh_metadata(target)
        self.assertEqual(actual.returncode, 3, actual.stdout + actual.stderr)
        evidence = json.loads(actual.stdout)
        self.assertEqual(evidence['code'], 'provenance_mismatch')
        self.assertEqual(evidence['status'], 'indeterminate')
        self.assertEqual(Path(evidence['loaded']), shadow / '__init__.py')
        self.assertEqual((target / 'local_hand/observe.py').read_bytes(), original)

    def test_flat_payload_rejects_unbound_entries_and_cache_aliases(self):
        scenarios = ('extra-file', 'extension', 'extra-directory', 'package-link',
                     'entry-link', 'cache-link', 'cache-directory', 'cache-extra', 'cache-unknown-source')
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                target, _ = self._payload(scenario)
                package = target / 'local_hand'
                if scenario == 'extra-file': (package / 'unbound.json').write_text('{}')
                elif scenario == 'extension': (package / 'observe.so').write_bytes(b'fixture, not a library')
                elif scenario == 'extra-directory': (package / 'unexpected').mkdir()
                elif scenario == 'package-link':
                    package.rename(target / 'real-package');package.symlink_to('real-package', target_is_directory=True)
                elif scenario == 'entry-link': (package / 'alias').symlink_to('observe.py')
                else:
                    cache = package / '__pycache__'
                    if scenario == 'cache-link':
                        (self.root / 'cache-target').mkdir();cache.symlink_to(self.root / 'cache-target', target_is_directory=True)
                    else:
                        cache.mkdir()
                        if scenario == 'cache-directory': (cache / 'nested').mkdir()
                        elif scenario == 'cache-extra': (cache / 'unbound.txt').write_text('fixture')
                        else: (cache / 'unknown.cpython-312.pyc').write_bytes(b'fixture')
                with self.assertRaises(LocalHandError) as raised:
                    provenance.payload_hashes(target)
                self.assertEqual(raised.exception.code, 'provenance_mismatch')

    def test_metadata_and_real_bytecode_work_for_wheel_and_source_staging(self):
        for controller in (True, False):
            target, metadata = self._payload('valid-' + str(controller), include_controller=controller)
            source = target / 'local_hand/observe.py'
            py_compile.compile(str(source), doraise=True)
            py_compile.compile(str(source), doraise=True, optimize=1)
            self.assertEqual(provenance.payload_hashes(target), metadata['files'])
            actual = self._fresh_metadata(target)
            self.assertEqual(actual.returncode, 0, actual.stderr)
            self.assertEqual(json.loads(actual.stdout)['source_commit'], metadata['source_commit'])


if __name__ == '__main__':
    unittest.main()
