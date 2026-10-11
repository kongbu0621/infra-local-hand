"""Fixed dual archives, retained completion, and nonrefundable continuation costs."""
import copy
import json
import sys

import pytest

from e3_host import q2_core_prior_attempt as p
from runtime_preparation_continuation_fixture import records, archive, source, DUMP, PIN

if sys.platform.startswith('linux'):
    from e3_host import q2_core_delivery_dispatcher as d
else:
    d = None


def test_two_fixed_archives_preserve_old_failure_and_exact_history():
    files, identity, _ = records()
    raw = archive(files)
    proof, activation, previous = p.build_runtime_preparation_source(raw, identity)
    prior, old_activation, legacy = p.build_identity_source(identity)
    assert proof['prior'] == prior and activation == old_activation
    assert len(raw) == 409600 and len(identity) == 798720
    assert len(p.runtime_preparation_archive_files(raw)[0]) == 18
    assert previous == p.identity_maintenance_resume()
    assert legacy == p.persistent_maintenance_resume()
    logical = dict(resume=p.maintenance_resume(), persistent_source=proof)
    manifest = dict(schema='lhq-journal-growth-manifest/v21',
        inputs=p.encode_manifest_inputs(logical),
        resume=p.encode_maintenance_resume(logical['resume'], proof))
    assert p.decode_manifest_inputs(manifest, previous) == logical
    assert len(DUMP(manifest['resume'])) < len(DUMP(logical['resume']))
    assert proof['summary']['remote_exit'] == 'UNKNOWN'
    assert proof['summary']['core_cases'] == 'NOT_RUN'
    if d:
        assert d.validate_runtime_preparation_source(proof) == proof


@pytest.mark.parametrize('fault', ['short', 'long', 'padding', 'trailing', 'order', 'identity'])
def test_fixed_pair_rejects_shape_or_identity_replacement(fault):
    files, identity, _ = records()
    raw = bytearray(archive(files))
    if fault == 'short': raw = raw[:-512]
    elif fault == 'long': raw += b'\0' * 512
    elif fault == 'padding':
        entries, _ = p.runtime_preparation_archive_files(bytes(raw))
        raw[512 + len(entries[p.PREPARATION_MEMBERS[0]])] = 1
    elif fault == 'trailing': raw[-1024] = 1
    elif fault == 'order': raw[:6] = b'other/'
    else: identity = identity[:-512] + b'\1' * 512
    with pytest.raises(p.c.ContractError):
        p.build_runtime_preparation_source(bytes(raw), identity)


@pytest.mark.parametrize('fault', ['success', 'authority', 'old_schema', 'history', 'source',
    'guest_success', 'diagnostic_trace', 'freeze', 'core_run', 'coordinator', 'custodian',
    'cpu', 'rss', 'caller_exit', 'stdout_eof', 'stderr_eof', 'caller_stdout', 'caller_stderr',
    'execute', 'preflight', 'index', 'absent', 'started', 'identity_pin', 'caller_set'])
def test_reindexed_failure_cannot_forge_actual_completion(fault):
    files, identity, _ = records()
    name = {
        'success':p.PREPARATION_ORIGINALS[-1], 'authority':p.PREPARATION_ORIGINALS[-1],
        'old_schema':p.PREPARATION_ORIGINALS[-1], 'history':p.PREPARATION_ORIGINALS[0],
        'source':p.PREPARATION_ORIGINALS[2], 'guest_success':p.PREPARATION_ORIGINALS[2],
        'diagnostic_trace':p.PREPARATION_ORIGINALS[2], 'freeze':'ir1-freeze.json',
        'core_run':'ir2-terminal.json', 'coordinator':'ir2-terminal.json',
        'custodian':'ir2-terminal.json', 'cpu':'ir2-terminal.json', 'rss':'ir2-terminal.json',
        'caller_exit':'ir2-caller-completion.json', 'stdout_eof':'ir2-caller-completion.json',
        'stderr_eof':'ir2-caller-completion.json', 'caller_stdout':'ir2-caller-completion.json',
        'caller_stderr':'ir2-caller.stderr', 'execute':'ir2-execute.stdout',
        'preflight':'ir2-preflight.stdout', 'index':p.PREPARATION_RECORDS[0],
        'absent':p.PREPARATION_RECORDS[0], 'started':'ir2-caller-started.json',
        'identity_pin':'ir1-freeze.json', 'caller_set':'ir1-freeze.json'}[fault]
    key = 'old11a/' + name
    if fault == 'caller_stderr': files[key] = b'unreported stderr\n'
    else:
        value = json.loads(files[key])
        if fault == 'success': value['state'] = 'VERIFIED'
        elif fault == 'authority': value['A'] = p.c.RUNTIME_PREPARATION_BASELINE['commit']
        elif fault == 'old_schema': value['schema'] = 'lhq-journal-growth-receipt/v18'
        elif fault == 'history': value['manifest']['resume']['previous_reference']['field'] = 'other'
        elif fault == 'source': value['source_binding_sha256'] = 'f' * 64
        elif fault == 'guest_success': value['status'] = 'VERIFIED'
        elif fault == 'diagnostic_trace': value['diagnostic']['traceback'] = 'changed'
        elif fault == 'freeze': value['ir2']['state'] = 'CURRENT_READY'
        elif fault == 'core_run': value['ir3']['H01'] = 'PASS'
        elif fault == 'coordinator': value['ir2']['coordinator_completion']['returncode'] = 0
        elif fault == 'custodian': value['ir2']['coordinator_completion']['child']['returncode'] = 3
        elif fault == 'cpu': value['ir2']['coordinator_completion']['usage']['cpu_nanoseconds'] = 240000000001
        elif fault == 'rss': value['ir2']['coordinator_completion']['usage']['rss_peak_bytes'] = 1073741825
        elif fault == 'caller_exit': value['returncode'] = 0
        elif fault in ('stdout_eof', 'stderr_eof'): value[fault] = False
        elif fault == 'caller_stdout': value['stdout']['sha256'] = 'f' * 64
        elif fault == 'execute': value['coordinator_completion']['returncode'] = 0
        elif fault == 'preflight': value['manifest_sha256'] = 'f' * 64
        elif fault == 'index': value['files'].pop(p.PREPARATION_ORIGINALS[-1])
        elif fault == 'absent': value['absent'].pop()
        elif fault == 'started': value['session'] = 'lhqjgrow-20261011b'
        elif fault == 'identity_pin': value['activation_archive']['sha256'] = 'f' * 64
        else: value['callers'].pop('core_once.py')
        files[key] = DUMP(value)
        # Bind the changed caller record into terminal as well: EOF must be checked itself.
        if fault in ('stdout_eof', 'stderr_eof'):
            terminal = json.loads(files['old11a/ir2-terminal.json'])
            terminal['ir2']['caller_completion'] = value
            files['old11a/ir2-terminal.json'] = DUMP(terminal)
    with pytest.raises((p.c.ContractError, KeyError)):
        p.build_runtime_preparation_source(archive(files), identity)


@pytest.mark.parametrize('fault', ['size', 'prior', 'history', 'summary', 'bool', 'member'])
def test_independent_consumers_reject_source_projection_changes(fault):
    value = copy.deepcopy(source())
    if fault == 'size': value['archive']['bytes'] += 512
    elif fault == 'prior': value['prior']['summary']['state'] = 'SUCCESS'
    elif fault == 'history': value['predecessor']['resume_sha256'] = 'f' * 64
    elif fault == 'summary': value['summary']['remote_exit'] = 'SUCCESS'
    elif fault == 'bool': value['summary']['caller_returncode'] = True
    else: value['predecessor']['member'] = 'old11a/other'
    with pytest.raises(p.c.ContractError): p.validate_runtime_preparation_source(value)
    if d:
        with pytest.raises(d.DispatchError): d.validate_runtime_preparation_source(value)


def test_old_full_costs_and_new_full_costs_are_separate():
    costs = p.maintenance_commitments()
    rows = costs['generations']
    assert len(rows) == len({r['session'] for r in rows}) == 18
    assert all((r['bytes'], r['inodes'], r['cpu_seconds']) == (1296*1048576,370,120)
        for r in rows[:16])
    assert rows[-2:] == [dict(session=s,bytes=2200*1048576,inodes=402,cpu_seconds=240)
        for s in ('lhqjgrow-20261011a','lhqjgrow-20261011b')]
    assert sum(r['cpu_seconds'] for r in rows) == 2400
    assert costs['identity_preparation']['host_bytes'] == costs['runtime_preparation']['host_bytes'] == 4194304
    assert costs['protection_read']['source_preparation_included'] is True
    if d: assert costs == d._maintenance_commitments()
