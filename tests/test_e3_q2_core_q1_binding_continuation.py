"""QI fixed-source admission and both continuation consumers; synthetic only."""
import base64
import copy
import json
import os
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux protected source admission',allow_module_level=True)

from core_prior_fixture import previous_journal_files
from q1_binding_fixture import source_raw, identity, compact, PARENT
from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_dispatcher as d
from test_e3_q2_core_minimal_continuation import originals


@pytest.fixture
def raw(monkeypatch):
    return source_raw(monkeypatch,previous_journal_files(monkeypatch,d))


def rebind(raw,monkeypatch):
    """Change synthetic carrier pins, forcing tests through semantic checks."""
    monkeypatch.setattr(h,'Q1_REPORT_PIN',(len(raw['report']),h.digest(raw['report'])))
    started=json.loads(raw['started']);started['prepared_sha256']=h.digest(raw['prepared'])
    raw['started']=h.canonical(started)
    capture=json.loads(raw['capture']);capture['start']=started
    capture['streams']={k:dict(bytes=len(raw[k]),sha256=h.digest(raw[k]),truncated=False)
                        for k in ('stdout','stderr')}
    raw['capture']=compact(capture)


def test_exact_one_service_and_parent_delta_preserves_all_other_rows(raw):
    original,proof=h.q1_declaration(raw)
    value=h.merge_q1_inventory(original,proof)
    assert [len(value[k]) for k in ('expected_units','domain_units','domain_cgroups')]==[19,7,7]
    service=proof['additions']['expected_units'][0]
    assert service['control_group']==PARENT+'/'+identity()[0]
    for key in ('protected_roots','essential_paths'):assert value[key]==original[key]
    for key,added in proof['additions'].items():
        assert [row for row in value[key] if row not in added]==sorted(original[key],
            key=(lambda row: row['name']) if key=='expected_units' else
                ((lambda row:(row['manager'],row['name'],row['control_group'])) if key=='domain_units' else None))
    assert all(proof[k] is False for k in ('independent_authority_proven','q2_reusable_allocation',
                                         'q2_parent_admitted','full_manifest_validated'))


@pytest.mark.parametrize('fault',['runtime','ambiguous_runtime','manifest','parent','source','boot',
    'program','duplicate_row','authority','query_id','noncanonical_ticket','ticket_identity',
    'ticket_bool_clock','ticket_phase','extra_command','old_source','wrong_request','two_queries',
    'incomplete','eof','exit_bool','truncated','stream_pin','started_pin'])
def test_rehashed_sources_cannot_change_identity_or_capture_relation(raw,monkeypatch,fault):
    report=json.loads(raw['report']);checks={row['check']:row['facts'] for row in report['checks']}
    if fault=='runtime':checks['original_config']['files']['runtime.json']='f'*64
    elif fault=='ambiguous_runtime':checks['revision_config']['files']['runtime.json']='b'*64
    elif fault=='manifest':checks['original_config']['files']['manifest.json']='f'*64
    elif fault=='parent':checks['original_query_parent']['path']='/sys/fs/cgroup/other.slice'
    elif fault=='source':checks['original_source_head']['detached_head']='f'*40
    elif fault=='boot':checks['declared_guest']['boot_id']='22222222-2222-3333-4444-555555555555'
    elif fault=='program':checks['original_program_worker']['path']='/other/worker.py'
    elif fault=='duplicate_row':report['checks'].append(copy.deepcopy(report['checks'][0]))
    elif fault=='authority':checks['original_config']['independent_authority_proven']=True
    elif fault=='query_id':raw['stdout']=raw['stdout'].replace(b'Id=lhq-',b'Id=other-',1)
    elif fault.startswith('ticket_') or fault=='noncanonical_ticket':
        token=identity()[1][-1];ticket=json.loads(base64.b64decode(token))
        if fault=='ticket_identity':ticket['request_id']='f'*32
        elif fault=='ticket_bool_clock':ticket['issued_ns']=True
        elif fault=='ticket_phase':ticket['phase']='shell'
        encoded=json.dumps(ticket,indent=1).encode() if fault=='noncanonical_ticket' else compact(ticket)
        raw['stdout']=raw['stdout'].replace(token.encode(),base64.b64encode(encoded))
    elif fault=='extra_command':raw['stdout']+=raw['stdout'].split(b'ExecStart=')[1].join([b'ExecStart=',b''])
    elif fault in ('old_source','wrong_request','two_queries'):
        prepared=json.loads(raw['prepared'])
        if fault=='old_source':prepared['source_originals']['pre.stderr']['sha256']='f'*64
        elif fault=='wrong_request':prepared['unit']='other.service'
        else:prepared['field_commands']=2
        raw['prepared']=h.canonical(prepared)
    raw['report']=h.canonical(report);rebind(raw,monkeypatch)
    if fault in ('incomplete','eof','exit_bool','truncated','stream_pin'):
        capture=json.loads(raw['capture'])
        if fault=='incomplete':capture['complete']=False
        elif fault=='eof':capture['eof']['stderr']=False
        elif fault=='exit_bool':capture['exit_code']=False
        elif fault=='truncated':capture['streams']['stdout']['truncated']=True
        else:capture['streams']['stdout']['sha256']='f'*64
        raw['capture']=compact(capture)
    elif fault=='started_pin':raw['started']=h.canonical(dict(prepared_sha256='f'*64))
    with pytest.raises((g.r.ObservationError,ValueError)):h.q1_declaration(raw)


@pytest.mark.parametrize('fault',['service_name','service_path','parent_name','parent_path','count'])
def test_conflicting_old_declarations_are_not_overwritten(raw,fault):
    old,proof=h.q1_declaration(raw);added=proof['additions']
    if fault=='service_name':old['expected_units'][0]['name']=added['expected_units'][0]['name']
    elif fault=='service_path':old['expected_units'][0]['control_group']=added['expected_units'][0]['control_group']
    elif fault=='parent_name':old['domain_units'][0]['name']=added['domain_units'][0]['name']
    elif fault=='parent_path':old['domain_cgroups'][0]=PARENT
    else:old['expected_units'].pop()
    with pytest.raises(g.r.ObservationError):h.merge_q1_inventory(old,proof)


@pytest.mark.parametrize('fault',['extra','missing','null_cgroup','roots','proof','boot','source_pin','source_bytes'])
def test_core_original_consumer_rejects_frozen_declaration_tampering(originals,fault):
    files,args=originals;args=copy.deepcopy(args);frozen=args['frozen']
    if fault=='extra':frozen['inventory']['expected_units'].append(dict(name='other.service',control_group=None))
    elif fault=='missing':frozen['inventory']['expected_units'].pop()
    elif fault=='null_cgroup':next(row for row in frozen['inventory']['expected_units'] if row['name']==identity()[0])['control_group']=None
    elif fault=='roots':frozen['inventory']['protected_roots'].pop()
    elif fault=='proof':frozen['source_binding']['q1_declaration']['q2_reusable_allocation']=True
    elif fault=='boot':frozen['boot_id']='22222222-2222-3333-4444-555555555555'
    elif fault=='source_pin':frozen['source_binding']['sources']['q1_stdout']['sha256']='f'*64
    else:frozen['q1_raw']['stdout']+=b'\nwrong'
    with pytest.raises((g.r.ObservationError,p.c.ContractError)):
        p.build_journal_transition(files,**args)


@pytest.mark.parametrize('role',h.Q1_ROLES)
def test_protected_reader_requires_the_frozen_original_pin(raw,role,tmp_path,monkeypatch):
    monkeypatch.setattr(h.local,"open_directory",lambda path,owner:os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW))
    spec={}
    for key,value in raw.items():
        path=tmp_path/key;path.write_bytes(value);path.chmod(0o600)
        spec[key]=dict(path=str(path),bytes=len(value),sha256=h.digest(value))
    spec[role]['sha256']='f'*64
    reader=h.prior.Inputs()
    try:
        with pytest.raises(g.r.ObservationError,match='INPUT_PIN'):h.read_q1_inputs(reader,spec)
    finally:reader.close()


@pytest.mark.parametrize('fault',['replace','edit','alias'])
def test_same_fd_bytes_and_path_must_survive_until_consumption(raw,tmp_path,fault,monkeypatch):
    monkeypatch.setattr(h.local,"open_directory",lambda path,owner:os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW))
    spec={}
    for key,value in raw.items():
        path=tmp_path/key;path.write_bytes(value);path.chmod(0o600)
        spec[key]=dict(path=str(path),bytes=len(value),sha256=h.digest(value))
    reader=h.prior.Inputs()
    try:
        if fault=='alias':
            spec['stderr']=copy.deepcopy(spec['stdout'])
            with pytest.raises(g.r.ObservationError,match='SOURCE_ALIAS'):h.read_q1_inputs(reader,spec)
            return
        assert h.read_q1_inputs(reader,spec)==raw
        target=tmp_path/'stdout'
        if fault=='replace':target.rename(tmp_path/'retained-original')
        target.write_bytes(raw['stdout'] if fault=='replace' else raw['stdout']+b'x')
        with pytest.raises(RuntimeError):
            h.recheck_q1_inputs(reader,dict(q1_raw=raw,q1_sources=spec))
    finally:reader.close()


@pytest.mark.parametrize('fault',['schema','assurance','resume','remote_exit','actions'])
def test_seventh_failure_cannot_change_coverage_or_be_promoted(monkeypatch,fault):
    files=previous_journal_files(monkeypatch,d);prefix='.'+p.SEVENTH_JOURNAL_SESSION+'.'
    failure=json.loads(files[prefix+'pre.stderr']);marker=json.loads(files[prefix+'consumed.json'])
    receipt=json.loads(files[prefix+'receipt.json'])
    if fault=='schema':failure['schema']='lhq-journal-growth-guest/v1'
    elif fault=='assurance':failure['guest_startup_assurance']['continuous_exclusion_proven']=True
    elif fault=='resume':marker['resume']['previous_maintenance'].pop()
    elif fault=='remote_exit':receipt['remote_exit']='PASSED'
    else:failure['actions_started']=['POWER_OFF']
    files[prefix+'pre.stderr']=h.canonical(failure)
    receipt['transports'][0]['files']['stderr']=dict(bytes=len(files[prefix+'pre.stderr']),sha256=h.digest(files[prefix+'pre.stderr']))
    files[prefix+'consumed.json']=h.canonical(marker);files[prefix+'receipt.json']=h.canonical(receipt)
    for name in p.SEVENTH_JOURNAL_PINS:
        value=files[prefix+name];monkeypatch.setitem(p.SEVENTH_JOURNAL_PINS,name,(len(value),h.digest(value)))
    with pytest.raises((p.c.ContractError,g.r.ObservationError)):p.build_previous_maintenance(files)


@pytest.mark.parametrize('fault',[None,'active','edge','cgroup'])
def test_added_service_still_uses_original_quiet_and_cgroup_checks(raw,monkeypatch,fault):
    _,proof=h.q1_declaration(raw);expected=proof['additions']['expected_units'][0]
    inv=object.__new__(g.GuestInventory)
    props={key:'' for key in g.GuestInventory.SHOW}
    props.update(Id=expected['name'],LoadState='loaded',ActiveState='failed',SubState='failed',
        MainPID='0',ControlPID='0',Restart='no',Transient='yes',UnitFileState='transient')
    if fault=='active':props.update(ActiveState='active',SubState='running',MainPID='17')
    elif fault=='edge':props['TriggeredBy']='unapproved.timer'
    elif fault=='cgroup':props['ControlGroup']='/other.slice'
    seen=[];inv.show=lambda _:props
    inv.cgroup=lambda path:(seen.append(path) or dict(path=path,state='ABSENT'))
    if fault is None:
        assert inv.quiet_service(expected)['cgroup']['state']=='ABSENT'
        assert seen==[expected['control_group']]
    else:
        with pytest.raises(g.r.ObservationError):inv.quiet_service(expected)
