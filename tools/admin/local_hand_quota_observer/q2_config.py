"""Pinned, root-owned Q2 installation. Load only before listening or in a worker.

Nothing in this file provisions a host or obtains authority from a wire request.
The administrator supplies existing finite grants, storage and process parents.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import PurePosixPath

from local_hand_jobs import quota_contract as q, quota_grant as g
from .protected_inputs import open_protected, read_fd, read_protected

LIMIT = 2 * 1024 * 1024


def identity(value, *, path=True):
    q._keys(value, {"device", "inode", *({"path"} if path else set())})
    q.integer(value["device"])
    q.integer(value["inode"], 1)
    if path:
        q.canonical_path(value["path"])
    return value


def overlap(a, b):
    a, b = PurePosixPath(a), PurePosixPath(b)
    return a == b or a in b.parents or b in a.parents


@dataclass(frozen=True, slots=True)
class Config:
    wire: bytes
    path: str

    @property
    def digest(self):
        return hashlib.sha256(self.wire).hexdigest()

    def data(self):
        return q._load(self.wire, LIMIT, 18)

    def active(self):
        return self.grants()[self.data()["service"]["request_id"]]

    def grants(self):
        return {key: g.decode_grant(q._canonical(value, g.GRANT_LIMIT))
                for key, value in self.data()["grants"].items()}


def decode(raw, path, digest):
    q.canonical_path(path)
    q.require(hashlib.sha256(raw).hexdigest() == digest, "CONFIG_DIGEST")
    v = q._load(raw, LIMIT, 18)
    q._keys(v, {"schema", "source_commit", "tools_path", "entry", "package_files", "programs", "abi",
        "initial_userns", "capacity", "grants", "peers", "journal", "evidence", "session", "service"})
    q.require(v["schema"] == "local-hand-quota-service/v1", "CONFIG_SCHEMA")
    q.match(v["source_commit"], r"[0-9a-f]{40}")
    q.canonical_path(v["tools_path"])
    q._keys(v["programs"], {"python", "native", "systemctl", "systemd_run"})
    for item in (v["entry"], *v["programs"].values()):
        q._keys(item, {"path", "sha256"})
        q.canonical_path(item["path"])
        q.match(item["sha256"], r"[0-9a-f]{64}")
    q.require(v["entry"]["path"] == v["tools_path"] + "/admin/local_hand_quota_observer/q2_entry.py", "ENTRY_PATH")
    files = v["package_files"]
    q.require(type(files) is dict and 1 <= len(files) <= 256, "PACKAGE_COUNT")
    for name, checksum in files.items():
        q.match(name, r"(?:[a-z_][a-z0-9_]*/)+[a-z_][a-z0-9_]*\.py")
        q.match(checksum, r"[0-9a-f]{64}")
        if name.endswith("/__init__.py"):
            q.require(name[:-12] + ".py" not in files, "PACKAGE_ALIAS")
    for name in ("q2_config", "q2_runtime", "q2_listener", "q2_journal", "q2_service"):
        q.require("admin/local_hand_quota_observer/" + name + ".py" in files, "PACKAGE_MISSING")
    q._keys(v["abi"], {"fsxattr_bytes", "dqblk_bytes", "qstatv_bytes"})
    for number in v["abi"].values():
        q.integer(number, 1, 1024)
    q.require(v["abi"]["fsxattr_bytes"] == 28, "ABI")
    identity(v["initial_userns"], path=False)
    capacity = g.decode_capacity(q._canonical(v["capacity"], g.GRANT_LIMIT))
    q.require(type(v["grants"]) is dict and 0 < len(v["grants"]) <= g.MAX_GRANTS, "GRANT_COUNT")
    grants = [g.decode_grant(q._canonical(item, g.GRANT_LIMIT)) for item in v["grants"].values()]
    q.require(list(v["grants"]) == [item.request.as_dict()["request_id"] for item in grants], "GRANT_KEY")
    # Provisioned grants, including requests not yet used, must fit together.
    g.check_capacity(capacity, grants)
    q._keys(v["peers"], set(v["grants"]))
    q._keys(v["journal"], {"path", "pin"})
    q.canonical_path(v["journal"]["path"])
    pin = v["journal"]["pin"]
    q._keys(pin, {"directory", "files"})
    q._keys(pin["files"], {"lock", "policy", *(key + ".cell" for key in v["grants"])})
    for item in (pin["directory"], *pin["files"].values()):
        identity(item, path=False)
    identity(v["evidence"])
    identity(v["session"])
    service = v["service"]
    q._keys(service, {"request_id", "parent", "control_path", "accept_ns", "end_ns", "max_connections"})
    q.require(service["request_id"] in v["grants"], "SERVICE_REQUEST")
    identity(service["parent"])
    q.require(PurePosixPath(service["parent"]["path"]).parent == PurePosixPath("/"), "SERVICE_PARENT")
    q.match(PurePosixPath(service["parent"]["path"]).name, r"lhq[a-z0-9]+\.slice")
    q.require(len(q.canonical_path(service["control_path"]).encode()) <= 107, "ENDPOINT_LENGTH")
    q.integer(service["accept_ns"], 1, 2_000_000_000)
    q.integer(service["max_connections"], 1, g.MAX_GRANTS)
    q.integer(service["end_ns"], 1)
    endpoints = {}
    protected = [path, v["journal"]["path"], v["evidence"]["path"], v["session"]["path"],
                 service["control_path"], v["tools_path"], *(item["path"] for item in v["programs"].values())]
    for i, first in enumerate(protected):
        q.require(all(not overlap(first, other) for other in protected[i + 1:]), "CONFIG_GEOMETRY")
    for grant in grants:
        data = grant.as_dict(); request = grant.request.as_dict()
        peer = v["peers"][request["request_id"]]
        q._keys(peer, {"parent", "command_sha256", "executable"})
        identity(peer["parent"])
        identity(peer["executable"])
        q.match(peer["command_sha256"], r"[0-9a-f]{64}")
        q.require(data["management_parent"] == service["parent"], "MANAGEMENT_PARENT")
        q.require(not overlap(data["query_parent"]["path"], service["parent"]["path"])
                  and not overlap(peer["parent"]["path"], data["query_parent"]["path"])
                  and not overlap(peer["parent"]["path"], service["parent"]["path"]), "CGROUP_OVERLAP")
        q.match(PurePosixPath(data["query_parent"]["path"]).name, r"lhq[a-z0-9]+\.slice")
        q.require(PurePosixPath(data["query_parent"]["path"]).parent == PurePosixPath("/"), "QUERY_PARENT")
        if request["request_id"] == service["request_id"]:
            q.require(data["management"]["issued_ns"] < service["end_ns"] <= request["deadline_ns"], "SERVICE_DEADLINE")
        endpoint = data["endpoint"]
        q.require(endpoint["uid"] == 0 and endpoint["gid"] > 0, "ENDPOINT_OWNER")
        q.require(endpoints.setdefault(endpoint["path"], endpoint) == endpoint, "ENDPOINT_ALIAS")
        q.require(next(r for r in data["roots"] if r["role"] == "work")["gid"] == endpoint["gid"], "ENDPOINT_GROUP")
        for stage in data["management"]["stages"].values():
            q.require(stage["cpu_ns"] >= 1_000_000_000 and stage["memory_bytes"] >= 16 * 1024**2
                      and 2 <= stage["pids"] <= 32 and stage["output_bytes"] >= q.RESPONSE_LIMIT, "RUNTIME_LIMITS")
        for root in g.root_paths(data["allocation"]).values():
            q.require(all(not overlap(root, other) for other in protected + list(endpoints)), "ROOT_CONFIG_OVERLAP")
        paths = list(g.root_paths(data["allocation"]).values())
        q.require(all(not overlap(a, b) for i, a in enumerate(paths) for b in paths[i + 1:]), "ROOT_OVERLAP")
    roots = [p for grant in grants for p in g.root_paths(grant.as_dict()["allocation"]).values()]
    for endpoint in endpoints:
        q.require(all(not overlap(endpoint, p) for p in protected + roots), "ENDPOINT_GEOMETRY")
    return Config(raw, path)


def pinned_directory(value):
    fd = open_protected(value["path"], directory=True)
    info = os.fstat(fd)
    if (info.st_dev, info.st_ino) != (value["device"], value["inode"]):
        os.close(fd)
        raise q.QuotaError("DIRECTORY_CHANGED")
    return fd


def executable(item):
    fd = open_protected(item["path"])
    try:
        before = os.fstat(fd)
        q.require(before.st_mode & 0o111 and not before.st_mode & 0o6000, "EXECUTABLE_MODE")
        raw = read_fd(fd, 64 * 1024 * 1024)
        q.require(hashlib.sha256(raw).hexdigest() == item["sha256"] and raw.startswith(b"\x7fELF"), "EXECUTABLE_DIGEST")
        after = os.fstat(fd)
        q.require(all(getattr(before, name) == getattr(after, name) for name in
            ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")), "EXECUTABLE_CHANGED")
        return fd
    except BaseException:
        os.close(fd)
        raise


def load(path, digest):
    config = decode(read_protected(path, LIMIT), path, digest)
    for item in config.data()["programs"].values():
        os.close(executable(item))
    return config
