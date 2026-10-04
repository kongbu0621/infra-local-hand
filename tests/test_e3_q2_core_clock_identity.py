"""Reused clock descriptors still read fresh boot bytes and protected names."""
import importlib.util
import os
from pathlib import Path
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux procfs and boot clocks', allow_module_level=True)

spec = importlib.util.spec_from_file_location('_core_clock_identity_test',
    Path(__file__).parent / 'e3_host/q2_core_delivery_dispatcher.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

BOOT = '11111111-2222-4333-8444-555555555555'
OTHER = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'


@pytest.fixture
def clock(tmp_path, monkeypatch):
    parent = tmp_path / 'proc/sys/kernel/random'
    parent.mkdir(parents=True)
    target = parent / 'boot_id'
    target.write_text(BOOT + '\n', encoding='ascii')
    effect = d.FieldEffects({})
    original_stat, original_open = os.stat, os.open
    opened = []
    paths = {'/', '/proc', '/proc/sys', '/proc/sys/kernel', '/proc/sys/kernel/random'}

    def named(path, *args, **kwargs):
        if str(path) in paths:
            path = tmp_path / str(path).lstrip('/')
        return original_stat(path, *args, **kwargs)

    def opening(*args, **kwargs):
        if args and str(args[0]) == '/' and kwargs.get('dir_fd') is None:
            args = (str(tmp_path), *args[1:])
        fd = original_open(*args, **kwargs)
        opened.append(fd)
        return fd

    effect._held_directory = lambda path: d.os.open(parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    monkeypatch.setattr(d.os, 'stat', named)
    monkeypatch.setattr(d.os, 'open', opening)
    try:
        yield effect, target, parent, opened
    finally:
        effect.close()


def test_each_call_reads_fresh_boot_bytes_and_both_clocks(clock, monkeypatch):
    effect, target, _, opened = clock
    calls = []
    original = d.time.clock_gettime_ns
    def fresh(which):
        calls.append(which)
        return original(which)
    monkeypatch.setattr(d.time, 'clock_gettime_ns', fresh)
    first = effect.now()
    for _ in range(4):
        assert effect.now()['boot_id'] == BOOT
    assert len(opened) == 6 and len(effect.held) == 6
    assert calls == [d.time.CLOCK_BOOTTIME, d.time.CLOCK_MONOTONIC] * 5
    inode = target.stat().st_ino
    target.write_text(OTHER + '\n', encoding='ascii')
    assert target.stat().st_ino == inode
    assert effect.now()['boot_id'] == OTHER
    with pytest.raises(d.DispatchError, match='BOOT_CHANGED'):
        d._clock(effect, {'boot_id': BOOT, 'boottime_deadline_ns': first['boottime_ns'] + 10**12,
            'monotonic_deadline_ns': first['monotonic_ns'] + 10**12})
    assert len(opened) == 6


@pytest.mark.parametrize('replace', ['file', 'parent', 'ancestor_alias'])
def test_reused_descriptors_reject_changed_names(clock, replace):
    effect, target, parent, opened = clock
    effect.now()
    if replace == 'file':
        target.rename(parent / 'old')
        target.write_text(BOOT + '\n', encoding='ascii')
    elif replace == 'parent':
        parent.rename(parent.with_name('old'))
        parent.mkdir()
        (parent / 'boot_id').write_text(BOOT + '\n', encoding='ascii')
    else:
        ancestor = parent.parent
        retained = ancestor.with_name('retained')
        ancestor.rename(retained)
        ancestor.symlink_to(retained, target_is_directory=True)
    with pytest.raises(d.DispatchError, match='BOOT_ID'):
        effect.now()
    assert len(opened) == 6


@pytest.mark.parametrize('raw', [b'', b'not-a-uuid\n', b'x' * 65, b'\xff' * 20])
def test_invalid_initial_bytes_do_not_retain_descriptors(clock, raw):
    effect, target, _, opened = clock
    target.write_bytes(raw)
    with pytest.raises(d.DispatchError, match='BOOT_ID'):
        effect.now()
    assert not effect.held and not hasattr(effect, '_clock_fds')
    for fd in opened:
        with pytest.raises(OSError): os.fstat(fd)


def test_explicit_eof_is_checked_on_each_read(clock, monkeypatch):
    effect, _, _, opened = clock
    original = os.pread
    calls = []
    def unexpected_tail(fd, size, offset):
        calls.append((size, offset))
        return b'x' if size == 1 else original(fd, size, offset)
    monkeypatch.setattr(d.os, 'pread', unexpected_tail)
    with pytest.raises(d.DispatchError, match='BOOT_ID'):
        effect.now()
    assert calls == [(65, 0), (1, len(BOOT) + 1)]
    assert not effect.held
    for fd in opened:
        with pytest.raises(OSError): os.fstat(fd)


def test_close_releases_owned_descriptors_and_clears_cache(clock):
    effect, _, _, opened = clock
    effect.now()
    effect.close()
    assert not effect.held and not hasattr(effect, '_clock_fds')
    for fd in opened:
        with pytest.raises(OSError): os.fstat(fd)
    effect.close()
    assert effect.now()['boot_id'] == BOOT
    assert len(opened) == 12 and len(effect.held) == 6


def test_real_proc_clock_reads_are_fresh_and_close_owned_fds():
    effect = d.FieldEffects({})
    try:
        first, second = effect.now(), effect.now()
        assert first['boot_id'] == second['boot_id']
        assert first['boottime_ns'] <= second['boottime_ns']
        assert first['monotonic_ns'] <= second['monotonic_ns']
        assert len(effect.held) == 6
        fds = list(effect.held)
    finally:
        effect.close()
    for fd in fds:
        with pytest.raises(OSError): os.fstat(fd)
