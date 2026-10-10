"""Bounded usage diagnostics with synthetic proc reads; no field operations."""
import errno
import json
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux coordinator resource observations", allow_module_level=True)

from e3_host import q2_journal_growth as h
from command_usage_fixture import stat_record


@pytest.fixture
def model(monkeypatch):
    calls = []
    children = []
    own = SimpleNamespace(ru_utime=1, ru_stime=2, ru_maxrss=2048)
    exited = [SimpleNamespace(ru_utime=4, ru_stime=5, ru_maxrss=3072)]
    records = {}

    def usage(kind):
        calls.append(("usage", kind))
        if kind == h.resource.RUSAGE_SELF:
            return own
        assert kind == h.resource.RUSAGE_CHILDREN
        return exited.pop(0) if len(exited) > 1 else exited[0]

    def read(pid, name, cap):
        calls.append(("stat", pid, name, cap))
        value = records.get(pid, stat_record(pid))
        if isinstance(value, BaseException):
            raise value
        return value

    def add(pid, *, polls=(None,), identity=True, vm=False):
        returns = list(polls)

        def poll():
            calls.append(("poll", pid))
            return returns.pop(0) if len(returns) > 1 else returns[0]

        child = SimpleNamespace(is_vm=vm,
            process=SimpleNamespace(pid=pid, poll=poll))
        if identity is True:
            child.identity = dict(pid=pid, argv_sha256="a" * 64, starttime=100 + pid)
        elif identity is not False:
            child.identity = identity
        children.append(child)
        return child

    monkeypatch.setattr(h, "COMMANDS", children)
    monkeypatch.setattr(h.custody, "ACTIVE", [])
    monkeypatch.setattr(h.resource, "getrusage", usage)
    monkeypatch.setattr(h.custody, "proc", read)
    monkeypatch.setattr(h, "proc_bytes", lambda *_: pytest.fail("no separate status read"))
    return SimpleNamespace(calls=calls, children=children, own=own,
        exited=exited, records=records, add=add)


def failed_usage():
    with pytest.raises(h.prior.r.ObservationError,
                       match="^GROWTH_USAGE_UNKNOWN$") as raised:
        h.management_usage()
    return raised.value


@pytest.mark.parametrize("stage", ["stat_read", "stat_parse", "process_identity"])
def test_live_failure_keeps_exact_stage_and_existing_read_poll_count(model, stage):
    model.add(101)
    if stage == "stat_read":
        model.records[101] = OSError(errno.EACCES, "private stat detail")
        expected_type, expected_errno, expected_reason = "PermissionError", errno.EACCES, None
    elif stage == "stat_parse":
        model.records[101] = b"private-process-name\n"
        expected_type, expected_errno, expected_reason = "ObservationError", None, "GROWTH_USAGE_STAT"
    else:
        model.records[101] = stat_record(101, start=202)
        expected_type, expected_errno, expected_reason = "ObservationError", None, "GROWTH_USAGE_IDENTITY"
    error = failed_usage()
    detail = error.diagnostic["failed_children"][0].pop("error")
    assert detail["error_type"] == expected_type and detail["traceback"]
    assert error.diagnostic == dict(operation="management_usage",
        stage="live_child_observation", complete=False, live_children=1,
        failed_children=[dict(pid=101, stage=stage, error_type=expected_type,
            errno=expected_errno, reason=expected_reason,
            identity=dict(argv_sha256="a" * 64, starttime=201))])
    expected = [("poll", 101), ("usage", h.resource.RUSAGE_SELF),
        ("usage", h.resource.RUSAGE_CHILDREN), ("stat", 101, "stat", 4096)]
    assert model.calls == expected + [("poll", 101)]


@pytest.mark.parametrize("problem", [
    OSError(errno.EIO, "secret-argv /private/key", "/private/status"),
    ValueError("secret-argv /private/key"),
    RuntimeError("GROWTH_INVALID secret-argv /private/key"),
])
def test_private_failure_preserves_exception_without_reading_raw_command(model, problem):
    child = model.add(101)
    child.identity.update(argv=["secret-argv", "/private/key"], arbitrary="private data")
    child.process.args = ["secret-argv", "/private/key"]
    model.records[101] = problem
    detail = failed_usage().diagnostic
    serialized = json.dumps(detail)
    assert detail["failed_children"][0]["error"]["message"] == str(problem)
    assert "\"argv\"" not in serialized
    assert "arbitrary" not in serialized and "private data" not in serialized
    failed = detail["failed_children"][0]
    assert failed["reason"] is None
    assert failed["error_type"] == type(problem).__name__
    assert failed["errno"] == getattr(problem, "errno", None)


@pytest.mark.parametrize("identity,expected", [
    (False, dict(argv_sha256=None, starttime=None)),
    (None, dict(argv_sha256=None, starttime=None)),
    ({}, dict(argv_sha256=None, starttime=None)),
    (dict(argv_sha256="raw command", starttime=True), dict(argv_sha256=None, starttime=None)),
    (dict(argv_sha256="a" * 63, starttime=-1), dict(argv_sha256=None, starttime=None)),
    (dict(argv_sha256="f" * 64, starttime=9), dict(argv_sha256="f" * 64, starttime=9)),
])
def test_missing_or_invalid_identity_never_breaks_or_expands_diagnostic(model, identity, expected):
    model.add(101, identity=identity)
    model.records[101] = ValueError("unavailable")
    assert failed_usage().diagnostic["failed_children"][0]["identity"] == expected


def test_eight_failed_children_are_all_reported_with_no_additional_reads(model):
    for pid in range(101, 109):
        model.add(pid)
        model.records[pid] = OSError(errno.ENOENT, "unavailable")
    detail = failed_usage().diagnostic
    assert detail["live_children"] == 8
    assert [row["pid"] for row in detail["failed_children"]] == list(range(101, 109))
    assert all(row["stage"] == "stat_read" for row in detail["failed_children"])
    assert len([call for call in model.calls if call[0] == "stat"]) == 8
    assert len([call for call in model.calls if call[0] == "poll"]) == 16


def test_existing_child_limit_rejects_seventeenth_child_before_resource_or_proc_reads(model):
    for pid in range(101, 118):
        model.add(pid)
    with pytest.raises(h.prior.r.ObservationError, match="^GROWTH_CHILD_BUDGET$"):
        h.management_usage()
    assert model.calls == [("poll", pid) for pid in range(101, 118)]


def test_custody_counts_toward_existing_limit_and_diagnostic(model, monkeypatch):
    model.add(101)
    model.records[101] = OSError(errno.EIO, "unavailable")
    calls = []

    def custody_usage():
        calls.append("custody")
        return 0.5, 1024

    monkeypatch.setattr(h.custody, "ACTIVE", [SimpleNamespace(usage=custody_usage)])
    detail = failed_usage().diagnostic
    assert detail["live_children"] == 2 and len(detail["failed_children"]) == 1
    assert calls == ["custody"]


def test_failed_observation_then_confirmed_exit_retains_reaped_cpu_accounting(model):
    model.add(101, polls=(None, 0))
    model.records[101] = OSError(errno.ENOENT, "already exited")
    model.exited.append(SimpleNamespace(ru_utime=6, ru_stime=6, ru_maxrss=4096))
    assert h.management_usage() == dict(cpu_seconds=15,
        rss_upper_observation_bytes=2 * h.MIB, complete=True, live_children=1,
        vm_excluded=True, guest_aggregate="UNKNOWN")
    assert model.calls == [("poll", 101), ("usage", h.resource.RUSAGE_SELF),
        ("usage", h.resource.RUSAGE_CHILDREN), ("stat", 101, "stat", 4096),
        ("poll", 101), ("usage", h.resource.RUSAGE_CHILDREN)]


def test_identity_mismatch_is_not_excused_by_a_later_exit(model):
    model.add(101, polls=(None, 0))
    model.records[101] = stat_record(101, start=999)
    error = failed_usage()
    assert error.diagnostic['failed_children'][0]['reason'] == 'GROWTH_USAGE_IDENTITY'


def test_known_budget_excess_retains_precedence_over_incomplete_usage(model):
    model.add(101)
    model.records[101] = OSError(errno.EIO, "unavailable")
    model.own.ru_utime = 241
    with pytest.raises(h.prior.r.ObservationError,
                       match="^GROWTH_MANAGEMENT_BUDGET$") as raised:
        h.management_usage()
    assert raised.value.diagnostic["operation"] == "management_budget"
    assert raised.value.diagnostic["cpu"]["exceeded"] is True
    assert raised.value.diagnostic["components"]["live_rss_complete"] is False


def test_usage_sample_propagates_unknown_without_replacing_last_valid_sample(model):
    model.add(101)
    model.records[101] = ValueError("unavailable")
    previous = dict(cpu_nanoseconds=17, rss_peak_bytes=19)
    sampler = h.Usage(previous)
    with pytest.raises(h.prior.r.ObservationError, match="^GROWTH_USAGE_UNKNOWN$") as raised:
        sampler.sample()
    assert raised.value.diagnostic["failed_children"][0]["pid"] == 101
    assert sampler.last == previous == dict(cpu_nanoseconds=17, rss_peak_bytes=19)
    assert [call for call in model.calls if call[0] == "usage"] == [
        ("usage", h.resource.RUSAGE_SELF), ("usage", h.resource.RUSAGE_CHILDREN)]


def test_success_vm_exclusion_and_finished_child_behavior_are_unchanged(model):
    model.add(101)
    model.add(102, vm=True)
    model.add(103, polls=(0,))
    assert h.management_usage() == dict(cpu_seconds=12.25,
        rss_upper_observation_bytes=3 * h.MIB, complete=True, live_children=1,
        vm_excluded=True, guest_aggregate="UNKNOWN")
    assert model.calls == [("poll", 101), ("poll", 103),
        ("usage", h.resource.RUSAGE_SELF), ("usage", h.resource.RUSAGE_CHILDREN),
        ("stat", 101, "stat", 4096)]


def test_main_json_boundary_retains_usage_diagnostic_before_any_field_effect(model, monkeypatch, capsys):
    model.add(101)
    model.records[101] = OSError(errno.EACCES, "private stat detail")
    closed = []
    monkeypatch.setattr(h.sys, "argv", ["growth", "--frame", "synthetic-frame",
        "--plan-archive", "synthetic-plan", "--archives-dir", "synthetic-archives",
        "--expected-commit", "d" * 40])
    monkeypatch.setattr(h.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(h.resource, "getrlimit", lambda _key: (-1, -1))
    monkeypatch.setattr(h.resource, "setrlimit", lambda *_args: None)
    monkeypatch.setattr(h.prior, "Inputs", lambda: SimpleNamespace(close=lambda: closed.append(True)))
    monkeypatch.setattr(h.history.c, "VM_ADOPTION_CLOSURE", dict(commit="c" * 40))
    monkeypatch.setattr(h.history.c, "HOST_FD_CLOSURE", dict(commit="c" * 40))
    monkeypatch.setattr(h, "growth_sources", lambda _commit: h.management_usage())

    def no_field(*_args, **_kwargs):
        pytest.fail("diagnostic propagation test must not perform field effects")

    monkeypatch.setattr(h, "freeze_growth_inputs", no_field)
    monkeypatch.setattr(h, "GrowthAnchor", no_field)
    monkeypatch.setattr(h.subprocess, "Popen", no_field)
    assert h.main() == 3
    captured = capsys.readouterr()
    assert not captured.err
    value = json.loads(captured.out)
    assert value["state"] == "BLOCKED" and value["reason"] == "GROWTH_USAGE_UNKNOWN"
    assert value["marker_created"] is False and value["ssh_requests"] == 0
    detail = value["diagnostic"]
    assert detail["traceback"] and detail["resource_level"] == 2
    child_error = detail["failed_children"][0].pop("error")
    assert child_error["message"] == "[Errno 13] private stat detail"
    assert {key:detail[key] for key in ("operation","stage","complete","live_children","failed_children")} == dict(operation="management_usage",
        stage="live_child_observation", complete=False, live_children=1,
        failed_children=[dict(pid=101, stage="stat_read", error_type="PermissionError",
            errno=errno.EACCES, reason=None,
            identity=dict(argv_sha256="a" * 64, starttime=201))])
    assert closed == [True]
