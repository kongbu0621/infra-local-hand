"""Actual 121/122-FD admission, inherited identity and full output lifetime at limit 128."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux fork, pidfd and descriptor admission', allow_module_level=True)

CHILD = r'''
import errno,hashlib,json,os,resource,sys,time
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
from e3_host import q2_journal_retained_fds as c
from e3_host import q2_journal_growth as h
path,mode,initial=sys.argv[2:]
initial=int(initial)
original_child=c.child
def debug_child(*args):
    try:
        if mode=='live_cpu':
            end=time.process_time()+.08
            while time.process_time()<end:pass
        return original_child(*args)
    except BaseException:
        import traceback
        traceback.print_exc()
        raise
c.child=debug_child
resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
resource.setrlimit(resource.RLIMIT_AS,(256*1048576,256*1048576))
os.chmod(path,0o700)
anchor=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
rows=[];pins={}
for i in range(55):
    name='evidence'+str(i)
    fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC|os.O_NOATIME,0o600,dir_fd=anchor)
    raw=('retained '+str(i)).encode();os.write(fd,raw);os.close(fd)
    fd=os.open(name,os.O_RDONLY|os.O_CLOEXEC|os.O_NOATIME,dir_fd=anchor)
    rows.append((name,fd,c.metadata(os.fstat(fd))));pins[name]=(len(raw),c.sha(raw))
start=time.monotonic()
def remaining():
    value=20-(time.monotonic()-start)
    c.need(value>0,'WINDOW');return value
a=SimpleNamespace(fd=anchor,info=c.metadata(os.fstat(anchor)),held=rows.copy(),deadline=SimpleNamespace(remaining=remaining))
def count():
    n=0
    for fd in range(128):
        try:os.fstat(fd)
        except OSError as e:assert e.errno==errno.EBADF
        else:n+=1
    return n
fill=[]
while count()<initial:fill.append(os.open(os.devnull,os.O_RDONLY|os.O_CLOEXEC))
assert count()==initial
if mode in ('bad_ready','bool_ready','missing_ready','wrong_D','truncated','timeout'):
    old=c.Channel.send
    def wrong(self,value,limit,end):
        if value['op']=='READY':
            if mode=='bad_ready':value=dict(value,seq=1)
            elif mode=='bool_ready':value=dict(value,seq=False)
            elif mode=='missing_ready':value={k:v for k,v in value.items() if k!='count'}
            elif mode=='wrong_D':value=dict(value,binding=dict(value['binding'],D='f'*40))
            elif mode=='timeout':time.sleep(5.1)
            elif mode=='truncated':
                self.sock.send(b'\x00\x00\x01\x00{}');self.sock.close();return
        return old(self,value,limit,end)
    c.Channel.send=wrong
if mode=='fork_failure':
    def nofork():raise OSError(errno.EAGAIN,'injected fork failure')
    c.os.fork=nofork
if mode in ('bad_ready','bool_ready','missing_ready','wrong_D','truncated','timeout','fork_failure'):
    try:c.Custodian(a,pins,commit='d'*40,nonce='a'*64,source_sha256='b'*64,history_sha256='c'*64)
    except (RuntimeError,OSError):pass
    else:raise AssertionError('admitted failed handoff')
    assert len(a.held)==55 and count()==initial
    for _,fd,_ in rows:os.fstat(fd)
    print(json.dumps(dict(mode=mode,retained=True)));sys.exit(0)
# Verify shared file position before the parent surrenders its copies.
original_response=c.Custodian.response
def response(self,op,seq,end=None):
    result=original_response(self,op,seq,end)
    if op=='READY':
        fd=rows[0][1];os.lseek(fd,2,os.SEEK_SET)
        info=c.proc(self.pid,'fdinfo/'+str(fd),4096)
        assert b'pos:\t2\n' in info
        os.lseek(fd,0,os.SEEK_SET)
    return result
c.Custodian.response=response
held=c.Custodian(a,pins,commit='d'*40,nonce='a'*64,source_sha256='b'*64,history_sha256='c'*64)
assert a.held==[] and count()==initial-53
h.host_fd_admission(anchor,lambda:None,'after_transfer')
assert count()==initial-53
# The child inherited the very same open-file description; change its offset
# via a retained alias and observe it through the child's /proc descriptor.
assert len(c.ACTIVE)==1
if mode=='live_cpu':assert held.usage()[0]>=.07
if mode in ('replace','delete','content','link','mode','sequence','nonce','child_exit','unknown_usage','check_limit'):
    if mode=='replace':
        os.rename(path+'/evidence0',path+'/old0')
        fd=os.open(path+'/evidence0',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    elif mode=='delete':os.unlink(path+'/evidence0')
    elif mode=='content':
        fd=os.open(path+'/evidence0',os.O_WRONLY);os.write(fd,b'changed');os.close(fd)
    elif mode=='link':os.link(path+'/evidence0',path+'/alias')
    elif mode=='mode':os.chmod(path+'/evidence0',0o644)
    elif mode=='sequence':held.sequence=2
    elif mode=='nonce':held.binding=dict(held.binding,nonce='e'*64)
    elif mode=='child_exit':held.channel.sock.shutdown(2)
    elif mode=='unknown_usage':
        original_proc=c.proc
        def missing(pid,name,limit):
            return b'' if name=='status' else original_proc(pid,name,limit)
        c.proc=missing
    elif mode=='check_limit':held.sequence=64
    try:held.check(True)
    except (RuntimeError,OSError,KeyError):pass
    else:raise AssertionError('admitted identity/protocol failure')
    try:held.close()
    except (RuntimeError,OSError,KeyError):pass
    assert not c.ACTIVE and count()==initial-55
    try:os.waitpid(held.pid,os.WNOHANG)
    except ChildProcessError:pass
    else:raise AssertionError('unreaped child')
    print(json.dumps(dict(mode=mode,rejected=True)));sys.exit(0)
# Actual pre pipes + selector and all nine persistent outputs, then post, receipt.
# Synthetic local peers replace remote SSH and VM; no host field observation.
exe=os.open(sys.executable,os.O_PATH|os.O_CLOEXEC)
store=h.Store(anchor,lambda:None)
store.put('consumed.json',b'{}\n');store.event(dict(synthetic=True))
for phase in ('pre','post'):
    peer=[sys.executable,'-I','-B','-c','import sys; sys.stdout.write("{\\"ok\\":true}\\n"); sys.stdout.flush()']
    t=h.MaintenanceTransport(SimpleNamespace(ssh=exe),store,peer,phase,'1'*64,'2'*64,'unused',lambda:None)
    # Exercise the real Popen/selector/pipe lifecycle without parsing a guest report.
    t.process.wait(timeout=5)
    t.close()
    held.check(True)
    if phase=='pre':
        store.put('journal.backup.qcow2',b'backup')
        store.put('vm.pid',b'123\n')
        simulated_vm_pidfd=os.pidfd_open(os.getpid())
store.put('receipt.json',b'{}\n')
held.check(True)
summary=held.summary();cpu,rss=held.usage()
own=resource.getrusage(resource.RUSAGE_SELF);done=resource.getrusage(resource.RUSAGE_CHILDREN)
minimum=own.ru_utime+own.ru_stime+done.ru_utime+done.ru_stime+held.usage()[0]
usage=h.management_usage()
assert usage['cpu_seconds']>=minimum
assert usage['live_children']==1 and usage['rss_upper_observation_bytes']>=rss
assert summary['checks']==3 and 0<summary['ipc_bytes']<=2*1048576
store.close();os.close(exe);os.close(simulated_vm_pidfd)
final=held.close()
assert final['returncode']==0 and final['cpu_nanoseconds']>=summary['cpu_nanoseconds']
assert final['rss_peak_bytes']>=summary['rss_bytes'] and count()==initial-55,(final,summary['rss_bytes'],count())
assert not c.ACTIVE
print(json.dumps(dict(mode=mode,before=initial,after_transfer=initial-53,after_close=count(),
    cpu_ns=final['cpu_nanoseconds'],rss=final['rss_peak_bytes'])))
'''


@pytest.mark.parametrize('initial',[121,122])
@pytest.mark.parametrize('mode',['lifecycle','live_cpu','bad_ready','bool_ready','missing_ready','wrong_D','truncated','timeout',
    'fork_failure','replace','delete','content','link','mode','sequence','nonce','child_exit','unknown_usage','check_limit'])
def test_bounded_custody_real_process_lifetime(tmp_path,mode,initial):
    result=subprocess.run([sys.executable,'-I','-B','-c',CHILD,str(Path(__file__).parent),
        str(tmp_path),mode,str(initial)],stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr.decode()
    value=json.loads(result.stdout)
    assert value['mode']==mode
