"""Finite original listener/admission supervision and six-stage assembly.

Run only in an independently supervised administrator controller. There is no
recovery launch: the create-once intent stays consumed after any uncertainty.
The test fixture supplies the controller envelope; nothing here provisions it.
"""
from __future__ import annotations

import hashlib
import fcntl
import os
from pathlib import PurePosixPath
from types import SimpleNamespace

from local_hand_jobs import quota_closure as close, quota_contract as q, quota_grant as g
from . import controller_guard as guard, q2_config as c, q2_runtime as runtime
from .systemd_runtime import Capture, boottime_ns, _boot_id


def controller(config, envelope):
    """Reobserve the actual enclosing service; declarations alone grant nothing."""
    q._keys(envelope, {"controller", "issued_ns", "deadline_ns", "output_bytes", "storage_bytes", "storage_inodes"})
    spec = guard.decode_controller(envelope["controller"])
    data = config.active().as_dict()
    issued = q.integer(envelope["issued_ns"], 1)
    end = q.integer(envelope["deadline_ns"], issued + 1)
    q.require(issued <= boottime_ns() < end and end - issued <= spec.runtime_max_usec * 1000, "CONTROLLER_DEADLINE")
    q.integer(envelope["output_bytes"], 1, 32768)
    q.integer(envelope["storage_bytes"], 65536)
    q.integer(envelope["storage_inodes"], 1)
    for parent in (data["query_parent"], data["management_parent"],
                   config.data()["peers"][data["request"]["request_id"]]["parent"]):
        q.require(not c.overlap(spec.cgroup, parent["path"]), "CONTROLLER_OVERLAP")
    grants = list(config.grants().values())
    g.check_capacity(config.data()["capacity"], grants)
    # The outer controller is additional simultaneous work, never borrowed
    # from a query/admission budget or charged as zero because it only reads.
    costs = dict(storage_bytes=envelope["storage_bytes"], storage_inodes=envelope["storage_inodes"],
        cpu_ns=((spec.runtime_max_usec + spec.timeout_stop_usec + 1_000_000) * spec.cpu_quota_per_sec_usec + 999) // 1000,
        memory_bytes=spec.memory_bytes, pids=spec.tasks_max, output_bytes=envelope["output_bytes"])
    capacity = config.data()["capacity"]
    for key, amount in costs.items():
        q.require(amount + sum(g.totals(item)[key] for item in grants) <= capacity["management"][key], "CONTROLLER_CAPACITY")
    q.require(envelope["storage_bytes"] + capacity["retained_bytes"] + sum(g.totals(x)["storage_bytes"] for x in grants)
              + sum(x["hard_bytes"] for x in capacity["domains"]) <= capacity["ceiling_bytes"], "CONTROLLER_STORAGE")
    q.require(envelope["storage_inodes"] + capacity["retained_inodes"] + sum(g.totals(x)["storage_inodes"] for x in grants)
              + sum(x["hard_inodes"] for x in capacity["domains"]) <= capacity["ceiling_inodes"], "CONTROLLER_INODES")
    raw = config.data()
    adapter = SimpleNamespace(initial_userns_device=raw["initial_userns"]["device"],
        initial_userns_inode=raw["initial_userns"]["inode"], systemctl_path=raw["programs"]["systemctl"]["path"],
        systemctl_sha256=raw["programs"]["systemctl"]["sha256"])
    manifest = SimpleNamespace(boot_id=data["request"]["boot_id"], cgroup_parent=data["query_parent"]["path"])
    before = guard._host_identity(adapter, manifest, spec)
    guard._cgroup_identity(spec)
    guard._check_manager(guard._show_once(adapter, spec), spec, before[0])
    guard._cgroup_identity(spec)
    q.require(before == guard._host_identity(adapter, manifest, spec), "CONTROLLER_CHANGED")
    return dict(unit=spec.unit, invocation_id=spec.invocation_id, boot_id=manifest.boot_id,
                cgroup=spec.cgroup, observed_ns=boottime_ns())


class Management(runtime.UnitTransport):
    """The two management launchers, serviced together under one fixed deadline."""
    def __init__(self, installation, envelope, persist):
        self.installation, self.envelope, self.persist = installation, envelope, persist
        self.owner = controller(installation, envelope)
        p = installation.active().as_dict()["management_parent"]
        self.config = SimpleNamespace(systemctl_path=installation.data()["programs"]["systemctl"]["path"],
            query_slice=PurePosixPath(p["path"]).name, cgroup_parent_device=p["device"], cgroup_parent_inode=p["inode"])
        self.controls = []; self.launcher = None; self.runs = {}; self.used = False; self.failure = None
        self.end = min(envelope["deadline_ns"], runtime.deadline(installation, "listener"))

    def _command(self, arguments, *, absolute_end_ns):
        q.require(sum(len(x.stdout) + len(x.stderr) for x in self.controls) < self.envelope["output_bytes"], "CONTROL_OUTPUT_BUDGET")
        raw = super()._command(arguments, absolute_end_ns=absolute_end_ns)
        for part in self.runs.values():
            part["capture"].pump()
        q.require(sum(len(x.stdout) + len(x.stderr) for x in self.controls) <= self.envelope["output_bytes"], "CONTROL_OUTPUT_BUDGET")
        return raw

    def binding(self, role):
        data = self.installation.active().as_dict()
        unit = runtime.name(self.installation, role)
        return SimpleNamespace(unit=unit, cgroup=data["management_parent"]["path"] + "/" + unit,
            manifest=SimpleNamespace(boot_id=data["request"]["boot_id"], cgroup_parent=data["management_parent"]["path"]))

    def begin(self):
        q.require(not self.used, "MANAGEMENT_ALREADY_CONSUMED")
        self.used = True
        q.require(self._parent_empty(self.binding("listener")), "MANAGEMENT_PARENT_OCCUPIED")
        for role in ("listener", "admission"):
            before = self._show(self.binding(role), absolute_end_ns=self.end)
            q.require(before["LoadState"] == "not-found" and before["Id"] == self.binding(role).unit
                      and before["Job"] in ("", "0"), "MANAGEMENT_ALREADY_EXISTS")
        self.persist("INTENT", dict(config_digest=self.installation.digest, controller=self.owner, deadline_ns=self.end))
        self.launch("listener")

    def launch(self, role):
        q.require(self.used and role in ("listener", "admission") and role not in self.runs, "MANAGEMENT_REPLAY")
        argv = runtime.command(self.installation, role, now_ns=boottime_ns())
        cap = Capture(min(32768, runtime.limits(self.installation, role)["output_bytes"]))
        part = self.runs[role] = dict(capture=cap, invocation=None, terminal=None, after=None, stop_attempted=False, stop_ok=False)
        self.persist("DELIVERY", dict(role=role, unit=self.binding(role).unit, command_digest=close.digest(argv)))
        cap.start(argv)
        return part

    def poll(self):
        q.require(self.used and not self.failure and boottime_ns() < self.end, "MANAGEMENT_DEADLINE")
        q.require(_boot_id() == self.owner["boot_id"], "BOOT_CHANGED")
        try:
            for role, part in self.runs.items():
                part["capture"].pump()
                v = self._show(self.binding(role), absolute_end_ns=self.end)
                if v["LoadState"] != "loaded":
                    if (v["LoadState"] == "not-found" and v["Id"] == self.binding(role).unit
                            and v["Job"] in ("", "0") and part["invocation"] is None
                            and part["capture"].process.poll() is None):
                        # Delivery is still pending. Absence is neither exit
                        # proof nor permission to launch a replacement.
                        continue
                    q.require(part["stop_ok"] and v["LoadState"] == "not-found" and v["Job"] in ("", "0"), "MANAGEMENT_UNIT_MISSING")
                    part["after"] = v
                    continue
                inv = self._unit_identity(self.binding(role), v, invocation=part["invocation"])
                if part["invocation"] is None:
                    self.persist("INVOCATION", dict(role=role, invocation_id=inv, unit=v["Id"]))
                    part["invocation"] = inv
                terminal = v["SubState"] == "exited" or v["ActiveState"] in ("inactive", "failed")
                if terminal and not part["stop_attempted"]:
                    part["terminal"] = v
                    part["stop_attempted"] = True
                    self._command(("stop", v["Id"]), absolute_end_ns=self.end)
                    part["stop_ok"] = True
                elif part["stop_ok"]:
                    part["after"] = v
            return self._closed()
        except (OSError, ValueError) as error:
            self.failure = type(error).__name__ + ":" + str(error)
            raise

    def _closed(self):
        q.require(self.used and not self.failure, "MANAGEMENT_EXIT_UNPROVEN")
        q.require(_boot_id() == self.owner["boot_id"], "BOOT_CHANGED")
        if set(self.runs) != {"listener", "admission"}:
            return None
        for part in self.runs.values():
            t, after, cap = part["terminal"], part["after"], part["capture"]
            if not (part["stop_ok"] and t and after and cap.done and cap.process.returncode == 0
                and t["ExecMainCode"] == "1" and t["ExecMainStatus"] == "0" and t["Result"] == "success"
                and after["Job"] in ("", "0") and (after["LoadState"] == "not-found" or after["ActiveState"] in ("inactive", "failed"))):
                return None
        q.require(all(x.done for x in self.controls) and self._parent_empty(self.binding("listener")), "MANAGEMENT_EXIT_UNPROVEN")
        now = boottime_ns(); q.require(now < self.end, "MANAGEMENT_DEADLINE")
        result = dict(schema="local-hand-quota-management-closed/v1", config_digest=self.installation.digest,
                      request_digest=self.installation.active().request.digest, controller=self.owner, observed_ns=now, stages={})
        for role, part in self.runs.items():
            name = "collector" if role == "listener" else "admission"
            cap = part["capture"]
            evidence = dict(terminal=part["terminal"], after=part["after"], stdout_sha256=hashlib.sha256(cap.stdout).hexdigest(),
                stderr_sha256=hashlib.sha256(cap.stderr).hexdigest(), eof=sorted(cap.eof), returncode=cap.process.poll(), error=cap.error)
            identity = close.stage_identity(self.installation.active(), name, {}, part["invocation"])
            result["stages"][name] = dict(**dict.fromkeys(q.EXIT_FLAGS, True), identity=identity, observed_ns=now, proof_digest=close.digest(evidence))
        return result

    def finish(self):
        result = self._closed()
        q.require(result is not None, "MANAGEMENT_EXIT_UNPROVEN")
        captures = [*self.controls, *(p["capture"] for p in self.runs.values())]
        for capture in captures:
            capture.close_pipes()
        q.require(all(capture.done for capture in captures), "MANAGEMENT_CAPTURE_CLOSE_UNPROVEN")
        self.persist("CLOSED", result)
        q.require(_boot_id() == self.owner["boot_id"] and boottime_ns() < self.end, "MANAGEMENT_DEADLINE")
        return result


def assemble(grant, receipt, peer, ordinary, management, parents, *, now_ns):
    """Combine already retained facts; caller authenticates their protected files."""
    stages = close.ordinary(ordinary, grant)
    q._keys(management, {"schema", "config_digest", "request_digest", "controller", "observed_ns", "stages"})
    q.require(management["schema"] == "local-hand-quota-management-closed/v1"
              and management["request_digest"] == grant.request.digest, "MANAGEMENT_BINDING")
    q._keys(management["stages"], {"collector", "admission"})
    query = receipt.as_dict()
    query_proof = {key: query["exit"][key] for key in (*q.EXIT_FLAGS, "proof_digest")}
    query_proof.update(observed_ns=query["finished_ns"],
        identity=dict(query["query"], boot_id=grant.request.as_dict()["boot_id"], parent=grant.as_dict()["query_parent"]))
    value = dict(schema=close.SCHEMA, request_digest=grant.request.digest, receipt_digest=hashlib.sha256(receipt.wire).hexdigest(),
        boot_id=grant.request.as_dict()["boot_id"], execution_id=grant.request.as_dict()["execution_id"], closed_ns=now_ns,
        ordinary_digest=close.digest(ordinary), management_digest=close.digest(management), parents=parents,
        stages=dict(stages, query=query_proof, **management["stages"]))
    value["proof_digest"] = close.digest(value)
    return close.decode(value, grant, receipt, peer, now_ns=now_ns)


class RunRecord:
    """One existing, protected empty file; never create, truncate, or resume it."""
    def __init__(self, pin):
        c.identity(pin)
        self.fd = -1; self.total = 0; self.previous = "0" * 64; self.poisoned = False
        self.delivered = set(); self.invocations = set(); self.finished = False
        parent = PurePosixPath(pin["path"]).parent
        descriptor = c.open_protected(str(parent), directory=True)
        checked = -1
        try:
            checked = c.open_protected(pin["path"])
            before = os.fstat(checked)
            q.require((before.st_dev, before.st_ino) == (pin["device"], pin["inode"])
                      and before.st_size == 0 and before.st_mode & 0o777 == 0o600, "MANAGEMENT_RECORD_CONSUMED")
            self.fd = os.open(PurePosixPath(pin["path"]).name, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            after = os.fstat(self.fd)
            q.require((after.st_dev, after.st_ino, after.st_size, after.st_nlink) ==
                      (before.st_dev, before.st_ino, 0, 1), "MANAGEMENT_RECORD_CHANGED")
        except BaseException:
            self.close()
            raise
        finally:
            if checked >= 0:os.close(checked)
            os.close(descriptor)

    def __call__(self, kind, value):
        q.require(self.fd >= 0 and not self.poisoned, "MANAGEMENT_RECORD_UNAVAILABLE")
        try:
            q.require(not self.finished, "MANAGEMENT_RECORD_CLOSED")
            if kind == "INTENT":
                q.require(self.total == 0, "MANAGEMENT_RECORD_CONSUMED")
            elif kind in ("DELIVERY", "INVOCATION"):
                role = value.get("role")
                q.require(self.total > 0 and role in ("listener", "admission"), "MANAGEMENT_RECORD_ORDER")
                q.require(role not in (self.delivered if kind == "DELIVERY" else self.invocations)
                    and (kind != "INVOCATION" or role in self.delivered), "MANAGEMENT_RECORD_ORDER")
            elif kind == "CLOSED":
                q.require(self.invocations == {"listener", "admission"}, "MANAGEMENT_RECORD_ORDER")
            else:
                raise q.QuotaError("MANAGEMENT_RECORD_KIND")
            row = dict(kind=kind, value=value, previous_digest=self.previous)
            raw = q._canonical(row, 32768) + b"\n"
            q.require(self.total + len(raw) <= 65536, "MANAGEMENT_RECORD_LIMIT")
            q.require(os.write(self.fd, raw) == len(raw), "MANAGEMENT_RECORD_WRITE")
            os.fsync(self.fd)
            self.total += len(raw); self.previous = hashlib.sha256(raw).hexdigest()
            if kind == "DELIVERY":self.delivered.add(role)
            if kind == "INVOCATION":self.invocations.add(role)
            if kind == "CLOSED":self.finished = True
        except BaseException:
            self.poisoned = True
            raise

    def close(self):
        if self.fd >= 0:
            os.close(self.fd); self.fd = -1
