"""Synthetic missing-receipt history; no field paths or private hashes."""
import copy
import json

from e3_host import q2_core_prior_attempt as p
from local_preflight_fixture import archive, source_projection as local_source


def source_projection():
    pins={name:dict(bytes=100,sha256='b'*64) for name in p.TRANSPORT_FAILURE_MEMBERS}
    for name in pins:
        if name.endswith(('pre.stdout','pre.stderr','caller.stderr','execute.stderr','preflight.stderr')):
            pins[name]=dict(bytes=0,sha256=p.c.sha256(b''))
    pins['freeze-complete.json']['sha256']=p.TRANSPORT_FAILURE_FREEZE
    return dict(schema='local-hand-q2-transport-failure-source/v1',summary=p.transport_failure_summary(),
        archive=dict(bytes=20480,sha256='a'*64),originals=pins,freeze_sha256=p.TRANSPORT_FAILURE_FREEZE,
        callers={name:'c'*64 for name in p.LOCAL_PREFLIGHT_CALLERS},diagnostic_sha256='d'*64)


def records(monkeypatch,*consumers):
    encode=lambda value:(json.dumps(value,sort_keys=True,indent=2)+'\n').encode('ascii')
    canonical=lambda value:p.c.canonical(value,newline=True)
    pin=lambda raw:dict(bytes=len(raw),sha256=p.c.sha256(raw))
    authority=p.transport_failure_summary()['authority'];old_D=p.TRANSPORT_FAILURE_D
    resume=dict(p.maintenance_resume(),scope='LH-Q2-CORE-USAGE-CONTINUATION-v1',session=p.TRANSPORT_FAILURE_SESSION)
    resume.pop('previous_transport_failure');resume.pop('previous_host_preflight');resume_sha=p.c.sha256(canonical(resume))
    window=dict(boot_id='10000000-0000-4000-8000-000000000001',origins=[100,200])
    inputs=dict(resume_sha256=resume_sha,inventory_sha256='a'*64,local_preflight_source=local_source())
    restored=dict(inputs,resume=resume);restored.pop('resume_sha256')
    manifest=dict(authority,schema='lhq-journal-growth-manifest/v14',D=old_D,nonce='e'*64,
        resume=resume,inputs=inputs,inventory_sha256='a'*64,window_binding=window,
        access_mode='TRUSTED_SINGLE_ADMIN',host_writer_observation='NOT_PERFORMED',continuous_exclusion_proven=False)
    desc=dict(session=p.TRANSPORT_FAILURE_SESSION,nonce='e'*64,source_binding_sha256=p.c.sha256(canonical(restored)),
        window_seconds=880,change_seconds=760)
    marker=dict(manifest=manifest,manifest_sha256=p.c.sha256(canonical(manifest)),D=old_D,nonce='e'*64,
        pre_description=desc,session=p.TRANSPORT_FAILURE_SESSION,resume_sha256=resume_sha,clocks=[100,200],
        pre_command_sha256='f'*64,access_mode='TRUSTED_SINGLE_ADMIN',host_writer_observation='NOT_PERFORMED',
        continuous_exclusion_proven=False)
    handoff=dict(authority,schema='lhq-journal-growth-preflight/v13',D=old_D,nonce='e'*64,
        manifest_sha256=marker['manifest_sha256'],resume_sha256=resume_sha,window_binding=window)
    pre=dict(D=old_D,state='LOCAL_PREFLIGHT_PASSED',marker_created=False,ssh_requests=0,business_cases=0,
        manifest=manifest,manifest_sha256=marker['manifest_sha256'],preflight=handoff,window_binding=window)
    diagnostic=dict(complete=False,live_children=1,operation='management_usage',stage='live_child_observation',
        failed_children=[dict(errno=None,error_type='ObservationError',identity=dict(argv_sha256=None,starttime=None),
            pid=101,reason='GROWTH_USAGE_IDENTITY',stage='process_identity')])
    execute=dict(state='UNKNOWN',reason='GROWTH_USAGE_UNKNOWN',marker_created=True,ssh_requests=1,
        diagnostic=diagnostic,errno=None,error_type='ObservationError',window_binding=window,
        management_usage=dict(cpu_nanoseconds=100000,rss_peak_bytes=1048576))
    summary={k:v for k,v in execute.items() if k not in ('window_binding','management_usage')}
    summary.update(D=old_D,phase='execute',exit_code=3,started=None,last_step=None,business_cases=None)
    events=[dict(step='CONSUMED',state='STARTED'),
        dict(step='CONSUMED',state='RETURNED',result=dict(manifest_sha256=marker['manifest_sha256'])),
        dict(step='GUEST_QUIET',state='STARTED'),dict(phase='pre',argv_sha256=marker['pre_command_sha256'],
            description_sha256=p.c.sha256(canonical(desc)),window_seconds=880,change_seconds=760)]
    prefix='.'+p.TRANSPORT_FAILURE_SESSION+'.'
    files={prefix+'consumed.json':canonical(marker),prefix+'events.jsonl':b''.join(map(canonical,events)),
        prefix+'pre.stdout':b'',prefix+'pre.stderr':b'',
        'uc2-caller-started.json':encode(dict(D=old_D,session=p.TRANSPORT_FAILURE_SESSION)),
        'uc2-caller.stdout':encode(summary),'uc2-summary.json':encode(summary),'uc2-caller.stderr':b'',
        'uc2-execute.stdout':canonical(execute),'uc2-execute.stderr':b'',
        'uc2-preflight.stdout':canonical(pre),'uc2-preflight.stderr':b''}
    freeze=dict(authority,scope='LH-Q2-CORE-USAGE-CONTINUATION-v1',state='FROZEN_UC1_VERIFIED',
        implementation=dict(commit=old_D,tree=p.TRANSPORT_FAILURE_TREE),
        callers={name:'c'*64 for name in p.LOCAL_PREFLIGHT_CALLERS},local_preflight_source=local_source(),
        uc2=dict(state='NOT_STARTED',session=p.TRANSPORT_FAILURE_SESSION),
        uc3=dict(state='NOT_RUN',session='lhqcore-20261007a'))
    files['freeze-complete.json']=encode(freeze);freeze_sha=p.c.sha256(files['freeze-complete.json'])
    for module in (p,*consumers):monkeypatch.setattr(module,'TRANSPORT_FAILURE_FREEZE',freeze_sha)
    result=dict(D=old_D,session=p.TRANSPORT_FAILURE_SESSION,state='UC2_CONSUMED_FAILED_UC3_NOT_RUN',
        frozen_sha256=freeze_sha,originals={n:pin(files[n]) for n in p.TRANSPORT_FAILURE_ORIGINALS},
        local_returns={n:pin(files[n]) for n in p.TRANSPORT_FAILURE_RETURNS},
        missing_expected=[prefix+'receipt.json'],remote_exit='UNKNOWN',coordinator_completion='NOT_CAPTURED',
        core='NOT_RUN',core_package='NOT_BUILT',caller_exit=3,returned_state='UNKNOWN',diagnostic=diagnostic,
        reason='GROWTH_USAGE_UNKNOWN',marker_created=True,ssh_requests=1)
    files['uc2-failure-private.json']=encode(result)
    files['release-gate.json']=encode(dict(freeze,state='UC2_CONSUMED_FAILED_UC3_NOT_RUN',uc2=result,
        uc3=dict(core_package='NOT_BUILT',reason='INCOMPLETE_UC2',state='NOT_RUN')))
    raw=archive(files)
    spec=dict(path='/synthetic/old10a-retained.tar',bytes=len(raw),sha256=p.c.sha256(raw),freeze_sha256=freeze_sha,
        callers=copy.deepcopy(freeze['callers']),originals={n:pin(b) for n,b in files.items()})
    return raw,spec,files
