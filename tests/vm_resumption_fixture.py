"""Synthetic, internally consistent three-source proof; never reads a VM."""
import copy
import io
import json
import tarfile
from e3_host import q2_core_prior_attempt as p
from vm_activation_fixture import records as activation_records, index as activation_index

DUMP=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
PIN=lambda raw:dict(bytes=len(raw),sha256=p.c.sha256(raw))
BOOT='55555555-2222-3333-4444-555555555555'


def records(historical_boot='11111111-2222-3333-4444-555555555555'):
    old,_,_=activation_records(historical_boot=historical_boot)
    proposal=json.loads(old['activation-proposal-private.json'])
    proposal['package']['Package']='linux-modules-extra-6.8.0-fixture'
    old['activation-proposal-private.json']=DUMP(proposal)
    # Rebind all affected historical records, without changing their meaning.
    for name in ('explicit-owner-approval-private.json','execution-freeze-private.json','launch-consumed-private.json'):
        row=json.loads(old[name]);row['proposal_sha256']=p.c.sha256(old['activation-proposal-private.json'])
        if name!='explicit-owner-approval-private.json':row['authority_sha256']=p.c.sha256(old['explicit-owner-approval-private.json'])
        old[name]=DUMP(row)
    quota=dict(source='/dev/vdb',target='/srv/quota',fstype='ext4',uuid='quota-fixture',options='rw,nodev,nosuid,noexec,prjquota')
    guest=json.loads(old['ssh-install.stdout'])
    for i in (2,8):
        guest['steps'][i]['stdout']=DUMP(dict(filesystems=[quota])).decode()
        guest['steps'][i]['argv']=['findmnt','--json','--mountpoint',quota['target'],'-o','UUID,FSTYPE,OPTIONS']
    for i in (5,6):guest['steps'][i]['argv'][-1]=proposal['package']['Package']
    old['ssh-install.stdout']=DUMP(guest)
    binding=json.loads(old['current-vm-binding-private.json']);binding['installed_package']=proposal['package']['Package']
    for key in ('authority','launch_marker','ssh_marker','source_guest_stdout','source_result'):
        name=binding[key]['name'];binding[key]=dict(name=name,**PIN(old[name]))
    old['current-vm-binding-private.json']=DUMP(binding)
    idx=activation_index(old);hist=p.build_vm_activation(old,idx,historical_boot=historical_boot)
    old['execution-return-index-private.json']=idx
    sf={n:b'' for n in p.STARTUP_FILES};event=p.STARTUP_EVENT
    argv=list(proposal['minimal_change']['full_argv']);argv[argv.index('-serial')+1]='file:/resumed/console.log';argv[argv.index('-pidfile')+1]='/resumed/vm.pid'
    vm=dict(pid=123,starttime=1,argv_sha256=p.c.sha256(DUMP(argv)+b'\n'),exe='/usr/bin/qemu-system-x86_64',namespace='net:[1]')
    hostboot='66666666-2222-3333-4444-555555555555'
    images={name:dict(path=hist['system_path'] if name=='system' else '/fixture/'+name,metadata=dict(dev=pair[0],ino=pair[1])) for name,pair in dict(hist['image_identities'],original_system=hist['original_system_identity']).items()}
    start=dict(event='LH-Q1-VM-RESUME-PROPOSAL-20261010-01',images=images,proposed_argv=argv,original_argv=proposal['minimal_change']['full_argv'],output_directory='/resumed',host_boot_id=hostboot,network_namespace=vm['namespace'])
    sf['start-proposal-private.json']=DUMP(start);sf['start-once.py']=b'# retained startup, never executed\n'
    authority=dict(event=event,state='APPROVED',owner_reply='批准',startup_attempts=1,ssh_attempts=0,proposal_sha256=p.c.sha256(sf['start-proposal-private.json']),source_sha256=p.c.sha256(sf['start-once.py']))
    sf['explicit-owner-approval-private.json']=DUMP(authority)
    freeze=dict(event=event,proposal_sha256=authority['proposal_sha256'],approval_sha256=p.c.sha256(sf['explicit-owner-approval-private.json']),files={'start-once.py':PIN(sf['start-once.py'])})
    sf['execution-freeze-private.json']=DUMP(freeze)
    sf['launch-consumed-private.json']=DUMP(dict(event=event,proposal_sha256=authority['proposal_sha256'],authority_sha256=freeze['approval_sha256'],argv=argv,host_boot_id=hostboot,image_bindings=images))
    result=dict(event=event,state='STARTED_AND_HOST_ENDPOINT_VERIFIED',startup_calls=1,ssh_calls=0,listener_queries=1,listener='PRESENT',errors=[],original_system_and_old_serial_preserved=True,guest_boot_id='UNKNOWN',guest_ssh_ready='UNKNOWN',identity_checks=[dict(actual={},expected={},differences={}) for _ in range(49)],commands=[dict(label=n,eof=True,returncode=0) for n in ('qemu-version','qemu-start','listener')],host_boot_id=hostboot,new_vm=vm,images_before=images,elapsed_seconds=1.5)
    sf['result-private.json']=DUMP(result);sf['new-pid-cmdline.raw']=b'\0'.join(s.encode() for s in argv)+b'\0';sf['new-pid-stat.raw']=b'123 (qemu) S '+b'0 '*18+b'1\n';sf['new-pidfile.raw']=b'123\n'
    sf['execution-return-index-private.json']=DUMP(dict(event=event,result_state=result['state'],files=p._resume_pins(sf),nonruntime_test_source_reference=dict(name='check_control_flow.py',not_reread_or_executed=True,preparation_pin=PIN(b'synthetic'))))
    pf={n:b'' for n in p.HOST_PREFLIGHT_FILES};oldD=p.host_preflight_summary()['D'];session=p.host_preflight_summary()['session']
    pf['tc2-caller-started.json']=DUMP(dict(D=oldD,session=session))
    summary=dict(D=oldD,reason='GROWTH_ACTIVATION_HOST_BOOT',ssh_requests=0,marker_created=False,diagnostic={},state='BLOCKED',phase='preflight',exit_code=3,started=None,last_step=None,business_cases=None)
    pf['tc2-preflight.stdout']=DUMP(summary);pf['tc2-summary.json']=pf['tc2-caller.stdout']=DUMP(summary)
    frozen=dict(implementation=dict(commit=oldD),callers={'old.py':'a'*64});pf['freeze-complete.json']=DUMP(frozen)
    failed=dict(summary,frozen_sha256=p.c.sha256(pf['freeze-complete.json']),session=session,originals={},maintenance_window_consumed=False,core='NOT_RUN',coordinator_completion='NOT_CAPTURED',core_package='NOT_BUILT',caller_exit=3,remote_exit='UNKNOWN',local_returns={n:PIN(pf[n]) for n in p.HOST_PREFLIGHT_FILES[:6]})
    failed['state']='TC2_PREFLIGHT_FAILED_TC3_NOT_RUN';pf['tc2-failure-private.json']=DUMP(failed)
    pf['release-gate.json']=DUMP(dict(frozen,state=failed['state'],tc2=failed,tc3=dict(core_package='NOT_BUILT',reason='INCOMPLETE_TC2',state='NOT_RUN')))
    gf={n:b'' for n in p.GUEST_VERIFICATION_FILES};event=p.RESUMPTION_EVENT
    gp=dict(event=event,historical_activation_sha256=p.c.sha256(p.c.canonical(hist)),startup_index_sha256=p.c.sha256(sf['execution-return-index-private.json']),host_preflight_index_sha256=p.c.sha256(p.c.canonical(p._resume_pins(pf))),expected_host_boot_id=hostboot,expected_vm=vm,package=proposal['package'],quota=quota,ssh_prefix=['ssh','fixed'],implementation=dict(commit='d'*40,tree='e'*40),guest_source_sha256='a'*64)
    gf['proposal.json']=DUMP(gp);gf['check-approved.py']=b'# synthetic one-shot guest caller\n'
    gf['approval.json']=DUMP(dict(event=event,owner_reply='批准',R=p.c.RULE['commit'],A=p.c.PROTECTED_SOURCE_BASELINE['commit'],C=p.c.PROTECTED_SOURCE_CLOSURE['commit'],state='APPROVED'))
    gf['freeze.json']=DUMP(dict(event=event,implementation=gp['implementation'],proposal=PIN(gf['proposal.json']),caller=PIN(gf['check-approved.py']),approval=PIN(gf['approval.json'])))
    bind_protected_sources(gf)
    gf['consumed.json']=DUMP(dict(event=event,nonce='9'*64,freeze_sha256=p.c.sha256(gf['freeze.json'])))
    outputs=['6.8.0-fixture\n','install ok installed\t1.0','', '6.8.0-fixture SMP\n','insmod /lib/modules/6.8.0-fixture/kernel/fs/quota/quota_v2.ko\n',DUMP(dict(filesystems=[quota])).decode()]
    steps=[dict(label=label,argv=argv,exit=0,eof=True,stdout=out,stderr='') for (label,argv),out in zip(p.current_guest_commands(gp['package'],quota['target']),outputs)]
    gf['guest.stdout']=DUMP(dict(schema='local-hand-q2-current-guest/v1',status='VERIFIED',nonce='9'*64,boot_id=BOOT,boot_end=BOOT,steps=steps,package_install_calls=0,module_load_calls=0,reboots=0,management_usage=dict(cpu_nanoseconds=100,rss_peak_bytes=1000,elapsed_nanoseconds=10000)))
    returned=dict(event=event,implementation=gp['implementation'],guest_source_sha256=gp['guest_source_sha256'],management_usage=dict(cpu_nanoseconds=100,rss_peak_bytes=1000),state='CURRENT_GUEST_VERIFIED',nonce='9'*64,marker_sha256=p.c.sha256(gf['consumed.json']),ssh_calls=1,startup_calls=0,package_install_calls=0,retries=0,guest_returncode=0,guest_eof=True,errors=[],guest_stdout=PIN(gf['guest.stdout']),guest_stderr=PIN(gf['guest.stderr']),host_before=dict(boot_id=hostboot,vm=vm),host_after=dict(boot_id=hostboot,vm=vm),image_identities=dict(hist['image_identities'],original_system=hist['original_system_identity']),guest_boot_id=BOOT)
    gf['result.json']=DUMP(returned)
    gf['caller.stdout']=DUMP(dict(event=event,state=returned['state'],result_sha256=p.c.sha256(gf['result.json'])))
    files={group+'/'+name:raw for group,parts in (('activation',old),('startup',sf),('old10b',pf),('guest',gf)) for name,raw in parts.items()}
    return files,index(files),historical_boot


def index(files):
    return DUMP(dict(schema='local-hand-q2-vm-resumption-sources/v1',event=p.RESUMPTION_EVENT,files=p._resume_pins(files),references=p.RESUMPTION_REFERENCES,guest_caller_completion=dict(returncode=0,stdout_eof=True,stderr_eof=True,stdout=PIN(files['guest/caller.stdout']),stderr=PIN(files['guest/caller.stderr']))))


def archive(files,idx):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as tar:
        for name,raw in sorted(dict(files,**{'execution-return-index-private.json':idx}).items()):
            if name in p.RESUMPTION_REFERENCES:
                assert raw==files[p.RESUMPTION_REFERENCES[name]]
                continue
            member=tarfile.TarInfo(name);member.size=len(raw);member.mode=0o600;tar.addfile(member,io.BytesIO(raw))
    return stream.getvalue()


def bind_protected_sources(gf):
    """Synthetic retention/preparation, explicitly confined to offline fixtures."""
    authority=json.loads(gf['approval.json']);freeze=json.loads(gf['freeze.json'])
    pins={n:dict(bytes=1,sha256='a'*64) for n in (*p.JOURNAL_SOURCE_NAMES,'q2_current_guest_verification.py')}
    failure=dict(event=p.c.RESUMED_VM_OWNER_DECISION['event'],D='0eece27637930dfc31f724c7dd1392e11a47cad9',
        state='INVOKED_FAILED_UNCONSUMED',reason='LOCAL_PARENT',ssh_calls=0,marker_created=False,
        guest_streams='ABSENT',remote_exit='UNKNOWN',index=PIN(b'old index'),freeze=PIN(b'old freeze'),terminal=PIN(b'old terminal'))
    prep=dict(state='PREPARED',source_index_sha256=p.c.sha256(p.c.canonical(pins)),source_bytes=14,
        allocated_bytes=65536,inodes=16,cpu_nanoseconds=100,rss_peak_bytes=4096,elapsed_nanoseconds=100)
    for row in (authority,freeze):row.update(previous_guest_failure=failure,source_preparation=prep)
    gf['approval.json']=DUMP(authority);freeze.update(source_pins=pins,approval=PIN(gf['approval.json']))
    gf['freeze.json']=DUMP(freeze)
