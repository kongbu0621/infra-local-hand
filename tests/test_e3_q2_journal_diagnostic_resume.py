"""Selected journal source fixture; no historical approval chain is required."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only journal source admission", allow_module_level=True)

from e3_host import q2_journal_growth as h


@pytest.fixture
def source_git(monkeypatch):
    root = Path(h.__file__).resolve().parents[2]
    state = SimpleNamespace(head="d" * 40, changed_doc=None, calls=[])

    def run(argv, **kwargs):
        assert argv[:5] == ["git", "-c", "maintenance.auto=false", "-c", "gc.auto=0"]
        args = argv[5:]
        state.calls.append(args)
        code, raw = 0, b""
        if args[0] == "show":
            _, path = args[1].split(":", 1)
            raw = (root / path).read_bytes()
            if path == state.changed_doc:
                raw += b"\nchanged source\n"
        else:
            raise AssertionError(args)
        return SimpleNamespace(returncode=code, stdout=raw, stderr=b"")

    monkeypatch.setattr(h.subprocess, "run", run)
    return state
