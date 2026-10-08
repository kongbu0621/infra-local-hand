"""Decode systemctl's Names display without changing unit identity admission."""
from __future__ import annotations

import ctypes
import glob
import hashlib
import json
import string
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux guest systemctl helper", allow_module_level=True)

from e3_host import q2_journal_growth_guest as g


@pytest.fixture
def boundary(monkeypatch):
    trace = []
    outcome = dict(returncode=0, both_eof=True, pid=712, stdout=b"", stderr=b"")
    binding = dict(path="/usr/bin/systemctl", sha256="a" * 64)

    def check():
        pass

    def tool_binding(path, guard):
        assert path == "/usr/bin/systemctl" and guard is check
        return binding

    class Command:
        def collect(self):
            trace.append("collect")
            return dict(outcome)

    def bound_command(observed, arguments, guard, **kwargs):
        assert observed is binding and guard is check
        trace.append(("bound", arguments, kwargs))
        return Command()

    def verify_tool(observed, guard):
        assert observed is binding and guard is check
        trace.append("verify")

    monkeypatch.setattr(g, "tool_binding", tool_binding)
    monkeypatch.setattr(g, "bound_command", bound_command)
    monkeypatch.setattr(g, "verify_tool", verify_tool)
    inventory = g.GuestInventory(dict(protected_roots=["/fixture/private"]), check)
    return inventory, outcome, trace


@pytest.fixture(scope="module")
def native_quote():
    # The v255 string-array printer calls this exact pure formatting function.
    # Loading the library and formatting bytes creates no manager/bus connection.
    paths = sorted(glob.glob("/usr/lib/*/systemd/libsystemd-shared-255.so") +
                   glob.glob("/usr/lib/systemd/libsystemd-shared-255.so"))
    if not paths:
        pytest.skip("native systemd v255 string formatter unavailable")
    shared = ctypes.CDLL(paths[0])
    quote = shared.shell_maybe_quote
    quote.argtypes = [ctypes.c_char_p, ctypes.c_int]
    quote.restype = ctypes.c_void_p
    libc = ctypes.CDLL(None)
    libc.free.argtypes = [ctypes.c_void_p]
    libc.free.restype = None

    def render(name):
        pointer = quote(name.encode("ascii"), 0)
        assert pointer, "native formatter allocation failed"
        try:
            return ctypes.string_at(pointer).decode("ascii")
        finally:
            libc.free(pointer)

    return render


def properties(identity, displayed_names, *, state="inactive"):
    return (f"Id={identity}\nNames={displayed_names}\nLoadState=loaded\n"
            f"ActiveState={state}\nSubState=dead\nMainPID=0\nControlPID=0\n"
            "Restart=no\n").encode("ascii")


@pytest.mark.parametrize("identity", [
    "ordinary.service", "-.slice", r"system-systemd\x2dfsck.slice",
    r"getty@tty\x2d1.service", r"escaped\x20name.service",
])
def test_native_v255_names_pass_real_inventory(boundary, native_quote, identity):
    inventory, outcome, trace = boundary
    displayed = native_quote(identity)
    expected = ('"' + identity.replace("\\", "\\\\") + '"'
                if "\\" in identity else identity)
    assert displayed == expected
    if "\\" in identity:
        # Demonstrate the previous split-based rejection of legal native output.
        assert g.UNIT_PATTERN.fullmatch(displayed.split()[0]) is None
    outcome["stdout"] = properties(identity, displayed)

    result = inventory.show_many([identity])

    assert result[identity]["Id"] == identity
    assert result[identity]["Names"] == displayed
    assert trace[1:] == ["collect", "verify"]
    assert inventory.command_count == 1


@pytest.mark.parametrize("copies", [1, 2])
def test_native_escaped_alias_proves_exact_membership(boundary, native_quote, copies):
    inventory, outcome, trace = boundary
    identity, alias = r"real\x2dname.service", r"alias\x2dname.service"
    displayed = " ".join(native_quote(name) for name in (identity, alias))
    outcome["stdout"] = b"\n".join([properties(identity, displayed)] * copies)

    result = inventory.show_many([identity, alias])

    assert set(result) == {identity, alias}
    assert result[identity] == result[alias]
    assert result[alias]["Id"] == identity
    assert inventory.command_count == 1
    assert trace[1:] == ["collect", "verify"]


@pytest.mark.parametrize("displayed", [
    r'"escaped\\x2dname.service"',
    r'"escaped\\x2dname.service" ordinary.service',
    r'ordinary.service "escaped\\x2dname.service"',
])
def test_encoded_escape_is_preserved_as_literal_unit_name(boundary, displayed):
    inventory, outcome, trace = boundary
    identity = r"escaped\x2dname.service"
    outcome["stdout"] = properties(identity, displayed)
    result = inventory.show_many([identity])
    assert result[identity]["Id"] == identity
    assert "escaped-name.service" not in result
    assert trace[1:] == ["collect", "verify"]


@pytest.mark.parametrize("displayed", [
    '"real.service', 'real.service"', "real.service\\",
    "real.service /bad.service", 'real.service "bad name.service"',
    "real.service bad.device", "real.service bad.mount",
    "real.service bad.automount", "real.service bad.swap",
    "real.service real.service", 'real.service "real.service"',
    "alias.service", "alias.service other.service",
])
def test_bad_names_stop_after_same_single_response(boundary, displayed):
    inventory, outcome, trace = boundary
    outcome["stdout"] = properties("real.service", displayed)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_NAMES$"):
        inventory.show_many(["real.service"])
    assert inventory.command_count == 1
    assert trace[1:] == ["collect", "verify"]


def test_escaped_duplicate_names_still_rejected(boundary, native_quote):
    inventory, outcome, trace = boundary
    identity = r"real\x2dname.service"
    displayed = " ".join([native_quote(identity)] * 2)
    outcome["stdout"] = properties(identity, displayed)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_NAMES$"):
        inventory.show_many([identity])
    assert inventory.command_count == 1
    assert trace[1:] == ["collect", "verify"]


def test_escaped_alias_does_not_resolve_to_unescaped_request(boundary, native_quote):
    inventory, outcome, _ = boundary
    identity = r"real\x2dname.service"
    outcome["stdout"] = properties(identity, native_quote(identity))
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_UNIT_SET$"):
        inventory.show_many(["real-name.service"])


def test_escaped_alias_conflicting_properties_still_rejected(boundary, native_quote):
    inventory, outcome, trace = boundary
    identity, alias = r"real\x2dname.service", "alias.service"
    displayed = " ".join(native_quote(name) for name in (identity, alias))
    outcome["stdout"] = (properties(identity, displayed) + b"\n" +
                         properties(identity, displayed, state="active"))
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_ALIAS_CONFLICT$"):
        inventory.show_many([identity, alias])
    assert inventory.command_count == 1
    assert trace[1:] == ["collect", "verify"]


def test_declared_identity_stays_strict_after_display_decoding(boundary, native_quote):
    inventory, outcome, _ = boundary
    identity, alias = r"real\x2dname.service", "alias.service"
    displayed = " ".join(native_quote(name) for name in (identity, alias))
    outcome["stdout"] = properties(identity, displayed)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_UNIT_IDENTITY$"):
        inventory.quiet_service(dict(name=alias, control_group=None))


def test_all_allowed_name_characters_roundtrip_native_formatter(boundary, native_quote):
    inventory, outcome, trace = boundary
    identity = string.ascii_letters + string.digits + r"_.:@-\x.service"
    assert g.UNIT_PATTERN.fullmatch(identity)
    outcome["stdout"] = properties(identity, native_quote(identity))
    assert inventory.show_many([identity])[identity]["Id"] == identity
    assert trace[1:] == ["collect", "verify"]


@pytest.mark.parametrize("displayed,checks,count", [
    ('"real.service', ["parse"], None),
    ("real.service real.service", ["duplicate"], 2),
    ("real.service /bad.service", ["format"], 2),
    ("other.service", ["id_member"], 1),
    ("real.service 'real.service'", ["duplicate", "encoding"], 2),
    ("'real.service'", ["encoding"], 1),
    ('"real".service', ["encoding"], 1),
    ('"real.service"', ["encoding"], 1),
    ("real.service  alias.service", ["encoding"], 2),
    ("real.service bad.device bad.device", ["duplicate", "format"], 3),
    ("bad.device bad.device", ["duplicate", "format", "id_member"], 2),
    (r"real.service escaped\x2dname.service", ["encoding"], 2),
])
def test_failure_diagnostics_identify_exact_rejection(boundary, displayed, checks, count):
    inventory, outcome, trace = boundary
    inventory.context = dict(unit="stale.service", names_diagnostic={"stale": True})
    outcome["stdout"] = properties("real.service", displayed)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_NAMES$"):
        inventory.show_many(["real.service"])
    context = inventory.context
    assert context["manager"] == "system"
    assert context["verb"] == "show"
    assert context["command_index"] == context["response_index"] == 1
    assert context["unit_count"] == 1
    assert context["unit"] == "real.service"
    assert context["arguments_sha256"] == g.digest(g.canonical(trace[0][1][3:]))
    raw = displayed.encode("ascii")
    assert context["names_diagnostic"] == dict(
        failed_checks=checks, alias_count=count, bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(), prefix_hex=raw.hex(), truncated=False)
    assert inventory.command_count == 1
    assert trace[1:] == ["collect", "verify"]


@pytest.mark.parametrize("size", [511, 512, 513, 4096])
def test_names_diagnostic_prefix_has_fixed_byte_bound(boundary, size):
    inventory, outcome, trace = boundary
    displayed = "a" * size
    raw = displayed.encode("ascii")
    outcome["stdout"] = properties("real.service", displayed)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_NAMES$"):
        inventory.show_many(["real.service"])
    diagnostic = inventory.context["names_diagnostic"]
    assert diagnostic == dict(
        failed_checks=["format", "id_member"], alias_count=1, bytes=size,
        sha256=hashlib.sha256(raw).hexdigest(), prefix_hex=raw[:512].hex(),
        truncated=size > 512)
    assert len(json.dumps(inventory.context)) < 2048
    assert "stdout" not in inventory.context and "stderr" not in inventory.context
    assert trace[1:] == ["collect", "verify"]


def test_diagnostic_second_block_retains_its_unit_and_same_response(boundary):
    inventory, outcome, trace = boundary
    outcome["stdout"] = (properties("first.service", "first.service") + b"\n" +
                         properties("second.service", "other.service"))
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SYSTEMCTL_NAMES$"):
        inventory.show_many(["first.service", "second.service"])
    assert inventory.context["response_index"] == 2
    assert inventory.context["unit"] == "second.service"
    assert inventory.context["unit_count"] == 2
    assert inventory.context["command_index"] == 1
    assert inventory.command_count == 1
    assert trace[1:] == ["collect", "verify"]


def test_names_empty_identity_response_retains_existing_behavior(boundary):
    inventory, outcome, trace = boundary
    outcome["stdout"] = properties("real.service", "")
    assert inventory.show_many(["real.service"])["real.service"]["Id"] == "real.service"
    assert "names_diagnostic" not in inventory.context
    assert trace[1:] == ["collect", "verify"]
