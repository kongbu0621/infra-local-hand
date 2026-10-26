"""Finite ordinary-systemd-service deployment adapter.

No restart operation exists: stop, policy links, shared reload and start are
separate effects. The coordinator publishes definitions between stop and reload.
Automatic activation requires an installed startup guard supplied by the runtime.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat

from .files import _binding
from .supervision import AdapterError, boot_id, digest, verify_lock
from .systemd_bus import SystemdBus


UNIT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,160}\.service\Z")
BOUND_UNIT = re.compile(r"[A-Za-z0-9-][A-Za-z0-9_.@\\-]{0,240}\.(?:service|mount)\Z")
POLICIES = {"enabled", "enabled-runtime", "disabled", "static", "absent"}
STOPPED = {"inactive", "failed"}
FORBIDDEN_PROPAGATION = ("PartOf", "ConsistsOf", "BoundBy", "PropagatesStopTo", "StopPropagatedFrom", "OnFailure", "OnSuccess", "TriggeredBy", "Triggers", "Upholds", "UpheldBy")
HOOKS = ("ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost", "ExecReload", "ExecCondition")
DEFINITION_FIELDS = ("Type", "Restart", "KillMode", "ExecStart", *HOOKS, *FORBIDDEN_PROPAGATION, "BindsTo",
                     "Requires", "Wants", "Requisite", "Conflicts", "Before", "After", "FragmentPath", "DropInPaths")


def _hex(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def definition_digest(properties):
    configuration = {key: properties.get(key, []) for key in DEFINITION_FIELDS}
    # Exec* replies also contain last execution timestamps, PID and exit status.
    # Those are instance observations, never part of the loaded definition hash.
    for key in ("ExecStart", *HOOKS):
        configuration[key] = [entry[:3] for entry in configuration[key]]
    return digest(configuration)


def tree_snapshot(roots, *, max_files=8192, max_bytes=16777216):
    """Finite metadata/content manifest, including symlinks without following them."""
    result, total = {}, 0
    def visit(path):
        nonlocal total
        if len(result) >= max_files:
            raise AdapterError("RELOAD_TREE_FILE_BOUND")
        try:
            info = path.lstat()
        except FileNotFoundError:
            result[str(path)] = {"kind": "absent"}
            return
        common = {"mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid}
        if stat.S_ISLNK(info.st_mode):
            result[str(path)] = {**common, "kind": "link", "target": os.readlink(path)}
        elif stat.S_ISDIR(info.st_mode):
            result[str(path)] = {**common, "kind": "directory"}
            for child in sorted(path.iterdir()):
                visit(child)
        elif stat.S_ISREG(info.st_mode):
            if info.st_size > max_bytes - total:
                raise AdapterError("RELOAD_TREE_BYTE_BOUND")
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
            try:
                current = os.fstat(fd)
                if (current.st_dev, current.st_ino, current.st_size) != (info.st_dev, info.st_ino, info.st_size):
                    raise AdapterError("RELOAD_TREE_CHANGED")
                raw = os.read(fd, info.st_size + 1)
                if len(raw) != info.st_size or os.fstat(fd).st_mtime_ns != info.st_mtime_ns:
                    raise AdapterError("RELOAD_TREE_CHANGED")
            finally:
                os.close(fd)
            total += len(raw)
            result[str(path)] = {**common, "kind": "file", "digest": hashlib.sha256(raw).hexdigest()}
        else:
            raise AdapterError("RELOAD_TREE_SPECIAL_OBJECT")
    for root in roots:
        path = Path(root)
        if not path.is_absolute() or ".." in path.parts:
            raise AdapterError("RELOAD_TREE_PATH")
        visit(path)
    return result


def _link_state(path):
    try:
        # Bind the link itself, including its filesystem generation, without
        # following even a dangling target. Inode numbers alone are reusable.
        fd = os.open(path, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return {"kind": "absent"}
    try:
        info = os.fstat(fd)
        if not stat.S_ISLNK(info.st_mode):
            raise AdapterError("ENABLE_LINK_CONFLICT")
        return {"kind": "link", "target": os.readlink('', dir_fd=fd), "dev": info.st_dev,
                "ino": info.st_ino, "binding": _binding(fd)}
    finally:
        os.close(fd)


def _same_link(actual, expected):
    """Compare exact objects; old dev/ino-only snapshots cannot prove identity."""
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    if actual.get('kind') == expected.get('kind') == 'absent':
        return True
    return (actual.get('kind') == expected.get('kind') == 'link'
            and actual.get('target') == expected.get('target')
            and isinstance(actual.get('binding'), dict) and bool(actual['binding'])
            and actual['binding'] == expected.get('binding'))


def _sync_link_directory(path, expected):
    """Finish only the directory sync; never repeat a link/unlink effect."""
    path = Path(path)
    parent = path.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid() or parent.st_mode & 0o022:
        raise AdapterError("ENABLE_LINK_PARENT")
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        held = os.fstat(fd)
        if (held.st_dev, held.st_ino) != (parent.st_dev, parent.st_ino) or not _same_link(_link_state(path), expected):
            raise AdapterError("ENABLE_LINK_CHANGED")
        os.fsync(fd)
        current = path.parent.lstat()
        if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino) or not _same_link(_link_state(path), expected):
            raise AdapterError("ENABLE_LINK_CHANGED")
        return expected
    finally:
        os.close(fd)


def validate_guard(value, target, *, attempt_id=None, allow_stopped=False):
    if not isinstance(value, dict) or not all(_hex(value.get(k)) for k in
                                              ("descriptor_digest", "config_digest", "deployment_digest")):
        raise AdapterError("STARTUP_GUARD_PROOF_REQUIRED")
    stopped_creation = allow_stopped and target.get("running") is False and value.get("target_running") is False
    if value.get("mode") not in ("candidate", "stable") or not (value.get("target_running") is True or stopped_creation):
        raise AdapterError("STARTUP_GUARD_BLOCKED")
    if value["config_digest"] != target["config_digest"] or value["deployment_digest"] != target["deployment_digest"]:
        raise AdapterError("STARTUP_GUARD_CONFIG_MISMATCH")
    if value["mode"] == "candidate" and (value.get("boot") != boot_id() or value.get("attempt_id") != attempt_id):
        raise AdapterError("STARTUP_GUARD_PERMIT_MISMATCH")
    return value


class SystemdAdapter:
    def __init__(self, profile, runner, *, bus_factory=None, guard_check=None, loaded_probe=None):
        self.profile, self.runner = profile, runner
        self.units = profile.get("units", {})
        if not self.units or len(self.units) > 8 or any(not UNIT.fullmatch(name) for name in self.units):
            raise AdapterError("FIXED_SERVICE_SET_REQUIRED")
        if profile.get("manager", "system") not in ("system", "user"):
            raise AdapterError("SYSTEMD_MANAGER_SCOPE")
        for spec in self.units.values():
            bindings = spec.get("read_only_bindings", [])
            if (not isinstance(bindings, list) or len(bindings) > 32
                    or any(not isinstance(name, str) or not BOUND_UNIT.fullmatch(name) for name in bindings)
                    or len(set(bindings)) != len(bindings)
                    or set(bindings) - set(spec.get("read_only_dependencies", []))):
                raise AdapterError("READ_ONLY_SERVICE_BINDINGS_REQUIRED")
            mode = spec.get("start_job_mode", "fail")
            if mode not in ("fail", "ignore-requirements") or (bindings and mode != "ignore-requirements"):
                raise AdapterError("READ_ONLY_BINDING_JOB_MODE_REQUIRED")
        self.bus_factory = bus_factory or (lambda: SystemdBus(user=profile.get("manager") == "user", timeout=min(runner.timeout / 2, 30)))
        self.guard_check, self.loaded_probe = guard_check, loaded_probe

    def _snapshot(self, bus, unit, *, starting=False):
        value = bus.unit(unit)
        load, active = value.get("LoadState"), value.get("ActiveState")
        if load not in ("loaded", "not-found") or active not in ("active", "inactive", "failed", "activating", "deactivating"):
            raise AdapterError("UNSUPPORTED_SERVICE_TRANSITION")
        policy = value.get("UnitFileState", "absent" if load == "not-found" else None)
        if policy not in POLICIES:
            raise AdapterError("UNSUPPORTED_ENABLE_POLICY")
        if load == "loaded":
            if value.get("Type") not in ("simple", "exec") or value.get("KillMode") != "control-group":
                raise AdapterError("UNSUPPORTED_SERVICE_TYPE")
            for key in FORBIDDEN_PROPAGATION:
                if value.get(key):
                    raise AdapterError("UNDECLARED_SERVICE_PROPAGATION:" + key)
            bindings = set(value.get("BindsTo", []))
            if bindings != set(self.units[unit].get("read_only_bindings", [])):
                raise AdapterError("UNDECLARED_SERVICE_PROPAGATION:BindsTo")
            if bindings - set(value.get("After", [])):
                raise AdapterError("SERVICE_BINDING_ORDER_REQUIRED")
            hooks = self.units[unit].get("hooks", {})
            if any([entry[:3] for entry in value.get(key, [])] != hooks.get(key, []) for key in HOOKS):
                raise AdapterError("UNDECLARED_SERVICE_HOOK")
            dependencies = set(value.get("Requires", [])) | set(value.get("Wants", [])) | set(value.get("Requisite", [])) | bindings
            if dependencies - set(self.units[unit].get("read_only_dependencies", [])):
                raise AdapterError("UNDECLARED_SERVICE_DEPENDENCY")
            if value.get("Restart") not in self.units[unit].get("restart_modes", ["no"]):
                raise AdapterError("UNGUARDED_SERVICE_RESTART")
            if starting:
                for dependency in dependencies:
                    dep = bus.unit(dependency)
                    if dep.get("ActiveState") != "active" or dep.get("Job", [0])[0]:
                        raise AdapterError("SHARED_DEPENDENCY_NOT_READY")
            conflicts = set(value.get("Conflicts", [])) - set(self.units[unit].get("inactive_conflicts", []))
            if conflicts:
                raise AdapterError("UNDECLARED_SERVICE_CONFLICT")
            if starting:
                for conflict in value.get("Conflicts", []):
                    if bus.unit(conflict).get("ActiveState") not in STOPPED:
                        raise AdapterError("SERVICE_CONFLICT_NOT_STOPPED")
        links = {path: _link_state(path) for path in self.units[unit].get("policy_links", {})}
        loaded = None
        if active == "active" and self.loaded_probe is not None:
            loaded = self.loaded_probe(unit)
            if not isinstance(loaded, dict):
                raise AdapterError("LOADED_CONFIG_PROOF_REQUIRED")
        return {"unit": unit, "boot": boot_id(), "load": load, "policy": policy, "active": active,
                "substate": value.get("SubState"), "invocation_id": value.get("InvocationID"),
                "pid": value.get("MainPID", 0), "job": value.get("Job", [0, "/"]),
                "definition_digest": definition_digest(value), "links": links, "loaded": loaded,
                "stop_dependents": sorted(set(value.get("RequiredBy", [])) | set(value.get("RequisiteOf", []))),
                "needs_reload": value.get("NeedDaemonReload", False)}

    def _stop_dependents(self, unit, snapshot):
        dependents = snapshot.get("stop_dependents", [])
        for dependent in dependents:
            if (dependent not in self.units or unit not in self.units[dependent].get("read_only_dependencies", [])):
                raise AdapterError("UNDECLARED_SERVICE_STOP_DEPENDENT")
        return dependents

    def observe(self):
        with self.bus_factory() as bus:
            snapshots = {unit: self._snapshot(bus, unit) for unit in self.units}
            jobs = [row for row in bus.jobs() if row[1] in self.units]
        return {"units": snapshots, "jobs": jobs, "boot": boot_id()}

    def check_reload_scope(self, expected=None):
        scope = self.profile.get("reload_scope")
        if not isinstance(scope, dict) or not scope.get("roots") or not scope.get("loaded_snapshot"):
            raise AdapterError("GLOBAL_RELOAD_LOADED_BASELINE_REQUIRED")
        # Roots must contain all unit search paths AND generator programs, inputs,
        # and outputs declared by the protected, version-specific support profile.
        for key in ("unit_search_roots", "generator_program_roots", "generator_inputs", "generator_output_roots"):
            if key not in scope or not set(scope[key]).issubset(set(scope["roots"])):
                raise AdapterError("GLOBAL_RELOAD_SCOPE_INCOMPLETE:" + key)
        current = tree_snapshot(scope["roots"])
        expected = scope["loaded_snapshot"] if expected is None else expected
        if current != expected:
            raise AdapterError("GLOBAL_RELOAD_UNACCOUNTED_CHANGES")
        return current

    def plan(self, targets, baseline=None, *, _check_global=True):
        """Pure observation; resulting actions must be merged with file ordering.

        Targets are a subset of the fixed profile. Reload is requested separately
        with plan_reload after exact expected published tree has been constructed.
        """
        if set(targets) - set(self.units):
            raise AdapterError("SERVICE_OUTSIDE_PROFILE")
        before = self.observe() if baseline is None else baseline
        if before["jobs"]:
            raise AdapterError("SERVICE_JOB_PENDING")
        if _check_global:
            self.check_reload_scope()
        actions = []
        for unit, target in targets.items():
            old = before["units"][unit]
            if not isinstance(target.get("running"), bool) or target.get("policy") not in POLICIES:
                raise AdapterError("SERVICE_TARGET")
            if old["active"] not in STOPPED | {"active"}:
                raise AdapterError("SERVICE_JOB_PENDING")
            loaded = old["loaded"] or {}
            needs_stop = old["active"] == "active" and (not target["running"] or
                old["definition_digest"] != target.get("definition_digest", old["definition_digest"]) or
                any(loaded.get(key) != target.get(key) for key in ("config_digest", "deployment_digest")))
            if needs_stop:
                self._stop_dependents(unit, old)
                actions.append({"kind": "service_stop", "target": unit, "before": old,
                                "after": {"running": False}, "subeffects": ["stop"], "phase": "quiesced_before_files"})
            # Finite exact links instead of systemctl enable/disable, whose Also=
            # expansion and implicit daemon reload would exceed the scope.
            for path, link in self.units[unit].get("policy_links", {}).items():
                want = {"kind": "link", "target": link["target"]} if target["policy"] == link["policy"] else {"kind": "absent"}
                actual = old["links"][path]
                if actual.get("kind") != want["kind"] or actual.get("target") != want.get("target"):
                    if actual.get("kind") == want["kind"] == "link":
                        raise AdapterError("UNSUPPORTED_ENABLE_LINK_RELOCATION")
                    actions.append({"kind": "service_policy_link", "target": unit, "path": path,
                                    "before": actual, "after": want, "subeffects": ["link"], "phase": "files"})
            if target["running"] and (old["active"] != "active" or needs_stop):
                if not all(_hex(target.get(key)) for key in ("config_digest", "deployment_digest", "definition_digest")):
                    raise AdapterError("SERVICE_TARGET_BINDING_REQUIRED")
                actions.append({"kind": "service_start", "target": unit, "before": old, "after": target,
                                "subeffects": ["start"], "phase": "after_reload"})
        stops = {action["target"] for action in actions if action["kind"] == "service_stop"}
        for unit in stops:
            for dependent in self._stop_dependents(unit, before["units"][unit]):
                if before["units"][dependent]["active"] not in STOPPED and dependent not in stops:
                    raise AdapterError("DEPENDENT_STOP_NOT_PLANNED")
        return actions

    def plan_reload(self, expected_tree):
        self.check_reload_scope()
        return {"kind": "service_daemon_reload", "target": "manager", "before": self.profile["reload_scope"]["loaded_snapshot"],
                "after": expected_tree, "subeffects": ["manager_reload"], "phase": "after_files"}

    def plan_restore(self, original_actions, observations=None, *, retained_tree=None, retained_target=None,
                     policy_observations=None):
        """Build compensation by original targets, never by reversing commands.

        The coordinator restores files between quiesced_before_files and
        after_files; it must preserve this phase ordering across adapters.
        """
        policy_observations = policy_observations or {}
        owned_links = {}
        for action in original_actions:
            if action['kind'] != 'service_policy_link':
                continue
            path = action['path']
            observed = policy_observations.get(path) or {}
            current = _link_state(path)
            if (observed.get('outcome') not in {'original', 'target'} or observed.get('closed') is not True
                    or not _same_link(observed.get('observation'), current)):
                raise AdapterError('RESTORE_POLICY_LINK_CONFLICT')
            owned_links[path] = current
        targets = {}
        for action in original_actions:
            if action["kind"] in ("service_start", "service_stop"):
                old = action["before"]
                if action["target"] in targets:
                    continue
                loaded = old.get("loaded") or {}
                targets[action["target"]] = {"running": old["active"] == "active", "policy": old["policy"],
                    "definition_digest": old["definition_digest"], **{key: loaded.get(key) for key in ("config_digest", "deployment_digest")}}
        before = self.observe() if observations is None else observations
        restored = self.plan(targets, before, _check_global=False)
        for action in restored:
            if (action['kind'] == 'service_policy_link'
                    and not _same_link(owned_links.get(action['path']), action['before'])):
                raise AdapterError('RESTORE_POLICY_LINK_CONFLICT')
        addressed = {a.get("path") for a in restored if a["kind"] == "service_policy_link"}
        for action in original_actions:
            if action["kind"] != "service_policy_link" or action["path"] in addressed:
                continue
            current = owned_links[action['path']]
            original = {k: v for k, v in action["before"].items() if k in ("kind", "target")}
            observed = policy_observations[action['path']]
            pending_sync = observed.get('outcome') == 'target' and observed.get('synced') is not True
            if (current.get("kind") != original["kind"] or current.get("target") != original.get("target")
                    or pending_sync):
                restored.append({**action, "before": current, "after": original})
            addressed.add(action["path"])
        reloads = [a for a in original_actions if a["kind"] == "service_daemon_reload"]
        if reloads:
            current = tree_snapshot(self.profile["reload_scope"]["roots"])
            first = dict(reloads[0]["before"])
            history = [action[side] for action in reloads for side in ("before", "after")]
            retained_tree = {} if retained_tree is None else retained_tree
            retained_target = retained_tree if retained_target is None else retained_target
            if any(path not in retained_tree or retained_tree[path] != value
                   for path, value in retained_target.items()):
                raise AdapterError("RETAINED_RELOAD_TARGET_NOT_OBSERVED")
            if any(path in first and first[path] != value for path, value in retained_target.items()):
                raise AdapterError("RETAINED_RELOAD_OBJECT_COLLIDES_WITH_ORIGINAL")
            # The runtime supplies exact file-handle-verified retained objects,
            # never a filename-pattern exclusion. Rename-consumed staging
            # objects may be present now but must not enter the restored tree.
            first.update(retained_target)
            for path in set(current).union(retained_tree, *(set(tree) for tree in history)):
                allowed = [tree.get(path) for tree in history]
                if path in retained_tree:
                    allowed.append(retained_tree[path])
                if current.get(path) not in allowed:
                    raise AdapterError("RESTORE_GLOBAL_RELOAD_UNACCOUNTED_CHANGES")
            restored.append({"kind": "service_daemon_reload", "target": "manager", "before": current,
                             "after": first, "subeffects": ["manager_reload"], "phase": "after_files"})
        order = {"quiesced_before_files": 0, "files": 1, "after_files": 2, "after_reload": 3}
        return sorted(restored, key=lambda action: order[action["phase"]])

    def _validate_action(self, action):
        kind = action.get("kind")
        if kind not in ("service_start", "service_stop", "service_policy_link", "service_daemon_reload"):
            raise AdapterError("SERVICE_ACTION")
        if kind != "service_daemon_reload" and action.get("target") not in self.units:
            raise AdapterError("SERVICE_OUTSIDE_PROFILE")
        if kind == "service_policy_link":
            spec = self.units[action["target"]].get("policy_links", {}).get(action.get("path"))
            if not spec or action["after"].get("kind") not in ("link", "absent"):
                raise AdapterError("SERVICE_POLICY_LINK_OUTSIDE_PROFILE")
            if action["after"].get("kind") == "link" and action["after"].get("target") != spec["target"]:
                raise AdapterError("SERVICE_POLICY_LINK_TARGET")

    def observe_action(self, action, previous=None, *, lock_fd=None):
        self._validate_action(action)
        if (previous and action['kind'] == 'service_policy_link'
                and previous.get('binding', previous).get('action_digest') != digest(action)):
            raise AdapterError('ATTEMPT_BINDING_CONFLICT')
        supervised = self.runner.observe(previous.get("binding", previous), lock_fd=lock_fd) if previous else None
        local_closed = supervised is None or supervised["closed"]
        events = supervised["events"] if supervised else []
        if not local_closed:
            return {"outcome": "running", "closed": False, "postcondition": False, "supervision": supervised,
                    "dispatched": None}
        kind = action["kind"]
        if kind == "service_policy_link":
            actual = _link_state(action["path"])
            target = actual["kind"] == action["after"]["kind"] and actual.get("target") == action["after"].get("target")
            original = _same_link(actual, action["before"])
            result = supervised and supervised.get("result") or {}
            effects = [event.get('link') for event in events if event.get('kind') == 'policy_link_effect']
            returned = result.get('value') if result.get('status') == 'returned' else None
            receipt = returned.get('link') if isinstance(returned, dict) else None
            owned = effects[-1] if effects else receipt
            effect_recorded = bool(effects or receipt is not None)
            # New attempts persist the exact effect before syncing its parent.
            # Successful receipts also carry that identity. Historical receipts
            # with only dev/ino still prove an effect occurred, but cannot claim
            # today's object: a filesystem can immediately reuse the same inode.
            effect_matches = (isinstance(owned, dict) and owned.get('kind') == action['after']['kind']
                              and owned.get('target') == action['after'].get('target'))
            conflict = effect_recorded and (not effect_matches or not _same_link(actual, owned)
                          or receipt is not None and not _same_link(receipt, owned))
            known_target = target and not conflict and (_same_link(owned, actual) or original)
            outcome = ('conflict' if conflict else 'target' if known_target else 'original' if original
                       else 'unknown' if target and previous else 'conflict')
            # Visibility is not evidence that the parent directory was synced.
            # A returned _perform receipt follows fsync and binds the exact link.
            synced = bool(known_target and _same_link(receipt, actual))
            proof = ('published_identity' if actual['kind'] == 'link' else 'satisfied_observed') if known_target else None
            return {"outcome": outcome, "closed": True,
                    "postcondition": known_target and synced, "synced": synced, "observation": actual, "supervision": supervised,
                    "proof": "original_identity" if original and not conflict else proof,
                    "effective": effect_recorded,
                    "dispatched": True if effect_recorded else None if previous else False}
        with self.bus_factory() as bus:
            sender = next((event.get("sender") for event in reversed(events) if event.get("kind") == "bus_binding"), None)
            dispatch_recorded = any(event.get("kind") in ("dispatching", "reload_dispatching") for event in events)
            same_boot = not previous or previous.get("binding", previous).get("boot") == boot_id()
            fence = bus.fence_sender(sender) if sender and supervised and same_boot else None
            if fence is not None and not fence["closed"]:
                return {"outcome": "running", "closed": False, "postcondition": False, "supervision": supervised}
            jobs = [row for row in bus.jobs() if kind == "service_daemon_reload" or row[1] == action["target"]]
            if jobs:
                return {"outcome": "running", "closed": False, "postcondition": False, "jobs": jobs, "supervision": supervised}
            if kind == "service_daemon_reload":
                self.check_reload_scope(action["after"])
                snapshots = {unit: self._snapshot(bus, unit) for unit in self.units}
                target = not any(item["needs_reload"] for item in snapshots.values())
                # Reloading is a signal, not a systemd 255 Manager property.
                # Reload() returns after reload completion; a recovered sender
                # fence plus subsequent manager reply also crosses that queue.
                bus.properties("/org/freedesktop/systemd1", "org.freedesktop.systemd1.Manager")
                completed = any(event.get("kind") == "reload_returned" for event in events) or bool(fence and fence["closed"])
                closed = previous is None or completed or not dispatch_recorded
                return {"outcome": "target" if target and completed else "original" if closed else "unknown", "closed": closed,
                        "postcondition": target and completed, "observation": snapshots, "supervision": supervised,
                        "dispatched": dispatch_recorded}
            actual = self._snapshot(bus, action["target"])
        accepted = [event for event in events if event.get("kind") == "job_accepted"]
        removed = [event for event in events if event.get("kind") == "job_removed"]
        completed = bool(accepted and any(done["job_path"] == accepted[-1]["job_path"] for done in removed))
        if previous and not completed:
            completed = (previous.get("binding", previous).get("boot") != boot_id()
                         or bool(fence and fence["closed"]) or not dispatch_recorded)
        closed = local_closed and (not previous or completed)
        if kind == "service_stop":
            target = actual["active"] in STOPPED and actual["pid"] == 0 and not actual["job"][0]
        else:
            loaded, desired = actual["loaded"] or {}, action["after"]
            target = (actual["active"] == "active" and actual["definition_digest"] == desired["definition_digest"]
                      and loaded.get("invocation_id") == actual["invocation_id"] and loaded.get("pid") == actual["pid"]
                      and actual["pid"] > 0 and loaded.get("protocol_ready") is True
                      and all(loaded.get(key) == desired[key] for key in ("config_digest", "deployment_digest")))
        original = actual == action["before"]
        outcome = "target" if target and closed else "unknown" if not closed else "original" if original else "partial" if actual["active"] in STOPPED else "conflict"
        return {"outcome": outcome, "closed": closed, "postcondition": target and closed,
                "observation": actual, "supervision": supervised, "dispatched": dispatch_recorded}

    def execute(self, action, *, attempt_id, lock_fd, persist_intent, previous=None):
        self._validate_action(action)
        verify_lock(lock_fd)
        observed = self.observe_action(action, previous, lock_fd=lock_fd)
        if observed["postcondition"] or not observed["closed"] or observed['outcome'] == 'unknown':
            return observed
        if action["kind"] == "service_policy_link" and observed["outcome"] == "target":
            # The coordinator saves SYNC_INTENT before this no-attempt call.
            # No supervisor attempt or link mutation is replayed for durability.
            if attempt_id is None:
                _sync_link_directory(action["path"], observed["observation"])
                return {**observed, "synced": True, "postcondition": True}
            return observed
        if observed["outcome"] == "conflict":
            raise AdapterError("SERVICE_OBSERVATION_CONFLICT")
        # Never reuse an attempt identifier to dispatch. A new retry is explicitly
        # recorded by the coordinator after the preceding attempt was reconciled.
        if previous is not None and previous.get("binding", previous).get("attempt_id") == attempt_id:
            return observed
        if action["kind"] == "service_start":
            if self.guard_check is None:
                raise AdapterError("STARTUP_GUARD_REQUIRED")
            validate_guard(self.guard_check(action["target"], {**action["after"], "attempt_id": attempt_id}),
                           action["after"], attempt_id=attempt_id)
        outcome = self.runner.run(action, self._perform, attempt_id=attempt_id, lock_fd=lock_fd,
                                  persist_intent=persist_intent)
        return {**self.observe_action(action, outcome, lock_fd=lock_fd), "attempt": outcome}

    def _perform(self, action, emit):
        self._validate_action(action)
        kind = action["kind"]
        if kind == "service_policy_link":
            path = Path(action["path"])
            if not _same_link(_link_state(path), action["before"]):
                raise AdapterError("ENABLE_LINK_CHANGED")
            parent = path.parent.lstat()
            if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid() or parent.st_mode & 0o022:
                raise AdapterError("ENABLE_LINK_PARENT")
            if action["after"]["kind"] == "absent":
                path.unlink()
            else:
                if action["before"]["kind"] != "absent":
                    raise AdapterError("ENABLE_LINK_REPLACEMENT_REQUIRES_SEPARATE_REMOVE")
                os.symlink(action["after"]["target"], path)
            effect = _link_state(path)
            emit({'kind': 'policy_link_effect', 'link': effect})
            return {"link": _sync_link_directory(path, effect)}
        with self.bus_factory() as bus:
            if kind == "service_daemon_reload":
                self.check_reload_scope(action["after"])
                emit({"kind": "bus_binding", "sender": bus.unique_name(), "unit": "manager"})
                emit({"kind": "reload_dispatching", "expected_tree": digest(action["after"])})
                bus.call("Reload")
                emit({"kind": "reload_returned"})
                return {"reload": "returned"}
            snapshot = self._snapshot(bus, action["target"], starting=kind == "service_start")
            if snapshot["job"][0]:
                raise AdapterError("SERVICE_JOB_PENDING")
            if kind == "service_stop":
                # Requires/Requisite reverse edges can make StopUnit stop a
                # second service. Its own planned stop must already be closed;
                # discovering an external or still-running dependent is not
                # permission to stop it implicitly.
                for dependent in self._stop_dependents(action["target"], snapshot):
                    current = bus.unit(dependent)
                    if (current.get("ActiveState") not in STOPPED or current.get("MainPID", 0)
                            or current.get("ControlPID", 0) or current.get("Job", [0])[0]):
                        raise AdapterError("SERVICE_STOP_DEPENDENT_NOT_CLOSED")
            mode = self.units[action["target"]].get("start_job_mode", "fail") if kind == "service_start" else "fail"
            # The explicit read-only mode keeps ordering and BindsTo stop
            # semantics, but cannot pull in a dependency that went down after
            # the readiness observation. The node lock serializes managed jobs;
            # independent writers must use the same maintenance protocol.
            return bus.run_job(action["target"], "StartUnit" if kind == "service_start" else "StopUnit", emit, mode=mode)
