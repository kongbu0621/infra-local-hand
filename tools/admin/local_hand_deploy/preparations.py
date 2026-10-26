"""Bounded, read-only inventory of the original final-admission records.

These records are never rewritten by deployment. Compatibility concerns an
exact preparation and unchanged executor, not arbitrary cross-version jobs.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import uuid

from local_hand_jobs import maintenance, startup
from local_hand_jobs.contract import JobError, validate_tool_args

from .model import DeployError, decode, digest

MAX_TASKS = 128
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_ORPHAN_ENTRIES = 128


def inventory(profile, *, candidates=None):
    candidates = candidates or {}
    owner = profile.get("owner_uid", 0)
    remaining = MAX_INPUT_BYTES
    admissions = {}

    def read(path):
        nonlocal remaining
        raw = startup.protected_read(path, owner_uid=owner, maximum=min(2 * 1024 * 1024, remaining))
        remaining -= len(raw)
        if remaining <= 0:
            raise DeployError("RETENTION_LIMIT", "Preparation inventory exceeds its byte budget")
        return decode(raw), hashlib.sha256(raw).hexdigest()

    def admission_snapshot(config):
        nonlocal remaining
        gate = maintenance.from_config(config)
        if (gate is None or str(gate.directory) != profile['maintenance_directory']
                or config['maintenance']['startup_descriptor'] != profile['startup_descriptor']):
            raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation admission is not bound')
        key = (str(gate.directory), gate.node_id)
        if key not in admissions:
            snapshot = maintenance.MaintenanceGate(gate.directory, gate.node_id, owner_uid=owner).snapshot()
            remaining -= len(maintenance.canonical_bytes(snapshot))
            if remaining <= 0:
                raise DeployError('RETENTION_LIMIT', 'Preparation inventory exceeds its byte budget')
            admissions[key] = snapshot
        return admissions[key]

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
            task_count = 0
            try:
                # Enforce the limit while enumerating, before sorting/reading.
                with os.scandir(fd) as entries:
                    for entry in entries:
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                        if task_count >= min(config["max_tasks"], MAX_TASKS):
                            raise DeployError("RETENTION_LIMIT", "Preparation inventory exceeds its task budget")
                        task_count += 1
                        try:
                            record, record_hash = read(str(root / entry.name / "current.json"))
                        except JobError as error:
                            if not isinstance(error.__cause__, FileNotFoundError):
                                raise
                            records.extend(_unpublished_preparations(profile, config, component, root, entry.name,
                                                                    admission_snapshot(config)))
                            continue
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
            if record.get('record_source') == 'admission':
                item['record_source'] = 'admission'
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
    result["tasks"].sort(key=lambda item: (item["component"], item["operation_id"], item.get('admission_id') or ''))
    return result


def _never_dispatched(duty):
    return (duty['state'] == 'ACCEPTED'
            or duty['state'] == 'CLOSED' and duty['proof'] == {'never_dispatched': True})


def _unpublished_preparations(profile, config, component, root, operation, snapshot):
    """Inventory original admissions from the mkdir-before-current window.

    Only empty, exactly reserved attempts can precede current publication.
    The stable identity excludes mutable gate state/proof; closing a duty does
    not rewrite its inventory, and no current record or result is manufactured.
    """
    duties = [duty for duty in snapshot['responsibilities'].values()
              if duty['operation_id'] == operation and duty['loaded']['component'] == component]
    if any(duty['kind'] != 'prepare' for duty in duties):
        raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation has retained execution history')
    if len(duties) > MAX_ORPHAN_ENTRIES:
        raise DeployError('RETENTION_LIMIT', 'Preparation admission inventory exceeds its entry budget')
    if not duties:
        raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation has no bounded admission binding')
    for duty in duties:
        if not _never_dispatched(duty):
            raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation was dispatched without its current record')
        original_preparation(profile, duty, configuration=config)
    attempts = {duty['attempt_id'] for duty in duties}
    if len(attempts) != len(duties) or len({duty['binding']['principal_id'] for duty in duties}) != 1:
        raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation identities differ')
    owner = profile.get('owner_uid', 0)
    directory = startup._protected_directory(root / operation, owner_uid=owner)
    try:
        with os.scandir(directory) as entries:
            for count, entry in enumerate(entries):
                if count >= MAX_ORPHAN_ENTRIES:
                    raise DeployError('RETENTION_LIMIT', 'Preparation attempt inventory exceeds its entry budget')
                path = root / operation / entry.name
                if not entry.is_dir(follow_symlinks=False) or str(path) not in attempts:
                    raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation contains an unmatched entry')
                attempt = startup._protected_directory(path, owner_uid=owner)
                try:
                    with os.scandir(attempt) as children:
                        if next(children, None) is not None:
                            raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation has unexplained attempt content')
                finally:
                    os.close(attempt)
    finally:
        os.close(directory)
    result = []
    for duty in duties:
        identity = {key: value for key, value in duty.items() if key not in {'state', 'proof'}}
        result.append(({'operation_id': operation, 'state': 'PREPARING', 'boot_id': duty['loaded']['boot_id'],
                        'maintenance_admission': {'id': duty['id']}, 'record_source': 'admission'}, digest(identity)))
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


def original_preparation(profile, duty, *, configuration=None):
    """Bind an orphan prepare duty without adopting the current attempt.

    ACCEPTED predates all dispatch and may predate every task directory. A
    dispatched old attempt still needs its own delivery and retained task root;
    the caller must separately prove the original boot's processes/jobs closed.
    Return whether an exact delivery remains, including never-started attempts
    that wrote their command before failing to create a process.
    """
    owner = profile.get('owner_uid', 0)
    try:
        component = duty['loaded']['component']
        guard = profile['guarded_components'][component]
        config = (decode(startup.protected_read(guard['configuration'], owner_uid=owner))
                  if configuration is None else configuration)
        binding = duty['binding']
        operation = duty['operation_id']
        arguments = binding['arguments']
        validate_tool_args('lh_job_prepare', arguments)
        root = Path(config['private_root'])
        attempt = Path(duty['attempt_id'])
        valid = (duty['kind'] == 'prepare' and profile['probes'][component]['kind'] == 'resident'
                 and 'prepare' in guard['entrypoints']
                 and set(binding) == {'arguments', 'principal_id', 'private_root'}
                 and type(binding['principal_id']) is str and 0 < len(binding['principal_id']) <= 256
                 and duty['loaded']['node_id'] == config['maintenance']['node_id']
                 and arguments['operation_id'] == operation and binding['private_root'] == str(root)
                 and str(attempt) == duty['attempt_id'] and attempt.parent == root / operation
                 and re.fullmatch(r'attempt-[1-9][0-9]{0,19}', attempt.name))
        if not valid:
            raise ValueError('binding differs')
        try:
            current = decode(startup.protected_read(root / operation / 'current.json', owner_uid=owner))
        except JobError as error:
            # protected_read wraps I/O errors. Only actual absence is allowed
            # before dispatch; denied/aliased/damaged objects remain failures.
            if not _never_dispatched(duty) or not isinstance(error.__cause__, FileNotFoundError):
                raise
        else:
            if (type(current) is not dict or current.get('operation_id') != operation
                    or current.get('principal_id') != binding['principal_id']):
                raise ValueError('task binding differs')
            if (current.get('attempt') == duty['attempt_id'] and current.get('boot_id') is not None
                    and current['boot_id'] != duty['loaded']['boot_id']):
                raise ValueError('attempt boot differs')
        try:
            delivery = decode(startup.protected_read(attempt / 'preparation-delivery.json', owner_uid=owner))
        except JobError as error:
            if _never_dispatched(duty) and isinstance(error.__cause__, FileNotFoundError):
                return False
            raise
        unit = 'lhprepare' + uuid.UUID(operation).hex + 'a' + attempt.name.removeprefix('attempt-') + '.service'
        command = delivery.get('command') if type(delivery) is dict else None
        if (type(command) is not list or not all(type(arg) is str for arg in command)
                or [arg for arg in command if arg.startswith('--unit=')] != ['--unit=' + unit]
                or command[-2:] != [str(attempt / 'input.json'), str(attempt / 'result.json')]):
            raise ValueError('delivery binding differs')
        return True
    except (KeyError, TypeError, ValueError, JobError) as error:
        raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation binding differs') from error


def original_not_started(profile, duty):
    """Read the original no-child receipt after preparation identity checking."""
    proof = {'schema': 'local-hand-preparation-not-started/v1', 'admission_id': duty['id'],
             'binding_digest': duty['binding_digest']}
    if duty['state'] != 'CLOSED' or duty['proof'] != {'never_dispatched': True}:
        raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation has no closed non-delivery responsibility')
    actual = decode(startup.protected_read(Path(duty['attempt_id']) / 'preparation-not-started.json',
                                          owner_uid=profile.get('owner_uid', 0)))
    if actual != proof:
        raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation no-start binding differs')
    return proof


def observe_reboot_closure(profile, component, *, expected_boot, current_boot, preparation_boots=None,
                          preparation_unstarted=None):
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
    if preparation_boots is not None:
        root = Path(config['private_root']) if kind == 'resident' else None
        if (type(preparation_boots) is not dict or root is None or any(
                type(path) is not str or str(Path(path)) != path or Path(path).parent.parent != root
                or re.fullmatch(r'attempt-[1-9][0-9]{0,19}', Path(path).name) is None
                or type(boot) is not str or re.fullmatch(r'[0-9a-f-]{36}', boot) is None or boot == current_boot
                for path, boot in preparation_boots.items())):
            raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation boot binding differs')
    if preparation_unstarted is not None:
        root = Path(config['private_root']) if kind == 'resident' else None
        if (type(preparation_unstarted) is not dict or root is None or any(
                type(path) is not str or str(Path(path)) != path or Path(path).parent.parent != root
                or re.fullmatch(r'attempt-[1-9][0-9]{0,19}', Path(path).name) is None
                or type(proof) is not dict or set(proof) != {'schema', 'admission_id', 'binding_digest'}
                or proof['schema'] != 'local-hand-preparation-not-started/v1'
                or type(proof['admission_id']) is not str or re.fullmatch(r'[0-9a-f]{32}', proof['admission_id']) is None
                or type(proof['binding_digest']) is not str or re.fullmatch(r'[0-9a-f]{64}', proof['binding_digest']) is None
                for path, proof in preparation_unstarted.items())):
            raise DeployError('RETAINED_DISPATCH_UNRESOLVED', 'Original preparation no-start binding differs')
    observer.deadline = time.monotonic() + profile.get("timeout_seconds", 30)
    with observer.bus_factory() as bus:
        bindings = {}
        if preparation_boots:
            bindings['preparation_boots'] = preparation_boots
        if preparation_unstarted:
            bindings['preparation_unstarted'] = preparation_unstarted
        proof = observer.duties(bus, entry, **bindings)
    if startup.boot_id() != current_boot:
        raise DeployError("RETAINED_DISPATCH_UNRESOLVED", "Host boot changed while observing original task closure")
    return {"original_boot_id": expected_boot, "observed_boot_id": current_boot, "duties": proof}
