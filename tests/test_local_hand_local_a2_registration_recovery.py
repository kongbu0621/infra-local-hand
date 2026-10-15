"""Withdrawing future runtime admission preserves original preparation queries."""
import copy
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux resident preparation')

from admin.local_hand_system_manager import resident_service as admin
from local_hand_jobs.contract import JobError, Principal, validate_tool_args
from local_hand_jobs.policy import Policy
from test_local_hand_jobs_local_a2_admission import local_a2_policy_fixture
import test_local_hand_local_a2_preparation as local_fixtures
import test_local_hand_resident as resident_fixtures


class RuntimeAdapterRegistrationTests(unittest.TestCase):
    setUp = resident_fixtures.ResidentTests.setUp
    call = resident_fixtures.ResidentTests.call

    def args(self):
        return dict(operation_id=self.request['operation_id'], kind='ledger.test.local_a2',
                    profile_ref='fixture', inputs={'runtime_ref': 'installed-a2'})

    def test_dynamic_registration_is_shared_by_admitted_submit_principals(self):
        # A retained task's grants are not the resident dynamic registry. Entry
        # scopes/revocation and the administrator's registration govern new jobs.
        self.broker.policy = Policy(local_a2_policy_fixture('/synthetic-resident'))
        other = Principal('other', self.owner.scopes)
        self.assertNotIn('ledger.test.local_a2',
                         self.broker.policy.capabilities(other)['profiles'][0]['allowed_kinds'])
        self.broker.config['local_a2'] = dict(runtime_refs=['installed-a2'], budgets={})
        self.broker._record.return_value = None
        self.retained.state.get.return_value = None
        self.assertEqual(['installed-a2'], self.call('lh_capabilities', {}, other)['profiles'][0]['runtime_refs'])
        self.call('lh_job_prepare', self.args(), other)
        self.service.call.assert_called_once_with('prepare', principal_id='other', **self.args())
        for denied in (Principal('other', frozenset({'lh:read'})), Principal('unknown', self.owner.scopes)):
            with self.assertRaises(JobError): self.call('lh_job_prepare', self.args(), denied)

    def test_withdrawn_registration_only_routes_existing_identity_as_query(self):
        self.record['request'].update(kind=self.args()['kind'], inputs=self.args()['inputs'])
        self.service.call.return_value = dict(state='READY', request=self.record['request'])
        self.assertEqual(self.record['request'], self.call('lh_job_prepare', self.args())['request'])
        self.service.call.assert_called_once_with('prepare', principal_id='owner', **self.args(), allow_new=False)
        self.service.call.reset_mock()
        self.broker._record.return_value = None
        with self.assertRaises(JobError): self.call('lh_job_prepare', self.args())
        self.service.call.assert_not_called()

    def test_internal_query_flag_is_not_public_caller_authority(self):
        with self.assertRaises(JobError):
            validate_tool_args('lh_job_prepare', dict(self.args(), allow_new=True))


class RuntimePreparationRecoveryTests(unittest.TestCase):
    setUp = local_fixtures.LocalA2PreparationTests.setUp

    def ready(self):
        record = resident_fixtures.PreparationTests.ready_record(self)
        record['request'].update(kind=self.args['kind'], inputs=self.args['inputs'])
        record.update(kind=self.args['kind'], inputs=self.args['inputs'])
        self.service._save(record)
        return record

    def test_removed_registration_preserves_original_ready_request_even_after_restart_or_expiry(self):
        record = self.ready()
        original = copy.deepcopy(record['request'])
        record['boot_id'] = 'old-boot'
        self.service._save(record)
        self.config['local_a2']['runtimes'].clear()
        with patch.object(self.service, '_prepare_worker') as worker, \
             patch.object(self.service, '_replaceable') as replace:
            returned = self.service.call(dict(self.args, retry_failed=True))
        self.assertEqual(dict(operation_id=record['operation_id'], state='READY', request=original), returned)
        self.assertEqual(record, self.service.records[record['operation_id']])
        worker.assert_not_called(); replace.assert_not_called()

    def test_adapter_withdrawal_prevents_automatic_stale_repreparation_while_manager_still_registered(self):
        record = self.ready()
        record['request']['expires_at'] = int(time.time()) - 1
        self.service._save(record)
        with patch.object(self.service, '_prepare_worker') as worker, \
             patch.object(self.service, '_replaceable') as replace:
            returned = self.service.call(dict(self.args, allow_new=False))
        self.assertEqual(record['request'], returned['request'])
        worker.assert_not_called(); replace.assert_not_called()

    def test_restarted_preparation_recovers_its_original_result_after_registration_removed(self):
        record = self.ready()
        attempt = Path(record['attempt']); attempt.mkdir()
        (attempt / 'result.json').write_text('{}')
        preparing = dict(record, state='PREPARING')
        self.service._save(preparing)
        self.config['local_a2']['runtimes'].clear()
        with patch.object(self.service, '_preparation_active', return_value=False), \
             patch.object(self.service, '_ready', return_value=record) as recover, \
             patch.object(self.service, '_prepare_worker') as worker:
            returned = self.service.call(self.args)
        self.assertEqual(record['request'], returned['request'])
        recover.assert_called_once_with(preparing); worker.assert_not_called()

    def test_failed_attempt_is_queryable_but_cannot_restart_without_registration(self):
        record = self.ready()
        record.update(state='FAILED'); record.pop('request')
        self.service._save(record)
        self.config['local_a2']['runtimes'].clear()
        with patch.object(self.service, '_prepare_worker') as worker:
            returned = self.service.call(dict(self.args, retry_failed=True))
        self.assertEqual(dict(operation_id=record['operation_id'], state='FAILED', retryable=False), returned)
        self.assertEqual(record, self.service.records[record['operation_id']]); worker.assert_not_called()

    def test_manager_rejects_runtime_overlap_before_private_attempt_or_catalog_write(self):
        runtime = self.config['local_a2']['runtimes']['ledger-a2']
        root = self.config['private_root']
        runtime.update(runtime_root=root, runtime_python=root + '/bin/python',
                       package_root=root + '/lib/python3.12/site-packages/infra_artifact_ledger')
        with patch.object(admin.Path, 'mkdir') as mkdir, patch.object(admin, 'publish') as publish, \
             patch.object(self.service, '_prepare_worker') as worker:
            with self.assertRaisesRegex(ValueError, 'PROVISION_LOCAL_A2_INPUT_OVERLAP'):
                self.service.call(self.args)
        self.assertEqual({}, self.service.records)
        mkdir.assert_not_called(); publish.assert_not_called(); worker.assert_not_called()

    def test_startup_rejects_catalog_overlap_before_republication(self):
        self.config['local_a2']['runtimes']['ledger-a2']['source_root'] = self.config['catalog']
        with patch.object(admin.Path, 'glob') as glob, patch.object(admin, 'publish') as publish:
            with self.assertRaisesRegex(ValueError, 'PROVISION_LOCAL_A2_INPUT_OVERLAP'):
                admin.ResidentService(self.config)
        glob.assert_not_called(); publish.assert_not_called()

    def test_service_rejects_socket_overlap_before_lock_or_socket_writes(self):
        runtime = self.config['local_a2']['runtimes']['ledger-a2']
        self.config['socket'] = runtime['runtime_root'] + '/service.sock'
        with patch.object(admin.os, 'getuid', return_value=0), \
             patch.object(admin.os, 'geteuid', return_value=0), \
             patch.object(admin.os, 'open') as opened:
            with self.assertRaisesRegex(ValueError, 'PROVISION_LOCAL_A2_INPUT_OVERLAP'):
                admin.serve(self.config)
        opened.assert_not_called()

    def test_query_retains_owner_kind_and_input_checks(self):
        self.ready(); self.config['local_a2']['runtimes'].clear()
        self.config['principals'].append('other')
        for change, expected in (({'principal_id': 'other'}, 'UNAUTHORIZED'),
                                 ({'inputs': {'runtime_ref': 'foreign'}}, 'CONFLICT'),
                                 ({'kind': 'host.inspect', 'inputs': {}}, 'CONFLICT')):
            request = dict(self.args, allow_new=False, **change)
            if request['kind'] == 'host.inspect': request.pop('inputs')
            with self.subTest(change=change), self.assertRaises(JobError) as caught:
                self.service.call(request)
            self.assertEqual(expected, caught.exception.code)
        for flag in ('false', 0, None):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.service.call(dict(self.args, allow_new=flag))


if __name__ == '__main__':
    unittest.main()
