"""Seven-tool Streamable HTTP adapter for the single Local Hand broker.

Imports remain optional so base installations retain the existing worker/CLI.
The official SDK owns MCP transport; this adapter adds a strict raw-byte gate and
passes only an authenticated in-process Principal to the broker.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import importlib.metadata
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

from local_hand_jobs.contract import JobError, TOOL_SCHEMAS, TOOL_SCOPES, strict_loads, validate_tool_args

MAX_BODY = 64 * 1024
MAX_RESPONSE = 512 * 1024
BODY_SECONDS = 5
CONTROL_SECONDS = 5
MAX_CONTROL_REQUESTS = 32
_READ_ONLY = frozenset({"lh_capabilities", "lh_job_status", "lh_evidence_manifest", "lh_evidence_read_chunk"})
_DESCRIPTIONS = {
    "lh_capabilities": "Discover only admitted logical references and exact deployment bindings.",
    "lh_job_submit": "Durably submit one fixed job; preserve its operation ID across uncertain replies.",
    "lh_job_status": "Read one owned job or the exact requested reconciliation round.",
    "lh_job_cancel": "Durably request cancellation of the explicitly selected execution identity.",
    "lh_job_reconcile": "Observe original effects under a stable reconciliation ID; never rerun business work.",
    "lh_evidence_manifest": "Read a page of an owned, durably sealed evidence manifest.",
    "lh_evidence_read_chunk": "Read a bounded authenticated evidence chunk for host-side file assembly.",
}

# Stable public result fields. Nested evidence/identity documents retain their
# own schema_version; no raw process handles or filesystem paths are declared.
_STRING = {"type": "string"}
_INTEGER = {"type": "integer", "minimum": 0}
_STATUS_SCHEMA = {
    "type": "object", "required": ["operation_id", "request_digest", "lifecycle", "outcome", "evidence", "phase"],
    "properties": {
        "operation_id": _STRING, "request_digest": _STRING, "reconcile_id": _STRING,
        "lifecycle": {"enum": ["ACCEPTED", "RUNNING", "RECONCILE_REQUIRED", "TERMINAL"]},
        "outcome": {"enum": ["PENDING", "SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN"]},
        "evidence": {"enum": ["STAGING", "SEALED", "DURABILITY_UNKNOWN", "FAILED"]},
        "phase": _STRING, "event_seq": _INTEGER, "observed_at": {"type": "number"},
        "cancel_requested": {"type": "boolean"}, "business_started": {"type": "boolean"},
        "helper_started": {"type": "boolean"}, "side_effects": _STRING,
        "gaps": {"type": "array", "items": _STRING}, "exit_proof": {"type": ["object", "null"]},
        "seal_refs": {"type": "array", "items": {"type": "object"}},
        "reconciliations": {"type": "array", "items": {"type": "object"}},
        "outputs": {"type": "object", "properties": {
            "schema_version": _STRING, "prepared_ref": _STRING, "source_operation_id": _STRING,
            "source_commit": _STRING,
            "bindings": {"type": "object"}, "seal_ref": _STRING}},
    },
}
_OUTPUT_SCHEMAS = {name: _STATUS_SCHEMA for name in
                   ("lh_job_submit", "lh_job_status", "lh_job_cancel", "lh_job_reconcile")}
_OUTPUT_SCHEMAS.update({
    "lh_capabilities": {"type": "object", "required": ["schema_version", "authority_id", "tool_schema_digest", "profiles"],
        "properties": {"schema_version": _STRING, "supported_versions": {"type": "array", "items": _STRING},
            "authority_id": _STRING, "tool_schema_digest": _STRING, "policy_digest": _STRING,
            "generation": _INTEGER, "catalog_version": _STRING,
            "execution_support": {"type": "object", "additionalProperties": {"type": "object",
                "properties": {"status": _STRING, "reason": _STRING}}},
            "profiles": {"type": "array", "maxItems": 100, "items": {"type": "object", "properties": {
                "profile_ref": _STRING, "expected": {"type": "object"},
                **{key: {"type": "array", "items": _STRING} for key in
                   ("allowed_kinds", "source_refs", "build_cache_refs", "storage_refs", "prepared_refs")},
                "budgets": {"type": "object"}}}}, "next_cursor": {"type": ["string", "null"]}}},
    "lh_evidence_manifest": {"type": "object", "required": ["schema_version", "operation_id", "catalog_digest", "artifacts"],
        "properties": {"schema_version": _STRING, "operation_id": _STRING, "catalog_digest": _STRING,
            "artifacts": {"type": "array", "maxItems": 100, "items": {"type": "object", "properties": {
                "artifact_id": _STRING, "role": _STRING, "size": _INTEGER, "sha256": _STRING,
                "operation_id": _STRING, "seal_id": _STRING, "event_seq": _INTEGER,
                "reconcile_id": {"type": ["string", "null"]}, "seal_sha256": _STRING}}},
            "next_cursor": {"type": ["string", "null"]}}},
    "lh_evidence_read_chunk": {"type": "object", "required": ["artifact_id", "offset", "length", "total_size", "sha256", "chunk_sha256", "data_base64", "eof"],
        "properties": {"artifact_id": _STRING, "offset": _INTEGER, "length": _INTEGER, "total_size": _INTEGER,
            "sha256": _STRING, "chunk_sha256": _STRING, "data_base64": {"type": "string", "contentEncoding": "base64"},
            "eof": {"type": "boolean"}}},
})


def _require_optional() -> None:
    try:
        import mcp  # noqa: F401
        import jwt  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        raise RuntimeError("MCP dependencies are unavailable; install the pinned infra-local-hand[mcp] extra") from None
    if (importlib.metadata.version("mcp") != "2.2.0"
            or importlib.metadata.version("PyJWT") != "2.14.0"):
        raise RuntimeError("MCP dependency versions differ from the admitted 2.2.0 / PyJWT 2.14.0 baseline")


async def _json_error(send, status: int, code: str, message: str, *, challenge: str | None = None):
    body = json.dumps({"error": {"code": code, "message": message}}, separators=(",", ":")).encode()
    headers = [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]
    if challenge is not None:
        headers.append((b"www-authenticate", challenge.encode("ascii")))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def validate_rpc(payload: dict) -> None:
    """Validate the envelope before the SDK can erase duplicate/unknown keys."""
    if (not isinstance(payload, dict) or set(payload) - {"jsonrpc", "id", "method", "params"}
            or payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str)):
        raise JobError("UNSUPPORTED", "Invalid JSON-RPC envelope")
    if "id" in payload:
        identifier = payload["id"]
        if not ((type(identifier) is int and abs(identifier) <= 2**53 - 1)
                or (isinstance(identifier, str) and 0 < len(identifier) <= 128)):
            raise JobError("UNSUPPORTED", "Invalid JSON-RPC request identity")
    method = payload["method"]
    if method == "tools/call":
        if "id" not in payload:
            raise JobError("UNSUPPORTED", "Tool calls require a transport request identity")
        params = payload.get("params")
        if not isinstance(params, dict) or set(params) - {"name", "arguments"}:
            raise JobError("UNSUPPORTED", "Invalid tool-call parameters")
        if not isinstance(params.get("name"), str):
            raise JobError("UNSUPPORTED", "Missing tool name")
        validate_tool_args(params["name"], params.get("arguments", {}))


class _StrictBody:
    """Installed inside SDK authentication/context and outside its JSON parser."""
    def __init__(self, app, verifier):
        self.app = app
        self.verifier = verifier

    async def __call__(self, scope, receive, send):
        from mcp.server.auth.middleware.auth_context import get_access_token

        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if get_access_token() is None:
            return await _json_error(send, 401, "UNAUTHORIZED", "Authentication required",
                                     challenge=self.verifier.config.challenge())
        headers = list(scope.get("headers", []))
        # Duplicate Authorization headers must not let different middleware
        # layers select different credentials.
        if sum(key.lower() == b"authorization" for key, _ in headers) != 1:
            return await _json_error(send, 401, "UNAUTHORIZED", "Exactly one authorization header is required",
                                     challenge=self.verifier.config.challenge())
        if scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        if any(key.lower() == b"content-encoding" and value.lower() != b"identity" for key, value in headers):
            return await _json_error(send, 415, "UNSUPPORTED", "Encoded request bodies are unsupported")
        body = bytearray()
        try:
            async with asyncio.timeout(BODY_SECONDS):
                while True:
                    event = await receive()
                    if event["type"] != "http.request":
                        return
                    body.extend(event.get("body", b""))
                    if len(body) > MAX_BODY:
                        return await _json_error(send, 413, "LIMIT_EXCEEDED", "Request body exceeds 64 KiB")
                    if not event.get("more_body", False):
                        break
        except TimeoutError:
            return await _json_error(send, 408, "LIMIT_EXCEEDED", "Request body deadline exceeded")
        try:
            # Reading the body can outlive the token authenticated at the HTTP
            # boundary. Expiry must close new admission, not cancel old jobs.
            self.verifier.principal(get_access_token())
        except JobError:
            return await _json_error(send, 401, "UNAUTHORIZED", "Authentication expired before dispatch",
                                     challenge=self.verifier.config.challenge())
        try:
            payload = strict_loads(bytes(body))
            validate_rpc(payload)
        except (JobError, ValueError, TypeError):
            return await _json_error(send, 400, "UNSUPPORTED", "Malformed or unsupported request")
        supplied = False

        async def replay():
            nonlocal supplied
            if not supplied:
                supplied = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def create_app(broker, verifier):
    """Use one supplied broker; no independent executor or production bypass."""
    _require_optional()
    from mcp import types
    from mcp.server.lowlevel import Server
    from mcp.server.auth.middleware.auth_context import get_access_token
    from mcp.server.auth.settings import AuthSettings
    from mcp.server.transport_security import TransportSecuritySettings
    from jsonschema import Draft202012Validator

    pending: set[asyncio.Task] = set()
    slots = asyncio.Semaphore(MAX_CONTROL_REQUESTS)
    output_validators = {name: Draft202012Validator(schema) for name, schema in _OUTPUT_SCHEMAS.items()}

    def result_error(code: str, message: str):
        metadata = None
        if code == "UNAUTHORIZED":
            metadata = {"mcp/www_authenticate": [verifier.config.challenge(insufficient_scope=True)]}
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=message)],
            structured_content={"error": {"code": code, "message": message}},
            is_error=True, meta=metadata,
        )

    async def list_tools(context, params):
        # Authentication is transport-wide. Visibility here does not grant the
        # kind/resource permissions independently enforced by the broker.
        verifier.principal(get_access_token())
        return types.ListToolsResult(tools=[
            types.Tool(
                name=name, description=_DESCRIPTIONS[name], input_schema=schema, output_schema=_OUTPUT_SCHEMAS[name],
                annotations=types.ToolAnnotations(
                    read_only_hint=name in _READ_ONLY, destructive_hint=name not in _READ_ONLY,
                    idempotent_hint=True, open_world_hint=False,
                ),
                meta={"securitySchemes": [{"type": "oauth2", "scopes": [TOOL_SCOPES[name]]}]},
            )
            for name, schema in TOOL_SCHEMAS.items()
        ])

    async def call_tool(context, params):
        try:
            access_token = get_access_token()
            principal = verifier.principal(access_token)
            arguments = validate_tool_args(params.name, params.arguments or {})
            if TOOL_SCOPES[params.name] not in principal.scopes:
                raise JobError("UNAUTHORIZED", "The current token does not grant this tool")
            limits = getattr(getattr(broker, "policy", None), "limits", {})
            control_seconds = min(CONTROL_SECONDS, limits.get("control_response_seconds", CONTROL_SECONDS))
            try:
                async with asyncio.timeout(0.1):
                    await slots.acquire()
            except TimeoutError:
                return result_error("LIMIT_EXCEEDED", "Control request capacity is occupied")

            async def invoke():
                try:
                    def dispatch():
                        # The executor queue can also outlive authentication.
                        # Recheck at delivery, before the broker sees the call.
                        current = verifier.principal(access_token)
                        return broker.call(params.name, arguments, current)
                    return await asyncio.to_thread(dispatch)
                finally:
                    slots.release()

            invocation = invoke()
            try:
                task = asyncio.create_task(invocation)
            except BaseException:
                # Nothing reached the broker; neither an unawaited coroutine
                # nor a reserved control slot may survive this failed start.
                invocation.close()
                slots.release()
                raise
            pending.add(task)

            def consume(done):
                pending.discard(done)
                # An uncertain HTTP reply does not abandon the actual local
                # call, free its capacity, or create a replacement job.
                if not done.cancelled():
                    done.exception()

            task.add_done_callback(consume)
            try:
                output = await asyncio.wait_for(asyncio.shield(task), control_seconds)
            except TimeoutError:
                return result_error("IO_UNCERTAIN", "Receipt is uncertain; query or resend the original identity")
            result = types.CallToolResult(
                content=[types.TextContent(type="text", text="Local Hand structured result")],
                structured_content=output,
            )
            if len(result.model_dump_json(by_alias=True).encode("utf-8")) > MAX_RESPONSE - 1024:
                return result_error("LIMIT_EXCEEDED", "Response exceeds the fixed size bound")
            output_validators[params.name].validate(output)
            return result
        except JobError as exc:
            # Codes are public protocol; arbitrary exception text/details may
            # contain private paths, tokens or subprocess output.
            code = exc.code if exc.code in {
                "UNAUTHORIZED", "CONFLICT", "STALE_DEPLOYMENT", "UNSUPPORTED", "RESOURCE_BUSY",
                "NOT_FOUND", "NOT_SEALED", "LIMIT_EXCEEDED", "IO_UNCERTAIN",
            } else "IO_UNCERTAIN"
            return result_error(code, f"Local Hand request rejected: {code}")
        except Exception:
            return result_error("IO_UNCERTAIN", "Local Hand request could not be completed")

    config = verifier.config
    resource = urlsplit(config.resource)
    sdk = Server("infra-local-hand", version="0.2.0a1", on_list_tools=list_tools, on_call_tool=call_tool)
    app = sdk.streamable_http_app(
        streamable_http_path=resource.path or "/mcp", json_response=True, stateless_http=True,
        max_request_body_size=MAX_BODY, max_sessions=MAX_CONTROL_REQUESTS,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=[resource.netloc],
            allowed_origins=[f"{resource.scheme}://{resource.netloc}"],
        ),
        auth=AuthSettings(issuer_url=config.issuer, resource_server_url=config.resource,
                          required_scopes=[], validate_token_resource=True),
        token_verifier=verifier,
    )
    for route in app.routes:
        if getattr(route, "path", None) == (resource.path or "/mcp"):
            route.app = _StrictBody(route.app, verifier)
    # Required scopes at the HTTP gate are intentionally empty: a read-only
    # token must remain able to query old jobs. PRM advertises the union instead.
    from starlette.responses import JSONResponse

    async def resource_metadata(request):
        return JSONResponse({"resource": config.resource, "authorization_servers": [config.issuer],
                             "scopes_supported": list(config.scopes), "bearer_methods_supported": ["header"]},
                            headers={"Cache-Control": "no-store"})

    from starlette.routing import request_response
    for route in app.routes:
        if "/.well-known/oauth-protected-resource" in getattr(route, "path", ""):
            route.app = request_response(resource_metadata)

    sdk_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(current):
        await verifier.validate_issuer_metadata()
        async with sdk_lifespan(current):
            yield
        # The broker owns acceptance and job lifetime. Process-manager recovery
        # remains authoritative when transport shutdown interrupts pending I/O.

    app.router.lifespan_context = lifespan
    return app


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the authenticated MCP adapter with the single Local Hand broker")
    parser.add_argument("--config", required=True, help="Private admitted broker policy")
    parser.add_argument("--auth-config", required=True, help="Private external-issuer admission")
    parser.add_argument("--port", required=True, type=int, help="Admitted loopback listener port")
    args = parser.parse_args(argv)
    try:
        _require_optional()
        from local_hand_mcp.auth import AuthConfig, JWTVerifier
        from local_hand_jobs.cli import create_broker, MaintenanceServer
        from local_hand_jobs.contract import Principal
        import uvicorn

        if not 1 <= args.port <= 65535:
            raise ValueError("Invalid listener port")
        auth = AuthConfig.from_file(args.auth_config)
        # The first implementation only listens on loopback, for an admitted
        # TLS gateway/Tunnel; it cannot accidentally publish an unauthenticated
        # host interface. External connection admission remains E4.
        broker = create_broker(args.config, actual_entrypoint=__file__)
        maintenance = None
        try:
            peers = {int(uid): Principal(identity, frozenset(broker.policy.principals[identity]["scopes"]))
                     for uid, identity in broker.policy.local_peers.items()}
            maintenance = MaintenanceServer(broker, Path(broker.policy.broker_root) / "maintenance.sock", peers)
            broker.start()
            maintenance.start()
            uvicorn.run(create_app(broker, JWTVerifier(auth)), host="127.0.0.1", port=args.port,
                        access_log=False, log_level="warning", limit_concurrency=MAX_CONTROL_REQUESTS,
                        timeout_keep_alive=5, proxy_headers=False)
        finally:
            if maintenance is not None:
                maintenance.close()
            broker.close()
            broker.state.close()
            broker.authority_lock.close()
        return 0
    except (RuntimeError, ValueError, JobError) as exc:
        message = str(exc) if isinstance(exc, RuntimeError) else "Private MCP admission or broker startup failed"
        print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
