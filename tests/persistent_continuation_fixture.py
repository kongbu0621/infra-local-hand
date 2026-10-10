"""Synthetic old10c envelope; never reads private originals or a VM."""
import copy
import io
import tarfile

from e3_host import q2_core_prior_attempt as p
from vm_resumption_fixture import records as vm_records, archive as vm_archive

DUMP=lambda x:p.c.canonical(x,newline=True)
PIN=lambda raw:dict(bytes=len(raw),sha256=p.c.sha256(raw))


def source():
    return dict(schema='local-hand-q2-persistent-continuation-archive/v1',
        archive=dict(bytes=522240,sha256='a'*64),index_sha256='b'*64,records_sha256='c'*64,
        predecessor=dict(member='old10c/.lhqjgrow-20261010c.consumed.json',
            marker=dict(bytes=100,sha256='d'*64),field='manifest.resume',
            resume_sha256=p.c.sha256(DUMP(p.legacy_maintenance_resume()))),
        summary=p.persistent_failure_summary())


def records():
    files,idx,boot=vm_records()
    activation=p.build_vm_activation(files,idx,historical_boot=boot)
    outer={p.PERSISTENT_INNER:vm_archive(files,idx)}
    legacy=p.legacy_maintenance_resume();session=p.PERSISTENT_OLD_SESSION
    authority=dict(R=p.c.RULE['commit'],A=p.c.PROTECTED_SOURCE_BASELINE['commit'],
        C=p.c.PROTECTED_SOURCE_CLOSURE['commit'])
    common=dict(authority,D=p.persistent_failure_summary()['D'],nonce='9'*64)
    inputs=dict(resume=legacy,inventory_sha256='8'*64,vm_activation=activation)
    encoded=copy.deepcopy(inputs);encoded['resume_sha256']=p.c.sha256(DUMP(encoded.pop('resume')))
    manifest=dict(common,schema='lhq-journal-growth-manifest/v17',resume=legacy,
        inputs=encoded,window_binding=dict(origins=[1,2]),vm=activation['vm'],
        image_identities=activation['image_identities'])
    marker=dict(D=common['D'],manifest=manifest,manifest_sha256=p.c.sha256(DUMP(manifest)),
        nonce=common['nonce'],session=session,clocks=[1,2],resume_sha256=p.c.sha256(DUMP(legacy)),
        pre_description=dict(source_binding_sha256=p.c.sha256(DUMP(inputs)),session=session,
            original_boot_id=activation['current_boot_id']))
    receipt=dict(common,schema='lhq-journal-growth-receipt/v17',resume=legacy,
        manifest_sha256=marker['manifest_sha256'],clock_origins_ns=[1,2],session=session,
        state='STOP_AND_RETAIN',last_step='STOP_AND_RETAIN',reason='GROWTH_REPORT_MISSING',
        remote_exit='UNKNOWN',marker_created=True,ssh_requests=1,started=['CONSUMED','GUEST_QUIET'],
        original_boot_id=activation['current_boot_id'])
    old=dict(zip(p.PERSISTENT_ORIGINALS,(
        DUMP(marker),b''.join(DUMP(x) for x in [dict(step='CONSUMED',state='STARTED'),
            dict(step='CONSUMED',state='RETURNED'),dict(step='GUEST_QUIET',state='STARTED'),dict(phase='pre')]),
        DUMP(dict(schema='lhq-journal-growth-guest/v4',session=session,phase='pre',status='INCOMPLETE',
            stage='PRE_RUNTIME_PREPARATION',reason='GROWTH_GUEST_IO_OR_RUNTIME')),b'',DUMP(receipt))))
    old[p.PERSISTENT_RECORDS[0]]=DUMP(dict(event=p.c.PROTECTED_SOURCE_OWNER_DECISION['event'],
        session=session,files=p._resume_pins(old),absent=['.'+session+'.'+n for n in
            ('post.stdout','post.stderr','vm.pid','journal.backup.qcow2')]))
    freeze=dict(authority,implementation=dict(commit=common['D'],tree='e'*40),scope=p.c.PROTECTED_SOURCE_SCOPE,
        state='FROZEN_PS1_VERIFIED',rc3=dict(state='NOT_ISSUED'),callers={'maintenance_once.py':'a'*64},
        historical_boot_id=boot)
    old['ps1-freeze.json']=DUMP(freeze)
    terminal=dict(freeze,state='PS3_MAINTENANCE_CONSUMED_FAILED_CORE_NOT_RUN',vm_activation=activation,rc3=dict(
        originals_index=PIN(old[p.PERSISTENT_RECORDS[0]]),coordinator_completion=dict(returncode=3,
            child=dict(returncode=0,cpu_nanoseconds=100,rss_peak_bytes=1000),
            usage=dict(cpu_nanoseconds=200,rss_peak_bytes=2000),
            receipt_sha256=p.c.sha256(old[p.PERSISTENT_ORIGINALS[-1]]))))
    old['release-gate.json']=DUMP(terminal)
    old['rc3-summary.json']=DUMP(dict(exit_code=3,state='STOP_AND_RETAIN',reason=receipt['reason'],
        marker_created=True,ssh_requests=1))
    old['ps3-field-review-private.json']=DUMP(dict(freeze_sha256=p.c.sha256(old['ps1-freeze.json']),
        H01='NOT_RUN',Q4='NOT_RUN',H11='NOT_RUN'))
    outer.update({'old10c/'+n:old[n] for n in (*p.PERSISTENT_ORIGINALS,*p.PERSISTENT_RECORDS)})
    return outer,boot


def archive(files):
    files=dict(files)
    files['continuation-index-private.json']=DUMP(dict(files=p._resume_pins(files)))
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:',format=tarfile.USTAR_FORMAT) as t:
        for name in p.PERSISTENT_MEMBERS:
            raw=files[name];info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600
            t.addfile(info,io.BytesIO(raw))
    raw=stream.getvalue()
    assert len(raw)<=522240
    return raw.ljust(522240,b'\0')


def bind(frozen):
    files,_=records();raw=archive(files)
    proof,activation,previous=p.build_persistent_source(raw)
    frozen.update(persistent_raw=raw,persistent_predecessor=previous)
    frozen['source_binding']['persistent_source']=proof
    frozen['source_binding']['sources']['vm_activation_archive']=proof['archive']
    assert activation.pop('execution-return-index-private.json')==frozen['activation_index']
    assert activation==frozen['activation_files']
    return proof
