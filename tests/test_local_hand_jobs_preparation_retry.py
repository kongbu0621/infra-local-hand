"""Preparation-local failures keep durable attempt identity and remain retryable."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import unittest
import uuid
from unittest.mock import Mock, patch

from admin.local_hand_system_manager import resident_service as admin
import test_local_hand_maintenance_gate as fixtures
import test_local_hand_resident as resident_fixtures


class PreparationRetryTests(unittest.TestCase):
    def service(self):
        case=fixtures.RuntimeGateTests('runTest');case.setUp();self.addCleanup(case.doCleanups)
        return case,case.retry_service()

    @staticmethod
    def request():
        return dict(action='prepare',operation_id=str(uuid.uuid4()),kind='host.inspect',
                    profile_ref='fixture',principal_id='owner')

    def restart(self,case,service):
        with patch.object(admin.maintenance,'from_config',return_value=case.gate), \
                patch.object(admin.budget,'current_clock',return_value={'boot_id':'test-boot'}):
            return admin.ResidentService(service.config)

    def local_retry(self,service,request):
        with patch.object(admin.provision_task,'task_input',side_effect=OSError('local pre-process failure')):
            result=service.call(dict(request,retry_failed=True));service.worker.join(3)
            self.assertFalse(service.worker.is_alive())
            return result

    def test_accept_before_directory_failure_retries_without_reusing_attempt(self):
        for leaf in ('operation','attempt'):
            with self.subTest(leaf=leaf):
                case,service=self.service();request=self.request()
                operation_root=service.root/request['operation_id']
                target=operation_root if leaf=='operation' else operation_root/'attempt-1'
                mkdir=Path.mkdir
                def fail_selected(path,*args,**kwargs):
                    if path==target:raise OSError('temporary mkdir failure')
                    return mkdir(path,*args,**kwargs)
                with patch.object(Path,'mkdir',new=fail_selected):
                    with self.assertRaises(OSError):service.call(request)
                old=next(iter(case.gate.snapshot()['responsibilities'].values()))
                self.assertEqual('CLOSED',old['state'])
                self.assertEqual({'never_dispatched':True},old['proof'])
                self.assertEqual('PREPARING',self.local_retry(service,request)['state'])
                current=service.records[request['operation_id']]
                self.assertNotEqual(old['attempt_id'],current['attempt'])
                self.assertEqual(2,current['serial'])
                self.assertEqual([],case.gate.active())

    def test_global_serial_includes_another_tasks_durable_attempt(self):
        case,service=self.service();first=self.request()
        with patch.object(Path,'mkdir',side_effect=OSError('before any directory')):
            with self.assertRaises(OSError):service.call(first)
        second=self.request();self.local_retry(service,second)
        self.assertEqual(2,service.records[second['operation_id']]['serial'])
        self.assertEqual([],case.gate.active())

    def test_lost_accept_reply_recovers_before_directory_creation(self):
        case,service=self.service();request=self.request();accept=case.gate.accept
        def lost_reply(*args,**kwargs):
            accept(*args,**kwargs)
            raise OSError('accept persisted but acknowledgement lost')
        with patch.object(case.gate,'accept',side_effect=lost_reply):
            with self.assertRaises(OSError):service.call(request)
        self.assertEqual([],list(service.root.iterdir()))
        self.assertEqual('ACCEPTED',case.gate.active()[0]['state'])
        restarted=self.restart(case,service);restarted.recover_undispatched()
        self.local_retry(restarted,request)
        self.assertEqual(2,restarted.records[request['operation_id']]['serial'])
        self.assertEqual([],case.gate.active())

    def test_gate_only_original_identity_cannot_change_owner_or_inputs(self):
        from local_hand_jobs.contract import JobError
        for change in ('owner','inputs'):
            with self.subTest(change=change):
                case,service=self.service();request=self.request()
                service.config['principals'].append('other')
                service.config['workspace']={'sources':{'project':{
                    'blobs':{'sample.py':'a'*40},'validations':{'core':{}}}}}
                inputs=dict(source_ref='project',relative_path='sample.py',expected_sha256='a'*64,
                            content='VALUE=2\n',validation_ref='core')
                request.update(kind='workspace.edit',inputs=inputs)
                with patch.object(Path,'mkdir',side_effect=OSError('before current identity is published')):
                    with self.assertRaises(OSError):service.call(request)
                changed=(dict(request,principal_id='other') if change=='owner' else
                         dict(request,inputs=dict(inputs,content='VALUE=3\n')))
                error=None
                with patch.object(service,'_prepare_worker') as worker:
                    try:service.call(changed)
                    except JobError as caught:error=caught
                    if service.worker is not None:service.worker.join(3)
                    self.assertIsNotNone(error)
                    self.assertEqual('UNAUTHORIZED' if change=='owner' else 'CONFLICT',error.code)
                    worker.assert_not_called()
                self.assertEqual(1,len(case.gate.snapshot()['responsibilities']))
                self.local_retry(service,request)
                self.assertEqual('owner',service.records[request['operation_id']]['principal_id'])

    def test_lost_dispatch_reply_before_popen_retains_positive_non_delivery(self):
        case,service=self.service();request=self.request();dispatch=case.gate.dispatch
        def lost_reply(*args,**kwargs):
            dispatch(*args,**kwargs)
            raise OSError('dispatch record acknowledgement lost before Popen')
        with patch.object(admin.provision_task,'task_input',return_value={}), \
                patch.object(case.gate,'dispatch',side_effect=lost_reply), \
                patch.object(case.gate,'finish',side_effect=OSError('closure record unavailable')), \
                patch.object(admin.subprocess,'Popen') as popen:
            service.call(request);service.worker.join(3)
            self.assertFalse(service.worker.is_alive());popen.assert_not_called()
        self.assertEqual('DISPATCHING',case.gate.active()[0]['state'])
        restarted=self.restart(case,service)
        with patch.object(admin,'unit_closed') as observed:
            restarted.recover_undispatched();observed.assert_not_called()
        self.assertEqual([],case.gate.active())

    def test_durable_attempt_reservations_keep_the_original_quota_bound(self):
        from local_hand_jobs.contract import JobError
        case,service=self.service();request=self.request()
        service.config['last_project_id']=service.config['first_project_id']+6
        with patch.object(Path,'mkdir',side_effect=OSError('before any directory')):
            with self.assertRaises(OSError):service.call(request)
        with patch.object(service,'_prepare_worker') as worker:
            with self.assertRaises(JobError) as denied:service.call(request)
            self.assertEqual('LIMIT_EXCEEDED',denied.exception.code)
            worker.assert_not_called()
        self.assertEqual(1,len(case.gate.snapshot()['responsibilities']))

    def test_initial_current_and_catalog_publication_failures_resume_after_restart(self):
        for method in ('_save','_catalog'):
            with self.subTest(method=method):
                case,service=self.service();request=self.request()
                with patch.object(service,method,side_effect=OSError('temporary publication failure')), \
                        patch.object(service,'_prepare_worker') as worker:
                    with self.assertRaises(OSError):service.call(request)
                    worker.assert_not_called()
                self.assertEqual([],case.gate.active())
                restarted=self.restart(case,service);restarted.recover_undispatched()
                if method=='_catalog':
                    self.assertEqual('FAILED',restarted.records[request['operation_id']]['state'])
                self.local_retry(restarted,request)
                self.assertEqual(2,restarted.records[request['operation_id']]['serial'])
                self.assertEqual([],case.gate.active())

    def test_live_worker_keeps_its_accepted_responsibility(self):
        case,service=self.service();request=self.request()
        entered=threading.Event();release=threading.Event()
        def waiting_worker(record):entered.set();release.wait(3)
        with patch.object(service,'_prepare_worker',side_effect=waiting_worker):
            try:
                service.call(request);self.assertTrue(entered.wait(1))
                before=case.gate.snapshot()
                service.recover_undispatched();service.deployment_status()
                self.assertEqual(before,case.gate.snapshot())
                self.assertEqual('PREPARING',service.records[request['operation_id']]['state'])
            finally:
                release.set();service.worker.join(3)
        self.assertFalse(service.worker.is_alive())
        service.recover_undispatched()
        self.assertEqual('FAILED',service.records[request['operation_id']]['state'])
        self.assertEqual([],case.gate.active())

    def test_closed_undispatched_duty_repairs_failed_current_publication_after_restart(self):
        case,service=self.service();request=self.request()
        with patch.object(service,'_prepare_worker'):
            service.call(request);service.worker.join(3)
            self.assertFalse(service.worker.is_alive())
        with patch.object(service,'_save',side_effect=OSError('temporary current publication failure')):
            service.recover_undispatched()
        self.assertEqual([],case.gate.active())
        self.assertEqual('PREPARING',service.records[request['operation_id']]['state'])
        restarted=self.restart(case,service)
        restarted.recover_undispatched()
        self.assertEqual('FAILED',restarted.records[request['operation_id']]['state'])
        self.assertEqual('FAILED',json.loads((restarted.catalog/(request['operation_id']+'.json')).read_text())['state'])
        self.local_retry(restarted,request)
        self.assertEqual([],case.gate.active())

    def test_explicit_process_creation_failure_recovers_after_lost_gate_closure(self):
        case,service=self.service();request=self.request()
        # Exercise actual Popen ENOENT; no test executable or unit is created.
        service.config['installation']['installed']['programs']['systemd_run']['path']=str(case.root/'missing-program')
        with patch.object(admin.provision_task,'task_input',return_value={}), \
                patch.object(admin,'unit_closed',return_value=False), \
                patch.object(case.gate,'finish',side_effect=OSError('temporary gate closure failure')):
            service.call(request);service.worker.join(3)
            self.assertFalse(service.worker.is_alive())
        original=service.records[request['operation_id']]
        self.assertEqual('FAILED',original['state'])
        self.assertEqual('DISPATCHING',case.gate.active()[0]['state'])
        self.assertFalse((Path(original['attempt'])/'preparation-exit.json').exists())
        restarted=self.restart(case,service)
        proof_path=Path(original['attempt'])/'preparation-not-started.json'
        raw=proof_path.read_bytes();proof=json.loads(raw)
        proof['admission_id']='0'*32;proof_path.write_text(json.dumps(proof))
        restarted.deployment_status()
        self.assertEqual(1,len(case.gate.active()))
        proof_path.write_bytes(raw)
        with patch.object(admin,'unit_closed',return_value=False) as observed:
            restarted.recover_undispatched();restarted.deployment_status()
            observed.assert_not_called()
        self.assertEqual([],case.gate.active())
        closed=case.gate.snapshot()['responsibilities'][original['maintenance_admission']['id']]
        self.assertEqual({'never_dispatched':True},closed['proof'])

    def test_communication_failure_cannot_be_reclassified_as_unstarted(self):
        case,service=self.service();request=self.request()
        process=Mock(returncode=1)
        process.__enter__=Mock(return_value=process);process.__exit__=Mock(return_value=False)
        process.communicate.side_effect=OSError('capture failed after process creation')
        with patch.object(admin.provision_task,'task_input',return_value={}), \
                patch.object(admin.subprocess,'Popen',return_value=process), \
                patch.object(admin,'unit_closed',return_value=False):
            service.call(request);service.worker.join(3)
            self.assertFalse(service.worker.is_alive())
            service.deployment_status()
        original=service.records[request['operation_id']]
        self.assertFalse((Path(original['attempt'])/'preparation-not-started.json').exists())
        self.assertEqual('DISPATCHING',case.gate.active()[0]['state'])
        proof=json.loads((Path(original['attempt'])/'preparation-exit.json').read_text())
        self.assertEqual({'returncode':1,'capture_complete':False},proof)
        with patch.object(admin,'unit_closed',return_value=True):service.deployment_status()
        self.assertEqual([],case.gate.active())

    def test_waiter_without_an_exit_proof_cannot_close_from_unit_state_alone(self):
        case,service=self.service();request=self.request()
        process=Mock(returncode=None)
        process.__enter__=Mock(return_value=process);process.__exit__=Mock(return_value=False)
        process.communicate.side_effect=OSError('waiter exit is unknown')
        with patch.object(admin.provision_task,'task_input',return_value={}), \
                patch.object(admin.subprocess,'Popen',return_value=process), \
                patch.object(admin,'unit_closed',return_value=True) as observer:
            service.call(request);service.worker.join(3)
            self.assertFalse(service.worker.is_alive())
            service.deployment_status();observer.assert_not_called()
        self.assertEqual('DISPATCHING',case.gate.active()[0]['state'])

    def test_real_waiter_timeout_keeps_partial_exit_and_waits_for_original_unit(self):
        case,service=self.service();request=self.request();children=[]
        popen=subprocess.Popen
        def temporary_waiter(command,**kwargs):
            # Substitute only the fixed systemd-run program with a harmless
            # real child; use the production capture/kill/wait path.
            child=popen([sys.executable,'-B','-c',
                         "import time; print('partial',flush=True); time.sleep(5)"],**kwargs)
            communicate=child.communicate
            child.communicate=lambda timeout:communicate(timeout=.05)
            children.append(child)
            return child
        try:
            with patch.object(admin.provision_task,'task_input',return_value={}), \
                    patch.object(admin.subprocess,'Popen',side_effect=temporary_waiter), \
                    patch.object(admin,'unit_closed',return_value=False):
                service.call(request);service.worker.join(3)
                self.assertFalse(service.worker.is_alive())
            self.assertEqual(1,len(children));self.assertIsNotNone(children[0].poll())
            original=service.records[request['operation_id']];attempt=Path(original['attempt'])
            self.assertFalse((attempt/'preparation-not-started.json').exists())
            proof=json.loads((attempt/'preparation-exit.json').read_text())
            self.assertEqual(children[0].returncode,proof['returncode'])
            self.assertFalse(proof['capture_complete'])
            self.assertEqual('DISPATCHING',case.gate.active()[0]['state'])
            with patch.object(admin,'unit_closed',return_value=True):service.deployment_status()
            self.assertEqual([],case.gate.active())
        finally:
            for child in children:
                if child.poll() is None:child.kill()
                child.wait(timeout=3)

    def test_worker_ready_reply_failure_preserves_result_and_closes_original_duty(self):
        case,service=self.service();request=self.request();sync=os.fsync;injected=[]
        current=service.root/request['operation_id']/'current.json'
        process=Mock(returncode=0)
        process.__enter__=Mock(return_value=process);process.__exit__=Mock(return_value=False)
        def prepared(timeout):
            record=service.records[request['operation_id']];attempt=Path(record['attempt'])
            launch=dict(request=dict(operation_id=request['operation_id'],kind='host.inspect',inputs={},
                                     request_digest='a'*64,expires_at=int(time.time())+300),
                        principal_id='owner',policy_path='/synthetic-policy',
                        controller_envelope=dict(controller=dict(unit='controller.service')))
            (attempt/'result.json').write_text(json.dumps(dict(launch=launch,reservation=str(attempt))))
            return b'',b''
        process.communicate.side_effect=prepared
        def lost_reply(fd):
            sync(fd);info=os.fstat(fd)
            if current.exists():
                parent=current.parent.stat()
                if (not injected and (info.st_dev,info.st_ino)==(parent.st_dev,parent.st_ino)
                        and json.loads(current.read_text())['state']=='READY'):
                    injected.append(True);raise OSError('worker READY sync reply lost')
        with patch.object(admin.os,'fsync',side_effect=lost_reply), \
                patch.object(admin.provision_task,'task_input',return_value={}), \
                patch.object(admin.subprocess,'Popen',return_value=process), \
                patch.object(admin.task_service,'TaskService'):
            service.call(request);service.worker.join(3)
            self.assertFalse(service.worker.is_alive())
            result=service.call(request)
        self.assertTrue(injected);self.assertEqual('READY',result['state'])
        record=service.records[request['operation_id']]
        self.assertTrue((Path(record['attempt'])/'preparation-failure.json').exists())
        duty=case.gate.snapshot()['responsibilities'][record['maintenance_admission']['id']]
        self.assertEqual('CLOSED',duty['state'])
        self.assertEqual(dict(process_exited=True,writers_stopped=True),duty['proof'])


class ReadyPublicationTests(unittest.TestCase):
    def preparation(self):
        case=resident_fixtures.PreparationTests('runTest');case.setUp();self.addCleanup(case.doCleanups)
        self.addCleanup(lambda:getattr(case.service,'close',lambda:None)())
        record=case.ready_record();record['state']='PREPARING'
        attempt=Path(record['attempt']);attempt.mkdir()
        record.update(serial=1,prepare_unit='original.service')
        launch=dict(request=record.pop('request'),principal_id='owner',policy_path=record['policy_path'],
                    controller_envelope=dict(controller=dict(unit='controller.service')))
        (attempt/'result.json').write_text(json.dumps(dict(launch=launch,reservation=str(attempt))))
        case.service._save(record)
        return case,record,launch

    def test_ready_rename_or_sync_reply_failure_preserves_original_result(self):
        for boundary in ('rename','sync'):
            with self.subTest(boundary=boundary):
                case,record,launch=self.preparation();attempt=Path(record['attempt'])
                current=attempt.parent/'current.json';original_result=(attempt/'result.json').read_bytes()
                directory=attempt.parent.stat();injected=[];sync=os.fsync;rename=os.rename
                def lose_sync_reply(fd):
                    sync(fd);info=os.fstat(fd)
                    if (boundary=='sync' and not injected
                            and (info.st_dev,info.st_ino)==(directory.st_dev,directory.st_ino)
                            and json.loads(current.read_text())['state']=='READY'):
                        injected.append(True);raise OSError('lost READY directory-sync reply')
                def lose_rename_reply(*args,**kwargs):
                    rename(*args,**kwargs)
                    if boundary=='rename' and not injected and json.loads(current.read_text())['state']=='READY':
                        injected.append(True);raise OSError('lost READY rename reply')
                with patch.object(admin.os,'fsync',side_effect=lose_sync_reply), \
                        patch.object(admin.os,'rename',side_effect=lose_rename_reply), \
                        patch.object(case.service,'_preparation_active',return_value=False), \
                        patch.object(admin.task_service,'TaskService'), \
                        patch.object(case.service,'_prepare_worker') as worker:
                    response=case.service.call(case.args)
                    retried=case.service.call(dict(case.args,retry_failed=True))
                    if case.service.worker is not None:case.service.worker.join(3)
                self.assertTrue(injected)
                self.assertEqual('READY',response['state']);self.assertEqual(response,retried)
                self.assertEqual(launch['request'],response['request'])
                self.assertEqual('READY',json.loads(current.read_text())['state'])
                self.assertEqual(original_result,(attempt/'result.json').read_bytes())
                self.assertTrue((attempt/'preparation-failure.json').exists());worker.assert_not_called()

    def test_persistent_ready_sync_uncertainty_is_retained_then_same_task_recovers(self):
        from local_hand_jobs.contract import JobError
        case,record,launch=self.preparation();attempt=Path(record['attempt'])
        current=attempt.parent/'current.json';directory=attempt.parent.stat();sync=os.fsync
        def unavailable(fd):
            info=os.fstat(fd)
            if ((info.st_dev,info.st_ino)==(directory.st_dev,directory.st_ino)
                    and json.loads(current.read_text())['state']=='READY'):
                raise OSError('READY directory sync remains unavailable')
            sync(fd)
        with patch.object(case.service,'_preparation_active',return_value=False), \
                patch.object(admin.task_service,'TaskService'), \
                patch.object(case.service,'_prepare_worker') as worker:
            with patch.object(admin.os,'fsync',side_effect=unavailable):
                with self.assertRaises(JobError) as unknown:case.service.call(case.args)
                self.assertEqual('IO_UNCERTAIN',unknown.exception.code)
            self.assertEqual('READY',json.loads(current.read_text())['state'])
            self.assertEqual('PREPARING',case.service.records[record['operation_id']]['state'])
            failure=json.loads((attempt/'preparation-failure.json').read_text())
            self.assertIn('READY directory sync remains unavailable',' '.join(failure['notes']))
            response=case.service.call(dict(case.args,retry_failed=True))
            self.assertEqual('READY',response['state']);self.assertEqual(launch['request'],response['request'])
            self.assertEqual(record['attempt'],case.service.records[record['operation_id']]['attempt'])
            worker.assert_not_called()

    def test_same_bytes_from_another_inode_cannot_confirm_this_ready_publication(self):
        from local_hand_jobs.contract import JobError
        case,record,_=self.preparation();attempt=Path(record['attempt'])
        current=attempt.parent/'current.json';directory=attempt.parent.stat();sync=os.fsync;changed=[]
        def replace_after_sync(fd):
            sync(fd);info=os.fstat(fd)
            if (not changed and (info.st_dev,info.st_ino)==(directory.st_dev,directory.st_ino)
                    and json.loads(current.read_text())['state']=='READY'):
                changed.append(current.stat().st_ino)
                replacement=current.with_name('independent-current.json')
                replacement.write_bytes(current.read_bytes());replacement.chmod(0o600)
                os.replace(replacement,current)
                raise OSError('READY publication name changed before confirmation')
        with patch.object(admin.os,'fsync',side_effect=replace_after_sync), \
                patch.object(case.service,'_preparation_active',return_value=False), \
                patch.object(admin.task_service,'TaskService'), \
                patch.object(case.service,'_prepare_worker') as worker:
            with self.assertRaises(JobError) as unknown:case.service.call(case.args)
        self.assertEqual('IO_UNCERTAIN',unknown.exception.code);self.assertTrue(changed)
        self.assertNotEqual(changed[0],current.stat().st_ino)
        self.assertEqual('READY',json.loads(current.read_text())['state'])
        self.assertEqual('PREPARING',case.service.records[record['operation_id']]['state'])
        replacement=current.stat().st_ino;raw=current.read_bytes()
        with patch.object(case.service,'_preparation_active',return_value=False), \
                patch.object(admin.task_service,'TaskService'), \
                patch.object(case.service,'_prepare_worker') as worker:
            for _ in range(2):
                with self.assertRaises(JobError) as pending:case.service.call(dict(case.args,retry_failed=True))
                self.assertEqual('IO_UNCERTAIN',pending.exception.code)
                self.assertEqual(replacement,current.stat().st_ino);self.assertEqual(raw,current.read_bytes())
        worker.assert_not_called()

    def test_pending_ready_poll_skips_new_admission_and_staging_failures(self):
        from local_hand_jobs.contract import JobError
        for boundary in ('admission_read','staging_write'):
            with self.subTest(boundary=boundary):
                case,record,launch=self.preparation();attempt=Path(record['attempt'])
                current=attempt.parent/'current.json';parent=current.parent.stat();sync=os.fsync
                def unavailable(fd):
                    info=os.fstat(fd)
                    if ((info.st_dev,info.st_ino)==(parent.st_dev,parent.st_ino)
                            and json.loads(current.read_text())['state']=='READY'):
                        raise OSError('original READY directory sync unavailable')
                    sync(fd)
                with patch.object(case.service,'_preparation_active',return_value=False), \
                        patch.object(case.service,'_prepare_worker') as worker:
                    with patch.object(admin.os,'fsync',side_effect=unavailable), \
                            patch.object(admin.task_service,'TaskService'):
                        with self.assertRaises(JobError):case.service.call(case.args)
                    original=current.read_bytes();inode=current.stat().st_ino
                    failure=(attempt/'preparation-failure.json').read_bytes();save=admin.task_service.save
                    def fail_staging(directory,name,value,mode=0o600):
                        if name.startswith('.current.json-') and value.get('state')=='READY':
                            raise OSError('second local READY staging failure')
                        return save(directory,name,value,mode)
                    fault=(patch.object(admin.task_service,'TaskService',side_effect=OSError('second admission read failed'))
                           if boundary=='admission_read' else patch.object(admin.task_service,'save',side_effect=fail_staging))
                    with patch.object(admin.task_service,'TaskService'),fault, \
                            patch.object(case.service,'_preparation_active',side_effect=AssertionError('already completed')):
                        response=case.service.call(case.args)
                    self.assertEqual('READY',response['state']);self.assertEqual(launch['request'],response['request'])
                    self.assertEqual(original,current.read_bytes());self.assertEqual(inode,current.stat().st_ino)
                    self.assertEqual(failure,(attempt/'preparation-failure.json').read_bytes())
                    self.assertEqual(record['attempt'],case.service.records[record['operation_id']]['attempt'])
                    worker.assert_not_called()

    def test_pending_ready_never_confirms_or_overwrites_a_replaced_parent(self):
        from local_hand_jobs.contract import JobError
        case,record,_=self.preparation();current=Path(record['attempt']).parent/'current.json'
        directory=current.parent.stat();sync=os.fsync;changed=[]
        def replace_parent(fd):
            sync(fd);info=os.fstat(fd)
            if (not changed and (info.st_dev,info.st_ino)==(directory.st_dev,directory.st_ino)
                    and json.loads(current.read_text())['state']=='READY'):
                changed.append(True)
                retained=current.parent.with_name('original-operation-parent')
                current.parent.rename(retained);shutil.copytree(retained,current.parent)
                raise OSError('original READY parent was replaced')
        with patch.object(case.service,'_preparation_active',return_value=False), \
                patch.object(admin.task_service,'TaskService'), \
                patch.object(case.service,'_prepare_worker') as worker:
            with patch.object(admin.os,'fsync',side_effect=replace_parent):
                with self.assertRaises(JobError):case.service.call(case.args)
            raw=current.read_bytes();inode=current.stat().st_ino;parent=current.parent.stat().st_ino
            for _ in range(2):
                with self.assertRaises(JobError) as pending:case.service.call(case.args)
                self.assertEqual('IO_UNCERTAIN',pending.exception.code)
                self.assertEqual(raw,current.read_bytes());self.assertEqual(inode,current.stat().st_ino)
                self.assertEqual(parent,current.parent.stat().st_ino)
            worker.assert_not_called()

    def test_rename_without_effect_resumes_original_candidate_and_checks_previous_pointer(self):
        from local_hand_jobs.contract import JobError
        for replace_previous in (False,True):
            with self.subTest(replace_previous=replace_previous):
                case,record,launch=self.preparation();current=Path(record['attempt']).parent/'current.json'
                rename=os.rename;staged=[]
                def not_renamed(source,destination,**kwargs):
                    if destination=='current.json':
                        staged.append(current.with_name(source));raise OSError('READY rename did not execute')
                    return rename(source,destination,**kwargs)
                with patch.object(case.service,'_preparation_active',return_value=False), \
                        patch.object(admin.task_service,'TaskService'), \
                        patch.object(case.service,'_prepare_worker') as worker:
                    with patch.object(admin.os,'rename',side_effect=not_renamed):
                        with self.assertRaises(JobError):case.service.call(case.args)
                    candidate=staged[0].stat().st_ino
                    self.assertEqual('PREPARING',json.loads(current.read_text())['state'])
                    if replace_previous:
                        replacement=current.with_name('independent-previous.json')
                        replacement.write_bytes(current.read_bytes());replacement.chmod(0o600);os.replace(replacement,current)
                        previous=current.stat().st_ino
                    with patch.object(admin.task_service,'TaskService',side_effect=AssertionError('must reuse original candidate')):
                        if replace_previous:
                            with self.assertRaises(JobError) as pending:case.service.call(case.args)
                            self.assertEqual('IO_UNCERTAIN',pending.exception.code)
                            self.assertEqual(previous,current.stat().st_ino)
                            self.assertEqual(candidate,staged[0].stat().st_ino)
                        else:
                            response=case.service.call(case.args)
                            self.assertEqual('READY',response['state']);self.assertEqual(launch['request'],response['request'])
                            self.assertEqual(candidate,current.stat().st_ino);self.assertFalse(staged[0].exists())
                    worker.assert_not_called()

    def test_pending_ready_descriptors_are_bounded_and_closed_on_confirmation_or_service_close(self):
        from local_hand_jobs.contract import JobError
        for recover in (False,True):
            with self.subTest(recover=recover):
                case,record,_=self.preparation();current=Path(record['attempt']).parent/'current.json'
                parent=current.parent.stat();sync=os.fsync
                def unavailable(fd):
                    info=os.fstat(fd)
                    if ((info.st_dev,info.st_ino)==(parent.st_dev,parent.st_ino)
                            and json.loads(current.read_text())['state']=='READY'):
                        raise OSError('READY sync still unavailable')
                    sync(fd)
                count=lambda:len(os.listdir('/proc/self/fd'))
                baseline=count()
                with patch.object(case.service,'_preparation_active',return_value=False), \
                        patch.object(admin.task_service,'TaskService'):
                    with patch.object(admin.os,'fsync',side_effect=unavailable):
                        for _ in range(3):
                            with self.assertRaises(JobError) as pending:case.service.call(case.args)
                            self.assertEqual('IO_UNCERTAIN',pending.exception.code)
                            self.assertEqual(baseline+3,count())
                    if recover:self.assertEqual('READY',case.service.call(case.args)['state'])
                    else:case.service.close();case.service.close()
                self.assertEqual(baseline,count())

    def test_repeated_pending_failure_reuses_records_and_retains_different_errors(self):
        from local_hand_jobs.contract import JobError
        case,record,launch=self.preparation();attempt=Path(record['attempt'])
        current=attempt.parent/'current.json';parent=current.parent.stat();sync=os.fsync;cause=['sync failure A']
        def unavailable(fd):
            info=os.fstat(fd)
            if ((info.st_dev,info.st_ino)==(parent.st_dev,parent.st_ino)
                    and json.loads(current.read_text())['state']=='READY'):
                raise OSError(cause[0])
            sync(fd)
        failures=lambda:{path.name:path.read_bytes() for path in attempt.glob('preparation-failure*.json')}
        with patch.object(case.service,'_preparation_active',return_value=False), \
                patch.object(admin.task_service,'TaskService'), \
                patch.object(case.service,'_prepare_worker') as worker:
            with patch.object(admin.os,'fsync',side_effect=unavailable):
                # The initial publication and its later confirmation have
                # different failure notes; both originals must be retained.
                for _ in range(2):
                    with self.assertRaises(JobError):case.service.call(case.args)
                original=failures();self.assertEqual(2,len(original))
                for _ in range(4):
                    with self.assertRaises(JobError) as pending:case.service.call(case.args)
                    self.assertEqual('IO_UNCERTAIN',pending.exception.code)
                    self.assertEqual(original,failures())
                cause[0]='sync failure B'
                with self.assertRaises(JobError):case.service.call(case.args)
                changed=failures();self.assertEqual(3,len(changed))
                self.assertTrue(any(b'sync failure B' in raw for raw in changed.values()))
                self.assertTrue(all(changed[name]==raw for name,raw in original.items()))
                cause[0]='sync failure A'
                with self.assertRaises(JobError):case.service.call(case.args)
                self.assertEqual(changed,failures())
            raw=current.read_bytes();inode=current.stat().st_ino
            response=case.service.call(case.args)
            self.assertEqual('READY',response['state']);self.assertEqual(launch['request'],response['request'])
            self.assertEqual(raw,current.read_bytes());self.assertEqual(inode,current.stat().st_ino)
            self.assertEqual(changed,failures());worker.assert_not_called()

    def test_pending_failure_digest_record_cannot_be_reused_with_different_content(self):
        from local_hand_jobs.contract import JobError
        case,record,_=self.preparation();attempt=Path(record['attempt'])
        current=attempt.parent/'current.json';parent=current.parent.stat();sync=os.fsync
        def unavailable(fd):
            info=os.fstat(fd)
            if ((info.st_dev,info.st_ino)==(parent.st_dev,parent.st_ino)
                    and json.loads(current.read_text())['state']=='READY'):
                raise OSError('same pending failure')
            sync(fd)
        with patch.object(case.service,'_preparation_active',return_value=False), \
                patch.object(admin.task_service,'TaskService'), \
                patch.object(admin.os,'fsync',side_effect=unavailable):
            for _ in range(2):
                with self.assertRaises(JobError):case.service.call(case.args)
            retained=next(attempt.glob('preparation-failure-*.json'))
            retained.write_bytes(b'{"different":"record"}\n');replacement=retained.read_bytes()
            current_bytes=current.read_bytes()
            with self.assertRaisesRegex(ValueError,'RESIDENT_FAILURE_RECORD_CONFLICT'):
                case.service.call(case.args)
        self.assertEqual(2,len(list(attempt.glob('preparation-failure*.json'))))
        self.assertEqual(replacement,retained.read_bytes());self.assertEqual(current_bytes,current.read_bytes())

    def test_restart_reconfirms_visible_ready_before_catalog_and_preserves_original_bytes(self):
        from local_hand_jobs.contract import JobError
        case,record,launch=self.preparation();attempt=Path(record['attempt'])
        current=attempt.parent/'current.json';directory=attempt.parent.stat();sync=os.fsync
        catalog=Path(case.config['catalog'])/(record['operation_id']+'.json')
        original_catalog=catalog.read_bytes();blocked=[]
        def unavailable(fd):
            info=os.fstat(fd)
            if ((info.st_dev,info.st_ino)==(directory.st_dev,directory.st_ino)
                    and json.loads(current.read_text())['state']=='READY'):
                blocked.append(True);raise OSError('READY parent sync remains unavailable across restart')
            sync(fd)
        with patch.object(admin.os,'fsync',side_effect=unavailable), \
                patch.object(case.service,'_preparation_active',return_value=False), \
                patch.object(admin.task_service,'TaskService'):
            with self.assertRaises(JobError):case.service.call(case.args)
            self.assertEqual('PREPARING',case.service.records[record['operation_id']]['state'])
            # Legacy valid JSON formatting is retained byte for byte, rather
            # than being rewritten into the latest publisher's representation.
            current.write_text(json.dumps(json.loads(current.read_text()),indent=2)+'\n')
            original_current=current.read_bytes()
            failure=(attempt/'preparation-failure.json').read_bytes()
            count=len(blocked)
            with self.assertRaises(JobError) as pending:admin.ResidentService(case.config)
            self.assertEqual('IO_UNCERTAIN',pending.exception.code)
            self.assertIsInstance(pending.exception.__cause__,OSError)
            self.assertGreater(len(blocked),count)
        self.assertEqual(original_catalog,catalog.read_bytes())
        synchronized=[];publish=admin.publish;current_info=current.stat()
        def observed_sync(fd):
            info=os.fstat(fd);sync(fd)
            for name,expected in (('file',current_info),('parent',directory)):
                if (info.st_dev,info.st_ino)==(expected.st_dev,expected.st_ino):synchronized.append(name)
        def publish_after_confirmation(path,*args,**kwargs):
            if Path(path)==catalog:self.assertEqual(['file','parent'],synchronized)
            return publish(path,*args,**kwargs)
        with patch.object(admin.os,'fsync',side_effect=observed_sync), \
                patch.object(admin,'publish',side_effect=publish_after_confirmation), \
                patch.object(admin.ResidentService,'_prepare_worker') as worker:
            restarted=admin.ResidentService(case.config)
            response=restarted.call(case.args)
        self.assertEqual('READY',response['state']);self.assertEqual(launch['request'],response['request'])
        self.assertEqual(record['attempt'],restarted.records[record['operation_id']]['attempt'])
        self.assertEqual(original_current,current.read_bytes())
        self.assertEqual(failure,(attempt/'preparation-failure.json').read_bytes());worker.assert_not_called()

    def test_restart_rejects_current_replacement_during_protected_load(self):
        from local_hand_jobs.contract import JobError
        case,record,_=self.preparation();attempt=Path(record['attempt'])
        with patch.object(case.service,'_preparation_active',return_value=False), \
                patch.object(admin.task_service,'TaskService'):
            self.assertEqual('READY',case.service.call(case.args)['state'])
        current=attempt.parent/'current.json';raw=current.read_bytes();load=admin.load
        catalog=Path(case.config['catalog'])/(record['operation_id']+'.json');original=catalog.read_bytes()
        def replaced(path):
            result=load(path)
            if Path(path)==current:
                other=current.with_name('independent-current.json')
                other.write_bytes(raw);other.chmod(0o600);os.replace(other,current)
            return result
        with patch.object(admin,'load',side_effect=replaced), \
                patch.object(admin.ResidentService,'_prepare_worker') as worker:
            with self.assertRaises(JobError) as pending:admin.ResidentService(case.config)
        self.assertEqual('IO_UNCERTAIN',pending.exception.code)
        self.assertEqual(original,catalog.read_bytes());self.assertEqual(raw,current.read_bytes())
        worker.assert_not_called()


if __name__=='__main__':unittest.main()
