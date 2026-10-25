"""Bounded, read-only inventory of the original final-admission records.

These records are never rewritten by deployment. Compatibility concerns an
exact preparation and unchanged executor, not arbitrary cross-version jobs.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from local_hand_jobs import maintenance, startup

from .model import DeployError, decode, digest

MAX_TASKS = 128
MAX_INPUT_BYTES = 64 * 1024 * 1024


def inventory(profile, *, candidates=None):
    candidates = candidates or {}
    owner = profile.get("owner_uid", 0)
    remaining = MAX_INPUT_BYTES

    def read(path):
        nonlocal remaining
        raw = startup.protected_read(path, owner_uid=owner, maximum=min(2 * 1024 * 1024, remaining))
        remaining -= len(raw)
        if remaining <= 0:
            raise DeployError("RETENTION_LIMIT", "Preparation inventory exceeds its byte budget")
        return decode(raw), hashlib.sha256(raw).hexdigest()

    result = {"schema": "local-hand-retained-preparations/v1", "components": {}, "tasks": []}
    for component, probe in profile["probes"].items():
        if probe["kind"] not in {"resident", "prepared"}:
            continue
        guard = profile["guarded_components"][component]
        path = guard["configuration"]
        config, _ = read(candidates.get(path, path))
        # File-only fixtures/administrative components with no task admission
        # do not manufacture an empty inventory for an actual execution entry.
        if not {"prepare", "execute"}.intersection(guard["entrypoints"]):
            continue
        installation = config.get("installation")
        if not isinstance(installation, dict):
            raise DeployError("RETENTION_CONFIGURATION", "Task entry has no bound executor installation")
        result["components"][component] = {"installation_digest": digest(installation),
            "configuration_digest": maintenance.digest({k: v for k, v in config.items() if k != "maintenance"})}
        records = []
        if probe["kind"] == "resident":
            root = Path(config["private_root"])
            fd = startup._protected_directory(root, owner_uid=owner)
            try:
                # Enforce the limit while enumerating, before sorting/reading.
                with os.scandir(fd) as entries:
                    for entry in entries:
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                        if len(records) >= min(config["max_tasks"], MAX_TASKS):
                            raise DeployError("RETENTION_LIMIT", "Preparation inventory exceeds its task budget")
                        record, record_hash = read(str(root / entry.name / "current.json"))
                        if record.get("operation_id") != entry.name:
                            raise DeployError("RETENTION_CONFLICT", "Preparation directory and original identity differ")
                        records.append((record, record_hash))
            finally:
                os.close(fd)
        else:
            launch, launch_hash = read(config["launch_path"])
            if launch_hash != config["launch_sha256"]:
                raise DeployError("RETENTION_CONFLICT", "Fixed preparation launch changed")
            prepared = config.get("maintenance_prepared")
            records = [({"operation_id": launch["request"]["operation_id"], "state": "READY",
                "attempt": prepared.get("attempt_id") if prepared else None,
                "request": launch["request"], "launch_path": config["launch_path"],
                "output": config["output"], "maintenance_prepared": prepared}, launch_hash)]
        for record, record_hash in records:
            if len(result["tasks"]) >= MAX_TASKS:
                raise DeployError("RETENTION_LIMIT", "Combined preparation inventory exceeds its task budget")
            item = {"component": component, "operation_id": record["operation_id"],
                    "record_digest": record_hash, "state": record["state"],
                    "dispatch_boot_id": record.get("boot_id"),
                    "admission_id": (record.get("maintenance_admission") or {}).get("id")}
            if record["state"] == "READY":
                launch, launch_hash = read(record["launch_path"])
                prepared = record.get("maintenance_prepared")
                if prepared is not None:
                    maintenance.MaintenanceGate._validate_prepared(prepared)
                    if (prepared["operation_id"] != record["operation_id"]
                            or prepared["attempt_id"] != record["attempt"]
                            or prepared["request_digest"] != launch["request"]["request_digest"]
                            or prepared["resource_digest"] != maintenance.digest(launch)
                            or record["request"] != launch["request"]):
                        raise DeployError("RETENTION_CONFLICT", "Original request, attempt or resources changed")
                output = Path(record["output"])
                directory = startup._protected_directory(output, owner_uid=owner)
                try:
                    # A named intent can never be treated as an unused READY.
                    names = set()
                    with os.scandir(directory) as entries:
                        for entry in entries:
                            if len(names) >= 128:
                                raise DeployError("RETENTION_LIMIT", "Launch output directory exceeds inventory budget")
                            names.add(entry.name)
                finally:
                    os.close(directory)
                dispatched = bool(names.intersection({"launch-intent.json", "started.json"}))
                if dispatched:
                    if "finished.json" in names:
                        finished, _ = read(str(output / "finished.json"))
                    else:
                        finished = {}
                    closed = type(finished.get("returncode")) is int and finished.get("streams_eof") is True
                    # Gate drain separately proves original writers/system jobs
                    # closed. This observation cannot retire their responsibility.
                    state = "EXECUTION_RETAINED" if closed else "UNRESOLVED"
                else:
                    state = "UNSUBMITTED"
                item.update(prepared=prepared, launch_digest=launch_hash, execution=state,
                            dispatch_boot_id=record.get("boot_id") or launch.get("controller_envelope", {}).get("controller", {}).get("boot_id"),
                            expires_at=launch["request"]["expires_at"],
                            policy_path=record.get("policy_path", launch.get("policy_path")))
            result["tasks"].append(item)
    result["tasks"].sort(key=lambda item: (item["component"], item["operation_id"]))
    return result


def decisions(snapshot, target_components, *, now, boot_id, closed=()):
    """A conservative complete predicate; changed executors require re-prepare.

    Re-preparation remains the original authenticated task workflow. Deployment
    never allocates resources or submits an old job to make a check pass.
    """
    result = []
    for item in snapshot["tasks"]:
        if (item["state"] == "PREPARING" or item.get("execution") == "UNRESOLVED") and digest(item) not in closed:
            raise DeployError("RETAINED_DISPATCH_UNRESOLVED", "Original preparation/dispatch must close before switching")
        if item["state"] != "READY" or item["execution"] != "UNSUBMITTED":
            continue
        component = item["component"]
        prepared = item["prepared"]
        same = bool(prepared and prepared["boot_id"] == boot_id and item["expires_at"] > now
                    and prepared["payload_digest"] == target_components[component]["payload_digest"]
                    and prepared["configuration_digest"] == target_components[component]["configuration_digest"])
        result.append({"component": component, "operation_id": item["operation_id"], "prepared": prepared,
                       "compatible": same, "reason": "UNCHANGED_EXECUTOR" if same else "REPREPARATION_REQUIRED"})
    return result


def observe_reboot_closure(profile, component, *, expected_boot, current_boot):
    """Only actual old-boot task parents/jobs can discharge lost pipe custody.

    Reuse the offline import's bounded, independent systemd/cgroup observer.
    This proves process closure; original outcome and missing pipe bytes stay
    unknown and no finished.json or task-ledger event is manufactured.
    """
    import re
    import time
    from .bootstrap import OfflineObserver
    if (not isinstance(expected_boot, str) or not re.fullmatch(r"[0-9a-f-]{36}", expected_boot)
            or expected_boot == current_boot or startup.boot_id() != current_boot):
        raise DeployError("RETAINED_DISPATCH_UNRESOLVED", "No distinct original host boot is proven")
    observer = OfflineObserver(profile)
    path = profile["guarded_components"][component]["configuration"]
    config = decode(startup.protected_read(path, owner_uid=profile.get("owner_uid", 0)))
    kind = profile["probes"][component]["kind"]
    if kind == "resident":
        entry = {"kind": kind, "records_root": config["private_root"]}
    elif kind == "prepared":
        raw = startup.protected_read(config["launch_path"], owner_uid=profile.get("owner_uid", 0))
        if hashlib.sha256(raw).hexdigest() != config["launch_sha256"]:
            raise DeployError("RETENTION_CONFLICT", "Original fixed launch changed")
        launch = decode(raw)
        entry = {"kind": kind, "launch_path": config["launch_path"], "launch_digest": config["launch_sha256"],
                 "output": config["output"], "controller_unit": launch["controller_envelope"]["controller"]["unit"]}
    else:
        raise DeployError("RETENTION_CONFIGURATION", "Reboot closure has no original task manager")
    observer.deadline = time.monotonic() + profile.get("timeout_seconds", 30)
    with observer.bus_factory() as bus:
        proof = observer.duties(bus, entry)
    if startup.boot_id() != current_boot:
        raise DeployError("RETAINED_DISPATCH_UNRESOLVED", "Host boot changed while observing original task closure")
    return {"original_boot_id": expected_boot, "observed_boot_id": current_boot, "duties": proof}
