"""Real coordinator, synthetic effects: no SSH, image change or VM execution."""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux maintenance coordinator", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as guest


BOOT = "10000000-0000-4000-8000-000000000001"
NEW_BOOT = "20000000-0000-4000-8000-000000000001"
ORDER = ["marker", "pre_ssh", "pre_report", "poweroff", "pre_finish", "backup",
         "image_resize", "qemu_start", "post_ssh", "filesystem_resize", "post_finish", "verify"]


@pytest.fixture
def rig(monkeypatch, tmp_path):
    # The effects and identity in this fixture model the ordinary coordinator.
    monkeypatch.setattr(h.os, "geteuid", lambda: 1000)
    actions, events, files, failure, clock, errors = [], [], {}, [None], [0.0], []
    safe_reason = h.prior.safe_reason
    def reason(error):
        errors.append(repr(error))
        return safe_reason(error)
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    def effect(name):
        actions.append(name)
        if failure[0] == name:
            raise RuntimeError("INJECTED_" + name.upper())
    def nothing(*_args, **_kwargs):
        return None
    class Store:
        def __init__(self, fd, check):
            self.fd, self.opened = fd, {}
        def absent(self):
            assert not self.opened
        capacity = nothing
        def put(self, name, raw):
            assert name not in self.opened
            self.opened[name] = None
            files[name] = raw
            if name == "consumed.json":
                effect("marker")
        def event(self, value):
            events.append(value)
        def budget(self):
            return {"bytes": sum(map(len, files.values())), "files": len(files)}
        def close(self):
            for key, fd in self.opened.items():
                if type(fd) is int:
                    os.close(fd)
                    self.opened[key] = None
    class Process:
        def __init__(self, pid, *_args):
            self.pid, self.dead = pid, False
        def recheck(self):
            assert not self.dead
            return {"pid": self.pid}
        def exited(self):
            return self.dead
        close = nothing
    old = Process(111)
    class Images:
        journal_fd, journal_path, journal_serial = 43, "/fixed/journal.qcow2", "fixed-journal"
        recheck = capacity = checkpoint = close = nothing
        def image_keys(self):
            return {"journal": [1, 2]}
        def verify_writers(self, pid):
            pytest.fail("removed host writer scan must never be called")
        def offline_info(self, _tool, size):
            assert old.dead and size == h.OLD_SIZE
            return {"virtual-size": size}
        def grow(self, _tool, backup):
            assert old.dead and "backup" in actions
            assert backup == str(tmp_path) + "/" + h.NAMES["journal.backup.qcow2"]
            effect("image_resize")
            return {"virtual-size": h.NEW_SIZE}
    class Tool:
        fd = 42
        recheck = close = nothing
        def binding(self):
            return {"fixed": "tool"}
        def run(self, args, *, vm=False):
            assert vm and old.dead and "image_resize" in actions
            assert args == ["fixed-arguments"]
            (tmp_path / h.NAMES["vm.pid"]).write_text("222\n")
            effect("qemu_start")
            return {"returncode": 0}
    pre = {"boot_id": BOOT, "tree": {"fixed": "preserved"}, "rows": ["saved"]}
    def descriptor(_frozen, nonce, phase, _window, prior=None):
        value = {"phase": phase, "nonce": nonce}
        if prior is not None:
            value["pre_report"] = prior
        return value
    class Transport:
        def __init__(self, _anchor, _store, argv, phase, _nonce, _sha, _boot, _check, *, validate=None):
            self.phase, self.validate = phase, validate
            self.output = {"stdout": bytearray(), "stderr": bytearray()}
            self.process = SimpleNamespace(pid=333 if phase == "pre" else 444, poll=lambda: 0)
            assert argv[0] == "/synthetic/ssh"
            effect(phase + "_ssh")
        def receive_report(self):
            if self.phase == "pre":
                effect("pre_report")
                value = pre
            else:
                assert actions.count("qemu_start") == 1
                effect("filesystem_resize")
                value = {"boot_id": NEW_BOOT, "tree": pre["tree"], "rows": ["grown"],
                         "pre_report_sha256": h.digest(h.canonical(pre))}
            if self.validate:
                self.validate(value)
            return value
        def continue_poweroff(self, sha):
            assert sha == h.digest(h.canonical(pre)) and "consumed.json" in files
            old.dead = True
            effect("poweroff")
        def finish(self):
            effect(self.phase + "_finish")
            return {"returncode": 0, "eof": {"stdout": True, "stderr": True}}
        close = nothing
    def backup(_store, fd):
        assert old.dead and fd == 43 and "image_resize" not in actions
        effect("backup")
        return {"sha256": "b" * 64}
    def compare(_report, _horizon):
        effect("verify")
        return {"pools": [{"bytes": {"deficit": 0}, "inodes": {"deficit": 0}}]}
    def advance(seconds):
        clock[0] += seconds
    window = SimpleNamespace(check=nothing, change=nothing, remaining=lambda limit=900: limit,
                             binding={"boot_id": BOOT, "origins": [0, 0]},
                             origins={"monotonic": 0, "boottime": 0},kernel_report={})
    anchor = SimpleNamespace(fd=parent, path=str(tmp_path), ssh=44, recheck=nothing,
                             absent=nothing, close=nothing, growth_inputs=nothing,
                             raw={"start.sh": b"fixed"}, retained={})
    inputs = SimpleNamespace(recheck=nothing, close=nothing)
    frozen = {"boot_id": BOOT, "source_binding_sha256": "a" * 64, "horizon": {},
              "anchor_path": str(tmp_path), "source_binding": {}, "inventory": {}}
    sources = {"q2_core_capacity_reader.py": b"pass", "q2_journal_growth_guest.py": b"pass"}
    vm = {"images": Images(), "process": old, "restart_argv": ["qemu", "fixed-arguments"],
          "binding": {}, "original_argv": ["qemu", "old-arguments"]}
    tools = {"image": Tool(), "qemu": Tool()}
    monkeypatch.setattr(h, "Store", Store)
    monkeypatch.setattr(h, "COMMANDS", [])
    monkeypatch.setattr(h, "management_usage", lambda: {"complete": True,"cpu_seconds":0.01,"rss_upper_observation_bytes":100})
    monkeypatch.setattr(h, "run_tool", lambda *_args, **_kwargs: {"stderr": b""})
    monkeypatch.setattr(h, "growth_descriptor", descriptor)
    monkeypatch.setattr(h.local, "make_argv", lambda *_args: ["/synthetic/ssh", "fixed-host", "unused"])
    monkeypatch.setattr(h, "MaintenanceTransport", Transport)
    monkeypatch.setattr(h, "full_backup", backup)
    monkeypatch.setattr(h, "ProcessIdentity", Process)
    monkeypatch.setattr(h, "pidfile", lambda *_args: 222)
    monkeypatch.setattr(h, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=advance))
    monkeypatch.setattr(guest, "validate_pre_report", nothing)
    monkeypatch.setattr(guest, "validate_post_report", nothing)
    monkeypatch.setattr(guest, "verify_preservation", nothing)
    monkeypatch.setattr(guest, "validate_completion", nothing)
    monkeypatch.setattr(h.prior, "compare", compare)
    monkeypatch.setattr(h.prior, "safe_reason", reason)
    work = h.Maintenance(anchor, inputs, frozen, sources, vm, tools, window, "d" * 40)
    manifest = work.preflight()
    value = SimpleNamespace(work=work, actions=actions, failure=failure, events=events, files=files,
        pre=pre, anchor=anchor, inputs=inputs, frozen=frozen, sources=sources, vm=vm, tools=tools,
        window=window, clock=clock, manifest=manifest, nothing=nothing, errors=errors)
    yield value
    work.store.close()
    os.close(parent)


def test_real_coordinator_orders_exactly_two_ssh_and_one_restart(rig):
    result = rig.work.run(rig.manifest)
    assert result["state"] == "VERIFIED", (result, rig.errors)
    assert rig.actions == ORDER
    assert result["ssh_requests"] == 2 and result["business_cases"] == 0
    assert result["production_supported"] is False
    assert result['host_writer_observation']=='NOT_PERFORMED'
    assert result['continuous_exclusion_proven'] is False
    assert 'writer_reports' not in result and result['schema']=='lhq-journal-growth-receipt/v2'
    assert rig.clock[0] >= 60
    assert rig.files["consumed.json"] and rig.files["receipt.json"]
    started = [row["step"] for row in rig.events if row.get("state") == "STARTED"]
    assert started == list(h.STATES[1:])
    assert rig.actions.index("backup") < rig.actions.index("image_resize") < rig.actions.index("qemu_start")
    assert rig.actions.index("poweroff") < rig.actions.index("backup")


@pytest.mark.parametrize("stop", ORDER)
def test_effect_failure_never_runs_a_later_effect_or_retries(rig, stop):
    rig.failure[0] = stop
    result = rig.work.run(rig.manifest)
    assert result["state"] == "STOP_AND_RETAIN", result
    assert rig.actions == ORDER[:ORDER.index(stop) + 1]
    assert rig.actions.count(stop) == 1
    assert result["ssh_requests"] <= 2 and result["business_cases"] == 0
    assert result["production_supported"] is False


def test_oversize_post_descriptor_blocks_before_poweroff_token(rig):
    # Pre transport admits a report under its 1 MiB cap, but embedding it in the
    # post command would exceed the independently bounded 64 KiB descriptor.
    rig.pre["tree"] = {"retained_entry": "x" * 65536}
    result = rig.work.run(rig.manifest)
    assert result["state"] == "STOP_AND_RETAIN", result
    assert result["reason"] == "GROWTH_BUNDLE_INPUT"
    assert rig.actions == ORDER[:3]
    assert result["ssh_requests"] == 1


def test_root_coordinator_is_rejected_before_source_or_field_reads(rig, monkeypatch, capsys):
    monkeypatch.setattr(h.os, "geteuid", lambda: 0)
    monkeypatch.setattr(h.sys, "argv", ["growth", "--frame", "frame", "--plan-archive", "plan",
        "--archives-dir", "archives", "--expected-commit", "d" * 40, "--trusted-single-admin"])
    def unexpected(*args):
        pytest.fail("root must be rejected before source or field admission")
    monkeypatch.setattr(h, "growth_sources", unexpected)
    monkeypatch.setattr(h, "freeze_growth_inputs", unexpected)
    assert h.main() == 3
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "GROWTH_ORDINARY_COORDINATOR"
    assert result["marker_created"] is False and result["ssh_requests"] == 0
    assert rig.actions == []


@pytest.mark.parametrize("stale", ["digest", "missing_scope", "A", "C", "D"])
def test_main_manifest_mismatch_creates_no_marker_or_transport(rig, monkeypatch, capsys, stale):
    old=json.loads(h.canonical(rig.manifest))
    if stale=='missing_scope': old.pop('A')
    elif stale!='digest': old[stale]='0'*40
    rig.window.binding['origins']=[1,2]
    handoff=h.make_preflight('d'*40,h.digest(h.canonical(rig.manifest)),rig.window.binding,
        rig.work.nonce,dict(cpu_nanoseconds=1,rss_peak_bytes=1))
    expected = "0" * 64 if stale == "digest" else h.digest(h.canonical(old))
    monkeypatch.setattr(h.sys, "argv", ["growth", "--frame", "frame", "--plan-archive", "plan",
        "--archives-dir", "archives", "--expected-commit", "d" * 40, "--expected-manifest", expected,
        "--window-binding", h.canonical(rig.window.binding).decode(), "--preflight",h.canonical(handoff).decode(),
        "--trusted-single-admin", "--execute"])
    monkeypatch.setattr(h.prior, "Inputs", lambda: rig.inputs)
    monkeypatch.setattr(h, "growth_sources", lambda _commit: rig.sources)
    monkeypatch.setattr(h, "Window", lambda: rig.window)
    monkeypatch.setattr(h, "bind_window", rig.nothing)
    monkeypatch.setattr(h, "freeze_growth_inputs", lambda *_args: rig.frozen)
    monkeypatch.setattr(h, "GrowthAnchor", lambda *_args: rig.anchor)
    monkeypatch.setattr(h, "Tool", lambda *_args: rig.tools["image"])
    monkeypatch.setattr(h, "freeze_vm", lambda *_args: rig.vm)
    monkeypatch.setattr(h.Store, "absent", rig.nothing)
    monkeypatch.setattr(rig.vm["images"], "image_keys", lambda: {})
    monkeypatch.setattr(rig.work, "preflight", lambda: rig.manifest)
    monkeypatch.setattr(h, "Maintenance", lambda *_args: rig.work)
    monkeypatch.setattr(h, "resource", SimpleNamespace(RLIMIT_AS=1, RLIMIT_NOFILE=2,
        RLIMIT_CPU=3, RLIMIT_FSIZE=4, RLIM_INFINITY=-1,
        getrlimit=lambda kind: (-1, -1) if kind in (3, 4) else (100, 100), setrlimit=rig.nothing))
    assert h.main() == 3
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "GROWTH_MANIFEST_NOT_FROZEN"
    assert result["marker_created"] is False and result["ssh_requests"] == 0
    assert rig.actions == [] and rig.files == {} and rig.work.transports == []


def test_expired_seal_retains_cached_live_processes(rig, monkeypatch):
    command = SimpleNamespace(is_vm=False, identity={"pid": 777, "starttime": 88},
                              process=SimpleNamespace(pid=777, poll=lambda: None))
    monkeypatch.setattr(h, "COMMANDS", [command])
    def expired():
        if "poweroff" in rig.actions:
            raise h.prior.r.ObservationError("DEADLINE")
    rig.window.check = expired
    value = rig.work.run(rig.manifest)
    assert value["state"] == "UNKNOWN" and value["seal"] == "INCOMPLETE"
    assert value["processes"] == [{"identity": command.identity, "exit": None, "vm": False}]
    assert value["marker_created"] is True and "image_resize" not in rig.actions
    assert value["transports"][0]["pid"] == 333


def test_execute_without_original_window_stops_before_field_reads(rig, monkeypatch, capsys):
    monkeypatch.setattr(h.sys, "argv", ["growth", "--frame", "frame", "--plan-archive", "plan",
        "--archives-dir", "archives", "--expected-commit", "d" * 40,
        "--trusted-single-admin", "--execute"])
    monkeypatch.setattr(h, "growth_sources", lambda _: rig.sources)
    def unexpected(*args):
        pytest.fail("field inputs must not be read without original window")
    monkeypatch.setattr(h, "freeze_growth_inputs", unexpected)
    assert h.main() == 3
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "GROWTH_ORIGINAL_WINDOW_REQUIRED"
    assert result["marker_created"] is False and result["ssh_requests"] == 0


def test_management_premise_is_required_before_window(rig,monkeypatch,capsys):
    monkeypatch.setattr(h.sys,"argv",["growth","--frame","frame","--plan-archive","plan",
        "--archives-dir","archives","--expected-commit","d"*40])
    monkeypatch.setattr(h,"growth_sources",lambda _:rig.sources)
    monkeypatch.setattr(h,"Window",lambda:pytest.fail("unconfirmed premise must not start a window"))
    assert h.main()==3
    result=json.loads(capsys.readouterr().out)
    assert result['reason']=='GROWTH_ACCESS_PREMISE' and not result['marker_created']


def test_boot_open_failure_retains_origins_and_never_reads_inputs(rig, monkeypatch, capsys):
    monkeypatch.setattr(h.sys, "argv", ["growth", "--frame", "frame", "--plan-archive", "plan",
        "--archives-dir", "archives", "--expected-commit", "d" * 40,
        "--trusted-single-admin"])
    monkeypatch.setattr(h, "growth_sources", lambda _: rig.sources)
    def denied(check, report):
        error = guest.r.ObservationError("GROWTH_KERNEL_OPEN")
        error.diagnostic = dict(operation="open_kernel", target="boot", errno=1)
        raise error
    def unexpected(*args):
        pytest.fail("boot failure must stop before field inputs")
    monkeypatch.setattr(guest, "host_boot_id", denied)
    monkeypatch.setattr(h, "freeze_growth_inputs", unexpected)
    assert h.main() == 3
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "GROWTH_KERNEL_OPEN"
    assert result["diagnostic"] == dict(operation="open_kernel", target="boot", errno=1)
    assert set(result["window_binding"]) == {"origins"}
    assert len(result["window_binding"]["origins"]) == 2
    assert result["marker_created"] is False and result["ssh_requests"] == 0


def test_ordinary_preflight_carries_original_cpu_and_peak_rss(monkeypatch):
    previous=dict(cpu_nanoseconds=25_000_000_000,rss_peak_bytes=80*h.MIB)
    value=[dict(cpu_seconds=2,rss_upper_observation_bytes=40*h.MIB)]
    monkeypatch.setattr(h,'management_usage',lambda:value[0])
    monkeypatch.setattr(h.resource,'getrusage',lambda kind:SimpleNamespace(ru_maxrss=100*h.MIB//1024))
    usage=h.Usage(previous)
    first=usage.sample()
    assert first==dict(cpu_nanoseconds=27_000_000_001,rss_peak_bytes=100*h.MIB)
    # Repeated sampling of this process adds its cumulative time once, rather
    # than summing snapshots; peak RSS never resets at process handoff.
    value[0]['cpu_seconds']=3
    assert usage.sample()==dict(cpu_nanoseconds=28_000_000_001,rss_peak_bytes=100*h.MIB)
    value[0]['cpu_seconds']=96
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_MANAGEMENT_BUDGET'):
        usage.sample()
    assert previous==dict(cpu_nanoseconds=25_000_000_000,rss_peak_bytes=80*h.MIB)


@pytest.mark.parametrize('change',['old_schema','writer_fields','missing','cpu_zero','cpu_bool',
    'cpu_limit','rss_zero','rss_limit','fresh_deadline','short_change','boot','origins'])
def test_ordinary_handoff_rejects_old_or_unbounded_inputs(change):
    value=h.make_preflight('d'*40,'a'*64,dict(boot_id=BOOT,origins=[1,2]),'b'*64,
        dict(cpu_nanoseconds=1,rss_peak_bytes=1))
    if change=='old_schema':value['schema']='lhq-journal-writer-preflight/v1'
    elif change=='writer_fields':value['writer']={}
    elif change=='missing':value.pop('usage')
    elif change=='cpu_zero':value['usage']['cpu_nanoseconds']=0
    elif change=='cpu_bool':value['usage']['cpu_nanoseconds']=True
    elif change=='cpu_limit':value['usage']['cpu_nanoseconds']=120_000_000_001
    elif change=='rss_zero':value['usage']['rss_peak_bytes']=0
    elif change=='rss_limit':value['usage']['rss_peak_bytes']=512*h.MIB+1
    elif change=='fresh_deadline':value['window_seconds']=901
    elif change=='short_change':value['change_seconds']=900
    elif change=='boot':value['window_binding']['boot_id']='invalid'
    else:value['window_binding']['origins']=[True,2]
    with pytest.raises(h.prior.r.ObservationError):h.parse_preflight(h.canonical(value))
