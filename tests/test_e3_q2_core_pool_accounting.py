"""Real temporary-file allocation scans; quota/clock identities are explicit doubles.

No guest connection, project mutation, installation or business execution occurs.
"""
from __future__ import annotations

from collections import Counter
import copy
import errno
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux O_PATH/no-atime metadata observations', allow_module_level=True)

from test_e3_q2_core_candidate_loader import d


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    roles = ('install', 'state', 'quota', 'journal', 'evidence')
    locators = {role + '_parent': '/' + role for role in roles}
    parents, filesystems = {}, {}
    for role in roles:
        path = tmp_path / role
        path.mkdir(mode=0o700)
        pin = path.stat()
        parents[role] = dict(path='/' + role, dev=pin.st_dev, ino=pin.st_ino,
            mode=0o700, uid=os.getuid(), gid=os.getgid())
        filesystems[role] = dict(dev=pin.st_dev, fs_uuid='a' * 32)
    absence = [dict(kind='path', name=path, absent=True, collision=False)
        for path in d._admission_absent_paths(locators)]
    absence += [dict(kind='project', project_id=project, absent=True, collision=False)
        for case in d.CASES for project in case['project_ids']]
    e = d.FieldEffects(dict(manifest=dict(locators=locators), guest_deadlines=dict(boot_id='test-boot')))
    e._admission = dict(parents=parents, filesystems=filesystems,
        guest=dict(ordinary_uid=os.getuid(), ordinary_gid=os.getgid()), absence=absence)
    e._capacity_owners = {0, os.getuid()}
    clock = SimpleNamespace(expired=False, now=100)
    def guard():
        if clock.expired:
            raise d.DispatchError('TEST_DEADLINE')
    e._effect_guard = guard
    def now():
        clock.now += 1
        return dict(boot_id='test-boot', boottime_ns=clock.now, monotonic_ns=clock.now)
    e.now = now
    opened, closed, flags, queries = [], [], [], []
    real_open, real_close = os.open, os.close
    def mapped_open(path, options, *args, **kwargs):
        actual = str(tmp_path) if path == '/' else path
        fd = real_open(actual, options, *args, **kwargs)
        opened.append(fd); flags.append((str(path), options))
        return fd
    def close(fd):
        closed.append(fd)
        return real_close(fd)
    monkeypatch.setattr(os, 'open', mapped_open)
    monkeypatch.setattr(os, 'close', close)
    monkeypatch.setattr(d, '_cap_uuid', lambda fd: 'a' * 32)
    e._capacity_quota_inventory = lambda **kwargs: queries.append('inventory') or []
    e._capacity_quota_enforcement = lambda **kwargs: queries.append('enforcement') or 48
    engine = d._PoolAccounting(e)
    engine.observe('ADMISSION')
    yield SimpleNamespace(e=e, root=tmp_path, engine=engine, clock=clock,
        opened=opened, closed=closed, flags=flags, queries=queries, open=mapped_open)
    assert Counter(opened) == Counter(closed), 'pool observer leaked a descriptor'


def create(f, path, data=None):
    f.engine.before_write(path, requested_bytes=len(data) if data is not None else 0, create=True)
    real = f.root / path.lstrip('/')
    if data is None:
        real.mkdir(mode=0o700)
        f.engine.record_io(path, created_inodes=1)
    else:
        real.write_bytes(data)
        f.engine.record_io(path, written_bytes=len(data), created_inodes=1)
    return real


def shared(f):
    path = '/install/' + d.STAGING_BASENAME
    create(f, path)
    return path


def test_admission_absence_covers_all_32_pools_without_quota_queries(fixture):
    f = fixture
    assert len(f.engine.rows) == 32
    assert all(row['status'] == 'ABSENT' for row in f.engine.rows.values())
    assert f.queries == []
    f.engine.observe('FINALIZATION')
    report = f.engine.snapshot({'implementation': 'test-double'})
    assert report['observed_maxima_sum'] == {'bytes': 0, 'inodes': 0}
    assert report['full_guest_filesystem_peak_proven'] is False
    assert report['missing'] == []
    for row in report['pools']:
        observed = row['last_observation']
        payload = {key: value for key, value in observed.items() if key != 'source_sha256'}
        assert observed['source_sha256'] == d._sha(d.canonical(dict(
            pool_id=row['pool_id'], case_id=row['case_id'], observation=payload)))
    payload = {key: report[key] for key in ('completion_adjustment', 'pools', 'observed_maxima_sum')}
    assert report['snapshot_sha256'] == d._sha(d.canonical(payload))


def test_real_metadata_allocation_no_payload_reads_and_no_atime_changes(fixture, monkeypatch):
    f = fixture
    path = shared(f)
    file = create(f, path + '/payload', b'payload' * 1000)
    for p in (file, file.parent):
        os.utime(p, ns=(1000000000, 2000000000))
    before = [p.stat() for p in (file, file.parent)]
    def forbidden(*args, **kwargs):
        raise AssertionError('allocation observation read payload')
    monkeypatch.setattr(os, 'read', forbidden)
    monkeypatch.setattr(os, 'pread', forbidden)
    f.engine.observe('CONTROLLED_IO', ['shared_install'])
    row = f.engine.rows['shared_install']
    assert row['last_observation']['allocated_bytes'] == sum(x.st_blocks * 512 for x in before)
    assert row['last_observation']['allocated_inodes'] == 2
    assert row['controlled_io'] == dict(written_bytes=7000, created_inodes=2)
    for old, p in zip(before, (file, file.parent)):
        assert old.st_atime_ns == p.stat().st_atime_ns
    assert any(name == 'payload' and options & os.O_PATH for name, options in f.flags)
    assert all(options & os.O_NOATIME for name, options in f.flags if name == '.')


def test_disappearing_temporary_file_keeps_independent_maxima(fixture):
    f = fixture
    path = shared(f)
    file = create(f, path + '/temporary', b'x' * 8192)
    f.engine.observe('CHILD_AFTER', ['shared_install'])
    first = copy.deepcopy(f.engine.rows['shared_install']['last_observation'])
    file.unlink()  # Models a child-owned temporary disappearing, not a field cleanup.
    f.engine.observe('FINALIZATION')
    row = f.engine.rows['shared_install']
    assert row['last_observation']['allocated_inodes'] == 1
    assert row['bytes_maximum'] == first
    assert row['inodes_maximum'] == first
    assert f.engine.snapshot({})['full_guest_filesystem_peak_proven'] is False


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'fifo', 'writable'])
def test_unsafe_objects_stop_without_content_read(fixture, kind):
    f = fixture
    path = shared(f)
    file = create(f, path + '/original', b'x')
    target = file.parent / 'bad'
    if kind == 'symlink': target.symlink_to('original')
    elif kind == 'hardlink': os.link(file, target)
    elif kind == 'fifo': os.mkfifo(target, 0o600)
    else: file.chmod(0o666)
    with pytest.raises(d.DispatchError, match='FILE_TYPE|PROTECTION'):
        f.engine.observe('CHILD_AFTER', ['shared_install'])
    row = f.engine.rows['shared_install']
    assert row['status'] == 'INCOMPLETE'
    assert row['missing']
    assert f.engine.snapshot({})['observed_maxima_sum'] == dict(bytes=None, inodes=None)


def test_replaced_owned_root_and_recreated_absence_cannot_reset_maximum(fixture):
    f = fixture
    path = shared(f)
    f.engine.observe('CHILD_AFTER', ['shared_install'])
    real = f.root / path.lstrip('/')
    old = real.with_name('retained-original')
    real.rename(old)
    real.mkdir(mode=0o700)
    with pytest.raises(d.DispatchError, match='ROOT_REPLACED'):
        f.engine.observe('CHILD_AFTER', ['shared_install'])
    assert f.engine.rows['shared_install']['bytes_maximum'] is not None


def test_partial_create_then_missing_is_not_absent(fixture):
    f = fixture
    path = shared(f)
    (f.root / path.lstrip('/')).rmdir()
    with pytest.raises(d.DispatchError, match='UNPROVEN_ABSENCE'):
        f.engine.observe('FINALIZATION', ['shared_install'])
    assert f.engine.rows['shared_install']['status'] == 'INCOMPLETE'


def test_late_open_is_closed_and_not_retried(fixture, monkeypatch):
    f = fixture
    shared(f)
    def late(path, flags, *args, **kwargs):
        fd = f.open(path, flags, *args, **kwargs)
        if str(path) == '.':
            f.clock.expired = True
        return fd
    monkeypatch.setattr(os, 'open', late)
    with pytest.raises(d.DispatchError, match='TEST_DEADLINE'):
        f.engine.observe('CHILD_AFTER', ['shared_install'])
    assert sum(name == '.' for name, _ in f.flags) == 1
    assert f.engine.rows['shared_install']['status'] == 'INCOMPLETE'


def test_late_successful_io_retains_actual_short_write_count(fixture):
    f = fixture
    path = shared(f)
    f.clock.expired = True
    f.engine.record_io(path + '/late-file', written_bytes=3, created_inodes=1)
    assert f.engine.rows['shared_install']['controlled_io'] == dict(written_bytes=3, created_inodes=2)
    assert f.engine.snapshot({})['observed_maxima_sum'] == dict(bytes=None, inodes=None)
    with pytest.raises(d.DispatchError, match='TEST_DEADLINE'):
        f.engine.before_write(path + '/next', 1)


def test_noatime_denial_does_not_fallback(fixture, monkeypatch):
    f = fixture
    shared(f)
    attempts = []
    def denied(path, flags, *args, **kwargs):
        if flags & os.O_NOATIME:
            attempts.append(path)
            raise PermissionError(errno.EPERM, 'explicit test denial')
        return f.open(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, 'open', denied)
    with pytest.raises(PermissionError):
        f.engine.observe('CHILD_AFTER', ['shared_install'])
    assert len(attempts) == 1


def test_known_request_and_observed_allocation_have_separate_limits(fixture):
    f = fixture
    path = shared(f)
    f.engine.observe('CONTROLLED_IO', ['shared_install'])
    row = f.engine.rows['shared_install']
    amount = row['last_observation']['allocated_bytes']
    with pytest.raises(d.DispatchError, match='REQUEST_LIMIT'):
        f.engine.before_write(path + '/large', row['byte_limit'] - amount + 1)
    assert row['controlled_io']['written_bytes'] == 0


def test_last_boundary_failure_preserves_prior_maxima_but_never_complete(fixture, monkeypatch):
    f = fixture
    path = shared(f)
    create(f, path + '/payload', b'a')
    f.engine.observe('CHILD_AFTER', ['shared_install'])
    previous = copy.deepcopy(f.engine.rows['shared_install']['bytes_maximum'])
    monkeypatch.setattr(f.e, '_capacity_protection', lambda info: (_ for _ in ()).throw(OSError('test scan error')))
    with pytest.raises(OSError): f.engine.observe('FINALIZATION', ['shared_install'])
    assert f.engine.rows['shared_install']['bytes_maximum'] == previous
    assert f.engine.snapshot({})['observed_maxima_sum']['bytes'] is None
    with pytest.raises(d.DispatchError, match='PREVIOUS_FAILURE'):
        f.engine.observe('FINALIZATION', ['shared_install'])


def test_allocation_drift_during_scan_is_rejected(fixture, monkeypatch):
    f = fixture
    path = shared(f)
    file = create(f, path + '/payload', b'a')
    original = os.fstat
    changed = False
    def mutate(fd):
        nonlocal changed
        info = original(fd)
        if info.st_ino == file.stat().st_ino and not changed:
            changed = True
            file.write_bytes(b'changed bytes')
        return info
    monkeypatch.setattr(os, 'fstat', mutate)
    with pytest.raises(d.DispatchError, match='OBJECT_DRIFT'):
        f.engine.observe('CHILD_AFTER', ['shared_install'])


def test_longest_prefix_excludes_quota_business_subtree_before_stat(fixture, monkeypatch):
    f = fixture
    case = d.CASES[2]
    prefix = '/quota/' + d.SESSION
    create(f, prefix)
    create(f, prefix + '/' + case['case_id'])
    roots = d.FieldEffects.preparation_paths(case, f.e.context['manifest']['locators'])['roots']
    root = roots[0]
    target = f.root / root['path'].lstrip('/')
    target.mkdir(parents=True, mode=0o700)
    (target / 'business-result').write_bytes(b'NEVER ACCESS')
    original = os.stat
    def protect(path, *args, **kwargs):
        assert path not in (target.name, 'business-result'), 'quota subtree was statted'
        return original(path, *args, **kwargs)
    monkeypatch.setattr(os, 'stat', protect)
    f.engine.observe('CASE_BOUNDARY', [case['case_id'] + '/state'])
    assert f.engine.rows[case['case_id'] + '/state']['status'] == 'OBSERVED'


def test_unregistered_quota_root_rejected_without_scan(fixture, monkeypatch):
    f = fixture
    definition = next(p for p in f.engine.definitions if p['measurement_kind'] == 'PROJECT_QUOTA')
    path = definition['roots'][0]['path']
    target = f.root / path.lstrip('/')
    target.mkdir(parents=True, mode=0o700)
    (target / 'business-result').write_bytes(b'NEVER ACCESS')
    original = os.scandir
    def denied(fd):
        assert os.fstat(fd).st_ino != target.stat().st_ino, 'quota root was enumerated'
        return original(fd)
    monkeypatch.setattr(os, 'scandir', denied)
    with pytest.raises(d.DispatchError, match='QUOTA_UNREGISTERED'):
        f.engine.observe('CASE_BOUNDARY', [definition['pool_id']])


def quota_setup(f, case):
    definitions = [p for p in f.engine.definitions if p['case_id'] == case['case_id']
        and p['measurement_kind'] == 'PROJECT_QUOTA']
    roots = []
    for index, definition in enumerate(definitions):
        path = definition['roots'][0]['path']
        f.engine.record_io(path, created_inodes=1)
        roots.append(dict(path=path, device=f.e._admission['filesystems']['quota']['dev'],
            inode=10000 + index, filesystem_uuid='a' * 32, project_id=definition['project_id'],
            hard_bytes=1048576, inode_hard_limit=128, accounting=True, enforcement=True,
            identity_unchanged=True, xflags=512))
    return definitions, roots


def test_quota_initialization_partial_is_incomplete_and_never_queries(fixture):
    f = fixture
    definitions, roots = quota_setup(f, d.CASES[0])
    f.engine.observe('CONTROLLED_IO', [p['pool_id'] for p in definitions])
    assert f.queries == []
    assert all(f.engine.rows[p['pool_id']]['status'] == 'INCOMPLETE' for p in definitions)
    with pytest.raises(d.DispatchError, match='QUOTA_BINDING'):
        f.engine.quota_ready(d.CASES[0]['case_id'], roots[:-1])


def test_ready_quota_uses_only_bound_original_pins_and_readonly_inventory(fixture, monkeypatch):
    f = fixture
    case = d.CASES[2]
    definitions, roots = quota_setup(f, case)
    f.engine.quota_ready(case['case_id'], roots)
    f.e._capacity_quota_inventory = lambda **kwargs: [dict(project=p['project_id'], hard=1024,
        ihard=128, space=4096 + index * 512, inodes=1 + index) for index, p in enumerate(definitions)]
    monkeypatch.setattr(f.engine, '_locate', lambda *_: (_ for _ in ()).throw(AssertionError('quota path access')))
    f.engine.observe('FINALIZATION', [p['pool_id'] for p in definitions])
    for index, definition in enumerate(definitions):
        row = f.engine.rows[definition['pool_id']]
        assert row['status'] == 'OBSERVED'
        assert row['last_observation']['method'] == 'PROJECT_QUOTA'
        assert row['last_observation']['allocated_bytes'] == 4096 + index * 512
        assert row['last_observation']['identities'][0]['ino'] == roots[index]['inode']
        assert row['last_observation']['quota']['used_inodes'] == 1 + index


def test_quota_over_limit_retains_actual_observation_and_stops(fixture):
    f = fixture
    case = d.CASES[0]
    definitions, roots = quota_setup(f, case)
    f.engine.quota_ready(case['case_id'], roots)
    f.e._capacity_quota_inventory = lambda **kwargs: [dict(project=p['project_id'], hard=1024,
        ihard=128, space=1048577, inodes=1) for p in definitions]
    with pytest.raises(d.DispatchError, match='OBSERVED_LIMIT'):
        f.engine.observe('CHILD_AFTER', [definitions[0]['pool_id']])
    row = f.engine.rows[definitions[0]['pool_id']]
    assert row['bytes_maximum']['allocated_bytes'] == 1048577
    assert row['status'] == 'INCOMPLETE'


def test_snapshot_requires_final_boundary_and_unobserved_io_is_missing(fixture):
    f = fixture
    path = shared(f)
    report = f.engine.snapshot({})
    assert report['observed_maxima_sum']['bytes'] is None
    assert any(item['code'] == 'CORE_POOL_UNOBSERVED_IO' for item in report['missing'])
    assert any(item['code'] == 'CORE_POOL_FINALIZATION_MISSING' for item in report['missing'])


def test_only_frozen_pending_venv_alias_is_permitted(fixture):
    f = fixture
    if os.getuid() != 0:
        pytest.skip('Frozen installer alias requires original root owner')
    path = '/install/' + d.INSTALL_BASENAME
    create(f, path)
    create(f, path + '/runtime')
    create(f, path + '/runtime/lib')
    link = f.root / (path + '/runtime/lib64').lstrip('/')
    link.symlink_to('lib')
    os.utime(link, ns=(1000000000, 2000000000), follow_symlinks=False)
    alias_atime = link.lstat().st_atime_ns
    f.e._venv_alias_pending = True
    f.engine.observe('CHILD_AFTER', ['shared_install'])
    assert f.engine.rows['shared_install']['last_observation']['allocated_inodes'] == 4
    assert link.lstat().st_atime_ns == alias_atime
    f.e._venv_alias_pending = False
    with pytest.raises(d.DispatchError, match='PROTECTION|FILE_TYPE'):
        f.engine.observe('CHILD_AFTER', ['shared_install'])


def test_earlier_sibling_changed_during_later_visit_is_rechecked(fixture, monkeypatch):
    f = fixture
    path = shared(f)
    first = create(f, path + '/a', b'first')
    second = create(f, path + '/b', b'second')
    original = os.fstat
    changed = False
    second_ino = second.stat().st_ino
    def mutate(fd):
        nonlocal changed
        info = original(fd)
        if info.st_ino == second_ino and not changed:
            changed = True
            first.write_bytes(b'changed while later sibling inspected')
        return info
    monkeypatch.setattr(os, 'fstat', mutate)
    with pytest.raises(d.DispatchError, match='OBJECT_DRIFT'):
        f.engine.observe('CHILD_AFTER', ['shared_install'])


def test_unrecorded_root_creation_cannot_become_owned(fixture):
    f = fixture
    (f.root / 'install' / d.STAGING_BASENAME).mkdir(mode=0o700)
    with pytest.raises(d.DispatchError, match='ROOT_CREATION_UNKNOWN'):
        f.engine.observe('CASE_BOUNDARY', ['shared_install'])


def test_finalization_uses_supplied_original_outer_guard_without_refresh(fixture):
    f = fixture
    f.clock.expired = True
    outer_calls = []
    def outer():
        outer_calls.append(True)
    f.engine.observe('FINALIZATION', guard=outer)
    assert outer_calls
    assert f.engine.snapshot({})['missing'] == []
    with pytest.raises(d.DispatchError, match='TEST_DEADLINE'):
        f.engine.observe('CASE_BOUNDARY')
    assert f.engine.snapshot({})['observed_maxima_sum'] == dict(bytes=None, inodes=None)


def test_quota_finalization_forwards_original_outer_guard_to_native_helpers(fixture):
    f = fixture
    case = d.CASES[0]
    definitions, roots = quota_setup(f, case)
    f.engine.quota_ready(case['case_id'], roots)
    f.clock.expired = True
    calls = []
    def outer():
        calls.append('outer')
    def enforcement(*, guard):
        guard()
        return 48
    def inventory(*, guard):
        guard()
        return [dict(project=p['project_id'], hard=1024, ihard=128, space=4096, inodes=1)
            for p in definitions]
    f.e._capacity_quota_enforcement = enforcement
    f.e._capacity_quota_inventory = inventory
    f.engine.observe('FINALIZATION', [p['pool_id'] for p in definitions], guard=outer)
    assert calls
    assert all(f.engine.rows[p['pool_id']]['status'] == 'OBSERVED' for p in definitions)
