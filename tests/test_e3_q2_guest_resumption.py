"""Retained failed HR SSH cannot be hidden or used to admit the original core."""
import copy
import json
import sys

import pytest

from e3_host import q2_host_rebind as r, q2_core_prior_attempt as p
from guest_resumption_fixture import records, archive, projection, source, DUMP


def consumers(value, proof):
    assert p.validate_vm_activation(value) == value
    assert p.validate_host_rebind_source(proof) == proof
    if sys.platform.startswith('linux'):
        from e3_host import q2_core_delivery_dispatcher as d
        assert d._validate_vm_activation(value) == value
        assert d.validate_host_rebind_source(proof) == proof
        assert d._maintenance_commitments() == p.maintenance_commitments()


def test_new_success_consumes_retained_failure_and_old_start(monkeypatch):
    files,identity,failure = records(monkeypatch)
    before = {n:b for n,b in files.items() if n.startswith(('start/','failed-guest/'))}
    raw = archive(files)
    value,proof,base = r.consume_activation(raw,identity,failure)
    consumers(value,proof)
    assert value['schema'] == 'local-hand-q2-vm-activation/v4'
    assert value['execution_permission'] is False
    assert value['vm']['pid'] == json.loads(files['start/result.json'])['process']['pid']
    assert proof['previous_guest_failure']['ssh_child_returncode'] == 'UNKNOWN'
    assert proof['previous_guest_failure']['state'] == 'CONSUMED_FAILED_STOP_AND_RETAIN'
    assert proof['costs']['total_mib'] == 27503 and proof['costs']['maintenance_obligations'] == 19
    assert len(raw) <= 1048576
    assert {n:files[n] for n in before} == before


@pytest.mark.parametrize('name', ['hr1-freeze.json','continuation-owner.json',
    'failed-guest/index.json','failed-guest/terminal.json',
    *('failed-guest/'+n for n in r.GUEST_FILES), 'start/result.json'])
def test_missing_or_replaced_retained_original_never_admits(monkeypatch,name):
    files,identity,failure=records(monkeypatch)
    files[name] += b' '
    with pytest.raises((ValueError,KeyError)):
        r.consume_activation(archive(files),identity,failure)


@pytest.mark.parametrize('fault', ['old_nonce','extra_command','source_substitution','old_session',
    'missing_eof','caller_failed','host_drift','vm_drift','wrong_quota','report_absent'])
def test_new_guest_must_be_exact_and_complete(monkeypatch,fault):
    files,identity,failure=records(monkeypatch)
    request=json.loads(files['guest/request.json'])
    result=json.loads(files['guest/result.json'])
    if fault=='old_nonce':request['nonce']=json.loads(files['failed-guest/request.json'])['nonce']
    elif fault=='extra_command':request['remote_command']+='; true'
    elif fault=='source_substitution':request['remote_command']=request['remote_command'].replace('import resource','import socket',1)
    elif fault=='old_session':request['session']=r.GUEST_SESSION
    elif fault=='missing_eof':result['command']['eof']['stdout']=False
    elif fault=='caller_failed':
        row=json.loads(files['guest/caller-completion.json']);row['returncode']=3
        files['guest/caller-completion.json']=DUMP(row)
    elif fault=='host_drift':result['host_after']['boot_id']='99999999-2222-3333-4444-555555555555'
    elif fault=='vm_drift':result['vm_after']['starttime']+=1
    elif fault=='wrong_quota':request['quota']['uuid']='wrong'
    else:files['guest/guest.stdout']=b''
    files['guest/request.json']=DUMP(request);files['guest/result.json']=DUMP(result)
    frozen=json.loads(files['continuation-freeze.json'])
    frozen['requests']['guest']=r.pin(files['guest/request.json'])
    files['continuation-freeze.json']=DUMP(frozen)
    with pytest.raises((ValueError,KeyError,TypeError)):
        r.consume_activation(archive(files),identity,failure)


@pytest.mark.parametrize('fault',['old_version','owner','old_failure_omitted','old_failure_pass',
    'invent_exit','old_terminal','old_freeze','refund','duplicate_generation','old_costs'])
def test_independent_consumers_require_failed_history_and_full_costs(fault):
    value=projection();proof=source(value)
    if fault=='old_version':value['schema']='local-hand-q2-vm-activation/v3'
    elif fault=='owner':value['continuation_owner_sha256']='f'*64
    elif fault=='old_failure_omitted':proof.pop('previous_guest_failure')
    elif fault=='old_failure_pass':proof['previous_guest_failure']['state']='VERIFIED'
    elif fault=='invent_exit':proof['previous_guest_failure']['ssh_child_returncode']=255
    elif fault=='old_terminal':proof['previous_terminal_sha256']='f'*64
    elif fault=='old_freeze':proof['previous_freeze_sha256']='f'*64
    elif fault=='refund':proof['costs']['total_mib']-=6
    elif fault=='duplicate_generation':proof['costs']['maintenance_obligations']=20
    else:proof['costs']=r.costs()
    project=fault in ('old_version','owner')
    validators=[p.validate_vm_activation if project else p.validate_host_rebind_source]
    if sys.platform.startswith('linux'):
        from e3_host import q2_core_delivery_dispatcher as d
        validators.append(d._validate_vm_activation if project else d.validate_host_rebind_source)
    for validate in validators:
        with pytest.raises(Exception):validate(value if project else proof)
