"""Host/container proof boundaries; Engine and namespace facts are modeled.

These tests do not claim a real Docker lifecycle or namespace acceptance run.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from admin.local_hand_deploy.model import DeployError
from admin.local_hand_deploy.runtime import PlanningEnvironment
from local_hand_jobs import startup


class GatewayProbeTests(unittest.TestCase):
    def setUp(self):
        self.container_id = "c" * 64
        self.identity = {"pid": 12001, "start_ticks": "8000", "boot_id": "boot"}
        self.environment = PlanningEnvironment({"probes": {"gateway": {
            "kind": "gateway", "socket": "/run/local-hand/status.sock", "peer_uid": 0}},
            "gateway": {"component": "gateway"}})
        self.engine = MagicMock()
        self.environment._gateway = SimpleNamespace(engine=self.engine, profile={"daemon_id": "daemon"},
                                                    project="fixture", service="gateway", name="fixture-gateway")
        self.container = {"Id": self.container_id, "State": {"Running": True, "Pid": 12001},
                          "Config": {"Labels": {"com.docker.compose.project": "fixture",
                                                 "com.docker.compose.service": "gateway"}}}
        self.engine.request.side_effect = lambda _, path: ({"ID": "daemon"} if path == "/info" else self.container)
        self.selected = {"container_id": self.container_id, "instance": self.identity}
        self.loaded = {**self.identity, "component": "gateway", "namespace_pid": 1,
                       "protocol_ready": True, "public_ready": False, "container_id": "forged"}

    def instance(self, status="NSpid:\t12001\t1\n", same_namespace=False):
        def stat(path):
            return SimpleNamespace(st_ino=1 if same_namespace or "/self/" in path else 2)
        with patch("admin.local_hand_deploy.runtime.startup.instance", return_value=self.identity), \
             patch.object(Path, "read_text", return_value=status), \
             patch("admin.local_hand_deploy.runtime.os.stat", side_effect=stat):
            return self.environment._gateway_instance()

    def test_engine_pid_and_private_namespace_are_the_identity_source(self):
        self.assertEqual(self.selected, self.instance())

    def test_stopped_restarting_foreign_or_host_namespace_has_no_live_proof(self):
        for field in ("Paused", "Restarting", "Dead"):
            with self.subTest(field=field):
                self.container["State"][field] = True
                with self.assertRaises(DeployError):
                    self.instance()
                del self.container["State"][field]
        self.container["State"]["Running"] = False
        with self.assertRaises(DeployError):
            self.instance()
        self.container["State"]["Running"] = True
        with self.assertRaises(DeployError):
            self.instance(same_namespace=True)
        with self.assertRaises(DeployError):
            self.instance(status="NSpid:\t12001\t2\n")
        self.container["Config"]["Labels"]["com.docker.compose.project"] = "other"
        with self.assertRaises(DeployError):
            self.instance()

    def probe(self, *, peer=None, loaded=None, second=None):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.getsockopt.return_value = struct.pack("3i", *(peer or (12001, 0, 0)))
        response = json.dumps({"result": loaded or self.loaded}).encode()
        with patch.object(self.environment, "_gateway_instance", side_effect=[self.selected, second or self.selected]), \
             patch("admin.local_hand_deploy.runtime.socket.socket", return_value=connection), \
             patch("admin.local_hand_deploy.runtime.cli._send_frame"), \
             patch("admin.local_hand_deploy.runtime.cli._read_frame", return_value=response):
            result = self.environment._probe("gateway")
        connection.connect.assert_called_once_with("/proc/12001/root/run/local-hand/status.sock")
        return result

    def test_probe_derives_container_id_from_engine_and_allows_local_candidate(self):
        result = self.probe()["loaded"]
        self.assertEqual(self.container_id, result["container_id"])
        self.assertFalse(result["public_ready"])

    def test_probe_rejects_another_process_or_nonroot_peer(self):
        for peer in ((12002, 0, 0), (12001, 1000, 1000)):
            with self.subTest(peer=peer), self.assertRaises(DeployError):
                self.probe(peer=peer)

    def test_stale_or_namespace_local_identity_cannot_claim_host_identity(self):
        for key, value in (("pid", 1), ("start_ticks", "7999"), ("boot_id", "old"),
                           ("namespace_pid", 2), ("protocol_ready", False), ("public_ready", "yes")):
            with self.subTest(key=key), self.assertRaises(DeployError):
                self.probe(loaded={**self.loaded, key: value})
        changed = copy.deepcopy(self.selected)
        changed["instance"]["start_ticks"] = "9000"
        with self.assertRaises(DeployError):
            self.probe(second=changed)

    def test_different_container_path_cannot_substitute_selected_input(self):
        config = {"public_port": 8080, "nginx_config": "/config/nginx.conf", "manager_socket": "/manager/status.sock"}
        service = {"entrypoint": ["/opt/local-hand/gateway/bin/python", "-B", "-m", "local_hand_mcp.gateway_guard"],
                   "command": ["--config", "/config/guard.json"], "user": "0:0",
                   "ports": [{"target": 8080}], "volumes": [
            {"source": "/config", "target": "/config", "read_only": True},
            {"source": "/manager", "target": "/manager", "read_only": True}]}
        self.environment.profile["gateway"].update(service="gateway", compose={"services": {"gateway": service}})
        self.environment._gateway_input_mounts(config, "/config/guard.json")
        service["volumes"][0]["source"] = "/another-config"
        with self.assertRaises(DeployError):
            self.environment._gateway_input_mounts(config, "/config/guard.json")

        service["volumes"][0]["source"] = "/config"
        service["volumes"][0]["read_only"] = False
        with self.assertRaises(DeployError):
            self.environment._gateway_input_mounts(config, "/config/guard.json")
        service["volumes"][0]["read_only"] = True
        service["volumes"].append({"source": "/other/nginx.conf", "target": "/config/nginx.conf", "read_only": True})
        with self.assertRaises(DeployError):
            self.environment._gateway_input_mounts(config, "/config/guard.json")
        service["volumes"][-1]["source"] = "/config/nginx.conf"
        # A direct file bind pins the old inode across atomic publication.
        with self.assertRaises(DeployError):
            self.environment._gateway_input_mounts(config, "/config/guard.json")
        service["volumes"].pop()
        self.environment._gateway_input_mounts(config, "/config/guard.json")
        service["volumes"].append(copy.deepcopy(service["volumes"][-1]))
        with self.assertRaises(DeployError):
            self.environment._gateway_input_mounts(config, "/config/guard.json")

    def test_manager_socket_binding_follows_recreated_directory_entry(self):
        config = {"public_port": 8080, "nginx_config": "/config/nginx.conf", "manager_socket": "/config/manager.sock"}
        service = {"entrypoint": ["/opt/local-hand/gateway/bin/python", "-B", "-m", "local_hand_mcp.gateway_guard"],
                   "command": ["--config", "/config/guard.json"], "user": "0:0", "ports": [{"target": 8080}],
                   "volumes": [{"source": "/config", "target": "/config", "read_only": True}]}
        self.environment.profile["gateway"].update(service="gateway", compose={"services": {"gateway": service}})
        self.environment._gateway_input_mounts(config, "/config/guard.json")
        service["volumes"].append({"source": "/config/manager.sock", "target": "/config/manager.sock", "read_only": True})
        with self.assertRaises(DeployError):
            self.environment._gateway_input_mounts(config, "/config/guard.json")

    def test_original_compose_cannot_hide_an_invalid_selected_target(self):
        config = {"public_port": 8080, "nginx_config": "/config/nginx.conf", "manager_socket": "/config/manager.sock"}
        service = {"entrypoint": ["/opt/local-hand/gateway/bin/python", "-B", "-m", "local_hand_mcp.gateway_guard"],
                   "command": ["--config", "/config/guard.json"], "user": "0:0", "ports": [{"target": 8080}],
                   "volumes": [{"source": "/config", "target": "/config", "read_only": True}]}
        original = {"services": {"gateway": service}}
        target = copy.deepcopy(original)
        target["services"]["gateway"]["entrypoint"] = ["unprotected-entry"]
        self.environment.profile["gateway"].update(service="gateway", compose=target, original_compose=original)
        with self.assertRaises(DeployError):
            self.environment._gateway_input_mounts(config, "/config/guard.json")
        self.environment._gateway_input_mounts(config, "/config/guard.json", compose=original)


class GatewayConfigurationTests(unittest.TestCase):
    def setUp(self):
        from local_hand_mcp.gateway_guard import configuration_binding
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.nginx = self.root / "nginx.conf"
        self.guard = self.root / "guard.json"
        self.nginx.write_text("worker_processes 1; error_log stderr; events { worker_connections 32; } "
                              "http { access_log off; server { listen 127.0.0.1:8081; server_name _; "
                              "location / { return 404; } } }")
        self.nginx.chmod(0o600)
        self.config = {"schema": "local-hand-gateway-startup/v1", "node_id": "node",
                       "deployment_digest": "a" * 64, "payload_digest": "b" * 64,
                       "manager_socket": str(self.root / "manager.sock"), "nginx_config": str(self.nginx),
                       "public_port": 8080, "upstream_port": 8081,
                       "status_socket": "/run/local-hand-gateway/status.sock"}
        self.guard.write_bytes(startup.canonical(self.config)); self.guard.chmod(0o600)
        self.selection = {"node_id": "node", "deployment_digest": "a" * 64,
                          "components": {"gateway": {"payload_digest": "b" * 64,
                              "configuration_digest": startup.digest(configuration_binding(self.config))}},
                          "members": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                                      for path in (self.nginx, self.guard)]}
        self.profile = {"owner_uid": os.geteuid(), "guarded_components": {
            "gateway": {"configuration": str(self.guard)}}, "probes": {
            "manager": {"kind": "resident", "socket": str(self.root / "manager.sock")},
            "gateway": {"kind": "gateway", "socket": self.config["status_socket"]}},
            "gateway": {"service": "gateway", "compose": {"services": {"gateway": {
                "entrypoint": ["/opt/local-hand/gateway/bin/python", "-B", "-m", "local_hand_mcp.gateway_guard"],
                "command": ["--config", str(self.guard)], "user": "0:0",
                "ports": [{"target": 8080}], "volumes": [{"source": str(self.root),
                    "target": str(self.root), "read_only": True}]}}}}}
        self.environment = PlanningEnvironment(self.profile)

    def test_complete_gateway_input_set_and_actual_binding_are_verified(self):
        self.environment._verify_components(self.selection)
        self.selection["members"] = [member for member in self.selection["members"] if member["path"] != str(self.nginx)]
        with self.assertRaisesRegex(DeployError, "outside the complete selection"):
            self.environment._verify_components(self.selection)

    def test_candidate_bytes_are_bound_to_logical_input_path(self):
        candidate = self.root / "candidate.conf"
        candidate.write_text(self.nginx.read_text().replace("return 404", "return 403")); candidate.chmod(0o600)
        with self.assertRaisesRegex(DeployError, "differs from selection"):
            self.environment._verify_components(self.selection, {str(self.nginx): str(candidate)})

    def test_probe_endpoint_cannot_be_substituted_after_selection(self):
        self.profile["probes"]["gateway"]["socket"] = "/run/local-hand-gateway/other.sock"
        with self.assertRaisesRegex(DeployError, "guarded startup selection"):
            self.environment._verify_components(self.selection)

    def test_running_gateway_cannot_wait_on_a_stopped_or_missing_manager(self):
        self.selection["components"]["gateway"]["running"] = True
        with self.assertRaisesRegex(DeployError, "running startup manager"):
            self.environment._verify_components(self.selection)
        self.selection["components"]["manager"] = {"running": False}
        with self.assertRaisesRegex(DeployError, "running startup manager"):
            self.environment._verify_components(self.selection)
        self.selection["components"]["manager"]["running"] = True
        self.environment._verify_components(self.selection)
