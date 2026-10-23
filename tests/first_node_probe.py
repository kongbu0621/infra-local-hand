"""Explicit Linux P0/P1 fixture; never run by ordinary test discovery.

--inspect reads a supplied manager configuration without printing secrets.
--probe additionally starts five bounded synthetic system services in a fresh
slice. It never calls Local Hand, changes accounts, mounts storage, or touches
existing task directories. Success is primitive evidence, not product acceptance.
"""
from __future__ import annotations

import argparse
import errno
import grp
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import socket
import stat
import subprocess
import sys
import time
import uuid

LIMIT = 2 * 1024 * 1024
PARENT_MEMORY_BYTES = 512 * 1024 * 1024
DENIED = {errno.EACCES, errno.EPERM}
UNIT = re.compile(r"lhp1[0-9a-f]{12}(?:s[0-4]|r0)?\.(?:service|slice)\Z")


def read_json(path, limit=LIMIT):
    with open(path, "rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("JSON byte limit")
    return json.loads(raw)


def write_json(path, value, *, mode=0o600):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def run(argv, *, check=True):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=12, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    if check and result.returncode:
        raise RuntimeError(f"{Path(argv[0]).name} failed ({result.returncode}): {result.stderr[:1024]}")
    return result


def show(unit):
    result = run(["/usr/bin/systemctl", "show", unit, "--no-pager",
                  "-p", "LoadState", "-p", "ActiveState", "-p", "MainPID",
                  "-p", "ControlGroup", "-p", "InvocationID", "-p", "Result",
                  "-p", "ExecMainCode", "-p", "ExecMainStatus"], check=False)
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if result.returncode and fields.get("LoadState") != "not-found":
        raise RuntimeError("cannot observe unit: " + unit)
    return fields


def cgroup_limits(group):
    if not group.startswith("/") or ".." in Path(group).parts:
        raise ValueError("invalid cgroup path")
    root = Path("/sys/fs/cgroup") / group.lstrip("/")
    return {name: (root / name).read_text().strip()
            for name in ("memory.max", "memory.swap.max", "pids.max", "cpu.max", "cgroup.events")}


def inspect_manager(config_path):
    """Allow-list only; never emit raw config, tokens, keys or session values."""
    path = Path(config_path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("manager configuration must be protected and root owned")
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("manager configuration byte limit")
    value = json.loads(raw)
    template = value.get("template", {})
    plan = template.get("plan", {})
    installation = value.get("installation", {})
    observed = template.get("observed", {})
    parents = {}
    for role, pin in observed.get("parents", {}).items():
        group = pin["path"]
        try:
            parents[role] = dict(path=group, limits=cgroup_limits(group))
        except OSError as exc:
            parents[role] = dict(path=group, unavailable=type(exc).__name__)
    return dict(config_sha256=hashlib.sha256(raw).hexdigest(),
                profile_ref=value.get("profile_ref"),
                source_commit=installation.get("source", {}).get("commit"),
                adapter_uid=value.get("uid"), adapter_gid=value.get("gid"),
                task_uid=plan.get("account", {}).get("uid"),
                task_gid=plan.get("account", {}).get("gid"),
                principal_count=len(value.get("principals", [])),
                source_refs=sorted(value.get("workspace", {}).get("sources", {})),
                original_budgets=plan.get("settings", {}).get("original_budgets", {}),
                management_limits=plan.get("settings", {}).get("limits", {}),
                parents=parents,
                host=dict(system=platform.system(), machine=platform.machine(),
                          kernel=platform.release(), boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip()),
                authentication="Not established by local Unix-socket availability; inventory separately.")


def attempt_read(path):
    try:
        with Path(path).open("rb") as stream:
            stream.read(64)
        return 0
    except OSError as exc:
        return exc.errno


def attempt_connect(path):
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(1)
            connection.connect(str(path))
        return 0
    except OSError as exc:
        return exc.errno


def worker(root, number):
    """Unprivileged fixed workload: tiny fixture files and Unix sockets only."""
    root = Path(root)
    if os.geteuid() == 0 or root.parent != Path("/run") or not re.fullmatch(r"lhp1[0-9a-f]{12}", root.name) or number not in range(5):
        raise ValueError("worker requires an unprivileged fixture identity and slot")
    own = root / "tasks" / str(number)
    (own / "sentinel").write_text("synthetic fixture\n")
    os.chmod(own / "sentinel", 0o600)
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(own / "control.sock"))
        os.chmod(own / "control.sock", 0o600)
        listener.listen(16)
        status = Path("/proc/self/status").read_text()
        fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
        write_json(own / "ready.json", dict(pid=os.getpid(), uid=os.getuid(), gid=os.getgid(),
                   groups=os.getgroups(), cap_eff=fields["CapEff"].strip(),
                   capabilities={key: fields[key].strip() for key in
                                 ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")},
                   uids=list(map(int, fields["Uid"].split())),
                   gids=list(map(int, fields["Gid"].split())),
                   no_new_privs=fields["NoNewPrivs"].strip()))
        deadline = time.monotonic() + 150
        sequence = 0
        while time.monotonic() < deadline:
            command_path = root / (str(number) + ".command.json")
            try:
                command = read_json(command_path, 4096)
            except FileNotFoundError:
                time.sleep(0.05)
                continue
            if command["sequence"] <= sequence:
                time.sleep(0.05)
                continue
            sequence = command["sequence"]
            peers = [root / "tasks" / str(i) for i in range(5) if i != number]
            result = dict(sequence=sequence, pid=os.getpid(), uid=os.getuid(),
                          own_file=attempt_read(own / "sentinel"),
                          own_socket=attempt_connect(own / "control.sock"),
                          peer_files=[attempt_read(p / "sentinel") for p in peers],
                          peer_sockets=[attempt_connect(p / "control.sock") for p in peers],
                          manager_socket=attempt_connect(root / "manager" / "control.sock"))
            if command.get("retained"):
                result["retained_file"] = attempt_read(root / "retained" / "old" / "sentinel")
                result["retained_socket"] = attempt_connect(root / "retained" / "old" / "control.sock")
            write_json(own / "response.json", result)
    return 0


def choose_uids():
    occupied = {entry.pw_uid for entry in pwd.getpwall()}
    occupied.update(entry.gr_gid for entry in grp.getgrall())
    for item in Path("/proc").iterdir():
        if item.name.isdigit():
            try:
                for line in (item / "status").read_text().splitlines():
                    if line.startswith(("Uid:", "Gid:")):
                        occupied.update(map(int, line.split()[1:]))
            except FileNotFoundError:
                pass
    # No persistent account creation. Different numeric IDs for five live
    # fixture services; fail on observed collisions, never borrow a host user.
    first = 700000 + uuid.uuid4().int % 100000
    return [number for number in range(first, first + 100) if number not in occupied][:5]


def service_command(unit, slice_name, root, number, uid):
    if not UNIT.fullmatch(unit) or not UNIT.fullmatch(slice_name):
        raise ValueError("fixture unit name required")
    # systemd 255 may require an NSS entry even for numeric User=. Use its
    # existing fixed setpriv launch path: only the short launcher has the three
    # capabilities needed to drop groups/UID and its bounding set. Leave User=
    # unset: systemd 255's explicit-UID/seccomp path drops CAP_SETUID before exec;
    # NoNewPrivileges then prevents root exec from restoring it. This is always
    # a system unit, never --user. Python checks non-root, zero capabilities.
    properties = dict(SupplementaryGroups="",
                      RuntimeMaxSec="150s", TimeoutStopSec="2s", KillMode="control-group",
                      MemoryMax="64M", MemorySwapMax="0", TasksMax="4", CPUQuota="10%",
                      LimitFSIZE="65536", NoNewPrivileges="yes",
                      CapabilityBoundingSet="CAP_SETUID CAP_SETGID CAP_SETPCAP",
                      AmbientCapabilities="", UMask="0077", ProtectSystem="strict",
                      ProtectHome="yes", PrivateTmp="yes", PrivateDevices="yes",
                      PrivateNetwork="yes", ProtectControlGroups="yes", RestrictSUIDSGID="yes",
                      RestrictNamespaces="yes", LockPersonality="yes", Restart="no",
                      ReadWritePaths=str(root / "tasks" / str(number)),
                      StandardOutput="null",
                      StandardError="append:" + str(root / "diagnostics" / (unit + ".stderr")))
    return ["/usr/bin/systemd-run", "--quiet", "--collect", "--service-type=exec",
            "--unit=" + unit, "--slice=" + slice_name,
            *["--property=" + key + "=" + val for key, val in properties.items()],
            "--", "/usr/bin/setpriv", "--reuid=" + str(uid), "--regid=" + str(uid),
            "--clear-groups", "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all",
            "--no-new-privs", "--", "/usr/bin/python3", "-I", "-B", str(root / "probe.py"),
            "--worker", str(root), str(number)]


def await_file(path, predicate=lambda value: True, *, unit=None):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        try:
            value = read_json(path, 65536)
            if predicate(value):
                return value
        except FileNotFoundError:
            pass
        if unit is not None:
            state = show(unit)
            if state.get("ActiveState") in {"inactive", "failed"} or state.get("LoadState") == "not-found":
                if state.get("LoadState") == "not-found":
                    # Collected units expose synthetic defaults, not exit proof.
                    state = {"LoadState": "not-found", "exit_status": "unavailable_after_collection"}
                raise RuntimeError("fixture exited before response: " + json.dumps(dict(unit=unit, **state)))
        time.sleep(0.05)
    raise TimeoutError("fixture response missing: " + str(path))


def verify_ready(unit, own, uid):
    ready = await_file(own / "ready.json", unit=unit)
    if (ready["uids"] != [uid] * 4 or ready["gids"] != [uid] * 4
            or ready["uid"] != uid or ready["gid"] != uid or ready["groups"]
            or set(ready["capabilities"]) != {"CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"}
            or any(int(value, 16) != 0 for value in ready["capabilities"].values())
            or ready["no_new_privs"] != "1"):
        raise ValueError("unexpected execution identity or capabilities")
    state = show(unit)
    if state.get("ActiveState") != "active" or int(state["MainPID"]) != ready["pid"]:
        raise ValueError("fixture is not the observed active unit")
    limits = cgroup_limits(state["ControlGroup"])
    cpu, period = map(int, limits["cpu.max"].split())
    if (limits["memory.max"] != str(64 * 1024**2) or limits["memory.swap.max"] != "0"
            or limits["pids.max"] != "4" or cpu * 10 != period):
        raise ValueError("leaf resource boundary differs")
    return dict(unit=unit, **ready, cgroup=state["ControlGroup"], limits=limits)


def assert_access(result, *, retained=False):
    if result["own_file"] != 0 or result["own_socket"] != 0:
        raise ValueError("positive access control failed")
    refusals = [*result["peer_files"], *result["peer_sockets"], result["manager_socket"]]
    if retained:
        refusals += [result["retained_file"], result["retained_socket"]]
    if any(code not in DENIED for code in refusals):
        raise ValueError("cross-task access was not refused by permissions")


def stopped(unit):
    state = show(unit)
    if state.get("ActiveState") not in {"inactive", "failed"} or state.get("MainPID") not in {None, "0"}:
        return False
    # Observe the original fixture cgroup even if --collect removed the unit.
    group = state.get("ControlGroup") or "/" + unit[:16] + ".slice/" + unit
    if group:
        try:
            return "populated 0" in cgroup_limits(group)["cgroup.events"].splitlines()
        except FileNotFoundError:
            pass
    return True


def probe():
    if os.getuid() != 0 or os.geteuid() != 0:
        raise PermissionError("native fixture requires root")
    token = "lhp1" + uuid.uuid4().hex[:12]
    root = Path("/run") / token
    root.mkdir(mode=0o755)
    os.chmod(root, 0o755)
    slice_name = token + ".slice"
    units = []
    result = dict(status="FAILED", primitive_only=True, production_changed=False,
                  product_queue_verified=False, quota_parallel_admission_verified=False,
                  root=str(root), observations=[], cleanup={})
    parent_configured = False
    manager = None
    try:
        (root / "probe.py").write_bytes(Path(__file__).read_bytes())
        os.chmod(root / "probe.py", 0o444)
        (root / "tasks").mkdir(mode=0o755)
        os.chmod(root / "tasks", 0o755)
        (root / "manager").mkdir(mode=0o700)
        (root / "retained").mkdir(mode=0o700)
        (root / "diagnostics").mkdir(mode=0o700)
        manager = socket.socket(socket.AF_UNIX)
        manager.bind(str(root / "manager" / "control.sock"))
        manager.listen(8)
        uids = choose_uids()
        if len(uids) != 5:
            raise RuntimeError("no five unused fixture identities")
        identities = []
        for number, uid in enumerate(uids):
            own = root / "tasks" / str(number)
            own.mkdir(mode=0o700)
            os.chown(own, uid, uid)
            unit = token + "s" + str(number) + ".service"
            units.append(unit)  # Also clean up a start with an uncertain reply.
            run(service_command(unit, slice_name, root, number, uid))
            if not parent_configured:
                # Revert only this fresh slice even if the reply is lost.
                parent_configured = True
                run(["/usr/bin/systemctl", "set-property", "--runtime", slice_name,
                     "MemoryMax=" + str(PARENT_MEMORY_BYTES), "MemorySwapMax=0", "TasksMax=24", "CPUQuota=50%"])
            identities.append(verify_ready(unit, own, uid))
        result["identities"] = identities
        result["parent_limits"] = cgroup_limits(show(slice_name)["ControlGroup"])
        parent = result["parent_limits"]
        cpu, period = map(int, parent["cpu.max"].split())
        if (parent["memory.max"] != str(PARENT_MEMORY_BYTES) or parent["memory.swap.max"] != "0"
                or parent["pids.max"] != "24" or cpu * 2 != period):
            raise ValueError("aggregate resource boundary differs")
        if len({x["cgroup"] for x in identities}) != 5:
            raise ValueError("execution cgroups are shared")
        for number in range(5):
            write_json(root / (str(number) + ".command.json"), dict(sequence=1), mode=0o644)
        for number in range(5):
            observation = await_file(root / "tasks" / str(number) / "response.json")
            assert_access(observation)
            result["observations"].append(observation)
        run(["/usr/bin/systemctl", "stop", units[0]])
        if not stopped(units[0]):
            raise ValueError("cancelled fixture exit not proven")
        for number in range(1, 5):
            write_json(root / (str(number) + ".command.json"), dict(sequence=2), mode=0o644)
            observation = await_file(root / "tasks" / str(number) / "response.json", lambda x: x["sequence"] == 2)
            if observation["pid"] != identities[number]["pid"]:
                raise ValueError("other fixture changed after cancellation")
            assert_access(observation)
            result["observations"].append(observation)
        # Archive the stopped identity before it can be reused. Its old data
        # remains under a root-only parent, including its old control socket.
        os.rename(root / "tasks" / "0", root / "retained" / "old")
        (root / "tasks" / "0").mkdir(mode=0o700)
        os.chown(root / "tasks" / "0", uids[0], uids[0])
        reuse_unit = token + "r0.service"
        units.append(reuse_unit)
        run(service_command(reuse_unit, slice_name, root, 0, uids[0]))
        result["reused_identity"] = verify_ready(reuse_unit, root / "tasks" / "0", uids[0])
        write_json(root / "0.command.json", dict(sequence=3, retained=True), mode=0o644)
        observation = await_file(root / "tasks" / "0" / "response.json", lambda x: x["sequence"] == 3)
        assert_access(observation, retained=True)
        result["observations"].append(observation)
        result["status"] = "PASS"
    except Exception as exc:
        result["error"] = dict(type=type(exc).__name__, message=str(exc))
        result["launch_errors"] = {}
        for unit in units:
            try:
                with (root / "diagnostics" / (unit + ".stderr")).open("rb") as stream:
                    raw = stream.read(65537)
                result["launch_errors"][unit] = dict(text=raw[:65536].decode("utf-8", errors="replace"),
                                                    truncated=len(raw) > 65536)
            except OSError as log_error:
                result["launch_errors"][unit] = dict(unavailable=type(log_error).__name__)
        result["fixture_journal"] = {}
        for unit in units:
            try:
                log = run(["/usr/bin/journalctl", "-u", unit, "--no-pager", "-n", "12", "-o", "short-precise"], check=False)
                result["fixture_journal"][unit] = log.stdout[:8192]
            except Exception as log_error:
                result["fixture_journal"][unit] = type(log_error).__name__
    finally:
        clean = True
        for unit in units:
            try:
                run(["/usr/bin/systemctl", "stop", unit], check=False)
                proven = stopped(unit)
                result["cleanup"][unit] = proven
                clean = clean and proven
            except Exception as exc:
                result["cleanup"][unit] = type(exc).__name__
                clean = False
        if manager is not None:
            manager.close()
        if clean:
            try:
                run(["/usr/bin/systemctl", "stop", slice_name], check=False)
                if parent_configured:
                    run(["/usr/bin/systemctl", "revert", slice_name])
                shutil.rmtree(root)
                result["cleanup"]["fixture_removed"] = True
            except Exception as exc:
                result["cleanup"]["error"] = str(exc)
                clean = False
        if not clean:
            result["status"] = "CLEANUP_UNCERTAIN"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manager-config", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--worker", nargs=2, metavar=("FIXTURE", "SLOT"))
    args = parser.parse_args(argv)
    if args.worker:
        return worker(args.worker[0], int(args.worker[1]))
    if args.manager_config is None:
        parser.error("--manager-config is required for inspection and native probes")
    report = dict(schema="local-hand-first-node-probe/v1",
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    try:
        report["inspection"] = inspect_manager(args.manager_config)
        if args.probe:
            report["native_probe"] = probe()
            after = inspect_manager(args.manager_config)
            report["manager_configuration_unchanged"] = (
                after["config_sha256"] == report["inspection"]["config_sha256"])
    except Exception as exc:
        report["error"] = dict(type=type(exc).__name__, message=str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if ("error" not in report and report.get("manager_configuration_unchanged", True)
                 and report.get("native_probe", {}).get("status", "PASS") == "PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
