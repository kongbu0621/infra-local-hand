"""Synthetic runtime roles; these names and identities are not field evidence."""
import copy
import hashlib
import json

def raw(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode()

def binding():
    from e3_host import q2_core_prior_attempt as g
    parents={}
    for role in g.RUNTIME_ROLES:
        unit=('controller-ordinary.slice' if role=='ordinary' else 'retained.slice' if role=='retained_ordinary' else role+'.slice')
        path=('/controller.slice/' if role=='ordinary' else '/user.slice/user-1100.slice/user@1100.service/' if role=='retained_ordinary' else '/')+unit
        parents[role]=dict(unit=unit,control_group=path,manager='user' if role=='retained_ordinary' else 'system',
            memory_bytes=268435456 if role in ('query','ordinary','retained_ordinary') else 536870912,
            tasks_max=32 if role=='ordinary' else 64,cpu_quota_per_sec_usec=1000000)
    return dict(schema='lhq-runtime-parent-binding/v1',sources=dict(g.RUNTIME_SOURCES),
        account=dict(name='q2job',uid=1100,gid=1100),parents=parents,
        manager=dict(unit='user@1100.service',control_group='/user.slice/user-1100.slice/user@1100.service',
            fragment='/usr/lib/systemd/system/user@.service',
            dropins=['/etc/systemd/system/user@1100.service.d/50-local-hand-q2.conf']))

def patch(monkeypatch,*dispatchers):
    import sys
    from e3_host import q2_core_prior_attempt as p
    digest=hashlib.sha256(raw(binding())).hexdigest()
    monkeypatch.setattr(p,'RUNTIME_BINDING_SHA',digest)
    g=sys.modules.get('e3_host.q2_journal_growth_guest')
    if g is not None:monkeypatch.setattr(g,'RUNTIME_BINDING_SHA',digest)
    for module in dispatchers:monkeypatch.setattr(module,'RUNTIME_BINDING_SHA',digest)

def inventory():
    rows=[dict(name=row['unit'],manager=row['manager'],control_group=row['control_group']) for row in binding()['parents'].values()]
    return dict(domain_units=sorted(rows,key=lambda row:(row['manager'],row['name'])),
        domain_cgroups=sorted(row['control_group'] for row in rows))

def properties(row,*,manager=False,active=True):
    from e3_host import q2_journal_growth_guest as g
    value=dict.fromkeys(g.RUNTIME_SHOW,'')
    value.update(Id=row['unit'],LoadState='loaded',ActiveState='active' if active else 'inactive',
        SubState=('running' if manager else 'active') if active else 'dead',
        ControlGroup=row['control_group'] if active else '',InvocationID='1'*32 if active else '',
        MemoryMax=str(row['memory_bytes']),MemorySwapMax='0',TasksMax=str(row['tasks_max']),CPUQuotaPerSecUSec='1s',
        MainPID='22' if manager and active else '0',ControlPID='0',
        Delegate='yes' if manager else '',User='1100' if manager else '')
    return value

def report(desc,boot=None,phase=None):
    from e3_host import q2_journal_growth_guest as g
    b=binding();phase=phase or desc['phase'];boot=boot or desc['original_boot_id']
    configs=[];parents={}
    for i,(role,row) in enumerate(b['parents'].items()):
        path=('/run/user/1100/systemd/user/' if role=='retained_ordinary' else '/etc/systemd/system/')+row['unit']
        content=g.runtime_config(row);p=properties(row);p['FragmentPath']=path
        parents[role]=dict(properties=p,cgroup=dict(path=row['control_group'],state='UNPOPULATED',
            identity=dict(dev=9,ino=i+1,mode=0o40755,uid=1100 if role=='retained_ordinary' else 0,gid=1100 if role=='retained_ordinary' else 0),events_sha256='e'*64))
        uid=1100 if role=='retained_ordinary' else 0
        configs.append(dict(role=role,path=path,identity=[1,10+i,0o100644,uid,uid,1],bytes=len(content),sha256=g.digest(content),created=False))
    content=g.runtime_config(b['parents']['retained_ordinary'],manager=True)
    configs.append(dict(role='manager',path='/etc/systemd/system/user@1100.service.d/50-local-hand-q2.conf',identity=[1,19,0o100644,0,0,1],bytes=len(content),sha256=g.digest(content),created=False))
    manager=properties(dict(b['parents']['retained_ordinary'],**{k:b['manager'][k] for k in ('unit','control_group')}),manager=True)
    manager.update(FragmentPath=b['manager']['fragment'],DropInPaths=' '.join(b['manager']['dropins']))
    commands=[]
    for step in ('guard_units','system_before','system_after','user_before','user_after'):
        names=([p['unit'] for p in b['parents'].values() if p['manager']=='system']+['user-runtime-dir@1100.service','user@1100.service']
            if step.startswith('system') else [b['parents']['retained_ordinary']['unit']])
        if step=='guard_units':names=[row['name'] for row in desc.get('expected_units',[dict(name='old.service')])]
        args=['show','--all','--property='+','.join(g.GuestInventory.SHOW if step=='guard_units' else g.RUNTIME_SHOW),'--',*names]
        commands.append(dict(step=step,arguments=args,arguments_sha256=g.digest(g.canonical(args)),returncode=0,both_eof=True,
            stdout_bytes=1,stderr_bytes=0,stdout_sha256='b'*64,stderr_sha256=g.digest(b'')))
    return dict(schema='lhq-runtime-preparation/v1',binding_sha256=g.digest(g.canonical(b)),nonce=desc['nonce'],
        boot_id=boot,phase=phase,commands=commands,
        configs=configs,directories=[],parents=parents,manager=manager,bus={name:[1,i+30,0o40700 if name=='runtime' else 0o140600,1100,1100,1]
        for i,name in enumerate(('runtime','bus','private'))},elapsed_ns=100,
        tool=dict(path='/usr/bin/systemctl',identity=dict(dev=1,ino=100,mode=0o100755,uid=0,gid=0,nlink=1),bytes=100,sha256='f'*64),
        pools=[dict(dev=10,reserved_bytes=8192*(1 if phase=='pre' else 2),reserved_inodes=32*(1 if phase=='pre' else 2),before=[1000000,1000],after=[990000,900])])

def transition(value):
    b=binding();value['runtime_parent_binding']=b;value['runtime_preparation']={}
    for phase,key in (('pre','old_boot_id'),('post','new_boot_id')):
        summary=dict(schema='lhq-runtime-transition/v1',binding_sha256=hashlib.sha256(raw(b)).hexdigest(),
            nonce=value['nonce'],phase=phase,boot_id=value[key],report_sha256=value['reports'][phase]['sha256'],
            runtime_sha256='c'*64,commands_sha256='d'*64,configs_sha256='e'*64,elapsed_ns=100,
            parents={role:dict(unit=row['unit'],control_group=row['control_group'],invocation_id='1'*32,
                identity=dict(dev=9,ino=i+1,mode=0o40755,uid=0,gid=0))
                for i,(role,row) in enumerate(b['parents'].items())},
            manager=dict(Id=b['manager']['unit'],ControlGroup=b['manager']['control_group'],InvocationID='1'*32),
            pools=[dict(dev=10,reserved_bytes=8192*(1 if phase=='pre' else 2),
                reserved_inodes=32*(1 if phase=='pre' else 2),before=[1000000,1000],after=[990000,900])])
        value['runtime_preparation'][phase]=summary
    return value
