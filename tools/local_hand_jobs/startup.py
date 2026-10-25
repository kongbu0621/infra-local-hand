"""Protected startup selections shared by deployment and actual listeners.

An ExecStartPre check alone is insufficient.  The listener holds the admission
lock while verifying the configuration it already loaded and opening its socket.
The coordinator revokes a candidate selection under this same lock before it
changes any member of the configuration set.  This is a cooperative writer
protocol, not protection against another privileged administrator.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import time
import uuid

from .contract import JobError

SCHEMA = "local-hand-startup-selection/v1"
MAX_BYTES = 4 * 1024 * 1024
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def boot_id():
    value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    if re.fullmatch(r"[0-9a-f-]{36}", value) is None:
        raise JobError("STARTUP_UNKNOWN", "Boot identity is unavailable")
    return value


def _protected_directory(path, *, owner_uid=0):
    """Pin every ancestor; a writable grandparent cannot replace the leaf."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or str(path).startswith("//"):
        raise JobError("STARTUP_UNKNOWN", "Startup paths must be absolute")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd); fd = child
            info = os.fstat(fd)
            if (info.st_uid not in (0, owner_uid) or info.st_mode & 0o022
                    and not (info.st_uid == 0 and info.st_mode & stat.S_ISVTX)):
                raise ValueError("unprotected ancestor")
        info = os.fstat(fd)
        if info.st_uid not in (0, owner_uid) or info.st_mode & 0o022:
            raise ValueError("unprotected parent")
        return fd
    except BaseException:
        os.close(fd)
        raise


def protected_read(path, *, owner_uid=0, maximum=MAX_BYTES):
    path = Path(path)
    directory = None
    try:
        directory = _protected_directory(path.parent, owner_uid=owner_uid)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or before.st_uid not in (0, owner_uid) or before.st_mode & 0o022
                    or before.st_size > maximum):
                raise ValueError("unprotected or oversized file")
            chunks = []; remaining = maximum + 1
            while remaining:
                chunk = os.read(fd, min(remaining, 65536))
                if not chunk:
                    break
                chunks.append(chunk); remaining -= len(chunk)
            raw = b"".join(chunks)
            after = os.fstat(fd)
            named = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            fields = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
            if (len(raw) > maximum or any(getattr(before, key) != getattr(after, key) for key in fields)
                    or (named.st_dev, named.st_ino) != (after.st_dev, after.st_ino)):
                raise ValueError("changed file")
            return raw
        finally:
            os.close(fd)
    except (OSError, ValueError) as exc:
        raise JobError("STARTUP_UNKNOWN", "Cannot verify a protected startup object") from exc
    finally:
        if directory is not None:
            os.close(directory)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def read_selection(path, *, owner_uid=0):
    try:
        value = json.loads(protected_read(path, owner_uid=owner_uid), object_pairs_hook=_unique)
        validate(value)
        return value
    except (ValueError, TypeError, KeyError) as exc:
        raise JobError("STARTUP_UNKNOWN", "Startup selection is invalid") from exc


def validate(value):
    if (not isinstance(value, dict) or set(value) != {
            "schema", "node_id", "deployment_digest", "decision_id", "mode", "owner",
            "members", "components", "permit"} or value["schema"] != SCHEMA
            or value["mode"] not in {"blocked", "candidate", "stable"}
            or not isinstance(value["node_id"], str) or not value["node_id"]
            or not isinstance(value["deployment_digest"], str)
            or _HEX.fullmatch(value["deployment_digest"]) is None
            or not isinstance(value["components"], dict) or not 1 <= len(value["components"]) <= 16
            or not isinstance(value["members"], list) or not 1 <= len(value["members"]) <= 64):
        raise ValueError("selection schema")
    paths = set()
    for member in value["members"]:
        if (not isinstance(member, dict) or set(member) != {"path", "sha256"}
                or not isinstance(member["path"], str) or not Path(member["path"]).is_absolute()
                or ".." in Path(member["path"]).parts or member["path"] in paths
                or not isinstance(member["sha256"], str) or _HEX.fullmatch(member["sha256"]) is None):
            raise ValueError("member binding")
        paths.add(member["path"])
    for name, component in value["components"].items():
        if (not isinstance(name, str) or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) is None
                or not isinstance(component, dict) or set(component) != {
                    "configuration_digest", "payload_digest", "entry", "running"}
                or any(not isinstance(component[k], str) or _HEX.fullmatch(component[k]) is None
                       for k in ("configuration_digest", "payload_digest"))
                or component["entry"] not in {"local", "public"}
                or type(component["running"]) is not bool):
            raise ValueError("component binding")
    if value["mode"] == "stable":
        if not isinstance(value["decision_id"], str) or not value["decision_id"] or value["permit"] is not None:
            raise ValueError("stable decision binding")
    elif value["mode"] == "candidate":
        permit = value["permit"]
        if (not isinstance(value["owner"], str) or not value["owner"] or value["decision_id"] is not None
                or not isinstance(permit, dict) or set(permit) != {"boot_id", "attempt_id", "claims"}
                or any(not isinstance(permit[k], str) or not permit[k] for k in ("boot_id", "attempt_id"))
                or not isinstance(permit["claims"], dict) or set(permit["claims"]) - set(value["components"])):
            raise ValueError("candidate permit binding")
        for claim in permit["claims"].values():
            if (not isinstance(claim, dict) or set(claim) != {"pid", "start_ticks", "boot_id"}
                    or type(claim["pid"]) is not int or claim["pid"] <= 0
                    or type(claim["start_ticks"]) is not int or claim["start_ticks"] <= 0
                    or claim["boot_id"] != permit["boot_id"]):
                raise ValueError("candidate instance binding")
    elif value["permit"] is not None:
        raise ValueError("blocked permit")


def verify_members(value, *, owner_uid=0):
    validate(value)
    total = 0
    for member in value["members"]:
        raw = protected_read(member["path"], owner_uid=owner_uid)
        total += len(raw)
        if total > 64 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != member["sha256"]:
            raise JobError("STARTUP_MISMATCH", "The complete configuration set differs from the selection")


def _write_selection(path, value, *, owner_uid=0):
    directory = _protected_directory(path.parent, owner_uid=owner_uid)
    temporary = "." + path.name + "." + uuid.uuid4().hex
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            raw = canonical(value) + b"\n"
            offset = 0
            while offset < len(raw):
                count = os.write(fd, raw[offset:])
                if count <= 0:
                    raise OSError("short startup descriptor write")
                offset += count
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        os.close(directory)


def _confirm_selection(path, *, owner_uid=0):
    directory = _protected_directory(Path(path).parent, owner_uid=owner_uid)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def publish(path, value, gate, *, expected_digest, owner_uid=0, maintenance_owner=None):
    """CAS a descriptor under the admission lock. Caller persists intent first.

    Bootstrap is explicit: expected_digest=None requires an absent descriptor;
    all normal transitions require its previous exact digest. A repeated write
    only syncs the directory and never overwrites another selection.
    """
    validate(value)
    path = Path(path)
    with gate.admission_lock() as state:
        if value["node_id"] != state["node_id"]:
            raise JobError("STARTUP_MISMATCH", "Startup selection belongs to another node")
        if value["mode"] in {"blocked", "candidate"} and (
                state["state"] != "CLOSED" or state["owner"] != value["owner"]):
            raise JobError("STARTUP_MISMATCH", "Selection requires its current maintenance owner")
        try:
            current = read_selection(path, owner_uid=owner_uid)
        except JobError:
            # Missing is the only admissible bootstrap state. Dangling symlinks,
            # unreadable and malformed descriptors cannot be replaced here.
            try:
                path.lstat()
            except FileNotFoundError:
                current = None
            else:
                raise
        if value['mode']=='stable':
            if current is None:
                if (expected_digest is not None or state['state']!='OPEN' or maintenance_owner is not None
                        or state['deployment_digest']!=value['deployment_digest']
                        or state['decision_id']!=value['decision_id']):
                    raise JobError('STARTUP_MISMATCH','Stable bootstrap requires the exact initialized open decision')
            elif (state['state']!='CLOSED' or not isinstance(maintenance_owner,str)
                    or not maintenance_owner or state['owner']!=maintenance_owner):
                raise JobError('STARTUP_MISMATCH','Stable publication requires the current maintenance owner')
        if current == value:
            _confirm_selection(path, owner_uid=owner_uid)
            return digest(value)
        if (None if current is None else digest(current)) != expected_digest:
            raise JobError("STARTUP_CONFLICT", "Startup selection was independently changed")
        parent = path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid not in (0, owner_uid) or parent.st_mode & 0o022:
            raise JobError("STARTUP_UNKNOWN", "Startup descriptor directory is not protected")
        if value["mode"] != "blocked":
            verify_members(value, owner_uid=owner_uid)
        _write_selection(path, value, owner_uid=owner_uid)
        return digest(value)


def instance(pid):
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        fields = raw[raw.rindex(")") + 2:].split()
        return {"pid": pid, "start_ticks": int(fields[19]), "boot_id": boot_id()}
    except (OSError, ValueError, IndexError) as exc:
        raise JobError("STARTUP_UNKNOWN", "Listener process identity cannot be verified") from exc


def _admit_selection(path, state, component, pid, *, owner_uid=0):
    value = read_selection(path, owner_uid=owner_uid)
    verify_members(value, owner_uid=owner_uid)
    selected = value["components"].get(component)
    if (value["node_id"] != state["node_id"] or value["mode"] == "blocked"
            or not selected or not selected["running"]):
        raise JobError("STARTUP_MISMATCH", "Component has no active startup selection")
    if value["mode"] == "candidate":
        if (state["state"] != "CLOSED" or state["owner"] != value["owner"]
                or value["permit"]["boot_id"] != boot_id()):
            raise JobError("STARTUP_MISMATCH", "Candidate startup permit is not current")
        claim = instance(pid)
        previous = value["permit"]["claims"].get(component)
        if previous is not None and previous != claim:
            raise JobError("STARTUP_MISMATCH", "Candidate permit is already bound to another instance")
        if previous is None:
            value["permit"]["claims"][component] = claim
            _write_selection(Path(path), value, owner_uid=owner_uid)
        else:
            _confirm_selection(path, owner_uid=owner_uid)
    elif (state["state"] not in {"OPEN", "CLOSED"} or
          state["state"] == "OPEN" and state["deployment_digest"] != value["deployment_digest"]):
        raise JobError("STARTUP_MISMATCH", "Admission does not select this stable deployment")
    return value


@contextmanager
def authorize(config, proof, gate):
    """Keep the verified loaded configuration bound through actual bind/listen."""
    maintenance = config.get("maintenance")
    if maintenance is None:
        # Legacy mode is explicit in the deployment support profile. It is not
        # evidence that an old unguarded listener can join the new protocol.
        yield None
        return
    path = maintenance.get("startup_descriptor")
    with gate.admission_lock() as state:
        value = _admit_selection(path, state, proof.get("component"), os.getpid(), owner_uid=gate.owner_uid)
        component = value["components"].get(proof.get("component"))
        if (value["mode"] == "blocked" or not component or not component["running"]
                or value["node_id"] != proof.get("node_id") or value["node_id"] != state["node_id"]
                or value["deployment_digest"] != proof.get("deployment_digest")
                or any(component[key] != proof.get(key) for key in ("configuration_digest", "payload_digest"))):
            raise JobError("STARTUP_MISMATCH", "Loaded configuration is not selected for startup")
        if value["mode"] == "candidate":
            if (state["state"] != "CLOSED" or state["owner"] != value["owner"]
                    or value["permit"]["boot_id"] != boot_id()
                    or proof.get("entry", "local") != "local"):
                raise JobError("STARTUP_MISMATCH", "Candidate startup requires current local-only maintenance")
        elif state["state"] not in {"OPEN", "CLOSED"}:
            raise JobError("STARTUP_UNKNOWN", "Startup admission state is unknown")
        elif state["state"] == "OPEN" and state["deployment_digest"] != value["deployment_digest"]:
            raise JobError("STARTUP_MISMATCH", "Open admission does not select this deployment")
        elif proof.get("entry", "local") == "public" and component["entry"] != "public":
            raise JobError("STARTUP_MISMATCH", "Public protocol was not selected")
        yield {"descriptor_digest": digest(value), "mode": value["mode"],
               "decision_id": value["decision_id"], "deployment_digest": value["deployment_digest"]}


def _frame_send(connection, value, deadline):
    if time.monotonic() >= deadline:
        raise JobError("STARTUP_UNKNOWN", "Startup handshake expired")
    raw = canonical(value)
    if len(raw) > MAX_BYTES:
        raise JobError("STARTUP_UNKNOWN", "Startup handshake exceeds its bound")
    connection.settimeout(max(0.001, deadline - time.monotonic()))
    connection.sendall(struct.pack("!I", len(raw)) + raw)


def _frame_read(connection, deadline):
    def receive(count):
        raw = bytearray()
        while len(raw) < count:
            connection.settimeout(max(0.001, deadline - time.monotonic()))
            if time.monotonic() >= deadline:
                raise JobError("STARTUP_UNKNOWN", "Startup handshake expired")
            block = connection.recv(min(65536, count - len(raw)))
            if not block:
                raise JobError("STARTUP_UNKNOWN", "Startup handshake was interrupted")
            raw.extend(block)
        return bytes(raw)
    size = struct.unpack("!I", receive(4))[0]
    if size > MAX_BYTES:
        raise JobError("STARTUP_UNKNOWN", "Startup handshake exceeds its bound")
    try:
        return json.loads(receive(size), object_pairs_hook=_unique)
    except (ValueError, UnicodeError) as exc:
        raise JobError("STARTUP_UNKNOWN", "Invalid startup handshake") from exc


def serve_authorization(connection, config, gate, *, peer_pid):
    """Root manager's fixed MCP startup handshake; caller already checked peer.

    Only a configuration digest acknowledgement follows. It grants no business
    permissions. The nonroot caller must close its socket if this handshake
    fails, and cannot start serving before the final acknowledgement.
    """
    deadline = time.monotonic() + 30
    with gate.admission_lock() as state:
        selected = _admit_selection(config["maintenance"]["startup_descriptor"], state, "mcp", peer_pid,
                                    owner_uid=gate.owner_uid)
        _frame_send(connection, {"admitted": True, "selection": selected}, deadline)
        request = _frame_read(connection, deadline)
        expected = selected["components"]["mcp"]
        if (not isinstance(request, dict) or set(request) != {"action", "proof"}
                or request["action"] != "startup_bound" or not isinstance(request["proof"], dict)):
            raise JobError("STARTUP_MISMATCH", "Startup completion is not bound")
        proof = request["proof"]
        if (proof.get("component") != "mcp" or proof.get("pid") != peer_pid or proof.get("boot_id") != boot_id()
                or proof.get("start_ticks") != instance(peer_pid)["start_ticks"]
                or proof.get("node_id") != selected["node_id"]
                or proof.get("deployment_digest") != selected["deployment_digest"]
                or proof.get("entry") != "local"
                or any(proof.get(key) != expected[key] for key in ("configuration_digest", "payload_digest"))):
            raise JobError("STARTUP_MISMATCH", "MCP loaded configuration differs from its selection")
        _frame_send(connection, {"bound": True, "descriptor_digest": digest(selected)}, deadline)


@contextmanager
def remote_authorization(socket_path):
    """Hold the privileged startup guard without exposing its private gate DB."""
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    deadline = time.monotonic() + 30
    try:
        connection.settimeout(30)
        connection.connect(str(socket_path))
        _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
        if uid != 0:
            raise JobError("STARTUP_MISMATCH", "Startup manager is not the root service")
        _frame_send(connection, {"action": "startup_authorize", "component": "mcp"}, deadline)
        response = _frame_read(connection, deadline)
        if not isinstance(response, dict) or set(response) != {"admitted", "selection"} or response.get("admitted") is not True:
            raise JobError("STARTUP_MISMATCH", "MCP startup was not admitted")
        selected = response["selection"]
        validate(selected)
        acknowledged = False
        def bound(proof):
            nonlocal acknowledged
            _frame_send(connection, {"action": "startup_bound", "proof": proof}, deadline)
            result = _frame_read(connection, deadline)
            if (not isinstance(result, dict) or set(result) != {"bound", "descriptor_digest"}
                    or result.get("bound") is not True or result.get("descriptor_digest") != digest(selected)):
                raise JobError("STARTUP_MISMATCH", "MCP startup acknowledgement is missing")
            acknowledged = True
        yield selected, bound
        if not acknowledged:
            raise JobError("STARTUP_UNKNOWN", "MCP socket startup was not acknowledged")
    finally:
        connection.close()
