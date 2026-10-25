"""Opt-in ordinary-user systemd verification of read-only BindsTo dependencies.

Uses two random temporary services, each bounded to 60 seconds. No existing
service, storage mount, enable link, daemon reload or external endpoint changes.
Exercises the production service adapter and D-Bus transport, including a real
dependency stop between its readiness read and start dispatch. The dependency
is a synthetic service; this is not live migration or physical storage testing.
"""
import argparse
import os
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from admin.local_hand_deploy.services import SystemdAdapter
from admin.local_hand_deploy.supervision import AdapterError
from admin.local_hand_deploy.systemd_bus import SystemdBus


def main():
    root = Path("/run/user") / str(os.geteuid()) / "systemd/user"
    if not root.is_dir():
        raise RuntimeError("user unit directory unavailable")
    prefix = "lh-deploy-dependency-" + uuid.uuid4().hex[:12]
    dependency, service = prefix + "-dep.service", prefix + "-managed.service"
    created, events = [], []
    def dependency_job(method):
        # One subscribed connection per job, as in the production adapter.
        with SystemdBus(user=True, timeout=5) as bus:
            return bus.run_job(dependency, method, events.append)
    try:
        for name, binding in ((dependency, ""), (service, f"BindsTo={dependency}\nAfter={dependency}\n")):
            path = root / name
            with path.open("x") as stream:
                stream.write("[Unit]\nDescription=Isolated deployment dependency verification\n"
                             "DefaultDependencies=no\n" + binding + "[Service]\nType=exec\n"
                             "ExecStart=/usr/bin/sleep 60\nRestart=no\nKillMode=control-group\nRuntimeMaxSec=60s\n")
            created.append(path)
        with SystemdBus(user=True, timeout=5) as keeper:
            for name in (dependency, service):
                keeper.call("LoadUnit", (("s", name),))
                keeper.call("RefUnit", (("s", name),))
            initial = keeper.unit(service)
            dependencies = sorted(set(initial.get("Requires", [])) | set(initial.get("Wants", []))
                                  | set(initial.get("Requisite", [])) | {dependency})
            profile = {"manager": "user", "units": {service: {
                "read_only_dependencies": dependencies, "read_only_bindings": [dependency],
                "start_job_mode": "ignore-requirements"}}}
            factory = lambda: SystemdBus(user=True, timeout=5)
            adapter = SystemdAdapter(profile, None, bus_factory=factory)
            start = {"kind": "service_start", "target": service}
            stop = {"kind": "service_stop", "target": service}
            try:
                adapter._perform(start, events.append)
            except AdapterError as error:
                if "SHARED_DEPENDENCY_NOT_READY" not in str(error):
                    raise
            else:
                raise AssertionError("inactive dependency accepted")
            assert not events
            dependency_job("StartUnit")
            original = keeper.unit(dependency)["InvocationID"]
            assert adapter._perform(start, events.append)["result"] == "done"
            assert keeper.unit(service)["ActiveState"] == "active"
            adapter._perform(stop, events.append)
            assert keeper.unit(dependency)["InvocationID"] == original
            assert keeper.unit(dependency)["ActiveState"] == "active"
            adapter._perform(start, events.append)
            dependency_job("StopUnit")
            deadline = time.monotonic() + 5
            while keeper.unit(service)["ActiveState"] not in ("inactive", "failed"):
                if time.monotonic() >= deadline:
                    raise TimeoutError("binding stop did not converge")
                time.sleep(0.03)
            dependency_job("StartUnit")

            class DependencyRace(SystemdBus):
                def run_job(self, unit, method, emit, *, mode="fail"):
                    # Actual state changes after the adapter's readiness read.
                    dependency_job("StopUnit")
                    return super().run_job(unit, method, emit, mode=mode)

            racing = SystemdAdapter(profile, None, bus_factory=lambda: DependencyRace(user=True, timeout=5))
            race = racing._perform(start, events.append)
            assert race["result"] != "done"
            assert keeper.unit(dependency)["ActiveState"] == "inactive"
            assert keeper.unit(service)["ActiveState"] in ("inactive", "failed")
            dependency_job("StartUnit")
            assert adapter._perform(start, events.append)["result"] == "done"
            assert keeper.unit(service)["ActiveState"] == "active"
            actual_modes = {e["job_mode"] for e in events if e.get("kind") == "dispatching"
                            and e["unit"] == service and e["method"] == "StartUnit"}
            assert actual_modes == {"ignore-requirements"}
            adapter._perform(stop, events.append)
            dependency_job("StopUnit")
            for name in (service, dependency):
                keeper.call("UnrefUnit", (("s", name),))
    finally:
        errors = []
        for path in reversed(created):
            try:
                with SystemdBus(user=True, timeout=5) as bus:
                    bus.run_job(path.name, "StopUnit", lambda _: None)
                path.unlink()
            except Exception as error:
                errors.append(type(error).__name__)
        if errors:
            raise RuntimeError("temporary service cleanup failed: " + ",".join(errors))
    print("PASSED: inactive dependency rejected; active dependency unchanged; BindsTo stop retained; "
          "read/dispatch race did not start dependency; explicit retry converged; temporary services cleaned")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-isolated-user-services", action="store_true", required=True)
    parser.parse_args()
    main()
