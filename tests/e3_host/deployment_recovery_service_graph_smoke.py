"""Opt-in fixed dependency / hook verification against a real systemd manager.

Creates two random, bounded temporary services only. No daemon reload, enable,
existing service changes, business resources or external network. The hooks
write only this fixture's event file. Tests the production planner ordering,
service adapter and D-Bus transport; not a complete production migration.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from admin.local_hand_deploy.planner import action_order
from admin.local_hand_deploy.services import HOOKS, SystemdAdapter
from admin.local_hand_deploy.supervision import AdapterError
from admin.local_hand_deploy.systemd_bus import SystemdBus


def main(*, user):
    if not user and os.geteuid() != 0:
        raise RuntimeError("system manager verification requires root")
    unitroot = (Path("/run/user") / str(os.geteuid()) / "systemd/user" if user else Path("/run/systemd/system"))
    if not unitroot.is_dir():
        raise RuntimeError("manager runtime unit directory is unavailable")
    prefix = "lh-deploy-graph-" + uuid.uuid4().hex[:12]
    manager, mcp = prefix + "-manager.service", prefix + "-mcp.service"
    paths, events = [], []
    with tempfile.TemporaryDirectory(prefix="lh-deploy-graph-") as temp:
        root = Path(temp)
        helper, log, failure = root / "hook.py", root / "events", root / "fail"
        helper.write_text("import os,sys\nfrom pathlib import Path\n"
                          "with open(sys.argv[1], 'a') as f: f.write(sys.argv[3]+'\\n'); f.flush(); os.fsync(f.fileno())\n"
                          "sys.exit(1 if Path(sys.argv[2]).exists() and sys.argv[3]=='mcp.pre' else 0)\n")
        helper.chmod(0o600)
        try:
            for name, component in ((manager, "manager"), (mcp, "mcp")):
                path = unitroot / name
                binding = f"Requires={manager}\nAfter={manager}\n" if component == "mcp" else ""
                hook = f"/usr/bin/python3 -I -B {helper} {log} {failure} {component}"
                with path.open("x") as stream:
                    stream.write("[Unit]\nDescription=Isolated deployment graph verification\nDefaultDependencies=no\n"
                                 + binding + "[Service]\nType=exec\nExecStart=/usr/bin/sleep 90\n"
                                 + f"ExecStartPre={hook}.pre\nExecStopPost={hook}.post\n"
                                 + "Restart=no\nKillMode=control-group\nRuntimeMaxSec=90s\nTimeoutStartSec=8s\nTimeoutStopSec=8s\n")
                paths.append(path)
            factory = lambda: SystemdBus(user=user, timeout=10)
            with factory() as keeper:
                for name in (manager, mcp):
                    keeper.call("LoadUnit", (("s", name),)); keeper.call("RefUnit", (("s", name),))
                units = {}
                for name, component in ((manager, "manager"), (mcp, "mcp")):
                    value = keeper.unit(name)
                    units[name] = {"component": component, "hooks": {key: [entry[:3] for entry in value.get(key, [])]
                                                                           for key in HOOKS if value.get(key)},
                                   "read_only_dependencies": sorted(set(value.get("Requires", [])) | set(value.get("Wants", []))),
                                   "inactive_conflicts": value.get("Conflicts", []), "start_job_mode": "ignore-requirements"}
                profile = {"systemd": {"manager": "user" if user else "system", "units": units},
                           "probes": {"manager": {"kind": "resident"}, "mcp": {"kind": "mcp"}}}
                adapter = SystemdAdapter(profile["systemd"], None, bus_factory=factory)
                def actions(kind, names):
                    phase = "after_reload" if kind == "service_start" else "quiesced_before_files"
                    values = [{"kind": "service", "action": {"kind": kind, "target": name, "phase": phase}} for name in names]
                    return [item["action"] for item in sorted(values, key=lambda item: action_order(item, profile))]
                def run(action):
                    return adapter._perform(action, events.append)
                starts, stops = actions("service_start", (mcp, manager)), actions("service_stop", (manager, mcp))
                assert [a["target"] for a in starts] == [manager, mcp]
                assert [a["target"] for a in stops] == [mcp, manager]
                for action in starts:
                    assert run(action)["result"] == "done"
                identities = {name: keeper.unit(name)["InvocationID"] for name in (manager, mcp)}
                count = len(events)
                try:
                    run(stops[1])
                except AdapterError as error:
                    assert "SERVICE_STOP_DEPENDENT_NOT_CLOSED" in str(error)
                else:
                    raise AssertionError("manager stop implicitly affected active MCP")
                assert len(events) == count
                assert identities == {name: keeper.unit(name)["InvocationID"] for name in (manager, mcp)}
                for action in stops:
                    assert run(action)["result"] == "done"
                assert log.read_text().splitlines() == ["manager.pre", "mcp.pre", "mcp.post", "manager.post"]
                assert run(starts[0])["result"] == "done"
                original = keeper.unit(manager)["InvocationID"]
                failure.touch()
                assert run(starts[1])["result"] != "done"
                assert keeper.unit(mcp)["ActiveState"] == "failed"
                assert keeper.unit(manager)["InvocationID"] == original
                failure.unlink()
                assert run(starts[1])["result"] == "done"
                assert keeper.unit(manager)["InvocationID"] == original
                for action in stops:
                    assert run(action)["result"] == "done"
                for name in (mcp, manager):
                    keeper.call("UnrefUnit", (("s", name),))
            result = {"status": "PASSED", "manager": "user" if user else "system", "ordered_start_stop": True,
                      "active_reverse_dependency_rejected_before_dispatch": True, "actual_pre_and_post_hooks": True,
                      "hook_failure_then_recovery": True, "dependency_not_restarted": True,
                      "events": log.read_text().splitlines(), "shared_reload_exercised": False, "live_migration": False}
        finally:
            errors = []
            # Explicit dependent-first cleanup, never stop the manager first.
            for path in reversed(paths):
                try:
                    with SystemdBus(user=user, timeout=10) as bus:
                        bus.run_job(path.name, "StopUnit", lambda _: None)
                    path.unlink()
                except Exception as error:
                    errors.append(type(error).__name__)
            if errors:
                raise RuntimeError("temporary service cleanup incomplete: " + ",".join(errors))
        result["temporary_units_removed"] = True
        print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--run-isolated-user-services", action="store_true")
    choice.add_argument("--run-isolated-system-services", action="store_true")
    args = parser.parse_args()
    main(user=args.run_isolated_user_services)
