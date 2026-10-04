"""Late persistent I/O must stop under the original paired deadlines."""
import importlib.util
import os
from pathlib import Path
import sys

import pytest


if not sys.platform.startswith('linux'):
    pytest.skip('Linux held-directory persistence', allow_module_level=True)


spec = importlib.util.spec_from_file_location('_core_persist_guard_test',
    Path(__file__).parent / 'e3_host/q2_core_delivery_dispatcher.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def test_session_persist_stops_after_late_file_fsync(tmp_path, monkeypatch):
    effect = object.__new__(d.FieldEffects)
    effect._persistence_ready = True
    effect.context = {'guest_deadlines': {'boot_id': 'test',
        'boottime_deadline_ns': 1000, 'monotonic_deadline_ns': 1000}}
    effect._persistence_path = lambda *_: str(tmp_path / 'session.json')
    expired = False
    calls = []
    effect.now = lambda: {'boot_id': 'test', 'boottime_ns': 1001 if expired else 900,
        'monotonic_ns': 1001 if expired else 900}
    real_fsync = os.fsync

    def late_fsync(fd):
        nonlocal expired
        real_fsync(fd)
        calls.append(fd)
        expired = True

    monkeypatch.setattr(d.os, 'fsync', late_fsync)
    with pytest.raises(d.DispatchError, match='DEADLINE'):
        effect.persist('carrier', 'carrier/session.json', b'{}\n', 0o600)
    # Keep the partial file; a late effect cannot proceed to the parent fsync.
    assert (tmp_path / 'session.json').read_bytes() == b'{}\n'
    assert len(calls) == 1
