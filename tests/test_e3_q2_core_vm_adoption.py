"""Retained activation adoption and three-boot continuation, entirely synthetic."""
import copy
import io
import json
import os
import tarfile
from pathlib import Path
from types import SimpleNamespace
import pytest
import sys
if not sys.platform.startswith("linux"):
    pytest.skip("Linux activation and maintenance originals",allow_module_level=True)
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_dispatcher as d
from e3_host import q2_journal_growth as h
from test_e3_q2_core_minimal_continuation import originals
from vm_activation_fixture import records,index

def test_retained_activation_requires_all_thirty_exact_bytes():
    files,idx,boot=records()
    value=p.build_vm_activation(files,idx,historical_boot=boot)
    assert d._validate_vm_activation(value)==value
    assert value['candidate_digest_scope']=='PRELAUNCH_ONLY'
    assert not value['execution_permission']
    for name in files:
        changed=dict(files);changed[name]+=b'x'
        with pytest.raises(p.c.ContractError):p.build_vm_activation(changed,idx,historical_boot=boot)
    del files['index-preparation-note-private.json']
    with pytest.raises(p.c.ContractError):p.build_vm_activation(files,index(files),historical_boot=boot)

@pytest.mark.parametrize('case',['approval','helper','failed_install','integrity','quota','argv','stat','package','script','boolean_count'])
def test_rehashed_bad_activation_remains_rejected(case):
    files,_,boot=records()
    name='result-private.json'
    if case=='approval':name='explicit-owner-approval-private.json'
    elif case in ('failed_install','integrity','quota','package'):name='ssh-install.stdout'
    elif case=='script':name='ssh-consumed-private.json'
    if case=='helper':files['activate-approved.py']+=b'changed'
    elif case=='argv':files['new-pid-cmdline.raw']+=b'--extra\0'
    elif case=='stat':files['new-pid-stat.raw']=files['new-pid-stat.raw'].replace(b'1\n',b'2\n')
    else:
        value=json.loads(files[name])
        if case=='approval':value['state']='PENDING'
        elif case=='failed_install':value['steps'][4]['exit']=1
        elif case=='integrity':value['steps'][6]['stdout']='changed installed module'
        elif case=='quota':value['steps'][8]['stdout']='{"filesystems":[]}'
        elif case=='package':value['steps'][4]['argv']=['dpkg','--install','/unapproved.deb']
        elif case=='script':value['script_sha256']='0'*64
        else:value['startup_calls']=True
        files[name]=p.c.canonical(value)
    with pytest.raises(p.c.ContractError):p.build_vm_activation(files,index(files),historical_boot=boot)

@pytest.mark.parametrize('originals',[True],indirect=True)
def test_actual_producer_and_independent_consumer_keep_three_boots(originals):
    files,args=originals
    value=p.build_journal_transition(files,**args)
    assert d._validate_journal_transition(value,priors=args['priors'],implementation=args['implementation'])==value
    activation=value['vm_activation']
    assert len({activation['historical_boot_id'],value['old_boot_id'],value['new_boot_id']})==3
    assert len(value['previous_maintenance']['previous_maintenance'])==11
    marker=json.loads(files['.'+h.SESSION+'.consumed.json'])
    assert 'resume' not in marker and marker['resume_sha256']==h.resume_sha256(marker['manifest']['resume'])
    assert len(h.canonical(marker))<=65536

@pytest.mark.parametrize('originals',[True],indirect=True)
@pytest.mark.parametrize('case',['history','current','pid','start','image','same_system','permission','missing','old_window','digest_scope'])
def test_both_consumers_reject_mixed_identity(originals,case):
    files,args=originals;value=p.build_journal_transition(files,**args)
    activation=value['vm_activation']
    if case=='history':activation['historical_boot_id']=value['old_boot_id']
    elif case=='current':activation['current_boot_id']=value['new_boot_id']
    elif case=='pid':activation['vm']['pid']+=1
    elif case=='start':activation['vm']['starttime']+=1
    elif case=='image':activation['image_identities']['system'][1]+=100
    elif case=='same_system':activation['original_system_identity']=activation['image_identities']['system']
    elif case=='permission':activation['execution_permission']=True
    elif case=='missing':value['vm_activation']=None
    elif case=='old_window':value['session']=p.NINTH_JOURNAL_SESSION
    else:activation['candidate_digest_scope']='CURRENT_CONTENT'
    for verify in (p.validate_journal_transition,d._validate_journal_transition):
        with pytest.raises((p.c.ContractError,d.DispatchError)):verify(value,priors=args['priors'],implementation=args['implementation'])

@pytest.mark.parametrize('originals',[True],indirect=True)
def test_digest_reference_cannot_drop_full_history(originals):
    files,args=originals;prefix='.'+h.SESSION+'.'
    marker=json.loads(files[prefix+'consumed.json'])
    marker['resume_sha256']='0'*64;files[prefix+'consumed.json']=h.canonical(marker)
    with pytest.raises(p.c.ContractError,match='PREVIOUS_DIGEST'):p.build_journal_transition(files,**args)

@pytest.mark.parametrize('bad',['duplicate','link','extra','missing'])
def test_activation_archive_rejects_nonexact_members_before_adoption(bad):
    files,idx,_=records();members=list(dict(files,**{'execution-return-index-private.json':idx}).items())
    if bad=='duplicate':members.append(members[0])
    elif bad=='extra':members.append(('../escape',b'x'))
    elif bad=='missing':members.pop()
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w') as archive:
        for i,(name,raw) in enumerate(members):
            member=tarfile.TarInfo(name);member.size=len(raw)
            if bad=='link' and i==0:member.type=tarfile.SYMTYPE;member.linkname='/outside'
            archive.addfile(member,io.BytesIO(raw))
    raw=stream.getvalue()
    fake=SimpleNamespace(read=lambda *a:raw)
    with pytest.raises(h.prior.r.ObservationError):h.adopt_vm_activation(fake,{},dict(path='/fixture/a.tar',bytes=len(raw),sha256=h.digest(raw)))

def test_external_active_system_keeps_identity_and_write_protection(tmp_path,monkeypatch):
    anchor=tmp_path/'anchor';active=tmp_path/'active';anchor.mkdir();active.mkdir()
    argv=[];images={}
    for i,role in enumerate(('system','quota','journal','evidence','seed')):
        path=(active/'system-repaired.qcow2' if role=='system' else anchor/(role+('.iso' if role=='seed' else '.qcow2')))
        path.write_bytes(b'fixture');path.chmod(0o600);info=path.stat();images[role]=[info.st_dev,info.st_ino]
        options='format=raw,readonly=on' if role=='seed' else 'format=qcow2,id='+('os' if role=='system' else role)
        argv+=['-drive',options+',file='+str(path)]
    argv+=['-device','virtio-blk-pci,drive=journal,serial=journal']
    files,idx,boot=records();proof=p.build_vm_activation(files,idx,historical_boot=boot)
    proof.update(system_path=str(active/'system-repaired.qcow2'),image_identities=images,original_system_identity=[images['system'][0],999999999])
    monkeypatch.setattr(h.local,'open_directory',lambda path,owner:os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW))
    fd=os.open(anchor,os.O_RDONLY|os.O_DIRECTORY)
    value=h.ImageSet(fd,str(anchor),argv,lambda:None,activation=proof)
    try:
        path=Path(proof['system_path']);path.write_bytes(b'approved live guest writes')
        value.recheck()
        with pytest.raises(h.prior.r.ObservationError,match='IMAGE_WRITE'):value.recheck(stable=True)
        value.checkpoint();value.recheck(stable=True)
        path.rename(active/'retained');path.write_bytes(b'replaced');path.chmod(0o600)
        with pytest.raises(h.prior.r.ObservationError,match='IMAGE_DRIFT'):value.recheck()
    finally:value.close();os.close(fd)

def test_pending_adoption_cannot_open_field_window(monkeypatch,capsys):
    monkeypatch.setattr(h.history.c,'VM_ADOPTION_CLOSURE',None)
    monkeypatch.setattr(h.os,'geteuid',lambda:1000)
    monkeypatch.setattr(h.sys,'argv',['growth','--frame','fixed','--plan-archive','fixed','--archives-dir','fixed',
        '--expected-commit','d'*40,'--trusted-single-admin','--trusted-guest-startup'])
    monkeypatch.setattr(h,'growth_sources',lambda *_:pytest.fail('pending authority reached source/field admission'))
    assert h.main()==3
    result=json.loads(capsys.readouterr().out)
    assert result['reason']=='GROWTH_RC_NOT_AUTHORIZED'
    assert not result['marker_created'] and result['ssh_requests']==0

@pytest.mark.parametrize('originals',[True],indirect=True)
def test_activated_transition_round_trips_complete_core_package(originals,monkeypatch):
    from e3_host import q2_core_approved_inputs as approved
    from e3_host import q2_core_delivery_package as package
    from e3_host import q2_core_delivery_entry as entry
    from test_e3_q2_core_approved_inputs import artifact
    import test_e3_q2_core_delivery_package as envelope
    files,args=originals
    transition=p.build_journal_transition(files,**args)
    value,_,_=artifact.__wrapped__(monkeypatch)
    value['reconciliation']['journal_transition']=transition
    raw=approved.c.canonical(value,newline=True)
    assert approved.validate(raw)==value
    monkeypatch.setattr(envelope,'IMPLEMENTATION',args['implementation'])
    manifest,members=envelope.fixture(monkeypatch)
    monkeypatch.setattr(package,'_approved_module',lambda:approved)
    row,header=package.approved_input_member(raw,amendment=manifest['amendment'])
    manifest['approved_inputs']=header
    manifest['members']=[row if item['role']=='approved-inputs' else item for item in manifest['members']]
    members[row['path']]=raw
    # Exercise the actual code-member byte limits, not short dispatcher stubs.
    code={role:Path(h.__file__).with_name('q2_core_delivery_'+role+'.py').read_bytes() for role in ('loader','bootstrap','dispatcher')}
    rows,raws=package.field_member_blobs(code['loader'],code['bootstrap'],code['dispatcher'],implementation_commit=args['implementation']['commit'])
    manifest['members']=[item for item in manifest['members'] if item['role']!='field-code']+rows
    manifest['members'].sort(key=lambda item:item['path'])
    members.update(raws)
    for role,data in code.items():
        manifest['entry'][role+'_bytes']=len(data)
        manifest['entry'][role+'_sha256']=h.digest(data)
    encoded=package.build_package(manifest,members)
    decoded,restored=package.parse_package(encoded)
    assert decoded==manifest and restored==members
    forwarded=d._approved_inputs_envelope(dict(manifest=decoded,members=restored))
    assert d._validate_journal_transition(forwarded['reconciliation']['journal_transition'],priors=args['priors'],implementation=args['implementation'])==transition
    assert len(raw)<=1048576 and len(encoded)<=32*1048576
    if entry.contract.VM_ADOPTION_CLOSURE is None:
        with pytest.raises(entry.contract.ContractError,match='RELEASE_GATE'):entry.field_release_gate(decoded,restored)
