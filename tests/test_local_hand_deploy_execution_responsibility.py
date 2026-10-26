"""Original execution duties survive launcher reconstruction and pointer retries.

All effects are confined to temporary files and harmless local child processes.
The maintenance Gate and resident current-pointer publications remain real.
"""
import os
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux administrator execution responsibilities')

from admin.local_hand_system_manager import prepared_service as prepared
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


if __name__=='__main__':unittest.main()
