"""Synthetic retained C10/query relation; never reads a host or private file."""
import base64
import json

from e3_host import q2_core_delivery_contract as c
from e3_host import q2_core_prior_attempt as p

BOOT='11111111-2222-3333-4444-555555555555'
BASE='/fixture/q1-original'
PYTHON='/usr/bin/python3.12'
WORKER=BASE+'/source/tools/admin/local_hand_quota_observer/worker.py'
PARENT='/lhqfixture.slice'


def compact(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def identity():
    ticket=dict(schema='local-hand-quota-ticket/v1',slot_ref='q1.slot',generation='1'*32,
        request_id='2'*32,allocation_digest='3'*64,execution_id='4'*32,phase='preflight',
        issued_ns=100,deadline_ns=200)
    fields=['a'*64]+[ticket[k] for k in ('slot_ref','generation','request_id',
                                      'allocation_digest','execution_id','phase')]
    unit='lhq-'+c.sha256(compact(fields))+'.service'
    return unit,[PYTHON,'-I','-B',WORKER,BASE+'/config/runtime.json','b'*64,
                 base64.b64encode(compact(ticket)).decode()]


def inventory():
    from core_runtime_fixture import inventory as runtime_inventory
    from retained_root_fixture import roots
    paths=[r['path'] for r in roots()]
    return dict(expected_units=[dict(name=f'old{i}.service',control_group=None) for i in range(18)],
        **runtime_inventory(),
        protected_roots=sorted(['/fixture',BASE,*paths]),essential_paths=sorted(['/fixture/evidence',*paths]))


def source_raw(monkeypatch,previous):
    from e3_host import q2_journal_growth as h, q2_host_export as e
    unit,argv=identity()
    prefix='.'+p.SEVENTH_JOURNAL_SESSION+'.'
    raw=dict(old_marker=previous[prefix+'consumed.json'],old_stderr=previous[prefix+'pre.stderr'])
    marker=json.loads(raw['old_marker'])
    checks={
        'original_config':dict(status='Q1_CONFIG_BYTES_LINKED_ONLY',independent_authority_proven=False,
            q2_reusable_allocation=False,files={'runtime.json':'b'*64,'manifest.json':'a'*64},
            source_commit='c'*40,boot_id=BOOT),
        'revision_config':dict(status='Q1_CONFIG_BYTES_LINKED_ONLY',independent_authority_proven=False,
            q2_reusable_allocation=False,files={'runtime.json':'d'*64,'manifest.json':'e'*64}),
        'original_program_python':dict(path=PYTHON),'original_program_worker':dict(path=WORKER),
        'original_source_head':dict(declared_commit='c'*40,detached_head='c'*40,
            source_bytes_verified=False,clean_tree_verified=False),
        'original_current_boot':dict(boot_id=BOOT),'declared_guest':dict(boot_id=BOOT),
        'original_query_parent':dict(path='/sys/fs/cgroup'+PARENT,q2_parent_admitted=False)}
    report=dict(schema='local-hand-q2-host-export/v1',scope='READ_ONLY_SELECTED_Q1_HOST_HANDOFF',
        status='EXPORTED',source_config_status='Q1_EVIDENCE_ONLY',independent_supervision_required=True,
        q2_input_groups=dict.fromkeys(e.MISSING,'NOT_DELIVERED'),
        checks=[dict(check=k,status='OBSERVED',facts=v) for k,v in checks.items()])
    report.update(dict.fromkeys(('q1_history_reassessed','q2_accepted','q3_accepted',
        'production_supported','complete_q1_domain_inventory','quota_observed',
        'current_capacity_is_new_budget','fixture_generated'),False))
    raw['report']=c.canonical(report,newline=True)
    monkeypatch.setattr(h,'Q1_REPORT_PIN',(len(raw['report']),c.sha256(raw['report'])))
    prepared=dict(kind='CURRENT_OBSERVATION',task_commit='38ff001',manager='system',field_commands=1,
        retry=False,prior_D=p.SEVENTH_JOURNAL_D,unit=unit,description=marker['pre_description'],
        prior_manifest_sha256=marker['manifest_sha256'],source_originals={name:
            dict(bytes=len(raw[role]),sha256=c.sha256(raw[role])) for role,name in
            (('old_marker','consumed.json'),('old_stderr','pre.stderr'))})
    raw['prepared']=c.canonical(prepared,newline=True)
    started=dict(prepared_sha256=c.sha256(raw['prepared']))
    raw['started']=c.canonical(started,newline=True)
    props=dict(Id=unit,Names=unit,LoadState='loaded',ActiveState='failed',SubState='failed',
        MainPID='0',ControlPID='0',Restart='no',ExecStart='{ path='+PYTHON+' ; argv[]='+' '.join(argv)+' ; ignore_errors=no ; pid=0 }')
    raw['stdout']=''.join(k+'='+v+'\n' for k,v in props.items()).encode()
    raw['stderr']=b''
    capture=dict(kind='CURRENT_OBSERVATION',start=started,complete=True,error=None,
        exit_code=0,ssh_requests_attempted=1,eof=dict(stdout=True,stderr=True),elapsed_seconds=0.25,
        streams={k:dict(bytes=len(raw[k]),sha256=c.sha256(raw[k]),truncated=False) for k in ('stdout','stderr')})
    raw['capture']=compact(capture)
    return raw
