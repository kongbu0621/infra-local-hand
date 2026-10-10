"""Synthetic triple-history regressions; these are never field acceptance."""
import base64
import copy
import os
import sys
import uuid

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux fixed field dispatcher and held-source checks', allow_module_level=True)

from core_prior_fixture import triple_fixture, patch_pins, quiescence, raw_files
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_contract as c
from e3_host import q2_core_delivery_dispatcher as d
from test_e3_q2_core_dispatch_v2 import context_v2
from test_e3_q2_core_prior_attempt import observer_fixture, call


def test_fixed_triple_has_distinct_original_truth_and_nonrefundable_cost(monkeypatch):
    priors, files = triple_fixture(monkeypatch, d)
    assert len(files) == 20 and p.validate_all(priors) == d._prior_attempts(priors)
    for index, prior in enumerate(priors):
        hello = p.validate(prior, index=index)
        assert hello['carrier_unit']['name'] == p.profile(index)['unit']
        raw = c.document(files[p.basename('acceptance-receipt.json', index)], limit=65536, newline=True)
        assert raw['transport']['bind_written'] is bool(index)
        assert raw['wait']['status'] == (255, 3, 3, 3)[index]
        assert raw['real_task_execution']['status'] == 'UNKNOWN'
    charges = [p.commitment(prior, index=index) for index, prior in enumerate(priors)]
    assert sum(row['logical_bytes'] for row in charges) + c.LIMITS['total_guest_admission_bytes'] == 1736441856
    assert sum(row['logical_inodes'] for row in charges) + c.LIMITS['total_guest_admission_inodes'] == 99072
    assert sum(row['cpu_seconds'] for row in charges) + c.LIMITS['total_cpu_seconds'] == 12540
    assert all(row['released_or_refunded'] is False for row in charges)


@pytest.mark.parametrize('change', ['single', 'reverse', 'duplicate', 'third', 'old_schema', 'foreign_d', 'cross_files'])
def test_both_consumers_reject_mixed_or_incomplete_triple(monkeypatch, change):
    priors, _ = triple_fixture(monkeypatch, d)
    if change == 'single': priors.pop()
    elif change == 'reverse': priors.reverse()
    elif change == 'duplicate': priors[1] = copy.deepcopy(priors[0])
    elif change == 'third': priors.append(copy.deepcopy(priors[1]))
    elif change == 'old_schema': priors[1]['schema'] = 'local-hand-q2-core-prior-attempt/v1'
    elif change == 'foreign_d': priors[1]['implementation'] = copy.deepcopy(priors[0]['implementation'])
    else: priors[1]['files'] = copy.deepcopy(priors[0]['files'])
    with pytest.raises(c.ContractError): p.validate_all(priors)
    with pytest.raises(d.DispatchError): d._prior_attempts(priors)


@pytest.mark.parametrize('change', ['zero_bind', 'zero_bytes', 'old_wait', 'success', 'missing_eof',
    'marker', 'capture', 'duplicate', 'extra_hello', 'wrong_hello_unit', 'wrong_source', 'sudo_text'])
def test_second_structural_consumer_does_not_borrow_first_truth(monkeypatch, change):
    priors, _ = triple_fixture(monkeypatch, d)
    files = raw_files(1); key = p.basename('acceptance-receipt.json', 1)
    receipt = c.document(files[key], limit=65536, newline=True)
    if change == 'zero_bind': receipt['transport']['bind_written'] = False
    elif change == 'zero_bytes': receipt['transport']['stdin_bytes_written'] = 0
    elif change == 'old_wait': receipt['wait']['status'] = 255
    elif change == 'success': receipt['real_task_execution']['status'] = 'YES'
    elif change == 'missing_eof': receipt['wait']['stdout_eof'] = False
    elif change == 'marker': receipt['consumption']['sha256'] = '0' * 64
    elif change == 'capture': receipt['capture']['manifest_sha256'] = '0' * 64
    files[key] = c.canonical(receipt, newline=True)
    if change == 'duplicate': files[key] = b'{"scope":"duplicate",' + files[key][1:]
    elif change == 'extra_hello': files[p.basename('stdout', 1)] *= 2
    elif change in ('wrong_hello_unit', 'wrong_source'):
        key = p.basename('stdout', 1)
        files[key] = files[key].replace(b'lhqcore20261005a', b'lhqcore20261005b') if change == 'wrong_hello_unit' else files[key].replace(
            p.profile(1)['bootstrap_sha'].encode(), p.BOOTSTRAP_SHA.encode())
    elif change == 'sudo_text': files[p.basename('stderr', 1)] = b'CORE_ADMIT_SUDO_SOURCE\n'
    patch_pins(monkeypatch, files, d, index=1)
    priors[1]['files'] = [dict(basename=name, bytes=len(raw), sha256=c.sha256(raw),
        raw_base64=base64.b64encode(raw).decode()) for name, raw in sorted(files.items())]
    with pytest.raises(c.ContractError): p.validate_all(priors)
    with pytest.raises(d.DispatchError): d._prior_attempts(priors)


@pytest.mark.parametrize('index', [0, 1, 2, 3])
@pytest.mark.parametrize('change', [None, 'missing', 'hardlink', 'mode', 'result'])
def test_fifteen_original_reader_checks_each_profile(tmp_path, monkeypatch, index, change):
    _, files = triple_fixture(monkeypatch, d)
    tmp_path.chmod(0o700)
    for name, raw in files.items():
        target = tmp_path / name; target.write_bytes(raw); target.chmod(0o600)
    target = tmp_path / p.basename('acceptance-receipt.json', index)
    if change == 'missing': target.unlink()
    elif change == 'hardlink': os.link(target, tmp_path / 'alias')
    elif change == 'mode': target.chmod(0o644)
    elif change == 'result': (tmp_path / p.basename('remote-result.json', index)).write_bytes(b'')
    info = tmp_path.stat()
    anchor = dict(path=str(tmp_path), dev=info.st_dev, ino=info.st_ino, mode=0o700,
                  uid=info.st_uid, gid=info.st_gid)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        if change is None:
            before = {name: (tmp_path/name).stat().st_atime_ns for name in files}
            assert p.read_all_files(fd, anchor, call) == files
            assert before == {name: (tmp_path/name).stat().st_atime_ns for name in files}
        else:
            with pytest.raises((c.ContractError, FileNotFoundError)): p.read_all_files(fd, anchor, call)
    finally: os.close(fd)


@pytest.mark.parametrize('change', [None, 'second_loaded', 'missing', 'duplicate', 'reverse',
    'cross_digest', 'second_active', 'second_boot', 'second_invocation', 'order', 'refund'])
def test_triple_quiescence_exact_order_and_four_carrier_bound(monkeypatch, change):
    priors, _ = triple_fixture(monkeypatch, d); context = context_v2()
    values = [quiescence(prior, context) for prior in priors]
    assert d._prior_concurrency_bound(context) == dict(memory_bytes=6442450944, pids=768)
    assert d.LIMITS['peak_memory_bytes'] == 5248 * 1048576 and d.LIMITS['peak_pids'] == 2320
    if change == 'second_loaded':
        values[1]['branch'] = 'LOADED_TERMINAL'
        for row in values[1]['observations']:
            row['unit'].update(LoadState='loaded', InvocationID='5'*32, ExitType='cgroup')
    elif change == 'missing': values.pop()
    elif change == 'duplicate': values[1] = copy.deepcopy(values[0])
    elif change == 'reverse': values.reverse()
    elif change == 'cross_digest': values[1]['prior_attempt_sha256'] = values[0]['prior_attempt_sha256']
    elif change == 'second_active': values[1]['observations'][0]['unit']['ActiveState'] = 'active'
    elif change == 'second_boot': values[1]['boot_id'] = '00000000-0000-0000-0000-000000000000'
    elif change == 'second_invocation': values[1]['observations'][0]['unit']['InvocationID'] = '6'*32
    elif change == 'order': values[1]['observations'][0]['boottime_ns'] += 20
    elif change == 'refund': values[1]['released_bytes'] = 1
    if change is None: assert d._validate_prior_quiescences(values, context) == values
    else:
        with pytest.raises(d.DispatchError): d._validate_prior_quiescences(values, context)


@pytest.mark.parametrize('index', [0, 1, 2, 3])
@pytest.mark.parametrize('present', [False, True])
def test_each_final_held_name_drift_is_rejected_without_an_extra_show(monkeypatch, index, present):
    priors, _ = triple_fixture(monkeypatch, d)
    observer, state = observer_fixture((d, priors[0], context_v2()), monkeypatch, index=index, present=present)
    try:
        if present:
            with pytest.raises(d.DispatchError, match='COLLECTED'):
                observer.observe()
            assert state['calls'] == 1
            return
        observer.observe(); observer.observe(); observer.finish()
        assert state['calls'] == 2 and state['open_fds']
        state['drift'] = True
        with pytest.raises(d.DispatchError, match='DRIFT'): observer.recheck()
        assert state['calls'] == 2
    finally: observer.close()
    assert not state['open_fds']


def test_fixed_new_uuid_projects_and_artifacts_are_disjoint():
    old_sessions = {p.profile(index)['session'] for index in (0, 1, 2, 3)}
    assert c.SESSION_ID == d.SESSION == 'lhqcore-20261007a' and c.SESSION_ID not in old_sessions
    assert c.CARRIER_UNIT == 'lhqcore20261007a-carrier.service'
    for case in d.CASES:
        seed = 'urn:local-hand:LH-Q2-CORE-MINIMAL-CONTINUATION-v1:' + case['kind']
        assert case['operation_id'] == str(uuid.UUID(bytes=bytes.fromhex(c.sha256(seed.encode()))[:16], version=4))
    assert [project for case in d.CASES for project in case['project_ids']] == list(range(12501, 12522))
    assert len(d._admission_absent_units()) == 21
