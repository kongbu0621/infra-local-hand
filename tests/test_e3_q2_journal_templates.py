"""Template inventory over synthetic results and a private, managerless D-Bus."""
from __future__ import annotations

import os
import select
import subprocess
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux guest systemctl helper", allow_module_level=True)

from e3_host import q2_journal_growth_guest as g


def inventory(unit_files, *, loaded=(), sources=None, states=None):
    value = object.__new__(g.GuestInventory)
    value.description = dict(expected_units=[], domain_units=[])
    value.roots = ["/fixture/protected"]
    value.context = {}
    value.check = lambda: None
    trace = []
    sources = sources or {}
    states = states or {}

    def ctl(arguments, *, user_uid=None):
        trace.append((arguments, user_uid))
        if arguments[0] == "list-units":
            return "".join(f"{name} loaded inactive dead Fixture\n" for name in loaded).encode()
        if arguments[0] == "list-unit-files":
            return unit_files
        if arguments[0] == "cat":
            assert arguments[1] == "--" and len(arguments) == 3
            return sources[arguments[2]]
        assert arguments[0] == "show"
        names = arguments[arguments.index("--") + 1:]
        assert not any(name.rsplit(".", 1)[0].endswith("@") for name in names)
        blocks = []
        for name in names:
            row = {key: "" for key in value.SHOW}
            row.update(Id=name, Names=name, LoadState="loaded", ActiveState="inactive", SubState="dead",
                       MainPID="0", ControlPID="0", Restart="no", UnitFileState=states.get(name, "disabled"))
            blocks.append("\n".join(f"{key}={item}" for key, item in row.items() if key in value.SHOW))
        return "\n\n".join(blocks).encode() + b"\n"

    value.ctl = ctl
    return value, trace


TEMPLATE = "fixture@.service"
SOURCE = b"# /etc/systemd/system/fixture@.service\n[Service]\nExecStart=/usr/bin/true\n"


@pytest.mark.parametrize("user_uid", [None, 1100])
def test_templates_use_one_cat_while_plain_and_instance_keep_full_show(user_uid):
    value, trace = inventory(b"fixture@.service disabled enabled\nplain.service disabled enabled\n",
                             loaded=["fixture@actual.service", "plain.service"],
                             sources={TEMPLATE: SOURCE})
    result = value.startup_manager(user_uid=user_uid)
    assert result == dict(unit_count=3, related=[], domains=[], indirect_startup="NOT_PERFORMED")
    assert [call for call, _ in trace if call[0] == "cat"] == [["cat", "--", TEMPLATE]]
    shown = [call[call.index("--") + 1:] for call, _ in trace if call[0] == "show"]
    assert shown == [["fixture@actual.service", "plain.service"]]
    assert all(uid == user_uid for _, uid in trace)


@pytest.mark.parametrize("state", sorted(g.UNIT_FILE_STATES))
def test_every_template_state_still_reads_and_checks_dropin_contents(state):
    raw = SOURCE + b"\n# /etc/systemd/system/fixture@.service.d/override.conf\n[Service]\nWorkingDirectory=/fixture/protected\n"
    value, trace = inventory(f"{TEMPLATE} {state}\n".encode(), sources={TEMPLATE: raw})
    with pytest.raises(g.r.ObservationError, match="UNDECLARED_BUSINESS_UNIT"):
        value.startup_manager()
    assert trace[-1][0] == ["cat", "--", TEMPLATE]
    assert value.context == dict(manager="system", unit=TEMPLATE)


@pytest.mark.parametrize("state", sorted(g.STARTUP_ENABLED_STATES))
@pytest.mark.parametrize("action", [b"/bin/bash -c true", b"/usr/bin/python3 task.py", b"/usr/bin/perl task.pl",
                                     b"/usr/sbin/cron", b"/usr/bin/systemd-run true"])
def test_enabled_template_records_approved_indirect_observation_gap(state, action):
    raw = SOURCE + b"ExecStartPost=" + action + b"\n"
    value, _ = inventory(f"{TEMPLATE} {state}\n".encode(), sources={TEMPLATE: raw})
    assert value.startup_manager()["indirect_startup"] == "NOT_PERFORMED"
    assert "action_kind" not in value.context


def test_comments_and_description_do_not_create_exec_actions():
    raw = SOURCE + b"# ExecStart=/bin/bash -c true\n; ExecStop=/bin/sh\nDescription=/bin/bash helper\n"
    value, _ = inventory(f"{TEMPLATE} enabled\n".encode(), sources={TEMPLATE: raw})
    assert value.startup_manager()["indirect_startup"] == "NOT_PERFORMED"


def test_continued_exec_with_interleaved_comment_records_unobserved_indirect_startup():
    raw = SOURCE + b"ExecStartPost=\\\n# physical-line comment\n /bin/bash -c true\n"
    value, _ = inventory(f"{TEMPLATE} enabled\n".encode(), sources={TEMPLATE: raw})
    assert value.startup_manager()["indirect_startup"] == "NOT_PERFORMED"


def test_overridden_exec_is_conservatively_retained_without_merge_parser():
    raw = SOURCE + b"ExecStop=/bin/bash -c true\nExecStop=\nExecStop=/usr/bin/true\n"
    value, _ = inventory(f"{TEMPLATE} enabled\n".encode(), sources={TEMPLATE: raw})
    assert value.startup_manager()["indirect_startup"] == "NOT_PERFORMED"


@pytest.mark.parametrize("action", [b'"/usr/bin/python3" -c pass', b"'/usr/bin/perl' -e 1",
                                     b"@bash alternate-name -c true", b"-@bash alternate-name",
                                     b'+"/bin/bash" -c true', b"!python3 -c pass",
                                     b"perl -e 1", b"cron -f", b"systemd-run true"])
def test_template_interpreter_quotes_prefixes_and_bare_names_are_not_classified(action):
    value, _ = inventory(f"{TEMPLATE} enabled\n".encode(),
                         sources={TEMPLATE: SOURCE + b"ExecStartPost=" + action + b"\n"})
    assert value.startup_manager()["indirect_startup"] == "NOT_PERFORMED"


def test_encoded_template_executable_is_not_assumed_to_be_classified():
    value, _ = inventory(f"{TEMPLATE} enabled\n".encode(),
                         sources={TEMPLATE: SOURCE + b"ExecStartPost=/bin/\\x62ash -c true\n"})
    assert value.startup_manager()["indirect_startup"] == "NOT_PERFORMED"


@pytest.mark.parametrize("state", ["disabled", "static", "masked", "masked-runtime"])
def test_non_enabled_template_does_not_invent_an_active_instance(state):
    raw = SOURCE + b"ExecStop=/bin/bash -c true\n[Install]\nDefaultInstance=example\n"
    value, trace = inventory(f"{TEMPLATE} {state}\n".encode(), sources={TEMPLATE: raw})
    assert value.startup_manager()["unit_count"] == 1
    assert not any(call[0] == "show" for call, _ in trace)


@pytest.mark.parametrize("raw", [b"", b"[Service]\nExecStart=/usr/bin/true\n", SOURCE + b"\0", b"# /" + b"x" * g.STREAM_LIMIT])
def test_missing_incomplete_or_oversized_template_content_fails_closed(raw):
    value, _ = inventory(f"{TEMPLATE} masked\n".encode(), sources={TEMPLATE: raw})
    with pytest.raises(g.r.ObservationError, match="TEMPLATE_CONTENT"):
        value.startup_manager()


@pytest.mark.parametrize("raw", [b"# /dev/null\n", b"# /etc/systemd/system/fixture@.service\n"])
def test_masked_template_header_is_valid_but_still_collected(raw):
    value, trace = inventory(f"{TEMPLATE} masked\n".encode(), sources={TEMPLATE: raw})
    assert value.startup_manager()["unit_count"] == 1
    assert trace[-1][0] == ["cat", "--", TEMPLATE]


@pytest.mark.parametrize("line", [b"fixture@.service\n", b"fixture@.service unknown enabled\n",
                                  b"fixture@.service disabled enabled extra\n"])
def test_template_file_state_is_required_and_validated(line):
    value, trace = inventory(line, sources={TEMPLATE: SOURCE})
    with pytest.raises(g.r.ObservationError, match="UNIT_FILE_STATE"):
        value.startup_manager()
    assert all(call[0] != "cat" for call, _ in trace)


@pytest.mark.parametrize("key", ["expected_units", "domain_units"])
def test_template_cannot_stand_in_for_a_declared_runtime_unit(key):
    value, _ = inventory(f"{TEMPLATE} disabled\n".encode(), sources={TEMPLATE: SOURCE})
    value.description[key] = [dict(name=TEMPLATE)]
    with pytest.raises(g.r.ObservationError, match="UNIT_TEMPLATE"):
        value.startup_manager()


@pytest.fixture
def private_bus(tmp_path):
    """Only a private D-Bus, with no service activation or real systemd manager."""
    executables = ["/usr/bin/dbus-daemon", "/usr/bin/systemctl"]
    if not all(os.path.isfile(path) and os.access(path, os.X_OK) for path in executables):
        pytest.skip("native private D-Bus/systemctl fixture unavailable")
    runtime = tmp_path / "run"
    runtime.mkdir(mode=0o700)
    units = tmp_path / "units"
    units.mkdir()
    config = tmp_path / "bus.conf"
    config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=' + str(runtime) +
                      '</listen><auth>EXTERNAL</auth><policy context="default">'
                      '<allow send_destination="*"/><allow receive_sender="*"/>'
                      '<allow own="*"/></policy></busconfig>')
    daemon = subprocess.Popen([executables[0], "--config-file=" + str(config), "--nofork", "--print-address=1"],
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=dict(g.ENVIRONMENT))
    try:
        assert select.select([daemon.stdout], [], [], 5)[0], "private bus did not report its address"
        address = daemon.stdout.readline().decode().strip()
        if not address:
            _, errors = daemon.communicate(timeout=5)
            if b"Failed to open socket: Operation not permitted" in errors:
                pytest.skip("sandbox forbids private Unix sockets; no manager connection attempted")
            pytest.fail("private D-Bus startup failed: " + errors.decode("utf-8", "replace"))
        assert address.startswith("unix:")
        environment = dict(g.ENVIRONMENT, HOME=str(tmp_path), XDG_RUNTIME_DIR=str(runtime),
                           DBUS_SESSION_BUS_ADDRESS=address, SYSTEMD_UNIT_PATH=str(units))
        yield units, environment
    finally:
        daemon.terminate()
        daemon.communicate(timeout=5)


def native_cat(environment, name):
    return subprocess.run(["/usr/bin/systemctl", "--user", "--no-pager", "--no-ask-password", "cat", "--", name],
                          stdin=subprocess.DEVNULL, capture_output=True, env=environment, timeout=5, check=False)


def test_native_cat_template_reads_fragment_and_dropin_without_manager(private_bus):
    units, environment = private_bus
    (units / TEMPLATE).write_text("[Service]\nExecStart=/usr/bin/true\n[Install]\nDefaultInstance=unused\n")
    dropins = units / (TEMPLATE + ".d")
    dropins.mkdir()
    (dropins / "override.conf").write_text("[Service]\nWorkingDirectory=/fixture/protected\n")
    result = native_cat(environment, TEMPLATE)
    assert result.returncode == 0 and result.stderr == b""
    assert b"DefaultInstance=unused" in result.stdout
    assert b"WorkingDirectory=/fixture/protected" in result.stdout
    value, _ = inventory(f"{TEMPLATE} disabled\n".encode(), sources={TEMPLATE: result.stdout})
    with pytest.raises(g.r.ObservationError, match="UNDECLARED_BUSINESS_UNIT"):
        value.startup_manager()


@pytest.mark.parametrize("mask", ["symlink", "empty"])
def test_native_cat_masked_template_has_header_and_no_runtime_properties(private_bus, mask):
    units, environment = private_bus
    path = units / TEMPLATE
    if mask == "symlink":
        path.symlink_to("/dev/null")
    else:
        path.write_bytes(b"")
    result = native_cat(environment, TEMPLATE)
    assert result.returncode == 0 and result.stderr == b""
    assert result.stdout.startswith(b"# /") and len(result.stdout.splitlines()) == 1
    value, _ = inventory(f"{TEMPLATE} masked\n".encode(), sources={TEMPLATE: result.stdout})
    assert value.startup_manager()["unit_count"] == 1
