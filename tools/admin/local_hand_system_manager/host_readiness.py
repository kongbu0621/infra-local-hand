"""Read-only checks of the resident executor's already prepared host resources.

Unlike initialize_host this never starts units or changes cgroup limits. It is
safe to call while retained jobs still exist; quiescence remains a separate
maintenance/admission decision. Resource creation after boot is an explicit
infrastructure preparation step, not a side effect of a guarded service start.
"""
from pathlib import Path
import re

from local_hand_jobs import quota_contract as q
from admin.local_hand_deploy.systemd_bus import SystemdBus


def _cgroup(path):
    q.require(isinstance(path, str) and path.startswith("/") and path != "/"
              and str(Path(path)) == path and ".." not in Path(path).parts,
              "RESIDENT_PARENT_PATH")
    return Path("/sys/fs/cgroup" + path)


def check_host(config):
    observed = config["template"]["observed"]
    parents = observed["parents"]
    geometry = observed["system_geometry"]
    q.require(isinstance(parents, dict) and 1 <= len(parents) <= 16
              and isinstance(geometry, dict) and 1 <= len(geometry) <= 17,
              "RESIDENT_PARENT_BOUND")
    uid = config["uid"]
    q.require(type(uid) is int and uid > 0, "RESIDENT_ORDINARY_ACCOUNT")
    units = {}
    for spec in parents.values():
        path = spec["path"]
        _cgroup(path)
        name = Path(path).name
        q.require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,160}\.slice", name) is not None,
                  "RESIDENT_PARENT_UNIT")
        q.require(name not in units or units[name] == path, "RESIDENT_PARENT_UNIT")
        units[name] = path
    # The retained ordinary cgroup is owned by this separately prepared user
    # manager. Its actual limits are read below; no user bus/start is needed.
    units["user@" + str(uid) + ".service"] = None
    states = {}
    with SystemdBus(timeout=3) as bus:
        for name, path in units.items():
            state = bus.unit(name)
            q.require(state.get("LoadState") == "loaded" and state.get("ActiveState") == "active"
                      and state.get("Job", [None])[0] == 0, "RESIDENT_RUNTIME_NOT_READY")
            if path is not None:
                q.require(state.get("ControlGroup") == path, "RESIDENT_PARENT_CHANGED")
                q.require(_cgroup(path).is_dir(), "RESIDENT_PARENT_MISSING")
            states[name] = {key: state.get(key) for key in ("ActiveState", "ControlGroup", "InvocationID")}
    limits = {}
    for name, spec in geometry.items():
        if name == "schema":
            continue
        path = _cgroup(spec["parent"]["path"])
        quota, period = (path / "cpu.max").read_text().split()
        quota, period = int(quota), int(period)
        q.require(quota > 0 and period > 0, "RESIDENT_PARENT_LIMIT_CHANGED")
        measured = {"memory_bytes": int((path / "memory.max").read_text()),
                    "memory_swap_max": int((path / "memory.swap.max").read_text()),
                    "tasks_max": int((path / "pids.max").read_text()),
                    "cpu_quota_per_sec_usec": quota * 1000000 // period}
        q.require(all(type(spec.get(key)) is int and value == spec[key] for key, value in measured.items()),
                  "RESIDENT_PARENT_LIMIT_CHANGED")
        limits[name] = measured
    q.require("retained_ordinary_parent" in limits, "RESIDENT_RETAINED_PARENT_MISSING")
    return {"ready": True, "units": states, "limits": limits, "mutations": False}
