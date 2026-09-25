"""Fixed Q2 system-manager adapter; invoke only inside the admission unit.

Reuses the bounded Q1 manager transport and native report validator, never its
single-root ledger/tickets. One Q2 query unit contains at most four fixed native
children; an uncertain child or manager client prevents further launches.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
import re
import stat
from pathlib import PurePosixPath
import time
from types import SimpleNamespace

from local_hand_jobs import quota_contract as q, quota_grant as g
from . import admission as a, q2_config as c, worker
from .systemd_runtime import (Capture, Q1Controller, boottime_ns, _boot_id,
                             _own_cgroup, _fixed_read, SHOW_FIELDS)


def name(config, role):
    request = config.active().request
    q.require(role in {"listener", "admission", "query", "native"}, "RUNTIME_ROLE")
    return request.query_unit if role in {"query", "native"} else (
        "lhqoc-" if role == "listener" else "lhqoa-") + request.digest + ".service"


def limits(config, role):
    grant = config.active().as_dict()
    stage = "collector" if role == "listener" else "query" if role in {"query", "native"} else "admission"
    return grant["management"]["stages"][stage]


def parent(config, role):
    return config.active().as_dict()["query_parent" if role in {"query", "native"} else "management_parent"]


def deadline(config, role):
    value = config.active().as_dict(); management = value["management"]
    if role in {"query", "native"}:
        return min(value["request"]["deadline_ns"] - management["receive_ns"] - management["stop_ns"],
                   management["issued_ns"] + management["stages"]["admission"]["runtime_ns"]
                   + management["stages"]["query"]["runtime_ns"])
    return config.data()["service"]["end_ns"]


def command(config, role, *, now_ns):
    """Reviewable fixed argv; does not provision, install or start anything."""
    q.require(role in {"listener", "admission", "query"}, "RUNTIME_ROLE")
    v = config.data(); grant = config.active().as_dict(); cap = limits(config, role)
    remaining = min(deadline(config, role) - q.integer(now_ns), cap["runtime_ns"])
    remaining -= grant["management"]["stop_ns"]
    q.require(remaining >= 1000, "RUNTIME_DEADLINE")
    query = role == "query"
    # The stop grace is inside the original envelope. Reserve one maximum CFS
    # period for a boundary burst; verify the actual kernel period below.
    cpu_quota = min(100, cap["cpu_ns"] * 100 // (cap["runtime_ns"] + 1_000_000_000))
    q.require(cpu_quota >= 1, "CPU_GRANULARITY")
    properties = {
        "Slice": PurePosixPath(parent(config, role)["path"]).name,
        "Type": "exec", "ExitType": "cgroup", "RemainAfterExit": "yes",
        "Restart": "no", "KillMode": "control-group", "SendSIGKILL": "yes",
        "RuntimeMaxSec": str(remaining // 1000) + "us", "TimeoutStartSec": str(remaining // 1000) + "us",
        "TimeoutStopSec": str(grant["management"]["stop_ns"] // 1000) + "us",
        "MemoryMax": str(cap["memory_bytes"]), "MemorySwapMax": "0", "TasksMax": str(cap["pids"]),
        "CPUQuota": str(cpu_quota) + "%", "CPUQuotaPeriodSec": "1ms",
        "LimitCPU": str(cap["cpu_ns"] // 1_000_000_000), "LimitCORE": "0",
        "User": "", "Group": str(grant["endpoint"]["gid"]) if role == "listener" else "0", "NoNewPrivileges": "yes", "PrivateUsers": "no",
        "CapabilityBoundingSet": ("CAP_SYS_ADMIN CAP_DAC_READ_SEARCH" if query else
            "CAP_DAC_READ_SEARCH CAP_SYS_PTRACE" if role == "admission" else "CAP_CHOWN"),
        "AmbientCapabilities": "", "PrivateDevices": "yes", "PrivateNetwork": "yes",
        "PrivateMounts": "yes", "PrivateTmp": "yes", "ProtectSystem": "strict",
        "ProtectControlGroups": "yes", "ProtectKernelTunables": "yes", "ProtectKernelModules": "yes",
        "ProtectKernelLogs": "yes", "RestrictNamespaces": "yes", "RestrictSUIDSGID": "yes",
        "LockPersonality": "yes", "UMask": "0077",
        "SystemCallFilter": "~@mount @reboot @swap @module @raw-io",
    }
    if query:
        properties["ReadWritePaths"] = " ".join(g.root_paths(grant["allocation"]).values())
        properties["InaccessiblePaths"] = " ".join((v["journal"]["path"], v["session"]["path"], v["evidence"]["path"]))
        properties["LimitFSIZE"] = "0"
    elif role == "admission":
        properties["ReadWritePaths"] = " ".join((v["journal"]["path"], v["session"]["path"], v["evidence"]["path"]))
        properties["LimitFSIZE"] = str(grant["management"]["storage_bytes"])
    else:
        properties["ReadWritePaths"] = " ".join(sorted({str(PurePosixPath(p).parent) for p in
            (grant["endpoint"]["path"], v["service"]["control_path"])}))
        properties["InaccessiblePaths"] = " ".join((v["journal"]["path"], v["session"]["path"], v["evidence"]["path"]))
        properties["LimitFSIZE"] = "0"
    return (v["programs"]["systemd_run"]["path"], "--system", "--quiet", "--pipe", "--no-ask-password",
        "--unit=" + name(config, role), *("--property=" + k + "=" + val for k, val in properties.items()),
        "--", v["programs"]["python"]["path"], "-I", "-B", v["entry"]["path"], role, config.path, config.digest)


def host(config, role):
    """Actual process/cgroup facts; no peer-supplied booleans are accepted."""
    grant = config.active().as_dict(); v = config.data()
    q.require(os.getuid() == os.geteuid() == 0 and _boot_id() == grant["request"]["boot_id"], "RUNTIME_IDENTITY")
    expected = v["initial_userns"]
    for path in ("/proc/self/ns/user", "/proc/1/ns/user"):
        info = os.stat(path)
        q.require((info.st_dev, info.st_ino) == (expected["device"], expected["inode"]), "RUNTIME_USERNS")
    invocation = q.match(os.environ.get("INVOCATION_ID"), r"[0-9a-f]{32}")
    p = parent(config, role); group = p["path"] + "/" + name(config, role)
    q.require(_own_cgroup() == group, "RUNTIME_CGROUP")
    fd = c.pinned_directory(dict(p, path="/sys/fs/cgroup" + p["path"]))
    os.close(fd)
    q.require(grant["management"]["issued_ns"] <= boottime_ns() < deadline(config, role), "RUNTIME_DEADLINE")
    cap = limits(config, role)
    for key, upper in (("memory.max", cap["memory_bytes"]), ("pids.max", cap["pids"]), ("memory.swap.max", 0)):
        raw = _fixed_read("/sys/fs/cgroup" + group + "/" + key, 128).strip()
        q.require(raw.isdigit() and int(raw) <= upper, "RUNTIME_LIMIT")
    cpu = _fixed_read("/sys/fs/cgroup" + group + "/cpu.max", 128).split()
    q.require(len(cpu) == 2 and all(n.isdigit() for n in cpu)
              and 0 < int(cpu[0]) and 0 < int(cpu[1]) <= 1_000_000
              and int(cpu[0]) * (cap["runtime_ns"] + int(cpu[1]) * 1000)
                  <= int(cpu[1]) * cap["cpu_ns"], "RUNTIME_CPU")
    if role in {"query", "native"}:
        worker.parse_status(_fixed_read("/proc/self/status", 16384))
    else:
        capabilities(_fixed_read("/proc/self/status", 16384), role)
    return {"unit": name(config, role), "invocation_id": invocation, "cgroup": group}


def capabilities(raw, role):
    q.require(role in {"listener", "admission"}, "RUNTIME_ROLE")
    fields = {}
    for line in raw.decode("ascii").splitlines():
        key, separator, value = line.partition(":")
        if key in {"CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb", "NoNewPrivs"}:
            q.require(separator and key not in fields, "RUNTIME_STATUS")
            value = value.strip()
            q.require(re.fullmatch(r"[01]" if key == "NoNewPrivs" else r"[0-9a-f]{16}", value), "RUNTIME_STATUS")
            fields[key] = int(value, 10 if key == "NoNewPrivs" else 16)
    expected = 1 if role == "listener" else (1 << 2) | (1 << 19)
    q.require(fields == {"CapInh": 0, "CapAmb": 0, "CapPrm": expected, "CapEff": expected,
                         "CapBnd": expected, "NoNewPrivs": 1}, "RUNTIME_CAPABILITIES")


def native_context(config, root):
    grant = config.active().as_dict(); req = grant["request"]
    slot = a.Slot(root["role"], req["generation"], g.root_paths(grant["allocation"])[root["role"]],
        root["filesystem"], root["filesystem_uuid"], a.Root(*(root[k] for k in ("device", "inode", "uid", "gid", "mode"))),
        root["project_id"], root["xflags"], root["hard_bytes"])
    # Only native report comparison is reused. No Q1 request or ledger is made.
    context = SimpleNamespace(slots=(slot,), query_uid=0, query_euid=0,
        abi=tuple(config.data()["abi"][k] for k in ("fsxattr_bytes", "dqblk_bytes", "qstatv_bytes")))
    return context, slot


def native(config, role):
    roots = [r for r in config.active().as_dict()["roots"] if r["role"] == role]
    q.require(len(roots) == 1, "NATIVE_ROLE")
    before = host(config, "native")
    context, slot = native_context(config, roots[0])
    binary = c.executable(config.data()["programs"]["native"])
    try:
        executable = fcntl.fcntl(binary, fcntl.F_DUPFD_CLOEXEC, 10)
    finally:
        os.close(binary)
    root = None
    try:
        root = worker.open_slot(slot)
        q.require(host(config, "native") == before, "INVOCATION_CHANGED")
        descriptors = os.listdir("/proc/self/fd")
        q.require(len(descriptors) <= 256, "DESCRIPTOR_LIMIT")
        for item in descriptors:
            if item.isdigit() and int(item) > 2:
                try:
                    os.set_inheritable(int(item), False)
                except OSError as error:
                    if error.errno != 9:
                        raise
        os.dup2(root, 3, inheritable=True)
        q.require(os.execve in os.supports_fd and boottime_ns() < deadline(config, "native"), "NATIVE_DEADLINE")
        os.execve(executable, [config.data()["programs"]["native"]["path"]], {"LANG": "C", "LC_ALL": "C"})
    finally:
        if root is not None:
            os.close(root)
        os.close(executable)


def query(config):
    identity = host(config, "query")
    v = config.data(); reports = []
    for root in config.active().as_dict()["roots"]:
        q.require(host(config, "query") == identity, "INVOCATION_CHANGED")
        capture = Capture(a.MAX_REPORT_BYTES)
        try:
            capture.start((v["programs"]["python"]["path"], "-I", "-B", v["entry"]["path"],
                           "native", config.path, config.digest, root["role"]))
            while boottime_ns() < deadline(config, "query") and not capture.settled:
                capture.pump()
                if capture.error:
                    break
                time.sleep(0.001)
            q.require(capture.done, "NATIVE_CAPTURE_UNCERTAIN")
            reports.append({"role": root["role"], "stdout": bytes(capture.stdout).decode("ascii"),
                            "stderr": bytes(capture.stderr).decode("ascii"), "rc": capture.process.returncode})
            if capture.process.returncode:
                break
            context, slot = native_context(config, root)
            a.match_report(bytes(capture.stdout), context, slot)
        finally:
            if capture.settled:
                capture.close_pipes()
            else:
                capture.kill_client()  # Parent unit remains the recursive fence.
    raw = q._canonical({"schema": "local-hand-quota-native-set/v1", "config_digest": config.digest,
        "request_digest": config.active().request.digest, "query": identity, "reports": reports}, q.RESPONSE_LIMIT)
    q.require(host(config, "query") == identity and os.write(1, raw) == len(raw), "QUERY_OUTPUT")


def reports(config, raw, identity):
    """Return only roots independently checked against each original native report."""
    v = q._load(raw, q.RESPONSE_LIMIT, 6)
    q._keys(v, {"schema", "config_digest", "request_digest", "query", "reports"})
    q.require(v["schema"] == "local-hand-quota-native-set/v1" and v["config_digest"] == config.digest
              and v["request_digest"] == config.active().request.digest and v["query"] == identity, "REPORT_BINDING")
    expected = config.active().as_dict()["roots"]
    q.require(type(v["reports"]) is list and len(v["reports"]) == len(expected), "REPORT_COUNT")
    roots, calls = [], []
    for item, root in zip(v["reports"], expected):
        q._keys(item, {"role", "stdout", "stderr", "rc"})
        q.require(item["role"] == root["role"] and type(item["rc"]) is int
                  and item["rc"] == 0 and item["stderr"] == "", "NATIVE_FAILED")
        context, slot = native_context(config, root)
        facts = a.match_report(item["stdout"].encode("ascii"), context, slot)
        roots.append(dict(root))  # Equality to these declarations was just checked above.
        native_calls = {call["name"]: call for call in facts["calls"]}
        for operation, key in zip(q.CALL_OPERATIONS, ("state.before", "getquota", "state.after")):
            call = native_calls["quotactl_fd." + key]
            calls.append(dict(role=root["role"], operation=operation, rc=call["rc"], errno=call["errno"]))
    return roots, calls


class Dispatcher(Q1Controller):
    """Uses fixed transport/stop primitives, not Q1 admission or journal methods."""
    def __init__(self, config):
        self.installation = config
        data = config.active().as_dict(); p = data["query_parent"]
        self.config = SimpleNamespace(systemctl_path=config.data()["programs"]["systemctl"]["path"],
            query_slice=PurePosixPath(p["path"]).name, cgroup_parent_device=p["device"], cgroup_parent_inode=p["inode"])
        self.controls = []; self.launcher = None; self.used = False; self._stop_attempted = False

    def _command(self, arguments, *, absolute_end_ns):
        cap = limits(self.installation, "admission")["output_bytes"]
        q.require(sum(len(x.stdout) + len(x.stderr) for x in self.controls) < cap, "CONTROL_OUTPUT_BUDGET")
        raw = super()._command(arguments, absolute_end_ns=absolute_end_ns)
        q.require(sum(len(x.stdout) + len(x.stderr) for x in self.controls) <= cap, "CONTROL_OUTPUT_BUDGET")
        return raw

    def __call__(self, grant, end, remember):
        config = self.installation
        q.require(not self.used and grant == config.active(), "DISPATCH_BINDING")
        self.used = True
        host(config, "admission")
        data = grant.as_dict(); start = boottime_ns()
        q.require(end == deadline(config, "query"), "QUERY_DEADLINE")
        binding = SimpleNamespace(unit=grant.request.query_unit, cgroup=data["query_parent"]["path"] + "/" + grant.request.query_unit,
            manifest=SimpleNamespace(boot_id=data["request"]["boot_id"], cgroup_parent=data["query_parent"]["path"]))
        identity = None; terminal = None; stopped = False; reason = "QUERY_INCOMPLETE"; roots = []; calls = []
        try:
            q.require(self._parent_empty(binding), "QUERY_TREE_NOT_EMPTY")
            before = self._show(binding, absolute_end_ns=end)
            q.require(before["Id"] == binding.unit and before["LoadState"] == "not-found" and before["Job"] in ("", "0"), "QUERY_ALREADY_EXISTS")
            self.launcher = Capture(q.RESPONSE_LIMIT)
            self.launcher.start(command(config, "query", now_ns=boottime_ns()))
            interval = max(0.01, (end - boottime_ns()) / 20_000_000_000)
            for _ in range(21):
                q.require(boottime_ns() < end, "QUERY_DEADLINE")
                self.launcher.pump()
                values = self._show(binding, absolute_end_ns=end)
                if values["LoadState"] == "loaded" and values["InvocationID"]:
                    inv = self._unit_identity(binding, values, invocation=identity and identity["invocation_id"])
                    if identity is None:
                        identity = {"unit": binding.unit, "cgroup": binding.cgroup, "invocation_id": inv}
                        remember(dict(identity, parent=data["query_parent"]))
                    if (values["ActiveState"] in ("inactive", "failed") or values["SubState"] == "exited") and values["Job"] in ("", "0"):
                        terminal = values
                        break
                q.require(not self.launcher.error, "CAPTURE_UNCERTAIN")
                time.sleep(min(interval, max(0, end - boottime_ns()) / 1e9))
            q.require(identity is not None, "INVOCATION_REQUIRED")
            stopped = self._stop_original(binding, identity["invocation_id"], absolute_end_ns=end)
            q.require(terminal is not None and stopped and terminal["Result"] == "success"
                and terminal["ExecMainCode"] == "1" and terminal["ExecMainStatus"] == "0"
                and self.launcher.done and self.launcher.process.returncode == 0
                and not self.launcher.stderr and all(x.done for x in self.controls), "QUERY_EXIT_UNPROVEN")
            roots, calls = reports(config, bytes(self.launcher.stdout), identity)
            q.require(boottime_ns() < end, "QUERY_DEADLINE")
            reason = "PINNED_FACTS_MATCH"
        except (OSError, ValueError) as error:
            reason = str(error) if isinstance(error, (q.QuotaError, a.Rejected)) else "RUNTIME_IO_UNCERTAIN"
            if identity is not None and not self._stop_attempted:
                try:
                    stopped = self._stop_original(binding, identity["invocation_id"], absolute_end_ns=end)
                except (OSError, ValueError):
                    stopped = False
        captures = self.controls + ([self.launcher] if self.launcher else [])
        proof = {"query": identity, "terminal": terminal, "stopped": stopped,
                 "captures": [{"stdout": bytes(x.stdout).decode("ascii", "replace"),
                               "stderr": bytes(x.stderr).decode("ascii", "replace"),
                               "eof": sorted(x.eof), "error": x.error,
                               "returncode": x.process.poll() if x.process else None} for x in captures]}
        raw = q._canonical(proof, data["management"]["storage_bytes"] - g.CELL_BYTES)
        evidence = c.pinned_directory(config.data()["evidence"])
        try:
            q.require(stat.S_IMODE(os.fstat(evidence).st_mode) == 0o700, "EVIDENCE_PRIVATE")
            fd = os.open(grant.request.digest + ".json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=evidence)
            try:
                q.require(os.write(fd, raw) == len(raw), "EVIDENCE_WRITE")
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(evidence)
        finally:
            os.close(evidence)
        for capture in captures:
            if capture.settled:
                capture.close_pipes()
        observed = reason == "PINNED_FACTS_MATCH" and boottime_ns() < end
        if not observed and reason == "PINNED_FACTS_MATCH":
            reason = "QUERY_DEADLINE"
        complete = stopped and all(x.done for x in captures) and self.launcher is not None
        return q._canonical({"schema": "local-hand-quota-receipt/v1", "request_digest": grant.request.digest,
            "status": "OBSERVED" if observed else "UNKNOWN", "reason": reason if not observed else "PINNED_FACTS_MATCH",
            "deadline_ns": data["request"]["deadline_ns"], "started_ns": start, "finished_ns": boottime_ns(),
            "query": identity, "roots": roots, "calls": calls,
            "exit": {**dict.fromkeys(q.EXIT_FLAGS, bool(complete)), "proof_digest": hashlib.sha256(raw).hexdigest(),
                "exec_main_code": int(terminal["ExecMainCode"]) if terminal and terminal["ExecMainCode"].isdigit() else None,
                "exec_main_status": int(terminal["ExecMainStatus"]) if terminal and terminal["ExecMainStatus"].isdigit() else None,
                "client_returncode": self.launcher.process.poll() if self.launcher and self.launcher.process else None}}, q.RESPONSE_LIMIT)
