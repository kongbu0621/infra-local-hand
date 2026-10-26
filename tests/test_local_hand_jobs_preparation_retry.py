"""Preparation-local failures keep durable attempt identity and remain retryable."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
import uuid
from unittest.mock import Mock, patch

from admin.local_hand_system_manager import resident_service as admin
import test_local_hand_maintenance_gate as fixtures


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


if __name__=='__main__':unittest.main()
