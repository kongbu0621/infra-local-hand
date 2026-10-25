"""Selected implementation bytes and installed projection agree, without old approvals."""
import hashlib
import json
import os
import marshal
from pathlib import Path
import py_compile
import subprocess
import tempfile
import unittest
from unittest import mock

from admin.local_hand_deploy import identity
from admin.local_hand_deploy.model import DeployError
from local_hand import provenance


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        names = set(provenance._SOURCE_PROJECTION_REQUIRED)
        names.update('tools/admin/local_hand_deploy/' + name for name in
                     ('__init__.py', 'identity.py', 'cli.py', 'coordinator.py'))
        for name in names:
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'# isolated identity fixture\n'); path.chmod(0o644)
        for path in self.root.rglob('*'):
            if path.is_dir(): path.chmod(0o755)
        self.root.chmod(0o755)
        self.files = {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest() for name in names}
        for module, path in ((identity, self.root / 'tools/admin/local_hand_deploy/identity.py'),
                             (provenance, self.root / 'tools/local_hand/provenance.py')):
            patcher = mock.patch.object(module, '__file__', str(path)); patcher.start(); self.addCleanup(patcher.stop)

    def project(self):
        value = {'schema': provenance.SOURCE_PROJECTION_SCHEMA, 'source_commit': 'a' * 40,
                 'source_tree': 'b' * 40,
                 'files': {name: {'mode': 0o644, 'sha256': value} for name, value in self.files.items()}}
        path = self.root / provenance.SOURCE_PROJECTION_MANIFEST
        path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n'); path.chmod(0o644)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.PIPE,
            env={**os.environ, 'GIT_CONFIG_SYSTEM': os.devnull, 'GIT_CONFIG_GLOBAL': os.devnull}, text=True).strip()

    def source(self):
        self.git('init', '-q'); self.git('config', 'user.name', 'Identity fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('add', '.'); self.git('commit', '-qm', 'fixture')

    def test_installed_administrator_is_in_projection_and_digest(self):
        self.project()
        value = identity.implementation_identity()
        self.assertEqual('a' * 40, value['source_commit'])
        self.assertEqual(64, len(value['adapter_digest']))
        (self.root / 'tools/admin/local_hand_deploy/coordinator.py').write_bytes(b'changed = True\n')
        with self.assertRaises(RuntimeError): identity.implementation_identity()

    def test_unmanifested_projection_entry_cannot_shadow_installed_code(self):
        self.project()
        (self.root / 'tools/admin/local_hand_deploy/extra.py').write_bytes(b'pass\n')
        with self.assertRaises(RuntimeError): identity.implementation_identity()

    def test_source_checks_selected_bytes_without_requiring_unrelated_clean_worktree(self):
        self.source()
        value = identity.implementation_identity()
        (self.root / 'README.md').write_text('Unrelated documentation edit\n')
        # These real repository siblings are not Python import candidates and
        # are intentionally omitted from the installed source projection.
        for name in ('README.md', 'quota_syscall_filter.h', 'quota_fd_query.c'):
            (self.root / 'tools/admin/local_hand_quota_observer' / name).write_text('Other source or docs\n')
        self.assertEqual(value, identity.implementation_identity())
        (self.root / 'tools/admin/local_hand_deploy/coordinator.py').write_bytes(b'changed = True\n')
        with self.assertRaises(DeployError): identity.implementation_identity()

    def test_source_rejects_hidden_index_drift_and_untracked_modules(self):
        self.source()
        name = 'tools/admin/local_hand_deploy/coordinator.py'
        self.git('update-index', '--skip-worktree', name)
        (self.root / name).write_bytes(b'changed = True\n')
        with self.assertRaises(DeployError): identity.implementation_identity()
        (self.root / name).write_bytes(b'# isolated identity fixture\n')
        (self.root / 'tools/admin/local_hand_deploy/extra.py').write_bytes(b'pass\n')
        with self.assertRaises(DeployError): identity.implementation_identity()

    def test_source_rejects_unbound_namespace_initializer(self):
        self.source()
        (self.root / 'tools/admin/__init__.py').write_bytes(b'executed = True\n')
        with self.assertRaises(DeployError): identity.implementation_identity()

    def test_source_requires_the_same_core_entries_as_installed_projection(self):
        self.source()
        self.git('rm', '-q', 'tests/e3_host/q2_prepare.py')
        self.git('commit', '-qm', 'incomplete fixture')
        with self.assertRaises(DeployError): identity.implementation_identity()

    def test_normal_admin_cache_is_accepted_but_changed_executable_code_is_not(self):
        self.source()
        original = identity.implementation_identity()
        source = self.root / 'tools/admin/local_hand_deploy/coordinator.py'
        cache = Path(py_compile.compile(str(source), doraise=True))
        self.assertEqual(original, identity.implementation_identity())
        raw = cache.read_bytes()
        cache.write_bytes(raw[:16] + marshal.dumps(compile('different = True\n', str(source), 'exec')))
        with self.assertRaises(DeployError): identity.implementation_identity()

    def test_normal_runtime_cache_is_bound_as_well_as_admin_cache(self):
        self.source()
        source = self.root / 'tools/local_hand/provenance.py'
        cache = Path(py_compile.compile(str(source), doraise=True))
        identity.implementation_identity()
        raw = cache.read_bytes()
        cache.write_bytes(raw[:16] + marshal.dumps(compile('different = True\n', str(source), 'exec')))
        with self.assertRaises(DeployError): identity.implementation_identity()

    def test_selected_source_does_not_follow_a_replaced_package_directory(self):
        self.source()
        package = self.root / 'tools/admin/local_hand_deploy'
        retained = self.root / 'retained-package';package.rename(retained)
        package.symlink_to(retained, target_is_directory=True)
        with self.assertRaises(DeployError): identity.implementation_identity()


if __name__ == '__main__': unittest.main()
