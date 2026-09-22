"""Private Unix-socket maintenance client using exactly the broker tool API."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import threading
import time

from .contract import JobError, Principal, MAX_REQUEST_BYTES, MAX_SAFE_INTEGER, strict_loads

MAX_RESPONSE_BYTES = 512 * 1024


def _deadline(connection, deadline):
    if deadline is None:
        return
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise JobError("IO_UNCERTAIN", "Local transport deadline expired; retain the original ID")
    connection.settimeout(remaining)


def _seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 60:
        raise JobError("INVALID_REQUEST", "Local transport requires a finite response budget")
    return value


def _receive(connection, length, *, deadline=None):
    chunks = []
    while length:
        _deadline(connection, deadline)
        part = connection.recv(min(length, 65536))
        _deadline(connection, deadline)
        if not part:
            raise JobError("IO_UNCERTAIN", "Local transport ended before its response")
        chunks.append(part)
        length -= len(part)
    return b"".join(chunks)


def _read_frame(connection, limit, *, deadline=None):
    size = struct.unpack("!I", _receive(connection, 4, deadline=deadline))[0]
    if size > limit:
        raise JobError("LIMIT_EXCEEDED", "Local transport frame exceeds its limit")
    return _receive(connection, size, deadline=deadline)


def _send_frame(connection, value, *, deadline=None, limit=MAX_RESPONSE_BYTES):
    raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > limit:
        raise JobError("LIMIT_EXCEEDED", "Local transport response exceeds its limit")
    _deadline(connection, deadline)
    connection.sendall(struct.pack("!I", len(raw)) + raw)


def _response(raw):
    """Decode bounded responses without losing keys; finite timestamps are valid.

    Request decoding deliberately rejects floats and has a smaller byte limit,
    so it cannot be reused for evidence chunks or status observation times.
    """
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def integer(text):
        if len(text.lstrip("-")) > 16 or abs(int(text)) > MAX_SAFE_INTEGER:
            raise ValueError("unsafe integer")
        return int(text)

    def number(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("nonfinite number")
        return value

    try:
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("oversized response")
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=unique,
                           parse_int=integer, parse_float=number, parse_constant=number)
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if depth > 16:
                raise ValueError("response nesting exceeds its bound")
            if isinstance(item, dict):
                pending.extend((part, depth + 1) for pair in item.items() for part in pair)
            elif isinstance(item, list):
                pending.extend((part, depth + 1) for part in item)
            elif isinstance(item, str) and any(0xD800 <= ord(char) <= 0xDFFF for char in item):
                raise ValueError("invalid Unicode")
        if type(value) is not dict or set(value) not in ({"result"}, {"error"}):
            raise ValueError("invalid response envelope")
        if "result" in value:
            if type(value["result"]) is not dict:
                raise ValueError("invalid tool result")
        else:
            error = value["error"]
            if (type(error) is not dict or not {"code", "message"} <= error.keys()
                    or error.keys() - {"code", "message", "details"}
                    or not isinstance(error["code"], str) or not isinstance(error["message"], str)
                    or ("details" in error and not isinstance(error["details"], dict))):
                raise ValueError("invalid error result")
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise JobError("IO_UNCERTAIN", "Local response is ambiguous or invalid; retain the original ID") from None


class MaintenanceServer:
    """Only protected OS peer mappings can introduce a Principal."""

    def __init__(self, broker, socket_path, peer_map, *, response_seconds=2, max_clients=16):
        if not hasattr(socket, "SO_PEERCRED"):
            raise JobError("UNSUPPORTED", "Authenticated Unix peers are unavailable")
        self.broker, self.path = broker, Path(socket_path)
        self.peer_map = dict(peer_map)
        limits = getattr(getattr(broker, "policy", None), "limits", {})
        self.response_seconds = min(_seconds(response_seconds),
                                    limits.get("control_response_seconds", response_seconds))
        if type(max_clients) is not int or not 1 <= max_clients <= 32:
            raise JobError("INVALID_REQUEST", "Local transport client capacity is invalid")
        self._closed = threading.Event()
        self._slots = threading.BoundedSemaphore(max_clients)
        self._listener = None
        self._identity = None
        self._thread = None
        self._connections = set()
        self._connection_lock = threading.Lock()

    def start(self):
        if self._listener is not None or self._closed.is_set():
            raise JobError("CONFLICT", "Maintenance listener is already started or closed")
        parent = self.path.parent
        listener = None
        try:
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or parent.resolve() != parent:
                raise JobError("UNAUTHORIZED", "Maintenance directory is not private")
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.settimeout(0.2)
            # bind is create-only; an existing socket/file is never unlinked.
            listener.bind(str(self.path))
            self._listener = listener
            info = self.path.lstat()
            self._identity = (info.st_dev, info.st_ino)
            self.path.chmod(0o600)
            listener.listen(16)
        except OSError as exc:
            if listener is not None and self._listener is None:
                listener.close()
            # bind may have created our entry before chmod/listen failed.
            # Reuse identity-checked cleanup; unknown identity or a concurrent
            # replacement is retained, never blindly unlinked on startup.
            try:
                self.close()
            except OSError:
                pass  # Cleanup uncertainty remains an unsuccessful startup.
            raise JobError("IO_UNCERTAIN", "Maintenance socket could not be established") from exc
        try:
            self._thread = threading.Thread(target=self._serve, daemon=True, name="local-hand-maintenance")
            self._thread.start()
        except Exception as exc:
            self.close()
            raise JobError("IO_UNCERTAIN", "Maintenance listener thread could not be started") from exc
        return self

    def _serve(self):
        while not self._closed.is_set():
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            if not self._slots.acquire(blocking=False):
                connection.close()
                continue
            with self._connection_lock:
                if self._closed.is_set():
                    connection.close()
                    self._slots.release()
                    continue
                self._connections.add(connection)
            try:
                threading.Thread(target=self._handle, args=(connection,), daemon=True).start()
            except Exception:
                try:
                    connection.close()
                finally:
                    with self._connection_lock:
                        self._connections.discard(connection)
                    self._slots.release()

    def _handle(self, connection):
        deadline = time.monotonic() + self.response_seconds
        try:
            _deadline(connection, deadline)
            credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            _, uid, _ = struct.unpack("3i", credentials)
            principal = self.peer_map.get(uid)
            if not isinstance(principal, Principal):
                raise JobError("UNAUTHORIZED", "OS peer has no admitted principal")
            request = strict_loads(_read_frame(connection, MAX_REQUEST_BYTES, deadline=deadline))
            if type(request) is not dict or set(request) != {"tool", "arguments"} or not isinstance(request["tool"], str):
                raise JobError("INVALID_REQUEST", "Local request must name only tool and arguments")
            if self._closed.is_set():
                raise JobError("IO_UNCERTAIN", "Maintenance transport closed before dispatch")
            _deadline(connection, deadline)
            result = self.broker.call(request["tool"], request["arguments"], principal)
            _send_frame(connection, {"result": result}, deadline=deadline)
        except JobError as error:
            try:
                _send_frame(connection, {"error": error.as_dict()}, deadline=deadline)
            except (OSError, JobError):
                pass
        except (OSError, ValueError, TypeError):
            try:
                _send_frame(connection, {"error": {"code": "IO_UNCERTAIN", "message": "Local request outcome is unresolved"}}, deadline=deadline)
            except (OSError, JobError):
                pass
        finally:
            try:
                connection.close()
            finally:
                with self._connection_lock:
                    self._connections.discard(connection)
                self._slots.release()

    def close(self):
        self._closed.set()
        if self._listener is not None:
            self._listener.close()
        with self._connection_lock:
            connections = tuple(self._connections)
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        if (self._thread is not None and self._thread.ident is not None
                and self._thread is not threading.current_thread()):
            self._thread.join(timeout=1)
        try:
            info = self.path.lstat()
            if self._identity == (info.st_dev, info.st_ino) and stat.S_ISSOCK(info.st_mode):
                self.path.unlink()
        except FileNotFoundError:
            pass


def request(socket_path, tool, arguments, *, timeout=2):
    """The client has no subprocess, ledger, policy, or execution fallback."""
    connection = None
    deadline = time.monotonic() + _seconds(timeout)
    try:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        _deadline(connection, deadline)
        connection.connect(str(socket_path))
        _send_frame(connection, {"tool": tool, "arguments": arguments}, deadline=deadline, limit=MAX_REQUEST_BYTES)
        result = _response(_read_frame(connection, MAX_RESPONSE_BYTES, deadline=deadline))
        _deadline(connection, deadline)
        if "error" in result:
            error = result["error"]
            raise JobError(error["code"], error["message"], error.get("details"))
        return result["result"]
    except OSError as exc:
        raise JobError("IO_UNCERTAIN", "Local request outcome is unresolved; retain the original ID") from exc
    finally:
        if connection is not None:
            connection.close()


def create_broker(policy_path, *, actual_entrypoint, initialize=False):
    """Both service entrypoints use this production-only composition root.

    Missing supervision, private admission or provenance is a hard failure.
    ``initialize`` is explicit first-ledger provisioning, never automatic recovery.
    """
    if sys.platform != "linux":
        raise JobError("UNSUPPORTED", "The restricted job service requires Linux supervision")
    from .broker import Broker
    from .deployment import verify_release
    from .policy import Policy
    from .registry import Registry
    from .resources import AuthorityLock, verify_local_filesystem
    from .runner import Runner, SystemdManager
    from .state import StateStore
    from .evidence import EvidenceStore
    policy = Policy.from_file(policy_path)
    verify_release(expected_source_commit=policy.source_commit,
                   expected_payload_digest=policy.installed_payload_digest,
                   expected_entrypoint=policy.execution_entrypoint,
                   actual_entrypoint=actual_entrypoint)
    manager = SystemdManager(policy.config.get("process_manager"))
    support = manager.support()
    if support.get("supported") is not True:
        raise JobError("UNSUPPORTED", "The admitted independent process supervisor is unavailable")
    verify_local_filesystem(policy.broker_root)
    verify_local_filesystem(policy.authority_root)
    anchor_path = Path(policy.authority_root) / "authority.json"
    # Identity is administratively provisioned, independent of the requested DB.
    try:
        fd = os.open(anchor_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise JobError("IO_UNCERTAIN", "Authority registration is not a unique regular file")
            registration = strict_loads(os.read(fd, 8193))
        finally:
            os.close(fd)
        ledger_id = registration["ledger_id"]
    except (OSError, KeyError, TypeError) as exc:
        raise JobError("IO_UNCERTAIN", "Registered authority identity is unavailable") from exc
    authority = AuthorityLock(anchor_path, authority_id=policy.authority_id,
                              ledger_id=ledger_id, state_root=policy.broker_root)
    state = None
    try:
        if initialize:
            marker = Path(policy.authority_root) / "ledger.initialized"
            try:
                descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                try:
                    os.write(descriptor, ledger_id.encode("ascii"))
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                directory = os.open(marker.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except OSError as exc:
                raise JobError("IO_UNCERTAIN", "Ledger bootstrap is already recorded or its durability is unresolved") from exc
        state = StateStore(Path(policy.broker_root) / "jobs.sqlite", policy.authority_id,
                           ledger_id, initialize=initialize)
        with state.transaction() as tx:
            units = [handle.get("unit", "lhj-" + hashlib.sha256(handle["execution_id"].encode()).hexdigest() + ".service")
                     for row in state.all(tx) for handle in row["record"].get("handles", {}).values()]
        inventory = manager.scan(units)
        if inventory.get("status") != "READY":
            raise JobError("IO_UNCERTAIN", "Supervisor inventory has orphaned or unresolved executions")
        broker = Broker(state, policy, Registry(), Runner(manager))
        def no_direct_seal(_):
            raise JobError("UNSUPPORTED", "Evidence publication must use a registered supervised phase")
        def authorize_evidence(principal, operation_id):
            with broker.state.transaction() as tx:
                broker._row(tx, "job", operation_id, principal, "lh:evidence")
        broker.evidence = EvidenceStore(Path(policy.broker_root) / "artifacts",
            snapshot_provider=no_direct_seal, register_seal=broker.register_seal,
            is_registered=broker.is_registered, list_seals=broker.list_seals,
            authorize=authorize_evidence,
            max_source_bytes=policy.limits["retained_bytes"],
            max_artifact_bytes=policy.limits["retained_bytes"])
        broker.authority_lock = authority
        return broker
    except BaseException:
        try:
            if state is not None:
                state.close()
        finally:
            authority.close()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Call the admitted broker over its private Unix socket")
    parser.add_argument("--socket", required=True, type=Path)
    parser.add_argument("tool")
    parser.add_argument("--json", default="{}", dest="arguments")
    args = parser.parse_args(argv)
    try:
        result = request(args.socket, args.tool, strict_loads(args.arguments))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except JobError as error:
        print(json.dumps({"error": error.as_dict()}), file=sys.stderr)
        return 2


def broker_main(argv=None):
    parser = argparse.ArgumentParser(description="Run the single admitted Local Hand broker")
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--initialize", action="store_true", help="Explicitly initialize an absent first ledger")
    args = parser.parse_args(argv)
    broker = server = None
    try:
        broker = create_broker(args.policy, actual_entrypoint=__file__, initialize=args.initialize)
        peers = {int(uid): Principal(identity, frozenset(broker.policy.principals[identity]["scopes"]))
                 for uid, identity in broker.policy.local_peers.items()}
        server = MaintenanceServer(broker, Path(broker.policy.broker_root) / "maintenance.sock", peers)
        broker.start()
        server.start()
        threading.Event().wait()
    except KeyboardInterrupt:
        return 0
    except JobError as error:
        print(json.dumps({"error": error.as_dict()}), file=sys.stderr)
        return 2
    finally:
        if server:
            server.close()
        if broker:
            broker.close()
            broker.state.close()
            broker.authority_lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
