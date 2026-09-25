"""Orchestration fault/order models; real contract/closure validation, no host PASS."""
from contextlib import contextmanager
import copy
import os
import stat
from types import SimpleNamespace
import sys
import unittest
from unittest import mock

from local_hand_jobs import quota_contract as q, quota_grant as g
from q2_fixtures import make_grant, capacity, SECOND
from test_e3_quota_q2_closure import complete
if sys.platform.startswith('linux'):
    from admin.local_hand_quota_observer import q2_coordinator as driver
    from admin.local_hand_quota_observer.q2_service import Service


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux Q2 coordinator')
class CoordinatorTests(unittest.TestCase):
    def clock(self):
        self.now += 1_000_000
        return self.now

    def setup_driver(self, fault=None, *, long_phase=False, pending_after=0,
                     management_close_poll=3, eof_after=0):
        self.now=3*SECOND
        grant=make_grant()
        if long_phase:
            declaration=grant.as_dict()
            declaration['budget']['limits']['wall_seconds']=120
            declaration['budget']['deadline_boottime_ns']=361*SECOND
            declaration['request']['deadline_ns']=110*SECOND
            grant=g.decode_grant(q._canonical(declaration,g.GRANT_LIMIT))
        v=grant.as_dict();fence,ordinary,receipt,peer=complete(grant)
        owner=self
        order=[];states={grant.request.as_dict()['request_id']:{'status':'READY'}}
        key=grant.request.as_dict()['request_id']
        class Journal:
            grants={key:grant}
            capacity=capacity()
            @contextmanager
            def locked(self):yield
            def scan(self):return states
            def append(self,key,kind,value):
                order.append('admin-'+kind);states[key][kind.lower()]=value;states[key]['status']=kind
            def close(self):order.append('journal-close')
        cfg=SimpleNamespace(active=lambda:grant,grants=lambda:{key:grant},digest='c'*64,data=lambda:{
            'journal':{'path':'/synthetic/journal','pin':{}},'capacity':capacity(),'service':{'control_path':'/synthetic/private'}})
        management=dict(schema='local-hand-quota-management-closed/v1',config_digest=cfg.digest,
            request_digest=grant.request.digest,controller={},observed_ns=3*SECOND,
            stages={k:fence['stages'][k] for k in ('collector','admission')})
        class Management:
            end=(100 if long_phase else 10)*SECOND
            def __init__(self,*args):self.runs={};self.polls=0
            def begin(self):order.append('listener');self.launch('listener')
            def launch(self,role):
                if role=='admission':order.append('admission')
                cap=SimpleNamespace(error=None,exited=False,done=False,settled=False,
                    process=SimpleNamespace(returncode=0))
                def pump():
                    if self.polls>=management_close_poll and owner.now>=eof_after:
                        cap.done=cap.settled=cap.exited=True
                cap.pump=pump
                self.runs[role]={'invocation':None,'stop_attempted':False,'stop_ok':False,'after':None,'capture':cap}
            def poll(self):
                self.polls+=1
                for p in self.runs.values():
                    p['invocation']='e'*32
                    if self.polls>=management_close_poll-1:p['stop_attempted']=p['stop_ok']=True
                    if self.polls>=management_close_poll:p['after']={'LoadState':'not-found'}
                    p['capture'].pump()
                return management if all(p['capture'].done for p in self.runs.values()) else None
            def finish(self):
                order.append('management-closed')
                if fault=='management':raise q.QuotaError('CLOSE_FAULT')
                return management
        prep=dict(allocation=v['allocation'],budget=v['budget'],phase='preflight')
        if fault=='preparation':prep['budget']=dict(v['budget'],reserved_boottime_ns=2*SECOND)
        snap=dict(preparation=prep,observation=None,pending=None,closed=None)
        class Client:
            def call(self,action,value=None):
                order.append(action)
                if sum(order.count(k) for k in ('snapshot','bind','start','close'))>64:
                    raise q.QuotaError('BRIDGE_EXCHANGE_LIMIT')
                if action=='start':
                    states[key]=dict(status='RESULT',intent={'peer':peer},result={'receipt':receipt.as_dict(),'received_ns':2*SECOND+10})
                    snap['observation']={'phase':'preflight','observation':{'receipt':receipt.as_dict()}}
                    if fault=='receipt':snap['observation']['observation']['receipt']=dict(receipt.as_dict(),reason='OTHER')
                if snap['observation'] is not None and owner.now>=pending_after:
                    snap['pending']={'phase':'preflight','proof':ordinary}
                if action=='close':
                    if states[key]['status']!='CLOSED':raise AssertionError('broker closed before administrator')
                    if fault=='ack':raise OSError('lost ack')
                    snap['closed']={'phase':'preflight','fence':value}
                return copy.deepcopy(snap)
        def ready(path,*args):order.append('private-ready' if path.endswith('private') else 'public-ready');return True
        patches=[mock.patch.object(driver.m,'Management',Management),mock.patch.object(driver,'Journal',lambda *args:Journal()),
            mock.patch.object(driver,'Service',lambda j,closure_version:Service(j,clock=lambda:dict(boot_id=v['request']['boot_id'],ns=self.now),closure_version=closure_version)),
            mock.patch.object(driver,'ready',side_effect=ready),mock.patch.object(driver,'boottime_ns',side_effect=self.clock),
            mock.patch.object(driver.time,'sleep'),mock.patch.object(driver.quota_lifecycle,'parent',side_effect=lambda path,pin:(pin,fault!='occupied'))]
        for p in patches:p.start();self.addCleanup(p.stop)
        instance=driver.Coordinator(cfg,{'deadline_ns':(130 if long_phase else 30)*SECOND},None,Client())
        return instance,order,states[key],states

    def test_fixed_readiness_order_and_two_ledger_commit_order(self):
        instance,order,_,states=self.setup_driver();result=instance.run()
        self.assertEqual('PHASE_CLOSED',result['status']);self.assertFalse(result['q3_accepted'])
        expected=['listener','private-ready','admission','public-ready','bind','start','management-closed','admin-CLOSED','close']
        positions=[order.index(x) for x in expected];self.assertEqual(sorted(positions),positions)
        self.assertEqual('CLOSED',next(iter(states.values()))['status'])
        with self.assertRaises(q.QuotaError):instance.run()

    def test_preparation_mismatch_stops_before_any_manager_delivery(self):
        instance,order,_,_=self.setup_driver('preparation')
        with self.assertRaises(q.QuotaError):instance.run()
        self.assertNotIn('listener',order);self.assertNotIn('bind',order)

    def test_lost_broker_ack_retains_admin_close_and_never_replays(self):
        instance,order,_,states=self.setup_driver('ack')
        with self.assertRaises(OSError):instance.run()
        self.assertEqual('CLOSED',next(iter(states.values()))['status'])
        with self.assertRaises(q.QuotaError):instance.run()
        self.assertEqual(1,order.count('start'));self.assertEqual(1,order.count('admin-CLOSED'))

    def test_incomplete_management_prevents_both_ledger_closures(self):
        instance,order,_,_=self.setup_driver('management')
        with self.assertRaises(q.QuotaError):instance.run()
        self.assertNotIn('admin-CLOSED',order);self.assertNotIn('close',order)

    def test_changed_receipt_prevents_both_ledger_closures(self):
        instance,order,_,_=self.setup_driver('receipt')
        with self.assertRaises(q.QuotaError):instance.run()
        self.assertNotIn('admin-CLOSED',order);self.assertNotIn('close',order)

    def test_occupied_parent_prevents_both_ledger_closures(self):
        instance,order,_,_=self.setup_driver('occupied')
        with self.assertRaises(q.QuotaError):instance.run()
        self.assertNotIn('admin-CLOSED',order);self.assertNotIn('close',order)

    def test_long_original_phase_keeps_bridge_capacity_for_close(self):
        instance,order,_,_=self.setup_driver(long_phase=True,pending_after=80*SECOND)
        result=instance.run()
        self.assertEqual('PHASE_CLOSED',result['status'])
        self.assertGreater(self.now,80*SECOND)
        self.assertLessEqual(order.count('snapshot'),driver.SNAPSHOT_POLLS+1)
        self.assertLessEqual(sum(order.count(k) for k in ('snapshot','bind','start','close')),64)

    def test_last_regular_poll_can_stop_then_observe_original_exit(self):
        # Initial readiness poll plus ten running-service polls; the final
        # regular poll issues stop and needs a separate post-stop observation.
        instance,order,_,_=self.setup_driver(management_close_poll=12)
        result=instance.run()
        self.assertEqual('PHASE_CLOSED',result['status'])
        self.assertEqual(12,instance.management.polls)
        self.assertLessEqual(2+2*instance.management.polls+2,32)

    def test_delayed_client_eof_does_not_spend_more_systemctl_polls(self):
        instance,order,_,_=self.setup_driver(eof_after=8*SECOND)
        result=instance.run()
        self.assertEqual('PHASE_CLOSED',result['status'])
        self.assertGreaterEqual(self.now,8*SECOND)
        self.assertEqual(3,instance.management.polls)

    def test_unpublished_socket_is_not_ready_or_an_error(self):
        # Socket filesystem state is modeled: no actual systemd readiness PASS.
        parent=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
        info=SimpleNamespace(st_mode=stat.S_IFSOCK,st_uid=0,st_gid=1234)
        with mock.patch.object(driver.c,'open_protected',return_value=parent),\
             mock.patch.object(driver.os,'stat',return_value=info):
            self.assertFalse(driver.ready('/synthetic/private',0,0,0o600))


if __name__=='__main__':unittest.main()
