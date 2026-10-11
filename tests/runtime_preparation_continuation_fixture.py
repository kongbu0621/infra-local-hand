"""Synthetic old11a returns; no private reads or field effects."""
import copy
import io
import tarfile

from e3_host import q2_core_prior_attempt as p
from identity_continuation_fixture import records as prior_records, archive as prior_archive, source as prior_source

DUMP=lambda value:p.c.canonical(value,newline=True)
PIN=lambda raw:dict(bytes=len(raw),sha256=p.c.sha256(raw))


def source():
    return dict(schema='local-hand-q2-runtime-preparation-continuation-archive/v1',
        archive=dict(bytes=409600,sha256='a'*64),index_sha256='b'*64,records_sha256='c'*64,
        predecessor=dict(member='old11a/.lhqjgrow-20261011a.consumed.json',
            marker=dict(bytes=100,sha256='d'*64),field='manifest.resume',
            resume_sha256=p.c.sha256(DUMP(p.identity_maintenance_resume()))),
        summary=p.runtime_preparation_failure_summary(),prior=prior_source())


def records():
    prior,boot=prior_records();inner=prior_archive(prior)
    proof,activation_files,_=p.build_identity_source(inner)
    activation=p.build_vm_activation({n:b for n,b in activation_files.items()
        if n!='execution-return-index-private.json'},activation_files['execution-return-index-private.json'],
        historical_boot=boot)
    session=p.PREPARATION_OLD_SESSION;previous=p.identity_maintenance_resume()
    authority=dict(R=p.c.RULE['commit'],A=p.c.IDENTITY_RESOURCE_BASELINE['commit'],C=p.c.IDENTITY_RESOURCE_CLOSURE['commit'])
    common=dict(authority,D=p.runtime_preparation_failure_summary()['D'],nonce='9'*64)
    inputs=dict(resume=previous,persistent_source=proof,vm_activation=activation,
        sources=dict(vm_activation_archive=proof["archive"]))
    encoded=copy.deepcopy(inputs);encoded['resume_sha256']=p.c.sha256(DUMP(encoded.pop('resume')))
    wire=dict(scope=previous['scope'],session=previous['session'],previous_reference=proof['predecessor'],
        previous_path_failure=proof['summary'])
    manifest=dict(common,schema='lhq-journal-growth-manifest/v20',resume=wire,inputs=encoded,
        window_binding=dict(origins=[1,2]),vm=activation['vm'],image_identities=activation['image_identities'])
    marker=dict(D=common['D'],manifest=manifest,manifest_sha256=p.c.sha256(DUMP(manifest)),nonce=common['nonce'],
        session=session,clocks=[1,2],resume_sha256=p.c.sha256(DUMP(previous)),
        pre_description=dict(schema="lhq-journal-growth-input/v6",source_binding_sha256=p.c.sha256(DUMP(inputs)),session=session,
            original_boot_id=activation['current_boot_id']))
    detail=dict(errno=None,error_type='ObservationError',context=dict(operation='persistent_inventory'),
        message='synthetic preparation limit failure',traceback='synthetic traceback',
        runtime_preparation=dict(commands=[]))
    guest=dict(schema='lhq-journal-growth-guest/v5',session=session,phase='pre',status='INCOMPLETE',
        stage='PRE_RUNTIME_PREPARATION',reason='GROWTH_RUNTIME_LIMITS',nonce=marker['nonce'],
        source_binding_sha256=marker['pre_description']['source_binding_sha256'],
        actions_started=['runtime_preparation'],diagnostic=detail)
    receipt=dict(common,schema='lhq-journal-growth-receipt/v20',session=session,resume=previous,
        manifest_sha256=marker['manifest_sha256'],clock_origins_ns=[1,2],state='STOP_AND_RETAIN',
        last_step='STOP_AND_RETAIN',reason='GROWTH_REPORT_MISSING',remote_exit='UNKNOWN',marker_created=True,
        ssh_requests=1,started=['CONSUMED','GUEST_QUIET'],original_boot_id=activation['current_boot_id'],
        diagnostic=dict(guest_failure=dict(stage=guest['stage'],reason=guest['reason'],diagnostic=detail)))
    old=dict(zip(p.PREPARATION_ORIGINALS,(DUMP(marker),b''.join(DUMP(x) for x in [
        dict(step='CONSUMED',state='STARTED'),dict(step='CONSUMED',state='RETURNED'),
        dict(step='GUEST_QUIET',state='STARTED'),dict(phase='pre')]),DUMP(guest),b'',DUMP(receipt))))
    old[p.PREPARATION_RECORDS[0]]=DUMP(dict(event=p.c.IDENTITY_RESOURCE_OWNER_DECISION['event'],session=session,
        files={n:PIN(old[n]) for n in p.PREPARATION_ORIGINALS},absent=['.'+session+'.'+n for n in
            ('journal.backup.qcow2','post.stderr','post.stdout','vm.pid')]))
    freeze=dict(authority,implementation=dict(commit=common['D'],tree='e'*40),scope=p.c.IDENTITY_RESOURCE_SCOPE,
        state='FROZEN_IR1_VERIFIED',ir2=dict(session=session,state='NOT_ISSUED'),
        callers={n:'a'*64 for n in p.PREPARATION_CALLERS},historical_boot_id=boot,vm_activation=activation,
        activation_archive=dict(proof['archive'],path='/synthetic/identity.tar'),persistent_source=proof)
    old['ir1-freeze.json']=DUMP(freeze)
    complete=dict(returncode=3,child=dict(returncode=0,cpu_nanoseconds=100,rss_peak_bytes=1000),
        usage=dict(cpu_nanoseconds=200,rss_peak_bytes=2000),receipt_sha256=p.c.sha256(old[p.PREPARATION_ORIGINALS[-1]]))
    summary={k:receipt[k] for k in ('state','reason','diagnostic','marker_created','ssh_requests','D')}
    summary.update(exit_code=3,phase='execute')
    old['ir2-summary.json']=old['ir2-caller.stdout']=DUMP(summary)
    for n in ('ir2-caller.stderr','ir2-execute.stderr','ir2-preflight.stderr'):old[n]=b''
    caller=dict(returncode=3,stdout=PIN(old['ir2-caller.stdout']),stderr=PIN(b''),source='synthetic completion',stdout_eof=True,stderr_eof=True)
    old['ir2-caller-completion.json']=DUMP(caller)
    terminal=dict(freeze,state='IR2_MAINTENANCE_CONSUMED_FAILED_IR3_NOT_RUN',
        ir1_freeze_sha256=p.c.sha256(old['ir1-freeze.json']),
        ir2=dict(coordinator_completion=complete,caller_completion=caller,summary=summary,
            originals_index=PIN(old[p.PREPARATION_RECORDS[0]])),
        ir3=dict(H01='NOT_RUN',Q4='NOT_RUN',H11='NOT_RUN',state='NOT_RUN'))
    old['ir2-terminal.json']=DUMP(terminal)
    old['ir2-execute.stdout']=DUMP(dict(receipt,coordinator_completion=complete))
    old['ir2-preflight.stdout']=DUMP(dict(state='LOCAL_PREFLIGHT_PASSED',manifest=manifest,
        manifest_sha256=marker['manifest_sha256']))
    old['ir2-caller-started.json']=DUMP(dict(D=common['D'],session=session))
    return {'old11a/'+n:old[n] for n in (*p.PREPARATION_ORIGINALS,*p.PREPARATION_RECORDS)},inner,boot


def archive(files):
    files=dict(files)
    files['continuation-index-private.json']=DUMP(dict(files={n:PIN(b) for n,b in files.items()}))
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:',format=tarfile.USTAR_FORMAT) as tar:
        for name in p.PREPARATION_MEMBERS:
            raw=files[name];info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600
            tar.addfile(info,io.BytesIO(raw))
    raw=stream.getvalue();assert len(raw)<=p.PREPARATION_ARCHIVE_BYTES
    return raw.ljust(p.PREPARATION_ARCHIVE_BYTES,b'\0')


def bind(frozen):
    files,identity_raw,_=records();raw=archive(files)
    proof,activation,previous=p.build_runtime_preparation_source(raw,identity_raw)
    frozen.update(persistent_raw=identity_raw,runtime_preparation_raw=raw,persistent_predecessor=previous)
    frozen['source_binding']['persistent_source']=proof
    frozen['source_binding']['sources']['vm_activation_archive']=proof['prior']['archive']
    frozen['source_binding']['sources']['runtime_preparation_archive']=proof['archive']
    assert activation.pop('execution-return-index-private.json')==frozen['activation_index']
    assert activation==frozen['activation_files']
    return proof
