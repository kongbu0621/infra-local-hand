"""Third consumed prefix, its nested authority, and the single new boundary."""
import json
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux protected continuation', allow_module_level=True)

from core_prior_fixture import previous_journal_files
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_dispatcher as d
from e3_host import q2_journal_growth as h
from test_e3_q2_journal_diagnostic_resume import source_git


@pytest.mark.parametrize('location', ['manifest', 'marker', 'receipt', 'inputs'])
@pytest.mark.parametrize('fault', ['missing', 'new_resume', 'order', 'authority', 'bool', 'extra'])
def test_third_failure_retains_its_original_two_generation_resume(monkeypatch, location, fault):
    files=previous_journal_files(monkeypatch,d)
    prefix='.'+p.THIRD_JOURNAL_SESSION+'.'
    marker=json.loads(files[prefix+'consumed.json'])
    receipt=json.loads(files[prefix+'receipt.json'])
    target={'manifest':marker['manifest'], 'marker':marker,
            'receipt':receipt, 'inputs':marker['manifest']['inputs']}[location]
    if fault=='missing': del target['resume']
    elif fault=='new_resume': target['resume']=p.maintenance_resume()
    elif fault=='order': target['resume']['previous_maintenance'].reverse()
    elif fault=='authority': target['resume']['previous_maintenance'][1]['authority']['A']=h.TEMPLATE_A
    elif fault=='bool': target['resume']['previous_maintenance'][0]['window_consumed']=1
    else: target['resume']['retry']=True
    # Re-pin only synthetic bytes and their dependent hashes, isolating semantics.
    dump=h.canonical
    marker['pre_description']['source_binding_sha256']=h.digest(dump(marker['manifest']['inputs']))
    marker['manifest_sha256']=receipt['manifest_sha256']=h.digest(dump(marker['manifest']))
    events=[json.loads(line) for line in files[prefix+'events.jsonl'].splitlines()]
    events[1]['result']['manifest_sha256']=marker['manifest_sha256']
    events[3]['description_sha256']=h.digest(dump(marker['pre_description']))
    for name,raw in {'consumed.json':dump(marker), 'receipt.json':dump(receipt),
                     'events.jsonl':b''.join(dump(row) for row in events)}.items():
        files[prefix+name]=raw
        monkeypatch.setitem(p.THIRD_JOURNAL_PINS,name,(len(raw),h.digest(raw)))
    with pytest.raises(p.c.ContractError,match='PREVIOUS_SYSTEMCTL_RESUME'):
        p.build_previous_maintenance(files)


@pytest.mark.parametrize('record',list(p.c.TEMPLATE_BASELINE['documents_sha256'])
                         +[p.c.TEMPLATE_OWNER_DECISION['record_path']])
def test_template_authority_rejected_before_source_admission(source_git,record):
    source_git.changed_doc=record
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_TEMPLATE_'):
        h.growth_sources(source_git.head)
    assert not any(call[0]=='show' and ':tests/' in call[1] for call in source_git.calls)


@pytest.mark.parametrize('edge',[(h.TEMPLATE_A,h.TEMPLATE_C),(h.TEMPLATE_C,'d'*40)])
def test_template_implementation_requires_its_independent_closure(source_git,edge):
    source_git.rejected_edge=edge
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_SOURCE'):
        h.growth_sources(source_git.head)


def preflight():
    return h.make_preflight('d'*40,'e'*64,
        dict(boot_id='11111111-2222-3333-4444-555555555555',origins=[10**19,10**19]),
        'f'*64,dict(cpu_nanoseconds=120000000000,rss_peak_bytes=536870912),resume=p.maintenance_resume())


def test_four_history_digest_handoff_fits_with_maximum_usage_and_large_clocks():
    value=preflight()
    assert len(h.canonical(value))<=4096
    assert value['resume_sha256']==h.digest(h.canonical(d._maintenance_resume()))
    assert [row['session'] for row in p.maintenance_resume()['previous_maintenance']]==[
        'lhqjgrow-20261006a','lhqjgrow-20261007a','lhqjgrow-20261007b','lhqjgrow-20261008a','lhqjgrow-20261008b','lhqjgrow-20261008c']
    assert (value['R'],value['A'],value['C'])==(h.R,h.GS_A,h.GS_C)


@pytest.mark.parametrize('old_schema', ['v1','v2','v3','v4','v5','v6'])
def test_no_old_handoff_schema_can_open_new_window(old_schema):
    value=preflight();value['schema']='lhq-journal-growth-preflight/'+old_schema
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_PREFLIGHT_SCHEMA'):
        h.parse_preflight(h.canonical(value))


@pytest.mark.parametrize('fault',['old_scope','old_authority','refund','missing_third'])
def test_rebinding_old_window_does_not_create_new_permission(fault):
    value=preflight()
    resume=p.maintenance_resume()
    if fault=='old_scope': resume=p.systemctl_maintenance_resume()
    elif fault=='old_authority': value.update(A=h.SYSTEMCTL_A,C=h.SYSTEMCTL_C)
    elif fault=='refund': resume['previous_maintenance'][2]['window_consumed']=False
    else: resume['previous_maintenance'].pop()
    value['resume_sha256']=h.digest(h.canonical(resume))
    with pytest.raises((p.c.ContractError,h.prior.r.ObservationError)):
        h.parse_preflight(h.canonical(value))
