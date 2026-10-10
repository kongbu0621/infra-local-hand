"""One fixed predecessor, complete retained failures and independent core checks."""
import copy
import json
import sys

import pytest

from e3_host import q2_core_prior_attempt as p
from persistent_continuation_fixture import records, archive, source, DUMP
from core_prior_fixture import triple_fixture, journal_transition

if sys.platform.startswith('linux'):
    from e3_host import q2_core_delivery_dispatcher as d
else:
    d=None


def test_fixed_envelope_preserves_old_archive_and_restores_full_history():
    files,_=records();raw=archive(files)
    proof,old,previous=p.build_persistent_source(raw)
    assert len(raw)==522240<524288 and len(p.persistent_archive_files(raw)[0])==12
    assert old==p.activation_archive_files(files[p.PERSISTENT_INNER])
    logical=dict(resume=p.maintenance_resume(),persistent_source=proof,other='retained')
    manifest=dict(schema='lhq-journal-growth-manifest/v19',inputs=p.encode_manifest_inputs(logical),
        resume=p.encode_maintenance_resume(logical['resume'],proof))
    assert p.decode_manifest_inputs(manifest,previous)==logical
    assert len(DUMP(manifest['resume']))<len(DUMP(logical['resume']))
    assert proof['summary']['remote_exit']=='UNKNOWN'
    assert proof['summary']['coordinator_returncode']==3
    if d:assert d.validate_persistent_source(proof)==proof


@pytest.mark.parametrize('fault',['short','long','header','padding','tail','extra_member'])
def test_fixed_envelope_rejects_changed_namespace_or_bounds(fault):
    files,_=records();raw=bytearray(archive(files))
    if fault=='short':raw=raw[:-512]
    elif fault=='long':raw+=b'\0'*512
    elif fault=='header':raw[:5]=b'other'
    elif fault=='padding':raw[512+len(files[p.PERSISTENT_INNER])]=1
    elif fault=='tail':raw[-1]=1
    else:raw[-2048:-1536]=raw[:512]
    with pytest.raises(p.c.ContractError):p.build_persistent_source(bytes(raw))


@pytest.mark.parametrize('fault',['receipt_success','wrong_authority','history_loss','coordinator',
    'custodian','missing_original','invented_post','freeze','guest_success','boot','vm','source','cpu'])
def test_rehashed_old_failure_cannot_become_success_or_different_source(fault):
    files,_=records();prefix='old10c/'
    name={'receipt_success':p.PERSISTENT_ORIGINALS[-1],'wrong_authority':p.PERSISTENT_ORIGINALS[-1],
        'history_loss':p.PERSISTENT_ORIGINALS[0],'coordinator':'release-gate.json','custodian':'release-gate.json',
        'missing_original':p.PERSISTENT_RECORDS[0],'invented_post':p.PERSISTENT_RECORDS[0],
        'freeze':'ps1-freeze.json','guest_success':'.lhqjgrow-20261010c.pre.stderr','boot':'release-gate.json',
        'vm':'release-gate.json','source':p.PERSISTENT_ORIGINALS[0],'cpu':'release-gate.json'}[fault]
    value=json.loads(files[prefix+name])
    if fault=='receipt_success':value['state']='VERIFIED'
    elif fault=='wrong_authority':value['A']=p.c.PERSISTENT_PATH_BASELINE['commit']
    elif fault=='history_loss':value['manifest']['resume']['previous_maintenance'].pop()
    elif fault=='coordinator':value['rc3']['coordinator_completion']['returncode']=0
    elif fault=='custodian':value['rc3']['coordinator_completion']['child']['returncode']=3
    elif fault=='missing_original':value['files'].pop(p.PERSISTENT_ORIGINALS[-1])
    elif fault=='invented_post':value['absent'].pop()
    elif fault=='freeze':value['state']='CURRENT_READY'
    elif fault=='guest_success':value['status']='VERIFIED'
    elif fault=='boot':value['vm_activation']['current_boot_id']='9'*36
    elif fault=='vm':value['vm_activation']['vm']['pid']+=1
    elif fault=='source':value['pre_description']['source_binding_sha256']='f'*64
    elif fault=='cpu':value['rc3']['coordinator_completion']['usage']['cpu_nanoseconds']=120000000001
    files[prefix+name]=DUMP(value)
    with pytest.raises((p.c.ContractError,KeyError)):p.build_persistent_source(archive(files))


@pytest.mark.parametrize('fault',['reference','member','cycle','digest','missing','replacement'])
def test_fixed_history_reference_rejects_loss_or_substitution(fault):
    proof=source();logical=dict(resume=p.maintenance_resume(),persistent_source=proof)
    previous=p.legacy_maintenance_resume()
    manifest=dict(schema='lhq-journal-growth-manifest/v19',inputs=p.encode_manifest_inputs(logical),
        resume=p.encode_maintenance_resume(logical['resume'],proof))
    if fault=='reference':manifest['resume']['previous_reference']['field']='manifest.inputs'
    elif fault=='member':manifest['resume']['previous_reference']['member']='other'
    elif fault=='cycle':manifest['resume']['previous_reference']['field']='previous_reference'
    elif fault=='digest':manifest['inputs']['resume_sha256']='f'*64
    elif fault=='missing':previous=None
    else:previous['previous_maintenance'].pop()
    with pytest.raises((p.c.ContractError,KeyError)):p.decode_manifest_inputs(manifest,previous)


@pytest.mark.parametrize('fault',['archive_limit','reference','old_failure','missing','boolean'])
def test_both_completion_consumers_require_new_retained_failure_proof(monkeypatch,fault):
    priors,_=triple_fixture(monkeypatch,*(() if d is None else (d,)))
    implementation=dict(commit='d'*40,tree='e'*40);value=journal_transition(implementation)
    proof=value['persistent_source']
    if fault=='archive_limit':proof['archive']['bytes']=524289
    elif fault=='reference':proof['predecessor']['resume_sha256']='f'*64
    elif fault=='old_failure':proof['summary']['remote_exit']='SUCCESS'
    elif fault=='missing':value.pop('persistent_source')
    else:proof['summary']['ssh_requests']=True
    with pytest.raises((p.c.ContractError,KeyError)):
        p.validate_journal_transition(value,priors=priors,implementation=implementation)
    if d:
        with pytest.raises((d.DispatchError,KeyError)):
            d._validate_journal_transition(value,priors=priors,implementation=implementation)


def test_all_sixteen_obligations_and_completed_read_pools_remain_charged(monkeypatch):
    priors,_=triple_fixture(monkeypatch,*(() if d is None else (d,)))
    rows=p._capacity_rows(priors,p.diagnostic_retention())
    assert sum(row['bytes'] for row in rows)==21779*1048576
    assert sum(row['inodes'] for row in rows)==6336
    by_session={row['session_id']:row for row in rows}
    assert len(by_session)==len(rows)
    for name in ('lhqprotect-20261010a','lhqprotect-source-20261010a'):
        assert by_session[name]==dict(session_id=name,bytes=1048576,inodes=32)
    costs=p.maintenance_commitments()
    assert len(costs['generations'])==16 and costs['released_or_refunded'] is False
    if d:assert costs==d._maintenance_commitments()
