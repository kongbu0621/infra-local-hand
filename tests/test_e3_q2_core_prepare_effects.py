"""Real temporary-file effects; quota/service observations are explicit unit doubles.

These tests neither configure a quota nor run an original acceptance case.
"""
import copy
import errno
import os
from pathlib import Path
import stat
import struct
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux preparation effects", allow_module_level=True)

from test_e3_q2_core_prepare_plan import d, effect, translated


def test_missing_capacity_collectors_stops_before_clock_or_files(monkeypatch):
    e = d.FieldEffects({})
    e._installation_receipt = e._admission = {"synthetic": True}
    e._persistence_ready = True
    monkeypatch.setattr(d.os, "geteuid", lambda: 0)
    monkeypatch.setattr(d.os, "getegid", lambda: 0)
    monkeypatch.setattr(e, "now", lambda: pytest.fail("clock before dependency check"))
    with pytest.raises(d.DispatchError, match="CURRENT_FACTS_REQUIRED"):
        e.prepare_case(d.CASES[0], d.build_intent(d.CASES[0]), 100)


@pytest.mark.parametrize("operation", ["open", "fchown", "fchmod", "write", "fsync", "fstat", "pread", "stat"])
def test_late_file_syscall_is_last_noncleanup_effect(tmp_path, monkeypatch, operation):
    e = effect()
    events, opened = [], []
    with monkeypatch.context() as m:
        for name in ("open", "fchown", "fchmod", "write", "fsync", "fstat", "pread", "stat"):
            original = getattr(d.os, name)
            def call(*args, _name=name, _original=original, **kwargs):
                # Only the create-open, not path traversal, is delayed.
                selected = _name != "open" or args[0] == "new.json"
                result = _original(*args, **kwargs)
                if _name == "open": opened.append(result)
                if selected:
                    events.append(_name)
                    if _name == operation:
                        e.now = lambda: {"boot_id": "fixture", "boottime_ns": 200, "monotonic_ns": 210}
                return result
            m.setattr(d.os, name, call)
        with pytest.raises(d.DispatchError, match="DEADLINE"):
            d._prep_file(e, str(tmp_path / "new.json"), b"{}\n", 200, uid=os.getuid(), gid=os.getgid())
    assert events[-1] == operation
    assert (tmp_path / "new.json").exists()  # Partial objects are retained.
    assert not e.held
    for fd in opened:
        with pytest.raises(OSError) as failure: os.fstat(fd)
        assert failure.value.errno == errno.EBADF


@pytest.mark.parametrize("operation", ["mkdir", "fchown", "fchmod", "fsync", "fstat", "stat"])
def test_late_directory_call_has_no_followup_mutation(tmp_path, monkeypatch, operation):
    e = effect()
    events = []
    with monkeypatch.context() as m:
        for name in ("mkdir", "fchown", "fchmod", "fsync", "fstat", "stat"):
            original = getattr(d.os, name)
            def call(*args, _name=name, _original=original, **kwargs):
                value = _original(*args, **kwargs)
                events.append(_name)
                if _name == operation:
                    e.now = lambda: {"boot_id": "fixture", "boottime_ns": 200, "monotonic_ns": 210}
                return value
            m.setattr(d.os, name, call)
        with pytest.raises(d.DispatchError, match="DEADLINE"):
            d._prep_directory(e, str(tmp_path / "new"), os.getuid(), os.getgid(), 448, 200)
    assert events[-1] == operation
    assert (tmp_path / "new").is_dir()


def test_directory_create_only_and_symlink_ancestry(tmp_path):
    e = effect()
    target = tmp_path / "new"
    row = d._prep_directory(e, str(target), os.getuid(), os.getgid(), 448, 200)
    assert (row["device"], row["inode"], row["mode"]) == (
        target.stat().st_dev, target.stat().st_ino, stat.S_IFDIR | 448)
    with pytest.raises(FileExistsError):
        d._prep_directory(e, str(target), os.getuid(), os.getgid(), 448, 200)
    (tmp_path / "alias").symlink_to(target, target_is_directory=True)
    with pytest.raises(OSError):
        d._prep_file(e, str(tmp_path / "alias" / "escape"), b"x", 200)
    assert not (target / "escape").exists()


@pytest.mark.parametrize("fault", ["project", "quota", "enforcement", "late_set", "existing", "inherited", None])
def test_project_preparation_checks_actual_returned_values(tmp_path, monkeypatch, fault):
    import fcntl
    e = effect()
    e._capacity_quota_enforcement = lambda: 16 if fault == "enforcement" else 48
    planned = dict(d._planned_roots(d.CASES[0])[0], path=str(tmp_path / "root"))
    account = {"uid": os.getuid(), "gid": os.getgid()}
    mount = {"source": "/synthetic-quota-device", "uuid": "synthetic-uuid"}
    state = {"project": 0, "flags": 0, "hard": 0, "ihard": 0}
    sets = []
    def ioctl(fd, command, raw):
        assert stat.S_ISDIR(os.fstat(fd).st_mode)
        if command == 0x801c581f:
            project = 99 if fault == "inherited" or (fault == "project" and state["project"]) else state["project"]
            return struct.pack("=IIIII8s", state["flags"], 0, 0, project, 0, b"\0" * 8)
        assert command == 0x401c5820
        state["flags"], _, _, state["project"], _, _ = struct.unpack("=IIIII8s", raw)
        return raw
    def quota(source, command, project, values=None):
        assert source == mount["source"] and project == planned["project_id"]
        if command == 0x800008:
            sets.append(copy.deepcopy(values))
            state.update(hard=values["hard"], ihard=values["ihard"])
            if fault == "late_set":
                e.now = lambda: {"boot_id": "fixture", "boottime_ns": 200, "monotonic_ns": 210}
        return dict(project=project, hard=1 if fault == "existing" else state["hard"],
            ihard=1 if fault == "quota" and state["ihard"] else state["ihard"],
            soft=0, isoft=0, btime=0, itime=0, space=0, inodes=int(bool(state["project"])), valid=5)
    monkeypatch.setattr(fcntl, "ioctl", ioctl)
    monkeypatch.setattr(d, "_prep_quota", quota)
    if fault:
        with pytest.raises(d.DispatchError): d._prep_root(e, planned, account, mount, 200)
        assert len(sets) <= 1
    else:
        row = d._prep_root(e, planned, account, mount, 200)
        assert row["inode"] == (tmp_path / "root").stat().st_ino
        assert row["project_id"] == planned["project_id"] and row["accounting"] and row["enforcement"]
        assert sets == [{"hard": 1024, "ihard": 128, "valid": 5}]


@pytest.mark.parametrize("change", [{"project_id": 1001}, {"hard_bytes": 2097152}, {"inode_hard_limit": 256}])
def test_other_quota_objects_refused_before_io(change, monkeypatch):
    monkeypatch.setattr(d.os, "open", lambda *a, **kw: pytest.fail("unapproved IO"))
    planned = dict(d._planned_roots(d.CASES[0])[0], **change)
    with pytest.raises(d.DispatchError, match="QUOTA_MUTATION"):
        d._prep_root(effect(), planned, {}, {}, 200)


@pytest.mark.skipif(os.getuid() == 0, reason="This fixture exercises the existing ordinary test account")
def test_ordinary_ledger_initializer_real_child_create_once(tmp_path, monkeypatch):
    from test_e3_quota_q2_prepare_assembly import facts, a, ROOT
    from test_e3_q2_core_delivery_dispatcher import _command_effects
    value = facts(str(tmp_path))
    assembled = a.assemble(value)
    for name in ("broker", "authority", "reservation"):
        (tmp_path / name).mkdir(mode=448)
    # Runtime/source are this isolated test checkout, not the frozen field
    # installation. The original field argv is inspected before substitution.
    source = tmp_path / "source/tests/e3_host/q2_prepare_assembly.py"
    source.parent.mkdir(parents=True)
    source.write_bytes((ROOT / "tests/e3_host/q2_prepare_assembly.py").read_bytes())
    source.chmod(0o644)
    value["source"]["root"] = str(tmp_path / "source")
    value["installation"]["programs"]["python"]["path"] = sys.executable
    value["installation"]["package_root"] = str(ROOT / "tools")
    prepared = dict(facts=value, assembled=assembled, source_objects={},
        case=d.CASES[0], authority={"fixture": "authority"}, manifest={"fixture": "manifest"},
        paths={"reservation": str(tmp_path / "reservation")})
    e = _command_effects(tmp_path)
    outer = e.context["guest_deadlines"]
    deadline = outer["boottime_deadline_ns"] - 45 * d.NS
    e._active_case_deadlines = {"preparation_deadline_ns": deadline,
        "preparation_monotonic_deadline_ns": outer["monotonic_deadline_ns"] - 45 * d.NS}
    command = e._installation_command
    attempted = []
    def ordinary_child(argv):
        attempted.append(argv)
        assert argv[:9] == [value["setpriv"]["path"], "--reuid=" + str(os.getuid()),
            "--regid=" + str(os.getgid()), "--clear-groups", "--bounding-set=-all",
            "--inh-caps=-all", "--ambient-caps=-all", "--no-new-privs", sys.executable]
        child = list(argv[8:])
        # No privilege changes in the test: only source ownership differs.
        child[4] = child[4].replace("read(source,262144,0,expected)",
                                    "read(source,262144,os.getuid(),expected)")
        try:
            return command(child)
        except d.DispatchError as error:
            raise AssertionError(e._install_commands[-1]["stderr"].decode()) from error
    monkeypatch.setattr(e, "_installation_command", ordinary_child)
    write = d._prep_file
    def owned_write(*args, **kwargs):
        kwargs.setdefault("uid", os.getuid())
        kwargs.setdefault("gid", os.getgid())
        return write(*args, **kwargs)
    monkeypatch.setattr(d, "_prep_file", owned_write)
    try:
        d._prep_initialize(e, prepared, deadline)
        assert prepared["prepared_result"]["ledger"]["generation"] == [1, 1]
        assert prepared["prepared_result"]["status"] == "PREPARED"
        ledger = tmp_path / "broker/jobs.sqlite"
        before = ledger.read_bytes()
        assert len(attempted) == 1
        assert e._install_commands[0]["eof"] == ["stderr", "stdout"]
        assert e._install_commands[0]["wait4"]["wait_status"] == 0
        with pytest.raises(FileExistsError): d._prep_initialize(e, prepared, deadline)
        assert len(attempted) == 1 and ledger.read_bytes() == before
        assert not list((tmp_path / "broker").glob("*-wal"))
    finally:
        e.close()


@pytest.mark.parametrize("case", d.CASES)
@pytest.mark.parametrize("fault", [None, "retained_before", "retained_after", "project_exists", "plan_write"])
def test_preparation_orchestration_uses_original_constructors(case, fault, monkeypatch):
    # Explicit modeled OS only: the schema/assembly constructors below are real.
    plan, receipt, child_pins, helpers = translated(case)
    original = receipt["facts"]
    plan["host"] = original["host"]
    plan["mounts"]["quota"].update(original["mounts"]["quota"])
    roles = {r["role"]: r for r in d._planned_directories(case)}
    for role, row in plan["directories"].items():
        row.update(owner=roles[role]["owner"], mode=roles[role]["mode"])
    parents = {role: {"path": "/synthetic-parent/" + role, "dev": 70, "ino": 800 + n,
                      "uid": 0, "gid": 0, "mode": 493}
               for n, role in enumerate(("state", "quota", "journal", "evidence"))}
    for role, row in original["parents"].items():
        parents[role + "_cgroup"] = dict(row, path="/sys/fs/cgroup" + row["path"])
    parents["retained_ordinary_cgroup"] = parents["ordinary_cgroup"]
    e = effect()
    e._admission = {"parents": parents}
    e._persistence_ready = True
    e._installation_receipt = original["installation"]
    e._admission_detail = {"retained_before": original["retained_before"]}
    if case["index"] != 2: e._admission_detail["system_geometry"] = original["system_geometry"]
    e._persistence_path = lambda *a: "/synthetic-intent"
    intent = d.build_intent(case)
    e.stable_read = lambda *a, **kw: (d.canonical(intent, newline=True), {"uid": 0, "gid": 0})
    steps, writes = [], []
    def retained():
        steps.append("snapshot")
        bad = (fault == "retained_before" and steps.count("snapshot") == 1 or
               fault == "retained_after" and steps.count("snapshot") == 2)
        return ["changed"] if bad else original["retained_before"]
    e._capacity_retained_snapshot = retained
    e._capacity_quota_inventory = lambda: (original["capacity_observed"]["quota_inventory"] +
        ([{"project": case["project_ids"][0]}] if fault == "project_exists" else []))
    e._capacity_quota_enforcement = lambda: 48
    driver = helpers["q2_prepare_driver"]
    helpers["q2_prepare_driver"] = SimpleNamespace(encoded=driver.encoded,
        validate_plan=lambda p: steps.append("validate"), facts_from_observed=driver.facts_from_observed)
    e.preparation_helpers = lambda: helpers
    class ModelIO:
        def __init__(self, *a): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def directory(self, path): return path
        def call(self, fn, *args, **kw):
            if fn is os.fstat:
                pin = next((p for p in parents.values() if p["path"] == args[0]),
                           {"dev": 70, "ino": 999, "uid": 0, "gid": 0, "mode": 493})
                return SimpleNamespace(st_dev=pin["dev"], st_ino=pin["ino"], st_uid=pin["uid"],
                                       st_gid=pin["gid"], st_mode=stat.S_IFDIR | pin["mode"])
            return fn(*args, **kw)
    def directory(effects, path, uid, gid, mode, deadline):
        steps.append("directory:" + path)
        pin = next((p for p in original["directories"].values() if p["path"] == path), None)
        if pin: return dict(pin, uid=uid, gid=gid, mode=stat.S_IFDIR | mode)
        pin = next((p for p in child_pins.values() if p["path"] == path), None)
        return dict(path=path, device=70, inode=pin["inode"] if pin else 10000 + len(steps),
                    uid=uid, gid=gid, mode=stat.S_IFDIR | mode)
    def write(effects, path, raw, deadline):
        steps.append("write:" + path)
        if fault == "plan_write" and path.endswith("preparation-plan.json"):
            raise OSError("partial plan retained")
        assert path not in [p for p, _ in writes]
        writes.append((path, raw))
        return {"path": path, "raw": raw}
    def root(effects, planned, *args):
        steps.append("quota")
        return next(r for r in original["roots"] if r["project_id"] == planned["project_id"])
    monkeypatch.setattr(d, "_PrepIO", ModelIO)
    monkeypatch.setattr(d, "_prep_directory", directory)
    monkeypatch.setattr(d, "_prep_file", write)
    monkeypatch.setattr(d, "_prep_root", root)
    monkeypatch.setattr(d, "_prep_initialize", lambda *a: steps.append("initialize"))
    monkeypatch.setattr(d, "_prep_make_plan", lambda *a: plan)
    monkeypatch.setattr(d.os, "geteuid", lambda: 0)
    monkeypatch.setattr(d.os, "getegid", lambda: 0)
    if fault:
        with pytest.raises((d.DispatchError, OSError)): e.prepare_case(case, intent, 200)
        assert "initialize" not in steps
        assert not any(p.endswith("preparation-result.json") for p, _ in writes)
        if fault != "retained_after": assert "quota" not in steps
    else:
        prepared = e.prepare_case(case, intent, 200)
        assert steps[-1] == "initialize" and steps.count("quota") == 7
        assert writes[0][0].endswith("preparation-plan.json")
        assert sum(s.startswith("directory:") for s in steps[:steps.index("write:" + writes[0][0])]) == 2
        assert prepared["assembled"]["resident"]["request"]["operation_id"] == case["operation_id"]
        assert prepared["receipt"]["q2_accepted"] is False
