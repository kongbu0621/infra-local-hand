"""Synthetic guest-phase verification; never connects to the original guest."""
from __future__ import annotations

import copy
import os
import sys
import time
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux guest helper", allow_module_level=True)

from e3_host import q2_journal_growth_guest as g


UUID = "11111111-2222-3333-4444-555555555555"
NEW_BOOT = "22222222-3333-4444-5555-666666666666"


@pytest.mark.parametrize("kind", [g.resource.RLIMIT_CPU, g.resource.RLIMIT_FSIZE])
def test_inherited_mutator_kill_limit_stops_before_descriptor(monkeypatch, kind):
    messages = []
    monkeypatch.setattr(g.os, "geteuid", lambda: 0)
    monkeypatch.setattr(g.resource, "getrlimit", lambda key: (1, 1) if key == kind else (-1, -1))
    monkeypatch.setattr(g, "emit", lambda value, *_: messages.append(value))
    assert g.entry(b"not a descriptor") == 3
    assert messages[0]["reason"] == "GROWTH_INHERITED_MUTATOR_LIMIT"


def rows():
    result = []
    for index, role in enumerate(g.r.ROLES):
        result.append(dict(role=role, path="/fixture/" + role,
            directory=dict(dev=12 + index, ino=2, mode=0o40755, uid=0, gid=0),
            filesystem=dict(uuid=UUID, mount=dict(root="/", path="/fixture/" + role, fstype="ext4",
                options=["rw"], device=12 + index, source="/dev/vdc", mount_id=20 + index)),
            available=dict(bytes=500 * 1048576, inodes=65536)))
    return result


def description():
    samples = rows()
    return dict(schema=g.SCHEMA, session=g.SESSION, phase="pre", nonce="a" * 64,
        source_binding_sha256="b" * 64, paths={row["role"]: row["path"] for row in samples},
        saved_rows=samples, original_boot_id=UUID, journal_serial="lh-journal",
        expected_units=[dict(name="old.service", control_group="/old.service")],
        domain_cgroups=["/old.slice"], domain_units=[dict(name="old.slice", manager="system", control_group="/old.slice")],
        protected_roots=["/fixture"], essential_paths=["/fixture/evidence"], window_seconds=900, change_seconds=780)


def tree():
    return dict(entries=1, content_bytes=9, sha256="c" * 64, observation_sha256="d" * 64)


def device(size=g.OLD_SIZE):
    return dict(path="/dev/vdc", uuid=UUID, serial="lh-journal", block_bytes=size,
        node=dict(mode=0o60660, uid=0, gid=6),
        superblock=dict(uuid=UUID, features=[60, 706, 1131], block_size=4096, filesystem_bytes=g.OLD_SIZE))


def tool():
    return dict(path="/usr/sbin/resize2fs", identity=dict(dev=1, ino=80, mode=0o100755, uid=0, gid=0, nlink=1),
                bytes=100, sha256="e" * 64, version_sha256="f" * 64)


def pre_report():
    desc = description()
    return dict(schema=g.REPORT_SCHEMA, session=g.SESSION, phase="pre", status="GUEST_QUIET",
        nonce=desc["nonce"], source_binding_sha256=desc["source_binding_sha256"], boot_id=UUID,
        rows=rows(), tree=tree(), journal_device=device(), resize2fs=tool(), quiescence=dict(historical_exit="UNKNOWN"),
        resource_observation=dict(self_cpu_microseconds=1000, exited_children_cpu_microseconds=100,
            self_peak_rss_bytes=100000, exited_child_peak_rss_bytes=100000, coverage="THROUGH_REPORT_ONLY", complete=False))


def post_description():
    result = description()
    result.update(phase="post", pre_report=pre_report(), pre_report_sha256=g.digest(g.canonical(pre_report())))
    return result


@pytest.mark.parametrize("change", [dict(session="another"), dict(phase="shell"), dict(nonce="x"),
    dict(window_seconds=901), dict(change_seconds=781), dict(change_seconds=0), dict(original_boot_id="invalid"),
    dict(protected_roots=["/fixture/../other"]), dict(essential_paths=[]),
    dict(domain_cgroups=["/old.slice", "/old.slice"]), dict(extra=True),
    dict(expected_units=[dict(name="x.service; rm", control_group=None)])])
def test_descriptor_rejects_scope_expansion(change):
    value = description(); value.update(change)
    with pytest.raises(g.r.ObservationError):
        g.descriptor(g.canonical(value))


def test_descriptor_post_binds_exact_pre_report_and_identity():
    value = post_description()
    assert g.descriptor(g.canonical(value)) == value
    value["pre_report"]["nonce"] = "0" * 64
    with pytest.raises(g.r.ObservationError, match="DIGEST"):
        g.descriptor(g.canonical(value))
    value["pre_report_sha256"] = g.digest(g.canonical(value["pre_report"]))
    with pytest.raises(g.r.ObservationError, match="PRE_REPORT"):
        g.descriptor(g.canonical(value))


def test_parser_rejects_duplicate_json_and_noninteger_window():
    raw = g.canonical(description()).replace(b'"window_seconds":900', b'"window_seconds":900,"window_seconds":900')
    with pytest.raises(g.r.ObservationError, match="DUPLICATE"):
        g.descriptor(raw)
    value = description(); value["window_seconds"] = True
    with pytest.raises(g.r.ObservationError):
        g.descriptor(g.canonical(value))


@pytest.mark.parametrize("suffix", [b"", b"extra", b"\n"])
def test_exact_continuation_and_eof(suffix):
    expected = g.continue_token("a" * 64, "b" * 64)
    assert expected.startswith(b"POWER_OFF lhqjgrow-20261006a ")
    read, write = os.pipe()
    try:
        os.write(write, expected + suffix); os.close(write); write = None
        if suffix:
            with pytest.raises(g.r.ObservationError, match="LIMIT"):
                g.receive_token(expected, lambda: None, fd=read)
        else:
            g.receive_token(expected, lambda: None, fd=read)
    finally:
        os.close(read)
        if write is not None: os.close(write)


def test_incomplete_token_never_poweroffs():
    read, write = os.pipe()
    os.write(write, b"POWER_OFF"); os.close(write)
    try:
        with pytest.raises(g.r.ObservationError, match="TOKEN"):
            g.receive_token(g.continue_token("a" * 64, "b" * 64), lambda: None, fd=read)
    finally:
        os.close(read)


def test_window_uses_both_clocks_and_no_deadline_reset():
    now = {time.CLOCK_MONOTONIC: 0, time.CLOCK_BOOTTIME: 0}
    window = g.GuestWindow(900, 780, clock=now.__getitem__)
    now[time.CLOCK_BOOTTIME] = 780 * 10**9
    with pytest.raises(g.r.ObservationError, match="CHANGE_DEADLINE"):
        window.check(change=True)
    window.check()
    now[time.CLOCK_BOOTTIME] = 900 * 10**9
    with pytest.raises(g.r.ObservationError, match="DEADLINE"):
        window.check()


def test_overdue_command_is_not_killed():
    until = time.monotonic() + 0.05
    def check():
        if time.monotonic() >= until:
            raise TimeoutError("elapsed")
    command = g.GuestCommand([sys.executable, "-I", "-B", "-c", "import time;time.sleep(.25)"], check)
    try:
        with pytest.raises(TimeoutError): command.collect()
        assert command.process.poll() is None
    finally:
        command.process.wait(timeout=3)


def test_output_overflow_is_bounded():
    command = g.GuestCommand([sys.executable, "-I", "-B", "-c", "print('x'*300)"], lambda: None, limit=16)
    try:
        with pytest.raises(g.r.ObservationError, match="OUTPUT"):
            command.collect()
        assert len(command.output["stdout"]) == 17
    finally:
        command.process.wait(timeout=3)


class Window:
    def check(self, change=False):
        pass


@pytest.fixture
def effects(monkeypatch):
    trace = []
    class Inventory:
        systemctl = dict(path="/usr/bin/systemctl")
        def __init__(self, *_): pass
        def collect(self):
            trace.append("quiet")
            return dict(historical_exit="UNKNOWN")
    monkeypatch.setattr(g, "GuestInventory", Inventory)
    monkeypatch.setattr(g, "tool_binding", lambda *a, **k: tool())
    monkeypatch.setattr(g, "verify_tool", lambda *a, **k: trace.append("tool"))
    monkeypatch.setattr(g, "boot_id", lambda _: UUID)
    class Command:
        process = SimpleNamespace(pid=200, poll=lambda: 0)
        def collect(self):
            return dict(returncode=0, stdout=b"", stderr=b"", both_eof=True, pid=200)
        def close(self): pass
    def command(binding, args, *_a, **_k):
        trace.append((binding["path"], tuple(args)))
        return Command()
    monkeypatch.setattr(g, "bound_command", command)
    def prepare(desc):
        maintenance = g.GuestMaintenance(desc, window=Window())
        maintenance.observation = SimpleNamespace(reopen=lambda: trace.append("reopen"), close=lambda: None)
        maintenance.sample = lambda: rows()
        maintenance.journal_tree = lambda: (trace.append("tree") or tree())
        def observed(samples, size):
            value = device(size)
            maintenance.device = SimpleNamespace(path="/dev/vdc", recheck=lambda: trace.append("device"), close=lambda: None,
                read_superblock=lambda: dict(value["superblock"], filesystem_bytes=g.NEW_SIZE),
                report=lambda: dict(value, superblock=maintenance.device.superblock))
            return value
        maintenance.observe_device = observed
        return maintenance
    return trace, prepare


def test_pre_report_is_durable_handshake_before_poweroff(effects):
    trace, prepare = effects
    maintenance = prepare(description())
    output = []
    def receive(token, check):
        assert len(output) == 1 and output[0]["status"] == "GUEST_QUIET"
        assert not any(isinstance(item, tuple) for item in trace)
        assert token == g.continue_token(description()["nonce"], g.digest(g.canonical(output[0])))
        trace.append("host_saved_pre")
    maintenance.pre(output=output.append, receive=receive)
    assert [value["status"] for value in output] == ["GUEST_QUIET", "POWER_OFF_REQUESTED"]
    assert trace.count("tree") == 1 and trace.count("quiet") == 2
    assert trace.index("host_saved_pre") < trace.index(("/usr/bin/systemctl", ("--system", "--no-pager", "--no-ask-password", "poweroff")))
    assert maintenance.started == {"poweroff"}


def test_missing_or_bad_host_continuation_has_no_mutation(effects):
    trace, prepare = effects
    maintenance = prepare(description())
    def fail(*_): raise g.r.ObservationError("GROWTH_CONTINUE_TOKEN")
    with pytest.raises(g.r.ObservationError, match="TOKEN"):
        maintenance.pre(output=lambda _: None, receive=fail)
    assert maintenance.started == set() and not any(isinstance(item, tuple) for item in trace)


def test_pre_boot_change_has_no_poweroff(effects, monkeypatch):
    trace, prepare = effects
    monkeypatch.setattr(g, "boot_id", lambda _: NEW_BOOT)
    maintenance = prepare(description())
    with pytest.raises(g.r.ObservationError, match="ORIGINAL_BOOT"):
        maintenance.pre(output=lambda _: pytest.fail("no pre report"))
    assert not trace


def test_post_no_new_boot_prevents_resize(effects):
    trace, prepare = effects
    maintenance = prepare(post_description())
    with pytest.raises(g.r.ObservationError, match="NEW_BOOT"):
        maintenance.post(output=lambda _: pytest.fail("no post report"))
    assert maintenance.started == set() and not trace


def test_post_exactly_one_resize_and_only_final_tree_scan(effects, monkeypatch):
    trace, prepare = effects
    monkeypatch.setattr(g, "boot_id", lambda _: NEW_BOOT)
    maintenance = prepare(post_description())
    output = []
    report = maintenance.post(output=output.append)
    assert report["status"] == "FILESYSTEM_GROWN" and report["boot_id"] == NEW_BOOT
    assert report["original_boot_id"] == UUID and report["resize_result"]["both_eof"]
    assert trace.count("tree") == 1 and trace.count(("/usr/sbin/resize2fs", ("/dev/vdc",))) == 1
    assert trace.index(("/usr/sbin/resize2fs", ("/dev/vdc",))) < trace.index("tree")
    with pytest.raises(g.r.ObservationError, match="NO_RETRY"):
        maintenance.post(output=output.append)
    assert len(output) == 1


def test_post_changed_content_reports_failure_after_single_resize(effects, monkeypatch):
    trace, prepare = effects
    monkeypatch.setattr(g, "boot_id", lambda _: NEW_BOOT)
    maintenance = prepare(post_description())
    maintenance.journal_tree = lambda: dict(tree(), sha256="0" * 64)
    with pytest.raises(g.r.ObservationError, match="TREE_CHANGED") as failure:
        maintenance.post(output=lambda _: pytest.fail("failure cannot emit success"))
    report = maintenance.failure(failure.value)
    assert report["status"] == "INCOMPLETE" and report["actions_started"] == ["resize2fs"]
    assert trace.count(("/usr/sbin/resize2fs", ("/dev/vdc",))) == 1


def test_post_capacity_failure_cannot_emit_success(effects, monkeypatch):
    trace, prepare = effects
    monkeypatch.setattr(g, "boot_id", lambda _: NEW_BOOT)
    maintenance = prepare(post_description())
    samples = rows(); samples[3]["available"]["bytes"] = 399 * 1048576
    maintenance.sample = lambda: samples
    with pytest.raises(g.r.ObservationError, match="TARGET_CAPACITY"):
        maintenance.post(output=lambda _: pytest.fail("insufficient capacity"))


@pytest.mark.parametrize("key,value", [("uuid", NEW_BOOT), ("serial", "other"), ("block_bytes", g.NEW_SIZE)])
def test_pre_device_binding_rejected(key, value):
    report = pre_report(); report["journal_device"][key] = value
    with pytest.raises(g.r.ObservationError, match="PRE_JOURNAL"):
        g.validate_pre_report(report, description())


def test_property_batch_rejects_duplicate_missing_extra_units(monkeypatch):
    inventory = object.__new__(g.GuestInventory)
    base = b"Id=x.service\nLoadState=not-found\nActiveState=inactive\nSubState=dead\n"
    for raw in (base + b"Id=x.service\n", base.replace(b"x.service", b"other.service"), b"Id=x.service\n"):
        inventory.ctl = lambda *a, raw=raw, **k: raw
        with pytest.raises(g.r.ObservationError): inventory.show_many(["x.service"])
    inventory.ctl = lambda *a, **k: base
    assert inventory.show_many(["x.service"])["x.service"]["LoadState"] == "not-found"


def test_unloaded_but_activatable_unit_is_not_quiet():
    inventory = object.__new__(g.GuestInventory)
    value = {key: "" for key in inventory.SHOW}
    value.update(Id="x.service", LoadState="not-found", ActiveState="inactive", SubState="dead", TriggeredBy="x.timer")
    inventory.show = lambda _: value
    with pytest.raises(g.r.ObservationError, match="ACTIVATION"):
        inventory.quiet_service(dict(name="x.service", control_group=None))


def test_known_scope_paths_do_not_match_similar_prefix():
    assert g.under("/fixture/journal/a", ["/fixture/journal"])
    assert not g.under("/fixture/journal-other/a", ["/fixture/journal"])


def test_start_time_uses_last_parenthesis_not_process_name():
    raw = b"18 (odd ) name) S " + b"0 " * 18 + b"123 0 0\n"
    assert g.process_start(raw) == 123


def test_self_process_fd_inventory_keeps_its_scandir_fd_alive(monkeypatch):
    # A real scan of only this synthetic pytest process catches listdir's
    # ephemeral-fd bug without inspecting another process or the field VM.
    # The execution sandbox may translate getpid without remounting procfs.
    # Bind this synthetic test to procfs's own self identity explicitly.
    pid = os.readlink("/proc/self")
    monkeypatch.setattr(os, "getpid", lambda: int(pid))
    original_listdir = os.listdir
    monkeypatch.setattr(os, "listdir", lambda path: [pid] if path == "/proc" else original_listdir(path))
    inventory = object.__new__(g.GuestInventory)
    inventory.roots = ["/definitely-not-a-synthetic-test-path"]
    inventory.check = lambda: None
    result = inventory.processes()
    assert result["processes"] == 1 and result["fd_count"] >= 3


@pytest.mark.parametrize("field,value", [("block_bytes", g.OLD_SIZE), ("serial", "other")])
def test_host_post_validator_rejects_wrong_device(field, value, effects, monkeypatch):
    _, prepare = effects
    monkeypatch.setattr(g, "boot_id", lambda _: NEW_BOOT)
    desc = post_description()
    report = prepare(desc).post(output=lambda _: None)
    report["journal_device"][field] = value
    with pytest.raises(g.r.ObservationError, match="POST_DEVICE"):
        g.validate_post_report(report, desc)


def test_resource_report_cannot_claim_complete_or_hide_negative_usage():
    value = pre_report()["resource_observation"]
    for changed in (dict(value, complete=True), dict(value, self_cpu_microseconds=-1),
                    dict(value, self_cpu_microseconds=120000001)):
        with pytest.raises(g.r.ObservationError): g.validate_resources(changed)


def test_unclassified_enabled_scheduler_names_exact_blocking_unit():
    inventory = object.__new__(g.GuestInventory)
    inventory.description = description()
    inventory.roots = ["/fixture"]
    inventory.context = {}
    inventory.check = lambda: None
    inventory.ctl = lambda *a, **k: b"cron.service enabled enabled\n"
    unit = {key: "" for key in inventory.SHOW}
    unit.update(Id="cron.service", LoadState="loaded", ActiveState="active", SubState="running",
                UnitFileState="enabled", ExecStart="{ path=/usr/sbin/cron ; argv[]=/usr/sbin/cron -f ; }")
    inventory.show_many = lambda *a, **k: {"cron.service": unit}
    with pytest.raises(g.r.ObservationError, match="INDIRECT_STARTUP_UNVERIFIED"):
        inventory.startup_manager()
    assert inventory.context == dict(manager="system", unit="cron.service", action_kind="cron")


def test_actual_active_writer_is_rejected_even_inside_self(monkeypatch, tmp_path):
    # The helper's own file descriptors are not exempt from writer checks.
    pid = os.readlink("/proc/self")
    monkeypatch.setattr(os, "getpid", lambda: int(pid))
    original_listdir = os.listdir
    monkeypatch.setattr(os, "listdir", lambda path: [pid] if path == "/proc" else original_listdir(path))
    target = tmp_path / "evidence"
    fd = os.open(target, os.O_CREAT | os.O_RDWR | os.O_EXCL, 0o600)
    inventory = object.__new__(g.GuestInventory)
    inventory.roots = [str(tmp_path)]
    inventory.check = lambda: None
    try:
        with pytest.raises(g.r.ObservationError, match="UNKNOWN_WRITER"):
            inventory.processes()
    finally:
        os.close(fd)
