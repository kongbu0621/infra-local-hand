"""Task preparation authorization, durable retry boundaries and result routing."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import Mock, patch

from local_hand_jobs.contract import JobError, Principal, TOOL_SCOPES, request_digest
from local_hand_jobs.policy import Policy
from local_hand_mcp.resident import ResidentBroker
from admin.local_hand_system_manager import resident_service as admin
from test_local_hand_jobs_policy import policy_fixture


class ResidentTests(unittest.TestCase):
    def setUp(self):
        self.policy=Policy(policy_fixture('/synthetic-resident'))
        self.owner=Principal('owner',frozenset(TOOL_SCOPES.values()))
        self.retained=Mock(policy=self.policy)
        self.service=Mock()
        self.reader=Mock()
        self.factory=Mock(return_value=self.reader)
        config=dict(profile_ref='fixture',authority_id='resident-fixture',budgets={},retained=[],catalog='/synthetic-catalog')
        self.broker=ResidentBroker(self.retained,config,self.service,self.factory)
        operation=str(uuid.uuid4())
        self.request=dict(schema_version='lh-job-v1',operation_id=operation,kind='host.inspect',profile_ref='fixture',
            expected=self.policy.expected('fixture'),inputs={},expires_at=int(time.time())+300)
        self.request['request_digest']=request_digest(self.request)
        self.record=dict(operation_id=operation,principal_id='owner',state='READY',request=self.request,policy_path='/synthetic-policy')
        self.lookup=patch.object(self.broker,'_record',return_value=self.record).start()
        patch('local_hand_mcp.resident.Policy.from_file',return_value=self.policy).start()
        self.local=patch('local_hand_mcp.resident.cli.request').start()
        self.addCleanup(patch.stopall)

    def call(self,name,args,principal=None):return self.broker.call(name,args,principal or self.owner)

    def test_preparation_needs_submit_scope_and_admitted_profile(self):
        args=dict(operation_id=self.request['operation_id'],kind='host.inspect',profile_ref='fixture')
        for selected,principal in ((args,Principal('owner',frozenset({'lh:read'}))),
                (dict(args,profile_ref='elsewhere'),self.owner)):
            with self.assertRaises(JobError):self.call('lh_job_prepare',selected,principal)
        self.service.call.assert_not_called()
        self.call('lh_job_prepare',args)
        self.service.call.assert_called_once_with('prepare',principal_id='owner',**args)
        self.local.assert_not_called()

    def test_capabilities_and_idle_status_do_not_prepare_or_submit(self):
        self.retained.policy=self.policy
        self.call('lh_capabilities',{})
        self.service.call.assert_not_called()
        self.service.call.return_value={'state':'IDLE'}
        with self.assertRaises(JobError) as caught:
            self.call('lh_job_status',{'operation_id':self.request['operation_id']})
        self.assertEqual('NOT_FOUND',caught.exception.code)
        self.assertEqual(['status'],[call.args[0] for call in self.service.call.call_args_list])
        self.local.assert_not_called()

    def test_changed_request_or_owner_cannot_launch(self):
        changed=dict(self.request,expires_at=self.request['expires_at']+1)
        changed['request_digest']=request_digest(changed)
        with self.assertRaises(JobError):self.call('lh_job_submit',changed)
        self.record['principal_id']='another-owner'
        with self.assertRaises(JobError):self.call('lh_job_submit',self.request)
        self.service.call.assert_not_called()

    def test_uncertain_submission_is_followed_by_read_of_same_task(self):
        self.service.call.side_effect=[{'state':'IDLE'},{'state':'RUNNING'},{'state':'RUNNING'}]
        self.local.side_effect=[JobError('IO_UNCERTAIN','lost response'),{'outcome':'SUCCEEDED'}]
        with self.assertRaises(JobError):self.call('lh_job_submit',self.request)
        self.assertEqual({'outcome':'SUCCEEDED'},self.call('lh_job_status',{'operation_id':self.request['operation_id']}))
        self.assertEqual(1,sum(call.args[0]=='start' for call in self.service.call.call_args_list))
        self.assertEqual('lh_job_status',self.local.call_args.args[1])

    def test_completed_or_unresolved_controller_never_launches_again(self):
        self.reader.state.get.return_value=dict(digest=self.request['request_digest'],principal='owner')
        self.reader._view.return_value={'outcome':'SUCCEEDED'}
        for state in ('EXITED','UNRESOLVED'):
            self.service.call.return_value={'state':state}
            self.assertEqual({'outcome':'SUCCEEDED'},self.call('lh_job_submit',self.request))
        self.assertTrue(all(call.args[0]=='status' for call in self.service.call.call_args_list))
        self.local.assert_not_called()
        self.factory.assert_called_once()

    def test_one_transient_read_failure_does_not_disable_future_queries(self):
        self.service.call.side_effect=[JobError('IO_UNCERTAIN','temporary'),{'state':'EXITED'}]
        args=dict(operation_id=self.request['operation_id'])
        with self.assertRaises(JobError):self.call('lh_job_status',args)
        self.call('lh_job_status',args)
        self.reader.call.assert_called_once_with('lh_job_status',args,self.owner)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);(root/'private').mkdir();(root/'public').mkdir()
        self.config=dict(private_root=str(root/'private'),catalog=str(root/'public'),profile_ref='fixture',
            first_project_id=15000,last_project_id=20000,max_tasks=32,principals=['owner'],installation={})
        patch.object(admin,'load',side_effect=lambda path:json.loads(Path(path).read_text())).start()
        patch.object(admin.budget,'current_clock',return_value={'boot_id':'boot-one'}).start()
        self.addCleanup(patch.stopall)
        self.service=admin.ResidentService(self.config)
        self.args=dict(action='prepare',operation_id=str(uuid.uuid4()),kind='host.inspect',profile_ref='fixture',principal_id='owner')

    def test_failure_is_retained_and_explicit_retry_has_same_operation(self):
        with patch.object(admin.provision_task,'task_input',side_effect=OSError('local pre-admission failure')):
            self.assertEqual('PREPARING',self.service.call(self.args)['state'])
            self.service.worker.join(3)
            self.assertEqual('FAILED',self.service.call(self.args)['state'])
            first=self.service.records[self.args['operation_id']]['attempt']
            self.assertEqual('PREPARING',self.service.call(dict(self.args,retry_failed=True))['state'])
            self.service.worker.join(3)
            self.assertEqual('FAILED',self.service.call(self.args)['state'])
            second=self.service.records[self.args['operation_id']]['attempt']
        self.assertNotEqual(first,second)
        self.assertTrue((Path(first)/'preparation-failure.json').exists())
        self.assertTrue((Path(second)/'preparation-failure.json').exists())
        self.assertEqual(1,len(self.service.records))

    def test_prepare_polls_do_not_duplicate_a_live_preparation(self):
        entered=threading.Event();release=threading.Event()
        def worker(record):entered.set();release.wait(3)
        with patch.object(self.service,'_prepare_worker',side_effect=worker):
            self.service.call(self.args);self.assertTrue(entered.wait(1))
            for _ in range(3):self.assertEqual('PREPARING',self.service.call(self.args)['state'])
            self.assertEqual(1,len(list(Path(self.config['private_root']).glob('*/attempt-*'))))
            release.set();self.service.worker.join(2)

    def test_unknown_principal_rejected_before_task_files(self):
        with self.assertRaises(JobError):self.service.call(dict(self.args,principal_id='other'))
        self.assertEqual([],list(Path(self.config['private_root']).iterdir()))

    def test_restart_preserves_failed_identity_and_failure_record(self):
        with patch.object(admin.provision_task,'task_input',side_effect=OSError('local')):
            self.service.call(self.args);self.service.worker.join(3)
        restarted=admin.ResidentService(self.config)
        self.assertEqual('FAILED',restarted.call(self.args)['state'])
        self.assertEqual(self.service.records,restarted.records)

    def test_lost_controller_handle_never_creates_another_process(self):
        operation=self.args['operation_id'];output=Path(self.temp.name)/'execution';output.mkdir()
        (output/'launch-intent.json').write_text('{}')
        record=dict(state='READY',operation_id=operation,principal_id='owner',output=str(output),
            boot_id='older-boot',request=dict(request_digest='a'*64,expires_at=int(time.time())+300))
        self.service.records[operation]=record
        with patch.object(self.service,'_launcher') as launcher:
            self.assertEqual({'state':'UNRESOLVED'},self.service.call(dict(action='start',operation_id=operation,
                principal_id='owner',request_digest='a'*64)))
        launcher.assert_not_called()

    def test_no_committed_job_and_proved_exit_allow_new_preparation(self):
        output=Path(self.temp.name)/'execution';output.mkdir()
        (output/'launch-intent.json').write_text('{}')
        (output/'finished.json').write_text(json.dumps(dict(returncode=1,streams_eof=True)))
        record=dict(output=str(output))
        with patch.object(self.service,'_unit_active',return_value=False), \
             patch.object(self.service,'_has_committed_task',return_value=False):
            self.assertTrue(self.service._replaceable(record))
        with patch.object(self.service,'_unit_active',return_value=False), \
             patch.object(self.service,'_has_committed_task',return_value=True):
            self.assertFalse(self.service._replaceable(record))
