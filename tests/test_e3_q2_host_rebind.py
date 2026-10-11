"""Approved HB2 adoption, strict v3/null semantics and actual completion evidence."""
import copy
import json
import sys

import pytest

from e3_host import q2_host_rebind as r, q2_core_prior_attempt as p
from host_rebind_fixture import records, archive, projection, source, DUMP, PIN


@pytest.fixture
def evidence(monkeypatch):
    return records(monkeypatch)


def test_full_originals_new_baseline_and_preserved_unknowns(evidence):
    files, identity, failure = evidence
    raw = archive(files)
    activation, proof, base = r.build_activation(raw,identity,failure)
    assert raw == r.envelope(files) and len(raw) <= 1048576
    assert p.validate_vm_activation(activation) == activation
    assert p.validate_host_rebind_source(proof) == proof
    assert activation['execution_permission'] is False
    assert activation['serial'] is None and activation['serial_backend'] == 'null'
    assert activation['historical_filesystem_continuity'] == 'UNKNOWN'
    assert base['historical']['schema'] == 'local-hand-q2-vm-activation/v2'
    assert activation['image_identities'] != base['historical']['image_identities']
    assert len(p.maintenance_commitments()['generations']) == 19
    if sys.platform.startswith('linux'):
        from e3_host import q2_core_delivery_dispatcher as d
        assert d._validate_vm_activation(activation) == activation
        assert d.validate_host_rebind_source(proof) == proof
        assert d._maintenance_commitments() == p.maintenance_commitments()


@pytest.mark.parametrize('fault',['owner','revision','hb_original','hb_request','rp_failure',
    'old_archive','missing_role','alias','device','inode','owner_uid','write_permission',
    'readonly_seed','readonly_original','host_reboot','namespace','tool','pre_listener',
    'pidfile','pid','starttime','argv','serial_file','serial_fifo','serial_claim',
    'double_start','bool_count','missing_eof','caller_exit','tool_exit','usage',
    'guest_boot','guest_uuid','guest_install','guest_eof','guest_exit','guest_source'])
def test_reindexed_originals_cannot_admit_broken_evidence(evidence,fault):
    files, identity, failure = evidence
    name = 'start/result.json'
    value = json.loads(files[name])
    if fault in ('owner','revision','hb_request'):
        name = {'owner':'owner.json','revision':'revision.json','hb_request':'hb/request.json'}[fault]
        files[name] += b' '
    elif fault == 'hb_original': files['hb/listener.stdout'] = b'LISTEN 0 128 127.0.0.1:22221 *:*\n'
    elif fault == 'rp_failure': files['source/old-return-rp2-caller.stdout'] = DUMP(dict(reason='PASS'))
    elif fault == 'old_archive': identity = identity[:-512]+b'x'*512
    elif fault == 'missing_role': del value['images_after']['quota']
    elif fault == 'alias': value['images_after']['quota'] = copy.deepcopy(value['images_after']['system'])
    elif fault in ('device','inode','owner_uid','write_permission'):
        key = dict(device='dev',inode='ino',owner_uid='uid',write_permission='mode')[fault]
        value['images_after']['quota']['metadata'][key] += 16
    elif fault in ('readonly_seed','readonly_original'):
        role = 'seed' if fault=='readonly_seed' else 'original_system'
        value['images_after'][role]['metadata']['mtime_ns'] += 1
    elif fault == 'host_reboot': value['host_after']['boot_id'] = '99999999-2222-3333-4444-555555555555'
    elif fault == 'namespace': value['process']['namespaces']['net'] = 'net:[999]'
    elif fault == 'tool': value['tools']['qemu']['ino'] += 1
    elif fault == 'pre_listener': files['start/pre-listener.stdout'] = b'LISTEN 0 128 127.0.0.1:22221 *:*\n'
    elif fault == 'pidfile': files['start/pidfile.raw'] = b'987\n'
    elif fault in ('pid','starttime'): value['process'][fault] += 1
    elif fault == 'argv': value['argv'][-1] += '-other'
    elif fault in ('serial_file','serial_fifo'): value['argv'][value['argv'].index('-serial')+1] = 'file:/extra' if fault=='serial_file' else 'pipe:/extra'
    elif fault == 'serial_claim': value['serial_capture'] = 'CAPTURED_EMPTY'
    elif fault == 'double_start': value['startup_calls'] = 2
    elif fault == 'bool_count': value['startup_calls'] = True
    elif fault == 'missing_eof': value['commands']['qemu']['eof']['stderr'] = False
    elif fault in ('caller_exit','tool_exit'):
        name = 'start/'+('caller-completion.json' if fault=='caller_exit' else 'tool-completion.json')
        value = json.loads(files[name]); value['returncode' if fault=='caller_exit' else 'exit_code'] = 3
    elif fault == 'usage': value['usage']['cpu_nanoseconds'] = 240000000001
    elif fault in ('guest_boot','guest_uuid'):
        name='guest/guest.stdout';value=json.loads(files[name])
        if fault=='guest_boot':value['boot_end']='99999999-2222-3333-4444-555555555555'
        else:
            row=json.loads(value['steps'][-1]['stdout']);row['filesystems'][0]['uuid']='wrong'
            value['steps'][-1]['stdout']=DUMP(row).decode()
    elif fault in ('guest_install','guest_eof','guest_exit'):
        name='guest/result.json';value=json.loads(files[name])
        if fault=='guest_install':value['package_install_calls']=1
        elif fault=='guest_eof':value['command']['eof']['stdout']=False
        else:value['command']['returncode']=3
    elif fault=='guest_source':
        name='guest/request.json';value=json.loads(files[name]);value['guest_source']['sha256']='f'*64
    if fault not in ('owner','revision','hb_original','hb_request','rp_failure','old_archive','pre_listener','pidfile'):
        files[name]=DUMP(value)
    with pytest.raises((ValueError,KeyError,TypeError)):
        r.build_activation(archive(files),identity,failure)


@pytest.mark.parametrize('fault',['version','missing_owner','known_history','content_verified',
    'release','file','fifo','capture','old_boot','alias','missing_image','cost_refund','cost_double',
    'old_obligations','missing_source'])
def test_both_consumers_reject_projection_or_budget_substitution(fault):
    value=projection(); proof=source(value)
    if fault=='version':value['schema']='local-hand-q2-vm-activation/v2'
    elif fault=='missing_owner':value.pop('owner_decision_sha256')
    elif fault=='known_history':value['historical_filesystem_continuity']='VERIFIED'
    elif fault=='content_verified':value['historical_content_continuity']='VERIFIED'
    elif fault=='release':value['execution_permission']=True
    elif fault in ('file','fifo'):value['serial']='file:/extra' if fault=='file' else 'pipe:/extra'
    elif fault=='capture':value['serial_capture']='CAPTURED_EMPTY'
    elif fault=='old_boot':value['current_boot_id']=value['historical_boot_id']
    elif fault=='alias':value['image_identities']['quota']=value['image_identities']['system']
    elif fault=='missing_image':del value['image_identities']['quota']
    elif fault=='cost_refund':proof['costs']['total_mib']-=1
    elif fault=='cost_double':proof['costs']['total_inodes']+=32
    elif fault=='old_obligations':proof['costs']['maintenance_obligations']=18
    else:proof['prior'].pop('prior')
    is_source=fault in ('cost_refund','cost_double','old_obligations','missing_source')
    with pytest.raises((ValueError,KeyError)):
        (p.validate_host_rebind_source if is_source else p.validate_vm_activation)(proof if is_source else value)
    if sys.platform.startswith('linux'):
        from e3_host import q2_core_delivery_dispatcher as d
        with pytest.raises((d.DispatchError,KeyError)):
            (d.validate_host_rebind_source if is_source else d._validate_vm_activation)(proof if is_source else value)


@pytest.mark.parametrize('fault',['padding','trailing','short','missing','reference','extra'])
def test_sidecar_bounds_canonical_encoding_and_exact_coverage(evidence,fault):
    files,_,_=evidence; raw=archive(files)
    if fault=='padding':raw=raw[:-512]+b'\1'+raw[-511:]
    elif fault=='trailing':raw+=b'\0'*512
    elif fault=='short':raw=raw[:-1]
    else:
        if fault=='missing':files.pop('owner.json')
        elif fault=='reference':
            files['source/rp2-terminal.json']=b'{}'
            with pytest.raises(ValueError):r.envelope(files)
            return
        else:files['extra']=b'{}'
        raw=archive(files)
    with pytest.raises(ValueError):r.read_envelope(raw)


@pytest.mark.parametrize('raw',[b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e400}',
    b'{"a":'+b'['*70+b'0'+b']'*70+b'}',b'x'*131073],
    ids=['duplicate-key','nan','infinite-float','too-deep','oversized'])
def test_record_decoder_is_bounded_and_unambiguous(raw):
    with pytest.raises(ValueError):r.document(raw)
