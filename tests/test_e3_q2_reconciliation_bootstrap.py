"""Bounded input and write ordering; no SSH, guest, service or quota operation."""
import base64
import importlib.util
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name + '_test',
        Path(__file__).parent / 'e3_host' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


m = module('q2_reconciliation_bootstrap')


def test_no_arguments_or_unknown_configuration_never_produces_ready(capsys):
    result = m.bootstrap({'release_old':True}, {})
    assert result['ready'] is False and result['backend'] is None
    assert result['record']['reason'] == 'RECONCILIATION_BOOTSTRAP_FIELDS'
    assert result['record']['window_consumed'] is None
    assert 'READY' not in capsys.readouterr().out


@pytest.mark.parametrize('value,limit', [('a!',100),('AAAA',1),('A'*32,4),(b'AAAA',4)])
def test_base64_is_strict_and_bounded(value, limit):
    with pytest.raises(ValueError): m.unbase64(value,limit)


def test_input_bundle_cannot_silently_add_an_execution_option():
    config = dict(manifest_raw='e30=',manifest_sha256='0'*64,blobs={},implementation_commit='1'*40,
        host_window={},release_unconditionally=True)
    result = m.input_bundle(config)
    assert set(result) == {'manifest_raw','manifest_sha256','blobs','implementation_commit','host_window'}
    result['release_unconditionally']=True
    with pytest.raises(ValueError, match='FIELDS'): m.load_inputs(result)


def test_expired_guard_cannot_begin_stage_or_write_a_file(tmp_path):
    touched=[]
    def expired(): raise ValueError('RECONCILIATION_DEADLINE')
    backend=SimpleNamespace(effect_admission=expired)
    base=SimpleNamespace(protected_parent=lambda path:touched.append(path))
    with pytest.raises(ValueError,match='DEADLINE'):
        m.guarded_extract(base,{},'a'*64,root=str(tmp_path/'stage'),backend=backend,admission={},entry={})
    assert touched==[] and list(tmp_path.iterdir())==[]


def test_stage_metadata_requires_seal_before_any_filesystem_write(tmp_path):
    def unsealed(): raise ValueError('RECONCILIATION_SEAL_REQUIRED')
    backend=SimpleNamespace(effect_admission=unsealed)
    with pytest.raises(ValueError,match='SEAL_REQUIRED'):
        m.write_metadata(str(tmp_path),'retry.json',b'{}',backend)
    assert list(tmp_path.iterdir())==[]


def test_archive_and_new_state_do_not_get_unbounded_metadata_reserve():
    assert len(m.METADATA_LIMITS)==6
    assert m.METADATA_LIMITS['reconciliation-inputs.json']==16*1024**2
    assert m.METADATA_INODES==6
    # This is an installation/staging peak, independent of the five-file state
    # record's unchanged 1MiB/16 inode subbudget.
    assert m.METADATA_BYTES == sum(m.METADATA_LIMITS.values())


def pipeline(monkeypatch, failure=None):
    events=[]
    real_helper=m.helper
    contract=real_helper('q2_reconciliation_contract')
    # This is a synthetic guest protocol/ordering model. Its Linux clock and
    # guest path semantics must not depend on the operating system running CI.
    # No clock, filesystem or actual Windows execution support is established.
    now, boot = 100 * 10**9, 200 * 10**9
    boot_clock = object()
    def model_boottime(clock):
        assert clock is boot_clock
        return boot
    monkeypatch.setattr(m, 'time', SimpleNamespace(CLOCK_BOOTTIME=boot_clock,
        clock_gettime_ns=model_boottime))
    entry=dict(monotonic_ns=now,boottime_ns=boot)
    files={'/root/synthetic/tools/q2_fixture.py':'# synthetic\n'}
    hashes={name:contract.sha(raw.encode()) for name,raw in files.items()}
    verified=SimpleNamespace(digest='a'*64,implementation_commit='b'*40,
        host_window={'intent':{'window_consumed':True,'window':{'issued_ns':now,'deadline_ns':now+300*10**9}}},
        execution=dict(attempt_id='syntheticonce',source=dict(files=hashes,tree='c'*40)),
        plan=dict(candidate=dict(source='/root/synthetic/source'),
            directories=dict(reservation=dict(path='/new/reservation'))))
    envelope=dict(attempt_id='syntheticonce',issued_ns=boot,preparation_deadline_ns=boot+140*10**9,
        deadline_ns=boot+270*10**9,clock_anchor_sha256='d'*64)
    host_fields={name:'f'*64 for name in ('host_binding_sha256','host_marker_sha256','host_bill_sha256','joint_bill_sha256')}
    ack_seen=[]
    class Backend:
        def __init__(self,*args,**kwargs):
            self.retry=verified.execution; self.verified=verified
            self.reconciliation_sealed=False; self.seal={'schema':'synthetic-seal'}
            self.reconciliation_directory='/new/reservation.reconciliation'
        def preflight(self,**kwargs):
            events.append('full-live')
            if failure=='preflight':raise ValueError('UNPROVEN_QUOTA')
        def stage_admission(self,*args):events.append('full-bill');return {}
        def recheck_before_record(self):events.append('second-live');return {}
        def guard(self):
            if failure=='deadline' or failure=='ack_late' and ack_seen:
                raise ValueError('RECONCILIATION_DEADLINE')
        def host_bindings(self):return host_fields
        def accept_host_ack(self,*args):events.append('host-ack-accepted')
        def record_guard(self):self.guard()
        def accept_new_seal(self,*args):
            events.append('verify-new-seal');self.reconciliation_sealed=True
            if failure=='seal_recheck':raise ValueError('LIVE_CHANGED')
        def verify_preserved(self):events.append('post-staging-recheck')
        def close(self):events.append('close')
    config=dict(manifest_raw='e30=',manifest_sha256='a'*64,blobs={},implementation_commit='b'*40,
        stage='/root/synthetic',archive=base64.b64encode(b'archive').decode(),archive_sha256='e'*64,
        files=files,file_hashes=hashes,clock_anchor={'host_issued_ns':now,'host_deadline_ns':now+300*10**9},
        guest_pin={'boot_id':'test'},host_window={})
    fake={
        'q2_reconciliation_contract':contract,
        # Only this isolated protocol fixture replaces the known-unsatisfied
        # field-readiness gate. It does not establish actual host provenance.
        'q2_host_window_contract':SimpleNamespace(require_field_readiness=lambda value:None),
        'q2_reconciliation_delivery':SimpleNamespace(guest_envelope=lambda *a,**k:envelope,
            validate_envelope=lambda *a,**k:None,legacy=SimpleNamespace(preparation_window=lambda *a:(now,now+140*10**9))),
        'q2_prepare_delivery':SimpleNamespace(verify_guest=lambda pin:pin,
            archive_members=lambda *a,**k:dict(staging_bytes=4096,entries=1)),
        'q2_startup_retry_bootstrap':SimpleNamespace(check_archive_sources=lambda *a:None,
            check_stage_layout=lambda *a:None),
        'q2_reconciliation_backend':SimpleNamespace(ReconciliationBackend=Backend),
        'q2_reconciliation_driver':SimpleNamespace(make_documents=lambda *a:{'live-attestation.json':b'{}'}),
        'q2_reconciliation_records':SimpleNamespace(write_once=lambda *a:(events.append('persistent-record') or {})),
    }
    monkeypatch.setattr(m,'load_inputs',lambda value:verified)
    # Resolve actual contract modules before replacing guest lexical paths, so
    # native host paths remain in use while loading their source files.
    if failure=='field_readiness':
        fake['q2_host_window_contract']=real_helper('q2_host_window_contract')
    monkeypatch.setattr(m,'helper',lambda name:fake[name])
    monkeypatch.setattr(m,'Path',PurePosixPath)
    monkeypatch.setattr(m,'guarded_extract',lambda *a,**k:(events.append('persistent-stage') or {}))
    monkeypatch.setattr(m,'write_metadata',lambda root,name,*a:events.append('metadata:'+name))
    def on_live(event):
        events.append('live-signal');ack_seen.append(True)
        if failure=='ack_none':return b''
        ack=dict(schema=m.ACK_SCHEMA,status='HOST_JOINT_ACK',**{key:event[key] for key in m.ACK_BINDINGS})
        if failure=='ack_wrong':ack['host_marker_sha256']='0'*64
        return contract.encoded(ack)
    return m.bootstrap(config,entry,on_live=on_live),events


def test_complete_joint_live_and_after_quote_precede_every_persistent_write(monkeypatch,capsys):
    result,events=pipeline(monkeypatch)
    assert result['ready'] is True
    assert events[:8]==['full-live','full-bill','second-live','live-signal','second-live','host-ack-accepted','persistent-record','verify-new-seal']
    assert events.index('persistent-stage')>events.index('verify-new-seal')
    assert 'metadata:clock-anchor.json' in events
    text=capsys.readouterr().out
    assert text.index('LIVE_ATTESTED')<text.index('RECONCILIATION_BOOTSTRAP_READY')


@pytest.mark.parametrize('failure',['preflight','deadline','seal_recheck'])
def test_any_joint_or_seal_drift_blocks_following_mutations(monkeypatch,failure,capsys):
    result,events=pipeline(monkeypatch,failure)
    assert result['ready'] is False and result['record']['window_consumed'] is True
    assert 'persistent-stage' not in events
    if failure!='seal_recheck':
        assert 'persistent-record' not in events and 'live-signal' not in events
    assert 'RECONCILIATION_BOOTSTRAP_READY' not in capsys.readouterr().out


def ack_fixture():
    event = {name: ('a' * 40 if name in ('source_commit', 'source_tree') else 'b' * 64)
        for name in m.ACK_BINDINGS}
    event['attempt_id'] = 'synthetic-attempt'
    return event, dict(schema=m.ACK_SCHEMA, status='HOST_JOINT_ACK', **event)


def test_host_ack_is_exact_bounded_and_rejects_duplicate_keys():
    contract = m.helper('q2_reconciliation_contract')
    event, ack = ack_fixture()
    raw = contract.encoded(ack)
    assert m.validate_live_ack(raw, event) == ack
    for invalid in (raw.replace(b'{', b'{"status":"HOST_JOINT_ACK",', 1),
                    raw[:-2] + b',"extra":true}\n', b' ' * (m.ACK_LIMIT + 1), ack):
        with pytest.raises(ValueError):
            m.validate_live_ack(invalid, event)


@pytest.mark.parametrize('field', m.ACK_BINDINGS)
def test_host_ack_cannot_authorize_a_different_live_event(field):
    contract = m.helper('q2_reconciliation_contract')
    event, ack = ack_fixture()
    ack[field] = 'changed'
    with pytest.raises(ValueError, match='ACK_BINDING'):
        m.validate_live_ack(contract.encoded(ack), event)


@pytest.mark.parametrize('failure', ['ack_none', 'ack_wrong', 'ack_late'])
def test_missing_changed_or_late_host_ack_never_reaches_first_guest_write(monkeypatch, capsys, failure):
    result, events = pipeline(monkeypatch, failure)
    assert result['ready'] is False
    assert 'live-signal' in events
    assert 'host-ack-accepted' not in events
    assert 'persistent-record' not in events and 'persistent-stage' not in events
    text = capsys.readouterr().out
    assert text.count('"status":"LIVE_ATTESTED"') == 1
    assert 'RECONCILIATION_BOOTSTRAP_READY' not in text


def test_actual_field_readiness_gate_blocks_before_guest_observation_or_backend(monkeypatch, capsys):
    result, events = pipeline(monkeypatch, 'field_readiness')
    assert result['ready'] is False
    assert result['record']['reason'] == 'HOST_WINDOW_FIELD_READINESS_UNPROVEN'
    assert events == []
    assert 'LIVE_ATTESTED' not in capsys.readouterr().out
