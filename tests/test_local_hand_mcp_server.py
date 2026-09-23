"""Real SDK/ASGI integration against a synthetic signed issuer and local broker."""
from __future__ import annotations

import asyncio
from functools import partial
import importlib.util
import io
import json
from pathlib import Path
import sys
import socket
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_hand_jobs.contract import JobError, Principal, TOOL_SCHEMAS
from local_hand_mcp.server import create_app, main
from test_local_hand_mcp_auth import HAS_EXTRA, SyntheticIssuer


class ASGIClient:
    """Use current AnyIO portal API without Starlette's deprecated test alias."""
    def __init__(self, app, base_url):
        self.app, self.base_url = app, base_url

    async def _serve(self, *, task_status):
        import httpx2
        self.stop = asyncio.Event()
        # SDK lifespan enters an AnyIO task group, so entry and exit must remain
        # in this same owner task, independently of individual HTTP calls.
        async with self.app.router.lifespan_context(self.app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=self.app), base_url=self.base_url) as client:
                task_status.started(client)
                await self.stop.wait()

    def __enter__(self):
        from anyio.from_thread import start_blocking_portal
        self.portal_manager = start_blocking_portal()
        self.portal = self.portal_manager.__enter__()
        self.future, self.client = self.portal.start_task(self._serve)
        return self

    def __exit__(self, *exc):
        try:
            self.portal.call(self.stop.set)
            self.future.result(timeout=5)
        finally:
            self.portal_manager.__exit__(*exc)

    def post(self, *args, **kwargs):
        return self.portal.call(partial(self.client.post, *args, **kwargs))

    def get(self, *args, **kwargs):
        return self.portal.call(partial(self.client.get, *args, **kwargs))


class MemoryBroker:
    def __init__(self):
        self.calls = []
        self.revoked = False
        self.output = {"schema_version": "lh-job-v1", "authority_id": "synthetic-authority",
                       "tool_schema_digest": "1" * 64, "profiles": []}

    def call(self, name, arguments, principal):
        self.calls.append((name, arguments, principal))
        if self.revoked:
            raise JobError("UNAUTHORIZED", "private /secret/path and token must not leak")
        return self.output


@unittest.skipUnless(HAS_EXTRA, "Optional pinned MCP extra is not installed")
class ServerTests(unittest.TestCase):
    def setUp(self):
        self.issuer = SyntheticIssuer()
        self.broker = MemoryBroker()
        self.client = ASGIClient(create_app(self.broker, self.issuer.verifier), base_url="http://127.0.0.1:8765")
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.headers = {"Authorization": "Bearer " + self.issuer.token(),
                        "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}

    def rpc(self, method, params=None, *, headers=None):
        return self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method,
                                             "params": {} if params is None else params},
                                headers=self.headers if headers is None else headers)

    def test_real_sdk_initialization_tools_and_principal_mapping(self):
        response = self.rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                            "clientInfo": {"name": "fixture", "version": "1"}})
        self.assertEqual(200, response.status_code, response.text)
        response = self.rpc("tools/list")
        tools = response.json()["result"]["tools"]
        self.assertEqual(set(TOOL_SCHEMAS), {tool["name"] for tool in tools})
        self.assertTrue(all(tool["_meta"]["securitySchemes"][0]["type"] == "oauth2" for tool in tools))
        self.assertTrue(all(tool["outputSchema"]["type"] == "object" for tool in tools))
        response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(self.broker.output, response.json()["result"]["structuredContent"])
        principal = self.broker.calls[-1][2]
        self.assertIsInstance(principal, Principal)
        self.assertEqual("project-owner", principal.principal_id)

    def test_protected_resource_metadata_and_first_link_challenge(self):
        response = self.client.get("/.well-known/oauth-protected-resource/mcp")
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual([self.issuer.config.issuer], response.json()["authorization_servers"])
        self.assertIn("lh:evidence", response.json()["scopes_supported"])
        response = self.client.post("/mcp", content=b'{"broken":', headers={"Content-Type": "application/json"})
        self.assertEqual(401, response.status_code)
        self.assertIn('error="invalid_token"', response.headers["www-authenticate"])
        self.assertIn("oauth-protected-resource/mcp", response.headers["www-authenticate"])
        self.assertEqual([], self.broker.calls)

    def test_duplicate_json_unicode_depth_size_and_free_input_are_rejected_before_sdk(self):
        bad = [b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"lh_capabilities","arguments":{},"arguments":{}}}',
               b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"bad":"\\ud800"}}',
               b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":' + b'[' * 9 + b']' * 9 + b'}',
               b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"bad":NaN}}',
               b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"lh_capabilities","arguments":{"principal":"project-owner"}}}',
               b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"bad":"\xff"}}',
               b'null', b'"a string"', b'[]', b'[' + b' ' * 65536 + b']']
        for body in bad:
            with self.subTest(body=body[:50]):
                response = self.client.post("/mcp", content=body, headers=self.headers)
                self.assertIn(response.status_code, {400, 413}, response.text)
        self.assertEqual([], self.broker.calls)

    def test_tool_scope_error_and_local_revocation_return_standard_challenges(self):
        read_only = {**self.headers, "Authorization": "Bearer " + self.issuer.token(claims={"scope": "lh:read"})}
        response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}}, headers=read_only)
        result = response.json()["result"]
        self.assertTrue(result["isError"])
        self.assertIn("mcp/www_authenticate", result["_meta"])
        self.assertEqual([], self.broker.calls)
        self.broker.revoked = True
        response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
        self.assertEqual("UNAUTHORIZED", response.json()["result"]["structuredContent"]["error"]["code"])
        self.assertNotIn("/secret/path", response.text)

    def test_reauthorization_keeps_stable_identity_and_does_not_grant_resources(self):
        params = {"name": "lh_capabilities", "arguments": {}}
        self.rpc("tools/call", params)
        self.headers["Authorization"] = "Bearer " + self.issuer.token(claims={"jti": "replacement"})
        self.rpc("tools/call", params)
        self.assertEqual(self.broker.calls[0][2], self.broker.calls[1][2])

    def test_token_expiring_during_body_read_cannot_reach_the_broker(self):
        expiry = int(time.time()) + 2
        headers = {**self.headers, "Authorization": "Bearer " + self.issuer.token(claims={"exp": expiry})}
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "lh_capabilities", "arguments": {}}}).encode()

        async def slow_body():
            yield body[:1]  # Middleware has verified the still-valid signature.
            await asyncio.sleep(max(0, expiry - time.time()) + 0.05)
            yield body[1:]

        async def invoke():
            return await self.client.client.post("/mcp", content=slow_body(), headers=headers)

        response = self.client.portal.call(invoke)
        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHORIZED")
        self.assertIn('error="invalid_token"', response.headers["www-authenticate"])
        self.assertEqual([], self.broker.calls)

    def test_token_expiring_in_executor_queue_cannot_reach_the_broker(self):
        expiry = int(time.time()) + 2
        headers = {**self.headers, "Authorization": "Bearer " + self.issuer.token(claims={"exp": expiry})}
        to_thread = asyncio.to_thread
        async def delayed_dispatch(function, *args, **kwargs):
            if getattr(function, "__name__", "") == "dispatch":
                await asyncio.sleep(max(0, expiry - time.time()) + 0.05)
            return await to_thread(function, *args, **kwargs)
        with mock.patch("local_hand_mcp.server.asyncio.to_thread", side_effect=delayed_dispatch):
            response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}}, headers=headers)
        result = response.json()["result"]
        self.assertTrue(result["isError"], response.text)
        self.assertEqual(result["structuredContent"]["error"]["code"], "UNAUTHORIZED")
        self.assertIn("mcp/www_authenticate", result["_meta"])
        self.assertEqual([], self.broker.calls)

    def test_removed_signing_key_during_body_read_cannot_reach_the_broker(self):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "lh_capabilities", "arguments": {}}}).encode()

        async def rotate_during_body():
            yield body[:1]  # SDK accepted key-one for this HTTP request.
            self.issuer.now += self.issuer.config.refresh_cooldown_seconds + 1
            self.issuer.keys = [self.issuer.other_key]
            await self.issuer.verifier.authenticate(self.issuer.token(
                private=self.issuer.other_private, headers={"kid": "key-two"}))
            yield body[1:]

        async def invoke():
            return await self.client.client.post("/mcp", content=rotate_during_body(), headers=self.headers)

        response = self.client.portal.call(invoke)
        self.assertEqual(401, response.status_code, response.text)
        self.assertEqual("UNAUTHORIZED", response.json()["error"]["code"])
        self.assertEqual([], self.broker.calls)

    def test_removed_signing_key_in_executor_queue_cannot_reach_the_broker(self):
        to_thread = asyncio.to_thread

        async def rotate_before_dispatch(function, *args, **kwargs):
            if getattr(function, "__name__", "") == "dispatch":
                self.issuer.now += self.issuer.config.refresh_cooldown_seconds + 1
                self.issuer.keys = [self.issuer.other_key]
                await self.issuer.verifier.authenticate(self.issuer.token(
                    private=self.issuer.other_private, headers={"kid": "key-two"}))
            return await to_thread(function, *args, **kwargs)

        with mock.patch("local_hand_mcp.server.asyncio.to_thread", side_effect=rotate_before_dispatch):
            response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
        result = response.json()["result"]
        self.assertTrue(result["isError"], response.text)
        self.assertEqual("UNAUTHORIZED", result["structuredContent"]["error"]["code"])
        self.assertEqual([], self.broker.calls)

    def test_response_budget_rejects_large_result(self):
        self.broker.output = {"raw": "x" * 524288}
        response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
        self.assertEqual("LIMIT_EXCEEDED", response.json()["result"]["structuredContent"]["error"]["code"])
        self.assertLess(len(response.content), 2048)

    def test_control_task_start_failure_does_not_exhaust_unused_slots(self):
        from local_hand_mcp.server import MAX_CONTROL_REQUESTS
        create_task = asyncio.create_task
        rejected = []
        def fail_dispatch(coroutine, *args, **kwargs):
            if (getattr(getattr(coroutine, "cr_code", None), "co_name", None) == "invoke"
                    and coroutine.cr_frame.f_globals.get("__name__") == "local_hand_mcp.server"):
                rejected.append(coroutine)
                raise RuntimeError("synthetic event-loop task creation failure")
            return create_task(coroutine, *args, **kwargs)
        try:
            with mock.patch("local_hand_mcp.server.asyncio.create_task", side_effect=fail_dispatch):
                for _ in range(MAX_CONTROL_REQUESTS):
                    response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
                    self.assertEqual("IO_UNCERTAIN", response.json()["result"]["structuredContent"]["error"]["code"])
        finally:
            for coroutine in rejected:
                coroutine.close()
        self.assertEqual([], self.broker.calls)
        response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
        self.assertFalse(response.json()["result"]["isError"], response.text)
        self.assertEqual(len(self.broker.calls), 1)

    def test_host_origin_and_duplicate_credentials_rejected(self):
        response = self.rpc("tools/list", headers={**self.headers, "Host": "attacker.example"})
        self.assertNotEqual(200, response.status_code)
        response = self.rpc("tools/list", headers={**self.headers, "Origin": "https://attacker.example"})
        self.assertNotEqual(200, response.status_code)
        headers = list(self.headers.items()) + [("Authorization", "Bearer " + self.issuer.token())]
        response = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=headers)
        self.assertEqual(401, response.status_code)
        self.assertEqual([], self.broker.calls)

    def test_uncertain_control_receipt_does_not_cancel_or_repeat_broker_call(self):
        release = threading.Event()
        completed = threading.Event()
        original = self.broker.call

        def delayed(*args):
            release.wait(timeout=3)
            output = original(*args)
            completed.set()
            return output

        with mock.patch.object(self.broker, "call", side_effect=delayed), \
                mock.patch("local_hand_mcp.server.CONTROL_SECONDS", 0.05):
            try:
                response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
                self.assertEqual("IO_UNCERTAIN", response.json()["result"]["structuredContent"]["error"]["code"])
                self.assertFalse(completed.is_set())
            finally:
                release.set()
            self.assertTrue(completed.wait(timeout=2))
        self.assertEqual(1, len(self.broker.calls))

    def test_private_control_budget_tightens_the_adapter_reply_deadline(self):
        self.broker.policy = SimpleNamespace(limits={"control_response_seconds": 1})
        release, completed = threading.Event(), threading.Event()
        original = self.broker.call
        def delayed(*args):
            release.wait(timeout=3)
            result = original(*args)
            completed.set()
            return result
        with mock.patch.object(self.broker, "call", side_effect=delayed):
            started = time.monotonic()
            try:
                response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
                self.assertLess(time.monotonic() - started, 2)
                self.assertEqual("IO_UNCERTAIN", response.json()["result"]["structuredContent"]["error"]["code"])
                self.assertFalse(completed.is_set())
            finally:
                release.set()
            self.assertTrue(completed.wait(timeout=1))
        self.assertEqual(1, len(self.broker.calls))

    def test_service_teardown_attempts_every_resource_and_preserves_body_error(self):
        for body_fails in (False, True):
            with self.subTest(body_fails=body_fails):
                broker, maintenance = mock.Mock(), mock.Mock()
                broker.policy = SimpleNamespace(local_peers={}, principals={}, broker_root="/synthetic/private")
                resources = (maintenance, broker, broker.state, broker.authority_lock)
                cleanup_error = OSError("synthetic maintenance close failure")
                for resource in resources:
                    resource.close.side_effect = cleanup_error
                stderr = io.StringIO()
                with mock.patch("local_hand_mcp.server._require_optional"), \
                        mock.patch("local_hand_mcp.auth.AuthConfig.from_file", return_value=self.issuer.config), \
                        mock.patch("local_hand_jobs.cli.create_broker", return_value=broker), \
                        mock.patch("local_hand_jobs.cli.MaintenanceServer", return_value=maintenance), \
                        mock.patch("local_hand_mcp.server.create_app", return_value=mock.Mock()), \
                        mock.patch("local_hand_mcp.server.sys.stderr", stderr), \
                        mock.patch("uvicorn.run", side_effect=RuntimeError("synthetic primary run failure") if body_fails else None):
                    args = ["--config", "synthetic", "--auth-config", "synthetic", "--port", "8765"]
                    if body_fails:
                        self.assertEqual(2, main(args))
                        self.assertIn("synthetic primary run failure", stderr.getvalue())
                    else:
                        try:
                            raise ValueError("unrelated caller error")
                        except ValueError:
                            with self.assertRaises(OSError) as caught:
                                main(args)
                        self.assertIs(cleanup_error, caught.exception)
                for resource in resources:
                    resource.close.assert_called_once()

    def test_real_loopback_listener_uses_the_same_signed_transport(self):
        import httpx2
        import uvicorn
        from local_hand_mcp.auth import AuthConfig, JWTVerifier

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            fixture = SyntheticIssuer()
            fixture.configuration["resource"] = f"http://127.0.0.1:{port}/mcp"
            fixture.config = AuthConfig.from_dict(fixture.configuration)
            fixture.verifier = JWTVerifier(fixture.config, http_transport=fixture.transport)
            broker = MemoryBroker()
            server = uvicorn.Server(uvicorn.Config(create_app(broker, fixture.verifier),
                                    host="127.0.0.1", port=port, access_log=False, log_level="error"))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 3
                while not server.started and thread.is_alive() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(server.started, "Isolated loopback listener did not start")
                with httpx2.Client(trust_env=False, timeout=2) as client:
                    response = client.post(fixture.config.resource,
                        headers={"Authorization": "Bearer " + fixture.token(), "Accept": "application/json, text/event-stream"},
                        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "lh_capabilities", "arguments": {}}})
                self.assertEqual(200, response.status_code, response.text)
                self.assertEqual(broker.output, response.json()["result"]["structuredContent"])
                self.assertEqual(1, len(broker.calls))
            finally:
                server.should_exit = True
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive(), "Isolated listener failed to stop")


if __name__ == "__main__":
    unittest.main()
