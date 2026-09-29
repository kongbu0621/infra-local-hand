"""No live cgroup, account, compiler or helper invocation in these tests."""
from __future__ import annotations

import importlib.util
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

if sys.platform != "linux":
    pytest.skip("the fixture driver is intentionally Linux-only", allow_module_level=True)

_SPEC = importlib.util.spec_from_file_location("h07_fixture_admission", Path(__file__).with_name("run_fixture.py"))
assert _SPEC and _SPEC.loader
driver = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(driver)


def test_dispatch_source_mismatch_stops_before_setup(monkeypatch, tmp_path):
    candidate = "a" * 40
    monkeypatch.setattr(driver, "git", lambda *args: (candidate + "\n").encode())
    touched = []
    monkeypatch.setattr(driver.Fixture, "initialize_output", lambda self: touched.append("setup"))
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    assert driver.main(["--expected-commit", candidate, "--round", "2"]) == 4
    assert touched == []


def test_dirty_source_stops_before_environment_and_setup(monkeypatch):
    candidate = "a" * 40
    def git(_repo, *args):
        return (candidate + "\n").encode() if args[0] == "rev-parse" else b" M AGENTS.md\n"
    monkeypatch.setattr(driver, "git", git)
    monkeypatch.setenv("GITHUB_SHA", candidate)
    def forbidden(*_args, **_kwargs):
        pytest.fail("dirty source must not reach environment admission/setup")
    monkeypatch.setattr(driver, "admission", forbidden)
    monkeypatch.setattr(driver.Fixture, "initialize_output", forbidden)
    assert driver.main(["--expected-commit", candidate, "--round", "2"]) == 4


@pytest.mark.parametrize("replaced_path", [
    "tests/e3_host/spikes/q2_cgroup_fence/run_fixture.py",
    "docs/a2-execution/q2-h07-r1-continuation/REQUIREMENTS.md",
    "docs/governance/Q2_H07_R1_CONTINUATION_OWNER_DECISION.md",
    "docs/governance/Q2_H07_R1_CONTINUATION_BASELINE.md",
    "docs/a2-execution/evidence/q2-h07-cgroup-fence-spike/round-1-verification.json",
    "docs/a2-execution/evidence/q2-h07-cgroup-fence-spike/round-1-repair-ci.json",
])
def test_worktree_bytes_are_compared_to_the_exact_commit(monkeypatch, tmp_path, replaced_path):
    import continuation
    candidate = "a" * 40
    paths = [driver.SCOPE_DIR + "/run_fixture.py", driver.WORKFLOW, "AGENTS.md",
             "docs/governance/Q2_H07_CGROUP_FENCE_SPIKE_OWNER_DECISION.md"]
    paths += ["docs/a2-execution/q2-h07-cgroup-fence-spike/" + name
              for name in driver.PINNED_DOCUMENTS]
    paths += sorted(continuation.REQUIRED_SOURCE_PATHS)
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"committed bytes\n")
    (tmp_path / replaced_path).write_bytes(b"uncommitted replacement\n")
    def git(_repo, *args):
        if args[0] == "rev-parse":
            return (candidate + "\n").encode()
        if args[0] == "ls-tree":
            return (driver.SCOPE_DIR + "/run_fixture.py\n").encode()
        if args[0] == "show":
            return b"committed bytes\n"
        return b""
    monkeypatch.setattr(driver, "git", git)
    with pytest.raises(driver.Refusal, match="working source differs"):
        driver.source_identity(tmp_path, candidate, {"GITHUB_SHA": candidate})


def test_current_source_closure_and_historical_continuation_integrate(monkeypatch):
    """Read actual repository bytes while replacing every Git process call."""
    import continuation
    repo = Path(__file__).resolve().parents[4]
    candidate = "d" * 40
    paths = sorted(str(path.relative_to(repo)) for path in (repo / driver.SCOPE_DIR).iterdir()
                   if path.is_file() and path.suffix in (".py", ".c"))
    ancestors = []
    def git(_repo, *args):
        assert _repo == repo
        if args[0] == "rev-parse":
            return (candidate + "\n").encode()
        if args[0] in ("status", "ls-files"):
            return b""
        if args[0] == "merge-base":
            ancestors.append(args[2])
            return b""
        if args[0] == "ls-tree":
            return ("\n".join(paths) + "\n").encode()
        if args[0] == "show":
            commit, relative = args[1].split(":", 1)
            assert commit == candidate
            return (repo / relative).read_bytes()
        pytest.fail("unexpected Git operation: " + repr(args))
    def forbidden(*_args, **_kwargs):
        pytest.fail("source and continuation checks must not launch a process")
    monkeypatch.setattr(driver, "git", git)
    monkeypatch.setattr(driver.subprocess, "Popen", forbidden)
    source = driver.source_identity(repo, candidate, {"GITHUB_SHA": candidate})
    assert ancestors == [driver.C, continuation.CONTINUATION_C]
    assert continuation.REQUIRED_SOURCE_PATHS <= source["closure_sha256"].keys()
    assert set(paths) <= source["closure_sha256"].keys()
    for path, expected in {**continuation.PINNED_DOCUMENTS, **continuation.PINNED_FACTS}.items():
        assert source["closure_sha256"][path] == expected
    result = continuation.admit_continuation(
        repo, run={"id": "123456", "attempt": 1, "round": 2}, source=source,
        provenance={"boot_id": "11111111-1111-4111-8111-111111111111"},
        reason=continuation.ROUND2_REASON)
    assert result["used_before"] == 1 and result["limit"] == 3
    assert result["disposition"] == "ACCEPTED_HISTORICAL_UNKNOWN_ONLY"
    assert result["current_boot_sha256"] != continuation.ROUND1_BOOT_SHA256


def hosted_env(tmp_path):
    return {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REPOSITORY": "kongbu0621/infra-local-hand", "GITHUB_RUN_ATTEMPT": "1",
            "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
            "ImageOS": "ubuntu24", "GITHUB_RUN_ID": "123456", "RUNNER_TEMP": str(tmp_path),
            "LAB_REASON": "account argument and setup-evidence repair"}


def test_existing_dispatch_output_is_never_reused(monkeypatch, tmp_path):
    env = hosted_env(tmp_path)
    output = tmp_path / "q2-h07-123456-1-r2"
    output.mkdir()
    marker = output / "original-evidence"
    marker.write_bytes(b"retained")
    monkeypatch.setattr(driver.os, "geteuid", lambda: 0)
    monkeypatch.setattr(driver.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(driver, "read_small", lambda *_args, **_kwargs: 'ID=ubuntu\nVERSION_ID="24.04"')
    with pytest.raises(driver.Refusal, match="cannot be replayed"):
        driver.admission(env, 2)
    assert marker.read_bytes() == b"retained"
    assert list(output.iterdir()) == [marker]


@pytest.mark.parametrize("attempt", ["0", "2", "01"])
def test_github_rerun_never_becomes_a_fresh_lab_round(tmp_path, attempt):
    env = hosted_env(tmp_path)
    env["GITHUB_RUN_ATTEMPT"] = attempt
    with pytest.raises(driver.Refusal, match="GITHUB_RUN_ATTEMPT"):
        driver.admission(env, 2)
    assert list(tmp_path.iterdir()) == []


def test_account_creation_delegates_to_bounded_lifecycle(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    calls = []
    uid, gid = 60001, 60002
    identity = {"uid": uid, "gid": gid, "supplementary_groups": [], "home_created": False}
    def create(deadline):
        calls.append(deadline)
        fixture.account_attempted = True
        fixture.account_id = (uid, gid)
        fixture.facts["account"] = identity
    def forbidden(*_args, **_kwargs):
        pytest.fail("fixture wrapper must delegate, not launch a second account command")
    monkeypatch.setattr(fixture, "account_lifecycle", SimpleNamespace(create=create))
    monkeypatch.setattr(driver.subprocess, "Popen", forbidden)
    deadline = driver.Deadline(1)
    fixture.create_account(deadline)
    assert calls == [deadline]
    assert fixture.account_attempted is True
    assert fixture.account_id == (uid, gid)
    assert fixture.facts["account"] == identity


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_account_lifecycle_refusal_and_unknown_cleanup_are_preserved(monkeypatch, tmp_path, error_type):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    calls = []
    failure = error_type("account evidence unresolved")
    def create(deadline):
        calls.append(("create", deadline))
        fixture.account_attempted = True
        raise failure
    def cleanup(deadline):
        calls.append(("cleanup", deadline))
        return False, ["account evidence unresolved"]
    def forbidden(*_args, **_kwargs):
        pytest.fail("lifecycle refusal must not fall back to an unaudited account command")
    monkeypatch.setattr(fixture, "account_lifecycle", SimpleNamespace(create=create, cleanup=cleanup))
    monkeypatch.setattr(driver.subprocess, "Popen", forbidden)
    with pytest.raises(driver.Refusal, match="account evidence unresolved") as raised:
        fixture.create_account(driver.Deadline(1))
    assert raised.value.__cause__ is failure
    assert fixture.account_attempted is True
    assert fixture.account_id is None and fixture.facts["account"] is None
    assert fixture.cg_objects == [] and fixture.native_started is False
    result = fixture.cleanup()
    assert result["verified"] is False
    assert result["records"] == []
    assert result["residuals"] == ["account evidence unresolved"]
    assert [name for name, _ in calls] == ["create", "cleanup"]
    assert not (tmp_path / "out").exists()


class FakeClock:
    def __init__(self, monkeypatch):
        self.mono_ns, self.boot_ns = 100_000_000_000, 200_000_000_000
        monkeypatch.setattr(driver.time, "monotonic_ns", lambda: self.mono_ns)
        monkeypatch.setattr(driver.time, "clock_gettime_ns", lambda _clock: self.boot_ns)

    def advance(self, seconds, *, boot_only=False):
        nanoseconds = int(seconds * 1_000_000_000)
        if not boot_only:
            self.mono_ns += nanoseconds
        self.boot_ns += nanoseconds


def audited_process(monkeypatch, clock, events, *, rc=0, poll_rc=0,
                    wait_timeout=False, wait_delay=0, boot_only=False):
    """Script pipe readiness and process state without opening descriptors."""
    class Pipe:
        def __init__(self, number):
            self.number, self.closed = number, False
        def fileno(self):
            return self.number
        def close(self):
            self.closed = True

    stdout, stderr = Pipe(101), Pipe(102)
    script, reads, killed, starts = list(events), {}, [], []
    def wait(**kwargs):
        clock.advance(wait_delay or (kwargs["timeout"] if wait_timeout else 0), boot_only=boot_only)
        if wait_timeout:
            raise driver.subprocess.TimeoutExpired("fake-original", 1)
        return rc
    process = SimpleNamespace(pid=987654, stdout=stdout, stderr=stderr,
                              wait=wait, poll=lambda: poll_rc)
    class Selector:
        def __init__(self):
            self.keys = {}
        def register(self, stream, _events, data):
            self.keys[stream.fileno()] = SimpleNamespace(fileobj=stream, data=data)
        def get_map(self):
            return self.keys
        def unregister(self, stream):
            del self.keys[stream.fileno()]
        def select(self, timeout):
            if not script:
                clock.advance(timeout)
                return []
            kind, payload = script.pop(0)
            number = 101 if kind == "stdout" else 102
            reads[number] = payload
            clock.advance(min(timeout, 0.001))
            return [(self.keys[number], 1)]
        def close(self):
            pass
    def popen(*args, **kwargs):
        starts.append((args, kwargs))
        return process
    monkeypatch.setattr(driver.subprocess, "Popen", popen)
    monkeypatch.setattr(driver.selectors, "DefaultSelector", Selector)
    monkeypatch.setattr(driver.os, "set_blocking", lambda *_args: None)
    monkeypatch.setattr(driver.os, "read", lambda number, _limit: reads.pop(number))
    monkeypatch.setattr(driver.os, "killpg", lambda *args: killed.append(args))
    return SimpleNamespace(process=process, starts=starts, killed=killed)


def stream_receipt(data, *, eof=True, complete=True):
    return {"eof": eof, "complete": complete, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


@pytest.mark.parametrize("rc", [0, 3])
def test_audited_command_retains_both_streams_and_original_exit(monkeypatch, tmp_path, rc):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    clock = FakeClock(monkeypatch)
    fake = audited_process(monkeypatch, clock, [
        ("stdout", b"first"), ("stderr", b"warning"), ("stdout", b" second"),
        ("stderr", b""), ("stdout", b""),
    ], rc=rc)
    deadline = driver.Deadline(1)
    actual_rc, output, audit = fixture.audit_command(["never-launched"], deadline, role="useradd")
    assert (actual_rc, output) == (rc, b"first second")
    assert audit is fixture.last_command_audit
    assert audit["command_id"] == "123456-2-1" and audit["role"] == "useradd"
    assert audit["attempted"] and audit["started"] and audit["exit_observed"]
    assert audit["rc"] == rc and audit["deadline_met"]
    assert not audit["pending"] and not audit["timeout"] and not audit["termination_requested"]
    assert audit["stdout"] == stream_receipt(b"first second")
    assert audit["stderr"] == stream_receipt(b"warning")
    for suffix in ("mono_ns", "boot_ns"):
        assert audit["start_" + suffix] <= audit["end_" + suffix] <= audit["deadline_" + suffix]
        assert audit["deadline_" + suffix] == getattr(deadline, "deadline_" + suffix)
    assert bytes(fixture.diagnostics) == b"firstwarning second"
    assert not fixture.account_commands_blocked and fixture.pending_commands == []
    assert len(fake.starts) == 1 and fake.killed == []


def test_audited_spawn_failure_has_no_invented_process_or_exit(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    FakeClock(monkeypatch)
    def fail(*_args, **_kwargs):
        raise OSError("synthetic launch failure")
    monkeypatch.setattr(driver.subprocess, "Popen", fail)
    with pytest.raises(driver.CommandFailure, match="synthetic launch failure"):
        fixture.audit_command(["never-launched"], driver.Deadline(1), role="pre_create")
    audit = fixture.last_command_audit
    assert audit["attempted"] and not audit["started"]
    assert not audit["exit_observed"] and audit["rc"] is None and not audit["pending"]
    assert audit["stdout"] == stream_receipt(b"", eof=False, complete=False)
    assert audit["stderr"] == stream_receipt(b"", eof=False, complete=False)
    assert not audit["termination_requested"] and fixture.pending_commands == []
    assert fixture.account_commands_blocked


@pytest.mark.parametrize("reason", ["deadline", "blocked", "diagnostic_budget"])
def test_audited_prelaunch_refusal_records_no_attempt(monkeypatch, tmp_path, reason):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    clock = FakeClock(monkeypatch)
    deadline = driver.Deadline(1)
    if reason == "deadline":
        clock.advance(2)
    elif reason == "blocked":
        fixture.account_commands_blocked = True
    else:
        fixture.diagnostics.extend(b"x" * driver.LIMITS["diagnostic_bytes"])
    def forbidden(*_args, **_kwargs):
        pytest.fail("refused account action must not launch a process")
    monkeypatch.setattr(driver.subprocess, "Popen", forbidden)
    with pytest.raises(driver.CommandFailure):
        fixture.audit_command(["never-launched"], deadline, role="pre_cleanup", cleanup=True)
    audit = fixture.last_command_audit
    assert not audit["attempted"] and not audit["started"] and not audit["pending"]
    assert not audit["exit_observed"] and audit["rc"] is None
    assert not audit["termination_requested"]


def test_original_exit_without_both_eof_stays_unknown(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    clock = FakeClock(monkeypatch)
    fake = audited_process(monkeypatch, clock, [("stdout", b"partial"), ("stdout", b"")])
    with pytest.raises(driver.CommandFailure, match="deadline exceeded"):
        fixture.audit_command(["never-launched"], driver.Deadline(0.1), role="post_create")
    audit = fixture.last_command_audit
    assert audit["exit_observed"] and audit["rc"] == 0 and audit["pending"]
    assert audit["stdout"] == stream_receipt(b"partial")
    assert audit["stderr"] == stream_receipt(b"", eof=False, complete=False)
    assert audit["timeout"] and audit["termination_requested"]
    assert fixture.account_commands_blocked and len(fake.killed) == 1
    assert fake.process.stderr.closed  # Closing a reader is not evidence of EOF.
    with pytest.raises(driver.CommandFailure, match="no further account action"):
        fixture.audit_command(["never-launched-again"], driver.Deadline(1), role="userdel", cleanup=True)
    assert len(fake.starts) == 1
    assert audit["pending"] and not audit["stderr"]["eof"]


def test_signal_and_later_reap_do_not_rewrite_original_account_audit(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    clock = FakeClock(monkeypatch)
    fake = audited_process(monkeypatch, clock, [("stdout", b""), ("stderr", b"")],
                           poll_rc=None, wait_timeout=True)
    with pytest.raises(driver.CommandFailure, match="exit not observed within original deadline"):
        fixture.audit_command(["never-launched"], driver.Deadline(1), role="useradd")
    audit = fixture.last_command_audit
    assert audit["pending"] and not audit["exit_observed"] and audit["rc"] is None
    assert audit["termination_requested"] and len(fake.killed) == 1
    assert audit["stdout"]["eof"] and audit["stderr"]["eof"]
    assert fixture.pending_commands == [fake.process]
    snapshot = {**audit, "stdout": dict(audit["stdout"]), "stderr": dict(audit["stderr"])}
    fake.process.poll = lambda: 0
    fake.process.wait = lambda **_kwargs: 0
    def forbidden_cleanup(_deadline):
        pytest.fail("later reaping must not reopen account observation or deletion")
    monkeypatch.setattr(fixture, "account_lifecycle", SimpleNamespace(cleanup=forbidden_cleanup))
    result = fixture.cleanup()
    assert result["verified"] is False and fixture.pending_commands == []
    assert any(row["operation"] == "reap" for row in result["records"])
    assert fixture.account_commands_blocked and fixture.last_command_audit == snapshot


def test_wait_after_both_eof_rechecks_boottime_without_a_fresh_window(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    clock = FakeClock(monkeypatch)
    fake = audited_process(monkeypatch, clock, [("stdout", b""), ("stderr", b"")],
                           poll_rc=None, wait_timeout=True, wait_delay=2, boot_only=True)
    deadline = driver.Deadline(1)
    with pytest.raises(driver.CommandFailure, match="exit not observed within original deadline"):
        fixture.audit_command(["never-launched"], deadline, role="pre_create")
    audit = fixture.last_command_audit
    assert audit["end_mono_ns"] < audit["deadline_mono_ns"]
    assert audit["end_boot_ns"] > audit["deadline_boot_ns"]
    assert audit["deadline_mono_ns"] == deadline.deadline_mono_ns
    assert audit["deadline_boot_ns"] == deadline.deadline_boot_ns
    assert not audit["deadline_met"] and not audit["exit_observed"] and audit["pending"]
    assert audit["stdout"]["complete"] and audit["stderr"]["complete"]
    assert audit["timeout"] and audit["termination_requested"] and len(fake.killed) == 1
    assert fixture.account_commands_blocked


@pytest.mark.parametrize("boot_only", [False, True])
def test_late_original_exit_cannot_start_another_account_action(monkeypatch, tmp_path, boot_only):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    clock = FakeClock(monkeypatch)
    fake = audited_process(monkeypatch, clock, [("stdout", b""), ("stderr", b"")],
                           wait_delay=2, boot_only=boot_only)
    deadline = driver.Deadline(1)
    with pytest.raises(driver.CommandFailure, match="completion was late"):
        fixture.audit_command(["never-launched"], deadline, role="post_create")
    audit = fixture.last_command_audit
    assert audit["exit_observed"] and not audit["pending"]
    assert not audit["deadline_met"] and audit["timeout"]
    assert audit["stdout"]["complete"] and audit["stderr"]["complete"]
    assert fixture.account_commands_blocked
    with pytest.raises(driver.CommandFailure, match="no further account action"):
        fixture.audit_command(["never-launched-again"], driver.Deadline(1), role="userdel", cleanup=True)
    assert len(fake.starts) == 1


def test_audited_stdout_overflow_is_an_incomplete_bounded_prefix(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    clock = FakeClock(monkeypatch)
    fake = audited_process(monkeypatch, clock, [("stdout", b"0123456789ABCDEFG")])
    with pytest.raises(driver.CommandFailure, match="output bound") as raised:
        fixture.audit_command(["never-launched"], driver.Deadline(1), role="post_create", stdout_limit=16)
    prefix = b"0123456789ABCDEF"
    assert raised.value.output == prefix and bytes(fixture.diagnostics) == prefix
    audit = fixture.last_command_audit
    assert audit["stdout"] == stream_receipt(prefix, eof=False, complete=False)
    assert audit["pending"] and fixture.account_commands_blocked and len(fake.killed) == 1


def test_audited_stdout_and_stderr_share_existing_diagnostic_budget(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    clock = FakeClock(monkeypatch)
    monkeypatch.setattr(driver, "LIMITS", {**driver.LIMITS, "diagnostic_bytes": 8})
    fixture.diagnostic(b"old")
    audited_process(monkeypatch, clock, [("stdout", b"abc"), ("stderr", b"xyz")])
    with pytest.raises(driver.CommandFailure, match="output bound"):
        fixture.audit_command(["never-launched"], driver.Deadline(1), role="pre_cleanup", cleanup=True)
    assert bytes(fixture.diagnostics) == b"oldabcxy" and fixture.diagnostic_exceeded
    assert fixture.last_command_audit["stdout"] == stream_receipt(b"abc", eof=False, complete=False)
    assert fixture.last_command_audit["stderr"] == stream_receipt(b"xy", eof=False, complete=False)
    assert fixture.account_commands_blocked


def test_observer_window_uses_earlier_parent_clock_deadlines(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 2)
    clock = FakeClock(monkeypatch)
    parent = driver.Deadline(10)
    child = fixture.observer_deadline(parent)
    assert child.deadline_mono_ns == child.start_mono_ns + 2_000_000_000
    assert child.deadline_boot_ns == child.start_boot_ns + 2_000_000_000
    clock.advance(8.5)
    clock.advance(0.5, boot_only=True)
    child = fixture.observer_deadline(parent)
    assert child.deadline_mono_ns == parent.deadline_mono_ns
    assert child.deadline_boot_ns == parent.deadline_boot_ns
    assert child.remaining() == 1
    clock.advance(1, boot_only=True)
    with pytest.raises(driver.Refusal, match="deadline exhausted"):
        fixture.observer_deadline(parent)


def simulated_process(monkeypatch, stream_name, payload):
    """Exercise the real bounded collector using fake descriptors, not a process."""
    class Pipe:
        def __init__(self, number):
            self.number, self.closed = number, False
        def fileno(self):
            return self.number
        def close(self):
            self.closed = True
    stdout, stderr = Pipe(101), Pipe(102)
    process = SimpleNamespace(pid=987654, stdout=stdout, stderr=stderr, wait=lambda **kwargs: 0)
    class Selector:
        def __init__(self):
            self.keys = {}
        def register(self, stream, _events, data):
            self.keys[stream.fileno()] = SimpleNamespace(fileobj=stream, data=data)
        def get_map(self):
            return self.keys
        def unregister(self, stream):
            del self.keys[stream.fileno()]
        def select(self, _timeout):
            number = 101 if stream_name == "stdout" else 102
            return [(self.keys[number], 1)]
        def close(self):
            pass
    killed = []
    monkeypatch.setattr(driver.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(driver.selectors, "DefaultSelector", Selector)
    monkeypatch.setattr(driver.os, "set_blocking", lambda *_args: None)
    monkeypatch.setattr(driver.os, "read", lambda *_args: payload)
    monkeypatch.setattr(driver.os, "killpg", lambda *args: killed.append(args))
    return killed


def test_native_stdout_overflow_retains_only_bounded_prefix(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 1)
    killed = simulated_process(monkeypatch, "stdout", b"0123456789ABCDEFG")
    with pytest.raises(driver.CommandFailure) as raised:
        fixture.command(["never-launched"], driver.Deadline(1), stdout_limit=16, native=True)
    assert raised.value.output == b"0123456789ABCDEF"
    assert fixture.native_timed_out is True
    assert len(killed) == 1
    assert fixture.pending_commands == []


def test_diagnostic_limit_is_cumulative_across_commands(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 1)
    monkeypatch.setattr(driver, "LIMITS", {**driver.LIMITS, "diagnostic_bytes": 8})
    fixture.diagnostic(b"first!")
    killed = simulated_process(monkeypatch, "stderr", b"next")
    with pytest.raises(driver.CommandFailure, match="output bound"):
        fixture.command(["never-launched"], driver.Deadline(1))
    assert bytes(fixture.diagnostics) == b"first!ne"
    assert fixture.diagnostic_exceeded is True
    assert len(killed) == 1


def test_exhausted_diagnostic_budget_stops_before_next_process(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 1)
    fixture.diagnostic_exceeded = True
    def forbidden(*_args, **_kwargs):
        pytest.fail("budget-exhausted work must not create the next process")
    monkeypatch.setattr(driver.subprocess, "Popen", forbidden)
    with pytest.raises(driver.Refusal, match="no further work started"):
        fixture.command(["never-launched"], driver.Deadline(1), native=True)


def test_cleanup_retains_a_replaced_build_object(monkeypatch, tmp_path):
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 1)
    fixture.build.mkdir(parents=True)
    info = fixture.build.stat()
    fixture.objects.append((fixture.build, info.st_dev, info.st_ino))
    fixture.helper.write_bytes(b"original")
    info = fixture.helper.stat()
    fixture.created_files[fixture.helper] = (info.st_dev, info.st_ino)
    original = tmp_path / "retained-original"
    fixture.helper.rename(original)
    fixture.helper.write_bytes(b"replacement-must-not-delete")
    result = fixture.cleanup()
    assert not result["verified"]
    assert any("identity mismatch" in reason for reason in result["residuals"])
    assert fixture.helper.read_bytes() == b"replacement-must-not-delete"
    assert original.read_bytes() == b"original"


def test_cleanup_does_not_write_to_a_replaced_cgroup_path(tmp_path):
    # Ordinary temp directories stand in for stat/control boundaries only.
    fixture = driver.Fixture(tmp_path, tmp_path / "out", "123456", 1)
    fixture.e = tmp_path / "synthetic-cgroup"
    fixture.e.mkdir()
    info = fixture.e.stat()
    fixture.cg_objects.append((fixture.e, info.st_dev, info.st_ino))
    fixture.e.rename(tmp_path / "original-group")
    fixture.e.mkdir()
    control = fixture.e / "cgroup.kill"
    control.write_bytes(b"do-not-touch")
    result = fixture.cleanup()
    assert not result["verified"]
    assert any("identity changed" in reason for reason in result["residuals"])
    assert control.read_bytes() == b"do-not-touch"
