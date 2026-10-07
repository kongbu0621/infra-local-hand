"""Fixed generation admission, protected old originals and independent consumers."""
import copy
import json
import os
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux held-descriptor maintenance',allow_module_level=True)

from core_prior_fixture import previous_journal_files
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_dispatcher as d
from e3_host import q2_journal_growth as h
from test_e3_q2_core_minimal_continuation import originals
from test_e3_q2_journal_growth_coordinator import rig
from test_e3_q2_journal_diagnostic_resume import source_git


@pytest.fixture
def retained(monkeypatch,tmp_path):
    raw=previous_journal_files(monkeypatch,d)
    tmp_path.chmod(0o700)
    for name,data in raw.items():
        file=tmp_path/name;file.write_bytes(data);file.chmod(0o600)
    fd=os.open(tmp_path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOATIME)
    info=os.fstat(fd)
    anchor=dict(path=str(tmp_path),dev=info.st_dev,ino=info.st_ino,mode=0o700,
        uid=info.st_uid,gid=info.st_gid)
    def call(fn,*args,returned=None,**kwargs):
        value=fn(*args,**kwargs)
        if returned is not None:returned(value)
        return value
    yield tmp_path,fd,anchor,call,raw
    os.close(fd)


def test_real_protected_reader_retains_exact_failed_prefix_without_atime_change(retained):
    root,fd,anchor,call,raw=retained
    before={name:os.stat(root/name).st_atime_ns for name in raw}
    assert p.read_previous_journal_files(fd,anchor,call)==raw
    assert {name:os.stat(root/name).st_atime_ns for name in raw}==before
    assert p.build_previous_maintenance(raw)==d._validate_maintenance_resume(p.maintenance_resume())


@pytest.mark.parametrize('name',tuple(p.PREVIOUS_JOURNAL_PINS))
@pytest.mark.parametrize('fault',['missing','bytes','mode','symlink','hardlink'])
def test_any_old_original_fault_refused_by_protected_reader(retained,name,fault):
    root,fd,anchor,call,raw=retained
    file=root/('.'+p.PREVIOUS_JOURNAL_SESSION+'.'+name)
    if fault=='missing':file.unlink()
    elif fault=='bytes':file.write_bytes(b'changed')
    elif fault=='mode':file.chmod(0o644)
    elif fault=='symlink':
        file.unlink();file.symlink_to(root/'unavailable')
    else:os.link(file,root/'alias')
    with pytest.raises((OSError,p.c.ContractError)):
        p.read_previous_journal_files(fd,anchor,call)


@pytest.mark.parametrize('suffix',p.PREVIOUS_JOURNAL_ABSENT)
def test_old_later_name_even_empty_blocks(retained,suffix):
    root,fd,anchor,call,_=retained
    (root/('.'+p.PREVIOUS_JOURNAL_SESSION+'.'+suffix)).touch()
    with pytest.raises(p.c.ContractError,match='PREVIOUS_LATER_OBJECT'):
        p.read_previous_journal_files(fd,anchor,call)


@pytest.mark.parametrize('fault',['D','authority','nonce','input','order','success','exit','actions','streams'])
def test_old_internal_relation_checked_even_with_matching_synthetic_byte_pins(monkeypatch,fault):
    raw=previous_journal_files(monkeypatch,d);prefix='.'+p.PREVIOUS_JOURNAL_SESSION+'.'
    name='pre.stderr' if fault=='actions' else 'events.jsonl' if fault=='order' else 'receipt.json'
    if fault=='order':
        data=b''.join(reversed(raw[prefix+name].splitlines(keepends=True)))
    else:
        value=json.loads(raw[prefix+name])
        if fault=='D':value['D']='1'*40
        elif fault=='authority':value['A']='1'*40
        elif fault=='nonce':value['nonce']='1'*64
        elif fault=='input':value['manifest_sha256']='1'*64
        elif fault=='success':value['state']='VERIFIED'
        elif fault=='exit':value['remote_exit']='PASS'
        elif fault=='actions':value['actions_started']=['unmount']
        elif fault=='streams':value['transports'][0]['files']['stdout']['bytes']=1
        data=h.canonical(value)
    raw[prefix+name]=data
    monkeypatch.setitem(p.PREVIOUS_JOURNAL_PINS,name,(len(data),h.digest(data)))
    with pytest.raises(p.c.ContractError):p.build_previous_maintenance(raw)


@pytest.mark.parametrize('where',['manifest','marker','receipt','input','projection'])
@pytest.mark.parametrize('fault',['session','D','digest','order','bool','extra'])
def test_new_binding_and_both_consumers_reject_changed_previous_summary(originals,where,fault):
    files,args=originals
    projection=p.build_journal_transition(files,**args)
    prefix='.'+h.SESSION+'.'
    marker=json.loads(files[prefix+'consumed.json']);receipt=json.loads(files[prefix+'receipt.json'])
    target={'manifest':marker['manifest']['resume'],'marker':marker['resume'],'receipt':receipt['resume'],
        'input':args['frozen']['source_binding']['resume'],'projection':projection['previous_maintenance']}[where]
    if fault=='session':target['session']=p.PREVIOUS_JOURNAL_SESSION
    elif fault=='D':target['previous_D']='0'*40
    elif fault=='digest':target['originals'][0]['sha256']='0'*64
    elif fault=='order':target['originals'].reverse()
    elif fault=='bool':target['old_window_consumed']=1
    else:target['retry']=True
    if where=='projection':
        with pytest.raises(p.c.ContractError):p.validate_journal_transition(projection,priors=args['priors'],implementation=args['implementation'])
        with pytest.raises(d.DispatchError):d._validate_journal_transition(projection,priors=args['priors'],implementation=args['implementation'])
    else:
        files[prefix+'consumed.json']=h.canonical(marker);files[prefix+'receipt.json']=h.canonical(receipt)
        with pytest.raises((p.c.ContractError,h.prior.r.ObservationError)):
            p.build_journal_transition(files,**args)


@pytest.mark.parametrize('fault',['changed','missing','later_name'])
def test_last_old_recheck_failure_stops_coordinator_before_new_marker(rig,fault):
    def reject():raise p.c.ContractError('CORE_JOURNAL_PREVIOUS_'+fault.upper())
    rig.anchor.previous_maintenance_recheck=reject
    result=rig.work.run(rig.manifest)
    assert result['state']=='STOP_AND_RETAIN' and result['marker_created'] is False
    assert result['ssh_requests']==0 and rig.actions==[]


@pytest.mark.parametrize('fault',['old_schema','old_session','missing_resume','wrong_pin','usage_reset'])
def test_new_preflight_rejects_old_or_changed_generation(fault):
    value=h.make_preflight('d'*40,'e'*64,dict(boot_id='11111111-2222-3333-4444-555555555555',origins=[1,2]),
        'f'*64,dict(cpu_nanoseconds=1,rss_peak_bytes=1))
    if fault=='old_schema':value['schema']='lhq-journal-growth-preflight/v1'
    elif fault=='old_session':value['resume']['session']=p.PREVIOUS_JOURNAL_SESSION
    elif fault=='missing_resume':del value['resume']
    elif fault=='wrong_pin':value['resume']['originals'][0]['bytes']+=1
    else:value['usage']['cpu_nanoseconds']=0
    with pytest.raises((p.c.ContractError,h.prior.r.ObservationError)):h.parse_preflight(h.canonical(value))


def test_fixed_two_generation_capacity_and_unchanged_action_limits():
    assert h.SESSION=='lhqjgrow-20261007a'
    assert (h.HOST_BYTES,h.HOST_INODES)==(2592*1048576,740)
    assert (h.BACKUP_CAP,h.IMAGE_CAP,h.CAPTURE_CAP)==(320*1048576,576*1048576,8*1048576)
    rows=p.maintenance_commitments()['generations']
    assert sum(row['cpu_seconds'] for row in rows)==240
    assert p.maintenance_commitments()==d._maintenance_commitments()


@pytest.mark.parametrize('record',list(p.c.SERIAL_BASELINE['documents_sha256'])+[p.c.SERIAL_OWNER_DECISION['record_path']])
def test_serial_authority_exact_bytes_are_required_before_source_admission(source_git,record):
    source_git.changed_doc=record
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_SERIAL_'):
        h.growth_sources(source_git.head)
    assert not any(call[0]=='show' and ':tests/' in call[1] for call in source_git.calls)


@pytest.mark.parametrize('edge',[(h.SERIAL_A,h.SERIAL_C),(h.SERIAL_C,'d'*40)])
def test_serial_closure_lineage_is_required(source_git,edge):
    source_git.rejected_edge=edge
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_SOURCE'):h.growth_sources(source_git.head)
