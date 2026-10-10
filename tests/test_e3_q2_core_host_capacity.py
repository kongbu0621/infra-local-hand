"""Synthetic capacity observations and real temporary anchor I/O, not field PASS."""
import copy
import errno
import os
import stat
import sys
import time
from types import SimpleNamespace

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux held-anchor and original dual-clock checks', allow_module_level=True)

from core_prior_fixture import triple_fixture as fixture, diagnostic_files, journal_transition
from test_e3_q2_core_minimal_continuation import originals
from e3_host import q2_journal_growth as maintenance
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_capture as cap
from test_e3_q2_core_capture import Clock


@pytest.fixture
def inputs(tmp_path, monkeypatch,originals):
    prior, files = fixture(monkeypatch)
    files.update(diagnostic_files(monkeypatch))
    tmp_path.chmod(0o700)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    info = os.fstat(fd)
    anchor = dict(path=str(tmp_path), dev=info.st_dev, ino=info.st_ino, mode=0o700,
                  uid=info.st_uid, gid=info.st_gid, nlink=info.st_nlink)
    clock = Clock()
    deadline = cap.Deadline(clock.origins(), clock)
    writer = cap.observe_writer(deadline.call)
    binding = dict(anchor=anchor, writer=writer)
    args = dict(binding=binding, prior=prior, diagnostic=p.diagnostic_retention(), implementation=dict(commit='a'*40, tree='b'*40),
                deadline=deadline, writer_observer=cap.observe_writer)
    journal_files,original_args=originals
    transition=p.build_journal_transition(journal_files,**original_args)
    transition['implementation']=args['implementation']
    transition['retained_custody']['binding']['D']=args['implementation']['commit']
    transition['image_identities']={role:[info.st_dev,row[1]] for role,row in transition['image_identities'].items()}
    args.update(journal=transition,journal_files=journal_files)
    files.update(original_args['frozen']['previous_maintenance_files'])
    files.update(journal_files);files.update(original_args['frozen']['capacity_files'])
    class Images:
        def __init__(self,*args,**kwargs):self.fds={role:fd for role in transition['image_identities']}
        def image_keys(self):return transition['image_identities']
        def recheck(self):pass
        def close(self):pass
    monkeypatch.setattr(maintenance,'ImageSet',Images)
    yield fd, args, clock, files
    os.close(fd)


def validate(value, args):
    return p.validate_capacity_condition(value, binding=args['binding'], prior=args['prior'], diagnostic=args['diagnostic'],journal=args['journal'],
        implementation=args['implementation'], origins=args['deadline'].origins)


@pytest.mark.parametrize('frsize,blocks,inodes,accepted', [
    (1, 19092471808, 5196, True), (1, 19092471807, 5196, False), (4096, 4661248, 5195, False),
    (4096, 4661248, 5196, True), (4096, 2**30, 2**30, True), (0, 19092471808, 5196, False),
    (-1, 19092471808, 5196, False), (1, -1, 5196, False), (1, 19092471808, -1, False),
    (None, 19092471808, 5196, False), (True, 19092471808, 5196, False),
    (1, '19092471808', 5196, False), (1, 19092471808, 5196.0, False)])
def test_exact_fixed_five_rows_and_invalid_observation(inputs, monkeypatch, frsize, blocks, inodes, accepted):
    fd, args, clock, _ = inputs
    samples = []
    def observe(held):
        assert held == fd
        samples.append(held)
        return SimpleNamespace(f_frsize=frsize, f_bavail=blocks, f_favail=inodes)
    monkeypatch.setattr(os, 'fstatvfs', observe)
    if not accepted:
        with pytest.raises(p.c.ContractError, match='HOST_CAPACITY'):
            p.observe_capture_condition(fd, **args)
    else:
        value = p.observe_capture_condition(fd, **args)
        assert validate(value, args) is value
        assert value['capacity']['required_bytes'] == 19092471808
        assert value['known_commitments']==p._capacity_rows(args['prior'],args['diagnostic'])
        assert value['earlier_host_obligations'] == dict(coverage='UNKNOWN', bytes=None,
                                                      inodes=None, shared_pool='UNKNOWN')
        assert value['exclusive_reservation_proven'] is value['complete_host_admission_proven'] is False
        assert value['released_bytes'] == value['released_inodes'] == 0
        assert value['local_management_binding_sha256'] == p.c.sha256(p.c.canonical(args['binding'], newline=True))
    assert samples == [fd]
    assert clock.calls == [time.CLOCK_BOOTTIME, time.CLOCK_MONOTONIC] * (len(clock.calls)//2)


@pytest.mark.parametrize('change', ['mode', 'uid', 'gid', 'nlink', 'ino', 'dev', 'name',
                                    'writer', 'late', 'backward', 'io', 'missing'])
def test_drift_or_failed_observation_stops_before_marker(inputs, monkeypatch, change):
    fd, args, clock, _ = inputs
    fstat = os.fstat
    drifted = False
    def observed(held):
        nonlocal drifted
        drifted = True
        if change == 'late': clock.expire()
        elif change == 'backward': clock.now[time.CLOCK_MONOTONIC] -= 1
        elif change == 'io': raise OSError(errno.EIO, 'synthetic IO failure')
        if change == 'missing': return SimpleNamespace()
        return SimpleNamespace(f_frsize=4096, f_bavail=4661248, f_favail=5196)
    def identity(held):
        value = fstat(held)
        if held == fd and drifted and change in ('mode', 'uid', 'gid', 'nlink', 'ino', 'dev'):
            fields = {key: getattr(value, key) for key in
                      ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink')}
            fields['st_' + change] += 1
            return SimpleNamespace(**fields)
        return value
    original_stat = os.stat
    def named(path, **kwargs):
        value = original_stat(path, **kwargs)
        if drifted and change == 'name':
            fields = {key: getattr(value, key) for key in
                      ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink')}
            fields['st_ino'] += 1
            return SimpleNamespace(**fields)
        return value
    def writer(call):
        result = cap.observe_writer(call)
        if drifted and change == 'writer': result['process']['starttime_ticks'] += 1
        return result
    args['writer_observer'] = writer
    monkeypatch.setattr(os, 'fstatvfs', observed)
    monkeypatch.setattr(os, 'fstat', identity)
    monkeypatch.setattr(os, 'stat', named)
    with pytest.raises((p.c.ContractError, cap.CaptureError, OSError)):
        p.observe_capture_condition(fd, **args)
    assert not os.listdir(args['binding']['anchor']['path'])


@pytest.mark.parametrize('change', ['null', 'false', 'exclusive', 'refund', 'row', 'extra',
    'implementation', 'binding', 'prior', 'diagnostic', 'window', 'observation', 'dev', 'arithmetic',
    'omit_diagnostic', 'old_threshold'])
def test_live_record_cannot_promote_unknown_or_change_bindings(inputs, monkeypatch, change):
    fd, args, _, _ = inputs
    monkeypatch.setattr(os, 'fstatvfs', lambda _: SimpleNamespace(f_frsize=4096, f_bavail=4661248, f_favail=5196))
    value = p.observe_capture_condition(fd, **args)
    if change == 'null': value['earlier_host_obligations']['bytes'] = 0
    elif change == 'false': value['complete_host_admission_proven'] = True
    elif change == 'exclusive': value['exclusive_reservation_proven'] = True
    elif change == 'refund': value['released_inodes'] = False
    elif change == 'row': value['known_commitments'].reverse()
    elif change == 'extra': value['extra'] = 'caller claims PASS'
    elif change == 'implementation': value['implementation']['commit'] = 'c'*40
    elif change == 'binding': value['local_management_binding_sha256'] = 'c'*64
    elif change == 'prior': value['prior_attempts_sha256'] = 'c'*64
    elif change == 'diagnostic': value['diagnostic_retention_sha256'] = 'c'*64
    elif change == 'omit_diagnostic': value['known_commitments'].pop(0)
    elif change == 'old_threshold': value['capacity'].update(required_bytes=201326592, required_inodes=48)
    elif change == 'window': value['origins']['host_boottime_origin_ns'] += 1
    elif change == 'observation': value['observation']['after']['boottime_ns'] += cap.WINDOW_NS
    elif change == 'dev': value['dev'] += 1
    elif change == 'arithmetic': value['capacity']['bytes_available'] += 1
    with pytest.raises(p.c.ContractError): validate(value, args)


@pytest.mark.parametrize('failure', [None, 'capacity', 'prior', 'writer', 'late', 'tamper_return'])
def test_real_package_parser_through_pre_marker_and_live_return(inputs, monkeypatch, failure):
    # Explicit fixtures; actual builder/parser, source reader and delivery flow.
    from test_e3_q2_core_delivery_entry import e
    from test_e3_q2_core_delivery_package import fixture as package_fixture, p as package
    fd, args, clock, files = inputs
    manifest, members = package_fixture(monkeypatch)
    args['implementation']=manifest['implementation']
    args['journal']['implementation']=manifest['implementation']
    args['journal']['retained_custody']['binding']['D']=manifest['implementation']['commit']
    monkeypatch.setattr(package, '_approved_module', lambda: SimpleNamespace(prior_attempt=p,
        validate=lambda raw: package.c.validate_approved_inputs(package.c.document(raw, limit=1072576, newline=True))))
    old_helper = e._helper
    monkeypatch.setattr(e, '_helper', lambda name: package if name == 'q2_core_delivery_package' else old_helper(name))
    binding = dict(args['binding'], wrapper=dict(path='/fixture/wrapper'),
                   cwd=dict(path=args['binding']['anchor']['path']), remote_expectation={})
    digest = p.c.sha256(p.c.canonical(binding, newline=True))
    manifest['entry'].update(writer=binding['writer'], local_management_binding_sha256=digest,
                             carrier_argv_sha256=e.argv_digest(['/fixture/wrapper']))
    manifest['locators']['source_relation_sha256'] = p.c.sha256(p.c.canonical(
        package.locator_relation(manifest['locators'], digest)))
    approved = package.c.document(members[package.c.APPROVED_INPUTS_PATH], limit=1072576, newline=True)
    approved['reconciliation'] = dict(prior_core_attempts=args['prior'], prior_diagnostic_capture=args['diagnostic'],journal_transition=args['journal'])
    approved['policy_basis'] = dict(remote_expectation={})
    raw = package.c.canonical(approved, newline=True)
    row, header = package.approved_input_member(raw, amendment=manifest['amendment'])
    manifest['approved_inputs'] = header
    manifest['members'] = [row if item['path'] == row['path'] else item for item in manifest['members']]
    members[row['path']] = raw
    encoded = package.build_package(manifest, members)
    assert package.parse_package(encoded) == (manifest, members)
    for name, content in files.items():
        path = os.path.join(binding['anchor']['path'], name)
        with open(path, 'wb') as stream: stream.write(content)
        os.chmod(path, 0o600)
    if failure == 'prior':
        with open(path, 'ab') as stream: stream.write(b'changed')
    monkeypatch.setattr(e, 'field_release_gate', lambda *_: None)
    monkeypatch.setattr(e, 'wrapper_argv', lambda *_: ['/fixture/wrapper'])
    monkeypatch.setattr(e, 'requalify_management_anchor', lambda *_a, **_k:
        dict(wrapper_raw=b'fixture', binding_sha256=digest, fds=[]))
    monkeypatch.setattr(e, 'close_held_management', lambda _: None)
    observations = []
    def observe(_):
        observations.append(1)
        if failure == 'late': clock.expire()
        return SimpleNamespace(f_frsize=1, f_bavail=19092471807 if failure == 'capacity' else 19092471808,
                               f_favail=5196)
    monkeypatch.setattr(os, 'fstatvfs', observe)
    if failure == 'writer':
        changed = copy.deepcopy(binding['writer']); changed['process']['starttime_ticks'] += 1
        monkeypatch.setattr(e.capture_contract, 'observe_writer', lambda _: changed)
    markers, requests, returned = [], [], []
    original_marker = e.create_consumption_marker
    def marker(*a, **kw):
        value = original_marker(*a, **kw); markers.append(value); return value
    monkeypatch.setattr(e, 'create_consumption_marker', marker)
    monkeypatch.setattr(e, 'execute_carrier_once', lambda **kw: requests.append(kw) or {})
    def finalize(_fd, **kwargs):
        value = kwargs['host_capacity_condition']
        returned.append(value)
        if failure == 'tamper_return': value['capacity']['blocks_available'] += 1
        return dict(host_capacity_condition=value, receipt=dict(state='STOP_AND_RETAIN'))
    monkeypatch.setattr(e, 'finalize_carrier', finalize)
    options = dict(binding=binding, package_basename=package.c.SESSION_ID+'.lhfp', package_raw=encoded,
        loader_raw=members['field/loader.py'], bootstrap_raw=members['field/bootstrap.py'],
        wrapper_raw=b'fixture', origins=clock.origins(), clock_gettime_ns=clock)
    if failure:
        with pytest.raises((ValueError, RuntimeError)): e.deliver_once(fd, **options)
    else:
        result = e.deliver_once(fd, **options)
        assert result['host_capacity_condition'] is returned[0]
        assert result['receipt']['state'] == 'STOP_AND_RETAIN'
    consumed = failure in (None, 'tamper_return')
    assert len(markers) == len(requests) == int(consumed)
    assert len(observations) == int(failure not in ('prior', 'writer'))
    assert os.path.exists(os.path.join(binding['anchor']['path'], package.c.MARKER_BASENAME)) == consumed
