"""Private supervised result collection and bounded, storage-free parent IPC.

Only ``run`` and its child-side helpers touch task storage. ``PipeReader`` is a
pure in-memory decoder; completion additionally requires the manager's original
reader invocation and its independent cgroup exit proof at the call site.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys

from . import bootstrap, bootstrap_roots, budget
from .contract import JobError, UUID_PATTERN

encode_payload = bootstrap.encode_payload
decode_payload = bootstrap.decode_payload

MAX_RESULT_BYTES = 1024 * 1024
MAX_FRAME_BYTES = MAX_RESULT_BYTES + 8192
MAX_READY_BYTES = 4096
MAX_TRANSPORT_BYTES = MAX_FRAME_BYTES + MAX_READY_BYTES + 8
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 250000
_PAYLOAD_KEYS = {"execution_id", "phase", "operation_id", "budget_grant", "budgets",
    "supervision_version", "bootstrap_allocation", "parent_mount_namespace",
    "phase_deadline_boottime_ns", "runtime_cap_us", "reader_unit", "unit",
    "helper_identity", "result_name"}
_IDENTITY_KEYS = {"unit", "boot_id", "invocation_id", "cgroup"}
_FRAME_KEYS = {"version", "type", "execution_id", "phase", "reader_identity", "helper_identity"}


def _invalid(message):
    return JobError("IO_UNCERTAIN", message)


def unit_name(execution_id):
    return "lhj-" + hashlib.sha256((execution_id + ":result_reader").encode()).hexdigest() + ".service"


def result_name(execution_id):
    return "result-" + hashlib.sha256(execution_id.encode()).hexdigest()[:24] + ".json"


def _identity(value, *, helper=False):
    keys = _IDENTITY_KEYS | ({"exit_code"} if helper else set())
    if type(value) is not dict or set(value) != keys:
        raise _invalid("Result collection invocation fields are incomplete")
    if (type(value["unit"]) is not str or re.fullmatch(r"lhj-[0-9a-f]{64}\.service", value["unit"]) is None
            or type(value["boot_id"]) is not str or re.fullmatch(UUID_PATTERN, value["boot_id"]) is None
            or type(value["invocation_id"]) is not str or re.fullmatch(r"[0-9a-f]{32}", value["invocation_id"]) is None
            or type(value["cgroup"]) is not str or not value["cgroup"].startswith("/")
            or str(Path(value["cgroup"])) != value["cgroup"] or ".." in Path(value["cgroup"]).parts
            or "\x00" in value["cgroup"] or len(value["cgroup"]) > 2048
            or Path(value["cgroup"]).name != value["unit"]):
        raise _invalid("Result collection invocation identity is invalid")
    if helper and value["exit_code"] is not None and (
            type(value["exit_code"]) is not int or not 0 <= value["exit_code"] < 2**31):
        raise _invalid("Original helper exit status is invalid")
    return copy.deepcopy(value)


def _json_data(value):
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise _invalid("Result JSON complexity exceeds its fixed bound")
        if type(item) is dict:
            pending.extend((child, depth + 1) for pair in item.items() for child in pair)
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            item.encode("utf-8", "strict")
        elif type(item) is float:
            if not math.isfinite(item):
                raise _invalid("Result JSON contains a non-finite number")
        elif item is not None and type(item) not in (bool, int):
            raise _invalid("Result JSON contains a non-JSON value")


def _strict_json(raw, maximum):
    if type(raw) is not bytes or len(raw) > maximum:
        raise _invalid("Result JSON exceeds its fixed byte bound")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("non-finite JSON constant")
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs, parse_constant=constant)
        _json_data(value)
        return value
    except (ValueError, UnicodeError, RecursionError) as error:
        raise _invalid("Result JSON is invalid") from error


def _result(value, execution_id, phase):
    if (type(value) is not dict or value.get("execution_id") != execution_id or value.get("phase") != phase
            or value.get("outcome") not in ("SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN")
            or type(value.get("effects_checked")) is not bool or type(value.get("facts")) is not dict):
        raise _invalid("Result identity or required fields differ from the original helper")
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False).encode("utf-8", "strict")
    if len(encoded) > MAX_RESULT_BYTES:
        raise _invalid("Result metadata exceeds its fixed byte bound")
    # Business-specific metadata is retained, including legal floating point
    # observations and prepared/seal records; it is not an executable plan.
    return value


def _frame_bytes(frame):
    try:
        _json_data(frame)
        raw = json.dumps(frame, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False).encode("utf-8", "strict")
    except (ValueError, UnicodeError, RecursionError) as error:
        raise _invalid("Result transport JSON is invalid") from error
    maximum = MAX_READY_BYTES if frame["type"] == "READY" else MAX_FRAME_BYTES
    if len(raw) > maximum:
        raise _invalid("Result transport frame exceeds its fixed bound")
    return struct.pack("!I", len(raw)) + raw


class PipeReader:
    """Exactly two length-prefixed frames, with no file access or wait calls.

    The manager feeds only bytes from its nonblocking pipe. A complete frame is
    not trusted until ``finish`` follows an independent unit exit observation.
    Extra bytes, truncation and every decoding error permanently poison it.
    """
    def __init__(self, execution_id, phase, reader_unit, helper_identity):
        if (type(execution_id) is not str or not 1 <= len(execution_id) <= 256
                or phase not in ("preflight", "business", "reconcile", "evidence")
                or reader_unit != unit_name(execution_id)):
            raise _invalid("Result transport execution identity is invalid")
        self.execution_id, self.phase, self.reader_unit = execution_id, phase, reader_unit
        self.helper_identity = _identity(helper_identity, helper=True)
        expected_helper = "lhj-" + hashlib.sha256(execution_id.encode()).hexdigest() + ".service"
        if self.helper_identity["unit"] != expected_helper:
            raise _invalid("Result transport belongs to another helper")
        self._buffer = bytearray()
        self._total = 0
        self._frames = 0
        self._failed = False
        self._finished = False
        self._reader_identity = None
        self._bound_identity = None
        self._candidate = None

    @property
    def ready(self):
        return self._frames >= 1 and not self._failed

    @property
    def complete(self):
        return self._frames == 2 and not self._failed and not self._buffer

    @property
    def result(self):
        return copy.deepcopy(self._candidate) if self._finished and not self._failed else None

    def _reject(self, message):
        self._failed = True
        self._candidate = None
        self._buffer.clear()
        raise _invalid(message)

    def bind_reader(self, identity):
        try:
            bound = _identity({"unit": self.reader_unit, **identity})
        except (JobError, TypeError):
            self._reject("Observed result reader identity is invalid")
        if (bound["unit"] != self.reader_unit or bound["boot_id"] != self.helper_identity["boot_id"]
                or self._bound_identity not in (None, bound) or self._reader_identity not in (None, bound)):
            self._reject("Observed result reader invocation differs from the result transport")
        if self._failed:
            self._reject("Result transport was already rejected")
        self._bound_identity = bound

    def feed(self, data):
        if self._failed or self._finished or type(data) is not bytes:
            self._reject("Result transport received invalid or late bytes")
        if self._total + len(data) > MAX_TRANSPORT_BYTES:
            self._reject("Result transport exceeds its total byte bound")
        self._total += len(data)
        self._buffer.extend(data)
        try:
            while self._buffer:
                if self._frames == 2:
                    self._reject("Result transport contains an extra frame or trailing bytes")
                if len(self._buffer) < 4:
                    return
                size = struct.unpack("!I", self._buffer[:4])[0]
                maximum = MAX_READY_BYTES if self._frames == 0 else MAX_FRAME_BYTES
                if not 0 < size <= maximum:
                    self._reject("Result transport frame length is invalid")
                if len(self._buffer) < size + 4:
                    return
                raw = bytes(self._buffer[4:size + 4])
                del self._buffer[:size + 4]
                frame = _strict_json(raw, maximum)
                expected_type = "READY" if self._frames == 0 else "RESULT"
                keys = _FRAME_KEYS | ({"result"} if self._frames == 1 else set())
                if (type(frame) is not dict or set(frame) != keys or type(frame["version"]) is not int
                        or frame["version"] != 1 or frame["type"] != expected_type
                        or frame["execution_id"] != self.execution_id or frame["phase"] != self.phase
                        or _identity(frame["helper_identity"], helper=True) != self.helper_identity):
                    self._reject("Result transport frame identity, fields or order differs")
                identity = _identity(frame["reader_identity"])
                if (identity["unit"] != self.reader_unit or identity["boot_id"] != self.helper_identity["boot_id"]
                        or self._reader_identity not in (None, identity) or self._bound_identity not in (None, identity)):
                    self._reject("Result transport reader invocation differs")
                self._reader_identity = identity
                if self._frames == 1:
                    self._candidate = _result(frame["result"], self.execution_id, self.phase)
                self._frames += 1
        except (JobError, ValueError, TypeError, KeyError, RecursionError) as error:
            self._reject("Result transport was rejected: " + type(error).__name__)

    def finish(self):
        if not self.complete or self._bound_identity is None or self._bound_identity != self._reader_identity:
            self._reject("Result transport is incomplete or its original reader is unverified")
        self._finished = True


def _validate_payload(payload):
    if (type(payload) is not dict or set(payload) != _PAYLOAD_KEYS
            or type(payload["supervision_version"]) is not int or payload["supervision_version"] != 3):
        raise _invalid("Result reader requires its fixed version-three private payload")
    # Reuse the bounded canonical launch transport validation, not the public
    # request contract (helper result metadata has a different private bound).
    bootstrap.encode_payload(payload)
    grant = payload["budget_grant"]
    budget.validate_grant(grant, execution_id=payload["execution_id"],
        phase=payload["phase"], operation_id=payload["operation_id"], budgets=payload["budgets"])
    allocation = bootstrap_roots.validate_grant(payload["bootstrap_allocation"],
        execution_id=payload["execution_id"], phase=payload["phase"], operation_id=payload["operation_id"],
        namespace=grant["namespace"], record_id=grant["record_id"])
    helper = _identity(payload["helper_identity"], helper=True)
    expected_helper = "lhj-" + hashlib.sha256(payload["execution_id"].encode()).hexdigest() + ".service"
    expected_reader = unit_name(payload["execution_id"])
    fixed_deadline = budget.phase_deadline_ns(grant) - grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS
    if (helper["unit"] != expected_helper or helper["boot_id"] != grant["boot_id"]
            or payload["reader_unit"] != expected_reader or payload["unit"] != expected_reader
            or payload["result_name"] != result_name(payload["execution_id"])
            or type(payload["parent_mount_namespace"]) is not str or not payload["parent_mount_namespace"]
            or type(payload["phase_deadline_boottime_ns"]) is not int
            or payload["phase_deadline_boottime_ns"] != fixed_deadline
            or type(payload["runtime_cap_us"]) is not int or payload["runtime_cap_us"] <= 0
            or payload["runtime_cap_us"] * 1000 > fixed_deadline - grant["reserved_boottime_ns"]):
        raise _invalid("Result reader does not match its original helper, roots or deadline")
    return grant, allocation


def _file_state(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_result(payload, allocation, deadline):
    """Child only: one bound root descriptor and one fixed openat filename."""
    from . import runner
    root = allocation["roots"]["evidence"]
    parent = bootstrap._root_descriptor(root, allocation["paths"][root])
    descriptor = None
    try:
        root_before = _file_state(os.fstat(parent))
        if _file_state(os.stat(root, follow_symlinks=False)) != root_before:
            raise _invalid("Result evidence root changed before collection")
        runner._deadline_remaining(deadline)
        descriptor = os.open(payload["result_name"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        before = os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_uid != os.geteuid()
                or before.st_mode & 0o022 or before.st_size > MAX_RESULT_BYTES
                or _file_state(os.stat(payload["result_name"], dir_fd=parent, follow_symlinks=False)) != _file_state(before)):
            raise _invalid("Result is not a single bounded original regular file")
        chunks, seen = [], 0
        while True:
            runner._deadline_remaining(deadline)
            chunk = os.read(descriptor, min(65536, MAX_RESULT_BYTES + 1 - seen))
            if not chunk:
                break
            seen += len(chunk)
            if seen > MAX_RESULT_BYTES:
                raise _invalid("Result file exceeds its fixed byte bound")
            chunks.append(chunk)
        if (seen != before.st_size or _file_state(os.fstat(descriptor)) != _file_state(before)
                or _file_state(os.stat(payload["result_name"], dir_fd=parent, follow_symlinks=False)) != _file_state(before)
                or _file_state(os.fstat(parent)) != root_before
                or _file_state(os.stat(root, follow_symlinks=False)) != root_before
                or str(Path(root).resolve()) != root):
            raise _invalid("Result file or evidence root changed during collection")
        runner._deadline_remaining(deadline)
        return _result(_strict_json(b"".join(chunks), MAX_RESULT_BYTES), payload["execution_id"], payload["phase"])
    finally:
        bootstrap._close_all(([descriptor] if descriptor is not None else []) + [parent], sys.exc_info()[1])


def _emit(frame):
    raw = _frame_bytes(frame)
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def run(payload):
    """Fixed child entry point; no free command, path, grant or retry interface."""
    from . import runner
    grant, allocation = _validate_payload(payload)
    now = budget.current_clock()
    deadline = (grant, min(payload["phase_deadline_boottime_ns"],
                          now["boottime_ns"] + payload["runtime_cap_us"] * 1000))
    runner._deadline_remaining(deadline)
    if (os.readlink("/proc/self/ns/mnt") == payload["parent_mount_namespace"]
            or "ro" not in runner._mount_for("/")["options"].split(",")
            or any(os.access(path, os.W_OK) for path in ("/tmp", "/var/tmp", "/dev/shm"))):
        raise _invalid("Result reader filesystem namespace is not isolated")
    observed = runner._verify_cgroup_limits(dict(payload,
        budgets=budget.substage_limits(grant, "result_reader", supervision_version=3)))
    identity = _identity({"unit": payload["unit"], "boot_id": now["boot_id"],
        "invocation_id": os.environ.get("INVOCATION_ID"), "cgroup": observed["cgroup"]})
    frame = {"version": 1, "type": "READY", "execution_id": payload["execution_id"],
        "phase": payload["phase"], "reader_identity": identity, "helper_identity": payload["helper_identity"]}
    _emit(frame)
    result = _read_result(payload, allocation, deadline)
    runner._deadline_remaining(deadline)
    _emit({**frame, "type": "RESULT", "result": result})
    runner._deadline_remaining(deadline)
    return 0
