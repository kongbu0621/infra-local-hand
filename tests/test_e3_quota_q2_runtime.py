"""Modeled systemd/proc facts, real native-validator/pipe/socket framing.

Socket transport runs only where permitted; this is not the Q3 host harness.
"""
import copy
import hashlib
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import unittest
from unittest import mock

from local_hand_jobs import quota_contract as q, quota_grant as g
from q2_fixtures import grant_data, capacity, SECOND
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import q2_config as c, q2_runtime as r, q2_listener as l
    from admin.local_hand_quota_observer import admission as a
    from test_e3_quota_monitor import report


def declaration():
    cap = capacity(); grant = grant_data()
    grant["query_parent"]["path"] = "/lhqquery.slice"
    grant["management_parent"]["path"] = "/lhqcontrol.slice"
    grant["management"]["stop_ns"] = SECOND // 10
    for stage in grant["management"]["stages"].values(): stage["memory_bytes"] = 16*1024**2
    grant["endpoint"]["gid"] = grant["roots"][0]["gid"]
    key = grant["request"]["request_id"]
    return {"schema":"local-hand-quota-service/v1", "source_commit":"c"*40, "tools_path":"/synthetic/code/tools",
        "entry":{"path":"/synthetic/code/tools/admin/local_hand_quota_observer/q2_entry.py","sha256":"e"*64},
        "package_files":{"admin/local_hand_quota_observer/"+name+".py":"e"*64 for name in
            ("q2_config","q2_runtime","q2_listener","q2_journal","q2_service")},
        "programs":{name:{"path":"/synthetic/bin/"+name,"sha256":"b"*64} for name in ("python","native","systemctl","systemd_run")},
        "abi":{"fsxattr_bytes":28,"dqblk_bytes":72,"qstatv_bytes":160},
        "initial_userns":{"device":4,"inode":123}, "capacity":cap, "grants":{key:grant},
        "peers":{key:{"parent":{"path":"/synthetic-job.slice","device":4,"inode":124},
            "executable":{"path":"/synthetic/bin/python","device":7,"inode":125}, "command_sha256":"d"*64}},
        "journal":{"path":"/synthetic/journal","pin":{"directory":{"device":7,"inode":310},
            "files":{name:{"device":7,"inode":320+i} for i,name in enumerate(("lock","policy",key+".cell"))}}},
        "evidence":{"path":"/synthetic/evidence","device":7,"inode":300},
        "session":{"path":"/synthetic/session","device":7,"inode":301},
        "service":{"request_id":key,"parent":grant["management_parent"],"control_path":"/synthetic/control/private.sock",
                   "accept_ns":SECOND,"end_ns":11*SECOND,"max_connections":4}}


def config(value=None):
    value = declaration() if value is None else value
    raw = q._canonical(value,c.LIMIT)
    return c.decode(raw,"/synthetic/config.json",hashlib.sha256(raw).hexdigest())


def fixture_open(path, *, directory=False):
    """Model protected administrator ownership; retain real nofollow FDs/I/O."""
    return os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | (os.O_DIRECTORY if directory else 0))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux administrative runtime")
class ConfigAndRuntimeTests(unittest.TestCase):
    def test_config_and_fixed_three_unit_commands(self):
        cfg = config()
        for role, prefix in (("listener","lhqoc-"),("admission","lhqoa-"),("query","lhqo-")):
            argv = r.command(cfg,role,now_ns=2*SECOND)
            self.assertIn("--unit="+prefix+cfg.active().request.digest+".service",argv)
            self.assertIn("--property=Restart=no",argv)
            self.assertIn("--property=MemorySwapMax=0",argv)
            self.assertIn("--property=KillMode=control-group",argv)
            self.assertEqual(role,argv[-3])
            caps = next(item for item in argv if item.startswith("--property=CapabilityBoundingSet="))
            self.assertEqual(role=="query","CAP_SYS_ADMIN" in caps)
            self.assertIn("--property=Group="+(str(cfg.active().as_dict()["endpoint"]["gid"]) if role=="listener" else "0"),argv)
            runtime=int(next(x for x in argv if x.startswith("--property=RuntimeMaxSec=")).split("=")[-1][:-2])*1000
            self.assertLessEqual(runtime+cfg.active().as_dict()["management"]["stop_ns"],r.limits(cfg,role)["runtime_ns"])
        with self.assertRaises(q.QuotaError): r.command(cfg,"query",now_ns=11*SECOND)
        with self.assertRaises(q.QuotaError): r.command(cfg,"listener",now_ns=11*SECOND-SECOND//10)

    def test_administrative_roles_drop_all_unneeded_capabilities(self):
        for role,mask in (("listener",1),("admission",(1<<2)|(1<<19))):
            value={"CapPrm":mask,"CapEff":mask,"CapBnd":mask,"CapInh":0,"CapAmb":0}
            raw="".join(k+": "+format(v,"016x")+"\n" for k,v in value.items())+"NoNewPrivs: 1\n"
            r.capabilities(raw.encode(),role)
            for bad in (raw.replace("NoNewPrivs: 1","NoNewPrivs: 0"),raw+"CapInh: 0000000000000000\n",
                        raw.replace(format(mask,"016x"),format(mask|(1<<21),"016x"))):
                with self.assertRaises(q.QuotaError):r.capabilities(bad.encode(),role)

    def test_wire_paths_and_overlapping_control_geometry_rejected(self):
        for fault in ("root", "program", "endpoint", "group", "budget", "alias", "pin"):
            value = declaration(); grant = next(iter(value["grants"].values()))
            if fault == "root": value["tools_path"] = "/synthetic/slot-0/work"
            if fault == "program": value["programs"]["python"]["path"] = "/synthetic/code/tools/python"
            if fault == "endpoint": value["service"]["control_path"] = grant["endpoint"]["path"]
            if fault == "group": grant["endpoint"]["gid"] = 0
            if fault == "budget": grant["management"]["stages"]["admission"]["memory_bytes"] = 1
            if fault == "alias": value["package_files"].update({"local_hand_jobs/quota.py":"e"*64,"local_hand_jobs/quota/__init__.py":"e"*64})
            if fault == "pin": value["journal"]["pin"]["files"].pop("lock")
            with self.subTest(fault=fault), self.assertRaises(q.QuotaError): config(value)

    def bundle(self,cfg):
        identity = {"unit":cfg.active().request.query_unit,"invocation_id":"a"*32,
                    "cgroup":cfg.active().as_dict()["query_parent"]["path"]+"/"+cfg.active().request.query_unit}
        bundle = {"schema":"local-hand-quota-native-set/v1","config_digest":cfg.digest,
                  "request_digest":cfg.active().request.digest,"query":identity,"reports":[]}
        for root in cfg.active().as_dict()["roots"]:
            context, slot = r.native_context(cfg,root); native = report(context)
            for key in ("project","project_after"): native[key] = {"id":root["project_id"],"xflags":root["xflags"]}
            native["restriction"]["project_id"] = root["project_id"]
            native["quota"].update(hard_blocks_1024=root["hard_bytes"]//1024,hard_bytes=root["hard_bytes"])
            # Successful syscall errno is retained rather than rewritten.
            native["calls"][6]["errno"] = 17
            bundle["reports"].append({"role":root["role"],"stdout":q._canonical(native,4094).decode()+"\n","stderr":"","rc":0})
        return bundle,identity

    def test_three_roots_each_validate_native_abi_quota_and_actual_errno(self):
        cfg=config(); bundle,identity=self.bundle(cfg)
        roots,calls=r.reports(cfg,q._canonical(bundle,q.RESPONSE_LIMIT),identity)
        self.assertEqual(cfg.active().as_dict()["roots"],roots)
        self.assertEqual(9,len(calls)); self.assertEqual(17,calls[0]["errno"])
        for fault in ("missing", "root", "foreign", "eof", "exit"):
            candidate=copy.deepcopy(bundle)
            if fault=="missing": candidate["reports"].pop()
            if fault=="foreign": candidate["query"]["invocation_id"]="f"*32
            if fault=="eof": candidate["reports"][0]["stdout"]=candidate["reports"][0]["stdout"].rstrip()
            if fault=="exit": candidate["reports"][0]["rc"]=2
            if fault=="root":
                raw=q._load(candidate["reports"][0]["stdout"].encode(),4095,8);raw["root"]["inode"]+=1
                candidate["reports"][0]["stdout"]=q._canonical(raw,4094).decode()+"\n"
            with self.subTest(fault=fault),self.assertRaises((q.QuotaError,a.Rejected)):
                r.reports(cfg,q._canonical(candidate,q.RESPONSE_LIMIT),identity)

    def test_session_consumption_is_permanent_after_first_fsync(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as directory:
            path=Path(directory)/"session";path.touch(mode=0o600)
            value=declaration();info=path.stat();value["session"]={"path":str(path),"device":info.st_dev,"inode":info.st_ino}
            cfg=config(value)
            with mock.patch.object(r,"host",return_value={"invocation_id":"a"*32}),\
                 mock.patch.object(c,"open_protected",side_effect=fixture_open):
                l.reserve_session(cfg)
                original=path.read_bytes()
                with self.assertRaises(q.QuotaError):l.reserve_session(cfg)
            self.assertEqual(original,path.read_bytes())


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux listener framing")
class FrameTests(unittest.TestCase):
    def test_readiness_permission_published_only_after_listen(self):
        # Modeled setup interleavings; even an initial umask that would create
        # mode 600 cannot publish readiness before listen. Named IPC is tested
        # separately where the executor permits it.
        for seqpacket in (False,True):
            for fault in (None,'bind','listen'):
                with self.subTest(seqpacket=seqpacket,fault=fault):
                    calls=[];mask=[0o177];mode=[None];listening=[False];nonblocking=[False]
                    def umask(value):old=mask[0];mask[0]=value;return old
                    def bind(path):
                        self.assertEqual(0o777,mask[0]);mode[0]=0
                        if fault=='bind':raise OSError('bind fault')
                    def listen(backlog):
                        self.assertEqual(0,mode[0]);self.assertEqual(0o177,mask[0])
                        if fault=='listen':raise OSError('listen fault')
                        listening[0]=True
                    def setblocking(value):nonblocking[0]=not value
                    def chmod(path,value,**kwargs):
                        self.assertTrue(listening[0] and nonblocking[0]);mode[0]=value;calls.append('published')
                    sock=mock.Mock(bind=bind,listen=listen,setblocking=setblocking)
                    parent=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
                    with mock.patch.object(c,'open_protected',return_value=parent),\
                         mock.patch.object(l.socket,'socket',return_value=sock),\
                         mock.patch.object(l.os,'umask',side_effect=umask),\
                         mock.patch.object(l.os,'chown'),mock.patch.object(l.os,'chmod',side_effect=chmod):
                        if fault:
                            with self.assertRaises(OSError):l.bind('/synthetic/socket',seqpacket=seqpacket)
                            self.assertEqual([],calls);sock.close.assert_called_once()
                        else:
                            self.assertIs(sock,l.bind('/synthetic/socket',seqpacket=seqpacket))
                            self.assertEqual(['published'],calls)
                            self.assertEqual(0o600 if seqpacket else 0o660,mode[0])
                        self.assertEqual(0o177,mask[0])

    def test_fragmented_exact_frame_requires_peer_eof(self):
        raw=b'{}';frame=l.Frame(10)
        self.assertIsNone(frame.feed(struct.pack("!I",2)[:2],now=1))
        self.assertIsNone(frame.feed(struct.pack("!I",2)[2:]+raw,now=2))
        self.assertEqual(raw,frame.feed(b"",now=3))
        with self.assertRaises(q.QuotaError):frame.feed(b"",now=4)
    def test_oversize_trailing_and_slow_sender(self):
        for packet,now in ((struct.pack("!I",8193),1),(struct.pack("!I",1)+b'{}',1),(b'a',10)):
            with self.subTest(packet=packet),self.assertRaises(q.QuotaError):l.Frame(10).feed(packet,now=now)
        frame=l.Frame(10);frame.feed(struct.pack("!I",9)+b'{}',now=1)
        with self.assertRaises(q.QuotaError):frame.feed(b'',now=2)
    def test_real_socket_and_descriptor_detection_when_available(self):
        import array
        try:a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
        except PermissionError:self.skipTest("Executor denies AF_UNIX; no IPC success claimed")
        rfd,wfd=os.pipe()
        try:
            a.sendmsg([b'x'],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[rfd]))])
            raw,items,flags,_=b.recvmsg(1,socket.CMSG_SPACE(16),socket.MSG_CMSG_CLOEXEC)
            received=l.ancillary(items)
            try:
                self.assertEqual(b'x',raw);self.assertEqual(1,len(received));self.assertFalse(os.get_inheritable(received[0]))
            finally:
                for fd in received:os.close(fd)
        finally:a.close();b.close();os.close(rfd);os.close(wfd)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux real local listener IPC")
class ListenerIPCTests(unittest.TestCase):
    def setUp(self):
        try:
            check=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);check.close()
        except PermissionError:self.skipTest("AF_UNIX unavailable")

    def test_real_fd_handoff_request_and_response_with_supervision_modeled(self):
        import array
        import threading
        import time
        with tempfile.TemporaryDirectory(dir=Path.home()) as directory:
            value=declaration();grant=next(iter(value['grants'].values()))
            grant['endpoint']['path']=directory+'/public.sock'
            value['service']['control_path']=directory+'/private.sock'
            cfg=config(value);failures=[]
            def serve():
                try:l.listener(cfg)
                except BaseException as error:failures.append(error)
            # Supervised attestation and root ownership are modeled, allowing
            # the same transport check on unprivileged Linux CI.
            # Frames, SO_PEERCRED, FD passing, EOF and disconnect are real.
            real_chown=os.chown
            with mock.patch.object(r,'host',return_value={}),mock.patch.object(l.peer,'control',return_value=os.getpid()),\
                 mock.patch.object(l,'boottime_ns',return_value=2*SECOND),mock.patch.object(c,'open_protected',side_effect=fixture_open),\
                 mock.patch.object(l.os,'chown',side_effect=lambda path,uid,gid,**kw:real_chown(path,os.getuid(),os.getgid(),**kw)):
                thread=threading.Thread(target=serve,daemon=True);thread.start()
                worker=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);worker.settimeout(2)
                limit=time.monotonic()+2
                def wait_ready(path,mode):
                    while time.monotonic()<limit:
                        try:ready=Path(path).stat().st_mode & 0o777 == mode
                        except FileNotFoundError:ready=False
                        if ready:return
                        time.sleep(.001)
                    self.fail('listener did not publish readiness')
                wait_ready(value['service']['control_path'],0o600)
                worker.connect(value['service']['control_path'])
                wait_ready(grant['endpoint']['path'],0o660)
                wrong=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);wrong.connect(grant['endpoint']['path'])
                rfd,wfd=os.pipe()
                try:wrong.sendmsg([b'x'],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[rfd]))])
                finally:os.close(rfd);os.close(wfd);wrong.close()
                client=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);client.settimeout(2);client.connect(grant['endpoint']['path'])
                raw=cfg.active().request.wire
                client.sendall(struct.pack('!I',len(raw))+raw);client.shutdown(socket.SHUT_WR)
                data,items,flags,_=worker.recvmsg(q.REQUEST_LIMIT,socket.CMSG_SPACE(16),socket.MSG_CMSG_CLOEXEC)
                self.assertEqual(raw,data);self.assertEqual(0,flags & ~socket.MSG_CMSG_CLOEXEC)
                fds=l.ancillary(items);self.assertEqual(1,len(fds))
                with socket.socket(fileno=fds[0]) as passed:
                    pid,uid,gid=l.peer.credentials(passed)
                    self.assertEqual((os.getpid(),os.getuid(),os.getgid()),(pid,uid,gid))
                    passed.sendall(b'result');passed.shutdown(socket.SHUT_WR)
                self.assertEqual(b'result',client.recv(6));self.assertEqual(b'',client.recv(1))
                worker.sendall(b'1');thread.join(2)
                client.close();worker.close()
                self.assertFalse(thread.is_alive());self.assertEqual([],failures)
                # The first endpoint remains a restart/replay barrier.
                with self.assertRaises(OSError):l.bind(grant['endpoint']['path'])


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux supervised dispatcher model")
class DispatcherTests(unittest.TestCase):
    bundle = ConfigAndRuntimeTests.bundle

    def test_fixed_dispatch_evidence_and_unknown_failure_have_no_retry(self):
        from types import SimpleNamespace
        for fault in (None,'eof','invocation','exit'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(dir=Path.home()) as directory:
                value=declaration();info=os.stat(directory)
                value['evidence']={'path':directory,'device':info.st_dev,'inode':info.st_ino}
                cfg=config(value);bundle,identity=self.bundle(cfg)
                if fault=='invocation':bundle['query']['invocation_id']='f'*32
                class Capture:
                    def __init__(self,limit):
                        self.stdout=bytearray(q._canonical(bundle,q.RESPONSE_LIMIT));self.stderr=bytearray()
                        self.done=self.settled=fault!='eof';self.eof=set() if fault=='eof' else {'stdout','stderr'}
                        self.error=None;self.process=SimpleNamespace(returncode=0,poll=lambda:0)
                    def start(self,argv):self.argv=argv
                    def pump(self):pass
                    def close_pipes(self):pass
                terminal={'Id':identity['unit'],'LoadState':'loaded','InvocationID':'a'*32,'ControlGroup':identity['cgroup'],
                    'Slice':'lhqquery.slice','Type':'exec','ExitType':'cgroup','RemainAfterExit':'yes','Restart':'no',
                    'KillMode':'control-group','ExecStop':'','ExecStopPost':'','ExecReload':'','TriggeredBy':'',
                    'ActiveState':'active','SubState':'exited','Job':'','Result':'exit-code' if fault=='exit' else 'success',
                    'ExecMainCode':'1','ExecMainStatus':'2' if fault=='exit' else '0'}
                terminal.update(dict.fromkeys(r.UnitTransport.extra_fields, ''))
                dispatch=r.Dispatcher(cfg);remember=[]
                with mock.patch.object(r,'Capture',Capture),mock.patch.object(r,'host',return_value={}),mock.patch.object(r,'boottime_ns',return_value=2*SECOND),\
                     mock.patch.object(c,'open_protected',side_effect=fixture_open),\
                     mock.patch.object(dispatch,'_parent_empty',return_value=True),\
                     mock.patch.object(dispatch,'_show',side_effect=[dict(terminal,LoadState='not-found'),terminal]),\
                     mock.patch.object(dispatch,'_stop_original',return_value=fault!='eof'):
                    raw=dispatch(cfg.active(),r.deadline(cfg,'query'),remember.append)
                    result=q.decode_receipt(raw,cfg.active().request,cfg.active().as_dict()['roots'],now_ns=2*SECOND)
                    self.assertEqual('OBSERVED' if fault is None else 'UNKNOWN',result.as_dict()['status'])
                    with self.assertRaises(q.QuotaError):dispatch(cfg.active(),r.deadline(cfg,'query'),remember.append)
                self.assertEqual(1,len(remember));self.assertEqual(1,len(list(Path(directory).iterdir())))
