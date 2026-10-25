"""Fixed nginx gateway with a guarded public listener and protected readiness.

This is a container PID 1, not a command wrapper. Nginx receives one validated
configuration file and listens only on the container loopback address. The
supervisor owns the public TCP socket, limits relay resources, and never exposes
it until the root manager acknowledges the matching stable selection.
"""
from __future__ import annotations

import argparse
from contextlib import suppress
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import selectors
import shlex
import signal
import socket
import stat
import struct
import subprocess
import threading
import time

from local_hand.provenance import full_payload_digest
from local_hand_jobs import startup
from local_hand_jobs.contract import JobError

SCHEMA = "local-hand-gateway-startup/v1"
MAX_CONNECTIONS = 32
BUFFER_BYTES = 65536
IDLE_SECONDS = 60
CONNECTION_SECONDS = 3600
RUN_DIRECTORY = Path("/run/local-hand-gateway")
NGINX = "/usr/sbin/nginx"
HEX = re.compile(r"[0-9a-f]{64}\Z")


def _fail(message):
    raise JobError("GATEWAY_STARTUP_MISMATCH", message)


def validate_config(config):
    keys = {"schema", "node_id", "deployment_digest", "payload_digest", "manager_socket",
            "nginx_config", "public_port", "upstream_port", "status_socket"}
    if (not isinstance(config, dict) or not keys <= set(config)
            or set(config) - keys - {"worker_group"} or config["schema"] != SCHEMA):
        _fail("Invalid fixed gateway startup configuration")
    if not isinstance(config["node_id"], str) or not config["node_id"]:
        _fail("Gateway node identity is missing")
    if any(not isinstance(config[key], str) or HEX.fullmatch(config[key]) is None
           for key in ("deployment_digest", "payload_digest")):
        _fail("Gateway release identity is invalid")
    for key in ("manager_socket", "nginx_config", "status_socket"):
        value = config[key]
        if (not isinstance(value, str) or not Path(value).is_absolute() or str(Path(value)) != value
                or ".." in Path(value).parts or any(c.isspace() for c in value)):
            _fail("Gateway paths must be normalized absolute paths")
    if (len(set(config[key] for key in ("manager_socket", "nginx_config", "status_socket"))) != 3
            or any(type(config[key]) is not int or not 1024 <= config[key] <= 65535
                   for key in ("public_port", "upstream_port"))
            or config["public_port"] == config["upstream_port"]
            or Path(config["status_socket"]).parent != RUN_DIRECTORY):
        _fail("Gateway listener scope is invalid")
    if "worker_group" in config:
        group = config["worker_group"]
        if (not isinstance(group, dict) or set(group) != {"name", "gid"}
                or not isinstance(group["name"], str)
                or re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", group["name"]) is None
                or type(group["gid"]) is not int or not 1 <= group["gid"] <= 2**31 - 1):
            _fail("Invalid bound nginx worker group")
    return config


def validate_nginx(raw, upstream_port):
    """Accept one bounded HTTP reverse-proxy file, with no external config reads.

    The finite grammar forbids include/modules, TLS key files, static files,
    script execution, extra listeners and arbitrary log/temp paths. Configured
    upstream network or Unix sockets remain explicit proxy destinations, not
    additional configuration inputs. The complete file is separately hashed.
    """
    if not isinstance(raw, bytes) or len(raw) > 256 * 1024:
        _fail("Gateway nginx configuration exceeds its bound")
    try:
        lexer = shlex.shlex(raw.decode("utf-8"), posix=True, punctuation_chars="{};")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        tokens = []
        for token in lexer:
            tokens.extend(token if token and set(token) <= set("{};") else [token])
        if len(tokens) > 16384:
            _fail("Gateway nginx directive count exceeds its bound")
    except (UnicodeError, ValueError) as exc:
        raise JobError("GATEWAY_STARTUP_MISMATCH", "Invalid nginx tokenization") from exc
    index, listeners, default_deny, stderr_log, no_access_log = 0, 0, False, False, False
    sections = {"events": 0, "http": 0, "server": 0}
    backends, zones, used_backends, used_zones = {}, set(), set(), set()
    def size(value, maximum):
        match = re.fullmatch(r"([1-9][0-9]{0,9})([kKmM]?)", value)
        return bool(match and int(match[1]) * {"": 1, "k": 1024, "m": 1024**2}[match[2].lower()] <= maximum)
    def block(context, *, location=None, prefix=False):
        nonlocal index, listeners, default_deny, stderr_log, no_access_log
        terminal = False
        while index < len(tokens):
            if tokens[index] == "}":
                index += 1
                if context == "root": _fail("Unexpected nginx block end")
                if context == "location" and not terminal: _fail("Every location must proxy or return")
                if context == "methods" and not terminal: _fail("Method restriction must deny all other methods")
                return
            words = []
            while index < len(tokens) and tokens[index] not in {"{", "}", ";"}:
                words.append(tokens[index]); index += 1
            if not words or index == len(tokens): _fail("Incomplete nginx directive")
            delimiter = tokens[index]; index += 1
            name, args = words[0], words[1:]
            if delimiter == "{":
                if context == "root" and name in {"events", "http"} and not args:
                    sections[name] += 1
                    block(name)
                elif context == "http" and name == "upstream" and len(args) == 1 and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", args[0]):
                    block("upstream")
                elif context == "http" and name == "server" and not args:
                    sections["server"] += 1
                    block("server")
                elif context == "server" and name == "location" and len(args) in {1, 2}:
                    path = args[-1]
                    if (len(args) == 2 and args[0] != "=" or not path.startswith("/")
                            or re.search(r"[\s$;{}]", path)):
                        _fail("Only fixed literal gateway locations are supported")
                    block("location", location=path, prefix=len(args) == 1)
                elif context == "location" and name == "limit_except" and args == ["GET"]:
                    block("methods")
                else:
                    _fail("Unsupported nginx block")
                continue
            if delimiter != ";": _fail("Invalid nginx directive terminator")
            allowed = False
            if context == "root":
                allowed = (name == "worker_processes" and args == ["1"] or
                           name == "error_log" and args in (["stderr"], ["stderr", "warn"], ["stderr", "error"]))
                if name == "error_log" and allowed: stderr_log = True
            elif context == "events":
                allowed = name == "worker_connections" and len(args) == 1 and args[0].isdigit() and 16 <= int(args[0]) <= 1024
            elif context == "upstream":
                allowed = (name == "keepalive" and len(args) == 1 and args[0].isdigit() and 1 <= int(args[0]) <= 32)
                if name == "server" and len(args) == 1:
                    address = args[0]
                    allowed = bool(re.fullmatch(r"[A-Za-z0-9_.-]+:[0-9]{1,5}", address))
                    if allowed: allowed = 1 <= int(address.rsplit(":", 1)[1]) <= 65535
                    if address.startswith("unix:"):
                        path = address[5:]
                        allowed = Path(path).is_absolute() and ".." not in Path(path).parts and not any(c.isspace() for c in path)
            elif context == "methods":
                allowed = not terminal and name == "deny" and args == ["all"]
                terminal = allowed
            else:
                if context == "server" and name == "listen":
                    allowed = args == ["127.0.0.1:" + str(upstream_port)]
                    listeners += 1
                elif context == "server" and name == "server_name":
                    allowed = len(args) == 1 and re.fullmatch(r"_|[A-Za-z0-9][A-Za-z0-9.-]{0,252}", args[0]) is not None
                elif context == "http" and name == "resolver":
                    allowed = (len(args) == 3 and args[0] == "127.0.0.11" and args[2] == "ipv6=off"
                               and re.fullmatch(r"valid=(?:[1-9]|[1-5][0-9]|60)s", args[1]) is not None)
                elif context == "server" and name == "set":
                    # Only literal backend addresses under a private variable
                    # prefix. Request-controlled variables can never select a destination.
                    allowed = (len(args) == 2 and re.fullmatch(r"\$lh_backend_[a-z][a-z0-9_]{0,31}", args[0]) is not None
                               and re.fullmatch(r"http://[A-Za-z0-9][A-Za-z0-9_.-]{0,252}:[0-9]{1,5}", args[1]) is not None
                               and 1 <= int(args[1].rsplit(":", 1)[1]) <= 65535
                               and args[0] not in backends and len(backends) < 8)
                    if allowed: backends[args[0]] = args[1]
                elif context == "http" and name == "limit_req_zone":
                    zone = re.fullmatch(r"zone=([A-Za-z][A-Za-z0-9_]{0,31}):([1-9]|1[0-6])m", args[1]) if len(args) == 3 else None
                    rate = re.fullmatch(r"rate=([1-9][0-9]{0,3})r/s", args[2]) if len(args) == 3 else None
                    allowed = (bool(zone and rate) and args[0] == "$binary_remote_addr"
                               and int(rate[1]) <= 1000 and zone[1] not in zones and len(zones) < 8)
                    if allowed: zones.add(zone[1])
                elif name == "server_tokens":
                    allowed = args == ["off"]
                elif name == "access_log":
                    allowed = args == ["off"]
                    if context == "http" and allowed: no_access_log = True
                elif name == "default_type":
                    allowed = len(args) == 1 and args[0] in {"application/json", "text/plain", "application/octet-stream"}
                elif name == "client_max_body_size":
                    allowed = len(args) == 1 and size(args[0], 64 * 1024**2)
                elif name in {"client_body_temp_path", "proxy_temp_path", "fastcgi_temp_path", "uwsgi_temp_path", "scgi_temp_path"}:
                    directory = "client-body" if name == "client_body_temp_path" else name.removesuffix("_path").replace("_", "-")
                    allowed = args == [str(RUN_DIRECTORY / directory)]
                elif context == "location":
                    if name == "return":
                        if terminal: _fail("A gateway location must have exactly one response handler")
                        allowed = len(args) == 1 and args[0] in {"400", "401", "403", "404", "405", "503"}
                        terminal = allowed
                        if prefix and location == "/" and args == ["404"]: default_deny = True
                    elif name == "proxy_pass":
                        if terminal: _fail("A gateway location must have exactly one response handler")
                        allowed = len(args) == 1 and re.fullmatch(r"http://[A-Za-z0-9_.:-]+(?:/[^\s$;{}]*)?", args[0]) is not None
                        if len(args) == 1 and re.fullmatch(r"\$lh_backend_[a-z][a-z0-9_]{0,31}", args[0]):
                            allowed = True; used_backends.add(args[0])
                        terminal = allowed
                    elif name == "rewrite":
                        allowed = (not prefix and not terminal and len(args) == 3 and args[0] == "^" and args[2] == "break"
                                   and re.fullmatch(r"/[A-Za-z0-9/_.-]+", args[1]) is not None
                                   and ".." not in Path(args[1]).parts and not args[1].startswith("//"))
                    elif name == "limit_req":
                        zone = re.fullmatch(r"zone=([A-Za-z][A-Za-z0-9_]{0,31})", args[0]) if len(args) == 3 else None
                        burst = re.fullmatch(r"burst=([1-9][0-9]{0,3})", args[1]) if len(args) == 3 else None
                        allowed = bool(zone and burst) and int(burst[1]) <= 1024 and args[2] == "nodelay"
                        if allowed: used_zones.add(zone[1])
                    elif name == "proxy_set_header":
                        allowed = (len(args) == 2 and re.fullmatch(r"[A-Za-z0-9-]{1,64}", args[0]) is not None
                                   and len(args[1]) <= 1024 and not re.search(r"[\r\n]", args[1]))
                    elif name == "proxy_http_version": allowed = args == ["1.1"]
                    elif name in {"proxy_buffering", "proxy_request_buffering", "proxy_redirect"}: allowed = args == ["off"]
                    elif name in {"proxy_read_timeout", "proxy_send_timeout", "proxy_connect_timeout"}:
                        allowed = len(args) == 1 and re.fullmatch(r"[0-9]+s?", args[0]) is not None and 1 <= int(args[0].rstrip("s")) <= 300
            if not allowed: _fail("Unsupported nginx directive or value: " + name)
        if context != "root": _fail("Unclosed nginx block")
    block("root")
    if not used_backends <= backends.keys() or not used_zones <= zones:
        _fail("Gateway proxy or rate limit refers to an undeclared binding")
    if any(count != 1 for count in sections.values()) or listeners != 1 or not default_deny or not stderr_log or not no_access_log:
        _fail("Gateway requires one loopback listener, default deny and bounded logging destinations")
    return raw


def configuration_binding(config, *, read=None):
    validate_config(config)
    read = read or (lambda path: startup.protected_read(path, owner_uid=os.geteuid()))
    raw = read(config["nginx_config"])
    validate_nginx(raw, config["upstream_port"])
    return {"inputs": {"nginx_config": {"path": config["nginx_config"], "sha256": hashlib.sha256(raw).hexdigest()}},
            "public_port": config["public_port"], "upstream_port": config["upstream_port"],
            "status_socket": config["status_socket"],
            **({"worker_group": config["worker_group"]} if "worker_group" in config else {})}


def nginx_identity(config):
    """Bind the actual image group, including Unix backend access after setgid."""
    account = pwd.getpwnam("nginx")
    group = config.get("worker_group")
    if group is None:
        return account.pw_uid, account.pw_gid, "nginx"
    actual = grp.getgrnam(group["name"])
    if actual.gr_gid != group["gid"]:
        _fail("Nginx worker group differs from its selected identity")
    return account.pw_uid, actual.gr_gid, "nginx " + group["name"]


class Relay:
    """Bounded byte relay to one fixed container-loopback HTTP upstream."""
    def __init__(self, upstream_port, *, maximum=MAX_CONNECTIONS, idle=IDLE_SECONDS, lifetime=CONNECTION_SECONDS):
        self.upstream_port, self.maximum = upstream_port, maximum
        self.idle, self.lifetime = idle, lifetime
        self.listener = None
        self.connections = set()
        self.threads = set()
        self.lock = threading.Lock()
        self.allowed_until = 0.0

    def bind(self, port, *, address="0.0.0.0"):
        if self.listener is not None: return
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((address, port)); listener.listen(self.maximum); listener.setblocking(False)
        except BaseException:
            listener.close(); raise
        self.listener = listener

    def renew(self):
        self.allowed_until = time.monotonic() + 3

    def close_public(self):
        self.allowed_until = 0
        if self.listener is not None:
            self.listener.close(); self.listener = None
        with self.lock:
            connections = list(self.connections)
        for connection in connections:
            with suppress(OSError): connection.shutdown(socket.SHUT_RDWR)
            connection.close()

    def accept(self):
        if self.listener is None: return
        try: incoming, _ = self.listener.accept()
        except BlockingIOError: return
        with self.lock:
            self.threads = {thread for thread in self.threads if thread.is_alive()}
            if len(self.threads) >= self.maximum or time.monotonic() >= self.allowed_until:
                incoming.close(); return
            self.connections.add(incoming)
            thread = threading.Thread(target=self._relay, args=(incoming,), daemon=True)
            self.threads.add(thread)
            try: thread.start()
            except BaseException:
                self.connections.discard(incoming); self.threads.discard(thread); incoming.close(); raise

    def _relay(self, incoming):
        outgoing = None
        try:
            outgoing = socket.create_connection(("127.0.0.1", self.upstream_port), timeout=2)
            with self.lock: self.connections.add(outgoing)
            pair = (incoming, outgoing)
            for connection in pair: connection.setblocking(False)
            pending = {incoming: bytearray(), outgoing: bytearray()}
            eof = set(); started = activity = time.monotonic()
            while time.monotonic() < min(started + self.lifetime, activity + self.idle, self.allowed_until):
                with selectors.DefaultSelector() as selector:
                    for connection, other in ((incoming, outgoing), (outgoing, incoming)):
                        events = (selectors.EVENT_READ if connection not in eof and len(pending[other]) < BUFFER_BYTES else 0)
                        if pending[connection]: events |= selectors.EVENT_WRITE
                        if events: selector.register(connection, events, other)
                    if not selector.get_map(): return
                    ready = selector.select(.2)
                for key, mask in ready:
                    connection, other = key.fileobj, key.data
                    if mask & selectors.EVENT_READ:
                        try: data = connection.recv(BUFFER_BYTES - len(pending[other]))
                        except BlockingIOError: data = None
                        if data == b"": eof.add(connection)
                        elif data: pending[other].extend(data); activity = time.monotonic()
                    if mask & selectors.EVENT_WRITE:
                        try: count = connection.send(pending[connection])
                        except BlockingIOError: count = 0
                        if count: del pending[connection][:count]; activity = time.monotonic()
                if len(eof) == 2 and not any(pending.values()): return
                for connection, other in ((incoming, outgoing), (outgoing, incoming)):
                    if connection in eof and not pending[other]:
                        with suppress(OSError): other.shutdown(socket.SHUT_WR)
        except (OSError, ValueError):
            pass
        finally:
            for connection in (incoming, outgoing):
                if connection is not None:
                    with self.lock: self.connections.discard(connection)
                    connection.close()


def _verify_loaded(raw, config_path, config, binding, selection):
    if startup.protected_read(config_path, owner_uid=os.geteuid()) != raw or configuration_binding(config) != binding:
        _fail("Gateway configuration changed during startup")
    members = {member["path"]: member["sha256"] for member in selection["members"]}
    if (members.get(config_path) != hashlib.sha256(raw).hexdigest()
            or members.get(config["nginx_config"]) != binding["inputs"]["nginx_config"]["sha256"]):
        _fail("Gateway inputs are outside the complete selection")
    expected = selection["components"].get("gateway", {})
    if (selection["node_id"] != config["node_id"] or selection["deployment_digest"] != config["deployment_digest"]
            or expected.get("configuration_digest") != startup.digest(binding)
            or expected.get("payload_digest") != config["payload_digest"]):
        _fail("Gateway loaded input binding differs from selection")


def serve(config_path):
    if os.getpid() != 1 or os.geteuid() != 0:
        _fail("Gateway requires the supported root container PID 1 profile")
    raw = startup.protected_read(config_path, owner_uid=0)
    config = json.loads(raw, object_pairs_hook=startup._unique); validate_config(config)
    binding = configuration_binding(config)
    payload = full_payload_digest()
    if payload != config["payload_digest"]: _fail("Gateway installed payload differs from selection")
    RUN_DIRECTORY.mkdir(mode=0o755, exist_ok=True)
    directory = RUN_DIRECTORY.lstat()
    if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != 0 or directory.st_mode & 0o022:
        _fail("Gateway runtime directory is not protected")
    nginx_uid, nginx_gid, nginx_user = nginx_identity(config)
    for name in ("client-body", "proxy-temp", "fastcgi-temp", "uwsgi-temp", "scgi-temp"):
        temporary = RUN_DIRECTORY / name
        temporary.mkdir(mode=0o700, exist_ok=True)
        info = temporary.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, nginx_uid)
                or stat.S_IMODE(info.st_mode) != 0o700):
            _fail("Gateway temporary directory changed independently")
        os.chown(temporary, nginx_uid, nginx_gid, follow_symlinks=False)
    status_path = Path(config["status_socket"])
    if status_path.exists() or status_path.is_symlink():
        info = status_path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0: _fail("Gateway status path changed independently")
        status_path.unlink()
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT): signal.signal(signum, lambda *_: stop.set())
    relay, child, status = Relay(config["upstream_port"]), None, socket.socket(socket.AF_UNIX)
    route_slot = threading.BoundedSemaphore(1)
    route_threads = []
    def check_routes(connection, specification, observed):
        try:
            from .http_observation import observe_local
            with connection:
                checked = observe_local(config["upstream_port"], specification)
                startup._frame_send(connection, {"result": {**observed, "routes": checked}}, time.monotonic() + 1)
        except (JobError, OSError, ValueError):
            pass
        finally:
            route_slot.release()
    proof = None
    try:
        with startup.remote_gateway_authorization(config["manager_socket"], mode="candidate") as (selected, instance, acknowledge):
            _verify_loaded(raw, config_path, config, binding, selected)
            argv = [NGINX, "-p", str(RUN_DIRECTORY) + "/", "-c", config["nginx_config"], "-g", "daemon off; user " + nginx_user + "; pid " + str(RUN_DIRECTORY / "nginx.pid") + ";"]
            subprocess.run(argv + ["-t"], check=True, stdin=subprocess.DEVNULL, timeout=10)
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, start_new_session=True)
            deadline = time.monotonic() + 10
            while True:
                if child.poll() is not None: _fail("Internal nginx exited before readiness")
                try:
                    with socket.create_connection(("127.0.0.1", config["upstream_port"]), timeout=.2) as check:
                        check.sendall(b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n")
                        response = check.recv(1024).split(b"\r\n", 1)[0].split()
                        if len(response) < 2 or response[1] != b"404":
                            _fail("Internal nginx default route is not denied")
                    break
                except OSError:
                    if time.monotonic() >= deadline: _fail("Internal nginx did not become ready")
                    time.sleep(.05)
            _verify_loaded(raw, config_path, config, binding, selected)
            status.bind(str(status_path)); os.chmod(status_path, 0o600); status.listen(8); status.setblocking(False)
            proof = {**instance, "namespace_pid": 1, "component": "gateway", "entry": "local",
                     "node_id": config["node_id"], "deployment_digest": config["deployment_digest"],
                     "configuration_digest": startup.digest(binding), "payload_digest": payload,
                     "protocol_ready": True, "public_ready": False}
            acknowledge(proof)
        next_check = 0.0
        while not stop.is_set():
            if child.poll() is not None: _fail("Internal nginx exited")
            if time.monotonic() >= next_check:
                try:
                    with startup.remote_gateway_authorization(config["manager_socket"], mode="public") as (selected, instance, acknowledge):
                        _verify_loaded(raw, config_path, config, binding, selected)
                        if any(proof[k] != instance[k] for k in ("pid", "start_ticks", "boot_id")):
                            _fail("Gateway process binding changed")
                        relay.bind(config["public_port"])
                        acknowledge({**proof, "entry": "public"})
                    relay.renew()
                except (JobError, OSError, ValueError):
                    relay.close_public()
                next_check = time.monotonic() + 1
            proof["public_ready"] = relay.listener is not None and time.monotonic() < relay.allowed_until
            relay.accept()
            try: connection, _ = status.accept()
            except BlockingIOError: connection = None
            if connection is not None:
                with connection:
                    deadline = time.monotonic() + 1
                    connection.settimeout(1)
                    _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid == 0:
                        try:
                            request = startup._frame_read(connection, deadline)
                            if request == {"action": "deployment_observe"}:
                                startup._frame_send(connection, {"result": proof}, deadline)
                            elif (isinstance(request, dict) and set(request) == {"action", "specification"}
                                  and request["action"] == "deployment_check_routes"):
                                from .http_observation import validate_local
                                validate_local(request["specification"])
                                if route_slot.acquire(blocking=False):
                                    # One bounded reader, independent of lease renewal
                                    # and relaying. A read-only check cannot close an
                                    # otherwise healthy public listener by blocking PID 1.
                                    duplicate = None
                                    try:
                                        duplicate = connection.dup()
                                        route_threads[:] = [t for t in route_threads if t.is_alive()]
                                        thread = threading.Thread(target=check_routes,
                                            args=(duplicate, request["specification"], dict(proof)), daemon=True)
                                        thread.start(); route_threads.append(thread)
                                    except BaseException:
                                        if duplicate is not None: duplicate.close()
                                        route_slot.release(); raise
                        except (JobError, OSError, ValueError): pass
            stop.wait(.02)
    finally:
        relay.close_public(); status.close()
        for thread in route_threads: thread.join(timeout=10)
        if child is not None and child.poll() is None:
            with suppress(ProcessLookupError): os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                with suppress(ProcessLookupError): os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)
        with suppress(FileNotFoundError): status_path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    serve(args.config)


if __name__ == "__main__":
    main()
