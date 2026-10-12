"""Retained maintenance source and transport bounds after host scan removal."""
from __future__ import annotations

import base64
import io
import json
import random
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import zlib

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only journal scan work", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g
from test_e3_q2_journal_diagnostic_resume import source_git

@pytest.mark.parametrize("name", ["q2_journal_growth.py", "q2_journal_growth_guest.py"])
@pytest.mark.parametrize("extra", [0, 1])
def test_source_admission_196608_boundary_only_for_maintenance_sources(source_git, monkeypatch, name, extra):
    original_read, original_run = h.local.stable_read, h.subprocess.run
    raw = b"#" + b"x" * (196607 + extra)
    def read(fd, cap, check):
        original, info = original_read(fd, cap, check)
        return (raw if original == Path(h.__file__).with_name(name).read_bytes() else original), info
    def run(argv, **kw):
        result = original_run(argv, **kw)
        if argv[-2:] == ["show", source_git.head + ":tests/e3_host/" + name]:
            result.stdout = raw
        return result
    monkeypatch.setattr(h.local, "stable_read", read)
    monkeypatch.setattr(h.subprocess, "run", run)
    if extra:
        with pytest.raises(g.r.ObservationError, match="SOURCE_LIMIT"): h.growth_sources(source_git.head)
    else:
        assert len(h.growth_sources(source_git.head)[name]) == 196608


@pytest.mark.parametrize("key,cap", [("guest", 196608), ("reader", 131072), ("input", 131072)])
@pytest.mark.parametrize("extra", [0, 1])
def test_bundle_and_actual_loader_apply_only_declared_source_limits(key, cap, extra):
    # Harmless synthetic code; the actual loader runs only in an unprivileged subprocess.
    entries = dict(reader=b"VALUE=1\n", guest=b"def entry(raw):\n return 0\n", input=b"{}")
    entries[key] += b" " * (cap + extra - len(entries[key]))
    packed = h.canonical(dict(encoding="utf8",**{k:v.decode() for k,v in entries.items()}))
    zipped = zlib.compress(packed, 9)
    result = subprocess.run([sys.executable, "-I", "-B", "-c", h.GUEST_LOADER,
        base64.b64encode(zipped).decode(), h.digest(zipped)], capture_output=True, timeout=5)
    assert (result.returncode == 0) is (not extra)
    if extra: assert (b"INPUT_BOUND" if key == "input" else b"SOURCE_BOUND") in result.stderr
    sources = {"q2_core_capacity_reader.py": entries["reader"], "q2_journal_growth_guest.py": entries["guest"]}
    # The bundle producer canonicalizes descriptor input; cover its exact byte boundary too.
    descriptor = {"padding": "x" * (cap + extra - len(h.canonical({"padding": ""})))} if key == "input" else {}
    if extra:
        with pytest.raises(g.r.ObservationError, match="BUNDLE_INPUT"): h.source_bundle(sources, descriptor)
    else:
        h.source_bundle(sources, descriptor)


def test_compressed_bundle_and_argv_limits_remain_independent(monkeypatch):
    # Deterministic high-entropy synthetic input; each source is within its own cap.
    raw = bytes(random.Random(42).choices(range(32,127),k=196608))
    sources = {"q2_core_capacity_reader.py": b"#reader", "q2_journal_growth_guest.py": raw}
    with pytest.raises(g.r.ObservationError, match="BUNDLE_BOUND"):
        h.source_bundle(sources, {})
    zipped = b"x" * 98305
    with pytest.raises(g.r.ObservationError, match="BUNDLE_BOUND"):
        h.source_bundle(sources, {})
    monkeypatch.setattr(h, "source_bundle", lambda *a: ("x" * 131072, "a" * 64))
    with pytest.raises(g.r.ObservationError, match="ARGV_LIMIT"):
        h.remote_argv("/synthetic/anchor", sources, {})
