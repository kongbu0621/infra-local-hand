"""Lossless single-history encoding and independent custody/exit validation."""
import copy
import json
import sys

import pytest
from e3_host import q2_core_prior_attempt as p
from core_prior_fixture import previous_journal_files, journal_transition, triple_fixture
from persistent_continuation_fixture import source

if sys.platform.startswith('linux'):
    from e3_host import q2_core_delivery_dispatcher as d
else:
    d=None


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='retained guest report parser')
def test_full_history_reconstruction_and_exact_old09b_failure(monkeypatch):
    files=previous_journal_files(monkeypatch,d)
    assert len(files)==55
    resume=p.build_previous_maintenance(files)
    assert len(resume['previous_maintenance'])==11
    old=resume['previous_maintenance'][-1]
    assert old['session']=='lhqjgrow-20261009b' and old['remote_exit']=='UNKNOWN'
    assert old['reason']=='LOCAL_IO_OR_TRANSPORT'
    original=dict(resume=resume,persistent_source=source(),inventory_sha256='a'*64,other=dict(retained=True))
    compact=p.encode_manifest_inputs(original)
    manifest=dict(schema='lhq-journal-growth-manifest/v19',resume=p.encode_maintenance_resume(resume,source()),inputs=compact)
    assert p.decode_manifest_inputs(manifest,p.legacy_maintenance_resume())==original
    assert len(p.c.canonical(compact))<len(p.c.canonical(original))
    assert 'resume' not in compact and original['resume']==resume


@pytest.mark.parametrize('fault',['digest','missing_ref','double','history','old_version','source'])
def test_history_encoding_faults_cannot_change_full_source_binding(monkeypatch,fault):
    original=dict(resume=p.maintenance_resume(),persistent_source=source(),inventory_sha256='a'*64)
    manifest=dict(schema='lhq-journal-growth-manifest/v19',resume=p.encode_maintenance_resume(original['resume'],source()),
        inputs=p.encode_manifest_inputs(original))
    if fault=='digest':manifest['inputs']['resume_sha256']='f'*64
    elif fault=='missing_ref':manifest['inputs'].pop('resume_sha256')
    elif fault=='double':manifest['inputs']['resume']=original['resume']
    elif fault=='history':manifest['resume']['previous_runtime_failure']['state']='PASS'
    elif fault=='old_version':manifest['schema']='lhq-journal-growth-manifest/v12'
    elif fault=='source':
        manifest['inputs']['inventory_sha256']='b'*64
        restored=p.decode_manifest_inputs(manifest,p.legacy_maintenance_resume())
        assert p.c.sha256(p.c.canonical(restored))!=p.c.sha256(p.c.canonical(original))
        return
    with pytest.raises(p.c.ContractError):p.decode_manifest_inputs(manifest,p.legacy_maintenance_resume())


@pytest.mark.parametrize('fault',['fields','count','pid','checks','bytes','pin','same_inode','mode',
    'D','nonce','source','history','set_hash','coordinator','child','cpu','rss','receipt'])
def test_both_portable_consumers_reject_custody_or_real_exit_fault(monkeypatch,fault):
    priors,_=triple_fixture(monkeypatch,*(() if d is None else (d,)))
    implementation=dict(commit='d'*40,tree='e'*40)
    value=journal_transition(implementation);custody=value['retained_custody'];finish=value['coordinator_completion']
    if fault=='fields':custody['extra']=True
    elif fault in ('count','pid','checks'):custody[fault]=True
    elif fault=='bytes':custody['ipc_bytes']=4194305
    elif fault=='pin':custody['originals'][0]['sha256']='f'*64
    elif fault=='same_inode':custody['originals'][1]['metadata']['ino']=custody['originals'][0]['metadata']['ino']
    elif fault=='mode':custody['originals'][0]['metadata']['mode']=33188
    elif fault in ('D','nonce'):custody['binding'][fault]='f'*(40 if fault=='D' else 64)
    elif fault in ('source','history','set_hash'):custody['binding'][{'source':'source_sha256','history':'history_sha256','set_hash':'set_sha256'}[fault]]='f'*64
    elif fault=='coordinator':finish['returncode']=3
    elif fault=='child':finish['child']['returncode']=3
    elif fault=='cpu':finish['usage']['cpu_nanoseconds']=240000000001
    elif fault=='rss':finish['usage']['rss_peak_bytes']=1073741825
    elif fault=='receipt':finish['receipt_sha256']='f'*64
    with pytest.raises((p.c.ContractError,KeyError)):p.validate_journal_transition(value,priors=priors,implementation=implementation)
    if d is not None:
        with pytest.raises((d.DispatchError,KeyError)):d._validate_journal_transition(value,priors=priors,implementation=implementation)


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='full original host report consumer')
def test_success_requires_real_top_level_exit_even_when_receipt_verified(originals):
    files,args=originals
    args['frozen']['coordinator_completion']['returncode']=3
    with pytest.raises(p.c.ContractError,match='COORDINATOR_EXIT'):
        p.build_journal_transition(files,**args)


if sys.platform.startswith('linux'):
    from test_e3_q2_core_minimal_continuation import originals, effects


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='actual retained identity relation')
def test_custody_identity_cannot_be_self_reported_with_recomputed_hash(originals):
    files,args=originals
    # This is the independently re-observed retained source, not the receipt.
    args['frozen']['previous_maintenance_identities'][0]['metadata']['ino']+=10000
    with pytest.raises(p.c.ContractError,match='CUSTODY_RETAINED_IDENTITIES'):
        p.build_journal_transition(files,**args)


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='host transport originals')
@pytest.mark.parametrize('fault',[None,'tool_255','missing_pre','wrong_pre','duplicate_pre'])
def test_pre_ssh_255_requires_exact_verified_transport_process(originals,fault):
    files,args=originals
    name='.'+p.JOURNAL_SESSION+'.receipt.json'
    receipt=json.loads(files[name]);assert receipt['processes'][1]['exit']==255
    if fault=='tool_255':receipt['processes'][0]['exit']=255
    elif fault=='missing_pre':receipt['processes'].pop(1)
    elif fault=='wrong_pre':receipt['processes'][1]['identity']['pid']=999
    elif fault=='duplicate_pre':receipt['processes'].append(copy.deepcopy(receipt['processes'][1]))
    files[name]=p.c.canonical(receipt,newline=True)
    args['frozen']['coordinator_completion']['receipt_sha256']=p.c.sha256(files[name])
    if fault:
        with pytest.raises(p.c.ContractError,match='JOURNAL_(PROCESS_EXIT|TRANSPORT_PROCESS)'):
            p.build_journal_transition(files,**args)
    else:
        assert p.build_journal_transition(files,**args)['transport_exits']==[255,0]


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='real guest producer with synthetic effects')
@pytest.mark.parametrize('originals',['actual_guest'],indirect=True)
def test_actual_guest_reports_reach_both_independent_core_consumers(originals):
    files,args=originals
    value=p.build_journal_transition(files,**args)
    assert d._validate_journal_transition(value,priors=args['priors'],implementation=args['implementation'])==value
    assert value['transport_exits']==[255,0] and value['all_streams_eof'] is True
