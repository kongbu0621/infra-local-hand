"""Synthetic negative boundaries; no guest/systemd mutation."""
import copy
import importlib.util
from pathlib import Path
import stat
import pytest

spec = importlib.util.spec_from_file_location("cgroup_fragment", Path(__file__).parent / "e3_host/q2_reconciliation_backend.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def pin(ino=1, uid=0):
    return dict(device=1, inode=ino, mode=stat.S_IFDIR | 0o755, uid=uid, gid=uid, nlink=1)


def row(path, *, members="", children=(), populated=0, uid=0):
    files = {name: "" for name in m.CGROUP_FILES}
    files.update({"cgroup.procs": members, "cgroup.threads": members,
                  "cgroup.events": f"populated {populated}\nfrozen 0\n", "cgroup.type": "domain\n",
                  "cgroup.controllers": "cpu memory pids\n", "cgroup.subtree_control": "cpu memory pids\n",
                  "memory.max": "1048576\n", "memory.swap.max": "0\n", "pids.max": "64\n",
                  "cpu.max": "10000 100000\n", "memory.events": "low 0\nhigh 0\noom 0\n",
                  "memory.events.local": "low 0\nhigh 0\noom 0\n", "pids.events": "max 0\n",
                  "pids.current": f"{populated}\n"})
    return dict(path=path, files=files, children=list(children), identity=pin(), delegation=pin(uid=uid))


def state(unit, group="", pid=0, *, manager=False):
    active = bool(group)
    return dict(Id=unit, LoadState="loaded", ActiveState="active" if active else "inactive",
                SubState=("running" if manager else "active") if active else "dead", Job="", MainPID=str(pid),
                ControlPID="0", ControlGroup=group, User="1000" if manager else "", Delegate="yes")


def inputs():
    limits = dict(memory_bytes=1048576, tasks_max=64, cpu_quota_per_sec_usec=100000)
    plan = dict(account=dict(uid=1000, gid=1000), parents={role: dict(limits, unit=f"lhq{role}.slice")
                                                        for role in ("system", "ordinary")})
    observed = dict(manager=state("user@1000.service", manager=True),
                    parents=dict(system=state("lhqsystem.slice", "/lhqsystem.slice")))
    return plan, observed


class Reader:
    def __init__(self, rows):
        self.rows = rows
        self.count = 0
        self.absences = {}
        self.processes = {}
        self.change = None

    def tree(self, path):
        self.count += 1
        rows = copy.deepcopy(self.rows[path])
        if self.change is not None and self.count > 1:
            self.change(rows)
        return rows

    def absent(self, path):
        return self.absences.get(path, True)

    def process(self, pid):
        return copy.deepcopy(self.processes[pid])


def test_empty_complete_tree_and_guard():
    plan, observed = inputs()
    root = row("/lhqsystem.slice", children=("child",))
    child = row("/lhqsystem.slice/child")
    calls = []
    out = m.audit_cgroups(plan, observed, reader=Reader({"/sys/fs/cgroup/lhqsystem.slice": [root, child]}),
                          guard=lambda: calls.append(True))
    assert out["node_count"] == 2 and len(calls) >= 4
    assert out["absent_paths"] == ["/user.slice/user-1000.slice/user@1000.service"]


@pytest.mark.parametrize("file,value,code", [
    ("cgroup.procs", "123\n", "BUSY"), ("cgroup.threads", "123\n", "THREADS_BUSY"),
    ("cgroup.events", "populated 1\nfrozen 0\n", "POPULATED"),
    ("memory.max", "max\n", "PARENT_LIMIT"), ("cpu.max", "max 100000\n", "PARENT_CPU"),
    ("memory.events", "oom 0\noom 1\n", "EVENT_FIELDS"),
    ("cgroup.type", "domain threaded\n", "CGROUP_TYPE")])
def test_occupied_bad_limits_and_events(file, value, code):
    plan, observed = inputs()
    root = row("/lhqsystem.slice")
    root["files"][file] = value
    with pytest.raises(ValueError, match=code):
        m.audit_cgroups(plan, observed, reader=Reader({"/sys/fs/cgroup/lhqsystem.slice": [root]}))


def test_grandchild_pid_is_not_hidden_by_root_empty():
    plan, observed = inputs()
    nodes = [row("/lhqsystem.slice", children=("child",)),
             row("/lhqsystem.slice/child", children=("grandchild",)),
             row("/lhqsystem.slice/child/grandchild", members="234\n", populated=1)]
    with pytest.raises(ValueError, match="BUSY"):
        m.audit_cgroups(plan, observed, reader=Reader({"/sys/fs/cgroup/lhqsystem.slice": nodes}))


def test_missing_descendant_is_rejected():
    plan, observed = inputs()
    with pytest.raises(ValueError, match="DESCENDANTS_MISSING"):
        m.audit_cgroups(plan, observed, reader=Reader({"/sys/fs/cgroup/lhqsystem.slice":
                                                     [row("/lhqsystem.slice", children=("hidden",))]}))


def test_inactive_manager_cgroup_exists():
    plan, observed = inputs()
    reader = Reader({"/sys/fs/cgroup/lhqsystem.slice": [row("/lhqsystem.slice")]})
    reader.absences["/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service"] = False
    with pytest.raises(ValueError, match="INACTIVE_CGROUP_PRESENT"):
        m.audit_cgroups(plan, observed, reader=reader)


def test_between_walk_inode_replacement():
    plan, observed = inputs()
    reader = Reader({"/sys/fs/cgroup/lhqsystem.slice": [row("/lhqsystem.slice")]})
    reader.change = lambda rows: rows[0]["identity"].update(inode=2)
    with pytest.raises(ValueError, match="CGROUP_DRIFT"):
        m.audit_cgroups(plan, observed, reader=reader)


def test_system_parent_cannot_be_world_writable_or_ordinary_owned():
    plan, observed = inputs()
    for changed in ({"uid": 1000}, {"mode": stat.S_IFDIR | 0o777}):
        node = row("/lhqsystem.slice")
        node["identity"].update(changed)
        with pytest.raises(ValueError, match="CGROUP_PERMISSION"):
            m.audit_cgroups(plan, observed, reader=Reader({"/sys/fs/cgroup/lhqsystem.slice": [node]}))


def process(pid, ppid, uid, *, cgroup="0::/\n", args="/usr/lib/systemd/systemd\0--user\0"):
    names = {name: dict(text=f"{name}:[{index + 10}]", identity=pin(index + 10))
             for index, name in enumerate(m.NAMESPACES)}
    status = f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\nGid:\t{uid}\t{uid}\t{uid}\t{uid}\nGroups:\t{uid}\n"
    status += f"Pid:\t{pid}\nPPid:\t{ppid}\nThreads:\t1\nNoNewPrivs:\t0\n"
    status += "".join(f"{key}:\t0000000000000000\n" for key in m.CAP_FIELDS)
    fields = ["S", str(ppid)] + ["0"] * 17 + ["100"]
    return dict(identity=pin(pid, uid), stat=f"{pid} (systemd) " + " ".join(fields), status=status,
                namespaces=names, cgroup=cgroup, cmdline=args,
                exe=dict(text="/usr/lib/systemd/systemd", identity=pin(500)))


def manager_input():
    plan, observed = inputs()
    path = "/user.slice/user-1000.slice/user@1000.service"
    observed["manager"] = state("user@1000.service", path, 222, manager=True)
    observed["parents"]["ordinary"] = state("lhqordinary.slice", path + "/lhqordinary.slice")
    roots = {"/sys/fs/cgroup/lhqsystem.slice": [row("/lhqsystem.slice")],
             "/sys/fs/cgroup" + path: [row(path, children=("init.scope", "lhqordinary.slice"), populated=1),
                 row(path + "/init.scope", members="222\n", populated=1), row(path + "/lhqordinary.slice", uid=1000)]}
    reader = Reader(roots)
    reader.processes = {1: process(1, 0, 0), 222: process(222, 1, 1000, cgroup="0::" + path + "/init.scope\n")}
    return plan, observed, reader, path


def test_manager_only_allowed_at_init_scope_real_caps_retained():
    plan, observed, reader, _ = manager_input()
    result = m.audit_cgroups(plan, observed, reader=reader)
    assert result["manager_process"]["status"]["NoNewPrivs"] == 0
    assert result["manager_process"]["status"]["CapBnd"] == 0
    assert result["node_count"] == 4


@pytest.mark.parametrize("mutation,match", [
    (lambda r, p: r.rows["/sys/fs/cgroup" + p][1]["files"].update({"cgroup.procs": "222\n223\n"}), "BUSY"),
    (lambda r, p: r.processes[222].update(cgroup="0::/wrong/init.scope\n"), "PROCESS_IDENTITY"),
    (lambda r, p: r.processes[222].update(status=r.processes[222]["status"].replace("CapEff:\t0000000000000000", "CapEff:\t0000000000000001")), "CAPABILITIES"),
    (lambda r, p: r.processes[222]["namespaces"]["mnt"]["identity"].update(inode=999), "NAMESPACE"),
])
def test_manager_bad_identity_extra_pid_caps_namespace(mutation, match):
    plan, observed, reader, path = manager_input()
    mutation(reader, path)
    with pytest.raises(ValueError, match=match):
        m.audit_cgroups(plan, observed, reader=reader)


def test_path_alias_and_non_kernel_paths():
    reader = m.KernelReader(lambda: None)
    for path in ("/proc/../etc/passwd", "/proc//1/status", "/etc/passwd"):
        with pytest.raises(ValueError):
            reader.read(path)


def test_real_kernel_reader_bound_and_numeric_proc():
    reader = m.KernelReader(lambda: None)
    with pytest.raises(ValueError, match="FILE_BOUND"):
        reader.read("/proc/sys/kernel/random/boot_id", 1)
    try:
        observed = m.KernelReader(lambda: None).process(m.os.getpid())
    except (FileNotFoundError, PermissionError):
        pytest.skip("Execution container numeric proc identity is unavailable/inaccessible; live admission would BLOCK")
    assert m.process_stat(observed["stat"])["identity"][0] == m.os.getpid()
    assert set(observed["namespaces"]) == set(m.NAMESPACES)


def namespace_reader():
    reader = Reader({})
    reader.processes = {1: process(1, 0, 0), m.os.getpid(): process(m.os.getpid(), 1, 0)}
    reader.read = lambda path, limit: b"boot\n"
    return reader


def test_namespace_boot_and_live_status_observation():
    reader = namespace_reader()
    plan = dict(host=dict(boot_id="boot", initial_userns=dict(device=1, inode=10)))
    out = m.audit_namespaces(plan, reader=reader)
    assert out["boot_id"] == "boot" and out["administrator"]["status"]["NoNewPrivs"] == 0


@pytest.mark.parametrize("kind", ["user", "mnt", "pid", "cgroup", "net", "ipc", "uts"])
def test_namespace_mismatch_is_never_filled_true(kind):
    reader = namespace_reader()
    reader.processes[m.os.getpid()]["namespaces"][kind]["identity"]["inode"] += 1
    plan = dict(host=dict(boot_id="boot", initial_userns=dict(device=1, inode=10)))
    with pytest.raises(ValueError, match="USERNS|NAMESPACE"):
        m.audit_namespaces(plan, reader=reader)


def test_boot_drift_after_namespace_observation():
    reader = namespace_reader()
    calls = []
    def read(path, limit):
        calls.append(path)
        return b"boot\n" if len(calls) == 1 else b"other\n"
    reader.read = read
    plan = dict(host=dict(boot_id="boot", initial_userns=dict(device=1, inode=10)))
    with pytest.raises(ValueError, match="BOOT_CHANGED"):
        m.audit_namespaces(plan, reader=reader)
