"""New task policies must not inherit the entire project registry."""
import copy
import sys
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux protected task provisioner')

from admin.local_hand_system_manager import provision_task
from local_hand_jobs import quota_contract


class TaskProjectBindingTests(unittest.TestCase):
    def setUp(self):
        self.inputs = dict(source_ref='project-a', validation_ref='core', relative_path='app.py',
                           expected_sha256='a' * 64, content='print(1)\n')
        self.workspace = dict(git={'path': '/usr/bin/git'}, sources={
            'project-a': dict(root='/protected/project-a', commit='a' * 40,
                              blobs={'app.py': '1' * 40, 'support.py': '2' * 40},
                              validations={'core': ['test_core'], 'extra': ['test_extra']}),
            'project-b': dict(root='/private/project-b', commit='b' * 40,
                              blobs={'secret.py': '3' * 40}, validations={'core': ['test_b']})})

    def test_task_contains_only_selected_project_and_validation(self):
        binding = provision_task.workspace_binding(self.workspace, self.inputs)
        self.assertEqual({'project-a'}, set(binding['sources']))
        self.assertEqual({'core': ['test_core']}, binding['sources']['project-a']['validations'])
        self.assertEqual(self.workspace['sources']['project-a']['blobs'], binding['sources']['project-a']['blobs'])
        self.assertEqual(self.inputs, binding['inputs'])
        self.assertNotIn('/private/project-b', repr(binding))
        self.assertNotIn('test_extra', repr(binding))
        provision_task.check_workspace_binding({'workspace': binding})

    def generated_config(self):
        template = dict(plan=dict(host=dict(hostname='guest', dmi_vendor='QEMU', dmi_product='fixture'),
            mounts=dict(quota=dict(uuid='quota-id', source='/dev/fixture', path='/fixture')),
            settings=dict(identity={}, controllers=dict(target={}, supervisor={})),
            roots=[dict(role='work')]), observed=dict(parents={}, system_geometry=dict(
                schema='fixture', retained_ordinary_parent=dict(parent=dict(path='/parent'),
                memory_bytes=7, memory_swap_max=7, tasks_max=7, cpu_quota_per_sec_usec=1000000))))
        workspace = dict(self.workspace, budgets={'wall_seconds': 72}, limits={}, quotas={'work': {}})
        return dict(template=template, installation=dict(source=dict(commit='a' * 40)),
            bases={'/old': '/new'}, mounts=[], minimum_free_bytes=1, profile_ref='fixture',
            install_uuid=str(uuid.uuid4()), request_ttl_seconds=3600, first_project_id=15000,
            workspace=workspace)

    def generate(self, module, config):
        def read(path, *args, **kwargs):
            path = str(path)
            for suffix, value in (('hostname', 'guest'), ('sys_vendor', 'QEMU'),
                                  ('product_name', 'fixture'), ('cpu.max', '100000 100000')):
                if path.endswith(suffix):
                    return value
            return '7'
        info = SimpleNamespace(st_dev=7, st_ino=7, st_rdev=7)
        with patch.object(module.Path, 'read_text', read), patch.object(module.os, 'stat', return_value=info), \
             patch.object(module.os, 'statvfs', return_value=SimpleNamespace(f_bavail=10000, f_frsize=4096, f_favail=10000)), \
             patch.object(module.budget, 'current_clock', return_value={'boot_id': 'fixture-boot'}):
            return module.task_input(config, str(uuid.uuid4()), 'owner', 1, workspace_inputs=self.inputs)

    def test_actual_task_input_never_carries_other_project_into_policy_assembly(self):
        config = self.generated_config()
        before = copy.deepcopy(config)
        result = self.generate(provision_task, config)
        self.assertEqual({'project-a'}, set(result['workspace']['sources']))
        self.assertEqual({'core'}, set(result['workspace']['sources']['project-a']['validations']))
        self.assertNotIn('/private/project-b', repr(result))
        self.assertEqual(before, config)

    def test_binding_preserves_registry_and_original_request(self):
        original = copy.deepcopy((self.workspace, self.inputs))
        binding = provision_task.workspace_binding(self.workspace, self.inputs)
        binding['sources']['project-a']['blobs']['app.py'] = '0' * 40
        binding['sources']['project-a']['validations']['core'].append('other')
        binding['inputs']['content'] = 'different'
        self.assertEqual(original, (self.workspace, self.inputs))

    def test_unknown_source_file_and_validation_are_rejected(self):
        for field, value in (('source_ref', 'unknown'), ('relative_path', 'secret.py'),
                             ('validation_ref', 'unknown')):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'PROVISION_WORKSPACE_NOT_ADMITTED'):
                provision_task.workspace_binding(self.workspace, dict(self.inputs, **{field: value}))

    def test_direct_preparation_cannot_reintroduce_unrelated_projects(self):
        good = provision_task.workspace_binding(self.workspace, self.inputs)
        for altered in (dict(good, sources=copy.deepcopy(self.workspace['sources'])),
                        dict(good, unexpected='authority')):
            with self.subTest(keys=list(altered)), patch.object(provision_task, 'verify_release') as verify, \
                 patch.object(provision_task, '_helper') as helper:
                with self.assertRaisesRegex(quota_contract.QuotaError, 'PROVISION_WORKSPACE_BINDING'):
                    provision_task.prepare({'workspace': altered})
                verify.assert_not_called()
                helper.assert_not_called()

    def test_direct_preparation_cannot_reintroduce_unselected_validation(self):
        binding = provision_task.workspace_binding(self.workspace, self.inputs)
        binding['sources']['project-a']['validations']['extra'] = ['test_extra']
        with self.assertRaisesRegex(quota_contract.QuotaError, 'PROVISION_WORKSPACE_BINDING'):
            provision_task.prepare({'workspace': binding})

    def test_host_only_preparation_has_no_project_requirement(self):
        provision_task.check_workspace_binding({'plan': {'kind': 'host.inspect'}})


if __name__ == '__main__':
    unittest.main()
