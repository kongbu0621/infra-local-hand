"""Changed adoption, target, window and receipt bindings fail before execution."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(name, path=None):
    path = path or Path(__file__).parent / 'e3_host' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name + '_test', path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


m = module('q2_reconciliation_driver')
billing_test = module('bill_fixture', Path(__file__).with_name('test_e3_q2_reconciliation_billing.py'))


def fixture():
    args, _ = billing_test.fixture()
    quote = billing_test.m.quote_bill(**args)
    authority = dict(rule=m.contract.RULE, baseline=m.contract.BASELINE,
        closure=m.contract.CLOSURE, owner_decision=m.contract.OWNER_DECISION,
        operation_id='synthetic-amendment', startup_authority=dict(baseline='a' * 40, closure='b' * 40))
    execution = dict(attempt_id='syntheticonce', source=dict(tree='c' * 40))
    plan = dict(host=dict(boot_id='synthetic-boot'), candidate=dict(commit='d' * 40,
        tree='e' * 40, wheel_sha256='f' * 64))
    verified = SimpleNamespace(manifest=authority, digest='0' * 64, implementation_commit='1' * 40,
        execution=execution, plan=plan, original=dict(candidate=dict(destination='/old/install')),
        previous=dict(candidate=dict(destination='/second/install')), source_classes={'/old/pin':'HISTORICAL_PIN'},
        obligations=tuple(args['obligations']), adoption=dict(schema='synthetic-test-adoption', prospective_only=True))
    envelope = dict(attempt_id='syntheticonce', clock_anchor_sha256='2' * 64,
        issued_ns=1, preparation_deadline_ns=140, deadline_ns=270)
    live = dict(schema='local-hand-q2-installation-reconciliation-live/v1', attempt_id='syntheticonce',
        amendment_sha256=verified.digest, source_commit=verified.implementation_commit,
        boot_before=plan['host'], boot_after=plan['host'], source_classes=verified.source_classes,
        historical_atime_preservation_proven=False, predecessors=[], ledgers=[], historical_units=[], roots=[],
        q1=[], preserved_trees=[], parents={}, bill=quote, current_tree_coverage={},
        deadline_ns=270, preparation_deadline_ns=140, clock_anchor_sha256='2' * 64)
    backend = SimpleNamespace(reconciliation_sealed=False, execution_entered=False, quote=quote, verified=verified, retry=execution,
        delivery_envelope=envelope, reconciliation_directory='/new/reservation.reconciliation',
        histories=[verified.original, verified.previous], _billing=billing_test.m, live_document=lambda: live)
    return backend, live


def test_exact_new_documents_bind_all_sources_and_only_two_obligations():
    backend, live = fixture()
    documents = m.make_documents(backend, live)
    result = m.validate_documents(backend.verified, backend.delivery_envelope,
        backend.reconciliation_directory, documents)
    assert result['reconciliation-intent.json']['binding']['run_permission'] == 'existing_startup_once'
    assert result['live-attestation.json']['historical_atime_preservation_proven'] is False
    assert len(result['reconciliation-record.json']['targets']) == 2


@pytest.mark.parametrize('fault', ['adoption', 'cross_plan', 'old_scope', 'deadline', 'third_target',
    'free_actual', 'release_staging', 'positive_history', 'missing_obligation', 'extra_live'])
def test_independent_record_mutations_fail(fault):
    backend, live = fixture(); documents = m.make_documents(backend, live)
    parsed = {name:m.contract.document(raw) for name,raw in documents.items()}
    if fault == 'adoption': parsed['evidence-adoption.json']['prospective_only'] = False
    elif fault == 'cross_plan': parsed['reconciliation-intent.json']['binding']['attempt_id'] = 'anotheronce'
    elif fault == 'old_scope': parsed['reconciliation-intent.json']['binding']['baseline'] = m.contract.old.BASELINE
    elif fault == 'deadline': parsed['reconciliation-record.json']['binding']['deadline_ns'] += 300
    elif fault == 'third_target': parsed['reconciliation-record.json']['targets'].append(parsed['reconciliation-record.json']['targets'][0])
    elif fault == 'free_actual': parsed['reconciliation-record.json']['after']['actual']['bytes'] = 0
    elif fault == 'release_staging': parsed['reconciliation-record.json']['obligations'][1]['terminated_by_amendment'] = True
    elif fault == 'positive_history': parsed['live-attestation.json']['historical_atime_preservation_proven'] = True
    elif fault == 'missing_obligation': parsed['reconciliation-record.json']['obligations'].pop()
    else: parsed['live-attestation.json']['skip_quota'] = True
    documents = {name:m.encoded(value) for name,value in parsed.items()}
    with pytest.raises(ValueError):
        m.validate_documents(backend.verified, backend.delivery_envelope,
            backend.reconciliation_directory, documents)


def test_unsealed_or_collection_backend_never_reaches_assembly(monkeypatch):
    backend, _ = fixture(); backend.read_only_collection = True
    calls = []
    backend.effect_admission = lambda: calls.append('effect')
    result = m.execute(backend, backend.delivery_envelope, {}, execv=lambda *args: calls.append('exec'))
    assert result['status'] == 'BLOCKED_RETAINED' and result['window_consumed'] is True
    assert calls == []


def test_expired_or_changed_live_document_is_rejected_before_record():
    backend, live = fixture(); changed = copy.deepcopy(live); changed['deadline_ns'] += 1
    with pytest.raises(ValueError, match='LIVE_DOCUMENT_CHANGED'):
        m.make_documents(backend, changed)


def test_second_entry_is_blocked_even_if_the_first_failed_before_startup_reservation():
    backend, _ = fixture(); backend.read_only_collection = False
    calls = []
    def interrupted():
        calls.append('first-effect-check')
        raise ValueError('EARLY_BLOCKED')
    backend.effect_admission = interrupted
    first = m.execute(backend, backend.delivery_envelope, {})
    second = m.execute(backend, backend.delivery_envelope, {})
    assert first['reason'] == 'EARLY_BLOCKED'
    assert second['reason'] == 'RECONCILIATION_EXECUTION_ALREADY_ENTERED'
    assert calls == ['first-effect-check']
