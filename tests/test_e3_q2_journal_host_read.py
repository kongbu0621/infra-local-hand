"""R2 offline adversaries. No sudo, original VM, marker or maintenance window."""
from __future__ import annotations

import ast
import base64
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only journal host-read contract", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g
from e3_host import q2_host_kernel_facts as k

BOOT = "11111111-2222-3333-4444-555555555555"
KEYS = {name: (42, index) for index, name in enumerate(
    ("system", "quota", "journal", "evidence", "seed"), 1)}
NOW = 100_000_000_000


def test_partial_stderr_is_bounded_and_never_killed():
    command = h.Command([sys.executable, "-I", "-B", "-c", "import sys; sys.stderr.write('x'*4097)"],
                        lambda: None, limit=65536, stderr_limit=4096)
    try:
        with pytest.raises(g.r.ObservationError, match="STREAM_LIMIT"):
            command.collect()
        assert len(command.output["stderr"]) == 4097
    finally:
        command.process.wait(timeout=5)


def test_host_reader_uses_qualified_fixed_module_not_guest_fallback(monkeypatch):
    calls, details = [], {}
    def read(kind, check, report):
        calls.append(kind); report["status"] = "OBSERVED"
        return (BOOT + "\n").encode()
    monkeypatch.setattr(k, "read_fact", read)
    monkeypatch.setattr(g, "read_kernel", lambda *args: pytest.fail("guest fallback"))
    assert g.host_boot_id(lambda: None, details) == BOOT
    assert calls == ["boot"] and details["status"] == "OBSERVED"


def test_host_reader_retains_sanitized_qualification_failure(monkeypatch):
    def denied(*args):
        raise k.KernelFactError("HOST_LOCAL_KERNEL_SUBMOUNT", "mount_id", "boot", errno=13)
    monkeypatch.setattr(k, "read_fact", denied)
    with pytest.raises(g.r.ObservationError, match="HOST_KERNEL_FACT") as caught:
        g.host_boot_id(lambda: None)
    assert caught.value.diagnostic == dict(reason="HOST_LOCAL_KERNEL_SUBMOUNT", operation="mount_id", target="boot", errno=13)
