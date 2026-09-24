"""Pure, bounded private Q1 diagnostic encoding; not a Q2 receipt or job API.

The 128 KiB cap is for one private administrative diagnostic artifact. It does
not replace or enlarge the architecture's 32 KiB Q2 socket receipt/response cap.

An Outcome is the trusted controller's internal result, not client input. Shape
and consistency checks here cannot authenticate OS observations. No file, clock,
pipe, process, query, journal mutation or resource release is performed here.
The caller owns transmission; a failed write must never cause another query.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import PurePosixPath

from .admission import (Manifest, Root, Slot, UUID, fields, integer, match_report,
                        path, require, strict_json, token)
from .protected_inputs import decode_ticket
from .supervision import Binding, Decision
from .systemd_runtime import CONTROL_BYTES, MAX_CONTROL_CALLS, SHOW_FIELDS, Outcome


SCHEMA = "local-hand-quota-q1-experiment/v1"
MAX_EVIDENCE_BYTES = 128 * 1024
MAX_CAPTURE_BYTES = 32768
CONTROLLER_FIELDS = (
    "unit", "invocation_id", "cgroup", "cgroup_device", "cgroup_inode", "boot_id",
    "pid", "observed_ns", "stdout_pipe_device", "stdout_pipe_inode",
    "stderr_pipe_device", "stderr_pipe_inode",
)
UNVERIFIED = (
    "Q1_REAL_FIXTURE_EXIT_CRITERIA",
    "INDEPENDENT_FILESYSTEM_UUID_AND_EXCLUSIVE_ROOT",
    "STABLE_MOUNT_GENERATION_PROJECT_AND_LIMIT",
    "REAL_OVER_LIMIT_WRITE_AND_OUTSIDE_DOMAIN_DENIAL",
    "UNPRIVILEGED_PERMISSION_COMPARISON",
    "FULL_CONTROLLER_AND_RUNTIME_INSTALLATION_BASELINE",
    "LOCAL_FINITE_JOURNAL_AND_EVIDENCE_STORAGE",
    "Q2_BINDING_BUDGET_AND_CONTROL_RESPONSE",
    "E3_REAL_INTEGRATION_AND_PRODUCTION_ADMISSION",
)


def _operation(value, *, optional=False):
    require((optional and value is None) or
            (type(value) is str and value in ("run", "recover_original")), "EVIDENCE_OPERATION")
    return value


def _code(value):
    return token(value, r"[A-Z][A-Z0-9_]{0,95}")


def _ticket(value):
    # This also bounds failure-context input; full binding validation requires
    # the original manifest and is done by encode_outcome below.
    token(value, r"[A-Za-z0-9+/]{1,10922}={0,2}")
    try:
        raw = base64.b64decode(value, validate=True)
    except ValueError:
        require(False, "EVIDENCE_TICKET")
    require(len(raw) <= 8192 and base64.b64encode(raw).decode("ascii") == value,
            "EVIDENCE_TICKET")
    return {"sha256": hashlib.sha256(value.encode("ascii")).hexdigest(),
            "encoded_bytes": len(value)}


def _controller(value):
    """Copy exact guarded facts; this dict is never an admission credential."""
    fields(value, CONTROLLER_FIELDS)
    result = dict(value)
    token(result["unit"], r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.service")
    token(result["invocation_id"], r"[0-9a-f]{32}")
    path(result["cgroup"])
    require(PurePosixPath(result["cgroup"]).name == result["unit"] and
            PurePosixPath(result["cgroup"]).parent.name.endswith(".slice"),
            "EVIDENCE_CONTROLLER_CGROUP")
    token(result["boot_id"], UUID)
    integer(result["pid"], 1, 2**31 - 1)
    integer(result["observed_ns"])
    for key in ("cgroup_device", "stdout_pipe_device", "stderr_pipe_device"):
        integer(result[key])
    for key in ("cgroup_inode", "stdout_pipe_inode", "stderr_pipe_inode"):
        integer(result[key], 1)
    require((result["stdout_pipe_device"], result["stdout_pipe_inode"]) !=
            (result["stderr_pipe_device"], result["stderr_pipe_inode"]), "EVIDENCE_CONTROLLER_PIPES")
    return result


def _base(operation, *, controller_entered, source_commit, runtime_digest,
          experiment_digest, original_ticket, controller_observation):
    require(type(controller_entered) is bool, "EVIDENCE_CONTROLLER_ENTERED")
    for value, pattern in ((source_commit, r"[0-9a-f]{40}"),
                           (runtime_digest, r"[0-9a-f]{64}"),
                           (experiment_digest, r"[0-9a-f]{64}")):
        if value is not None:
            token(value, pattern)
    return {
        "schema": SCHEMA, "evidence_class": "PRIVATE_Q1_ADMIN_DIAGNOSTIC",
        "operation": operation, "controller_entered": controller_entered,
        "source_commit": source_commit, "runtime_digest": runtime_digest,
        "experiment_digest": experiment_digest,
        "original_ticket": None if original_ticket is None else _ticket(original_ticket),
        "controller_observation": (None if controller_observation is None
                                   else _controller(controller_observation)),
        "admission_proven": False, "real_e3_accepted": False, "production_supported": False,
        "q1_real_exit_accepted": False,
        "retention": {
            "policy": "PERMANENT_NO_RELEASE_OR_REUSE", "max_intents": 32,
            "intent_consumption": "NOT_DETERMINED_BY_THIS_RECORD",
            "resource_release_authorized": False,
            "reserved_identities": ["request_id", "allocation_digest", "slot_ref", "root_device_inode",
                                    "filesystem_uuid_project_id"],
        },
        "unverified": list(UNVERIFIED),
    }


def _encode(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    require(len(raw) <= MAX_EVIDENCE_BYTES, "EVIDENCE_BYTE_LIMIT")
    return raw


def _binding(binding, original_ticket, source_commit):
    require(type(binding) is Binding and type(binding.manifest) is Manifest and
            type(binding.slot) is Slot and type(binding.slot.root) is Root, "EVIDENCE_BINDING")
    manifest, slot = binding.manifest, binding.slot
    require(type(manifest.slots) is tuple and 1 <= len(manifest.slots) <= 32,
            "EVIDENCE_MANIFEST_SLOTS")
    require(all(type(item) is Slot for item in manifest.slots), "EVIDENCE_MANIFEST_SLOTS")
    require(decode_ticket(original_ticket, manifest) == binding, "EVIDENCE_TICKET_BINDING")
    require(manifest.source_commit == source_commit, "EVIDENCE_SOURCE_CHANGED")
    token(manifest.source_commit, r"[0-9a-f]{40}")
    for value in (manifest.digest, manifest.authority_digest, manifest.installation_digest):
        token(value, r"[0-9a-f]{64}")
    token(manifest.boot_id, UUID)
    token(manifest.epoch, r"[0-9a-f]{32}")
    for value in (binding.request_id, binding.execution_id, slot.generation):
        token(value, r"[0-9a-f]{32}")
    token(binding.allocation_digest, r"[0-9a-f]{64}")
    token(binding.phase, r"preflight|business|reconcile|evidence")
    token(binding.unit, r"lhq-[0-9a-f]{64}\.service")
    token(slot.ref, r"[a-z0-9][a-z0-9_.-]{0,63}")
    integer(binding.issued_ns)
    integer(binding.deadline_ns, binding.issued_ns + 1)
    token(slot.filesystem_uuid, UUID)
    token(slot.filesystem, r"ext4|xfs")
    integer(slot.root.device)
    integer(slot.root.inode, 1)
    integer(slot.project_id, 1, 2**32 - 1)
    require(integer(slot.xflags, 0, 2**32 - 1) & 0x200, "PROJECT_INHERIT")
    require(integer(slot.hard_bytes, 1024) % 1024 == 0, "PROJECT_LIMIT")
    path(manifest.cgroup_parent)
    path(binding.cgroup)
    return {
        "manifest_digest": manifest.digest, "authority_digest": manifest.authority_digest,
        "installation_digest": manifest.installation_digest, "boot_id": manifest.boot_id,
        "epoch": manifest.epoch, "request_id": binding.request_id,
        "allocation_digest": binding.allocation_digest, "execution_id": binding.execution_id,
        "phase": binding.phase, "issued_ns": binding.issued_ns, "deadline_ns": binding.deadline_ns,
        "unit": binding.unit, "cgroup": binding.cgroup, "cgroup_parent": manifest.cgroup_parent,
        "root": {"logical_ref": slot.ref, "generation": slot.generation,
                 "device": slot.root.device, "inode": slot.root.inode,
                 "filesystem": slot.filesystem, "filesystem_uuid": slot.filesystem_uuid,
                 "project_id": slot.project_id, "xflags": slot.xflags, "hard_bytes": slot.hard_bytes},
    }


def _decision(value):
    require(type(value) is Decision, "EVIDENCE_DECISION")
    require(type(value.status) is str and value.status in ("OBSERVED", "UNKNOWN", "WAITING"),
            "EVIDENCE_DECISION_STATUS")
    _code(value.reason)
    flags = (value.query_stopped, value.facts_match, value.admission_proven,
             value.real_e3_accepted, value.production_supported)
    require(all(type(item) is bool for item in flags), "EVIDENCE_DECISION_FLAGS")
    require(not any(flags[2:]), "EVIDENCE_UNSUPPORTED_CLAIM")
    require(not value.facts_match or value.status == "OBSERVED", "EVIDENCE_FACTS_CLAIM")
    if value.status == "OBSERVED":
        require(value.query_stopped and value.facts_match and value.reason == "PINNED_FACTS_MATCH",
                "EVIDENCE_OBSERVED_CLAIM")
    return {"status": value.status, "reason": value.reason, "query_stopped": value.query_stopped,
            "facts_match": value.facts_match, "admission_proven": False,
            "real_e3_accepted": False, "production_supported": False}


def _unit_facts(value):
    require(type(value) is tuple and len(value) in (0, len(SHOW_FIELDS)), "EVIDENCE_UNIT_FACTS")
    result, size = {}, 0
    for item in value:
        require(type(item) is tuple and len(item) == 2, "EVIDENCE_UNIT_FACTS")
        key, text = item
        require(type(key) is str and key in SHOW_FIELDS and key not in result and type(text) is str,
                "EVIDENCE_UNIT_FACTS")
        require(len(text) <= CONTROL_BYTES, "EVIDENCE_UNIT_FACT_LIMIT")
        try:
            size += len(key) + len(text.encode("utf-8", "strict")) + 2
        except UnicodeError:
            require(False, "EVIDENCE_UNIT_FACT_ENCODING")
        require(size <= CONTROL_BYTES, "EVIDENCE_UNIT_FACT_LIMIT")
        result[key] = text
    return result


def _observed_consistency(outcome, unit_facts, runtime_digest):
    """Reject conflicting success claims; do not reconstruct missing EOF facts."""
    binding = outcome.binding
    require(outcome.invocation_id is not None and not outcome.pending_clients and
            outcome.cleanup_reason is None and outcome.journal_reason is None and
            outcome.control_calls > 0, "EVIDENCE_OBSERVED_CONFLICT")
    fields(unit_facts, SHOW_FIELDS)
    expected = {
        "Id": binding.unit, "LoadState": "loaded", "InvocationID": outcome.invocation_id,
        "ExecMainCode": "1", "ExecMainStatus": "0", "Result": "success",
        "Slice": PurePosixPath(binding.manifest.cgroup_parent).name,
        "Type": "exec", "ExitType": "cgroup", "RemainAfterExit": "yes", "Restart": "no",
        "KillMode": "control-group", "ExecStop": "", "ExecStopPost": "",
        "ExecReload": "", "TriggeredBy": "",
    }
    require(all(unit_facts[key] == value for key, value in expected.items()) and
            unit_facts["ControlGroup"] in (binding.cgroup, "") and unit_facts["Job"] in ("", "0") and
            ((unit_facts["ActiveState"], unit_facts["SubState"]) == ("active", "exited") or
             unit_facts["ActiveState"] in ("inactive", "failed")), "EVIDENCE_OBSERVED_UNIT")
    line, separator, native = outcome.stdout.partition(b"\n")
    require(separator and len(line) <= 2048, "EVIDENCE_WORKER_READY")
    ready = fields(strict_json(line, 2048, depth=2), (
        "schema", "boot_id", "unit", "invocation_id", "cgroup", "manifest_digest", "runtime_digest",
        "request_id"))
    require(ready == {"schema": "local-hand-quota-worker-ready/v1", "boot_id": binding.manifest.boot_id,
                      "unit": binding.unit, "invocation_id": outcome.invocation_id,
                      "cgroup": binding.cgroup, "manifest_digest": binding.manifest.digest,
                      "runtime_digest": runtime_digest, "request_id": binding.request_id},
            "EVIDENCE_WORKER_IDENTITY")
    match_report(native, binding.manifest, binding.slot)


def encode_outcome(outcome, *, operation, source_commit, runtime_digest, experiment_digest,
                   original_ticket, controller_observation, entry_error=None):
    """Serialize one original internal result, retaining captured bytes exactly.

    stdout/stderr describe stored bytes only. Outcome does not carry the two EOF
    flags, capture overflow flags or launcher return code; neither a parseable
    stdout nor query_stopped allows this serializer to invent those facts.
    """
    require(type(outcome) is Outcome, "EVIDENCE_OUTCOME")
    _operation(operation)
    for value, pattern in ((source_commit, r"[0-9a-f]{40}"), (runtime_digest, r"[0-9a-f]{64}"),
                           (experiment_digest, r"[0-9a-f]{64}")):
        token(value, pattern)
    require(controller_observation is not None, "EVIDENCE_CONTROLLER_REQUIRED")
    if entry_error is not None:
        _code(entry_error)
    result = _base(operation, controller_entered=True, source_commit=source_commit,
                   runtime_digest=runtime_digest, experiment_digest=experiment_digest,
                   original_ticket=original_ticket, controller_observation=controller_observation)
    result["binding"] = _binding(outcome.binding, original_ticket, source_commit)
    require(result["controller_observation"]["boot_id"] == outcome.binding.manifest.boot_id,
            "EVIDENCE_CONTROLLER_BOOT")
    control_group = PurePosixPath(result["controller_observation"]["cgroup"])
    query_group = PurePosixPath(outcome.binding.manifest.cgroup_parent)
    require(control_group != query_group and control_group not in query_group.parents and
            query_group not in control_group.parents, "EVIDENCE_CONTROLLER_QUERY_TREE")
    result["decision"] = _decision(outcome.decision)
    require(operation != "recover_original" or outcome.decision.status == "UNKNOWN",
            "EVIDENCE_RECOVERY_STATUS")
    require(type(outcome.stdout) is bytes and type(outcome.stderr) is bytes and
            len(outcome.stdout) + len(outcome.stderr) <= MAX_CAPTURE_BYTES, "EVIDENCE_CAPTURE_LIMIT")
    if outcome.invocation_id is not None:
        token(outcome.invocation_id, r"[0-9a-f]{32}")
    require(path(outcome.empty_scope) == outcome.binding.manifest.cgroup_parent, "EVIDENCE_EMPTY_SCOPE")
    integer(outcome.control_calls, 0, MAX_CONTROL_CALLS)
    for reason in (outcome.cleanup_reason, outcome.journal_reason):
        if reason is not None:
            _code(reason)
    require(type(outcome.pending_clients) is tuple and
            len(outcome.pending_clients) <= outcome.control_calls + 1, "EVIDENCE_PENDING_CLIENTS")
    for pid in outcome.pending_clients:
        integer(pid, 1, 2**31 - 1)
    require(len(set(outcome.pending_clients)) == len(outcome.pending_clients), "EVIDENCE_PENDING_CLIENTS")
    unit_facts = _unit_facts(outcome.unit_facts)
    if outcome.decision.status == "OBSERVED":
        _observed_consistency(outcome, unit_facts, runtime_digest)
    result.update(status="OBSERVED" if outcome.decision.status == "OBSERVED" and entry_error is None
                  else "UNKNOWN", entry_error=entry_error,
                  invocation_id=outcome.invocation_id, empty_scope=outcome.empty_scope,
                  control_calls=outcome.control_calls, pending_clients=list(outcome.pending_clients),
                  unit_facts=unit_facts, cleanup_reason=outcome.cleanup_reason,
                  journal_reason=outcome.journal_reason,
                  capture={name: {"encoding": "base64", "bytes": len(raw),
                                   "data": base64.b64encode(raw).decode("ascii")}
                           for name, raw in (("stdout", outcome.stdout), ("stderr", outcome.stderr))},
                  capture_completeness="NOT_REPRESENTED_BY_OUTCOME",
                  independent_eof_facts="NOT_REPRESENTED_BY_OUTCOME",
                  evidence_complete=False)
    return _encode(result)


def encode_failure(code, *, operation=None, controller_entered=False, source_commit=None,
                   runtime_digest=None, experiment_digest=None, original_ticket=None,
                   controller_observation=None, status=None, entry_error=None):
    """A stable failure code, never exception text or a claim of no delivery.

    Context pins must already have been validated by the entry point. No binding
    or consumption claim is inferred without an Outcome. A controller-entered
    failure is always UNKNOWN, including any recovery failure.
    """
    _code(code)
    if entry_error is not None:
        _code(entry_error)
    _operation(operation, optional=True)
    require(type(controller_entered) is bool, "EVIDENCE_CONTROLLER_ENTERED")
    require(status is None or (type(status) is str and status == "UNSUPPORTED" and
                               not controller_entered), "EVIDENCE_FAILURE_STATUS")
    result = _base(operation, controller_entered=controller_entered, source_commit=source_commit,
                   runtime_digest=runtime_digest, experiment_digest=experiment_digest,
                   original_ticket=original_ticket, controller_observation=controller_observation)
    result.update(status=status or ("UNKNOWN" if controller_entered else "REJECTED"),
                  failure_code=code, entry_error=entry_error, outcome_available=False,
                  evidence_complete=False)
    return _encode(result)
