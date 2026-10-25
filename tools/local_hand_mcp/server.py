"""Streamable HTTP tools for the single Local Hand broker.

Imports remain optional so base installations retain the existing worker/CLI.
The official SDK owns MCP transport; this adapter adds a strict raw-byte gate and
passes only an authenticated in-process Principal to the broker.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager, ExitStack
from contextvars import ContextVar
import importlib.metadata
import json
import logging
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlsplit
import uuid

from local_hand_jobs.contract import MAX_REQUEST_BYTES, JobError, SUBMIT_SCHEMA, TOOL_SCHEMAS, TOOL_SCOPES, strict_loads, validate_tool_args

MAX_BODY = MAX_REQUEST_BYTES
MAX_RESPONSE = 512 * 1024
BODY_SECONDS = 5
CONTROL_SECONDS = 5
MAX_CONTROL_REQUESTS = 32
_READ_ONLY = frozenset({"lh_capabilities", "lh_workspace_read", "lh_job_status", "lh_evidence_manifest", "lh_evidence_read_chunk"})
_REQUEST_ID = ContextVar("local_hand_mcp_request_id", default="none")
_REQUEST_LOG = logging.getLogger("local_hand_mcp.requests")
_DESCRIPTIONS = {
    "lh_workspace_read": "读取已登记项目来源快照中的 UTF-8 文件，返回原文、SHA-256 和源码提交。文件最多 120 KiB，JSON 转义后的响应最多 512 KiB；替换任务的完整 inputs 按规范化 JSON（含转义）限 120 KiB。只能使用 capabilities 给出的来源引用及仓库相对路径。读取不会准备或提交任务。",
    "lh_capabilities": "查看当前获准使用的功能、资源引用和身份绑定。若返回 prepared_request，原样提交该请求一次，并保留其任务标识。",
    "lh_job_submit": "提交一个确定的任务并持久保存记录。返回结果不确定时，保留原 operation_id，沿同一任务查询。",
    "lh_job_prepare": "使用新的任务 UUID 准备获准的任务。host.inspect 检查本机；workspace.edit 在任务独立副本中按原文件摘要修改并运行固定验证。先查询 capabilities 获取允许的引用。PREPARING 时用原参数和同一 UUID 查询；READY 后原样提交返回的请求。FAILED 记录保留，解决原因后可用 retry_failed=true 重试。准备本身不执行业务。",
    "lh_job_status": "查询属于当前用户的任务状态，或指定核对轮次的状态。",
    "lh_job_cancel": "使用原请求摘要和明确目标申请取消；取消整个任务时指定 target.kind=job。随后沿同一 operation_id 查询并确认退出，收到取消回执不代表进程已停止。可安全重复取消，已完成的目标保留并返回原结果。",
    "lh_job_reconcile": "使用固定的核对 ID 检查原任务已产生的影响，不重新执行业务。",
    "lh_evidence_manifest": "分页查看属于当前用户、已持久封存的证据文件清单。",
    "lh_evidence_read_chunk": "通过鉴权按限定大小读取证据文件分块，供客户端组装完整文件。",
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
        "cancel_requested": {"type": "boolean"}, "business_started": {"type": ["boolean", "null"]},
        "helper_started": {"type": ["boolean", "null"]}, "side_effects": _STRING,
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
    "lh_workspace_read": {"type":"object","required":["source_ref","source_commit","relative_path","sha256","bytes","content"],
        "properties":{**{key:_STRING for key in ('source_ref','source_commit','relative_path','sha256','content')},'bytes':_INTEGER}},
    # An original READY response can contain a now-retired request kind.
    # Result decoding must not confuse that history with new admission.
    "lh_job_prepare": {"type": "object", "required": ["operation_id", "state"],
        "properties": {"operation_id": _STRING, "state": {"enum": ["PREPARING", "READY", "FAILED"]},
            "retryable": {"type": "boolean"}, "request": SUBMIT_SCHEMA}},
    "lh_capabilities": {"type": "object", "required": ["schema_version", "authority_id", "tool_schema_digest", "profiles"],
        "properties": {"schema_version": _STRING, "supported_versions": {"type": "array", "items": _STRING},
            "authority_id": _STRING, "tool_schema_digest": _STRING, "policy_digest": _STRING,
            "generation": _INTEGER, "catalog_version": _STRING,
            "prepared_request": TOOL_SCHEMAS["lh_job_submit"],
            "preparation": {"type": "object", "properties": {
                "tool": _STRING, "profile_ref": _STRING, "kind": _STRING, "max_active": _INTEGER}},
            "execution_support": {"type": "object", "additionalProperties": {"type": "object",
                "properties": {"status": _STRING, "reason": _STRING}}},
            "profiles": {"type": "array", "maxItems": 100, "items": {"type": "object", "properties": {
                "profile_ref": _STRING, "expected": {"type": "object"},
                **{key: {"type": "array", "items": _STRING} for key in
                   ("allowed_kinds", "source_refs", "validation_refs", "runtime_refs", "build_cache_refs", "storage_refs", "prepared_refs")},
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


def _request_event(event, **fields):
    # Only fixed stages, validated tool names, numeric observations and exception
    # types belong here. Never log headers, arguments, results or exception text.
    _REQUEST_LOG.info(json.dumps(dict(request_id=_REQUEST_ID.get(), event=event, **fields),
                                 separators=(",", ":")))


class _RequestTrace:
    """Observe the admitted HTTP route before auth, without reading its body."""
    def __init__(self, app, path):
        self.app, self.path = app, path

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != self.path:
            return await self.app(scope, receive, send)
        token = _REQUEST_ID.set(uuid.uuid4().hex)
        started = time.monotonic()
        status, size, completed, failure = None, 0, False, None
        method = scope.get("method")
        _request_event("http_received", method=method if method in {"GET", "POST", "DELETE", "OPTIONS"} else "OTHER")

        async def observed_send(message):
            nonlocal status, size, completed
            await send(message)
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body":
                size += len(message.get("body", b""))
                completed = not message.get("more_body", False)

        try:
            return await self.app(scope, receive, observed_send)
        except BaseException as error:
            from .auth import _exception_location
            failure = _exception_location(error)
            raise
        finally:
            try:
                _request_event("http_finished", status=status, response_bytes=size, completed=completed,
                               elapsed_ms=round((time.monotonic() - started) * 1000), failure=failure)
            finally:
                _REQUEST_ID.reset(token)


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
        if not isinstance(params, dict) or set(params) - {"name", "arguments", "_meta"}:
            raise JobError("UNSUPPORTED", "Invalid tool-call parameters")
        # The official client includes _meta even when it is empty. It is
        # transport metadata, never a replacement for authenticated identity
        # or broker arguments; the raw document size/depth limits still apply.
        if "_meta" in params and type(params["_meta"]) is not dict:
            raise JobError("UNSUPPORTED", "Invalid tool-call metadata")
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
                        return await _json_error(send, 413, "LIMIT_EXCEEDED", "Request body exceeds 512 KiB")
                    if not event.get("more_body", False):
                        break
        except TimeoutError:
            return await _json_error(send, 408, "LIMIT_EXCEEDED", "Request body deadline exceeded")
        try:
            # Reading the body can outlive the token authenticated at the HTTP
            # boundary. Expiry must close new admission, not cancel old jobs.
            self.verifier.principal(get_access_token())
        except JobError:
            return await _json_error(send, 401, "UNAUTHORIZED", "Authentication is no longer current before dispatch",
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
    closing = threading.Event()
    config = verifier.config
    # Publish deployment capabilities, not every protocol operation. Keep this
    # independent of the current token so enabled tools can request step-up auth.
    enabled_tools = {
        name: schema for name, schema in TOOL_SCHEMAS.items()
        if TOOL_SCOPES[name] in config.scopes
        and (not getattr(broker, "read_only", False) or name in _READ_ONLY)
        and name in getattr(broker, "supported_tools", set(TOOL_SCHEMAS) - {"lh_job_prepare", "lh_workspace_read"})
    }
    enabled_scopes = sorted({TOOL_SCOPES[name] for name in enabled_tools})
    output_validators = {name: Draft202012Validator(schema) for name, schema in _OUTPUT_SCHEMAS.items()}

    def result_error(code: str, message: str, *, stage: str, required_scope: str | None = None):
        _request_event("tool_rejected", stage=stage, code=code)
        metadata = None
        if code == "UNAUTHORIZED":
            metadata = {"mcp/www_authenticate": [verifier.config.challenge(
                insufficient_scope=True, required_scope=required_scope)]}
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
            for name, schema in enabled_tools.items()
        ])

    async def call_tool(context, params):
        stage = "admission"
        _request_event("tool_received", tool=params.name if params.name in enabled_tools else "unsupported")
        try:
            if closing.is_set():
                raise JobError("IO_UNCERTAIN", "MCP transport has closed admission")
            access_token = get_access_token()
            stage = "authentication"
            principal = verifier.principal(access_token)
            stage = "arguments"
            arguments = validate_tool_args(params.name, params.arguments or {})
            if params.name not in enabled_tools:
                raise JobError("UNSUPPORTED", "This deployment does not offer this tool")
            if TOOL_SCOPES[params.name] not in principal.scopes:
                return result_error("UNAUTHORIZED", "The current token does not grant this tool",
                                    stage="authorization",
                                    required_scope=TOOL_SCOPES[params.name])
            limits = getattr(getattr(broker, "policy", None), "limits", {})
            control_seconds = min(CONTROL_SECONDS, limits.get("control_response_seconds", CONTROL_SECONDS))
            stage = "capacity"
            try:
                async with asyncio.timeout(0.1):
                    await slots.acquire()
            except TimeoutError:
                return result_error("LIMIT_EXCEEDED", "Control request capacity is occupied", stage=stage)

            async def invoke():
                try:
                    def dispatch():
                        # The executor queue can also outlive authentication.
                        # Recheck at delivery, before the broker sees the call.
                        current = verifier.principal(access_token)
                        if closing.is_set():
                            raise JobError("IO_UNCERTAIN", "MCP transport closed before dispatch")
                        began = time.monotonic()
                        _request_event("broker_started")
                        failure = None
                        try:
                            return broker.call(params.name, arguments, current)
                        except BaseException as error:
                            from .auth import _exception_location
                            failure = _exception_location(error)
                            raise
                        finally:
                            _request_event("broker_finished", elapsed_ms=round((time.monotonic() - began) * 1000),
                                           failure=failure)
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
            stage = "broker_wait"
            try:
                output = await asyncio.wait_for(asyncio.shield(task), control_seconds)
            except TimeoutError:
                return result_error("IO_UNCERTAIN", "Receipt is uncertain; query or resend the original identity", stage=stage)
            stage = "response_encoding"
            result = types.CallToolResult(
                content=[types.TextContent(type="text", text="Local Hand structured result")],
                structured_content=output,
            )
            if len(result.model_dump_json(by_alias=True).encode("utf-8")) > MAX_RESPONSE - 1024:
                return result_error("LIMIT_EXCEEDED", "Response exceeds the fixed size bound", stage=stage)
            stage = "response_schema"
            output_validators[params.name].validate(output)
            _request_event("tool_completed")
            return result
        except JobError as exc:
            # Codes are public protocol; arbitrary exception text/details may
            # contain private paths, tokens or subprocess output.
            code = exc.code if exc.code in {
                "UNAUTHORIZED", "CONFLICT", "STALE_DEPLOYMENT", "UNSUPPORTED", "RESOURCE_BUSY",
                "NOT_FOUND", "NOT_SEALED", "LIMIT_EXCEEDED", "IO_UNCERTAIN",
            } else "IO_UNCERTAIN"
            return result_error(code, f"Local Hand request rejected: {code}", stage=stage)
        except Exception as error:
            from .auth import _exception_location
            _request_event("tool_failed", stage=stage, failure=_exception_location(error))
            return result_error("IO_UNCERTAIN", "Local Hand request could not be completed", stage=stage)

    resource = urlsplit(config.resource)
    sdk = Server("infra-local-hand", version="0.2.0a1", on_list_tools=list_tools, on_call_tool=call_tool)

    async def publish_oauth_schemes(context, call_next):
        result = await call_next(context)
        if context.method == "tools/list":
            # SDK 2.2's version serializer strips unknown Tool fields, even
            # declared subclass fields. Its public middleware hook runs after
            # that serializer; mirror our trusted metadata into the OpenAI
            # top-level extension here while retaining the compatibility copy.
            return {**result, "tools": [
                {**tool, "securitySchemes": tool["_meta"]["securitySchemes"]}
                for tool in result["tools"]
            ]}
        return result

    sdk.middleware.append(publish_oauth_schemes)
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
                             "scopes_supported": enabled_scopes, "bearer_methods_supported": ["header"]},
                            headers={"Cache-Control": "no-store"})

    from starlette.routing import request_response
    for route in app.routes:
        if "/.well-known/oauth-protected-resource" in getattr(route, "path", ""):
            route.app = request_response(resource_metadata)

    sdk_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(current):
        try:
            await verifier.validate_readiness()
            async with sdk_lifespan(current):
                try:
                    if isinstance(getattr(broker, "deployment_proof", None), dict):
                        broker.deployment_proof["protocol_ready"] = True
                    yield
                finally:
                    if isinstance(getattr(broker, "deployment_proof", None), dict):
                        broker.deployment_proof["protocol_ready"] = False
                    # Refuse executor-queued calls before SDK teardown. Calls
                    # already delivered to the broker retain their identity and
                    # occupied capacity; transport shutdown is not job cancel.
                    closing.set()
        finally:
            closing.set()
        # The broker owns acceptance and job lifetime. Process-manager recovery
        # remains authoritative when transport shutdown interrupts pending I/O.

    app.router.lifespan_context = lifespan
    app.add_middleware(_RequestTrace, path=resource.path or "/mcp")
    return app


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the authenticated MCP adapter with the single Local Hand broker")
    parser.add_argument("--config", required=True, help="Private admitted broker policy")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--session", help="Administrator-created task session descriptor")
    mode.add_argument("--read-only", action="store_true", help="Read retained results without an execution session")
    mode.add_argument("--prepared-task", help="Admitted single task launcher; retain --config history for reads")
    mode.add_argument("--resident", help="Persistent task preparation and routing descriptor")
    parser.add_argument("--auth-config", required=True, help="Private external-issuer admission")
    parser.add_argument("--port", required=True, type=int, help="Admitted loopback listener port")
    parser.add_argument("--startup-config", help="Protected deployment startup selection binding")
    args = parser.parse_args(argv)
    try:
        _require_optional()
        # Enable only our sanitized authentication/request diagnostics. Raising the
        # root/HTTP-client level would also log private issuer URLs.
        for name in ("local_hand_mcp.auth", "local_hand_mcp.requests"):
            logger = logging.getLogger(name)
            if not logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter(
                    "%(asctime)s %(levelname)s pid=%(process)d %(name)s %(filename)s:%(lineno)d %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S%z"))
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
                logger.propagate = False
        from local_hand_mcp.auth import AuthConfig, JWTVerifier
        from local_hand_jobs.cli import create_broker, MaintenanceServer, close_service
        from local_hand_jobs.contract import Principal
        import uvicorn

        if not 1 <= args.port <= 65535:
            raise ValueError("Invalid listener port")
        from local_hand_mcp.startup_guard import guard
        with ExitStack() as startup_stack:
            guarded = startup_stack.enter_context(guard(args))
            auth = AuthConfig.from_file(args.auth_config)
            # Configuration reads and bind share the privileged startup lock.
            # Only the prebound loopback socket is handed to the HTTP server.
            broker = create_broker(args.config, actual_entrypoint=__file__, session_path=args.session,
                                   **({"read_only": True} if args.read_only or args.prepared_task or args.resident else {}))
            maintenance = listener = None
            failed = False
            try:
                retained = broker
                if args.prepared_task:
                    from local_hand_mcp.prepared import PreparedBroker
                    broker = PreparedBroker.open(retained, args.prepared_task, actual_entrypoint=__file__)
                if args.resident:
                    from local_hand_mcp.resident import ResidentBroker
                    broker = ResidentBroker.open(retained, args.resident)
                peers = {int(uid): Principal(identity, frozenset(broker.policy.principals[identity]["scopes"]))
                         for uid, identity in broker.policy.local_peers.items()}
                maintenance = MaintenanceServer(broker, Path(retained.policy.broker_root) / "maintenance.sock", peers)
                broker.start()
                if guarded is not None:
                    listener = guarded["bind"]()
                    broker.deployment_proof = guarded["proof"]
                startup_stack.close()
                # The secondary Unix endpoint can execute broker requests too;
                # publish it only after the same startup lease was acknowledged.
                maintenance.start()
                options = {"fd": listener.fileno()} if listener is not None else {"host": "127.0.0.1", "port": args.port}
                uvicorn.run(create_app(broker, JWTVerifier(auth)), **options,
                            access_log=False, log_level="warning", limit_concurrency=MAX_CONTROL_REQUESTS,
                            timeout_keep_alive=5, proxy_headers=False)
            except BaseException:
                failed = True
                raise
            finally:
                if listener is not None:
                    listener.close()
                close_service(broker, maintenance, failed=failed)
        return 0
    except (RuntimeError, ValueError, JobError) as exc:
        message = str(exc) if isinstance(exc, RuntimeError) else "Private MCP admission or broker startup failed"
        print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
