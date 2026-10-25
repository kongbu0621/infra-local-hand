"""Durable admission and original-attempt continuation, using real files/locks.

These tests do not configure systemd or change an installed deployment. Systemd
observation is modeled only where a local test cannot own a real service unit.
"""
import copy
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import Mock, patch

from local_hand_jobs.contract import JobError, Principal
from local_hand_jobs import maintenance
from admin.local_hand_system_manager import prepared_service, resident_service
import test_local_hand_prepared_service as fixed_tests


def fixture_loaded(deployment='a', configuration='b'):
    return dict(node_id='test-node',deployment_digest=deployment*64,configuration_digest=configuration*64,
                payload_digest='c'*64,boot_id='test-boot',component='manager')


class GateTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory();self.addCleanup(root.cleanup)
        self.root=Path(root.name)
        self.gate=maintenance.MaintenanceGate(self.root,'test-node',owner_uid=os.getuid())
        self.loaded=fixture_loaded()
        self.gate.initialize('a'*64,'trusted-bootstrap',bootstrap=True)

    def receipt(self, *, attempt='prepare-1'):
        return self.gate.accept('prepare','task-one',attempt,dict(input='fixed'),self.loaded)

    def prepared(self,loaded=None,attempt='prepare-1'):
        return maintenance.prepared_binding(loaded or self.loaded,operation_id='task-one',attempt_id=attempt,
                                            request_digest='d'*64,launch=dict(fixed='resources'))

    def execute(self,prepared,loaded=None,attempt='execute-1'):
        return self.gate.accept('execute','task-one',attempt,dict(prepared=prepared),loaded or self.loaded,prepared=prepared)

    def test_missing_corrupt_and_unknown_schema_are_never_open(self):
        original=(self.root/'gate.json').read_bytes()
        for raw in (None,b'{',b'{"schema":"future"}'):
            if raw is None:(self.root/'gate.json').unlink()
            else:(self.root/'gate.json').write_bytes(raw)
            with self.assertRaises(JobError) as error:self.receipt()
            self.assertEqual('MAINTENANCE_UNKNOWN',error.exception.code)
            if raw is not None:
                with self.assertRaises(JobError):self.gate.initialize('a'*64,'trusted-bootstrap',bootstrap=True)
            (self.root/'gate.json').write_bytes(original)
            (self.root/'gate.json').chmod(0o600)
        with self.assertRaises(JobError):self.gate.initialize('a'*64,'bootstrap-without-approval')

    def test_handoff_release_lost_response_and_old_command_are_fenced(self):
        before=self.gate.snapshot()
        a=self.gate.close('operation-a',expected=before)
        self.assertEqual(a,self.gate.close('operation-a',expected=before))
        b=self.gate.handoff('operation-a','operation-b',expected=a)
        self.assertEqual(b,self.gate.handoff('operation-a','operation-b',expected=a))
        with self.assertRaises(JobError):self.gate.release('operation-a','old-release','a'*64)
        with self.assertRaises(JobError):self.gate.handoff('operation-b','operation-a')
        result=self.gate.release('operation-b','durable-b','a'*64,expected=b)
        restarted=maintenance.MaintenanceGate(self.root,'test-node',owner_uid=os.getuid())
        self.assertEqual(result,restarted.release('operation-b','durable-b','a'*64,expected=b))
        self.assertEqual('OPEN',restarted.snapshot()['state'])
        with self.assertRaises(JobError):restarted.close('operation-a')
        with self.assertRaises(JobError):restarted.close('operation-b')
        with self.assertRaises(JobError):restarted.close('operation-c',expected=a)

    def test_accept_commits_before_concurrent_close_can_complete(self):
        # The child pauses during its *real* locked publication. Parent closes
        # concurrently; close cannot miss this already-accepted responsibility.
        program='''import json,os,sys
sys.path.insert(0,sys.argv[3])
from local_hand_jobs.maintenance import MaintenanceGate
class Paused(MaintenanceGate):
 def _write(self,fd,value):
  print('locked',flush=True);sys.stdin.readline();super()._write(fd,value)
gate=Paused(sys.argv[1],'test-node',owner_uid=os.getuid())
proof=json.loads(sys.argv[2])
gate.accept('prepare','task-one','process-attempt',{'input':'fixed'},proof)
print('accepted',flush=True)
'''
        # pytest's configured pythonpath affects this interpreter, not its
        # children. Bind the actual loaded installation, including when this
        # test runs against an independent wheel or source projection.
        package_root=str(Path(maintenance.__file__).resolve().parents[1])
        environment={key:value for key,value in os.environ.items() if key != 'PYTHONPATH'}
        child=subprocess.Popen([sys.executable,'-B','-c',program,str(self.root),json.dumps(self.loaded),package_root],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                               env=environment)
        done=threading.Event();results=[];errors=[];worker=None
        def close():
            try:results.append(self.gate.close('deploy'))
            except BaseException as error:errors.append(error)
            finally:done.set()
        try:
            self.assertTrue(select.select([child.stdout],[],[],3)[0], 'child did not reach locked publication')
            self.assertEqual('locked',child.stdout.readline().strip())
            worker=threading.Thread(target=close,daemon=True);worker.start()
            self.assertFalse(done.wait(.1))
            output,error=child.communicate('\n',timeout=3)
            self.assertEqual(0,child.returncode,error)
            self.assertEqual('accepted',output.strip())
            self.assertTrue(done.wait(3));worker.join(timeout=3)
            self.assertEqual([],errors)
            self.assertEqual('CLOSED',results[0]['state'])
            self.assertEqual(1,len(self.gate.active()))
            with self.assertRaises(JobError) as denied:self.receipt(attempt='later')
            self.assertEqual('MAINTENANCE',denied.exception.code)
        finally:
            # Kill first so an early assertion also releases the child's real
            # flock before joining the concurrent closer; reap and close every
            # pipe even when communicate/another assertion fails.
            if child.poll() is None:child.kill()
            try:child.wait(timeout=3)
            finally:
                for stream in (child.stdin,child.stdout,child.stderr):stream.close()
                if worker is not None:
                    worker.join(timeout=3)
                    self.assertFalse(worker.is_alive(), 'concurrent closer did not exit')

    def test_accepted_preparation_dispatches_after_close_but_cannot_first_execute(self):
        receipt=self.receipt();self.gate.close('deploy')
        self.gate.dispatch(receipt)
        child=subprocess.run([sys.executable,'-c',"print('original accepted work')"],capture_output=True,check=True)
        self.assertEqual(b'original accepted work\n',child.stdout)
        self.gate.finish(receipt,dict(process_exited=True,writers_stopped=True))
        self.assertEqual([],self.gate.active())
        with self.assertRaises(JobError) as denied:self.execute(self.prepared())
        self.assertEqual('MAINTENANCE',denied.exception.code)

    def test_unknown_dispatch_is_not_replayed_or_rebound(self):
        receipt=self.receipt();self.gate.dispatch(receipt)
        restarted=maintenance.MaintenanceGate(self.root,'test-node',owner_uid=os.getuid())
        self.assertEqual('DISPATCHING',restarted.active()[0]['state'])
        with self.assertRaises(JobError):restarted.dispatch(receipt)
        wrong=dict(receipt,attempt_id='other-attempt')
        with self.assertRaises(JobError):restarted.finish(wrong,dict(never_dispatched=True))
        with self.assertRaises(JobError):restarted.finish(receipt,dict(process_exited=True))
        self.assertEqual(1,len(restarted.active()))

    def test_local_failure_ends_one_attempt_and_next_attempt_needs_current_open(self):
        receipt=self.receipt();self.gate.close('deploy')
        self.gate.finish(receipt,dict(never_dispatched=True))
        with self.assertRaises(JobError):self.gate.dispatch(receipt)
        with self.assertRaises(JobError):self.receipt(attempt='prepare-2')
        self.gate.release('deploy','abort-no-change','a'*64)
        retry=self.receipt(attempt='prepare-2')
        self.assertNotEqual(receipt['id'],retry['id'])
        with self.assertRaises(JobError):self.receipt()

    def test_no_change_abort_can_release_while_original_business_is_active(self):
        receipt=self.execute(self.prepared());self.gate.dispatch(receipt)
        self.gate.close('deploy')
        released=self.gate.release('deploy','aborted-no-change','a'*64)
        self.assertEqual('OPEN',released['state'])
        self.assertEqual('DISPATCHING',self.gate.active()[0]['state'])

    def test_first_execute_requires_exact_same_or_explicit_target_compatibility(self):
        old=self.prepared();new=fixture_loaded('e','f')
        self.gate.close('deploy');self.gate.release('deploy','commit','e'*64)
        with self.assertRaises(JobError) as denied:self.execute(old,new)
        self.assertEqual('STALE_DEPLOYMENT',denied.exception.code)
        self.gate.close('fix-compatibility')
        self.gate.authorize_compatibility('fix-compatibility',old,'e'*64,target_loaded=new)
        self.gate.release('fix-compatibility','confirmed','e'*64)
        accepted=self.execute(old,new)
        self.assertEqual(old,accepted['binding']['prepared'])
        for changed in (dict(old,attempt_id='other'),dict(old,resource_digest='0'*64)):
            with self.assertRaises(JobError):self.execute(changed,new,attempt=uuid.uuid4().hex)
        # New preparations were never in the deployment's retained snapshot.
        fresh=self.prepared(new,'prepare-new')
        self.assertEqual('ACCEPTED',self.execute(fresh,new,attempt='new-execute')['state'])
        with self.assertRaises(JobError):self.execute(fresh,self.loaded,attempt='stale-process')

    def test_expired_authority_cannot_accept_or_dispatch_after_wait(self):
        expiry=int(time.time())-1
        principal=Principal('owner',frozenset({'lh:submit'}),expires_at=expiry)
        with self.assertRaises(JobError):
            self.gate.accept('prepare','task-one','new',{},self.loaded,authorization=principal)
        receipt=self.receipt()
        with self.assertRaises(JobError):self.gate.dispatch(receipt,authorization=principal)
        self.assertEqual('ACCEPTED',self.gate.active()[0]['state'])

    def test_published_close_with_lost_directory_sync_is_observed_without_reclosing(self):
        sync=os.fsync;failed=[]
        def lose_reply(fd):
            import stat
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not failed:
                failed.append(True);raise OSError('synthetic directory sync outage')
            return sync(fd)
        with patch.object(maintenance.os,'fsync',side_effect=lose_reply):
            with self.assertRaises(JobError):self.gate.close('deploy')
        actual=self.gate.snapshot()
        self.assertEqual('CLOSED',actual['state'])
        with patch.object(maintenance.os,'fsync',wraps=sync) as sync_again:
            self.assertEqual(actual,self.gate.close('deploy'))
            self.assertEqual(2,sync_again.call_count)

    def test_marker_symlink_and_unprotected_bytes_are_rejected(self):
        path=self.root/'gate.json';data=path.read_bytes();path.unlink()
        outside=self.root/'other.json';outside.write_bytes(data);outside.chmod(0o600)
        path.symlink_to(outside)
        with self.assertRaises(JobError):self.gate.snapshot()
        path.unlink();path.write_bytes(data);path.chmod(0o644)
        with self.assertRaises(JobError):self.gate.snapshot()

    def test_corrupt_closed_responsibility_cannot_look_quiescent(self):
        receipt=self.receipt();self.gate.finish(receipt,dict(never_dispatched=True))
        original=self.gate.snapshot()
        for proof in (None,{},dict(process_exited=True,writers_stopped=False)):
            value=copy.deepcopy(original);value['responsibilities'][receipt['id']]['proof']=proof
            (self.root/'gate.json').write_text(json.dumps(value))
            with self.assertRaises(JobError) as denied:self.gate.active()
            self.assertEqual('MAINTENANCE_UNKNOWN',denied.exception.code)


class RuntimeGateTests(unittest.TestCase):
    setUp=GateTests.setUp
    def fixed(self):
        fixture=fixed_tests.FixedLaunchTests('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        item=fixture.launcher
        item.launch['request']['request_digest']='d'*64
        item.launch['controller_envelope']={'controller':{'unit':'synthetic.service'}}
        item.maintenance_gate=self.gate;item.loaded_deployment=self.loaded
        item.maintenance_admission=None
        item.maintenance_prepared=maintenance.prepared_binding(self.loaded,
            operation_id=item.launch['request']['operation_id'],attempt_id='original-preparation',
            request_digest='d'*64,launch=item.launch)
        return item

    def execution_patches(self,item,command):
        from contextlib import ExitStack
        stack=ExitStack()
        stack.enter_context(patch.object(prepared_service,'controller_command',return_value=command))
        stack.enter_context(patch.object(prepared_service.budget,'current_clock',return_value={'boot_id':'test-boot'}))
        stack.enter_context(patch.object(prepared_service.q2_config,'executable',side_effect=lambda _:os.open('/dev/null',os.O_RDONLY)))
        return stack

    def test_real_controller_can_finish_after_close_and_status_remains_readable(self):
        item=self.fixed();commit=item._commit_intent
        def close_before_dispatch(command):
            self.gate.close('deploy');commit(command)
        with self.execution_patches(item,[sys.executable,'-c',"print('accepted controller')"]), \
             patch.object(item,'_commit_intent',side_effect=close_before_dispatch):
            item.start();self.assertTrue(item.complete.wait(3))
            self.assertEqual('EXITED',item.state())
        self.assertEqual([],self.gate.active())
        self.assertEqual('CLOSED',self.gate.snapshot()['state'])
        (self.root/'gate.json').unlink()
        self.assertEqual('EXITED',item.state()) # Query is not new admission.

    def test_fixed_local_failure_retries_only_after_fresh_admission(self):
        item=self.fixed()
        with self.execution_patches(item,['/not-delivered']), \
             patch.object(prepared_service.subprocess,'Popen',side_effect=OSError('local')):
            with self.assertRaises(JobError):item.start()
        old=list(self.gate.snapshot()['responsibilities'].values())
        self.assertEqual(1,len(old));self.assertEqual('CLOSED',old[0]['state'])
        self.gate.close('deploy')
        with self.execution_patches(item,[sys.executable,'-c','pass']), \
             patch.object(prepared_service.subprocess,'Popen') as popen:
            with self.assertRaises(JobError) as denied:item.start()
            self.assertEqual('MAINTENANCE',denied.exception.code);popen.assert_not_called()
        self.gate.release('deploy','abort','a'*64)
        with self.execution_patches(item,[sys.executable,'-c','pass']):
            item.start();self.assertTrue(item.complete.wait(3));self.assertEqual('EXITED',item.state())
        records=list(self.gate.snapshot()['responsibilities'].values())
        self.assertEqual(2,len(records));self.assertEqual(2,len({r['attempt_id'] for r in records}))

    def test_fixed_rejects_changed_prepared_resources_before_process_creation(self):
        item=self.fixed();item.launch['policy']['broker_root']='/changed-resource'
        with patch.object(prepared_service.subprocess,'Popen') as popen:
            with self.assertRaises(JobError) as denied:item.start()
            self.assertEqual('STALE_DEPLOYMENT',denied.exception.code);popen.assert_not_called()
        self.assertEqual([],self.gate.active())

    def resident(self):
        private=self.root/'private';private.mkdir();catalog=self.root/'catalog';catalog.mkdir()
        config=dict(private_root=str(private),catalog=str(catalog),profile_ref='fixture',first_project_id=15000,
                    last_project_id=20000,max_tasks=32,principals=['owner'],
                    installation={'installed':{'payload_digest':'c'*64}},
                    maintenance=dict(schema=maintenance.CONFIG_SCHEMA,directory=str(self.root),node_id='test-node',
                                     deployment_digest='a'*64,startup_descriptor=str(self.root/'startup.json')))
        with patch.object(resident_service.maintenance,'from_config',return_value=self.gate), \
             patch.object(resident_service.budget,'current_clock',return_value={'boot_id':'test-boot'}):
            service=resident_service.ResidentService(config)
        return service

    def test_resident_closed_prepare_has_no_attempt_or_thread(self):
        service=self.resident()
        request=dict(action='prepare',operation_id=str(uuid.uuid4()),kind='host.inspect',profile_ref='fixture',principal_id='owner')
        self.gate.close('deploy')
        with patch.object(resident_service.threading,'Thread') as worker:
            with self.assertRaises(JobError) as denied:service.call(request)
            self.assertEqual('MAINTENANCE',denied.exception.code);worker.assert_not_called()
        self.assertEqual([],list(service.root.iterdir()))
        self.assertEqual('CLOSED',service.call(dict(action='deployment_status',principal_id='owner'))['marker']['state'])

    def test_thread_start_failure_after_native_creation_cannot_dispatch(self):
        service=self.resident()
        request=dict(action='prepare',operation_id=str(uuid.uuid4()),kind='host.inspect',profile_ref='fixture',principal_id='owner')
        native=threading.Thread.start
        def failed(worker):
            native(worker)
            raise RuntimeError('native thread created but start acknowledgment failed')
        with patch.object(threading.Thread,'start',new=failed), \
             patch.object(service,'_prepare_worker') as dispatch:
            with self.assertRaises(RuntimeError):service.call(request)
            service.worker.join(2)
            self.assertFalse(service.worker.is_alive())
            dispatch.assert_not_called()
        self.assertEqual([],self.gate.active())
        duty=next(iter(self.gate.snapshot()['responsibilities'].values()))
        self.assertEqual({'never_dispatched':True},duty['proof'])

    def test_recovery_closes_only_undispatched_original_service_responsibilities(self):
        service=self.resident()
        receipt=self.gate.accept('prepare','task-one','lost-before-current-json',
            dict(private_root=str(service.root)),service.loaded_deployment)
        unknown=self.gate.accept('prepare','task-two','delivery-unknown',
            dict(private_root=str(service.root)),service.loaded_deployment)
        self.gate.dispatch(unknown)
        foreign=self.gate.accept('prepare','task-three','other-service',
            dict(private_root='/different-service'),service.loaded_deployment)
        self.gate.close('deploy')
        service.recover_undispatched()
        self.assertEqual({unknown['id'],foreign['id']},{item['id'] for item in self.gate.active()})
        self.assertEqual('CLOSED',self.gate.snapshot()['responsibilities'][receipt['id']]['state'])

    def test_loaded_status_is_actual_snapshot_and_instance_without_new_work(self):
        service=self.resident()
        proof=service.deployment_status()['loaded']
        self.assertEqual(os.getpid(),proof['pid'])
        self.assertGreater(proof['start_ticks'],0)
        self.assertIs(False,proof['protocol_ready'])
        self.assertEqual(service.loaded_deployment['configuration_digest'],proof['configuration_digest'])
        self.assertEqual([],self.gate.active())

    def test_deployment_observe_does_not_reconcile_or_write_any_responsibility(self):
        service=self.resident()
        self.gate.accept('prepare','task-one','accepted',dict(private_root=str(service.root)),service.loaded_deployment)
        before=(self.root/'gate.json').read_bytes()
        with patch.object(service,'_launcher',side_effect=AssertionError('read-only must not recover')):
            proof=service.deployment_observe()
        self.assertEqual(os.getpid(),proof['loaded']['pid'])
        self.assertEqual(before,(self.root/'gate.json').read_bytes())
        self.assertEqual(1,len(self.gate.active()))

    def test_unit_inactive_with_pending_job_never_proves_quiescence(self):
        for job in ('99 /org/freedesktop/systemd1/job/99','unknown'):
            with patch.object(prepared_service.subprocess,'run',return_value=Mock(returncode=0,stdout='ActiveState=inactive\nJob='+job+'\n')):
                self.assertFalse(prepared_service.unit_closed('/systemctl','test.service'))
        with patch.object(prepared_service.subprocess,'run',return_value=Mock(returncode=0,stdout='ActiveState=inactive\nJob=0\n')):
            self.assertTrue(prepared_service.unit_closed('/systemctl','test.service'))


if __name__=='__main__':unittest.main()
