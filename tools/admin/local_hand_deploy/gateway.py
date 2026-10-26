"""Fixed Compose single-service scope implemented through the local Engine API.

Only an existing daemon, pinned image, external networks and bind mounts are
accepted. Container create/start/stop/remove are separate resumable effects;
there is no project up/down, dependency start, image pull, network/volume create,
prune or orphan cleanup. This is the finite --no-deps equivalent adapter.
"""
from __future__ import annotations

import hashlib
import http.client
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import socket
import stat
import urllib.parse

from .services import validate_guard
from .supervision import AdapterError, boot_id, digest, verify_lock


class DockerHTTPError(AdapterError):
    """A complete bounded HTTP error reply, not a transport completion guess."""
    def __init__(self, method, path, status, body):
        super().__init__(f"DOCKER_HTTP_{status}")
        self.response = {"method": method, "path": path, "status": status,
                         "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


class DockerRequestNotSent(AdapterError):
    """Failure at a local boundary that precedes every HTTP request byte."""
    def __init__(self, method, path, stage, error):
        detail = str(error)[:256]
        super().__init__(f"DOCKER_REQUEST_NOT_SENT:{stage}:{type(error).__name__}:{detail}")
        self.request = {"method": method, "path": path, "stage": stage,
                        "error_type": type(error).__name__, "error": detail}


class _UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class DockerEngine:
    def __init__(self, socket_path="/var/run/docker.sock", *, api_version="v1.45", timeout=15, maximum=1048576):
        self.path, self.version, self.timeout, self.maximum = socket_path, api_version, timeout, maximum
        if not re.fullmatch(r"v1\.[0-9]{2}", api_version):
            raise AdapterError("DOCKER_API_VERSION")
        if not Path(socket_path).is_absolute() or ".." in Path(socket_path).parts:
            raise AdapterError("DOCKER_SOCKET_PATH")

    def request(self, method, path, body=None, *, missing=False):
        connection = _UnixHTTP(self.path, self.timeout)
        try:
            try:
                raw = None if body is None else json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
                if raw is not None and len(raw) > self.maximum:
                    raise AdapterError("DOCKER_REQUEST_BOUND")
            except (TypeError, ValueError, OverflowError, RecursionError, AdapterError) as error:
                raise DockerRequestNotSent(method, path, "encoding", error) from error
            try:
                # Connect explicitly: HTTPConnection.request otherwise mixes
                # connect failures with potentially partial request transmission.
                connection.connect()
            except OSError as error:
                raise DockerRequestNotSent(method, path, "connect", error) from error
            connection.request(method, "/" + self.version + path, raw,
                               {"Content-Type": "application/json", "Connection": "close"})
            response = connection.getresponse()
            data = response.read(self.maximum + 1)
            if len(data) > self.maximum:
                raise AdapterError("DOCKER_REPLY_BOUND")
            # HTTPResponse.read(amt) can return a short body without raising
            # IncompleteRead. A truncated error is not a completed API reply.
            if response.length not in (None, 0) or (response.chunked and not response.isclosed()):
                raise AdapterError("DOCKER_REPLY_INCOMPLETE")
            if response.status == 404 and missing:
                return None
            if not 200 <= response.status < 300:
                raise DockerHTTPError(method, path, response.status, data)
            return None if not data else json.loads(data)
        finally:
            connection.close()


def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}", value):
        raise AdapterError("GATEWAY_NAME")
    return value


def _quote(value):
    return urllib.parse.quote(value, safe="")


def _resource_config(source):
    """Normalize only the bounded container controls supported by this adapter."""
    result = {}
    def memory(value, *, minimum=1, maximum=16 * 1024**3):
        if type(value) is int:
            size = value
        elif isinstance(value, str) and (match := re.fullmatch(r"([1-9][0-9]{0,12})([kKmMgG]?)", value)):
            size = int(match[1]) * {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3}[match[2].lower()]
        else:
            raise AdapterError("GATEWAY_MEMORY_BOUND")
        if not minimum <= size <= maximum: raise AdapterError("GATEWAY_MEMORY_BOUND")
        return size
    if "cpus" in source:
        try:
            number = Decimal(str(source["cpus"]))
            if not number.is_finite() or not 0 < number <= 64:
                raise ValueError()
            nano = number * 10**9
            if nano != nano.to_integral_value():
                raise ValueError()
            result["NanoCpus"] = int(nano)
        except (InvalidOperation, ValueError, OverflowError):
            raise AdapterError("GATEWAY_CPU_BOUND") from None
    if "mem_limit" in source:
        result["Memory"] = memory(source["mem_limit"], minimum=6 * 1024**2)
    if "pids_limit" in source:
        value = source["pids_limit"]
        if type(value) is not int or not 1 <= value <= 4096: raise AdapterError("GATEWAY_PID_BOUND")
        result["PidsLimit"] = value
    if "cap_add" in source:
        values = source["cap_add"]
        if (not isinstance(values, list) or any(not isinstance(v, str) or v not in {"CHOWN", "SETUID", "SETGID"} for v in values)
                or len(values) != len(set(values))):
            raise AdapterError("GATEWAY_CAPABILITY_SCOPE")
        result["CapAdd"] = values
    if "group_add" in source:
        values = source["group_add"]
        if (not isinstance(values, list) or len(values) > 16
                or any(not isinstance(v, str) or re.fullmatch(r"[1-9][0-9]{0,9}", v) is None or int(v) > 2**31 - 1 for v in values)
                or len(values) != len(set(values))):
            raise AdapterError("GATEWAY_GROUP_SCOPE")
        result["GroupAdd"] = values
    if "tmpfs" in source:
        mounts = source["tmpfs"]
        if not isinstance(mounts, dict) or set(mounts) != {"/run/local-hand-gateway"}:
            raise AdapterError("GATEWAY_TMPFS_SCOPE")
        options = mounts["/run/local-hand-gateway"]
        if not isinstance(options, str): raise AdapterError("GATEWAY_TMPFS_OPTIONS")
        parts = options.split(",")
        size = [part[5:] for part in parts if part.startswith("size=")]
        if (len(parts) != 6 or len(set(parts)) != 6 or len(size) != 1
                or not {"rw", "nosuid", "nodev", "noexec", "mode=0755"} <= set(parts)):
            raise AdapterError("GATEWAY_TMPFS_OPTIONS")
        memory(size[0], maximum=64 * 1024**2)
        result["Tmpfs"] = mounts
    if "logging" in source:
        config = source["logging"]
        if (not isinstance(config, dict) or set(config) != {"driver", "options"} or config["driver"] != "local"
                or not isinstance(config["options"], dict) or set(config["options"]) != {"max-size", "max-file"}):
            raise AdapterError("GATEWAY_LOG_SCOPE")
        options = config["options"]
        if not isinstance(options["max-file"], str) or options["max-file"] not in {str(i) for i in range(1, 11)}:
            raise AdapterError("GATEWAY_LOG_BOUND")
        memory(options["max-size"], maximum=64 * 1024**2)
        if not isinstance(options["max-size"], str): raise AdapterError("GATEWAY_LOG_BOUND")
        result["LogConfig"] = {"Type": "local", "Config": options}
    return result


class GatewayAdapter:
    def __init__(self, profile, runner, *, engine=None, guard_check=None, route_probe=None):
        self.profile, self.runner = profile, runner
        self.project = _name(profile["project"])
        self.service = _name(profile["service"])
        self.name = _name(profile["container_name"])
        self.engine = engine or DockerEngine(profile.get("socket", "/var/run/docker.sock"),
            api_version=profile.get("api_version", "v1.45"), timeout=min(runner.timeout / 2, 30))
        self.guard_check, self.route_probe = guard_check, route_probe
        self._validate_compose(profile["compose"])
        retained = profile.get("retained_composes", [])
        if not isinstance(retained, list) or len(retained) > 32:
            raise AdapterError("RETAINED_GATEWAY_PROFILE_BOUND")
        for compose in retained:
            self._validate_compose(compose)

    def _validate_compose(self, compose):
        if not isinstance(compose, dict) or set(compose) - {"name", "services", "networks", "volumes"}:
            raise AdapterError("COMPOSE_SCOPE")
        if compose.get("name", self.project) != self.project or self.service not in compose.get("services", {}):
            raise AdapterError("COMPOSE_PROJECT_SERVICE")
        service = compose["services"][self.service]
        supported = {"image", "container_name", "entrypoint", "command", "environment", "volumes", "networks",
                     "ports", "restart", "read_only", "user", "labels", "depends_on", "cap_drop", "security_opt",
                     "cpus", "mem_limit", "pids_limit", "tmpfs", "logging", "group_add", "cap_add"}
        if set(service) - supported:
            raise AdapterError("UNSUPPORTED_GATEWAY_SERVICE_FIELD")
        _resource_config(service)
        if service.get("container_name", self.name) != self.name:
            raise AdapterError("GATEWAY_CONTAINER_NAME")
        if not re.fullmatch(r"(?:[^\s]+@)?sha256:[0-9a-f]{64}", service.get("image", "")):
            raise AdapterError("PINNED_GATEWAY_IMAGE_REQUIRED")
        if service.get("restart", "no") not in ("no", "unless-stopped", "always", "on-failure"):
            raise AdapterError("GATEWAY_RESTART_POLICY")
        for name in service.get("networks", {}):
            network = compose.get("networks", {}).get(name)
            if not isinstance(network, dict) or network.get("external") is not True or set(network) - {"external", "name"}:
                raise AdapterError("EXTERNAL_NETWORK_REQUIRED")
            if isinstance(service["networks"], dict) and service["networks"][name] not in ({}, None):
                raise AdapterError("GATEWAY_NETWORK_OPTIONS_NOT_SUPPORTED")
        for mount in service.get("volumes", []):
            if (not isinstance(mount, dict) or set(mount) - {"type", "source", "target", "read_only", "bind"}
                    or mount.get("type") != "bind" or not mount.get("read_only")):
                raise AdapterError("READ_ONLY_BIND_REQUIRED")
            for key in ("source", "target"):
                if not Path(mount[key]).is_absolute() or ".." in Path(mount[key]).parts:
                    raise AdapterError("GATEWAY_BIND_PATH")
            if mount.get("bind", {}).get("create_host_path", False):
                raise AdapterError("GATEWAY_MUST_NOT_CREATE_HOST_PATH")
        if service.get("environment") and not isinstance(service["environment"], dict):
            raise AdapterError("RESOLVED_ENVIRONMENT_REQUIRED")
        for key in ("entrypoint", "command"):
            if key in service and (not isinstance(service[key], list) or any(not isinstance(x, str) for x in service[key])):
                raise AdapterError("RESOLVED_ARGV_REQUIRED")
        for port in service.get("ports", []):
            if not isinstance(port, dict) or set(port) - {"target", "published", "host_ip", "protocol", "mode"}:
                raise AdapterError("RESOLVED_PORT_REQUIRED")
            if port.get("protocol", "tcp") != "tcp" or port.get("mode", "ingress") not in ("ingress", "host"):
                raise AdapterError("GATEWAY_PORT_PROTOCOL")
            if not all(str(port.get(k, "")).isdigit() and 1 <= int(port[k]) <= 65535 for k in ("target", "published")):
                raise AdapterError("GATEWAY_PORT_RANGE")
        if any(key.startswith("com.docker.compose.") or key.startswith("local-hand.deploy.") for key in service.get("labels", {})):
            raise AdapterError("RESERVED_GATEWAY_LABEL")
        if any(value is None or not isinstance(value, (str, int, float, bool)) for value in service.get("environment", {}).values()):
            raise AdapterError("UNRESOLVED_GATEWAY_ENVIRONMENT")

    def prerequisites(self, *, starting=False):
        info = self.engine.request("GET", "/info")
        if info.get("ID") != self.profile.get("daemon_id"):
            raise AdapterError("DOCKER_DAEMON_ID_MISMATCH")
        source = self.profile["compose"]["services"][self.service]
        image = self.engine.request("GET", "/images/" + _quote(source["image"]) + "/json")
        if image.get("Config", {}).get("Volumes"):
            raise AdapterError("GATEWAY_IMAGE_IMPLICIT_VOLUMES")
        if image.get("Config", {}).get("OnBuild"):
            raise AdapterError("GATEWAY_IMAGE_ONBUILD")
        # Image entrypoint is part of the frozen image, and startup guarding must
        # actually be installed there; a callback alone does not make it so.
        networks = {}
        for logical in source.get("networks", {}):
            external = self.profile["compose"]["networks"][logical].get("name", logical)
            observed = self.engine.request("GET", "/networks/" + _quote(external))
            if observed.get("Id") != self.profile.get("network_ids", {}).get(external):
                raise AdapterError("GATEWAY_EXTERNAL_NETWORK_CHANGED")
            networks[external] = observed["Id"]
        for mount in source.get("volumes", []):
            value = Path(mount["source"]).lstat()
            if not (stat.S_ISREG(value.st_mode) or stat.S_ISDIR(value.st_mode)):
                raise AdapterError("GATEWAY_BIND_OBJECT")
        for service in source.get("depends_on", {}):
            dep_id = self.profile.get("dependency_container_ids", {}).get(service)
            if not dep_id:
                raise AdapterError("GATEWAY_DEPENDENCY_BINDING_REQUIRED")
            if not starting:
                continue
            dep = self.engine.request("GET", "/containers/" + _quote(dep_id) + "/json")
            if dep["Id"] != dep_id or not dep.get("State", {}).get("Running"):
                raise AdapterError("GATEWAY_DEPENDENCY_NOT_READY")
            health = dep.get("State", {}).get("Health", {}).get("Status")
            if health not in (None, "healthy"):
                raise AdapterError("GATEWAY_DEPENDENCY_NOT_HEALTHY")
        return {"daemon_id": info["ID"], "image_id": image["Id"], "image_config": image.get("Config", {}), "networks": networks}

    def _using(self, compose):
        if compose == self.profile["compose"]:
            return self
        retained = []
        for value in [self.profile["compose"], self.profile.get("original_compose"), *self.profile.get("retained_composes", [])]:
            if value is not None and value != compose and value not in retained:
                retained.append(value)
        return GatewayAdapter({**self.profile, "compose": compose, "original_compose": self.profile["compose"],
                               "retained_composes": retained}, self.runner, engine=self.engine,
                              guard_check=self.guard_check, route_probe=self.route_probe)

    def _matches_spec(self, value, compose):
        adapter = self._using(compose)
        prerequisites = adapter.prerequisites()
        source = compose["services"][self.service]
        config, host = value.get("Config", {}), value.get("HostConfig", {})
        image = prerequisites["image_config"]
        if value.get("Image") != prerequisites["image_id"]:
            return False
        for source_key, field in (("entrypoint", "Entrypoint"), ("command", "Cmd"), ("user", "User")):
            if config.get(field) != source.get(source_key, image.get(field)):
                return False
        def environment(items):
            return dict(item.split("=", 1) for item in (items or []))
        expected_env = {**environment(image.get("Env")), **{key: str(val) for key, val in source.get("environment", {}).items()}}
        if environment(config.get("Env")) != expected_env:
            return False
        expected_body = adapter._create_body({"config_digest": "0" * 64, "deployment_digest": "0" * 64}, "observe")
        for field in ("PortBindings", "ReadonlyRootfs", "CapDrop", "SecurityOpt"):
            if (host.get(field) or ({} if field == "PortBindings" else [] if field in ("CapDrop", "SecurityOpt") else False)) != expected_body["HostConfig"][field]:
                return False
        for field, expected in _resource_config(source).items():
            actual = host.get(field)
            if field in ("CapAdd", "GroupAdd"):
                if sorted(actual or []) != sorted(expected): return False
            elif actual != expected:
                return False
        if host.get("RestartPolicy", {}).get("Name", "no") != source.get("restart", "no"):
            return False
        # Engines may also list tmpfs mounts here; their exact map is checked
        # above in HostConfig, and any listed entries must agree with that map.
        for mount in value.get("Mounts", []):
            if mount.get("Type") == "tmpfs" and (mount.get("Destination") not in source.get("tmpfs", {})
                    or mount.get("Source") not in (None, "") or mount.get("RW") is not True):
                return False
        actual_mounts = sorted((m.get("Type"), m.get("Source"), m.get("Destination"), not m.get("RW", True))
                               for m in value.get("Mounts", []) if m.get("Type") != "tmpfs")
        expected_mounts = sorted(("bind", m["source"], m["target"], True) for m in source.get("volumes", []))
        if actual_mounts != expected_mounts:
            return False
        actual_networks = value.get("NetworkSettings", {}).get("Networks", {})
        if set(actual_networks) != set(prerequisites["networks"]) and not (not prerequisites["networks"] and set(actual_networks) == {"none"}):
            return False
        return all(actual_networks[name].get("NetworkID") == network_id for name, network_id in prerequisites["networks"].items())

    def observe(self, *, require_route=True):
        prerequisites = self.prerequisites()
        value = self.engine.request("GET", "/containers/" + _quote(self.name) + "/json", missing=True)
        if value is None:
            return {"kind": "absent", "daemon_id": prerequisites["daemon_id"]}
        labels = value.get("Config", {}).get("Labels", {}) or {}
        if labels.get("com.docker.compose.project") != self.project or labels.get("com.docker.compose.service") != self.service:
            raise AdapterError("FOREIGN_GATEWAY_CONTAINER")
        matched_compose = None
        for compose in (self.profile["compose"], self.profile.get("original_compose"), *self.profile.get("retained_composes", [])):
            if compose is not None and self._matches_spec(value, compose):
                matched_compose = compose
                break
        if matched_compose is None:
            raise AdapterError("GATEWAY_CONFIG_OUTSIDE_RETAINED_PROFILES")
        state = value.get("State", {})
        if state.get("Paused") or state.get("Restarting") or state.get("Dead"):
            status = "transition"
        else:
            status = "running" if state.get("Running") else "stopped"
        # A stopped container has no live status listener. Its durable inspect
        # state is sufficient for create/stop/absence recovery; readiness is
        # required only for a running instance.
        route = (self.route_probe(value["Id"]) if require_route and self.route_probe is not None
                 and status == "running" else None)
        return {"kind": "container", "id": value["Id"], "daemon_id": prerequisites["daemon_id"],
                "status": status, "image_id": value.get("Image"), "labels": labels,
                "started_at": state.get("StartedAt"), "finished_at": state.get("FinishedAt"),
                "restart_policy": value.get("HostConfig", {}).get("RestartPolicy"),
                "mounts": value.get("Mounts", []), "route": route, "compose": matched_compose}

    @staticmethod
    def _configuration(value):
        labels = value.get("labels", {})
        return {key: value.get(key, labels.get("local-hand.deploy." + suffix))
                for key, suffix in (("config_digest", "config"), ("deployment_digest", "deployment"))}

    @classmethod
    def _retain_original_binding(cls, value, original):
        # The planner may bind a pre-existing unlabeled container to its verified
        # original startup selection. Carry that proof only for that exact object
        # and resolved configuration, never onto a replacement container.
        if (value.get("kind") == original.get("kind") == "container"
                and value.get("id") == original.get("id")
                and value.get("daemon_id") == original.get("daemon_id")
                and value.get("compose") == original.get("compose")):
            return {**value, **cls._configuration(original)}
        return value

    def plan(self, target, baseline=None):
        if target.get("running") not in (True, False) or not isinstance(target.get("present", True), bool):
            raise AdapterError("GATEWAY_TARGET")
        before = self.observe(require_route=target["running"] and target.get("present", True)) if baseline is None else baseline
        if before.get("status") == "transition":
            raise AdapterError("GATEWAY_TRANSITION_PENDING")
        desired = {"present": True, **target}
        if desired["present"] and desired["running"]:
            self.prerequisites(starting=True)
        configuration = self._configuration(before)
        changed = before["kind"] == "container" and (before.get("compose") != self.profile["compose"] or
            any(configuration.get(key) != target.get(key) for key in ("config_digest", "deployment_digest")))
        actions = []
        if before.get("status") == "running" and (changed or not desired["running"] or not desired["present"]):
            actions.append({"kind": "gateway_stop", "target": self.service, "before": before,
                            "after": {"running": False}, "subeffects": ["stop"], "phase": "quiesced_before_files"})
        if before["kind"] == "container" and (changed or not desired["present"]):
            actions.append({"kind": "gateway_remove", "target": self.service, "before": before,
                            "after": {"present": False}, "subeffects": ["remove"], "phase": "after_stop"})
        if desired["present"] and (before["kind"] == "absent" or changed):
            actions.append({"kind": "gateway_create", "target": self.service, "before": {"kind": "absent", "daemon_id": before["daemon_id"]},
                            "original": before, "after": desired, "subeffects": ["create"], "phase": "after_files"})
        if desired["present"] and desired["running"] and (before.get("status") != "running" or changed):
            actions.append({"kind": "gateway_start", "target": self.service, "before": before,
                            "after": desired, "subeffects": ["start"], "phase": "after_create",
                            "requires_create": any(action['kind'] == 'gateway_create' for action in actions)})
        return [{**action, "compose": self.profile["compose"]} for action in actions]

    def plan_restore(self, original_actions, observations=None, *, creation_observations=()):
        if not original_actions:
            return []
        old = original_actions[0].get("original", original_actions[0]["before"])
        current = self.observe(require_route=False) if observations is None else observations
        if current['kind'] == 'container':
            retained = [action['before'] for action in original_actions if action['before'].get('kind') == 'container']
            retained += [value['observation'] for value in creation_observations
                         if value.get('outcome') == 'target' and value.get('closed') is True
                         and value.get('observation', {}).get('kind') == 'container']
            if not any(value.get('id') == current['id'] and value.get('daemon_id') == current['daemon_id']
                       for value in retained):
                raise AdapterError('RESTORE_GATEWAY_IDENTITY')
        if old["kind"] == "absent":
            return self.plan({"present": False, "running": False}, current)
        if not old.get("compose"):
            raise AdapterError("ORIGINAL_GATEWAY_COMPOSE_REQUIRED")
        configuration = self._configuration(old)
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
               for value in configuration.values()):
            raise AdapterError("ORIGINAL_GATEWAY_CONFIGURATION_BINDING_REQUIRED")
        restored = self._using(old["compose"])
        current = self._retain_original_binding(current, old)
        return restored.plan({"present": True, "running": old["status"] == "running",
                              **configuration}, current)

    def _validate_action(self, action):
        if action.get("kind") not in ("gateway_create", "gateway_start", "gateway_stop", "gateway_remove") or action.get("target") != self.service:
            raise AdapterError("GATEWAY_ACTION_SCOPE")
        if "compose" in action:
            self._validate_compose(action["compose"])

    def _dispatch_identity(self, action, events):
        """Bind one durable dispatch intent to its fixed mutation endpoint."""
        dispatched = [(index, event) for index, event in enumerate(events) if event.get("kind") == "engine_dispatch"]
        if len(dispatched) != 1:
            return False
        index, dispatch = dispatched[0]
        kind = action["kind"]
        if dispatch.get("action") != kind:
            return False
        if kind == "gateway_create":
            identity = {"name": self.name}
            method, path = "POST", "/containers/create?name=" + _quote(self.name)
        else:
            container = dispatch.get("container_id")
            if not isinstance(container, str) or not container:
                return False
            if kind in {"gateway_stop", "gateway_remove"} and container != action["before"]["id"]:
                return False
            identity = {"container_id": container}
            method = "DELETE" if kind == "gateway_remove" else "POST"
            suffix = {"gateway_remove": "?force=false&v=false", "gateway_stop": "/stop?t=10", "gateway_start": "/start"}[kind]
            path = "/containers/" + _quote(container) + suffix
        if any(dispatch.get(key) != value for key, value in identity.items()):
            return False
        return index, identity, method, path

    def _request_not_sent(self, action, events):
        dispatch = self._dispatch_identity(action, events)
        if not dispatch or any(event.get("kind") in {"engine_response", "engine_returned"} for event in events):
            return False
        index, identity, method, path = dispatch
        for event in events[index + 1:]:
            if (event.get("kind") != "engine_not_sent" or event.get("action") != action["kind"]
                    or any(event.get(key) != value for key, value in identity.items())):
                continue
            request = event.get("request")
            if (isinstance(request, dict) and request.get("method") == method and request.get("path") == path
                    and request.get("stage") in {"encoding", "connect"}
                    and isinstance(request.get("error_type"), str) and request["error_type"]
                    and isinstance(request.get("error"), str)):
                return True
        return False

    def _response_closed(self, action, events):
        """Match a saved response to this fixed mutation's preceding dispatch.

        A completed failed request may have partial effects. Their identity and
        readiness are still decided by inspect, never by this transport receipt.
        Old successful engine_returned events remain valid completion evidence.
        """
        dispatch = self._dispatch_identity(action, events)
        if not dispatch:
            return False
        index, identity, method, path = dispatch
        kind = action["kind"]
        for event in events[index + 1:]:
            if event.get("action") != kind:
                continue
            if event.get("kind") == "engine_returned":
                returned = event.get("container_id")
                if isinstance(returned, str) and returned and (kind == "gateway_create" or returned == identity["container_id"]):
                    return True
            if event.get("kind") != "engine_response" or any(event.get(key) != value for key, value in identity.items()):
                continue
            reply = event.get("response", {})
            if (isinstance(reply, dict) and reply.get("method") == method and reply.get("path") == path
                    and type(reply.get("status")) is int and 300 <= reply["status"] <= 599
                    and type(reply.get("bytes")) is int and 0 <= reply["bytes"] <= getattr(self.engine, "maximum", 1048576)
                    and isinstance(reply.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", reply["sha256"])):
                return True
        return False

    def creation_identity(self, action, previous, *, observation=None, lock_fd=None):
        """Recover a fixed creation ID from retained evidence, never a new inspect."""
        if not previous or action.get('kind') != 'gateway_create':
            return None
        binding = previous.get('binding', previous)
        if binding.get('action_digest') != digest({**action, 'attempt_id': binding['attempt_id']}):
            raise AdapterError('GATEWAY_ATTEMPT_BINDING_CONFLICT')
        retained = previous.get('effect_identity')
        if retained is not None and (set(retained) != {'daemon_id', 'container_id', 'attempt_id'}
                or retained['daemon_id'] != self.profile['daemon_id']
                or retained['attempt_id'] != binding['attempt_id']
                or not isinstance(retained['container_id'], str) or not retained['container_id']):
            raise AdapterError('GATEWAY_EFFECT_IDENTITY_CONFLICT')
        saved = observation or {}
        supervised = saved.get('supervision')
        if not isinstance(supervised, dict) or supervised.get('binding') != binding:
            supervised = self.runner.observe(binding, lock_fd=lock_fd)
        ids = set()
        events = supervised.get('events', [])
        if supervised.get('closed') and self._dispatch_identity(action, events):
            ids.update(event['container_id'] for event in events
                if event.get('kind') == 'engine_returned' and event.get('action') == 'gateway_create'
                and isinstance(event.get('container_id'), str) and event['container_id'])
            result = supervised.get('result') or {}
            returned = result.get('value') if result.get('status') == 'returned' else None
            if isinstance(returned, dict) and isinstance(returned.get('container_id'), str) and returned['container_id']:
                ids.add(returned['container_id'])
            value = saved.get('observation') or {}
            if (saved.get('state', saved.get('outcome')) == 'target' and saved.get('closed') is True
                    and saved.get('supervision', {}).get('binding') == binding
                    and value.get('kind') == 'container' and value.get('daemon_id') == self.profile['daemon_id']
                    and value.get('labels', {}).get('local-hand.deploy.attempt') == binding['attempt_id']
                    and all(self._configuration(value).get(key) == action['after'].get(key)
                            for key in ('config_digest', 'deployment_digest'))):
                ids.add(value['id'])
        if retained is not None:
            ids.add(retained['container_id'])
        if len(ids) > 1:
            raise AdapterError('GATEWAY_EFFECT_IDENTITY_CONFLICT')
        return ({'daemon_id': self.profile['daemon_id'], 'container_id': next(iter(ids)),
                 'attempt_id': binding['attempt_id']} if ids else None)

    def _start_identity(self, action, expected):
        if expected is not None:
            if (expected.get('daemon_id') != self.profile['daemon_id']
                    or not isinstance(expected.get('container_id'), str) or not expected['container_id']):
                raise AdapterError('GATEWAY_START_IDENTITY_REQUIRED')
            return expected['container_id']
        before = action['before']
        if (action.get('requires_create') or before.get('kind') != 'container'
                or before.get('compose') != action.get('compose', self.profile['compose'])
                or any(self._configuration(before).get(key) != action['after'].get(key)
                       for key in ('config_digest', 'deployment_digest'))):
            return None
        return before['id']

    def observe_action(self, action, previous=None, *, lock_fd=None, require_route=None, expected_identity=None):
        self._validate_action(action)
        adapter = self._using(action.get("compose", self.profile["compose"]))
        if adapter is not self:
            return adapter.observe_action(action, previous, lock_fd=lock_fd, require_route=require_route,
                                          expected_identity=expected_identity)
        binding = previous.get('binding', previous) if previous else None
        if binding and binding.get('action_digest') != digest({**action, 'attempt_id': binding['attempt_id']}):
            raise AdapterError('GATEWAY_ATTEMPT_BINDING_CONFLICT')
        supervised = self.runner.observe(previous.get("binding", previous), lock_fd=lock_fd) if previous else None
        if supervised and not supervised["closed"]:
            return {"outcome": "running", "closed": False, "postcondition": False, "supervision": supervised,
                    "dispatched": None}
        kind = action["kind"]
        value = self._retain_original_binding(self.observe(require_route=False), action["before"])
        start_id = self._start_identity(action, expected_identity) if kind == 'gateway_start' else None
        if (kind == 'gateway_start' and require_route is not False and value.get('status') == 'running'
                and value.get('id') == start_id and self.route_probe is not None):
            try:
                value['route'] = self.route_probe(value['id'])
            except (OSError, RuntimeError, ValueError) as error:
                # Readiness failure cannot strand an otherwise closed original
                # Engine call and prevent stopping its exactly bound container.
                value['route'] = None
                value['route_error'] = {'error_type': type(error).__name__, 'error': str(error)[:512]}
        result = supervised and supervised.get("result") or {}
        events = supervised["events"] if supervised else []
        dispatch_recorded = supervised and any(event.get("kind") == "engine_dispatch" for event in events)
        not_sent = self._request_not_sent(action, events)
        completed = (previous is None or result.get("status") == "returned" or not dispatch_recorded
                     or not_sent or self._response_closed(action, events))
        # Engine stop/start/create may outlive a broken HTTP request. Exact
        # matching container/attempt effects are adoptable; original values alone
        # are never a retry proof following an unknown response.
        created = set()
        fixed_identity = self.creation_identity(action, previous, lock_fd=lock_fd) if kind == 'gateway_create' else None
        if fixed_identity:
            created.add(fixed_identity['container_id'])
        if kind == 'gateway_create' and self._dispatch_identity(action, events):
            created.update(event['container_id'] for event in events
                           if event.get('kind') == 'engine_returned' and event.get('action') == kind
                           and isinstance(event.get('container_id'), str) and event['container_id'])
            returned = result.get('value') if result.get('status') == 'returned' else None
            if isinstance(returned, dict) and isinstance(returned.get('container_id'), str) and returned['container_id']:
                created.add(returned['container_id'])
        if kind == "gateway_remove":
            target = value["kind"] == "absent"
        elif kind == "gateway_stop":
            target = value["kind"] == "container" and value["id"] == action["before"]["id"] and value["status"] == "stopped"
        else:
            labels = value.get("labels", {})
            target = value["kind"] == "container" and all(self._configuration(value).get(key) == action["after"].get(key)
                for key in ("config_digest", "deployment_digest"))
            if kind == "gateway_create":
                target = (target and binding is not None and not not_sent and bool(self._dispatch_identity(action, events))
                          and labels.get("local-hand.deploy.attempt") == binding['attempt_id']
                          and (not previous.get('effect_identity_required') or fixed_identity is not None)
                          and (not created or created == {value['id']}))
            if kind == "gateway_start":
                route = value.get("route") or {}
                target = (target and start_id is not None and value.get('id') == start_id
                          and value.get("status") == "running" and route.get("container_id") == value["id"]
                          and route.get("config_digest") == action["after"]["config_digest"] and route.get("protocol_ready") is True)
        # Losing a live status endpoint must not prevent stopping the exact
        # frozen container. Engine identity/config remain fully checked above;
        # readiness is required for start and final commit, not for isolation.
        def frozen(observation):
            normalized = dict(observation)
            # Docker inspect may enumerate the same mounts in another order.
            # Compare the full multiset, including propagation/mode and duplicate
            # entries; neither discard fields nor rewrite retained observations.
            if "mounts" in normalized:
                normalized["mounts"] = sorted(normalized["mounts"], key=lambda mount:
                    json.dumps(mount, sort_keys=True, separators=(",", ":"), allow_nan=False))
            if kind in {"gateway_stop", "gateway_remove"}:
                normalized.update(self._configuration(observation))
                normalized.pop("route", None)
            return normalized
        original = frozen(value) == frozen(action["before"])
        # An acknowledged fixed Engine operation is synchronous at this API
        # boundary. Lost response may be adopted ONLY for its exact target; no
        # retry against original/absent state without daemon-side completion proof.
        closed = completed or target
        outcome = ("target" if target and closed else "unknown" if not closed else "original" if original
                   else "conflict" if kind == 'gateway_create' or kind == 'gateway_start' and value.get('id') != start_id
                   else "partial" if value.get("status") == "stopped" else "conflict")
        observed = {"outcome": outcome, "postcondition": target and closed, "closed": closed,
                "observation": value, "supervision": supervised,
                "proof": "satisfied_observed" if target and not completed else "observed",
                **({'effective': bool(created) or target} if kind == 'gateway_create' else {}),
                "dispatched": bool(dispatch_recorded and not not_sent)}
        if kind == 'gateway_create' and target:
            observed['effect_identity'] = self.creation_identity(action, previous, observation=observed, lock_fd=lock_fd)
        return observed

    def execute(self, action, *, attempt_id, lock_fd, persist_intent, previous=None, expected_identity=None):
        self._validate_action(action)
        adapter = self._using(action.get("compose", self.profile["compose"]))
        if adapter is not self:
            return adapter.execute(action, attempt_id=attempt_id, lock_fd=lock_fd, persist_intent=persist_intent,
                                   previous=previous, expected_identity=expected_identity)
        verify_lock(lock_fd)
        observed = self.observe_action(action, previous, lock_fd=lock_fd, expected_identity=expected_identity)
        if observed["postcondition"] or not observed["closed"]:
            return observed
        if observed["outcome"] == "conflict":
            error = AdapterError("GATEWAY_OBSERVATION_CONFLICT")
            # Private callers may retain the actual conflicting read. A later
            # probe can differ again and cannot explain this refusal reliably.
            error.observation = observed["observation"]
            raise error
        if previous is not None and previous.get("binding", previous).get("attempt_id") == attempt_id:
            return observed
        if action["kind"] in ("gateway_create", "gateway_start"):
            if self.guard_check is None:
                raise AdapterError("GATEWAY_STARTUP_GUARD_REQUIRED")
            validate_guard(self.guard_check(self.service, {**action["after"], "attempt_id": attempt_id}), action["after"],
                           attempt_id=attempt_id, allow_stopped=action["kind"] == "gateway_create")
        self.prerequisites(starting=action["kind"] == "gateway_start")
        augmented = {**action, "attempt_id": attempt_id}
        perform = lambda command, emit: self._perform(command, emit, expected_identity=expected_identity)
        outcome = self.runner.run(augmented, perform, attempt_id=attempt_id, lock_fd=lock_fd,
                                  persist_intent=persist_intent)
        observed = self.observe_action(action, outcome, lock_fd=lock_fd, expected_identity=expected_identity)
        if observed.get('effect_identity'):
            outcome['effect_identity'] = observed['effect_identity']
        return {**observed, "attempt": outcome}

    def _create_body(self, target, attempt_id):
        source = self.profile["compose"]["services"][self.service]
        ports, bindings = {}, {}
        for port in source.get("ports", []):
            key = str(port["target"]) + "/tcp"
            ports[key] = {}
            bindings.setdefault(key, []).append({"HostIp": port.get("host_ip", ""), "HostPort": str(port["published"])})
        labels = {**source.get("labels", {}), "com.docker.compose.project": self.project,
                  "com.docker.compose.service": self.service, "com.docker.compose.oneoff": "False",
                  "local-hand.deploy.config": target["config_digest"], "local-hand.deploy.deployment": target["deployment_digest"],
                  "local-hand.deploy.attempt": attempt_id}
        mounts = [{"Type": "bind", "Source": m["source"], "Target": m["target"], "ReadOnly": True,
                   "BindOptions": {"CreateMountpoint": False}} for m in source.get("volumes", [])]
        endpoints = {self.profile["compose"]["networks"][logical].get("name", logical): {} for logical in source.get("networks", {})}
        body = {"Image": source["image"], "Labels": labels, "Env": [str(k) + "=" + str(v) for k, v in sorted(source.get("environment", {}).items())],
                "ExposedPorts": ports,
                "HostConfig": {"Mounts": mounts, "PortBindings": bindings, "ReadonlyRootfs": source.get("read_only", False),
                               "RestartPolicy": {"Name": source.get("restart", "no")}, "AutoRemove": False,
                               "CapDrop": source.get("cap_drop", []), "SecurityOpt": source.get("security_opt", []),
                               "NetworkMode": next(iter(endpoints), "none"), **_resource_config(source)},
                "NetworkingConfig": {"EndpointsConfig": endpoints}}
        for source_key, destination in (("entrypoint", "Entrypoint"), ("command", "Cmd"), ("user", "User")):
            if source_key in source:
                body[destination] = source[source_key]
        return body

    def _perform(self, action, emit, *, expected_identity=None):
        self._validate_action(action)
        adapter = self._using(action.get("compose", self.profile["compose"]))
        if adapter is not self:
            return adapter._perform(action, emit, expected_identity=expected_identity)
        self.prerequisites(starting=action["kind"] == "gateway_start")
        kind = action["kind"]
        value = self.observe(require_route=kind not in {"gateway_stop", "gateway_remove"})
        if kind == "gateway_create":
            if value["kind"] != "absent":
                raise AdapterError("GATEWAY_CREATE_TARGET_OCCUPIED")
            created = self._mutate(kind, {"name": self.name}, "POST", "/containers/create?name=" + _quote(self.name), emit,
                                   self._create_body(action["after"], action["attempt_id"]))
            emit({"kind": "engine_returned", "action": kind, "container_id": created["Id"]})
            return {"container_id": created["Id"]}
        if value["kind"] != "container":
            raise AdapterError("GATEWAY_CONTAINER_MISSING")
        if kind in ("gateway_stop", "gateway_remove") and value["id"] != action["before"]["id"]:
            raise AdapterError("GATEWAY_CONTAINER_ID_CHANGED")
        if kind == 'gateway_start' and value['id'] != self._start_identity(action, expected_identity):
            raise AdapterError('GATEWAY_CONTAINER_ID_CHANGED')
        if kind == "gateway_remove" and value["status"] != "stopped":
            raise AdapterError("GATEWAY_REMOVE_REQUIRES_STOPPED")
        path = "/containers/" + _quote(value["id"])
        if kind == "gateway_remove":
            self._mutate(kind, {"container_id": value["id"]}, "DELETE", path + "?force=false&v=false", emit)
        elif kind == "gateway_stop":
            self._mutate(kind, {"container_id": value["id"]}, "POST", path + "/stop?t=10", emit)
        else:
            self._mutate(kind, {"container_id": value["id"]}, "POST", path + "/start", emit)
        emit({"kind": "engine_returned", "action": kind, "container_id": value["id"]})
        return {"container_id": value["id"]}

    def _mutate(self, kind, identity, method, path, emit, body=None):
        emit({"kind": "engine_dispatch", "action": kind, **identity})
        try:
            return self.engine.request(method, path, body)
        except DockerRequestNotSent as error:
            # A saved dispatch intent is not proof of delivery. Only the fixed
            # encoder/connect boundaries can prove no request bytes were sent;
            # later send/read failures still retain the original unknown call.
            try:
                emit({"kind": "engine_not_sent", "action": kind, **identity, "request": error.request})
            except Exception as recording_error:
                raise AdapterError(f"{error}; PROOF_RECORD_FAILED:{type(recording_error).__name__}") from error
            raise
        except DockerHTTPError as error:
            # Only a full response from this mutation supplies a completion
            # receipt. Connection loss, timeout, truncation and oversized replies
            # do not enter this branch. Preserve failures as failures.
            try:
                emit({"kind": "engine_response", "action": kind, **identity, "response": error.response})
            except Exception as recording_error:
                raise AdapterError(f"{error}; RESPONSE_RECORD_FAILED:{type(recording_error).__name__}") from error
            raise
