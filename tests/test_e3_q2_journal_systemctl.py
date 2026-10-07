"""Guest systemctl admission over synthetic results and offline CLI parsing."""
from __future__ import annotations

import copy
import itertools
import os
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux guest systemctl helper", allow_module_level=True)

from e3_host import q2_journal_growth_guest as g


@pytest.fixture
def boundary(monkeypatch):
    trace = []
    outcome = dict(returncode=0, both_eof=True, pid=712,
                   stdout=b"synthetic-result\n", stderr=b"")
    binding = dict(path="/usr/bin/systemctl", sha256="a" * 64)

    def check():
        pass

    def tool_binding(path, guard):
        assert path == "/usr/bin/systemctl" and guard is check
        return binding

    class Command:
        def collect(self):
            trace.append(("collect",))
            return dict(outcome)

    def bound_command(observed, arguments, guard, **kwargs):
        assert observed is binding and guard is check
        trace.append(("bound", arguments, kwargs))
        return Command()

    def verify_tool(observed, guard):
        assert observed is binding and guard is check
        trace.append(("verify",))

    monkeypatch.setattr(g, "tool_binding", tool_binding)
    monkeypatch.setattr(g, "bound_command", bound_command)
    monkeypatch.setattr(g, "verify_tool", verify_tool)
    inventory = g.GuestInventory(dict(protected_roots=["/fixture/private"]), check)
    return inventory, outcome, trace


def properties(names):
    return b"\n\n".join(
        (f"Id={name}\nLoadState=not-found\nActiveState=inactive\nSubState=dead").encode()
        for name in names
    ) + b"\n"


def test_real_show_many_preserves_leading_dash_unit_and_exact_set(boundary):
    inventory, outcome, trace = boundary
    names = ["-.slice", "fixture.service"]
    outcome["stdout"] = properties(names)

    parsed = inventory.show_many(names)

    assert set(parsed) == set(names)
    assert all(parsed[name]["Id"] == name for name in names)
    assert parsed["-.slice"]["LoadState"] == "not-found"
    arguments = trace[0][1]
    assert arguments == ["--system", "--no-pager", "--no-ask-password",
                         "show", "--all", "--property=" + ",".join(inventory.SHOW),
                         "--", *names]
    assert trace[1:] == [("collect",), ("verify",)]
    assert inventory.context["unit_count"] == 2


def test_native_systemctl_parses_dash_unit_only_after_separator(boundary, tmp_path):
    """--root forbids this verb before any manager connection or unit read."""
    executable = "/usr/bin/systemctl"
    if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        pytest.skip("native systemctl CLI unavailable")
    inventory, outcome, trace = boundary
    outcome["stdout"] = properties(["-.slice"])
    inventory.show_many(["-.slice"])
    arguments = trace[0][1]
    prefix = [executable, "--root=" + str(tmp_path / "absent-offline-root")]
    environment = dict(g.ENVIRONMENT)
    old = subprocess.run(prefix + [part for part in arguments if part != "--"],
                         stdin=subprocess.DEVNULL, capture_output=True,
                         env=environment, timeout=5, check=False)
    fixed = subprocess.run(prefix + arguments, stdin=subprocess.DEVNULL,
                           capture_output=True, env=environment, timeout=5, check=False)

    assert old.returncode != 0 and b"invalid option -- '.'" in old.stderr
    assert fixed.returncode != 0
    assert b"invalid option" not in fixed.stderr
    assert b"Verb 'show' cannot be used with --root=" in fixed.stderr
    assert old.stdout == fixed.stdout == b""


def test_success_still_verifies_tool_and_replaces_stale_context(boundary):
    inventory, outcome, trace = boundary
    arguments = ["list-units", "--all", "--plain", "--no-legend"]
    inventory.context = dict(unit="stale.service", action_kind="old")

    assert inventory.ctl(arguments) == outcome["stdout"]
    assert inventory.context == dict(manager="system", command_index=1,
                                    verb="list-units", unit_count=0,
                                    arguments_sha256=g.digest(g.canonical(arguments)))
    assert inventory.command_count == 1
    assert [item[0] for item in trace] == ["bound", "collect", "verify"]
    assert trace[0][2] == dict(environment=None, preexec_fn=None)


@pytest.mark.parametrize("bad_code,bad_eof,has_stderr", [
    values for values in itertools.product((False, True), repeat=3) if any(values)
])
def test_failure_reports_exact_original_conditions_without_second_command(
        boundary, bad_code, bad_eof, has_stderr):
    inventory, outcome, trace = boundary
    arguments = ["show", "--all", "--property=Id", "--", "-.slice"]
    outcome.update(returncode=5 if bad_code else 0, both_eof=not bad_eof,
                   stdout=b"private ExecStart=/fixture/secret\n",
                   stderr=b"synthetic parser failure\n" if has_stderr else b"")
    inventory.context = dict(unit="stale.service", manager="user_1100")

    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_STDERR$"):
        inventory.ctl(arguments)

    assert inventory.context == dict(
        manager="system", command_index=1, verb="show", unit_count=1,
        arguments_sha256=g.digest(g.canonical(arguments)),
        returncode=outcome["returncode"], both_eof=outcome["both_eof"], pid=712,
        stdout_bytes=len(outcome["stdout"]), stderr_bytes=len(outcome["stderr"]),
        stdout_sha256=g.digest(outcome["stdout"]), stderr_sha256=g.digest(outcome["stderr"]),
        stderr_prefix_hex=outcome["stderr"].hex(), stderr_truncated=False,
        failed_checks=[name for name, failed in (
            ("returncode", bad_code), ("both_eof", bad_eof), ("stderr", has_stderr)) if failed])
    assert inventory.command_count == 1
    assert [item[0] for item in trace] == ["bound", "collect"]
    rendered = g.canonical(inventory.context)
    assert b"ExecStart" not in rendered and b"/fixture/secret" not in rendered
    assert b"environment" not in rendered and b"stale.service" not in rendered


@pytest.mark.parametrize("length", [511, 512, 513, 1024])
def test_stderr_bytes_bounded_without_losing_full_length_or_digest(boundary, length):
    inventory, outcome, trace = boundary
    outcome["stderr"] = bytes(range(256)) * 4
    outcome["stderr"] = outcome["stderr"][:length]
    with pytest.raises(g.r.ObservationError, match="GROWTH_SYSTEMCTL_STDERR"):
        inventory.ctl(["list-unit-files", "--no-legend"])

    detail = inventory.context
    assert detail["stderr_bytes"] == length
    assert detail["stderr_sha256"] == g.digest(outcome["stderr"])
    assert bytes.fromhex(detail["stderr_prefix_hex"]) == outcome["stderr"][:512]
    assert detail["stderr_truncated"] is (length > 512)
    assert detail["failed_checks"] == ["stderr"]
    assert len(g.canonical(detail)) < 2048
    assert [item[0] for item in trace] == ["bound", "collect"]


def test_command_indices_advance_and_success_does_not_reuse_failure_detail(boundary):
    inventory, outcome, trace = boundary
    outcome["stderr"] = b"first diagnostic"
    with pytest.raises(g.r.ObservationError, match="GROWTH_SYSTEMCTL_STDERR"):
        inventory.ctl(["list-units", "--all"])
    first = copy.deepcopy(inventory.context)
    outcome["stderr"] = b""
    inventory.ctl(["list-unit-files", "--no-legend"])

    assert first["command_index"] == 1 and first["verb"] == "list-units"
    assert inventory.context["command_index"] == 2
    assert inventory.context["verb"] == "list-unit-files"
    assert "failed_checks" not in inventory.context
    assert "stderr_prefix_hex" not in inventory.context
    assert inventory.command_count == 2
    assert [item[0] for item in trace] == ["bound", "collect", "bound", "collect", "verify"]


def test_guest_failure_preserves_same_systemctl_context_with_bounded_stderr(boundary):
    inventory, outcome, trace = boundary
    outcome.update(returncode=1, stdout=b"ExecStart=/private/command-secret\n",
                   stderr=b"synthetic-failure:" + b"z" * 700)
    maintenance = g.GuestMaintenance(dict(phase="pre"), window=SimpleNamespace())
    maintenance.stage = "PRE_QUIESCENCE"
    maintenance.inventory = inventory

    with pytest.raises(g.r.ObservationError, match="GROWTH_SYSTEMCTL_STDERR") as caught:
        inventory.ctl(["show", "--all", "--property=Id", "--", "-.slice"])
    report = maintenance.failure(caught.value)

    assert report["reason"] == "GROWTH_SYSTEMCTL_STDERR"
    assert report["status"] == "INCOMPLETE" and report["stage"] == "PRE_QUIESCENCE"
    assert report["actions_started"] == []
    detail = report["diagnostic"]["context"]
    assert detail == inventory.context
    assert detail["command_index"] == 1 and detail["failed_checks"] == ["returncode", "stderr"]
    assert detail["stderr_bytes"] == len(outcome["stderr"])
    assert detail["stderr_sha256"] == g.digest(outcome["stderr"])
    assert bytes.fromhex(detail["stderr_prefix_hex"]) == outcome["stderr"][:512]
    assert detail["stderr_truncated"] is True
    rendered = g.canonical(report)
    assert len(rendered) < 4096
    assert b"/private/command-secret" not in rendered and b"ExecStart" not in rendered
    assert b"environment" not in rendered
    assert [item[0] for item in trace] == ["bound", "collect"]


@pytest.mark.parametrize("returncode", [0, 1])
def test_user_manager_records_identity_without_environment_or_credential_side_effects(
        boundary, monkeypatch, returncode):
    inventory, outcome, trace = boundary
    runtime = SimpleNamespace(st_uid=1100, st_gid=1100, st_mode=stat.S_IFDIR | 0o700)
    bus = SimpleNamespace(st_dev=1, st_ino=2, st_uid=1100, st_gid=1100,
                          st_mode=stat.S_IFSOCK | 0o600)
    monkeypatch.setattr(g, "pwd", SimpleNamespace(
        getpwuid=lambda uid: SimpleNamespace(pw_uid=uid, pw_gid=uid)))
    monkeypatch.setattr(g, "open_path", lambda *args, **kwargs: 61)
    fake_os = SimpleNamespace(**vars(os))
    fake_os.fstat = lambda fd: runtime
    fake_os.stat = lambda *args, **kwargs: bus
    fake_os.close = lambda fd: None
    fake_os.setgroups = fake_os.setresgid = fake_os.setresuid = (
        lambda *args: pytest.fail("synthetic command must never change credentials"))
    monkeypatch.setattr(g, "os", fake_os)
    outcome["returncode"] = returncode

    if returncode:
        with pytest.raises(g.r.ObservationError, match="GROWTH_SYSTEMCTL_STDERR"):
            inventory.ctl(["show", "--all", "--", "fixture.slice"], user_uid=1100)
    else:
        inventory.ctl(["show", "--all", "--", "fixture.slice"], user_uid=1100)

    assert inventory.context["manager"] == "user_1100"
    assert inventory.context["unit_count"] == 1
    assert trace[0][1][0] == "--user"
    assert callable(trace[0][2]["preexec_fn"])
    assert trace[0][2]["environment"]["XDG_RUNTIME_DIR"] == "/run/user/1100"
    assert [item[0] for item in trace] == ["bound", "collect"] + ([] if returncode else ["verify"])
    rendered = g.canonical(inventory.context)
    assert b"DBUS_SESSION_BUS_ADDRESS" not in rendered
    assert b"XDG_RUNTIME_DIR" not in rendered and b"/run/user/1100" not in rendered
