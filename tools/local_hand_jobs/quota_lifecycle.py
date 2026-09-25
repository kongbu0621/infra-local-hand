"""Q2 original-launcher exit observation used by the real SystemdManager.

No subprocess wait or task-filesystem read lives here. Manager commands retain
the existing bounded transport; pipe reads are nonblocking and limited per tick.
"""
from __future__ import annotations

import hashlib
import os

from . import budget, quota_closure as close, quota_contract as q
from .contract import JobError

FIELDS = ("Id", "LoadState", "ActiveState", "SubState", "ControlGroup", "InvocationID", "Job",
          "ExecMainCode", "ExecMainStatus", "Result", "Restart", "TriggeredBy", "ExecStop",
          "ExecStopPost", "ExecReload", "KillMode", "Type", "ExitType", "RemainAfterExit",
          "ExecStartPre", "ExecStartPost", "OnFailure", "OnSuccess", "RestartForceExitStatus")


def parent(path, expected=None):
    q.require(type(path) is str and path.startswith("/sys/fs/cgroup/"), "ORDINARY_PARENT")
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        pin = dict(path=path[len("/sys/fs/cgroup"):], device=info.st_dev, inode=info.st_ino)
        q.require(expected is None or pin == expected, "ORDINARY_PARENT_CHANGED")
        with open("/proc/self/fdinfo/" + str(fd), "rb") as stream:
            fdinfo = stream.read(4097)
        with open("/proc/self/mountinfo", "rb") as stream:
            mountinfo = stream.read(1024 * 1024 + 1)
        q.require(len(fdinfo) <= 4096 and len(mountinfo) <= 1024 * 1024, "CGROUP_MOUNT_LIMIT")
        ids = [line.split(":", 1)[1].strip() for line in fdinfo.decode("ascii").splitlines() if line.startswith("mnt_id:")]
        q.require(len(ids) == 1, "CGROUP_MOUNT_ID")
        mounts = [line.split() for line in mountinfo.decode("utf-8").splitlines() if line.split()[0] == ids[0]]
        q.require(len(mounts) == 1 and mounts[0][mounts[0].index("-") + 1] == "cgroup2"
                  and mounts[0][2] == str(os.major(info.st_dev)) + ":" + str(os.minor(info.st_dev)), "CGROUP_FILESYSTEM")
        event = os.open("cgroup.events", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=fd)
        try:
            raw = os.read(event, 4097)
            q.require(len(raw) <= 4096, "CGROUP_EVENTS_SIZE")
            rows = [line.split() for line in raw.decode("ascii").splitlines()]
            q.require(all(len(row) == 2 for row in rows) and len({row[0] for row in rows}) == len(rows), "CGROUP_EVENTS")
            values = dict(rows)
            q.require(values.get("populated") in ("0", "1"), "CGROUP_EVENTS")
        finally:
            os.close(event)
        after = os.stat(path, follow_symlinks=False)
        q.require((info.st_dev, info.st_ino) == (after.st_dev, after.st_ino), "ORDINARY_PARENT_CHANGED")
        return pin, values["populated"] == "0"
    finally:
        os.close(fd)


class Transport:
    def __init__(self, limit):
        self.limit = q.integer(limit, 1, 2 * 1024 * 1024)
        self.total = 0
        self.eof = set()
        self.error = None
        self.hashes = {name: hashlib.sha256() for name in ("stdout", "stderr")}

    def pump(self, part):
        client = part.get("launch")
        q.require(client is not None and part.get("pipe_nonblocking") is True, "PIPE_SETUP_UNPROVEN")
        for name in ("stdout", "stderr"):
            if name in self.eof:
                continue
            try:
                raw = os.read(getattr(client, name).fileno(), 8192)
            except BlockingIOError:
                continue
            except (OSError, ValueError):
                self.error = self.error or "PIPE_READ_UNCERTAIN"
                continue
            self.total += len(raw)
            self.hashes[name].update(raw)
            if self.total > self.limit:
                self.error = self.error or "PIPE_BYTE_LIMIT"
            if not raw:
                self.eof.add(name)
            if name == "stdout" and self.error is None:
                try:
                    if "quota_pipe" in part:
                        part["quota_pipe"].feed(raw)
                    elif part.get("reader") is not None and raw:
                        part["reader"].feed(raw)
                except (ValueError, RuntimeError, JobError):
                    self.error = "PIPE_FRAME_REJECTED"

    def record(self, client):
        return dict(bytes=self.total, eof=sorted(self.eof), error=self.error,
                    returncode=client.poll(), digests={k: v.hexdigest() for k, v in self.hashes.items()})


def _loaded_identity(part, values):
    """Validate the original live or retained loaded-unit observation."""
    q._keys(values, set(FIELDS))
    q.require(values["Id"] == part["unit"] and values["LoadState"] == "loaded", "ORIGINAL_UNIT_MISSING")
    inv = q.match(values["InvocationID"], r"[0-9a-f]{32}")
    q.require(part["invocation_id"] in (None, inv), "ORIGINAL_INVOCATION_CHANGED")
    expected = part["quota_parent"]["path"] + "/" + part["unit"]
    q.require(values["ControlGroup"] in (expected, ""), "ORIGINAL_CGROUP_CHANGED")
    required = dict(Restart="no", TriggeredBy="", ExecStop="", ExecStopPost="", ExecReload="",
                    KillMode="control-group", Type="exec", ExitType="cgroup", RemainAfterExit="yes",
                    ExecStartPre="", ExecStartPost="", OnFailure="", OnSuccess="", RestartForceExitStatus="")
    q.require(all(values[k] == v for k, v in required.items()), "UNIT_CONFIG_CHANGED")
    return dict(boot_id=part["boot_id"], invocation_id=inv, cgroup=expected)


def _terminal(values):
    return values["SubState"] == "exited" or values["ActiveState"] in ("inactive", "failed")


def observe(manager, part, unknown):
    """Stop the same retained invocation, then require its real client and EOFs."""
    q.require(not part.get("recovered"), "ORIGINAL_TRANSPORT_LOST")
    now = budget.current_clock()
    q.require(now["boot_id"] == part["boot_id"], "BOOT_CHANGED")
    if part.get("quota_final") is not None:
        return part["quota_final"]
    cap = part["quota_transport"]
    cap.pump(part)
    response = manager._command("show", part["unit"], "--all", "--property=" + ",".join(FIELDS))
    q.require(response.returncode == 0, "UNIT_SHOW_FAILED")
    pairs = [line.split("=", 1) for line in response.stdout.decode().splitlines()]
    q.require(all(len(p) == 2 for p in pairs) and len({p[0] for p in pairs}) == len(pairs), "UNIT_PROPERTIES")
    values = dict(pairs)
    for hook in ("ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost", "ExecReload"):
        values.setdefault(hook, "")
    q._keys(values, set(FIELDS))
    expired = now["boottime_ns"] >= part["phase_deadline_boottime_ns"]
    if values["LoadState"] == "loaded":
        identity = _loaded_identity(part, values)
        inv = identity["invocation_id"]
        part["invocation_id"], part["launch_acked"] = inv, True
        if part.get("reader") is not None:
            part["reader"].bind_reader(identity)
        terminal = _terminal(values)
        if (terminal or expired or cap.error) and not part.get("quota_stop_attempted"):
            part["quota_stop_attempted"] = True
            part["quota_terminal"] = values
            # Recheck original identity immediately before the bounded StopUnit.
            same = manager._command("show", part["unit"], "--property=InvocationID", "--value")
            q.require(same.returncode == 0 and same.stdout.decode().strip() == inv, "ORIGINAL_INVOCATION_CHANGED")
            part["quota_stop_ok"] = manager._command("stop", part["unit"]).returncode == 0
            return {**unknown(), "identity": identity}
        if not terminal:
            return {**unknown(), "state": "RUNNING", "identity": identity}
    else:
        # A successful StopUnit may garbage-collect the transient unit. Only
        # this same process's retained loaded terminal observation and stop ACK
        # can bridge that absence; it can never adopt a missing or new launch.
        q.require(values["LoadState"] == "not-found" and values["Id"] == part["unit"]
                  and values["InvocationID"] == "" and values["ControlGroup"] == ""
                  and values["ActiveState"] == "inactive" and values["SubState"] == "dead"
                  and values["Job"] in ("", "0") and part.get("quota_stop_attempted") is True
                  and part.get("quota_stop_ok") is True and part.get("launch_acked") is True
                  and part.get("invocation_id") is not None and type(part.get("quota_terminal")) is dict,
                  "ORIGINAL_UNIT_MISSING")
        identity = _loaded_identity(part, part["quota_terminal"])
        q.require(_terminal(part["quota_terminal"]), "ORIGINAL_TERMINAL_UNPROVEN")
    _, empty = parent(part["cgroup_parent"], part["quota_parent"])
    now = budget.current_clock()
    q.require(now["boot_id"] == part["boot_id"], "BOOT_CHANGED")
    q.require(not expired and now["boottime_ns"] < part["phase_deadline_boottime_ns"], "ORIGINAL_DEADLINE")
    q.require(part.get("quota_stop_ok") and values["ActiveState"] in ("inactive", "failed")
        and values["Job"] in ("", "0") and empty, "ORIGINAL_EXIT_UNPROVEN")
    terminal = part["quota_terminal"]
    q.require(terminal["ExecMainCode"] == "1" and terminal["ExecMainStatus"].isdigit(), "ORIGINAL_EXIT_STATUS")
    code = int(terminal["ExecMainStatus"])
    q.require(cap.eof == {"stdout", "stderr"} and cap.error is None
              and part["launch"].poll() == code, "ORIGINAL_CLIENT_EOF_UNPROVEN")
    result = dict(outcome="UNKNOWN")
    if "quota_pipe" in part:
        result = dict(outcome="SUCCEEDED" if code == 0 else "FAILED", bootstrap_prepared=code == 0,
                      business_started=False, helper_started=True,
                      quota_observation=part["quota_pipe"].finish(part["quota_grant"], now_ns=now["boottime_ns"]))
    elif part.get("reader") is not None:
        part["reader"].finish()
    evidence = dict(identity=identity, terminal=terminal, after=values, transport=cap.record(part["launch"]),
                    parent=part["quota_parent"])
    stage = dict.fromkeys(q.EXIT_FLAGS, True)
    stage.update(identity=dict(identity, unit=part["unit"], parent=part["quota_parent"]),
                 proof_digest=close.digest(evidence), observed_ns=now["boottime_ns"])
    for stream in (part["launch"].stdout, part["launch"].stderr):
        try:
            stream.close()
        except OSError:
            cap.error = "PIPE_CLOSE_UNCERTAIN"
    q.require(cap.error is None, "ORIGINAL_CLIENT_CLOSE_UNPROVEN")
    part["pipe_closed"] = part["client_stopped"] = True
    part["quota_exit"] = stage
    proof = dict(state="EXITED", future_start_blocked=True, tree_exited=True, collectors_stopped=True,
                 writers_stopped=True, effects_checked=result.get("bootstrap_prepared", False),
                 exit_code=code, execution_id=part["execution_id"], unit=part["unit"], facts={}, result=result,
                 identity=identity, missing=[])
    part["quota_final"] = proof
    return proof
