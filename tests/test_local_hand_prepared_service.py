"""Fixed launch retention and real pipe exit; no production host claim."""
import os
import json
from contextlib import nullcontext
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, Mock, patch

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux administrator task launcher')

from admin.local_hand_system_manager import prepared_service as prepared
from admin.local_hand_system_manager.resident_service import ResidentService
from local_hand_jobs.contract import JobError, Principal


class FixedLaunchMaintenanceRetryTests(unittest.TestCase):
    def maintained(self):
        # Imported here because the maintenance fixtures also reuse the plain
        # launcher fixture below; production protection remains unchanged.
        from test_local_hand_maintenance_gate import RuntimeGateTests
        case=RuntimeGateTests('runTest');self.addCleanup(case.doCleanups);case.setUp()
        return case,case.fixed()

    def fail_without_child(self,case,item):
        with case.execution_patches(item,[str(case.root/'missing-controller')]), \
                patch.object(case.gate,'finish',side_effect=OSError('original closure unavailable')):
            with self.assertRaises((JobError,OSError)):item.start()
        return item.maintenance_admission

    def test_no_child_retry_closes_original_receipt_before_fresh_accept(self):
        case,item=self.maintained();old=self.fail_without_child(case,item)
        self.assertEqual('DISPATCHING',case.gate.active()[0]['state'])
        retained={path:path.read_bytes() for path in item.output.glob('local-start-failed-*.json')}
        accept=case.gate.accept
        def checked_accept(*args,**kwargs):
            original=case.gate.snapshot()['responsibilities'][old['id']]
            self.assertEqual('CLOSED',original['state'])
            self.assertEqual({'never_dispatched':True},original['proof'])
            return accept(*args,**kwargs)
        with case.execution_patches(item,[sys.executable,'-c','pass']), \
                patch.object(case.gate,'accept',side_effect=checked_accept):
            item.start();self.assertTrue(item.complete.wait(3));self.assertEqual('EXITED',item.state())
        self.assertEqual([],case.gate.active())
        self.assertEqual(2,len(case.gate.snapshot()['responsibilities']))
        self.assertEqual(retained,{path:path.read_bytes() for path in retained})

    def test_unavailable_old_closure_never_replaces_receipt_or_accepts_another_attempt(self):
        case,item=self.maintained();old=self.fail_without_child(case,item)
        retained={path.name:path.read_bytes() for path in item.output.iterdir()}
        with case.execution_patches(item,[sys.executable,'-c','pass']), \
                patch.object(case.gate,'finish',side_effect=OSError('still unavailable')), \
                patch.object(case.gate,'accept',wraps=case.gate.accept) as accept, \
                patch.object(prepared.subprocess,'Popen',side_effect=OSError('must not deliver')) as popen:
            for _ in range(2):
                with self.assertRaises((JobError,OSError)):item.start()
                self.assertEqual(old,item.maintenance_admission)
            accept.assert_not_called();popen.assert_not_called()
        self.assertEqual(1,len(case.gate.snapshot()['responsibilities']))
        self.assertEqual(retained,{path.name:path.read_bytes() for path in item.output.iterdir()})

    def test_recreated_launcher_cannot_infer_no_child_from_missing_intent(self):
        case,item=self.maintained();old=self.fail_without_child(case,item)
        require=prepared.q.require
        def fixture_protection(condition,code):
            if code!='PREPARED_OUTPUT_PROTECTION':require(condition,code)
        with patch.object(prepared.q,'require',side_effect=fixture_protection), \
                patch.object(prepared.q2_config,'pinned_directory',side_effect=lambda _:os.dup(item.directory)):
            reopened=prepared.FixedLauncher(item.launch,item.installation,item.static,item.output,
                maintenance_gate=case.gate,loaded=item.loaded_deployment,prepared=item.maintenance_prepared)
        self.addCleanup(os.close,reopened.directory)
        with case.execution_patches(reopened,[sys.executable,'-c','pass']), \
                patch.object(case.gate,'accept',wraps=case.gate.accept) as accept, \
                patch.object(prepared.subprocess,'Popen',side_effect=OSError('must not deliver')) as popen:
            with self.assertRaises(JobError) as pending:reopened.start()
            self.assertEqual('IO_UNCERTAIN',pending.exception.code)
            accept.assert_not_called();popen.assert_not_called()
        self.assertEqual(old['id'],reopened.maintenance_admission['id'])
        self.assertEqual('DISPATCHING',case.gate.active()[0]['state'])

    def test_asynchronous_popen_interruption_is_not_positive_no_child_evidence(self):
        case,item=self.maintained()
        with case.execution_patches(item,[str(case.root/'unknown-controller')]), \
                patch.object(prepared.subprocess,'Popen',side_effect=KeyboardInterrupt('unknown process boundary')):
            with self.assertRaises(KeyboardInterrupt):item.start()
        self.assertEqual('DISPATCHING',case.gate.active()[0]['state'])
        with self.assertRaises(JobError) as pending:item.state()
        self.assertEqual('IO_UNCERTAIN',pending.exception.code)
        with patch.object(case.gate,'accept',wraps=case.gate.accept) as accept, \
                patch.object(prepared.subprocess,'Popen') as popen:
            with self.assertRaises(JobError):item.start()
            accept.assert_not_called();popen.assert_not_called()

    def test_lost_accept_reply_reuses_one_original_attempt_until_confirmed(self):
        case,item=self.maintained();accept=case.gate.accept;attempts=[]
        def lost_reply(*args,**kwargs):
            receipt=accept(*args,**kwargs);attempts.append(receipt['attempt_id'])
            raise OSError('original admission committed but reply lost')
        with patch.object(case.gate,'accept',side_effect=lost_reply), \
                patch.object(prepared.subprocess,'Popen') as popen:
            for _ in range(3):
                with self.assertRaisesRegex(OSError,'reply lost'):item.start()
                self.assertIsNone(item.maintenance_admission)
                self.assertEqual('IDLE',item.state())
                self.assertEqual(1,len(case.gate.snapshot()['responsibilities']))
            popen.assert_not_called()
        self.assertEqual(1,len(set(attempts)))
        original=case.gate.active()[0];self.assertEqual('ACCEPTED',original['state'])
        case.gate.close('fixture-maintenance')
        with case.execution_patches(item,[sys.executable,'-c','pass']):
            item.start();self.assertTrue(item.complete.wait(3));self.assertEqual('EXITED',item.state())
        responsibilities=case.gate.snapshot()['responsibilities']
        self.assertEqual([original['id']],list(responsibilities))
        self.assertEqual('CLOSED',responsibilities[original['id']]['state'])
        self.assertEqual({'process_exited':True,'writers_stopped':True},responsibilities[original['id']]['proof'])
        self.assertEqual(original['id'],item.maintenance_admission['id'])

    def resident_pending(self):
        from test_local_hand_deploy_execution_responsibility import ExecutionResponsibilityTests
        fixture=ExecutionResponsibilityTests('runTest');self.addCleanup(fixture.doCleanups)
        case,service,item,record,args=fixture.maintained();self.addCleanup(service.close)
        record['request']['expires_at']=time.time()+600
        item.maintenance_prepared=prepared.maintenance.prepared_binding(item.loaded_deployment,
            operation_id=record['operation_id'],attempt_id=record['attempt'],request_digest='d'*64,launch=item.launch)
        record['maintenance_prepared']=item.maintenance_prepared
        arguments={key:value for key,value in args.items() if key not in {'action','principal_id'}}
        admission=case.gate.accept('prepare',record['operation_id'],record['attempt'],
            dict(arguments=arguments,principal_id='owner',private_root=str(service.root)),service.loaded_deployment)
        case.gate.finish(admission,dict(never_dispatched=True));record['maintenance_admission']=admission
        service._save(record)
        accept=case.gate.accept
        def lost_reply(*args,**kwargs):
            accept(*args,**kwargs);raise OSError('original acceptance reply lost')
        with patch.object(case.gate,'accept',side_effect=lost_reply):
            with self.assertRaises(OSError):
                service.call(dict(action='start',operation_id=record['operation_id'],principal_id='owner',request_digest='d'*64))
        return case,service,item,record,args

    def test_closed_maintenance_retires_lost_accept_without_new_authorization_or_admission(self):
        case,service,item,record,_=self.resident_pending()
        current=Path(record['attempt']).parent/'current.json';raw=current.read_bytes()
        pending=item.admission_attempt;original=case.gate.active()[0];finish=case.gate.finish
        expired=Principal('owner',frozenset({'lh:submit'}),expires_at=int(time.time())-1)
        def lost_finish(*args,**kwargs):
            finish(*args,**kwargs);raise OSError('original closure reply lost')
        with patch.object(case.gate,'accept',wraps=case.gate.accept) as accept, \
                patch.object(prepared.subprocess,'Popen') as popen:
            self.assertEqual({'state':'IDLE'},service.call(dict(action='status',operation_id=record['operation_id'],principal_id='owner')))
            service.deployment_status()
            self.assertEqual('ACCEPTED',case.gate.active()[0]['state'])
            self.assertEqual(pending,item.admission_attempt)
            with self.assertRaises(JobError) as denied:item.start(authorization=expired)
            self.assertEqual('UNAUTHORIZED',denied.exception.code)
            case.gate.close('fixture-maintenance')
            with patch.object(case.gate,'finish',side_effect=lost_finish):service.deployment_status()
            self.assertEqual(pending,item.admission_attempt)
            service.deployment_status()
            self.assertIsNone(item.admission_attempt)
            accept.assert_not_called();popen.assert_not_called()
        duty=case.gate.snapshot()['responsibilities'][original['id']]
        self.assertEqual('CLOSED',duty['state']);self.assertEqual({'never_dispatched':True},duty['proof'])
        self.assertEqual(raw,current.read_bytes())
        with self.assertRaises(JobError) as denied:item.start(authorization=expired)
        self.assertEqual('UNAUTHORIZED',denied.exception.code)

    def test_expired_ready_replacement_waits_for_original_acceptance_closure(self):
        case,service,item,record,args=self.resident_pending()
        current=Path(record['attempt']).parent/'current.json';raw=current.read_bytes()
        pending=item.admission_attempt;original=case.gate.active()[0]
        with patch('time.time',return_value=record['request']['expires_at']+1), \
                patch.object(service,'_prepare_worker') as worker:
            with patch.object(case.gate,'finish',side_effect=OSError('closure unavailable')):
                with self.assertRaises(JobError) as unknown:service.call(args)
                self.assertEqual('IO_UNCERTAIN',unknown.exception.code)
                worker.assert_not_called();self.assertEqual(raw,current.read_bytes())
                self.assertEqual(record,service.records[record['operation_id']])
                self.assertEqual(pending,item.admission_attempt)
            self.assertEqual('PREPARING',service.call(args)['state']);service.worker.join(3)
            worker.assert_called_once()
        duty=case.gate.snapshot()['responsibilities'][original['id']]
        self.assertEqual('CLOSED',duty['state']);self.assertEqual({'never_dispatched':True},duty['proof'])
        self.assertNotEqual(record['attempt'],service.records[record['operation_id']]['attempt'])
        self.assertIsNone(item.admission_attempt)

    def test_explicit_retirement_cannot_adopt_changed_loaded_binding_or_dispatch(self):
        case,_,item,_,_=self.resident_pending();original=case.gate.active()[0]
        pending=item.admission_attempt;loaded=item.loaded_deployment
        item.loaded_deployment=dict(loaded,component='another-manager')
        with self.assertRaises(JobError):item.retire_unstarted_admission()
        self.assertEqual(original,case.gate.active()[0]);self.assertEqual(pending,item.admission_attempt)
        item.loaded_deployment=loaded;case.gate.dispatch(original)
        with self.assertRaises(JobError):item.retire_unstarted_admission()
        self.assertEqual('DISPATCHING',case.gate.active()[0]['state'])
        self.assertEqual(pending,item.admission_attempt)

    def test_standalone_maintenance_status_retires_pending_accept_but_observe_does_not(self):
        from local_hand_jobs import startup
        case,_,item,_,_=self.resident_pending();pending=item.admission_attempt
        original=case.gate.active()[0]
        launch=json.loads(json.dumps(item.launch))
        launch['request']['expires_at']=int(launch['request']['expires_at'])
        launch.update(transport='broker',mcp=None,principal_id='owner',policy_path='/synthetic-policy')
        launch['policy']['process_manager']['gid']=os.getgid()
        raw=json.dumps(launch).encode()
        endpoint=case.root/'prepared.sock';endpoint.touch()
        config=dict(schema='local-hand-prepared-service/v1',launch_path=item.static,
            launch_sha256=prepared.hashlib.sha256(raw).hexdigest(),installation=item.installation,
            output=str(item.output),socket=str(endpoint),descriptor=str(case.root/'descriptor.json'))
        listener=MagicMock();listener.__enter__.return_value=listener
        connection=MagicMock();connection.__enter__.return_value=connection
        connection.getsockopt.return_value=struct.pack('3i',os.getpid(),0,0)
        listener.accept.side_effect=[(connection,None)]*3+[StopIteration('fixture complete')]
        requests=iter(('deployment_status','deployment_observe','deployment_status'));responses=[]
        def read_frame(*args,**kwargs):
            action=next(requests)
            if action=='deployment_observe':case.gate.close('fixture-maintenance')
            return json.dumps({'action':action}).encode()
        def send_frame(_,response,**kwargs):
            self.assertIn('result',response);responses.append(response)
            if len(responses)<3:
                self.assertEqual('ACCEPTED',case.gate.active()[0]['state'])
                self.assertEqual(pending,item.admission_attempt)
            else:
                self.assertEqual([],case.gate.active());self.assertIsNone(item.admission_attempt)
        require=prepared.q.require
        def fixture_protection(condition,code):
            if code not in {'PREPARED_ADMINISTRATOR','PREPARED_SOCKET_PARENT'}:require(condition,code)
        with patch.object(prepared.q,'require',side_effect=fixture_protection), \
                patch.object(prepared,'read_protected',return_value=raw), \
                patch.object(prepared.task_service,'TaskService'), \
                patch.object(prepared,'acquire_service_lock'), \
                patch.object(prepared,'FixedLauncher',return_value=item), \
                patch.object(prepared.maintenance,'from_config',return_value=case.gate), \
                patch.object(prepared.maintenance,'loaded_configuration',return_value=item.loaded_deployment), \
                patch.object(startup,'authorize',return_value=nullcontext()), \
                patch.object(prepared.socket,'socket',return_value=listener), \
                patch.object(prepared.os,'chown'),patch('builtins.print'), \
                patch.object(prepared.cli,'_read_frame',side_effect=read_frame), \
                patch.object(prepared.cli,'_send_frame',side_effect=send_frame), \
                patch.object(case.gate,'accept',wraps=case.gate.accept) as accept, \
                patch.object(prepared.subprocess,'Popen') as popen:
            with self.assertRaisesRegex(StopIteration,'fixture complete'):prepared.serve(config)
            accept.assert_not_called();popen.assert_not_called()
        self.assertEqual(3,len(responses))
        duty=case.gate.snapshot()['responsibilities'][original['id']]
        self.assertEqual('CLOSED',duty['state']);self.assertEqual({'never_dispatched':True},duty['proof'])


class FixedLaunchTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.launcher=prepared.FixedLauncher.__new__(prepared.FixedLauncher)
        item=self.launcher
        item.output=Path(root.name)
        item.directory=os.open(root.name,os.O_RDONLY|os.O_DIRECTORY)
        self.addCleanup(os.close,item.directory)
        item.process=None;item.complete=threading.Event();item.result=None;item.failure=None
        item.record_lock=threading.Lock()
        item.started=False;item.finished=False
        item.static='/synthetic/static.json'
        item.installation={'installed':{'programs':{'python':{},'systemd_run':{}}}}
        item.launch={'request':{'operation_id':'prepared-operation'},'policy':{
            'broker_root':root.name,'process_manager':{'uid':os.getuid(),'manager_binding':{'boot_id':'test-boot'}}}}

    def test_expiry_during_executable_check_precedes_intent_and_delivery(self):
        cutoff = int(time.time()) + 100
        principal = Principal('owner', frozenset({'lh:submit'}), expires_at=cutoff)
        with patch('time.time', return_value=cutoff - 1) as clock:
            def executable(_):
                clock.return_value = cutoff
                return os.open('/dev/null', os.O_RDONLY)
            with patch.object(prepared, 'controller_command', return_value=['/synthetic/not-started']), \
                 patch.object(prepared.budget, 'current_clock', return_value={'boot_id':'test-boot'}), \
                 patch.object(prepared.q2_config, 'executable', side_effect=executable), \
                 patch.object(prepared.subprocess, 'Popen') as popen:
                with self.assertRaises(JobError) as caught:
                    self.launcher.start(authorization=principal)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        popen.assert_not_called()
        self.assertEqual([], list(self.launcher.output.iterdir()))

    def test_expiry_after_intent_or_thread_creation_retains_failure_and_allows_one_retry(self):
        for stage in ('intent', 'thread'):
            with self.subTest(stage=stage):
                fixture = FixedLaunchTests('runTest')
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                item = fixture.launcher
                cutoff = int(time.time()) + 100
                principal = Principal('owner', frozenset({'lh:submit'}), expires_at=cutoff)
                create, start_thread, commit = subprocess.Popen, threading.Thread.start, item._commit_intent
                workers = []
                command = [sys.executable, '-c', "print('one refreshed attempt')"]
                with patch('time.time', return_value=cutoff - 1) as clock:
                    def publish(argv):
                        commit(argv)
                        if stage == 'intent': clock.return_value = cutoff
                    def start(worker):
                        workers.append(worker)
                        start_thread(worker)
                        if stage == 'thread': clock.return_value = cutoff
                    with patch.object(prepared, 'controller_command', return_value=command), \
                         patch.object(prepared.budget, 'current_clock', return_value={'boot_id':'test-boot'}), \
                         patch.object(prepared.q2_config, 'executable', side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
                         patch.object(item, '_commit_intent', side_effect=publish), \
                         patch.object(prepared.threading.Thread, 'start', new=start), \
                         patch.object(prepared.subprocess, 'Popen', side_effect=create) as popen:
                        with self.assertRaises(JobError) as caught:
                            item.start(authorization=principal)
                        self.assertEqual('UNAUTHORIZED', caught.exception.code)
                        popen.assert_not_called()
                        self.assertEqual('IDLE', item.state())
                        self.assertFalse((item.output/'launch-intent.json').exists())
                        retained = list(item.output.glob('local-authorization-expired-*.json'))
                        self.assertEqual(1, len(retained))
                        original = retained[0].read_bytes()
                        for worker in workers:
                            worker.join(1)
                            self.assertFalse(worker.is_alive())
                        refreshed = Principal('owner', principal.scopes, expires_at=cutoff + 100)
                        item.start(authorization=refreshed)
                        self.assertTrue(item.complete.wait(3))
                        # Expiry cannot cancel or replay an already delivered process.
                        clock.return_value = refreshed.expires_at
                        self.assertEqual('EXITED', item.state())
                        self.assertEqual('EXITED', item.start())
                        popen.assert_called_once()
                        self.assertEqual(original, retained[0].read_bytes())
                        self.assertEqual(0, item.result['returncode'])

    def test_fixed_receiver_retains_authority_until_process_delivery(self):
        from local_hand_jobs.forwarded_bounds import attach
        launch = dict(self.launcher.launch, principal_id='owner')
        launch['request'] = dict(launch['request'], request_digest='a'*64)
        launch['policy']['principals'] = {'owner': {'scopes': ['lh:submit', 'lh:read']}}
        body = dict(action='start', **launch['request'])
        cutoff = int(time.time()) + 100
        principal = Principal('owner', frozenset({'lh:submit'}), expires_at=cutoff)
        request, authorization = prepared.bounded_request(attach(body, principal), launch)
        self.assertEqual(body, request)
        self.assertEqual(cutoff, authorization.expires_at)
        with patch('time.time', return_value=cutoff), patch.object(prepared.subprocess, 'Popen') as popen:
            with self.assertRaises(JobError) as caught:
                self.launcher.start(authorization=authorization)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        popen.assert_not_called()
        self.assertEqual((body, None), prepared.bounded_request(body, launch))

    def test_local_popen_failure_retains_record_and_can_retry_without_remote_execution(self):
        with patch.object(prepared,'controller_command',return_value=['/synthetic/absent']), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=OSError('not started')) as popen:
            for _ in range(2):
                with self.assertRaises(JobError):self.launcher.start()
                self.assertEqual('IDLE',self.launcher.state())
            self.assertEqual(2,popen.call_count)
        self.assertEqual(2,len(list(self.launcher.output.glob('local-start-failed-*.json'))))
        self.assertFalse((self.launcher.output/'launch-intent.json').exists())

    def test_uncertain_previous_start_is_not_replayed(self):
        self.launcher.started=True
        with patch.object(prepared.subprocess,'Popen') as popen:
            with self.assertRaises(JobError):self.launcher.start()
        popen.assert_not_called()

    def test_repeated_clock_values_cannot_replace_previous_local_failures(self):
        with patch.object(prepared.time,'time_ns',return_value=123), \
             patch.object(prepared,'controller_command',side_effect=[['/synthetic/first'],['/synthetic/second']]), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=OSError('not started')):
            with self.assertRaises(JobError):self.launcher.start()
            originals={p:p.read_bytes() for p in self.launcher.output.glob('local-start-failed-*.json')}
            with self.assertRaises(JobError):self.launcher.start()
        self.assertEqual(2,len(list(self.launcher.output.glob('local-start-failed-*.json'))))
        self.assertTrue(all(p.read_bytes()==raw for p,raw in originals.items()))

    def test_failed_retention_before_process_creation_can_resume_after_storage_recovers(self):
        with patch.object(prepared,'controller_command',return_value=['/synthetic/absent']), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=OSError('not started')) as popen:
            with patch.object(prepared.os,'rename',side_effect=OSError('storage unavailable')), \
                 patch.object(prepared,'_publish_create_only',side_effect=OSError('storage unavailable')):
                with self.assertRaises((JobError,OSError)):self.launcher.start()
            self.assertEqual(1,popen.call_count)
            original=(self.launcher.output/'launch-intent.json').read_bytes()
            self.assertEqual('IDLE',self.launcher.state())
            self.assertFalse((self.launcher.output/'launch-intent.json').exists())
            self.assertIn(original,[p.read_bytes() for p in self.launcher.output.glob('local-start-failed-*.json')])
            with self.assertRaises(JobError):self.launcher.start()
            self.assertEqual(2,popen.call_count)

    def test_failure_publication_collision_preserves_existing_bytes(self):
        self.launcher._commit_intent(['/synthetic/undelivered'])
        original=(self.launcher.output/'launch-intent.json').read_bytes()
        collision=self.launcher.output/('local-start-failed-'+('aa'*16)+'.json')
        collision.write_bytes(b'older retained failure')
        with patch.object(prepared.os,'urandom',side_effect=[bytes.fromhex('aa'*16),bytes.fromhex('bb'*16)]):
            self.launcher._retain_unstarted_intent('local-start-failed')
        self.assertEqual(b'older retained failure',collision.read_bytes())
        self.assertEqual(original,(self.launcher.output/('local-start-failed-'+('bb'*16)+'.json')).read_bytes())
        self.assertEqual('IDLE',self.launcher.state())

    def test_initial_retention_metadata_failure_is_retryable_without_delivery(self):
        original_stat=os.stat
        def unavailable(path,*args,**kwargs):
            if path=='launch-intent.json':raise OSError('temporary metadata outage')
            return original_stat(path,*args,**kwargs)
        with patch.object(prepared,'controller_command',return_value=['/synthetic/absent']), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=OSError('not started')) as popen:
            with patch.object(prepared.os,'stat',side_effect=unavailable):
                with self.assertRaises((JobError,OSError)):self.launcher.start()
                with self.assertRaises(JobError):self.launcher.state()
            self.assertEqual('IDLE',self.launcher.state())
            with self.assertRaises(JobError):self.launcher.start()
            self.assertEqual(2,popen.call_count)
        self.assertEqual(2,len(list(self.launcher.output.glob('local-start-failed-*.json'))))

    def test_retention_cannot_adopt_intent_replaced_before_first_identity_lookup(self):
        self.launcher._commit_intent(['/synthetic/undelivered'])
        path=self.launcher.output/'launch-intent.json';saved=self.launcher.output/'original.json'
        path.rename(saved);path.write_bytes(b'foreign intent')
        with self.assertRaises(JobError):self.launcher._retain_unstarted_intent('local-start-failed')
        with patch.object(prepared.subprocess,'Popen') as popen:
            with self.assertRaises(JobError):self.launcher.state()
            with self.assertRaises(JobError):self.launcher.start()
        popen.assert_not_called()
        self.assertEqual(b'foreign intent',path.read_bytes())

    def test_descriptor_identity_read_failure_retains_original_handle_until_recovery(self):
        original_fstat=os.fstat
        def unavailable(fd):
            if os.readlink('/proc/self/fd/'+str(fd)).endswith('/launch-intent.json'):
                raise OSError('temporary descriptor metadata outage')
            return original_fstat(fd)
        with patch.object(prepared.os,'fstat',side_effect=unavailable):
            with self.assertRaises(JobError):self.launcher._commit_intent(['/synthetic/undelivered'])
        retained_fd=self.launcher.intent_fd
        self.assertEqual('IDLE',self.launcher.state())
        with self.assertRaises(OSError):os.fstat(retained_fd)
        self.assertEqual(1,len(list(self.launcher.output.glob('local-intent-failed-*.json'))))

    def test_failed_retention_sync_reuses_same_record_without_redelivery(self):
        self.launcher._commit_intent(['/synthetic/undelivered'])
        with patch.object(prepared.os,'fsync',side_effect=OSError('directory sync unavailable')):
            with self.assertRaises(JobError):self.launcher._retain_unstarted_intent('local-authorization-expired')
        retained={p:p.read_bytes() for p in self.launcher.output.iterdir()}
        self.assertFalse((self.launcher.output/'launch-intent.json').exists())
        with patch.object(prepared,'_publish_create_only') as publish,patch.object(prepared.subprocess,'Popen') as popen:
            self.assertEqual('IDLE',self.launcher.state())
            self.assertEqual('IDLE',self.launcher.state())
        publish.assert_not_called();popen.assert_not_called()
        self.assertEqual(retained,{p:p.read_bytes() for p in self.launcher.output.iterdir()})

    def test_failure_retention_never_moves_a_replaced_intent(self):
        self.launcher._commit_intent(['/synthetic/undelivered'])
        with patch.object(prepared,'_publish_create_only',side_effect=OSError('storage unavailable')):
            with self.assertRaises(JobError):self.launcher._retain_unstarted_intent('local-start-failed')
        path=self.launcher.output/'launch-intent.json';saved=self.launcher.output/'original-intent.json'
        path.rename(saved);path.write_bytes(b'foreign intent')
        with patch.object(prepared.subprocess,'Popen') as popen:
            with self.assertRaises(JobError):self.launcher.state()
            with self.assertRaises(JobError):self.launcher.start()
        popen.assert_not_called()
        self.assertEqual(b'foreign intent',path.read_bytes())
        self.assertEqual([],list(self.launcher.output.glob('local-start-failed-*.json')))

    def test_capture_thread_start_failure_precedes_process_delivery_and_allows_retry(self):
        create=subprocess.Popen
        command=[sys.executable,'-c',"print('completed once after local failures')"]
        with patch.object(prepared,'controller_command',return_value=command), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=create) as popen:
            with patch.object(prepared.threading.Thread,'start',side_effect=RuntimeError('no thread resources')):
                for _ in range(2):
                    with self.assertRaises(JobError):self.launcher.start()
                    self.assertEqual('IDLE',self.launcher.state())
                popen.assert_not_called()
            self.assertFalse((self.launcher.output/'launch-intent.json').exists())
            self.launcher.start()
            self.assertTrue(self.launcher.complete.wait(3))
            self.assertEqual('EXITED',self.launcher.start())
            popen.assert_called_once()
        self.assertEqual(2,len(list(self.launcher.output.glob('local-start-failed-*.json'))))
        self.assertEqual(0,self.launcher.result['returncode'])
        self.assertEqual(b'completed once after local failures\n',
                         bytes.fromhex(self.launcher.result['streams']['stdout']['hex']))

    def test_started_capture_worker_cannot_adopt_a_later_attempt_after_start_raises(self):
        original_start=threading.Thread.start
        workers=[]
        def interrupted_start(worker):
            workers.append(worker)
            original_start(worker)
            raise RuntimeError('interrupted after native thread start')
        with patch.object(prepared,'controller_command',return_value=['/synthetic/absent']), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.threading.Thread,'start',new=interrupted_start), \
             patch.object(self.launcher,'_capture') as capture, \
             patch.object(prepared.subprocess,'Popen') as popen:
            try:
                with self.assertRaises(JobError):self.launcher.start()
            finally:
                for worker in workers:worker.join(timeout=1)
            self.assertTrue(all(not worker.is_alive() for worker in workers))
            popen.assert_not_called()
            capture.assert_not_called()
        self.assertEqual('IDLE',self.launcher.state())

    def test_capture_drains_large_real_dual_streams_without_additional_threads(self):
        process=subprocess.Popen([sys.executable,'-c',
            "import os;os.write(1,b'x'*100000);os.write(2,b'y'*100000)"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None:process.kill()
            process.wait(timeout=3)
            for stream in (process.stdout,process.stderr):
                if not stream.closed:stream.close()
        self.addCleanup(cleanup)
        self.launcher.process=process
        self.launcher.started=True
        with patch.object(prepared.threading.Thread,'start',side_effect=RuntimeError('no thread resources')):
            self.launcher._capture()
        self.assertEqual('EXITED',self.launcher.state())
        self.assertTrue(self.launcher.result['streams_eof'])
        for name,byte in [('stdout',b'x'),('stderr',b'y')]:
            stream=self.launcher.result['streams'][name]
            self.assertEqual(100000,stream['total_bytes'])
            self.assertEqual(byte*32768,bytes.fromhex(stream['hex']))
            self.assertTrue(stream['truncated'])

    def test_waiter_exit_does_not_finish_capture_while_descendant_holds_pipes(self):
        process=subprocess.Popen([sys.executable,'-c',
            "import os\nif os.fork()==0:\n os.read(0,1)\n os._exit(0)\nos._exit(0)"],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.launcher.process=process
        self.launcher.started=True
        worker=threading.Thread(target=self.launcher._capture,daemon=True)
        try:
            self.assertEqual(0,process.wait(timeout=3))
            worker.start()
            self.assertFalse(self.launcher.complete.wait(.05))
            self.assertEqual('RUNNING',self.launcher.state())
            self.assertFalse((self.launcher.output/'finished.json').exists())
        finally:
            process.stdin.close()
            if worker.ident is not None:worker.join(timeout=3)
            if process.poll() is None:process.kill()
            process.wait(timeout=3)
            for stream in (process.stdout,process.stderr):
                if not stream.closed:stream.close()
        self.assertFalse(worker.is_alive())
        self.assertEqual('EXITED',self.launcher.state())
        self.assertTrue(self.launcher.result['streams_eof'])

    def test_capture_read_failure_is_unknown_and_never_an_exit_or_second_launch(self):
        process=subprocess.Popen([sys.executable,'-c',"print('retained')"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        process.wait(timeout=3)
        self.launcher.process=process
        self.launcher.started=True
        with patch.object(prepared.os,'read',side_effect=OSError('pipe failure')):
            self.launcher._capture()
        self.assertFalse(self.launcher.complete.is_set())
        self.assertFalse((self.launcher.output/'finished.json').exists())
        with patch.object(prepared.subprocess,'Popen') as popen:
            with self.assertRaises(JobError):self.launcher.state()
            with self.assertRaises(JobError):self.launcher.start()
            popen.assert_not_called()

    def completed_child(self):
        process=subprocess.Popen([sys.executable,'-c',"print('original exit proof')"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None:process.kill()
            process.wait(timeout=3)
            for stream in (process.stdout,process.stderr):
                if not stream.closed:stream.close()
        self.addCleanup(cleanup)
        self.launcher.process=process
        self.launcher.started=True
        return process

    def test_exit_record_open_failure_retries_publication_without_recapturing_or_launching(self):
        process=self.completed_child()
        with patch.object(prepared.task_service,'save',side_effect=OSError('record open unavailable')):
            self.launcher._capture()
        self.assertEqual(0,process.returncode)
        self.assertTrue(self.launcher.complete.is_set())
        original=self.launcher.result
        with patch.object(prepared.subprocess,'Popen') as spawn, \
             patch.object(self.launcher,'_capture') as capture:
            self.assertEqual('EXITED',self.launcher.state())
            self.assertEqual('EXITED',self.launcher.start())
            spawn.assert_not_called()
            capture.assert_not_called()
        self.assertIs(original,self.launcher.result)
        self.assertEqual(original,json.loads((self.launcher.output/'finished.json').read_bytes()))

    def test_partial_exit_record_is_retained_without_publishing_a_truncated_completion(self):
        self.completed_child()
        write=os.write
        calls=0
        def interrupted(fd,raw):
            nonlocal calls
            calls+=1
            if calls==1:return write(fd,raw[:19])
            raise OSError('storage interrupted after partial write')
        with patch.object(prepared.os,'write',side_effect=interrupted):
            self.launcher._capture()
        partials={p:p.read_bytes() for p in self.launcher.output.iterdir()}
        self.assertEqual(1,len(partials))
        self.assertEqual([19],[len(raw) for raw in partials.values()])
        self.assertFalse((self.launcher.output/'finished.json').exists())
        self.assertEqual('EXITED',self.launcher.state())
        self.assertEqual(partials,{p:p.read_bytes() for p in partials})
        self.assertEqual(self.launcher.result,json.loads((self.launcher.output/'finished.json').read_bytes()))

    def test_published_exit_record_sync_failure_reuses_same_inode_and_result(self):
        self.completed_child()
        resident=ResidentService.__new__(ResidentService)
        resident.boot='test-boot'
        resident.launchers={'original-attempt':self.launcher}
        record=dict(output=str(self.launcher.output),attempt='original-attempt',boot_id=resident.boot)
        self.enterContext(patch('admin.local_hand_system_manager.resident_service.load',
                               side_effect=lambda path:json.loads(Path(path).read_bytes())))
        fsync=os.fsync
        def interrupted(fd):
            if fd==self.launcher.directory and (self.launcher.output/'finished.json').exists():
                raise OSError('completion directory sync failed')
            fsync(fd)
        with patch.object(prepared.os,'fsync',side_effect=interrupted):
            self.launcher._capture()
            with self.assertRaises(JobError):self.launcher.state()
            with self.assertRaises(JobError):resident.execution_state(record)
        path=self.launcher.output/'finished.json'
        identity=path.stat().st_ino
        original=path.read_bytes()
        with patch.object(prepared.task_service,'save') as save:
            self.assertEqual('EXITED',resident.execution_state(record))
            save.assert_not_called()
        self.assertEqual(identity,path.stat().st_ino)
        self.assertEqual(original,path.read_bytes())

    def test_conflicting_exit_record_is_never_replaced_or_treated_as_this_result(self):
        self.completed_child()
        path=self.launcher.output/'finished.json'
        original=b'{"returncode":7,"streams_eof":true}\n'
        path.write_bytes(original)
        path.chmod(0o600)
        self.launcher._capture()
        with patch.object(prepared.subprocess,'Popen') as spawn:
            for _ in range(2):
                with self.assertRaises(JobError):self.launcher.start()
            spawn.assert_not_called()
        self.assertEqual(original,path.read_bytes())

    def test_completion_cannot_follow_aliases_or_accept_shared_or_public_records(self):
        self.completed_child()
        with patch.object(prepared.task_service,'save',side_effect=OSError('not published yet')):
            self.launcher._capture()
        raw=prepared.q._canonical(self.launcher.result,2*1024**2)+b'\n'
        path=self.launcher.output/'finished.json'
        retained=self.launcher.output/'retained.json'
        retained.write_bytes(raw)
        retained.chmod(0o600)
        for kind in ('symlink','hardlink','fifo','public'):
            with self.subTest(kind=kind):
                if kind=='symlink':path.symlink_to(retained)
                elif kind=='hardlink':os.link(retained,path)
                elif kind=='fifo':os.mkfifo(path,0o600)
                else:
                    path.write_bytes(raw)
                    path.chmod(0o644)
                try:
                    with self.assertRaises(JobError):self.launcher.state()
                    self.assertEqual(raw,retained.read_bytes())
                finally:path.unlink()
        self.assertEqual('EXITED',self.launcher.state())

    def test_completion_replacement_during_sync_keeps_original_proof_and_rejects_entry(self):
        self.completed_child()
        fsync=os.fsync
        path=self.launcher.output/'finished.json'
        archived=self.launcher.output/'original-finished.json'
        foreign=b'{"foreign":true}\n'
        def replace(fd):
            fsync(fd)
            if fd==self.launcher.directory and path.exists() and not archived.exists():
                path.rename(archived)
                path.write_bytes(foreign)
                path.chmod(0o600)
        with patch.object(prepared.os,'fsync',side_effect=replace):
            self.launcher._capture()
        self.assertTrue(self.launcher.complete.is_set())
        self.assertEqual(self.launcher.result,json.loads(archived.read_bytes()))
        with self.assertRaises(JobError):self.launcher.state()
        self.assertEqual(foreign,path.read_bytes())

    def test_intent_commit_failure_before_popen_does_not_block_local_retry(self):
        fsync=os.fsync
        interrupted_once=False
        def interrupted(fd):
            nonlocal interrupted_once
            if fd==self.launcher.directory and not interrupted_once:
                interrupted_once=True
                raise OSError('directory sync failed before process creation')
            fsync(fd)
        with patch.object(prepared,'controller_command',return_value=['/synthetic/absent']), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=OSError('not started')) as popen:
            with patch.object(prepared.os,'fsync',side_effect=interrupted):
                with self.assertRaises(JobError):self.launcher.start()
            popen.assert_not_called()
            with self.assertRaises(JobError):self.launcher.start()
            popen.assert_called_once()
        self.assertEqual('IDLE',self.launcher.state())
        self.assertEqual(1,len(list(self.launcher.output.glob('local-intent-failed-*.json'))))

    def test_intent_open_error_does_not_claim_ownership_of_an_existing_record(self):
        original=b'{"prior":"unknown effects"}'
        (self.launcher.output/'launch-intent.json').write_bytes(original)
        with patch.object(prepared.os,'open',side_effect=OSError('cannot inspect storage')):
            with self.assertRaises(JobError):self.launcher._commit_intent(['/synthetic'])
        self.assertEqual(original,(self.launcher.output/'launch-intent.json').read_bytes())
        self.assertEqual([],list(self.launcher.output.glob('local-intent-failed-*.json')))

    def test_running_controller_is_reused_without_second_popen(self):
        self.launcher.process=Mock()
        self.launcher.started=True
        with patch.object(prepared.subprocess,'Popen') as popen:
            self.assertEqual('RUNNING',self.launcher.start())
        popen.assert_not_called()

    def test_real_child_starts_only_after_intent_commit_and_is_not_restarted(self):
        popen=subprocess.Popen
        command=[sys.executable,'-c',"print('completed once')"]
        def create(argv,**kwargs):
            import json
            intent=json.loads((self.launcher.output/'launch-intent.json').read_text())
            self.assertEqual(command,intent['command'])
            self.assertEqual(self.launcher.launch['request']['operation_id'],intent['operation_id'])
            return popen(argv,**kwargs)
        with patch.object(prepared,'controller_command',return_value=command), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen',side_effect=create) as spawn:
            self.launcher.start()
            self.assertTrue(self.launcher.complete.wait(3))
            self.assertEqual('EXITED',self.launcher.start())
            spawn.assert_called_once()
        self.assertEqual(0,self.launcher.result['returncode'])
        self.assertTrue(self.launcher.result['streams_eof'])

    def test_intent_appearing_after_launcher_open_is_preserved_and_not_replayed(self):
        original=b'{"prior":"unknown effects"}'
        (self.launcher.output/'launch-intent.json').write_bytes(original)
        with patch.object(prepared,'controller_command',return_value=['/synthetic/absent']), \
             patch.object(prepared.budget,'current_clock',return_value={'boot_id':'test-boot'}), \
             patch.object(prepared.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)), \
             patch.object(prepared.subprocess,'Popen') as popen:
            for _ in range(2):
                with self.assertRaises(JobError):self.launcher.start()
        popen.assert_not_called()
        self.assertEqual(original,(self.launcher.output/'launch-intent.json').read_bytes())
        self.assertEqual([],list(self.launcher.output.glob('local-*-failed-*.json')))

    def test_exit_requires_reaped_child_and_real_stdout_stderr_eof(self):
        process=subprocess.Popen([sys.executable,'-c',"import sys;print('retained');print('error record',file=sys.stderr)"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(lambda:process.poll() is None and process.kill())
        self.launcher.process=process
        self.launcher.started=True
        self.launcher._capture()
        self.assertTrue(self.launcher.complete.is_set())
        self.assertEqual(0,self.launcher.result['returncode'])
        self.assertTrue(self.launcher.result['streams_eof'])
        self.assertEqual(b'retained\n',bytes.fromhex(self.launcher.result['streams']['stdout']['hex']))
        self.assertEqual('EXITED',self.launcher.state())
        self.assertTrue((self.launcher.output/'finished.json').exists())
        self.assertEqual('EXITED',self.launcher.start())
