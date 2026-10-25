"""Fixed administrator-only verification of existing client read routes.

The Unix transport authenticates root and a guarded runtime before calling
this module. No request in this protocol can prepare, execute, cancel or write.
User authorization/ownership still runs; private probes have a separate finite
transport budget instead of consuming a user's interactive rate allowance.
"""
from contextvars import ContextVar
from contextlib import contextmanager, nullcontext
import base64
import hashlib
import os
from pathlib import Path
import time

from .contract import JobError, Principal, canonical_bytes, validate_tool_args
from .task_session import read_descriptor

MAX_TASKS = 128
MAX_BYTES = 256 * 1024 * 1024
_verification = ContextVar("local_hand_retained_verification", default=False)


def private_verification():
    return _verification.get()


@contextmanager
def owned_readers():
    """Close every temporary reader without replacing an earlier read error."""
    from . import cli
    readers, failed = [], False
    try:
        def temporary(factory):
            reader = factory()
            readers.append(reader)
            return reader
        yield temporary
    except BaseException:
        failed = True
        raise
    finally:
        failure = None
        for reader in reversed(readers):
            try:
                cli.close_service(reader, None, failed=failed)
            except BaseException as error:
                if failure is None:
                    failure = error
        if failure is not None:
            raise failure


def index(broker):
    with getattr(broker, "fence", nullcontext()), owned_readers() as temporary:
        return _index(broker, temporary)


def _index(broker, temporary):
    readers = [getattr(broker, "retained", broker)]
    readers.extend(getattr(broker, "verification_readers", ()))
    config = getattr(broker, "config", {})
    paths = list(config.get("retained", []))
    if len(paths) > MAX_TASKS:
        raise JobError("LIMIT_EXCEEDED", "Retained policy index exceeds its fixed bound")
    if "catalog" in config:
        with os.scandir(config["catalog"]) as entries:
            count = 0
            for entry in entries:
                count += 1
                if count > MAX_TASKS * 4:
                    raise JobError("LIMIT_EXCEEDED", "Retained catalog scan exceeds its fixed bound")
                if entry.name.endswith(".json"):
                    record = read_descriptor(str(Path(config["catalog"]) / entry.name))
                    if not isinstance(record.get("operation_id"), str) or record["operation_id"] + ".json" != entry.name:
                        raise JobError("CONFLICT", "Retained catalog identity changed")
                    if record.get("state") == "READY":
                        paths.append(record["policy_path"])
                        if len(paths) > MAX_TASKS * 2:
                            raise JobError("LIMIT_EXCEEDED", "Retained policies exceed their fixed bound")
        for path in dict.fromkeys(paths):
            if path == getattr(broker.retained, "retained_policy_path", None):
                continue  # The anchor already owns this ledger lock.
            reader = broker.readers.get(path)
            # Never retain a new reader's authority lock merely to inventory
            # an unused READY. That would block its later first execution.
            readers.append(reader if reader is not None else temporary(lambda: broker.reader_factory(path)))
    elif hasattr(broker, "reader_factory"):
        # Fixed prepared adapter, whose reader opens no execution manager.
        readers.append(broker.reader if broker.reader is not None else temporary(broker.reader_factory))
    found = {}
    for reader in readers:
        if not getattr(reader, "read_only", False):
            raise JobError("UNSUPPORTED", "Deployment inventory requires retained read-only ledgers")
        with reader.state.transaction() as tx:
            rows = tx.execute("SELECT id,principal,digest FROM operations WHERE namespace='job' ORDER BY id LIMIT ?",
                              (MAX_TASKS + 1,)).fetchall()
        if len(rows) > MAX_TASKS:
            raise JobError("LIMIT_EXCEEDED", "Retained ledger exceeds its fixed task bound")
        for operation, principal, request_digest in rows:
            key = {"operation_id": operation, "principal_id": principal, "request_digest": request_digest}
            route = (reader.policy.broker_root, key)
            if operation in found and found[operation] != route:
                raise JobError("CONFLICT", "Retained task identity has conflicting ledger routes")
            found[operation] = route
            if len(found) > MAX_TASKS:
                raise JobError("LIMIT_EXCEEDED", "Combined retained task index exceeds its fixed bound")
    return [found[key][1] for key in sorted(found)]


def handle(broker, request):
    if request == {"action": "deployment_retention_index"}:
        return {"tasks": index(broker)}
    if (not isinstance(request, dict) or set(request) != {"action", "tool", "arguments", "principal_id"}
            or request["action"] != "deployment_retention_read"
            or request["tool"] not in {"lh_job_status", "lh_evidence_manifest", "lh_evidence_read_chunk"}
            or not isinstance(request["principal_id"], str)):
        raise JobError("UNAUTHORIZED", "Deployment verifier only reads original task status and sealed evidence")
    args = validate_tool_args(request["tool"], request["arguments"])
    principal = Principal(request["principal_id"], frozenset({"lh:read", "lh:evidence"}))
    token = _verification.set(True)
    try:
        # This is the actual adapter route, including entry revocation, task
        # ownership, retained reader selection and digest-checked evidence IO.
        return broker.call(request["tool"], args, principal)
    finally:
        _verification.reset(token)


def merge_readbacks(snapshots):
    """Compare original results, independently of which service exposes them."""
    found = {}
    for snapshot in snapshots:
        if snapshot.get("schema") != "local-hand-retained-readback/v1":
            raise JobError("CONFLICT", "Unsupported retained readback format")
        for task in snapshot["tasks"]:
            operation = task["operation_id"]
            if operation in found and found[operation] != task:
                raise JobError("CONFLICT", "Selected read routes disagree on an original task")
            found[operation] = task
            if len(found) > MAX_TASKS:
                raise JobError("LIMIT_EXCEEDED", "Combined retained routes exceed their task budget")
    tasks = [found[key] for key in sorted(found)]
    total = sum(item["size"] for task in tasks for item in task["artifacts"])
    if total > MAX_BYTES:
        raise JobError("LIMIT_EXCEEDED", "Combined retained routes exceed their byte budget")
    return {"schema": "local-hand-retained-readback/v1", "tasks": tasks, "bytes_verified": total}


def collect(call, *, deadline, maximum_bytes=MAX_BYTES):
    try:
        return _collect(call, deadline=deadline, maximum_bytes=maximum_bytes)
    except (KeyError, TypeError, ValueError) as error:
        raise JobError("CONFLICT", "Retained read route returned malformed verification data") from error


def _collect(call, *, deadline, maximum_bytes):
    """Read back every sealed byte through the selected read API, with bounds."""
    def request(value):
        if time.monotonic() >= deadline:
            raise JobError("LIMIT_EXCEEDED", "Retained verification exhausted its time budget")
        result = call(value)
        if time.monotonic() >= deadline:
            raise JobError("LIMIT_EXCEEDED", "Retained response exceeded its verification deadline")
        return result

    def fingerprint(value):
        return hashlib.sha256(canonical_bytes(value)).hexdigest()

    tasks = request({"action": "deployment_retention_index"})["tasks"]
    if not isinstance(tasks, list) or len(tasks) > MAX_TASKS:
        raise JobError("LIMIT_EXCEEDED", "Retained task index exceeds its fixed bound")
    result, total, artifact_count = [], 0, 0
    seen = set()
    for task in tasks:
        if (not isinstance(task, dict) or set(task) != {"operation_id", "principal_id", "request_digest"}
                or task["operation_id"] in seen):
            raise JobError("CONFLICT", "Retained task index is ambiguous")
        seen.add(task["operation_id"])
        def read(tool, arguments):
            return request({"action": "deployment_retention_read", "tool": tool,
                            "principal_id": task["principal_id"], "arguments": arguments})
        status_args = {"operation_id": task["operation_id"]}
        status = read("lh_job_status", status_args)
        if any(status.get(key) != task[key] for key in ("operation_id", "request_digest")):
            raise JobError("CONFLICT", "Client route did not return the original request")
        artifacts, cursor, cursors, catalog = [], None, set(), None
        while True:
            try:
                page = read("lh_evidence_manifest", {**status_args, **({"cursor": cursor} if cursor else {})})
            except JobError as error:
                if error.code != "NOT_SEALED" or cursor is not None or status.get("seal_refs") or status.get("evidence") == "SEALED":
                    raise
                break
            if page.get("operation_id") != task["operation_id"] or (catalog is not None and catalog != page.get("catalog_digest")):
                raise JobError("CONFLICT", "Retained artifact catalog changed during pagination")
            catalog = page["catalog_digest"]
            for item in page["artifacts"]:
                artifact_count += 1
                if (artifact_count > 1024 or type(item.get("size")) is not int or item["size"] < 0
                        or item["size"] > maximum_bytes - total):
                    raise JobError("LIMIT_EXCEEDED", "Retained artifact budget exceeded before reading bytes")
                total += item["size"]
                artifacts.append(item)
            cursor = page["next_cursor"]
            if cursor is None:
                break
            if cursor in cursors or len(cursors) >= 16:
                raise JobError("CONFLICT", "Retained pagination failed to advance")
            cursors.add(cursor)
        for artifact in artifacts:
            sha, offset = hashlib.sha256(), 0
            while True:
                chunk = read("lh_evidence_read_chunk", {"artifact_id": artifact["artifact_id"],
                    "expected_sha256": artifact["sha256"], "offset": offset, "length": 256 * 1024})
                try:
                    raw = base64.b64decode(chunk["data_base64"], validate=True)
                except (ValueError, KeyError, TypeError) as error:
                    raise JobError("CONFLICT", "Retained evidence chunk is malformed") from error
                if (chunk.get("artifact_id") != artifact["artifact_id"] or chunk.get("offset") != offset
                        or chunk.get("length") != len(raw) or len(raw) > 256 * 1024
                        or chunk.get("total_size") != artifact["size"] or chunk.get("sha256") != artifact["sha256"]
                        or chunk.get("chunk_sha256") != hashlib.sha256(raw).hexdigest()
                        or offset + len(raw) > artifact["size"]
                        or chunk.get("eof") is not (offset + len(raw) == artifact["size"])):
                    raise JobError("CONFLICT", "Retained evidence readback identity, size or digest differs")
                sha.update(raw); offset += len(raw)
                if chunk["eof"]:
                    break
                if not raw:
                    raise JobError("CONFLICT", "Retained readback did not advance")
            if sha.hexdigest() != artifact["sha256"]:
                raise JobError("CONFLICT", "Retained artifact full-byte digest differs")
        if read("lh_job_status", status_args) != status:
            raise JobError("CONFLICT", "Original task changed during retained verification")
        result.append({**task, "status_digest": fingerprint(status), "catalog_digest": catalog,
                       "artifacts": artifacts})
    if request({"action": "deployment_retention_index"})["tasks"] != tasks:
        raise JobError("CONFLICT", "Retained task routes changed during verification")
    return {"schema": "local-hand-retained-readback/v1", "tasks": result, "bytes_verified": total}
