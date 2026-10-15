"""Pure runtime/path admission must precede task resource allocation."""
import copy
from pathlib import Path
from unittest.mock import Mock, patch
import unittest
import sys

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux resident preparation')

from admin.local_hand_system_manager import provision_task
from test_e3_quota_q2_prepare_driver import fixture, d as driver
from test_local_hand_local_a2_preparation import runtime_fixture


class LocalA2PreallocationTests(unittest.TestCase):
    def value(self):
        runtime = runtime_fixture()
        plan = dict(directories={'management': {'path': '/allocation/management'}},
                    roots=[{'path': '/allocation/work'}])
        return dict(plan=plan, bases=['/allocation/base'], local_a2=dict(
            inputs={'runtime_ref': 'ledger-a2'}, runtimes={'ledger-a2': runtime}))

    def test_all_preparation_write_groups_reject_input_overlap_in_both_directions(self):
        for field in ('source_root', 'runtime_root', 'runtime_python',
                      'runtime_python_realpath', 'package_root', 'wheel'):
            for group in ('base', 'management', 'quota'):
                for relation in ('equal', 'child', 'parent'):
                    with self.subTest(field=field, group=group, relation=relation):
                        value = self.value()
                        source = Path(value['local_a2']['runtimes']['ledger-a2'][field])
                        target = str({'equal': source, 'child': source / 'task', 'parent': source.parent}[relation])
                        if group == 'base':
                            value['bases'] = [target]
                        elif group == 'management':
                            value['plan']['directories']['management']['path'] = target
                        else:
                            value['plan']['roots'][0]['path'] = target
                        before = copy.deepcopy(value)
                        with self.assertRaisesRegex(ValueError, 'PROVISION_LOCAL_A2_INPUT_OVERLAP'):
                            provision_task.check_local_a2_paths_before_allocation(value, value['plan'])
                        self.assertEqual(before, value)

    def test_disjoint_and_similarly_named_paths_need_no_runtime_files(self):
        value = self.value()
        value['bases'] = ['/registered/ledger-runtime-adjacent']
        before = copy.deepcopy(value)
        with patch.object(provision_task.os, 'open', side_effect=AssertionError('must remain pure')):
            provision_task.check_local_a2_paths_before_allocation(value, value['plan'])
        self.assertEqual(before, value)
        provision_task.check_local_a2_paths_before_allocation({}, {})

    def test_loaded_input_rejects_conflicting_or_extra_runtime_before_allocation(self):
        value = self.value()
        value['workspace'] = {}
        with self.assertRaisesRegex(ValueError, 'PROVISION_JOB_CONFLICT'):
            provision_task.check_local_a2_paths_before_allocation(value, value['plan'])
        del value['workspace']
        value['local_a2']['runtimes']['unselected'] = runtime_fixture()
        with self.assertRaisesRegex(ValueError, 'PROVISION_RUNTIME_BINDING'):
            provision_task.check_local_a2_paths_before_allocation(value, value['plan'])

    def test_real_prepare_rejects_before_first_mkdir_or_quota_mutation(self):
        plan, _ = fixture()
        plan['host'] = {'boot_id': 'modeled-boot'}
        runtime = runtime_fixture()
        runtime.update(runtime_root='/synthetic-q2', runtime_python='/synthetic-q2/bin/python',
                       package_root='/synthetic-q2/lib/python3.12/site-packages/infra_artifact_ledger')
        value = dict(plan=plan, bases=['/synthetic-q2/new-attempt'], observed={'parents': {}},
            installation=dict(source={'commit': 'a' * 40}, installed=dict(
                payload_digest='b' * 64, package_root='/installed')),
            local_a2=dict(inputs={'runtime_ref': 'ledger-a2'}, runtimes={'ledger-a2': runtime}))
        # Keep the real driver validation. Only deployment observations and
        # helpers that must never be invoked are modeled; no host writes occur.
        quota, assembly = Mock(), Mock()
        helpers = {'q2_prepare': quota, 'q2_prepare_driver': driver, 'q2_prepare_assembly': assembly}
        with patch.object(provision_task.os, 'geteuid', return_value=0), \
                patch.object(provision_task.budget, 'current_clock', return_value={'boot_id': 'modeled-boot'}), \
                patch.object(provision_task, 'verify_release'), \
                patch.object(provision_task, '_helper', side_effect=lambda _, name: helpers[name]), \
                patch.object(provision_task.os, 'open') as opened, \
                patch.object(provision_task.Path, 'mkdir') as mkdir:
            with self.assertRaisesRegex(ValueError, 'PROVISION_LOCAL_A2_INPUT_OVERLAP'):
                provision_task.prepare(value)
        opened.assert_not_called()
        mkdir.assert_not_called()
        quota.Quota.assert_not_called()
        assembly.assemble.assert_not_called()


if __name__ == '__main__':
    unittest.main()
