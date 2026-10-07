"""Post-locale synthetic regressions: no saved snapshot or field execution."""
import base64
import os
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux field consumer and held-descriptor tests', allow_module_level=True)

from core_prior_fixture import diagnostic_files, triple_fixture, patch_pins, raw_files
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_contract as c
from e3_host import q2_core_delivery_dispatcher as d
from e3_host import q2_core_delivery_freeze as f
from test_e3_q2_core_prior_attempt import observer_fixture, call
from test_e3_q2_core_dispatch_v2 import context_v2


def test_fixed_diagnostic_metadata_has_no_raw_and_preserves_unknown():
    value = p.diagnostic_retention()
    assert p.validate_diagnostic(value) == d._validate_diagnostic_retention(value)
    assert sum(row['bytes'] for row in value['files']) == 8782
    assert value['host_capture_bytes'] == 4194304 and value['host_capture_inodes'] == 8
    assert value['remote_exit'] == value['management_usage'] == 'UNKNOWN'
    assert value['remote_supervision_proven'] is value['released_or_refunded'] is False
    assert all(set(row) == {'basename', 'bytes', 'sha256'} for row in value['files'])


@pytest.mark.parametrize('change', ['raw', 'missing', 'order', 'digest', 'length', 'supervision',
    'exit', 'usage', 'refund', 'bytes', 'inodes', 'reader', 'implementation', 'session'])
def test_both_metadata_consumers_reject_omission_and_truth_promotion(change):
    value = p.diagnostic_retention()
    if change == 'raw': value['files'][0]['raw_base64'] = 'private'
    elif change == 'missing': value['files'].pop()
    elif change == 'order': value['files'].reverse()
    elif change == 'digest': value['files'][0]['sha256'] = '0' * 64
    elif change == 'length': value['files'][0]['bytes'] += 1
    elif change == 'supervision': value['remote_supervision_proven'] = True
    elif change == 'exit': value['remote_exit'] = 'COMPLETE'
    elif change == 'usage': value['management_usage'] = 0
    elif change == 'refund': value['released_or_refunded'] = True
    elif change == 'bytes': value['host_capture_bytes'] = 0
    elif change == 'inodes': value['host_capture_inodes'] = 0
    elif change == 'reader': value['reader_cpu_seconds'] += 1
    elif change == 'implementation': value['implementation']['commit'] = '0' * 40
    else: value['session_id'] = c.SESSION_ID
    with pytest.raises(c.ContractError): p.validate_diagnostic(value)
    with pytest.raises(d.DispatchError): d._validate_diagnostic_retention(value)


@pytest.mark.parametrize('change', [None, 'pin', 'missing', 'extra', 'marker', 'receipt',
    'streams', 'clock', 'success', 'duplicate'])
def test_local_diagnostic_records_bind_without_interpreting_stdout(monkeypatch, change):
    files = diagnostic_files(monkeypatch)
    prefix = '.' + p.DIAGNOSTIC_SESSION + '.'
    if change == 'pin': files[prefix + 'stdout'] += b'x'
    elif change == 'missing': files.pop(prefix + 'stderr')
    elif change == 'extra': files['unexpected'] = b''
    elif change:
        role = 'consumed.json' if change in ('marker', 'clock') else 'receipt.json'
        value = c.document(files[prefix + role], limit=65536, newline=True)
        if change == 'marker': value['D'] = '0' * 40
        elif change == 'receipt': value['requests_attempted'] = 2
        elif change == 'streams': value['files']['stdout']['sha256'] = '0' * 64
        elif change == 'clock': value['clock_origins_ns'] = [False, 1]
        elif change == 'success': value['remote_supervision_proven'] = True
        raw = c.canonical(value, newline=True)
        if change == 'duplicate': raw = b'{"state":"COMPLETE",' + raw[1:]
        files[prefix + role] = raw
        monkeypatch.setitem(p.DIAGNOSTIC_PINS, role, (len(raw), c.sha256(raw)))
    if change is None:
        # Opaque non-JSON stdout deliberately cannot be a configuration snapshot.
        result = p.build_diagnostic(files)
        assert result == p.diagnostic_retention()
        assert b'opaque' not in c.canonical(result)
    else:
        with pytest.raises(c.ContractError): p.build_diagnostic(files)


@pytest.mark.parametrize('suffix', ['consumed.json', 'stdout', 'stderr', 'receipt.json'])
@pytest.mark.parametrize('change', [None, 'missing', 'hardlink', 'mode', 'bytes'])
def test_each_diagnostic_original_is_stable_and_no_atime(tmp_path, monkeypatch, suffix, change):
    files = diagnostic_files(monkeypatch)
    tmp_path.chmod(0o700)
    for name, raw in files.items():
        path = tmp_path / name; path.write_bytes(raw); path.chmod(0o600)
    target = tmp_path / ('.' + p.DIAGNOSTIC_SESSION + '.' + suffix)
    if change == 'missing': target.unlink()
    elif change == 'hardlink': os.link(target, tmp_path / 'alias')
    elif change == 'mode': target.chmod(0o644)
    elif change == 'bytes': target.write_bytes(b'changed')
    info = tmp_path.stat()
    anchor = dict(path=str(tmp_path), dev=info.st_dev, ino=info.st_ino, mode=0o700,
                  uid=info.st_uid, gid=info.st_gid)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        if change is None:
            before = {name: (tmp_path / name).stat().st_atime_ns for name in files}
            assert p.read_diagnostic_files(fd, anchor, call, _seen=set()) == files
            assert before == {name: (tmp_path / name).stat().st_atime_ns for name in files}
        else:
            with pytest.raises((c.ContractError, OSError)):
                p.read_diagnostic_files(fd, anchor, call, _seen=set())
    finally: os.close(fd)


@pytest.mark.parametrize('change', ['bind', 'bytes', 'wait', 'success', 'eof', 'marker',
    'extra_frame', 'source', 'stderr', 'approved'])
def test_third_original_is_independently_bound(monkeypatch, change):
    priors, _ = triple_fixture(monkeypatch, d)
    files = raw_files(2); role = 'acceptance-receipt.json'
    if change == 'extra_frame': files[p.basename('stdout', 2)] *= 2
    elif change == 'source': files[p.basename('stdout', 2)] = raw_files(1)[p.basename('stdout', 1)]
    elif change == 'stderr': files[p.basename('stderr', 2)] = b'CORE_ADMIT_SUDO_OUTPUT\n'
    else:
        if change == 'approved': role = 'carrier-consumed.json'
        value = c.document(files[p.basename(role, 2)], limit=65536, newline=True)
        if change == 'bind': value['transport']['bind_written'] = False
        elif change == 'bytes': value['transport']['stdin_bytes_written'] -= 1
        elif change == 'wait': value['wait']['status'] = 0
        elif change == 'success': value['real_task_execution']['status'] = 'PASS'
        elif change == 'eof': value['wait']['stderr_eof'] = False
        elif change == 'marker': value['consumption']['sha256'] = '0' * 64
        else: value['approved_inputs_sha256'] = '0' * 64
        files[p.basename(role, 2)] = c.canonical(value, newline=True)
    patch_pins(monkeypatch, files, d, index=2)
    priors[2]['files'] = [dict(basename=name, bytes=len(raw), sha256=c.sha256(raw),
        raw_base64=base64.b64encode(raw).decode()) for name, raw in sorted(files.items())]
    with pytest.raises(c.ContractError): p.validate_all(priors)
    with pytest.raises(d.DispatchError): d._prior_attempts(priors)


@pytest.mark.parametrize('index', [0, 1, 2, 3])
@pytest.mark.parametrize('ordinal', [1, 2])
@pytest.mark.parametrize('failure', ['truncated', 'active', 'timeout', 'late', 'populated', 'boot', 'parent_drift'])
def test_each_old_observer_failure_is_terminal(monkeypatch, index, ordinal, failure):
    priors, _ = triple_fixture(monkeypatch, d)
    observer, state = observer_fixture((d, priors[index], context_v2()), monkeypatch,
                                      index=index, present=False)
    try:
        if ordinal == 2: observer.observe()
        if failure == 'parent_drift':
            if ordinal == 1:
                # Drift after the first held identity, not before any baseline exists.
                original_show = observer.effects._capacity_systemctl
                def changing_show(*args, **kwargs):
                    result = original_show(*args, **kwargs); state['drift'] = True
                    return result
                observer.effects._capacity_systemctl = changing_show
            else: state['drift'] = True
        elif failure == 'populated': state.update(present=True,populated=True)
        elif failure == 'boot': state['boot'] = 'changed'
        else: state['bad_show'] = failure
        with pytest.raises(d.DispatchError): observer.observe()
        calls = state['calls']
        with pytest.raises(d.DispatchError, match='STOPPED'): observer.observe()
        assert state['calls'] == calls and observer.effects._installation is None
    finally: observer.close()
    assert not state['open_fds']


@pytest.mark.parametrize('change', [None, 'body', 'missing', 'duplicate', 'decorator'])
def test_locale_source_comparison_does_not_execute_or_reparse_snapshot(change):
    original = b'def _require():\n    pass\ndef _admit_text():\n    pass\ndef _admit_sshd_source():\n    pass\n'
    current = original
    if change == 'body': current = current.replace(b'    pass', b'    return None', 1)
    elif change == 'missing': current = current.replace(b'_admit_text', b'_other')
    elif change == 'duplicate': current += b'def _admit_text():\n    pass\n'
    elif change == 'decorator': current = current.replace(b'def _require', b'@replacement\ndef _require')
    if change is None: f._validate_locale_source_preserved(original, current)
    else:
        with pytest.raises(f.c.ContractError): f._validate_locale_source_preserved(original, current)
