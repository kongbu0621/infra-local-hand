"""Synthetic maintenance originals and independent host/guest transition consumers."""
import copy
import json
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux maintenance and core consumers',allow_module_level=True)

from core_prior_fixture import triple_fixture, journal_transition
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_dispatcher as d
from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g
from test_e3_q2_journal_growth_guest_completion import description, pre_report, device


@pytest.fixture
def originals(monkeypatch):
    priors,_=triple_fixture(monkeypatch,d)
    implementation=dict(commit='d'*40,tree='e'*40)
    projection=journal_transition(implementation)
    sources={name:b'# synthetic source\n' for name in p.JOURNAL_SOURCE_NAMES}
    desc=description();pre=pre_report()
    frozen=dict(boot_id=desc['original_boot_id'],paths=desc['paths'],saved_rows=desc['saved_rows'],
        source_binding=dict(synthetic='eight fixed input relation'),
        inventory={key:desc[key] for key in ('expected_units','domain_cgroups','domain_units','protected_roots','essential_paths')},
        horizon={},description=b'synthetic capacity description')
    sha=h.digest(h.canonical(frozen['source_binding']))
    desc['source_binding_sha256']=pre['source_binding_sha256']=sha
    start=b'q1_vm=/fixture\nqemu-system-x86_64 \\\n -serial file:/fixture/serial -pidfile /fixture/vm.pid\n\n'
    monkeypatch.setitem(h.local.PINS,'start.sh',(0o700,h.digest(start)))
    frozen['start_raw']=start
    original,restart=h.qemu_argv(start,'/fixture','/fixture/serial')
    oldvm=dict(pid=123,starttime=1,argv_sha256=h.digest(b'\0'.join(x.encode() for x in original)+b'\0'))
    newvm=dict(pid=124,starttime=2,argv_sha256=h.digest(b'\0'.join(x.encode() for x in restart)+b'\0'))
    post=copy.deepcopy(pre)
    post.update(phase='post',status='FILESYSTEM_GROWN',boot_id=projection['new_boot_id'],
        original_boot_id=pre['boot_id'],pre_report_sha256=h.digest(h.canonical(pre)),
        journal_device=device(g.NEW_SIZE),resize_result=dict(returncode=0,both_eof=True,
            stdout_bytes=0,stderr_bytes=0,stdout_sha256=h.digest(b''),stderr_sha256=h.digest(b'')))
    post['journal_device']['superblock']['filesystem_bytes']=g.NEW_SIZE
    ack=dict(schema=g.REPORT_SCHEMA,session=g.SESSION,status='POWER_OFF_REQUESTED',
        nonce=desc['nonce'],pre_report_sha256=h.digest(h.canonical(pre)))
    streams={'pre.stdout':h.canonical(pre)+h.canonical(ack),'pre.stderr':b'',
        'post.stdout':h.canonical(post),'post.stderr':b''}
    transports=[]
    for phase in ('pre','post'):
        transports.append(dict(returncode=255 if phase=='pre' else 0,eof=dict(stdout=True,stderr=True),
            ack=ack if phase=='pre' else None,files={key:dict(bytes=len(streams[phase+'.'+key]),
                sha256=h.digest(streams[phase+'.'+key])) for key in ('stdout','stderr')}))
    manifest=dict(schema='lhq-journal-growth-manifest/v2',R=h.R,A=h.MINIMAL_A,C=h.MINIMAL_C,
        D=implementation['commit'],nonce=desc['nonce'],access_mode=h.ACCESS_MODE,
        host_writer_observation='NOT_PERFORMED',continuous_exclusion_proven=False,
        historical_authority=dict(A=h.A,C=h.C,observer_superseded_by=h.MINIMAL_A),
        inputs=frozen['source_binding'],window_binding=dict(boot_id=pre['boot_id'],origins=[1,2]),
        inventory_sha256=h.digest(h.canonical(frozen['inventory'])),retained_sha256='e'*64,
        sources={key:dict(bytes=len(raw),sha256=h.digest(raw)) for key,raw in sources.items()},
        tools={},vm=oldvm,image_identities=projection['image_identities'],original_argv=original,
        restart_argv=restart,image_commands=h.image_commands('/fixture/journal.qcow2',
            '/fixture/'+h.NAMES['journal.backup.qcow2']),
        protocol='two fixed phases; post bound to the durably saved pre report; no probe or retry')
    marker=dict(manifest_sha256=h.digest(h.canonical(manifest)),manifest=manifest,nonce=desc['nonce'],
        clocks=[1,2],session=h.SESSION,D=implementation['commit'],access_mode=h.ACCESS_MODE,
        host_writer_observation='NOT_PERFORMED',continuous_exclusion_proven=False,
        pre_command_sha256='a'*64,post_command_derivation='same fixed sources; post descriptor bound to saved canonical pre report',
        pre_description=desc)
    def image(size):
        return dict(info={'format':'qcow2','virtual-size':size,'format-specific':{'data':{'compat':'1.1','corrupt':False}}},
            check={'check-errors':0,'corruptions':0,'leaks':0},check_returncode=0,check_eof=dict(stdout=True,stderr=True))
    comparison=dict(pools=[dict(bytes=dict(deficit=0),inodes=dict(deficit=0))])
    monkeypatch.setattr(h.prior,'compare',lambda report,horizon:comparison)
    results={'CONSUMED':dict(manifest_sha256=marker['manifest_sha256']),'GUEST_QUIET':pre,
        'POWERED_OFF':dict(transport=transports[0],pidfd_exit=True,image=image(g.OLD_SIZE)),
        'BACKED_UP':dict(bytes=1024,sha256='c'*64),'IMAGE_GROWN':dict(image(g.NEW_SIZE),
            logical_compare=dict(returncode=0,eof=dict(stdout=True,stderr=True))),
        'BOOTED':dict(process=newvm,returncode=0,passive_wait_seconds=60),'FILESYSTEM_GROWN':post,
        'VERIFIED':dict(comparison=comparison,tree=post['tree'],rows=post['rows'])}
    events=[]
    for step in h.STATES[1:]:
        events.append(dict(step=step,state='STARTED'))
        if step in ('GUEST_QUIET','FILESYSTEM_GROWN'):
            events.append(dict(phase='pre' if step=='GUEST_QUIET' else 'post',argv_sha256='a'*64,description_sha256='b'*64))
        if step=='POWERED_OFF':events.append(dict(step='POWER_OFF_TOKEN',state='STARTED',pre_report_sha256=h.digest(h.canonical(pre))))
        events.append(dict(step=step,state='RETURNED',result=results[step]))
    receipt=dict(schema='lhq-journal-growth-receipt/v2',R=h.R,A=h.MINIMAL_A,C=h.MINIMAL_C,
        D=implementation['commit'],nonce=desc['nonce'],session=h.SESSION,access_mode=h.ACCESS_MODE,
        host_writer_observation='NOT_PERFORMED',continuous_exclusion_proven=False,
        manifest_sha256=marker['manifest_sha256'],clock_origins_ns=[1,2],
        state='VERIFIED',reason='MAINTENANCE_COMPLETE',last_step='VERIFIED',started=sorted(h.STATES[1:]),
        marker_created=True,ssh_requests=2,business_cases=0,remote_exit='HELPER_REPORTED_COMPLETE',
        production_supported=False,old_commitments_refunded=False,exclusive_reservation_proven=False,
        original_boot_id=pre['boot_id'],new_boot_id=post['boot_id'],post_transport=transports[1],
        transports=[dict(pid=i+100,exit=t['returncode'],files=t['files']) for i,t in enumerate(transports)],
        new_vm=newvm,image_identities=projection['image_identities'],processes=[dict(vm=False,exit=0)])
    post_desc=dict(desc,phase='post',pre_report=pre,pre_report_sha256=h.digest(h.canonical(pre)),
        window_seconds=600,change_seconds=480)
    for row in events:
        if 'phase' in row:
            phase_desc=desc if row['phase']=='pre' else post_desc
            row.update(argv_sha256=h.digest(h.canonical(h.remote_argv('/fixture',sources,phase_desc))),
                description_sha256=h.digest(h.canonical(phase_desc)),window_seconds=phase_desc['window_seconds'],
                change_seconds=phase_desc['change_seconds'])
    marker['pre_command_sha256']=next(row['argv_sha256'] for row in events if row.get('phase')=='pre')
    receipt.update(serial_capture='NOT_CAPTURED_NULL_BACKEND',kernel_report={},
        budget=dict(logical_bytes=10000,allocated_bytes=32768,inodes=7),
        management_usage=dict(cpu_nanoseconds=1000000,rss_peak_bytes=1000000))
    raw=dict(streams,**{'consumed.json':h.canonical(marker),'receipt.json':h.canonical(receipt),
        'events.jsonl':b''.join(h.canonical(row) for row in events),'vm.pid':b'124\n'})
    capraw={name:b'synthetic retained '+name.encode() for name in p.CAPACITY_DIAGNOSTIC_PINS}
    monkeypatch.setattr(p,'CAPACITY_DIAGNOSTIC_PINS',{name:(len(data),h.digest(data)) for name,data in capraw.items()})
    frozen['capacity_files']={'.lhqcap-20261006a.'+name:data for name,data in capraw.items()}
    monkeypatch.setattr(h.prior,'validate_result',lambda *args:dict(rows=frozen['saved_rows']))
    return {'.'+h.SESSION+'.'+name:data for name,data in raw.items()},dict(implementation=implementation,
        sources=sources,frozen=frozen,priors=priors)


def test_full_original_consumer_and_independent_projection(originals):
    files,args=originals
    value=p.build_journal_transition(files,**args)
    assert d._validate_journal_transition(value,priors=args['priors'],implementation=args['implementation'],
        current_boot=value['new_boot_id'])==value
    assert value['host_writer_observation']=='NOT_PERFORMED' and value['historical_exit']=='UNKNOWN'
    assert len(p.c.canonical(value))<65536


@pytest.mark.parametrize('change',['missing','truncated','D','nonce','order','repeat','failure','old_boot',
    'new_boot','backup','image_check','compare','pidfd','pid','argv','eof','transport_exit','streams','content','size','capacity','phase_window','phase_digest'])
def test_original_failure_cannot_become_new_boot_permission(originals,change):
    files,args=originals;files=copy.deepcopy(files)
    prefix='.'+h.SESSION+'.'
    if change=='missing':files.pop(prefix+'pre.stderr')
    elif change=='truncated':files[prefix+'post.stdout']=files[prefix+'post.stdout'][:-1]
    elif change=='pid':files[prefix+'vm.pid']=b'125\n'
    elif change in ('order','repeat','backup','image_check','compare','pidfd','phase_window','phase_digest'):
        rows=[json.loads(row) for row in files[prefix+'events.jsonl'].splitlines()]
        if change=='order':rows.reverse()
        elif change=='repeat':rows.append(rows[-1])
        elif change=='phase_window':next(row for row in rows if row.get('phase')=='post')['window_seconds']=901
        elif change=='phase_digest':next(row for row in rows if row.get('phase')=='post')['description_sha256']='0'*64
        else:
            results={row['step']:row['result'] for row in rows if row.get('state')=='RETURNED'}
            if change=='backup':results['BACKED_UP']['sha256']='wrong'
            elif change=='image_check':results['IMAGE_GROWN']['check']['corruptions']=1
            elif change=='compare':results['IMAGE_GROWN']['logical_compare']['returncode']=1
            else:results['POWERED_OFF']['pidfd_exit']=False
        files[prefix+'events.jsonl']=b''.join(h.canonical(row) for row in rows)
    elif change in ('content','size','capacity'):
        row=json.loads(files[prefix+'post.stdout'])
        if change=='content':row['tree']['sha256']='0'*64
        elif change=='size':row['journal_device']['superblock']['filesystem_bytes']=g.OLD_SIZE
        else:row['rows'][3]['available']['bytes']=0
        files[prefix+'post.stdout']=h.canonical(row)
    else:
        row=json.loads(files[prefix+'receipt.json'])
        if change=='D':row['D']='0'*40
        elif change=='nonce':row['nonce']='0'*64
        elif change=='failure':row['state']='STOP_AND_RETAIN'
        elif change=='old_boot':row['original_boot_id']=row['new_boot_id']
        elif change=='new_boot':row['new_boot_id']=row['original_boot_id']
        elif change=='argv':row['new_vm']['argv_sha256']='0'*64
        elif change=='eof':row['post_transport']['eof']['stdout']=False
        elif change=='transport_exit':row['transports'][1]['exit']=3
        elif change=='streams':row['transports'][0]['files']['stdout']['bytes']+=1
        files[prefix+'receipt.json']=h.canonical(row)
    with pytest.raises((p.c.ContractError,g.r.ObservationError)):
        p.build_journal_transition(files,**args)


@pytest.mark.parametrize('change',['authority','prior_missing','old_boot','current_boot','success_flag',
    'eof','size','capacity','extra','source','images','unknown','refund','schema'])
def test_both_projection_consumers_reject_boundary_changes(originals,change):
    files,args=originals;value=p.build_journal_transition(files,**args)
    boot=value['new_boot_id'];priors=args['priors']
    if change=='authority':value['authority']['C']='0'*40
    elif change=='prior_missing':priors=priors[:-1]
    elif change=='old_boot':value['old_boot_id']=value['new_boot_id']
    elif change=='current_boot':boot=value['old_boot_id']
    elif change=='success_flag':value['completed_steps']=['VERIFIED']
    elif change=='eof':value['all_streams_eof']=False
    elif change=='size':value['virtual_bytes']['after']=True
    elif change=='capacity':value['filesystem']['available']['inodes']=32767
    elif change=='extra':value['trusted_pass']=True
    elif change=='source':value['source_files'].pop('q2_journal_growth.py')
    elif change=='images':value['image_identities']['seed']=value['image_identities']['journal']
    elif change=='unknown':value['historical_exit']='PASS'
    elif change=='refund':value['old_commitments_refunded']=True
    else:value['schema']='lhq-journal-growth-receipt/v1'
    with pytest.raises(p.c.ContractError):p.validate_journal_transition(value,priors=priors,implementation=args['implementation'],current_boot=boot)
    with pytest.raises(d.DispatchError):d._validate_journal_transition(value,priors=priors,implementation=args['implementation'],current_boot=boot)
