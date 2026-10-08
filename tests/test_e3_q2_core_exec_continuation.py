"""Fifth retained failure and exact Exec continuation authority."""
import copy
import json
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux protected continuation', allow_module_level=True)

from core_prior_fixture import previous_journal_files
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_dispatcher as d
from e3_host import q2_journal_growth as h
from test_e3_q2_core_minimal_continuation import originals
from test_e3_q2_core_template_continuation import preflight
from test_e3_q2_journal_diagnostic_resume import source_git


@pytest.mark.parametrize('location', ['manifest', 'marker', 'receipt', 'inputs'])
@pytest.mark.parametrize('fault', ['missing','new_resume','order','authority','bool','extra','missing_fourth'])
def test_fifth_failure_keeps_original_four_generation_resume(monkeypatch,location,fault):
    files=previous_journal_files(monkeypatch,d)
    prefix='.'+p.FIFTH_JOURNAL_SESSION+'.'
    marker=json.loads(files[prefix+'consumed.json']);receipt=json.loads(files[prefix+'receipt.json'])
    target={'manifest':marker['manifest'],'marker':marker,'receipt':receipt,
            'inputs':marker['manifest']['inputs']}[location]
    if fault=='missing':del target['resume']
    elif fault=='new_resume':target['resume']=p.maintenance_resume()
    elif fault=='order':target['resume']['previous_maintenance'].reverse()
    elif fault=='authority':target['resume']['previous_maintenance'][3]['authority']['A']=h.EXEC_A
    elif fault=='bool':target['resume']['previous_maintenance'][3]['window_consumed']=1
    elif fault=='extra':target['resume']['retry']=True
    else:target['resume']['previous_maintenance'].pop()
    # Rebind only synthetic original pins so rejection must come from semantics.
    marker['pre_description']['source_binding_sha256']=h.digest(h.canonical(marker['manifest']['inputs']))
    marker['manifest_sha256']=receipt['manifest_sha256']=h.digest(h.canonical(marker['manifest']))
    events=[json.loads(raw) for raw in files[prefix+'events.jsonl'].splitlines()]
    events[1]['result']['manifest_sha256']=marker['manifest_sha256']
    events[3]['description_sha256']=h.digest(h.canonical(marker['pre_description']))
    for name,raw in {'consumed.json':h.canonical(marker),'receipt.json':h.canonical(receipt),
                     'events.jsonl':b''.join(h.canonical(row) for row in events)}.items():
        files[prefix+name]=raw
        monkeypatch.setitem(p.FIFTH_JOURNAL_PINS,name,(len(raw),h.digest(raw)))
    with pytest.raises(p.c.ContractError,match='PREVIOUS_NAMES_RESUME'):
        p.build_previous_maintenance(files)


@pytest.mark.parametrize('record',list(p.c.EXEC_BASELINE['documents_sha256'])
                         +[p.c.EXEC_OWNER_DECISION['record_path']])
def test_exec_authority_bytes_are_required_before_source_admission(source_git,record):
    source_git.changed_doc=record
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_EXEC_'):
        h.growth_sources(source_git.head)
    assert not any(call[0]=='show' and ':tests/' in call[1] for call in source_git.calls)


@pytest.mark.parametrize('edge',[(h.EXEC_A,h.EXEC_C),(h.EXEC_C,'d'*40)])
def test_exec_candidate_descends_from_independent_closure(source_git,edge):
    source_git.rejected_edge=edge
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_SOURCE'):h.growth_sources(source_git.head)


@pytest.mark.parametrize('commit',[h.EXEC_A,h.EXEC_C])
def test_exact_authority_trees_are_checked_before_source_reads(source_git,commit):
    source_git.changed_tree=commit
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_EXEC_TREE'):h.growth_sources(source_git.head)


def test_closure_bookkeeping_is_not_an_execution_candidate(source_git):
    source_git.head=h.EXEC_C
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_EXEC_D'):h.growth_sources(source_git.head)


def test_old_v5_short_handoff_cannot_open_exec_window():
    value=preflight();value['schema']='lhq-journal-growth-preflight/v5'
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_PREFLIGHT_SCHEMA'):
        h.parse_preflight(h.canonical(value))


def test_original_names_resume_digest_cannot_substitute_for_fifth_history():
    value=preflight();value['resume_sha256']=h.digest(h.canonical(p.names_maintenance_resume()))
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_PREFLIGHT_HISTORY'):
        h.parse_preflight(h.canonical(value))


def test_exec_candidate_binds_exact_scope_and_new_independent_closure(source_git):
    h.growth_sources(source_git.head)
    value=preflight()
    assert (value['A'],value['C'])==(h.QI_A,h.QI_C)
    assert p.maintenance_resume()['scope']==p.c.QI_SCOPE
    assert p.maintenance_resume()['session']==h.SESSION=='lhqjgrow-20261008e'
    assert len(p.previous_journal_profiles())==7
    assert len(p.previous_maintenance_pins())==35
    assert len(p.maintenance_commitments()['generations'])==8
    assert ['merge-base','--is-ancestor',h.EXEC_A,h.EXEC_C] in source_git.calls
    assert ['merge-base','--is-ancestor',h.EXEC_C,source_git.head] in source_git.calls
