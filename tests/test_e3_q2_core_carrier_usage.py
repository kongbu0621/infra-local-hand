"""Bound carrier counter component tests; kernel views below are explicit doubles.

These tests do not prove that the real guest supports pids.peak and do not
establish complete resource accounting or field acceptance.
"""
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux cgroup component', allow_module_level=True)

spec = importlib.util.spec_from_file_location('_core_usage_test',
    Path(__file__).parent / 'e3_host/q2_core_delivery_dispatcher.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def fixture(tmp_path, monkeypatch):
    effect = object.__new__(d.FieldEffects)
    info = tmp_path.stat()
    bound = dict(unit='carrier.service', path='/carrier.service', invocation_id='a' * 32,
        device=info.st_dev, inode=info.st_ino)
    effect._admission = {}
    effect._admission_detail = dict(carrier=bound)
    effect.context = dict(hello=dict(carrier_unit=dict(name=bound['unit'],
        control_group=bound['path'], invocation_id=bound['invocation_id'])))
    effect._effect_guard = lambda: None
    effect.now = lambda: dict(boot_id='test', boottime_ns=100, monotonic_ns=90)
    effect._capacity_directory = lambda path: os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    # Only ownership is synthetic; all held-fd lifecycle operations are real.
    real_fstat = os.fstat
    def root_owned(fd):
        original = real_fstat(fd)
        return SimpleNamespace(**{name: (0 if name == 'st_uid' else getattr(original, name))
            for name in dir(original) if name.startswith('st_')})
    monkeypatch.setattr(d.os, 'fstat', root_owned)
    source = {'/proc/self/cgroup': b'0::/carrier.service\n',
        'cpu.stat': b'usage_usec 12000\nuser_usec 10000\nsystem_usec 2000\n',
        'memory.peak': b'345678\n', 'pids.peak': b'7\n'}
    trace = []
    def kernel(name, maximum, **kwargs):
        trace.append(name)
        if isinstance(source[name], Exception): raise source[name]
        return source[name]
    effect._capacity_kernel = kernel
    return effect, source, trace


def test_reads_actual_counter_names_and_retains_bound_sources(tmp_path, monkeypatch):
    effect, source, trace = fixture(tmp_path, monkeypatch)
    result = effect._carrier_usage()
    assert result == dict(carrier_cpu_ns=12000000, carrier_memory_peak_bytes=345678,
        carrier_pids_peak=7)
    assert trace == ['/proc/self/cgroup', 'cpu.stat', 'memory.peak', 'pids.peak', '/proc/self/cgroup']
    assert effect._carrier_usage_evidence['sources']['pids.peak'] == source['pids.peak']
    assert effect._carrier_usage_evidence['binding'] == effect._admission_detail['carrier']


@pytest.mark.parametrize('value', [FileNotFoundError('unsupported'), b'max\n', b'-1\n', b'7', b'7\n8\n'])
def test_missing_or_invalid_peak_never_uses_current_or_limit(tmp_path, monkeypatch, value):
    effect, source, trace = fixture(tmp_path, monkeypatch)
    source['pids.peak'] = value
    with pytest.raises((FileNotFoundError, d.DispatchError)):
        effect._carrier_usage()
    assert not hasattr(effect, '_carrier_usage_evidence')
    assert all(name not in trace for name in ('pids.current', 'pids.max'))


@pytest.mark.parametrize('value', [b'usage_usec 2\n', b'usage_usec 1\nusage_usec 2\n',
    b'usage_usec infinity\n', b'garbage\n'])
def test_invalid_cpu_does_not_publish_partial_usage(tmp_path, monkeypatch, value):
    effect, source, trace = fixture(tmp_path, monkeypatch)
    source['cpu.stat'] = value
    with pytest.raises(d.DispatchError): effect._carrier_usage()
    assert 'memory.peak' not in trace and not hasattr(effect, '_carrier_usage_evidence')


def test_bound_identity_and_membership_must_match(tmp_path, monkeypatch):
    effect, source, _ = fixture(tmp_path, monkeypatch)
    effect._admission_detail['carrier']['inode'] += 1
    with pytest.raises(d.DispatchError, match='CARRIER_IDENTITY'): effect._carrier_usage()
    assert not hasattr(effect, '_carrier_usage_evidence')
    effect._admission_detail['carrier']['inode'] -= 1
    source['/proc/self/cgroup'] = b'0::/different.service\n'
    with pytest.raises(d.DispatchError, match='MEMBERSHIP'): effect._carrier_usage()


def test_late_observation_retains_no_complete_fact(tmp_path, monkeypatch):
    effect, _, _ = fixture(tmp_path, monkeypatch)
    expired = False
    def now():
        nonlocal expired
        expired = True
        return dict(boot_id='test', boottime_ns=100, monotonic_ns=90)
    def guard():
        if expired: raise d.DispatchError('ORIGINAL_DEADLINE')
    effect.now, effect._effect_guard = now, guard
    with pytest.raises(d.DispatchError, match='ORIGINAL_DEADLINE'): effect._carrier_usage()
    assert not hasattr(effect, '_carrier_usage_evidence')
