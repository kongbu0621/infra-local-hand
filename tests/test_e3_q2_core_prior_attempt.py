"""Synthetic prior-attempt and current-scope tests, never field acceptance."""
import base64
import copy
import importlib.util
import os
from pathlib import Path
import stat
import struct
import sys
from types import SimpleNamespace

import pytest

from core_prior_fixture import fixture, patch_pins, quiescence, raw_files
from e3_host import q2_core_prior_attempt as p

c = p.c


def test_public_original_pins_and_full_commitment_are_fixed():
    assert p.TOTAL_BYTES == sum(size for size, _ in p.PINS.values()) == 9318
    assert len(p.PINS) == 5
    assert p.SESSION != c.SESSION_ID and p.UNIT != c.CARRIER_UNIT
    with pytest.raises(c.ContractError, match='PIN'):
        p.build(raw_files())  # Synthetic bytes must never pass production pins.


def test_host_independent_consumer_and_full_old_commitment(monkeypatch):
    prior, files = fixture(monkeypatch)
    hello = p.validate(copy.deepcopy(prior))
    assert hello['carrier_unit']['name'] == p.UNIT
    commitment = p.commitment(prior)
    assert commitment['logical_bytes'] == 276 * 1048576
    assert commitment['logical_inodes'] == 16512 and commitment['cpu_seconds'] == 2090
    assert commitment['host_capture_bytes'] == 64 * 1048576
    assert commitment['host_capture_inodes'] == 16 and not commitment['released_or_refunded']
    assert sum(map(len, files.values())) < commitment['host_capture_bytes']


@pytest.mark.parametrize('change', ['missing', 'extra', 'order', 'base64', 'raw', 'length',
    'digest', 'scope', 'package', 'implementation', 'file_fields'])
def test_host_rejects_altered_envelope(monkeypatch, change):
    value, _ = fixture(monkeypatch)
    if change == 'missing': value['files'].pop()
    elif change == 'extra': value['files'].append(copy.deepcopy(value['files'][0]))
    elif change == 'order': value['files'].reverse()
    elif change == 'base64': value['files'][0]['raw_base64'] += '\n'
    elif change == 'raw': value['files'][0]['raw_base64'] = base64.b64encode(b'x').decode()
    elif change == 'length': value['files'][0]['bytes'] += 1
    elif change == 'digest': value['files'][0]['sha256'] = '0' * 64
    elif change == 'scope': value['scope'] = 'different'
    elif change == 'package': value['package_sha256'] = '0' * 64
    elif change == 'implementation': value['implementation']['tree'] = '0' * 40
    else: value['files'][0]['trusted'] = True
    with pytest.raises(c.ContractError): p.validate(value)


def altered_files(change):
    files = raw_files()
    role = 'acceptance-receipt.json'
    value = c.document(files[p.basename(role)], limit=65536, newline=True)
    if change == 'bind': value['transport']['bind_written'] = True
    elif change == 'package': value['transport']['package_written'] = True
    elif change == 'stdin': value['transport']['stdin_bytes_written'] = 1
    elif change == 'hello_false': value['transport']['hello_valid'] = False
    elif change == 'success': value['real_task_execution']['status'] = 'PASS'
    elif change == 'wait': value['wait']['status'] = 0
    elif change == 'capture': value['capture']['manifest_sha256'] = '0' * 64
    elif change == 'marker': value['consumption']['sha256'] = '0' * 64
    elif change == 'extra_field': value['trusted'] = True
    elif change == 'duplicate_key':
        files[p.basename(role)] = b'{"scope":"different",' + files[p.basename(role)][1:]
        return files
    elif change in ('extra_frame', 'truncated', 'hello_source', 'hello_uid', 'hello_limit'):
        out = files[p.basename('stdout')]
        if change == 'extra_frame': out += out
        elif change == 'truncated': out = out[:-1]
        else:
            hello = c.document(out[16:], limit=4096, newline=True)
            if change == 'hello_source': hello['loader_sha256'] = '0' * 64
            elif change == 'hello_uid': hello['uid'] = 1000
            else: hello['carrier_unit']['memory_max'] += 1
            raw = c.canonical(hello, newline=True)
            out = c.HELLO_MAGIC + struct.pack('>Q', len(raw)) + raw
        files[p.basename('stdout')] = out
        return files
    files[p.basename(role)] = c.canonical(value, newline=True)
    return files


@pytest.mark.parametrize('change', ['bind', 'package', 'stdin', 'hello_false', 'success', 'wait',
    'capture', 'marker', 'extra_field', 'duplicate_key', 'extra_frame', 'truncated',
    'hello_source', 'hello_uid', 'hello_limit'])
def test_structural_checks_reject_even_when_test_pins_match(monkeypatch, change):
    files = altered_files(change)
    patch_pins(monkeypatch, files)
    with pytest.raises(c.ContractError): p.build(files)


def call(function, *args, returned=None, **kwargs):
    value = function(*args, **kwargs)
    if returned: returned(value)
    return value


@pytest.mark.skipif(not hasattr(os, 'fstatvfs'), reason='Descriptor filesystem capacity observation')
@pytest.mark.parametrize('available_bytes,available_inodes,accept_floor', [
    (128 * 1048576, 32, True), (128 * 1048576 - 1, 32, False),
    (128 * 1048576, 31, False), (2**40, 2**30, True)])
def test_host_floor_never_refunds_old_or_claims_complete_bill(monkeypatch,
        available_bytes, available_inodes, accept_floor):
    prior, _ = fixture(monkeypatch)
    def observed(function, *_args):
        if function is os.fstat: return SimpleNamespace(st_dev=1, st_ino=2)
        assert function is os.fstatvfs
        return SimpleNamespace(f_frsize=1, f_bavail=available_bytes, f_favail=available_inodes)
    if accept_floor:
        result = p.observe_capture_floor(10, dict(dev=1, ino=2), prior, observed)
        assert result['core_reserved_bytes'] == 128 * 1048576
        assert result['core_reserved_inodes'] == 32
        assert result['earlier_host_obligations'] == 'NOT_BOUND'
        assert result['complete_host_admission_proven'] is False
    else:
        with pytest.raises(c.ContractError, match='HOST_CAPACITY_FLOOR'):
            p.observe_capture_floor(10, dict(dev=1, ino=2), prior, observed)


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux no-atime held descriptors')
@pytest.mark.parametrize('change', [None, 'link', 'mode', 'result', 'parent', 'late_open'])
def test_exact_held_original_reader(tmp_path, monkeypatch, change):
    _, files = fixture(monkeypatch)
    root = tmp_path / 'anchor'; root.mkdir(mode=0o700)
    for name, raw in files.items():
        (root / name).write_bytes(raw); (root / name).chmod(0o600)
    selected = root / sorted(files)[0]
    if change == 'link': os.link(selected, root / 'alias')
    elif change == 'mode': selected.chmod(0o644)
    elif change == 'result': (root / p.basename('remote-result.json')).write_bytes(b'')
    info = root.stat()
    anchor = dict(path=str(root), dev=info.st_dev, ino=info.st_ino, mode=0o700,
                  uid=info.st_uid, gid=info.st_gid)
    if change == 'parent': anchor['ino'] += 1
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    opened = []
    def late(function, *args, returned=None, **kwargs):
        value = call(function, *args, returned=returned, **kwargs)
        if function is os.open:
            opened.append(value)
            raise c.ContractError('TEST_LATE_OPEN')
        return value
    try:
        if change is None:
            before = {name: (root / name).stat().st_atime_ns for name in files}
            assert p.read_files(fd, anchor, call) == files
            assert {name: (root / name).stat().st_atime_ns for name in files} == before
        else:
            with pytest.raises(c.ContractError):
                p.read_files(fd, anchor, late if change == 'late_open' else call)
        for held in opened:
            with pytest.raises(OSError): os.fstat(held)
    finally:
        os.close(fd)


@pytest.fixture
def guest(monkeypatch):
    if not sys.platform.startswith('linux'): pytest.skip('Linux standalone dispatcher')
    spec = importlib.util.spec_from_file_location('_core_prior_guest_test',
        Path(__file__).parent / 'e3_host/q2_core_delivery_dispatcher.py')
    d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
    prior, _ = fixture(monkeypatch, d)
    from test_e3_q2_core_dispatch_v2 import context_v2
    return d, prior, context_v2()


def test_guest_pins_match_source_and_independent_parser(guest):
    d, prior, _ = guest
    assert d.PRIOR_PINS == p.PINS
    assert d._prior_attempt(prior) == p.validate(prior)


@pytest.mark.parametrize('change', ['bind', 'package', 'stdin', 'hello_false', 'success', 'wait',
    'capture', 'marker', 'extra_field', 'duplicate_key', 'extra_frame', 'truncated',
    'hello_source', 'hello_uid', 'hello_limit'])
def test_guest_independent_structural_rejection(guest, monkeypatch, change):
    d, prior, _ = guest
    files = altered_files(change); patch_pins(monkeypatch, files, d)
    prior['files'] = [dict(basename=name, bytes=len(raw), sha256=c.sha256(raw),
        raw_base64=base64.b64encode(raw).decode()) for name, raw in sorted(files.items())]
    with pytest.raises(d.DispatchError): d._prior_attempt(prior)


@pytest.mark.parametrize('branch', ['COLLECTED_ABSENT', 'LOADED_ABSENT', 'LOADED_EMPTY'])
def test_quiescent_branches_preserve_unknown(guest, branch):
    d, prior, context = guest
    record = quiescence(prior, context)
    if branch.startswith('LOADED'):
        record['branch'] = 'LOADED_TERMINAL'
        for row in record['observations']:
            row['unit'].update(LoadState='loaded', InvocationID='4' * 32, ExitType='cgroup')
            if branch.endswith('EMPTY'):
                group = row['cgroup']
                group.update(state='EMPTY', populated=0, procs_bytes=0,
                    identity=dict(group['parent'], path=group['path'], ino=3))
    assert d._validate_prior_quiescence(record, context) is record
    assert record['historical_usage'] == record['historical_remote_exit'] == 'UNKNOWN'


@pytest.mark.parametrize('change', ['active', 'pid', 'invocation', 'loaded_stub', 'populated',
    'boot', 'parent', 'alias', 'parent_drift', 'missing_field', 'extra_field', 'clock',
    'late', 'branch_drift', 'inode_drift', 'success', 'zero_usage', 'refund', 'one_observation'])
def test_new_scope_unknown_or_identity_drift_cannot_pass(guest, change):
    d, prior, context = guest; value = quiescence(prior, context)
    row = value['observations'][1]; unit = row['unit']; group = row['cgroup']
    if change == 'active': unit.update(ActiveState='active', SubState='running')
    elif change == 'pid': unit['MainPID'] = '999'
    elif change == 'invocation': unit['InvocationID'] = '5' * 32
    elif change == 'loaded_stub': unit['LoadState'] = 'loaded'
    elif change == 'populated': group['populated'] = 1
    elif change == 'boot': value['boot_id'] = '0' * 36
    elif change == 'parent': group['parent']['uid'] = 1000
    elif change == 'alias': group['parent']['mode'] = 0o777
    elif change == 'parent_drift': group['parent']['ino'] += 1
    elif change == 'missing_field': del unit['InvocationID']
    elif change == 'extra_field': unit['PIDStartTime'] = 'invented'
    elif change == 'clock': row['monotonic_ns'] = 1
    elif change == 'late': row['boottime_ns'] = context['guest_deadlines']['boottime_deadline_ns']
    elif change == 'branch_drift':
        unit.update(LoadState='loaded', InvocationID='4' * 32, ExitType='cgroup')
    elif change == 'inode_drift':
        group.update(state='EMPTY', populated=0, procs_bytes=0,
            identity=dict(group['parent'], path=group['path'], ino=55))
    elif change == 'success': value['historical_remote_exit'] = 'PASS'
    elif change == 'zero_usage': value['historical_usage'] = 0
    elif change == 'refund': value['released_bytes'] = 1
    else: value['observations'].pop()
    with pytest.raises(d.DispatchError): d._validate_prior_quiescence(value, context)


def observer_fixture(guest, monkeypatch, *, present=False):
    """Synthetic kernel/manager boundary. No real manager or guest is contacted."""
    d, prior, context = guest; e = d.FieldEffects(context)
    state = dict(tick=0, late=False, boot=context['hello']['guest_boot_id'], calls=0,
        present=present, populated=False, drift=False, open_fds={}, closed=[], bad_show=None)
    group_path = '/sys/fs/cgroup/system.slice/' + p.UNIT
    paths = ['/', '/sys', '/sys/fs', '/sys/fs/cgroup', '/sys/fs/cgroup/system.slice', group_path]
    def info(path):
        inode = paths.index(path) + 1 + (100 if state['drift'] and path.endswith('system.slice') else 0)
        return SimpleNamespace(st_dev=1, st_ino=inode, st_mode=stat.S_IFDIR | 0o755, st_uid=0, st_gid=0)
    def guard():
        if state['late']: raise d.DispatchError('TEST_DEADLINE')
        state['tick'] += 1
        return dict(boot_id=state['boot'], boottime_ns=context['hello']['guest_boottime_origin_ns'] + state['tick'],
                    monotonic_ns=context['hello']['guest_monotonic_origin_ns'] + state['tick'])
    def fs(function, *args, **kwargs):
        if function is os.fstat: return info(state['open_fds'][args[0]])
        if function is d._kernel_fs_type: return 0x63677270
        name = args[0]; parent = kwargs.get('dir_fd')
        path = name if parent is None else state['open_fds'][parent].rstrip('/') + '/' + name
        if path == group_path and not state['present']: raise FileNotFoundError(path)
        if function is os.stat: return info(path)
        assert function is os.open and args[1] & os.O_NOFOLLOW
        fd = max([10000, *state['open_fds']]) + 1; state['open_fds'][fd] = path
        return fd
    def guarded(function, *args, release=None, **kwargs):
        return d._guard_call(guard, lambda: fs(function, *args, **kwargs), release=release)
    real_close = os.close
    def close(fd):
        if fd in state['open_fds']:
            del state['open_fds'][fd]; state['closed'].append(fd)
        else: real_close(fd)
    monkeypatch.setattr(d.os, 'close', close)
    e._effect_guard = guard; e._capacity_call = guarded
    def show(arguments, program):
        state['calls'] += 1
        assert arguments == ['show', '--all', p.UNIT, '--property=' + ','.join(d.PRIOR_SHOW_FIELDS)]
        if state['bad_show'] == 'timeout': raise d.DispatchError('TEST_TIMEOUT')
        if state['bad_show'] == 'late': state['late'] = True
        unit = quiescence(prior, context)['observations'][0]['unit']
        if state['present']: unit.update(LoadState='loaded', InvocationID='4' * 32, ExitType='cgroup')
        raw = ''.join(key + '=' + unit[key] + '\n' for key in d.PRIOR_SHOW_FIELDS).encode()
        if state['bad_show'] == 'truncated': raw = raw[:-15]
        if state['bad_show'] == 'duplicate': raw += b'Id=duplicate\n'
        if state['bad_show'] == 'active': raw = raw.replace(b'ActiveState=inactive', b'ActiveState=active')
        return raw
    e._capacity_systemctl = show
    e._capacity_kernel = lambda name, *_args, **_kwargs: (b'' if name == 'cgroup.procs'
        else b'populated ' + (b'1' if state['populated'] else b'0') + b'\nfrozen 0\n')
    return d._PriorScopeObserver(e, {'systemctl': {}}), state


@pytest.mark.parametrize('present', [False, True])
def test_two_observations_use_same_held_parent_and_no_third_call(guest, monkeypatch, present):
    observer, state = observer_fixture(guest, monkeypatch, present=present)
    try:
        observer.observe(); observer.observe()
        result = observer.finish()
        assert state['calls'] == 2 and result['current_scope_quiescent'] is True
        with pytest.raises(guest[0].DispatchError, match='NO_RETRY'): observer.observe()
        assert state['calls'] == 2
    finally: observer.close()
    assert not state['open_fds']


@pytest.mark.parametrize('failure', ['truncated', 'duplicate', 'active', 'timeout', 'late', 'populated', 'boot', 'parent_drift'])
def test_failed_observation_never_retries_or_installs(guest, monkeypatch, failure):
    d, _, _ = guest
    observer, state = observer_fixture(guest, monkeypatch, present=failure == 'populated')
    try:
        if failure == 'parent_drift':
            observer.observe(); state['drift'] = True
        elif failure == 'populated': state['populated'] = True
        elif failure == 'boot': state['boot'] = 'changed'
        else: state['bad_show'] = failure
        with pytest.raises(d.DispatchError): observer.observe()
        calls = state['calls']
        with pytest.raises(d.DispatchError, match='STOPPED'): observer.observe()
        with pytest.raises(d.DispatchError, match='INCOMPLETE'): observer.finish()
        assert state['calls'] == calls and observer.effects._installation is None
    finally: observer.close()
    assert not state['open_fds']
