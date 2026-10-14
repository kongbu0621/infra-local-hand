"""Task preparation authorization, durable retry boundaries and result routing."""
import copy
import hashlib
import json
import socket
import sqlite3
import sys
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux resident task service')

from local_hand_jobs.contract import JobError, Principal, TOOL_SCOPES, request_digest
from local_hand_jobs.policy import Policy
from local_hand_jobs.cli import request as socket_request
from local_hand_jobs import cli
from local_hand_mcp.resident import ResidentBroker
from admin.local_hand_system_manager import resident_service as admin
from admin.local_hand_system_manager import provision_task
from test_local_hand_jobs_policy import policy_fixture


class ResidentTests(unittest.TestCase):
    def setUp(self):
        self.policy=Policy(policy_fixture('/synthetic-resident'))
        self.owner=Principal('owner',frozenset(TOOL_SCOPES.values()))
        self.retained=Mock(policy=self.policy)
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE revocations(principal TEXT)')
        self.addCleanup(db.close);self.retained.state.transaction.return_value=db
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

    def test_workspace_read_requires_read_authority_and_never_launches(self):
        self.broker.config['workspace']=dict(source_refs=['project'],validation_refs=['core'],budgets={})
        args=dict(profile_ref='fixture',source_ref='project',relative_path='sample.py')
        with self.assertRaises(JobError):
            self.call('lh_workspace_read',args,Principal('owner',frozenset({'lh:submit'})))
        self.service.call.assert_not_called()
        self.call('lh_workspace_read',args,Principal('owner',frozenset({'lh:read'})))
        self.service.call.assert_called_once_with('workspace_read',principal_id='owner',**args)
        self.local.assert_not_called();self.factory.assert_not_called()

    def test_preparation_needs_submit_scope_and_admitted_profile(self):
        args=dict(operation_id=self.request['operation_id'],kind='host.inspect',profile_ref='fixture')
        for selected,principal in ((args,Principal('owner',frozenset({'lh:read'}))),
                (dict(args,profile_ref='elsewhere'),self.owner)):
            with self.assertRaises(JobError):self.call('lh_job_prepare',selected,principal)
        self.service.call.assert_not_called()
        self.call('lh_job_prepare',args)
        self.service.call.assert_called_once_with('prepare',principal_id='owner',**args)
        self.local.assert_not_called()

    def test_preparation_cannot_shadow_a_retained_task_with_the_same_uuid(self):
        self.lookup.return_value=None
        self.retained.state.get.return_value={'id':self.request['operation_id'],'principal':'owner'}
        self.broker.config['retained']=['/unrelated-policy']
        args=dict(operation_id=self.request['operation_id'],kind='host.inspect',profile_ref='fixture')
        with self.assertRaises(JobError) as caught:self.call('lh_job_prepare',args)
        self.assertEqual('CONFLICT',caught.exception.code)
        self.retained.state.get.assert_called_once_with('job',self.request['operation_id'])
        self.service.call.assert_not_called();self.factory.assert_not_called()

    def test_new_uuid_checks_older_deployments_and_prepares_only_when_absent(self):
        self.lookup.return_value=None
        self.retained.state.get.return_value=None
        self.broker.config['retained']=['/older-policy']
        self.reader.state.get.return_value={'id':self.request['operation_id'],'principal':'other'}
        args=dict(operation_id=self.request['operation_id'],kind='host.inspect',profile_ref='fixture')
        with self.assertRaises(JobError) as caught:self.call('lh_job_prepare',args)
        self.assertEqual('CONFLICT',caught.exception.code)
        self.service.call.assert_not_called()
        self.reader.state.get.return_value=None
        self.call('lh_job_prepare',args)
        self.service.call.assert_called_once_with('prepare',principal_id='owner',**args)

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

    def test_read_crossing_controller_exit_uses_same_retained_task(self):
        artifact=str(uuid.uuid4())+'.seal'
        self.broker.artifact_routes[('owner',artifact)]=(self.request['operation_id'],self.record['policy_path'])
        cases=(('lh_job_status',dict(operation_id=self.request['operation_id']),{'outcome':'SUCCEEDED'}),
               ('lh_evidence_manifest',dict(operation_id=self.request['operation_id']),{'artifacts':[{'artifact_id':artifact}]}),
               ('lh_evidence_read_chunk',dict(artifact_id=artifact,expected_sha256='a'*64,offset=0),{'artifact_id':artifact}))
        with tempfile.TemporaryDirectory() as root:
            policy=Policy(policy_fixture(root))
            path=Path(policy.broker_root)/'maintenance.sock';path.parent.mkdir()
            for name,args,result in cases:
                for state in ('EXITED','UNRESOLVED'):
                    with self.subTest(tool=name,state=state):
                        # The status observation precedes a real listener closing.
                        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
                            listener.bind(str(path));listener.listen(1)
                        self.service.call.reset_mock()
                        self.service.call.side_effect=[{'state':'RUNNING'},{'state':state}]
                        self.local.reset_mock();self.local.side_effect=socket_request
                        self.reader.call.reset_mock();self.reader.call.return_value=result
                        try:
                            with patch('local_hand_mcp.resident.Policy.from_file',return_value=policy):
                                self.assertEqual(result,self.call(name,args))
                            self.local.assert_called_once_with(path,name,args,timeout=3)
                            self.reader.call.assert_called_once_with(name,args,self.owner)
                            self.assertEqual(['status','status'],[c.args[0] for c in self.service.call.call_args_list])
                        finally:
                            path.unlink()

    def test_read_handoff_is_bounded_and_preserves_refusals(self):
        args=dict(operation_id=self.request['operation_id'])
        for state in ('RUNNING','IDLE','UNRECOGNIZED'):
            with self.subTest(state=state):
                failure=JobError('IO_UNCERTAIN','original read failure')
                self.service.call.reset_mock();self.local.reset_mock()
                self.service.call.side_effect=[{'state':'RUNNING'},{'state':state}]
                self.local.side_effect=failure
                with self.assertRaises(JobError) as caught:self.call('lh_job_status',args)
                self.assertIs(failure,caught.exception)
                self.assertEqual(2,self.service.call.call_count);self.local.assert_called_once()
        for code in ('UNAUTHORIZED','CONFLICT','NOT_SEALED'):
            with self.subTest(code=code):
                self.service.call.reset_mock();self.local.reset_mock()
                self.service.call.side_effect=None;self.service.call.return_value={'state':'RUNNING'}
                failure=JobError(code,'original refusal');self.local.side_effect=failure
                with self.assertRaises(JobError) as caught:self.call('lh_job_status',args)
                self.assertIs(failure,caught.exception)
                self.service.call.assert_called_once();self.local.assert_called_once()
        self.factory.assert_not_called()

    def test_uncertain_writes_never_use_read_handoff(self):
        for name,args in (('lh_job_submit',self.request),('lh_job_cancel',self.cancel_args())):
            with self.subTest(tool=name):
                self.service.call.reset_mock();self.local.reset_mock()
                self.service.call.side_effect=[{'state':'RUNNING'},{'state':'EXITED'}]
                failure=JobError('IO_UNCERTAIN','response lost');self.local.side_effect=failure
                with self.assertRaises(JobError) as caught:self.call(name,args)
                self.assertIs(failure,caught.exception)
                self.service.call.assert_called_once();self.local.assert_called_once()
        self.factory.assert_not_called()

    def test_read_response_lost_after_dispatch_uses_retained_result_once(self):
        args=dict(operation_id=self.request['operation_id']);received=[];failures=[]
        with tempfile.TemporaryDirectory() as root:
            policy=Policy(policy_fixture(root))
            path=Path(policy.broker_root)/'maintenance.sock';path.parent.mkdir()
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
                listener.bind(str(path));listener.listen(1);listener.settimeout(3)
                def original_controller():
                    try:
                        connection,_=listener.accept()
                        with connection:
                            received.append(json.loads(cli._read_frame(connection,cli.MAX_REQUEST_BYTES,
                                                                       deadline=time.monotonic()+3)))
                            # The read was accepted but no response survived exit.
                    except BaseException as error:
                        failures.append(error)
                worker=threading.Thread(target=original_controller);worker.start()
                self.service.call.side_effect=[{'state':'RUNNING'},{'state':'EXITED'}]
                self.local.side_effect=socket_request
                self.reader.call.return_value={'outcome':'SUCCEEDED','event_seq':58}
                try:
                    with patch('local_hand_mcp.resident.Policy.from_file',return_value=policy):
                        self.assertEqual(self.reader.call.return_value,self.call('lh_job_status',args))
                finally:
                    worker.join(4)
                self.assertFalse(worker.is_alive());self.assertEqual([],failures)
                self.assertEqual([{'tool':'lh_job_status','arguments':args}],received)
                self.local.assert_called_once()
                self.reader.call.assert_called_once_with('lh_job_status',args,self.owner)

    def test_handoff_status_failure_or_reader_refusal_is_not_hidden(self):
        args=dict(operation_id=self.request['operation_id'])
        self.local.side_effect=JobError('IO_UNCERTAIN','controller closed')
        for code in ('IO_UNCERTAIN','UNAUTHORIZED'):
            with self.subTest(status_error=code):
                failure=JobError(code,'status failed')
                self.service.call.side_effect=[{'state':'RUNNING'},failure]
                with self.assertRaises(JobError) as caught:self.call('lh_job_status',args)
                self.assertIs(failure,caught.exception)
                self.factory.assert_not_called()
        for code in ('UNAUTHORIZED','CONFLICT','IO_UNCERTAIN'):
            with self.subTest(reader_error=code):
                self.service.call.side_effect=[{'state':'RUNNING'},{'state':'EXITED'}]
                failure=JobError(code,'retained read refused');self.reader.call.side_effect=failure
                with self.assertRaises(JobError) as caught:self.call('lh_job_status',args)
                self.assertIs(failure,caught.exception)

    def cancel_args(self):
        return dict(operation_id=self.request['operation_id'],
                    expected_request_digest=self.request['request_digest'],target={'kind':'job'})

    def test_running_cancel_routes_original_identity_and_never_starts_a_controller(self):
        args=self.cancel_args()
        self.service.call.return_value={'state':'RUNNING'}
        self.local.return_value={'cancel_requested':True,'lifecycle':'RUNNING'}
        self.assertEqual(self.local.return_value,self.call('lh_job_cancel',args))
        self.local.assert_called_once_with(Path(self.policy.broker_root)/'maintenance.sock',
                                           'lh_job_cancel',args,timeout=3)
        self.assertEqual(['status'],[item.args[0] for item in self.service.call.call_args_list])
        self.factory.assert_not_called()

    def test_cancel_requires_entry_and_task_grants_and_owner_before_delivery(self):
        args=self.cancel_args()
        for principal in (Principal('owner',frozenset({'lh:read'})),Principal('other',self.owner.scopes)):
            with self.assertRaises(JobError) as caught:self.call('lh_job_cancel',args,principal)
            self.assertEqual('UNAUTHORIZED',caught.exception.code)
        config=policy_fixture('/synthetic-resident')
        config['principals']['owner']['scopes'].remove('lh:cancel')
        with patch('local_hand_mcp.resident.Policy.from_file',return_value=Policy(config)):
            with self.assertRaises(JobError) as caught:self.call('lh_job_cancel',args)
        self.assertEqual('UNAUTHORIZED',caught.exception.code)
        self.service.call.assert_not_called();self.local.assert_not_called()

    def test_cancel_before_submission_or_during_preparation_does_not_launch(self):
        args=self.cancel_args();self.service.call.return_value={'state':'IDLE'}
        with self.assertRaises(JobError) as caught:self.call('lh_job_cancel',args)
        self.assertEqual('NOT_FOUND',caught.exception.code)
        self.record['state']='PREPARING'
        with self.assertRaises(JobError) as caught:self.call('lh_job_cancel',args)
        self.assertEqual('RESOURCE_BUSY',caught.exception.code)
        self.assertEqual(['status'],[item.args[0] for item in self.service.call.call_args_list])
        self.local.assert_not_called();self.factory.assert_not_called()

    def test_cancel_response_loss_never_redelivers_or_restarts_and_status_remains_usable(self):
        args=self.cancel_args();self.service.call.return_value={'state':'RUNNING'}
        self.local.side_effect=[JobError('IO_UNCERTAIN','lost cancellation receipt'),{'cancel_requested':True}]
        with self.assertRaises(JobError):self.call('lh_job_cancel',args)
        self.assertEqual({'cancel_requested':True},self.call('lh_job_status',{'operation_id':args['operation_id']}))
        self.assertEqual(['lh_job_cancel','lh_job_status'],[item.args[1] for item in self.local.call_args_list])
        self.assertTrue(all(item.args[0]=='status' for item in self.service.call.call_args_list))

    def test_exited_or_unresolved_cancel_uses_only_retained_terminal_check(self):
        args=self.cancel_args();self.reader.cancel.return_value={'lifecycle':'TERMINAL','outcome':'CANCELLED'}
        for state in ('EXITED','UNRESOLVED'):
            self.service.call.return_value={'state':state}
            self.assertEqual(self.reader.cancel.return_value,self.call('lh_job_cancel',args))
        self.reader.cancel.assert_called_with(principal=self.owner,**args)
        self.reader.call.assert_not_called();self.local.assert_not_called()
        self.assertTrue(all(item.args[0]=='status' for item in self.service.call.call_args_list))

    def test_historical_cancel_falls_through_only_on_missing_original_task(self):
        args=self.cancel_args();self.lookup.return_value=None
        self.broker.config['retained']=['/older-policy']
        self.retained.cancel.side_effect=JobError('NOT_FOUND','not here')
        self.reader.cancel.return_value={'lifecycle':'TERMINAL','outcome':'SUCCEEDED'}
        self.assertEqual(self.reader.cancel.return_value,self.call('lh_job_cancel',args))
        self.reader.cancel.assert_called_once_with(principal=self.owner,**args)
        self.service.call.assert_not_called();self.local.assert_not_called()

    def test_retained_result_does_not_open_an_unrelated_broken_reader(self):
        self.lookup.return_value=None
        self.broker.config['retained']=['/unrelated-policy']
        self.factory.side_effect=OSError('unrelated retained configuration unavailable')
        self.retained.call.return_value={'operation_id':self.request['operation_id'],'outcome':'SUCCEEDED'}
        result=self.call('lh_job_status',{'operation_id':self.request['operation_id']})
        self.assertEqual('SUCCEEDED',result['outcome'])
        self.factory.assert_not_called()

    def test_close_attempts_all_readers_after_one_cleanup_fails(self):
        second=Mock()
        self.broker.readers={'first':self.reader,'second':second}
        with patch('local_hand_mcp.resident.cli.close_service',side_effect=[OSError('close failed'),None]) as close:
            with self.assertRaises(OSError):self.broker.close()
        self.assertEqual([self.reader,second],[call.args[0] for call in close.call_args_list])
        self.retained.close.assert_called_once()

    def test_history_falls_through_only_on_not_found(self):
        self.lookup.return_value=None
        self.broker.config['retained']=['/next-policy']
        args=dict(operation_id=self.request['operation_id'])
        self.retained.call.side_effect=JobError('UNAUTHORIZED','owner mismatch')
        with self.assertRaises(JobError):self.call('lh_job_status',args)
        self.factory.assert_not_called()
        self.retained.call.side_effect=JobError('NOT_FOUND','not retained here')
        self.reader.call.return_value={'outcome':'SUCCEEDED'}
        self.assertEqual({'outcome':'SUCCEEDED'},self.call('lh_job_status',args))
        self.factory.assert_called_once_with('/next-policy')

    def test_manifest_routes_its_artifact_without_opening_unrelated_history(self):
        artifact=str(uuid.uuid4())+'.zip'
        args=dict(artifact_id=artifact,expected_sha256='a'*64,offset=0)
        self.service.call.return_value={'state':'EXITED'}
        self.reader.call.side_effect=[{'artifacts':[{'artifact_id':artifact}]},{'artifact_id':artifact}]
        self.call('lh_evidence_manifest',{'operation_id':self.request['operation_id']})
        self.retained.call.side_effect=OSError('unrelated historical evidence unavailable')
        self.assertEqual({'artifact_id':artifact},self.call('lh_evidence_read_chunk',args))
        self.retained.call.assert_not_called()
        self.reader.call.assert_called_with('lh_evidence_read_chunk',args,self.owner)

    def test_artifact_hint_never_bypasses_an_unavailable_admission_ledger(self):
        artifact=str(uuid.uuid4())+'.zip'
        self.service.call.return_value={'state':'EXITED'}
        self.reader.call.return_value={'artifacts':[{'artifact_id':artifact}]}
        self.call('lh_evidence_manifest',{'operation_id':self.request['operation_id']})
        self.reader.call.reset_mock();self.service.call.reset_mock()
        self.retained.state.transaction.side_effect=JobError('IO_UNCERTAIN','admission ledger unavailable')
        with self.assertRaises(JobError) as caught:
            self.call('lh_evidence_read_chunk',dict(artifact_id=artifact,expected_sha256='a'*64,offset=0))
        self.assertEqual('IO_UNCERTAIN',caught.exception.code)
        self.reader.call.assert_not_called();self.service.call.assert_not_called()

    def test_manifest_hint_rechecks_owner_binding_and_task_policy(self):
        artifact=str(uuid.uuid4())+'.zip'
        args=dict(artifact_id=artifact,expected_sha256='a'*64,offset=0)
        self.service.call.return_value={'state':'EXITED'}
        self.reader.call.return_value={'artifacts':[{'artifact_id':artifact}]}
        self.call('lh_evidence_manifest',{'operation_id':self.request['operation_id']})
        self.reader.call.reset_mock();self.service.call.reset_mock()
        for change,code in (({'principal_id':'other'},'UNAUTHORIZED'),
                            ({'policy_path':'/replacement-policy'},'CONFLICT'),
                            ({'state':'PREPARING'},'RESOURCE_BUSY')):
            self.lookup.return_value=dict(self.record,**change)
            with self.assertRaises(JobError) as caught:self.call('lh_evidence_read_chunk',args)
            self.assertEqual(code,caught.exception.code)
        self.lookup.return_value=self.record
        config=policy_fixture('/synthetic-resident')
        config['principals']['owner']['scopes'].remove('lh:evidence')
        with patch('local_hand_mcp.resident.Policy.from_file',return_value=Policy(config)):
            with self.assertRaises(JobError) as caught:self.call('lh_evidence_read_chunk',args)
        self.assertEqual('UNAUTHORIZED',caught.exception.code)
        self.reader.call.assert_not_called();self.service.call.assert_not_called()

    def test_manifest_hint_is_principal_bound_and_survives_a_temporary_read_error(self):
        artifact=str(uuid.uuid4())+'.zip'
        args=dict(artifact_id=artifact,expected_sha256='a'*64,offset=0)
        self.service.call.return_value={'state':'EXITED'}
        self.reader.call.return_value={'artifacts':[{'artifact_id':artifact}]}
        self.call('lh_evidence_manifest',{'operation_id':self.request['operation_id']})
        self.service.call.reset_mock();self.reader.call.reset_mock()
        self.retained.call.side_effect=JobError('UNAUTHORIZED','foreign artifact')
        with self.assertRaises(JobError):
            self.call('lh_evidence_read_chunk',args,Principal('other',self.owner.scopes))
        self.reader.call.assert_not_called();self.service.call.assert_not_called()
        self.service.call.side_effect=[JobError('IO_UNCERTAIN','temporary status failure'),{'state':'EXITED'}]
        with self.assertRaises(JobError):self.call('lh_evidence_read_chunk',args)
        self.reader.call.return_value={'artifact_id':artifact}
        self.assertEqual({'artifact_id':artifact},self.call('lh_evidence_read_chunk',args))
        self.assertEqual(['status','status'],[item.args[0] for item in self.service.call.call_args_list])

    def test_manifest_pages_keep_bounded_routes_and_evicted_artifacts_use_normal_lookup(self):
        artifacts=[{'artifact_id':str(uuid.uuid4())+'.zip'} for _ in range(300)]
        self.service.call.return_value={'state':'EXITED'}
        for start in range(0,len(artifacts),100):
            self.reader.call.return_value={'artifacts':artifacts[start:start+100]}
            self.call('lh_evidence_manifest',{'operation_id':self.request['operation_id']})
        self.assertLessEqual(len(self.broker.artifact_routes),256)
        args=dict(artifact_id=artifacts[0]['artifact_id'],expected_sha256='a'*64,offset=0)
        self.retained.call.return_value={'artifact_id':args['artifact_id']}
        self.assertEqual({'artifact_id':args['artifact_id']},self.call('lh_evidence_read_chunk',args))
        self.retained.call.assert_called_once_with('lh_evidence_read_chunk',args,self.owner)


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

    def test_failed_waiter_cannot_release_a_still_active_preparation(self):
        operation=self.args['operation_id'];root=Path(self.config['private_root'])/operation
        attempt=root/'attempt-1';attempt.mkdir(parents=True)
        (attempt/'preparation-delivery.json').write_text('{}')
        original=json.dumps({'returncode':-9})
        (attempt/'preparation-exit.json').write_text(original)
        record=dict(state='FAILED',operation_id=operation,principal_id='owner',attempt=str(attempt),
            boot_id='boot-one',serial=1,prepare_unit='original.service')
        self.service._save(record)
        other=dict(self.args,operation_id=str(uuid.uuid4()))
        with patch.object(self.service,'_preparation_active',return_value=True) as active, \
             patch.object(self.service,'_prepare_worker') as worker:
            for args in (dict(self.args,retry_failed=True),other):
                with self.assertRaises(JobError) as caught:self.service.call(args)
                self.assertEqual('RESOURCE_BUSY',caught.exception.code)
            worker.assert_not_called()
            active.return_value=False
            self.assertEqual('PREPARING',self.service.call(dict(self.args,retry_failed=True))['state'])
            self.service.worker.join(2)
        self.assertEqual(original,(attempt/'preparation-exit.json').read_text())
        self.assertEqual(operation,worker.call_args.args[0]['operation_id'])

    def test_failed_preparation_waiter_also_blocks_business_start_until_unit_exits(self):
        record=self.ready_record();self.service._save(record)
        attempt=Path(self.temp.name)/'failed-attempt';attempt.mkdir()
        (attempt/'preparation-delivery.json').write_text('{}')
        (attempt/'preparation-exit.json').write_text('{"returncode":1}')
        self.service.records[str(uuid.uuid4())]=dict(state='FAILED',attempt=str(attempt))
        args=dict(action='start',operation_id=record['operation_id'],principal_id='owner',request_digest='a'*64)
        with patch.object(self.service,'execution_state',return_value='IDLE'), \
             patch.object(self.service,'_preparation_active',return_value=True) as active, \
             patch.object(self.service,'_launcher') as launcher:
            with self.assertRaises(JobError) as caught:self.service.call(args)
            self.assertEqual('RESOURCE_BUSY',caught.exception.code)
            launcher.assert_not_called()
            active.return_value=False
            launcher.return_value.start.return_value='RUNNING'
            self.assertEqual({'state':'RUNNING'},self.service.call(args))
            launcher.return_value.start.assert_called_once()

    def test_temporary_preparation_observation_failure_does_not_permanently_block_retry(self):
        attempt=Path(self.temp.name)/'failed-attempt';attempt.mkdir()
        (attempt/'preparation-delivery.json').write_text('{}')
        (attempt/'preparation-exit.json').write_text('{"returncode":1}')
        self.service.records[str(uuid.uuid4())]=dict(state='FAILED',attempt=str(attempt))
        with patch.object(self.service,'_preparation_active',
                side_effect=[JobError('IO_UNCERTAIN','temporary manager failure'),False]), \
             patch.object(self.service,'_prepare_worker') as worker:
            with self.assertRaises(JobError) as caught:self.service.call(self.args)
            self.assertEqual('IO_UNCERTAIN',caught.exception.code)
            worker.assert_not_called()
            self.assertFalse((Path(self.config['private_root'])/self.args['operation_id']).exists())
            self.assertEqual('PREPARING',self.service.call(self.args)['state'])
            self.service.worker.join(2)
            worker.assert_called_once()

    def test_unknown_principal_rejected_before_task_files(self):
        with self.assertRaises(JobError):self.service.call(dict(self.args,principal_id='other'))
        self.assertEqual([],list(Path(self.config['private_root']).iterdir()))

    def test_failed_execution_waiter_blocks_new_work_until_controller_exit_is_observed(self):
        original=self.ready_record();output=Path(original['output']);output.mkdir(parents=True)
        proof=json.dumps(dict(returncode=-9,streams_eof=True))
        (output/'finished.json').write_text(proof)
        self.service._save(original)
        self.args['operation_id']=str(uuid.uuid4())
        candidate=self.ready_record();self.service._save(candidate)
        start=dict(action='start',operation_id=candidate['operation_id'],principal_id='owner',request_digest='a'*64)
        prepare=dict(self.args,operation_id=str(uuid.uuid4()))
        with patch.object(self.service,'_unit_active',return_value=True) as active, \
             patch.object(self.service,'_launcher') as launcher, \
             patch.object(self.service,'_prepare_worker') as worker:
            launcher.return_value.state.return_value='IDLE'
            launcher.return_value.start.return_value='RUNNING'
            for request in (prepare,start):
                with self.assertRaises(JobError) as caught:self.service.call(request)
                self.assertEqual('RESOURCE_BUSY',caught.exception.code)
            active.side_effect=JobError('IO_UNCERTAIN','temporary controller observation failure')
            with self.assertRaises(JobError) as caught:self.service.call(prepare)
            self.assertEqual('IO_UNCERTAIN',caught.exception.code)
            worker.assert_not_called();launcher.return_value.start.assert_not_called()
            self.assertFalse((Path(self.config['private_root'])/prepare['operation_id']).exists())
            active.side_effect=None;active.return_value=False
            self.assertEqual({'state':'RUNNING'},self.service.call(start))
            launcher.return_value.start.assert_called_once()
        self.assertEqual(proof,(output/'finished.json').read_text())

    def test_newly_captured_failed_waiter_also_observes_original_controller(self):
        record=self.ready_record();output=Path(record['output']);output.mkdir(parents=True)
        def finish():
            (output/'finished.json').write_text(json.dumps(dict(returncode=1,streams_eof=True)))
            return 'EXITED'
        with patch.object(self.service,'_launcher') as launcher, \
             patch.object(self.service,'_unit_active',return_value=True) as active:
            launcher.return_value.state.side_effect=finish
            self.assertEqual('RUNNING',self.service.execution_state(record))
            active.assert_called_once_with(record)

    def test_immediate_failed_start_does_not_hide_a_live_controller(self):
        record=self.ready_record();output=Path(record['output']);output.mkdir(parents=True)
        self.service._save(record)
        def finish():
            (output/'finished.json').write_text(json.dumps(dict(returncode=1,streams_eof=True)))
            return 'EXITED'
        with patch.object(self.service,'_launcher') as launcher, \
             patch.object(self.service,'_unit_active',return_value=True) as active:
            launcher.return_value.state.return_value='IDLE'
            launcher.return_value.start.side_effect=finish
            self.assertEqual({'state':'RUNNING'},self.service.call(dict(action='start',
                operation_id=record['operation_id'],principal_id='owner',request_digest='a'*64)))
            launcher.return_value.start.assert_called_once()
            active.assert_called_once_with(record)

    def test_successful_waiter_and_previous_boot_do_not_need_a_live_unit(self):
        record=self.ready_record();output=Path(record['output']);output.mkdir(parents=True)
        with patch.object(self.service,'_unit_active',side_effect=AssertionError('unnecessary unit lookup')):
            for code,boot in ((0,'boot-one'),(-9,'previous-boot')):
                with self.subTest(code=code,boot=boot):
                    (output/'finished.json').write_text(json.dumps(dict(returncode=code,streams_eof=True)))
                    self.assertEqual('EXITED',self.service.execution_state(dict(record,boot_id=boot)))

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

    def ready_record(self):
        operation=self.args['operation_id']
        root=Path(self.config['private_root'])/operation;root.mkdir()
        return dict(state='READY',operation_id=operation,principal_id='owner',
            attempt=str(root/'attempt-1'),boot_id='boot-one',policy_path='/synthetic-policy',
            output=str(root/'attempt-1'/'execution'),
            request=dict(operation_id=operation,kind='host.inspect',inputs={},request_digest='a'*64,expires_at=int(time.time())+300))

    def test_workspace_read_checks_inventory_and_size_without_task_creation(self):
        raw=b'VALUE = 1\n'
        self.config['workspace']=dict(sources={'project':dict(root='/protected-source',commit='c'*40,
            blobs={'sample.py':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})})
        args=dict(action='workspace_read',principal_id='owner',profile_ref='fixture',source_ref='project',relative_path='sample.py')
        with patch.object(admin,'read_protected',return_value=raw) as read:
            value=self.service.call(args)
            self.assertEqual(raw.decode(),value['content']);self.assertEqual(hashlib.sha256(raw).hexdigest(),value['sha256'])
            read.assert_called_once_with('/protected-source/sample.py',4096)
            read.return_value=b'changed'
            with self.assertRaises(JobError) as caught:self.service.call(args)
            self.assertEqual('CONFLICT',caught.exception.code)
            read.side_effect=ValueError('INPUT_BYTE_LIMIT')
            with self.assertRaises(JobError) as caught:self.service.call(args)
            self.assertEqual('LIMIT_EXCEEDED',caught.exception.code)
            read.reset_mock()
            with self.assertRaises(JobError):self.service.call(dict(args,source_ref='foreign'))
            read.assert_not_called()
        self.assertFalse(self.service.records);self.assertIsNone(self.service.worker)
        self.assertEqual([],list(Path(self.config['private_root']).iterdir()))

    def test_workspace_preparation_binds_inputs_before_worker_and_rejects_changed_poll(self):
        inputs=dict(source_ref='project',relative_path='sample.py',expected_sha256='a'*64,content='VALUE=2\n',validation_ref='core')
        self.config['workspace']=dict(sources={'project':dict(blobs={'sample.py':'b'*40},validations={'core':['test_sample']})})
        args=dict(self.args,kind='workspace.edit',inputs=inputs)
        entered=threading.Event();release=threading.Event()
        def wait(record):entered.set();release.wait(3)
        with patch.object(self.service,'_prepare_worker',side_effect=wait) as worker:
            try:
                self.assertEqual('PREPARING',self.service.call(args)['state']);self.assertTrue(entered.wait(1))
                self.assertEqual('PREPARING',self.service.call(args)['state'])
                with self.assertRaises(JobError) as caught:
                    self.service.call(dict(args,inputs=dict(inputs,content='VALUE=3\n')))
                self.assertEqual('CONFLICT',caught.exception.code)
                worker.assert_called_once()
                self.assertEqual(inputs,worker.call_args.args[0]['inputs'])
            finally:release.set();self.service.worker.join(2)

    def test_restart_repairs_catalog_after_private_commit_before_publication(self):
        record=self.ready_record()
        with patch.object(self.service,'_catalog',side_effect=OSError('publication interrupted')):
            with self.assertRaises(OSError):self.service._save(record)
        restarted=admin.ResidentService(self.config)
        public=json.loads((Path(self.config['catalog'])/(record['operation_id']+'.json')).read_text())
        self.assertEqual('READY',public['state'])
        self.assertEqual(record['request'],public['request'])
        self.assertEqual(record,restarted.records[record['operation_id']])

    def test_ready_poll_repairs_stale_public_catalog_without_new_preparation(self):
        record=self.ready_record();self.service._save(record)
        path=Path(self.config['catalog'])/(record['operation_id']+'.json')
        path.write_text(json.dumps(dict(operation_id=record['operation_id'],principal_id='owner',state='PREPARING')))
        with patch.object(self.service,'_prepare_worker') as worker:
            self.assertEqual('READY',self.service.call(self.args)['state'])
        worker.assert_not_called()
        self.assertEqual(record['request'],json.loads(path.read_text())['request'])

    def test_successful_preparation_retry_polls_preserve_the_ready_request(self):
        record=self.ready_record();Path(record['attempt']).mkdir();self.service._save(record)
        with patch.object(self.service,'_prepare_worker') as worker, \
             patch.object(self.service,'execution_state',return_value='IDLE'):
            for _ in range(3):
                response=self.service.call(dict(self.args,retry_failed=True))
                self.assertEqual('READY',response['state'])
                self.assertEqual(record['request'],response['request'])
        worker.assert_not_called()
        self.assertEqual(record,self.service.records[record['operation_id']])
        self.assertEqual(1,len(list(Path(self.config['private_root']).glob('*/attempt-*'))))

    def test_stale_unsubmitted_request_can_still_be_prepared_for_the_same_uuid(self):
        record=self.ready_record();Path(record['attempt']).mkdir()
        record['boot_id']='previous-boot';self.service._save(record)
        with patch.object(self.service,'_prepare_worker') as worker:
            response=self.service.call(self.args);self.service.worker.join(2)
        self.assertEqual('PREPARING',response['state'])
        self.assertEqual(record['operation_id'],worker.call_args.args[0]['operation_id'])
        self.assertNotEqual(record['attempt'],worker.call_args.args[0]['attempt'])

    def test_explicit_retry_replaces_only_a_proved_uncommitted_execution_failure(self):
        record=self.ready_record();output=Path(record['output']);output.mkdir(parents=True)
        (output/'launch-intent.json').write_text('{}')
        (output/'finished.json').write_text(json.dumps(dict(returncode=1,streams_eof=True)))
        self.service._save(record)
        with patch.object(self.service,'_unit_active',return_value=False), \
             patch.object(self.service,'_has_committed_task',return_value=True) as committed, \
             patch.object(self.service,'_prepare_worker') as worker, \
             patch.object(self.service,'execution_state',return_value='EXITED'):
            self.assertEqual('READY',self.service.call(dict(self.args,retry_failed=True))['state'])
            worker.assert_not_called()
            committed.return_value=False
            self.assertEqual('PREPARING',self.service.call(dict(self.args,retry_failed=True))['state'])
            self.service.worker.join(2)
            worker.assert_called_once()

    def test_recovered_preparation_admission_failure_can_retry_same_identity(self):
        operation=self.args['operation_id'];root=Path(self.config['private_root'])/operation
        attempt=root/'attempt-1';attempt.mkdir(parents=True)
        result=attempt/'result.json';result.write_text('{"retained":"original preparation"}')
        record=dict(state='PREPARING',operation_id=operation,principal_id='owner',attempt=str(attempt),
            boot_id='boot-one',serial=1,prepare_unit='original.service')
        self.service._save(record)
        with patch.object(self.service,'_preparation_active',return_value=False), \
             patch.object(self.service,'_ready',side_effect=OSError('preparation admission unavailable')) as ready, \
             patch.object(self.service,'_prepare_worker') as worker:
            self.assertEqual('FAILED',self.service.call(self.args)['state'])
            self.assertEqual('PREPARING',self.service.call(dict(self.args,retry_failed=True))['state'])
            self.service.worker.join(2)
        ready.assert_called_once()
        self.assertEqual('boot-one',worker.call_args.args[0]['boot_id'])
        self.assertEqual(operation,worker.call_args.args[0]['operation_id'])
        self.assertEqual('{"retained":"original preparation"}',result.read_text())

    def test_recovery_publication_failure_does_not_demote_committed_ready_state(self):
        record=self.ready_record();record['state']='PREPARING'
        attempt=Path(record['attempt']);attempt.mkdir()
        record.update(serial=1,prepare_unit='original.service')
        launch=dict(request=record.pop('request'),principal_id='owner',policy_path=record['policy_path'],
            controller_envelope=dict(controller=dict(unit='controller.service')))
        result=json.dumps(dict(launch=launch,reservation=str(attempt)))
        (attempt/'result.json').write_text(result)
        self.service._save(record)
        catalog=self.service._catalog
        def interrupted(value):
            # Inject exactly the split commit: private READY persisted while
            # readers still see the earlier public PREPARING record.
            public=json.loads((Path(self.config['catalog'])/(record['operation_id']+'.json')).read_text())
            if public['state']=='PREPARING' and not (attempt/'preparation-failure.json').exists():
                raise OSError('public view unavailable once')
            catalog(value)
        with patch.object(self.service,'_preparation_active',return_value=False), \
             patch.object(admin.task_service,'TaskService') as admission, \
             patch.object(self.service,'_catalog',side_effect=interrupted), \
             patch.object(self.service,'_prepare_worker') as worker:
            response=self.service.call(self.args)
        self.assertEqual('READY',response['state'])
        self.assertEqual(launch['request'],response['request'])
        self.assertEqual('READY',self.service.records[record['operation_id']]['state'])
        worker.assert_not_called();admission.assert_called_once_with(launch)
        self.assertEqual(result,(attempt/'result.json').read_text())
        self.assertTrue((attempt/'preparation-failure.json').exists())

    def test_exact_quota_pool_end_accepts_last_complete_allocation(self):
        self.config['last_project_id']=self.config['first_project_id']+6
        with patch.object(self.service,'_prepare_worker'):
            self.assertEqual('PREPARING',self.service.call(self.args)['state'])
            self.service.worker.join(2)
            before=set(Path(self.config['private_root']).iterdir())
            for _ in range(3):
                with self.assertRaises(JobError) as caught:
                    self.service.call(dict(self.args,operation_id=str(uuid.uuid4())))
                self.assertEqual('LIMIT_EXCEEDED',caught.exception.code)
            self.assertEqual(before,set(Path(self.config['private_root']).iterdir()))
            self.assertEqual(1,len(self.service.records))


class GeneratedInputTests(unittest.TestCase):
    def test_helper_executes_the_verified_bytes_without_reopening_source(self):
        with tempfile.TemporaryDirectory() as root:
            relative='tests/e3_host/fixture.py';path=Path(root)/relative
            path.parent.mkdir(parents=True);raw=b'VALUE = "verified"\n';path.write_bytes(raw)
            installation={'source':{'root':root,'files':{relative:hashlib.sha256(raw).hexdigest()}}}
            def read(*args):
                path.write_bytes(b'VALUE = "replacement"\n')
                return raw
            with patch.object(provision_task,'read_protected',side_effect=read):
                self.assertEqual('verified',provision_task._helper(installation,'fixture').VALUE)

    def test_helper_digest_mismatch_is_rejected_before_execution(self):
        installation={'source':{'root':'/synthetic-source','files':{'tests/e3_host/fixture.py':'0'*64}}}
        with patch.object(provision_task,'read_protected',return_value=b'raise RuntimeError("must not execute")'):
            with self.assertRaisesRegex(ValueError,'PROVISION_SOURCE_CHANGED'):
                provision_task._helper(installation,'fixture')

    def test_server_generated_request_material_is_serializable_and_unique(self):
        template=dict(plan=dict(host=dict(hostname='guest',dmi_vendor='QEMU',dmi_product='fixture'),
            mounts=dict(quota=dict(uuid='quota-id',source='/dev/fixture',path='/fixture')),
            directories=dict(control=dict(path='/old/control'),state=dict(path='/old/state')),
            settings=dict(identity={},controllers=dict(target={},supervisor={}),original_budgets=dict(wall_seconds=72)),
            roots=[{} for _ in range(7)]),observed=dict(parents={},system_geometry=dict(
                schema='fixture',retained_ordinary_parent=dict(parent=dict(path='/old'),
                memory_bytes=7,memory_swap_max=7,tasks_max=7,cpu_quota_per_sec_usec=1000000))))
        config=dict(template=template,installation=dict(source=dict(commit='a'*40)),
            bases={'/old':'/'+'r'*39},mounts=[],minimum_free_bytes=1,
            profile_ref='host-inspect',install_uuid=str(uuid.uuid4()),request_ttl_seconds=3600,first_project_id=15000)
        def read(path,*args,**kwargs):
            path=str(path)
            if path.endswith('hostname'):return 'guest'
            if path.endswith('sys_vendor'):return 'QEMU'
            if path.endswith('product_name'):return 'fixture'
            if path.endswith('cpu.max'):return '100000 100000'
            return '7'
        info=SimpleNamespace(st_dev=7,st_ino=7,st_rdev=7)
        operation=str(uuid.uuid4())
        serials=(1,9,10,32,99,100)
        with patch.object(provision_task.Path,'read_text',read), \
             patch.object(provision_task.os,'stat',return_value=info), \
             patch.object(provision_task.os,'statvfs',return_value=SimpleNamespace(f_bavail=10000,f_frsize=4096,f_favail=10000)), \
             patch.object(provision_task.budget,'current_clock',return_value={'boot_id':'new-boot'}):
            values=[provision_task.task_input(config,operation,'owner',serial) for serial in serials]
        for value in values:
            provision_task.check_endpoint_lengths(value['plan'])
            self.assertEqual(value,json.loads(json.dumps(value)))
            self.assertTrue(value['cancellation'])
            self.assertEqual({'lh:inspect','lh:submit','lh:read','lh:cancel','lh:evidence'},set(value['scopes']))
            identity=value['plan']['settings']['identity']
            self.assertRegex(identity['session'],r'^[0-9a-f]{64}$')
            self.assertEqual('new-boot',value['plan']['host']['boot_id'])
            self.assertEqual(template['plan']['settings']['original_budgets'],value['plan']['settings']['original_budgets'])
        self.assertNotEqual(values[0]['plan']['settings']['identity']['authority_id'],values[1]['plan']['settings']['identity']['authority_id'])
        self.assertTrue({x['project_id'] for x in values[0]['plan']['roots']}.isdisjoint(
            {x['project_id'] for x in values[1]['plan']['roots']}))
        self.assertEqual(len(serials),len({v['plan']['directories']['control']['path'] for v in values}))
        self.assertEqual('/old/control',template['plan']['directories']['control']['path'])

    def test_endpoint_limit_covers_control_api_and_preserves_path_rules(self):
        control_name='/preflight-ctl.sock'
        api_name='/maintenance.sock'
        for role,ending in (('control',control_name),('state',api_name)):
            for prefix in ('/', '/nested/'):
                path=prefix+'a'*(107-len(prefix.encode())-len(ending))
                plan={'directories':{'control':{'path':'/control'},'state':{'path':'/state'}}}
                plan['directories'][role]['path']=path
                provision_task.check_endpoint_lengths(plan)
                plan['directories'][role]['path']+='a'
                with self.assertRaisesRegex(ValueError,'ENDPOINT_LENGTH'):
                    provision_task.check_endpoint_lengths(plan)
        plan={'directories':{'control':{'path':'/中'},'state':{'path':'/state'}}}
        with self.assertRaisesRegex(ValueError,'PATH'):
            provision_task.check_endpoint_lengths(plan)

    def test_overlong_endpoint_fails_before_directory_or_quota_creation(self):
        plan=dict(host={'boot_id':'boot'},directories=dict(control={'path':'/'+'a'*100},state={'path':'/state'}))
        installation=dict(source={'commit':'a'*40},installed={'payload_digest':'b'*64,'package_root':'/installed'})
        helpers=[Mock(),Mock(),Mock()]
        with patch.object(provision_task.os,'geteuid',return_value=0), \
             patch.object(provision_task.budget,'current_clock',return_value={'boot_id':'boot'}), \
             patch.object(provision_task,'verify_release'), \
             patch.object(provision_task,'_helper',side_effect=helpers), \
             patch.object(provision_task.os,'open') as opened, \
             patch.object(provision_task.Path,'mkdir') as mkdir:
            with self.assertRaisesRegex(ValueError,'ENDPOINT_LENGTH'):
                provision_task.prepare(dict(plan=plan,installation=installation))
        helpers[1].validate_plan.assert_called_once_with(plan)
        helpers[0].Quota.assert_not_called()
        opened.assert_not_called();mkdir.assert_not_called()
