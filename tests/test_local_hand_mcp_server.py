"""Real SDK/ASGI integration against a synthetic signed issuer and local broker."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from functools import partial
import hashlib
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
from local_hand_jobs.contract import JobError, Principal, TOOL_SCHEMAS, TOOL_SCOPES, TOOL_SCHEMA_DIGEST, canonical_bytes
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

    def test_official_client_metadata_is_accepted_without_changing_principal_or_arguments(self):
        for metadata in ({}, {"principal": "untrusted", "progressToken": "request-1"}):
            response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}, "_meta": metadata})
            self.assertEqual(200, response.status_code, response.text)
            self.assertEqual(self.broker.output, response.json()["result"]["structuredContent"])
            self.assertEqual({}, self.broker.calls[-1][1])
            self.assertEqual("project-owner", self.broker.calls[-1][2].principal_id)
        before = len(self.broker.calls)
        response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}, "_meta": []})
        self.assertEqual(400, response.status_code)
        self.assertEqual(before, len(self.broker.calls))

    def test_request_trace_correlates_parallel_calls_with_reused_rpc_ids(self):
        barrier = threading.Barrier(3)
        operations = [f"12345678-1234-4234-8234-123456789ab{x}" for x in range(3)]

        def status(name, arguments, principal):
            barrier.wait(timeout=3)
            return dict(operation_id=arguments["operation_id"], request_digest="a" * 64,
                        lifecycle="TERMINAL", outcome="SUCCEEDED", evidence="SEALED", phase="EXITED")

        with self.assertLogs("local_hand_mcp.requests", level="INFO") as capture, \
                mock.patch.object(self.broker, "call", side_effect=status), ThreadPoolExecutor(max_workers=3) as pool:
            responses = list(pool.map(lambda op: self.rpc("tools/call", {
                "name": "lh_job_status", "arguments": {"operation_id": op},
                "_meta": {"private": "private-metadata-sentinel"}}), operations))
        for operation, response in zip(operations, responses):
            self.assertEqual(200, response.status_code, response.text)
            self.assertEqual(operation, response.json()["result"]["structuredContent"]["operation_id"])
        traces = {}
        for record in capture.records:
            item = json.loads(record.getMessage())
            self.assertRegex(item["request_id"], r"^[0-9a-f]{32}$")
            traces.setdefault(item["request_id"], []).append(item)
        self.assertEqual(3, len(traces))
        for events in traces.values():
            self.assertEqual(["http_received", "tool_received", "broker_started", "broker_finished",
                              "tool_completed", "http_finished"], [event["event"] for event in events])
            self.assertTrue(events[-1]["completed"])
            self.assertEqual(200, events[-1]["status"])
            self.assertGreater(events[-1]["response_bytes"], 0)
        emitted = "\n".join(capture.output)
        for private in (self.headers["Authorization"], "private-metadata-sentinel", *operations):
            self.assertNotIn(private, emitted)

    def test_request_trace_distinguishes_http_auth_rejection_and_broker_failure(self):
        with self.assertLogs("local_hand_mcp.requests", level="INFO") as capture:
            denied = self.rpc("tools/list", headers={**self.headers, "Authorization": "Bearer private-token-sentinel"})
        events = [json.loads(record.getMessage()) for record in capture.records]
        self.assertEqual(401, denied.status_code)
        self.assertEqual(["http_received", "http_finished"], [event["event"] for event in events])
        self.assertEqual(401, events[-1]["status"])
        self.assertNotIn("private-token-sentinel", "\n".join(capture.output))
        with self.assertLogs("local_hand_mcp.requests", level="INFO") as capture, \
                mock.patch.object(self.broker, "call", side_effect=ValueError("private-path-and-error-sentinel")):
            response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
        self.assertEqual("IO_UNCERTAIN", response.json()["result"]["structuredContent"]["error"]["code"])
        events = [json.loads(record.getMessage()) for record in capture.records]
        failure = next(event for event in events if event["event"] == "tool_failed")
        self.assertEqual("broker_wait", failure["stage"])
        self.assertEqual("ValueError", failure["failure"])
        self.assertEqual(1, len({event["request_id"] for event in events}))
        self.assertNotIn("private-path-and-error-sentinel", "\n".join(capture.output))

    def test_unknown_start_facts_remain_null_in_status_result(self):
        operation = "12345678-1234-4234-8234-123456789abc"
        self.broker.output = dict(operation_id=operation, request_digest="a" * 64,
            lifecycle="RUNNING", outcome="UNKNOWN", evidence="STAGING", phase="BUSINESS",
            business_started=None, helper_started=None)
        response = self.rpc("tools/call", {"name": "lh_job_status", "arguments": {"operation_id": operation}, "_meta": {}})
        self.assertEqual(200, response.status_code, response.text)
        result = response.json()["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(self.broker.output, result["structuredContent"])

    def test_resident_preparation_has_submit_scope_and_valid_async_result(self):
        from local_hand_mcp.resident import ResidentBroker
        broker = MemoryBroker()
        broker.supported_tools = ResidentBroker.supported_tools
        operation = "12345678-1234-4234-8234-123456789abc"
        broker.output = dict(operation_id=operation, state="PREPARING")
        with ASGIClient(create_app(broker, self.issuer.verifier), base_url="http://127.0.0.1:8765") as client:
            response = client.post("/mcp", json=dict(jsonrpc="2.0", id=1, method="tools/list"), headers=self.headers)
            tools = {tool["name"]: tool for tool in response.json()["result"]["tools"]}
            self.assertEqual(set(ResidentBroker.supported_tools), set(tools))
            self.assertEqual([{"type": "oauth2", "scopes": ["lh:submit"]}], tools["lh_job_prepare"]["securitySchemes"])
            self.assertEqual([{"type": "oauth2", "scopes": ["lh:cancel"]}], tools["lh_job_cancel"]["securitySchemes"])
            self.assertNotIn('lh_job_reconcile',tools)
            args = dict(operation_id=operation, kind="host.inspect", profile_ref="fixture")
            response = client.post("/mcp", json=dict(jsonrpc="2.0", id=2, method="tools/call",
                params=dict(name="lh_job_prepare", arguments=args)), headers=self.headers)
            result = response.json()["result"]
            self.assertFalse(result["isError"])
            self.assertEqual(broker.output, result["structuredContent"])
            self.assertEqual("project-owner", broker.calls[0][2].principal_id)
            cancel=dict(operation_id=operation,expected_request_digest='a'*64,target={'kind':'job'})
            response=client.post('/mcp',json=dict(jsonrpc='2.0',id=3,method='tools/call',
                params=dict(name='lh_job_cancel',arguments=cancel)),headers={**self.headers,
                    'Authorization':'Bearer '+self.issuer.token(claims={'scope':'lh:read'})})
            result=response.json()['result']
            self.assertEqual('UNAUTHORIZED',result['structuredContent']['error']['code'])
            self.assertIn('lh:cancel',result['_meta']['mcp/www_authenticate'][0])
            self.assertEqual(1,len(broker.calls))
            broker.output=dict(operation_id=operation,request_digest='a'*64,lifecycle='RUNNING',
                               outcome='PENDING',evidence='STAGING',phase='PREFLIGHT',cancel_requested=True)
            response=client.post('/mcp',json=dict(jsonrpc='2.0',id=4,method='tools/call',
                params=dict(name='lh_job_cancel',arguments=cancel)),headers=self.headers)
            self.assertFalse(response.json()['result']['isError'])
            self.assertEqual(('lh_job_cancel',cancel),broker.calls[-1][:2])

    def test_real_sdk_initialization_tools_and_principal_mapping(self):
        response = self.rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                            "clientInfo": {"name": "fixture", "version": "1"}})
        self.assertEqual(200, response.status_code, response.text)
        response = self.rpc("tools/list")
        tools = response.json()["result"]["tools"]
        expected_schemas = {k:v for k,v in TOOL_SCHEMAS.items() if k not in {"lh_job_prepare", "lh_workspace_read"}}
        self.assertEqual(set(expected_schemas), {tool["name"] for tool in tools})
        published = {tool["name"]: tool["inputSchema"] for tool in tools}
        self.assertNotIn("ledger.nas.roundtrip", json.dumps(published))
        self.assertEqual(published, expected_schemas)
        for tool in tools:
            expected = [{"type": "oauth2", "scopes": [TOOL_SCOPES[tool["name"]]]}]
            self.assertEqual(expected, tool.get("securitySchemes"))
            self.assertEqual(expected, tool["_meta"]["securitySchemes"])
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

    def test_read_only_deployment_publishes_only_usable_tools_and_scopes(self):
        self.broker.read_only = True
        with ASGIClient(create_app(self.broker, self.issuer.verifier), self.client.base_url) as client:
            response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                   headers=self.headers)
            tools = response.json()["result"]["tools"]
            self.assertEqual({"lh_capabilities", "lh_job_status", "lh_evidence_manifest",
                              "lh_evidence_read_chunk"}, {tool["name"] for tool in tools})
            self.assertTrue(all(tool["annotations"]["readOnlyHint"] for tool in tools))
            metadata = client.get("/.well-known/oauth-protected-resource/mcp").json()
            self.assertEqual({"lh:inspect", "lh:read", "lh:evidence"}, set(metadata["scopes_supported"]))
            # A stale client must not request an impossible permission upgrade.
            response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "lh_job_cancel", "arguments": {
                    "operation_id": "12345678-1234-4234-8234-123456789abc",
                    "expected_request_digest": "a" * 64, "target": {"kind": "job"}}}},
                headers={**self.headers, "Authorization": "Bearer " + self.issuer.token(
                    claims={"scope": "lh:read"})})
            result = response.json()["result"]
            self.assertEqual("UNSUPPORTED", result["structuredContent"]["error"]["code"])
            self.assertNotIn("mcp/www_authenticate", result.get("_meta") or {})
            self.assertEqual([], self.broker.calls)

    def test_unconfigured_scope_is_not_advertised_or_requested(self):
        self.issuer.verifier.config = replace(self.issuer.config, scopes=("lh:read", "lh:evidence"))
        with ASGIClient(create_app(self.broker, self.issuer.verifier), self.client.base_url) as client:
            response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                   headers=self.headers)
            self.assertEqual({"lh_job_status", "lh_evidence_manifest", "lh_evidence_read_chunk"},
                             {tool["name"] for tool in response.json()["result"]["tools"]})
            response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "lh_capabilities", "arguments": {}}}, headers=self.headers)
            result = response.json()["result"]
            self.assertEqual("UNSUPPORTED", result["structuredContent"]["error"]["code"])
            self.assertNotIn("mcp/www_authenticate", result.get("_meta") or {})
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
        tools = self.rpc("tools/list", headers=read_only).json()["result"]["tools"]
        self.assertIn("lh_capabilities", {tool["name"] for tool in tools})
        response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}}, headers=read_only)
        result = response.json()["result"]
        self.assertTrue(result["isError"])
        self.assertIn("mcp/www_authenticate", result["_meta"])
        challenge = result["_meta"]["mcp/www_authenticate"][0]
        self.assertIn('error="insufficient_scope"', challenge)
        self.assertIn('scope="lh:inspect"', challenge)
        self.assertNotIn('lh:submit', challenge)
        self.assertNotIn('lh:cancel', challenge)
        self.assertNotIn('lh:reconcile', challenge)
        self.assertEqual([], self.broker.calls)
        upgraded = {**read_only, "Authorization": "Bearer " + self.issuer.token(
            claims={"scope": "lh:read lh:inspect"})}
        response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}}, headers=upgraded)
        self.assertFalse(response.json()["result"]["isError"])
        self.assertEqual(self.broker.output, response.json()["result"]["structuredContent"])
        self.assertEqual(1, len(self.broker.calls))
        self.assertEqual("project-owner", self.broker.calls[0][2].principal_id)
        self.assertEqual({"lh:read", "lh:inspect"}, self.broker.calls[0][2].scopes)
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

        with self.assertLogs("local_hand_mcp.requests", level="INFO") as capture, \
                mock.patch.object(self.broker, "call", side_effect=delayed), \
                mock.patch("local_hand_mcp.server.CONTROL_SECONDS", 0.05):
            try:
                response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
                self.assertEqual("IO_UNCERTAIN", response.json()["result"]["structuredContent"]["error"]["code"])
                self.assertFalse(completed.is_set())
                events = [json.loads(record.getMessage()) for record in capture.records]
                rejection = next(event for event in events if event["event"] == "tool_rejected")
                self.assertEqual("broker_wait", rejection["stage"])
                self.assertEqual("IO_UNCERTAIN", rejection["code"])
                self.assertNotIn("tool_completed", [event["event"] for event in events])
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

    def test_lifespan_closes_executor_queue_admission_before_teardown(self):
        occupied, release = threading.Event(), threading.Event()
        executor = ThreadPoolExecutor(max_workers=1)

        def occupy():
            occupied.set()
            release.wait(timeout=5)

        blocker = executor.submit(occupy)
        self.assertTrue(occupied.wait(timeout=1))
        try:
            async def use_bounded_executor():
                asyncio.get_running_loop().set_default_executor(executor)
            self.client.portal.call(use_bounded_executor)
            with mock.patch("local_hand_mcp.server.CONTROL_SECONDS", 0.01):
                response = self.rpc("tools/call", {"name": "lh_capabilities", "arguments": {}})
            self.assertEqual("IO_UNCERTAIN", response.json()["result"]["structuredContent"]["error"]["code"])
            self.assertEqual([], self.broker.calls)
            self.client.portal.call(self.client.stop.set)
            self.client.future.result(timeout=2)
            release.set()
            blocker.result(timeout=2)
            # A barrier queued behind dispatch proves that the worker ran.
            executor.submit(lambda: None).result(timeout=2)
            self.client.portal.call(asyncio.sleep, 0.01)
            self.assertEqual([], self.broker.calls)
        finally:
            release.set()
            executor.shutdown()

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
                    args = ["--config", "synthetic", "--session", "synthetic-session", "--auth-config", "synthetic", "--port", "8765"]
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

    def test_real_loopback_listener_waits_for_issuer_then_uses_signed_transport(self):
        import httpx2
        import uvicorn
        from local_hand_mcp.auth import AuthConfig, JWTVerifier

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            fixture = SyntheticIssuer()
            fixture.configuration["resource"] = f"http://127.0.0.1:{port}/mcp"
            fixture.config = AuthConfig.from_dict(fixture.configuration)
            unavailable = threading.Event()
            metadata_calls = []

            def respond(request):
                if str(request.url) == fixture.config.metadata_url:
                    metadata_calls.append(request)
                    if len(metadata_calls) == 1:
                        unavailable.set()
                        return httpx2.Response(503)
                return fixture.handle(request)

            fixture.verifier = JWTVerifier(fixture.config, http_transport=httpx2.MockTransport(respond))
            broker = MemoryBroker()
            server = uvicorn.Server(uvicorn.Config(create_app(broker, fixture.verifier),
                                    host="127.0.0.1", port=port, access_log=False, log_level="error"))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                self.assertTrue(unavailable.wait(timeout=2))
                self.assertFalse(server.started)
                self.assertEqual([], broker.calls)
                deadline = time.monotonic() + 5
                while not server.started and thread.is_alive() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(server.started, "Isolated loopback listener did not start")
                self.assertEqual(2, len(metadata_calls))
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
