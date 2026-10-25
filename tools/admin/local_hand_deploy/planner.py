"""Read-only construction of the finite, node-local deployment plan.

Manifests select files and fixed service/container targets. They cannot name a
Python callable, command, plugin, probe program, or arbitrary shell operation.
"""
from __future__ import annotations

import copy
from pathlib import Path

from local_hand_jobs import startup

from .files import FileLimits, plan_files
from .model import DeployError, PLAN_SCHEMA, canonical, identity, seal_plan

MANIFEST_SCHEMA = "local-hand-deployment-manifest/v1"
PROFILE_SCHEMA = "local-hand-deployment-profile/v1"
PHASES = {"isolate": 0, "quiesced_before_files": 10, "after_stop": 20,
          "files": 30, "after_files": 40, "after_reload": 50, "after_create": 60}


def _path(value):
    if (not isinstance(value, str) or not Path(value).is_absolute()
            or str(Path(value)) != value or ".." in Path(value).parts):
        raise DeployError("INVALID_PLAN", "Expected a normalized absolute path")
    return value


def validate_profile(profile, source, target):
    allowed = {"schema", "owner_uid", "startup_descriptor", "maintenance_directory",
               "guarded_components", "probes", "systemd", "gateway", "file_limits",
               "timeout_seconds", "output_limit", "filesystem_support"}
    if (not isinstance(profile, dict) or set(profile) - allowed
            or profile.get("schema") != PROFILE_SCHEMA):
        raise DeployError("UNSUPPORTED_PROFILE", "Unknown deployment support profile")
    for key in ("startup_descriptor", "maintenance_directory"):
        _path(profile.get(key))
    owner = profile.get("owner_uid", 0)
    if type(owner) is not int or owner < 0:
        raise DeployError("UNSUPPORTED_PROFILE", "Invalid trusted local owner")
    timeout = profile.get("timeout_seconds", 30)
    output = profile.get("output_limit", 65536)
    if (type(timeout) is not int or not 1 <= timeout <= 120 or
            type(output) is not int or not 4096 <= output <= 1048576):
        raise DeployError("UNSUPPORTED_PROFILE", "Invalid fixed observation bounds")
    guards, probes = profile.get("guarded_components"), profile.get("probes")
    components = set(source["selection"]["components"]) | set(target["selection"]["components"])
    if (not isinstance(guards, dict) or set(guards) != components
            or not isinstance(probes, dict) or set(probes) != components):
        raise DeployError("UNGUARDED_ENTRY", "Every selected component needs its actual startup/admission guard and probe")
    for name, guard in guards.items():
        if not isinstance(guard, dict) or set(guard) != {"configuration", "entrypoints"}:
            raise DeployError("UNGUARDED_ENTRY", "Guard binding is incomplete")
        _path(guard["configuration"])
        if (not isinstance(guard["entrypoints"], list) or not 1 <= len(guard["entrypoints"]) <= 8
                or set(guard["entrypoints"]) - {"prepare", "execute", "listener", "cli"}):
            raise DeployError("UNGUARDED_ENTRY", "Unknown guarded entrypoint")
        if "prepare" in guard["entrypoints"] and not {"execute", "cli"}.issubset(guard["entrypoints"]):
            raise DeployError("UNGUARDED_ENTRY", "Preparation, first execution and local CLI share one barrier")
        probe = probes[name]
        if (not isinstance(probe, dict) or set(probe) - {"kind", "socket", "principal_id", "peer_uid"}
                or probe.get("kind") not in {"resident", "prepared", "mcp"}):
            raise DeployError("UNSUPPORTED_PROBE", "Only the protected deployment-status protocol is supported")
        _path(probe.get("socket"))
        if type(probe.get("peer_uid", 0)) is not int or probe.get("peer_uid", 0) < 0:
            raise DeployError("UNSUPPORTED_PROBE", "Invalid status peer")
    support = profile.get("filesystem_support")
    if (not isinstance(support, dict) or set(support) != {"ordinary_handles", "fsid", "reboot_verified"}
            or any(support[key] is not True for key in support)):
        raise DeployError("MIGRATION_NOT_READY", "The selected filesystem needs verified persistent ordinary handles and filesystem binding")
    return profile


def _selection(deployment, node_id):
    if not isinstance(deployment, dict) or set(deployment) - {"deployment_digest", "selection", "services", "gateway"}:
        raise DeployError("INVALID_PLAN", "Unknown deployment selection")
    selection = deployment.get("selection")
    try:
        startup.validate(selection)
    except (ValueError, TypeError, KeyError) as exc:
        raise DeployError("INVALID_PLAN", "Invalid complete startup selection") from exc
    if (selection["node_id"] != node_id or selection["deployment_digest"] != deployment.get("deployment_digest")
            or selection["mode"] != "stable"):
        raise DeployError("INVALID_PLAN", "Deployment must identify a complete stable selection")


def build_plan(manifest, environment=None):
    """Observe and return JSON only; do not create state dirs or supervisors.

    ``environment`` is a trusted embedding object, never a manifest-supplied
    import. The concrete default has only fixed local read-only observations.
    """
    required = {"schema", "request_id", "node_id", "source", "target", "files", "profile"}
    if (not isinstance(manifest, dict) or set(manifest) != required
            or manifest["schema"] != MANIFEST_SCHEMA or len(canonical(manifest)) > 1024 * 1024):
        raise DeployError("INVALID_PLAN", "Unknown or oversized deployment manifest")
    identity(manifest["request_id"], "request ID"); identity(manifest["node_id"], "node ID")
    source, target, profile = (copy.deepcopy(manifest[key]) for key in ("source", "target", "profile"))
    _selection(source, manifest["node_id"]); _selection(target, manifest["node_id"])
    validate_profile(profile, source, target)
    if set(source["selection"]["components"]) != set(target["selection"]["components"]):
        raise DeployError("UNSUPPORTED_PROFILE", "The fixed guarded component set cannot change")
    if (source["deployment_digest"] == target["deployment_digest"] and
            any(source["selection"][key] != target["selection"][key] for key in ("members", "components"))):
        raise DeployError("INVALID_PLAN", "One deployment identity cannot describe two configuration sets")
    managed = {spec.get("component") for spec in profile.get("systemd", {}).get("units", {}).values()}
    if profile.get("gateway"):
        managed.add(profile["gateway"].get("component"))
    if source["selection"] != target["selection"]:
        needed = {name for selection in (source["selection"], target["selection"])
                  for name, spec in selection["components"].items() if spec["running"]}
        if not needed.issubset(managed):
            raise DeployError("UNGUARDED_ENTRY", "Changed complete configuration set has an uncontrolled running component")
    limits = FileLimits(**profile.get("file_limits", {}))
    file_plan = plan_files(manifest["files"], limits=limits, owner_uid=profile.get("owner_uid", 0))
    if environment is None:
        from .runtime import PlanningEnvironment
        environment = PlanningEnvironment(profile)
    environment.validate_baseline(manifest["node_id"], source, target, file_plan)
    actions = []
    for entry in file_plan["files"]:
        original = {key: value for key, value in entry["original"].items() if key != "binding"}
        candidate = ({"exists": False} if entry["source"] is None else
                     {**{key: value for key, value in entry["source"]["snapshot"].items() if key != "binding"}, **entry["attributes"]})
        if original == candidate:
            continue
        actions.append({"kind": "file", "action": {**entry, "phase": "files"}})
    if source.get("services") or target.get("services"):
        if set(source.get("services", {})) != set(target.get("services", {})):
            raise DeployError("UNSUPPORTED_PROFILE", "The fixed service set cannot change in this deployment")
        for action in environment.plan_services(source, target, file_plan):
            actions.append({"kind": "service", "action": action})
    if source.get("gateway") is not None or target.get("gateway") is not None:
        if source.get("gateway") is None or target.get("gateway") is None:
            raise DeployError("UNSUPPORTED_PROFILE", "Gateway absence must be an explicit target")
        for action in environment.plan_gateway(source, target):
            actions.append({"kind": "gateway", "action": action})
    if any(item["action"].get("phase") not in PHASES for item in actions):
        raise DeployError("INVALID_PLAN", "Adapter returned an unknown deployment phase")
    actions.sort(key=lambda item: PHASES[item["action"]["phase"]])
    steps = [{"id": f"step-{number:03d}", **item} for number, item in enumerate(actions)]
    return seal_plan({"schema": PLAN_SCHEMA, "request_id": manifest["request_id"],
                      "node_id": manifest["node_id"], "source": source, "target": target,
                      "steps": steps, "profile": profile})
