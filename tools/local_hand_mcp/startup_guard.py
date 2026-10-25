"""Bind a nonroot MCP listener to a privileged, finite startup selection."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import stat

from local_hand.provenance import full_payload_digest
from local_hand_jobs import startup
from local_hand_jobs.contract import JobError


def invocation_paths(config, args):
    keys = {"schema", "node_id", "deployment_digest", "payload_digest", "manager_socket", "inputs", "mode", "port"}
    if (not isinstance(config, dict) or not keys <= set(config) or set(config) - keys - {"unix_socket"}
            or config["schema"] != "local-hand-mcp-startup/v1"):
        raise JobError("STARTUP_MISMATCH", "Invalid MCP startup configuration")
    mode = next((name for name in ("resident", "prepared_task", "session", "read_only") if getattr(args, name, None)), None)
    if mode not in {'resident','prepared_task','read_only'}:
        raise JobError('STARTUP_MISMATCH','This MCP mode has no guarded final task admission')
    paths = {"config": args.config, "auth_config": args.auth_config}
    if mode != "read_only":
        paths[mode] = getattr(args, mode)
    if (config["mode"] != mode or config["port"] != args.port or config["inputs"] != paths
            or not Path(config["manager_socket"]).is_absolute()):
        raise JobError("STARTUP_MISMATCH", "Actual MCP invocation differs from the selected inputs")
    validate_listener(config)
    selected_socket = config.get("unix_socket")
    actual_socket = getattr(args, "http_socket", None)
    if (bool(selected_socket) != bool(actual_socket) or selected_socket is not None and
            selected_socket != {"path": actual_socket, "mode": getattr(args, "http_socket_mode", 0o660)}):
        raise JobError("STARTUP_MISMATCH", "Actual MCP Unix listener differs from its selected binding")
    if any(not isinstance(path, str) or not Path(path).is_absolute() or ".." in Path(path).parts for path in paths.values()):
        raise JobError("STARTUP_MISMATCH", "MCP input paths must be absolute")
    return paths


def validate_listener(config):
    unix = config.get("unix_socket")
    if unix is None:
        if type(config.get("port")) is not int or not 1 <= config["port"] <= 65535:
            raise JobError("STARTUP_MISMATCH", "Invalid loopback port")
    elif (not isinstance(unix, dict) or set(unix) != {"path", "mode"} or config.get("port") is not None
            or not isinstance(unix.get("path"), str) or not Path(unix["path"]).is_absolute()
            or str(Path(unix["path"])) != unix["path"] or ".." in Path(unix["path"]).parts
            or len(os.fsencode(unix["path"])) > 107 or type(unix.get("mode")) is not int
            or unix["mode"] not in {0o600, 0o660, 0o666}):
        raise JobError("STARTUP_MISMATCH", "Invalid protected Unix listener")


def listener_binding(config):
    validate_listener(config)
    return {"port": config["port"], **({"unix_socket": config["unix_socket"]} if config.get("unix_socket") else {})}


def bind_unix(spec):
    """Exact protected listener path; never unlink regular files or a live peer."""
    path = Path(spec["path"])
    directory = startup._protected_directory(path.parent, owner_uid=os.geteuid())
    os.close(directory)
    try:
        before = path.lstat()
    except FileNotFoundError:
        before = None
    if before is not None:
        if not stat.S_ISSOCK(before.st_mode) or before.st_uid != os.geteuid() or stat.S_IMODE(before.st_mode) != spec["mode"]:
            raise JobError("STARTUP_MISMATCH", "Existing HTTP listener is not the selected socket")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(.2)
            try:
                probe.connect(str(path))
            except ConnectionRefusedError:
                current = path.lstat()
                if (current.st_dev, current.st_ino, current.st_ctime_ns) != (before.st_dev, before.st_ino, before.st_ctime_ns):
                    raise JobError("STARTUP_MISMATCH", "Stale listener changed before removal")
                path.unlink()
            else:
                raise JobError("STARTUP_MISMATCH", "HTTP socket still has a live listener")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    binding = None
    def cleanup():
        listener.close()
        try:
            current = path.lstat()
            if binding and (current.st_dev, current.st_ino) == binding:
                path.unlink()
        except FileNotFoundError:
            pass
    try:
        listener.bind(str(path))
        current = path.lstat(); binding = (current.st_dev, current.st_ino)
        path.chmod(spec["mode"])
        listener.listen(128); listener.setblocking(False)
        return listener, cleanup
    except BaseException:
        cleanup(); raise


def input_binding(config, args, *, owner_uid=None):
    owner_uid = os.geteuid() if owner_uid is None else owner_uid
    paths = invocation_paths(config, args)
    inputs = {name: {"path": path, "sha256": hashlib.sha256(
        startup.protected_read(path, owner_uid=owner_uid)).hexdigest()} for name, path in paths.items()}
    return {"inputs": inputs, "mode": config["mode"], **listener_binding(config)}


@contextmanager
def guard(args):
    """Initialization and bind occur inside the same admission lease.

    The configuration hashes describe files actually read by this invocation.
    Cooperative configuration writers must revoke startup selection under the
    admission lock before modifying any member of this set.
    """
    if not args.startup_config:
        yield None
        return
    try:
        raw = startup.protected_read(args.startup_config, owner_uid=os.geteuid())
        config = json.loads(raw, object_pairs_hook=startup._unique)
        invocation_paths(config, args)
    except (ValueError, TypeError, KeyError) as exc:
        raise JobError("STARTUP_MISMATCH", "Invalid MCP startup binding") from exc
    listener = None
    cleanup = None
    try:
        with startup.remote_authorization(config["manager_socket"]) as (selection, acknowledged):
            binding = input_binding(config, args)
            members = {item["path"]: item["sha256"] for item in selection["members"]}
            # The guard itself was first read to find the management endpoint.
            # Re-bind those bytes to the complete selected set under its lock.
            if (startup.protected_read(args.startup_config, owner_uid=os.geteuid()) != raw
                    or members.get(args.startup_config) != hashlib.sha256(raw).hexdigest()
                    or any(members.get(item["path"]) != item["sha256"] for item in binding["inputs"].values())):
                raise JobError("STARTUP_MISMATCH", "MCP inputs are outside the complete selected configuration set")
            payload = full_payload_digest()
            proof = {**startup.instance(os.getpid()), "component": "mcp", "entry": "local",
                     "configuration_digest": startup.digest(binding), "payload_digest": payload,
                     "node_id": config["node_id"], "deployment_digest": config["deployment_digest"],
                     "invocation_id": os.environ.get("INVOCATION_ID"), "protocol_ready": False}
            expected = selection["components"].get("mcp", {})
            if (payload != config["payload_digest"] or config["node_id"] != selection["node_id"]
                    or config["deployment_digest"] != selection["deployment_digest"]
                    or any(proof[key] != expected.get(key) for key in ("configuration_digest", "payload_digest"))):
                raise JobError("STARTUP_MISMATCH", "MCP loaded configuration or release differs from selection")
            result = {"proof": proof, "listener": None, "cleanup": None}
            def bind():
                nonlocal listener, cleanup
                if listener is not None:
                    raise JobError("STARTUP_MISMATCH", "MCP listener was already bound")
                # Recheck the snapshot while still holding the same lease.
                if (input_binding(config, args) != binding
                        or startup.protected_read(args.startup_config, owner_uid=os.geteuid()) != raw):
                    raise JobError("STARTUP_MISMATCH", "MCP inputs changed during initialization")
                if config.get("unix_socket"):
                    listener, cleanup = bind_unix(config["unix_socket"])
                else:
                    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    listener.bind(("127.0.0.1", args.port))
                    listener.listen(128)
                    listener.setblocking(False)
                    cleanup = listener.close
                result["listener"] = listener
                result["cleanup"] = cleanup
                acknowledged(proof)
                return listener
            result["bind"] = bind
            yield result
    except BaseException:
        # Includes a missing ACK or failure from the outer authorization
        # context's __exit__, not just failures thrown back through yield.
        if cleanup is not None:
            cleanup()
        elif listener is not None:
            listener.close()
        raise
