"""Retry attestation uses real SQLite/files/pipes but never creates services or quotas."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("Linux retry attestation requires fcntl and Unix ownership")

PATH=Path(__file__).parent/'e3_host/q2_retry.py'
spec=importlib.util.spec_from_file_location('_retry_test',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def startup_fixture():
    controller=dict(cgroup='/lhqsupervisor.slice/lhqold.service',cpu_quota_per_sec_usec=1000000,
        runtime_max_usec=100000000,timeout_stop_usec=1000000,memory_bytes=64*1024**2,tasks_max=32,
        limit_cpu_seconds=100,unit='lhqold.service')
    fixture=dict(supervisor_envelope=dict(controller=controller),launcher=dict(
        resident=dict(entry=dict(path='/old/source/tests/e3_host/q2_resident.py')),
        assembly=dict(installation=dict(programs=dict(systemd_run=dict(path='/usr/bin/systemd-run'),python=dict(path='/old/python'))))))
    plan=dict(declarations=dict(path='/old/declarations'),owner_envelope=dict(deadline_ns=100))
    envelope=dict(schema='local-hand-q2-issued-handoff/v1',plan=plan,fixture=fixture)
    eraw=m.c.encoded(envelope);praw=m.c.encoded(plan)
    argv=m.legacy_argv(envelope,'/old/declarations/envelope.json',m.p.sha(eraw))
    facts='Id=lhqold.service\nLoadState=not-found\nActiveState=inactive\nSubState=dead\nMainPID=0\nControlPID=0\nInvocationID=\nControlGroup=\nJob=\n'
    control=dict(complete=True,returncode=0,eof=['stderr','stdout'],error=None,stderr_hex='',stdout_hex=facts.encode().hex())
    values=dict(reservation=dict(envelope_sha256=m.p.sha(eraw),plan_sha256=m.p.sha(praw)),
        delivery=dict(argv_sha256=m.p.sha(m.c.encoded(argv)),unit='lhqold.service',started_ns=2,deadline_ns=100),
        capture=dict(complete=True,returncode=1,eof=['stderr','stdout'],error=None,close_errors=[],
            stdout_sha256=m.p.sha(b''),stderr_sha256=m.p.sha(m.ERROR),started_ns=2,deadline_ns=100),
        result=dict(status='INCOMPLETE',reason='SUPERVISOR_DELIVERY_UNCERTAIN',sealed=False,q2_accepted=False,cleanup_errors=[]),
        stop={},controls=[control,copy.deepcopy(control)])
    raw={key+'.json':m.c.encoded(value) for key,value in values.items()}
    raw.update({'supervisor.stdout':b'','supervisor.stderr':m.ERROR})
    prepared=dict(status='RECOVERED_PREPARED',q2_accepted=False,first_request_issuance=dict(original_request_unissued=True))
    return raw,eraw,praw,prepared


class ExactStartup(unittest.TestCase):
    def test_original_issuance_is_retained_as_failed(self):
        args=startup_fixture();before=copy.deepcopy(args);proof=m.attest_startup(*args)
        self.assertTrue(proof['original_owner_issued']);self.assertEqual('INCOMPLETE',proof['original_status']);self.assertEqual(before,args)

    def test_other_error_missing_eof_nonzero_mismatch_and_extra_child_rejected(self):
        for name,mutation in (
            ('supervisor.stderr',lambda v:b'other failure\n'),
            ('capture.json',lambda v:dict(v,eof=['stdout'])),
            ('capture.json',lambda v:dict(v,returncode=0)),
            ('capture.json',lambda v:dict(v,close_errors=['close'])),
            ('delivery.json',lambda v:dict(v,argv_sha256='0'*64)),
            ('result.json',lambda v:dict(v,status='COMPLETE')),
            ('reservation.json',lambda v:dict(v,envelope_sha256='0'*64))):
            args=list(startup_fixture());raw=args[0]
            raw[name]=mutation(raw[name]) if not name.endswith('.json') else m.c.encoded(mutation(m.c.document(raw[name])))
            with self.subTest(name=name),self.assertRaises(ValueError):m.attest_startup(*args)
        args=list(startup_fixture());args[0]['invocation.json']=b'{}'
        with self.assertRaises(ValueError):m.attest_startup(*args)

    def test_created_or_busy_old_child_rejected(self):
        for old,new in [('LoadState=not-found','LoadState=loaded'),('MainPID=0','MainPID=42'),('InvocationID=\n','InvocationID=abc\n')]:
            args=list(startup_fixture());v=m.c.document(args[0]['controls.json'])
            v[1]['stdout_hex']=bytes.fromhex(v[1]['stdout_hex']).decode().replace(old,new).encode().hex()
            args[0]['controls.json']=m.c.encoded(v)
            with self.subTest(old=old),self.assertRaisesRegex(ValueError,'RETRY_OLD_CHILD_CREATED'):m.attest_startup(*args)


class ReadOnlyLedger(unittest.TestCase):
    def setUp(self):
        # Protected repository ancestry, not world-writable /tmp.
        self.directory=tempfile.TemporaryDirectory(dir=Path.home());self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'jobs.sqlite'
        from local_hand_jobs.state import StateStore
        store=StateStore(self.path,'authority','ledger',initialize=True);store.close()
        info=self.path.stat();self.pin=dict(path=str(self.path),device=info.st_dev,inode=info.st_ino,uid=info.st_uid,
            mode=stat.S_IMODE(info.st_mode),ledger_id='ledger',generation=[1,1])

    def attest(self):return m.attest_ledger(self.path,self.pin,'authority')

    def test_actual_initialized_schema_autoindexes_triggers_and_sequence_accepted(self):
        before=self.path.read_bytes();proof=self.attest();self.assertTrue(proof['unused'])
        self.assertEqual(m.p.sha(before),proof['sha256']);self.assertEqual(before,self.path.read_bytes())
        self.assertEqual(['jobs.sqlite'],os.listdir(self.directory.name))

    def test_sqlite_validation_preserves_retained_ledger_atime_and_bytes(self):
        raw=self.path.read_bytes()
        os.utime(self.path,ns=(10**9,2*10**9));before=self.path.stat()
        proof=self.attest()
        self.assertEqual(before.st_atime_ns,self.path.stat().st_atime_ns)
        self.assertEqual(before,self.path.stat())
        self.assertEqual(m.p.sha(raw),proof['sha256'])
        self.assertEqual(raw,m.p.read(self.path,len(raw),owner=before.st_uid,noatime=True))

    def test_invalid_sqlite_journal_header_is_not_normalized_into_acceptance(self):
        raw=bytearray(self.path.read_bytes())
        for version in (b'\3\3',b'\1\2',b'\0\0'):
            with self.subTest(version=version):
                raw[18:20]=version;self.path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError,'RETRY_LEDGER_FORMAT'):self.attest()

    def test_consumption_generation_unknown_schema_and_revocation_rejected(self):
        mutations=["INSERT INTO events(namespace,id,kind,observed_at,data_json) VALUES('job','id','x',1,'{}')",
            "UPDATE counters SET value=2", "CREATE TABLE surprise(x)", "INSERT INTO revocations VALUES('x',1)",
            "DROP TRIGGER events_no_delete"]
        original=self.path.read_bytes()
        for sql in mutations:
            with self.subTest(sql=sql):
                self.path.write_bytes(original)
                with sqlite3.connect(self.path) as db:db.execute(sql)
                db.close()
                with self.assertRaises(ValueError):self.attest()

    def test_sidecar_changed_identity_or_metadata_rejected(self):
        side=Path(str(self.path)+'-wal');side.write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'SIDECAR'):self.attest()
        side.unlink();self.pin['inode']+=1
        with self.assertRaisesRegex(ValueError,'IDENTITY'):self.attest()
        self.pin['inode']-=1
        with sqlite3.connect(self.path) as db:db.execute("UPDATE metadata SET value='other' WHERE key='authority_id'")
        db.close()
        with self.assertRaisesRegex(ValueError,'METADATA'):self.attest()


class RetentionAndDeadlines(unittest.TestCase):
    def test_snapshot_preserves_retained_file_and_directory_atimes(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as td:
            path=Path(td);file=path/'payload';file.write_bytes(b'retained')
            for name in (file,path):os.utime(name,ns=(10**9,2*10**9))
            before={name:name.stat() for name in (file,path)}
            m.snapshot_tree(path,lambda:None)
            # Retry also inherits the original Q1 retained-tree snapshot.
            backend=m.p.LinuxBackend.__new__(m.p.LinuxBackend);backend.guard=lambda:None
            info=path.stat();backend.plan=dict(retained=[dict(path=str(path),device=info.st_dev,inode=info.st_ino)],
                budgets=dict(retained_scan_entries=8,retained_scan_bytes=128))
            self.assertEqual(2,backend.snapshot()[0]['entries'])
            for name,info in before.items():
                with self.subTest(name=name):
                    self.assertEqual(info.st_atime_ns,name.stat().st_atime_ns)
                    self.assertEqual(info,name.stat())

    def test_old_directory_membership_preserves_atime_and_rejects_extra_members(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as td:
            path=Path(td);(path/'envelope.json').write_bytes(b'{}')
            os.utime(path,ns=(10**9,2*10**9));before=path.stat()
            m.require_members(path,{'envelope.json'},'RETRY_OLD_CHILD_CREATED',owner=os.getuid())
            self.assertEqual(before.st_atime_ns,path.stat().st_atime_ns)
            (path/'unexpected.json').write_bytes(b'{}')
            os.utime(path,ns=(10**9,2*10**9));before=path.stat()
            with self.assertRaisesRegex(ValueError,'RETRY_OLD_CHILD_CREATED'):
                m.require_members(path,{'envelope.json'},'RETRY_OLD_CHILD_CREATED',owner=os.getuid())
            self.assertEqual(before.st_atime_ns,path.stat().st_atime_ns)

    def test_real_snapshot_detects_same_size_edit_and_hardlinks(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as td:
            path=Path(td);file=path/'payload';file.write_bytes(b'one');before=m.snapshot_tree(path,lambda:None)
            file.write_bytes(b'two');after=m.snapshot_tree(path,lambda:None);self.assertNotEqual(before['sha256'],after['sha256'])
            os.link(file,path/'alias')
            with self.assertRaisesRegex(ValueError,'TREE_TYPE|TREE_ALIAS'):m.snapshot_tree(path,lambda:None)

    def test_absent_new_staging_excluded_from_old_preservation_only(self):
        b=m.RetryBackend.__new__(m.RetryBackend);b.plan={'candidate':{'source':'/new/stage/source','wheel':'/new/stage/wheel'}}
        b.retry={'source':{'files':{'/new/stage/tools/q.py':'a'*64}},'retained_inputs':[
            {'path':'/old','category':'installation'},{'path':'/new/stage','category':'installation'},
            {'path':'/new/stage.intent.json','category':'installation'}]};b.guard=lambda:None
        with mock.patch.object(m,'snapshot_tree',return_value={'old':True}) as snap:
            self.assertEqual([{'old':True}],b.old_snapshot());snap.assert_called_once_with('/old',b.guard)
        self.assertFalse(b.new_staging({'path':'/other','category':'installation'}))

    def test_no_argument_entry_is_inert(self):
        result=subprocess.run([sys.executable,'-I','-B',str(PATH)],capture_output=True,timeout=10)
        self.assertEqual(3,result.returncode);self.assertEqual('BLOCKED',json.loads(result.stdout)['status']);self.assertEqual(b'',result.stderr)

    def test_boot_time_advance_bounds_a_live_command_and_reaps_it(self):
        plan={'budgets':{'preparation_seconds':140,'state_bytes':32*1024**2,'state_inodes':8192,
            'command_seconds':30,'command_output_bytes':32768}}
        b=m.RetryBackend.__new__(m.RetryBackend);m.p.LinuxBackend.__init__(b,plan)
        b.deadline=time.monotonic_ns()+10**10;b.boot_deadline_ns=100*10**9
        clocks=iter([1,1,1,101*10**9,101*10**9])
        with mock.patch.object(m.time,'clock_gettime_ns',side_effect=lambda _:next(clocks,101*10**9)):
            with self.assertRaisesRegex(ValueError,'TIMEOUT'):
                b.command([sys.executable,'-I','-c','import time; time.sleep(30)'])
        self.assertEqual(-9,b.last_command_failure['returncode'])
        self.assertEqual('PREPARE_COMMAND_TIMEOUT',b.last_command_failure['failure'])

    def test_reservation_requires_verified_candidate(self):
        b=m.RetryBackend.__new__(m.RetryBackend);b.candidate_checked=False
        with self.assertRaisesRegex(ValueError,'RETRY_CANDIDATE_UNCHECKED'):b.reserve()


class LifecycleAndCapacity(unittest.TestCase):
    def backend(self):
        b=m.RetryBackend.__new__(m.RetryBackend)
        b.plan={'account':{'uid':1100},'parents':{'ordinary':{'unit':'ordinary.slice'},'query':{'unit':'query.slice'}},
                'tools':{'systemctl':{'path':'/usr/bin/systemctl'}}}
        b.started=set();b.event=mock.Mock();b.command=mock.Mock(return_value=b'');b.user_command=mock.Mock(return_value=b'')
        return b

    def test_inactive_slice_has_no_service_pid_fields_and_can_start_once(self):
        b=self.backend();b.unit_show=mock.Mock(return_value=dict(Id='ordinary.slice',LoadState='loaded',
            ActiveState='inactive',SubState='dead',ControlGroup='',Job=''))
        self.assertEqual('inactive',b.idle_unit('ordinary.slice',True)['ActiveState'])
        b.start_once('ordinary.slice',True)
        b.user_command.assert_called_once_with(['/usr/bin/systemctl','--user','start','ordinary.slice'])
        with self.assertRaisesRegex(ValueError,'ALREADY_ISSUED'):b.start_once('ordinary.slice',True)

    def test_start_failure_is_never_retried(self):
        b=self.backend();b.command.side_effect=ValueError('START_FAILED')
        with self.assertRaisesRegex(ValueError,'START_FAILED'):b.start_once('query.slice')
        with self.assertRaisesRegex(ValueError,'ALREADY_ISSUED'):b.start_once('query.slice')
        b.command.assert_called_once()

    def test_failed_unit_job_and_inactive_manager_with_pid_are_rejected(self):
        for value in (dict(ActiveState='failed'),dict(Job='44'),dict(ActiveState='inactive',MainPID='9')):
            b=self.backend();base=dict(Id='user@1100.service',LoadState='loaded',ActiveState='inactive',SubState='dead',Job='',
                MainPID='0',ControlPID='0');base.update(value);b.unit_show=mock.Mock(return_value=base)
            with self.subTest(value=value),self.assertRaises(ValueError):b.idle_unit('user@1100.service',manager=True)

    def test_manager_runtime_limit_override_rejected(self):
        b=self.backend();b.plan['parents']['ordinary'].update(memory_bytes=64,tasks_max=8,cpu_quota_per_sec_usec=1000000)
        with mock.patch.object(m.p,'kernel',return_value=b'max'):
            with self.assertRaisesRegex(ValueError,'RETRY_MANAGER_LIMIT'):b.manager_limits({'ControlGroup':'/manager'})

    def test_old_unspent_commitment_is_retained_without_double_charging_actual(self):
        b=self.backend();b.guard=lambda:None;b.skip_candidate=False
        b.plan.update(candidate={key:'/new/'+key for key in ('source','wheel','destination')},
            directories={role:{'path':'/new/'+role} for role in ('reservation','state','authority','journal','capture','declarations','session','control')},
            budgets={category+'_'+key:(64*1024**2 if key=='bytes' else 4096) for category in m.CATEGORIES for key in ('bytes','inodes')},
            settings={'management':dict(storage_bytes=1024**2,storage_inodes=32),'owner':dict(storage_bytes=8*1024**2,storage_inodes=64),
                'controllers':{'target':dict(storage_bytes=1024**2,storage_inodes=64),'supervisor':dict(storage_bytes=8*1024**2,storage_inodes=64)}})
        b.retry={'retained_inputs':[{'path':'/old/capture','category':'capture'}],'source':{'files':{}}}
        b.old_storage_commitment=dict(storage_bytes=20*1024**2,storage_inodes=288)
        with mock.patch.object(m.os.path,'lexists',return_value=False),mock.patch.object(m,'snapshot_tree',return_value=dict(bytes=3*1024**2,inodes=10)):
            costs=b.measure_costs()['capture'];self.assertEqual(40*1024**2,costs['admitted_bytes'])
            self.assertEqual(17*1024**2,costs['retained_unspent_bytes'])
            b.plan['budgets']['capture_bytes']=39*1024**2
            with self.assertRaisesRegex(ValueError,'COMMITMENT_CAPACITY'):b.measure_costs()


if __name__=='__main__':unittest.main()
