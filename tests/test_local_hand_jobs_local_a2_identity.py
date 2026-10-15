"""Independent PR 43 regression probes; no host or A2 acceptance claim."""
import importlib.util
import marshal
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

if sys.platform != 'linux':
    raise unittest.SkipTest('Local A2 supervised runtime requires Linux')

from local_hand_jobs import bootstrap, local_a2_jobs
from local_hand_jobs.contract import JobError
import test_local_hand_jobs_local_a2_runtime as runtime_fixtures


class Pr43IdentityRegressionTests(unittest.TestCase):
    def bytecode_probe(self, *, mutation=None, header='timestamp', optimized=False):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / 'demo'
            package.mkdir()
            source = package / '__init__.py'
            raw = b'def f():\n    return 1\n'
            source.write_bytes(raw)
            original = compile(raw, str(source), 'exec')
            changed = original if mutation is None else original.replace(co_consts=tuple(
                item.replace(**mutation) if isinstance(item, types.CodeType) else item
                for item in original.co_consts))
            if mutation is not None:
                self.assertEqual(original, changed)  # Why CodeType == is insufficient.
            cache = Path(importlib.util.cache_from_source(str(source)))
            cache.parent.mkdir()
            if header == 'timestamp':
                metadata = ((0).to_bytes(4, 'little')
                    + int(source.stat().st_mtime).to_bytes(4, 'little')
                    + len(raw).to_bytes(4, 'little'))
            else:
                metadata = (1).to_bytes(4, 'little') + importlib.util.source_hash(raw)
            cache.write_bytes(importlib.util.MAGIC_NUMBER + metadata + marshal.dumps(changed))
            before = cache.read_bytes()
            probe = subprocess.run([sys.executable, '-I', '-S', '-B',
                *(['-O'] if optimized else []), '-c',
                local_a2_jobs._BYTECODE_PROBE, str(package), '__init__.py'],
                capture_output=True, text=True)
            self.assertEqual(before, cache.read_bytes())
            return probe

    def test_bytecode_probe_rejects_nested_fields_ignored_by_code_equality(self):
        for header in ('timestamp', 'unchecked-hash'):
            for mutation in ({'co_qualname': 'UNREVIEWED_NAME'}, {'co_stacksize': 1000},
                             {'co_filename': '/unreviewed/module.py'}):
                with self.subTest(header=header, mutation=mutation):
                    probe = self.bytecode_probe(mutation=mutation, header=header)
                    self.assertNotEqual(0, probe.returncode,
                        'Probe accepted executable bytecode differing from verified source')
                    self.assertIn('installed bytecode differs from source', probe.stderr)

    def test_bytecode_probe_accepts_unchanged_nested_code_without_writing_cache(self):
        for header in ('timestamp', 'unchecked-hash'):
            with self.subTest(header=header):
                probe = self.bytecode_probe(header=header)
                self.assertEqual(0, probe.returncode, probe.stderr)
                self.assertEqual('LOCAL_A2_BYTECODE_VERIFIED\n', probe.stdout)
                self.assertEqual('', probe.stderr)

    def test_bytecode_probe_rejects_optimization_not_used_by_the_fixed_commands(self):
        probe = self.bytecode_probe(optimized=True)
        self.assertNotEqual(0, probe.returncode)
        self.assertIn('bytecode selection differs from the fixed invocation', probe.stderr)


class LocalA2StartupCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.descriptor, blobs = runtime_fixtures.synthetic_runtime(self.root)
        patched = patch.object(local_a2_jobs, 'SOURCE_BLOBS', blobs)
        patched.start()
        self.addCleanup(patched.stop)
        self.plan = runtime_fixtures.execution_fixture(self.root, self.descriptor)
        for root in self.plan['roots'].values():
            Path(root).mkdir(parents=True)
        self.site = Path(self.descriptor['package_root']).parent

    def test_inactive_old_tag_and_optimized_caches_are_ignored_and_preserved(self):
        source = Path(self.descriptor['package_root']) / '__init__.py'
        subprocess.run([self.descriptor['runtime_python'], '-I', '-S', '-B', '-c',
            'import py_compile,sys; py_compile.compile(sys.argv[1],doraise=True)',
            str(source)], check=True, capture_output=True)
        active = Path(importlib.util.cache_from_source(str(source), optimization=''))
        old_tag = 'cpython-311' if sys.implementation.cache_tag != 'cpython-311' else 'cpython-312'
        inactive = [active.parent / ('__init__.' + old_tag + '.pyc'),
            Path(importlib.util.cache_from_source(str(source), optimization='1')),
            Path(importlib.util.cache_from_source(str(source), optimization='2'))]
        for path in inactive:
            path.write_bytes(b'damaged cache never selected by these fixed commands')
        before = {path: path.read_bytes() for path in [active, *inactive]}
        self.assertTrue(local_a2_jobs.verify_inputs(self.plan)['local_a2_payload_verified'])
        stage = local_a2_jobs.runtime_probe_stage(self.plan)
        probe = subprocess.run(stage['argv'], cwd=stage['cwd'], env=stage['env'],
            capture_output=True, text=True)
        self.assertEqual(0, probe.returncode, probe.stderr)
        self.assertEqual('LOCAL_A2_BYTECODE_VERIFIED\n', probe.stdout)
        actual = subprocess.run([self.descriptor['runtime_python'], '-I', '-B', '-c',
            'import infra_artifact_ledger as m; print(m.VALUE); print(m.__cached__)'],
            env=self.plan['environment'], capture_output=True, text=True)
        self.assertEqual(0, actual.returncode, actual.stderr)
        self.assertEqual('', actual.stderr)
        self.assertEqual(['src/infra_artifact_ledger/__init__.py', str(active)],
            actual.stdout.splitlines())
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_exact_setuptools_hook_is_inert_for_parent_and_child(self):
        hook = self.site / 'distutils-precedence.pth'
        hook.write_bytes(local_a2_jobs._STANDARD_DISTUTILS_PTH)
        marker = self.root / 'unverified-helper-ran'
        (self.site / '_distutils_hack.py').write_text(
            'from pathlib import Path\nPath(%r).write_text("unexpected")\n'
            'raise RuntimeError("unverified helper executed")\n' % str(marker))
        self.assertTrue(local_a2_jobs.verify_inputs(self.plan)['local_a2_payload_verified'])
        self.assertEqual('stdlib', self.plan['environment']['SETUPTOOLS_USE_DISTUTILS'])
        self.assertEqual(self.plan['environment'], self.plan['stages'][0]['env'])
        # As with the fixed walkthrough's CLI subprocess, -I preserves this
        # non-PYTHON environment setting in the child process.
        script = ('import subprocess,sys; import infra_artifact_ledger; '
            'subprocess.run([sys.executable,"-I","-B","-c",'
            '"import infra_artifact_ledger"],check=True)')
        result = subprocess.run([self.descriptor['runtime_python'], '-I', '-B', '-c', script],
            env=self.plan['environment'], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('', result.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(local_a2_jobs._STANDARD_DISTUTILS_PTH, hook.read_bytes())

    def test_modified_or_renamed_startup_hook_is_not_admitted(self):
        for name, raw in (
            ('distutils-precedence.pth', local_a2_jobs._STANDARD_DISTUTILS_PTH + b'import os\n'),
            ('distutils-precedence.pth', local_a2_jobs._STANDARD_DISTUTILS_PTH.replace(b"'local'", b"'stdlib'")),
            ('other.pth', local_a2_jobs._STANDARD_DISTUTILS_PTH),
        ):
            path = self.site / name
            try:
                path.write_bytes(raw)
                with self.subTest(name=name, raw=raw), self.assertRaises(ValueError):
                    local_a2_jobs.verify_inputs(self.plan)
            finally:
                path.unlink()

    def test_bootstrap_only_transports_the_fixed_distutils_setting(self):
        for key in ('environment', 'env'):
            value = {key: self.plan['environment']}
            self.assertEqual(value, bootstrap.decode_payload(bootstrap.encode_payload(value)))
            for changed in ('local', '', None):
                with self.subTest(key=key, changed=changed), self.assertRaises(JobError):
                    bootstrap.encode_payload({key: dict(self.plan['environment'],
                        SETUPTOOLS_USE_DISTUTILS=changed)})

    def test_shadow_configuration_is_rejected_before_any_runtime_probe(self):
        for name in ('pyvenv.cfg', 'python._pth'):
            path = Path(self.descriptor['runtime_python']).parent / name
            try:
                path.write_text('include-system-site-packages = true\n' if name == 'pyvenv.cfg' else 'elsewhere\nimport site\n')
                with self.subTest(name=name), self.assertRaises(ValueError):
                    local_a2_jobs.verify_inputs(self.plan)
            finally:
                path.unlink()


if __name__ == '__main__':
    unittest.main()
