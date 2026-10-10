"""Bounded runtime preparation with injected effects, never a field window."""
import copy
import os
import stat
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux runtime preparation',allow_module_level=True)

from e3_host import q2_journal_growth_guest as g
from e3_host import q2_core_prior_attempt as p
from core_runtime_fixture import binding, inventory, patch, properties, report
from test_e3_q2_journal_growth_guest_completion import description


@pytest.fixture
def runtime(monkeypatch):
    patch(monkeypatch)
    desc=description();baseline=report(desc);trace=[];states={}
    b=binding()
    for role,row in b['parents'].items():
        manager=row['manager'];unit=row['unit'];value=properties(row,active=False)
        value['FragmentPath']=next(v['path'] for v in baseline['configs'] if v['role']==role)
        if role in ('ordinary','retained_ordinary'):
            value.update(LoadState='not-found',FragmentPath='')
        states[manager,unit]=value
    manager=copy.deepcopy(baseline['manager']);manager.update(ActiveState='inactive',SubState='dead',ControlGroup='',InvocationID='',MainPID='0')
    states['system',manager['Id']]=manager
    directory=dict.fromkeys(g.RUNTIME_SHOW,'');directory.update(Id='user-runtime-dir@1100.service',LoadState='loaded',
        ActiveState='inactive',SubState='dead',MainPID='0',ControlPID='0',
        FragmentPath='/usr/lib/systemd/system/user-runtime-dir@.service')
    states['system',directory['Id']]=directory
    class Inventory:
        SHOW=g.GuestInventory.SHOW
        systemctl=copy.deepcopy(baseline['tool'])
        check=staticmethod(lambda:None)
        last_result=None
        context={}
        def ctl(self,args,*,user_uid=None,runtime_missing=False):
            scope='user' if user_uid is not None else 'system'
            trace.append((scope,list(args)))
            self.last_result=dict(returncode=0,both_eof=True,stdout_bytes=0,stderr_bytes=0,
                stdout_sha256=g.digest(b''),stderr_sha256=g.digest(b''))
            if args[0]=='show' and args[2]=='--property='+','.join(self.SHOW):return b'guard'
            if args[0]=='show':
                selected=[states[scope,name] for name in args[4:]]
                raw=('\n\n'.join('\n'.join(key+'='+row[key] for key in g.RUNTIME_SHOW) for row in selected)+'\n').encode()
                self.last_result.update(stdout_bytes=len(raw),stdout_sha256=g.digest(raw))
                return raw
            if args[0]=='start':
                for name in args[2:]:
                    row=states[scope,name]
                    row.update(LoadState='loaded',ActiveState='active',InvocationID='1'*32)
                    if name==directory['Id']:row['SubState']='exited'
                    elif name==manager['Id']:row.update(SubState='running',ControlGroup=b['manager']['control_group'],MainPID='22')
                    else:
                        role=next(role for role,parent in b['parents'].items() if parent['unit']==name)
                        row.update(SubState='active',ControlGroup=b['parents'][role]['control_group'])
            return b''
        def show_many(self,names,**_):return dict.fromkeys(names,{})
        def quiet_service(self,item,value=None):trace.append('quiet:'+item['name'])
        def cgroup(self,path):trace.append('empty:'+path)
        def processes(self):trace.append('processes')
        def persistent(self):trace.append('persistent')
    m=g.GuestMaintenance(desc,window=SimpleNamespace(check=lambda **_:None))
    m.inventory=Inventory()
    class Runtime(g.RuntimePreparation):
        def config(self,role,path,raw,*,create=False,uid=0):
            if create:self.m.once('runtime_config_'+role)
            trace.append(('config',role,create))
            value=copy.deepcopy(next(row for row in baseline['configs'] if row['role']==role))
            value.update(path=path,created=create);self.report['configs'].append(value)
            if create:states[b['parents'][role]['manager'],b['parents'][role]['unit']]['FragmentPath']=path
        def slice_config(self,role,*,user=False):
            if role in ('ordinary','retained_ordinary') and states[b['parents'][role]['manager'],b['parents'][role]['unit']]['LoadState']=='not-found':return None
            value=next(row for row in baseline['configs'] if row['role']==role)
            self.config(role,value['path'],b'')
            return value['path']
        def pool(self,path):
            if not self.report['pools']:self.report['pools']=copy.deepcopy(baseline['pools'])
        def user_directories(self):trace.append('user_directories')
        def bus(self):return copy.deepcopy(baseline['bus'])
        def group(self,row):
            role=next(role for role,parent in b['parents'].items() if parent['unit']==row['unit'])
            return copy.deepcopy(baseline['parents'][role]['cgroup'])
    # Only fixed configuration protected reads are simulated here. Separate
    # tests below exercise actual O_EXCL/no-follow and inode retention.
    fake_fd=987654
    real_stat,real_close=os.fstat,os.close
    monkeypatch.setattr(g,'open_path',lambda *a,**k:fake_fd)
    monkeypatch.setattr(os,'fstat',lambda fd: SimpleNamespace(st_mode=stat.S_IFREG|0o644,st_uid=0,st_gid=0,st_nlink=1) if fd==fake_fd else real_stat(fd))
    monkeypatch.setattr(os,'close',lambda fd:None if fd==fake_fd else real_close(fd))
    monkeypatch.setattr(g.pwd,'getpwuid',lambda uid:SimpleNamespace(pw_name='q2job',pw_uid=1100,pw_gid=1100))
    value=Runtime(m,desc['original_boot_id']);m.runtime=value
    return SimpleNamespace(runtime=value,m=m,trace=trace,states=states,binding=b)


def test_missing_runtime_is_prepared_once_with_complete_current_proof(runtime):
    f=runtime;value=f.runtime.run()
    assert len(g.canonical(value))<=16384
    assert [row['step'] for row in value['commands']]==['guard_units','system_before','system_reload','system_start',
        'system_after','user_before','user_reload','user_start','user_after']
    assert [(row['role'],row['created']) for row in value['configs'] if row['created']]==[('ordinary',True),('retained_ordinary',True)]
    assert f.trace.index('processes')<f.trace.index(('config','ordinary',True))
    assert value['parents']['ordinary']['properties']['TasksMax']=='32'
    assert value['parents']['retained_ordinary']['properties']['TasksMax']=='64'
    before=list(f.trace)
    with pytest.raises(g.r.ObservationError,match='NO_RETRY'):f.runtime.run()
    assert f.trace==before


@pytest.mark.parametrize('phase',['pre','post'])
def test_matching_active_runtime_is_reused_without_mutations(runtime,phase):
    f=runtime;f.m.description['phase']=phase;f.runtime.report['phase']=phase
    expected=report(f.m.description)
    for role,parent in f.binding['parents'].items():
        value=properties(parent,active=True)
        value['FragmentPath']=next(row['path'] for row in expected['configs'] if row['role']==role)
        f.states[parent['manager'],parent['unit']]=value
    f.states['system',f.binding['manager']['unit']]=copy.deepcopy(expected['manager'])
    f.states['system','user-runtime-dir@1100.service'].update(ActiveState='active',SubState='exited')
    # This fixture represents a separate boot for post, with cumulative reserves.
    if phase=='post':
        f.runtime.report['boot_id']='22222222-2222-3333-4444-555555555555'
    def pool(_):
        f.runtime.report['pools']=copy.deepcopy(expected['pools'])
    f.runtime.pool=pool
    value=f.runtime.run()
    assert [row['step'] for row in value['commands']]==[
        'guard_units','system_before','system_after','user_before','user_after']
    assert not any(row['created'] for row in value['configs'])
    assert f.m.started=={'runtime_preparation'}
    assert all(row['reserved_bytes']==8192*(1 if phase=='pre' else 2) for row in value['pools'])


def test_bus_identity_drift_stops_before_maintenance(runtime):
    f=runtime;original=f.runtime.bus;count=0
    def bus():
        nonlocal count
        value=original();count+=1
        if count>1:value['bus'][1]+=1
        return value
    f.runtime.bus=bus
    with pytest.raises(g.r.ObservationError,match='USER_DRIFT'):f.runtime.run()
    assert 'poweroff' not in f.m.started and 'resize2fs' not in f.m.started


def test_runtime_deadline_and_command_ceiling_precede_execution(runtime,monkeypatch):
    f=runtime;before=list(f.trace)
    f.runtime.used=set(str(n) for n in range(12))
    with pytest.raises(g.r.ObservationError,match='COMMAND_REPLAY'):
        f.runtime.command('system_start',['start','--','fixture.slice'])
    assert f.trace==before
    monkeypatch.setattr(g.time,'monotonic_ns',lambda:f.runtime.start[0]+120000000000)
    with pytest.raises(g.r.ObservationError,match='DEADLINE'):f.runtime.check()


def test_core_user_helper_drops_all_credentials_before_held_executable(monkeypatch):
    from test_e3_q2_core_admission import helper_fixture, d
    effects,policy,_=helper_fixture(monkeypatch,'pass')
    policy['argv']=['/usr/bin/systemctl','--user','--no-pager','--no-ask-password','show','fixture.slice']
    policy['environment'].update(XDG_RUNTIME_DIR='/run/user/1100',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1100/bus')
    fake_os=SimpleNamespace(**vars(os));calls=[]
    fake_os.setgroups=lambda groups:calls.append(('groups',groups))
    fake_os.setresgid=lambda *ids:calls.append(('gid',ids))
    fake_os.setresuid=lambda *ids:calls.append(('uid',ids))
    monkeypatch.setattr(d,'os',fake_os)
    monkeypatch.setattr(d,'resource',SimpleNamespace(RLIMIT_CPU=0,setrlimit=lambda *args:calls.append(('cpu',args))))
    def launch(argv,**kwargs):
        assert argv==policy['argv'] and kwargs['env']==policy['environment']
        assert kwargs['executable']=='/proc/self/fd/'+str(kwargs['pass_fds'][0])
        kwargs['preexec_fn']()
        raise d.DispatchError('SYNTHETIC_STOP_BEFORE_EXEC')
    monkeypatch.setattr(d.subprocess,'Popen',launch)
    with pytest.raises(d.DispatchError):d._admit_run_helper(effects,policy,lambda:None,user_uid=1100)
    assert calls[1:]==[('groups',[]),('gid',(1100,1100,1100)),('uid',(1100,1100,1100))]
    assert calls[0][0]=='cpu'


@pytest.mark.parametrize('fault',['failed','activating','job','wrong_limit','wrong_parent','wrong_fragment'])
def test_conflicting_system_target_stops_before_any_runtime_write_or_start(runtime,fault):
    f=runtime;row=f.states['system',f.binding['parents']['controller']['unit']]
    if fault in ('failed','activating'):row['ActiveState']=fault
    elif fault=='job':row['Job']='12'
    elif fault=='wrong_limit':row['TasksMax']='65'
    elif fault=='wrong_parent':row['ControlGroup']='/other.slice'
    else:row['FragmentPath']='/run/other.slice'
    with pytest.raises(g.r.ObservationError):f.runtime.run()
    assert not any(isinstance(row,tuple) and (row[0]=='config' and row[-1] or row[0] in ('system','user') and row[1][0]=='start') for row in f.trace)


def test_process_rejection_is_not_a_management_process_exception(runtime):
    def blocked():raise g.r.ObservationError('GROWTH_BUSINESS_PROCESS')
    runtime.m.inventory.processes=blocked
    with pytest.raises(g.r.ObservationError,match='BUSINESS_PROCESS'):runtime.runtime.run()
    assert runtime.m.started=={'runtime_preparation'}


def test_start_failure_retains_intent_and_actual_result_without_retry(runtime):
    f=runtime;original=f.m.inventory.ctl
    def failed(args,**kwargs):
        if args[0]=='start':
            f.m.inventory.last_result=dict(returncode=1,both_eof=True,stdout_bytes=0,stderr_bytes=9,
                stdout_sha256=g.digest(b''),stderr_sha256='a'*64)
            raise g.r.ObservationError('GROWTH_SYSTEMCTL_STDERR')
        return original(args,**kwargs)
    f.m.inventory.ctl=failed
    with pytest.raises(g.r.ObservationError,match='SYSTEMCTL_STDERR') as caught:f.runtime.run()
    result=f.m.failure(caught.value)
    assert 'runtime_system_start' in result['actions_started']
    assert result['diagnostic']['runtime_preparation']['commands'][-1]['returncode']==1
    assert 'poweroff' not in f.m.started and 'resize2fs' not in f.m.started


@pytest.mark.parametrize('fault',['schema','nonce','boot','old_limits','manager','reordered_commands','duplicate_command','missing_eof','wrong_argv','config_digest','owner','bus_type','tool_owner','refund'])
def test_runtime_proof_cannot_be_accepted_after_tampering(runtime,fault):
    f=runtime;value=f.runtime.run();changed=copy.deepcopy(value)
    if fault=='schema':changed['schema']='lhq-runtime-preparation/v0'
    elif fault=='nonce':changed['nonce']='b'*64
    elif fault=='boot':changed['boot_id']='22222222-2222-3333-4444-555555555555'
    elif fault=='old_limits':changed['parents']['ordinary']['properties']['TasksMax']='64'
    elif fault=='manager':changed['parents']['retained_ordinary']['properties']['ControlGroup']='/retained.slice'
    elif fault=='reordered_commands':changed['commands'][0],changed['commands'][1]=changed['commands'][1],changed['commands'][0]
    elif fault=='duplicate_command':changed['commands'].append(copy.deepcopy(changed['commands'][-1]))
    elif fault=='missing_eof':changed['commands'][0]['both_eof']=False
    elif fault=='wrong_argv':
        row=changed['commands'][3];row['arguments']=['start','--','other.service'];row['arguments_sha256']=g.digest(g.canonical(row['arguments']))
    elif fault=='config_digest':changed['configs'][0]['sha256']='a'*64
    elif fault=='owner':changed['configs'][0]['identity'][3]=1000
    elif fault=='bus_type':changed['bus']['private'][2]=stat.S_IFREG|0o600
    elif fault=='tool_owner':changed['tool']['identity']['uid']=1100
    else:changed['pools'][0]['reserved_bytes']=0
    with pytest.raises(g.r.ObservationError):g.validate_runtime_report(changed,f.m.description,value['boot_id'],'pre')


def test_source_binding_has_no_historical_pid_inode_or_boot(monkeypatch):
    patch(monkeypatch)
    b=binding();g.validate_runtime_binding(b,inventory())
    for mutation in ('manager','tasks_max','unit','control_group'):
        changed=copy.deepcopy(b);changed['parents']['ordinary'][mutation]='wrong'
        with pytest.raises(g.r.ObservationError,match='BINDING'):g.validate_runtime_binding(changed)
    assert not any(key.encode() in raw for raw in [g.canonical(b)] for key in ('InvocationID','inode','boot_id','pid'))


def test_config_creation_never_overwrites_or_follows_an_existing_leaf(tmp_path,monkeypatch):
    m=SimpleNamespace(window=SimpleNamespace(check=lambda **_:None),once=lambda *_:None)
    prep=object.__new__(g.RuntimePreparation);prep.m=m;prep.check=lambda:None;prep.config_fds=[];prep.report=dict(configs=[])
    real_open=os.open
    monkeypatch.setattr(g,'open_path',lambda path,**kw:real_open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW))
    target=tmp_path/'slice';target.write_bytes(b'original')
    inode=target.stat().st_ino
    with pytest.raises(FileExistsError):prep.config('ordinary',str(target),b'new',create=True,uid=os.getuid())
    assert target.read_bytes()==b'original' and target.stat().st_ino==inode
    link=tmp_path/'alias';link.symlink_to(target)
    with pytest.raises(FileExistsError):prep.config('ordinary',str(link),b'new',create=True,uid=os.getuid())
    assert target.read_bytes()==b'original' and prep.report['configs']==[]


@pytest.mark.parametrize('fault',['mode','owner','content','hardlink','symlink'])
def test_existing_config_conflict_is_never_repaired(tmp_path,monkeypatch,fault):
    prep=object.__new__(g.RuntimePreparation);prep.check=lambda:None;prep.config_fds=[];prep.report=dict(configs=[])
    target=tmp_path/'slice';target.write_bytes(b'original');target.chmod(0o644)
    if fault=='mode':target.chmod(0o600)
    if fault=='hardlink':os.link(target,tmp_path/'second')
    if fault=='symlink':
        alias=tmp_path/'alias';alias.symlink_to(target);path=alias
    else:path=target
    before=target.stat();real_open=os.open
    monkeypatch.setattr(g,'open_path',lambda path,**kw:real_open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW))
    with pytest.raises((g.r.ObservationError,OSError)):
        prep.config('ordinary',str(path),b'changed!' if fault=='content' else b'original',
            uid=os.getuid()+1 if fault=='owner' else os.getuid())
    assert target.read_bytes()==b'original' and target.stat().st_ino==before.st_ino
    assert target.stat().st_mode==before.st_mode and prep.report['configs']==[]
