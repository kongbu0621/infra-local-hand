"""Sixth retained failure, exact GS authority and reduced coverage binding."""
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
def test_sixth_failure_keeps_original_five_generation_resume(monkeypatch,location,fault):
    files=previous_journal_files(monkeypatch,d)
    prefix='.'+p.SIXTH_JOURNAL_SESSION+'.'
    marker=json.loads(files[prefix+'consumed.json']);receipt=json.loads(files[prefix+'receipt.json'])
    target={'manifest':marker['manifest'],'marker':marker,'receipt':receipt,
            'inputs':marker['manifest']['inputs']}[location]
    if fault=='missing':del target['resume']
    elif fault=='new_resume':target['resume']=p.maintenance_resume()
    elif fault=='order':target['resume']['previous_maintenance'].reverse()
    elif fault=='authority':target['resume']['previous_maintenance'][4]['authority']['A']=h.QI_A
    elif fault=='bool':target['resume']['previous_maintenance'][4]['window_consumed']=1
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
        monkeypatch.setitem(p.SIXTH_JOURNAL_PINS,name,(len(raw),h.digest(raw)))
    with pytest.raises(p.c.ContractError,match='PREVIOUS_EXEC_RESUME'):
        p.build_previous_maintenance(files)


@pytest.mark.parametrize('record',list(p.c.QI_BASELINE['documents_sha256'])
                         +[p.c.QI_OWNER_DECISION['record_path']])
def test_exec_authority_bytes_are_required_before_source_admission(source_git,record):
    source_git.changed_doc=record
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_QI_'):
        h.growth_sources(source_git.head)
    assert not any(call[0]=='show' and ':tests/' in call[1] for call in source_git.calls)


@pytest.mark.parametrize('edge',[(h.QI_A,h.QI_C),(h.QI_C,'d'*40)])
def test_exec_candidate_descends_from_independent_closure(source_git,edge):
    source_git.rejected_edge=edge
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_SOURCE'):h.growth_sources(source_git.head)


@pytest.mark.parametrize('commit',[h.QI_A,h.QI_C])
def test_exact_authority_trees_are_checked_before_source_reads(source_git,commit):
    source_git.changed_tree=commit
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_QI_TREE'):h.growth_sources(source_git.head)


def test_closure_bookkeeping_is_not_an_execution_candidate(source_git):
    source_git.head=h.QI_C
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_QI_D'):h.growth_sources(source_git.head)


def test_old_v5_short_handoff_cannot_open_exec_window():
    value=preflight();value['schema']='lhq-journal-growth-preflight/v6'
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_PREFLIGHT_SCHEMA'):
        h.parse_preflight(h.canonical(value))


def test_original_names_resume_digest_cannot_substitute_for_fifth_history():
    value=preflight();value['resume_sha256']=h.digest(h.canonical(p.exec_maintenance_resume()))
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_PREFLIGHT_HISTORY'):
        h.parse_preflight(h.canonical(value))


def test_exec_candidate_binds_exact_scope_and_new_independent_closure(source_git):
    h.growth_sources(source_git.head)
    value=preflight()
    assert (value['A'],value['C'])==(h.RC_A,h.RC_C)
    assert p.maintenance_resume()['scope']==p.c.RESUMED_VM_SCOPE
    assert p.maintenance_resume()['session']==h.SESSION=='lhqjgrow-20261010c'
    assert len(p.previous_journal_profiles())==11
    assert len(p.previous_maintenance_pins())==55
    assert len(p.maintenance_commitments()['generations'])==15
    assert ['merge-base','--is-ancestor',h.DS_A,h.DS_C] in source_git.calls
    assert ['merge-base','--is-ancestor',h.DS_C,source_git.head] in source_git.calls

from e3_host import q2_journal_growth_guest as g
from test_e3_q2_journal_growth_guest_completion import description, pre_report, post_description, device

def post_report():
    pre=pre_report();value=copy.deepcopy(pre)
    value.update(phase='post',status='FILESYSTEM_GROWN',boot_id='22222222-2222-3333-4444-555555555555',
        original_boot_id=pre['boot_id'],pre_report_sha256=g.digest(g.canonical(pre)),
        journal_device=device(g.NEW_SIZE),resize_result=dict(returncode=0,both_eof=True,stdout_bytes=0,stderr_bytes=0,stdout_sha256=g.digest(b''),stderr_sha256=g.digest(b'')))
    from core_runtime_fixture import report as runtime_report
    value['runtime_preparation']=runtime_report(description(),value['boot_id'],'post')
    value['journal_device']['superblock']['filesystem_bytes']=g.NEW_SIZE
    return value


def changed_assurance(fault):
    value=g.guest_startup_assurance()
    if fault=='missing':value.pop('no_undeclared_business_startup')
    elif fault=='denied':value['no_undeclared_business_startup']=False
    elif fault=='integer':value['no_undeclared_business_startup']=1
    elif fault=='observed':value['indirect_startup_observation']='CLASSIFIED'
    elif fault=='proof':value['continuous_exclusion_proven']=True
    elif fault=='extra':value['verified']=True
    elif fault=='inventory_missing':value.pop('undeclared_unit_inventory_observation')
    elif fault=='inventory_claim':value['undeclared_unit_inventory_observation']='COMPLETE'
    elif fault=='none':value=None
    return value


@pytest.mark.parametrize('fault',['missing','denied','integer','observed','proof','extra','none','inventory_missing','inventory_claim'])
@pytest.mark.parametrize('boundary',['description','pre','post','host_projection','guest_projection'])
def test_reduced_coverage_requires_exact_confirmed_premise(originals,fault,boundary):
    bad=changed_assurance(fault)
    if boundary=='description':
        value=description();value['guest_startup_assurance']=bad
        call=lambda:g.descriptor(g.canonical(value))
    elif boundary in ('pre','post'):
        value=pre_report() if boundary=='pre' else post_report()
        value['guest_startup_assurance']=bad
        call=(lambda:g.validate_pre_report(value,description())) if boundary=='pre' else (lambda:g.validate_post_report(value,post_description()))
    else:
        files,args=originals
        value=p.build_journal_transition(files,**args);value['guest_startup_assurance']=bad
        fn=p.validate_journal_transition if boundary=='host_projection' else d._validate_journal_transition
        call=lambda:fn(value,priors=args['priors'],implementation=args['implementation'])
    with pytest.raises((g.r.ObservationError,p.c.ContractError,d.DispatchError),match='GUEST_STARTUP_PREMISE'):
        call()


@pytest.mark.parametrize('user',[False,True])
@pytest.mark.parametrize('fault',['missing_manager','extra_manager','missing_marker','old_marker','wrong_type'])
def test_pre_and_post_require_exact_manager_coverage(user,fault):
    for report,desc,validate in ((pre_report(),description(),g.validate_pre_report),
                                 (post_report(),post_description(),g.validate_post_report)):
        if user:
            desc['domain_units'].append(dict(name='user.slice',manager='user',control_group='/user.slice'))
            report['quiescence']['startup']['user_1100']=dict(copy.deepcopy(report['quiescence']['startup']['system']),domains=[dict(name='user.slice',properties_sha256='b'*64)])
            if 'pre_report' in desc:
                desc['pre_report']['quiescence']['startup']['user_1100']=copy.deepcopy(report['quiescence']['startup']['system'])
                desc['pre_report_sha256']=report['pre_report_sha256']=g.digest(g.canonical(desc['pre_report']))
        startup=report['quiescence']['startup']
        if fault=='missing_manager':startup.pop('system')
        elif fault=='extra_manager':startup['user_999']=copy.deepcopy(startup['system'])
        elif fault=='missing_marker':startup['system'].pop('indirect_startup')
        elif fault=='old_marker':startup['system']['indirect_startup']='CLASSIFIED'
        else:startup['system']['unit_count']=False
        with pytest.raises(g.r.ObservationError):validate(report,desc)


@pytest.mark.parametrize('which',['manifest','marker','receipt'])
def test_original_consumer_rejects_missing_assurance_even_with_consistent_digests(originals,which):
    files,args=originals;files=copy.deepcopy(files);prefix='.'+h.SESSION+'.'
    marker=json.loads(files[prefix+'consumed.json']);receipt=json.loads(files[prefix+'receipt.json'])
    target={'manifest':marker['manifest'],'marker':marker,'receipt':receipt}[which]
    target.pop('guest_startup_assurance')
    marker['manifest_sha256']=receipt['manifest_sha256']=h.digest(h.canonical(marker['manifest']))
    files[prefix+'consumed.json']=h.canonical(marker);files[prefix+'receipt.json']=h.canonical(receipt)
    with pytest.raises((g.r.ObservationError,p.c.ContractError),match='GUEST_STARTUP_PREMISE|RECEIPT_FIELDS|CORE_JOURNAL_MARKER|CORE_JOURNAL_MANIFEST'):
        p.build_journal_transition(files,**args)


def test_old_descriptor_and_report_cannot_supply_new_success():
    desc=description();desc['schema']='lhq-journal-growth-input/v1'
    with pytest.raises(g.r.ObservationError):g.descriptor(g.canonical(desc))
    report=pre_report();report['schema']='lhq-journal-growth-guest/v1'
    with pytest.raises(g.r.ObservationError):g.validate_pre_report(report,description())


def test_host_only_confirmation_cannot_enter_new_window(monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',['growth','--frame','frame','--plan-archive','archive',
        '--archives-dir','archives','--expected-commit','d'*40,'--trusted-single-admin'])
    monkeypatch.setattr(h,'growth_sources',lambda _: {})
    monkeypatch.setattr(h.os,'geteuid',lambda:1000)
    monkeypatch.setattr(h.resource,'getrlimit',lambda _: (h.resource.RLIM_INFINITY,h.resource.RLIM_INFINITY))
    monkeypatch.setattr(h.resource,'setrlimit',lambda *_: None)
    monkeypatch.setattr(h,'freeze_growth_inputs',lambda *a:pytest.fail('premise must precede input reads'))
    monkeypatch.setattr(h,'Window',lambda:pytest.fail('premise must precede window'))
    monkeypatch.setattr(h.history.c,"VM_ADOPTION_CLOSURE",dict(commit="c"*40))
    assert h.main()==3
    result=json.loads(capsys.readouterr().out)
    assert result['reason']=='GROWTH_GUEST_STARTUP_PREMISE'
    assert result['marker_created'] is False and result['ssh_requests']==0


def test_pre_and_post_accept_exact_declared_manager_set():
    desc=description();pre=pre_report();post=post_report()
    assert {row['manager'] for row in desc['domain_units']}=={'system','user'}
    post['pre_report_sha256']=g.digest(g.canonical(pre))
    post_desc=dict(desc,phase='post',pre_report=pre,pre_report_sha256=post['pre_report_sha256'])
    assert g.validate_pre_report(pre,desc)==pre
    assert g.validate_post_report(post,post_desc)==post


@pytest.fixture(autouse=True)
def runtime_pin(monkeypatch):
    from core_runtime_fixture import patch
    patch(monkeypatch)
