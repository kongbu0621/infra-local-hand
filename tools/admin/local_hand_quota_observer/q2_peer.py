"""Linux peer attestation performed only by the supervised admission worker."""
import hashlib
import os
import select
import socket
import struct

from local_hand_jobs import quota_contract as q
from . import q2_config as c, q2_runtime as runtime
from .systemd_runtime import _fixed_read, _boot_id


def credentials(connection):
    q.require(connection.family == socket.AF_UNIX, "PEER_FAMILY")
    return struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))


def inspect(config, connection):
    grant = config.active(); data = grant.as_dict(); req = grant.request.as_dict()
    policy = config.data()["peers"][req["request_id"]]
    pid, uid, gid = credentials(connection)
    root = next(r for r in data["roots"] if r["role"] == "work")
    q.require((uid, gid) == (root["uid"], root["gid"]) and pid > 1, "BOOTSTRAP_CREDENTIALS")
    pidfd = os.pidfd_open(pid, 0)
    try:
        poll = select.poll(); poll.register(pidfd, select.POLLIN)
        q.require(not poll.poll(0), "PEER_EXITED")
        base = "/proc/" + str(pid)
        stat_before = _fixed_read(base + "/stat", 8192)
        fields = stat_before[stat_before.rfind(b")") + 2:].split()
        q.require(len(fields) >= 20, "PEER_STAT")
        start = int(fields[19])
        expected_unit = "lhj-" + hashlib.sha256((req["execution_id"] + ":bootstrap").encode()).hexdigest() + ".service"
        group = policy["parent"]["path"] + "/" + expected_unit
        q.require(_fixed_read(base + "/cgroup", 4096) == ("0::" + group + "\n").encode(), "PEER_CGROUP")
        parent = c.pinned_directory(dict(policy["parent"], path="/sys/fs/cgroup" + policy["parent"]["path"]))
        os.close(parent)
        executable = os.stat(base + "/exe")
        fixed = policy["executable"]
        q.require((executable.st_dev, executable.st_ino) == (fixed["device"], fixed["inode"]), "PEER_EXECUTABLE")
        fd = c.open_protected(fixed["path"])
        try:
            info = os.fstat(fd)
            q.require((info.st_dev, info.st_ino) == (fixed["device"], fixed["inode"]), "PEER_EXECUTABLE_CHANGED")
        finally:
            os.close(fd)
        q.require(hashlib.sha256(_fixed_read(base + "/cmdline", 131072)).hexdigest() == policy["command_sha256"], "PEER_COMMAND")
        status = dict(line.split(":", 1) for line in _fixed_read(base + "/status", 16384).decode("ascii").splitlines())
        q.require([int(x) for x in status["Uid"].split()] == [uid] * 4
                  and [int(x) for x in status["Gid"].split()] == [gid] * 4, "PEER_IDS")
        q.require(all(int(status[key], 16) == 0 for key in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"))
                  and status["NoNewPrivs"].strip() == "1", "PEER_CAPABILITIES")
        ns = os.stat(base + "/ns/user"); initial = config.data()["initial_userns"]
        q.require((ns.st_dev, ns.st_ino) != (initial["device"], initial["inode"]), "PEER_PRIVATE_USERNS")
        entries = _fixed_read(base + "/environ", 131072).split(b"\0")
        inv = [item[len(b"INVOCATION_ID="):] for item in entries if item.startswith(b"INVOCATION_ID=")]
        q.require(len(inv) == 1, "PEER_INVOCATION")
        invocation = q.match(inv[0].decode("ascii"), r"[0-9a-f]{32}")
        q.require(_fixed_read(base + "/stat", 8192).rsplit(b") ", 1)[1].split()[19] == str(start).encode()
                  and not poll.poll(0) and credentials(connection) == (pid, uid, gid)
                  and _boot_id() == req["boot_id"], "PEER_CHANGED")
        return {"uid": uid, "gid": gid, "pid": pid, "start_ticks": start, "boot_id": req["boot_id"],
                "unit": expected_unit, "invocation_id": invocation, "cgroup": group, "parent": policy["parent"]}
    finally:
        os.close(pidfd)


def control(config, connection, role):
    pid, uid, gid = credentials(connection)
    expected_gid = config.active().as_dict()["endpoint"]["gid"] if role == "listener" else 0
    q.require(uid == 0 and gid == expected_gid and pid > 1, "CONTROL_PEER")
    expected = runtime.parent(config, role)["path"] + "/" + runtime.name(config, role)
    q.require(_fixed_read("/proc/" + str(pid) + "/cgroup", 4096) == ("0::" + expected + "\n").encode(), "CONTROL_CGROUP")
    return pid
