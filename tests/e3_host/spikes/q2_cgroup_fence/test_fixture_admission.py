"""No live cgroup, account, compiler or helper invocation in these tests."""
from __future__ import annotations

import importlib.util
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
    assert driver.main(["--expected-commit", candidate, "--round", "1"]) == 4
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
    assert driver.main(["--expected-commit", candidate, "--round", "1"]) == 4


def test_worktree_bytes_are_compared_to_the_exact_commit(monkeypatch, tmp_path):
    candidate = "a" * 40
    paths = [driver.SCOPE_DIR + "/run_fixture.py", driver.WORKFLOW, "AGENTS.md",
             "docs/governance/Q2_H07_CGROUP_FENCE_SPIKE_OWNER_DECISION.md"]
    paths += ["docs/a2-execution/q2-h07-cgroup-fence-spike/" + name
              for name in driver.PINNED_DOCUMENTS]
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"committed bytes\n")
    (tmp_path / driver.SCOPE_DIR / "run_fixture.py").write_bytes(b"uncommitted replacement\n")
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


def hosted_env(tmp_path):
    return {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REPOSITORY": "kongbu0621/infra-local-hand", "GITHUB_RUN_ATTEMPT": "1",
            "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
            "ImageOS": "ubuntu24", "GITHUB_RUN_ID": "123456", "RUNNER_TEMP": str(tmp_path),
            "LAB_REASON": "initial exact source verification"}


def test_existing_dispatch_output_is_never_reused(monkeypatch, tmp_path):
    env = hosted_env(tmp_path)
    output = tmp_path / "q2-h07-123456-1-r1"
    output.mkdir()
    marker = output / "original-evidence"
    marker.write_bytes(b"retained")
    monkeypatch.setattr(driver.os, "geteuid", lambda: 0)
    monkeypatch.setattr(driver.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(driver, "read_small", lambda *_args, **_kwargs: 'ID=ubuntu\nVERSION_ID="24.04"')
    with pytest.raises(driver.Refusal, match="cannot be replayed"):
        driver.admission(env, 1)
    assert marker.read_bytes() == b"retained"
    assert list(output.iterdir()) == [marker]


@pytest.mark.parametrize("attempt", ["0", "2", "01"])
def test_github_rerun_never_becomes_a_fresh_lab_round(tmp_path, attempt):
    env = hosted_env(tmp_path)
    env["GITHUB_RUN_ATTEMPT"] = attempt
    with pytest.raises(driver.Refusal, match="GITHUB_RUN_ATTEMPT"):
        driver.admission(env, 2)
    assert list(tmp_path.iterdir()) == []


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
