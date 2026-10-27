"""Real temporary startup selections, sockets and process-bound permits."""
from contextlib import contextmanager
import copy
import hashlib
import json
import logging
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from local_hand_jobs import maintenance, startup
from local_hand_jobs.contract import JobError
from local_hand_mcp import startup_guard


class StartupTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory();self.addCleanup(root.cleanup)
        self.root=Path(root.name)
        self.gate=maintenance.MaintenanceGate(self.root,'test-node',owner_uid=os.getuid())
        self.gate.initialize('a'*64,'bootstrap',bootstrap=True)
        self.path=self.root/'selection.json'
        self.member=self.root/'member.json';self.member.write_text('{"fixture":true}');self.member.chmod(0o600)
        self.config={'maintenance':{'startup_descriptor':str(self.path)}}
        self.proof=dict(node_id='test-node',deployment_digest='a'*64,configuration_digest='b'*64,
                        payload_digest='c'*64,boot_id=startup.boot_id(),component='manager')
        self.selection=dict(schema=startup.SCHEMA,node_id='test-node',deployment_digest='a'*64,
            decision_id='bootstrap',owner=None,mode='stable',permit=None,
            members=[dict(path=str(self.member),sha256=hashlib.sha256(self.member.read_bytes()).hexdigest())],
            components={'manager':dict(configuration_digest='b'*64,payload_digest='c'*64,entry='local',running=True)})
        self.publish(self.selection)

    def publish(self,value):
        expected=startup.digest(startup.read_selection(self.path,owner_uid=os.getuid())) if self.path.exists() else None
        owner=None
        if expected is not None and value['mode']=='stable':
            owner='fixture-'+uuid.uuid4().hex;self.gate.close(owner)
        startup.publish(self.path,value,self.gate,expected_digest=expected,owner_uid=os.getuid(),maintenance_owner=owner)
        if owner is not None:self.gate.release(owner,value['decision_id'],value['deployment_digest'])

    def candidate(self):
        self.gate.close('deploy')
        value=copy.deepcopy(self.selection)
        value.update(mode='candidate',decision_id=None,owner='deploy',
            permit=dict(boot_id=startup.boot_id(),attempt_id='boot-attempt',claims={}))
        self.publish(value)
        return value

    def test_stable_restart_requires_selected_actual_snapshot_and_complete_inputs(self):
        for _ in range(2):
            with startup.authorize(self.config,self.proof,self.gate) as proof:
                self.assertEqual('stable',proof['mode'])
        self.gate.close('deploy')
        with startup.authorize(self.config,self.proof,self.gate):pass
        with self.assertRaises(JobError):
            with startup.authorize(self.config,dict(self.proof,configuration_digest='d'*64),self.gate):pass
        self.member.write_text('{"changed":true}')
        with self.assertRaises(JobError):
            with startup.authorize(self.config,self.proof,self.gate):pass

    def test_candidate_permit_cannot_authorize_a_new_process_or_boot(self):
        self.candidate()
        with startup.authorize(self.config,self.proof,self.gate):pass
        selected=startup.read_selection(self.path,owner_uid=os.getuid())
        self.assertEqual(startup.instance(os.getpid()),selected['permit']['claims']['manager'])
        child=subprocess.Popen([sys.executable,'-c','import sys;print("ready",flush=True);sys.stdin.readline()'],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual('ready',child.stdout.readline().strip())
            with self.gate.admission_lock() as state:
                with self.assertRaises(JobError):
                    startup._admit_selection(self.path,state,'manager',child.pid,owner_uid=os.getuid())
        finally:child.communicate('\n',timeout=3)
        with patch.object(startup,'boot_id',return_value='different-boot'):
            with self.assertRaises(JobError):
                with startup.authorize(self.config,self.proof,self.gate):pass

    def test_candidate_claim_lost_sync_is_reconfirmed_without_new_instance(self):
        self.candidate();sync=os.fsync;failed=[]
        def fail_directory(fd):
            import stat
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not failed:
                failed.append(True);raise OSError('lost sync')
            return sync(fd)
        with patch.object(startup.os,'fsync',side_effect=fail_directory):
            with self.assertRaises(JobError):
                with startup.authorize(self.config,self.proof,self.gate):pass
        claim=startup.read_selection(self.path,owner_uid=os.getuid())['permit']['claims']['manager']
        with patch.object(startup.os,'fsync',wraps=sync) as again:
            with startup.authorize(self.config,self.proof,self.gate):pass
            self.assertGreater(again.call_count,0)
        self.assertEqual(claim,startup.read_selection(self.path,owner_uid=os.getuid())['permit']['claims']['manager'])

    def test_actual_listener_bind_excludes_concurrent_close(self):
        arrived=threading.Event();done=threading.Event();errors=[]
        def closer():
            arrived.set()
            try:self.gate.close('deploy')
            except BaseException as exc:errors.append(exc)
            finally:done.set()
        with startup.authorize(self.config,self.proof,self.gate):
            worker=threading.Thread(target=closer);worker.start();self.assertTrue(arrived.wait(2))
            self.assertFalse(done.wait(.1))
            with socket.socket(socket.AF_UNIX) as listener:listener.bind(str(self.root/'actual.sock'));listener.listen()
        self.assertTrue(done.wait(2));worker.join();self.assertEqual([],errors)

    def test_writable_grandparent_and_symlink_members_are_rejected(self):
        outer=self.root/'writable';outer.mkdir();inner=outer/'protected';inner.mkdir(mode=0o700)
        member=inner/'member';member.write_text('protected')
        outer.chmod(0o777)
        try:
            with self.assertRaises(JobError):startup.protected_read(member,owner_uid=os.getuid())
        finally:outer.chmod(0o700)
        linked=self.root/'alias';linked.symlink_to(inner,target_is_directory=True)
        with self.assertRaises(JobError):startup.protected_read(linked/'member',owner_uid=os.getuid())

    def test_expired_frame_cannot_send_late_success(self):
        left,right=socket.socketpair()
        with left,right:
            with self.assertRaises(JobError):startup._frame_send(left,{'bound':True},time.monotonic()-1)
            right.settimeout(.02)
            with self.assertRaises(TimeoutError):right.recv(1)

    def test_stable_publication_needs_current_owner_even_for_same_value(self):
        expected=startup.digest(self.selection)
        with self.assertRaises(JobError):
            startup.publish(self.path,self.selection,self.gate,expected_digest=expected,owner_uid=os.getuid())
        self.gate.close('deploy')
        with self.assertRaises(JobError):
            startup.publish(self.path,self.selection,self.gate,expected_digest=expected,
                            owner_uid=os.getuid(),maintenance_owner='wrong-owner')
        self.assertEqual(expected,startup.publish(self.path,self.selection,self.gate,expected_digest=expected,
                         owner_uid=os.getuid(),maintenance_owner='deploy'))


class MCPGuardTests(unittest.TestCase):
    publish=StartupTests.publish
    def setUp(self):
        StartupTests.setUp(self)
        config=self.root/'cli.json';config.write_text('{"synthetic":"cli"}');config.chmod(0o600)
        auth=self.root/'auth.json';auth.write_text('{"synthetic":"auth"}');auth.chmod(0o600)
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
        self.args=SimpleNamespace(startup_config=str(self.root/'mcp-startup.json'),config=str(config),
            auth_config=str(auth),resident=None,prepared_task=None,session=None,read_only=True,port=port)
        self.binding=dict(schema='local-hand-mcp-startup/v1',node_id='test-node',deployment_digest='a'*64,
            payload_digest='c'*64,manager_socket=str(self.root/'manager.sock'),mode='read_only',port=port,
            inputs=dict(config=str(config),auth_config=str(auth)))
        Path(self.args.startup_config).write_text(json.dumps(self.binding));Path(self.args.startup_config).chmod(0o600)
        self.selection['components']['mcp']=dict(configuration_digest=startup.digest(startup_guard.input_binding(
            self.binding,self.args)),payload_digest='c'*64,entry='local',running=True)
        self.selection['members']=[dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for path in (self.member,config,auth,Path(self.args.startup_config))]
        self.publish(self.selection)

    def test_recovery_binding_is_in_selected_digest_and_cannot_change_before_bind(self):
        declaration = {'schema': 'local-hand-retained-filesystem/v1',
            'policy_path': self.args.config, 'policy_sha256': 'e'*64,
            'original_root': {}, 'filesystem': {}}
        original = startup_guard.input_binding(self.binding, self.args)
        self.binding['retained_filesystems'] = {self.args.config: declaration}
        changed = startup_guard.input_binding(self.binding, self.args)
        self.assertNotEqual(startup.digest(original), startup.digest(changed))
        config_path = Path(self.args.startup_config)
        config_path.write_text(json.dumps(self.binding))
        for member in self.selection['members']:
            if member['path'] == str(config_path):
                member['sha256'] = hashlib.sha256(config_path.read_bytes()).hexdigest()
        with patch.object(startup, 'remote_authorization', self.remote()), \
             patch.object(startup_guard, 'full_payload_digest', return_value='c'*64):
            with self.assertRaises(JobError):
                with startup_guard.guard(self.args):
                    self.fail('Changed binding must not be admitted by old digest')
            self.selection['components']['mcp']['configuration_digest'] = startup.digest(changed)
            with startup_guard.guard(self.args) as guarded:
                self.assertEqual(self.binding['retained_filesystems'], guarded['filesystem_bindings'])
                self.binding['retained_filesystems'][self.args.config]['policy_sha256'] = 'f'*64
                config_path.write_text(json.dumps(self.binding))
                with self.assertRaises(JobError):
                    guarded['bind']()

    def remote(self, ack=None, exit_error=None):
        @contextmanager
        def selected(_):
            def bound(proof):
                self.assertEqual(self.selection['components']['mcp']['configuration_digest'],proof['configuration_digest'])
                if ack is not None:raise ack
            yield self.selection,bound
            if exit_error is not None:raise exit_error
        return selected

    def test_successful_guard_binds_only_loopback_and_closes_no_successful_socket(self):
        with patch.object(startup,'remote_authorization',self.remote()), \
                patch.object(startup_guard,'full_payload_digest',return_value='c'*64):
            with startup_guard.guard(self.args) as guarded:
                listener=guarded['bind']()
                self.assertEqual(('127.0.0.1',self.args.port),listener.getsockname())
            self.assertGreaterEqual(listener.fileno(),0)
            listener.close()

    def test_guarded_unix_listener_is_bound_and_cleaned_without_tcp_exposure(self):
        self.args.port=None;self.args.http_socket=str(self.root/'http.sock');self.args.http_socket_mode=0o660
        self.binding.update(port=None,unix_socket={'path':self.args.http_socket,'mode':0o660})
        Path(self.args.startup_config).write_text(json.dumps(self.binding))
        self.selection['components']['mcp']['configuration_digest']=startup.digest(startup_guard.input_binding(self.binding,self.args))
        for member in self.selection['members']:
            member['sha256']=hashlib.sha256(Path(member['path']).read_bytes()).hexdigest()
        with patch.object(startup,'remote_authorization',self.remote()),patch.object(startup_guard,'full_payload_digest',return_value='c'*64):
            with startup_guard.guard(self.args) as guarded:
                listener=guarded['bind']()
                self.assertEqual(socket.AF_UNIX,listener.family)
                self.assertEqual(self.args.http_socket,listener.getsockname())
            self.assertEqual(0o660,Path(self.args.http_socket).stat().st_mode & 0o777)
            with socket.socket(socket.AF_UNIX) as peer:
                peer.connect(self.args.http_socket)
                accepted,_=listener.accept();accepted.close()
            guarded['cleanup']()
            self.assertFalse(Path(self.args.http_socket).exists())

    def test_unix_listener_rejects_live_peer_and_preserves_foreign_files(self):
        path=self.root/'http.sock';spec={'path':str(path),'mode':0o600}
        path.write_bytes(b'original')
        with self.assertRaises(JobError):startup_guard.bind_unix(spec)
        self.assertEqual(b'original',path.read_bytes());path.unlink()
        listener,cleanup=startup_guard.bind_unix(spec)
        try:
            with self.assertRaises(JobError):startup_guard.bind_unix(spec)
        finally:cleanup()
        stale=socket.socket(socket.AF_UNIX);stale.bind(str(path));path.chmod(0o600);stale.close()
        listener,cleanup=startup_guard.bind_unix(spec)
        try:self.assertGreaterEqual(listener.fileno(),0)
        finally:cleanup()

    def test_unix_cleanup_does_not_remove_independent_replacement(self):
        path=self.root/'http.sock';listener,cleanup=startup_guard.bind_unix({'path':str(path),'mode':0o600})
        path.unlink();path.write_bytes(b'replacement');cleanup()
        self.assertEqual(b'replacement',path.read_bytes())

    def test_lost_ack_and_guard_exit_failure_close_prebound_socket(self):
        for ack,exit_error in ((JobError('STARTUP_UNKNOWN','lost ack'),None),
                               (None,JobError('STARTUP_UNKNOWN','lost authorization'))):
            with self.subTest(ack=ack),patch.object(startup,'remote_authorization',self.remote(ack,exit_error)), \
                    patch.object(startup_guard,'full_payload_digest',return_value='c'*64):
                with self.assertRaises(JobError):
                    with startup_guard.guard(self.args) as guarded:guarded['bind']()
                self.assertEqual(-1,guarded['listener'].fileno())
                with socket.socket() as available:available.bind(('127.0.0.1',self.args.port))

    def test_changed_input_or_guard_file_before_bind_prevents_protocol_open(self):
        for path in (self.args.config,self.args.startup_config):
            original=Path(path).read_bytes()
            with self.subTest(path=path),patch.object(startup,'remote_authorization',self.remote()), \
                    patch.object(startup_guard,'full_payload_digest',return_value='c'*64):
                try:
                    with self.assertRaises(JobError):
                        with startup_guard.guard(self.args) as guarded:
                            Path(path).write_bytes(original+b' ');guarded['bind']()
                    self.assertIsNone(guarded['listener'])
                finally:Path(path).write_bytes(original)

    def test_guard_file_itself_must_belong_to_complete_selection(self):
        self.selection['members']=[m for m in self.selection['members'] if m['path']!=self.args.startup_config]
        with patch.object(startup,'remote_authorization',self.remote()), \
                patch.object(startup_guard,'full_payload_digest',return_value='c'*64):
            with self.assertRaises(JobError):
                with startup_guard.guard(self.args):pass

    def test_session_mode_cannot_claim_guarded_final_task_admission(self):
        args=copy.copy(self.args);args.read_only=False;args.session='/synthetic/session'
        config=dict(self.binding,mode='session',inputs=dict(self.binding['inputs'],session=args.session))
        with self.assertRaises(JobError):startup_guard.invocation_paths(config,args)

    def test_real_framed_handshake_releases_lock_only_after_bound_ack(self):
        left,right=socket.socketpair();errors=[];end=time.monotonic()+3
        def manager():
            with left:
                try:startup.serve_authorization(left,self.config,self.gate,peer_pid=os.getpid())
                except BaseException as exc:errors.append(exc)
        worker=threading.Thread(target=manager);worker.start()
        with right:
            selected=startup._frame_read(right,end)['selection']
            proof={**startup.instance(os.getpid()),'component':'mcp','entry':'local','node_id':'test-node',
                   'deployment_digest':'a'*64,'configuration_digest':selected['components']['mcp']['configuration_digest'],
                   'payload_digest':'c'*64}
            done=threading.Event()
            closer=threading.Thread(target=lambda:(self.gate.close('deploy'),done.set()));closer.start()
            self.assertFalse(done.wait(.1))
            startup._frame_send(right,dict(action='startup_bound',proof=proof),end)
            self.assertEqual({'bound':True,'descriptor_digest':startup.digest(selected)},startup._frame_read(right,end))
        worker.join(3);closer.join(3)
        self.assertFalse(worker.is_alive());self.assertTrue(done.is_set());self.assertEqual([],errors)

    def test_disconnect_releases_remote_startup_lock_without_open_permission(self):
        left,right=socket.socketpair();errors=[]
        def manager():
            with left:
                try:startup.serve_authorization(left,self.config,self.gate,peer_pid=os.getpid())
                except BaseException as exc:errors.append(exc)
        worker=threading.Thread(target=manager);worker.start()
        startup._frame_read(right,time.monotonic()+3);right.close();worker.join(3)
        self.assertFalse(worker.is_alive());self.assertEqual(1,len(errors));self.assertIsInstance(errors[0],JobError)
        self.assertEqual('CLOSED',self.gate.close('deploy')['state'])


class MCPMainTests(unittest.TestCase):
    def setUp(self):
        for name in ('local_hand_mcp.auth','local_hand_mcp.requests'):
            logger=logging.getLogger(name)
            handlers,level,propagate=list(logger.handlers),logger.level,logger.propagate
            def restore(logger=logger,handlers=handlers,level=level,propagate=propagate):
                for handler in list(logger.handlers):
                    if handler not in handlers:logger.removeHandler(handler);handler.close()
                logger.setLevel(level);logger.propagate=propagate
            self.addCleanup(restore)

    def test_secondary_and_http_listeners_wait_for_startup_ack(self):
        from unittest.mock import Mock
        from local_hand_mcp import server
        try:
            import uvicorn
        except ImportError:
            self.skipTest('Optional MCP runtime is unavailable')
        for denied in (False, True):
            events=[];listener=None
            broker=Mock();broker.policy=SimpleNamespace(local_peers={},principals={},broker_root='/synthetic')
            maintenance_server=Mock()
            maintenance_server.start.side_effect=lambda:events.append('secondary-open')
            @contextmanager
            def guard(args):
                nonlocal listener
                events.append('guard-held')
                def bind():
                    nonlocal listener
                    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
                    if denied:
                        listener.close()
                        raise JobError('STARTUP_UNKNOWN','missing ACK')
                    events.append('ack')
                    return listener
                yield {'bind':bind,'proof':{'protocol_ready':False},'filesystem_bindings':{'/original':'selected-declaration'}}
                events.append('guard-released')
            def run(*args,**kwargs):
                events.append('http-start')
                self.assertEqual(listener.fileno(),kwargs['fd'])
                self.assertNotIn('port',kwargs)
            with self.subTest(denied=denied), patch.object(server,'_require_optional'), \
                    patch.object(startup_guard,'guard',guard), \
                    patch('local_hand_mcp.auth.AuthConfig.from_file',return_value=Mock()) as auth, \
                    patch('local_hand_mcp.auth.JWTVerifier',return_value=Mock()), \
                    patch('local_hand_jobs.cli.create_retained_broker',return_value=broker) as create, \
                    patch('local_hand_jobs.deployment.release_identity',return_value={}), \
                    patch('local_hand_jobs.cli.MaintenanceServer',return_value=maintenance_server), \
                    patch('local_hand_jobs.cli.close_service') as close, \
                    patch.object(server,'create_app',return_value=Mock()), \
                    patch.object(uvicorn,'run',side_effect=run):
                result=server.main(['--config','/synthetic','--read-only','--auth-config','/synthetic/auth',
                                    '--port','8765','--startup-config','/synthetic/startup'])
                self.assertEqual(2 if denied else 0,result)
                auth.assert_called_once_with('/synthetic/auth', allow_administrator_owned=True)
                self.assertEqual({'/original':'selected-declaration'},create.call_args.kwargs['filesystem_bindings'])
                self.assertEqual(['guard-held'] if denied else
                    ['guard-held','ack','guard-released','secondary-open','http-start'],events)
                self.assertEqual(-1,listener.fileno())
                close.assert_called_once()

    def test_unguarded_entry_keeps_private_auth_file_contract(self):
        from local_hand_mcp import server
        @contextmanager
        def unguarded(args): yield None
        with patch.object(server, '_require_optional'), patch.object(startup_guard, 'guard', unguarded), \
                patch('local_hand_mcp.auth.AuthConfig.from_file', side_effect=ValueError('fixture')) as auth:
            self.assertEqual(2, server.main(['--config', '/synthetic', '--read-only',
                '--auth-config', '/synthetic/auth', '--port', '8765']))
            auth.assert_called_once_with('/synthetic/auth')


if __name__=='__main__':unittest.main()
