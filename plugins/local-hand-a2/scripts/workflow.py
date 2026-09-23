"""Client-only workflow: pinned admission, durable identities and bounded calls.

The host injects an authenticated, request-time-bounded callback. This module
does not create a connection, load tokens, spawn a process or execute a job.
Its journal belongs to the private client workspace, never the public package.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Callable
import uuid

from local_hand_jobs.contract import (
    JobError, SCHEMA_VERSION, TOOL_SCHEMA_DIGEST, canonical_bytes,
    request_digest, strict_loads, validate_submit, validate_tool_args,
)
from local_hand_jobs.evidence import EvidenceError, _close_descriptors, _publish_create_only


def _copy(value):
    return json.loads(canonical_bytes(value))


def _fail(code, message):
    raise JobError(code, message)


class Workflow:
    """Use one immutable private admission and a host-owned authenticated API."""

    def __init__(self, call: Callable, journal: Path, admission: dict, *,
                 clock=time.monotonic, sleep=time.sleep, wall_clock=time.time):
        self.call = call
        self.clock, self.sleep, self.wall_clock = clock, sleep, wall_clock
        self.contract = json.loads((Path(__file__).resolve().parents[1] / "contract.json").read_text())
        self.admission = _copy(admission)
        if set(self.admission) != {"authority_id", "profiles"} or not isinstance(self.admission["authority_id"], str) or not self.admission["authority_id"]:
            _fail("UNAUTHORIZED", "Private admission is incomplete")
        if not isinstance(self.admission["profiles"], dict) or not self.admission["profiles"]:
            _fail("UNAUTHORIZED", "No privately admitted target")
        for profile, expected in self.admission["profiles"].items():
            request_digest({"schema_version": SCHEMA_VERSION, "operation_id": str(uuid.uuid4()),
                            "kind": "host.inspect", "profile_ref": profile, "expected": expected,
                            "inputs": {}, "expires_at": 0})
        self.journal = Path(journal).absolute()
        if self.journal.parent.resolve() != self.journal.parent:
            _fail("UNAUTHORIZED", "Client journal ancestors must not be linked")
        parent = directory = None
        failure = None
        try:
            parent = os.open(self.journal.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            parent_info = os.fstat(parent)
            self._journal_parent_identity = (parent_info.st_dev, parent_info.st_ino)
            self._check_journal_parent(parent)
            try:
                # Creation stays bound to this parent even if its name is
                # replaced. Never follow a new path before detecting the race.
                os.mkdir(self.journal.name, mode=0o700, dir_fd=parent)
            except FileExistsError:
                pass
            directory = os.open(self.journal.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            st = os.fstat(directory)
            if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
                _fail("UNAUTHORIZED", "Client journal must be a private owned directory")
            self._journal_identity = (st.st_dev, st.st_ino)
            self._check_journal_parent(parent)
            self._check_journal(directory)
        except (OSError, RuntimeError) as error:
            failure = error
            _fail("IO_UNCERTAIN", "Client journal creation or identity is unresolved")
        except BaseException as error:
            failure = error
            raise
        finally:
            _close_descriptors(directory, parent, failure=failure)
        self._profiles = {}
        self._execution_support = {}

    @property
    def execution_support(self):
        return _copy(self._execution_support)

    def _require_supported(self, kind):
        status = self._execution_support.get(kind, {}).get("status")
        if status in ("UNSUPPORTED", "BLOCKED"):
            _fail("UNSUPPORTED", "The backend reports this execution kind is not available")

    def _invoke(self, tool, arguments):
        validate_tool_args(tool, arguments)
        result = self.call(tool, _copy(arguments))
        if not isinstance(result, dict):
            _fail("IO_UNCERTAIN", "Host callback did not return a structured tool result")
        if len(canonical_bytes(result)) > self.contract["client_limits"]["max_response_bytes"]:
            _fail("LIMIT_EXCEEDED", "Tool response exceeds client budget")
        if result.get("ok") is False or "error" in result:
            error = result.get("error", {})
            _fail(error.get("code", "IO_UNCERTAIN"), "The authenticated tool returned an error")
        return _copy(result)

    def _record_name(self, kind, key):
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", key):
            _fail("INVALID_REQUEST", "Use an explicit bounded client intent key")
        return kind + "-" + hashlib.sha256(key.encode("ascii")).hexdigest() + ".json"

    def _invoke_bound(self, tool, arguments, digest, reconcile_id=None):
        result = self._invoke(tool, arguments)
        if "operation_id" not in result or "request_digest" not in result or (
                reconcile_id is not None and "reconcile_id" not in result):
            _fail("IO_UNCERTAIN", "Tool receipt omitted the original identity binding")
        if (result["operation_id"] != arguments["operation_id"] or result["request_digest"] != digest
                or result.get("reconcile_id") != reconcile_id):
            _fail("CONFLICT", "Tool receipt belongs to a different job or reconciliation")
        return result

    def _check_journal(self, directory):
        opened, named = os.fstat(directory), self.journal.lstat()
        if (self.journal.parent.resolve() != self.journal.parent
                or any(not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid()
                       or st.st_mode & 0o077 or (st.st_dev, st.st_ino) != self._journal_identity
                       for st in (opened, named))):
            _fail("IO_UNCERTAIN", "Client journal directory identity changed")

    def _check_journal_parent(self, parent):
        if (self.journal.parent.resolve() != self.journal.parent
                or any(not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) != self._journal_parent_identity
                       for st in (os.fstat(parent), self.journal.parent.lstat()))):
            _fail("IO_UNCERTAIN", "Client journal parent identity changed")

    @contextmanager
    def _journal_directory(self):
        directory = parent = None
        body_failed = False
        try:
            parent = os.open(self.journal.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self._check_journal_parent(parent)
            directory = os.open(self.journal.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            self._check_journal(directory)
            yield directory, parent
            self._check_journal_parent(parent)
            self._check_journal(directory)
        except EvidenceError as error:
            body_failed = True
            _fail(error.code, "Client identity publication is unavailable")
        except (OSError, RuntimeError):
            body_failed = True
            _fail("IO_UNCERTAIN", "Client journal identity or durability is unresolved")
        except BaseException:
            body_failed = True
            raise
        finally:
            close_failed = False
            for descriptor in (directory, parent):
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        # The failing close may already have released its FD.
                        # Do not retry it, but still release the other directory.
                        close_failed = True
            if close_failed and not body_failed:
                _fail("IO_UNCERTAIN", "Client journal directory close is unresolved")

    def _read(self, name, expected_identity=None):
        with self._journal_directory() as (directory, parent):
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            except FileNotFoundError:
                if expected_identity is not None:
                    _fail("IO_UNCERTAIN", "Published client identity disappeared")
                return None
            try:
                stream = os.fdopen(fd, "rb")
            except BaseException:
                # A failed wrapper has not taken ownership of the raw FD.
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise
            with stream:
                st = os.fstat(stream.fileno())
                if expected_identity is not None and (st.st_dev, st.st_ino) != expected_identity:
                    _fail("IO_UNCERTAIN", "Published client identity was replaced")
                maximum = self.contract["client_limits"]["max_record_bytes"]
                if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1 or st.st_mode & 0o077 or st.st_size > maximum:
                    _fail("IO_UNCERTAIN", "Client identity has invalid ownership or type")
                try:
                    raw = stream.read(maximum + 1)
                    if len(raw) > maximum:
                        _fail("IO_UNCERTAIN", "Client identity exceeds its read budget")
                    record = strict_loads(raw)
                except (JobError, ValueError, UnicodeError):
                    _fail("IO_UNCERTAIN", "Client identity is incomplete")
                # Retrying a prior uncertain publish must reestablish durability
                # for the same named file and directory, not a replacement.
                os.fsync(stream.fileno())
                os.fsync(directory)
                # The journal can have just been created, or an earlier parent
                # commit can have failed. Keep this verified file open through
                # every durability barrier before checking its final identity.
                os.fsync(parent)
                identity = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_nlink,
                                          item.st_size, item.st_mtime_ns, item.st_ctime_ns)
                if any(identity(item) != identity(st) for item in
                       (os.fstat(stream.fileno()), os.stat(name, dir_fd=directory, follow_symlinks=False))):
                    _fail("IO_UNCERTAIN", "Client identity changed while being read")
        if not isinstance(record, dict) or record.get("authority_id") != self.admission["authority_id"]:
            _fail("CONFLICT", "Client identity belongs to a different authority")
        return record

    def _save(self, name, record):
        """Create-only publish; no network call is possible before this returns."""
        raw = canonical_bytes(record)
        if len(raw) > self.contract["client_limits"]["max_record_bytes"]:
            _fail("LIMIT_EXCEEDED", "Client identity exceeds local record budget")
        staging = Path(".pending-" + str(uuid.uuid4()))
        expected_identity = None
        with self._journal_directory() as (directory, parent):
            fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            try:
                stream = os.fdopen(fd, "wb")
            except BaseException:
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise
            with stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
                created = os.fstat(stream.fileno())
            try:
                _publish_create_only(staging, Path(name), source_dir_fd=directory, destination_dir_fd=directory)
            except FileExistsError:
                pass  # Preserve staging residue; never unlink a possibly replaced entry.
            else:
                expected_identity = (created.st_dev, created.st_ino)
                published = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if (published.st_dev, published.st_ino) != (created.st_dev, created.st_ino):
                    _fail("IO_UNCERTAIN", "Client identity changed during publication")
            os.fsync(directory)
            os.fsync(parent)
        saved = self._read(name, expected_identity=expected_identity)
        if saved is None or (expected_identity is not None and saved != record):
            _fail("IO_UNCERTAIN", "Published client identity content changed")
        return saved

    def preflight(self):
        self._profiles = {}
        self._execution_support = {}
        if (self.contract["job_schema_version"] != SCHEMA_VERSION or
                self.contract["tool_schema_digest"] != TOOL_SCHEMA_DIGEST or
                hashlib.sha256(canonical_bytes(self.contract["tools"])).hexdigest() != TOOL_SCHEMA_DIGEST):
            _fail("UNSUPPORTED", "Plugin and installed client contracts differ")
        profiles, cursor, seen, version, support = {}, None, set(), None, None
        for _ in range(self.contract["client_limits"]["max_discovery_pages"]):
            page = self._invoke("lh_capabilities", {} if cursor is None else {"cursor": cursor})
            if page.get("schema_version") != SCHEMA_VERSION or page.get("tool_schema_digest") != TOOL_SCHEMA_DIGEST:
                _fail("UNSUPPORTED", "Backend and plugin tool contracts differ")
            if page.get("authority_id") != self.admission["authority_id"]:
                _fail("STALE_DEPLOYMENT", "Discovered authority does not match private admission")
            current = page.get("catalog_version")
            if not isinstance(current, str) or not current or (version is not None and current != version):
                _fail("STALE_DEPLOYMENT", "Capability pages do not share one catalog version")
            version = current
            announced = page.get("execution_support", {})
            if (not isinstance(announced, dict) or any(not isinstance(item, dict) for item in announced.values())
                    or (support is not None and support != announced)):
                _fail("IO_UNCERTAIN", "Execution support changed within the capability catalog")
            support = announced
            entries = page.get("profiles")
            if not isinstance(entries, list) or len(entries) > 100:
                _fail("IO_UNCERTAIN", "Malformed capability catalog")
            for profile in entries:
                if not isinstance(profile, dict):
                    _fail("IO_UNCERTAIN", "Malformed profile in capability catalog")
                ref = profile.get("profile_ref")
                if ref not in self.admission["profiles"]:
                    continue  # Visible alternatives are not privately admitted targets.
                if profile.get("expected") != self.admission["profiles"][ref]:
                    _fail("STALE_DEPLOYMENT", "Discovered deployment does not match private admission")
                if ref in profiles:
                    _fail("IO_UNCERTAIN", "Duplicate profile in capability catalog")
                profiles[ref] = profile
            cursor = page.get("next_cursor")
            if cursor is None:
                self._profiles = profiles
                self._execution_support = support
                return _copy(profiles)
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                _fail("IO_UNCERTAIN", "Capability pagination did not progress")
            seen.add(cursor)
        _fail("LIMIT_EXCEEDED", "Capability pagination exceeded the bounded observation")

    def reserve_job(self, key, *, kind, profile_ref, inputs, lifetime_seconds=300):
        name = self._record_name("job", key)
        old = self._read(name)
        if old is not None:
            original = old.get("request", {})
            validate_submit(original)
            if (original["kind"], original["profile_ref"], original["inputs"]) != (kind, profile_ref, inputs):
                _fail("CONFLICT", "Client intent key already names a different job")
            return old
        profile = self._profiles.get(profile_ref)
        if profile is None or kind not in profile.get("allowed_kinds", []):
            _fail("UNAUTHORIZED", "Preflight has not admitted this target and job kind")
        self._require_supported(kind)
        if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= 3600:
            _fail("INVALID_REQUEST", "Client submission lifetime must be finite")
        for field, directory in (("source_ref", "source_refs"), ("build_cache_ref", "build_cache_refs"),
                                 ("storage_ref", "storage_refs"), ("prepared_ref", "prepared_refs")):
            if field in inputs and inputs[field] not in profile.get(directory, []):
                _fail("UNAUTHORIZED", "Logical input is absent from the admitted catalog")
        request = {"schema_version": SCHEMA_VERSION, "operation_id": str(uuid.uuid4()), "kind": kind,
                   "profile_ref": profile_ref, "expected": _copy(self.admission["profiles"][profile_ref]),
                   "inputs": _copy(inputs), "expires_at": int(self.wall_clock()) + lifetime_seconds}
        request["request_digest"] = request_digest(request)
        record = {"authority_id": self.admission["authority_id"], "request": request}
        saved = self._save(name, record)
        if saved != record:
            original = saved.get("request", {})
            validate_submit(original)
            if (original["kind"], original["profile_ref"], original["inputs"], original["expected"]) != (kind, profile_ref, inputs, request["expected"]):
                _fail("CONFLICT", "Concurrent client intent differs")
        return saved

    def submit(self, key):
        record = self._job(key)
        request = record["request"]
        profile = self._profiles.get(request["profile_ref"])
        if profile is None or profile.get("expected") != request["expected"]:
            _fail("STALE_DEPLOYMENT", "Do not rebind a saved request before submission")
        if request["kind"] not in profile.get("allowed_kinds", []):
            _fail("UNAUTHORIZED", "The discovered grant does not allow this job")
        self._require_supported(request["kind"])
        return self._invoke_bound("lh_job_submit", request, request["request_digest"])

    def _job(self, key):
        record = self._read(self._record_name("job", key))
        if record is None:
            _fail("NOT_FOUND", "No durable client identity exists")
        validate_submit(record.get("request"))
        return record

    def reserve_reconcile(self, key, job_key):
        request = self._job(job_key)["request"]
        name = self._record_name("reconcile", key)
        record = self._read(name)
        arguments = {"operation_id": request["operation_id"],
                     "expected_request_digest": request["request_digest"]}
        if record is None:
            record = self._save(name, {"authority_id": self.admission["authority_id"],
                                     "arguments": {**arguments, "reconcile_id": str(uuid.uuid4())}})
        actual = record.get("arguments", {})
        validate_tool_args("lh_job_reconcile", actual)
        if any(actual.get(k) != v for k, v in arguments.items()):
            _fail("CONFLICT", "Reconciliation identity belongs to another original job")
        return record

    def _reconcile(self, key):
        record = self._read(self._record_name("reconcile", key))
        if record is None:
            _fail("NOT_FOUND", "No durable reconciliation identity exists")
        validate_tool_args("lh_job_reconcile", record.get("arguments"))
        return record["arguments"]

    def reconcile(self, key):
        args = self._reconcile(key)
        return self._invoke_bound("lh_job_reconcile", args, args["expected_request_digest"], args["reconcile_id"])

    def cancel_job(self, key):
        request = self._job(key)["request"]
        return self._invoke_bound("lh_job_cancel", {"operation_id": request["operation_id"],
                            "expected_request_digest": request["request_digest"], "target": {"kind": "job"}},
                            request["request_digest"])

    def cancel_reconcile(self, key):
        args = self._reconcile(key)
        return self._invoke_bound("lh_job_cancel", {"operation_id": args["operation_id"],
                            "expected_request_digest": args["expected_request_digest"],
                            "target": {"kind": "reconcile", "reconcile_id": args["reconcile_id"]}},
                            args["expected_request_digest"], args["reconcile_id"])

    def observe(self, *, job_key=None, reconcile_key=None):
        if (job_key is None) == (reconcile_key is None):
            _fail("INVALID_REQUEST", "Select one exact job or reconciliation identity")
        if job_key is not None:
            request = self._job(job_key)["request"]
            args = {"operation_id": request["operation_id"]}
            digest = request["request_digest"]
        else:
            saved = self._reconcile(reconcile_key)
            args = {key: saved[key] for key in ("operation_id", "reconcile_id")}
            digest = saved["expected_request_digest"]
        limits = self.contract["client_limits"]
        started, latest = self.clock(), None
        for index in range(limits["max_poll_calls"]):
            if self.clock() - started >= limits["max_observe_seconds"]:
                break
            latest = self._invoke_bound("lh_job_status", args, digest, args.get("reconcile_id"))
            if latest.get("lifecycle") in ("TERMINAL", "RECONCILE_REQUIRED"):
                break
            remaining = limits["max_observe_seconds"] - (self.clock() - started)
            if index + 1 < limits["max_poll_calls"] and remaining > 0:
                self.sleep(min(limits["poll_interval_seconds"], remaining))
        return {"target": args, "latest": latest, "observation_complete": bool(latest and latest.get("lifecycle") == "TERMINAL")}

    def prepared_reference(self, status):
        if status.get("outcome") != "SUCCEEDED" or status.get("evidence") != "SEALED":
            _fail("NOT_SEALED", "Prepared output is not successful and sealed")
        outputs = status.get("outputs", {})
        if not isinstance(outputs, dict) or outputs.get("schema_version") != "lh-prepared-output-v1":
            _fail("UNSUPPORTED", "Prepared output contract is unsupported")
        if outputs.get("source_commit") != self.contract["ledger_source_commit"]:
            _fail("CONFLICT", "Prepared source does not match the frozen Ledger input")
        origin = outputs.get("source_operation_id")
        if (not isinstance(origin, str) or not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", origin)
                or origin != status.get("operation_id")):
            _fail("CONFLICT", "Prepared output does not belong to the queried job")
        bindings = outputs.get("bindings", {})
        required = {"source_digest", "wheel_digest", "installed_payload_digest", "runtime_digest", "environment_fingerprint"}
        if (not isinstance(bindings, dict) or set(bindings) != required or
                any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for v in bindings.values())):
            _fail("IO_UNCERTAIN", "Prepared identity bindings are incomplete")
        seal = outputs.get("seal_ref")
        if not isinstance(seal, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", seal):
            _fail("IO_UNCERTAIN", "Prepared output has no valid seal reference")
        ref = outputs.get("prepared_ref")
        if not isinstance(ref, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", ref):
            _fail("IO_UNCERTAIN", "Sealed prepared output did not provide a valid reference")
        return ref
