"""Bounded isolated HTTPS observations, never deployment or rollback triggers."""
from __future__ import annotations

import hashlib
import os
import re
import select
import signal
import time
import urllib.error
import urllib.parse
import urllib.request

from .model import DeployError, canonical, decode

REQUEST_SECONDS = 5.0
CLEANUP_SECONDS = 1.0
MAX_BODY_BYTES = 262144
MAX_WORKER_BYTES = 8192


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate(specification):
    if (not isinstance(specification, dict) or set(specification) != {"deployment_digest", "checks"}
            or not isinstance(specification["deployment_digest"], str)
            or re.fullmatch(r"[0-9a-f]{64}", specification["deployment_digest"]) is None
            or not isinstance(specification["checks"], list) or not 1 <= len(specification["checks"]) <= 8):
        raise DeployError("INVALID_CHECK", "Public check must select a finite list of read-only requests")
    if len(canonical(specification)) > 512 * 1024:
        raise DeployError("INVALID_CHECK", "Public observation expectations exceed their bound")
    for spec in specification["checks"]:
        if (not isinstance(spec, dict) or set(spec) - {"url", "statuses", "json_equals", "www_authenticate"}
                or not isinstance(spec.get("url"), str) or not 1 <= len(spec["url"]) <= 8192
                or any(ord(char) <= 32 or ord(char) == 127 for char in spec["url"])
                or not isinstance(spec.get("statuses"), list) or not 1 <= len(spec["statuses"]) <= 16
                or any(type(code) is not int or not 100 <= code <= 599 for code in spec["statuses"])
                or "json_equals" in spec and not isinstance(spec["json_equals"], dict)
                or "www_authenticate" in spec and (not isinstance(spec["www_authenticate"], str)
                    or not 1 <= len(spec["www_authenticate"]) <= 8192)):
            raise DeployError("INVALID_CHECK", "Invalid expected public response")
        try:
            url = urllib.parse.urlsplit(spec["url"])
            valid_port = url.port is None or 1 <= url.port <= 65535
        except ValueError:
            valid_port = False
        if (not valid_port or url.scheme != "https" or not url.hostname
                or url.username is not None or url.password is not None or url.fragment or url.query):
            raise DeployError("INVALID_CHECK", "Public check requires an exact HTTPS URL without credentials or query")


def _request(spec):
    """Runs only in the disposable child. Socket timeout is an extra bound."""
    # Inherit neither ambient proxy credentials nor authentication handlers.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(spec["url"], method="GET", headers={
        "Accept": "application/json", "Accept-Encoding": "identity", "Cache-Control": "no-cache"})
    try:
        response = opener.open(request, timeout=REQUEST_SECONDS)
    except urllib.error.HTTPError as error:
        response = error  # 401 challenges and redirect responses are evidence.
    with response:
        raw = response.read(MAX_BODY_BYTES + 1)
        if len(raw) > MAX_BODY_BYTES:
            raise ValueError("response exceeds bound")
        matches = response.status in spec["statuses"]
        if "json_equals" in spec:
            body = decode(raw)
            matches = matches and isinstance(body, dict) and all(
                key in body and canonical(body[key]) == canonical(value)
                for key, value in spec["json_equals"].items())
        if "www_authenticate" in spec:
            matches = matches and spec["www_authenticate"] in response.headers.get("WWW-Authenticate", "")
        return dict(status="PASSED" if matches else "FAILED", http_status=response.status,
                    response_digest=hashlib.sha256(raw).hexdigest())


def _child(write_fd, spec, timeout):
    try:
        os.setsid()
        # Default SIGALRM terminates even a blocked resolver. No Python callback
        # or parent lifetime is required to enforce the read-only worker limit.
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        null = os.open(os.devnull, os.O_RDWR)
        try:
            for fd in (0, 1, 2):
                if fd != write_fd: os.dup2(null, fd)
        finally:
            if null not in (0, 1, 2, write_fd): os.close(null)
        try:
            result = _request(spec)
        except (OSError, ValueError, RuntimeError, urllib.error.URLError) as error:
            result = {"status": "UNKNOWN", "error": type(error).__name__}
        raw = canonical(result)
        if len(raw) > MAX_WORKER_BYTES:
            os._exit(2)
        while raw:
            count = os.write(write_fd, raw)
            if count <= 0: os._exit(2)
            raw = raw[count:]
        os._exit(0)
    except BaseException:
        os._exit(2)


def _reap(pid, *, terminate):
    if terminate:
        try: os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError: pass
        except PermissionError: pass
        # A deadline can fire before setsid. The PID is still our unreaped
        # direct child and cannot have been reused by another process.
        try: os.kill(pid, signal.SIGKILL)
        except ProcessLookupError: pass
    deadline = time.monotonic() + CLEANUP_SECONDS
    while True:
        try:
            actual, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return True, None
        if actual == pid:
            return True, status
        if time.monotonic() >= deadline:
            return False, None
        time.sleep(min(.01, max(0, deadline - time.monotonic())))


def _isolated(spec, *, timeout=None):
    """Total wall limit includes DNS and a slow body; cleanup is separately finite."""
    if not hasattr(os, "fork"):
        raise DeployError("UNSUPPORTED", "Public observation requires the supported Linux process boundary")
    timeout = REQUEST_SECONDS if timeout is None else timeout
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    pid = None; reaped = False
    deadline = time.monotonic() + timeout
    try:
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            _child(write_fd, spec, max(.001, deadline - time.monotonic()))
        os.close(write_fd); write_fd = None
        os.set_blocking(read_fd, False)
        raw = bytearray(); timed_out = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True; break
            ready, _, _ = select.select([read_fd], [], [], remaining)
            if not ready:
                timed_out = True; break
            block = os.read(read_fd, min(4096, MAX_WORKER_BYTES + 1 - len(raw)))
            if not block: break
            raw.extend(block)
            if len(raw) > MAX_WORKER_BYTES: break
        reaped, status = _reap(pid, terminate=timed_out or len(raw) > MAX_WORKER_BYTES)
        if not reaped:
            return {"status": "UNKNOWN", "error": "PROBE_CLEANUP_UNCONFIRMED"}
        if timed_out or status is not None and os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGALRM:
            return {"status": "UNKNOWN", "error": "PROBE_TIMEOUT"}
        if status is None or status != 0 or len(raw) > MAX_WORKER_BYTES:
            return {"status": "UNKNOWN", "error": "PROBE_INCOMPLETE"}
        try:
            result = decode(bytes(raw))
            if (not isinstance(result, dict) or result.get("status") not in {"PASSED", "FAILED", "UNKNOWN"}
                    or set(result) not in ({"status", "error"}, {"status", "http_status", "response_digest"})):
                raise ValueError("worker result")
            return result
        except (ValueError, RuntimeError):
            return {"status": "UNKNOWN", "error": "PROBE_INCOMPLETE"}
    finally:
        os.close(read_fd)
        if write_fd is not None: os.close(write_fd)
        if pid not in (None, 0) and not reaped:
            _reap(pid, terminate=True)


def check_public(specification):
    """No credentials, redirects or state writes. This is not client acceptance."""
    _validate(specification)  # Validate the entire batch before any request.
    results = []
    for spec in specification["checks"]:
        record = {"endpoint_digest": hashlib.sha256(spec["url"].encode()).hexdigest(), "observed_ns": time.time_ns()}
        record.update(_isolated(spec))
        results.append(record)
        if record.get('error') == 'PROBE_CLEANUP_UNCONFIRMED':
            break  # Do not accumulate workers whose exit has not been proved.
    return {"schema": "local-hand-public-observation/v1", "deployment_digest": specification["deployment_digest"],
            "status": "PASSED" if len(results) == len(specification["checks"])
                and all(row["status"] == "PASSED" for row in results) else "NOT_PASSED",
            "client_acceptance": "NOT_CHECKED", "checks": results}
