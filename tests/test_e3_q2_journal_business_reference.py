"""Locate retained business-root matches without querying the guest again."""
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


def assert_show_diagnostic(value, row, key, *, root=ROOT, root_index=1):
    content = g.canonical(row)
    fragment = g.canonical({key: row[key]})
    expected = dict(source="systemctl_show", root_index=root_index,
                    root_bytes=len(root.encode()), root_sha256=sha(root.encode()),
                    content_bytes=len(content), content_sha256=sha(content),
                    byte_offset=content.index(root.encode()), property=key,
                    property_bytes=len(fragment), property_sha256=sha(fragment),
                    property_byte_offset=fragment.index(root.encode()), line_index=None)
    assert value.context["business_reference_diagnostic"] == expected


@pytest.mark.parametrize("key", ["ExecStart", "ExecStartPre", "ExecStartPost", "ExecStop",
                                  "ExecStopPost", "ExecReload", "WorkingDirectory",
                                  "FragmentPath", "DropInPaths", "RootDirectory", "RootImage"])
@pytest.mark.parametrize("position", [0, 1, 2])
def test_same_response_locates_property_and_preserves_rejection(inventory, key, position):
    parts = ["/unrelated/one", "/unrelated/two"]
    parts.insert(position, ROOT + "/retained-item")
    row = properties(**{key: " ".join(parts)})
    value, calls, events = inventory({UNIT: row})
    with pytest.raises(g.r.ObservationError, match="^GROWTH_UNDECLARED_BUSINESS_UNIT$"):
        value.startup_manager()
    assert_show_diagnostic(value, row, key)
    assert value.context["unit"] == value.context["actual_unit"] == UNIT
    assert [call[0] for call in calls] == ["list-units", "list-unit-files", "show"]
    assert events == ["bound", "collect", "verify"] * 3


def test_repeated_exec_rows_locate_all_retained_commands(inventory):
    row = properties(ExecStart="{ path=/usr/bin/true ; }\n{ path=" + ROOT + "/task ; }")
    value, _, _ = inventory({UNIT: row})
    with pytest.raises(g.r.ObservationError, match="UNDECLARED_BUSINESS_UNIT"):
        value.startup_manager()
    assert_show_diagnostic(value, row, "ExecStart")


def test_first_root_and_show_property_order_are_stable(inventory):
    roots = ["/fixture/first", "/fixture/second"]
    row = properties(FragmentPath=roots[0] + "/fragment", ExecStart=roots[0] + "/task",
                     WorkingDirectory=roots[1])
    value, _, _ = inventory({UNIT: row}, roots=roots)
    with pytest.raises(g.r.ObservationError, match="UNDECLARED_BUSINESS_UNIT"):
        value.startup_manager()
    # SHOW order chooses FragmentPath, even though canonical JSON sorts ExecStart first.
    assert_show_diagnostic(value, row, "FragmentPath", root=roots[0])


def test_second_root_index_is_one_based(inventory):
    roots = ["/fixture/absent", ROOT]
    row = properties(WorkingDirectory=ROOT)
    value, _, _ = inventory({UNIT: row}, roots=roots)
    with pytest.raises(g.r.ObservationError, match="UNDECLARED_BUSINESS_UNIT"):
        value.startup_manager()
    assert_show_diagnostic(value, row, "WorkingDirectory", root_index=2)


def test_requested_alias_and_actual_unit_remain_distinguishable(inventory):
    alias = "alias.service"
    row = properties(Names=alias + " " + UNIT, WorkingDirectory=ROOT)
    value, calls, _ = inventory({alias: row})
    with pytest.raises(g.r.ObservationError, match="UNDECLARED_BUSINESS_UNIT"):
        value.startup_manager()
    assert value.context["unit"] == alias
    assert value.context["actual_unit"] == UNIT
    assert calls[-1][-1] == alias
    assert_show_diagnostic(value, row, "WorkingDirectory")


@pytest.mark.parametrize("matched", [ROOT + "-backup", "/other/prefix" + ROOT + "/file",
                                      "description=" + ROOT + "; trailing text"])
def test_existing_substring_match_is_not_weakened_to_path_boundaries(inventory, matched):
    row = properties(ExecStart=matched)
    value, _, _ = inventory({UNIT: row})
    with pytest.raises(g.r.ObservationError, match="UNDECLARED_BUSINESS_UNIT"):
        value.startup_manager()
    assert_show_diagnostic(value, row, "ExecStart")


@pytest.mark.parametrize("prefix", [b"", "# non-ASCII comment: 中文\n".encode()])
def test_template_diagnostic_uses_captured_bytes_and_physical_line(inventory, prefix):
    raw = (b"# /etc/systemd/system/fixture@.service\n[Service]\n" + prefix +
           b"WorkingDirectory=" + ROOT.encode() + b"\nExecStart=/usr/bin/true\n")
    value, calls, events = inventory(sources={TEMPLATE: raw})
    with pytest.raises(g.r.ObservationError, match="UNDECLARED_BUSINESS_UNIT"):
        value.startup_manager()
    offset = raw.index(ROOT.encode())
    assert value.context["business_reference_diagnostic"] == dict(
        source="systemctl_cat", root_index=1, root_bytes=len(ROOT.encode()), root_sha256=sha(ROOT.encode()),
        content_bytes=len(raw), content_sha256=sha(raw), byte_offset=offset,
        property=None, property_bytes=None, property_sha256=None, property_byte_offset=None,
        line_index=raw[:offset].count(b"\n") + 1)
    assert value.context["unit"] == TEMPLATE
    assert [call[0] for call in calls] == ["list-units", "list-unit-files", "cat"]
    assert events == ["bound", "collect", "verify"] * 3


def test_no_root_match_keeps_normal_inventory_without_diagnostic(inventory):
    value, calls, events = inventory({UNIT: properties(ExecStart="/usr/bin/true")})
    assert value.startup_manager() == dict(unit_count=1, related=[], domains=[], indirect_startup="NOT_PERFORMED")
    assert "business_reference_diagnostic" not in value.context
    assert len(calls) == 3 and events == ["bound", "collect", "verify"] * 3


def test_declared_business_still_runs_quiet_service_and_reuses_identity(inventory):
    row = properties(WorkingDirectory=ROOT)
    value, calls, events = inventory({UNIT: row}, expected=[dict(name=UNIT, control_group=None)])
    result = value.startup_manager()
    assert result["related"] == [dict(name=UNIT, properties_sha256=sha(g.canonical(row)))]
    assert "business_reference_diagnostic" not in value.context
    assert [call[0] for call in calls] == ["list-units", "list-unit-files", "show", "show"]
    assert events == ["bound", "collect", "verify"] * 4


def test_declared_business_must_still_be_quiet(inventory):
    row = properties(WorkingDirectory=ROOT, ActiveState="active", SubState="running", MainPID="72")
    value, _, _ = inventory({UNIT: row}, expected=[dict(name=UNIT, control_group=None)])
    with pytest.raises(g.r.ObservationError, match="^GROWTH_UNIT_ACTIVE$"):
        value.startup_manager()
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
    assert len(calls) == 3


def test_large_private_arguments_are_hashed_not_disclosed(inventory):
    private = "PRIVATE-ARGUMENT-SENTINEL-" * 16000
    row = properties(ExecStart="/usr/bin/fixture " + private + ROOT + "/private-task")
    value, calls, events = inventory({UNIT: row})
    with pytest.raises(g.r.ObservationError, match="UNDECLARED_BUSINESS_UNIT"):
        value.startup_manager()
    assert_show_diagnostic(value, row, "ExecStart")
    report = g.canonical(value.context)
    assert len(report) < 1500
    assert b"PRIVATE-ARGUMENT" not in report and ROOT.encode() not in report and b"/private-task" not in report
    assert "prefix" not in report.decode()
    assert len(calls) == 3 and events == ["bound", "collect", "verify"] * 3
