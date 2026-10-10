"""Four retained failures, bounded digest handoff, and unchanged admission boundaries."""
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
@pytest.mark.parametrize('fault', ['missing','new_resume','order','authority','bool','extra','missing_third'])
def test_fourth_failure_keeps_original_three_generation_resume(monkeypatch,location,fault):
    files=previous_journal_files(monkeypatch,d)
    prefix='.'+p.FOURTH_JOURNAL_SESSION+'.'
    marker=json.loads(files[prefix+'consumed.json']);receipt=json.loads(files[prefix+'receipt.json'])
    target={'manifest':marker['manifest'],'marker':marker,'receipt':receipt,
            'inputs':marker['manifest']['inputs']}[location]
    if fault=='missing':del target['resume']
    elif fault=='new_resume':target['resume']=p.maintenance_resume()
    elif fault=='order':target['resume']['previous_maintenance'].reverse()
    elif fault=='authority':target['resume']['previous_maintenance'][2]['authority']['A']=h.NAMES_A
    elif fault=='bool':target['resume']['previous_maintenance'][2]['window_consumed']=1
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
        monkeypatch.setitem(p.FOURTH_JOURNAL_PINS,name,(len(raw),h.digest(raw)))
    with pytest.raises(p.c.ContractError,match='PREVIOUS_TEMPLATE_RESUME'):
        p.build_previous_maintenance(files)


@pytest.mark.parametrize('index',range(7))
@pytest.mark.parametrize('fault',['D','authority','pin','bytes','refund','exit','order'])
def test_rehashing_changed_full_history_never_admits_it(index,fault):
    resume=p.maintenance_resume();row=resume['previous_maintenance'][index]
    if fault=='D':row['D']='0'*40
    elif fault=='authority':row['authority']['C']=h.QI_C
    elif fault=='pin':row['originals'][0]['sha256']='0'*64
    elif fault=='bytes':row['originals'][0]['bytes']=False
    elif fault=='refund':row['window_consumed']=False
    elif fault=='exit':row['remote_exit']=0
    else:row['originals'].reverse()
    value=preflight();value['resume_sha256']=h.digest(h.canonical(resume))
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_PREFLIGHT_HISTORY'):
        h.parse_preflight(h.canonical(value))
    with pytest.raises(p.c.ContractError,match='JOURNAL_PREVIOUS_SUMMARY'):
        h.make_preflight(value['D'],value['manifest_sha256'],value['window_binding'],value['nonce'],
                         value['usage'],resume=resume)


@pytest.mark.parametrize('fault',['missing','extra','short','upper','nonhex','bool','without_lf',
                                 'old_three','different_scope','different_session'])
def test_digest_wire_shape_and_exact_full_history(fault):
    value=preflight();resume=p.maintenance_resume()
    if fault=='missing':del value['resume_sha256']
    elif fault=='extra':value['resume']=resume
    elif fault=='short':value['resume_sha256']=value['resume_sha256'][:-1]
    elif fault=='upper':value['resume_sha256']=value['resume_sha256'].upper()
    elif fault=='nonhex':value['resume_sha256']='g'*64
    elif fault=='bool':value['resume_sha256']=True
    elif fault=='without_lf':value['resume_sha256']=h.digest(h.canonical(resume)[:-1])
    elif fault=='old_three':value['resume_sha256']=h.digest(h.canonical(p.template_maintenance_resume()))
    else:
        resume['scope' if fault=='different_scope' else 'session']='other'
        value['resume_sha256']=h.digest(h.canonical(resume))
    with pytest.raises(h.prior.r.ObservationError):h.parse_preflight(h.canonical(value))


def test_real_fourth_pins_do_not_need_any_larger_short_record():
    value=preflight();resume=p.maintenance_resume()
    assert value['schema']=='lhq-journal-growth-preflight/v18'
    assert len(h.canonical(dict(value,A="a"*40,C="c"*40)))==711
    assert value['resume_sha256']==h.digest(h.canonical(resume))
    assert h.canonical(resume)==h.canonical(d._maintenance_resume())
    assert len(resume['previous_maintenance'])==11
    raw=h.canonical(value)
    at_limit=raw+b' '*(4096-len(raw))
    assert h.parse_preflight(at_limit)==value
    with pytest.raises(h.prior.r.ObservationError,match='JSON_SIZE'):h.parse_preflight(at_limit+b' ')
    # The previous inline-history representation fails for the same exact data.
    old=copy.deepcopy(value);old['schema']='lhq-journal-growth-preflight/v4'
    del old['resume_sha256'];old['resume']=resume
    assert len(h.canonical(old))>4096
    with pytest.raises(h.prior.r.ObservationError,match='JSON_SIZE'):h.parse_preflight(h.canonical(old))


@pytest.mark.parametrize('fault',['digest','scope','schema','manifest_format','nonce','window','usage','size'])
def test_bad_handoff_stops_before_any_field_read(monkeypatch,capsys,fault):
    value=preflight()
    if fault=='digest':value['resume_sha256']='0'*64
    elif fault=='scope':value['A']=h.TEMPLATE_A
    elif fault=='schema':value['schema']='lhq-journal-growth-preflight/v4'
    elif fault=='manifest_format':value['manifest_sha256']=''
    elif fault=='nonce':value['nonce']=False
    elif fault=='window':value['window_binding']['origins'][0]=True
    elif fault=='usage':value['usage']['cpu_nanoseconds']=0
    raw=h.canonical(value)+(b' '*4096 if fault=='size' else b'')
    monkeypatch.setattr(h.os,'geteuid',lambda:1000)
    monkeypatch.setattr(h,'growth_sources',lambda _:{})
    def unexpected(*args,**kwargs):pytest.fail('invalid handoff reached field observation')
    monkeypatch.setattr(h,'Window',unexpected)
    monkeypatch.setattr(h,'freeze_growth_inputs',unexpected)
    monkeypatch.setattr(h.sys,'argv',['growth','--frame','frame','--plan-archive','plan',
        '--archives-dir','archives','--expected-commit','d'*40,'--window-binding','{}',
        '--preflight',raw.decode(),'--expected-manifest','e'*64,'--trusted-single-admin','--execute'])
    monkeypatch.setattr(h.history.c,"VM_ADOPTION_CLOSURE",dict(commit="c"*40))
    assert h.main()==3
    returned=json.loads(capsys.readouterr().out)
    assert returned['marker_created'] is False and returned['ssh_requests']==0


@pytest.mark.parametrize('index',range(7))
@pytest.mark.parametrize('fault',['authority','pin','refund','drop'])
def test_full_projection_stays_mandatory_for_both_core_consumers(originals,index,fault):
    files,args=originals
    value=p.build_journal_transition(files,**args)
    rows=value['previous_maintenance']['previous_maintenance']
    if fault=='authority':rows[index]['authority']['A']=h.QI_A
    elif fault=='pin':rows[index]['originals'][0]['sha256']='0'*64
    elif fault=='refund':rows[index]['window_consumed']=False
    else:rows.pop(index)
    with pytest.raises(p.c.ContractError):
        p.validate_journal_transition(value,priors=args['priors'],implementation=args['implementation'])
    with pytest.raises(d.DispatchError):
        d._validate_journal_transition(value,priors=args['priors'],implementation=args['implementation'])


@pytest.mark.parametrize('record',list(p.c.NAMES_BASELINE['documents_sha256'])
                         +[p.c.NAMES_OWNER_DECISION['record_path']])
def test_names_authority_bytes_are_required_before_source_admission(source_git,record):
    source_git.changed_doc=record
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_NAMES_'):
        h.growth_sources(source_git.head)
    assert not any(call[0]=='show' and ':tests/' in call[1] for call in source_git.calls)


@pytest.mark.parametrize('edge',[(h.NAMES_A,h.NAMES_C),(h.NAMES_C,'d'*40)])
def test_names_candidate_descends_from_independent_closure(source_git,edge):
    source_git.rejected_edge=edge
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_SOURCE'):h.growth_sources(source_git.head)


@pytest.mark.parametrize('commit',[h.NAMES_A,h.NAMES_C])
def test_exact_authority_trees_are_checked_before_source_reads(source_git,commit):
    source_git.changed_tree=commit
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_NAMES_TREE'):h.growth_sources(source_git.head)


def test_closure_bookkeeping_is_not_an_execution_candidate(source_git):
    source_git.head=h.NAMES_C
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_NAMES_D'):h.growth_sources(source_git.head)
