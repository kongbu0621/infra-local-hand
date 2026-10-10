"""DS coverage, fixed old-QI history and original core handoff; no field calls."""
import copy
import json
import sys
import pytest
if not sys.platform.startswith('linux'):
    pytest.skip('Linux maintenance source and original consumer',allow_module_level=True)
from e3_host import q2_journal_growth as h, q2_journal_growth_guest as g
from e3_host import q2_core_prior_attempt as p, q2_core_delivery_dispatcher as d
from core_prior_fixture import previous_journal_files
from test_e3_q2_core_minimal_continuation import originals
from test_e3_q2_journal_diagnostic_resume import source_git
from test_e3_q2_journal_growth_guest_completion import description, pre_report

@pytest.mark.parametrize('record',list(p.c.DS_BASELINE['documents_sha256'])+[p.c.DS_OWNER_DECISION['record_path']])
def test_exact_ds_authority_is_required_before_sources(source_git,record):
    source_git.changed_doc=record
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_DS_'):h.growth_sources(source_git.head)
    assert not any(call[0]=='show' and ':tests/' in call[1] for call in source_git.calls)

@pytest.mark.parametrize('edge',[(h.DS_A,h.DS_C),(h.DS_C,'d'*40)])
def test_ds_implementation_must_descend_from_separate_closure(source_git,edge):
    source_git.rejected_edge=edge
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_SOURCE'):h.growth_sources(source_git.head)

@pytest.mark.parametrize('commit',[h.DS_A,h.DS_C])
def test_ds_trees_are_exact(source_git,commit):
    source_git.changed_tree=commit
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_DS_TREE'):h.growth_sources(source_git.head)

def test_ds_closure_cannot_execute(source_git):
    source_git.head=h.DS_C
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_DS_D'):h.growth_sources(source_git.head)

@pytest.mark.parametrize('phase',['pre','post'])
@pytest.mark.parametrize('fault',['missing','extra','duplicate','order','foreign_name','name_type','bad_sha','row_extra','scope','unknown_claim','old_fields'])
def test_report_cannot_claim_unread_or_misbound_domains(phase,fault):
    desc=description();desc['domain_units'].append(dict(name='z.slice',manager='system',control_group='/z.slice'))
    pre=pre_report();startup=pre['quiescence']['startup'];row=startup['system']
    row['domains'].append(dict(name='z.slice',properties_sha256='b'*64))
    if phase=='pre':report=pre;validate=lambda:g.validate_pre_report(report,desc)
    else:
        from test_e3_q2_core_guest_startup_continuation import post_report
        report=post_report();report['quiescence']=copy.deepcopy(pre['quiescence'])
        report['pre_report_sha256']=g.digest(g.canonical(pre))
        desc=dict(desc,phase='post',pre_report=pre,pre_report_sha256=report['pre_report_sha256'])
        validate=lambda:g.validate_post_report(report,desc)
    row=report['quiescence']['startup']['system'];domains=row['domains']
    if fault=='missing':domains.pop()
    elif fault=='extra':domains.append(dict(name='other.slice',properties_sha256='c'*64))
    elif fault=='duplicate':domains[1]=copy.deepcopy(domains[0])
    elif fault=='order':domains.reverse()
    elif fault=='foreign_name':domains[0]['name']='other.slice'
    elif fault=='name_type':domains[0]['name']=False
    elif fault=='bad_sha':domains[0]['properties_sha256']='g'*64
    elif fault=='row_extra':domains[0]['observed_all']=True
    elif fault=='scope':row['scope']='ALL'
    elif fault=='unknown_claim':row['undeclared_unit_inventory']='VERIFIED'
    else:row.update(unit_count=0,related=[])
    with pytest.raises(g.r.ObservationError,match='GROWTH_STARTUP_'):validate()

@pytest.mark.parametrize('location',['manifest','marker','receipt','inputs'])
@pytest.mark.parametrize('fault',['current_assurance','current_resume','dropped_history','changed_authority'])
def test_old08e_keeps_old_four_field_coverage_and_seven_history(monkeypatch,location,fault):
    files=previous_journal_files(monkeypatch,d);prefix='.'+p.EIGHTH_JOURNAL_SESSION+'.'
    marker=json.loads(files[prefix+'consumed.json']);receipt=json.loads(files[prefix+'receipt.json'])
    target={'manifest':marker['manifest'],'marker':marker,'receipt':receipt,'inputs':marker['manifest']['inputs']}[location]
    if fault=='current_assurance':target['guest_startup_assurance']=g.guest_startup_assurance()
    elif fault=='current_resume':target['resume']=p.maintenance_resume()
    elif fault=='dropped_history':target['resume']['previous_maintenance'].pop()
    else:target['resume']['previous_maintenance'][6]['authority']['A']=h.DS_A
    marker['pre_description']['source_binding_sha256']=h.digest(h.canonical(marker['manifest']['inputs']))
    marker['manifest_sha256']=receipt['manifest_sha256']=h.digest(h.canonical(marker['manifest']))
    events=[json.loads(line) for line in files[prefix+'events.jsonl'].splitlines()]
    events[1]['result']['manifest_sha256']=marker['manifest_sha256']
    events[3]['description_sha256']=h.digest(h.canonical(marker['pre_description']))
    for name,raw in {'consumed.json':h.canonical(marker),'receipt.json':h.canonical(receipt),'events.jsonl':b''.join(h.canonical(row) for row in events)}.items():
        files[prefix+name]=raw;monkeypatch.setitem(p.EIGHTH_JOURNAL_PINS,name,(len(raw),h.digest(raw)))
    with pytest.raises(p.c.ContractError,match='PREVIOUS_GS_'):p.build_previous_maintenance(files)

def test_new_success_uses_nine_consumed_histories_and_original_caps(originals):
    files,args=originals;value=p.build_journal_transition(files,**args)
    assert d._validate_journal_transition(value,priors=args['priors'],implementation=args['implementation'])==value
    assert value['authority']==dict(R=h.R,A=h.RC_A,C=h.RC_C)
    assert value['session']=='lhqjgrow-20261010c'
    assert len(value['previous_maintenance']['previous_maintenance'])==11
    rows=p.maintenance_commitments()['generations']
    assert len(rows)==15 and sum(row['bytes'] for row in rows)==19440*1048576
    assert sum(row['inodes'] for row in rows)==5550
    assert sum(row['cpu_seconds'] for row in rows)==1800
    assert h.HOST_BYTES==19441*1048576 and h.HOST_INODES==5582


@pytest.fixture(autouse=True)
def runtime_pin(monkeypatch):
    from core_runtime_fixture import patch
    patch(monkeypatch)
