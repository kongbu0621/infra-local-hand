"""Private Unix-socket maintenance client using exactly the broker tool API."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import threading

from .contract import JobError, Principal, MAX_REQUEST_BYTES, strict_loads

MAX_RESPONSE_BYTES = 512 * 1024


def _receive(connection, length):
    chunks = []
    while length:
        part = connection.recv(min(length, 65536))
        if not part:
            raise JobError("IO_UNCERTAIN", "Local transport ended before its response")
        chunks.append(part)
        length -= len(part)
    return b"".join(chunks)


def _read_frame(connection, limit):
    size = struct.unpack("!I", _receive(connection, 4))[0]
    if size > limit:
        raise JobError("LIMIT_EXCEEDED", "Local transport frame exceeds its limit")
    return _receive(connection, size)


def _send_frame(connection, value):
    raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise JobError("LIMIT_EXCEEDED", "Local transport response exceeds its limit")
    connection.sendall(struct.pack("!I", len(raw)) + raw)


class MaintenanceServer:
    """Only protected OS peer mappings can introduce a Principal."""

    def __init__(self, broker, socket_path, peer_map, *, response_seconds=2, max_clients=16):
        if not hasattr(socket, "SO_PEERCRED"):
            raise JobError("UNSUPPORTED", "Authenticated Unix peers are unavailable")
        self.broker, self.path = broker, Path(socket_path)
        self.peer_map = dict(peer_map)
        self.response_seconds = response_seconds
        self._closed = threading.Event()
        self._slots = threading.BoundedSemaphore(max_clients)
        self._listener = None
        self._identity = None
        self._thread = None

    def start(self):
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
            self.path.chmod(0o600)
            info = self.path.lstat()
            self._identity = (info.st_dev, info.st_ino)
            listener.listen(16)
        except OSError as exc:
            if listener is not None:
                listener.close()
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
            try:
                threading.Thread(target=self._handle, args=(connection,), daemon=True).start()
            except Exception:
                try:
                    connection.close()
                finally:
                    self._slots.release()

    def _handle(self, connection):
        try:
            connection.settimeout(self.response_seconds)
            credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            _, uid, _ = struct.unpack("3i", credentials)
            principal = self.peer_map.get(uid)
            if not isinstance(principal, Principal):
                raise JobError("UNAUTHORIZED", "OS peer has no admitted principal")
            request = strict_loads(_read_frame(connection, MAX_REQUEST_BYTES))
            if type(request) is not dict or set(request) != {"tool", "arguments"} or not isinstance(request["tool"], str):
                raise JobError("INVALID_REQUEST", "Local request must name only tool and arguments")
            result = self.broker.call(request["tool"], request["arguments"], principal)
            _send_frame(connection, {"result": result})
        except JobError as error:
            try:
                _send_frame(connection, {"error": error.as_dict()})
            except (OSError, JobError):
                pass
        except (OSError, ValueError, TypeError):
            try:
                _send_frame(connection, {"error": {"code": "IO_UNCERTAIN", "message": "Local request outcome is unresolved"}})
            except (OSError, JobError):
                pass
        finally:
            try:
                connection.close()
            finally:
                self._slots.release()

    def close(self):
        self._closed.set()
        if self._listener is not None:
            self._listener.close()
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
    try:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(timeout)
        connection.connect(str(socket_path))
        _send_frame(connection, {"tool": tool, "arguments": arguments})
        result = json.loads(_read_frame(connection, MAX_RESPONSE_BYTES))
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
            state.close()
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
