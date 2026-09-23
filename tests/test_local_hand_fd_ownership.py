"""Real descriptor ownership when an output stream cannot be constructed."""
from contextlib import ExitStack
import errno
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE / 'tests')]
from config_fixtures import profile_v2
from local_hand import act, installation
from local_hand.paths import load_profile


class DescriptorOwnership(unittest.TestCase):
    def check_boundary(self, kind, close_error=False):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as patches:
            root = Path(temporary)
            project = root / 'projects' / 'demo'
            project.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            (project / 'sample.txt').write_bytes(b'before\n')
            profile_path = root / 'profile.json'
            profile_path.write_text(json.dumps(profile_v2({'node_id': 'fixture',
                'projects_root': str(root / 'projects'), 'repositories': {
                    'demo': {'path': 'demo', 'single_writer': True, 'validations': {}}}})))
            profile = load_profile(profile_path)
            owned = []
            primary = OSError(errno.EMFILE, 'synthetic wrapper construction failure')
            real_close = os.close
            def wrapper(fd, *args, **kwargs):
                owned.append(fd)
                raise primary
            def close(fd):
                real_close(fd)
                if close_error and fd in owned:
                    raise OSError(errno.EIO, 'synthetic close-after-release failure')
            patches.enter_context(mock.patch.object(os, 'fdopen', wrapper))
            patches.enter_context(mock.patch.object(os, 'close', close))
            if kind == 'installation':
                (root / '_build_metadata.json').write_text('{}\n')
                patches.enter_context(mock.patch.object(installation, '__file__', str(root / 'installation.py')))
                patches.enter_context(mock.patch.object(installation, 'build_metadata', return_value={'artifact_kind': 'source-staging'}))
                patches.enter_context(mock.patch.object(installation, 'implementation_commit', return_value='a' * 40))
                patches.enter_context(mock.patch.object(installation, 'core_digest', return_value='b' * 64))
                invoke = lambda: installation.create_record(profile_path, root / 'record.json',
                    install_instance_id='00000000-0000-4000-8000-000000000001',
                    bindings={key: str(profile_path) for key in installation.ENV_PATHS},
                    state_root=root / 'state', mailbox_root=root / 'mailbox')
            else:
                invoke = lambda: act.fs_write_text_cas(profile, 'demo', 'sample.txt',
                    hashlib.sha256(b'before\n').hexdigest(), 'after\n', lease_root=root / 'leases')
            try:
                with self.assertRaises(OSError) as raised:
                    invoke()
                self.assertIs(raised.exception, primary)
                self.assertEqual(len(owned), 1)
                with self.assertRaises(OSError) as closed:
                    os.fstat(owned[0])
                self.assertEqual(closed.exception.errno, errno.EBADF)
                self.assertEqual((project / 'sample.txt').read_bytes(), b'before\n')
            finally:
                for fd in owned:
                    try:
                        real_close(fd)
                    except OSError:
                        pass

    def test_installation_fdopen_failure_closes_owned_descriptor(self):
        self.check_boundary('installation')

    def test_cas_fdopen_failure_closes_owned_descriptor(self):
        self.check_boundary('cas')

    def test_installation_fdopen_failure_preserves_primary_on_close_error(self):
        self.check_boundary('installation', True)

    def test_cas_fdopen_failure_preserves_primary_on_close_error(self):
        self.check_boundary('cas', True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
