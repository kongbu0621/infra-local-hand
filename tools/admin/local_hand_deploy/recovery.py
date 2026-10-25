"""Read-only corrective planning for an owned, partially published deployment.

The source remains the original restoration target. Observed mixed files are
only preconditions for the next fixed actions, never a releasable baseline.
"""
from __future__ import annotations

import copy

from local_hand_jobs import startup

from . import files
from .model import DeployError
from .runtime import ConcreteEnvironment, PlanningEnvironment
from .services import tree_snapshot


def fixed_profile(profile):
    value = copy.deepcopy(profile)
    for key in ("recovery_from", "security_repair", "gateway_checks"):
        value.pop(key, None)
    if value.get("gateway"):
        value["gateway"].pop("compose", None)
        value["gateway"].pop("original_compose", None)
        value["gateway"].pop("retained_composes", None)
    return value


def origins(store, op):
    return [store.get(value) for value in op.get("inherited", [])] + [op]


def entries(chain):
    for op in chain:
        for step, record in zip(op["plan"]["steps"], op["steps"]):
            if record["prepared"] is not None:
                yield step, record["prepared"], record["attempts"], record["effective"] or record["state"] == "VERIFIED"
        for entry in op.get("compensation", []):
            record = entry["record"]
            yield entry["step"], record["restore"], record["restore_attempts"], record["state"] == "RESTORED"


def closed_effects(store, gate, op):
    """Observe the latest responsible caller per object without saving records."""
    chain = origins(store, op)
    env = ConcreteEnvironment(op["plan"], store, gate)
    covered = set()
    for step, prepared, attempts, effective in reversed(list(entries(chain))):
        key = env.effect_key(step)
        if key in covered or not (attempts or effective):
            continue
        value = env.observe(step, prepared, attempts[-1] if attempts else None)
        if value.get("closed") is not True or value.get("state") in {"unknown", "running"}:
            raise DeployError("CALLER_NOT_CLOSED", "The original caller or system job still needs reconciliation")
        # Known independent changes are not silently made ours. New file steps
        # bind their current handles; compensation still checks old ownership.
        covered.add(key)
    return chain


def reload_tree(profile, chain):
    if not profile.get("systemd"):
        return {}
    scope = profile["systemd"]["reload_scope"]
    current = tree_snapshot(scope["roots"])
    history = [scope["loaded_snapshot"]]
    owned = {}
    for step, prepared, _, _ in entries(chain):
        if step["kind"] == "file":
            # Exact held identities for every retained object, not a staging
            # filename exclusion from the shared systemd reload boundary.
            for item in files.preparation_objects(prepared):
                snapshot = item["snapshot"]
                owned[item["path"]] = [{"kind": "file", "digest": snapshot["sha256"],
                    **{key: snapshot[key] for key in ("mode", "uid", "gid")}}]
            values = owned.setdefault(prepared["target"], [])
            for key in ("original", "staged"):
                item = prepared.get(key)
                if item is None:
                    values.extend([None, {"kind": "absent"}]); continue
                snapshot = item.get("snapshot", item)
                if not snapshot.get("exists", True):
                    values.extend([None, {"kind": "absent"}]); continue
                values.append({"kind": "file", "digest": snapshot["sha256"],
                    **{name: snapshot[name] for name in ("mode", "uid", "gid")}})
        elif step["action"]["kind"] == "service_daemon_reload":
            history.extend([prepared["before"], prepared["after"]])
        elif step["action"]["kind"] == "service_policy_link":
            # Metadata remains part of the tree comparison. Prepared reload
            # snapshots carry the exact expected link uid/gid/mode.
            pass
    for path in set(current).union(*(set(tree) for tree in history), owned):
        allowed = [tree.get(path) for tree in history] + owned.get(path, [])
        if current.get(path) not in allowed:
            raise DeployError("RELOAD_SCOPE_CHANGED", "Shared reload input changed outside recorded deployment effects")
    return current


def context(store, gate, op, profile, *, successor=None):
    if op["released"] or (op["successor"] and op["successor"] != successor):
        raise DeployError("RECOVERY_CONFLICT", "The operation has already released or handed off its responsibility")
    if fixed_profile(profile) != fixed_profile(op["plan"]["profile"]):
        raise DeployError("RECOVERY_SCOPE_CHANGED", "A correction cannot change the fixed managed targets or adapter support scope")
    state = gate.snapshot()
    if not op["gate_owned"] or state["state"] != "CLOSED" or state["owner"] != (successor or op["id"]):
        raise DeployError("RECOVERY_CONFLICT", "Corrective planning requires the matching closed maintenance owner")
    selection = startup.read_selection(profile["startup_descriptor"], owner_uid=profile.get("owner_uid", 0))
    chain = closed_effects(store, gate, op)
    env = ConcreteEnvironment(op["plan"], store, gate)
    env._verify_selection_owner(op, selection)
    return {"operation": op["id"], "plan_digest": op["plan"]["digest"],
            "selection_digest": startup.digest(selection), "reload_tree": reload_tree(profile, chain)}


class RecoveryPlanningEnvironment(PlanningEnvironment):
    """Only used after context() has proved the original closed responsibility."""
    def validate_baseline(self, node_id, source, target, file_plan):
        current = startup.read_selection(self.profile["startup_descriptor"], owner_uid=self.owner)
        if current["node_id"] != node_id or startup.digest(current) != self.profile["recovery_from"]["selection_digest"]:
            raise DeployError("BASELINE_CHANGED", "The recorded mixed startup state changed before corrective planning")
        self.validate_target(target, file_plan)


def validate_link(plan, store, gate, predecessor, *, successor=None):
    expected = plan["profile"].get("recovery_from")
    if not expected or expected["operation"] != predecessor["id"]:
        raise DeployError("RECOVERY_REQUIRED", "A partial deployment needs a corrective plan bound to this predecessor")
    if context(store, gate, predecessor, plan["profile"], successor=successor) != expected:
        raise DeployError("RECOVERY_CONFLICT", "Corrective planning observations have changed")
    original = origins(store, predecessor)[0]["plan"]["source"]
    if plan["source"]["selection"] != original["selection"]:
        raise DeployError("RECOVERY_CONFLICT", "The original restoration target cannot become the observed mixed state")
    unsafe = {item["plan"]["profile"]["security_repair"]["unsafe_deployment_digest"]
              for item in origins(store, predecessor) if item["plan"]["profile"].get("security_repair")}
    if plan["target"]["deployment_digest"] in unsafe:
        raise DeployError("UNSAFE_REPAIR_TARGET", "A corrective target cannot reopen an already unsafe deployment")
