"""Independent checks of startup rejection before any target interpreter launch."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux supervised helper')

from local_hand_jobs import local_a2_jobs as a2, runner
from test_local_hand_jobs_local_a2_runtime import synthetic_runtime, execution_fixture
from test_local_hand_jobs_runner import helper_budget_fixture


class LocalA2ProbeRoutingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runtime, blobs = synthetic_runtime(self.root / 'inputs')
        pinned = patch.object(a2, 'SOURCE_BLOBS', blobs)
        pinned.start(); self.addCleanup(pinned.stop)

    def inventory(self):
        root = Path(self.runtime['runtime_root'])
        return {str(path.relative_to(root)): ('link', path.readlink().as_posix()) if path.is_symlink()
                else ('file', path.read_bytes()) for path in root.rglob('*')
                if path.is_file() or path.is_symlink()}

    def test_normal_runtime_probe_preserves_complete_runtime_file_inventory(self):
        plan = execution_fixture(self.root / 'execution', self.runtime)
        for path in plan['roots'].values(): Path(path).mkdir(parents=True)
        original = self.inventory()
        facts = a2.verify_inputs(plan)
        directory = Path(plan['roots']['evidence'])
        stage = runner._capture_stage(a2.runtime_probe_stage(plan), directory, 65536, 10)
        facts.update(a2.finish_runtime_probe(plan, directory, stage))
        self.assertTrue(facts['local_a2_runtime_verified'])
        self.assertEqual(original, self.inventory())

    def test_invalid_search_configuration_never_starts_probe_or_normal_interpreter(self):
        for phase in ('preflight', 'business'):
            for name in ('python._pth', 'pyvenv.cfg'):
                invalid = Path(self.runtime['runtime_python']).parent / name
                invalid.write_text('import site\n')
                try:
                    with self.subTest(phase=phase, name=name), helper_budget_fixture(phase) as (plan, _):
                        base = execution_fixture(self.root / ('execution-' + phase + '-' + name), self.runtime)
                        for path in base['roots'].values(): Path(path).mkdir(parents=True)
                        plan.update({key: value for key, value in base.items() if key != 'budgets'})
                        target = Path(plan['roots']['evidence']) / 'result.json'
                        plan['result_path'] = str(target)
                        with patch.object(runner, '_capture_stage') as capture, \
                             patch.object(runner, '_interpreter_temp_check') as normal, \
                             patch.object(a2, 'prepare_run') as prepare, \
                             patch.object(a2, '_fail', wraps=a2._fail) as rejected:
                            code = runner._helper(plan)
                        self.assertEqual(1, code)
                        output = json.loads(target.read_text())
                        self.assertEqual('FAILED', output['outcome'])
                        self.assertFalse(output['business_started'])
                        self.assertEqual([], output['stages'])
                        expected = ('runtime has an overriding Python search-path configuration'
                                    if name == 'python._pth' else 'runtime has a shadow venv configuration')
                        rejected.assert_called_once_with(expected)
                        capture.assert_not_called(); normal.assert_not_called(); prepare.assert_not_called()
                finally:
                    invalid.unlink()


if __name__ == '__main__':
    unittest.main()
