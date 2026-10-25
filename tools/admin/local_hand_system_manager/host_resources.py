"""Explicit boot preparation of one retained ordinary-user slice.

Run once by a separately installed oneshot, as that ordinary user, after the
system slices and user manager have been started by declared boot dependencies.
The guarded manager only checks readiness. This helper never stops a slice,
changes a running slice's limits, starts a business service, or reloads a manager.
The deployment profile must exclude competing writers to these fixed resources.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import stat

from local_hand_jobs import quota_contract as q
from local_hand_jobs import startup
from admin.local_hand_deploy.systemd_bus import SystemdBus


SCHEMA = "local-hand-retained-boot-resource/v1"
LIMITS = {"MemoryMax": 268435456, "MemorySwapMax": 0, "TasksMax": 64,
          "CPUQuotaPerSecUSec": 1000000, "CPUQuotaPeriodUSec": 100000}
DROPINS = {"MemoryMax", "MemorySwapMax", "TasksMax", "CPUQuota", "CPUQuotaPeriodSec"}
FORBIDDEN = ("BindsTo", "PartOf", "Requisite",
             "PropagatesStopTo", "StopPropagatedFrom", "OnFailure", "OnSuccess",
             "TriggeredBy", "Triggers", "Upholds", "UpheldBy")


def validate(config):
    q.require(isinstance(config, dict) and set(config) == {"schema", "uid", "unit", "parent", "limits"}
              and config["schema"] == SCHEMA, "HOST_RESOURCE_CONFIG")
    uid, name = config["uid"], config["unit"]
    # One top-level, distinctly named slice in the specified user's manager.
    q.require(type(uid) is int and uid > 0 and isinstance(name, str)
              and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,80}\.slice", name) is not None
              and name not in {"app.slice", "session.slice", "background.slice"}, "HOST_RESOURCE_IDENTITY")
    q.require(config["parent"] == f"/user.slice/user-{uid}.slice/user@{uid}.service/{name}",
              "HOST_RESOURCE_PARENT")
    q.require(config["limits"] == LIMITS and all(type(n) is int for n in config["limits"].values()),
              "HOST_RESOURCE_BUDGET")
    return config


def from_resident(config):
    """Produce a non-secret, immutable boot input without task/auth configuration."""
    old = config["template"]["observed"]["system_geometry"]["retained_ordinary_parent"]
    q.require((old["memory_bytes"], old["memory_swap_max"], old["tasks_max"], old["cpu_quota_per_sec_usec"])
              == (268435456, 0, 64, 1000000), "HOST_RESOURCE_BUDGET")
    return validate({"schema": SCHEMA, "uid": config["uid"], "unit": Path(old["parent"]["path"]).name,
                     "parent": old["parent"]["path"], "limits": dict(LIMITS)})


def service_definition(resident, *, python, package_root, admin_tools, configuration):
    """Render the separately reviewed boot unit; never install or enable it.

    Files and dependencies belong to the offline infrastructure transition and
    shared-reload scope. Normal guarded releases treat this unit as read-only.
    """
    config = from_resident(resident)
    uid, gid = config["uid"], resident["gid"]
    q.require(type(gid) is int and gid > 0, "HOST_RESOURCE_ORDINARY_IDENTITY")
    paths = (python, package_root, admin_tools, configuration)
    q.require(all(isinstance(p, str) and re.fullmatch(r"/[A-Za-z0-9_./-]+", p)
                  and str(Path(p)) == p and ".." not in Path(p).parts for p in paths), "HOST_RESOURCE_SERVICE_PATH")
    parents = resident["template"]["observed"]["parents"]
    q.require(isinstance(parents, dict) and 1 <= len(parents) <= 16, "HOST_RESOURCE_DEPENDENCIES")
    names = set()
    for parent in parents.values():
        path = parent["path"]
        q.require(isinstance(path, str) and path.startswith("/") and path != "/" and str(Path(path)) == path
                  and all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,100}\.slice", p)
                          for p in Path(path).parts[1:]), "HOST_RESOURCE_DEPENDENCIES")
        names.add(Path(path).name)
    dependencies = " ".join(sorted(names) + [f"user@{uid}.service"])
    command = ('import sys;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];'
               'from admin.local_hand_system_manager.host_resources import main;main()')
    return ("[Unit]\nDescription=Local Hand explicit boot resource preparation\n"
            f"Requires={dependencies}\nAfter={dependencies}\n"
            "[Service]\nType=oneshot\nRemainAfterExit=yes\nRestart=no\n"
            f"User={uid}\nGroup={gid}\nEnvironment=XDG_RUNTIME_DIR=/run/user/{uid}\n"
            f"Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus\n"
            f'ExecStart={python} -I -B -c "{command}" {package_root} {admin_tools} --config {configuration}\n'
            "NoNewPrivileges=yes\nUMask=0077\nKillMode=control-group\nTimeoutStartSec=45s\n"
            "[Install]\nWantedBy=multi-user.target\n")


def _state(bus, config):
    state = bus.unit(config["unit"])
    q.require(state.get("LoadState") == "loaded" and state.get("Job", [None])[0] == 0
              and state.get("ActiveState") in {"active", "inactive"}, "HOST_RESOURCE_BUSY")
    control = f"/run/user/{config['uid']}/systemd/user.control/{config['unit']}.d/"
    allowed = {control + "50-" + key + ".conf" for key in DROPINS}
    q.require(not state.get("FragmentPath") and set(state.get("DropInPaths", [])) <= allowed
              and not any(state.get(key) for key in FORBIDDEN), "HOST_RESOURCE_DEFINITION")
    # Only the implicit root slice / shutdown ordering of a fileless slice.
    q.require(set(state.get("Requires", [])) <= {"-.slice"}
              and not state.get("Wants") and set(state.get("Conflicts", [])) <= {"shutdown.target"},
              "HOST_RESOURCE_DEPENDENCIES")
    group = state.get("ControlGroup", "")
    q.require(group in {"", config["parent"]}, "HOST_RESOURCE_PARENT")
    if state["ActiveState"] == "active":
        q.require(group == config["parent"], "HOST_RESOURCE_PARENT")
    return state


def _limits_match(state, config):
    return all(state.get(key) == value for key, value in config["limits"].items())


def _kernel_check(config):
    path = Path("/sys/fs/cgroup" + config["parent"])
    cpu = (path / "cpu.max").read_text().split()
    q.require(cpu == ["100000", "100000"], "HOST_RESOURCE_KERNEL_LIMIT")
    for key, name in (("MemoryMax", "memory.max"), ("MemorySwapMax", "memory.swap.max"), ("TasksMax", "pids.max")):
        q.require(int((path / name).read_text()) == config["limits"][key], "HOST_RESOURCE_KERNEL_LIMIT")


def prepare(config):
    validate(config)
    uid = config["uid"]
    q.require(os.getuid() == os.geteuid() == uid, "HOST_RESOURCE_ORDINARY_IDENTITY")
    directory = startup._protected_directory(f"/run/user/{uid}", owner_uid=uid)
    try:
        fd = os.open(".local-hand-boot-" + config["unit"] + ".lock",
                     os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, 0o600, dir_fd=directory)
    finally:
        os.close(directory)
    try:
        info = os.fstat(fd)
        q.require(stat.S_ISREG(info.st_mode) and info.st_uid == uid and info.st_nlink == 1
                  and stat.S_IMODE(info.st_mode) == 0o600, "HOST_RESOURCE_LOCK")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        changed = False
        with SystemdBus(user=True, timeout=10) as bus:
            state = _state(bus, config)
            if state["ActiveState"] == "active":
                # Existing tasks may live here. Readiness can succeed but no
                # repair, reset, stop or resource update is permitted.
                q.require(_limits_match(state, config), "HOST_RESOURCE_ACTIVE_DRIFT")
            else:
                path = Path("/sys/fs/cgroup" + config["parent"])
                q.require(not path.exists(), "HOST_RESOURCE_NOT_CLOSED")
                if not _limits_match(state, config):
                    bus.call("SetUnitProperties", (("s", config["unit"]), ("b", True),
                             ("a(sv)", list(config["limits"].items()))))
                    changed = True
                state = _state(bus, config)
                q.require(state["ActiveState"] == "inactive" and _limits_match(state, config),
                          "HOST_RESOURCE_CONFIGURATION_CHANGED")
                job = bus.run_job(config["unit"], "StartUnit", lambda _: None, mode="ignore-requirements")
                q.require(job["result"] == "done", "HOST_RESOURCE_START_FAILED")
                changed = True
                state = _state(bus, config)
                q.require(state["ActiveState"] == "active" and _limits_match(state, config),
                          "HOST_RESOURCE_NOT_READY")
            _kernel_check(config)
            return {"ready": True, "changed": changed, "unit": config["unit"],
                    "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                    "invocation_id": state.get("InvocationID")}
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    # Public non-secret input, but owned and writable only by the administrator.
    config = json.loads(startup.protected_read(args.config, owner_uid=0, maximum=16384))
    print(json.dumps(prepare(config), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
