"""Fixed installed A2 preparation; host/quota observations are modeled."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux resident task preparation')

from admin.local_hand_system_manager import provision_task, resident_service as admin
from local_hand_jobs import local_a2_jobs
from local_hand_jobs.contract import JobError
from test_e3_quota_q2_prepare_assembly import a, system_facts
import test_local_hand_resident as resident_fixtures


def runtime_fixture():
    return dict(source_root='/registered/ledger-source', source_commit='a'*40,
        source_blobs=dict(local_a2_jobs.SOURCE_BLOBS), runtime_root='/registered/ledger-runtime',
        runtime_python='/registered/ledger-runtime/bin/python', runtime_python_realpath='/usr/bin/python3.12',
        runtime_python_sha256='b'*64, venv_config_sha256='c'*64, console_script_sha256='d'*64,
        package_root='/registered/ledger-runtime/lib/python3.12/site-packages/infra_artifact_ledger',
        wheel='/registered/wheels/infra_artifact_ledger-0.2.0a1-py3-none-any.whl', wheel_sha256='e'*64)


class LocalA2PreparationTests(unittest.TestCase):
    def setUp(self):
        resident_fixtures.PreparationTests.setUp(self)
        self.config['local_a2'] = dict(runtimes={'ledger-a2': runtime_fixture()})
        self.args.update(kind=local_a2_jobs.KIND, inputs={'runtime_ref': 'ledger-a2'})

    def test_new_attempt_refused_before_allocating_even_when_registered(self):
        for reference in ('ledger-a2', 'unknown'):
            for retry in ({}, {'retry_failed': True}):
                with self.subTest(reference=reference, retry=retry), \
                     patch.object(self.service, '_prepare_worker') as worker:
                    with self.assertRaises(JobError) as caught:
                        self.service.call(dict(self.args, inputs={'runtime_ref': reference}, **retry))
                    self.assertEqual('UNSUPPORTED', caught.exception.code)
                    self.assertEqual({}, self.service.records)
                    self.assertEqual([], list(Path(self.config['private_root']).iterdir()))
                    worker.assert_not_called()

    def test_original_preparing_identity_is_polled_without_new_worker(self):
        record = resident_fixtures.PreparationTests.ready_record(self)
        record.pop('request')
        record.update(state='PREPARING', kind=self.args['kind'], inputs=self.args['inputs'])
        self.service._save(record)
        with patch.object(self.service, '_preparation_active', return_value=True), \
             patch.object(self.service, '_prepare_worker') as worker:
            self.assertEqual('PREPARING', self.service.call(self.args)['state'])
            with self.assertRaises(JobError) as caught:
                self.service.call(dict(self.args, inputs={'runtime_ref': 'other'}))
            self.assertEqual('CONFLICT', caught.exception.code)
            self.assertEqual(record, self.service.records[record['operation_id']])
            worker.assert_not_called()


class LocalA2AssemblyTests(unittest.TestCase):
    def test_real_policy_and_registry_resolve_selected_runtime_without_prepared_fact(self):
        value = system_facts()
        before = copy.deepcopy(value)
        job = dict(inputs={'runtime_ref': 'ledger-a2'}, runtimes={'ledger-a2': runtime_fixture()})
        result = a.assemble(value, local_a2=job)
        self.assertEqual(before, value)
        request = result['resident']['request']
        self.assertEqual(local_a2_jobs.KIND, request['kind'])
        self.assertEqual(job['inputs'], request['inputs'])
        access = result['policy']['principals'][value['identity']['principal_id']]['profiles'][request['profile_ref']]
        self.assertEqual([local_a2_jobs.KIND], access['kinds'])
        self.assertEqual(['ledger-a2'], access['runtime_refs'])
        self.assertEqual([], access['prepared_refs'])
        execution = result['resident']['plan']['execution']
        self.assertEqual(1, len(execution['stages']))
        self.assertNotIn('--storage-config', execution['stages'][0]['argv'])
        self.assertEqual({}, execution['storage'])

    def test_conflicting_job_or_extra_runtime_is_not_assembled(self):
        job = dict(inputs={'runtime_ref': 'ledger-a2'}, runtimes={'ledger-a2': runtime_fixture()})
        with self.assertRaisesRegex(ValueError, 'PREP_ASSEMBLY_JOB_CONFLICT'):
            a.assemble(system_facts(), workspace={}, local_a2=job)
        job['runtimes']['unselected'] = runtime_fixture()
        with self.assertRaisesRegex(ValueError, 'PREP_ASSEMBLY_RUNTIME_BINDING'):
            a.assemble(system_facts(), local_a2=job)

    def test_provision_input_uses_only_registered_runtime_and_server_budgets(self):
        template = dict(plan=dict(host=dict(hostname='guest', dmi_vendor='QEMU', dmi_product='fixture'),
            mounts=dict(quota=dict(uuid='quota-id', source='/dev/fixture', path='/fixture')),
            directories=dict(control=dict(path='/old/control'), state=dict(path='/old/state')),
            settings=dict(identity={}, controllers=dict(target={}, supervisor={}), original_budgets={}),
            roots=[dict(role=role) for role in ('work', 'temporary', 'evidence', 'retained_store')]),
            observed=dict(parents={}, system_geometry=dict(schema='fixture', retained_ordinary_parent=dict(
                parent=dict(path='/old'), memory_bytes=7, memory_swap_max=7, tasks_max=7,
                cpu_quota_per_sec_usec=1000000))))
        local = dict(runtimes={'ledger-a2': runtime_fixture(), 'other': runtime_fixture()},
            budgets=dict(wall_seconds=72), limits={'max_running': 1},
            quotas={role: dict(hard_bytes=1024**2) for role in ('work', 'temporary', 'evidence', 'retained_store')})
        config = dict(template=template, installation=dict(source=dict(commit='a'*40)),
            bases={'/old':'/new'}, mounts=[], minimum_free_bytes=1, profile_ref='fixture',
            install_uuid=str(uuid.uuid4()), request_ttl_seconds=3600, first_project_id=15000, local_a2=local)
        before = copy.deepcopy(config)
        def read(path, *args, **kwargs):
            return {'hostname':'guest', 'sys_vendor':'QEMU', 'product_name':'fixture',
                    'cpu.max':'100000 100000'}.get(Path(path).name, '7')
        info = SimpleNamespace(st_dev=7, st_ino=7, st_rdev=7)
        with patch.object(provision_task.Path, 'read_text', read), \
             patch.object(provision_task.os, 'stat', return_value=info), \
             patch.object(provision_task.os, 'statvfs', return_value=SimpleNamespace(f_bavail=10000, f_frsize=4096, f_favail=10000)), \
             patch.object(provision_task.budget, 'current_clock', return_value={'boot_id':'new-boot'}):
            value = provision_task.task_input(config, str(uuid.uuid4()), 'owner', 1,
                                             local_a2_inputs={'runtime_ref':'ledger-a2'})
        self.assertEqual(before, config)
        self.assertEqual({'ledger-a2'}, set(value['local_a2']['runtimes']))
        self.assertEqual(local['budgets'], value['plan']['settings']['original_budgets'])
        self.assertEqual(local['limits'], value['plan']['settings']['limits'])
        self.assertEqual(value, json.loads(json.dumps(value)))
        self.assertNotIn('workspace', value)


if __name__ == '__main__':
    unittest.main()
