"""Finite unauthenticated route observations; never follow redirects or submit jobs."""
from __future__ import annotations

import hashlib
import http.client
import io
import json
import re
import socket
import time
import urllib.parse

PURPOSES = {"reachability", "anonymous_protected", "management_hidden", "issuer_metadata", "resource_metadata"}
SECURITY_PURPOSES = PURPOSES - {"reachability"}
MAX_BODY = 262144


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def validate_check(spec, *, path=False):
    address = "path" if path else "url"
    if (not isinstance(spec, dict) or set(spec) - {address, "statuses", "json_equals", "www_authenticate", "purpose"}
            or not isinstance(spec.get(address), str) or not 1 <= len(spec[address]) <= 8192
            or any(ord(c) <= 32 or ord(c) >= 127 for c in spec[address])
            or not isinstance(spec.get("statuses"), list) or not 1 <= len(spec["statuses"]) <= 16
            or any(type(code) is not int or not 100 <= code <= 599 for code in spec["statuses"])
            or "json_equals" in spec and not isinstance(spec["json_equals"], dict)
            or "www_authenticate" in spec and (not isinstance(spec["www_authenticate"], str)
                or not 1 <= len(spec["www_authenticate"]) <= 8192)
            or not isinstance(spec.get("purpose", "reachability"), str)
            or spec.get("purpose", "reachability") not in PURPOSES):
        raise ValueError("Invalid finite HTTP observation")
    parsed = urllib.parse.urlsplit(spec[address])
    if path and (not spec[address].startswith("/") or spec[address].startswith("//")
                 or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment):
        raise ValueError("Only literal local route paths are supported")
    purpose = spec.get("purpose", "reachability")
    if (purpose == "anonymous_protected" and spec["statuses"] != [401]
            or purpose == "management_hidden" and not set(spec["statuses"]) <= {403, 404}
            or purpose.endswith("_metadata") and spec["statuses"] != [200]):
        raise ValueError("Safety expectations cannot accept an unsafe response")
    expected = spec.get("json_equals", {})
    if purpose == "issuer_metadata" and not isinstance(expected.get("issuer"), str):
        raise ValueError("Issuer expectation is required")
    if purpose == "resource_metadata" and (not isinstance(expected.get("resource"), str)
            or not isinstance(expected.get("authorization_servers"), list)
            or len(expected["authorization_servers"]) != 1
            or not isinstance(expected["authorization_servers"][0], str)):
        raise ValueError("Resource and authorization server expectations are required")


def validate_local(specification):
    if (not isinstance(specification, dict) or set(specification) != {"authority", "checks"}
            or not isinstance(specification["authority"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*(?::[0-9]{1,5})?", specification["authority"])
            or not isinstance(specification["checks"], list) or not 1 <= len(specification["checks"]) <= 8
            or len(canonical(specification)) > 16384):
        raise ValueError("Invalid local gateway observation scope")
    for spec in specification["checks"]:
        validate_check(spec, path=True)
    if not SECURITY_PURPOSES <= {spec.get("purpose") for spec in specification["checks"]}:
        raise ValueError("All four security route checks are required before opening")


def evaluate(spec, status, headers, raw):
    if len(raw) > MAX_BODY:
        raise ValueError("Response exceeds bound")
    matches = status in spec["statuses"]
    body = None
    if "json_equals" in spec:
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value: raise ValueError("Duplicate JSON field")
                value[key] = item
            return value
        body = json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
        matches = matches and isinstance(body, dict) and all(
            key in body and canonical(body[key]) == canonical(value) for key, value in spec["json_equals"].items())
    if "www_authenticate" in spec:
        matches = matches and spec["www_authenticate"] in headers.get("WWW-Authenticate", "")
    purpose = spec.get("purpose", "reachability")
    unsafe = (purpose in {"anonymous_protected", "management_hidden"} and 200 <= status < 300
              or purpose.endswith("_metadata") and status == 200 and isinstance(body, dict) and not matches)
    return {"status": "SECURITY_FAILED" if unsafe else "PASSED" if matches else "FAILED",
            "http_status": status, "response_digest": hashlib.sha256(raw).hexdigest()}


def unsafe_headers(spec, status):
    # An anonymously accepted SSE stream may never finish a body. Its 2xx
    # response already proves this expectation failed; a later read timeout
    # must not downgrade that known safety failure to a network unknown.
    if spec.get("purpose") in {"anonymous_protected", "management_hidden"} and 200 <= status < 300:
        return {"status": "SECURITY_FAILED", "http_status": status,
                "response_digest": None, "body_observed": False}
    return None


def local_check(port, authority, spec, *, timeout=1.0):
    """Only the supervisor's container loopback. One wall deadline, bounded bytes.

    HTTP parsing happens on the already bounded in-memory response, so neither
    slow chunked bodies nor DNS can extend the read budget. No ambient proxy.
    """
    validate_check(spec, path=True)
    deadline = time.monotonic() + timeout
    raw = bytearray()
    class MemorySocket:
        def makefile(self, *args, **kwargs): return io.BytesIO(raw)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(max(.001, deadline - time.monotonic()))
        connection.connect(("127.0.0.1", port))
        request = ("GET " + spec["path"] + " HTTP/1.0\r\nHost: " + authority
                   + "\r\nAccept: application/json\r\nConnection: close\r\n\r\n").encode("ascii")
        connection.settimeout(max(.001, deadline - time.monotonic()))
        connection.sendall(request)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError("Route observation deadline")
            connection.settimeout(remaining)
            block = connection.recv(min(8192, MAX_BODY + 16385 - len(raw)))
            if not block: break
            raw.extend(block)
            if len(raw) > MAX_BODY + 16384: raise ValueError("Response exceeds bound")
            if b"\r\n\r\n" in raw:
                with http.client.HTTPResponse(MemorySocket()) as headers:
                    headers.begin()
                    unsafe = unsafe_headers(spec, headers.status)
                    if unsafe: return unsafe
    with http.client.HTTPResponse(MemorySocket()) as response:
        response.begin()
        return evaluate(spec, response.status, response.headers, response.read(MAX_BODY + 1))


def observe_local(port, specification):
    validate_local(specification)
    results = []
    for spec in specification["checks"]:
        item = {"purpose": spec.get("purpose", "reachability"), "endpoint_digest": hashlib.sha256(spec["path"].encode()).hexdigest(),
                "observed_ns": time.time_ns()}
        try:
            item.update(local_check(port, specification["authority"], spec))
        except (OSError, ValueError, http.client.HTTPException) as error:
            item.update(status="UNKNOWN", error=type(error).__name__)
        results.append(item)
    return {"specification_digest": hashlib.sha256(canonical(specification)).hexdigest(), "checks": results,
            "passed": all(item["status"] == "PASSED" for item in results)}
