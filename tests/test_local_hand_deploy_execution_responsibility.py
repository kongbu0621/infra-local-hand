"""Original execution duties survive launcher reconstruction and pointer retries.

All effects are confined to temporary files and harmless local child processes.
The maintenance Gate and resident current-pointer publications remain real.
"""
import os
import json
from pathlib import Path
import sqlite3
import sys
import time
import unittest
import uuid
from unittest.mock import Mock, patch

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux administrator execution responsibilities')

from admin.local_hand_system_manager import prepared_service as prepared
from admin.local_hand_system_manager import resident_service as resident
from local_hand_jobs import maintenance
from local_hand_jobs.contract import JobError
import test_local_hand_maintenance_gate as fixtures


class ExecutionResponsibilityTests(unittest.TestCase):
    def maintained(self):
        case=fixtures.RuntimeGateTests('runTest')
        self.addCleanup(case.doCleanups);case.setUp()
        service=case.resident();item=case.fixed()
        operation=str(uuid.uuid4())
        attempt=service.root/operation/'attempt-1'
        output=attempt/'execution';output.mkdir(parents=True,mode=0o700)
        item.output=output;item.directory=os.open(output,os.O_RDONLY|os.O_DIRECTORY)
        self.addCleanup(os.close,item.directory)
        request=dict(operation_id=operation,kind='host.inspect',inputs={},request_digest='d'*64,expires_at=1)
        item.launch['request']=request
        item.loaded_deployment=service.loaded_deployment
        item.maintenance_prepared=maintenance.prepared_binding(service.loaded_deployment,
            operation_id=operation,attempt_id=str(attempt),request_digest=request['request_digest'],launch=item.launch)
        record=dict(operation_id=operation,principal_id='owner',state='READY',attempt=str(attempt),
            boot_id=service.boot,output=str(output),request=request,policy_path='/synthetic-policy',
            maintenance_prepared=item.maintenance_prepared)
        service._save(record);service.launchers[str(attempt)]=item
        args=dict(action='prepare',operation_id=operation,kind='host.inspect',profile_ref='fixture',principal_id='owner')
        return case,service,item,record,args

    def fail_without_child(self,case,item):
        with case.execution_patches(item,[str(case.root/'missing-controller')]), \
                patch.object(case.gate,'finish',side_effect=OSError('original closure unavailable')):
            with self.assertRaises((JobError,OSError)):item.start()
        self.assertEqual('DISPATCHING',case.gate.active()[0]['state'])
        self.assertFalse((item.output/'launch-intent.json').exists())
        self.assertFalse((item.output/'started.json').exists())
        self.assertFalse((item.output/'finished.json').exists())
        return item.maintenance_admission

    def reopen(self,case,service,item,record):
        require=prepared.q.require
        def fixture_protection(condition,code):
            if code!='PREPARED_OUTPUT_PROTECTION':require(condition,code)
        with patch.object(prepared.q,'require',side_effect=fixture_protection), \
                patch.object(prepared.q2_config,'pinned_directory',side_effect=lambda _:os.dup(item.directory)):
            reopened=prepared.FixedLauncher(item.launch,item.installation,item.static,item.output,
                maintenance_gate=case.gate,loaded=item.loaded_deployment,prepared=item.maintenance_prepared)
        self.addCleanup(os.close,reopened.directory)
        service.launchers[record['attempt']]=reopened
        return reopened

    def test_reconstructed_dispatching_receipt_remains_unresolved_without_intent(self):
        case,service,item,record,_=self.maintained()
        old=self.fail_without_child(case,item)
        reopened=self.reopen(case,service,item,record)
        before=case.gate.snapshot()['responsibilities'][old['id']]
        with self.assertRaises(JobError) as caught:reopened.state()
        self.assertEqual('IO_UNCERTAIN',caught.exception.code)
        with patch.object(service,'_unit_active',return_value=False):
            self.assertEqual('UNRESOLVED',service.execution_state(record))
        self.assertEqual(before,case.gate.snapshot()['responsibilities'][old['id']])

    def test_stale_current_never_advances_past_reconstructed_unknown_dispatch(self):
        case,service,item,record,args=self.maintained()
        self.fail_without_child(case,item);self.reopen(case,service,item,record)
        current=service.root/record['operation_id']/'current.json'
        retained=current.read_bytes();duties=case.gate.snapshot()['responsibilities']
        failures={path.name:path.read_bytes() for path in item.output.iterdir()}
        with patch.object(service,'_unit_active',return_value=False), \
                patch.object(service,'_prepare_worker') as worker:
            with self.assertRaises(JobError) as caught:service.call(args)
            self.assertEqual('IO_UNCERTAIN',caught.exception.code)
            worker.assert_not_called()
        self.assertEqual(retained,current.read_bytes())
        self.assertEqual(record,service.records[record['operation_id']])
        self.assertEqual([Path(record['attempt'])],list(current.parent.glob('attempt-*')))
        self.assertEqual(duties,case.gate.snapshot()['responsibilities'])
        self.assertEqual(failures,{path.name:path.read_bytes() for path in item.output.iterdir()})

    def test_same_launcher_positive_no_child_fact_allows_original_closure_then_retry(self):
        case,_,item,_,_=self.maintained();old=self.fail_without_child(case,item)
        failures={path.name:path.read_bytes() for path in item.output.iterdir()}
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
        self.assertEqual(failures,{name:(item.output/name).read_bytes() for name in failures})

    def test_reconstructed_accepted_receipt_closes_before_stale_current_can_advance(self):
        case,service,item,record,args=self.maintained()
        old=case.gate.accept('execute',record['operation_id'],'accepted-without-dispatch',
            dict(prepared=item.maintenance_prepared),item.loaded_deployment,prepared=item.maintenance_prepared)
        reopened=self.reopen(case,service,item,record)
        self.assertEqual('IDLE',reopened.state())
        original=case.gate.snapshot()['responsibilities'][old['id']]
        self.assertEqual('CLOSED',original['state']);self.assertEqual({'never_dispatched':True},original['proof'])
        with patch.object(service,'_prepare_worker') as worker:
            response=service.call(args);service.worker.join(3)
            self.assertFalse(service.worker.is_alive());worker.assert_called_once()
        self.assertEqual('PREPARING',response['state'])
        self.assertNotEqual(record['attempt'],service.records[record['operation_id']]['attempt'])
        self.assertEqual(original,case.gate.snapshot()['responsibilities'][old['id']])
        self.assertFalse((item.output/'finished.json').exists())

    def fresh_request(self,service,item,record):
        record['request']['expires_at']=time.time()+600
        item.maintenance_prepared=maintenance.prepared_binding(item.loaded_deployment,
            operation_id=record['operation_id'],attempt_id=record['attempt'],
            request_digest=record['request']['request_digest'],launch=item.launch)
        record['maintenance_prepared']=item.maintenance_prepared;service._save(record)

    def test_constructor_gate_read_failure_never_hides_original_dispatch_on_start(self):
        case,service,item,record,_=self.maintained();self.fresh_request(service,item,record)
        old=self.fail_without_child(case,item)
        with patch.object(case.gate,'active',side_effect=JobError('MAINTENANCE_UNKNOWN','temporary read failure')):
            reopened=self.reopen(case,service,item,record)
        original=case.gate.snapshot()['responsibilities'][old['id']]
        with case.execution_patches(reopened,[sys.executable,'-c','pass']), \
                patch.object(service,'_unit_active',return_value=False), \
                patch.object(case.gate,'accept',wraps=case.gate.accept) as accept, \
                patch.object(prepared.subprocess,'Popen',side_effect=AssertionError('must not replay')) as popen:
            result=service.call(dict(action='start',operation_id=record['operation_id'],
                principal_id='owner',request_digest=record['request']['request_digest']))
            self.assertEqual({'state':'UNRESOLVED'},result)
            accept.assert_not_called();popen.assert_not_called()
        self.assertEqual({old['id']:original},case.gate.snapshot()['responsibilities'])
        self.assertFalse((item.output/'finished.json').exists())

    def test_constructor_gate_read_failure_can_recover_accepted_before_normal_start(self):
        case,service,item,record,_=self.maintained();self.fresh_request(service,item,record)
        old=case.gate.accept('execute',record['operation_id'],'original-accepted',
            dict(prepared=item.maintenance_prepared),item.loaded_deployment,prepared=item.maintenance_prepared)
        with patch.object(case.gate,'active',side_effect=JobError('MAINTENANCE_UNKNOWN','temporary read failure')):
            reopened=self.reopen(case,service,item,record)
        self.assertEqual('IDLE',reopened.state())
        closed=case.gate.snapshot()['responsibilities'][old['id']]
        self.assertEqual('CLOSED',closed['state']);self.assertEqual({'never_dispatched':True},closed['proof'])
        with case.execution_patches(reopened,[sys.executable,'-c','pass']):
            reopened.start();self.assertTrue(reopened.complete.wait(3));self.assertEqual('EXITED',reopened.state())
        self.assertEqual([],case.gate.active())
        self.assertEqual(closed,case.gate.snapshot()['responsibilities'][old['id']])
        self.assertEqual(2,len(case.gate.snapshot()['responsibilities']))

    def test_failed_waiter_queued_original_job_blocks_retry_until_job_is_gone(self):
        case,service,item,record,args=self.maintained()
        item.installation['installed']['programs']['systemctl']={'path':'/synthetic/systemctl'}
        service.config['installation']['installed']['programs']={'systemctl':{'path':'/synthetic/systemctl'}}
        record['controller_unit']=item.launch['controller_envelope']['controller']['unit']
        launch_path=Path(record['attempt'])/'launch-static.json'
        launch_path.write_text(json.dumps(item.launch));launch_path.chmod(0o600)
        record['launch_path']=str(launch_path);service._save(record)
        with sqlite3.connect(str(Path(item.launch['policy']['broker_root'])/'jobs.sqlite')) as db:
            db.execute('create table operations(namespace text,id text)')
        queued=True
        def systemctl(argv,**kwargs):
            self.assertEqual(record['controller_unit'],argv[2])
            job='23 /org/freedesktop/systemd1/job/23' if queued else '0'
            return Mock(returncode=0,stdout='inactive\n' if '--value' in argv else
                        'ActiveState=inactive\nJob='+job+'\n')
        with case.execution_patches(item,[sys.executable,'-c','raise SystemExit(1)']), \
                patch.object(prepared.subprocess,'run',side_effect=systemctl), \
                patch.object(resident,'load',side_effect=lambda path:json.loads(Path(path).read_text())):
            item.start();self.assertTrue(item.complete.wait(3));item.state()
            old=case.gate.active()[0]
            current=Path(record['attempt']).parent/'current.json';original=current.read_bytes()
            finished=(item.output/'finished.json').read_bytes()
            self.assertEqual('RUNNING',service.execution_state(record))
            with patch.object(service,'_prepare_worker') as worker:
                self.assertEqual('READY',service.call(args)['state']);worker.assert_not_called()
                self.assertEqual(original,current.read_bytes())
                self.assertEqual('DISPATCHING',case.gate.snapshot()['responsibilities'][old['id']]['state'])
                queued=False
                self.assertEqual('EXITED',service.execution_state(record))
                self.assertEqual('CLOSED',case.gate.snapshot()['responsibilities'][old['id']]['state'])
                self.assertEqual('PREPARING',service.call(args)['state']);service.worker.join(3)
                worker.assert_called_once();self.assertFalse(service.worker.is_alive())
            self.assertEqual(finished,(item.output/'finished.json').read_bytes())
            self.assertNotEqual(record['attempt'],service.records[record['operation_id']]['attempt'])

    def test_cross_boot_failed_waiter_retry_checks_original_database_without_current_unit(self):
        for committed in (False,True):
            with self.subTest(committed=committed):
                case,service,item,record,args=self.maintained()
                launch_path=Path(record['attempt'])/'launch-static.json'
                launch_path.write_text(json.dumps(item.launch));launch_path.chmod(0o600)
                record['launch_path']=str(launch_path);service._save(record)
                with sqlite3.connect(str(Path(item.launch['policy']['broker_root'])/'jobs.sqlite')) as db:
                    db.execute('create table operations(namespace text,id text)')
                    if committed:db.execute('insert into operations values (?,?)',('job',record['operation_id']))
                with case.execution_patches(item,[sys.executable,'-c','raise SystemExit(1)']):
                    item.start();self.assertTrue(item.complete.wait(3));item.state()
                original=(item.output/'finished.json').read_bytes()
                service.boot='next-boot'
                service.loaded_deployment=maintenance.loaded_configuration(service.config,boot_id=service.boot)
                with patch.object(resident,'load',side_effect=lambda path:json.loads(Path(path).read_text())), \
                        patch.object(service,'_unit_active',side_effect=AssertionError('new boot unit is not original')), \
                        patch.object(service,'_prepare_worker') as worker:
                    self.assertEqual('EXITED',service.execution_state(record))
                    response=service.call(args)
                    if committed:
                        self.assertEqual('READY',response['state']);worker.assert_not_called()
                        self.assertEqual(record,service.records[record['operation_id']])
                    else:
                        self.assertEqual('PREPARING',response['state']);service.worker.join(3)
                        self.assertFalse(service.worker.is_alive());worker.assert_called_once()
                self.assertEqual(original,(item.output/'finished.json').read_bytes())


if __name__=='__main__':unittest.main()
