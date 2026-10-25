"""Private node bindings contain data only; every release uses the same planner.

No private installer imports, shell callbacks, automatic image builds or config
copies are allowed here. The source is observed, not reconstructed from a dated
installer's globals. Binding/release reads and plan generation are read-only.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

from local_hand_jobs import startup

from .model import DeployError, canonical, identity
from .planner import MANIFEST_SCHEMA, _selection, build_plan, validate_profile
from .runtime import PlanningEnvironment

BINDING_SCHEMA = "local-hand-node-binding/v1"
RELEASE_SCHEMA = "local-hand-release/v1"


def validate_binding(value):
    if (not isinstance(value, dict) or set(value) != {"schema", "node_id", "state", "profile"}
            or value["schema"] != BINDING_SCHEMA or len(canonical(value)) > 512 * 1024):
        raise DeployError("INVALID_BINDING", "Node binding must contain only fixed node, state and profile data")
    identity(value["node_id"], "node ID")
    state = value["state"]
    if (not isinstance(state, str) or not Path(state).is_absolute() or str(Path(state)) != state
            or ".." in Path(state).parts or not isinstance(value["profile"], dict)
            or value["profile"].get("owner_uid", 0) != os.geteuid()):
        raise DeployError("INVALID_BINDING", "Node binding must select the current trusted administrator and absolute state path")
    return copy.deepcopy(value)


def release_plan(binding, release, *, environment=None, _recovery=None):
    binding = validate_binding(binding)
    required = {"schema", "node_id", "request_id", "target", "files"}
    optional = {"gateway_compose", "security_repair", "gateway_checks"}
    if (not isinstance(release, dict) or not required <= set(release) or set(release) - required - optional
            or release["schema"] != RELEASE_SCHEMA or release["node_id"] != binding["node_id"]
            or len(canonical(release)) > 1024 * 1024):
        raise DeployError("INVALID_RELEASE", "Release must select this node and finite deployment inputs")
    profile = binding["profile"]
    if "security_repair" in profile or "recovery_from" in profile:
        raise DeployError("INVALID_BINDING", "One repair's evidence belongs in its release, not the permanent node binding")
    for name in ("security_repair", "gateway_checks"):
        if name in release: profile[name] = copy.deepcopy(release[name])
    if "gateway_compose" in release:
        if not profile.get("gateway"):
            raise DeployError("INVALID_RELEASE", "Release cannot add an uncontrolled gateway")
        profile["gateway"]["original_compose"] = copy.deepcopy(profile["gateway"]["compose"])
        profile["gateway"]["compose"] = copy.deepcopy(release["gateway_compose"])
    # Read the actual stable decision, including its generated decision_id.
    # Never substitute a stale target template from a prior release manifest.
    if _recovery:
        from .recovery import context, origins, RecoveryPlanningEnvironment
        store, gate, operation = _recovery
        profile["recovery_from"] = context(store, gate, operation, profile)
        chain = origins(store, operation)
        selection = chain[0]["plan"]["source"]["selection"]
        if profile.get("gateway"):
            retained = []
            for item in chain:
                gateway = item["plan"]["profile"].get("gateway", {})
                for value in [gateway.get("compose"), gateway.get("original_compose"), *gateway.get("retained_composes", [])]:
                    if value is not None and value not in retained:
                        retained.append(value)
            profile["gateway"]["retained_composes"] = retained
        environment = RecoveryPlanningEnvironment(profile)
    else:
        selection = startup.read_selection(profile["startup_descriptor"], owner_uid=profile.get("owner_uid", 0))
        if selection["mode"] != "stable" or selection["node_id"] != binding["node_id"]:
            raise DeployError("RECOVERY_REQUIRED", "An unfinished deployment requires its original record or explicit handoff")
    source = {"deployment_digest": selection["deployment_digest"], "selection": selection}
    target = copy.deepcopy(release["target"])
    _selection(target, binding["node_id"])
    validate_profile(profile, source, target)
    observer = environment or PlanningEnvironment(profile)
    if profile.get("systemd"):
        observed = observer.services.observe()
        if observed["jobs"]:
            raise DeployError("SERVICE_JOB_PENDING", "A selected service still has a manager job")
        source["services"] = {}
        for unit, spec in profile["systemd"]["units"].items():
            value = observed["units"][unit]
            expected = selection["components"][spec["component"]]
            running = value["active"] == "active"
            if value["active"] not in {"active", "inactive", "failed"} or not _recovery and running != expected["running"]:
                raise DeployError("BASELINE_CHANGED", "Actual service run state differs from the stable selection")
            source["services"][unit] = {"running": running, "policy": value["policy"],
                "definition_digest": value["definition_digest"], "config_digest": expected["configuration_digest"],
                "deployment_digest": selection["deployment_digest"]}
    if profile.get("gateway"):
        value = observer.gateway.observe(require_route=False)
        expected = selection["components"][profile["gateway"]["component"]]
        running = value.get("status") == "running"
        if value.get("status") == "transition" or not _recovery and running != expected["running"]:
            raise DeployError("BASELINE_CHANGED", "Actual gateway run state differs from the stable selection")
        configuration = ({"config_digest": expected["configuration_digest"], "deployment_digest": selection["deployment_digest"]}
                         if not _recovery else observer.gateway._configuration(value))
        if _recovery and value["kind"] == "container" and any(not isinstance(v, str) or len(v) != 64 for v in configuration.values()):
            raise DeployError("RECOVERY_CONFLICT", "An intermediate container lacks its recorded deployment identity")
        source["gateway"] = {"present": value["kind"] == "container", "running": running, **configuration}
    return build_plan({"schema": MANIFEST_SCHEMA, "request_id": release["request_id"], "node_id": binding["node_id"],
                       "source": source, "target": target, "files": copy.deepcopy(release["files"]),
                       "profile": profile}, observer)


def repair_plan(binding, release, operation_id):
    """Lock existing records for consistent observation; SQLite is read-only."""
    from local_hand_jobs.maintenance import MaintenanceGate
    from .store import Store
    binding = validate_binding(binding)
    store = Store(binding["state"], binding["node_id"])
    gate = MaintenanceGate(binding["profile"]["maintenance_directory"], binding["node_id"],
                           owner_uid=binding["profile"].get("owner_uid", 0))
    with store.locked(readonly=True):
        operation = store.get(operation_id)
        if operation["released"] or not operation["gate_owned"]:
            return release_plan(binding, release)
        return release_plan(binding, release, _recovery=(store, gate, operation))
