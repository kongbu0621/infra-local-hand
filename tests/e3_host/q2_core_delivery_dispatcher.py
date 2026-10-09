"""Strict field dispatcher for the closed Q2 core acceptance delivery.

The module is a field blob: it is deliberately self-contained and must not
import another D helper.  ``dispatch`` owns all ordering and validation.  The
``FieldEffects`` object owns operating-system effects and is injected into the
dispatcher so the contract can be tested without substituting modeled case
results for field evidence.

Current-guest admission and resource accounting are under the approved completion
adjustment. Field release remains closed; component tests are not field evidence.
"""
from __future__ import annotations

import base64
import csv
import copy
from functools import partial
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import resource
import selectors
import signal
import stat
import struct
import subprocess
import time
import zipfile


class DispatchError(RuntimeError):
    """A stable fail-closed dispatcher rejection."""


def _require(condition, code):
    if not condition:
        raise DispatchError(code)


def _pairs(items):
    result = {}
    for key, value in items:
        _json(type(key) is str and key not in result, "DUPLICATE")
        result[key] = value
    return result


def _nonfinite(_value):
    raise _json.error("NONFINITE")


def _shape(value, depth=0, count=None):
    count = [0] if count is None else count
    count[0] += 1
    _json(depth <= 32 and count[0] <= 262144, "COMPLEXITY")
    _json(not isinstance(value, float), "FLOAT")
    if isinstance(value, dict):
        _json(all(type(key) is str for key in value), "KEY")
        for item in value.values():
            _shape(item, depth + 1, count)
    elif isinstance(value, list):
        for item in value:
            _shape(item, depth + 1, count)
    else:
        _json(value is None or type(value) in (str, int, bool), "VALUE")
        if type(value) is int:
            _json(-(2**63) <= value < 2**63, "INTEGER")
    return value


def _fields(names):
    """Ordered fixed schema names; callers supply source literals only."""
    return tuple(names.split())


def canonical(value, *, newline=False, limit=None):
    _shape(value)
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as error:
        raise _json.error("ENCODE") from error
    if newline:
        raw += b"\n"
    if limit is not None:
        _json(0 < len(raw) <= limit, "LIMIT")
    return raw


def document(raw, *, limit, newline=True):
    _json(type(raw) is bytes and 0 < len(raw) <= limit, "LIMIT")
    _json(raw.endswith(b"\n") == newline and
        (not newline or not raw.endswith(b"\n\n")), "NEWLINE")
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
            parse_constant=_nonfinite)
    except DispatchError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise _json.error("DECODE") from error
    _shape(value)
    _json(canonical(value, newline=newline) == raw, "CANONICAL")
    return value


def _exact(value, fields, code):
    _require(type(value) is dict and set(value) == set(fields), code)
    return value


def _integer(value, low=0, high=2**63 - 1, code="CORE_DISPATCH_INTEGER"):
    _require(type(value) is int and low <= value <= high, code)
    return value


def _digest(value, code="CORE_DISPATCH_DIGEST"):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        code)
    return value


def _commit(value, code="CORE_DISPATCH_COMMIT"):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None,
        code)
    return value


def _path(value, code="CORE_DISPATCH_PATH"):
    _require(type(value) is str and value.isascii() and 0 < len(value) <= 4096
        and re.fullmatch(r"[A-Za-z0-9._/-]+", value) is not None
        and "//" not in value and "\\" not in value and "\0" not in value,
        code)
    parsed = PurePosixPath(value)
    _require(not parsed.is_absolute() and parsed.as_posix() == value
        and all(part not in ("", ".", "..") for part in parsed.parts), code)
    return value


def _sha(raw):
    _check(type(raw) is bytes or (isinstance(raw, memoryview) and raw.readonly),
        "BYTES")
    return hashlib.sha256(raw).hexdigest()


class _Checks:
    """Use a stable error-code prefix while retaining the primitive validators."""

    def __init__(self, prefix):
        self.prefix = prefix

    def __call__(self, condition, code):
        _require(condition, self.prefix + code)

    def exact(self, value, fields, code):
        return _exact(value, fields, self.prefix + code)

    def integer(self, value, low=0, high=2**63 - 1, code="INTEGER"):
        return _integer(value, low, high, self.prefix + code)

    def digest(self, value, code="DIGEST"):
        return _digest(value, self.prefix + code)

    def commit(self, value, code="COMMIT"):
        return _commit(value, self.prefix + code)

    def path(self, value, code="PATH"):
        return _path(value, self.prefix + code)

    def absolute(self, value, code):
        return _absolute_text(value, self.prefix + code)

    def program(self, value, code):
        return _program_identity(value, self.prefix + code)

    def error(self, code):
        return DispatchError(self.prefix + code)


_admit = _Checks('CORE_DISPATCH_ADMISSION_')
_plan = _Checks('CORE_DISPATCH_PLAN_')
_h11 = _Checks('CORE_DISPATCH_H11_')
_remote = _Checks('CORE_DISPATCH_REMOTE_')
_phase_raw = _Checks('CORE_EFFECT_PHASE_')
_package = _Checks('CORE_EFFECT_PACKAGE_')
_wheel = _Checks('CORE_EFFECT_WHEEL_')
_approved = _Checks('CORE_DISPATCH_APPROVED_')
_json = _Checks('CORE_DISPATCH_JSON_')
_envelope = _Checks('CORE_DISPATCH_PACKAGE_')
_phase = _Checks('CORE_DISPATCH_PHASE_')
_projection = _Checks('CORE_EFFECT_PROJECTION_')
_check = _Checks('CORE_DISPATCH_')
_effect = _Checks('CORE_EFFECT_')
_cap = _Checks('CORE_CAP_')


SCOPE = "LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1"
SESSION = "lhqcore-20261007a"
RULE = {
    "commit": "10d2a5c827964989f41ca6e8eeac3d44de6d0f04",
    "source_sha256": "c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5",
}
BASELINE = {
    "commit": "74366b3fe41e675b1aa2d677228714a5606c275c",
    "tree": "7df4fd0c876df13af4ec73c6f910272a72d7ea4d",
    "documents_sha256": {
        "docs/a2-execution/Q2_CORE_LIVE_INPUT_REVIEW_20261003.md":
        "39853b72755e4737b5329856691e1f616cfd2ffdf403d1c06cbeccff89686f1c",
        "docs/a2-execution/q2-core-acceptance-delivery/ARCHITECTURE.md":
        "7599870a39f04a68a84992dbc2f3035ba202963fc1cc688914f9b5fa596b54ab",
        "docs/a2-execution/q2-core-acceptance-delivery/IMPLEMENTATION_PLAN.md":
        "dd128597f90cfdf38d4a9f716fa53fd12acbb12cbc86c261f3f9c760477938c1",
        "docs/a2-execution/q2-core-acceptance-delivery/REQUIREMENTS.md":
        "8ef192452302ae2c2c55c38dd6889a0a62265404f4baa823be097f0a2524ce76",
    },
}
OWNER_DECISION = {
    "event": "LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01",
    "record_path": "docs/governance/Q2_CORE_ACCEPTANCE_DELIVERY_OWNER_DECISION.md",
    "record_sha256": "e6a810ac5a76c903c687b6487ac2a4b08e02022fcf90927f7a34993dedb695cb",
}
CLOSURE = {
    "commit": "a8dd077392ebb656770c8f94ca3b051e93fc296d",
    "tree": "b0d651ea5cbc2c408bb43ce6f3cdc5becd5170c6",
}
AMENDMENT_BASELINE = {
    "commit": "0bdb49cae5586be60a7ba31d4a8e8367854d1e8c",
    "tree": "ee15aa4fa26fd2e87b40f6fad72828265e5cf9bc",
    "documents_sha256": {
        "docs/a2-execution/q2-core-binding-finalization-amendment/REQUIREMENTS.md":
        "e6b29c45c550f2ae8b3eaa91baad8d1382851dec6a69e2f807cce9233b14cdb1",
        "docs/a2-execution/q2-core-binding-finalization-amendment/ARCHITECTURE.md":
        "7782e2fb89a28052978d3ce205278906b92752e3ba1add9cd634c0e7c0f92c96",
        "docs/a2-execution/q2-core-binding-finalization-amendment/IMPLEMENTATION_PLAN.md":
        "52faaf002d9b5b9d88aef0b6f568e8ed56d2aa49eb0ea41e7eeb85d2d0b64cce",
    },
}
AMENDMENT_OWNER_DECISION = {
    "event": "LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-CLOSURE-20261004-01",
    "record_path": "docs/governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_OWNER_DECISION.md",
    "record_sha256": "800f01b3e7d4aeec77095bbc67196837427a7dbece7f1212bca266adb3d9ddbd",
}
AMENDMENT_CLOSURE = {
    "commit": "7598886e15ed6911fe0e09e2f8d66203455f9057",
    "tree": "7f2178942c126f883829a139b842cfc2c2e12159",
}
COMPLETION_ADJUSTMENT_BASELINE = {
    "commit": "851a1afe4e55196212aa6913e81e0722deed1032",
    "tree": "5b6c8d3a55d8d0678f2b4543f13df32016630fdd",
    "documents_sha256": {
        "docs/a2-execution/q2-core-completion-adjustment/REQUIREMENTS.md":
            "08bba40c9d9c49b2b8af3a15310597514ea61641512b5ca43c70de35f06d46d1",
        "docs/a2-execution/q2-core-completion-adjustment/ARCHITECTURE.md":
            "adc7e6be062c6b85deacc774d148bce515aa51c965b3dd31152cee4a73f1455f",
        "docs/a2-execution/q2-core-completion-adjustment/IMPLEMENTATION_PLAN.md":
            "a70d51557f034f5f0ec7e626eb6226064a4e604fd6f217267282fe524495f60c",
    },
}
COMPLETION_ADJUSTMENT_OWNER_DECISION = {
    "event": "LH-Q2-CORE-COMPLETION-ADJUSTMENT-CLOSURE-20261004-01",
    "record_path": "docs/governance/Q2_CORE_COMPLETION_ADJUSTMENT_OWNER_DECISION.md",
    "record_sha256": "0f6ec728c28ca658b4c77ab035cc42bbb57e1dbe72a1a8606e579ce08b2a1757",
}
COMPLETION_ADJUSTMENT_CLOSURE = {
    "commit": "c32799c03a32d81deec02f7492c1b71eb47b2b6d",
    "tree": "1ccf7b10f65e43f5099c17c7c7fb7e9f5e5da77b",
}
CANDIDATE = {
    "commit": "4b6e4a7c403362358192086b88679e1326dcb2e1",
    "tree": "4d4349580c9f4b67cc26f601126849c2bc8d76a4",
}
WHEEL = {
    "basename": "infra_local_hand-0.2.0a1-py3-none-any.whl",
    "bytes": 288375,
    "sha256": "ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9",
    "payload_digest": "b4d094a9f70c308c63870c9fbf273b6b0646ad211d6f61a79901f52e67cf2e23",
}
PROJECTION = {
    "basename": ".local-hand-source-projection.json",
    "bytes": 11811,
    "sha256": "55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d",
    "file_count": 89,
}

INSTALL_BASENAME = "local-hand-core-acceptance-20261007a"
STAGING_BASENAME = ".local-hand-core-acceptance-20261007a.staging"
PREPARATION_HELPERS = _fields('q2_prepare_contract q2_prepare_driver q2_prepare_assembly')
WHEEL_PACKAGES = _fields('local_hand local_hand_connect local_hand_jobs local_hand_mcp')
WHEEL_METADATA = "local_hand/_build_metadata.json"
PROJECTION_HARNESS = frozenset({
    "tests/e3_host/q2_fixture_check.py",
    "tests/e3_host/q2_launcher.py",
    "tests/e3_host/q2_prepare_assembly.py",
    "tests/e3_host/q2_prepare_driver.py",
    "tests/e3_host/q2_prepare_run.py",
    "tests/e3_host/q2_resident.py",
    "tests/e3_host/q2_supervisor.py",
    "tests/e3_host/q4_cancel_case.py",
    "tests/e3_host/q4_cancel_runtime.py",
    "tests/e3_host/q4_h11_recovery.py",
})
PROJECTION_REQUIRED = PROJECTION_HARNESS | frozenset({
    "tools/admin/local_hand_quota_observer/q2_entry.py",
    "tools/admin/local_hand_system_manager/__init__.py",
    "tools/admin/local_hand_system_manager/server.py",
    "tools/local_hand/__init__.py",
    "tools/local_hand/provenance.py",
    "tools/local_hand_connect/__init__.py",
    "tools/local_hand_jobs/__init__.py",
    "tools/local_hand_mcp/__init__.py",
})

# Static preimages and current-guest collectors are now connected. This is
# source readiness only, not a claim that a guest has been observed or admitted.
# Source effects are connected. Private release review and the independent host
# digest allowlist remain separate prerequisites for issuing the one carrier.
UNBOUND_APPROVED_INPUTS = ()
UNIMPLEMENTED_FIELD_EFFECTS = ()

OUTPUT_MAGIC = b"LHCOUT1\n"
PACKAGE_MAGIC = b"LHCFP1\n"
CONTEXT_SCHEMA = "local-hand-q2-core-bootstrap-context/v1"
OUTPUT_SCHEMA = "local-hand-q2-core-output-package/v1"
REMOTE_SCHEMA = "local-hand-q2-core-remote-result/v2"
RESOURCE_SCHEMA = "local-hand-q2-core-resource-accounting/v1"
INTENT_SCHEMA = "local-hand-q2-core-case-intent/v1"
PLAN_SCHEMA = "local-hand-q2-core-case-plan/v1"
RECEIPT_SCHEMA = "local-hand-q2-core-phase-receipt/v1"
VERDICT_SCHEMA = "local-hand-q2-core-case-verdict/v1"
PROOF_SCHEMA = "local-hand-q2-core-h11-recovery-proof/v1"
CONSUMPTION_SCHEMA = "local-hand-q2-core-carrier-consumption/v2"
PACKAGE_SCHEMA = "local-hand-q2-core-field-package/v3"
HELLO_SCHEMA = "local-hand-q2-core-carrier-hello/v2"
SESSION_SCHEMA = "local-hand-q2-core-dispatch-session/v2"
APPROVED_INPUTS_PATH = "private/approved-inputs.json"
APPROVED_INPUTS_LIMIT = 1048576
REMOTE_ALIASES = {"shell": "/bin/bash", "sudo": "/usr/bin/sudo", "env": "/usr/bin/env",
    "systemd_run": "/usr/bin/systemd-run", "python": "/usr/bin/python3"}
PROGRAM_FIELDS = {"path", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes", "sha256"}
ADMISSION_COMPONENTS = _fields('source_relation policy_basis historical_capacity_obligations retained_preparation reconciliation')

NS = 1_000_000_000
REMOTE_FINAL_RESERVE_NS = 45 * NS
CASE_GATE_NS = 315 * NS
PREPARATION_NS = 150 * NS
OWNER_NS = 120 * NS
MANIFEST_LIMIT = 1_048_576
MEMBER_LIMIT = 16_777_216
MEMBER_COUNT_LIMIT = 4096
FRAME_LIMIT = 58_716_144
STDERR_LIMIT = 4_194_304
CASE_BYTES_LIMIT = 16_777_216

LIMITS = {
    "carrier_seconds": 900, "remote_unit_seconds": 800,
    "guest_duration_cap_seconds": 750, "preparation_seconds": 150,
    "owner_seconds": 120, "case_gate_seconds": 315,
    "hello_frame_bytes": 4112, "bind_frame_bytes": 4112,
    "package_bytes": 33550320, "carrier_input_bytes": 33554432,
    "output_package_bytes": FRAME_LIMIT, "carrier_stderr_bytes": STDERR_LIMIT,
    "carrier_output_bytes": 62914560, "host_capture_bytes": 67108864,
    "host_capture_inodes": 16, "carrier_cpu_seconds": 800,
    "carrier_memory_bytes": 1073741824, "carrier_pids": 128,
    "carrier_audit_bytes": 8388608, "carrier_audit_inodes": 512,
    "shared_bytes": 67108864, "shared_inodes": 4096,
    "case_physical_bytes": 37748736, "case_physical_inodes": 2944,
    "all_case_physical_bytes": 113246208, "all_case_physical_inodes": 8832,
    "case_admission_bytes": 71303168, "case_admission_inodes": 3968,
    "all_case_admission_bytes": 213909504, "all_case_admission_inodes": 11904,
    "all_case_cpu_seconds": 1290, "total_cpu_seconds": 2090,
    "all_case_output_bytes": 50331648, "peak_memory_bytes": 2751463424,
    "peak_pids": 1160, "job_units": 15, "controller_units": 6,
    "quota_query_units": 5, "dynamic_quota_units": 15, "native_children": 16,
    "total_guest_physical_bytes": 188743680,
    "total_guest_physical_inodes": 13440,
    "total_guest_admission_bytes": 289406976,
    "total_guest_admission_inodes": 16512,
}
OUTPUT_LIMITS = {
    "frame_bytes": FRAME_LIMIT, "manifest_bytes": MANIFEST_LIMIT,
    "members": MEMBER_COUNT_LIMIT, "member_bytes": MEMBER_LIMIT,
    "stderr_bytes": STDERR_LIMIT,
}
PACKAGE_LIMITS = {
    "package_bytes": 33550320, "manifest_bytes": 1048576, "members": 4096,
    "member_bytes": 16777216, "shared_allocated_bytes": 67108864,
    "shared_entries": 4096, "carrier_audit_bytes": 8388608,
    "carrier_audit_inodes": 512, "carrier_output_bytes": 62914560,
}

DIRECTORY_ROLES = _fields('reservation state authority journal capture declarations session control profile_work profile_evidence profile_temporary store_parent')
ROOT_REFS = (
    ("work-a", "a", "work"), ("evidence-a", "a", "evidence"),
    ("temporary-a", "a", "temporary"), ("work-b", "b", "work"),
    ("evidence-b", "b", "evidence"), ("temporary-b", "b", "temporary"),
    ("retained_store", "store", "retained_store"),
)


def _unit(execution_id, suffix=""):
    return "lhj-" + hashlib.sha256((execution_id + suffix).encode("utf-8")).hexdigest() + ".service"


def _phase_units(operation_id, phases):
    result = []
    for phase in phases:
        execution = "job-" + operation_id + "-" + phase
        result.append({
            "phase": phase,
            "bootstrap_unit": _unit(execution, ":bootstrap"),
            "helper_unit": _unit(execution),
            "result_reader_unit": _unit(execution, ":result_reader"),
        })
    return result


CASES = (
    {"index": 1, "case_id": "c01-h01-normal", "kind": "H01_NORMAL",
     "predecessor": None, "preparation_id": "lhqc07a01h01normal",
     "operation_id": "9d68ffce-3e53-4933-8643-dc65e48d9ba2",
     "controller_prefix": "lhqcore20261007a-c01", "project_ids": list(range(12501, 12508)),
     "phases": ["preflight", "business", "evidence"]},
    {"index": 2, "case_id": "c02-q4-cancel", "kind": "Q4_HELPER_RUNNING_CANCEL_SUBSET",
     "predecessor": "c01-h01-normal", "preparation_id": "lhqc07a02q4cancel",
     "operation_id": "a214d2c1-f3d4-4c72-b01a-e0446626dedf",
     "controller_prefix": "lhqcore20261007a-c02", "project_ids": list(range(12508, 12515)),
     "phases": ["preflight"]},
    {"index": 3, "case_id": "c03-h11-recovery", "kind": "H11_SAME_LEDGER_RECOVERY",
     "predecessor": "c02-q4-cancel", "preparation_id": "lhqc07a03h11recovery",
     "operation_id": "bd223507-1240-456f-82e0-0ae12e0a50ea",
     "controller_prefix": "lhqcore20261007a-c03", "project_ids": list(range(12515, 12522)),
     "phases": ["preflight"]},
)


def _budget(phases):
    return {
        "operation": {"wall_seconds": 72, "terminate_grace_seconds": 1,
            "cpu_seconds": 30, "memory_bytes": 67108864, "processes": 8,
            "temporary_bytes": 1048576, "nas_bytes": 0, "log_bytes": 98304,
            "reservation_bytes": 8388608},
        "phases": [{"phase": phase, "wall_seconds": 24, "cpu_seconds": 10,
                "bootstrap_cpu_seconds": 3, "helper_cpu_seconds": 4,
                "result_reader_cpu_seconds": 3} for phase in phases],
        **{role: {"memory_bytes": memory, "tasks_max": tasks,
                "cpu_quota_per_sec_usec": 1000000, "memory_swap_max": 0}
           for role, memory, tasks in (("controller", 536870912, 64),
                ("ordinary", 268435456, 32),
                ("retained_ordinary", 268435456, 64))},
        "target": {"memory_bytes": 268435456, "tasks_max": 32,
            "cpu_quota_per_sec_usec": 1000000, "runtime_seconds": 85,
            "stop_seconds": 1, "storage_bytes": 1048576, "storage_inodes": 64},
        "supervisor": {"memory_bytes": 67108864, "tasks_max": 32,
            "cpu_quota_per_sec_usec": 1000000, "runtime_seconds": 100,
            "stop_seconds": 1, "storage_bytes": 8388608, "storage_inodes": 64},
        "owner": {"wall_seconds": 120, "cpu_seconds": 120, "memory_bytes": 536870912,
            "tasks_max": 64, "storage_bytes": 8388608, "storage_inodes": 64,
            "output_bytes": 69632},
        "management": {
            "cpu_seconds": 400, "memory_bytes": 1610612736, "pids": 1024,
            "output_bytes": 16777216, "storage_bytes": 33554432,
            "storage_inodes": 1024, "manager_wire_bytes": 4194304,
            "receive_seconds": 1, "stop_seconds": 1,
            "stages": [{"stage": stage, "memory_bytes": 67108864, "tasks_max": 8,
                    "cpu_seconds": 2, "output_bytes": 32768, "runtime_seconds": seconds}
                for stage, seconds in (("collector", 8), ("admission", 7), ("query", 5))],
        },
        "durable": {"state_bytes": 8388608, "state_inodes": 1536,
            "journal_bytes": 1048576, "journal_inodes": 128,
            "capture_declarations_bytes": 20971520,
            "capture_declarations_inodes": 384},
        "roots": {"count": 7, "hard_bytes_each": 1048576,
            "hard_inodes_each": 128},
    }


def _identity(case, *, full=False):
    seed = (SESSION + ":" + case["case_id"]).encode("ascii")
    prefix = SESSION + "-" + case["case_id"]
    result = {
        "id": hashlib.sha256(seed + b":identity").hexdigest()[:32],
        "authority_id": prefix + "-authority",
        "node_id": SESSION + "-guest",
        "install_uuid": "452e2905-1442-4b89-988c-50eefcbd3a09",
        "deployment_epoch": 1, "generation": 1,
        "operation_id": case["operation_id"],
        "profile_ref": prefix + "-profile",
        "principal_id": "q2-synthetic-" + SESSION + "-" + case["case_id"],
        "epoch": hashlib.sha256(seed + b":epoch").hexdigest()[:32],
        "slot_generation": hashlib.sha256(seed + b":slot-generation").hexdigest()[:32],
        "session": hashlib.sha256(seed + b":session").hexdigest(),
        "ledger_id": prefix + "-ledger",
    }
    if full:
        result.update(authority_digest=None, manifest_digest=None, expires_at=None)
    return result


def _planned_directories(case):
    ordinary = {"state", "authority", "profile_work", "profile_evidence",
        "profile_temporary", "store_parent"}
    root_755 = {"control", "session", "declarations"}
    parent_for = {
        "reservation": "state", "state": "state", "authority": "state",
        "journal": "journal", "capture": "evidence", "declarations": "evidence",
        "session": "state", "control": "state", "profile_work": "quota",
        "profile_evidence": "quota", "profile_temporary": "quota", "store_parent": "quota",
    }
    return [{"role": role, "parent_role": parent_for[role],
            "relative_path": SESSION + "/" + case["case_id"] + "/" + role.replace("_", "-"),
            "owner": "ordinary" if role in ordinary else "root",
            "mode": 448 if role in ordinary or role not in root_755 else 493}
        for role in DIRECTORY_ROLES]


def _planned_roots(case):
    base = SESSION + "/" + case["case_id"] + "/"
    paths = _fields('profile-work/work-a profile-evidence/evidence-a profile-temporary/temporary-a profile-work/work-b profile-evidence/evidence-b profile-temporary/temporary-b store-parent/retained_store')
    return [{"ref": ref, "slot": slot, "role": role, "path": base + path,
            "project_id": case["project_ids"][index], "hard_bytes": 1048576,
            "inode_hard_limit": 128}
        for index, ((ref, slot, role), path) in enumerate(zip(ROOT_REFS, paths, strict=True))]


def build_intent(case):
    """Build A's deterministic pre-mutation intent."""
    _check(case in CASES, "CASE")
    identity = _identity(case)
    directories = _planned_directories(case)
    roots = _planned_roots(case)
    budgets = _budget(case["phases"])
    preimage = {
        "schema": "local-hand-q2-core-preparation-input/v1", "session_id": SESSION,
        "index": case["index"], "case_id": case["case_id"],
        "preparation_id": case["preparation_id"], "identity": identity,
        "planned_directories": directories, "planned_roots": roots, "budgets": budgets,
    }
    return {
        "schema": INTENT_SCHEMA, "session_id": SESSION, "index": case["index"],
        "case_id": case["case_id"], "kind": case["kind"],
        "predecessor": case["predecessor"], "preparation_id": case["preparation_id"],
        "identity": identity, "operation_id": case["operation_id"],
        "controller_prefix": case["controller_prefix"],
        "project_ids": list(case["project_ids"]), "directory_roles": list(DIRECTORY_ROLES),
        "planned_directories": directories, "planned_roots": roots,
        "preparation_input_sha256": _sha(canonical(preimage)),
        "phases": list(case["phases"]), "budgets": budgets, "state": "INTENT_RECORDED",
    }


INTENT_FIELDS = _fields('schema session_id index case_id kind predecessor preparation_id identity operation_id controller_prefix project_ids directory_roles planned_directories planned_roots preparation_input_sha256 phases budgets state')
PLAN_FIELDS = _fields('schema session_id index case_id kind predecessor preparation_id identity principal authority_path ledger_path request operation_id roots controllers system_geometry phases empty_ledger_expectation deadlines budgets')


def validate_plan(case, intent, plan, deadlines):
    """Validate all D-owned/static plan bindings before owner or submit."""
    _plan.exact(plan, PLAN_FIELDS, "FIELDS")
    expected = {key: intent[key] for key in
        _fields('session_id index case_id kind predecessor preparation_id operation_id budgets')}
    _plan(plan["schema"] == PLAN_SCHEMA and all(plan[key] == value for key, value in expected.items()),
        "BINDING")
    identity = _plan.exact(plan["identity"], _fields('id authority_id node_id install_uuid deployment_epoch generation operation_id profile_ref principal_id epoch authority_digest manifest_digest slot_generation expires_at session ledger_id'), "IDENTITY_FIELDS")
    logical = intent["identity"]
    _plan(all(identity[key] == value for key, value in logical.items()),
        "IDENTITY")
    _plan.digest(identity["authority_digest"], "AUTHORITY")
    _plan.digest(identity["manifest_digest"], "MANIFEST")
    _plan.integer(identity["expires_at"], 1, code="EXPIRY")
    scopes = ["lh:submit", "lh:read", "lh:evidence"] + (["lh:cancel"] if case["index"] == 2 else [])
    _plan(plan["principal"] == {"principal_id": identity["principal_id"], "scopes": scopes},
        "PRINCIPAL")
    _plan(plan["authority_path"].endswith("/authority/authority.json")
        and plan["ledger_path"].endswith("/state/jobs.sqlite"), "PATH")
    request = _plan.exact(plan["request"], _fields('schema_version operation_id kind profile_ref expected inputs expires_at request_digest'), "REQUEST_FIELDS")
    _plan(request["schema_version"] == "lh-job-v1"
        and request["operation_id"] == case["operation_id"]
        and request["kind"] == "host.inspect"
        and request["profile_ref"] == identity["profile_ref"]
        and request["inputs"] == {}
        and request["expires_at"] == identity["expires_at"], "REQUEST")
    _plan.digest(request["request_digest"], "REQUEST")
    _plan.exact(request["expected"], _fields('node_id install_uuid deployment_epoch profile_digest policy_digest registry_digest'), "EXPECTED")
    for key in ("profile_digest", "policy_digest", "registry_digest"):
        _plan.digest(request["expected"][key], "EXPECTED")
    _plan(request["expected"]["node_id"] == identity["node_id"]
        and request["expected"]["install_uuid"] == identity["install_uuid"]
        and request["expected"]["deployment_epoch"] == 1, "EXPECTED")
    _plan(type(plan["roots"]) is list and len(plan["roots"]) == 7, "ROOTS")
    for wrapper, planned in zip(plan["roots"], intent["planned_roots"], strict=True):
        _plan.exact(wrapper, _fields('ref slot planned observed'), "ROOT_FIELDS")
        _plan(wrapper["ref"] == planned["ref"] and wrapper["slot"] == planned["slot"]
            and wrapper["planned"] == planned, "ROOT")
        observed = _plan.exact(wrapper["observed"], _fields('path role device inode uid gid mode filesystem filesystem_uuid project_id xflags hard_bytes accounting enforcement identity_unchanged hard_inodes'), "OBSERVED_FIELDS")
        _plan(observed["path"] == planned["path"] and observed["role"] == planned["role"]
            and observed["project_id"] == planned["project_id"]
            and observed["hard_bytes"] == planned["hard_bytes"]
            and observed["hard_inodes"] == planned["inode_hard_limit"]
            and observed["mode"] == 16832 and observed["accounting"] is True
            and observed["enforcement"] is True and observed["identity_unchanged"] is True,
            "OBSERVED")
        for key in _fields('device inode uid gid project_id xflags'):
            _plan.integer(observed[key], 1 if key in ("inode", "project_id") else 0,
                code="OBSERVED")
    _plan.exact(plan["controllers"], _fields('target supervisor controller_parent query_parent management_parent supervisor_parent target_storage_bytes target_storage_inodes supervisor_storage_bytes supervisor_storage_inodes'), "CONTROLLERS")
    _plan(plan["controllers"]["target_storage_bytes"] == 1048576
        and plan["controllers"]["target_storage_inodes"] == 64
        and plan["controllers"]["supervisor_storage_bytes"] == 8388608
        and plan["controllers"]["supervisor_storage_inodes"] == 64,
        "CONTROLLER_BUDGET")
    expected_units = _phase_units(case["operation_id"], case["phases"])
    _plan(plan["phases"] == expected_units, "PHASES")
    if case["index"] == 2:
        _plan(plan["system_geometry"] is None, "GEOMETRY")
    else:
        geometry = _plan.exact(plan["system_geometry"], _fields('schema controller_parent ordinary_parent retained_ordinary_parent'), "GEOMETRY")
        _plan(geometry["schema"] == "local-hand-q2-system-geometry/v1",
            "GEOMETRY")
    expectation = _plan.exact(plan["empty_ledger_expectation"], _fields('ledger_path authority_id ledger_id expected_operations expected_events expected_leases expected_sidecars'), "EMPTY")
    _plan(expectation == {"ledger_path": plan["ledger_path"],
            "authority_id": identity["authority_id"],
            "ledger_id": identity["ledger_id"],
            "expected_operations": 0, "expected_events": 0,
            "expected_leases": 0, "expected_sidecars": []},
        "EMPTY")
    _plan(plan["deadlines"] == deadlines, "DEADLINE")
    return plan


_RESIDENT_SOURCES = (
    ("launcher_output/result.json", "launcher-result", 384),
    ("launcher_output/resident.stdout", "stdout", 384),
    ("launcher_output/resident.stderr", "stderr", 384),
    ("launcher_output/capture.json", "wait", 384),
)

_CONTROL_SOURCES = (
    ("supervisor_output/stop.json", "stop", 384),
    ("owner_output/stop.json", "stop", 384),
    ("supervisor_output/seal.json", "control-seal", 384),
    ("owner_output/seal.json", "control-seal", 384),
)

COMMON = (
    ("intent.json", "intent", 384),
    ("reservation/case-plan.json", "plan", 384),
    ("reservation/preparation-plan.json", "preparation-plan", 384),
    ("reservation/preparation-result.json", "preparation-result", 384),
    ("reservation/empty-ledger-gate.json", "empty-ledger-gate", 384),
    ("owner_declarations/fixture-check.json", "fixture-check", 384),
    ("authority/authority.json", "authority", 384),
    ("reservation/case-verdict.json", "verdict", 384),
)


def _h01_special(seal_id):
    _check(type(seal_id) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        seal_id) is not None, "H01_SEAL_ID")
    rows = []
    for phase in ("preflight", "business", "evidence"):
        rows.extend(((phase + "/observer.json", "observer-config", 384),
                ("reservation/phase-" + phase + "-receipt.json", "phase-receipt", 384),
                ("launcher_output/phase-" + phase + ".json", "phase-result", 384)))
    rows.extend((
        ("launcher_output/reservation.json", "launcher-reservation", 384),
        ("launcher_output/gateway.json", "gateway", 384),
        *_RESIDENT_SOURCES,
        ("records/ledger-export.json", "ledger", 384),
        ("business/result-03c94c57c840717302854a3f.json", "result", 384),
        ("business-evidence/" + seal_id + "/evidence.zip", "business-evidence-archive", 384),
        ("business-evidence/" + seal_id + "/manifest.json", "business-evidence-manifest", 384),
        ("business-evidence/" + seal_id + "/seal.json", "business-evidence-seal", 384),
        *_CONTROL_SOURCES,
    ))
    return tuple(rows)


Q4_SPECIAL = (
    ("preflight/observer.json", "observer-config", 384),
    ("reservation/phase-preflight-receipt.json", "phase-receipt", 384),
    ("launcher_output/reservation.json", "launcher-reservation", 384),
    ("launcher_output/phase.json", "phase-result", 384),
    *_RESIDENT_SOURCES,
    ("records/ledger-export.json", "ledger", 384),
    *_CONTROL_SOURCES,
)
H11_SPECIAL = (
    ("preflight/observer.json", "observer-config", 384),
    ("reservation/phase-preflight-receipt.json", "phase-receipt", 384),
    ("launcher_output/reservation.json", "launcher-reservation", 384),
    ("launcher_declarations/recovery-resident.json", "recovery-plan", 420),
    ("launcher_output/recovery.json", "recovery-summary", 384),
    ("launcher_output/origin-resident.stdout", "stdout", 384),
    ("launcher_output/origin-resident.stderr", "stderr", 384),
    ("launcher_output/origin-capture.json", "origin-capture", 384),
    ("launcher_output/gateway.json", "gateway", 384),
    *_RESIDENT_SOURCES,
    ("reservation/h11-recovery-proof.json", "recovery-proof", 384),
    *_CONTROL_SOURCES,
)


def required_paths(case, *, seal_id=None):
    special = _h01_special(seal_id) if case["index"] == 1 else (
        Q4_SPECIAL if case["index"] == 2 else H11_SPECIAL)
    prefix = "cases/" + case["case_id"] + "/"
    return tuple((prefix + path, role, mode) for path, role, mode in COMMON + special)


def phase_source_specs(case, phase):
    prefix = "cases/" + case["case_id"] + "/"
    preparation = (prefix + "reservation/preparation-result.json", "preparation-result")
    observer = (prefix + phase + "/observer.json", "observer-config")
    reservation = (prefix + "launcher_output/reservation.json", "launcher-reservation")
    launcher = (prefix + "launcher_output/result.json", "launcher-result")
    if case["index"] == 1:
        rows = (preparation, observer,
            (prefix + "launcher_output/phase-" + phase + ".json", "phase-result"),
            launcher, reservation)
    elif case["index"] == 2:
        rows = (preparation, observer,
            (prefix + "launcher_output/phase.json", "phase-result"), launcher, reservation)
    else:
        rows = (preparation, observer,
            (prefix + "launcher_declarations/recovery-resident.json", "recovery-plan"),
            (prefix + "launcher_output/recovery.json", "recovery-summary"),
            (prefix + "launcher_output/gateway.json", "gateway"),
            (prefix + "launcher_output/origin-capture.json", "origin-capture"),
            launcher, reservation)
    return tuple(sorted(rows, key=lambda row: (row[1].encode("ascii"), row[0].encode("ascii"))))


SOURCE_FIELDS = _fields('path role mode raw')


def _source(value, *, case_id=None):
    _check.exact(value, SOURCE_FIELDS, "SOURCE_FIELDS")
    _check.path(value["path"], "SOURCE_PATH")
    _check(type(value["role"]) is str and value["role"].isascii()
        and value["mode"] in (384, 420) and type(value["raw"]) is bytes
        and len(value["raw"]) <= MEMBER_LIMIT, "SOURCE")
    if case_id is not None:
        _check(value["path"].startswith("cases/" + case_id + "/"), "SOURCE_CASE")
    return value


def _reference(source, *, sealed=False):
    return {"role": source["role"], "path": source["path"], "bytes": len(source["raw"]),
        "sha256": _sha(source["raw"]), **({"sealed": sealed} if sealed is not None else {})}


def _plain_reference(source):
    return {"path": source["path"], "bytes": len(source["raw"]),
        "sha256": _sha(source["raw"])}


def _member(source, case_id):
    ref = _reference(source, sealed=None)
    return {"path": ref["path"], "case_id": case_id, "role": ref["role"],
        "mode": source["mode"], "bytes": ref["bytes"], "sha256": ref["sha256"]}


def _validate_source_set(case, sources, *, seal_id):
    expected = required_paths(case, seal_id=seal_id)
    _check(len(expected) == (32 if case["index"] == 1 else 21 if case["index"] == 2 else 26),
        "INTERNAL_COUNT")
    actual = []
    seen = set()
    total = 0
    for source in sources:
        _source(source, case_id=case["case_id"])
        key = source["path"]
        _check(key not in seen, "SOURCE_DUPLICATE")
        seen.add(key); total += len(source["raw"])
        actual.append((key, source["role"], source["mode"]))
    _check(set(actual) == set(expected) and len(actual) == len(expected),
        "REQUIRED_SET")
    _check(total <= CASE_BYTES_LIMIT, "CASE_BYTES")
    if case["index"] == 3:
        forbidden = _fields('business/result- business-evidence/ ledger-export /ledger result-receipt ledger-identity result-identity')
        for source in sources:
            suffix = source["path"].split("/", 2)[-1]
            _h11(not any(token in suffix for token in forbidden),
                "FORBIDDEN_SOURCE")
    return sources


def _parse_source(sources, path, *, maximum=MEMBER_LIMIT, newline=True):
    source = next((item for item in sources if item["path"] == path), None)
    _check(source is not None, "SOURCE_MISSING")
    return document(source["raw"], limit=maximum, newline=newline)


def _phase_receipt(case, phase, facts, sources):
    _phase.exact(facts, _fields('quota_request_id quota_request_sha256 query_unit listener_unit admission_unit budget_deadline_ns phase_deadline_ns stage_deadline_ns controller_deadline_ns'),
        "FACT_FIELDS")
    digest = _phase.digest(facts["quota_request_sha256"], "DIGEST")
    _phase(facts["listener_unit"] == "lhqoc-" + digest + ".service"
        and facts["admission_unit"] == "lhqoa-" + digest + ".service"
        and facts["query_unit"] == "lhqo-" + digest + ".service", "UNITS")
    for key in _fields('budget_deadline_ns phase_deadline_ns stage_deadline_ns controller_deadline_ns'):
        _phase.integer(facts[key], 1, code="DEADLINE")
    _phase(facts["stage_deadline_ns"] < facts["phase_deadline_ns"]
        <= facts["budget_deadline_ns"], "DEADLINE")
    expected = phase_source_specs(case, phase)
    refs = []
    for path, role in expected:
        source = next((item for item in sources if item["path"] == path), None)
        _phase(source is not None and source["role"] == role, "SOURCES")
        refs.append(_reference(source, sealed=None))
    refs.sort(key=lambda row: (row["role"].encode("ascii"), row["path"].encode("ascii")))
    return {
        "schema": RECEIPT_SCHEMA, "session_id": SESSION, "index": case["index"],
        "case_id": case["case_id"], "phase": phase,
        **facts, "source_artifacts": refs,
        "source_artifacts_sha256": _sha(canonical(refs)),
    }


H01_OBSERVATIONS = _fields('empty_ledger_gate resident_empty_gate request_accepted grant_issued manager_delivered unit_identities bootstrap_exited helper_started helper_exited result_reader_exited result_verified client_waited stdout_eof stderr_eof future_start_blocked tree_exited writers_stopped collectors_stopped ledger_terminal evidence_sealed')
Q4_OBSERVATIONS = _fields('empty_ledger_gate resident_empty_gate request_accepted helper_running_seen cancel_called cancel_durable cancel_returned no_late_delivery unit_identities stop_ack helper_exited exit_flags_complete client_returned stdout_eof stderr_eof chain_closed ordinary_phase_closed independent_ordinary_cleanup_required full_h07')
H11_OBSERVATIONS = _fields('empty_ledger_gate resident_empty_gate original_request_accepted recovery_plan recovery_summary launcher_result gateway_snapshot origin_capture ledger_identity recovery_proof result_identity future_start_blocked tree_exited writers_stopped collectors_stopped effects_checked outcome leases_retained result_reread start_replayed business_evidence_sealed control_closure_sealed')


def _validate_gate(value, source):
    _check.exact(value, ("path", "bytes", "sha256"), "GATE_REF")
    _check(value == _plain_reference(source), "GATE_REF")


def _validate_resident_gate(value, case):
    _check.exact(value, _fields('passed candidate_commit resident_source_sha256 accepted_operation_id accepted_event_seq'), "RESIDENT_GATE")
    _check(value["passed"] is True and value["candidate_commit"] == CANDIDATE["commit"]
        and value["accepted_operation_id"] == case["operation_id"],
        "RESIDENT_GATE")
    _check.digest(value["resident_source_sha256"], "RESIDENT_GATE")
    _check.integer(value["accepted_event_seq"], 1, code="RESIDENT_GATE")


def _validate_units(value, case):
    phases = case["phases"]
    _check(type(value) is list and value, 'UNIT_IDENTITIES')
    stages = ("bootstrap", "helper") if case["index"] == 2 else ("bootstrap", "helper", "result_reader")
    expected_stages = {(phase, stage) for phase in phases
        for stage in stages}
    actual = set()
    last = None
    for row in value:
        _check.exact(row, _fields('phase stage unit invocation_id'),
            'UNIT_IDENTITY')
        key = (row["phase"], row["stage"])
        _check(key not in actual and key in expected_stages, 'UNIT_IDENTITY')
        actual.add(key)
        expected = next(item for item in _phase_units(case["operation_id"], phases)
            if item["phase"] == row["phase"])
        unit_key = row["stage"] + "_unit" if row["stage"] != "result_reader" else "result_reader_unit"
        _check(row["unit"] == expected[unit_key]
            and re.fullmatch(r"[0-9a-f]{32}", row["invocation_id"] or "") is not None,
            'UNIT_IDENTITY')
        ordering = (row["phase"], row["stage"], row["unit"])
        _check(last is None or last < ordering, 'UNIT_ORDER')
        last = ordering
    _check(actual == expected_stages, 'UNIT_IDENTITIES')


def _validate_stop(stop, owner_deadline):
    _check.exact(stop, _fields('requested acknowledged tree_exited writers_stopped deadline_ns'),
        "STOP_FIELDS")
    _check(stop == {"requested": True, "acknowledged": True, "tree_exited": True,
            "writers_stopped": True, "deadline_ns": owner_deadline}, "STOP")


def _validate_verdict(case, observations, stop, sources, proof, owner_deadline):
    expected_fields = H01_OBSERVATIONS if case["index"] == 1 else (
        Q4_OBSERVATIONS if case["index"] == 2 else H11_OBSERVATIONS)
    _check.exact(observations, expected_fields, "OBSERVATION_FIELDS")
    gate_path = "cases/" + case["case_id"] + "/reservation/empty-ledger-gate.json"
    gate_source = next(item for item in sources if item["path"] == gate_path)
    _validate_gate(observations["empty_ledger_gate"], gate_source)
    _validate_resident_gate(observations["resident_empty_gate"], case)
    if case["index"] != 3:
        _validate_units(observations.get("unit_identities"), case)
    _validate_stop(stop, owner_deadline)
    if case["index"] == 1:
        for key in expected_fields:
            if key not in ("empty_ledger_gate", "resident_empty_gate", "unit_identities"):
                _check(observations[key] is True, "H01_TRUTH")
    elif case["index"] == 2:
        false = {"chain_closed", "ordinary_phase_closed", "full_h07"}
        for key in expected_fields:
            if key in ("empty_ledger_gate", "resident_empty_gate", "unit_identities"):
                continue
            _check(observations[key] is (False if key in false else True),
                "Q4_TRUTH")
    else:
        _validate_h11_proof(proof, case, sources, owner_deadline)
        for key in _fields('recovery_plan recovery_summary launcher_result gateway_snapshot origin_capture ledger_identity result_identity'):
            _h11(observations[key] == proof[key], "PROJECTION")
        proof_source = next(item for item in sources if item["role"] == "recovery-proof")
        _h11(observations["recovery_proof"] == _plain_reference(proof_source), "PROJECTION")
        _h11(observations["outcome"] == "UNKNOWN", "TRUTH")
        false = {"collectors_stopped", "effects_checked", "result_reread", "start_replayed",
            "business_evidence_sealed"}
        objects = {"empty_ledger_gate", "resident_empty_gate", "unit_identities", "recovery_plan",
            "recovery_summary", "launcher_result", "gateway_snapshot", "origin_capture",
            "ledger_identity", "recovery_proof", "result_identity", "outcome"}
        for key in expected_fields:
            if key not in objects:
                _h11(observations[key] is (False if key in false else True), "TRUTH")
    artifacts = [_reference(source, sealed=True) for source in sources
        if source["role"] != "verdict"]
    artifacts.sort(key=lambda row: row["path"].encode("ascii"))
    return {"schema": VERDICT_SCHEMA, "session_id": SESSION, "index": case["index"],
        "case_id": case["case_id"], "status": "PASS", "semantic_pass": True,
        "observations": observations, "artifacts": artifacts, "missing": [], "stop": stop}


def _validate_h11_proof(proof, case, sources, owner_deadline):
    _h11.exact(proof, _fields('schema session_id index case_id candidate ledger_identity recovery_plan recovery_summary launcher_result gateway_snapshot origin_capture control_seal result_identity assertions'), "PROOF_FIELDS")
    _h11(proof["schema"] == PROOF_SCHEMA and proof["session_id"] == SESSION
        and proof["index"] == 3 and proof["case_id"] == case["case_id"], "PROOF_BINDING")
    candidate = _h11.exact(proof["candidate"], _fields('commit tree h11_source_path h11_source_sha256 resident_source_path resident_source_sha256 launcher_source_path launcher_source_sha256'), "CANDIDATE")
    _h11(candidate["commit"] == CANDIDATE["commit"] and candidate["tree"] == CANDIDATE["tree"],
        "CANDIDATE")
    for key in ("h11_source_sha256", "resident_source_sha256", "launcher_source_sha256"):
        _h11.digest(candidate[key], "CANDIDATE")
    ledger = _h11.exact(proof["ledger_identity"], _fields('path dev ino unchanged'), "LEDGER")
    _h11(ledger["path"].endswith("/state/jobs.sqlite") and ledger["unchanged"] is True, "LEDGER")
    _h11.integer(ledger["dev"], 0, code="LEDGER")
    _h11.integer(ledger["ino"], 1, code="LEDGER")
    result = _h11.exact(proof["result_identity"], _fields('expected_path expected_basename stat_performed opened hashed'), "RESULT_IDENTITY")
    _h11(result["expected_basename"] == "result-f7b176ecb6b8081fac3a7a47.json"
        and result["expected_path"].endswith("/" + result["expected_basename"])
        and result["stat_performed"] is False and result["opened"] is False
        and result["hashed"] is False, "RESULT_IDENTITY")
    refs = {
        "recovery_plan": ("launcher_declarations/recovery-resident.json", "recovery-plan"),
        "recovery_summary": ("launcher_output/recovery.json", "recovery-summary"),
        "launcher_result": ("launcher_output/result.json", "launcher-result"),
        "gateway_snapshot": ("launcher_output/gateway.json", "gateway"),
        "origin_capture": ("launcher_output/origin-capture.json", "origin-capture"),
        "control_seal": ("owner_output/seal.json", "control-seal"),
    }
    prefix = "cases/" + case["case_id"] + "/"
    for key, (suffix, role) in refs.items():
        source = next((item for item in sources if item["path"] == prefix + suffix), None)
        _h11(source is not None and source["role"] == role, "REFERENCE")
        fields = _fields('path bytes sha256 embedded_plan_sha256') if key == "recovery_plan" \
            else ("path", "bytes", "sha256")
        _h11.exact(proof[key], fields, "REFERENCE")
        basic = _plain_reference(source)
        _h11(all(proof[key][name] == value for name, value in basic.items()), "REFERENCE")
        if key == "recovery_plan":
            _h11.digest(proof[key]["embedded_plan_sha256"], "REFERENCE")
    assertions = _h11.exact(proof["assertions"], _fields('same_operation same_request_digest original_handle_admitted same_original_stage_units same_grant_and_deadlines leases_retained delivery_intents_unchanged recovery_launch_forbidden gateway_parts_unchanged recovery_barrier_count quota_exit_pending_count start_replayed result_reread deadline_extended future_start_blocked tree_exited writers_stopped collectors_stopped effects_checked outcome business_evidence_sealed'), "ASSERTIONS")
    for key in _fields('same_operation same_request_digest original_handle_admitted same_original_stage_units same_grant_and_deadlines leases_retained delivery_intents_unchanged recovery_launch_forbidden gateway_parts_unchanged future_start_blocked tree_exited writers_stopped'):
        _h11(assertions[key] is True, "ASSERTIONS")
    for key in _fields('start_replayed result_reread deadline_extended collectors_stopped effects_checked business_evidence_sealed'):
        _h11(assertions[key] is False, "ASSERTIONS")
    _h11(assertions["recovery_barrier_count"] == assertions["quota_exit_pending_count"] == 1
        and assertions["outcome"] == "UNKNOWN", "ASSERTIONS")
    reservation = _parse_source(sources, prefix + "launcher_output/reservation.json")
    _h11(type(reservation.get("controller")) is dict
        and reservation["controller"].get("deadline_ns") == owner_deadline, "DEADLINE")
    return proof


# Self-contained source-less approved-input parser for amendment A §3.
# Fixed public source descriptors are ordinary Python literals. No module from
# the host, package candidate or retained evidence is imported or executed.
# Private raw verification remains the host builder's duty before issuance.
APPROVED_FIXED_PINS = {'horizon': (7402, '7e149980e1fbb5f4494dcba06a11e0da451268a19d0cc30354ed375db2750b9d'), 'later': (795, 'c4ca5a1a83cb0247975c2178f2b8c43831503c771e714ac04147201ca7758481'), 'legacy': (885, '1e022bb0e7f3fb7ed09f5dd00ed61debda9992c7aa17324b8d36bb5cd2aaa585'), 'locator': (2893, '7d8364c8a417ee4879d4598e2ae6a9bb8cc14d14b79dc90d906bbad406bd5531'), 'placement': (790, '3bfbf6dd7417a1605286d3295b42df9b4e9b07202252b30eb46ed51a30f5c7a4'), 'producer': (1778, '851583a3a5268cb43fcd50990b2ef297f45fa7fe6e3ad679e9ea5af8ed978ab1'), 'quota': (847, '53fefd38c4b1795feb316ef9cc22d0d1aca99f1787af521b11af77d8e1ef82c6')}
APPROVED_LEGACY_FIELDS = _fields('archive chain inventory manifest producer_blobs')

APPROVED_ADOPTED_RAW = (('second-bootstrap-intent', 556, '58992ee2ff0d66fec5e10c7e138e8de4529089ca35d76f71200db1a05ac160b6'),
 ('second-bootstrap-attestation', 7766, 'cfc6c07265b4edc6d0b26e67a6ca9cfc19c652b4d011a2386b9bd95e945a34cb'))

APPROVED_RETAINED_PINS = {'domains': (267, '45c231e6f4dd1360888b9e4e3f790ce175440b8af89231801feeede2b21a2c4c'),
 'object': (1484, '24772cefec5e2c51364a1f4d1dadf692a2a666999077772138201004f811a808'),
 'paths': (1196, '1ea38f024d0ed06ec5d801ac9fc1b99f4938366d3cc979d8f5ba3b9eddd013c6')}

APPROVED_RECONCILIATION = {'applied': [],
 'record_basenames': ['evidence-adoption.json',
        'reconciliation-intent.json',
        'live-attestation.json',
        'reconciliation-record.json',
        'reconciliation-seal.json'],
 'released_bytes': 0,
 'released_inodes': 0,
 'state': 'NO_ELIGIBLE_RETAINED_SEALED_RECORD_SOURCE'}

APPROVED_VECTOR_PINS = {'delta': (6678, 'b8af1d3264b77b9142a48288482c26d2eafa894523f85baa0fc71d595da90352'),
 'effective': (18110, '7c2786f240144e7a2de90bc9a70561089a7334559bd8e962371132cf1db806e9'),
 'placement_normalized': (4549, 'b6153d8c45e5b009bcc1f878406565e08bcf7c7d07c17f18361b562bf1096703'),
 'placement_source': (4327, 'edcb0bb95508c15e5b3fb60d679c46c93961e95d8e802a338fc1f4397c18ee0d'),
 'quota': (2997, '95b59d878d643bfbce2eef6ce88145bf1086058694dee127b3de49d13319bde0'),
 'row_relation': (462, '89dea12770f6c6ab19b901adcf4c4d42e6b8b42300c1ca470b1ec7ac03ec47e6'),
 'snapshot': (11433, '82bdb7a94c85a7450a45d9ee7dff2baa4e5fef7b8a7a7d8f7787a0cb7bea358e')}

APPROVED_PREFIX_SHA256 = '09f107f265986afd0dcc0535de84d2df37ac47ddeff78d20569c2bb8a5513e88'

APPROVED_TAIL_SHA256 = '60885e762f1dfe007f43b6ae1e056dabdce9b1e142688741d333f806f6952a68'

APPROVED_TOTALS = {'configured_quota_bytes': 249561088,
 'configured_quota_inodes': 17792,
 'delta_bytes': 138412032,
 'delta_inodes': 8064,
 'effective_bytes': 765202432,
 'effective_inodes': 40177,
 'snapshot_bytes': 626790400,
 'snapshot_inodes': 32113}

APPROVED_POLICY_SOURCE_PINS = {'fixture_cloud_config': '5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523',
 'identity_public': 'e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c',
 'known_hosts': 'd1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd'}

def _approved_require(ok, code):
    _require(ok, "CORE_DISPATCH_APPROVED_" + code)


def _approved_exact(value, fields):
    return _approved.exact(value, fields, "FIELDS")


def _approved_absolute(value):
    return _approved.absolute(value, "PATH")


def _approved_hash(value):
    return _sha(canonical(value))


def _approved_equal(value, expected, code):
    _approved_require(canonical(value) == canonical(expected), code)


def _approved_vector(value, pin, code):
    raw = canonical(value)
    _approved_require((len(raw), _sha(raw)) == pin, code)


def _approved_union(relation):
    obligations = relation["obligations"]
    return dict(schema="local-hand-q2-core-source-union/v1", locator=relation["locator"],
        **{key: obligations[key] for key in _fields('legacy_20260927 horizon_20261001e producer configured_quota_liability placement')},
        later_nonissuance=relation["later_nonissuance"])


def _approved_adoption(value):
    _approved_exact(value, {"current_owner_supplied_raw", "forward_baseline_entries", "disclosed_atime_changes",
            "run_permission_adopted", "released_bytes", "released_inodes"})
    _approved_require(value["run_permission_adopted"] is False and type(value["released_bytes"]) is int
        and type(value["released_inodes"]) is int and value["released_bytes"] == value["released_inodes"] == 0,
        "LEGACY_PERMISSION")
    rows = value["current_owner_supplied_raw"]
    _approved_require(type(rows) is list and len(rows) == 2, "LEGACY_ADOPTION_COUNT")
    for row, (identifier, size, digest) in zip(rows, APPROVED_ADOPTED_RAW, strict=True):
        _approved_absolute(row.get("path"))
        _approved_equal(row, dict(id=identifier, path=row["path"], bytes=size, sha256=digest,
                source_class="CURRENT_OWNER_SUPPLIED_RAW", proof_id="owner-adoption"), "LEGACY_ADOPTION")
    _approved_require(rows[0]["path"].endswith(".intent.json")
        and rows[1]["path"] == rows[0]["path"][:-len(".intent.json")] + "/bootstrap-attestation.json",
        "LEGACY_ADOPTION_PATH_RELATION")
    forward = value["forward_baseline_entries"]
    _approved_require(type(forward) is list and len(forward) == 610, "LEGACY_FORWARD_COUNT")
    seen, by_path = set(), {}
    for row in forward:
        _approved_require(type(row) is dict and set(row) in ({"source_metadata", "sha256"},
                {"source_metadata", "sha256", "link_target"}), "LEGACY_FORWARD_FIELDS")
        meta = row["source_metadata"]
        fields = {"device", "inode", "st_mode", "uid", "gid", "nlink", "size", "blocks",
            "atime_ns", "mtime_ns", "ctime_ns", "path", "type"}
        _approved_exact(meta, fields)
        _approved_absolute(meta["path"])
        for key in fields - {"path", "type"}:
            _integer(meta[key], 1 if key in ("device", "inode", "nlink") else 0)
        identity = meta["device"], meta["inode"]
        _approved_require(identity not in seen and meta["path"] not in by_path, "LEGACY_FORWARD_ALIAS")
        seen.add(identity); by_path[meta["path"]] = row
        _approved_require(meta["type"] in ("regular", "directory", "symlink"), "LEGACY_FORWARD_TYPE")
        _approved_require(stat.S_IFMT(meta["st_mode"]) == {
            "regular": stat.S_IFREG, "directory": stat.S_IFDIR, "symlink": stat.S_IFLNK}[meta["type"]],
            "LEGACY_FORWARD_MODE")
        if meta["type"] == "regular":
            _digest(row["sha256"])
            _approved_require(meta["nlink"] == 1 and "link_target" not in row, "LEGACY_FORWARD_REGULAR")
        elif meta["type"] == "directory":
            _approved_require(row["sha256"] is None and "link_target" not in row, "LEGACY_FORWARD_DIRECTORY")
        else:
            _approved_require(row["sha256"] is None and type(row.get("link_target")) is str, "LEGACY_FORWARD_SYMLINK")
    _approved_require(list(by_path) == sorted(by_path), "LEGACY_FORWARD_ORDER")
    parent = rows[0]["path"][:-len(".intent.json")]
    _approved_require(parent in by_path and by_path[parent]["source_metadata"]["type"] == "directory"
        and all(path == rows[0]["path"] or path == parent or path.startswith(parent + "/")
            for path in by_path), "LEGACY_FORWARD_ROOT")
    for row in rows:
        _approved_require(row["path"] in by_path and by_path[row["path"]]["sha256"] == row["sha256"]
            and by_path[row["path"]]["source_metadata"]["size"] == row["bytes"], "LEGACY_FORWARD_ADOPTED")
    changed = value["disclosed_atime_changes"]
    _approved_require(type(changed) is dict and len(changed) == 5, "LEGACY_ATIME_COUNT")
    for path, row in changed.items():
        _approved_absolute(path)
        _approved_exact(row, {"source_class", "sha256", "source_metadata", "historical_atime_preservation_proven"})
        _approved_require(row["source_class"] == "POST_READ_METADATA_BASELINE"
            and row["historical_atime_preservation_proven"] is False, "LEGACY_ATIME_CLASS")
        _digest(row["sha256"])
        _approved_exact(row["source_metadata"], fields - {"path", "type"})
        for field, number in row["source_metadata"].items():
            _integer(number, 1 if field in ("device", "inode", "nlink") else 0)
        if path in by_path:
            _approved_equal(row["source_metadata"], {key: item for key, item in by_path[path]["source_metadata"].items()
                    if key not in ("path", "type")}, "LEGACY_ATIME_METADATA")
            _approved_require(row["sha256"] == by_path[path]["sha256"], "LEGACY_ATIME_DIGEST")


def _approved_validate_relations(value):
    relation = value["source_relation"]
    _approved_exact(relation, {"schema", "locator", "obligations", "later_nonissuance", "zero_mismatch"})
    _approved_require(relation["schema"] == "local-hand-q2-core-approved-source-relation/v1"
        and relation["zero_mismatch"] is True, "SOURCE_RELATION")
    _approved_vector(relation["locator"], APPROVED_FIXED_PINS['locator'], "LOCATOR_RELATION")
    _approved_vector(relation["later_nonissuance"], APPROVED_FIXED_PINS['later'], "LATER_RELATION")
    obligations = relation["obligations"]
    fields = {"schema", "legacy_20260927", "horizon_20261001e", "producer", "configured_quota_liability",
        "placement", "row_relation", "source_horizon", "snapshot_rows_sha256", "delta_rows_sha256",
        "effective_rows_sha256", "source_union_sha256", "run_permission_adopted", "zero_mismatch"}
    _approved_exact(obligations, fields)
    _approved_require(obligations["schema"] == "local-hand-q2-core-approved-obligation-sources/v1"
        and obligations["source_horizon"] == "20261001e" and obligations["zero_mismatch"] is True
        and obligations["run_permission_adopted"] is False, "OBLIGATION_RELATION")
    old = obligations["legacy_20260927"]
    _approved_exact(old, {*APPROVED_LEGACY_FIELDS, "adoption"})
    _approved_vector({key: item for key, item in old.items() if key != "adoption"}, APPROVED_FIXED_PINS['legacy'], "LEGACY_FIXED")
    _approved_adoption(old["adoption"])
    for key, expected in (("horizon_20261001e", APPROVED_FIXED_PINS['horizon']), ("producer", APPROVED_FIXED_PINS['producer']),
        ("configured_quota_liability", APPROVED_FIXED_PINS['quota']), ("placement", APPROVED_FIXED_PINS['placement'])):
        _approved_vector(obligations[key], expected, "RELATION_" + key.upper())
    _approved_vector(obligations["row_relation"], APPROVED_VECTOR_PINS["row_relation"], "ROW_RELATION")
    for field, name in (("snapshot_rows_sha256", "snapshot"), ("delta_rows_sha256", "delta"),
        ("effective_rows_sha256", "effective")):
        _approved_require(obligations[field] == APPROVED_VECTOR_PINS[name][1], "ROW_DIGEST")
    _approved_require(obligations["source_union_sha256"] == _approved_hash(_approved_union(relation)), "SOURCE_UNION")
    return obligations


def _approved_validate_capacity(value, obligations):
    _approved_exact(value, {"schema", "source_horizon", "source_union_sha256", "snapshot_rows", "delta_rows",
            "effective_rows", "row_relation", "placement", "configured_quota_rows", "totals",
            "released_or_refunded", "prior_commitments", "maintenance"})
    _approved_require(value["schema"] == "local-hand-q2-core-historical-capacity-obligations/v17"
        and value["source_horizon"] == "20261001e" and value["released_or_refunded"] is False,
        "CAPACITY_SCHEMA")
    _approved_equal(value["maintenance"],_maintenance_commitments(),"MAINTENANCE_COMMITMENTS")
    for key in ("source_union_sha256", "row_relation", "placement"):
        _approved_equal(value[key], obligations[key], "CAPACITY_RELATION")
    for key, name in (("snapshot_rows", "snapshot"), ("delta_rows", "delta"),
        ("effective_rows", "effective"), ("configured_quota_rows", "quota")):
        _approved_vector(value[key], APPROVED_VECTOR_PINS[name], "CAPACITY_" + name.upper())
    _approved_equal(value["effective_rows"], value["snapshot_rows"] + value["delta_rows"], "CAPACITY_CONSTRUCTION")
    _approved_require(_approved_hash(value["snapshot_rows"][:7]) == APPROVED_PREFIX_SHA256
        and _approved_hash(value["snapshot_rows"][7:]) == APPROVED_TAIL_SHA256, "CAPACITY_PREFIX")
    _approved_equal(value["totals"], APPROVED_TOTALS, "CAPACITY_TOTALS")
    for key, count in (("snapshot_rows", 24), ("delta_rows", 12), ("effective_rows", 36)):
        rows = value[key]
        _approved_require(type(rows) is list and len(rows) == count, "CAPACITY_COUNT")
        prefix = key.removesuffix("_rows")
        for field in ("bytes", "inodes"):
            _approved_require(sum(_integer(row["commitment"][field]) for row in rows)
                == value["totals"][prefix + "_" + field], "CAPACITY_SUM")
    _approved_require([row["project_id"] for row in value["configured_quota_rows"]]
        == obligations["configured_quota_liability"]["project_ids"], "CAPACITY_PROJECTS")


def _approved_validate_retained(value):
    _approved_exact(value, {"paths", "domains"})
    for key in ("paths", "domains"):
        _approved_vector(value[key], APPROVED_RETAINED_PINS[key], "RETAINED_" + key.upper())
    _approved_vector(value, APPROVED_RETAINED_PINS["object"], "RETAINED_OBJECT")
    _approved_require(len(value["paths"]) == 16 and len(value["domains"]) == 4, "RETAINED_COUNT")
    for row in value["paths"]:
        _approved_exact(row, {"path", "device", "inode"})
        _approved_absolute(row["path"]); _integer(row["device"], 1); _integer(row["inode"], 1)
    for row in value["domains"]:
        _approved_exact(row, {"project_id", "hard_bytes", "inode_hard_limit"})
        for number in row.values():
            _integer(number, 1)


def _approved_validate_policy(value):
    _approved_exact(value, {"schema", "fixture_cloud_config", "identity_public", "known_hosts",
            "remote_expectation", "policies", "policy_predicates_sha256"})
    _approved_require(value["schema"] == "local-hand-q2-core-policy-basis/v1", "POLICY_SCHEMA")
    for name, digest in APPROVED_POLICY_SOURCE_PINS.items():
        _approved_equal(value[name], dict(binding_pointer="/" + name, sha256=digest), "POLICY_SOURCE")
    expected = copy.deepcopy(value["remote_expectation"])
    _approved_require(type(expected) is dict, "POLICY_EXPECTATION")
    for key in ("remote_tokens_sha256", "remote_command_sha256"):
        _digest(expected.get(key))
        expected[key] = ""
    # These template pins cover every fixed key and scalar in A §3.2. Only the
    # two D-dependent command digests and source-derived key are normalized.
    # The parser does not call the policy builder, so rehashing a weakened
    # predicate cannot turn it into a valid predicate.
    _approved_vector(expected, (410, "307997766eca2a5bef0411b6a41e72c1e904fa74831a03659e26a61b5c1d80cd"),
        "POLICY_EXPECTATION_TEMPLATE")
    policies = value["policies"]
    _approved_exact(policies, {"sudo", "sshd", "authorized_keys", "rc"})
    _approved_require(value["policy_predicates_sha256"] == _approved_hash(policies), "POLICY_DIGEST")
    normalized = copy.deepcopy(policies)
    for name, item in policies.items():
        _approved_exact(item, {"schema", "mode", "sources", "paths", "argv", "environment", "execution",
                "predicate", "limits", "predicate_sha256"})
        _approved_require(item["predicate_sha256"] == _approved_hash(item["predicate"]), "POLICY_PREDICATE_DIGEST")
        normalized[name]["predicate_sha256"] = ""
    try:
        key = policies["authorized_keys"]["predicate"]["parameters"]["approved_key"]
        _approved_exact(key, {"type", "key_base64", "source_sha256"})
        _approved_require(type(key["key_base64"]) is str and key["key_base64"].isascii(), "POLICY_KEY")
        _approved_equal(key, _approved_key(("ssh-ed25519 " + key["key_base64"] + "\n").encode("ascii")), "POLICY_KEY")
        target = normalized["authorized_keys"]["predicate"]["parameters"]["approved_key"]
        target["key_base64"] = target["source_sha256"] = ""
    except (KeyError, TypeError) as error:
        raise _approved.error("POLICY_KEY") from error
    _approved_vector(normalized, (6574, "b70e64bb418db787b2e7756f70d5e605329a00008a970aaf9939a32104e8506a"),
        "POLICY_PREDICATE_TEMPLATE")


def _approved_key(raw):
    try:
        lines = [line.strip() for line in raw.decode("ascii").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]
        _approved_require(len(lines) == 1, "KEY_COUNT")
        fields = lines[0].split()
        _approved_require(len(fields) >= 2 and fields[0] == "ssh-ed25519", "KEY_TYPE")
        decoded = base64.b64decode(fields[1], validate=True)
        _approved_require(base64.b64encode(decoded).decode("ascii") == fields[1]
            and decoded == struct.pack(">I", 11) + b"ssh-ed25519"
            + struct.pack(">I", 32) + decoded[-32:] and len(decoded) == 51, "KEY_ENCODING")
    except (UnicodeError, ValueError, IndexError) as error:
        raise _approved.error("POLICY_KEY") from error
    return dict(type="ssh-ed25519", key_base64=fields[1], source_sha256=APPROVED_POLICY_SOURCE_PINS["identity_public"])


PRIOR_SESSION = 'lhqcore-20261003a'
PRIOR_UNIT = 'lhqcore20261003a-carrier.service'
PRIOR_IMPLEMENTATION = dict(commit='605a2a38d1db5ef85c961b4d357cafa157bdd7d5',
    tree='ced38519fe6e3b86973de5ccf0dff60fc62322e4')
PRIOR_PACKAGE_SHA = 'a8ca34f3fba3fd370485b522f3c009fa41de70fab1441224b56232885b77380e'
PRIOR_MANIFEST_SHA = '9c05d55ed52dc1e0c04ad340549de6e584a4296b392d84abd07428f179a1989f'
PRIOR_TOTAL_BYTES = 9318
PRIOR_PINS = {
    'carrier-consumed.json': (3577, '5d85f8d5c51329bf46eba91d0106a41d449389e16b018bbb30ddbc667e69d502'),
    'stdout': (2852, 'bd042a224271b03eadaddb99868e3f0c4cef4f71365482f112577005d8be5e1d'),
    'stderr': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'capture-manifest.json': (1637, '5ab260b4062404991151dd917fd636d4f1cd4ba5dd0ffa45a1578f5cf6bb3db3'),
    'acceptance-receipt.json': (1252, 'dd1d4f5c607572fa9eb1527ddb94e2eb839f5ae5e59509042b6d03313cf74700'),
}
SECOND_PRIOR_PINS = {
    'carrier-consumed.json': (3577, '126a3fc0c40085c360e6392d06ec286e42f05edc93823fd01f36c0869103d2a6'),
    'stdout': (2852, '3cf4a279a36daeb3348d52544c92bdfeba3f295e0650f2bf49bd204d3e0bd3b9'),
    'stderr': (23, 'ef5aad9b8e8b977441ad9ab1e58cd1dc8ad994798f5802d2f6768c241afb8ece'),
    'capture-manifest.json': (None, '081019f289a561839ddf13da0c5bf55150879e998a6b52241864f3813b132d1b'),
    'acceptance-receipt.json': (None, '541198e61811e4b6f2df3d17eb4ade8f91ef567ae4c00e89e7023f5709040f35'),
}
SECOND_PRIOR_TOTAL_BYTES = 9072
THIRD_PRIOR_PINS = {
    'carrier-consumed.json': (3577, '3d38e232e66580d588f03cfd444e5d1729904af801dfeb83af51f87e721d6c20'),
    'stdout': (2852, 'cde70ed0b21d2b6cc7c5d9a21652c68f7e0f3b171e7ee03627eb594b56204f3f'),
    'stderr': (24, '7c8bda65cecc5daeba8693865946e37aed794bdb930f1f71e0fe0ddb9c8684de'),
    'capture-manifest.json': (1503, 'fd9e85a9b368cfaf58c3138b9860f3d4ba3c4370fa2319e8c992f04d64f23918'),
    'acceptance-receipt.json': (1117, '1274a7522d4f7151f894fbf530618cba12ba8134b1dd162731cb32c72f43929b'),
}
THIRD_PRIOR_TOTAL_BYTES = 9073
PRIOR_ROLE_LIMITS = dict(zip(('carrier-consumed.json', 'stdout', 'stderr',
    'capture-manifest.json', 'acceptance-receipt.json'), (16384, 4112, 4194304, 262144, 65536)))


FOURTH_PRIOR_TOTAL_BYTES = 9071
FOURTH_PRIOR_PINS = {'carrier-consumed.json': (3577, 'ac0314d584ce7dfdbe5892f779cfbc01a702459fb31ab539b2752f70c07f7deb'), 'stdout': (2852, 'ff0f1b11037028b766c6bf8d4b6623f84241541f9e9240bf1f90efe3c9d6f7e9'), 'stderr': (22, 'e1c59576e732df777e6542b880a21994430f06f72ca54d9a0319507d1126aa75'), 'capture-manifest.json': (1503, '44398704da222ff3d5200b53dfbc732c1ad23fa4b35bd4d75e4671c5b8d5b406'), 'acceptance-receipt.json': (1117, '184439515c226a8b108b270522800174a7adb476191a606a66b7d451c25e601c')}


def _prior_profile(index):
    _require(type(index) is int and index in (0, 1, 2, 3), 'CORE_PRIOR_PROFILE')
    if index == 0:
        return dict(session=PRIOR_SESSION, unit=PRIOR_UNIT, implementation=PRIOR_IMPLEMENTATION,
            pins=PRIOR_PINS, total=PRIOR_TOTAL_BYTES, package_sha=PRIOR_PACKAGE_SHA,
            manifest_sha=PRIOR_MANIFEST_SHA, package_bytes=18111397, sent=False, status=255,
            bootstrap_sha='039fe87cc91a64c0327dc404e0ccf9728c32a1cc07e3e6fb11ed74c979f904f3')
    if index == 3:
        return dict(session='lhqcore-20261005c', unit='lhqcore20261005c-carrier.service',
            implementation=dict(commit='657b1bcd749cb4281b0193b2bc9430b0662faf98',
                tree='4bb00b2e9ccbec3c43160159811e51eec76702cd'), pins=FOURTH_PRIOR_PINS,
            total=FOURTH_PRIOR_TOTAL_BYTES, package_bytes=18193664, sent=True, status=3,
            package_sha='0acdfcaad942191b85f9bf24832c08d2c344fee3fe392a41d376a84ec2271184',
            manifest_sha='28cc514a5c622720744dc7633520c2ee326b7a5681276bfbaebb975f882264db',
            bootstrap_sha='7e2d08800951528c81f9078eb772cc4937dc76a3fd1ed7a1ccadde2a12a23cf5')
    if index == 2:
        return dict(session='lhqcore-20261005b', unit='lhqcore20261005b-carrier.service',
            implementation=dict(commit='8704a24b6c3c79ce4a36028ae2182dec2a35843e',
                tree='89a5f221883c11838a10a452be2dcb756abb5a17'), pins=THIRD_PRIOR_PINS,
            total=THIRD_PRIOR_TOTAL_BYTES, package_bytes=18173610, sent=True, status=3,
            package_sha='dc30af5fed782615501df61c601461ca3d214d379e8805d86e4f0dc458b6a498',
            manifest_sha='bb7c854f7279a352064de3f9bb260f92d7a0c8456a636cda747b363ac9481d2a',
            bootstrap_sha='4a58b342ea4fabb95903e9362cc9b0007c6aafda5a5ece3203692c5033982ce3')
    return dict(session='lhqcore-20261005a', unit='lhqcore20261005a-carrier.service',
        implementation=dict(commit='59d7c32bbe10d580603b8e5e62dd49ad6a538e56',
            tree='15bfe2192ced5aad0acf5c74a58b6e865afe34d1'), pins=SECOND_PRIOR_PINS,
        total=SECOND_PRIOR_TOTAL_BYTES, package_bytes=18149835, sent=True, status=3,
        package_sha='da72c862bbcbe4ae43df681f91576d38586eec1eeb550b46e378d3398e07008b',
        manifest_sha='09e7b8ef0df3b3103f0ba87113dfcf2d3470b861ad14f84c83c144a0f6b3c6fb',
        bootstrap_sha='c9f6e89f874d83856552e65810b04a5d88e7ab0687395dfa5dfd80d7affdee83')


def _prior_attempt(prior, index=0):
    """Standalone guest consumer; no imported host builder or private paths."""
    check = _Checks('CORE_PRIOR_')
    fixed = _prior_profile(index)
    check.exact(prior, _fields('schema scope session_id implementation package_sha256 manifest_sha256 files'), 'FIELDS')
    check(prior['schema'] == 'local-hand-q2-core-prior-attempt/v2' and prior['scope'] == SCOPE
        and prior['session_id'] == fixed['session'] and prior['implementation'] == fixed['implementation']
        and prior['package_sha256'] == fixed['package_sha'] and prior['manifest_sha256'] == fixed['manifest_sha'], 'IDENTITY')
    prefix = '.' + fixed['session'] + '.'
    rows = prior['files']; raw = {}
    check(type(rows) is list and len(rows) == 5 and [row.get('basename') for row in rows]
        == sorted(prefix + suffix for suffix in fixed['pins']), 'FILES')
    for row in rows:
        check.exact(row, _fields('basename bytes sha256 raw_base64'), 'FILE_FIELDS')
        suffix = row['basename'][len(prefix):]; size, digest = fixed['pins'][suffix]
        check(type(row['bytes']) is int and (size is None or row['bytes'] == size)
            and 0 <= row['bytes'] <= PRIOR_ROLE_LIMITS[suffix] and row['sha256'] == digest
            and type(row['raw_base64']) is str and len(row['raw_base64']) <= 22000, 'PIN')
        try:
            data = base64.b64decode(row['raw_base64'], validate=True)
        except (ValueError, UnicodeError) as error:
            raise check.error('BASE64') from error
        check(len(data) == row['bytes'] and _sha(data) == digest
            and base64.b64encode(data).decode('ascii') == row['raw_base64'], 'RAW')
        raw[suffix] = data
    check(sum(map(len, raw.values())) == fixed['total'], 'TOTAL')
    marker = document(raw['carrier-consumed.json'], limit=16384)
    cap = document(raw['capture-manifest.json'], limit=262144)
    receipt = document(raw['acceptance-receipt.json'], limit=65536)
    check.exact(marker, _fields('schema scope session_id baseline owner_decision closure implementation amendment candidate package approved_inputs_sha256 local_management_binding_sha256 writer carrier_argv_sha256 host_boottime_origin_ns host_monotonic_origin_ns host_boottime_deadline_ns host_monotonic_deadline_ns state'), 'MARKER_FIELDS')
    check.exact(cap, _fields('schema session_id consumption_sha256 stdout stderr output_package wait files logical_bytes allocated_bytes inodes fsync_complete reread_equal missing'), 'CAPTURE_FIELDS')
    check.exact(receipt, _fields('schema scope session_id consumption transport remote_result wait capture real_task_execution result_evidence_collection state missing'), 'RECEIPT_FIELDS')
    check(marker['schema'] == 'local-hand-q2-core-carrier-consumption/v2'
        and cap['schema'] == 'local-hand-q2-core-capture-manifest/v1'
        and receipt['schema'] == 'local-hand-q2-core-local-acceptance-receipt/v1'
        and all(item['session_id'] == fixed['session'] for item in (marker, cap, receipt))
        and marker['scope'] == receipt['scope'] == SCOPE, 'SCHEMAS')
    check(marker['implementation'] == fixed['implementation'] and marker['baseline'] == BASELINE
        and marker['owner_decision'] == OWNER_DECISION and marker['closure'] == CLOSURE
        and marker['candidate'] == CANDIDATE and marker['state'] == 'CONSUMPTION_RECORD_COMPLETE', 'AUTHORITY')
    _amendment(marker['amendment'], fixed['implementation'])
    _validate_local_writer(marker['writer'])
    check.exact(marker['package'], _fields('basename bytes sha256 manifest_sha256'), 'PACKAGE')
    check(marker['package']['sha256'] == fixed['package_sha'] and marker['package']['manifest_sha256'] == fixed['manifest_sha']
        and marker['package']['basename'] == fixed['session'] + '.lhfp'
        and marker['package']['bytes'] == fixed['package_bytes']
        and re.fullmatch(r'[A-Za-z0-9._-]+\.lhfp', marker['package']['basename']) is not None, 'PACKAGE')
    for name in ('approved_inputs_sha256', 'local_management_binding_sha256', 'carrier_argv_sha256'):
        check.digest(marker[name], 'DIGEST')
    if index == 1:
        check(marker['approved_inputs_sha256'] ==
            '5bcbf535f6c8d0d2c974756af6815ba95a03da7fadc31c97a0622cdeeaf4846e'
            and raw['stderr'] == b'CORE_ADMIT_SUDO_OUTPUT\n', 'SECOND_FAILURE')
    if index == 3:
        check(marker['approved_inputs_sha256'] ==
            '169c6e8cef5a3d6ee94d7cf433996016710b5e5613a7158e57875baad09ee793'
            and raw['stderr'] == b'CORE_CAP_INSUFFICIENT\n', 'FOURTH_FAILURE')
    if index == 2:
        check(marker['approved_inputs_sha256'] ==
            '5d227ecbef0eb0b72a3c5ddee998c1505b88ddf70d3c3c506e262144c25198da'
            and raw['stderr'] == b'CORE_ADMIT_SSHD_GRAMMAR\n', 'THIRD_FAILURE')
    for clock in ('boottime', 'monotonic'):
        origin = check.integer(marker['host_' + clock + '_origin_ns'], 1, code='CLOCK')
        check(marker['host_' + clock + '_deadline_ns'] == origin + 900000000000, 'CLOCK')
    out = raw['stdout']
    check(out.startswith(b'LHCHLO1\n') and len(out) >= 16
        and struct.unpack('>Q', out[8:16])[0] == len(out) - 16, 'HELLO_FRAME')
    hello = document(out[16:], limit=4096)
    _validate_hello_identity(hello, fixed['unit'])
    check(hello['loader_sha256'] == '6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61'
        and hello['bootstrap_sha256'] == fixed['bootstrap_sha'], 'HELLO_SOURCE')
    marker_sha = _sha(raw['carrier-consumed.json'])
    check(receipt['consumption'] == dict(object_created=True, record_complete=True,
        basename=prefix + 'carrier-consumed.json', bytes=len(raw['carrier-consumed.json']), sha256=marker_sha)
        and cap['consumption_sha256'] == marker_sha, 'MARKER_LINK')
    check(receipt['transport'] == dict(execve_succeeded=True, hello_valid=True, bind_written=fixed['sent'],
        package_written=fixed['sent'], stdin_bytes_written=(0, 18150763, 18174538, 18194592)[index],
        stdin_eof=fixed['sent']), 'TRANSPORT')
    check(receipt['wait'] == dict(status=fixed['status'], stdout_eof=fixed['sent'],
        stderr_eof=fixed['sent'], host_deadline_met=fixed['sent'])
        and cap['wait'] == dict(status=fixed['status'], host_deadline_met=fixed['sent']), 'WAIT')
    check(receipt['state'] == 'STOP_AND_RETAIN' and receipt['real_task_execution'] == receipt['result_evidence_collection']
        == dict(status='UNKNOWN', evidence_sha256=None), 'TRUTH')
    check(receipt['remote_result'] == dict(present=False, sha256=None, frame_sha256=None)
        and cap['output_package'] == dict(present=False, frame_bytes=0, manifest_sha256=None,
            members_sha256=None, valid=False), 'OUTPUT')
    for stream in ('stdout', 'stderr'):
        check(cap[stream] == dict(basename=prefix + stream, bytes=len(raw[stream]),
            sha256=_sha(raw[stream]), eof=fixed['sent']), 'STREAM')
    check(type(cap['files']) is list and len(cap['files']) == 3 and [r['basename'] for r in cap['files']]
        == sorted(prefix + name for name in ('carrier-consumed.json', 'stdout', 'stderr')), 'CAPTURE_FILES')
    identities = set()
    for item in cap['files']:
        check.exact(item, _fields('basename bytes allocated_bytes sha256 dev ino mode nlink'), 'CAPTURE_FILE')
        data = raw[item['basename'][len(prefix):]]
        check(item['bytes'] == len(data) and item['sha256'] == _sha(data)
            and item['mode'] == 384 and item['nlink'] == 1, 'CAPTURE_PIN')
        for key in ('dev', 'allocated_bytes'):
            check.integer(item[key], 0, code='CAPTURE_FILE')
        check.integer(item['ino'], 1, code='CAPTURE_FILE')
        identities.add((item['dev'], item['ino']))
    check(len(identities) == 3 and cap['inodes'] == 3
        and cap['logical_bytes'] == sum(item['bytes'] for item in cap['files'])
        and cap['allocated_bytes'] == sum(item['allocated_bytes'] for item in cap['files'])
        and cap['fsync_complete'] is cap['reread_equal'] is True, 'CAPTURE_TOTAL')
    check(receipt['capture'] == dict(bytes=cap['allocated_bytes'], inodes=3,
        manifest_sha256=_sha(raw['capture-manifest.json']), fsync_complete=True, reread_equal=True), 'CAPTURE_LINK')
    missing = {'CORE_OUTPUT_MISSING'} if fixed['sent'] else {'CORE_OUTPUT_MISSING', 'CORE_TRANSPORT_FAILED'}
    check(receipt['missing'] == cap['missing'] and len(cap['missing']) == len(missing)
        and {item['code'] for item in cap['missing']} == missing, 'MISSING')
    for item in cap['missing']:
        check.exact(item, _fields('code role detail_sha256'), 'MISSING_FIELDS')
        check.digest(item['detail_sha256'], 'MISSING')
    return hello


def _prior_attempts(values):
    _require(type(values) is list and len(values) == 4, 'CORE_PRIOR_FOUR')
    return [_prior_attempt(value, index) for index, value in enumerate(values)]


def _prior_commitment(prior, index=0):
    _prior_attempt(prior, index)
    return dict(scope=SCOPE, session_id=_prior_profile(index)['session'], source_attempt_sha256=_sha(canonical(prior)),
        logical_bytes=289406976, logical_inodes=16512, cpu_seconds=2090,
        host_capture_bytes=67108864, host_capture_inodes=16, released_or_refunded=False)


PRIOR_SHOW_FIELDS = _fields('Id LoadState ActiveState SubState MainPID InvocationID ControlGroup Restart KillMode ExitType')


def _prior_scope_branch(unit, group, hello):
    check = _Checks('CORE_PRIOR_SCOPE_')
    check.exact(unit, PRIOR_SHOW_FIELDS, 'UNIT_FIELDS')
    check(all(type(value) is str and value.isascii() and '\n' not in value and '\0' not in value
        for value in unit.values()) and unit['Id'] == hello['carrier_unit']['name'] and unit['MainPID'] == '0', 'UNIT')
    old = hello['carrier_unit']; path = '/sys/fs/cgroup' + old['control_group']
    check.exact(group, _fields('path state parent identity populated procs_bytes'), 'CGROUP_FIELDS')
    check(group['path'] == path and group['state'] in ('ABSENT', 'EMPTY'), 'CGROUP')
    for name in ('parent', 'identity'):
        identity = group[name]
        if name == 'identity' and group['state'] == 'ABSENT':
            check(identity is None, 'ABSENT_IDENTITY'); continue
        check.exact(identity, _fields('path dev ino mode uid gid'), 'IDENTITY_FIELDS')
        check(identity['path'] == (str(PurePosixPath(path).parent) if name == 'parent' else path), 'PATH')
        for key in ('dev', 'ino', 'mode', 'uid', 'gid'):
            check.integer(identity[key], 1 if key == 'ino' else 0, code='IDENTITY')
        check(identity['uid'] == identity['gid'] == 0 and identity['mode'] <= 0o7777
              and not identity['mode'] & 0o022, 'PROTECTION')
    if group['state'] == 'ABSENT':
        check(group['populated'] is None and group['procs_bytes'] is None, 'ABSENT')
    else:
        check(type(group['populated']) is type(group['procs_bytes']) is int
            and group['populated'] == group['procs_bytes'] == 0, 'EMPTY')
    check(unit['LoadState'] == 'not-found' and unit['ActiveState'] == 'inactive'
        and unit['SubState'] == 'dead' and unit['InvocationID'] == unit['ControlGroup'] == ''
        and group['state'] == 'ABSENT', 'COLLECTED')
    return 'COLLECTED_ABSENT'


def _validate_prior_quiescence(value, context, index=0):
    check = _Checks('CORE_PRIOR_SCOPE_')
    priors = _approved_inputs_envelope(context)['reconciliation']['prior_core_attempts']
    _prior_attempts(priors)
    prior = priors[index]
    old = _prior_attempt(prior, index)
    check.exact(value, _fields('schema prior_attempt_sha256 boot_id branch observations current_scope_quiescent historical_remote_exit historical_usage released_bytes released_inodes'), 'RECORD_FIELDS')
    check(value['schema'] == 'local-hand-q2-core-prior-quiescence/v2'
        and value['prior_attempt_sha256'] == _sha(canonical(prior))
        and value['boot_id'] == context['hello']['guest_boot_id']
        and value['current_scope_quiescent'] is True
        and value['historical_remote_exit'] == value['historical_usage'] == 'UNKNOWN'
        and type(value['released_bytes']) is type(value['released_inodes']) is int
        and value['released_bytes'] == value['released_inodes'] == 0, 'RECORD')
    observations = value['observations']
    check(type(observations) is list and len(observations) == 2, 'COUNT')
    previous = None
    for ordinal, observation in enumerate(observations, 1):
        check.exact(observation, _fields('ordinal boottime_ns monotonic_ns unit cgroup'), 'OBSERVATION_FIELDS')
        check(type(observation['ordinal']) is int and observation['ordinal'] == ordinal, 'ORDINAL')
        for clock in ('boottime', 'monotonic'):
            now = check.integer(observation[clock + '_ns'], 1, code='CLOCK')
            check(context['hello']['guest_' + clock + '_origin_ns'] <= now
                < context['guest_deadlines'][clock + '_deadline_ns'] - REMOTE_FINAL_RESERVE_NS
                and (previous is None or previous[clock + '_ns'] <= now), 'CLOCK')
        check(_prior_scope_branch(observation['unit'], observation['cgroup'], old) == value['branch'], 'BRANCH')
        if previous is not None:
            check(previous['unit'] == observation['unit'] and previous['cgroup'] == observation['cgroup'], 'DRIFT')
        previous = observation
    return value


def _validate_prior_quiescences(values, context):
    _journal_transition_context(context)
    _prior_concurrency_bound(context)
    _require(type(values) is list and len(values) == 4, 'CORE_PRIOR_SCOPE_FOUR')
    result = [_validate_prior_quiescence(value, context, index) for index, value in enumerate(values)]
    for clock in ('boottime_ns', 'monotonic_ns'):
        ordered = [row['observations'][ordinal][clock] for ordinal in (0, 1) for row in result]
        _require(ordered == sorted(ordered), 'CORE_PRIOR_SCOPE_ORDER')
    return result


def _prior_concurrency_bound(context):
    """Derived from four core HELLO limits, not a whole-host capacity promise.

    The pre-business premise is reviewed against fixed historical Git bytes by
    the offline freezer. Helpers inherit the new carrier; no new unit is made.
    Returned admissions retain three priors and the current HELLO binding.
    Diagnostic/management ancestors and unrelated load are not covered here.
    LIMITS remains the new batch's post-quiescence 2624 MiB / 1160 pid bound.
    """
    hellos = _prior_attempts(_approved_inputs_envelope(context)['reconciliation']['prior_core_attempts'])
    _validate_hello_identity(context['hello'], 'lhqcore20261007a-carrier.service')
    units = [value['carrier_unit'] for value in [*hellos, context['hello']]]
    memory = sum(value['memory_max'] for value in units)
    pids = sum(value['tasks_max'] for value in units)
    _require(len({value['name'] for value in units}) == 5
        and memory == 5368709120 and pids == 640, 'CORE_PRIOR_CONCURRENCY')
    return dict(memory_bytes=memory, pids=pids)


class _PriorScopeObserver:
    """Two finite observations in this carrier, no polls, stop or PID adoption."""

    def __init__(self, effects, programs, index=0):
        _prior_profile(index)
        self.effects = effects; self.programs = programs; self.nodes = []; self.group_fd = None
        self.observations = []
        self.index = index
        priors = _approved_inputs_envelope(effects.context)['reconciliation']['prior_core_attempts']
        _prior_attempts(priors)
        self.prior = priors[index]
        self.old = _prior_attempt(self.prior, index)
        _journal_transition_context(effects.context)
        self.path = '/sys/fs/cgroup' + self.old['carrier_unit']['control_group']
        self.parent_path = str(PurePosixPath(self.path).parent)
        self.name = PurePosixPath(self.path).name

    @staticmethod
    def identity(path, info):
        _require(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 0
            and not info.st_mode & 0o022, 'CORE_PRIOR_SCOPE_PARENT_PROTECTION')
        return dict(path=path, dev=info.st_dev, ino=info.st_ino, mode=stat.S_IMODE(info.st_mode),
                    uid=info.st_uid, gid=info.st_gid)

    def _parents(self):
        call = self.effects._capacity_call
        if not self.nodes:
            parts = PurePosixPath(self.parent_path).parts
            parent = None; path = ''
            for index, name in enumerate(parts):
                path = '/' if index == 0 else path.rstrip('/') + '/' + name
                fd = call(os.open, name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                          dir_fd=parent, release=os.close)
                self.nodes.append((fd, parent, name, path, None))
                identity = self.identity(path, call(os.fstat, fd))
                self.nodes[-1] = (fd, parent, name, path, identity)
                parent = fd
            _require(call(_kernel_fs_type, self.nodes[-1][0]) == 0x63677270, 'CORE_PRIOR_SCOPE_FILESYSTEM')
        for fd, parent, name, path, identity in self.nodes:
            _require(self.identity(path, call(os.fstat, fd)) == identity
                == self.identity(path, call(os.stat, name, dir_fd=parent, follow_symlinks=False)),
                'CORE_PRIOR_SCOPE_PARENT_DRIFT')
        return self.nodes[-1][0], self.nodes[-1][4]

    def observe(self):
        _require(len(self.observations) < 2, 'CORE_PRIOR_SCOPE_NO_RETRY')
        # Consume the observation slot before any effect. A failed A cannot be
        # retried or advanced to B by this same observer.
        ordinal = len(self.observations) + 1
        _require(not getattr(self, 'failed', False), 'CORE_PRIOR_SCOPE_STOPPED')
        self.failed = True
        e = self.effects; call = e._capacity_call
        e._effect_guard(); parent, parent_pin = self._parents()
        raw = e._capacity_systemctl(['show', '--all', self.old['carrier_unit']['name'],
            '--property=' + ','.join(PRIOR_SHOW_FIELDS)], self.programs['systemctl'],
            prior_observation=(self.index, ordinal))
        try:
            lines = raw.decode('ascii').splitlines()
            pairs = [line.split('=', 1) for line in lines]
            _require(len(pairs) == len(PRIOR_SHOW_FIELDS) and all(len(row) == 2 for row in pairs)
                and len({row[0] for row in pairs}) == len(pairs), 'CORE_PRIOR_SCOPE_SHOW')
            unit = dict(pairs)
        except UnicodeError as error:
            raise DispatchError('CORE_PRIOR_SCOPE_SHOW') from error
        try:
            fd = call(os.open, self.name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                      dir_fd=parent, release=os.close)
        except FileNotFoundError:
            _require(self.group_fd is None, 'CORE_PRIOR_SCOPE_CGROUP_DRIFT')
            group = dict(path=self.path, state='ABSENT', parent=parent_pin,
                         identity=None, populated=None, procs_bytes=None)
        else:
            try:
                pin = self.identity(self.path, call(os.fstat, fd))
                _require(call(_kernel_fs_type, fd) == 0x63677270, 'CORE_PRIOR_SCOPE_FILESYSTEM')
                if self.group_fd is not None:
                    _require(pin == self.identity(self.path, call(os.fstat, self.group_fd)), 'CORE_PRIOR_SCOPE_CGROUP_DRIFT')
                events = e._capacity_kernel('cgroup.events', 1024, dir_fd=fd)
                procs = e._capacity_kernel('cgroup.procs', 4096, dir_fd=fd)
                event_rows = [line.split() for line in events.decode('ascii').splitlines()]
                _require(all(len(row) == 2 for row in event_rows)
                    and len({row[0] for row in event_rows}) == len(event_rows), 'CORE_PRIOR_SCOPE_EVENTS')
                parsed = dict(event_rows)
                _require(set(parsed) == {'populated', 'frozen'} and parsed['populated'] == '0'
                    and parsed['frozen'] in ('0', '1') and procs == b'', 'CORE_PRIOR_SCOPE_POPULATED')
                _require(pin == self.identity(self.path, call(os.fstat, fd))
                    == self.identity(self.path, call(os.stat, self.name, dir_fd=parent, follow_symlinks=False)),
                    'CORE_PRIOR_SCOPE_CGROUP_DRIFT')
                group = dict(path=self.path, state='EMPTY', parent=parent_pin, identity=pin, populated=0, procs_bytes=0)
                if self.group_fd is None:
                    self.group_fd = fd; fd = None
            finally:
                if fd is not None: os.close(fd)
        self._parents()
        if group['state'] == 'ABSENT':
            try:
                call(os.stat, self.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise DispatchError('CORE_PRIOR_SCOPE_CGROUP_DRIFT')
        now = e._effect_guard()
        _require(now['boot_id'] == e.context['hello']['guest_boot_id'], 'CORE_PRIOR_SCOPE_BOOT')
        branch = _prior_scope_branch(unit, group, self.old)
        observation = dict(ordinal=ordinal, boottime_ns=now['boottime_ns'], monotonic_ns=now['monotonic_ns'], unit=unit, cgroup=group)
        if self.observations:
            previous = self.observations[0]
            _require(previous['unit'] == unit and previous['cgroup'] == group
                and all(previous[name] <= observation[name] for name in ('boottime_ns', 'monotonic_ns')), 'CORE_PRIOR_SCOPE_DRIFT')
        self.observations.append(observation); self.branch = branch; self.failed = False
        return observation

    def finish(self):
        _require(not getattr(self, 'failed', True) and len(self.observations) == 2, 'CORE_PRIOR_SCOPE_INCOMPLETE')
        self.recheck()
        return _validate_prior_quiescence(dict(schema='local-hand-q2-core-prior-quiescence/v2',
            prior_attempt_sha256=_sha(canonical(self.prior)), boot_id=self.effects.context['hello']['guest_boot_id'], branch=self.branch,
            observations=self.observations, current_scope_quiescent=True, historical_remote_exit='UNKNOWN',
            historical_usage='UNKNOWN', released_bytes=0, released_inodes=0), self.effects.context, self.index)

    def recheck(self):
        """Final held-name check only; never a fifth SHOW or a new observation."""
        _require(not getattr(self, 'failed', True) and len(self.observations) == 2, 'CORE_PRIOR_SCOPE_INCOMPLETE')
        call = self.effects._capacity_call
        parent, _ = self._parents()
        if self.group_fd is None:
            try:
                call(os.stat, self.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return
            raise DispatchError('CORE_PRIOR_SCOPE_CGROUP_DRIFT')
        expected = self.observations[-1]['cgroup']['identity']
        _require(expected == self.identity(self.path, call(os.fstat, self.group_fd))
            == self.identity(self.path, call(os.stat, self.name, dir_fd=parent, follow_symlinks=False)),
            'CORE_PRIOR_SCOPE_CGROUP_DRIFT')

    def close(self):
        if self.group_fd is not None:
            os.close(self.group_fd); self.group_fd = None
        while self.nodes:
            os.close(self.nodes.pop()[0])


def _validate_diagnostic_retention(value):
    """Independent strict metadata consumer; private config is never transported."""
    pins = {
        'consumed.json': (495, '88f6c88c96d90effc2f06d15693bc04dd23353ef65825331275d0746e87e50a7'),
        'stdout': (7028, '7c22202275cc851bac0707c7a630a4b302d7d347de087b2705af2289ab4a5dcc'),
        'stderr': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
        'receipt.json': (1259, '1cc9fcdbf3179652d00e5c41cc37070e017f107f2ed96919a5ab0fbd64e5179c'),
    }
    expected = dict(schema='local-hand-q2-core-diagnostic-retention/v1',
        scope='LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1', session_id='lhqsshd-20261005a',
        implementation=dict(commit='bf8d391c3fdb24a5d4fc188b0ec9f2b36d9e5891',
            tree='460acde6c11a7b7555bf9992eb65bff16e822cad'),
        files=[dict(basename='.lhqsshd-20261005a.' + suffix, bytes=pins[suffix][0],
                    sha256=pins[suffix][1]) for suffix in sorted(pins)],
        reader_state='READER_REPORTED_COMPLETE', remote_supervision_proven=False,
        remote_exit='UNKNOWN', management_usage='UNKNOWN', reader_cpu_seconds=5,
        reader_address_space_bytes=134217728, host_capture_bytes=4194304,
        host_capture_inodes=8, released_or_refunded=False)
    _approved_equal(value, expected, 'DIAGNOSTIC_RETENTION')
    return value


# Fixed K2 originals; no capture or maintenance command is executed here.
# Public pins of the consumed 06a originals; no raw machine evidence is embedded.
PREVIOUS_JOURNAL_SESSION = 'lhqjgrow-20261006a'
PREVIOUS_JOURNAL_D = 'a743af326cdff6e4485b69332e2309130d82a915'
PREVIOUS_JOURNAL_PINS = {
    'consumed.json': (34007,'e5c7a9d540be9f1c7a7202039e43d7fc0d3ea359528582033d2fb1d9c5a12734'),
    'events.jsonl': (441,'02d8e0783337c774a44aeccda1f7788c10c5f9f424d479a01a14088d2bf013b2'),
    'pre.stdout': (0,'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'pre.stderr': (517,'4464dd988e5867af7e0f0c7bbd0b4c848391553c65095c5a57b5ff43958321af'),
    'receipt.json': (6577,'9d34abbf1917c5d352961fb8dface00d9b674549bf99f7b85335928d5e204573'),
}
PREVIOUS_JOURNAL_ABSENT = ('post.stdout','post.stderr','vm.pid','journal.backup.qcow2')


SECOND_JOURNAL_SESSION = 'lhqjgrow-20261007a'
SECOND_JOURNAL_D = 'a20bf2a4575df7578341af744630ceaac131a6a7'
# Explicit Owner-approved minimal index; raw originals remain private.
SECOND_JOURNAL_PINS = {'consumed.json': (37083, '8809770315137a0d5376422e2ac8098a9fb6e71cbc06943848a550cddfbbf9ea'),
 'events.jsonl': (441, '5a5e0ce88ac9b4ec72630edb7d96616f2c16c44745071c4846e0fc3d051a1d00'),
 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
 'pre.stderr': (532, '56af6ce2bb3a58df04b6b1bf67d10faff7585878eac6f436769f9e790df0205d'),
 'receipt.json': (7584, 'ff646655c3d0c87f6a112397c3c2d9e82bce8757e6e2581f7f2456d00519412d')}


THIRD_JOURNAL_SESSION = 'lhqjgrow-20261007b'
THIRD_JOURNAL_D = 'b2bc054d0c06526b454cd320f167cc1a40242ab8'
# Owner-approved five-original index; retained bodies and diagnostics stay private.
THIRD_JOURNAL_PINS = {
    'consumed.json': (40860, 'ebf9da98c36649fc957aadff8f06fb89362c694110976212ea39d5b9e4d4e888'),
    'events.jsonl': (441, 'd33e59a2b499982a0fa3c2d84862d9cbba3aa40127c5c669f7fe2b0f180b6555'),
    'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'pre.stderr': (1250, '060b70afbdc653ebe325c0ffab27ae0bad51367187c08d01a431a7ea08b935cc'),
    'receipt.json': (8808, '9c3af36a2d91e0f46bcace05999b93ddd64108f9e9d7721d08c4df0528168ce6'),
}


FOURTH_JOURNAL_SESSION = 'lhqjgrow-20261008a'
FOURTH_JOURNAL_D = 'd5b34316bc93b37442eb5db64ba265b965e68379'
# Owner-approved minimal index; retained originals and diagnostics stay private.
FOURTH_JOURNAL_PINS = {
    'consumed.json': (44154, 'b4b413abef4ff36527decd1731cfe92435df1a6b9c58345c64463cd46b06b557'),
    'events.jsonl': (441, '428dc35e25d521242cdfc4485b8b14687a1d7174eedc8f858158f7d9f53d0969'),
    'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'pre.stderr': (685, '08b9f7866e00edbe02a64bfb05247bdd0cb1ac48064e73c1b6e8485b4ccc8dfa'),
    'receipt.json': (9872, '85e8edadd61f3d66eb6cc6a1992a0f9d691e1c477270cabe44ce18fb75540b8f'),
}


FIFTH_JOURNAL_SESSION = 'lhqjgrow-20261008b'
FIFTH_JOURNAL_D = 'dc538b9034f00c635344defae57b7054319c2184'
# Owner-approved minimal index; raw evidence remains private.
FIFTH_JOURNAL_PINS = {
    'consumed.json': (47434, '711fc817db3a244fa7b9f820712c49691f6cbea1ef148af92201ebddeaf2b683'),
    'events.jsonl': (441, '1d3c5be159e507453897371135c3d7fd880af6bcf7bb1b82cf720e0591b51bca'),
    'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'pre.stderr': (686, '93b3c81cf4a7b9203fc6bd1e344e8ba78015f1eac11927a38be457de2fe3af84'),
    'receipt.json': (10928, '43bef2765b0b7cbe65262d794ac1119339238115b85bfd2c51214921ffd5d04c'),
}


SIXTH_JOURNAL_SESSION = 'lhqjgrow-20261008c'
SIXTH_JOURNAL_D = '064bdd614db4224c8c7e9d3b011af90622c11066'
# Owner-approved minimal index; raw evidence remains private.
SIXTH_JOURNAL_PINS = {
    'consumed.json': (50720, 'c3406555625f1d67cfd62d1208a29c58cbae374dfe4babd29d95b92734b186fa'),
    'events.jsonl': (441, '03829472e564be760a89e41954c1a5de892eb64324b5fb8540ef35878b26680f'),
    'pre.stderr': (605, '1f7bf58d562f5789c3b176e5a6661d3fdd0d1a105c10beed7986369dcadc8b4a'),
    'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'receipt.json': (11988, 'a0b67b05d79db01723c6340cadb7d03fa366fbf8571579e4437f37827e721274'),
}


SEVENTH_JOURNAL_SESSION = 'lhqjgrow-20261008d'
SEVENTH_JOURNAL_D = '341796561a6aaa6f95779f438b57d958a1fd5954'
# Owner-approved 08d minimal index; original capture remains private.
SEVENTH_JOURNAL_PINS = {'consumed.json': (54783, '83a2d8362eb429c0fb1517002196d4e0740cd2ade3dd10b3f71288626de568e7'), 'events.jsonl': (441, '2569845129129856b35a1c22d2d0cb1a8fa1e7cd511fc3abc975fb0a5153191b'), 'pre.stderr': (824, '274ec520be611f366fa0352b751867e9a56a9639b53b694e4585b0ba3d935207'), 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'receipt.json': (13242, 'f646741ff3fff6b237637266daef33f8c21e7c98c524b356aa3f6011d32a0cd1')}


EIGHTH_JOURNAL_SESSION = 'lhqjgrow-20261008e'
EIGHTH_JOURNAL_D = 'fa30146b0a49744b25df0f23969bf96b17eaacad'
# Owner-approved 08e minimal index; raw evidence remains private.
EIGHTH_JOURNAL_PINS = {'consumed.json': (61113, '0b09dc689f602ad36e8be8e3d15df559519b898d9b4419a08eb79194496dcdcb'), 'events.jsonl': (441, 'edca318f7d72d7220220607cd967f25df018d6d5cc6040ad087f035c674ffbf0'), 'pre.stderr': (1332, '2432edcb0e41893a1859538d67124dd266381f0920cb5c63c9d20edf6650fd76'), 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'receipt.json': (14315, 'ad85fadb333c7281e4ab967a5a699537dbee276937daaf5f6739fea972093a7c')}


NINTH_JOURNAL_SESSION = 'lhqjgrow-20261008f'
NINTH_JOURNAL_D = 'db6e7165322da3072ca1fd88a36401e18ebd4a86'
# Owner-approved old08f basename/bytes/SHA-256 index; raw returns remain private.
NINTH_JOURNAL_PINS = {'consumed.json': (64566, '75e0e745f13745d3efd45d52495d13bd8ea5a3ff626316fbf5168a5a493e30af'), 'events.jsonl': (441, '264edd9660fd59ba3b6884ae4df0cdd8846a16a4cc97665a835f5fa691d91749'), 'pre.stderr': (817, 'df134297b8556f6d3939fe17424807a44e275c57470c84d81577d1da30d307b8'), 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'receipt.json': (15447, 'de08569fc6fadccafcf434d842e43ad713fbb4b6fdb7c45d03cf95df5fa3ad4e')}


TENTH_JOURNAL_SESSION = 'lhqjgrow-20261009a'
TENTH_JOURNAL_D = '54d32df2f82fe863e1535ddb8134617c2654e33d'
# Owner-approved old09a minimal index; raw returns remain private.
TENTH_JOURNAL_PINS = {'consumed.json': (59556, '777715c3cbf6d9c9ecef43a63ae1fe2dee6fa4c48170f0114aa883383f55c87d'), 'events.jsonl': (441, '687cce89ef1ef88e44d482655d61e2a8e48d84bb4e2da36d154ccf98accfec60'), 'pre.stderr': (922, '6c40a4e9d0882c80ffb89829be5c52cf9bc861a698d5bd498c1efa434539a88e'), 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'receipt.json': (16482, '1737c6c75c8dc97b80734e94b4d161f33b9893d7ad8e63658acc9514e190d096')}


ELEVENTH_JOURNAL_SESSION = 'lhqjgrow-20261009b'
ELEVENTH_JOURNAL_D = '547bbb05816e17525470b1a3c136b328ff96adc1'
# Owner-approved old09b minimal index; no remote completion is inferred.
ELEVENTH_JOURNAL_PINS = {'consumed.json': (63853, '30aa04638c3682a3317a5e83ba5769a167e98ea0e32053b204812ae0a0c03f45'), 'events.jsonl': (441, '9852dffa8014fd2e1385f7aa1d46b6ec37849773830fa13b3d065af0372aa6fd'), 'pre.stderr': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'receipt.json': (17254, 'cd87d061060c3fdbaad785c46f598ec31f5f806f2b0f88a490e1bf4a7a1261e3')}


def previous_journal_profiles():
    return (
        dict(session=PREVIOUS_JOURNAL_SESSION, D=PREVIOUS_JOURNAL_D, pins=PREVIOUS_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A='5d6cefa602e9146f02887ebfaa4b0cad4e376ff2', C='8a4c24cefe4abbab193577b2dff48fc49626cae4'),
            version=2, stage='PRE_IDENTITY', reason='GROWTH_JOURNAL_SERIAL'),
        dict(session=SECOND_JOURNAL_SESSION, D=SECOND_JOURNAL_D, pins=SECOND_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A='7869bbcaeb1dad3a1736131a3ff2e225ddf5e7cc', C='91c706b52dbc70498d5d872f59874c002cef23db'),
            version=3, stage='PRE_QUIESCENCE', reason='GROWTH_SYSTEMCTL_STDERR'),
        dict(session=THIRD_JOURNAL_SESSION, D=THIRD_JOURNAL_D, pins=THIRD_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A='62666eeec9f2f28833876df3d68ce6e8b8e0af54', C='7b342ced547639f93797e849b34ed3da4915c8d3'),
            version=4, stage='PRE_QUIESCENCE', reason='GROWTH_SYSTEMCTL_STDERR'),
        dict(session=FOURTH_JOURNAL_SESSION, D=FOURTH_JOURNAL_D, pins=FOURTH_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A='80c7c8eaeda0853317c679b31b0ed1f1ac13e49b', C='bb9b3c6e9b397121220c22515e4ef637d12c7297'),
            version=5, stage='PRE_QUIESCENCE', reason='GROWTH_SYSTEMCTL_NAMES'),
        dict(session=FIFTH_JOURNAL_SESSION, D=FIFTH_JOURNAL_D, pins=FIFTH_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A='68cae882e3b831aaa191e7a877278ccf6ba10e2b', C='eba5023b13e42d4610533b7e7c4eede3ebd658db'),
            version=6, stage='PRE_QUIESCENCE', reason='GROWTH_SYSTEMCTL_FORMAT'),
        dict(session=SIXTH_JOURNAL_SESSION, D=SIXTH_JOURNAL_D, pins=SIXTH_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A='5b14123206ced8117374d3fd2ef84b9f38784db3', C='987c77f6eb16e7ca41d8b1d4ccd7f89faf418d32'),
            version=7, stage='PRE_QUIESCENCE', reason='GROWTH_INDIRECT_STARTUP_UNVERIFIED'),
        dict(session=SEVENTH_JOURNAL_SESSION, D=SEVENTH_JOURNAL_D, pins=SEVENTH_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A='7ea9aed6a4f8be6d6fee0ee549e1e02378f32672', C='001bd4f7baedf115ce67feba87a21d8e259c8d1d'),
            version=8, stage='PRE_QUIESCENCE', reason='GROWTH_UNDECLARED_BUSINESS_UNIT'),
        dict(session=EIGHTH_JOURNAL_SESSION, D=EIGHTH_JOURNAL_D, pins=EIGHTH_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A='e66b1b5524f22d60c810dffac59ca418c5ad4236', C='61fae1da528105605a023f260130c4e0d9c1bc02'),
            version=9, stage='PRE_QUIESCENCE', reason='GROWTH_UNDECLARED_BUSINESS_UNIT'),
        dict(session=NINTH_JOURNAL_SESSION, D=NINTH_JOURNAL_D, pins=NINTH_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A='2b13dd653ca19eaaf46a18e6ffc3f447b62eee59', C='a2a6d62de08b2d1d8fbf9da97e8ccf938e3777c1'),
            version=10, stage='PRE_QUIESCENCE', reason='GROWTH_BUSINESS_PROCESS'),
        dict(session=TENTH_JOURNAL_SESSION,D=TENTH_JOURNAL_D,pins=TENTH_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A='13cd2d3e7ac9a307a7c960f713524fefa2959a95', C='31b8e21116edd3678d738c1b9525edb6b3da8ae8'),
            version=11,stage='PRE_QUIESCENCE',reason='GROWTH_GUEST_IO_OR_RUNTIME'),
        dict(session=ELEVENTH_JOURNAL_SESSION,D=ELEVENTH_JOURNAL_D,pins=ELEVENTH_JOURNAL_PINS,
            authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04', A=RUNTIME_A, C=RUNTIME_C),version=12,stage='LOCAL_TRANSPORT_CONSTRUCTION',reason='LOCAL_IO_OR_TRANSPORT'))





# Only the Owner-approved six local-return pins are public. The other archive
# pins and frozen caller hashes are private inputs, bound by the new caller freeze.
LOCAL_PREFLIGHT_D = '5db76ed8ad6f336dd5daf2401635c6be7a637d3b'
LOCAL_PREFLIGHT_SESSION = 'lhqjgrow-20261009c'
LOCAL_PREFLIGHT_SCOPE = 'LH-Q2-CORE-HOST-FD-CONTINUATION-v1'
LOCAL_PREFLIGHT_CALLERS = ('accept_maintenance.py','core_once.py','maintenance_once.py',
    'offline_maintenance.py','static_inputs.py')
LOCAL_PREFLIGHT_PINS = {'fd2-caller-started.json': (83, 'd48d67b065b1f86baa47b47590ea22ba0c02f4729a3c15477b8dc70330a7fa3f'), 'fd2-caller.stderr': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'fd2-caller.stdout': (313, '27927a51afe50b131a390a649bd37521fbfaaf531cc340a8d502277ec114cf87'), 'fd2-preflight.stderr': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'fd2-preflight.stdout': (339, '4cdba663538b0c930f36f739235361b00894cc0a603384b85b68a0a199b2079e'), 'fd2-summary.json': (313, '27927a51afe50b131a390a649bd37521fbfaaf531cc340a8d502277ec114cf87')}
LOCAL_PREFLIGHT_RECORDS = ('freeze-complete.json','execution-result.json','release-gate.json')


def local_preflight_summary():
    return dict(scope=LOCAL_PREFLIGHT_SCOPE,session=LOCAL_PREFLIGHT_SESSION,D=LOCAL_PREFLIGHT_D,
        originals=[dict(basename=n,bytes=v[0],sha256=v[1]) for n,v in sorted(LOCAL_PREFLIGHT_PINS.items())],
        state='PREFLIGHT_FAILED_STOP_AND_RETAIN',terminal='FD2_PREFLIGHT_FAILED_FD3_NOT_RUN',
        caller_invocations=1,execute_invocations=0,ssh_requests=0,marker_created=False,
        maintenance_window_consumed=False,core_package='NOT_BUILT',core_cases='NOT_RUN',
        reason='GROWTH_USAGE_UNKNOWN',diagnostic_retained=False,old_commitments_refunded=False)


def validate_local_preflight_source(value):
    check=_Checks('CORE_JOURNAL_')
    check.exact(value,{'schema','summary','archive','originals','freeze_sha256','callers'},'LOCAL_PREFLIGHT_FIELDS')
    check(value['schema']=='local-hand-q2-local-preflight-source/v1'
        and canonical(value['summary'])==canonical(local_preflight_summary()),'LOCAL_PREFLIGHT_SUMMARY')
    check.exact(value['archive'],{'bytes','sha256'},'LOCAL_PREFLIGHT_ARCHIVE_PIN')
    check.integer(value['archive']['bytes'],1,131072);check.digest(value['archive']['sha256'])
    check.digest(value['freeze_sha256'])
    check.exact(value['callers'],LOCAL_PREFLIGHT_CALLERS,'LOCAL_PREFLIGHT_CALLERS')
    for pin in value['callers'].values():check.digest(pin)
    pins=value['originals'];check.exact(pins,(*LOCAL_PREFLIGHT_PINS,*LOCAL_PREFLIGHT_RECORDS),'LOCAL_PREFLIGHT_ORIGINALS')
    for name,row in pins.items():
        check.exact(row,{'bytes','sha256'},'LOCAL_PREFLIGHT_PIN')
        check.integer(row['bytes'],0,65536);check.digest(row['sha256'])
        if name in LOCAL_PREFLIGHT_PINS:
            check((row['bytes'],row['sha256'])==LOCAL_PREFLIGHT_PINS[name],'LOCAL_PREFLIGHT_RETURN_PIN')
    check(pins['freeze-complete.json']['sha256']==value['freeze_sha256'],'LOCAL_PREFLIGHT_FREEZE_PIN')
    return value

def _maintenance_resume():
    return dict(scope='LH-Q2-CORE-USAGE-CONTINUATION-v1', session='lhqjgrow-20261010a',
        previous_local_preflight=local_preflight_summary(),
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()])


def _maintenance_commitments():
    return dict(previous_maintenance=_maintenance_resume(),
        generations=[dict(session=session,bytes=1296*1048576,inodes=370,cpu_seconds=120)
            for session in (PREVIOUS_JOURNAL_SESSION,SECOND_JOURNAL_SESSION,THIRD_JOURNAL_SESSION,FOURTH_JOURNAL_SESSION,FIFTH_JOURNAL_SESSION,SIXTH_JOURNAL_SESSION,SEVENTH_JOURNAL_SESSION,EIGHTH_JOURNAL_SESSION,NINTH_JOURNAL_SESSION,TENTH_JOURNAL_SESSION,ELEVENTH_JOURNAL_SESSION,'lhqjgrow-20261009c','lhqjgrow-20261010a')],
        released_or_refunded=False)


def _validate_maintenance_resume(value):
    _Checks('CORE_JOURNAL_')(type(value) is dict and canonical(value)==canonical(_maintenance_resume()),
        'PREVIOUS_SUMMARY')
    return value


JOURNAL_SESSION = 'lhqjgrow-20261010a'
JOURNAL_FILES = {'consumed.json': 65536, 'events.jsonl': 1048576,
    'pre.stdout': 1048576, 'pre.stderr': 1048576, 'post.stdout': 1048576,
    'post.stderr': 1048576, 'receipt.json': 65536, 'vm.pid': 64}
JOURNAL_SOURCE_NAMES = ('q2_journal_growth.py', 'q2_journal_growth_guest.py',
    'q2_core_capacity_capture.py', 'q2_core_capacity_reader.py', 'q2_sshd_source_capture.py',
    'q2_sshd_source_reader.py', 'q2_core_obligation_inputs.py', 'q2_core_prior_attempt.py',
    'q2_core_delivery_contract.py', 'q2_local_source_delivery.py', 'q2_core_approved_inputs.py',
    'q2_host_kernel_facts.py', 'q2_journal_retained_fds.py')


ACTIVATION_EVENT = 'LH-Q1-QUOTA-REPAIR-ACTIVATION-20261009-03'
ACTIVATION_FILES = ('activate-approved.py','activation-proposal-private.json',
    'current-vm-binding-private.json','endpoint-after.stderr','endpoint-after.stdout',
    'endpoint-before.stderr','endpoint-before.stdout','execution-freeze-private.json',
    'explicit-owner-approval-private.json','independent-return-verification-private.json',
    'index-preparation-note-private.json','launch-consumed-private.json','new-pid-cmdline.raw',
    'new-pid-stat.raw','offline-control-flow-result-private.json','offline-control-flow-test.py',
    'pending-owner-approval-private.json','preparation-pins-private.json',
    'protected-source/q2_sshd_source_capture.py','protected-source/q2_sshd_source_reader.py',
    'qemu-start.stderr','qemu-start.stdout','qemu-version.stderr','qemu-version.stdout',
    'result-private.json','retained-index-private.json','ssh-consumed-private.json',
    'ssh-install.stderr','ssh-install.stdout','started-private.json')
ACTIVATION_PROJECTION_FIELDS = {'schema','event','historical_boot_id','current_boot_id','host_boot_id',
    'vm','image_identities','original_system_identity','system_path','pidfile','serial',
    'index','evidence_sha256','candidate_prelaunch_sha256','candidate_digest_scope',
    'package_verified','quota_verified','old_records_preserved','execution_permission'}


def _validate_vm_activation(value):
    """Validate the host-verified projection without asserting unseen originals."""
    check = _Checks("CORE_ACTIVATION_")
    check.exact(value, ACTIVATION_PROJECTION_FIELDS, 'CORE_ACTIVATION_FIELDS')
    check(value['schema']=='local-hand-q2-vm-activation/v1' and value['event']==ACTIVATION_EVENT,
        'ACTIVATION_SCHEMA')
    check(len(canonical(value))<=4096, 'ACTIVATION_BOUND')
    for key in ('historical_boot_id','current_boot_id','host_boot_id'):
        check(type(value[key]) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value[key]),'ACTIVATION_BOOT')
    check(value['historical_boot_id']!=value['current_boot_id'],'ACTIVATION_BOOT_CHANGE')
    vm=value['vm'];check.exact(vm,{'pid','starttime','argv_sha256'},'CORE_ACTIVATION_VM')
    check.integer(vm['pid'],2);check.integer(vm['starttime'],1);check.digest(vm['argv_sha256'])
    check.exact(value['image_identities'],{'system','quota','journal','evidence','seed'},'CORE_ACTIVATION_IMAGES')
    pairs=list(value['image_identities'].values())+[value['original_system_identity']]
    for pair in pairs:
        check(type(pair) is list and len(pair)==2,'ACTIVATION_IMAGE_IDENTITY')
        check.integer(pair[0]);check.integer(pair[1],1)
    check(len({tuple(v) for v in pairs})==6,'ACTIVATION_IMAGE_ALIAS')
    for key in ('system_path','pidfile','serial'):
        path=value[key]
        check(type(path) is str and re.fullmatch(r'/[A-Za-z0-9_./-]{1,4095}',path)
            and os.path.normpath(path)==path and '..' not in path.split('/'),'ACTIVATION_PATH')
    check(len({value[k] for k in ('system_path','pidfile','serial')})==3,'ACTIVATION_PATH_ALIAS')
    check.exact(value['index'],{'bytes','sha256'},'CORE_ACTIVATION_INDEX')
    check.integer(value['index']['bytes'],1,65536);check.digest(value['index']['sha256'])
    for key in ('evidence_sha256','candidate_prelaunch_sha256'):check.digest(value[key])
    check(value['candidate_digest_scope']=='PRELAUNCH_ONLY'
        and value['package_verified'] is value['quota_verified'] is value['old_records_preserved'] is True
        and value['execution_permission'] is False,'ACTIVATION_ACCEPTANCE')
    return value


# Pending authority is not a commit or execution permission.
VM_ADOPTION_A = '13cd2d3e7ac9a307a7c960f713524fefa2959a95'
VM_ADOPTION_C = '31b8e21116edd3678d738c1b9525edb6b3da8ae8'
HOST_FD_A = '0ed9ba0a8eefa4d1a88ee46192fc18a5ad3fafc8'
HOST_FD_C = '26a89a1a11a958c24987eb590944331a9769b2ad'
USAGE_A = 'bb75dfd835640ba3fff5d1124b7820b0aecf87e5'
USAGE_C = '2a4282800eaae404ff3163446cc06297ce99526a'
RUNTIME_A = 'dc6e6c511936e02f41cda0cf86cbd571f3aa253d'
RUNTIME_C = '3633b1e963b35647bef8d7f94592089130ff25a1'


RUNTIME_BINDING_SHA="8593dcfdf2b169176b8f7025e392a9942589ee19d3cc9d3c04a5692a5f6ccd9b"
def _validate_runtime_binding(value):
    check=_Checks("CORE_RUNTIME_")
    check.exact(value,{"schema","sources","account","parents","manager"},"BINDING_FIELDS")
    check(len(canonical(value))<8192 and _sha(canonical(value)+b"\n")==RUNTIME_BINDING_SHA,"BINDING_PIN")
    return value

def _validate_runtime_summaries(value,binding,nonce,boots,reports):
 check=_Checks("CORE_RUNTIME_")
 _validate_runtime_binding(binding)
 check(type(value) is dict and set(value)=={"pre","post"},"GROWTH_RUNTIME_SUMMARIES")
 for phase,row in value.items():
  check(type(row) is dict and set(row)=={"schema","binding_sha256","nonce","phase","boot_id","report_sha256",
 "runtime_sha256","commands_sha256","configs_sha256","elapsed_ns","parents","manager","pools"}
 and row["schema"]=="lhq-runtime-transition/v1" and row["binding_sha256"]==_sha(canonical(binding)+b"\n")
 and row["nonce"]==nonce and row["phase"]==phase and row["boot_id"]==boots[phase]
 and row["report_sha256"]==reports[phase]["sha256"],"GROWTH_RUNTIME_SUMMARY_BINDING")
  for name in ("runtime_sha256","commands_sha256","configs_sha256"):check.digest(row[name])
  check.integer(row["elapsed_ns"],0,60000000000)
  check(type(row["parents"]) is dict and set(row["parents"])==set(binding["parents"]),"GROWTH_RUNTIME_SUMMARY_PARENTS")
  for role,item in row["parents"].items():
   check(type(item) is dict and set(item)=={"unit","control_group","invocation_id","identity"}
 and all(item[key]==binding["parents"][role][key] for key in ("unit","control_group"))
 and re.fullmatch(r"[0-9a-f]{32}",item["invocation_id"] or ""),"GROWTH_RUNTIME_SUMMARY_PARENT")
   check(type(item["identity"]) is dict and set(item["identity"])==set(("dev","ino","mode","uid","gid")),"GROWTH_RUNTIME_SUMMARY_IDENTITY")
   for v in item["identity"].values():check.integer(v)
  check(type(row["manager"]) is dict and set(row["manager"])=={"Id","ControlGroup","InvocationID"}
 and row["manager"]["Id"]==binding["manager"]["unit"] and row["manager"]["ControlGroup"]==binding["manager"]["control_group"]
 and re.fullmatch(r"[0-9a-f]{32}",row["manager"]["InvocationID"] or ""),"GROWTH_RUNTIME_SUMMARY_MANAGER")
  check(type(row["pools"]) is list and 1<=len(row["pools"])<=2,"GROWTH_RUNTIME_SUMMARY_POOLS")
  for pool in row["pools"]:
   check(type(pool) is dict and set(pool)=={"dev","reserved_bytes","reserved_inodes","before","after"}
 and pool["reserved_bytes"]==8192*(1 if phase=="pre" else 2)
 and pool["reserved_inodes"]==32*(1 if phase=="pre" else 2),"GROWTH_RUNTIME_SUMMARY_POOL")
   check.integer(pool["dev"])
   for key in ("before","after"):
    check(type(pool[key]) is list and len(pool[key])==2 and all(type(n) is int for n in pool[key])
 and pool[key][0]>=pool["reserved_bytes"] and pool[key][1]>=pool["reserved_inodes"],"GROWTH_RUNTIME_SUMMARY_CAPACITY")
 return value

def _validate_retained_custody(value, *, implementation, nonce, source_files):
    check=_Checks('CORE_JOURNAL_')
    check(type(value) is dict and set(value)=={'schema','binding','pid','starttime','count','checks',
        'originals','ipc_bytes','cpu_nanoseconds','rss_bytes','state'},'CUSTODY_FIELDS')
    check(value['schema']=='lhq-retained-custody/v1' and value['state']=='HELD_UNTIL_TEARDOWN'
        and value['count']==55,'CUSTODY_SCHEMA')
    for name,low,high in (('pid',2,2147483647),('starttime',1,2**63-1),('checks',1,64),
        ('ipc_bytes',1,2097152),('cpu_nanoseconds',0,120000000000),('rss_bytes',1,536870912)):
        check(type(value[name]) is int and low<=value[name]<=high,'CUSTODY_BOUNDS')
    pins={'.'+row['session']+'.'+name:(size,digest) for row in previous_journal_profiles()
        for name,(size,digest) in row['pins'].items()}
    originals=value['originals']
    check(type(originals) is list and len(originals)==55,'CUSTODY_ORIGINALS')
    check([row['basename'] for row in originals]==list(pins),'CUSTODY_SET_ORDER')
    seen=set();owner=None
    for row in originals:
        check(type(row) is dict and set(row)=={'basename','metadata','bytes','sha256'}
            and (row['bytes'],row['sha256'])==pins[row['basename']],'CUSTODY_PIN')
        info=row['metadata']
        check(type(info) is dict and set(info)=={'dev','ino','mode','uid','gid','nlink','size','blocks','mtime_ns','ctime_ns'}
            and all(type(v) is int and v>=0 for v in info.values()),'CUSTODY_METADATA')
        check(info['mode']==33152 and info['nlink']==1 and info['uid']>0 and info['gid']>0
            and info['size']==row['bytes'],'CUSTODY_PROTECTION')
        key=(info['dev'],info['ino']);check(key not in seen,'CUSTODY_ALIAS');seen.add(key)
        current=(info['uid'],info['gid'],info['dev'])
        if owner is None:owner=current
        check(current==owner,'CUSTODY_OWNER')
    check(value['binding']==dict(D=implementation['commit'],nonce=nonce,
        source_sha256=source_files['q2_journal_retained_fds.py']['sha256'],
        history_sha256=_sha(canonical(_maintenance_resume())+b'\n'),set_sha256=_sha(canonical(originals)+b'\n')),'CUSTODY_BINDING')
    return value


def _validate_coordinator_completion(value, custody):
    check=_Checks('CORE_JOURNAL_')
    check(type(value) is dict and set(value)=={'returncode','receipt_sha256','child','usage'}
        and type(value['returncode']) is int and value['returncode']==0,'COORDINATOR_EXIT')
    check(type(value['receipt_sha256']) is str and re.fullmatch(r'[0-9a-f]{64}',value['receipt_sha256']) is not None,
        'COORDINATOR_RECEIPT')
    child=value['child'];usage=value['usage']
    check(type(child) is dict and set(child)=={'returncode','cpu_nanoseconds','rss_peak_bytes'}
        and type(child['returncode']) is int and child['returncode']==0,'CUSTODY_EXIT')
    check(type(usage) is dict and set(usage)=={'cpu_nanoseconds','rss_peak_bytes'},'COORDINATOR_USAGE')
    for key,low,high in (('cpu_nanoseconds',custody['cpu_nanoseconds'],120000000000),
        ('rss_peak_bytes',custody['rss_bytes'],536870912)):
        check(type(child[key]) is int and low<=child[key]<=high
            and type(usage[key]) is int and child[key]<=usage[key]<=high,'CUSTODY_FINAL_USAGE')
    return value


def _validate_journal_transition(value, *, priors, implementation, current_boot=None):
    """Consume the host projection; no host-original verification is claimed."""
    check = _Checks("CORE_JOURNAL_")
    check.exact(value, {'schema','authority','implementation','session','nonce','access_mode',
        'host_writer_observation','continuous_exclusion_proven','input_sha256','manifest_sha256','runtime_parent_binding','runtime_preparation',
        'source_files','originals','old_boot_id','new_boot_id','vm_activation','old_vm','new_vm','image_identities',
        'old_pidfd_exited','original_argv_sha256','restart_argv_sha256','backup','virtual_bytes',
        'filesystem','content','reports','completed_steps','transport_exits','image_checks',
        'logical_compare_exit','resize_exit','all_streams_eof','historical_exit','old_commitments_refunded','previous_maintenance','guest_startup_assurance','retained_custody','coordinator_completion','local_preflight_source'},
        'CORE_JOURNAL_FIELDS')
    check(len(canonical(value)) <= 65536 and value['schema']=='local-hand-q2-core-journal-transition/v13'
        and value['session']=='lhqjgrow-20261010a', 'JOURNAL_SCHEMA')
    check(value['authority']==dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04',
        A=USAGE_A,C=USAGE_C)
        and value['implementation']==implementation, 'JOURNAL_AUTHORITY')
    check(type(value['guest_startup_assurance']) is dict and canonical(value['guest_startup_assurance'])
        == canonical(dict(mode='TRUSTED_SINGLE_ADMIN',indirect_startup_observation='NOT_PERFORMED',
            undeclared_unit_inventory_observation='NOT_PERFORMED',
            no_undeclared_business_startup=True,continuous_exclusion_proven=False)), 'GUEST_STARTUP_PREMISE')
    _validate_retained_custody(value['retained_custody'],implementation=implementation,
        nonce=value['nonce'],source_files=value['source_files'])
    _validate_coordinator_completion(value['coordinator_completion'],value['retained_custody'])
    _validate_maintenance_resume(value['previous_maintenance'])
    validate_local_preflight_source(value['local_preflight_source'])
    _validate_runtime_summaries(value['runtime_preparation'],value['runtime_parent_binding'],value['nonce'],
        dict(pre=value['old_boot_id'],post=value['new_boot_id']),value['reports'])
    check.exact(implementation,{'commit','tree'},'CORE_JOURNAL_IMPLEMENTATION')
    for item in implementation.values():
        check(type(item) is str and re.fullmatch(r"[0-9a-f]{40}",item), "IMPLEMENTATION")
    check(value['access_mode']=='TRUSTED_SINGLE_ADMIN' and value['host_writer_observation']=='NOT_PERFORMED'
        and value['continuous_exclusion_proven'] is value['old_commitments_refunded'] is False
        and value['historical_exit']=='UNKNOWN', 'JOURNAL_ACCESS')
    for key in ('nonce','input_sha256','manifest_sha256','original_argv_sha256','restart_argv_sha256'):
        check.digest(value[key])
    for key in ('old_boot_id','new_boot_id'):
        check(type(value[key]) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value[key]),
            'JOURNAL_BOOT')
    activation=value['vm_activation']
    if activation is not None:
        _validate_vm_activation(activation)
        check(activation['current_boot_id']==value['old_boot_id'] and activation['vm']==value['old_vm']
            and activation['image_identities']==value['image_identities'], 'ACTIVATION_MAINTENANCE_BINDING')
    history_boot=activation['historical_boot_id'] if activation else value['old_boot_id']
    check(value['old_boot_id']!=value['new_boot_id']
        and all(hello['guest_boot_id']==history_boot for hello in _prior_attempts(priors))
        and (current_boot is None or current_boot==value['new_boot_id']), 'JOURNAL_BOOT_BINDING')
    rows=value['originals']
    check(type(rows) is list and len(rows)==8 and [row.get('basename') for row in rows]
        == sorted('.lhqjgrow-20261010a.'+name for name in JOURNAL_FILES), 'JOURNAL_ORIGINALS')
    check(next(row['sha256'] for row in value['originals'] if row['basename'].endswith('.receipt.json'))
        ==value['coordinator_completion']['receipt_sha256'],'JOURNAL_COMPLETION_RECEIPT')
    for row in rows:
        check.exact(row,{'basename','bytes','sha256'},'CORE_JOURNAL_ORIGINAL')
        check.integer(row['bytes'],0,JOURNAL_FILES[row['basename'][len('.lhqjgrow-20261010a.'):]])
        check.digest(row['sha256'])
    check.exact(value['source_files'],JOURNAL_SOURCE_NAMES,'CORE_JOURNAL_SOURCES')
    for name,row in value['source_files'].items():
        check.exact(row,{'bytes','sha256'},'CORE_JOURNAL_SOURCE')
        check.integer(row['bytes'],1,16384 if name=='q2_journal_retained_fds.py' else 98304 if name.startswith('q2_journal_growth') else 524288);check.digest(row['sha256'])
    for key in ('old_vm','new_vm'):
        row=value[key];check.exact(row,{'pid','starttime','argv_sha256'},'CORE_JOURNAL_VM')
        check.integer(row['pid'],2);check.integer(row['starttime'],1);check.digest(row['argv_sha256'])
    check(value['old_vm']!=value['new_vm'] and value['old_pidfd_exited'] is True,'JOURNAL_VM_EXIT')
    images=value['image_identities'];check.exact(images,{'system','quota','journal','evidence','seed'},'CORE_JOURNAL_IMAGES')
    for row in images.values():
        check(type(row) in (list,tuple) and len(row)==2,'JOURNAL_IMAGE_IDENTITY')
        check.integer(row[0]);check.integer(row[1],1)
    check(len({tuple(row) for row in images.values()})==5,'JOURNAL_IMAGE_ALIAS')
    check.exact(value['backup'],{'bytes','sha256'},'CORE_JOURNAL_BACKUP')
    check.integer(value['backup']['bytes'],1,335544320);check.digest(value['backup']['sha256'])
    check(canonical(value['virtual_bytes'])==canonical(dict(before=268435456,after=536870912)),
        'JOURNAL_SIZE')
    fs=value['filesystem'];check.exact(fs,{'uuid','before_bytes','after_bytes','available'},'CORE_JOURNAL_FILESYSTEM')
    check(type(fs['uuid']) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',fs['uuid']),
        'JOURNAL_UUID')
    check(type(fs['before_bytes']) is type(fs['after_bytes']) is int
        and fs['before_bytes']==268435456 and fs['after_bytes']==536870912,'JOURNAL_FILESYSTEM_SIZE')
    check.exact(fs['available'],{'bytes','inodes'},'CORE_JOURNAL_CAPACITY')
    check.integer(fs['available']['bytes'],419430400);check.integer(fs['available']['inodes'],32768)
    content=value['content'];check.exact(content,{'entries','content_bytes','sha256'},'CORE_JOURNAL_CONTENT')
    check.integer(content['entries'],1,32768);check.integer(content['content_bytes'],0,268435456);check.digest(content['sha256'])
    check.exact(value['reports'],{'pre','post'},'CORE_JOURNAL_REPORTS')
    for row in value['reports'].values():
        check.exact(row,{'bytes','sha256'},'CORE_JOURNAL_REPORT');check.integer(row['bytes'],1,1048576);check.digest(row['sha256'])
    check(value['completed_steps']==['CONSUMED','GUEST_QUIET','POWERED_OFF','BACKED_UP','IMAGE_GROWN',
        'BOOTED','FILESYSTEM_GROWN','VERIFIED'] and value['all_streams_eof'] is True,'JOURNAL_COMPLETION')
    check(type(value['transport_exits']) is list and len(value['transport_exits'])==2
        and all(type(v) is int for v in value['transport_exits'])
        and value['transport_exits'][0] in (0,255) and value['transport_exits'][1]==0,'JOURNAL_TRANSPORT')
    check(canonical(value['image_checks'])==b'[0,0]' and type(value['logical_compare_exit']) is int
        and value['logical_compare_exit']==0 and type(value['resize_exit']) is int and value['resize_exit']==0,
        'JOURNAL_CHECKS')
    return value


def _journal_transition_context(context):
    approved = _approved_inputs_envelope(context)
    return _validate_journal_transition(approved['reconciliation']['journal_transition'],
        priors=approved['reconciliation']['prior_core_attempts'],
        implementation=context['manifest']['implementation'], current_boot=context['hello']['guest_boot_id'])


def _validate_approved_components(value):
    """Validate all fixed component relations; this is not a live admission."""
    try:
        _approved_exact(value, ("schema", "scope", "amendment", *ADMISSION_COMPONENTS))
        _approved_require(value["schema"] == "local-hand-q2-core-approved-inputs/v1"
            and value["scope"] == SCOPE, "SCHEMA")
        _amendment(value["amendment"], value["amendment"]["implementation"])
        obligations = _approved_validate_relations(value)
        _approved_validate_capacity(value["historical_capacity_obligations"], obligations)
        _approved_validate_retained(value["retained_preparation"])
        reconciliation = value["reconciliation"]
        _approved_exact(reconciliation, (*APPROVED_RECONCILIATION, "schema", "prior_core_attempts", "prior_diagnostic_capture", "journal_transition"))
        _approved_require(reconciliation["schema"] == "local-hand-q2-core-reconciliation/v17", "RECONCILIATION_SCHEMA")
        _approved_equal({key: reconciliation[key] for key in APPROVED_RECONCILIATION},
                        APPROVED_RECONCILIATION, "RECONCILIATION")
        prior = reconciliation["prior_core_attempts"]
        _prior_attempts(prior)
        _validate_journal_transition(reconciliation['journal_transition'],priors=prior,
            implementation=value['amendment']['implementation'])
        _validate_diagnostic_retention(reconciliation['prior_diagnostic_capture'])
        _approved_equal(value["historical_capacity_obligations"]["prior_commitments"],
                        [_prior_commitment(item, index) for index, item in enumerate(prior)], "PRIOR_COMMITMENT")
        _approved_validate_policy(value["policy_basis"])
        return value
    except DispatchError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError, ValueError) as error:
        raise _approved.error("INVALID_SHAPE") from error


def _amendment(value, implementation):
    _check.exact(value, _fields('baseline owner_decision closure implementation'),
        "AMENDMENT_FIELDS")
    _check(value["baseline"] == AMENDMENT_BASELINE
        and value["owner_decision"] == AMENDMENT_OWNER_DECISION
        and value["closure"] == AMENDMENT_CLOSURE
        and value["implementation"] == implementation, "AMENDMENT_AUTHORITY")
    _check.exact(implementation, ("commit", "tree"), "IMPLEMENTATION")
    for item in implementation.values():
        _check.commit(item, "IMPLEMENTATION")
    _check(implementation["commit"] not in (
        CLOSURE["commit"], AMENDMENT_BASELINE["commit"], AMENDMENT_CLOSURE["commit"],
        "520f77f578b90d31870517e33e29bee42918f3c0"), "IMPLEMENTATION")
    return value


def _remote_management(value):
    _remote.exact(value, set(REMOTE_ALIASES) | {
        "account", "uid", "gid", "home", "login_shell", "parser_profile",
        "remote_tokens_sha256", "remote_command_sha256"}, "FIELDS")
    _remote(value["account"] == "q1admin" and value["home"] == "/home/q1admin"
        and value["login_shell"] == "/bin/bash"
        and value["parser_profile"] == "bash-noninteractive-c-v1", "ACCOUNT")
    for key in ("uid", "gid"):
        _remote.integer(value[key], 1, 2**32 - 2, "ACCOUNT")
    for key in ("remote_tokens_sha256", "remote_command_sha256"):
        _remote.digest(value[key], "COMMAND")
    total = 0
    for name, alias in REMOTE_ALIASES.items():
        item = _remote.exact(value[name], PROGRAM_FIELDS | {"resolved_path", "symlink_chain"},
            "ENTITY_FIELDS")
        _remote(item["path"] == alias, "ALIAS")
        _remote.absolute(item["resolved_path"], "ENTITY")
        for key in ("dev", "uid", "gid"):
            _remote.integer(item[key], 0, code="ENTITY")
        _remote.integer(item["ino"], 1, code="ENTITY")
        _remote.integer(item["nlink"], 1, 1, "ENTITY")
        _remote.integer(item["mode"], 0, 0o7777, "ENTITY")
        _remote.integer(item["bytes"], 1, 16777216, "ENTITY")
        _remote(item["uid"] == item["gid"] == 0 and item["mode"] & 0o111
            and not item["mode"] & 0o022, "ENTITY")
        _remote.digest(item["sha256"], "ENTITY")
        chain = item["symlink_chain"]
        _remote(type(chain) is list and len(chain) <= 8, "ALIAS")
        seen = set()
        for link in chain:
            _remote.exact(link, ("path", "target"), "ALIAS")
            _remote.absolute(link["path"], "ALIAS")
            target = link["target"]
            _remote(type(target) is str and target.isascii() and 0 < len(target) <= 4096
                and re.fullmatch(r"[A-Za-z0-9._/-]+", target) is not None
                and "//" not in target and ".." not in target.split("/")
                and len(target.split("/")) <= 64 and link["path"] not in seen, "ALIAS")
            seen.add(link["path"])
        total += item["bytes"]
    _remote(total <= 83886080, "ENTITY_LIMIT")
    return value


def _approved_inputs_envelope(context):
    """Bind preimages, not live facts; raw verification/admission remain required."""
    manifest, members = context["manifest"], context["members"]
    descriptor = _approved.exact(manifest["approved_inputs"], _fields('path bytes sha256 approved_source_relation_sha256'), "DESCRIPTOR")
    _approved(descriptor["path"] == APPROVED_INPUTS_PATH, "DESCRIPTOR")
    _approved.integer(descriptor["bytes"], 1, APPROVED_INPUTS_LIMIT, "DESCRIPTOR")
    for key in ("sha256", "approved_source_relation_sha256"):
        _approved.digest(descriptor[key], "DESCRIPTOR")
    view = members.get(APPROVED_INPUTS_PATH)
    _approved(type(view) is bytes or (isinstance(view, memoryview) and view.readonly), "MEMBER")
    raw = bytes(view)
    _approved(len(raw) == descriptor["bytes"] and _sha(raw) == descriptor["sha256"], "MEMBER")
    rows = [row for row in manifest["members"] if row.get("role") == "approved-inputs"]
    expected = {"path": APPROVED_INPUTS_PATH, "role": "approved-inputs", "mode": 384,
        "bytes": len(raw), "sha256": _sha(raw), "origin": {
            "kind": "approved-inputs", "bytes": len(raw), "sha256": _sha(raw),
            "approved_source_relation_sha256": descriptor["approved_source_relation_sha256"]}}
    _approved(rows == [expected], "ROW")
    value = document(raw, limit=APPROVED_INPUTS_LIMIT)
    _approved.exact(value, ("schema", "scope", "amendment", *ADMISSION_COMPONENTS), "FIELDS")
    _approved(value["schema"] == "local-hand-q2-core-approved-inputs/v1"
        and value["scope"] == SCOPE, "SCHEMA")
    _amendment(value["amendment"], manifest["implementation"])
    _approved(value["amendment"] == manifest["amendment"], "AMENDMENT")
    for key in ADMISSION_COMPONENTS:
        _approved(type(value[key]) is dict, "COMPONENT")
    _approved(_sha(canonical(value["source_relation"]))
        == descriptor["approved_source_relation_sha256"], "SOURCE_RELATION")
    return value


def _admission_binding(context):
    """Return the nine exact, distinct digests specified by amendment A §4."""
    approved = _approved_inputs_envelope(context)
    binding = {"approved_inputs_sha256": context["manifest"]["approved_inputs"]["sha256"]}
    for key in ADMISSION_COMPONENTS:
        name = "approved_source_relation" if key == "source_relation" else key
        binding[name + "_sha256"] = _sha(canonical(approved[key]))
    binding.update({
        "local_management_binding_sha256": context["manifest"]["entry"]["local_management_binding_sha256"],
        "hello_sha256": _sha(canonical(context["hello"], newline=True)),
        "remote_management_sha256": _sha(canonical(context["hello"]["remote_management"])),
    })
    for digest in binding.values():
        _admit.digest(digest, "BINDING")
    return binding


def _validate_admission_binding(value, context):
    expected = _admission_binding(context)
    _admit.exact(value, expected, "BINDING_FIELDS")
    _admit(value == expected, "BINDING")
    return value


def _validate_hello_identity(hello, carrier_name):
    """Pure frozen HELLO shape/limits; callers provide one of three fixed names."""
    _check.exact(hello, _fields('schema scope loader_sha256 bootstrap_sha256 guest_boot_id guest_boottime_origin_ns guest_monotonic_origin_ns pid uid gid euid egid python carrier_unit process_limits remote_management'),
        "HELLO_FIELDS")
    _check(hello["schema"] == HELLO_SCHEMA
        and hello["scope"] == SCOPE and hello["uid"] == hello["gid"] == 0
        and hello["euid"] == hello["egid"] == 0, "HELLO")
    for key in ("loader_sha256", "bootstrap_sha256"):
        _check.digest(hello[key], "HELLO")
    for key in _fields('uid gid euid egid'):
        _check.integer(hello[key], 0, 0, "HELLO")
    for key in ("pid", "guest_boottime_origin_ns", "guest_monotonic_origin_ns"):
        _check.integer(hello[key], 1, code="HELLO")
    _check(type(hello["guest_boot_id"]) is str and re.fullmatch(
        r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", hello["guest_boot_id"]), "HELLO")
    remote = _remote_management(hello["remote_management"])
    _check(hello["python"] == {
        key: remote["python"]["resolved_path"] if key == "path" else remote["python"][key]
        for key in PROGRAM_FIELDS}, "PYTHON_PROJECTION")
    unit = _check.exact(hello["carrier_unit"], _fields('name control_group invocation_id active_state sub_state runtime_max_usec timeout_stop_usec memory_max memory_swap_max tasks_max cpu_quota_per_sec_usec restart kill_mode exit_type'),
        "CARRIER_FIELDS")
    _check.absolute(unit["control_group"], "CARRIER")
    _check(unit["name"] == carrier_name and unit["control_group"].endswith("/" + carrier_name)
        and type(unit["invocation_id"]) is str
        and re.fullmatch(r"[0-9a-f]{32}", unit["invocation_id"])
        and unit["active_state"] == "active" and unit["sub_state"] in ("running", "start")
        and unit["restart"] == "no" and unit["kill_mode"] == "control-group"
        and unit["exit_type"] == "cgroup", "CARRIER")
    for key, expected in {"runtime_max_usec": 800000000, "timeout_stop_usec": 30000000,
        "memory_max": 1073741824, "memory_swap_max": 0, "tasks_max": 128,
        "cpu_quota_per_sec_usec": 1000000}.items():
        _check.integer(unit[key], expected, expected, "CARRIER")
    limits = {"cpu_soft": 800, "cpu_hard": 800, "nofile_soft": 256, "nofile_hard": 256,
        "fsize_soft": 67108864, "fsize_hard": 67108864, "umask": 0o077}
    _check.exact(hello["process_limits"], limits, "PROCESS_LIMITS")
    for key, expected in limits.items():
        _check.integer(hello["process_limits"][key], expected, expected, "PROCESS_LIMITS")
    canonical(hello, newline=True, limit=4096)
    return hello


def _validate_context_envelope(context):
    """Validate the v2 transport envelope without claiming admission/consumption."""
    _check.exact(context, _fields('schema hello bind manifest members guest_deadlines stdin_bytes_received'), "CONTEXT_FIELDS")
    _check(context["schema"] == CONTEXT_SCHEMA, "CONTEXT_SCHEMA")
    hello, bind, manifest = context["hello"], context["bind"], context["manifest"]
    carrier_name = "lhqcore20261007a-carrier.service"
    _validate_hello_identity(hello, carrier_name)
    remote = hello['remote_management']
    _check.exact(bind, _fields('schema scope session_id hello_sha256 consumption_sha256 package_basename package_bytes package_sha256 host_boottime_origin_ns host_monotonic_origin_ns host_boottime_deadline_ns host_monotonic_deadline_ns host_boottime_bind_ns host_monotonic_bind_ns host_remaining_floor_ns clock_margin_ns local_final_reserve_ns mapped_duration_ns guest_duration_cap_ns guest_duration_ns'), "BIND_FIELDS")
    _check(bind["schema"] == "local-hand-q2-core-carrier-bind/v1" and bind["scope"] == SCOPE
        and bind["session_id"] == SESSION and bind['package_basename'] == SESSION + '.lhfp'
        and bind["hello_sha256"] == _sha(canonical(hello, newline=True)),
        "BIND")
    for key in ("hello_sha256", "consumption_sha256", "package_sha256"):
        _check.digest(bind[key], "BIND")
    for key in _fields('host_boottime_origin_ns host_monotonic_origin_ns host_boottime_deadline_ns host_monotonic_deadline_ns host_boottime_bind_ns host_monotonic_bind_ns'):
        _check.integer(bind[key], 1, code="BIND_CLOCK")
    _check(bind["host_boottime_deadline_ns"]
        == bind["host_boottime_origin_ns"] + LIMITS["carrier_seconds"] * NS
        and bind["host_monotonic_deadline_ns"]
        == bind["host_monotonic_origin_ns"] + LIMITS["carrier_seconds"] * NS
        and bind["host_boottime_origin_ns"] <= bind["host_boottime_bind_ns"]
        < bind["host_boottime_deadline_ns"]
        and bind["host_monotonic_origin_ns"] <= bind["host_monotonic_bind_ns"]
        < bind["host_monotonic_deadline_ns"], "OUTER_DEADLINE")
    remaining = min(bind["host_boottime_deadline_ns"] - bind["host_boottime_bind_ns"],
        bind["host_monotonic_deadline_ns"] - bind["host_monotonic_bind_ns"])
    floor = remaining // 1_000_000 * 1_000_000
    _check(remaining > 0 and bind["host_remaining_floor_ns"] == floor
        and bind["clock_margin_ns"] == 2_000_000_000
        and bind["local_final_reserve_ns"] == 15_000_000_000
        and bind["mapped_duration_ns"] == floor - 17_000_000_000 > 0
        and bind["guest_duration_cap_ns"] == 750_000_000_000
        and bind["guest_duration_ns"] == min(bind["mapped_duration_ns"], 750_000_000_000),
        "BIND_MAPPING")
    _check.exact(manifest, _fields('schema scope rule baseline owner_decision closure implementation candidate wheel projection entry locators members limits amendment approved_inputs'), "MANIFEST_FIELDS")
    _check(manifest["schema"] == PACKAGE_SCHEMA
        and manifest["scope"] == SCOPE and manifest["rule"] == RULE
        and manifest["baseline"] == BASELINE and manifest["owner_decision"] == OWNER_DECISION
        and manifest["closure"] == CLOSURE and manifest["candidate"] == CANDIDATE
        and manifest["wheel"] == WHEEL and manifest["projection"] == PROJECTION
        and manifest["limits"] == PACKAGE_LIMITS, "MANIFEST_AUTHORITY")
    _check.exact(manifest["implementation"], ("commit", "tree"), "IMPLEMENTATION")
    _check.commit(manifest["implementation"]["commit"], "IMPLEMENTATION")
    _check.commit(manifest["implementation"]["tree"], "IMPLEMENTATION")
    _check(manifest["implementation"] != CLOSURE, "IMPLEMENTATION")
    _amendment(manifest["amendment"], manifest["implementation"])
    entry = manifest["entry"]
    _check.exact(entry, _fields('loader_path loader_bytes loader_sha256 bootstrap_path bootstrap_bytes bootstrap_sha256 dispatcher_path dispatcher_bytes dispatcher_sha256 carrier_argv_sha256 local_management_binding_sha256 writer'),
        "ENTRY_FIELDS")
    _validate_local_writer(entry["writer"])
    for key in ("carrier_argv_sha256", "local_management_binding_sha256"):
        _check.digest(entry[key], "ENTRY")
    _check(type(entry) is dict and entry.get("loader_path") == "field/loader.py"
        and entry.get("bootstrap_path") == "field/bootstrap.py"
        and entry.get("dispatcher_path") == "field/dispatcher.py"
        and hello["loader_sha256"] == entry.get("loader_sha256")
        and hello["bootstrap_sha256"] == entry.get("bootstrap_sha256"), "ENTRY")
    locators = _check.exact(manifest["locators"], _fields('schema observation_record_sha256 source_relation_sha256 state_parent quota_parent install_parent journal_parent evidence_parent ordinary_user ordinary_group user_manager_unit query_parent_unit controller_parent_unit management_parent_unit supervisor_parent_unit ordinary_parent_unit retained_ordinary_parent_path carrier_unit'), "LOCATOR_FIELDS")
    _check(locators["schema"] == "local-hand-q2-core-private-locators/v1"
        and locators["carrier_unit"] == carrier_name, "LOCATOR")
    _check.digest(locators["observation_record_sha256"], "LOCATOR")
    relation = {"schema": "local-hand-q2-core-locator-relation/v2",
        "local_management_binding_sha256": entry["local_management_binding_sha256"],
        "observation_record_sha256": locators["observation_record_sha256"],
        "locators": {key: item for key, item in locators.items()
            if key != "source_relation_sha256"}}
    _check(locators["source_relation_sha256"] == _sha(canonical(relation)), "LOCATOR_RELATION")
    members = context["members"]
    _envelope(type(manifest["members"]) is list and manifest["members"], "MEMBERS")
    paths = []
    for row in manifest["members"]:
        _envelope.exact(row, _fields('path role mode bytes sha256 origin'), "ROW")
        paths.append(_envelope.path(row["path"], "ROW"))
        _envelope.integer(row["bytes"], 0, MEMBER_LIMIT, "ROW")
        _envelope.digest(row["sha256"], "ROW")
        _envelope(type(row["mode"]) is int
            and ((row["role"] == "approved-inputs" and row["mode"] == 384)
                or (row["role"] in _fields('candidate-worktree candidate-git-metadata wheel projection field-code')
                    and row["mode"] in (420, 493))), "ROW")
    _envelope(len(paths) <= MEMBER_COUNT_LIMIT and len(set(paths)) == len(paths)
        and paths == sorted(paths, key=lambda item: item.encode("ascii")), "MEMBERS")
    _envelope(type(members) is dict and set(members) == {row["path"] for row in manifest["members"]},
        "MEMBERS")
    manifest_raw = canonical(manifest, newline=True)
    package_hash = hashlib.sha256()
    package_hash.update(PACKAGE_MAGIC)
    package_hash.update(struct.pack(">Q", len(manifest_raw)))
    package_hash.update(manifest_raw)
    package_bytes = len(PACKAGE_MAGIC) + 8 + len(manifest_raw)
    for row in manifest["members"]:
        raw = members[row["path"]]
        _envelope((type(raw) is bytes or (isinstance(raw, memoryview) and raw.readonly))
            and len(raw) == row["bytes"] and _sha(raw) == row["sha256"], "MEMBER")
        package_hash.update(raw)
        package_bytes += len(raw)
    _envelope(package_bytes == bind["package_bytes"]
        and package_hash.hexdigest() == bind["package_sha256"], "BINDING")
    _check(entry.get("dispatcher_bytes") == len(members["field/dispatcher.py"])
        and entry.get("dispatcher_sha256") == _sha(members["field/dispatcher.py"]), "ENTRY")
    for role in ("loader", "bootstrap", "dispatcher"):
        raw = members.get("field/" + role + ".py")
        _check(raw is not None and type(entry[role + "_bytes"]) is int
            and entry[role + "_bytes"] == len(raw)
            and entry[role + "_sha256"] == _sha(raw), "ENTRY")
    deadlines = _check.exact(context["guest_deadlines"],
        ("boot_id", "boottime_deadline_ns", "monotonic_deadline_ns"),
        "GUEST_DEADLINES")
    _check(deadlines["boot_id"] == hello["guest_boot_id"]
        and deadlines["boottime_deadline_ns"] == hello["guest_boottime_origin_ns"] + bind["guest_duration_ns"]
        and deadlines["monotonic_deadline_ns"] == hello["guest_monotonic_origin_ns"] + bind["guest_duration_ns"],
        "GUEST_DEADLINES")
    _check.integer(context["stdin_bytes_received"], 1, LIMITS["carrier_input_bytes"], "STDIN")
    expected_stdin = 8 + 8 + len(canonical(bind, newline=True)) + bind["package_bytes"]
    _check(context["stdin_bytes_received"] == expected_stdin, "STDIN")
    approved = _approved_inputs_envelope(context)
    policy = approved["policy_basis"]
    _remote(type(policy.get("remote_expectation")) is dict, "EXPECTATION")
    expected = policy["remote_expectation"]
    _remote.exact(expected, _fields('account home_path login_shell hello_schema parser_profile aliases remote_tokens_sha256 remote_command_sha256 remote_entity_preimages_stage'), "EXPECTATION")
    _remote(expected == {
        "account": "q1admin", "home_path": "/home/q1admin", "login_shell": "/bin/bash",
        "hello_schema": HELLO_SCHEMA, "parser_profile": "bash-noninteractive-c-v1",
        "aliases": REMOTE_ALIASES, "remote_tokens_sha256": remote["remote_tokens_sha256"],
        "remote_command_sha256": remote["remote_command_sha256"],
        "remote_entity_preimages_stage": "HELLO_JIT"}, "EXPECTATION")
    return context


def _validate_context(context):
    _validate_context_envelope(context)
    _validate_approved_components(_approved_inputs_envelope(context))
    _journal_transition_context(context)
    _consumption_info(context)
    return context


def _validate_local_writer(value):
    """Validate transported host bytes, never sample a guest substitute."""
    code = "CORE_DISPATCH_HOST_WRITER"
    _exact(value, _fields('schema user_namespace pid_namespace process uid gid supplementary_gids'), code)
    _require(value["schema"] == "local-hand-q2-core-local-writer/v1", code)
    for name in _fields('user_namespace pid_namespace process uid gid'):
        fields = ({"dev": 0, "ino": 1} if name.endswith("namespace") else
            {"pid": 1, "starttime_ticks": 0} if name == "process" else
            dict.fromkeys(_fields('real effective saved filesystem'), 0))
        _exact(value[name], fields, code)
        for key, minimum in fields.items():
            _integer(value[name][key], minimum, code=code)
        if name in ("uid", "gid"):
            _require(len(set(value[name].values())) == 1, code)
    groups = value["supplementary_gids"]
    _require(type(groups) is list, code)
    for item in groups:
        _integer(item, code=code)
    _require(groups == sorted(set(groups)), code)
    canonical(value, limit=4096)
    return value


def _consumption_info(context):
    """Rebuild marker v2 from v3 inputs; this is not host persistence proof."""
    manifest, bind = context["manifest"], context["bind"]
    _check(manifest["schema"] == PACKAGE_SCHEMA, "MANIFEST_AUTHORITY")
    entry = manifest["entry"]
    writer = _validate_local_writer(entry["writer"])
    marker = {"schema": "local-hand-q2-core-carrier-consumption/v2",
        "scope": SCOPE, "session_id": SESSION,
        **{key: manifest[key] for key in _fields('baseline owner_decision closure implementation amendment candidate')},
        "package": {"basename": bind["package_basename"], "bytes": bind["package_bytes"],
            "sha256": bind["package_sha256"],
            "manifest_sha256": _sha(canonical(manifest, newline=True))},
        "approved_inputs_sha256": manifest["approved_inputs"]["sha256"],
        "local_management_binding_sha256": entry["local_management_binding_sha256"],
        "writer": writer, "carrier_argv_sha256": entry["carrier_argv_sha256"],
        **{key: bind[key] for key in _fields('host_boottime_origin_ns host_monotonic_origin_ns host_boottime_deadline_ns host_monotonic_deadline_ns')},
        "state": "CONSUMPTION_RECORD_COMPLETE"}
    raw = canonical(marker, newline=True, limit=16384)
    _check(_sha(raw) == bind["consumption_sha256"], "CONSUMPTION_BINDING")
    return {"basename": ".lhqcore-20261007a.carrier-consumed.json", "bytes": len(raw),
        "sha256": _sha(raw), "state": marker["state"]}


def field_readiness():
    """Inert readiness report: distinguish missing input bindings from D code gaps."""
    return {
        "schema": "local-hand-q2-core-field-readiness/v1",
        "scope": SCOPE,
        "releasable": not (UNBOUND_APPROVED_INPUTS or UNIMPLEMENTED_FIELD_EFFECTS),
        "unbound_approved_inputs": list(UNBOUND_APPROVED_INPUTS),
        "protocol_blockers": [],
        "unimplemented_effects": list(UNIMPLEMENTED_FIELD_EFFECTS),
    }


def _git_blob(raw):
    _package(type(raw) is bytes, "BYTES")
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _projection_path(name):
    if type(name) is not str:
        return False
    path = PurePosixPath(name)
    module = re.fullmatch(
        r"tools/(?:admin/(?:local_hand_quota_observer|local_hand_system_manager)|"
        r"local_hand|local_hand_connect|local_hand_jobs|local_hand_mcp)/"
        r"[a-z_][a-z0-9_]*\.py", name)
    return (not path.is_absolute() and path.as_posix() == name
        and all(part not in ("", ".", "..") for part in path.parts)
        and (name in PROJECTION_HARNESS or module is not None)) \
        and "namespace" not in name.lower() and "watchdog" not in name.lower()


def _json_object(raw, code):
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_pairs,
            parse_constant=_nonfinite)
    except DispatchError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DispatchError(code) from error
    _shape(value)
    return value


def _wheel_payload(raw, source_files):
    """Verify the exact wheel and its source/payload binding in memory."""
    _wheel(type(raw) is bytes and len(raw) == WHEEL["bytes"]
        and _sha(raw) == WHEEL["sha256"], "PIN")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            _wheel(1 <= len(names) <= 1024 and len(names) == len(set(names))
                and sum(item.file_size for item in infos) <= 32 * 1024 * 1024, "INVENTORY")
            for item in infos:
                path = PurePosixPath(item.filename)
                file_type = stat.S_IFMT(item.external_attr >> 16)
                _wheel(not item.is_dir() and not path.is_absolute()
                    and path.as_posix() == item.filename
                    and all(part not in ("", ".", "..") for part in path.parts)
                    and item.file_size <= MEMBER_LIMIT
                    and file_type in (0, stat.S_IFREG), "ENTRY")
            content = {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise _wheel.error("ARCHIVE") from error
    metadata = _json_object(content.get(WHEEL_METADATA, b""), "CORE_EFFECT_WHEEL_METADATA")
    _wheel.exact(metadata, _fields('schema_version product_version source_commit artifact_kind files'), "METADATA")
    _wheel(metadata["schema_version"] == "infra-local-hand-build/v1"
        and metadata["product_version"] == "0.2.0a1"
        and metadata["source_commit"] == CANDIDATE["commit"]
        and metadata["artifact_kind"] == "wheel", "METADATA")
    package_pattern = r"tools/(?:(?:" + "|".join(WHEEL_PACKAGES) + \
        r"))/[a-z_][a-z0-9_]*\.(?:py|sh|ps1)"
    expected = {name[6:]: digest for name, digest in source_files.items()
        if re.fullmatch(package_pattern, name)}
    _wheel(metadata["files"] == expected
        and all(package + "/__init__.py" in expected for package in WHEEL_PACKAGES), "SOURCE")
    for name, digest in expected.items():
        _wheel(name in content and _sha(content[name]) == digest, "PAYLOAD")
    dist = "infra_local_hand-0.2.0a1.dist-info/"
    extras = set(content) - set(expected) - {WHEEL_METADATA}
    _wheel(extras and all(name.startswith(dist)
            and len(PurePosixPath(name).parts) == 2 for name in extras)
        and {dist + name for name in ("METADATA", "WHEEL", "RECORD")} <= extras, "EXTRAS")
    _wheel(b"Name: infra-local-hand\n" in content[dist + "METADATA"]
        and b"Version: 0.2.0a1\n" in content[dist + "METADATA"]
        and b"Root-Is-Purelib: true\n" in content[dist + "WHEEL"], "DISTRIBUTION")
    try:
        rows = list(csv.reader(io.StringIO(content[dist + "RECORD"].decode("utf-8", "strict"))))
    except (UnicodeError, csv.Error) as error:
        raise _wheel.error("RECORD") from error
    _wheel(len(rows) == len(content) and all(len(row) == 3 for row in rows)
        and len({row[0] for row in rows}) == len(rows)
        and {row[0] for row in rows} == set(content), "RECORD")
    for name, digest, size in rows:
        if name == dist + "RECORD":
            _wheel(digest == size == "", "RECORD")
        else:
            actual = base64.urlsafe_b64encode(hashlib.sha256(content[name]).digest()) \
                .rstrip(b"=").decode("ascii")
            _wheel(digest == "sha256=" + actual and size == str(len(content[name])), "RECORD")
    payload = _sha(json.dumps({"schema_version": "infra-local-hand-full-payload/v1",
                "files": expected}, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True).encode("ascii"))
    _wheel(payload == WHEEL["payload_digest"], "PAYLOAD_DIGEST")
    return {"files": expected, "payload_digest": payload, "content": content}


def verify_install_inputs(context):
    """RAM-only P5 input verification; no effects or live-readiness claim."""
    manifest, members = context["manifest"], context["members"]
    if manifest.get("schema") == PACKAGE_SCHEMA:
        _approved_inputs_envelope(context)
    rows = manifest["members"]
    _package(type(rows) is list and rows
        and [row.get("path") for row in rows]
        == sorted((row.get("path") for row in rows), key=lambda item: item.encode("ascii")),
        "ORDER")
    source_files = {}
    helper_digests = {}
    wheel_raw = projection_raw = None
    for row in rows:
        _package.exact(row, _fields('path role mode bytes sha256 origin'), "ROW")
        path = _package.path(row["path"], "PATH")
        _package((row["role"] == "approved-inputs" and row["mode"] == 384
                and path == APPROVED_INPUTS_PATH and manifest.get("schema") == PACKAGE_SCHEMA)
            or (row["mode"] in (420, 493) and row["role"] in _fields('candidate-worktree candidate-git-metadata wheel projection field-code')),
            "ROW")
        view = members.get(path)
        _package(type(view) is bytes or (isinstance(view, memoryview) and view.readonly), "MEMBER")
        raw = bytes(view)
        _package(len(raw) == row["bytes"] and _sha(raw) == row["sha256"], "MEMBER")
        origin = row["origin"]
        if row["role"] == "approved-inputs":
            # The envelope check above validates its exact descriptor/origin.
            # Private approved facts never become installation/projection input.
            continue
        if row["role"] == "candidate-worktree":
            _package.exact(origin, _fields('kind commit path blob'), "ORIGIN")
            name = _package.path(origin["path"], "ORIGIN")
            _package(origin["kind"] == "candidate-blob"
                and origin["commit"] == CANDIDATE["commit"]
                and path == "candidate/" + name
                and origin["blob"] == _git_blob(raw)
                and name not in source_files, "ORIGIN")
            source_files[name] = row["sha256"]
            if name in {"tests/e3_host/" + item + ".py" for item in PREPARATION_HELPERS}:
                helper_digests[name.rsplit("/", 1)[-1][:-3]] = row["sha256"]
        elif row["role"] == "candidate-git-metadata":
            _package.exact(origin, ("kind", "commit", "git_path"), "ORIGIN")
            name = _package.path(origin["git_path"], "ORIGIN")
            _package(origin["kind"] == "candidate-git-metadata"
                and origin["commit"] == CANDIDATE["commit"]
                and name.startswith(".git/") and path == "candidate/" + name, "ORIGIN")
        elif row["role"] in ("wheel", "projection"):
            _package.exact(origin, ("kind", "basename", "sha256"), "ORIGIN")
            expected = WHEEL if row["role"] == "wheel" else PROJECTION
            _package(origin == {"kind": row["role"], "basename": expected["basename"],
                    "sha256": expected["sha256"]}, "ORIGIN")
            if row["role"] == "wheel":
                _package(wheel_raw is None, "ARTIFACT")
                wheel_raw = raw
            else:
                _package(projection_raw is None, "ARTIFACT")
                projection_raw = raw
        else:
            _package.exact(origin, _fields('kind commit path blob'), "ORIGIN")
            _package(origin["kind"] == "implementation-blob"
                and origin["commit"] == manifest["implementation"]["commit"]
                and origin["blob"] == _git_blob(raw), "ORIGIN")
    _package(set(helper_digests) == set(PREPARATION_HELPERS)
        and wheel_raw is not None and projection_raw is not None, "REQUIRED")
    projection = document(projection_raw, limit=MEMBER_LIMIT, newline=True)
    _effect.exact(projection, _fields('schema source_commit source_tree files'), "PROJECTION")
    _effect(projection["schema"] == "local-hand-q2-source-projection/v1"
        and projection["source_commit"] == CANDIDATE["commit"]
        and projection["source_tree"] == CANDIDATE["tree"]
        and type(projection["files"]) is dict
        and len(projection["files"]) == PROJECTION["file_count"], "PROJECTION")
    for name, item in projection["files"].items():
        _projection(_projection_path(name), "PATH")
        _projection.exact(item, ("mode", "sha256"), "ENTRY")
        _projection(item["mode"] in (420, 493) and source_files.get(name) == item["sha256"],
            "ENTRY")
    _projection(PROJECTION_REQUIRED <= set(projection["files"]), "REQUIRED")
    wheel = _wheel_payload(wheel_raw, source_files)
    return {"source_files": source_files, "projection": projection,
        "wheel_files": wheel["files"], "payload_digest": wheel["payload_digest"],
        "helper_digests": helper_digests,
        "members_sha256": _sha(canonical(rows))}


def _prep_require(condition, code):
    _require(condition, "CORE_EFFECT_PREPARATION_" + code)


def _prep_guard(effects, deadline):
    outer = effects.context["guest_deadlines"]
    active = getattr(effects, "_active_case_deadlines", {})
    pairs = {active.get("preparation_deadline_ns"): active.get("preparation_monotonic_deadline_ns"),
        active.get("owner_deadline_ns"): active.get("owner_monotonic_deadline_ns"),
        active.get("remote_final_deadline_ns"): active.get("remote_final_monotonic_deadline_ns"),
        outer["boottime_deadline_ns"]: outer["monotonic_deadline_ns"]}
    mono = pairs.get(deadline)
    _prep_require(type(mono) is int and deadline <= outer["boottime_deadline_ns"]
        and mono <= outer["monotonic_deadline_ns"], 'CLOCK_BINDING')
    # Original per-case clocks survive suspend; an outer-offset recalculation
    # could incorrectly extend the case's monotonic deadline.
    return _clock(effects, {"boot_id": outer["boot_id"],
        "boottime_deadline_ns": deadline, "monotonic_deadline_ns": mono})


def _prep_settings(case, expires_at):
    b = _budget(case["phases"])
    identity = dict(_identity(case), expires_at=expires_at)
    controllers = {}
    for role in ("target", "supervisor"):
        v = b[role]
        controllers[role] = {"unit": case["controller_prefix"] + "-" + role + ".service",
            "runtime_max_usec": v["runtime_seconds"] * 10**6,
            "timeout_stop_usec": v["stop_seconds"] * 10**6,
            "memory_bytes": v["memory_bytes"], "tasks_max": v["tasks_max"],
            "cpu_quota_per_sec_usec": v["cpu_quota_per_sec_usec"],
            "limit_cpu_seconds": v["runtime_seconds"],
            "storage_bytes": v["storage_bytes"], "storage_inodes": v["storage_inodes"]}
    m = b["management"]
    settings = {"identity": identity, "original_budgets": b["operation"],
        "limits": {"max_queued": 1, "max_running": 1, "retained_bytes": 8388608,
            "ledger_emergency_bytes": 65536, "requests_per_minute": 1},
        "controllers": controllers,
        "management": {"receive_ns": NS, "stop_ns": NS, "storage_bytes": 1048576,
            "storage_inodes": 64, "accept_ns": NS, "max_connections": 4,
            "stages": {v["stage"]: {"cpu_ns": v["cpu_seconds"] * NS,
                "memory_bytes": v["memory_bytes"], "pids": v["tasks_max"],
                "output_bytes": v["output_bytes"], "runtime_ns": v["runtime_seconds"] * NS}
                for v in m["stages"]}},
        "capacity_management": {"storage_bytes": m["storage_bytes"],
            "storage_inodes": m["storage_inodes"], "cpu_ns": m["cpu_seconds"] * NS,
            "memory_bytes": m["memory_bytes"], "pids": m["pids"],
            "output_bytes": m["output_bytes"]},
        "owner": {"runtime_ns": OWNER_NS, "cpu_ns": b["owner"]["cpu_seconds"] * NS,
            "memory_bytes": b["owner"]["memory_bytes"], "pids": b["owner"]["tasks_max"],
            "storage_bytes": b["owner"]["storage_bytes"],
            "storage_inodes": b["owner"]["storage_inodes"],
            "output_bytes": b["owner"]["output_bytes"]}}
    if case["index"] != 2:
        settings["schema"] = "local-hand-q2-system-preparation-settings/v1"
    return settings


def _prep_pin(value):
    return {"path": value["path"], "device": value.get("device", value.get("dev")),
        "inode": value.get("inode", value.get("ino"))}


def _prep_make_plan(effects, case, expires_at):
    admission = effects._admission
    detail = getattr(effects, "_admission_detail", None)
    _prep_require(type(detail) is dict and {"quota_mount", "quota_inventory", "retained_before"}
        <= set(detail), 'CURRENT_FACTS_REQUIRED')
    _prep_require(case["index"] == 2 or type(detail.get("system_geometry")) is dict,
        'GEOMETRY_REQUIRED')
    paths = effects.preparation_paths(case, effects.context["manifest"]["locators"])
    guest = admission["guest"]
    retained = _approved_inputs_envelope(effects.context)["retained_preparation"]
    plan = {"schema": "local-hand-q2-system-preparation-plan/v1" if case["index"] != 2
        else "local-hand-q2-core-preparation-plan/v1",
        "purpose": "ISOLATED_Q2_CORE_PREPARATION", "scope": SCOPE,
        "baseline": BASELINE["commit"], "preparation_id": case["preparation_id"],
        "host": {key: guest[key] for key in _fields('hostname dmi_vendor dmi_product boot_id')},
        "account": {"name": guest["ordinary_user"], "uid": guest["ordinary_uid"],
            "gid": guest["ordinary_gid"]},
        "directories": {role: {"path": row["path"], "owner": row["owner"],
            "mode": row["mode"], "filesystem": row["parent_role"]}
            for role, row in paths["directories"].items()},
        "roots": paths["roots"], "candidate": copy.deepcopy(effects._installation_receipt["source"]),
        "retained": copy.deepcopy(retained["paths"]),
        "retained_domains": copy.deepcopy(retained["domains"]),
        "mounts": {"quota": copy.deepcopy(detail["quota_mount"])},
        "tools": {key: {"path": val["path"], "sha256": val["sha256"]}
            for key, val in admission["programs"].items()},
        "settings": _prep_settings(case, expires_at)}
    plan["host"]["initial_userns"] = {"device": guest["initial_userns"]["dev"],
        "inode": guest["initial_userns"]["ino"]}
    if case["index"] != 2:
        plan["retained_ordinary_parent"] = _prep_pin(admission["parents"]["retained_ordinary_cgroup"])
        plan["retained_ordinary_parent"]["path"] = plan["retained_ordinary_parent"]["path"].removeprefix("/sys/fs/cgroup")
    return plan


def _prep_translate(case, plan, receipt, children, helpers):
    """The original candidate constructor is authoritative; only schema changes."""
    driver, assembly = helpers["q2_prepare_driver"], helpers["q2_prepare_assembly"]
    _prep_require(case in CASES and plan["scope"] == SCOPE and plan["baseline"] == BASELINE["commit"]
        and plan["preparation_id"] == case["preparation_id"], 'SCOPE')
    _effect.exact(receipt, _fields('schema preparation_id plan_sha256 status reason facts q2_accepted q3_accepted production_supported fixture_generated'),
        'PREPARATION_RESULT')
    _prep_require(receipt["schema"] == "local-hand-q2-fixture-preparation/v1"
        and receipt["preparation_id"] == case["preparation_id"]
        and receipt["plan_sha256"] == _sha(driver.encoded(plan))
        and receipt["status"] == "RESOURCES_PREPARED" and receipt["reason"] is None
        and all(receipt[key] is False for key in
            _fields('q2_accepted q3_accepted production_supported fixture_generated')),
        'RESULT')
    observed = receipt["facts"]
    _prep_require(observed["retained_before"] == observed["retained_after"],
        'RETAINED_CHANGED')
    authority = {"schema": "local-hand-q2-preparation-authority/v1", "scope": SCOPE,
        "baseline": BASELINE["commit"], "plan_sha256": receipt["plan_sha256"],
        "preparation_id": case["preparation_id"], "receipt_sha256": _sha(driver.encoded(receipt))}
    original, bound, manifest = driver.facts_from_observed(plan, observed, children, authority)
    _prep_require(bound == authority, 'AUTHORITY_CHANGED')
    facts = copy.deepcopy(original)
    schemas = {1: "local-hand-q2-system-assembly-facts/v1",
        2: "local-hand-q4-cancel-assembly-facts/v1", 3: "local-hand-q4-h11-assembly-facts/v1"}
    _prep_require(original["schema"] == ("local-hand-q2-assembly-facts/v1" if case["index"] == 2
            else "local-hand-q2-system-assembly-facts/v1"), 'SCHEMA')
    facts["schema"] = schemas[case["index"]]
    assembled = assembly.assemble(facts)
    return {"facts": facts, "authority": authority, "manifest": manifest, "assembled": assembled}


class _PrepIO:
    """Guard each syscall; retain late-opened fds for release, never retry I/O."""
    def __init__(self, effects, deadline):
        self.effects, self.deadline, self.fds = effects, deadline, []

    def call(self, function, *args, **kwargs):
        return _guard_call(partial(_prep_guard, self.effects, self.deadline),
            function, *args, **kwargs)

    def mutate(self, path, function, *args, **kwargs):
        return _accounting_io(getattr(self.effects, '_pool_accounting', None),
            partial(_prep_guard, self.effects, self.deadline), path, function, *args, **kwargs)

    def open(self, *args, accounting_path=None, **kwargs):
        if len(args) > 1 and args[1] & os.O_CREAT:
            _prep_require(accounting_path is not None, 'ACCOUNTING_PATH')
            fd = self.mutate(accounting_path, os.open, *args, create=True, release=os.close, **kwargs)
        else:
            fd = _guard_call(partial(_prep_guard, self.effects, self.deadline),
                os.open, *args, release=os.close, **kwargs)
        self.fds.append(fd)
        return fd

    def directory(self, path):
        FieldEffects._absolute(path, "CORE_EFFECT_PREPARATION_PATH")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = self.open("/", flags)
        for part in PurePosixPath(path).parts[1:]:
            child = self.open(part, flags, dir_fd=fd)
            self.fds.remove(fd)
            os.close(fd)
            fd = child
        return fd

    def __enter__(self):
        return self

    def __exit__(self, *_):
        for fd in reversed(self.fds):
            os.close(fd)


def _prep_directory(effects, path, uid, gid, mode, deadline):
    with _PrepIO(effects, deadline) as io:
        parent = io.directory(str(PurePosixPath(path).parent))
        name = PurePosixPath(path).name
        io.mutate(path, os.mkdir, name, mode, dir_fd=parent, create=True)
        fd = io.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent)
        io.call(os.fchown, fd, uid, gid)
        io.call(os.fchmod, fd, mode)
        io.mutate(path, os.fsync, fd)
        io.mutate(path, os.fsync, parent)
        info = io.call(os.fstat, fd)
        named = io.call(os.stat, name, dir_fd=parent, follow_symlinks=False)
        _prep_require((info.st_dev, info.st_ino) == (named.st_dev, named.st_ino)
            and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, mode),
            'DIRECTORY_OWNER')
        return {"path": path, "device": info.st_dev, "inode": info.st_ino,
            "uid": uid, "gid": gid, "mode": info.st_mode}


def _prep_file(effects, path, raw, deadline, *, uid=0, gid=0):
    _prep_require(type(raw) is bytes and len(raw) <= MEMBER_LIMIT,
        'FILE_LIMIT')
    with _PrepIO(effects, deadline) as io:
        parent = io.directory(str(PurePosixPath(path).parent))
        name = PurePosixPath(path).name
        fd = io.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NOATIME,
            0o600, dir_fd=parent, accounting_path=path)
        io.call(os.fchown, fd, uid, gid)
        io.call(os.fchmod, fd, 0o600)
        view = memoryview(raw)
        while view:
            part = view[:65536]
            count = io.mutate(path, os.write, fd, part, write=True, requested_bytes=len(part))
            _prep_require(count > 0, 'SHORT_WRITE')
            view = view[count:]
        io.mutate(path, os.fsync, fd)
        io.mutate(path, os.fsync, parent)
        info = io.call(os.fstat, fd)
        reread = io.call(os.pread, fd, len(raw) + 1, 0)
        _prep_require(reread == raw and info.st_nlink == 1 and stat.S_ISREG(info.st_mode)
            and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (uid, gid, 384),
            'FILE')
        identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        named = io.call(os.stat, name, dir_fd=parent, follow_symlinks=False)
        _prep_require((named.st_dev, named.st_ino, named.st_size, named.st_mtime_ns, named.st_ctime_ns)
            == identity, 'SOURCE_CHANGED')
        result = {"path": path, "fd": fd, "identity": identity, "raw": raw,
            "uid": uid, "gid": gid}
        effects.held.append(fd)
        io.fds.remove(fd)
        return result


def _prep_reread(effects, record, deadline):
    with _PrepIO(effects, deadline) as io:
        before = io.call(os.fstat, record["fd"])
        raw = io.call(os.pread, record["fd"], len(record["raw"]) + 1, 0)
        parent = io.directory(str(PurePosixPath(record["path"]).parent))
        named = io.call(os.stat, PurePosixPath(record["path"]).name,
            dir_fd=parent, follow_symlinks=False)
        after = io.call(os.fstat, record["fd"])
        for info in (before, named, after):
            _prep_require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                == record["identity"] and info.st_nlink == 1 and stat.S_ISREG(info.st_mode)
                and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
                == (record["uid"], record["gid"], 384) and raw == record["raw"],
                'SOURCE_CHANGED')
        return raw


def _prep_quota(source, command, project, values=None):
    """Share the verified read ABI; this mutator accepts only fixed new limits."""
    _prep_require(command in (0x800007, 0x800008), 'QUOTA_ABI')
    if command == 0x800008:
        _prep_require(project in {i for c in CASES for i in c["project_ids"]}
            and values == {"hard": 1024, "ihard": 128, "valid": 5},
            'QUOTA_MUTATION')
    quota = _CapQuota(source)
    if command == 0x800007:
        _prep_require(values is None, 'QUOTA_MUTATION')
        return quota.block(project)
    block = quota.Block()
    for key, value in values.items(): setattr(block, key, value)
    quota.ct.set_errno(0)
    if quota.lib.quotactl(quota.ct.c_int((command << 8) | 2), quota.device,
        quota.ct.c_int(project), quota.ct.byref(block)):
        raise OSError(quota.ct.get_errno(), "core project quota operation")
    return {name: getattr(block, name) for name, _ in block._fields_}


def _prep_quota_retained(rows):
    result = copy.deepcopy(rows)
    for row in result:
        # Ordinary unassigned directories are charged to project zero before
        # assignment. Only that unconstrained domain's own usage may advance;
        # all configured limits and every nonzero historical row stay exact.
        if row["project"] == 0 and all(row[key] == 0 for key in _fields('hard soft ihard isoft')):
            row["space"] = row["inodes"] = 0
    return result


def _prep_root(effects, planned, account, mount, deadline):
    import errno
    import fcntl
    project = planned["project_id"]
    _prep_require(project in {i for c in CASES for i in c["project_ids"]}
        and planned["hard_bytes"] == 1048576 and planned["inode_hard_limit"] == 128,
        'QUOTA_MUTATION')
    with _PrepIO(effects, deadline) as io:
        try:
            old = io.call(_prep_quota, mount["source"], 0x800007, project)
        except OSError as error:
            if error.errno != errno.ESRCH: raise
            old = {}
        _prep_require(all(v == 0 for k, v in old.items() if k not in ("valid", "project")),
            'PROJECT_EXISTS')
        created = _prep_directory(effects, planned["path"], account["uid"], account["gid"], 448, deadline)
        fd = io.directory(planned["path"])
        values = list(struct.unpack("=IIIII8s", io.call(fcntl.ioctl, fd, 0x801c581f, bytes(28))))
        _prep_require(values[3] == 0, 'INHERITED_PROJECT')
        values[0] |= 512
        values[3] = project
        io.call(fcntl.ioctl, fd, 0x401c5820, struct.pack("=IIIII8s", *values))
        assigned = io.call(_prep_quota, mount["source"], 0x800007, project)
        _prep_require(assigned["inodes"] == 1 and all(assigned[k] == 0 for k in
                _fields('hard soft ihard isoft btime itime')),
            'PROJECT_ASSIGNMENT')
        io.call(_prep_quota, mount["source"], 0x800008, project,
            {"hard": 1024, "ihard": 128, "valid": 5})
        io.mutate(planned['path'], os.fsync, fd)
        flags, _, _, actual, _, _ = struct.unpack("=IIIII8s", io.call(fcntl.ioctl, fd, 0x801c581f, bytes(28)))
        quota = io.call(_prep_quota, mount["source"], 0x800007, project)
        for info in (io.call(os.fstat, fd), io.call(os.stat, planned["path"], follow_symlinks=False)):
            _prep_require((info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode)
                == tuple(created[k] for k in _fields('device inode uid gid mode')),
                'ROOT_CHANGED')
        _prep_require(actual == project and flags & 512 and quota["valid"] & 5 == 5
            and quota["hard"] == 1024 and quota["ihard"] == 128
            and io.call(effects._capacity_quota_enforcement,
                guard=partial(_prep_guard, effects, deadline)) & 48 == 48,
            'QUOTA_ENFORCEMENT')
        return dict(planned, **{k: v for k, v in created.items() if k != "path"},
            filesystem="ext4", filesystem_uuid=mount["uuid"], xflags=flags,
            accounting=True, enforcement=True, identity_unchanged=True)


def _prep_initialize(effects, prepared, deadline):
    facts, assembled = prepared["facts"], prepared["assembled"]
    uid, gid = facts["ordinary"]["uid"], facts["ordinary"]["gid"]
    policy = canonical(assembled["policy"], newline=True)
    sources = prepared["source_objects"]
    sources["policy"] = _prep_file(effects, facts["paths"]["policy"], policy, deadline, uid=uid, gid=gid)
    authority = {"authority_id": facts["identity"]["authority_id"],
        "ledger_id": facts["identity"]["ledger_id"], "state_root": facts["paths"]["broker_root"]}
    sources["authority"] = _prep_file(effects, facts["paths"]["authority_root"] + "/authority.json",
        canonical(authority, newline=True), deadline, uid=uid, gid=gid)
    name = "tests/e3_host/q2_prepare_assembly.py"
    # Execute the fixed projected constructor as the ordinary identity, not
    # its CLI (which would require the deliberately unprojected contract).
    program = """import hashlib,importlib.util,json,os,stat,sys
source,expected,policy,digest,ledger,tools,installed=sys.argv[1:]
def read(path,limit,owner,digest):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  before=os.fstat(fd); raw=os.read(fd,limit+1); after=os.fstat(fd)
  assert all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
  assert stat.S_ISREG(after.st_mode) and after.st_nlink==1
  assert after.st_uid==owner and not after.st_mode&18
  assert path!=policy or (stat.S_IMODE(after.st_mode)==384 and after.st_gid==os.getgid())
  assert len(raw)<=limit and hashlib.sha256(raw).hexdigest()==digest
  return raw
 finally: os.close(fd)
raw=read(source,262144,0,expected)
payload=read(policy,65536,os.getuid(),digest)
sys.path[:0]=[installed,tools]
module=importlib.util.module_from_spec(importlib.util.spec_from_file_location('_core_ledger',source))
exec(compile(raw,source,'exec'),module.__dict__)
value=module.initialize_ledger(json.loads(payload),ledger)
print(json.dumps(value,sort_keys=True,separators=(',',':')))
"""
    argv = [facts["setpriv"]["path"], "--reuid=" + str(uid), "--regid=" + str(gid),
        "--clear-groups", "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all",
        "--no-new-privs", facts["installation"]["programs"]["python"]["path"], "-I", "-B", "-c",
        program, facts["source"]["root"] + "/" + name, facts["source"]["files"][name],
        facts["paths"]["policy"], _sha(policy), facts["identity"]["ledger_id"],
        facts["source"]["root"] + "/tools", facts["installation"]["package_root"]]
    original = effects._effect_guard
    def guard():
        _prep_guard(effects, deadline)
        return original()
    effects._effect_guard = guard
    try:
        ledger = document(effects._installation_command(argv), limit=32768)
    finally:
        effects._effect_guard = original
    _effect.exact(ledger, _fields('path device inode uid mode ledger_id generation'),
        'PREPARATION_LEDGER')
    _prep_require(ledger["path"] == facts["paths"]["broker_root"] + "/jobs.sqlite"
        and ledger["uid"] == uid and ledger["mode"] == 384
        and ledger["ledger_id"] == facts["identity"]["ledger_id"]
        and ledger["generation"] == assembled["chain"]["broker_generation"],
        'LEDGER')
    with _PrepIO(effects, deadline) as io:
        info = io.call(os.stat, ledger["path"], follow_symlinks=False)
        _prep_require((info.st_dev, info.st_ino, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
            == (ledger["device"], ledger["inode"], uid, gid, 384)
            and stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
            'LEDGER')
    result = dict(schema="local-hand-q2-preparation-result/v1", status="PREPARED",
        source_commit=facts["source"]["commit"], preparation_id=prepared["case"]["preparation_id"],
        policy={"path": facts["paths"]["policy"], "sha256": _sha(policy)}, ledger=ledger,
        authority_sha256=_sha(canonical(prepared["authority"], newline=True)),
        manifest_sha256=_sha(canonical(prepared["manifest"], newline=True)),
        q2_accepted=False, q3_accepted=False, production_supported=False)
    _prep_file(effects, prepared["paths"]["reservation"] + "/prepared.json",
        canonical(result, newline=True), deadline)
    prepared["prepared_result"] = result


def _plan_from_prepared(case, prepared, deadlines):
    facts, assembled = prepared["facts"], prepared["assembled"]
    identity = facts["identity"]
    _effect(all(identity.get(key) == val for key, val in _identity(case).items()),
        'PLAN_IDENTITY')
    by_project = {root["project_id"]: root for root in prepared["receipt"]["facts"]["roots"]}
    wrappers = []
    for planned in _planned_roots(case):
        root = by_project.get(planned["project_id"])
        _effect(root is not None, 'PLAN_ROOT')
        observed = {key: root[key] for key in _fields('path role device inode uid gid mode filesystem filesystem_uuid project_id xflags hard_bytes accounting enforcement identity_unchanged')}
        actual = next(r for r in prepared["plan"]["roots"] if r["project_id"] == planned["project_id"])
        _effect(observed["path"] == actual["path"], 'PLAN_ROOT_PATH')
        # The case-plan's path is relative; the preparation preimage retains the
        # matching absolute root. No observed identity/quota field is replaced.
        observed["path"] = planned["path"]
        observed["hard_inodes"] = root["inode_hard_limit"]
        wrappers.append({"ref": planned["ref"], "slot": planned["slot"],
                "planned": planned, "observed": observed})
    ledger_path = facts["paths"]["broker_root"] + "/jobs.sqlite"
    plan = {"schema": PLAN_SCHEMA, **{k: build_intent(case)[k] for k in
        _fields('session_id index case_id kind predecessor preparation_id operation_id budgets')},
        "identity": copy.deepcopy(identity), "principal": copy.deepcopy(assembled["resident"]["principal"]),
        "authority_path": facts["paths"]["authority_root"] + "/authority.json", "ledger_path": ledger_path,
        "request": copy.deepcopy(assembled["resident"]["request"]), "roots": wrappers,
        "controllers": copy.deepcopy(facts["controllers"]),
        "system_geometry": copy.deepcopy(facts.get("system_geometry")),
        "phases": _phase_units(case["operation_id"], case["phases"]),
        "empty_ledger_expectation": {"ledger_path": ledger_path, "authority_id": identity["authority_id"],
            "ledger_id": identity["ledger_id"], "expected_operations": 0, "expected_events": 0,
            "expected_leases": 0, "expected_sidecars": []}, "deadlines": dict(deadlines)}
    return validate_plan(case, build_intent(case), plan, deadlines)


class _CapQuota:
    """The candidate's bounded Linux project quota observation UAPI only."""
    def __init__(self, source):
        import ctypes
        import platform
        _cap(platform.system() == 'Linux' and platform.machine() == 'x86_64',
            'QUOTA_ABI')
        self.ct = ctypes
        class Block(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                _fields('hard soft space ihard isoft inodes btime itime')]
            _fields_ += [('valid', ctypes.c_uint32), ('project', ctypes.c_uint32)]
        self.Block = Block
        _cap(ctypes.sizeof(Block) == 72, 'QUOTA_ABI')
        self.lib = ctypes.CDLL(None, use_errno=True)
        self.lib.quotactl.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        self.lib.quotactl.restype = ctypes.c_int
        self.device = os.fsencode(source)

    def call(self, command, project, buffer):
        _cap(command in (0x800007, 0x800009, (ord('X') << 8) | 8), 'QUOTA_READ_ONLY')
        self.ct.set_errno(0)
        if self.lib.quotactl(self.ct.c_int((command << 8) | 2), self.device,
            self.ct.c_int(project), self.ct.byref(buffer)):
            raise OSError(self.ct.get_errno(), 'quota observation failed')

    def block(self, project):
        value = self.Block(); self.call(0x800007, project, value)
        return {key: getattr(value, key) for key, _ in value._fields_ if key != 'project'}

    def unused(self, project):
        import errno
        try:
            value = self.block(project)
        except OSError as error:
            if error.errno == errno.ESRCH:
                return
            raise
        _cap(all(number == 0 for key, number in value.items() if key != 'valid'),
            'PROJECT_OCCUPIED')

    def inventory(self, guard):
        import errno
        rows = []; start = 0
        for _ in range(128):
            value = self.Block()
            try:
                _guard_call(guard, self.call, 0x800009, start, value)
            except OSError as error:
                if error.errno == errno.ENOENT:
                    return rows
                raise
            _cap(start <= value.project < 2**32 - 1, 'QUOTA_ORDER')
            rows.append({key: getattr(value, key) for key, _ in value._fields_})
            start = value.project + 1
        raise _cap.error('QUOTA_INVENTORY_LIMIT')

    def enforcement(self):
        buffer = self.ct.create_string_buffer(160); buffer[0] = b'\x01'
        self.call((ord('X') << 8) | 8, 0, buffer)
        raw = bytes(buffer); flags = int.from_bytes(raw[2:4], 'little')
        _cap(raw[0] == 1 and flags & 48 == 48, 'QUOTA_ENFORCEMENT')
        return flags


def _capacity_stat(info):
    return tuple(getattr(info, key) for key in _fields(
        'st_dev st_ino st_mode st_uid st_gid st_nlink st_size st_mtime_ns st_ctime_ns'))


def _cap_same(before, after):
    _cap(_capacity_stat(before) == _capacity_stat(after)
        and before.st_atime_ns == after.st_atime_ns, 'RETAINED_DRIFT')


def _guard_call(guard, function, /, *args, release=None, **kwargs):
    """Reject late returns; this cannot interrupt a blocking kernel call."""
    if guard is not None: guard()
    try:
        value = function(*args, **kwargs)
    except BaseException:
        if guard is not None: guard()
        raise
    try:
        if guard is not None: guard()
    except BaseException:
        if release is not None: release(value)
        raise
    return value


def _accounting_observe(accounting, guard, boundary, pool_ids=None):
    """Run the observer under the caller's unchanged preparation/owner clocks."""
    if accounting is None:
        return
    try:
        if guard is not None: guard()
        accounting.observe(boundary, pool_ids, guard=guard)
        if guard is not None: guard()
    except BaseException:
        for identifier in accounting.by_id if pool_ids is None else pool_ids:
            accounting.mark_incomplete(identifier, 'last_observation', 'OBSERVATION_BOUNDARY_MISSING')
        raise


def _accounting_io(accounting, guard, path, function, /, *args,
        create=False, write=False, requested_bytes=0, release=None, **kwargs):
    """Retain a successful syscall's real charge before checking a late return.

    A late operation leaves its object and accounting record intact. No next
    observation or filesystem effect is issued after the original clock expires.
    """
    if guard is not None: guard()
    pool = None
    touched = []
    if accounting is not None:
        pool = accounting.before_write(path, requested_bytes=requested_bytes, create=create, guard=guard)
        touched.append(pool)
        parent = str(PurePosixPath(path).parent)
        if any(parent == root or parent.startswith(root + '/')
                for root, *_ in accounting.roots):
            parent_pool = accounting.classify(parent)
            if parent_pool != pool:
                touched.append(parent_pool)
    if guard is not None: guard()
    try:
        value = function(*args, **kwargs)
    except BaseException:
        if accounting is not None:
            for identifier in touched:
                accounting.mark_incomplete(identifier, 'last_observation', 'CONTROLLED_IO_EFFECT_FAILED')
        if guard is not None: guard()
        raise
    try:
        if accounting is not None:
            accounting.record_io(path, written_bytes=value if write else 0,
                created_inodes=1 if create else 0)
            if len(touched) > 1:
                # A directory entry can allocate blocks in its containing pool.
                # It is observed there without inventing a second inode create.
                accounting.record_io(parent)
        if guard is not None: guard()
        ordinary = [identifier for identifier in touched
            if accounting.by_id[identifier]['measurement_kind'] != 'PROJECT_QUOTA']
        if ordinary:
            _accounting_observe(accounting, guard, 'CONTROLLED_IO', ordinary)
    except BaseException:
        if accounting is not None:
            for identifier in touched:
                accounting.mark_incomplete(identifier, 'last_observation', 'CONTROLLED_IO_BOUNDARY_MISSING')
        if release is not None: release(value)
        raise
    return value


class _InstallIO:
    """Private frozen-installer bindings; preserve its checks and control flow.

    Guard each effect with original clocks. Late kernel returns cannot be
    interrupted; only owned-handle closure remains allowed after expiry.
    """

    def __init__(self, guard, accounting=None):
        from types import SimpleNamespace
        self.guard = guard
        self.accounting, self.paths = accounting, {}
        self.call = partial(_guard_call, guard)
        call = self.call

        class InstallPath(type(Path())):
            def stat(path, *, follow_symlinks=True):
                return call(os.stat, path, follow_symlinks=follow_symlinks)

            def chmod(path, mode, *, follow_symlinks=True):
                return call(os.chmod, path, mode, follow_symlinks=follow_symlinks)

            def mkdir(path, mode=511, parents=False, exist_ok=False):
                _effect(not parents and not exist_ok, "INSTALL_MKDIR_OPTIONS")
                return _accounting_io(accounting, guard, str(path), os.mkdir, path, mode, create=True)

            def unlink(path, missing_ok=False):
                _effect(not missing_ok, "INSTALL_UNLINK_OPTIONS")
                return _accounting_io(accounting, guard, str(path), os.unlink, path)

            def iterdir(path):
                for name in call(os.listdir, path):
                    guard()
                    yield path / name

            def resolve(path, strict=False):
                # Only these admission-pinned, non-aliased literals may resolve.
                _effect(strict and str(path) in ("/usr/bin/systemctl", "/usr/bin/systemd-run"),
                    "INSTALL_RESOLVE_PATH")
                for parent in (*reversed(path.parents), path):
                    info = parent.lstat()
                    _effect(not stat.S_ISLNK(info.st_mode), "INSTALL_RESOLVE_ALIAS")
                return path

        self.Path = InstallPath
        self.os = SimpleNamespace(**{name: getattr(os, name) for name in
            _fields('O_RDONLY O_NOFOLLOW O_CLOEXEC O_NONBLOCK O_WRONLY O_CREAT O_EXCL O_DIRECTORY')})
        for name in _fields('fstat read fchmod getxattr geteuid readlink'):
            setattr(self.os, name, partial(call, getattr(os, name)))
        self.os.open, self.os.close, self.os.fsync = self.open, self.close, self.fsync
        self.os.fdopen = self.fdopen
        self.os.walk = self.walk
        self.os.path = SimpleNamespace(lexists=self.lexists)

    def open(self, path, flags, mode=0o777, *, dir_fd=None):
        _effect(dir_fd is None and PurePosixPath(path).is_absolute(), 'INSTALL_IO_PATH')
        if flags & os.O_CREAT:
            _effect(flags & os.O_EXCL, 'INSTALL_IO_CREATE')
            fd = _accounting_io(self.accounting, self.guard, str(path), os.open,
                path, flags, mode, create=True, release=os.close)
        else:
            fd = self.call(os.open, path, flags, mode, release=os.close)
        self.paths[fd] = str(path)
        return fd

    def close(self, fd):
        self.paths.pop(fd, None)
        os.close(fd)

    def fsync(self, fd):
        _effect(fd in self.paths, 'INSTALL_IO_DESCRIPTOR')
        return _accounting_io(self.accounting, self.guard, self.paths[fd], os.fsync, fd)

    def lexists(self, path):
        try:
            self.call(os.lstat, path)
        except FileNotFoundError:
            return False
        return True

    def fdopen(self, fd, mode, *, closefd):
        _effect(mode == "wb" and closefd is False, "INSTALL_STREAM_OPTIONS")
        call, guard = self.call, self.guard
        accounting, path = self.accounting, self.paths.get(fd)
        _effect(accounting is None or path is not None, 'INSTALL_IO_DESCRIPTOR')
        guard()

        class Stream:
            # Caller owns fd. Unbuffered writes prevent late cleanup flushes.
            def __enter__(stream):
                return stream

            def __exit__(stream, *error):
                return False

            def write(stream, raw):
                view = memoryview(raw)
                offset = 0
                while offset < len(view):
                    part = view[offset:offset + 65536]
                    count = _accounting_io(accounting, guard, path, os.write, fd, part,
                        write=True, requested_bytes=len(part))
                    _effect(type(count) is int and 0 < count <= min(65536, len(view) - offset),
                        "INSTALL_STREAM_WRITE")
                    offset += count
                return offset

            def flush(stream):
                guard()

        return Stream()

    def walk(self, root):
        pending = [self.Path(root)]
        while pending:
            path = pending.pop()
            directories, files = [], []
            for child in path.iterdir():
                info = child.lstat()
                _effect(not stat.S_ISLNK(info.st_mode), "INSTALL_WALK_ALIAS")
                (directories if stat.S_ISDIR(info.st_mode) else files).append(child.name)
            self.guard()
            yield str(path), directories, files
            pending.extend(path / name for name in reversed(directories))


def _admit_stat(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class _admit_reader:
    """Held no-follow policy reads, including end-of-snapshot name rechecks."""
    def __init__(self, guard, home, uid):
        self.guard, self.home, self.uid = guard, home, uid
        self.held, self.names, self.objects, self.raw = [], [], {}, {}
        self.root = self.root_info = None
        self.directories = {}

    def call(self, function, *args, **kwargs):
        return _guard_call(self.guard, function, *args, **kwargs)

    def open(self, *args, **kwargs):
        fd = self.call(os.open, *args, release=os.close, **kwargs)
        self.held.append(fd)
        return fd

    def close(self):
        while self.held:
            os.close(self.held.pop())

    def owner(self, path):
        return self.uid if path == self.home or path.startswith(self.home + "/") else 0

    def protected(self, info, path, *, directory=False):
        _require(info.st_uid == self.owner(path) and not stat.S_IMODE(info.st_mode) & 0o022
                 and (stat.S_ISDIR(info.st_mode) if directory else
                      stat.S_ISREG(info.st_mode) and info.st_nlink == 1),
                 "CORE_ADMIT_POLICY_PROTECTION")

    def parent(self, path):
        parts = FieldEffects._absolute(path).parts[1:]
        _require(0 < len(parts) <= 64, "CORE_ADMIT_POLICY_DEPTH")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NOATIME
        if self.root is None:
            self.root = self.open("/", flags)
            self.root_info = self.call(os.fstat, self.root)
            self.protected(self.root_info, "/", directory=True)
            self.directories["/"] = self.root
        fd = self.root
        current = ""
        for part in parts[:-1]:
            current += "/" + part
            before = self.call(os.stat, part, dir_fd=fd, follow_symlinks=False)
            self.protected(before, current, directory=True)
            if current in self.directories:
                child = self.directories[current]
                _require(_admit_stat(self.call(os.fstat, child)) == _admit_stat(before),
                         "CORE_ADMIT_POLICY_DRIFT")
                fd = child
                continue
            child = self.open(part, flags, dir_fd=fd)
            _require(_admit_stat(self.call(os.fstat, child)) == _admit_stat(before),
                     "CORE_ADMIT_POLICY_DRIFT")
            self.names.append((fd, part, child, before))
            self.directories[current] = child
            fd = child
        return fd, parts[-1]

    def read(self, path, *, maximum=262144, required=True, directory=False, private=False):
        _require(path not in self.objects, "CORE_ADMIT_POLICY_REPEAT")
        parent, name = self.parent(path)
        try:
            before = self.call(os.stat, name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            _require(not required, "CORE_ADMIT_POLICY_MISSING")
            self.names.append((parent, name, None, None))
            self.objects[path] = dict(path=path, state="ABSENT", **dict.fromkeys(
                ("kind", "dev", "ino", "mode", "uid", "gid", "nlink", "bytes", "sha256")))
            return None
        self.protected(before, path, directory=directory)
        _require(not private or not stat.S_IMODE(before.st_mode) & 0o177,
                 "CORE_ADMIT_KEY_MODE")
        _require(directory or 0 <= before.st_size <= maximum, "CORE_ADMIT_POLICY_BYTES")
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NOATIME | os.O_NONBLOCK
        if directory:
            flags |= os.O_DIRECTORY
        fd = self.open(name, flags, dir_fd=parent)
        _require(_admit_stat(self.call(os.fstat, fd)) == _admit_stat(before),
                 "CORE_ADMIT_POLICY_DRIFT")
        self.names.append((parent, name, fd, before))
        raw = bytearray()
        if not directory:
            while len(raw) <= maximum:
                block = self.call(os.read, fd, min(65536, maximum + 1 - len(raw)))
                if not block:
                    break
                raw.extend(block)
            _require(len(raw) == before.st_size and len(raw) <= maximum,
                     "CORE_ADMIT_POLICY_BYTES")
        self.objects[path] = dict(path=path, state="PRESENT", kind="directory" if directory else "regular",
            dev=before.st_dev, ino=before.st_ino, mode=stat.S_IMODE(before.st_mode), uid=before.st_uid,
            gid=before.st_gid, nlink=before.st_nlink, bytes=None if directory else len(raw),
            sha256=None if directory else _sha(bytes(raw)))
        self.raw[path] = bytes(raw)
        self.recheck()
        return fd if directory else bytes(raw)

    def recheck(self):
        if self.root is not None:
            _require(_admit_stat(self.call(os.fstat, self.root)) == _admit_stat(self.root_info)
                     and _admit_stat(self.call(os.stat, "/", follow_symlinks=False)) == _admit_stat(self.root_info),
                     "CORE_ADMIT_ROOT_DRIFT")
        for parent, name, fd, before in self.names:
            try:
                current = self.call(os.stat, name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                _require(fd is None, "CORE_ADMIT_POLICY_DRIFT")
                continue
            _require(fd is not None and _admit_stat(current) == _admit_stat(before)
                     and _admit_stat(self.call(os.fstat, fd)) == _admit_stat(before),
                     "CORE_ADMIT_POLICY_DRIFT")

    def listing(self, path, maximum):
        fd = self.read(path, directory=True)
        names = []
        with self.call(os.scandir, fd, release=lambda it: it.close()) as entries:
            while (item := self.call(next, entries, None)) is not None:
                _require(len(names) < maximum and item.name.isascii(), "CORE_ADMIT_POLICY_ENTRIES")
                names.append(item.name)
        self.recheck()
        return sorted(names)


def _admit_text(raw):
    try:
        value = raw.decode("ascii", "strict")
    except UnicodeError as error:
        raise DispatchError("CORE_ADMIT_POLICY_ENCODING") from error
    _require("\0" not in value and "\r" not in value, "CORE_ADMIT_POLICY_ENCODING")
    return value


def _admit_sudo_source(raws, literal):
    """Only the fixed ordinary sudoers grammar; no custom plugin or alias."""
    count = includes = 0
    for path, raw in raws.items():
        if path == "/etc/sudo.conf":
            _require(all(not line.strip() or line.lstrip().startswith("#")
                         for line in _admit_text(raw).splitlines()), "CORE_ADMIT_SUDO_PLUGIN")
            continue
        for line in _admit_text(raw).splitlines():
            line = line.strip()
            if line in ("@includedir /etc/sudoers.d", "#includedir /etc/sudoers.d"):
                _require(path == "/etc/sudoers", "CORE_ADMIT_SUDO_INCLUDE")
                includes += 1
                continue
            _require(not line.startswith(("@include", "#include")), "CORE_ADMIT_SUDO_INCLUDE")
            if not line or line.startswith("#"):
                continue
            if line == literal:
                count += 1
                continue
            if line.startswith("Defaults"):
                _require(re.fullmatch(r'Defaults\s+(?:env_reset|mail_badpass|use_pty|'
                    r'secure_path="/[A-Za-z0-9_/:.-]+")', line) is not None,
                    "CORE_ADMIT_SUDO_SOURCE_GRAMMAR")
                continue
            _require(re.fullmatch(r'(?:root|%admin|%sudo)\s+ALL\s*=\s*\(ALL(?::ALL)?\)\s+ALL', line)
                     is not None, "CORE_ADMIT_SUDO_SOURCE_GRAMMAR")
    _require(count == includes == 1, "CORE_ADMIT_SUDO_SOURCE_GRANT")
    return count


def _admit_sudo_output(raw, grant, source_paths=()):
    """Parse C-locale long listings without changing the required grant.

    sudo 1.9.15 adds a source path to entry headers; pipe output uses a literal
    TAB before commands. Paths are labels for already held source files, never
    new read targets or substitutes for the source/grant checks.
    """
    raw_lines = raw.split(b"\n")
    summary = (f"_BYTES{len(raw)}_LINES{len(raw_lines) - (not raw or raw.endswith(b'\n'))}"
        f"_ENTRIES{sum(line.startswith(b'Sudoers entry:') for line in raw_lines)}"
        f"_SOURCE{sum(line.startswith(b'Sudoers entry: ') for line in raw_lines)}"
        f"_TAB{sum(line == b'\tALL' for line in raw_lines)}"
        f"_SPACES{sum(line == b'        ALL' for line in raw_lines)}"
        f"_SHA256_{_sha(raw).upper()}")

    def check(condition, stage, line=0, entry=0, *, category="OUTPUT"):
        if not condition:
            # Only fixed stages, counts and a digest cross bootstrap's existing
            # CORE_[A-Z0-9_]+ stderr filter. Never echo policy text or paths.
            raise DispatchError(f"CORE_ADMIT_SUDO_{category}_{stage}_L{line}_E{entry}" + summary)

    check(all(byte in (9, 10) or 32 <= byte <= 126 for byte in raw), "ENCODING")
    lines = raw.decode("ascii").split("\n")
    user_header = r"User q1admin may run the following commands on [A-Za-z0-9_.-]+:"
    index = 0
    if lines and re.fullmatch(r"Matching Defaults entries for q1admin on [A-Za-z0-9_.-]+:", lines[0]):
        index = 1
        while index < len(lines) and (not lines[index] or lines[index].startswith("    ")):
            index += 1
    check(index < len(lines) and re.fullmatch(user_header, lines[index]) is not None,
          "USER_HEADER", index + 1)
    index += 1
    sources = set(source_paths) - {"/etc/sudo.conf"}
    sections = []
    for number, line in enumerate(lines[index:], index + 1):
        if not line:
            continue
        if line.startswith("Sudoers entry:"):
            source = line[len("Sudoers entry:"):]
            check(not source or (source.startswith(" /") and source[1:] in sources),
                  "ENTRY_SOURCE", number, len(sections) + 1)
            sections.append((number, []))
        else:
            check(bool(sections), "ENTRY_HEADER", number)
            sections[-1][1].append((number, line))
    check(bool(sections), "ENTRY_COUNT", index + 1)
    grants = []
    for entry, (start, section) in enumerate(sections, 1):
        fields, commands = {}, []
        command_mode = False
        for number, line in section:
            if command_mode:
                check(line in ("\tALL", "        ALL"), "COMMAND", number, entry)
                commands.append("ALL")
                continue
            match = re.fullmatch(r'    (RunAsUsers|RunAsGroups|Options|Commands):(.*)', line)
            check(match is not None, "FIELD", number, entry)
            check(match[1] not in fields, "DUPLICATE_FIELD", number, entry)
            key, value = match[1], match[2].strip()
            fields[key] = value
            if key == "Commands":
                check(value == "", "COMMAND_HEADER", number, entry)
                command_mode = True
        check(set(fields) >= {"RunAsUsers", "Commands"}
                 and set(fields) <= {"RunAsUsers", "RunAsGroups", "Options", "Commands"},
              "REQUIRED_FIELDS", start, entry)
        check(commands == ["ALL"], "COMMAND_COUNT", start, entry)
        check(fields["RunAsUsers"] == "ALL", "RUNAS_USERS", start, entry)
        check(fields.get("RunAsGroups", "") in ("", "ALL"), "RUNAS_GROUPS", start, entry)
        check(fields.get("Options", "authenticate") in ("!authenticate", "authenticate"),
              "OPTIONS", start, entry)
        grants.append(dict(host="ALL", runas_users=["ALL"],
            runas_groups=["ALL"] if fields.get("RunAsGroups") else [],
            tags=["NOPASSWD"] if fields.get("Options") == "!authenticate" else ["PASSWD"], commands=commands))
    check(grant in grants, "MATCH", category="GRANT")
    return grants


def _admit_sshd_source(raws):
    """Fixed grammar with the approved single main-file locale exception.

    F is the one-based collector input order and L the existing splitlines()
    parser line. F0/L0 identifies a closure-wide check; L0 a whole-file check.
    Closure digests bind ordered path/file digests, not a new source or read.
    """
    includes = 0
    locale_declarations = 0
    file_index, path, raw = 0, None, None

    def check(condition, code, stage, line=0):
        if condition:
            return
        if file_index:
            size, lines, digest = len(raw), len(raw.decode("ascii", "replace").splitlines()), _sha(raw)
            path_digest = _sha(path.encode("utf-8", "surrogatepass"))
        else:
            size = sum(map(len, raws.values()))
            lines = sum(len(value.decode("ascii", "replace").splitlines()) for value in raws.values())
            path_digest = "0" * 64
            digest = _sha(canonical([
                dict(path_sha256=_sha(name.encode("utf-8", "surrogatepass")), bytes=len(value), sha256=_sha(value))
                for name, value in raws.items()]))
        raise DispatchError(f"{code}_{stage}_F{file_index}_L{line}_FILES{len(raws)}"
            f"_BYTES{size}_LINES{lines}_INCLUDES{includes}"
            f"_PATHSHA256_{path_digest.upper()}_SHA256_{digest.upper()}")

    for file_index, (path, raw) in enumerate(raws.items(), 1):
        try:
            text = _admit_text(raw)
        except DispatchError:
            check(False, "CORE_ADMIT_POLICY_ENCODING", "SSHD_SOURCE_TEXT")
        offset = 0
        for number, source_line in enumerate(text.splitlines(keepends=True), 1):
            # Preserve parser line numbering, but never let splitlines/strip
            # turn a control-delimited fragment into the new LF-only exception.
            lf_start = offset == 0 or text[offset - 1] == "\n"
            offset += len(source_line)
            line = source_line.strip()
            if not line or line.startswith("#"):
                continue
            check(not any(char in line for char in ('"', "'", "\\", "`", "$")),
                  "CORE_ADMIT_SSHD_GRAMMAR", "QUOTE_OR_EXPANSION", number)
            words = line.split()
            check(len(words) >= 2, "CORE_ADMIT_SSHD_GRAMMAR", "ARGUMENT_COUNT", number)
            name = words[0].lower()
            check(name != "match", "CORE_ADMIT_SSHD_MATCH", "DIRECTIVE", number)
            if name == "include":
                check(path == "/etc/ssh/sshd_config", "CORE_ADMIT_SSHD_INCLUDE", "LOCATION", number)
                check(words[1:] == ["/etc/ssh/sshd_config.d/*.conf"],
                      "CORE_ADMIT_SSHD_INCLUDE", "TARGET", number)
                includes += 1
            else:
                check(re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', words[0]) is not None,
                      "CORE_ADMIT_SSHD_GRAMMAR", "KEYWORD", number)
                locale_line = (path == "/etc/ssh/sshd_config" and locale_declarations == 0
                    and name == "acceptenv" and words[1:] == ["LANG", "LC_*"] and lf_start
                    and re.fullmatch(r'[ \t]*[A-Za-z]+[ \t]+LANG[ \t]+LC_\*[ \t]*\n?', source_line) is not None)
                check(not any(char in line for char in "*?[]") or locale_line,
                      "CORE_ADMIT_SSHD_GRAMMAR", "GLOB", number)
                if locale_line:
                    locale_declarations += 1
    file_index = 0
    check(includes == 1, "CORE_ADMIT_SSHD_INCLUDE", "COUNT")


def _admit_sshd_output(raw, required):
    values = {}
    for line in _admit_text(raw).splitlines():
        words = line.split()
        _require(len(words) >= 2 and re.fullmatch(r'[a-z][a-z0-9]*', words[0]),
                 "CORE_ADMIT_SSHD_OUTPUT")
        # sshd reports list-valued settings (e.g. hostkey) on several lines.
        # The five admission predicates themselves must each occur exactly once.
        values.setdefault(words[0], []).append(words[1:])
    effective = {}
    for key, wanted in required.items():
        _require(key in values and values[key] == [wanted if type(wanted) is list else [wanted]],
                 "CORE_ADMIT_SSHD_PREDICATE")
        effective[key] = wanted
    return effective


def _admit_authorized(raw, path, approved):
    rows = [(index, line.strip()) for index, line in enumerate(_admit_text(raw).splitlines(), 1)
            if line.strip() and not line.lstrip().startswith("#")]
    _require(len(rows) == 1, "CORE_ADMIT_KEY_COUNT")
    number, line = rows[0]
    parts = line.split(None, 2)
    _require(len(parts) >= 2 and parts[0] == approved["type"] == "ssh-ed25519"
             and parts[1] == approved["key_base64"], "CORE_ADMIT_KEY_MISMATCH")
    try:
        key = base64.b64decode(parts[1], validate=True)
    except (ValueError, TypeError) as error:
        raise DispatchError("CORE_ADMIT_KEY_ENCODING") from error
    _require(len(key) == 51 and key[:19] == b'\0\0\0\x0bssh-ed25519\0\0\0 ', "CORE_ADMIT_KEY_ENCODING")
    return [dict(path=path, line_number=number, key_type=parts[0], key_sha256=_sha(key),
                 options=[], comment_present=len(parts) == 3)]


def _admit_bashrc(raw):
    lines = _admit_text(raw).splitlines()
    active = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    # Match only the approved first AST, with whitespace variation, never eval.
    text = "\n".join(active)
    guard = re.match(r'case[ \t]+\$-[ \t]+in\s+\*i\*\)[ \t]*;;\s+\*\)[ \t]*return[ \t]*;;\s+esac(?:[ \t]*\n|[ \t]*$)', text)
    _require(guard is not None, "CORE_ADMIT_BASHRC_GUARD")
    return True


def _admit_program(reader, path, expected=None):
    """Resolve a bounded executable alias, retain each link and target identity."""
    pending = list(FieldEffects._absolute(path).parts[1:])
    resolved, chain, links, seen = [], [], [], set()
    components = 0
    while pending:
        components += 1
        _require(components <= 64, "CORE_ADMIT_PROGRAM_COMPONENTS")
        name = pending.pop(0)
        current = "/" + "/".join(resolved + [name])
        _require(current not in ("/proc", "/dev/fd"), "CORE_ADMIT_PROGRAM_MAGIC_LINK")
        parent, leaf = reader.parent(current)
        info = reader.call(os.stat, leaf, dir_fd=parent, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            _require(current not in seen and len(chain) < 8 and info.st_uid == 0,
                     "CORE_ADMIT_PROGRAM_LINK")
            target = reader.call(os.readlink, leaf, dir_fd=parent)
            _require(type(target) is str and target.isascii() and 0 < len(target) <= 4096
                     and re.fullmatch(r'[A-Za-z0-9._/-]+', target) is not None
                     and '//' not in target and all(p not in ('.', '..') for p in target.split('/')),
                     "CORE_ADMIT_PROGRAM_LINK")
            seen.add(current); chain.append(dict(path=current, target=target))
            links.append((parent, leaf, info, target))
            if target.startswith('/'):
                resolved = []
            pending = [p for p in target.split('/') if p] + pending
        elif pending:
            reader.protected(info, current, directory=True)
            resolved.append(name)
        else:
            target_path = current
    raw = reader.read(target_path, maximum=16777216)
    item = reader.objects[target_path]
    _require(raw and item["mode"] & 0o111 and item["uid"] == item["gid"] == 0,
             "CORE_ADMIT_PROGRAM_IDENTITY")
    for parent, leaf, before, target in links:
        _require(_admit_stat(reader.call(os.stat, leaf, dir_fd=parent, follow_symlinks=False)) == _admit_stat(before)
                 and reader.call(os.readlink, leaf, dir_fd=parent) == target, "CORE_ADMIT_PROGRAM_DRIFT")
    item["kind"] = "executable"
    value = {key: item[key] for key in PROGRAM_FIELDS if key != "path"}
    value.update(path=path, resolved_path=target_path, symlink_chain=chain)
    _require(expected is None or value == expected, "CORE_ADMIT_PROGRAM_BINDING")
    return value


def _admit_exec_binding(effects, path, expected):
    """Execute the verified, held ELF, not a later lookup of its pathname."""
    _require(type(expected) is dict, "CORE_ADMIT_HELPER_PROGRAM")
    reader = _admit_reader(effects._effect_guard, '/', 0)
    try:
        entity = _admit_program(reader, path, expected)
        fd = reader.names[-1][2]
        _require(fd is not None and reader.call(os.pread, fd, 4, 0) == b'\x7fELF',
                 "CORE_ADMIT_HELPER_ELF")
        reader.recheck()
        return reader, fd
    except BaseException:
        reader.close()
        raise


def _admit_run_helper(effects, policy, program_check, *, prior_observation=None, user_uid=None):
    """One approved semantic child: bounded streams, CPU limit, real wait4/EOF."""
    argv, env, limits = policy["argv"], policy["environment"], policy["limits"]
    if user_uid is not None:
        _require(type(user_uid) is int and user_uid == 1100 and prior_observation is None
            and argv[:5] == ['/usr/bin/systemctl','--user','--no-pager','--no-ask-password','show']
            and env.get('XDG_RUNTIME_DIR') == '/run/user/1100'
            and env.get('DBUS_SESSION_BUS_ADDRESS') == 'unix:path=/run/user/1100/bus',
            'CORE_RUNTIME_HELPER_CREDENTIALS')
    seen = getattr(effects, "_admit_helpers_attempted", None)
    if seen is None:
        effects._admit_helpers_attempted = seen = set()
    attempt_key = tuple(argv)
    if prior_observation is not None:
        slots = ((0, 1), (1, 1), (2, 1), (3, 1), (0, 2), (1, 2), (2, 2), (3, 2))
        consumed = getattr(effects, '_prior_show_slots', [])
        _require(type(prior_observation) is tuple
            and all(type(value) is int for value in prior_observation)
            and not getattr(effects, '_prior_show_stopped', False)
            and len(consumed) < 8 and prior_observation == slots[len(consumed)],
            'CORE_PRIOR_SCOPE_SHOW_SLOT')
        index, ordinal = prior_observation
        _require(argv == ['/usr/bin/systemctl', '--system', '--no-pager', '--no-ask-password',
            'show', '--all', _prior_profile(index)['unit'], '--property=' + ','.join(PRIOR_SHOW_FIELDS)]
            and limits == dict(command_seconds=5, command_cpu_seconds=2,
                stdout_bytes=32768, stderr_bytes=32768, combined_output_bytes=32768),
            'CORE_PRIOR_SCOPE_SHOW_POLICY')
        effects._prior_show_slots = [*consumed, prior_observation]
        effects._prior_show_stopped = True
        attempt_key += ('prior-observation', ordinal)
    _require(attempt_key not in seen, "CORE_ADMIT_HELPER_REPLAY")
    seen.add(attempt_key)
    effects._effect_guard()
    expected_program = program_check()
    started = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    started_mono = time.monotonic_ns()
    end = started + limits["command_seconds"] * NS
    mono_end = started_mono + limits["command_seconds"] * NS
    proc = None
    executable_reader = None
    waited = None
    output = {"stdout": bytearray(), "stderr": bytearray()}
    observed_bytes = dict.fromkeys(output, 0)
    eof = set()
    failure = cleanup = None
    def guard():
        effects._effect_guard()
        _require(time.clock_gettime_ns(time.CLOCK_BOOTTIME) < end
                 and time.monotonic_ns() < mono_end, "CORE_ADMIT_HELPER_TIMEOUT")
    def cpu_limit():
        resource.setrlimit(resource.RLIMIT_CPU, (limits["command_cpu_seconds"], limits["command_cpu_seconds"]))
        if user_uid is not None:
            os.setgroups([])
            os.setresgid(1100,1100,1100)
            os.setresuid(1100,1100,1100)
    def poll(stopping=False):
        nonlocal waited
        check = (lambda: _clock(effects, effects.context["guest_deadlines"])) if stopping else guard
        call = partial(_guard_call, check)
        check()
        if waited is None:
            # Record successful reap before a late guard can raise: cleanup
            # must not wait4 the already reaped child or lose its real status.
            pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
            if pid:
                _require(pid == proc.pid, "CORE_ADMIT_HELPER_WAIT")
                proc.returncode = os.waitstatus_to_exitcode(status)
                waited = dict(pid=pid, wait_status=status, user_cpu_ns=math.ceil(usage.ru_utime * NS),
                              system_cpu_ns=math.ceil(usage.ru_stime * NS), max_rss_bytes=usage.ru_maxrss * 1024)
            check()
        for name in output:
            if name in eof:
                continue
            room = min(limits[name + "_bytes"] - len(output[name]),
                       limits["combined_output_bytes"] - sum(map(len, output.values())))
            try:
                raw = call(os.read, getattr(proc, name).fileno(),
                    65536 if stopping else min(65536, max(0, room) + 1))
            except BlockingIOError:
                continue
            if not raw:
                eof.add(name)
            else:
                observed_bytes[name] += len(raw)
                output[name].extend(raw[:max(0, room)])
                if not stopping:
                    _require(len(raw) <= room, "CORE_ADMIT_HELPER_OUTPUT_LIMIT")
        if not stopping:
            guard()
    try:
        guard()
        executable_reader, executable_fd = _admit_exec_binding(effects, argv[0], expected_program)
        guard()
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd="/", env=env, shell=False, close_fds=True,
            start_new_session=True, preexec_fn=cpu_limit,
            executable='/proc/self/fd/' + str(executable_fd), pass_fds=(executable_fd,))
        guard()
        for name in output:
            os.set_blocking(getattr(proc, name).fileno(), False)
            guard()
        while waited is None or len(eof) != 2:
            poll()
            if waited is None or len(eof) != 2:
                time.sleep(0.002)
        _require(proc.returncode == 0 and waited["user_cpu_ns"] + waited["system_cpu_ns"] <= limits["command_cpu_seconds"] * NS,
                 "CORE_ADMIT_HELPER_EXIT")
        guard(); program_check(); guard()
    except BaseException as error:
        failure = str(error) if isinstance(error, DispatchError) else type(error).__name__
        if proc is not None:
            try:
                if waited is None or len(eof) != 2:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                for name in output:
                    os.set_blocking(getattr(proc, name).fileno(), False)
                while waited is None or len(eof) != 2:
                    poll(stopping=True)
                    if waited is None or len(eof) != 2:
                        time.sleep(0.002)
            except BaseException as error2:
                cleanup = str(error2) if isinstance(error2, DispatchError) else type(error2).__name__
        raise
    finally:
        finished = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        usage = getattr(effects, "_admit_helper_usage", None)
        if usage is None:
            effects._admit_helper_usage = usage = []
        usage.append(dict(argv=list(argv), started_boottime_ns=started, finished_boottime_ns=finished,
            wait4=waited, eof=sorted(eof), failure=failure, cleanup_failure=cleanup,
            stdout_bytes=observed_bytes["stdout"], stderr_bytes=observed_bytes["stderr"],
            retained_stdout_bytes=len(output["stdout"]), retained_stderr_bytes=len(output["stderr"])))
        if proc is not None:
            proc.stdout.close(); proc.stderr.close()
        if executable_reader is not None:
            executable_reader.close()
    stdout, stderr = bytes(output["stdout"]), bytes(output["stderr"])
    if prior_observation is not None:
        effects._prior_show_stopped = False
    return stdout, stderr, dict(argv_sha256=_sha(canonical(argv)), environment_sha256=_sha(canonical(env)),
        started_boottime_ns=started, finished_boottime_ns=finished, exit_status=proc.returncode,
        stdout_bytes=len(stdout), stdout_sha256=_sha(stdout), stderr_bytes=len(stderr), stderr_sha256=_sha(stderr),
        combined_bytes=len(stdout) + len(stderr), timed_out=False, stdout_eof=True, stderr_eof=True)


def _admit_helper(effects, policy, program_check):
    _require(policy["argv"] in (["/usr/bin/sudo", "-n", "-ll", "-U", "q1admin"],
            ["/usr/sbin/sshd", "-T"]), "CORE_ADMIT_HELPER_ARGV")
    return _admit_run_helper(effects, policy, program_check)


def _admit_programs(effects):
    remote = effects.context["hello"]["remote_management"]
    programs, resolved = {}, {}
    aliases = dict(python="/usr/bin/python3", git="/usr/bin/git", cc="/usr/bin/cc",
                   setpriv="/usr/bin/setpriv", systemctl="/usr/bin/systemctl", systemd_run="/usr/bin/systemd-run")
    for name, path in aliases.items():
        reader = _admit_reader(effects._effect_guard, remote["home"], remote["uid"])
        try:
            item = _admit_program(reader, path, remote.get(name))
            programs[name] = {key: item[key] for key in PROGRAM_FIELDS}
            if name in ("python", "git", "cc"):
                programs[name]["path"] = item["resolved_path"]
            else:
                _require(item["resolved_path"] == path, "CORE_ADMIT_FIXED_PROGRAM_ALIAS")
            resolved[name] = item
        finally:
            reader.close()
    effects._admit_program_entities = resolved
    return programs


def _admit_guest(effects, programs):
    import pwd
    import grp
    import socket
    call = effects._capacity_call
    read = effects._capacity_kernel
    _require(read("/proc/1/comm", 64) == b"systemd\n", "CORE_ADMIT_PID1_COMM")
    one, current = [], []
    try:
        for path, target in (("/proc/1/ns/user", one), ("/proc/self/ns/user", current)):
            fd = call(os.open, path, os.O_RDONLY | os.O_CLOEXEC, release=os.close)
            target.append(fd); target.append(call(os.fstat, fd))
        _require((one[1].st_dev, one[1].st_ino) == (current[1].st_dev, current[1].st_ino),
                 "CORE_ADMIT_INITIAL_NAMESPACE")
        namespace = dict(dev=one[1].st_dev, ino=one[1].st_ino)
    finally:
        for item in (one, current):
            if item:
                os.close(item[0])
    vendor = _admit_text(read("/sys/devices/virtual/dmi/id/sys_vendor", 256)).strip()
    product = _admit_text(read("/sys/devices/virtual/dmi/id/product_name", 256)).strip()
    _require((vendor in ("QEMU", "KVM") or product == "KVM")
             and 0 < len(vendor) <= 128 and 0 < len(product) <= 128, "CORE_ADMIT_ISOLATED_GUEST")
    boot = _admit_text(read("/proc/sys/kernel/random/boot_id", 64)).strip()
    _require(boot == effects.context["hello"]["guest_boot_id"] == effects.context["guest_deadlines"]["boot_id"],
             "CORE_ADMIT_GUEST_BOOT")
    controllers = _admit_text(read("/sys/fs/cgroup/cgroup.controllers", 4096)).split()
    _require(set(("cpu", "memory", "pids")) <= set(controllers), "CORE_ADMIT_CGROUP_V2")
    locators = effects.context["manifest"]["locators"]
    account = call(pwd.getpwnam, locators["ordinary_user"])
    group = call(grp.getgrnam, locators["ordinary_group"])
    _require(account.pw_uid > 0 and account.pw_gid == group.gr_gid > 0
             and call(pwd.getpwuid, account.pw_uid) == account
             and call(grp.getgrgid, group.gr_gid) == group, "CORE_ADMIT_ORDINARY_ACCOUNT")
    groups = sorted(set(call(os.getgrouplist, account.pw_name, account.pw_gid)))
    _require(groups == [account.pw_gid], "CORE_ADMIT_ORDINARY_GROUPS")
    pid1 = call(os.readlink, "/proc/1/exe")
    _require(pid1 in ("/lib/systemd/systemd", "/usr/lib/systemd/systemd"), "CORE_ADMIT_PID1_PATH")
    remote = effects.context["hello"]["remote_management"]
    reader = _admit_reader(effects._effect_guard, remote["home"], remote["uid"])
    try:
        entity = _admit_program(reader, pid1)
        def check_pid1():
            reader.recheck()
            info = call(os.stat, "/proc/1/exe")
            _require(call(os.readlink, "/proc/1/exe") == pid1
                     and (info.st_dev, info.st_ino, info.st_size) ==
                     (entity["dev"], entity["ino"], entity["bytes"]), "CORE_ADMIT_PID1_DRIFT")
            return entity
        policy = dict(argv=[pid1, "--version"],
            environment={"HOME": "/root", "LANG": "C", "LC_ALL": "C", "LOGNAME": "root",
                         "PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "SYSTEMD_COLORS": "0", "USER": "root"},
            limits=dict(command_seconds=5, command_cpu_seconds=2, stdout_bytes=32768,
                        stderr_bytes=32768, combined_output_bytes=32768))
        stdout, stderr, _ = _admit_run_helper(effects, policy, check_pid1)
        lines = _admit_text(stdout).splitlines()
        _require(not stderr and lines and re.fullmatch(r'systemd [0-9]+(?: [ -~]+)?', lines[0]),
                 "CORE_ADMIT_PID1_VERSION")
    finally:
        reader.close()
    return dict(hostname=call(socket.gethostname), dmi_vendor=vendor, dmi_product=product,
        initial_userns=namespace, boot_id=boot, pid1_exe=pid1, pid1_version=lines[0], cgroup_version=2,
        ordinary_user=account.pw_name, ordinary_uid=account.pw_uid, ordinary_gid=account.pw_gid,
        ordinary_groups=groups)


def _admit_collect_policies(effects, basis, remote):
    import pwd
    effects._effect_guard()
    _require(os.geteuid() == os.getegid() == 0, "CORE_ADMIT_ROOT_REQUIRED")
    account = effects._capacity_call(pwd.getpwnam, remote["account"])
    observed = dict(name=account.pw_name, uid=account.pw_uid, gid=account.pw_gid,
                    home=account.pw_dir, login_shell=account.pw_shell)
    _require(observed == dict(name=remote["account"], uid=remote["uid"], gid=remote["gid"],
                             home=remote["home"], login_shell=remote["login_shell"]), "CORE_ADMIT_ACCOUNT_DRIFT")
    snapshots, policies = {}, {}
    for name in ("sudo", "sshd", "authorized_keys", "rc"):
        policy = basis["policies"][name]
        params, paths = policy["predicate"]["parameters"], policy["paths"]
        reader = _admit_reader(effects._effect_guard, remote["home"], remote["uid"])
        try:
            def read_policy(path, required=True, private=False):
                files = sum(row["kind"] == "regular" for row in reader.objects.values())
                remaining = paths["limits"]["max_total_bytes"] - sum(map(len, reader.raw.values()))
                _require(files < paths["limits"]["max_files"] and remaining >= 0, "CORE_ADMIT_POLICY_TOTAL")
                return reader.read(path, maximum=min(paths["limits"]["max_file_bytes"], remaining),
                                   required=required, private=private)
            for item in paths["fixed_paths"]:
                read_policy(item["path"], required=item["required"])
            for item in paths["home_relative_paths"]:
                read_policy(remote["home"] + "/" + item["path"],
                            required=item["required"], private=name == "authorized_keys")
            for item in paths["include_roots"]:
                for leaf in reader.listing(item["path"], paths["limits"]["max_directory_entries"]):
                    selected = (not leaf.startswith('.') and '.' not in leaf and not leaf.endswith('~')
                                if name == "sudo" else leaf.endswith('.conf'))
                    if selected:
                        read_policy(item["path"] + "/" + leaf)
            _require(len(reader.raw) <= paths["limits"]["max_files"] + len(paths["include_roots"])
                     and sum(map(len, reader.raw.values())) <= paths["limits"]["max_total_bytes"],
                     "CORE_ADMIT_POLICY_TOTAL")
            raw = {path: value for path, value in reader.raw.items()
                   if reader.objects[path]["kind"] == "regular"}
            if name in ("sudo", "sshd"):
                if name == "sudo":
                    count = _admit_sudo_source(raw, params["cloud_config_literal"])
                else:
                    _admit_sshd_source(raw)
                executable = policy["execution"]["executable"]
                pin = remote["sudo"] if name == "sudo" else None
                program = _admit_program(reader, executable, pin)
                def check_program():
                    # Full reread in a fresh bounded reader checks alias and bytes,
                    # not merely the already open target's inode.
                    check = _admit_reader(effects._effect_guard, remote["home"], remote["uid"])
                    try:
                        _admit_program(check, executable, program)
                    finally:
                        check.close()
                    reader.recheck()
                    return program
                stdout, stderr, helper = _admit_helper(effects, policy, check_program)
                _require(not stderr, "CORE_ADMIT_HELPER_STDERR")
                if name == "sudo":
                    facts = dict(helper=helper, cloud_config_literal_count=count,
                                 parsed_grants=_admit_sudo_output(stdout, params["required_grant"], raw), matched=True)
                else:
                    facts = dict(helper=helper, effective=_admit_sshd_output(stdout, params["required_effective"]), matched=True)
            elif name == "authorized_keys":
                first, second = [remote["home"] + "/" + path for path in params["authorized_keys_files"]]
                _require(reader.objects[second]["state"] == "ABSENT", "CORE_ADMIT_SECOND_KEY_FILE")
                facts = dict(effective_entries=_admit_authorized(raw[first], first, params["approved_key"]), matched=True)
            else:
                absent = [dict(path=path, absent=reader.objects[path]["state"] == "ABSENT")
                          for path in params["required_absent"]]
                environment = [dict(name=key, absent=key not in os.environ) for key in params["forbidden_environment"]]
                _require(all(row["absent"] for row in absent + environment), "CORE_ADMIT_RC_ACTIVE")
                startup = [{key: reader.objects[path][key] for key in ("path", "state", "bytes", "sha256")}
                           for path in params["shell_startup_paths"]]
                bashrc = remote["home"] + "/.bashrc"
                if reader.objects[bashrc]["state"] == "PRESENT":
                    _admit_bashrc(raw[bashrc])
                facts = dict(required_absent=absent, shell_startup=startup,
                    bashrc_guard=dict(path=bashrc, state=reader.objects[bashrc]["state"],
                        profile=params["bashrc_guard_profile"], matched=True),
                    forbidden_environment_absent=environment, matched=True)
            reader.recheck()
            snapshot = dict(schema="local-hand-q2-core-policy-snapshot/v1", policy=name,
                account=observed, objects=[reader.objects[path] for path in sorted(reader.objects)], facts=facts)
            encoded = canonical(snapshot)
            policies[name] = dict(paths=sorted(reader.objects), bytes=len(encoded), sha256=_sha(encoded),
                relation=dict(stage="POST_ENTRY_PRE_H01_INTENT", pre_entry_containment=False,
                    policy_basis_sha256=_sha(canonical(basis)), predicate_sha256=policy["predicate_sha256"],
                    snapshot_sha256=_sha(encoded), facts_sha256=_sha(canonical(facts)), matched=True))
            snapshots[name] = snapshot
        finally:
            reader.close()
    return dict(policies=policies, snapshots=snapshots)


_CAP_ROLES = ('state', 'quota', 'install', 'journal', 'evidence')


_CAP_SNAPSHOT_ROLES = (
    ('system',), ('system',), ('system', 'journal', 'evidence'), ('system',),
    ('system',), ('system', 'journal', 'evidence'), ('system',),
    *(('system', 'quota'), ('journal',), ('system', 'journal', 'evidence')) * 5,
    ('system',), ('system',),
)


def _cap_usec(value):
    parts = re.findall(r"([0-9]+)(us|ms|min|s|h|d)", value)
    _require(parts and ''.join(number + unit for number, unit in parts) == value.replace(' ', ''),
             'CORE_CAP_TIME_VALUE')
    return sum(int(number) * {'us': 1, 'ms': 1000, 's': 1000000, 'min': 60000000,
                             'h': 3600000000, 'd': 86400000000}[unit] for number, unit in parts)


def _cap_mounts(raw):
    _require(type(raw) is bytes and len(raw) <= 1048576, 'CORE_CAP_MOUNT_LIMIT')
    rows = {}
    for line in raw.decode('ascii', 'strict').splitlines():
        fields = line.split(); separator = fields.index('-')
        _require(separator >= 6 and len(fields) == separator + 4, 'CORE_CAP_MOUNT_FORMAT')
        mid = int(fields[0]); major, minor = map(int, fields[2].split(':'))
        # This scope has simple ASCII paths; do not silently unescape aliases.
        _require(mid not in rows and not any('\\' in fields[i] for i in (3, 4, separator + 2)),
                 'CORE_CAP_MOUNT_ALIAS')
        rows[mid] = dict(mount_id=mid, device=os.makedev(major, minor), root=fields[3],
            path=fields[4], fstype=fields[separator + 1], source=fields[separator + 2],
            options=sorted(set(fields[5].split(',') + fields[separator + 3].split(','))))
    _require(rows, 'CORE_CAP_MOUNT_EMPTY')
    return rows


def _cap_uuid(fd):
    import fcntl
    import uuid
    # Linux ext4.h: _IOR('f', 44, struct fsuuid), sizeof header == 8.
    # Existing ext4 read-only ioctl, on the held filesystem fd, never a block read.
    value = bytearray(struct.pack('=II', 16, 0) + bytes(16))
    fcntl.ioctl(fd, 0x8008662c, value, True)
    _require(struct.unpack('=II', value[:8]) == (16, 0) and any(value[8:]),
             'CORE_CAP_FILESYSTEM_UUID')
    return str(uuid.UUID(bytes=bytes(value[8:])))


def _resource_pools(locators):
    """A's 32 fixed pools; nested roots are classified by longest-prefix ownership."""
    pools = []
    def add(identifier, case, amount, inodes, roots, project=None):
        pools.append(dict(pool_id=identifier, case_id=case,
            measurement_kind='PROJECT_QUOTA' if project is not None else 'OWNED_ALLOCATION',
            byte_limit=amount, inode_limit=inodes, roots=roots, project_id=project))
    def root(role, suffix):
        return dict(path=locators[role + '_parent'] + '/' + suffix, parent_role=role)
    add('shared_install', None, 67108864, 4096,
        [root('install', name) for name in (INSTALL_BASENAME, STAGING_BASENAME)])
    roles = ('state', 'quota', 'journal', 'evidence')
    add('carrier_audit', None, 8388608, 512, [root(role, SESSION) for role in roles])
    for case in CASES:
        case_id = case['case_id']; prefix = SESSION + '/' + case_id
        add(case_id + '/state', case_id, 8388608, 1536, [root(role, prefix) for role in roles])
        add(case_id + '/journal', case_id, 1048576, 128, [root('journal', prefix + '/journal')])
        add(case_id + '/capture', case_id, 20971520, 384,
            [root('evidence', prefix + '/' + name) for name in ('capture', 'declarations')])
        for row in FieldEffects.preparation_paths(case, locators)['roots']:
            add(case_id + '/quota/' + row['ref'], case_id, 1048576, 128,
                [dict(path=row['path'], parent_role='quota')], row['project_id'])
    _cap(len(pools) == 32 and sum(p['byte_limit'] for p in pools) == 188743680
        and sum(p['inode_limit'] for p in pools) == 13440, 'POOL_DEFINITION')
    return pools


def _cap_new_reservations(filesystems, locators):
    """Reserve full pool amount on every physical output device, never a spendable increase."""
    charges = {}
    for pool in _resource_pools(locators):
        keys = {(filesystems[r['parent_role']]['dev'], filesystems[r['parent_role']]['fs_uuid'])
            for r in pool['roots']}
        for key in keys:
            values = charges.setdefault(key, dict(bytes=0, inodes=0))
            values['bytes'] += pool['byte_limit']; values['inodes'] += pool['inode_limit']
    state = filesystems['state']
    values = charges[(state['dev'], state['fs_uuid'])]
    values['bytes'] += 3 * 33554432; values['inodes'] += 3 * 1024
    return charges


def _kernel_fs_type(fd):
    """Linux fstatfs type only; enough space for both supported native ABIs."""
    import ctypes
    library = ctypes.CDLL(None, use_errno=True)
    value = ctypes.create_string_buffer(256)
    library.fstatfs.argtypes = [ctypes.c_int, ctypes.c_void_p]
    library.fstatfs.restype = ctypes.c_int
    if library.fstatfs(fd, ctypes.byref(value)):
        raise OSError(ctypes.get_errno(), 'core kernel filesystem identity')
    return ctypes.c_long.from_buffer(value).value


def _admission_absent_paths(locators):
    paths = {locators['install_parent'] + '/' + name for name in (INSTALL_BASENAME, STAGING_BASENAME)}
    for role in ('state', 'quota', 'journal', 'evidence'):
        paths.add(locators[role + '_parent'] + '/' + SESSION)
    for case in CASES:
        planned = FieldEffects.preparation_paths(case, locators)
        paths.update(row['path'] for row in planned['directories'].values())
        paths.update(row['path'] for row in planned['roots'])
        paths.update(locators[role + '_parent'] + '/' + SESSION + '/' + case['case_id']
                     for role in ('state', 'quota', 'journal', 'evidence'))
    return paths


def _admission_absent_units():
    units = set()
    for case in CASES:
        units.update(row[key] for row in _phase_units(case['operation_id'], case['phases'])
                     for key in ('bootstrap_unit', 'helper_unit', 'result_reader_unit'))
        units.update(case['controller_prefix'] + '-' + role + '.service'
                     for role in ('target', 'supervisor'))
    return units


def _cap_insufficient_code(row):
    """Bounded rejection detail from the already-computed first failing pool.

    Keep bootstrap's existing CORE_[A-Z0-9_]+ stderr channel and failure status.
    No new observation, path/UUID disclosure, accounting change or release.
    NEG prefixes a negative availability; invalid detail retains the base code.
    """
    base = 'CORE_CAP_INSUFFICIENT'
    roles = row.get('roles')
    fields = ('bytes', 'inodes')
    names = [prefix + field for field in fields
             for prefix in ('historical_', 'new_required_')]
    available = [field + '_available' for field in fields]
    if (type(roles) is not list or not roles or len(roles) > len(_CAP_ROLES)
        or any(type(role) is not str or role not in _CAP_ROLES for role in roles)
        or len(set(roles)) != len(roles)
        or any(type(row.get(name)) is not int or not 0 <= row[name] < 2**64 for name in names)
        or any(type(row.get(name)) is not int or not -(2**63) <= row[name] < 2**64
               for name in available)
        or type(row.get('dev')) is not int or not 0 <= row['dev'] < 2**63
        or type(row.get('fs_uuid')) is not str or not 0 < len(row['fs_uuid']) <= 64
        or not row['fs_uuid'].isascii()):
        return base
    # Only a digest of the existing physical identity leaves this function.
    identity = _sha(canonical(dict(dev=row['dev'], fs_uuid=row['fs_uuid']))).upper()
    parts = [base, 'ROLES', *[role.upper() for role in sorted(roles)], 'POOLSHA256', identity]
    for field in fields:
        old, new, free = row['historical_' + field], row['new_required_' + field], row[field + '_available']
        for label, value in (('AVAILABLE', free), ('HISTORICAL', old), ('NEW', new),
                             ('REQUIRED', old + new), ('DEFICIT', max(0, old + new - free))):
            parts.extend((field.upper(), label, str(value) if value >= 0 else 'NEG' + str(-value)))
    code = '_'.join(parts)
    return code if len(code) <= 1024 else base


def _cap_charge(approved, filesystems, path_pool, inventory, locators):
    obligations = approved['historical_capacity_obligations']
    normalized = [dict(id=row['id'], category=row['category'], pool_roles=list(roles),
                       full_commitment=row['commitment'], no_refund=True)
                  for row, roles in zip(obligations['snapshot_rows'], _CAP_SNAPSHOT_ROLES, strict=True)]
    raw = canonical(normalized)
    _require((len(raw), _sha(raw)) == APPROVED_VECTOR_PINS['placement_normalized'],
             'CORE_CAP_PLACEMENT_PIN')
    pools = {}; byrole = {}
    for role in _CAP_ROLES:
        fs = filesystems[role]; key = (fs['dev'], fs['fs_uuid']); byrole[role] = key
        row = pools.setdefault(key, dict(dev=key[0], fs_uuid=key[1], roles=[], historical_bytes=0,
            historical_inodes=0, new_required_bytes=0, new_required_inodes=0,
            bytes_available=fs['bytes_available'], inodes_available=fs['inodes_available'], admitted=False))
        row['roles'].append(role)
        row['bytes_available'] = min(row['bytes_available'], fs['bytes_available'])
        row['inodes_available'] = min(row['inodes_available'], fs['inodes_available'])
    _require(byrole['state'] == byrole['install'], 'CORE_CAP_SYSTEM_POOL_SPLIT')
    byrole['system'] = byrole['state']
    def charge(key, values, prefix):
        for field in ('bytes', 'inodes'):
            _integer(values[field], 0, 2**63 - 1, 'CORE_CAP_AMOUNT')
            pools[key][prefix + '_' + field] += values[field]
    for source, placement in zip(obligations['snapshot_rows'], normalized, strict=True):
        expected = {byrole[role] for role in placement['pool_roles']}
        _require({path_pool(path) for path in source['covered_paths']} == expected,
                 'CORE_CAP_HISTORICAL_PLACEMENT')
        for key in expected:
            charge(key, source['commitment'], 'historical')
    for row in obligations['delta_rows']:
        key = byrole[row['device_selector'].removesuffix('_parent')]
        _require({path_pool(path) for path in row['covered_paths']} == {key}, 'CORE_CAP_DELTA_PLACEMENT')
        charge(key, row['commitment'], 'historical')
    configured = [dict(project_id=row['project'], hard_bytes=row['hard'] * 1024,
                       inode_hard_limit=row['ihard']) for row in inventory if row['hard'] > 0]
    _require(configured == obligations['configured_quota_rows'], 'CORE_CAP_CONFIGURED_QUOTA_CHANGED')
    for row in configured:
        charge(byrole['quota'], dict(bytes=row['hard_bytes'], inodes=row['inode_hard_limit']), 'historical')
    for pool in _resource_pools(locators):
        for root in pool['roots']:
            _cap(path_pool(root['path']) == byrole[root['parent_role']], 'NEW_PLACEMENT')
            # Check the fixed old namespace against the same current parents,
            # without claiming an old filesystem observation. A mount inserted
            # at an old name cannot move its full commitment to a guessed pool.
            parent = locators[root['parent_role'] + '_parent'] + '/'
            suffix = root['path'].removeprefix(parent)
            for index in (0, 1, 2, 3):
                old_session = _prior_profile(index)['session']
                if pool['pool_id'] == 'shared_install':
                    _cap(suffix in (INSTALL_BASENAME, STAGING_BASENAME), 'PRIOR_PLACEMENT')
                    old_suffix = suffix.replace(SESSION.removeprefix('lhqcore-'),
                                                old_session.removeprefix('lhqcore-'))
                else:
                    _cap(suffix == SESSION or suffix.startswith(SESSION + '/'), 'PRIOR_PLACEMENT')
                    old_suffix = old_session + suffix[len(SESSION):]
                _cap(path_pool(parent + old_suffix) == byrole[root['parent_role']], 'PRIOR_PLACEMENT')
    for key, values in _cap_new_reservations(filesystems, locators).items():
        # Each consumed batch retains its own full 32 pools and headroom.
        for _ in (0, 1, 2, 3):
            charge(key, values, 'historical')
        charge(key, values, 'new_required')
    for row in pools.values():
        row['roles'].sort()
        row['admitted'] = all(row[field + '_available'] >= row['historical_' + field] +
            row['new_required_' + field] for field in ('bytes', 'inodes'))
        if not row['admitted']:
            raise DispatchError(_cap_insufficient_code(row))
    return [pools[key] for key in sorted(pools)]


def _cap_historical_expected(approved, filesystems, locators):
    """Return-side arithmetic from pinned rows, independent of guest totals."""
    obligations = approved['historical_capacity_obligations']
    priors = approved['reconciliation']['prior_core_attempts']
    _prior_attempts(priors)
    _approved_equal(obligations['prior_commitments'],
        [_prior_commitment(value, index) for index, value in enumerate(priors)], 'PRIOR_COMMITMENT')
    byrole = {role: (fs['dev'], fs['fs_uuid']) for role, fs in filesystems.items()}
    byrole['system'] = byrole['state']
    totals = {key: dict(bytes=0, inodes=0) for key in set(byrole.values())}
    def add(key, byte_count, inode_count):
        totals[key]['bytes'] += byte_count; totals[key]['inodes'] += inode_count
    for row, roles in zip(obligations['snapshot_rows'], _CAP_SNAPSHOT_ROLES, strict=True):
        for key in {byrole[role] for role in roles}:
            add(key, row['commitment']['bytes'], row['commitment']['inodes'])
    for row in obligations['delta_rows']:
        add(byrole[row['device_selector'].removesuffix('_parent')],
            row['commitment']['bytes'], row['commitment']['inodes'])
    for row in obligations['configured_quota_rows']:
        add(byrole['quota'], row['hard_bytes'], row['inode_hard_limit'])
    # Old and new pool *identities* are distinct; their fixed role placement and
    # ceilings are identical. This is a conservative reservation, not old usage.
    for key, values in _cap_new_reservations(filesystems, locators).items():
        for _ in (0, 1, 2, 3):
            add(key, values['bytes'], values['inodes'])
    return totals


class _PoolAccounting:
    """Fixed owned-pool observations; never a full-filesystem peak claim.

    The caller records only successful dispatcher I/O. Child-internal I/O is
    deliberately absent from that event ledger and is observed at boundaries.
    """
    boundaries = frozenset(('ADMISSION', 'CONTROLLED_IO', 'CHILD_BEFORE',
        'CHILD_AFTER', 'CASE_BOUNDARY', 'FINALIZATION'))

    def __init__(self, effects):
        self.effects = effects
        _require(type(effects._admission) is dict, 'CORE_POOL_ADMISSION_REQUIRED')
        self.locators = effects.context['manifest']['locators']
        self.definitions = _resource_pools(self.locators)
        self.by_id = {row['pool_id']: row for row in self.definitions}
        self.roots = sorted(((root['path'], row['pool_id'], root['parent_role'])
            for row in self.definitions for root in row['roots']), reverse=True)
        _require(len({path for path, _, _ in self.roots}) == len(self.roots), 'CORE_POOL_ROOT_ALIAS')
        self.absence = {r['name'] for r in effects._admission['absence']
            if r['kind'] == 'path' and r['absent'] is True and r['collision'] is False}
        self.projects_absent = {r['project_id'] for r in effects._admission['absence']
            if r['kind'] == 'project' and r['absent'] is True and r['collision'] is False}
        self.created = set()
        self.pending = {row['pool_id']: dict(bytes=0, inodes=0) for row in self.definitions}
        self.dirty = set()
        self.pins = {}
        self.quota_pins = {}
        self.failed = set()
        self.rows = {}
        for definition in self.definitions:
            identifier = definition['pool_id']
            _require(all(any(root['path'] == path or root['path'].startswith(path + '/')
                for path in self.absence) for root in definition['roots']), 'CORE_POOL_ABSENCE_BASELINE')
            if definition['measurement_kind'] == 'PROJECT_QUOTA':
                _require(definition['project_id'] in self.projects_absent, 'CORE_POOL_PROJECT_BASELINE')
            self.rows[identifier] = dict(
                **{key: definition[key] for key in ('pool_id', 'case_id', 'measurement_kind',
                    'byte_limit', 'inode_limit')}, status='INCOMPLETE',
                controlled_io=dict(written_bytes=0, created_inodes=0),
                last_observation=None, bytes_maximum=None, inodes_maximum=None, missing=[])
            for field in ('last_observation', 'bytes_maximum', 'inodes_maximum'):
                self._missing(identifier, field, 'NOT_OBSERVED')

    def _guard(self):
        guard = getattr(self, '_observation_guard', None) or self.effects._effect_guard
        return guard()

    def _call(self, function, *args, **kwargs):
        return _guard_call(self._guard, function, *args, **kwargs)

    def _missing(self, identifier, field, reason):
        row = self.rows[identifier]
        item = dict(code='CORE_POOL_' + reason, role=identifier + '/' + field,
            detail_sha256=_sha(canonical(dict(pool_id=identifier, field=field, reason=reason))))
        if item not in row['missing']:
            row['missing'].append(item)
            row['missing'].sort(key=lambda value: (value['code'], value['role'], value['detail_sha256']))
        row['status'] = 'INCOMPLETE'

    def mark_incomplete(self, identifier, field, reason):
        _require(identifier in self.rows and type(field) is str and field.isascii() and field
            and type(reason) is str and reason.isascii() and reason, 'CORE_POOL_MISSING_INPUT')
        self.failed.add(identifier)
        self._missing(identifier, field, reason)

    def classify(self, path):
        self.effects._absolute(path, 'CORE_POOL_PATH')
        matches = [(root, identifier) for root, identifier, _ in self.roots
            if path == root or path.startswith(root + '/')]
        _require(bool(matches), 'CORE_POOL_PATH_OUTSIDE')
        return max(matches, key=lambda value: len(value[0]))[1]

    def before_write(self, path, requested_bytes=0, create=False, *, guard=None):
        (guard or self.effects._effect_guard)()
        _require(type(requested_bytes) is int and requested_bytes >= 0
            and type(create) is bool, 'CORE_POOL_IO_INPUT')
        identifier = self.classify(path)
        row, pending = self.rows[identifier], self.pending[identifier]
        _require(identifier not in self.failed, 'CORE_POOL_PREVIOUS_FAILURE')
        observation = row['last_observation']
        # During project setup these are only known application requests. They
        # do not purport to be an observed quota amount or an initialized root.
        _require(observation is not None or row['measurement_kind'] == 'PROJECT_QUOTA',
            'CORE_POOL_WRITE_OBSERVATION_REQUIRED')
        amount = observation['allocated_bytes'] if observation is not None else 0
        inodes = observation['allocated_inodes'] if observation is not None else 0
        _require(amount + pending['bytes'] + requested_bytes <= row['byte_limit']
            and inodes + pending['inodes'] + int(create) <= row['inode_limit'], 'CORE_POOL_REQUEST_LIMIT')
        return identifier

    def record_io(self, path, written_bytes=0, created_inodes=0):
        # Do not check clocks here: a syscall that returned late still happened.
        # This method is RAM-only, so the enclosing guard retains its original
        # failure while the actual successful short write/create is recorded.
        _require(type(written_bytes) is int and written_bytes >= 0
            and type(created_inodes) is int and created_inodes in (0, 1), 'CORE_POOL_IO_INPUT')
        identifier = self.classify(path)
        row, pending = self.rows[identifier], self.pending[identifier]
        if created_inodes:
            _require(path not in self.created, 'CORE_POOL_RECREATE')
            self.created.add(path)
        row['controlled_io']['written_bytes'] += written_bytes
        row['controlled_io']['created_inodes'] += created_inodes
        pending['bytes'] += written_bytes
        pending['inodes'] += created_inodes
        self.dirty.add(identifier)
        if row['measurement_kind'] == 'PROJECT_QUOTA' and identifier not in self.quota_pins:
            self._missing(identifier, 'last_observation', 'QUOTA_SETUP_INCOMPLETE')
        return identifier

    def quota_ready(self, case_id, roots):
        self.effects._effect_guard()
        definitions = [p for p in self.definitions if p['case_id'] == case_id
            and p['measurement_kind'] == 'PROJECT_QUOTA']
        _require(len(definitions) == 7 and type(roots) is list and len(roots) == 7,
            'CORE_POOL_QUOTA_BINDING')
        by_project = {row['project_id']: row for row in roots}
        _require(len(by_project) == 7 and set(by_project) == {p['project_id'] for p in definitions},
            'CORE_POOL_QUOTA_BINDING')
        verified = {}
        for definition in definitions:
            identifier = definition['pool_id']
            _require(identifier not in self.quota_pins, 'CORE_POOL_QUOTA_REINITIALIZATION')
            pin = by_project[definition['project_id']]
            mount = self.effects._admission['filesystems']['quota']
            _require(pin['path'] == definition['roots'][0]['path']
                and pin['device'] == mount['dev'] and pin['filesystem_uuid'] == mount['fs_uuid']
                and type(pin['inode']) is int and pin['inode'] > 0
                and pin['hard_bytes'] == definition['byte_limit']
                and pin['inode_hard_limit'] == definition['inode_limit']
                and pin['accounting'] is True and pin['enforcement'] is True
                and pin['identity_unchanged'] is True and pin['xflags'] & 512
                and pin['path'] in self.created, 'CORE_POOL_QUOTA_BINDING')
            verified[identifier] = dict(path=pin['path'], role='POOL_ROOT',
                dev=pin['device'], ino=pin['inode'], fs_uuid=pin['filesystem_uuid'],
                project_id=pin['project_id'])
        all_pins = [*self.quota_pins.values(), *verified.values()]
        _require(len({(row['dev'], row['ino']) for row in all_pins}) == len(all_pins),
            'CORE_POOL_QUOTA_ROOT_ALIAS')
        self.effects._effect_guard()
        self.quota_pins.update(verified)
        for identifier in verified:
            self.dirty.add(identifier)

    @staticmethod
    def _same(before, after):
        _require(_capacity_stat(before) == _capacity_stat(after)
            and before.st_atime_ns == after.st_atime_ns
            and before.st_blocks == after.st_blocks, 'CORE_POOL_OBJECT_DRIFT')

    def _protect(self, info, device=None, *, allowed_alias=False):
        if allowed_alias:
            _require(info.st_uid == info.st_gid == 0 and info.st_nlink == 1,
                'CORE_POOL_SYMLINK_OWNER')
        else:
            self.effects._capacity_protection(info)
        guest = self.effects._admission['guest']
        _require(info.st_gid in (0, guest['ordinary_gid'])
            and (device is None or info.st_dev == device), 'CORE_POOL_OBJECT_PROTECTION')
        _require(type(info.st_blocks) is int and info.st_blocks >= 0, 'CORE_POOL_ALLOCATION')

    def _locate(self, root):
        """Hold the admitted parent and every named component through recheck."""
        role, path = root['parent_role'], root['path']
        admitted = self.effects._admission['parents'][role]
        filesystem = self.effects._admission['filesystems'][role]
        parent_path = self.locators[role + '_parent']
        _require(admitted['path'] == parent_path and path.startswith(parent_path + '/'),
            'CORE_POOL_PARENT_BINDING')
        fds, chain = [], []
        try:
            fd = self.effects._held_directory(parent_path, guard=self._guard,
                validate=self.effects._capacity_protection)
            fds.append(fd)
            info = self._call(os.fstat, fd)
            self._protect(info, filesystem['dev'])
            _require((info.st_dev, info.st_ino, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
                == tuple(admitted[key] for key in ('dev', 'ino', 'uid', 'gid', 'mode')),
                'CORE_POOL_PARENT_DRIFT')
            _require(self._call(_cap_uuid, fd) == filesystem['fs_uuid'], 'CORE_POOL_FILESYSTEM_DRIFT')
            current = parent_path
            for part in path[len(parent_path) + 1:].split('/'):
                before = self._call(os.fstat, fd)
                try:
                    named = self._call(os.stat, part, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    chain.append((fd, before, part, None, None))
                    return fds, chain, current, before, False
                self._protect(named, filesystem['dev'])
                _require(stat.S_ISDIR(named.st_mode), 'CORE_POOL_ROOT_TYPE')
                child = self._call(os.open, part, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC |
                    os.O_NOFOLLOW | os.O_NOATIME, dir_fd=fd, release=os.close)
                fds.append(child)
                self._same(named, self._call(os.fstat, child))
                chain.append((fd, before, part, named, child))
                fd, current = child, current + '/' + part
            return fds, chain, current, self._call(os.fstat, fd), True
        except BaseException:
            for fd in reversed(fds):
                os.close(fd)
            raise

    def _recheck_chain(self, chain):
        for fd, before, name, named, child in reversed(chain):
            if named is None:
                try:
                    self._call(os.stat, name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise DispatchError('CORE_POOL_ABSENCE_DRIFT')
            else:
                self._same(named, self._call(os.fstat, child))
                self._same(named, self._call(os.stat, name, dir_fd=fd, follow_symlinks=False))
            self._same(before, self._call(os.fstat, fd))

    def _walk(self, fd, path, identifier, device, seen, totals, records, depth=0):
        before = self._call(os.fstat, fd)
        self._protect(before, device)
        key = (before.st_dev, before.st_ino)
        _require(depth <= 64 and len(path) <= 4096 and key not in seen, 'CORE_POOL_SCAN_ALIAS')
        seen.add(key)
        records.append((path, before))
        totals[0] += before.st_blocks * 512
        totals[1] += 1
        _require(totals[1] <= self.rows[identifier]['inode_limit'] + 1, 'CORE_POOL_SCAN_LIMIT')
        listing = self._call(os.open, '.', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC |
            os.O_NOFOLLOW | os.O_NOATIME, dir_fd=fd, release=os.close)
        try:
            entries = self._call(os.scandir, listing, release=lambda value: value.close())
            with entries:
                names = []
                while (entry := self._call(next, entries, None)) is not None:
                    names.append(entry.name)
                    _require(len(names) <= 13440, 'CORE_POOL_SCAN_LIMIT')
                _require(len(names) == len(set(names)), 'CORE_POOL_SCAN_DRIFT')
        finally:
            os.close(listing)
        for name in sorted(names):
            _require(type(name) is str and name.isascii() and
                re.fullmatch(r'[A-Za-z0-9._-]+', name) and name not in ('.', '..'), 'CORE_POOL_NAME')
            child_path = path + '/' + name
            # Classification precedes stat, open or any payload access. This is
            # essential for all seven project roots, especially H11 results.
            if self.classify(child_path) != identifier:
                continue
            named = self._call(os.stat, name, dir_fd=fd, follow_symlinks=False)
            allowed_alias = stat.S_ISLNK(named.st_mode) and identifier == 'shared_install' \
                and getattr(self.effects, '_venv_alias_pending', False) \
                and child_path == self.locators['install_parent'] + '/' + INSTALL_BASENAME + '/runtime/lib64'
            self._protect(named, device, allowed_alias=allowed_alias)
            if stat.S_ISDIR(named.st_mode):
                child = self._call(os.open, name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC |
                    os.O_NOFOLLOW | os.O_NOATIME, dir_fd=fd, release=os.close)
                try:
                    self._same(named, self._call(os.fstat, child))
                    self._walk(child, child_path, identifier, device, seen, totals, records, depth + 1)
                    self._same(named, self._call(os.fstat, child))
                finally:
                    os.close(child)
            else:
                _require((stat.S_ISREG(named.st_mode) and named.st_nlink == 1) or allowed_alias,
                    'CORE_POOL_FILE_TYPE')
                child = self._call(os.open, name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=fd, release=os.close)
                try:
                    self._same(named, self._call(os.fstat, child))
                    # The original installer validates/removes this one alias.
                    # Allocation accounting never follows or reads the link;
                    # readlink itself would mutate an old symlink's atime.
                    key = (named.st_dev, named.st_ino)
                    _require(key not in seen, 'CORE_POOL_SCAN_ALIAS')
                    seen.add(key)
                    records.append((child_path, named))
                    totals[0] += named.st_blocks * 512
                    totals[1] += 1
                    self._same(named, self._call(os.fstat, child))
                finally:
                    os.close(child)
            self._same(named, self._call(os.stat, name, dir_fd=fd, follow_symlinks=False))
            _require(totals[1] <= self.rows[identifier]['inode_limit'] + 1, 'CORE_POOL_SCAN_LIMIT')
        self._same(before, self._call(os.fstat, fd))

    def _recheck_objects(self, records):
        # Recheck every recorded object after the complete first pass. Reuse a
        # parent descriptor only within this pass; no allocation or identity is
        # cached across observations. The full named parent walk is checked on
        # both sides of each group, so a renamed held directory is not enough.
        by_path = dict(records)
        _require(len(by_path) == len(records), 'CORE_POOL_SCAN_ALIAS')
        groups = {}
        for path, before in records:
            parsed = PurePosixPath(path)
            groups.setdefault(str(parsed.parent), []).append((parsed.name, before))
        for parent_path, children in groups.items():
            parent = self.effects._held_directory(parent_path,
                guard=self._guard, validate=self.effects._capacity_protection)
            try:
                parent_before = self._call(os.fstat, parent)
                if parent_path in by_path:
                    self._same(by_path[parent_path], parent_before)
                else:
                    admitted = [row for row in self.effects._admission['parents'].values()
                        if row['path'] == parent_path]
                    if admitted:
                        actual = (parent_before.st_dev, parent_before.st_ino, parent_before.st_uid,
                            parent_before.st_gid, stat.S_IMODE(parent_before.st_mode))
                        _require(all(actual == tuple(expected[key] for key in
                            ('dev', 'ino', 'uid', 'gid', 'mode')) for expected in admitted),
                            'CORE_POOL_PARENT_DRIFT')
                    else:
                        # A case root's parent belongs to carrier, and a capture
                        # root's parent belongs to state. They are fixed owned
                        # roots, not new uncharged external ancestors.
                        _require(parent_path in self.created and any(root == parent_path
                            for root, *_ in self.roots), 'CORE_POOL_PARENT_BINDING')
                        expected = self.pins.get(parent_path)
                        _require(expected is None or expected ==
                            (parent_before.st_dev, parent_before.st_ino), 'CORE_POOL_PARENT_DRIFT')
                for name, before in children:
                    self._same(before, self._call(os.stat, name, dir_fd=parent, follow_symlinks=False))
                    fd = self._call(os.open, name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                        dir_fd=parent, release=os.close)
                    try:
                        self._same(before, self._call(os.fstat, fd))
                        self._same(before, self._call(os.stat, name, dir_fd=parent, follow_symlinks=False))
                    finally:
                        os.close(fd)
                self._same(parent_before, self._call(os.fstat, parent))
                named = self.effects._held_directory(parent_path,
                    guard=self._guard, validate=self.effects._capacity_protection)
                try:
                    self._same(parent_before, self._call(os.fstat, named))
                    self._same(parent_before, self._call(os.fstat, parent))
                finally:
                    os.close(named)
            finally:
                os.close(parent)

    def _owned(self, definition):
        identifier = definition['pool_id']
        seen, identities, totals, records = set(), {}, [0, 0], []
        existing = False
        for root in definition['roots']:
            fds, chain, current, info, found = self._locate(root)
            try:
                filesystem = self.effects._admission['filesystems'][root['parent_role']]
                if found:
                    _require(definition['measurement_kind'] != 'PROJECT_QUOTA',
                        'CORE_POOL_QUOTA_UNREGISTERED')
                    existing = True
                    _require(root['path'] in self.created, 'CORE_POOL_ROOT_CREATION_UNKNOWN')
                    pin = (info.st_dev, info.st_ino)
                    previous = self.pins.get(root['path'])
                    _require(previous is None or previous == pin, 'CORE_POOL_ROOT_REPLACED')
                    _require(all(other == root['path'] or value != pin for other, value in self.pins.items()),
                        'CORE_POOL_ROOT_ALIAS')
                    self.pins[root['path']] = pin
                    self._walk(fds[-1], root['path'], identifier, filesystem['dev'], seen, totals, records)
                else:
                    _require(root['path'] not in self.pins and not any(path == root['path']
                        or path.startswith(root['path'] + '/') for path in self.created),
                        'CORE_POOL_UNPROVEN_ABSENCE')
                identity = dict(path=current, role='POOL_ROOT' if found else 'ABSENCE_PARENT',
                    dev=info.st_dev, ino=info.st_ino, fs_uuid=filesystem['fs_uuid'], project_id=None)
                _require(current not in identities or identities[current] == identity, 'CORE_POOL_ROOT_ALIAS')
                identities[current] = identity
                self._recheck_chain(chain)
            finally:
                for fd in reversed(fds):
                    os.close(fd)
        self._recheck_objects(records)
        _require(1 <= len(identities) <= 16, 'CORE_POOL_IDENTITY_COUNT')
        return ('OWNED_ALLOCATION' if existing else 'VERIFIED_ABSENCE', totals,
            [identities[path] for path in sorted(identities)], None)

    def _quota(self, definition, inventory, enforcement):
        identifier = definition['pool_id']
        pin = self.quota_pins[identifier]
        actual = inventory.get(definition['project_id'])
        _require(actual is not None and actual['hard'] * 1024 == definition['byte_limit']
            and actual['ihard'] == definition['inode_limit'] and enforcement & 48 == 48,
            'CORE_POOL_QUOTA_LIMIT')
        for key in ('space', 'inodes'):
            _require(type(actual[key]) is int and actual[key] >= 0, 'CORE_POOL_QUOTA_VALUE')
        quota = dict(project_id=definition['project_id'], hard_bytes=actual['hard'] * 1024,
            hard_inodes=actual['ihard'], used_bytes=actual['space'], used_inodes=actual['inodes'],
            enforcement_flags=enforcement)
        return 'PROJECT_QUOTA', [actual['space'], actual['inodes']], [dict(pin)], quota

    def _observation(self, definition, boundary, values):
        method, totals, identities, quota = values
        now = self._call(self.effects.now)
        deadlines = self.effects.context['guest_deadlines']
        _require(now['boot_id'] == deadlines['boot_id'], 'CORE_POOL_CLOCK_BOOT')
        result = dict(method=method, boundary=boundary,
            boottime_ns=now['boottime_ns'], monotonic_ns=now['monotonic_ns'],
            allocated_bytes=totals[0], allocated_inodes=totals[1], identities=identities, quota=quota)
        previous = self.rows[definition['pool_id']]['last_observation']
        _require(previous is None or all(result[key] >= previous[key]
            for key in ('boottime_ns', 'monotonic_ns')), 'CORE_POOL_CLOCK_ORDER')
        result['source_sha256'] = _sha(canonical(dict(pool_id=definition['pool_id'],
            case_id=definition['case_id'], observation=result)))
        return result

    def observe(self, boundary, pool_ids=None, *, guard=None):
        # A caller may supply the original outer finalization guard, including
        # its reserved interval. No clock origin or deadline is created here.
        _require(guard is None or callable(guard), 'CORE_POOL_GUARD')
        _require(getattr(self, '_observation_guard', None) is None, 'CORE_POOL_REENTRANT')
        self._observation_guard = guard
        try:
            return self._observe(boundary, pool_ids)
        finally:
            self._observation_guard = None

    def _observe(self, boundary, pool_ids):
        _require(boundary in self.boundaries, 'CORE_POOL_BOUNDARY')
        requested = list(self.rows) if pool_ids is None else list(pool_ids)
        _require(requested and len(requested) == len(set(requested))
            and set(requested) <= set(self.rows), 'CORE_POOL_SELECTION')
        selected = [row for row in self.definitions if row['pool_id'] in requested]
        try:
            self._guard()
        except BaseException as error:
            reason = str(error) if isinstance(error, DispatchError) else type(error).__name__
            for definition in selected:
                self.mark_incomplete(definition['pool_id'], 'last_observation', reason)
            raise
        inventory = None
        enforcement = None
        for definition in selected:
            identifier = definition['pool_id']
            _require(identifier not in self.failed, 'CORE_POOL_PREVIOUS_FAILURE')
            row = self.rows[identifier]
            try:
                if definition['measurement_kind'] == 'PROJECT_QUOTA' and identifier in self.quota_pins:
                    if inventory is None:
                        enforcement = self._call(self.effects._capacity_quota_enforcement, guard=self._guard)
                        raw = self._call(self.effects._capacity_quota_inventory, guard=self._guard)
                        inventory = {item['project']: item for item in raw}
                        _require(len(inventory) == len(raw) and enforcement ==
                            self._call(self.effects._capacity_quota_enforcement, guard=self._guard), 'CORE_POOL_QUOTA_DRIFT')
                    values = self._quota(definition, inventory, enforcement)
                elif definition['measurement_kind'] == 'PROJECT_QUOTA' and any(path == definition['roots'][0]['path']
                        or path.startswith(definition['roots'][0]['path'] + '/') for path in self.created):
                    self._missing(identifier, 'last_observation', 'QUOTA_SETUP_INCOMPLETE')
                    continue
                else:
                    values = self._owned(definition)
                    _require(definition['measurement_kind'] != 'PROJECT_QUOTA'
                        or values[0] == 'VERIFIED_ABSENCE', 'CORE_POOL_QUOTA_UNREGISTERED')
                observed = self._observation(definition, boundary, values)
                row['last_observation'] = observed
                for field, amount in (('bytes_maximum', 'allocated_bytes'), ('inodes_maximum', 'allocated_inodes')):
                    if row[field] is None or observed[amount] >= row[field][amount]:
                        row[field] = copy.deepcopy(observed)
                row['missing'] = []
                row['status'] = 'ABSENT' if observed['method'] == 'VERIFIED_ABSENCE' else 'OBSERVED'
                self.pending[identifier] = dict(bytes=0, inodes=0)
                self.dirty.discard(identifier)
                _require(observed['allocated_bytes'] <= row['byte_limit']
                    and observed['allocated_inodes'] <= row['inode_limit'], 'CORE_POOL_OBSERVED_LIMIT')
            except BaseException as error:
                reason = str(error) if isinstance(error, DispatchError) else type(error).__name__
                self.mark_incomplete(identifier, 'last_observation', reason)
                raise
        self._totals(enforce=True)
        return [copy.deepcopy(self.rows[row['pool_id']]) for row in selected]

    def _totals(self, *, enforce=False):
        maxima = [(row['case_id'], row['bytes_maximum'], row['inodes_maximum']) for row in self.rows.values()]
        if enforce:
            for case_id in (None, *(case['case_id'] for case in CASES)):
                selected = maxima if case_id is None else [row for row in maxima if row[0] == case_id]
                amount = sum(row[1]['allocated_bytes'] for row in selected if row[1] is not None)
                inodes = sum(row[2]['allocated_inodes'] for row in selected if row[2] is not None)
                if amount > (188743680 if case_id is None else 37748736) or inodes > (13440 if case_id is None else 2944):
                    for definition in self.definitions:
                        if case_id is None or definition['case_id'] == case_id:
                            if amount > (188743680 if case_id is None else 37748736):
                                self.mark_incomplete(definition['pool_id'], 'bytes_maximum', 'AGGREGATE_LIMIT')
                            if inodes > (13440 if case_id is None else 2944):
                                self.mark_incomplete(definition['pool_id'], 'inodes_maximum', 'AGGREGATE_LIMIT')
                    raise DispatchError('CORE_POOL_AGGREGATE_LIMIT')
        if any(row['status'] == 'INCOMPLETE' or row['missing'] for row in self.rows.values()):
            return dict(bytes=None, inodes=None)
        return dict(bytes=sum(row[1]['allocated_bytes'] for row in maxima),
            inodes=sum(row[2]['allocated_inodes'] for row in maxima))

    def snapshot(self, completion_adjustment):
        # Snapshot does not collect more evidence or hide an earlier failed
        # boundary. It remains usable after a deadline failure for reporting.
        rows = copy.deepcopy(list(self.rows.values()))
        for row in rows:
            identifier = row['pool_id']
            if identifier in self.dirty:
                item = dict(code='CORE_POOL_UNOBSERVED_IO', role=identifier + '/last_observation',
                    detail_sha256=_sha(canonical(dict(pool_id=identifier, reason='UNOBSERVED_IO'))))
                if item not in row['missing']:
                    row['missing'].append(item)
                row['status'] = 'INCOMPLETE'
            if row['last_observation'] is None or row['last_observation']['boundary'] != 'FINALIZATION':
                item = dict(code='CORE_POOL_FINALIZATION_MISSING', role=identifier + '/last_observation',
                    detail_sha256=_sha(canonical(dict(pool_id=identifier, reason='FINALIZATION_MISSING'))))
                if item not in row['missing']:
                    row['missing'].append(item)
                row['status'] = 'INCOMPLETE'
            row['missing'].sort(key=lambda value: (value['code'], value['role'], value['detail_sha256']))
        missing = sorted((item for row in rows for item in row['missing']),
            key=lambda value: (value['code'], value['role'], value['detail_sha256']))
        totals = dict(bytes=None, inodes=None) if missing else self._totals()
        preimage = dict(completion_adjustment=copy.deepcopy(completion_adjustment),
            pools=rows, observed_maxima_sum=totals)
        return dict(schema='local-hand-q2-core-resource-accounting/v1',
            basis='APPLICATION_AND_OBSERVED_OWNED_ALLOCATION', full_guest_filesystem_peak_proven=False,
            **preimage, snapshot_sha256=_sha(canonical(preimage)), missing=missing)


class FieldEffects:
    """Inert construction; protected fd-relative effects. See field_readiness gaps."""

    def __init__(self, context):
        self.context = context
        self.held = []
        self._admission = None
        self._installation = None
        self._candidate_root = None
        self._persistence_ready = False
        self._installation_receipt = None
        self._install_roots = []
        self._install_temp = None
        self._install_commands = []
        self._shared_observed_bytes = 0
        self._shared_observed_inodes = 0
        self._venv_alias_pending = False
        self._started_boottime_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        self._started_cpu_ns = time.process_time_ns()

    def close(self):
        self.__dict__.pop('_clock_fds', None)
        while self.held:
            os.close(self.held.pop())

    def readiness(self):
        return field_readiness()

    def now(self):
        path = '/proc/sys/kernel/random'
        cached = getattr(self, '_clock_fds', None)
        opened = []
        def pin(info):
            return (info.st_dev, info.st_ino, info.st_mode, info.st_uid,
                    info.st_gid)
        def ancestors_match(ancestors):
            for descriptor, name, expected in ancestors:
                current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                _effect(stat.S_ISDIR(current.st_mode) and pin(current) == expected,
                    'BOOT_ID_PARENT')
        try:
            if cached is None:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
                parent = os.open('/', flags)
                opened.append(parent)
                ancestors = [(None, '/', pin(os.fstat(parent)))]
                for component in PurePosixPath(path).parts[1:]:
                    child = os.open(component, flags, dir_fd=parent)
                    opened.append(child)
                    ancestors.append((parent, component, pin(os.fstat(child))))
                    parent = child
                ancestors = tuple(ancestors)
                parent_pin = ancestors[-1][2]
                fd = os.open('boot_id', os.O_RDONLY | os.O_CLOEXEC
                    | getattr(os, 'O_NOFOLLOW', 0), dir_fd=parent)
                opened.append(fd)
                file_pin = pin(os.fstat(fd))
            else:
                parent, fd, parent_pin, file_pin, ancestors = cached
            ancestors_match(ancestors)
            _effect(pin(os.fstat(parent)) == parent_pin
                and stat.S_ISDIR(parent_pin[2]), 'BOOT_ID_PARENT')
            before = os.fstat(fd)
            _effect(stat.S_ISREG(before.st_mode) and pin(before) == file_pin
                == pin(os.stat('boot_id', dir_fd=parent, follow_symlinks=False)), 'BOOT_ID')
            # The descriptors are reused, never the boot bytes or clock values.
            raw = os.pread(fd, 65, 0)
            _effect(len(raw) <= 64 and os.pread(fd, 1, len(raw)) == b'', 'BOOT_ID')
            after = os.fstat(fd)
            _effect(_admit_stat(before) == _admit_stat(after)
                and pin(after) == file_pin
                == pin(os.stat('boot_id', dir_fd=parent, follow_symlinks=False))
                and pin(os.fstat(parent)) == parent_pin
                == pin(os.stat(path, follow_symlinks=False)), 'BOOT_ID')
            try:
                boot_id = raw.decode('ascii', 'strict').strip()
            except UnicodeError as error:
                raise _effect.error('BOOT_ID') from error
            _effect(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',
                    boot_id) is not None, 'BOOT_ID')
            result = {'boot_id': boot_id,
                'boottime_ns': time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                'monotonic_ns': time.clock_gettime_ns(time.CLOCK_MONOTONIC)}
            if cached is None:
                self.held.extend(opened)
                self._clock_fds = (parent, fd, parent_pin, file_pin, ancestors)
                opened.clear()
            return result
        finally:
            for descriptor in reversed(opened):
                os.close(descriptor)

    @staticmethod
    def _absolute(path, code="CORE_EFFECT_ABSOLUTE_PATH"):
        _require(type(path) is str and path.isascii() and path.startswith("/")
            and not path.startswith("//") and len(path) <= 4096
            and "\\" not in path and "\0" not in path, code)
        parsed = PurePosixPath(path)
        _require(parsed.as_posix() == path and all(part not in ("", ".", "..")
                for part in parsed.parts[1:]), code)
        return parsed

    @staticmethod
    def _held_directory(path, *, guard=None, validate=None):
        """Walk an absolute directory from a held slash fd without symlinks."""
        parsed = FieldEffects._absolute(path)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
        call = partial(_guard_call, guard)
        current = call(os.open, "/", flags, release=os.close)
        try:
            if validate: validate(call(os.fstat, current))
            for component in parsed.parts[1:]:
                following = call(os.open, component, flags, dir_fd=current, release=os.close)
                os.close(current)
                current = following
                if validate: validate(call(os.fstat, current))
            info = call(os.fstat, current)
            _effect(stat.S_ISDIR(info.st_mode), "DIRECTORY")
            return current
        except BaseException:
            os.close(current)
            raise

    @staticmethod
    def stable_read_at(directory_fd, name, *, maximum, expected_mode=None,
        noatime=True, guard=None):
        _effect(type(directory_fd) is int and type(name) is str
            and re.fullmatch(r"[A-Za-z0-9._-]+", name) is not None
            and type(maximum) is int and 0 <= maximum <= MEMBER_LIMIT,
            "READ_INPUT")
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
        if noatime:
            flags |= getattr(os, "O_NOATIME", 0)
        call = partial(_guard_call, guard)
        fd = call(os.open, name, flags, dir_fd=directory_fd, release=os.close)
        try:
            before = call(os.fstat, fd)
            _effect(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 <= before.st_size <= maximum, "READ_FILE")
            if expected_mode is not None:
                _effect(stat.S_IMODE(before.st_mode) == expected_mode,
                    "READ_MODE")
            raw = bytearray()
            while len(raw) <= maximum:
                part = call(os.read, fd, min(65536, maximum + 1 - len(raw)))
                if not part:
                    break
                raw.extend(part)
            after = call(os.fstat, fd)
            stable = _capacity_stat
            _effect(len(raw) <= maximum and stable(before) == stable(after)
                and len(raw) == after.st_size, "READ_CHANGED")
            result = bytes(raw)
            return result, {"dev": after.st_dev, "ino": after.st_ino,
                "mode": stat.S_IMODE(after.st_mode), "uid": after.st_uid,
                "gid": after.st_gid, "nlink": after.st_nlink,
                "bytes": after.st_size, "sha256": _sha(result)}
        finally:
            os.close(fd)

    @staticmethod
    def stable_read(path, *, maximum, expected_mode=None, noatime=True, guard=None):
        parsed = FieldEffects._absolute(path)
        _effect(len(parsed.parts) > 1, "READ_PATH")
        parent = FieldEffects._held_directory(str(parsed.parent), guard=guard)
        try:
            return FieldEffects.stable_read_at(parent, parsed.name, maximum=maximum,
                expected_mode=expected_mode,
                noatime=noatime, guard=guard)
        finally:
            os.close(parent)

    @staticmethod
    def create_only_at(directory_fd, name, raw, *, mode, guard=None, accounting=None, path=None):
        _effect(type(directory_fd) is int and type(name) is str
            and re.fullmatch(r"[A-Za-z0-9._-]+", name) is not None
            and type(raw) is bytes and mode in (384, 420, 493),
            "CREATE_INPUT")
        call = partial(_guard_call, guard)
        _effect(accounting is None or type(path) is str, 'CREATE_ACCOUNTING_PATH')
        mutate = partial(_accounting_io, accounting, guard, path)
        parent_before = call(os.fstat, directory_fd)
        _effect(stat.S_ISDIR(parent_before.st_mode), "CREATE_PARENT")
        flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0))
        fd = mutate(os.open, name, flags, mode, dir_fd=directory_fd, release=os.close, create=True)
        created = None
        try:
            call(os.fchmod, fd, mode)
            offset = 0
            while offset < len(raw):
                part = raw[offset:offset + 65536]
                wrote = mutate(os.write, fd, part, write=True, requested_bytes=len(part))
                _effect(wrote > 0, "CREATE_WRITE")
                offset += wrote
            mutate(os.fsync, fd)
            created = call(os.fstat, fd)
            _effect(stat.S_ISREG(created.st_mode) and created.st_nlink == 1
                and created.st_size == len(raw)
                and stat.S_IMODE(created.st_mode) == mode,
                "CREATE_FILE")
        finally:
            os.close(fd)
        reread, identity = FieldEffects.stable_read_at(
            directory_fd, name, maximum=len(raw), expected_mode=mode, guard=guard)
        _effect(reread == raw and created is not None
            and (identity["dev"], identity["ino"]) == (created.st_dev, created.st_ino),
            "CREATE_REREAD")
        mutate(os.fsync, directory_fd)
        parent_after = call(os.fstat, directory_fd)
        _effect((parent_before.st_dev, parent_before.st_ino)
            == (parent_after.st_dev, parent_after.st_ino),
            "CREATE_PARENT_CHANGED")
        return identity

    @staticmethod
    def create_only(path, raw, *, mode, guard=None, accounting=None):
        parsed = FieldEffects._absolute(path)
        _effect(len(parsed.parts) > 1, "CREATE_PATH")
        parent = FieldEffects._held_directory(str(parsed.parent), guard=guard)
        try:
            return FieldEffects.create_only_at(parent, parsed.name, raw, mode=mode,
                guard=guard, accounting=accounting, path=path)
        finally:
            os.close(parent)

    def verify_install_inputs(self):
        return verify_install_inputs(self.context)

    @staticmethod
    def preparation_paths(case, locators):
        """Map A's relative intents to fixed absolute candidate preparation paths."""
        _prep_require(case in CASES and type(locators) is dict,
            'PATH_INPUT')
        parents = {role: locators.get(role + "_parent")
            for role in _fields('state quota journal evidence')}
        for value in parents.values():
            FieldEffects._absolute(value, "CORE_EFFECT_PREPARATION_PARENT")
        _prep_require(len(set(parents.values())) == len(parents),
            'PARENT_ALIAS')
        directories = {}
        for row in _planned_directories(case):
            relative = PurePosixPath(row["relative_path"])
            target = PurePosixPath(parents[row["parent_role"]]).joinpath(relative)
            directories[row["role"]] = dict(row, path=target.as_posix())
        roots = []
        for planned in _planned_roots(case):
            role = "store_parent" if planned["slot"] == "store" else \
                "profile_" + planned["role"]
            basename = PurePosixPath(planned["path"]).name
            roots.append(dict(planned, path=(PurePosixPath(directories[role]["path"])
                        / basename).as_posix()))
        _prep_require(len({row["path"] for row in directories.values()}) == len(DIRECTORY_ROLES)
            and len({row["path"] for row in roots}) == 7,
            'PATH_ALIAS')
        return {"directories": directories, "roots": roots}

    def _persistence_path(self, case_id, logical):
        _effect.path(logical, 'PERSIST_LOGICAL')
        locators = self.context["manifest"]["locators"]
        if logical.startswith("carrier/"):
            suffix = logical.split("/", 1)[1]
            _effect("/" not in suffix, "PERSIST_LOGICAL")
            return str(PurePosixPath(locators["state_parent"]) / SESSION / "carrier" / suffix)
        prefix = "cases/" + case_id + "/"
        _effect(case_id in {case["case_id"] for case in CASES}
            and logical.startswith(prefix), "PERSIST_CASE")
        suffix = logical[len(prefix):]
        if suffix == "intent.json":
            return str(PurePosixPath(locators["state_parent"]) / SESSION / "carrier"
                / "intents" / (case_id + ".json"))
        _effect(suffix.startswith("reservation/")
            and "/" not in suffix[len("reservation/"):],
            "PERSIST_LOGICAL")
        return str(PurePosixPath(locators["state_parent"]) / SESSION / case_id
            / "reservation" / suffix[len("reservation/"):])


    def _capacity_call(self, function, *args, **kwargs):
        return _guard_call(self._effect_guard, function, *args, **kwargs)

    def _capacity_directory(self, path, *, guard=None):
        fd, info, missing = self._capacity_path(path) if guard is None else self._capacity_path(path, guard=guard)
        if missing or not stat.S_ISDIR(info.st_mode):
            os.close(fd)
            raise DispatchError('CORE_CAP_DIRECTORY_MISSING')
        return fd

    def _capacity_kernel(self, path, maximum=1048576, *, dir_fd=None, guard=None):
        call = self._capacity_call if guard is None else partial(_guard_call, guard)
        actual_guard = self._effect_guard if guard is None else guard
        parent = None
        expected = 0x63677270  # CGROUP2_SUPER_MAGIC for fd-relative fixed facts.
        if dir_fd is None:
            self._absolute(path)
            allowed_proc = {'/proc/1/comm', '/proc/self/mountinfo', '/proc/self/cgroup',
                '/proc/sys/kernel/random/boot_id'}
            allowed_sys = {'/sys/devices/virtual/dmi/id/sys_vendor',
                '/sys/devices/virtual/dmi/id/product_name'}
            if path in allowed_proc or re.fullmatch(r'/proc/self/fdinfo/[0-9]+', path):
                expected = 0x9fa0  # PROC_SUPER_MAGIC
                path = path.replace('/proc/self/', '/proc/' + str(os.getpid()) + '/')
            elif path in allowed_sys:
                expected = 0x62656572  # SYSFS_MAGIC
            else:
                _cap(path == '/sys/fs/cgroup/cgroup.controllers', 'KERNEL_PATH')
            parsed = PurePosixPath(path)
            parent = self._held_directory(str(parsed.parent), guard=actual_guard,
                validate=self._capacity_protection)
            dir_fd, path = parent, parsed.name
        else:
            _cap(path in {'cgroup.controllers', 'cpu.max', 'cpu.stat', 'memory.max',
                'memory.swap.max', 'memory.peak', 'pids.max', 'pids.peak',
                'cgroup.events', 'cgroup.procs'}, 'KERNEL_PATH')
        try:
            _cap(call(_kernel_fs_type, dir_fd) == expected, 'KERNEL_FILESYSTEM')
            fd = call(os.open, path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=dir_fd, release=os.close)
            try:
                before = call(os.fstat, fd)
                _cap(stat.S_ISREG(before.st_mode) and call(_kernel_fs_type, fd) == expected,
                    'KERNEL_FILESYSTEM')
                raw = bytearray()
                while len(raw) <= maximum:
                    part = call(os.read, fd, min(65536, maximum + 1 - len(raw)))
                    if not part:
                        break
                    raw.extend(part)
                _cap(len(raw) <= maximum, 'KERNEL_LIMIT')
                _cap(_admit_stat(before) == _admit_stat(call(os.fstat, fd))
                    == _admit_stat(call(os.stat, path, dir_fd=dir_fd, follow_symlinks=False)),
                    'KERNEL_DRIFT')
                return bytes(raw)
            finally:
                os.close(fd)
        finally:
            if parent is not None:
                os.close(parent)

    def _capacity_filesystem(self, path, mounts):
        fd = self._capacity_directory(path)
        try:
            before = self._capacity_call(os.fstat, fd)
            _require(before.st_uid == before.st_gid == 0 and stat.S_IMODE(before.st_mode) in (448, 493),
                     'CORE_CAP_PARENT_PROTECTION')
            info = self._capacity_kernel('/proc/self/fdinfo/' + str(fd), 4096).decode('ascii')
            matches = re.findall(r'^mnt_id:\s*([0-9]+)$', info, re.MULTILINE)
            _require(len(matches) == 1 and int(matches[0]) in mounts, 'CORE_CAP_MOUNT_BINDING')
            mount = mounts[int(matches[0])]
            _require(mount['device'] == before.st_dev and mount['fstype'] == 'ext4'
                     and mount['root'] == '/' and 'rw' in mount['options'], 'CORE_CAP_FILESYSTEM')
            value = self._capacity_call(_cap_uuid, fd)
            fs = self._capacity_call(os.fstatvfs, fd)
            _require(_admit_stat(before) == _admit_stat(self._capacity_call(os.fstat, fd))
                     and fs.f_frsize > 0 and fs.f_favail <= fs.f_files,
                     'CORE_CAP_PARENT_DRIFT')
            parent = dict(path=path, dev=before.st_dev, ino=before.st_ino,
                mode=stat.S_IMODE(before.st_mode), uid=before.st_uid, gid=before.st_gid,
                nlink=before.st_nlink, mount_id=mount['mount_id'], fs_uuid=value)
            public = dict(mount_id=mount['mount_id'], dev=before.st_dev, fs_uuid=value,
                fstype=mount['fstype'], mount_options=mount['options'],
                bytes_available=fs.f_bavail * fs.f_frsize, inodes_available=fs.f_favail)
            detail = dict(path=mount['path'], source=mount['source'], device=before.st_dev, uuid=value,
                total_bytes=fs.f_blocks * fs.f_frsize, total_inodes=fs.f_files,
                available_bytes=public['bytes_available'], free_inodes=fs.f_favail)
            return parent, public, detail
        finally:
            os.close(fd)

    def _capacity_path(self, path, *, absent=False, guard=None):
        call = self._capacity_call if guard is None else partial(_guard_call, guard)
        parts = self._absolute(path).parts[1:]
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
        fd = call(os.open, '/', flags, release=os.close)
        try:
            self._capacity_protection(call(os.fstat, fd))
            for i, part in enumerate(parts):
                try:
                    info = call(os.stat, part, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    parent = call(os.fstat, fd)
                    return fd, parent, True
                _require(not stat.S_ISLNK(info.st_mode), 'CORE_CAP_PATH_SYMLINK')
                self._capacity_protection(info)
                if i == len(parts) - 1:
                    _require(not absent, 'CORE_CAP_OBJECT_EXISTS')
                    if not stat.S_ISDIR(info.st_mode):
                        return fd, info, False
                _require(stat.S_ISDIR(info.st_mode), 'CORE_CAP_PATH_TYPE')
                child = call(os.open, part, flags, dir_fd=fd, release=os.close)
                try:
                    _cap(_admit_stat(info) == _admit_stat(call(os.fstat, child)), 'PATH_DRIFT')
                except BaseException:
                    os.close(child)
                    raise
                os.close(fd); fd = child
            _require(not absent, 'CORE_CAP_OBJECT_EXISTS')
            return fd, call(os.fstat, fd), False
        except BaseException:
            os.close(fd)
            raise

    def _capacity_user_bus(self):
        result = {}
        for path, names in (('/run/user/1100',('bus',)),('/run/user/1100/systemd',('private',))):
            fd = self._capacity_directory(path)
            try:
                info = self._capacity_call(os.fstat,fd)
                _require(info.st_uid == info.st_gid == 1100
                    and stat.S_IMODE(info.st_mode) in ((0o700,) if path.endswith('/1100') else (0o700,0o755)),
                    'CORE_RUNTIME_USER_DIRECTORY')
                result[path] = _admit_stat(info)
                for name in names:
                    item = self._capacity_call(os.stat,name,dir_fd=fd,follow_symlinks=False)
                    _require(stat.S_ISSOCK(item.st_mode) and item.st_uid == item.st_gid == 1100,
                        'CORE_RUNTIME_USER_SOCKET')
                    result[path+'/'+name] = _admit_stat(item)
                _require(_admit_stat(self._capacity_call(os.stat,path,follow_symlinks=False)) == _admit_stat(info),
                    'CORE_RUNTIME_USER_DIRECTORY_DRIFT')
            finally:os.close(fd)
        return result

    def _capacity_systemctl(self, arguments, program, *, prior_observation=None, user_uid=None):
        old_show = any(arguments[:3] == ['show', '--all', _prior_profile(index)['unit']]
                       for index in (0, 1, 2, 3))
        _require(old_show == (prior_observation is not None), 'CORE_PRIOR_SCOPE_SHOW_POLICY')
        bus = None
        if user_uid is not None:
            import pwd
            binding = _validate_runtime_binding(_approved_inputs_envelope(self.context)['reconciliation']['journal_transition']['runtime_parent_binding'])
            account = self._capacity_call(pwd.getpwuid,1100)
            _require(user_uid == 1100 and dict(name=account.pw_name,uid=account.pw_uid,gid=account.pw_gid) == binding['account']
                and prior_observation is None and arguments[:2] == ['show',binding['parents']['retained_ordinary']['unit']],
                'CORE_RUNTIME_USER_QUERY')
            bus = self._capacity_user_bus()
        def verify():
            reader = _admit_reader(self._effect_guard, '/', 0)
            try:
                current = _admit_program(reader, program['path'])
                _require({key: current[key] for key in PROGRAM_FIELDS} == program, 'CORE_CAP_SYSTEMCTL_CHANGED')
                return current
            finally:
                reader.close()
        policy = dict(argv=[program['path'], '--user' if user_uid is not None else '--system', '--no-pager', '--no-ask-password', *arguments],
            environment={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'SYSTEMD_COLORS': '0'},
            limits=dict(command_seconds=5, command_cpu_seconds=2, stdout_bytes=32768,
                        stderr_bytes=32768, combined_output_bytes=32768))
        if user_uid is not None:
            policy['environment'].update(XDG_RUNTIME_DIR='/run/user/1100',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1100/bus')
        if prior_observation is None:
            if user_uid is None:raw, stderr, receipt = _admit_run_helper(self, policy, verify)
            else:raw, stderr, receipt = _admit_run_helper(self, policy, verify,user_uid=1100)
        else:
            membership = ('0::' + self.context['hello']['carrier_unit']['control_group'] + '\n').encode('ascii')
            _require(self._capacity_kernel('/proc/self/cgroup', 4096) == membership,
                'CORE_PRIOR_SCOPE_HELPER_CGROUP')
            raw, stderr, receipt = _admit_run_helper(self, policy, verify, prior_observation=prior_observation)
            _require(self._capacity_kernel('/proc/self/cgroup', 4096) == membership,
                'CORE_PRIOR_SCOPE_HELPER_CGROUP')
        _require(not stderr and receipt['exit_status'] == 0, 'CORE_CAP_SYSTEMCTL_FAILED')
        if bus is not None:_require(bus == self._capacity_user_bus(),'CORE_RUNTIME_USER_BUS_DRIFT')
        return raw

    def _capacity_managers(self, programs, ordinary_uid):
        locators = self.context['manifest']['locators']; hello = self.context['hello']['carrier_unit']
        binding = _validate_runtime_binding(_approved_inputs_envelope(self.context)['reconciliation']['journal_transition']['runtime_parent_binding'])
        roles = {role + '_cgroup': row['unit'] for role,row in binding['parents'].items()}
        roles['user_manager'] = locators['user_manager_unit']; roles['carrier'] = locators['carrier_unit']
        _require(roles['user_manager'] == 'user@' + str(ordinary_uid) + '.service', 'CORE_CAP_MANAGER_USER')
        properties = ('Id', 'LoadState', 'ActiveState', 'SubState', 'ControlGroup', 'InvocationID',
            'MemoryMax', 'MemorySwapMax', 'TasksMax', 'CPUQuotaPerSecUSec', 'Delegate', 'User',
            'RuntimeMaxUSec', 'TimeoutStopUSec', 'Restart', 'KillMode', 'ExitType')
        units = {}
        targets = {role: ('user' if role == 'retained_ordinary_cgroup' else 'system',unit) for role,unit in roles.items()}
        _require(len(set(targets.values())) == len(targets),'CORE_RUNTIME_ROLE_ALIAS')
        for manager in ('system','user'):
            names = sorted(unit for scope,unit in targets.values() if scope == manager)
            args = ['show', *names, '--property=' + ','.join(properties)]
            raw = (self._capacity_systemctl(args,programs['systemctl'],user_uid=1100) if manager == 'user'
                else self._capacity_systemctl(args,programs['systemctl']))
            found = set()
            for block in raw.decode('ascii', 'strict').strip().split('\n\n'):
                rows = [line.split('=', 1) for line in block.splitlines()]
                _require(all(len(row) == 2 for row in rows) and len({row[0] for row in rows}) == len(rows),
                         'CORE_CAP_MANAGER_FORMAT')
                value = dict(rows)
                _require(set(value) <= set(properties) and {'Id', 'LoadState', 'ActiveState', 'SubState',
                    'ControlGroup', 'InvocationID', 'MemoryMax', 'MemorySwapMax', 'TasksMax',
                    'CPUQuotaPerSecUSec'} <= set(value) and value['Id'] not in found, 'CORE_CAP_MANAGER_FORMAT')
                found.add(value['Id']);units[manager,value['Id']] = value
            _require(found == set(names),'CORE_CAP_MANAGER_SET')
        parents = {}; observed = {}
        for role, unit in roles.items():
            value = units[targets[role]]; logical = value['ControlGroup']
            _require(value['LoadState'] == 'loaded' and value['ActiveState'] == 'active'
                     and value['SubState'] in ('active', 'running')
                     and re.fullmatch(r'[0-9a-f]{32}', value['InvocationID']) is not None,
                     'CORE_CAP_MANAGER_STATE')
            self._absolute(logical)
            if role.endswith('_cgroup'):
                row = binding['parents'][role.removesuffix('_cgroup')]
                _require(logical == row['control_group'] and value['MemoryMax'] == str(row['memory_bytes'])
                    and value['MemorySwapMax'] == '0' and value['TasksMax'] == str(row['tasks_max'])
                    and _cap_usec(value['CPUQuotaPerSecUSec']) == row['cpu_quota_per_sec_usec'],
                    'CORE_RUNTIME_CURRENT_PARENT')
            fd = self._capacity_directory('/sys/fs/cgroup' + logical)
            try:
                info = self._capacity_call(os.fstat, fd)
                controllers = self._capacity_kernel('cgroup.controllers', 256, dir_fd=fd).decode('ascii').split()
                for filename, property_name in (('memory.max', 'MemoryMax'), ('memory.swap.max', 'MemorySwapMax'),
                                                 ('pids.max', 'TasksMax')):
                    actual = self._capacity_kernel(filename, 64, dir_fd=fd).decode('ascii').strip()
                    _require(actual == ('max' if value[property_name] == 'infinity' else value[property_name]),
                             'CORE_CAP_CGROUP_LIMIT_DRIFT')
                cpu = self._capacity_kernel('cpu.max', 128, dir_fd=fd).decode('ascii').split()
                _require(len(cpu) == 2 and cpu[1].isdecimal() and int(cpu[1]) > 0,
                         'CORE_CAP_CGROUP_CPU')
                _require(cpu[0] == 'max' if value['CPUQuotaPerSecUSec'] == 'infinity' else
                         cpu[0].isdecimal() and int(cpu[0]) * 1000000 ==
                         _cap_usec(value['CPUQuotaPerSecUSec']) * int(cpu[1]), 'CORE_CAP_CGROUP_CPU')
                if role not in ('carrier', 'user_manager'):
                    _require({'cpu', 'memory', 'pids'} <= set(controllers), 'CORE_CAP_CONTROLLERS')
                    parents[role] = dict(path='/sys/fs/cgroup' + logical, dev=info.st_dev, ino=info.st_ino,
                        unit=unit, invocation_id=value['InvocationID'], controllers=sorted(set(controllers) & {'cpu', 'memory', 'pids'}))
                observed[role] = dict(path=logical, device=info.st_dev, inode=info.st_ino, unit=unit,
                                     invocation_id=value['InvocationID'], properties=value)
                _require(_admit_stat(info) == _admit_stat(self._capacity_call(os.fstat, fd)), 'CORE_CAP_CGROUP_DRIFT')
            finally:
                os.close(fd)
        manager = observed['user_manager']
        _require(manager['properties']['Delegate'] == 'yes' and manager['properties']['User'] == str(ordinary_uid),
                 'CORE_CAP_MANAGER_DELEGATION')
        expected_manager = binding['parents']['retained_ordinary']
        _require(manager['path'] == binding['manager']['control_group']
            and manager['properties']['MemoryMax'] == str(expected_manager['memory_bytes'])
            and manager['properties']['TasksMax'] == str(expected_manager['tasks_max'])
            and manager['properties']['MemorySwapMax'] == '0'
            and _cap_usec(manager['properties']['CPUQuotaPerSecUSec']) == 1000000, 'CORE_RUNTIME_MANAGER_LIMITS')
        carrier = observed['carrier']; value = carrier['properties']
        expected = {'Id': 'name', 'ControlGroup': 'control_group', 'InvocationID': 'invocation_id',
            'ActiveState': 'active_state', 'SubState': 'sub_state', 'Restart': 'restart',
            'KillMode': 'kill_mode', 'ExitType': 'exit_type'}
        _require(all(value[key] == hello[field] for key, field in expected.items()), 'CORE_CAP_CARRIER_DRIFT')
        for key, field in (('MemoryMax', 'memory_max'), ('MemorySwapMax', 'memory_swap_max'), ('TasksMax', 'tasks_max')):
            _require(value[key].isdecimal() and int(value[key]) == hello[field], 'CORE_CAP_CARRIER_LIMIT')
        for key, field in (('RuntimeMaxUSec', 'runtime_max_usec'), ('TimeoutStopUSec', 'timeout_stop_usec'),
                           ('CPUQuotaPerSecUSec', 'cpu_quota_per_sec_usec')):
            _require(_cap_usec(value[key]) == hello[field], 'CORE_CAP_CARRIER_LIMIT')
        membership = self._capacity_kernel('/proc/self/cgroup', 4096).decode('ascii').splitlines()
        _require(membership == ['0::' + carrier['path']], 'CORE_CAP_CARRIER_MEMBERSHIP')
        geometry = dict(schema='local-hand-q2-system-geometry/v1')
        for public, role in (('controller_parent', 'controller_cgroup'), ('ordinary_parent', 'ordinary_cgroup'),
                             ('retained_ordinary_parent', 'retained_ordinary_cgroup')):
            observation = observed[role]; current = observation['properties']
            _require(all(current[key].isdecimal() for key in ('MemoryMax', 'MemorySwapMax', 'TasksMax')),
                     'CORE_CAP_GEOMETRY_LIMIT')
            geometry[public] = dict(parent={key: observation[key] for key in ('path', 'device', 'inode')},
                memory_bytes=int(current['MemoryMax']), memory_swap_max=int(current['MemorySwapMax']),
                tasks_max=int(current['TasksMax']), cpu_quota_per_sec_usec=_cap_usec(current['CPUQuotaPerSecUSec']))
        for role, limits in {'controller_parent': (536870912, 64), 'ordinary_parent': (268435456, 32),
                             'retained_ordinary_parent': (268435456, 64)}.items():
            item = geometry[role]
            _require((item['memory_bytes'], item['tasks_max']) == limits and item['memory_swap_max'] == 0
                     and item['cpu_quota_per_sec_usec'] == 1000000, 'CORE_CAP_GEOMETRY_LIMIT')
        fixed = _admission_absent_units()
        for arguments in (['list-units', '--all', '--plain', '--no-legend', '--type=service,slice'],
                          ['list-unit-files', '--no-legend', '--type=service,slice']):
            output = self._capacity_systemctl(arguments, programs['systemctl'])
            names = {line.split()[0] for line in output.decode('ascii', 'strict').splitlines() if line.split()}
            _require(not fixed & names, 'CORE_CAP_UNIT_EXISTS')
        for unit in sorted(fixed):
            for prefix in ('/etc/systemd/system/', '/run/systemd/system/', '/usr/lib/systemd/system/'):
                for suffix in ('', '.d'):
                    fd, _, _ = self._capacity_path(prefix + unit + suffix, absent=True)
                    os.close(fd)
        self._admission_detail.update(carrier=carrier, system_geometry=geometry)
        return dict(parents=parents, manager=dict(user_manager_unit=manager['unit'],
            user_manager_invocation_id=manager['invocation_id'], user_manager_cgroup=manager['path']),
            absence=[dict(kind='unit', name=unit, parent_dev=None, parent_ino=None, project_id=None,
                          unit=unit, absent=True, collision=False) for unit in sorted(fixed)])

    def _capacity_admission(self, programs, ordinary_uid):
        self._capacity_owners = {0, ordinary_uid}
        approved = _approved_inputs_envelope(self.context)
        locators = self.context['manifest']['locators']
        mounts_raw = self._capacity_kernel('/proc/self/mountinfo')
        mounts = _cap_mounts(mounts_raw); parents = {}; filesystems = {}; details = {}
        for role in _CAP_ROLES:
            parents[role], filesystems[role], details[role] = self._capacity_filesystem(locators[role + '_parent'], mounts)
        quota_mount = details['quota']
        _require('prjquota' in filesystems['quota']['mount_options'], 'CORE_CAP_QUOTA_MOUNT')
        source = self._capacity_call(os.stat, quota_mount['source'], follow_symlinks=False)
        _require(stat.S_ISBLK(source.st_mode) and source.st_rdev == quota_mount['device'], 'CORE_CAP_QUOTA_DEVICE')
        self._admission_detail = dict(quota_mount=quota_mount, mounts=details)
        self._capacity_quota_enforcement()
        inventory = self._capacity_quota_inventory()
        quota = self._capacity_call(_CapQuota, quota_mount['source'])
        byproject = {row['project']: row for row in inventory}
        for row in approved['retained_preparation']['domains']:
            actual = byproject.get(row['project_id'])
            _require(actual is not None and actual['hard'] * 1024 == row['hard_bytes'] and
                     actual['ihard'] == row['inode_hard_limit'], 'CORE_CAP_RETAINED_QUOTA')
        def path_pool(path):
            fd, info, _ = self._capacity_path(path)
            try:
                uuid = self._capacity_call(_cap_uuid, fd)
                _require(info.st_dev == self._capacity_call(os.fstat, fd).st_dev, 'CORE_CAP_PATH_POOL')
                return info.st_dev, uuid
            finally:
                os.close(fd)
        capacity = _cap_charge(approved, filesystems, path_pool, inventory, locators)
        absence = []; paths = _admission_absent_paths(locators)
        # Derive reconciliation from the pinned original plan, not a guessed directory.
        row = next(row for row in approved['source_relation']['locator']['members'] if row['role'] == 'original_plan')
        raw, _ = self.stable_read('/' + row['path'], maximum=row['bytes'], guard=self._effect_guard)
        _require(_sha(raw) == row['sha256'], 'CORE_CAP_ORIGINAL_PLAN_CHANGED')
        original = _json_object(raw, 'CORE_CAP_ORIGINAL_PLAN')
        paths.add(original['directories']['reservation']['path'] + '.reconciliation')
        for path in sorted(paths):
            fd, parent, missing = self._capacity_path(path, absent=True)
            try:
                _require(missing, 'CORE_CAP_OBJECT_EXISTS')
                absence.append(dict(kind='path', name=path, parent_dev=parent.st_dev if str(PurePosixPath(path).parent) in locators.values() else None,
                    parent_ino=parent.st_ino if str(PurePosixPath(path).parent) in locators.values() else None, project_id=None, unit=None, absent=True, collision=False))
            finally:
                os.close(fd)
        for project in [*range(12051, 12058), *(p for case in CASES for p in case['project_ids'])]:
            _require(project not in byproject, 'CORE_CAP_PROJECT_EXISTS')
            self._capacity_call(quota.unused, project)
            absence.append(dict(kind='project', name=str(project), parent_dev=quota_mount['device'],
                parent_ino=parents['quota']['ino'], project_id=project, unit=None, absent=True, collision=False))
        self._admission_detail = dict(quota_mount=quota_mount, mounts=details, quota_inventory=inventory)
        self._admission_detail['retained_before'] = self._capacity_retained_snapshot()
        _require(mounts_raw == self._capacity_kernel('/proc/self/mountinfo'), 'CORE_CAP_MOUNT_DRIFT')
        return dict(parents=parents, filesystems=filesystems, capacity=capacity,
                    absence=sorted(absence, key=lambda row: (row['kind'], row['name'])))

    def admit(self, expected):
        _exact(expected, ("hello", "manifest", "guest_deadlines"), "CORE_EFFECT_ADMISSION_INPUT")
        _require(all(expected[key] == self.context[key] for key in expected)
                 and self._admission is None and not getattr(self, "_admit_attempted", False),
                 "CORE_EFFECT_ADMISSION_BINDING")
        self._admit_attempted = True
        self._effect_guard()
        approved = _approved_inputs_envelope(self.context)
        _validate_approved_components(approved)
        _prior_concurrency_bound(self.context)
        current = _admit_collect_policies(self, approved["policy_basis"], self.context["hello"]["remote_management"])
        self._admission_components = current
        programs = _admit_programs(self)
        guest = _admit_guest(self, programs)
        prior_observers = [_PriorScopeObserver(self, programs, index) for index in (0, 1, 2, 3)]
        try:
            for observer in prior_observers:
                observer.observe()
            capacity = self._capacity_admission(programs, guest["ordinary_uid"])
            managers = self._capacity_managers(programs, guest["ordinary_uid"])
            for observer in prior_observers:
                observer.observe()
            prior_quiescence = [observer.finish() for observer in prior_observers]
            # All three held scopes survive until every B and final name check.
            for observer in prior_observers:
                observer.recheck()
            _validate_prior_quiescences(prior_quiescence, self.context)
        finally:
            for observer in prior_observers:
                observer.close()
        guest.update(managers["manager"])
        capacity["parents"].update(managers["parents"])
        capacity["absence"] = sorted(capacity["absence"] + managers["absence"],
                                     key=lambda row: (row["kind"], row["name"]))
        admission = dict(guest=guest, programs=programs, policies=current["policies"],
                         binding=_admission_binding(self.context), prior_core_attempts=prior_quiescence, **capacity)
        self._effect_guard()
        self._admission = _validate_admission(admission, self.context)
        try:
            self._pool_accounting = _PoolAccounting(self)
            self._pool_accounting.observe('ADMISSION')
        except BaseException:
            self._admission = None
            raise
        return self._admission

    def install(self, expected):
        _effect.exact(expected, ("manifest", "members", "admission"),
            'INSTALLATION_INPUT')
        verified = self.verify_install_inputs()
        _effect(self._admission is not None and expected["admission"] == self._admission,
            "INSTALLATION_ADMISSION_REQUIRED")
        _effect(expected["manifest"] == self.context["manifest"]
            and expected["members"] == self.context["members"]
            and self._installation is None and self._candidate_root is None,
            "INSTALLATION_BINDING")
        _effect(os.geteuid() == os.getegid() == 0, "INSTALLATION_OWNER")
        self._effect_guard()
        self._verify_install_programs()
        manifest = self.context["manifest"]
        locators = manifest["locators"]
        staging = str(PurePosixPath(locators["install_parent"]) / STAGING_BASENAME)
        destination = str(PurePosixPath(locators["install_parent"]) / INSTALL_BASENAME)
        accounting = getattr(self, '_pool_accounting', None)
        call = partial(_guard_call, self._effect_guard)
        parent = self._held_directory(locators["install_parent"], guard=self._effect_guard)
        try:
            parent_pin = self._admission["parents"]["install"]
            info = call(os.fstat, parent)
            _effect((info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode),
                    info.st_uid, info.st_gid) ==
                (parent_pin["dev"], parent_pin["ino"], parent_pin["mode"],
                    parent_pin["uid"], parent_pin["gid"]),
                "INSTALLATION_PARENT_CHANGED")
            # Both names must be absent before the first mutation. O_EXCL
            # remains authoritative if another writer races this observation.
            for name in (STAGING_BASENAME, INSTALL_BASENAME):
                try:
                    call(os.stat, name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise _effect.error('INSTALLATION_EXISTS')
            self._prepare_carrier_storage()
            self._effect_guard()
            staging_fd = self._mkdir_at(parent, STAGING_BASENAME, 0o700, guard=self._effect_guard,
                accounting=accounting, path=staging)
        finally:
            os.close(parent)
        self._install_roots = [staging, destination]
        try:
            self._effect_guard()
            temporary_fd = self._mkdir_at(staging_fd, ".build-tmp", 0o700, guard=self._effect_guard,
                accounting=accounting, path=staging + '/.build-tmp')
            os.close(temporary_fd)
            self._effect_guard()
            self._install_temp = staging + "/.build-tmp"
            self._extract_install_members(staging_fd)
        finally:
            os.close(staging_fd)
        self._candidate_root = staging + "/candidate"
        self._observe_install_storage()
        build = self._candidate_helper("q2_prepare_build", verified)
        wheel_row = next(row for row in manifest["members"] if row["role"] == "wheel")
        programs = self._admission["programs"]
        guest = self._admission["guest"]
        self._effect_guard()
        self._install_build_active = True
        try:
            receipt = build.install_candidate(
                source=self._candidate_root, source_commit=CANDIDATE["commit"],
                source_tree=CANDIDATE["tree"], wheel=staging + "/" + wheel_row["path"],
                wheel_sha256=WHEEL["sha256"], destination=destination,
                python=programs["python"]["path"], compiler=programs["cc"]["path"],
                ordinary_uid=guest["ordinary_uid"], ordinary_gid=guest["ordinary_gid"],
                command=self._installation_command)
        finally:
            self._install_build_active = False
        self._effect_guard()
        self._install_build_receipt = receipt
        self._verify_install_programs()
        _effect(type(receipt) is dict and receipt.get("status") == "INSTALLED"
            and receipt.get("ordinary_verified") is True
            and receipt.get("fixture_provisioned") is False
            and receipt["source"]["commit"] == CANDIDATE["commit"]
            and receipt["source"]["tree"] == CANDIDATE["tree"]
            and receipt["source"]["manifest_sha256"] == PROJECTION["sha256"]
            and receipt["installed"]["payload_digest"] == verified["payload_digest"],
            "INSTALLATION_RECEIPT")
        projection_raw, _ = self.stable_read(
            destination + "/source/.local-hand-source-projection.json", maximum=262144,
            guard=self._effect_guard)
        _effect(_sha(projection_raw) == PROJECTION["sha256"],
            "INSTALLATION_PROJECTION")
        # Only the dispatcher D blob is installed alongside the frozen
        # candidate. Private approved inputs stay exclusively in bootstrap RAM.
        installed_fd = self._held_directory(destination, guard=self._effect_guard)
        try:
            self._effect_guard()
            self.create_only_at(installed_fd, "core-dispatcher.py",
                bytes(self.context["members"]["field/dispatcher.py"]), mode=420,
                guard=self._effect_guard, accounting=accounting, path=destination + '/core-dispatcher.py')
            self._effect_guard()
            info = call(os.fstat, installed_fd)
        finally:
            os.close(installed_fd)
        observed = self._observe_install_storage()
        self._effect_guard()
        self._installation_receipt = receipt
        result = {"destination": destination, "staging": staging,
            "receipt_path": str(PurePosixPath(locators["state_parent"]) / SESSION
                / "carrier" / "installation.json"),
            "dev": info.st_dev, "ino": info.st_ino,
            "mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid,
            "members_sha256": verified["members_sha256"],
            "native_sha256": receipt["native_build"]["program"]["sha256"],
            "projection_sha256": PROJECTION["sha256"], "wheel_sha256": WHEEL["sha256"],
            "allocated_bytes": observed["bytes"], "allocated_inodes": observed["inodes"],
            "status": "INSTALLED"}
        self._installation = _validate_installation(result, manifest)
        return self._installation

    def _effect_guard(self):
        # A reserves the final 45 seconds for bounded stop/final output only.
        # Installation, extraction and new child work cannot borrow it. Keep
        # the original outer deadlines unchanged for the remote finalizer.
        outer = self.context["guest_deadlines"]
        return _clock(self, {
            "boot_id": outer["boot_id"],
            "boottime_deadline_ns": outer["boottime_deadline_ns"] - REMOTE_FINAL_RESERVE_NS,
            "monotonic_deadline_ns": outer["monotonic_deadline_ns"] - REMOTE_FINAL_RESERVE_NS,
        })

    def _prepare_carrier_storage(self):
        _effect(not self._persistence_ready and self._admission is not None,
            "CARRIER_STORAGE_STATE")
        parent = self._held_directory(self.context["manifest"]["locators"]["state_parent"],
            guard=self._effect_guard)
        opened = [parent]
        path = self.context["manifest"]["locators"]["state_parent"]
        try:
            expected = self._admission["parents"]["state"]
            info = _guard_call(self._effect_guard, os.fstat, parent)
            _effect((info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid)
                == (expected["dev"], expected["ino"], expected["mode"],
                    expected["uid"], expected["gid"]), "CARRIER_PARENT_CHANGED")
            for name, mode in ((SESSION, 0o755), ("carrier", 0o700), ("intents", 0o700)):
                self._effect_guard()
                path += '/' + name
                parent = self._mkdir_at(parent, name, mode, guard=self._effect_guard,
                    accounting=getattr(self, '_pool_accounting', None), path=path)
                opened.append(parent)
                self._effect_guard()
            self._persistence_ready = True
        finally:
            for fd in reversed(opened):
                os.close(fd)

    def _verify_install_programs(self):
        _effect(self._admission is not None, "INSTALLATION_ADMISSION_REQUIRED")
        for name in _fields('python git cc setpriv systemctl systemd_run'):
            expected = self._admission["programs"][name]
            self._effect_guard()
            raw, identity = self.stable_read(expected["path"], maximum=MEMBER_LIMIT,
                expected_mode=expected["mode"], guard=self._effect_guard)
            _effect(dict(path=expected["path"], **identity) == expected
                and identity["uid"] == 0 and not identity["mode"] & 0o6022
                and identity["mode"] & 0o111 and raw.startswith(b"\x7fELF"),
                "INSTALL_PROGRAM_CHANGED")
        _effect(self._admission["programs"]["git"]["path"] == "/usr/bin/git"
            and self._admission["programs"]["setpriv"]["path"] == "/usr/bin/setpriv",
            "INSTALL_PROGRAM_ALIAS")
        if hasattr(self, "_install_build_receipt"):
            receipt = self._install_build_receipt
            for item in (receipt["installed"]["programs"]["python"], receipt["native_build"]["abi_program"]):
                expected = self._install_program_pins[item["path"]]
                _, identity = self.stable_read(item["path"], maximum=MEMBER_LIMIT, guard=self._effect_guard)
                _effect(dict(path=item["path"], **identity) == expected
                    and item == {key: expected[key] for key in ("path", "sha256")},
                    "INSTALL_PROGRAM_CHANGED")

    @staticmethod
    def _mkdir_at(parent, name, mode, *, guard=None, accounting=None, path=None):
        _effect(type(name) is str and re.fullmatch(r"[A-Za-z0-9._-]+", name)
            and name not in (".", "..") and mode in (0o700, 0o755),
            "MKDIR_INPUT")
        call = partial(_guard_call, guard)
        _effect(accounting is None or type(path) is str, 'MKDIR_ACCOUNTING_PATH')
        mutate = partial(_accounting_io, accounting, guard, path)
        mutate(os.mkdir, name, mode, dir_fd=parent, create=True)
        fd = call(os.open, name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent, release=os.close)
        try:
            call(os.fchmod, fd, mode)
            info = call(os.fstat, fd)
            _effect(info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == mode,
                "MKDIR_OWNER")
            mutate(os.fsync, fd)
            mutate(os.fsync, parent)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _extract_install_members(self, staging_fd):
        directories = {"": staging_fd}
        staging = self.context['manifest']['locators']['install_parent'] + '/' + STAGING_BASENAME
        accounting = getattr(self, '_pool_accounting', None)
        try:
            for row in self.context["manifest"]["members"]:
                self._effect_guard()
                # This private source relation must never reach installation,
                # ordinary projection, sys.path or public output.
                if row["role"] == "approved-inputs":
                    continue
                relative = PurePosixPath(_effect.path(row["path"], 'INSTALL_MEMBER_PATH'))
                for index in range(1, len(relative.parts)):
                    name = PurePosixPath(*relative.parts[:index]).as_posix()
                    if name not in directories:
                        previous = PurePosixPath(*relative.parts[:index - 1]).as_posix()
                        self._effect_guard()
                        directories[name] = self._mkdir_at(
                            directories["" if previous == "." else previous],
                            relative.parts[index - 1], 0o700, guard=self._effect_guard,
                            accounting=accounting, path=staging + '/' + name)
                        self._effect_guard()
                parent_name = relative.parent.as_posix()
                fd = directories["" if parent_name == "." else parent_name]
                raw = bytes(self.context["members"][row["path"]])
                _effect(len(raw) == row["bytes"] and _sha(raw) == row["sha256"],
                    "INSTALL_MEMBER_CHANGED")
                self._effect_guard()
                self.create_only_at(fd, relative.name, raw, mode=row["mode"], guard=self._effect_guard,
                    accounting=accounting, path=staging + '/' + relative.as_posix())
                self._effect_guard()
                reread, identity = self.stable_read_at(fd, relative.name,
                    maximum=row["bytes"], expected_mode=row["mode"], guard=self._effect_guard)
                _effect(identity["uid"] == identity["gid"] == 0 and reread == raw,
                    "INSTALL_MEMBER_CHANGED")
                self._observe_install_storage()
                self._effect_guard()
        finally:
            for path, fd in directories.items():
                if path:
                    os.close(fd)

    def _candidate_helper(self, name, verified):
        _effect(name in (*PREPARATION_HELPERS, "q2_prepare_build"), "HELPER_NAME")
        return self._candidate_modules((name,), verified)[name]

    def _candidate_modules(self, names, verified=None):
        """Held-byte imports, including lazy imports, never expose the checkout."""
        import builtins
        import sys
        import types
        verified = self.verify_install_inputs() if verified is None else verified
        pin = _sha(canonical(verified))
        prior = getattr(self, "_candidate_loader", None)
        if prior is not None:
            _effect(prior[0] == pin, "HELPER_SOURCE_CHANGED")
            return {name: prior[1](name) for name in names}
        sources = copy.deepcopy(verified)
        cache = {}
        roots = frozenset((*WHEEL_PACKAGES, "admin"))
        helpers = frozenset((*PREPARATION_HELPERS, "q2_prepare_build"))
        namespaces = {"admin", "admin.local_hand_quota_observer"}

        def load(name):
            _effect(type(name) is str and re.fullmatch(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*", name)
                and (name in helpers or name.split(".")[0] in roots
                    or "tests/e3_host/" + name + ".py" in PROJECTION_HARNESS),
                "HELPER_NAME")
            if name in cache:
                return cache[name]
            package = name in namespaces
            relative = "tools/" + name.replace(".", "/")
            if name in helpers:
                _effect(self._candidate_root is not None, "HELPER_INSTALLATION_REQUIRED")
                relative = "tests/e3_host/" + name + ".py"
                path = self._candidate_root + "/" + relative
                digest = sources["source_files"].get(relative)
            elif name in namespaces:
                path, digest = "<core-namespace>", None
            else:
                receipt = self._installation_receipt
                _effect(receipt is not None and self._installation is not None,
                    "HELPER_INSTALLATION_REQUIRED")
                package = relative + "/__init__.py" in sources["projection"]["files"]
                relative = (relative + "/__init__.py" if package else relative + ".py") \
                    if name.split(".")[0] in roots else "tests/e3_host/" + name + ".py"
                entry = sources["projection"]["files"].get(relative)
                _effect(entry is not None and _projection_path(relative), "HELPER_PROJECTION")
                digest = entry["sha256"]
                if name.split(".")[0] in WHEEL_PACKAGES:
                    _effect(sources["wheel_files"].get(relative[6:]) == digest,
                        "HELPER_WHEEL")
                    path = receipt["installed"]["package_root"] + "/" + relative[6:]
                else:
                    path = receipt["source"]["root"] + "/" + relative
            raw = b""
            if digest is not None:
                self._effect_guard()
                raw, identity = self.stable_read(path, maximum=MEMBER_LIMIT, expected_mode=420,
                    guard=self._effect_guard)
                self._effect_guard()
                _effect(identity["uid"] == identity["gid"] == 0 and _sha(raw) == digest,
                    "HELPER_CHANGED")
            else:
                _effect(name in namespaces, "HELPER_SOURCE_MISSING")
            parent, _, child = name.rpartition(".")
            if parent:
                load(parent)
                if name in cache:
                    return cache[name]
            module = types.ModuleType(name)
            module.__file__, module.__package__ = path, name if package else parent
            if package:
                module.__path__ = []
            module.__dict__["__builtins__"] = dict(vars(builtins), __import__=import_bound)
            cache[name] = module
            previous = sys.modules.get(name)
            existed = name in sys.modules
            try:
                sys.modules[name] = module
                exec(compile(raw, path, "exec"), module.__dict__)
                if name == "q2_prepare_driver":
                    module.helper = lambda helper: load(helper) if helper in PREPARATION_HELPERS else \
                        _effect(False, "HELPER_NAME")
                if name == "q2_prepare_build":
                    bindings = _InstallIO(self._effect_guard, getattr(self, '_pool_accounting', None))
                    module.os, module.Path = bindings.os, bindings.Path
            except BaseException:
                cache.pop(name, None)
                raise
            finally:
                if existed:
                    sys.modules[name] = previous
                else:
                    sys.modules.pop(name, None)
            if parent:
                setattr(cache[parent], child, module)
            return module

        def import_bound(name, globals=None, locals=None, fromlist=(), level=0):
            if level:
                name = importlib.util.resolve_name("." * level + name, globals["__package__"])
            root = name.split(".")[0]
            if root not in roots and name not in helpers and not name.startswith(("q2_", "q4_")):
                _effect(root in sys.stdlib_module_names, "HELPER_IMPORT")
                return builtins.__import__(name, globals, locals, fromlist, 0)
            module = load(name)
            for item in fromlist or ():
                if item != "*" and not hasattr(module, item):
                    load(name + "." + item)
            return module if fromlist else load(root)

        result = {name: load(name) for name in names}
        self._candidate_loader = (pin, load)
        return result

    def _observe_install_storage(self):
        """Charge actual simultaneous owned files; this is not a peak proof."""
        call = partial(_guard_call, self._effect_guard)
        total_bytes = total_inodes = 0
        seen = set()
        for root in self._install_roots:
            try:
                root_fd = self._held_directory(root, guard=self._effect_guard)
            except FileNotFoundError:
                continue
            pending = [(root_fd, root)]
            try:
                while pending:
                    fd, directory = pending.pop()
                    try:
                        info = call(os.fstat, fd)
                        _effect(info.st_uid == 0 and not info.st_mode & 0o022,
                            "INSTALL_STORAGE_OWNER")
                        key = (info.st_dev, info.st_ino)
                        _effect(key not in seen, "INSTALL_STORAGE_ALIAS")
                        seen.add(key)
                        total_bytes += info.st_blocks * 512
                        total_inodes += 1
                        with call(os.scandir, fd, release=lambda value: value.close()) as entries:
                            for entry in iter(lambda: call(next, entries, None), None):
                                item = call(entry.stat, follow_symlinks=False)
                                if stat.S_ISLNK(item.st_mode):
                                    # The frozen installer removes only this
                                    # venv-generated convenience alias directly
                                    # after the venv child returns. Count its
                                    # inode without traversing it meanwhile.
                                    _effect(self._venv_alias_pending
                                        and directory == self._install_roots[1] + "/runtime"
                                        and entry.name == "lib64"
                                        and call(os.readlink, entry.name, dir_fd=fd) == "lib",
                                        "INSTALL_STORAGE_SYMLINK")
                                    total_bytes += item.st_blocks * 512
                                    total_inodes += 1
                                    continue
                                if stat.S_ISDIR(item.st_mode):
                                    pending.append((call(os.open, entry.name, os.O_RDONLY | os.O_DIRECTORY
                                        | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd, release=os.close),
                                        directory + "/" + entry.name))
                                else:
                                    _effect(stat.S_ISREG(item.st_mode) and item.st_nlink == 1
                                        and item.st_uid == 0 and not item.st_mode & 0o022,
                                        "INSTALL_STORAGE_FILE")
                                    key = (item.st_dev, item.st_ino)
                                    _effect(key not in seen, "INSTALL_STORAGE_ALIAS")
                                    seen.add(key)
                                    total_bytes += item.st_blocks * 512
                                    total_inodes += 1
                                _effect(total_bytes <= LIMITS["shared_bytes"]
                                    and total_inodes + len(pending) <= LIMITS["shared_inodes"],
                                    "INSTALL_STORAGE_LIMIT")
                    finally:
                        os.close(fd)
            finally:
                for fd, _ in pending:
                    os.close(fd)
        _effect(total_bytes <= LIMITS["shared_bytes"]
            and total_inodes <= LIMITS["shared_inodes"], "INSTALL_STORAGE_LIMIT")
        self._shared_observed_bytes = max(self._shared_observed_bytes, total_bytes)
        self._shared_observed_inodes = max(self._shared_observed_inodes, total_inodes)
        return {"bytes": total_bytes, "inodes": total_inodes}

    def _installation_binding(self, argv):
        """Execute held ELF bytes while retaining Python's approved venv path."""
        _effect(self._admission is not None, "INSTALLATION_ADMISSION_REQUIRED")
        call = partial(_guard_call, self._effect_guard)
        programs = self._admission["programs"]
        pins = {item["path"]: item for item in programs.values()}
        paths, actual, descriptors, environment = [argv[0]], list(argv), [], {}
        destination = str(PurePosixPath(self.context["manifest"]["locators"]["install_parent"])
            / INSTALL_BASENAME)
        runtime = destination + "/runtime/bin/python3"
        dynamic = getattr(self, "_install_program_pins", {})
        self._install_program_pins = dynamic
        if argv[0] == programs["setpriv"]["path"]:
            guest = self._admission["guest"]
            flags = {"--reuid=" + str(guest["ordinary_uid"]),
                "--regid=" + str(guest["ordinary_gid"]), "--clear-groups",
                "--no-new-privs", "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all"}
            _effect(len(argv) > 8 and set(argv[1:8]) == flags and argv[8] == runtime,
                "INSTALL_PROGRAM_CHAIN")
            paths.append(runtime)
            environment["__PYVENV_LAUNCHER__"] = runtime
        try:
            for path in paths:
                self._effect_guard()
                raw, identity = self.stable_read(path, maximum=MEMBER_LIMIT, guard=self._effect_guard)
                expected = pins.get(path)
                observed = dict(path=path, **identity)
                if expected is None and path in (runtime, destination + "/native/abi"):
                    _effect(getattr(self, "_install_build_active", False)
                        or (path == runtime and self._installation_receipt is not None),
                        "INSTALL_PROGRAM_STAGE")
                    _effect(path != runtime or identity["sha256"] == programs["python"]["sha256"],
                        "INSTALL_PROGRAM_CHANGED")
                    if self._installation_receipt is not None:
                        receipt = self._installation_receipt
                        _effect({"path": path, "sha256": identity["sha256"]}
                            == receipt["installed"]["programs"]["python"]
                            and {"device": identity["dev"], "inode": identity["ino"]}
                            == receipt["python_identity"], "INSTALL_PROGRAM_CHANGED")
                    expected = dynamic.setdefault(path, observed)
                _effect(observed == expected,
                    "INSTALL_PROGRAM_CHANGED")
                _effect(identity["uid"] == identity["gid"] == 0 and identity["nlink"] == 1
                    and not identity["mode"] & 0o6022 and identity["mode"] & 0o111
                    and raw.startswith(b"\x7fELF"), "INSTALL_PROGRAM_CHANGED")
                parsed = PurePosixPath(path)
                parent = self._held_directory(str(parsed.parent), guard=self._effect_guard)
                try:
                    fd = call(os.open, parsed.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NOATIME,
                        dir_fd=parent, release=os.close)
                    descriptors.append(fd)
                    before = call(os.fstat, fd)
                    try:
                        call(os.getxattr, fd, "security.capability")
                    except OSError as error:
                        import errno
                        _effect(error.errno in (errno.ENODATA, errno.ENOTSUP),
                            "INSTALL_PROGRAM_CAPABILITY")
                    else:
                        raise _effect.error('INSTALL_PROGRAM_CAPABILITY')
                    _effect((before.st_dev, before.st_ino, stat.S_IMODE(before.st_mode),
                            before.st_uid, before.st_gid, before.st_nlink, before.st_size)
                        == tuple(identity[key] for key in _fields('dev ino mode uid gid nlink bytes'))
                        and call(os.pread, fd, MEMBER_LIMIT + 1, 0) == raw,
                        "INSTALL_PROGRAM_CHANGED")
                    _effect(before == call(os.fstat, fd) == call(os.stat, parsed.name, dir_fd=parent, follow_symlinks=False),
                        "INSTALL_PROGRAM_CHANGED")
                finally:
                    os.close(parent)
            if len(descriptors) == 2:
                actual[8] = "/proc/self/fd/" + str(descriptors[1])
            return actual, {"executable": "/proc/self/fd/" + str(descriptors[0]),
                "pass_fds": tuple(descriptors)}, environment, descriptors
        except BaseException:
            for fd in descriptors:
                os.close(fd)
            raise

    def _installation_command(self, argv):
        """One real child, wait4 accounting and paired EOF; never retry.

        Normal work cannot borrow the remote-final reserve. After a failure,
        only kill/reap/drain is permitted inside the unchanged outer window.
        Child rusage is retained as a measured component, not a substitute for
        the still-missing all-unit CPU/memory/pid/storage accounting.
        """
        _effect(type(argv) in (list, tuple) and 1 <= len(argv) <= 128
            and all(type(arg) is str and "\0" not in arg and len(arg) <= 65536 for arg in argv)
            and argv[0].startswith("/"), "INSTALL_COMMAND")
        self._effect_guard()
        self._observe_install_storage()
        self._effect_guard()
        output = {"stdout": bytearray(), "stderr": bytearray()}
        eof = set()
        proc = selector = None
        failure = cleanup_failure = waited = None
        attempted = False
        accounting = getattr(self, '_pool_accounting', None)
        child_after_observed = False
        killed = False
        bound_fds = []

        def call(function, *args, stopping=False, returned=None, **kwargs):
            guard = (lambda: _clock(self, self.context["guest_deadlines"])) if stopping else self._effect_guard
            guard()
            value = function(*args, **kwargs)
            # Preserve completed effects even when a syscall returns late.
            if returned is not None:
                returned(value)
            guard()
            return value

        def set_process(value):
            nonlocal proc
            proc = value

        def set_selector(value):
            nonlocal selector
            selector = value

        def reap(stopping=False):
            nonlocal waited
            if waited is not None:
                return
            def retain(value):
                nonlocal waited
                pid, status, usage = value
                if pid:
                    _effect(pid == proc.pid, "INSTALL_COMMAND_WAIT_IDENTITY")
                    proc.returncode = os.waitstatus_to_exitcode(status)
                    # Linux ru_maxrss is KiB. Round CPU upward, never to an
                    # optimistic zero for a positive sub-nanosecond value.
                    waited = {"pid": pid, "wait_status": status,
                        "user_cpu_ns": math.ceil(usage.ru_utime * NS),
                        "system_cpu_ns": math.ceil(usage.ru_stime * NS),
                        "max_rss_bytes": usage.ru_maxrss * 1024}
            call(os.wait4, proc.pid, os.WNOHANG, stopping=stopping, returned=retain)

        def read_pipe(name, stopping=False):
            stream = getattr(proc, name)
            room = 32768 - sum(map(len, output.values()))
            def retain(block):
                if not block:
                    eof.add(name)
                else:
                    # A remaining+1 sentinel is observed but never retained.
                    output[name].extend(block[:room])
            try:
                block = call(os.read, stream.fileno(), 4096 if stopping else min(4096, room + 1),
                    stopping=stopping, returned=retain)
            except BlockingIOError:
                return
            if not stopping:
                _effect(len(block) <= room, "INSTALL_COMMAND_OUTPUT_LIMIT")

        try:
            actual, binding, environment, bound_fds = self._installation_binding(argv)
            _accounting_observe(accounting, self._effect_guard, 'CHILD_BEFORE')
            attempted = True
            call(subprocess.Popen, actual, **binding, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, cwd=self._candidate_root, close_fds=True,
                start_new_session=True, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C",
                    "LANG": "C", "PYTHONDONTWRITEBYTECODE": "1",
                    "TMPDIR": self._install_temp or self._candidate_root,
                    "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": "/dev/null", **environment}, returned=set_process)
            call(selectors.DefaultSelector, returned=set_selector)
            for name in output:
                stream = getattr(proc, name)
                call(os.set_blocking, stream.fileno(), False)
                call(selector.register, stream, selectors.EVENT_READ, name)
            while len(eof) != 2 or waited is None:
                for key, _ in call(selector.select, 0.02):
                    read_pipe(key.data)
                    if key.data in eof:
                        call(selector.unregister, key.fileobj)
                reap()
            self._effect_guard()
            self._venv_alias_pending = list(argv[1:7]) == ["-I", "-B", "-m", "venv", "--copies", "--without-pip"]
            try:
                self._observe_install_storage()
                _accounting_observe(accounting, self._effect_guard, 'CHILD_AFTER')
                child_after_observed = True
            finally:
                self._venv_alias_pending = False
            _effect(proc.returncode == 0, "INSTALL_COMMAND_FAILED")
            self._effect_guard()
            return bytes(output["stdout"])
        except BaseException as error:
            failure = str(error)[:128] if isinstance(error, DispatchError) else type(error).__name__
            if proc is not None and accounting is not None and not child_after_observed:
                for identifier in accounting.by_id:
                    accounting.mark_incomplete(identifier, 'last_observation', 'CHILD_AFTER_MISSING')
            if proc is not None:
                try:
                    # The leader may already be reaped while a descendant
                    # still owns a pipe. Signal its original process group.
                    def kill():
                        nonlocal killed
                        killed = True
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    if waited is None or len(eof) != 2:
                        call(kill, stopping=True)
                    for name in output:
                        call(os.set_blocking, getattr(proc, name).fileno(), False, stopping=True)
                    # Do not depend on selector construction succeeding. A
                    # bounded empty poll allows kill/reap even under EMFILE.
                    while waited is None or len(eof) != 2:
                        reap(stopping=True)
                        for name in output:
                            if name not in eof:
                                read_pipe(name, stopping=True)
                        if waited is None or len(eof) != 2:
                            call(time.sleep, 0.005, stopping=True)
                except BaseException as cleanup_error:
                    cleanup_failure = (str(cleanup_error)[:128]
                        if isinstance(cleanup_error, DispatchError) else type(cleanup_error).__name__)
            raise
        finally:
            for fd in bound_fds:
                os.close(fd)
            if attempted:
                self._install_commands.append({"argv": list(argv),
                    "returncode": proc.returncode if proc is not None else None,
                    "eof": sorted(eof), "failure": failure, "cleanup_failure": cleanup_failure,
                    "kill_sent": killed, "wait4": waited,
                    "stdout": bytes(output["stdout"]), "stderr": bytes(output["stderr"])})
            # Local descriptor release is not evidence of EOF or child exit.
            try:
                if selector is not None:
                    selector.close()
            finally:
                if proc is not None:
                    for name in output:
                        getattr(proc, name).close()

    def persist(self, case_id, path, raw, mode):
        _effect(self._persistence_ready, "PERSISTENCE_NOT_READY")
        target = self._persistence_path(case_id, path)
        role = ("session" if path == "carrier/session.json" else
            "admission" if path == "carrier/admission.json" else
            "installation" if path == "carrier/installation.json" else
            "intent" if path.endswith("/intent.json") else
            "phase-receipt" if "/phase-" in path and path.endswith("-receipt.json") else
            "recovery-proof" if path.endswith("/h11-recovery-proof.json") else
            "verdict" if path.endswith("/case-verdict.json") else None)
        _effect(role is not None, "PERSIST_ROLE")
        if role == 'session':
            guard = lambda: _clock(self, self.context['guest_deadlines'])
        elif role in ('phase-receipt', 'recovery-proof', 'verdict'):
            active = getattr(self, '_active_case_deadlines', {})
            _effect(type(active.get('owner_deadline_ns')) is int, 'PERSIST_CASE_CLOCK')
            guard = partial(_prep_guard, self, active['owner_deadline_ns'])
        elif role == 'intent':
            active = getattr(self, '_active_case_deadlines', {})
            _effect(type(active.get('preparation_deadline_ns')) is int, 'PERSIST_CASE_CLOCK')
            guard = partial(_prep_guard, self, active['preparation_deadline_ns'])
        else:
            guard = self._effect_guard
        self.create_only(target, raw, mode=mode, guard=guard,
            accounting=getattr(self, '_pool_accounting', None))
        return {"path": path, "role": role, "mode": mode, "raw": raw}

    def accounting_boundary(self, boundary):
        _effect(boundary == 'CASE_BOUNDARY', 'ACCOUNTING_BOUNDARY')
        active = getattr(self, '_active_case_deadlines', None)
        _effect(type(active) is dict and type(active.get('owner_deadline_ns')) is int,
            'ACCOUNTING_CASE_CLOCK')
        _accounting_observe(getattr(self, '_pool_accounting', None),
            partial(_prep_guard, self, active['owner_deadline_ns']), boundary)

    def preparation_helpers(self):
        _effect(self._candidate_root is not None, "HELPER_INSTALLATION_REQUIRED")
        verified = self.verify_install_inputs()
        return {name: self._candidate_helper(name, verified) for name in PREPARATION_HELPERS}

    def _capacity_protection(self, info):
        _cap(info.st_uid in getattr(self, '_capacity_owners', {0})
            and not info.st_mode & 0o022, 'PATH_PROTECTION')

    def _capacity_retained_snapshot(self, *, guard=None):
        """Read only approved roots, with no-atime enumeration and named rechecks."""
        guard = self._effect_guard if guard is None else guard
        call = partial(_guard_call, guard)
        approved = _approved_inputs_envelope(self.context)
        count = total = 0
        def directory(path):
            return self._held_directory(path, guard=guard, validate=self._capacity_protection)
        def snapshot(fd, path, device, rows, depth=0):
            nonlocal count, total
            before = call(os.fstat, fd)
            self._capacity_protection(before)
            count += 1
            _cap(depth <= 64 and len(path) <= 4096 and count <= 32768
                and before.st_dev == device, 'RETAINED_LIMIT')
            listing = call(os.open, '.', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC |
                os.O_NOFOLLOW | os.O_NOATIME, dir_fd=fd, release=os.close)
            try:
                entries = call(os.scandir, listing, release=lambda it: it.close())
                with entries:
                    names = []
                    while (entry := call(next, entries, None)) is not None:
                        names.append(entry.name)
                        _cap(count + len(names) <= 32768, 'RETAINED_LIMIT')
                    _cap(len(names) == len(set(names)), 'RETAINED_DRIFT')
            finally:
                os.close(listing)
            rows.append(dict(path=path, identity=list(_capacity_stat(before))))
            for name in sorted(names):
                _cap(re.fullmatch(r'[A-Za-z0-9._-]+', name) and name not in ('.', '..'), 'RETAINED_NAME')
                child = call(os.stat, name, dir_fd=fd, follow_symlinks=False)
                self._capacity_protection(child)
                _cap(child.st_dev == device and not stat.S_ISLNK(child.st_mode), 'RETAINED_TYPE')
                if stat.S_ISDIR(child.st_mode):
                    opened = call(os.open, name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC |
                        os.O_NOFOLLOW, dir_fd=fd, release=os.close)
                    try:
                        _cap_same(child, call(os.fstat, opened))
                        snapshot(opened, path + '/' + name, device, rows, depth + 1)
                    finally:
                        os.close(opened)
                else:
                    count += 1; total += child.st_size
                    _cap(stat.S_ISREG(child.st_mode) and child.st_nlink == 1 and count <= 32768
                        and 0 <= child.st_size <= MEMBER_LIMIT and total <= 536870912, 'RETAINED_LIMIT')
                    raw, pin = self.stable_read_at(fd, name, maximum=child.st_size, guard=guard)
                    _cap((pin['dev'], pin['ino']) == (child.st_dev, child.st_ino), 'RETAINED_DRIFT')
                    rows.append(dict(path=path + '/' + name, identity=list(_capacity_stat(child)), sha256=_sha(raw)))
                named = call(os.stat, name, dir_fd=fd, follow_symlinks=False)
                _cap_same(child, named)
            _cap_same(before, call(os.fstat, fd))
        result = []
        for root in approved['retained_preparation']['paths']:
            fd = directory(root['path'])
            try:
                before = call(os.fstat, fd)
                _cap((before.st_dev, before.st_ino) == (root['device'], root['inode']), 'RETAINED_IDENTITY')
                rows = []
                snapshot(fd, root['path'], root['device'], rows)
                named = directory(root['path'])
                try:
                    _cap_same(before, call(os.fstat, named))
                finally:
                    os.close(named)
                result.append(dict(root=copy.deepcopy(root), files=sorted(rows, key=lambda row: row['path'])))
            finally:
                os.close(fd)
        return result

    def _capacity_quota(self, inventory, guard):
        guard = self._effect_guard if guard is None else guard
        call = partial(_guard_call, guard)
        detail = getattr(self, '_admission_detail', None)
        _cap(type(detail) is dict and 'quota_mount' in detail, 'CONTEXT_REQUIRED')
        mount = detail['quota_mount']
        source = self._absolute(mount['source'])
        parent = self._held_directory(str(source.parent), guard=guard, validate=self._capacity_protection)
        try:
            before = call(os.stat, source.name, dir_fd=parent, follow_symlinks=False)
            _cap(stat.S_ISBLK(before.st_mode) and before.st_rdev == mount['device'], 'QUOTA_DEVICE')
            quota = call(_CapQuota, str(source))
            result = quota.inventory(guard) if inventory else call(quota.enforcement)
            after = call(os.stat, source.name, dir_fd=parent, follow_symlinks=False)
            _cap(_capacity_stat(before) == _capacity_stat(after)
                and before.st_rdev == after.st_rdev, 'QUOTA_DEVICE_DRIFT')
            return result
        finally:
            os.close(parent)

    def _capacity_quota_inventory(self, *, guard=None):
        return self._capacity_quota(True, guard)

    def _capacity_quota_enforcement(self, *, guard=None):
        return self._capacity_quota(False, guard)

    def prepare_case(self, case, intent, preparation_deadline_ns):
        _prep_require(case in CASES and intent == build_intent(case), 'INPUT')
        _effect.integer(preparation_deadline_ns, 1, code='PREPARATION_DEADLINE')
        _prep_require(self._installation_receipt is not None and self._persistence_ready
            and self._admission is not None and os.geteuid() == os.getegid() == 0,
            'INSTALLATION_REQUIRED')
        _prep_require(type(getattr(self, '_admission_detail', None)) is dict
            and 'retained_before' in self._admission_detail
            and all(callable(getattr(self, "_capacity_" + name, None)) for name in
                ("retained_snapshot", "quota_inventory", "quota_enforcement")),
            'CURRENT_FACTS_REQUIRED')
        deadline = preparation_deadline_ns
        guard = partial(_prep_guard, self, deadline)
        with _PrepIO(self, deadline) as io:
            intent_path = self._persistence_path(case["case_id"], "cases/" + case["case_id"] + "/intent.json")
            actual, pin = io.call(self.stable_read, intent_path, maximum=65536, expected_mode=384)
            _prep_require(actual == canonical(intent, newline=True) and pin["uid"] == pin["gid"] == 0,
                'INTENT_REQUIRED')
            helpers = io.call(self.preparation_helpers)
            driver = helpers["q2_prepare_driver"]
            # Fixed before the first write; never refresh expiry after preparation.
            plan = _prep_make_plan(self, case, (time.time_ns() + OWNER_NS) // NS)
            driver.validate_plan(plan)
            parents, directories, children = self._admission["parents"], {}, {}
            before = io.call(self._capacity_retained_snapshot, guard=guard)
            inventory = io.call(self._capacity_quota_inventory, guard=guard)
            _prep_require(before == self._admission_detail["retained_before"]
                and not set(case["project_ids"]) & {r["project"] for r in inventory},
                'RETAINED_CHANGED')
            for role in _fields('state quota journal evidence'):
                pin = parents[role]
                info = io.call(os.fstat, io.directory(pin["path"]))
                _prep_require((info.st_dev, info.st_ino, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))
                    == tuple(pin[k] for k in _fields('dev ino uid gid mode')),
                    'PARENT_CHANGED')
            def directory(path, uid=0, gid=0, mode=493):
                return _prep_directory(self, path, uid, gid, mode, deadline)
            def save(path, value):
                return _prep_file(self, path, canonical(value, newline=True), deadline)
            reservation = plan["directories"]["reservation"]["path"]
            directory(parents["state"]["path"] + "/" + SESSION + "/" + case["case_id"])
            directories["reservation"] = directory(reservation, mode=448)
            # Durable preimage precedes every other case resource.
            objects = {"preparation-plan": save(reservation + "/preparation-plan.json", plan)}
            for role in _fields('state quota journal evidence'):
                session = parents[role]["path"] + "/" + SESSION
                if role != "state" and case["index"] == 1: directory(session)
                info = io.call(os.fstat, io.directory(session))
                _prep_require(info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 493,
                    'SESSION_PROTECTION')
                if role != "state": directory(session + "/" + case["case_id"])
            account = plan["account"]
            for role, row in plan["directories"].items():
                if role == "reservation": continue
                uid, gid = (account["uid"], account["gid"]) if row["owner"] == "ordinary" else (0, 0)
                directories[role] = directory(row["path"], uid, gid, row["mode"])
            for name in _fields('preflight business evidence management_evidence launcher_output supervisor_output owner_output launcher_declarations supervisor_declarations owner_declarations'):
                parent = directories["declarations" if name.endswith("declarations") else "capture"]["path"]
                children[name] = _prep_pin(directory(parent + "/" + name,
                    mode=493 if name == "launcher_declarations" else 448))
            roots = [_prep_root(self, row, account, plan["mounts"]["quota"], deadline) for row in plan["roots"]]
            accounting = getattr(self, '_pool_accounting', None)
            if accounting is not None:
                io.call(accounting.quota_ready, case['case_id'], roots)
                _accounting_observe(accounting, guard, 'CASE_BOUNDARY')
            after = io.call(self._capacity_retained_snapshot, guard=guard)
            remaining = [r for r in io.call(self._capacity_quota_inventory, guard=guard)
                if r["project"] not in case["project_ids"]]
            _prep_require(before == after and _prep_quota_retained(inventory) == _prep_quota_retained(remaining),
                'RETAINED_CHANGED')
            pins = {}
            for role in _fields('controller management query supervisor ordinary'):
                key = "retained_ordinary_cgroup" if role == "ordinary" and case["index"] == 2 else role + "_cgroup"
                pins[role] = _prep_pin(parents[key])
                pins[role]["path"] = pins[role]["path"].removeprefix("/sys/fs/cgroup")
            observed = dict(host=plan["host"], ordinary=account, directories=directories, parents=pins,
                mounts=plan["mounts"], roots=roots, installation=self._installation_receipt,
                capacity_observed={"quota_inventory": inventory}, retained_before=before, retained_after=after)
            if case["index"] != 2: observed["system_geometry"] = self._admission_detail["system_geometry"]
            result = dict(schema="local-hand-q2-fixture-preparation/v1", preparation_id=case["preparation_id"],
                plan_sha256=_sha(objects["preparation-plan"]["raw"]), status="RESOURCES_PREPARED", reason=None,
                facts=observed, q2_accepted=False, q3_accepted=False, production_supported=False, fixture_generated=False)
            objects["preparation-result"] = save(reservation + "/preparation-result.json", result)
            prepared = dict(case=case, intent=intent, plan=plan, receipt=result, children=children,
                source_objects=objects, **_prep_translate(case, plan, result, children, helpers))
            prepared["paths"] = {k: v["path"] for k, v in {**directories, **children}.items()}
            prepared["paths"]["retained_store"] = next(r["path"] for r in roots if r["slot"] == "store")
            for name in ("authority", "manifest"): save(reservation + "/" + name + ".json", prepared[name])
            io.call(_prep_initialize, self, prepared, deadline)
            _accounting_observe(accounting, guard, 'CASE_BOUNDARY')
            return prepared

    def plan_case(self, case, prepared, deadlines):
        _effect(case in CASES and prepared.get("case") == case,
            "PLAN_PREPARATION_REQUIRED")
        now = _prep_guard(self, deadlines["owner_deadline_ns"])
        realtime = time.time_ns()
        expires = prepared["facts"]["identity"]["expires_at"]
        _effect(realtime // NS < expires
            and expires * NS <= realtime + deadlines["owner_deadline_ns"] - now["boottime_ns"],
            "PLAN_REQUEST_EXPIRED")
        plan = _plan_from_prepared(case, prepared, deadlines)
        owner = dict(prepared["plan"]["settings"]["owner"])
        owner.pop("runtime_ns")
        owner.update(issued_ns=now["boottime_ns"], deadline_ns=deadlines["owner_deadline_ns"])
        runtime = self._candidate_modules(("q2_prepare_run",))["q2_prepare_run"]
        schema, purpose = {1: (runtime.SYSTEM_SCHEMA, "ONE_ORIGINAL_Q2_HANDOFF"),
            2: (runtime.CANCEL_SCHEMA, runtime.CANCEL_PURPOSE),
            3: (runtime.H11_SCHEMA, runtime.H11_PURPOSE)}[case["index"]]
        handoff = {"schema": schema, "purpose": purpose,
            "preparation_id": prepared["facts"]["identity"]["id"],
            "boot_id": self.context["guest_deadlines"]["boot_id"],
            "template": prepared["assembled"]["supervisor_template"],
            "supervisor_parent": prepared["assembled"]["supervisor_parent"],
            "output": prepared["children"]["owner_output"],
            "declarations": prepared["children"]["owner_declarations"], "owner_envelope": owner}
        raw = runtime.encoded(handoff)
        runtime.decode(raw, _sha(raw))
        prepared["handoff"] = prepared["handoff_plan"] = handoff
        prepared["handoff_path"] = prepared["paths"]["reservation"] + "/handoff.json"
        prepared["handoff_sha256"] = _sha(raw)
        prepared["source_objects"]["handoff"] = _prep_file(self, prepared["handoff_path"], raw,
            deadlines["owner_deadline_ns"])
        sources = []
        for role in ("preparation-plan", "preparation-result", "authority"):
            record = prepared["source_objects"][role]
            raw = _prep_reread(self, record, deadlines["owner_deadline_ns"])
            suffix = "authority/authority.json" if role == "authority" else "reservation/" + role + ".json"
            sources.append({"path": "cases/" + case["case_id"] + "/" + suffix,
                    "role": role, "mode": 384, "raw": raw})
        raw = canonical(plan, newline=True)
        prepared["source_objects"]["case-plan"] = _prep_file(self,
            prepared["paths"]["reservation"] + "/case-plan.json", raw, deadlines["owner_deadline_ns"])
        sources.append({"path": "cases/" + case["case_id"] + "/reservation/case-plan.json",
                "role": "plan", "mode": 384, "raw": raw})
        prepared["sources"] = list(sources)
        _accounting_observe(getattr(self, '_pool_accounting', None),
            partial(_prep_guard, self, deadlines['owner_deadline_ns']), 'CASE_BOUNDARY')
        return {"plan": plan, "sources": sources}

    def _exec_empty_ledger_gate(self, case, prepared, plan):
        import sqlite3
        self._exec_guard(plan)
        modules = self._candidate_modules(("q2_fixture_check", "local_hand_jobs.policy"))
        checker = modules["q2_fixture_check"]
        policy = modules["local_hand_jobs.policy"].Policy(prepared["assembled"]["policy"])
        fd, held = prepared["_exec_ledger_fd"], prepared["_exec_ledger_identity"]
        path, uid = plan["ledger_path"], prepared["facts"]["ordinary"]["uid"]
        _effect(held["path"] == path == policy.broker_root + "/jobs.sqlite",
            "EMPTY_LEDGER_PATH")
        parent = self._held_directory(policy.broker_root)
        def snapshot():
            self._exec_guard(plan)
            info = os.fstat(fd)
            _effect((info.st_dev, info.st_ino) == (held["dev"], held["ino"])
                and stat.S_ISREG(info.st_mode) and info.st_uid == uid
                and info.st_gid == prepared["facts"]["ordinary"]["gid"]
                and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 384
                and 100 <= info.st_size <= 33554432,
                "EMPTY_LEDGER_IDENTITY")
            for suffix in ("-wal", "-shm", "-journal"):
                try: os.stat("jobs.sqlite" + suffix, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError: continue
                raise _effect.error('EMPTY_LEDGER_SIDECAR')
            raw = os.pread(fd, info.st_size + 1, 0)
            _effect(len(raw) == info.st_size and checker.identity(info) == checker.identity(os.fstat(fd))
                == checker.identity(os.stat("jobs.sqlite", dir_fd=parent, follow_symlinks=False)),
                "EMPTY_LEDGER_CHANGED")
            self._exec_guard(plan)
            return raw, checker.identity(info), checker.identity(os.fstat(parent))
        try:
            before = snapshot()
            checker.empty_ledger(policy, uid, prepared["assembled"]["chain"]["broker_generation"])
            self._exec_guard(plan)
            db = sqlite3.connect(":memory:")
            try:
                raw = before[0]
                db.deserialize(raw[:18] + b"\1\1" + raw[20:])
                db.execute("PRAGMA query_only=ON")
                db.set_progress_handler(lambda: (self._exec_guard(plan), 0)[1], 100)
                rows = db.execute("SELECT key,value FROM metadata").fetchall()
                _effect(len(rows) == 3 and dict(rows) == {"schema": "1",
                    "authority_id": plan["identity"]["authority_id"],
                    "ledger_id": plan["identity"]["ledger_id"]}, "EMPTY_LEDGER_METADATA")
            finally:
                db.close()
            _effect(snapshot() == before, "EMPTY_LEDGER_CHANGED")
        finally:
            os.close(parent)
        gate = {"schema": "local-hand-q2-core-empty-ledger-gate/v1", "session_id": SESSION,
            "index": case["index"], "case_id": case["case_id"], "ledger_path": path,
            "dev": held["dev"], "ino": held["ino"],
            "authority_id": plan["identity"]["authority_id"], "ledger_id": plan["identity"]["ledger_id"],
            "snapshot_sha256": _sha(before[0]), "operations": 0, "events": 0, "leases": 0,
            "sidecars": [], "checked_boottime_ns": self.now()["boottime_ns"],
            "stage": "fixture", "before_submit": True}
        raw = canonical(gate, newline=True)
        _prep_file(self, prepared["paths"]["reservation"] + "/empty-ledger-gate.json", raw,
            plan["deadlines"]["owner_deadline_ns"])
        return {"path": "cases/" + case["case_id"] + "/reservation/empty-ledger-gate.json",
            "role": "empty-ledger-gate", "mode": 384, "raw": raw}

    def _exec_ledger_export(self, case, prepared, plan):
        """Read the closed original ledger; preserve its SQLite TEXT verbatim.

        The case runner calls this only after verifying owner wait/EOF, both
        control seals and the original units' complete stop acknowledgements.
        The descriptor was held before that same original owner was started.
        """
        import sqlite3
        _effect(case in CASES[:2], "LEDGER_EXPORT_CASE")
        held = prepared["_exec_ledger_identity"]
        fd = prepared["_exec_ledger_fd"]
        path = plan["ledger_path"]
        _effect(held["path"] == path, "LEDGER_EXPORT_IDENTITY")
        parent = self._held_directory(str(PurePosixPath(path).parent))
        name = PurePosixPath(path).name
        def identity():
            self._exec_guard(plan)
            info = os.fstat(fd)
            named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _effect(stat.S_ISREG(info.st_mode) and stat.S_ISREG(named.st_mode)
                and info.st_nlink == named.st_nlink == 1
                and (info.st_dev, info.st_ino) == (held["dev"], held["ino"])
                == (named.st_dev, named.st_ino)
                and 0 < info.st_size <= 33554432, "LEDGER_EXPORT_IDENTITY")
            for suffix in ("-wal", "-shm", "-journal"):
                try:
                    os.stat(name + suffix, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise _effect.error('LEDGER_EXPORT_SIDECAR')
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        def digest():
            value = hashlib.sha256()
            offset = 0
            while True:
                self._exec_guard(plan)
                chunk = os.pread(fd, min(65536, 33554433 - offset), offset)
                if not chunk:
                    break
                offset += len(chunk)
                _effect(offset <= 33554432, "LEDGER_EXPORT_SIZE")
                value.update(chunk)
            return offset, value.hexdigest()
        def text_object(raw):
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError("duplicate key")
                    result[key] = value
                return result
            def number(value):
                result = float(value)
                if not math.isfinite(result):
                    raise ValueError("nonfinite number")
                return result
            _effect(type(raw) is str, "LEDGER_EXPORT_TEXT")
            try:
                value = json.loads(raw, object_pairs_hook=pairs,
                    parse_constant=number, parse_float=number)
                _effect(type(value) is dict, "LEDGER_EXPORT_TEXT")
                raw.encode("utf-8", "strict")
            except (ValueError, TypeError, RecursionError, UnicodeError) as error:
                raise _effect.error('LEDGER_EXPORT_TEXT') from error
        connection = None
        try:
            before = identity()
            size, sha = digest()
            _effect(size == before[2], "LEDGER_EXPORT_CHANGED")
            # immutable avoids a read-only WAL connection creating -shm. The
            # prior quiescence/sidecar checks and held-fd reread enforce its premise.
            connection = sqlite3.connect("file:/proc/self/fd/" + str(fd)
                + "?mode=ro&immutable=1", uri=True, timeout=0)
            connection.row_factory = sqlite3.Row
            connection.set_progress_handler(lambda: (self._exec_guard(plan), 0)[1], 100)
            connection.execute("PRAGMA query_only=ON")
            _effect(connection.execute("PRAGMA quick_check").fetchall()[0][0] == "ok",
                "LEDGER_EXPORT_DATABASE")
            metadata = dict(connection.execute("SELECT key,value FROM metadata"))
            identity_fields = plan["identity"]
            _effect(metadata == {"schema": "1", "authority_id": identity_fields["authority_id"],
                    "ledger_id": identity_fields["ledger_id"]},
                "LEDGER_EXPORT_METADATA")
            rows = connection.execute("SELECT namespace,id,parent,principal,digest,reserved_bytes,"
                "request_json,plan_json,record_json FROM operations LIMIT 2").fetchall()
            _effect(len(rows) == 1, "LEDGER_EXPORT_OPERATION")
            operation = dict(rows[0])
            _effect(operation["namespace"] == "job" and operation["id"] == case["operation_id"]
                and operation["principal"] == identity_fields["principal_id"]
                and operation["digest"] == plan["request"]["request_digest"]
                and type(operation["reserved_bytes"]) is int and operation["reserved_bytes"] > 0,
                "LEDGER_EXPORT_OPERATION")
            for key in ("request_json", "plan_json", "record_json"):
                text_object(operation[key])
            events = []
            cursor = connection.execute("SELECT seq,namespace,id,kind,"
                "printf('%.17g',observed_at) AS observed_at,data_json FROM events ORDER BY seq")
            for row in cursor:
                self._exec_guard(plan)
                event = dict(row)
                _effect(type(event["seq"]) is int and event["seq"] > 0
                    and (not events or event["seq"] > events[-1]["seq"])
                    and event["namespace"] == "job" and event["id"] == case["operation_id"]
                    and type(event["kind"]) is str and event["kind"]
                    and re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?", event["observed_at"])
                    is not None, "LEDGER_EXPORT_EVENT")
                text_object(event["data_json"])
                events.append(event)
                _effect(len(events) <= 4096, "LEDGER_EXPORT_SIZE")
            connection.close(); connection = None
            _effect(identity() == before and digest() == (size, sha)
                and identity() == before, "LEDGER_EXPORT_CHANGED")
            exported = self.now()["boottime_ns"]
            value = {"schema": "local-hand-q2-core-ledger-export/v1", "session_id": SESSION,
                "index": case["index"], "case_id": case["case_id"],
                "authority_id": identity_fields["authority_id"], "ledger_id": identity_fields["ledger_id"],
                "operation_id": case["operation_id"], "ledger_identity": dict(path=path,
                    dev=before[0], ino=before[1], bytes=size, sha256=sha),
                "operation": operation, "events": events, "sidecars": [],
                "exported_boottime_ns": exported}
            raw = canonical(value, newline=True, limit=1048576)
            logical = "cases/" + case["case_id"] + "/records/ledger-export.json"
            destination = self._persistence_path(case["case_id"],
                "cases/" + case["case_id"] + "/reservation/ledger-export.json")
            deadline = min(plan["deadlines"]["owner_deadline_ns"],
                self.context["guest_deadlines"]["boottime_deadline_ns"] - REMOTE_FINAL_RESERVE_NS)
            record = _prep_file(self, destination, raw, deadline)
            _effect(_prep_reread(self, record, deadline) == raw, "LEDGER_EXPORT_CHANGED")
            return {"path": logical, "role": "ledger", "mode": 384, "raw": raw}
        finally:
            if connection is not None: connection.close()
            os.close(parent)

    def _exec_guard(self, plan, *, parent_guard=None):
        (self._effect_guard if parent_guard is None else parent_guard)()
        now = self.now(); original = getattr(self, "_active_case_deadlines", {})
        _effect(original.get("owner_deadline_ns") == plan["deadlines"]["owner_deadline_ns"]
            and type(original.get("owner_monotonic_deadline_ns")) is int
            and now["boottime_ns"] < original["owner_deadline_ns"]
            and now["monotonic_ns"] < original["owner_monotonic_deadline_ns"],
            "CASE_DEADLINE")

    def _exec_child(self, argv, plan):
        """Reuse the bounded original wait4/EOF collector with both earlier clocks."""
        original = self._effect_guard
        previous = self.__dict__.get("_effect_guard")
        self._effect_guard = lambda: self._exec_guard(plan, parent_guard=original)
        try:
            # 32 KiB is stricter than the owner 68 KiB maximum; overflow fails.
            raw = self._installation_command(argv)
            _effect(self._install_commands[-1]["stderr"] == b"", "OWNER_STDERR")
            return raw
        finally:
            if previous is None: del self._effect_guard
            else: self._effect_guard = previous

    def _exec_source(self, case, prepared, plan, suffix, role, mode=384):
        _effect.path(suffix, 'CASE_SOURCE_PATH')
        root, relative = suffix.split("/", 1)
        self._exec_guard(plan)
        if role == "result":
            _effect(case["index"] == 1 and suffix == "business/result-03c94c57c840717302854a3f.json",
                "CASE_RESULT_SOURCE")
            physical = prepared["facts"]["slots"][0]["roots"]["evidence"]["path"] + "/" + relative
        elif role.startswith("business-evidence-"):
            _effect(case["index"] == 1, "CASE_RESULT_SOURCE")
            physical = prepared["paths"]["retained_store"] + "/" + relative
        else:
            _effect(root in prepared["paths"], "CASE_SOURCE_ROOT")
            physical = prepared["paths"][root] + "/" + relative
        raw, identity = self.stable_read(physical, maximum=MEMBER_LIMIT, expected_mode=mode)
        self._exec_guard(plan)
        owner = prepared["facts"]["ordinary"] if role == "result" or role.startswith("business-evidence-") else {"uid": 0, "gid": 0}
        _effect(identity["nlink"] == 1 and identity["uid"] == owner["uid"]
            and identity["gid"] == owner["gid"], "CASE_SOURCE_OWNER")
        source = {"path": "cases/" + case["case_id"] + "/" + suffix,
            "role": role, "mode": mode, "raw": raw}
        prepared.setdefault("_exec_physical", {})[source["path"]] = physical
        return source

    def _exec_controls(self, case, prepared, plan, sources, child):
        prefix = "cases/" + case["case_id"] + "/"
        for folder, status in (("supervisor_output", "CONTROLLER_CLOSED"),
            ("owner_output", "SUPERVISOR_CLOSED")):
            stop = _parse_source(sources, prefix + folder + "/stop.json")
            seal = _parse_source(sources, prefix + folder + "/seal.json")
            _effect(stop.get("attempted") is True and stop.get("acknowledged") is True
                and stop.get("parent_empty") is True and stop.get("complete") is True
                and type(stop.get("closed_ns")) is int
                and 0 < stop["closed_ns"] < plan["deadlines"]["owner_deadline_ns"]
                and seal.get("status") == status and seal.get("production_supported") is False,
                "CASE_STOP_UNPROVEN")
            before, after = stop["before"], stop["after"]
            _effect(before["Id"] == after["Id"] == plan["controllers"][
                    "target" if folder == "supervisor_output" else "supervisor"]["unit"]
                and before["InvocationID"] == seal["original"]["invocation_id"]
                and after["MainPID"] == after["ControlPID"] == "0"
                and (after["LoadState"] == "not-found" or (after["LoadState"] == "loaded"
                    and after["ActiveState"] in ("inactive", "failed")
                    and after["InvocationID"] == before["InvocationID"])),
                "CASE_STOP_IDENTITY")
            for source in sources:
                physical = prepared["_exec_physical"].get(source["path"])
                if physical in seal.get("files", {}):
                    _effect(seal["files"][physical] == {"sha256": _sha(source["raw"]),
                        "bytes": len(source["raw"])}, "CASE_CONTROL_SEAL")
            own = next(s for s in sources if s["path"] == prefix + folder + "/stop.json")
            _effect(seal.get("files", {}).get(prepared["_exec_physical"][own["path"]]) ==
                {"sha256": _sha(own["raw"]), "bytes": len(own["raw"])}, "CASE_CONTROL_SEAL")
        _effect(child.get("status") == "SUPERVISOR_CLOSED" and child.get("sealed") is True
            and not child.get("cleanup_errors"), "CASE_OWNER_UNCLOSED")
        return {"requested": True, "acknowledged": True, "tree_exited": True,
            "writers_stopped": True, "deadline_ns": plan["deadlines"]["owner_deadline_ns"]}

    def _exec_case(self, case, prepared, plan):
        _effect(case in CASES and prepared.get("case") == case
            and plan["case_id"] == case["case_id"] and plan["operation_id"] == case["operation_id"],
            "CASE_INPUT")
        _effect(not prepared.get("_exec_attempted"), "CASE_ALREADY_ATTEMPTED")
        self._exec_guard(plan)
        handoff = prepared["handoff"]
        for record in prepared["source_objects"].values():
            _prep_reread(self, record, plan["deadlines"]["owner_deadline_ns"])
        _effect(handoff["owner_envelope"]["deadline_ns"] == plan["deadlines"]["owner_deadline_ns"],
            "CASE_OWNER_DEADLINE")
        raw, _ = self.stable_read(prepared["handoff_path"], maximum=2097152, expected_mode=384)
        _effect(document(raw, limit=2097152, newline=True) == handoff, "CASE_HANDOFF_CHANGED")
        verified = self.verify_install_inputs()
        source_pin = handoff["template"]["launcher"]["source"]
        _effect(source_pin["commit"] == CANDIDATE["commit"]
            and all(verified["source_files"].get(k) == v for k, v in source_pin["files"].items()),
            "CASE_CANDIDATE")
        runtime_root = prepared["facts"]["source"]["root"]
        _effect(runtime_root == self._installation_receipt["source"]["root"],
            "CASE_RUNTIME_ROOT")
        for name, digest in source_pin["files"].items():
            content, _ = self.stable_read(runtime_root + "/" + name,
                maximum=MEMBER_LIMIT, expected_mode=420)
            _effect(_sha(content) == digest, "CASE_SOURCE_CHANGED")
        python = prepared["facts"]["installation"]["programs"]["python"]
        executable, _ = self.stable_read(python["path"], maximum=MEMBER_LIMIT)
        _effect(_sha(executable) == python["sha256"], "CASE_PYTHON_CHANGED")
        parent = self._held_directory(str(PurePosixPath(plan["ledger_path"]).parent))
        fd = -1
        try:
            fd = os.open("jobs.sqlite", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK | os.O_NOATIME,
                dir_fd=parent)
            info = os.fstat(fd)
            _effect(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 384, "CASE_LEDGER")
            prepared["_exec_ledger_fd"] = fd
            prepared["_exec_ledger_identity"] = {"path": plan["ledger_path"], "dev": info.st_dev, "ino": info.st_ino}
            gate_source = self._exec_empty_ledger_gate(case, prepared, plan)
            prepared.setdefault("sources", []).append(gate_source)
            prepared["_exec_attempted"] = True
            child_raw = self._exec_child([python["path"], "-I", "-B", runtime_root +
                "/tests/e3_host/q2_prepare_run.py", "--plan", prepared["handoff_path"], "--sha256", _sha(raw)], plan)
            child = document(child_raw, limit=69632, newline=True)
            for record in prepared["source_objects"].values():
                _prep_reread(self, record, plan["deadlines"]["owner_deadline_ns"])
            current = os.stat("jobs.sqlite", dir_fd=parent, follow_symlinks=False)
            _effect((current.st_dev, current.st_ino) == (info.st_dev, info.st_ino)
                and stat.S_ISREG(current.st_mode), "CASE_LEDGER_CHANGED")
            sources = [gate_source]
            # Only approved fixed names: H11 never touches a business result,
            # raw ledger contents, wildcard or business evidence directory.
            rows = _h01_special("00000000-0000-4000-8000-000000000000") if case["index"] == 1 else (
                Q4_SPECIAL if case["index"] == 2 else H11_SPECIAL)
            for suffix, role, mode in rows:
                if role in _fields('phase-receipt recovery-proof ledger result') or role.startswith("business-evidence-"):
                    continue
                sources.append(self._exec_source(case, prepared, plan, suffix, role, mode))
            sources.append(self._exec_source(case, prepared, plan, "owner_declarations/fixture-check.json", "fixture-check"))
            stop = self._exec_controls(case, prepared, plan, sources, child)
            prefix = "cases/" + case["case_id"] + "/"
            cap = _parse_source(sources, prefix + "launcher_output/capture.json")
            launch = _parse_source(sources, prefix + "launcher_output/result.json")
            _effect(cap.get("complete") is True and cap.get("returncode") == 0
                and set(cap.get("eof", [])) == {"stdout", "stderr"}
                and launch.get("resident_capture") == cap and not launch.get("cleanup_errors")
                and next(s["raw"] for s in sources if s["path"] == prefix +
                    "launcher_output/resident.stderr") == b"", "CASE_QUIESCENCE")
            if case["index"] != 3:
                sources.append(self._exec_ledger_export(case, prepared, plan))
            outcome = self._exec_observations(case, prepared, plan, sources, stop, verified)
            self._record_case_usage(case, prepared, plan, sources, outcome['observations'])
            return outcome
        finally:
            prepared.pop("_exec_ledger_fd", None)
            if fd >= 0: os.close(fd)
            os.close(parent)

    def _exec_observations(self, case, prepared, plan, sources, stop, verified):
        prefix = "cases/" + case["case_id"] + "/"
        get = lambda suffix: _parse_source(sources, prefix + suffix)
        launch, capture = get("launcher_output/result.json"), get("launcher_output/capture.json")
        _effect(capture.get("complete") is True and capture.get("returncode") == 0
            and set(capture.get("eof", [])) == {"stdout", "stderr"}
            and launch.get("resident_capture") == capture and not launch.get("cleanup_errors"),
            "CASE_RESIDENT_CAPTURE")
        stdout = next(s["raw"] for s in sources if s["path"] == prefix + "launcher_output/resident.stdout")
        stderr = next(s["raw"] for s in sources if s["path"] == prefix + "launcher_output/resident.stderr")
        _effect(stderr == b"", "CASE_RESIDENT_STDERR")
        resident = document(stdout, limit=32768, newline=True)
        gate = next(s for s in prepared["sources"] if s["role"] == "empty-ledger-gate")
        obs = {"empty_ledger_gate": _plain_reference(gate)}
        proof = seal_id = None; summary = {}
        if case["index"] == 3:
            proof = self._exec_h11_proof(case, prepared, plan, sources, verified, launch, resident)
            obs.update({k: proof[k] for k in _fields('recovery_plan recovery_summary launcher_result gateway_snapshot origin_capture ledger_identity result_identity')})
            obs.update({k: proof["assertions"][k] for k in _fields('future_start_blocked tree_exited writers_stopped collectors_stopped effects_checked outcome leases_retained result_reread start_replayed business_evidence_sealed')})
            proof_raw = canonical(proof, newline=True)
            obs.update(original_request_accepted=True, control_closure_sealed=True,
                recovery_proof={"path": prefix + "reservation/h11-recovery-proof.json",
                    "bytes": len(proof_raw), "sha256": _sha(proof_raw)})
            # The exact pinned origin submits once after compose's empty gate;
            # candidate recovery asserts the unchanged original ACCEPTED row.
            accepted = self._exec_h11_accepted(case, prepared, plan)
        else:
            export = get("records/ledger-export.json"); operation = export["operation"]
            record = json.loads(operation["record_json"])
            events = export["events"]; accepts = [x for x in events if x["kind"] == "ACCEPTED"]
            _effect(len(accepts) == 1 and operation["id"] == case["operation_id"]
                and operation["digest"] == plan["request"]["request_digest"], "CASE_ACCEPTED")
            accepted = accepts[0]["seq"]
            if case["index"] == 1:
                _effect(launch.get("status") == resident.get("status") == "CHAIN_CLOSED"
                    and resident.get("operation_id") == case["operation_id"]
                    and record.get("lifecycle") == "TERMINAL" and record.get("outcome") == "SUCCEEDED"
                    and record.get("evidence") == "SEALED", "H01_TERMINAL")
                seals = record.get("seals", [])
                _effect(len(seals) == 1, "H01_SEAL_REGISTRATION")
                seal_id = seals[0]["seal_id"]; _h01_special(seal_id)
                for suffix, role, mode in _h01_special(seal_id):
                    if role == "result" or role.startswith("business-evidence-"):
                        sources.append(self._exec_source(case, prepared, plan, suffix, role, mode))
                reader = self._candidate_modules(("local_hand_jobs.result_reader",))["local_hand_jobs.result_reader"]
                business_raw = next(s["raw"] for s in sources if s["role"] == "result")
                business_value = reader._result(reader._strict_json(business_raw, reader.MAX_RESULT_BYTES),
                    "job-" + case["operation_id"] + "-business", "business")
                retained = record.get("quota_pending", {}).get("business", {}).get("proof", {})
                _effect(retained.get("helper_result_verified") is True and retained.get("result") == business_value
                    and business_value.get("outcome") == "SUCCEEDED" and business_value.get("effects_checked") is True,
                    "H01_RESULT_BINDING")
                seal_source = next(s for s in sources if s["path"] == prefix + "business-evidence/" + seal_id + "/seal.json")
                seal = document(seal_source["raw"], limit=MEMBER_LIMIT, newline=False)
                _effect(all(seal.get(k) == v for k, v in seals[0].items() if k in seal)
                    and seal.get("operation_id") == case["operation_id"] and seal.get("complete") is True
                    and _sha(seal_source["raw"]) == seals[0]["seal_sha256"], "H01_BUSINESS_SEAL")
                for artifact in seal["artifacts"]:
                    filename = "evidence.zip" if artifact["role"] == "zip" else "manifest.json"
                    content = next(s["raw"] for s in sources if s["path"] == prefix +
                        "business-evidence/" + seal_id + "/" + filename)
                    _effect(len(content) == artifact["size"] and _sha(content) == artifact["sha256"],
                        "H01_BUSINESS_EVIDENCE")
                units = []
                for phase in case["phases"]:
                    value = get("launcher_output/phase-" + phase + ".json")
                    fence = value.get("fence", {})
                    _effect(value.get("status") == "PHASE_CLOSED" and fence.get("execution_id") ==
                        "job-" + case["operation_id"] + "-" + phase, "H01_PHASE")
                    for stage in ("bootstrap", "helper", "result_reader"):
                        closed = fence["stages"]["reader" if stage == "result_reader" else stage]; identity = closed["identity"]
                        _effect(all(closed.get(k) is True for k in _fields('delivery_settled future_start_blocked job_empty unit_terminal tree_empty collectors_stopped stdout_eof stderr_eof')),
                            "H01_EXIT")
                        units.append({"phase": phase, "stage": stage, "unit": identity["unit"],
                                "invocation_id": identity["invocation_id"]})
                units.sort(key=lambda row: (row["phase"], row["stage"], row["unit"]))
                _validate_units(units, case)
                gateway = get("launcher_output/gateway.json")
                _effect(gateway.get("failure") is None, "H01_GATEWAY")
                for row in units:
                    match = [x for x in gateway["stages"] if all(x.get(k) == v for k, v in row.items())]
                    _effect(len(match) == 1 and match[0].get("sealed") is True
                        and type(match[0].get("returncode")) is int, "H01_GATEWAY_UNIT")
                business = next(x for x in gateway["stages"] if x["phase"] == "business" and x["stage"] == "helper")
                summary = {"business_invocation_id": business["invocation_id"], "business_wait_status": business["returncode"]}
                obs.update({k: True for k in H01_OBSERVATIONS if k not in
                    ("empty_ledger_gate", "resident_empty_gate", "unit_identities")})
                obs["unit_identities"] = units
            else:
                modules = self._candidate_modules(("q2_launcher", "q4_cancel_case"))
                report = modules["q2_launcher"].validate_cancel_result(launch,
                    prepared["handoff"]["template"]["launcher"]["resident"], modules["q4_cancel_case"])
                _effect(report == get("launcher_output/phase.json")["case"] == resident.get("case")
                    and report["status"] == "EXERCISED" and report["helper_exit_proven"] is True,
                    "Q4_NOT_EXERCISED")
                cancels = [x for x in events if x["kind"] == "CANCEL_REQUESTED"]
                _effect(len(cancels) == 1 and cancels[0]["seq"] == report["ledger"]["cancel_event"]["seq"]
                    and record.get("cancel_requested") is True, "Q4_CANCEL_LEDGER")
                manager = record["handles"]["preflight"]["manager"]
                deliveries = [{"seq": x["seq"], "delivery_ids": json.loads(x["data_json"])["delivery_intents"]}
                    for x in events if x["kind"] == "MANAGER_DELIVERY_INTENT"]
                _effect(manager["result_reader"] is None and report["ledger"]["reader_delivered"] is False
                    and report["ledger"]["no_delivery_after_cancel"] is True
                    and deliveries == report["ledger"]["delivery_events"], "Q4_READER_DELIVERED")
                _effect(all(manager["helper"][key] == report["trigger"]["identity"][key]
                    == report["helper"]["identity"][key] for key in ("boot_id", "unit", "invocation_id")),
                    "Q4_HELPER_IDENTITY")
                units = [{"phase": "preflight", "stage": stage, "unit": item["unit"],
                    "invocation_id": item["invocation_id"]} for stage, item in
                    manager.items() if stage in ("bootstrap", "helper")]
                units.sort(key=lambda row: (row["phase"], row["stage"], row["unit"]))
                _validate_units(units, case)
                obs.update({k: True for k in Q4_OBSERVATIONS if k not in
                    _fields('empty_ledger_gate resident_empty_gate unit_identities chain_closed ordinary_phase_closed full_h07')})
                obs.update(unit_identities=units, chain_closed=False, ordinary_phase_closed=False, full_h07=False)
        obs["resident_empty_gate"] = {"passed": True, "candidate_commit": CANDIDATE["commit"],
            "resident_source_sha256": verified["source_files"]["tests/e3_host/q2_resident.py"],
            "accepted_operation_id": case["operation_id"], "accepted_event_seq": accepted}
        return {"sources": sources, "observations": obs, "stop": stop, "proof": proof,
            "seal_id": seal_id, "summary": summary}

    def _exec_h11_proof(self, case, prepared, plan, sources, verified, launch, resident):
        prefix = "cases/" + case["case_id"] + "/"
        item = lambda suffix: next(s for s in sources if s["path"] == prefix + suffix)
        get = lambda suffix: _parse_source(sources, prefix + suffix)
        declaration = get("launcher_declarations/recovery-resident.json")
        modules = self._candidate_modules(("q2_launcher", "q4_h11_recovery"))
        recovery = modules["q4_h11_recovery"].validate(declaration["recovery"])
        report = modules["q2_launcher"].validate_h11_result(launch,
            prepared["handoff"]["template"]["launcher"]["resident"])
        gateway = get("launcher_output/gateway.json")
        origin = get("launcher_output/origin-capture.json")
        _effect(report == resident == get("launcher_output/recovery.json")
            and launch["origin_capture"] == origin and origin.get("complete") is True
            and set(origin.get("eof", [])) == {"stdout", "stderr"}
            and origin.get("returncode") == -signal.SIGKILL
            and recovery["operation_id"] == case["operation_id"]
            and recovery["request_digest"] == plan["request"]["request_digest"]
            and report["units"] == recovery["units"]
            and report["original_deadline_ns"] == recovery["budget_deadline_ns"]
            and report["phase_deadline_ns"] == recovery["phase_deadline_ns"]
            and report["controller_deadline_ns"] == recovery["controller_deadline_ns"]
            and report["original_event_seq"] == recovery["event_seq"]
            and report["event_kinds"].count("RECOVERY_BARRIER") == 1
            and report["event_kinds"].count("QUOTA_EXIT_PENDING") == 1
            and set(report["event_kinds"]) <= modules["q4_h11_recovery"].RECOVERY_EVENTS,
            "H11_ORIGINAL_BINDING")
        _effect(gateway.get("failure") is None and gateway.get("recovery_finished") is True
            and gateway.get("recovery_only") is True and gateway.get("recovery_rebinds") == 1
            and gateway.get("recovery_arm_ack") is True
            and gateway.get("recovery_plan_sha256") == _sha(canonical(recovery)),
            "H11_GATEWAY_BINDING")
        expected_units = _phase_units(case["operation_id"], ["preflight"])[0]
        for stage, unit in recovery["units"].items():
            _effect(unit == expected_units[stage + "_unit"], "H11_UNIT")
            rows = [r for r in gateway["stages"] if r["stage"] == stage and r["phase"] == "preflight"]
            _effect(len(rows) == 1 and rows[0]["unit"] == unit
                and rows[0].get("recovery_observed") is True, "H11_UNIT")
        for stream in ("stdout", "stderr"):
            _effect(item("launcher_output/origin-resident." + stream)["raw"] == b"",
                "H11_ORIGIN_OUTPUT")
        refs = {key: _plain_reference(item(suffix)) for key, suffix in (
            ("recovery_plan", "launcher_declarations/recovery-resident.json"),
            ("recovery_summary", "launcher_output/recovery.json"),
            ("launcher_result", "launcher_output/result.json"),
            ("gateway_snapshot", "launcher_output/gateway.json"),
            ("origin_capture", "launcher_output/origin-capture.json"),
            ("control_seal", "owner_output/seal.json"))}
        refs["recovery_plan"]["embedded_plan_sha256"] = _sha(canonical(recovery))
        candidate = {"commit": CANDIDATE["commit"], "tree": CANDIDATE["tree"]}
        for role, name in (("h11", "q4_h11_recovery"), ("resident", "q2_resident"), ("launcher", "q2_launcher")):
            relative = "tests/e3_host/" + name + ".py"
            candidate.update({role + "_source_path": relative,
                    role + "_source_sha256": verified["source_files"][relative]})
        assertions = {key: report[key] for key in _fields('future_start_blocked tree_exited writers_stopped collectors_stopped effects_checked outcome leases_retained result_reread start_replayed')}
        # These are explicitly the pinned recovery helper's assertions, not
        # invented raw before-snapshots. validate_h11_result has checked them.
        assertions.update({key: True for key in _fields('same_operation same_request_digest original_handle_admitted same_original_stage_units same_grant_and_deadlines delivery_intents_unchanged recovery_launch_forbidden gateway_parts_unchanged')})
        assertions.update(recovery_barrier_count=1, quota_exit_pending_count=1,
            deadline_extended=False, business_evidence_sealed=False)
        basename = "result-f7b176ecb6b8081fac3a7a47.json"
        return {"schema": PROOF_SCHEMA, "session_id": SESSION, "index": case["index"],
            "case_id": case["case_id"], "candidate": candidate, **refs,
            "ledger_identity": {**prepared["_exec_ledger_identity"], "unchanged": True},
            "result_identity": {"expected_path": prepared["facts"]["slots"][0]["roots"]["evidence"]["path"] + "/" + basename,
                "expected_basename": basename, "stat_performed": False, "opened": False, "hashed": False},
            "assertions": assertions}

    def _exec_h11_accepted(self, case, prepared, plan):
        import sqlite3
        self._exec_guard(plan)
        _effect(case == CASES[2], "H11_ACCEPTED_CASE")
        fd = prepared["_exec_ledger_fd"]
        path = PurePosixPath(plan["ledger_path"])
        parent = self._held_directory(str(path.parent))
        def identity():
            self._exec_guard(plan)
            info = os.fstat(fd)
            named = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            _effect(stat.S_ISREG(info.st_mode) and stat.S_ISREG(named.st_mode)
                and info.st_nlink == named.st_nlink == 1
                and (info.st_dev, info.st_ino) == (named.st_dev, named.st_ino),
                "H11_LEDGER_CHANGED")
            for suffix in ("-wal", "-shm", "-journal"):
                try: os.stat(path.name + suffix, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError: continue
                raise _effect.error('H11_LEDGER_SIDECAR')
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        db = None
        try:
            before = identity()
            # Closed WAL-format files must not create reader sidecars.
            db = sqlite3.connect("file:/proc/self/fd/" + str(fd) + "?mode=ro&immutable=1",
                uri=True, timeout=0)
            db.execute("PRAGMA query_only=ON")
            db.set_progress_handler(lambda: (self._exec_guard(plan), 0)[1], 500)
            rows = db.execute("SELECT seq FROM events WHERE namespace='job' AND id=? AND kind='ACCEPTED'",
                (case["operation_id"],)).fetchmany(2)
            _effect(len(rows) == 1 and type(rows[0][0]) is int and rows[0][0] > 0,
                "H11_ACCEPTED_EVENT")
            db.close(); db = None
            _effect(identity() == before, "H11_LEDGER_CHANGED")
        finally:
            if db is not None: db.close()
            os.close(parent)
        self._exec_guard(plan)
        return rows[0][0]

    def run_h01(self, case, prepared, plan):
        _effect(case == CASES[0], "H01_CASE")
        return self._exec_case(case, prepared, plan)

    def run_q4(self, case, prepared, plan):
        _effect(case == CASES[1], "Q4_CASE")
        return self._exec_case(case, prepared, plan)

    def recover_h11(self, case, prepared, plan):
        _effect(case == CASES[2], "H11_CASE")
        return self._exec_case(case, prepared, plan)

    def phase_facts(self, case, phase, plan, sources):
        names = _fields('admin.local_hand_quota_observer.q2_config local_hand_jobs.budget admin.local_hand_quota_observer.controller_guard')
        modules = self._candidate_modules(names)
        return _phase_extract(case, phase, plan, sources, *(modules[name] for name in names))

    def _carrier_usage(self, *, guard=None):
        """Actual bound-cgroup counters, never process rusage or configured limits.

        This is a component observation, not complete usage/resource_accounting.
        It covers this carrier at this pre-return point, not future transmission
        or independently managed business units. No pids.current fallback.
        """
        _effect(self._admission is not None and type(getattr(self, '_admission_detail', None)) is dict,
            'USAGE_ADMISSION_REQUIRED')
        bound = self._admission_detail.get('carrier')
        hello = self.context['hello']['carrier_unit']
        _effect(type(bound) is dict and bound['unit'] == hello['name']
            and bound['path'] == hello['control_group']
            and bound['invocation_id'] == hello['invocation_id'], 'USAGE_CARRIER_BINDING')
        call = self._capacity_call if guard is None else partial(_guard_call, guard)
        kernel = self._capacity_kernel if guard is None else partial(self._capacity_kernel, guard=guard)
        directory = self._capacity_directory if guard is None else partial(self._capacity_directory, guard=guard)
        actual_guard = self._effect_guard if guard is None else guard
        membership = ('0::' + bound['path'] + '\n').encode('ascii')
        _effect(kernel('/proc/self/cgroup', 4096) == membership, 'USAGE_MEMBERSHIP')
        fd = directory('/sys/fs/cgroup' + bound['path'])
        try:
            before = call(os.fstat, fd)
            _effect((before.st_dev, before.st_ino) == (bound['device'], bound['inode'])
                and stat.S_ISDIR(before.st_mode) and before.st_uid == 0,
                'USAGE_CARRIER_IDENTITY')
            cpu_raw = kernel('cpu.stat', 4096, dir_fd=fd)
            cpu = {}
            for line in cpu_raw.decode('ascii', 'strict').splitlines():
                fields = line.split()
                _effect(len(fields) == 2 and re.fullmatch('[a-z_]+', fields[0]) is not None
                    and fields[0] not in cpu and re.fullmatch('[0-9]+', fields[1]) is not None,
                    'USAGE_CPU_STAT')
                cpu[fields[0]] = int(fields[1])
            _effect({'usage_usec', 'user_usec', 'system_usec'} <= set(cpu), 'USAGE_CPU_STAT')
            result = {'carrier_cpu_ns': cpu['usage_usec'] * 1000}
            raw_sources = {'cpu.stat': cpu_raw}
            for filename, field in (('memory.peak', 'carrier_memory_peak_bytes'),
                                    ('pids.peak', 'carrier_pids_peak')):
                raw = kernel(filename, 64, dir_fd=fd)
                _effect(re.fullmatch(rb'[0-9]+\n', raw) is not None, 'USAGE_KERNEL_COUNTER')
                result[field] = int(raw)
                raw_sources[filename] = raw
            after = call(os.fstat, fd)
            _effect(_capacity_stat(before) == _capacity_stat(after), 'USAGE_CARRIER_DRIFT')
            named = directory('/sys/fs/cgroup' + bound['path'])
            try:
                _effect(_capacity_stat(before) == _capacity_stat(call(os.fstat, named)),
                    'USAGE_CARRIER_DRIFT')
            finally:
                os.close(named)
            _effect(kernel('/proc/self/cgroup', 4096) == membership,
                'USAGE_MEMBERSHIP')
            observed_at = self.now()
            actual_guard()
            self._carrier_usage_evidence = dict(binding=copy.deepcopy(bound),
                observed_at=observed_at, sources=raw_sources, counters=copy.deepcopy(result))
            return result
        finally:
            os.close(fd)


    def resource_accounting(self):
        engine = getattr(self, '_pool_accounting', None)
        _effect(engine is not None, 'RESOURCE_ACCOUNTING_INCOMPLETE')
        try:
            engine.observe('FINALIZATION', guard=lambda: _clock(self, self.context['guest_deadlines']))
        except (DispatchError, OSError):
            # The engine retains the failing pool and all previous maxima.
            # Framing that partial evidence performs no further field mutation.
            pass
        return engine.snapshot(_completion_adjustment(self.context))

    def _record_case_usage(self, case, prepared, plan, sources, observations):
        """Count original invocations, never launch intents or budget ceilings.

        Only existing control evidence is read here: the management RunRecord
        and the query's native capture. H11 business paths are never inspected.
        A case is committed atomically after all its actual identities bind.
        """
        self._exec_guard(plan)
        prefix = 'cases/' + case['case_id'] + '/'
        get = lambda suffix: _parse_source(sources, prefix + suffix)
        boot = self.context['hello']['guest_boot_id']
        modules = self._candidate_modules(('admin.local_hand_quota_observer.q2_config',
            'admin.local_hand_quota_observer.q2_runtime'))
        config_api = modules['admin.local_hand_quota_observer.q2_config']
        runtime = modules['admin.local_hand_quota_observer.q2_runtime']
        rows, evidence = [], []
        def add(kind, identity, expected_unit, expected_parent):
            value = _usage_unit_identity(identity, boot, expected_unit, expected_parent)
            rows.append(dict(kind=kind, **value))
        controllers = {}
        for folder, role in (('supervisor_output', 'target'), ('owner_output', 'supervisor')):
            stop, seal = get(folder + '/stop.json'), get(folder + '/seal.json')
            original, before = seal['original'], stop['before']
            spec = plan['controllers'][role]
            _effect(stop['acknowledged'] is True and stop['complete'] is True
                and before['LoadState'] == 'loaded' and before['Id'] == spec['unit']
                and before['InvocationID'] == original['invocation_id']
                and before['ControlGroup'] == spec['cgroup'], 'USAGE_CONTROLLER_IDENTITY')
            identity = dict(boot_id=boot, unit=before['Id'],
                invocation_id=before['InvocationID'], cgroup=before['ControlGroup'])
            add('controller', identity, spec['unit'], str(PurePosixPath(spec['cgroup']).parent))
            controllers[role] = identity
        for phase in case['phases']:
            facts = self.phase_facts(case, phase, plan, sources)
            source = next(item for item in sources if item['path'] == prefix + phase + '/observer.json')
            path = prepared['paths'][phase] + '/observer.json'
            config = config_api.decode(source['raw'], path, _sha(source['raw']))
            grant = config.active(); data = grant.as_dict(); request = data['request']
            _effect(request['boot_id'] == boot and grant.request.digest == facts['quota_request_sha256']
                and request['execution_id'] == 'job-' + case['operation_id'] + '-' + phase,
                'USAGE_REQUEST_BINDING')
            peer = config.data()['peers'][request['request_id']]
            expected = next(row for row in plan['phases'] if row['phase'] == phase)
            if case['index'] == 1:
                fence = get('launcher_output/phase-' + phase + '.json')['fence']
                _effect(fence['request_digest'] == grant.request.digest and fence['boot_id'] == boot
                    and fence['execution_id'] == request['execution_id'], 'USAGE_FENCE_BINDING')
                for stage in ('bootstrap', 'helper', 'result_reader'):
                    closed = fence['stages']['reader' if stage == 'result_reader' else stage]
                    add('job', closed['identity'], expected[stage + '_unit'], peer['parent']['path'])
            elif case['index'] == 2:
                export = get('records/ledger-export.json')
                manager = json.loads(export['operation']['record_json'])['handles']['preflight']['manager']
                _effect(manager['result_reader'] is None, 'USAGE_Q4_READER')
                for stage in ('bootstrap', 'helper'):
                    part = manager[stage]
                    _effect(part['delivery_attempted'] is True
                        and part['execution_id'] == request['execution_id'], 'USAGE_JOB_DELIVERY')
                    identity = {key: part[key] for key in ('boot_id', 'unit', 'invocation_id')}
                    _effect(part['cgroup_parent'] == '/sys/fs/cgroup' + peer['parent']['path'],
                        'USAGE_Q4_CGROUP_PARENT')
                    identity['cgroup'] = part['cgroup_parent'].removeprefix('/sys/fs/cgroup') + '/' + part['unit']
                    add('job', identity, expected[stage + '_unit'], peer['parent']['path'])
            else:
                gateway = get('launcher_output/gateway.json')
                _effect(gateway['recovery_finished'] is True and gateway['recovery_only'] is True
                    and gateway['failure'] is None, 'USAGE_H11_GATEWAY')
                _effect(len(gateway['stages']) == 3, 'USAGE_H11_STAGE_SET')
                for stage in ('bootstrap', 'helper', 'result_reader'):
                    parts = [row for row in gateway['stages'] if row['stage'] == stage and row['phase'] == phase]
                    _effect(len(parts) == 1, 'USAGE_H11_STAGE_SET')
                    identity = _usage_h11_identity(gateway, parts[0], boot,
                        expected[stage + '_unit'], peer['parent'], plan['identity']['authority_id'])
                    add('job', identity, expected[stage + '_unit'], peer['parent']['path'])
            # These are original control files, not a new query or collection run.
            control_path = str(PurePosixPath(path).parent) + '/management.jsonl'
            parent = self._held_directory(prepared['paths'][phase], guard=lambda: self._exec_guard(plan))
            try:
                current = _guard_call(lambda: self._exec_guard(plan), os.fstat, parent)
                declared = prepared['children'][phase]
                _effect((current.st_dev, current.st_ino) == (declared['device'], declared['inode'])
                    and current.st_uid == current.st_gid == 0 and stat.S_IMODE(current.st_mode) == 448,
                    'USAGE_MANAGEMENT_PARENT')
                raw, identity = self.stable_read_at(parent, 'management.jsonl', maximum=65536,
                    expected_mode=384, guard=lambda: self._exec_guard(plan))
            finally:
                os.close(parent)
            _effect(identity['uid'] == identity['gid'] == 0, 'USAGE_CONTROL_OWNER')
            management = _usage_management_record(config, raw, controllers['target'],
                allow_unclosed=case['index'] == 3)
            evidence.append(dict(path=control_path, identity=identity, kind='management'))
            for name, value in management.items():
                add('dynamic', value, facts['listener_unit' if name == 'listener' else 'admission_unit'],
                    data['management_parent']['path'])
            query_path = config.data()['evidence']['path'] + '/' + grant.request.digest + '.json'
            parent = self._held_directory(config.data()['evidence']['path'], guard=lambda: self._exec_guard(plan))
            try:
                current = _guard_call(lambda: self._exec_guard(plan), os.fstat, parent)
                declared = config.data()['evidence']
                _effect((current.st_dev, current.st_ino) == (declared['device'], declared['inode'])
                    and current.st_uid == current.st_gid == 0 and stat.S_IMODE(current.st_mode) == 448,
                    'USAGE_QUERY_PARENT')
                raw, identity = self.stable_read_at(parent, grant.request.digest + '.json', maximum=MEMBER_LIMIT,
                    expected_mode=384, guard=lambda: self._exec_guard(plan))
            finally:
                os.close(parent)
            _effect(identity['uid'] == identity['gid'] == 0, 'USAGE_CONTROL_OWNER')
            query, native = _usage_query_record(config, raw, runtime)
            add('query', dict(query, boot_id=boot), facts['query_unit'], data['query_parent']['path'])
            evidence.append(dict(path=query_path, identity=identity, kind='query', native_reports=native))
            if case['index'] == 1:
                for name, value in (('query', query), ('collector', management['listener']),
                    ('admission', management['admission'])):
                    original = fence['stages'][name]['identity']
                    _effect(all(original[key] == value[key] for key in ('unit', 'invocation_id', 'cgroup')),
                        'USAGE_FENCE_IDENTITY')
            rows.append(dict(kind='native', boot_id=boot, unit=query['unit'],
                invocation_id=query['invocation_id'], count=native))
        self._exec_guard(plan)
        _usage_commit_case(self, case, rows, evidence)


    def usage(self):
        """Keep known groups; unknown facts stay null with exact missing roles."""
        fields = _fields('guest_elapsed_ns carrier_cpu_ns carrier_memory_peak_bytes carrier_pids_peak stdin_bytes_received output_frame_bytes guest_allocated_bytes guest_allocated_inodes job_units_started controller_units_started quota_query_units_started dynamic_quota_units_started native_children_started')
        value = dict.fromkeys(fields)
        value.update(stdin_bytes_received=self.context['stdin_bytes_received'], output_frame_bytes=0)
        missing = []; diagnostics = []
        def unknown(keys, code):
            detail = _sha(canonical(dict(code=code, fields=list(keys))))
            missing.extend(dict(code=code, role='usage/' + key, detail_sha256=detail) for key in keys)
            diagnostics.append(dict(code=code, fields=list(keys)))
        counts = _fields('job_units_started controller_units_started quota_query_units_started dynamic_quota_units_started native_children_started')
        try:
            cases = getattr(self, '_usage_cases', {})
            _effect(set(cases) == {case['case_id'] for case in CASES}, 'USAGE_ACCOUNTING_INCOMPLETE')
            units, native = _usage_merge_cases(cases.values())
            value.update(job_units_started=sum(row['kind'] == 'job' for row in units.values()),
                controller_units_started=sum(row['kind'] == 'controller' for row in units.values()),
                quota_query_units_started=sum(row['kind'] == 'query' for row in units.values()),
                dynamic_quota_units_started=sum(row['kind'] in ('query', 'dynamic') for row in units.values()),
                native_children_started=sum(native.values()))
        except (DispatchError, KeyError, TypeError, ValueError):
            unknown(counts, 'CORE_USAGE_STARTS_INCOMPLETE')
        allocated = ('guest_allocated_bytes', 'guest_allocated_inodes')
        try:
            snapshot = getattr(self, '_resource_snapshot', None)
            _effect(type(snapshot) is dict and snapshot.get('missing') == []
                and snapshot.get('full_guest_filesystem_peak_proven') is False, 'USAGE_RESOURCE_INCOMPLETE')
            observed = snapshot['observed_maxima_sum']
            _effect(type(observed) is dict and set(observed) == {'bytes', 'inodes'}
                and all(type(amount) is int and amount >= 0 for amount in observed.values()),
                'USAGE_RESOURCE_INCOMPLETE')
            value.update(guest_allocated_bytes=observed['bytes'], guest_allocated_inodes=observed['inodes'])
        except (DispatchError, KeyError, TypeError, ValueError):
            unknown(allocated, 'CORE_USAGE_RESOURCE_INCOMPLETE')
        carrier = ('carrier_cpu_ns', 'carrier_memory_peak_bytes', 'carrier_pids_peak')
        guard = lambda: _clock(self, self.context['guest_deadlines'])
        try:
            now = guard()
            origin = self.context['hello']['guest_boottime_origin_ns']
            _effect(type(origin) is int and now['boottime_ns'] >= origin, 'USAGE_CLOCK')
            value['guest_elapsed_ns'] = now['boottime_ns'] - origin
        except (DispatchError, OSError, KeyError, TypeError, ValueError):
            unknown(('guest_elapsed_ns', *carrier), 'CORE_USAGE_CLOCK_INCOMPLETE')
        else:
            try:
                observed = self._carrier_usage(guard=guard)
                _effect(set(observed) == set(carrier) and all(type(amount) is int and amount >= 0
                    for amount in observed.values()), 'USAGE_CARRIER_INCOMPLETE')
                value.update(observed)
            except (DispatchError, OSError, KeyError, TypeError, ValueError):
                # A partially read cgroup lacks the original final identity check.
                # Keep its raw diagnostic privately, never promote it as a count.
                unknown(carrier, 'CORE_USAGE_CARRIER_INCOMPLETE')
        self._usage_missing = sorted(missing, key=lambda row: (row['code'], row['role'], row['detail_sha256']))
        self._usage_diagnostics = diagnostics
        return value



def _usage_h11_identity(gateway, part, boot, unit, parent, authority):
    """Count the original invocation, retaining raw terminal observations unchanged."""
    _effect(gateway['manager_binding'] == dict(schema='local-hand-manager-binding/v1',
        manager_kind='system', authority_id=authority, boot_id=boot, parent=parent),
        'USAGE_H11_MANAGER_BINDING')
    observed = part['identity_observation']
    _effect(part['recovery_observed'] is True and part['unit'] == unit
        and observed['LoadState'] == 'loaded' and observed['Id'] == unit
        and observed['InvocationID'] == part['invocation_id'], 'USAGE_H11_IDENTITY')
    group = observed['ControlGroup']
    if group == '':
        # The frozen gateway permits a terminal unit's first observation to
        # have no remaining leaf cgroup. This is a derived counting key from
        # the original pinned manager, not a new observed ControlGroup value.
        after = part['after']
        _effect((observed['SubState'] == 'exited' or observed['ActiveState'] in ('inactive', 'failed'))
            and part['stop_ack'] is True and part['collectors_lost'] is True
            and after['Id'] == unit and after['ActiveState'] in ('inactive', 'failed')
            and after['Job'] in ('', '0') and after['ControlGroup'] in ('', parent['path'] + '/' + unit)
            and (after['LoadState'] == 'loaded' and after['InvocationID'] == part['invocation_id']
                or after['LoadState'] == 'not-found' and after['InvocationID'] == ''),
            'USAGE_H11_TERMINAL_IDENTITY')
        group = parent['path'] + '/' + unit
    return _usage_unit_identity(dict(boot_id=boot, unit=unit,
        invocation_id=part['invocation_id'], cgroup=group), boot, unit, parent['path'])


def _usage_unit_identity(value, boot, unit, parent):
    _effect(type(value) is dict and value.get('boot_id') == boot
        and value.get('unit') == unit and value.get('cgroup') == parent + '/' + unit
        and type(value.get('invocation_id')) is str
        and re.fullmatch(r'[0-9a-f]{32}', value['invocation_id']) is not None
        and value['invocation_id'] != '0' * 32, 'USAGE_UNIT_IDENTITY')
    return {key: value[key] for key in ('boot_id', 'unit', 'invocation_id', 'cgroup')}


def _usage_management_record(config, raw, controller, *, allow_unclosed):
    """Validate the original append-only record before counting actual invocations."""
    _effect(type(raw) is bytes and 0 < len(raw) <= 65536 and raw.endswith(b'\n'), 'USAGE_MANAGEMENT_RECORD')
    lines = raw.splitlines(keepends=True)
    _effect(5 <= len(lines) <= 6, 'USAGE_MANAGEMENT_RECORD')
    data = config.active().as_dict(); boot = data['request']['boot_id']
    previous = '0' * 64; delivered = {}; observed = {}; closed = None
    for index, line in enumerate(lines):
        row = document(line, limit=32769, newline=True)
        _effect.exact(row, ('kind', 'value', 'previous_digest'), 'USAGE_MANAGEMENT_RECORD')
        _effect(row['previous_digest'] == previous and closed is None, 'USAGE_MANAGEMENT_CHAIN')
        previous = _sha(line); value = row['value']; kind = row['kind']
        if index == 0:
            _effect(kind == 'INTENT' and value['config_digest'] == config.digest,
                'USAGE_MANAGEMENT_INTENT')
            _effect(all(value['controller'][key] == expected for key, expected in controller.items())
                and type(value['controller']['observed_ns']) is int
                and data['management']['issued_ns'] <= value['controller']['observed_ns']
                < value['deadline_ns'] <= data['request']['deadline_ns'], 'USAGE_MANAGEMENT_CONTROLLER')
        elif kind in ('DELIVERY', 'INVOCATION'):
            role = value['role']
            _effect(role in ('listener', 'admission'), 'USAGE_MANAGEMENT_ROLE')
            unit = ('lhqoc-' if role == 'listener' else 'lhqoa-') + config.active().request.digest + '.service'
            _effect(value['unit'] == unit, 'USAGE_MANAGEMENT_UNIT')
            if kind == 'DELIVERY':
                _effect(role not in delivered and type(value['command_digest']) is str
                    and re.fullmatch(r'[0-9a-f]{64}', value['command_digest']) is not None,
                    'USAGE_MANAGEMENT_DELIVERY')
                delivered[role] = value
            else:
                _effect(role in delivered and role not in observed, 'USAGE_MANAGEMENT_INVOCATION')
                observed[role] = _usage_unit_identity(dict(value, boot_id=boot,
                    cgroup=data['management_parent']['path'] + '/' + unit), boot, unit, data['management_parent']['path'])
        elif kind == 'CLOSED':
            _effect(set(observed) == {'listener', 'admission'} and index == len(lines) - 1,
                'USAGE_MANAGEMENT_CLOSED')
            _effect(value['schema'] == 'local-hand-quota-management-closed/v1'
                and value['config_digest'] == config.digest
                and value['request_digest'] == config.active().request.digest
                and all(value['controller'][key] == expected for key, expected in controller.items()),
                'USAGE_MANAGEMENT_CLOSED')
            for role, stage in (('listener', 'collector'), ('admission', 'admission')):
                _effect(all(value['stages'][stage]['identity'][key] == expected
                    for key, expected in observed[role].items()), 'USAGE_MANAGEMENT_CLOSED')
            closed = value
        else:
            raise _effect.error('USAGE_MANAGEMENT_RECORD')
    _effect(set(observed) == {'listener', 'admission'} and (closed is not None or allow_unclosed),
        'USAGE_MANAGEMENT_INCOMPLETE')
    return observed


def _usage_query_record(config, raw, runtime):
    """A validated original native-set counts the children that actually ran."""
    proof = document(raw, limit=MEMBER_LIMIT, newline=False)
    _effect.exact(proof, ('query', 'terminal', 'stopped', 'captures'), 'USAGE_QUERY_RECORD')
    query = proof['query']; data = config.active().as_dict()
    _usage_unit_identity(dict(query, boot_id=data['request']['boot_id']), data['request']['boot_id'],
        config.active().request.query_unit, data['query_parent']['path'])
    terminal = proof['terminal']
    _effect(proof['stopped'] is True and terminal['Id'] == query['unit']
        and terminal['InvocationID'] == query['invocation_id'] and terminal['ControlGroup'] == query['cgroup']
        and terminal['LoadState'] == 'loaded' and terminal['Result'] == 'success'
        and terminal['ExecMainCode'] == '1' and terminal['ExecMainStatus'] == '0', 'USAGE_QUERY_TERMINAL')
    captures = proof['captures']
    _effect(type(captures) is list and 1 <= len(captures) <= 64, 'USAGE_QUERY_CAPTURE')
    for capture in captures:
        _effect.exact(capture, ('stdout', 'stderr', 'eof', 'error', 'returncode'), 'USAGE_QUERY_CAPTURE')
        _effect(capture['eof'] == ['stderr', 'stdout'] and capture['error'] is None
            and type(capture['returncode']) is int and capture['returncode'] == 0
            and capture['stderr'] == '', 'USAGE_QUERY_CAPTURE')
    native_raw = captures[-1]['stdout'].encode('ascii', 'strict')
    native = document(native_raw, limit=MEMBER_LIMIT, newline=False)
    # Frozen validator checks request/config/query, each root, native ABI, calls,
    # exit status and complete report count. Never use configured roots as starts.
    runtime.reports(config, native_raw, query)
    _effect(type(native['reports']) is list and 1 <= len(native['reports']) <= 4, 'USAGE_NATIVE_REPORTS')
    return query, len(native['reports'])


def _usage_merge_cases(cases):
    units = {}; native = {}; invocations = {}
    for case in cases:
        for row in case['rows']:
            key = (row['boot_id'], row['unit'])
            invocation_key = (row['boot_id'], row['invocation_id'])
            _effect(invocations.get(invocation_key, row['unit']) == row['unit'], 'USAGE_INVOCATION_ALIAS')
            invocations[invocation_key] = row['unit']
            if row['kind'] == 'native':
                native_key = (*key, row['invocation_id'])
                _effect(type(row['count']) is int and 1 <= row['count'] <= 4
                    and native.get(native_key, row['count']) == row['count'], 'USAGE_NATIVE_CONFLICT')
                native[native_key] = row['count']
            else:
                _effect(row['kind'] in ('job', 'controller', 'query', 'dynamic')
                    and units.get(key, row) == row, 'USAGE_IDENTITY_CONFLICT')
                units[key] = row
    for key in native:
        _effect(key[:2] in units and units[key[:2]]['kind'] == 'query'
            and units[key[:2]]['invocation_id'] == key[2], 'USAGE_NATIVE_BINDING')
    _effect({key for key, row in units.items() if row['kind'] == 'query'} == {key[:2] for key in native},
        'USAGE_NATIVE_INCOMPLETE')
    return units, native


def _usage_commit_case(effects, case, rows, evidence):
    _effect(case in CASES, 'USAGE_CASE')
    item = dict(rows=copy.deepcopy(rows), evidence=copy.deepcopy(evidence))
    prior = getattr(effects, '_usage_cases', {})
    _effect(case['case_id'] not in prior or prior[case['case_id']] == item, 'USAGE_CASE_CHANGED')
    proposed = dict(prior, **{case['case_id']: item})
    _usage_merge_cases(proposed.values())
    effects._usage_cases = proposed
    effects._usage_evidence = {name: copy.deepcopy(value['evidence']) for name, value in proposed.items()}



def _phase_extract(case, phase, plan, sources, config_api, budget_api, controller_api):
    """Rebuild receipts from original candidate bytes, never from plan defaults."""
    _phase_raw(case in CASES and phase in case["phases"], "CASE")
    by_path = {}
    for source in sources:
        _source(source, case_id=case["case_id"])
        _phase_raw(source["path"] not in by_path, "DUPLICATE")
        by_path[source["path"]] = source
    rows = {}
    for path, role in phase_source_specs(case, phase):
        item = by_path.get(path)
        _phase_raw(item is not None and item["role"] == role
            and item["mode"] == (420 if role == "recovery-plan" else 384), "SOURCE")
        rows[role] = item
    values = {role: document(item["raw"], limit=MEMBER_LIMIT,
            newline=role == "preparation-result")
        for role, item in rows.items()}
    try:
        prepared = values["preparation-result"]
        _phase_raw.exact(prepared, _fields('schema preparation_id plan_sha256 status reason facts q2_accepted q3_accepted production_supported fixture_generated'), "PREPARATION")
        _phase_raw(prepared["schema"] == "local-hand-q2-fixture-preparation/v1"
            and prepared["status"] == "RESOURCES_PREPARED" and prepared["reason"] is None
            and prepared["preparation_id"] == plan["preparation_id"]
            and all(prepared[key] is False for key in
                _fields('q2_accepted q3_accepted production_supported fixture_generated')),
            "PREPARATION")
        observed = prepared["facts"]
        raw = rows["observer-config"]["raw"]
        path = observed["directories"]["capture"]["path"] + "/" + phase + "/observer.json"
        config = config_api.decode(raw, path, _sha(raw))
        grant = config.active()
        data, request = grant.as_dict(), grant.request.as_dict()
        execution = "job-" + case["operation_id"] + "-" + phase
        _phase_raw(config.data()["source_commit"] == CANDIDATE["commit"]
            and request["execution_id"] == execution and request["phase"] == phase
            and request["boot_id"] == observed["host"]["boot_id"]
            and request["generation"] == plan["identity"]["slot_generation"]
            and all(request[key] == plan["identity"][key]
                for key in ("authority_digest", "manifest_digest", "epoch")),
            "GRANT_BINDING")
        budget = data["budget"]
        budget_api.validate_grant(budget, execution_id=execution, phase=phase,
            namespace="job", operation_id=case["operation_id"], record_id=case["operation_id"],
            original_budgets=plan["budgets"]["operation"])
        original_roots = {row["project_id"]: row for row in observed["roots"]}
        _phase_raw(len(original_roots) == 7 and set(original_roots) == set(case["project_ids"]),
            "ROOTS")
        projects = case["project_ids"][3:] if phase == "evidence" else case["project_ids"][:3]
        _phase_raw(len(data["roots"]) == len(projects)
            and {row["project_id"] for row in data["roots"]} == set(projects), "ROOTS")
        for root in data["roots"]:
            original = original_roots.get(root["project_id"])
            _phase_raw(original is not None and all(original[key] == value for key, value in root.items()),
                "ROOTS")
        reservation = values["launcher-reservation"]
        _phase_raw.exact(reservation, _fields('schema fixture_digest session controller started_ns'),
            "RESERVATION")
        _phase_raw(reservation["schema"] == ("local-hand-q2-system-launcher-reservation/v1"
                if case["index"] == 1 else "local-hand-q2-launcher-reservation/v1"
                if case["index"] == 2 else "local-hand-q4-h11-launcher-reservation/v1")
            and reservation["session"] == plan["identity"]["session"], "RESERVATION")
        _digest(reservation["fixture_digest"])
        envelope = reservation["controller"]
        _phase_raw.exact(envelope, _fields('controller issued_ns deadline_ns output_bytes storage_bytes storage_inodes'), "CONTROLLER")
        _integer(envelope["issued_ns"], 1)
        _integer(reservation["started_ns"], 1)
        controller_api.decode_controller(envelope["controller"])
        target = plan["controllers"]["target"]
        _phase_raw(all(envelope["controller"][key] == value for key, value in target.items())
            and envelope["issued_ns"] <= reservation["started_ns"] < envelope["deadline_ns"]
            and envelope["deadline_ns"] <= plan["deadlines"]["owner_deadline_ns"]
            and envelope["deadline_ns"] - envelope["issued_ns"]
            <= envelope["controller"]["runtime_max_usec"] * 1000
            and envelope["output_bytes"] == 32768
            and all(envelope[key] == plan["controllers"]["target_" + key]
                for key in ("storage_bytes", "storage_inodes")), "CONTROLLER")
        digest = grant.request.digest
        facts = dict(quota_request_id=request["request_id"], quota_request_sha256=digest,
            query_unit=grant.request.query_unit, listener_unit="lhqoc-" + digest + ".service",
            admission_unit="lhqoa-" + digest + ".service",
            budget_deadline_ns=budget["deadline_boottime_ns"],
            phase_deadline_ns=budget_api.phase_deadline_ns(budget),
            stage_deadline_ns=budget_api.phase_deadline_ns(budget) - budget["limits"]["terminate_grace_seconds"] * NS,
            controller_deadline_ns=envelope["deadline_ns"])
        _phase_raw(request["deadline_ns"] <= facts["stage_deadline_ns"]
            and facts["budget_deadline_ns"] <= facts["controller_deadline_ns"], "DEADLINE")
        _phase_raw_binding(case, phase, plan, values, grant.digest, facts)
        _phase_receipt(case, phase, facts, sources)
        return facts
    except DispatchError:
        raise
    except Exception as error:
        raise _phase_raw.error("RAW_INVALID") from error


def _phase_raw_binding(case, phase, plan, values, grant_digest, facts):
    launcher = values["launcher-result"]
    _phase_raw(launcher["q3_accepted"] is False and launcher["production_supported"] is False,
        "LAUNCHER")
    if case["index"] != 3:
        result = values["phase-result"]
        _phase_raw(result["grant_digest"] == grant_digest and result["q3_accepted"] is False
            and result["production_supported"] is False, "RESULT")
        if case["index"] == 1:
            _phase_raw(result["status"] == "PHASE_CLOSED" and launcher["status"] == "CHAIN_CLOSED"
                and launcher["grant_digests"][phase] == grant_digest
                and result["fence"]["request_digest"] == facts["quota_request_sha256"],
                "RESULT")
        else:
            report = result["case"]
            _phase_raw(result["status"] == launcher["status"] == "CANCEL_CASE_RECORDED"
                and launcher["grant_digest"] == grant_digest and launcher["case"] == report
                and report["operation_id"] == case["operation_id"]
                and report["request_digest"] == plan["request"]["request_digest"]
                and report["phase_deadline_ns"] == facts["stage_deadline_ns"],
                "CANCEL_BINDING")
    else:
        original = values["recovery-plan"]["recovery"]
        summary = values["recovery-summary"]
        _phase_raw(launcher["status"] == "RECOVERY_RECORDED" and launcher["recovery"] == summary,
            "RECOVERY")
        for item, budget_name in ((original, "budget_deadline_ns"), (summary, "original_deadline_ns")):
            _phase_raw(item["operation_id"] == case["operation_id"] and item["phase"] == phase
                and item[budget_name] == facts["budget_deadline_ns"]
                and all(item[key] == facts[key] for key in ("phase_deadline_ns", "controller_deadline_ns")),
                "RECOVERY_DEADLINE")
        expected = next(row for row in plan["phases"] if row["phase"] == phase)
        _phase_raw(original["units"] == summary["units"] ==
            {key: expected[key + "_unit"] for key in ("bootstrap", "helper", "result_reader")},
            "RECOVERY_UNITS")


def _clock(effects, deadlines):
    now = effects.now()
    _check.exact(now, ("boot_id", "boottime_ns", "monotonic_ns"), 'CLOCK_FIELDS')
    _check(now["boot_id"] == deadlines["boot_id"], 'BOOT_CHANGED')
    _check.integer(now["boottime_ns"], 1, code='CLOCK')
    _check.integer(now["monotonic_ns"], 1, code='CLOCK')
    _check(now["boottime_ns"] < deadlines["boottime_deadline_ns"]
        and now["monotonic_ns"] < deadlines["monotonic_deadline_ns"],
        'DEADLINE')
    return now


def _persist(effects, case_id, path, role, value, *, mode=384, raw=False):
    content = value if raw else canonical(value, newline=True)
    returned = effects.persist(case_id, path, content, mode)
    _source(returned, case_id=None if case_id == "carrier" else case_id)
    _check(returned == {"path": path, "role": role, "mode": mode, "raw": content},
        'PERSIST_RESULT')
    return returned


def _validate_phase_receipts(case, sources, phase_facts, owner_deadline):
    _phase(type(phase_facts) is dict and set(phase_facts) == set(case["phases"]), "FACTS")
    generated = []
    for phase in case["phases"]:
        facts = phase_facts[phase]
        _check(facts["controller_deadline_ns"] <= owner_deadline, "CONTROLLER_DEADLINE")
        generated.append((phase, _phase_receipt(case, phase, facts, sources)))
    return generated


def _case_outcome(effects, case, intent, intent_source, deadlines):
    effects._active_case_deadlines = dict(deadlines)
    prepared = effects.prepare_case(case, intent, deadlines["preparation_deadline_ns"])
    _check(type(prepared) is dict, 'PREPARED')
    now = _clock(effects, effects.context["guest_deadlines"])
    _check(now["boottime_ns"] < deadlines["preparation_deadline_ns"]
        and now["monotonic_ns"] < deadlines["preparation_monotonic_deadline_ns"],
        'PREPARATION_DEADLINE')
    owner_deadline = min(now["boottime_ns"] + OWNER_NS, deadlines["remote_final_deadline_ns"])
    owner_mono_deadline = min(now["monotonic_ns"] + OWNER_NS,
        deadlines["remote_final_monotonic_deadline_ns"])
    effects._active_case_deadlines.update(owner_deadline_ns=owner_deadline,
        owner_monotonic_deadline_ns=owner_mono_deadline)
    plan_deadlines = {
        "case_origin_ns": deadlines["case_origin_ns"],
        "preparation_deadline_ns": deadlines["preparation_deadline_ns"],
        "owner_deadline_ns": owner_deadline,
        "remote_final_deadline_ns": deadlines["remote_final_deadline_ns"],
        "carrier_deadline_ns": deadlines["carrier_deadline_ns"],
    }
    planned = effects.plan_case(case, prepared, plan_deadlines)
    _check(type(planned) is dict and set(planned) == {"plan", "sources"},
        'PLANNED')
    plan = validate_plan(case, intent, planned["plan"], plan_deadlines)
    sources = [intent_source, *planned["sources"]]
    for source in sources:
        _source(source, case_id=case["case_id"])
    plan_path = "cases/" + case["case_id"] + "/reservation/case-plan.json"
    plan_source = next((item for item in sources if item["path"] == plan_path), None)
    _check(plan_source == {"path": plan_path, "role": "plan", "mode": 384,
            "raw": canonical(plan, newline=True)},
        'PLAN_SOURCE')
    if case["index"] == 1:
        outcome = effects.run_h01(case, prepared, plan)
    elif case["index"] == 2:
        outcome = effects.run_q4(case, prepared, plan)
    else:
        outcome = effects.recover_h11(case, prepared, plan)
    _check.exact(outcome, _fields('sources observations stop proof seal_id summary'),
        'OUTCOME_FIELDS')
    sources.extend(outcome["sources"])
    for source in sources:
        _source(source, case_id=case["case_id"])
    phase_facts = {phase: effects.phase_facts(case, phase, plan, sources)
        for phase in case["phases"]}
    receipts = _validate_phase_receipts(case, sources, phase_facts, owner_deadline)
    prefix = "cases/" + case["case_id"] + "/"
    for phase, receipt in receipts:
        sources.append(_persist(effects, case["case_id"],
                prefix + "reservation/phase-" + phase + "-receipt.json",
                "phase-receipt", receipt, mode=384))
    proof = outcome["proof"]
    if case["index"] == 3:
        _validate_h11_proof(proof, case, sources, owner_deadline)
        sources.append(_persist(effects, case["case_id"],
                prefix + "reservation/h11-recovery-proof.json",
                "recovery-proof", proof, mode=384))
    else:
        _check(proof is None, 'UNEXPECTED_PROOF')
    # Add a temporary verdict source only after all other exact members exist.
    expected_without_verdict = set(required_paths(case, seal_id=outcome["seal_id"]))
    expected_without_verdict = {row for row in expected_without_verdict if row[1] != "verdict"}
    actual_without_verdict = {(item["path"], item["role"], item["mode"]) for item in sources}
    _check(actual_without_verdict == expected_without_verdict,
        'PREVERDICT_SET')
    placeholder = {"path": prefix + "reservation/case-verdict.json", "role": "verdict",
        "mode": 384, "raw": b""}
    verdict = _validate_verdict(case, outcome["observations"], outcome["stop"],
        sources + [placeholder], proof, owner_deadline)
    verdict_source = _persist(effects, case["case_id"], placeholder["path"],
        "verdict", verdict, mode=384)
    sources.append(verdict_source)
    _validate_source_set(case, sources, seal_id=outcome["seal_id"])
    _check(type(outcome["summary"]) is dict, 'SUMMARY')
    if case["index"] == 1:
        summary = _h01_summary(case, sources, outcome["summary"], outcome["seal_id"])
    else:
        _check(outcome["summary"] == {} and outcome["seal_id"] is None,
            'NON_H01_SUMMARY')
        summary = {"seal_id": None}
    return sources, verdict, summary, owner_mono_deadline


def _h01_summary(case, sources, observed, seal_id):
    _check.exact(observed, ("business_invocation_id", "business_wait_status"),
        "H01_SUMMARY_INPUT")
    _check(re.fullmatch(r"[0-9a-f]{32}", observed["business_invocation_id"] or "") is not None,
        "H01_SUMMARY_INPUT")
    _check.integer(observed["business_wait_status"], 0, 255,
        "H01_SUMMARY_INPUT")
    prefix = "cases/" + case["case_id"] + "/"
    result = next(item for item in sources
        if item["path"] == prefix + "business/result-03c94c57c840717302854a3f.json")
    evidence = next(item for item in sources
        if item["path"] == prefix + "business-evidence/" + seal_id + "/seal.json")
    references = [_reference(item, sealed=None) for item in sources]
    references.sort(key=lambda row: (row["role"].encode("ascii"), row["path"].encode("ascii")))
    result_ref = _reference(result, sealed=None)
    execution_id = "job-" + case["operation_id"] + "-business"
    business_unit = next(item["helper_unit"] for item in _phase_units(
        case["operation_id"], case["phases"]) if item["phase"] == "business")
    return {
        "seal_id": seal_id,
        "h01_business_execution": {
            "status": "VERIFIED", "operation_id": case["operation_id"],
            "execution_id": execution_id, "unit": business_unit,
            "invocation_id": observed["business_invocation_id"],
            "wait_status": observed["business_wait_status"], "business_started": True,
            "outcome": "SUCCEEDED", "evidence_sha256": _sha(evidence["raw"]),
        },
        "h01_result_package": {
            "status": "VERIFIED", "result_member": result_ref,
            "result_sha256": result_ref["sha256"],
            "required_members_sha256": _sha(canonical(references)),
        },
    }


def _case_deadlines(now, outer):
    remote_boot = outer["boottime_deadline_ns"] - REMOTE_FINAL_RESERVE_NS
    remote_mono = outer["monotonic_deadline_ns"] - REMOTE_FINAL_RESERVE_NS
    _check(remote_boot - now["boottime_ns"] >= CASE_GATE_NS
        and remote_mono - now["monotonic_ns"] >= CASE_GATE_NS, "CASE_GATE")
    return {
        "case_origin_ns": now["boottime_ns"],
        "preparation_deadline_ns": min(now["boottime_ns"] + PREPARATION_NS,
            remote_boot - OWNER_NS),
        "preparation_monotonic_deadline_ns": min(now["monotonic_ns"] + PREPARATION_NS,
            remote_mono - OWNER_NS),
        "remote_final_deadline_ns": remote_boot,
        "remote_final_monotonic_deadline_ns": remote_mono,
        "carrier_deadline_ns": outer["boottime_deadline_ns"],
    }


def _completion_adjustment(context):
    return {"baseline": COMPLETION_ADJUSTMENT_BASELINE,
        "owner_decision": COMPLETION_ADJUSTMENT_OWNER_DECISION,
        "closure": COMPLETION_ADJUSTMENT_CLOSURE,
        "implementation": context["manifest"]["implementation"]}


def _resource_missing(rows):
    _check(type(rows) is list, 'RESOURCE_MISSING')
    order = []
    for row in rows:
        _check.exact(row, _fields('code role detail_sha256'), 'RESOURCE_MISSING')
        _check(all(type(row[key]) is str and row[key] and row[key].isascii()
            for key in ('code', 'role')), 'RESOURCE_MISSING')
        _check.digest(row['detail_sha256'], 'RESOURCE_MISSING')
        order.append((row['code'], row['role'], row['detail_sha256']))
    _check(order == sorted(set(order)), 'RESOURCE_MISSING')
    return rows


def _validate_resource_accounting(value, context, *, admission=None, plans=(),
        installation=None, preparations=(), complete=True):
    """Check the produced record before framing; the host verifies independently."""
    _check.exact(value, _fields('schema completion_adjustment basis full_guest_filesystem_peak_proven pools observed_maxima_sum snapshot_sha256 missing'), 'RESOURCE_FIELDS')
    _check(value['schema'] == RESOURCE_SCHEMA
        and value['basis'] == 'APPLICATION_AND_OBSERVED_OWNED_ALLOCATION'
        and value['full_guest_filesystem_peak_proven'] is False, 'RESOURCE_GUARANTEE')
    _check(value['completion_adjustment'] == _completion_adjustment(context), 'RESOURCE_AUTHORITY')
    for part in ('commit', 'tree'):
        _check.commit(context['manifest']['implementation'][part], 'RESOURCE_AUTHORITY')
        _check(context['manifest']['implementation'][part] != '0' * 40, 'RESOURCE_AUTHORITY')
    _resource_missing(value['missing'])
    _check(not complete or not value['missing'], 'RESOURCE_INCOMPLETE')
    definitions = _resource_pools(context['manifest']['locators'])
    _check(type(value['pools']) is list and len(value['pools']) == len(definitions) == 32,
        'RESOURCE_POOL_SET')
    pins = {}
    for plan in plans:
        case = next((case for case in CASES if case['case_id'] == plan.get('case_id')), None)
        _check(case is not None, 'RESOURCE_PLAN')
        fixed_paths = {row['path'] for row in _planned_roots(case)}
        for row in plan['roots']:
            pin = row['observed']
            _check(pin['path'] in fixed_paths, 'RESOURCE_PLAN')
            path = context['manifest']['locators']['quota_parent'] + '/' + pin['path']
            _check(path not in pins, 'RESOURCE_ROOT_DUPLICATE')
            pins[path] = dict(dev=pin['device'], ino=pin['inode'],
                fs_uuid=pin['filesystem_uuid'], project_id=pin['project_id'])
    if installation is not None:
        pins[installation['destination']] = dict(dev=installation['dev'], ino=installation['ino'],
            project_id=None)
    for prepared in preparations:
        for pin in prepared['facts']['directories'].values():
            _check(pin['path'] not in pins, 'RESOURCE_ROOT_DUPLICATE')
            pins[pin['path']] = dict(dev=pin['device'], ino=pin['inode'], project_id=None)
    parents = {} if admission is None else admission['parents']
    absent = set() if admission is None else {row['name'] for row in admission['absence']
        if row['kind'] == 'path' and row['absent'] is True and row['collision'] is False}
    known = {}; inode_paths = {}; total = [0, 0]; all_known = True
    case_totals = {case['case_id']: [0, 0] for case in CASES}
    for pool, spec in zip(value['pools'], definitions, strict=True):
        _check.exact(pool, _fields('pool_id case_id measurement_kind byte_limit inode_limit status controlled_io last_observation bytes_maximum inodes_maximum missing'), 'RESOURCE_POOL_FIELDS')
        _check(all(pool[key] == spec[key] for key in
            _fields('pool_id case_id measurement_kind byte_limit inode_limit')), 'RESOURCE_POOL_BINDING')
        _check(pool['status'] in ('OBSERVED', 'ABSENT', 'INCOMPLETE'), 'RESOURCE_STATUS')
        missing = _resource_missing(pool['missing'])
        _check(all(row in value['missing'] for row in missing), 'RESOURCE_MISSING_BINDING')
        roles = {row['role'] for row in missing}
        io = _check.exact(pool['controlled_io'], _fields('written_bytes created_inodes'), 'RESOURCE_IO')
        for amount in io.values():
            if amount is None:
                _check(pool['status'] == 'INCOMPLETE'
                    and pool['pool_id'] + '/controlled_io' in roles, 'RESOURCE_IO_MISSING')
            else:
                _check.integer(amount, code='RESOURCE_IO')
        observed = []; local_identities = {}
        for field in ('last_observation', 'bytes_maximum', 'inodes_maximum'):
            observation = pool[field]
            if observation is None:
                _check(pool['status'] == 'INCOMPLETE' and pool['pool_id'] + '/' + field in roles,
                    'RESOURCE_OBSERVATION_MISSING')
                continue
            _check.exact(observation, _fields('method boundary boottime_ns monotonic_ns allocated_bytes allocated_inodes identities quota source_sha256'), 'RESOURCE_OBSERVATION_FIELDS')
            method = observation['method']
            _check(method in (spec['measurement_kind'], 'VERIFIED_ABSENCE')
                and observation['boundary'] in ('ADMISSION', 'CONTROLLED_IO', 'CHILD_BEFORE',
                    'CHILD_AFTER', 'CASE_BOUNDARY', 'FINALIZATION'), 'RESOURCE_METHOD')
            for clock in ('boottime', 'monotonic'):
                timestamp = _check.integer(observation[clock + '_ns'], code='RESOURCE_WINDOW')
                _check(context['hello']['guest_' + clock + '_origin_ns'] <= timestamp
                    < context['guest_deadlines'][clock + '_deadline_ns'], 'RESOURCE_WINDOW')
            for amount, limit in (('allocated_bytes', spec['byte_limit']),
                    ('allocated_inodes', spec['inode_limit'])):
                _check.integer(observation[amount], code='RESOURCE_ALLOCATION')
                _check(not complete or observation[amount] <= limit, 'RESOURCE_LIMIT')
            payload = {key: actual for key, actual in observation.items() if key != 'source_sha256'}
            _check(observation['source_sha256'] == _sha(canonical(dict(pool_id=pool['pool_id'],
                case_id=pool['case_id'], observation=payload))), 'RESOURCE_SOURCE_DIGEST')
            identities = observation['identities']
            _check(admission is not None and type(identities) is list and 1 <= len(identities) <= 16,
                'RESOURCE_IDENTITIES')
            present_paths = {identity.get('path') for identity in identities
                if type(identity) is dict and identity.get('role') == 'POOL_ROOT'}
            coverage = set(); paths = []
            for identity in identities:
                _check.exact(identity, _fields('path role dev ino fs_uuid project_id'), 'RESOURCE_IDENTITY_FIELDS')
                path = _check.absolute(identity['path'], 'RESOURCE_IDENTITY_PATH'); paths.append(path)
                _check.integer(identity['dev'], code='RESOURCE_IDENTITY')
                _check.integer(identity['ino'], 1, code='RESOURCE_IDENTITY')
                _check(type(identity['fs_uuid']) is str and re.fullmatch(
                    r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', identity['fs_uuid']) is not None,
                    'RESOURCE_IDENTITY')
                role = identity['role']
                _check(role in ('POOL_ROOT', 'ABSENCE_PARENT'), 'RESOURCE_IDENTITY')
                matched = []
                for root in spec['roots']:
                    parent = parents[root['parent_role']]
                    match = path == root['path'] if role == 'POOL_ROOT' else (
                        root['path'] in absent and root['path'] not in present_paths and (path == parent['path']
                            or (path in known or path in pins) and root['path'].startswith(path + '/')))
                    if match:
                        _check(identity['dev'] == parent['dev'] and identity['fs_uuid'] == parent['fs_uuid'],
                            'RESOURCE_DEVICE_BINDING')
                        matched.append(root['path'])
                _check(matched and not coverage.intersection(matched), 'RESOURCE_ROOT_COVERAGE')
                coverage.update(matched)
                if role == 'ABSENCE_PARENT':
                    pin = next((parent for parent in parents.values() if parent.get('path') == path),
                        known.get(path, pins.get(path)))
                    _check(pin is not None and all(identity[key] == pin[key] for key in ('dev', 'ino'))
                        and ('fs_uuid' not in pin or identity['fs_uuid'] == pin['fs_uuid'])
                        and identity['project_id'] is None, 'RESOURCE_ABSENCE_BINDING')
                else:
                    pin = pins.get(path)
                    _check(identity['project_id'] == spec['project_id']
                        and (spec['project_id'] is None or pin is not None)
                        and (pin is None or all(identity[key] == actual for key, actual in pin.items())),
                        'RESOURCE_PREPARATION_BINDING')
                    inode = (identity['dev'], identity['ino'])
                    _check(inode not in inode_paths or inode_paths[inode] == path, 'RESOURCE_ALIAS')
                    inode_paths[inode] = path
                key = (path, role)
                _check(key not in local_identities or local_identities[key] == identity, 'RESOURCE_IDENTITY_DRIFT')
                local_identities[key] = identity
            _check(paths == sorted(set(paths)) and coverage == {root['path'] for root in spec['roots']},
                'RESOURCE_ROOT_COVERAGE')
            if method == 'PROJECT_QUOTA':
                quota = _check.exact(observation['quota'],
                    _fields('project_id hard_bytes hard_inodes used_bytes used_inodes enforcement_flags'), 'RESOURCE_QUOTA')
                for amount in quota.values():
                    _check.integer(amount, code='RESOURCE_QUOTA')
                _check(len(identities) == 1 and identities[0]['role'] == 'POOL_ROOT'
                    and quota['project_id'] == spec['project_id']
                    and quota['hard_bytes'] == spec['byte_limit'] and quota['hard_inodes'] == spec['inode_limit']
                    and quota['used_bytes'] == observation['allocated_bytes']
                    and quota['used_inodes'] == observation['allocated_inodes']
                    and quota['enforcement_flags'] & 0x30 == 0x30, 'RESOURCE_QUOTA')
            else:
                _check(observation['quota'] is None, 'RESOURCE_QUOTA')
                if method == 'VERIFIED_ABSENCE':
                    _check(observation['allocated_bytes'] == observation['allocated_inodes'] == 0
                        and all(identity['role'] == 'ABSENCE_PARENT' for identity in identities), 'RESOURCE_ABSENCE')
            observed.append(observation)
        if pool['status'] == 'INCOMPLETE':
            _check(not complete and missing, 'RESOURCE_INCOMPLETE'); all_known = False
        else:
            method = 'VERIFIED_ABSENCE' if pool['status'] == 'ABSENT' else spec['measurement_kind']
            _check(not missing and len(observed) == 3 and None not in io.values()
                and all(item['method'] == method for item in observed), 'RESOURCE_INCOMPLETE')
            _check(not complete or pool['last_observation']['boundary'] == 'FINALIZATION', 'RESOURCE_FINAL_BOUNDARY')
            if pool['status'] == 'ABSENT':
                _check(io == dict(written_bytes=0, created_inodes=0)
                    and not any(path == root['path'] or path.startswith(root['path'] + '/')
                        for path in pins for root in spec['roots']), 'RESOURCE_ABSENCE_IO')
            amounts = [pool['bytes_maximum']['allocated_bytes'], pool['inodes_maximum']['allocated_inodes']]
            for index, amount in enumerate(amounts):
                total[index] += amount
                if pool['case_id'] is not None:
                    case_totals[pool['case_id']][index] += amount
        for field, amount in (('bytes_maximum', 'allocated_bytes'), ('inodes_maximum', 'allocated_inodes')):
            maximum = pool[field]
            if maximum is not None:
                _check(all(maximum[amount] >= item[amount] for item in observed), 'RESOURCE_MAXIMUM')
                if pool['last_observation'] is not None:
                    _check(all(maximum[clock + '_ns'] <= pool['last_observation'][clock + '_ns']
                        for clock in ('boottime', 'monotonic')), 'RESOURCE_TIME_ORDER')
        for (path, role), identity in local_identities.items():
            if role == 'POOL_ROOT':
                _check(path not in known or known[path] == identity, 'RESOURCE_IDENTITY_DRIFT')
                known[path] = identity
    _check.exact(value['observed_maxima_sum'], ('bytes', 'inodes'), 'RESOURCE_TOTAL_FIELDS')
    _check(value['observed_maxima_sum'] == dict(zip(('bytes', 'inodes'), total if all_known else (None, None))),
        'RESOURCE_TOTAL_BINDING')
    _check(not complete or total[0] <= LIMITS['total_guest_physical_bytes']
        and total[1] <= LIMITS['total_guest_physical_inodes']
        and all(amount[0] <= LIMITS['case_physical_bytes'] and amount[1] <= LIMITS['case_physical_inodes']
            for amount in case_totals.values()), 'RESOURCE_TOTAL_LIMIT')
    _check(value['snapshot_sha256'] == _sha(canonical({key: value[key] for key in
        ('completion_adjustment', 'pools', 'observed_maxima_sum')})), 'RESOURCE_SNAPSHOT_DIGEST')
    return value


def _usage(value, context, frame_bytes, *, accounting=None, missing=(), complete=True):
    fields = _fields('guest_elapsed_ns carrier_cpu_ns carrier_memory_peak_bytes carrier_pids_peak stdin_bytes_received output_frame_bytes guest_allocated_bytes guest_allocated_inodes job_units_started controller_units_started quota_query_units_started dynamic_quota_units_started native_children_started')
    _check.exact(value, fields, "USAGE_FIELDS")
    for key in fields:
        if value[key] is None:
            _check(not complete and any(row['role'] == 'usage/' + key for row in missing), 'USAGE_MISSING')
        else:
            _check.integer(value[key], 0, code="USAGE")
    _check(value["stdin_bytes_received"] == context["stdin_bytes_received"]
        and value["output_frame_bytes"] in (0, frame_bytes), "USAGE_BINDING")
    ceilings = {"carrier_cpu_ns": 800 * NS, "carrier_memory_peak_bytes": 1073741824,
        "carrier_pids_peak": 128, "guest_allocated_bytes": 188743680,
        "guest_allocated_inodes": 13440, "job_units_started": 15,
        "controller_units_started": 6, "quota_query_units_started": 5,
        "dynamic_quota_units_started": 15, "native_children_started": 16}
    ceilings['guest_elapsed_ns'] = context['bind']['guest_duration_ns']
    _check(not complete or all(value[key] <= limit for key, limit in ceilings.items()), "USAGE_LIMIT")
    if accounting is not None:
        _check(value['guest_allocated_bytes'] == accounting['observed_maxima_sum']['bytes']
            and value['guest_allocated_inodes'] == accounting['observed_maxima_sum']['inodes'], 'USAGE_RESOURCE_BINDING')
    return value


def _session(context, admission, installation):
    manifest, bind, hello = context["manifest"], context["bind"], context["hello"]
    return {
        "schema": SESSION_SCHEMA, "scope": SCOPE,
        "rule": RULE, "baseline": BASELINE, "owner_decision": OWNER_DECISION,
        "closure": CLOSURE, "implementation": manifest["implementation"],
        "amendment": manifest["amendment"],
        "package": {"basename": bind["package_basename"], "bytes": bind["package_bytes"],
            "sha256": bind["package_sha256"],
            "manifest_sha256": _sha(canonical(manifest, newline=True))},
        "entry": manifest["entry"], "locators": manifest["locators"],
        "consumption": _consumption_info(context),
        "session_id": SESSION,
        "outer": {**{key: bind[key] for key in _fields('host_boottime_origin_ns host_monotonic_origin_ns host_boottime_deadline_ns host_monotonic_deadline_ns clock_margin_ns host_boottime_bind_ns host_monotonic_bind_ns hello_sha256 mapped_duration_ns host_remaining_floor_ns guest_duration_cap_ns guest_duration_ns')},
            **{key: hello[key] for key in _fields('guest_boot_id guest_boottime_origin_ns guest_monotonic_origin_ns')},
            "guest_boottime_deadline_ns": context["guest_deadlines"]["boottime_deadline_ns"],
            "guest_monotonic_deadline_ns": context["guest_deadlines"]["monotonic_deadline_ns"],
            "remote_final_reserve_ns": REMOTE_FINAL_RESERVE_NS,
            "local_final_reserve_ns": bind["local_final_reserve_ns"]},
        "admission": admission, "installation": installation,
        "output": {"stdout_basename": ".lhqcore-20261007a.stdout",
            "stderr_basename": ".lhqcore-20261007a.stderr",
            "remote_result_basename": ".lhqcore-20261007a.remote-result.json",
            "capture_manifest_basename": ".lhqcore-20261007a.capture-manifest.json",
            "local_receipt_basename": ".lhqcore-20261007a.acceptance-receipt.json",
            "output_package_bytes": FRAME_LIMIT, "stderr_bytes": STDERR_LIMIT},
        "limits": LIMITS, "cases": [{key: case[key] for key in
                _fields('index case_id kind predecessor preparation_id operation_id controller_prefix project_ids phases')} for case in CASES],
        "state": "REMOTE_FINALIZED",
    }


def _absolute_text(value, code):
    FieldEffects._absolute(value, code)
    return value


def _program_identity(value, code):
    _exact(value, _fields('path dev ino mode uid gid nlink bytes sha256'),
        code)
    _absolute_text(value["path"], code)
    for key in _fields('dev uid gid bytes'):
        _integer(value[key], 0, code=code)
    _integer(value["ino"], 1, code=code)
    _require(value["mode"] in (365, 493) and value["nlink"] == 1,
        code)
    _digest(value["sha256"], code)
    return value


def _validate_admission(value, context):
    _admit.exact(value, _fields('guest programs policies parents filesystems capacity absence binding prior_core_attempts'),
        "FIELDS")
    _validate_admission_binding(value["binding"], context)
    _validate_prior_quiescences(value['prior_core_attempts'], context)
    locators = context['manifest']['locators']
    guest = _admit.exact(value["guest"], _fields('hostname dmi_vendor dmi_product initial_userns boot_id pid1_exe pid1_version cgroup_version ordinary_user ordinary_uid ordinary_gid ordinary_groups user_manager_unit user_manager_invocation_id user_manager_cgroup'), "GUEST_FIELDS")
    _admit(type(guest["hostname"]) is str and 1 <= len(guest["hostname"]) <= 253
        and (guest["dmi_vendor"] in ("QEMU", "KVM") or guest["dmi_product"] == "KVM")
        and guest["cgroup_version"] == 2
        and type(guest["ordinary_user"]) is str
        and type(guest["ordinary_groups"]) is list
        and all(type(item) is int and item >= 0 for item in guest["ordinary_groups"]), "GUEST")
    _admit.exact(guest["initial_userns"], ("dev", "ino"), "NAMESPACE")
    _admit.integer(guest["initial_userns"]["dev"], 0, code="NAMESPACE")
    _admit.integer(guest["initial_userns"]["ino"], 1, code="NAMESPACE")
    _admit.integer(guest["ordinary_uid"], 1, 2**32 - 2, "ACCOUNT")
    _admit.integer(guest["ordinary_gid"], 1, 2**32 - 2, "ACCOUNT")
    _admit(guest['boot_id'] == context['hello']['guest_boot_id']
        and guest['ordinary_user'] == locators['ordinary_user']
        and guest['ordinary_groups'] == [guest['ordinary_gid']]
        and guest['user_manager_unit'] == locators['user_manager_unit']
        == 'user@' + str(guest['ordinary_uid']) + '.service', 'GUEST_BINDING')
    _admit.absolute(guest["pid1_exe"], "PID1")
    _admit(type(guest["pid1_version"]) is str and guest["pid1_version"].startswith("systemd ")
        and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
            guest["boot_id"] or "") is not None
        and re.fullmatch(r"[0-9a-f]{32}", guest["user_manager_invocation_id"] or "")
        is not None, "GUEST")
    _admit.absolute(guest["user_manager_cgroup"], "GUEST")
    programs = _admit.exact(value["programs"],
        _fields('python git cc setpriv systemctl systemd_run'),
        "PROGRAM_FIELDS")
    for item in programs.values():
        _admit.program(item, "PROGRAM")
    _admit(programs["setpriv"]["path"] == "/usr/bin/setpriv"
        and programs["systemctl"]["path"] == "/usr/bin/systemctl"
        and programs["systemd_run"]["path"] == "/usr/bin/systemd-run", "PROGRAM")
    policies = _admit.exact(value["policies"], _fields('sudo sshd authorized_keys rc'),
        "POLICY_FIELDS")
    basis = _approved_inputs_envelope(context)["policy_basis"]
    for name, item in policies.items():
        relation = _exact(item.get("relation"), _fields('stage pre_entry_containment policy_basis_sha256 predicate_sha256 snapshot_sha256 facts_sha256 matched'), "CORE_ADMIT_POLICY_RELATION")
        _require(relation["stage"] == "POST_ENTRY_PRE_H01_INTENT"
            and relation["pre_entry_containment"] is False and relation["matched"] is True
            and relation["policy_basis_sha256"] == _sha(canonical(basis))
            and relation["predicate_sha256"] == basis["policies"][name]["predicate_sha256"]
            and relation["snapshot_sha256"] == item["sha256"], "CORE_ADMIT_POLICY_RELATION")
        for key in ("predicate_sha256", "snapshot_sha256", "facts_sha256"):
            _digest(relation[key], "CORE_ADMIT_POLICY_RELATION")
        _admit.exact(item, _fields('paths bytes sha256 relation'), "POLICY")
        _admit(type(item["paths"]) is list and item["paths"]
            and all(type(path) is str and path.startswith("/") for path in item["paths"])
            and type(item["bytes"]) is int and item["bytes"] >= 0
            and type(item["relation"]) is dict, "POLICY")
        _admit.digest(item["sha256"], "POLICY")
    directory_roles = _fields('state quota install journal evidence')
    cgroup_roles = _fields('controller_cgroup management_cgroup supervisor_cgroup query_cgroup ordinary_cgroup retained_ordinary_cgroup')
    parents = _admit.exact(value["parents"], directory_roles + cgroup_roles, "PARENT_FIELDS")
    for role in directory_roles:
        item = _admit.exact(parents[role], _fields('path dev ino mode uid gid nlink mount_id fs_uuid'), "DIRECTORY")
        _admit.absolute(item["path"], "DIRECTORY")
        _admit(item['path'] == locators[role + '_parent'] and item['uid'] == item['gid'] == 0,
            'DIRECTORY_BINDING')
        for key in _fields('dev uid gid mount_id'):
            _admit.integer(item[key], 0, code="DIRECTORY")
        _admit.integer(item["ino"], 1, code="DIRECTORY")
        _admit(item["mode"] in (448, 493) and item["nlink"] >= 2
            and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
                item["fs_uuid"] or "") is not None, "DIRECTORY")
    for role in cgroup_roles:
        item = _admit.exact(parents[role], _fields('path dev ino unit invocation_id controllers'),
            "CGROUP")
        _admit.absolute(item["path"], "CGROUP")
        _admit.integer(item["dev"], 0, code="CGROUP")
        _admit.integer(item["ino"], 1, code="CGROUP")
        _admit(type(item["unit"]) is str and item["unit"].endswith((".slice", ".service"))
            and re.fullmatch(r"[0-9a-f]{32}", item["invocation_id"] or "") is not None
            and type(item["controllers"]) is list
            and all(controller in ("cpu", "memory", "pids")
                for controller in item["controllers"]), "CGROUP")
        runtime = _validate_runtime_binding(_approved_inputs_envelope(context)['reconciliation']['journal_transition']['runtime_parent_binding'])
        target = runtime['parents'][role.removesuffix('_cgroup')]
        expected_unit = target['unit']
        _admit(item['unit'] == expected_unit
            and item['path'].startswith('/sys/fs/cgroup/')
            and PurePosixPath(item['path']).name == expected_unit, 'CGROUP_BINDING')
        _admit(item['path'] == '/sys/fs/cgroup' + target['control_group'], 'CGROUP_BINDING')
    filesystems = _admit.exact(value["filesystems"], directory_roles, "FILESYSTEM_FIELDS")
    for role, item in filesystems.items():
        _admit.exact(item, _fields('mount_id dev fs_uuid fstype mount_options bytes_available inodes_available'), "FILESYSTEM")
        for key in _fields('mount_id dev bytes_available inodes_available'):
            _admit.integer(item[key], 0, code="FILESYSTEM")
        _admit(item["mount_id"] == parents[role]["mount_id"]
            and item["dev"] == parents[role]["dev"]
            and item["fs_uuid"] == parents[role]["fs_uuid"]
            and item["fstype"] == "ext4"
            and type(item["mount_options"]) is list
            and all(type(option) is str for option in item["mount_options"]), "FILESYSTEM")
    capacity = value["capacity"]
    _admit(type(capacity) is list and capacity, "CAPACITY")
    reserves = _cap_new_reservations(filesystems, locators)
    historical = _cap_historical_expected(_approved_inputs_envelope(context), filesystems, locators)
    _admit((filesystems['state']['dev'], filesystems['state']['fs_uuid']) ==
        (filesystems['install']['dev'], filesystems['install']['fs_uuid']), 'CAPACITY_DEVICE')
    ordering = []
    seen_roles = set()
    for row in capacity:
        _admit.exact(row, _fields('dev fs_uuid roles historical_bytes historical_inodes new_required_bytes new_required_inodes bytes_available inodes_available admitted'), "CAPACITY")
        for key in _fields('dev historical_bytes historical_inodes new_required_bytes new_required_inodes bytes_available inodes_available'):
            _admit.integer(row[key], 0, code="CAPACITY")
        _admit(type(row["roles"]) is list and row["roles"]
            and row["roles"] == sorted(row["roles"])
            and not (seen_roles & set(row["roles"]))
            and set(row["roles"]) <= set(directory_roles)
            and row["admitted"] is True
            and row["bytes_available"] >= row["historical_bytes"] + row["new_required_bytes"]
            and row["inodes_available"] >= row["historical_inodes"] + row["new_required_inodes"],
            "CAPACITY")
        seen_roles.update(row["roles"]); ordering.append((row["dev"], row["fs_uuid"]))
        key = (row['dev'], row['fs_uuid'])
        _admit(key in reserves and all((filesystems[role]['dev'], filesystems[role]['fs_uuid']) == key
            for role in row['roles']), 'CAPACITY_DEVICE')
        for field in ('bytes', 'inodes'):
            _admit(row['new_required_' + field] == reserves[key][field]
                and row['historical_' + field] == historical[key][field]
                and row[field + '_available'] == min(filesystems[role][field + '_available']
                    for role in row['roles']), 'CAPACITY_RESERVATION')
    _admit(seen_roles == set(directory_roles) and ordering == sorted(reserves), "CAPACITY")
    absence = value["absence"]
    _admit(type(absence) is list and absence, "ABSENCE")
    ordering = []
    for row in absence:
        _admit.exact(row, _fields('kind name parent_dev parent_ino project_id unit absent collision'), "ABSENCE")
        _admit(row["kind"] in ("path", "project", "unit")
            and type(row["name"]) is str and row["name"]
            and row["absent"] is True and row["collision"] is False, "ABSENCE")
        for key in ("parent_dev", "parent_ino", "project_id"):
            _admit(row[key] is None or type(row[key]) is int and row[key] >= 0, "ABSENCE")
        _admit(row["unit"] is None or type(row["unit"]) is str, "ABSENCE")
        ordering.append((row["kind"], row["name"]))
    _admit(ordering == sorted(ordering) and len(ordering) == len(set(ordering)), "ABSENCE")
    _admit(_admission_absent_paths(locators) <= {row['name'] for row in absence if row['kind'] == 'path'},
        'ABSENCE_PATH_SET')
    _admit({*range(12051, 12058), *(p for case in CASES for p in case['project_ids'])} <=
        {row['project_id'] for row in absence if row['kind'] == 'project'}, 'ABSENCE_PROJECT_SET')
    unit_absence = [row for row in absence if row['kind'] == 'unit']
    _admit({row['name'] for row in unit_absence} == _admission_absent_units()
        and all(row['unit'] == row['name'] and row['parent_dev'] is None
            and row['parent_ino'] is None and row['project_id'] is None
            for row in unit_absence), 'ABSENCE_UNIT_SET')
    return value


def _validate_installation(value, manifest):
    _check.exact(value, _fields('destination staging receipt_path dev ino mode uid gid members_sha256 native_sha256 projection_sha256 wheel_sha256 allocated_bytes allocated_inodes status'), "INSTALLATION_FIELDS")
    expected_members = _sha(canonical(manifest["members"]))
    locators = manifest["locators"]
    expected_destination = str(PurePosixPath(locators["install_parent"]) / INSTALL_BASENAME)
    expected_staging = str(PurePosixPath(locators["install_parent"]) / STAGING_BASENAME)
    expected_receipt = str(PurePosixPath(locators["state_parent"]) / SESSION / "carrier"
        / "installation.json")
    _check(value["members_sha256"] == expected_members
        and value["projection_sha256"] == PROJECTION["sha256"]
        and value["wheel_sha256"] == WHEEL["sha256"] and value["status"] == "INSTALLED"
        and value["destination"] == expected_destination
        and value["staging"] == expected_staging
        and value["receipt_path"] == expected_receipt
        and value["mode"] == 493 and value["uid"] == value["gid"] == 0
        and type(value["dev"]) is int and value["dev"] >= 0
        and type(value["ino"]) is int and value["ino"] > 0
        and type(value["allocated_bytes"]) is int and value["allocated_bytes"] > 0
        and type(value["allocated_inodes"]) is int and value["allocated_inodes"] > 0
        and value["allocated_bytes"] <= LIMITS["shared_bytes"]
        and value["allocated_inodes"] <= LIMITS["shared_inodes"], "INSTALLATION")
    _check.digest(value["native_sha256"], "INSTALLATION")
    return value


def dispatch(context, effects):
    """Run the exact H01 -> Q4 -> H11 chain and return one complete frame."""
    _validate_context(context)
    _check(isinstance(effects, FieldEffects) or all(hasattr(effects, name) for name in _fields('now admit install persist prepare_case plan_case run_h01 run_q4 recover_h11 phase_facts usage resource_accounting')), 'EFFECTS')
    # The first clock/deadline gate precedes every persistent field effect.
    _clock(effects, context["guest_deadlines"])
    admission = _validate_admission(effects.admit({"hello": context["hello"],
                "manifest": context["manifest"],
                "guest_deadlines": context["guest_deadlines"]}), context)
    installation = _validate_installation(effects.install({"manifest": context["manifest"],
                "members": context["members"],
                "admission": admission}),
        context["manifest"])
    all_sources = []
    admission_source = _persist(effects, "carrier", "carrier/admission.json",
        "admission", admission)
    installation_source = _persist(effects, "carrier", "carrier/installation.json",
        "installation", installation)
    all_sources.extend((admission_source, installation_source))
    cases_index = []
    h01_execution = h01_package = None
    for case in CASES:
        now = _clock(effects, context["guest_deadlines"])
        deadlines = _case_deadlines(now, context["guest_deadlines"])
        effects._active_case_deadlines = dict(deadlines)
        intent = build_intent(case)
        prefix = "cases/" + case["case_id"] + "/"
        intent_source = _persist(effects, case["case_id"], prefix + "intent.json",
            "intent", intent)
        sources, verdict, summary, _owner_mono = _case_outcome(
            effects, case, intent, intent_source, deadlines)
        if hasattr(effects, 'accounting_boundary'):
            effects.accounting_boundary('CASE_BOUNDARY')
        _validate_source_set(case, sources, seal_id=summary.get("seal_id"))
        verdict_source = next(item for item in sources if item["role"] == "verdict")
        cases_index.append({"index": case["index"], "case_id": case["case_id"], "status": "PASS",
                "semantic_pass": True, "verdict_path": verdict_source["path"],
                "verdict_sha256": _sha(verdict_source["raw"])})
        if case["index"] == 1:
            _check.exact(summary, ("seal_id", "h01_business_execution", "h01_result_package"),
                'H01_SUMMARY_FIELDS')
            h01_execution = summary["h01_business_execution"]
            h01_package = summary["h01_result_package"]
        else:
            _check(summary == {"seal_id": None}, 'NON_H01_SUMMARY')
        all_sources.extend(sources)
    session = _session(context, admission, installation)
    session_source = _persist(effects, "carrier", "carrier/session.json", "session", session)
    all_sources.append(session_source)
    carrier_specs = {(item["path"], item["role"], item["mode"]) for item in all_sources
        if item["path"].startswith("carrier/")}
    _check(carrier_specs == {("carrier/session.json", "session", 384),
            ("carrier/admission.json", "admission", 384),
            ("carrier/installation.json", "installation", 384)},
        'CARRIER_SET')
    members = []
    raw_by_path = {}
    for source in all_sources:
        _source(source)
        _check(source["path"] not in raw_by_path, 'MEMBER_DUPLICATE')
        case_id = "carrier" if source["path"].startswith("carrier/") else source["path"].split("/")[1]
        members.append(_member(source, case_id)); raw_by_path[source["path"]] = source["raw"]
    members.sort(key=lambda row: row["path"].encode("ascii"))
    _check(len(members) == 3 + 32 + 21 + 26 and len(members) <= MEMBER_COUNT_LIMIT,
        'MEMBER_COUNT')
    effects._active_case_deadlines = None
    accounting = effects.resource_accounting()
    effects._resource_snapshot = copy.deepcopy(accounting)
    plans = [document(source['raw'], limit=MEMBER_LIMIT, newline=True) for source in all_sources if source['role'] == 'plan']
    preparations = [document(source['raw'], limit=MEMBER_LIMIT, newline=True) for source in all_sources
        if source['role'] == 'preparation-result' and '/reservation/' in source['path']]
    usage = effects.usage()
    missing = sorted({(row['code'], row['role'], row['detail_sha256']): row
        for row in accounting['missing'] + list(getattr(effects, '_usage_missing', ()))
        }.values(), key=lambda row: (row['code'], row['role'], row['detail_sha256']))
    _resource_missing(missing)
    complete = not missing
    _validate_resource_accounting(accounting, context, admission=admission, plans=plans,
        installation=installation, preparations=preparations, complete=complete)
    remote = {"schema": REMOTE_SCHEMA, "session_id": SESSION,
        "consumption_sha256": context["bind"]["consumption_sha256"],
        "state": "REMOTE_FINALIZED" if complete else "REMOTE_STOP_AND_RETAIN", "cases": cases_index,
        "h01_business_execution": h01_execution, "h01_result_package": h01_package,
        "usage": None, "resource_accounting": accounting, "missing": missing}
    manifest = {"schema": OUTPUT_SCHEMA, "session_id": SESSION, "remote_result": remote,
        "cases": cases_index, "members": members, "limits": OUTPUT_LIMITS}
    # Frame length participates in usage.  Iterate to the unique fixed point.
    for _ in range(4):
        remote["usage"] = _usage(usage, context, usage.get("output_frame_bytes", 0),
            accounting=accounting, missing=missing, complete=complete)
        raw_manifest = canonical(manifest, newline=True, limit=MANIFEST_LIMIT)
        frame = OUTPUT_MAGIC + struct.pack(">Q", len(raw_manifest)) + raw_manifest + b"".join(
            raw_by_path[item["path"]] for item in members)
        _check(len(frame) <= FRAME_LIMIT, 'FRAME_LIMIT')
        if usage["output_frame_bytes"] == len(frame):
            break
        usage = dict(usage, output_frame_bytes=len(frame))
    _check(usage["output_frame_bytes"] == len(frame), 'USAGE_FRAME')
    remote["usage"] = _usage(usage, context, len(frame), accounting=accounting,
        missing=missing, complete=complete)
    raw_manifest = canonical(manifest, newline=True, limit=MANIFEST_LIMIT)
    frame = OUTPUT_MAGIC + struct.pack(">Q", len(raw_manifest)) + raw_manifest + b"".join(
        raw_by_path[item["path"]] for item in members)
    _check(len(frame) == usage["output_frame_bytes"] and len(frame) <= FRAME_LIMIT,
        'FRAME_LIMIT')
    return frame


__all__ = [
    "DispatchError", "FieldEffects", "build_intent", "validate_plan", "required_paths",
    "phase_source_specs", "dispatch",
]
