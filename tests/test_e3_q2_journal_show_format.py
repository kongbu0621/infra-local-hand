"""Preserve systemctl Exec array entries while keeping scalar format checks."""
from __future__ import annotations

import ctypes
import glob
import hashlib
import json
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux guest systemctl helper", allow_module_level=True)

from e3_host import q2_journal_growth_guest as g


EXEC_PROPERTIES = ("ExecStart", "ExecStartPre", "ExecStartPost", "ExecStop",
                   "ExecStopPost", "ExecReload")


@pytest.fixture
def boundary(monkeypatch):
    trace = []
    responses = {"show": b"", "list-units": b"", "list-unit-files": b""}
    binding = dict(path="/usr/bin/systemctl", sha256="a" * 64)

    def check():
        pass

    def tool_binding(path, guard):
        assert path == "/usr/bin/systemctl" and guard is check
        return binding

    class Command:
        def __init__(self, verb):
            self.verb = verb

        def collect(self):
            trace.append(("collect", self.verb))
            return dict(returncode=0, both_eof=True, pid=712,
                        stdout=responses[self.verb], stderr=b"")

    def bound_command(observed, arguments, guard, **kwargs):
        assert observed is binding and guard is check
        trace.append(("bound", arguments))
        return Command(arguments[3])

    def verify_tool(observed, guard):
        assert observed is binding and guard is check
        trace.append(("verify",))

    monkeypatch.setattr(g, "tool_binding", tool_binding)
    monkeypatch.setattr(g, "bound_command", bound_command)
    monkeypatch.setattr(g, "verify_tool", verify_tool)
    inventory = g.GuestInventory(dict(protected_roots=["/fixture/private"],
                                      expected_units=[], domain_units=[]), check)
    return inventory, responses, trace


def command_value(executable="/usr/bin/true", argument="fixture"):
    # v255 systemctl-show.c renders one structured value for each Exec member.
    return (f"{{ path={executable} ; argv[]={executable} {argument} ; "
            "ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; "
            "pid=0 ; code=(null) ; status=0/0 }")


def properties(*, name="fixture.service", names=None, actions=()):
    entries = [("Id", name), ("Names", name if names is None else names),
               ("LoadState", "loaded"), ("ActiveState", "inactive"),
               ("SubState", "dead"), ("MainPID", "0"), ("ControlPID", "0"),
               ("Restart", "no"), ("UnitFileState", "enabled"), *actions]
    return "".join(f"{key}={value}\n" for key, value in entries).encode()


def assert_one_show(inventory, trace):
    assert inventory.command_count == 1
    assert [row[0] for row in trace] == ["bound", "collect", "verify"]
    assert trace[1] == ("collect", "show")


@pytest.mark.parametrize("key", EXEC_PROPERTIES)
@pytest.mark.parametrize("values", [
    [command_value(argument="first"), command_value(argument="second")],
    [command_value(), command_value(), command_value()],
])
def test_all_exec_array_members_keep_order_and_identical_entries(boundary, key, values):
    inventory, responses, trace = boundary
    responses["show"] = properties(actions=[(key, value) for value in values])
    result = inventory.show_many(["fixture.service"])
    assert result["fixture.service"][key] == "\n".join(values)
    assert "format_diagnostic" not in inventory.context
    assert_one_show(inventory, trace)


def test_native_v255_property_printer_produces_accepted_repeated_exec(boundary, capfd):
    paths = sorted(glob.glob("/usr/lib/*/systemd/libsystemd-shared-255.so") +
                   glob.glob("/usr/lib/systemd/libsystemd-shared-255.so"))
    if not paths:
        pytest.skip("native systemd v255 property formatter unavailable")
    shared = ctypes.CDLL(paths[0])
    printer = shared.bus_print_property_value
    printer.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint,
                        ctypes.c_char_p]
    printer.restype = ctypes.c_int
    libc = ctypes.CDLL(None)
    libc.fflush.argtypes = [ctypes.c_void_p]
    libc.fflush.restype = ctypes.c_int
    values = [command_value(argument="first"), command_value(argument="second")]
    # Pure formatting only: no message object, bus, manager, or guest connection.
    for value in values:
        assert printer(b"ExecStart", None, 0, value.encode()) >= 0
    assert libc.fflush(None) == 0
    captured = capfd.readouterr()
    assert captured.err == ""
    native = captured.out.encode()
    assert native == b"".join(b"ExecStart=" + value.encode() + b"\n" for value in values)
    inventory, responses, trace = boundary
    responses["show"] = properties() + native
    old_entries = [line.split(b"=", 1) for line in responses["show"].splitlines()]
    assert len(old_entries) != len({entry[0] for entry in old_entries})
    assert inventory.show_many(["fixture.service"])["fixture.service"]["ExecStart"] == "\n".join(values)
    assert_one_show(inventory, trace)


@pytest.mark.parametrize("key", [key for key in g.GuestInventory.SHOW
                                 if key not in EXEC_PROPERTIES])
def test_every_scalar_property_still_rejects_duplicate_even_if_identical(boundary, key):
    inventory, responses, trace = boundary
    base = properties()
    present = dict(line.split(b"=", 1) for line in base.splitlines())
    value = present.get(key.encode(), b"fixture")
    row = key.encode() + b"=" + value + b"\n"
    responses["show"] = base + (row if key.encode() in present else row * 2)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_FORMAT$"):
        inventory.show_many(["fixture.service"])
    assert inventory.context["format_diagnostic"]["failed_check"] == "duplicate_scalar"
    assert inventory.context["format_diagnostic"]["property"] == key
    assert_one_show(inventory, trace)


@pytest.mark.parametrize("key", EXEC_PROPERTIES)
@pytest.mark.parametrize("position", [0, 1, 2])
@pytest.mark.parametrize("kind,reason", [
    ("protected", "GROWTH_UNDECLARED_BUSINESS_UNIT"),
    ("indirect", "GROWTH_INDIRECT_STARTUP_UNVERIFIED"),
    ("domain", "GROWTH_DOMAIN_UNIT_ACTION"),
])
def test_startup_guards_inspect_every_retained_exec_member(
        boundary, key, position, kind, reason):
    inventory, responses, trace = boundary
    name = "fixture.slice" if kind == "domain" else "fixture.service"
    executable = {"protected": "/fixture/private/run", "indirect": "/bin/bash",
                  "domain": "/usr/bin/true"}[kind]
    values = ["", "", ""] if kind == "domain" else [command_value()] * 3
    values[position] = command_value(executable)
    responses["list-units"] = f"{name} loaded inactive dead\n".encode()
    responses["show"] = properties(name=name, actions=[(key, value) for value in values])
    if kind == "domain":
        inventory.description["domain_units"] = [dict(
            name=name, manager="system", control_group="/fixture.slice")]
    with pytest.raises(g.r.ObservationError, match="^" + reason + "$"):
        inventory.startup_manager()
    assert inventory.context["unit"] == name
    assert inventory.command_count == 3
    assert [row for row in trace if row[0] == "collect"] == [
        ("collect", "list-units"), ("collect", "list-unit-files"), ("collect", "show")]


def test_alias_conflict_in_middle_exec_member_is_not_hidden(boundary):
    inventory, responses, trace = boundary
    values = [command_value(argument=word) for word in ("first", "middle", "last")]
    first = properties(name="real.service", names="real.service alias.service",
                       actions=[("ExecStartPre", value) for value in values])
    values[1] = command_value(argument="changed")
    second = properties(name="real.service", names="real.service alias.service",
                        actions=[("ExecStartPre", value) for value in values])
    responses["show"] = first + b"\n" + second
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_ALIAS_CONFLICT$"):
        inventory.show_many(["real.service", "alias.service"])
    assert_one_show(inventory, trace)


@pytest.mark.parametrize("change", [0, 1, 2, "order"])
def test_quiet_service_hash_binds_every_exec_member_and_order(boundary, change):
    inventory, responses, trace = boundary
    values = [command_value(argument=word) for word in ("first", "middle", "last")]

    def receipt():
        responses["show"] = properties(actions=[("ExecStopPost", value) for value in values]).replace(
            b"UnitFileState=enabled\n", b"UnitFileState=static\n")
        return inventory.quiet_service(dict(name="fixture.service", control_group=None))

    before = receipt()
    if change == "order":
        values.reverse()
    else:
        values[change] = command_value(argument="changed")
    after = receipt()
    assert before["name"] == after["name"] == "fixture.service"
    assert before["properties_sha256"] != after["properties_sha256"]
    assert inventory.command_count == 2
    assert [row for row in trace if row[0] == "collect"] == [("collect", "show")] * 2


@pytest.mark.parametrize("bad_row,failed_check,property_name,first_line", [
    (b"private-command-without-equals", "missing_equals", None, None),
    (b"Restart=private-value", "duplicate_scalar", "Restart", 8),
    (b"private-key=private-value", "duplicate_scalar", None, 10),
])
def test_format_diagnostic_identifies_same_response_without_leaking_values(
        boundary, bad_row, failed_check, property_name, first_line):
    inventory, responses, trace = boundary
    first = properties(name="first.service")
    second = properties()
    if first_line == 10:
        second += b"private-key=private-value\n"
    line_index = len(second.splitlines()) + 1
    responses["show"] = first + b"\n" + second + bad_row + b"\n"
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_FORMAT$"):
        inventory.show_many(["first.service", "fixture.service"])
    assert inventory.context["response_index"] == 2
    assert inventory.context["unit"] == "fixture.service"
    assert inventory.context["format_diagnostic"] == dict(
        failed_check=failed_check, line_index=line_index, property=property_name,
        first_line_index=first_line, line_bytes=len(bad_row),
        line_sha256=hashlib.sha256(bad_row).hexdigest())
    rendered = json.dumps(inventory.context)
    assert "private-" not in rendered and len(rendered) < 1024
    assert_one_show(inventory, trace)


def test_large_rejected_line_has_fixed_size_diagnostic(boundary):
    inventory, responses, trace = boundary
    bad_row = b"Restart=" + b"private-value" * 8192
    responses["show"] = properties() + bad_row + b"\n"
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_FORMAT$"):
        inventory.show_many(["fixture.service"])
    diagnostic = inventory.context["format_diagnostic"]
    assert diagnostic["line_bytes"] == len(bad_row)
    assert diagnostic["line_sha256"] == hashlib.sha256(bad_row).hexdigest()
    assert "private-value" not in json.dumps(inventory.context)
    assert len(json.dumps(inventory.context)) < 1024
    assert_one_show(inventory, trace)
