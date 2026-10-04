"""Complete second-pass grouping uses real temporary files, never field state."""
from __future__ import annotations

import os
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux held-directory metadata recheck', allow_module_level=True)

from test_e3_q2_core_pool_accounting import fixture, create, shared, d


def sample(f):
    root = shared(f)
    create(f, root + '/group')
    first = create(f, root + '/group/a', b'first')
    second = create(f, root + '/group/b', b'second')
    return root, first, second


def test_grouped_pass_still_checks_earlier_sibling_after_later_first_pass(fixture, monkeypatch):
    f = fixture
    root, first, second = sample(f)
    calls = []
    def opened(name, flags, *args, **kwargs):
        fd = f.open(name, flags, *args, **kwargs)
        if name == 'b' and flags & os.O_PATH:
            calls.append(name)
            if len(calls) == 1:
                first.write_bytes(b'changed after first sibling was visited')
        return fd
    monkeypatch.setattr(os, 'open', opened)
    with pytest.raises(d.DispatchError, match='OBJECT_DRIFT'):
        f.engine.observe('CHILD_AFTER', ['shared_install'])
    assert calls == ['b']


@pytest.mark.parametrize('replacement', ['directory', 'symlink'])
def test_group_cannot_accept_renamed_parent_even_with_original_fd(fixture, monkeypatch, replacement):
    f = fixture
    root, first, second = sample(f)
    group = first.parent
    opens = 0
    def opened(name, flags, *args, **kwargs):
        nonlocal opens
        fd = f.open(name, flags, *args, **kwargs)
        if name == 'b' and flags & os.O_PATH:
            opens += 1
            if opens == 2:
                retained = group.with_name('retained-group')
                group.rename(retained)
                if replacement == 'directory': group.mkdir(mode=0o700)
                else: group.symlink_to(retained.name, target_is_directory=True)
        return fd
    monkeypatch.setattr(os, 'open', opened)
    with pytest.raises((d.DispatchError, OSError)):
        f.engine.observe('CHILD_AFTER', ['shared_install'])
    assert opens == 2
    assert f.engine.rows['shared_install']['status'] == 'INCOMPLETE'


def test_late_file_open_in_second_pass_closes_new_fd_and_parent(fixture, monkeypatch):
    f = fixture
    sample(f)
    opens = 0
    def opened(name, flags, *args, **kwargs):
        nonlocal opens
        fd = f.open(name, flags, *args, **kwargs)
        if name == 'b' and flags & os.O_PATH:
            opens += 1
            if opens == 2:
                f.clock.expired = True
        return fd
    monkeypatch.setattr(os, 'open', opened)
    with pytest.raises(d.DispatchError, match='TEST_DEADLINE'):
        f.engine.observe('CHILD_AFTER', ['shared_install'])
    assert opens == 2
    assert f.engine.rows['shared_install']['status'] == 'INCOMPLETE'


def test_every_file_is_reopened_as_metadata_and_no_atime_is_changed(fixture, monkeypatch):
    f = fixture
    root, first, second = sample(f)
    third = create(f, root + '/group/c', b'third')
    paths = (first.parent.parent, first.parent, first, second, third)
    for path in paths:
        os.utime(path, ns=(1000000000, 2000000000))
    before = {path: path.stat() for path in paths}
    def denied(*args, **kwargs):
        raise AssertionError('metadata observation attempted payload read')
    monkeypatch.setattr(os, 'read', denied)
    monkeypatch.setattr(os, 'pread', denied)
    f.engine.observe('CHILD_AFTER', ['shared_install'])
    for name in ('a', 'b', 'c'):
        flags = [options for path, options in f.flags if path == name]
        assert len(flags) == 2
        assert all(options & os.O_PATH and options & os.O_NOFOLLOW for options in flags)
    for path, old in before.items():
        assert path.stat().st_atime_ns == old.st_atime_ns
    assert f.engine.rows['shared_install']['last_observation']['allocated_inodes'] == 5


def test_each_parent_is_rewalked_after_group_to_detect_namespace_replacement(fixture, monkeypatch):
    f = fixture
    root, first, second = sample(f)
    original = f.e._held_directory
    calls = []
    def held(path, **kwargs):
        calls.append(path)
        return original(path, **kwargs)
    monkeypatch.setattr(f.e, '_held_directory', held)
    f.engine.observe('CHILD_AFTER', ['shared_install'])
    # One no-follow walk enters the second-pass group and another verifies the
    # named parent after all its children. There is no per-file parent cache.
    assert calls.count(root + '/group') == 2
