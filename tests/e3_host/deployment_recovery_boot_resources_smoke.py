"""Opt-in real user-manager preparation of one random, empty resource slice.

No existing slices/services, business tasks, global reload or host reboot.
Runtime property files and the empty test cgroup are removed after the check.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from admin.local_hand_system_manager import host_resources as boot
from admin.local_hand_deploy.systemd_bus import SystemdBus


def await_removed(path):
    deadline = time.monotonic() + 5
    while path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not path.exists(), "temporary cgroup removal remains pending"


def main():
    uid = os.getuid()
    if uid <= 0:
        raise RuntimeError("run as a delegated ordinary user")
    name = "lhboot" + uuid.uuid4().hex[:12] + ".slice"
    config = {"schema": boot.SCHEMA, "uid": uid, "unit": name,
              "parent": f"/user.slice/user-{uid}.slice/user@{uid}.service/{name}", "limits": dict(boot.LIMITS)}
    root = Path(f"/run/user/{uid}/systemd/user.control/{name}.d")
    if root.exists() or Path("/sys/fs/cgroup" + config["parent"]).exists():
        raise RuntimeError("fixture collision")
    try:
        first = boot.prepare(config)
        second = boot.prepare(config)
        assert first["ready"] and first["changed"] and second["ready"] and not second["changed"]
        assert first["invocation_id"] == second["invocation_id"]
        # Real active limit drift must be refused without undoing it or restart.
        with SystemdBus(user=True, timeout=10) as bus:
            bus.call("SetUnitProperties", (("s", name), ("b", True), ("a(sv)", [("TasksMax", 65)])))
        try:
            boot.prepare(config)
        except ValueError as error:
            assert "ACTIVE_DRIFT" in str(error)
        else:
            raise AssertionError("active drift was accepted")
        with SystemdBus(user=True, timeout=10) as bus:
            state = bus.unit(name)
            assert state["TasksMax"] == 65 and state["InvocationID"] == first["invocation_id"]
            assert bus.run_job(name, "StopUnit", lambda _: None)["result"] == "done"
        await_removed(Path("/sys/fs/cgroup" + config["parent"]))
        # After the fixture is explicitly closed, the same input can prepare
        # again. This is not a business retry or evidence of a normal reboot.
        recovered = boot.prepare(config)
        assert recovered["ready"] and recovered["changed"]
        assert recovered["invocation_id"] != first["invocation_id"]
        result = {"status": "PASSED", "first_preparation": True, "repeat_no_effect": True,
                  "active_drift_rejected_without_update": True, "closed_resource_recovery": True,
                  "normal_reboot": False, "live_migration": False}
    finally:
        with SystemdBus(user=True, timeout=10) as bus:
            assert bus.run_job(name, "StopUnit", lambda _: None)["result"] == "done"
        if root.exists():
            for path in root.iterdir():
                path.unlink()
            root.rmdir()
        lock = Path(f"/run/user/{uid}/.local-hand-boot-{name}.lock")
        lock.unlink(missing_ok=True)
        await_removed(Path("/sys/fs/cgroup" + config["parent"]))
    result["temporary_resources_removed"] = True
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-isolated-user-resource", action="store_true", required=True)
    parser.parse_args()
    main()
