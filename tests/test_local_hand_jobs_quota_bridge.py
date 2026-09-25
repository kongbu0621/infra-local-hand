"""Actual credentialed socketpair/FD tests and immutable SQLite bridge tests.

Systemd stage proofs in the SQLite tests remain explicitly modeled.
"""
import array
import os
import socket
import sys
import threading
import unittest

from local_hand_jobs import budget, quota_contract as q
from local_hand_jobs.contract import JobError
from local_hand_jobs import quota_bridge as bridge
import test_local_hand_jobs_quota_closure as closure_tests


@unittest.skipUnless(sys.platform.startswith('linux') and hasattr(os,'pidfd_open'), 'Linux credentialed inherited bridge')
class ChannelTests(unittest.TestCase):
    def pair(self, peer=None):
        left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        clock=budget.current_clock()
        options=dict(peer=peer or (os.getpid(),os.getuid(),os.getgid()),session='a'*64,
            boot_id=clock['boot_id'],deadline_ns=clock['boottime_ns']+5_000_000_000)
        a=bridge.Channel(left,**options);b=bridge.Channel(right,**options)
        self.addCleanup(a.close);self.addCleanup(b.close)
        return a,b

    def test_actual_credentials_fragmentation_and_two_way_order(self):
        a,b=self.pair();value={'payload':'x'*100000};errors=[]
        def send():
            try:a.send(value)
            except BaseException as e:errors.append(e)
        thread=threading.Thread(target=send);thread.start()
        self.assertEqual(value,b.receive());thread.join(timeout=3)
        self.assertFalse(thread.is_alive());self.assertEqual([],errors)
        b.send({'ack':True});self.assertEqual({'ack':True},a.receive())
        self.assertEqual((1,1,1,1),(a.tx,a.rx,b.tx,b.rx))

    def test_wrong_actual_uid_poisoned_before_payload_use(self):
        a,b=self.pair(peer=(os.getpid(),os.getuid()+1,os.getgid()))
        a.send({'safe':True})
        with self.assertRaises(q.QuotaError):b.receive()
        with self.assertRaises(q.QuotaError):b.send({'retry':True})

    def test_received_descriptors_closed_even_when_rejected(self):
        a,b=self.pair();fd=os.open(os.devnull,os.O_RDONLY)
        try:
            before=len(os.listdir('/proc/self/fd'))
            a.sock.sendmsg([bridge.HEADER.pack(0,0,1)+b'x'],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))])
            with self.assertRaises(q.QuotaError):b.receive()
            self.assertEqual(before,len(os.listdir('/proc/self/fd')))
        finally:os.close(fd)

    def test_sequence_session_truncation_and_trailing_frame_rejected(self):
        for kind in ('sequence','session','truncated','oversize'):
            with self.subTest(kind=kind):
                a,b=self.pair()
                if kind=='session':a.session='b'*64;a.send({'safe':True})
                else:
                    seq=1 if kind=='sequence' else 0
                    raw=b'x'*(bridge.CHUNK+1) if kind=='oversize' else b'x'
                    a.sock.send(bridge.HEADER.pack(seq,0,2 if kind=='truncated' else len(raw))+raw)
                with self.assertRaises(q.QuotaError):b.receive()
                self.assertTrue(b.poisoned)

    def test_peer_exit_is_not_an_ack_or_permission_to_reconnect(self):
        left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        read,write=os.pipe();child=os.fork()
        if child==0:
            os.close(write);left.close();right.close();os.read(read,1);os._exit(0)
        os.close(read)
        clock=budget.current_clock()
        a=bridge.Channel(left,peer=(child,os.getuid(),os.getgid()),session='a'*64,
            boot_id=clock['boot_id'],deadline_ns=clock['boottime_ns']+5_000_000_000)
        self.addCleanup(a.close);right.close();os.close(write);os.waitpid(child,0)
        with self.assertRaises(q.QuotaError):a.receive()

    def test_inherited_socket_reports_child_sender_not_creator(self):
        left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        left.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
        read,write=os.pipe();child=os.fork()
        if child==0:
            left.close();os.close(write)
            os.read(read,1)
            raw=q._canonical(dict(schema=bridge.SCHEMA,session='a'*64,value={'child':True}),bridge.LIMIT)
            right.send(bridge.HEADER.pack(0,0,len(raw))+raw)
            os.read(read,1);os._exit(0)
        os.close(read);right.close()
        clock=budget.current_clock()
        a=bridge.Channel(left,peer=(child,os.getuid(),os.getgid()),session='a'*64,
            boot_id=clock['boot_id'],deadline_ns=clock['boottime_ns']+5_000_000_000)
        try:
            os.write(write,b'x');self.assertEqual({'child':True},a.receive())
        finally:
            os.close(write);os.waitpid(child,0);a.close()


class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.f=closure_tests.BrokerClosureTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f.f
        self.phase=bridge.Phase(f.broker,'job',f.id,'preflight')

    def test_original_pending_export_close_and_no_public_fields(self):
        f=self.f.f;f.broker._complete('job',f.id,self.f.proof)
        before=self.phase.handle({'action':'snapshot','value':None})
        self.assertEqual(self.f.proof,before['pending']['proof'])
        after=self.phase.handle({'action':'close','value':self.f.fence})
        self.assertEqual(self.f.fence,after['closed']['fence'])
        self.assertFalse(any(k.startswith('quota_') for k in f.broker.status(f.id,f.f.owner)))

    def test_arbitrary_action_or_operation_field_poison_without_start(self):
        f=self.f.f;n=len(f.runner.starts)
        with self.assertRaises(q.QuotaError):self.phase.handle({'action':'shell','value':'id'})
        with self.assertRaises(q.QuotaError):self.phase.handle({'action':'snapshot','value':None})
        self.assertEqual(n,len(f.runner.starts))

    def test_snapshot_damage_and_restart_not_repaired(self):
        f=self.f.f;f.broker._complete('job',f.id,self.f.proof)
        with f.f.db.transaction() as tx:f.f.db.update(tx,'job',f.id,'FAULT',{'quota_pending':{}})
        with self.assertRaises(JobError):self.phase.handle({'action':'snapshot','value':None})
        self.assertTrue(self.phase.failed)
        self.assertEqual(1,sum(x['kind']=='QUOTA_EXIT_PENDING' for x in f.f.db.events('job',f.id)))

    def test_foreign_root_command_cannot_select_another_operation(self):
        with self.assertRaises(q.QuotaError):self.phase.handle({'action':'snapshot','value':None,'operation_id':'other'})


if __name__=='__main__':unittest.main()
