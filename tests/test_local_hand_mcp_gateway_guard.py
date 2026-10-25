"""Fixed gateway grammar/build checks and real bounded loopback relay traffic.

These tests do not claim a real nginx/Docker platform acceptance. No container,
existing service, daemon or public interface is modified.
"""
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock
import zipfile

from admin.build_gateway_image import prepare
from local_hand_jobs.contract import JobError
from local_hand_mcp import gateway_guard as guard

ROOT = Path(__file__).resolve().parents[1]
NGINX = (ROOT / "containers/gateway/nginx.conf.example").read_bytes()


def config():
    return {"schema": guard.SCHEMA, "node_id": "fixture", "deployment_digest": "a" * 64,
            "payload_digest": "b" * 64, "manager_socket": "/run/fixture-manager.sock",
            "nginx_config": "/etc/local-hand/nginx.conf", "public_port": 18080,
            "upstream_port": 18081, "status_socket": "/run/local-hand-gateway/status.sock"}


class ConfigurationTests(unittest.TestCase):
    def test_example_is_a_complete_fixed_gateway(self):
        self.assertEqual(NGINX, guard.validate_nginx(NGINX, 18081))
        self.assertEqual(config(), guard.validate_config(config()))

    def test_exact_schema_and_listener_scope(self):
        for update in ({"extra": True}, {"public_port": True}, {"upstream_port": 18080},
                       {"status_socket": "/tmp/status.sock"}, {"nginx_config": "/etc/../nginx.conf"},
                       {"manager_socket": "/run//socket"}, {"payload_digest": "unknown"}):
            with self.subTest(update=update), self.assertRaises(JobError):
                guard.validate_config({**config(), **update})

    def test_binding_uses_selected_bytes_and_preserves_logical_path(self):
        seen = []
        def read(path):
            seen.append(path)
            return NGINX
        binding = guard.configuration_binding(config(), read=read)
        self.assertEqual([config()["nginx_config"]], seen)
        self.assertEqual({"path": config()["nginx_config"], "sha256": hashlib.sha256(NGINX).hexdigest()},
                         binding["inputs"]["nginx_config"])
        changed = guard.configuration_binding(config(), read=lambda _: NGINX + b"\n# selected revision\n")
        self.assertNotEqual(binding, changed)

    def test_external_configuration_and_extra_listeners_are_rejected(self):
        cases = [
            b"include /etc/nginx/*.conf;\n" + NGINX,
            b"load_module /tmp/module.so;\n" + NGINX,
            NGINX.replace(b"listen 127.0.0.1:18081;", b"listen 0.0.0.0:18081;"),
            NGINX.replace(b"server_name _;", b"server_name _; listen 127.0.0.1:18082;"),
            # An implicit nginx server listener is also forbidden.
            NGINX.replace(b"http {", b"http { server { location / { return 404; } }"),
            NGINX.replace(b"location / { return 404; }", b"location = / { return 404; }"),
            NGINX.replace(b"location / { return 404; }", b"location / { return 404; proxy_pass http://mcp; }"),
            NGINX.replace(b"server_name _;", b"server_name _; ssl_certificate /tmp/key;"),
            NGINX.replace(b"server_name _;", b"server_name _; root /etc;"),
            NGINX.replace(b"server_name _;", b"server_name _; alias /etc;"),
            NGINX.replace(b"error_log stderr warn;", b"error_log /tmp/log warn;"),
            NGINX.replace(b"access_log off;", b"access_log /tmp/log;"),
            NGINX.replace(b"identity:8080", b"identity:65536"),
        ]
        for raw in cases:
            with self.subTest(raw=raw[:120]), self.assertRaises(JobError):
                guard.validate_nginx(raw, 18081)

    def test_configuration_size_and_proxy_timeout_are_bounded(self):
        for raw in (b"#" * (256 * 1024 + 1), NGINX.replace(b"300s", b"301s"),
                    NGINX.replace(b"worker_connections 128", b"worker_connections 2048")):
            with self.assertRaises(JobError): guard.validate_nginx(raw, 18081)

    def test_host_process_cannot_impersonate_container_pid_one(self):
        with self.assertRaisesRegex(JobError, "root container PID 1"):
            guard.serve("/path/never/read")


class RelayFixture:
    def __init__(self, **options):
        self.backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.backend.bind(("127.0.0.1", 0)); self.backend.listen(4); self.backend.settimeout(.1)
        self.stop = threading.Event()
        self.clients, self.errors = [], []
        self.relay = guard.Relay(self.backend.getsockname()[1], **options)
        self.relay.bind(0, address="127.0.0.1"); self.relay.renew()
        self.port = self.relay.listener.getsockname()[1]
        self.server = threading.Thread(target=self.echo, daemon=True)
        self.pump = threading.Thread(target=self.accept, daemon=True)
        self.server.start(); self.pump.start()

    def echo(self):
        try:
            while not self.stop.is_set():
                try: client, _ = self.backend.accept()
                except socket.timeout: continue
                with client:
                    client.settimeout(2)
                    while not self.stop.is_set():
                        data = client.recv(8192)
                        if not data: break
                        client.sendall(data)
        except OSError:
            if not self.stop.is_set(): self.errors.append("backend socket failed")

    def accept(self):
        try:
            while not self.stop.wait(.005): self.relay.accept()
        except OSError:
            if not self.stop.is_set(): self.errors.append("relay accept failed")

    def connect(self):
        client = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        self.clients.append(client)
        return client

    def close(self):
        self.stop.set(); self.pump.join(timeout=2)
        self.relay.close_public()
        for client in self.clients: client.close()
        self.backend.close(); self.server.join(timeout=3)
        with self.relay.lock: threads = list(self.relay.threads)
        for thread in threads: thread.join(timeout=3)
        if self.server.is_alive() or self.pump.is_alive() or any(t.is_alive() for t in threads):
            raise AssertionError("fixture left a running thread")


class RelayTests(unittest.TestCase):
    def setUp(self): self.fixture = None
    def tearDown(self):
        if self.fixture:
            self.fixture.close()
            self.assertEqual([], self.fixture.errors)

    def test_real_bytes_cross_both_directions_and_half_close(self):
        self.fixture = RelayFixture()
        client = self.fixture.connect()
        sent = b"fixed gateway relay\n" * 10000
        client.sendall(sent); client.shutdown(socket.SHUT_WR)
        actual = bytearray()
        while True:
            chunk = client.recv(65536)
            if not chunk: break
            actual.extend(chunk)
        self.assertEqual(sent, actual)

    def test_revocation_closes_existing_connection(self):
        self.fixture = RelayFixture()
        client = self.fixture.connect(); client.sendall(b"before")
        self.assertEqual(b"before", client.recv(1024))
        self.fixture.relay.close_public()
        self.assertEqual(b"", client.recv(1024))
        self.assertIsNone(self.fixture.relay.listener)

    def test_expired_permission_never_forwards_new_connection(self):
        self.fixture = RelayFixture()
        self.fixture.relay.allowed_until = time.monotonic() - 1
        client = self.fixture.connect()
        self.assertEqual(b"", client.recv(1024))

    def test_connection_limit_closes_excess_connection(self):
        self.fixture = RelayFixture(maximum=1)
        first = self.fixture.connect(); first.sendall(b"occupied")
        self.assertEqual(b"occupied", first.recv(1024))
        excess = self.fixture.connect()
        self.assertEqual(b"", excess.recv(1024))
        first.sendall(b"retained")
        self.assertEqual(b"retained", first.recv(1024))

    def test_idle_connection_has_bounded_lifetime(self):
        self.fixture = RelayFixture(idle=.15)
        client = self.fixture.connect(); client.sendall(b"initial")
        self.assertEqual(b"initial", client.recv(1024))
        self.assertEqual(b"", client.recv(1024))


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.wheel = self.root / "infra_local_hand-0.2.0a1-py3-none-any.whl"
        with zipfile.ZipFile(self.wheel, "w") as archive:
            for package in ("local_hand", "local_hand_connect", "local_hand_jobs", "local_hand_mcp"):
                archive.writestr(package + "/__init__.py", "")
            archive.writestr("local_hand_mcp/gateway_guard.py", "# build fixture only\n")
        self.base = "nginx@sha256:" + "1" * 64
    def tearDown(self): self.temp.cleanup()

    def test_context_preparation_is_daemon_free_and_binds_exact_wheel(self):
        with mock.patch("subprocess.run", side_effect=AssertionError("daemon access")):
            result = prepare(self.wheel, self.base, self.root / "context")
        self.assertEqual(hashlib.sha256(self.wheel.read_bytes()).hexdigest(), result["wheel_sha256"])
        self.assertEqual(self.wheel.read_bytes(), (self.root / "context/wheels" / self.wheel.name).read_bytes())
        self.assertEqual(result, json.loads((self.root / "context/build-inputs.json").read_text()))
        self.assertIn(b"local_hand_mcp.gateway_guard", (self.root / "context/Dockerfile").read_bytes())

    def test_unpinned_base_or_missing_guard_are_rejected_before_context(self):
        with self.assertRaises(ValueError): prepare(self.wheel, "nginx:alpine", self.root / "no-base")
        self.assertFalse((self.root / "no-base").exists())
        with zipfile.ZipFile(self.wheel, "w") as archive: archive.writestr("local_hand/__init__.py", "")
        with self.assertRaises(ValueError): prepare(self.wheel, self.base, self.root / "no-guard")
        self.assertFalse((self.root / "no-guard").exists())

    def test_existing_context_is_never_overwritten(self):
        output = self.root / "existing"; output.mkdir(); (output / "original").write_text("keep")
        with self.assertRaises(FileExistsError): prepare(self.wheel, self.base, output)
        self.assertEqual("keep", (output / "original").read_text())


if __name__ == "__main__": unittest.main()
