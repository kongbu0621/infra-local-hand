"""Original invocation/native facts; modeled evidence is not a field acceptance."""
import copy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Frozen quota report decoder is Linux-only', allow_module_level=True)

from admin.local_hand_quota_observer import q2_runtime
from test_e3_quota_q2_runtime import config, ConfigAndRuntimeTests

SPEC = importlib.util.spec_from_file_location('_core_usage_test',
    Path(__file__).parent / 'e3_host/q2_core_delivery_dispatcher.py')
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def query_fixture():
    cfg = config()
    bundle, identity = ConfigAndRuntimeTests().bundle(cfg)
    terminal = dict(Id=identity['unit'], InvocationID=identity['invocation_id'],
        ControlGroup=identity['cgroup'], LoadState='loaded', Result='success',
        ExecMainCode='1', ExecMainStatus='0')
    capture = dict(stdout=d.canonical(bundle).decode(), stderr='', eof=['stderr', 'stdout'],
        error=None, returncode=0)
    proof = dict(query=identity, terminal=terminal, stopped=True, captures=[capture])
    return cfg, proof


def management_fixture(closed=True):
    cfg = config(); data = cfg.active().as_dict(); boot = data['request']['boot_id']
    controller = dict(unit='lhqcore-test-target.service', invocation_id='f' * 32,
        boot_id=boot, cgroup='/lhqcore.slice/lhqcore-test-target.service')
    observed = dict(controller, observed_ns=data['management']['issued_ns'] + 1)
    values = [('INTENT', dict(config_digest=cfg.digest, controller=observed,
        deadline_ns=data['request']['deadline_ns']))]
    identities = {}
    for index, role in enumerate(('listener', 'admission')):
        unit = ('lhqoc-' if role == 'listener' else 'lhqoa-') + cfg.active().request.digest + '.service'
        values.append(('DELIVERY', dict(role=role, unit=unit, command_digest='e' * 64)))
        values.append(('INVOCATION', dict(role=role, unit=unit, invocation_id=str(index + 2) * 32)))
        identities[role] = dict(boot_id=boot, unit=unit, invocation_id=str(index + 2) * 32,
            cgroup=data['management_parent']['path'] + '/' + unit)
    if closed:
        values.append(('CLOSED', dict(schema='local-hand-quota-management-closed/v1',
            config_digest=cfg.digest, request_digest=cfg.active().request.digest,
            controller=observed, stages={stage: {'identity': identities[role]}
                for stage, role in (('collector', 'listener'), ('admission', 'admission'))})))
    return cfg, controller, values


def encode_record(values):
    previous = '0' * 64; rows = []
    for kind, value in values:
        raw = d.canonical(dict(kind=kind, value=value, previous_digest=previous), newline=True)
        rows.append(raw); previous = d._sha(raw)
    return b''.join(rows)


def test_native_children_are_real_complete_reports_not_sixteen_budget():
    cfg, proof = query_fixture()
    identity, count = d._usage_query_record(cfg, d.canonical(proof), q2_runtime)
    assert identity == proof['query']
    assert count == 3 and count != d.LIMITS['native_children']


@pytest.mark.parametrize('fault', ['missing_report', 'duplicate_report', 'query', 'config',
    'bad_native', 'nonzero', 'missing_eof', 'stderr', 'not_stopped', 'terminal'])
def test_native_unknown_or_misbound_report_cannot_supply_successful_count(fault):
    cfg, proof = query_fixture(); capture = proof['captures'][-1]
    bundle = d.document(capture['stdout'].encode(), limit=d.MEMBER_LIMIT, newline=False)
    if fault == 'missing_report': bundle['reports'].pop()
    elif fault == 'duplicate_report': bundle['reports'][1] = copy.deepcopy(bundle['reports'][0])
    elif fault == 'query': bundle['query']['invocation_id'] = 'b' * 32
    elif fault == 'config': bundle['config_digest'] = 'b' * 64
    elif fault == 'bad_native': bundle['reports'][0]['stdout'] = '{}\n'
    elif fault == 'nonzero': capture['returncode'] = 2
    elif fault == 'missing_eof': capture['eof'] = ['stdout']
    elif fault == 'stderr': capture['stderr'] = 'uncertain'
    elif fault == 'not_stopped': proof['stopped'] = False
    else: proof['terminal']['InvocationID'] = 'b' * 32
    capture['stdout'] = d.canonical(bundle).decode()
    with pytest.raises((d.DispatchError, ValueError)):
        d._usage_query_record(cfg, d.canonical(proof), q2_runtime)


def test_original_invocations_not_intents_prove_two_management_starts():
    cfg, controller, values = management_fixture()
    result = d._usage_management_record(cfg, encode_record(values), controller, allow_unclosed=False)
    assert set(result) == {'listener', 'admission'}
    assert len({item['invocation_id'] for item in result.values()}) == 2


def test_h11_started_invocations_do_not_require_fabricated_phase_closure():
    cfg, controller, values = management_fixture(closed=False)
    assert len(d._usage_management_record(cfg, encode_record(values), controller, allow_unclosed=True)) == 2
    with pytest.raises(d.DispatchError, match='INCOMPLETE'):
        d._usage_management_record(cfg, encode_record(values), controller, allow_unclosed=False)


@pytest.mark.parametrize('fault', ['no_invocation', 'duplicate', 'wrong_unit', 'wrong_controller',
    'config', 'closed_identity', 'zero_invocation', 'chain', 'truncated'])
def test_management_missing_or_conflicting_fact_is_incomplete(fault):
    cfg, controller, values = management_fixture()
    if fault == 'no_invocation': values.pop(2)
    elif fault == 'duplicate': values[4] = copy.deepcopy(values[2])
    elif fault == 'wrong_unit': values[2][1]['unit'] = 'other.service'
    elif fault == 'wrong_controller': values[0][1]['controller']['invocation_id'] = 'a' * 32
    elif fault == 'config': values[0][1]['config_digest'] = 'a' * 64
    elif fault == 'closed_identity': values[-1][1]['stages']['collector']['identity']['invocation_id'] = 'a' * 32
    elif fault == 'zero_invocation': values[2][1]['invocation_id'] = '0' * 32
    raw = encode_record(values)
    if fault == 'chain': raw = raw.replace(b'"previous_digest":"', b'"previous_digest":"f', 1)
    elif fault == 'truncated': raw = raw[:-1]
    with pytest.raises((d.DispatchError, ValueError)):
        d._usage_management_record(cfg, raw, controller, allow_unclosed=False)


def count_rows(case_index, jobs, phases):
    rows = []; base = case_index * 100
    def unit(kind, n):
        return dict(kind=kind, boot_id='boot', unit=f'{kind}-{base + n}.service',
            invocation_id=f'{base + n:032x}', cgroup=f'/parent/{kind}-{base + n}.service')
    rows.extend(unit('job', n) for n in range(jobs))
    rows.extend(unit('controller', 20 + n) for n in range(2))
    for phase in range(phases):
        query = unit('query', 30 + phase)
        rows.append(query)
        rows.extend(unit('dynamic', 40 + phase * 2 + n) for n in range(2))
        rows.append(dict(kind='native', **{k: query[k] for k in ('boot_id', 'unit', 'invocation_id')},
            count=4 if phase == 2 else 3))
    return rows


def effects_fixture():
    effects = object.__new__(d.FieldEffects)
    for case, jobs, phases in zip(d.CASES, (9, 2, 3), (3, 1, 1)):
        d._usage_commit_case(effects, case, count_rows(case['index'], jobs, phases), [])
    effects.context = dict(hello=dict(guest_boottime_origin_ns=10), stdin_bytes_received=1024,
        guest_deadlines=dict(boot_id='boot', boottime_deadline_ns=1000, monotonic_deadline_ns=1000))
    effects._resource_snapshot = dict(missing=[], full_guest_filesystem_peak_proven=False,
        observed_maxima_sum=dict(bytes=4096, inodes=32))
    effects._carrier_usage = lambda **_: dict(carrier_cpu_ns=1234, carrier_memory_peak_bytes=5678, carrier_pids_peak=7)
    effects.now = lambda: dict(boot_id='boot', boottime_ns=110, monotonic_ns=120)
    return effects


def test_usage_real_counts_q4_has_no_reader_and_no_cpu_peak_sums():
    value = effects_fixture().usage()
    assert value == dict(guest_elapsed_ns=100, carrier_cpu_ns=1234, carrier_memory_peak_bytes=5678,
        carrier_pids_peak=7, stdin_bytes_received=1024, output_frame_bytes=0,
        guest_allocated_bytes=4096, guest_allocated_inodes=32, job_units_started=14,
        controller_units_started=6, quota_query_units_started=5,
        dynamic_quota_units_started=15, native_children_started=16)


def test_identical_reobservation_is_not_a_second_start():
    effects = effects_fixture(); prior = effects.usage()
    item = effects._usage_cases[d.CASES[1]['case_id']]
    d._usage_commit_case(effects, d.CASES[1], item['rows'], item['evidence'])
    assert effects.usage() == prior
    units, native = d._usage_merge_cases([item, item])
    assert sum(row['kind'] == 'job' for row in units.values()) == 2
    assert sum(native.values()) == 3


@pytest.mark.parametrize('fault', ['new_invocation', 'invocation_alias', 'native_count', 'native_missing'])
def test_identity_conflict_or_unknown_native_never_degrades_to_zero(fault):
    item = dict(rows=count_rows(1, 2, 1), evidence=[])
    other = copy.deepcopy(item)
    if fault == 'new_invocation': other['rows'][0]['invocation_id'] = 'f' * 32
    elif fault == 'invocation_alias': other['rows'][0]['invocation_id'] = item['rows'][1]['invocation_id']
    elif fault == 'native_count': other['rows'][-1]['count'] = 4
    else:
        item['rows'].pop(); other = copy.deepcopy(item)
    with pytest.raises(d.DispatchError):
        d._usage_merge_cases([item, other])


@pytest.mark.parametrize('fault', ['case', 'snapshot', 'missing', 'unknown', 'pids_peak', 'clock'])
def test_usage_missing_facts_never_become_budget_or_zero(fault):
    effects = effects_fixture()
    if fault == 'case': effects._usage_cases.pop(d.CASES[-1]['case_id'])
    elif fault == 'snapshot': del effects._resource_snapshot
    elif fault == 'missing': effects._resource_snapshot['missing'] = ['pool unavailable']
    elif fault == 'unknown': effects._resource_snapshot['observed_maxima_sum']['bytes'] = None
    elif fault == 'pids_peak': effects._carrier_usage = lambda **_: (_ for _ in ()).throw(d.DispatchError('PIDS_UNAVAILABLE'))
    else: effects.context['hello']['guest_boottime_origin_ns'] = 111
    value = effects.usage()
    assert effects._usage_missing
    unknown = {key for key, item in value.items() if item is None}
    assert {row['role'] for row in effects._usage_missing} == {'usage/' + key for key in unknown}
    assert value['stdin_bytes_received'] == 1024
    if fault != 'case': assert value['job_units_started'] == 14
    if fault in ('case', 'pids_peak', 'clock'): assert value['guest_allocated_bytes'] == 4096
    if fault not in ('clock', 'pids_peak'): assert value['carrier_cpu_ns'] == 1234


def record_case_fixture(monkeypatch, index):
    """Assemble frozen decoded configs and original control formats, no host run."""
    from admin.local_hand_quota_observer import q2_config
    from test_e3_q2_core_phase_facts import fixture
    case = d.CASES[index - 1]; sources = []; configurations = {}; files = {}; pins = {}
    prefix = 'cases/' + case['case_id'] + '/'
    boot = None; phases = {}; plan = None
    def source(suffix, value, role='control'):
        sources.append(dict(path=prefix + suffix, role=role, mode=384,
            raw=d.canonical(value, newline=True)))
    for phase_index, phase in enumerate(case['phases']):
        _, _, original_plan, items = fixture(index, phase)
        if plan is None: plan = original_plan
        item = next(item for item in items if item['role'] == 'observer-config')
        config_raw = item['raw']; cfg = q2_config.decode(config_raw,
            '/synthetic/capture/' + phase + '/observer.json', d._sha(config_raw))
        sources.append(item); configurations[phase] = cfg
        boot = cfg.active().as_dict()['request']['boot_id']
        data = cfg.active().as_dict(); digest = cfg.active().request.digest
        phases[phase] = dict(quota_request_sha256=digest, query_unit=cfg.active().request.query_unit,
            listener_unit='lhqoc-' + digest + '.service', admission_unit='lhqoa-' + digest + '.service')
        parent = '/synthetic/capture/' + phase
        pins[parent] = SimpleNamespace(st_dev=7, st_ino=900 + phase_index, st_uid=0, st_gid=0, st_mode=0o40700)
        pins[cfg.data()['evidence']['path']] = SimpleNamespace(st_dev=7, st_ino=300,
            st_uid=0, st_gid=0, st_mode=0o40700)
        target = original_plan['controllers']['target']
        target_identity = dict(unit=target['unit'], invocation_id='d' * 32, boot_id=boot, cgroup=target['cgroup'])
        owner = dict(target_identity, observed_ns=data['management']['issued_ns'] + 1)
        values = [('INTENT', dict(config_digest=cfg.digest, controller=owner,
            deadline_ns=data['request']['deadline_ns']))]
        management = {}
        for n, role in enumerate(('listener', 'admission')):
            unit = phases[phase]['listener_unit' if role == 'listener' else 'admission_unit']
            inv = f'{1000 + index * 100 + phase_index * 10 + n:032x}'
            values.extend([('DELIVERY', dict(role=role, unit=unit, command_digest='e' * 64)),
                ('INVOCATION', dict(role=role, unit=unit, invocation_id=inv))])
            management['collector' if role == 'listener' else 'admission'] = dict(boot_id=boot,
                unit=unit, invocation_id=inv, cgroup=data['management_parent']['path'] + '/' + unit)
        if index != 3:
            values.append(('CLOSED', dict(schema='local-hand-quota-management-closed/v1', config_digest=cfg.digest,
                request_digest=digest, controller=owner,
                stages={key: {'identity': value} for key, value in management.items()})))
        files[(parent, 'management.jsonl')] = encode_record(values)
        bundle, identity = ConfigAndRuntimeTests().bundle(cfg)
        identity['invocation_id'] = f'{2000 + index * 100 + phase_index:032x}'
        proof = dict(query=identity, terminal=dict(Id=identity['unit'], InvocationID=identity['invocation_id'],
            ControlGroup=identity['cgroup'], LoadState='loaded', Result='success', ExecMainCode='1', ExecMainStatus='0'),
            stopped=True, captures=[dict(stdout=d.canonical(bundle).decode(), stderr='', eof=['stderr','stdout'], error=None, returncode=0)])
        files[(cfg.data()['evidence']['path'], digest + '.json')] = d.canonical(proof)
        expected = next(row for row in plan['phases'] if row['phase'] == phase)
        ordinary = cfg.data()['peers'][data['request']['request_id']]['parent']['path']
        jobs = {}
        for n, stage in enumerate(('bootstrap', 'helper', 'result_reader')):
            unit = expected[stage + '_unit']
            jobs[stage] = dict(boot_id=boot, unit=unit, invocation_id=f'{3000 + index * 100 + phase_index * 10 + n:032x}',
                cgroup=ordinary + '/' + unit)
        if index == 1:
            stage_rows = {('reader' if key == 'result_reader' else key): {'identity': value} for key, value in jobs.items()}
            stage_rows.update({key: {'identity': value} for key,value in management.items()})
            stage_rows['query'] = {'identity': identity}
            source('launcher_output/phase-' + phase + '.json', {'fence': dict(boot_id=boot,
                request_digest=digest, execution_id=data['request']['execution_id'], stages=stage_rows)})
        elif index == 2:
            manager = {key: dict(value, delivery_attempted=True, execution_id=data['request']['execution_id'],
                cgroup_parent='/sys/fs/cgroup' + ordinary) for key,value in jobs.items() if key != 'result_reader'}
            manager['result_reader'] = None
            source('records/ledger-export.json', {'operation': {'record_json': d.canonical({'handles': {'preflight': {'manager': manager}}}).decode()}})
        else:
            source('launcher_output/gateway.json', dict(failure=None, recovery_finished=True, recovery_only=True,
                manager_binding=dict(schema='local-hand-manager-binding/v1', manager_kind='system',
                    authority_id=plan['identity']['authority_id'], boot_id=boot,
                    parent=cfg.data()['peers'][data['request']['request_id']]['parent']),
                stages=[dict(stage=stage, phase=phase, unit=value['unit'], invocation_id=value['invocation_id'],
                    recovery_observed=True, stop_ack=True, collectors_lost=True,
                    identity_observation=dict(Id=value['unit'], InvocationID=value['invocation_id'],
                        ControlGroup=value['cgroup'], LoadState='loaded', ActiveState='active', SubState='running'),
                    after=dict(Id=value['unit'], InvocationID=value['invocation_id'], LoadState='loaded',
                        ActiveState='inactive', SubState='dead', Job='0', ControlGroup=''))
                    for stage,value in jobs.items()]))
    plan['controllers']['supervisor'] = dict(unit=case['controller_prefix'] + '-supervisor.service',
        cgroup='/supervisor.slice/' + case['controller_prefix'] + '-supervisor.service')
    for folder, role, inv in (('supervisor_output','target','d' * 32), ('owner_output','supervisor','e' * 32)):
        spec = plan['controllers'][role]
        source(folder + '/stop.json', dict(acknowledged=True, complete=True,
            before=dict(Id=spec['unit'], InvocationID=inv, ControlGroup=spec['cgroup'], LoadState='loaded')))
        source(folder + '/seal.json', dict(original=dict(invocation_id=inv)))
    prepared = dict(paths={phase: '/synthetic/capture/' + phase for phase in case['phases']},
        children={phase: dict(device=7, inode=900 + n) for n, phase in enumerate(case['phases'])})
    effects = object.__new__(d.FieldEffects); effects.context = {'hello': {'guest_boot_id': boot}}
    effects._exec_guard = lambda _: None
    effects.phase_facts = lambda case, phase, plan, sources: phases[phase]
    effects._candidate_modules = lambda _: {'admin.local_hand_quota_observer.q2_config': q2_config,
        'admin.local_hand_quota_observer.q2_runtime': q2_runtime}
    fd_paths = {700 + i: path for i,path in enumerate(pins)}
    effects._held_directory = lambda path, **_: next(fd for fd,p in fd_paths.items() if p == path)
    monkeypatch.setattr(d.os, 'fstat', lambda fd: pins[fd_paths[fd]])
    monkeypatch.setattr(d.os, 'close', lambda fd: None)
    reads = []
    def read(fd, name, **kwargs):
        key = (fd_paths[fd], name); reads.append(key)
        kwargs['guard']()
        raw = files[key]
        return raw, dict(uid=0,gid=0,dev=7,ino=999,sha256=d._sha(raw),bytes=len(raw),mode=384,nlink=1)
    effects.stable_read_at = read
    return effects, case, prepared, plan, sources, reads


@pytest.mark.parametrize('index,jobs,queries,native', [(1,9,3,10), (2,2,1,3), (3,3,1,3)])
def test_case_effect_reads_only_original_controls_and_counts_actual_stage_set(monkeypatch, index, jobs, queries, native):
    effects, case, prepared, plan, sources, reads = record_case_fixture(monkeypatch, index)
    effects._record_case_usage(case, prepared, plan, sources, {})
    units, children = d._usage_merge_cases(effects._usage_cases.values())
    assert sum(row['kind'] == 'job' for row in units.values()) == jobs
    assert sum(row['kind'] == 'query' for row in units.values()) == queries
    assert sum(children.values()) == native
    assert len(reads) == queries * 2
    assert all(name == 'management.jsonl' or name.endswith('.json') and len(name) == 69 for _,name in reads)
    assert all('/business/' not in parent and 'ledger' not in name for parent,name in reads)
    assert len(effects._usage_evidence[case['case_id']]) == len(reads)


def test_q4_reader_identity_cannot_be_counted_when_cancel_contract_says_not_started(monkeypatch):
    effects, case, prepared, plan, sources, _ = record_case_fixture(monkeypatch, 2)
    source = next(row for row in sources if row['path'].endswith('/records/ledger-export.json'))
    exported = d.document(source['raw'],limit=d.MEMBER_LIMIT,newline=True)
    record = d.document(exported['operation']['record_json'].encode(),limit=d.MEMBER_LIMIT,newline=False)
    record['handles']['preflight']['manager']['result_reader'] = {}
    exported['operation']['record_json'] = d.canonical(record).decode()
    source['raw'] = d.canonical(exported,newline=True)
    with pytest.raises(d.DispatchError,match='Q4_READER'):
        effects._record_case_usage(case, prepared, plan, sources, {})
    assert not getattr(effects, '_usage_cases', {})


@pytest.mark.parametrize('change', ['logical_only', 'wrong_mount', 'wrong_parent', 'duplicate_prefix'])
def test_q4_exported_parent_must_be_the_original_physical_cgroup_path(monkeypatch, change):
    effects, case, prepared, plan, sources, _ = record_case_fixture(monkeypatch, 2)
    source = next(row for row in sources if row['path'].endswith('/records/ledger-export.json'))
    exported = d.document(source['raw'], limit=d.MEMBER_LIMIT, newline=True)
    record = d.document(exported['operation']['record_json'].encode(), limit=d.MEMBER_LIMIT, newline=False)
    part = record['handles']['preflight']['manager']['helper']
    original = part['cgroup_parent']
    part['cgroup_parent'] = {'logical_only': original.removeprefix('/sys/fs/cgroup'),
        'wrong_mount': original.replace('/sys/fs/cgroup', '/tmp/cgroup'),
        'wrong_parent': original + '/another.slice',
        'duplicate_prefix': '/sys/fs/cgroup' + original}[change]
    exported['operation']['record_json'] = d.canonical(record).decode()
    source['raw'] = d.canonical(exported, newline=True)
    with pytest.raises(d.DispatchError, match='Q4_CGROUP_PARENT'):
        effects._record_case_usage(case, prepared, plan, sources, {})
    assert not getattr(effects, '_usage_cases', {})


def terminal_h11_fixture(monkeypatch):
    """Use the frozen producer's accepted terminal form, with its leaf removed."""
    from local_hand_jobs import quota_lifecycle as life
    result = record_case_fixture(monkeypatch, 3)
    effects, _, _, _, sources, _ = result
    source = next(row for row in sources if row['path'].endswith('/launcher_output/gateway.json'))
    gateway = d.document(source['raw'], limit=d.MEMBER_LIMIT, newline=True)
    for part in gateway['stages']:
        observed = dict.fromkeys(life.FIELDS, '')
        observed.update(part['identity_observation'], ActiveState='inactive', SubState='dead',
            ControlGroup='', Job='0', Restart='no', KillMode='control-group', Type='exec',
            ExitType='cgroup', RemainAfterExit='yes')
        original = dict(unit=part['unit'], invocation_id=part['invocation_id'],
            quota_parent=gateway['manager_binding']['parent'], boot_id=effects.context['hello']['guest_boot_id'])
        # This exact pure producer check is why an empty terminal value can be
        # present in the frozen Gateway.snapshot; the raw observation stays empty.
        assert life._loaded_identity(original, observed)['invocation_id'] == part['invocation_id']
        assert life._terminal(observed)
        part['identity_observation'] = observed
    source['raw'] = d.canonical(gateway, newline=True)
    return result, source, gateway


def test_h11_terminal_identity_with_removed_leaf_counts_original_invocation(monkeypatch):
    (effects, case, prepared, plan, sources, _), source, gateway = terminal_h11_fixture(monkeypatch)
    original_raw = source['raw']
    effects._record_case_usage(case, prepared, plan, sources, {})
    units, _ = d._usage_merge_cases(effects._usage_cases.values())
    assert sum(row['kind'] == 'job' for row in units.values()) == 3
    assert source['raw'] == original_raw
    assert all(part['identity_observation']['ControlGroup'] == '' for part in gateway['stages'])


@pytest.mark.parametrize('change', ['active', 'manager_boot', 'parent_inode', 'invocation',
    'after_invocation', 'after_group', 'stop_unacknowledged'])
def test_h11_empty_leaf_requires_original_terminal_and_manager_bindings(monkeypatch, change):
    (effects, case, prepared, plan, sources, _), source, gateway = terminal_h11_fixture(monkeypatch)
    part = gateway['stages'][0]
    if change == 'active': part['identity_observation'].update(ActiveState='active', SubState='running')
    elif change == 'manager_boot': gateway['manager_binding']['boot_id'] = '0' * 36
    elif change == 'parent_inode': gateway['manager_binding']['parent']['inode'] += 1
    elif change == 'invocation': part['identity_observation']['InvocationID'] = 'f' * 32
    elif change == 'after_invocation': part['after']['InvocationID'] = 'f' * 32
    elif change == 'after_group': part['after']['ControlGroup'] = '/another.slice/' + part['unit']
    else: part['stop_ack'] = False
    source['raw'] = d.canonical(gateway, newline=True)
    with pytest.raises(d.DispatchError, match='H11_'):
        effects._record_case_usage(case, prepared, plan, sources, {})
    assert not getattr(effects, '_usage_cases', {})


def test_expired_original_clock_stops_before_any_carrier_io():
    effects = effects_fixture()
    effects.context['guest_deadlines']['boottime_deadline_ns'] = 110
    effects._carrier_usage = lambda **_: pytest.fail('carrier I/O after deadline')
    value = effects.usage()
    assert value['guest_elapsed_ns'] is None and value['carrier_cpu_ns'] is None
    assert value['job_units_started'] == 14 and value['guest_allocated_bytes'] == 4096


def test_usage_carrier_receives_original_outer_guard_not_new_window():
    effects = effects_fixture(); clocks = []
    def carrier(*, guard):
        clocks.append(guard())
        return dict(carrier_cpu_ns=1, carrier_memory_peak_bytes=2, carrier_pids_peak=3)
    effects._carrier_usage = carrier
    assert effects.usage()['carrier_pids_peak'] == 3
    assert clocks == [effects.now()]
    assert effects._usage_missing == []


def test_explicit_final_guard_reaches_nested_kernel_io_without_normal_reserve(tmp_path, monkeypatch):
    effect = object.__new__(d.FieldEffects)
    effect._effect_guard = lambda: pytest.fail('normal work reserve used for final observation')
    (tmp_path / 'pids.peak').write_bytes(b'3\n')
    calls = []
    monkeypatch.setattr(d, '_kernel_fs_type', lambda fd: 0x63677270)
    fd = d.os.open(tmp_path, d.os.O_RDONLY | d.os.O_DIRECTORY)
    try:
        assert effect._capacity_kernel('pids.peak',64,dir_fd=fd,guard=lambda: calls.append('guard')) == b'3\n'
    finally: d.os.close(fd)
    assert len(calls) >= 10


def test_explicit_final_guard_reaches_directory_path_walk(tmp_path, monkeypatch):
    effect = object.__new__(d.FieldEffects)
    effect._effect_guard = lambda: pytest.fail('normal work reserve used for final observation')
    effect._capacity_protection = lambda info: None  # Temp fixture ownership only.
    calls = []
    fd = effect._capacity_directory(str(tmp_path),guard=lambda: calls.append('guard'))
    try: assert d.os.fstat(fd).st_ino == tmp_path.stat().st_ino
    finally: d.os.close(fd)
    assert len(calls) >= 10
