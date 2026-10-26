"""Concrete local adapters and protected observations for deployment.

The runtime never saves coordinator records. Every effective operation follows
the caller's durable intent; returned JSON is the caller's recovery evidence.
"""
from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import struct
import time
from types import SimpleNamespace

from local_hand_jobs import cli, maintenance, startup

from . import files
from .gateway import GatewayAdapter
from .model import DeployError, PLAN_SCHEMA, canonical, decode, digest, operation_id, seal_plan
from .planner import action_order, validate_profile, validate_schedule
from .services import SystemdAdapter, tree_snapshot
from .supervision import SupervisedRunner


def _clone(value):
    return decode(canonical(value))


class PlanningEnvironment:
    """Constructing this observer never creates a directory or child process."""
    def __init__(self, profile):
        self.profile = profile
        self.owner = profile.get("owner_uid", 0)
        self.runner = SimpleNamespace(timeout=profile.get("timeout_seconds", 30))
        self._services = self._gateway = None

    def preparation_inventory(self, candidates=None):
        from .preparations import inventory
        return inventory(self.profile, candidates=candidates)

    def _probe(self, component, *, reconcile=False, retention=None):
        spec = self.profile["probes"][component]
        if spec["kind"] == "gateway":
            return self._gateway_probe(component)
        path = Path(spec["socket"])
        # The MCP maintenance listener lives in the original private broker
        # directory. Its pinned SO_PEERCRED identity owns that directory;
        # root manager controls keep the administrator-only ancestry rule.
        parent_owners = {0, self.owner}
        if spec["kind"] == "mcp":
            parent_owners.add(spec.get("peer_uid", 0))
        for parent in path.parents:
            info = parent.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in parent_owners
                    or info.st_mode & 0o022 and not (info.st_uid == 0 and info.st_mode & stat.S_ISVTX)):
                raise DeployError("UNTRUSTED_PROBE", "Status socket ancestor is not protected")
        info = path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != spec.get("peer_uid", 0):
            raise DeployError("UNTRUSTED_PROBE", "Status socket is not its fixed local peer")
        end = time.monotonic() + min(self.profile.get("timeout_seconds", 30), 10)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(max(0.01, end - time.monotonic()))
            connection.connect(str(path))
            pid, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != spec.get("peer_uid", 0):
                raise DeployError("UNTRUSTED_PROBE", "Status peer identity changed")
            request = retention if retention is not None else {"action": "deployment_status" if reconcile else "deployment_observe"}
            if os.geteuid() != 0 and spec["kind"] == "resident":
                request["principal_id"] = spec["principal_id"]
            cli._send_frame(connection, request, deadline=end, limit=4096)
            response = decode(cli._read_frame(connection, cli.MAX_RESPONSE_BYTES if retention is not None else 65536, deadline=end))
        if not isinstance(response, dict) or "error" in response or not isinstance(response.get("result"), dict):
            if retention is not None and isinstance(response, dict) and isinstance(response.get("error"), dict):
                from local_hand_jobs.contract import JobError
                error = response["error"]
                raise JobError(error.get("code", "IO_UNCERTAIN"), "Original retained read route refused verification")
            raise DeployError("PROBE_FAILED", "Protected status did not return a valid observation")
        result = response["result"]
        readback = None
        if retention is not None:
            if spec["kind"] != "mcp" or set(result) != {"proof", "readback"}:
                raise DeployError("RETENTION_PROTOCOL", "Retained readback lacks its actual guarded runtime proof")
            readback, result = result["readback"], result["proof"]
        direct = spec["kind"] == "mcp" and result.get("component") == component
        loaded = result if direct else result.get("loaded")
        if ((not direct and result.get("maintenance_supported") is not True) or not isinstance(loaded, dict)
                or loaded.get("pid") != pid or loaded.get("protocol_ready") is not True
                or loaded.get("boot_id") != startup.boot_id()):
            raise DeployError("UNGUARDED_ENTRY", "Actual listener did not prove its loaded guarded configuration")
        # Bind the successful socket response to this live process instance.
        raw = Path(f"/proc/{pid}/stat").read_text()
        if str(loaded.get("start_ticks")) != raw[raw.rindex(")") + 2:].split()[19]:
            raise DeployError("PROBE_INSTANCE_CHANGED", "Status process instance changed")
        value = {"maintenance_supported": True, "loaded": loaded} if direct else result
        if retention is not None:
            value["readback"] = readback
        return value

    def retained_results(self, selected, candidates=None):
        from local_hand_jobs.retained_probe import collect, merge_readbacks
        result = {}
        candidates = candidates or {}
        deadline = time.monotonic() + self.profile.get("timeout_seconds", 30)
        covered_managers = set()
        for component, probe in self.profile["probes"].items():
            if probe["kind"] == "mcp":
                path = self.profile["guarded_components"][component]["configuration"]
                config = decode(startup.protected_read(candidates.get(path, path), owner_uid=self.owner))
                covered_managers.update(name for name, peer in self.profile["probes"].items()
                    if peer["kind"] in {"resident", "prepared"} and peer["socket"] == config.get("manager_socket"))
        for component, probe in self.profile["probes"].items():
            if probe["kind"] != "mcp":
                if (component not in covered_managers and {"prepare", "execute"}.intersection(
                        self.profile["guarded_components"][component]["entrypoints"])):
                    from .retained_reader import offline_readback
                    result[component] = offline_readback(self, component, selected, deadline=deadline, candidates=candidates)
                continue
            if not selected["selection"]["components"][component]["running"]:
                from .retained_reader import offline_readback
                result[component] = offline_readback(self, component, selected, deadline=deadline, candidates=candidates)
                continue
            def call(request):
                observed = self._probe(component, retention=request)
                self._match_loaded(observed["loaded"], selected["selection"], component)
                return observed["readback"]
            result[component] = collect(call, deadline=deadline)
        return merge_readbacks(result.values())

    def _gateway_instance(self, container_id=None):
        adapter = self.gateway
        if adapter.engine.request("GET", "/info").get("ID") != adapter.profile["daemon_id"]:
            raise DeployError("GATEWAY_INSTANCE_CHANGED", "Gateway daemon identity differs")
        value = adapter.engine.request("GET", "/containers/" + (container_id or adapter.name) + "/json")
        selected_id, state = value.get("Id"), value.get("State", {})
        labels = value.get("Config", {}).get("Labels", {}) or {}
        if (not isinstance(selected_id, str) or not re.fullmatch(r"[0-9a-f]{64}", selected_id)
                or container_id is not None and selected_id != container_id
                or labels.get("com.docker.compose.project") != adapter.project
                or labels.get("com.docker.compose.service") != adapter.service
                or state.get("Running") is not True or any(state.get(key) for key in ("Paused", "Restarting", "Dead"))
                or type(state.get("Pid")) is not int or state["Pid"] <= 1):
            raise DeployError("GATEWAY_INSTANCE_CHANGED", "Gateway does not have its fixed running container instance")
        pid = state["Pid"]
        instance = startup.instance(pid)
        namespace = next((line.split()[1:] for line in Path(f"/proc/{pid}/status").read_text().splitlines()
                          if line.startswith("NSpid:")), [])
        if (len(namespace) < 2 or namespace[0] != str(pid) or namespace[-1] != "1"
                or any(os.stat(f"/proc/{pid}/ns/{kind}").st_ino == os.stat(f"/proc/self/ns/{kind}").st_ino
                       for kind in ("pid", "mnt"))):
            raise DeployError("GATEWAY_INSTANCE_CHANGED", "Gateway must be PID 1 in its own container namespaces")
        return {"container_id": selected_id, "instance": instance}

    def _gateway_probe(self, component, *, checks=None):
        # Resolve through the actual Engine-selected PID 1, never a caller's
        # container_id or a writable host mount containing a claimed proof.
        spec = self.profile["probes"][component]
        selected = self._gateway_instance()
        expected = selected["instance"]
        path = Path(f"/proc/{expected['pid']}/root") / spec["socket"].lstrip("/")
        end = time.monotonic() + min(self.profile.get("timeout_seconds", 30), 10)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(max(0.01, end - time.monotonic()))
            connection.connect(str(path))
            pid, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if pid != expected["pid"] or uid != 0:
                raise DeployError("UNTRUSTED_PROBE", "Gateway status listener is not the actual root container supervisor")
            request = ({"action": "deployment_observe"} if checks is None else
                       {"action": "deployment_check_routes", "specification": checks})
            cli._send_frame(connection, request, deadline=end, limit=32768)
            response = decode(cli._read_frame(connection, 65536, deadline=end))
        loaded = response.get("result") if isinstance(response, dict) and "error" not in response else None
        if (not isinstance(loaded, dict) or loaded.get("component") != component
                or loaded.get("protocol_ready") is not True or loaded.get("namespace_pid") != 1
                or type(loaded.get("public_ready")) is not bool
                or any(loaded.get(key) != expected[key] for key in ("pid", "start_ticks", "boot_id"))
                or selected != self._gateway_instance(selected["container_id"])):
            raise DeployError("GATEWAY_INSTANCE_CHANGED", "Gateway proof does not match the unchanged actual supervisor")
        return {"maintenance_supported": True, "loaded": {**loaded, "container_id": selected["container_id"]}}

    def _loaded(self, unit):
        component = self.profile["systemd"]["units"][unit]["component"]
        value = self._probe(component)["loaded"]
        return {**value, "config_digest": value["configuration_digest"]}

    @property
    def services(self):
        if self._services is None:
            profile = self.profile.get("systemd")
            if not profile:
                raise DeployError("UNSUPPORTED_PROFILE", "No fixed service profile")
            self._services = SystemdAdapter(profile, self.runner, loaded_probe=self._loaded,
                                             guard_check=getattr(self, "_guard", None))
        return self._services

    @property
    def gateway(self):
        if self._gateway is None:
            profile = self.profile.get("gateway")
            if not profile:
                raise DeployError("UNSUPPORTED_PROFILE", "No fixed gateway profile")
            self._gateway = GatewayAdapter(profile, self.runner,
                guard_check=getattr(self, "_guard", None), route_probe=self._route)
        return self._gateway

    def _route(self, container_id):
        component = self.profile["gateway"]["component"]
        value = self._probe(component)["loaded"]
        if value.get("container_id") != container_id:
            raise DeployError("GATEWAY_INSTANCE_CHANGED", "Gateway status is not bound to the selected container")
        return {**value, "config_digest": value["configuration_digest"]}

    def _verify_components(self, selection, candidates=None, *, gateway_compose=None):
        candidates = candidates or {}
        members = {item["path"]: item["sha256"] for item in selection["members"]}
        owners = {item["path"]: item.get("owner_uid", self.owner) for item in selection["members"]}
        # Read control configurations only with the administrator identity.
        # A member cannot delegate ownership of its own startup authority.
        configurations = {}
        control_paths = set()
        for component, guard in self.profile["guarded_components"].items():
            path = guard["configuration"]
            if path not in members or owners[path] != self.owner:
                raise DeployError("UNGUARDED_ENTRY", "Startup controls require the deployment owner")
            raw = startup.protected_read(candidates.get(path, path), owner_uid=self.owner)
            if hashlib.sha256(raw).hexdigest() != members[path]:
                raise DeployError("CONFIGURATION_CHANGED", "Startup control differs from selection")
            configurations[component] = decode(raw)
            control_paths.add(path)
        policy_owners = {}
        for config in configurations.values():
            if config.get("schema") == "local-hand-gateway-startup/v1":
                control_paths.add(config.get("nginx_config"))
            if config.get("schema") != "local-hand-mcp-startup/v1":
                continue
            inputs = config.get("inputs")
            if (not isinstance(inputs, dict) or not {"config", "auth_config"} <= set(inputs)
                    or config.get("mode") not in {"resident", "prepared_task", "read_only"}
                    or set(inputs) != ({"config", "auth_config"} if config.get("mode") == "read_only"
                                       else {"config", "auth_config", config.get("mode")})
                    or any(not isinstance(path, str) for path in inputs.values())):
                raise DeployError("UNGUARDED_ENTRY", "MCP startup configuration is incomplete")
            control_paths.update(path for name, path in inputs.items() if name != "config")
            managers = [name for name, probe in self.profile["probes"].items()
                        if probe["kind"] in {"resident", "prepared"}
                        and probe["socket"] == config.get("manager_socket")]
            if len(managers) != 1 or managers[0] not in configurations:
                raise DeployError("UNGUARDED_ENTRY", "MCP policy needs one selected manager identity")
            uid = configurations[managers[0]].get("uid", self.owner)
            if type(uid) is not int or not 0 <= uid < 2**32 - 1:
                raise DeployError("UNGUARDED_ENTRY", "Invalid task policy owner")
            path = inputs["config"]
            if path in policy_owners and policy_owners[path] != uid:
                raise DeployError("UNGUARDED_ENTRY", "Policy has conflicting manager identities")
            policy_owners[path] = uid
        for member in selection["members"]:
            path, uid = member["path"], owners[member["path"]]
            if (path in policy_owners and "owner_uid" in member
                    and (path in control_paths or policy_owners[path] != uid)
                    or uid != self.owner and (path in control_paths or policy_owners.get(path) != uid)):
                raise DeployError("UNGUARDED_ENTRY", "Only the selected task policy may bind its data owner")
        total = 0
        for member in selection["members"]:
            path, expected = member["path"], member["sha256"]
            actual_path = candidates.get(path, path)
            raw = startup.protected_read(actual_path, owner_uid=owners[path],
                                         required_uid=member.get("owner_uid"), maximum=4 * 1024 * 1024)
            total += len(raw)
            if total > 64 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected:
                raise DeployError("CONFIGURATION_CHANGED", "Complete configuration member differs from selection")
        for component, guard in self.profile["guarded_components"].items():
            path = guard["configuration"]
            if path not in members:
                raise DeployError("UNGUARDED_ENTRY", "Guard configuration is outside the complete selection")
            config = decode(startup.protected_read(candidates.get(path, path), owner_uid=self.owner))
            expected = selection["components"][component]
            if config.get("schema") == "local-hand-gateway-startup/v1":
                from local_hand_mcp.gateway_guard import validate_config, configuration_binding
                validate_config(config)
                nginx_path = config["nginx_config"]
                if nginx_path not in members:
                    raise DeployError("UNGUARDED_ENTRY", "Gateway configuration is outside the complete selection")
                binding = configuration_binding(config, read=lambda name: startup.protected_read(
                    candidates.get(name, name), owner_uid=self.owner))
                manager_sockets = {probe["socket"] for probe in self.profile["probes"].values()
                                   if probe["kind"] in {"resident", "prepared"}}
                if (component != "gateway" or self.profile["probes"][component]["kind"] != "gateway"
                        or config["status_socket"] != self.profile["probes"][component]["socket"]
                        or config["node_id"] != selection["node_id"]
                        or config["deployment_digest"] != selection["deployment_digest"]
                        or config["payload_digest"] != expected["payload_digest"]
                        or startup.digest(binding) != expected["configuration_digest"]
                        or config["manager_socket"] not in manager_sockets):
                    raise DeployError("UNGUARDED_ENTRY", "Gateway actual inputs do not match its guarded startup selection")
                self._manager_dependency(config["manager_socket"], selection, expected)
                self._gateway_input_mounts(config, path, compose=gateway_compose)
                continue
            if config.get("schema") == "local-hand-mcp-startup/v1":
                inputs = config["inputs"]
                from local_hand_mcp.startup_guard import listener_binding, retention_binding
                listener = listener_binding(config)
                bindings = {}
                for name, input_path in inputs.items():
                    if input_path not in members:
                        raise DeployError("UNGUARDED_ENTRY", "MCP input is outside the complete selection")
                    raw = startup.protected_read(candidates.get(input_path, input_path), owner_uid=owners[input_path])
                    bindings[name] = {"path": input_path, "sha256": hashlib.sha256(raw).hexdigest()}
                config_digest = startup.digest({"inputs": bindings, "mode": config["mode"], **listener, **retention_binding(config)})
                manager_sockets = {probe["socket"] for probe in self.profile["probes"].values()
                                   if probe["kind"] in {"resident", "prepared"}}
                if (config.get("node_id") != selection["node_id"] or config.get("deployment_digest") != selection["deployment_digest"]
                        or config.get("payload_digest") != expected["payload_digest"]
                        or config_digest != expected["configuration_digest"] or config.get("manager_socket") not in manager_sockets):
                    raise DeployError("UNGUARDED_ENTRY", "MCP actual inputs do not match its guarded startup selection")
                self._manager_dependency(config["manager_socket"], selection, expected)
                continue
            bound = config.get("maintenance", {})
            if (bound.get("schema") != maintenance.CONFIG_SCHEMA or bound.get("node_id") != selection["node_id"]
                    or bound.get("deployment_digest") != selection["deployment_digest"]
                    or bound.get("directory") != self.profile["maintenance_directory"]
                    or bound.get("startup_descriptor") != self.profile["startup_descriptor"]
                    or maintenance.digest({k: v for k, v in config.items() if k != "maintenance"}) != expected["configuration_digest"]
                    or config.get("installation", {}).get("installed", {}).get("payload_digest") != expected["payload_digest"]):
                raise DeployError("UNGUARDED_ENTRY", "Actual configuration does not bind all selected maintenance/startup guards")

    def _manager_dependency(self, socket_path, selection, expected):
        managers = [name for name, probe in self.profile["probes"].items()
                    if probe["kind"] in {"resident", "prepared"} and probe["socket"] == socket_path]
        if len(managers) != 1 or (expected.get("running") and
                selection["components"].get(managers[0], {}).get("running") is not True):
            raise DeployError("UNGUARDED_ENTRY", "A running network listener needs its selected running startup manager")

    def _gateway_input_mounts(self, config, guard_path, *, compose=None):
        profile = self.profile["gateway"]
        # Preserve the same absolute names across namespaces so the privileged
        # manager and image validate the same selected bytes, not two aliases.
        for compose in (compose if compose is not None else profile["compose"],):
            service = compose["services"][profile["service"]]
            from .gateway import _resource_config
            resources = _resource_config(service)
            needed = {"CHOWN", "SETUID", "SETGID"}
            dropped = {str(cap).upper() for cap in service.get("cap_drop", [])}
            added = set(resources.get("CapAdd", []))
            missing = (needed if "ALL" in dropped else needed & dropped) - added
            if (service.get("entrypoint") != ["/opt/local-hand/gateway/bin/python", "-B", "-m", "local_hand_mcp.gateway_guard"]
                    or service.get("command") != ["--config", guard_path] or service.get("user") != "0:0"
                    or type(service.get("read_only", False)) is not bool
                    or service.get("read_only", False) and "/run/local-hand-gateway" not in resources.get("Tmpfs", {})
                    or missing
                    or any(name.startswith("PYTHON") and name not in {"PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED"}
                           for name in service.get("environment", {}))):
                continue
            if not any(int(port["target"]) == config["public_port"] for port in service.get("ports", [])):
                continue
            mounts = service.get("volumes", [])
            def covered(name):
                covering = [mount for mount in mounts
                            if name == mount["target"] or Path(mount["target"]) in Path(name).parents]
                if not covering:
                    return False
                deepest = max(len(Path(mount["target"]).parts) for mount in covering)
                selected = [mount for mount in covering if len(Path(mount["target"]).parts) == deepest]
                # A nested bind wins over a parent bind in the container. Do
                # not validate the parent while ignoring a substituted input.
                return (len(selected) == 1 and selected[0].get("read_only") is True
                        and selected[0]["source"] == selected[0]["target"]
                        and selected[0]["target"] != name)
            if all(covered(name) for name in (guard_path, config["nginx_config"], config["manager_socket"])):
                return
        raise DeployError("UNGUARDED_ENTRY", "Gateway inputs and manager endpoint need identical protected read-only bindings")

    def validate_baseline(self, node_id, source, target, file_plan):
        if self.profile.get("recovery_from"):
            raise DeployError("RECOVERY_REQUIRED", "Corrective plans require the existing deployment record")
        current = startup.read_selection(self.profile["startup_descriptor"], owner_uid=self.owner)
        if current != source["selection"] or current["node_id"] != node_id:
            raise DeployError("BASELINE_CHANGED", "Stable startup selection changed before planning")
        gateway = self.profile.get("gateway", {})
        self._verify_components(source["selection"], gateway_compose=gateway.get("original_compose", gateway.get("compose")))
        self.validate_target(target, file_plan)
        for component, desired in source["selection"]["components"].items():
            if desired["running"]:
                self._match_loaded(self._probe(component)["loaded"], source["selection"], component)

    def validate_target(self, target, file_plan):
        candidates = {entry["target"]: entry["source"]["path"] for entry in file_plan["files"] if entry["source"] is not None}
        target_members = {member["path"] for member in target["selection"]["members"]}
        if any(entry["source"] is None and entry["target"] in target_members for entry in file_plan["files"]):
            raise DeployError("INVALID_PLAN", "A removed target cannot remain in the complete startup selection")
        self._verify_components(target["selection"], candidates)

    @staticmethod
    def _match_loaded(loaded, selection, component):
        desired = selection["components"][component]
        if (loaded.get("node_id") != selection["node_id"]
                or loaded.get("deployment_digest") != selection["deployment_digest"]
                or any(loaded.get(key) != desired[key] for key in ("configuration_digest", "payload_digest"))):
            raise DeployError("LOADED_CONFIGURATION_MISMATCH", "Process did not load the selected deployment")

    def plan_services(self, source, target, file_plan):
        if set(source["services"]) != set(self.profile["systemd"]["units"]):
            raise DeployError("UNSUPPORTED_PROFILE", "All fixed services require explicit original and target states")
        baseline = self.services.observe()
        for unit, expected in source["services"].items():
            actual = baseline["units"][unit]
            if (actual["active"] not in {"active", "inactive", "failed"}
                    or (actual["active"] == "active") != expected["running"] or actual["policy"] != expected["policy"]
                    or expected.get("definition_digest", actual["definition_digest"]) != actual["definition_digest"]):
                raise DeployError("BASELINE_CHANGED", "Actual service state differs from the declared source")
        recovery = self.profile.get("recovery_from")
        before = (recovery["reload_tree"] if recovery else self.profile["systemd"]["reload_scope"]["loaded_snapshot"])
        self.services.check_reload_scope(before)
        actions = self.services.plan(target["services"], baseline, _check_global=not recovery)
        after = copy.deepcopy(before)
        roots = [Path(path) for path in self.profile["systemd"]["reload_scope"]["roots"]]
        def overlay(path, value):
            parsed = Path(path)
            included = parsed in roots or any(root in parsed.parents and before.get(str(root), {}).get("kind") == "directory" for root in roots)
            if not included:
                return False
            if value["kind"] == "absent" and parsed not in roots:
                after.pop(path, None)
            else:
                after[path] = value
            return True
        for entry in file_plan["files"]:
            overlay(entry["target"], {"kind": "absent"} if entry["source"] is None else
                    {"kind": "file", "digest": entry["source"]["snapshot"]["sha256"], **entry["attributes"]})
        for action in actions:
            if action["kind"] == "service_policy_link":
                parent = Path(action["path"]).parent.stat()
                value = {**action["after"], **({"mode": 0o777, "uid": self.owner,
                    "gid": parent.st_gid if parent.st_mode & stat.S_ISGID else os.getegid()}
                    if action["after"]["kind"] == "link" else {})}
                if not overlay(action["path"], value):
                    raise DeployError("RELOAD_SCOPE_CHANGED", "Enable link is outside the fixed manager tree")
        if recovery:
            # Observed disk is not claimed to be the manager's loaded tree.
            # A corrective deployment must explicitly fence and complete reload.
            actions.append({"kind": "service_daemon_reload", "target": "manager", "before": before,
                "after": after, "subeffects": ["manager_reload"], "phase": "after_files"})
        elif before != after:
            actions.append(self.services.plan_reload(after))
        return actions

    def plan_gateway(self, source, target):
        before = self.gateway.observe(require_route=False)
        expected = source["gateway"]
        if ((before["kind"] == "container") != expected.get("present", True)
                or (before.get("status") == "running") != expected["running"]):
            raise DeployError("BASELINE_CHANGED", "Actual gateway state differs from the declared source")
        if before["kind"] == "container":
            before.update(config_digest=expected["config_digest"], deployment_digest=expected["deployment_digest"])
        return self.gateway.plan(target["gateway"], before)


class ConcreteEnvironment(PlanningEnvironment):
    def __init__(self, plan, store, gate):
        super().__init__(plan["profile"])
        self.plan, self.store, self.gate = plan, store, gate
        self._runner = None

    def for_operation(self, op):
        return ConcreteEnvironment(op["plan"], self.store, self.gate)

    def _mutating_adapters(self, *, readonly=False):
        if self._runner is None:
            self._runner = SupervisedRunner(self.store.root / "supervision",
                timeout=self.profile.get("timeout_seconds", 30), output_limit=self.profile.get("output_limit", 65536),
                create=not readonly)
            self.runner = self._runner
            if self._services is not None:
                self._services.runner = self.runner
            if self._gateway is not None:
                self._gateway.runner = self.runner
        elif not readonly:
            # The runner creates only its private fixed journal directory here.
            self._runner.ensure_directory()

    def _directory(self, op, step_id, suffix):
        path = self.store.root
        for part in ("operations", op["id"], step_id, suffix):
            path = path / part
            try:
                path.mkdir(mode=0o700)
            except FileExistsError:
                pass
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != self.owner or stat.S_IMODE(info.st_mode) != 0o700:
                raise DeployError("UNPROTECTED_STATE", "File preparation directory is not private")
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        return path

    def preflight(self, op):
        plan = op["plan"]
        validate_schedule(plan)
        validate_profile(plan["profile"], plan["source"], plan["target"])
        file_plan = {"files": [step["action"] for step in plan["steps"] if step["kind"] == "file"]}
        if plan["profile"].get("recovery_from"):
            from .recovery import validate_link, RecoveryPlanningEnvironment
            if not op["predecessor"] or not op["gate_owned"]:
                raise DeployError("RECOVERY_REQUIRED", "Corrective deployment has not received its linked maintenance responsibility")
            validate_link(plan, self.store, self.gate, self.store.get(op["predecessor"]), successor=op["id"])
            RecoveryPlanningEnvironment.validate_baseline(self, plan["node_id"], plan["source"], plan["target"], file_plan)
        else:
            self.validate_baseline(plan["node_id"], plan["source"], plan["target"], file_plan)
        state = self.gate.snapshot()
        if state["node_id"] != plan["node_id"] or state["deployment_digest"] != plan["source"]["deployment_digest"]:
            raise DeployError("BASELINE_CHANGED", "Maintenance marker does not select the planned source")
        return {"passed": True, "selection_digest": startup.digest(plan["source"]["selection"]), "gate_sequence": state["sequence"]}

    def quiesced_retention(self, op):
        """Save original bindings before the first effect, including handoff."""
        from .preparations import decisions
        baseline = next((origin["checks"]["retained"] for origin in self._origins(op)
                         if "retained" in origin["checks"]), None)
        current = self.preparation_inventory()
        if baseline is not None and current["tasks"] != baseline["preparations"]["tasks"]:
            raise DeployError("RETENTION_CONFLICT", "Retained preparation changed during deployment")
        snapshot = current if baseline is None else baseline["preparations"]
        candidates = {step["action"]["target"]: step["action"]["source"]["path"]
                      for step in op["plan"]["steps"] if step["kind"] == "file" and step["action"]["source"] is not None}
        target = self.preparation_inventory(candidates)
        if target["tasks"] != current["tasks"]:
            raise DeployError("RETENTION_CONFLICT", "Target task admission would hide or replace original preparations")
        closure = self.retained_closure(snapshot)
        choices = decisions(snapshot, op["plan"]["target"]["selection"]["components"],
                            now=time.time(), boot_id=startup.boot_id(), closed=closure)
        results = self.retained_results(op["plan"]["source"]) if baseline is None else baseline["results"]
        return {"preparations": snapshot, "compatibility": choices, "results": results, "closure": closure,
                "target_deployment_digest": op["plan"]["target"]["deployment_digest"]}

    def retention_decisions(self, op, selected):
        """Compute current decisions; the coordinator must save before publish."""
        from .preparations import decisions
        baseline = op["checks"].get("retained")
        if baseline is None:
            return []
        current = self.preparation_inventory()
        if current["tasks"] != baseline["preparations"]["tasks"]:
            raise DeployError("RETENTION_CONFLICT", "Original preparations changed before admission release")
        return decisions(baseline["preparations"], selected["selection"]["components"],
                         now=time.time(), boot_id=startup.boot_id(), closed=self.retained_closure(current))

    def retained_closure(self, snapshot):
        from .preparations import observe_reboot_closure
        marker = self.gate.snapshot()
        result, observed = {}, {}
        for item in snapshot["tasks"]:
            if item["state"] != "PREPARING" and item.get("execution") != "UNRESOLVED":
                continue
            matching = [duty for duty in marker["responsibilities"].values()
                if duty["operation_id"] == item["operation_id"] and duty["loaded"]["component"] == item["component"]
                and (duty["kind"] == "prepare" and duty["id"] == item.get("admission_id")
                     or duty["kind"] == "execute" and duty["binding"].get("prepared") == item.get("prepared"))]
            if matching and all(duty["state"] == "CLOSED" for duty in matching):
                result[digest(item)] = {"closed_responsibilities": [duty["id"] for duty in matching]}
            else:
                key = (item["component"], item.get("dispatch_boot_id"))
                if key not in observed:
                    observed[key] = observe_reboot_closure(self.profile, key[0],
                        expected_boot=key[1], current_boot=startup.boot_id())
                result[digest(item)] = observed[key]
        return result

    def activate_retention(self, op, selected):
        """Publish only saved exact decisions under the still-closed gate."""
        choices = op["checks"].get("released_compatibility", [])
        durable = self.store.get(op["id"])
        if durable["checks"].get("released_compatibility") != choices:
            raise DeployError("DECISION_NOT_DURABLE", "Prepared compatibility decisions were not saved")
        for item in choices:
            if not item["compatible"]:
                continue
            component = item["component"]
            bound = selected["selection"]["components"][component]
            loaded = {"node_id": op["plan"]["node_id"], "component": component,
                      "deployment_digest": selected["deployment_digest"], "boot_id": startup.boot_id(),
                      **{key: bound[key] for key in ("configuration_digest", "payload_digest")}}
            self.gate.authorize_compatibility(op["id"], item["prepared"], selected["deployment_digest"], target_loaded=loaded)

    def validate_successor(self, op, plan):
        if op["gate_owned"] and not op["released"]:
            from .recovery import validate_link
            validate_link(plan, self.store, self.gate, op)
        elif plan["profile"].get("recovery_from"):
            raise DeployError("RECOVERY_CONFLICT", "This predecessor has no closed responsibility to transfer")

    def prepare(self, step, op, record):
        if step["kind"] == "file":
            return files.prepare_file(step["action"], self._directory(op, step["id"], "publish"),
                operation_id=op["id"], attempt_id="prepare-" + step["id"], lock_fd=self.store.lock_fd)
        adapter = self.services if step["kind"] == "service" else self.gateway
        adapter._validate_action(step["action"])
        if step["action"].get("kind") == "service_daemon_reload":
            prepared_files = [entry["prepared"] for entry in op["steps"]
                              if entry["prepared"] and entry["prepared"].get("schema") == "lh-deploy-file-action-v1"]
            _, retained, objects = self._retention(prepared_files)
            action = _clone(step["action"])
            for side in ("before", "after"):
                action[side].update(retained)
            action["retained_files"] = objects
            return action
        action = _clone(step["action"])
        if action.get('kind') == 'gateway_start':
            reference = self._creation_reference(step, op)
            if reference is not None:
                action['creation_ref'] = reference
        return action

    @staticmethod
    def _creation_reference(step, op, *, restore=False):
        steps = [item['step'] for item in op.get('compensation', [])] if restore else op['plan']['steps']
        creator = None
        for item in steps:
            if item['id'] == step['id']:
                break
            if (item['kind'] == 'gateway' and item['action'].get('kind') == 'gateway_create'
                    and item['action']['target'] == step['action']['target']):
                creator = item['id']
        return ({'operation_id': op['id'], 'step_id': creator, 'restore': restore} if creator else None)

    def _start_identity(self, step, prepared, op=None):
        if prepared.get('kind') != 'gateway_start':
            return None
        reference = prepared.get('creation_ref')
        if reference is None:
            # Older prepared actions did not retain the producer reference.
            # Recover it from the fixed recorded order, never today's inspect.
            op = op or self.store.get(operation_id(self.plan['request_id']))
            restore = any(entry['step']['id'] == step['id'] for entry in op.get('compensation', []))
            reference = self._creation_reference(step, op, restore=restore)
        if reference is None:
            return None
        origin = op if op is not None and op['id'] == reference['operation_id'] else self.store.get(reference['operation_id'])
        if reference['restore']:
            pairs = [(item['step'], item['record']) for item in origin.get('compensation', [])]
            action_key, attempts_key, observation_key = 'restore', 'restore_attempts', 'restore_observation'
        else:
            pairs = list(zip(origin['plan']['steps'], origin['steps']))
            action_key, attempts_key, observation_key = 'prepared', 'attempts', 'observation'
        producer = next((record for source, record in pairs if source['id'] == reference['step_id']), None)
        action = producer.get(action_key) if producer else None
        if (not action or action.get('kind') != 'gateway_create' or action['target'] != prepared['target']
                or action.get('compose') != prepared.get('compose') or action['after'] != prepared['after']):
            raise DeployError('GATEWAY_START_IDENTITY_REQUIRED', 'Start has no matching recorded creation')
        attempts = producer[attempts_key]
        return self.gateway.creation_identity(action, self._previous(attempts[-1]) if attempts else None,
            observation=producer.get(observation_key), lock_fd=self.store.lock_fd)

    def effect_identity(self, step, prepared, attempt, observation):
        if step['kind'] == 'gateway' and prepared.get('kind') == 'gateway_create':
            return self.gateway.creation_identity(prepared, self._previous(attempt),
                observation=observation, lock_fd=self.store.lock_fd)
        return None

    def _retention(self, prepared_files):
        """Declare exact inert staging objects in the shared reload tree.

        Nothing is filtered from that tree. Failed preparation objects remain
        visible, handle-bound and byte-for-byte checked, while the current
        candidate's path disappears when its separately recorded rename runs.
        """
        if not self.profile.get("systemd"):
            return {}, {}, []
        roots = [Path(path) for path in self.profile["systemd"]["reload_scope"]["roots"]]
        consumed = {item["staged"]["path"] for item in prepared_files if item.get("staged")}
        objects = {}
        for action in prepared_files:
            for item in files.preparation_objects(action):
                path = Path(item["path"])
                if path in roots or any(root in path.parents for root in roots):
                    previous = objects.get(item["path"])
                    if previous and previous != item:
                        raise DeployError("RESTORE_CONFLICT", "Retained staging identity changed")
                    objects[item["path"]] = item
        current = {path: {"kind": "file", "digest": item["snapshot"]["sha256"],
                          **{key: item["snapshot"][key] for key in ("mode", "uid", "gid")}}
                   for path, item in objects.items()}
        retained = {path: value for path, value in current.items() if path not in consumed}
        return current, retained, [objects[path] for path in sorted(retained)]

    def _verify_retention(self, prepared):
        if prepared.get("retained_files"):
            files.verify_preparation_objects(prepared["retained_files"], owner_uid=self.owner,
                limits=files.FileLimits(**self.profile.get("file_limits", {})))

    @staticmethod
    def effect_key(step):
        action = step["action"]
        if step["kind"] == "file":
            return "file:" + action["target"]
        if step["kind"] == "gateway":
            return "gateway:" + action["target"]
        if action["kind"] == "service_policy_link":
            return "policy:" + action["path"]
        return "reload:manager" if action["kind"] == "service_daemon_reload" else "service:" + action["target"]

    @staticmethod
    def _previous(attempt):
        if not attempt or not attempt.get('binding'):
            return None
        return attempt if ('effect_identity' in attempt or 'effect_identity_required' in attempt) else attempt['binding']

    @staticmethod
    def _observation(value, prepared, *, is_file=False):
        result = {**value, "state": value.get("state", value.get("outcome")), "closed": value.get("closed", is_file)}
        if is_file:
            result["effective"] = result["state"] == "target" and prepared["action"] != "noop"
        else:
            result["effective"] = (value.get('effective') is True or
                result["state"] in {"target", "partial"} and prepared.get("before") != value.get("observation"))
        return result

    def observe(self, step, prepared, attempt=None):
        if step["kind"] == "file":
            return self._observation(files.observe_file(prepared), prepared, is_file=True)
        self._mutating_adapters(readonly=True)
        self._verify_retention(prepared)
        adapter = self.services if step["kind"] == "service" else self.gateway
        kwargs = {'expected_identity': self._start_identity(step, prepared)} if step['kind'] == 'gateway' else {}
        return self._observation(adapter.observe_action(prepared, self._previous(attempt), lock_fd=self.store.lock_fd, **kwargs), prepared)

    def execute(self, step, prepared, op, attempt_id, persist_intent, previous=None):
        if step["kind"] == "file":
            return self._observation(files.execute_file(prepared, lock_fd=self.store.lock_fd), prepared, is_file=True)
        self._mutating_adapters()
        self._verify_retention(prepared)
        adapter = self.services if step["kind"] == "service" else self.gateway
        kwargs = {'expected_identity': self._start_identity(step, prepared, op)} if step['kind'] == 'gateway' else {}
        return self._observation(adapter.execute(prepared, attempt_id=attempt_id, lock_fd=self.store.lock_fd,
            persist_intent=persist_intent, previous=self._previous(previous), **kwargs), prepared)

    def _origins(self, op):
        return [self.store.get(value) for value in op.get("inherited", [])] + [op]

    def _source(self, op):
        return self._origins(op)[0]["plan"]["source"]

    def prepare_restore(self, step, op, record):
        if step["kind"] != "file":
            raise DeployError("COMPENSATION_ORDER", "Service and gateway restoration require the aggregate compensation plan")
        return files.prepare_restore(record["prepared"], self._directory(op, step["id"], "restore"),
            operation_id=op["id"], attempt_id="restore-" + step["id"], lock_fd=self.store.lock_fd)

    def prepare_compensation(self, op):
        origins = self._origins(op)
        selected, service_actions, gateway_actions = {}, [], []
        policy_records = {}
        gateway_creations = []
        for origin in origins:
            for step, record in zip(origin["plan"]["steps"], origin["steps"]):
                if record["prepared"] is None:
                    continue
                if step['kind'] == 'gateway' and record['prepared']['kind'] == 'gateway_create' and record['attempts']:
                    gateway_creations.append((record['prepared'], record['attempts'][-1],
                                              record.get('observation'), record['state'] == 'VERIFIED'))
                if (step['kind'] == 'service' and record['prepared'].get('kind') == 'service_policy_link'
                        and (record['effective'] or record['attempts'] or record['state'] == 'VERIFIED')):
                    policy_records[record['prepared']['path']] = (record['prepared'], record['attempts'])
                # A reboot can load published definitions before the planned
                # explicit reload is attempted. Their original manager tree
                # remains a required restoration target in either case.
                if step["kind"] == "service" and step["action"].get("kind") == "service_daemon_reload":
                    service_actions.append(record["prepared"])
                    continue
                if not record["effective"]:
                    continue
                if step["kind"] == "file":
                    selected.setdefault(step["action"]["target"], []).append((step, record))
                elif step["kind"] == "service":
                    service_actions.append(record["prepared"])
                else:
                    gateway_actions.append(record["prepared"])
            for entry in origin.get("compensation", []):
                step, record = entry["step"], entry["record"]
                if not (record["effective"] or record["restore_attempts"] or record["state"] == "RESTORED"):
                    continue
                if step["kind"] == "file":
                    prepared = record["restore"]
                    selected.setdefault(step["action"]["target"], []).append((step, {
                        **record, "prepared": prepared, "attempts": record["restore_attempts"]}))
                elif step["kind"] == "service":
                    service_actions.append(record["restore"])
                    if record['restore'].get('kind') == 'service_policy_link':
                        policy_records[record['restore']['path']] = (record['restore'], record['restore_attempts'])
                elif step['kind'] == 'gateway':
                    gateway_actions.append(record['restore'])
                    if record['restore']['kind'] == 'gateway_create' and record['restore_attempts']:
                        gateway_creations.append((record['restore'], record['restore_attempts'][-1],
                                                  record.get('restore_observation'), record['state'] == 'RESTORED'))
        # A retained action describes the desired value, not the identity of
        # whatever currently occupies that path. Follow the latest forward or
        # compensation attempt across inheritance to its original supervisor.
        policy_observations = {path: self.services.observe_action(action,
            self._previous(attempts[-1]) if attempts else None, lock_fd=self.store.lock_fd)
            for path, (action, attempts) in policy_records.items()}
        creation_observations = []
        for action, attempt, saved, verified in gateway_creations:
            previous = self._previous(attempt)
            identity = self.gateway.creation_identity(action, previous, observation=saved, lock_fd=self.store.lock_fd)
            if identity is not None or verified:
                previous = {'binding': attempt['binding'], **({'effect_identity': identity} if identity is not None
                            else {'effect_identity_required': True})}
            creation_observations.append(self.gateway.observe_action(action, previous,
                lock_fd=self.store.lock_fd, require_route=False))
        # All file conflicts are checked before even staging a compensation.
        merged = []
        for chain in selected.values():
            first_step, first_record = chain[0]
            step, record = chain[-1]
            observed = self.observe(step, record["prepared"], record["attempts"][-1] if record["attempts"] else None)
            if observed["state"] not in {"original", "target"} or not observed["closed"]:
                raise DeployError("RESTORE_CONFLICT", "A retained file cannot be safely compensated")
            published = _clone(record["prepared"])
            original = first_record["prepared"]
            reservations = {}
            for _, item in chain:
                for key, value in item["prepared"]["preparation_reservations"].items():
                    if key in reservations and reservations[key] != value:
                        raise DeployError("RESTORE_CONFLICT", "Inherited preparation reservation changed")
                    reservations[key] = value
            published.update(
                retained_state_dirs=list(dict.fromkeys(path for _, item in chain for path in item["prepared"]["retained_state_dirs"])),
                retained_namespaces=list(dict.fromkeys(prefix for _, item in chain for prefix in item["prepared"]["retained_namespaces"])),
                preparation_reservations=reservations, preparation_budget_bytes=sum(reservations.values()))
            merged.append((first_step, published, original))
        result = []
        for number, (step, published, original) in enumerate(merged):
            restore_step = {"id": f"restore-file-{number:03d}", "kind": "file", "action": {**step["action"], "phase": "files"}}
            prepared = files.prepare_restore(published, self._directory(op, restore_step["id"], "restore"),
                operation_id=op["id"], attempt_id=restore_step["id"], lock_fd=self.store.lock_fd, baseline=original)
            result.append({"step": restore_step, "prepared": prepared})
        current, retained, objects = self._retention([entry["prepared"] for entry in result])
        for kind, actions, adapter in (("service", service_actions, self.services if service_actions else None),
                                       ("gateway", gateway_actions, self.gateway if gateway_actions else None)):
            if actions:
                kwargs = {"retained_tree": current, "retained_target": retained,
                          "policy_observations": policy_observations} if kind == "service" else {
                          'creation_observations': creation_observations}
                for action in adapter.plan_restore(actions, **kwargs):
                    if action["kind"] == "service_daemon_reload":
                        action["retained_files"] = objects
                    result.append({"step": {"id": "pending", "kind": kind, "action": action}, "prepared": _clone(action)})
        result.sort(key=lambda item: action_order(item["step"], self.profile))
        for number, item in enumerate(result):
            item["step"]["id"] = f"compensate-{number:03d}"
        fixed = {**op, 'compensation': result}
        for item in result:
            if item['prepared'].get('kind') == 'gateway_start':
                reference = self._creation_reference(item['step'], fixed, restore=True)
                if reference is not None:
                    item['prepared']['creation_ref'] = reference
        return result

    def drain(self, op):
        marker = self.gate.snapshot()
        if marker["state"] != "CLOSED" or marker["owner"] != op["id"]:
            raise DeployError("MAINTENANCE_CONFLICT", "Drain requires the operation's durable maintenance ownership")
        active = [value for value in marker["responsibilities"].values() if value["state"] != "CLOSED"]
        if not active:
            # Once CLOSED, no new responsibility can be accepted. This durable
            # empty set remains sufficient after our own manager stop/reboot;
            # asking its now-stopped socket would deadlock normal recovery.
            return {"quiescent": True, "accepted_responsibilities": 0, "gate_sequence": marker["sequence"]}
        # Original pipes cannot survive a host boot. Close their admission
        # custody only after separately proving all original task parents/jobs
        # empty; do not need a stopped manager socket to recover that fact.
        from .preparations import observe_reboot_closure, original_preparation, original_not_started, original_execution
        boot = startup.boot_id()
        old = [duty for duty in active if duty["loaded"]["boot_id"] != boot]
        observations = {}
        if old:
            current_components = {duty['loaded']['component'] for duty in active
                                  if duty['loaded']['boot_id'] == boot}
            if current_components:
                # A current-boot no-child receipt may still need its manager's
                # finish write. Resolve that custody before the independent
                # old-boot scan; otherwise the scan blocks its own prerequisite.
                for component in sorted(current_components):
                    observations[component] = self._probe(component, reconcile=True)
                marker = self.gate.snapshot()
                if marker['state'] != 'CLOSED' or marker['owner'] != op['id']:
                    raise DeployError('MAINTENANCE_CONFLICT', "Drain requires the operation's durable maintenance ownership")
                active = [duty for duty in marker['responsibilities'].values() if duty['state'] != 'CLOSED']
                if not active:
                    return {'quiescent': True, 'accepted_responsibilities': 0, 'observations': observations}
                old = [duty for duty in active if duty['loaded']['boot_id'] != boot]
            snapshot = None
            checked = set()
            preparation_boots = {}
            preparation_unstarted = {}
            components = {duty['loaded']['component'] for duty in old}
            configurations = {}
            # The observer scans the original task tree, including attempts
            # already closed by an earlier drain. Retain their precise boot
            # identities across interruption between individual finish writes.
            for duty in marker['responsibilities'].values():
                component = duty['loaded']['component']
                never_started = duty['state'] == 'CLOSED' and duty['proof'] == {'never_dispatched': True}
                if (duty['kind'] != 'prepare' or component not in components
                        or duty['loaded']['boot_id'] == boot and not never_started):
                    continue
                if component not in configurations:
                    path = self.profile['guarded_components'][component]['configuration']
                    configurations[component] = decode(startup.protected_read(path, owner_uid=self.owner))
                config = configurations[component]
                # A completed responsibility from an older task root is outside
                # this observer's scope. Active responsibilities may never use
                # that exclusion to evade their original identity check.
                if duty['state'] == 'CLOSED' and duty['binding'].get('private_root') != config.get('private_root'):
                    continue
                if original_preparation(self.profile, duty, configuration=config):
                    if duty['loaded']['boot_id'] != boot:
                        preparation_boots.setdefault(component, {})[duty['attempt_id']] = duty['loaded']['boot_id']
                    elif never_started:
                        preparation_unstarted.setdefault(component, {})[duty['attempt_id']] = original_not_started(self.profile, duty)
            for duty in old:
                execution = None
                if duty['kind'] == 'prepare':
                    if duty['state'] == 'ACCEPTED':
                        self.gate.finish(duty, {'never_dispatched': True})
                        continue
                else:
                    if snapshot is None:
                        snapshot = self.preparation_inventory()
                    matching = [item for item in snapshot["tasks"] if item["component"] == duty["loaded"]["component"]
                        and item["operation_id"] == duty["operation_id"]
                        and item.get("prepared") == duty["binding"].get("prepared")]
                    if not matching:
                        execution = original_execution(self.profile, duty)
                    elif len(matching) != 1:
                        raise DeployError("RETAINED_DISPATCH_UNRESOLVED", "Original boot responsibility has no exact task binding")
                key = (duty["loaded"]["component"], duty["loaded"]["boot_id"])
                if execution is not None:
                    key += (digest(execution),)
                if key not in checked:
                    kwargs = ({'preparation_boots': preparation_boots[key[0]]} if key[0] in preparation_boots else {})
                    if key[0] in preparation_unstarted:
                        kwargs['preparation_unstarted'] = preparation_unstarted[key[0]]
                    if execution is not None:
                        kwargs['original_execution'] = execution
                    observe_reboot_closure(self.profile, key[0], expected_boot=key[1], current_boot=boot, **kwargs)
                    checked.add(key)
                self.gate.finish(duty, {"process_exited": True, "writers_stopped": True})
            active = self.gate.active()
            if not active:
                return {"quiescent": True, "accepted_responsibilities": 0, "reboot_closed": len(old)}
        for component, guard in self.profile["guarded_components"].items():
            if component not in observations and ("prepare" in guard["entrypoints"] or "execute" in guard["entrypoints"]):
                observations[component] = self._probe(component, reconcile=True)
        active = self.gate.active()
        return {"quiescent": not active, "accepted_responsibilities": len(active), "observations": observations}

    def _current_selection(self):
        return startup.read_selection(self.profile["startup_descriptor"], owner_uid=self.owner)

    def _publish_selection(self, op, desired):
        current = self._current_selection()
        self._verify_selection_owner(op, current, desired)
        value = startup.publish(self.profile["startup_descriptor"], desired, self.gate,
                                expected_digest=startup.digest(current), owner_uid=self.owner,
                                maintenance_owner=op["id"])
        return {"digest": value, "selection": desired}

    def _verify_selection_owner(self, op, current, desired=None):
        source = self._source(op)["selection"]
        saved = op["startup"].get("current")
        saved_value = saved.get("selection") if isinstance(saved, dict) else None
        ours = current.get("owner") == op["id"] and current.get("mode") in {"candidate", "blocked"}
        predecessors = set(op.get("inherited", []))
        if op.get("predecessor"):
            predecessors.add(op["predecessor"])
        inherited = current.get("owner") in predecessors and current.get("mode") in {"candidate", "blocked"}
        if current not in (source, saved_value, desired) and not (ours or inherited):
            raise DeployError("STARTUP_CONFLICT", "Startup selection changed outside this recovery chain")
        if ours or inherited:
            templates = [origin["plan"][side]["selection"] for origin in self._origins(op) for side in ("source", "target")]
            if not any(all(current[key] == template[key] for key in ("node_id", "deployment_digest", "members", "components")) for template in templates):
                raise DeployError("STARTUP_CONFLICT", "Owned descriptor has an unrelated configuration")

    def block_startup(self, op):
        current = self._current_selection()
        desired = {**current, "mode": "blocked", "owner": op["id"], "decision_id": None, "permit": None}
        return self._publish_selection(op, desired)

    def candidate_startup(self, op, step, attempt_id):
        if step["kind"] == "file" or step["action"].get("kind") not in {"service_start", "gateway_create", "gateway_start"}:
            return {"changed": False}
        selected = self._source(op) if op["direction"] == "ROLLBACK" else op["plan"]["target"]
        current = self._current_selection()
        permit = current.get("permit") or {}
        claims = _clone(permit.get("claims", {})) if permit.get("boot_id") == startup.boot_id() else {}
        component = (self.profile.get("systemd", {}).get("units", {}).get(step["action"].get("target"), {}).get("component")
                     or self.profile.get("gateway", {}).get("component"))
        claims.pop(component, None)
        desired = {**_clone(selected["selection"]), "mode": "candidate", "owner": op["id"], "decision_id": None,
                   "permit": {"boot_id": startup.boot_id(), "attempt_id": attempt_id, "claims": claims}}
        return self._publish_selection(op, desired)

    def _guard(self, target, wanted):
        selection = self._current_selection()
        component = (self.profile.get("systemd", {}).get("units", {}).get(target, {}).get("component")
                     or self.profile.get("gateway", {}).get("component"))
        desired = selection["components"].get(component)
        if not desired:
            raise DeployError("STARTUP_GUARD_REQUIRED", "Action has no selected guarded component")
        startup.verify_members(selection, owner_uid=self.owner)
        permit = selection.get("permit") or {}
        return {"descriptor_digest": startup.digest(selection), "config_digest": desired["configuration_digest"],
                "deployment_digest": selection["deployment_digest"], "mode": selection["mode"],
                "target_running": desired["running"], "boot": permit.get("boot_id"), "attempt_id": permit.get("attempt_id")}

    def check_local(self, op, rollback=False):
        selected = self._source(op) if rollback else op["plan"]["target"]
        gateway = self.profile.get("gateway", {})
        original_gateway = self._origins(op)[0]["plan"]["profile"].get("gateway", {})
        compose = original_gateway.get("original_compose", original_gateway.get("compose")) if rollback else gateway.get("compose")
        self._verify_components(selected["selection"], gateway_compose=compose)
        current = self._current_selection()
        proofs = {}
        for component, desired in selected["selection"]["components"].items():
            if desired["running"]:
                loaded = self._probe(component)["loaded"]
                self._match_loaded(loaded, selected["selection"], component)
                if current["mode"] == "candidate":
                    claim = current["permit"]["claims"].get(component)
                    if claim != {key: loaded.get(key) for key in ("pid", "start_ticks", "boot_id")}:
                        raise DeployError("STARTUP_INSTANCE_MISMATCH", "Candidate listener did not claim this process instance")
                proofs[component] = loaded
        if selected.get("services"):
            actual = self.services.observe()
            if actual["jobs"]:
                raise DeployError("SERVICE_JOB_PENDING", "Service manager still has selected jobs")
            for unit, target in selected["services"].items():
                value = actual["units"][unit]
                if (value["active"] == "active") != target["running"] or value["policy"] != target["policy"]:
                    raise DeployError("SERVICE_POSTCONDITION", "Selected service run/enable state differs")
                if target["running"] and value["definition_digest"] != target["definition_digest"]:
                    raise DeployError("SERVICE_POSTCONDITION", "Manager did not load the selected unit definition")
                if not target["running"] and (value["active"] not in {"inactive", "failed"} or value["pid"] or value["job"][0]):
                    raise DeployError("SERVICE_POSTCONDITION", "Selected stopped service still has activity")
        if selected.get("gateway") is not None:
            value, target = self.gateway.observe(), selected["gateway"]
            if ((value["kind"] == "container") != target.get("present", True)
                    or (value.get("status") == "running") != target["running"]
                    or value["kind"] == "container" and value.get("compose") != compose):
                raise DeployError("GATEWAY_POSTCONDITION", "Gateway run/presence state differs from selection")
        safety = None
        if selected.get("gateway", {}).get("running") and not self.profile.get("gateway_checks"):
            raise DeployError("LOCAL_SECURITY_CHECK_REQUIRED", "A running gateway needs the four route safety checks")
        if selected.get("gateway", {}).get("running") and self.profile.get("gateway_checks"):
            loaded = self._gateway_probe(self.profile["gateway"]["component"], checks=self.profile["gateway_checks"])["loaded"]
            self._match_loaded(loaded, selected["selection"], self.profile["gateway"]["component"])
            safety = loaded.get("routes")
            if (not isinstance(safety, dict) or safety.get("specification_digest") != digest(self.profile["gateway_checks"])
                    or safety.get("passed") is not True or not isinstance(safety.get("checks"), list)
                    or len(safety["checks"]) != len(self.profile["gateway_checks"]["checks"])
                    or any(item.get("status") != "PASSED" for item in safety["checks"])):
                raise DeployError("LOCAL_SECURITY_CHECK_FAILED", "Candidate routes have not passed their bound safety checks")
        baseline = op["checks"].get("retained")
        if baseline is not None and self.preparation_inventory()["tasks"] != baseline["preparations"]["tasks"]:
            raise DeployError("RETENTION_CONFLICT", "Selected deployment changed original preparation records")
        results = {} if op.get("decision") == "ABORTED_NO_CHANGE" and baseline is None else self.retained_results(selected)
        if baseline is not None and results != baseline["results"]:
            raise DeployError("RETENTION_CONFLICT", "Selected read routes differ from the original task/evidence readback")
        return {"passed": True, "deployment_digest": selected["deployment_digest"], "loaded": proofs,
                "security": safety, "retained_results": results, "observed_ns": time.time_ns()}

    def publish_stable(self, op):
        durable = self.store.get(op["id"])
        if (op.get("decision") not in {"COMMITTED", "ROLLED_BACK", "ABORTED_NO_CHANGE"}
                or not op.get("decision_id")
                or durable["decision"] != op["decision"] or durable["decision_id"] != op["decision_id"]):
            raise DeployError("DECISION_NOT_DURABLE", "Stable selection requires the saved matching decision")
        selected = op["plan"]["target"] if op["decision"] == "COMMITTED" else self._source(op)
        desired = {**_clone(selected["selection"]), "mode": "stable", "owner": None,
                   "decision_id": op["decision_id"], "permit": None}
        return self._publish_selection(op, desired)

    def release_valid(self, op):
        selected = op["plan"]["target"] if op["decision"] == "COMMITTED" else self._source(op)
        unsafe = {origin["plan"]["profile"]["security_repair"]["unsafe_deployment_digest"]
                  for origin in self._origins(op) if origin["plan"]["profile"].get("security_repair")}
        if selected["deployment_digest"] in unsafe:
            return {"passed": False, "reason": "UNSAFE_BASELINE_REQUIRES_REPAIR"}
        current = self._current_selection()
        desired = {**_clone(selected["selection"]), "mode": "stable", "owner": None,
                   "decision_id": op["decision_id"], "permit": None}
        self._verify_selection_owner(op, current, desired)
        return self.check_local(op, rollback=op["decision"] != "COMMITTED")

    def selected_deployment(self, op):
        return op["plan"]["target"] if op["decision"] == "COMMITTED" else self._source(op)

    def _committed_gateway(self, chain):
        """Verify the last original gateway identity before planning rollback.

        A committed decision is historical evidence, not permission to replace
        a new container now occupying the old name. Keep route readiness out of
        this identity/closure check so an unhealthy original can be restored.
        """
        latest = None
        for origin in chain:
            for step, record in zip(origin['plan']['steps'], origin['steps']):
                if (step['kind'] == 'gateway' and record.get('prepared') is not None
                        and (record['effective'] or record['attempts'] or record['state'] == 'VERIFIED')):
                    latest = origin, step, record['prepared'], record['attempts'], record.get('observation')
            for entry in origin.get('compensation', []):
                step, record = entry['step'], entry['record']
                if (step['kind'] == 'gateway' and (record['effective'] or record['restore_attempts']
                        or record['state'] == 'RESTORED')):
                    latest = origin, step, record['restore'], record['restore_attempts'], record.get('restore_observation')
        if latest is None:
            return None
        self._mutating_adapters(readonly=True)
        origin, step, action, attempts, saved = latest
        previous = self._previous(attempts[-1]) if attempts else None
        kind = action['kind']
        identity = None
        if kind == 'gateway_create':
            identity = self.gateway.creation_identity(action, previous, observation=saved, lock_fd=self.store.lock_fd)
            if identity is not None:
                previous = {'binding': attempts[-1]['binding'], 'effect_identity': identity}
        elif kind == 'gateway_start':
            identity = self._start_identity(step, action, origin)
            if identity is None:
                identifier = self.gateway._start_identity(action, None)
                if identifier is not None:
                    identity = {'container_id': identifier, 'daemon_id': action['before']['daemon_id']}
        elif action['before'].get('kind') == 'container':
            identity = {'container_id': action['before']['id'], 'daemon_id': action['before']['daemon_id']}
        if identity is None or identity['daemon_id'] != self.profile['gateway']['daemon_id']:
            raise DeployError('RESTORE_GATEWAY_IDENTITY', 'Committed gateway has no exact original object proof')
        observed = self.gateway.observe_action(action, previous, lock_fd=self.store.lock_fd,
            require_route=False, expected_identity=identity if kind == 'gateway_start' else None)
        if observed.get('closed') is not True or observed.get('outcome') in {'unknown', 'running'}:
            raise DeployError('CALLER_NOT_CLOSED', 'Original gateway call still needs reconciliation')
        current = observed['observation']
        if current['kind'] == 'container':
            if current['id'] != identity['container_id'] or current['daemon_id'] != identity['daemon_id']:
                raise DeployError('RESTORE_GATEWAY_IDENTITY', 'Committed gateway was independently replaced')
        else:
            from urllib.parse import quote
            original = self.gateway.engine.request('GET', '/containers/' + quote(identity['container_id'], safe='') + '/json', missing=True)
            if original is not None:
                raise DeployError('RESTORE_GATEWAY_IDENTITY', 'Original gateway still exists outside its recorded name')
        return current

    def restored_plan(self, op, request_id):
        # A rollback of a committed deployment is a new plan, never a rewrite of
        # its historic decision. Build from retained originals after observation.
        from .planner import MANIFEST_SCHEMA, build_plan
        from .recovery import entries, reload_tree
        chain = self._origins(op)
        gateway_selected = bool(self.profile.get('gateway') and op['plan']['target'].get('gateway') is not None)
        gateway = self._committed_gateway(chain) if gateway_selected else None
        original_files, latest_files = {}, {}
        for step, prepared, attempts, effective in entries(chain):
            if step["kind"] != "file" or not (effective or attempts):
                continue
            path = step["action"]["target"]
            original_files.setdefault(path, prepared)
            latest_files[path] = (step, prepared, attempts)
        for step, prepared, attempts in latest_files.values():
            observed = self.observe(step, prepared, attempts[-1] if attempts else None)
            if observed["state"] != "target" or not observed["closed"]:
                raise DeployError("RESTORE_CONFLICT", "Committed file changed outside the original deployment")
        specs = []
        for path, prepared in original_files.items():
            original = prepared["original"]
            if not original.get("exists"):
                specs.append({"target": path, "remove": True})
                continue
            files.verify_preparation_objects([prepared["backup"]], owner_uid=self.owner,
                                             limits=files.FileLimits(**self.profile.get("file_limits", {})))
            specs.append({"target": path, "source": prepared["backup"]["path"],
                          **{key: original[key] for key in ("mode", "uid", "gid")}})
        source = _clone(op["plan"]["target"])
        source["selection"] = self._current_selection()
        if gateway is not None:
            source['gateway'].update(present=gateway['kind'] == 'container', running=gateway.get('status') == 'running')
        profile = _clone(self.profile)
        profile.pop("recovery_from", None)
        if any(origin["plan"]["profile"].get("security_repair") for origin in chain):
            # An explicit rollback cannot turn a previously unsafe selection
            # into a new safe target merely by swapping source and target.
            raise DeployError("UNSAFE_ROLLBACK_TARGET", "Known unsafe baseline requires a corrected linked plan")
        if profile.get("systemd"):
            profile["systemd"]["reload_scope"]["loaded_snapshot"] = reload_tree(profile, chain)
        if "gateway" in profile:
            original = self._origins(op)[0]["plan"]["profile"]["gateway"]
            profile["gateway"]["original_compose"] = profile["gateway"]["compose"]
            profile["gateway"]["compose"] = _clone(original.get("original_compose", original["compose"]))
        plan = build_plan({"schema": MANIFEST_SCHEMA, "request_id": request_id, "node_id": op["plan"]["node_id"],
                           "source": source, "target": self._source(op), "files": specs, "profile": profile}, PlanningEnvironment(profile))
        if gateway_selected and gateway is None and any(step['kind'] == 'gateway' for step in plan['steps']):
            raise DeployError('RESTORE_GATEWAY_IDENTITY', 'Rollback cannot claim an unrecorded gateway object')
        if gateway is not None:
            for step in plan['steps']:
                if step['kind'] != 'gateway':
                    continue
                before = step['action']['before']
                if (before['kind'] == 'container' and (gateway['kind'] != 'container'
                        or before['id'] != gateway['id'] or before['daemon_id'] != gateway['daemon_id'])):
                    raise DeployError('RESTORE_GATEWAY_IDENTITY', 'Gateway changed while constructing rollback')
        return plan
