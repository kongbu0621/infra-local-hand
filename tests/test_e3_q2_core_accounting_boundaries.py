"""Real syscall/observer integration at successful, partial and late boundaries.

Uses private temporary files only. No guest, quota mutation or installation.
"""
from __future__ import annotations

import errno
import os
from pathlib import PurePosixPath
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux held-file pool boundaries', allow_module_level=True)

from test_e3_q2_core_pool_accounting import fixture, create, shared, d


def parent_fd(f, path):
    return f.e._held_directory(str(PurePosixPath(path).parent), guard=f.e._effect_guard)


def make_file(f, path):
    parent = parent_fd(f, path)
    try:
        return d._accounting_io(f.engine, f.e._effect_guard, path, os.open,
            PurePosixPath(path).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600, dir_fd=parent, create=True, release=os.close)
    finally:
        os.close(parent)


def test_successful_create_short_writes_and_fsync_have_actual_counts(fixture):
    f = fixture
    root = shared(f)
    path = root + '/actual-file'
    fd = make_file(f, path)
    try:
        def short(fd, data):
            return os.write(fd, data[:3])
        raw = b'abcdefgh'
        offset = 0
        while offset < len(raw):
            offset += d._accounting_io(f.engine, f.e._effect_guard, path,
                short, fd, raw[offset:], write=True, requested_bytes=len(raw) - offset)
        d._accounting_io(f.engine, f.e._effect_guard, path, os.fsync, fd)
    finally:
        os.close(fd)
    info = (f.root / path.lstrip('/')).stat()
    row = f.engine.rows['shared_install']
    assert row['controlled_io'] == dict(written_bytes=8, created_inodes=2)
    assert row['last_observation']['allocated_inodes'] == 2
    assert row['last_observation']['allocated_bytes'] >= info.st_blocks * 512
    assert (f.root / path.lstrip('/')).read_bytes() == raw


def test_late_real_write_is_counted_and_retained_without_followup_scan(fixture, monkeypatch):
    f = fixture
    path = shared(f) + '/late-file'
    fd = make_file(f, path)
    calls = []
    real_observe = f.engine.observe
    def observe(*args, **kwargs):
        calls.append(True)
        return real_observe(*args, **kwargs)
    monkeypatch.setattr(f.engine, 'observe', observe)
    try:
        def late(fd, data):
            count = os.write(fd, data[:2])
            f.clock.expired = True
            return count
        with pytest.raises(d.DispatchError, match='TEST_DEADLINE'):
            d._accounting_io(f.engine, f.e._effect_guard, path, late, fd,
                b'abcdef', write=True, requested_bytes=6)
    finally:
        os.close(fd)
    assert calls == []
    assert (f.root / path.lstrip('/')).read_bytes() == b'ab'
    assert f.engine.rows['shared_install']['controlled_io']['written_bytes'] == 2
    assert any(item['role'] == 'shared_install/last_observation'
        for item in f.engine.snapshot({})['missing'])


def test_late_created_fd_is_closed_but_successful_creation_is_retained(fixture):
    f = fixture
    path = shared(f) + '/late-created'
    parent = parent_fd(f, path)
    returned = []
    try:
        def late(*args, **kwargs):
            fd = os.open(*args, **kwargs)
            returned.append(fd)
            f.clock.expired = True
            return fd
        with pytest.raises(d.DispatchError, match='TEST_DEADLINE'):
            d._accounting_io(f.engine, f.e._effect_guard, path, late,
                PurePosixPath(path).name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC,
                0o600, dir_fd=parent, create=True, release=os.close)
    finally:
        os.close(parent)
    assert (f.root / path.lstrip('/')).exists()
    assert f.engine.rows['shared_install']['controlled_io']['created_inodes'] == 2
    assert len(returned) == 1
    with pytest.raises(OSError) as error:
        os.fstat(returned[0])
    assert error.value.errno == errno.EBADF


def test_scan_failure_after_real_create_does_not_erase_inode_or_object(fixture, monkeypatch):
    f = fixture
    path = shared(f) + '/kept-partial'
    parent = parent_fd(f, path)
    original = f.engine._owned
    def failed(definition):
        if definition['pool_id'] == 'shared_install':
            raise OSError('test observation fault after create')
        return original(definition)
    monkeypatch.setattr(f.engine, '_owned', failed)
    try:
        with pytest.raises(OSError, match='test observation fault'):
            d._accounting_io(f.engine, f.e._effect_guard, path, os.open,
                PurePosixPath(path).name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC,
                0o600, dir_fd=parent, create=True, release=os.close)
    finally:
        os.close(parent)
    assert (f.root / path.lstrip('/')).exists()
    assert f.engine.rows['shared_install']['controlled_io']['created_inodes'] == 2
    assert f.engine.rows['shared_install']['status'] == 'INCOMPLETE'


def test_child_root_create_observes_both_state_and_carrier_parent_pools(fixture):
    f = fixture
    session = '/state/' + d.SESSION
    create(f, session)
    f.engine.observe('CONTROLLED_IO', ['carrier_audit'])
    previous = f.engine.rows['carrier_audit']['last_observation']['monotonic_ns']
    path = session + '/' + d.CASES[0]['case_id']
    parent = parent_fd(f, path)
    try:
        d._accounting_io(f.engine, f.e._effect_guard, path, os.mkdir,
            PurePosixPath(path).name, 0o700, dir_fd=parent, create=True)
    finally:
        os.close(parent)
    child_row = f.engine.rows[d.CASES[0]['case_id'] + '/state']
    parent_row = f.engine.rows['carrier_audit']
    assert child_row['last_observation']['allocated_inodes'] == 1
    assert child_row['controlled_io']['created_inodes'] == 1
    assert parent_row['controlled_io']['created_inodes'] == 1
    assert parent_row['last_observation']['monotonic_ns'] > previous
    assert parent_row['last_observation']['boundary'] == 'CONTROLLED_IO'


def test_real_failed_create_retains_first_object_and_cannot_be_finalized_away(fixture):
    f = fixture
    path = shared(f) + '/first-object'
    fd = make_file(f, path)
    os.close(fd)
    parent = parent_fd(f, path)
    before = dict(f.engine.rows['shared_install']['controlled_io'])
    inode = (f.root / path.lstrip('/')).stat().st_ino
    try:
        with pytest.raises(FileExistsError):
            d._accounting_io(f.engine, f.e._effect_guard, path, os.open,
                PurePosixPath(path).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                0o600, dir_fd=parent, create=True, release=os.close)
    finally:
        os.close(parent)
    assert (f.root / path.lstrip('/')).stat().st_ino == inode
    assert f.engine.rows['shared_install']['controlled_io'] == before
    assert any(item['code'] == 'CORE_POOL_CONTROLLED_IO_EFFECT_FAILED'
        for item in f.engine.rows['shared_install']['missing'])
    with pytest.raises(d.DispatchError, match='PREVIOUS_FAILURE'):
        f.engine.observe('FINALIZATION', ['shared_install'], guard=lambda: None)
    assert f.engine.snapshot({})['observed_maxima_sum'] == dict(bytes=None, inodes=None)


def test_boundary_helper_predeadline_failure_is_sticky_without_any_observation(fixture, monkeypatch):
    f = fixture
    calls = []
    original = f.engine.observe
    def observe(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(f.engine, 'observe', observe)
    f.clock.expired = True
    with pytest.raises(d.DispatchError, match='TEST_DEADLINE'):
        d._accounting_observe(f.engine, f.e._effect_guard, 'CASE_BOUNDARY', ['shared_install'])
    assert calls == []
    assert any(item['code'] == 'CORE_POOL_OBSERVATION_BOUNDARY_MISSING'
        for item in f.engine.rows['shared_install']['missing'])
    with pytest.raises(d.DispatchError, match='PREVIOUS_FAILURE'):
        f.engine.observe('FINALIZATION', ['shared_install'], guard=lambda: None)


def test_boundary_helper_postdeadline_failure_retains_real_scan_but_never_completes(fixture, monkeypatch):
    f = fixture
    path = shared(f)
    create(f, path + '/payload', b'owned bytes')
    original = f.engine.observe
    def late_return(*args, **kwargs):
        result = original(*args, **kwargs)
        f.clock.expired = True
        return result
    monkeypatch.setattr(f.engine, 'observe', late_return)
    with pytest.raises(d.DispatchError, match='TEST_DEADLINE'):
        d._accounting_observe(f.engine, f.e._effect_guard, 'CASE_BOUNDARY', ['shared_install'])
    row = f.engine.rows['shared_install']
    assert row['last_observation']['boundary'] == 'CASE_BOUNDARY'
    assert row['last_observation']['allocated_inodes'] == 2
    assert row['bytes_maximum']['allocated_bytes'] > 0
    assert row['status'] == 'INCOMPLETE'
    monkeypatch.setattr(f.engine, 'observe', original)
    with pytest.raises(d.DispatchError, match='PREVIOUS_FAILURE'):
        f.engine.observe('FINALIZATION', ['shared_install'], guard=lambda: None)
    assert f.engine.snapshot({})['observed_maxima_sum'] == dict(bytes=None, inodes=None)
