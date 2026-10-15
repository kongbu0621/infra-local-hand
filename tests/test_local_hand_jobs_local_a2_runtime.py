"""Runtime byte checks and fixed runner routing; no real-filesystem acceptance claim.

The payload fixture is deliberately synthetic, with the fixed Git blobs patched
only inside tests. Production always pins the reviewed Ledger source payload.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import venv
import zipfile

if sys.platform != 'linux':
    raise unittest.SkipTest('Local A2 supervised runtime requires Linux')

from local_hand_jobs import local_a2_jobs as a2, runner
from local_hand_jobs.contract import JobError
from test_local_hand_jobs_local_a2_admission import runtime_fixture
from test_local_hand_jobs_runner import helper_budget_fixture


def synthetic_runtime(root):
    """Return descriptor + synthetic blob map; never a deployment receipt."""
    root = Path(root)
    descriptor = runtime_fixture(root)
    venv.EnvBuilder(with_pip=False, symlinks=True).create(descriptor['runtime_root'])
    descriptor['runtime_python_realpath'] = str(Path(descriptor['runtime_python']).resolve())
    package = Path(descriptor['package_root'])
    package = Path(descriptor['runtime_root']) / 'lib' / ('python%d.%d' % sys.version_info[:2]) / 'site-packages/infra_artifact_ledger'
    descriptor['package_root'] = str(package)
    package.mkdir(parents=True)
    blobs = {}
    for name in a2.SOURCE_BLOBS:
        raw = ('# synthetic fixture only\nVALUE = %r\n' % name).encode()
        path = Path(descriptor['source_root']) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        blobs[name] = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if name in a2.MODULE_FILES:
            (package / Path(name).name).write_bytes(raw)
    console = Path(descriptor['runtime_root']) / 'bin/artifact-ledger'
    console.write_text('# synthetic entry; never invoked\n')
    wheel = Path(descriptor['wheel'])
    wheel.parent.mkdir(parents=True)
    with zipfile.ZipFile(wheel, 'x') as archive:
        for name in a2.MODULE_FILES:
            archive.writestr(name.removeprefix('src/'), (Path(descriptor['source_root']) / name).read_bytes())
    for key, path in (('runtime_python_sha256', descriptor['runtime_python_realpath']),
                      ('venv_config_sha256', Path(descriptor['runtime_root']) / 'pyvenv.cfg'),
                      ('console_script_sha256', console), ('wheel_sha256', wheel)):
        descriptor[key] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    descriptor['source_blobs'] = blobs
    return descriptor, blobs


def execution_fixture(root, descriptor):
    profile = {'python': sys.executable, 'work_root': str(Path(root) / 'work'),
        'temporary_root': str(Path(root) / 'temporary'), 'evidence_root': str(Path(root) / 'evidence'),
        'local_a2_runtimes': {'installed-a2': descriptor},
        'budgets': dict(wall_seconds=60, terminate_grace_seconds=1, cpu_seconds=30,
            memory_bytes=128 * 1024**2, processes=16, temporary_bytes=1024**2,
            nas_bytes=0, log_bytes=65536, reservation_bytes=4 * 1024**2)}
    return a2.build_plan({'operation_id': 'synthetic-runtime', 'kind': a2.KIND,
                         'inputs': {'runtime_ref': 'installed-a2'}}, profile)


class LocalA2RuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.descriptor, blobs = synthetic_runtime(self.root)
        patched = patch.object(a2, 'SOURCE_BLOBS', blobs)
        patched.start(); self.addCleanup(patched.stop)
        self.plan = execution_fixture(self.root, self.descriptor)
        for root in self.plan['roots'].values(): Path(root).mkdir(parents=True)
        self.evidence = Path(self.plan['roots']['evidence'])

    def probe(self):
        stage = a2.runtime_probe_stage(self.plan)
        observed = runner._capture_stage(stage, self.evidence, 65536, 10)
        return a2.finish_runtime_probe(self.plan, self.evidence, observed)

    def test_source_wheel_installed_binding_accepts_normal_venv_symlink(self):
        self.assertTrue(Path(self.descriptor['runtime_python']).is_symlink())
        facts = a2.verify_inputs(self.plan)
        self.assertTrue(facts['local_a2_payload_verified'])
        self.assertNotIn('local_a2_runtime_verified', facts)
        self.assertEqual(17, facts['installed_module_count'])
        facts.update(self.probe())
        self.assertTrue(a2.local_effects_only(self.plan, facts))
        self.assertEqual('CALLER_ASSERTED_NOT_GIT_ATTESTED', facts['source_commit_evidence'])

    def test_each_input_mutation_is_rejected_before_task_parent_creation(self):
        paths = [Path(self.descriptor['source_root']) / a2.SCRIPT_FILE,
                 Path(self.descriptor['source_root']) / a2.MODULE_FILES[0],
                 Path(self.descriptor['package_root']) / Path(a2.MODULE_FILES[0]).name,
                 Path(self.descriptor['runtime_root']) / 'bin/artifact-ledger',
                 Path(self.descriptor['runtime_root']) / 'pyvenv.cfg', Path(self.descriptor['wheel'])]
        for path in paths:
            original = path.read_bytes()
            try:
                path.write_bytes(original + b'\n# changed')
                with self.subTest(path=path.name), self.assertRaises((ValueError, JobError)):
                    a2.verify_inputs(self.plan)
                self.assertFalse((Path(self.plan['roots']['work']) / 'local-parent').exists())
            finally:
                path.write_bytes(original)

    def test_wheel_rehash_does_not_allow_changed_payload(self):
        wheel = Path(self.descriptor['wheel'])
        with zipfile.ZipFile(wheel, 'w') as archive:
            for index, name in enumerate(a2.MODULE_FILES):
                raw = (Path(self.descriptor['source_root']) / name).read_bytes()
                archive.writestr(name.removeprefix('src/'), raw + (b'# changed\n' if index == 0 else b''))
        self.plan['local_a2_runtime']['wheel_sha256'] = hashlib.sha256(wheel.read_bytes()).hexdigest()
        self.plan['bindings']['runtime_descriptor_digest'] = a2.descriptor_digest(self.plan['local_a2_runtime'])
        self.plan['bindings']['wheel_digest'] = self.plan['local_a2_runtime']['wheel_sha256']
        with self.assertRaises(ValueError): a2.verify_inputs(self.plan)

    def test_startup_hooks_and_added_package_inputs_are_rejected(self):
        package = Path(self.descriptor['package_root'])
        for path in (package.parent / 'arbitrary.pth', package.parent / 'sitecustomize.pyc',
                     package / 'foreign.so', package / 'extra.py'):
            try:
                path.write_bytes(b'# unadmitted')
                with self.subTest(path=path.name), self.assertRaises(ValueError): a2.verify_inputs(self.plan)
            finally:
                path.unlink()

    def test_valid_pip_style_bytecode_is_verified_without_modifying_runtime(self):
        target = Path(self.descriptor['package_root']) / '__init__.py'
        subprocess.run([self.descriptor['runtime_python'], '-I', '-S', '-B', '-c',
                        'import py_compile,sys; py_compile.compile(sys.argv[1], doraise=True)', str(target)], check=True)
        before = {path.name: path.read_bytes() for path in (target.parent / '__pycache__').iterdir()}
        self.assertTrue(self.probe()['installed_bytecode_verified'])
        self.assertEqual(before, {path.name: path.read_bytes() for path in (target.parent / '__pycache__').iterdir()})

    def test_unchecked_hash_foreign_bytecode_is_rejected_without_executing_it(self):
        target = Path(self.descriptor['package_root']) / '__init__.py'
        marker = self.root / 'never-executed'
        code = ('import importlib.util,marshal,pathlib,sys; p=pathlib.Path(sys.argv[1]); '
                'c=pathlib.Path(importlib.util.cache_from_source(str(p))); c.parent.mkdir(exist_ok=True); '
                'c.write_bytes(importlib.util.MAGIC_NUMBER+(1).to_bytes(4,"little")+b"0"*8+'
                'marshal.dumps(compile(sys.argv[2],str(p),"exec")))')
        foreign = 'open(%r,"w").write("BAD")' % str(marker)
        subprocess.run([self.descriptor['runtime_python'], '-I', '-S', '-B', '-c', code, str(target), foreign], check=True)
        with self.assertRaises(ValueError): self.probe()
        self.assertFalse(marker.exists())

    def test_non_fixed_paths_commands_environment_and_runtime_facts_never_prove_local_scope(self):
        self.assertTrue(a2.local_effects_only(self.plan))
        self.assertTrue(a2.local_effects_only(json.loads(json.dumps(self.plan, sort_keys=True))))
        self.assertFalse(a2.local_effects_only(self.plan, {}))
        for mutator in (lambda p: p['stages'][0]['argv'].extend(['--storage-config', '/nas']),
                        lambda p: p['writable'].append('/outside'),
                        lambda p: p['environment'].update(PYTHONPATH='/source'),
                        lambda p: p['stages'][0]['env'].update(PYTHONPATH='/source'),
                        lambda p: p.update(prepared={'fake': True}),
                        lambda p: p['budgets'].update(nas_bytes=1)):
            altered = copy.deepcopy(self.plan); mutator(altered)
            self.assertFalse(a2.local_effects_only(altered))
        from local_hand_jobs.policy import freeze
        self.assertTrue(a2.local_effects_only(freeze(self.plan)))

    def report(self):
        a2.prepare_run(self.plan, self.evidence)
        work = Path(self.plan['roots']['work']) / 'local-parent/a2-installed-fixture'
        work.mkdir()
        return {'result': 'PASS', 'python': '3.12.0', 'sqlite': '3.0', 'platform': 'fixture',
            'package_version': '0.2.0a1', 'module_path': str(Path(self.descriptor['package_root']) / '__init__.py'),
            'source_commit': self.descriptor['source_commit'], 'source_commit_evidence': a2.SOURCE_EVIDENCE,
            'wheel_bytes_evidence': 'NOT_ATTESTED_BY_THIS_SMOKE_TOOL; bind wheel digest separately',
            'calls': [{'entry': entry, 'operation': op, 'status': 'PASS'} for entry in ('api', 'cli')
                      for op in ('create', 'verify', 'restore', 'check_restore')],
            'work_dir': str(work), 'nas_publish_flow': 'NOT_RUN', 'nas_capability_acceptance': 'NOT_ATTESTED',
            'nas_loss_exercise': 'NOT_RUN'}

    def test_report_requires_exact_eight_passes_no_nas_and_separate_wheel_binding(self):
        report = self.report()
        stdout = self.evidence / 'a2-installed-local.stdout'
        stderr = self.evidence / 'a2-installed-local.stderr'; stderr.write_bytes(b'')
        stage = {'name': 'a2-installed-local', 'outcome': 'SUCCEEDED', 'exit_code': 0}
        stdout.write_text(json.dumps(report) + '\n')
        result = a2.finish_run(self.plan, self.evidence, stage)
        self.assertEqual(self.descriptor['wheel_sha256'], result['wheel_digest'])
        for mutation in ({'calls': report['calls'][:-1]}, {'nas_publish_flow': 'PASS'}, {'result': 'FAIL'},
                         {'work_dir': str(self.root)}, {'extra': True}, {'python': 3}):
            stdout.write_text(json.dumps(dict(report, **mutation)) + '\n')
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, JobError)):
                a2.finish_run(self.plan, self.evidence, stage)
        stdout.write_text(json.dumps(report)[:-1] + ',"result":"PASS"}\n')
        with self.assertRaises(JobError): a2.finish_run(self.plan, self.evidence, stage)
        stdout.write_text(json.dumps(report) + '\n'); stderr.write_bytes(b'warning')
        with self.assertRaises(ValueError): a2.finish_run(self.plan, self.evidence, stage)

    def test_existing_local_parent_is_not_reused_or_deleted(self):
        a2.prepare_run(self.plan, self.evidence)
        parent = Path(self.plan['roots']['work']) / 'local-parent'
        marker = parent / 'preserved'; marker.write_bytes(b'original')
        with self.assertRaises(FileExistsError): a2.prepare_run(self.plan, self.evidence)
        self.assertEqual(b'original', marker.read_bytes())


class LocalA2RunnerRoutingTests(unittest.TestCase):
    def test_runner_uses_existing_runtime_and_requires_bytecode_then_report(self):
        for mode in ('preflight', 'business', 'probe-failed', 'report-failed'):
            phase = 'preflight' if mode == 'preflight' else 'business'
            with self.subTest(mode=mode), helper_budget_fixture(phase) as (plan, target):
                descriptor = runtime_fixture(Path(plan['roots']['work']).parent / 'inputs')
                base = execution_fixture(Path(plan['roots']['work']).parent / 'resolved', descriptor)
                # Reuse the existing real helper budget and namespace fixture.
                for name in ('kind', 'local_a2_runtime', 'bindings', 'runtime_ref'):
                    plan[name] = base[name]
                plan['stages'] = [{'name': 'a2-installed-local', 'argv': [descriptor['runtime_python']]}]
                observations = []
                def capture(stage, directory, limit, remaining, deadline):
                    observations.append((stage['name'], limit, remaining, deadline))
                    return {'name': stage['name'], 'outcome': 'SUCCEEDED', 'exit_code': 0,
                            'bytes_retained': {'stdout': 1, 'stderr': 0}}
                with patch.object(a2, 'verify_inputs', return_value={'inputs_stable': True}), \
                     patch.object(a2, 'runtime_probe_stage', return_value={'name': 'a2-runtime-bytecode'}), \
                     patch.object(a2, 'finish_runtime_probe', side_effect=ValueError('bytecode mismatch') if mode == 'probe-failed' else None,
                                  return_value={'local_a2_runtime_verified': True}), \
                     patch.object(a2, 'prepare_run') as prepare, \
                     patch.object(a2, 'finish_run', side_effect=ValueError('bad report') if mode == 'report-failed' else None,
                                  return_value={'scope': 'TASK_OWNED_LOCAL_A2'}) as finish, \
                     patch.object(runner, '_capture_stage', side_effect=capture), \
                     patch.object(runner, '_interpreter_temp_check', return_value={'bytes_retained': {}}) as interpreter:
                    result = runner._helper(plan)
                    runner.ledger_jobs.copy_verified_source.assert_not_called()
                output = json.loads(target.read_text())
                self.assertEqual(plan['bindings']['runtime_descriptor_digest'], output['bindings']['runtime_descriptor_digest'])
                self.assertEqual(0 if mode in ('preflight', 'business') else 1, result)
                self.assertEqual(['a2-runtime-bytecode'] + (['a2-installed-local'] if mode in ('business', 'report-failed') else []),
                                 [item[0] for item in observations])
                self.assertTrue(all(item[1] > 0 and item[2] > 0 and item[3] is not None for item in observations))
                if mode == 'probe-failed':
                    self.assertFalse(output['business_started']); prepare.assert_not_called(); interpreter.assert_not_called()
                elif mode == 'preflight':
                    self.assertFalse(output['business_started']); prepare.assert_not_called(); finish.assert_not_called()
                else:
                    prepare.assert_called_once(); finish.assert_called_once()
                    self.assertEqual(mode == 'business', output['effects_checked'])
                if mode != 'probe-failed':
                    self.assertEqual(descriptor['runtime_python'], interpreter.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
