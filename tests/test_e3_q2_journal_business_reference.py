"""Declared service and domain protections remain after removing unknown-unit enumeration."""
from __future__ import annotations

import hashlib
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux guest inventory helper", allow_module_level=True)

from e3_host import q2_journal_growth_guest as g


ROOT = "/fixture/private-business"
UNIT = "fixture.service"
TEMPLATE = "fixture@.service"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def properties(name=UNIT, **changes):
    value = dict.fromkeys(g.GuestInventory.SHOW, "")
    value.update(Id=name, Names=name, LoadState="loaded", ActiveState="inactive",
                 SubState="dead", MainPID="0", ControlPID="0", Restart="no",
                 UnitFileState="disabled")
    value.update(changes)
    return value


@pytest.fixture
def inventory(monkeypatch):
    """Exercise real ctl/show/startup methods with already-captured synthetic bytes."""
    def make(rows=None, *, roots=None, sources=None, expected=None, domains=None):
        rows = rows or {}
        sources = sources or {}
        calls = []
        events = []
        binding = dict(path="/usr/bin/systemctl", sha256="a" * 64)

        def check():
            pass

        def tool_binding(path, guard):
            assert path == "/usr/bin/systemctl" and guard is check
            return binding

        def verify_tool(observed, guard):
            assert observed is binding and guard is check
            events.append("verify")

        def bound_command(observed, arguments, guard, **kwargs):
            assert observed is binding and guard is check
            assert arguments[:3] == ["--system", "--no-pager", "--no-ask-password"]
            args = arguments[3:]
            calls.append(args)
            events.append("bound")
            if args[0] == "list-units":
                raw = "".join(f"{name} loaded inactive dead Fixture\n" for name in rows).encode()
            elif args[0] == "list-unit-files":
                raw = "".join(f"{name} disabled enabled\n" for name in [*rows, *sources]).encode()
            elif args[0] == "show":
                assert args[1:4] == ["--all", "--property=" + ",".join(g.GuestInventory.SHOW), "--"]
                blocks = []
                for name in args[4:]:
                    blocks.append("\n".join(f"{key}={part}" for key, value in rows[name].items()
                                            for part in value.split("\n")))
                raw = ("\n\n".join(blocks) + "\n").encode()
            else:
                assert args[0] == "cat" and args[1] == "--" and len(args) == 3
                raw = sources[args[2]]

            class Command:
                def collect(self):
                    events.append("collect")
                    return dict(stdout=raw, stderr=b"", returncode=0, both_eof=True, pid=712)

            return Command()

        monkeypatch.setattr(g, "tool_binding", tool_binding)
        monkeypatch.setattr(g, "verify_tool", verify_tool)
        monkeypatch.setattr(g, "bound_command", bound_command)
        value = g.GuestInventory(dict(protected_roots=roots or [ROOT],
                                     expected_units=expected or [], domain_units=domains or []), check)
        return value, calls, events

    return make


def test_declared_business_still_runs_quiet_service_and_reuses_identity(inventory):
    row = properties(WorkingDirectory=ROOT)
    value, calls, events = inventory({UNIT: row}, expected=[dict(name=UNIT, control_group=None)])
    result = value.quiet_service(value.description["expected_units"][0])
    assert result == dict(name=UNIT, properties_sha256=sha(g.canonical(row)))
    assert "business_reference_diagnostic" not in value.context
    assert [call[0] for call in calls] == ["show"]
    assert events == ["bound", "collect", "verify"]


def test_declared_business_must_still_be_quiet(inventory):
    row = properties(WorkingDirectory=ROOT, ActiveState="active", SubState="running", MainPID="72")
    value, _, _ = inventory({UNIT: row}, expected=[dict(name=UNIT, control_group=None)])
    with pytest.raises(g.r.ObservationError, match="^GROWTH_UNIT_ACTIVE$"):
        value.quiet_service(value.description["expected_units"][0])
    assert "business_reference_diagnostic" not in value.context


@pytest.mark.parametrize("action", ["", "/usr/bin/true"])
def test_declared_domain_retains_its_existing_action_check(inventory, action):
    name = "fixture.slice"
    row = properties(name, FragmentPath=ROOT + "/fixture.slice", ExecStart=action)
    value, calls, _ = inventory({name: row}, domains=[dict(name=name, manager="system", control_group="/fixture.slice")])
    if action:
        with pytest.raises(g.r.ObservationError, match="^GROWTH_DOMAIN_UNIT_ACTION$"):
            value.startup_manager()
    else:
        assert value.startup_manager()["domains"] == [dict(name=name, properties_sha256=sha(g.canonical(row)))]
    assert "business_reference_diagnostic" not in value.context
    assert len(calls) == 1
