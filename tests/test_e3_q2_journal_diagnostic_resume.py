"""DR1 source admission only; no window, sudo, proc scan or maintenance."""
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
    state = SimpleNamespace(head="d" * 40, rejected_edge=None, changed_doc=None,
                            calls=[])

    def run(argv, **kwargs):
        assert argv[:5] == ["git", "-c", "maintenance.auto=false", "-c", "gc.auto=0"]
        args = argv[5:]
        state.calls.append(args)
        code, raw = 0, b""
        if args == ["rev-parse", "HEAD"]:
            raw = (state.head + "\n").encode()
        elif args == ["diff", "--quiet", "HEAD"]:
            pass
        elif args[:2] == ["merge-base", "--is-ancestor"]:
            code = int(tuple(args[2:]) == state.rejected_edge)
        elif args[0] == "show":
            _, path = args[1].split(":", 1)
            raw = (root / path).read_bytes()
            if path == state.changed_doc:
                raw += b"\nchanged approval\n"
        else:
            raise AssertionError(args)
        return SimpleNamespace(returncode=code, stdout=raw, stderr=b"")

    monkeypatch.setattr(h.subprocess, "run", run)
    return state


def test_candidate_requires_all_closures_and_keeps_original_source_caps(source_git):
    sources = h.growth_sources(source_git.head)
    for earlier, later in ((h.C, source_git.head), (h.TERM_C, source_git.head),
                           (h.DR_A, h.DR_C), (h.DR_C, source_git.head)):
        assert ["merge-base", "--is-ancestor", earlier, later] in source_git.calls
    assert len(sources) == 12
    assert all(len(sources[name]) <= 65536 for name in
               ("q2_journal_growth.py", "q2_journal_growth_guest.py"))


@pytest.mark.parametrize("edge", ["approval_to_closure", "closure_to_candidate"])
def test_unrelated_candidate_or_closure_is_refused_before_source_reads(source_git, edge):
    source_git.rejected_edge = ((h.DR_A, h.DR_C) if edge == "approval_to_closure"
                                else (h.DR_C, source_git.head))
    with pytest.raises(h.prior.r.ObservationError, match="^GROWTH_SOURCE$"):
        h.growth_sources(source_git.head)
    assert not any(call[0] == "show" for call in source_git.calls)


def test_bookkeeping_closure_cannot_be_execution_candidate(source_git):
    source_git.head = h.DR_C
    with pytest.raises(h.prior.r.ObservationError, match="^GROWTH_RESUME_D$"):
        h.growth_sources(source_git.head)
    assert not any(call[0] == "show" for call in source_git.calls)


@pytest.mark.parametrize("name", ["REQUIREMENTS.md", "ARCHITECTURE.md", "IMPLEMENTATION_PLAN.md"])
def test_changed_resume_approval_is_refused_before_implementation_reads(source_git, name):
    source_git.changed_doc = "docs/a2-execution/q2-core-journal-diagnostic-resume/" + name
    with pytest.raises(h.prior.r.ObservationError, match="^GROWTH_RESUME_A_CHANGED$"):
        h.growth_sources(source_git.head)
    assert not any(call[0] == "show" and ":tests/" in call[1] for call in source_git.calls)
