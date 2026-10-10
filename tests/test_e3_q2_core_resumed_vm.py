"""Current VM proof, independent consumers and the fixed read-only RC2 protocol."""
import copy
import json
import pytest
import sys

if not sys.platform.startswith("linux"):
    pytest.skip("Linux current-VM proof and protected maintenance consumers",allow_module_level=True)

from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_dispatcher as d
from vm_resumption_fixture import records,index,archive,DUMP,PIN


def test_three_original_groups_build_current_projection_independently():
    files,idx,boot=records()
    raw=archive(files,idx);parsed=p.activation_archive_files(raw)
    assert parsed.pop('execution-return-index-private.json')==idx and parsed==files
    value=p.build_vm_resumption(files,idx,historical_boot=boot)
    assert p.validate_vm_activation(value)==d._validate_vm_activation(value)
    assert value['schema']=='local-hand-q2-vm-activation/v2'
    assert value['previous_host_preflight']['window_consumed'] is False
    assert value['execution_permission'] is False
    assert len(p.c.canonical(value))<=4096
    assert len(p.maintenance_commitments()['generations'])==15
    assert p.maintenance_commitments()==d._maintenance_commitments()


@pytest.mark.parametrize('fault',['absent','duplicate_json','nan','startup_failed','startup_identity',
    'old_marker_invented','old_consumer_replayed','guest_failed','boot_drift','package_drift',
    'loaded_module','mount_drift','stream_incomplete','host_drift','key_endpoint','source_drift',
    'bool_count','missing_top_exit','caller_mismatch','budget','old_v1'])
def test_rehashed_false_success_cannot_produce_current_proof(fault):
    files,_,boot=records()
    if fault=='absent':files.pop('old10b/tc2-preflight.stderr')
    elif fault in ('duplicate_json','nan'):
        files['guest/result.json']=b'{"a":1,"a":2}' if fault=='duplicate_json' else b'{"a":NaN}'
    elif fault.startswith('startup_'):
        name='startup/result-private.json';v=json.loads(files[name])
        if fault=='startup_failed':v['startup_calls']=0
        else:v['new_vm']['starttime']+=1
        files[name]=DUMP(v)
        ii=json.loads(files['startup/execution-return-index-private.json']);ii['files'][name.split('/',1)[1]]=PIN(files[name]);files['startup/execution-return-index-private.json']=DUMP(ii)
    elif fault in ('old_marker_invented','old_consumer_replayed'):
        name='old10b/tc2-failure-private.json';v=json.loads(files[name]);v['maintenance_window_consumed']=True;files[name]=DUMP(v)
    elif fault in ('boot_drift','package_drift','loaded_module','mount_drift','stream_incomplete'):
        name='guest/guest.stdout';v=json.loads(files[name])
        if fault=='boot_drift':v['boot_end']='77777777-2222-3333-4444-555555555555'
        elif fault=='package_drift':v['steps'][1]['stdout']='install ok installed\twrong-version'
        elif fault=='loaded_module':v['steps'][4]['argv']=['modprobe','quota_v2'];v['module_load_calls']=1
        elif fault=='mount_drift':v['steps'][5]['stdout']='{"filesystems":[]}'
        else:v['steps'][0]['eof']=False
        files[name]=DUMP(v)
        result=json.loads(files['guest/result.json']);result['guest_stdout']=PIN(files[name]);files['guest/result.json']=DUMP(result)
    elif fault=='key_endpoint':
        v=json.loads(files['guest/proposal.json']);v['ssh_prefix']=['ssh','other-host'];files['guest/proposal.json']=DUMP(v)
    elif fault=='old_v1':
        v=json.loads(files['guest/guest.stdout']);v['schema']='local-hand-q2-current-guest/v0';files['guest/guest.stdout']=DUMP(v)
    elif fault not in ('missing_top_exit','caller_mismatch'):
        v=json.loads(files['guest/result.json'])
        if fault=='guest_failed':v['guest_returncode']=255
        elif fault=='host_drift':v['host_after']['vm']['pid']+=1
        elif fault=='source_drift':v['guest_source_sha256']='b'*64
        elif fault=='bool_count':v['retries']=False
        elif fault=='budget':v['management_usage']['cpu_nanoseconds']=120000000001
        files['guest/result.json']=DUMP(v)
    if fault!='caller_mismatch':
        files['guest/caller.stdout']=DUMP(dict(event=p.RESUMPTION_EVENT,state='CURRENT_GUEST_VERIFIED',result_sha256=p.c.sha256(files['guest/result.json'])))
    else:files['guest/caller.stdout']=b'{}'
    idx=index(files)
    if fault=='missing_top_exit':
        i=json.loads(idx);i['guest_caller_completion']['returncode']=None;idx=DUMP(i)
    with pytest.raises(p.c.ContractError):p.build_vm_resumption(files,idx,historical_boot=boot)


@pytest.mark.parametrize('fault',['nonzero_tail','short_end','padding','extra','missing'])
def test_archive_rejects_hidden_or_incomplete_sources(fault):
    files,idx,_=records();raw=archive(files,idx)
    if fault=='nonzero_tail':raw+=b'x'*512
    elif fault=='short_end':raw=raw.rstrip(b'\0')
    elif fault=='padding':
        offset=512+len(files[sorted(files)[0]])
        raw=raw[:offset]+b'x'+raw[offset+1:]
    elif fault=='extra':files['guest/extra']=b'x';raw=archive(files,index(files))
    else:files.pop('old10b/tc2-preflight.stderr');raw=archive(files,index(files))
    with pytest.raises(p.c.ContractError):p.activation_archive_files(raw)


def test_current_consumers_reject_historical_activation():
    from core_prior_fixture import journal_transition
    value=journal_transition(dict(commit='d'*40,tree='e'*40))
    for verifier in (p.validate_journal_transition,d._validate_journal_transition):
        for activation in (None,dict(value['vm_activation'],schema='local-hand-q2-vm-activation/v1')):
            changed=copy.deepcopy(value);changed['vm_activation']=activation
            with pytest.raises((p.c.ContractError,d.DispatchError)):
                verifier(changed,priors=[],implementation=value['implementation'])


def test_fixed_guest_commands_and_actual_report_are_consumable():
    pytest.importorskip('resource')
    from e3_host import q2_current_guest_verification as guest
    files,_,_=records();proposal=json.loads(files['guest/proposal.json']);expected=json.loads(files['guest/guest.stdout'])
    desc=dict(nonce=expected['nonce'],package=proposal['package'],quota=proposal['quota'])
    seen=[]
    class Budget:
        def check(self):return expected['management_usage']
    def run(argv,budget):
        row=expected['steps'][len(seen)];seen.append(argv);assert argv==row['argv']
        return {k:row[k] for k in ('exit','stdout','stderr','eof')}
    value=guest.verify(desc,runner=run,boot_reader=lambda:expected['boot_id'],budget=Budget())
    assert value==expected
    assert p.validate_current_guest(value,**desc)==value
    assert len(seen)==6
    assert ['modprobe','--show-depends','quota_v2'] in seen
    assert all('--install' not in argv for argv in seen)


@pytest.mark.parametrize('case',['eof','nonzero','overflow'])
def test_current_guest_real_pipe_peer_under_original_process_limits(case):
    pytest.importorskip('resource')
    import subprocess,sys
    from pathlib import Path
    code='''import sys,os,resource
sys.path.insert(0,sys.argv[1])
from e3_host import q2_current_guest_verification as g
g.limits()
assert resource.getrlimit(resource.RLIMIT_AS)==(268435456,268435456)
assert resource.getrlimit(resource.RLIMIT_NOFILE)==(128,128)
mode=sys.argv[2]
source={'eof':"print('fixed output')",'nonzero':"raise SystemExit(7)",'overflow':"import sys;sys.stdout.write('x'*20000)"}[mode]
budget=g.Budget()
try:result=g.run([sys.executable,'-I','-B','-c',source],budget)
except ValueError as error:
    assert mode=='overflow' and str(error)=='GUEST_STREAM_BOUND'
else:
    assert mode!='overflow' and result['eof'] and result['stderr']==''
    assert result['exit']==(0 if mode=='eof' else 7)
    assert budget.last['cpu_nanoseconds']>0 and budget.last['rss_peak_bytes']>0
'''
    result=subprocess.run([sys.executable,'-I','-B','-c',code,str(Path(__file__).parent.resolve()),case],
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    assert result.returncode==0,result.stderr.decode()


@pytest.mark.parametrize('fault',['old_authority','old_failure_erased','invented_marker',
    'prep_budget','prep_source','missing_source','approval_drift','missing_provenance'])
def test_protected_source_rejects_rehashed_wrong_authority_or_preparation(fault):
    files,_,boot=records()
    authority=json.loads(files['guest/approval.json']);freeze=json.loads(files['guest/freeze.json'])
    if fault=='old_authority':authority['A']=p.c.RESUMED_VM_BASELINE['commit']
    elif fault=='old_failure_erased':authority['previous_guest_failure']['state']='PASS'
    elif fault=='invented_marker':authority['previous_guest_failure']['marker_created']=True
    elif fault=='prep_budget':authority['source_preparation']['allocated_bytes']=1048577
    elif fault=='prep_source':authority['source_preparation']['source_index_sha256']='b'*64
    elif fault=='missing_source':freeze['source_pins'].pop('q2_journal_growth.py')
    elif fault=='missing_provenance':authority.pop('source_preparation')
    elif fault=='approval_drift':freeze['previous_guest_failure']['index']['sha256']='b'*64
    if fault!='approval_drift':
        for key in ('previous_guest_failure','source_preparation'):
            if key in authority:freeze[key]=copy.deepcopy(authority[key])
    files['guest/approval.json']=DUMP(authority);freeze['approval']=PIN(files['guest/approval.json'])
    files['guest/freeze.json']=DUMP(freeze)
    marker=json.loads(files['guest/consumed.json']);marker['freeze_sha256']=p.c.sha256(files['guest/freeze.json'])
    files['guest/consumed.json']=DUMP(marker)
    returned=json.loads(files['guest/result.json']);returned['marker_sha256']=p.c.sha256(files['guest/consumed.json'])
    files['guest/result.json']=DUMP(returned)
    files['guest/caller.stdout']=DUMP(dict(event=p.RESUMPTION_EVENT,state='CURRENT_GUEST_VERIFIED',result_sha256=p.c.sha256(files['guest/result.json'])))
    with pytest.raises((p.c.ContractError,KeyError)):p.build_vm_resumption(files,index(files),historical_boot=boot)


def test_independent_projection_requires_protected_source_provenance():
    files,idx,boot=records();value=p.build_vm_resumption(files,idx,historical_boot=boot)
    for verifier in (p.validate_vm_activation,d._validate_vm_activation):
        bad=copy.deepcopy(value);bad.pop('protected_source_evidence_sha256')
        with pytest.raises((p.c.ContractError,d.DispatchError)):verifier(bad)
    costs=p.maintenance_commitments()
    assert costs==d._maintenance_commitments()
    assert costs['guest_verification']['sessions']==['lhqguest-20261010a','lhqguest-20261010b']
    assert costs['guest_verification']['host_bytes']+costs['source_preparation']['host_bytes']==3*1048576
    assert len(costs['generations'])==15
