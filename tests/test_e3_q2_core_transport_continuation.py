"""Absent receipts stay absent; source changes never become maintenance success."""
import copy
import io
import json
import sys
import tarfile

import pytest
from e3_host import q2_core_prior_attempt as p
from local_preflight_fixture import archive
from transport_failure_fixture import records, source_projection

if sys.platform.startswith('linux'):
    from e3_host import q2_core_delivery_dispatcher as d
else:
    d=None


def test_four_original_failure_with_full_local_returns_and_no_refund(monkeypatch):
    raw,spec,_=records(monkeypatch,*(() if d is None else (d,)))
    value=p.build_transport_failure_source(raw,spec)
    assert len(value['originals'])==15 and len(value['summary']['originals'])==4
    assert value['summary']['missing_expected']==['.lhqjgrow-20261010a.receipt.json']
    resume=p.maintenance_resume()
    assert len(resume['previous_maintenance'])==11
    assert resume['previous_local_preflight']['maintenance_window_consumed'] is False
    assert resume['previous_transport_failure']['maintenance_window_consumed'] is True
    costs=p.maintenance_commitments()['generations']
    assert len(costs)==16 and sum(r['bytes'] for r in costs)==20736*1048576
    assert sum(r['inodes'] for r in costs)==5920 and sum(r['cpu_seconds'] for r in costs)==1920
    if d is not None:
        assert d.validate_transport_failure_source(value)==value
        assert d._maintenance_resume()==resume and d._maintenance_commitments()==p.maintenance_commitments()


@pytest.mark.parametrize('fault',['missing','extra_receipt','duplicate','symlink','hardlink','oversize',
    'truncated','trailing','external_pin','freeze','caller','terminal','D','diagnostic','remote_success',
    'completion','missing_receipt_claim','count','boolean_count','marker','nonce','history','clocks','events','preflight'])
def test_archive_and_old_failure_relations_reject_resealed_false_claims(monkeypatch,fault):
    raw,spec,files=records(monkeypatch)
    def change(name,key,value):
        row=json.loads(files[name]);row[key]=value;files[name]=p.c.canonical(row,newline=True)
    if fault=='missing':files.pop('uc2-summary.json')
    elif fault=='extra_receipt':files['.lhqjgrow-20261010a.receipt.json']=b'{}\n'
    elif fault=='freeze':change('freeze-complete.json','D','f'*40)
    elif fault=='caller':spec['callers']['core_once.py']='f'*64
    elif fault=='terminal':change('release-gate.json','state','VERIFIED')
    elif fault in ('D','diagnostic','remote_success','completion','missing_receipt_claim','count','boolean_count'):
        key,value={'D':('D','f'*40),'diagnostic':('diagnostic',{}),'remote_success':('remote_exit','COMPLETE'),
            'completion':('coordinator_completion',dict(returncode=0)),'missing_receipt_claim':('missing_expected',[]),
            'count':('ssh_requests',0),'boolean_count':('ssh_requests',True)}[fault]
        change('uc2-failure-private.json',key,value)
        gate=json.loads(files['release-gate.json']);gate['uc2']=json.loads(files['uc2-failure-private.json'])
        files['release-gate.json']=p.c.canonical(gate,newline=True)
    elif fault in ('marker','nonce','history','clocks'):
        name='.lhqjgrow-20261010a.consumed.json';row=json.loads(files[name])
        if fault=='marker':row['D']='f'*40
        elif fault=='nonce':row['nonce']='f'*64
        elif fault=='clocks':row['clocks']=[3,4]
        else:row['manifest']['resume']['previous_maintenance'].pop()
        files[name]=p.c.canonical(row,newline=True)
    elif fault=='events':files['.lhqjgrow-20261010a.events.jsonl']+=b'{"step":"POWER_OFF_TOKEN","state":"STARTED"}\n'
    elif fault=='preflight':change('uc2-preflight.stdout','state','BLOCKED')
    raw=archive(files)
    if fault in ('duplicate','symlink','hardlink','oversize'):
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as tar:
            for name,data in files.items():
                member=tarfile.TarInfo(name);member.size=len(data);tar.addfile(member,io.BytesIO(data))
            member=tarfile.TarInfo('uc2-summary.json');member.linkname='uc2-caller.stdout'
            if fault=='symlink':member.type=tarfile.SYMTYPE
            elif fault=='hardlink':member.type=tarfile.LNKTYPE
            elif fault=='oversize':member.size=65537
            tar.addfile(member,io.BytesIO(b'x'*member.size))
        raw=stream.getvalue()
    if fault=='truncated':raw=raw[:100]
    elif fault=='trailing':raw+=b'x'*512
    spec.update(bytes=len(raw),sha256=p.c.sha256(raw))
    if fault!='external_pin':spec['originals']={n:dict(bytes=len(b),sha256=p.c.sha256(b)) for n,b in files.items()}
    else:spec['originals']['uc2-summary.json']['sha256']='f'*64
    with pytest.raises((p.c.ContractError,KeyError)):
        p.build_transport_failure_source(raw,spec)


@pytest.mark.parametrize('fault',['schema','summary','receipt','consumed','count','boolean','archive','freeze',
    'caller','pin','empty_stream','diagnostic','extra'])
def test_independent_portable_consumers_reject_false_projection(fault):
    value=source_projection()
    if fault=='schema':value['schema']='local-hand-q2-local-preflight-source/v1'
    elif fault=='summary':value['summary']['D']='f'*40
    elif fault=='receipt':value['summary']['missing_expected']=[]
    elif fault=='consumed':value['summary']['maintenance_window_consumed']=False
    elif fault in ('count','boolean'):value['summary']['ssh_requests']=0 if fault=='count' else True
    elif fault=='archive':value['archive']['bytes']=196609
    elif fault=='freeze':value['freeze_sha256']='f'*64
    elif fault=='caller':value['callers'].pop('maintenance_once.py')
    elif fault=='pin':value['originals']['uc2-summary.json']['sha256']='f'*64
    elif fault=='empty_stream':value['originals']['.lhqjgrow-20261010a.pre.stdout']['bytes']=1
    elif fault=='diagnostic':value['diagnostic_sha256']=None
    else:value['unexpected']=True
    with pytest.raises(p.c.ContractError):p.validate_transport_failure_source(value)
    if d is not None:
        with pytest.raises(d.DispatchError):d.validate_transport_failure_source(value)


@pytest.mark.parametrize('fault',['drop','unconsume','refund','old_session'])
def test_new_resume_never_drops_old10a_or_old09c_obligation(fault):
    value=copy.deepcopy(p.maintenance_resume())
    if fault=='drop':value.pop('previous_transport_failure')
    elif fault=='unconsume':value['previous_transport_failure']['maintenance_window_consumed']=False
    elif fault=='refund':value['previous_local_preflight']['old_commitments_refunded']=True
    else:value['session']='lhqjgrow-20261010a'
    with pytest.raises(p.c.ContractError):p.validate_maintenance_resume(value)
    if d is not None:
        with pytest.raises(d.DispatchError):d._validate_maintenance_resume(value)


if sys.platform.startswith('linux'):
    from test_e3_q2_journal_diagnostic_resume import source_git
    from test_e3_q2_core_minimal_continuation import originals,effects


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='host source authority')
@pytest.mark.parametrize('fault',['A','B','tree','ancestry'])
def test_tc_authority_precedes_any_field_effect(source_git,fault):
    from e3_host import q2_journal_growth as h
    if fault=='A':source_git.changed_doc=next(iter(p.c.TRANSPORT_BASELINE['documents_sha256']))
    elif fault=='B':source_git.changed_doc=p.c.TRANSPORT_OWNER_DECISION['record_path']
    elif fault=='tree':source_git.changed_tree=h.TC_C
    else:source_git.rejected_edge=(h.TC_C,source_git.head)
    with pytest.raises(h.prior.r.ObservationError):h.growth_sources(source_git.head)


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='source-aware host consumer')
def test_success_receipt_cannot_replace_retained_transport_archive(originals):
    files,args=originals
    args['frozen']['transport_failure_raw']=b'not the frozen archive'
    with pytest.raises(p.c.ContractError,match='TRANSPORT_FAILURE_ARCHIVE_PIN'):
        p.build_journal_transition(files,**args)
