"""Offline failure propagation; no sudo, proc scan, TTY or maintenance action."""
from __future__ import annotations

import copy
import json
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only journal writer diagnostics", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g
from test_e3_q2_journal_host_read import KEYS, observer  # Reuse isolated observer fixture.


PRIVATE_STDERR = b"synthetic-private-diagnostic-never-publish"
CHILD = dict(reason="GROWTH_WRITERS_UNKNOWN", errno=13)


def failure(command, **changes):
    return dict(schema="lhq-journal-writer-result/v1", request=command.request,
                complete=False, **CHILD) | changes


def response(observer, monkeypatch, encode, *, timeout=False):
    def collect(command):
        raw = encode(command)
        command.output["stdout"].extend(raw)
        command.output["stderr"].extend(PRIVATE_STDERR)
        command.process.poll = lambda: 3
        if timeout:
            raise g.r.ObservationError("GROWTH_WRITER_DEADLINE")
        return dict(returncode=3, eof=dict(stdout=True, stderr=True),
                    stdout=raw, stderr=PRIVATE_STDERR)
    monkeypatch.setattr(observer.Command, "collect", collect)


def stopped_once(observer):
    assert len(observer.calls) == 1
    assert observer.value.failed and observer.value.reports == []
    with pytest.raises(g.r.ObservationError, match="^GROWTH_WRITER_NO_RETRY$"):
        observer.value.observe(KEYS, lambda: None)
    assert len(observer.calls) == 1


def safe_diagnostic(error):
    text = json.dumps(error.diagnostic, sort_keys=True)
    assert PRIVATE_STDERR.decode() not in text
    assert PRIVATE_STDERR.decode() not in str(error)
    assert error.diagnostic["streams"]["stderr"] == dict(
        bytes=len(PRIVATE_STDERR), sha256=h.digest(PRIVATE_STDERR))


@pytest.mark.parametrize("errno", [None, 0, 13])
def test_parent_preserves_valid_child_reason_and_errno(observer, monkeypatch, errno):
    response(observer, monkeypatch, lambda command: h.canonical(failure(command, errno=errno)))
    with pytest.raises(g.r.ObservationError, match="^GROWTH_WRITERS_UNKNOWN$") as caught:
        observer.value.observe(KEYS, lambda: None)
    assert getattr(caught.value, "errno", None) == errno
    assert caught.value.diagnostic["child_failure"] == dict(reason=CHILD["reason"], errno=errno)
    safe_diagnostic(caught.value)
    stopped_once(observer)


def test_terminal_failure_retains_already_received_child_failure(observer, monkeypatch):
    response(observer, monkeypatch, lambda command: h.canonical(failure(command)))
    calls = []
    def terminal(expected=None):
        calls.append(expected)
        if len(calls) == 2:
            raise g.r.ObservationError("GROWTH_TERMINAL_FOREGROUND")
        return observer.value.terminal
    monkeypatch.setattr(h, "terminal_binding", terminal)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_TERMINAL_FOREGROUND$") as caught:
        observer.value.observe(KEYS, lambda: None)
    assert caught.value.diagnostic["child_failure"] == CHILD
    safe_diagnostic(caught.value)
    stopped_once(observer)


def malformed(command, case):
    if case == "empty":
        return b""
    if case == "json":
        return b"{not-json"
    if case == "non_ascii":
        return b"\xff"
    value = failure(command)
    if case == "schema":
        value["schema"] = "other"
    elif case == "request":
        value["request"] = copy.deepcopy(command.request)
        value["request"]["nonce"] = "b" * 64
    elif case == "complete":
        value["complete"] = True
    elif case == "extra":
        value["unapproved"] = "synthetic-private-field"
    elif case == "reason":
        value["reason"] = "private reason /synthetic/path"
    elif case == "errno":
        value["errno"] = True
    elif case == "duplicate":
        return h.canonical(value)[:-2] + b',"errno":13}\n'
    else:
        raise AssertionError(case)
    return h.canonical(value)


@pytest.mark.parametrize("case", ["empty", "json", "non_ascii", "schema", "request",
                                 "complete", "extra", "reason", "errno", "duplicate"])
def test_nonzero_invalid_report_has_one_safe_failure_code(observer, monkeypatch, case):
    response(observer, monkeypatch, lambda command: malformed(command, case))
    with pytest.raises(g.r.ObservationError, match="^GROWTH_WRITER_FAILURE_REPORT$") as caught:
        observer.value.observe(KEYS, lambda: None)
    assert not caught.value.diagnostic.get("child_failure")
    safe_diagnostic(caught.value)
    assert "private reason" not in json.dumps(caught.value.diagnostic)
    assert "synthetic-private-field" not in json.dumps(caught.value.diagnostic)
    stopped_once(observer)


def test_deadline_retains_complete_captured_child_failure(observer, monkeypatch):
    response(observer, monkeypatch, lambda command: h.canonical(failure(command)), timeout=True)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_WRITER_DEADLINE$") as caught:
        observer.value.observe(KEYS, lambda: None)
    assert caught.value.diagnostic["child_failure"] == CHILD
    safe_diagnostic(caught.value)
    stopped_once(observer)


@pytest.mark.parametrize("case", ["json", "request", "extra", "reason"])
def test_deadline_never_promotes_partial_or_invalid_capture(observer, monkeypatch, case):
    response(observer, monkeypatch, lambda command: malformed(command, case), timeout=True)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_WRITER_DEADLINE$") as caught:
        observer.value.observe(KEYS, lambda: None)
    assert not caught.value.diagnostic.get("child_failure")
    safe_diagnostic(caught.value)
    stopped_once(observer)


@pytest.mark.parametrize("raw", [b"already-read-failure-body\n", b""])
def test_command_keeps_read_bytes_or_eof_before_deadline_rejection(monkeypatch, raw):
    # Construct capture state directly: no Popen, real fd, proc read or clock.
    class Stream:
        closed = False
        def fileno(self): return 9191
        def close(self): self.closed = True
    stdout, stderr = Stream(), Stream()
    class Selector:
        present, closed = True, False
        def get_map(self): return {9191: True} if self.present else {}
        def select(self, _):
            return [(SimpleNamespace(data="stdout", fileobj=stdout), 1)]
        def unregister(self, _): self.present = False
        def close(self): self.closed = True
    calls = []
    def guard():
        calls.append(None)
        if len(calls) >= 2:
            raise g.r.ObservationError("GROWTH_WRITER_DEADLINE")
    def forbidden(*args, **kwargs):
        raise AssertionError("capture must not signal a process")
    command = object.__new__(h.Command)
    command.check, command.selector = guard, Selector()
    command.process = SimpleNamespace(stdout=stdout, stderr=stderr, poll=lambda: None,
                                      kill=forbidden, terminate=forbidden)
    command.caps = dict(stdout=1024, stderr=1024)
    command.output = dict(stdout=bytearray(), stderr=bytearray())
    command.eof = dict(stdout=False, stderr=False)
    reads = []
    def read(fd, limit):
        reads.append((fd, limit))
        assert len(reads) == 1
        return raw
    monkeypatch.setattr(h.os, "read", read)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_WRITER_DEADLINE$"):
        command.collect()
    assert bytes(command.output["stdout"]) == raw
    assert command.eof["stdout"] is (not raw)
    assert command.selector.closed and stdout.closed and stderr.closed
    assert len(reads) == 1
