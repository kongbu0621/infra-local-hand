"""Fixed old10d completion and lossless history; no field permission from tests."""
import copy
import json
import sys

import pytest

from e3_host import q2_core_prior_attempt as p
from identity_continuation_fixture import records,archive,source,DUMP

if sys.platform.startswith('linux'):
    from e3_host import q2_core_delivery_dispatcher as d
else:d=None


def test_fixed_archive_preserves_raw_completion_and_old_history():
    files,_=records();raw=archive(files)
    proof,activation,previous=p.build_identity_source(raw)
    assert len(raw)==798720<1048576 and len(p.identity_archive_files(raw)[0])==19
    prior,old,legacy=p.build_persistent_source(files[p.IDENTITY_INNER])
    assert proof['prior']==prior and activation==old
    assert previous==p.persistent_maintenance_resume() and legacy==p.legacy_maintenance_resume()
    assert previous['session']=='lhqjgrow-20261010d' and p.maintenance_resume()['session']=='lhqjgrow-20261011a'
    logical=dict(resume=p.maintenance_resume(),persistent_source=proof)
    manifest=dict(schema='lhq-journal-growth-manifest/v20',inputs=p.encode_manifest_inputs(logical),
        resume=p.encode_maintenance_resume(logical['resume'],proof))
    assert p.decode_manifest_inputs(manifest,previous)==logical
    assert len(DUMP(manifest['resume']))<len(DUMP(logical['resume']))
    assert proof['summary']['remote_exit']=='UNKNOWN' and proof['summary']['core_cases']=='NOT_RUN'
    if d:assert d.validate_identity_source(proof)==proof


@pytest.mark.parametrize('fault',['short','long','order','padding','extra_member'])
def test_fixed_archive_rejects_changed_shape(fault):
    files,_=records();raw=bytearray(archive(files))
    if fault=='short':raw=raw[:-512]
    elif fault=='long':raw+=b'\0'*512
    elif fault=='order':raw[:6]=b'other/'
    elif fault=='padding':raw[512+len(files[p.IDENTITY_MEMBERS[0]])]=1
    else:raw[-2048:-1536]=raw[:512]
    with pytest.raises(p.c.ContractError):p.build_identity_source(bytes(raw))


@pytest.mark.parametrize('fault',['success','authority','history','guest_success','guest_source',
    'diagnostic','freeze','core_run','receipt_hash','coordinator','custodian','cpu','rss',
    'caller_exit','caller_stdout','caller_stderr','execute','preflight','index','absent','started'])
def test_rehashed_originals_cannot_change_failure_or_actual_completion(fault):
    files,_=records()
    name={
        'success':p.IDENTITY_ORIGINALS[-1],'authority':p.IDENTITY_ORIGINALS[-1],
        'history':p.IDENTITY_ORIGINALS[0],'guest_success':p.IDENTITY_ORIGINALS[2],
        'guest_source':p.IDENTITY_ORIGINALS[2],'diagnostic':p.IDENTITY_ORIGINALS[2],
        'freeze':'pp1-freeze.json','core_run':'pp2-terminal.json','receipt_hash':'pp2-terminal.json',
        'coordinator':'pp2-terminal.json','custodian':'pp2-terminal.json','cpu':'pp2-terminal.json',
        'rss':'pp2-terminal.json','caller_exit':'pp2-caller-completion.json',
        'caller_stdout':'pp2-caller-completion.json','caller_stderr':'pp2-caller.stderr',
        'execute':'pp2-execute.stdout','preflight':'pp2-preflight.stdout',
        'index':p.IDENTITY_RECORDS[0],'absent':p.IDENTITY_RECORDS[0],'started':'pp2-caller-started.json'}[fault]
    key='old10d/'+name
    if fault=='caller_stderr':files[key]=b'unreported stderr\n'
    else:
        v=json.loads(files[key])
        if fault=='success':v['state']='VERIFIED'
        elif fault=='authority':v['A']=p.c.IDENTITY_RESOURCE_BASELINE['commit']
        elif fault=='history':v['manifest']['resume']['previous_reference']['field']='other'
        elif fault=='guest_success':v['status']='GUEST_QUIET'
        elif fault=='guest_source':v['source_binding_sha256']='f'*64
        elif fault=='diagnostic':v['diagnostic']['error_type']='different'
        elif fault=='freeze':v['pp2']['state']='CURRENT_READY'
        elif fault=='core_run':v['pp3']['H01']='PASS'
        elif fault=='receipt_hash':v['pp2']['coordinator_completion']['receipt_sha256']='f'*64
        elif fault=='coordinator':v['pp2']['coordinator_completion']['returncode']=0
        elif fault=='custodian':v['pp2']['coordinator_completion']['child']['returncode']=3
        elif fault=='cpu':v['pp2']['coordinator_completion']['usage']['cpu_nanoseconds']=120000000001
        elif fault=='rss':v['pp2']['coordinator_completion']['usage']['rss_peak_bytes']=536870913
        elif fault=='caller_exit':v['returncode']=0
        elif fault=='caller_stdout':v['stdout']['sha256']='f'*64
        elif fault=='execute':v['coordinator_completion']['returncode']=0
        elif fault=='preflight':v['manifest_sha256']='f'*64
        elif fault=='index':v['files'].pop(p.IDENTITY_ORIGINALS[-1])
        elif fault=='absent':v['absent'].pop()
        else:v['session']='lhqjgrow-20261011a'
        files[key]=DUMP(v)
    with pytest.raises((p.c.ContractError,KeyError)):p.build_identity_source(archive(files))


@pytest.mark.parametrize('fault',['size','prior','history','summary','bool','member'])
def test_independent_projection_rejects_changed_predecessor(fault):
    value=copy.deepcopy(source())
    if fault=='size':value['archive']['bytes']+=512
    elif fault=='prior':value['prior']['summary']['state']='SUCCESS'
    elif fault=='history':value['predecessor']['resume_sha256']='f'*64
    elif fault=='summary':value['summary']['remote_exit']='SUCCESS'
    elif fault=='bool':value['summary']['caller_returncode']=True
    else:value['predecessor']['member']='old10c/other'
    with pytest.raises(p.c.ContractError):p.validate_identity_source(value)
    if d:
        with pytest.raises(d.DispatchError):d.validate_identity_source(value)


def test_new_generation_preserves_all_sixteen_original_charges():
    costs=p.maintenance_commitments();rows=costs['generations']
    assert len(rows)==17 and len({r['session'] for r in rows})==17
    assert all((r['bytes'],r['inodes'],r['cpu_seconds'])==(1296*1048576,370,120) for r in rows[:-1])
    assert rows[-2]['session']=='lhqjgrow-20261010d'
    assert rows[-1]==dict(session='lhqjgrow-20261011a',bytes=2200*1048576,inodes=402,cpu_seconds=240)
    assert costs['protection_read']['source_preparation_included'] is True
    assert costs['protection_read']['aggregate_cpu_seconds']==120
    if d:assert costs==d._maintenance_commitments()
