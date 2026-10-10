"""No new field window: retained local failure, exact binding and independent consumers."""
import copy
import io
import json
import sys
import tarfile

import pytest
from e3_host import q2_core_prior_attempt as p
from local_preflight_fixture import records,archive,source_projection

if sys.platform.startswith('linux'):
    from e3_host import q2_core_delivery_dispatcher as d
else:
    d=None


def test_nine_originals_preserve_unconsumed_local_failure(monkeypatch):
    raw,spec,_=records(monkeypatch,*(() if d is None else (d,)))
    value=p.build_local_preflight_source(raw,spec)
    assert len(value['originals'])==9
    assert value['summary']['maintenance_window_consumed'] is False
    assert len(p.maintenance_resume()['previous_maintenance'])==11
    assert p.maintenance_resume()['previous_local_preflight']==value['summary']
    costs=p.maintenance_commitments()['generations']
    assert len(costs)==14 and sum(row['bytes'] for row in costs)==18144*1048576
    assert sum(row['inodes'] for row in costs)==5180 and sum(row['cpu_seconds'] for row in costs)==1680
    if d is not None:
        assert d.validate_local_preflight_source(value)==value
        assert d._maintenance_resume()==p.maintenance_resume()
        assert d._maintenance_commitments()==p.maintenance_commitments()


@pytest.mark.parametrize('fault',['missing','extra','duplicate','symlink','hardlink','oversize','truncated','wrong_hash','trailing','freeze','callers','D','authority','terminal','execute','ssh','core','diagnostic','return_pin','boolean_count'])
def test_archive_or_original_relation_faults_reject_even_resealed_archive(monkeypatch,fault):
    raw,spec,files=records(monkeypatch)
    if fault in ('D','authority','freeze','callers'):
        value=json.loads(files['freeze-complete.json'])
        if fault=='D':value['implementation']['commit']='f'*40
        elif fault=='authority':value['A']='f'*40
        elif fault=='callers':value['callers']['core_once.py']='f'*64
        else:value['state']='FD2_PREFLIGHT_FAILED_FD3_NOT_RUN'
        files['freeze-complete.json']=json.dumps(value).encode()
    elif fault in ('terminal','execute','ssh','core','diagnostic','boolean_count'):
        value=json.loads(files['execution-result.json'])
        key,new={'terminal':('state','VERIFIED'),'execute':('execute_invocations',1),
            'ssh':('ssh_requests',1),'core':('core_package','BUILT'),'diagnostic':('diagnostic',{'pid':42}),
            'boolean_count':('execute_invocations',False)}[fault]
        value[key]=new;files['execution-result.json']=json.dumps(value).encode()
        # Align the terminal gate so the test must reject the false semantic claim.
        gate=json.loads(files['release-gate.json']);gate['fd2']=value
        files['release-gate.json']=json.dumps(gate).encode()
    elif fault=='return_pin':files['fd2-summary.json']+=b' '
    elif fault=='missing':files.pop('fd2-summary.json')
    elif fault=='extra':files['unapproved.txt']=b'extra'
    raw=archive(files)
    if fault in ('duplicate','symlink','hardlink','oversize'):
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as target:
            for name,data in files.items():
                member=tarfile.TarInfo(name);member.size=len(data);target.addfile(member,io.BytesIO(data))
            member=tarfile.TarInfo('fd2-summary.json');member.linkname='fd2-caller.stdout'
            if fault=='symlink':member.type=tarfile.SYMTYPE
            elif fault=='hardlink':member.type=tarfile.LNKTYPE
            elif fault=='oversize':member.size=65537
            target.addfile(member,io.BytesIO(b'x'*member.size))
        raw=stream.getvalue()
    if fault=='truncated':raw=raw[:100]
    if fault=='trailing':raw+=b'x'*512
    spec.update(bytes=len(raw),sha256=p.c.sha256(raw))
    if fault=='wrong_hash':spec['sha256']='f'*64
    with pytest.raises((p.c.ContractError,KeyError)):
        p.build_local_preflight_source(raw,spec)


@pytest.mark.parametrize('fault',['source','missing','old_summary','consumed','pin','freeze','caller','archive_size','extra'])
def test_both_independent_portable_consumers_reject_local_source_faults(fault):
    value=source_projection()
    if fault=='source':value['summary']['D']='f'*40
    elif fault=='missing':value['originals'].pop('execution-result.json')
    elif fault=='old_summary':value['summary'].pop('terminal')
    elif fault=='consumed':value['summary']['maintenance_window_consumed']=True
    elif fault=='pin':value['originals']['fd2-summary.json']['sha256']='f'*64
    elif fault=='freeze':value['freeze_sha256']='f'*64
    elif fault=='caller':value['callers'].pop('core_once.py')
    elif fault=='archive_size':value['archive']['bytes']=131073
    else:value['unexpected']='self_report'
    with pytest.raises(p.c.ContractError):p.validate_local_preflight_source(value)
    if d is not None:
        with pytest.raises(d.DispatchError):d.validate_local_preflight_source(value)


def test_resume_cannot_drop_or_reclassify_old_local_failure():
    for change in ('missing','consume','session'):
        value=p.maintenance_resume()
        if change=='missing':value.pop('previous_local_preflight')
        elif change=='consume':value['previous_local_preflight']['maintenance_window_consumed']=True
        else:value['session']='lhqjgrow-20261009c'
        with pytest.raises(p.c.ContractError):p.validate_maintenance_resume(value)
        if d is not None:
            with pytest.raises(d.DispatchError):d._validate_maintenance_resume(value)


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='source-aware host verifier')
def test_complete_success_cannot_substitute_self_report_for_archive(originals):
    files,args=originals
    args['frozen']['local_preflight_raw']=b'not the frozen archive'
    with pytest.raises(p.c.ContractError,match='LOCAL_PREFLIGHT_ARCHIVE_PIN'):
        p.build_journal_transition(files,**args)


if sys.platform.startswith('linux'):
    from test_e3_q2_core_minimal_continuation import originals,effects


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='exact host authority source admission')
@pytest.mark.parametrize('fault',['A','B','tree','ancestry'])
def test_uc_authority_is_verified_before_field_effects(source_git,fault):
    from e3_host import q2_journal_growth as h
    if fault=='A':source_git.changed_doc=next(iter(h.history.c.USAGE_BASELINE['documents_sha256']))
    elif fault=='B':source_git.changed_doc=h.history.c.USAGE_OWNER_DECISION['record_path']
    elif fault=='tree':source_git.changed_tree=h.UC_C
    else:source_git.rejected_edge=(h.UC_C,source_git.head)
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_'):
        h.growth_sources(source_git.head)


if sys.platform.startswith('linux'):
    from test_e3_q2_journal_diagnostic_resume import source_git
