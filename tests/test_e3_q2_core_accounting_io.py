"""Controlled I/O records actual completed effects before late clock checks.

Accounting observations below are explicit doubles; filesystem effects are real
temporary files. These component checks do not establish guest acceptance.
"""
import importlib.util
import os
from pathlib import Path
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux held-file controlled I/O', allow_module_level=True)

spec = importlib.util.spec_from_file_location('_core_accounting_io_test',
    Path(__file__).parent / 'e3_host/q2_core_delivery_dispatcher.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class Guard:
    expired = False

    def __call__(self):
        if self.expired:
            raise d.DispatchError('TEST_ORIGINAL_DEADLINE')


class Accounting:
    def __init__(self, quota=False):
        self.by_id = {'pool': {'measurement_kind': 'PROJECT_QUOTA' if quota else 'OWNED_ALLOCATION'}}
        self.roots = []
        self.requests, self.records, self.observations = [], [], []
        self.missing = []

    def before_write(self, path, requested_bytes=0, create=False, *, guard=None):
        if guard is not None: guard()
        self.requests.append((path, requested_bytes, create))
        return 'pool'

    def record_io(self, path, written_bytes=0, created_inodes=0):
        self.records.append((path, written_bytes, created_inodes))

    def observe(self, boundary, pool_ids=None, *, guard=None):
        if guard is not None: guard()
        self.observations.append((boundary, pool_ids, guard))

    def mark_incomplete(self, identifier, field, reason):
        self.missing.append((identifier, field, reason))


def test_create_short_writes_and_fsync_use_actual_completed_bytes(tmp_path, monkeypatch):
    accounting, guard = Accounting(), Guard()
    real_write = os.write
    monkeypatch.setattr(d.os, 'write', lambda fd, raw: real_write(fd, raw[:3]))
    path = str(tmp_path / 'data')
    d.FieldEffects.create_only(path, b'abcdefgh', mode=0o600,
        accounting=accounting, guard=guard)
    assert Path(path).read_bytes() == b'abcdefgh'
    assert sum(row[1] for row in accounting.records) == 8
    assert sum(row[2] for row in accounting.records) == 1
    assert [row[1] for row in accounting.records if row[1]] == [3, 3, 2]
    assert [row[1] for row in accounting.requests if row[1]] == [8, 5, 2]
    assert len(accounting.observations) == 6  # create + three writes + two fsyncs
    assert all(row == ('CONTROLLED_IO', ['pool'], guard) for row in accounting.observations)


def test_late_create_is_charged_closes_fd_and_never_observed(tmp_path, monkeypatch):
    accounting, guard, opened = Accounting(), Guard(), []
    real_open = os.open
    path = str(tmp_path / 'partial')

    def late_open(*args, **kwargs):
        fd = real_open(*args, **kwargs)
        opened.append(fd)
        guard.expired = True
        return fd

    monkeypatch.setattr(d.os, 'open', late_open)
    with pytest.raises(d.DispatchError, match='ORIGINAL_DEADLINE'):
        d._accounting_io(accounting, guard, path, d.os.open, path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, create=True, release=os.close)
    assert accounting.records == [(path, 0, 1)] and accounting.observations == []
    assert Path(path).exists() and Path(path).stat().st_size == 0
    with pytest.raises(OSError): os.fstat(opened[0])


def test_late_short_write_records_actual_without_followup_io(tmp_path):
    accounting, guard = Accounting(), Guard()
    path = str(tmp_path / 'partial')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        def late_write(fd, raw):
            count = os.write(fd, raw[:3])
            guard.expired = True
            return count
        with pytest.raises(d.DispatchError, match='ORIGINAL_DEADLINE'):
            d._accounting_io(accounting, guard, path, late_write, fd, b'abcdefg',
                write=True, requested_bytes=7)
    finally:
        os.close(fd)
    assert accounting.records == [(path, 3, 0)] and accounting.observations == []
    assert Path(path).read_bytes() == b'abc'


def test_quota_root_creation_records_inode_without_early_quota_observation(tmp_path):
    accounting, guard = Accounting(quota=True), Guard()
    path = str(tmp_path / 'quota')
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        if os.geteuid() == os.getegid() == 0:
            fd = d.FieldEffects._mkdir_at(parent, 'quota', 0o700, guard=guard,
                accounting=accounting, path=path)
            os.close(fd)
        else:
            # Ordinary CI must retain the production root-owner rejection.
            # The completed create is still charged before that check fails.
            with pytest.raises(d.DispatchError, match='CORE_EFFECT_MKDIR_OWNER'):
                d.FieldEffects._mkdir_at(parent, 'quota', 0o700, guard=guard,
                    accounting=accounting, path=path)
    finally:
        os.close(parent)
    assert Path(path).is_dir() and sum(row[2] for row in accounting.records) == 1
    assert accounting.observations == []


def test_private_installer_fd_paths_account_create_write_and_sync(tmp_path):
    accounting, guard = Accounting(), Guard()
    bindings = d._InstallIO(guard, accounting)
    path = bindings.Path(tmp_path / 'installed')
    path.mkdir(0o700)
    file = path / 'payload'
    fd = bindings.os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with bindings.os.fdopen(fd, 'wb', closefd=False) as stream:
            assert stream.write(b'payload') == 7
            stream.flush()
        bindings.os.fsync(fd)
    finally:
        bindings.os.close(fd)
    assert file.read_bytes() == b'payload' and not bindings.paths
    assert sum(row[1] for row in accounting.records) == 7
    assert sum(row[2] for row in accounting.records) == 2
    assert len(accounting.observations) == 4
